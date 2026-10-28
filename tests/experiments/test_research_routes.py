"""AI-7: source-specific research route catalog and synthetic-only orchestration.

Tests the versioned route catalog, the strict route resolver, the deterministic
synthetic end-to-end route exercises, and the negative controls that keep this
layer from becoming an authorization back door.

Every fixture is deterministically generated in memory. No real patient record,
dataset file, or committed binary artifact is created or read. The frozen A3
diagnostic runtime (``ai.diagnostic_scope``) and the accepted real Cleveland
bundle are never touched by these tests.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from dataclasses import replace

from ai import (
    DA_A1_BASIC_CLINICAL_PANEL,
    DA_A1_CLINICAL_CORE_LABS_PANEL,
    DA_A2_RESTING_LABS_PANEL,
    DA_A2_RESTING_PANEL,
    ClinicalInputValidationError,
    CohortGovernanceError,
    ExternalEvaluationLedger,
    FoldSafeClinicalPreprocessor,
    ResearchCadPredictor,
    ResearchPanelContract,
    ResearchTrainingConfig,
    RouteResolutionError,
    evaluate_comprehensive_metrics,
    assert_route_eligible,
    evaluate_locked_external_cohort,
    execute_synthetic_route_exercise,
    validate_cohort_records,
    get_route_descriptor,
    get_panel_contract,
    resolve_route,
    train_research_model,
    validate_clinical_record,
)
from ai.calibration import compute_fold_prediction_dispersion
from ai.training import (
    _estimator_input_matrix,
    _positive_proba_and_optional_logit,
)
from ai.research_routes import (
    ADMISSIBLE_SYNTHETIC_TEST_ONLY,
    EVAL_NOT_AUTHORIZED,
    EVAL_NOT_EVALUATED,
    EVAL_SYNTHETIC_TEST,
    LOCKED_EXTERNAL_TARGET_NEVER_TRAIN,
    OP_BUNDLE_PACKAGING,
    OP_CLINICAL_SERVING,
    OP_END_TO_END_EXERCISE,
    OP_LIME_ASSESSMENT,
    OP_REAL_BUNDLE_INFERENCE,
    OP_REAL_DATA_TRAINING,
    OP_REAL_EXTERNAL_EVALUATION,
    OP_ROUTE_CONTRACT_QUERY,
    OP_SHAP_ATTRIBUTION,
    OP_SYNTHETIC_EXTERNAL_EVALUATION,
    OP_SYNTHETIC_PREDICTION,
    OP_SYNTHETIC_TRAINING,
    ResearchRouteDescriptor,
    RouteEligibilityResult,
    SyntheticRouteExerciseConfig,
    describe_route_catalog,
    build_synthetic_uci412_basic_clinical_cohort,
    build_synthetic_uci45_resting_cohort,
)
from ai.diagnostic_scope import RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES

REPO_ROOT = Path(__file__).resolve().parents[2]

SYNTHETIC_CTX = {
    "track": "A",
    "source": "structured_synthetic_research",
    "synthetic": True,
}


# --------------------------------------------------------------------------- #
# Route catalog                                                               #
# --------------------------------------------------------------------------- #

EXPECTED_ROUTE_IDS = frozenset(
    {
        "da_a2_resting_v1",
        "da_a2_resting_labs_v1",
        "da_a1_basic_clinical_v1",
        "da_a1_clinical_core_labs_v1",
        "da_a2_hungary_locked_transportability_v1",
    }
)


def test_route_catalog_contains_expected_routes() -> None:
    from ai import RESEARCH_ROUTE_CATALOG

    assert frozenset(RESEARCH_ROUTE_CATALOG.keys()) == EXPECTED_ROUTE_IDS
    assert len(RESEARCH_ROUTE_CATALOG) == 5
    assert describe_route_catalog()["route_count"] == 5


def test_route_descriptors_bind_to_registered_panels() -> None:
    from ai import RESEARCH_ROUTE_CATALOG, REGISTERED_PANELS

    for route_id, route in RESEARCH_ROUTE_CATALOG.items():
        assert isinstance(route, ResearchRouteDescriptor)
        assert route.route_id == route_id
        assert route.panel_id in REGISTERED_PANELS
        assert route.panel_contract_sha256 == REGISTERED_PANELS[route.panel_id].contract_sha256
        assert route.descriptor_sha256
        assert route.evaluation_status in {
            "INTERNAL",
            "EXTERNAL",
            "SYNTHETIC_TEST",
            "NOT_EVALUATED",
            "NOT_AUTHORIZED",
        }
        # The descriptor binds to the panel; it never redefines fields.
        assert route.panel_contract_sha256 == REGISTERED_PANELS[route.panel_id].contract_sha256


def test_route_descriptor_is_deterministic() -> None:
    route = get_route_descriptor("da_a2_resting_v1")
    first = route.descriptor_sha256
    second = get_route_descriptor("da_a2_resting_v1").descriptor_sha256
    assert first == second
    assert len(first) == 64


def test_da_a2_resting_route_metadata() -> None:
    route = get_route_descriptor("da_a2_resting_v1")
    assert route.dataset_id == "DA-A2"
    assert route.source_family == "UCI-45"
    assert route.panel_id == "da_a2_resting_v1"
    assert route.prediction_time_admissibility == ADMISSIBLE_SYNTHETIC_TEST_ONLY
    assert route.evaluation_status == EVAL_SYNTHETIC_TEST
    assert OP_REAL_DATA_TRAINING not in route.permitted_operations
    assert OP_CLINICAL_SERVING not in route.permitted_operations
    assert OP_REAL_BUNDLE_INFERENCE in route.forbidden_operations
    assert ">50%" in route.target_definition
    assert "not equivalent" in " ".join(route.non_equivalence_restrictions).lower()


def test_da_a1_basic_clinical_route_metadata() -> None:
    route = get_route_descriptor("da_a1_basic_clinical_v1")
    assert route.dataset_id == "DA-A1"
    assert route.source_family == "UCI-412"
    assert route.panel_id == "da_a1_basic_clinical_v1"
    assert len(route.panel_contract_sha256) == 64
    assert ">=50%" in route.target_definition
    assert route.evaluation_status == EVAL_SYNTHETIC_TEST
    # UCI-412 input is never translated into Cleveland schema here.
    assert "never translated" in " ".join(route.non_equivalence_restrictions).lower()


def test_planned_labs_routes_are_blocked() -> None:
    labs_route = get_route_descriptor("da_a2_resting_labs_v1")
    core_labs_route = get_route_descriptor("da_a1_clinical_core_labs_v1")
    assert labs_route.prediction_time_admissibility == "PLANNED_BLOCKED_PENDING_AUTHORIZATION"
    assert core_labs_route.prediction_time_admissibility.startswith("PROPOSED_PRE_ANGIOGRAPHY")
    assert labs_route.evaluation_status == EVAL_NOT_EVALUATED
    assert core_labs_route.evaluation_status == EVAL_NOT_EVALUATED
    # Only the contract query is permitted; no synthetic training exercise.
    assert OP_ROUTE_CONTRACT_QUERY in labs_route.permitted_operations
    assert OP_ROUTE_CONTRACT_QUERY in core_labs_route.permitted_operations
    assert OP_SYNTHETIC_TRAINING not in labs_route.permitted_operations
    assert OP_SYNTHETIC_TRAINING not in core_labs_route.permitted_operations


def test_hungary_locked_route_metadata() -> None:
    route = get_route_descriptor("da_a2_hungary_locked_transportability_v1")
    assert route.dataset_id == "DA-A2"
    assert route.panel_id == "da_a2_resting_v1"
    assert route.declared_external_target == "Hungary_locked"
    assert route.prediction_time_admissibility == LOCKED_EXTERNAL_TARGET_NEVER_TRAIN
    assert route.evaluation_status == EVAL_NOT_AUTHORIZED
    assert "never trained" in " ".join(route.evidence_limitations).lower()
    assert OP_REAL_EXTERNAL_EVALUATION not in route.permitted_operations


# --------------------------------------------------------------------------- #
# Route resolver                                                              #
# --------------------------------------------------------------------------- #

def _da_a2_resting() -> tuple[str, str]:
    return "DA-A2", "da_a2_resting_v1"


def _da_a1_basic() -> tuple[str, str]:
    return "DA-A1", "da_a1_basic_clinical_v1"


def test_resolve_da_a2_resting_synthetic_training_eligible() -> None:
    dataset_id, panel_id = _da_a2_resting()
    result = resolve_route(
        dataset_id=dataset_id,
        panel_id=panel_id,
        operation=OP_SYNTHETIC_TRAINING,
        source_family="UCI-45",
        declared_input_context=SYNTHETIC_CTX,
    )
    assert result.eligible is True
    assert result.decision == "ROUTE_RESOLVED"
    assert result.route_id == "da_a2_resting_v1"
    assert result.rejections == ()


def test_resolve_da_a1_basic_clinical_synthetic_training_eligible() -> None:
    dataset_id, panel_id = _da_a1_basic()
    result = resolve_route(
        dataset_id=dataset_id,
        panel_id=panel_id,
        operation=OP_SYNTHETIC_PREDICTION,
        source_family="UCI-412",
        declared_input_context=SYNTHETIC_CTX,
    )
    assert result.eligible is True
    assert result.route_id == "da_a1_basic_clinical_v1"


def test_resolve_hungary_route_requires_external_target() -> None:
    dataset_id, panel_id = _da_a2_resting()
    # Without the declared locked target, the internal Cleveland route resolves.
    internal = resolve_route(
        dataset_id=dataset_id,
        panel_id=panel_id,
        operation=OP_ROUTE_CONTRACT_QUERY,
        declared_input_context=SYNTHETIC_CTX,
    )
    assert internal.eligible is True
    assert internal.route_id == "da_a2_resting_v1"
    # With the locked Hungary target, the transportability route resolves.
    external = resolve_route(
        dataset_id=dataset_id,
        panel_id=panel_id,
        operation=OP_ROUTE_CONTRACT_QUERY,
        declared_input_context={**SYNTHETIC_CTX, "external_cohort_id": "Hungary_locked"},
    )
    assert external.eligible is True
    assert external.route_id == "da_a2_hungary_locked_transportability_v1"


def test_resolve_unknown_dataset_rejected() -> None:
    result = resolve_route(
        dataset_id="DA-X",
        panel_id="da_a2_resting_v1",
        operation=OP_SYNTHETIC_TRAINING,
        declared_input_context=SYNTHETIC_CTX,
    )
    assert result.eligible is False
    assert result.decision == "ROUTE_REJECTED"
    assert "no_matching_route" in result.rejections


def test_resolve_unknown_panel_rejected() -> None:
    result = resolve_route(
        dataset_id="DA-A2",
        panel_id="no_such_panel_v1",
        operation=OP_SYNTHETIC_TRAINING,
        declared_input_context=SYNTHETIC_CTX,
    )
    assert result.eligible is False
    assert "no_matching_route" in result.rejections


def test_resolve_dataset_panel_mismatch_rejected_no_translation() -> None:
    # A UCI-412 dataset is never matched to a Cleveland panel (no crosswalk).
    result = resolve_route(
        dataset_id="DA-A1",
        panel_id="da_a2_resting_v1",
        operation=OP_SYNTHETIC_TRAINING,
        declared_input_context=SYNTHETIC_CTX,
    )
    assert result.eligible is False
    assert "no_matching_route" in result.rejections
    result = resolve_route(
        dataset_id="DA-A2",
        panel_id="da_a1_basic_clinical_v1",
        operation=OP_SYNTHETIC_TRAINING,
        declared_input_context=SYNTHETIC_CTX,
    )
    assert result.eligible is False
    assert "no_matching_route" in result.rejections


def test_resolve_unknown_operation_rejected() -> None:
    dataset_id, panel_id = _da_a2_resting()
    result = resolve_route(
        dataset_id=dataset_id,
        panel_id=panel_id,
        operation="not_a_registered_operation",
        declared_input_context=SYNTHETIC_CTX,
    )
    assert result.eligible is False
    assert "unknown_operation" in result.rejections


@pytest.mark.parametrize(
    "operation",
    [OP_REAL_DATA_TRAINING, OP_REAL_EXTERNAL_EVALUATION, OP_REAL_BUNDLE_INFERENCE, OP_CLINICAL_SERVING],
)
def test_real_data_and_clinical_operations_rejected_on_every_route(operation) -> None:
    for route_id in EXPECTED_ROUTE_IDS:
        route = get_route_descriptor(route_id)
        result = resolve_route(
            dataset_id=route.dataset_id,
            panel_id=route.panel_id,
            operation=operation,
            declared_input_context=SYNTHETIC_CTX,
        )
        assert result.eligible is False, f"{route_id} / {operation} must be rejected"
        assert result.rejections


def test_resolve_track_b_rejected() -> None:
    dataset_id, panel_id = _da_a2_resting()
    result = resolve_route(
        dataset_id=dataset_id,
        panel_id=panel_id,
        operation=OP_SYNTHETIC_TRAINING,
        declared_input_context={"track": "B", "source": "patient_monitoring"},
    )
    assert result.eligible is False
    assert result.rejections
    assert "track_not_a" in result.rejections


def test_resolve_wearable_source_rejected() -> None:
    dataset_id, panel_id = _da_a2_resting()
    result = resolve_route(
        dataset_id=dataset_id,
        panel_id=panel_id,
        operation=OP_SYNTHETIC_PREDICTION,
        declared_input_context={"track": "A", "source": "simulated_wearable"},
    )
    assert result.eligible is False
    assert result.rejections
    assert "unsupported_input_source" in result.rejections


def test_resolve_real_data_input_context_rejected() -> None:
    dataset_id, panel_id = _da_a2_resting()
    result = resolve_route(
        dataset_id=dataset_id,
        panel_id=panel_id,
        operation=OP_SYNTHETIC_TRAINING,
        declared_input_context={**SYNTHETIC_CTX, "real_data": True},
    )
    assert result.eligible is False
    assert "real_data_input_context_rejected" in result.rejections


def test_resolve_labs_routes_contract_only() -> None:
    for route_id in ("da_a2_resting_labs_v1", "da_a1_clinical_core_labs_v1"):
        route = get_route_descriptor(route_id)
        result = resolve_route(
            dataset_id=route.dataset_id,
            panel_id=route.panel_id,
            operation=OP_ROUTE_CONTRACT_QUERY,
            declared_input_context=SYNTHETIC_CTX,
        )
        assert result.eligible is True
        result = resolve_route(
            dataset_id=route.dataset_id,
            panel_id=route.panel_id,
            operation=OP_SYNTHETIC_TRAINING,
            declared_input_context=SYNTHETIC_CTX,
        )
        assert result.eligible is False
        assert "not_permitted" in result.rejections[0]


def test_assert_route_eligible_raises_on_rejection() -> None:
    with pytest.raises(RouteResolutionError):
        assert_route_eligible(
            dataset_id="DA-X",
            panel_id="da_a2_resting_v1",
            operation=OP_SYNTHETIC_TRAINING,
            declared_input_context=SYNTHETIC_CTX,
        )


def test_resolver_never_ranks_by_performance() -> None:
    # The resolver accepts no performance input and returns no metrics; route
    # identity is decided solely by dataset, panel, operation and context.
    import inspect

    signature = inspect.signature(resolve_route)
    assert "auroc" not in signature.parameters
    assert "performance" not in signature.parameters
    result = resolve_route(
        dataset_id="DA-A2",
        panel_id="da_a2_resting_v1",
        operation=OP_SYNTHETIC_TRAINING,
        declared_input_context=SYNTHETIC_CTX,
    )
    assert "metrics" not in result.to_dict()


# --------------------------------------------------------------------------- #
# Synthetic end-to-end route exercises                                        #
# --------------------------------------------------------------------------- #

FAST_CONFIG = SyntheticRouteExerciseConfig(
    n_development=110,
    n_test=55,
    seed=20261027,
    outer_folds=3,
    inner_folds=2,
    bootstrap_resamples=60,
    shap_max_background_samples=20,
    lime_num_perturbations=120,
    shuffle_max_allowed_auroc=0.85,
)


def _assert_route_exercise_structure(result: Any, expected_route_id: str) -> None:
    assert isinstance(result.exercise_id, str)
    assert result.exercise_id.startswith(f"ai7-synthetic-{expected_route_id}")
    assert result.seed == FAST_CONFIG.seed
    assert result.route.route_id == expected_route_id
    assert result.eligibility.eligible is True
    assert result.eligibility.decision == "ROUTE_RESOLVED"
    # Per-instance prediction-score output, explicitly separated from dataset Accuracy.
    score = result.score_declaration
    assert 0.0 < score.calibrated_research_score < 1.0
    assert score.threshold_clinically_validated is False
    assert score.to_dict()["exploratory_threshold_clinically_validated"] is False
    assert score.to_dict()["interpretation"] == "RESEARCH_ONLY_NOT_INDIVIDUAL_CLINICAL_CAD_RISK"
    # Dataset-level contract.
    contract = result.evaluation_contract
    assert contract.evaluation_status == EVAL_SYNTHETIC_TEST
    assert contract.dataset_id == result.route.dataset_id
    assert contract.panel_id == result.route.panel_id
    assert contract.panel_contract_sha256 == result.route.panel_contract_sha256
    assert contract.threshold_clinically_approved is False
    assert contract.confidence_interval_method is not None
    assert "bootstrap" in str(contract.confidence_interval_method).lower()
    # Metrics families present.
    metrics = contract.metrics
    assert "roc_auc" in metrics["discrimination"]
    assert "average_precision" in metrics["discrimination"]
    assert "brier_score" in metrics["proper_scoring_and_calibration"]
    assert "log_loss" in metrics["proper_scoring_and_calibration"]
    cs = metrics["class_specific_at_exploratory_threshold"]
    for key in ("accuracy", "sensitivity_recall_pos", "specificity_recall_neg", "ppv_precision_pos", "npv_neg"):
        assert key in cs
    assert metrics["evaluation_scope"].startswith("SYNTHETIC_TEST_ROUTE_")
    assert 0.0 <= metrics["prevalence"] <= 1.0
    # SHAP additivity on the declared scale.
    assert result.evaluation_contract.shap_report["sum_check_passed"] is True
    assert result.evaluation_contract.shap_report["scale"] in ("calibrated_log_odds", "raw_model_probability")
    # LIME: declared scale, fidelity, stability, acceptance state.
    assert result.evaluation_contract.lime_report["quality_status"]
    assert result.evaluation_contract.lime_report["scale"]
    # Descriptive dispersion is explicitly not validated uncertainty.
    assert contract.fold_dispersion["validated_epistemic_uncertainty"] is False
    assert contract.fold_dispersion["uncertainty_semantics"].startswith("DESCRIPTIVE")
    # Mandatory research limitations.
    assert len(result.limitations) >= 3
    assert any("not CAD performance" in lim for lim in result.limitations)
    assert any("clinical decision threshold" in lim for lim in result.limitations)


def test_da_a2_resting_synthetic_exercise_end_to_end() -> None:
    result = execute_synthetic_route_exercise("da_a2_resting_v1", config=FAST_CONFIG)
    _assert_route_exercise_structure(result, "da_a2_resting_v1")
    assert result.route.dataset_id == "DA-A2"
    assert result.route.source_family == "UCI-45"
    assert len(result.route.panel_contract_sha256) == 64
    assert result.evaluation_contract.development_prevalence >= 0.0


def test_da_a1_basic_clinical_synthetic_exercise_end_to_end() -> None:
    result = execute_synthetic_route_exercise("da_a1_basic_clinical_v1", config=FAST_CONFIG)
    _assert_route_exercise_structure(result, "da_a1_basic_clinical_v1")
    assert result.route.dataset_id == "DA-A1"
    assert result.route.source_family == "UCI-412"
    # 16 basic clinical columns.
    panel = get_panel_contract("da_a1_basic_clinical_v1")
    assert len(panel.fields) == 16


def test_synthetic_exercise_is_deterministic_for_fixed_seed() -> None:
    cfg = SyntheticRouteExerciseConfig(
        n_development=70, n_test=35, seed=20261029, outer_folds=2, inner_folds=2,
        bootstrap_resamples=40, shap_max_background_samples=16, lime_num_perturbations=80,
    )
    first = execute_synthetic_route_exercise("da_a2_resting_v1", config=cfg)
    second = execute_synthetic_route_exercise("da_a2_resting_v1", config=cfg)
    assert first.deterministic_sha256 == second.deterministic_sha256
    assert first.score_declaration.calibrated_research_score == second.score_declaration.calibrated_research_score
    assert first.evaluation_contract.metrics["discrimination"]["roc_auc"] == second.evaluation_contract.metrics["discrimination"]["roc_auc"]


def test_blocked_routes_are_not_exercisable() -> None:
    from ai.research_routes import RouteNotExercisableError

    cfg = SyntheticRouteExerciseConfig(n_development=40, n_test=20, seed=1, bootstrap_resamples=20)
    with pytest.raises(RouteNotExercisableError):
        execute_synthetic_route_exercise("da_a2_resting_labs_v1", config=cfg)
    with pytest.raises(RouteNotExercisableError):
        execute_synthetic_route_exercise("da_a1_clinical_core_labs_v1", config=cfg)


# --------------------------------------------------------------------------- #
# Bundle round-trip: artifact loading + inference authorization boundary      #
# --------------------------------------------------------------------------- #

def test_synthetic_bundle_round_trip_not_approved_for_serving() -> None:
    from tempfile import mkdtemp

    cfg = SyntheticRouteExerciseConfig(
        n_development=60, n_test=30, seed=20261030, outer_folds=2, inner_folds=2,
        bootstrap_resamples=40, shap_max_background_samples=16, lime_num_perturbations=80,
        include_bundle_round_trip=True, work_root=Path(mkdtemp(prefix="ai7_bundle_")),
    )
    result = execute_synthetic_route_exercise("da_a2_resting_v1", config=cfg)
    bt = result.bundle_round_trip
    assert bt is not None
    assert bt["packaged_serving_eligibility"] == "RESEARCH_ONLY"
    assert bt["packaged_approved_for_serving"] is False
    assert bt["producer_authenticated"] is True
    assert bt["safe_for_pickle_deserialization"] is True
    assert bt["prediction_approved_for_serving"] is False
    assert bt["prediction_clinical_use_authorized"] is False
    assert bt["prediction_serving_eligibility"] == "RESEARCH_ONLY"
    assert bt["predictor_panel_id"] == "da_a2_resting_v1"
    assert bt["artifact_hashes"]


# --------------------------------------------------------------------------- #
# Negative controls: real-data guards are not weakened by the route layer     #
# --------------------------------------------------------------------------- #

def _minimal_uci45_resting_record(*, with_chol: bool = False, with_fbs: bool = True) -> dict[str, Any]:
    features: dict[str, Any] = {
        "age": 55.0,
        "sex": 1,
        "cp": 2,
        "trestbps": 130.0,
        "restecg": 1,
    }
    units: dict[str, str] = {"age": "years", "trestbps": "mmHg"}
    reasons: dict[str, str] = {}
    if with_chol:
        features["chol"] = 220.0
        units["chol"] = "mg/dL"
    else:
        reasons["chol"] = "not_provided"
    if with_fbs:
        features["fbs"] = 0
    else:
        reasons["fbs"] = "not_provided"
    return {
        "synthetic": True,
        "panel_id": DA_A2_RESTING_LABS_PANEL.panel_id,
        "features": features,
        "units": units,
        "missing_reasons": reasons,
        "context": SYNTHETIC_CTX,
    }


def test_real_data_training_is_blocked_without_synthetic_confirmation() -> None:
    records, labels = build_synthetic_uci45_resting_cohort(40, seed=1)
    with pytest.raises(CohortGovernanceError) as exc:
        train_research_model(
            records,
            labels,
            DA_A2_RESTING_PANEL,
            model_id="blocked_real",
            development_cohort_id="synthetic_cleveland",
            development_dataset_id="DA-A2",
            synthetic_data_confirmed=False,
        )
    assert exc.value.code == "gate_pt_closed_real_training_blocked"


def test_cohort_pooling_is_blocked() -> None:
    records, labels = build_synthetic_uci45_resting_cohort(40, seed=1)
    with pytest.raises(CohortGovernanceError) as exc:
        train_research_model(
            records,
            labels,
            DA_A2_RESTING_PANEL,
            model_id="pooled",
            development_cohort_id="synthetic_cleveland",
            development_dataset_id="DA-A2",
            synthetic_data_confirmed=True,
            pooled_cohorts=True,
        )
    assert exc.value.code == "cohort_pooling_prohibited"


def test_real_hungary_cohort_id_is_blocked_for_external_evaluation() -> None:
    dev_records, dev_labels = build_synthetic_uci45_resting_cohort(60, seed=1)
    run = train_research_model(
        dev_records,
        dev_labels,
        DA_A2_RESTING_PANEL,
        model_id="dev",
        development_cohort_id="synthetic_cleveland",
        development_dataset_id="DA-A2",
        synthetic_data_confirmed=True,
    )
    ext_records, ext_labels = build_synthetic_uci45_resting_cohort(30, seed=2)
    from tempfile import mkdtemp
    ledger_path = Path(mkdtemp(prefix="ai7_ledger_")) / "ledger.json"
    with pytest.raises(CohortGovernanceError) as exc:
        evaluate_locked_external_cohort(
            run,
            ext_records,
            ext_labels,
            external_cohort_id="real_hungary",
            external_dataset_id="DA-A2:hungary",
            synthetic_data_confirmed=True,
            one_shot_ledger_path=ledger_path,
        )
    assert exc.value.code == "real_hungary_blocked_pending_gate_pt"


def test_external_evaluation_requires_distinct_cohort() -> None:
    dev_records, dev_labels = build_synthetic_uci45_resting_cohort(60, seed=1)
    run = train_research_model(
        dev_records,
        dev_labels,
        DA_A2_RESTING_PANEL,
        model_id="dev2",
        development_cohort_id="synthetic_cleveland",
        development_dataset_id="DA-A2",
        synthetic_data_confirmed=True,
    )
    with pytest.raises(CohortGovernanceError) as exc:
        evaluate_locked_external_cohort(
            run,
            dev_records,
            dev_labels,
            external_cohort_id="synthetic_cleveland",
            external_dataset_id="DA-A2",
            synthetic_data_confirmed=True,
        )
    assert exc.value.code == "external_cohort_identical_to_development"


def test_unverified_lab_timing_rejects_zero_chol() -> None:
    # A measured chol of zero denotes an unavailable measurement and fails closed.
    payload = _minimal_uci45_resting_record(with_chol=True, with_fbs=True)
    payload["features"]["chol"] = 0.0
    with pytest.raises(ClinicalInputValidationError) as exc:
        validate_clinical_record(payload, DA_A2_RESTING_LABS_PANEL)
    assert exc.value.code == "zero_measurement_unavailable"


def test_track_b_wearable_record_rejected_by_panel_validation() -> None:
    payload = _minimal_uci45_resting_record()
    payload["context"] = {"track": "B", "source": "simulated_wearable"}
    payload["features"]["spo2"] = 98.0
    with pytest.raises(ClinicalInputValidationError):
        validate_clinical_record(payload, DA_A2_RESTING_PANEL)


def test_route_layer_never_allows_real_bundle_inference() -> None:
    from ai import RESEARCH_ROUTE_CATALOG

    for route in RESEARCH_ROUTE_CATALOG.values():
        result = resolve_route(
            dataset_id=route.dataset_id,
            panel_id=route.panel_id,
            operation=OP_REAL_BUNDLE_INFERENCE,
            declared_input_context=SYNTHETIC_CTX,
        )
        assert result.eligible is False
        assert result.rejections


def test_synthetic_cohort_builders_match_panel_contracts() -> None:
    # The synthetic fixtures must validate against the registered panels.
    records, labels = build_synthetic_uci45_resting_cohort(20, seed=1)
    X, y, validated = validate_cohort_records(
        records, labels, DA_A2_RESTING_PANEL, require_synthetic=True
    )
    assert X.shape == (20, 5)
    assert set(y.tolist()) == {0, 1}
    assert all(v.synthetic for v in validated)

    records, labels = build_synthetic_uci412_basic_clinical_cohort(20, seed=1)
    X, y, validated = validate_cohort_records(
        records, labels, DA_A1_BASIC_CLINICAL_PANEL, require_synthetic=True
    )
    assert X.shape == (20, 16)
    assert set(y.tolist()) == {0, 1}


def test_frozen_diagnostic_registry_is_untouched_by_route_layer() -> None:
    # The route catalog must not touch ai.diagnostic_scope or the A3 registry.
    assert RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES is not None
    record = RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES[
        "CAI-SCOPE-BOUNDED-OFFLINE-DIAGNOSTIC-INFERENCE-CLEVELAND-D047-V1"
    ]
    assert record["governance_baseline_commit_sha"] == "ad30acc7b05705bf45436d4be95aa1d6a616f8ed"
    assert record["approved_implementation_commit_sha"] == "87bccd6d3ef2331f1e2b2ba8905f34366734538d"
    assert record["expected_panel_id"] == "da_a2_resting_v1"
    assert record["expected_dataset_id"] == "DA-A2"


def test_evaluate_comprehensive_metrics_reports_prevalence_and_threshold() -> None:
    # Metrics reuse the existing implementation; the contract declares prevalence
    # and threshold semantics rather than inferring a clinical cutoff.
    y = np.array([0, 0, 1, 1, 0, 1, 0, 1])
    p = np.array([0.1, 0.4, 0.35, 0.8, 0.2, 0.75, 0.05, 0.9])
    metrics = evaluate_comprehensive_metrics(y, p, threshold=0.5, n_bootstrap=20)
    assert metrics["evaluation_scope"]
    assert metrics["prevalence"] == 0.5
    assert metrics["class_specific_at_exploratory_threshold"]["exploratory_threshold"] == 0.5
    assert metrics["class_specific_at_exploratory_threshold"]["threshold_clinically_approved"] is False
    assert metrics["bootstrap_95_ci"]["method"]


# --------------------------------------------------------------------------- #
# Finding 1 regression: fold-dispersion semantics                             #
# Outer-fold model variation on ONE fixed instance (each fold member's own     #
# preprocessor/estimator/calibrator), NOT between-record variation on a       #
# single final refit model across different test records.                     #
# --------------------------------------------------------------------------- #


def _train_small_dispersion_run(n_rows: int = 60, seed: int = 1):
    records, labels = build_synthetic_uci45_resting_cohort(n_rows, seed=seed)
    return train_research_model(
        records,
        labels,
        DA_A2_RESTING_PANEL,
        model_id="dispersion_repro",
        development_cohort_id="synthetic_cleveland",
        development_dataset_id="DA-A2",
        synthetic_data_confirmed=True,
        config=ResearchTrainingConfig(
            outer_folds=2,
            inner_folds=2,
            bootstrap_resamples=20,
            shap_max_background_samples=16,
        ),
    )


def test_fold_dispersion_count_matches_ensemble_not_test_size() -> None:
    # fold_ensemble_count is len(run.fold_ensemble) (outer_folds), never n_test.
    cfg_small_test = SyntheticRouteExerciseConfig(
        n_development=80,
        n_test=20,
        seed=20261031,
        outer_folds=3,
        inner_folds=2,
        bootstrap_resamples=20,
        shap_max_background_samples=12,
        lime_num_perturbations=64,
    )
    cfg_big_test = SyntheticRouteExerciseConfig(
        n_development=80,
        n_test=50,
        seed=20261031,
        outer_folds=3,
        inner_folds=2,
        bootstrap_resamples=20,
        shap_max_background_samples=12,
        lime_num_perturbations=64,
    )
    r_small = execute_synthetic_route_exercise("da_a2_resting_v1", config=cfg_small_test)
    r_big = execute_synthetic_route_exercise("da_a2_resting_v1", config=cfg_big_test)
    assert r_small.evaluation_contract.fold_dispersion["fold_ensemble_count"] == 3
    assert r_big.evaluation_contract.fold_dispersion["fold_ensemble_count"] == 3
    # Test-set size (10 vs 90) does not change the fold count.
    assert (
        r_small.evaluation_contract.fold_dispersion["fold_ensemble_count"]
        == r_big.evaluation_contract.fold_dispersion["fold_ensemble_count"]
    )
    assert r_small.evaluation_contract.fold_dispersion["fold_ensemble_count"] != 10
    assert r_big.evaluation_contract.fold_dispersion["fold_ensemble_count"] != 90


def test_fold_dispersion_reproduced_from_fold_member_predictions() -> None:
    # Independently reproduce dispersion from actual fold-member predictions on
    # one fixed instance, each calibrated by its own fold calibrator.
    run = _train_small_dispersion_run()
    records, labels = build_synthetic_uci45_resting_cohort(20, seed=7)
    X_test, _y_test, validated_test = validate_cohort_records(
        records, labels, DA_A2_RESTING_PANEL, require_synthetic=True
    )
    panel = DA_A2_RESTING_PANEL
    first_row = X_test[:1]

    fold_raw: list[float] = []
    fold_cal: list[float] = []
    fold_fams: list[str] = []
    for member in run.fold_ensemble:
        z = member.preprocessor.transform(first_row)
        E = _estimator_input_matrix(
            member.model_family, member.preprocessor, first_row, z, run.execution_profile
        )
        raw, raw_logit = _positive_proba_and_optional_logit(
            member.model_family, member.estimator, E
        )
        cal = member.calibrator.calibrate(raw, raw_logits=raw_logit)
        fold_raw.append(float(raw[0]))
        fold_cal.append(float(cal[0]))
        fold_fams.append(member.model_family)

    dispersion = compute_fold_prediction_dispersion(
        fold_raw_scores=fold_raw,
        fold_compatible_calibrated_scores=fold_cal,
        fold_model_families=fold_fams,
        missing_fields_with_reason=tuple(validated_test[0].missing_fields_with_reason),
        total_fields=len(panel.fields),
        development_prevalence=float(run.calibrator.development_prevalence),
    )
    assert dispersion["fold_ensemble_count"] == len(run.fold_ensemble)
    assert dispersion["fold_model_families"] == fold_fams
    assert dispersion["each_fold_calibrated_by_own_training_fold_calibrator"] is True
    assert dispersion["validated_epistemic_uncertainty"] is False
    assert "fold_raw_score_dispersion" in dispersion
    assert "fold_calibrated_score_dispersion" in dispersion


def test_exercise_fold_dispersion_uses_ensemble_count() -> None:
    # End-to-end exercise reports fold_ensemble_count == number of fold members.
    result = execute_synthetic_route_exercise("da_a2_resting_v1", config=FAST_CONFIG)
    assert result.evaluation_contract.fold_dispersion["fold_ensemble_count"] == (
        FAST_CONFIG.outer_folds
    )
    assert result.evaluation_contract.fold_dispersion["fold_ensemble_count"] != (
        FAST_CONFIG.n_test
    )


# --------------------------------------------------------------------------- #
# Finding 2 regression: strict synthetic input context (fail-closed resolver) #
# --------------------------------------------------------------------------- #


def test_resolve_missing_input_context_rejected() -> None:
    dataset_id, panel_id = _da_a2_resting()
    result = resolve_route(
        dataset_id=dataset_id,
        panel_id=panel_id,
        operation=OP_SYNTHETIC_TRAINING,
        declared_input_context=None,
    )
    assert result.eligible is False
    assert "missing_input_context" in result.rejections


def test_resolve_unknown_source_rejected() -> None:
    dataset_id, panel_id = _da_a2_resting()
    result = resolve_route(
        dataset_id=dataset_id,
        panel_id=panel_id,
        operation=OP_SYNTHETIC_TRAINING,
        declared_input_context={
            "track": "A",
            "source": "unknown_source",
            "synthetic": True,
        },
    )
    assert result.eligible is False
    assert "unsupported_input_source" in result.rejections


def test_resolve_missing_synthetic_declaration_rejected() -> None:
    dataset_id, panel_id = _da_a2_resting()
    result = resolve_route(
        dataset_id=dataset_id,
        panel_id=panel_id,
        operation=OP_SYNTHETIC_TRAINING,
        declared_input_context={
            "track": "A",
            "source": "structured_synthetic_research",
        },
    )
    assert result.eligible is False
    assert "synthetic_declaration_missing_or_false" in result.rejections


def test_resolve_false_synthetic_declaration_rejected() -> None:
    dataset_id, panel_id = _da_a2_resting()
    result = resolve_route(
        dataset_id=dataset_id,
        panel_id=panel_id,
        operation=OP_SYNTHETIC_TRAINING,
        declared_input_context={
            "track": "A",
            "source": "structured_synthetic_research",
            "synthetic": False,
        },
    )
    assert result.eligible is False
    assert "synthetic_declaration_missing_or_false" in result.rejections


def test_resolve_contradictory_synthetic_and_real_data_rejected() -> None:
    dataset_id, panel_id = _da_a2_resting()
    result = resolve_route(
        dataset_id=dataset_id,
        panel_id=panel_id,
        operation=OP_SYNTHETIC_TRAINING,
        declared_input_context={
            "track": "A",
            "source": "structured_synthetic_research",
            "synthetic": True,
            "real_data": True,
        },
    )
    assert result.eligible is False
    assert "real_data_input_context_rejected" in result.rejections


@pytest.mark.parametrize("source", ["patient_upload", "clinician_record", "ocr_document"])
def test_resolve_patient_clinician_ocr_source_rejected(source: str) -> None:
    dataset_id, panel_id = _da_a2_resting()
    result = resolve_route(
        dataset_id=dataset_id,
        panel_id=panel_id,
        operation=OP_SYNTHETIC_TRAINING,
        declared_input_context={"track": "A", "source": source, "synthetic": True},
    )
    assert result.eligible is False, f"source {source} must be rejected"
    assert "unsupported_input_source" in result.rejections


def test_resolve_contract_query_never_authorizes_execution() -> None:
    # route_contract_query may inspect metadata but is not an executable op.
    dataset_id, panel_id = _da_a2_resting()
    result = resolve_route(
        dataset_id=dataset_id,
        panel_id=panel_id,
        operation=OP_ROUTE_CONTRACT_QUERY,
        declared_input_context=SYNTHETIC_CTX,
    )
    assert result.eligible is True
    assert result.route_id == "da_a2_resting_v1"

    # A contract-only route resolves for query but rejects synthetic exercise.
    labs = get_route_descriptor("da_a2_resting_labs_v1")
    q = resolve_route(
        dataset_id=labs.dataset_id,
        panel_id=labs.panel_id,
        operation=OP_ROUTE_CONTRACT_QUERY,
        declared_input_context=SYNTHETIC_CTX,
    )
    assert q.eligible is True
    ex = resolve_route(
        dataset_id=labs.dataset_id,
        panel_id=labs.panel_id,
        operation=OP_SYNTHETIC_TRAINING,
        declared_input_context=SYNTHETIC_CTX,
    )
    assert ex.eligible is False
    assert "not_permitted" in ex.rejections[0]


# --------------------------------------------------------------------------- #
# Finding 3 regression: descriptor fingerprint covers bound restrictions      #
# --------------------------------------------------------------------------- #


def test_descriptor_fingerprint_changes_with_bound_restrictions() -> None:
    route = get_route_descriptor("da_a2_resting_v1")
    original = route.descriptor_sha256
    assert len(original) == 64

    # Changing any bound restriction displayed by to_dict() must change the SHA-256.
    for field, new_value in (
        ("evidence_limitations", ("a new evidence limitation",)),
        ("non_equivalence_restrictions", ("a new non-equivalence restriction",)),
        ("non_pooling_restrictions", ("a new non-pooling restriction",)),
    ):
        modified = replace(route, **{field: new_value})
        assert modified.descriptor_sha256 != original, (
            f"descriptor SHA-256 must change when {field} changes"
        )

    # Same route id reproduces the same fingerprint (determinism).
    assert route.descriptor_sha256 == get_route_descriptor("da_a2_resting_v1").descriptor_sha256
