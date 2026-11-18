"""AI-9.1 negative and reproducibility tests. Synthetic fixtures ONLY."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from ai.ai9_paired_synthetic import (
    CLINICAL_PANEL, LAB_PANEL, _align_generated_rows,
    _compare_generated_rows, _fabricate_paired_cohort, run_ai9_synthetic_comparison,
)
from ai.errors import ClinicalInputValidationError
from ai.panels import get_panel_contract

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run_ai9_synthetic_comparison.py"


@pytest.fixture(scope="module")
def report() -> dict:
    return run_ai9_synthetic_comparison(n_rows=120, seed=20261118, bootstrap_resamples=64)


@pytest.fixture
def pairs() -> tuple[list[dict], list[dict]]:
    return _fabricate_paired_cohort(n_rows=96, seed=20261118)


def test_paired_synthetic_completion_has_no_clinical_or_serving_claim(report: dict) -> None:
    assert report["status"] == "SYNTHETIC_INCREMENTAL_VALUE_EXERCISE_COMPLETE"
    assert report["evidence_class"] == "SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE"
    assert report["real_data_execution_authorized"] is False
    assert report["clinical_use_authorized"] is False
    assert report["labs_route_activated"] is False
    assert report["feasibility"]["sample_size_adequacy_for_real_study"] == "NOT_ESTABLISHED"
    assert report["cohort"]["n_matched"] == 120
    assert report["cohort"]["n_positive"] + report["cohort"]["n_negative"] == 120
    assert report["comparison_plan"]["same_outer_splits"] is True
    assert report["comparison_plan"]["model_family_fixed_both_arms"] == "l2_logistic_regression"
    assert len(report["outer_fold_lineage"]) == 3
    assert set(report["metrics"]) == {"clinical_only", "clinical_plus_labs"}
    assert set(report["paired_deltas_labs_minus_clinical"]) == {
        "roc_auc", "brier_score", "expected_calibration_error_10bin_descriptive_only",
    }
    payload = {k: v for k, v in report.items() if k != "sha256"}
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                   allow_nan=False).encode("utf-8")
    ).hexdigest()
    assert digest == report["sha256"]
    assert "patient_records" not in json.dumps(report)
    assert "C:\\Users\\" not in json.dumps(report)


def test_both_arms_share_folds_and_calibration_is_outer_train_only(report: dict) -> None:
    n_test = 0
    for f in report["outer_fold_lineage"]:
        c, l = f["clinical"], f["clinical_plus_labs"]
        assert c["fold"] == l["fold"] == f["fold"]
        assert c["n_train"] == l["n_train"]
        assert c["n_test"] == l["n_test"]
        assert c["n_preprocessor_training_rows"] == c["n_train"]
        assert l["n_preprocessor_training_rows"] == l["n_train"]
        assert c["n_calibration_training_rows"] == c["n_train"]
        assert l["n_calibration_training_rows"] == l["n_train"]
        assert c["n_encoded_features"] <= l["n_encoded_features"]
        assert c["calibrator_fit_scope"] == l["calibrator_fit_scope"] == "INNER_CV_FOLD_CONTAINED"
        assert c["n_train"] + c["n_test"] == 120
        n_test += c["n_test"]
    assert n_test == 120


def test_paired_bootstrap_has_conditional_not_clinical_interpretation(report: dict) -> None:
    u = report["paired_uncertainty"]
    assert "CONDITIONAL_ON_FITTED_OUTER_FOLD_PREDICTIONS" in u["type"]
    assert u["n_resamples"] == 64
    assert len(u["delta_labs_minus_clinical_roc_auc_95_interval"]) == 2
    assert len(u["delta_labs_minus_clinical_brier_95_interval"]) == 2
    assert "does not refit" in u["uncertainty_limitations"].lower()
    for m in report["metrics"].values():
        assert 0 <= m["roc_auc"] <= 1
        assert 0 <= m["brier_score"] <= 1
    assert not report.get("clinical_improvement_confirmed", False)


def test_repeat_synthetic_experiment_is_deterministic(report: dict) -> None:
    again = run_ai9_synthetic_comparison(n_rows=120, seed=20261118, bootstrap_resamples=64)
    assert json.dumps(again, sort_keys=True, allow_nan=False) == json.dumps(report, sort_keys=True, allow_nan=False)


def test_generated_lab_missingness_uses_same_denominator(report: dict) -> None:
    missing = report["cohort"]["lab_missingness"]
    assert set(missing) == {"chol", "fbs"}
    assert all(v["denominator"] == 120 for v in missing.values())
    assert all(v["missing"] > 0 for v in missing.values())
    assert all(v["fraction"] == pytest.approx(v["missing"] / 120) for v in missing.values())


def test_row_order_does_not_create_false_mismatch(pairs) -> None:
    c, l = pairs
    ids, y, C, L, _ = _align_generated_rows(c, l)
    ids2, y2, C2, L2, _ = _align_generated_rows(list(reversed(c)), list(reversed(l)))
    assert ids == ids2
    assert np.array_equal(y, y2)
    assert np.array_equal(C, C2, equal_nan=True)
    assert np.array_equal(L, L2, equal_nan=True)
    assert ids[0] == "AI9SYN_00000"
    assert get_panel_contract(CLINICAL_PANEL).feature_names == get_panel_contract(LAB_PANEL).feature_names[:C.shape[1]]


@pytest.mark.parametrize("mutation,expected", [
    ("missing_patient", "unmatched_cohort_count"),
    ("duplicate_patient", "invalid_or_duplicate_synthetic_identity"),
    ("wrong_patient_id", "unmatched_synthetic_participants"),
    ("target_label_mismatch", "mismatched_paired_target"),
    ("different_target", "panel_or_target_binding_mismatch"),
    ("wrong_panel_hash", "panel_or_target_binding_mismatch"),
    ("wrong_panel_version", "panel_or_target_binding_mismatch"),
    ("not_synthetic", "invalid_synthetic_source_or_features"),
    ("bad_context", "invalid_synthetic_source_or_features"),
    ("unknown_feature", "invalid_synthetic_source_or_features"),
    ("shared_feature_mismatch", "mismatched_shared_clinical_fields"),
])
def test_identity_target_contract_and_leakage_mutations_fail_closed(pairs, mutation, expected) -> None:
    c, l = copy.deepcopy(pairs)
    if mutation == "missing_patient":
        l.pop()
    elif mutation == "duplicate_patient":
        l[1]["id"] = l[0]["id"]
    elif mutation == "wrong_patient_id":
        l[0]["id"] = "AI9SYN_99999"
    elif mutation == "target_label_mismatch":
        l[0]["label"] = 1 - l[0]["label"]
    elif mutation == "different_target":
        l[0]["target_id"] = "target-other"
    elif mutation == "wrong_panel_hash":
        l[0]["panel_hash"] = "0" * 64
    elif mutation == "wrong_panel_version":
        l[0]["panel_version"] = "2.0.0"
    elif mutation == "not_synthetic":
        l[0]["record"]["synthetic"] = False
    elif mutation == "bad_context":
        l[0]["record"]["context"]["source"] = "patient_records"
    elif mutation == "unknown_feature":
        l[0]["record"]["features"]["patient_id"] = 42
    elif mutation == "shared_feature_mismatch":
        l[0]["record"]["features"]["age"] += 1.0
    with pytest.raises(ValueError, match=expected):
        _align_generated_rows(c, l)


def test_missingness_and_units_are_validated_against_registered_panel(pairs) -> None:
    c, l = copy.deepcopy(pairs)
    # Pick a measured chol entry rather than relying on a specific row seed.
    measured = next(r for r in l if r["record"]["features"]["chol"] is not None)
    measured["record"]["units"]["chol"] = "not-the-registered-unit"
    with pytest.raises(ClinicalInputValidationError, match="Unit token mismatch"):
        _align_generated_rows(c, l)


def test_missing_lab_measurement_requires_explicit_reason(pairs) -> None:
    c, l = copy.deepcopy(pairs)
    row = next(r for r in l if r["record"]["features"]["chol"] is None)
    del row["record"]["missing_reasons"]["chol"]
    with pytest.raises(ClinicalInputValidationError, match="missing reason"):
        _align_generated_rows(c, l)


@pytest.mark.parametrize("n,seed", [(0, 7), (95, 7), (385, 7), (120, -1), (120, True)])
def test_generator_refuses_unbounded_or_invalid_inputs(n, seed) -> None:
    with pytest.raises(ValueError):
        _fabricate_paired_cohort(n_rows=n, seed=seed)


def test_cli_unknown_arguments_and_repo_output_fail_without_training() -> None:
    cmd = [sys.executable, "-W", "error", str(SCRIPT)]
    bogus = subprocess.run([*cmd, "--data", "private.csv"], cwd=ROOT, capture_output=True)
    assert bogus.returncode == 2
    assert b"invalid_arguments" in bogus.stderr
    path = ROOT / "_ai9_should_never_write.json"
    assert not path.exists()
    bad = subprocess.run([*cmd, "--output", str(path)], cwd=ROOT, capture_output=True)
    assert bad.returncode == 2
    assert not path.exists()


def test_cli_exclusive_new_external_json_and_deterministic_content(tmp_path: Path) -> None:
    cmd = [sys.executable, "-W", "error", str(SCRIPT)]
    target = tmp_path / "synthetic-paired.json"
    good = subprocess.run([*cmd, "--output", str(target)], cwd=ROOT, capture_output=True)
    assert good.returncode == 0, good.stderr.decode(errors="replace")
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["status"] == "SYNTHETIC_INCREMENTAL_VALUE_EXERCISE_COMPLETE"
    assert payload["cohort"]["n_matched"] == 120
    previous = target.read_bytes()
    again = subprocess.run([*cmd, "--output", str(target)], cwd=ROOT, capture_output=True)
    assert again.returncode == 2
    assert target.read_bytes() == previous
