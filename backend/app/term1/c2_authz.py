"""Shared C2 authorization guards (Track 1-owned; imported by Track 2).

Frozen in ``docs/term1/TERM1_C2_SHARED_INTERFACE_RECONCILIATION_20261128.md``
§7: every clinical C2 operation authorizes through these helpers so consent,
assignment and role semantics stay identical across H1b/S1/S2/S3 and the
Track 2 document/OCR routes.

* writes require active ``synthetic_demo`` consent (``403 consent_required``);
* S1 additionally requires the caller's exact active assignment
  (``404 assignment_not_found`` / ``409 assignment_already_revoked``);
* ``ADMIN`` never touches clinical content
  (``403 admin_clinical_content_forbidden``), other wrong roles get the
  generic ``403 forbidden``;
* a missing patient profile for a patient-role account is
  ``409 role_profile_mismatch``.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import constants
from .errors import api_error
from .models import (
    ConsentRecord,
    DoctorPatientAssignment,
    PatientProfile,
    UserAccount,
)


def require_clinical_patient(session: Session, *, account: UserAccount) -> PatientProfile:
    """Role gate for patient-owned clinical routes; returns the patient profile."""
    if account.role == constants.ROLE_ADMIN:
        raise api_error("admin_clinical_content_forbidden")
    if account.role != constants.ROLE_PATIENT:
        raise api_error("forbidden")
    profile = session.execute(
        select(PatientProfile).where(PatientProfile.user_id == account.user_id)
    ).scalar_one_or_none()
    if profile is None:
        raise api_error("role_profile_mismatch")
    return profile


def require_active_consent(session: Session, *, patient_id: str) -> ConsentRecord:
    """Active synthetic-demo consent, or ``403 consent_required``.

    Self-read H1a and pure reads (S2/S3) never call this (OQ-H1A).
    """
    consent = session.execute(
        select(ConsentRecord).where(
            ConsentRecord.patient_id == patient_id,
            ConsentRecord.revoked_at.is_(None),
        )
    ).scalar_one_or_none()
    if consent is None:
        raise api_error("consent_required")
    return consent


def require_owned_assignment(
    session: Session,
    *,
    assignment_id: str,
    patient_id: str,
    allow_revoked: bool = False,
) -> DoctorPatientAssignment:
    """The caller's own assignment.

    Unknown id or another patient's assignment are the identical
    ``404 assignment_not_found`` (no IDOR oracle). A revoked assignment is
    ``409 assignment_already_revoked`` unless ``allow_revoked`` — S2 doctor
    reads treat a revoked assignment as not-owned (404).
    """
    assignment = session.execute(
        select(DoctorPatientAssignment).where(
            DoctorPatientAssignment.assignment_id == assignment_id
        )
    ).scalar_one_or_none()
    if assignment is None or assignment.patient_id != patient_id:
        raise api_error("assignment_not_found")
    if assignment.revoked_at is not None and not allow_revoked:
        raise api_error("assignment_already_revoked")
    return assignment


def active_consent_exists(session: Session, *, patient_id: str) -> bool:
    """Non-raising probe used by live idempotent-replay reauthorization."""
    row = session.execute(
        select(ConsentRecord.consent_id).where(
            ConsentRecord.patient_id == patient_id,
            ConsentRecord.revoked_at.is_(None),
        )
    ).first()
    return row is not None
