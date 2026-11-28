"""Backend-side OCR worker client (stdlib HTTP; no OCR dependency).

The backend reaches the isolated OCR worker over loopback HTTP/JSON. It never
imports the OCR engine in production. Two implementations satisfy the same
interface:

* :class:`HttpOcrWorkerClient` — the real loopback client used in deployment and
  in genuine end-to-end evidence;
* :class:`LocalOcrWorkerClient` — an in-process client (lazily importing the
  worker core) used by the test suite to run the *real* engine without a separate
  daemon. Hosted CI without native Tesseract uses an explicitly labelled stub.
"""

from __future__ import annotations

import json
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
                 media_type: str) -> StructureInfo: ...

    def extract(self, *, document_id: str, storage_key: str, content_sha256: str,
                byte_size: int, media_type: str, fixture_template_id: str) -> RawExtraction: ...


def _raise_for_result(result: dict) -> None:
    code = result.get("code", "worker_unavailable")
    reason = result.get("reason")
    if code == "document_integrity_mismatch":
        raise DocumentIntegrityMismatch()
    if code in ("worker_unavailable", "authentication_required", "not_found"):
        # An unauthorized/unreachable worker is a fail-closed 503, never a
        # silently admitted document.
        raise WorkerUnavailableError(reason or code)
    raise AdmissionRejection(code, reason)


def _deserialize_extraction(result: dict) -> RawExtraction:
    lines = tuple(
        OcrLine(
            page_number=item["page_number"], text=item["text"],
            confidence=item.get("confidence"),
            bbox=tuple(item["bbox"]) if item.get("bbox") else None,
        )
        for item in result.get("lines", [])
    )
    return RawExtraction(
        mode=result["mode"], engine_name=result["engine_name"],
        engine_version=result["engine_version"], page_count=result["page_count"],
        pixel_width=result.get("pixel_width"), pixel_height=result.get("pixel_height"),
        full_text=result["full_text"], lines=lines,
    )


class HttpOcrWorkerClient:
    """Real loopback HTTP/JSON client with bearer authentication and a deadline."""

    def __init__(self, base_url: str, token: str, *, timeout: float = C.OCR_TOTAL_TIMEOUT_SECONDS) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout

    def _post(self, path: str, payload: dict) -> dict:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self._base_url + path, data=body, method="POST",
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                raw = response.read(C.OCR_IPC_RESPONSE_CAP_BYTES + 1)
        except urllib.error.HTTPError as error:
            # The worker returns a typed JSON error body on 4xx; read it so the
            # closed code (e.g. document_integrity_mismatch) is mapped faithfully.
            raw = error.read(C.OCR_IPC_RESPONSE_CAP_BYTES + 1)
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise WorkerUnavailableError("worker_unreachable") from error
        if len(raw) > C.OCR_IPC_RESPONSE_CAP_BYTES:
            raise WorkerUnavailableError("response_cap")
        try:
            result = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeError) as error:
            raise WorkerUnavailableError("malformed_worker_response") from error
        if not isinstance(result, dict):
            raise WorkerUnavailableError("malformed_worker_response")
        return result

    def validate(self, *, storage_key: str, content_sha256: str, byte_size: int,
                 media_type: str) -> StructureInfo:
        result = self._post("/internal/ocr/v1/validate", {
            "storage_key": storage_key, "content_sha256": content_sha256,
            "byte_size": byte_size, "declared_media_type": media_type,
        })
        if not result.get("ok"):
            _raise_for_result(result)
        return StructureInfo(
            page_count=result["page_count"], pixel_width=result.get("pixel_width"),
            pixel_height=result.get("pixel_height"),
        )

    def extract(self, *, document_id: str, storage_key: str, content_sha256: str,
                byte_size: int, media_type: str, fixture_template_id: str) -> RawExtraction:
        result = self._post("/internal/ocr/v1/extract", {
            "document_id": document_id, "storage_key": storage_key,
            "content_sha256": content_sha256, "byte_size": byte_size,
            "declared_media_type": media_type, "fixture_template_id": fixture_template_id,
        })
        if not result.get("ok"):
            _raise_for_result(result)
        return _deserialize_extraction(result)


class LocalOcrWorkerClient:
    """In-process client running the real worker core (test/evidence use)."""

    def __init__(self, store, engine_config=None) -> None:
        from .ocr_engine import OcrEngineConfig
        from .worker import WorkerCore

        self._core = WorkerCore(store, engine_config or OcrEngineConfig())

    def validate(self, *, storage_key: str, content_sha256: str, byte_size: int,
                 media_type: str) -> StructureInfo:
        result = self._core.validate(
            storage_key=storage_key, content_sha256=content_sha256,
            byte_size=byte_size, media_type=media_type,
        )
        if not result.get("ok"):
            _raise_for_result(result)
        return StructureInfo(
            page_count=result["page_count"], pixel_width=result.get("pixel_width"),
            pixel_height=result.get("pixel_height"),
        )

    def extract(self, *, document_id: str, storage_key: str, content_sha256: str,
                byte_size: int, media_type: str, fixture_template_id: str) -> RawExtraction:
        result = self._core.extract(
            document_id=document_id, storage_key=storage_key, content_sha256=content_sha256,
            byte_size=byte_size, media_type=media_type, fixture_template_id=fixture_template_id,
        )
        if not result.get("ok"):
            _raise_for_result(result)
        return _deserialize_extraction(result)
