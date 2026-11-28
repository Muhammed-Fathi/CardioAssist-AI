"""C2 schema verification: combined 07/08 trigger inventory and fail-closed checks.

The integrated 06→07→08 chain has fifteen clinical-core triggers and thirteen
Document/OCR triggers. Startup pins all 28 fresh-upgrade ``sqlite_master``
statements against their frozen sources and refuses missing or modified DDL.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from backend.app.storage.database import Database
from backend.app.term1.triggers import C2_TRIGGER_DEFINITIONS, normalize_trigger_sql
from backend.app.term1_c2_documents.triggers import (
    ASSESSMENT_SCOPE_TRIGGER_OVERRIDE,
    DOCUMENT_TRIGGER_DEFINITIONS,
)


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


def test_fresh_integrated_upgrade_creates_exactly_28_frozen_triggers(migrated_database_url):
    actual = _trigger_map(migrated_database_url)
    definitions = C2_TRIGGER_DEFINITIONS | DOCUMENT_TRIGGER_DEFINITIONS
    definitions["tr_assessment_scope_insert"] = ASSESSMENT_SCOPE_TRIGGER_OVERRIDE
    expected = {
        name: normalize_trigger_sql(sql) for name, sql in definitions.items()
    }
    assert len(C2_TRIGGER_DEFINITIONS) == 15
    assert len(DOCUMENT_TRIGGER_DEFINITIONS) == 13
    assert (
        ASSESSMENT_SCOPE_TRIGGER_OVERRIDE
        != C2_TRIGGER_DEFINITIONS["tr_assessment_scope_insert"]
    )
    # The 08 migration replaces one core guard and adds thirteen DOC triggers:
    # the live 28-name inventory is exact, with no unreviewed extras.
    assert len(expected) == 28
    assert set(actual) == set(expected)
    assert actual == expected


def test_assessment_review_and_terminal_reason_constraints_are_closed(migrated_database_url):
    engine = create_engine(migrated_database_url)
    try:
        with engine.connect() as connection:
            assessment_sql = connection.exec_driver_sql(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='assessment'"
            ).scalar_one()
            attempt_sql = connection.exec_driver_sql(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='inference_attempt'"
            ).scalar_one()
    finally:
        engine.dispose()

    assert "review_state = 'NOT_REVIEWED'" in assessment_sql
    assert "review_version = 0" in assessment_sql
    assessment_reason_check = assessment_sql.split("ck_assessment_status_reason", 1)[1]
    attempt_reason_check = attempt_sql.split("ck_inference_attempt_state_reason", 1)[1]
    assert "reason_code IS NOT NULL" in assessment_reason_check
    assert "reason_code IS NOT NULL" in attempt_reason_check


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
        ).scalar_one() == "20261128_08"
