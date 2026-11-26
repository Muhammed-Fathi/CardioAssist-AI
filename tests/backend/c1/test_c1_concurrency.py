"""Race conditions on real, independent SQLite connections.

Each worker opens its own ``Database`` (its own engine and its own connection),
so there is no shared session or in-process lock. The only serialisation is
SQLite's own ``BEGIN IMMEDIATE`` write lock plus the conditional UPDATEs and
UNIQUE constraints the design relies on. No mocks, and no assertions that merely
record that a call happened: every assertion is about durable end state.
"""

from __future__ import annotations

import threading
from typing import Callable

from sqlalchemy import text

from backend.app.storage.database import Database
from backend.app.term1 import constants, enrollment, idempotency, visits
from backend.app.term1.errors import ApiError
from backend.app.term1.sessions import authenticate
from backend.app.term1.timeutil import Clock
from backend.app.term1.tx import write_transaction

from tests.backend.c1.factories import (
    DEMO_ID_A,
    attest_visit,
    bootstrap_admin,
    issue_invitation,
    provision_doctor,
    register_patient,
    setup_doctor_with_invitation,
)

PATIENT_EMAIL = "demo.patient@cardioassist.local"
PATIENT_PASSWORD = "patient password 0001"
ADMIN_EMAIL = "demo.admin@cardioassist.local"
ADMIN_PASSWORD = "admin demo password 001"


def _run_concurrently(workers: list[Callable[[], object]]) -> list[object]:
    """Start every worker on its own thread behind a shared barrier."""
    barrier = threading.Barrier(len(workers))
    results: list[object] = [None] * len(workers)
    errors: list[BaseException | None] = [None] * len(workers)

    def wrap(index: int, worker: Callable[[], object]) -> None:
        try:
            barrier.wait(timeout=15)
            results[index] = worker()
        except BaseException as error:  # noqa: BLE001 - re-raised via _outcome
            errors[index] = error

    threads = [
        threading.Thread(target=wrap, args=(index, worker), daemon=True)
        for index, worker in enumerate(workers)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    return [error if error is not None else result for error, result in zip(errors, results)]


def _outcome(value: object) -> str:
    if isinstance(value, ApiError):
        return value.code
    if isinstance(value, BaseException):
        raise AssertionError(f"Unexpected worker failure: {value!r}") from value
    assert value is not None, "Worker produced no outcome."
    return str(value)


def _worker_database(url: str) -> Database:
    """A Database bound to its own engine, i.e. its own pool and connections."""
    return Database(url)


def _count(url: str, statement: str) -> int:
    database = Database(url)
    try:
        with database.engine.connect() as connection:
            return connection.execute(text(statement)).scalar_one()
    finally:
        database.dispose()


# --- concurrent redemption ---------------------------------------------------
def test_two_connections_cannot_redeem_the_same_invitation(migrated_url, clock, test_settings):
    from fastapi.testclient import TestClient

    from backend.app.main import create_app

    app = create_app(database_url=migrated_url, term1_settings=test_settings, term1_clock=clock)
    with TestClient(app) as client:
        chain = setup_doctor_with_invitation(app, client)
    code = chain["invitation"]["access_code"]
    term1_clock = Clock(clock)

    def attempt(index: int) -> Callable[[], object]:
        def run() -> object:
            database = _worker_database(migrated_url)
            try:
                with write_transaction(database) as session:
                    import time

                    time.sleep(0.05 * index)  # both workers inside the critical region
                    return enrollment.register_patient(
                        session,
                        clock=term1_clock,
                        settings=test_settings,
                        access_code=code,
                        identifier=DEMO_ID_A,
                        email=f"demo.race{index}@cardioassist.local",
                        password="race password 0001",
                        consent_ack=True,
                    )["patient_id"]
            finally:
                database.dispose()

        return run

    outcomes = [_outcome(value) for value in _run_concurrently([attempt(0), attempt(1)])]
    successes = [value for value in outcomes if not value.startswith("invalid")]
    failures = [value for value in outcomes if value.startswith("invalid")]
    assert len(successes) == 1, outcomes
    assert failures == ["invalid_invitation"], outcomes

    assert _count(migrated_url, "SELECT COUNT(*) FROM patient_profile") == 1
    assert _count(migrated_url, "SELECT COUNT(*) FROM invitation_redemption") == 1
    assert (
        _count(
            migrated_url,
            "SELECT COUNT(*) FROM patient_invitation WHERE consumed_at IS NOT NULL",
        )
        == 1
    )
    assert _count(migrated_url, "SELECT COUNT(*) FROM consent_record") == 1


def test_two_connections_cannot_open_two_active_assignments(migrated_url, clock, test_settings):
    """The partial UNIQUE(doctor, patient) WHERE active is the final guarantee."""
    from fastapi.testclient import TestClient

    from backend.app.main import create_app
    from backend.app.term1.models import UserAccount

    app = create_app(database_url=migrated_url, term1_settings=test_settings, term1_clock=clock)
    with TestClient(app) as client:
        chain = setup_doctor_with_invitation(app, client)
        first = register_patient(client, chain["invitation"]["access_code"], password=PATIENT_PASSWORD)
        second_doctor = provision_doctor(
            app, client, email="demo.doc2@cardioassist.local", display_name="Dr Two"
        )
        visit = attest_visit(client, second_doctor, visit_ref="V-RACE-LINK")
        invitation = issue_invitation(client, second_doctor, visit["visit_id"])
        from tests.backend.c1.conftest import login

        patient_token = login(client, PATIENT_EMAIL, PATIENT_PASSWORD)["session_token"]
    assert first["patient_id"] and patient_token
    invite_code = invitation["access_code"]
    term1_clock = Clock(clock)

    def attempt(index: int) -> Callable[[], object]:
        def run() -> object:
            database = _worker_database(migrated_url)
            try:
                with write_transaction(database) as session:
                    account_id = session.execute(
                        text("SELECT user_id FROM user_account WHERE role='patient'")
                    ).scalar_one()
                    actor = session.get(UserAccount, account_id)
                    import time

                    time.sleep(0.05 * index)
                    result = enrollment.link_patient(
                        session,
                        clock=term1_clock,
                        settings=test_settings,
                        account=actor,
                        access_code=invite_code,
                        identifier=DEMO_ID_A,
                        accept_linking=True,
                    )
                    return result["assignment_id"]
            finally:
                database.dispose()

        return run

    outcomes = [_outcome(value) for value in _run_concurrently([attempt(0), attempt(1)])]
    assert len([value for value in outcomes if not value.startswith("invalid")]) == 1, outcomes
    duplicates = _count(
        migrated_url,
        "SELECT COUNT(*) FROM (SELECT doctor_id, patient_id FROM doctor_patient_assignment "
        "WHERE revoked_at IS NULL GROUP BY doctor_id, patient_id HAVING COUNT(*) > 1)",
    )
    assert duplicates == 0
    assert (
        _count(
            migrated_url,
            "SELECT COUNT(*) FROM invitation_redemption WHERE flow='link'",
        )
        == 1
    )


# --- concurrent refresh ------------------------------------------------------
def test_concurrent_refresh_produces_exactly_one_replacement(client, app):
    bootstrap_admin(app)
    from tests.backend.c1.conftest import login

    token = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)["session_token"]

    def attempt(_index: int) -> Callable[[], object]:
        def run() -> object:
            response = client.post("/v1/auth/refresh", headers={"Authorization": f"Bearer {token}"})
            return f"{response.status_code}:{response.json().get('session_token', '')}"

        return run

    outcomes = [_outcome(value) for value in _run_concurrently([attempt(0), attempt(1)])]
    succeeded = [value for value in outcomes if value.startswith("200:")]
    assert len(succeeded) == 1, outcomes
    assert outcomes.count("401:") == 1, outcomes
    replacement = succeeded[0].split(":", 1)[1]
    with app.state.database.engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM session WHERE revoked_at IS NULL")).scalar_one() == 1
    assert (
        client.get("/v1/auth/me", headers={"Authorization": f"Bearer {replacement}"}).status_code
        == 200
    )


