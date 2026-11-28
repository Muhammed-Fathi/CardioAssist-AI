"""Track 2 metadata-only workflow audit writer.

The C1 ``workflow_audit_event`` table has no DB CHECK on ``event_type`` /
``subject_type`` (only ``outcome``), so Track 2 writes its additive document
event types here without editing ``backend/app/term1/constants.py`` (a shared
file owned by the core integrator). The sanitization and digest rules are reused
verbatim from the C1 audit module so no identifier or secret is ever logged.
"""

from __future__ import annotations

import uuid
from typing import Any, Mapping

from sqlalchemy.orm import Session

from ..term1 import constants as c1
from ..term1.audit import payload_digest
from ..term1.models import WorkflowAuditEvent
from ..term1.timeutil import Clock
from . import constants as C

_EVENT_TYPES = frozenset(
    {
        C.AUDIT_EVENT_DOCUMENT_UPLOADED,
        C.AUDIT_EVENT_DOCUMENT_UPLOAD_FAILED,
        C.AUDIT_EVENT_DOCUMENT_EXTRACTED,
        C.AUDIT_EVENT_DOCUMENT_EXTRACTION_FAILED,
        C.AUDIT_EVENT_DOCUMENT_CONFIRMED,
        C.AUDIT_EVENT_DOCUMENT_INTEGRITY_MISMATCH,
        C.AUDIT_EVENT_DOCUMENT_RECOVERED,
    }
)
_SUBJECT_TYPES = frozenset(
    {C.AUDIT_SUBJECT_MEDICAL_DOCUMENT, C.AUDIT_SUBJECT_DOCUMENT_EXTRACTION}
)


def record_document_event(
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
    if event_type not in _EVENT_TYPES:
        raise ValueError(f"Unknown document audit event type: {event_type}")
    if outcome not in c1.OUTCOMES:
        raise ValueError(f"Unknown audit outcome: {outcome}")
    if subject_type not in _SUBJECT_TYPES:
        raise ValueError(f"Unknown document audit subject type: {subject_type}")
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
