"""AI-9.1 schema checks, independent of ML runtime and patient data.

The contract-only CI installs only JSON Schema/test tools; this static fabricated
fixture is intentionally not a training run. Execution and real report content
are separately tested under tests/experiments and native Windows acceptance.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs/research/ai9_1/synthetic-paired-comparison.v1.schema.json"
)
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA)


def _fake_report() -> dict:
    """Invented schema fixture only: numbers are NOT results from models."""
    h = "a" * 64
    panel = {"id": "test_only", "version": "1.0.0", "sha256": h}
    arm = {
        "fold": 1, "n_train": 80, "n_test": 40,
        "n_preprocessor_training_rows": 80,
        "n_calibration_training_rows": 80,
        "n_raw_features": 5, "n_encoded_features": 7,
        "estimated_fitted_coefficients_and_calibration_parameters": 10,
        "hyperparameter_C_selected_on_inner_train_only": 0.1,
        "calibrator_fit_scope": "INNER_CV_FOLD_CONTAINED",
    }
    metric = {
        "roc_auc": 0.5, "average_precision": 0.5, "brier_score": 0.25,
        "expected_calibration_error_10bin": 0.1, "cox_diagnostics": {},
    }
    folds = []
    for idx in range(1, 4):
        c = copy.deepcopy(arm)
        c["fold"] = idx
        lab = copy.deepcopy(c)
        lab["n_raw_features"] = 7
        lab["n_encoded_features"] = 11
        lab["estimated_fitted_coefficients_and_calibration_parameters"] = 14
        folds.append({
            "fold": idx, "matched_outer_test_identity_sha256": h,
            "clinical": c, "clinical_plus_labs": lab,
        })
    return {
        "schema_version": "cardioassist.ai.synthetic_paired_incremental_value/v1",
        "status": "SYNTHETIC_INCREMENTAL_VALUE_EXERCISE_COMPLETE",
        "evidence_class": "SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE",
        "source": "IN_PROCESS_FABRICATED_DA_A2_ONLY",
        "target_id": "t1.uci45.angiographic_cad_gt50.v1",
        "real_data_execution_authorized": False,
        "clinical_use_authorized": False,
        "labs_route_activated": False,
        "cohort": {
            "n_matched": 120, "n_positive": 60, "n_negative": 60,
            "matched_identity_checksum": h,
            "lab_missingness": {
                "chol": {"missing": 10, "denominator": 120, "fraction": 10 / 120},
                "fbs": {"missing": 20, "denominator": 120, "fraction": 20 / 120},
            },
        },
        "comparison_plan": {
            "same_source_and_target": True, "same_patient_ids": True,
            "same_outer_splits": True, "outer_folds": 3, "inner_folds": 3,
            "seed": 7, "model_family_fixed_both_arms": "l2_logistic_regression",
            "hyperparameters_selected_on_inner_training_folds_only": True,
            "preprocessing_and_calibration_fitted_inside_outer_train_only": True,
            "clinical_panel": copy.deepcopy(panel),
            "labs_panel": copy.deepcopy(panel),
        },
        "outer_fold_lineage": folds,
        "metrics": {
            "clinical_only": copy.deepcopy(metric),
            "clinical_plus_labs": copy.deepcopy(metric),
        },
        "paired_deltas_labs_minus_clinical": {
            "roc_auc": 0.0, "brier_score": 0.0,
            "expected_calibration_error_10bin_descriptive_only": 0.0,
        },
        "paired_uncertainty": {
            "type": "PAIRED_STRATIFIED_PERCENTILE_BOOTSTRAP_CONDITIONAL_ON_FITTED_OUTER_FOLD_PREDICTIONS",
            "n_resamples": 64, "interval": 0.95,
            "uncertainty_limitations": "Synthetic only, no model refits per resample.",
            "delta_labs_minus_clinical_roc_auc_95_interval": [-0.1, 0.1],
            "delta_labs_minus_clinical_brier_95_interval": [-0.1, 0.1],
        },
        "feasibility": {
            "status": "SYNTHETIC_FEASIBILITY_ONLY",
            "measured_clinical_lab_timing_or_source_semantics_verified": False,
            "sample_size_adequacy_for_real_study": "NOT_ESTABLISHED",
            "model_complexity_note": "Fabricated schema fixture, no model fitted.",
        },
        "interpretation": "Static schema fixture, NOT real or clinical data.",
        "sha256": h,
    }


@pytest.fixture(scope="module")
def output() -> dict:
    return _fake_report()


def test_schema_draft202012_accepts_static_synthetic_contract_fixture(output) -> None:
    Draft202012Validator.check_schema(SCHEMA)
    VALIDATOR.validate(output)


@pytest.mark.parametrize("path,value", [
    (("schema_version",), "cardioassist.ai.synthetic_paired_incremental_value/v2"),
    (("status",), "CLINICALLY_VALIDATED"),
    (("evidence_class",), "REAL_PATIENT_EVIDENCE"),
    (("source",), "real_cohort"),
    (("real_data_execution_authorized",), True),
    (("clinical_use_authorized",), True),
    (("labs_route_activated",), True),
    (("cohort", "n_matched"), -1),
    (("comparison_plan", "same_patient_ids"), False),
    (("comparison_plan", "same_outer_splits"), False),
    (("comparison_plan", "preprocessing_and_calibration_fitted_inside_outer_train_only"), False),
    (("comparison_plan", "model_family_fixed_both_arms"), "unknown_model"),
    (("feasibility", "status"), "APPROVED_CLINICAL_STUDY"),
    (("feasibility", "sample_size_adequacy_for_real_study"), "PROVEN"),
    (("outer_fold_lineage", 0, "clinical", "calibrator_fit_scope"), "FITTED_ALL_ROWS"),
    (("metrics", "clinical_only", "roc_auc"), 4.0),
])
def test_schema_rejects_synthetic_authorization_promotion(output, path, value) -> None:
    tampered = copy.deepcopy(output)
    parent = tampered
    for key in path[:-1]:
        parent = parent[key]
    parent[path[-1]] = value
    assert not VALIDATOR.is_valid(tampered)


def test_schema_refuses_unknown_fields_patient_records_and_missing_required(output) -> None:
    extra = copy.deepcopy(output)
    extra["patient_records"] = [{"raw": "not_allowed"}]
    assert not VALIDATOR.is_valid(extra)
    nested = copy.deepcopy(output)
    nested["outer_fold_lineage"][0]["clinical"]["private_bundle_path"] = "/secret"
    assert not VALIDATOR.is_valid(nested)
    absent = copy.deepcopy(output)
    del absent["paired_uncertainty"]["uncertainty_limitations"]
    assert not VALIDATOR.is_valid(absent)
