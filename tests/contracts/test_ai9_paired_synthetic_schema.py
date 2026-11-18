"""AI-9.1 versioned report contract: synthetic-only, no clinical promotion."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from ai.ai9_paired_synthetic import run_ai9_synthetic_comparison

SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs/research/ai9_1/synthetic-paired-comparison.v1.schema.json"
)
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA)


@pytest.fixture(scope="module")
def output() -> dict:
    return run_ai9_synthetic_comparison()


def test_schema_draft202012_accepts_real_generated_synthetic_report(output) -> None:
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
