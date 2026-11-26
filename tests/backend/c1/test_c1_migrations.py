"""C1.1 migration foundation: schema, ordering, preservation and startup checks."""

from __future__ import annotations

import pathlib
import re

import pytest
from alembic import command
from sqlalchemy import create_engine, inspect, text

from backend.app.storage.database import Database, _expected_migration_heads
from backend.app.term1.models import Base
from tests.backend.c1.conftest import alembic_config, downgrade, upgrade

LEGACY_TABLES = {"monitoring_observation", "monitoring_metric", "audit_event"}
C1_TABLES = {
    "user_account",
    "doctor_profile",
    "patient_identity",
    "patient_profile",
    "identity_key_check",
    "session",
    "login_attempt",
    "verified_visit",
    "patient_invitation",
    "invitation_attempt",
    "doctor_patient_assignment",
    "consent_record",
    "invitation_redemption",
    "durable_idempotency",
    "workflow_audit_event",
    "admin_bootstrap_record",
}
C2_C3_TABLES = {
    "health_profile",
    "assessment",
    "assessment_snapshot",
    "inference_attempt",
    "inference_result",
    "assessment_review",
    "follow_up_message",
    "notification_record",
}

REVISION_ORDER = [
    "20261017_01",
    "20261126_02",
    "20261126_03",
    "20261126_04",
    "20261126_05",
    "20261126_06",
]


def _tables(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_migration_head_graph_is_the_documented_c1_chain(migrated_url):
    assert _expected_migration_heads() == ("20261126_06",)
    config = alembic_config(migrated_url)
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(config)
    order = []
    revision = script.get_current_head()
    while revision is not None:
        order.append(revision)
        obj = script.get_revision(revision)
        revision = obj.down_revision
    assert list(reversed(order)) == REVISION_ORDER


def test_legacy_migration_is_unchanged_and_preserved(migrated_url):
    engine = create_engine(migrated_url)
    try:
        inspector = inspect(engine)
        assert LEGACY_TABLES <= set(inspector.get_table_names())
        # Exact legacy index and constraint inventory is untouched by C1.
        assert {i["name"] for i in inspector.get_indexes("monitoring_observation")} == {
            "ix_monitoring_observation_public_id",
            "ix_monitoring_observation_patient_time",
        }
        assert {i["name"] for i in inspector.get_indexes("audit_event")} == {
            "ix_audit_event_public_id",
            "ix_audit_event_recorded_at",
        }
        assert inspector.get_foreign_keys("audit_event")[0]["referred_table"] == (
            "monitoring_observation"
        )
    finally:
        engine.dispose()


def test_c1_inventory_is_exact_and_no_later_stage_table_exists(migrated_url):
    tables = _tables(migrated_url)
    assert C1_TABLES <= tables
    assert not (C2_C3_TABLES & tables), sorted(C2_C3_TABLES & tables)
    # Every declared table is mapped; nothing is created outside Base.metadata.
    assert tables - {"alembic_version"} == set(Base.metadata.tables)


def test_referenced_tables_are_created_before_dependents():
    """Each migration revision only references tables from earlier revisions."""
    from alembic.script import ScriptDirectory

    from tests.backend.c1.conftest import alembic_config

    script = ScriptDirectory.from_config(alembic_config("sqlite://"))
    declared: dict[str, set[str]] = {}
    for revision in script.walk_revisions():
        source = (pathlib.Path(revision.path)).read_text(encoding="utf-8")
        declared[revision.revision] = set(
            re.findall(r'op\.create_table\(\s*\n?\s*"([a-z_]+)"', source)
        )
    order = ["20261017_01", "20261126_02", "20261126_03", "20261126_04", "20261126_05", "20261126_06"]
    assert list(declared) == list(reversed(order)) or set(declared) == set(order)
    seen: set[str] = set()
    for revision in order:
        # The legacy revision references nothing (its FKs are intra-revision, and
        # the first table it creates is the FK target of the others).
        created = declared[revision]
        source = pathlib.Path(script.get_revision(revision).path).read_text(encoding="utf-8")
        referenced = set(re.findall(r"sa\.ForeignKeyConstraint\(\s*\[[^\]]*\],\s*\[\s*\"([a-z_]+)\.", source))
        missing = (referenced - seen) - declared[revision]
        assert not missing, (revision, sorted(missing))
        seen |= created


def test_foreign_keys_and_uniqueness_constraints_are_enforced(migrated_url):
    engine = create_engine(migrated_url)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            # UNIQUE(email_norm)
            connection.exec_driver_sql(
                "INSERT INTO user_account VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "u1", "a@cardioassist.local", "admin", "ACTIVE", "pbkdf2_hmac_sha256",
                    1, 1, "s", "v", 0, None, "t", None, None, None,
                ),
            )
            with pytest.raises(Exception):
                connection.exec_driver_sql(
                    "INSERT INTO user_account VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        "u2", "a@cardioassist.local", "admin", "ACTIVE",
                        "pbkdf2_hmac_sha256", 1, 1, "s", "v", 0, None, "t", None, None, None,
                    ),
                )
            # CHECK(role) and CHECK(status) are closed vocabularies.
            with pytest.raises(Exception):
                connection.exec_driver_sql(
                    "INSERT INTO user_account VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        "u3", "b@cardioassist.local", "superuser", "ACTIVE",
                        "pbkdf2_hmac_sha256", 1, 1, "s", "v", 0, None, "t", None, None, None,
                    ),
                )
            with pytest.raises(Exception):
                connection.exec_driver_sql(
                    "INSERT INTO user_account VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        "u4", "c@cardioassist.local", "doctor", "PENDING",
                        "pbkdf2_hmac_sha256", 1, 1, "s", "v", 0, None, "t", None, None, None,
                    ),
                )
            # Foreign keys are enforced (doctor_profile -> user_account).
            with pytest.raises(Exception):
                connection.exec_driver_sql(
                    "INSERT INTO doctor_profile VALUES (?,?,?,?,?)",
                    ("d1", "missing-user", "Dr X", 1, "t"),
                )
    finally:
        engine.dispose()


