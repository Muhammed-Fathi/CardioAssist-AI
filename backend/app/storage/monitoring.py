"""Insert/read repository for accepted Track-B monitoring observations."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .database import Database
from .models import AuditEvent, MonitoringMetric, MonitoringObservation


def _utc_iso(value: str) -> str:
    """Normalize a validated RFC 3339 timestamp to canonical UTC text."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("An RFC 3339 timestamp must include a timezone.")
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class StoredMonitoringMetric:
    metric_record_id: str
    ordinal: int
    metric_id: str
    value: object
    unit: str
    recorded_at: str | None
    quality_note: str | None


@dataclass(frozen=True)
class StoredMonitoringObservation:
    record_id: str
    observation_id: str
    request_id: str
    patient_ref: str
    consent_id: str
    observed_at: str
    source: str
    source_detail: str | None
    recorded_at: str
    metrics: tuple[StoredMonitoringMetric, ...]


@dataclass(frozen=True)
class StoredAuditEvent:
    audit_record_id: str
    observation_record_id: str
    event_id: str
    event_type: str
    path: str
    request_id: str
    payload_sha256: str
    recorded_at: str


class MonitoringRepository:
    """Persist one accepted observation, its non-null metrics and audit row.

    The transaction boundary is intentionally inside this repository method:
    all three row groups commit together or all are rolled back. Replays and
    rejected requests never call this repository.
    """

    def __init__(self, database: Database) -> None:
        self._database = database

    def record_accepted(
        self,
        *,
        observation_id: str,
        request_id: str,
        payload_sha256: str,
        path: str,
        observation: dict[str, Any],
    ) -> str:
        record_id = str(uuid.uuid4())
        recorded_at = _now_utc_iso()
        row = MonitoringObservation(
            record_id=record_id,
            observation_id=observation_id,
            request_id=request_id,
            patient_ref=observation["patient_ref"],
            consent_id=observation["consent_id"],
            observed_at=_utc_iso(observation["observed_at"]),
            source=observation["source"],
            source_detail=observation.get("source_detail"),
            recorded_at=recorded_at,
        )

        with self._database.transaction() as session:
            session.add(row)
            for ordinal, metric in enumerate(observation["metrics"]):
                # Match the approved runtime: null means not measured and is
                # not stored; repeated ids, booleans and strings are preserved.
                if metric["value"] is None:
                    continue
                session.add(
                    MonitoringMetric(
                        metric_record_id=str(uuid.uuid4()),
                        observation_record_id=record_id,
                        ordinal=ordinal,
                        metric_id=metric["metric_id"],
                        value_json=metric["value"],
                        unit=metric["unit"],
                        recorded_at=(
                            _utc_iso(metric["recorded_at"])
                            if metric.get("recorded_at") is not None
                            else None
                        ),
                        quality_note=metric.get("quality_note"),
                    )
                )
            session.add(
                AuditEvent(
                    audit_record_id=str(uuid.uuid4()),
                    observation_record_id=record_id,
                    event_id=observation_id,
                    event_type="observation_recorded",
                    path=path,
                    request_id=request_id,
                    payload_sha256=payload_sha256,
                    recorded_at=recorded_at,
                )
            )
            # Force FK/unique/JSON errors to happen before the transaction
            # context commits; every failure rolls back the observation too.
            session.flush()

        return record_id

    @staticmethod
    def _to_observation(row: MonitoringObservation) -> StoredMonitoringObservation:
        metrics = tuple(
            StoredMonitoringMetric(
                metric_record_id=metric.metric_record_id,
                ordinal=metric.ordinal,
                metric_id=metric.metric_id,
                value=metric.value_json,
                unit=metric.unit,
                recorded_at=metric.recorded_at,
                quality_note=metric.quality_note,
            )
            for metric in row.metrics
        )
        return StoredMonitoringObservation(
            record_id=row.record_id,
            observation_id=row.observation_id,
            request_id=row.request_id,
            patient_ref=row.patient_ref,
            consent_id=row.consent_id,
            observed_at=row.observed_at,
            source=row.source,
            source_detail=row.source_detail,
            recorded_at=row.recorded_at,
            metrics=metrics,
        )

    def get_by_record_id(self, record_id: str) -> StoredMonitoringObservation | None:
        """Read one stored row by its private, durable storage identity."""
        with self._database.transaction() as session:
            row = session.scalar(
                select(MonitoringObservation)
                .options(selectinload(MonitoringObservation.metrics))
                .where(MonitoringObservation.record_id == record_id)
            )
            return self._to_observation(row) if row is not None else None

    def list_observations(self) -> tuple[StoredMonitoringObservation, ...]:
        """Return stored rows for internal integration/tests; no HTTP route."""
        with self._database.transaction() as session:
            rows = session.scalars(
                select(MonitoringObservation)
                .options(selectinload(MonitoringObservation.metrics))
                .order_by(MonitoringObservation.recorded_at, MonitoringObservation.record_id)
            ).all()
            return tuple(self._to_observation(row) for row in rows)

    def list_audit_events(self) -> tuple[StoredAuditEvent, ...]:
        """Read append-only audit metadata without exposing update/delete paths."""
        with self._database.transaction() as session:
            rows = session.scalars(
                select(AuditEvent).order_by(AuditEvent.recorded_at, AuditEvent.audit_record_id)
            ).all()
            return tuple(
                StoredAuditEvent(
                    audit_record_id=row.audit_record_id,
                    observation_record_id=row.observation_record_id,
                    event_id=row.event_id,
                    event_type=row.event_type,
                    path=row.path,
                    request_id=row.request_id,
                    payload_sha256=row.payload_sha256,
                    recorded_at=row.recorded_at,
                )
                for row in rows
            )
