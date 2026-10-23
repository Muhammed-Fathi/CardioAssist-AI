"""Nested-CV, preprocessing, metrics and negative-control tests on synthetic fixtures."""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from research.experiments.config import DEFAULT_CONFIG
from research.experiments.data_adapter import ClevelandDataset
from research.experiments.errors import EvaluationError, SourceFormatError
from research.experiments.evaluation import (
    MODEL_NAMES,
    build_nested_split_plan,
    calculate_metrics,
    choose_model_family,
    _run_label_shuffle_negative_control,
    _run_nested_cv,
)
from research.experiments.models import build_family_estimator
from research.experiments.synthetic_fixtures import make_synthetic_dataset


def _small_config():
    return replace(
        DEFAULT_CONFIG,
        outer_folds=2,
        inner_folds=2,
        outer_repeat_seeds=(42,),
        rf_n_estimators=12,
        rf_max_depths=(3,),
        rf_min_samples_leaf=(5,),
        negative_control_seeds=(83,),
        negative_control_outer_repeats=1,
    )


def test_preprocessing_medians_and_categories_are_fitted_on_training_rows_only() -> None:
    X_train = np.asarray([
        [10.0, 0.0, 1.0, 100.0, 0.0],
        [20.0, 1.0, 2.0, 120.0, 1.0],
        [30.0, 0.0, 3.0, 130.0, 2.0],
        [40.0, 1.0, 4.0, 140.0, 0.0],
        [np.nan, 0.0, 2.0, np.nan, 1.0],
        [60.0, 1.0, 3.0, 160.0, 2.0],
    ])
    y_train = np.asarray([0, 0, 0, 1, 1, 1], dtype=np.int8)
    holdout = np.asarray([[1_000_000.0, 1.0, 4.0, 2_000_000.0, 2.0]])
    original_train = X_train.copy()
    original_holdout = holdout.copy()

    pipeline = build_family_estimator("l2_logistic_regression", random_state=7)
    pipeline.fit(X_train, y_train)
    preprocessing = pipeline.named_steps["preprocess"]
    numeric = preprocessing.named_transformers_["numeric"]
    medians = numeric.named_steps["imputer"].statistics_
    np.testing.assert_allclose(medians, np.asarray([30.0, 130.0]))

    # Transforming an extreme assessment row cannot change train-fit medians.
    preprocessing.transform(holdout)
    np.testing.assert_allclose(numeric.named_steps["imputer"].statistics_, [30.0, 130.0])
    np.testing.assert_array_equal(X_train, original_train)
    np.testing.assert_array_equal(holdout, original_holdout)
    encoder = preprocessing.named_transformers_["categorical"].named_steps["one_hot"]
    assert [tuple(values.astype(int)) for values in encoder.categories_] == [(0, 1), (1, 2, 3, 4), (0, 1, 2)]
    assert encoder.drop_idx_.tolist() == [0, 0, 0]


def test_all_missing_training_fold_feature_fails_instead_of_zero_imputation() -> None:
    X = np.asarray([
        [np.nan, 0, 1, 100, 0],
        [np.nan, 1, 2, 120, 1],
        [np.nan, 0, 3, 130, 2],
        [np.nan, 1, 4, 140, 0],
    ], dtype=np.float64)
    y = np.asarray([0, 0, 1, 1], dtype=np.int8)
    pipeline = build_family_estimator("l2_logistic_regression", random_state=1)
    with pytest.raises(ValueError, match="no observed values"):
        pipeline.fit(X, y)


def test_nested_split_plan_proves_outer_and_inner_separation() -> None:
    dataset = make_synthetic_dataset(seed=100)
    config = _small_config()
    plans = build_nested_split_plan(dataset.y, repeat_seed=42, config=config)
    assert len(plans) == config.outer_folds
    assessments: list[int] = []
    for fold in plans:
        outer_train = set(fold.outer_train_indices.tolist())
        outer_assessment = set(fold.outer_assessment_indices.tolist())
        assert outer_train.isdisjoint(outer_assessment)
        assessments.extend(outer_assessment)
        assert len(fold.inner_splits) == config.inner_folds
        for inner_train_local, inner_assessment_local in fold.inner_splits:
            inner_train_global = set(fold.outer_train_indices[inner_train_local].tolist())
            inner_assessment_global = set(fold.outer_train_indices[inner_assessment_local].tolist())
            assert inner_train_global.isdisjoint(inner_assessment_global)
            assert inner_train_global <= outer_train
            assert inner_assessment_global <= outer_train
            assert inner_train_global.isdisjoint(outer_assessment)
            assert inner_assessment_global.isdisjoint(outer_assessment)
    assert sorted(assessments) == list(range(dataset.row_count))