def test_invitation_cannot_be_both_consumed_and_revoked(migrated_url):
    engine = create_engine(migrated_url)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.exec_driver_sql(
                "INSERT INTO user_account VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "u1", "doc@cardioassist.local", "doctor", "ACTIVE",
                    "pbkdf2_hmac_sha256", 1, 1, "s", "v", 0, None, "t", None, None, None,
                ),
            )
            connection.exec_driver_sql(
                "INSERT INTO doctor_profile VALUES (?,?,?,?,?)", ("d1", "u1", "Dr", 1, "t")
            )
            connection.exec_driver_sql(
                "INSERT INTO verified_visit VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    "v1", "d1", "ref", "hmac", "demo-v1", "L", "t", "t",
                    "PRIOR_IN_PERSON_VISIT_DEMO", None,
                ),
            )
            with pytest.raises(Exception):
                connection.exec_driver_sql(
                    "INSERT INTO patient_invitation VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        "i1", "v1", "u1", "ver", "hmac", "demo-v1", "t", "t",
                        "t", "t", 0, 5, None, None, None,
                    ),
                )
    finally:
        engine.dispose()


def test_only_one_active_assignment_per_doctor_patient_pair(migrated_url):
    engine = create_engine(migrated_url)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.exec_driver_sql(
                "INSERT INTO user_account VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "u1", "d@cardioassist.local", "doctor", "ACTIVE",
                    "pbkdf2_hmac_sha256", 1, 1, "s", "v", 0, None, "t", None, None, None,
                ),
            )
            connection.exec_driver_sql(
                "INSERT INTO doctor_profile VALUES (?,?,?,?,?)", ("d1", "u1", "Dr", 1, "t")
            )
            connection.exec_driver_sql(
                "INSERT INTO patient_identity VALUES (?,?,?,?,?,?)",
                ("i1", "demo-v1", "h1", "c1", "L", "t"),
            )
            connection.exec_driver_sql(
                "INSERT INTO user_account VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "u2", "p@cardioassist.local", "patient", "ACTIVE",
                    "pbkdf2_hmac_sha256", 1, 1, "s", "v", 0, None, "t", None, None, None,
                ),
            )
            connection.exec_driver_sql(
                "INSERT INTO patient_profile VALUES (?,?,?,?,?)", ("p1", "u2", "i1", "L", "t")
            )
            connection.exec_driver_sql(
                "INSERT INTO doctor_patient_assignment VALUES (?,?,?,?,?,?,?,?)",
                ("a1", "d1", "p1", "t", None, None, None, None),
            )
            with pytest.raises(Exception):
                connection.exec_driver_sql(
                    "INSERT INTO doctor_patient_assignment VALUES (?,?,?,?,?,?,?,?)",
                    ("a2", "d1", "p1", "t", None, None, None, None),
                )
            # A revoked pair may be re-assigned (partial unique index).
            connection.exec_driver_sql(
                "UPDATE doctor_patient_assignment SET revoked_at='t' WHERE assignment_id='a1'"
            )
            connection.exec_driver_sql(
                "INSERT INTO doctor_patient_assignment VALUES (?,?,?,?,?,?,?,?)",
                ("a3", "d1", "p1", "t", None, None, None, None),
            )
    finally:
        engine.dispose()