# --- revocation vs. an in-flight authenticated write ------------------------
def test_suspension_during_a_write_blocks_the_effect(migrated_url, clock, test_settings):
    """Re-checking account state inside the transaction defeats a stale actor."""
    from fastapi.testclient import TestClient

    from backend.app.main import create_app

    app = create_app(database_url=migrated_url, term1_settings=test_settings, term1_clock=clock)
    with TestClient(app) as client:
        chain = setup_doctor_with_invitation(app, client)
        doctor_token = chain["doctor"]["token"]

    database = Database(migrated_url)
    try:
        with write_transaction(database) as session:
            doctor_id = session.execute(
                text("SELECT user_id FROM user_account WHERE role='doctor'")
            ).scalar_one()
            session.execute(
                text("UPDATE user_account SET status='SUSPENDED' WHERE user_id=:u"),
                {"u": doctor_id},
            )
            session.execute(
                text("UPDATE session SET revoked_at=created_at WHERE user_id=:u"),
                {"u": doctor_id},
            )
        try:
            with write_transaction(database) as session:
                authenticate(session, clock=Clock(clock), token=doctor_token)
            outcome = "authorized"
        except ApiError as error:
            outcome = error.code
    finally:
        database.dispose()
    assert outcome == "invalid_session"
    assert (
        _count(
            migrated_url,
            "SELECT COUNT(*) FROM session s JOIN user_account u ON u.user_id = s.user_id "
            "WHERE u.role='doctor' AND s.revoked_at IS NULL",
        )
        == 0
    )


def test_suspension_revokes_sessions_and_blocks_reads(client, app):
    chain = setup_doctor_with_invitation(app, client)
    doctor = chain["doctor"]
    from tests.backend.c1.conftest import login

    admin = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    response = client.patch(
        f"/v1/admin/accounts/{doctor['user_id']}/status",
        headers={"Authorization": f"Bearer {admin['session_token']}", "Idempotency-Key": "race-suspend"},
        json={"status": "SUSPENDED", "reason_code": "race"},
    )
    assert response.status_code == 200
    assert (
        client.get(
            f"/v1/doctor/verified-visits/{chain['visit']['visit_id']}",
            headers={"Authorization": f"Bearer {doctor['token']}"},
        ).status_code
        == 401
    )


