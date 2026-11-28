"""Isolated local OCR worker daemon (separate unprivileged OS account).

Loopback-only HTTP/JSON service exposing two Track 2 operations:

* ``POST /internal/ocr/v1/validate`` — bounded structural admission validation;
* ``POST /internal/ocr/v1/extract``  — genuine PDF text / raster OCR extraction.

Isolation properties (accepted design §4.3 / §5.3, corrections T2-R3/T2-R4):

* binds strictly to ``127.0.0.1``; zero external/browser access;
* mandatory ``Authorization: Bearer <CSPRNG_IPC_TOKEN>`` checked with
  ``hmac.compare_digest``;
* STRICT allowlisted environment: only the worker's own settings and a minimal
  OS locale/path set may be present. Startup fails closed if ANY non-allowlisted
  variable (including every backend secret / AI bundle binding) is present;
* the worker enforces the server-owned fixture SHA-256 allowlist ITSELF, before
  parsing: a request whose digest is not in the manifest, or whose declared
  template/size/media disagrees with the manifest entry, is rejected without
  reading or parsing the document;
* strict request schemas (exact keys/types), bounded simultaneous parser jobs,
  a per-socket read deadline and the engine's monotonic total/per-page deadline;
* the worker reads documents only under its private document root and has zero
  OS read access to AI bundles, signing keys or private research files (enforced
  by the separate account / DACL; see the runbook).

Run::

    CARDIOASSIST_OCR_IPC_TOKEN=... CARDIOASSIST_PRIVATE_DOC_DIR=... \\
    CARDIOASSIST_TESSERACT_CMD=... TESSDATA_PREFIX=... \\
    python -m backend.app.term1_c2_documents.worker --port 8765
"""

from __future__ import annotations

import argparse
import hmac
import json
import os
import re
import threading
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
from .fixture_manifest import FixtureManifest, load_manifest
from .ocr_engine import OcrEngineConfig, extract
from .storage import IntegrityError, PrivateDocStore, StorageError

