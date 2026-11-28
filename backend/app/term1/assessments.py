"""C2 canonical snapshot and assessment services (S1/S2/S3).

Builds the single canonical ``term1.c2.snapshot/v1`` envelope frozen in
``docs/term1/TERM1_C2_SHARED_INTERFACE_RECONCILIATION_20261128.md`` §3,
persists it with its SHA-256 before the assessment row (schema spec §3.2/§3.3
write order), and serves the frozen role projections of S2/S3.

SAFE_SCOPE semantics (§8): manual S1 always terminates
``INFERENCE_UNAVAILABLE / real_ai_not_authorized`` with one terminal
``inference_attempt`` row, zero ``inference_result`` rows and zero adapter or
artifact access; ``ocr_confirmed`` fails closed with
``403 ocr_inference_not_authorized`` until EXC+A3 are ratified. S2/S3 are
score-free by construction: no code path here can read a result or build a
``research_output`` payload (A3+B gate).
"""

from __future__ import annotations

import copy
import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import constants, inference_lifecycle
from .audit import record
from .c2_authz import (
    require_active_consent,
    require_clinical_patient,
    require_owned_assignment,
)
from .crypto import sha256_hex
from .errors import api_error
from .health_profile import canonical_bytes, verify_profile_digest
from .idempotency import canonical_public
from .models import (
    Assessment,
    AssessmentSnapshot,
    DoctorPatientAssignment,
    DoctorProfile,
    HealthProfile,
    InferenceAttempt,
    UserAccount,
)
from .panel import normalize_panel_fields, panel_contract_ok
from .timeutil import Clock, from_iso

__all__ = [
    "canonical_bytes",
    "snapshot_schema_definition",
    "snapshot_schema_sha256",
    "build_snapshot_envelope",
    "submit_assessment",
    "get_assessment",
    "list_assessments",
]

# ---------------------------------------------------------------------------
# Frozen snapshot schema definition (shared with Track 2; checkpoint §3.4)
# ---------------------------------------------------------------------------

_SNAPSHOT_SCHEMA_DEFINITION: dict[str, Any] = {
    "schema_version": constants.SNAPSHOT_SCHEMA_VERSION,
    "kind": "canonical-assessment-snapshot-envelope",
    "canonicalization": {
        "encoding": "utf-8",
        "sort_keys": True,
        "separators": [",", ":"],
        "allow_nan": False,
    },
    "keys": {
        "schema_version": {"const": constants.SNAPSHOT_SCHEMA_VERSION},
        "schema_sha256": {"type": "sha256-hex"},
        "assessment_id": {"type": "uuid"},
        "patient_id": {"type": "uuid"},
        "assignment_id": {"type": "uuid"},
        "consent_id": {"type": "uuid"},
        "health_profile_id": {"type": "uuid"},
        "panel": {
            "keys": {
                "panel_id": {"const": constants.PANEL_ID},
                "panel_version": {"const": constants.PANEL_VERSION},
                "panel_contract_sha256": {"type": "sha256-hex"},
            }
        },
        "source_contract_version": {"const": constants.SOURCE_CONTRACT_VERSION},
        "source_kind": {"enum": list(constants.SOURCE_KINDS)},
        "inputs": {"type": "panel-field-map"},
        "units": {"type": "unit-map"},
        "missing_reasons": {"type": "missing-reason-map"},
        "provenance": {
            "keys": {
                "source_contract_version": {"const": constants.SOURCE_CONTRACT_VERSION},
                "source_kind": {"enum": list(constants.SOURCE_KINDS)},
                "health_profile_id": {"type": "uuid"},
                "health_profile_sha256": {"type": "sha256-hex"},
                "provenance_fields": {
                    "type": "map",
                    "value_enum": ["patient_manual", "ocr_confirmed"],
                },
                "confirmed_values_sha256": {"type": "sha256-hex"},
            }
        },
        "attached_documents": {
            "type": "array",
            "sort_keys": ["document_id", "binding_id"],
            "item_keys": [
                "binding_id",
                "document_id",
                "attachment_role",
                "extraction_id",
                "extraction_version",
                "document_sha256_at_bind",
                "extraction_confirmed_at",
                "confirmed_values_sha256",
            ],
        },
    },
}


def snapshot_schema_definition() -> dict[str, Any]:
    """The frozen canonical schema-definition document (deep copy)."""
    return copy.deepcopy(_SNAPSHOT_SCHEMA_DEFINITION)


