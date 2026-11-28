"""Additive C2 document/OCR error catalogue (Track 2-owned).

The frozen C1 catalogue in ``backend/app/term1/errors.py`` (37 codes) is left
byte-for-byte unchanged. These additive codes are supplied here for the core
integrator to merge into the global catalogue and composed OpenAPI. Each code
maps to exactly one HTTP status with a static message that never embeds a
submitted value, identifier, token or fingerprint.

Track 2 raises the existing :class:`backend.app.term1.errors.ApiError` so the
shared error envelope and response boundary are reused without modification.
"""

from __future__ import annotations

from typing import Final

from ..term1.errors import ApiError, error_response

# code -> (status, static message). Mirrors the accepted API spec §5 additive
# catalogue, restricted to the codes reachable from DOC1–DOC7.
DOCUMENT_ERROR_CATALOGUE: Final[dict[str, tuple[int, str]]] = {
    "admin_clinical_content_forbidden": (
        403,
        "Administrators cannot access clinical intake, assessment, or medical document content.",
    ),
    "consent_required": (
        403,
        "Active synthetic-demo consent is required for this operation.",
    ),
    "ocr_inference_not_authorized": (
        403,
        "OCR-confirmed demo intake is not currently authorized for model inference.",
    ),
    "document_not_found": (404, "The document was not found."),
    "extraction_not_found": (404, "The document extraction was not found."),
    "document_not_confirmed": (
        409,
        "The OCR extraction must be explicitly confirmed by the patient first.",
    ),
    "document_integrity_mismatch": (
        409,
        "The stored document digest does not match the recorded immutable digest.",
    ),
    "document_limit_reached": (
        409,
        "The maximum document count or storage quota for this account has been reached.",
    ),
    "extraction_already_confirmed": (
        409,
        "This extraction version has already been confirmed.",
    ),
    "extraction_version_conflict": (
        409,
        "The submitted extraction version does not match the bound extraction version.",
    ),
    "payload_too_large": (
        413,
        "The uploaded document exceeds the maximum allowed size.",
    ),
    "unsupported_media_type": (
        415,
        "Only PDF, PNG, and JPEG documents are accepted.",
    ),
    "active_pdf_content_rejected": (
        422,
        "The PDF contains prohibited active, scripted, or embedded content.",
    ),
    "invalid_document_content": (
        422,
        "The uploaded file failed structural, fixture-allowlist, page, or pixel validation.",
    ),
    "invalid_panel_input": (
        422,
        "The clinical panel values, units, or missingness reasons failed validation.",
    ),
    "missing_reason_mismatch": (
        422,
        "Every omitted or null optional field requires a valid missingness reason.",
    ),
    "prohibited_clinical_field": (
        422,
        "Prohibited leakage, laboratory, or wearable fields are not permitted.",
    ),
    "unsupported_template_for_intake": (
        422,
        "This document template cannot be confirmed as resting-assessment intake.",
    ),
    "worker_unavailable": (
        503,
        "The isolated local inference or OCR worker is currently unavailable.",
    ),
}


def doc_api_error(code: str, *, extra: dict | None = None) -> ApiError:
    """Raise-ready ApiError for an additive C2 document code.

    Falls back to the frozen C1 catalogue for shared codes (``malformed_request``,
    ``validation_failed``, ``authentication_required``, ``forbidden``,
    ``idempotency_*``, ``concurrency_conflict``, ``internal_error``, ...), so a
    Track 2 handler can use one helper for every error it raises.
    """
    if code in DOCUMENT_ERROR_CATALOGUE:
        status, message = DOCUMENT_ERROR_CATALOGUE[code]
    else:
        from ..term1.errors import ERROR_CATALOGUE

        status, message = ERROR_CATALOGUE[code]
    return ApiError(status, code, message, extra=extra)


__all__ = ["DOCUMENT_ERROR_CATALOGUE", "doc_api_error", "error_response"]
