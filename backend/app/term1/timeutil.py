"""UTC wall-clock helpers for the Term 1 stage.

All persisted timestamps are fixed-width UTC ISO-8601 strings:

    2026-11-26T10:20:30.123456Z

The fixed width makes lexicographic ordering in SQLite identical to temporal
ordering, so comparisons can happen either in SQL or in Python without a
conversion. Naive datetimes are rejected rather than silently coerced.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable

ISO_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(moment: datetime) -> str:
    if moment.tzinfo is None:
        raise ValueError("Refusing to serialize a naive datetime.")
    return moment.astimezone(timezone.utc).strftime(ISO_FORMAT)


def from_iso(value: str) -> datetime:
    return datetime.strptime(value, ISO_FORMAT).replace(tzinfo=timezone.utc)


def parse_rfc3339(value: str) -> datetime | None:
    """Parse the RFC3339 forms accepted from clients (strict, UTC-normalized)."""
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def is_expired(value: str | None, now: datetime) -> bool:
    if value is None:
        return False
    return from_iso(value) <= now


class Clock:
    """Injectable UTC clock; tests advance it explicitly."""

    def __init__(self, source: Callable[[], datetime] | None = None) -> None:
        self._source = source or utc_now

    def now(self) -> datetime:
        moment = self._source()
        if moment.tzinfo is None:
            raise ValueError("The Term 1 clock must be timezone-aware.")
        return moment.astimezone(timezone.utc)

    def now_iso(self) -> str:
        return to_iso(self.now())

    def plus(self, seconds: float) -> str:
        return to_iso(self.now() + timedelta(seconds=seconds))

    def iso_after(self, seconds: float) -> str:
        return self.plus(seconds)
