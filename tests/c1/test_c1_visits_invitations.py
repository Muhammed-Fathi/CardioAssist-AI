"""C1.4/C1.5 verified visits, identity binding and the invitation lifecycle."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from backend.app.term1 import constants, crypto
from tests.c1.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, bootstrap_admin, login
from tests.c1.factories import (
    DEMO_ID_A,
    DEMO_ID_B,
    attest_visit,
    issue_invitation,
    provision_doctor,
    register_patient,
)


# --- identifier grammar ------------------------------------------------------
@pytest.mark.parametrize(
    "value,expected",
    [
        ("DEMO-ID-001", "DEMO-ID-001"),
        (" demo-id-001 ", "DEMO-ID-001"),
        ("DEMO-ID-9", None),
        ("DEMO-ID-999", "DEMO-ID-999"),
        ("DEMO-ID-999999", "DEMO-ID-999999"),
        ("DEMO-ID-9999999", None),
        ("DEMO-ID-0001", "DEMO-ID-0001"),
        ("30101010101010", None),  # 14-digit national-ID shape
        ("DEMO-ID-ABC", None),
        ("NF-001", None),
        ("", None),
    ],
)
def test_demo_identifier_grammar_is_closed(value, expected):
    assert crypto.normalize_demo_identifier(value) == expected


def test_real_national_id_shapes_are_rejected_by_the_visit_operation(client, app):
    bootstrap_admin(app)
    doctor = provision_doctor(
        app, client, email="demo.doc@cardioassist.local", display_name="Dr Doc"
    )
    for value in ("30101010101010", "29801011234567", "DEMO-ID-1"):
        response = client.post(
            "/v1/doctor/verified-visits",
            headers={
                "Authorization": f"Bearer {doctor['token']}",
                "Idempotency-Key": f"bad-id-{value}",
            },
            json={
                "visit_ref": f"V-{value}",
                "subject_identifier": value,
                "asserted_visit_at": "2026-11-25T10:00:00Z",
                "attestation_code": "PRIOR_IN_PERSON_VISIT_DEMO",
            },
        )
        assert response.status_code == 422, value
        assert response.json()["error"]["code"] == "invalid_demo_identifier"


# --- attestation -------------------------------------------------------------
def test_attestation_records_server_time_and_stores_no_raw_identifier(client, app):
    bootstrap_admin(app)
    doctor = provision_doctor(
        app, client, email="demo.doc@cardioassist.local", display_name="Dr Doc"
    )
    visit = attest_visit(client, doctor, visit_ref="DEMO-VISIT-001")
    assert visit["attested_at"].endswith("Z")
    assert visit["subject_label"].startswith("DEMO-SUBJECT-")
    assert DEMO_ID_A not in str(visit)

    with app.state.database.engine.connect() as connection:
        dump = "\n".join(
            str(connection.execute(text(f"SELECT * FROM {table}")).all())
            for table in (
                "verified_visit",
                "patient_invitation",
                "workflow_audit_event",
                "durable_idempotency",
            )
        )
    assert DEMO_ID_A not in dump
    assert "DEMO-ID-" not in dump.replace("DEMO-VISIT", "")


def test_attestation_requires_an_already_occurred_visit(client, app):
    bootstrap_admin(app)
    doctor = provision_doctor(
        app, client, email="demo.doc@cardioassist.local", display_name="Dr Doc"
    )
    future = client.post(
        "/v1/doctor/verified-visits",
        headers={
            "Authorization": f"Bearer {doctor['token']}",
            "Idempotency-Key": "future-visit",
        },
        json={
            "visit_ref": "V-FUTURE",
            "subject_identifier": DEMO_ID_A,
            "asserted_visit_at": "2026-12-31T10:00:00Z",
            "attestation_code": "PRIOR_IN_PERSON_VISIT_DEMO",
        },
    )
    assert future.status_code == 422
    assert future.json()["error"]["code"] == "invalid_attestation"


def test_attestation_code_vocabulary_is_closed(client, app):
    bootstrap_admin(app)
    doctor = provision_doctor(
        app, client, email="demo.doc@cardioassist.local", display_name="Dr Doc"
    )
    response = client.post(
        "/v1/doctor/verified-visits",
        headers={
            "Authorization": f"Bearer {doctor['token']}",
            "Idempotency-Key": "bad-attestation",
        },
        json={
            "visit_ref": "V-1",
            "subject_identifier": DEMO_ID_A,
            "asserted_visit_at": "2026-11-25T10:00:00Z",
            "attestation_code": "FREE_TEXT_CLINICAL_NARRATIVE",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_attestation"


def test_duplicate_visit_reference_per_doctor_is_a_conflict(client, app):
    bootstrap_admin(app)
    doctor = provision_doctor(
        app, client, email="demo.doc@cardioassist.local", display_name="Dr Doc"
    )
    attest_visit(client, doctor, visit_ref="DEMO-VISIT-001", key="dup-a")
    response = client.post(
        "/v1/doctor/verified-visits",
        headers={
            "Authorization": f"Bearer {doctor['token']}",
            "Idempotency-Key": "dup-b",
        },
        json={
            "visit_ref": "DEMO-VISIT-001",
            "subject_identifier": DEMO_ID_B,
            "asserted_visit_at": "2026-11-25T10:00:00Z",
            "attestation_code": "PRIOR_IN_PERSON_VISIT_DEMO",
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "concurrency_conflict"


# --- invitation issuance -----------------------------------------------------
def test_invitation_code_is_256_bit_and_disclosed_once(client, app):
    from tests.c1.factories import setup_doctor_with_invitation

    chain = setup_doctor_with_invitation(app, client)
    code = chain["invitation"]["access_code"]
    assert len(code) == 43  # 32 bytes base64url
    assert chain["invitation"]["status"] == "ACTIVE"
    assert chain["invitation"]["attempt_count"] == 0
    assert chain["invitation"]["max_attempts"] == constants.INVITATION_MAX_ATTEMPTS

    # Status inspection never discloses the code.
    status = client.get(
        f"/v1/doctor/invitations/{chain['invitation']['invitation_id']}",
        headers={"Authorization": f"Bearer {chain['doctor']['token']}"},
    )
    assert status.status_code == 200
    assert "access_code" not in status.json()
    assert code not in status.text

    with app.state.database.engine.connect() as connection:
        row = connection.execute(
            text("SELECT token_verifier_sha256 FROM patient_invitation")
        ).scalar_one()
    assert row == crypto.invitation_verifier(code)
    assert row != code


def test_visit_a_cannot_produce_an_invitation_for_patient_b(client, app):
    from tests.c1.factories import setup_doctor_with_invitation

    chain = setup_doctor_with_invitation(app, client)
    response = client.post(
        f"/v1/doctor/verified-visits/{chain['visit']['visit_id']}/invitations",
        headers={
            "Authorization": f"Bearer {chain['doctor']['token']}",
            "Idempotency-Key": "wrong-subject",
        },
        json={"subject_identifier": DEMO_ID_B},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_invitation"
    with app.state.database.engine.connect() as connection:
        # No second invitation was created and no identifier details leaked.
        assert connection.execute(text("SELECT COUNT(*) FROM patient_invitation")).scalar_one() == 1
        dump = str(
            connection.execute(text("SELECT * FROM workflow_audit_event")).all()
        )
    # Denial evidence is metadata only, and the raw identifier is never stored.
    assert "DEMO-ID-002" not in dump
    assert "subject_mismatch" in dump or "invalid_invitation" in dump or dump != ""


def test_only_one_live_invitation_per_visit(client, app):
    from tests.c1.factories import setup_doctor_with_invitation

    chain = setup_doctor_with_invitation(app, client)
    second = client.post(
        f"/v1/doctor/verified-visits/{chain['visit']['visit_id']}/invitations",
        headers={
            "Authorization": f"Bearer {chain['doctor']['token']}",
            "Idempotency-Key": "second-live",
        },
        json={"subject_identifier": DEMO_ID_A},
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "invitation_already_active"


def test_invitation_ttl_default_and_bounds(client, app):
    from tests.c1.factories import setup_doctor_with_invitation

    chain = setup_doctor_with_invitation(app, client)
    doctor = chain["doctor"]
    visit_id = chain["visit"]["visit_id"]
    for ttl in (3599, 259201):
        response = client.post(
            f"/v1/doctor/verified-visits/{visit_id}/invitations",
            headers={
                "Authorization": f"Bearer {doctor['token']}",
                "Idempotency-Key": f"ttl-{ttl}",
            },
            json={"subject_identifier": DEMO_ID_A, "ttl_seconds": ttl},
        )
        assert response.status_code == 422, ttl
    # A second visit can issue with an explicit in-range TTL.
    visit2 = attest_visit(client, doctor, visit_ref="DEMO-VISIT-002", key="visit-002")
    issued = client.post(
        f"/v1/doctor/verified-visits/{visit2['visit_id']}/invitations",
        headers={
            "Authorization": f"Bearer {doctor['token']}",
            "Idempotency-Key": "ttl-3600",
        },
        json={"subject_identifier": DEMO_ID_A, "ttl_seconds": 3600},
    )
    assert issued.status_code == 201
    from backend.app.term1.timeutil import from_iso

    issued_at = from_iso(issued.json()["issued_at"])
    expires_at = from_iso(issued.json()["expires_at"])
    assert (expires_at - issued_at).total_seconds() == 3600


def test_revocation_is_idempotent_and_owned_by_the_issuing_doctor(client, app):
    from tests.c1.factories import setup_doctor_with_invitation

    chain = setup_doctor_with_invitation(app, client)
    doctor, invitation = chain["doctor"], chain["invitation"]
    url = f"/v1/doctor/invitations/{invitation['invitation_id']}/revoke"
    first = client.post(
        url,
        headers={"Authorization": f"Bearer {doctor['token']}", "Idempotency-Key": "revoke-1"},
        json={"reason_code": "patient_request"},
    )
    assert first.status_code == 200
    assert first.json()["status"] == "REVOKED"
    repeat = client.post(
        url,
        headers={"Authorization": f"Bearer {doctor['token']}", "Idempotency-Key": "revoke-1"},
        json={"reason_code": "patient_request"},
    )
    assert repeat.status_code == 200
    assert repeat.json()["idempotent_replay"] is True
    assert repeat.json()["revoked_at"] == first.json()["revoked_at"]


def test_another_doctor_cannot_read_or_revoke_a_foreign_invitation(client, app):
    from tests.c1.factories import setup_doctor_with_invitation

    chain = setup_doctor_with_invitation(app, client)
    intruder = provision_doctor(
        app, client, email="demo.intruder@cardioassist.local", display_name="Dr Intruder"
    )
    invitation_id = chain["invitation"]["invitation_id"]
    read = client.get(
        f"/v1/doctor/invitations/{invitation_id}",
        headers={"Authorization": f"Bearer {intruder['token']}"},
    )
    assert read.status_code == 404
    revoke = client.post(
        f"/v1/doctor/invitations/{invitation_id}/revoke",
        headers={"Authorization": f"Bearer {intruder['token']}", "Idempotency-Key": "i-1"},
        json={"reason_code": "hostile"},
    )
    assert revoke.status_code == 404
    visit_read = client.get(
        f"/v1/doctor/verified-visits/{chain['visit']['visit_id']}",
        headers={"Authorization": f"Bearer {intruder['token']}"},
    )
    assert visit_read.status_code == 404


def test_patients_and_admins_cannot_use_doctor_operations(client, app):
    from tests.c1.factories import setup_doctor_with_invitation

    chain = setup_doctor_with_invitation(app, client)
    admin_token = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)["session_token"]
    forbidden = client.post(
        "/v1/doctor/verified-visits",
        headers={"Authorization": f"Bearer {admin_token}", "Idempotency-Key": "admin-visit"},
        json={
            "visit_ref": "V-ADMIN",
            "subject_identifier": DEMO_ID_A,
            "asserted_visit_at": "2026-11-25T10:00:00Z",
            "attestation_code": "PRIOR_IN_PERSON_VISIT_DEMO",
        },
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "forbidden"


def test_expired_invitation_cannot_be_redeemed_and_can_be_reissued(client, app, clock):
    from tests.c1.factories import setup_doctor_with_invitation

    chain = setup_doctor_with_invitation(app, client)
    clock.advance(hours=25)
    # The session died with the absolute 8 h cap, so the doctor logs in again
    # (documented outcome of an idle-elevated prototype session).
    doctor = {
        **chain["doctor"],
        "token": login(client, chain["doctor"]["email"], chain["doctor"]["password"])["session_token"],
    }
    status = client.get(
        f"/v1/doctor/invitations/{chain['invitation']['invitation_id']}",
        headers={"Authorization": f"Bearer {doctor['token']}"},
    )
    assert status.status_code == 200, status.text
    assert status.json()["status"] == "EXPIRED"
    register_patient(
        client, chain["invitation"]["access_code"], key="expired-1", expect=401
    )
    # A fresh invitation for the same visit is allowed after expiry.
    reissued = issue_invitation(
        client,
        doctor,
        chain["visit"]["visit_id"],
        key="reissue-1",
    )
    assert reissued["invitation_id"] != chain["invitation"]["invitation_id"]


# --- identity key material (C0-F02) -----------------------------------------
def test_key_check_rows_are_persisted_for_both_purposes(app, client):
    from tests.c1.factories import setup_doctor_with_invitation

    setup_doctor_with_invitation(app, client)
    with app.state.database.engine.connect() as connection:
        rows = connection.execute(
            text("SELECT purpose, key_id, key_check_hash, alg FROM identity_key_check ORDER BY purpose")
        ).all()
    assert [row[0] for row in rows] == ["identity_match", "subject_canonical"]
    assert all(row[1] == "demo-v1" and row[3] == "hmac_sha256" for row in rows)
    assert all(len(row[2]) == 64 for row in rows)


def test_key_material_replacement_under_the_same_key_id_is_detected(migrated_url, clock, test_settings):
    """Same key id, different bytes: the persisted check no longer matches."""
    from backend.app.main import create_app
    from backend.app.term1 import identity
    from backend.app.term1.errors import ApiError
    from backend.app.term1.settings import Term1Settings
    from backend.app.term1.tx import write_transaction

    app = create_app(database_url=migrated_url, term1_settings=test_settings, term1_clock=clock)
    from tests.c1.factories import setup_doctor_with_invitation
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        setup_doctor_with_invitation(app, client)

    replaced = Term1Settings(
        identity_match_key=b"REPLACED-identity-match-key-000000001",  # same length, new bytes
        subject_key=test_settings.subject_key,
        pepper=test_settings.pepper,
        admin_bootstrap_secret=test_settings.admin_bootstrap_secret,
        identity_key_id=test_settings.identity_key_id,
    )
    with pytest.raises(ApiError) as error:
        with write_transaction(app.state.database) as session:
            identity.verify_or_activate(session, settings=replaced, clock=app.state.term1.clock, write=True)
    assert error.value.code == "identity_key_material_mismatch"

    # Read-only startup verification fails closed for the same reason.
    with pytest.raises(ApiError) as startup_error:
        from backend.app.term1.tx import read_transaction

        with read_transaction(app.state.database) as session:
            identity.verify_startup(session, settings=replaced)
    assert startup_error.value.code == "identity_key_material_mismatch"


def test_key_id_change_on_a_populated_database_is_refused(migrated_url, clock, test_settings):
    from fastapi.testclient import TestClient

    from backend.app.main import create_app
    from backend.app.term1 import identity
    from backend.app.term1.errors import ApiError
    from backend.app.term1.settings import Term1Settings
    from backend.app.term1.tx import write_transaction
    from tests.c1.factories import setup_doctor_with_invitation

    app = create_app(database_url=migrated_url, term1_settings=test_settings, term1_clock=clock)
    with TestClient(app) as client:
        setup_doctor_with_invitation(app, client)

    rotated = Term1Settings(
        identity_match_key=test_settings.identity_match_key,
        subject_key=test_settings.subject_key,
        pepper=test_settings.pepper,
        admin_bootstrap_secret=test_settings.admin_bootstrap_secret,
        identity_key_id="demo-v2",
    )
    with pytest.raises(ApiError) as error:
        with write_transaction(app.state.database) as session:
            identity.verify_or_activate(session, settings=rotated, clock=app.state.term1.clock, write=True)
    assert error.value.code in {
        "identity_key_replacement_unsupported",
        "identity_key_material_mismatch",
    }


def test_missing_key_checks_on_a_populated_database_fail_closed(app, client):
    """Populated identity data with no key-check rows must refuse, not re-bind."""
    from backend.app.term1 import identity
    from backend.app.term1.errors import ApiError
    from backend.app.term1.tx import write_transaction
    from tests.c1.factories import setup_doctor_with_invitation

    setup_doctor_with_invitation(app, client)
    with app.state.database.engine.begin() as connection:
        connection.execute(text("DELETE FROM identity_key_check"))
    with pytest.raises(ApiError) as error:
        with write_transaction(app.state.database) as session:
            identity.verify_or_activate(
                session,
                settings=app.state.term1.settings(),
                clock=app.state.term1.clock,
                write=True,
            )
    assert error.value.code == "identity_key_material_mismatch"
    # Nothing was silently re-created.
    with app.state.database.engine.connect() as connection:
        assert connection.execute(
            text("SELECT COUNT(*) FROM identity_key_check")
        ).scalar_one() == 0


def test_populated_database_with_foreign_identity_keys_refuses_startup(
    migrated_url, clock, test_settings
):
    """A check row written under other material blocks startup, never re-binds."""
    from backend.app.term1 import identity
    from backend.app.term1.errors import ApiError
    from backend.app.term1.models import IdentityKeyCheck
    from backend.app.term1.settings import Term1Settings
    from backend.app.term1.tx import write_transaction
    from backend.app.storage.database import Database

    app_settings = test_settings
    from backend.app.term1.timeutil import Clock

    database = Database(migrated_url)
    other = Term1Settings(
        identity_match_key=b"other-identity-match-key-000000000002",
        subject_key=b"other-subject-canonical-key-0000000003",
        pepper=b"other-pepper-00000000000000000000000004",
    )
    with write_transaction(database) as session:
        identity.verify_or_activate(session, settings=other, clock=Clock(clock), write=True)
    database.dispose()

    database = Database(migrated_url)
    try:
        with pytest.raises(ApiError):
            with __import__("backend.app.term1.tx", fromlist=["read_transaction"]).read_transaction(
                database
            ) as session:
                identity.verify_startup(session, settings=app_settings)
    finally:
        database.dispose()


def test_identity_digests_are_purpose_separated_and_stable(test_settings):
    from backend.app.term1 import identity

    normalized = crypto.normalize_demo_identifier(DEMO_ID_A)
    binding = identity.compute_binding(test_settings, normalized)
    assert binding.identifier_hmac != binding.canonical_subject_id
    assert binding.identifier_hmac == crypto.identifier_match_hmac(
        test_settings.identity_match_key, normalized
    )
    # Stable across calls and independent of the display label.
    again = identity.compute_binding(test_settings, normalized)
    assert again == binding
    other = identity.compute_binding(test_settings, crypto.normalize_demo_identifier(DEMO_ID_B))
    assert other.canonical_subject_id != binding.canonical_subject_id