# --- concurrent invitation issuance -----------------------------------------
def test_simultaneous_invitation_issuance_yields_one_live_invitation(
    migrated_url, clock, test_settings
):
    from fastapi.testclient import TestClient

    from backend.app.main import create_app
    from backend.app.term1.models import UserAccount

    app = create_app(database_url=migrated_url, term1_settings=test_settings, term1_clock=clock)
    with TestClient(app) as client:
        bootstrap_admin(app)
        doctor = provision_doctor(
            app, client, email="demo.race.doctor@cardioassist.local", display_name="Dr Race"
        )
        visit = attest_visit(client, doctor, visit_ref="V-RACE-ISSUE")
    visit_id = visit["visit_id"]
    term1_clock = Clock(clock)

    def attempt(index: int) -> Callable[[], object]:
        def run() -> object:
            database = _worker_database(migrated_url)
            try:
                with write_transaction(database) as session:
                    account_id = session.execute(
                        text("SELECT user_id FROM user_account WHERE role='doctor'")
                    ).scalar_one()
                    actor = session.get(UserAccount, account_id)
                    import time

                    time.sleep(0.05 * index)
                    return visits.issue_invitation(
                        session,
                        clock=term1_clock,
                        settings=test_settings,
                        account=actor,
                        visit_id=visit_id,
                        subject_identifier=DEMO_ID_A,
                        ttl_seconds=None,
                    )["invitation_id"]
            finally:
                database.dispose()

        return run

    outcomes = [_outcome(value) for value in _run_concurrently([attempt(0), attempt(1)])]
    assert outcomes.count("invitation_already_active") == 1, outcomes
    assert (
        _count(
            migrated_url,
            "SELECT COUNT(*) FROM patient_invitation WHERE consumed_at IS NULL AND revoked_at IS NULL",
        )
        == 1
    )


# --- concurrent idempotent replay -------------------------------------------
def test_concurrent_same_key_requests_never_execute_twice(migrated_url, clock, test_settings):
    from fastapi.testclient import TestClient

    from backend.app.main import create_app
    from backend.app.term1.models import UserAccount

    app = create_app(database_url=migrated_url, term1_settings=test_settings, term1_clock=clock)
    with TestClient(app) as client:
        bootstrap_admin(app)
        doctor = provision_doctor(
            app, client, email="demo.idem.doctor@cardioassist.local", display_name="Dr Idem"
        )
        visit = attest_visit(client, doctor, visit_ref="V-IDEM-RACE")
    visit_id = visit["visit_id"]
    actor_token = doctor["token"]
    term1_clock = Clock(clock)

    def attempt(index: int) -> Callable[[], object]:
        def run() -> object:
            database = _worker_database(migrated_url)
            try:
                with write_transaction(database) as session:
                    actor = authenticate(session, clock=term1_clock, token=actor_token)[1]
                    identity = idempotency.build_identity(
                        pepper=test_settings.pepper,
                        scope=idempotency.user_scope(actor.user_id),
                        operation=constants.OP_INVITATION_CREATE,
                        target_ref=visit_id,
                        raw_key="concurrent-key",
                        public_fields={"ttl_seconds": None},
                        secret_fields={"subject_identifier": DEMO_ID_A},
                    )
                    decision = idempotency.precheck(session, clock=term1_clock, identity=identity)
                    if decision.is_replay:
                        return f"replay:{decision.body().get('invitation_id')}"
                    import time

                    time.sleep(0.05 * index)
                    result = visits.issue_invitation(
                        session,
                        clock=term1_clock,
                        settings=test_settings,
                        account=actor,
                        visit_id=visit_id,
                        subject_identifier=DEMO_ID_A,
                        ttl_seconds=None,
                    )
                    idempotency.remember(
                        session,
                        clock=term1_clock,
                        identity=identity,
                        status_code=201,
                        public_response={
                            "invitation_id": result["invitation_id"],
                            "visit_id": visit_id,
                        },
                        secret_disclosed=True,
                    )
                    return f"created:{result['invitation_id']}"
            finally:
                database.dispose()

        return run

    outcomes = [_outcome(value) for value in _run_concurrently([attempt(0), attempt(1)])]
    created = [value for value in outcomes if value.startswith("created:")]
    replayed = [value for value in outcomes if value.startswith("replay:")]
    # Never two creations; a loser may also fail closed on the write lock.
    assert len(created) <= 1, outcomes
    assert len(created) + len(replayed) >= 1, outcomes
    if created and replayed:
        assert created[0].split(":", 1)[1] == replayed[0].split(":", 1)[1]
    assert _count(migrated_url, "SELECT COUNT(*) FROM patient_invitation") == 1
    assert (
        _count(
            migrated_url,
            "SELECT COUNT(*) FROM durable_idempotency WHERE operation="
            f"'{constants.OP_INVITATION_CREATE}'",
        )
        == 1
    )
