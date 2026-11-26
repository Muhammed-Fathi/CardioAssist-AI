"""Deterministic composition of the single served OpenAPI document.

``shared/contracts/openapi.yaml`` remains byte-for-byte unchanged, keeps its two
legacy operations, and stays the legacy contract of record. The served document
at ``/openapi.json`` is composed here from the C1 contract source modules under
``shared/contracts/term1/`` (``paths-auth.yaml``, ``paths-admin.yaml``,
``paths-enrollment.yaml``, ``paths-patient.yaml``) together with the
operation-specific JSON Schemas under ``shared/contracts/term1/schemas/``.

Composition is canonical: every served C1 operation, its authenticated /
idempotent flags, and its request / response schema references are derived from
the modular YAML source — not re-declared in code — so the served contract
cannot drift from the contract source without a test failure.

``Authorization`` and ``Idempotency-Key`` are declared as ``in: header``
parameters — never as body fields.

One intentional difference from the legacy-only document: Starlette/FastAPI adds
a ``422`` validation response to the generated paths. The legacy two operations
therefore declare ``422`` here too, so the served contract states the same
status catalogue the handlers already implement. The legacy *file* is untouched.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from . import constants

TERM1_DIR = Path(__file__).resolve().parents[3] / "shared" / "contracts" / "term1"

LEGACY_OPERATIONS: tuple[tuple[str, str], ...] = (
    ("post", "/v1/predictions/cad-tabular"),
    ("post", "/v1/monitoring/observations"),
)


def _load_path_modules() -> list[dict[str, Any]]:
    """Load every ``paths-*.yaml`` contract module as machine-readable YAML."""
    modules = []
    for path in sorted(TERM1_DIR.glob("paths-*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict), f"{path.name} is not a YAML mapping"
        assert "operations" in data, f"{path.name} has no operations inventory"
        modules.append(data)
    return modules


def _contract_operations() -> list[dict[str, Any]]:
    """Return every declared C1 operation in deterministic (path, method) order."""
    ops: list[dict[str, Any]] = []
    for data in _load_path_modules():
        for op in data["operations"]:
            assert isinstance(op["method"], str), op
            assert isinstance(op["path"], str), op
            assert isinstance(op["authenticated"], bool), op
            assert isinstance(op["idempotent"], bool), op
            ops.append(op)
    ops.sort(key=lambda op: (op["path"], op["method"].lower()))
    return ops


# Canonical C1 operation inventory, derived from the modular YAML source.
# Each entry is (method, path), matching the order used by the served document.
C1_OPERATIONS: tuple[tuple[str, str], ...] = tuple(
    (op["method"].lower(), op["path"]) for op in _contract_operations()
)

# Every served method/path, as an explicit allowlist (GET and PATCH are separate
# operations). No additional operation may be served.
SERVED_OPERATIONS: tuple[tuple[str, str], ...] = tuple(
    sorted(LEGACY_OPERATIONS + C1_OPERATIONS, key=lambda item: (item[1], item[0]))
)

# Per-operation header requirements, derived from the YAML flags.
AUTHENTICATED_C1: frozenset[str] = frozenset(
    path for op in _contract_operations() if op["authenticated"] for path in {op["path"]}
)
IDEMPOTENT_C1: frozenset[str] = frozenset(
    path for op in _contract_operations() if op["idempotent"] for path in {op["path"]}
)


# ---------------------------------------------------------------------------
# Operation -> JSON Schema mapping (operation-specific request / response).
# Keys are (method, path) exactly as in C1_OPERATIONS.
# ---------------------------------------------------------------------------

def _schema_filename(operation_id: str, kind: str) -> str:
    return f"term1_{operation_id.lower()}_{kind}.schema.json"


OP_SCHEMAS: dict[tuple[str, str], dict[str, str | None]] = {
    # (method, path): {"request": <schema filename or None>, "response": <schema filename>}
    ("post", "/v1/auth/login"): {
        "request": _schema_filename("auth_login", "request"),
        "response": _schema_filename("auth_login", "response"),
    },
    ("post", "/v1/auth/refresh"): {
        "request": _schema_filename("auth_refresh", "request"),
        "response": _schema_filename("auth_refresh", "response"),
    },
    ("get", "/v1/auth/me"): {
        "request": None,
        "response": _schema_filename("auth_me", "response"),
    },
    ("post", "/v1/auth/logout"): {
        "request": _schema_filename("auth_logout", "request"),
        "response": _schema_filename("auth_logout", "response"),
    },
    ("post", "/v1/me/password"): {
        "request": _schema_filename("me_password", "request"),
        "response": _schema_filename("me_password", "response"),
    },
    ("get", "/v1/me/sessions"): {
        "request": None,
        "response": _schema_filename("me_sessions", "response"),
    },
    ("delete", "/v1/me/sessions/{session_id}"): {
        "request": None,
        "response": _schema_filename("auth_session_revoke", "response"),
    },
    ("post", "/v1/admin/doctors"): {
        "request": _schema_filename("admin_doctors", "request"),
        "response": _schema_filename("admin_doctors", "response"),
    },
    ("patch", "/v1/admin/accounts/{user_id}/status"): {
        "request": _schema_filename("admin_status", "request"),
        "response": _schema_filename("admin_status", "response"),
    },
    ("post", "/v1/doctor/verified-visits"): {
        "request": _schema_filename("visit_create", "request"),
        "response": _schema_filename("visit_create", "response"),
    },
    ("get", "/v1/doctor/verified-visits/{visit_id}"): {
        "request": None,
        "response": _schema_filename("visit_get", "response"),
    },
    ("post", "/v1/doctor/verified-visits/{visit_id}/invitations"): {
        "request": _schema_filename("invitation_create", "request"),
        "response": _schema_filename("invitation_create", "response"),
    },
    ("post", "/v1/doctor/invitations/{invitation_id}/revoke"): {
        "request": _schema_filename("invitation_revoke", "request"),
        "response": _schema_filename("invitation_revoke", "response"),
    },
    ("get", "/v1/doctor/invitations/{invitation_id}"): {
        "request": None,
        "response": _schema_filename("invitation_get", "response"),
    },
    ("post", "/v1/patients/register"): {
        "request": _schema_filename("patient_register", "request"),
        "response": _schema_filename("patient_register", "response"),
    },
    ("post", "/v1/patients/link"): {
        "request": _schema_filename("patient_link", "request"),
        "response": _schema_filename("patient_link", "response"),
    },
    ("get", "/v1/me/assignments"): {
        "request": None,
        "response": _schema_filename("me_assignments", "response"),
    },
    ("post", "/v1/doctor/assignments/{assignment_id}/revoke"): {
        "request": _schema_filename("assignment_doctor_revoke", "request"),
        "response": _schema_filename("assignment_doctor_revoke", "response"),
    },
    ("post", "/v1/me/assignments/{assignment_id}/revoke"): {
        "request": _schema_filename("assignment_patient_revoke", "request"),
        "response": _schema_filename("assignment_patient_revoke", "response"),
    },
    ("post", "/v1/me/consent/synthetic-demo/revoke"): {
        "request": _schema_filename("consent_revoke", "request"),
        "response": _schema_filename("consent_revoke", "response"),
    },
}

def _load_c1_schemas() -> dict[str, dict[str, Any]]:
    """Load every operation-specific C1 JSON Schema from disk."""
    schemas: dict[str, dict[str, Any]] = {}
    for path in sorted((TERM1_DIR / "schemas").glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        schemas[path.name] = document
    return schemas


C1_SCHEMAS: dict[str, dict[str, Any]] = _load_c1_schemas()


def _c1_registry() -> Registry:
    """Reference registry resolving every C1 schema's $ref to term1_common."""
    resources = []
    for name, document in C1_SCHEMAS.items():
        resource = Resource.from_contents(document, default_specification=DRAFT202012)
        resources.append((document["$id"], resource))
        resources.append(((TERM1_DIR / "schemas" / name).as_uri(), resource))
    return Registry().with_resources(resources)


