"""T2-R4 regressions: worker contract + resource boundaries.

Covers strict response schema / identity-echo validation, bounded concurrency,
a real processing deadline, pre-decode pixel guards, text-overflow rejection
(no silent truncation) and correct per-page provenance for text-layer PDFs.
Genuine PDF extraction + native Tesseract are preserved (see EVIDENCE.md).
"""

from __future__ import annotations

import json
import struct
import threading
import uuid
import zlib
from pathlib import Path

import pytest

from backend.app.term1_c2_documents import constants as C
from backend.app.term1_c2_documents.extraction_types import (
    ExtractionDeadlineError,
    ExtractionLimitError,
)
from backend.app.term1_c2_documents.fixture_manifest import load_manifest
from backend.app.term1_c2_documents.ocr_engine import OcrEngineConfig, extract
from backend.app.term1_c2_documents.storage import PrivateDocStore
from backend.app.term1_c2_documents.worker import build_server
from backend.app.term1_c2_documents.worker_client import HttpOcrWorkerClient, WorkerUnavailableError

from .conftest import ocr_engine_config, requires_native_ocr

FIXTURES = Path(__file__).resolve().parents[3] / "backend" / "app" / "term1_c2_documents" / "fixtures"
TOKEN = "c2-test-ocr-ipc-token-0000000000000001"


# --- pre-decode pixel guard --------------------------------------------------
def _png_header(width: int, height: int) -> bytes:
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    chunk = b"IHDR" + ihdr_data
    return sig + struct.pack(">I", len(ihdr_data)) + chunk + struct.pack(">I", zlib.crc32(chunk) & 0xFFFFFFFF)


# _extract_image checks native Tesseract availability before Pillow header decode;
# Tesseract-free structural pixel rejection is covered in test_c2_resource_limits.py.
@requires_native_ocr
def test_oversized_image_rejected_before_decode():
    # A 5000x5000 PNG header (no pixel data) must be rejected from the header
    # dimensions alone, before Image.load() allocates a decoded raster.
    data = _png_header(5000, 5000)
    with pytest.raises(ExtractionLimitError):
        extract(data, C.MEDIA_PNG, ocr_engine_config())


# --- text overflow rejection (no truncation) --------------------------------
def test_extracted_text_overflow_is_rejected_not_truncated():
    data = (FIXTURES / "resting_text.pdf").read_bytes()
    config = OcrEngineConfig(tesseract_cmd=ocr_engine_config().tesseract_cmd,
                             tessdata_dir=ocr_engine_config().tessdata_dir, text_cap=16)
    with pytest.raises(ExtractionLimitError):
        extract(data, C.MEDIA_PDF, config)


# --- real processing deadline -----------------------------------------------
def test_total_deadline_exceeded_raises():
    data = (FIXTURES / "resting_text.pdf").read_bytes()
    config = OcrEngineConfig(tesseract_cmd=ocr_engine_config().tesseract_cmd,
                             tessdata_dir=ocr_engine_config().tessdata_dir, total_timeout=0.0)
    with pytest.raises(ExtractionDeadlineError):
        extract(data, C.MEDIA_PDF, config)


# --- per-page provenance for text PDFs --------------------------------------
def _content_obj(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    return b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"


def _two_page_pdf() -> bytes:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 5 0 R "
        b"/Resources << /Font << /F1 6 0 R >> >> >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 7 0 R "
        b"/Resources << /Font << /F1 6 0 R >> >> >>",
        _content_obj("PageOneAlphaText"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        _content_obj("PageTwoBetaText"),
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_pos}\n%%EOF\n").encode()
    return bytes(out)


def test_text_pdf_lines_carry_real_page_provenance():
    raw = extract(_two_page_pdf(), C.MEDIA_PDF, ocr_engine_config())
    assert raw.mode == C.MODE_PDF_TEXT
    assert raw.page_count == 2
    pages = {line.page_number for line in raw.lines}
    assert pages == {1, 2}  # not a constant page 1
    assert any(line.page_number == 2 and "PageTwoBetaText" in line.text for line in raw.lines)


# --- strict response schema / identity echo ---------------------------------
def _valid_extract_response(document_id, sha, template):
    import hashlib
    text = "Age: 54"
    return {
        "ok": True, "document_id": document_id, "content_sha256": sha,
        "fixture_template_id": template, "mode": C.MODE_PDF_TEXT,
        "engine_name": "pdfminer", "engine_version": "20250506", "page_count": 1,
        "pixel_width": None, "pixel_height": None, "full_text": text,
        "raw_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "extracted_text_bytes": len(text.encode()),
        "lines": [{"page_number": 1, "text": text, "confidence": None, "bbox": None}],
    }


def _fake_worker(response_factory):
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(length).decode())
            payload = response_factory(request)
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


