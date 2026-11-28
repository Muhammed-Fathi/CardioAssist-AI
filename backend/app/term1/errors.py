"""Term 1 HTTP error type and the frozen C1 error catalogue.

Codes are closed. ``docs/term1/TERM1_API_INTEGRATION_MATRIX.md`` §3 fixes the
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
