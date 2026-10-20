"""M1b.1 SQLite migrations and monitoring persistence integration tests."""

from __future__ import annotations

import copy
import sqlite3
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy import event as sqlalchemy_event
from sqlalchemy.exc import IntegrityError

from backend.app.main import create_app
from backend.app.storage.database import Database
from backend.app.storage.models import AuditEvent, MonitoringMetric

ROOT = Path(__file__).resolve().parents[2]
MON = "/v1/monitoring/observations"
CAD = "/v1/predictions/cad-tabular"
KEY = {"Idempotency-Key": "m1b1-monitoring-write-001"}


def _alembic_config(database_url: str) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.attributes["database_url"] = database_url
    return config


def _upgrade(database_url: str) -> None:
    command.upgrade(_alembic_config(database_url), "head")


def test_unmigrated_database_fails_closed_with_actionable_error(database_url):
    database = Database(database_url)
    try:
        with pytest.raises(RuntimeError, match="alembic upgrade head"):
            database.verify_schema()
    finally:
        database.dispose()


@pytest.mark.parametrize("revision", ["20261016_00", "unknown_revision"])
def test_database_rejects_outdated_or_unknown_alembic_revision(database_url, revision):
    _upgrade(database_url)
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "UPDATE alembic_version SET version_num = ?", (revision,)
            )
    finally:
        engine.dispose()

    database = Database(database_url)
    try:
        with pytest.raises(RuntimeError, match="Alembic revision mismatch") as error:
            database.verify_schema()
        assert "20261017_01" in str(error.value)
        assert revision in str(error.value)
    finally:
        database.dispose()


def test_database_rejects_empty_alembic_revision_table(database_url):
    _upgrade(database_url)
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("DELETE FROM alembic_version")
    finally:
        engine.dispose()

    database = Database(database_url)
    try:
        with pytest.raises(RuntimeError, match="Alembic revision mismatch") as error:
            database.verify_schema()
        assert "found: <none>" in str(error.value)
    finally:
        database.dispose()


def test_database_rejects_missing_column_and_critical_index(database_url):
    _upgrade(database_url)
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "ALTER TABLE monitoring_observation DROP COLUMN source_detail"
            )
            connection.exec_driver_sql("DROP INDEX ix_monitoring_metric_metric_id")
    finally:
        engine.dispose()

    database = Database(database_url)
    try:
        with pytest.raises(RuntimeError, match="schema is incompatible") as error:
            database.verify_schema()
        message = str(error.value)
        assert "add_column monitoring_observation.source_detail" in message
        assert "add_index ix_monitoring_metric_metric_id" in message
    finally:
        database.dispose()


def test_database_rejects_missing_primary_key_constraint(database_url):
    _upgrade(database_url)
    database_path = Path(database_url.removeprefix("sqlite:///"))
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("DROP TABLE monitoring_metric")
        connection.execute(
            """
            CREATE TABLE monitoring_metric (
                metric_record_id VARCHAR(36) NOT NULL,
                observation_record_id VARCHAR(36) NOT NULL,
                ordinal INTEGER NOT NULL,
                metric_id VARCHAR(64) NOT NULL,
                value_json JSON NOT NULL,
                unit VARCHAR(32) NOT NULL,
                recorded_at VARCHAR(40),
                quality_note VARCHAR(200),
                FOREIGN KEY (observation_record_id)
                    REFERENCES monitoring_observation(record_id) ON DELETE RESTRICT,
                CONSTRAINT uq_monitoring_metric_observation_ordinal
                    UNIQUE (observation_record_id, ordinal)
            )
            """
        )
        connection.execute(
            "CREATE INDEX ix_monitoring_metric_observation "
            "ON monitoring_metric (observation_record_id)"
        )
        connection.execute(
            "CREATE INDEX ix_monitoring_metric_metric_id "
            "ON monitoring_metric (metric_id)"
        )

    database = Database(database_url)
    try:
        with pytest.raises(RuntimeError, match="primary_key monitoring_metric"):
            database.verify_schema()
    finally:
        database.dispose()


