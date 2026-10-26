"""Genuine tabular LIME regression, mathematical, and failure-mode tests (AI-5.1).

Synthetic fixtures only: every cohort, background row, prediction and bundle in
this module is deterministically generated in memory or inside pytest temporary
directories. No real patient record, dataset file, or committed artifact is
accessed.

Coverage:
1. Independent re-implementation of the kernel-weighted ridge surrogate, proving
   that reported weights really come from the documented estimator and that the
   perturbations are scored by actual model calls.
2. Local-fidelity / weighted-fit-quality / runtime / bounded-resource diagnostics.
3. Bitwise repeatability for the same seed and quantitative stability across
   specified seeds.
4. Valid logistic-regression and random-forest explanations (plus the frozen
   Cleveland D-047 8-column forest space and its explicit feature lineage).
5. Categorical-code, numeric-range and optional-missing-value semantics.
6. Fail-closed behaviour for malformed inputs, unsupported models, degenerate
   perturbations and poor surrogate fidelity.
7. Score-scale comparability guards and offline inference/CLI integration.
"""
from __future__ import annotations

from copy import deepcopy
import dataclasses
import json
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock

import numpy as np
import pytest
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression

import ai.lime_explainability as lime_mod
from ai import (
    DA_A2_RESTING_LABS_PANEL,
    DA_A2_RESTING_PANEL,
    ExplainabilityIntegrityError,
    FoldSafeClinicalPreprocessor,
    LimeConfig,
    LimeQualityPolicy,
    OofLogisticCalibrator,
    ResearchCadPredictor,
    ResearchTrainingConfig,
    ShapBackgroundReference,
    assess_lime_stability,
    assert_comparable_explanation_scales,
    build_lime_model_target,
    ensure_private_directory,
    explain_clinical_instance,
    explain_clinical_instance_lime,
    get_or_create_local_signing_key,
    package_research_bundle,
    require_acceptable_lime_quality,
    train_research_model,
    validate_cohort_records,
)
from ai.panels import ALL_PROHIBITED_FIELDS
from ai.training import (
    EXECUTION_PROFILE_AI1_GENERIC_V1,
    _d047_original_rf_matrix,
    _d047_rf_column_to_raw_feature,
)
from ai.validation_harness import _make_synthetic_cohort

REPO_ROOT = Path(__file__).resolve().parents[2]

FAST_LIME_TEST_CONFIG = ResearchTrainingConfig(
    protocol_id="CAI-AI51-LIME-SYNTHETIC-TEST-V1",
    model_version="0.1.0",
    outer_folds=3,
    inner_folds=2,
    repeat_seeds=(20261025,),
    shuffle_control_seeds=(20261101,),
    lr_c_grid=(0.1, 1.0),
    rf_max_depths=(2, 3),
    rf_min_samples_leaf=(5,),
    rf_n_estimators=20,
    bootstrap_resamples=40,
    shap_max_background_samples=24,
)


# --------------------------------------------------------------------------- #
# Deterministic synthetic fixtures
# --------------------------------------------------------------------------- #


def _resting_records(n_rows: int, *, seed: int) -> tuple[list[dict[str, Any]], list[int]]:
    """Derive a DA-A2 resting-panel cohort from the shared synthetic generator."""
    records, labels = _make_synthetic_cohort(n_rows, seed=seed)
    derived: list[dict[str, Any]] = []
    for record in records:
        features = dict(record["features"])
        units = dict(record["units"])
        reasons = dict(record["missing_reasons"])
        for field_name in ("chol", "fbs"):
            features.pop(field_name, None)
            units.pop(field_name, None)
            reasons.pop(field_name, None)
        derived.append(
            {
                "synthetic": True,
                "panel_id": DA_A2_RESTING_PANEL.panel_id,
                "features": features,
                "units": units,
                "missing_reasons": reasons,
            }
        )
    return derived, labels


def _fit_labs_environment() -> SimpleNamespace:
    records, labels = _make_synthetic_cohort(180, seed=20261025)
    X, y, _ = validate_cohort_records(
        records, labels, DA_A2_RESTING_LABS_PANEL, require_synthetic=True
    )
    preprocessor = FoldSafeClinicalPreprocessor.fit(X, DA_A2_RESTING_LABS_PANEL)
    Z = preprocessor.transform(X)
    background = ShapBackgroundReference.from_training_encoded(
        Z, y, preprocessor, max_samples=32, seed=7
    )
    logistic = LogisticRegression(
        C=1.0, solver="lbfgs", max_iter=1000, random_state=7
    ).fit(Z, y)
    forest = RandomForestClassifier(
        n_estimators=24,
        max_depth=4,
        min_samples_leaf=4,
        random_state=7,
        n_jobs=1,
    ).fit(Z, y)
    # Synthetic in-sample calibrators: these exist only to exercise the
    # calibrated-log-odds target plumbing, never a performance claim.
    logistic_calibrator = OofLogisticCalibrator.fit_from_oof(
        y,
        logistic.predict_proba(Z)[:, 1],
        model_family="l2_logistic_regression",
        raw_logits=logistic.decision_function(Z),
    )
    forest_calibrator = OofLogisticCalibrator.fit_from_oof(
        y,
        forest.predict_proba(Z)[:, 1],
        model_family="constrained_random_forest",
    )
    complete_index = next(
        index
        for index in range(len(records))
        if index % 9 != 0 and index % 11 != 0
    )
    return SimpleNamespace(
        records=records,
        labels=labels,
        X=X,
        y=y,
        Z=Z,
        preprocessor=preprocessor,
        background=background,
        logistic=logistic,
        forest=forest,
        logistic_calibrator=logistic_calibrator,
        forest_calibrator=forest_calibrator,
        instance=complete_index,
        missing_instance=0,  # chol and fbs are missing by construction
    )


@pytest.fixture(scope="module")
def labs_env() -> SimpleNamespace:
    return _fit_labs_environment()


