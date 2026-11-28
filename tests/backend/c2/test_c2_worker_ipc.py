"""Isolated OCR worker: loopback-only, bearer auth, strict env, real IPC."""

from __future__ import annotations

import hashlib
import threading
import uuid
from pathlib import Path

import pytest

from backend.app.term1_c2_documents import constants as C
from backend.app.term1_c2_documents.fixture_manifest import load_manifest
from backend.app.term1_c2_documents.storage import PrivateDocStore, make_storage_key
from backend.app.term1_c2_documents.worker import (
    WorkerStartupError,
    build_server,
    verify_sanitized_env,
)
from backend.app.term1_c2_documents.worker_client import (
    AdmissionRejection,
    DocumentIntegrityMismatch,
    HttpOcrWorkerClient,
    WorkerUnavailableError,
)

from .conftest import ocr_engine_config, requires_native_ocr

FIXTURES = Path(__file__).resolve().parents[3] / "backend" / "app" / "term1_c2_documents" / "fixtures"
TOKEN = "c2-test-ocr-ipc-token-0000000000000001"


def test_worker_refuses_non_loopback_bind(tmp_path):
    store = PrivateDocStore(tmp_path / "docs")
    with pytest.raises(WorkerStartupError):
        build_server(host="0.0.0.0", port=0, store=store,
                     engine_config=ocr_engine_config(), token=TOKEN, manifest=load_manifest())


def test_worker_refuses_short_token(tmp_path):
    store = PrivateDocStore(tmp_path / "docs")
    with pytest.raises(WorkerStartupError):
        build_server(port=0, store=store, engine_config=ocr_engine_config(), token="short",
                     manifest=load_manifest())


@pytest.mark.parametrize("secret", [
    "CARDIOASSIST_PEPPER", "CARDIOASSIST_IDENTITY_MATCH_KEY",
    "CARDIOASSIST_SUBJECT_KEY", "CARDIOASSIST_ADMIN_BOOTSTRAP_SECRET",
    "CARDIOASSIST_LOCAL_BUNDLE_DIR", "CARDIOASSIST_LOCAL_TRUSTED_ROOT",
    "CARDIOASSIST_LOCAL_HMAC_KEY_PATH",
])
def test_sanitized_env_fails_closed_on_backend_secret(secret):
    with pytest.raises(WorkerStartupError):
        verify_sanitized_env({"PATH": "/usr/bin", secret: "leaked"})


def test_sanitized_env_rejects_non_allowlisted_variable():
    # T2-R4: even a non-secret unexpected variable fails the strict allowlist.
    with pytest.raises(WorkerStartupError):
        verify_sanitized_env({"PATH": "/usr/bin", "SOME_OTHER_VAR": "x"})


def test_sanitized_env_accepts_clean_environment():
    verify_sanitized_env({"PATH": "/usr/bin", "TESSDATA_PREFIX": "/usr/share/tessdata",
                          "CARDIOASSIST_OCR_IPC_TOKEN": TOKEN})


@pytest.fixture
def worker_server(tmp_path):
    store = PrivateDocStore(tmp_path / "docs")
    server = build_server(port=0, store=store, engine_config=ocr_engine_config(), token=TOKEN,
                          manifest=load_manifest())
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield store, f"http://127.0.0.1:{port}"
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def _promote_fixture(store, name):
    data = (FIXTURES / name).read_bytes()
    patient_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())
    storage_key = make_storage_key(patient_id, document_id)
    staging = store.stage(data, storage_key)
    store.promote(staging, storage_key)
    return storage_key, hashlib.sha256(data).hexdigest(), len(data)


def test_real_ipc_validate_and_extract(worker_server):
    store, base_url = worker_server
    storage_key, sha, size = _promote_fixture(store, "resting_text.pdf")
    client = HttpOcrWorkerClient(base_url, TOKEN)
    info = client.validate(storage_key=storage_key, content_sha256=sha,
                           byte_size=size, media_type=C.MEDIA_PDF, fixture_file_sha256=sha)
    assert info.page_count == 1
    raw = client.extract(document_id=str(uuid.uuid4()), storage_key=storage_key, content_sha256=sha,
                         byte_size=size, media_type=C.MEDIA_PDF,
                         fixture_template_id=C.TEMPLATE_RESTING, fixture_file_sha256=sha)
    assert raw.mode == C.MODE_PDF_TEXT
    assert "54" in raw.full_text


def test_ipc_wrong_token_refused(worker_server):
    store, base_url = worker_server
    storage_key, sha, size = _promote_fixture(store, "resting_text.pdf")
    client = HttpOcrWorkerClient(base_url, "wrong-token-wrong-token-wrong-token-000")
    with pytest.raises(WorkerUnavailableError):
        client.validate(storage_key=storage_key, content_sha256=sha,
                        byte_size=size, media_type=C.MEDIA_PDF, fixture_file_sha256=sha)


def test_ipc_non_allowlisted_digest_refused_before_parse(worker_server):
    # T2-R4: a digest absent from the server-owned manifest is refused by the
    # worker itself, before any read/parse (not trusted from the caller).
    store, base_url = worker_server
    storage_key, sha, size = _promote_fixture(store, "resting_text.pdf")
    client = HttpOcrWorkerClient(base_url, TOKEN)
    with pytest.raises(AdmissionRejection) as exc:
        client.validate(storage_key=storage_key, content_sha256="f" * 64,
                        byte_size=size, media_type=C.MEDIA_PDF, fixture_file_sha256="f" * 64)
    assert exc.value.code == "invalid_document_content"


def test_ipc_tampered_blob_integrity_mismatch(worker_server):
    # The digest IS allowlisted, but the stored bytes were tampered: the
    # verified read fails and the worker reports document_integrity_mismatch.
    store, base_url = worker_server
    storage_key, sha, size = _promote_fixture(store, "resting_text.pdf")
    final = store.root / storage_key
    final.write_bytes(b"X" * size)
    client = HttpOcrWorkerClient(base_url, TOKEN)
    with pytest.raises(DocumentIntegrityMismatch):
        client.validate(storage_key=storage_key, content_sha256=sha,
                        byte_size=size, media_type=C.MEDIA_PDF, fixture_file_sha256=sha)


@requires_native_ocr
def test_ipc_raster_ocr_over_http(worker_server):
    store, base_url = worker_server
    storage_key, sha, size = _promote_fixture(store, "resting.png")
    client = HttpOcrWorkerClient(base_url, TOKEN)
    raw = client.extract(document_id=str(uuid.uuid4()), storage_key=storage_key, content_sha256=sha,
                         byte_size=size, media_type=C.MEDIA_PNG,
                         fixture_template_id=C.TEMPLATE_RESTING, fixture_file_sha256=sha)
    assert raw.mode == C.MODE_RASTER_OCR
    assert raw.pixel_width and raw.pixel_height
