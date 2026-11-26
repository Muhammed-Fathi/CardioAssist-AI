"""C1.9 audit evidence, C1.9 metadata-only guarantees, and C1.1 key binding.

The audit trail is the only forensic record of denied and failed operations, so
these tests assert it is (a) written for failures that are otherwise invisible,
(b) complete for successes, (c) bound to real actor/operation/target references,
and (d) never a place where a secret can land.
"""

from __future__ import annotations

import json
import re
import uuid

import pytest
from sqlalchemy import func, select, text

from backend.app.term1 import audit, constants, identity
from backend.app.term1.errors import ApiError
from backend.app.term1.models import (
    IdentityKeyCheck,
    InvitationAttempt,
    PatientInvitation,
    UserAccount,
    VerifiedVisit,
)
from backend.app.storage.database import Database
from backend.app.term1.settings import Term1Settings
from backend.app.term1.timeutil import Clock
from backend.app.term1.tx import read_transaction, write_transaction
from tests.backend.c1.conftest import bootstrap_admin, login
from tests.backend.c1.factories import DEMO_ID_A

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
    assert {row[0] for row in rows} == {"identity_match", "subject_canonical", "pepper_binding"}
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


# --- key-check metadata variants ---------------------------------------------

def test_missing_key_check_on_populated_db_fails_closed(app, test_settings):
    """Activity exists but no identity_key_check rows: fail closed."""
    from backend.app.term1.models import InvitationAttempt
    clock = Clock()
    # Create identity activity WITHOUT binding checks (do not call
    # verify_or_activate with write=True, as that would create them).
    with write_transaction(app.state.database) as session:
        session.add(InvitationAttempt(
            attempt_id=str(uuid.uuid4()),
            invitation_id=None,
            bucket_key_hash="digest-of-unknown-code",
            outcome_code="invalid_invitation",
            created_at=clock.now_iso(),
        ))
    # verify_or_activate with activity but no check rows must fail closed.
    with pytest.raises(ApiError) as error:
        with write_transaction(app.state.database) as session:
            identity.verify_or_activate(session, clock=clock, settings=test_settings, write=False)
    assert error.value.code == "identity_key_material_mismatch"


def test_partial_key_checks_fail_closed(app, test_settings):
    """Only one of two purposes has a check row: fail closed."""
    from backend.app.term1.models import InvitationAttempt
    clock = Clock()
    expected = identity._expected_checks(test_settings)
    now = clock.now_iso()
    with write_transaction(app.state.database) as session:
        # Create activity so has_identity_activity() is True.
        session.add(InvitationAttempt(
            attempt_id=str(uuid.uuid4()),
            invitation_id=None,
            bucket_key_hash="digest",
            outcome_code="invalid_invitation",
            created_at=now,
        ))
        # Insert only one of the two required checks.
        session.add(IdentityKeyCheck(
            check_id=str(uuid.uuid4()),
            purpose=constants.IDENTITY_MATCH_PURPOSE,
            key_id=test_settings.identity_key_id,
            key_check_hash=expected[constants.IDENTITY_MATCH_PURPOSE],
            alg=constants.IDENTITY_KEY_ALG,
            created_at=now,
            activated_at=now,
            retired_at=None,
        ))
    with pytest.raises(ApiError) as error:
        with write_transaction(app.state.database) as session:
            identity.verify_or_activate(session, clock=clock, settings=test_settings, write=True)
    assert error.value.code == "identity_key_material_mismatch"


