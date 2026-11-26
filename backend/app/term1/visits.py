"""Verified prior visits and the secure invitation lifecycle (C1.4/C1.5).

A doctor must attest an *already occurred* synthetic demo visit before an
invitation can exist. The attestation binds the doctor, the fictitious subject
digest computed at attestation time, the clinician-stated visit time and the
server-generated ``attested_at``.

Invariants enforced here:

* owner: only the doctor who attested a visit may read it or issue/revoke/read
  invitations for it; anyone else receives ``404``;
* binding: the invitation's ``subject_identifier_hmac`` and
  ``identifier_key_id`` are copied from the visit, and an invitation request
  whose submitted identifier digests differently is refused generically. A
  doctor therefore cannot issue patient B's code against patient A's visit;
* one active invitation per visit: issuance takes the write lock, expires any
  lapsed invitation first, and refuses with ``invitation_already_active`` while
  a live one exists;
* the access code is 256-bit CSPRNG, disclosed exactly once, and persisted only
  as ``sha256(code)``;
* a consumed invitation stays consumed forever (``consumed_at`` is never cleared
  and a revoked/consumed pair is rejected by the CHECK constraint).
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import constants, crypto
from .audit import record
from .errors import api_error
from .identity import IdentityBinding, compute_binding, verify_or_activate
from .models import DoctorProfile, PatientInvitation, UserAccount, VerifiedVisit
from .settings import Term1Settings
from .timeutil import Clock, from_iso, parse_rfc3339, to_iso

_MAX_VISIT_REF = 128


def require_doctor(
    session: Session, *, account: UserAccount
) -> DoctorProfile:
    if account.role != constants.ROLE_DOCTOR:
        raise api_error("forbidden")
    profile = session.execute(
        select(DoctorProfile).where(DoctorProfile.user_id == account.user_id)
    ).scalar_one_or_none()
    if profile is None:
        # Role/profile inconsistency fails closed rather than silently passing.
        raise api_error("role_profile_mismatch")
    if not profile.active:
        raise api_error("forbidden")
    return profile


def _validate_attestation(
    *, visit_ref: str, asserted_visit_at: str, attestation_code: str, clock: Clock
) -> tuple[str, str]:
    reference = visit_ref.strip()
    if not reference or len(reference) > _MAX_VISIT_REF:
        raise api_error("validation_failed")
    if any(ord(char) < 0x20 for char in reference):
        raise api_error("validation_failed")
    if attestation_code not in constants.ATTESTATION_CODES:
        raise api_error("invalid_attestation")
    moment = parse_rfc3339(asserted_visit_at)
    if moment is None:
        raise api_error("validation_failed")
    if moment > clock.now() + timedelta(seconds=300):
        # The attested visit must already have occurred (small clock skew only).
        raise api_error("invalid_attestation")
    return reference, to_iso(moment)


def attest_visit(
    session: Session,
    *,
    clock: Clock,
    settings: Term1Settings,
    account: UserAccount,
    visit_ref: str,
    subject_identifier: str,
    asserted_visit_at: str,
    attestation_code: str,
) -> dict[str, object]:
    profile = require_doctor(session, account=account)
    normalized = crypto.normalize_demo_identifier(subject_identifier)
    if normalized is None:
        raise api_error("invalid_demo_identifier")
    reference, stated = _validate_attestation(
        visit_ref=visit_ref,
        asserted_visit_at=asserted_visit_at,
        attestation_code=attestation_code,
        clock=clock,
    )
    verify_or_activate(session, settings=settings, clock=clock, write=True)
    binding = compute_binding(settings, normalized)

    existing = session.execute(
        select(VerifiedVisit).where(
            VerifiedVisit.doctor_id == profile.doctor_id, VerifiedVisit.visit_ref == reference
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise api_error("concurrency_conflict")

    visit = VerifiedVisit(
        visit_id=str(uuid.uuid4()),
        doctor_id=profile.doctor_id,
        visit_ref=reference,
        subject_identifier_hmac=binding.identifier_hmac,
        identifier_key_id=binding.identifier_key_id,
        subject_label=binding.subject_label,
        asserted_visit_at=stated,
        attested_at=clock.now_iso(),
        attestation_code=attestation_code,
        note_code=None,
    )
    session.add(visit)
    record(
        session,
        clock=clock,
        event_type=constants.EVENT_VISIT_ATTESTED,
        outcome=constants.OUTCOME_SUCCESS,
        subject_type=constants.SUBJECT_VERIFIED_VISIT,
        subject_id=visit.visit_id,
        actor_user_id=account.user_id,
        payload={"attestation_code": attestation_code, "doctor_id": profile.doctor_id},
    )
    return _visit_projection(visit)


def _visit_projection(visit: VerifiedVisit) -> dict[str, object]:
    return {
        "visit_id": visit.visit_id,
        "visit_ref": visit.visit_ref,
        "subject_label": visit.subject_label,
        "asserted_visit_at": visit.asserted_visit_at,
        "attested_at": visit.attested_at,
        "attestation_code": visit.attestation_code,
    }


def _owned_visit(
    session: Session, *, account: UserAccount, visit_id: str
) -> tuple[DoctorProfile, VerifiedVisit]:
    profile = require_doctor(session, account=account)
    visit = session.execute(
        select(VerifiedVisit).where(
            VerifiedVisit.visit_id == visit_id, VerifiedVisit.doctor_id == profile.doctor_id
        )
    ).scalar_one_or_none()
    if visit is None:
        # Wrong owner and nonexistent are indistinguishable.
        raise api_error("visit_not_found")
    return profile, visit


def get_visit(
    session: Session, *, account: UserAccount, visit_id: str
) -> dict[str, object]:
    _profile, visit = _owned_visit(session, account=account, visit_id=visit_id)
    return _visit_projection(visit)


def _invitation_status(invitation: PatientInvitation, clock: Clock) -> str:
    if invitation.consumed_at is not None:
        return constants.INVITATION_CONSUMED
    if invitation.revoked_at is not None:
        return constants.INVITATION_REVOKED
    if from_iso(invitation.expires_at) <= clock.now():
        return constants.INVITATION_EXPIRED
    return constants.INVITATION_ACTIVE


def _invitation_projection(invitation: PatientInvitation, clock: Clock) -> dict[str, object]:
    return {
        "invitation_id": invitation.invitation_id,
        "visit_id": invitation.visit_id,
        "status": _invitation_status(invitation, clock),
        "issued_at": invitation.issued_at,
        "expires_at": invitation.expires_at,
        "consumed_at": invitation.consumed_at,
        "revoked_at": invitation.revoked_at,
        "attempt_count": invitation.attempt_count,
        "max_attempts": invitation.max_attempts,
    }


def _expire_stale(session: Session, *, clock: Clock, visit_id: str) -> None:
    """Mark any lapsed invitation as expired by revoking it (terminal, auditable)."""
    rows = session.execute(
        select(PatientInvitation).where(
            PatientInvitation.visit_id == visit_id,
            PatientInvitation.consumed_at.is_(None),
            PatientInvitation.revoked_at.is_(None),
        )
    ).scalars().all()
    now = clock.now()
    now_iso = to_iso(now)
    changed = False
    for row in rows:
        if from_iso(row.expires_at) <= now:
            row.revoked_at = now_iso
            row.revoked_reason = "expired"
            changed = True
    if changed:
        # Persist the expiry before re-reading the active set, so a lapsed
        # invitation cannot mask the issuance of its replacement.
        session.flush()


def issue_invitation(
    session: Session,
    *,
    clock: Clock,
    settings: Term1Settings,
    account: UserAccount,
    visit_id: str,
    subject_identifier: str,
    ttl_seconds: int | None,
) -> dict[str, object]:
    _profile, visit = _owned_visit(session, account=account, visit_id=visit_id)

    ttl = constants.INVITATION_TTL_DEFAULT_SECONDS if ttl_seconds is None else int(ttl_seconds)
    if ttl < constants.INVITATION_TTL_MIN_SECONDS or ttl > constants.INVITATION_TTL_MAX_SECONDS:
        raise api_error("validation_failed")

    normalized = crypto.normalize_demo_identifier(subject_identifier)
    if normalized is None:
        raise api_error("invalid_demo_identifier")
    verify_or_activate(session, settings=settings, clock=clock, write=True)
    binding = compute_binding(settings, normalized)

    # The subject must be the identity attested for this visit. A mismatch (or a
    # key id drift) is refused before any invitation row is created.
    mismatch = not crypto.constant_time_equals(
        binding.identifier_hmac, visit.subject_identifier_hmac
    ) or binding.identifier_key_id != visit.identifier_key_id
    if mismatch:
        record(
            session,
            clock=clock,
            event_type=constants.EVENT_INVITATION_ATTEMPT_FAILED,
            outcome=constants.OUTCOME_DENIED,
            subject_type=constants.SUBJECT_VERIFIED_VISIT,
            subject_id=visit.visit_id,
            actor_user_id=account.user_id,
            code="subject_mismatch",
        )
        raise api_error("invalid_invitation")

    _expire_stale(session, clock=clock, visit_id=visit.visit_id)
    active = session.execute(
        select(PatientInvitation).where(
            PatientInvitation.visit_id == visit.visit_id,
            PatientInvitation.consumed_at.is_(None),
            PatientInvitation.revoked_at.is_(None),
        )
    ).scalars().all()
    if active:
        raise api_error("invitation_already_active")

    access_code = crypto.new_invitation_code()
    invitation = PatientInvitation(
        invitation_id=str(uuid.uuid4()),
        visit_id=visit.visit_id,
        issued_by_user_id=account.user_id,
        token_verifier_sha256=crypto.invitation_verifier(access_code),
        subject_identifier_hmac=visit.subject_identifier_hmac,
        identifier_key_id=visit.identifier_key_id,
        issued_at=clock.now_iso(),
        expires_at=clock.plus(ttl),
        consumed_at=None,
        revoked_at=None,
        attempt_count=0,
        max_attempts=constants.INVITATION_MAX_ATTEMPTS,
        revoked_reason=None,
    )
    session.add(invitation)
    record(
        session,
        clock=clock,
        event_type=constants.EVENT_INVITATION_ISSUED,
        outcome=constants.OUTCOME_SUCCESS,
        subject_type=constants.SUBJECT_INVITATION,
        subject_id=invitation.invitation_id,
        actor_user_id=account.user_id,
        payload={"visit_id": visit.visit_id, "ttl_seconds": ttl},
    )
    projection = _invitation_projection(invitation, clock)
    projection["access_code"] = access_code  # disclosed exactly once
    projection["expires_at"] = invitation.expires_at
    return projection


def revoke_invitation(
    session: Session,
    *,
    clock: Clock,
    account: UserAccount,
    invitation_id: str,
    reason_code: str,
) -> dict[str, object]:
    profile = require_doctor(session, account=account)
    reason = reason_code.strip()
    if not reason or len(reason) > 64:
        raise api_error("validation_failed")
    invitation = session.execute(
        select(PatientInvitation)
        .join(VerifiedVisit, PatientInvitation.visit_id == VerifiedVisit.visit_id)
        .where(
            PatientInvitation.invitation_id == invitation_id,
            VerifiedVisit.doctor_id == profile.doctor_id,
        )
    ).scalar_one_or_none()
    if invitation is None:
        raise api_error("invitation_not_found")
    if invitation.consumed_at is not None:
        # A consumed invitation is permanently consumed: never reopened.
        raise api_error("concurrency_conflict")
    if invitation.revoked_at is None:
        invitation.revoked_at = clock.now_iso()
        invitation.revoked_reason = reason
        record(
            session,
            clock=clock,
            event_type=constants.EVENT_INVITATION_REVOKED,
            outcome=constants.OUTCOME_SUCCESS,
            subject_type=constants.SUBJECT_INVITATION,
            subject_id=invitation.invitation_id,
            actor_user_id=account.user_id,
            payload={"reason_code": reason},
        )
    return {
        "invitation_id": invitation.invitation_id,
        "revoked_at": invitation.revoked_at,
        "status": _invitation_status(invitation, clock),
    }


def get_invitation(
    session: Session, *, clock: Clock, account: UserAccount, invitation_id: str
) -> dict[str, object]:
    profile = require_doctor(session, account=account)
    invitation = session.execute(
        select(PatientInvitation)
        .join(VerifiedVisit, PatientInvitation.visit_id == VerifiedVisit.visit_id)
        .where(
            PatientInvitation.invitation_id == invitation_id,
            VerifiedVisit.doctor_id == profile.doctor_id,
        )
    ).scalar_one_or_none()
    if invitation is None:
        raise api_error("invitation_not_found")
    # Status inspection never discloses the access code.
    return _invitation_projection(invitation, clock)
