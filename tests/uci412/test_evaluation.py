"""Nested-CV, metrics, uncertainty, negative-control, and leakage tests."""
from __future__ import annotations

import math
from types import SimpleNamespace

import numpy as np
import pytest

from research.uci412 import evaluation
from research.uci412.errors import EvaluationError
from research.uci412.models import MODEL_FAMILIES
from research.uci412.evaluation import (
    MODEL_NAMES,
    assess_label_permutation_sanity,
    assert_no_target_leakage,
    bootstrap_metric_ci,
    calculate_metrics,
    choose_model_family,
    derive_bootstrap_seed,
    derive_inner_seed,
    derive_model_seed,
    nested_result_to_report,
    plan_inner_folds,
    plan_outer_folds,
    run_label_shuffle_negative_control,
    run_nested_cv,
)

from tests.uci412.conftest import make_dataset, small_config


@pytest.fixture(scope="module")
def nested_result():
    config = small_config()
    dataset = make_dataset(config)
    return config, run_nested_cv(dataset, config=config)


def test_seed_derivation_is_fixed_and_repeatable() -> None:
    assert derive_inner_seed(20261024, 1) == 20261024 + 211 + 1013
    assert derive_model_seed(20261024, 1, "l2_logistic_regression") == 20261024 + 200003 + 131 + 17
    assert derive_model_seed(20261024, 1, "constrained_random_forest") == 20261024 + 200003 + 131 + 29
    assert derive_bootstrap_seed(20261024) == 20261024 + 500009
    with pytest.raises(EvaluationError):
        derive_model_seed(20261024, 1, "gradient_boosting_reserved")
    with pytest.raises(ValueError):
        derive_inner_seed(20261024, 0)


def test_outer_folds_partition_every_row_once_and_respect_stratification() -> None:
    config = small_config()
    dataset = make_dataset(config)
    for seed in config.outer_repeat_seeds:
        folds = plan_outer_folds(dataset.y, seed, config)
        assert len(folds) == config.outer_folds
        covered = np.concatenate([test for _, test in folds])
        assert sorted(covered.tolist()) == list(range(dataset.row_count))
        for train, test in folds:
            assert set(train.tolist()).isdisjoint(test.tolist())
            assert 0 < np.count_nonzero(dataset.y[test] == 1) < len(test)
            assert 0 < np.count_nonzero(dataset.y[train] == 0)


def test_inner_folds_stay_inside_the_outer_training_rows() -> None:
    config = small_config()
    dataset = make_dataset(config)
    outer = plan_outer_folds(dataset.y, config.outer_repeat_seeds[0], config)[0]
    train_index, _ = outer
    inner = plan_inner_folds(dataset.y[train_index], config.outer_repeat_seeds[0], 1, config)
    assert len(inner) == config.inner_folds
    for inner_train, inner_test in inner:
        assert inner_train.max() < len(train_index)
        assert inner_test.max() < len(train_index)
        assert set(inner_train.tolist()).isdisjoint(inner_test.tolist())
    covered = np.concatenate([test for _, test in inner])
    assert sorted(covered.tolist()) == list(range(len(train_index)))


def test_nested_cv_uses_inner_folds_only_for_hyperparameters(monkeypatch) -> None:
    config = small_config()
    dataset = make_dataset(config)
    observed: list[tuple[int, int]] = []
    real_grid_search = evaluation.GridSearchCV

    class Spy(real_grid_search):  # type: ignore[misc, valid-type]
        def fit(self, X, y, **kwargs):
            observed.append((int(np.asarray(X).shape[0]), int(np.asarray(y).shape[0])))
            return super().fit(X, y, **kwargs)

    monkeypatch.setattr(evaluation, "GridSearchCV", Spy)
    run_nested_cv(dataset, config=config, repeat_seeds=(config.outer_repeat_seeds[0],))
    assert observed
    assert all(rows < dataset.row_count for rows, _ in observed)
    # Every outer fold contributes one search per registered family.
    assert len(observed) == config.outer_folds * len(evaluation.MODEL_FAMILIES)


def test_hyperparameter_grid_passed_to_the_search_is_the_registered_grid(monkeypatch) -> None:
    config = small_config()
    dataset = make_dataset(config)
    grids: list[dict] = []
    real_grid_search = evaluation.GridSearchCV

    class Spy(real_grid_search):  # type: ignore[misc, valid-type]
        def __init__(self, estimator, param_grid, **kwargs):
            grids.append(dict(param_grid))
            super().__init__(estimator, param_grid, **kwargs)

    monkeypatch.setattr(evaluation, "GridSearchCV", Spy)
    run_nested_cv(dataset, config=config, repeat_seeds=(config.outer_repeat_seeds[0],))
    assert {"classifier__C": list(config.logistic_c_values)} in grids
    assert {
        "classifier__max_depth": list(config.rf_max_depths),
        "classifier__min_samples_leaf": list(config.rf_min_samples_leaf),
    } in grids


