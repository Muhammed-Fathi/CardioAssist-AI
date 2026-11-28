"""C2 H1a/H1b health-profile services (immutable versioned rows).

H1a reads the caller's active (``superseded_at IS NULL``) profile version and
is allowed after consent withdrawal (OQ-H1A). H1b merges an optional patch into
the active version, validates the pinned ``da_a2_resting_v1`` panel, supersedes
the old row and inserts the next immutable version — all inside the caller's
``BEGIN IMMEDIATE`` transaction, so a failure after the supersession UPDATE
rolls back atomically leaving the original active row intact (schema spec §3.1).

Neither operation triggers inference. ``source_kind`` is server-assigned
``synthetic_demo_patient_manual``; client-supplied provenance/OCR reference
keys are rejected with ``422 prohibited_clinical_field``.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import constants
from .audit import record
from .c2_authz import require_active_consent, require_clinical_patient
from .crypto import sha256_hex
from .errors import api_error
from .idempotency import canonical_public
from .models import HealthProfile, UserAccount
from .panel import normalize_panel_fields, panel_contract_ok
from .timeutil import Clock

# Top-level request keys a client may never supply (manual-only provenance).
_PROVENANCE_KEYS = (
    "provenance",
    "source_kind",
    "source_contract_version",
    "profile_sha256",
    "ocr_source",
    "document_id",
    "extraction_id",
)


def canonical_bytes(value: Any) -> bytes:
    """Frozen canonical JSON encoding (UTF-8, sort_keys, tight separators)."""
    return canonical_public(value).encode("utf-8")


def profile_sha256(
    *,
    panel_id: str,
    panel_version: str,
    schema_version: str,
    fields_json: dict[str, Any],
    provenance_json: dict[str, Any],
) -> str:
    """sha256(canonical({panel_id, panel_version, schema_version, fields_json,
    provenance_json})) — schema spec §3.1."""
    return sha256_hex(
        canonical_public(
            {
                "panel_id": panel_id,
                "panel_version": panel_version,
                "schema_version": schema_version,
                "fields_json": fields_json,
                "provenance_json": provenance_json,
            }
        )
    )


def verify_profile_digest(row: HealthProfile) -> None:
    """Recompute the stored digest; a mismatch fails closed (500)."""
    expected = profile_sha256(
        panel_id=row.panel_id,
        panel_version=row.panel_version,
        schema_version=row.schema_version,
        fields_json=row.fields_json,
        provenance_json=row.provenance_json,
    )
    if expected != row.profile_sha256:
        raise api_error("internal_error")


def profile_projection(row: HealthProfile) -> dict[str, Any]:
    """The frozen 13-key H1a/H1b 200 response (reconciliation §8)."""
    fields = row.fields_json
    return {
        "contract_version": "v1",
        "health_profile_id": row.health_profile_id,
        "version_number": row.version_number,
        "status": row.status,
        "panel_id": row.panel_id,
        "panel_version": row.panel_version,
        "schema_version": row.schema_version,
        "inputs": fields["inputs"],
        "units": fields["units"],
        "missing_reasons": fields["missing_reasons"],
        "provenance": row.provenance_json,
        "profile_sha256": row.profile_sha256,
        "created_at": row.created_at,
    }


def active_profile(session: Session, *, patient_id: str) -> HealthProfile | None:
    return session.execute(
        select(HealthProfile).where(
            HealthProfile.patient_id == patient_id,
            HealthProfile.superseded_at.is_(None),
        )
    ).scalar_one_or_none()


def get_health_profile(session: Session, *, account: UserAccount) -> dict[str, Any]:
    """H1a — self-read of the active profile version (no consent requirement)."""
    profile = require_clinical_patient(session, account=account)
    row = active_profile(session, patient_id=profile.patient_id)
    if row is None:
        raise api_error("health_profile_not_found")
    verify_profile_digest(row)
    return profile_projection(row)


def patch_health_profile(
    session: Session,
    *,
    clock: Clock,
    account: UserAccount,
    body: dict[str, Any],
) -> dict[str, Any]:
    """H1b — manual-only merge/supersede/insert of one immutable version."""
    profile = require_clinical_patient(session, account=account)
    require_active_consent(session, patient_id=profile.patient_id)

    for key in _PROVENANCE_KEYS:
        if key in body:
            raise api_error("prohibited_clinical_field")

    if not panel_contract_ok(body.get("panel_id"), body.get("panel_version")):
        raise api_error("invalid_panel_input")

    expected_version = body.get("expected_version_number")
    if expected_version is not None and (
        isinstance(expected_version, bool)
        or not isinstance(expected_version, int)
        or expected_version < 1
    ):
        raise api_error("validation_failed")

    current = active_profile(session, patient_id=profile.patient_id)
    if expected_version is not None and (
        current is None or current.version_number != expected_version
    ):
        raise api_error("concurrency_conflict")

    old_fields = (
        current.fields_json
        if current is not None
        else {"inputs": {}, "units": {}, "missing_reasons": {}}
    )
    patch_inputs = body.get("inputs") or {}
    patch_units = body.get("units") or {}
    patch_reasons = body.get("missing_reasons") or {}

    merged_inputs = dict(old_fields["inputs"])
    merged_inputs.update(patch_inputs)
    merged_units = dict(old_fields["units"])
    merged_units.update(patch_units)
    merged_reasons = dict(old_fields["missing_reasons"])
    merged_reasons.update(patch_reasons)

    # A reason resent for a field that is (or becomes) present is a client
    # error, not something to silently drop.
    for field in patch_reasons:
        if field in merged_inputs and merged_inputs[field] is not None:
            raise api_error("missing_reason_mismatch")

    inputs, units, missing_reasons, stage_complete = normalize_panel_fields(
        merged_inputs,
        merged_units,
        merged_reasons,
        allow_absent_mandatory=True,
        strict_reasons=False,
    )

    fields_json = {
        "inputs": inputs,
        "units": units,
        "missing_reasons": missing_reasons,
    }
    provenance_json = {
        "source_contract_version": constants.SOURCE_CONTRACT_VERSION,
        "source_kind": constants.SOURCE_KIND_MANUAL,
    }
    digest = profile_sha256(
        panel_id=constants.PANEL_ID,
        panel_version=constants.PANEL_VERSION,
        schema_version=constants.PROFILE_SCHEMA_VERSION,
        fields_json=fields_json,
        provenance_json=provenance_json,
    )
    now = clock.now_iso()

    # Mandatory write order (schema spec §3.1): supersede first (keeps the
    # partial unique "one active row per patient" satisfied), then insert.
    superseded_id: str | None = None
    if current is not None:
        superseded_id = current.health_profile_id
        current.status = constants.HEALTH_PROFILE_SUPERSEDED
        current.superseded_at = now
        session.flush()

    version_number = (current.version_number + 1) if current is not None else 1
    row = HealthProfile(
        health_profile_id=str(uuid.uuid4()),
        patient_id=profile.patient_id,
        version_number=version_number,
        status=(
            constants.HEALTH_PROFILE_COMPLETE
            if stage_complete
            else constants.HEALTH_PROFILE_DRAFT
        ),
        superseded_at=None,
        panel_id=constants.PANEL_ID,
        panel_version=constants.PANEL_VERSION,
        schema_version=constants.PROFILE_SCHEMA_VERSION,
        fields_json=fields_json,
        provenance_json=provenance_json,
        profile_sha256=digest,
        actor_user_id=account.user_id,
        created_at=now,
    )
    session.add(row)
    session.flush()

    record(
        session,
        clock=clock,
        event_type=constants.EVENT_HEALTH_PROFILE_VERSION_CREATED,
        outcome=constants.OUTCOME_SUCCESS,
        subject_type=constants.SUBJECT_HEALTH_PROFILE,
        subject_id=row.health_profile_id,
        actor_user_id=account.user_id,
        payload={
            "version_number": version_number,
            "status": row.status,
            "superseded_id": superseded_id,
        },
    )
    return profile_projection(row)
