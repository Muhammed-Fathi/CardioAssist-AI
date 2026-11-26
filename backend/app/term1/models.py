"""C1 data model: accounts, identity, sessions, visits, invitations, consent.

Scope is exactly C1.1 of the stage assignment. The three legacy monitoring
tables (``monitoring_observation``, ``monitoring_metric``, ``audit_event``) are
imported from :mod:`backend.app.storage.models` and are unchanged; the workflow
audit here is a separate table and never reuses ``audit_event``.

Design notes that the constraints encode:

* No ``patient.doctor_id`` exists anywhere (R-01). Doctor access is derived from
  ``doctor_patient_assignment`` rows, one active row per doctor/patient pair.
* ``user_account.email_norm`` is the only login identifier and is UNIQUE.
* ``patient_identity`` stores blind indexes only: a purpose-separated
  ``identifier_hmac`` and a key-version-independent ``canonical_subject_id``.
  No raw fictitious identifier is persisted.
* ``identity_key_check`` stores a non-secret verification value per
  ``(purpose, key_id)`` so that replacing key material under an unchanged key id
  is detectable before any identity-related write.
* ``patient_invitation`` stores a verifier digest only. ``consumed_at`` and
  ``revoked_at`` are mutually exclusive, and consumption is permanent.
* ``durable_idempotency`` is keyed by the complete actor/operation/target
  identity; no global lookup by key digest alone is possible.
* ``workflow_audit_event`` is metadata only: closed event/outcome codes, stable
  subject references, a payload digest, and no identifier or secret.
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..storage.models import Base  # same metadata: one Alembic target

ROLE_CHECK = "role IN ('admin','doctor','patient')"
STATUS_CHECK = "status IN ('ACTIVE','SUSPENDED','DISABLED')"
PURPOSE_CHECK = "purpose IN ('identity_match','subject_canonical')"
FLOW_CHECK = "flow IN ('register','link')"
ATTESTATION_CHECK = (
    "attestation_code IN ('PRIOR_IN_PERSON_VISIT_DEMO','PRIOR_TELEHEALTH_VISIT_DEMO')"
)
CONSENT_CHECK = "kind = 'synthetic_demo' AND scope = 'patient_wide_synthetic_demo'"
SCOPE_CHECK = "replay_scope IN ('user','anonymous')"
BUCKET_KIND_CHECK = "bucket_kind IN ('account','source')"
OUTCOME_CHECK = (
    "outcome IN ('SUCCESS','FAILED','DENIED','NOT_FOUND','CONFLICT','RATE_LIMITED')"
)


class UserAccount(Base):
    __tablename__ = "user_account"
    __table_args__ = (
        UniqueConstraint("email_norm", name="ux_user_account_email_norm"),
        CheckConstraint(ROLE_CHECK, name="ck_user_account_role"),
        CheckConstraint(STATUS_CHECK, name="ck_user_account_status"),
        CheckConstraint(
            "password_iterations >= 1 AND password_version >= 1",
            name="ck_user_account_kdf_parameters",
        ),
        Index("ix_user_account_status_role", "status", "role"),
    )

    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email_norm: Mapped[str] = mapped_column(String(254), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    password_alg: Mapped[str] = mapped_column(String(32), nullable=False)
    password_version: Mapped[int] = mapped_column(Integer, nullable=False)
    password_iterations: Mapped[int] = mapped_column(Integer, nullable=False)
    password_salt_b64: Mapped[str] = mapped_column(String(64), nullable=False)
    password_verifier_b64: Mapped[str] = mapped_column(String(64), nullable=False)
    password_change_required: Mapped[bool] = mapped_column(nullable=False)
    status_reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    password_changed_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status_changed_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_login_at: Mapped[str | None] = mapped_column(String(32), nullable=True)

    bootstrap_record: Mapped["AdminBootstrapRecord | None"] = relationship(
        "AdminBootstrapRecord", back_populates="account", uselist=False
    )


class DoctorProfile(Base):
    __tablename__ = "doctor_profile"
    __table_args__ = (
        UniqueConstraint("user_id", name="ux_doctor_profile_user"),
        Index("ix_doctor_profile_active", "active"),
    )

    doctor_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("user_account.user_id", ondelete="RESTRICT"), nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    active: Mapped[bool] = mapped_column(nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)

    account: Mapped["UserAccount"] = relationship("UserAccount")
    visits: Mapped[list["VerifiedVisit"]] = relationship("VerifiedVisit", back_populates="doctor")


class PatientIdentity(Base):
    """Blind, key-version-independent identity binding. No raw identifier."""

    __tablename__ = "patient_identity"
    __table_args__ = (
        UniqueConstraint("identifier_hmac", name="ux_patient_identity_hmac"),
        UniqueConstraint("canonical_subject_id", name="ux_patient_identity_subject"),
        Index("ix_patient_identity_key", "identifier_key_id"),
    )

    identity_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    identifier_key_id: Mapped[str] = mapped_column(String(64), nullable=False)
    identifier_hmac: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_subject_id: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_label: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)


class PatientProfile(Base):
    __tablename__ = "patient_profile"
    __table_args__ = (
        UniqueConstraint("user_id", name="ux_patient_profile_user"),
        UniqueConstraint("patient_identity_id", name="ux_patient_profile_identity"),
    )

    patient_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("user_account.user_id", ondelete="RESTRICT"), nullable=False
    )
    patient_identity_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("patient_identity.identity_id", ondelete="RESTRICT"),
        nullable=False,
    )
    display_label: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)

    account: Mapped["UserAccount"] = relationship("UserAccount")
    identity: Mapped["PatientIdentity"] = relationship("PatientIdentity")


class IdentityKeyCheck(Base):
    """Non-secret key-material binding; verified before identity writes."""

    __tablename__ = "identity_key_check"
    __table_args__ = (
        UniqueConstraint("purpose", "key_id", name="ux_identity_key_check_purpose_key"),
        UniqueConstraint("purpose", "key_check_hash", name="ux_identity_key_check_purpose_hash"),
        CheckConstraint(PURPOSE_CHECK, name="ck_identity_key_check_purpose"),
    )

    check_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    key_id: Mapped[str] = mapped_column(String(64), nullable=False)
    key_check_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    alg: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    activated_at: Mapped[str] = mapped_column(String(32), nullable=False)
    retired_at: Mapped[str | None] = mapped_column(String(32), nullable=True)


class Session(Base):
    __tablename__ = "session"
    __table_args__ = (
        UniqueConstraint("token_verifier_sha256", name="ux_session_token_verifier"),
        Index("ix_session_user_expires", "user_id", "expires_at"),
        Index("ix_session_user_revoked", "user_id", "revoked_at"),
    )

    session_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("user_account.user_id", ondelete="RESTRICT"), nullable=False
    )
    token_verifier_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    session_key_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    expires_at: Mapped[str] = mapped_column(String(32), nullable=False)
    last_seen_at: Mapped[str] = mapped_column(String(32), nullable=False)
    revoked_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)


class LoginAttempt(Base):
    """Durable failure counter rows, written outside the business transaction."""

    __tablename__ = "login_attempt"
    __table_args__ = (
        CheckConstraint(BUCKET_KIND_CHECK, name="ck_login_attempt_bucket_kind"),
        Index("ix_login_attempt_bucket_time", "bucket_key_hash", "created_at"),
        Index("ix_login_attempt_time", "created_at"),
    )

    attempt_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    bucket_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    bucket_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)


class VerifiedVisit(Base):
    __tablename__ = "verified_visit"
    __table_args__ = (
        UniqueConstraint("doctor_id", "visit_ref", name="ux_verified_visit_doctor_ref"),
        CheckConstraint(ATTESTATION_CHECK, name="ck_verified_visit_attestation"),
        Index("ix_verified_visit_doctor_time", "doctor_id", "attested_at"),
        Index("ix_verified_visit_subject", "identifier_key_id", "subject_identifier_hmac"),
    )

    visit_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    doctor_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("doctor_profile.doctor_id", ondelete="RESTRICT"), nullable=False
    )
    visit_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    subject_identifier_hmac: Mapped[str] = mapped_column(String(64), nullable=False)
    identifier_key_id: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_label: Mapped[str] = mapped_column(String(32), nullable=False)
    asserted_visit_at: Mapped[str] = mapped_column(String(32), nullable=False)
    attested_at: Mapped[str] = mapped_column(String(32), nullable=False)
    attestation_code: Mapped[str] = mapped_column(String(64), nullable=False)
    note_code: Mapped[str | None] = mapped_column(String(64), nullable=True)

    doctor: Mapped["DoctorProfile"] = relationship("DoctorProfile", back_populates="visits")
    invitations: Mapped[list["PatientInvitation"]] = relationship(
        "PatientInvitation", back_populates="visit"
    )


class PatientInvitation(Base):
    __tablename__ = "patient_invitation"
    __table_args__ = (
        UniqueConstraint("token_verifier_sha256", name="ux_patient_invitation_verifier"),
        CheckConstraint(
            "consumed_at IS NULL OR revoked_at IS NULL",
            name="ck_patient_invitation_not_consumed_and_revoked",
        ),
        CheckConstraint(
            "attempt_count >= 0 AND max_attempts >= 1 AND attempt_count <= max_attempts",
            name="ck_patient_invitation_attempts",
        ),
        Index("ix_patient_invitation_visit_expiry", "visit_id", "expires_at"),
        Index("ix_patient_invitation_subject", "identifier_key_id", "subject_identifier_hmac"),
        Index("ix_patient_invitation_issued_by", "issued_by_user_id"),
    )

    invitation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    visit_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("verified_visit.visit_id", ondelete="RESTRICT"), nullable=False
    )
    issued_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("user_account.user_id", ondelete="RESTRICT"), nullable=False
    )
    token_verifier_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_identifier_hmac: Mapped[str] = mapped_column(String(64), nullable=False)
    identifier_key_id: Mapped[str] = mapped_column(String(64), nullable=False)
    issued_at: Mapped[str] = mapped_column(String(32), nullable=False)
    expires_at: Mapped[str] = mapped_column(String(32), nullable=False)
    consumed_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    revoked_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    revoked_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)

    visit: Mapped["VerifiedVisit"] = relationship("VerifiedVisit", back_populates="invitations")


class InvitationAttempt(Base):
    """Durable attempt evidence; survives a rolled-back enrollment transaction.

    ``invitation_id`` is nullable on purpose: an unresolvable access code has no
    resource to reference, and the row must never contain the raw code.
    """

    __tablename__ = "invitation_attempt"
    __table_args__ = (
        Index("ix_invitation_attempt_invitation_time", "invitation_id", "created_at"),
        Index("ix_invitation_attempt_bucket_time", "bucket_key_hash", "created_at"),
    )

    attempt_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    invitation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("patient_invitation.invitation_id", ondelete="RESTRICT"), nullable=True
    )
    bucket_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome_code: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)

    invitation: Mapped["PatientInvitation | None"] = relationship("PatientInvitation")


class DoctorPatientAssignment(Base):
    __tablename__ = "doctor_patient_assignment"
    __table_args__ = (
        Index(
            "ux_doctor_patient_assignment_active_pair",
            "doctor_id",
            "patient_id",
            unique=True,
            sqlite_where=text("revoked_at IS NULL"),
        ),
        Index("ix_doctor_patient_assignment_patient_active", "patient_id", "revoked_at"),
        Index("ix_doctor_patient_assignment_doctor_active", "doctor_id", "revoked_at"),
    )

    assignment_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    doctor_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("doctor_profile.doctor_id", ondelete="RESTRICT"), nullable=False
    )
    patient_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("patient_profile.patient_id", ondelete="RESTRICT"), nullable=False
    )
    assigned_at: Mapped[str] = mapped_column(String(32), nullable=False)
    revoked_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    revoked_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("user_account.user_id", ondelete="RESTRICT"), nullable=True
    )
    revoked_by_role: Mapped[str | None] = mapped_column(String(16), nullable=True)
    reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)

    doctor: Mapped["DoctorProfile"] = relationship("DoctorProfile")
    patient: Mapped["PatientProfile"] = relationship("PatientProfile")


class ConsentRecord(Base):
    """One active patient-wide synthetic-demo consent per patient."""

    __tablename__ = "consent_record"
    __table_args__ = (
        CheckConstraint(CONSENT_CHECK, name="ck_consent_record_kind_scope"),
        Index(
            "ux_consent_record_active_patient",
            "patient_id",
            unique=True,
            sqlite_where=text("revoked_at IS NULL"),
        ),
        Index("ix_consent_record_patient", "patient_id", "acknowledged_at"),
    )

    consent_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    patient_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("patient_profile.patient_id", ondelete="RESTRICT"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    scope: Mapped[str] = mapped_column(String(48), nullable=False)
    acknowledged_at: Mapped[str] = mapped_column(String(32), nullable=False)
    revoked_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    contract_version: Mapped[str] = mapped_column(String(64), nullable=False)

    patient: Mapped["PatientProfile"] = relationship("PatientProfile")


class InvitationRedemption(Base):
    __tablename__ = "invitation_redemption"
    __table_args__ = (
        UniqueConstraint("invitation_id", name="ux_invitation_redemption_invitation"),
        CheckConstraint(FLOW_CHECK, name="ck_invitation_redemption_flow"),
        Index("ix_invitation_redemption_assignment", "assignment_id"),
        Index("ix_invitation_redemption_patient", "patient_id", "redeemed_at"),
    )

    redemption_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    invitation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("patient_invitation.invitation_id", ondelete="RESTRICT"), nullable=False
    )
    patient_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("patient_profile.patient_id", ondelete="RESTRICT"), nullable=False
    )
    assignment_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("doctor_patient_assignment.assignment_id", ondelete="RESTRICT"),
        nullable=False,
    )
    redeemed_at: Mapped[str] = mapped_column(String(32), nullable=False)
    flow: Mapped[str] = mapped_column(String(16), nullable=False)

    invitation: Mapped["PatientInvitation"] = relationship("PatientInvitation")
    patient: Mapped["PatientProfile"] = relationship("PatientProfile")
    assignment: Mapped["DoctorPatientAssignment"] = relationship("DoctorPatientAssignment")


class DurableIdempotency(Base):
    """Actor/operation/target-bound replay record with no secret material."""

    __tablename__ = "durable_idempotency"
    __table_args__ = (
        UniqueConstraint(
            "replay_scope",
            "key_hash",
            "actor_binding",
            "operation",
            "target_ref",
            name="ux_durable_idempotency_identity",
        ),
        CheckConstraint(SCOPE_CHECK, name="ck_durable_idempotency_scope"),
        Index("ix_durable_idempotency_expiry", "expires_at"),
        Index("ix_durable_idempotency_actor", "actor_binding", "operation"),
    )

    replay_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    replay_scope: Mapped[str] = mapped_column(String(16), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_binding: Mapped[str] = mapped_column(String(96), nullable=False)
    operation: Mapped[str] = mapped_column(String(96), nullable=False)
    target_ref: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    secret_fingerprints_json: Mapped[object] = mapped_column(JSON, nullable=False)
    response_public_json: Mapped[object] = mapped_column(JSON, nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    expires_at: Mapped[str] = mapped_column(String(32), nullable=False)
    secret_disclosed: Mapped[bool] = mapped_column(nullable=False)


class WorkflowAuditEvent(Base):
    """Metadata-only workflow audit; NOT a database-level immutable guarantee.

    SQLite cannot provide PostgreSQL GRANT/REVOKE protection, so append-only
    behaviour here is an application-layer property. The table is deliberately
    separate from the legacy monitoring ``audit_event`` table.
    """

    __tablename__ = "workflow_audit_event"
    __table_args__ = (
        CheckConstraint(OUTCOME_CHECK, name="ck_workflow_audit_outcome"),
        Index("ix_workflow_audit_subject_time", "subject_type", "subject_id", "recorded_at"),
        Index("ix_workflow_audit_actor_time", "actor_user_id", "recorded_at"),
        Index("ix_workflow_audit_event_time", "event_type", "recorded_at"),
        Index("ix_workflow_audit_request", "request_id"),
    )

    audit_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    subject_type: Mapped[str] = mapped_column(String(40), nullable=False)
    subject_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # Safe correlation identifiers only (never a bearer token or secret).
    request_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    code: Mapped[str | None] = mapped_column(String(48), nullable=True)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    recorded_at: Mapped[str] = mapped_column(String(32), nullable=False)


class AdminBootstrapRecord(Base):
    """Single-row guard proving the one-time administrator bootstrap ran.

    The ORM relationship is declared so the unit of work orders the guard row
    *after* its ``user_account`` parent; without it SQLAlchemy sorts by primary
    key (table name) and SQLite's immediate foreign-key enforcement rejects the
    insert. Auditing and redemption rows are ordered explicitly in ``tx``.
    """

    __tablename__ = "admin_bootstrap_record"

    bootstrap_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("user_account.user_id", ondelete="RESTRICT"), nullable=False
    )
    account: Mapped["UserAccount"] = relationship("UserAccount")
    email_norm: Mapped[str] = mapped_column(String(254), nullable=False)
    bootstrapped_at: Mapped[str] = mapped_column(String(32), nullable=False)


__all__ = [
    "AdminBootstrapRecord",
    "ConsentRecord",
    "DoctorPatientAssignment",
    "DoctorProfile",
    "DurableIdempotency",
    "IdentityKeyCheck",
    "InvitationAttempt",
    "InvitationRedemption",
    "LoginAttempt",
    "PatientIdentity",
    "PatientInvitation",
    "PatientProfile",
    "Session",
    "UserAccount",
    "VerifiedVisit",
    "WorkflowAuditEvent",
    "Text",
]
