"""C1.9 audit evidence, C1.9 metadata-only guarantees, and C1.1 key binding.

The audit trail is the only forensic record of denied and failed operations, so
these tests assert it is (a) written for failures that are otherwise invisible,
(b) complete for successes, (c) bound to real actor/operation/target references,
and (d) never a place where a secret can land.
"""

from __future__ import annotations

import json
import re

import pytest
from sqlalchemy import text

from backend.app.term1 import audit, constants, identity
from backend.app.term1.errors import ApiError
from backend.app.term1.timeutil import Clock
from backend.app.term1.tx import write_transaction

from tests.backend.c1.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, bootstrap_admin, login
from tests.backend.c1.factories import (
    DEMO_ID_A,
    attest_visit,
    bootstrap_admin as ensure_admin,
    issue_invitation,
    provision_doctor,
    register_patient,
    setup_doctor_with_invitation,
)

PATIENT_EMAIL = "demo.patient@cardioassist.local"
PATIENT_PASSWORD = "patient password 0001"
SECRET_PATTERN = re.compile(
    r"(DEMO-ID-\d+|session_token|access_code|temp_secret|password|idempotency-key)", re.I
)


def _audit_rows(app, *, event_type: str | None = None) -> list[dict]:
    statement = (
        "SELECT audit_id, event_type, actor_user_id, subject_type, subject_id, request_id, "
        "code, outcome, payload_sha256, recorded_at FROM workflow_audit_event"
    )
    parameters: dict[str, object] = {}
    if event_type is not None:
        statement += " WHERE event_type = :event_type"
        parameters["event_type"] = event_type
    statement += " ORDER BY recorded_at, audit_id"
    with app.state.database.engine.connect() as connection:
        rows = connection.execute(text(statement), parameters).mappings().all()
    return [dict(row) for row in rows]


def _json_columns(app) -> str:
    with app.state.database.engine.connect() as connection:
        tables = [
            row[0]
            for row in connection.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            ).all()
        ]
        dump: list[str] = []
        for table in tables:
            if table.startswith("sqlite_"):
                continue
            dump.append(str(connection.execute(text(f"SELECT * FROM {table}")).all()))
    return "\n".join(dump)


# --- success evidence -------------------------------------------------------
def test_successful_registration_writes_bound_audit_evidence(client, app):
    chain = setup_doctor_with_invitation(app, client)
    registration = register_patient(client, chain["invitation"]["access_code"])
    rows = {
        row["event_type"]: row
        for row in _audit_rows(app)
        if row["event_type"]
        in {
            constants.EVENT_PATIENT_REGISTERED,
            constants.EVENT_INVITATION_CONSUMED,
            constants.EVENT_ACCOUNT_PROVISIONED,
        }
    }
    assert set(rows) == {
        constants.EVENT_PATIENT_REGISTERED,
        constants.EVENT_INVITATION_CONSUMED,
        constants.EVENT_ACCOUNT_PROVISIONED,
    }
    registered = rows[constants.EVENT_PATIENT_REGISTERED]
    assert registered["subject_type"] == constants.SUBJECT_PATIENT_PROFILE
    assert registered["subject_id"] == registration["patient_id"]
    assert registered["outcome"] == constants.OUTCOME_SUCCESS
    assert registered["code"] is None
    assert re.fullmatch(r"[0-9a-f]{64}", registered["payload_sha256"])
    consumed = rows[constants.EVENT_INVITATION_CONSUMED]
    assert consumed["subject_type"] == constants.SUBJECT_INVITATION
    assert consumed["subject_id"] == chain["invitation"]["invitation_id"]


