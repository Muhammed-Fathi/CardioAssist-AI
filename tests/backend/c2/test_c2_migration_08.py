"""Migration 20261128_08 upgrade/downgrade behavior (disposable harness).

The full alembic ``06 → 07 → 08`` chain upgrade/downgrade is an integration
checkpoint pending Track 1's ``20261128_07``. These tests exercise the migration's
own ``upgrade()``/``downgrade()`` callables directly through a bound
``alembic.operations.Operations`` so the DDL, the thirteen triggers and the RB-C1
downgrade guard are genuinely verified without alembic head resolution.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text

from backend.app.storage.models import Base
import backend.app.term1.models  # noqa: F401
import backend.app.term1_c2_documents.models  # noqa: F401 - metadata registration

MIGRATION = Path(__file__).resolve().parents[3] / "backend" / "migrations" / "versions" / "20261128_08_c2_documents_ocr.py"
C2_TABLES = {"medical_document", "document_extraction", "extraction_field",
             "extraction_event", "assessment_document", "document_inflight_operation"}


def _load_migration():
    spec = importlib.util.spec_from_file_location("mig08_test", MIGRATION)
    mig = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mig)
    return mig


def _bind(engine, mig, *, as_sql=False):
    conn = engine.connect()
    ctx = MigrationContext.configure(conn, opts={"as_sql": as_sql})
    mig.op = Operations(ctx)
    return conn, ctx


def test_upgrade_creates_six_tables_and_thirteen_triggers(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'm.sqlite3').as_posix()}")
    c1_tables = [t for n, t in Base.metadata.tables.items() if n not in C2_TABLES]
    Base.metadata.create_all(engine, tables=c1_tables)
    mig = _load_migration()
    conn, _ = _bind(engine, mig)
    try:
        mig.upgrade()
        conn.commit()
        tables = {r[0] for r in conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table'"))}
        triggers = {r[0] for r in conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='trigger'"))}
        assert C2_TABLES.issubset(tables)
        assert len(triggers) == 13
        assert set(mig.TRIGGER_DEFINITIONS).issubset(triggers)
    finally:
        conn.close()
        engine.dispose()


def test_downgrade_refuses_populated_database(tmp_path, ):
    # A populated C1 table trips the RB-C1 guard before any drop occurs.
    engine = create_engine(f"sqlite:///{(tmp_path / 'm.sqlite3').as_posix()}")
    c1_tables = [t for n, t in Base.metadata.tables.items() if n not in C2_TABLES]
    Base.metadata.create_all(engine, tables=c1_tables)
    mig = _load_migration()
    conn, _ = _bind(engine, mig)
    try:
        mig.upgrade()
        conn.commit()
        # Populate a C1 table (the guard checks C1 + 07 + 08 tables).
        conn.execute(text(
            "INSERT INTO user_account (user_id, email_norm, role, status, password_alg, "
            "password_version, password_iterations, password_salt_b64, password_verifier_b64, "
            "password_change_required, created_at) "
            "VALUES ('u1', 'e@x.local', 'patient', 'ACTIVE', 'pbkdf2_sha256', 1, 1, 'c2FsdA==', "
            "'dmVyaWZpZXI=', 0, '2026-11-26T09:00:00Z')"))
        conn.commit()
        with pytest.raises(RuntimeError, match="downgrade refused"):
            mig.downgrade()
        # Nothing was dropped: the C2 tables and triggers still exist.
        tables = {r[0] for r in conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table'"))}
        assert C2_TABLES.issubset(tables)
    finally:
        conn.close()
        engine.dispose()


def test_downgrade_refuses_offline_as_sql(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'm.sqlite3').as_posix()}")
    mig = _load_migration()
    conn, _ = _bind(engine, mig, as_sql=True)
    try:
        with pytest.raises(RuntimeError, match="online verification"):
            mig.downgrade()
    finally:
        conn.close()
        engine.dispose()


def test_revision_metadata_is_additive_after_07():
    mig = _load_migration()
    assert mig.down_revision == "20261128_07"
    assert mig.revision == "20261128_08"


# --- residual P0 integration reconciliation: 6th-table coverage --------------
# The RB-C1 downgrade guard traverses the full C1 + 07 + 08 table list. Track 1's
# 07 tables are unpublished on this contributor branch, so the disposable harness
# creates EMPTY 07 stubs purely so the guard can reach the 08 tables. This is a
# labelled harness affordance, NOT a claim that 07 is integrated; the real
# 06 -> 07 -> 08 chain remains Track 1's integration checkpoint.
_CORE_07_TABLES = (
    "health_profile", "assessment_snapshot", "assessment",
    "inference_attempt", "inference_result",
)


def _create_07_stubs(conn):
    for name in _CORE_07_TABLES:
        conn.execute(text(f'CREATE TABLE IF NOT EXISTS "{name}" (id TEXT PRIMARY KEY)'))
    conn.commit()


def test_downgrade_refuses_populated_inflight_table(tmp_path):
    """The corrections-round 6th table is covered by the RB-C1 population guard."""
    engine = create_engine(f"sqlite:///{(tmp_path / 'm.sqlite3').as_posix()}")
    c1_tables = [t for n, t in Base.metadata.tables.items() if n not in C2_TABLES]
    Base.metadata.create_all(engine, tables=c1_tables)
    mig = _load_migration()
    conn, _ = _bind(engine, mig)
    try:
        _create_07_stubs(conn)
        mig.upgrade()
        conn.commit()
        # Populate ONLY document_inflight_operation (the 6th, corrections-round
        # table). FK enforcement is off in this raw harness; CHECKs are satisfied.
        conn.execute(text(
            "INSERT INTO document_inflight_operation (inflight_id, replay_scope, key_hash, "
            "actor_binding, operation, target_ref, request_fingerprint, actor_user_id, "
            "patient_id, document_id, state, fence_token, lease_owner, lease_expires_at, "
            "attempt_count, failure_code, created_at, updated_at) VALUES "
            "('i1','s','k','a','op','t','f','u','p','d','IN_FLIGHT',1,'o',"
            "'2026-11-26T09:01:30Z',1,NULL,'2026-11-26T09:00:00Z','2026-11-26T09:00:00Z')"))
        conn.commit()
        with pytest.raises(RuntimeError, match="downgrade refused"):
            mig.downgrade()
        tables = {r[0] for r in conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table'"))}
        assert "document_inflight_operation" in tables  # nothing dropped
    finally:
        conn.close()
        engine.dispose()


def test_empty_downgrade_drops_all_six_tables_and_triggers(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'm.sqlite3').as_posix()}")
    c1_tables = [t for n, t in Base.metadata.tables.items() if n not in C2_TABLES]
    Base.metadata.create_all(engine, tables=c1_tables)
    mig = _load_migration()
    conn, _ = _bind(engine, mig)
    try:
        _create_07_stubs(conn)
        mig.upgrade()
        conn.commit()
        mig.downgrade()
        conn.commit()
        tables = {r[0] for r in conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table'"))}
        triggers = {r[0] for r in conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='trigger'"))}
        assert C2_TABLES.isdisjoint(tables)              # all six dropped
        assert set(mig.TRIGGER_DEFINITIONS).isdisjoint(triggers)  # all 13 dropped
    finally:
        conn.close()
        engine.dispose()


def test_orm_metadata_matches_migration_for_all_six_tables(tmp_path):
    """ORM registration covers every migration column (startup verify_schema)."""
    from sqlalchemy import inspect
    engine = create_engine(f"sqlite:///{(tmp_path / 'm.sqlite3').as_posix()}")
    c1_tables = [t for n, t in Base.metadata.tables.items() if n not in C2_TABLES]
    Base.metadata.create_all(engine, tables=c1_tables)
    mig = _load_migration()
    conn, _ = _bind(engine, mig)
    try:
        mig.upgrade()
        conn.commit()
        inspector = inspect(engine)
        for table in C2_TABLES:
            migrated = {c["name"] for c in inspector.get_columns(table)}
            orm = {c.name for c in Base.metadata.tables[table].columns}
            assert migrated == orm, f"ORM/migration column drift in {table}"
        # The 6th table is registered in the ORM metadata for verify_schema.
        assert "document_inflight_operation" in Base.metadata.tables
    finally:
        conn.close()
        engine.dispose()
