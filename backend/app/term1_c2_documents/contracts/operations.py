"""Authoritative DOC1–DOC7 operation metadata and JSON Schemas (Track 2-owned).

The shapes here mirror ``service.py`` projections exactly. ``generate.py`` renders
them into the C1-style YAML/JSON contract artifacts that Track 1 composes.
"""

from __future__ import annotations

from typing import Any, Final

from .. import constants as C
from ..errors import DOCUMENT_ERROR_CATALOGUE

SCHEMA_ID_BASE: Final = "https://cardioassist.local/contracts/term1/schemas/"
CONTRACT_VERSION: Final = C.CONTRACT_VERSION

# --- shared sub-shapes -------------------------------------------------------
_FIELD_NAMES = list(C.PANEL_FIELD_ORDER)
_UPLOAD_STATUSES = list(C.UPLOAD_STATUSES)
_EXTRACTION_STATUSES = list(C.EXTRACTION_STATUSES)
_PARSE_STATUSES = list(C.PARSE_STATUSES)
_PROVENANCES = list(C.FIELD_PROVENANCES)
_MISSING_REASONS = sorted(C.MISSING_REASONS)


def _schema(name: str, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": SCHEMA_ID_BASE + name,
        "title": name,
        **body,
    }


def _obj(required: list[str], properties: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "required": required, "additionalProperties": False,
            "properties": properties}


_CV = {"type": "string", "enum": [CONTRACT_VERSION]}
_SHA = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
_UUID = {"type": "string", "minLength": 36, "maxLength": 36}
_ISO = {"type": "string", "minLength": 20, "maxLength": 32}

_DOCUMENT_PROPERTIES = {
    "contract_version": _CV,
    "document_id": _UUID,
    "status": {"type": "string", "enum": _UPLOAD_STATUSES},
    "document_kind": {"type": "string", "enum": list(C.DOCUMENT_KINDS)},
    "fixture_template_id": {"type": "string", "enum": list(C.FIXTURE_TEMPLATES)},
    "declared_media_type": {"type": "string", "enum": list(C.ALLOWED_MEDIA_TYPES)},
    "byte_size": {"type": "integer", "minimum": 0, "maximum": C.FILE_CAP_BYTES},
    "page_count": {"type": "integer", "minimum": 0, "maximum": C.MAX_PDF_PAGES},
    "content_sha256": {"anyOf": [_SHA, {"type": "null"}]},
    "pixel_width": {"anyOf": [{"type": "integer", "minimum": 1, "maximum": C.MAX_PIXEL_SIDE},
                              {"type": "null"}]},
    "pixel_height": {"anyOf": [{"type": "integer", "minimum": 1, "maximum": C.MAX_PIXEL_SIDE},
                               {"type": "null"}]},
    "created_at": _ISO,
    "latest_extraction_id": _UUID,
    "latest_extraction_version": {"type": "integer", "minimum": 1},
    "latest_extraction_status": {"type": "string", "enum": _EXTRACTION_STATUSES},
}

_EXTRACTION_FIELD = _obj(
    ["field_name", "raw_text", "typed_value_json", "confirmed_value_json", "unit",
     "confirmed_unit", "missing_reason", "confidence", "conflict_flag", "parse_status",
     "provenance_kind"],
    {
        "field_name": {"type": "string"},
        "raw_text": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "typed_value_json": {"anyOf": [{"type": "integer"}, {"type": "number"}, {"type": "null"}]},
        "confirmed_value_json": {"anyOf": [{"type": "integer"}, {"type": "number"}, {"type": "null"}]},
        "unit": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "confirmed_unit": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "missing_reason": {"anyOf": [{"type": "string", "enum": _MISSING_REASONS}, {"type": "null"}]},
        "confidence": {"anyOf": [{"type": "number", "minimum": 0, "maximum": 1}, {"type": "null"}]},
        "conflict_flag": {"type": "boolean"},
        "parse_status": {"type": "string", "enum": _PARSE_STATUSES},
        "provenance_kind": {"type": "string", "enum": _PROVENANCES},
    },
)