@pytest.fixture(scope="module")
def trained_bundle(tmp_path_factory: pytest.TempPathFactory) -> SimpleNamespace:
    """Train, package, verify, and load one synthetic RESEARCH_ONLY bundle."""
    root = ensure_private_directory(tmp_path_factory.mktemp("ai51_lime_root"))
    key_path = root / "private_keys" / "local_bundle_hmac_v1.key"
    signing_key = get_or_create_local_signing_key(key_path)
    trusted_root = ensure_private_directory(root / "trusted_bundles")
    records, labels = _make_synthetic_cohort(72, seed=20261025)
    run = train_research_model(
        records,
        labels,
        DA_A2_RESTING_LABS_PANEL,
        model_id="synth_ai51_lime_bundle",
        development_cohort_id="synthetic_cleveland",
        development_dataset_id="DA-A2:synthetic_cleveland",
        synthetic_data_confirmed=True,
        config=FAST_LIME_TEST_CONFIG,
    )
    bundle_dir = trusted_root / "synthetic_lime_bundle_v1"
    package_research_bundle(run, bundle_dir, signing_key=signing_key)
    predictor = ResearchCadPredictor.from_verified_bundle(
        bundle_dir, trusted_local_root=trusted_root, signing_key=signing_key
    )
    return SimpleNamespace(
        root=root,
        bundle_dir=bundle_dir,
        trusted_root=trusted_root,
        key_path=key_path,
        signing_key=signing_key,
        predictor=predictor,
        run=run,
        record=records[0],
    )


def _explain_labs(
    env: SimpleNamespace,
    *,
    family: str = "l2_logistic_regression",
    instance: int | None = None,
    config: LimeConfig | None = None,
    **overrides: Any,
) -> Any:
    if family == "l2_logistic_regression":
        estimator = env.logistic
        calibrator = env.logistic_calibrator
    else:
        estimator = env.forest
        calibrator = None
    index = env.instance if instance is None else instance
    kwargs: dict[str, Any] = dict(
        model_family=family,
        estimator=estimator,
        preprocessor=env.preprocessor,
        panel=DA_A2_RESTING_LABS_PANEL,
        background=env.background,
        x_raw_row=env.X[index],
        z_row=env.Z[index],
        calibrator=calibrator,
        config=config if config is not None else LimeConfig(
            num_perturbations=512, seed=4242
        ),
    )
    kwargs.update(overrides)
    return explain_clinical_instance_lime(**kwargs)


def _reference_kernel_weights(design: Any, kernel_width: float) -> np.ndarray:
    """Recompute the registered exponential-kernel weights independently."""
    replaced = np.sum(~design.mask, axis=1).astype(np.float64)
    distances = np.sqrt(replaced) / math.sqrt(design.mask.shape[1])
    return np.exp(-np.square(distances) / (float(kernel_width) ** 2))


def _reference_weighted_ridge(
    mask: np.ndarray, scores: np.ndarray, weights: np.ndarray, *, ridge_alpha: float
) -> np.ndarray:
    """Independent whitened-augmented-least-squares implementation."""
    n_rows, n_fields = mask.shape
    design = np.column_stack([np.ones(n_rows), mask.astype(np.float64)])
    square_root_weights = np.sqrt(weights)
    weighted_design = design * square_root_weights[:, None]
    weighted_target = np.asarray(scores, dtype=np.float64) * square_root_weights
    penalty = np.zeros((n_fields + 1, n_fields + 1), dtype=np.float64)
    penalty[1:, 1:] = math.sqrt(ridge_alpha) * np.eye(n_fields)
    augmented_design = np.vstack([weighted_design, penalty])
    augmented_target = np.concatenate(
        [weighted_target, np.zeros(n_fields + 1, dtype=np.float64)]
    )
    theta, *_ = np.linalg.lstsq(augmented_design, augmented_target, rcond=None)
    return theta


# --------------------------------------------------------------------------- #
# 1. Genuine weighted surrogate + actual model calls + local fidelity
# --------------------------------------------------------------------------- #


def test_lime_logistic_regression_matches_independent_weighted_ridge_solver(
    labs_env: SimpleNamespace,
) -> None:
    config = LimeConfig(num_perturbations=512, seed=4242)
    explanation = _explain_labs(labs_env, config=config)

    background_raw = lime_mod.decode_background_to_raw_rows(
        background=labs_env.background,
        preprocessor=labs_env.preprocessor,
        panel=DA_A2_RESTING_LABS_PANEL,
    )
    design = lime_mod._generate_perturbation_design(
        x_raw_row=labs_env.X[labs_env.instance],
        background_raw=background_raw,
        panel=DA_A2_RESTING_LABS_PANEL,
        config=config,
    )
    target = build_lime_model_target(
        model_family="l2_logistic_regression",
        estimator=labs_env.logistic,
        preprocessor=labs_env.preprocessor,
        calibrator=labs_env.logistic_calibrator,
    )
    scored = target.score_raw_rows(design.X_raw)
    theta = _reference_weighted_ridge(
        design.mask,
        scored.target_scores,
        design.weights,
        ridge_alpha=config.ridge_alpha,
    )

    reported = np.asarray(
        [item.lime_weight for item in explanation.attributions], dtype=np.float64
    )
    assert explanation.surrogate_intercept == pytest.approx(theta[0], abs=1e-9)
    assert np.max(np.abs(reported - theta[1:])) < 1e-9
    assert np.max(
        np.abs(design.weights - _reference_kernel_weights(design, config.kernel_width))
    ) < 1e-12

    # The surrogate value at the instance is exactly intercept + sum(weights).
    assert explanation.surrogate_prediction_at_instance == pytest.approx(
        float(theta[0] + np.sum(theta[1:])), abs=1e-12
    )
    # Local fidelity compares that value with an ACTUAL model call.
    z_instance = labs_env.Z[labs_env.instance]
    logits = float(labs_env.logistic.decision_function(z_instance.reshape(1, -1))[0])
    expected_target = float(
        labs_env.logistic_calibrator.transform_log_odds(logits)
    )
    assert explanation.model_prediction_at_instance == pytest.approx(
        expected_target, abs=1e-12
    )
    expected_probability = 1.0 / (1.0 + math.exp(-expected_target))
    assert explanation.linked_probability_value == pytest.approx(
        expected_probability, abs=1e-12
    )
    assert explanation.local_fidelity_abs_error == pytest.approx(
        abs(explanation.surrogate_prediction_at_instance - expected_target), abs=0.0
    )
    assert explanation.local_fidelity_abs_error >= 0.0
    assert explanation.local_fidelity_relative_error < 0.25
    assert explanation.weighted_r2 is not None and explanation.weighted_r2 > 0.2
    assert explanation.unweighted_r2 is not None
    assert explanation.holdout_weighted_r2 is not None
    assert explanation.holdout_rows > 0
    assert explanation.weighted_rmse > 0.0
    assert explanation.n_effective_samples > 100.0
    assert explanation.design_condition_number < 1e6
    assert explanation.explained_quantity == "calibrated_log_odds"
    assert explanation.scale == "calibrated_log_odds"
    assert explanation.explains_calibrated_score_directly is True

    # The exact LinearSHAP explanation on the same instance shares the scale and
    # target value, so SHAP and LIME may be reported side by side.
    shap = explain_clinical_instance(
        model_family="l2_logistic_regression",
        estimator=labs_env.logistic,
        preprocessor=labs_env.preprocessor,
        panel=DA_A2_RESTING_LABS_PANEL,
        background=labs_env.background,
        z_row=z_instance,
        calibrator=labs_env.logistic_calibrator,
    )
    comparability = assert_comparable_explanation_scales(shap, explanation)
    assert comparability["comparable"] is True
    assert comparability["shared_scale"] == "calibrated_log_odds"
    assert shap.target_prediction_on_scale == pytest.approx(
        explanation.model_prediction_at_instance, abs=1e-9
    )
    assert shap.sum_check_passed is True
    # LIME is a different (approximate) method: it is never an additive
    # decomposition and its weights are not required to equal SHAP values.
    assert explanation.additive_decomposition_claim is False
    assert explanation.is_exact is False


