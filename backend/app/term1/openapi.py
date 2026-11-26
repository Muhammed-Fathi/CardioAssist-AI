"""Deterministic composition of the single served OpenAPI document.

``shared/contracts/openapi.yaml`` remains byte-for-byte unchanged, keeps its two
legacy operations, and stays the legacy contract of record. The served document
at ``/openapi.json`` is composed here from:

* the legacy bundled document (rebased refs, unchanged schemas), and
* the C1 operation inventory declared in :mod:`backend.app.term1.constants`.

Composition is deterministic: the legacy paths keep their order, C1 paths are
appended in the frozen inventory order, and every reference resolves inside the
served document. ``Authorization`` and ``Idempotency-Key`` are declared as
``in: header`` parameters — never as body fields.

One intentional difference from the legacy-only document: Starlette/FastAPI adds
a ``422`` validation response to the generated paths. The legacy two operations
therefore declare ``422`` here too, so the served contract states the same
status catalogue the handlers already implement. The legacy *file* is untouched.
"""

from __future__ import annotations

import copy
from typing import Any

from . import constants

C1_OPERATIONS: tuple[tuple[str, str], ...] = (
    ("post", "/v1/auth/login"),
    ("post", "/v1/auth/logout"),
    ("get", "/v1/auth/me"),
    ("post", "/v1/auth/refresh"),
    ("post", "/v1/me/password"),
    ("get", "/v1/me/sessions"),
    ("delete", "/v1/me/sessions/{session_id}"),
    ("post", "/v1/admin/doctors"),
    ("patch", "/v1/admin/accounts/{user_id}/status"),
    ("post", "/v1/doctor/verified-visits"),
    ("get", "/v1/doctor/verified-visits/{visit_id}"),
    ("post", "/v1/doctor/verified-visits/{visit_id}/invitations"),
    ("post", "/v1/doctor/invitations/{invitation_id}/revoke"),
    ("get", "/v1/doctor/invitations/{invitation_id}"),
    ("post", "/v1/patients/register"),
    ("post", "/v1/patients/link"),
    ("get", "/v1/me/assignments"),
    ("post", "/v1/doctor/assignments/{assignment_id}/revoke"),
    ("post", "/v1/me/assignments/{assignment_id}/revoke"),
    ("post", "/v1/me/consent/synthetic-demo/revoke"),
)

LEGACY_OPERATIONS: tuple[tuple[str, str], ...] = (
    ("post", "/v1/predictions/cad-tabular"),
    ("post", "/v1/monitoring/observations"),
)

# Every served method/path, as an explicit allowlist (GET and PATCH are separate
# operations). No additional operation may be served.
SERVED_OPERATIONS: tuple[tuple[str, str], ...] = tuple(
    sorted(LEGACY_OPERATIONS + C1_OPERATIONS, key=lambda item: (item[1], item[0]))
)

IDEMPOTENT_C1 = frozenset(
    {
        "/v1/admin/doctors",
        "/v1/admin/accounts/{user_id}/status",
        "/v1/doctor/verified-visits",
        "/v1/doctor/verified-visits/{visit_id}/invitations",
        "/v1/doctor/invitations/{invitation_id}/revoke",
        "/v1/patients/register",
        "/v1/patients/link",
        "/v1/doctor/assignments/{assignment_id}/revoke",
        "/v1/me/assignments/{assignment_id}/revoke",
        "/v1/me/consent/synthetic-demo/revoke",
    }
)
AUTHENTICATED_C1 = frozenset(
    {
        "/v1/auth/logout",
        "/v1/auth/me",
        "/v1/auth/refresh",
        "/v1/me/password",
        "/v1/me/sessions",
        "/v1/me/sessions/{session_id}",
        "/v1/admin/doctors",
        "/v1/admin/accounts/{user_id}/status",
        "/v1/doctor/verified-visits",
        "/v1/doctor/verified-visits/{visit_id}",
        "/v1/doctor/verified-visits/{visit_id}/invitations",
        "/v1/doctor/invitations/{invitation_id}/revoke",
        "/v1/doctor/invitations/{invitation_id}",
        "/v1/patients/link",
        "/v1/me/assignments",
        "/v1/doctor/assignments/{assignment_id}/revoke",
        "/v1/me/assignments/{assignment_id}/revoke",
        "/v1/me/consent/synthetic-demo/revoke",
    }
)

ERROR_CODES: dict[str, list[str]] = {
    "400": ["malformed_request", "idempotency_key_required"],
    "401": [
        "invalid_credentials",
        "authentication_required",
        "invalid_session",
        "invalid_invitation",
    ],
    "403": [
        "forbidden",
        "password_change_required",
        "identity_key_change_unsupported",
    ],
    "404": [
        "not_found",
        "account_not_found",
        "visit_not_found",
        "invitation_not_found",
        "assignment_not_found",
        "consent_not_found",
    ],
    "409": [
        "account_registration_unavailable",
        "account_status_conflict",
        "last_administrator_protected",
        "role_profile_mismatch",
        "identity_key_material_mismatch",
        "identity_key_replacement_unsupported",
        "invitation_already_active",
        "invitation_attempts_exhausted",
        "subject_identity_conflict",
        "assignment_already_revoked",
        "idempotency_key_conflict",
        "idempotency_scope_conflict",
        "secret_not_redisclosable",
        "concurrency_conflict",
    ],
    "422": [
        "validation_failed",
        "password_policy_violation",
        "password_unchanged",
        "invalid_attestation",
        "invalid_demo_identifier",
    ],
    "429": ["rate_limited"],
    "500": ["internal_error"],
    "503": ["identity_key_configuration_error"],
}


