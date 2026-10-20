"""SQLAlchemy database configuration and transaction boundary.

SQLite is the default local store. The URL is configurable so the same
repository boundary can be exercised with another SQLAlchemy dialect later;
this slice has only been tested with SQLite.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL_ENV = "CARDIOASSIST_DATABASE_URL"
DEFAULT_DATABASE_URL = "sqlite:///./var/cardioassist.sqlite3"


def configured_database_url(override: str | None = None) -> str:
    """Return an explicit URL, environment URL, or relative local default."""
    return override or os.environ.get(DATABASE_URL_ENV, DEFAULT_DATABASE_URL)


def build_engine(database_url: str, *, poolclass: type | None = None) -> Engine:
    """Build an engine with SQLite integrity/concurrency settings when needed."""
    url = make_url(database_url)
    connect_args: dict[str, object] = {}
    if url.get_backend_name() == "sqlite":
        connect_args = {"check_same_thread": False, "timeout": 10}
        database_name = url.database
        if database_name and database_name != ":memory:" and not database_name.startswith("file:"):
            Path(database_name).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)

    engine_options: dict[str, object] = {
        "future": True,
        "pool_pre_ping": True,
        "connect_args": connect_args,
    }
    if poolclass is not None:
        engine_options["poolclass"] = poolclass
    engine = create_engine(database_url, **engine_options)

    if url.get_backend_name() == "sqlite":
        database_name = url.database

        @event.listens_for(engine, "connect")
        def _configure_sqlite(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=10000")
            cursor.execute("PRAGMA synchronous=NORMAL")
            if database_name and database_name != ":memory:" and not database_name.startswith("file:"):
                cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    return engine


def _expected_migration_heads() -> tuple[str, ...]:
    """Load the migration graph's expected heads without touching a database."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config_path = Path(__file__).resolve().parents[3] / "alembic.ini"
    if not config_path.is_file():
        raise RuntimeError(f"Alembic configuration was not found at {config_path}.")
    heads = tuple(sorted(ScriptDirectory.from_config(Config(str(config_path))).get_heads()))
    if not heads:
        raise RuntimeError(f"No Alembic migration heads are configured in {config_path}.")
    return heads


def _schema_change_label(change: tuple[object, ...]) -> str:
    """Describe a metadata difference compactly for startup diagnostics."""
    operation = str(change[0]) if change else "unknown schema change"
    try:
        if operation == "add_column":
            return f"add_column {change[2]}.{change[3].name}"
        if operation == "remove_column":
            return f"remove_column {change[1]}.{change[2].name}"
        if operation in {
            "modify_type",
            "modify_nullable",
            "modify_default",
            "modify_comment",
            "modify_name",
        }:
            return f"{operation} {change[2]}.{change[3]}"
        if operation in {"add_index", "remove_index"}:
            return f"{operation} {change[1].name}"
        if operation in {"add_constraint", "remove_constraint"}:
            constraint = change[1]
            return f"{operation} {constraint.name or type(constraint).__name__}"
        if operation in {"add_fk", "remove_fk"}:
            constraint = change[1]
            return f"{operation} {constraint.table.name}"
        if operation in {"add_table", "remove_table"}:
            return f"{operation} {change[1].name}"
    except (AttributeError, IndexError, TypeError):
        pass
    return operation