def test_lime_uses_only_actual_estimator_calls_not_fabricated_weights(
    labs_env: SimpleNamespace,
) -> None:
    config = LimeConfig(num_perturbations=256, seed=99, score_batch_size=64)
    with mock.patch.object(
        labs_env.forest, "predict_proba", wraps=labs_env.forest.predict_proba
    ) as spied:
        explanation = _explain_labs(
            labs_env, family="constrained_random_forest", config=config
        )
    # 256 perturbation rows scored in 4 batches of 64, plus one instance call.
    assert spied.call_count == 5
    assert explanation.model_call_count == 5
    assert explanation.model_rows_scored == 257
    assert explanation.perturbation_matrix_bytes < 64 * 1024
    assert explanation.runtime_seconds >= 0.0
    assert explanation.runtime_seconds < 10.0

    # A controlled logistic model whose calibrated log-odds depend ONLY on the
    # encoded 'age' column: every other LIME weight must collapse to (near) zero
    # and the 'age' weight must carry the model's sign, proving the weights are
    # derived from actual model outputs instead of being fabricated.
    controlled = LogisticRegression()
    controlled.classes_ = np.asarray([0, 1])
    controlled.n_features_in_ = labs_env.preprocessor.n_encoded_features
    controlled.coef_ = np.zeros((1, labs_env.preprocessor.n_encoded_features))
    age_column = labs_env.preprocessor.encoded_feature_names.index("age__zscore")
    controlled.coef_[0, age_column] = 5.0
    controlled.intercept_ = np.asarray([0.0])
    controlled_explanation = _explain_labs(
        labs_env,
        estimator=controlled,
        config=LimeConfig(num_perturbations=512, seed=99),
    )
    weights = controlled_explanation.weight_map()
    background_raw = lime_mod.decode_background_to_raw_rows(
        background=labs_env.background,
        preprocessor=labs_env.preprocessor,
        panel=DA_A2_RESTING_LABS_PANEL,
    )
    reference_mean_age = float(np.nanmean(background_raw[:, 0]))
    instance_age = float(labs_env.X[labs_env.instance][0])
    assert instance_age != reference_mean_age
    assert abs(weights["age"]) > 1e-3
    assert math.copysign(1.0, weights["age"]) == math.copysign(
        1.0, 5.0 * (instance_age - reference_mean_age)
    )
    other_weights = [value for name, value in weights.items() if name != "age"]
    assert max(abs(value) for value in other_weights) < 0.1 * abs(weights["age"])
    assert abs(weights["chol"]) < 0.05 * abs(weights["age"])


def test_lime_forest_explanation_is_on_raw_model_probability_scale(
    labs_env: SimpleNamespace,
) -> None:
    explanation = _explain_labs(
        labs_env, family="constrained_random_forest", config=LimeConfig(num_perturbations=512, seed=4242)
    )
    expected = float(
        labs_env.forest.predict_proba(labs_env.Z[labs_env.instance].reshape(1, -1))[0, 1]
    )
    assert explanation.explained_quantity == "raw_model_score"
    assert explanation.scale == "raw_model_probability"
    assert explanation.explains_calibrated_score_directly is False
    assert explanation.linked_probability_quantity == "raw_model_score"
    assert explanation.model_prediction_at_instance == pytest.approx(expected, abs=1e-12)
    assert explanation.linked_probability_value == pytest.approx(expected, abs=1e-12)
    assert explanation.score_bounds == (0.0, 1.0)
    assert explanation.target_specification.comparable_with_family_shap_target is True
    assert explanation.weighted_r2 is not None and explanation.weighted_r2 > 0.05
    assert explanation.local_fidelity_relative_error < 0.25
    assert len(explanation.attributions) == len(DA_A2_RESTING_LABS_PANEL.feature_names)
    assert [item.feature_name for item in explanation.attributions] == list(
        DA_A2_RESTING_LABS_PANEL.feature_names
    )


def test_lime_calibrated_forest_target_is_flagged_not_shap_comparable(
    labs_env: SimpleNamespace,
) -> None:
    explanation = _explain_labs(
        labs_env,
        family="constrained_random_forest",
        calibrator=labs_env.forest_calibrator,
        target="calibrated_log_odds",
        config=LimeConfig(num_perturbations=256, seed=5),
    )
    assert explanation.explained_quantity == "calibrated_log_odds"
    assert explanation.explains_calibrated_score_directly is True
    assert (
        explanation.target_specification.comparable_with_family_shap_target is False
    )
    assert "must never be compared" in explanation.score_alignment_note
    shap = explain_clinical_instance(
        model_family="constrained_random_forest",
        estimator=labs_env.forest,
        preprocessor=labs_env.preprocessor,
        panel=DA_A2_RESTING_LABS_PANEL,
        background=labs_env.background,
        z_row=labs_env.Z[labs_env.instance],
    )
    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        assert_comparable_explanation_scales(shap, explanation)
    assert exc_info.value.code == "incompatible_explanation_scales"


# --------------------------------------------------------------------------- #
# 2. Determinism, repeatability and seed stability
# --------------------------------------------------------------------------- #


def test_lime_is_bitwise_repeatable_for_the_same_seed(
    labs_env: SimpleNamespace,
) -> None:
    config = LimeConfig(num_perturbations=256, seed=20261026)
    first = _explain_labs(labs_env, config=config)
    second = _explain_labs(labs_env, config=config)
    assert first.state_sha256 == second.state_sha256
    assert first.weight_map() == second.weight_map()
    assert first.to_dict()["fidelity"] == second.to_dict()["fidelity"]
    assert first.deterministic_payload() == second.deterministic_payload()

    other_seed = _explain_labs(
        labs_env, config=dataclasses.replace(config, seed=20261027)
    )
    assert other_seed.state_sha256 != first.state_sha256
    assert json.dumps(first.to_dict(), allow_nan=False)


