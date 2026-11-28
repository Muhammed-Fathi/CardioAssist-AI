"""Isolated, terminable parser execution for the OCR worker (residual P0-03).

The worker's expensive, potentially-blocking work (``pdfminer`` text extraction,
``pypdfium2`` rasterization, native Tesseract OCR, structural validation) runs in a
**separate spawn-context child process** that the parent can hard-terminate. A
cooperative deadline check inside the engine is not enough: a parser blocked in
native code never reaches the check. Here the parent waits only until an absolute
deadline and then ``terminate()`` → ``kill()`` the child and reap it, so a stalled
parser can never hold a worker slot indefinitely and the next request proceeds.

Isolation properties:

* ``spawn`` (not ``fork``) gives a fresh interpreter with no inherited backend
  state, locks or secrets — safe to start from the multi-threaded HTTP server;
* the child receives only the already-verified document bytes, the media type and
  the engine config; it has no store, database or secret access;
* outbound network is disabled in the child (defence in depth): the genuine
  parser performs only local extraction and never makes a remote call or runs
  inference;
* the child maps every typed failure to the same structured result dict the
  in-process path produces, so the caller's response contract is identical.

This module is stdlib-only at import time; the OCR dependencies are imported
lazily inside the parse so the parent server import stays light.
"""

from __future__ import annotations

import multiprocessing as mp
import time
from dataclasses import asdict

from . import constants as C


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


def _child_entry(conn, kind: str, data: bytes, media_type: str, engine_config) -> None:
    """Child process body: parse once, send the structured result, exit."""
    try:
        _block_outbound_network()
        result = parse_inprocess(kind, data, media_type, engine_config)
        conn.send(result)
    except BaseException:  # noqa: BLE001 - never leave the parent waiting silently
        try:
            conn.send({"ok": False, "code": "worker_unavailable", "reason": "parser_error"})
        except Exception:  # noqa: BLE001
            pass
    finally:
        conn.close()


def _stall_child(conn) -> None:
    """Diagnostic child that blocks indefinitely (P0-03 regression evidence).

    Used only by the regression test to prove a deliberately stalled parser is
    hard-terminated by the parent and the next valid parse still succeeds. It is
    never used by the production parse path.
    """
    try:
        while True:
            time.sleep(3600)
    finally:
        conn.close()


def _network_probe_child(conn) -> None:
    """Diagnostic child: confirm outbound network is blocked (P0-03 evidence).

    Applies the same network block as the real parser child, then attempts an
    outbound connection and reports whether it was refused. Never used by the
    production parse path.
    """
    import socket

    try:
        _block_outbound_network()
        try:
            socket.create_connection(("127.0.0.1", 9), timeout=1)
            blocked = False
        except OSError:
            blocked = True
        conn.send({"ok": True, "blocked": blocked})
    finally:
        conn.close()


def _terminate_and_reap(proc: mp.process.BaseProcess) -> None:
    """Terminate, then kill if needed, and always reap the child (no zombie)."""
    grace = C.WORKER_PARSER_KILL_GRACE_SECONDS
    if proc.is_alive():
        proc.terminate()
        proc.join(timeout=grace)
        if proc.is_alive():
            proc.kill()
            proc.join(timeout=grace)
    else:
        proc.join(timeout=grace)
    if proc.is_alive():  # last resort: force kill and reap
        proc.kill()
        proc.join()


def spawn_and_wait(entry, args: tuple, deadline: float) -> tuple[dict, mp.process.BaseProcess]:
    """Run ``entry(conn, *args)`` in a spawn child bounded by an absolute deadline.

    Returns ``(result, process)``. On deadline expiry the child is terminated and
    reaped and a ``deadline_exceeded`` result is returned. The process is always
    reaped before return so the caller can inspect ``exitcode``/``is_alive``.
    """
    ctx = mp.get_context("spawn")
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=entry, args=(child_conn, *args))
    proc.start()
    child_conn.close()  # parent holds only the read end; detect child EOF
    try:
        remaining = deadline - time.monotonic()
        if remaining > 0 and parent_conn.poll(remaining):
            try:
                result = parent_conn.recv()
            except (EOFError, OSError):
                return {"ok": False, "code": "worker_unavailable",
                        "reason": "parser_crashed"}, proc
            if isinstance(result, dict) and "ok" in result:
                return result, proc
            return {"ok": False, "code": "worker_unavailable",
                    "reason": "malformed_parser_result"}, proc
        return {"ok": False, "code": "worker_unavailable", "reason": "deadline_exceeded"}, proc
    finally:
        _terminate_and_reap(proc)
        parent_conn.close()


def run_parse_isolated(kind: str, data: bytes, media_type: str, engine_config,
                       deadline: float) -> dict:
    """Parse in an isolated, terminable child bounded by ``deadline`` (P0-03)."""
    result, _proc = spawn_and_wait(_child_entry, (kind, data, media_type, engine_config), deadline)
    return result
