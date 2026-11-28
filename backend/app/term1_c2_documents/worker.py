"""Isolated local OCR worker daemon (separate unprivileged OS account).

Loopback-only HTTP/JSON service exposing two Track 2 operations:

* ``POST /internal/ocr/v1/validate`` — bounded structural admission validation;
* ``POST /internal/ocr/v1/extract``  — genuine PDF text / raster OCR extraction.

Isolation properties (accepted design §4.3 / §5.3):

* binds strictly to ``127.0.0.1``; zero external/browser access;
* mandatory ``Authorization: Bearer <CSPRNG_IPC_TOKEN>`` checked with
  ``hmac.compare_digest``;
* sanitized environment: only ``PATH``, ``TESSDATA_PREFIX``, ``LANG`` and the
  worker's own ``CARDIOASSIST_OCR_*`` settings. Startup **fails closed** if any
  backend secret (``CARDIOASSIST_IDENTITY_MATCH_KEY``, ``CARDIOASSIST_SUBJECT_KEY``,
  ``CARDIOASSIST_PEPPER``, ``CARDIOASSIST_ADMIN_BOOTSTRAP_SECRET``) or AI bundle
  binding is present in the environment;
* the worker reads documents only under its private document root and has zero
  OS read access to AI bundles, signing keys or private research files (enforced
  by the separate account / DACL; see the runbook);
* strict 30 s total deadline, 10 s/page, <= 1 MiB extracted text and response cap.

Run::

    CARDIOASSIST_OCR_IPC_TOKEN=... CARDIOASSIST_PRIVATE_DOC_DIR=... \
    CARDIOASSIST_TESSERACT_CMD=... TESSDATA_PREFIX=... \
    python -m backend.app.term1_c2_documents.worker --port 8765
"""

from __future__ import annotations

import argparse
import hmac
import json
import os
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import constants as C
from .admission import AdmissionError, validate_structure
from .extraction_types import (
    ExtractionDeadlineError,
    ExtractionLimitError,
    OcrUnavailableError,
)
from .ocr_engine import OcrEngineConfig, extract
from .storage import IntegrityError, PrivateDocStore, StorageError

# Backend secrets that must NEVER be present in the worker environment.
_FORBIDDEN_ENV = (
    "CARDIOASSIST_IDENTITY_MATCH_KEY",
    "CARDIOASSIST_SUBJECT_KEY",
    "CARDIOASSIST_PEPPER",
    "CARDIOASSIST_ADMIN_BOOTSTRAP_SECRET",
    "CARDIOASSIST_LOCAL_BUNDLE_DIR",
    "CARDIOASSIST_LOCAL_TRUSTED_ROOT",
    "CARDIOASSIST_LOCAL_HMAC_KEY_PATH",
)


class WorkerStartupError(RuntimeError):
    """The worker environment is not safely isolated; refuse to start."""


def verify_sanitized_env(environ: dict[str, str]) -> None:
    present = [name for name in _FORBIDDEN_ENV if environ.get(name)]
    if present:
        raise WorkerStartupError(
            "OCR worker environment leaks backend/AI secret bindings: "
            + ", ".join(sorted(present))
        )


