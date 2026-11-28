"""Residual P0-03 regressions: bounded connection admission, absolute request
deadlines, and an isolated, terminable parser process with real cleanup.

Reviewer residual review #7235517859: ``ThreadingHTTPServer`` spawned connection
threads before the parser semaphore; a socket timeout is not an absolute deadline;
``WorkerCore`` parsed in-process with cooperative checks only, so a parser blocked
in native code could never be hard-cancelled. These lock the fixes and demonstrate
that a deliberately stalled parser is terminated and the next valid OCR succeeds.
"""

from __future__ import annotations

import json
import os
import socket
import threading
import time
import uuid
from pathlib import Path

import pytest

from backend.app.term1_c2_documents import constants as C
from backend.app.term1_c2_documents.fixture_manifest import load_manifest
from backend.app.term1_c2_documents.parser_process import (
    ParserContainmentError,
    _descendant_stall_child,
    _ignore_term_stall_child,
    _network_probe_child,
    _oversized_ipc_child,
    _partial_ipc_child,
    _stall_child,
    run_parse_isolated,
    spawn_and_wait,
)
from backend.app.term1_c2_documents.storage import PrivateDocStore, make_storage_key
from backend.app.term1_c2_documents.worker import build_server

from .conftest import ocr_engine_config, requires_native_ocr

FIXTURES = Path(__file__).resolve().parents[3] / "backend" / "app" / "term1_c2_documents" / "fixtures"
TOKEN = "c2-test-parser-iso-token-000000000001"


def _serve(store, **kwargs):
    server = build_server(port=0, store=store, engine_config=ocr_engine_config(),
                          token=TOKEN, manifest=load_manifest(), **kwargs)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port, thread


def _request_bytes(path, body):
    return (
        f"POST {path} HTTP/1.1\r\nHost: 127.0.0.1\r\n"
        f"Authorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\n"
        f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n"
    ).encode() + body


def _drain(sock):
    data = b""
    sock.settimeout(5)
    try:
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
    except OSError:
        pass
    return data


# --- isolated, terminable parser --------------------------------------------
def test_stalled_parser_is_terminated_and_reaped():
    # A parser that blocks indefinitely is hard-killed at the absolute deadline.
    result, proc = spawn_and_wait(_stall_child, (), time.monotonic() + 0.5)
    assert result["ok"] is False
    assert result["reason"] == "deadline_exceeded"
    assert not proc.is_alive()                 # reaped, no zombie
    assert proc.exitcode is not None and proc.exitcode != 0  # killed by signal


@pytest.mark.skipif(
    os.name == "nt",
    reason="SIGTERM-ignore behavior is POSIX-only; Windows uses Job Object termination",
)
def test_parser_that_ignores_sigterm_is_hard_killed_within_cleanup_bound():
    started = time.monotonic()
    result, proc = spawn_and_wait(
        _ignore_term_stall_child, (), started + 5
    )
    elapsed = time.monotonic() - started
    assert result["ok"] is True
    assert not proc.is_alive()
    assert proc.exitcode is not None and proc.exitcode != 0
    assert elapsed < 4.5  # startup plus one bounded TERM grace and hard-kill reap


def _pid_is_running(pid: int) -> bool:
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.GetExitCodeProcess.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
        if not handle:
            return ctypes.get_last_error() == 5  # access denied means it still exists
        try:
            code = wintypes.DWORD()
            return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code)) and code.value == 259)
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    # A zombie has exited and cannot execute parser/native code; Linux subreaper
    # should reap it before this assertion, but treat it as not running if seen.
    stat_path = Path(f"/proc/{pid}/stat")
    if stat_path.exists():
        try:
            return stat_path.read_text().split()[2] != "Z"
        except (OSError, IndexError):
            pass
    return True


def test_parser_terminates_and_reaps_a_live_descendant():
    result, proc = spawn_and_wait(
        _descendant_stall_child, (), time.monotonic() + 5
    )
    assert result["ok"] is True
    assert isinstance(result.get("descendant_pid"), int)
    assert not proc.is_alive()
    assert not _pid_is_running(result["descendant_pid"])


def test_parser_ipc_rejects_oversized_frames():
    result, proc = spawn_and_wait(
        _oversized_ipc_child, (), time.monotonic() + 5
    )
    assert result["ok"] is False
    assert result["reason"] == "ipc_response_too_large"
    assert not proc.is_alive()


