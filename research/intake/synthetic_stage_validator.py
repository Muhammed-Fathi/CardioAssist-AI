"""Stage-aware intake *prototype* validator for SYNTHETIC fixtures only.

No I/O, persistence, network, model fitting, predictions or patient values in
return objects. Not linked to production routes or approved clinical contracts.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping


STAGE_FIELDS: dict[str, tuple[str, ...]] = {
    "history_only": ("age", "sex", "cp"),
    "resting_assessment": ("age", "sex", "cp", "trestbps", "restecg"),
    "resting_plus_labs": (
        "age", "sex", "cp", "trestbps", "restecg", "chol", "fbs",
    ),
    "includes_exercise_tests": (
        "age", "sex", "cp", "trestbps", "restecg", "chol", "fbs",
        "thalach", "exang", "oldpeak", "slope",
    ),
}
MANDATORY_HISTORY = frozenset({"age", "sex", "cp"})
CATEGORICAL_CODES: dict[str, frozenset[int]] = {
    "sex": frozenset((0, 1)),
    "cp": frozenset((1, 2, 3, 4)),
    "restecg": frozenset((0, 1, 2)),
    "fbs": frozenset((0, 1)),
    "exang": frozenset((0, 1)),
    "slope": frozenset((1, 2, 3)),
}
# Units are conventions for this synthetic UCI-45 representation only.
# Source-specific unit mapping must be clinically approved before a real UI.
UNIT_CONVENTIONS = {
    "age": "years",
    "trestbps": "mmHg",
    "chol": "mg/dL",
    "thalach": "bpm",
}
POSITIVE_NUMERICAL = frozenset(("age", "trestbps", "chol", "thalach"))
SIGNED_NUMERICAL = frozenset(("oldpeak",))
MISSING_REASONS = frozenset(("not_measured", "not_available_at_time", "unknown"))


class IntakeValidationError(ValueError):
    """Safe errors: never include the original submitted values."""


@dataclass(frozen=True, slots=True)
class SyntheticIntakeReview:
    stage: str
    present_fields: tuple[str, ...]
    missing_fields_with_reason: tuple[tuple[str, str], ...]
    stage_complete: bool
    synthetic_only: bool = True
    prediction_status: str = "NO_PREDICTION_GATE_PT_CLOSED"


def _finite_real(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and isfinite(value)
    )


def review_synthetic_stage_input(payload: Mapping[str, Any]) -> SyntheticIntakeReview:
    """Validate a UCI-45-style *synthetic* clinician-intake fixture.

    Reject target, ca, thal, IDs, angiography, wearables, unapproved fields
    and leakage by exact allowlist. Raw input values NEVER escape the result.
    The return is field-name metadata only and can never supply CAD scores.
    """
    if not isinstance(payload, Mapping):
        raise IntakeValidationError("Synthetic intake must be a mapping.")
    if set(payload) != {"synthetic", "stage", "features", "units", "missing_reasons"}:
        raise IntakeValidationError("Synthetic intake metadata keys mismatch.")
    if payload["synthetic"] is not True:
        raise IntakeValidationError("Only explicitly synthetic fixtures are supported.")

    stage = payload["stage"]
    if not isinstance(stage, str) or stage not in STAGE_FIELDS:
        raise IntakeValidationError("Unknown staged intake scenario.")
    features = payload["features"]
    units = payload["units"]
    reasons = payload["missing_reasons"]
    if not isinstance(features, dict) or not isinstance(units, dict) or not isinstance(reasons, dict):
        raise IntakeValidationError("Expected features, units and missing_reasons maps.")
    if not all(isinstance(k, str) for k in features):
        raise IntakeValidationError("Field names must be strings.")

    accepted = set(STAGE_FIELDS[stage])
    if not set(features).issubset(accepted):
        raise IntakeValidationError("Unknown, unavailable-stage or prohibited predictor field.")
    if not MANDATORY_HISTORY.issubset(features):
        raise IntakeValidationError("Synthetic core history fields must be present.")

    null_fields = {field for field, value in features.items() if value is None}
    if null_fields & MANDATORY_HISTORY:
        raise IntakeValidationError("History fields cannot be missing in this prototype.")
    if set(reasons) != null_fields or not all(
        isinstance(reason, str) and reason in MISSING_REASONS
        for reason in reasons.values()
    ):
        raise IntakeValidationError("Each null needs an explicit accepted missing reason.")

    measured_unit_fields = {
        field for field in features
        if field in UNIT_CONVENTIONS and features[field] is not None
    }
    if set(units) != measured_unit_fields:
        raise IntakeValidationError("Numeric measured fields require exact explicit unit keys.")
    for field in measured_unit_fields:
        if units[field] != UNIT_CONVENTIONS[field]:
            raise IntakeValidationError("Unit mismatch in synthetic intake.")

    for field, value in features.items():
        if value is None:
            continue
        if field in CATEGORICAL_CODES:
            if type(value) is not int or value not in CATEGORICAL_CODES[field]:
                raise IntakeValidationError("Invalid categorical code in synthetic intake.")
        elif field in POSITIVE_NUMERICAL:
            if not _finite_real(value) or value <= 0:
                raise IntakeValidationError("Nonpositive or nonfinite physiological input.")
        elif field in SIGNED_NUMERICAL:
            # Negative ST-depression relative-to-rest values occur in UCI source;
            # do not clip them or silently infer that they are invalid.
            if not _finite_real(value):
                raise IntakeValidationError("Nonfinite oldpeak measurement.")
        else:
            raise IntakeValidationError("Unexpected field definition.")

    present = tuple(k for k in STAGE_FIELDS[stage] if k in features and features[k] is not None)
    missing = tuple(
        (k, reasons[k])
        for k in STAGE_FIELDS[stage]
        if k in null_fields
    )
    return SyntheticIntakeReview(
        stage=stage,
        present_fields=present,
        missing_fields_with_reason=missing,
        stage_complete=len(present) == len(STAGE_FIELDS[stage]),
    )
