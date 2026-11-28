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
from .errors import ApiError, api_error
from .idempotency import canonical_public
from .models import HealthProfile, UserAccount
from .panel import (
    MANDATORY_FIELDS,
    MEASUREMENT_MISSING_REASONS,
    MISSING_REASONS,
    MISSING_REASON_STRUCTURAL,
    OPTIONAL_FIELDS,
    normalize_panel_fields,
    panel_contract_ok,
    validate_panel_keys,
)
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
    """Verify the stored canonical profile document before it is trusted.

    The digest is necessary but not sufficient: an internally consistent hash
    over an invalid envelope must not make an invalid profile authoritative.
    """
    try:
        if (
            row.panel_id != constants.PANEL_ID
            or row.panel_version != constants.PANEL_VERSION
            or row.schema_version != constants.PROFILE_SCHEMA_VERSION
            or not isinstance(row.fields_json, dict)
            or set(row.fields_json) != {"inputs", "units", "missing_reasons"}
            or row.provenance_json != {
                "source_contract_version": constants.SOURCE_CONTRACT_VERSION,
                "source_kind": constants.SOURCE_KIND_MANUAL,
            }
        ):
            raise ValueError("profile envelope mismatch")
        normalized = normalize_panel_fields(
            row.fields_json["inputs"],
            row.fields_json["units"],
            row.fields_json["missing_reasons"],
            allow_absent_mandatory=True,
            strict_reasons=False,
            allow_structural_null=True,
        )
        expected_fields = {
            "inputs": normalized[0],
            "units": normalized[1],
            "missing_reasons": normalized[2],
        }
        if expected_fields != row.fields_json:
            raise ValueError("profile fields are not normalized")
        expected_status = (
            constants.HEALTH_PROFILE_COMPLETE
            if all(normalized[0].get(field) is not None for field in MANDATORY_FIELDS)
            else constants.HEALTH_PROFILE_DRAFT
        )
        if row.superseded_at is None:
            if row.status != expected_status:
                raise ValueError("profile status mismatch")
        elif row.status != constants.HEALTH_PROFILE_SUPERSEDED:
            raise ValueError("profile supersession mismatch")
        expected_digest = profile_sha256(
            panel_id=row.panel_id,
            panel_version=row.panel_version,
            schema_version=row.schema_version,
            fields_json=row.fields_json,
            provenance_json=row.provenance_json,
        )
        if expected_digest != row.profile_sha256:
            raise ValueError("profile digest mismatch")
    except (ApiError, TypeError, ValueError, OverflowError, RecursionError):
        raise api_error("internal_error") from None


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
    if current is not None:
        # Verify the immutable source before using any of its values as merge
        # input; a corrupt row must not be laundered into a fresh digest.
        verify_profile_digest(current)

    old_fields = (
        current.fields_json
        if current is not None
        else {"inputs": {}, "units": {}, "missing_reasons": {}}
    )
    patch_inputs = body.get("inputs")
    patch_units = body.get("units")
    patch_reasons = body.get("missing_reasons")
    if not all(isinstance(value, dict) for value in (patch_inputs, patch_units, patch_reasons)):
        raise api_error("invalid_panel_input")
    validate_panel_keys(patch_inputs, patch_units, patch_reasons)

    merged_inputs = dict(old_fields["inputs"])
    merged_inputs.update(patch_inputs)
    merged_units = dict(old_fields["units"])
    merged_units.update(patch_units)
    merged_reasons = dict(old_fields["missing_reasons"])
    merged_reasons.update(patch_reasons)

    # Explicit null is an affirmative measurement-missing assertion. It must
    # carry a fresh measurement reason from this request; neither a previous
    # measurement reason nor the structural `not_provided` marker is enough.
    # This request-level check is deliberately separate from normalization of
    # the merged canonical record: inherited optional null/not_provided pairs
    # are trusted only after the stored row's digest/envelope was verified.
    for field, value in patch_inputs.items():
        if value is None and field in OPTIONAL_FIELDS:
            reason = patch_reasons.get(field)
            if reason is None or reason == MISSING_REASON_STRUCTURAL:
                raise api_error("missing_reason_mismatch")
            if not isinstance(reason, str) or reason not in MEASUREMENT_MISSING_REASONS:
                raise api_error("invalid_panel_input")
        if value is None and field in old_fields["units"] and field not in patch_units:
            merged_units.pop(field, None)

    # A client cannot relabel an existing null as a structural omission merely
    # by patching its reason while omitting the input. Structural reasons are
    # assigned by the canonicalizer; measurement reasons must be explicit.
    for field, reason in patch_reasons.items():
        if not isinstance(reason, str) or reason not in MISSING_REASONS:
            raise api_error("invalid_panel_input")
        if reason == MISSING_REASON_STRUCTURAL and merged_inputs.get(field) is None:
            raise api_error("missing_reason_mismatch")
        if field in patch_inputs and patch_inputs[field] is not None:
            raise api_error("missing_reason_mismatch")

    inputs, units, missing_reasons, _stage_complete = normalize_panel_fields(
        merged_inputs,
        merged_units,
        merged_reasons,
        allow_absent_mandatory=True,
        strict_reasons=False,
        # Safe here only because client-supplied explicit nulls and reasons
        # above were validated independently; untouched values came from the
        # digest-verified canonical row (or are defaults on first creation).
        allow_structural_null=True,
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
            if all(inputs.get(field) is not None for field in MANDATORY_FIELDS)
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
