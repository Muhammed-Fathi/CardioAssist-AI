"""UTC clock plumbing for Term 1.

The legacy backend is injected a monotonic float clock for its process-local
idempotency windows. Term 1 needs *wall-clock UTC* for session expiry, invitation
TTL, lockouts and audit timestamps, while tests still need to advance time
deterministically. This module bridges the two without letting a monotonic value
silently become a calendar time.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable

BASE = datetime(2026, 11, 26, 9, 0, 0, tzinfo=timezone.utc)


def clock_from(source: Callable[[], object] | None) -> Callable[[], datetime]:
    """Return a timezone-aware UTC clock.

    ``source`` may return a ``datetime`` (used directly, must be aware) or a
    numeric value, which is interpreted as an offset in seconds from a fixed
    synthetic epoch so that tests can advance time monotonically.
    """
    if source is None:
        return lambda: datetime.now(timezone.utc)

    def read() -> datetime:
        value = source()
        if isinstance(value, datetime):
            if value.tzinfo is None:
                raise ValueError("Injected Term 1 clocks must be timezone-aware.")
            return value.astimezone(timezone.utc)
        if isinstance(value, (int, float)):
            return BASE + timedelta(seconds=float(value))
        raise TypeError("Unsupported Term 1 clock value.")

    return read