@pytest.mark.parametrize("mutate", [
    lambda r, req: r.update(document_id=str(uuid.uuid4())),       # wrong document echo
    lambda r, req: r.update(content_sha256="f" * 64),             # wrong digest echo
    lambda r, req: r.update(raw_text_sha256="f" * 64),            # wrong text digest
    lambda r, req: r.update(extracted_text_bytes=999),            # wrong byte count
    lambda r, req: r.update(extra_key="x"),                       # unknown key
    lambda r, req: r.update(mode="BOGUS"),                        # invalid mode
    lambda r, req: r["lines"][0].update(confidence=5.0),          # non-finite/out-of-range
])
def test_client_rejects_mismatched_or_malformed_response(mutate):
    document_id = str(uuid.uuid4())
    sha = "a" * 64

    def factory(request):
        response = _valid_extract_response(document_id, sha, C.TEMPLATE_RESTING)
        mutate(response, request)
        return response

    server, thread = _fake_worker(factory)
    port = server.server_address[1]
    try:
        client = HttpOcrWorkerClient(f"http://127.0.0.1:{port}", TOKEN)
        with pytest.raises(WorkerUnavailableError):
            client.extract(document_id=document_id,
                           storage_key=f"{uuid.uuid4()}/{uuid.uuid4()}.bin",
                           content_sha256=sha, byte_size=100, media_type=C.MEDIA_PDF,
                           fixture_template_id=C.TEMPLATE_RESTING, fixture_file_sha256=sha)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


# --- bounded concurrency ----------------------------------------------------
def test_worker_bounds_simultaneous_parser_jobs(tmp_path, monkeypatch):
    import backend.app.term1_c2_documents.worker as wmod

    started = threading.Event()
    release = threading.Event()

    def slow_extract(self, **kwargs):
        started.set()
        release.wait(timeout=10)
        return {"ok": False, "code": "worker_unavailable", "reason": "done"}

    monkeypatch.setattr(wmod.WorkerCore, "extract", slow_extract)
    store = PrivateDocStore(tmp_path / "docs")
    server = build_server(port=0, store=store, engine_config=ocr_engine_config(),
                          token=TOKEN, manifest=load_manifest(), max_concurrency=1)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    sha = next(iter(load_manifest().entries))
    entry = load_manifest().lookup(sha)
    request = {
        "document_id": str(uuid.uuid4()), "storage_key": f"{uuid.uuid4()}/{uuid.uuid4()}.bin",
        "content_sha256": sha, "byte_size": entry.byte_size,
        "declared_media_type": entry.media_type, "fixture_template_id": entry.template_id,
        "fixture_file_sha256": sha,
    }
    import urllib.request
    import urllib.error

    def post():
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}{C.IPC_EXTRACT_PATH}",
            data=json.dumps(request).encode(), method="POST",
            headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read().decode())

    results = []
    first = threading.Thread(target=lambda: results.append(("first", post())))
    first.start()
    assert started.wait(timeout=10)  # first job holds the only slot
    second_status, second_body = post()  # second must be refused immediately
    release.set()
    first.join(timeout=10)
    try:
        assert second_status == 503
        assert second_body["code"] == "worker_unavailable"
        assert second_body["reason"] == "busy"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
