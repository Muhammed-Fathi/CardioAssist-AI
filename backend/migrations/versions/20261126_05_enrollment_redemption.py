"""C1.1d — invitation redemption record (created last: depends on everything).

Revision ID: 20261126_05
Revises: 20261126_04
Create Date: 2026-11-26

``invitation_redemption`` is written inside the same transaction that consumes
the invitation, so a consumed invitation and its redemption record can never
disagree. ``UNIQUE(invitation_id)`` makes one invitation redeemable once.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261126_05"
down_revision: Union[str, None] = "20261126_04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "invitation_redemption",
        sa.Column("redemption_id", sa.String(length=36), nullable=False),
        sa.Column("invitation_id", sa.String(length=36), nullable=False),
        sa.Column("patient_id", sa.String(length=36), nullable=False),
        sa.Column("assignment_id", sa.String(length=36), nullable=False),
        sa.Column("redeemed_at", sa.String(length=32), nullable=False),
        sa.Column("flow", sa.String(length=16), nullable=False),
        sa.CheckConstraint("flow IN ('register','link')", name="ck_invitation_redemption_flow"),
        sa.ForeignKeyConstraint(
            ["invitation_id"], ["patient_invitation.invitation_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["patient_id"], ["patient_profile.patient_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["assignment_id"],
            ["doctor_patient_assignment.assignment_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("redemption_id"),
        sa.UniqueConstraint("invitation_id", name="ux_invitation_redemption_invitation"),
    )
    op.create_index(
        "ix_invitation_redemption_assignment",
        "invitation_redemption",
        ["assignment_id"],
        unique=False,
    )
    op.create_index(
        "ix_invitation_redemption_patient",
        "invitation_redemption",
        ["patient_id", "redeemed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_invitation_redemption_patient", table_name="invitation_redemption")
    op.drop_index("ix_invitation_redemption_assignment", table_name="invitation_redemption")
    op.drop_table("invitation_redemption")
