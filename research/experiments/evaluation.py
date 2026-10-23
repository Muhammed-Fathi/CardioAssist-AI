"""Nested stratified CV, inner model selection, metrics, and label-shuffle smoke test."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping, Sequence

import numpy as np
from scipy.optimize import brentq, minimize
from scipy.special import expit
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    roc_auc_score,
)
from sklearn.model_selection import GridSearchCV, StratifiedKFold
from threadpoolctl import threadpool_limits

from research.experiments.config import DEFAULT_CONFIG, ExperimentConfig
from research.experiments.data_adapter import ClevelandDataset
from research.experiments.errors import EvaluationError
from research.experiments.models import (
    MODEL_FAMILIES,
    build_family_estimator,
    family_parameter_grid,
    make_prevalence_dummy,
)

MODEL_NAMES = (
    "prevalence_dummy",
    "l2_logistic_regression",
    "constrained_random_forest",
    "inner_selected_procedure",
)


@dataclass(frozen=True, slots=True)
class RepeatResult:
    """One OOF prediction per source row for one outer-CV repeat."""

    outer_repeat_seed: int
    metrics: Mapping[str, Mapping[str, Any]]
    predictions: Mapping[str, np.ndarray]
    fold_records: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True, slots=True)
class NestedCVResult:
    """Repeated nested-CV output; predictions are sensitive and remain in memory/local storage."""

    repeat_results: tuple[RepeatResult, ...]
    row_count: int
    positive_count: int
    negative_count: int
    model_names: tuple[str, ...] = MODEL_NAMES


@dataclass(frozen=True, slots=True)
class OuterFoldSplit:
    """Index-only fold plan; inner indices are relative to outer-training data."""

    fold_number: int
    outer_train_indices: np.ndarray
    outer_assessment_indices: np.ndarray
    inner_seed: int
    inner_splits: tuple[tuple[np.ndarray, np.ndarray], ...]


@dataclass(frozen=True, slots=True)
class NegativeControlResult:
    """Aggregate-only label-shuffle smoke-test output."""

    shuffle_seeds: tuple[int, ...]
    per_shuffle: tuple[Mapping[str, Any], ...]
    summary: Mapping[str, Any]
    interpretation: str = "SMOKE_TEST_NOT_FORMAL_PERMUTATION_P_VALUE"


def _validate_binary_inputs(
    X: np.ndarray,
    y: np.ndarray,
    config: ExperimentConfig,
) -> tuple[np.ndarray, np.ndarray]:
    if not isinstance(X, np.ndarray) or X.ndim != 2:
        raise EvaluationError("Evaluation requires a two-dimensional numeric feature matrix.")
    if X.shape[1] != len(config.feature_names):
        raise EvaluationError("Evaluation received a feature count outside the fixed allowlist.")
    if not isinstance(y, np.ndarray) or y.ndim != 1 or y.shape[0] != X.shape[0]:
        raise EvaluationError("Evaluation target shape does not match the feature matrix.")
    if X.shape[0] < config.outer_folds:
        raise EvaluationError("Too few rows for the registered outer stratified folds.")
    if not np.isfinite(X[~np.isnan(X)]).all():
        raise EvaluationError("Evaluation features contain a non-finite observed value.")
    if not np.isin(y, (0, 1)).all():
        raise EvaluationError("Evaluation target must contain only mapped binary labels 0 and 1.")
    unique, counts = np.unique(y, return_counts=True)
    if tuple(unique.tolist()) != (0, 1):
        raise EvaluationError("Both binary target classes must be present for nested stratification.")
    if int(counts.min()) < config.outer_folds:
        raise EvaluationError("A class has too few observations for the registered outer folds.")
    return X, y


def derive_inner_seed(outer_seed: int, outer_fold_number: int, config: ExperimentConfig) -> int:
    if outer_fold_number <= 0:
        raise ValueError("Outer fold numbers are one-based.")
    return int(outer_seed + config.inner_seed_offset + config.inner_fold_multiplier * outer_fold_number)


def derive_model_seed(
    outer_seed: int,
    outer_fold_number: int,
    family: str,
    config: ExperimentConfig,
) -> int:
    if outer_fold_number <= 0:
        raise ValueError("Outer fold numbers are one-based.")
    if family == "l2_logistic_regression":
        family_offset = config.logistic_seed_offset
    elif family == "constrained_random_forest":
        family_offset = config.forest_seed_offset
    else:
        raise ValueError("Only the registered model families have fit seeds.")
    seed = (
        outer_seed
        + config.model_seed_offset
        + config.model_fold_multiplier * outer_fold_number
        + family_offset
    )
    return int(seed % (2**32 - 1))


def choose_model_family(
    inner_auc_by_family: Mapping[str, float],
    *,
    tolerance: float = DEFAULT_CONFIG.auc_equivalence_tolerance,
) -> str:
    """Apply the prespecified LR simplicity preference within the AUC tolerance."""
    if set(inner_auc_by_family) != set(MODEL_FAMILIES):
        raise EvaluationError("Inner selection must compare exactly both registered model families.")
    lr_score = float(inner_auc_by_family["l2_logistic_regression"])
    rf_score = float(inner_auc_by_family["constrained_random_forest"])
    if not (math.isfinite(lr_score) and math.isfinite(rf_score)):
        raise EvaluationError("Inner-CV model-selection score is not finite.")
    best_score = max(lr_score, rf_score)
    if best_score - lr_score <= tolerance + 1e-12:
        return "l2_logistic_regression"
    return "constrained_random_forest"


def _positive_probability(estimator: Any, X: np.ndarray) -> np.ndarray:
    probabilities = estimator.predict_proba(X)
    classes = np.asarray(estimator.classes_)
    locations = np.flatnonzero(classes == 1)
    if len(locations) != 1:
        raise EvaluationError("Fitted estimator does not expose exactly one positive-class probability.")
    values = np.asarray(probabilities[:, int(locations[0])], dtype=np.float64)
    if values.shape != (X.shape[0],) or not np.isfinite(values).all():
        raise EvaluationError("Estimator produced invalid assessment-fold probabilities.")
    if np.any((values < 0.0) | (values > 1.0)):
        raise EvaluationError("Estimator produced probabilities outside [0, 1].")
    return values


def _safe_calibration_diagnostics(
    y_true: np.ndarray,
    probabilities: np.ndarray,
    *,
    n_bins: int,
) -> dict[str, Any]:
    """Describe OOF calibration; diagnostics never recalibrate or alter predictions."""
    y = np.asarray(y_true, dtype=np.float64)
    p = np.asarray(probabilities, dtype=np.float64)
    result: dict[str, Any] = {
        "calibration_in_the_large_intercept": None,
        "calibration_in_the_large_status": "NOT_ESTIMABLE",
        "calibration_slope": None,
        "calibration_intercept": None,
        "calibration_slope_status": "NOT_ESTIMABLE",
        "quantile_reliability_curve": [],
        "quantile_reliability_curve_status": "NOT_ESTIMABLE",
        "diagnostics_used_for_fitting_or_threshold_selection": False,
    }
    if y.size < 10 or np.unique(y).size != 2 or not np.isfinite(p).all():
        result["calibration_in_the_large_status"] = "NOT_ESTIMABLE_INSUFFICIENT_OR_SINGLE_CLASS"
        result["calibration_slope_status"] = "NOT_ESTIMABLE_INSUFFICIENT_OR_SINGLE_CLASS"
        result["quantile_reliability_curve_status"] = "NOT_ESTIMABLE_INSUFFICIENT_OR_SINGLE_CLASS"
        return result

    clipped = np.clip(p, 1e-12, 1.0 - 1e-12)
    logits = np.log(clipped) - np.log1p(-clipped)
    n_positive = float(np.sum(y))

    # Calibration-in-the-large is an intercept-only logistic update with the
    # OOF logit as an offset (slope held at 1), not a fitted prediction model.
    def intercept_equation(intercept: float) -> float:
        return float(np.sum(expit(logits + intercept)) - n_positive)

    try:
        intercept = brentq(intercept_equation, -40.0, 40.0, xtol=1e-12, rtol=1e-12)
        if math.isfinite(intercept):
            result["calibration_in_the_large_intercept"] = float(intercept)
            result["calibration_in_the_large_status"] = "ESTIMATED_DESCRIPTIVE_OOF_DIAGNOSTIC"
    except (ValueError, RuntimeError, OverflowError):
        result["calibration_in_the_large_status"] = "UNSTABLE_OR_NOT_ESTIMABLE"

    # A free intercept+slope recalibration fit is reported only as a diagnostic.
    # Constant scores or near-separation produce an explicit non-estimable status.
    design = np.column_stack((np.ones_like(logits), logits))
    if np.ptp(logits) <= 1e-10 or np.linalg.matrix_rank(design) < 2:
        result["calibration_slope_status"] = "NOT_ESTIMABLE_CONSTANT_OR_RANK_DEFICIENT_SCORES"
    else:
        def objective(beta: np.ndarray) -> tuple[float, np.ndarray]:
            linear = design @ beta
            loss = np.logaddexp(0.0, linear) - y * linear
            gradient = design.T @ (expit(linear) - y)
            return float(np.sum(loss)), gradient.astype(np.float64)

        try:
            fit = minimize(
                lambda beta: objective(beta)[0],
                x0=np.asarray([0.0, 1.0], dtype=np.float64),
                jac=lambda beta: objective(beta)[1],
                method="BFGS",
                options={"gtol": 1e-8, "maxiter": 1000},
            )
            beta = np.asarray(fit.x, dtype=np.float64)
            if (
                fit.success
                and beta.shape == (2,)
                and np.isfinite(beta).all()
                and np.max(np.abs(beta)) < 15.0
            ):
                result["calibration_intercept"] = float(beta[0])
                result["calibration_slope"] = float(beta[1])
                result["calibration_slope_status"] = "ESTIMATED_DESCRIPTIVE_OOF_DIAGNOSTIC"
            else:
                result["calibration_slope_status"] = "UNSTABLE_OR_NOT_ESTIMABLE"
        except (ValueError, FloatingPointError, np.linalg.LinAlgError):
            result["calibration_slope_status"] = "UNSTABLE_OR_NOT_ESTIMABLE"

    # Quantile bins are aggregate-only and collapse repeated cut-points so a
    # constant baseline is represented as one bin rather than artificial bins.
    interior = np.quantile(p, np.linspace(0.0, 1.0, n_bins + 1)[1:-1])
    boundaries = np.unique(interior)
    assignments = np.searchsorted(boundaries, p, side="left")
    bins: list[dict[str, Any]] = []
    for bin_index in range(len(boundaries) + 1):
        mask = assignments == bin_index
        count = int(np.count_nonzero(mask))
        if count == 0:
            continue
        bins.append({
            "n": count,
            "mean_predicted_probability": float(np.mean(p[mask])),
            "observed_positive_fraction": float(np.mean(y[mask])),
        })
    result["quantile_reliability_curve"] = bins
    result["quantile_reliability_curve_status"] = (
        "DESCRIPTIVE_OOF_AGGREGATES" if bins else "NOT_ESTIMABLE"
    )
    return result


def calculate_metrics(
    y_true: np.ndarray,
    probabilities: np.ndarray,
    *,
    config: ExperimentConfig = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Compute the fixed exploratory metrics and calibration diagnostics."""
    y = np.asarray(y_true, dtype=np.int8)
    p = np.asarray(probabilities, dtype=np.float64)
    if y.ndim != 1 or p.shape != y.shape or y.size == 0:
        raise EvaluationError("Metric inputs have incompatible shapes.")
    if not np.isin(y, (0, 1)).all() or np.unique(y).size != 2:
        raise EvaluationError("Both mapped binary labels are required for the prespecified metrics.")
    if not np.isfinite(p).all() or np.any((p < 0.0) | (p > 1.0)):
        raise EvaluationError("Metric predictions must be finite probabilities in [0, 1].")
    predicted = (p >= config.threshold).astype(np.int8)
    matrix = confusion_matrix(y, predicted, labels=[0, 1])
    tn, fp, fn, tp = (int(matrix[0, 0]), int(matrix[0, 1]), int(matrix[1, 0]), int(matrix[1, 1]))
    n_negative = tn + fp
    n_positive = tp + fn
    if n_negative == 0 or n_positive == 0:
        raise EvaluationError("Both classes must be represented in each assessment repeat.")
    return {
        "n_assessment_predictions": int(y.size),
        "positive_prevalence": float(np.mean(y)),
        "roc_auc": float(roc_auc_score(y, p)),
        "average_precision": float(average_precision_score(y, p)),
        "accuracy_at_0_5_exploratory": float(accuracy_score(y, predicted)),
        "sensitivity_at_0_5_exploratory": float(tp / n_positive),
        "specificity_at_0_5_exploratory": float(tn / n_negative),
        "confusion_matrix_at_0_5_exploratory": {
            "labels": [0, 1],
            "layout": "[[true_negative, false_positive], [false_negative, true_positive]]",
            "matrix": [[tn, fp], [fn, tp]],
        },
        "brier_score": float(brier_score_loss(y, p)),
        "calibration": _safe_calibration_diagnostics(y, p, n_bins=config.calibration_bins),
        "threshold_definition": "positive_if_probability_greater_than_or_equal_to_0_5_exploratory_only",
    }