# Strict environment allowlist (T2-R4). Anything else fails startup closed.
_ALLOWED_ENV = frozenset({
    "PATH", "TESSDATA_PREFIX", "LANG", "LC_ALL",
    "CARDIOASSIST_OCR_IPC_TOKEN", "CARDIOASSIST_PRIVATE_DOC_DIR",
    "CARDIOASSIST_TESSERACT_CMD", "CARDIOASSIST_OCR_FIXTURE_MANIFEST",
    # Minimal Windows OS variables required to launch a subprocess / CRT.
    "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATHEXT",
})
# Backend secrets that must NEVER be present (defence in depth; also caught by
# the allowlist, but named explicitly for a clear startup error).
_FORBIDDEN_ENV = (
    "CARDIOASSIST_IDENTITY_MATCH_KEY",
    "CARDIOASSIST_SUBJECT_KEY",
    "CARDIOASSIST_PEPPER",
    "CARDIOASSIST_ADMIN_BOOTSTRAP_SECRET",
    "CARDIOASSIST_LOCAL_BUNDLE_DIR",
    "CARDIOASSIST_LOCAL_TRUSTED_ROOT",
    "CARDIOASSIST_LOCAL_HMAC_KEY_PATH",
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class WorkerStartupError(RuntimeError):
    """The worker environment is not safely isolated; refuse to start."""


def verify_sanitized_env(environ: dict[str, str]) -> None:
    """Fail closed unless the environment is exactly the strict allowlist."""
    leaked_secrets = [name for name in _FORBIDDEN_ENV if environ.get(name)]
    if leaked_secrets:
        raise WorkerStartupError(
            "OCR worker environment leaks backend/AI secret bindings: "
            + ", ".join(sorted(leaked_secrets))
        )
    unexpected = sorted(name for name in environ if name not in _ALLOWED_ENV)
    if unexpected:
        raise WorkerStartupError(
            "OCR worker environment carries non-allowlisted variables: "
            + ", ".join(unexpected)
        )


def _is_sha(value: object) -> bool:
    return isinstance(value, str) and bool(_SHA256.match(value))


def _is_byte_size(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 < value <= C.FILE_CAP_BYTES


class WorkerCore:
    """Shared validate/extract logic used by the daemon and the in-process client.

    The server-owned fixture manifest is enforced here, inside the worker,
    before any document byte is read or parsed (T2-R4).
    """

    def __init__(self, store: PrivateDocStore, engine_config: OcrEngineConfig,
                 manifest: FixtureManifest) -> None:
        self._store = store
        self._engine = engine_config
        self._manifest = manifest

    def _read(self, storage_key: str, content_sha256: str, byte_size: int) -> bytes:
        return self._store.read_verified(
            storage_key, expected_sha256=content_sha256, expected_size=byte_size
        )

    def _manifest_gate(self, *, content_sha256: str, fixture_file_sha256: str,
                       byte_size: int, media_type: str,
                       fixture_template_id: str | None) -> str | None:
        """Return an error code if the request is not on the server allowlist."""
        if not (_is_sha(content_sha256) and _is_sha(fixture_file_sha256)):
            return "invalid_document_content"
        if content_sha256 != fixture_file_sha256:
            return "invalid_document_content"
        entry = self._manifest.lookup(content_sha256)
        if entry is None:
            return "invalid_document_content"
        if not _is_byte_size(byte_size) or byte_size != entry.byte_size:
            return "invalid_document_content"
        if media_type != entry.media_type:
            return "invalid_document_content"
        if fixture_template_id is not None and fixture_template_id != entry.template_id:
            return "invalid_document_content"
        return None

    def validate(self, *, storage_key: str, content_sha256: str, byte_size: int,
                 media_type: str, fixture_file_sha256: str) -> dict:
        gate = self._manifest_gate(
            content_sha256=content_sha256, fixture_file_sha256=fixture_file_sha256,
            byte_size=byte_size, media_type=media_type, fixture_template_id=None,
        )
        if gate is not None:
            return {"ok": False, "code": gate}
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
                byte_size: int, media_type: str, fixture_template_id: str,
                fixture_file_sha256: str) -> dict:
        if not isinstance(document_id, str) or not _UUID.match(document_id):
            return {"ok": False, "code": "malformed_request"}
        gate = self._manifest_gate(
            content_sha256=content_sha256, fixture_file_sha256=fixture_file_sha256,
            byte_size=byte_size, media_type=media_type,
            fixture_template_id=fixture_template_id,
        )
        if gate is not None:
            return {"ok": False, "code": gate}
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


# Exact request schemas (T2-R4): unknown keys / wrong types are refused.
_VALIDATE_KEYS = {"storage_key", "content_sha256", "byte_size", "declared_media_type",
                  "fixture_file_sha256"}
_EXTRACT_KEYS = {"document_id", "storage_key", "content_sha256", "byte_size",
                 "declared_media_type", "fixture_template_id", "fixture_file_sha256"}


def _schema_ok(request: dict, keys: set[str]) -> bool:
    if set(request) != keys:
        return False
    if not isinstance(request.get("storage_key"), str):
        return False
    if not _is_sha(request.get("content_sha256")):
        return False
    if not _is_sha(request.get("fixture_file_sha256")):
        return False
    if not _is_byte_size(request.get("byte_size")):
        return False
    if request.get("declared_media_type") not in C.ALLOWED_MEDIA_TYPES:
        return False
    if "fixture_template_id" in keys and request.get("fixture_template_id") not in C.FIXTURE_TEMPLATES:
        return False
    if "document_id" in keys and not (
        isinstance(request.get("document_id"), str) and _UUID.match(request["document_id"])
    ):
        return False
    return True


def _handler_factory(core: WorkerCore, token: str, slots: threading.BoundedSemaphore):
    class Handler(BaseHTTPRequestHandler):
        def setup(self) -> None:
            super().setup()
            # Per-socket read deadline so a slow/stalled client cannot hold a
            # worker thread indefinitely (T2-R4).
            self.connection.settimeout(C.WORKER_READ_TIMEOUT_SECONDS)

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
            if self.path not in (C.IPC_VALIDATE_PATH, C.IPC_EXTRACT_PATH):
                self._send(404, {"ok": False, "code": "not_found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._send(400, {"ok": False, "code": "malformed_request"})
                return
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
            keys = _VALIDATE_KEYS if self.path == C.IPC_VALIDATE_PATH else _EXTRACT_KEYS
            if not _schema_ok(request, keys):
                self._send(400, {"ok": False, "code": "malformed_request"})
                return
            # Bounded simultaneous parser jobs (T2-R4). A saturated worker
            # refuses immediately rather than queueing unbounded work.
            if not slots.acquire(blocking=False):
                self._send(503, {"ok": False, "code": "worker_unavailable", "reason": "busy"})
                return
            try:
                if self.path == C.IPC_VALIDATE_PATH:
                    result = core.validate(
                        storage_key=request["storage_key"],
                        content_sha256=request["content_sha256"],
                        byte_size=request["byte_size"],
                        media_type=request["declared_media_type"],
                        fixture_file_sha256=request["fixture_file_sha256"],
                    )
                else:
                    result = core.extract(
                        document_id=request["document_id"],
                        storage_key=request["storage_key"],
                        content_sha256=request["content_sha256"],
                        byte_size=request["byte_size"],
                        media_type=request["declared_media_type"],
                        fixture_template_id=request["fixture_template_id"],
                        fixture_file_sha256=request["fixture_file_sha256"],
                    )
            finally:
                slots.release()
            self._send(200 if result.get("ok") else 422, result)

    return Handler


def build_server(*, host: str = "127.0.0.1", port: int, store: PrivateDocStore,
                 engine_config: OcrEngineConfig, token: str, manifest: FixtureManifest,
                 max_concurrency: int = C.WORKER_MAX_CONCURRENCY) -> ThreadingHTTPServer:
    if host != "127.0.0.1":
        raise WorkerStartupError("OCR worker must bind strictly to 127.0.0.1.")
    if not token or len(token) < 32:
        raise WorkerStartupError("OCR IPC token must be a >= 32-char CSPRNG secret.")
    if max_concurrency < 1:
        raise WorkerStartupError("OCR worker concurrency bound must be >= 1.")
    slots = threading.BoundedSemaphore(max_concurrency)
    core = WorkerCore(store, engine_config, manifest)
    return ThreadingHTTPServer((host, port), _handler_factory(core, token, slots))


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
    manifest_path = os.environ.get("CARDIOASSIST_OCR_FIXTURE_MANIFEST")
    manifest = load_manifest(Path(manifest_path)) if manifest_path else load_manifest()
    server = build_server(port=args.port, store=store, engine_config=engine_config,
                          token=token, manifest=manifest)
    print(f"OCR worker listening on 127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