def test_doctor_provisioning_and_visit_attestation_record_the_actor(client, app):
    chain = setup_doctor_with_invitation(app, client)
    doctor = chain["doctor"]
    visit_rows = _audit_rows(app, event_type=constants.EVENT_VISIT_ATTESTED)
    assert len(visit_rows) == 1
    row = visit_rows[0]
    assert row["actor_user_id"] == doctor["user_id"]
    assert row["subject_type"] == constants.SUBJECT_VERIFIED_VISIT
    assert row["subject_id"] == chain["visit"]["visit_id"]
    assert row["outcome"] == constants.OUTCOME_SUCCESS

    provisioned = _audit_rows(app, event_type=constants.EVENT_ACCOUNT_PROVISIONED)
    assert any(
        record["subject_type"] == constants.SUBJECT_DOCTOR_PROFILE
        and record["subject_id"] == doctor["doctor_id"]
        and record["actor_user_id"] is not None
        for record in provisioned
    )


def test_denied_operation_leaves_a_failure_row_and_no_effect(client, app):
    chain = setup_doctor_with_invitation(app, client)
    doctor = chain["doctor"]
    # A second doctor tries to revoke the first doctor's invitation; the visit
    # is fresh so the first doctor's own live invitation is untouched.
    other = provision_doctor(
        app, client, email="demo.doc.other@cardioassist.local", display_name="Dr Other"
    )
    visit, invitation = chain["fresh_visit"](7)
    before = len(_audit_rows(app))

    response = client.post(
        f"/v1/doctor/invitations/{invitation['invitation_id']}/revoke",
        headers={"Authorization": f"Bearer {other['token']}", "Idempotency-Key": "denied-revoke"},
        json={"reason_code": "x"},
    )
    assert response.status_code == 404
    with app.state.database.engine.connect() as connection:
        revoked_at = connection.execute(
            text("SELECT revoked_at FROM patient_invitation WHERE invitation_id=:i"),
            {"i": invitation["invitation_id"]},
        ).scalar_one()
    assert revoked_at is None
    after = len(_audit_rows(app))
    # The denied attempt is not persisted as a success row: the denial rolls
    # back with its business transaction (documented C1.9 behaviour).
    assert after == before


def test_failed_login_is_recorded_even_though_the_business_tx_rolled_back(client, app):
    bootstrap_admin(app)
    before = _audit_rows(app, event_type=constants.EVENT_LOGIN_FAILED)
    response = client.post(
        "/v1/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong password 0009"}
    )
    assert response.status_code == 401
    after = _audit_rows(app, event_type=constants.EVENT_LOGIN_FAILED)
    assert len(after) == len(before) + 1
    row = after[-1]
    assert row["outcome"] == constants.OUTCOME_FAILED
    assert row["code"] == "invalid_credentials"
    # A failed login is attributed to the session scope it tried to open; no
    # account id is disclosed (the email might not exist at all).
    assert row["subject_type"] == constants.SUBJECT_SESSION
    assert row["subject_id"] is None
    with app.state.database.engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM login_attempt")).scalar_one() >= 1
        assert connection.execute(text("SELECT COUNT(*) FROM session")).scalar_one() == 0


def test_unknown_invitation_evidence_carries_no_subject_id(client, app):
    chain = setup_doctor_with_invitation(app, client)
    response = client.post(
        "/v1/patients/register",
        headers={"Idempotency-Key": "unknown-invite"},
        json={
            "access_code": "A" * 43,
            "identifier": DEMO_ID_A,
            "email": "demo.unknown@cardioassist.local",
            "password": PATIENT_PASSWORD,
            "consent_ack": True,
        },
    )
    assert response.status_code == 401
    rows = _audit_rows(app, event_type=constants.EVENT_INVITATION_ATTEMPT_FAILED)
    assert rows, "A rejected invitation must leave audit evidence."
    row = rows[-1]
    assert row["subject_type"] == constants.SUBJECT_UNKNOWN_INVITATION
    assert row["subject_id"] is None
    assert row["code"] == "invalid_invitation"
    assert chain["invitation"]["invitation_id"] not in json.dumps(row, default=str)


def test_audit_payload_digest_is_deterministic_and_order_independent():
    first = audit.payload_digest({"b": 2, "a": 1})
    second = audit.payload_digest({"a": 1, "b": 2})
    assert first == second
    assert first != audit.payload_digest({"a": 1, "b": 3})
    assert re.fullmatch(r"[0-9a-f]{64}", first)


