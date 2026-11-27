"""C1.6/C1.7 atomic registration, linking, assignments and consent."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from backend.app.term1 import constants, crypto
from tests.backend.c1.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, bearer, login
from tests.backend.c1.factories import (
    DEMO_ID_A,
    DEMO_ID_B,
    attest_visit,
    issue_invitation,
    clean_doctor,
    provision_doctor,
    register_patient,
    setup_doctor_with_invitation,
)

PATIENT_EMAIL = "demo.patient@cardioassist.local"
PATIENT_PASSWORD = "patient password 0001"


# --- registration ------------------------------------------------------------
def test_registration_creates_the_complete_atomic_effect(client, app):
    chain = setup_doctor_with_invitation(app, client)
    result = register_patient(
        client, chain["invitation"]["access_code"], email=PATIENT_EMAIL, password=PATIENT_PASSWORD
    )
    assert set(result) >= {
        "user_id",
        "patient_id",
        "assignment_id",
        "session_id",
        "session_token",
        "subject_label",
    }
    with app.state.database.engine.connect() as connection:
        counts = {
            table: connection.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
            for table in (
                "user_account",
                "patient_identity",
                "patient_profile",
                "doctor_patient_assignment",
                "consent_record",
                "invitation_redemption",
                "durable_idempotency",
            )
        }
        consumed = connection.execute(
            text("SELECT consumed_at FROM patient_invitation")
        ).scalar_one()
        audit_types = {
            row[0]
            for row in connection.execute(text("SELECT event_type FROM workflow_audit_event")).all()
        }
    assert counts["user_account"] == 3  # admin + doctor + patient
    assert all(
        counts[table] == 1
        for table in (
            "patient_identity",
            "patient_profile",
            "doctor_patient_assignment",
            "consent_record",
            "invitation_redemption",
        )
    )
    assert consumed is not None
    assert {
        "PATIENT_REGISTERED",
        "INVITATION_CONSUMED",
        "ACCOUNT_PROVISIONED",
        "VISIT_ATTESTED",
        "INVITATION_ISSUED",
        "ADMIN_BOOTSTRAPPED",
    } <= audit_types


def test_registration_returns_a_session_for_the_new_patient(client, app):
    chain = setup_doctor_with_invitation(app, client)
    result = register_patient(client, chain["invitation"]["access_code"], password=PATIENT_PASSWORD)
    me = client.get("/v1/auth/me", headers=bearer(result["session_token"]))
    assert me.status_code == 200
    assert me.json()["role"] == "patient"
    assert me.json()["profile_id"] == result["patient_id"]


@pytest.mark.parametrize(
    "identifier",
    ["DEMO-ID-002", "DEMO-ID-777"],
)
def test_invitation_for_patient_a_cannot_register_patient_b(client, app, identifier):
    chain = setup_doctor_with_invitation(app, client)
    response = client.post(
        "/v1/patients/register",
        headers={"Idempotency-Key": f"wrong-subject-{identifier}"},
        json={
            "access_code": chain["invitation"]["access_code"],
            "identifier": identifier,
            "email": PATIENT_EMAIL,
            "password": PATIENT_PASSWORD,
            "consent_ack": True,
        },
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_invitation"
    with app.state.database.engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM patient_identity")).scalar_one() == 0
        assert connection.execute(text("SELECT COUNT(*) FROM user_account")).scalar_one() == 2


def test_wrong_code_is_generic_and_counts_a_durable_attempt(client, app):
    chain = setup_doctor_with_invitation(app, client)
    bogus = crypto.new_invitation_code()
    response = client.post(
        "/v1/patients/register",
        headers={"Idempotency-Key": "wrong-code-1"},
        json={
            "access_code": bogus,
            "identifier": DEMO_ID_A,
            "email": PATIENT_EMAIL,
            "password": PATIENT_PASSWORD,
            "consent_ack": True,
        },
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_invitation"
    with app.state.database.engine.connect() as connection:
        attempts = connection.execute(
            text("SELECT outcome_code, invitation_id FROM invitation_attempt")
        ).all()
        unknown_audits = connection.execute(
            text(
                "SELECT COUNT(*) FROM workflow_audit_event "
                "WHERE subject_type='unknown_invitation' AND subject_id IS NULL"
            )
        ).scalar_one()
        dump = str(connection.execute(text("SELECT * FROM invitation_attempt")).all())
    assert attempts and attempts[-1][1] is None
    assert unknown_audits == 1
    # The raw code is never persisted.
    assert bogus not in dump


def test_consumed_invitation_cannot_be_reused_by_a_second_patient(client, app):
    chain = setup_doctor_with_invitation(app, client)
    first = register_patient(client, chain["invitation"]["access_code"], key="first-patient")
    second = client.post(
        "/v1/patients/register",
        headers={"Idempotency-Key": "second-patient"},
        json={
            "access_code": chain["invitation"]["access_code"],
            "identifier": DEMO_ID_A,
            "email": "demo.patient2@cardioassist.local",
            "password": PATIENT_PASSWORD,
            "consent_ack": True,
        },
    )
    assert second.status_code == 401
    with app.state.database.engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM patient_profile")).scalar_one() == 1
        assert connection.execute(text("SELECT COUNT(*) FROM user_account WHERE role='patient'")).scalar_one() == 1
    assert first["patient_id"]


def test_second_registration_for_the_same_identity_is_refused(client, app):
    chain = setup_doctor_with_invitation(app, client)
    register_patient(client, chain["invitation"]["access_code"], key="reg-1")
    # A second visit/invitation for the same fictitious identity.
    visit2 = attest_visit(client, chain["doctor"], visit_ref="DEMO-VISIT-002", key="v-2")
    invitation2 = issue_invitation(client, chain["doctor"], visit2["visit_id"], key="i-2")
    response = client.post(
        "/v1/patients/register",
        headers={"Idempotency-Key": "reg-2"},
        json={
            "access_code": invitation2["access_code"],
            "identifier": DEMO_ID_A,
            "email": "demo.patient.dup@cardioassist.local",
            "password": PATIENT_PASSWORD,
            "consent_ack": True,
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "subject_identity_conflict"
    with app.state.database.engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM patient_identity")).scalar_one() == 1
        assert connection.execute(
            text("SELECT COUNT(*) FROM user_account WHERE role='patient'")
        ).scalar_one() == 1


def test_duplicate_email_registration_is_generic(client, app):
    chain = setup_doctor_with_invitation(app, client)
    register_patient(client, chain["invitation"]["access_code"], key="reg-1")
    # The email conflict is checked before the identity conflict: a fresh
    # fictitious identity reusing the canonical (upper-cased) email.
    visit2 = attest_visit(client, chain["doctor"], visit_ref="DEMO-VISIT-002", key="v-2")
    invitation2 = issue_invitation(client, chain["doctor"], visit2["visit_id"], key="i-2")
    response = client.post(
        "/v1/patients/register",
        headers={"Idempotency-Key": "reg-dup-email"},
        json={
            "access_code": invitation2["access_code"],
            "identifier": DEMO_ID_A,
            "email": PATIENT_EMAIL.upper(),
            "password": PATIENT_PASSWORD,
            "consent_ack": True,
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "account_registration_unavailable"


def test_registration_requires_consent_and_a_synthetic_email(client, app):
    chain = setup_doctor_with_invitation(app, client)
    no_consent = client.post(
        "/v1/patients/register",
        headers={"Idempotency-Key": "no-consent"},
        json={
            "access_code": chain["invitation"]["access_code"],
            "identifier": DEMO_ID_A,
            "email": PATIENT_EMAIL,
            "password": PATIENT_PASSWORD,
            "consent_ack": False,
        },
    )
    assert no_consent.status_code == 422
    real_domain = client.post(
        "/v1/patients/register",
        headers={"Idempotency-Key": "real-domain"},
        json={
            "access_code": chain["invitation"]["access_code"],
            "identifier": DEMO_ID_A,
            "email": "someone@example.com",
            "password": PATIENT_PASSWORD,
            "consent_ack": True,
        },
    )
    assert real_domain.status_code == 422
    with app.state.database.engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM patient_profile")).scalar_one() == 0


def test_registration_rolls_back_completely_on_a_mid_transaction_failure(client, app, monkeypatch):
    """A failure after the flush must leave no orphan account/identity/profile."""
    from backend.app.term1 import enrollment

    chain = setup_doctor_with_invitation(app, client)

    original = enrollment._consume_invitation

    def explode(*args, **kwargs):
        raise RuntimeError("simulated persistence failure after flush")

    monkeypatch.setattr(enrollment, "_consume_invitation", explode)
    with pytest.raises(RuntimeError):
        client.post(
            "/v1/patients/register",
            headers={"Idempotency-Key": "explode"},
            json={
                "access_code": chain["invitation"]["access_code"],
                "identifier": DEMO_ID_A,
                "email": PATIENT_EMAIL,
                "password": PATIENT_PASSWORD,
                "consent_ack": True,
            },
        )
    with app.state.database.engine.connect() as connection:
        for table in (
            "user_account",
            "patient_identity",
            "patient_profile",
            "doctor_patient_assignment",
            "consent_record",
            "invitation_redemption",
        ):
            expected = 2 if table == "user_account" else 0
            assert connection.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one() == expected, table
        assert connection.execute(
            text("SELECT COUNT(*) FROM patient_invitation WHERE consumed_at IS NOT NULL")
        ).scalar_one() == 0


# --- linking -----------------------------------------------------------------
def test_existing_patient_links_a_second_doctor_without_a_new_account(client, app):
    chain = setup_doctor_with_invitation(app, client)
    registration = register_patient(client, chain["invitation"]["access_code"], password=PATIENT_PASSWORD)
    second = clean_doctor(
        app, client, email="demo.doctor2@cardioassist.local", display_name="Dr Second"
    )
    # Each doctor provisioning run opens its own admin/doctor sessions; the
    # patient simply authenticates again rather than borrowing a stale token.
    patient_token = login(client, PATIENT_EMAIL, PATIENT_PASSWORD)["session_token"]
    visit = attest_visit(client, second, visit_ref="DEMO-VISIT-SECOND", key="v-second")
    invitation = issue_invitation(client, second, visit["visit_id"], key="i-second")

    linked = client.post(
        "/v1/patients/link",
        headers={**bearer(patient_token), "Idempotency-Key": "link-1"},
        json={
            "access_code": invitation["access_code"],
            "identifier": DEMO_ID_A,
            "accept_linking": True,
        },
    )
    assert linked.status_code == 200, linked.text
    body = linked.json()
    assert body["assignment_id"] != registration["assignment_id"]
    assert body["doctor_label"] == "Dr Second"

    with app.state.database.engine.connect() as connection:
        assert connection.execute(
            text("SELECT COUNT(*) FROM user_account WHERE role='patient'")
        ).scalar_one() == 1
        # admin + first doctor + second doctor + the single patient account.
        assert connection.execute(text("SELECT COUNT(*) FROM user_account")).scalar_one() == 4
        assert connection.execute(
            text("SELECT COUNT(*) FROM user_account WHERE role='doctor'")
        ).scalar_one() == 2
        assert connection.execute(text("SELECT COUNT(*) FROM patient_profile")).scalar_one() == 1
        assert connection.execute(text("SELECT COUNT(*) FROM patient_identity")).scalar_one() == 1
        assert connection.execute(
            text("SELECT COUNT(*) FROM doctor_patient_assignment WHERE revoked_at IS NULL")
        ).scalar_one() == 2
        # Consent is not recreated by a second-doctor link.
        assert connection.execute(text("SELECT COUNT(*) FROM consent_record")).scalar_one() == 1
        flows = {
            row[0]
            for row in connection.execute(text("SELECT flow FROM invitation_redemption")).all()
        }
    assert flows == {"register", "link"}

    assignments = client.get("/v1/me/assignments", headers=bearer(patient_token)).json()
    assert len(assignments["assignments"]) == 2
    assert all(row["active"] for row in assignments["assignments"])


def test_link_with_a_foreign_identity_is_refused(client, app):
    chain = setup_doctor_with_invitation(app, client)
    registration = register_patient(client, chain["invitation"]["access_code"], password=PATIENT_PASSWORD)
    second = clean_doctor(
        app, client, email="demo.doctor2@cardioassist.local", display_name="Dr Second"
    )
    visit = attest_visit(client, second, visit_ref="V-OTHER", identifier=DEMO_ID_B, key="v-other")
    invitation = issue_invitation(
        client, second, visit["visit_id"], identifier=DEMO_ID_B, key="i-other"
    )
    response = client.post(
        "/v1/patients/link",
        headers={**bearer(registration["session_token"]), "Idempotency-Key": "link-wrong"},
        json={
            "access_code": invitation["access_code"],
            "identifier": DEMO_ID_A,
            "accept_linking": True,
        },
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_invitation"


def test_link_requires_patient_role_and_explicit_acceptance(client, app):
    chain = setup_doctor_with_invitation(app, client)
    register_patient(client, chain["invitation"]["access_code"], password=PATIENT_PASSWORD)
    second = clean_doctor(
        app, client, email="demo.doctor2@cardioassist.local", display_name="Dr Second"
    )
    visit = attest_visit(client, second, visit_ref="V-SECOND", key="v-second")
    invitation = issue_invitation(client, second, visit["visit_id"], key="i-second")

    doctor_response = client.post(
        "/v1/patients/link",
        headers={**bearer(second["token"]), "Idempotency-Key": "link-doctor"},
        json={
            "access_code": invitation["access_code"],
            "identifier": DEMO_ID_A,
            "accept_linking": True,
        },
    )
    assert doctor_response.status_code == 403

    patient_token = login(client, PATIENT_EMAIL, PATIENT_PASSWORD)["session_token"]
    declined = client.post(
        "/v1/patients/link",
        headers={**bearer(patient_token), "Idempotency-Key": "link-declined"},
        json={
            "access_code": invitation["access_code"],
            "identifier": DEMO_ID_A,
            "accept_linking": False,
        },
    )
    assert declined.status_code == 422


# --- assignments and consent -------------------------------------------------
def test_patient_revokes_one_assignment_and_keeps_the_other(client, app):
    chain = setup_doctor_with_invitation(app, client)
    registration = register_patient(client, chain["invitation"]["access_code"], password=PATIENT_PASSWORD)
    patient_token = registration["session_token"]
    second = clean_doctor(
        app, client, email="demo.doctor2@cardioassist.local", display_name="Dr Second"
    )
    visit = attest_visit(client, second, visit_ref="V-SECOND", key="v-second")
    invitation = issue_invitation(client, second, visit["visit_id"], key="i-second")
    linked = client.post(
        "/v1/patients/link",
        headers={**bearer(patient_token), "Idempotency-Key": "link-1"},
        json={"access_code": invitation["access_code"], "identifier": DEMO_ID_A, "accept_linking": True},
    ).json()

    revoked = client.post(
        f"/v1/me/assignments/{linked['assignment_id']}/revoke",
        headers={**bearer(patient_token), "Idempotency-Key": "revoke-e5"},
        json={"reason_code": "patient choice"},
    )
    assert revoked.status_code == 200 and revoked.json()["revoked_at"]

    assignments = client.get("/v1/me/assignments", headers=bearer(patient_token)).json()["assignments"]
    by_id = {row["assignment_id"]: row for row in assignments}
    assert by_id[linked["assignment_id"]]["active"] is False
    assert by_id[registration["assignment_id"]]["active"] is True

    # Consent is untouched by an assignment revocation.
    with app.state.database.engine.connect() as connection:
        assert connection.execute(
            text("SELECT COUNT(*) FROM consent_record WHERE revoked_at IS NULL")
        ).scalar_one() == 1


def test_doctor_revokes_an_assignment_it_owns(client, app):
    chain = setup_doctor_with_invitation(app, client)
    registration = register_patient(client, chain["invitation"]["access_code"], password=PATIENT_PASSWORD)
    response = client.post(
        f"/v1/doctor/assignments/{registration['assignment_id']}/revoke",
        headers={**bearer(chain["doctor"]["token"]), "Idempotency-Key": "doctor-revoke"},
        json={"reason_code": "care transferred"},
    )
    assert response.status_code == 200
    with app.state.database.engine.connect() as connection:
        row = connection.execute(
            text("SELECT revoked_by_role, reason_code FROM doctor_patient_assignment")
        ).one()
    assert row == ("doctor", "care transferred")


def test_doctor_cannot_revoke_another_doctors_assignment(client, app):
    chain = setup_doctor_with_invitation(app, client)
    registration = register_patient(client, chain["invitation"]["access_code"], password=PATIENT_PASSWORD)
    intruder = clean_doctor(
        app, client, email="demo.intruder@cardioassist.local", display_name="Dr Intruder"
    )
    response = client.post(
        f"/v1/doctor/assignments/{registration['assignment_id']}/revoke",
        headers={**bearer(intruder["token"]), "Idempotency-Key": "intrude"},
        json={"reason_code": "hostile"},
    )
    assert response.status_code == 404


def test_patient_cannot_revoke_another_patients_assignment(client, app):
    chain = setup_doctor_with_invitation(app, client)
    first = register_patient(client, chain["invitation"]["access_code"], password=PATIENT_PASSWORD)
    visit2 = attest_visit(client, chain["doctor"], visit_ref="V-2", identifier=DEMO_ID_B, key="v-2")
    invitation2 = issue_invitation(client, chain["doctor"], visit2["visit_id"], identifier=DEMO_ID_B, key="i-2")
    second = register_patient(
        client,
        invitation2["access_code"],
        identifier=DEMO_ID_B,
        email="demo.patient2@cardioassist.local",
        key="reg-2",
    )
    response = client.post(
        f"/v1/me/assignments/{second['assignment_id']}/revoke",
        headers={**bearer(first["session_token"]), "Idempotency-Key": "cross-patient"},
        json={"reason_code": "hostile"},
    )
    assert response.status_code == 404


def test_consent_withdrawal_is_patient_wide_and_distinct(client, app):
    chain = setup_doctor_with_invitation(app, client)
    registration = register_patient(client, chain["invitation"]["access_code"], password=PATIENT_PASSWORD)
    patient_token = registration["session_token"]
    response = client.post(
        "/v1/me/consent/synthetic-demo/revoke",
        headers={**bearer(patient_token), "Idempotency-Key": "consent-revoke"},
        json={"reason_code": "withdraw demo consent"},
    )
    assert response.status_code == 200 and response.json()["revoked_at"]
    with app.state.database.engine.connect() as connection:
        consent = connection.execute(
            text("SELECT revoked_at, kind, scope FROM consent_record")
        ).one()
        assignment = connection.execute(
            text("SELECT revoked_at FROM doctor_patient_assignment")
        ).one()
        audit = connection.execute(
            text("SELECT event_type FROM workflow_audit_event WHERE event_type='CONSENT_REVOKED'")
        ).scalar_one()
    assert consent[0] is not None
    assert consent[1] == constants.CONSENT_KIND_SYNTHETIC_DEMO
    assert consent[2] == constants.CONSENT_SCOPE_PATIENT_WIDE
    # Consent withdrawal did not revoke the assignment (distinct operations).
    assert assignment[0] is None
    assert audit == "CONSENT_REVOKED"

    # A second withdrawal finds no active consent.
    repeat = client.post(
        "/v1/me/consent/synthetic-demo/revoke",
        headers={**bearer(patient_token), "Idempotency-Key": "consent-revoke-2"},
        json={"reason_code": "again"},
    )
    assert repeat.status_code == 404
    assert repeat.json()["error"]["code"] == "consent_not_found"


def test_revoked_assignment_cannot_be_revoked_twice(client, app):
    chain = setup_doctor_with_invitation(app, client)
    registration = register_patient(client, chain["invitation"]["access_code"], password=PATIENT_PASSWORD)
    token = registration["session_token"]
    first = client.post(
        f"/v1/me/assignments/{registration['assignment_id']}/revoke",
        headers={**bearer(token), "Idempotency-Key": "r1"},
        json={"reason_code": "one"},
    )
    assert first.status_code == 200
    second = client.post(
        f"/v1/me/assignments/{registration['assignment_id']}/revoke",
        headers={**bearer(token), "Idempotency-Key": "r2"},
        json={"reason_code": "two"},
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "assignment_already_revoked"


def test_assignments_listing_is_role_and_owner_scoped(client, app):
    chain = setup_doctor_with_invitation(app, client)
    register_patient(client, chain["invitation"]["access_code"], password=PATIENT_PASSWORD)
    doctor_response = client.get(
        "/v1/me/assignments", headers=bearer(chain["doctor"]["token"])
    )
    assert doctor_response.status_code == 403
    admin_token = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)["session_token"]
    assert client.get("/v1/me/assignments", headers=bearer(admin_token)).status_code == 403
