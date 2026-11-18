"""AI-9.1: matched clinical-vs-labs incremental-value exercise, SYNTHETIC ONLY.

The only public runner fabricates a cohort internally. It never consumes a user
file, authenticates a patient, resolves a blocked lab route, or activates the
backend. Its internal alignment helper exists for fail-closed negative tests.

Fold-safe preprocessor, inner hyperparameter selection, logistic estimator and
OOF calibration are REUSED from the existing AI pipeline. A single patient
identity/order and the same outer folds are shared by both panel arms.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Final, Mapping, Sequence

import numpy as np
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import brier_score_loss, roc_auc_score

from ai.calibration import OofLogisticCalibrator, evaluate_comprehensive_metrics
from ai.panels import get_panel_contract, validate_clinical_record
from ai.preprocessing import FoldSafeClinicalPreprocessor
from ai.research_routes import build_synthetic_uci45_resting_cohort
from ai.training import (
    ResearchTrainingConfig,
    _build_estimator,
    _positive_proba_and_optional_logit,
    _select_best_params_and_inner_oof,
)

SCHEMA_VERSION: Final[str] = "cardioassist.ai.synthetic_paired_incremental_value/v1"
CLINICAL_PANEL: Final[str] = "da_a2_resting_v1"
LAB_PANEL: Final[str] = "da_a2_resting_labs_v1"
SOURCE_TOKEN: Final[str] = "ai9_in_process_synthetic"
FAMILY: Final[str] = "l2_logistic_regression"
ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^AI9SYN_[0-9]{5}$")
_ID_FIELDS: Final[frozenset[str]] = frozenset(
    ("id", "label", "target_id", "panel_id", "panel_version", "panel_hash", "record")
)


def _canonical_digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                   allow_nan=False).encode("utf-8")
    ).hexdigest()


def _row(patient_id: str, label: int, panel: Any, record: Mapping[str, Any]) -> dict:
    return {
        "id": patient_id,
        "label": label,
        "target_id": panel.target_id,
        "panel_id": panel.panel_id,
        "panel_version": panel.panel_version,
        "panel_hash": panel.contract_sha256,
        "record": dict(record),
    }


def _fabricate_paired_cohort(*, n_rows: int, seed: int) -> tuple[list[dict], list[dict]]:
    """Internally-generated data only. Synthetic labels precede optional labs."""
    if type(n_rows) is not int or not (96 <= n_rows <= 384):
        raise ValueError("invalid_synthetic_cohort_size")
    if type(seed) is not int or not (0 <= seed < 2**32):
        raise ValueError("invalid_synthetic_seed")
    clinical_panel = get_panel_contract(CLINICAL_PANEL)
    lab_panel = get_panel_contract(LAB_PANEL)
    if (
        clinical_panel.dataset_id != "DA-A2"
        or clinical_panel.target_id != lab_panel.target_id
        or clinical_panel.feature_names != lab_panel.feature_names[:len(clinical_panel.fields)]
        or lab_panel.feature_names[len(clinical_panel.fields):] != ("chol", "fbs")
    ):
        raise ValueError("panel_contract_pair_mismatch")

    base, labels = build_synthetic_uci45_resting_cohort(n_rows, seed=seed)
    rng = np.random.default_rng(seed ^ 0xA9195001)
    clinical: list[dict] = []
    labs: list[dict] = []
    for i, (source, label) in enumerate(zip(base, labels)):
        person_id = f"AI9SYN_{i:05d}"
        clinical_record = {
            **source,
            "context": {"track": "A", "source": SOURCE_TOKEN},
        }
        extra = {
            "chol": (
                None if rng.random() < 0.24
                else float(np.clip(150.0 + 0.65 * (source["features"]["age"] - 45.0)
                                   + rng.normal(0.0, 28.0), 70.0, 340.0))
            ),
            "fbs": None if rng.random() < 0.17 else int(rng.random() < 0.24),
        }
        extended_features = {**source["features"], **extra}
        extended_units = dict(source["units"])
        reasons = {}
        if extra["chol"] is None:
            reasons["chol"] = "not_measured"
        else:
            extended_units["chol"] = "mg/dL"
        if extra["fbs"] is None:
            reasons["fbs"] = "not_measured"
        extended_record = {
            "synthetic": True,
            "panel_id": lab_panel.panel_id,
            "features": extended_features,
            "units": extended_units,
            "missing_reasons": reasons,
            "context": {"track": "A", "source": SOURCE_TOKEN},
        }
        clinical.append(_row(person_id, label, clinical_panel, clinical_record))
        labs.append(_row(person_id, label, lab_panel, extended_record))
    return clinical, labs


def _align_generated_rows(
    clinical: Sequence[Mapping[str, Any]],
    labs: Sequence[Mapping[str, Any]],
) -> tuple[tuple[str, ...], np.ndarray, np.ndarray, np.ndarray, dict[str, int]]:
    """Fail closed on identity, target, ordering, feature, unit and source drift.

    This is an internal synthetic fixture checker, NOT a patient intake API.
    Input record content is never echoed into errors or output.
    """
    cp = get_panel_contract(CLINICAL_PANEL)
    lp = get_panel_contract(LAB_PANEL)
    if (
        cp.target_id != lp.target_id or cp.dataset_id != lp.dataset_id
        or tuple(cp.feature_names) != tuple(lp.feature_names[:len(cp.fields)])
        or tuple(lp.feature_names[len(cp.fields):]) != ("chol", "fbs")
    ):
        raise ValueError("panel_contract_pair_mismatch")
    if not isinstance(clinical, (tuple, list)) or not isinstance(labs, (tuple, list)):
        raise ValueError("invalid_paired_rows")
    if not clinical or len(clinical) != len(labs):
        raise ValueError("unmatched_cohort_count")

    def build_index(rows: Sequence[Mapping[str, Any]], panel: Any) -> dict[str, tuple[int, np.ndarray]]:
        index: dict[str, tuple[int, np.ndarray]] = {}
        for row in rows:
            if not isinstance(row, Mapping) or set(row) != _ID_FIELDS:
                raise ValueError("invalid_synthetic_row")
            pid = row["id"]
            if not isinstance(pid, str) or not ID_PATTERN.fullmatch(pid) or pid in index:
                raise ValueError("invalid_or_duplicate_synthetic_identity")
            if (
                row["panel_id"] != panel.panel_id
                or row["panel_version"] != panel.panel_version
                or row["panel_hash"] != panel.contract_sha256
                or row["target_id"] != panel.target_id
            ):
                raise ValueError("panel_or_target_binding_mismatch")
            label = row["label"]
            if type(label) is not int or label not in (0, 1):
                raise ValueError("invalid_synthetic_target_label")
            payload = row["record"]
            if (
                not isinstance(payload, Mapping)
                or payload.get("synthetic") is not True
                or payload.get("panel_id") != panel.panel_id
                or payload.get("context") != {"track": "A", "source": SOURCE_TOKEN}
                or set(payload.get("features", {})) != set(panel.feature_names)
            ):
                raise ValueError("invalid_synthetic_source_or_features")
            # Reuse the immutable source-specific panel policy, not a second
            # permissive numeric/units/missing-reasons validator.
            values = validate_clinical_record(payload, panel).as_row_array()
            index[pid] = (label, values)
        return index

    c_idx = build_index(clinical, cp)
    l_idx = build_index(labs, lp)
    if set(c_idx) != set(l_idx):
        raise ValueError("unmatched_synthetic_participants")
    ids = tuple(sorted(c_idx))
    y: list[int] = []
    X_clinical: list[np.ndarray] = []
    X_labs: list[np.ndarray] = []
    for pid in ids:
        cy, cx = c_idx[pid]
        ly, lx = l_idx[pid]
        if cy != ly:
            raise ValueError("mismatched_paired_target")
        if not np.array_equal(cx, lx[:len(cx)], equal_nan=True):
            raise ValueError("mismatched_shared_clinical_fields")
        y.append(cy)
        X_clinical.append(cx)
        X_labs.append(lx)
    yy = np.asarray(y, dtype=np.int64)
    count = np.bincount(yy, minlength=2)
    if min(count) < 12:
        raise ValueError("insufficient_synthetic_class_support")
    C = np.asarray(X_clinical, dtype=np.float64)
    L = np.asarray(X_labs, dtype=np.float64)
    missing = {
        name: int(np.isnan(L[:, j]).sum())
        for j, name in enumerate(lp.feature_names)
        if name in ("chol", "fbs")
    }
    return ids, yy, C, L, missing


def _fit_one_fold_arm(
    X: np.ndarray, y: np.ndarray,
    train_idx: np.ndarray, test_idx: np.ndarray,
    *, panel: Any, fold: int, seed: int, cfg: ResearchTrainingConfig,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Inner OOF + calibrator and preprocessor never see the outer test fold."""
    X_tr, y_tr = X[train_idx], y[train_idx]
    params, _, inner_probs, inner_logits = _select_best_params_and_inner_oof(
        X_tr, y_tr, family=FAMILY, panel=panel, config=cfg,
        inner_seed=seed + 1000 * fold + 10,
    )
    prep = FoldSafeClinicalPreprocessor.fit(X_tr, panel)
    E_tr = prep.transform(X_tr)
    E_te = prep.transform(X[test_idx])
    model = _build_estimator(
        FAMILY, params, seed=seed + 5000 * fold,
        rf_n_estimators=cfg.rf_n_estimators,
        execution_profile=cfg.execution_profile,
    )
    model.fit(E_tr, y_tr)
    raw, raw_logits = _positive_proba_and_optional_logit(FAMILY, model, E_te)
    cal = OofLogisticCalibrator.fit_from_oof(
        y_tr, inner_probs, model_family=FAMILY, raw_logits=inner_logits,
        fit_scope="INNER_CV_FOLD_CONTAINED",
    )
    preds = cal.calibrate(raw, raw_logits=raw_logits)
    return preds, {
        "fold": fold,
        "n_train": int(len(train_idx)),
        "n_test": int(len(test_idx)),
        "n_preprocessor_training_rows": prep.n_training_rows,
        "n_calibration_training_rows": cal.n_oof_samples,
        "n_raw_features": prep.n_raw_features,
        "n_encoded_features": prep.n_encoded_features,
        "estimated_fitted_coefficients_and_calibration_parameters": prep.n_encoded_features + 3,
        "hyperparameter_C_selected_on_inner_train_only": float(params["C"]),
        "calibrator_fit_scope": cal.fit_scope,
    }


