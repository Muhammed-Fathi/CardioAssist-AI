"""Alembic environment for the configured local database."""

from __future__ import annotations

import os
from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy.pool import NullPool

from backend.app.storage.database import DEFAULT_DATABASE_URL, build_engine
from backend.app.storage.models import Base

# Importing the C1 mappings registers the Term 1 tables on the same metadata so
# that `alembic check` (and read-only startup verification) compares the full
# expected schema, not only the legacy monitoring tables.
from backend.app.term1 import models as _term1_models  # noqa: F401  (side effect)
import backend.app.term1_c2_documents.models as _term1_c2_document_models  # noqa: F401 (side effect)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _database_url() -> str:
    return (
        config.attributes.get("database_url")
        or os.environ.get("CARDIOASSIST_DATABASE_URL")
        or config.get_main_option("sqlalchemy.url")
        or DEFAULT_DATABASE_URL
    )


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    supplied_connection = config.attributes.get("connection")
    if supplied_connection is not None:
        _run_with_connection(supplied_connection)
        return

    engine = build_engine(_database_url(), poolclass=NullPool)
    try:
        with engine.connect() as connection:
            _run_with_connection(connection)
    finally:
        engine.dispose()


def _run_with_connection(connection: Any) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        render_as_batch=connection.dialect.name == "sqlite",
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
