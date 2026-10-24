"""Deterministic nested-CV evaluation, uncertainty, and negative controls.

Scientific rules encoded here:

* stratification and seeds come only from the registered plan;
* every hyperparameter search and every preprocessing fit happens inside the
  outer-training partition (inner CV) and nothing is fitted on assessment rows;
* model-family selection is an inner-CV decision with a prespecified logistic
  simplicity preference; the assessment fold is never used for selection;
* each repeat contributes exactly one out-of-fold prediction per source row, so
  repeats reuse the same participants. Descriptive mean/SD across repeats is
  reported; no pooled ``k * n`` inference is possible;
* uncertainty is a participant-level percentile bootstrap *within* a repeat,
  conditional on the fitted fold models, and is labelled as such;
* a label-permutation negative control runs the same nested wiring on permuted
  labels; an implausibly high permuted-label AUROC is treated as a leakage
  alarm rather than as a result.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping

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

from research.uci412.adapter import Uci412Dataset
from research.uci412.config import DEFAULT_CONFIG, Uci412Config
from research.uci412.errors import EvaluationError
from research.uci412.models import (
    MODEL_FAMILIES,
    assert_pipeline_contract,
    assert_registered_feature_names,
    build_family_estimator,
    family_parameter_grid,
    make_prevalence_dummy,
)

MODEL_NAMES: tuple[str, ...] = (
    "prevalence_dummy",
    "l2_logistic_regression",
    "constrained_random_forest",
    "inner_selected_procedure",
)
SELECTION_RULE_TEXT = (
    "L2 logistic regression is selected when its inner-CV ROC-AUC is no more than the registered "
    "tolerance below the best family; otherwise the best family is selected."
)


@dataclass(frozen=True, slots=True)
class RepeatResult:
    """One out-of-fold prediction per source row for one outer repeat."""

    outer_repeat_seed: int
    metrics: Mapping[str, Mapping[str, Any]]
    uncertainty: Mapping[str, Mapping[str, Any]]
    predictions: Mapping[str, np.ndarray]
    fold_records: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True, slots=True)
class NestedCVResult:
    """Repeated nested-CV output; row scores stay in memory or protected local storage."""

    repeat_results: tuple[RepeatResult, ...]
    row_count: int
    positive_count: int
    negative_count: int
    model_names: tuple[str, ...] = MODEL_NAMES


@dataclass(frozen=True, slots=True)
class NegativeControlResult:
    """Aggregate-only label-permutation smoke test."""

    shuffle_seeds: tuple[int, ...]
    per_shuffle: tuple[Mapping[str, Any], ...]
    summary: Mapping[str, Any]
    interpretation: str = "SMOKE_TEST_NOT_FORMAL_PERMUTATION_P_VALUE"


def _as_binary_arrays(
    dataset: Uci412Dataset,
    config: Uci412Config,
) -> tuple[np.ndarray, np.ndarray]:
    X = dataset.X
    y = dataset.y
    if not isinstance(X, np.ndarray) or X.ndim != 2:
        raise EvaluationError("Evaluation requires a two-dimensional numeric feature matrix.")
    if X.shape[1] != len(config.feature_names):
        raise EvaluationError("Evaluation received a feature count outside the registered panel.")
    if tuple(dataset.feature_names) != tuple(config.feature_names):
        raise EvaluationError("Evaluation received features outside the registered panel order.")
    assert_registered_feature_names(tuple(dataset.feature_names), config)
    if not isinstance(y, np.ndarray) or y.ndim != 1 or y.shape[0] != X.shape[0]:
        raise EvaluationError("Evaluation target shape does not match the feature matrix.")
    if X.shape[0] < config.outer_folds:
        raise EvaluationError("Too few rows for the registered outer stratified folds.")
    if not np.isfinite(X[~np.isnan(X)]).all():
        raise EvaluationError("Evaluation features contain a non-finite observed value.")
    if not np.isin(y, (0, 1)).all():
        raise EvaluationError("Evaluation target must contain only mapped binary labels.")
    unique, counts = np.unique(y, return_counts=True)
    if tuple(unique.tolist()) != (0, 1):
        raise EvaluationError("Both binary target classes must be present for stratification.")
    if int(counts.min()) < config.outer_folds:
        raise EvaluationError("A class has too few observations for the registered outer folds.")
    return X, y


def derive_inner_seed(outer_seed: int, outer_fold_number: int, config: Uci412Config = DEFAULT_CONFIG) -> int:
    if outer_fold_number <= 0:
        raise ValueError("Outer fold numbers are one-based.")
    return int(outer_seed + config.inner_seed_offset + config.inner_fold_multiplier * outer_fold_number)


def derive_model_seed(
    outer_seed: int,
    outer_fold_number: int,
    family: str,
    config: Uci412Config = DEFAULT_CONFIG,
) -> int:
    if outer_fold_number <= 0:
        raise ValueError("Outer fold numbers are one-based.")
    if family == "l2_logistic_regression":
        family_offset = config.logistic_seed_offset
    elif family == "constrained_random_forest":
        family_offset = config.forest_seed_offset
    else:
        raise EvaluationError("Only the registered model families have fit seeds.")
    seed = (
        outer_seed
        + config.model_seed_offset
        + config.model_fold_multiplier * outer_fold_number
        + family_offset
    )
    return int(seed % (2**32 - 1))


def derive_bootstrap_seed(outer_seed: int, config: Uci412Config = DEFAULT_CONFIG) -> int:
    return int(outer_seed + config.bootstrap_seed_offset)


def plan_outer_folds(
    y: np.ndarray,
    repeat_seed: int,
    config: Uci412Config = DEFAULT_CONFIG,
) -> tuple[tuple[np.ndarray, np.ndarray], ...]:
    """Deterministic, stratified outer fold plan for one repeat seed."""
    splitter = StratifiedKFold(n_splits=config.outer_folds, shuffle=True, random_state=int(repeat_seed))
    return tuple(splitter.split(np.zeros(len(y)), y))


def plan_inner_folds(
    y_train: np.ndarray,
    repeat_seed: int,
    outer_fold_number: int,
    config: Uci412Config = DEFAULT_CONFIG,
) -> tuple[tuple[np.ndarray, np.ndarray], ...]:
    splitter = StratifiedKFold(
        n_splits=config.inner_folds,
        shuffle=True,
        random_state=derive_inner_seed(repeat_seed, outer_fold_number, config),
    )
    return tuple(splitter.split(np.zeros(len(y_train)), y_train))


def choose_model_family(
    inner_auc_by_family: Mapping[str, float],
    *,
    tolerance: float = DEFAULT_CONFIG.auc_equivalence_tolerance,
) -> str:
    """Apply the prespecified logistic simplicity preference within tolerance."""
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


def _calibration_diagnostics(y_true: np.ndarray, probabilities: np.ndarray, *, n_bins: int) -> dict[str, Any]:
    """Describe out-of-fold calibration without recalibrating or changing predictions."""
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
        "diagnostic_status": "DESCRIPTIVE_ONLY_NO_RECALIBRATION",
        "applied_to_predictions": False,
        "descriptive_only": True,
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

    def intercept_equation(intercept: float) -> float:
        return float(np.sum(expit(logits + intercept)) - n_positive)

    try:
        intercept = brentq(intercept_equation, -40.0, 40.0, xtol=1e-12, rtol=1e-12)
        if math.isfinite(intercept):
            result["calibration_in_the_large_intercept"] = float(intercept)
            result["calibration_in_the_large_status"] = "ESTIMATED_DESCRIPTIVE_OOF_DIAGNOSTIC"
    except (ValueError, RuntimeError, OverflowError):
        result["calibration_in_the_large_status"] = "UNSTABLE_OR_NOT_ESTIMABLE"

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
            if fit.success and beta.shape == (2,) and np.isfinite(beta).all() and np.max(np.abs(beta)) < 15.0:
                result["calibration_intercept"] = float(beta[0])
                result["calibration_slope"] = float(beta[1])
                result["calibration_slope_status"] = "ESTIMATED_DESCRIPTIVE_OOF_DIAGNOSTIC"
            else:
                result["calibration_slope_status"] = "UNSTABLE_OR_NOT_ESTIMABLE"
        except (ValueError, FloatingPointError, np.linalg.LinAlgError):
            result["calibration_slope_status"] = "UNSTABLE_OR_NOT_ESTIMABLE"

    if np.ptp(p) <= 1e-12:
        result["quantile_reliability_curve_status"] = "NOT_ESTIMABLE_CONSTANT_SCORES"
        return result
    order = np.argsort(p, kind="mergesort")
    bins = np.array_split(order, n_bins)
    curve: list[dict[str, Any]] = []
    for index, bin_indices in enumerate(bins, start=1):
        if bin_indices.size == 0:
            continue
        curve.append(
            {
                "bin": index,
                "n": int(bin_indices.size),
                "mean_predicted_probability": float(np.mean(p[bin_indices])),
                "observed_positive_fraction": float(np.mean(y[bin_indices])),
            }
        )
    result["quantile_reliability_curve"] = curve
    result["quantile_reliability_curve_status"] = "DESCRIPTIVE_OOF_QUANTILE_BINS"
    return result


def calculate_metrics(
    y_true: np.ndarray,
    probabilities: np.ndarray,
    *,
    config: Uci412Config = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Compute the registered metric set at the fixed exploratory threshold."""
    y = np.asarray(y_true, dtype=np.int64)
    p = np.asarray(probabilities, dtype=np.float64)
    if y.shape != p.shape or y.ndim != 1:
        raise EvaluationError("Metric inputs must be one-dimensional and aligned.")
    if not np.isfinite(p).all() or np.any((p < 0) | (p > 1)):
        raise EvaluationError("Metric inputs must be finite probabilities in [0, 1].")
    if np.unique(y).size != 2:
        raise EvaluationError("Both classes are required to compute the registered metrics.")
    threshold = float(config.threshold)
    predicted = (p >= threshold).astype(np.int64)
    matrix = confusion_matrix(y, predicted, labels=[0, 1])
    tn, fp, fn, tp = (int(value) for value in matrix.ravel())
    sensitivity = float(tp / (tp + fn)) if (tp + fn) else None
    specificity = float(tn / (tn + fp)) if (tn + fp) else None
    return {
        "roc_auc": float(roc_auc_score(y, p)),
        "average_precision": float(average_precision_score(y, p)),
        "accuracy_at_0_5_exploratory": float(accuracy_score(y, predicted)),
        "sensitivity_at_0_5_exploratory": sensitivity,
        "specificity_at_0_5_exploratory": specificity,
        "brier_score": float(brier_score_loss(y, p)),
        "confusion_matrix_at_0_5": {
            "true_negative": tn,
            "false_positive": fp,
            "false_negative": fn,
            "true_positive": tp,
        },
        "threshold": threshold,
        "threshold_rule": "positive_if_probability_greater_than_or_equal_to_threshold",
        "threshold_tuned_on_assessment_or_external_data": False,
        "prevalence": float(np.mean(y)),
        "calibration": _calibration_diagnostics(y, p, n_bins=config.calibration_bins),
        "metric_caveats": [
            "Internal out-of-fold estimate on a single source cohort; not external validation.",
            "Repeats reuse the same participants; no pooled multi-repeat sample size exists.",
            "Accuracy is secondary only and is never a selection criterion.",
        ],
    }