def _paired_bootstrap(
    y: np.ndarray, clinical: np.ndarray, labs: np.ndarray,
    *, seed: int, n_resamples: int,
) -> dict[str, Any]:
    rng = np.random.default_rng(seed ^ 0xA99130)
    pos = np.flatnonzero(y == 1)
    neg = np.flatnonzero(y == 0)
    auc_deltas: list[float] = []
    brier_deltas: list[float] = []
    for _ in range(n_resamples):
        idx = np.concatenate([
            rng.choice(pos, size=pos.size, replace=True),
            rng.choice(neg, size=neg.size, replace=True),
        ])
        auc_deltas.append(float(roc_auc_score(y[idx], labs[idx]) - roc_auc_score(y[idx], clinical[idx])))
        brier_deltas.append(float(brier_score_loss(y[idx], labs[idx]) - brier_score_loss(y[idx], clinical[idx])))
    return {
        "type": "PAIRED_STRATIFIED_PERCENTILE_BOOTSTRAP_CONDITIONAL_ON_FITTED_OUTER_FOLD_PREDICTIONS",
        "n_resamples": n_resamples,
        "interval": 0.95,
        "uncertainty_limitations": "Does not refit models per resample, does not quantify CV model-selection uncertainty, and is not a clinical confidence interval.",
        "delta_labs_minus_clinical_roc_auc_95_interval": [float(np.percentile(auc_deltas, 2.5)), float(np.percentile(auc_deltas, 97.5))],
        "delta_labs_minus_clinical_brier_95_interval": [float(np.percentile(brier_deltas, 2.5)), float(np.percentile(brier_deltas, 97.5))],
    }