def test_partial_parser_ipc_frame_stays_within_absolute_deadline():
    started = time.monotonic()
    result, proc = spawn_and_wait(
        _partial_ipc_child, (), started + 0.5
    )
    elapsed = time.monotonic() - started
    assert result["reason"] == "deadline_exceeded"
    assert elapsed < 4  # includes only the bounded termination grace
    assert not proc.is_alive()


def test_receiver_thread_start_failure_still_terminates_parser(monkeypatch):
    import backend.app.term1_c2_documents.parser_process as pmod

    original_start = threading.Thread.start

    def fail_receiver_start(thread):
        if thread.name == "ocr-parser-ipc-receiver":
            raise RuntimeError("simulated thread-start failure")
        return original_start(thread)

    monkeypatch.setattr(pmod.threading.Thread, "start", fail_receiver_start)
    result, proc = spawn_and_wait(_stall_child, (), time.monotonic() + 5)
    assert result["reason"] == "parser_start_failed"
    assert not proc.is_alive()


def test_containment_cleanup_error_is_raised_after_pipe_and_thread_cleanup(monkeypatch):
    import backend.app.term1_c2_documents.parser_process as pmod

    original_cleanup = pmod._terminate_and_reap
    processes = []

    def cleanup_then_report_failure(proc, **kwargs):
        original_cleanup(proc, **kwargs)
        processes.append(proc)
        raise ParserContainmentError("simulated failed cleanup verification")

    monkeypatch.setattr(pmod, "_terminate_and_reap", cleanup_then_report_failure)
    with pytest.raises(ParserContainmentError, match="failed cleanup verification"):
        spawn_and_wait(_network_probe_child, (), time.monotonic() + 5)
    assert len(processes) == 1 and not processes[0].is_alive()
    assert not any(
        thread.name == "ocr-parser-ipc-receiver" and thread.is_alive()
        for thread in threading.enumerate()
    )


@requires_native_ocr
def test_next_valid_ocr_succeeds_after_stall_kill(tmp_path):
    store = PrivateDocStore(tmp_path / "docs")
    data = (FIXTURES / "resting.png").read_bytes()
    key = make_storage_key(str(uuid.uuid4()), str(uuid.uuid4()))
    store.promote(store.stage(data, key), key)
    cfg = ocr_engine_config()
    # Stall and kill a parser first.
    result, proc = spawn_and_wait(_stall_child, (), time.monotonic() + 0.5)
    assert result["reason"] == "deadline_exceeded" and not proc.is_alive()
    # The next genuine raster OCR succeeds (native Tesseract, not a stub).
    out = run_parse_isolated("extract", data, C.MEDIA_PNG, cfg, time.monotonic() + 30)
    assert out["ok"] is True
    assert out["mode"] == C.MODE_RASTER_OCR
    assert out["engine_name"] == "tesseract"
    assert "54" in out["full_text"]


def test_parser_child_blocks_outbound_network():
    result, proc = spawn_and_wait(_network_probe_child, (), time.monotonic() + 10)
    assert result["ok"] is True
    assert result["blocked"] is True  # no remote call possible from the parser


def test_isolated_extract_matches_inprocess(tmp_path):
    from backend.app.term1_c2_documents.parser_process import parse_inprocess
    data = (FIXTURES / "resting_text.pdf").read_bytes()
    cfg = ocr_engine_config()
    isolated = run_parse_isolated("extract", data, C.MEDIA_PDF, cfg, time.monotonic() + 30)
    inproc = parse_inprocess("extract", data, C.MEDIA_PDF, cfg)
    assert isolated["ok"] is True and inproc["ok"] is True
    assert isolated["mode"] == inproc["mode"] == C.MODE_PDF_TEXT
    assert isolated["full_text"] == inproc["full_text"]
    assert isolated["raw_text_sha256"] == inproc["raw_text_sha256"]