def test_only_one_active_consent_per_patient(migrated_url):
    engine = create_engine(migrated_url)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.exec_driver_sql(
                "INSERT INTO user_account VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "u2", "p@cardioassist.local", "patient", "ACTIVE",
                    "pbkdf2_hmac_sha256", 1, 1, "s", "v", 0, None, "t", None, None, None,
                ),
            )
            connection.exec_driver_sql(
                "INSERT INTO patient_identity VALUES (?,?,?,?,?,?)",
                ("i1", "demo-v1", "h1", "c1", "L", "t"),
            )
            connection.exec_driver_sql(
                "INSERT INTO patient_profile VALUES (?,?,?,?,?)", ("p1", "u2", "i1", "L", "t")
            )
            values = ("cid", "p1", "synthetic_demo", "patient_wide_synthetic_demo", "t", None, None, "v")
            connection.exec_driver_sql(
                "INSERT INTO consent_record VALUES (?,?,?,?,?,?,?,?)", ("c1",) + values[1:]
            )
            with pytest.raises(Exception):
                connection.exec_driver_sql(
                    "INSERT INTO consent_record VALUES (?,?,?,?,?,?,?,?)", ("c2",) + values[1:]
                )
    finally:
        engine.dispose()


def test_legacy_rows_survive_upgrade_to_c1(migrated_url):
    """A database populated at the legacy revision keeps its monitoring rows."""
    url = migrated_url
    downgrade(url, "20261017_01")
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.exec_driver_sql(
                "INSERT INTO monitoring_observation VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    "r1", "o1", "req1", "patient_legacy", "consent_legacy",
                    "2026-10-16T10:25:00Z", "simulated_wearable", None,
                    "2026-10-16T10:25:01Z",
                ),
            )
            connection.exec_driver_sql(
                "INSERT INTO monitoring_metric VALUES (?,?,?,?,?,?,?,?)",
                ("m1", "r1", 0, "mock_metric_heart_rate", "64", "u_rate", None, None),
            )
            connection.exec_driver_sql(
                "INSERT INTO audit_event VALUES (?,?,?,?,?,?,?,?)",
                (
                    "a1", "r1", "o1", "monitoring.observation.recorded",
                    "/v1/monitoring/observations", "req1", "0" * 64,
                    "2026-10-16T10:25:02Z",
                ),
            )
    finally:
        engine.dispose()

    upgrade(url, "head")
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT patient_ref FROM monitoring_observation")
            ).scalar_one() == "patient_legacy"
            assert connection.execute(text("SELECT COUNT(*) FROM monitoring_metric")).scalar_one() == 1
            assert connection.execute(text("SELECT COUNT(*) FROM audit_event")).scalar_one() == 1
            # C1 workflow audit is a separate table and stays empty.
            assert connection.execute(
                text("SELECT COUNT(*) FROM workflow_audit_event")
            ).scalar_one() == 0
    finally:
        engine.dispose()
    Database(url).verify_schema()