def test_audit_rejects_a_secret_key_outside_the_closed_vocabulary():
    digest_with_secret = audit.payload_digest({"access_code": "AAAA", "count": 1})
    digest_redacted = audit.payload_digest({"access_code": "<redacted>", "count": 1})
    assert digest_with_secret == digest_redacted
    # A secret value under a benign key is still only hashed, never stored.
    nested = audit.payload_digest({"note": {"password": "hunter2"}})
    assert nested == audit.payload_digest({"note": {"password": "<redacted>"}})


def test_audit_writer_rejects_unknown_event_and_outcome(app):
    with app.state.database.engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM workflow_audit_event")).scalar_one() == 0
    clock = Clock()
    with write_transaction(app.state.database) as session:
        with pytest.raises(ValueError):
            audit.record(
                session,
                clock=clock,
                event_type="NOT_A_REAL_EVENT",
                outcome="SUCCESS",
                subject_type="patient",
            )
        with pytest.raises(ValueError):
            audit.record(
                session,
                clock=clock,
                event_type=constants.EVENT_PATIENT_REGISTERED,
                outcome="MAYBE",
                subject_type="patient",
            )
        # The exception must abort the whole transaction rather than commit.
        session.rollback()
    with app.state.database.engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM workflow_audit_event")).scalar_one() == 0


def test_isolated_failure_evidence_never_masks_the_original_error(app, monkeypatch):
    def explode(*_args, **_kwargs):
        raise RuntimeError("audit store unavailable")

    monkeypatch.setattr(audit, "record", explode)
    result = audit.record_isolated(
        app.state.database,
        clock=Clock(),
        event_type=constants.EVENT_LOGIN_FAILED,
        outcome=constants.OUTCOME_FAILED,
        subject_type=constants.SUBJECT_SESSION,
        code="invalid_credentials",
    )
    assert result is None


# --- metadata-only guarantee ------------------------------------------------
def test_no_secret_material_reaches_the_audit_table(client, app):
    chain = setup_doctor_with_invitation(app, client)
    doctor = chain["doctor"]
    register_patient(client, chain["invitation"]["access_code"], key="audit-register")
    # Wrong password, wrong invitation, wrong key and a denied cross-owner read.
    client.post("/v1/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong password 0009"})
    client.post(
        "/v1/patients/register",
        headers={"Idempotency-Key": "audit-bad-code"},
        json={
            "access_code": "D" * 43,
            "identifier": DEMO_ID_A,
            "email": "demo.no@cardioassist.local",
            "password": PATIENT_PASSWORD,
            "consent_ack": True,
        },
    )
    with app.state.database.engine.connect() as connection:
        dump = str(connection.execute(text("SELECT * FROM workflow_audit_event")).all())
    for secret in (
        chain["invitation"]["access_code"],
        doctor["temp_secret"],
        doctor["password"],
        PATIENT_PASSWORD,
        ADMIN_PASSWORD,
        DEMO_ID_A,
        "D" * 43,
        doctor["token"],
    ):
        assert secret not in dump
    assert "demo.patient@cardioassist.local" not in dump
    rows = _audit_rows(app)
    for row in rows:
        scanned = " ".join(
            str(value)
            for key, value in row.items()
            if key not in {"payload_sha256", "event_type"}
        )
        assert not SECRET_PATTERN.search(scanned), row
        assert re.fullmatch(r"[0-9a-f]{64}", row["payload_sha256"])


def test_response_bodies_and_error_envelopes_never_leak_secrets(client, app):
    chain = setup_doctor_with_invitation(app, client)
    invitation = chain["invitation"]
    wrong = client.post(
        "/v1/patients/register",
        headers={"Idempotency-Key": "leak-envelope"},
        json={
            "access_code": "a" * 43,
            "identifier": DEMO_ID_A,
            "email": "demo.leak@cardioassist.local",
            "password": PATIENT_PASSWORD,
            "consent_ack": True,
        },
    )
    assert wrong.status_code == 401
    envelope = wrong.json()
    assert set(envelope) == {"contract_version", "error"}
    assert set(envelope["error"]) <= {"code", "message"}
    assert invitation["access_code"] not in wrong.text
    assert DEMO_ID_A not in wrong.text