def _make_inner_splits(
    X_train: np.ndarray,
    y_train: np.ndarray,
    *,
    seed: int,
    n_splits: int,
) -> list[tuple[np.ndarray, np.ndarray]]:
    _, class_counts = np.unique(y_train, return_counts=True)
    if len(class_counts) != 2 or int(class_counts.min()) < n_splits:
        raise EvaluationError("Outer-training partition cannot support the registered inner stratification.")
    splitter = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    splits = list(splitter.split(X_train, y_train))
    for train_indices, assessment_indices in splits:
        if np.intersect1d(train_indices, assessment_indices).size:
            raise EvaluationError("Inner-CV training and assessment partitions overlap.")
        if not np.isin(assessment_indices, np.arange(X_train.shape[0])).all():
            raise EvaluationError("Inner-CV assessment partition escaped the outer-training partition.")
    return splits


def build_nested_split_plan(
    y: np.ndarray,
    *,
    repeat_seed: int,
    config: ExperimentConfig = DEFAULT_CONFIG,
) -> tuple[OuterFoldSplit, ...]:
    """Build and audit the exact nested split boundaries before model fitting.

    Inner indices are local to the outer-training subset; the explicit mapping
    check below proves that no outer-assessment row can enter model selection.
    """
    labels = np.asarray(y)
    if labels.ndim != 1 or not np.isin(labels, (0, 1)).all():
        raise EvaluationError("Nested split planning requires a one-dimensional binary target.")
    if np.unique(labels).size != 2:
        raise EvaluationError("Both target classes are required for stratified nested splits.")
    n_rows = labels.shape[0]
    splitter = StratifiedKFold(
        n_splits=config.outer_folds,
        shuffle=True,
        random_state=int(repeat_seed),
    )
    all_rows = np.arange(n_rows, dtype=np.int64)
    assignment_counts = np.zeros(n_rows, dtype=np.int8)
    fold_plans: list[OuterFoldSplit] = []
    for fold_number, (outer_train, outer_assessment) in enumerate(
        splitter.split(all_rows.reshape(-1, 1), labels), start=1
    ):
        if np.intersect1d(outer_train, outer_assessment).size:
            raise EvaluationError("Outer-CV training and assessment partitions overlap.")
        if np.any(assignment_counts[outer_assessment] != 0):
            raise EvaluationError("An observation appears in multiple outer assessment folds per repeat.")
        assignment_counts[outer_assessment] += 1
        inner_seed = derive_inner_seed(repeat_seed, fold_number, config)
        inner_splits = _make_inner_splits(
            all_rows[outer_train].reshape(-1, 1),
            labels[outer_train],
            seed=inner_seed,
            n_splits=config.inner_folds,
        )
        for inner_train_local, inner_assessment_local in inner_splits:
            inner_train_global = outer_train[inner_train_local]
            inner_assessment_global = outer_train[inner_assessment_local]
            if np.intersect1d(inner_train_global, inner_assessment_global).size:
                raise EvaluationError("Inner-CV training and assessment partitions overlap.")
            if np.intersect1d(inner_train_global, outer_assessment).size or np.intersect1d(
                inner_assessment_global, outer_assessment
            ).size:
                raise EvaluationError("An outer assessment row leaked into inner model selection.")
        fold_plans.append(OuterFoldSplit(
            fold_number=fold_number,
            outer_train_indices=np.asarray(outer_train, dtype=np.int64),
            outer_assessment_indices=np.asarray(outer_assessment, dtype=np.int64),
            inner_seed=inner_seed,
            inner_splits=tuple(inner_splits),
        ))
    if not np.all(assignment_counts == 1):
        raise EvaluationError("Outer assessment folds do not cover every observation exactly once.")
    return tuple(fold_plans)