def test_lime_stability_across_specified_seeds_is_quantified(
    labs_env: SimpleNamespace,
) -> None:
    seeds = (11, 12, 13, 14, 15)
    report = assess_lime_stability(
        seeds,
        config=LimeConfig(num_perturbations=512, seed=11),
        top_k=3,
        model_family="l2_logistic_regression",
        estimator=labs_env.logistic,
        preprocessor=labs_env.preprocessor,
        panel=DA_A2_RESTING_LABS_PANEL,
        background=labs_env.background,
        x_raw_row=labs_env.X[labs_env.instance],
        z_row=labs_env.Z[labs_env.instance],
        calibrator=labs_env.logistic_calibrator,
    )
    assert report.seeds == seeds
    assert report.reference_seed == 11
    assert report.n_features == len(DA_A2_RESTING_LABS_PANEL.feature_names)
    assert math.isfinite(report.min_pairwise_spearman)
    expected_stable = (
        report.min_pairwise_spearman >= report.criteria["min_pairwise_spearman"]
        and report.sign_agreement_fraction
        >= report.criteria["sign_agreement_fraction"]
        and report.top_k_overlap_fraction
        >= report.criteria["top_k_overlap_fraction"]
    )
    # The label always reflects the registered quantitative criteria, even when
    # a particular instance lands near a decision boundary.
    assert report.stability_assessment == (
        "STABLE_WITHIN_REGISTERED_TOLERANCE" if expected_stable else "SENSITIVE_TO_SEED"
    )
    stable_report = assess_lime_stability(
        seeds,
        config=LimeConfig(num_perturbations=512, seed=11),
        top_k=3,
        model_family="l2_logistic_regression",
        estimator=labs_env.logistic,
        preprocessor=labs_env.preprocessor,
        panel=DA_A2_RESTING_LABS_PANEL,
        background=labs_env.background,
        x_raw_row=labs_env.X[2],
        z_row=labs_env.Z[2],
        calibrator=labs_env.logistic_calibrator,
    )
    assert stable_report.stability_assessment == "STABLE_WITHIN_REGISTERED_TOLERANCE"
    assert (
        stable_report.min_pairwise_spearman
        >= stable_report.criteria["min_pairwise_spearman"]
    )
    assert (
        stable_report.sign_agreement_fraction
        >= stable_report.criteria["sign_agreement_fraction"]
    )
    assert (
        stable_report.top_k_overlap_fraction
        >= stable_report.criteria["top_k_overlap_fraction"]
    )
    assert report.max_feature_weight_std >= 0.0
    assert report.max_abs_weight_deviation_from_reference_seed >= 0.0
    assert report.min_weighted_r2 is not None and report.min_weighted_r2 > 0.0
    assert report.max_local_fidelity_relative_error < 0.25
    assert report.max_local_prediction_abs_deviation >= 0.0
    assert report.runtime_seconds > 0.0
    payload = report.to_dict()
    assert payload["criteria"]["min_pairwise_spearman"] == 0.5
    assert json.dumps(payload, allow_nan=False)

    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        assess_lime_stability([11], model_family="l2_logistic_regression")
    assert exc_info.value.code == "lime_stability_requires_multiple_seeds"
    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        assess_lime_stability([11, 11], model_family="l2_logistic_regression")
    assert exc_info.value.code == "lime_stability_duplicate_seed"


# --------------------------------------------------------------------------- #
# 3. Categorical codes, numeric ranges, missing-value semantics, lineage
# --------------------------------------------------------------------------- #


def test_lime_perturbations_respect_categorical_codes_numeric_ranges_and_missingness(
    labs_env: SimpleNamespace,
) -> None:
    config = LimeConfig(num_perturbations=384, seed=1234)
    background_raw = lime_mod.decode_background_to_raw_rows(
        background=labs_env.background,
        preprocessor=labs_env.preprocessor,
        panel=DA_A2_RESTING_LABS_PANEL,
    )
    # Decoded background marginals are panel-valid by construction.
    for raw_index, spec in enumerate(DA_A2_RESTING_LABS_PANEL.fields):
        column = background_raw[:, raw_index]
        observed = column[~np.isnan(column)]
        if spec.role == "categorical":
            assert set(int(v) for v in observed.tolist()).issubset(
                set(spec.categorical_codes)
            )
        else:
            assert np.all(observed > 0.0)

    design = lime_mod._generate_perturbation_design(
        x_raw_row=labs_env.X[labs_env.missing_instance],
        background_raw=background_raw,
        panel=DA_A2_RESTING_LABS_PANEL,
        config=config,
    )
    for raw_index, spec in enumerate(DA_A2_RESTING_LABS_PANEL.fields):
        column = design.X_raw[:, raw_index]
        if spec.role == "categorical":
            if spec.required:
                assert not np.isnan(column).any()
            observed = column[~np.isnan(column)]
            assert set(int(v) for v in np.rint(observed).tolist()).issubset(
                set(spec.categorical_codes)
            )
            assert np.array_equal(observed, np.rint(observed))
        else:
            assert not np.isinf(column).any()
            if spec.required:
                assert not np.isnan(column).any()
            assert np.all(column[~np.isnan(column)] > 0.0)

    # The forced all-ones row is exactly the explained instance, including the
    # explicit optional-missing states.
    assert np.array_equal(design.mask[0], np.ones(len(DA_A2_RESTING_LABS_PANEL.fields), dtype=bool))
    instance_row = labs_env.X[labs_env.missing_instance]
    assert np.array_equal(
        np.isnan(design.X_raw[0]), np.isnan(instance_row)
    )
    assert np.array_equal(
        design.X_raw[0][~np.isnan(instance_row)], instance_row[~np.isnan(instance_row)]
    )

    explanation = _explain_labs(
        labs_env, instance=labs_env.missing_instance, config=config
    )
    statuses = {item.feature_name: item.status for item in explanation.attributions}
    assert statuses["chol"] == "missing_imputed"
    assert statuses["fbs"] == "missing_imputed"
    assert statuses["age"] == "present"
    encoded = labs_env.preprocessor.transform(instance_row.reshape(1, -1))[0]
    assert encoded[labs_env.preprocessor.encoded_feature_names.index("chol__missing")] == 1.0
    assert encoded[labs_env.preprocessor.encoded_feature_names.index("fbs__missing")] == 1.0

    # Feature lineage: every attribution owns the exact preprocessor slices.
    slices = labs_env.preprocessor.feature_slices
    encoded_names = labs_env.preprocessor.encoded_feature_names
    for item in explanation.attributions:
        expected = tuple(encoded_names[index] for index in slices[item.feature_name])
        assert item.encoded_columns == expected
        assert item.represented_in_estimator_input is True
        assert item.estimator_input_columns == tuple(slices[item.feature_name])
    ranks = sorted(item.absolute_weight_rank for item in explanation.attributions)
    assert ranks == list(range(1, len(ranks) + 1))


