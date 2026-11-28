"""DA-A2 resting panel contract validation for C2 (stdlib only).

Term-1-owned re-declaration of the exact ``da_a2_resting_v1`` rules referenced
by OQ-4: ordered fields and closed vocabularies from
``research/intake/synthetic_stage_validator.py`` (field definitions, units,
missing-reason vocabulary) and the prohibited-field union from
``ai/panels.py::ALL_PROHIBITED_FIELDS``. The backend never imports ``ai`` or
``research`` (numpy/ML dependencies are forbidden in backend-only CI and
``backend.app.main`` must never import ``ai.*``); the literals are copied here
and pinned by tests.

Validation never returns a score and never touches an artifact or provider.
Every failure is a closed-catalogue ``ApiError``:

* prohibited leakage / laboratory / wearable / outcome field names
  -> ``422 prohibited_clinical_field``
* any other unknown key, bad value, bad unit or bad reason vocabulary
  -> ``422 invalid_panel_input``
* a reason supplied for a present value, or a null optional field without a
  reason (strict mode) -> ``422 missing_reason_mismatch``
"""

from __future__ import annotations

import math
from typing import Any

from .constants import PANEL_ID, PANEL_VERSION
from .errors import api_error

# Ordered panel fields; mandatory history fields first (stage rule).
PANEL_FIELDS: tuple[str, ...] = ("age", "sex", "cp", "trestbps", "restecg")
MANDATORY_FIELDS: tuple[str, ...] = ("age", "sex", "cp")
OPTIONAL_FIELDS: tuple[str, ...] = ("trestbps", "restecg")

# Exact unit tokens for the numerical fields; categorical fields take no unit.
UNIT_FIELDS: dict[str, str] = {"age": "years", "trestbps": "mmHg"}

# Closed missing-reason vocabulary (structural default + measurement reasons).
MISSING_REASON_STRUCTURAL = "not_provided"
MEASUREMENT_MISSING_REASONS: frozenset[str] = frozenset(
    {"not_measured", "not_available_at_time", "unknown"}
)
MISSING_REASONS: frozenset[str] = MEASUREMENT_MISSING_REASONS | {
    MISSING_REASON_STRUCTURAL
}

# Closed categorical codes.
CATEGORICAL_CODES: dict[str, frozenset[int]] = {
    "sex": frozenset({0, 1}),
    "cp": frozenset({1, 2, 3, 4}),
    "restecg": frozenset({0, 1, 2}),
}

# Closed prohibited field names (lab/outcome/wearable/leakage leakage): the
# union of research.uci412.source_spec PROHIBITED_PREDICTORS + ECHO_COLUMNS,
# ai/panels EXTRA_WEARABLE_OR_LEAKAGE_FIELDS, the UCI-45 exercise/lab fields,
# and the outcome aliases — lowercased for case-insensitive matching.
PROHIBITED_FIELDS: frozenset[str] = frozenset(
    {
        # outcome / angiography leakage
        "cath", "target", "num", "lad", "lcx", "rca", "ca", "thal", "lmt",
        "ladprox", "laddist", "diag", "cxmain", "ramus", "om1", "om2",
        "rcaprox", "rcadist", "cmo", "cday", "cyr",
        # identifiers
        "id", "ccf", "name", "site", "patient_id", "patient_ref", "mrn",
        # wearable / monitoring leakage
        "wearable_heart_rate", "heart_rate_bpm", "steps", "wearable_ecg",
        "monitoring_observation", "spo2", "hrv", "ppg", "resting_hr_wearable",
        "smartwatch_ecg", "step_count", "sleep_duration", "syntax_score",
        "stenosis_percent",
        # echo columns
        "ef-tte", "region rwma", "vhd",
        # UCI-45 laboratory / exercise fields outside the resting panel
        "chol", "fbs", "thalach", "exang", "oldpeak", "slope",
    }
)


def _reject(code: str):
    return api_error(code)


def _check_keys(mapping: dict[str, Any], *, label: str) -> None:
    for key in mapping:
        if key in PANEL_FIELDS:
            continue
        if key.lower() in PROHIBITED_FIELDS:
            raise _reject("prohibited_clinical_field")
        raise _reject("invalid_panel_input")


def _validate_value(field: str, value: Any) -> None:
    if field in UNIT_FIELDS:  # numerical, strictly positive, finite
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise _reject("invalid_panel_input")
        try:
            numeric = float(value)
        except (OverflowError, ValueError):
            raise _reject("invalid_panel_input") from None
        if not math.isfinite(numeric) or numeric <= 0:
            raise _reject("invalid_panel_input")
        return
    # categorical: integer codes only (0 is a valid categorical code)
    if isinstance(value, bool) or not isinstance(value, int):
        raise _reject("invalid_panel_input")
    if value not in CATEGORICAL_CODES[field]:
        raise _reject("invalid_panel_input")