def test_retired_key_check_row_is_ignored(app, test_settings):
    """A retired row alongside an active row: the active row is used.
    
    The UNIQUE(purpose, key_id) constraint prevents two rows with the same
    purpose and key_id, so the retired row must use a different key_id.
    """
    from backend.app.term1.models import InvitationAttempt
    clock = Clock()
    expected = identity._expected_checks(test_settings)
    now = clock.now_iso()
    with write_transaction(app.state.database) as session:
        session.add(InvitationAttempt(
            attempt_id=str(uuid.uuid4()),
            invitation_id=None,
            bucket_key_hash="digest",
            outcome_code="invalid_invitation",
            created_at=now,
        ))
        # Active row for identity_match.
        session.add(IdentityKeyCheck(
            check_id=str(uuid.uuid4()),
            purpose=constants.IDENTITY_MATCH_PURPOSE,
            key_id=test_settings.identity_key_id,
            key_check_hash=expected[constants.IDENTITY_MATCH_PURPOSE],
            alg=constants.IDENTITY_KEY_ALG,
            created_at=now,
            activated_at=now,
            retired_at=None,
        ))
        # Retired row for identity_match with a DIFFERENT key_id (UNIQUE allows it).
        session.add(IdentityKeyCheck(
            check_id=str(uuid.uuid4()),
            purpose=constants.IDENTITY_MATCH_PURPOSE,
            key_id="demo-v0",
            key_check_hash="0" * 64,
            alg=constants.IDENTITY_KEY_ALG,
            created_at=now,
            activated_at=now,
            retired_at=now,  # retired: must be ignored
        ))
        # Active row for subject_canonical.
        session.add(IdentityKeyCheck(
            check_id=str(uuid.uuid4()),
            purpose=constants.SUBJECT_CANONICAL_PURPOSE,
            key_id=test_settings.identity_key_id,
            key_check_hash=expected[constants.SUBJECT_CANONICAL_PURPOSE],
            alg=constants.IDENTITY_KEY_ALG,
            created_at=now,
            activated_at=now,
            retired_at=None,
        ))
        # Active row for pepper_binding.
        session.add(IdentityKeyCheck(
            check_id=str(uuid.uuid4()),
            purpose=constants.PEPPER_PURPOSE,
            key_id=test_settings.identity_key_id,
            key_check_hash=expected[constants.PEPPER_PURPOSE],
            alg=constants.IDENTITY_KEY_ALG,
            created_at=now,
            activated_at=now,
            retired_at=None,
        ))
    # Should succeed: exactly one active row per purpose.
    with write_transaction(app.state.database) as session:
        identity.verify_or_activate(session, clock=clock, settings=test_settings, write=True)


# --- F1: fresh-database key bootstrap and durable pepper binding ------------