C1_REGISTRY: Registry = _c1_registry()


def c1_request_validator(schema_name: str) -> Draft202012Validator:
    """A validator for a C1 request schema, resolving its $defs refs locally."""
    return Draft202012Validator(
        C1_SCHEMAS[schema_name],
        registry=C1_REGISTRY,
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    )


def c1_response_validator(schema_name: str) -> Draft202012Validator:
    """A validator for a C1 response schema, resolving its $defs refs locally."""
    return Draft202012Validator(
        C1_SCHEMAS[schema_name],
        registry=C1_REGISTRY,
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    )


def _operation_object(
    method: str,
    path: str,
    contract_version: str,
    authenticated: bool,
    idempotent: bool,
) -> dict[str, Any]:
    schemas = OP_SCHEMAS[(method, path)]
    operation: dict[str, Any] = {
        "operationId": f"{method}_{path.strip('/').replace('/', '_').replace('{', '').replace('}', '')}",
        "tags": ["term1-c1"],
        "summary": f"C1 {method.upper()} {path}",
        "x-term1-stage": "C1",
        "x-op-id": next(
            op["id"] for op in _contract_operations()
            if op["method"].lower() == method and op["path"] == path
        ),
    }
    parameters: list[dict[str, Any]] = []
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
    if authenticated:
        parameters.append(
            {
                "name": "Authorization",
                "in": "header",
                "required": True,
                "description": "Bearer session token issued by POST /v1/auth/login.",
                "schema": {"type": "string", "pattern": "^Bearer [A-Za-z0-9_-]{43}$"},
            }
        )
    if idempotent:
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
    operation["parameters"] = sorted(parameters, key=lambda item: (item["in"], item["name"]))

    if method in {"post", "patch", "delete"} and schemas["request"] is not None:
        operation["requestBody"] = {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {"$ref": f"#/components/schemas/{schemas['request']}"}
                }
            },
        }

    success = {"post": "201", "patch": "200", "delete": "200", "get": "200"}[method]
    operation["responses"] = {
        success: {
            "description": "Success.",
            "content": {
                "application/json": {
                    "schema": {"$ref": f"#/components/schemas/{schemas['response']}"}
                }
            },
        }
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
    """Component schemas for the composed document: every inline C1 schema
    (operation-specific request/response schemas plus the shared error
    envelope). All are fully inline ($defs-free) so each reference resolves
    inside the served OpenAPI document."""
    return dict(C1_SCHEMAS)


def compose_openapi(contracts) -> Any:
    """Return a callable producing the composed served document.

    C1 paths and their schemas are composed from the modular YAML source under
    ``shared/contracts/term1/``; the legacy bundled document supplies the two
    legacy operations.
    """
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
        for op in _contract_operations():
            method = op["method"].lower()
            path = op["path"]
            paths.setdefault(path, {})[method] = _operation_object(
                method,
                path,
                "v1",
                op["authenticated"],
                op["idempotent"],
            )

        schemas = document.setdefault("components", {}).setdefault("schemas", {})
        schemas.update(_c1_components())
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


# ---------------------------------------------------------------------------
# Error catalogue (closed, 37 codes) — kept consistent with
# backend/app/term1/errors.py::ERROR_CATALOGUE and
# shared/contracts/term1/errors.yaml.
# ---------------------------------------------------------------------------

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

# Expose per-operation request schema filename (or None) for runtime validation
# in backend/app/term1/api.py (C1-R01 runtime enforcement).
OP_REQUEST_SCHEMA: dict[tuple[str, str], str | None] = {
    key: value["request"] for key, value in OP_SCHEMAS.items()
}
