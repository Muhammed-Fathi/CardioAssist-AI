"""Isolated parser execution with whole-process-tree containment (P0-03).

All potentially blocking parser work runs in a spawned process with no store,
database or backend secrets. The supervisor gives it a separate POSIX session or
assigns it to a Windows Job Object *before* releasing it to parse. That boundary
contains native Tesseract and any other subprocess descendants. IPC is framed,
JSON-only and capped; a receiver thread prevents a partial frame from blocking
past the absolute monotonic deadline. Every wait/join is bounded.

On Linux the dedicated OCR-worker supervisor is marked as a child subreaper so
it can wait for orphaned parser descendants after killing the process group. On
Windows the Job Object uses KILL_ON_JOB_CLOSE and its active-process count is
checked before the worker slot is released. The worker is a separate unprivileged
account/process; this module never loads model bundles or dispatches inference.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import queue
import signal
import struct
import subprocess
import sys
import threading
import time
from dataclasses import asdict
from typing import Any

from . import constants as C


class ParserContainmentError(RuntimeError):
    """The parser process tree could not be conclusively terminated and reaped."""


def parse_inprocess(kind: str, data: bytes, media_type: str, engine_config) -> dict:
    """Run the genuine parse and map typed failures to a structured result.

    Shared by the in-process path and the isolated child so both produce the
    identical result contract. ``kind`` is ``"validate"`` or ``"extract"``.
    """
    from .admission import AdmissionError, validate_structure
    from .extraction_types import (
        ExtractionDeadlineError,
        ExtractionLimitError,
        OcrUnavailableError,
    )

    try:
        if kind == "validate":
            info = validate_structure(data, media_type)
            return {
                "ok": True,
                "page_count": info.page_count,
                "pixel_width": info.pixel_width,
                "pixel_height": info.pixel_height,
            }
        from .ocr_engine import extract

        raw = extract(data, media_type, engine_config)
        return {
            "ok": True,
            "mode": raw.mode,
            "engine_name": raw.engine_name,
            "engine_version": raw.engine_version,
            "page_count": raw.page_count,
            "pixel_width": raw.pixel_width,
            "pixel_height": raw.pixel_height,
            "full_text": raw.full_text,
            "raw_text_sha256": raw.raw_text_sha256,
            "extracted_text_bytes": raw.extracted_text_bytes,
            "lines": [asdict(line) for line in raw.lines],
        }
    except AdmissionError as error:
        return {"ok": False, "code": error.code}
    except OcrUnavailableError:
        return {"ok": False, "code": "worker_unavailable", "reason": "ocr_unavailable"}
    except ExtractionDeadlineError:
        return {"ok": False, "code": "worker_unavailable", "reason": "deadline_exceeded"}
    except ExtractionLimitError:
        return {"ok": False, "code": "invalid_document_content", "reason": "limit_exceeded"}
    except Exception:  # noqa: BLE001 - normalize any unexpected parser failure
        return {"ok": False, "code": "worker_unavailable", "reason": "parser_error"}


def _block_outbound_network() -> None:
    """Disable outbound network in the parser child (defence in depth).

    The genuine parser uses only local libraries and a Tesseract subprocess; it
    never needs a socket. Blocking connect/sendto guarantees no remote call or
    exfiltration even if a dependency were to attempt one.
    """
    import socket

    def _deny(*_args, **_kwargs):
        raise OSError("Outbound network is disabled in the isolated parser child.")

    socket.socket.connect = _deny
    socket.socket.connect_ex = _deny
    socket.socket.sendto = _deny
    socket.create_connection = _deny


def _send_json(conn, result: dict[str, Any]) -> None:
    """Send one bounded JSON frame; never pickle arbitrary parser output."""
    try:
        payload = json.dumps(
            result, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        payload = b'{"ok":false,"code":"worker_unavailable","reason":"malformed_parser_result"}'
    if len(payload) > C.OCR_IPC_RESPONSE_CAP_BYTES:
        payload = b'{"ok":false,"code":"worker_unavailable","reason":"response_cap"}'
    try:
        conn.send_bytes(payload)
    except (BrokenPipeError, EOFError, OSError):
        # The supervisor may have hit the absolute deadline and closed the pipe.
        pass


def _child_entry(conn, kind: str, data: bytes, media_type: str, engine_config) -> None:
    """Child body: parse once, send the structured result, and return."""
    try:
        _block_outbound_network()
        result = parse_inprocess(kind, data, media_type, engine_config)
    except BaseException:  # noqa: BLE001 - never leave the parent waiting silently
        result = {"ok": False, "code": "worker_unavailable", "reason": "parser_error"}
    _send_json(conn, result)


def _stall_child(_conn) -> None:
    """Diagnostic parser that blocks indefinitely (regression test only)."""
    while True:
        time.sleep(3600)


def _ignore_term_stall_child(conn) -> None:
    """Diagnostic parser that ignores graceful termination (regression only)."""
    if os.name != "nt":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    _send_json(conn, {"ok": True})
    while True:
        time.sleep(3600)


def _network_probe_child(conn) -> None:
    """Diagnostic child: confirm outbound network is blocked (regression only)."""
    import socket

    _block_outbound_network()
    try:
        socket.create_connection(("127.0.0.1", 9), timeout=1)
        blocked = False
    except OSError:
        blocked = True
    _send_json(conn, {"ok": True, "blocked": blocked})


def _descendant_stall_child(conn) -> None:
    """Diagnostic parent with a live native-style subprocess descendant."""
    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(300)"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )
    _send_json(conn, {"ok": True, "descendant_pid": child.pid})
    while True:
        time.sleep(3600)


def _oversized_ipc_child(conn) -> None:
    """Diagnostic child that attempts to exceed the bounded IPC frame cap."""
    conn.send_bytes(b"x" * (C.OCR_IPC_RESPONSE_CAP_BYTES + 1))


def _partial_ipc_child(conn) -> None:
    """Write an incomplete frame then stall, proving recv stays deadline-bound."""
    # Connection._send writes the same four-byte length prefix used by
    # send_bytes, but intentionally withholds the rest of the advertised frame.
    conn._send(struct.pack("!i", 4096) + b"{")
    while True:
        time.sleep(3600)


def _enable_linux_subreaper() -> None:
    """Make this isolated OCR supervisor reap killed parser grandchildren."""
    if not sys.platform.startswith("linux"):
        return
    libc = __import__("ctypes").CDLL(None, use_errno=True)
    # Linux PR_SET_CHILD_SUBREAPER. The OCR daemon is a dedicated process, so
    # this does not alter the API backend's child-reaping policy.
    if libc.prctl(36, 1, 0, 0, 0) != 0:
        error_number = __import__("ctypes").get_errno()
        raise ParserContainmentError(
            f"Cannot enable OCR parser child reaping (errno={error_number})."
        )


class _WindowsJob:
    """KILL_ON_JOB_CLOSE process-tree boundary for Windows native parsers."""

    def __init__(self) -> None:
        import ctypes
        from ctypes import wintypes

        self._ctypes = ctypes
        self._wintypes = wintypes
        self._kernel = ctypes.WinDLL("kernel32", use_last_error=True)

        class _BasicLimit(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class _IoCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount",
            )]

        class _ExtendedLimit(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", _BasicLimit),
                ("IoInfo", _IoCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        class _BasicAccounting(ctypes.Structure):
            _fields_ = [
                ("TotalUserTime", ctypes.c_longlong),
                ("TotalKernelTime", ctypes.c_longlong),
                ("ThisPeriodTotalUserTime", ctypes.c_longlong),
                ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
                ("TotalPageFaultCount", wintypes.DWORD),
                ("TotalProcesses", wintypes.DWORD),
                ("ActiveProcesses", wintypes.DWORD),
                ("TotalTerminatedProcesses", wintypes.DWORD),
            ]

        self._BasicAccounting = _BasicAccounting
        self._kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self._kernel.CreateJobObjectW.restype = wintypes.HANDLE
        self._kernel.SetInformationJobObject.argtypes = [
            wintypes.HANDLE, wintypes.INT, ctypes.c_void_p, wintypes.DWORD,
        ]
        self._kernel.SetInformationJobObject.restype = wintypes.BOOL
        self._kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self._kernel.AssignProcessToJobObject.restype = wintypes.BOOL
        self._kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self._kernel.TerminateJobObject.restype = wintypes.BOOL
        self._kernel.QueryInformationJobObject.argtypes = [
            wintypes.HANDLE, wintypes.INT, ctypes.c_void_p, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]
        self._kernel.QueryInformationJobObject.restype = wintypes.BOOL
        self._kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self._kernel.CloseHandle.restype = wintypes.BOOL

        self.handle = self._kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise ParserContainmentError("CreateJobObjectW failed for the OCR parser.")
        self.assigned = False
        self.closed = False
        limits = _ExtendedLimit()
        limits.BasicLimitInformation.LimitFlags = 0x00002000  # KILL_ON_JOB_CLOSE
        if not self._kernel.SetInformationJobObject(
            self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
        ):
            self.close()
            raise ParserContainmentError("Cannot set KILL_ON_JOB_CLOSE on OCR Job Object.")

    def assign(self, process: mp.process.BaseProcess) -> None:
        handle = getattr(getattr(process, "_popen", None), "_handle", None)
        if handle is None or not self._kernel.AssignProcessToJobObject(
            self.handle, self._wintypes.HANDLE(int(handle))
        ):
            raise ParserContainmentError("AssignProcessToJobObject failed for OCR parser.")
        self.assigned = True

    def terminate(self) -> None:
        if self.assigned and not self._kernel.TerminateJobObject(self.handle, 1):
            raise ParserContainmentError("TerminateJobObject failed for OCR parser tree.")

    def wait_empty(self, timeout: float) -> bool:
        end = time.monotonic() + max(0.0, timeout)
        while True:
            info = self._BasicAccounting()
            if not self._kernel.QueryInformationJobObject(
                self.handle, 1, self._ctypes.byref(info), self._ctypes.sizeof(info), None
            ):
                return False
            if info.ActiveProcesses == 0:
                return True
            remaining = end - time.monotonic()
            if remaining <= 0:
                return False
            time.sleep(min(0.01, remaining))

    def close(self) -> None:
        if not self.closed and self.handle:
            # KILL_ON_JOB_CLOSE is the final backstop for every assigned
            # descendant, including native Tesseract children.
            self._kernel.CloseHandle(self.handle)
            self.closed = True


def _process_group_exists(group_id: int) -> bool:
    try:
        os.killpg(group_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _reap_linux_group_children(group_id: int, timeout: float) -> bool:
    """Wait for adopted children in a parser process group, within ``timeout``."""
    end = time.monotonic() + max(0.0, timeout)
    while True:
        reaped_any = False
        while True:
            try:
                child_pid, _status = os.waitpid(-group_id, os.WNOHANG)
            except ChildProcessError:
                child_pid = 0
                break
            except OSError as error:
                if error.errno == 10:  # ECHILD
                    child_pid = 0
                    break
                raise ParserContainmentError("waitpid failed for OCR parser descendants.") from error
            if child_pid <= 0:
                break
            reaped_any = True
        if not _process_group_exists(group_id):
            return True
        remaining = end - time.monotonic()
        if remaining <= 0:
            return False
        if not reaped_any:
            time.sleep(min(0.01, remaining))


def _terminate_direct_process(proc: mp.process.BaseProcess, grace: float) -> None:
    """Bounded fallback for a child that never established its isolation group."""
    if proc.is_alive():
        try:
            proc.terminate()
        except (OSError, ValueError):
            # It may have exited between is_alive() and the signal call. The
            # bounded join + second liveness check decides whether cleanup held.
            pass
        proc.join(timeout=grace)
    if proc.is_alive():
        try:
            proc.kill()
        except (OSError, ValueError):
            pass
        proc.join(timeout=grace)
    if proc.is_alive():
        raise ParserContainmentError("OCR parser process survived bounded termination.")


def _terminate_and_reap(
    proc: mp.process.BaseProcess,
    *,
    isolated_group: bool,
    job: _WindowsJob | None,
) -> None:
    """Kill every parser descendant and reap the leader without unbounded joins."""
    grace = C.WORKER_PARSER_KILL_GRACE_SECONDS
    if os.name == "nt":
        try:
            if job is not None and job.assigned:
                # First stop the parser leader; then hard-terminate any remaining
                # native descendants and wait for the job's active count to hit 0.
                if proc.is_alive():
                    try:
                        proc.terminate()
                    except (OSError, ValueError):
                        pass  # process may have exited between the liveness check and signal
                    proc.join(timeout=grace)
                job.terminate()
                empty = job.wait_empty(grace)
                job.close()
                if proc.is_alive():
                    try:
                        proc.kill()
                    except (OSError, ValueError):
                        pass
                    proc.join(timeout=grace)
                if not empty:
                    raise ParserContainmentError(
                        "OCR Job Object still had active descendants after bounded termination."
                    )
            else:
                _terminate_direct_process(proc, grace)
        finally:
            if job is not None:
                job.close()
        if proc.is_alive():
            raise ParserContainmentError("OCR parser leader survived Job Object termination.")
        return

    if not isolated_group:
        _terminate_direct_process(proc, grace)
        return

    group_id = proc.pid
    try:
        os.killpg(group_id, signal.SIGTERM)
    except ProcessLookupError:
        pass
    except OSError as error:
        raise ParserContainmentError("Cannot signal OCR parser process group.") from error

    if proc.is_alive():
        proc.join(timeout=grace)
    if _process_group_exists(group_id):
        try:
            os.killpg(group_id, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except OSError as error:
            raise ParserContainmentError("Cannot kill OCR parser process group.") from error
    if proc.is_alive():
        try:
            proc.kill()
        except (OSError, ValueError):
            pass  # process may have exited between the liveness check and signal
        proc.join(timeout=grace)
    if proc.is_alive():
        raise ParserContainmentError("OCR parser leader survived bounded group termination.")

    if sys.platform.startswith("linux"):
        descendants_gone = _reap_linux_group_children(group_id, grace)
    else:
        end = time.monotonic() + grace
        while _process_group_exists(group_id) and time.monotonic() < end:
            time.sleep(min(0.01, max(0.0, end - time.monotonic())))
        descendants_gone = not _process_group_exists(group_id)
    if not descendants_gone:
        raise ParserContainmentError("OCR parser descendants survived bounded group termination.")


def _process_wrapper(conn, ready, release, setup_status, deadline, entry, args) -> None:
    """Establish isolation, wait for parent assignment, then invoke one entry."""
    try:
        if os.name != "nt":
            os.setsid()
        setup_status.value = 1
    except BaseException:  # noqa: BLE001 - failure to isolate is a hard refusal
        setup_status.value = -1
        ready.set()
        _send_json(conn, {
            "ok": False, "code": "worker_unavailable",
            "reason": "process_tree_isolation_failed",
        })
        conn.close()
        return

    ready.set()
    remaining = deadline - time.monotonic()
    if remaining <= 0 or not release.wait(timeout=remaining):
        _send_json(conn, {
            "ok": False, "code": "worker_unavailable", "reason": "deadline_exceeded",
        })
        conn.close()
        return
    try:
        entry(conn, *args)
    except BaseException:  # noqa: BLE001 - never leave the parent waiting silently
        _send_json(conn, {
            "ok": False, "code": "worker_unavailable", "reason": "parser_error",
        })
    finally:
        conn.close()


def _receive_bounded_frame(conn, output: queue.Queue) -> None:
    """Blocking receiver isolated in a daemon thread; parent waits by deadline."""
    try:
        payload = conn.recv_bytes(maxlength=C.OCR_IPC_RESPONSE_CAP_BYTES)
    except EOFError:
        message = ("eof", None)
    except OSError:
        message = ("oversized", None)
    else:
        message = ("frame", payload)
    try:
        output.put_nowait(message)
    except queue.Full:  # defensive; only one frame is accepted
        pass


def _decode_frame(payload: bytes) -> dict:
    try:
        result = json.loads(payload.decode("utf-8"))
    except (UnicodeError, ValueError):
        return {
            "ok": False, "code": "worker_unavailable",
            "reason": "malformed_parser_result",
        }
    if not isinstance(result, dict) or not isinstance(result.get("ok"), bool):
        return {
            "ok": False, "code": "worker_unavailable",
            "reason": "malformed_parser_result",
        }
    return result


def spawn_and_wait(entry, args: tuple, deadline: float) -> tuple[dict, mp.process.BaseProcess]:
    """Run ``entry(conn, *args)`` under a strict IPC and absolute deadline.

    ``deadline`` is an absolute ``time.monotonic()`` timestamp covering child
    startup, the parent/child isolation handshake, parsing and IPC reception.
    Process-tree teardown and all joins are separately bounded by the configured
    kill grace; failure to prove cleanup raises :class:`ParserContainmentError`.
    """
    ctx = mp.get_context("spawn")
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    ready = ctx.Event()
    release = ctx.Event()
    setup_status = ctx.Value("i", 0)
    proc = ctx.Process(
        target=_process_wrapper,
        args=(child_conn, ready, release, setup_status, deadline, entry, args),
    )
    job = None
    started = False
    receiver = None
    receiver_started = False
    output: queue.Queue = queue.Queue(maxsize=1)
    result = {
        "ok": False, "code": "worker_unavailable", "reason": "deadline_exceeded",
    }
    try:
        if os.name == "nt":
            job = _WindowsJob()
        else:
            _enable_linux_subreaper()
        proc.start()
        started = True
        child_conn.close()

        remaining = deadline - time.monotonic()
        if remaining > 0 and ready.wait(timeout=remaining):
            if setup_status.value == 1:
                if os.name == "nt":
                    assert job is not None
                    job.assign(proc)
                receiver = threading.Thread(
                    target=_receive_bounded_frame,
                    args=(parent_conn, output),
                    name="ocr-parser-ipc-receiver",
                    daemon=True,
                )
                receiver.start()
                receiver_started = True
                release.set()
                remaining = deadline - time.monotonic()
                if remaining > 0:
                    try:
                        kind, payload = output.get(timeout=remaining)
                    except queue.Empty:
                        kind, payload = "timeout", None
                    if kind == "frame":
                        result = _decode_frame(payload)
                    elif kind == "oversized":
                        result = {
                            "ok": False, "code": "worker_unavailable",
                            "reason": "ipc_response_too_large",
                        }
                    elif kind == "eof":
                        result = {
                            "ok": False, "code": "worker_unavailable",
                            "reason": "parser_crashed",
                        }
            else:
                # Isolation setup failed; the child sends a small structured
                # error frame and exits without parsing or spawning descendants.
                receiver = threading.Thread(
                    target=_receive_bounded_frame,
                    args=(parent_conn, output),
                    name="ocr-parser-ipc-receiver",
                    daemon=True,
                )
                receiver.start()
                receiver_started = True
                remaining = deadline - time.monotonic()
                if remaining > 0:
                    try:
                        kind, payload = output.get(timeout=remaining)
                    except queue.Empty:
                        kind, payload = "timeout", None
                    if kind == "frame":
                        result = _decode_frame(payload)
                    elif kind == "oversized":
                        result = {
                            "ok": False, "code": "worker_unavailable",
                            "reason": "ipc_response_too_large",
                        }
                    elif kind == "eof":
                        result = {
                            "ok": False, "code": "worker_unavailable",
                            "reason": "parser_crashed",
                        }
    except ParserContainmentError:
        result = {
            "ok": False, "code": "worker_unavailable",
            "reason": "process_tree_isolation_failed",
        }
    except (OSError, RuntimeError, ValueError):
        result = {
            "ok": False, "code": "worker_unavailable", "reason": "parser_start_failed",
        }
    finally:
        cleanup_error: ParserContainmentError | None = None
        try:
            if started:
                _terminate_and_reap(
                    proc,
                    isolated_group=setup_status.value == 1 and os.name != "nt",
                    job=job,
                )
            elif job is not None:
                job.close()
        except ParserContainmentError as error:
            cleanup_error = error
        except BaseException as error:  # noqa: BLE001 - cleanup errors fail closed
            cleanup_error = ParserContainmentError(
                "Unexpected error while cleaning up the OCR parser process tree."
            )
            cleanup_error.__cause__ = error

        # Always release both pipe handles, even when process-tree verification
        # failed. Closing the receive end also gives a stuck receiver thread a
        # chance to leave its bounded recv before we report containment failure.
        for conn in (parent_conn, child_conn):
            try:
                conn.close()
            except OSError as error:
                if cleanup_error is None:
                    cleanup_error = ParserContainmentError(
                        "Cannot close OCR parser IPC handles."
                    )
                    cleanup_error.__cause__ = error
        if receiver_started:
            try:
                receiver.join(timeout=C.WORKER_PARSER_KILL_GRACE_SECONDS)
            except BaseException as error:  # noqa: BLE001 - do not mask containment failure
                if cleanup_error is None:
                    cleanup_error = ParserContainmentError(
                        "Cannot join the OCR parser IPC receiver thread."
                    )
                    cleanup_error.__cause__ = error
            if receiver.is_alive() and cleanup_error is None:
                cleanup_error = ParserContainmentError(
                    "OCR parser IPC receiver survived bounded shutdown."
                )
        if cleanup_error is not None:
            raise cleanup_error
    return result, proc


def run_parse_isolated(kind: str, data: bytes, media_type: str, engine_config,
                       deadline: float) -> dict:
    """Parse in an isolated, terminable process tree bounded by ``deadline``."""
    result, _proc = spawn_and_wait(
        _child_entry, (kind, data, media_type, engine_config), deadline
    )
    return result
