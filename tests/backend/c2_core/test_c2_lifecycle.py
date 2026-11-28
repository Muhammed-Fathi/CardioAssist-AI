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


def test_wrong_worker_or_fence_rejects_completion_without_writes(
    monkeypatch, app, client
):
    _seeded, created = _start_running_attempt(monkeypatch, app, client)
    monkeypatch.undo()
    attempt = _attempt_row(app, created["attempt_id"])

    for worker_id, fence_token in (
        ("wrong-worker", attempt["fence_token"]),
        (attempt["worker_id"], "0" * 64),
    ):
        with pytest.raises(ApiError) as excinfo:
            with write_transaction(app.state.database) as session:
                inference_lifecycle.complete_unavailable(
                    session,
                    clock=app.state.term1.clock,
                    attempt_id=attempt["attempt_id"],
                    reason_code="real_ai_not_authorized",
                    worker_id=worker_id,
                    fence_token=fence_token,
                )
        assert excinfo.value.code == "stale_attempt_fenced"
        assert _attempt_row(app, attempt["attempt_id"])["state"] == "INFERENCE_RUNNING"
        state = _assessment_row(app, created["assessment_id"])
        assert state["status"] == "INFERENCE_RUNNING"
        assert state["active_attempt_id"] == attempt["attempt_id"]


def test_attempt_insert_is_generation_guarded_and_atomically_associated(
    monkeypatch, app, client
):
    _seeded, created = _start_running_attempt(monkeypatch, app, client)
    monkeypatch.undo()
    first_attempt = _attempt_row(app, created["attempt_id"])
    first_assessment = _assessment_row(app, created["assessment_id"])
    assert first_assessment["status"] == "INFERENCE_RUNNING"
    assert first_assessment["active_attempt_id"] == first_attempt["attempt_id"]

    # Complete generation 0 with a retryable error, then perform the valid
    # C0 ERROR -> INPUT_VALIDATED generation-advance transition directly.
    with write_transaction(app.state.database) as session:
        inference_lifecycle.complete_error(
            session,
            clock=app.state.term1.clock,
            attempt_id=first_attempt["attempt_id"],
            reason_code="worker_error",
            worker_id=first_attempt["worker_id"],
            fence_token=first_attempt["fence_token"],
        )
    with app.state.database.engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE assessment SET status = 'INPUT_VALIDATED', reason_code = NULL, "
                "current_generation = 1, updated_at = :now "
                "WHERE assessment_id = :assessment_id"
            ),
            {
                "now": app.state.term1.clock.now_iso(),
                "assessment_id": created["assessment_id"],
            },
        )

    def attempt_values(*, attempt_id: str, generation: int, digest: str):
        now = app.state.term1.clock.now_iso()
        return {
            "attempt_id": attempt_id,
            "assessment_id": created["assessment_id"],
            "generation": generation,
            "attempt_idempotency_hash": digest * 64,
            "worker_id": "disabled_stub",
            "fence_token": "f" * 64,
            "state": "INFERENCE_RUNNING",
            "reason_code": None,
            "leased_at": now,
            "lease_until": app.state.term1.clock.iso_after(300),
            "completed_at": None,
        }

    insert_sql = text(
        "INSERT INTO inference_attempt "
        "(attempt_id, assessment_id, generation, attempt_idempotency_hash, "
        "worker_id, fence_token, state, reason_code, leased_at, lease_until, completed_at) "
        "VALUES (:attempt_id, :assessment_id, :generation, :attempt_idempotency_hash, "
        ":worker_id, :fence_token, :state, :reason_code, :leased_at, :lease_until, :completed_at)"
    )
    invalid = attempt_values(attempt_id=str(uuid.uuid4()), generation=0, digest="a")
    with pytest.raises(DBAPIError, match="inference_attempt_insert_forbidden"):
        with app.state.database.engine.begin() as connection:
            connection.execute(insert_sql, invalid)

    validated = _assessment_row(app, created["assessment_id"])
    assert validated["status"] == "INPUT_VALIDATED"
    assert validated["active_attempt_id"] is None
    assert validated["current_generation"] == 1

    second_attempt_id = str(uuid.uuid4())
    valid = attempt_values(attempt_id=second_attempt_id, generation=1, digest="b")
    with app.state.database.engine.begin() as connection:
        connection.execute(insert_sql, valid)

    associated = _assessment_row(app, created["assessment_id"])
    assert associated["status"] == "INFERENCE_RUNNING"
    assert associated["active_attempt_id"] == second_attempt_id
    assert associated["current_generation"] == 1
    second_attempt = _attempt_row(app, second_attempt_id)
    assert second_attempt["state"] == "INFERENCE_RUNNING"
    assert second_attempt["worker_id"] == "disabled_stub"

    with write_transaction(app.state.database) as session:
        terminal = inference_lifecycle.complete_unavailable(
            session,
            clock=app.state.term1.clock,
            attempt_id=second_attempt_id,
            reason_code="real_ai_not_authorized",
            worker_id=second_attempt["worker_id"],
            fence_token=second_attempt["fence_token"],
        )
        assert terminal.state == "INFERENCE_UNAVAILABLE"
    assert _assessment_row(app, created["assessment_id"])["status"] == "INFERENCE_UNAVAILABLE"


def test_terminal_write_failure_rolls_back_both_attempt_and_assessment(
    monkeypatch, app, client
):
    _seeded, created = _start_running_attempt(monkeypatch, app, client)
    attempt = _attempt_row(app, created["attempt_id"])
    with app.state.database.engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TRIGGER tr_test_reject_attempt_terminal "
            "BEFORE UPDATE OF state ON inference_attempt "
            "WHEN NEW.state != 'INFERENCE_RUNNING' BEGIN "
            "SELECT RAISE(ABORT, 'test_attempt_terminal_failure'); END"
        )
    try:
        with pytest.raises(DBAPIError, match="test_attempt_terminal_failure"):
            with write_transaction(app.state.database) as session:
                inference_lifecycle.complete_error(
                    session,
                    clock=app.state.term1.clock,
                    attempt_id=attempt["attempt_id"],
                    reason_code="worker_error",
                    worker_id=attempt["worker_id"],
                    fence_token=attempt["fence_token"],
                )
    finally:
        with app.state.database.engine.begin() as connection:
            connection.exec_driver_sql(
                "DROP TRIGGER IF EXISTS tr_test_reject_attempt_terminal"
            )

    state = _assessment_row(app, created["assessment_id"])
    unchanged_attempt = _attempt_row(app, attempt["attempt_id"])
    assert state["status"] == "INFERENCE_RUNNING"
    assert state["active_attempt_id"] == attempt["attempt_id"]
    assert unchanged_attempt["state"] == "INFERENCE_RUNNING"
    assert unchanged_attempt["reason_code"] is None


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