_EXTRACTION_PROPERTIES = {
    "contract_version": _CV,
    "document_id": _UUID,
    "extraction_id": _UUID,
    "extraction_version": {"type": "integer", "minimum": 1},
    "extraction_status": {"type": "string", "enum": _EXTRACTION_STATUSES},
    "template_id": {"anyOf": [{"type": "string"}, {"type": "null"}]},
    "is_confirmed": {"type": "boolean"},
    "confirmed_values_sha256": {"anyOf": [_SHA, {"type": "null"}]},
    "fields": {"type": "array", "items": _EXTRACTION_FIELD},
    "created_at": _ISO,
}

# --- request schemas ---------------------------------------------------------
# DOC1 is multipart/form-data; its form fields are described here for the contract
# (the binary file part is bounded by the 5 MiB per-file / 6 MiB raw caps).
DOC1_FORM_FIELDS: Final[dict[str, Any]] = {
    "contract_version": {"type": "string", "enum": [CONTRACT_VERSION]},
    "document_kind": {"type": "string", "enum": list(C.DOCUMENT_KINDS)},
    "fixture_template_id": {"type": "string", "enum": list(C.FIXTURE_TEMPLATES)},
}

_CONFIRM_INPUT_VALUE = {"anyOf": [{"type": "integer"}, {"type": "null"}]}

SCHEMAS: Final[dict[str, dict[str, Any]]] = {
    "term1_document_upload_response.schema.json": _schema(
        "term1_document_upload_response.schema.json",
        _obj(["contract_version", "document_id", "status", "document_kind",
              "fixture_template_id", "declared_media_type", "byte_size", "page_count",
              "content_sha256", "pixel_width", "pixel_height", "created_at"], _DOCUMENT_PROPERTIES),
    ),
    "term1_document_list_response.schema.json": _schema(
        "term1_document_list_response.schema.json",
        _obj(["contract_version", "items", "next_cursor"], {
            "contract_version": _CV,
            "items": {"type": "array", "items": _obj(
                ["contract_version", "document_id", "status", "document_kind",
                 "fixture_template_id", "declared_media_type", "byte_size", "page_count",
                 "content_sha256", "pixel_width", "pixel_height", "created_at"], _DOCUMENT_PROPERTIES)},
            "next_cursor": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        }),
    ),
    "term1_document_read_response.schema.json": _schema(
        "term1_document_read_response.schema.json",
        _obj(["contract_version", "document_id", "status", "document_kind",
              "fixture_template_id", "declared_media_type", "byte_size", "page_count",
              "content_sha256", "pixel_width", "pixel_height", "created_at", "original_filename_sanitized",
              "latest_extraction", "event_count"], {
                  **_DOCUMENT_PROPERTIES,
                  "original_filename_sanitized": {"type": "string", "maxLength": 128},
                  "latest_extraction": {"anyOf": [
                      _obj(["extraction_id", "extraction_version", "extraction_status", "is_confirmed"], {
                          "extraction_id": _UUID,
                          "extraction_version": {"type": "integer", "minimum": 1},
                          "extraction_status": {"type": "string", "enum": _EXTRACTION_STATUSES},
                          "is_confirmed": {"type": "boolean"},
                      }), {"type": "null"}]},
                  "event_count": {"type": "integer", "minimum": 0},
              }),
    ),
    "term1_document_extraction_response.schema.json": _schema(
        "term1_document_extraction_response.schema.json",
        _obj(["contract_version", "document_id", "extraction_id", "extraction_version",
              "extraction_status", "template_id", "is_confirmed", "confirmed_values_sha256",
              "fields", "created_at"], _EXTRACTION_PROPERTIES),
    ),
    "term1_document_confirm_request.schema.json": _schema(
        "term1_document_confirm_request.schema.json",
        _obj(["contract_version", "extraction_id", "extraction_version", "confirmed_inputs",
              "units", "missing_reasons", "confirm_fabricated_demo_inputs"], {
                  "contract_version": _CV,
                  "extraction_id": _UUID,
                  "extraction_version": {"type": "integer", "minimum": 1},
                  "confirmed_inputs": _obj([], {n: _CONFIRM_INPUT_VALUE for n in _FIELD_NAMES}),
                  "units": _obj([], {n: {"type": "string"} for n in _FIELD_NAMES}),
                  "missing_reasons": _obj([], {n: {"type": "string", "enum": _MISSING_REASONS}
                                                 for n in _FIELD_NAMES}),
                  "confirm_fabricated_demo_inputs": {"type": "boolean", "enum": [True]},
              }),
    ),
    "term1_document_confirm_response.schema.json": _schema(
        "term1_document_confirm_response.schema.json",
        _obj(["contract_version", "document_id", "extraction_id", "extraction_version",
              "is_confirmed", "confirmed_values_sha256", "event_type", "confirmed_at"], {
                  "contract_version": _CV,
                  "document_id": _UUID,
                  "extraction_id": _UUID,
                  "extraction_version": {"type": "integer", "minimum": 1},
                  "is_confirmed": {"type": "boolean", "enum": [True]},
                  "confirmed_values_sha256": _SHA,
                  "event_type": {"type": "string",
                                 "enum": [C.EVENT_PATIENT_CONFIRMED, C.EVENT_EDITED_AND_CONFIRMED]},
                  "confirmed_at": _ISO,
              }),
    ),
}

