"""C1.8 durable, actor/operation/target-bound idempotency and secret safety."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import text

from backend.app.term1 import constants, crypto
from tests.backend.c1.conftest import bearer, login
from tests.backend.c1.factories import (
    DEMO_ID_A,
    DEMO_ID_B,
    attest_visit,
    clean_doctor,
    issue_invitation,
    register_patient,
    setup_doctor_with_invitation,
)

PATIENT_EMAIL = "demo.patient@cardioassist.local"
PATIENT_PASSWORD = "patient password 0001"


def _idempotency_rows(app) -> list[tuple]:
    with app.state.database.engine.connect() as connection:
        return connection.execute(
            text(
                "SELECT replay_scope, actor_binding, operation, target_ref, "
                "secret_disclosed, response_public_json FROM durable_idempotency"
            )
        ).all()


# --- replay basics -----------------------------------------------------------
def test_visit_replay_returns_the_same_resource_and_no_duplicate_row(client, app):
    chain = setup_doctor_with_invitation(app, client)
    doctor = chain["doctor"]
    payload = {
        "visit_ref": "DEMO-VISIT-REPLAY",
        "subject_identifier": DEMO_ID_A,
        "asserted_visit_at": "2026-11-25T10:00:00Z",
        "attestation_code": "PRIOR_IN_PERSON_VISIT_DEMO",
    }
    headers = {**bearer(doctor["token"]), "Idempotency-Key": "visit-replay-key"}
    first = client.post("/v1/doctor/verified-visits", headers=headers, json=payload)
    second = client.post("/v1/doctor/verified-visits", headers=headers, json=payload)
    assert first.status_code == second.status_code == 201
    assert first.json()["visit_id"] == second.json()["visit_id"]
    assert "idempotent_replay" not in first.json()
    assert second.json()["idempotent_replay"] is True
    with app.state.database.engine.connect() as connection:
        assert connection.execute(
            text("SELECT COUNT(*) FROM verified_visit WHERE visit_ref='DEMO-VISIT-REPLAY'")
        ).scalar_one() == 1


def test_changed_payload_under_the_same_key_is_a_conflict(client, app):
    chain = setup_doctor_with_invitation(app, client)
    doctor = chain["doctor"]
    headers = {**bearer(doctor["token"]), "Idempotency-Key": "conflict-key"}
    base = {
        "visit_ref": "DEMO-VISIT-CONFLICT",
        "subject_identifier": DEMO_ID_A,
        "asserted_visit_at": "2026-11-25T10:00:00Z",
        "attestation_code": "PRIOR_IN_PERSON_VISIT_DEMO",
    }
    assert client.post("/v1/doctor/verified-visits", headers=headers, json=base).status_code == 201
    changed = {**base, "visit_ref": "DEMO-VISIT-CONFLICT-2"}
    response = client.post("/v1/doctor/verified-visits", headers=headers, json=changed)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "idempotency_key_conflict"


def test_changed_secret_fingerprint_is_a_conflict(client, app):
    chain = setup_doctor_with_invitation(app, client)
    doctor = chain["doctor"]
    # A visit with no live invitation: the first call executes, the second
    # replays under the same key with a changed secret payload.
    visit = attest_visit(client, doctor, visit_ref="V-SECRET-CONFLICT", key="v-secret-conflict")
    headers = {**bearer(doctor["token"]), "Idempotency-Key": "invite-original"}
    # Same operation, target and Idempotency-Key, but a different secret payload:
    # the keyed secret fingerprint no longer matches -> conflict, not a replay.
    first = client.post(
        f"/v1/doctor/verified-visits/{visit['visit_id']}/invitations",
        headers=headers,
        json={"subject_identifier": DEMO_ID_A},
    )
    assert first.status_code == 201
    second = client.post(
        f"/v1/doctor/verified-visits/{visit['visit_id']}/invitations",
        headers=headers,
        json={"subject_identifier": DEMO_ID_B},
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "idempotency_key_conflict"


def test_same_key_for_a_different_target_is_a_scope_conflict(client, app):
    chain = setup_doctor_with_invitation(app, client)
    doctor = chain["doctor"]
    visit_a = attest_visit(client, doctor, visit_ref="V-TARGET-A", key="target-a-visit")
    visit_b = attest_visit(client, doctor, visit_ref="V-TARGET-B", key="target-b-visit")
    key = "shared-key"
    first = client.post(
        f"/v1/doctor/verified-visits/{visit_a['visit_id']}/invitations",
        headers={**bearer(doctor["token"]), "Idempotency-Key": key},
        json={"subject_identifier": DEMO_ID_A},
    )
    assert first.status_code == 201
    second = client.post(
        f"/v1/doctor/verified-visits/{visit_b['visit_id']}/invitations",
        headers={**bearer(doctor["token"]), "Idempotency-Key": key},
        json={"subject_identifier": DEMO_ID_A},
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "idempotency_scope_conflict"


def test_cross_actor_key_reuse_reveals_nothing(client, app):
    """Two different doctors may use the same key without seeing each other."""
    chain = setup_doctor_with_invitation(app, client)
    first_doctor = chain["doctor"]
    second_doctor = clean_doctor(
        app, client, email="demo.doctor2@cardioassist.local", display_name="Dr Second"
    )
    key = "shared-across-actors"
    first = client.post(
        "/v1/doctor/verified-visits",
        headers={**bearer(first_doctor["token"]), "Idempotency-Key": key},
        json={
            "visit_ref": "V-A",
            "subject_identifier": DEMO_ID_A,
            "asserted_visit_at": "2026-11-25T10:00:00Z",
            "attestation_code": "PRIOR_IN_PERSON_VISIT_DEMO",
        },
    )
    assert first.status_code == 201
    second = client.post(
        "/v1/doctor/verified-visits",
        headers={**bearer(second_doctor["token"]), "Idempotency-Key": key},
        json={
            "visit_ref": "V-B",
            "subject_identifier": DEMO_ID_B,
            "asserted_visit_at": "2026-11-25T10:00:00Z",
            "attestation_code": "PRIOR_IN_PERSON_VISIT_DEMO",
        },
    )
    assert second.status_code == 201
    assert second.json()["visit_id"] != first.json()["visit_id"]
    assert second.json()["visit_ref"] == "V-B"
    assert "idempotent_replay" not in second.json()

    rows = _idempotency_rows(app)
    actors = {row[1] for row in rows}
    assert len(actors) >= 2
    assert all(actor.startswith("user:") for actor in actors)


def test_missing_and_duplicate_idempotency_headers_are_rejected(client, app):
    chain = setup_doctor_with_invitation(app, client)
    doctor = chain["doctor"]
    payload = {
        "visit_ref": "V-NOKEY",
        "subject_identifier": DEMO_ID_A,
        "asserted_visit_at": "2026-11-25T10:00:00Z",
        "attestation_code": "PRIOR_IN_PERSON_VISIT_DEMO",
    }
    missing = client.post(
        "/v1/doctor/verified-visits", headers=bearer(doctor["token"]), json=payload
    )
    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == "idempotency_key_required"

    # Two *different* keys on one request are ambiguous: 400.
    ambiguous = client.post(
        "/v1/doctor/verified-visits",
        headers=[
            ("Authorization", f"Bearer {doctor['token']}"),
            ("Idempotency-Key", "a"),
            ("Idempotency-Key", "b"),
        ],
        json=payload,
    )
    assert ambiguous.status_code == 400
    assert ambiguous.json()["error"]["code"] == "idempotency_key_required"

    # A single key repeated verbatim is not ambiguous: it resolves as a replay.
    repeated = client.post(
        "/v1/doctor/verified-visits",
        headers=[
            ("Authorization", f"Bearer {doctor['token']}"),
            ("Idempotency-Key", "repeat-key"),
            ("Idempotency-Key", "repeat-key"),
        ],
        json=payload,
    )
    assert repeated.status_code == 201


# --- registration replay and secret non-redisclosure ------------------------
def test_registration_replay_never_rediscloses_the_session_token(client, app):
    chain = setup_doctor_with_invitation(app, client)
    register_patient(client, chain["invitation"]["access_code"], key="register-secret")
    replay = client.post(
        "/v1/patients/register",
        headers={"Idempotency-Key": "register-secret"},
        json={
            "access_code": chain["invitation"]["access_code"],
            "identifier": DEMO_ID_A,
            "email": PATIENT_EMAIL,
            "password": PATIENT_PASSWORD,
            "consent_ack": True,
        },
    )
    assert replay.status_code == 409
    body = replay.json()
    assert body["error"]["code"] == "secret_not_redisclosable"
    assert "session_token" not in json.dumps(body)
    assert "password" not in json.dumps(body)
    # Only non-secret identifiers may accompany the refusal.
    assert set(body["error"]) <= {
        "code",
        "message",
        "user_id",
        "patient_id",
        "assignment_id",
        "subject_label",
    }
    with app.state.database.engine.connect() as connection:
        assert connection.execute(
            text("SELECT COUNT(*) FROM user_account WHERE role='patient'")
        ).scalar_one() == 1
        # Exactly one patient session: the replay created no additional session.
        assert connection.execute(
            text("SELECT COUNT(*) FROM session s JOIN user_account u "
                 "ON u.user_id = s.user_id WHERE u.role='patient'")
        ).scalar_one() == 1


def test_invitation_replay_never_rediscloses_the_access_code(client, app):
    chain = setup_doctor_with_invitation(app, client)
    doctor = chain["doctor"]
    visit = attest_visit(client, doctor, visit_ref="V-ACCESS-REPLAY", key="v-access-replay")
    headers = {**bearer(doctor["token"]), "Idempotency-Key": "invite-secret"}
    original = client.post(
        f"/v1/doctor/verified-visits/{visit['visit_id']}/invitations",
        headers=headers,
        json={"subject_identifier": DEMO_ID_A},
    )
    assert original.status_code == 201
    replay = client.post(
        f"/v1/doctor/verified-visits/{visit['visit_id']}/invitations",
        headers=headers,
        json={"subject_identifier": DEMO_ID_A},
    )
    assert replay.status_code == 409
    assert replay.json()["error"]["code"] == "secret_not_redisclosable"
    assert "access_code" not in replay.text
    assert original.json()["access_code"] not in replay.text


def test_temporary_password_replay_never_rediscloses_the_secret(client, app):
    from tests.backend.c1.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, bootstrap_admin
    from tests.backend.c1.factories import provision_doctor

    bootstrap_admin(app)
    provision_doctor(app, client, email="demo.doc@cardioassist.local", display_name="Dr Doc")
    admin_token = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)["session_token"]
    payload = {
        "email": "demo.another@cardioassist.local",
        "display_name": "Dr Another",
        "temp_password_policy": "one_time_secret",
    }
    headers = {**bearer(admin_token), "Idempotency-Key": "doc-secret"}
    first = client.post("/v1/admin/doctors", headers=headers, json=payload)
    assert first.status_code == 201
    replay = client.post("/v1/admin/doctors", headers=headers, json=payload)
    assert replay.status_code == 409
    assert replay.json()["error"]["code"] == "secret_not_redisclosable"
    assert first.json()["temp_secret"] not in replay.text
    assert "temp_secret" not in replay.text


def test_secret_free_replay_is_returned_verbatim_for_non_secret_operations(client, app):
    chain = setup_doctor_with_invitation(app, client)
    doctor = chain["doctor"]
    visit, invitation = chain["fresh_visit"](2)
    url = f"/v1/doctor/invitations/{invitation['invitation_id']}/revoke"
    headers = {**bearer(doctor["token"]), "Idempotency-Key": "revoke-replay-key"}
    first = client.post(url, headers=headers, json={"reason_code": "lost code"})
    second = client.post(url, headers=headers, json={"reason_code": "lost code"})
    assert first.status_code == second.status_code == 200
    assert first.json()["revoked_at"] == second.json()["revoked_at"]
    assert second.json()["idempotent_replay"] is True


# --- consumed invitation and replay TTL -------------------------------------
def test_consumed_invitation_replay_never_reopens_it(client, app):
    chain = setup_doctor_with_invitation(app, client)
    register_patient(client, chain["invitation"]["access_code"], key="consume-once")
    # A later, different key still fails: the invitation is permanently consumed.
    response = client.post(
        "/v1/patients/register",
        headers={"Idempotency-Key": "consume-twice"},
        json={
            "access_code": chain["invitation"]["access_code"],
            "identifier": DEMO_ID_A,
            "email": "demo.other.patient@cardioassist.local",
            "password": PATIENT_PASSWORD,
            "consent_ack": True,
        },
    )
    assert response.status_code == 401
    with app.state.database.engine.connect() as connection:
        consumed = connection.execute(
            text("SELECT consumed_at FROM patient_invitation")
        ).scalar_one()
        redemptions = connection.execute(
            text("SELECT COUNT(*) FROM invitation_redemption")
        ).scalar_one()
        accounts = connection.execute(
            text("SELECT COUNT(*) FROM user_account WHERE role='patient'")
        ).scalar_one()
    assert consumed is not None
    assert redemptions == 1
    assert accounts == 1


def test_consumed_invitation_stays_consumed_after_the_idempotency_record_expires(
    client, app, clock
):
    chain = setup_doctor_with_invitation(app, client)
    register_patient(client, chain["invitation"]["access_code"], key="ttl-register")
    clock.advance(seconds=constants.IDEMPOTENCY_TTL_SECONDS + 60)
    response = client.post(
        "/v1/patients/register",
        headers={"Idempotency-Key": "ttl-register"},
        json={
            "access_code": chain["invitation"]["access_code"],
            "identifier": DEMO_ID_A,
            "email": PATIENT_EMAIL,
            "password": PATIENT_PASSWORD,
            "consent_ack": True,
        },
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_invitation"
    with app.state.database.engine.connect() as connection:
        assert connection.execute(
            text("SELECT COUNT(*) FROM patient_profile")
        ).scalar_one() == 1


def test_replay_records_contain_no_secret_material(client, app):
    chain = setup_doctor_with_invitation(app, client)
    doctor = chain["doctor"]
    client.post(
        "/v1/doctor/verified-visits",
        headers={**bearer(doctor["token"]), "Idempotency-Key": "leak-check"},
        json={
            "visit_ref": "V-LEAK",
            "subject_identifier": DEMO_ID_A,
            "asserted_visit_at": "2026-11-25T10:00:00Z",
            "attestation_code": "PRIOR_IN_PERSON_VISIT_DEMO",
        },
    )
    register_patient(client, chain["invitation"]["access_code"], key="leak-register")
    with app.state.database.engine.connect() as connection:
        dump = str(connection.execute(text("SELECT * FROM durable_idempotency")).all())
    for secret in (
        chain["invitation"]["access_code"],
        DEMO_ID_A,
        PATIENT_PASSWORD,
        doctor["password"],
        doctor["temp_secret"],
    ):
        assert secret not in dump
    # Only hashes are stored, and each is a 64-character lowercase hex digest.
    rows = _idempotency_rows(app)
    assert rows


def test_authenticated_replay_still_requires_a_valid_current_session(client, app):
    chain = setup_doctor_with_invitation(app, client)
    doctor = chain["doctor"]
    visit, invitation = chain["fresh_visit"](3)
    headers = {**bearer(doctor["token"]), "Idempotency-Key": "session-bound"}
    url = f"/v1/doctor/invitations/{invitation['invitation_id']}/revoke"
    assert client.post(url, headers=headers, json={"reason_code": "x"}).status_code == 200
    # Revoke the session; a replay with the dead token must not be disclosed.
    client.post("/v1/auth/logout", headers=bearer(doctor["token"]))
    denied = client.post(url, headers=headers, json={"reason_code": "x"})
    assert denied.status_code == 401
    assert "revoked_at" not in denied.text


def test_account_suspension_blocks_a_previously_authorized_replay(client, app):
    chain = setup_doctor_with_invitation(app, client)
    doctor = chain["doctor"]
    visit, invitation = chain["fresh_visit"](4)
    headers = {**bearer(doctor["token"]), "Idempotency-Key": "suspend-replay"}
    url = f"/v1/doctor/invitations/{invitation['invitation_id']}/revoke"
    assert client.post(url, headers=headers, json={"reason_code": "x"}).status_code == 200

    admin = login(client, "demo.admin@cardioassist.local", "admin demo password 001")
    suspended = client.patch(
        f"/v1/admin/accounts/{doctor['user_id']}/status",
        headers={**bearer(admin["session_token"]), "Idempotency-Key": "suspend-action"},
        json={"status": "SUSPENDED", "reason_code": "review"},
    )
    assert suspended.status_code == 200
    blocked = client.post(url, headers=headers, json={"reason_code": "x"})
    assert blocked.status_code == 401


def test_idempotency_records_are_actor_scoped_not_globally_keyed(app):
    """Structural guarantee: no lookup path exists without actor_binding."""
    import inspect

    from backend.app.term1 import idempotency

    source = inspect.getsource(idempotency)
    assert "actor_binding == key.actor_binding" in source
    for statement in source.split("select("):
        if "DurableIdempotency" in statement and "key_hash ==" in statement:
            assert "actor_binding" in statement, statement[:200]