def test_nested_cv_is_bitwise_deterministic() -> None:
    config = small_config()
    dataset = make_dataset(config)
    first = run_nested_cv(dataset, config=config, repeat_seeds=(config.outer_repeat_seeds[0],))
    second = run_nested_cv(dataset, config=config, repeat_seeds=(config.outer_repeat_seeds[0],))
    for model_name in MODEL_NAMES:
        assert first.repeat_results[0].metrics[model_name]["roc_auc"] == pytest.approx(
            second.repeat_results[0].metrics[model_name]["roc_auc"], rel=0, abs=0
        )
        assert np.array_equal(
            first.repeat_results[0].predictions[model_name],
            second.repeat_results[0].predictions[model_name],
        )


def test_each_repeat_assigns_every_row_exactly_once(nested_result) -> None:
    config, result = nested_result
    assert result.row_count == 303
    assert len(result.repeat_results) == len(config.outer_repeat_seeds)
    for repeat in result.repeat_results:
        assert len(repeat.fold_records) == config.outer_folds
        total = sum(record["n_outer_assessment"] for record in repeat.fold_records)
        assert total == result.row_count


def test_selected_model_is_one_of_the_registered_families(nested_result) -> None:
    _, result = nested_result
    for repeat in result.repeat_results:
        for record in repeat.fold_records:
            assert record["selected_family"] in MODEL_FAMILIES
            assert record["selection_rule"]


def test_predictions_are_read_only_score_arrays(nested_result) -> None:
    _, result = nested_result
    for repeat in result.repeat_results:
        for model_name in MODEL_NAMES:
            scores = repeat.predictions[model_name]
            assert scores.shape == (303,)
            assert np.isfinite(scores).all()
            assert scores.min() >= 0.0 and scores.max() <= 1.0
            with pytest.raises(ValueError):
                scores[0] = 0.5


def test_dummy_scores_are_constant_within_each_fold(nested_result) -> None:
    config, result = nested_result
    for repeat in result.repeat_results:
        folds = plan_outer_folds(result and make_dataset(config).y, repeat.outer_repeat_seed, config)
        scores = repeat.predictions["prevalence_dummy"]
        for _, test_index in folds:
            assert np.unique(scores[test_index]).size == 1


def test_metrics_include_the_registered_set_and_calibration() -> None:
    config = small_config()
    rng = np.random.default_rng(11)
    y = np.array([0] * 60 + [1] * 40)
    p = np.clip(rng.beta(2, 2, size=100) * 0.5 + 0.25 * y, 0, 1)
    metrics = calculate_metrics(y, p, config=config)
    assert {"roc_auc", "average_precision", "brier_score"}.issubset(metrics)
    assert "sensitivity_at_0_5_exploratory" in metrics
    assert "specificity_at_0_5_exploratory" in metrics
    assert metrics["threshold"] == 0.5
    assert metrics["threshold_tuned_on_assessment_or_external_data"] is False
    assert set(metrics["confusion_matrix_at_0_5"]) == {
        "true_negative",
        "false_positive",
        "false_negative",
        "true_positive",
    }
    assert metrics["calibration"]["diagnostic_status"] == "DESCRIPTIVE_ONLY_NO_RECALIBRATION"
    with pytest.raises(EvaluationError):
        calculate_metrics(np.zeros(10), np.zeros(10), config=config)


def test_calibration_status_marks_descriptive_only() -> None:
    config = small_config()
    y = np.array([0] * 50 + [1] * 50)
    p = np.concatenate([np.linspace(0.05, 0.45, 50), np.linspace(0.55, 0.95, 50)])
    calibration = calculate_metrics(y, p, config=config)["calibration"]
    assert calibration["descriptive_only"] is True
    assert calibration["applied_to_predictions"] is False
    assert calibration["diagnostics_used_for_fitting_or_threshold_selection"] is False
    assert len(calibration["quantile_reliability_curve"]) == config.calibration_bins


