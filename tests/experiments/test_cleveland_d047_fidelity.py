"""Cleveland D-047 protocol-fidelity and guarded-execution regressions (AI-3.2).

Synthetic-only: every cohort, source file, and bundle in this module is
deterministically generated in memory or inside pytest ``tmp_path``. No real
patient record, ``data/`` source file, or committed artifact is accessed.

These tests verify ACTUAL estimator construction and OBSERVED cross-validation
behavior for the frozen Cleveland D-047 execution profile -- not just static
configuration values -- while proving UCI-412 and ordinary AI-1 synthetic
behavior remain unchanged and the guarded wrapper stays fail-closed.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression

import ai.execution as execution_mod
import ai.training as training_mod
from ai.errors import CohortGovernanceError
from ai.errors import BundleIntegrityError
from ai.execution import (
    GUARDED_CLEVELAND_D047_OPERATOR_CONFIRMATION,
    DatasetAdapterIntegrityError,
    ExecutionAuthorizationError,
    GuardedClevelandExecutionProof,
    assert_training_config_approved,
    execute_authorized_research_run,
    execute_guarded_cleveland_d047_run,
    get_approved_training_config,
    load_cleveland_source_records,
)
from tests.experiments.test_authorized_real_data_execution import (
    _create_synthetic_cleveland_file,
    _create_valid_auth_manifest,
    _execute_isolated_test_simulation,
)
from ai.panels import (
    DA_A2_RESTING_LABS_PANEL,
    DA_A2_RESTING_PANEL,
    validate_cohort_records,
)
from ai.preprocessing import FoldSafeClinicalPreprocessor
from ai.training import (
    CLEVELAND_D047_RF_SPACE_VERSION,
    CLEVELAND_D047_RF_SPACE_WIDTH,
    EXECUTION_PROFILE_AI1_GENERIC_V1,
    EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1,
    ResearchTrainingConfig,
    _build_estimator,
    _d047_original_rf_matrix,
    _d047_project_background_to_rf_space,
    _d047_rf_column_to_raw_feature,
    _execute_shared_training_pipeline,
    _run_single_nested_pass,
    derive_cleveland_d047_inner_seed,
    derive_cleveland_d047_model_seed,
    derive_cleveland_d047_negative_control_outer_seed,
    train_research_model,
)
from research.audit.provenance import sha256_file
from research.experiments.config import (
    DEFAULT_CONFIG as CLEVELAND_DEFAULT_CONFIG,
    PLAN_PATH as CLEVELAND_PLAN_PATH,
)
import research.experiments.evaluation as cleveland_eval
import research.experiments.safety as cleveland_safety
from research.experiments.synthetic_fixtures import make_synthetic_source_bytes
from research.uci412.config import DEFAULT_CONFIG as UCI412_DEFAULT_CONFIG

REPO_ROOT = Path(__file__).resolve().parents[2]

FAST_D047_TEST_CONFIG = ResearchTrainingConfig(
    protocol_id="CAI-D047-CLEVELAND-SYNTHETIC-TEST-V1",
    model_version="0.2.0",
    outer_folds=3,
    inner_folds=2,
    repeat_seeds=(20261026,),
    shuffle_control_seeds=(20262001,),
    shuffle_max_allowed_auroc=0.75,
    auc_simplicity_tolerance=0.01,
    lr_c_grid=(0.1, 1.0, 10.0),
    rf_max_depths=(3,),
    rf_min_samples_leaf=(5,),
    rf_n_estimators=15,
    bootstrap_resamples=30,
    shap_max_background_samples=20,
    exploratory_threshold=0.5,
    execution_profile=EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1,
)

FAST_GENERIC_TEST_CONFIG = ResearchTrainingConfig(
    protocol_id="CAI-AI1-SYNTHETIC-TEST-V1",
    model_version="0.1.0",
    outer_folds=3,
    inner_folds=2,
    repeat_seeds=(20261026,),
    shuffle_control_seeds=(20262001,),
    shuffle_max_allowed_auroc=0.75,
    auc_simplicity_tolerance=0.01,
    lr_c_grid=(0.1, 1.0, 10.0),
    rf_max_depths=(3,),
    rf_min_samples_leaf=(5,),
    rf_n_estimators=15,
    bootstrap_resamples=30,
    shap_max_background_samples=20,
    exploratory_threshold=0.5,
    execution_profile=EXECUTION_PROFILE_AI1_GENERIC_V1,
)


def _generate_synthetic_resting_cohort(
    n: int, *, seed: int
) -> tuple[list[dict[str, Any]], list[int]]:
    """Complete five-field synthetic cohort with a linear CAD signal (LR-friendly)."""
    rng = np.random.default_rng(seed)
    records: list[dict[str, Any]] = []
    labels: list[int] = []
    for _ in range(n):
        age = float(rng.integers(35, 76))
        sex = int(rng.integers(0, 2))
        cp = int(rng.choice([1, 2, 3, 4]))
        trestbps = float(rng.integers(105, 175))
        restecg = int(rng.choice([0, 1, 2]))
        eta = (
            0.08 * (age - 55.0)
            + 1.1 * sex
            + (1.4 if cp == 4 else -0.6)
            + 0.025 * (trestbps - 135.0)
            + (0.5 if restecg == 1 else 0.0)
        )
        prob = 1.0 / (1.0 + np.exp(-eta))
        y = int(rng.random() < prob)
        records.append(
            {
                "synthetic": True,
                "panel_id": DA_A2_RESTING_PANEL.panel_id,
                "features": {
                    "age": age,
                    "sex": sex,
                    "cp": cp,
                    "trestbps": trestbps,
                    "restecg": restecg,
                },
                "units": {"age": "years", "trestbps": "mmHg"},
                "missing_reasons": {},
            }
        )
        labels.append(y)
    return records, labels


def _cohort_matrices(
    n: int = 90, *, seed: int = 47047
) -> tuple[np.ndarray, np.ndarray]:
    records, labels = _generate_synthetic_resting_cohort(n, seed=seed)
    X, y, _ = validate_cohort_records(
        records, labels, DA_A2_RESTING_PANEL, require_synthetic=True
    )
    return X, y


def _complete_synthetic_cleveland_bytes() -> bytes:
    """Synthetic Cleveland-shaped bytes with a complete five-field panel (no '?')."""
    lines = make_synthetic_source_bytes().decode("ascii").splitlines()
    clean: list[str] = []
    for line in lines:
        parts = line.split(",")
        if len(parts) == 14:
            if parts[0] == "?":
                parts[0] = "55"
            if parts[1] == "?":
                parts[1] = "1"
            if parts[2] == "?":
                parts[2] = "3"
            if parts[3] == "?":
                parts[3] = "130"
            if parts[6] == "?":
                parts[6] = "0"
        clean.append(",".join(parts))
    return ("\n".join(clean) + "\n").encode("ascii")


# --------------------------------------------------------------------------- #
# 1. Frozen D-047 constants, approved configs, and profile isolation
# --------------------------------------------------------------------------- #


def test_d047_constants_match_registered_plan_research_impl_and_approved_config() -> None:
    plan = json.loads(CLEVELAND_PLAN_PATH.read_text(encoding="utf-8"))

    # Registered plan strings and values (read, never modified).
    assert plan["cv"]["seed_derivation"]["inner_cv_seed"] == (
        "outer_repeat_seed + 97 + 1009 * outer_fold_number_1_based"
    )
    assert plan["cv"]["seed_derivation"]["model_seed"] == (
        "outer_repeat_seed + 100003 + 101 * outer_fold_number_1_based + model_family_offset"
    )
    assert plan["cv"]["seed_derivation"]["model_family_offsets"] == {
        "l2_logistic_regression": 11,
        "constrained_random_forest": 23,
    }
    assert plan["cv"]["seed_derivation"]["label_shuffle_outer_seed"] == (
        "the corresponding label_shuffle_seed"
    )
    assert plan["models"]["l2_logistic_regression"] == {
        "solver": "liblinear",
        "penalty": "l2",
        "C": [0.1, 1, 10],
        "max_iter": 2000,
        "class_weight": None,
    }
    assert plan["models"]["constrained_random_forest"] == {
        "n_estimators": 200,
        "max_depth": [3, 5],
        "min_samples_leaf": [5, 10],
        "max_features": "sqrt",
        "class_weight": None,
    }

    # Local AI constants match the registered in-code Cleveland config.
    assert training_mod.CLEVELAND_D047_INNER_SEED_OFFSET == CLEVELAND_DEFAULT_CONFIG.inner_seed_offset == 97
    assert training_mod.CLEVELAND_D047_INNER_FOLD_MULTIPLIER == CLEVELAND_DEFAULT_CONFIG.inner_fold_multiplier == 1009
    assert training_mod.CLEVELAND_D047_MODEL_SEED_OFFSET == CLEVELAND_DEFAULT_CONFIG.model_seed_offset == 100003
    assert training_mod.CLEVELAND_D047_MODEL_FOLD_MULTIPLIER == CLEVELAND_DEFAULT_CONFIG.model_fold_multiplier == 101
    assert training_mod.CLEVELAND_D047_LR_FAMILY_OFFSET == CLEVELAND_DEFAULT_CONFIG.logistic_seed_offset == 11
    assert training_mod.CLEVELAND_D047_RF_FAMILY_OFFSET == CLEVELAND_DEFAULT_CONFIG.forest_seed_offset == 23

    # Our derivations match the original research implementation exactly.
    for outer_seed in (20261023, 20261024, 20261025, 20261026, 20262001):
        for fold in (1, 2, 3, 4, 5):
            assert derive_cleveland_d047_inner_seed(outer_seed, fold) == (
                cleveland_eval.derive_inner_seed(outer_seed, fold, CLEVELAND_DEFAULT_CONFIG)
            )
            for fam in ("l2_logistic_regression", "constrained_random_forest"):
                assert derive_cleveland_d047_model_seed(outer_seed, fold, fam) == (
                    cleveland_eval.derive_model_seed(outer_seed, fold, fam, CLEVELAND_DEFAULT_CONFIG)
                )
    for shuf in (20262001, 20262002, 20262003):
        assert derive_cleveland_d047_negative_control_outer_seed(shuf) == shuf

    # Frozen approved Cleveland config binds the D-047 profile and full grids.
    clev = get_approved_training_config("DA-A2")
    assert clev.execution_profile == EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1
    assert clev.protocol_id == "CAI-D047-CLEVELAND-EXPLORATORY-V1"
    assert clev.model_version == "0.2.0"
    assert clev.outer_folds == 5 and clev.inner_folds == 5
    assert clev.repeat_seeds == (20261023, 20261024, 20261025, 20261026)
    assert clev.shuffle_control_seeds == (20262001, 20262002, 20262003)
    assert clev.lr_c_grid == (0.1, 1, 10)
    assert clev.rf_n_estimators == 200
    assert clev.rf_max_depths == (3, 5)
    assert clev.rf_min_samples_leaf == (5, 10)
    assert clev.auc_simplicity_tolerance == 0.01
    assert clev.exploratory_threshold == 0.5

    # UCI-412 and ordinary AI-1 synthetic behavior are explicitly unchanged.
    uci = get_approved_training_config("DA-A1")
    assert uci.execution_profile == EXECUTION_PROFILE_AI1_GENERIC_V1
    assert uci.outer_folds == UCI412_DEFAULT_CONFIG.outer_folds
    assert ResearchTrainingConfig().execution_profile == EXECUTION_PROFILE_AI1_GENERIC_V1


def test_unknown_execution_profile_fails_closed() -> None:
    with pytest.raises(ValueError, match="execution_profile"):
        ResearchTrainingConfig(execution_profile="BYPASS-PROFILE")
    with pytest.raises(ValueError, match="execution_profile"):
        _build_estimator(
            "l2_logistic_regression",
            {"C": 1.0},
            seed=1,
            rf_n_estimators=10,
            execution_profile="BYPASS-PROFILE",
        )


def test_execution_profile_deviation_rejected_for_both_cohorts() -> None:
    for dataset_id, approved_profile in (
        ("DA-A2", EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1),
        ("DA-A1", EXECUTION_PROFILE_AI1_GENERIC_V1),
    ):
        approved = get_approved_training_config(dataset_id)
        assert approved.execution_profile == approved_profile
        other = (
            EXECUTION_PROFILE_AI1_GENERIC_V1
            if approved_profile == EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1
            else EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1
        )
        kwargs = {
            f.name: getattr(approved, f.name)
            for f in dataclasses.fields(ResearchTrainingConfig)
        }
        kwargs["execution_profile"] = other
        with pytest.raises(ExecutionAuthorizationError) as exc_info:
            assert_training_config_approved(dataset_id, ResearchTrainingConfig(**kwargs))
        assert exc_info.value.code == "unapproved_training_configuration_deviation"
        assert "execution_profile" in exc_info.value.message


# --------------------------------------------------------------------------- #
# 2. Solver / iteration regression on ACTUAL constructed estimators
# --------------------------------------------------------------------------- #


def test_cleveland_estimator_construction_uses_liblinear_2000() -> None:
    lr = _build_estimator(
        "l2_logistic_regression",
        {"C": 1.0},
        seed=4242,
        rf_n_estimators=200,
        execution_profile=EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1,
    )
    assert isinstance(lr, LogisticRegression)
    assert lr.solver == "liblinear"
    assert lr.max_iter == 2000
    assert lr.penalty == "l2"
    assert lr.C == 1.0
    assert lr.class_weight is None

    rf = _build_estimator(
        "constrained_random_forest",
        {"max_depth": 5, "min_samples_leaf": 10},
        seed=4242,
        rf_n_estimators=200,
        execution_profile=EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1,
    )
    assert isinstance(rf, RandomForestClassifier)
    assert rf.n_estimators == 200
    assert rf.max_depth == 5
    assert rf.min_samples_leaf == 10
    assert rf.max_features == "sqrt"
    assert rf.class_weight is None
    assert rf.n_jobs == 1

    # Generic profile (AI-1 synthetic + UCI-412) is unchanged by construction.
    generic_lr = _build_estimator(
        "l2_logistic_regression",
        {"C": 1.0},
        seed=4242,
        rf_n_estimators=50,
        execution_profile=EXECUTION_PROFILE_AI1_GENERIC_V1,
    )
    assert generic_lr.solver == "lbfgs"
    assert generic_lr.max_iter == 1000


def test_observed_cv_constructs_d047_estimators_for_every_fit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    X, y = _cohort_matrices()
    seen: list[tuple[str, Any]] = []
    orig_build = training_mod._build_estimator

    def _spy(family: str, params: Any, **kwargs: Any) -> Any:
        est = orig_build(family, params, **kwargs)
        seen.append((family, est))
        return est

    monkeypatch.setattr(training_mod, "_build_estimator", _spy)
    _run_single_nested_pass(
        X,
        y,
        panel=DA_A2_RESTING_PANEL,
        config=FAST_D047_TEST_CONFIG,
        repeat_seed=20261026,
        retain_fold_models=False,
        fit_cross_calibrators=False,
    )
    lr_seen = [est for fam, est in seen if fam == "l2_logistic_regression"]
    rf_seen = [est for fam, est in seen if fam == "constrained_random_forest"]
    assert lr_seen and rf_seen
    for est in lr_seen:
        assert est.solver == "liblinear"
        assert est.max_iter == 2000
        assert est.C in (0.1, 1.0, 10.0)
    for est in rf_seen:
        assert est.n_estimators == FAST_D047_TEST_CONFIG.rf_n_estimators
        assert est.max_depth in tuple(FAST_D047_TEST_CONFIG.rf_max_depths)
        assert est.min_samples_leaf in tuple(FAST_D047_TEST_CONFIG.rf_min_samples_leaf)

    # Generic control run still constructs lbfgs/1000 throughout.
    seen.clear()
    _run_single_nested_pass(
        X,
        y,
        panel=DA_A2_RESTING_PANEL,
        config=FAST_GENERIC_TEST_CONFIG,
        repeat_seed=20261026,
        retain_fold_models=False,
        fit_cross_calibrators=False,
    )
    generic_lr = [est for fam, est in seen if fam == "l2_logistic_regression"]
    assert generic_lr
    for est in generic_lr:
        assert est.solver == "lbfgs"
        assert est.max_iter == 1000


# --------------------------------------------------------------------------- #
# 3. Frozen seed-derivation regression on OBSERVED CV behavior
# --------------------------------------------------------------------------- #


def test_d047_inner_and_model_seeds_observed_in_fold_records() -> None:
    X, y = _cohort_matrices()
    _, _, fold_records, _ = _run_single_nested_pass(
        X,
        y,
        panel=DA_A2_RESTING_PANEL,
        config=FAST_D047_TEST_CONFIG,
        repeat_seed=20261026,
        retain_fold_models=False,
        fit_cross_calibrators=True,
    )
    assert len(fold_records) == FAST_D047_TEST_CONFIG.outer_folds
    for rec in fold_records:
        fold = int(rec["outer_fold"])
        assert rec["execution_profile"] == EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1
        assert rec["inner_seed"] == derive_cleveland_d047_inner_seed(20261026, fold)
        assert rec["inner_seed"] == cleveland_eval.derive_inner_seed(
            20261026, fold, CLEVELAND_DEFAULT_CONFIG
        )
        for fam in ("l2_logistic_regression", "constrained_random_forest"):
            assert rec["model_seed_by_family"][fam] == derive_cleveland_d047_model_seed(
                20261026, fold, fam
            )
            assert rec["model_seed_by_family"][fam] == cleveland_eval.derive_model_seed(
                20261026, fold, fam, CLEVELAND_DEFAULT_CONFIG
            )

    # Generic profile preserves the historical derivations (and omits D-047 audit keys).
    _, _, generic_records, _ = _run_single_nested_pass(
        X,
        y,
        panel=DA_A2_RESTING_PANEL,
        config=FAST_GENERIC_TEST_CONFIG,
        repeat_seed=20261026,
        retain_fold_models=False,
        fit_cross_calibrators=False,
    )
    for rec in generic_records:
        assert rec["execution_profile"] == EXECUTION_PROFILE_AI1_GENERIC_V1
        assert "inner_seed" not in rec
        assert "model_seed_by_family" not in rec


def test_d047_inner_fits_share_one_model_seed_per_family_and_fold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    X, y = _cohort_matrices()
    captured: list[tuple[str, int, int]] = []  # (family, seed, rf_n_estimators)
    orig_build = training_mod._build_estimator

    def _spy(family: str, params: Any, **kwargs: Any) -> Any:
        captured.append((family, int(kwargs["seed"]), int(kwargs.get("rf_n_estimators", 0))))
        return orig_build(family, params, **kwargs)

    monkeypatch.setattr(training_mod, "_build_estimator", _spy)
    _run_single_nested_pass(
        X,
        y,
        panel=DA_A2_RESTING_PANEL,
        config=FAST_D047_TEST_CONFIG,
        repeat_seed=20261026,
        retain_fold_models=False,
        fit_cross_calibrators=False,
    )
    # Every LR fit for outer fold 1 uses the single frozen D-047 LR model seed:
    # inner fits (3 C values x 2 inner splits = 6) plus the outer refit (1).
    expected_lr_seed = derive_cleveland_d047_model_seed(
        20261026, 1, "l2_logistic_regression"
    )
    expected_rf_seed = derive_cleveland_d047_model_seed(
        20261026, 1, "constrained_random_forest"
    )
    # Call order per fold: dummy (1), LR inner (3x2=6), LR outer (1),
    # RF inner (1x2=2), RF outer (1). Fold 1 occupies indices 0..10.
    assert captured[0][0] == "prevalence_dummy"
    lr_seeds_fold1 = [
        seed for fam, seed, _ in captured[1:8] if fam == "l2_logistic_regression"
    ]
    assert len(lr_seeds_fold1) == 7
    assert set(lr_seeds_fold1) == {expected_lr_seed}
    rf_seeds_fold1 = [
        seed for fam, seed, _ in captured[8:11] if fam == "constrained_random_forest"
    ]
    assert len(rf_seeds_fold1) == 3
    assert set(rf_seeds_fold1) == {expected_rf_seed}


def test_generic_inner_fit_seeds_still_vary_per_candidate_and_split(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    X, y = _cohort_matrices()
    captured: list[int] = []
    orig_build = training_mod._build_estimator

    def _spy(family: str, params: Any, **kwargs: Any) -> Any:
        if family == "l2_logistic_regression":
            captured.append(int(kwargs["seed"]))
        return orig_build(family, params, **kwargs)

    monkeypatch.setattr(training_mod, "_build_estimator", _spy)
    _run_single_nested_pass(
        X,
        y,
        panel=DA_A2_RESTING_PANEL,
        config=FAST_GENERIC_TEST_CONFIG,
        repeat_seed=20261026,
        retain_fold_models=False,
        fit_cross_calibrators=False,
    )
    # Historical varying formula yields distinct seeds across candidates/splits.
    assert len(set(captured)) > 2


def test_d047_inner_splits_shared_across_families(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sklearn.model_selection import StratifiedKFold as SKFold

    X, y = _cohort_matrices()
    observed_inner_seeds: list[int] = []
    orig_split = SKFold.split

    def _spy_split(self: Any, X_in: Any, y_in: Any, *args: Any, **kwargs: Any) -> Any:
        # Inner splitters are the only ones with n_splits == inner_folds on the
        # outer-training subset; outer splitter uses outer_folds on full y.
        if int(self.n_splits) == FAST_D047_TEST_CONFIG.inner_folds and len(
            np.asarray(y_in)
        ) < len(y):
            observed_inner_seeds.append(int(self.random_state))
        return orig_split(self, X_in, y_in, *args, **kwargs)

    monkeypatch.setattr(SKFold, "split", _spy_split)
    _run_single_nested_pass(
        X,
        y,
        panel=DA_A2_RESTING_PANEL,
        config=FAST_D047_TEST_CONFIG,
        repeat_seed=20261026,
        retain_fold_models=False,
        fit_cross_calibrators=False,
    )
    # Two families share one inner seed per outer fold (3 folds -> 6 calls, 3 unique).
    assert len(observed_inner_seeds) == FAST_D047_TEST_CONFIG.outer_folds * 2
    for fold in (1, 2, 3):
        expected = derive_cleveland_d047_inner_seed(20261026, fold)
        assert observed_inner_seeds.count(expected) == 2


# --------------------------------------------------------------------------- #
# 4. Negative-control seed regression on OBSERVED behavior
# --------------------------------------------------------------------------- #


def test_negative_control_outer_seeds_restore_registered_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    X, y = _cohort_matrices()
    captured: list[tuple[tuple[int, ...], int]] = []  # (y_perm_digest_shape, repeat_seed)
    orig_pass = training_mod._run_single_nested_pass

    def _spy(
        X_in: np.ndarray, y_in: np.ndarray, **kwargs: Any
    ) -> tuple[Any, Any, Any, Any]:
        captured.append((tuple(np.asarray(y_in[:8]).tolist()), int(kwargs["repeat_seed"])))
        return orig_pass(X_in, y_in, **kwargs)

    monkeypatch.setattr(training_mod, "_run_single_nested_pass", _spy)
    run = _execute_shared_training_pipeline(
        X,
        y,
        DA_A2_RESTING_PANEL,
        model_id="synth_d047_shuffle_check",
        dev_cohort="synthetic_cleveland",
        dev_dataset="DA-A2:synthetic",
        config=FAST_D047_TEST_CONFIG,
        synthetic_only=True,
    )
    # One primary repeat plus one shuffle run for the fast single-seed config.
    assert run.negative_control["execution_profile"] == EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1
    assert run.negative_control["shuffle_seeds"] == [20262001]
    assert run.negative_control["outer_repeat_seed_by_shuffle"] == [20262001]
    shuffle_call = captured[-1]
    assert shuffle_call[1] == 20262001
    expected_perm_head = tuple(
        np.random.default_rng(20262001).permutation(y)[:8].tolist()
    )
    assert shuffle_call[0] == expected_perm_head

    captured.clear()
    run_generic = _execute_shared_training_pipeline(
        X,
        y,
        DA_A2_RESTING_PANEL,
        model_id="synth_generic_shuffle_check",
        dev_cohort="synthetic_cleveland",
        dev_dataset="DA-A2:synthetic",
        config=FAST_GENERIC_TEST_CONFIG,
        synthetic_only=True,
    )
    assert run_generic.negative_control["outer_repeat_seed_by_shuffle"] == [20262001 + 17]
    assert captured[-1][1] == 20262001 + 17


# --------------------------------------------------------------------------- #
# 5. Fold-local preprocessing and missingness checks
# --------------------------------------------------------------------------- #


def test_cleveland_preprocessing_is_fold_local_for_d047_profile() -> None:
    from ai.preprocessing import FoldSafeClinicalPreprocessor

    X, y = _cohort_matrices()
    prep = FoldSafeClinicalPreprocessor.fit(X[:60], DA_A2_RESTING_PANEL)
    before = json.loads(prep.to_canonical_json_bytes().decode("utf-8"))

    holdout = X[60:62].copy()
    holdout[:, 0] = 79.0
    holdout[:, 3] = 195.0
    Z_holdout = prep.transform(holdout)
    assert np.isfinite(Z_holdout).all()
    after = json.loads(prep.to_canonical_json_bytes().decode("utf-8"))
    assert before == after  # Holdout never leaks into fitted training statistics.


def test_d047_cross_fitted_calibrator_excludes_test_fold() -> None:
    from sklearn.model_selection import StratifiedKFold

    X, y = _cohort_matrices()
    outer = list(
        StratifiedKFold(
            n_splits=FAST_D047_TEST_CONFIG.outer_folds,
            shuffle=True,
            random_state=FAST_D047_TEST_CONFIG.repeat_seeds[0],
        ).split(np.zeros(len(y)), y)
    )
    _, fold1_test = outer[0]
    X_pert = X.copy()
    X_pert[fold1_test, 0] = 79.0
    X_pert[fold1_test, 3] = 195.0
    _, _, orig_recs, _ = _run_single_nested_pass(
        X,
        y,
        panel=DA_A2_RESTING_PANEL,
        config=FAST_D047_TEST_CONFIG,
        repeat_seed=FAST_D047_TEST_CONFIG.repeat_seeds[0],
        retain_fold_models=False,
        fit_cross_calibrators=True,
    )
    _, _, pert_recs, _ = _run_single_nested_pass(
        X_pert,
        y,
        panel=DA_A2_RESTING_PANEL,
        config=FAST_D047_TEST_CONFIG,
        repeat_seed=FAST_D047_TEST_CONFIG.repeat_seeds[0],
        retain_fold_models=False,
        fit_cross_calibrators=True,
    )
    assert orig_recs[0]["fold_calibrator"] == pert_recs[0]["fold_calibrator"]


def test_cleveland_loader_fails_closed_on_unexpected_question_marks(
    tmp_path: Path,
) -> None:
    # Uncleaned synthetic bytes contain '?' in the five-field panel.
    raw = make_synthetic_source_bytes()
    assert b"?" in raw
    src = tmp_path / "processed.cleveland.data"
    src.write_bytes(raw)
    digest, _ = sha256_file(src)
    with pytest.raises(DatasetAdapterIntegrityError) as exc_info:
        load_cleveland_source_records(
            src, expected_sha256=digest.lower(), panel=DA_A2_RESTING_PANEL
        )
    assert exc_info.value.code == "unexpected_cleveland_missingness_requires_review"
    assert "not_measured" in str(exc_info.value)  # names the forbidden fabrication
    assert "55,1," not in str(exc_info.value)  # aggregate-only, no patient values


def test_cleveland_loader_complete_panel_invents_no_missing_reasons(
    tmp_path: Path,
) -> None:
    src = tmp_path / "processed.cleveland.data"
    src.write_bytes(_complete_synthetic_cleveland_bytes())
    digest, _ = sha256_file(src)
    records, labels, dataset = load_cleveland_source_records(
        src, expected_sha256=digest.lower(), panel=DA_A2_RESTING_PANEL
    )
    assert len(records) == 303 and len(labels) == 303
    assert dataset.feature_names == ("age", "sex", "cp", "trestbps", "restecg")
    for rec in records:
        assert rec["missing_reasons"] == {}
        assert rec["synthetic"] is False
    X, y, _ = validate_cohort_records(
        records, labels, DA_A2_RESTING_PANEL, require_synthetic=False
    )
    assert not bool(np.isnan(X).any())


def test_complete_cleveland_lineage_has_all_zero_missing_indicators() -> None:
    from ai.preprocessing import FoldSafeClinicalPreprocessor

    X, y = _cohort_matrices()
    prep = FoldSafeClinicalPreprocessor.fit(X, DA_A2_RESTING_PANEL)
    # AI lineage reserves two always-present optional missing indicators beyond
    # the D-047 eight reference columns; on complete data they are all zeros.
    assert "trestbps__missing" in prep.encoded_feature_names
    assert "restecg__missing" in prep.encoded_feature_names
    Z = prep.transform(X)
    for col in ("trestbps__missing", "restecg__missing"):
        idx = prep.encoded_feature_names.index(col)
        assert bool((Z[:, idx] == 0.0).all())

    # All-zero columns carry no LR signal under the frozen liblinear fit.
    lr = _build_estimator(
        "l2_logistic_regression",
        {"C": 1.0},
        seed=derive_cleveland_d047_model_seed(20261026, 1, "l2_logistic_regression"),
        rf_n_estimators=15,
        execution_profile=EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1,
    )
    lr.fit(Z, y)
    for col in ("trestbps__missing", "restecg__missing"):
        idx = prep.encoded_feature_names.index(col)
        assert abs(float(lr.coef_[0, idx])) < 1e-9


# --------------------------------------------------------------------------- #
# 6. Cleveland synthetic E2E (D-047 profile) + UCI-412 / AI-1 regressions
# --------------------------------------------------------------------------- #


def test_cleveland_synthetic_e2e_d047_profile(tmp_path: Path) -> None:
    from ai.filesystem_security import ensure_private_directory
    from ai.inference import ResearchCadPredictor
    from ai.packaging import package_research_bundle

    tmp_path = ensure_private_directory(tmp_path)
    records, labels = _generate_synthetic_resting_cohort(96, seed=60606)
    run = train_research_model(
        records,
        labels,
        DA_A2_RESTING_PANEL,
        model_id="synth_cleveland_d047_e2e",
        development_cohort_id="synthetic_cleveland",
        development_dataset_id="DA-A2",
        synthetic_data_confirmed=True,
        config=FAST_D047_TEST_CONFIG,
    )
    assert run.internal_evaluation["execution_profile"] == EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1
    assert run.negative_control["outer_repeat_seed_by_shuffle"] == [20262001]
    # Truthful separate reporting for the added calibration/refit blocks.
    ie = run.internal_evaluation
    assert ie["uncalibrated_nested_cv"]["post_hoc_calibration_applied"] is False
    assert ie["cross_fitted_calibrated_nested_cv"][
        "each_observation_excluded_from_model_and_calibrator_fit"
    ] is True
    assert ie["final_development_calibrator_apparent_diagnostic"][
        "unbiased_calibrated_performance_estimate"
    ] is False
    # Frozen estimator settings observed on the final refit.
    if run.selected_model_family == "l2_logistic_regression":
        assert isinstance(run.estimator, LogisticRegression)
        assert run.estimator.solver == "liblinear"
        assert run.estimator.max_iter == 2000
    else:
        assert isinstance(run.estimator, RandomForestClassifier)
        assert run.estimator.n_estimators == FAST_D047_TEST_CONFIG.rf_n_estimators

    bundle_dir = tmp_path / "cleveland_d047_synth_bundle"
    verified = package_research_bundle(run, bundle_dir)
    assert verified.serving_eligibility == "RESEARCH_ONLY"
    predictor = ResearchCadPredictor.from_verified_bundle(
        bundle_dir, trusted_local_root=tmp_path
    )
    result = predictor.predict_research_only(records[0])
    assert 0.0 <= result.calibrated_research_score <= 1.0
    assert result.explanation.sum_check_passed is True
    assert len(result.explanation.attributions) == 5


@pytest.fixture
def d047_isolated_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, str, str]:
    """Isolated temporary Git repository for the D-047 file-based synthetic E2E."""
    import os
    import shutil

    from research.experiments.config import REPOSITORY_ROOT as REAL_ROOT

    repo = tmp_path / "d047_isolated_repo"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test Runner"],
        cwd=str(repo),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=str(repo),
        check=True,
        capture_output=True,
    )
    shutil.copy(REAL_ROOT / ".gitignore", repo / ".gitignore")
    for rel_path in (
        "docs/research/gate-pt/02_d047_internal_exploratory_cleveland_PROTOCOL_PROPOSED.md",
        "research/experiments/cleveland_d047_exploratory_plan.v0.1.json",
        "docs/research/gate-pt/08_m3a_uci412_source_specific_benchmark_SPECIFICATION.md",
        "research/uci412/uci412_cad_research_plan.v0.1.json",
        "research/uci412/schemas/uci412_feature_dictionary.v1.json",
    ):
        dst = repo / rel_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REAL_ROOT / rel_path, dst)
    subprocess.run(
        ["git", "config", "core.autocrlf", "false"],
        cwd=str(repo),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "core.eol", "lf"], cwd=str(repo), check=True, capture_output=True
    )
    amend_doc = repo / "docs/research/gate-pt/17_ai2_operational_scope_amendment.md"
    amend_doc.parent.mkdir(parents=True, exist_ok=True)
    amend_doc.write_bytes(
        b"# AI-2 Operational Scope Amendment\nRatified for isolated internal experimentation only.\n"
    )
    subprocess.run(["git", "add", "."], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Baseline specifications"],
        cwd=str(repo),
        check=True,
        capture_output=True,
    )
    hist_time = "2026-10-25T12:00:00+00:00"
    subprocess.run(
        ["git", "commit", "--amend", "--no-edit", f"--date={hist_time}"],
        cwd=str(repo),
        check=True,
        capture_output=True,
        env={**os.environ, "GIT_COMMITTER_DATE": hist_time},
    )
    head_sha = (
        subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo),
            check=True,
            capture_output=True,
            text=True,
        )
        .stdout.strip()
        .lower()
    )
    commit_time = subprocess.run(
        ["git", "show", "-s", "--format=%cI", head_sha],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    monkeypatch.setattr(cleveland_safety, "D047_AUTHORIZING_MERGE_SHA", head_sha)
    monkeypatch.setattr(cleveland_safety, "D047_AUTHORIZING_MERGED_AT_UTC", commit_time)
    monkeypatch.setattr(execution_mod, "RATIFIED_OPERATIONAL_SCOPE_AMENDMENTS", {})
    return repo, head_sha, commit_time


def test_cleveland_file_e2e_d047_profile_via_isolated_repo(
    d047_isolated_repo: tuple[Path, str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """File-based synthetic E2E: complete Cleveland file + D-047 profile + bundle.

    Exercises the actual Cleveland execution path (read-only file loader with
    ``synthetic=False`` records, frozen D-047 profile selection, nested CV with
    registered seeds, truthful real-provenance packaging) inside an isolated
    temporary repository. No real patient data is involved.
    """
    from ai.inference import ResearchCadPredictor
    from ai.packaging import get_or_create_local_signing_key

    repo, _, _ = d047_isolated_repo
    source_path = repo / "data" / "raw" / "uci-45" / "processed.cleveland.data"
    source_sha = _create_synthetic_cleveland_file(source_path)
    manifest_path = repo / "data" / "experiments" / "manifest.json"
    _create_valid_auth_manifest(
        manifest_path,
        repo,
        dataset_id="DA-A2",
        panel_id="da_a2_resting_v1",
        source_sha256=source_sha,
        row_count=303,
        model_packaging_authorized=True,
        patient_shap_authorized=True,
    )
    bundle_dir = repo / "data" / "experiments" / "cai_d047_file_e2e_v1"
    signing_key = get_or_create_local_signing_key(repo / "data" / "experiments" / "signer.key")
    monkeypatch.setattr(
        execution_mod, "get_approved_training_config", lambda dataset_id: FAST_D047_TEST_CONFIG
    )

    trained_run, descriptor = _execute_isolated_test_simulation(
        manifest_path=manifest_path,
        source_path=source_path,
        panel_id="da_a2_resting_v1",
        output_bundle_dir=bundle_dir,
        signing_key=signing_key,
        repo_root=repo,
    )
    assert descriptor.serving_eligibility == "RESEARCH_ONLY"
    assert trained_run.internal_evaluation["execution_profile"] == (
        EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1
    )
    assert trained_run.negative_control["outer_repeat_seed_by_shuffle"] == [20262001]
    if trained_run.selected_model_family == "l2_logistic_regression":
        assert trained_run.estimator.solver == "liblinear"
        assert trained_run.estimator.max_iter == 2000
    manifest_doc = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest_doc["eligibility"]["synthetic_only"] is False
    assert manifest_doc["research_authorization"]["governance_decision_id"] == "D-047"
    predictor = ResearchCadPredictor.from_verified_bundle(
        bundle_dir, trusted_local_root=bundle_dir.parent, signing_key=signing_key
    )
    result = predictor.predict_research_only(
        {
            "synthetic": False,
            "panel_id": "da_a2_resting_v1",
            "features": {"age": 60.0, "sex": 1, "cp": 4, "trestbps": 140.0, "restecg": 0},
            "units": {"age": "years", "trestbps": "mmHg"},
            "missing_reasons": {},
        }
    )
    assert 0.0 <= result.calibrated_research_score <= 1.0
    assert result.explanation.sum_check_passed is True


def test_uci412_methodology_unchanged_generic_profile() -> None:
    approved = get_approved_training_config("DA-A1")
    assert approved.execution_profile == EXECUTION_PROFILE_AI1_GENERIC_V1
    lr = _build_estimator(
        "l2_logistic_regression",
        {"C": 1.0},
        seed=99,
        rf_n_estimators=approved.rf_n_estimators,
        execution_profile=approved.execution_profile,
    )
    assert lr.solver == "lbfgs"
    assert lr.max_iter == 1000
    # Frozen UCI-412 grids still bound from the registered UCI-412 plan.
    assert approved.lr_c_grid == UCI412_DEFAULT_CONFIG.logistic_c_values
    assert approved.rf_n_estimators == UCI412_DEFAULT_CONFIG.rf_n_estimators
    assert approved.repeat_seeds == UCI412_DEFAULT_CONFIG.outer_repeat_seeds


def test_ai1_synthetic_calibration_and_shap_regression(tmp_path: Path) -> None:
    from ai.filesystem_security import ensure_private_directory
    from ai.inference import ResearchCadPredictor
    from ai.packaging import package_research_bundle

    tmp_path = ensure_private_directory(tmp_path)
    rng = np.random.default_rng(70707)
    records: list[dict[str, Any]] = []
    labels: list[int] = []
    for _ in range(84):
        age = float(rng.integers(35, 76))
        sex = int(rng.integers(0, 2))
        cp = int(rng.choice([1, 2, 3, 4]))
        bp = float(rng.integers(105, 175))
        ecg = int(rng.choice([0, 1, 2]))
        chol = float(rng.integers(155, 330))
        fbs = int(rng.choice([0, 1], p=[0.8, 0.2]))
        eta = 0.08 * (age - 55.0) + 1.1 * sex + (1.4 if cp == 4 else -0.6)
        labels.append(int(rng.random() < (1.0 / (1.0 + np.exp(-eta)))))
        records.append(
            {
                "synthetic": True,
                "panel_id": DA_A2_RESTING_LABS_PANEL.panel_id,
                "features": {
                    "age": age,
                    "sex": sex,
                    "cp": cp,
                    "trestbps": bp,
                    "restecg": ecg,
                    "chol": chol,
                    "fbs": fbs,
                },
                "units": {"age": "years", "trestbps": "mmHg", "chol": "mg/dL"},
                "missing_reasons": {},
            }
        )
    run = train_research_model(
        records,
        labels,
        DA_A2_RESTING_LABS_PANEL,
        model_id="synth_ai1_generic_regression",
        development_cohort_id="synthetic_cleveland",
        synthetic_data_confirmed=True,
        config=FAST_GENERIC_TEST_CONFIG,
    )
    assert run.internal_evaluation["execution_profile"] == EXECUTION_PROFILE_AI1_GENERIC_V1
    bundle_dir = tmp_path / "ai1_generic_bundle"
    package_research_bundle(run, bundle_dir)
    result = ResearchCadPredictor.from_verified_bundle(
        bundle_dir, trusted_local_root=tmp_path
    ).predict_research_only(records[0])
    assert result.explanation.sum_check_passed is True
    assert 0.0 < result.calibrated_research_score < 1.0


# --------------------------------------------------------------------------- #
# 7. Guarded wrapper: fail-closed readiness (synthetic/mocked only)
# --------------------------------------------------------------------------- #


def test_ratified_operational_registry_is_exactly_activated_training_amendment(
    tmp_path: Path,
) -> None:
    """Post-activation replacement for the obsolete 'registry is empty' sentinel.

    PR #58 activated exactly one ratified amendment by a registry-only change
    at A. Security-correct expectations now are: exactly that record, every
    frozen binding intact, no inferred inference/serving operation, no new
    diagnostic scope, and the guarded wrapper still refusing to run without
    its explicit operator confirmation at this (post-A) development revision.
    """
    registry = execution_mod.RATIFIED_OPERATIONAL_SCOPE_AMENDMENTS
    amendment_id = "CAI-AMEND-AI2-CLEVELAND-D047-V1"
    g = "7f4b7a50d7fd423914e5bd98ed2b525bddbfc627"
    a = "1c29c83cd07fcb0510ac37e185323c231b267670"
    assert set(registry) == {amendment_id}
    record = registry[amendment_id]
    assert record["governance_pr_number"] == 54
    assert record["governance_merge_commit_sha"] == g
    assert record["approved_code_revision"] == g
    assert record["approved_dataset_id"] == "DA-A2"
    assert record["approved_panel_id"] == "da_a2_resting_v1"
    assert len(record["frozen_source_sha256"]) == 64
    assert len(record["frozen_protocol_sha256"]) == 64
    assert len(record["frozen_amendment_document_sha256"]) == 64
    assert record["amendment_document_relative_path"] == (
        "docs/research/gate-pt/17_ai2_operational_scope_amendment.md"
    )
    assert record["approved_operations"] == (
        "persistent_model_packaging",
        "patient_level_shap_background",
    )
    assert record["protected_output_root"] == "data/experiments"
    assert record["ratified_by"] == "Muhammed Fathi"
    assert record["ratification_comment_exact"] == (
        "RATIFY-AI2-OPERATIONAL-SCOPE-EXPANSION"
    )
    assert not any("infer" in op or "serv" in op for op in record["approved_operations"])

    from ai.diagnostic_scope import (
        FROZEN_TRAINING_REVISION_A,
        RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES,
    )

    assert FROZEN_TRAINING_REVISION_A == a
    # The accepted bundle remains inference-prohibited until a NEW, separately
    # ratified and activated scope exists. Training activation is not enough.
    assert RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES == {}

    # Activation does not auto-authorize another training run either: the
    # wrapper still requires the exact operator confirmation before preflight.
    with pytest.raises(ExecutionAuthorizationError) as exc:
        execute_guarded_cleveland_d047_run(
            source_path=tmp_path / "processed.cleveland.data",
            manifest_path=tmp_path / "manifest.json",
            panel_id="da_a2_resting_v1",
            output_bundle_dir=tmp_path / "out_bundle",
            repo_root=REPO_ROOT,
            training_config=None,
            operator_confirmation=None,
        )
    assert exc.value.code == "guarded_wrapper_operator_confirmation_required"


def test_guarded_wrapper_rejects_panel_config_and_confirmation_before_preflight(
    tmp_path: Path,
) -> None:
    base = dict(
        source_path=tmp_path / "processed.cleveland.data",
        manifest_path=tmp_path / "manifest.json",
        panel_id="da_a2_resting_v1",
        output_bundle_dir=tmp_path / "out_bundle",
        repo_root=REPO_ROOT,
        training_config=None,
        operator_confirmation=GUARDED_CLEVELAND_D047_OPERATOR_CONFIRMATION,
    )
    with pytest.raises(ExecutionAuthorizationError) as exc_panel:
        execute_guarded_cleveland_d047_run(**{**base, "panel_id": "da_a2_resting_labs_v1"})
    assert exc_panel.value.code == "guarded_wrapper_panel_rejected"

    with pytest.raises(ExecutionAuthorizationError) as exc_cfg:
        execute_guarded_cleveland_d047_run(
            **{**base, "training_config": FAST_D047_TEST_CONFIG}
        )
    assert exc_cfg.value.code == "guarded_wrapper_frozen_config_required"

    with pytest.raises(ExecutionAuthorizationError) as exc_conf:
        execute_guarded_cleveland_d047_run(**{**base, "operator_confirmation": "yes"})
    assert exc_conf.value.code == "guarded_wrapper_operator_confirmation_required"

    with pytest.raises(ExecutionAuthorizationError) as exc_none:
        execute_guarded_cleveland_d047_run(**{**base, "operator_confirmation": None})
    assert exc_none.value.code == "guarded_wrapper_operator_confirmation_required"


def test_guarded_wrapper_runs_preflight_first_and_fails_closed_on_linux(
    tmp_path: Path,
) -> None:
    from research.experiments.errors import RuntimeGuardError

    src = tmp_path / "processed.cleveland.data"
    src.write_bytes(_complete_synthetic_cleveland_bytes())
    before_stat = src.stat()
    with pytest.raises(RuntimeGuardError):
        execute_guarded_cleveland_d047_run(
            source_path=src,
            manifest_path=tmp_path / "manifest.json",
            panel_id="da_a2_resting_v1",
            output_bundle_dir=tmp_path / "out_bundle",
            repo_root=REPO_ROOT,
            training_config=None,
            operator_confirmation=GUARDED_CLEVELAND_D047_OPERATOR_CONFIRMATION,
        )
    # Preflight runs before source-row parsing: source bytes untouched, no output.
    assert src.stat().st_size == before_stat.st_size
    assert not (tmp_path / "out_bundle").exists()


def _fake_preflight_context(tmp_path: Path) -> Any:
    repo = tmp_path / "fake_repo"
    canonical_manifest = repo / "data" / "manifests" / "internal_exploratory_authorization.local.json"
    canonical_manifest.parent.mkdir(parents=True, exist_ok=True)
    canonical_manifest.write_text("{}", encoding="utf-8")
    canonical_source = repo / "data" / "raw" / "uci-45" / "processed.cleveland.data"
    canonical_source.parent.mkdir(parents=True, exist_ok=True)
    canonical_source.write_bytes(_complete_synthetic_cleveland_bytes())
    digest, _ = sha256_file(canonical_source)
    ctx = MagicMock()
    ctx.repo_root = repo
    ctx.source_path = canonical_source
    ctx.source_sha256 = digest.lower()
    ctx.source_size_bytes = canonical_source.stat().st_size
    ctx.current_git_commit = "a" * 40
    ctx.authorization = {"expected_source_sha256": digest.lower()}
    return ctx


def _authorized_mock_context(source_sha: str, *, packaging: bool, shap: bool) -> Any:
    ctx = MagicMock()
    ctx.dataset_id = "DA-A2"
    ctx.panel_id = "da_a2_resting_v1"
    ctx.expected_source_sha256 = source_sha.lower()
    ctx.model_packaging_authorized = packaging
    ctx.patient_shap_authorized = shap
    return ctx


def test_guarded_wrapper_full_sequence_order_and_single_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ai.packaging import BUNDLE_ACCEPTANCE_MARKER_FILENAME

    preflight = _fake_preflight_context(tmp_path)
    calls: list[str] = []
    verify_kwargs: list[dict[str, Any]] = []

    def _fake_preflight(*args: Any, **kwargs: Any) -> Any:
        calls.append("preflight")
        assert Path(kwargs["repo_root"]) == tmp_path / "fake_repo"
        return preflight

    def _fake_parse(*args: Any, **kwargs: Any) -> Any:
        calls.append("parse_authorization")
        assert kwargs["expected_dataset_id"] == "DA-A2"
        assert kwargs["expected_panel_id"] == "da_a2_resting_v1"
        return _authorized_mock_context(preflight.source_sha256, packaging=True, shap=True)

    def _fake_activation(*args: Any, **kwargs: Any) -> None:
        calls.append("activation_binding")
        assert kwargs["effective_commit"] == preflight.current_git_commit
        return None

    def _fake_execute(*args: Any, **kwargs: Any) -> tuple[Any, Any]:
        calls.append("execute_once")
        assert kwargs["training_config"] is None
        assert kwargs["current_git_commit"] == preflight.current_git_commit
        assert kwargs["guarded_cleveland_proof"] is not None
        out = Path(kwargs["output_bundle_dir"])
        out.mkdir(parents=True, exist_ok=False)
        (out / "manifest.json").write_text("{}", encoding="utf-8")
        return MagicMock(), MagicMock()

    def _fake_verify_source(ctx: Any) -> None:
        calls.append("verify_source")
        assert ctx is preflight

    def _fake_verify_bundle(*args: Any, **kwargs: Any) -> Any:
        calls.append("verify_bundle")
        verify_kwargs.append(dict(kwargs))
        return MagicMock()

    monkeypatch.setattr(execution_mod, "cleveland_run_preflight", _fake_preflight)
    monkeypatch.setattr(
        execution_mod, "parse_and_validate_research_authorization", _fake_parse
    )
    monkeypatch.setattr(
        execution_mod, "_enforce_cleveland_activation_revision_binding", _fake_activation
    )
    monkeypatch.setattr(execution_mod, "execute_authorized_research_run", _fake_execute)
    monkeypatch.setattr(
        execution_mod, "cleveland_verify_source_still_unchanged", _fake_verify_source
    )
    monkeypatch.setattr(execution_mod, "verify_trusted_local_bundle", _fake_verify_bundle)

    trained, descriptor = execute_guarded_cleveland_d047_run(
        source_path=preflight.source_path,
        manifest_path=preflight.repo_root
        / "data"
        / "manifests"
        / "internal_exploratory_authorization.local.json",
        panel_id="da_a2_resting_v1",
        output_bundle_dir=preflight.repo_root / "data" / "experiments" / "new_bundle",
        repo_root=preflight.repo_root,
        training_config=None,
        operator_confirmation=GUARDED_CLEVELAND_D047_OPERATOR_CONFIRMATION,
    )
    assert trained is not None and descriptor is not None
    assert calls == [
        "preflight",
        "parse_authorization",
        "activation_binding",
        "execute_once",
        "verify_source",
        "verify_bundle",  # step 9: pre-acceptance custody check
        "verify_bundle",  # step 11: final acceptance-required verification
    ]
    # Step 9 must not require the marker it precedes; step 11 must.
    assert verify_kwargs[0].get("_require_post_run_acceptance") is False
    assert verify_kwargs[1].get("_require_post_run_acceptance", True) is True
    # Step 10 records post-run acceptance inside the output bundle directory.
    assert (
        preflight.repo_root
        / "data"
        / "experiments"
        / "new_bundle"
        / BUNDLE_ACCEPTANCE_MARKER_FILENAME
    ).exists()


def test_guarded_wrapper_binds_paths_revision_and_both_operations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    preflight = _fake_preflight_context(tmp_path)
    monkeypatch.setattr(
        execution_mod, "cleveland_run_preflight", lambda **kwargs: preflight
    )
    monkeypatch.setattr(
        execution_mod,
        "parse_and_validate_research_authorization",
        lambda *a, **k: _authorized_mock_context(
            preflight.source_sha256, packaging=True, shap=True
        ),
    )
    canonical_manifest = (
        preflight.repo_root / "data" / "manifests" / "internal_exploratory_authorization.local.json"
    )
    other_manifest = tmp_path / "other_manifest.json"
    other_manifest.write_text("{}", encoding="utf-8")
    with pytest.raises(ExecutionAuthorizationError) as exc_manifest:
        execute_guarded_cleveland_d047_run(
            source_path=preflight.source_path,
            manifest_path=other_manifest,
            panel_id="da_a2_resting_v1",
            output_bundle_dir=tmp_path / "out_bundle",
            repo_root=preflight.repo_root,
            operator_confirmation=GUARDED_CLEVELAND_D047_OPERATOR_CONFIRMATION,
        )
    assert exc_manifest.value.code == "guarded_wrapper_manifest_path_mismatch"

    other_source = tmp_path / "other_source.data"
    other_source.write_bytes(b"other")
    with pytest.raises(ExecutionAuthorizationError) as exc_source:
        execute_guarded_cleveland_d047_run(
            source_path=other_source,
            manifest_path=canonical_manifest,
            panel_id="da_a2_resting_v1",
            output_bundle_dir=tmp_path / "out_bundle",
            repo_root=preflight.repo_root,
            operator_confirmation=GUARDED_CLEVELAND_D047_OPERATOR_CONFIRMATION,
        )
    assert exc_source.value.code == "guarded_wrapper_source_path_mismatch"

    with pytest.raises(ExecutionAuthorizationError) as exc_rev:
        execute_guarded_cleveland_d047_run(
            source_path=preflight.source_path,
            manifest_path=canonical_manifest,
            panel_id="da_a2_resting_v1",
            output_bundle_dir=tmp_path / "out_bundle",
            repo_root=preflight.repo_root,
            current_git_commit="b" * 40,
            operator_confirmation=GUARDED_CLEVELAND_D047_OPERATOR_CONFIRMATION,
        )
    assert exc_rev.value.code == "guarded_wrapper_revision_mismatch"

    # Missing either operational authorization fails before any fitting.
    monkeypatch.setattr(
        execution_mod,
        "parse_and_validate_research_authorization",
        lambda *a, **k: _authorized_mock_context(
            preflight.source_sha256, packaging=True, shap=False
        ),
    )
    executed: list[bool] = []
    monkeypatch.setattr(
        execution_mod,
        "execute_authorized_research_run",
        lambda *a, **k: executed.append(True),
    )
    with pytest.raises(ExecutionAuthorizationError) as exc_ops:
        execute_guarded_cleveland_d047_run(
            source_path=preflight.source_path,
            manifest_path=canonical_manifest,
            panel_id="da_a2_resting_v1",
            output_bundle_dir=tmp_path / "out_bundle",
            repo_root=preflight.repo_root,
            operator_confirmation=GUARDED_CLEVELAND_D047_OPERATOR_CONFIRMATION,
        )
    assert exc_ops.value.code == "guarded_wrapper_operational_authorization_missing"
    assert executed == []


def test_guarded_wrapper_quarantines_source_mismatch_and_custody_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    preflight = _fake_preflight_context(tmp_path)
    monkeypatch.setattr(
        execution_mod, "cleveland_run_preflight", lambda **kwargs: preflight
    )
    monkeypatch.setattr(
        execution_mod,
        "parse_and_validate_research_authorization",
        lambda *a, **k: _authorized_mock_context(
            preflight.source_sha256, packaging=True, shap=True
        ),
    )

    def _fake_execute(*args: Any, **kwargs: Any) -> tuple[Any, Any]:
        out = Path(kwargs["output_bundle_dir"])
        out.mkdir(parents=True, exist_ok=False)
        (out / "evidence.txt").write_text("preserved", encoding="utf-8")
        return MagicMock(), MagicMock()

    monkeypatch.setattr(execution_mod, "execute_authorized_research_run", _fake_execute)
    monkeypatch.setattr(
        execution_mod,
        "_enforce_cleveland_activation_revision_binding",
        lambda **kwargs: None,
    )
    canonical_manifest = (
        preflight.repo_root / "data" / "manifests" / "internal_exploratory_authorization.local.json"
    )

    def _raise_source_mismatch(ctx: Any) -> None:
        raise RuntimeError("source bytes changed")

    monkeypatch.setattr(
        execution_mod, "cleveland_verify_source_still_unchanged", _raise_source_mismatch
    )
    with pytest.raises(ExecutionAuthorizationError) as exc_quarantine:
        execute_guarded_cleveland_d047_run(
            source_path=preflight.source_path,
            manifest_path=canonical_manifest,
            panel_id="da_a2_resting_v1",
            output_bundle_dir=tmp_path / "quarantine_bundle",
            repo_root=preflight.repo_root,
            operator_confirmation=GUARDED_CLEVELAND_D047_OPERATOR_CONFIRMATION,
        )
    assert exc_quarantine.value.code == "guarded_wrapper_source_changed_quarantined"
    quarantine_marker = (
        tmp_path / "quarantine_bundle" / "QUARANTINED_DO_NOT_TRUST.json"
    )
    assert quarantine_marker.is_file()
    assert (tmp_path / "quarantine_bundle" / "evidence.txt").is_file()

    monkeypatch.setattr(
        execution_mod, "cleveland_verify_source_still_unchanged", lambda ctx: None
    )

    def _raise_custody(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("HMAC mismatch")

    monkeypatch.setattr(execution_mod, "verify_trusted_local_bundle", _raise_custody)
    with pytest.raises(ExecutionAuthorizationError) as exc_custody:
        execute_guarded_cleveland_d047_run(
            source_path=preflight.source_path,
            manifest_path=canonical_manifest,
            panel_id="da_a2_resting_v1",
            output_bundle_dir=tmp_path / "custody_bundle",
            repo_root=preflight.repo_root,
            operator_confirmation=GUARDED_CLEVELAND_D047_OPERATOR_CONFIRMATION,
        )
    assert exc_custody.value.code == "guarded_wrapper_bundle_custody_failed_quarantined"
    assert (tmp_path / "custody_bundle" / "QUARANTINED_DO_NOT_TRUST.json").is_file()
    assert (tmp_path / "custody_bundle" / "evidence.txt").is_file()


def test_guarded_wrapper_never_retries_after_fitting_starts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    preflight = _fake_preflight_context(tmp_path)
    monkeypatch.setattr(
        execution_mod, "cleveland_run_preflight", lambda **kwargs: preflight
    )
    monkeypatch.setattr(
        execution_mod,
        "parse_and_validate_research_authorization",
        lambda *a, **k: _authorized_mock_context(
            preflight.source_sha256, packaging=True, shap=True
        ),
    )
    monkeypatch.setattr(
        execution_mod,
        "_enforce_cleveland_activation_revision_binding",
        lambda **kwargs: None,
    )
    attempts: list[int] = []

    def _fail_after_fitting(*args: Any, **kwargs: Any) -> tuple[Any, Any]:
        attempts.append(1)
        raise RuntimeError("simulated failure after fitting started")

    monkeypatch.setattr(execution_mod, "execute_authorized_research_run", _fail_after_fitting)
    canonical_manifest = (
        preflight.repo_root / "data" / "manifests" / "internal_exploratory_authorization.local.json"
    )
    with pytest.raises(RuntimeError, match="after fitting started"):
        execute_guarded_cleveland_d047_run(
            source_path=preflight.source_path,
            manifest_path=canonical_manifest,
            panel_id="da_a2_resting_v1",
            output_bundle_dir=tmp_path / "retry_bundle",
            repo_root=preflight.repo_root,
            operator_confirmation=GUARDED_CLEVELAND_D047_OPERATOR_CONFIRMATION,
        )
    assert len(attempts) == 1


# --------------------------------------------------------------------------- #
# 8. Windows Python 3.12 compatibility (static, cross-platform)
# --------------------------------------------------------------------------- #


def test_windows_python312_compatibility_static_checks() -> None:
    import ast

    banned_roots = {"pwd", "grp", "fcntl", "termios", "resource"}
    banned_calls = {"fchmod", "fchown", "chown", "mknod"}
    for rel in (
        Path("ai/training.py"),
        Path("ai/execution.py"),
        Path("ai/packaging.py"),
        Path("ai/__init__.py"),
        Path("tests/experiments/test_authorized_real_data_execution.py"),
        Path("tests/experiments/test_cleveland_d047_fidelity.py"),
    ):
        tree = ast.parse((REPO_ROOT / rel).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = {alias.name.split(".")[0] for alias in node.names}
                assert not (roots & banned_roots), f"{rel} imports {roots & banned_roots}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] not in banned_roots, rel
            elif isinstance(node, ast.Attribute) and node.attr in banned_calls:
                raise AssertionError(f"{rel} uses POSIX-only os.{node.attr}")
    # Profile constants are plain ASCII identifiers (no locale-sensitive text).
    for value in (
        EXECUTION_PROFILE_AI1_GENERIC_V1,
        EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1,
        GUARDED_CLEVELAND_D047_OPERATOR_CONFIRMATION,
    ):
        value.encode("ascii")


# --------------------------------------------------------------------------- #
# 9. Guarded execution boundary: silent direct invocation is prohibited
# --------------------------------------------------------------------------- #


def _forbid_call(recorder: list[str], name: str) -> Any:
    def _spy(*args: Any, **kwargs: Any) -> Any:
        reorder.append(name)
        raise AssertionError(f"{name} must not be called before the guard passes")
    return _spy


def test_direct_cleveland_execution_without_proof_fails_before_any_source_access(
    d047_isolated_repo: tuple[Path, str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Direct Cleveland invocation without a wrapper proof fails closed first.

    Only the OS-level Windows runtime guard is bypassed (exactly as the
    shared simulation helper does); no guarded proof is supplied even though
    the manifest is fully authorized. Manifest authorization, source hashing,
    source parsing, and fitting must all remain untouched.
    """
    repo, _, _ = d047_isolated_repo
    source_path = repo / "data" / "raw" / "uci-45" / "processed.cleveland.data"
    source_sha = _create_synthetic_cleveland_file(source_path)
    manifest_path = repo / "data" / "experiments" / "manifest.json"
    _create_valid_auth_manifest(
        manifest_path,
        repo,
        dataset_id="DA-A2",
        panel_id="da_a2_resting_v1",
        source_sha256=source_sha,
        row_count=303,
        model_packaging_authorized=True,
        patient_shap_authorized=True,
    )
    monkeypatch.setattr(
        execution_mod, "cleveland_enforce_local_windows_runtime", lambda **kwargs: None
    )
    touched: list[str] = []
    monkeypatch.setattr(
        execution_mod,
        "parse_and_validate_research_authorization",
        _forbid_call(touched, "parse_and_validate_research_authorization"),
    )
    monkeypatch.setattr(
        execution_mod, "sha256_file", _forbid_call(touched, "sha256_file")
    )
    monkeypatch.setattr(
        execution_mod,
        "load_cleveland_source_records",
        _forbid_call(touched, "load_cleveland_source_records"),
    )
    monkeypatch.setattr(
        execution_mod,
        "_execute_shared_training_pipeline",
        _forbid_call(touched, "_execute_shared_training_pipeline"),
    )
    output_dir = repo / "data" / "experiments" / "unguarded_bundle"
    with pytest.raises(ExecutionAuthorizationError) as exc_info:
        execute_authorized_research_run(
            source_path=source_path,
            manifest_path=manifest_path,
            panel_id="da_a2_resting_v1",
            output_bundle_dir=output_dir,
            repo_root=repo,
            training_config=None,
            current_git_commit=None,
            guarded_cleveland_proof=None,
        )
    assert exc_info.value.code == "unguarded_cleveland_execution_blocked"
    assert touched == []
    assert not output_dir.exists()


