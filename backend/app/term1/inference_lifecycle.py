"""Accepted P-16 lease/generation/fencing lifecycle for C2 inference attempts.

Implements the C0 §7.3 / schema spec §3.4 machinery as service functions used
by S1 under ``C2_SAFE_SCOPE`` and by future A3 code:

* ``begin_attempt`` — dispatch write order (insert ``INFERENCE_RUNNING`` attempt
  with generation/lease/fence, then set ``assessment.active_attempt_id``);
* ``complete_unavailable`` / ``complete_abstained`` / ``complete_error`` —
  common fence check first (zero DB writes on rejection, ``409
  stale_attempt_fenced``), then the mandatory terminal write order (clear the
  assessment pointer, then terminalize the attempt);
* ``recover_expired`` — lease expiry recovery, incrementing
  ``assessment.current_generation`` exactly once.

There is deliberately **no success-publication path**: no function here can
insert an ``inference_result`` row or contact an adapter, artifact or provider
(A3 gate). SAFE_SCOPE's S1 goes ``INPUT_VALIDATED -> INFERENCE_RUNNING ->
INFERENCE_UNAVAILABLE(real_ai_not_authorized)`` entirely inside one
``BEGIN IMMEDIATE`` transaction. ``worker_id`` is ``'disabled_stub'`` and no
mock fallback exists anywhere in this module.
"""

from __future__ import annotations

import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import constants
from .audit import record
from .crypto import sha256_hex
from .errors import api_error
from .idempotency import canonical_public
from .models import (
    Assessment,
    ConsentRecord,
    DoctorPatientAssignment,
    InferenceAttempt,
)
from .timeutil import Clock


def new_fence_token() -> str:
    """64-hex CSPRNG token bound to (attempt_id, assessment_id, generation)."""
    return secrets.token_hex(32)


def attempt_idempotency_hash(
    *,
    assessment_id: str,
    snapshot_sha256: str,
    generation: int,
    dispatch_kind: str,
) -> str:
    """sha256(canonical({assessment_id, snapshot_sha256, generation,
    dispatch_kind})) — schema spec §3.4."""
    return sha256_hex(
        canonical_public(
            {
                "assessment_id": assessment_id,
                "snapshot_sha256": snapshot_sha256,
                "generation": generation,
                "dispatch_kind": dispatch_kind,
            }
        )
    )


def begin_attempt(
    session: Session,
    *,
    clock: Clock,
    assessment: Assessment,
    snapshot_sha256: str,
    dispatch_kind: str = constants.DISPATCH_KIND_ASSESSMENT_SUBMIT,
) -> InferenceAttempt:
    """INPUT_VALIDATED -> INFERENCE_RUNNING (mandatory dispatch write order).

    Never dispatches: it only records the durable attempt with the P-16 lease
    (``leased_at + 300s``) and fence material. The caller must already hold the
    assessment's write transaction.
    """
    if assessment.status != constants.ASSESSMENT_INPUT_VALIDATED:
        raise api_error("stale_attempt_fenced")
    if assessment.active_attempt_id is not None:
        raise api_error("stale_attempt_fenced")
    now = clock.now_iso()
    lease_until = clock.plus(constants.LEASE_SECONDS)
    attempt = InferenceAttempt(
        attempt_id=str(uuid.uuid4()),
        assessment_id=assessment.assessment_id,
        generation=assessment.current_generation,
        attempt_idempotency_hash=attempt_idempotency_hash(
            assessment_id=assessment.assessment_id,
            snapshot_sha256=snapshot_sha256,
            generation=assessment.current_generation,
            dispatch_kind=dispatch_kind,
        ),
        worker_id=constants.WORKER_ID_DISABLED,
        fence_token=new_fence_token(),
        state=constants.ATTEMPT_STATE_RUNNING,
        reason_code=None,
        leased_at=now,
        lease_until=lease_until,
        completed_at=None,
    )
    session.add(attempt)
    session.flush()
    assessment.status = constants.ASSESSMENT_INFERENCE_RUNNING
    assessment.active_attempt_id = attempt.attempt_id
    assessment.updated_at = now
    session.flush()
    return attempt