def test_bootstrap_ci_is_deterministic_and_conditional() -> None:
    rng = np.random.default_rng(3)
    y = np.array([0] * 87 + [1] * 216)
    p = np.clip(0.2 + 0.5 * y + rng.normal(0, 0.15, size=y.size), 0.01, 0.99)
    first = bootstrap_metric_ci(y, p, seed=500001, config=small_config())
    second = bootstrap_metric_ci(y, p, seed=500001, config=small_config())
    assert first == second
    assert first["status"] == "ESTIMATED_CONDITIONAL_ON_FIXED_FOLD_FITS"
    assert first["roc_auc_ci_95"][0] <= first["roc_auc_ci_95"][1]
    assert "future patients" in first["interpretation"]


def test_model_family_selection_prefers_logistic_within_tolerance() -> None:
    assert choose_model_family(
        {"l2_logistic_regression": 0.800, "constrained_random_forest": 0.805}
    ) == "l2_logistic_regression"
    assert choose_model_family(
        {"l2_logistic_regression": 0.800, "constrained_random_forest": 0.850}
    ) == "constrained_random_forest"
    with pytest.raises(EvaluationError):
        choose_model_family({"l2_logistic_regression": 0.8})
    with pytest.raises(EvaluationError):
        choose_model_family(
            {"l2_logistic_regression": math.nan, "constrained_random_forest": 0.8}
        )


def test_negative_control_is_deterministic_and_near_chance() -> None:
    config = small_config()
    dataset = make_dataset(config)
    first = run_label_shuffle_negative_control(dataset, config=config)
    second = run_label_shuffle_negative_control(dataset, config=config)
    assert first.summary == second.summary
    assert first.shuffle_seeds == config.negative_control_seeds
    assert 0.0 <= first.summary["selected_procedure_roc_auc_mean"] <= 1.0
    assert first.summary["interpretation"] == "SMOKE_TEST_NOT_FORMAL_PERMUTATION_P_VALUE"
    assert first.summary["leakage_assessment"]["blocking"] is False
    for record in first.per_shuffle:
        assert record["true_labels_passed_to_nested_selection_or_scoring"] is False


def test_permuted_label_anomaly_is_treated_as_a_leakage_alarm() -> None:
    alarm = assess_label_permutation_sanity((0.5, 0.93))
    assert alarm["blocking"] is True
    assert alarm["status"].startswith("LEAKAGE_ALARM")
    warning = assess_label_permutation_sanity((0.5, 0.75))
    assert warning["blocking"] is False
    assert warning["status"].startswith("WARNING")
    clean = assess_label_permutation_sanity((0.48, 0.55))
    assert clean["status"].startswith("CONSISTENT")
    with pytest.raises(EvaluationError):
        run_label_shuffle_negative_control(
            SimpleNamespace(X=None, y=None, feature_names=(), row_count=0, class_counts=()),
            config=small_config(),
        )


def test_leakage_precondition_checks_pass_on_the_synthetic_dataset() -> None:
    config = small_config()
    dataset = make_dataset(config)
    checks = assert_no_target_leakage(dataset, config=config)
    assert all(checks.values())
    assert checks["target_column_not_in_features"] is True


def test_leakage_precondition_rejects_the_target_as_a_feature() -> None:
    config = small_config()
    dataset = make_dataset(config)
    fake = SimpleNamespace(
        X=dataset.X,
        y=dataset.y,
        feature_names=("Cath",) + tuple(dataset.feature_names[1:]),
        row_count=dataset.row_count,
        class_counts=dataset.class_counts,
    )
    with pytest.raises(EvaluationError, match="feature_names_equal_registered_panel"):
        assert_no_target_leakage(fake, config=config)


def test_report_never_contains_row_scores(nested_result) -> None:
    _, result = nested_result
    report = nested_result_to_report(result)
    assert report["independent_external_validation_performed"] is False
    assert "predictions" not in report
    assert len(str(report)) < 200_000
    serialized = str(report)
    assert "0.123456789" not in serialized
    first_repeat = report["per_repeat_metrics"][0]
    assert first_repeat["outer_repeat_seed"] == result.repeat_results[0].outer_repeat_seed


def test_report_summary_is_descriptive_only(nested_result) -> None:
    _, result = nested_result
    summary = nested_result_to_report(result)["descriptive_summary_across_repeats"]
    for model_name in MODEL_NAMES:
        entry = summary[model_name]["roc_auc"]
        assert entry["interpretation"] == "DESCRIPTIVE_ONLY_SAME_SOURCE_ROWS_REUSED_NO_CI"
        assert entry["repeat_count"] == len(result.repeat_results)