def test_lime_rejects_prohibited_or_duplicated_panel_features() -> None:
    prohibited_field = sorted(ALL_PROHIBITED_FIELDS)[0]
    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        lime_mod._assert_panel_is_lime_eligible(
            SimpleNamespace(
                panel_id="fake_panel",
                feature_names=("age", "sex", prohibited_field),
            )
        )
    assert exc_info.value.code == "lime_prohibited_feature_in_panel"
    assert exc_info.value.field == prohibited_field

    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        lime_mod._assert_panel_is_lime_eligible(
            SimpleNamespace(panel_id="fake_panel", feature_names=("age", "age"))
        )
    assert exc_info.value.code == "lime_duplicate_panel_feature"


def test_lime_uncalibrated_logistic_target_and_declared_lineage(
    labs_env: SimpleNamespace,
) -> None:
    target = build_lime_model_target(
        model_family="l2_logistic_regression",
        estimator=labs_env.logistic,
        preprocessor=labs_env.preprocessor,
    )
    specification = target.specification
    assert specification.resolved_target == "raw_model_log_odds"
    assert specification.explained_quantity == "raw_model_log_odds"
    assert specification.scale == "raw_log_odds"
    assert specification.uses_calibrator is False
    assert specification.score_bounds is None
    assert target.lineage_mode == "full_preprocessor_encoding"
    assert target.estimator_input_width == labs_env.preprocessor.n_encoded_features
    assert target.estimator_fitted_width == labs_env.preprocessor.n_encoded_features
    assert target.column_to_raw_feature == tuple(
        raw
        for raw, transform in enumerate(labs_env.preprocessor.field_transforms)
        for _ in transform.slice_indices
    )
    explanation = _explain_labs(
        labs_env, calibrator=None, config=LimeConfig(num_perturbations=256, seed=8)
    )
    expected = float(
        labs_env.logistic.decision_function(
            labs_env.Z[labs_env.instance].reshape(1, -1)
        )[0]
    )
    assert explanation.explained_quantity == "raw_model_log_odds"
    assert explanation.model_prediction_at_instance == pytest.approx(expected, abs=1e-12)
    assert explanation.linked_probability_value == pytest.approx(
        1.0 / (1.0 + math.exp(-expected)), abs=1e-12
    )
    assert explanation.target_specification.comparable_with_family_shap_target is True


def test_lime_tampered_background_encodings_fail_closed(
    labs_env: SimpleNamespace,
) -> None:
    one_hot_target = "sex__eq_1"
    one_hot_index = labs_env.preprocessor.encoded_feature_names.index(one_hot_target)
    matrix = np.array(labs_env.background.background_matrix, dtype=np.float64)
    matrix[0, one_hot_index] = 2.0
    tampered = dataclasses.replace(labs_env.background, background_matrix=matrix)
    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        lime_mod.decode_background_to_raw_rows(
            background=tampered,
            preprocessor=labs_env.preprocessor,
            panel=DA_A2_RESTING_LABS_PANEL,
        )
    assert exc_info.value.code == "lime_background_one_hot_invalid"

    missing_target = "chol__missing"
    missing_index = labs_env.preprocessor.encoded_feature_names.index(missing_target)
    matrix = np.array(labs_env.background.background_matrix, dtype=np.float64)
    matrix[0, missing_index] = 0.5
    tampered = dataclasses.replace(labs_env.background, background_matrix=matrix)
    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        lime_mod.decode_background_to_raw_rows(
            background=tampered,
            preprocessor=labs_env.preprocessor,
            panel=DA_A2_RESTING_LABS_PANEL,
        )
    assert exc_info.value.code == "lime_background_missing_indicator_invalid"

    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        lime_mod.decode_background_to_raw_rows(
            background=dataclasses.replace(
                labs_env.background,
                background_matrix=np.zeros(
                    (1, labs_env.preprocessor.n_encoded_features), dtype=np.float64
                ),
            ),
            preprocessor=labs_env.preprocessor,
            panel=DA_A2_RESTING_LABS_PANEL,
        )
    assert exc_info.value.code == "lime_background_matrix_invalid"


def test_lime_domain_validation_rejects_out_of_range_perturbations(
    labs_env: SimpleNamespace,
) -> None:
    bad_codes = np.zeros((4, len(DA_A2_RESTING_LABS_PANEL.fields)), dtype=np.float64)
    bad_codes[:, 0] = 50.0
    bad_codes[:, 1] = 0.0
    bad_codes[:, 2] = 9.0  # unregistered 'cp' code
    bad_codes[:, 3] = 120.0
    bad_codes[:, 4] = 0.0
    bad_codes[:, 5] = 200.0
    bad_codes[:, 6] = 0.0
    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        lime_mod._validate_perturbation_domain(bad_codes, DA_A2_RESTING_LABS_PANEL)
    assert exc_info.value.code == "lime_perturbation_domain_violation"

    negative_age = bad_codes.copy()
    negative_age[:, 2] = 1.0
    negative_age[:, 0] = -5.0
    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        lime_mod._validate_perturbation_domain(
            negative_age, DA_A2_RESTING_LABS_PANEL
        )
    assert exc_info.value.code == "lime_perturbation_domain_violation"

    missing_required = bad_codes.copy()
    missing_required[:, 2] = 1.0
    missing_required[0, 0] = np.nan
    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        lime_mod._validate_perturbation_domain(
            missing_required, DA_A2_RESTING_LABS_PANEL
        )
    assert exc_info.value.code == "lime_perturbation_domain_violation"


# --------------------------------------------------------------------------- #
# 4. Frozen Cleveland D-047 projection + explicit lineage
# --------------------------------------------------------------------------- #