# --- bounded connection admission -------------------------------------------
@pytest.mark.parametrize("failure_kind", ["cleanup_exception", "isolation_setup"])
def test_worker_poisoned_after_process_tree_failure(tmp_path, monkeypatch, failure_kind):
    import hashlib
    import backend.app.term1_c2_documents.worker as wmod

    data = (FIXTURES / "resting_text.pdf").read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    manifest = load_manifest()
    entry = manifest.lookup(digest)
    assert entry is not None
    store = PrivateDocStore(tmp_path / "docs")
    key = make_storage_key(str(uuid.uuid4()), str(uuid.uuid4()))
    store.promote(store.stage(data, key), key)
    calls = []

    def fail_containment(*_args, **_kwargs):
        calls.append("spawn")
        if failure_kind == "cleanup_exception":
            raise ParserContainmentError("simulated inability to prove process-tree cleanup")
        return {
            "ok": False, "code": "worker_unavailable",
            "reason": "process_tree_isolation_failed",
        }

    monkeypatch.setattr(wmod, "run_parse_isolated", fail_containment)
    server, port, thread = _serve(store)
    body = json.dumps({
        "storage_key": key,
        "content_sha256": digest,
        "byte_size": len(data),
        "declared_media_type": entry.media_type,
        "fixture_file_sha256": digest,
    }).encode()
    try:
        for _ in range(2):
            sock = socket.create_connection(("127.0.0.1", port), timeout=5)
            try:
                sock.sendall(_request_bytes(C.IPC_VALIDATE_PATH, body))
                response = _drain(sock)
                assert b" 503 " in response
                assert b"parser_containment_failed" in response
            finally:
                sock.close()
        assert calls == ["spawn"]  # second request was refused before parser dispatch
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_worker_bounds_connections(tmp_path, monkeypatch):
    import backend.app.term1_c2_documents.worker as wmod

    started = threading.Event()
    release = threading.Event()

    def slow_extract(self, **kwargs):
        started.set()
        release.wait(timeout=10)
        return {"ok": False, "code": "worker_unavailable", "reason": "done"}

    monkeypatch.setattr(wmod.WorkerCore, "extract", slow_extract)
    store = PrivateDocStore(tmp_path / "docs")
    server, port, thread = _serve(store, max_concurrency=1, max_connections=1)
    sha = next(iter(load_manifest().entries))
    entry = load_manifest().lookup(sha)
    body = json.dumps({
        "document_id": str(uuid.uuid4()), "storage_key": f"{uuid.uuid4()}/{uuid.uuid4()}.bin",
        "content_sha256": sha, "byte_size": entry.byte_size,
        "declared_media_type": entry.media_type, "fixture_template_id": entry.template_id,
        "fixture_file_sha256": sha,
    }).encode()
    raw = _request_bytes(C.IPC_EXTRACT_PATH, body)
    s1 = socket.create_connection(("127.0.0.1", port), timeout=10)
    try:
        s1.sendall(raw)
        assert started.wait(timeout=10)  # first connection holds the only slot
        # A second connection is refused at accept time: NO HTTP response.
        s2 = socket.create_connection(("127.0.0.1", port), timeout=10)
        try:
            try:
                s2.sendall(raw)
            except OSError:
                pass
            data = _drain(s2)
            assert b"HTTP/" not in data  # closed before any reply (admission refused)
        finally:
            s2.close()
        release.set()
    finally:
        s1.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


# --- absolute request deadline ----------------------------------------------
def test_absolute_request_deadline_bounds_dribbled_body(tmp_path, monkeypatch):
    # A short absolute deadline so the test is fast; the body is dribbled and then
    # stalled past the deadline. A per-socket timeout alone would not bound this.
    monkeypatch.setattr(C, "WORKER_REQUEST_DEADLINE_SECONDS", 0.5)
    store = PrivateDocStore(tmp_path / "docs")
    server, port, thread = _serve(store)
    headers = (
        f"POST {C.IPC_VALIDATE_PATH} HTTP/1.1\r\nHost: 127.0.0.1\r\n"
        f"Authorization: Bearer {TOKEN}\r\nContent-Length: 100\r\nConnection: close\r\n\r\n"
    ).encode()
    s = socket.create_connection(("127.0.0.1", port), timeout=10)
    try:
        s.sendall(headers + b"x" * 10)  # only 10 of 100 body bytes, then stall
        time.sleep(0.8)                  # exceed the 0.5s absolute deadline
        data = _drain(s)
        assert b"408" in data            # deadline_exceeded, not an unbounded wait
        assert b"deadline_exceeded" in data
    finally:
        s.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_absolute_request_deadline_bounds_dribbled_headers(tmp_path, monkeypatch):
    # Header parsing used to reset the socket timeout for every partial read;
    # the first byte must not hold a bounded connection slot past the deadline.
    monkeypatch.setattr(C, "WORKER_REQUEST_DEADLINE_SECONDS", 0.5)
    monkeypatch.setattr(C, "WORKER_READ_TIMEOUT_SECONDS", 2.0)
    store = PrivateDocStore(tmp_path / "docs")
    server, port, thread = _serve(store)
    sock = socket.create_connection(("127.0.0.1", port), timeout=2)
    started = time.monotonic()
    try:
        sock.sendall(b"P")  # incomplete request line
        response = sock.recv(1)
        elapsed = time.monotonic() - started
        assert response == b""  # timed-out incomplete request is closed
        assert elapsed < 1.5
    finally:
        sock.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
