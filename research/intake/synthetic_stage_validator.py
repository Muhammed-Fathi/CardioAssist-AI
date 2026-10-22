"""Stage-aware intake validator for SYNTHETIC fixtures only.

No I/O, persistence, network, model fitting, predictions or patient values in
review objects. This prototype is never used by a production route or clinical
contract. A ``synthetic`` flag is a caller assertion, not proof of provenance.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping


STAGE_FIELDS: Mapping[str, tuple[str, ...]] = MappingProxyType({
    "history_only": ("age", "sex", "cp"),
    "resting_assessment": ("age", "sex", "cp", "trestbps", "restecg"),
    "resting_plus_labs": (
        "age", "sex", "cp", "trestbps", "restecg", "chol", "fbs",
    ),
    "includes_exercise_tests": (
        "age", "sex", "cp", "trestbps", "restecg", "chol", "fbs",
        "thalach", "exang", "oldpeak", "slope",
    ),
})
MANDATORY_HISTORY = frozenset({"age", "sex", "cp"})


class FieldKind(str, Enum):
    """The only field types represented by this model-independent prototype."""

    NUMERICAL = "numerical"
    CATEGORICAL = "categorical"


class NumericRule(str, Enum):
    """Conservative value checks; these are not clinical reference ranges."""

    STRICTLY_POSITIVE = "strictly_positive"
    FINITE_SIGNED = "finite_signed"


@dataclass(frozen=True, slots=True)
class FieldDefinition:
    """Immutable UCI-45-style synthetic field metadata.

    ``source_codes`` are categorical source codes in a fixed, nominal ordering;
    their numerical labels must not be interpreted as an ordinal scale. A
    ``unit`` of ``None`` means no unit is asserted by this prototype (not that
    the physical quantity is unitless).
    """

    name: str
    kind: FieldKind
    unit: str | None = None
    source_codes: tuple[int, ...] = ()
    numeric_rule: NumericRule | None = None


# Source-code order is explicit and stable. It is not learned from records.
# Physical units below are UCI-45-style input conventions for synthetic tests,
# not ratified clinical definitions or permission to process a real cohort.
FIELD_DEFINITIONS: Mapping[str, FieldDefinition] = MappingProxyType({
    "age": FieldDefinition(
        "age", FieldKind.NUMERICAL, unit="years",
        numeric_rule=NumericRule.STRICTLY_POSITIVE,
    ),
    "sex": FieldDefinition(
        "sex", FieldKind.CATEGORICAL, source_codes=(0, 1),
    ),
    "cp": FieldDefinition(
        "cp", FieldKind.CATEGORICAL, source_codes=(1, 2, 3, 4),
    ),
    "trestbps": FieldDefinition(
        "trestbps", FieldKind.NUMERICAL, unit="mmHg",
        numeric_rule=NumericRule.STRICTLY_POSITIVE,
    ),
    "restecg": FieldDefinition(
        "restecg", FieldKind.CATEGORICAL, source_codes=(0, 1, 2),
    ),
    "chol": FieldDefinition(
        "chol", FieldKind.NUMERICAL, unit="mg/dL",
        numeric_rule=NumericRule.STRICTLY_POSITIVE,
    ),
    "fbs": FieldDefinition(
        "fbs", FieldKind.CATEGORICAL, source_codes=(0, 1),
    ),
    "thalach": FieldDefinition(
        "thalach", FieldKind.NUMERICAL, unit="bpm",
        numeric_rule=NumericRule.STRICTLY_POSITIVE,
    ),
    "exang": FieldDefinition(
        "exang", FieldKind.CATEGORICAL, source_codes=(0, 1),
    ),
    # The source-specific unit for oldpeak is not declared here. It remains
    # finite and signed; no conversion, clipping or zero-as-missing rule applies.
    "oldpeak": FieldDefinition(
        "oldpeak", FieldKind.NUMERICAL,
        numeric_rule=NumericRule.FINITE_SIGNED,
    ),
    "slope": FieldDefinition(
        "slope", FieldKind.CATEGORICAL, source_codes=(1, 2, 3),
    ),
})

CATEGORY_ORDER: Mapping[str, tuple[int, ...]] = MappingProxyType({
    name: definition.source_codes
    for name, definition in FIELD_DEFINITIONS.items()
    if definition.kind is FieldKind.CATEGORICAL
})
# Backwards-compatible views used by the M2b.1 validator and its tests.
CATEGORICAL_CODES: Mapping[str, frozenset[int]] = MappingProxyType({
    name: frozenset(codes) for name, codes in CATEGORY_ORDER.items()
})
UNIT_CONVENTIONS: Mapping[str, str] = MappingProxyType({
    name: definition.unit
    for name, definition in FIELD_DEFINITIONS.items()
    if definition.unit is not None
})
POSITIVE_NUMERICAL = frozenset(
    name for name, definition in FIELD_DEFINITIONS.items()
    if definition.numeric_rule is NumericRule.STRICTLY_POSITIVE
)
SIGNED_NUMERICAL = frozenset(
    name for name, definition in FIELD_DEFINITIONS.items()
    if definition.numeric_rule is NumericRule.FINITE_SIGNED
)

# Structural absence is distinct from an explicit null measurement. Both are
# observable in output, and every unavailable stage field has a reason.
MEASUREMENT_MISSING_REASONS = frozenset((
    "not_measured", "not_available_at_time", "unknown",
))
STRUCTURAL_MISSING_REASON = "not_provided"
MISSING_REASON_ORDER = (
    "not_measured", "not_available_at_time", "unknown", "not_provided",
)
MISSING_REASONS = frozenset(MISSING_REASON_ORDER)


class IntakeValidationError(ValueError):
    """Safe validation errors that never include submitted field values."""


@dataclass(frozen=True, slots=True)
class SyntheticIntakeReview:
    stage: str
    present_fields: tuple[str, ...]
    missing_fields_with_reason: tuple[tuple[str, str], ...]
    stage_complete: bool
    synthetic_only: bool = True
    prediction_status: str = "NO_PREDICTION_GATE_PT_CLOSED"
    unknown_category_fields: tuple[str, ...] = ()


def _finite_real(value: Any) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return isfinite(value)
    except OverflowError:
        # ``math.isfinite`` converts Python ints to float; sufficiently large
        # synthetic inputs can overflow that conversion. Treat them as invalid
        # numeric values so callers receive the validator's controlled error.
        return False


def review_synthetic_stage_input(
    payload: Mapping[str, Any],
    *,
    unknown_category_policy: str = "error",
) -> SyntheticIntakeReview:
    """Validate one UCI-45-style synthetic intake bundle.

    Accepted top-level keys and predictors are exact allowlists. Optional
    fields omitted from ``features`` require the ``not_provided`` reason; an
    explicit null instead requires one of the measurement missing reasons.
    Numerical units are exact-token checks only; values are never converted.

    ``unknown_category_policy="indicator"`` is available only for synthetic
    preprocessing tests. It permits an integer code outside the declared
    source-code vocabulary so the encoder can set its dedicated unknown bit.
    The default rejects unknown codes.
    """
    if not isinstance(payload, Mapping):
        raise IntakeValidationError("Synthetic intake must be a mapping.")
    if set(payload) != {"synthetic", "stage", "features", "units", "missing_reasons"}:
        raise IntakeValidationError("Synthetic intake metadata keys mismatch.")
    if payload["synthetic"] is not True:
        raise IntakeValidationError("Only explicitly synthetic fixtures are supported.")
    if (
        not isinstance(unknown_category_policy, str)
        or unknown_category_policy not in {"error", "indicator"}
    ):
        raise IntakeValidationError("Unsupported unknown-category policy.")

    stage = payload["stage"]
    if not isinstance(stage, str) or stage not in STAGE_FIELDS:
        raise IntakeValidationError("Unknown staged intake scenario.")
    features = payload["features"]
    units = payload["units"]
    reasons = payload["missing_reasons"]
    if not isinstance(features, Mapping) or not isinstance(units, Mapping) or not isinstance(reasons, Mapping):
        raise IntakeValidationError("Expected features, units and missing_reasons maps.")
    if not all(isinstance(key, str) for key in features):
        raise IntakeValidationError("Field names must be strings.")
    if not all(isinstance(key, str) for key in units):
        raise IntakeValidationError("Unit field names must be strings.")
    if not all(isinstance(key, str) for key in reasons):
        raise IntakeValidationError("Missing-reason field names must be strings.")

    stage_order = STAGE_FIELDS[stage]
    accepted = set(stage_order)
    feature_names = set(features)
    if not feature_names.issubset(accepted):
        raise IntakeValidationError("Unknown, unavailable-stage or prohibited predictor field.")
    if not MANDATORY_HISTORY.issubset(feature_names):
        raise IntakeValidationError("Synthetic core history fields must be present.")

    null_fields = {field for field, value in features.items() if value is None}
    absent_fields = accepted - feature_names
    if null_fields & MANDATORY_HISTORY:
        raise IntakeValidationError("History fields cannot be missing in this prototype.")
    missing_fields = null_fields | absent_fields
    if set(reasons) != missing_fields:
        raise IntakeValidationError("Every unavailable stage field needs exactly one reason.")
    for field, reason in reasons.items():
        if not isinstance(reason, str) or reason not in MISSING_REASONS:
            raise IntakeValidationError("Unsupported missing-value reason.")
        if field in absent_fields and reason != STRUCTURAL_MISSING_REASON:
            raise IntakeValidationError("An omitted field requires the not_provided reason.")
        if field in null_fields and reason not in MEASUREMENT_MISSING_REASONS:
            raise IntakeValidationError("A null measurement requires an explicit measurement reason.")

    measured_unit_fields = {
        field for field, value in features.items()
        if value is not None and FIELD_DEFINITIONS[field].unit is not None
    }
    if set(units) != measured_unit_fields:
        raise IntakeValidationError("Measured fields require exact explicit unit keys.")
    for field in measured_unit_fields:
        if units[field] != FIELD_DEFINITIONS[field].unit:
            raise IntakeValidationError("Unit mismatch in synthetic intake.")

    unknown_categories: list[str] = []
    for field, value in features.items():
        if value is None:
            continue
        definition = FIELD_DEFINITIONS[field]
        if definition.kind is FieldKind.CATEGORICAL:
            if type(value) is not int:
                raise IntakeValidationError("Categorical source codes must be integers.")
            if value not in definition.source_codes:
                if unknown_category_policy == "error":
                    raise IntakeValidationError("Unknown categorical source code.")
                unknown_categories.append(field)
        elif definition.kind is FieldKind.NUMERICAL:
            if not _finite_real(value):
                raise IntakeValidationError("Numerical values must be finite real numbers.")
            if (
                definition.numeric_rule is NumericRule.STRICTLY_POSITIVE
                and value <= 0
            ):
                raise IntakeValidationError("Nonpositive measurement is unavailable, not a valid value.")
        else:  # A registry extension must be reviewed before becoming usable.
            raise IntakeValidationError("Unexpected field definition.")

    present = tuple(
        field for field in stage_order
        if field in features and features[field] is not None
    )
    missing = tuple(
        (field, reasons[field])
        for field in stage_order
        if field in missing_fields
    )
    return SyntheticIntakeReview(
        stage=stage,
        present_fields=present,
        missing_fields_with_reason=missing,
        stage_complete=not missing_fields,
        unknown_category_fields=tuple(
            field for field in stage_order if field in unknown_categories
        ),
    )
