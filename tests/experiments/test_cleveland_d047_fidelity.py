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
from ai.execution import (
    GUARDED_CLEVELAND_D047_OPERATOR_CONFIRMATION,
    DatasetAdapterIntegrityError,
    ExecutionAuthorizationError,
    assert_training_config_approved,
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
from ai.training import (
    EXECUTION_PROFILE_AI1_GENERIC_V1,
    EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1,
    ResearchTrainingConfig,
    _build_estimator,
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


def test_production_operational_registry_remains_empty() -> None:
    assert execution_mod.RATIFIED_OPERATIONAL_SCOPE_AMENDMENTS == {}


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
    preflight = _fake_preflight_context(tmp_path)
    calls: list[str] = []

    def _fake_preflight(*args: Any, **kwargs: Any) -> Any:
        calls.append("preflight")
        assert Path(kwargs["repo_root"]) == tmp_path / "fake_repo"
        return preflight

    def _fake_parse(*args: Any, **kwargs: Any) -> Any:
        calls.append("parse_authorization")
        assert kwargs["expected_dataset_id"] == "DA-A2"
        assert kwargs["expected_panel_id"] == "da_a2_resting_v1"
        return _authorized_mock_context(preflight.source_sha256, packaging=True, shap=True)

    def _fake_execute(*args: Any, **kwargs: Any) -> tuple[Any, Any]:
        calls.append("execute_once")
        assert kwargs["training_config"] is None
        assert kwargs["current_git_commit"] == preflight.current_git_commit
        out = Path(kwargs["output_bundle_dir"])
        out.mkdir(parents=True, exist_ok=False)
        (out / "manifest.json").write_text("{}", encoding="utf-8")
        return MagicMock(), MagicMock()

    def _fake_verify_source(ctx: Any) -> None:
        calls.append("verify_source")
        assert ctx is preflight

    def _fake_verify_bundle(*args: Any, **kwargs: Any) -> Any:
        calls.append("verify_bundle")
        return MagicMock()

    monkeypatch.setattr(execution_mod, "cleveland_run_preflight", _fake_preflight)
    monkeypatch.setattr(
        execution_mod, "parse_and_validate_research_authorization", _fake_parse
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
        "execute_once",
        "verify_source",
        "verify_bundle",
    ]


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
        return MagicMock(), MagicMock()

    monkeypatch.setattr(execution_mod, "execute_authorized_research_run", _fake_execute)
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