def test_stale_guarded_proof_bound_elsewhere_fails_before_parsing_or_fitting(
    d047_isolated_repo: tuple[Path, str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A proof minted for different execution parameters cannot be reused."""
    repo, _, _ = d047_isolated_repo
    source_path = repo / "data" / "raw" / "uci-45" / "processed.cleveland.data"
    source_sha = _create_synthetic_cleveland_file(source_path)
    manifest_path = repo / "data" / "experiments" / "manifest.json"
    _create_valid_auth_manifest(
        manifest_path,
        repo,
        dataset_id="DA-A2",
        panel_id="da_a2_resting_v1",
        source_sha256=source_sha,
        row_count=303,
        model_packaging_authorized=True,
        patient_shap_authorized=True,
    )
    monkeypatch.setattr(
        execution_mod, "cleveland_enforce_local_windows_runtime", lambda **kwargs: None
    )
    touched: list[str] = []
    monkeypatch.setattr(
        execution_mod,
        "load_cleveland_source_records",
        _forbid_call(touched, "load_cleveland_source_records"),
    )
    monkeypatch.setattr(
        execution_mod,
        "_execute_shared_training_pipeline",
        _forbid_call(touched, "_execute_shared_training_pipeline"),
    )
    stale_proof = execution_mod._issue_test_guarded_cleveland_proof(
        source_path=source_path,
        manifest_path=manifest_path,
        output_bundle_dir=repo / "data" / "experiments" / "other_bundle",
        repo_root=repo,
        current_git_commit=None,
    )
    with pytest.raises(ExecutionAuthorizationError) as exc_info:
        execute_authorized_research_run(
            source_path=source_path,
            manifest_path=manifest_path,
            panel_id="da_a2_resting_v1",
            output_bundle_dir=repo / "data" / "experiments" / "real_bundle",
            repo_root=repo,
            training_config=None,
            current_git_commit=None,
            guarded_cleveland_proof=stale_proof,
        )
    assert exc_info.value.code == "guarded_proof_binding_mismatch"
    assert touched == []


# --------------------------------------------------------------------------- #
# 10. Activation-revision binding: fail closed until trusted evidence exists
# --------------------------------------------------------------------------- #


def _make_governance_activation_repo(
    tmp_path: Path,
    *,
    extra_diff_file: bool = False,
    dirty_tracked_file: bool = False,
) -> tuple[Path, str, str]:
    """Real git repo with governance commit G and activation commit A (HEAD)."""
    repo = tmp_path / "activation_repo"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test Runner"],
        cwd=str(repo),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=str(repo),
        check=True,
        capture_output=True,
    )
    (repo / "README.md").write_text("governance baseline\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "governance G"], cwd=str(repo), check=True, capture_output=True
    )
    g_sha = (
        subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo),
            check=True,
            capture_output=True,
            text=True,
        )
        .stdout.strip()
        .lower()
    )
    ai_pkg = repo / "ai"
    ai_pkg.mkdir(exist_ok=True)
    (ai_pkg / "execution.py").write_text(
        "RATIFIED_OPERATIONAL_SCOPE_AMENDMENTS = {'TEST-AMEND': {}}\n",
        encoding="utf-8",
    )
    if extra_diff_file:
        (repo / "unreviewed_change.py").write_text("print('x')\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "activation A"],
        cwd=str(repo),
        check=True,
        capture_output=True,
    )
    a_sha = (
        subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo),
            check=True,
            capture_output=True,
            text=True,
        )
        .stdout.strip()
        .lower()
    )
    if dirty_tracked_file:
        (repo / "README.md").write_text("dirty\n", encoding="utf-8")
    return repo, g_sha, a_sha


def _write_activation_manifest(manifest_path: Path, amendment: Any) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps({"operation_scope_amendment": amendment}), encoding="utf-8"
    )


def test_activation_revision_binding_happy_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, g_sha, a_sha = _make_governance_activation_repo(tmp_path)
    manifest_path = repo / "manifest.json"
    _write_activation_manifest(
        manifest_path,
        {"amendment_id": "TEST-AMEND", "activation_merge_commit_sha": a_sha},
    )
    monkeypatch.setattr(
        execution_mod,
        "RATIFIED_OPERATIONAL_SCOPE_AMENDMENTS",
        {"TEST-AMEND": {"governance_merge_commit_sha": g_sha}},
    )
    execution_mod._enforce_cleveland_activation_revision_binding(
        manifest_path=manifest_path, effective_commit=a_sha, repo_root=repo
    )


def test_activation_revision_binding_missing_evidence_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, g_sha, a_sha = _make_governance_activation_repo(tmp_path)
    monkeypatch.setattr(
        execution_mod,
        "RATIFIED_OPERATIONAL_SCOPE_AMENDMENTS",
        {"TEST-AMEND": {"governance_merge_commit_sha": g_sha}},
    )
    # No amendment mapping at all.
    missing = repo / "missing.json"
    missing.write_text("{}", encoding="utf-8")
    with pytest.raises(ExecutionAuthorizationError) as exc_missing:
        execution_mod._enforce_cleveland_activation_revision_binding(
            manifest_path=missing, effective_commit=a_sha, repo_root=repo
        )
    assert exc_missing.value.code == "activation_merge_evidence_missing"

    # Amendment without the compensating activation SHA field.
    no_sha = repo / "no_sha.json"
    _write_activation_manifest(no_sha, {"amendment_id": "TEST-AMEND"})
    with pytest.raises(ExecutionAuthorizationError) as exc_no_sha:
        execution_mod._enforce_cleveland_activation_revision_binding(
            manifest_path=no_sha, effective_commit=a_sha, repo_root=repo
        )
    assert exc_no_sha.value.code == "activation_merge_evidence_missing"

    # Malformed activation SHA is not evidence.
    bad_sha = repo / "bad_sha.json"
    _write_activation_manifest(
        bad_sha, {"amendment_id": "TEST-AMEND", "activation_merge_commit_sha": "zzz"}
    )
    with pytest.raises(ExecutionAuthorizationError) as exc_bad_sha:
        execution_mod._enforce_cleveland_activation_revision_binding(
            manifest_path=bad_sha, effective_commit=a_sha, repo_root=repo
        )
    assert exc_bad_sha.value.code == "activation_merge_evidence_missing"


def test_activation_revision_binding_head_and_worktree_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, g_sha, a_sha = _make_governance_activation_repo(tmp_path)
    manifest_path = repo / "manifest.json"
    _write_activation_manifest(
        manifest_path,
        {"amendment_id": "TEST-AMEND", "activation_merge_commit_sha": a_sha},
    )
    monkeypatch.setattr(
        execution_mod,
        "RATIFIED_OPERATIONAL_SCOPE_AMENDMENTS",
        {"TEST-AMEND": {"governance_merge_commit_sha": g_sha}},
    )
    # Declared activation merge is not the actual HEAD (stale/supplied SHA).
    stale = repo / "stale.json"
    _write_activation_manifest(
        stale, {"amendment_id": "TEST-AMEND", "activation_merge_commit_sha": g_sha}
    )
    with pytest.raises(ExecutionAuthorizationError) as exc_stale:
        execution_mod._enforce_cleveland_activation_revision_binding(
            manifest_path=stale, effective_commit=g_sha, repo_root=repo
        )
    assert exc_stale.value.code == "activation_revision_mismatch"

    # Preflight-verified HEAD no longer matches the independently resolved HEAD.
    with pytest.raises(ExecutionAuthorizationError) as exc_moved:
        execution_mod._enforce_cleveland_activation_revision_binding(
            manifest_path=manifest_path, effective_commit=g_sha, repo_root=repo
        )
    assert exc_moved.value.code == "activation_revision_mismatch"


def test_activation_revision_binding_dirty_worktree_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, g_sha, a_sha = _make_governance_activation_repo(
        tmp_path, dirty_tracked_file=True
    )
    manifest_path = repo / "manifest.json"
    _write_activation_manifest(
        manifest_path,
        {"amendment_id": "TEST-AMEND", "activation_merge_commit_sha": a_sha},
    )
    monkeypatch.setattr(
        execution_mod,
        "RATIFIED_OPERATIONAL_SCOPE_AMENDMENTS",
        {"TEST-AMEND": {"governance_merge_commit_sha": g_sha}},
    )
    with pytest.raises(ExecutionAuthorizationError) as exc_dirty:
        execution_mod._enforce_cleveland_activation_revision_binding(
            manifest_path=manifest_path, effective_commit=a_sha, repo_root=repo
        )
    assert exc_dirty.value.code == "activation_worktree_not_clean"


def test_activation_revision_binding_trust_and_diff_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, g_sha, a_sha = _make_governance_activation_repo(tmp_path)
    manifest_path = repo / "manifest.json"
    _write_activation_manifest(
        manifest_path,
        {"amendment_id": "TEST-AMEND", "activation_merge_commit_sha": a_sha},
    )
    # Amendment unknown to the trusted registry: no independent evidence.
    monkeypatch.setattr(execution_mod, "RATIFIED_OPERATIONAL_SCOPE_AMENDMENTS", {})
    with pytest.raises(ExecutionAuthorizationError) as exc_untrusted:
        execution_mod._enforce_cleveland_activation_revision_binding(
            manifest_path=manifest_path, effective_commit=a_sha, repo_root=repo
        )
    assert exc_untrusted.value.code == "activation_trusted_evidence_missing"

    # Trusted G that is not an ancestor of HEAD.
    monkeypatch.setattr(
        execution_mod,
        "RATIFIED_OPERATIONAL_SCOPE_AMENDMENTS",
        {"TEST-AMEND": {"governance_merge_commit_sha": "f" * 40}},
    )
    with pytest.raises(ExecutionAuthorizationError) as exc_ancestry:
        execution_mod._enforce_cleveland_activation_revision_binding(
            manifest_path=manifest_path, effective_commit=a_sha, repo_root=repo
        )
    assert exc_ancestry.value.code == "activation_governance_ancestry_failed"

    # Diff beyond the registry-only file stops activation.
    wide_repo, wide_g, wide_a = _make_governance_activation_repo(
        tmp_path / "wide", extra_diff_file=True
    )
    wide_manifest = wide_repo / "manifest.json"
    _write_activation_manifest(
        wide_manifest,
        {"amendment_id": "TEST-AMEND", "activation_merge_commit_sha": wide_a},
    )
    monkeypatch.setattr(
        execution_mod,
        "RATIFIED_OPERATIONAL_SCOPE_AMENDMENTS",
        {"TEST-AMEND": {"governance_merge_commit_sha": wide_g}},
    )
    with pytest.raises(ExecutionAuthorizationError) as exc_diff:
        execution_mod._enforce_cleveland_activation_revision_binding(
            manifest_path=wide_manifest, effective_commit=wide_a, repo_root=wide_repo
        )
    assert exc_diff.value.code == "activation_diff_not_registry_only"


# --------------------------------------------------------------------------- #
# 11. Quarantine semantics: a failed post-run check can never load as trusted
# --------------------------------------------------------------------------- #


def test_quarantined_bundle_refused_by_trusted_loading_after_post_write_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Post-packaging failure quarantines a real bundle; loading must refuse it.

    The mocked inner execution writes a genuine synthetic bundle (valid HMAC
    attestation included); the post-run source re-verification then fails.
    The wrapper must preserve every artifact, record a quarantine marker, and
    every trusted-loading path must refuse the directory afterwards.
    """
    from ai.filesystem_security import ensure_private_directory
    from ai.inference import ResearchCadPredictor
    from ai.packaging import (
        BUNDLE_QUARANTINE_MARKER_FILENAME,
        package_research_bundle,
        verify_research_bundle,
        verify_trusted_local_bundle,
    )

    tmp_path = ensure_private_directory(tmp_path)
    preflight = _fake_preflight_context(tmp_path)
    monkeypatch.setattr(
        execution_mod, "cleveland_run_preflight", lambda **kwargs: preflight
    )
    monkeypatch.setattr(
        execution_mod,
        "parse_and_validate_research_authorization",
        lambda *a, **k: _authorized_mock_context(
            preflight.source_sha256, packaging=True, shap=True
        ),
    )
    monkeypatch.setattr(
        execution_mod,
        "_enforce_cleveland_activation_revision_binding",
        lambda **kwargs: None,
    )

    def _fake_execute_and_package(*args: Any, **kwargs: Any) -> tuple[Any, Any]:
        out = Path(kwargs["output_bundle_dir"])
        records, labels = _generate_synthetic_resting_cohort(72, seed=80808)
        run = train_research_model(
            records,
            labels,
            DA_A2_RESTING_PANEL,
            model_id="synth_quarantine_e2e",
            development_cohort_id="synthetic_cleveland",
            development_dataset_id="DA-A2",
            synthetic_data_confirmed=True,
            config=FAST_D047_TEST_CONFIG,
        )
        package_research_bundle(run, out)
        return run, MagicMock()

    monkeypatch.setattr(
        execution_mod, "execute_authorized_research_run", _fake_execute_and_package
    )

    def _raise_source_changed(ctx: Any) -> None:
        raise RuntimeError("source bytes changed after packaging")

    monkeypatch.setattr(
        execution_mod, "cleveland_verify_source_still_unchanged", _raise_source_changed
    )
    bundle_dir = preflight.repo_root / "data" / "experiments" / "quarantine_real_bundle"
    with pytest.raises(ExecutionAuthorizationError) as exc_info:
        execute_guarded_cleveland_d047_run(
            source_path=preflight.source_path,
            manifest_path=preflight.repo_root
            / "data"
            / "manifests"
            / "internal_exploratory_authorization.local.json",
            panel_id="da_a2_resting_v1",
            output_bundle_dir=bundle_dir,
            repo_root=preflight.repo_root,
            training_config=None,
            operator_confirmation=GUARDED_CLEVELAND_D047_OPERATOR_CONFIRMATION,
        )
    assert exc_info.value.code == "guarded_wrapper_source_changed_quarantined"

    # Marker recorded; every previously written artifact preserved for audit.
    marker = bundle_dir / BUNDLE_QUARANTINE_MARKER_FILENAME
    assert marker.is_file()
    marker_doc = json.loads(marker.read_text(encoding="utf-8"))
    assert marker_doc["quarantined"] is True
    assert marker_doc["accepted_for_loading"] is False
    assert (
        marker_doc["reason_code"] == "guarded_wrapper_source_changed_quarantined"
    )
    assert (bundle_dir / "manifest.json").is_file()
    assert (bundle_dir / "model.joblib").is_file()

    # No trusted-loading path may accept the quarantined directory.
    with pytest.raises(BundleIntegrityError) as exc_trusted:
        verify_trusted_local_bundle(bundle_dir, trusted_local_root=tmp_path)
    assert exc_trusted.value.code == "bundle_quarantined_not_accepted"
    with pytest.raises(BundleIntegrityError) as exc_structural:
        verify_research_bundle(bundle_dir)
    assert exc_structural.value.code == "bundle_quarantined_not_accepted"
    with pytest.raises(BundleIntegrityError) as exc_predictor:
        ResearchCadPredictor.from_verified_bundle(
            bundle_dir, trusted_local_root=tmp_path
        )
    assert exc_predictor.value.code == "bundle_quarantined_not_accepted"


def test_quarantine_marker_unit_semantics(tmp_path: Path) -> None:
    """Marker refuses loading, never deletes artifacts, never overwrites itself."""
    from ai.filesystem_security import ensure_private_directory
    from ai.packaging import (
        package_research_bundle,
        verify_trusted_local_bundle,
        write_bundle_quarantine_marker,
    )

    tmp_path = ensure_private_directory(tmp_path)
    records, labels = _generate_synthetic_resting_cohort(72, seed=90909)
    run = train_research_model(
        records,
        labels,
        DA_A2_RESTING_PANEL,
        model_id="synth_quarantine_unit",
        development_cohort_id="synthetic_cleveland",
        synthetic_data_confirmed=True,
        config=FAST_D047_TEST_CONFIG,
    )
    bundle_dir = tmp_path / "marker_unit_bundle"
    package_research_bundle(run, bundle_dir)
    # Sanity: the intact bundle loads before quarantine.
    verify_trusted_local_bundle(bundle_dir, trusted_local_root=tmp_path)

    marker = write_bundle_quarantine_marker(
        bundle_dir, reason_code="unit_check", detail="synthetic quarantine unit check"
    )
    assert marker.is_file()
    with pytest.raises(BundleIntegrityError) as exc_info:
        verify_trusted_local_bundle(bundle_dir, trusted_local_root=tmp_path)
    assert exc_info.value.code == "bundle_quarantined_not_accepted"

    # A second quarantine attempt preserves the first failure record.
    marker_again = write_bundle_quarantine_marker(
        bundle_dir, reason_code="later", detail="must not overwrite"
    )
    assert marker_again == marker
    assert json.loads(marker.read_text(encoding="utf-8"))["reason_code"] == "unit_check"
    assert (bundle_dir / "model.joblib").is_file()


# --------------------------------------------------------------------------- #
# 12. Scientific reproducibility: original fold-local D-047 preprocessing
# --------------------------------------------------------------------------- #


def _dense(matrix: Any) -> np.ndarray:
    return matrix.toarray() if hasattr(matrix, "toarray") else np.asarray(matrix)


def test_d047_preprocessing_matches_original_fold_local_implementation() -> None:
    """Compare AI encoding against the original fold-local D-047 pipeline.

    The registered D-047 implementation fits a per-training-fold sklearn
    ``ColumnTransformer`` (median/mode imputation, LR-only z-scoring,
    fixed-category drop-first one-hot). On complete synthetic data the AI
    fold-local preprocessor must reproduce its 8 shared columns, and
    same-seed fits on either encoding must agree.
    """
    from sklearn.metrics import roc_auc_score

    from research.experiments.models import _preprocessor as original_preprocessor

    X, y = _cohort_matrices(n=120, seed=12121)
    X_tr, y_tr, X_te, y_te = X[:90], y[:90], X[90:], y[90:]
    ai_prep = FoldSafeClinicalPreprocessor.fit(X_tr, DA_A2_RESTING_PANEL)
    Z_ai_tr = ai_prep.transform(X_tr)
    Z_ai_te = ai_prep.transform(X_te)
    # Original column order -> AI column order for the 8 shared columns:
    # age, trestbps, sex_eq1, cp_eq2..4, restecg_eq1..2.
    shared = [(0, 0), (1, 5), (2, 1), (3, 2), (4, 3), (5, 4), (6, 7), (7, 8)]

    orig_lr = original_preprocessor(
        "l2_logistic_regression", CLEVELAND_DEFAULT_CONFIG
    )
    Z_orig_tr = _dense(orig_lr.fit_transform(X_tr))
    Z_orig_te = _dense(orig_lr.transform(X_te))
    assert Z_orig_tr.shape == (90, 8)
    for orig_idx, ai_idx in shared:
        assert np.allclose(
            Z_orig_tr[:, orig_idx], Z_ai_tr[:, ai_idx], rtol=1e-12, atol=1e-12
        )
        assert np.allclose(
            Z_orig_te[:, orig_idx], Z_ai_te[:, ai_idx], rtol=1e-12, atol=1e-12
        )

    seed = derive_cleveland_d047_model_seed(20261026, 1, "l2_logistic_regression")
    lr_orig = LogisticRegression(
        solver="liblinear",
        penalty="l2",
        C=1.0,
        max_iter=2000,
        class_weight=None,
        random_state=seed,
    ).fit(Z_orig_tr, y_tr)
    lr_ai = _build_estimator(
        "l2_logistic_regression",
        {"C": 1.0},
        seed=seed,
        rf_n_estimators=15,
        execution_profile=EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1,
    ).fit(Z_ai_tr, y_tr)
    assert (lr_orig.predict(Z_orig_te) == lr_ai.predict(Z_ai_te)).all()
    assert roc_auc_score(y_te, lr_orig.predict_proba(Z_orig_te)[:, 1]) == pytest.approx(
        roc_auc_score(y_te, lr_ai.predict_proba(Z_ai_te)[:, 1]), abs=1e-12
    )

    # Forest family: one-hots identical and AI z-scoring is a strictly
    # monotone affine map of the original raw numerics (same ordering), so
    # any same-seed forest divergence comes only from the two extra
    # always-present missing-indicator columns: encoded widths 8 vs 10 change
    # the 'sqrt' per-split subsample from 2 to 3 over different index spaces.
    # Measured effect on this fixed synthetic fixture (90 train / 30 holdout,
    # 15 trees, depth 3): 2/30 holdout disagreements, AUROC 0.8235 vs 0.7647.
    # This pins the mechanism and the observed magnitude; it is not a claim
    # about real-data performance direction, and bit-for-bit RF reproduction
    # of earlier D-047 performance is explicitly NOT claimed.
    orig_rf = original_preprocessor(
        "constrained_random_forest", CLEVELAND_DEFAULT_CONFIG
    )
    R_orig_tr = _dense(orig_rf.fit_transform(X_tr))
    R_orig_te = _dense(orig_rf.transform(X_te))
    assert R_orig_tr.shape[1] == 8
    assert Z_ai_tr.shape[1] == 10
    for orig_idx, ai_idx in shared[2:]:
        assert (R_orig_te[:, orig_idx] == Z_ai_te[:, ai_idx]).all()
    for orig_idx, ai_idx in shared[:2]:
        assert (
            np.argsort(R_orig_te[:, orig_idx], kind="stable")
            == np.argsort(Z_ai_te[:, ai_idx], kind="stable")
        ).all()
    rf_seed = derive_cleveland_d047_model_seed(
        20261026, 1, "constrained_random_forest"
    )
    rf_orig = RandomForestClassifier(
        n_estimators=15,
        max_depth=3,
        min_samples_leaf=5,
        max_features="sqrt",
        class_weight=None,
        random_state=rf_seed,
        n_jobs=1,
    ).fit(R_orig_tr, y_tr)
    rf_ai = _build_estimator(
        "constrained_random_forest",
        {"max_depth": 3, "min_samples_leaf": 5},
        seed=rf_seed,
        rf_n_estimators=15,
        execution_profile=EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1,
    ).fit(Z_ai_tr, y_tr)
    rf_disagreements = int(
        (rf_orig.predict(R_orig_te) != rf_ai.predict(Z_ai_te)).sum()
    )
    assert rf_disagreements == 2
    assert roc_auc_score(y_te, rf_orig.predict_proba(R_orig_te)[:, 1]) == pytest.approx(
        0.823529411765, abs=1e-12
    )
    assert roc_auc_score(y_te, rf_ai.predict_proba(Z_ai_te)[:, 1]) == pytest.approx(
        0.764705882353, abs=1e-12
    )


def test_d047_primary_estimate_is_uncalibrated_oof_reported_separately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The D-047 primary estimate is pure uncalibrated OOF; extras are separate.

    Recomputes the reported primary AUROC from the captured uncalibrated
    out-of-fold scores (no calibration may leak in) and verifies the
    cross-fitted calibrated block is built from genuinely different,
    calibrator-transformed scores in its own labeled block.
    """
    from sklearn.metrics import roc_auc_score

    X, y = _cohort_matrices(n=90, seed=47047)
    captured: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    orig_pass = training_mod._run_single_nested_pass

    def _spy(X_in: np.ndarray, y_in: np.ndarray, **kwargs: Any) -> Any:
        uncal, cal, recs, ens = orig_pass(X_in, y_in, **kwargs)
        if y_in is y and "primary" not in captured:
            captured["primary"] = (
                np.asarray(uncal["inner_selected_procedure"]),
                np.asarray(cal["inner_selected_procedure"]),
            )
        return uncal, cal, recs, ens

    monkeypatch.setattr(training_mod, "_run_single_nested_pass", _spy)
    run = _execute_shared_training_pipeline(
        X,
        y,
        DA_A2_RESTING_PANEL,
        model_id="synth_d047_separation_check",
        dev_cohort="synthetic_cleveland",
        dev_dataset="DA-A2:synthetic",
        config=FAST_D047_TEST_CONFIG,
        synthetic_only=True,
    )
    uncal_scores, cal_scores = captured["primary"]
    reported_primary = run.internal_evaluation["uncalibrated_nested_cv"]["repeats"][0][
        "models"
    ]["inner_selected_procedure"]["discrimination"]["roc_auc"]
    assert reported_primary == pytest.approx(
        roc_auc_score(y, uncal_scores), abs=1e-12
    )
    assert run.internal_evaluation["uncalibrated_nested_cv"][
        "post_hoc_calibration_applied"
    ] is False
    # The calibrated block is genuinely separate: different scores, own block.
    assert not np.allclose(uncal_scores, cal_scores)
    reported_calibrated = run.internal_evaluation["cross_fitted_calibrated_nested_cv"][
        "repeats"
    ][0]["models"]["inner_selected_procedure"]["discrimination"]["roc_auc"]
    assert reported_calibrated == pytest.approx(
        roc_auc_score(y, cal_scores), abs=1e-12
    )


# --------------------------------------------------------------------------- #
# 13. D-047 Random Forest feature-space fidelity (same-seed pipeline equivalence)
# --------------------------------------------------------------------------- #


def _generate_rf_selecting_cohort(
    n: int = 120, *, seed: int = 777
) -> tuple[list[dict[str, Any]], list[int]]:
    """Deterministic complete cohort on which inner-CV selects the forest family."""
    rng = np.random.default_rng(seed)
    age = rng.integers(29, 78, size=n).astype(float)
    sex = rng.integers(0, 2, size=n).astype(float)
    cp = rng.integers(1, 5, size=n).astype(float)
    trestbps = rng.integers(94, 201, size=n).astype(float)
    restecg = rng.integers(0, 3, size=n).astype(float)
    logit = (
        -3.0
        + 0.05 * (age - 50)
        + 0.8 * sex
        + 0.4 * (cp - 1)
        + 0.01 * (trestbps - 120)
        + 0.3 * restecg
    )
    labels = [int(v) for v in (rng.random(n) < 1 / (1 + np.exp(-logit)))]
    records: list[dict[str, Any]] = []
    for i in range(n):
        records.append(
            {
                "synthetic": True,
                "panel_id": DA_A2_RESTING_PANEL.panel_id,
                "features": {
                    "age": float(age[i]),
                    "sex": int(sex[i]),
                    "cp": int(cp[i]),
                    "trestbps": float(trestbps[i]),
                    "restecg": int(restecg[i]),
                },
                "units": {"age": "years", "trestbps": "mmHg"},
                "missing_reasons": {},
            }
        )
    return records, labels


def _d047_comparison_configs() -> tuple[Any, ResearchTrainingConfig]:
    """Matched reduced-cost configs: original plan vs AI D-047 profile."""
    original = dataclasses.replace(
        CLEVELAND_DEFAULT_CONFIG,
        outer_folds=3,
        inner_folds=2,
        outer_repeat_seeds=(20261026,),
        rf_n_estimators=25,
    )
    ai_config = dataclasses.replace(
        FAST_D047_TEST_CONFIG,
        rf_max_depths=(3, 5),
        rf_min_samples_leaf=(5, 10),
        rf_n_estimators=25,
    )
    return original, ai_config


def test_d047_rf_matches_original_pipeline_same_seed() -> None:
    """Gap A: the adapted D-047 forest reproduces the original pipeline bit-for-bit."""
    from research.experiments.data_adapter import ClevelandDataset

    records, labels = _generate_rf_selecting_cohort()
    original_config, ai_config = _d047_comparison_configs()
    X_raw = np.array(
        [
            [
                r["features"]["age"],
                r["features"]["sex"],
                r["features"]["cp"],
                r["features"]["trestbps"],
                r["features"]["restecg"],
            ]
            for r in records
        ],
        dtype=np.float64,
    )
    y_raw = np.array(labels, dtype=int)
    dataset = ClevelandDataset(
        X=X_raw,
        y=y_raw,
        feature_names=original_config.feature_names,
        row_count=len(labels),
        binary_target_counts=((0, int((y_raw == 0).sum())), (1, int(y_raw.sum()))),
    )
    original = cleveland_eval._run_nested_cv(dataset, config=original_config)
    assert len(original.repeat_results) == 1
    original_repeat = original.repeat_results[0]

    X_ai, y_ai, _ = validate_cohort_records(
        records, labels, DA_A2_RESTING_PANEL, require_synthetic=True
    )
    uncalibrated, _, fold_records, _ = _run_single_nested_pass(
        X_ai,
        y_ai,
        panel=DA_A2_RESTING_PANEL,
        config=ai_config,
        repeat_seed=20261026,
        retain_fold_models=False,
        fit_cross_calibrators=False,
    )

    # Forest out-of-fold scores: exact same-input/same-seed/same-procedure match.
    assert np.array_equal(
        uncalibrated["constrained_random_forest"],
        original_repeat.predictions["constrained_random_forest"],
    )
    # Inner-selected procedure: exact match (same inner AUCs + same rule).
    assert np.array_equal(
        uncalibrated["inner_selected_procedure"],
        original_repeat.predictions["inner_selected_procedure"],
    )
    # Inner-CV mean ROC-AUC per family per fold: exact match.
    assert len(fold_records) == len(original_repeat.fold_records) == 3
    for ai_fold, original_fold in zip(fold_records, original_repeat.fold_records):
        for family in ("l2_logistic_regression", "constrained_random_forest"):
            assert (
                ai_fold["inner_cv_roc_auc"][family]
                == original_fold["inner_best_mean_roc_auc_by_family"][family]
            )
        assert ai_fold["selected_family"] == original_fold["selected_family"]
        chosen = ai_fold["selected_family"]
        assert chosen == "constrained_random_forest"
        original_params = original_fold["inner_best_parameters_by_family"][chosen]
        assert ai_fold["selected_hyperparameters"] == {
            "max_depth": original_params["classifier__max_depth"],
            "min_samples_leaf": original_params["classifier__min_samples_leaf"],
        }
        # Audit records the forest input space per family.
        assert (
            ai_fold["estimator_input_space_by_family"]["constrained_random_forest"]
            == CLEVELAND_D047_RF_SPACE_VERSION
        )
    # Logistic family stays on the full 10-column encoding: identical ranks,
    # ~1ulp score differences from the two all-zero indicator columns.
    assert np.allclose(
        uncalibrated["l2_logistic_regression"],
        original_repeat.predictions["l2_logistic_regression"],
        rtol=0.0,
        atol=1e-12,
    )


def test_d047_rf_space_matrix_matches_original_encoding() -> None:
    """Gap A: the projected 8-column matrix equals the original preprocessor output."""
    from research.experiments.models import build_family_estimator

    records, labels = _generate_rf_selecting_cohort()
    X_ai, _, _ = validate_cohort_records(
        records, labels, DA_A2_RESTING_PANEL, require_synthetic=True
    )
    prep = FoldSafeClinicalPreprocessor.fit(X_ai, DA_A2_RESTING_PANEL)
    R = _d047_original_rf_matrix(prep, X_ai)
    assert R.shape == (len(labels), CLEVELAND_D047_RF_SPACE_WIDTH)
    # Bit-exact agreement with the original D-047 preprocessor fitted on the
    # same fold data (read-only reference; the original module is untouched).
    original_pipe = build_family_estimator(
        "constrained_random_forest",
        random_state=1,
        config=CLEVELAND_DEFAULT_CONFIG,
    )
    original_pre = original_pipe.named_steps["preprocess"].fit(X_ai)
    assert np.array_equal(R, original_pre.transform(X_ai))
    # Numerics are raw median-imputed values in panel order (no z-scoring).
    assert np.array_equal(R[:, 0], X_ai[:, 0])
    assert np.array_equal(R[:, 1], X_ai[:, 3])
    # One-hots equal the AI full-encoding one-hot slices (drop-first levels).
    name_to_col = {name: idx for idx, name in enumerate(prep.encoded_feature_names)}
    expected_one_hot = np.column_stack(
        [
            prep.transform(X_ai)[
                :,
                [
                    name_to_col["sex__eq_1"],
                    name_to_col["cp__eq_2"],
                    name_to_col["cp__eq_3"],
                    name_to_col["cp__eq_4"],
                    name_to_col["restecg__eq_1"],
                    name_to_col["restecg__eq_2"],
                ],
            ]
        ]
    )
    assert np.array_equal(R[:, 2:], expected_one_hot)
    # Column-to-raw mapping covers the five raw fields in projected order.
    assert _d047_rf_column_to_raw_feature(prep) == (0, 3, 1, 2, 2, 2, 4, 4)
    # Optional-missing trestbps imputes the fitted fold median, like the original.
    X_missing = X_ai.copy()
    X_missing[0, 3] = np.nan
    R_missing = _d047_original_rf_matrix(prep, X_missing)
    median = float(np.nanmedian(X_ai[:, 3]))
    assert R_missing[0, 1] == median


def test_d047_rf_space_layout_rejects_unexpected_preprocessor() -> None:
    """Gap A: projection fails closed unless the preprocessor is the D-047 layout."""
    records, labels = _generate_rf_selecting_cohort(n=40)
    X_ai, _, _ = validate_cohort_records(
        records, labels, DA_A2_RESTING_PANEL, require_synthetic=True
    )
    prep = FoldSafeClinicalPreprocessor.fit(X_ai, DA_A2_RESTING_PANEL)
    truncated = dataclasses.replace(prep, field_transforms=prep.field_transforms[:4])
    with pytest.raises(CohortGovernanceError) as exc_info:
        _d047_original_rf_matrix(truncated, X_ai)
    assert exc_info.value.code == "d047_rf_space_layout_mismatch"


def test_d047_background_projection_matches_direct_space() -> None:
    """Gap A: stored-background projection agrees with the direct 8-column space."""
    records, labels = _generate_rf_selecting_cohort()
    X_ai, _, _ = validate_cohort_records(
        records, labels, DA_A2_RESTING_PANEL, require_synthetic=True
    )
    X_ai = X_ai.copy()
    X_ai[0, 3] = np.nan  # optional-missing trestbps exercises median imputation
    prep = FoldSafeClinicalPreprocessor.fit(X_ai, DA_A2_RESTING_PANEL)
    Z = prep.transform(X_ai)
    projected = _d047_project_background_to_rf_space(prep, Z)
    direct = _d047_original_rf_matrix(prep, X_ai)
    assert projected.shape == direct.shape == (len(labels), CLEVELAND_D047_RF_SPACE_WIDTH)
    # One-hot columns transfer exactly; numerics invert the z-score (~1ulp).
    assert np.array_equal(projected[:, 2:], direct[:, 2:])
    assert np.allclose(projected[:, :2], direct[:, :2], rtol=0.0, atol=1e-9)


def test_d047_projected_bundle_round_trip_aligns_inference_and_shap(
    tmp_path: Path,
) -> None:
    """Gap A: an RF-selected D-047 bundle loads, predicts, and explains on 8 columns."""
    import joblib

    from ai.filesystem_security import ensure_private_directory
    from ai.inference import ResearchCadPredictor
    from ai.packaging import package_research_bundle

    tmp_path = ensure_private_directory(tmp_path)
    records, labels = _generate_rf_selecting_cohort()
    _, ai_config = _d047_comparison_configs()
    run = train_research_model(
        records,
        labels,
        DA_A2_RESTING_PANEL,
        model_id="synth_cleveland_d047_rf_fidelity",
        development_cohort_id="synthetic_cleveland",
        development_dataset_id="DA-A2",
        synthetic_data_confirmed=True,
        config=ai_config,
    )
    assert run.selected_model_family == "constrained_random_forest"
    assert run.execution_profile == EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1
    assert int(run.estimator.n_features_in_) == CLEVELAND_D047_RF_SPACE_WIDTH

    bundle_dir = tmp_path / "cleveland_d047_rf_bundle"
    verified = package_research_bundle(run, bundle_dir)
    manifest_model = verified.manifest["model"]
    assert manifest_model["execution_profile"] == EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1
    container = joblib.load(bundle_dir / "model.joblib")
    assert container["execution_profile"] == EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1

    predictor = ResearchCadPredictor.from_verified_bundle(
        bundle_dir, trusted_local_root=tmp_path
    )
    assert predictor.execution_profile == EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1
    result = predictor.predict_research_only(records[0])
    assert 0.0 <= result.calibrated_research_score <= 1.0
    assert result.explanation.sum_check_passed is True
    assert len(result.explanation.attributions) == 5


def test_inference_execution_profile_and_width_guards() -> None:
    """Gap A: profile/width enforcement accepts declared spaces and rejects the rest."""
    from ai.inference import _validate_estimator_fitted_width, _validated_execution_profile

    records, labels = _generate_rf_selecting_cohort(n=40)
    X_ai, _, _ = validate_cohort_records(
        records, labels, DA_A2_RESTING_PANEL, require_synthetic=True
    )
    prep = FoldSafeClinicalPreprocessor.fit(X_ai, DA_A2_RESTING_PANEL)
    forest8 = RandomForestClassifier(n_estimators=2, random_state=1).fit(
        _d047_original_rf_matrix(prep, X_ai), np.array(labels)
    )
    forest10 = RandomForestClassifier(n_estimators=2, random_state=1).fit(
        prep.transform(X_ai), np.array(labels)
    )

    assert (
        _validated_execution_profile(
            {"execution_profile": EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1},
            {"execution_profile": EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1},
        )
        == EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1
    )
    with pytest.raises(BundleIntegrityError) as exc_info:
        _validated_execution_profile(
            {"execution_profile": EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1},
            {"execution_profile": EXECUTION_PROFILE_AI1_GENERIC_V1},
        )
    assert exc_info.value.code == "execution_profile_container_mismatch"
    with pytest.raises(BundleIntegrityError) as exc_info:
        _validated_execution_profile({"execution_profile": "unknown_profile"}, {})
    assert exc_info.value.code == "execution_profile_container_mismatch"

    _validate_estimator_fitted_width(
        forest8,
        "constrained_random_forest",
        prep,
        EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1,
    )
    with pytest.raises(BundleIntegrityError) as exc_info:
        _validate_estimator_fitted_width(
            forest10,
            "constrained_random_forest",
            prep,
            EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1,
        )
    assert exc_info.value.code == "estimator_fitted_width_mismatch"
    _validate_estimator_fitted_width(
        forest10, "constrained_random_forest", prep, EXECUTION_PROFILE_AI1_GENERIC_V1
    )


def test_generic_profile_uses_full_encoding_unchanged() -> None:
    """Gap A: the generic AI-1 profile keeps the full 10-column forest space."""
    records, labels = _generate_rf_selecting_cohort()
    run = train_research_model(
        records,
        labels,
        DA_A2_RESTING_PANEL,
        model_id="synth_generic_full_encoding",
        development_cohort_id="synthetic_generic",
        development_dataset_id="DA-A2",
        synthetic_data_confirmed=True,
        config=FAST_GENERIC_TEST_CONFIG,
    )
    assert run.execution_profile == EXECUTION_PROFILE_AI1_GENERIC_V1
    assert int(run.estimator.n_features_in_) == run.preprocessor.n_encoded_features == 10
    for repeat in run.internal_evaluation["uncalibrated_nested_cv"]["repeats"]:
        for fold_rec in repeat["fold_selections"]:
            assert "estimator_input_space_by_family" not in fold_rec


# --------------------------------------------------------------------------- #
# 14. Wrapper-issued proof tokens: manual construction and replay fail closed
# --------------------------------------------------------------------------- #


def test_manually_constructed_matching_proof_is_rejected(
    d047_isolated_repo: tuple[Path, str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gap B: a hand-built proof with exact bindings still fails the boundary.

    Only wrapper-issued (process-local token) proofs authorize the Cleveland
    path; structural equality of the bound paths is insufficient.
    """
    repo, _, _ = d047_isolated_repo
    source_path = repo / "data" / "raw" / "uci-45" / "processed.cleveland.data"
    source_sha = _create_synthetic_cleveland_file(source_path)
    manifest_path = repo / "data" / "experiments" / "manifest.json"
    _create_valid_auth_manifest(
        manifest_path,
        repo,
        dataset_id="DA-A2",
        panel_id="da_a2_resting_v1",
        source_sha256=source_sha,
        row_count=303,
        model_packaging_authorized=True,
        patient_shap_authorized=True,
    )
    monkeypatch.setattr(
        execution_mod, "cleveland_enforce_local_windows_runtime", lambda **kwargs: None
    )
    touched: list[str] = []
    monkeypatch.setattr(
        execution_mod,
        "parse_and_validate_research_authorization",
        _forbid_call(touched, "parse_and_validate_research_authorization"),
    )
    monkeypatch.setattr(execution_mod, "sha256_file", _forbid_call(touched, "sha256_file"))
    monkeypatch.setattr(
        execution_mod,
        "load_cleveland_source_records",
        _forbid_call(touched, "load_cleveland_source_records"),
    )
    monkeypatch.setattr(
        execution_mod,
        "_execute_shared_training_pipeline",
        _forbid_call(touched, "_execute_shared_training_pipeline"),
    )
    output_dir = repo / "data" / "experiments" / "manual_proof_bundle"
    manual_proof = GuardedClevelandExecutionProof(
        source_path_resolved=str(source_path.resolve()),
        manifest_path_resolved=str(manifest_path.resolve()),
        output_bundle_dir_resolved=str(output_dir.resolve()),
        repo_root_resolved=str(repo.resolve()),
        current_git_commit="",
    )
    with pytest.raises(ExecutionAuthorizationError) as exc_info:
        execute_authorized_research_run(
            source_path=source_path,
            manifest_path=manifest_path,
            panel_id="da_a2_resting_v1",
            output_bundle_dir=output_dir,
            repo_root=repo,
            training_config=None,
            current_git_commit=None,
            guarded_cleveland_proof=manual_proof,
        )
    assert exc_info.value.code == "unguarded_cleveland_execution_blocked"
    assert touched == []
    assert not output_dir.exists()


def test_wrapper_issued_proof_token_is_single_use(
    d047_isolated_repo: tuple[Path, str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gap B: a consumed proof token cannot authorize a second execution."""
    repo, _, _ = d047_isolated_repo
    source_path = repo / "data" / "raw" / "uci-45" / "processed.cleveland.data"
    _create_synthetic_cleveland_file(source_path)
    manifest_path = repo / "data" / "experiments" / "manifest.json"
    _create_valid_auth_manifest(
        manifest_path,
        repo,
        dataset_id="DA-A2",
        panel_id="da_a2_resting_v1",
        source_sha256="f" * 64,  # wrong hash: first call passes the guard, then fails
        row_count=303,
        model_packaging_authorized=True,
        patient_shap_authorized=True,
    )
    monkeypatch.setattr(
        execution_mod, "cleveland_enforce_local_windows_runtime", lambda **kwargs: None
    )
    touched: list[str] = []
    monkeypatch.setattr(
        execution_mod,
        "load_cleveland_source_records",
        _forbid_call(touched, "load_cleveland_source_records"),
    )
    monkeypatch.setattr(
        execution_mod,
        "_execute_shared_training_pipeline",
        _forbid_call(touched, "_execute_shared_training_pipeline"),
    )
    output_dir = repo / "data" / "experiments" / "replay_bundle"
    proof = execution_mod._issue_test_guarded_cleveland_proof(
        source_path=source_path,
        manifest_path=manifest_path,
        output_bundle_dir=output_dir,
        repo_root=repo,
        current_git_commit=None,
    )
    call_kwargs: dict[str, Any] = dict(
        source_path=source_path,
        manifest_path=manifest_path,
        panel_id="da_a2_resting_v1",
        output_bundle_dir=output_dir,
        repo_root=repo,
        training_config=None,
        current_git_commit=None,
        guarded_cleveland_proof=proof,
    )
    with pytest.raises(DatasetAdapterIntegrityError) as exc_info:
        execute_authorized_research_run(**call_kwargs)
    # Past the step-0b boundary (token consumed), failed at source integrity.
    assert exc_info.value.code == "source_hash_mismatch"
    with pytest.raises(ExecutionAuthorizationError) as exc_info:
        execute_authorized_research_run(**call_kwargs)
    assert exc_info.value.code == "guarded_proof_token_reused"
    assert touched == []


def test_expired_proof_token_is_rejected(
    d047_isolated_repo: tuple[Path, str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gap B: TTL-expired tokens fail closed as never-issued."""
    repo, _, _ = d047_isolated_repo
    source_path = repo / "data" / "raw" / "uci-45" / "processed.cleveland.data"
    source_sha = _create_synthetic_cleveland_file(source_path)
    manifest_path = repo / "data" / "experiments" / "manifest.json"
    _create_valid_auth_manifest(
        manifest_path,
        repo,
        dataset_id="DA-A2",
        panel_id="da_a2_resting_v1",
        source_sha256=source_sha,
        row_count=303,
        model_packaging_authorized=True,
        patient_shap_authorized=True,
    )
    monkeypatch.setattr(
        execution_mod, "cleveland_enforce_local_windows_runtime", lambda **kwargs: None
    )
    output_dir = repo / "data" / "experiments" / "expired_bundle"
    proof = execution_mod._issue_test_guarded_cleveland_proof(
        source_path=source_path,
        manifest_path=manifest_path,
        output_bundle_dir=output_dir,
        repo_root=repo,
        current_git_commit=None,
    )
    monkeypatch.setattr(execution_mod, "_GUARDED_PROOF_TOKEN_TTL_SECONDS", -1)
    with pytest.raises(ExecutionAuthorizationError) as exc_info:
        execute_authorized_research_run(
            source_path=source_path,
            manifest_path=manifest_path,
            panel_id="da_a2_resting_v1",
            output_bundle_dir=output_dir,
            repo_root=repo,
            training_config=None,
            current_git_commit=None,
            guarded_cleveland_proof=proof,
        )
    assert exc_info.value.code == "unguarded_cleveland_execution_blocked"


def test_proof_token_redacted_from_repr() -> None:
    """Gap B: proof tokens never appear in reprs, logs, or tracebacks."""
    proof = execution_mod._issue_test_guarded_cleveland_proof(
        source_path=Path("/tmp/synth_source.data"),
        manifest_path=Path("/tmp/synth_manifest.json"),
        output_bundle_dir=Path("/tmp/synth_bundle"),
        repo_root=Path("/tmp"),
        current_git_commit=None,
    )
    assert proof.proof_token
    assert proof.proof_token not in repr(proof)
    assert "proof_token" not in repr(proof)


# --------------------------------------------------------------------------- #
# 15. Post-run acceptance: real bundles load only after recorded success
# --------------------------------------------------------------------------- #


def _wrapper_integration_preflight(
    repo: Path, source_path: Path, source_sha: str, head_commit: str
) -> Any:
    ctx = MagicMock()
    ctx.repo_root = repo
    ctx.source_path = source_path
    ctx.source_sha256 = source_sha
    ctx.current_git_commit = head_commit
    ctx.authorization = {"expected_source_sha256": source_sha}
    return ctx


def _setup_wrapper_integration(
    d047_isolated_repo: tuple[Path, str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Any]:
    """Real inner Cleveland execution behind mocked preflight/activation only.

    Preflight, activation-revision binding, and the Windows runtime guard are
    mocked (each covered by dedicated real-git/real-filesystem suites);
    authorization parsing, the guarded proof, training under the D-047
    profile, real-mode packaging, and the post-run checks all execute for
    real on synthetic fixtures.
    """
    from ai.packaging import get_or_create_local_signing_key

    repo, head_commit, _ = d047_isolated_repo
    source_path = repo / "data" / "raw" / "uci-45" / "processed.cleveland.data"
    source_sha = _create_synthetic_cleveland_file(source_path)
    manifest_path = (
        repo / "data" / "manifests" / "internal_exploratory_authorization.local.json"
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    _create_valid_auth_manifest(
        manifest_path,
        repo,
        dataset_id="DA-A2",
        panel_id="da_a2_resting_v1",
        source_sha256=source_sha,
        row_count=303,
        model_packaging_authorized=True,
        patient_shap_authorized=True,
    )
    preflight = _wrapper_integration_preflight(repo, source_path, source_sha, head_commit)
    monkeypatch.setattr(
        execution_mod, "cleveland_run_preflight", lambda **kwargs: preflight
    )
    monkeypatch.setattr(
        execution_mod, "_enforce_cleveland_activation_revision_binding", lambda **kwargs: None
    )
    monkeypatch.setattr(
        execution_mod, "cleveland_enforce_local_windows_runtime", lambda **kwargs: None
    )
    monkeypatch.setattr(
        execution_mod, "get_approved_training_config", lambda dataset_id: FAST_D047_TEST_CONFIG
    )
    signing_key = get_or_create_local_signing_key(
        repo / "data" / "experiments" / "signer.key"
    )
    return {
        "repo": repo,
        "head_commit": head_commit,
        "source_path": source_path,
        "source_sha": source_sha,
        "manifest_path": manifest_path,
        "preflight": preflight,
        "signing_key": signing_key,
    }


def test_wrapper_integration_success_records_acceptance_and_loads(
    d047_isolated_repo: tuple[Path, str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gap C: the full wrapper path records acceptance; the bundle loads."""
    from ai.inference import ResearchCadPredictor
    from ai.packaging import (
        BUNDLE_ACCEPTANCE_MARKER_FILENAME,
        verify_trusted_local_bundle,
    )

    setup = _setup_wrapper_integration(d047_isolated_repo, monkeypatch)
    source_checks: list[Any] = []

    def _ok_source(ctx: Any) -> None:
        source_checks.append(ctx)

    monkeypatch.setattr(execution_mod, "cleveland_verify_source_still_unchanged", _ok_source)
    bundle_dir = setup["repo"] / "data" / "experiments" / "wrapper_accepted_bundle"
    trained_run, descriptor = execute_guarded_cleveland_d047_run(
        source_path=setup["source_path"],
        manifest_path=setup["manifest_path"],
        panel_id="da_a2_resting_v1",
        output_bundle_dir=bundle_dir,
        repo_root=setup["repo"],
        training_config=None,
        signing_key=setup["signing_key"],
        current_git_commit=setup["head_commit"],
        operator_confirmation=GUARDED_CLEVELAND_D047_OPERATOR_CONFIRMATION,
    )
    assert descriptor.manifest["research_authorization"]["governance_decision_id"] == "D-047"
    assert source_checks == [setup["preflight"]]
    marker_path = bundle_dir / BUNDLE_ACCEPTANCE_MARKER_FILENAME
    assert marker_path.is_file()
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    assert marker["accepted_for_loading"] is True
    assert marker["expected_source_sha256"] == setup["source_sha"].lower()
    assert marker["accepted_by"] == "execute_guarded_cleveland_d047_run"
    # The production loading gate accepts the bundle.
    reverified = verify_trusted_local_bundle(
        bundle_dir,
        trusted_local_root=bundle_dir.parent,
        signing_key=setup["signing_key"],
    )
    assert reverified.manifest["model"]["model_id"] == trained_run.model_id
    predictor = ResearchCadPredictor.from_verified_bundle(
        bundle_dir, trusted_local_root=bundle_dir.parent, signing_key=setup["signing_key"]
    )
    result = predictor.predict_research_only(
        {
            "synthetic": False,
            "panel_id": "da_a2_resting_v1",
            "features": {"age": 60.0, "sex": 1, "cp": 4, "trestbps": 140.0, "restecg": 0},
            "units": {"age": "years", "trestbps": "mmHg"},
            "missing_reasons": {},
        }
    )
    assert 0.0 <= result.calibrated_research_score <= 1.0
    assert result.explanation.sum_check_passed is True


def test_wrapper_integration_source_change_quarantines_without_acceptance(
    d047_isolated_repo: tuple[Path, str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gap C: a failed post-run source check quarantines and records no acceptance."""
    from ai.errors import BundleIntegrityError
    from ai.inference import ResearchCadPredictor
    from ai.packaging import (
        BUNDLE_ACCEPTANCE_MARKER_FILENAME,
        BUNDLE_QUARANTINE_MARKER_FILENAME,
        verify_trusted_local_bundle,
    )

    setup = _setup_wrapper_integration(d047_isolated_repo, monkeypatch)

    def _boom(ctx: Any) -> None:
        raise RuntimeError("simulated post-run source change")

    monkeypatch.setattr(execution_mod, "cleveland_verify_source_still_unchanged", _boom)
    bundle_dir = setup["repo"] / "data" / "experiments" / "wrapper_quarantined_bundle"
    with pytest.raises(ExecutionAuthorizationError) as exc_info:
        execute_guarded_cleveland_d047_run(
            source_path=setup["source_path"],
            manifest_path=setup["manifest_path"],
            panel_id="da_a2_resting_v1",
            output_bundle_dir=bundle_dir,
            repo_root=setup["repo"],
            training_config=None,
            signing_key=setup["signing_key"],
            current_git_commit=setup["head_commit"],
            operator_confirmation=GUARDED_CLEVELAND_D047_OPERATOR_CONFIRMATION,
        )
    assert exc_info.value.code == "guarded_wrapper_source_changed_quarantined"
    assert (bundle_dir / BUNDLE_QUARANTINE_MARKER_FILENAME).is_file()
    assert not (bundle_dir / BUNDLE_ACCEPTANCE_MARKER_FILENAME).exists()
    # Artifacts preserved; loading refused through every trusted path.
    assert (bundle_dir / "manifest.json").is_file()
    assert (bundle_dir / "model.joblib").is_file()
    with pytest.raises(BundleIntegrityError) as exc_verify:
        verify_trusted_local_bundle(
            bundle_dir,
            trusted_local_root=bundle_dir.parent,
            signing_key=setup["signing_key"],
        )
    assert exc_verify.value.code == "bundle_quarantined_not_accepted"
    with pytest.raises(BundleIntegrityError) as exc_load:
        ResearchCadPredictor.from_verified_bundle(
            bundle_dir, trusted_local_root=bundle_dir.parent, signing_key=setup["signing_key"]
        )
    assert exc_load.value.code == "bundle_quarantined_not_accepted"


def test_wrapper_integration_quarantine_write_failure_stays_unloadable(
    d047_isolated_repo: tuple[Path, str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gap C: the review's core scenario -- marker-write failure fails closed.

    Post-run source check fails AND the quarantine marker cannot be written:
    the original failure code is preserved (never masked), the missing audit
    record is surfaced in the message, and the signed bundle stays
    unloadable because no post-run acceptance exists.
    """
    from ai.errors import BundleIntegrityError
    from ai.inference import ResearchCadPredictor
    from ai.packaging import (
        BUNDLE_ACCEPTANCE_MARKER_FILENAME,
        BUNDLE_QUARANTINE_MARKER_FILENAME,
        verify_trusted_local_bundle,
    )

    setup = _setup_wrapper_integration(d047_isolated_repo, monkeypatch)

    def _boom_source(ctx: Any) -> None:
        raise RuntimeError("simulated post-run source change")

    def _boom_marker(*args: Any, **kwargs: Any) -> Path:
        raise OSError("simulated marker-write failure")

    monkeypatch.setattr(execution_mod, "cleveland_verify_source_still_unchanged", _boom_source)
    monkeypatch.setattr(execution_mod, "write_bundle_quarantine_marker", _boom_marker)
    bundle_dir = setup["repo"] / "data" / "experiments" / "wrapper_unmarked_bundle"
    with pytest.raises(ExecutionAuthorizationError) as exc_info:
        execute_guarded_cleveland_d047_run(
            source_path=setup["source_path"],
            manifest_path=setup["manifest_path"],
            panel_id="da_a2_resting_v1",
            output_bundle_dir=bundle_dir,
            repo_root=setup["repo"],
            training_config=None,
            signing_key=setup["signing_key"],
            current_git_commit=setup["head_commit"],
            operator_confirmation=GUARDED_CLEVELAND_D047_OPERATOR_CONFIRMATION,
        )
    assert exc_info.value.code == "guarded_wrapper_source_changed_quarantined"
    assert "quarantine marker write also failed" in exc_info.value.message
    assert not (bundle_dir / BUNDLE_QUARANTINE_MARKER_FILENAME).exists()
    assert not (bundle_dir / BUNDLE_ACCEPTANCE_MARKER_FILENAME).exists()
    # Nothing deleted; the signed bundle refuses loading for missing acceptance.
    assert (bundle_dir / "manifest.json").is_file()
    assert (bundle_dir / "model.joblib").is_file()
    with pytest.raises(BundleIntegrityError) as exc_verify:
        verify_trusted_local_bundle(
            bundle_dir,
            trusted_local_root=bundle_dir.parent,
            signing_key=setup["signing_key"],
        )
    assert exc_verify.value.code == "bundle_post_run_acceptance_missing"
    with pytest.raises(BundleIntegrityError) as exc_load:
        ResearchCadPredictor.from_verified_bundle(
            bundle_dir, trusted_local_root=bundle_dir.parent, signing_key=setup["signing_key"]
        )
    assert exc_load.value.code == "bundle_post_run_acceptance_missing"


def test_wrapper_integration_acceptance_write_failure_fails_closed(
    d047_isolated_repo: tuple[Path, str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gap C: acceptance-write failure on the success path fails closed."""
    from ai.errors import BundleIntegrityError
    from ai.inference import ResearchCadPredictor
    from ai.packaging import (
        BUNDLE_ACCEPTANCE_MARKER_FILENAME,
        verify_trusted_local_bundle,
    )

    setup = _setup_wrapper_integration(d047_isolated_repo, monkeypatch)
    monkeypatch.setattr(
        execution_mod, "cleveland_verify_source_still_unchanged", lambda ctx: None
    )

    def _boom_marker(*args: Any, **kwargs: Any) -> Path:
        raise OSError("simulated acceptance-write failure")

    monkeypatch.setattr(execution_mod, "write_bundle_acceptance_marker", _boom_marker)
    bundle_dir = setup["repo"] / "data" / "experiments" / "wrapper_no_acceptance_bundle"
    with pytest.raises(ExecutionAuthorizationError) as exc_info:
        execute_guarded_cleveland_d047_run(
            source_path=setup["source_path"],
            manifest_path=setup["manifest_path"],
            panel_id="da_a2_resting_v1",
            output_bundle_dir=bundle_dir,
            repo_root=setup["repo"],
            training_config=None,
            signing_key=setup["signing_key"],
            current_git_commit=setup["head_commit"],
            operator_confirmation=GUARDED_CLEVELAND_D047_OPERATOR_CONFIRMATION,
        )
    assert exc_info.value.code == "guarded_wrapper_acceptance_marker_failed"
    assert not (bundle_dir / BUNDLE_ACCEPTANCE_MARKER_FILENAME).exists()
    assert (bundle_dir / "manifest.json").is_file()
    assert (bundle_dir / "model.joblib").is_file()
    with pytest.raises(BundleIntegrityError) as exc_verify:
        verify_trusted_local_bundle(
            bundle_dir,
            trusted_local_root=bundle_dir.parent,
            signing_key=setup["signing_key"],
        )
    assert exc_verify.value.code == "bundle_post_run_acceptance_missing"
    with pytest.raises(BundleIntegrityError) as exc_load:
        ResearchCadPredictor.from_verified_bundle(
            bundle_dir, trusted_local_root=bundle_dir.parent, signing_key=setup["signing_key"]
        )
    assert exc_load.value.code == "bundle_post_run_acceptance_missing"


def _build_helper_accepted_bundle(
    d047_isolated_repo: tuple[Path, str, str],
    monkeypatch: pytest.MonkeyPatch,
    bundle_name: str,
) -> tuple[Path, bytes]:
    """Real-provenance bundle via the isolated simulation (acceptance recorded)."""
    from ai.packaging import get_or_create_local_signing_key

    repo, _, _ = d047_isolated_repo
    source_path = repo / "data" / "raw" / "uci-45" / "processed.cleveland.data"
    source_sha = _create_synthetic_cleveland_file(source_path)
    manifest_path = repo / "data" / "experiments" / "manifest.json"
    _create_valid_auth_manifest(
        manifest_path,
        repo,
        dataset_id="DA-A2",
        panel_id="da_a2_resting_v1",
        source_sha256=source_sha,
        row_count=303,
        model_packaging_authorized=True,
        patient_shap_authorized=True,
    )
    bundle_dir = repo / "data" / "experiments" / bundle_name
    signing_key = get_or_create_local_signing_key(repo / "data" / "experiments" / "signer.key")
    monkeypatch.setattr(
        execution_mod, "get_approved_training_config", lambda dataset_id: FAST_D047_TEST_CONFIG
    )
    _execute_isolated_test_simulation(
        manifest_path=manifest_path,
        source_path=source_path,
        panel_id="da_a2_resting_v1",
        output_bundle_dir=bundle_dir,
        signing_key=signing_key,
        repo_root=repo,
    )
    return bundle_dir, signing_key


def test_real_bundle_without_acceptance_refuses_every_loading_path(
    d047_isolated_repo: tuple[Path, str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gap C: removing post-run acceptance renders a signed bundle unloadable."""
    from ai.errors import BundleIntegrityError
    from ai.inference import ResearchCadPredictor
    from ai.packaging import (
        BUNDLE_ACCEPTANCE_MARKER_FILENAME,
        verify_research_bundle,
        verify_trusted_local_bundle,
    )

    bundle_dir, signing_key = _build_helper_accepted_bundle(
        d047_isolated_repo, monkeypatch, "acceptance_removed_bundle"
    )
    assert (bundle_dir / BUNDLE_ACCEPTANCE_MARKER_FILENAME).is_file()
    (bundle_dir / BUNDLE_ACCEPTANCE_MARKER_FILENAME).unlink()
    for loader in (
        lambda: verify_research_bundle(bundle_dir),
        lambda: verify_trusted_local_bundle(
            bundle_dir, trusted_local_root=bundle_dir.parent, signing_key=signing_key
        ),
        lambda: ResearchCadPredictor.from_verified_bundle(
            bundle_dir, trusted_local_root=bundle_dir.parent, signing_key=signing_key
        ),
    ):
        with pytest.raises(BundleIntegrityError) as exc_info:
            loader()
        assert exc_info.value.code == "bundle_post_run_acceptance_missing"
    # Pre-acceptance verification still passes: the gate is the only refusal.
    pre = verify_trusted_local_bundle(
        bundle_dir,
        trusted_local_root=bundle_dir.parent,
        signing_key=signing_key,
        _require_post_run_acceptance=False,
    )
    assert pre.manifest["research_authorization"]["governance_decision_id"] == "D-047"


def test_acceptance_marker_must_bind_authorized_source_sha(
    d047_isolated_repo: tuple[Path, str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gap C: a marker bound to another source cannot authorize loading."""
    from ai.errors import BundleIntegrityError
    from ai.packaging import (
        BUNDLE_ACCEPTANCE_MARKER_FILENAME,
        verify_research_bundle,
    )

    bundle_dir, _ = _build_helper_accepted_bundle(
        d047_isolated_repo, monkeypatch, "acceptance_rebound_bundle"
    )
    marker_path = bundle_dir / BUNDLE_ACCEPTANCE_MARKER_FILENAME
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    marker["expected_source_sha256"] = "0" * 64
    marker_path.write_text(json.dumps(marker, indent=2), encoding="utf-8")
    with pytest.raises(BundleIntegrityError) as exc_info:
        verify_research_bundle(bundle_dir)
    assert exc_info.value.code == "bundle_post_run_acceptance_mismatch"


def test_synthetic_bundle_loads_without_acceptance(tmp_path: Path) -> None:
    """Gap C: synthetic bundles are unaffected by the acceptance gate."""
    from ai.filesystem_security import ensure_private_directory
    from ai.inference import ResearchCadPredictor
    from ai.packaging import (
        BUNDLE_ACCEPTANCE_MARKER_FILENAME,
        package_research_bundle,
        verify_trusted_local_bundle,
    )

    tmp_path = ensure_private_directory(tmp_path)
    records, labels = _generate_synthetic_resting_cohort(48, seed=4242)
    run = train_research_model(
        records,
        labels,
        DA_A2_RESTING_PANEL,
        model_id="synth_no_acceptance_needed",
        development_cohort_id="synthetic_cleveland",
        development_dataset_id="DA-A2",
        synthetic_data_confirmed=True,
        config=FAST_D047_TEST_CONFIG,
    )
    bundle_dir = tmp_path / "synthetic_bundle"
    verified = package_research_bundle(run, bundle_dir)
    assert verified.manifest["eligibility"]["synthetic_only"] is True
    assert not (bundle_dir / BUNDLE_ACCEPTANCE_MARKER_FILENAME).exists()
    loaded = verify_trusted_local_bundle(bundle_dir, trusted_local_root=tmp_path)
    assert loaded.serving_eligibility == "RESEARCH_ONLY"
    predictor = ResearchCadPredictor.from_verified_bundle(
        bundle_dir, trusted_local_root=tmp_path
    )
    assert predictor.execution_profile == EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1


def test_projected_shap_requires_complete_projection_arguments() -> None:
    """Gap A: partial projected-SHAP requests fail closed (never silently mis-group)."""
    from ai.errors import ExplainabilityIntegrityError
    from ai.explainability import ShapBackgroundReference, explain_clinical_instance

    records, labels = _generate_rf_selecting_cohort(n=60)
    X_ai, y_ai, _ = validate_cohort_records(
        records, labels, DA_A2_RESTING_PANEL, require_synthetic=True
    )
    prep = FoldSafeClinicalPreprocessor.fit(X_ai, DA_A2_RESTING_PANEL)
    Z = prep.transform(X_ai)
    forest8 = RandomForestClassifier(n_estimators=4, max_depth=3, random_state=7).fit(
        _d047_original_rf_matrix(prep, X_ai), y_ai
    )
    background = ShapBackgroundReference.from_training_encoded(
        Z, y_ai, prep, max_samples=16, synthetic_only=True
    )
    base_kwargs: dict[str, Any] = dict(
        model_family="constrained_random_forest",
        estimator=forest8,
        preprocessor=prep,
        panel=DA_A2_RESTING_PANEL,
        background=background,
        z_row=Z[0],
    )
    # No projection at all: required, not optional.
    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        explain_clinical_instance(**base_kwargs)
    assert exc_info.value.code == "shap_projection_required"
    # Partial projection (instance only): still refused, never mis-grouped.
    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        explain_clinical_instance(
            **base_kwargs,
            projected_z_row=_d047_original_rf_matrix(prep, X_ai[[0]])[0],
        )
    assert exc_info.value.code == "shap_projection_required"
    # Complete projection explains with an exact efficiency sum-check.
    explanation = explain_clinical_instance(
        **base_kwargs,
        projected_z_row=_d047_original_rf_matrix(prep, X_ai[[0]])[0],
        projected_background=_d047_project_background_to_rf_space(prep, Z),
        projected_column_to_raw_feature=_d047_rf_column_to_raw_feature(prep),
    )
    assert explanation.sum_check_passed is True
    assert len(explanation.attributions) == 5
