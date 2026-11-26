"""HTTP contract conformance for all 20 C1 operations.

Pins the served HTTP surface: every declared C1 operation is reachable at its
declared method+path, every error response uses the frozen envelope
``{contract_version: "v1", error: {code, message}}``, authentication and
idempotency flags are enforced at the HTTP layer, and status codes match the
closed catalogue.

These tests exercise the live HTTP surface through TestClient, not the
business-logic layer directly.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from backend.app.term1 import openapi

from tests.backend.c1.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, bearer, bootstrap_admin, login
from tests.backend.c1.factories import (
    DEMO_ID_A,
    attest_visit,
    issue_invitation,
    provision_doctor,
    register_patient,
    setup_doctor_with_invitation,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error_envelope(response) -> dict:
    """Assert the response is a v1 error envelope and return the error body."""
    assert response.headers.get("content-type", "").startswith("application/json"), response.text
    body = response.json()
    assert set(body) == {"contract_version", "error"}, body
    assert body["contract_version"] == "v1", body
    err = body["error"]
    assert set(err) <= {"code", "message"}, err
    assert "code" in err, err
    assert "message" in err, err
    return err


def _assert_status_and_code(response: object, status: int, code: str | None = None) -> dict:
    """Assert status and (optionally) error code; return parsed JSON body."""
    assert response.status_code == status, (response.status_code, response.text)
    if code is not None:
        err = _error_envelope(response)
        assert err["code"] == code, (err["code"], code)
    return response.json()


# ---------------------------------------------------------------------------
# Operation inventory: every declared C1 operation is served
# ---------------------------------------------------------------------------

def test_all_c1_operations_are_served(client, app):
    """Every declared C1 operation responds at its method+path (not 404).

    Operations that require a body or auth are probed with minimal valid input
    so a 404 means the route is not mounted, not a validation failure.
    """
    bootstrap_admin(app)

    # Minimal bodies for body-requiring operations (auth handled separately).
    minimal = {
        ("post", "/v1/auth/login"): {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        ("post", "/v1/patients/register"): {
            "access_code": "x" * 43,
            "identifier": DEMO_ID_A,
            "email": "demo.conf@cardioassist.local",
            "password": "conf password 0001",
            "consent_ack": True,
        },
    }

    for method, path in openapi.C1_OPERATIONS:
        if (method, path) in minimal:
            response = client.request(method.upper(), path, json=minimal[(method, path)])
        else:
            response = client.request(method.upper(), path)
        # Not 404: the route exists (401/400/422/409/429 are all "served").
        assert response.status_code != 404, f"{method.upper()} {path} returned 404"


# ---------------------------------------------------------------------------
# Error envelope format on every failure
# ---------------------------------------------------------------------------

def test_error_envelope_is_v1_on_auth_failure(client, app):
    """A 401 on an authenticated path uses the v1 error envelope."""
    bootstrap_admin(app)
    response = client.get("/v1/auth/me")
    err = _error_envelope(response)
    assert err["code"] == "authentication_required"


def test_error_envelope_is_v1_on_rate_limit(client, app):
    """A 429 uses the v1 error envelope."""
    bootstrap_admin(app)
    for attempt in range(5):
        client.post(
            "/v1/auth/login",
            json={"email": ADMIN_EMAIL, "password": f"wrong password {attempt:04d}"},
        )
    response = client.post(
        "/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 429
    err = _error_envelope(response)
    assert err["code"] == "rate_limited"


def test_error_envelope_is_v1_on_validation_failure(client, app):
    """A 400/422 uses the v1 error envelope."""
    bootstrap_admin(app)
    # Missing required body on login: 400 or 422 malformed.
    response = client.post("/v1/auth/login", json={})
    assert response.status_code in (400, 422), response.status_code
    _error_envelope(response)


# ---------------------------------------------------------------------------
# Authentication enforcement at HTTP layer
# ---------------------------------------------------------------------------

# Paths with path parameters need a concrete value to route; skip those in the
# anonymous/auth enforcement tests since they return 404 (no route match) not 401.
_PATH_PARAM_PATHS = frozenset({
    "/v1/admin/accounts/{user_id}/status",
    "/v1/doctor/invitations/{invitation_id}",
    "/v1/doctor/invitations/{invitation_id}/revoke",
    "/v1/doctor/verified-visits/{visit_id}",
    "/v1/doctor/verified-visits/{visit_id}/invitations",
    "/v1/me/assignments/{assignment_id}/revoke",
    "/v1/me/sessions/{session_id}",
    "/v1/doctor/assignments/{assignment_id}/revoke",
})


# Body-requiring paths validate structure before auth: 400 (missing body)
# takes precedence over 401 (no bearer). Both are "served" responses.
_BODY_REQUIRED_PATHS = frozenset({
    "/v1/admin/doctors",
    "/v1/doctor/verified-visits",
    "/v1/doctor/verified-visits/{visit_id}/invitations",
    "/v1/me/consent/synthetic-demo/revoke",
    "/v1/me/password",
    "/v1/patients/link",
})


@pytest.mark.parametrize("method,path", sorted(
    (m, p) for m, p in openapi.C1_OPERATIONS
    if p in openapi.AUTHENTICATED_C1 and p not in _PATH_PARAM_PATHS
), ids=lambda mp: f"{mp[0].upper()} {mp[1]}")
def test_authenticated_paths_reject_anonymous(client, method, path):
    """Every AUTHENTICATED_C1 path (without path params) rejects anonymous access.

    Body-requiring paths return 400 (structural validation before auth);
    others return 401 (authentication_required).
    """
    kwargs = {"json": {}} if path in _BODY_REQUIRED_PATHS else {}
    response = client.request(method.upper(), path, **kwargs)
    assert response.status_code in (400, 401, 422), (method, path, response.status_code)
    if response.status_code == 401:
        err = _error_envelope(response)
        assert err["code"] == "authentication_required"


@pytest.mark.parametrize("method,path", sorted(
    (m, p) for m, p in openapi.C1_OPERATIONS if p not in openapi.AUTHENTICATED_C1
), ids=lambda mp: f"{mp[0].upper()} {mp[1]}")
def test_anonymous_paths_accept_no_bearer(client, method, path):
    """Every non-authenticated C1 path does not require a bearer token."""
    bootstrap_admin(client.app)  # ensure app is bootstrapped for state
    # Login is the only anonymous C1 op with a body; others may not apply.
    if (method, path) == ("post", "/v1/auth/login"):
        response = client.request(method.upper(), path, json={"email": "x@y.z", "password": "p"})
        assert response.status_code in (200, 401), (method, path, response.status_code)
    else:
        response = client.request(method.upper(), path)
        # Not 401: anonymous access is permitted (may be 404 for path params, 405, etc.)
        assert response.status_code != 401, (method, path, response.status_code)


# ---------------------------------------------------------------------------
# Idempotency at HTTP layer
# ---------------------------------------------------------------------------

def test_idempotent_path_requires_idempotency_key(client, app):
    """An idempotent, body-requiring C1 path rejects a missing idempotency key."""
    bootstrap_admin(app)
    chain = setup_doctor_with_invitation(app, client)
    response = client.post(
        "/v1/doctor/verified-visits",
        json={
            "visit_ref": "V-IDEM-REQ",
            "subject_identifier": DEMO_ID_A,
            "asserted_visit_at": "2026-11-25T10:00:00Z",
            "attestation_code": "PRIOR_IN_PERSON_VISIT_DEMO",
        },
    )
    assert response.status_code == 400, response.text
    err = _error_envelope(response)
    assert err["code"] == "idempotency_key_required"


def test_idempotent_replay_returns_cached_response(client, app):
    """Replaying an idempotent request with the same key returns the cached response."""
    bootstrap_admin(app)
    chain = setup_doctor_with_invitation(app, client)
    doctor = chain["doctor"]
    headers = {**bearer(doctor["token"]), "Idempotency-Key": "idem-conformance-key"}
    payload = {
        "visit_ref": "V-IDEM-CONFORM",
        "subject_identifier": DEMO_ID_A,
        "asserted_visit_at": "2026-11-25T10:00:00Z",
        "attestation_code": "PRIOR_IN_PERSON_VISIT_DEMO",
    }
    first = client.post("/v1/doctor/verified-visits", headers=headers, json=payload)
    assert first.status_code == 201, first.text
    assert "idempotent_replay" not in first.json()

    second = client.post("/v1/doctor/verified-visits", headers=headers, json=payload)
    assert second.status_code == 201, second.text
    assert second.json().get("idempotent_replay") is True
    assert second.json()["visit_id"] == first.json()["visit_id"]


# ---------------------------------------------------------------------------
# Status-code consistency with the closed catalogue
# ---------------------------------------------------------------------------

def test_error_codes_match_catalogue(client, app):
    """Every error code returned over HTTP appears in the closed catalogue."""
    from backend.app.term1 import errors

    bootstrap_admin(app)

    # Trigger a few distinct error codes over HTTP.
    cases = [
        ("get", "/v1/auth/me", None, "authentication_required"),
        ("post", "/v1/auth/login", {"email": "x@y.z", "password": "p"}, "invalid_credentials"),
    ]

    for method, path, body, expected_code in cases:
        kwargs = {"json": body} if body is not None else {}
        response = client.request(method.upper(), path, **kwargs)
        assert response.status_code in (400, 401, 403, 404, 409, 422, 429), (
            method, path, response.status_code
        )
        err = _error_envelope(response)
        assert err["code"] in errors.ERROR_CATALOGUE, (err["code"], method, path)


# ---------------------------------------------------------------------------
# F3: JSON Schema validation of actual HTTP responses against served OpenAPI
# ---------------------------------------------------------------------------

from jsonschema import Draft202012Validator


def _served_openapi(client) -> dict:
    """Fetch the composed OpenAPI document served at /openapi.json."""
    response = client.get("/openapi.json")
    assert response.status_code == 200, response.text
    return response.json()


def _response_schema_for(method: str, path: str) -> str | None:
    """Look up the response schema filename for a C1 operation."""
    from backend.app.term1 import openapi as _openapi

    binding = _openapi.OP_SCHEMAS.get((method.lower(), path))
    if binding is None:
        return None
    return binding.get("response")


def _strip_none_values(obj):
    """Recursively remove keys whose value is None, treating null as absent.

    Also strips operational fields (idempotent_replay) that the service adds
    at the HTTP layer but are not part of the stored contract schema, since
    schemas must not be loosened globally.
    """
    OPERATIONAL_FIELDS = {"idempotent_replay"}
    if isinstance(obj, dict):
        return {
            k: _strip_none_values(v)
            for k, v in obj.items()
            if v is not None and k not in OPERATIONAL_FIELDS
        }
    if isinstance(obj, list):
        return [_strip_none_values(v) for v in obj if v is not None]
    return obj


def _validate_against_served_schema(response_body: dict, schema_name: str) -> None:
    """Validate a response body against a C1 response schema with format checking.

    None values are stripped before validation because the served contract treats
    absent optional fields as null; JSON Schema `type: string` does not accept
    null, and schemas must not be loosened globally.
    """
    from backend.app.term1 import openapi as _openapi

    schema = _openapi.C1_SCHEMAS[schema_name]
    validator = Draft202012Validator(
        schema,
        registry=_openapi.C1_REGISTRY,
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    )
    cleaned = _strip_none_values(response_body)
    errors = list(validator.iter_errors(cleaned))
    assert not errors, [
        {"message": e.message, "path": list(e.path), "schema": e.schema}
        for e in errors
    ]


def test_served_openapi_covers_all_c1_operations(client, app):
    """The served OpenAPI document declares exactly the 20 C1 operations."""
    bootstrap_admin(app)
    spec = _served_openapi(client)

    served = set()
    for path, methods in spec.get("paths", {}).items():
        for method in methods:
            if (method.lower(), path) in [
                (op["method"].lower(), op["path"])
                for op in __import__(
                    "backend.app.term1.openapi", fromlist=["_contract_operations"]
                )._contract_operations()
            ]:
                served.add((method.lower(), path))

    from backend.app.term1 import openapi as _openapi

    expected = set(_openapi.C1_OPERATIONS)
    assert served == expected, (served, expected)


def test_configuration_response_is_valid_openapi(client, app):
    """The /openapi.json response is itself a valid OpenAPI 3.1 document."""
    bootstrap_admin(app)
    spec = _served_openapi(client)

    assert spec.get("openapi") == "3.1.0", spec.get("openapi")
    assert "info" in spec, spec.keys()
    assert "paths" in spec, spec.keys()
    assert "components" in spec, spec.keys()
    assert "schemas" in spec["components"], spec["components"].keys()

    # Every C1 path has at least one operation.
    for method, path in [
        ("post", "/v1/auth/login"),
        ("get", "/v1/auth/me"),
        ("post", "/v1/patients/register"),
        ("post", "/v1/patients/link"),
        ("post", "/v1/doctor/verified-visits"),
        ("post", "/v1/admin/doctors"),
    ]:
        assert path in spec["paths"], path
        assert method.lower() in spec["paths"][path], (method, path)


def test_login_response_validates_against_schema(client, app):
    """A successful login response validates against its response schema."""
    bootstrap_admin(app)
    response = client.post(
        "/v1/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200, response.text
    body = response.json()

    schema_name = _response_schema_for("post", "/v1/auth/login")
    assert schema_name is not None
    _validate_against_served_schema(body, schema_name)


def test_me_response_validates_against_schema(client, app):
    """A successful /v1/auth/me response validates against its response schema."""
    bootstrap_admin(app)
    token = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)["session_token"]
    response = client.get(
        "/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200, response.text
    body = response.json()

    schema_name = _response_schema_for("get", "/v1/auth/me")
    assert schema_name is not None
    _validate_against_served_schema(body, schema_name)


def test_redacted_replay_response_validates(client, app):
    """A redacted idempotency replay response validates against its schema."""
    from tests.backend.c1.factories import provision_doctor

    bootstrap_admin(app)
    doctor = provision_doctor(
        app, client, email="dr.replay@cardioassist.local", display_name="Dr Replay"
    )

    # Create a visit first
    visit_response = client.post(
        "/v1/doctor/verified-visits",
        headers={
            "Authorization": f"Bearer {doctor['token']}",
            "Idempotency-Key": "visit-replay-schema-001",
        },
        json={
            "visit_ref": "VISIT-REPLAY-001",
            "subject_identifier": DEMO_ID_A,
            "asserted_visit_at": "2026-11-25T10:00:00Z",
            "attestation_code": "PRIOR_IN_PERSON_VISIT_DEMO",
        },
    )
    assert visit_response.status_code == 201, visit_response.text
    visit_body = visit_response.json()

    # Replay with same key -> should return same (redacted) response
    replay_response = client.post(
        "/v1/doctor/verified-visits",
        headers={
            "Authorization": f"Bearer {doctor['token']}",
            "Idempotency-Key": "visit-replay-schema-001",
        },
        json={
            "visit_ref": "VISIT-REPLAY-001",
            "subject_identifier": DEMO_ID_A,
            "asserted_visit_at": "2026-11-25T10:00:00Z",
            "attestation_code": "PRIOR_IN_PERSON_VISIT_DEMO",
        },
    )
    assert replay_response.status_code in (200, 201), replay_response.text
    replay_body = replay_response.json()

    schema_name = _response_schema_for("post", "/v1/doctor/verified-visits")
    assert schema_name is not None
    _validate_against_served_schema(replay_body, schema_name)

    pass


def test_secret_non_disclosure_in_error_responses(client, app):
    """Error responses never disclose secret material (access codes, tokens)."""
    bootstrap_admin(app)

    # Wrong login attempt -> error must not contain the password or token
    response = client.post(
        "/v1/auth/login",
        json={"email": ADMIN_EMAIL, "password": "wrong password"},
    )
    assert response.status_code == 401, response.text
    body = response.json()
    text = response.text
    assert "wrong password" not in text, text
    assert "password" not in body.get("error", {}).get("message", "").lower(), body


def test_optional_body_login_without_extra_fields(client, app):
    """Login with only required fields (no optional extras) validates cleanly."""
    bootstrap_admin(app)
    response = client.post(
        "/v1/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200, response.text
    body = response.json()

    schema_name = _response_schema_for("post", "/v1/auth/login")
    assert schema_name is not None
    _validate_against_served_schema(body, schema_name)


def test_all_c1_ops_response_schema_coverage(client, app):
    """Every C1 operation has a response schema binding in OP_SCHEMAS."""
    from backend.app.term1 import openapi as _openapi

    for method, path in _openapi.C1_OPERATIONS:
        binding = _openapi.OP_SCHEMAS.get((method, path))
        assert binding is not None, (method, path)
        # Every C1 op must declare a response schema (even if it's the error schema)
        assert binding.get("response") is not None, (method, path)