def _compare_generated_rows(
    clinical: Sequence[Mapping[str, Any]],
    labs: Sequence[Mapping[str, Any]],
    *, seed: int, bootstrap_resamples: int,
) -> dict[str, Any]:
    """Internal synthetic test hook; real/patient input is not an executable interface."""
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("invalid_synthetic_seed")
    if type(bootstrap_resamples) is not int or not 40 <= bootstrap_resamples <= 1000:
        raise ValueError("invalid_synthetic_bootstrap_budget")
    ids, y, C, L, missing = _align_generated_rows(clinical, labs)
    cfg = ResearchTrainingConfig(
        outer_folds=3, inner_folds=3, repeat_seeds=(seed,),
        lr_c_grid=(0.1, 1.0), rf_n_estimators=10,
        bootstrap_resamples=bootstrap_resamples,
    )
    splitter = StratifiedKFold(n_splits=cfg.outer_folds, shuffle=True, random_state=seed)
    splits = list(splitter.split(np.zeros(len(y)), y))
    c_out = np.full(len(y), np.nan)
    l_out = np.full(len(y), np.nan)
    fold_data: list[dict[str, Any]] = []
    for fold, (tr, te) in enumerate(splits, start=1):
        clinical_preds, clinical_info = _fit_one_fold_arm(
            C, y, tr, te, panel=get_panel_contract(CLINICAL_PANEL),
            fold=fold, seed=seed, cfg=cfg,
        )
        labs_preds, labs_info = _fit_one_fold_arm(
            L, y, tr, te, panel=get_panel_contract(LAB_PANEL),
            fold=fold, seed=seed, cfg=cfg,
        )
        c_out[te] = clinical_preds
        l_out[te] = labs_preds
        fold_data.append({
            "fold": fold,
            "matched_outer_test_identity_sha256": hashlib.sha256(
                "|".join(ids[i] for i in te).encode("ascii")
            ).hexdigest(),
            "clinical": clinical_info,
            "clinical_plus_labs": labs_info,
        })
    if not np.isfinite(c_out).all() or not np.isfinite(l_out).all():
        raise ValueError("incomplete_outer_oof_predictions")

    c_metrics = evaluate_comprehensive_metrics(
        y, c_out, seed=seed + 1, n_bootstrap=bootstrap_resamples,
        evaluation_scope="AI9_SYNTHETIC_PAIRED_OUTER_OOF",
    )
    l_metrics = evaluate_comprehensive_metrics(
        y, l_out, seed=seed + 1, n_bootstrap=bootstrap_resamples,
        evaluation_scope="AI9_SYNTHETIC_PAIRED_OUTER_OOF",
    )
    def select_metrics(m: dict) -> dict:
        return {
            "roc_auc": m["discrimination"]["roc_auc"],
            "average_precision": m["discrimination"]["average_precision"],
            "brier_score": m["proper_scoring_and_calibration"]["brier_score"],
            "expected_calibration_error_10bin": m["proper_scoring_and_calibration"]["expected_calibration_error_10bin"],
            "cox_diagnostics": m["proper_scoring_and_calibration"]["cox_diagnostics"],
        }

    cm = select_metrics(c_metrics)
    lm = select_metrics(l_metrics)
    paired_bootstrap = _paired_bootstrap(
        y, c_out, l_out, seed=seed, n_resamples=bootstrap_resamples,
    )
    cp, lp = get_panel_contract(CLINICAL_PANEL), get_panel_contract(LAB_PANEL)
    document = {
        "schema_version": SCHEMA_VERSION,
        "status": "SYNTHETIC_INCREMENTAL_VALUE_EXERCISE_COMPLETE",
        "evidence_class": "SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE",
        "source": "IN_PROCESS_FABRICATED_DA_A2_ONLY",
        "target_id": cp.target_id,
        "real_data_execution_authorized": False,
        "clinical_use_authorized": False,
        "labs_route_activated": False,
        "cohort": {
            "n_matched": len(y),
            "n_positive": int(sum(y)),
            "n_negative": int(len(y) - sum(y)),
            "matched_identity_checksum": hashlib.sha256("|".join(ids).encode("ascii")).hexdigest(),
            "lab_missingness": {
                k: {"missing": v, "denominator": len(y), "fraction": v / len(y)}
                for k, v in sorted(missing.items())
            },
        },
        "comparison_plan": {
            "same_source_and_target": True,
            "same_patient_ids": True,
            "same_outer_splits": True,
            "outer_folds": cfg.outer_folds,
            "inner_folds": cfg.inner_folds,
            "seed": seed,
            "model_family_fixed_both_arms": FAMILY,
            "hyperparameters_selected_on_inner_training_folds_only": True,
            "preprocessing_and_calibration_fitted_inside_outer_train_only": True,
            "clinical_panel": {"id": cp.panel_id, "version": cp.panel_version, "sha256": cp.contract_sha256},
            "labs_panel": {"id": lp.panel_id, "version": lp.panel_version, "sha256": lp.contract_sha256},
        },
        "outer_fold_lineage": fold_data,
        "metrics": {"clinical_only": cm, "clinical_plus_labs": lm},
        "paired_deltas_labs_minus_clinical": {
            "roc_auc": float(lm["roc_auc"] - cm["roc_auc"]),
            "brier_score": float(lm["brier_score"] - cm["brier_score"]),
            "expected_calibration_error_10bin_descriptive_only": float(
                lm["expected_calibration_error_10bin"] - cm["expected_calibration_error_10bin"]
            ),
        },
        "paired_uncertainty": paired_bootstrap,
        "feasibility": {
            "status": "SYNTHETIC_FEASIBILITY_ONLY",
            "measured_clinical_lab_timing_or_source_semantics_verified": False,
            "sample_size_adequacy_for_real_study": "NOT_ESTABLISHED",
            "model_complexity_note": "Per-fold encoded coefficient counts are engineering diagnostics, not an evidence-based real-data sample-size decision.",
        },
        "interpretation": "Artificial generated records, not clinical improvement evidence. No automatic favorable-labs claim; no patient outcome, treatment or threshold decision.",
    }
    document["sha256"] = _canonical_digest(document)
    return document


def run_ai9_synthetic_comparison(
    *, seed: int = 20261118, n_rows: int = 120, bootstrap_resamples: int = 64,
) -> dict[str, Any]:
    """Only public execution API: manufacture synthetic records internally."""
    clinical, labs = _fabricate_paired_cohort(n_rows=n_rows, seed=seed)
    return _compare_generated_rows(
        clinical, labs, seed=seed, bootstrap_resamples=bootstrap_resamples,
    )


def comparison_json_bytes() -> bytes:
    return (
        json.dumps(run_ai9_synthetic_comparison(), indent=2, sort_keys=True,
                   ensure_ascii=True, allow_nan=False) + "\n"
    ).encode("utf-8")