def _search_family(
    family: str,
    X_train: np.ndarray,
    y_train: np.ndarray,
    inner_splits: Sequence[tuple[np.ndarray, np.ndarray]],
    *,
    random_state: int,
    config: ExperimentConfig,
) -> GridSearchCV:
    search = GridSearchCV(
        estimator=build_family_estimator(family, random_state=random_state, config=config),
        param_grid=family_parameter_grid(family, config=config),
        scoring="roc_auc",
        cv=list(inner_splits),
        refit=True,
        n_jobs=1,
        error_score="raise",
        return_train_score=False,
        verbose=0,
    )
    search.fit(X_train, y_train)
    if not math.isfinite(float(search.best_score_)):
        raise EvaluationError("Inner-CV selection returned a non-finite ROC-AUC.")
    return search


def _run_nested_cv(
    dataset: ClevelandDataset,
    *,
    config: ExperimentConfig = DEFAULT_CONFIG,
    repeat_seeds: Sequence[int] | None = None,
) -> NestedCVResult:
    """Run repeated outer evaluation with all selection confined to outer training.

    For each outer fold, both model families and all fixed hyperparameters are
    selected by inner stratified CV. Preprocessing lives inside each sklearn
    Pipeline, so imputation, scaling, and one-hot transforms are learned only
    from the corresponding inner-training split. The selected procedure's
    outer score reuses its already-computed family prediction; no second fit or
    evaluation-fold tuning occurs.
    """
    if dataset.feature_names != config.feature_names:
        raise EvaluationError("Dataset columns do not match the registered predictor allowlist.")
    X, y = _validate_binary_inputs(dataset.X, dataset.y, config)
    seeds = tuple(config.outer_repeat_seeds if repeat_seeds is None else repeat_seeds)
    if not seeds or any(type(seed) is not int or seed < 0 for seed in seeds):
        raise EvaluationError("Outer repeat seeds must be a non-empty sequence of non-negative integers.")

    repeat_results: list[RepeatResult] = []
    with threadpool_limits(limits=1):
        for repeat_seed in seeds:
            fold_plan = build_nested_split_plan(y, repeat_seed=int(repeat_seed), config=config)
            assignment_counts = np.zeros(X.shape[0], dtype=np.int8)
            per_model_scores = {
                name: np.full(X.shape[0], np.nan, dtype=np.float64)
                for name in MODEL_NAMES
            }
            fold_records: list[Mapping[str, Any]] = []

            for fold in fold_plan:
                fold_number = fold.fold_number
                outer_train_idx = fold.outer_train_indices
                outer_test_idx = fold.outer_assessment_indices
                if np.intersect1d(outer_train_idx, outer_test_idx).size:
                    raise EvaluationError("Outer-CV training and assessment partitions overlap.")
                if np.any(assignment_counts[outer_test_idx] != 0):
                    raise EvaluationError("An observation appears in more than one assessment fold per repeat.")
                assignment_counts[outer_test_idx] += 1
                X_train = X[outer_train_idx]
                y_train = y[outer_train_idx]
                X_assessment = X[outer_test_idx]
                y_assessment = y[outer_test_idx]
                train_labels, train_counts = np.unique(y_train, return_counts=True)
                assessment_labels, assessment_counts = np.unique(y_assessment, return_counts=True)
                if tuple(train_labels.tolist()) != (0, 1) or tuple(assessment_labels.tolist()) != (0, 1):
                    raise EvaluationError("A stratified outer fold does not contain both target labels.")
                train_count_map = {int(label): int(count) for label, count in zip(train_labels, train_counts)}
                assessment_count_map = {
                    int(label): int(count) for label, count in zip(assessment_labels, assessment_counts)
                }
                if min(train_count_map.values()) < config.inner_folds:
                    raise EvaluationError("Outer-training fold is too small for registered inner stratification.")

                inner_seed = fold.inner_seed
                inner_splits = fold.inner_splits
                family_searches: dict[str, GridSearchCV] = {}
                family_scores: dict[str, float] = {}
                for family in MODEL_FAMILIES:
                    family_searches[family] = _search_family(
                        family,
                        X_train,
                        y_train,
                        inner_splits,
                        random_state=derive_model_seed(repeat_seed, fold_number, family, config),
                        config=config,
                    )
                    family_scores[family] = float(family_searches[family].best_score_)
                chosen_family = choose_model_family(
                    family_scores,
                    tolerance=config.auc_equivalence_tolerance,
                )

                # Baseline is fit only on the outer-training labels and ignores X.
                dummy = make_prevalence_dummy()
                dummy.fit(np.zeros((len(y_train), 1), dtype=np.float64), y_train)
                dummy_scores = _positive_probability(
                    dummy,
                    np.zeros((len(y_assessment), 1), dtype=np.float64),
                )
                per_model_scores["prevalence_dummy"][outer_test_idx] = dummy_scores

                family_probabilities: dict[str, np.ndarray] = {}
                for family in MODEL_FAMILIES:
                    probabilities = _positive_probability(
                        family_searches[family].best_estimator_,
                        X_assessment,
                    )
                    family_probabilities[family] = probabilities
                    per_model_scores[family][outer_test_idx] = probabilities
                per_model_scores["inner_selected_procedure"][outer_test_idx] = family_probabilities[
                    chosen_family
                ]

                fold_records.append({
                    "outer_fold_number": fold_number,
                    "inner_seed": inner_seed,
                    "model_seed_by_family": {
                        family: derive_model_seed(repeat_seed, fold_number, family, config)
                        for family in MODEL_FAMILIES
                    },
                    "n_outer_training": int(len(outer_train_idx)),
                    "n_outer_assessment": int(len(outer_test_idx)),
                    "outer_training_class_counts": {
                        "0": train_count_map[0],
                        "1": train_count_map[1],
                    },
                    "outer_assessment_class_counts": {
                        "0": assessment_count_map[0],
                        "1": assessment_count_map[1],
                    },
                    "inner_best_mean_roc_auc_by_family": {
                        family: family_scores[family] for family in MODEL_FAMILIES
                    },
                    "inner_best_parameters_by_family": {
                        family: dict(family_searches[family].best_params_)
                        for family in MODEL_FAMILIES
                    },
                    "selected_family": chosen_family,
                    "selection_rule": (
                        "L2 logistic regression if its inner ROC-AUC is no more than "
                        f"{config.auc_equivalence_tolerance:.2f} below the best family; otherwise best family"
                    ),
                })

            if not np.all(assignment_counts == 1):
                raise EvaluationError("Outer assessment folds do not cover each source row exactly once.")
            if any(not np.isfinite(values).all() for values in per_model_scores.values()):
                raise EvaluationError("At least one outer-fold prediction is missing or non-finite.")
            metrics = {
                model_name: calculate_metrics(y, per_model_scores[model_name], config=config)
                for model_name in MODEL_NAMES
            }
            readonly_scores: dict[str, np.ndarray] = {}
            for model_name, scores in per_model_scores.items():
                snapshot = np.array(scores, dtype=np.float64, copy=True)
                snapshot.setflags(write=False)
                readonly_scores[model_name] = snapshot
            repeat_results.append(RepeatResult(
                outer_repeat_seed=int(repeat_seed),
                metrics=metrics,
                predictions=readonly_scores,
                fold_records=tuple(fold_records),
            ))

    return NestedCVResult(
        repeat_results=tuple(repeat_results),
        row_count=int(X.shape[0]),
        positive_count=int(np.count_nonzero(y == 1)),
        negative_count=int(np.count_nonzero(y == 0)),
    )