def test_lime_frozen_d047_projection_uses_explicit_forest_column_lineage() -> None:
    records, labels = _resting_records(120, seed=60606)
    X, y, _ = validate_cohort_records(
        records, labels, DA_A2_RESTING_PANEL, require_synthetic=True
    )
    preprocessor = FoldSafeClinicalPreprocessor.fit(X, DA_A2_RESTING_PANEL)
    Z = preprocessor.transform(X)
    background = ShapBackgroundReference.from_training_encoded(
        Z, y, preprocessor, max_samples=24, seed=5
    )
    projected = _d047_original_rf_matrix(preprocessor, X)
    forest = RandomForestClassifier(
        n_estimators=16, max_depth=3, min_samples_leaf=4, random_state=3, n_jobs=1
    ).fit(projected, y)
    mapping = _d047_rf_column_to_raw_feature(preprocessor)
    assert mapping == (0, 3, 1, 2, 2, 2, 4, 4)
    assert forest.n_features_in_ == 8

    # Without the projection the frozen forest cannot be explained implicitly.
    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        explain_clinical_instance_lime(
            model_family="constrained_random_forest",
            estimator=forest,
            preprocessor=preprocessor,
            panel=DA_A2_RESTING_PANEL,
            background=background,
            x_raw_row=X[0],
            z_row=Z[0],
            config=LimeConfig(num_perturbations=192, seed=9),
        )
    assert exc_info.value.code == "lime_estimator_width_lineage_mismatch"

    builder = lambda raw_rows: _d047_original_rf_matrix(preprocessor, raw_rows)
    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        explain_clinical_instance_lime(
            model_family="constrained_random_forest",
            estimator=forest,
            preprocessor=preprocessor,
            panel=DA_A2_RESTING_PANEL,
            background=background,
            x_raw_row=X[0],
            z_row=Z[0],
            estimator_input_builder=builder,
            config=LimeConfig(num_perturbations=192, seed=9),
        )
    assert exc_info.value.code == "lime_projection_mapping_required"

    explanation = explain_clinical_instance_lime(
        model_family="constrained_random_forest",
        estimator=forest,
        preprocessor=preprocessor,
        panel=DA_A2_RESTING_PANEL,
        background=background,
        x_raw_row=X[0],
        z_row=Z[0],
        estimator_input_builder=builder,
        projected_column_to_raw_feature=mapping,
        config=LimeConfig(num_perturbations=384, seed=9),
    )
    assert [item.feature_name for item in explanation.attributions] == list(
        DA_A2_RESTING_PANEL.feature_names
    )
    assert explanation.explained_quantity == "raw_model_score"
    expected = float(forest.predict_proba(projected[0].reshape(1, -1))[0, 1])
    assert explanation.model_prediction_at_instance == pytest.approx(expected, abs=1e-12)
    feature_names = DA_A2_RESTING_PANEL.feature_names
    for item in explanation.attributions:
        raw_index = feature_names.index(item.feature_name)
        assert item.estimator_input_columns == tuple(
            column for column, raw in enumerate(mapping) if raw == raw_index
        )
        assert item.encoded_columns == tuple(
            preprocessor.field_transforms[raw_index].encoded_columns
        )
    assert explanation.weighted_r2 is not None and explanation.weighted_r2 > 0.0
    assert explanation.local_fidelity_relative_error < 0.25

    report = assess_lime_stability(
        (9, 10, 11),
        config=LimeConfig(num_perturbations=384, seed=9),
        top_k=2,
        model_family="constrained_random_forest",
        estimator=forest,
        preprocessor=preprocessor,
        panel=DA_A2_RESTING_PANEL,
        background=background,
        x_raw_row=X[0],
        z_row=Z[0],
        estimator_input_builder=builder,
        projected_column_to_raw_feature=mapping,
    )
    assert report.stability_assessment == "STABLE_WITHIN_REGISTERED_TOLERANCE"
    assert report.min_pairwise_spearman >= 0.5


# --------------------------------------------------------------------------- #
# 5. Fail-closed behaviour
# --------------------------------------------------------------------------- #


def test_lime_config_and_target_validation_fails_closed(
    labs_env: SimpleNamespace,
) -> None:
    invalid_configs = (
        {"num_perturbations": 1},
        {"num_perturbations": 1_000_000},
        {"seed": -1},
        {"kernel_width": 0.0},
        {"ridge_alpha": -1.0},
        {"holdout_fraction": 1.0},
        {"score_batch_size": 0},
        {"max_abs_lime_weight": 0.0},
        {"reference_scheme": "unregistered_reference_scheme"},
    )
    for overrides in invalid_configs:
        with pytest.raises(ExplainabilityIntegrityError) as exc_info:
            LimeConfig(**overrides)
        assert exc_info.value.code == "lime_invalid_config"

    # Generation knobs and acceptance thresholds are deliberately separate:
    # a LimeConfig must not be able to carry a quality threshold.
    for removed in (
        "min_weighted_r2",
        "max_local_fidelity_relative_error",
        "min_effective_samples",
        "max_design_condition_number",
    ):
        assert removed not in {
            field.name for field in dataclasses.fields(LimeConfig)
        }

    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        _explain_labs(labs_env, target="raw_model_probability")
    assert exc_info.value.code == "lime_incompatible_target_scale"

    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        _explain_labs(labs_env, family="constrained_random_forest", target="raw_model_log_odds")
    assert exc_info.value.code == "lime_incompatible_target_scale"

    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        _explain_labs(labs_env, calibrator=None, target="calibrated_log_odds")
    assert exc_info.value.code == "lime_calibrator_required"

    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        _explain_labs(labs_env, calibrator=labs_env.forest_calibrator)
    assert exc_info.value.code == "lime_incompatible_calibrator"

    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        _explain_labs(labs_env, target="not_a_target")
    assert exc_info.value.code == "lime_invalid_target"


def test_lime_unsupported_models_fail_closed(labs_env: SimpleNamespace) -> None:
    dummy = DummyClassifier(strategy="prior").fit(labs_env.Z, labs_env.y)
    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        _explain_labs(labs_env, estimator=dummy, model_family="prevalence_dummy")
    assert exc_info.value.code == "unsupported_model_family_for_lime"

    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        _explain_labs(labs_env, model_family="gradient_boosting")
    assert exc_info.value.code == "unsupported_model_family_for_lime"

    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        _explain_labs(labs_env, family="constrained_random_forest", estimator=labs_env.logistic)
    assert exc_info.value.code == "estimator_family_mismatch"

    unpacked = RandomForestClassifier(n_estimators=2, random_state=1)
    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        _explain_labs(labs_env, family="constrained_random_forest", estimator=unpacked)
    assert exc_info.value.code == "lime_estimator_not_fitted"


