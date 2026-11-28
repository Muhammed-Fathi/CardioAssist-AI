"""Track 2 HTTP surface — DOC1–DOC7 (additive; never edits shared C1 routes).

``register_document_routes`` attaches exactly the seven bounded document/OCR
operations to an application. The core integrator (Track 1) calls it from the
shared application wiring and composes the DOC OpenAPI/error catalogue; this
module does not modify ``backend/app/main.py``, ``term1/api.py``, ``term1/errors.py``
or ``term1/openapi.py``.

Every route inherits the C1 closure invariants: bearer authentication, duplicate
header refusal, ``Idempotency-Key`` on mutating POSTs, ``Cache-Control: no-store``,
admin ``403`` / non-enumerating IDOR ``404``, and the uniform error envelope.
DOC1 enforces the pre-parser 6 MiB raw body cap and bounded multipart cardinality
before any parsing effect; DOC4 verifies the complete bounded buffer before any
HTTP status/headers/body are sent.
"""

from __future__ import annotations

import io
from typing import Any

import python_multipart as multipart
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from ..term1.api import (
    Term1Handler,
    error_response_json,
    unexpected_failure_json,
)
from ..term1.errors import ApiError
from ..term1.tx import write_transaction
from . import constants as C
from .errors import doc_api_error
from .fixture_manifest import ManifestError, load_manifest
from .service import Actor, DocumentService
from .settings import DocumentSettingsError, load_document_settings
from .storage import PrivateDocStore
from .worker_client import HttpOcrWorkerClient

NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}


def _json(status: int, body: dict[str, Any]) -> JSONResponse:
    return JSONResponse(body, status_code=status, headers=dict(NO_STORE))


class DocumentHandler:
    """Shared plumbing: authentication, service construction, error mapping."""

    def __init__(
        self,
        *,
        database,
        term1: Term1Handler,
        service: DocumentService | None = None,
    ) -> None:
        self.database = database
        self.term1 = term1
        self._service = service

    @property
    def clock(self):
        return self.term1.clock

    def service(self) -> DocumentService:
        if self._service is not None:
            return self._service
        try:
            settings = load_document_settings()
            store = PrivateDocStore(settings.private_doc_dir)
            manifest = load_manifest()
            worker = HttpOcrWorkerClient(settings.ocr_worker_url, settings.ocr_ipc_token)
            pepper = self.term1.settings().pepper
        except (DocumentSettingsError, ManifestError) as error:
            raise doc_api_error("worker_unavailable") from error
        self._service = DocumentService(
            database=self.database, clock=self.clock, pepper=pepper,
            store=store, manifest=manifest, worker=worker,
        )
        return self._service

    def authenticate(self, request: Request, *, operation: str) -> Actor:
        with write_transaction(self.database) as session:
            actor = self.term1.authenticate(session, request, operation=operation)
            return Actor(
                user_id=actor.account.user_id, role=actor.account.role, patient_id=None
            )

    @staticmethod
    def idempotency_key(request: Request) -> str:
        return Term1Handler.idempotency_key(request)


async def _read_bounded_body(request: Request, cap: int) -> bytes:
    """Pre-parser raw body cap: reject before multipart parsing runs."""
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > cap:
                raise doc_api_error("payload_too_large")
        except ValueError:
            raise doc_api_error("malformed_request")
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > cap:
            raise doc_api_error("payload_too_large")
        chunks.append(chunk)
    return b"".join(chunks)


# Exact DOC1 multipart contract (T2-R5): precisely these three text fields and
# one file part named ``file``. Any extra/unknown field or a differently named
# file part is refused — no silent acceptance of unexpected parts.
_DOC1_FIELDS = frozenset({"contract_version", "document_kind", "fixture_template_id"})
_DOC1_FILE_PART = "file"