def _summary_for_nested_result(result: NestedCVResult) -> dict[str, Any]:
    scalar_metrics = (
        "roc_auc",
        "average_precision",
        "accuracy_at_0_5_exploratory",
        "sensitivity_at_0_5_exploratory",
        "specificity_at_0_5_exploratory",
        "brier_score",
    )
    summary: dict[str, Any] = {}
    for model_name in result.model_names:
        model_summary: dict[str, Any] = {}
        for metric_name in scalar_metrics:
            values = np.asarray(
                [repeat.metrics[model_name][metric_name] for repeat in result.repeat_results],
                dtype=np.float64,
            )
            model_summary[metric_name] = {
                "mean_across_repeats": float(np.mean(values)),
                "population_sd_across_repeats": float(np.std(values, ddof=0)),
                "repeat_count": int(values.size),
                "interpretation": "DESCRIPTIVE_ONLY_SAME_SOURCE_ROWS_REUSED_NO_CI",
            }
        for metric_name in (
            "calibration_in_the_large_intercept",
            "calibration_slope",
        ):
            values = [
                repeat.metrics[model_name]["calibration"].get(metric_name)
                for repeat in result.repeat_results
            ]
            available = np.asarray([value for value in values if value is not None], dtype=np.float64)
            model_summary[metric_name] = {
                "mean_across_estimable_repeats": (
                    float(np.mean(available)) if available.size else None
                ),
                "population_sd_across_estimable_repeats": (
                    float(np.std(available, ddof=0)) if available.size else None
                ),
                "estimable_repeat_count": int(available.size),
                "repeat_count": len(result.repeat_results),
                "interpretation": "DESCRIPTIVE_ONLY_SAME_SOURCE_ROWS_REUSED_NO_CI",
            }
        summary[model_name] = model_summary
    return summary