def validate_panel_keys(
    inputs: dict[str, Any],
    units: dict[str, Any],
    missing_reasons: dict[str, Any],
) -> None:
    """Validate map shapes, closed field names and allowed unit keys only."""
    if not isinstance(inputs, dict) or not isinstance(units, dict) or not isinstance(
        missing_reasons, dict
    ):
        raise _reject("invalid_panel_input")
    _check_keys(inputs, label="inputs")
    _check_keys(units, label="units")
    _check_keys(missing_reasons, label="missing_reasons")
    for key in units:
        if key not in UNIT_FIELDS:
            raise _reject("invalid_panel_input")


def normalize_panel_fields(
    inputs: dict[str, Any],
    units: dict[str, Any],
    missing_reasons: dict[str, Any],
    *,
    allow_absent_mandatory: bool,
    strict_reasons: bool,
    allow_structural_null: bool = False,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], bool]:
    """Validate and normalize one panel payload.

    Returns ``(inputs, units, missing_reasons, stage_complete)`` where:

    * every key is a closed panel field (or raises);
    * every present value passes the DA-A2 resting rules;
    * units are derived from present numerical fields (exact tokens);
    * reasons are dropped for present values, defaulted to ``not_provided``
      for absent optional fields, and required for null optional fields;
    * ``stage_complete`` is true iff all five fields are present and valid.

    ``allow_absent_mandatory`` permits a DRAFT profile (H1b partial progress);
    ``strict_reasons`` rejects a client-supplied reason for a field it also
    presents (S1 payload semantics) instead of dropping it. Internal canonical
    row verification may set ``allow_structural_null`` because an omitted
    optional value is serialized as null plus ``not_provided`` after validation.
    """
    validate_panel_keys(inputs, units, missing_reasons)

    # Reject (strict) or drop (merge) reasons attached to present values.
    present = {
        field
        for field in PANEL_FIELDS
        if field in inputs and inputs[field] is not None
    }
    for field in missing_reasons:
        if field in present:
            if strict_reasons:
                raise _reject("missing_reason_mismatch")
            # merge path: stale inherited reason, dropped below

    normalized_inputs: dict[str, Any] = {}
    normalized_reasons: dict[str, Any] = {}
    for field in PANEL_FIELDS:
        supplied = inputs.get(field, None)
        has_key = field in inputs
        if has_key and supplied is not None:
            _validate_value(field, supplied)
            normalized_inputs[field] = supplied
        elif has_key and supplied is None:
            if field in MANDATORY_FIELDS:
                # A history field cannot be explicitly null; omit it instead.
                raise _reject("invalid_panel_input")
            reason = missing_reasons.get(field)
            if reason is None:
                raise _reject("missing_reason_mismatch")
            if not isinstance(reason, str) or reason not in MISSING_REASONS:
                raise _reject("invalid_panel_input")
            if reason == MISSING_REASON_STRUCTURAL and not allow_structural_null:
                raise _reject("missing_reason_mismatch")
            normalized_inputs[field] = None
            normalized_reasons[field] = reason
        else:  # absent key
            if field in MANDATORY_FIELDS:
                if not allow_absent_mandatory:
                    raise _reject("invalid_panel_input")
                # Draft: absent mandatory field; no reason required.
                if field in missing_reasons:
                    reason = missing_reasons[field]
                    if not isinstance(reason, str) or reason not in MISSING_REASONS:
                        raise _reject("invalid_panel_input")
                    normalized_reasons[field] = reason
                continue
            # Optional: default to null + structural reason on first creation;
            # an inherited null keeps its stored reason (checked above).
            reason = missing_reasons.get(field, MISSING_REASON_STRUCTURAL)
            if not isinstance(reason, str) or reason not in MISSING_REASONS:
                raise _reject("invalid_panel_input")
            normalized_inputs[field] = None
            normalized_reasons[field] = reason

    # Units are derived state: exact token for every present numerical field,
    # nothing for absent/null fields. A unit supplied without its value is
    # inconsistent input, not a value to silently discard.
    for field in units:
        if normalized_inputs.get(field) is None:
            raise _reject("invalid_panel_input")
    normalized_units = {
        field: UNIT_FIELDS[field]
        for field in UNIT_FIELDS
        if normalized_inputs.get(field) is not None
    }
    for field, token in UNIT_FIELDS.items():
        if normalized_inputs.get(field) is not None and units.get(field) != token:
            raise _reject("invalid_panel_input")

    stage_complete = all(
        normalized_inputs.get(field) is not None for field in PANEL_FIELDS
    )
    return normalized_inputs, normalized_units, normalized_reasons, stage_complete


def panel_contract_ok(panel_id: Any, panel_version: Any) -> bool:
    """Exact pinned panel identity (OQ-4 literals)."""
    return panel_id == PANEL_ID and panel_version == PANEL_VERSION