def test_disposable_downgrade_and_reupgrade_preserves_legacy_data(migrated_url):
    url = migrated_url
    downgrade(url, "20261017_01")
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.exec_driver_sql(
                "INSERT INTO monitoring_observation VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    "r1", "o1", "req1", "patient_keep", "consent", "2026-10-16T10:25:00Z",
                    "simulated_wearable", None, "2026-10-16T10:25:01Z",
                ),
            )
    finally:
        engine.dispose()
    upgrade(url, "head")
    # Legacy data must be readable after the C1 upgrade.
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT patient_ref FROM monitoring_observation")
            ).scalar_one() == "patient_keep"
    finally:
        engine.dispose()

    # Downgrade on a *disposable* database: only the C1 revisions are removed and
    # the legacy monitoring data survives the round trip.
    downgrade(url, "20261017_01")
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT patient_ref FROM monitoring_observation")
            ).scalar_one() == "patient_keep"
        assert not (C1_TABLES & _tables(url))
    finally:
        engine.dispose()
    upgrade(url, "head")
    database = Database(url)
    try:
        database.verify_schema()
    finally:
        database.dispose()
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT patient_ref FROM monitoring_observation")
            ).scalar_one() == "patient_keep"
    finally:
        engine.dispose()


def test_alembic_check_reports_no_drift(migrated_url):
    from tests.backend.c1.conftest import alembic_check

    alembic_check(migrated_url)


@pytest.mark.parametrize(
    "mutation",
    [
        "DROP TABLE workflow_audit_event",
        "DROP INDEX ix_workflow_audit_subject_time",
        "DROP TABLE identity_key_check",
    ],
)
def test_startup_verification_rejects_missing_c1_schema(migrated_url, mutation):
    engine = create_engine(migrated_url)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            connection.exec_driver_sql(mutation)
    finally:
        engine.dispose()
    database = Database(migrated_url)
    try:
        with pytest.raises(RuntimeError):
            database.verify_schema()
    finally:
        database.dispose()


def test_startup_verification_rejects_wrong_database_collation_of_columns(migrated_url):
    """A removed C1 column is schema drift and must fail closed, not self-heal."""
    engine = create_engine(migrated_url)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "ALTER TABLE user_account DROP COLUMN password_change_required"
            )
    finally:
        engine.dispose()
    database = Database(migrated_url)
    try:
        with pytest.raises(RuntimeError, match="incompatible"):
            database.verify_schema()
    finally:
        database.dispose()


def test_startup_verification_is_read_only(migrated_url):
    database = Database(migrated_url)
    try:
        database.verify_schema()
        database.verify_schema()
    finally:
        database.dispose()
    # No repair happened: alembic head and table inventory are unchanged.
    assert _expected_migration_heads() == ("20261126_06",)
    assert C1_TABLES <= _tables(migrated_url)


def test_timestamps_and_digests_are_stored_as_text_not_numbers(migrated_url):
    """Regression for the Windows SQLite numeric-parsing defect seen in C0.

    Fixed-width timestamp text and 64-hex digests must round-trip byte-exactly and
    must never be interpreted as numeric values by a report/export path.
    """
    engine = create_engine(migrated_url)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.exec_driver_sql(
                "INSERT INTO user_account VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "u1", "typed@cardioassist.local", "admin", "ACTIVE",
                    "pbkdf2_hmac_sha256", 1, 600000, "c2FsdA==", "dmVyaWZpZXI=", 0,
                    None, "2026-11-26T09:00:00.000000Z", None, None, None,
                ),
            )
            row = connection.execute(
                text("SELECT typeof(created_at), created_at, typeof(email_norm) FROM user_account")
            ).one()
    finally:
        engine.dispose()
    assert row[0] == "text"
    assert row[1] == "2026-11-26T09:00:00.000000Z"
    assert row[2] == "text"