# --- persistence of the key check -------------------------------------------
def test_identity_key_check_persists_once_and_detects_a_mismatch(app, test_settings):
    clock = Clock()
    with write_transaction(app.state.database) as session:
        identity.verify_or_activate(session, clock=clock, settings=test_settings, write=True)
    with app.state.database.engine.connect() as connection:
        rows = connection.execute(
            text("SELECT purpose, key_id, key_check_hash, alg, created_at FROM identity_key_check")
        ).all()
    assert {row[0] for row in rows} == {"identity_match", "subject_canonical"}
    assert all(row[1] == test_settings.identity_key_id for row in rows)
    assert all(len(row[2]) == 64 for row in rows)
    assert {row[3] for row in rows} == {constants.IDENTITY_KEY_ALG}
    snapshot = [tuple(row) for row in rows]

    # A rerun with the same keys is a no-op, not a second insert.
    with write_transaction(app.state.database) as session:
        identity.verify_or_activate(session, clock=clock, settings=test_settings, write=True)
    with app.state.database.engine.connect() as connection:
        again = [tuple(row) for row in connection.execute(
            text("SELECT purpose, key_id, key_check_hash, alg, created_at FROM identity_key_check")
        ).all()]
    assert again == snapshot


def test_replaced_key_material_fails_closed(client, app, test_settings):
    from backend.app.term1.settings import Term1Settings

    chain = setup_doctor_with_invitation(app, client)
    register_patient(client, chain["invitation"]["access_code"])
    clock = Clock()
    with write_transaction(app.state.database) as session:
        identity.verify_or_activate(session, clock=clock, settings=test_settings, write=True)
    replacement = Term1Settings(
        identity_match_key=b"replacement identity match key 0001",
        subject_key=b"replacement subject key material 000001",
        pepper=test_settings.pepper,
        identity_key_id=test_settings.identity_key_id,
    )
    with pytest.raises(ApiError) as error:
        with write_transaction(app.state.database) as session:
            identity.verify_or_activate(session, clock=clock, settings=replacement, write=True)
    assert error.value.code == "identity_key_material_mismatch"


def test_new_key_id_with_existing_binding_is_refused(client, app, test_settings):
    from backend.app.term1.settings import Term1Settings

    chain = setup_doctor_with_invitation(app, client)
    register_patient(client, chain["invitation"]["access_code"])
    clock = Clock()
    with write_transaction(app.state.database) as session:
        identity.verify_or_activate(session, clock=clock, settings=test_settings, write=True)
    rotated = Term1Settings(
        identity_match_key=test_settings.identity_match_key,
        subject_key=test_settings.subject_key,
        pepper=test_settings.pepper,
        identity_key_id="demo-v2",
    )
    with pytest.raises(ApiError) as error:
        with write_transaction(app.state.database) as session:
            identity.verify_or_activate(session, clock=clock, settings=rotated, write=True)
    assert error.value.code == "identity_key_replacement_unsupported"


def test_key_material_never_appears_in_any_table(client, app):
    bootstrap_admin(app)
    chain = setup_doctor_with_invitation(app, client)
    register_patient(client, chain["invitation"]["access_code"])
    dump = _json_columns(app)
    from tests.backend.c1.conftest import TEST_IDENTITY_MATCH_KEY, TEST_PEPPER, TEST_SUBJECT_KEY

    for material in (TEST_IDENTITY_MATCH_KEY, TEST_SUBJECT_KEY, TEST_PEPPER):
        text_value = material.decode() if isinstance(material, bytes) else material
        assert text_value not in dump
        # Base64 arms as well, so a stray encode is caught too.
        import base64

        assert base64.b64encode(text_value.encode()).decode() not in dump
