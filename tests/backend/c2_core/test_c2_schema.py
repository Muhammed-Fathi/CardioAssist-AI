"""C2.1 schema verification: frozen trigger inventory and fail-closed checks.

Migration ``20261128_07`` and ``backend.app.term1.triggers`` both carry the
twelve C2 trigger definitions; this suite pins the fresh-upgrade
``sqlite_master`` output against the frozen dictionary (single drift guard)
and proves ``Database.verify_schema()`` refuses startup when a trigger is
missing or modified, while accepting an untouched head database.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from backend.app.storage.database import Database
from backend.app.term1.triggers import C2_TRIGGER_DEFINITIONS, normalize_trigger_sql


def _trigger_map(url: str) -> dict[str, str]:
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            rows = connection.exec_driver_sql(
                "SELECT name, sql FROM sqlite_master WHERE type='trigger'"
            ).fetchall()
            return {
                str(name): normalize_trigger_sql(str(sql or ""))
                for name, sql in rows
            }
    finally:
        engine.dispose()


def test_fresh_upgrade_creates_exactly_the_frozen_c2_trigger_set(migrated_database_url):
    actual = _trigger_map(migrated_database_url)
    expected = {
        name: normalize_trigger_sql(sql)
        for name, sql in C2_TRIGGER_DEFINITIONS.items()
    }
    # Exactly the twelve 07 triggers exist anywhere in the database (legacy C1
    # and monitoring tables own none), and every statement matches.
    assert set(actual) == set(expected) == {
        "tr_health_profile_immutable_update",
        "tr_health_profile_no_delete",
        "tr_snapshot_no_update",
        "tr_snapshot_no_delete",
        "tr_assessment_scope_insert",
        "tr_assessment_pointer_insert",
        "tr_assessment_pointer_update",
        "tr_assessment_no_delete",
        "tr_attempt_transition_guard",
        "tr_attempt_no_delete",
        "tr_result_no_update",
        "tr_result_no_delete",
    }
    assert actual == expected


def test_startup_verification_accepts_an_untouched_head_database(migrated_database_url):
    database = Database(migrated_database_url)
    try:
        database.verify_schema()  # complete, unmodified head: no exception
    finally:
        database.dispose()


def test_startup_verification_refuses_a_missing_c2_trigger(migrated_database_url):
    engine = create_engine(migrated_database_url)
    with engine.begin() as connection:
        connection.exec_driver_sql('DROP TRIGGER "tr_result_no_delete"')
    engine.dispose()

    database = Database(migrated_database_url)
    try:
        with pytest.raises(RuntimeError, match="tr_result_no_delete missing"):
            database.verify_schema()
    finally:
        database.dispose()


def test_startup_verification_refuses_a_modified_c2_trigger(migrated_database_url):
    engine = create_engine(migrated_database_url)
    with engine.begin() as connection:
        connection.exec_driver_sql('DROP TRIGGER "tr_result_no_delete"')
        connection.exec_driver_sql(
            "CREATE TRIGGER tr_result_no_delete "
            "BEFORE DELETE ON inference_result FOR EACH ROW "
            "BEGIN SELECT RAISE(ABORT, 'tampered'); END"
        )
    engine.dispose()

    database = Database(migrated_database_url)
    try:
        with pytest.raises(RuntimeError, match="tr_result_no_delete modified"):
            database.verify_schema()
    finally:
        database.dispose()


def test_c2_trigger_failures_never_modify_the_database(migrated_database_url):
    """Verification is read-only: a refused startup leaves rows and DDL intact."""
    engine = create_engine(migrated_database_url)
    with engine.begin() as connection:
        connection.exec_driver_sql('DROP TRIGGER "tr_snapshot_no_delete"')
    engine.dispose()

    before = _trigger_map(migrated_database_url)
    database = Database(migrated_database_url)
    try:
        with pytest.raises(RuntimeError, match="tr_snapshot_no_delete missing"):
            database.verify_schema()
    finally:
        database.dispose()
    assert _trigger_map(migrated_database_url) == before
    with create_engine(migrated_database_url).connect() as connection:
        assert connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one() == "20261128_07"
