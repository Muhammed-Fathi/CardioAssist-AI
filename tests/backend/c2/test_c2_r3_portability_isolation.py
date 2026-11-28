"""T2-R3 regressions: portable secure storage, exact loopback origin, no-proxy /
no-redirect IPC client, and backend-writer / OCR-reader permissions.

Native Windows reparse-point / DACL behavior cannot be executed on this Linux
sandbox; those checks are covered by the owner-local Windows runbook and are
reported as requiring owner execution (never claimed as passed here).
"""

from __future__ import annotations

import os
import stat
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from backend.app.term1_c2_documents import constants as C
from backend.app.term1_c2_documents.settings import (
    DocumentSettings,
    DocumentSettingsError,
    load_document_settings,
    validate_worker_origin,
)
from backend.app.term1_c2_documents.storage import IntegrityError, PrivateDocStore, StorageError
from backend.app.term1_c2_documents.worker_client import HttpOcrWorkerClient, WorkerUnavailableError

TOKEN = "c2-test-ocr-ipc-token-0000000000000001"


# --- exact parsed loopback origin -------------------------------------------
@pytest.mark.parametrize("url", [
    "https://127.0.0.1:8765",          # not http
    "http://localhost:8765",           # ambiguous hostname
    "http://10.0.0.1:8765",            # non-loopback
    "http://127.0.0.1",                # missing port
    "http://127.0.0.1:0",              # invalid port
    "http://127.0.0.1:70000",          # out of range
    "http://user:pass@127.0.0.1:8765",  # credentials
    "http://127.0.0.1:8765/path",      # path
    "http://127.0.0.1:8765/?a=b",      # query
    "http://127.0.0.1:8765/#f",        # fragment
    "http://127.0.0.1.evil.com:8765",  # prefix trick
])
def test_worker_origin_rejects_non_exact_loopback(url):
    with pytest.raises(DocumentSettingsError):
        validate_worker_origin(url)


@pytest.mark.parametrize("url,normalized", [
    ("http://127.0.0.1:8765", "http://127.0.0.1:8765"),
    ("http://127.0.0.1:8765/", "http://127.0.0.1:8765"),
    ("http://[::1]:8765", "http://[::1]:8765"),
])
def test_worker_origin_accepts_exact_loopback(url, normalized):
    assert validate_worker_origin(url) == normalized


def test_settings_reject_doc_root_inside_repository(tmp_path):
    repo_root = Path(__file__).resolve().parents[3]
    with pytest.raises(DocumentSettingsError):
        load_document_settings({
            "CARDIOASSIST_PRIVATE_DOC_DIR": str(repo_root / "private-docs"),
            "CARDIOASSIST_OCR_WORKER_URL": "http://127.0.0.1:8765",
            "CARDIOASSIST_OCR_IPC_TOKEN": TOKEN,
        })


def test_settings_reject_token_with_control_chars(tmp_path):
    with pytest.raises(DocumentSettingsError):
        DocumentSettings(private_doc_dir=tmp_path / "docs",
                         ocr_worker_url="http://127.0.0.1:8765",
                         ocr_ipc_token="bad token with spaces and\r\nnewline")


def test_settings_accept_valid_outside_root(tmp_path):
    settings = load_document_settings({
        "CARDIOASSIST_PRIVATE_DOC_DIR": str(tmp_path / "docs"),
        "CARDIOASSIST_OCR_WORKER_URL": "http://127.0.0.1:8765/",
        "CARDIOASSIST_OCR_IPC_TOKEN": TOKEN,
    })
    assert settings.ocr_worker_url == "http://127.0.0.1:8765"


# --- portable secure storage / permissions ----------------------------------
@pytest.mark.skipif(os.name == "nt", reason="POSIX permission-bit check")
def test_private_root_and_files_have_no_world_or_group_write(tmp_path):
    store = PrivateDocStore(tmp_path / "docs")
    root_mode = stat.S_IMODE(os.stat(store.root).st_mode)
    assert root_mode & 0o007 == 0  # no world access
    assert root_mode & 0o020 == 0  # no group write (OCR account is read-only)
    key = f"{uuid.uuid4()}/{uuid.uuid4()}.bin"
    staging = store.stage(b"%PDF-1.4\nhello", key)
    file_mode = stat.S_IMODE(os.stat(store.root / staging).st_mode)
    assert file_mode & 0o007 == 0
    assert file_mode & 0o022 == 0  # group/world write both denied


@pytest.mark.skipif(os.name == "nt", reason="POSIX symlink check")
def test_storage_rejects_symlink_final_component(tmp_path):
    store = PrivateDocStore(tmp_path / "docs")
    key = f"{uuid.uuid4()}/{uuid.uuid4()}.bin"
    staging = store.stage(b"%PDF-1.4\nhello", key)
    store.promote(staging, key)
    final = store.root / key
    real = final.read_bytes()
    final.unlink()
    outside = tmp_path / "outside.bin"
    outside.write_bytes(real)
    final.symlink_to(outside)  # attacker swaps in a symlink
    assert store.exists(key) is False
    with pytest.raises(IntegrityError):
        store.read_verified(key, expected_sha256="0" * 64, expected_size=len(real))


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission check")
def test_verify_access_policy_fails_closed_on_world_writable_root(tmp_path):
    store = PrivateDocStore(tmp_path / "docs")  # constructor normalizes to 0750
    # If the root is later weakened to world-writable, startup verification
    # must fail closed (no permissive fallback).
    os.chmod(store.root, 0o777)
    with pytest.raises(StorageError):
        store.verify_access_policy()


def test_storage_rejects_symlink_root(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    with pytest.raises(StorageError):
        PrivateDocStore(link)


# --- no-proxy / no-redirect IPC client --------------------------------------
def test_client_rejects_non_loopback_base_url():
    with pytest.raises(DocumentSettingsError):
        HttpOcrWorkerClient("http://example.com:8765", TOKEN)


def test_client_refuses_redirect():
    class RedirectHandler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1:1/elsewhere")
            self.end_headers()

    server = HTTPServer(("127.0.0.1", 0), RedirectHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = HttpOcrWorkerClient(f"http://127.0.0.1:{port}", TOKEN)
        with pytest.raises(WorkerUnavailableError):
            client.validate(storage_key=f"{uuid.uuid4()}/{uuid.uuid4()}.bin",
                            content_sha256="0" * 64, byte_size=10,
                            media_type=C.MEDIA_PDF, fixture_file_sha256="0" * 64)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_client_disables_environment_proxies(monkeypatch):
    # Even with a hostile proxy in the environment, the opener must carry no
    # active proxy routing (ProxyHandler({}) suppresses the env default).
    import urllib.request

    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("http_proxy", "http://127.0.0.1:9")
    client = HttpOcrWorkerClient("http://127.0.0.1:8765", TOKEN)
    assert all(not getattr(h, "proxies", None) for h in client._opener.handlers)
    # A default opener WOULD pick up the env proxy; ours must not.
    default = urllib.request.build_opener()
    assert any(getattr(h, "proxies", None) for h in default.handlers)