def _path_parameters(path: str) -> list[dict[str, Any]]:
    parameters = []
    for segment in path.split("/"):
        if segment.startswith("{") and segment.endswith("}"):
            parameters.append(
                {
                    "name": segment[1:-1],
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string", "minLength": 1, "maxLength": 64},
                }
            )
    return parameters


def _parameters(path: str) -> list[dict[str, Any]]:
    parameters: list[dict[str, Any]] = _path_parameters(path)
    if path in AUTHENTICATED_C1:
        parameters.append(
            {
                "name": "Authorization",
                "in": "header",
                "required": True,
                "description": "Bearer session token issued by POST /v1/auth/login.",
                "schema": {"type": "string", "pattern": "^Bearer [A-Za-z0-9_-]{43}$"},
            }
        )
    if path in IDEMPOTENT_C1:
        parameters.append(
            {
                "name": "Idempotency-Key",
                "in": "header",
                "required": True,
                "description": (
                    "Client-supplied replay key, scoped to the authenticated actor, "
                    "the operation and the target resource (24 h TTL)."
                ),
                "schema": {"type": "string", "minLength": 1, "maxLength": 255},
            }
        )
    return sorted(parameters, key=lambda item: (item["in"], item["name"]))


def _operation_object(method: str, path: str, contract_version: str) -> dict[str, Any]:
    operation: dict[str, Any] = {
        "operationId": f"{method}_{path.strip('/').replace('/', '_').replace('{', '').replace('}', '')}",
        "tags": ["term1-c1"],
        "summary": f"C1 {method.upper()} {path}",
        "parameters": _parameters(path),
        "responses": {},
        "x-term1-stage": "C1",
        "x-error-codes": copy.deepcopy(ERROR_CODES),
    }
    if method in {"post", "patch", "delete"}:
        operation["requestBody"] = {
            "required": path not in {"/v1/auth/logout", "/v1/auth/refresh", "/v1/me/sessions/{session_id}"},
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/term1_operation_body.schema.json"}
                }
            },
        }
    success = {
        "post": "201",
        "patch": "200",
        "delete": "200",
        "get": "200",
    }[method]
    operation["responses"][success] = {
        "description": "Success.",
        "content": {
            "application/json": {
                "schema": {"$ref": f"#/components/schemas/term1_{path.strip('/').split('/')[1]}_response.schema.json"}
            }
        },
    }
    for status in ("400", "401", "403", "404", "409", "422", "429", "500"):
        operation["responses"][status] = {
            "description": "C1 error.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/term1_error.schema.json"}
                }
            },
        }
    return operation


def _c1_components() -> dict[str, Any]:
    """Minimal, explicit component schemas for the composed document."""
    generic_object = {"type": "object", "additionalProperties": True}
    return {
        "term1_operation_body.schema.json": {
            "$id": "https://cardioassist.local/contracts/term1/schemas/operation_body.schema.json",
            "title": "C1 operation body (validated per operation)",
            "type": "object",
            "additionalProperties": True,
            "properties": {"contract_version": {"const": "v1"}},
        },
        "term1_error.schema.json": {
            "$id": "https://cardioassist.local/contracts/term1/schemas/error.schema.json",
            "title": "C1 error envelope",
            "type": "object",
            "required": ["contract_version", "error"],
            "additionalProperties": False,
            "properties": {
                "contract_version": {"const": "v1"},
                "error": {
                    "type": "object",
                    "required": ["code", "message"],
                    "additionalProperties": True,
                    "properties": {
                        "code": {"type": "string"},
                        "message": {"type": "string"},
                        "details": {"type": "array", "items": generic_object},
                    },
                },
            },
        },
    }


def compose_openapi(contracts) -> Any:
    """Return a callable producing the composed served document."""
    legacy_renderer = contracts.bundled_openapi

    def render() -> dict[str, Any]:
        document = legacy_renderer()
        paths = document.setdefault("paths", {})
        for _method, path in LEGACY_OPERATIONS:
            operation = paths[path]["post"]
            operation.setdefault("responses", {})
            # The served catalogue states 422 for every operation (see module docstring).
            operation["responses"].setdefault(
                "422",
                {
                    "description": "Optional-null / validation response (M1a.2).",
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/common.schema.json#/$defs/ErrorResponse"
                            }
                        }
                    },
                },
            )
        for method, path in C1_OPERATIONS:
            paths.setdefault(path, {})[method] = _operation_object(method, path, "v1")

        schemas = document.setdefault("components", {}).setdefault("schemas", {})
        schemas.update(_c1_components())
        for _method, path in C1_OPERATIONS:
            key = f"term1_{path.strip('/').split('/')[1]}_response.schema.json"
            schemas.setdefault(
                key,
                {
                    "$id": f"https://cardioassist.local/contracts/term1/schemas/{key}",
                    "title": "C1 success envelope",
                    "type": "object",
                    "required": ["contract_version"],
                    "additionalProperties": True,
                    "properties": {"contract_version": {"const": "v1"}},
                },
            )
        document.setdefault("tags", []).append(
            {
                "name": "term1-c1",
                "description": (
                    "Term 1 C1 — authentication, verified enrollment and durable "
                    "identity workflows. Synthetic demo data only; patient score "
                    "display remains NOT AUTHORIZED (Decision B pending)."
                ),
            }
        )
        return document

    return render
