"""Explicit transaction boundaries for Term 1.

SQLite has no ``SELECT ... FOR UPDATE``, so any read-then-conditional-write that
must be race-safe runs inside ``BEGIN IMMEDIATE``: the write lock is taken up
front, which serialises competing transactions instead of letting them upgrade
lazily and fail with ``database is locked`` after doing work.

Two helpers exist:

``write_transaction``
    ``BEGIN IMMEDIATE`` + commit on success + rollback on any failure. Every
    business effect (and its success audit row and idempotency row) commits
    atomically here.

``read_transaction``
    A plain read-only connection for lookups (replay pre-check, session
    inspection, listings). Never mutates.

Attempt counters for failed authentication/enrollment are intentionally written
*after* a business rollback, in their own ``write_transaction``, so a rejected
attempt still leaves durable evidence (C1.9).
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy.orm import Session

from ..storage.database import Database
from .models import AdminBootstrapRecord, InvitationRedemption, UserAccount


def _open(database: Database, *, immediate: bool) -> tuple[object, Session]:
    connection = database.engine.connect()
    try:
        if immediate:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        session = Session(
            bind=connection,
            join_transaction_mode="control_fully",
            autoflush=False,
            expire_on_commit=False,
            future=True,
        )
    except BaseException:
        connection.close()
        raise
    return connection, session


@contextmanager
def write_transaction(database: Database) -> Iterator[Session]:
    connection, session = _open(database, immediate=True)
    try:
        yield session
        # ORM units of work order INSERTs by mapper dependency. Tables without a
        # mapped relationship (the one-to-one bootstrap guard row, the audit and
        # redemption rows) are ordered here so that SQLite's immediate
        # foreign-key enforcement always sees their referenced rows first.
        session.flush()
        _flush_dependents_in_order(session)
        connection.commit()
    except BaseException:
        try:
            connection.rollback()
        finally:
            session.close()
            connection.close()
        raise
    else:
        session.close()
        connection.close()


_FLUSH_ORDER = (AdminBootstrapRecord, InvitationRedemption)


def _flush_dependents_in_order(session: Session) -> None:
    for model in _FLUSH_ORDER:
        pending = [obj for obj in session.new if isinstance(obj, model)]
        if pending:
            session.flush(pending)


@contextmanager
def read_transaction(database: Database) -> Iterator[Session]:
    connection, session = _open(database, immediate=False)
    try:
        yield session
    finally:
        session.close()
        connection.close()