def _fenced(
    session: Session,
    *,
    clock: Clock,
    attempt_id: str,
    worker_id: str,
    fence_token: str,
) -> tuple[InferenceAttempt, Assessment]:
    """Common fence check (schema spec §3.4 item 1); zero DB writes."""
    attempt = session.execute(
        select(InferenceAttempt).where(InferenceAttempt.attempt_id == attempt_id)
    ).scalar_one_or_none()
    if attempt is None:
        raise api_error("stale_attempt_fenced")
    assessment = session.execute(
        select(Assessment).where(
            Assessment.assessment_id == attempt.assessment_id
        )
    ).scalar_one_or_none()
    now_iso = clock.now_iso()
    if (
        assessment is None
        or assessment.active_attempt_id != attempt.attempt_id
        or attempt.generation != assessment.current_generation
        or attempt.state != constants.ATTEMPT_STATE_RUNNING
        or assessment.status != constants.ASSESSMENT_INFERENCE_RUNNING
        or attempt.worker_id != worker_id
        or attempt.fence_token != fence_token
        or not (attempt.lease_until > now_iso)
    ):
        raise api_error("stale_attempt_fenced")
    return attempt, assessment


def _authorization_is_active(
    session: Session, assessment: Assessment
) -> bool:
    """Validate the exact persisted assignment and consent pins.

    Missing rows, cross-patient references, revoked assignments/consents, and
    unexpected consent kind/scope/version all fail closed. The checks use the
    immutable IDs stored on this assessment, never a replacement active row.
    """
    assignment = session.execute(
        select(DoctorPatientAssignment).where(
            DoctorPatientAssignment.assignment_id == assessment.assignment_id
        )
    ).scalar_one_or_none()
    consent = session.execute(
        select(ConsentRecord).where(
            ConsentRecord.consent_id == assessment.consent_id
        )
    ).scalar_one_or_none()
    return bool(
        assignment is not None
        and assignment.assignment_id == assessment.assignment_id
        and assignment.patient_id == assessment.patient_id
        and assignment.revoked_at is None
        and consent is not None
        and consent.consent_id == assessment.consent_id
        and consent.patient_id == assessment.patient_id
        and consent.kind == constants.CONSENT_KIND_SYNTHETIC_DEMO
        and consent.scope == constants.CONSENT_SCOPE_PATIENT_WIDE
        and consent.contract_version == constants.CONSENT_CONTRACT_VERSION
        and consent.revoked_at is None
    )


def _terminalize(
    session: Session,
    *,
    clock: Clock,
    attempt: InferenceAttempt,
    assessment: Assessment,
    state: str,
    reason_code: str,
    actor_user_id: str | None,
    increment_generation: bool = False,
) -> None:
    """Terminalize atomically after exact authorization revalidation.

    Revoked, missing, cross-patient or wrong-scope authorization changes every
    attempted outcome into ``INFERENCE_UNAVAILABLE / authorization_withdrawn``.
    Recovery increments the generation once before the attempt is terminalized.
    """
    if not _authorization_is_active(session, assessment):
        state = constants.ATTEMPT_STATE_UNAVAILABLE
        reason_code = constants.REASON_AUTHORIZATION_WITHDRAWN
    now = clock.now_iso()
    assessment.status = state
    assessment.reason_code = reason_code
    assessment.active_attempt_id = None
    assessment.current_result_id = None
    if increment_generation:
        assessment.current_generation += 1
    assessment.updated_at = now
    session.flush()
    attempt.state = state
    attempt.reason_code = reason_code
    attempt.completed_at = now
    session.flush()
    record(
        session,
        clock=clock,
        event_type=constants.EVENT_INFERENCE_ATTEMPT_TERMINATED,
        outcome=constants.OUTCOME_SUCCESS,
        subject_type=constants.SUBJECT_INFERENCE_ATTEMPT,
        subject_id=attempt.attempt_id,
        actor_user_id=actor_user_id,
        payload={
            "assessment_id": assessment.assessment_id,
            "state": state,
            "reason_code": reason_code,
            "generation": attempt.generation,
            "current_generation": assessment.current_generation,
            "recovery": increment_generation,
        },
    )


