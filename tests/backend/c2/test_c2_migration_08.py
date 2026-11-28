"""Migration 20261128_08 upgrade/downgrade behavior (disposable harness).

The full alembic ``06 → 07 → 08`` chain upgrade/downgrade is an integration
checkpoint pending Track 1's ``20261128_07``. These tests exercise the migration's
own ``upgrade()``/``downgrade()`` callables directly through a bound
``alembic.operations.Operations`` so the DDL, the eight triggers and the RB-C1
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
             "extraction_event", "assessment_document"}


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


def test_upgrade_creates_five_tables_and_eight_triggers(tmp_path):
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
        assert len(triggers) == 8
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
