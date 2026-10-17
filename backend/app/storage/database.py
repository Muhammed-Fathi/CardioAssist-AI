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
        """Fail closed when migrations have not created the required schema."""
        from sqlalchemy import inspect

        from .models import Base

        inspector = inspect(self.engine)
        tables = set(inspector.get_table_names())
        required = set(Base.metadata.tables)
        missing = required - tables
        if "alembic_version" not in tables or missing:
            details = ", ".join(sorted(missing)) or "alembic_version"
            raise RuntimeError(
                "Database schema is missing or not migrated (missing: "
                f"{details}); run `python -m alembic upgrade head` first."
            )

    def dispose(self) -> None:
        self.engine.dispose()