def _parse_multipart(body: bytes, content_type: str) -> tuple[dict[str, str], bytes, str]:
    """Bounded multipart parse: exact field set, 1 file named ``file``."""
    if not content_type.lower().startswith("multipart/form-data"):
        raise doc_api_error("malformed_request")
    fields: dict[str, str] = {}
    files: list[tuple[str, bytes]] = []
    metadata_bytes = 0

    def on_field(field) -> None:
        nonlocal metadata_bytes
        name = field.field_name.decode("utf-8", errors="strict")
        value = field.value
        metadata_bytes += len(value)
        if metadata_bytes > C.MAX_METADATA_FIELD_BYTES:
            raise doc_api_error("payload_too_large")
        if len(fields) >= C.MAX_FORM_FIELDS:
            raise doc_api_error("malformed_request")
        if name in fields:
            raise doc_api_error("malformed_request")  # duplicate form field
        if name not in _DOC1_FIELDS:
            raise doc_api_error("malformed_request")  # unexpected/extra field
        fields[name] = value.decode("utf-8", errors="strict")

    def on_file(file) -> None:
        if len(files) >= C.MAX_FILE_PARTS:
            raise doc_api_error("malformed_request")  # more than one file part
        part_name = (file.field_name or b"").decode("utf-8", errors="strict")
        if part_name != _DOC1_FILE_PART:
            raise doc_api_error("malformed_request")  # exact file-part name required
        file_object = file.file_object
        # The parser leaves the spooled file cursor at EOF; rewind before read.
        if hasattr(file_object, "seek"):
            file_object.seek(0)
        data = file_object.read(C.FILE_CAP_BYTES + 1)
        if len(data) > C.FILE_CAP_BYTES:
            raise doc_api_error("payload_too_large")
        filename = (file.file_name or b"document").decode("utf-8", errors="replace")
        files.append((filename, data))

    try:
        multipart.parse_form(
            {"Content-Type": content_type.encode("latin-1")},
            io.BytesIO(body), on_field, on_file,
        )
    except (UnicodeError, ValueError) as error:
        raise doc_api_error("malformed_request") from error
    if len(files) != 1:
        raise doc_api_error("malformed_request")
    if set(fields) != _DOC1_FIELDS:
        raise doc_api_error("validation_failed")
    if fields.get("contract_version") != C.CONTRACT_VERSION:
        raise doc_api_error("malformed_request")
    filename, data = files[0]
    return fields, data, filename


def register_document_routes(app: FastAPI, *, handler: DocumentHandler) -> None:
    """Attach exactly DOC1–DOC7 to ``app`` (additive)."""

    # ------------------------------------------------------------- DOC1 upload
    async def _impl_doc1(request: Request) -> Response:
        actor = handler.authenticate(request, operation=C.OP_DOC1_UPLOAD)
        key = handler.idempotency_key(request)
        body = await _read_bounded_body(request, C.RAW_MULTIPART_CAP_BYTES)
        content_type = request.headers.get("content-type", "")
        fields, data, filename = _parse_multipart(body, content_type)
        service = handler.service()
        result = await run_in_threadpool(
            service.upload,
            actor=actor, data=data,
            declared_template_id=fields["fixture_template_id"],
            declared_document_kind=fields["document_kind"],
            original_filename=filename, idempotency_key=key,
        )
        return _json(201, result)

    @app.post("/v1/me/documents")
    async def doc1(request: Request) -> Response:
        try:
            return await _impl_doc1(request)
        except ApiError as error:
            return error_response_json(error)
        except Exception as error:  # noqa: BLE001
            return unexpected_failure_json(error)

    # ------------------------------------------------------------- DOC2 list
    @app.get("/v1/me/documents")
    async def doc2(request: Request, limit: int = 20, cursor: str | None = None) -> Response:
        try:
            actor = handler.authenticate(request, operation=C.OP_DOC2_LIST)
            if limit < 1 or limit > 100:
                raise doc_api_error("malformed_request")
            if cursor is not None and not cursor.isdigit():
                raise doc_api_error("malformed_request")
            service = handler.service()
            result = await run_in_threadpool(
                service.list_documents, actor=actor, limit=limit, cursor=cursor
            )
            return _json(200, result)
        except ApiError as error:
            return error_response_json(error)
        except Exception as error:  # noqa: BLE001
            return unexpected_failure_json(error)

    # ------------------------------------------------------------- DOC3 read
    @app.get("/v1/me/documents/{document_id}")
    async def doc3(request: Request, document_id: str) -> Response:
        try:
            actor = handler.authenticate(request, operation=C.OP_DOC3_READ)
            service = handler.service()
            result = await run_in_threadpool(
                service.read_document, actor=actor, document_id=document_id
            )
            return _json(200, result)
        except ApiError as error:
            return error_response_json(error)
        except Exception as error:  # noqa: BLE001
            return unexpected_failure_json(error)

    # ------------------------------------------------------------- DOC4 content
    @app.get("/v1/me/documents/{document_id}/content")
    async def doc4(request: Request, document_id: str) -> Response:
        try:
            actor = handler.authenticate(request, operation=C.OP_DOC4_CONTENT)
            service = handler.service()
            data, media_type, filename = await run_in_threadpool(
                service.read_content, actor=actor, document_id=document_id
            )
            # The complete bounded buffer was SHA-verified before this point.
            headers = {
                **NO_STORE,
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "default-src 'none'",
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(data)),
            }
            return Response(content=data, status_code=200, media_type=media_type, headers=headers)
        except ApiError as error:
            return error_response_json(error)
        except Exception as error:  # noqa: BLE001
            return unexpected_failure_json(error)

    # ------------------------------------------------------------- DOC5 extract
    async def _impl_doc5(request: Request, document_id: str) -> Response:
        actor = handler.authenticate(request, operation=C.OP_DOC5_EXTRACT)
        key = handler.idempotency_key(request)
        await _expect_empty_json(request)
        service = handler.service()
        result = await run_in_threadpool(
            service.extract, actor=actor, document_id=document_id, idempotency_key=key
        )
        return _json(200, result)

    @app.post("/v1/me/documents/{document_id}/extract")
    async def doc5(request: Request, document_id: str) -> Response:
        try:
            return await _impl_doc5(request, document_id)
        except ApiError as error:
            return error_response_json(error)
        except Exception as error:  # noqa: BLE001
            return unexpected_failure_json(error)

    # ------------------------------------------------------------- DOC6 extraction
    @app.get("/v1/me/documents/{document_id}/extraction")
    async def doc6(request: Request, document_id: str) -> Response:
        try:
            actor = handler.authenticate(request, operation=C.OP_DOC6_EXTRACTION)
            service = handler.service()
            result = await run_in_threadpool(
                service.read_extraction, actor=actor, document_id=document_id
            )
            return _json(200, result)
        except ApiError as error:
            return error_response_json(error)
        except Exception as error:  # noqa: BLE001
            return unexpected_failure_json(error)

    # ------------------------------------------------------------- DOC7 confirm
    async def _impl_doc7(request: Request, document_id: str) -> Response:
        actor = handler.authenticate(request, operation=C.OP_DOC7_CONFIRM)
        key = handler.idempotency_key(request)
        body = await _read_json_body(request)
        # Exact DOC7 schema (T2-R5): every field is explicit; missing mappings
        # are NOT silently defaulted to {} and unknown keys are refused.
        required = {
            "contract_version", "extraction_id", "extraction_version",
            "confirmed_inputs", "units", "missing_reasons",
            "confirm_fabricated_demo_inputs",
        }
        if set(body) != required:
            raise doc_api_error("malformed_request")
        service = handler.service()
        result = await run_in_threadpool(
            service.confirm,
            actor=actor, document_id=document_id,
            extraction_id=body["extraction_id"],
            extraction_version=body["extraction_version"],
            confirmed_inputs=body["confirmed_inputs"],
            units=body["units"],
            missing_reasons=body["missing_reasons"],
            confirm_fabricated_demo_inputs=body["confirm_fabricated_demo_inputs"],
            idempotency_key=key,
        )
        return _json(200, result)

    @app.post("/v1/me/documents/{document_id}/confirm")
    async def doc7(request: Request, document_id: str) -> Response:
        try:
            return await _impl_doc7(request, document_id)
        except ApiError as error:
            return error_response_json(error)
        except Exception as error:  # noqa: BLE001
            return unexpected_failure_json(error)