def nested_result_to_report(result: NestedCVResult) -> dict[str, Any]:
    """Convert nested CV output to aggregate report data; never serializes row scores."""
    return {
        "primary_estimand": "repeated_nested_outer_OOF_ROC_AUC_of_inner_selected_procedure",
        "repeat_count": len(result.repeat_results),
        "source_row_count_per_repeat": result.row_count,
        "positive_count": result.positive_count,
        "negative_count": result.negative_count,
        "independent_external_validation_performed": False,
        "repeat_dependence_note": (
            "Each repeat contains one outer-fold prediction per source row. All repeats reuse the same "
            "people; mean and population SD across repeat-level metrics are descriptive only. No confidence "
            "interval or pooled 4-repeat n is reported."
        ),
        "per_repeat_metrics": [
            {
                "outer_repeat_seed": repeat.outer_repeat_seed,
                "metrics_by_model": {
                    model_name: dict(repeat.metrics[model_name])
                    for model_name in result.model_names
                },
            }
            for repeat in result.repeat_results
        ],
        "descriptive_summary_across_repeats": _summary_for_nested_result(result),
        "outer_fold_selection_and_class_counts": [
            {
                "outer_repeat_seed": repeat.outer_repeat_seed,
                "folds": [dict(fold) for fold in repeat.fold_records],
            }
            for repeat in result.repeat_results
        ],
    }