def test_l2_simplicity_preference_applies_only_within_prespecified_tolerance() -> None:
    assert choose_model_family({"l2_logistic_regression": 0.80, "constrained_random_forest": 0.81}) == "l2_logistic_regression"
    assert choose_model_family({"l2_logistic_regression": 0.80, "constrained_random_forest": 0.8111}) == "constrained_random_forest"
    assert choose_model_family({"l2_logistic_regression": 0.84, "constrained_random_forest": 0.81}) == "l2_logistic_regression"
    with pytest.raises(EvaluationError):
        choose_model_family({"l2_logistic_regression": 0.8})


def test_metrics_have_fixed_threshold_confusion_matrix_and_calibration_diagnostics() -> None:
    y = np.asarray([0, 0, 1, 1], dtype=np.int8)
    probabilities = np.asarray([0.1, 0.4, 0.35, 0.9], dtype=np.float64)
    metrics = calculate_metrics(y, probabilities)
    assert metrics["roc_auc"] == pytest.approx(0.75)
    assert metrics["accuracy_at_0_5_exploratory"] == pytest.approx(0.75)
    assert metrics["sensitivity_at_0_5_exploratory"] == pytest.approx(0.5)
    assert metrics["specificity_at_0_5_exploratory"] == pytest.approx(1.0)
    assert metrics["confusion_matrix_at_0_5_exploratory"]["matrix"] == [[2, 0], [1, 1]]
    assert 0 <= metrics["average_precision"] <= 1
    assert 0 <= metrics["brier_score"] <= 1
    calibration = metrics["calibration"]
    assert "calibration_in_the_large_intercept" in calibration
    assert "calibration_slope" in calibration
    assert calibration["diagnostics_used_for_fitting_or_threshold_selection"] is False
    assert calibration["quantile_reliability_curve_status"] == "NOT_ESTIMABLE_INSUFFICIENT_OR_SINGLE_CLASS"

    calibration_y = np.asarray([0, 1] * 6, dtype=np.int8)
    calibration_p = np.linspace(0.1, 0.9, 12)
    calibrated_diagnostics = calculate_metrics(calibration_y, calibration_p)["calibration"]
    assert sum(item["n"] for item in calibrated_diagnostics["quantile_reliability_curve"]) == 12
    assert calibrated_diagnostics["quantile_reliability_curve_status"] == "DESCRIPTIVE_OOF_AGGREGATES"


def test_nested_cv_and_label_shuffle_are_deterministic_and_use_all_models() -> None:
    config = _small_config()
    dataset = make_synthetic_dataset(seed=700)
    original_X = dataset.X.copy()
    original_y = dataset.y.copy()

    first = _run_nested_cv(dataset, config=config)
    second = _run_nested_cv(dataset, config=config)
    assert first.repeat_results[0].metrics == second.repeat_results[0].metrics
    assert first.repeat_results[0].fold_records == second.repeat_results[0].fold_records
    for model in MODEL_NAMES:
        np.testing.assert_array_equal(
            first.repeat_results[0].predictions[model],
            second.repeat_results[0].predictions[model],
        )
        assert first.repeat_results[0].metrics[model]["n_assessment_predictions"] == 303
    assert [fold["selected_family"] for fold in first.repeat_results[0].fold_records]
    np.testing.assert_array_equal(dataset.X, original_X)
    np.testing.assert_array_equal(dataset.y, original_y)

    null_first = _run_label_shuffle_negative_control(dataset, config=config)
    null_second = _run_label_shuffle_negative_control(dataset, config=config)
    assert null_first.summary == null_second.summary
    assert null_first.per_shuffle == null_second.per_shuffle
    assert null_first.interpretation == "SMOKE_TEST_NOT_FORMAL_PERMUTATION_P_VALUE"
    assert null_first.summary["shuffle_count"] == 1
    assert null_first.summary["no_p_value_or_independent_sample_claim"] is True
    assert null_first.per_shuffle[0]["true_labels_passed_to_nested_selection_or_scoring"] is False
    np.testing.assert_array_equal(dataset.X, original_X)
    np.testing.assert_array_equal(dataset.y, original_y)


def test_model_selection_does_not_accept_dummy_or_unregistered_family_as_tunable() -> None:
    from research.experiments.models import family_parameter_grid

    with pytest.raises(ValueError):
        family_parameter_grid("prevalence_dummy")
    with pytest.raises(ValueError):
        family_parameter_grid("unregistered_model")


def test_dataset_constructor_rejects_extra_or_leakage_columns() -> None:
    dataset = make_synthetic_dataset(seed=9)
    with pytest.raises(SourceFormatError):
        ClevelandDataset(
            X=np.column_stack([dataset.X, np.zeros(dataset.row_count)]),
            y=dataset.y.copy(),
            feature_names=(*DEFAULT_CONFIG.feature_names, "num"),
            row_count=dataset.row_count,
            binary_target_counts=dataset.binary_target_counts,
        )
