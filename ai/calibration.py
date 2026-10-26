"""Out-of-fold probability calibration, comprehensive metrics, and fold dispersion.

Reuses :func:`research.uci412.evaluation.calculate_metrics` for core
discrimination, confusion-matrix, and Cox calibration diagnostics, while adding:
1. ``OofLogisticCalibrator`` — monotone logistic (Platt/Cox) post-hoc
   recalibration fitted on out-of-fold predictions (either inner-CV OOF within
   each outer training fold for cross-fitted evaluation, or full-development OOF
   for the packaged final calibrator), serializable as ``calibration.json``.
   Supports exact affine transformation on ``raw_log_odds`` for linear logistic
   models and clipped-logit transformation on bounded ``[0, 1]`` probabilities
   for tree/baseline models.
2. Full class-specific metrics (sensitivity, specificity, PPV, NPV, F1, log-loss,
   ECE) and stratified bootstrap 95% confidence intervals.
3. Prevalence-shift prior-odds diagnostics for locked external cohort evaluation.
4. Descriptive outer-fold prediction dispersion (using each outer fold's own
   compatible training-fold calibrator) and missing-stage completeness metadata,
   without claiming validated patient-specific epistemic uncertainty or clinical
   action thresholds.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import math
from typing import Any, Final, Mapping, Sequence

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    log_loss,
    roc_auc_score,
)

from ai.errors import CalibrationIntegrityError
from research.uci412.config import DEFAULT_CONFIG as UCI412_DEFAULT_CONFIG
from research.uci412.evaluation import calculate_metrics as uci412_calculate_metrics

CALIBRATION_SCHEMA_VERSION: Final[str] = "cardioassist.ai.calibration/v1"
PROB_CLIP_EPS: Final[float] = 1e-6

VALID_INPUT_LINKS: Final[frozenset[str]] = frozenset(
    {
        "exact_raw_log_odds",
        "clipped_logit_of_raw_probability",
    }
)
VALID_FIT_SCOPES: Final[frozenset[str]] = frozenset(
    {
        "INNER_CV_FOLD_CONTAINED",
        "FULL_DEVELOPMENT_OOF_FINAL",
    }
)


def safe_clipped_logit(probabilities: np.ndarray | float) -> np.ndarray:
    """Compute logit after clamping bounded [0, 1] probabilities away from {0, 1}."""
    clipped = np.clip(
        np.asarray(probabilities, dtype=np.float64),
        PROB_CLIP_EPS,
        1.0 - PROB_CLIP_EPS,
    )
    return np.log(clipped) - np.log1p(-clipped)


def _expected_calibration_error(
    y: np.ndarray, p: np.ndarray, *, n_bins: int = 10
) -> float:
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    total = float(y.size)
    ece = 0.0
    for idx in range(n_bins):
        low, high = edges[idx], edges[idx + 1]
        if idx == n_bins - 1:
            mask = (p >= low) & (p <= high)
        else:
            mask = (p >= low) & (p < high)
        count = int(np.sum(mask))
        if count > 0:
            ece += (count / total) * abs(float(np.mean(p[mask]) - np.mean(y[mask])))
    return float(ece)


def evaluate_comprehensive_metrics(
    y_true: np.ndarray,
    probabilities: np.ndarray,
    *,
    seed: int = 20261025,
    n_bootstrap: int = 300,
    threshold: float = 0.5,
    calibration_bins: int = 10,
    evaluation_scope: str = "INTERNAL_OUT_OF_FOLD_RESEARCH_ONLY",
) -> dict[str, Any]:
    """Compute discrimination, calibration, class-specific metrics, and bootstrap 95% CIs."""
    y = np.asarray(y_true, dtype=np.int64)
    p = np.asarray(probabilities, dtype=np.float64)
    if y.ndim != 1 or y.shape != p.shape or y.size < 4:
        raise CalibrationIntegrityError(
            "invalid_metric_inputs",
            "Labels and probabilities must be aligned 1-D arrays of length >= 4.",
        )
    if not np.isfinite(p).all() or np.any((p < 0.0) | (p > 1.0)):
        raise CalibrationIntegrityError(
            "invalid_probabilities",
            "Predicted probabilities must be finite values in [0, 1].",
        )
    if set(np.unique(y).tolist()) != {0, 1}:
        raise CalibrationIntegrityError(
            "single_class_evaluation",
            "Evaluation requires both positive (1) and negative (0) target classes.",
        )

    cfg = replace(
        UCI412_DEFAULT_CONFIG,
        threshold=float(threshold),
        calibration_bins=int(calibration_bins),
    )
    base = uci412_calculate_metrics(y, p, config=cfg)
    cm = base["confusion_matrix_at_0_5"]
    tn, fp, fn, tp = (
        int(cm["true_negative"]),
        int(cm["false_positive"]),
        int(cm["false_negative"]),
        int(cm["true_positive"]),
    )
    ppv = float(tp / (tp + fp)) if (tp + fp) > 0 else None
    npv = float(tn / (tn + fn)) if (tn + fn) > 0 else None
    f1 = float((2 * tp) / (2 * tp + fp + fn)) if (2 * tp + fp + fn) > 0 else 0.0
    clipped = np.clip(p, PROB_CLIP_EPS, 1.0 - PROB_CLIP_EPS)

    rng = np.random.default_rng(int(seed))
    pos_idx = np.flatnonzero(y == 1)
    neg_idx = np.flatnonzero(y == 0)
    aucs: list[float] = []
    aps: list[float] = []
    briers: list[float] = []
    sens_list: list[float] = []
    spec_list: list[float] = []

    for _ in range(int(n_bootstrap)):
        b_pos = rng.choice(pos_idx, size=pos_idx.size, replace=True)
        b_neg = rng.choice(neg_idx, size=neg_idx.size, replace=True)
        idx = np.concatenate([b_pos, b_neg])
        by = y[idx]
        bp = p[idx]
        aucs.append(float(roc_auc_score(by, bp)))
        aps.append(float(average_precision_score(by, bp)))
        briers.append(float(brier_score_loss(by, bp)))
        b_pred = (bp >= threshold).astype(np.int64)
        sens_list.append(float(np.mean(b_pred[by == 1] == 1)))
        spec_list.append(float(np.mean(b_pred[by == 0] == 0)))

    def _ci(vals: list[float]) -> list[float]:
        return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]

    return {
        "evaluation_scope": evaluation_scope,
        "n_samples": int(y.size),
        "n_positive": int(pos_idx.size),
        "n_negative": int(neg_idx.size),
        "prevalence": float(base["prevalence"]),
        "discrimination": {
            "roc_auc": float(base["roc_auc"]),
            "average_precision": float(base["average_precision"]),
        },
        "proper_scoring_and_calibration": {
            "brier_score": float(base["brier_score"]),
            "log_loss": float(log_loss(y, clipped, labels=[0, 1])),
            "expected_calibration_error_10bin": _expected_calibration_error(
                y, p, n_bins=calibration_bins
            ),
            "cox_diagnostics": base["calibration"],
        },
        "class_specific_at_exploratory_threshold": {
            "exploratory_threshold": float(threshold),
            "threshold_clinically_approved": False,
            "accuracy": float(base["accuracy_at_0_5_exploratory"]),
            "sensitivity_recall_pos": base["sensitivity_at_0_5_exploratory"],
            "specificity_recall_neg": base["specificity_at_0_5_exploratory"],
            "ppv_precision_pos": ppv,
            "npv_neg": npv,
            "f1_pos": f1,
            "confusion_matrix": cm,
        },
        "bootstrap_95_ci": {
            "method": "stratified_percentile_bootstrap_conditional_on_fitted_models",
            "n_resamples": int(n_bootstrap),
            "seed": int(seed),
            "roc_auc": _ci(aucs),
            "average_precision": _ci(aps),
            "brier_score": _ci(briers),
            "sensitivity_at_threshold": _ci(sens_list),
            "specificity_at_threshold": _ci(spec_list),
        },
    }


@dataclass(frozen=True, slots=True)
class OofLogisticCalibrator:
    """Monotone out-of-fold Platt/Cox logistic probability calibrator.

    When ``input_link == 'exact_raw_log_odds'`` (used for ``l2_logistic_regression``),
    the calibrator maps unclipped raw log-odds ``eta_raw`` via the exact affine
    function ``eta_cal = intercept + slope * eta_raw`` and ``p_cal = expit(eta_cal)``,
    preserving exact Shapley linearity on ``calibrated_log_odds``.

    When ``input_link == 'clipped_logit_of_raw_probability'`` (used for tree and
    dummy models whose leaves may emit exact ``0.0`` or ``1.0``), probabilities are
    clamped to ``[1e-6, 1 - 1e-6]`` prior to ``logit``.
    """

    model_family: str
    intercept: float
    slope: float
    development_prevalence: float
    n_oof_samples: int
    oof_brier_before: float
    oof_brier_after: float
    status: str  # "FITTED_OOF_MONOTONE_LOGISTIC" | "IDENTITY_CONSTANT_FALLBACK"
    input_link: str = "clipped_logit_of_raw_probability"
    fit_scope: str = "FULL_DEVELOPMENT_OOF_FINAL"

    @classmethod
    def fit_from_oof(
        cls,
        y_oof: np.ndarray,
        p_oof_raw: np.ndarray,
        *,
        model_family: str,
        raw_logits: np.ndarray | None = None,
        fit_scope: str = "FULL_DEVELOPMENT_OOF_FINAL",
        l2_anchor: float = 1e-3,
    ) -> "OofLogisticCalibrator":
        if fit_scope not in VALID_FIT_SCOPES:
            raise CalibrationIntegrityError(
                "invalid_calibration_fit_scope",
                f"Unsupported calibration fit_scope '{fit_scope}'.",
            )
        y = np.asarray(y_oof, dtype=np.float64)
        p = np.asarray(p_oof_raw, dtype=np.float64)
        if y.ndim != 1 or y.shape != p.shape or y.size < 8:
            raise CalibrationIntegrityError(
                "invalid_oof_calibration_inputs",
                "Out-of-fold calibration requires >= 8 aligned 1-D observations.",
            )
        if not np.isfinite(p).all() or np.any((p < 0.0) | (p > 1.0)):
            raise CalibrationIntegrityError(
                "invalid_oof_probabilities",
                "Out-of-fold probabilities must be finite in [0, 1].",
            )
        if set(np.unique(y).astype(int).tolist()) != {0, 1}:
            raise CalibrationIntegrityError(
                "single_class_oof_labels",
                "Out-of-fold calibration requires both target classes.",
            )

        if raw_logits is not None:
            logits = np.asarray(raw_logits, dtype=np.float64)
            if logits.shape != p.shape or not np.isfinite(logits).all():
                raise CalibrationIntegrityError(
                    "invalid_oof_raw_logits",
                    "Provided raw_logits must be finite and aligned with p_oof_raw.",
                )
            if not np.allclose(expit(logits), p, atol=1e-9):
                raise CalibrationIntegrityError(
                    "inconsistent_oof_raw_logits",
                    "Provided raw_logits do not match p_oof_raw under expit.",
                )
            input_link = "exact_raw_log_odds"
        else:
            logits = safe_clipped_logit(p)
            input_link = "clipped_logit_of_raw_probability"

        brier_before = float(brier_score_loss(y.astype(np.int64), p))
        dev_prev = float(np.mean(y))

        if float(np.ptp(logits)) <= 1e-8 or model_family == "prevalence_dummy":
            prior_logit = float(np.log(dev_prev / (1.0 - dev_prev)))
            p_after = np.full_like(p, float(expit(prior_logit)))
            return cls(
                model_family=model_family,
                intercept=prior_logit,
                slope=0.0,
                development_prevalence=dev_prev,
                n_oof_samples=int(y.size),
                oof_brier_before=brier_before,
                oof_brier_after=float(brier_score_loss(y.astype(np.int64), p_after)),
                status="IDENTITY_CONSTANT_FALLBACK",
                input_link=input_link,
                fit_scope=fit_scope,
            )

        def objective(params: np.ndarray) -> tuple[float, np.ndarray]:
            a, b = float(params[0]), float(params[1])
            eta = a + b * logits
            nll = float(np.mean(np.logaddexp(0.0, eta) - y * eta))
            reg = 0.5 * l2_anchor * (a * a + (b - 1.0) ** 2)
            diff = expit(eta) - y
            grad_a = float(np.mean(diff)) + l2_anchor * a
            grad_b = float(np.mean(diff * logits)) + l2_anchor * (b - 1.0)
            return nll + reg, np.array([grad_a, grad_b], dtype=np.float64)

        opt = minimize(
            lambda theta: objective(theta)[0],
            x0=np.array([0.0, 1.0], dtype=np.float64),
            jac=lambda theta: objective(theta)[1],
            method="L-BFGS-B",
            bounds=[(-15.0, 15.0), (0.01, 15.0)],
        )
        intercept = float(opt.x[0]) if np.isfinite(opt.x[0]) else 0.0
        slope = float(opt.x[1]) if (np.isfinite(opt.x[1]) and opt.x[1] >= 0.0) else 1.0
        calibrated = expit(intercept + slope * logits)
        brier_after = float(brier_score_loss(y.astype(np.int64), calibrated))

        return cls(
            model_family=model_family,
            intercept=intercept,
            slope=slope,
            development_prevalence=dev_prev,
            n_oof_samples=int(y.size),
            oof_brier_before=brier_before,
            oof_brier_after=brier_after,
            status="FITTED_OOF_MONOTONE_LOGISTIC",
            input_link=input_link,
            fit_scope=fit_scope,
        )

    def transform_log_odds(self, raw_logits: np.ndarray | float) -> np.ndarray:
        """Apply exact affine calibration map ``intercept + slope * raw_logits``."""
        arr = np.asarray(raw_logits, dtype=np.float64)
        if not np.isfinite(arr).all():
            raise CalibrationIntegrityError(
                "invalid_raw_logit",
                "Raw log-odds passed to calibrator must be finite.",
            )
        return np.asarray(self.intercept + self.slope * arr, dtype=np.float64)

    def calibrate_from_log_odds(self, raw_logits: np.ndarray | float) -> np.ndarray:
        """Map exact raw log-odds directly to calibrated probabilities via ``expit``."""
        if self.input_link != "exact_raw_log_odds":
            raise CalibrationIntegrityError(
                "calibrator_not_exact_log_odds_link",
                "calibrate_from_log_odds requires a calibrator fitted on exact_raw_log_odds.",
            )
        return np.asarray(expit(self.transform_log_odds(raw_logits)), dtype=np.float64)

    def calibrated_log_odds(
        self,
        raw_probabilities: np.ndarray | float,
        *,
        raw_logits: np.ndarray | float | None = None,
    ) -> np.ndarray:
        """Return calibrated log-odds matching this calibrator's ``input_link``."""
        arr = np.asarray(raw_probabilities, dtype=np.float64)
        if not np.isfinite(arr).all() or np.any((arr < 0.0) | (arr > 1.0)):
            raise CalibrationIntegrityError(
                "invalid_raw_probability",
                "Raw model score passed to calibrator must lie in [0, 1].",
            )
        if self.input_link == "exact_raw_log_odds":
            if raw_logits is None:
                raise CalibrationIntegrityError(
                    "missing_exact_raw_logits",
                    "Calibrator with input_link='exact_raw_log_odds' requires raw_logits so "
                    "clamped probability inversion never introduces truncation error.",
                )
            logits_arr = np.asarray(raw_logits, dtype=np.float64)
            if logits_arr.shape != arr.shape or not np.isfinite(logits_arr).all():
                raise CalibrationIntegrityError(
                    "invalid_raw_logit",
                    "Provided raw_logits must be finite and shape-aligned with raw_probabilities.",
                )
            if not np.allclose(expit(logits_arr), arr, atol=1e-9):
                raise CalibrationIntegrityError(
                    "inconsistent_raw_logits",
                    "Provided raw_logits do not match raw_probabilities under expit.",
                )
            return self.transform_log_odds(logits_arr)

        return self.transform_log_odds(safe_clipped_logit(arr))

    def calibrate(
        self,
        raw_probabilities: np.ndarray | float,
        *,
        raw_logits: np.ndarray | float | None = None,
    ) -> np.ndarray:
        """Map raw model outputs to calibrated probabilities in ``(0, 1)``."""
        return np.asarray(
            expit(self.calibrated_log_odds(raw_probabilities, raw_logits=raw_logits)),
            dtype=np.float64,
        )

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "schema_version": CALIBRATION_SCHEMA_VERSION,
            "method": "oof_monotone_platt_logistic",
            "model_family": self.model_family,
            "input_link": self.input_link,
            "fit_scope": self.fit_scope,
            "status": self.status,
            "intercept": self.intercept,
            "slope": self.slope,
            "development_prevalence": self.development_prevalence,
            "n_oof_samples": self.n_oof_samples,
            "oof_brier_before_apparent_on_fit_oof": self.oof_brier_before,
            "oof_brier_after_apparent_on_fit_oof": self.oof_brier_after,
            "fitted_strictly_out_of_fold": True,
        }

    def to_canonical_json_bytes(self) -> bytes:
        return (
            json.dumps(
                self.to_json_dict(),
                indent=2,
                sort_keys=True,
                ensure_ascii=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")

    @property
    def state_sha256(self) -> str:
        return hashlib.sha256(self.to_canonical_json_bytes()).hexdigest()

    @classmethod
    def from_json_dict(cls, payload: Mapping[str, Any]) -> "OofLogisticCalibrator":
        if not isinstance(payload, Mapping) or (
            payload.get("schema_version") != CALIBRATION_SCHEMA_VERSION
        ):
            raise CalibrationIntegrityError(
                "invalid_calibration_schema",
                "Unsupported or malformed calibration JSON schema.",
            )
        slope = float(payload["slope"])
        intercept = float(payload["intercept"])
        prev = float(payload["development_prevalence"])
        input_link = str(payload.get("input_link", "clipped_logit_of_raw_probability"))
        fit_scope = str(payload.get("fit_scope", "FULL_DEVELOPMENT_OOF_FINAL"))
        if (
            not (math.isfinite(slope) and math.isfinite(intercept) and math.isfinite(prev))
            or slope < 0.0
            or not (0.0 < prev < 1.0)
            or input_link not in VALID_INPUT_LINKS
            or fit_scope not in VALID_FIT_SCOPES
        ):
            raise CalibrationIntegrityError(
                "invalid_calibration_parameters",
                "Calibrator parameters violate monotonicity, link, scope, or prevalence bounds.",
            )
        brier_before = float(
            payload.get(
                "oof_brier_before_apparent_on_fit_oof",
                payload.get("oof_brier_before", 0.0),
            )
        )
        brier_after = float(
            payload.get(
                "oof_brier_after_apparent_on_fit_oof",
                payload.get("oof_brier_after", 0.0),
            )
        )
        return cls(
            model_family=str(payload["model_family"]),
            intercept=intercept,
            slope=slope,
            development_prevalence=prev,
            n_oof_samples=int(payload["n_oof_samples"]),
            oof_brier_before=brier_before,
            oof_brier_after=brier_after,
            status=str(payload["status"]),
            input_link=input_link,
            fit_scope=fit_scope,
        )


def compute_prevalence_shift_diagnostic(
    *,
    development_prevalence: float,
    external_prevalence: float,
) -> dict[str, Any]:
    """Quantify prior-odds log-odds shift between development and external cohorts."""
    dev_clamped = min(
        max(float(development_prevalence), PROB_CLIP_EPS), 1.0 - PROB_CLIP_EPS
    )
    ext_clamped = min(
        max(float(external_prevalence), PROB_CLIP_EPS), 1.0 - PROB_CLIP_EPS
    )
    prior_log_odds_shift = float(
        (math.log(ext_clamped / (1.0 - ext_clamped)))
        - (math.log(dev_clamped / (1.0 - dev_clamped)))
    )
    return {
        "development_prevalence": float(development_prevalence),
        "external_prevalence": float(external_prevalence),
        "absolute_prevalence_difference": float(
            external_prevalence - development_prevalence
        ),
        "theoretical_prior_log_odds_shift": prior_log_odds_shift,
        "external_recalibration_applied_to_primary_metrics": False,
        "note": (
            "Primary external metrics evaluate the locked model + development calibrator "
            "as-is so transport miscalibration under prevalence shift is exposed rather than hidden."
        ),
    }


def _summarize_1d_scores(scores: np.ndarray) -> dict[str, float]:
    q75, q25 = np.percentile(scores, [75.0, 25.0])
    return {
        "mean": float(np.mean(scores)),
        "std": float(np.std(scores, ddof=0)),
        "min": float(np.min(scores)),
        "max": float(np.max(scores)),
        "range": float(np.max(scores) - np.min(scores)),
        "iqr": float(q75 - q25),
    }


def compute_fold_prediction_dispersion(
    fold_raw_scores: Sequence[float],
    fold_compatible_calibrated_scores: Sequence[float],
    *,
    fold_model_families: Sequence[str],
    missing_fields_with_reason: Sequence[tuple[str, str]],
    total_fields: int,
    development_prevalence: float,
) -> dict[str, Any]:
    """Summarize descriptive outer-fold model dispersion and input completeness.

    Scientific contract:
    - Each outer-fold model's raw score is calibrated ONLY by that same outer
      fold's inner-OOF-fitted calibrator (never applying a final-family calibrator
      across heterogeneous fold model families).
    - Results are explicitly labeled as descriptive outer-fold model dispersion
      across overlapping CV partitions—NOT validated epistemic uncertainty, NOT a
      patient-specific coverage interval, and WITHOUT any unvalidated action or
      uncertainty cutoff.
    """
    raw_arr = np.asarray(list(fold_raw_scores), dtype=np.float64)
    cal_arr = np.asarray(list(fold_compatible_calibrated_scores), dtype=np.float64)
    fams = [str(f) for f in fold_model_families]

    if (
        raw_arr.size == 0
        or raw_arr.shape != cal_arr.shape
        or len(fams) != raw_arr.size
        or not np.isfinite(raw_arr).all()
        or not np.isfinite(cal_arr).all()
        or np.any((raw_arr < 0.0) | (raw_arr > 1.0))
        or np.any((cal_arr < 0.0) | (cal_arr > 1.0))
    ):
        raise CalibrationIntegrityError(
            "invalid_fold_dispersion_inputs",
            "Outer-fold dispersion requires >= 1 aligned finite raw/calibrated scores in [0, 1].",
        )

    missing_names = [name for name, _ in missing_fields_with_reason]
    present_count = total_fields - len(missing_names)
    completeness = float(present_count / total_fields) if total_fields > 0 else 1.0
    homogeneous = len(set(fams)) == 1

    limitations: list[str] = [
        "Descriptive dispersion across outer-fold models trained on overlapping CV partitions; "
        "NOT a validated epistemic uncertainty estimate, posterior credible interval, or patient-specific coverage guarantee.",
        f"Calibrated against a development cohort with {development_prevalence:.1%} CAD prevalence; "
        "scores do NOT transfer without recalibration to lower-prevalence outpatient populations.",
        "No clinical action threshold or uncertainty cutoff has been validated (Gate P-4 pending).",
    ]
    if not homogeneous:
        limitations.append(
            "Outer folds selected heterogeneous model families; each fold score uses its own "
            "fold-fitted preprocessor and fold-compatible inner-OOF calibrator, so spread reflects "
            "combined split + family selection variability."
        )
    if missing_names:
        limitations.append(
            f"{len(missing_names)} optional stage field(s) ({', '.join(missing_names)}) were absent "
            "and imputed from training-fold statistics."
        )

    return {
        "uncertainty_semantics": "DESCRIPTIVE_OUTER_FOLD_DISPERSION_NOT_VALIDATED_UNCERTAINTY",
        "validated_epistemic_uncertainty": False,
        "validated_patient_specific_interval": False,
        "action_threshold_validated": False,
        "fold_ensemble_count": int(raw_arr.size),
        "fold_model_families": fams,
        "homogeneous_model_family": homogeneous,
        "each_fold_calibrated_by_own_training_fold_calibrator": True,
        "fold_raw_score_dispersion": _summarize_1d_scores(raw_arr),
        "fold_calibrated_score_dispersion": _summarize_1d_scores(cal_arr),
        "input_completeness": {
            "present_feature_count": int(present_count),
            "total_panel_features": int(total_fields),
            "stage_completeness_fraction": completeness,
            "missing_optional_features": [
                {"field": name, "reason": reason}
                for name, reason in missing_fields_with_reason
            ],
        },
        "limitations": limitations,
    }


# Backwards-compatible alias preserving explicit descriptive-dispersion semantics
compute_instance_uncertainty = compute_fold_prediction_dispersion
