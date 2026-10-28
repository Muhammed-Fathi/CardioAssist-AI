"""AI-8 source-specific standalone UCI-412 synthetic research model tests.

Covers the thin orchestration layer :mod:`ai.uci412_research`:

* source-specific fail-closed guards (synthetic Track A only; OCR, wearable,
  Track B, patient-upload, real-data and cross-source inputs rejected);
* the complete synthetic build (nested CV, cross-fitted calibration, negative
  control, independent held-out test, SHAP/LIME) with an origin-labelled,
  never-merged metrics contract;
* deterministic, JSON-clean reporting with the SYNTHETIC_TEST marker;
* the full RESEARCH_ONLY bundle round-trip, authenticated load and tamper
  rejection; and
* proof that only the generic AI-1 execution profile is used (never the
  Cleveland D-047 frozen profile) and that no cross-source AUROC comparison is
  produced.

Everything runs on generated synthetic fixtures inside private temporary
directories; no real UCI-412 row, workbook, patient background or lab panel is
ever read or written.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from ai import ensure_private_directory
from ai.errors import BundleIntegrityError, ClinicalInputValidationError
from ai.training import (
    EXECUTION_PROFILE_AI1_GENERIC_V1,
    EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1,
)
from ai.uci412_research import (
    ORIGIN_APPARENT_FINAL_CALIBRATOR_DIAGNOSTIC,
    ORIGIN_DEVELOPMENT_OOF_CROSS_FITTED_CALIBRATED,
    ORIGIN_DEVELOPMENT_OOF_UNCALIBRATED,
    ORIGIN_HELD_OUT_SYNTHETIC_TEST,
    SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE,
    UCI412_PANEL_ID,
    Uci412ResearchGovernanceError,
    Uci412ResearchModelConfig,
    build_uci412_synthetic_research_model,
    load_uci412_research_predictor,
    validate_uci412_synthetic_cohort,
)
from ai.research_routes import build_synthetic_uci412_basic_clinical_cohort
from ai.panels import DA_A1_BASIC_CLINICAL_PANEL

ALL_ORIGINS = (
    ORIGIN_DEVELOPMENT_OOF_UNCALIBRATED,
    ORIGIN_DEVELOPMENT_OOF_CROSS_FITTED_CALIBRATED,
    ORIGIN_APPARENT_FINAL_CALIBRATOR_DIAGNOSTIC,
    ORIGIN_HELD_OUT_SYNTHETIC_TEST,
)


# --------------------------------------------------------------------------- #
# Session-scoped full build (packaged)                                        #
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="session")
def work_root(tmp_path_factory) -> Path:
    return ensure_private_directory(tmp_path_factory.mktemp("ai8_uci412"))


@pytest.fixture(scope="session")
def packaged_build(work_root: Path):
    config = Uci412ResearchModelConfig.fast(
        package_bundle=True, work_root=work_root
    )
    return build_uci412_synthetic_research_model(config)


# --------------------------------------------------------------------------- #
# Configuration                                                               #
# --------------------------------------------------------------------------- #


def test_default_config_is_real_budget_and_fast_profile_is_reduced():
    default = Uci412ResearchModelConfig()
    assert (default.n_development, default.n_test) == (240, 120)
    assert default.seed == 20261028
    fast = Uci412ResearchModelConfig.fast()
    assert fast.outer_folds == 3
    assert fast.n_development < default.n_development
    assert fast.package_bundle is False


def test_config_validation_rejects_impossible_budgets():
    with pytest.raises(ValueError, match="n_development"):
        Uci412ResearchModelConfig(n_development=8, n_test=40)
    with pytest.raises(ValueError, match="exploratory_threshold"):
        Uci412ResearchModelConfig(exploratory_threshold=1.0)
    with pytest.raises(ValueError, match="shuffle_max_allowed_auroc"):
        Uci412ResearchModelConfig(shuffle_max_allowed_auroc=0.4)


def test_training_config_uses_only_generic_ai1_profile_never_cleveland_d047():
    training = Uci412ResearchModelConfig.fast().training_config()
    assert training.execution_profile is EXECUTION_PROFILE_AI1_GENERIC_V1
    assert training.execution_profile is not EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1
    assert training.protocol_id == "CAI-AI8-SYNTHETIC-UCI412-DA-A1-BASIC-CLINICAL-V1"


# --------------------------------------------------------------------------- #
# Source-specific guards (no training)                                        #
# --------------------------------------------------------------------------- #


@pytest.fixture()
def cohort():
    records, labels = build_synthetic_uci412_basic_clinical_cohort(48, seed=20261028)
    return records, labels


def test_valid_synthetic_cohort_validates_to_sixteen_feature_matrix(cohort):
    records, labels = cohort
    X, y, panel = validate_uci412_synthetic_cohort(records, labels)
    assert X.shape == (48, 16)
    assert y.shape == (48,)
    assert panel.panel_id == UCI412_PANEL_ID
    assert set(np.unique(y)).issubset({0, 1})


def test_development_and_test_cohorts_are_distinct_rows():
    dev, dev_labels = build_synthetic_uci412_basic_clinical_cohort(48, seed=20261028)
    test, test_labels = build_synthetic_uci412_basic_clinical_cohort(48, seed=20261029)
    X_dev, _, _ = validate_uci412_synthetic_cohort(dev, dev_labels)
    X_test, _, _ = validate_uci412_synthetic_cohort(test, test_labels)
    assert not np.array_equal(X_dev, X_test)


def test_non_synthetic_record_is_rejected(cohort):
    records, labels = cohort
    records[0]["synthetic"] = False
    with pytest.raises(Uci412ResearchGovernanceError, match="synthetic"):
        validate_uci412_synthetic_cohort(records, labels)


def test_track_b_context_is_rejected(cohort):
    records, labels = cohort
    records[0]["context"]["track"] = "B"
    with pytest.raises(Uci412ResearchGovernanceError, match="Track B"):
        validate_uci412_synthetic_cohort(records, labels)


@pytest.mark.parametrize(
    "source",
    [
        "ocr",
        "ocr_document",
        "wearable",
        "simulated_wearable",
        "patient_upload",
        "real_patient",
        "real_data",
        "clinician_record",
        "track_b",
    ],
)
def test_prohibited_input_sources_are_rejected(cohort, source):
    records, labels = cohort
    records[0]["context"]["source"] = source
    with pytest.raises(Uci412ResearchGovernanceError):
        validate_uci412_synthetic_cohort(records, labels)


def test_unknown_input_source_is_rejected(cohort):
    records, labels = cohort
    records[0]["context"]["source"] = "manual_intake_form"
    with pytest.raises(Uci412ResearchGovernanceError, match="structured_synthetic_research"):
        validate_uci412_synthetic_cohort(records, labels)


@pytest.mark.parametrize(
    "foreign_panel",
    ["da_a2_resting_v1", "da_a2_resting_labs_v1", "da_a1_clinical_core_labs_v1"],
)
def test_foreign_panel_records_are_rejected(cohort, foreign_panel):
    records, labels = cohort
    records[0]["panel_id"] = foreign_panel
    with pytest.raises(Uci412ResearchGovernanceError):
        validate_uci412_synthetic_cohort(records, labels)


def test_empty_cohort_is_rejected(cohort):
    _, labels = cohort
    with pytest.raises(ClinicalInputValidationError, match="at least one record"):
        validate_uci412_synthetic_cohort([], [])


def test_non_mapping_record_is_rejected(cohort):
    records, labels = cohort
    records[0] = ("Age", 53)  # type: ignore[assignment]
    with pytest.raises(ClinicalInputValidationError, match="mapping"):
        validate_uci412_synthetic_cohort(records, labels)


def test_malformed_context_is_rejected(cohort):
    records, labels = cohort
    records[0]["context"] = "track-a"
    with pytest.raises(ClinicalInputValidationError, match="context metadata"):
        validate_uci412_synthetic_cohort(records, labels)


def test_label_length_mismatch_is_rejected(cohort):
    records, labels = cohort
    with pytest.raises(ClinicalInputValidationError, match="label count"):
        validate_uci412_synthetic_cohort(records, labels[:-1])


def test_non_binary_label_is_rejected(cohort):
    records, labels = cohort
    labels = list(labels)
    labels[0] = 2
    with pytest.raises(ClinicalInputValidationError, match="binary integers"):
        validate_uci412_synthetic_cohort(records, labels)


# --------------------------------------------------------------------------- #
# Origin-labelled metrics contract                                           #
# --------------------------------------------------------------------------- #


def test_report_has_exactly_four_never_merged_origins(packaged_build):
    origins = packaged_build.report.metrics_by_origin
    assert tuple(origins.keys()) == ALL_ORIGINS


def test_every_metric_block_carries_synthetic_not_clinical_marker(packaged_build):
    for origin, block in packaged_build.report.metrics_by_origin.items():
        assert block["evidence_marker"] == SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE
        assert block["clinical_evidence"] is False
        assert block["prediction_origin"] == origin


def test_development_origin_blocks_record_exclusion_guarantees(packaged_build):
    blocks = packaged_build.report.metrics_by_origin
    uncal = blocks[ORIGIN_DEVELOPMENT_OOF_UNCALIBRATED]
    cross = blocks[ORIGIN_DEVELOPMENT_OOF_CROSS_FITTED_CALIBRATED]
    assert uncal["each_observation_excluded_from_model_fit"] is True
    assert uncal["each_observation_excluded_from_calibrator_fit"] is False
    assert cross["each_observation_excluded_from_model_fit"] is True
    assert cross["each_observation_excluded_from_calibrator_fit"] is True
    # Summary metrics resolve to real numbers, never silent None.
    for value in uncal["selected_procedure_summary_across_repeats"].values():
        assert isinstance(value, float) and np.isfinite(value)
    assert cross["selected_procedure_summary_across_repeats"]["log_loss"] > 0


def test_apparent_block_is_explicitly_labelled_not_unbiased(packaged_build):
    apparent = packaged_build.report.metrics_by_origin[
        ORIGIN_APPARENT_FINAL_CALIBRATOR_DIAGNOSTIC
    ]
    assert apparent["unbiased_calibrated_performance_estimate"] is False
    assert apparent["apparent_in_calibrator_fit"] is True
    assert apparent["metrics"]["n_samples"] == packaged_build.config.n_development


def test_held_out_block_is_independent_and_uses_frozen_model(packaged_build):
    config = packaged_build.config
    block = packaged_build.report.metrics_by_origin[ORIGIN_HELD_OUT_SYNTHETIC_TEST]
    assert block["test_cohort_seed"] == config.seed + 1
    assert block["class_distribution"]["n"] == config.n_test
    dist = block["class_distribution"]
    assert dist["n_positive"] + dist["n_negative"] == config.n_test
    assert 0.0 < block["prevalence"] < 1.0
    assert (
        block["metrics"]["evaluation_scope"]
        == "SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE_UCI412_HELD_OUT"
    )
    # No external recalibration is silently applied to the primary metrics.
    assert (
        block["prevalence_shift_vs_development"][
            "external_recalibration_applied_to_primary_metrics"
        ]
        is False
    )
    assert block["threshold_semantics"]["threshold_clinically_approved"] is False


def test_metric_values_lie_in_valid_ranges(packaged_build):
    held_out = packaged_build.report.metrics_by_origin[ORIGIN_HELD_OUT_SYNTHETIC_TEST]
    metrics = held_out["metrics"]
    auc = metrics["discrimination"]["roc_auc"]
    ap = metrics["discrimination"]["average_precision"]
    brier = metrics["proper_scoring_and_calibration"]["brier_score"]
    assert 0.0 <= auc <= 1.0
    assert 0.0 <= ap <= 1.0
    assert 0.0 <= brier <= 1.0
    ci = metrics["bootstrap_95_ci"]["roc_auc"]
    assert ci[0] <= auc <= ci[1]


def test_no_cross_source_auroc_comparison_is_emitted(packaged_build):
    serialized = json.dumps(packaged_build.report.to_dict()).lower()
    metric_section = json.dumps(
        dict(packaged_build.report.metrics_by_origin)
    ).lower()
    # The metric contract never references Cleveland/UCI-45 as a comparator.
    assert "cleveland" not in metric_section
    assert "uci45" not in metric_section
    assert "cross_source" not in metric_section
    # The only permitted UCI-45 mention is the target non-equivalence warning.
    assert "related-but-not-identical" in serialized


# --------------------------------------------------------------------------- #
# Source, feature and target bindings                                        #
# --------------------------------------------------------------------------- #


def test_feature_contract_is_bound_to_registered_panel(packaged_build):
    feature_contract = packaged_build.report.feature_contract
    assert feature_contract["panel_id"] == UCI412_PANEL_ID
    assert feature_contract["feature_count"] == 16
    assert feature_contract["ordered_feature_names"] == list(
        DA_A1_BASIC_CLINICAL_PANEL.feature_names
    )
    assert (
        feature_contract["contract_sha256"]
        == DA_A1_BASIC_CLINICAL_PANEL.contract_sha256
    )
    assert feature_contract["field_order_is_contract"] is True


def test_target_contract_preserves_ge50_boundary(packaged_build):
    target = packaged_build.report.target_contract
    assert target["threshold_boundary"] == "GREATER_THAN_OR_EQUAL_50_PERCENT"
    assert target["target_id"] == DA_A1_BASIC_CLINICAL_PANEL.target_id
    assert len(target["target_definition_sha256"]) == 64


def test_source_identity_declares_uci411_participant_overlap(packaged_build):
    identity = packaged_build.report.source_identity
    assert identity["dataset_id"] == "DA-A1"
    assert identity["source_family"] == "UCI-412"
    assert identity["same_participants_as_uci411"] is True
    assert identity["synthetic_only"] is True


def test_model_binding_uses_generic_profile_and_fold_contained_preprocessing(
    packaged_build,
):
    binding = packaged_build.report.model_binding
    assert packaged_build.run.execution_profile is EXECUTION_PROFILE_AI1_GENERIC_V1
    assert binding["execution_profile"] == "AI1_GENERIC_V1"
    assert binding["preprocessing_contract"] == "fold_contained_json_lineage_v1"
    assert binding["model_and_preprocessing_version_bound"] is True


# --------------------------------------------------------------------------- #
# Calibration, dispersion, explainability, negative control                   #
# --------------------------------------------------------------------------- #


def test_calibration_integrity_is_cross_fitted(packaged_build):
    config = packaged_build.config
    calibration = packaged_build.report.calibration_integrity
    assert calibration["cross_fitted_per_fold_calibrators"] == config.outer_folds
    assert calibration["calibration_binding_matches_model_family"] is True
    assert calibration["n_oof_samples"] == config.n_development
    assert calibration["evidence_marker"] == SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE
    assert np.isfinite(calibration["intercept"])
    assert np.isfinite(calibration["slope"])


def test_fold_dispersion_is_descriptive_not_validated_uncertainty(packaged_build):
    config = packaged_build.config
    dispersion = packaged_build.report.fold_dispersion
    assert dispersion["fold_ensemble_count"] == config.outer_folds
    assert dispersion["uncertainty_semantics"].startswith("DESCRIPTIVE")
    assert dispersion["validated_patient_specific_interval"] is False
    assert dispersion["validated_epistemic_uncertainty"] is False


def test_shap_is_additive_over_sixteen_attributions(packaged_build):
    shap = packaged_build.report.shap_quality
    # Additivity must hold on the quantity actually explained, over exactly the
    # 16 panel features, with a tight numerical sum-check.
    assert shap["sum_check_passed"] is True
    assert shap["attribution_count"] == 16
    assert shap["max_abs_discrepancy"] < 1e-9
    assert shap["background_sample_count"] > 0
    assert shap["faithful_to_model_family"] is True
    assert shap["explained_quantity"] in {
        "raw_model_score",
        "raw_model_log_odds",
        "calibrated_log_odds",
    }
    # Only the linear calibrated-log-odds path explains the calibrated score
    # directly; nothing is ever claimed additive in calibrated probability
    # units. The flags must stay internally consistent for the chosen family.
    assert shap["additive_on_calibrated_probability"] is False
    assert shap["explains_calibrated_score_directly"] == (
        shap["explained_quantity"] == "calibrated_log_odds"
    )


def test_lime_quality_is_reported_truthfully_with_stability(packaged_build):
    lime = packaged_build.report.lime_quality
    assert lime["stability_assessed"] is True
    assert isinstance(lime["quality_status"], str) and lime["quality_status"]
    assert isinstance(lime["is_reliable_for_interpretation"], bool)
    assert lime["is_local_approximation"] is True
    assert lime["local_fidelity_abs_error"] >= 0.0
    assert np.isfinite(lime["local_fidelity_relative_error"])


def test_negative_control_respects_leakage_ceiling(packaged_build):
    config = packaged_build.config
    negative = packaged_build.report.negative_control
    assert negative["leakage_alarm_triggered"] is False
    assert negative["max_permuted_roc_auc"] <= negative["leakage_ceiling"]
    assert negative["leakage_ceiling"] == config.shuffle_max_allowed_auroc
    assert len(negative["label_shuffle_seeds"]) == len(
        negative["permuted_selected_roc_aucs"]
    )
    assert len(negative["label_shuffle_seeds"]) >= 1


def test_eligibility_remains_research_only(packaged_build):
    eligibility = packaged_build.report.eligibility
    assert eligibility["serving_eligibility"] == "RESEARCH_ONLY"
    assert eligibility["approved_for_serving"] is False
    assert eligibility["clinical_use_authorized"] is False
    assert eligibility["real_data_authorized"] is False
    assert eligibility["gate_pt_p3"] == "CLOSED"
    assert len(packaged_build.report.limitations) >= 4


# --------------------------------------------------------------------------- #
# Determinism and JSON cleanliness                                            #
# --------------------------------------------------------------------------- #


def test_report_is_json_clean_without_nan(tmp_path):
    config = Uci412ResearchModelConfig.fast(work_root=ensure_private_directory(tmp_path))
    result = build_uci412_synthetic_research_model(config)
    json.dumps(result.to_dict(), allow_nan=False, sort_keys=True)


def test_identical_configs_produce_identical_report_hash(tmp_path_factory):
    root_a = ensure_private_directory(tmp_path_factory.mktemp("det_a"))
    root_b = ensure_private_directory(tmp_path_factory.mktemp("det_b"))
    config_a = Uci412ResearchModelConfig.fast(work_root=root_a)
    config_b = Uci412ResearchModelConfig.fast(work_root=root_b)
    hash_a = build_uci412_synthetic_research_model(config_a).report.deterministic_sha256
    hash_b = build_uci412_synthetic_research_model(config_b).report.deterministic_sha256
    assert hash_a == hash_b


def test_report_hash_excludes_local_filesystem_paths(packaged_build):
    payload = json.dumps(packaged_build.report.to_dict(), sort_keys=True)
    assert str(packaged_build.bundle_dir) not in payload
    assert "trusted_bundles" not in payload


# --------------------------------------------------------------------------- #
# Bundle round-trip, authenticated load and tamper rejection                  #
# --------------------------------------------------------------------------- #


def test_bundle_binding_is_research_only_and_panel_bound(packaged_build):
    binding = packaged_build.report.bundle_binding
    assert binding is not None
    assert binding["producer_authenticated"] is True
    assert binding["safe_for_pickle_deserialization"] is True
    assert binding["serving_eligibility"] == "RESEARCH_ONLY"
    assert binding["approved_for_serving"] is False
    assert binding["clinical_use_authorized"] is False
    assert binding["manifest_panel_id"] == UCI412_PANEL_ID
    assert (
        binding["manifest_panel_contract_sha256"]
        == DA_A1_BASIC_CLINICAL_PANEL.contract_sha256
    )
    assert binding["manifest_pooled_cohorts"] is False
    assert len(binding["manifest_ordered_feature_names"]) == 16
    assert len(binding["verified_file_hashes"]) >= 5
    assert binding["attestation_scheme"]


def test_offline_prediction_is_research_only_and_explained(packaged_build):
    offline = packaged_build.report.offline_prediction
    assert offline is not None
    assert offline["serving_eligibility"] == "RESEARCH_ONLY"
    assert offline["approved_for_serving"] is False
    assert offline["shap_sum_check_passed"] is True
    assert 0.0 <= offline["calibrated_research_score"] <= 1.0
    assert 0.0 <= offline["raw_model_score"] <= 1.0
    assert np.isfinite(offline["calibrated_log_odds"])
    assert offline["score_interpretation"] == "RESEARCH_ONLY_NOT_INDIVIDUAL_CLINICAL_RISK"


def test_bundle_reloads_through_source_specific_loader(packaged_build):
    key = packaged_build.signing_key_path.read_bytes()
    predictor = load_uci412_research_predictor(
        packaged_build.bundle_dir,
        trusted_local_root=packaged_build.trusted_root,
        signing_key=key,
    )
    assert predictor.panel.panel_id == UCI412_PANEL_ID
    # The predictor carries no serving surface of its own; eligibility lives
    # on the trusted VerifiedBundleDescriptor that the loader asserts against.
    descriptor = predictor._descriptor
    assert descriptor.serving_eligibility == "RESEARCH_ONLY"
    assert descriptor.approved_for_serving is False
    assert descriptor.clinical_use_authorized is False
    assert predictor.model_id == packaged_build.run.model_id


def test_bundle_rejects_wrong_signing_key(packaged_build):
    with pytest.raises(BundleIntegrityError, match="attestation failed verification"):
        load_uci412_research_predictor(
            packaged_build.bundle_dir,
            trusted_local_root=packaged_build.trusted_root,
            signing_key=b"B" * 32,
        )


def test_bundle_outside_trusted_root_is_rejected(packaged_build, tmp_path):
    other_root = ensure_private_directory(tmp_path / "other_trusted_root")
    key = packaged_build.signing_key_path.read_bytes()
    with pytest.raises(BundleIntegrityError, match="outside trusted_local_root"):
        load_uci412_research_predictor(
            packaged_build.bundle_dir,
            trusted_local_root=other_root,
            signing_key=key,
        )


@pytest.fixture()
def isolated_packaged_build(tmp_path):
    """A function-scoped packaged build so tamper tests never touch shared state."""
    work_root = ensure_private_directory(tmp_path / "tamper_work")
    config = Uci412ResearchModelConfig.fast(
        package_bundle=True, work_root=work_root
    )
    return build_uci412_synthetic_research_model(config)


def test_tampered_bundle_artifact_fails_closed_before_joblib_load(
    isolated_packaged_build,
):
    # Mutating an authenticated, hash-bound artifact (the fitted model) must
    # fail integrity verification before any deserialization can occur.
    build = isolated_packaged_build
    bundle = build.bundle_dir
    key = build.signing_key_path.read_bytes()
    target = bundle / "model.joblib"
    original = target.read_bytes()
    try:
        target.write_bytes(original + b"\x00")
        with pytest.raises(BundleIntegrityError):
            load_uci412_research_predictor(
                bundle,
                trusted_local_root=build.trusted_root,
                signing_key=key,
            )
    finally:
        target.write_bytes(original)


def test_no_bundle_path_leaves_bundle_sections_none(tmp_path):
    config = Uci412ResearchModelConfig.fast(
        package_bundle=False, work_root=ensure_private_directory(tmp_path)
    )
    result = build_uci412_synthetic_research_model(config)
    assert result.bundle_dir is None
    assert result.report.bundle_binding is None
    assert result.report.offline_prediction is None
