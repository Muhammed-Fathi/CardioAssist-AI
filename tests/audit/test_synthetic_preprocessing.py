"""Synthetic-only preprocessing tests; no real records or CAD model fitting."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError

import pytest

from research.intake.synthetic_preprocessing import (
    MissingnessIndicator,
    UnknownCategoryPolicy,
    encode_categorical,
    fit_synthetic_preprocessor,
)
from research.intake.synthetic_stage_validator import (
    CATEGORY_ORDER,
    FIELD_DEFINITIONS,
    STAGE_FIELDS,
    UNIT_CONVENTIONS,
    FieldKind,
    IntakeValidationError,
    review_synthetic_stage_input,
)


# Small, deliberately artificial values are software-test sentinels only. They
# are not copied from a source dataset and are not clinical reference values.
_TOY_VALUES = {
    "age": 10,
    "sex": 0,
    "cp": 1,
    "trestbps": 20.0,
    "restecg": 0,
    "chol": 30.0,
    "fbs": 0,
    "thalach": 40.0,
    "exang": 0,
    "oldpeak": 0.0,
    "slope": 1,
}


def synthetic_record(stage: str = "resting_plus_labs") -> dict:
    features = {field: _TOY_VALUES[field] for field in STAGE_FIELDS[stage]}
    units = {
        field: UNIT_CONVENTIONS[field]
        for field in features
        if features[field] is not None and field in UNIT_CONVENTIONS
    }
    return {
        "synthetic": True,
        "stage": stage,
        "features": features,
        "units": units,
        "missing_reasons": {},
    }


def mark_missing(record: dict, field: str, reason: str = "not_measured") -> dict:
    record["features"][field] = None
    record["units"].pop(field, None)
    record["missing_reasons"][field] = reason
    return record


def vector_value(record, name: str) -> float:
    return record.as_feature_mapping()[name]


@pytest.mark.parametrize("stage", tuple(STAGE_FIELDS))
def test_each_stage_has_fixed_columns_and_accepts_valid_synthetic_fields(stage: str) -> None:
    source = synthetic_record(stage)
    before = deepcopy(source)
    fitted = fit_synthetic_preprocessor([source])
    output = fitted.transform(source)

    assert source == before
    assert output.stage == stage
    assert output.synthetic_only is True
    assert output.prediction_status == "NO_PREDICTION_GATE_PT_CLOSED"
    assert output.feature_names == fitted.feature_names
    assert len(output.values) == len(output.feature_names)
    assert output.missingness == tuple(
        # Every stage field is explicitly present in this fixture.
        MissingnessIndicator(field, False, None, False)
        for field in STAGE_FIELDS[stage]
    )
    assert vector_value(output, "sex__category_0") == 1.0
    assert vector_value(output, "cp__category_1") == 1.0
    assert vector_value(output, "age__missing") == 0.0


def test_field_definitions_and_category_order_are_explicit_and_stable() -> None:
    assert FIELD_DEFINITIONS["age"].kind is FieldKind.NUMERICAL
    assert FIELD_DEFINITIONS["trestbps"].unit == "mmHg"
    assert FIELD_DEFINITIONS["chol"].unit == "mg/dL"
    assert FIELD_DEFINITIONS["oldpeak"].unit is None  # Deliberately not asserted.
    assert FIELD_DEFINITIONS["oldpeak"].kind is FieldKind.NUMERICAL
    assert FIELD_DEFINITIONS["cp"].kind is FieldKind.CATEGORICAL
    assert CATEGORY_ORDER["sex"] == (0, 1)
    assert CATEGORY_ORDER["cp"] == (1, 2, 3, 4)
    assert CATEGORY_ORDER["restecg"] == (0, 1, 2)
    assert CATEGORY_ORDER["fbs"] == (0, 1)
    assert CATEGORY_ORDER["exang"] == (0, 1)
    assert CATEGORY_ORDER["slope"] == (1, 2, 3)

    first = synthetic_record()
    second = synthetic_record()
    first["features"]["cp"] = 1
    second["features"]["cp"] = 4
    # Training observations do not decide one-hot dimensions or column order.
    assert fit_synthetic_preprocessor([first]).feature_names == (
        fit_synthetic_preprocessor([second]).feature_names
    )
    assert tuple(
        name for name in fit_synthetic_preprocessor([first]).feature_names
        if name.startswith("cp__category_")
    ) == tuple(f"cp__category_{code}" for code in (1, 2, 3, 4))


def test_null_is_distinct_from_valid_categorical_and_numeric_zero() -> None:
    training = synthetic_record()
    fitted = fit_synthetic_preprocessor([training])
    source = synthetic_record()
    mark_missing(source, "chol", "not_measured")
    output = fitted.transform(source)

    assert vector_value(output, "chol") == 30.0  # Training median only.
    assert vector_value(output, "chol__missing") == 1.0
    assert vector_value(output, "chol__missing_reason__not_measured") == 1.0
    assert vector_value(output, "chol__missing_reason__unknown") == 0.0
    assert vector_value(output, "sex__category_0") == 1.0
    assert vector_value(output, "fbs__category_0") == 1.0
    assert vector_value(output, "restecg__category_0") == 1.0
    assert vector_value(output, "chol__missing") != vector_value(output, "fbs__missing")
    assert output.missingness[5].field == "chol"
    assert output.missingness[5].missing is True
    assert output.missingness[5].reason == "not_measured"


def test_omitted_optional_field_is_structural_missingness_with_explicit_reason() -> None:
    source = synthetic_record()
    del source["features"]["chol"]
    source["units"].pop("chol")
    source["missing_reasons"]["chol"] = "not_provided"
    fitted = fit_synthetic_preprocessor([synthetic_record()])
    output = fitted.transform(source)

    assert vector_value(output, "chol__missing") == 1.0
    assert vector_value(output, "chol__missing_reason__not_provided") == 1.0
    assert output.missingness[5].reason == "not_provided"

    invalid = synthetic_record()
    del invalid["features"]["chol"]
    invalid["units"].pop("chol")
    with pytest.raises(IntakeValidationError):
        fitted.transform(invalid)


def test_valid_zero_and_negative_oldpeak_are_preserved_without_clipping() -> None:
    fitted = fit_synthetic_preprocessor([synthetic_record("includes_exercise_tests")])
    zero = fitted.transform(synthetic_record("includes_exercise_tests"))
    negative_source = synthetic_record("includes_exercise_tests")
    negative_source["features"]["oldpeak"] = -2.5
    negative = fitted.transform(negative_source)

    assert vector_value(zero, "oldpeak") == 0.0
    assert vector_value(zero, "oldpeak__missing") == 0.0
    assert vector_value(negative, "oldpeak") == -2.5
    assert vector_value(negative, "oldpeak__missing") == 0.0
    assert negative_source["features"]["oldpeak"] == -2.5
    assert "oldpeak" not in negative_source["units"]


def test_cholesterol_and_blood_pressure_zero_are_rejected_as_measurements() -> None:
    fitted = fit_synthetic_preprocessor([synthetic_record()])
    for field in ("chol", "trestbps"):
        source = synthetic_record()
        source["features"][field] = 0
        with pytest.raises(IntakeValidationError):
            fitted.transform(source)


def test_unknown_category_can_fail_closed_or_use_a_separate_indicator() -> None:
    training = synthetic_record()
    fitted_default = fit_synthetic_preprocessor([training])
    source = synthetic_record()
    source["features"]["cp"] = 99

    with pytest.raises(IntakeValidationError):
        encode_categorical("cp", 99)
    with pytest.raises(IntakeValidationError):
        fitted_default.transform(source)

    encoded = encode_categorical(
        "cp", 99, unknown_category_policy=UnknownCategoryPolicy.INDICATOR,
    )
    assert encoded.category_order == (1, 2, 3, 4)
    assert encoded.one_hot == (0, 0, 0, 0)
    assert encoded.unknown_category is True

    fitted_indicator = fit_synthetic_preprocessor(
        [training], unknown_category_policy=UnknownCategoryPolicy.INDICATOR,
    )
    output = fitted_indicator.transform(source)
    assert [vector_value(output, f"cp__category_{code}") for code in (1, 2, 3, 4)] == [
        0.0, 0.0, 0.0, 0.0,
    ]
    assert vector_value(output, "cp__unknown_category") == 1.0
    assert vector_value(output, "cp__missing") == 0.0
    assert output.missingness[2].unknown_category is True
    # Unknown source values are not copied into the result or its field names.
    assert "99" not in repr(output)


@pytest.mark.parametrize("field,value", [
    ("age", float("nan")),
    ("trestbps", float("inf")),
    ("chol", float("-inf")),
    ("oldpeak", float("nan")),
    ("thalach", float("-inf")),
])
def test_nonfinite_numeric_values_are_rejected(field: str, value: float) -> None:
    fitted = fit_synthetic_preprocessor([synthetic_record("includes_exercise_tests")])
    source = synthetic_record("includes_exercise_tests")
    source["features"][field] = value
    with pytest.raises(IntakeValidationError):
        fitted.transform(source)


@pytest.mark.parametrize("field", ["age", "chol"])
@pytest.mark.parametrize("path", ["validator", "fit", "transform"])
def test_extreme_integer_is_rejected_safely_in_all_preprocessing_paths(
    field: str,
    path: str,
) -> None:
    # An invented software sentinel large enough to overflow int-to-float
    # conversion in math.isfinite; never a clinical value or patient record.
    oversized = 10**1000
    source = synthetic_record()
    source["features"][field] = oversized

    with pytest.raises(IntakeValidationError) as error:
        if path == "validator":
            review_synthetic_stage_input(source)
        elif path == "fit":
            fit_synthetic_preprocessor([source])
        else:
            fitted = fit_synthetic_preprocessor([synthetic_record()])
            fitted.transform(source)

    assert str(oversized) not in str(error.value)


def test_declared_units_are_exact_and_no_conversion_is_performed() -> None:
    fitted = fit_synthetic_preprocessor([synthetic_record()])
    source = synthetic_record()
    source["units"]["trestbps"] = "kPa"
    with pytest.raises(IntakeValidationError, match="Unit mismatch"):
        fitted.transform(source)

    # An unknown unit is not accepted for oldpeak; the source unit is unresolved.
    source = synthetic_record("includes_exercise_tests")
    source["units"]["oldpeak"] = "unitless"
    fitted_exercise = fit_synthetic_preprocessor([
        synthetic_record("includes_exercise_tests"),
    ])
    with pytest.raises(IntakeValidationError):
        fitted_exercise.transform(source)


@pytest.mark.parametrize("forbidden", [
    "ca", "Cath", "num", "LAD", "LCX", "RCA", "thal",
    "lmt", "ladprox", "laddist", "diag", "cxmain", "ramus", "om1",
    "om2", "rcaprox", "rcadist", "angiography", "stenosis_percent",
    "target", "outcome", "patient_id", "patient_ref", "mrn", "name",
    "site", "wearable_heart_rate", "heart_rate_bpm", "steps",
    "wearable_ecg", "monitoring_observation",
])
def test_leakage_identifiers_angiography_and_wearables_are_rejected(forbidden: str) -> None:
    source = synthetic_record("resting_assessment")
    source["features"][forbidden] = "SYNTHETIC_SENTINEL"
    with pytest.raises(IntakeValidationError) as error:
        fit_synthetic_preprocessor([source])
    assert "SYNTHETIC_SENTINEL" not in str(error.value)


def test_unexpected_top_level_context_and_non_synthetic_context_are_rejected() -> None:
    source = synthetic_record()
    source["label"] = 1
    with pytest.raises(IntakeValidationError):
        fit_synthetic_preprocessor([source])

    non_synthetic = synthetic_record()
    non_synthetic["synthetic"] = False
    with pytest.raises(IntakeValidationError):
        fit_synthetic_preprocessor([non_synthetic])

    fitted = fit_synthetic_preprocessor([synthetic_record()])
    with pytest.raises(IntakeValidationError):
        fitted.transform(non_synthetic)


def test_training_holdout_separation_uses_training_medians_only() -> None:
    train_low = synthetic_record()
    train_high = synthetic_record()
    train_high["features"].update({"age": 30, "trestbps": 40.0, "chol": 50.0})
    training = [train_low, train_high]
    training_before = deepcopy(training)

    fitted = fit_synthetic_preprocessor(training)
    expected_training_medians = (
        ("age", 20.0),
        ("trestbps", 30.0),
        ("chol", 40.0),
    )
    assert fitted.numeric_medians == expected_training_medians
    assert training == training_before

    holdout_a = synthetic_record()
    holdout_a["features"].update({"age": 900.0, "trestbps": 800.0})
    mark_missing(holdout_a, "chol", "not_available_at_time")
    holdout_b = synthetic_record()
    holdout_b["features"].update({"age": 1900.0, "trestbps": 1800.0})
    mark_missing(holdout_b, "chol", "not_available_at_time")
    holdout_before = (deepcopy(holdout_a), deepcopy(holdout_b))

    # The fitted state has no holdout argument and transform is read-only.
    medians_before_transform = fitted.numeric_medians
    output_a = fitted.transform(holdout_a)
    output_b = fitted.transform(holdout_b)
    assert fitted.numeric_medians == medians_before_transform == expected_training_medians
    assert vector_value(output_a, "chol") == 40.0
    assert vector_value(output_b, "chol") == 40.0
    assert output_a.values != output_b.values  # Their observed holdout values remain distinct.
    assert (holdout_a, holdout_b) == holdout_before


def test_training_requires_observed_synthetic_values_for_each_numeric_column() -> None:
    first = synthetic_record()
    second = synthetic_record()
    mark_missing(first, "chol", "not_measured")
    mark_missing(second, "chol", "unknown")
    with pytest.raises(IntakeValidationError, match="no observed synthetic training value"):
        fit_synthetic_preprocessor([first, second])


def test_preprocessing_is_deterministic_immutable_and_identifier_free() -> None:
    training = synthetic_record("includes_exercise_tests")
    holdout = synthetic_record("includes_exercise_tests")
    training_before = deepcopy(training)
    holdout_before = deepcopy(holdout)
    fitted = fit_synthetic_preprocessor([training])

    first = fitted.transform(holdout)
    second = fitted.transform(holdout)
    assert first == second
    assert training == training_before
    assert holdout == holdout_before
    assert first.feature_names == fitted.feature_names
    assert not any(
        token in name.lower()
        for name in first.feature_names
        for token in ("patient", "identifier", "mrn", "target", "outcome", "site")
    )
    with pytest.raises(FrozenInstanceError):
        first.stage = "history_only"
    with pytest.raises(TypeError):
        first.as_feature_mapping()["age"] = 999.0
