"""Canonical JSON encoding and request-payload hashing.

These helpers were extracted unchanged from ``mock_prediction`` so that
idempotency hashing (both tracks) does not depend on the Track A synthetic
scoring module. The canonical form, the ``request_id`` exclusion and the
SHA-256 digest are byte-for-byte identical to the merged implementation; the
approved OpenAPI contract and the reference oracle define that behavior.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def payload_hash(body: dict[str, Any]) -> str:
    payload = {key: value for key, value in body.items() if key != "request_id"}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
