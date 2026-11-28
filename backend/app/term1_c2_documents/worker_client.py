"""Backend-side OCR worker client (stdlib HTTP; no OCR dependency).

The backend reaches the isolated OCR worker over loopback HTTP/JSON. It never
imports the OCR engine in production. Two implementations satisfy the same
interface:

* :class:`HttpOcrWorkerClient` — the real loopback client used in deployment and
  in genuine end-to-end evidence;
* :class:`LocalOcrWorkerClient` — an in-process client (lazily importing the
  worker core) used by the test suite to run the *real* engine without a separate
  daemon. Hosted CI without native Tesseract uses an explicitly labelled stub.

Corrections (T2-R3/T2-R4):

* the HTTP client disables proxies and refuses every redirect, so the private
  bearer token can never be forwarded to another origin;
* a monotonic TOTAL deadline bounds the whole exchange (not just one socket op);
* the complete response is schema-validated and every identity echo
  (``document_id``, ``content_sha256``, ``fixture_template_id``,
  ``raw_text_sha256``, ``extracted_text_bytes``, page/pixel counts, line types)
  is checked against the request before any value is trusted. A malformed,
  mismatched or unbounded response fails closed.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
import urllib.error
import urllib.request
from typing import Protocol

from . import constants as C
from .admission import StructureInfo
from .extraction_types import OcrLine, RawExtraction


class WorkerError(RuntimeError):
    def __init__(self, code: str, reason: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.reason = reason


class WorkerUnavailableError(WorkerError):
    def __init__(self, reason: str | None = None) -> None:
        super().__init__("worker_unavailable", reason)


class AdmissionRejection(WorkerError):
    pass


class DocumentIntegrityMismatch(WorkerError):
    def __init__(self) -> None:
        super().__init__("document_integrity_mismatch")


class OcrWorkerClient(Protocol):
    def validate(self, *, storage_key: str, content_sha256: str, byte_size: int,
                 media_type: str, fixture_file_sha256: str) -> StructureInfo: ...

    def extract(self, *, document_id: str, storage_key: str, content_sha256: str,
                byte_size: int, media_type: str, fixture_template_id: str,
                fixture_file_sha256: str) -> RawExtraction: ...


# Closed set of worker error codes the client will map; anything else is a
# malformed/untrusted response (T2-R4).
_WORKER_ERROR_CODES = frozenset({
    "document_integrity_mismatch", "worker_unavailable", "authentication_required",
    "not_found", "invalid_document_content", "active_pdf_content_rejected",
    "unsupported_media_type", "payload_too_large", "malformed_request",
})


def _raise_for_result(result: dict) -> None:
    code = result.get("code")
    reason = result.get("reason")
    if not isinstance(code, str) or code not in _WORKER_ERROR_CODES:
        raise WorkerUnavailableError("malformed_worker_response")
    if code == "document_integrity_mismatch":
        raise DocumentIntegrityMismatch()
    if code in ("worker_unavailable", "authentication_required", "not_found"):
        raise WorkerUnavailableError(reason if isinstance(reason, str) else code)
    raise AdmissionRejection(code, reason if isinstance(reason, str) else None)


def _finite_unit(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) \
        and math.isfinite(value) and 0.0 <= value <= 1.0


def _valid_pixel(value: object) -> bool:
    return value is None or (isinstance(value, int) and not isinstance(value, bool)
                             and 1 <= value <= C.MAX_PIXEL_SIDE)


def _validate_structure_response(result: dict) -> StructureInfo:
    if set(result) != {"ok", "page_count", "pixel_width", "pixel_height"}:
        raise WorkerUnavailableError("malformed_worker_response")
    page_count = result["page_count"]
    if not isinstance(page_count, int) or isinstance(page_count, bool) \
            or not (1 <= page_count <= C.MAX_PDF_PAGES):
        raise WorkerUnavailableError("malformed_worker_response")
    if not _valid_pixel(result["pixel_width"]) or not _valid_pixel(result["pixel_height"]):
        raise WorkerUnavailableError("malformed_worker_response")
    return StructureInfo(
        page_count=page_count, pixel_width=result["pixel_width"],
        pixel_height=result["pixel_height"],
    )


_EXTRACT_RESPONSE_KEYS = {
    "ok", "document_id", "content_sha256", "fixture_template_id", "mode",
    "engine_name", "engine_version", "page_count", "pixel_width", "pixel_height",
    "full_text", "raw_text_sha256", "extracted_text_bytes", "lines",
}


def _validate_extract_response(result: dict, *, document_id: str, content_sha256: str,
                               fixture_template_id: str) -> RawExtraction:
    if set(result) != _EXTRACT_RESPONSE_KEYS:
        raise WorkerUnavailableError("malformed_worker_response")
    # Exact identity echoes (T2-R4): a response for another document/digest/
    # template is rejected, never trusted.
    if result["document_id"] != document_id:
        raise WorkerUnavailableError("identity_echo_mismatch")
    if result["content_sha256"] != content_sha256:
        raise WorkerUnavailableError("identity_echo_mismatch")
    if result["fixture_template_id"] != fixture_template_id:
        raise WorkerUnavailableError("identity_echo_mismatch")
    mode = result["mode"]
    if mode not in (C.MODE_PDF_TEXT, C.MODE_RASTER_OCR):
        raise WorkerUnavailableError("malformed_worker_response")
    if not isinstance(result["engine_name"], str) or not result["engine_name"]:
        raise WorkerUnavailableError("malformed_worker_response")
    if not isinstance(result["engine_version"], str) or not result["engine_version"]:
        raise WorkerUnavailableError("malformed_worker_response")
    page_count = result["page_count"]
    if not isinstance(page_count, int) or isinstance(page_count, bool) \
            or not (1 <= page_count <= C.MAX_PDF_PAGES):
        raise WorkerUnavailableError("malformed_worker_response")
    if not _valid_pixel(result["pixel_width"]) or not _valid_pixel(result["pixel_height"]):
        raise WorkerUnavailableError("malformed_worker_response")
    full_text = result["full_text"]
    if not isinstance(full_text, str):
        raise WorkerUnavailableError("malformed_worker_response")
    text_bytes = len(full_text.encode("utf-8"))
    if result["extracted_text_bytes"] != text_bytes or text_bytes > C.EXTRACTED_TEXT_CAP_BYTES:
        raise WorkerUnavailableError("malformed_worker_response")
    if result["raw_text_sha256"] != hashlib.sha256(full_text.encode("utf-8")).hexdigest():
        raise WorkerUnavailableError("identity_echo_mismatch")
    raw_lines = result["lines"]
    if not isinstance(raw_lines, list):
        raise WorkerUnavailableError("malformed_worker_response")
    lines: list[OcrLine] = []
    for item in raw_lines:
        if not isinstance(item, dict) or set(item) != {"page_number", "text", "confidence", "bbox"}:
            raise WorkerUnavailableError("malformed_worker_response")
        page_number = item["page_number"]
        if not isinstance(page_number, int) or isinstance(page_number, bool) \
                or not (1 <= page_number <= page_count):
            raise WorkerUnavailableError("malformed_worker_response")
        if not isinstance(item["text"], str):
            raise WorkerUnavailableError("malformed_worker_response")
        confidence = item["confidence"]
        if confidence is not None and not _finite_unit(confidence):
            raise WorkerUnavailableError("malformed_worker_response")
        bbox = item["bbox"]
        if bbox is not None:
            if not isinstance(bbox, (list, tuple)) or len(bbox) != 4 \
                    or not all(isinstance(v, int) and not isinstance(v, bool) for v in bbox):
                raise WorkerUnavailableError("malformed_worker_response")
            bbox = tuple(bbox)
        lines.append(OcrLine(page_number=page_number, text=item["text"],
                             confidence=confidence, bbox=bbox))
    return RawExtraction(
        mode=mode, engine_name=result["engine_name"], engine_version=result["engine_version"],
        page_count=page_count, pixel_width=result["pixel_width"], pixel_height=result["pixel_height"],
        full_text=full_text, lines=tuple(lines),
    )


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse every redirect so the bearer token never leaves the origin."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise WorkerUnavailableError("worker_redirect_refused")


def _set_socket_timeout(response, remaining: float) -> None:
    sock = getattr(getattr(getattr(response, "fp", None), "raw", None), "_sock", None)
    if sock is not None:
        try:
            sock.settimeout(max(0.05, remaining))
        except OSError:
            pass


class HttpOcrWorkerClient:
    """Real loopback HTTP/JSON client: no proxy, no redirect, total deadline."""

    def __init__(self, base_url: str, token: str, *, timeout: float = C.OCR_TOTAL_TIMEOUT_SECONDS) -> None:
        from .settings import validate_worker_origin

        self._base_url = validate_worker_origin(base_url)
        self._token = token
        self._timeout = timeout
        # ProxyHandler({}) disables environment proxies; _NoRedirect refuses 3xx.
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())

    def _read_bounded(self, response, deadline: float) -> bytes:
        chunks: list[bytes] = []
        total = 0
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise WorkerUnavailableError("deadline_exceeded")
            _set_socket_timeout(response, remaining)
            chunk = response.read(min(65536, C.OCR_IPC_RESPONSE_CAP_BYTES + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > C.OCR_IPC_RESPONSE_CAP_BYTES:
                raise WorkerUnavailableError("response_cap")
        return b"".join(chunks)

    def _post(self, path: str, payload: dict) -> dict:
        deadline = time.monotonic() + self._timeout
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self._base_url + path, data=body, method="POST",
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
        )
        try:
            response = self._opener.open(request, timeout=self._timeout)
        except urllib.error.HTTPError as error:
            response = error  # typed JSON error body on 4xx; read it faithfully
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise WorkerUnavailableError("worker_unreachable") from error
        try:
            raw = self._read_bounded(response, deadline)
        except WorkerUnavailableError:
            raise
        except (TimeoutError, OSError) as error:
            raise WorkerUnavailableError("worker_unreachable") from error
        finally:
            response.close()
        try:
            result = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeError) as error:
            raise WorkerUnavailableError("malformed_worker_response") from error
        if not isinstance(result, dict):
            raise WorkerUnavailableError("malformed_worker_response")
        return result

    def validate(self, *, storage_key: str, content_sha256: str, byte_size: int,
                 media_type: str, fixture_file_sha256: str) -> StructureInfo:
        result = self._post(C.IPC_VALIDATE_PATH, {
            "storage_key": storage_key, "content_sha256": content_sha256,
            "byte_size": byte_size, "declared_media_type": media_type,
            "fixture_file_sha256": fixture_file_sha256,
        })
        if result.get("ok") is not True:
            _raise_for_result(result)
        return _validate_structure_response(result)

    def extract(self, *, document_id: str, storage_key: str, content_sha256: str,
                byte_size: int, media_type: str, fixture_template_id: str,
                fixture_file_sha256: str) -> RawExtraction:
        result = self._post(C.IPC_EXTRACT_PATH, {
            "document_id": document_id, "storage_key": storage_key,
            "content_sha256": content_sha256, "byte_size": byte_size,
            "declared_media_type": media_type, "fixture_template_id": fixture_template_id,
            "fixture_file_sha256": fixture_file_sha256,
        })
        if result.get("ok") is not True:
            _raise_for_result(result)
        return _validate_extract_response(
            result, document_id=document_id, content_sha256=content_sha256,
            fixture_template_id=fixture_template_id,
        )


class LocalOcrWorkerClient:
    """In-process client running the real worker core (test/evidence use).

    It applies the SAME response validation as the HTTP client, so the genuine
    engine output is held to the identical contract in tests.
    """

    def __init__(self, store, engine_config=None, manifest=None) -> None:
        from .fixture_manifest import load_manifest
        from .ocr_engine import OcrEngineConfig
        from .worker import WorkerCore

        self._core = WorkerCore(
            store, engine_config or OcrEngineConfig(), manifest or load_manifest()
        )

    def validate(self, *, storage_key: str, content_sha256: str, byte_size: int,
                 media_type: str, fixture_file_sha256: str) -> StructureInfo:
        result = self._core.validate(
            storage_key=storage_key, content_sha256=content_sha256,
            byte_size=byte_size, media_type=media_type,
            fixture_file_sha256=fixture_file_sha256,
        )
        if result.get("ok") is not True:
            _raise_for_result(result)
        return _validate_structure_response(result)

    def extract(self, *, document_id: str, storage_key: str, content_sha256: str,
                byte_size: int, media_type: str, fixture_template_id: str,
                fixture_file_sha256: str) -> RawExtraction:
        result = self._core.extract(
            document_id=document_id, storage_key=storage_key, content_sha256=content_sha256,
            byte_size=byte_size, media_type=media_type, fixture_template_id=fixture_template_id,
            fixture_file_sha256=fixture_file_sha256,
        )
        if result.get("ok") is not True:
            _raise_for_result(result)
        return _validate_extract_response(
            result, document_id=document_id, content_sha256=content_sha256,
            fixture_template_id=fixture_template_id,
        )