def _run_label_shuffle_negative_control(
    dataset: ClevelandDataset,
    *,
    config: ExperimentConfig = DEFAULT_CONFIG,
) -> NegativeControlResult:
    """Run three prespecified label-shuffle nested-CV smoke tests.

    The true labels are used only by NumPy to create each permutation. Each
    nested run receives a new dataset object containing the permuted labels,
    then performs stratification, tuning, and evaluation exclusively against
    those shuffled labels. No true-label baseline score or formal p-value is
    computed.
    """
    _validate_binary_inputs(dataset.X, dataset.y, config)
    records: list[Mapping[str, Any]] = []
    aucs: list[float] = []
    for shuffle_seed in config.negative_control_seeds:
        shuffled_y = np.random.default_rng(int(shuffle_seed)).permutation(dataset.y).astype(np.int8)
        counts = tuple((label, int(np.count_nonzero(shuffled_y == label))) for label in (0, 1))
        shuffled = ClevelandDataset(
            X=dataset.X,
            y=shuffled_y,
            feature_names=dataset.feature_names,
            row_count=dataset.row_count,
            binary_target_counts=counts,
        )
        result = _run_nested_cv(
            shuffled,
            config=config,
            repeat_seeds=(int(shuffle_seed),),
        )
        repeat = result.repeat_results[0]
        selected_metrics = repeat.metrics["inner_selected_procedure"]
        auc = float(selected_metrics["roc_auc"])
        aucs.append(auc)
        records.append({
            "shuffle_seed": int(shuffle_seed),
            "outer_repeat_seed": int(shuffle_seed),
            "outer_repeat_count": config.negative_control_outer_repeats,
            "selected_procedure_metrics": dict(selected_metrics),
            "per_model_roc_auc": {
                model_name: float(repeat.metrics[model_name]["roc_auc"])
                for model_name in result.model_names
            },
            "same_nested_cv_wiring": True,
            "true_labels_passed_to_nested_selection_or_scoring": False,
        })
        # Release per-row shuffled predictions immediately; only aggregate
        # metrics survive in the protected experiment report.
        del result, shuffled, shuffled_y

    values = np.asarray(aucs, dtype=np.float64)
    summary = {
        "selected_procedure_roc_auc_by_shuffle": aucs,
        "selected_procedure_roc_auc_mean": float(np.mean(values)),
        "selected_procedure_roc_auc_population_sd": float(np.std(values, ddof=0)),
        "shuffle_count": len(aucs),
        "interpretation": "SMOKE_TEST_NOT_FORMAL_PERMUTATION_P_VALUE",
        "no_p_value_or_independent_sample_claim": True,
    }
    return NegativeControlResult(
        shuffle_seeds=tuple(config.negative_control_seeds),
        per_shuffle=tuple(records),
        summary=summary,
    )


def _synthetic_smoke_result(
    dataset: ClevelandDataset,
    *,
    config: ExperimentConfig = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Small safe summary for CLI dry-run; no patient or per-row output."""
    nested = _run_nested_cv(dataset, config=config)
    negative = _run_label_shuffle_negative_control(dataset, config=config)
    return {
        "status": "PASS",
        "scope": "SYNTHETIC_SOFTWARE_FIXTURE_ONLY_NOT_A_RESEARCH_RESULT",
        "source_rows_parsed_in_memory": dataset.row_count,
        "real_data_path_opened": False,
        "real_model_run_authorization_checked_or_used": False,
        "outer_repeat_count": len(nested.repeat_results),
        "outer_fold_count_per_repeat": config.outer_folds,
        "negative_control_shuffle_count": len(negative.shuffle_seeds),
        "models_exercised": list(MODEL_NAMES),
        "metrics_generated_for_medical_or_benchmark_use": False,
    }
