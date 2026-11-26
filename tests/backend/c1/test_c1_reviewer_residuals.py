"""Independent proposed regressions for PR #144 (2472f02 and dd91af5 baselines).

Synthetic disposable fixtures only. These are proposed acceptance tests, not
evidence of a successful run. Do not relax assertions to make a candidate pass.
"""
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from sqlalchemy import text

from backend.app.term1.errors import ApiError
from .conftest import ADMIN_EMAIL, ADMIN_PASSWORD, bearer, bootstrap_admin
from .factories import (
    DEMO_ID_A, attest_visit, issue_invitation, provision_doctor,
    register_patient, setup_doctor_with_invitation,
)


def _scalar(app, statement, parameters=None):
    with app.state.database.engine.connect() as connection:
        return connection.execute(text(statement), parameters or {}).scalar_one()


def _assert_http_schema(document, method, path, response):
    """Validate the real response using its actual served schema and status."""
    operation = document["paths"][path][method.lower()]
    status = str(response.status_code)
    assert status in operation["responses"], f"{method} {path}: undeclared {status}"
    content = operation["responses"][status]["content"]["application/json"]
    schema = content["schema"]
    # Resolve local JSON pointers against the actual served document. Existing
    # C1 schemas are inline after the component reference is resolved.
    while "$ref" in schema:
        ref = schema["$ref"]
        assert ref.startswith("#/"), "Expected local response reference"
        schema = document
        for segment in ref[2:].split("/"):
            schema = schema[segment.replace("~1", "/").replace("~0", "~")]
    validator = Draft202012Validator(
        schema, format_checker=Draft202012Validator.FORMAT_CHECKER
    )
    # Do not print response values: even synthetic credentials must stay out of
    # diagnostic messages.
    errors = [
        (tuple(error.absolute_path), tuple(error.absolute_schema_path), error.validator)
        for error in validator.iter_errors(response.json())
    ]
    assert not errors, f"{method} {path} {status}: schema violations {errors}"


def test_reviewer_fresh_unknown_invitation_then_first_visit_and_restart(
    app_factory, test_settings
):
    app = app_factory()
    with TestClient(app) as client:
        for table in ("identity_key_check", "verified_visit",
                      "patient_invitation", "invitation_attempt"):
            assert _scalar(app, f"SELECT COUNT(*) FROM {table}") == 0
        rejected = client.post(
            "/v1/patients/register",
            headers={"Idempotency-Key": "reviewer-first-unknown"},
            json={
                "access_code": "Z" * 43, "identifier": DEMO_ID_A,
                "email": "reviewer.unknown@cardioassist.local",
                "password": "synthetic patient password", "consent_ack": True,
            },
        )
        assert rejected.status_code == 401
        assert rejected.json()["error"]["code"] == "invalid_invitation"
        assert _scalar(app, "SELECT COUNT(*) FROM invitation_attempt") == 1
        assert _scalar(app, "SELECT COUNT(*) FROM user_account") == 0
        # No test-only binding or direct SQL mutation is permitted here.
        bootstrap_admin(app)
        doctor = provision_doctor(
            app, client, email="reviewer.doctor@cardioassist.local",
            display_name="Reviewer Demo Doctor",
        )
        first_visit = attest_visit(client, doctor, visit_ref="REVIEWER-FIRST")
        assert first_visit["visit_id"]
        assert _scalar(app, "SELECT COUNT(*) FROM identity_key_check") == 3

    restarted = app_factory()
    with TestClient(restarted) as client:
        assert attest_visit(client, doctor, visit_ref="REVIEWER-RESTART")["visit_id"]

    for field in ("identity_match_key", "subject_key", "pepper"):
        changed = replace(test_settings, **{field: b"reviewer-synthetic-changed-key-0001"})
        with pytest.raises(ApiError) as caught:
            with TestClient(app_factory(term1_settings=changed)):
                pytest.fail("Changed key unexpectedly accepted at startup")
        assert caught.value.code in {
            "identity_key_material_mismatch", "identity_key_replacement_unsupported"
        }

    with TestClient(app_factory()) as client:
        assert attest_visit(client, doctor, visit_ref="REVIEWER-ORIGINAL")["visit_id"]


