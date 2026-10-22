"""Deterministic synthetic-only safety tests; no patient records or model fit."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict

import pytest

from research.intake.synthetic_stage_validator import (
    IntakeValidationError,
    STAGE_FIELDS,
    review_synthetic_stage_input,
)


def fixture(stage: str = "resting_assessment") -> dict:
    all_features = {
        "age": 54,
        "sex": 0,
        "cp": 2,
        "trestbps": 124.0,
        "restecg": 0,
        "chol": 202.0,
        "fbs": 0,
        "thalach": 138.0,
        "exang": 0,
        "oldpeak": -0.4,
        "slope": 2,
    }
    all_units = {
        "age": "years",
        "trestbps": "mmHg",
        "chol": "mg/dL",
        "thalach": "bpm",
    }
    return {
        "synthetic": True,
        "stage": stage,
        "features": {k: all_features[k] for k in STAGE_FIELDS[stage]},
        "units": {k: u for k, u in all_units.items() if k in STAGE_FIELDS[stage]},
        "missing_reasons": {},
    }


@pytest.mark.parametrize("stage", tuple(STAGE_FIELDS))
def test_stage_complete_and_return_is_metadata_only(stage: str) -> None:
    source = fixture(stage)
    original = deepcopy(source)
    review = review_synthetic_stage_input(source)
    assert source == original
    assert review.stage_complete
    assert review.synthetic_only
    assert review.prediction_status == "NO_PREDICTION_GATE_PT_CLOSED"
    assert review.present_fields == STAGE_FIELDS[stage]
    assert review.missing_fields_with_reason == ()
    output = repr(asdict(review))
    assert "124.0" not in output
    assert "202.0" not in output
    assert "138.0" not in output


def test_null_is_explicit_and_not_equal_zero() -> None:
    source = fixture("resting_plus_labs")
    source["features"]["chol"] = None
    source["units"].pop("chol")
    source["missing_reasons"]["chol"] = "not_measured"
    review = review_synthetic_stage_input(source)
    assert review.missing_fields_with_reason == (("chol", "not_measured"),)
    assert not review.stage_complete
    assert "fbs" in review.present_fields
    assert source["features"]["fbs"] == 0


def test_negative_and_zero_oldpeak_are_not_clipped_or_flagged_as_missing() -> None:
    negative = fixture("includes_exercise_tests")
    review = review_synthetic_stage_input(negative)
    assert review.stage_complete
    assert negative["features"]["oldpeak"] == -0.4

    zero = fixture("includes_exercise_tests")
    zero["features"]["oldpeak"] = 0.0
    zero_review = review_synthetic_stage_input(zero)
    assert zero_review.stage_complete
    assert zero["features"]["oldpeak"] == 0.0
    assert not zero_review.missing_fields_with_reason


@pytest.mark.parametrize(
    "forbidden",
    [
        "ca", "thal", "num", "target", "outcome", "Cath", "LAD", "LCX", "RCA",
        "lmt", "ladprox", "laddist", "diag", "cxmain", "ramus", "om1",
        "om2", "rcaprox", "rcadist", "angiography", "stenosis_percent",
        "patient_id", "patient_ref", "mrn", "name", "site",
        "wearable_heart_rate", "heart_rate_bpm", "steps", "wearable_ecg",
        "monitoring_observation",
    ],
)
def test_leakage_identifier_and_wearable_fields_fail_closed(forbidden: str) -> None:
    source = fixture()
    source["features"][forbidden] = "synthetic-only"
    with pytest.raises(IntakeValidationError) as error:
        review_synthetic_stage_input(source)
    assert "synthetic-only" not in str(error.value)


def test_later_stage_inputs_fail_closed() -> None:
    source = fixture("history_only")
    source["features"]["chol"] = 210
    source["units"]["chol"] = "mg/dL"
    with pytest.raises(IntakeValidationError):
        review_synthetic_stage_input(source)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("age", 0), ("age", -12), ("age", float("nan")),
        ("trestbps", 0), ("trestbps", float("inf")),
        ("sex", 2), ("sex", True), ("cp", 0),
        ("restecg", -1), ("restecg", 9),
    ],
)
def test_invalid_source_codes_or_physically_invalid_measured_values(field: str, value: object) -> None:
    source = fixture("resting_assessment")
    source["features"][field] = value
    with pytest.raises(IntakeValidationError):
        review_synthetic_stage_input(source)


def test_cholesterol_zero_cannot_masquerade_as_measured_lab() -> None:
    source = fixture("resting_plus_labs")
    source["features"]["chol"] = 0
    with pytest.raises(IntakeValidationError):
        review_synthetic_stage_input(source)


@pytest.mark.parametrize("bad_unit", ["kPa", "mmol/L", "", None])
def test_no_silent_unit_conversion(bad_unit: object) -> None:
    source = fixture("resting_plus_labs")
    source["units"]["chol"] = bad_unit
    with pytest.raises(IntakeValidationError):
        review_synthetic_stage_input(source)


def test_missing_value_requires_reason_and_absent_unit() -> None:
    source = fixture("resting_plus_labs")
    source["features"]["chol"] = None
    # A null without an explicit missing reason and with stale units fails.
    with pytest.raises(IntakeValidationError):
        review_synthetic_stage_input(source)
    source["missing_reasons"]["chol"] = "unknown"
    with pytest.raises(IntakeValidationError):
        review_synthetic_stage_input(source)
    source["units"].pop("chol")
    assert not review_synthetic_stage_input(source).stage_complete


def test_omitted_optional_measurement_has_distinct_not_provided_reason() -> None:
    source = fixture("resting_plus_labs")
    del source["features"]["chol"]
    source["units"].pop("chol")
    with pytest.raises(IntakeValidationError):
        review_synthetic_stage_input(source)
    source["missing_reasons"]["chol"] = "not_provided"
    review = review_synthetic_stage_input(source)
    assert review.missing_fields_with_reason == (("chol", "not_provided"),)
    assert not review.stage_complete


@pytest.mark.parametrize("reason", ["", "zero_means_missing", "not_requested", None])
def test_no_unapproved_missing_reason(reason: object) -> None:
    source = fixture("resting_plus_labs")
    source["features"]["chol"] = None
    source["units"].pop("chol")
    source["missing_reasons"]["chol"] = reason
    with pytest.raises(IntakeValidationError):
        review_synthetic_stage_input(source)


@pytest.mark.parametrize("tag", [False, None, "True", 1])
def test_never_accept_non_explicit_synthetic_tag(tag: object) -> None:
    source = fixture()
    source["synthetic"] = tag
    with pytest.raises(IntakeValidationError):
        review_synthetic_stage_input(source)


def test_no_accidental_top_level_phi_or_target_fields() -> None:
    source = fixture()
    source["real_patient_record"] = "unsafe"
    with pytest.raises(IntakeValidationError):
        review_synthetic_stage_input(source)


def test_mandatory_history_not_imputed() -> None:
    source = fixture()
    del source["features"]["cp"]
    with pytest.raises(IntakeValidationError):
        review_synthetic_stage_input(source)
    source = fixture()
    source["features"]["age"] = None
    source["units"].pop("age")
    source["missing_reasons"]["age"] = "unknown"
    with pytest.raises(IntakeValidationError):
        review_synthetic_stage_input(source)
