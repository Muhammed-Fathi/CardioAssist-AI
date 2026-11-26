"""C1.1c — doctor-patient assignments and patient-wide synthetic consent.

Revision ID: 20261126_04
Revises: 20261126_03
Create Date: 2026-11-26

Assignments replace any ``patient.doctor_id`` ownership shortcut (R-01): one
active row per doctor/patient pair is enforced by a partial UNIQUE index, and
several doctors may hold independent active assignments. Consent is separate
and patient-wide; revoking one assignment never revokes consent (and vice
versa).
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261126_04"
down_revision: Union[str, None] = "20261126_03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "doctor_patient_assignment",
        sa.Column("assignment_id", sa.String(length=36), nullable=False),
        sa.Column("doctor_id", sa.String(length=36), nullable=False),
        sa.Column("patient_id", sa.String(length=36), nullable=False),
        sa.Column("assigned_at", sa.String(length=32), nullable=False),
        sa.Column("revoked_at", sa.String(length=32), nullable=True),
        sa.Column("revoked_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("revoked_by_role", sa.String(length=16), nullable=True),
        sa.Column("reason_code", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctor_profile.doctor_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["patient_id"], ["patient_profile.patient_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["revoked_by_user_id"], ["user_account.user_id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("assignment_id"),
    )
    op.create_index(
        "ux_doctor_patient_assignment_active_pair",
        "doctor_patient_assignment",
        ["doctor_id", "patient_id"],
        unique=True,
        sqlite_where=sa.text("revoked_at IS NULL"),
    )
    op.create_index(
        "ix_doctor_patient_assignment_patient_active",
        "doctor_patient_assignment",
        ["patient_id", "revoked_at"],
        unique=False,
    )
    op.create_index(
        "ix_doctor_patient_assignment_doctor_active",
        "doctor_patient_assignment",
        ["doctor_id", "revoked_at"],
        unique=False,
    )

    op.create_table(
        "consent_record",
        sa.Column("consent_id", sa.String(length=36), nullable=False),
        sa.Column("patient_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("scope", sa.String(length=48), nullable=False),
        sa.Column("acknowledged_at", sa.String(length=32), nullable=False),
        sa.Column("revoked_at", sa.String(length=32), nullable=True),
        sa.Column("revoked_reason", sa.String(length=64), nullable=True),
        sa.Column("contract_version", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "kind = 'synthetic_demo' AND scope = 'patient_wide_synthetic_demo'",
            name="ck_consent_record_kind_scope",
        ),
        sa.ForeignKeyConstraint(["patient_id"], ["patient_profile.patient_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("consent_id"),
    )
    op.create_index(
        "ux_consent_record_active_patient",
        "consent_record",
        ["patient_id"],
        unique=True,
        sqlite_where=sa.text("revoked_at IS NULL"),
    )
    op.create_index(
        "ix_consent_record_patient",
        "consent_record",
        ["patient_id", "acknowledged_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_consent_record_patient", table_name="consent_record")
    op.drop_index("ux_consent_record_active_patient", table_name="consent_record")
    op.drop_table("consent_record")

    op.drop_index(
        "ix_doctor_patient_assignment_doctor_active", table_name="doctor_patient_assignment"
    )
    op.drop_index(
        "ix_doctor_patient_assignment_patient_active", table_name="doctor_patient_assignment"
    )
    op.drop_index(
        "ux_doctor_patient_assignment_active_pair", table_name="doctor_patient_assignment"
    )
    op.drop_table("doctor_patient_assignment")