class WorkerCore:
    """Shared validate/extract logic used by the daemon and the in-process client."""

    def __init__(self, store: PrivateDocStore, engine_config: OcrEngineConfig) -> None:
        self._store = store
        self._engine = engine_config

    def _read(self, storage_key: str, content_sha256: str, byte_size: int) -> bytes:
        return self._store.read_verified(
            storage_key, expected_sha256=content_sha256, expected_size=byte_size
        )

    def validate(self, *, storage_key: str, content_sha256: str, byte_size: int,
                 media_type: str) -> dict:
        try:
            data = self._read(storage_key, content_sha256, byte_size)
        except (IntegrityError, StorageError):
            return {"ok": False, "code": "document_integrity_mismatch"}
        try:
            info = validate_structure(data, media_type)
        except AdmissionError as error:
            return {"ok": False, "code": error.code}
        return {
            "ok": True, "page_count": info.page_count,
            "pixel_width": info.pixel_width, "pixel_height": info.pixel_height,
        }

    def extract(self, *, document_id: str, storage_key: str, content_sha256: str,
                byte_size: int, media_type: str, fixture_template_id: str) -> dict:
        try:
            data = self._read(storage_key, content_sha256, byte_size)
        except (IntegrityError, StorageError):
            return {"ok": False, "code": "document_integrity_mismatch"}
        try:
            raw = extract(data, media_type, self._engine)
        except OcrUnavailableError:
            return {"ok": False, "code": "worker_unavailable", "reason": "ocr_unavailable"}
        except ExtractionDeadlineError:
            return {"ok": False, "code": "worker_unavailable", "reason": "deadline_exceeded"}
        except ExtractionLimitError:
            return {"ok": False, "code": "invalid_document_content", "reason": "limit_exceeded"}
        return {
            "ok": True,
            "document_id": document_id,
            "content_sha256": content_sha256,
            "fixture_template_id": fixture_template_id,
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


def _handler_factory(core: WorkerCore, token: str):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # noqa: D401 - no document content in logs
            pass

        def _send(self, status: int, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            if len(body) > C.OCR_IPC_RESPONSE_CAP_BYTES:
                body = json.dumps({"ok": False, "code": "worker_unavailable",
                                   "reason": "response_cap"}).encode("utf-8")
                status = 503
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):  # noqa: N802
            auth = self.headers.get("Authorization", "")
            scheme, _, presented = auth.partition(" ")
            if scheme.lower() != "bearer" or not hmac.compare_digest(presented, token):
                self._send(401, {"ok": False, "code": "authentication_required"})
                return
            if self.path not in ("/internal/ocr/v1/validate", "/internal/ocr/v1/extract"):
                self._send(404, {"ok": False, "code": "not_found"})
                return
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > C.FILE_CAP_BYTES + C.MAX_METADATA_FIELD_BYTES:
                self._send(413, {"ok": False, "code": "payload_too_large"})
                return
            try:
                request = json.loads(self.rfile.read(length).decode("utf-8"))
            except (ValueError, UnicodeError):
                self._send(400, {"ok": False, "code": "malformed_request"})
                return
            if not isinstance(request, dict):
                self._send(400, {"ok": False, "code": "malformed_request"})
                return
            if self.path == "/internal/ocr/v1/validate":
                result = core.validate(
                    storage_key=request.get("storage_key", ""),
                    content_sha256=request.get("content_sha256", ""),
                    byte_size=int(request.get("byte_size", 0)),
                    media_type=request.get("declared_media_type", ""),
                )
            else:
                result = core.extract(
                    document_id=request.get("document_id", ""),
                    storage_key=request.get("storage_key", ""),
                    content_sha256=request.get("content_sha256", ""),
                    byte_size=int(request.get("byte_size", 0)),
                    media_type=request.get("declared_media_type", ""),
                    fixture_template_id=request.get("fixture_template_id", ""),
                )
            self._send(200 if result.get("ok") else 422, result)

    return Handler


def build_server(*, host: str = "127.0.0.1", port: int, store: PrivateDocStore,
                 engine_config: OcrEngineConfig, token: str) -> ThreadingHTTPServer:
    if host != "127.0.0.1":
        raise WorkerStartupError("OCR worker must bind strictly to 127.0.0.1.")
    if not token or len(token) < 32:
        raise WorkerStartupError("OCR IPC token must be a >= 32-char CSPRNG secret.")
    return ThreadingHTTPServer((host, port), _handler_factory(core=WorkerCore(store, engine_config), token=token))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    verify_sanitized_env(dict(os.environ))
    token = os.environ.get("CARDIOASSIST_OCR_IPC_TOKEN", "")
    doc_dir = os.environ.get("CARDIOASSIST_PRIVATE_DOC_DIR", "")
    if not doc_dir:
        raise WorkerStartupError("CARDIOASSIST_PRIVATE_DOC_DIR is required.")
    engine_config = OcrEngineConfig(
        tesseract_cmd=os.environ.get("CARDIOASSIST_TESSERACT_CMD", "tesseract"),
        tessdata_dir=os.environ.get("TESSDATA_PREFIX") or None,
    )
    store = PrivateDocStore(Path(doc_dir))
    server = build_server(port=args.port, store=store, engine_config=engine_config, token=token)
    print(f"OCR worker listening on 127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
