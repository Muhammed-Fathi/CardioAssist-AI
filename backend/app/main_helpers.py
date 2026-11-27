"""Strict JSON decoding helpers shared by the legacy and Term 1 routes.

These are the exact functions the legacy handlers already use; they live in a
small module so Term 1 can reuse byte-identical strictness (duplicate object
members, non-finite numbers and non-standard constants all fail) without
importing the application object (which would be circular).
"""

from __future__ import annotations

import math
from typing import Any


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object member.")
        result[key] = value
    return result


def finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Non-finite JSON number.")
    return number


def reject_constant(value: str) -> None:
    raise ValueError("Non-standard JSON numeric constant.")