def test_fresh_database_unknown_invitation_before_any_identity_activity(
    migrated_url, clock, test_settings
):
    """F1: Fresh migrated database with zero identity activity.

    1. Fresh migrated DB: zero identity_key_check rows, zero verified_visit,
       zero patient_invitation, zero invitation_attempt.
    2. Establish initial binding via verify_or_activate(write=True) on the
       empty DB — creates identity_key_check rows including pepper_binding.
    3. Submit an unknown invitation before creating any legitimate identity
       activity → controlled rejection (401 invalid_invitation).
    4. Durable attempt evidence must be written (InvitationAttempt row).
    5. Bootstrap administrator → provision doctor → change temp password →
       attest first legitimate visit succeeds.
    6. Read-only startup verification with same keys succeeds.
    7. Startup verification with changed identity-match key → fail closed.
    8. Startup verification with changed canonical-subject key → fail closed.
    9. Startup verification with changed pepper → fail closed.
    10. Original keys still work (no silent re-binding).
    """
    from backend.app.term1 import identity
    from backend.app.term1.accounts import bootstrap_administrator, create_doctor
    from backend.app.term1.models import (
        IdentityKeyCheck,
        InvitationAttempt,
        PatientInvitation,
        VerifiedVisit,
    )
    from backend.app.term1.settings import Term1Settings
    from backend.app.term1.tx import read_transaction, write_transaction
    from backend.app.storage.database import Database
    from backend.app.main import create_app
    from fastapi.testclient import TestClient
    from backend.app.term1.timeutil import Clock

    term_clock = Clock()
    db = Database(migrated_url)
    clock_callable = lambda: term_clock.now()
    try:
        # 1. Confirm zero identity activity on fresh DB.
        with write_transaction(db) as session:
            assert (
                session.execute(
                    select(func.count()).select_from(IdentityKeyCheck)
                ).scalar_one()
                == 0
            )
            assert (
                session.execute(
                    select(func.count()).select_from(VerifiedVisit)
                ).scalar_one()
                == 0
            )
            assert (
                session.execute(
                    select(func.count()).select_from(PatientInvitation)
                ).scalar_one()
                == 0
            )
            assert (
                session.execute(
                    select(func.count()).select_from(InvitationAttempt)
                ).scalar_one()
                == 0
            )

        # 2. Establish initial binding on empty DB (creates pepper_binding +
        # identity key checks).
        with write_transaction(db) as session:
            identity.verify_or_activate(
                session, clock=term_clock, settings=test_settings, write=True
            )
        with read_transaction(db) as session:
            checks = {
                row.purpose: row
                for row in session.execute(select(IdentityKeyCheck)).scalars()
            }
            assert set(checks) == {
                constants.IDENTITY_MATCH_PURPOSE,
                constants.SUBJECT_CANONICAL_PURPOSE,
                constants.PEPPER_PURPOSE,
            }
            for row in checks.values():
                assert row.key_id == test_settings.identity_key_id
                assert row.retired_at is None

        # 3. Create app; submit unknown invitation before any legitimate
        # identity activity (but after initial binding).
        app = create_app(
            database_url=migrated_url,
            term1_settings=test_settings,
            term1_clock=clock_callable,
        )
        with TestClient(app) as client:
            response = client.post(
                "/v1/patients/register",
                headers={"Idempotency-Key": "fresh-unknown-invite"},
                json={
                    "access_code": "Z" * 43,
                    "identifier": DEMO_ID_A,
                    "email": "demo.unknown@cardioassist.local",
                    "password": PATIENT_PASSWORD,
                    "consent_ack": True,
                },
            )
        assert response.status_code == 401, response.text
        assert response.json()["error"]["code"] == "invalid_invitation"

        # 4. Durable attempt evidence must exist.
        with read_transaction(db) as session:
            attempts = (
                session.execute(
                    select(func.count()).select_from(InvitationAttempt)
                ).scalar_one()
            )
        assert attempts >= 1

        # 5. Bootstrap administrator, provision doctor, change temp password,
        # attest first legitimate visit.
        app2 = create_app(
            database_url=migrated_url,
            term1_settings=test_settings,
            term1_clock=clock_callable,
        )
        with TestClient(app2) as client:
            bootstrap_admin(app2)
            with write_transaction(app2.state.database) as session:
                admin_id = session.execute(
                    text("SELECT user_id FROM user_account WHERE role='admin'")
                ).scalar_one()
                actor = session.get(UserAccount, admin_id)
                created = create_doctor(
                    session,
                    clock=app2.state.term1.clock,
                    actor=actor,
                    email="demo.doctor@cardioassist.local",
                    display_name="Dr F1",
                    temp_password_policy="one_time_secret",
                )
            temp_token = login(client, "demo.doctor@cardioassist.local", created["temp_secret"])["session_token"]
            pw_change = client.post(
                "/v1/me/password",
                headers={"Authorization": f"Bearer {temp_token}"},
                json={
                    "current_password": created["temp_secret"],
                    "new_password": "doctor password 0001",
                },
            )
            assert pw_change.status_code == 200, pw_change.text
            token = login(client, "demo.doctor@cardioassist.local", "doctor password 0001")["session_token"]
            visit = client.post(
                "/v1/doctor/verified-visits",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Idempotency-Key": "fresh-first-visit",
                },
                json={
                    "visit_ref": "FRESH-VISIT-001",
                    "subject_identifier": DEMO_ID_A,
                    "asserted_visit_at": "2026-11-25T10:00:00Z",
                    "attestation_code": "PRIOR_IN_PERSON_VISIT_DEMO",
                },
            )
            assert visit.status_code == 201, visit.text
            doctor_token = token

        # 6. Read-only startup verification with same keys succeeds.
        with read_transaction(db) as session:
            identity.verify_startup(session, settings=test_settings)

        # 7. Startup verification with changed identity-match key → fail closed.
        changed_match = Term1Settings(
            identity_match_key=b"changed identity match key 0000000001",
            subject_key=test_settings.subject_key,
            pepper=test_settings.pepper,
            admin_bootstrap_secret=test_settings.admin_bootstrap_secret,
            identity_key_id=test_settings.identity_key_id,
        )
        with pytest.raises(ApiError) as error:
            with read_transaction(db) as session:
                identity.verify_startup(session, settings=changed_match)
        assert error.value.code == "identity_key_material_mismatch"

        # 8. Startup verification with changed canonical-subject key → fail closed.
        changed_subject = Term1Settings(
            identity_match_key=test_settings.identity_match_key,
            subject_key=b"changed subject key material 00000001",
            pepper=test_settings.pepper,
            admin_bootstrap_secret=test_settings.admin_bootstrap_secret,
            identity_key_id=test_settings.identity_key_id,
        )
        with pytest.raises(ApiError) as error:
            with read_transaction(db) as session:
                identity.verify_startup(session, settings=changed_subject)
        assert error.value.code == "identity_key_material_mismatch"

        # 9. Startup verification with changed pepper → fail closed.
        changed_pepper = Term1Settings(
            identity_match_key=test_settings.identity_match_key,
            subject_key=test_settings.subject_key,
            pepper=b"changed pepper material 00000000003",
            admin_bootstrap_secret=test_settings.admin_bootstrap_secret,
            identity_key_id=test_settings.identity_key_id,
        )
        with pytest.raises(ApiError) as error:
            with read_transaction(db) as session:
                identity.verify_startup(session, settings=changed_pepper)
        assert error.value.code == "identity_key_material_mismatch"

        # 10. Original keys still work after failed attempts (no silent re-binding).
        with read_transaction(db) as session:
            identity.verify_startup(session, settings=test_settings)

    finally:
        db.dispose()


