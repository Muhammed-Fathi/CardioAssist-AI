"""Reusable synthetic-only preprocessing primitives; no ML dependency.

The fitted object learns numerical medians from the explicitly supplied
synthetic training records only. It has no API for receiving holdout data while
fitting. Category columns come from the fixed source-code registry, not from
observed samples. This module does not fit, select or evaluate a CAD model.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from statistics import median
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from research.intake.synthetic_stage_validator import (
    CATEGORY_ORDER,
    FIELD_DEFINITIONS,
    MISSING_REASON_ORDER,
    STAGE_FIELDS,
    FieldKind,
    IntakeValidationError,
    NumericRule,
    review_synthetic_stage_input,
)


class UnknownCategoryPolicy(str, Enum):
    """Unknown categorical source-code behavior for synthetic transforms."""

    ERROR = "error"
    INDICATOR = "indicator"


@dataclass(frozen=True, slots=True)
class CategoricalEncoding:
    """A stable one-hot result; an unknown value is never echoed."""

    category_order: tuple[int, ...]
    one_hot: tuple[int, ...]
    unknown_category: bool


def _coerce_unknown_category_policy(
    policy: UnknownCategoryPolicy | str,
) -> UnknownCategoryPolicy:
    try:
        return UnknownCategoryPolicy(policy)
    except (TypeError, ValueError):
        raise IntakeValidationError("Unsupported unknown-category policy.") from None


def encode_categorical(
    field: str,
    value: Any,
    *,
    unknown_category_policy: UnknownCategoryPolicy | str = UnknownCategoryPolicy.ERROR,
) -> CategoricalEncoding:
    """One-hot encode an integer source code using fixed registry ordering.

    With ``ERROR`` (the default), unrecognized codes are rejected. With
    ``INDICATOR``, an integer code outside the source vocabulary maps to an
    all-zero known-category vector plus ``unknown_category=True``. The
    preprocessor exposes a dedicated indicator column for that state, so it
    cannot silently collapse into a known category or a missing value.
    """
    definition = FIELD_DEFINITIONS.get(field)
    if definition is None or definition.kind is not FieldKind.CATEGORICAL:
        raise IntakeValidationError("The requested field is not categorical.")
    if type(value) is not int:
        raise IntakeValidationError("Categorical source codes must be integers.")
    policy = _coerce_unknown_category_policy(unknown_category_policy)
    category_order = CATEGORY_ORDER[field]
    unknown = value not in category_order
    if unknown and policy is UnknownCategoryPolicy.ERROR:
        raise IntakeValidationError("Unknown categorical source code.")
    return CategoricalEncoding(
        category_order=category_order,
        one_hot=tuple(int(value == code) for code in category_order) if not unknown
        else tuple(0 for _ in category_order),
        unknown_category=unknown,
    )


@dataclass(frozen=True, slots=True)
class MissingnessIndicator:
    """Safe per-field metadata; never includes the submitted measurement."""

    field: str
    missing: bool
    reason: str | None
    unknown_category: bool = False


@dataclass(frozen=True, slots=True)
class PreprocessedSyntheticRecord:
    """Deterministic numeric vector plus explicit missingness metadata.

    The vector contains feature columns only. Patient identifiers, labels,
    input values outside the declared feature list, predictions and explanations
    are not represented in this result type.
    """

    stage: str
    feature_names: tuple[str, ...]
    values: tuple[float, ...]
    missingness: tuple[MissingnessIndicator, ...]
    synthetic_only: bool = True
    prediction_status: str = "NO_PREDICTION_GATE_PT_CLOSED"

    def __post_init__(self) -> None:
        if not isinstance(self.stage, str) or self.stage not in STAGE_FIELDS:
            raise ValueError("Preprocessed stage is invalid.")
        if not isinstance(self.feature_names, tuple) or not isinstance(self.values, tuple):
            raise ValueError("Preprocessed columns and values must be immutable tuples.")
        if self.feature_names != preprocessing_feature_names(self.stage):
            raise ValueError("Preprocessed columns do not match the declared stage.")
        if len(self.feature_names) != len(self.values):
            raise ValueError("Preprocessed vector shape mismatch.")
        if not all(
            isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)
            for value in self.values
        ):
            raise ValueError("Preprocessed values must be finite real numbers.")
        if not isinstance(self.missingness, tuple) or any(
            not isinstance(item, MissingnessIndicator)
            or type(item.missing) is not bool
            or type(item.unknown_category) is not bool
            for item in self.missingness
        ):
            raise ValueError("Missingness metadata must be an immutable tuple of valid indicators.")
        if tuple(item.field for item in self.missingness) != STAGE_FIELDS[self.stage]:
            raise ValueError("Missingness metadata does not match the declared stage.")
        if any(
            (item.missing and item.reason not in MISSING_REASON_ORDER)
            or (not item.missing and item.reason is not None)
            for item in self.missingness
        ):
            raise ValueError("Missingness metadata is invalid.")
        if self.synthetic_only is not True:
            raise ValueError("Only synthetic preprocessing results are supported.")
        if self.prediction_status != "NO_PREDICTION_GATE_PT_CLOSED":
            raise ValueError("Preprocessing cannot produce a prediction status other than no prediction.")

    def as_feature_mapping(self) -> Mapping[str, float]:
        """Return a read-only name-to-value view with a fresh backing mapping."""
        return MappingProxyType(dict(zip(self.feature_names, self.values, strict=True)))


@dataclass(frozen=True, slots=True)
class FittedSyntheticPreprocessor:
    """Immutable preprocessing parameters learned from synthetic training rows."""

    stage: str
    numeric_medians: tuple[tuple[str, float], ...]
    unknown_category_policy: UnknownCategoryPolicy = UnknownCategoryPolicy.ERROR

    def __post_init__(self) -> None:
        if not isinstance(self.stage, str) or self.stage not in STAGE_FIELDS:
            raise IntakeValidationError("Unknown staged intake scenario.")
        if not isinstance(self.numeric_medians, tuple) or any(
            not isinstance(item, tuple) or len(item) != 2
            for item in self.numeric_medians
        ):
            raise IntakeValidationError("Fitted statistics must be immutable name/value pairs.")
        expected_numeric_fields = tuple(
            field for field in STAGE_FIELDS[self.stage]
            if FIELD_DEFINITIONS[field].kind is FieldKind.NUMERICAL
        )
        if tuple(field for field, _ in self.numeric_medians) != expected_numeric_fields:
            raise IntakeValidationError("Fitted statistics do not match the declared stage.")
        for field, value in self.numeric_medians:
            if (
                not isinstance(field, str)
                or not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not isfinite(value)
            ):
                raise IntakeValidationError("Training statistics must be finite real numbers.")
            if (
                FIELD_DEFINITIONS[field].numeric_rule is NumericRule.STRICTLY_POSITIVE
                and value <= 0
            ):
                raise IntakeValidationError("Positive-field training statistic must be positive.")
        if not isinstance(self.unknown_category_policy, UnknownCategoryPolicy):
            raise IntakeValidationError("Unsupported unknown-category policy.")

    @property
    def feature_names(self) -> tuple[str, ...]:
        return preprocessing_feature_names(self.stage)

    def transform(self, payload: Mapping[str, Any]) -> PreprocessedSyntheticRecord:
        """Transform one separate synthetic row without changing it or this fit."""
        review = review_synthetic_stage_input(
            payload,
            unknown_category_policy=self.unknown_category_policy.value,
        )
        if review.stage != self.stage:
            raise IntakeValidationError("Transform stage differs from fitted stage.")

        features = payload["features"]
        reasons = payload["missing_reasons"]
        medians = dict(self.numeric_medians)
        output: list[float] = []
        missingness: list[MissingnessIndicator] = []

        for field in STAGE_FIELDS[self.stage]:
            definition = FIELD_DEFINITIONS[field]
            is_missing = field not in features or features[field] is None
            reason = reasons[field] if is_missing else None
            unknown = False

            if definition.kind is FieldKind.NUMERICAL:
                if is_missing:
                    # Every numeric field in the stage must have an observed
                    # synthetic training value; fit fails rather than inventing
                    # an imputation constant.
                    encoded_number = medians[field]
                else:
                    encoded_number = float(features[field])
                output.append(float(encoded_number))
            elif definition.kind is FieldKind.CATEGORICAL:
                if is_missing:
                    one_hot = tuple(0 for _ in definition.source_codes)
                else:
                    encoded = encode_categorical(
                        field,
                        features[field],
                        unknown_category_policy=self.unknown_category_policy,
                    )
                    one_hot = encoded.one_hot
                    unknown = encoded.unknown_category
                output.extend(float(bit) for bit in one_hot)
                output.append(float(unknown))
            else:  # A registry extension must be reviewed before becoming usable.
                raise IntakeValidationError("Unexpected field definition.")

            output.append(float(is_missing))
            output.extend(float(reason == item) for item in MISSING_REASON_ORDER)
            missingness.append(MissingnessIndicator(
                field=field,
                missing=is_missing,
                reason=reason,
                unknown_category=unknown,
            ))

        return PreprocessedSyntheticRecord(
            stage=self.stage,
            feature_names=self.feature_names,
            values=tuple(output),
            missingness=tuple(missingness),
        )


def preprocessing_feature_names(stage: str) -> tuple[str, ...]:
    """Return the fixed, stage-specific matrix column order."""
    if not isinstance(stage, str) or stage not in STAGE_FIELDS:
        raise IntakeValidationError("Unknown staged intake scenario.")
    names: list[str] = []
    for field in STAGE_FIELDS[stage]:
        definition = FIELD_DEFINITIONS[field]
        if definition.kind is FieldKind.CATEGORICAL:
            names.extend(f"{field}__category_{code}" for code in definition.source_codes)
            names.append(f"{field}__unknown_category")
        else:
            names.append(field)
        names.append(f"{field}__missing")
        names.extend(
            f"{field}__missing_reason__{reason}"
            for reason in MISSING_REASON_ORDER
        )
    return tuple(names)


def fit_synthetic_preprocessor(
    training_records: Iterable[Mapping[str, Any]],
    *,
    unknown_category_policy: UnknownCategoryPolicy | str = UnknownCategoryPolicy.ERROR,
) -> FittedSyntheticPreprocessor:
    """Fit median imputation on a synthetic training iterable only.

    There is deliberately no holdout/evaluation argument. Every row must pass
    the standalone synthetic-stage validator, use the same stage, and contain
    no target, identifier, angiography, site or wearable fields. Numeric
    medians are the only data-dependent statistics. Category order and output
    dimensions are fixed by ``FIELD_DEFINITIONS`` and are never learned from
    either the training or transformed records.
    """
    policy = _coerce_unknown_category_policy(unknown_category_policy)
    if isinstance(training_records, (str, bytes, Mapping)):
        raise IntakeValidationError("Training input must be an iterable of synthetic records.")
    try:
        records = tuple(training_records)
    except TypeError:
        raise IntakeValidationError("Training input must be an iterable of synthetic records.") from None
    if not records:
        raise IntakeValidationError("At least one synthetic training record is required.")

    stage: str | None = None
    observed: dict[str, list[float]] = {}
    for record in records:
        if not isinstance(record, Mapping):
            raise IntakeValidationError("Each training item must be a synthetic record.")
        candidate_stage = record.get("stage")
        if stage is None:
            if not isinstance(candidate_stage, str) or candidate_stage not in STAGE_FIELDS:
                raise IntakeValidationError("Unknown staged intake scenario.")
            stage = candidate_stage
            observed = {
                field: []
                for field in STAGE_FIELDS[stage]
                if FIELD_DEFINITIONS[field].kind is FieldKind.NUMERICAL
            }
        elif candidate_stage != stage:
            raise IntakeValidationError("Synthetic training records must use one stage.")

        # Validate each record independently before reading any values.
        review_synthetic_stage_input(
            record,
            unknown_category_policy=policy.value,
        )
        features = record["features"]
        for field in observed:
            value = features.get(field)
            if value is not None:
                observed[field].append(float(value))

    assert stage is not None  # records is non-empty and a valid first stage was checked.
    medians: list[tuple[str, float]] = []
    for field in STAGE_FIELDS[stage]:
        if field not in observed:
            continue
        if not observed[field]:
            raise IntakeValidationError(
                "A numeric field has no observed synthetic training value."
            )
        field_median = float(median(observed[field]))
        if not isfinite(field_median):
            raise IntakeValidationError("Training statistics must be finite.")
        medians.append((field, field_median))

    return FittedSyntheticPreprocessor(
        stage=stage,
        numeric_medians=tuple(medians),
        unknown_category_policy=policy,
    )
