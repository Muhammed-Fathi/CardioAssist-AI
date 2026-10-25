"""Fold-contained nested-CV selection, cross-fitted calibration, negative controls,
and frozen external-cohort evaluation.

Enforces CardioAssist-AI scientific and governance rules in code:
1. Real-data model fitting and real external cohort evaluation (including real
   Hungary and real AngioCAD) are blocked while Gate PT (``P-3``) and ``D-021``
   are unresolved; only explicitly synthetic cohorts (``synthetic_data_confirmed=True``
   and every record carrying ``synthetic: True``) execute now.
2. Cohort pooling (e.g., concatenating UCI-45 sites or UCI-412 + UCI-411) is
   rejected fail-closed.
3. Internal evaluation strictly separates THREE distinct quantities:
   - **Uncalibrated nested-CV performance** (raw outer-fold probabilities).
   - **Independently evaluated cross-fitted calibrated nested-CV performance**:
     inside each outer fold, hyperparameters, model family, AND ``OofLogisticCalibrator``
     are fitted strictly on inner-CV predictions within ``train_idx`` so every
     evaluated observation in ``test_idx`` is excluded from fitting both its
     prediction model and its calibrator.
   - **Final development-OOF calibrator** (fitted on development OOF predictions
     for future inference/transport in ``calibration.json``), whose in-calibrator
     resubstitution summary is explicitly labeled as an *apparent diagnostic*,
     never an unbiased calibrated performance estimate.
4. ``evaluate_locked_external_cohort`` is documented honestly as a frozen-model
   evaluation primitive unless paired with ``one_shot_ledger_path``
   (:class:`ExternalEvaluationLedger`), which enforces local single-shot execution
   per ``(protocol_id, external_cohort_id)`` and ``(model_id, external_cohort_id)``.
   String-based cohort provenance checks are metadata guards only, never proof of
   participant-level non-overlap.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
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

REPOSITORY_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
EXTERNAL_EVAL_LEDGER_SCHEMA: Final[str] = "cardioassist.ai.external_eval_ledger/v1"

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
    """Deterministic configuration for nested CV, cross-fitted calibration, and SHAP."""

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
    """Single outer-fold (preprocessor, estimator, fold-compatible calibrator) triple."""

    fold_index: int
    model_family: str
    preprocessor: FoldSafeClinicalPreprocessor
    estimator: Any
    calibrator: OofLogisticCalibrator


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


def _enforce_synthetic_cohort_identifier_guard(
    cohort_id: str,
    dataset_id: str,
    *,
    field_name: str,
) -> None:
    """Block real Hungary or AngioCAD cohort identifiers under synthetic-only authorization."""
    c_low = cohort_id.lower()
    d_low = dataset_id.lower()
    if ("angiocad" in c_low or "angiocad" in d_low) and "synthetic" not in c_low:
        raise CohortGovernanceError(
            "angiocad_blocked_pending_d021_and_gate_da",
            "Real AngioCAD evaluation is blocked pending human D-021 decision, "
            "read-only Gate DA file verification, and Gate PT (P-3) authorization.",
            field=field_name,
        )
    if ("hungary" in c_low or "hungarian" in c_low) and "synthetic" not in c_low:
        raise CohortGovernanceError(
            "real_hungary_blocked_pending_gate_pt",
            "Real Hungary external cohort evaluation is blocked while Gate PT (P-3) is closed.",
            field=field_name,
        )


def _ensure_untracked_local_path(target_path: Path, *, purpose: str) -> Path:
    if target_path.is_symlink():
        raise CohortGovernanceError(
            "symlink_ledger_prohibited",
            f"Refusing to use symlinked path for {purpose}.",
        )
    resolved_parent = target_path.parent.resolve()
    resolved = resolved_parent / target_path.name
    try:
        rel = resolved.relative_to(REPOSITORY_ROOT.resolve())
    except ValueError:
        rel = None
    if rel is not None:
        probe = subprocess.run(
            ["git", "check-ignore", "-q", "--", rel.as_posix()],
            cwd=str(REPOSITORY_ROOT),
            check=False,
        )
        if probe.returncode != 0:
            raise CohortGovernanceError(
                "unignored_ledger_path_prohibited",
                f"Refusing to write {purpose} inside a non-ignored repository path.",
            )
    return resolved


class ExternalEvaluationLedger:
    """Locally protected append-only registry enforcing single-shot external evaluation."""

    def __init__(self, ledger_path: Path) -> None:
        self._path = _ensure_untracked_local_path(
            Path(ledger_path), purpose="external evaluation ledger"
        )

    @property
    def path(self) -> Path:
        return self._path

    def _load_entries(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        if self._path.is_symlink():
            raise CohortGovernanceError(
                "symlink_ledger_prohibited",
                "External evaluation ledger must not be a symlink.",
            )
        st = self._path.stat()
        if hasattr(os, "getuid") and st.st_uid != os.getuid():
            raise CohortGovernanceError(
                "untrusted_ledger_owner",
                "External evaluation ledger is not owned by the current local user.",
            )
        if (st.st_mode & 0o077) != 0:
            raise CohortGovernanceError(
                "insecure_ledger_permissions",
                "External evaluation ledger must have user-private (0600) permissions.",
            )
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise CohortGovernanceError(
                "corrupted_external_eval_ledger",
                "External evaluation ledger could not be parsed as valid JSON.",
            ) from exc
        if (
            not isinstance(payload, Mapping)
            or payload.get("schema_version") != EXTERNAL_EVAL_LEDGER_SCHEMA
            or not isinstance(payload.get("entries"), list)
        ):
            raise CohortGovernanceError(
                "invalid_external_eval_ledger_schema",
                "External evaluation ledger has an invalid schema.",
            )
        return list(payload["entries"])

    def record_single_shot(
        self,
        *,
        protocol_id: str,
        model_id: str,
        model_version: str,
        external_cohort_id: str,
        external_dataset_id: str,
        preprocessor_sha256: str,
        calibrator_sha256: str,
        cohort_fingerprint_sha256: str,
    ) -> dict[str, Any]:
        entries = self._load_entries()
        norm_cohort = external_cohort_id.strip().lower()
        for existing in entries:
            same_cohort = str(existing.get("external_cohort_id_norm")) == norm_cohort
            if same_cohort and (
                str(existing.get("protocol_id")) == protocol_id
                or str(existing.get("model_id")) == model_id
            ):
                raise CohortGovernanceError(
                    "one_shot_external_evaluation_already_consumed",
                    f"One-shot external evaluation for cohort '{external_cohort_id}' has "
                    f"already been consumed under protocol '{protocol_id}' / model '{model_id}'.",
                    field="external_cohort_id",
                )

        new_entry = {
            "recorded_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "protocol_id": protocol_id,
            "model_id": model_id,
            "model_version": model_version,
            "external_cohort_id": external_cohort_id,
            "external_cohort_id_norm": norm_cohort,
            "external_dataset_id": external_dataset_id,
            "preprocessor_sha256": preprocessor_sha256,
            "calibrator_sha256": calibrator_sha256,
            "cohort_fingerprint_sha256": cohort_fingerprint_sha256,
        }
        entries.append(new_entry)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        doc = {
            "schema_version": EXTERNAL_EVAL_LEDGER_SCHEMA,
            "entries": entries,
        }
        raw = (
            json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False)
            + "\n"
        ).encode("utf-8")

        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{self._path.name}.", dir=str(self._path.parent)
        )
        tmp_path = Path(tmp_name)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb") as handle:
                handle.write(raw)
                handle.flush()
            os.replace(tmp_path, self._path)
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise

        return new_entry


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


def _parameter_grid(
    family: str, config: ResearchTrainingConfig
) -> list[dict[str, Any]]:
    if family == "l2_logistic_regression":
        return [{"C": float(c)} for c in config.lr_c_grid]
    if family == "constrained_random_forest":
        return [
            {"max_depth": int(d), "min_samples_leaf": int(leaf)}
            for d in config.rf_max_depths
            for leaf in config.rf_min_samples_leaf
        ]
    raise ValueError(f"No hyperparameter grid for family: {family}")


def _positive_proba_and_optional_logit(
    family: str,
    estimator: Any,
    Z: np.ndarray,
) -> tuple[np.ndarray, np.ndarray | None]:
    probs = estimator.predict_proba(Z)
    classes = list(estimator.classes_)
    pos_idx = classes.index(1)
    pos_probs = np.asarray(probs[:, pos_idx], dtype=np.float64)
    if family == "l2_logistic_regression":
        raw_logits = np.asarray(estimator.decision_function(Z), dtype=np.float64)
        return pos_probs, raw_logits
    return pos_probs, None


def _select_best_params_and_inner_oof(
    X_outer_train: np.ndarray,
    y_outer_train: np.ndarray,
    *,
    family: str,
    panel: ResearchPanelContract,
    config: ResearchTrainingConfig,
    inner_seed: int,
) -> tuple[dict[str, Any], float, np.ndarray, np.ndarray | None]:
    """Select hyperparameters strictly inside X_outer_train and retain inner-CV OOF scores."""
    splitter = StratifiedKFold(
        n_splits=config.inner_folds,
        shuffle=True,
        random_state=int(inner_seed),
    )
    splits = list(splitter.split(np.zeros(len(y_outer_train)), y_outer_train))
    grid = _parameter_grid(family, config)

    best_params = grid[0]
    best_auc = -1.0
    best_oof_probs = np.zeros(len(y_outer_train), dtype=np.float64)
    best_oof_logits: np.ndarray | None = (
        np.zeros(len(y_outer_train), dtype=np.float64)
        if family == "l2_logistic_regression"
        else None
    )

    for cand_idx, params in enumerate(grid):
        fold_aucs: list[float] = []
        cand_oof_probs = np.zeros(len(y_outer_train), dtype=np.float64)
        cand_oof_logits: np.ndarray | None = (
            np.zeros(len(y_outer_train), dtype=np.float64)
            if family == "l2_logistic_regression"
            else None
        )
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
            p_val, logits_val = _positive_proba_and_optional_logit(family, est, Z_val)
            cand_oof_probs[val_idx] = p_val
            if cand_oof_logits is not None and logits_val is not None:
                cand_oof_logits[val_idx] = logits_val
            fold_aucs.append(float(roc_auc_score(y_outer_train[val_idx], p_val)))
        mean_auc = float(np.mean(fold_aucs))
        if mean_auc > best_auc + 1e-12:
            best_auc = mean_auc
            best_params = params
            best_oof_probs = cand_oof_probs
            best_oof_logits = cand_oof_logits

    return dict(best_params), best_auc, best_oof_probs, best_oof_logits


def _compute_dummy_inner_oof(
    y_outer_train: np.ndarray,
    *,
    inner_folds: int,
    inner_seed: int,
) -> np.ndarray:
    splitter = StratifiedKFold(
        n_splits=inner_folds,
        shuffle=True,
        random_state=int(inner_seed),
    )
    oof = np.zeros(len(y_outer_train), dtype=np.float64)
    dummy_X = np.zeros((len(y_outer_train), 1), dtype=np.float64)
    for tr_idx, val_idx in splitter.split(dummy_X, y_outer_train):
        est = DummyClassifier(strategy="prior")
        est.fit(dummy_X[tr_idx], y_outer_train[tr_idx])
        probs, _ = _positive_proba_and_optional_logit(
            "prevalence_dummy", est, dummy_X[val_idx]
        )
        oof[val_idx] = probs
    return oof


def _run_single_nested_pass(
    X: np.ndarray,
    y: np.ndarray,
    *,
    panel: ResearchPanelContract,
    config: ResearchTrainingConfig,
    repeat_seed: int,
    retain_fold_models: bool,
    fit_cross_calibrators: bool = True,
) -> tuple[
    dict[str, np.ndarray],
    dict[str, np.ndarray],
    list[dict[str, Any]],
    list[FoldEnsembleMember],
]:
    """Execute one outer/inner nested-CV pass with strictly fold-contained calibration.

    For every outer fold ``(train_idx, test_idx)``:
    - ``outer_prep``, inner hyperparameter tuning, model-family selection, outer
      model fitting, AND ``fold_calibrator`` fitting see ONLY ``train_idx``.
    - Every observation in ``test_idx`` is 100% excluded from fitting both its
      prediction model and its calibrator.
    """
    outer_splitter = StratifiedKFold(
        n_splits=config.outer_folds,
        shuffle=True,
        random_state=int(repeat_seed),
    )
    keys = (
        "prevalence_dummy",
        "l2_logistic_regression",
        "constrained_random_forest",
        "inner_selected_procedure",
    )
    uncalibrated_oof: dict[str, np.ndarray] = {
        k: np.zeros(len(y), dtype=np.float64) for k in keys
    }
    calibrated_oof: dict[str, np.ndarray] = {
        k: np.zeros(len(y), dtype=np.float64) for k in keys
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

        dummy = _build_estimator(
            "prevalence_dummy", {}, seed=repeat_seed, rf_n_estimators=1
        )
        dummy.fit(Z_tr, y_tr)
        p_dummy_te, _ = _positive_proba_and_optional_logit(
            "prevalence_dummy", dummy, Z_te
        )
        uncalibrated_oof["prevalence_dummy"][test_idx] = p_dummy_te

        if fit_cross_calibrators:
            dummy_inner_oof = _compute_dummy_inner_oof(
                y_tr,
                inner_folds=config.inner_folds,
                inner_seed=repeat_seed + 1000 * fold_idx + 1,
            )
            dummy_cal = OofLogisticCalibrator.fit_from_oof(
                y_tr,
                dummy_inner_oof,
                model_family="prevalence_dummy",
                fit_scope="INNER_CV_FOLD_CONTAINED",
            )
            calibrated_oof["prevalence_dummy"][test_idx] = dummy_cal.calibrate(
                p_dummy_te
            )

        inner_aucs: dict[str, float] = {}
        best_params_by_fam: dict[str, dict[str, Any]] = {}
        fitted_by_fam: dict[str, Any] = {}
        calibrators_by_fam: dict[str, OofLogisticCalibrator] = {}

        for fam_offset, family in enumerate(CANDIDATE_FAMILIES, start=1):
            (
                best_params,
                best_inner_auc,
                inner_oof_probs,
                inner_oof_logits,
            ) = _select_best_params_and_inner_oof(
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
            p_te, logits_te = _positive_proba_and_optional_logit(family, est, Z_te)
            uncalibrated_oof[family][test_idx] = p_te

            if fit_cross_calibrators:
                fold_cal = OofLogisticCalibrator.fit_from_oof(
                    y_tr,
                    inner_oof_probs,
                    model_family=family,
                    raw_logits=inner_oof_logits,
                    fit_scope="INNER_CV_FOLD_CONTAINED",
                )
                calibrators_by_fam[family] = fold_cal
                calibrated_oof[family][test_idx] = fold_cal.calibrate(
                    p_te, raw_logits=logits_te
                )

        chosen_family = choose_model_family(
            inner_aucs,
            tolerance=config.auc_simplicity_tolerance,
        )
        uncalibrated_oof["inner_selected_procedure"][test_idx] = uncalibrated_oof[
            chosen_family
        ][test_idx]

        fold_rec: dict[str, Any] = {
            "outer_fold": fold_idx,
            "n_train": int(len(train_idx)),
            "n_test": int(len(test_idx)),
            "inner_cv_roc_auc": dict(inner_aucs),
            "selected_family": chosen_family,
            "selected_hyperparameters": dict(best_params_by_fam[chosen_family]),
        }
        if fit_cross_calibrators:
            chosen_cal = calibrators_by_fam[chosen_family]
            calibrated_oof["inner_selected_procedure"][test_idx] = calibrated_oof[
                chosen_family
            ][test_idx]
            fold_rec["fold_calibrator"] = {
                "model_family": chosen_family,
                "input_link": chosen_cal.input_link,
                "fit_scope": chosen_cal.fit_scope,
                "n_calibrator_fit_samples": int(len(train_idx)),
                "test_fold_excluded_from_calibrator_fit": True,
                "intercept": float(chosen_cal.intercept),
                "slope": float(chosen_cal.slope),
            }
            if retain_fold_models:
                fold_ensemble.append(
                    FoldEnsembleMember(
                        fold_index=fold_idx,
                        model_family=chosen_family,
                        preprocessor=outer_prep,
                        estimator=fitted_by_fam[chosen_family],
                        calibrator=chosen_cal,
                    )
                )

        fold_records.append(fold_rec)

    return uncalibrated_oof, calibrated_oof, fold_records, fold_ensemble


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
    """Execute fold-contained nested CV, cross-fitted calibration, negative control, and refit."""
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
    _enforce_synthetic_cohort_identifier_guard(
        dev_cohort, dev_dataset, field_name="development_cohort_id"
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

    # 1. Repeated nested-CV internal evaluation (BOTH uncalibrated AND cross-fitted calibrated)
    uncalibrated_repeat_summaries: list[dict[str, Any]] = []
    calibrated_repeat_summaries: list[dict[str, Any]] = []
    primary_fold_ensemble: list[FoldEnsembleMember] = []
    selection_counts: dict[str, int] = {fam: 0 for fam in CANDIDATE_FAMILIES}

    for rep_idx, seed in enumerate(config.repeat_seeds):
        (
            uncal_oof_scores,
            cal_oof_scores,
            fold_records,
            fold_models,
        ) = _run_single_nested_pass(
            X,
            y,
            panel=panel,
            config=config,
            repeat_seed=seed,
            retain_fold_models=(rep_idx == 0),
            fit_cross_calibrators=True,
        )
        if rep_idx == 0:
            primary_fold_ensemble = fold_models
        for rec in fold_records:
            selection_counts[rec["selected_family"]] += 1

        uncal_metrics = {
            name: evaluate_comprehensive_metrics(
                y,
                scores,
                seed=seed + 77,
                n_bootstrap=config.bootstrap_resamples,
                threshold=config.exploratory_threshold,
                evaluation_scope="INTERNAL_NESTED_CV_OUT_OF_FOLD_UNCALIBRATED",
            )
            for name, scores in uncal_oof_scores.items()
        }
        cal_metrics = {
            name: evaluate_comprehensive_metrics(
                y,
                scores,
                seed=seed + 177,
                n_bootstrap=config.bootstrap_resamples,
                threshold=config.exploratory_threshold,
                evaluation_scope="INTERNAL_NESTED_CV_CROSS_FITTED_CALIBRATED",
            )
            for name, scores in cal_oof_scores.items()
        }

        uncalibrated_repeat_summaries.append(
            {
                "repeat_seed": int(seed),
                "fold_selections": fold_records,
                "models": uncal_metrics,
            }
        )
        calibrated_repeat_summaries.append(
            {
                "repeat_seed": int(seed),
                "each_observation_excluded_from_model_and_calibrator_fit": True,
                "models": cal_metrics,
            }
        )

    # 2. Label-shuffle negative control (must not show spurious signal / leakage)
    shuffle_aucs: list[float] = []
    for shuf_seed in config.shuffle_control_seeds:
        rng = np.random.default_rng(int(shuf_seed))
        y_perm = rng.permutation(y)
        perm_uncal_oof, _, _, _ = _run_single_nested_pass(
            X,
            y_perm,
            panel=panel,
            config=config,
            repeat_seed=int(shuf_seed) + 17,
            retain_fold_models=False,
            fit_cross_calibrators=False,
        )
        shuffle_aucs.append(
            float(roc_auc_score(y_perm, perm_uncal_oof["inner_selected_procedure"]))
        )

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

    # 3. Full-development-cohort inner-CV selection + final development-OOF calibrator
    #    (stored in calibration.json for future inference / external transport ONLY)
    full_cv_seed = int(config.repeat_seeds[0]) + 90000
    full_aucs: dict[str, float] = {}
    full_best_params: dict[str, dict[str, Any]] = {}
    for fam_offset, family in enumerate(CANDIDATE_FAMILIES, start=1):
        params, auc_val, _, _ = _select_best_params_and_inner_oof(
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

    cal_splitter = StratifiedKFold(
        n_splits=config.outer_folds,
        shuffle=True,
        random_state=full_cv_seed + 333,
    )
    oof_for_cal = np.zeros(len(y), dtype=np.float64)
    oof_logits_for_cal: np.ndarray | None = (
        np.zeros(len(y), dtype=np.float64)
        if selected_family == "l2_logistic_regression"
        else None
    )
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
        p_val, logits_val = _positive_proba_and_optional_logit(
            selected_family, est_k, prep_k.transform(X[val_idx])
        )
        oof_for_cal[val_idx] = p_val
        if oof_logits_for_cal is not None and logits_val is not None:
            oof_logits_for_cal[val_idx] = logits_val

    calibrator = OofLogisticCalibrator.fit_from_oof(
        y,
        oof_for_cal,
        model_family=selected_family,
        raw_logits=oof_logits_for_cal,
        fit_scope="FULL_DEVELOPMENT_OOF_FINAL",
    )
    apparent_cal_probs = calibrator.calibrate(
        oof_for_cal, raw_logits=oof_logits_for_cal
    )
    apparent_calibrator_fit_diagnostic = {
        "apparent_in_calibrator_fit": True,
        "unbiased_calibrated_performance_estimate": False,
        "warning": (
            "Apparent resubstitution diagnostic on the same development OOF predictions "
            "used to fit the 2-parameter final calibrator and after full-cohort family "
            "selection. Do NOT report as unbiased out-of-sample calibrated performance; "
            "use 'cross_fitted_calibrated_nested_cv' instead."
        ),
        "metrics": evaluate_comprehensive_metrics(
            y,
            apparent_cal_probs,
            seed=full_cv_seed + 555,
            n_bootstrap=config.bootstrap_resamples,
            threshold=config.exploratory_threshold,
            evaluation_scope="APPARENT_IN_CALIBRATOR_FIT_DIAGNOSTIC_NOT_UNBIASED",
        ),
    }

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
        synthetic_only=True,
    )

    uncal_selected_aucs = [
        rep["models"]["inner_selected_procedure"]["discrimination"]["roc_auc"]
        for rep in uncalibrated_repeat_summaries
    ]
    uncal_selected_briers = [
        rep["models"]["inner_selected_procedure"]["proper_scoring_and_calibration"][
            "brier_score"
        ]
        for rep in uncalibrated_repeat_summaries
    ]

    cal_selected_aucs = [
        rep["models"]["inner_selected_procedure"]["discrimination"]["roc_auc"]
        for rep in calibrated_repeat_summaries
    ]
    cal_selected_briers = [
        rep["models"]["inner_selected_procedure"]["proper_scoring_and_calibration"][
            "brier_score"
        ]
        for rep in calibrated_repeat_summaries
    ]
    cal_selected_eces = [
        rep["models"]["inner_selected_procedure"]["proper_scoring_and_calibration"][
            "expected_calibration_error_10bin"
        ]
        for rep in calibrated_repeat_summaries
    ]
    cal_selected_log_losses = [
        rep["models"]["inner_selected_procedure"]["proper_scoring_and_calibration"][
            "log_loss"
        ]
        for rep in calibrated_repeat_summaries
    ]

    internal_summary = {
        "evaluation_design": f"repeated_{config.outer_folds}x{config.inner_folds}_nested_stratified_cv",
        "development_cohort_id": dev_cohort,
        "development_dataset_id": dev_dataset,
        "pooled_cohorts": False,
        "n_participants": int(len(y)),
        "n_positive": int(np.sum(y == 1)),
        "n_negative": int(np.sum(y == 0)),
        "repeat_count": len(uncalibrated_repeat_summaries),
        "outer_fold_family_selection_counts": selection_counts,
        "inner_selected_roc_auc_mean_across_repeats": float(
            np.mean(uncal_selected_aucs)
        ),
        "inner_selected_roc_auc_sd_across_repeats": float(
            np.std(uncal_selected_aucs, ddof=0)
        ),
        "uncalibrated_nested_cv": {
            "each_observation_excluded_from_model_fit": True,
            "post_hoc_calibration_applied": False,
            "inner_selected_roc_auc_mean_across_repeats": float(
                np.mean(uncal_selected_aucs)
            ),
            "inner_selected_roc_auc_sd_across_repeats": float(
                np.std(uncal_selected_aucs, ddof=0)
            ),
            "inner_selected_brier_mean_across_repeats": float(
                np.mean(uncal_selected_briers)
            ),
            "repeats": uncalibrated_repeat_summaries,
        },
        "cross_fitted_calibrated_nested_cv": {
            "evaluation_design": "outer_fold_evaluation_with_inner_cv_oof_calibrator",
            "each_observation_excluded_from_model_and_calibrator_fit": True,
            "unbiased_within_cohort_calibrated_estimate": True,
            "inner_selected_roc_auc_mean_across_repeats": float(
                np.mean(cal_selected_aucs)
            ),
            "inner_selected_brier_mean_across_repeats": float(
                np.mean(cal_selected_briers)
            ),
            "inner_selected_ece_mean_across_repeats": float(
                np.mean(cal_selected_eces)
            ),
            "inner_selected_log_loss_mean_across_repeats": float(
                np.mean(cal_selected_log_losses)
            ),
            "repeats": calibrated_repeat_summaries,
        },
        "full_cohort_cv_family_roc_aucs": full_aucs,
        "selected_model_family": selected_family,
        "selected_hyperparameters": selected_params,
        "final_development_calibrator_apparent_diagnostic": (
            apparent_calibrator_fit_diagnostic
        ),
        "repeats": uncalibrated_repeat_summaries,
        "caveats": [
            "Internal nested-CV results estimate within-cohort performance only; not external validation.",
            "Cross-fitted calibrated nested-CV ('cross_fitted_calibrated_nested_cv') excludes every evaluated observation from fitting both its prediction model and its calibrator.",
            "Final calibrator fit diagnostic ('final_development_calibrator_apparent_diagnostic') is an apparent resubstitution check on development OOF scores—never report it as unbiased calibrated performance.",
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
    one_shot_ledger_path: Path | None = None,
    seed: int = 20261201,
    n_bootstrap: int = 250,
) -> dict[str, Any]:
    """Evaluate a frozen ``TrainedResearchRun`` on a declared external synthetic cohort.

    Important scientific & operational boundaries:
    - Blocked for real patient data (including real Hungary and real AngioCAD)
      while Gate PT (``P-3``) and ``D-021`` remain unresolved.
    - When ``one_shot_ledger_path`` is supplied, :class:`ExternalEvaluationLedger`
      records the evaluation in a locally protected (``0600``) untracked registry
      and rejects any second evaluation against the same external cohort under the
      same ``protocol_id`` or ``model_id``.
    - When ``one_shot_ledger_path`` is ``None``, this function acts strictly as a
      **stateless frozen-model evaluation primitive** and does NOT prevent a caller
      from invoking it repeatedly across different candidate models.
    - String-based cohort/dataset checks block known overlapping benchmark labels
      (``DA-A1``/``DA-B1``, ``Cleveland``/``Statlog``) and non-``T1`` datasets,
      but do NOT prove participant-level independence.
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
    _enforce_synthetic_cohort_identifier_guard(
        ext_cohort, ext_dataset, field_name="external_cohort_id"
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

    cohort_digest = hashlib.sha256(
        np.ascontiguousarray(X_ext, dtype=np.float64).tobytes()
        + np.ascontiguousarray(y_ext, dtype=np.int64).tobytes()
    ).hexdigest()

    ledger_receipt: dict[str, Any] | None = None
    if one_shot_ledger_path is not None:
        ledger = ExternalEvaluationLedger(one_shot_ledger_path)
        ledger_receipt = ledger.record_single_shot(
            protocol_id=trained_run.protocol_id,
            model_id=trained_run.model_id,
            model_version=trained_run.model_version,
            external_cohort_id=ext_cohort,
            external_dataset_id=ext_dataset,
            preprocessor_sha256=trained_run.preprocessor.state_sha256,
            calibrator_sha256=trained_run.calibrator.state_sha256,
            cohort_fingerprint_sha256=cohort_digest,
        )

    # Apply frozen development preprocessor, estimator, and calibrator without modification
    Z_ext = trained_run.preprocessor.transform(X_ext)
    p_ext_raw, logits_ext = _positive_proba_and_optional_logit(
        trained_run.selected_model_family, trained_run.estimator, Z_ext
    )
    p_ext_cal = trained_run.calibrator.calibrate(p_ext_raw, raw_logits=logits_ext)

    uncalibrated_metrics = evaluate_comprehensive_metrics(
        y_ext,
        p_ext_raw,
        seed=seed,
        n_bootstrap=n_bootstrap,
        evaluation_scope="FROZEN_EXTERNAL_COHORT_UNCALIBRATED_RESEARCH_ONLY",
    )
    calibrated_metrics = evaluate_comprehensive_metrics(
        y_ext,
        p_ext_cal,
        seed=seed + 100,
        n_bootstrap=n_bootstrap,
        evaluation_scope="FROZEN_EXTERNAL_COHORT_TRANSPORT_CALIBRATED_RESEARCH_ONLY",
    )
    shift_diag = compute_prevalence_shift_diagnostic(
        development_prevalence=trained_run.calibrator.development_prevalence,
        external_prevalence=float(np.mean(y_ext)),
    )
    complete_count = sum(1 for item in validated_ext if item.stage_complete)

    limitations = [
        "Frozen-model external transport assessment: the external cohort is not used inside this call to refit preprocessing, model weights, or calibration.",
        "String-based cohort/dataset checks block known overlapping IDs (e.g., DA-A1/DA-B1, Cleveland/Statlog) but do NOT establish participant-level non-overlap without verified institutional data-custody provenance.",
        "Transported probabilities retain development-cohort prevalence calibration unless separately recalibrated under a clinical protocol.",
        "Synthetic/research evaluation only; real Hungary and AngioCAD evaluations remain blocked pending Gate PT (P-3) and D-021.",
    ]
    if ledger_receipt is None:
        limitations.insert(
            1,
            "Invoked without 'one_shot_ledger_path': this call acted as a stateless evaluation primitive and did NOT enforce single-shot protocol consumption across repeated runs.",
        )

    return {
        "evaluation_type": (
            "LEDGER_RECORDED_SINGLE_SHOT_EXTERNAL_ASSESSMENT"
            if ledger_receipt is not None
            else "FROZEN_MODEL_EXTERNAL_EVALUATION_PRIMITIVE"
        ),
        "execution_semantics": (
            "LOCAL_LEDGER_ENFORCED_SINGLE_EVALUATION"
            if ledger_receipt is not None
            else "STATELESS_FROZEN_MODEL_EVALUATION_PRIMITIVE_NOT_ONE_SHOT_ENFORCED"
        ),
        "one_shot_enforced_by_ledger": ledger_receipt is not None,
        "one_shot_ledger_receipt": ledger_receipt,
        "participant_independence_verification": (
            "DECLARED_COHORT_METADATA_GUARD_ONLY_NOT_PATIENT_LEVEL_PROOF"
        ),
        "model_id": trained_run.model_id,
        "model_version": trained_run.model_version,
        "protocol_id": trained_run.protocol_id,
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
        "uncalibrated_transport_metrics": uncalibrated_metrics,
        "locked_transport_metrics": calibrated_metrics,
        "limitations": limitations,
    }
