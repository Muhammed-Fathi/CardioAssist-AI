"""Reusable C1 setup steps for tests (synthetic demo data only)."""

from __future__ import annotations

import uuid

from sqlalchemy import text

from backend.app.term1.accounts import create_doctor
from backend.app.term1.models import UserAccount
from backend.app.term1.tx import write_transaction

from .conftest import ADMIN_EMAIL, ADMIN_PASSWORD, bootstrap_admin, login

VISIT_AT = "2026-11-25T10:00:00Z"
DEMO_ID_A = "DEMO-ID-001"
DEMO_ID_B = "DEMO-ID-002"


def admin_token_for(client) -> str:
    """Admin session token, tolerant of a rotated admin password in one test."""
    for password in ("admin demo password 001", "admin rotated password 01"):
        response = client.post(
            "/v1/auth/login", json={"email": ADMIN_EMAIL, "password": password}
        )
        if response.status_code == 200:
            return response.json()["session_token"]
    raise AssertionError("No working administrator password in this test.")


def provision_doctor(
    app, client, *, email: str, display_name: str, password: str = "doctor password 0001"
) -> dict:
    """Admin-provisions a doctor, who then clears the temporary-password state."""
    admin_token = admin_token_for(client)
    with write_transaction(app.state.database) as session:
        admin_id = session.execute(
            text("SELECT user_id FROM user_account WHERE role='admin'")
        ).scalar_one()
        actor = session.get(UserAccount, admin_id)
        created = create_doctor(
            session,
            clock=app.state.term1.clock,
            actor=actor,
            email=email,
            display_name=display_name,
            temp_password_policy="one_time_secret",
        )
    temp_token = login(client, email, created["temp_secret"])["session_token"]
    changed = client.post(
        "/v1/me/password",
        headers={"Authorization": f"Bearer {temp_token}"},
        json={"current_password": created["temp_secret"], "new_password": password},
    )
    assert changed.status_code == 200, changed.text
    token = login(client, email, password)["session_token"]
    return {
        **created,
        "email": email,
        "display_name": display_name,
        "password": password,
        "token": token,
        "admin_token": admin_token,
    }


def attest_visit(
    client, doctor: dict, *, visit_ref: str, identifier: str = DEMO_ID_A, key: str | None = None
) -> dict:
    headers = {
        "Authorization": f"Bearer {doctor['token']}",
        "Idempotency-Key": key or f"visit-{uuid.uuid4()}",
    }
    response = client.post(
        "/v1/doctor/verified-visits",
        headers=headers,
        json={
            "visit_ref": visit_ref,
            "subject_identifier": identifier,
            "asserted_visit_at": VISIT_AT,
            "attestation_code": "PRIOR_IN_PERSON_VISIT_DEMO",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def issue_invitation(
    client,
    doctor: dict,
    visit_id: str,
    *,
    identifier: str = DEMO_ID_A,
    ttl_seconds: int | None = None,
    key: str | None = None,
    expect: int = 201,
) -> dict:
    headers = {
        "Authorization": f"Bearer {doctor['token']}",
        "Idempotency-Key": key or f"invite-{uuid.uuid4()}",
    }
    payload = {"subject_identifier": identifier}
    if ttl_seconds is not None:
        payload["ttl_seconds"] = ttl_seconds
    response = client.post(
        f"/v1/doctor/verified-visits/{visit_id}/invitations", headers=headers, json=payload
    )
    assert response.status_code == expect, (headers["Idempotency-Key"], response.text)
    return response.json()


def register_patient(
    client,
    access_code: str,
    *,
    identifier: str = DEMO_ID_A,
    email: str = "demo.patient@cardioassist.local",
    password: str = "patient password 0001",
    key: str | None = None,
    consent_ack: bool = True,
    expect: int = 201,
) -> dict:
    response = client.post(
        "/v1/patients/register",
        headers={"Idempotency-Key": key or f"register-{uuid.uuid4()}"},
        json={
            "access_code": access_code,
            "identifier": identifier,
            "email": email,
            "password": password,
            "consent_ack": consent_ack,
        },
    )
    assert response.status_code == expect, response.text
    return response.json()


def clean_doctor(
    app, client, *, email: str, display_name: str, password: str = "doctor password 0001"
) -> dict:
    """Provision a doctor directly and clear the temporary-password restriction.

    Used when further doctors are created inside a test whose admin password may
    already have been rotated, so it never depends on a stored admin session.
    """
    from backend.app.term1.accounts import create_doctor
    from backend.app.term1.models import UserAccount
    from backend.app.term1.tx import write_transaction

    with write_transaction(app.state.database) as session:
        admin_id = session.execute(
            text("SELECT user_id FROM user_account WHERE role='admin'")
        ).scalar_one()
        actor = session.get(UserAccount, admin_id)
        created = create_doctor(
            session,
            clock=app.state.term1.clock,
            actor=actor,
            email=email,
            display_name=display_name,
            temp_password_policy="one_time_secret",
        )
    temp_token = login(client, email, created["temp_secret"])["session_token"]
    changed = client.post(
        "/v1/me/password",
        headers={"Authorization": f"Bearer {temp_token}"},
        json={"current_password": created["temp_secret"], "new_password": password},
    )
    assert changed.status_code == 200, changed.text
    token = login(client, email, password)["session_token"]
    return {
        **created,
        "email": email,
        "display_name": display_name,
        "password": password,
        "token": token,
    }


def setup_doctor_with_invitation(
    app,
    client,
    *,
    doctor_email: str = "demo.doctor@cardioassist.local",
    doctor_name: str = "Dr Demo",
    visit_ref: str = "DEMO-VISIT-001",
    identifier: str = DEMO_ID_A,
    password: str = "doctor password 0001",
) -> dict:
    """Full pre-enrollment chain: admin -> doctor -> visit -> invitation code."""
    bootstrap_admin(app)
    doctor = provision_doctor(
        app, client, email=doctor_email, display_name=doctor_name, password=password
    )
    visit = attest_visit(client, doctor, visit_ref=visit_ref, identifier=identifier)
    invitation = issue_invitation(client, doctor, visit["visit_id"], identifier=identifier)

    # Every later issuance opens a *new* visit: a visit holds at most one live
    # invitation, so reusing visit_id in a test would be a domain conflict.
    def _fresh_visit(seq: int = 0, target_identifier: str = identifier) -> tuple[dict, dict]:
        reference = f"{visit_ref}-NEXT-{seq}"
        fresh = attest_visit(client, doctor, visit_ref=reference, identifier=target_identifier)
        fresh_invitation = issue_invitation(
            client, doctor, fresh["visit_id"], identifier=target_identifier
        )
        return fresh, fresh_invitation

    return {
        "doctor": doctor,
        "visit": visit,
        "invitation": invitation,
        "fresh_visit": _fresh_visit,
    }