class Database:
    """Owns an engine and short, explicit SQLAlchemy transaction scopes."""

    def __init__(self, database_url: str | None = None) -> None:
        self.url = configured_database_url(database_url)
        self.engine = build_engine(self.url)
        self._sessions = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
            future=True,
        )

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        """Commit on normal exit and roll back every failure before re-raising."""
        session = self._sessions()
        try:
            with session.begin():
                yield session
        except BaseException:
            # Session.begin() already rolls back; this makes the boundary
            # explicit for callers and also covers failures during commit.
            session.rollback()
            raise
        finally:
            session.close()

    def verify_schema(self) -> None:
        """Fail closed unless the database matches the current migration head.

        This is a read-only startup check. Migrations and repairs remain
        explicit operator actions; this method never creates or upgrades schema.
        """
        from alembic.autogenerate import compare_metadata
        from alembic.migration import MigrationContext
        from sqlalchemy import String, inspect

        from .models import Base

        expected_heads = _expected_migration_heads()
        with self.engine.connect() as connection:
            inspector = inspect(connection)
            tables = set(inspector.get_table_names())
            required = set(Base.metadata.tables)
            missing = required - tables
            if "alembic_version" not in tables or missing:
                details = sorted(missing)
                if "alembic_version" not in tables:
                    details.append("alembic_version")
                raise RuntimeError(
                    "Database schema is missing required tables (missing: "
                    f"{', '.join(details)}). Run `python -m alembic upgrade head` "
                    "explicitly; application startup never upgrades the database."
                )

            version_columns = inspector.get_columns("alembic_version")
            if (
                len(version_columns) != 1
                or version_columns[0]["name"] != "version_num"
                or version_columns[0]["nullable"]
                or not version_columns[0]["primary_key"]
                or not isinstance(version_columns[0]["type"], String)
                or version_columns[0]["type"].length != 32
            ):
                raise RuntimeError(
                    "The alembic_version table has an incompatible structure; "
                    "restore a known-good schema or repair it with an explicit, "
                    "operator-reviewed migration. Startup does not repair schema."
                )

            actual_heads = tuple(
                sorted(
                    str(head)
                    for head in MigrationContext.configure(connection).get_current_heads()
                )
            )
            if actual_heads != expected_heads:
                expected = ", ".join(expected_heads)
                found = ", ".join(actual_heads) or "<none>"
                raise RuntimeError(
                    "Database Alembic revision mismatch "
                    f"(expected head(s): {expected}; found: {found}). No migration "
                    "was run. Review the revision history and explicitly migrate "
                    "a known older revision or restore a verified backup."
                )

            # Alembic autogenerate compares columns, indexes, unique constraints
            # and foreign keys, but does not report primary-key changes. Check
            # those explicitly so a database cannot pass with its row identity
            # constraints removed or altered.
            summaries: list[str] = []
            for table in Base.metadata.sorted_tables:
                expected_primary_key = list(table.primary_key.columns.keys())
                actual_primary_key = inspector.get_pk_constraint(table.name).get(
                    "constrained_columns", []
                )
                if actual_primary_key != expected_primary_key:
                    summaries.append(
                        f"primary_key {table.name} "
                        f"(expected {expected_primary_key}; found {actual_primary_key})"
                    )

            differences = compare_metadata(
                MigrationContext.configure(connection, opts={"compare_type": True}),
                Base.metadata,
            )
            summaries.extend(_schema_change_label(change) for change in differences)
            if summaries:
                details = ", ".join(summaries[:10])
                if len(summaries) > 10:
                    details += f", and {len(summaries) - 10} more"
                raise RuntimeError(
                    "Database schema is incompatible with the current Alembic "
                    f"head (differences: {details}). Restore a verified backup or "
                    "repair it with an explicit, operator-reviewed migration; "
                    "startup never changes the schema."
                )

            if connection.dialect.name == "sqlite":
                foreign_keys_enabled = connection.exec_driver_sql(
                    "PRAGMA foreign_keys"
                ).scalar_one()
                if foreign_keys_enabled != 1:
                    raise RuntimeError(
                        "SQLite foreign-key enforcement is disabled for this "
                        "connection; database startup verification failed."
                    )

                integrity_result = connection.exec_driver_sql(
                    "PRAGMA integrity_check"
                ).scalar_one()
                if integrity_result != "ok":
                    raise RuntimeError(
                        f"SQLite integrity_check failed: {integrity_result}"
                    )

                foreign_key_violation = connection.exec_driver_sql(
                    "PRAGMA foreign_key_check"
                ).first()
                if foreign_key_violation is not None:
                    raise RuntimeError(
                        "SQLite foreign-key integrity check failed "
                        f"(first violation: {tuple(foreign_key_violation)})."
                    )

    def dispose(self) -> None:
        self.engine.dispose()