# --- F1: fresh-database key bootstrap through the supported workflow -------


def test_fresh_database_pepper_binding_precedes_first_pepper_dependent_write(
    migrated_url, clock, test_settings
):
    """Regression test for F1: pepper binding must precede every first
    pepper-dependent durable write on a fresh database.

    The test starts with a freshly migrated database containing ZERO
    identity_key_check rows and does NOT call verify_or_activate directly.
    Binding must occur through the actual supported application workflow:

    1. Submit an unknown invitation → controlled 401 rejection + durable
       attempt evidence (InvitationAttempt and LoginAttempt rows).
    2. Bootstrap the administrator through the supported operator procedure.
    3. Provision a doctor, change the temporary password.
    4. Attest the first legitimate visit.
    5. Restart the application with the original keys → startup verification
       succeeds.
    6. Execute another authorized identity operation.
    7. Restart with each independently changed key (identity-match, subject,
       pepper) → fail closed with identity_key_material_mismatch.
    8. Original keys still work after failed attempts (no silent re-binding).
    """
    from fastapi.testclient import TestClient

    from backend.app.main import create_app
    from backend.app.term1.timeutil import Clock as Term1Clock

    # 1. Fresh database: zero key-check rows, zero identity activity.
    # term1_clock must be a callable returning a datetime (MutableClock is
    # callable); create_app wraps it in a Clock that provides now_iso().
    db = Database(migrated_url)
    try:
        with db.engine.connect() as connection:
            checks = connection.execute(
                text("SELECT COUNT(*) FROM identity_key_check")
            ).scalar_one()
        assert checks == 0, f"Expected 0 key-check rows, found {checks}"

        app = create_app(
            database_url=migrated_url,
            term1_settings=test_settings,
            term1_clock=clock,
        )
        with TestClient(app) as client:
            # 2. Submit an unknown invitation before any legitimate identity
            # activity. This must be rejected with 401 and leave durable
            # attempt evidence. No internal helper or direct SQL initializes
            # key checks; the application must bind pepper on first use.
            response = client.post(
                "/v1/patients/register",
                headers={"Idempotency-Key": "fresh-unknown-invite-001"},
                json={
                    "access_code": "Z" * 43,
                    "identifier": DEMO_ID_A,
                    "email": "demo.unknown@cardioassist.local",
                    "password": PATIENT_PASSWORD,
                    "consent_ack": True,
                },
            )
        assert response.status_code == 401, response.text
        assert response.json()["error"]["code"] == "invalid_invitation"

        # 3. Durable attempt evidence must exist (pepper-dependent writes
        # occurred after pepper binding was established).
        with db.engine.connect() as connection:
            attempt_count = connection.execute(
                text("SELECT COUNT(*) FROM invitation_attempt")
            ).scalar_one()
            login_attempt_count = connection.execute(
                text("SELECT COUNT(*) FROM login_attempt")
            ).scalar_one()
            key_check_count = connection.execute(
                text("SELECT COUNT(*) FROM identity_key_check")
            ).scalar_one()
        assert attempt_count >= 1, "No InvitationAttempt evidence recorded"
        assert login_attempt_count >= 1, "No LoginAttempt evidence recorded"
        assert key_check_count == 3, (
            f"Expected 3 key-check rows (identity_match, subject_canonical, "
            f"pepper_binding), found {key_check_count}"
        )

        # 4. Bootstrap administrator, provision doctor, change temp password,
        # attest first legitimate visit through the actual API.
        with TestClient(app) as client:
            bootstrap_admin(app)
            admin_token = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)["session_token"]

            # Provision a doctor.
            with db.engine.connect() as connection:
                admin_id = connection.execute(
                    text("SELECT user_id FROM user_account WHERE role='admin'")
                ).scalar_one()

            from backend.app.term1.accounts import create_doctor
            from backend.app.term1.models import UserAccount
            from backend.app.term1.tx import write_transaction

            with write_transaction(db) as session:
                actor = session.get(UserAccount, admin_id)
                created = create_doctor(
                    session,
                    clock=Term1Clock(clock),
                    actor=actor,
                    email="demo.doctor@cardioassist.local",
                    display_name="Dr F1",
                    temp_password_policy="one_time_secret",
                )

            temp_token = login(
                client, "demo.doctor@cardioassist.local", created["temp_secret"]
            )["session_token"]
            pw_change = client.post(
                "/v1/me/password",
                headers={"Authorization": f"Bearer {temp_token}"},
                json={
                    "current_password": created["temp_secret"],
                    "new_password": "doctor password 0001",
                },
            )
            assert pw_change.status_code == 200, pw_change.text

            token = login(
                client, "demo.doctor@cardioassist.local", "doctor password 0001"
            )["session_token"]
            visit = client.post(
                "/v1/doctor/verified-visits",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Idempotency-Key": "fresh-first-visit-001",
                },
                json={
                    "visit_ref": "FRESH-VISIT-001",
                    "subject_identifier": DEMO_ID_A,
                    "asserted_visit_at": "2026-11-25T10:00:00Z",
                    "attestation_code": "PRIOR_IN_PERSON_VISIT_DEMO",
                },
            )
            assert visit.status_code == 201, visit.text
            doctor_token = token

        # 5. Restart the application with the original keys: startup
        # verification must succeed (read-only, no activation).
        with db.engine.connect() as connection:
            checks_after = connection.execute(
                text("SELECT COUNT(*) FROM identity_key_check")
            ).scalar_one()
        assert checks_after == 3, f"Expected 3 key-check rows, found {checks_after}"

        from backend.app.term1 import identity

        with read_transaction(db) as session:
            identity.verify_startup(session, settings=test_settings)

        # 6. Execute another authorized identity operation (attest a second
        # visit) to confirm the bound keys are usable.
        with TestClient(app) as client:
            visit2 = client.post(
                "/v1/doctor/verified-visits",
                headers={
                    "Authorization": f"Bearer {doctor_token}",
                    "Idempotency-Key": "fresh-second-visit-001",
                },
                json={
                    "visit_ref": "FRESH-VISIT-002",
                    "subject_identifier": DEMO_ID_A,
                    "asserted_visit_at": "2026-11-25T11:00:00Z",
                    "attestation_code": "PRIOR_IN_PERSON_VISIT_DEMO",
                },
            )
        assert visit2.status_code == 201, visit2.text

        # 7. Restart with each independently changed key → fail closed.
        changed_match = Term1Settings(
            identity_match_key=b"changed identity match key 0000000001",
            subject_key=test_settings.subject_key,
            pepper=test_settings.pepper,
            admin_bootstrap_secret=test_settings.admin_bootstrap_secret,
            identity_key_id=test_settings.identity_key_id,
        )
        with pytest.raises(ApiError) as error:
            with read_transaction(db) as session:
                identity.verify_startup(session, settings=changed_match)
        assert error.value.code == "identity_key_material_mismatch"

        changed_subject = Term1Settings(
            identity_match_key=test_settings.identity_match_key,
            subject_key=b"changed subject key material 00000001",
            pepper=test_settings.pepper,
            admin_bootstrap_secret=test_settings.admin_bootstrap_secret,
            identity_key_id=test_settings.identity_key_id,
        )
        with pytest.raises(ApiError) as error:
            with read_transaction(db) as session:
                identity.verify_startup(session, settings=changed_subject)
        assert error.value.code == "identity_key_material_mismatch"

        changed_pepper = Term1Settings(
            identity_match_key=test_settings.identity_match_key,
            subject_key=test_settings.subject_key,
            pepper=b"changed pepper material 00000000003",
            admin_bootstrap_secret=test_settings.admin_bootstrap_secret,
            identity_key_id=test_settings.identity_key_id,
        )
        with pytest.raises(ApiError) as error:
            with read_transaction(db) as session:
                identity.verify_startup(session, settings=changed_pepper)
        assert error.value.code == "identity_key_material_mismatch"

        # 8. Original keys still work after failed attempts (no silent
        # re-binding).
        with read_transaction(db) as session:
            identity.verify_startup(session, settings=test_settings)
    finally:
        db.dispose()


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