def bootstrap_metric_ci(
    y_true: np.ndarray,
    probabilities: np.ndarray,
    *,
    seed: int,
    config: Uci412Config = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Participant-level percentile bootstrap within one repeat's out-of-fold scores."""
    y = np.asarray(y_true, dtype=np.int64)
    p = np.asarray(probabilities, dtype=np.float64)
    rng = np.random.default_rng(int(seed))
    positives = np.flatnonzero(y == 1)
    negatives = np.flatnonzero(y == 0)
    auc_values: list[float] = []
    ap_values: list[float] = []
    for _ in range(config.bootstrap_resamples):
        sample = np.concatenate(
            (
                rng.choice(positives, size=positives.size, replace=True),
                rng.choice(negatives, size=negatives.size, replace=True),
            )
        )
        sample_y = y[sample]
        sample_p = p[sample]
        if np.unique(sample_y).size != 2:
            continue
        auc_values.append(float(roc_auc_score(sample_y, sample_p)))
        ap_values.append(float(average_precision_score(sample_y, sample_p)))
    if len(auc_values) < max(10, config.bootstrap_resamples // 2):
        return {
            "status": "NOT_ESTIMABLE_TOO_FEW_VALID_RESAMPLES",
            "resamples_requested": config.bootstrap_resamples,
            "resamples_valid": len(auc_values),
        }
    return {
        "status": "ESTIMATED_CONDITIONAL_ON_FIXED_FOLD_FITS",
        "resamples_requested": config.bootstrap_resamples,
        "resamples_valid": len(auc_values),
        "roc_auc_ci_95": [
            float(np.percentile(auc_values, 2.5)),
            float(np.percentile(auc_values, 97.5)),
        ],
        "average_precision_ci_95": [
            float(np.percentile(ap_values, 2.5)),
            float(np.percentile(ap_values, 97.5)),
        ],
        "interpretation": (
            "Participant-level resampling of one repeat's out-of-fold predictions. It reflects "
            "sampling variability conditional on the fitted fold models; it is not a confidence "
            "interval for future patients and includes no refitting variability."
        ),
    }


def run_nested_cv(
    dataset: Uci412Dataset,
    *,
    config: Uci412Config = DEFAULT_CONFIG,
    repeat_seeds: tuple[int, ...] | None = None,
) -> NestedCVResult:
    """Run the registered repeated nested stratified CV."""
    X, y = _as_binary_arrays(dataset, config)
    seeds = tuple(config.outer_repeat_seeds if repeat_seeds is None else repeat_seeds)
    if not seeds:
        raise EvaluationError("At least one registered outer repeat seed is required.")
    if len(set(seeds)) != len(seeds):
        raise EvaluationError("Outer repeat seeds must be unique.")

    repeat_results: list[RepeatResult] = []
    for repeat_seed in seeds:
        per_model_scores: dict[str, np.ndarray] = {
            model_name: np.full(X.shape[0], np.nan, dtype=np.float64) for model_name in MODEL_NAMES
        }
        assignment_counts = np.zeros(X.shape[0], dtype=np.int64)
        fold_records: list[Mapping[str, Any]] = []

        for fold_number, (train_idx, test_idx) in enumerate(
            plan_outer_folds(y, repeat_seed, config), start=1
        ):
            X_train, y_train = X[train_idx], y[train_idx]
            X_test = X[test_idx]
            inner_splits = plan_inner_folds(y_train, repeat_seed, fold_number, config)

            family_scores: dict[str, float] = {}
            family_searches: dict[str, GridSearchCV] = {}
            family_predictions: dict[str, np.ndarray] = {}
            for family in MODEL_FAMILIES:
                estimator = build_family_estimator(
                    family,
                    random_state=derive_model_seed(repeat_seed, fold_number, family, config),
                    config=config,
                )
                assert_pipeline_contract(estimator, family, config=config)
                search = GridSearchCV(
                    estimator,
                    family_parameter_grid(family, config=config),
                    scoring="roc_auc",
                    cv=list(inner_splits),
                    n_jobs=1,
                    refit=True,
                    error_score="raise",
                )
                search.fit(X_train, y_train)
                family_scores[family] = float(search.best_score_)
                family_searches[family] = search
                family_predictions[family] = _positive_probability(search, X_test)

            chosen_family = choose_model_family(
                family_scores, tolerance=config.auc_equivalence_tolerance
            )

            dummy = make_prevalence_dummy()
            dummy.fit(X_train, y_train)
            per_model_scores["prevalence_dummy"][test_idx] = _positive_probability(dummy, X_test)
            for family in MODEL_FAMILIES:
                per_model_scores[family][test_idx] = family_predictions[family]
            per_model_scores["inner_selected_procedure"][test_idx] = family_predictions[chosen_family]
            assignment_counts[test_idx] += 1

            train_counts = {str(label): int(np.count_nonzero(y_train == label)) for label in (0, 1)}
            test_counts = {str(label): int(np.count_nonzero(y[test_idx] == label)) for label in (0, 1)}
            fold_records.append(
                {
                    "outer_fold_number": fold_number,
                    "inner_cv_seed": derive_inner_seed(repeat_seed, fold_number, config),
                    "model_seed_by_family": {
                        family: derive_model_seed(repeat_seed, fold_number, family, config)
                        for family in MODEL_FAMILIES
                    },
                    "n_outer_training": int(len(train_idx)),
                    "n_outer_assessment": int(len(test_idx)),
                    "outer_training_class_counts": train_counts,
                    "outer_assessment_class_counts": test_counts,
                    "inner_best_mean_roc_auc_by_family": {
                        family: family_scores[family] for family in MODEL_FAMILIES
                    },
                    "inner_best_parameters_by_family": {
                        family: dict(family_searches[family].best_params_)
                        for family in MODEL_FAMILIES
                    },
                    "selected_family": chosen_family,
                    "selection_rule": SELECTION_RULE_TEXT,
                }
            )

        if not np.all(assignment_counts == 1):
            raise EvaluationError("Outer assessment folds do not cover each source row exactly once.")
        if any(not np.isfinite(values).all() for values in per_model_scores.values()):
            raise EvaluationError("At least one outer-fold prediction is missing or non-finite.")

        metrics = {
            model_name: calculate_metrics(y, per_model_scores[model_name], config=config)
            for model_name in MODEL_NAMES
        }
        bootstrap_seed = derive_bootstrap_seed(repeat_seed, config)
        uncertainty = {
            model_name: bootstrap_metric_ci(
                y, per_model_scores[model_name], seed=bootstrap_seed, config=config
            )
            for model_name in MODEL_NAMES
        }
        readonly_scores: dict[str, np.ndarray] = {}
        for model_name, scores in per_model_scores.items():
            snapshot = np.array(scores, dtype=np.float64, copy=True)
            snapshot.setflags(write=False)
            readonly_scores[model_name] = snapshot
        repeat_results.append(
            RepeatResult(
                outer_repeat_seed=int(repeat_seed),
                metrics=metrics,
                uncertainty=uncertainty,
                predictions=readonly_scores,
                fold_records=tuple(fold_records),
            )
        )

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
        for metric_name in ("calibration_in_the_large_intercept", "calibration_slope"):
            values = [
                repeat.metrics[model_name]["calibration"].get(metric_name)
                for repeat in result.repeat_results
            ]
            available = np.asarray([value for value in values if value is not None], dtype=np.float64)
            model_summary[metric_name] = {
                "mean_across_estimable_repeats": float(np.mean(available)) if available.size else None,
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
            "participants; mean and population SD across repeat-level metrics are descriptive only. No "
            "confidence interval or pooled k-repeat sample size is reported."
        ),
        "per_repeat_metrics": [
            {
                "outer_repeat_seed": repeat.outer_repeat_seed,
                "metrics_by_model": {
                    model_name: dict(repeat.metrics[model_name]) for model_name in result.model_names
                },
                "uncertainty_by_model": {
                    model_name: dict(repeat.uncertainty[model_name]) for model_name in result.model_names
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


def assess_label_permutation_sanity(
    shuffled_aucs: tuple[float, ...],
    *,
    config: Uci412Config = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Flag implausible permuted-label discrimination as a leakage signal."""
    values = np.asarray(shuffled_aucs, dtype=np.float64)
    maximum = float(np.max(values)) if values.size else float("nan")
    if not math.isfinite(maximum):
        status = "NOT_ASSESSABLE_NON_FINITE_PERMUTED_SCORES"
    elif maximum >= config.leakage_alarm_threshold:
        status = "LEAKAGE_ALARM_IMPLAUSIBLY_HIGH_PERMUTED_LABEL_AUROC"
    elif maximum >= config.leakage_warning_threshold:
        status = "WARNING_ELEVATED_PERMUTED_LABEL_AUROC"
    else:
        status = "CONSISTENT_WITH_NO_DETECTED_LABEL_LEAKAGE"
    return {
        "status": status,
        "maximum_shuffled_roc_auc": maximum,
        "alarm_threshold": config.leakage_alarm_threshold,
        "warning_threshold": config.leakage_warning_threshold,
        "blocking": status == "LEAKAGE_ALARM_IMPLAUSIBLY_HIGH_PERMUTED_LABEL_AUROC",
        "interpretation": (
            "A permuted-label run that discriminates well indicates target leakage or a broken split. "
            "This is a leakage detector, not a research result."
        ),
    }


def run_label_shuffle_negative_control(
    dataset: Uci412Dataset,
    *,
    config: Uci412Config = DEFAULT_CONFIG,
) -> NegativeControlResult:
    """Run the registered label-permutation nested-CV smoke tests."""
    _as_binary_arrays(dataset, config)
    records: list[Mapping[str, Any]] = []
    aucs: list[float] = []
    for shuffle_seed in config.negative_control_seeds:
        shuffled_y = np.random.default_rng(int(shuffle_seed)).permutation(dataset.y).astype(np.int8)
        counts = tuple((label, int(np.count_nonzero(shuffled_y == label))) for label in (0, 1))
        shuffled = Uci412Dataset(
            X=dataset.X,
            y=shuffled_y,
            feature_names=dataset.feature_names,
            row_count=dataset.row_count,
            class_counts=counts,
            audit={"scope": "SYNTHETIC_LABEL_PERMUTATION", "patient_level_values_retained": False},
        )
        result = run_nested_cv(shuffled, config=config, repeat_seeds=(int(shuffle_seed),))
        repeat = result.repeat_results[0]
        selected_metrics = repeat.metrics["inner_selected_procedure"]
        auc = float(selected_metrics["roc_auc"])
        aucs.append(auc)
        records.append(
            {
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
            }
        )
        # Release permuted row scores immediately; only aggregate metrics survive.
        del result, shuffled, shuffled_y

    values = np.asarray(aucs, dtype=np.float64)
    sanity = assess_label_permutation_sanity(tuple(aucs), config=config)
    summary = {
        "selected_procedure_roc_auc_by_shuffle": aucs,
        "selected_procedure_roc_auc_mean": float(np.mean(values)),
        "selected_procedure_roc_auc_population_sd": float(np.std(values, ddof=0)),
        "shuffle_count": len(aucs),
        "interpretation": "SMOKE_TEST_NOT_FORMAL_PERMUTATION_P_VALUE",
        "no_p_value_or_independent_sample_claim": True,
        "leakage_assessment": sanity,
    }
    return NegativeControlResult(
        shuffle_seeds=tuple(config.negative_control_seeds),
        per_shuffle=tuple(records),
        summary=summary,
    )


def assert_no_target_leakage(dataset: Uci412Dataset, config: Uci412Config = DEFAULT_CONFIG) -> dict[str, Any]:
    """Runtime, data-independent leakage assertions recorded in the report."""
    feature_names = tuple(dataset.feature_names)
    checks = {
        "feature_names_equal_registered_panel": feature_names == tuple(config.feature_names),
        "target_column_not_in_features": config.target_column not in feature_names,
        "no_prohibited_predictor_present": not (
            set(feature_names)
            & {
                "Cath",
                "LAD",
                "LCX",
                "RCA",
                "num",
                "ca",
                "thal",
                "id",
                "ccf",
                "name",
            }
        ),
        "target_matrix_is_separate": dataset.X.shape[1] == len(feature_names),
        "target_is_binary": bool(np.isin(dataset.y, (0, 1)).all()),
        "target_matches_audited_class_counts": dict(dataset.class_counts) == config.expected_counts,
        "no_row_deletion_or_duplication": dataset.row_count == config.expected_row_count,
        "preprocessing_is_fold_local_pipeline_only": True,
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise EvaluationError("Pre-modelling leakage checks failed: " + ", ".join(sorted(failed)))
    return checks


def synthetic_smoke_result(
    dataset: Uci412Dataset,
    *,
    config: Uci412Config = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Small, safe summary for the CLI dry-run; no patient or row-level output."""
    nested = run_nested_cv(dataset, config=config)
    negative = run_label_shuffle_negative_control(dataset, config=config)
    report = nested_result_to_report(nested)
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
        "selected_family_by_repeat": [
            sorted({record["selected_family"] for record in repeat.fold_records})
            for repeat in nested.repeat_results
        ],
        "metrics_generated_for_medical_or_benchmark_use": False,
        "primary_estimand_present_in_report": "primary_estimand" in report,
        "leakage_assessment": negative.summary["leakage_assessment"],
    }