# --- operations --------------------------------------------------------------
_COMMON_ERRORS = {
    400: ["malformed_request", "idempotency_key_required"],
    401: ["authentication_required", "invalid_session"],
    403: ["forbidden", "password_change_required", "admin_clinical_content_forbidden", "consent_required"],
    409: ["idempotency_key_conflict", "idempotency_scope_conflict", "concurrency_conflict"],
    422: ["validation_failed"],
    500: ["internal_error"],
    503: ["worker_unavailable", "identity_key_configuration_error"],
}


def _responses(success_status: int, success_schema: str | None, success_desc: str,
               extra: dict[int, list[str]] | None = None) -> list[dict[str, Any]]:
    responses = [{"status": success_status, "description": success_desc,
                  "response_schema": success_schema}]
    merged = {status: list(codes) for status, codes in _COMMON_ERRORS.items()}
    for status, codes in (extra or {}).items():
        merged.setdefault(status, [])
        for code in codes:
            if code not in merged[status]:
                merged[status].append(code)
    for status in sorted(merged):
        responses.append({"status": status, "codes": sorted(merged[status]),
                          "description": f"Declared failure statuses for {status}"})
    return responses


OPERATIONS: Final[list[dict[str, Any]]] = [
    {
        "id": "DOC1", "method": "POST", "path": "/v1/me/documents",
        "authenticated": True, "idempotent": True, "target_ref": "none",
        "content_type": "multipart/form-data",
        "summary": "Upload a fabricated demo document; durable PENDING_SCAN quota reservation, "
                   "bounded isolated-worker validation, atomic STORED promotion.",
        "request": {"form_fields": DOC1_FORM_FIELDS, "file_part": "file",
                    "raw_body_cap_bytes": C.RAW_MULTIPART_CAP_BYTES,
                    "file_cap_bytes": C.FILE_CAP_BYTES},
        "responses": _responses(201, "term1_document_upload_response.schema.json",
                                "Document stored and digest-verified.",
                                {409: ["document_limit_reached"],
                                 413: ["payload_too_large"],
                                 415: ["unsupported_media_type"],
                                 422: ["invalid_document_content", "active_pdf_content_rejected"]}),
    },
    {
        "id": "DOC2", "method": "GET", "path": "/v1/me/documents",
        "authenticated": True, "idempotent": False,
        "summary": "List the caller's stored documents (cursor pagination).",
        "request": {"query": {"limit": {"min": 1, "max": 100, "default": 20},
                              "cursor": {"type": "string", "optional": True}}},
        "responses": _responses(200, "term1_document_list_response.schema.json",
                                "Owned stored documents."),
    },
    {
        "id": "DOC3", "method": "GET", "path": "/v1/me/documents/{document_id}",
        "authenticated": True, "idempotent": False,
        "summary": "Read one owned document's metadata.",
        "request": {"path_params": ["document_id"]},
        "responses": _responses(200, "term1_document_read_response.schema.json",
                                "Document metadata.", {404: ["document_not_found"]}),
    },
    {
        "id": "DOC4", "method": "GET", "path": "/v1/me/documents/{document_id}/content",
        "authenticated": True, "idempotent": False, "binary": True,
        "summary": "Download the verified document bytes. The complete bounded buffer is "
                   "SHA-256 verified BEFORE any HTTP status/headers/body are sent.",
        "request": {"path_params": ["document_id"]},
        "responses": [
            {"status": 200, "description": "Verified bytes; attachment; nosniff; CSP default-src 'none'.",
             "media_types": list(C.ALLOWED_MEDIA_TYPES)},
            {"status": 404, "codes": ["document_not_found"], "description": "Not found / not owned."},
            {"status": 409, "codes": ["document_integrity_mismatch"],
             "description": "Stored digest mismatch; zero document bytes sent."},
            {"status": 401, "codes": ["authentication_required", "invalid_session"], "description": "Unauthenticated."},
            {"status": 403, "codes": ["forbidden", "admin_clinical_content_forbidden"], "description": "Wrong role."},
            {"status": 500, "codes": ["internal_error"], "description": "Unexpected failure."},
        ],
    },
    {
        "id": "DOC5", "method": "POST", "path": "/v1/me/documents/{document_id}/extract",
        "authenticated": True, "idempotent": True, "target_ref": "document_id",
        "summary": "Run genuine local extraction (PDF text / raster OCR) into a new immutable "
                   "extraction version. Never dispatches inference.",
        "request": {"path_params": ["document_id"], "body": "optional"},
        "responses": _responses(200, "term1_document_extraction_response.schema.json",
                                "Extraction draft / review result.",
                                {404: ["document_not_found"],
                                 409: ["document_integrity_mismatch"],
                                 422: ["invalid_document_content", "active_pdf_content_rejected"]}),
    },
    {
        "id": "DOC6", "method": "GET", "path": "/v1/me/documents/{document_id}/extraction",
        "authenticated": True, "idempotent": False,
        "summary": "Read the latest extraction version for an owned document.",
        "request": {"path_params": ["document_id"]},
        "responses": _responses(200, "term1_document_extraction_response.schema.json",
                                "Latest extraction.",
                                {404: ["document_not_found", "extraction_not_found"]}),
    },
    {
        "id": "DOC7", "method": "POST", "path": "/v1/me/documents/{document_id}/confirm",
        "authenticated": True, "idempotent": True, "target_ref": "document_id",
        "summary": "Explicit patient confirmation (with optional edits) of one extraction version. "
                   "Patient confirmation is NOT clinician verification and NOT assessment submission.",
        "request": {"path_params": ["document_id"], "body": "required",
                    "request_schema": "term1_document_confirm_request.schema.json"},
        "responses": _responses(200, "term1_document_confirm_response.schema.json",
                                "Confirmed immutable version + provenance.",
                                {404: ["document_not_found", "extraction_not_found"],
                                 409: ["extraction_version_conflict", "extraction_already_confirmed"],
                                 422: ["unsupported_template_for_intake", "invalid_panel_input",
                                       "missing_reason_mismatch", "prohibited_clinical_field"]}),
    },
]

ERROR_CODES: Final[dict[str, dict[str, Any]]] = {
    code: {"status": status, "message": message}
    for code, (status, message) in sorted(DOCUMENT_ERROR_CATALOGUE.items())
}