def test_reviewer_pepper_is_bound_before_login_failure_without_visits(
    app_factory, test_settings
):
    app = app_factory()
    with TestClient(app) as client:
        bootstrap_admin(app)
        rejected = client.post("/v1/auth/login", json={
            "email": ADMIN_EMAIL, "password": "synthetic incorrect password",
        })
        assert rejected.status_code == 401
        assert _scalar(app, "SELECT COUNT(*) FROM login_attempt") > 0
        assert _scalar(app, "SELECT COUNT(*) FROM verified_visit") == 0
    with pytest.raises(ApiError):
        with TestClient(app_factory(term1_settings=replace(
            test_settings, pepper=b"reviewer-synthetic-changed-pepper-001"
        ))):
            pytest.fail("Changed pepper accepted after durable login attempts")


def test_reviewer_link_success_and_replay_match_served_response_schema(client, app):
    document = client.get("/openapi.json").json()
    chain = setup_doctor_with_invitation(app, client)
    registration = register_patient(client, chain["invitation"]["access_code"])
    second = provision_doctor(
        app, client, email="reviewer.second@cardioassist.local",
        display_name="Reviewer Second Doctor",
    )
    visit = attest_visit(client, second, visit_ref="REVIEWER-LINK")
    invitation = issue_invitation(client, second, visit["visit_id"])
    headers = {
        **bearer(registration["session_token"]),
        "Idempotency-Key": "reviewer-link-schema",
    }
    payload = {
        "access_code": invitation["access_code"], "identifier": DEMO_ID_A,
        "accept_linking": True,
    }
    path = "/v1/patients/link"
    first = client.post(path, headers=headers, json=payload)
    assert first.status_code == 200
    replay = client.post(path, headers=headers, json=payload)
    assert replay.status_code == 200
    assert replay.json()["idempotent_replay"] is True
    assert first.json()["assignment_id"] == replay.json()["assignment_id"]
    _assert_http_schema(document, "post", path, first)
    _assert_http_schema(document, "post", path, replay)


def test_reviewer_unauthenticated_link_does_not_consume_invitation_attempt(client, app):
    chain = setup_doctor_with_invitation(app, client)
    invitation = chain["invitation"]
    query = "SELECT attempt_count FROM patient_invitation WHERE invitation_id=:id"
    params = {"id": invitation["invitation_id"]}
    before = _scalar(app, query, params)
    response = client.post(
        "/v1/patients/link",
        headers={"Idempotency-Key": "reviewer-no-auth-link"},
        json={
            "access_code": invitation["access_code"], "identifier": DEMO_ID_A,
            "accept_linking": True,
        },
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"
    assert _scalar(app, query, params) == before


def test_reviewer_failure_audit_uses_one_writer_and_one_event(client, app, monkeypatch):
    from backend.app.term1 import api

    chain = setup_doctor_with_invitation(app, client)
    invite = chain["invitation"]
    query = ("SELECT COUNT(*) FROM workflow_audit_event "
             "WHERE event_type='INVITATION_ATTEMPT_FAILED'")
    before = _scalar(app, query)

    def forbidden_isolated_writer(*args, **kwargs):
        pytest.fail("Enrollment failure opened an isolated writer under the outer lock")

    monkeypatch.setattr(api, "record_isolated", forbidden_isolated_writer)
    response = client.post(
        "/v1/patients/register",
        headers={"Idempotency-Key": "reviewer-single-writer"},
        json={
            "access_code": invite["access_code"],
            "identifier": "DEMO-ID-999",
            "email": "reviewer.mismatch@cardioassist.local",
            "password": "synthetic patient password", "consent_ack": True,
        },
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_invitation"
    assert _scalar(app, query) == before + 1
    assert _scalar(app, "SELECT COUNT(*) FROM patient_identity") == 0