def test_database_rejects_missing_foreign_key_and_unique_constraints(database_url):
    _upgrade(database_url)
    database_path = Path(database_url.removeprefix("sqlite:///"))
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("DROP TABLE monitoring_metric")
        connection.execute(
            """
            CREATE TABLE monitoring_metric (
                metric_record_id VARCHAR(36) NOT NULL PRIMARY KEY,
                observation_record_id VARCHAR(36) NOT NULL,
                ordinal INTEGER NOT NULL,
                metric_id VARCHAR(64) NOT NULL,
                value_json JSON NOT NULL,
                unit VARCHAR(32) NOT NULL,
                recorded_at VARCHAR(40),
                quality_note VARCHAR(200)
            )
            """
        )
        connection.execute(
            "CREATE INDEX ix_monitoring_metric_observation "
            "ON monitoring_metric (observation_record_id)"
        )
        connection.execute(
            "CREATE INDEX ix_monitoring_metric_metric_id "
            "ON monitoring_metric (metric_id)"
        )

    database = Database(database_url)
    try:
        with pytest.raises(RuntimeError, match="schema is incompatible") as error:
            database.verify_schema()
        assert "add_constraint uq_monitoring_metric_observation_ordinal" in str(error.value)
        assert "add_fk" in str(error.value)
    finally:
        database.dispose()


