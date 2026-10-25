"""Fold-contained nested-CV selection, negative controls, and locked external evaluation.

Enforces CardioAssist-AI scientific and governance rules in code:
1. Real-data model fitting is blocked while Gate PT (``P-3``) is closed; only
   explicitly synthetic cohorts (``synthetic_data_confirmed=True`` and every
   record carrying ``synthetic: True``) execute now.
2. Cohort pooling (e.g., concatenating UCI-45 sites or UCI-412 + UCI-411) is
   rejected fail-closed.
3. Every imputation, scaling, reference-coding, hyperparameter grid search,
   model-family selection, and probability calibration step is strictly
   fold-contained on development data.
4. ``evaluate_locked_external_cohort`` accepts only an already-frozen
   ``TrainedResearchRun`` and enforces non-overlapping cohort provenance—making
   it structurally impossible to use an external assessment cohort (such as
   Hungary) for model selection, tuning, or recalibration.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, Mapping, Sequence

import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold

from ai.calibration import (
    OofLogisticCalibrator,
    compute_prevalence_shift_diagnostic,
    evaluate_comprehensive_metrics,
)
from ai.errors import CohortGovernanceError
from ai.explainability import ShapBackgroundReference
from ai.panels import (
    ResearchPanelContract,
    validate_cohort_records,
)
from ai.preprocessing import FoldSafeClinicalPreprocessor
from research.uci412.evaluation import choose_model_family

CANDIDATE_FAMILIES: Final[tuple[str, ...]] = (
    "l2_logistic_regression",
    "constrained_random_forest",
)

PROHIBITED_COHORT_TOKENS: Final[tuple[str, ...]] = (
    "pooled",
    "merged",
    "combined",
    "+",
)

PROHIBITED_OVERLAPPING_PAIRS: Final[frozenset[frozenset[str]]] = frozenset(
    {
        frozenset({"da-a1", "da-b1"}),
        frozenset({"uci-412", "uci-411"}),
        frozenset({"uci412", "uci411"}),
        frozenset({"cleveland", "statlog"}),
        frozenset({"da-a2:cleveland", "uci-145"}),
    }
)

PROHIBITED_NON_T1_EXTERNAL_TOKENS: Final[tuple[str, ...]] = (
    "uci-411",
    "da-b1",
    "statlog",
    "uci-145",
    "brfss",
    "nhanes",
    "framingham",
    "ptb-xl",
    "kaggle",
)


@dataclass(frozen=True, slots=True)
class ResearchTrainingConfig:
    """Deterministic configuration for nested CV, calibration, and SHAP background."""

    protocol_id: str = "CAI-AI1-SYNTHETIC-RESEARCH-PIPELINE-V1"
    model_version: str = "0.1.0"
    outer_folds: int = 4
    inner_folds: int = 3
    repeat_seeds: tuple[int, ...] = (20261025,)
    shuffle_control_seeds: tuple[int, ...] = (20261101,)
    shuffle_max_allowed_auroc: float = 0.65
    auc_simplicity_tolerance: float = 0.005
    lr_c_grid: tuple[float, ...] = (0.01, 0.1, 1.0, 10.0)
    rf_max_depths: tuple[int, ...] = (2, 3, 4)
    rf_min_samples_leaf: tuple[int, ...] = (5, 10)
    rf_n_estimators: int = 50
    bootstrap_resamples: int = 250
    shap_max_background_samples: int = 64
    exploratory_threshold: float = 0.5


@dataclass(frozen=True, slots=True)
class FoldEnsembleMember:
    """Single outer-fold (preprocessor, estimator) pair retained for epistemic spread."""

    fold_index: int
    model_family: str
    preprocessor: FoldSafeClinicalPreprocessor
    estimator: Any


@dataclass(frozen=True, slots=True)
class TrainedResearchRun:
    """Frozen output of development-cohort nested-CV evaluation and refit."""

    model_id: str
    model_version: str
    protocol_id: str
    panel: ResearchPanelContract
    development_cohort_id: str
    development_dataset_id: str
    synthetic_only: bool
    selected_model_family: str
    selected_hyperparameters: Mapping[str, Any]
    preprocessor: FoldSafeClinicalPreprocessor
    estimator: Any
    calibrator: OofLogisticCalibrator
    shap_background: ShapBackgroundReference
    fold_ensemble: tuple[FoldEnsembleMember, ...]
    internal_evaluation: Mapping[str, Any]
    negative_control: Mapping[str, Any]


def _validate_cohort_provenance_token(token: str, *, field_name: str) -> str:
    cleaned = token.strip()
    if not cleaned:
        raise CohortGovernanceError(
            "empty_cohort_identifier",
            f"'{field_name}' must be a non-empty cohort identifier.",
            field=field_name,
        )
    lowered = cleaned.lower()
    if any(bad in lowered for bad in PROHIBITED_COHORT_TOKENS):
        raise CohortGovernanceError(
            "cohort_pooling_prohibited",
            f"Pooled or merged cohort identifier in '{field_name}' is prohibited.",
            field=field_name,
        )
    return cleaned


def _build_estimator(
    family: str,
    params: Mapping[str, Any],
    *,
    seed: int,
    rf_n_estimators: int,
) -> Any:
    if family == "l2_logistic_regression":
        return LogisticRegression(
            penalty="l2",
            C=float(params["C"]),
            solver="lbfgs",
            max_iter=1000,
            random_state=int(seed),
        )
    if family == "constrained_random_forest":
        return RandomForestClassifier(
            n_estimators=int(rf_n_estimators),
            max_depth=int(params["max_depth"]),
            min_samples_leaf=int(params["min_samples_leaf"]),
            max_features="sqrt",
            random_state=int(seed),
            n_jobs=1,
        )
    if family == "prevalence_dummy":
        return DummyClassifier(strategy="prior")
    raise ValueError(f"Unsupported model family: {family}")


def _parameter_grid(family: str, config: ResearchTrainingConfig) -> list[dict[str, Any]]:
    if family == "l2_logistic_regression":
        return [{"C": float(c)} for c in config.lr_c_grid]
    if family == "constrained_random_forest":
        return [
            {"max_depth": int(d), "min_samples_leaf": int(leaf)}
            for d in config.rf_max_depths
            for leaf in config.rf_min_samples_leaf
        ]
    raise ValueError(f"No hyperparameter grid for family: {family}")


def _positive_proba(estimator: Any, Z: np.ndarray) -> np.ndarray:
    probs = estimator.predict_proba(Z)
    classes = list(estimator.classes_)
    pos_idx = classes.index(1)
    return np.asarray(probs[:, pos_idx], dtype=np.float64)


def _select_best_params_inner_cv(
    X_outer_train: np.ndarray,
    y_outer_train: np.ndarray,
    *,
    family: str,
    panel: ResearchPanelContract,
    config: ResearchTrainingConfig,
    inner_seed: int,
) -> tuple[dict[str, Any], float]:
    splitter = StratifiedKFold(
        n_splits=config.inner_folds,
        shuffle=True,
        random_state=int(inner_seed),
    )
    splits = list(splitter.split(np.zeros(len(y_outer_train)), y_outer_train))
    grid = _parameter_grid(family, config)

    best_params = grid[0]
    best_auc = -1.0

    for cand_idx, params in enumerate(grid):
        fold_aucs: list[float] = []
        for split_idx, (tr_idx, val_idx) in enumerate(splits):
            prep = FoldSafeClinicalPreprocessor.fit(X_outer_train[tr_idx], panel)
            Z_tr = prep.transform(X_outer_train[tr_idx])
            Z_val = prep.transform(X_outer_train[val_idx])
            est = _build_estimator(
                family,
                params,
                seed=inner_seed + 100 * cand_idx + split_idx + 1,
                rf_n_estimators=config.rf_n_estimators,
            )
            est.fit(Z_tr, y_outer_train[tr_idx])
            p_val = _positive_proba(est, Z_val)
            fold_aucs.append(float(roc_auc_score(y_outer_train[val_idx], p_val)))
        mean_auc = float(np.mean(fold_aucs))
        if mean_auc > best_auc + 1e-12:
            best_auc = mean_auc
            best_params = params

    return dict(best_params), best_auc


def _run_single_nested_pass(
    X: np.ndarray,
    y: np.ndarray,
    *,
    panel: ResearchPanelContract,
    config: ResearchTrainingConfig,
    repeat_seed: int,
    retain_fold_models: bool,
) -> tuple[dict[str, np.ndarray], list[dict[str, Any]], list[FoldEnsembleMember]]:
    outer_splitter = StratifiedKFold(
        n_splits=config.outer_folds,
        shuffle=True,
        random_state=int(repeat_seed),
    )
    oof_scores: dict[str, np.ndarray] = {
        "prevalence_dummy": np.zeros(len(y), dtype=np.float64),
        "l2_logistic_regression": np.zeros(len(y), dtype=np.float64),
        "constrained_random_forest": np.zeros(len(y), dtype=np.float64),
        "inner_selected_procedure": np.zeros(len(y), dtype=np.float64),
    }
    fold_records: list[dict[str, Any]] = []
    fold_ensemble: list[FoldEnsembleMember] = []

    for fold_idx, (train_idx, test_idx) in enumerate(
        outer_splitter.split(np.zeros(len(y)), y), start=1
    ):
        X_tr, y_tr = X[train_idx], y[train_idx]
        X_te = X[test_idx]

        outer_prep = FoldSafeClinicalPreprocessor.fit(X_tr, panel)
        Z_tr = outer_prep.transform(X_tr)
        Z_te = outer_prep.transform(X_te)

        dummy = _build_estimator("prevalence_dummy", {}, seed=repeat_seed, rf_n_estimators=1)
        dummy.fit(Z_tr, y_tr)
        oof_scores["prevalence_dummy"][test_idx] = _positive_proba(dummy, Z_te)

        inner_aucs: dict[str, float] = {}
        best_params_by_fam: dict[str, dict[str, Any]] = {}
        fitted_by_fam: dict[str, Any] = {}

        for fam_offset, family in enumerate(CANDIDATE_FAMILIES, start=1):
            best_params, best_inner_auc = _select_best_params_inner_cv(
                X_tr,
                y_tr,
                family=family,
                panel=panel,
                config=config,
                inner_seed=repeat_seed + 1000 * fold_idx + 10 * fam_offset,
            )
            inner_aucs[family] = best_inner_auc
            best_params_by_fam[family] = best_params
            est = _build_estimator(
                family,
                best_params,
                seed=repeat_seed + 5000 * fold_idx + fam_offset,
                rf_n_estimators=config.rf_n_estimators,
            )
            est.fit(Z_tr, y_tr)
            fitted_by_fam[family] = est
            oof_scores[family][test_idx] = _positive_proba(est, Z_te)

        chosen_family = choose_model_family(
            inner_aucs,
            tolerance=config.auc_simplicity_tolerance,
        )
        oof_scores["inner_selected_procedure"][test_idx] = oof_scores[chosen_family][test_idx]
        fold_records.append(
            {
                "outer_fold": fold_idx,
                "n_train": int(len(train_idx)),
                "n_test": int(len(test_idx)),
                "inner_cv_roc_auc": dict(inner_aucs),
                "selected_family": chosen_family,
                "selected_hyperparameters": dict(best_params_by_fam[chosen_family]),
            }
        )
        if retain_fold_models:
            fold_ensemble.append(
                FoldEnsembleMember(
                    fold_index=fold_idx,
                    model_family=chosen_family,
                    preprocessor=outer_prep,
                    estimator=fitted_by_fam[chosen_family],
                )
            )

    return oof_scores, fold_records, fold_ensemble


def train_research_model(
    records: Sequence[Mapping[str, Any]],
    labels: Sequence[int],
    panel: ResearchPanelContract,
    *,
    model_id: str,
    development_cohort_id: str,
    development_dataset_id: str | None = None,
    pooled_cohorts: bool = False,
    synthetic_data_confirmed: bool = False,
    config: ResearchTrainingConfig = ResearchTrainingConfig(),
) -> TrainedResearchRun:
    """Execute fold-contained nested CV, negative control, OOF calibration, and refit."""
    if not synthetic_data_confirmed:
        raise CohortGovernanceError(
            "gate_pt_closed_real_training_blocked",
            "Gate PT (P-3) remains closed; real-patient model artifact fitting is not authorized.",
            field="synthetic_data_confirmed",
        )
    if pooled_cohorts:
        raise CohortGovernanceError(
            "cohort_pooling_prohibited",
            "Pooling multiple cohorts to inflate sample size is strictly prohibited.",
            field="pooled_cohorts",
        )

    dev_cohort = _validate_cohort_provenance_token(
        development_cohort_id, field_name="development_cohort_id"
    )
    dev_dataset = _validate_cohort_provenance_token(
        development_dataset_id or panel.dataset_id,
        field_name="development_dataset_id",
    )

    X, y, _ = validate_cohort_records(
        records,
        labels,
        panel,
        require_synthetic=True,
    )
    _, counts = np.unique(y, return_counts=True)
    min_class = int(counts.min())
    min_required = config.outer_folds * config.inner_folds
    if min_class < min_required:
        raise CohortGovernanceError(
            "insufficient_minority_events_for_nested_cv",
            f"Minority class count ({min_class}) is below nested-CV floor ({min_required}).",
            field="labels",
        )

    # 1. Repeated nested-CV internal evaluation
    repeat_summaries: list[dict[str, Any]] = []
    primary_oof_by_model: dict[str, np.ndarray] | None = None
    primary_fold_ensemble: list[FoldEnsembleMember] = []
    selection_counts: dict[str, int] = {fam: 0 for fam in CANDIDATE_FAMILIES}

    for rep_idx, seed in enumerate(config.repeat_seeds):
        oof_scores, fold_records, fold_models = _run_single_nested_pass(
            X,
            y,
            panel=panel,
            config=config,
            repeat_seed=seed,
            retain_fold_models=(rep_idx == 0),
        )
        if rep_idx == 0:
            primary_oof_by_model = oof_scores
            primary_fold_ensemble = fold_models
        for rec in fold_records:
            selection_counts[rec["selected_family"]] += 1

        per_model_metrics = {
            name: evaluate_comprehensive_metrics(
                y,
                scores,
                seed=seed + 77,
                n_bootstrap=config.bootstrap_resamples,
                threshold=config.exploratory_threshold,
                evaluation_scope="INTERNAL_NESTED_CV_OUT_OF_FOLD_UNRECALIBRATED",
            )
            for name, scores in oof_scores.items()
        }
        repeat_summaries.append(
            {
                "repeat_seed": int(seed),
                "fold_selections": fold_records,
                "models": per_model_metrics,
            }
        )

    assert primary_oof_by_model is not None

    # 2. Label-shuffle negative control (must not show spurious signal / leakage)
    shuffle_aucs: list[float] = []
    for shuf_seed in config.shuffle_control_seeds:
        rng = np.random.default_rng(int(shuf_seed))
        y_perm = rng.permutation(y)
        perm_oof, _, _ = _run_single_nested_pass(
            X,
            y_perm,
            panel=panel,
            config=config,
            repeat_seed=int(shuf_seed) + 17,
            retain_fold_models=False,
        )
        shuffle_aucs.append(float(roc_auc_score(y_perm, perm_oof["inner_selected_procedure"])))

    max_shuffle_auc = float(max(shuffle_aucs))
    if max_shuffle_auc >= config.shuffle_max_allowed_auroc:
        raise CohortGovernanceError(
            "label_shuffle_leakage_alarm",
            "Label-permutation negative control exceeded leakage ceiling; run discarded.",
        )

    negative_control = {
        "shuffle_seeds": [int(s) for s in config.shuffle_control_seeds],
        "permuted_selected_roc_aucs": shuffle_aucs,
        "max_permuted_roc_auc": max_shuffle_auc,
        "ceiling": float(config.shuffle_max_allowed_auroc),
        "leakage_alarm_triggered": False,
    }

    # 3. Full-development-cohort inner-CV selection + leak-free OOF calibration
    full_cv_seed = int(config.repeat_seeds[0]) + 90000
    full_aucs: dict[str, float] = {}
    full_best_params: dict[str, dict[str, Any]] = {}
    for fam_offset, family in enumerate(CANDIDATE_FAMILIES, start=1):
        params, auc_val = _select_best_params_inner_cv(
            X,
            y,
            family=family,
            panel=panel,
            config=config,
            inner_seed=full_cv_seed + 10 * fam_offset,
        )
        full_aucs[family] = auc_val
        full_best_params[family] = params

    selected_family = choose_model_family(
        full_aucs,
        tolerance=config.auc_simplicity_tolerance,
    )
    selected_params = full_best_params[selected_family]

    # Collect strictly out-of-fold raw probabilities for the chosen (family, params)
    # to fit OofLogisticCalibrator without in-sample optimism.
    cal_splitter = StratifiedKFold(
        n_splits=config.outer_folds,
        shuffle=True,
        random_state=full_cv_seed + 333,
    )
    oof_for_cal = np.zeros(len(y), dtype=np.float64)
    for fold_idx, (tr_idx, val_idx) in enumerate(
        cal_splitter.split(np.zeros(len(y)), y), start=1
    ):
        prep_k = FoldSafeClinicalPreprocessor.fit(X[tr_idx], panel)
        est_k = _build_estimator(
            selected_family,
            selected_params,
            seed=full_cv_seed + 1000 * fold_idx,
            rf_n_estimators=config.rf_n_estimators,
        )
        est_k.fit(prep_k.transform(X[tr_idx]), y[tr_idx])
        oof_for_cal[val_idx] = _positive_proba(est_k, prep_k.transform(X[val_idx]))

    calibrator = OofLogisticCalibrator.fit_from_oof(
        y,
        oof_for_cal,
        model_family=selected_family,
    )
    calibrated_oof_metrics = evaluate_comprehensive_metrics(
        y,
        calibrator.calibrate(oof_for_cal),
        seed=full_cv_seed + 555,
        n_bootstrap=config.bootstrap_resamples,
        threshold=config.exploratory_threshold,
        evaluation_scope="INTERNAL_OUT_OF_FOLD_CALIBRATED_SELECTED_FAMILY",
    )

    # 4. Final refit on development cohort + deterministic SHAP background
    final_preprocessor = FoldSafeClinicalPreprocessor.fit(X, panel)
    Z_full = final_preprocessor.transform(X)
    final_estimator = _build_estimator(
        selected_family,
        selected_params,
        seed=full_cv_seed + 9999,
        rf_n_estimators=config.rf_n_estimators,
    )
    final_estimator.fit(Z_full, y)
    shap_bg = ShapBackgroundReference.from_training_encoded(
        Z_full,
        y,
        final_preprocessor,
        max_samples=config.shap_max_background_samples,
        seed=full_cv_seed + 4242,
    )

    selected_repeat_aucs = [
        rep["models"]["inner_selected_procedure"]["discrimination"]["roc_auc"]
        for rep in repeat_summaries
    ]
    internal_summary = {
        "evaluation_design": f"repeated_{config.outer_folds}x{config.inner_folds}_nested_stratified_cv",
        "development_cohort_id": dev_cohort,
        "development_dataset_id": dev_dataset,
        "pooled_cohorts": False,
        "n_participants": int(len(y)),
        "n_positive": int(np.sum(y == 1)),
        "n_negative": int(np.sum(y == 0)),
        "repeat_count": len(repeat_summaries),
        "outer_fold_family_selection_counts": selection_counts,
        "inner_selected_roc_auc_mean_across_repeats": float(np.mean(selected_repeat_aucs)),
        "inner_selected_roc_auc_sd_across_repeats": float(
            np.std(selected_repeat_aucs, ddof=0)
        ),
        "full_cohort_cv_family_roc_aucs": full_aucs,
        "selected_model_family": selected_family,
        "selected_hyperparameters": selected_params,
        "calibrated_selected_oof_metrics": calibrated_oof_metrics,
        "repeats": repeat_summaries,
        "caveats": [
            "Internal nested-CV results estimate within-cohort discrimination/calibration only; not external validation.",
            "Repeats reuse the same synthetic/development participants; multi-repeat counts never multiply sample size.",
            "Probabilities reflect cohort referral prevalence and are NOT clinically validated individual CAD risks.",
        ],
    }

    return TrainedResearchRun(
        model_id=model_id,
        model_version=config.model_version,
        protocol_id=config.protocol_id,
        panel=panel,
        development_cohort_id=dev_cohort,
        development_dataset_id=dev_dataset,
        synthetic_only=True,
        selected_model_family=selected_family,
        selected_hyperparameters=selected_params,
        preprocessor=final_preprocessor,
        estimator=final_estimator,
        calibrator=calibrator,
        shap_background=shap_bg,
        fold_ensemble=tuple(primary_fold_ensemble),
        internal_evaluation=internal_summary,
        negative_control=negative_control,
    )


def evaluate_locked_external_cohort(
    trained_run: TrainedResearchRun,
    external_records: Sequence[Mapping[str, Any]],
    external_labels: Sequence[int],
    *,
    external_cohort_id: str,
    external_dataset_id: str,
    synthetic_data_confirmed: bool = False,
    seed: int = 20261201,
    n_bootstrap: int = 250,
) -> dict[str, Any]:
    """Evaluate an already-frozen ``TrainedResearchRun`` once on a locked external cohort.

    Enforces:
    - Synthetic-only gate while Gate PT is closed.
    - Disjoint cohort provenance (rejects same-cohort, UCI-412/UCI-411 overlap,
      Cleveland/Statlog suspect overlap, pooled tokens, and non-angiographic
      T3/T4/T5 datasets).
    - Zero refitting, zero hyperparameter/family re-selection, and zero
      recalibration on the external cohort.
    """
    if not synthetic_data_confirmed:
        raise CohortGovernanceError(
            "gate_pt_closed_external_evaluation_blocked",
            "Gate PT (P-3) remains closed; real external cohort evaluation is not yet authorized.",
            field="synthetic_data_confirmed",
        )
    ext_cohort = _validate_cohort_provenance_token(
        external_cohort_id, field_name="external_cohort_id"
    )
    ext_dataset = _validate_cohort_provenance_token(
        external_dataset_id, field_name="external_dataset_id"
    )

    dev_cohort_norm = trained_run.development_cohort_id.lower()
    ext_cohort_norm = ext_cohort.lower()
    dev_ds_norm = trained_run.development_dataset_id.lower()
    ext_ds_norm = ext_dataset.lower()

    if ext_cohort_norm == dev_cohort_norm:
        raise CohortGovernanceError(
            "external_cohort_identical_to_development",
            "External evaluation cohort must be distinct from the development cohort.",
            field="external_cohort_id",
        )
    for bad_tok in PROHIBITED_NON_T1_EXTERNAL_TOKENS:
        if bad_tok in ext_cohort_norm or bad_tok in ext_ds_norm:
            raise CohortGovernanceError(
                "prohibited_external_cohort",
                f"Cohort '{ext_cohort}' / '{ext_dataset}' is prohibited for T1 external CAD validation.",
                field="external_cohort_id",
            )
    for pair in (
        frozenset({dev_cohort_norm, ext_cohort_norm}),
        frozenset({dev_ds_norm, ext_ds_norm}),
    ):
        if pair in PROHIBITED_OVERLAPPING_PAIRS:
            raise CohortGovernanceError(
                "overlapping_cohort_prohibited",
                "Development and external cohorts have documented or suspected participant overlap.",
                field="external_cohort_id",
            )

    X_ext, y_ext, validated_ext = validate_cohort_records(
        external_records,
        external_labels,
        trained_run.panel,
        require_synthetic=True,
    )
    # Apply LOCKED development preprocessor, estimator, and calibrator without modification
    Z_ext = trained_run.preprocessor.transform(X_ext)
    p_ext_raw = _positive_proba(trained_run.estimator, Z_ext)
    p_ext_cal = trained_run.calibrator.calibrate(p_ext_raw)

    metrics = evaluate_comprehensive_metrics(
        y_ext,
        p_ext_cal,
        seed=seed,
        n_bootstrap=n_bootstrap,
        evaluation_scope="LOCKED_INDEPENDENT_COHORT_TRANSPORT_RESEARCH_ONLY",
    )
    shift_diag = compute_prevalence_shift_diagnostic(
        development_prevalence=trained_run.calibrator.development_prevalence,
        external_prevalence=float(np.mean(y_ext)),
    )
    complete_count = sum(1 for item in validated_ext if item.stage_complete)

    return {
        "evaluation_type": "LOCKED_EXTERNAL_COHORT_ASSESSMENT",
        "model_id": trained_run.model_id,
        "model_version": trained_run.model_version,
        "selected_model_family": trained_run.selected_model_family,
        "development_cohort_id": trained_run.development_cohort_id,
        "development_dataset_id": trained_run.development_dataset_id,
        "external_cohort_id": ext_cohort,
        "external_dataset_id": ext_dataset,
        "pooled_with_development": False,
        "used_for_feature_or_model_or_threshold_selection": False,
        "external_stage_complete_records": int(complete_count),
        "external_total_records": int(len(validated_ext)),
        "prevalence_shift_diagnostic": shift_diag,
        "locked_transport_metrics": metrics,
        "limitations": [
            "Locked external transport assessment only; external cohort never influenced training, selection, or calibration.",
            "Transported probabilities retain development-cohort prevalence calibration unless separately recalibrated under a clinical protocol.",
            "Synthetic/research evaluation only; not clinical validation.",
        ],
    }
