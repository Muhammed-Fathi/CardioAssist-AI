"""Database mappings for the M1b.1 monitoring persistence slice.

Only accepted Track-B observations, their non-null metric rows, and their
success-audit metadata are stored here. Patient/consent master records and
Track-A predictions are deliberately not represented by placeholder rows.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class MonitoringObservation(Base):
    __tablename__ = "monitoring_observation"
    __table_args__ = (
        Index("ix_monitoring_observation_public_id", "observation_id"),
        Index(
            "ix_monitoring_observation_patient_time",
            "patient_ref",
            "observed_at",
        ),
    )

    # This storage UUID is separate from the deterministic public response ID.
    # The current contract runtime resets its ID counters on process restart;
    # keeping the public ID non-unique preserves that existing behavior while
    # retaining a unique durable database identity for every accepted write.
    record_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    observation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False)

    # These remain opaque contract references in M1b.1: the existing endpoint
    # does not resolve a PatientProfile or ConsentRecord, and must not imply
    # that it does. Both values are synthetic/demo-only at this milestone.
    patient_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    consent_id: Mapped[str] = mapped_column(String(128), nullable=False)

    observed_at: Mapped[str] = mapped_column(String(40), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_detail: Mapped[str | None] = mapped_column(String(200), nullable=True)
    recorded_at: Mapped[str] = mapped_column(String(40), nullable=False)

    metrics: Mapped[list["MonitoringMetric"]] = relationship(
        back_populates="observation",
        order_by="MonitoringMetric.ordinal",
        passive_deletes=True,
    )
    audit_event: Mapped["AuditEvent | None"] = relationship(
        back_populates="observation",
        uselist=False,
        passive_deletes=True,
    )


class MonitoringMetric(Base):
    __tablename__ = "monitoring_metric"
    __table_args__ = (
        UniqueConstraint(
            "observation_record_id",
            "ordinal",
            name="uq_monitoring_metric_observation_ordinal",
        ),
        Index("ix_monitoring_metric_observation", "observation_record_id"),
        Index("ix_monitoring_metric_metric_id", "metric_id"),
    )

    metric_record_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    observation_record_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("monitoring_observation.record_id", ondelete="RESTRICT"),
        nullable=False,
    )
    # B-04 permits repeated metric ids; preserve every accepted occurrence and
    # its order rather than adding a uniqueness rule on (observation, metric).
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    metric_id: Mapped[str] = mapped_column(String(64), nullable=False)
    value_json: Mapped[object] = mapped_column(JSON, nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    recorded_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    quality_note: Mapped[str | None] = mapped_column(String(200), nullable=True)

    observation: Mapped[MonitoringObservation] = relationship(back_populates="metrics")


class AuditEvent(Base):
    """Append-only application-layer audit metadata for an accepted write.

    There is intentionally no update/delete repository method. SQLite cannot
    enforce PostgreSQL GRANT/REVOKE permissions; direct SQL access remains
    outside this application-layer guarantee.
    """

    __tablename__ = "audit_event"
    __table_args__ = (
        UniqueConstraint(
            "observation_record_id",
            name="uq_audit_event_observation_record",
        ),
        Index("ix_audit_event_public_id", "event_id"),
        Index("ix_audit_event_recorded_at", "recorded_at"),
    )

    audit_record_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    observation_record_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("monitoring_observation.record_id", ondelete="RESTRICT"),
        nullable=False,
    )
    # event_id is the public observation id, which can repeat after the
    # process-local runtime state resets; audit_record_id stays unique.
    event_id: Mapped[str] = mapped_column(String(36), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    path: Mapped[str] = mapped_column(String(128), nullable=False)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    recorded_at: Mapped[str] = mapped_column(String(40), nullable=False)

    observation: Mapped[MonitoringObservation] = relationship(back_populates="audit_event")
