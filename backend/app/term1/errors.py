"""Term 1 HTTP error type and the frozen C1+C2 error catalogue.

Codes are closed. The original 37 C1 codes and messages are byte-identical;
the 26 additive C2 codes (C2.1 clinical intake/assessment and C2.2
documents/OCR vocabulary) follow the same status-per-code rule. Every code maps
to exactly one HTTP status.
``docs/term1/TERM1_API_INTEGRATION_MATRIX.md`` §3 fixes the
status semantics: ``400`` malformed/schema, ``401`` unauthenticated or generic
auth/invitation failure, ``403`` wrong role or ``password_change_required``,
``404`` wrong owner, ``409`` idempotency/domain conflict, ``422`` semantic
validation, ``429`` rate limit.

Messages are static per code. A message never embeds a submitted value, a
resource identifier, a token or a fingerprint, so an error response cannot be
used to enumerate accounts, invitations or identities.
"""

from __future__ import annotations

from typing import Any


class ApiError(Exception):
    """A single failure mapped to one catalogue entry."""

    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        *,
        retry_after: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.retry_after = retry_after
        self.extra = extra or {}


# code -> (status, static message)
ERROR_CATALOGUE: dict[str, tuple[int, str]] = {
    # --- transport / generic --------------------------------------------------
    "malformed_request": (400, "The request body is not acceptable."),
    "validation_failed": (422, "The request failed semantic validation."),
    "invalid_credentials": (401, "Authentication failed."),
    "authentication_required": (401, "Provide a bearer session token."),
    "invalid_session": (401, "The session is not valid."),
    "rate_limited": (429, "Too many attempts. Retry later."),
    "forbidden": (403, "The authenticated account may not perform this operation."),
    "not_found": (404, "The resource was not found."),
    "password_change_required": (
        403,
        "This account must change its temporary password before other operations.",
    ),
    "internal_error": (500, "The service could not complete the request."),
    # --- accounts -------------------------------------------------------------
    "account_registration_unavailable": (409, "The account cannot be created."),
    "account_not_found": (404, "The account was not found."),
    "account_status_conflict": (409, "The requested status transition is not permitted."),
    "last_administrator_protected": (
        409,
        "The operation would leave no usable administrator.",
    ),
    "role_profile_mismatch": (409, "The account role and profile are inconsistent."),
    # --- password -------------------------------------------------------------
    "password_policy_violation": (422, "The password does not meet the policy."),
    "password_unchanged": (422, "The new password must differ from the current one."),
    # --- verified visits and identity ----------------------------------------
    "invalid_attestation": (422, "The attestation attested visit data is not admissible."),
    "invalid_demo_identifier": (422, "Only the fictitious DEMO-ID-nnn grammar is accepted."),
    "identity_key_material_mismatch": (
        409,
        "The configured identity key material does not match the database key check.",
    ),
    "identity_key_change_unsupported": (
        403,
        "The supplied identity key id does not match the stored identity.",
    ),
    "identity_key_replacement_unsupported": (
        409,
        "Identity key replacement is not supported for a populated database.",
    ),
    "identity_key_configuration_error": (
        503,
        "Identity key material is not configured correctly for this database.",
    ),
    "visit_not_found": (404, "The verified visit was not found."),
    # --- invitations ----------------------------------------------------------
    "invalid_invitation": (401, "The invitation is not usable."),
    "invitation_not_found": (404, "The invitation was not found."),
    "invitation_already_active": (409, "An active invitation already exists for this visit."),
    "invitation_attempts_exhausted": (409, "The invitation was revoked after too many attempts."),
    # --- enrollment -----------------------------------------------------------
    "subject_identity_conflict": (
        409,
        "An account already exists for this identity; use the authenticated link flow.",
    ),
    # --- assignments and consent ---------------------------------------------
    "assignment_not_found": (404, "The assignment was not found."),
    "assignment_already_revoked": (409, "The assignment is already revoked."),
    "consent_not_found": (404, "No active synthetic-demo consent was found."),
    # --- idempotency ----------------------------------------------------------
    "idempotency_key_required": (400, "Supply exactly one Idempotency-Key header."),
    "idempotency_key_conflict": (409, "The Idempotency-Key was reused with a different request."),
    "idempotency_scope_conflict": (
        409,
        "The Idempotency-Key was already used for a different operation or target.",
    ),
    "secret_not_redisclosable": (
        409,
        "The original response contained a one-time secret and cannot be replayed.",
    ),
    "concurrency_conflict": (409, "A concurrent request changed the resource."),
    # --- C2 additive codes (C2.1/C2.2; messages verbatim from
    # docs/term1/TERM1_C2_API_AND_OCR_CONTRACT_SPEC_20261127.md §5) -----------
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
    "health_profile_not_found": (404, "The health profile was not found."),
    "assessment_not_found": (404, "The assessment was not found."),
    "document_not_found": (404, "The document was not found."),
    "extraction_not_found": (404, "The document extraction was not found."),
    "health_profile_superseded": (
        409,
        "The referenced health profile version has already been superseded.",
    ),
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
    "stale_attempt_fenced": (
        409,
        "The inference attempt completion was rejected by fencing or lease expiration.",
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
    "health_profile_incomplete": (
        422,
        "A complete health profile version is required before assessment submission.",
    ),
    "invalid_document_content": (
        422,
        "The uploaded file failed structural, fixture-allowlist, page, or pixel validation.",
    ),
    "invalid_panel_input": (
        422,
        "The clinical panel values, units, or missingness reasons failed validation.",
    ),
    "missing_mandatory_attachment": (
        422,
        "OCR-assisted assessment submission requires a bound confirmed resting-vitals document.",
    ),
    "missing_reason_mismatch": (
        422,
        "Every omitted or null optional field requires a valid missingness reason.",
    ),
    "prohibited_clinical_field": (
        422,
        "Prohibited leakage, laboratory, or wearable fields are not permitted.",
    ),
    "provenance_relabeling_forbidden": (
        422,
        "OCR-derived clinical values cannot be submitted as manual-only provenance.",
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


def api_error(code: str, *, retry_after: int | None = None, extra: dict[str, Any] | None = None) -> ApiError:
    status, message = ERROR_CATALOGUE[code]
    return ApiError(status, code, message, retry_after=retry_after, extra=extra)


def error_response(error: ApiError) -> dict[str, Any]:
    """Safe error envelope (the legacy ``ErrorResponse`` shape, C1 codes)."""
    body: dict[str, Any] = {"code": error.code, "message": error.message}
    for key, value in error.extra.items():
        body[key] = value
    return body
