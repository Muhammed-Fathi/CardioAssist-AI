"""Atomic patient registration, existing-account linking and assignments (C1.6/C1.7).

Registration is one business transaction. On success it contains: invitation
verification, conditional consumption, identity match, account + identity +
profile creation, assignment, initial patient-wide synthetic-demo consent, the
redemption record, an initial session, the workflow audit row and the durable
idempotency row. Any failure rolls the whole effect back, and failed-attempt
evidence is then written in a separate transaction so it survives.

Linking binds an *existing* patient account to a second doctor through a new
invitation for the same canonical subject. It never creates an account,
identity, profile or consent; a new assignment only. Consent is never recreated
by a replay or by a second doctor: the single active-consent rule is enforced by
a partial unique index.

Assignment revocation is local to one assignment. Patient-wide consent
withdrawal is a separate operation (``revoke_consent``).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import constants, crypto
from .accounts import find_account_by_email
from .audit import record
from .errors import api_error
from .identity import compute_binding, verify_or_activate
from .models import (
    ConsentRecord,
    DoctorPatientAssignment,
    DoctorProfile,
    InvitationAttempt,
    InvitationRedemption,
    PatientIdentity,
    PatientInvitation,
    PatientProfile,
    UserAccount,
    VerifiedVisit,
)
from .sessions import _issue_session
from .settings import Term1Settings
from .timeutil import Clock, from_iso


# --- invitation lookup --------------------------------------------------------
def find_invitation_by_code(session: Session, access_code: str) -> PatientInvitation | None:
    verifier = crypto.invitation_verifier(access_code)
    return session.execute(
        select(PatientInvitation).where(PatientInvitation.token_verifier_sha256 == verifier)
    ).scalar_one_or_none()


def invitation_is_usable(invitation: PatientInvitation, now) -> bool:
    return (
        invitation.consumed_at is None
        and invitation.revoked_at is None
        and from_iso(invitation.expires_at) > now
        and invitation.attempt_count < invitation.max_attempts
    )


def record_failure(
    session: Session,
    *,
    clock: Clock,
    invitation: PatientInvitation | None,
    code_digest: str,
    outcome: str,
) -> None:
    """Durable attempt evidence (written by the caller after rollback).

    A consumed invitation is never re-marked as revoked: consumption is
    permanent and the ``consumed_at IS NULL OR revoked_at IS NULL`` constraint
    forbids the pair. Only an unconsumed, unrevoked invitation accumulates
    attempts and is revoked only when its own limit is exhausted.
    """
    now = clock.now_iso()
    if (
        invitation is not None
        and invitation.consumed_at is None
        and invitation.revoked_at is None
    ):
        invitation.attempt_count = min(invitation.attempt_count + 1, invitation.max_attempts)
        if invitation.attempt_count >= invitation.max_attempts:
            invitation.revoked_at = now
            invitation.revoked_reason = "attempts_exhausted"
    session.add(
        InvitationAttempt(
            attempt_id=str(uuid.uuid4()),
            invitation_id=invitation.invitation_id if invitation is not None else None,
            bucket_key_hash=code_digest,
            outcome_code=outcome,
            created_at=now,
        )
    )


# --- shared validation --------------------------------------------------------
def _validate_enrollment_inputs(
    *, access_code: str, normalized: str, email_norm: str, password: str
) -> None:
    if not access_code or len(access_code) < 32 or len(access_code) > 256:
        raise api_error("invalid_invitation")
    if crypto.password_problem(password) is not None:
        raise api_error("password_policy_violation")
    if not crypto.is_synthetic_email(email_norm):
        raise api_error("invalid_demo_identifier")


def _enforce_subject_binding(
    settings: Term1Settings, invitation: PatientInvitation, normalized: str
) -> str:
    binding = compute_binding(settings, normalized)
    if binding.identifier_key_id != invitation.identifier_key_id:
        raise api_error("identity_key_change_unsupported")
    if not crypto.constant_time_equals(binding.identifier_hmac, invitation.subject_identifier_hmac):
        raise api_error("invalid_invitation")
    return binding.canonical_subject_id


def register_patient(
    session: Session,
    *,
    clock: Clock,
    settings: Term1Settings,
    access_code: str,
    identifier: str,
    email: str,
    password: str,
    consent_ack: bool,
) -> dict[str, object]:
    """New-patient enrollment; a single atomic business transaction."""
    normalized = crypto.normalize_demo_identifier(identifier)
    email_norm = crypto.normalize_email(email)
    if normalized is None:
        raise api_error("invalid_demo_identifier")
    if not consent_ack:
        raise api_error("validation_failed")
    if email_norm is None:
        raise api_error("invalid_demo_identifier")
    _validate_enrollment_inputs(
        access_code=access_code, normalized=normalized, email_norm=email_norm, password=password
    )

    invitation = find_invitation_by_code(session, access_code)
    now = clock.now()
    if invitation is None or not invitation_is_usable(invitation, now):
        raise api_error("invalid_invitation")

    verify_or_activate(session, settings=settings, clock=clock, write=True)
    canonical = _enforce_subject_binding(settings, invitation, normalized)
    binding = compute_binding(settings, normalized)

    # Email uniqueness is checked first: a duplicate account is reported
    # generically whether or not the identity also already exists.
    if find_account_by_email(session, email_norm) is not None:
        raise api_error("account_registration_unavailable")
    existing_identity = session.execute(
        select(PatientIdentity).where(PatientIdentity.canonical_subject_id == canonical)
    ).scalar_one_or_none()
    if existing_identity is not None:
        # One account per identity: a second new-patient registration must use
        # the authenticated link flow instead.
        raise api_error("subject_identity_conflict")

    kdf = crypto.hash_password(password)
    account = UserAccount(
        user_id=str(uuid.uuid4()),
        email_norm=email_norm,
        role=constants.ROLE_PATIENT,
        status=constants.STATUS_ACTIVE,
        password_alg=str(kdf["password_alg"]),
        password_version=int(kdf["password_version"]),
        password_iterations=int(kdf["password_iterations"]),
        password_salt_b64=str(kdf["password_salt_b64"]),
        password_verifier_b64=str(kdf["password_verifier_b64"]),
        password_change_required=False,
        status_reason_code=None,
        created_at=clock.now_iso(),
        password_changed_at=clock.now_iso(),
        status_changed_at=None,
        last_login_at=None,
    )
    session.add(account)

    identity = PatientIdentity(
        identity_id=str(uuid.uuid4()),
        identifier_key_id=binding.identifier_key_id,
        identifier_hmac=binding.identifier_hmac,
        canonical_subject_id=canonical,
        subject_label=binding.subject_label,
        created_at=clock.now_iso(),
    )
    session.add(identity)

    profile = PatientProfile(
        patient_id=str(uuid.uuid4()),
        user_id=account.user_id,
        patient_identity_id=identity.identity_id,
        display_label=binding.subject_label,
        created_at=clock.now_iso(),
    )
    session.add(profile)

    visit = session.execute(
        select(VerifiedVisit).where(VerifiedVisit.visit_id == invitation.visit_id)
    ).scalar_one()
    _require_usable_doctor(session, visit.doctor_id)
    assignment = _active_or_new_assignment(
        session, clock=clock, doctor_id=visit.doctor_id, patient_id=profile.patient_id
    )
    consent = ConsentRecord(
        consent_id=str(uuid.uuid4()),
        patient_id=profile.patient_id,
        kind=constants.CONSENT_KIND_SYNTHETIC_DEMO,
        scope=constants.CONSENT_SCOPE_PATIENT_WIDE,
        acknowledged_at=clock.now_iso(),
        revoked_at=None,
        revoked_reason=None,
        contract_version=constants.CONSENT_CONTRACT_VERSION,
    )
    session.add(consent)

    _consume_invitation(session, clock=clock, invitation=invitation, patient_id=profile.patient_id, assignment_id=assignment.assignment_id, flow=constants.REDEMPTION_FLOW_REGISTER)

    session_row, token = _issue_session(session, clock=clock, account=account)
    record(
        session,
        clock=clock,
        event_type=constants.EVENT_PATIENT_REGISTERED,
        outcome=constants.OUTCOME_SUCCESS,
        subject_type=constants.SUBJECT_PATIENT_PROFILE,
        subject_id=profile.patient_id,
        actor_user_id=account.user_id,
        payload={
            "assignment_id": assignment.assignment_id,
            "consent_id": consent.consent_id,
            "invitation_id": invitation.invitation_id,
        },
    )
    return {
        "user_id": account.user_id,
        "patient_id": profile.patient_id,
        "assignment_id": assignment.assignment_id,
        "session_id": session_row.session_id,
        "session_token": token,
        "expires_at": session_row.expires_at,
        "subject_label": binding.subject_label,
    }


def link_patient(
    session: Session,
    *,
    clock: Clock,
    settings: Term1Settings,
    account: UserAccount,
    access_code: str,
    identifier: str,
    accept_linking: bool,
) -> dict[str, object]:
    """Authenticated enrollment: attach an existing patient to another doctor."""
    if account.role != constants.ROLE_PATIENT:
        raise api_error("forbidden")
    if not accept_linking:
        raise api_error("validation_failed")
    if not access_code or len(access_code) < 32 or len(access_code) > 256:
        raise api_error("invalid_invitation")
    normalized = crypto.normalize_demo_identifier(identifier)
    if normalized is None:
        raise api_error("invalid_demo_identifier")

    profile = session.execute(
        select(PatientProfile).where(PatientProfile.user_id == account.user_id)
    ).scalar_one_or_none()
    if profile is None:
        raise api_error("role_profile_mismatch")
    identity = session.execute(
        select(PatientIdentity).where(PatientIdentity.identity_id == profile.patient_identity_id)
    ).scalar_one()

    invitation = find_invitation_by_code(session, access_code)
    now = clock.now()
    if invitation is None or not invitation_is_usable(invitation, now):
        raise api_error("invalid_invitation")

    verify_or_activate(session, settings=settings, clock=clock, write=True)
    canonical = _enforce_subject_binding(settings, invitation, normalized)
    # Compare the blind canonical subject, never two differently keyed HMACs.
    if not crypto.constant_time_equals(canonical, identity.canonical_subject_id):
        raise api_error("invalid_invitation")

    visit = session.execute(
        select(VerifiedVisit).where(VerifiedVisit.visit_id == invitation.visit_id)
    ).scalar_one()
    _require_usable_doctor(session, visit.doctor_id)
    assignment = _active_or_new_assignment(
        session, clock=clock, doctor_id=visit.doctor_id, patient_id=profile.patient_id
    )
    _consume_invitation(
        session,
        clock=clock,
        invitation=invitation,
        patient_id=profile.patient_id,
        assignment_id=assignment.assignment_id,
        flow=constants.REDEMPTION_FLOW_LINK,
    )
    doctor = session.execute(
        select(DoctorProfile).where(DoctorProfile.doctor_id == visit.doctor_id)
    ).scalar_one()
    record(
        session,
        clock=clock,
        event_type=constants.EVENT_PATIENT_LINKED,
        outcome=constants.OUTCOME_SUCCESS,
        subject_type=constants.SUBJECT_ASSIGNMENT,
        subject_id=assignment.assignment_id,
        actor_user_id=account.user_id,
        payload={"invitation_id": invitation.invitation_id, "patient_id": profile.patient_id},
    )
    return {
        "assignment_id": assignment.assignment_id,
        "doctor_label": doctor.display_name,
        "assigned_at": assignment.assigned_at,
        "patient_id": profile.patient_id,
    }


def _require_usable_doctor(session: Session, doctor_id: str) -> DoctorProfile:
    """The destination doctor must be active and usable; suspensions and
    disabilities fail closed before any assignment or consumption is created."""
    doctor = session.execute(
        select(DoctorProfile).where(DoctorProfile.doctor_id == doctor_id)
    ).scalar_one_or_none()
    if doctor is None or not doctor.active:
        raise api_error("forbidden")
    account = session.execute(
        select(UserAccount).where(UserAccount.user_id == doctor.user_id)
    ).scalar_one_or_none()
    if account is None or account.status != constants.STATUS_ACTIVE:
        raise api_error("forbidden")
    return doctor


def _active_or_new_assignment(
    session: Session, *, clock: Clock, doctor_id: str, patient_id: str
) -> DoctorPatientAssignment:
    existing = session.execute(
        select(DoctorPatientAssignment).where(
            DoctorPatientAssignment.doctor_id == doctor_id,
            DoctorPatientAssignment.patient_id == patient_id,
            DoctorPatientAssignment.revoked_at.is_(None),
        )
    ).scalar_one_or_none()
    if existing is not None:
        # Repeat visit: the pair already has one active assignment.
        return existing
    assignment = DoctorPatientAssignment(
        assignment_id=str(uuid.uuid4()),
        doctor_id=doctor_id,
        patient_id=patient_id,
        assigned_at=clock.now_iso(),
        revoked_at=None,
        revoked_by_user_id=None,
        revoked_by_role=None,
        reason_code=None,
    )
    session.add(assignment)
    session.flush()
    return assignment


def _consume_invitation(
    session: Session,
    *,
    clock: Clock,
    invitation: PatientInvitation,
    patient_id: str,
    assignment_id: str,
    flow: str,
) -> None:
    """Conditional consumption: exactly-one-winner semantics.

    Expiry is rechecked at the authoritative consumption boundary (defence in
    depth for the concurrent exactly-one-winner race): a lapsed invitation is
    never consumed, even if an earlier usability check passed.
    """
    now_iso = clock.now_iso()
    if invitation.consumed_at is not None or invitation.revoked_at is not None:
        raise api_error("invalid_invitation")
    if from_iso(invitation.expires_at) <= clock.now():
        raise api_error("invalid_invitation")
    invitation.consumed_at = now_iso
    session.add(
        InvitationRedemption(
            redemption_id=str(uuid.uuid4()),
            invitation_id=invitation.invitation_id,
            patient_id=patient_id,
            assignment_id=assignment_id,
            redeemed_at=now_iso,
            flow=flow,
        )
    )
    record(
        session,
        clock=clock,
        event_type=constants.EVENT_INVITATION_CONSUMED,
        outcome=constants.OUTCOME_SUCCESS,
        subject_type=constants.SUBJECT_INVITATION,
        subject_id=invitation.invitation_id,
        payload={"flow": flow, "assignment_id": assignment_id},
    )


# --- assignments --------------------------------------------------------------
def list_assignments(
    session: Session, *, account: UserAccount
) -> dict[str, object]:
    if account.role != constants.ROLE_PATIENT:
        raise api_error("forbidden")
    profile = session.execute(
        select(PatientProfile).where(PatientProfile.user_id == account.user_id)
    ).scalar_one_or_none()
    if profile is None:
        raise api_error("role_profile_mismatch")
    rows = session.execute(
        select(DoctorPatientAssignment, DoctorProfile)
        .join(DoctorProfile, DoctorPatientAssignment.doctor_id == DoctorProfile.doctor_id)
        .where(DoctorPatientAssignment.patient_id == profile.patient_id)
        .order_by(DoctorPatientAssignment.assigned_at.desc())
    ).all()
    return {
        "assignments": [
            {
                "assignment_id": assignment.assignment_id,
                "doctor_label": doctor.display_name,
                "active": assignment.revoked_at is None,
                "assigned_at": assignment.assigned_at,
                "revoked_at": assignment.revoked_at,
            }
            for assignment, doctor in rows
        ]
    }


def _assignment_for_update(
    session: Session, *, assignment_id: str, patient_id: str | None, doctor_id: str | None
) -> DoctorPatientAssignment:
    conditions = [DoctorPatientAssignment.assignment_id == assignment_id]
    if patient_id is not None:
        conditions.append(DoctorPatientAssignment.patient_id == patient_id)
    if doctor_id is not None:
        conditions.append(DoctorPatientAssignment.doctor_id == doctor_id)
    assignment = session.execute(
        select(DoctorPatientAssignment).where(*conditions)
    ).scalar_one_or_none()
    if assignment is None:
        raise api_error("assignment_not_found")
    return assignment


def _mark_revoked(
    session: Session,
    *,
    clock: Clock,
    assignment: DoctorPatientAssignment,
    actor: UserAccount,
    reason_code: str,
) -> None:
    reason = reason_code.strip()
    if not reason or len(reason) > 64:
        raise api_error("validation_failed")
    if assignment.revoked_at is not None:
        raise api_error("assignment_already_revoked")
    assignment.revoked_at = clock.now_iso()
    assignment.revoked_by_user_id = actor.user_id
    assignment.revoked_by_role = actor.role
    assignment.reason_code = reason
    record(
        session,
        clock=clock,
        event_type=constants.EVENT_ASSIGNMENT_REVOKED,
        outcome=constants.OUTCOME_SUCCESS,
        subject_type=constants.SUBJECT_ASSIGNMENT,
        subject_id=assignment.assignment_id,
        actor_user_id=actor.user_id,
        payload={"by_role": actor.role, "reason_code": reason},
    )


def revoke_assignment_as_doctor(
    session: Session,
    *,
    clock: Clock,
    account: UserAccount,
    assignment_id: str,
    reason_code: str,
) -> dict[str, object]:
    from .visits import require_doctor

    profile = require_doctor(session, account=account)
    assignment = _assignment_for_update(
        session, assignment_id=assignment_id, patient_id=None, doctor_id=profile.doctor_id
    )
    _mark_revoked(
        session, clock=clock, assignment=assignment, actor=account, reason_code=reason_code
    )
    return {"assignment_id": assignment.assignment_id, "revoked_at": assignment.revoked_at}


def revoke_assignment_as_patient(
    session: Session,
    *,
    clock: Clock,
    account: UserAccount,
    assignment_id: str,
    reason_code: str,
) -> dict[str, object]:
    if account.role != constants.ROLE_PATIENT:
        raise api_error("forbidden")
    profile = session.execute(
        select(PatientProfile).where(PatientProfile.user_id == account.user_id)
    ).scalar_one_or_none()
    if profile is None:
        raise api_error("role_profile_mismatch")
    assignment = _assignment_for_update(
        session, assignment_id=assignment_id, patient_id=profile.patient_id, doctor_id=None
    )
    _mark_revoked(
        session, clock=clock, assignment=assignment, actor=account, reason_code=reason_code
    )
    return {"assignment_id": assignment.assignment_id, "revoked_at": assignment.revoked_at}


def revoke_consent(
    session: Session, *, clock: Clock, account: UserAccount, reason_code: str
) -> dict[str, object]:
    """Patient-wide synthetic-demo consent withdrawal (distinct from E4/E5)."""
    if account.role != constants.ROLE_PATIENT:
        raise api_error("forbidden")
    profile = session.execute(
        select(PatientProfile).where(PatientProfile.user_id == account.user_id)
    ).scalar_one_or_none()
    if profile is None:
        raise api_error("role_profile_mismatch")
    reason = reason_code.strip()
    if not reason or len(reason) > 64:
        raise api_error("validation_failed")
    consent = session.execute(
        select(ConsentRecord).where(
            ConsentRecord.patient_id == profile.patient_id, ConsentRecord.revoked_at.is_(None)
        )
    ).scalar_one_or_none()
    if consent is None:
        raise api_error("consent_not_found")
    consent.revoked_at = clock.now_iso()
    consent.revoked_reason = reason
    record(
        session,
        clock=clock,
        event_type=constants.EVENT_CONSENT_REVOKED,
        outcome=constants.OUTCOME_SUCCESS,
        subject_type=constants.SUBJECT_CONSENT,
        subject_id=consent.consent_id,
        actor_user_id=account.user_id,
        payload={"reason_code": reason, "scope": consent.scope},
    )
    return {"consent_id": consent.consent_id, "revoked_at": consent.revoked_at}
