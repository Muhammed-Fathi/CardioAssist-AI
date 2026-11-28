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
import socket
import threading
import time
import uuid
from pathlib import Path

from backend.app.term1_c2_documents import constants as C
from backend.app.term1_c2_documents.fixture_manifest import load_manifest
from backend.app.term1_c2_documents.parser_process import (
    _network_probe_child,
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


@requires_native_ocr
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