def complete_unavailable(
    session: Session,
    *,
    clock: Clock,
    attempt_id: str,
    reason_code: str,
    worker_id: str,
    fence_token: str,
    actor_user_id: str | None = None,
) -> InferenceAttempt:
    """Terminal INFERENCE_UNAVAILABLE with mid-flight revocation precedence.

    If the exact assignment or referenced consent is unavailable or no longer
    valid, the terminal state is ``authorization_withdrawn`` regardless of the
    caller's requested reason.
    """
    if reason_code != constants.REASON_REAL_AI_NOT_AUTHORIZED:
        raise api_error("validation_failed")
    attempt, assessment = _fenced(
        session,
        clock=clock,
        attempt_id=attempt_id,
        worker_id=worker_id,
        fence_token=fence_token,
    )
    _terminalize(
        session,
        clock=clock,
        attempt=attempt,
        assessment=assessment,
        state=constants.ATTEMPT_STATE_UNAVAILABLE,
        reason_code=reason_code,
        actor_user_id=actor_user_id,
    )
    return attempt


def complete_abstained(
    session: Session,
    *,
    clock: Clock,
    attempt_id: str,
    worker_id: str,
    fence_token: str,
    actor_user_id: str | None = None,
) -> InferenceAttempt:
    """Terminal INFERENCE_ABSTAINED (optional resting field missing)."""
    attempt, assessment = _fenced(
        session,
        clock=clock,
        attempt_id=attempt_id,
        worker_id=worker_id,
        fence_token=fence_token,
    )
    if assessment.stage_complete:
        raise api_error("validation_failed")
    _terminalize(
        session,
        clock=clock,
        attempt=attempt,
        assessment=assessment,
        state=constants.ATTEMPT_STATE_ABSTAINED,
        reason_code=constants.REASON_OPTIONAL_PANEL_FIELD_MISSING,
        actor_user_id=actor_user_id,
    )
    return attempt


def complete_error(
    session: Session,
    *,
    clock: Clock,
    attempt_id: str,
    reason_code: str,
    worker_id: str,
    fence_token: str,
    actor_user_id: str | None = None,
) -> InferenceAttempt:
    """Terminal INFERENCE_ERROR (worker/malformed/digest failure reasons)."""
    if reason_code not in (
        constants.REASON_WORKER_ERROR,
        constants.REASON_MALFORMED_WORKER_RESPONSE,
        constants.REASON_ARTIFACT_INTEGRITY_FAILED,
    ):
        raise api_error("validation_failed")
    attempt, assessment = _fenced(
        session,
        clock=clock,
        attempt_id=attempt_id,
        worker_id=worker_id,
        fence_token=fence_token,
    )
    _terminalize(
        session,
        clock=clock,
        attempt=attempt,
        assessment=assessment,
        state=constants.ATTEMPT_STATE_ERROR,
        reason_code=reason_code,
        actor_user_id=actor_user_id,
    )
    return attempt


def recover_expired(session: Session, *, clock: Clock) -> int:
    """Recover expired running attempts once using the strict lease boundary.

    Rows with a stale pointer, assessment status or generation are not counted
    or mutated. A recovered attempt increments the assessment generation once;
    if its exact authorization is no longer valid it ends unavailable with
    ``authorization_withdrawn`` rather than an ordinary lease error.
    """
    now_iso = clock.now_iso()
    expired = session.execute(
        select(InferenceAttempt).where(
            InferenceAttempt.state == constants.ATTEMPT_STATE_RUNNING,
            InferenceAttempt.lease_until <= now_iso,
        )
    ).scalars().all()
    recovered = 0
    for attempt in expired:
        assessment = session.execute(
            select(Assessment).where(
                Assessment.assessment_id == attempt.assessment_id
            )
        ).scalar_one_or_none()
        if (
            assessment is None
            or assessment.active_attempt_id != attempt.attempt_id
            or assessment.status != constants.ASSESSMENT_INFERENCE_RUNNING
            or assessment.current_generation != attempt.generation
        ):
            continue
        _terminalize(
            session,
            clock=clock,
            attempt=attempt,
            assessment=assessment,
            state=constants.ATTEMPT_STATE_ERROR,
            reason_code=constants.REASON_LEASE_EXPIRED,
            actor_user_id=None,
            increment_generation=True,
        )
        recovered += 1
    return recovered