def snapshot_schema_sha256() -> str:
    """sha256(canonical(snapshot_schema_definition()))."""
    return sha256_hex(
        json.dumps(
            _SNAPSHOT_SCHEMA_DEFINITION,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    )


def _confirmed_values_sha256(
    *,
    inputs: dict[str, Any],
    units: dict[str, Any],
    missing_reasons: dict[str, Any],
    provenance_fields: dict[str, str],
) -> str:
    """sha256(canonical({inputs, units, missing_reasons, provenance_fields})) —
    one formula for both source kinds (checkpoint §3.3)."""
    return sha256_hex(
        canonical_public(
            {
                "inputs": inputs,
                "units": units,
                "missing_reasons": missing_reasons,
                "provenance_fields": provenance_fields,
            }
        )
    )


def build_snapshot_envelope(
    *,
    assessment_id: str,
    patient_id: str,
    assignment_id: str,
    consent_id: str,
    health_profile: HealthProfile,
    inputs: dict[str, Any],
    units: dict[str, Any],
    missing_reasons: dict[str, Any],
    source_kind: str,
    attached_documents: list[dict[str, Any]],
) -> dict[str, Any]:
    """Assemble the canonical envelope (checkpoint §3.2)."""
    provenance_value = (
        "patient_manual"
        if source_kind == constants.SOURCE_KIND_MANUAL
        else "ocr_confirmed"
    )
    provenance_fields = {
        field: provenance_value
        for field in sorted(inputs)
        if inputs[field] is not None
    }
    sorted_documents = sorted(
        attached_documents,
        key=lambda item: (item["document_id"], item["binding_id"]),
    )
    envelope: dict[str, Any] = {
        "schema_version": constants.SNAPSHOT_SCHEMA_VERSION,
        "schema_sha256": snapshot_schema_sha256(),
        "assessment_id": assessment_id,
        "patient_id": patient_id,
        "assignment_id": assignment_id,
        "consent_id": consent_id,
        "health_profile_id": health_profile.health_profile_id,
        "panel": {
            "panel_id": constants.PANEL_ID,
            "panel_version": constants.PANEL_VERSION,
            "panel_contract_sha256": constants.PANEL_CONTRACT_SHA256,
        },
        "source_contract_version": constants.SOURCE_CONTRACT_VERSION,
        "source_kind": source_kind,
        "inputs": inputs,
        "units": units,
        "missing_reasons": missing_reasons,
        "provenance": {
            "source_contract_version": constants.SOURCE_CONTRACT_VERSION,
            "source_kind": source_kind,
            "health_profile_id": health_profile.health_profile_id,
            "health_profile_sha256": health_profile.profile_sha256,
            "provenance_fields": provenance_fields,
            "confirmed_values_sha256": _confirmed_values_sha256(
                inputs=inputs,
                units=units,
                missing_reasons=missing_reasons,
                provenance_fields=provenance_fields,
            ),
        },
        "attached_documents": sorted_documents,
    }
    return envelope


def snapshot_digest(envelope: dict[str, Any]) -> str:
    """snapshot_sha256 = sha256(canonical UTF-8 snapshot_json)."""
    return sha256_hex(canonical_public(envelope))


def _verify_snapshot_integrity(session: Session, assessment: Assessment) -> AssessmentSnapshot:
    """Recompute the stored snapshot digest on S2/S3 reads (fail closed)."""
    snapshot = session.execute(
        select(AssessmentSnapshot).where(
            AssessmentSnapshot.snapshot_id == assessment.snapshot_id,
            AssessmentSnapshot.patient_id == assessment.patient_id,
        )
    ).scalar_one_or_none()
    if snapshot is None:
        raise api_error("internal_error")
    if snapshot_digest(snapshot.snapshot_json) != snapshot.snapshot_sha256:
        raise api_error("internal_error")
    return snapshot


def _latest_attempt_id(session: Session, assessment_id: str) -> str:
    attempt = session.execute(
        select(InferenceAttempt)
        .where(InferenceAttempt.assessment_id == assessment_id)
        .order_by(InferenceAttempt.generation.desc(), InferenceAttempt.leased_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if attempt is None:
        # Every assessment created by S1 owns at least one attempt row.
        raise api_error("internal_error")
    return attempt.attempt_id


# ---------------------------------------------------------------------------
# S1 — POST /v1/assessments
# ---------------------------------------------------------------------------


def submit_assessment(
    session: Session,
    *,
    clock: Clock,
    account: UserAccount,
    body: dict[str, Any],
) -> dict[str, Any]:
    """Create snapshot + assessment + terminal attempt in one transaction."""
    profile = require_clinical_patient(session, account=account)
    patient_id = profile.patient_id

    # Strict input_mode XOR (also enforced by the request schema).
    input_mode = body.get("input_mode")
    if input_mode == constants.INPUT_MODE_OCR_CONFIRMED:
        # EXC-TERM1-OCR-DEMO-V1 and A3 remain PENDING (SAFE_SCOPE gate).
        raise api_error("ocr_inference_not_authorized")
    if input_mode != constants.INPUT_MODE_MANUAL:
        raise api_error("validation_failed")
    panel_input = body.get("panel_input")
    if not isinstance(panel_input, dict) or body.get("ocr_source") is not None:
        raise api_error("validation_failed")

    consent = require_active_consent(session, patient_id=patient_id)
    assignment = require_owned_assignment(
        session,
        assignment_id=str(body.get("assignment_id")),
        patient_id=patient_id,
    )

    # Active COMPLETE profile pin (404 / 409 / 422 order per API spec §2.1).
    health_profile_id = body.get("health_profile_id")
    if not isinstance(health_profile_id, str):
        raise api_error("validation_failed")
    pinned = session.execute(
        select(HealthProfile).where(
            HealthProfile.health_profile_id == health_profile_id,
            HealthProfile.patient_id == patient_id,
        )
    ).scalar_one_or_none()
    if pinned is None:
        raise api_error("health_profile_not_found")
    if pinned.superseded_at is not None:
        raise api_error("health_profile_superseded")
    if pinned.status != constants.HEALTH_PROFILE_COMPLETE:
        raise api_error("health_profile_incomplete")
    verify_profile_digest(pinned)

    if not panel_contract_ok(body.get("panel_id"), body.get("panel_version")):
        raise api_error("invalid_panel_input")
    inputs, units, missing_reasons, stage_complete = normalize_panel_fields(
        panel_input.get("inputs") or {},
        panel_input.get("units") or {},
        panel_input.get("missing_reasons") or {},
        allow_absent_mandatory=False,
        strict_reasons=True,
    )

    # Attachments: Track 1 has no document tables (migration 08 is Track 2);
    # any non-empty list fails closed with the non-enumerating 404.
    attached_document_ids = body.get("attached_document_ids") or []
    if not isinstance(attached_document_ids, list):
        raise api_error("validation_failed")
    if attached_document_ids:
        raise api_error("document_not_found")

    reassessment_of_id = body.get("reassessment_of_id")
    reassessment_reason = body.get("reassessment_reason")
    if reassessment_of_id is None:
        if reassessment_reason is not None:
            raise api_error("validation_failed")
    else:
        if not isinstance(reassessment_reason, str) or not (
            1 <= len(reassessment_reason) <= 128
        ):
            raise api_error("validation_failed")
        target = session.execute(
            select(Assessment).where(
                Assessment.assessment_id == reassessment_of_id,
                Assessment.patient_id == patient_id,
                Assessment.assignment_id == assignment.assignment_id,
            )
        ).scalar_one_or_none()
        if target is None:
            raise api_error("assessment_not_found")

    now = clock.now_iso()
    assessment_id = str(uuid.uuid4())
    snapshot_id = str(uuid.uuid4())
    envelope = build_snapshot_envelope(
        assessment_id=assessment_id,
        patient_id=patient_id,
        assignment_id=assignment.assignment_id,
        consent_id=consent.consent_id,
        health_profile=pinned,
        inputs=inputs,
        units=units,
        missing_reasons=missing_reasons,
        source_kind=constants.SOURCE_KIND_MANUAL,
        attached_documents=[],
    )
    snapshot_sha256 = snapshot_digest(envelope)

    session.add(
        AssessmentSnapshot(
            snapshot_id=snapshot_id,
            patient_id=patient_id,
            health_profile_id=pinned.health_profile_id,
            panel_id=constants.PANEL_ID,
            panel_version=constants.PANEL_VERSION,
            panel_contract_sha256=constants.PANEL_CONTRACT_SHA256,
            schema_version=constants.SNAPSHOT_SCHEMA_VERSION,
            schema_sha256=envelope["schema_sha256"],
            source_contract_version=constants.SOURCE_CONTRACT_VERSION,
            source_kind=constants.SOURCE_KIND_MANUAL,
            snapshot_json=envelope,
            snapshot_sha256=snapshot_sha256,
            created_at=now,
        )
    )
    session.flush()

    assessment = Assessment(
        assessment_id=assessment_id,
        patient_id=patient_id,
        health_profile_id=pinned.health_profile_id,
        snapshot_id=snapshot_id,
        assignment_id=assignment.assignment_id,
        consent_id=envelope["consent_id"],
        reassessment_of_id=reassessment_of_id,
        reassessment_reason=reassessment_reason,
        panel_id=constants.PANEL_ID,
        panel_version=constants.PANEL_VERSION,
        source_contract_version=constants.SOURCE_CONTRACT_VERSION,
        source_kind=constants.SOURCE_KIND_MANUAL,
        stage_complete=stage_complete,
        status=constants.ASSESSMENT_INPUT_VALIDATED,
        reason_code=None,
        active_attempt_id=None,
        current_generation=0,
        current_result_id=None,
        review_state=constants.REVIEW_NOT_REVIEWED,
        review_version=0,
        created_at=now,
        updated_at=now,
    )
    session.add(assessment)
    session.flush()

    # SAFE_SCOPE: durable attempt -> terminal unavailable, no dispatch.
    attempt = inference_lifecycle.begin_attempt(
        session,
        clock=clock,
        assessment=assessment,
        snapshot_sha256=snapshot_sha256,
    )
    inference_lifecycle.complete_unavailable(
        session,
        clock=clock,
        attempt_id=attempt.attempt_id,
        reason_code=constants.REASON_REAL_AI_NOT_AUTHORIZED,
        worker_id=attempt.worker_id,
        fence_token=attempt.fence_token,
        actor_user_id=account.user_id,
    )

    record(
        session,
        clock=clock,
        event_type=constants.EVENT_ASSESSMENT_CREATED,
        outcome=constants.OUTCOME_SUCCESS,
        subject_type=constants.SUBJECT_ASSESSMENT,
        subject_id=assessment.assessment_id,
        actor_user_id=account.user_id,
        payload={
            "assignment_id": assessment.assignment_id,
            "snapshot_id": assessment.snapshot_id,
            "status": assessment.status,
            "reason_code": assessment.reason_code,
            "input_mode": constants.INPUT_MODE_MANUAL,
        },
    )

    return {
        "contract_version": "v1",
        "assessment_id": assessment.assessment_id,
        "assignment_id": assessment.assignment_id,
        "health_profile_id": assessment.health_profile_id,
        "snapshot_id": assessment.snapshot_id,
        "snapshot_sha256": snapshot_sha256,
        "panel_id": assessment.panel_id,
        "panel_version": assessment.panel_version,
        "source_contract_version": assessment.source_contract_version,
        "source_kind": assessment.source_kind,
        "status": assessment.status,
        "reason_code": assessment.reason_code,
        "attempt_id": attempt.attempt_id,
        "review_state": assessment.review_state,
        "created_at": assessment.created_at,
    }


# ---------------------------------------------------------------------------
# S2 — GET /v1/assessments/{assessment_id}
# ---------------------------------------------------------------------------


def _patient_projection(assessment: Assessment) -> dict[str, Any]:
    return {
        "contract_version": "v1",
        "assessment_id": assessment.assessment_id,
        "status": assessment.status,
        "reason_code": assessment.reason_code,
        "created_at": assessment.created_at,
        "review_state": assessment.review_state,
        "research_output": None,
    }


def _doctor_projection(
    assessment: Assessment, snapshot: AssessmentSnapshot
) -> dict[str, Any]:
    envelope = snapshot.snapshot_json
    return {
        "contract_version": "v1",
        "assessment_id": assessment.assessment_id,
        "assignment_id": assessment.assignment_id,
        "health_profile_id": assessment.health_profile_id,
        "snapshot_id": assessment.snapshot_id,
        "snapshot_sha256": snapshot.snapshot_sha256,
        "panel_id": assessment.panel_id,
        "panel_version": assessment.panel_version,
        "source_contract_version": assessment.source_contract_version,
        "source_kind": assessment.source_kind,
        "status": assessment.status,
        "reason_code": assessment.reason_code,
        "inputs": envelope["inputs"],
        "units": envelope["units"],
        "missing_reasons": envelope["missing_reasons"],
        "attached_documents": envelope["attached_documents"],
        "review_state": assessment.review_state,
        "review_version": assessment.review_version,
        "research_output": None,
        "created_at": assessment.created_at,
        "updated_at": assessment.updated_at,
    }


def get_assessment(
    session: Session,
    *,
    clock: Clock,
    account: UserAccount,
    assessment_id: str,
) -> dict[str, Any]:
    if account.role == constants.ROLE_ADMIN:
        raise api_error("admin_clinical_content_forbidden")

    if account.role == constants.ROLE_PATIENT:
        profile = require_clinical_patient(session, account=account)
        assessment = session.execute(
            select(Assessment).where(
                Assessment.assessment_id == assessment_id,
                Assessment.patient_id == profile.patient_id,
            )
        ).scalar_one_or_none()
        if assessment is None:
            raise api_error("assessment_not_found")
        _verify_snapshot_integrity(session, assessment)
        return _patient_projection(assessment)

    if account.role == constants.ROLE_DOCTOR:
        assessment = session.execute(
            select(Assessment).where(
                Assessment.assessment_id == assessment_id
            )
        ).scalar_one_or_none()
        doctor = session.execute(
            select(DoctorProfile).where(DoctorProfile.user_id == account.user_id)
        ).scalar_one_or_none()
        if doctor is None:
            raise api_error("role_profile_mismatch")
        if assessment is None:
            raise api_error("assessment_not_found")
        assignment = session.execute(
            select(DoctorPatientAssignment).where(
                DoctorPatientAssignment.assignment_id
                == assessment.assignment_id,
                DoctorPatientAssignment.doctor_id == doctor.doctor_id,
            )
        ).scalar_one_or_none()
        # Wrong doctor, revoked assignment or unassigned access are the
        # identical non-enumerating 404 (P-14).
        if (
            assignment is None
            or assignment.revoked_at is not None
            or assignment.patient_id != assessment.patient_id
        ):
            raise api_error("assessment_not_found")
        snapshot = _verify_snapshot_integrity(session, assessment)
        return _doctor_projection(assessment, snapshot)

    raise api_error("forbidden")


# ---------------------------------------------------------------------------
# S3 — GET /v1/me/assessments
# ---------------------------------------------------------------------------


def _parse_limit(raw: str | None) -> int:
    if raw is None:
        return 20
    try:
        limit = int(raw)
    except ValueError:
        raise api_error("malformed_request") from None
    if not 1 <= limit <= 100:
        raise api_error("malformed_request")
    return limit


def _parse_cursor(raw: str | None) -> tuple[str, str] | None:
    if raw is None or raw == "":
        return None
    parts = raw.split("|")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise api_error("malformed_request")
    try:
        from_iso(parts[0])
    except ValueError:
        raise api_error("malformed_request") from None
    return parts[0], parts[1]


def list_assessments(
    session: Session,
    *,
    clock: Clock,
    account: UserAccount,
    limit_raw: str | None,
    cursor_raw: str | None,
) -> dict[str, Any]:
    profile = require_clinical_patient(session, account=account)
    limit = _parse_limit(limit_raw)
    cursor = _parse_cursor(cursor_raw)

    query = select(Assessment).where(
        Assessment.patient_id == profile.patient_id
    )
    if cursor is not None:
        created_at, assessment_id = cursor
        query = query.where(
            (Assessment.created_at < created_at)
            | (
                (Assessment.created_at == created_at)
                & (Assessment.assessment_id < assessment_id)
            )
        )
    query = query.order_by(
        Assessment.created_at.desc(), Assessment.assessment_id.desc()
    ).limit(limit + 1)
    rows = list(session.execute(query).scalars().all())

    has_more = len(rows) > limit
    rows = rows[:limit]
    items: list[dict[str, Any]] = []
    for assessment in rows:
        _verify_snapshot_integrity(session, assessment)
        items.append(
            {
                "assessment_id": assessment.assessment_id,
                "assignment_id": assessment.assignment_id,
                "panel_id": assessment.panel_id,
                "panel_version": assessment.panel_version,
                "status": assessment.status,
                "reason_code": assessment.reason_code,
                "source_kind": assessment.source_kind,
                "attempt_id": _latest_attempt_id(
                    session, assessment.assessment_id
                ),
                "review_state": assessment.review_state,
                "created_at": assessment.created_at,
            }
        )
    next_cursor = (
        f"{items[-1]['created_at']}|{items[-1]['assessment_id']}"
        if has_more and items
        else None
    )
    return {
        "contract_version": "v1",
        "items": items,
        "next_cursor": next_cursor,
    }
