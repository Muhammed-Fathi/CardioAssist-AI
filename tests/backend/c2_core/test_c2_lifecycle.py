"""P-16 fencing, recovery and authorization precedence tests for C2.

S1 deliberately terminalizes its disabled worker inline. These tests replace
only that SAFE_SCOPE terminal call so a real, fully constrained RUNNING row is
committed, then exercise the lifecycle service against the fresh migrated
schema and immutable SQL triggers.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from backend.app.term1 import assessments, inference_lifecycle
from backend.app.term1.errors import ApiError
from backend.app.term1.models import Assessment, InferenceAttempt
from backend.app.term1.tx import read_transaction, write_transaction
from tests.backend.c2_core.conftest import both
from tests.backend.c2_core.test_c2_services import seed_patient, submit_s1


def _start_running_attempt(
    monkeypatch, app, client, *, seed_args=None, **s1_overrides
):
    """Create a real assessment/attempt but leave the attempt RUNNING."""
    seeded = seed_patient(app, client, **(seed_args or {}))
    monkeypatch.setattr(
        assessments.inference_lifecycle,
        "complete_unavailable",
        lambda *args, **kwargs: None,
    )
    response = submit_s1(
        client,
        seeded["token"],
        seeded["assignment_id"],
        seeded["profile"]["health_profile_id"],
        **s1_overrides,
    )
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "INFERENCE_RUNNING"
    return seeded, response.json()


def _attempt_row(app, attempt_id: str):
    with read_transaction(app.state.database) as session:
        row = session.execute(
            select(InferenceAttempt).where(InferenceAttempt.attempt_id == attempt_id)
        ).scalar_one()
        return {
            "attempt_id": row.attempt_id,
            "worker_id": row.worker_id,
            "fence_token": row.fence_token,
            "lease_until": row.lease_until,
            "completed_at": row.completed_at,
            "state": row.state,
            "reason_code": row.reason_code,
        }


def _assessment_row(app, assessment_id: str):
    with read_transaction(app.state.database) as session:
        row = session.execute(
            select(Assessment).where(Assessment.assessment_id == assessment_id)
        ).scalar_one()
        return {
            "assessment_id": row.assessment_id,
            "status": row.status,
            "reason_code": row.reason_code,
            "active_attempt_id": row.active_attempt_id,
            "current_generation": row.current_generation,
            "stage_complete": row.stage_complete,
        }


def test_recovery_includes_exact_lease_expiry_and_increments_once(
    monkeypatch, app, client, clock
):
    _seeded, created = _start_running_attempt(monkeypatch, app, client)
    attempt = _attempt_row(app, created["attempt_id"])
    assert attempt["state"] == "INFERENCE_RUNNING"
    assert attempt["lease_until"] == app.state.term1.clock.iso_after(300)

    # A worker cannot terminalize at equality: lease_until must be strictly
    # greater than now. The failed transaction must leave both rows untouched.
    clock.advance(seconds=300)
    with pytest.raises(ApiError) as excinfo:
        with write_transaction(app.state.database) as session:
            inference_lifecycle.complete_error(
                session,
                clock=app.state.term1.clock,
                attempt_id=attempt["attempt_id"],
                reason_code="worker_error",
                worker_id=attempt["worker_id"],
                fence_token=attempt["fence_token"],
            )
    assert excinfo.value.code == "stale_attempt_fenced"
    assert _attempt_row(app, attempt["attempt_id"])["state"] == "INFERENCE_RUNNING"
    assert _assessment_row(app, created["assessment_id"])["status"] == "INFERENCE_RUNNING"

    # Recovery uses the inclusive cutoff (<= now), increments the generation
    # exactly once and records completion at the lease boundary.
    with write_transaction(app.state.database) as session:
        assert inference_lifecycle.recover_expired(
            session, clock=app.state.term1.clock
        ) == 1
    assessment = _assessment_row(app, created["assessment_id"])
    terminal = _attempt_row(app, attempt["attempt_id"])
    assert assessment["status"] == "INFERENCE_ERROR"
    assert assessment["reason_code"] == "lease_expired"
    assert assessment["active_attempt_id"] is None
    assert assessment["current_generation"] == 1
    assert terminal["state"] == "INFERENCE_ERROR"
    assert terminal["reason_code"] == "lease_expired"
    assert terminal["completed_at"] == terminal["lease_until"]

    with write_transaction(app.state.database) as session:
        assert inference_lifecycle.recover_expired(
            session, clock=app.state.term1.clock
        ) == 0
    assert _assessment_row(app, created["assessment_id"])["current_generation"] == 1


def test_revoked_assignment_overrides_a_requested_worker_error(
    monkeypatch, app, client
):
    seeded, created = _start_running_attempt(monkeypatch, app, client)
    attempt = _attempt_row(app, created["attempt_id"])

    revoke = client.post(
        f"/v1/me/assignments/{seeded['assignment_id']}/revoke",
        headers=both(seeded["token"], f"revoke-running-{uuid.uuid4()}"),
        json={"reason_code": "patient_revoked_demo"},
    )
    assert revoke.status_code == 200, revoke.text

    with write_transaction(app.state.database) as session:
        terminal = inference_lifecycle.complete_error(
            session,
            clock=app.state.term1.clock,
            attempt_id=attempt["attempt_id"],
            reason_code="worker_error",
            worker_id=attempt["worker_id"],
            fence_token=attempt["fence_token"],
        )
        assert terminal.state == "INFERENCE_UNAVAILABLE"
        assert terminal.reason_code == "authorization_withdrawn"

    assessment = _assessment_row(app, created["assessment_id"])
    terminal = _attempt_row(app, attempt["attempt_id"])
    assert assessment["status"] == "INFERENCE_UNAVAILABLE"
    assert assessment["reason_code"] == "authorization_withdrawn"
    assert assessment["current_generation"] == 0
    assert terminal["state"] == "INFERENCE_UNAVAILABLE"
    assert terminal["reason_code"] == "authorization_withdrawn"


def test_revoked_authorization_during_recovery_uses_unavailable(
    monkeypatch, app, client, clock
):
    seeded, created = _start_running_attempt(monkeypatch, app, client)
    attempt = _attempt_row(app, created["attempt_id"])

    revoke = client.post(
        "/v1/me/consent/synthetic-demo/revoke",
        headers=both(seeded["token"], f"revoke-expired-{uuid.uuid4()}"),
        json={"reason_code": "patient_revoked_demo"},
    )
    assert revoke.status_code == 200, revoke.text
    clock.advance(seconds=300)

    with write_transaction(app.state.database) as session:
        assert inference_lifecycle.recover_expired(
            session, clock=app.state.term1.clock
        ) == 1

    assessment = _assessment_row(app, created["assessment_id"])
    terminal = _attempt_row(app, attempt["attempt_id"])
    assert assessment["status"] == "INFERENCE_UNAVAILABLE"
    assert assessment["reason_code"] == "authorization_withdrawn"
    assert assessment["active_attempt_id"] is None
    assert assessment["current_generation"] == 1
    assert terminal["state"] == "INFERENCE_UNAVAILABLE"
    assert terminal["reason_code"] == "authorization_withdrawn"
    assert terminal["completed_at"] == terminal["lease_until"]


def test_direct_sql_cannot_rewrite_or_bypass_attempt_lifecycle(
    monkeypatch, app, client
):
    _seeded, created = _start_running_attempt(monkeypatch, app, client)
    attempt = _attempt_row(app, created["attempt_id"])

    for column, value in (
        ("worker_id", "forged-worker"),
        ("fence_token", "0" * 64),
        ("lease_until", "2026-11-28T10:00:00.000000Z"),
    ):
        with pytest.raises(DBAPIError, match="inference_attempt_update_forbidden"):
            with app.state.database.engine.begin() as connection:
                connection.execute(
                    text(
                        f"UPDATE inference_attempt SET {column} = :value "
                        "WHERE attempt_id = :id"
                    ),
                    {"value": value, "id": attempt["attempt_id"]},
                )

    # A direct terminal-state write cannot beat the still-live assessment
    # pointer; the service must clear the assessment first under the fence CAS.
    with pytest.raises(DBAPIError, match="inference_attempt_update_forbidden"):
        with app.state.database.engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE inference_attempt SET state = 'INFERENCE_ERROR', "
                    "reason_code = 'worker_error', completed_at = :completed_at "
                    "WHERE attempt_id = :id"
                ),
                {
                    "completed_at": app.state.term1.clock.now_iso(),
                    "id": attempt["attempt_id"],
                },
            )

    with write_transaction(app.state.database) as session:
        inference_lifecycle.complete_error(
            session,
            clock=app.state.term1.clock,
            attempt_id=attempt["attempt_id"],
            reason_code="worker_error",
            worker_id=attempt["worker_id"],
            fence_token=attempt["fence_token"],
        )

    with pytest.raises(DBAPIError, match="inference_attempt_update_forbidden"):
        with app.state.database.engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE inference_attempt SET reason_code = 'lease_expired' "
                    "WHERE attempt_id = :id"
                ),
                {"id": attempt["attempt_id"]},
            )
    assert _attempt_row(app, attempt["attempt_id"])["reason_code"] == "worker_error"


def test_abstention_requires_an_incomplete_optional_panel(monkeypatch, app, client):
    seeded, created = _start_running_attempt(monkeypatch, app, client)
    attempt = _attempt_row(app, created["attempt_id"])

    with pytest.raises(ApiError) as excinfo:
        with write_transaction(app.state.database) as session:
            inference_lifecycle.complete_abstained(
                session,
                clock=app.state.term1.clock,
                attempt_id=attempt["attempt_id"],
                worker_id=attempt["worker_id"],
                fence_token=attempt["fence_token"],
            )
    assert excinfo.value.code == "validation_failed"
    assert _attempt_row(app, attempt["attempt_id"])["state"] == "INFERENCE_RUNNING"
    assert _assessment_row(app, created["assessment_id"])["status"] == "INFERENCE_RUNNING"

    with pytest.raises(DBAPIError, match="assessment_pointer_update_forbidden"):
        with app.state.database.engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE assessment SET status = 'INFERENCE_ABSTAINED', "
                    "reason_code = 'optional_panel_field_missing', "
                    "active_attempt_id = NULL, updated_at = :updated_at "
                    "WHERE assessment_id = :id"
                ),
                {
                    "updated_at": app.state.term1.clock.now_iso(),
                    "id": created["assessment_id"],
                },
            )

    panel_input = {
        "inputs": {
            "age": 54.0,
            "sex": 0,
            "cp": 1,
            "trestbps": None,
        },
        "units": {"age": "years"},
        "missing_reasons": {"trestbps": "not_measured"},
    }
    response = submit_s1(
        client,
        seeded["token"],
        seeded["assignment_id"],
        seeded["profile"]["health_profile_id"],
        panel_input=panel_input,
    )
    assert response.status_code == 201, response.text
    incomplete = response.json()
    incomplete_assessment = _assessment_row(app, incomplete["assessment_id"])
    assert incomplete_assessment["stage_complete"] is False
    incomplete_attempt = _attempt_row(app, incomplete["attempt_id"])
    with write_transaction(app.state.database) as session:
        terminal = inference_lifecycle.complete_abstained(
            session,
            clock=app.state.term1.clock,
            attempt_id=incomplete_attempt["attempt_id"],
            worker_id=incomplete_attempt["worker_id"],
            fence_token=incomplete_attempt["fence_token"],
        )
        assert terminal.state == "INFERENCE_ABSTAINED"
        assert terminal.reason_code == "optional_panel_field_missing"
    assert _assessment_row(app, incomplete["assessment_id"])["status"] == "INFERENCE_ABSTAINED"