def test_database_rejects_existing_foreign_key_violations(database_url):
    _upgrade(database_url)
    database_path = Path(database_url.removeprefix("sqlite:///"))
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            """
            INSERT INTO monitoring_metric (
                metric_record_id, observation_record_id, ordinal, metric_id,
                value_json, unit, recorded_at, quality_note
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                str(uuid.uuid4()),
                0,
                "mock_metric_heart_rate",
                "64",
                "u_rate",
                None,
                None,
            ),
        )

    database = Database(database_url)
    try:
        with pytest.raises(RuntimeError, match="foreign-key integrity check failed"):
            database.verify_schema()
    finally:
        database.dispose()


def test_fastapi_lifespan_fails_without_automatically_migrating(database_url):
    app = create_app(database_url=database_url)
    with pytest.raises(RuntimeError, match="missing required tables"):
        with TestClient(app):
            pytest.fail("An unmigrated database must not start the application.")

    engine = create_engine(database_url)
    try:
        assert inspect(engine).get_table_names() == []
    finally:
        engine.dispose()


def test_fastapi_lifespan_rejects_malformed_schema_without_repairing(database_url):
    _upgrade(database_url)
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "ALTER TABLE monitoring_observation DROP COLUMN source_detail"
            )
    finally:
        engine.dispose()

    app = create_app(database_url=database_url)
    with pytest.raises(RuntimeError, match="schema is incompatible"):
        with TestClient(app):
            pytest.fail("A malformed schema must not start the application.")

    engine = create_engine(database_url)
    try:
        column_names = {
            column["name"]
            for column in inspect(engine).get_columns("monitoring_observation")
        }
        assert "source_detail" not in column_names
    finally:
        engine.dispose()


def test_configured_database_url_is_shared_by_alembic_and_application(tmp_path, monkeypatch):
    database_path = tmp_path / "configured" / "cardioassist.sqlite3"
    database_url = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("CARDIOASSIST_DATABASE_URL", database_url)

    command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
    database = Database()
    try:
        assert database.url == database_url
        database.verify_schema()
    finally:
        database.dispose()


def test_fresh_migration_creates_expected_tables_indexes_and_foreign_keys(database_url):
    config = _alembic_config(database_url)
    command.upgrade(config, "head")
    command.upgrade(config, "head")  # Re-applying head is a safe no-op.
    command.check(config)  # Migration schema and SQLAlchemy metadata agree.

    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        assert set(inspector.get_table_names()) == {
            "alembic_version",
            "monitoring_observation",
            "monitoring_metric",
            "audit_event",
        }
        assert {item["name"] for item in inspector.get_indexes("monitoring_observation")} == {
            "ix_monitoring_observation_public_id",
            "ix_monitoring_observation_patient_time",
        }
        assert {item["name"] for item in inspector.get_indexes("monitoring_metric")} == {
            "ix_monitoring_metric_observation",
            "ix_monitoring_metric_metric_id",
        }
        assert {item["name"] for item in inspector.get_indexes("audit_event")} == {
            "ix_audit_event_public_id",
            "ix_audit_event_recorded_at",
        }
        assert inspector.get_foreign_keys("monitoring_metric")[0]["referred_table"] == "monitoring_observation"
        assert inspector.get_foreign_keys("audit_event")[0]["referred_table"] == "monitoring_observation"
        assert {item["name"] for item in inspector.get_unique_constraints("monitoring_metric")} == {
            "uq_monitoring_metric_observation_ordinal",
        }
        assert {item["name"] for item in inspector.get_unique_constraints("audit_event")} == {
            "uq_audit_event_observation_record",
        }
    finally:
        engine.dispose()

    database = Database(database_url)
    try:
        database.verify_schema()
    finally:
        database.dispose()


def test_migrations_downgrade_and_reupgrade_only_on_disposable_test_database(database_url):
    config = _alembic_config(database_url)
    command.upgrade(config, "head")
    command.downgrade(config, "base")

    engine = create_engine(database_url)
    try:
        names = set(inspect(engine).get_table_names())
        assert not {"monitoring_observation", "monitoring_metric", "audit_event"} & names
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    command.check(config)


def test_monitoring_post_persists_readable_rows_and_append_only_audit(
    client, http_app, monitoring_body
):
    body = copy.deepcopy(monitoring_body)
    body["observation"]["metrics"] = [
        {
            "metric_id": "mock_metric_heart_rate",
            "value": 64,
            "unit": "u_rate",
            "recorded_at": "2026-10-16T10:25:01Z",
            "quality_note": "synthetic demo value",
        },
        {"metric_id": "mock_metric_heart_rate", "value": None, "unit": "u_rate"},
        {"metric_id": "mock_metric_steps", "value": 0, "unit": "u_count"},
        {"metric_id": "mock_metric_sleep_minutes", "value": False, "unit": "u_duration_min"},
        {"metric_id": "mock_metric_spo2", "value": "synthetic-string", "unit": "u_fraction"},
    ]

    response = client.post(MON, json=body, headers=KEY)
    assert response.status_code == 201
    assert response.json()["recorded_metric_count"] == 4
    assert not {"score", "target", "explanation"} & response.json().keys()

    repository = http_app.state.monitoring_repository
    rows = repository.list_observations()
    audit = repository.list_audit_events()
    assert len(rows) == len(audit) == 1
    stored = repository.get_by_record_id(rows[0].record_id)
    assert stored == rows[0]
    assert stored.observation_id == response.json()["observation_id"]
    assert stored.request_id == response.json()["request_id"]
    assert stored.patient_ref == "pseudo_http_demo"
    assert stored.consent_id == "consent_mock_http_demo"
    assert stored.source == "simulated_wearable"
    assert stored.observed_at == "2026-10-16T10:25:00.000000Z"
    assert [metric.ordinal for metric in stored.metrics] == [0, 2, 3, 4]
    assert [metric.value for metric in stored.metrics] == [64, 0, False, "synthetic-string"]
    assert stored.metrics[0].recorded_at == "2026-10-16T10:25:01.000000Z"
    assert stored.metrics[0].quality_note == "synthetic demo value"

    event = audit[0]
    assert event.observation_record_id == stored.record_id
    assert event.event_id == response.json()["observation_id"]
    assert event.event_type == "observation_recorded"
    assert event.path == MON
    assert len(event.payload_sha256) == 64
    assert not hasattr(event, "patient_ref")
    assert not hasattr(event, "metrics")


def test_keyed_replay_does_not_duplicate_durable_rows_or_audit(client, http_app, monitoring_body):
    first = client.post(MON, json=monitoring_body, headers=KEY)
    replay = client.post(MON, json=monitoring_body, headers=KEY)
    assert first.status_code == replay.status_code == 201
    assert first.json()["idempotent_replay"] is False
    assert replay.json()["idempotent_replay"] is True
    assert replay.json()["observation_id"] == first.json()["observation_id"]
    assert len(http_app.state.monitoring_repository.list_observations()) == 1
    assert len(http_app.state.monitoring_repository.list_audit_events()) == 1


def test_write_transaction_rolls_back_observation_metrics_and_audit_on_failure(
    client, http_app, monitoring_body
):
    engine = http_app.state.database.engine

    def fail_audit_insert(_connection, _cursor, statement, _parameters, _context, _executemany):
        if "insert into audit_event" in statement.lower():
            raise RuntimeError("synthetic injected database failure")

    sqlalchemy_event.listen(engine, "before_cursor_execute", fail_audit_insert)
    try:
        failed = client.post(MON, json=monitoring_body, headers=KEY)
    finally:
        sqlalchemy_event.remove(engine, "before_cursor_execute", fail_audit_insert)

    assert failed.status_code == 500
    assert failed.json()["error"]["code"] == "internal_error"
    repository = http_app.state.monitoring_repository
    assert repository.list_observations() == ()
    assert repository.list_audit_events() == ()
    # A failed write did not consume the runtime key or publish a success event.
    assert len(http_app.state.mock.audit_events) == 1
    assert http_app.state.mock.audit_events[0].event_type == "internal_error"

    retried = client.post(MON, json=monitoring_body, headers=KEY)
    assert retried.status_code == 201
    assert retried.json()["idempotent_replay"] is False
    assert len(repository.list_observations()) == 1
    assert len(repository.list_audit_events()) == 1


@pytest.mark.parametrize(
    ("mutation", "status", "code"),
    [
        ("missing_consent", 422, "consent_required"),
        ("unknown_metric", 422, "unknown_metric"),
        ("wrong_unit", 422, "unit_mismatch"),
        ("out_of_range", 422, "value_out_of_range"),
        ("invalid_source", 400, "malformed_request"),
    ],
)
def test_rejected_monitoring_requests_never_reach_storage(
    client, http_app, monitoring_body, mutation, status, code
):
    body = copy.deepcopy(monitoring_body)
    observation = body["observation"]
    if mutation == "missing_consent":
        observation["consent_id"] = ""
    elif mutation == "unknown_metric":
        observation["metrics"][0]["metric_id"] = "mock_metric_unknown"
    elif mutation == "wrong_unit":
        observation["metrics"][0]["unit"] = "u_wrong"
    elif mutation == "out_of_range":
        observation["metrics"][0]["value"] = 301
    elif mutation == "invalid_source":
        observation["source"] = "unreviewed_source"

    response = client.post(MON, json=body, headers=KEY)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert http_app.state.monitoring_repository.list_observations() == ()
    assert http_app.state.monitoring_repository.list_audit_events() == ()


def test_malformed_json_and_track_a_writes_do_not_touch_monitoring_storage(
    client, http_app, cad_body
):
    malformed = client.post(
        MON,
        content=b'{"observation":',
        headers={"Content-Type": "application/json", **KEY},
    )
    assert malformed.status_code == 400
    assert malformed.json()["error"]["code"] == "malformed_request"

    cad_response = client.post(CAD, json=cad_body, headers=KEY)
    assert cad_response.status_code == 200
    assert http_app.state.monitoring_repository.list_observations() == ()
    assert http_app.state.monitoring_repository.list_audit_events() == ()


def test_sqlite_foreign_key_and_uniqueness_constraints_fail_closed(
    client, http_app, monitoring_body
):
    database = http_app.state.database
    with database.engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1

    with pytest.raises(IntegrityError):
        with database.transaction() as session:
            session.add(
                MonitoringMetric(
                    metric_record_id=str(uuid.uuid4()),
                    observation_record_id=str(uuid.uuid4()),
                    ordinal=0,
                    metric_id="mock_metric_heart_rate",
                    value_json=64,
                    unit="u_rate",
                )
            )

    accepted = client.post(MON, json=monitoring_body, headers=KEY)
    assert accepted.status_code == 201
    stored = http_app.state.monitoring_repository.list_observations()[0]
    existing_metric = stored.metrics[0]

    with pytest.raises(IntegrityError):
        with database.transaction() as session:
            session.add(
                MonitoringMetric(
                    metric_record_id=str(uuid.uuid4()),
                    observation_record_id=stored.record_id,
                    ordinal=existing_metric.ordinal,
                    metric_id=existing_metric.metric_id,
                    value_json=existing_metric.value,
                    unit=existing_metric.unit,
                )
            )

    with pytest.raises(IntegrityError):
        with database.transaction() as session:
            session.add(
                AuditEvent(
                    audit_record_id=str(uuid.uuid4()),
                    observation_record_id=stored.record_id,
                    event_id=stored.observation_id,
                    event_type="observation_recorded",
                    path=MON,
                    request_id=stored.request_id,
                    payload_sha256="0" * 64,
                    recorded_at=stored.recorded_at,
                )
            )

    assert len(http_app.state.monitoring_repository.list_observations()) == 1
    assert len(http_app.state.monitoring_repository.list_audit_events()) == 1


def test_two_migrated_test_databases_are_isolated(tmp_path, monitoring_body):
    database_a = f"sqlite:///{(tmp_path / 'first' / 'cardioassist.sqlite3').as_posix()}"
    database_b = f"sqlite:///{(tmp_path / 'second' / 'cardioassist.sqlite3').as_posix()}"
    _upgrade(database_a)
    _upgrade(database_b)
    app_a = create_app(database_url=database_a)
    app_b = create_app(database_url=database_b)
    body_a = copy.deepcopy(monitoring_body)
    body_b = copy.deepcopy(monitoring_body)
    body_a["observation"]["patient_ref"] = "pseudo_isolation_a"
    body_b["observation"]["patient_ref"] = "pseudo_isolation_b"

    with TestClient(app_a) as client_a, TestClient(app_b) as client_b:
        assert client_a.post(MON, json=body_a).status_code == 201
        assert client_b.post(MON, json=body_b).status_code == 201

    rows_a = app_a.state.monitoring_repository.list_observations()
    rows_b = app_b.state.monitoring_repository.list_observations()
    assert len(rows_a) == len(rows_b) == 1
    assert rows_a[0].patient_ref == "pseudo_isolation_a"
    assert rows_b[0].patient_ref == "pseudo_isolation_b"
    assert rows_a[0].record_id != rows_b[0].record_id
