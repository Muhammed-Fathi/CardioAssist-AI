"""C1.1b — verified prior visits, invitations and durable attempt evidence.

Revision ID: 20261126_03
Revises: 20261126_02
Create Date: 2026-11-26

``verified_visit`` -> ``patient_invitation`` -> ``invitation_attempt``.
``invitation_attempt.invitation_id`` is nullable so that an unresolvable access
code can be recorded durably without inventing a resource reference and without
ever persisting the raw code.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261126_03"
down_revision: Union[str, None] = "20261126_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "verified_visit",
        sa.Column("visit_id", sa.String(length=36), nullable=False),
        sa.Column("doctor_id", sa.String(length=36), nullable=False),
        sa.Column("visit_ref", sa.String(length=128), nullable=False),
        sa.Column("subject_identifier_hmac", sa.String(length=64), nullable=False),
        sa.Column("identifier_key_id", sa.String(length=64), nullable=False),
        sa.Column("subject_label", sa.String(length=32), nullable=False),
        sa.Column("asserted_visit_at", sa.String(length=32), nullable=False),
        sa.Column("attested_at", sa.String(length=32), nullable=False),
        sa.Column("attestation_code", sa.String(length=64), nullable=False),
        sa.Column("note_code", sa.String(length=64), nullable=True),
        sa.CheckConstraint(
            "attestation_code IN ('PRIOR_IN_PERSON_VISIT_DEMO','PRIOR_TELEHEALTH_VISIT_DEMO')",
            name="ck_verified_visit_attestation",
        ),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctor_profile.doctor_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("visit_id"),
        sa.UniqueConstraint("doctor_id", "visit_ref", name="ux_verified_visit_doctor_ref"),
    )
    op.create_index(
        "ix_verified_visit_doctor_time", "verified_visit", ["doctor_id", "attested_at"], unique=False
    )
    op.create_index(
        "ix_verified_visit_subject",
        "verified_visit",
        ["identifier_key_id", "subject_identifier_hmac"],
        unique=False,
    )

    op.create_table(
        "patient_invitation",
        sa.Column("invitation_id", sa.String(length=36), nullable=False),
        sa.Column("visit_id", sa.String(length=36), nullable=False),
        sa.Column("issued_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("token_verifier_sha256", sa.String(length=64), nullable=False),
        sa.Column("subject_identifier_hmac", sa.String(length=64), nullable=False),
        sa.Column("identifier_key_id", sa.String(length=64), nullable=False),
        sa.Column("issued_at", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.String(length=32), nullable=False),
        sa.Column("consumed_at", sa.String(length=32), nullable=True),
        sa.Column("revoked_at", sa.String(length=32), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("revoked_reason", sa.String(length=64), nullable=True),
        sa.CheckConstraint(
            "consumed_at IS NULL OR revoked_at IS NULL",
            name="ck_patient_invitation_not_consumed_and_revoked",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0 AND max_attempts >= 1 AND attempt_count <= max_attempts",
            name="ck_patient_invitation_attempts",
        ),
        sa.ForeignKeyConstraint(["visit_id"], ["verified_visit.visit_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["issued_by_user_id"], ["user_account.user_id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("invitation_id"),
        sa.UniqueConstraint("token_verifier_sha256", name="ux_patient_invitation_verifier"),
    )
    op.create_index(
        "ix_patient_invitation_visit_expiry",
        "patient_invitation",
        ["visit_id", "expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_patient_invitation_subject",
        "patient_invitation",
        ["identifier_key_id", "subject_identifier_hmac"],
        unique=False,
    )
    op.create_index(
        "ix_patient_invitation_issued_by", "patient_invitation", ["issued_by_user_id"], unique=False
    )

    op.create_table(
        "invitation_attempt",
        sa.Column("attempt_id", sa.String(length=36), nullable=False),
        sa.Column("invitation_id", sa.String(length=36), nullable=True),
        sa.Column("bucket_key_hash", sa.String(length=64), nullable=False),
        sa.Column("outcome_code", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["invitation_id"], ["patient_invitation.invitation_id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("attempt_id"),
    )
    op.create_index(
        "ix_invitation_attempt_invitation_time",
        "invitation_attempt",
        ["invitation_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_invitation_attempt_bucket_time",
        "invitation_attempt",
        ["bucket_key_hash", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_invitation_attempt_bucket_time", table_name="invitation_attempt")
    op.drop_index("ix_invitation_attempt_invitation_time", table_name="invitation_attempt")
    op.drop_table("invitation_attempt")

    op.drop_index("ix_patient_invitation_issued_by", table_name="patient_invitation")
    op.drop_index("ix_patient_invitation_subject", table_name="patient_invitation")
    op.drop_index("ix_patient_invitation_visit_expiry", table_name="patient_invitation")
    op.drop_table("patient_invitation")

    op.drop_index("ix_verified_visit_subject", table_name="verified_visit")
    op.drop_index("ix_verified_visit_doctor_time", table_name="verified_visit")
    op.drop_table("verified_visit")