def test_lime_malformed_inputs_and_backgrounds_fail_closed(
    labs_env: SimpleNamespace,
) -> None:
    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        _explain_labs(labs_env, x_raw_row=labs_env.X[labs_env.instance][:-1])
    assert exc_info.value.code == "lime_invalid_instance_vector"

    broken = labs_env.X[labs_env.instance].copy()
    broken[2] = 99.0  # unregistered 'cp' code
    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        _explain_labs(labs_env, x_raw_row=broken)
    assert exc_info.value.code == "lime_unknown_categorical_code"

    missing_required = labs_env.X[labs_env.instance].copy()
    missing_required[0] = np.nan  # required 'age'
    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        _explain_labs(labs_env, x_raw_row=missing_required)
    assert exc_info.value.code == "lime_missing_required_instance_value"

    infinite = labs_env.X[labs_env.instance].copy()
    infinite[3] = np.inf
    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        _explain_labs(labs_env, x_raw_row=infinite)
    assert exc_info.value.code == "lime_invalid_instance_vector"

    tampered_row = labs_env.Z[labs_env.instance].copy()
    tampered_row[0] += 0.5
    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        _explain_labs(labs_env, z_row=tampered_row)
    assert exc_info.value.code == "lime_instance_lineage_mismatch"

    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        _explain_labs(
            labs_env,
            background=dataclasses.replace(
                labs_env.background, panel_id="not_the_active_panel"
            ),
        )
    assert exc_info.value.code == "lime_background_contract_mismatch"

    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        _explain_labs(
            labs_env,
            panel=DA_A2_RESTING_PANEL,
        )
    assert exc_info.value.code == "lime_panel_lineage_mismatch"

    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        _explain_labs(
            labs_env,
            estimator_input_builder=lambda rows: labs_env.preprocessor.transform(rows),
        )
    assert exc_info.value.code == "lime_projection_mapping_required"

    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        _explain_labs(
            labs_env,
            estimator_input_builder=lambda rows: labs_env.preprocessor.transform(rows),
            projected_column_to_raw_feature=(0, 1),
        )
    assert exc_info.value.code == "lime_projection_mapping_mismatch"

    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        _explain_labs(labs_env, projected_column_to_raw_feature=(0, 1, 2))
    assert exc_info.value.code == "lime_projection_unexpected"


def test_lime_degenerate_perturbations_and_poor_fidelity_fail_closed(
    labs_env: SimpleNamespace,
) -> None:
    n_fields = len(DA_A2_RESTING_LABS_PANEL.fields)
    constant_mask = np.ones((64, n_fields), dtype=bool)
    constant_mask[1:, 0] = False
    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        lime_mod._weighted_ridge_fit(
            constant_mask,
            np.linspace(0.0, 1.0, 64),
            np.ones(64),
            ridge_alpha=1.0,
        )
    assert exc_info.value.code == "lime_degenerate_perturbations"

    collapsed = np.zeros((64, n_fields), dtype=bool)
    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        lime_mod._weighted_ridge_fit(
            collapsed, np.linspace(0.0, 1.0, 64), np.ones(64), ridge_alpha=1.0
        )
    assert exc_info.value.code == "lime_degenerate_perturbations"

    fitted_width = int(labs_env.forest.n_features_in_)
    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        _explain_labs(
            labs_env,
            family="constrained_random_forest",
            estimator_input_builder=lambda rows: np.zeros((rows.shape[0], fitted_width)),
            projected_column_to_raw_feature=tuple(
                raw
                for raw, ft in enumerate(labs_env.preprocessor.field_transforms)
                for _ in ft.slice_indices
            ),
            config=LimeConfig(num_perturbations=128, seed=3),
        )
    assert exc_info.value.code == "lime_degenerate_model_output"

    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        _explain_labs(
            labs_env, config=LimeConfig(num_perturbations=192, seed=3, max_abs_lime_weight=1e-9)
        )
    assert exc_info.value.code == "lime_unbounded_surrogate_weight"

    # An unreachable acceptance policy no longer raises during generation; it
    # produces an explicit non-acceptable verdict instead (see the dedicated
    # quality tests), and callers that demand acceptance fail closed.
    strict_policy = LimeQualityPolicy(
        min_weighted_r2=0.999999,
        min_holdout_weighted_r2=0.999999,
    )
    strict = _explain_labs(
        labs_env,
        config=LimeConfig(num_perturbations=192, seed=3),
        quality_policy=strict_policy,
    )
    assert strict.quality_status == "LOW_LOCAL_FIDELITY"
    assert strict.is_reliable_for_interpretation is False
    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        require_acceptable_lime_quality(strict)
    assert exc_info.value.code == "lime_quality_not_acceptable"


def test_lime_never_claims_exactness_additivity_or_causality(
    labs_env: SimpleNamespace,
) -> None:
    explanation = _explain_labs(
        labs_env, config=LimeConfig(num_perturbations=192, seed=17)
    )
    payload = explanation.to_dict()
    assert payload["is_exact"] is False
    assert payload["is_local_approximation"] is True
    assert payload["additive_decomposition_claim"] is False
    assert payload["method_family"] == "lime_local_approximation"
    assert "NOT Shapley" in payload["interpretation_note"]
    assert "NOT Shapley" in payload["score_alignment_note"] or (
        "not Shapley" in payload["score_alignment_note"].lower()
    )
    for item in payload["attributions"]:
        assert "NOT a Shapley value" in item["interpretation"]
        assert "NOT causal" in item["interpretation"]
    assert any("RESEARCH_ONLY" in item for item in payload["limitations"])
    assert any("causal" in item for item in payload["limitations"])
    assert payload["background"]["contains_background_values_in_output"] is False


# --------------------------------------------------------------------------- #
# 6. Offline inference + CLI integration (synthetic provenance only)
# --------------------------------------------------------------------------- #


