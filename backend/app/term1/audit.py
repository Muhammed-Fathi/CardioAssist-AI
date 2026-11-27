"""Metadata-only workflow audit writer (C1.9).

Rules encoded here:

* Success rows are inserted in the same transaction as the business effect, so a
  committed effect always has its audit row and a rolled-back effect never does.
* Failure rows are written by the caller in a *separate* transaction after the
  business rollback, so evidence survives a rejected attempt.
* The payload digest is computed over a canonical JSON document of *metadata
  only*. Callers pass references (ids, codes from a closed vocabulary, counts)
  and never secrets, tokens, access codes or raw identifiers.
* If the audit insert itself fails, the caller's transaction fails and the
  original error is not masked; nothing here retries or swallows.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from typing import Any, Mapping

from sqlalchemy.orm import Session

from . import constants
from .models import WorkflowAuditEvent
from .timeutil import Clock

logger = logging.getLogger("cardioassist.term1.audit")

_REDACTED = "<redacted>"
_FORBIDDEN_KEYS = frozenset(
    {
        "password",
        "current_password",
        "new_password",
        "temp_password",
        "temp_secret",
        "access_code",
        "session_token",
        "token",
        "identifier",
        "subject_identifier",
        "email",
        "national_id",
        "authorization",
        "idempotency_key",
        "bootstrap_secret",
        "key",
        "pepper",
    }
)


def _sanitize(value: Any, depth: int = 0) -> Any:
    """Drop secret-bearing members and bound the document size."""
    if depth > 5:
        return _REDACTED
    if isinstance(value, Mapping):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            name = str(key)
            if name.lower() in _FORBIDDEN_KEYS:
                cleaned[name] = _REDACTED
            else:
                cleaned[name] = _sanitize(item, depth + 1)
        return cleaned
    if isinstance(value, (list, tuple)):
        return [_sanitize(item, depth + 1) for item in value[:20]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        if isinstance(value, str) and len(value) > 200:
            return value[:64] + "…"
        return value
    return _REDACTED


def payload_digest(payload: Mapping[str, Any] | None) -> str:
    document = {"payload": _sanitize(dict(payload or {}))}
    canonical = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def record(
    session: Session,
    *,
    clock: Clock,
    event_type: str,
    outcome: str,
    subject_type: str,
    subject_id: str | None = None,
    actor_user_id: str | None = None,
    code: str | None = None,
    request_id: str | None = None,
    payload: Mapping[str, Any] | None = None,
) -> str:
    """Append one workflow audit row inside the caller's transaction."""
    if event_type not in constants.WORKFLOW_EVENT_TYPES:
        raise ValueError(f"Unknown workflow event type: {event_type}")
    if outcome not in constants.OUTCOMES:
        raise ValueError(f"Unknown audit outcome: {outcome}")
    if subject_type not in constants.AUDIT_SUBJECT_TYPES:
        raise ValueError(f"Unknown audit subject type: {subject_type}")
    if subject_type == constants.SUBJECT_UNKNOWN_INVITATION and subject_id is not None:
        raise ValueError("An unknown-invitation audit row must not carry a subject id.")
    audit_id = str(uuid.uuid4())
    session.add(
        WorkflowAuditEvent(
            audit_id=audit_id,
            event_type=event_type,
            actor_user_id=actor_user_id,
            subject_type=subject_type,
            subject_id=subject_id,
            request_id=request_id,
            code=code,
            outcome=outcome,
            payload_sha256=payload_digest(payload),
            recorded_at=clock.now_iso(),
        )
    )
    return audit_id


def record_isolated(
    database,
    *,
    clock: Clock,
    **kwargs: Any,
) -> str | None:
    """Write failure evidence after a rollback; never masks the original error."""
    from .tx import write_transaction

    try:
        with write_transaction(database) as session:
            return record(session, clock=clock, **kwargs)
    except Exception:  # pragma: no cover - defensive, exercised by a test double
        logger.error(
            "workflow_audit_write_failed event_type=%s subject_type=%s",
            kwargs.get("event_type"),
            kwargs.get("subject_type"),
        )
        return None
