"""Add the first durable monitoring write path.

Revision ID: 20261017_01
Revises:
Create Date: 2026-10-17
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261017_01"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "monitoring_observation",
        sa.Column("record_id", sa.String(length=36), nullable=False),
        sa.Column("observation_id", sa.String(length=36), nullable=False),
        sa.Column("request_id", sa.String(length=36), nullable=False),
        sa.Column("patient_ref", sa.String(length=128), nullable=False),
        sa.Column("consent_id", sa.String(length=128), nullable=False),
        sa.Column("observed_at", sa.String(length=40), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("source_detail", sa.String(length=200), nullable=True),
        sa.Column("recorded_at", sa.String(length=40), nullable=False),
        sa.PrimaryKeyConstraint("record_id"),
    )
    op.create_index(
        "ix_monitoring_observation_public_id",
        "monitoring_observation",
        ["observation_id"],
        unique=False,
    )
    op.create_index(
        "ix_monitoring_observation_patient_time",
        "monitoring_observation",
        ["patient_ref", "observed_at"],
        unique=False,
    )

    op.create_table(
        "monitoring_metric",
        sa.Column("metric_record_id", sa.String(length=36), nullable=False),
        sa.Column("observation_record_id", sa.String(length=36), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("metric_id", sa.String(length=64), nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("recorded_at", sa.String(length=40), nullable=True),
        sa.Column("quality_note", sa.String(length=200), nullable=True),
        sa.ForeignKeyConstraint(
            ["observation_record_id"],
            ["monitoring_observation.record_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("metric_record_id"),
        sa.UniqueConstraint(
            "observation_record_id",
            "ordinal",
            name="uq_monitoring_metric_observation_ordinal",
        ),
    )
    op.create_index(
        "ix_monitoring_metric_observation",
        "monitoring_metric",
        ["observation_record_id"],
        unique=False,
    )
    op.create_index(
        "ix_monitoring_metric_metric_id",
        "monitoring_metric",
        ["metric_id"],
        unique=False,
    )

    op.create_table(
        "audit_event",
        sa.Column("audit_record_id", sa.String(length=36), nullable=False),
        sa.Column("observation_record_id", sa.String(length=36), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("path", sa.String(length=128), nullable=False),
        sa.Column("request_id", sa.String(length=36), nullable=False),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("recorded_at", sa.String(length=40), nullable=False),
        sa.ForeignKeyConstraint(
            ["observation_record_id"],
            ["monitoring_observation.record_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("audit_record_id"),
        sa.UniqueConstraint(
            "observation_record_id",
            name="uq_audit_event_observation_record",
        ),
    )
    op.create_index("ix_audit_event_public_id", "audit_event", ["event_id"], unique=False)
    op.create_index("ix_audit_event_recorded_at", "audit_event", ["recorded_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_event_recorded_at", table_name="audit_event")
    op.drop_index("ix_audit_event_public_id", table_name="audit_event")
    op.drop_table("audit_event")

    op.drop_index("ix_monitoring_metric_metric_id", table_name="monitoring_metric")
    op.drop_index("ix_monitoring_metric_observation", table_name="monitoring_metric")
    op.drop_table("monitoring_metric")

    op.drop_index(
        "ix_monitoring_observation_patient_time",
        table_name="monitoring_observation",
    )
    op.drop_index(
        "ix_monitoring_observation_public_id",
        table_name="monitoring_observation",
    )
    op.drop_table("monitoring_observation")