def test_lime_inference_integration_and_scale_comparability(
    trained_bundle: SimpleNamespace,
) -> None:
    predictor = trained_bundle.predictor
    payload = deepcopy(dict(trained_bundle.record))
    result = predictor.predict_research_only(
        payload,
        lime_config=LimeConfig(num_perturbations=192, seed=2468),
    )
    assert result.lime_explanation is not None
    lime = result.lime_explanation
    assert lime.model_family == result.model_family
    assert lime.explained_quantity == result.explanation.explained_quantity
    assert lime.scale == result.explanation.scale
    assert result.lime_comparability is not None
    assert result.lime_comparability["comparable"] is True
    if lime.explained_quantity == "calibrated_log_odds":
        assert lime.model_prediction_at_instance == pytest.approx(
            result.calibrated_log_odds, abs=1e-9
        )
    else:
        assert lime.explained_quantity == "raw_model_score"
        assert lime.model_prediction_at_instance == pytest.approx(
            result.raw_model_score, abs=1e-9
        )
    assert any("LIME" in item for item in result.limitations)
    # Stability is assessed by default, so the attached verdict is complete and
    # never silently defaults to "acceptable".
    assert result.lime_stability is not None
    assert lime.quality.stability_seeds == (20261026, 20261027, 20261028)
    assert lime.quality.policy.policy_sha256 == (
        result.lime_stability.quality_policy_sha256
    )
    assert lime.quality_status in {
        "ACCEPTABLE_LOCAL_APPROXIMATION",
        "LOW_LOCAL_FIDELITY",
        "UNSTABLE",
        "UNVERIFIED_STABILITY",
        "INVALID",
    }
    exported = result.to_dict()
    assert exported["lime_explanation"]["method"] == lime.method
    assert exported["explanation_comparability"]["comparable"] is True
    assert exported["lime_stability"] is not None
    assert exported["prediction"]["lime_quality_status"] == lime.quality_status
    assert exported["prediction"]["lime_reliable_for_interpretation"] is (
        lime.is_reliable_for_interpretation
    )
    assert any(
        "LIME quality verdict" in item for item in result.limitations
    )
    assert json.dumps(exported, allow_nan=False)

    # Without a stability assessment the verdict cannot be acceptable.
    unverified = predictor.predict_research_only(
        deepcopy(dict(trained_bundle.record)),
        lime_config=LimeConfig(num_perturbations=192, seed=2468),
        lime_stability_seeds=None,
    )
    assert unverified.lime_stability is None
    assert unverified.lime_explanation.quality_status == "UNVERIFIED_STABILITY"
    assert unverified.lime_explanation.is_reliable_for_interpretation is False

    # Strict callers fail closed instead of receiving a diagnostic-only verdict.
    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        predictor.predict_research_only(
            deepcopy(dict(trained_bundle.record)),
            lime_config=LimeConfig(num_perturbations=192, seed=2468),
            lime_stability_seeds=None,
            lime_require_acceptable_quality=True,
        )
    assert exc_info.value.code == "lime_quality_not_acceptable"

    # A deliberately incompatible LIME target is refused by the combined path.
    incompatible_target = (
        "raw_model_log_odds"
        if result.model_family == "l2_logistic_regression"
        else "calibrated_log_odds"
    )
    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        predictor.predict_research_only(
            payload,
            lime_config=LimeConfig(num_perturbations=96, seed=2468),
            lime_target=incompatible_target,
        )
    assert exc_info.value.code == "incompatible_explanation_scales"

    # Without LIME the result shape stays backward compatible.
    plain = predictor.predict_research_only(payload)
    assert plain.lime_explanation is None
    assert plain.to_dict()["lime_explanation"] is None


def test_lime_cli_predict_flag_and_flag_misuse(
    trained_bundle: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from ai.cli import main as cli_main

    common = [
        "predict",
        "--bundle-dir",
        str(trained_bundle.bundle_dir),
        "--trusted-root",
        str(trained_bundle.trusted_root),
        "--signing-key-path",
        str(trained_bundle.key_path),
        "--input",
        str(REPO_ROOT / "ai" / "examples" / "synthetic_da_a2_resting_labs_v1.json"),
        "--format",
        "json",
    ]
    assert cli_main([*common, "--with-lime", "--lime-seed", "777", "--lime-perturbations", "128"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["cli"]["lime_requested"] is True
    assert payload["cli"]["lime_stability_assessed"] is True
    lime = payload["lime_explanation"]
    assert lime["is_exact"] is False
    assert lime["sampling"]["seed"] == 777
    assert lime["sampling"]["num_perturbations"] == 128
    assert lime["explained_quantity"] == payload["explanation"]["explained_quantity"]
    assert payload["explanation_comparability"]["comparable"] is True
    assert lime["reference"]["scheme"] == "fixed_background_reference"
    quality = lime["quality"]
    assert quality["status"] == payload["cli"]["lime_quality_status"]
    assert quality["is_reliable_for_interpretation"] is payload["cli"][
        "lime_reliable_for_interpretation"
    ]
    assert quality["stability_summary"]["seeds"] == [20261026, 20261027, 20261028]
    assert quality["warnings"]
    assert quality["policy_sha256"]
    if not quality["is_reliable_for_interpretation"]:
        assert "DO NOT RELY" in quality["interpretation_guard"]

    # Text rendering surfaces the verdict and, when unreliable, the guard.
    assert cli_main(
        [
            *common[:-2],
            "--format",
            "text",
            "--with-lime",
            "--lime-seed",
            "777",
            "--lime-perturbations",
            "128",
        ]
    ) == 0
    text = capsys.readouterr().out
    assert f"quality status: {payload['cli']['lime_quality_status']}" in text
    if not payload["cli"]["lime_reliable_for_interpretation"]:
        assert "DO NOT RELY ON THESE FEATURE WEIGHTS" in text

    # Explicitly skipping stability leaves the verdict unverified.
    assert cli_main([*common, "--with-lime", "--lime-no-stability"]) == 0
    unverified = json.loads(capsys.readouterr().out)
    assert unverified["cli"]["lime_stability_assessed"] is False
    assert unverified["lime_explanation"]["quality"]["status"] == (
        "UNVERIFIED_STABILITY"
    )
    assert unverified["lime_explanation"]["quality"]["stability_summary"] is None

    # The sampled reference scheme is selectable and recorded in the payload.
    assert cli_main(
        [*common, "--with-lime", "--lime-reference-scheme", "sampled_background_marginals"]
    ) == 0
    sampled = json.loads(capsys.readouterr().out)
    assert sampled["lime_explanation"]["reference"]["scheme"] == (
        "sampled_background_marginals"
    )

    assert cli_main([*common, "--lime-seed", "777"]) == 2
    error = json.loads(capsys.readouterr().err)["error"]
    assert error["code"] == "cli_lime_flags_require_with_lime"

    assert cli_main([*common, "--lime-no-stability"]) == 2
    error = json.loads(capsys.readouterr().err)["error"]
    assert error["code"] == "cli_lime_flags_require_with_lime"

    assert cli_main([*common, "--with-lime", "--lime-perturbations", "4"]) == 2
    error = json.loads(capsys.readouterr().err)["error"]
    assert error["code"] == "lime_invalid_config"


# --------------------------------------------------------------------------- #
# 7. Source-level safety guards
# --------------------------------------------------------------------------- #


def test_lime_module_is_pure_python_without_external_lime_dependency() -> None:
    source = (REPO_ROOT / "ai" / "lime_explainability.py").read_text(encoding="utf-8")
    assert "import lime" not in source
    assert "from lime" not in source
    assert "backend" not in source
    for banned in ("requests", "urllib.request", "http.client", "socket"):
        assert banned not in source
    from ai.training import EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1

    assert EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1  # profile remains registered
    assert EXECUTION_PROFILE_AI1_GENERIC_V1
    # LIME never mutates or re-fits the estimator / preprocessor.
    assert ".fit(" not in source
