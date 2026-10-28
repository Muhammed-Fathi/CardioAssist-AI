"""Tests for the observable AI-8 UCI-412 synthetic research demo.

The demo is a thin orchestration layer over :mod:`ai.uci412_research`; these
tests prove the documented ``python -m ai uci412-demo`` command runs end to
end, stays synthetic/RESEARCH_ONLY, reports SHAP/LIME truthfully, rejects an
invalid input through the real validator, and is reproducible. No real data,
patient background, secret or tracked artifact is produced.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
import subprocess
import sys

import pytest

from ai import ensure_private_directory
from ai.panels import DA_A1_BASIC_CLINICAL_PANEL
from ai.uci412_demo import (
    DEMO_COMMAND_SMOKE,
    render_uci412_demo_text,
    run_uci412_research_demo,
)
from ai.uci412_research import (
    SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE,
    UCI412_PANEL_ID,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_PANEL_SHA = (
    "efd51491c06d808ac3e02a62c45302dd9a57966b6f619b0c604df980ba71a208"
)
EXPECTED_TARGET_ID = "t1.uci412.angiographic_cad_ge50.v1"


@pytest.fixture(scope="module")
def smoke_payload() -> dict:
    return run_uci412_research_demo(budget="smoke")


def _stage(payload: dict, name: str) -> dict:
    for stage in payload["stage_results"]:
        if stage["stage"] == name:
            return stage["detail"]
    raise AssertionError(f"stage {name} not found in demo payload")


# --------------------------------------------------------------------------- #
# Overall contract and JSON cleanliness                                       #
# --------------------------------------------------------------------------- #


def test_smoke_demo_passes_every_stage_and_is_json_clean(smoke_payload):
    assert smoke_payload["status"] == "PASSED"
    assert smoke_payload["budget"] == "smoke"
    assert smoke_payload["summary"]["stages_failed"] == 0
    assert (
        smoke_payload["summary"]["stages_succeeded"]
        == smoke_payload["summary"]["stages_total"]
        == 12
    )
    # Every value must be finite and the full payload JSON serializable.
    json.dumps(smoke_payload, allow_nan=False, sort_keys=True)


def test_demo_command_strings_match_the_documented_cli(smoke_payload):
    assert smoke_payload["command"] == DEMO_COMMAND_SMOKE
    assert smoke_payload["reproduction"]["smoke_command"] == "python -m ai uci412-demo"
    assert (
        smoke_payload["reproduction"]["full_command"]
        == "python -m ai uci412-demo --budget full"
    )


def test_demo_uses_correct_route_panel_and_registered_hash(smoke_payload):
    assert smoke_payload["route_id"] == UCI412_PANEL_ID
    assert smoke_payload["panel_id"] == "da_a1_basic_clinical_v1"
    binding = _stage(smoke_payload, "2_route_and_panel_binding")
    assert binding["panel_contract_sha256"] == EXPECTED_PANEL_SHA
    assert binding["panel_contract_sha256"] == DA_A1_BASIC_CLINICAL_PANEL.contract_sha256
    assert binding["feature_count"] == 16
    assert binding["ordered_feature_names"] == list(
        DA_A1_BASIC_CLINICAL_PANEL.feature_names
    )


# --------------------------------------------------------------------------- #
# Synthetic / research-only boundaries                                        #
# --------------------------------------------------------------------------- #


def test_demo_is_synthetic_and_cannot_activate_serving(smoke_payload):
    assert smoke_payload["evidence_marker"] == SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE
    provenance = _stage(smoke_payload, "7_prediction_provenance_and_target")
    assert provenance["serving_eligibility"] == "RESEARCH_ONLY"
    assert provenance["approved_for_serving"] is False
    assert provenance["clinical_use_authorized"] is False
    bundle = _stage(smoke_payload, "10_bundle_verification")
    assert bundle["serving_eligibility"] == "RESEARCH_ONLY"
    assert bundle["approved_for_serving"] is False
    assert bundle["clinical_use_authorized"] is False


def test_demo_bundle_is_authenticated_and_contract_bound(smoke_payload):
    bundle = _stage(smoke_payload, "10_bundle_verification")
    assert bundle["producer_authenticated"] is True
    assert bundle["safe_for_pickle_deserialization"] is True
    assert bundle["manifest_pooled_cohorts"] is False
    assert bundle["verified_file_count"] >= 5
    assert bundle["attestation_scheme"] == "hmac-sha256-local-producer-v1"
    provenance = _stage(smoke_payload, "7_prediction_provenance_and_target")
    assert provenance["target_id"] == EXPECTED_TARGET_ID
    assert provenance["threshold_boundary"] == "GREATER_THAN_OR_EQUAL_50_PERCENT"


# --------------------------------------------------------------------------- #
# Scores, SHAP and LIME are reported on their true scales                     #
# --------------------------------------------------------------------------- #


def test_raw_and_calibrated_scores_are_distinct_and_bounded(smoke_payload):
    raw = _stage(smoke_payload, "5_raw_model_score")
    cal = _stage(smoke_payload, "6_calibrated_research_score")
    assert 0.0 < raw["raw_model_score"] < 1.0
    assert 0.0 < cal["calibrated_research_score"] < 1.0
    assert isinstance(cal["calibrated_log_odds"], float)
    assert (
        cal["score_interpretation"]
        == "RESEARCH_ONLY_NOT_INDIVIDUAL_CLINICAL_RISK"
    )
    assert cal["threshold_clinically_approved"] is False


def test_shap_scale_and_additivity_are_truthful(smoke_payload):
    shap = _stage(smoke_payload, "8_shap_explanation")
    assert shap["sum_check_passed"] is True
    assert shap["attribution_count"] == 16
    assert shap["max_abs_discrepancy"] < 1e-9
    # TreeSHAP explains the raw model score/probability, never a calibrated
    # probability decomposition; the flags must say so.
    assert shap["explained_quantity"] == "raw_model_score"
    assert shap["scale"] == "raw_model_probability"
    assert shap["additive_on_calibrated_probability"] is False


def test_lime_quality_is_reported_with_real_fidelity_numbers(smoke_payload):
    lime = _stage(smoke_payload, "9_lime_explanation")
    assert lime["stability_assessed"] is True
    assert isinstance(lime["quality_status"], str) and lime["quality_status"]
    assert isinstance(lime["is_reliable_for_interpretation"], bool)
    assert lime["local_fidelity_abs_error"] >= 0.0
    if lime["weighted_r2"] is not None:
        assert 0.0 <= lime["weighted_r2"] <= 1.0
    if lime["holdout_weighted_r2"] is not None:
        assert 0.0 <= lime["holdout_weighted_r2"] <= 1.0


# --------------------------------------------------------------------------- #
# Genuine invalid-input rejection and held-out labelling                      #
# --------------------------------------------------------------------------- #


def test_invalid_input_demo_is_genuinely_rejected_by_validator(smoke_payload):
    invalid = smoke_payload["invalid_input_demo"]
    assert invalid["rejected"] is True
    assert invalid["error_code"] == "uci412_synthetic_context_rejected"
    assert "unsupported_input_source" in invalid["error_message"]
    assert invalid["mutation"].startswith("removed context.source")
    # The rejection must never be confused with a model result.
    assert "cad_probability" not in invalid


def test_held_out_evidence_is_not_marked_external_clinical_validation(smoke_payload):
    held = _stage(smoke_payload, "12_held_out_synthetic_evidence")
    assert held["evidence_marker"] == SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE
    assert held["not_external_clinical_validation"] is True
    assert 0.0 <= held["roc_auc"] <= 1.0
    assert held["evaluation_scope"].endswith("UCI412_HELD_OUT")


def test_intake_contract_stage_preserves_no_result_guarantee(smoke_payload):
    contract = _stage(smoke_payload, "3_feature_contract_validation")
    assert contract["intake_review_status"] == "ACCEPTED_SYNTHETIC_FIXTURE_CONTRACT_ONLY"
    assert contract["intake_result_state"] == "NO_RESULT_NO_CAD_PROBABILITY_COMPUTED"
    assert contract["cad_probability_computed"] is False
    # Smoke profile holds out 60 synthetic rows across the 16-feature panel.
    assert contract["panel_validation_matrix_shape"] == [60, 16]


# --------------------------------------------------------------------------- #
# Reproducibility, privacy and retained artifacts                             #
# --------------------------------------------------------------------------- #


def test_demo_is_reproducible_across_separate_runs():
    first = run_uci412_research_demo(budget="smoke")
    second = run_uci412_research_demo(budget="smoke")
    assert first["report_deterministic_sha256"] == second["report_deterministic_sha256"]


def test_payload_contains_no_local_paths_or_secret_material(smoke_payload):
    serialized = json.dumps(smoke_payload)
    for banned in ("/home/", "\\\\", "trusted_bundles/", "private_keys/", ".key", "Traceback"):
        assert banned not in serialized


def test_retained_work_dir_keeps_artifacts_but_payload_stays_path_free(tmp_path):
    work_dir = ensure_private_directory(tmp_path / "ai8_demo_work")
    payload = run_uci412_research_demo(budget="smoke", work_dir=work_dir)
    assert payload["reproduction"]["work_artifacts_retained"] is True
    bundle_root = work_dir / "trusted_bundles"
    assert bundle_root.exists()
    model_files = list(bundle_root.rglob("model.joblib"))
    assert model_files, "a packaged model artifact should be retained"
    assert str(work_dir) not in json.dumps(payload)


def test_full_budget_demo_runs_and_is_distinguished_from_smoke(tmp_path):
    work_dir = ensure_private_directory(tmp_path / "ai8_demo_full")
    payload = run_uci412_research_demo(budget="full", work_dir=work_dir)
    assert payload["status"] == "PASSED"
    assert payload["budget"] == "full"
    assert payload["summary"]["stages_succeeded"] == 12
    cohort = _stage(payload, "1_synthetic_cohort_generation")
    # Full default budget is larger than the smoke profile.
    assert cohort["development_n"] == 240
    assert cohort["held_out_test_n"] == 120


# --------------------------------------------------------------------------- #
# Text rendering and A3/frozen-runtime boundary                               #
# --------------------------------------------------------------------------- #


def test_text_rendering_contains_required_markers(smoke_payload):
    text = render_uci412_demo_text(smoke_payload)
    assert SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE in text
    assert "RESEARCH_ONLY_NOT_INDIVIDUAL_CLINICAL_RISK" in text
    assert "12/12 stages succeeded" in text
    assert "uci412_synthetic_context_rejected" in text


def test_demo_module_does_not_touch_frozen_a3_or_serving_runtime():
    demo_source = (REPO_ROOT / "ai" / "uci412_demo.py").read_text(encoding="utf-8")
    tree = ast.parse(demo_source)
    imported_roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])
    # The demo must not reach into the frozen Cleveland A3 registry or the
    # real-data execution/serving layer.
    assert "backend" not in imported_roots
    assert not imported_roots & {"shap", "lime", "joblib"}
    for banned in ("diagnostic_scope", "ai.execution", "approved_for_serving=True"):
        assert banned not in demo_source


# --------------------------------------------------------------------------- #
# Actual CLI entry point through a subprocess                                  #
# --------------------------------------------------------------------------- #


def test_uci412_demo_cli_subprocess_json_and_text():
    run = subprocess.run(
        [sys.executable, "-m", "ai", "uci412-demo", "--format", "json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert run.returncode == 0, run.stderr
    payload = json.loads(run.stdout)
    assert payload["status"] == "PASSED"
    assert payload["panel_id"] == UCI412_PANEL_ID
    assert "Traceback" not in run.stdout + run.stderr

    text_run = subprocess.run(
        [sys.executable, "-m", "ai", "uci412-demo", "--format", "text"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert text_run.returncode == 0, text_run.stderr
    assert SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE in text_run.stdout


def test_uci412_demo_cli_rejects_unknown_budget():
    run = subprocess.run(
        [sys.executable, "-m", "ai", "uci412-demo", "--budget", "bogus"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert run.returncode == 2
    assert "invalid choice" in run.stderr