async def _read_json_body(request: Request) -> dict[str, Any]:
    import json

    from ..main_helpers import finite_float, reject_constant, unique_object

    media_type = request.headers.get("content-type", "").partition(";")[0].strip().lower()
    if media_type != "application/json":
        raise doc_api_error("malformed_request")
    # Bounded JSON request body (T2-R5): reject before buffering an unbounded body.
    raw = await _read_bounded_body(request, C.JSON_BODY_CAP_BYTES)
    if not raw.strip():
        raise doc_api_error("malformed_request")
    try:
        parsed = json.loads(
            raw.decode("utf-8"), object_pairs_hook=unique_object,
            parse_float=finite_float, parse_constant=reject_constant,
        )
    except (ValueError, UnicodeError, RecursionError) as error:
        raise doc_api_error("malformed_request") from error
    if not isinstance(parsed, dict) or parsed.get("contract_version") != C.CONTRACT_VERSION:
        raise doc_api_error("malformed_request")
    return parsed


async def _expect_empty_json(request: Request) -> None:
    raw = await _read_bounded_body(request, C.JSON_BODY_CAP_BYTES)
    if raw.strip():
        # A non-empty DOC5 body must still be a bounded, contract-versioned JSON
        # object; re-parse the already-bounded buffer rather than re-reading.
        import json

        from ..main_helpers import finite_float, reject_constant, unique_object

        try:
            parsed = json.loads(
                raw.decode("utf-8"), object_pairs_hook=unique_object,
                parse_float=finite_float, parse_constant=reject_constant,
            )
        except (ValueError, UnicodeError, RecursionError) as error:
            raise doc_api_error("malformed_request") from error
        if not isinstance(parsed, dict) or parsed.get("contract_version") != C.CONTRACT_VERSION:
            raise doc_api_error("malformed_request")
