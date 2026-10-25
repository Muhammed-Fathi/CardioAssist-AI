"""Automated unit, mathematical SHAP oracle, reproducibility, governance,
tamper-rejection, and end-to-end integration tests for the ``ai/`` Track A
RESEARCH_ONLY CAD tabular pipeline.

Synthetic fixtures only: every cohort and record is deterministically generated
in memory. No real patient record, dataset file, or committed binary artifact is
created. All packaged bundles are written exclusively inside pytest ``tmp_path``.
"""
from __future__ import annotations

import ast
from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression

from ai import (
    DA_A1_BASIC_CLINICAL_PANEL,
    DA_A1_CLINICAL_CORE_LABS_PANEL,
    DA_A2_RESTING_LABS_PANEL,
    DA_A2_RESTING_PANEL,
    BundleIntegrityError,
    CalibrationIntegrityError,
    ClinicalInputValidationError,
    CohortGovernanceError,
    ExplainabilityIntegrityError,
    ExternalEvaluationLedger,
    FoldEnsembleMember,
    FoldSafeClinicalPreprocessor,
    OofLogisticCalibrator,
    PreprocessingContractError,
    ResearchCadPredictor,
    ResearchTrainingConfig,
    ShapBackgroundReference,
    TrainedResearchRun,
    ensure_private_directory,
    evaluate_locked_external_cohort,
    exact_coalition_shapley_oracle,
    explain_clinical_instance,
    get_or_create_local_signing_key,
    package_research_bundle,
    protect_private_file,
    train_research_model,
    validate_clinical_record,
    verify_access_control,
    verify_research_bundle,
    verify_trusted_local_bundle,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def tmp_path(tmp_path: Path) -> Path:
    """Ensure pytest temporary root has platform-verified private isolation (POSIX 0700 / NTFS D:PAI)."""
    return ensure_private_directory(tmp_path)

FAST_TEST_CONFIG = ResearchTrainingConfig(
    protocol_id="CAI-AI1-SYNTHETIC-TEST-V1",
    model_version="0.1.0",
    outer_folds=3,
    inner_folds=2,
    repeat_seeds=(20261025,),
    shuffle_control_seeds=(20261101,),
    shuffle_max_allowed_auroc=0.68,
    lr_c_grid=(0.1, 1.0, 5.0),
    rf_max_depths=(2, 4),
    rf_min_samples_leaf=(4,),
    rf_n_estimators=25,
    bootstrap_resamples=80,
    shap_max_background_samples=28,
)


# --------------------------------------------------------------------------- #
# Deterministic synthetic cohort generators
# --------------------------------------------------------------------------- #


def _make_uci45_resting_labs_record(
    *,
    age: float = 54.0,
    sex: int = 1,
    cp: int = 4,
    trestbps: float | None = 138.0,
    restecg: int | None = 1,
    chol: float | None = 235.0,
    fbs: int | None = 0,
    omit_chol: bool = False,
) -> dict[str, Any]:
    features: dict[str, Any] = {
        "age": age,
        "sex": sex,
        "cp": cp,
        "trestbps": trestbps,
        "restecg": restecg,
        "fbs": fbs,
    }
    units: dict[str, str] = {"age": "years"}
    reasons: dict[str, str] = {}

    if trestbps is not None:
        units["trestbps"] = "mmHg"
    else:
        reasons["trestbps"] = "not_measured"

    if restecg is None:
        reasons["restecg"] = "not_available_at_time"

    if omit_chol:
        reasons["chol"] = "not_provided"
    elif chol is None:
        features["chol"] = None
        reasons["chol"] = "not_measured"
    else:
        features["chol"] = chol
        units["chol"] = "mg/dL"

    if fbs is None:
        reasons["fbs"] = "unknown"

    return {
        "synthetic": True,
        "panel_id": DA_A2_RESTING_LABS_PANEL.panel_id,
        "features": features,
        "units": units,
        "missing_reasons": reasons,
    }


def _generate_synthetic_uci45_cohort(
    n: int,
    *,
    seed: int,
    nonlinear: bool = False,
    missing_lab_rate: float = 0.0,
    logit_intercept_shift: float = 0.0,
) -> tuple[list[dict[str, Any]], list[int]]:
    rng = np.random.default_rng(seed)
    records: list[dict[str, Any]] = []
    labels: list[int] = []
    for _ in range(n):
        age = float(rng.integers(35, 76))
        sex = int(rng.integers(0, 2))
        cp = int(rng.choice([1, 2, 3, 4]))
        trestbps_val = float(rng.integers(105, 175))
        restecg = int(rng.choice([0, 1, 2]))
        chol_val = float(rng.integers(155, 330))
        fbs = int(rng.choice([0, 1], p=[0.8, 0.2]))

        if nonlinear:
            # Symmetric U-shaped / central-band interaction: zero monotone linear
            # correlation with every feature (LR AUROC ~0.50), strong root+child Gini
            # gain for shallow decision trees (RF AUROC >0.85).
            band_signal = (abs(age - 55.0) > 10.0) or (abs(chol_val - 242.0) > 48.0)
            eta = (3.2 if band_signal else -3.2) + logit_intercept_shift
        else:
            eta = (
                0.08 * (age - 55.0)
                + 1.1 * sex
                + (1.4 if cp == 4 else -0.6)
                + 0.025 * (trestbps_val - 135.0)
                + 0.012 * (chol_val - 230.0)
                + 0.6 * fbs
                + logit_intercept_shift
            )
        prob = 1.0 / (1.0 + np.exp(-eta))
        y = int(rng.random() < prob)

        drop_chol = bool(rng.random() < missing_lab_rate)
        records.append(
            _make_uci45_resting_labs_record(
                age=age,
                sex=sex,
                cp=cp,
                trestbps=trestbps_val,
                restecg=restecg,
                chol=None if drop_chol else chol_val,
                fbs=fbs,
            )
        )
        labels.append(y)
    return records, labels


def _generate_synthetic_uci412_core_labs_cohort(
    n: int, *, seed: int
) -> tuple[list[dict[str, Any]], list[int]]:
    rng = np.random.default_rng(seed)
    records: list[dict[str, Any]] = []
    labels: list[int] = []
    for idx in range(n):
        age = float(rng.integers(38, 78))
        sex_tok = "Male" if int(rng.integers(0, 2)) == 1 else "Female"
        bmi = float(np.round(rng.uniform(19.0, 36.0), 1))
        dm = int(rng.integers(0, 2))
        htn = int(rng.integers(0, 2))
        smoker = int(rng.integers(0, 2))
        ex_smoker = int(0 if smoker == 1 else rng.integers(0, 2))
        fh = int(rng.integers(0, 2))
        dlp = "Y" if int(rng.integers(0, 2)) == 1 else "N"
        bp = float(rng.integers(100, 175))
        pr = float(rng.integers(58, 105))
        tcp = int(rng.integers(0, 2))
        atyp = "Y" if (tcp == 0 and rng.random() < 0.35) else "N"
        nonang = "N"
        exert = "Y" if tcp == 1 else "N"
        dyspnea = "Y" if rng.random() < 0.3 else "N"

        fbs = float(rng.integers(75, 220))
        cr = float(np.round(rng.uniform(0.6, 1.9), 2))
        tg = float(rng.integers(70, 320))
        ldl = float(rng.integers(65, 210))
        hdl = float(rng.integers(30, 75))
        hb = float(np.round(rng.uniform(11.0, 16.8), 1))
        wbc = float(rng.integers(4200, 11500))

        eta = (
            0.06 * (age - 56.0)
            + 1.3 * tcp
            + 0.8 * dm
            + 0.7 * htn
            + 0.015 * (ldl - 125.0)
            - 0.02 * (hdl - 45.0)
            + 0.5 * (cr - 1.0)
        )
        y = int(rng.random() < (1.0 / (1.0 + np.exp(-eta))))

        features: dict[str, Any] = {
            "Age": age,
            "Sex": sex_tok,
            "BMI": bmi,
            "DM": dm,
            "HTN": htn,
            "Current Smoker": smoker,
            "EX-Smoker": ex_smoker,
            "FH": fh,
            "DLP": dlp,
            "BP": bp,
            "PR": pr,
            "Typical Chest Pain": tcp,
            "Atypical": atyp,
            "Nonanginal": nonang,
            "Exertional CP": exert,
            "Dyspnea": dyspnea,
            "FBS": fbs,
            "CR": cr,
            "TG": tg,
            "LDL": ldl,
            "HDL": hdl,
            "HB": hb,
        }
        units: dict[str, str] = {
            "Age": "years",
            "BMI": "kg/m^2",
            "BP": "mmHg",
            "PR": "beats/min",
            "FBS": "mg/dL",
            "CR": "mg/dL",
            "TG": "mg/dL",
            "LDL": "mg/dL",
            "HDL": "mg/dL",
            "HB": "g/dL",
        }
        reasons: dict[str, str] = {}
        if idx % 5 == 0:
            # Omit optional WBC on every 5th synthetic patient to exercise lab partial completeness
            reasons["WBC"] = "not_provided"
        else:
            features["WBC"] = wbc
            units["WBC"] = "cells/uL"

        records.append(
            {
                "synthetic": True,
                "panel_id": DA_A1_CLINICAL_CORE_LABS_PANEL.panel_id,
                "features": features,
                "units": units,
                "missing_reasons": reasons,
            }
        )
        labels.append(y)
    return records, labels


# --------------------------------------------------------------------------- #
# 1. Validated clinical & laboratory input contracts
# --------------------------------------------------------------------------- #


def test_panel_contracts_reuse_authoritative_uci45_and_uci412_definitions() -> None:
    assert DA_A2_RESTING_PANEL.feature_names == (
        "age",
        "sex",
        "cp",
        "trestbps",
        "restecg",
    )
    assert DA_A2_RESTING_LABS_PANEL.feature_names == (
        "age",
        "sex",
        "cp",
        "trestbps",
        "restecg",
        "chol",
        "fbs",
    )
    assert len(DA_A1_BASIC_CLINICAL_PANEL.fields) == 16
    assert len(DA_A1_CLINICAL_CORE_LABS_PANEL.fields) == 23
    assert DA_A1_CLINICAL_CORE_LABS_PANEL.governance_status == (
        "PROPOSED_SYNTHETIC_ONLY_GATE_PT_REQUIRED"
    )
    assert not DA_A1_CLINICAL_CORE_LABS_PANEL.real_data_execution_authorized


def test_zero_categorical_preserved_while_zero_blood_pressure_and_cholesterol_fail() -> None:
    rec = _make_uci45_resting_labs_record(sex=0, restecg=0, fbs=0, chol=None)
    validated = validate_clinical_record(rec, DA_A2_RESTING_LABS_PANEL)
    assert validated.values[1] == 0.0  # sex=0 preserved
    assert validated.values[4] == 0.0  # restecg=0 preserved
    assert validated.values[6] == 0.0  # fbs=0 preserved
    assert np.isnan(validated.values[5])  # chol=None -> NaN
    assert not validated.stage_complete
    assert validated.missing_fields_with_reason == (("chol", "not_measured"),)

    for zero_field in ("trestbps", "chol"):
        bad = _make_uci45_resting_labs_record()
        bad["features"][zero_field] = 0.0
        with pytest.raises(ClinicalInputValidationError) as exc_info:
            validate_clinical_record(bad, DA_A2_RESTING_LABS_PANEL)
        assert exc_info.value.code == "zero_measurement_unavailable"


@pytest.mark.parametrize(
    "bad_field",
    [
        "ca",
        "num",
        "Cath",
        "LAD",
        "LCX",
        "RCA",
        "EF-TTE",
        "Region RWMA",
        "VHD",
        "heart_rate_bpm",
        "spo2",
        "wearable_ecg",
    ],
)
def test_leakage_echo_and_wearable_fields_fail_closed(bad_field: str) -> None:
    rec = _make_uci45_resting_labs_record()
    rec["features"][bad_field] = 1
    with pytest.raises(ClinicalInputValidationError) as exc_info:
        validate_clinical_record(rec, DA_A2_RESTING_LABS_PANEL)
    assert exc_info.value.code == "prohibited_leakage_or_wearable_field"


def test_track_b_context_non_synthetic_boolean_and_unit_errors_fail_closed() -> None:
    wearable_ctx = _make_uci45_resting_labs_record()
    wearable_ctx["context"] = {"track": "A", "source": "simulated_wearable"}
    with pytest.raises(ClinicalInputValidationError) as exc_info:
        validate_clinical_record(wearable_ctx, DA_A2_RESTING_LABS_PANEL)
    assert exc_info.value.code == "wearable_or_track_b_rejected"

    non_synth = _make_uci45_resting_labs_record()
    non_synth["synthetic"] = False
    with pytest.raises(ClinicalInputValidationError) as exc_info:
        validate_clinical_record(non_synth, DA_A2_RESTING_LABS_PANEL)
    assert exc_info.value.code == "non_synthetic_input_rejected"

    bool_cat = _make_uci45_resting_labs_record()
    bool_cat["features"]["sex"] = True
    with pytest.raises(ClinicalInputValidationError) as exc_info:
        validate_clinical_record(bool_cat, DA_A2_RESTING_LABS_PANEL)
    assert exc_info.value.code == "invalid_categorical_type"

    wrong_unit = _make_uci45_resting_labs_record()
    wrong_unit["units"]["chol"] = "mmol/L"
    with pytest.raises(ClinicalInputValidationError) as exc_info:
        validate_clinical_record(wrong_unit, DA_A2_RESTING_LABS_PANEL)
    assert exc_info.value.code == "unit_mismatch"
    assert "235" not in str(exc_info.value)


# --------------------------------------------------------------------------- #
# 2. Fold-contained preprocessing & deterministic JSON lineage
# --------------------------------------------------------------------------- #


def test_preprocessor_is_strictly_fold_contained_and_preserves_missing_columns() -> None:
    # Complete training fold (0% missing chol, just like Cleveland processed)
    X_train = np.array(
        [
            [45.0, 0.0, 1.0, 120.0, 0.0, 200.0, 0.0],
            [55.0, 1.0, 2.0, 130.0, 1.0, 220.0, 0.0],
            [65.0, 1.0, 4.0, 140.0, 2.0, 240.0, 1.0],
            [50.0, 0.0, 3.0, 125.0, 0.0, 210.0, 0.0],
        ],
        dtype=np.float64,
    )
    prep_clean = FoldSafeClinicalPreprocessor.fit(X_train, DA_A2_RESTING_LABS_PANEL)

    # Holdout contains missing chol/trestbps AND extreme values: training stats never see it
    X_holdout = np.array(
        [
            [60.0, 1.0, 4.0, np.nan, 0.0, np.nan, 1.0],
            [70.0, 0.0, 1.0, 9999.0, 2.0, 9999.0, 0.0],
        ],
        dtype=np.float64,
    )
    Z_holdout = prep_clean.transform(X_holdout)
    assert np.isfinite(Z_holdout).all()
    assert "chol__missing" in prep_clean.encoded_feature_names
    chol_miss_idx = prep_clean.encoded_feature_names.index("chol__missing")
    assert Z_holdout[0, chol_miss_idx] == 1.0
    assert Z_holdout[1, chol_miss_idx] == 0.0

    # JSON round-trip preserves exact SHA-256 and output matrix
    reloaded = FoldSafeClinicalPreprocessor.from_json_dict(
        json.loads(prep_clean.to_canonical_json_bytes().decode("utf-8")),
        expected_panel=DA_A2_RESTING_LABS_PANEL,
    )
    assert reloaded.state_sha256 == prep_clean.state_sha256
    assert np.array_equal(reloaded.transform(X_holdout), Z_holdout)

    # Tampered slice order fails closed
    tampered = prep_clean.to_json_dict()
    tampered["field_transforms"][0]["slice_indices"] = [0, 1]
    with pytest.raises(PreprocessingContractError):
        FoldSafeClinicalPreprocessor.from_json_dict(
            tampered, expected_panel=DA_A2_RESTING_LABS_PANEL
        )


# --------------------------------------------------------------------------- #
# 3. Mathematical verification of genuine LinearSHAP & TreeSHAP against 2^M oracle
# --------------------------------------------------------------------------- #


def test_grouped_linear_shap_matches_exact_2_to_m_coalition_oracle_to_machine_precision() -> None:
    records, labels = _generate_synthetic_uci45_cohort(
        60, seed=101, nonlinear=False, missing_lab_rate=0.25
    )
    X = np.vstack(
        [
            validate_clinical_record(r, DA_A2_RESTING_LABS_PANEL).as_row_array()
            for r in records
        ]
    )
    y = np.asarray(labels, dtype=np.int64)
    prep = FoldSafeClinicalPreprocessor.fit(X, DA_A2_RESTING_LABS_PANEL)
    Z = prep.transform(X)

    lr = LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000, random_state=7)
    lr.fit(Z, y)

    X_bg_raw = X[:12]
    Z_bg = prep.transform(X_bg_raw)
    bg_ref = ShapBackgroundReference(
        panel_id=prep.panel_id,
        panel_contract_sha256=prep.panel_contract_sha256,
        encoded_feature_names=prep.encoded_feature_names,
        background_matrix=Z_bg,
    )

    # Test both a complete row and a row with missing optional measurements
    for row_idx in (0, 3, 7):
        x_raw = X[row_idx]
        z_row = prep.transform(x_raw)[0]
        expl = explain_clinical_instance(
            model_family="l2_logistic_regression",
            estimator=lr,
            preprocessor=prep,
            panel=DA_A2_RESTING_LABS_PANEL,
            background=bg_ref,
            z_row=z_row,
        )
        oracle_base, oracle_target, oracle_phi = exact_coalition_shapley_oracle(
            lambda Z_in: lr.decision_function(Z_in),
            prep,
            x_raw,
            X_bg_raw,
        )
        computed_phi = np.array([a.shap_value for a in expl.attributions])

        assert expl.method == "linear_shap_interventional"
        assert expl.explained_quantity == "raw_model_log_odds"
        assert expl.scale == "raw_log_odds"
        assert expl.explains_calibrated_score_directly is False
        assert expl.additive_on_calibrated_probability is False
        assert expl.synthetic_placeholder is False
        assert expl.sum_check_passed is True
        assert abs(expl.base_value - oracle_base) < 1e-12
        assert abs(expl.target_prediction_on_scale - oracle_target) < 1e-12
        assert np.max(np.abs(computed_phi - oracle_phi)) < 1e-12


def test_grouped_interventional_tree_shap_matches_exact_2_to_m_coalition_oracle() -> None:
    records, labels = _generate_synthetic_uci45_cohort(
        80, seed=202, nonlinear=True, missing_lab_rate=0.25
    )
    X = np.vstack(
        [
            validate_clinical_record(r, DA_A2_RESTING_LABS_PANEL).as_row_array()
            for r in records
        ]
    )
    y = np.asarray(labels, dtype=np.int64)
    prep = FoldSafeClinicalPreprocessor.fit(X, DA_A2_RESTING_LABS_PANEL)
    Z = prep.transform(X)

    rf = RandomForestClassifier(
        n_estimators=25, max_depth=4, min_samples_leaf=3, random_state=19, n_jobs=1
    )
    rf.fit(Z, y)

    X_bg_raw = X[:14]
    Z_bg = prep.transform(X_bg_raw)
    bg_ref = ShapBackgroundReference(
        panel_id=prep.panel_id,
        panel_contract_sha256=prep.panel_contract_sha256,
        encoded_feature_names=prep.encoded_feature_names,
        background_matrix=Z_bg,
    )

    for row_idx in (0, 2, 5, 15):
        x_raw = X[row_idx]
        z_row = prep.transform(x_raw)[0]
        expl = explain_clinical_instance(
            model_family="constrained_random_forest",
            estimator=rf,
            preprocessor=prep,
            panel=DA_A2_RESTING_LABS_PANEL,
            background=bg_ref,
            z_row=z_row,
        )
        oracle_base, oracle_target, oracle_phi = exact_coalition_shapley_oracle(
            lambda Z_in: rf.predict_proba(Z_in)[:, 1],
            prep,
            x_raw,
            X_bg_raw,
        )
        computed_phi = np.array([a.shap_value for a in expl.attributions])

        assert expl.method == "tree_shap_interventional"
        assert expl.scale == "raw_model_probability"
        assert expl.synthetic_placeholder is False
        assert expl.sum_check_passed is True
        assert abs(expl.base_value - oracle_base) < 1e-12
        assert abs(expl.target_prediction_on_scale - oracle_target) < 1e-12
        assert np.max(np.abs(computed_phi - oracle_phi)) < 1e-12


def test_shap_null_player_and_estimator_family_mismatch_guards() -> None:
    records, labels = _generate_synthetic_uci45_cohort(40, seed=303)
    X = np.vstack(
        [
            validate_clinical_record(r, DA_A2_RESTING_LABS_PANEL).as_row_array()
            for r in records
        ]
    )
    y = np.asarray(labels, dtype=np.int64)
    prep = FoldSafeClinicalPreprocessor.fit(X, DA_A2_RESTING_LABS_PANEL)
    Z = prep.transform(X)
    bg_ref = ShapBackgroundReference.from_training_encoded(Z, y, prep, max_samples=10)

    # Zero out every encoded column belonging to 'chol' in LR -> chol SHAP must be identically 0.0
    lr = LogisticRegression(C=1.0, random_state=1).fit(Z, y)
    chol_slice = list(prep.feature_slices["chol"])
    lr.coef_[0, chol_slice] = 0.0
    expl = explain_clinical_instance(
        model_family="l2_logistic_regression",
        estimator=lr,
        preprocessor=prep,
        panel=DA_A2_RESTING_LABS_PANEL,
        background=bg_ref,
        z_row=Z[0],
    )
    assert expl.attribution_map()["chol"] == 0.0

    # Dummy baseline returns exact 0 attributions
    dummy = DummyClassifier(strategy="prior").fit(Z, y)
    dummy_expl = explain_clinical_instance(
        model_family="prevalence_dummy",
        estimator=dummy,
        preprocessor=prep,
        panel=DA_A2_RESTING_LABS_PANEL,
        background=bg_ref,
        z_row=Z[0],
    )
    assert all(val == 0.0 for val in dummy_expl.attribution_map().values())

    # Claiming tree_shap on a LogisticRegression fails closed
    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        explain_clinical_instance(
            model_family="constrained_random_forest",
            estimator=lr,
            preprocessor=prep,
            panel=DA_A2_RESTING_LABS_PANEL,
            background=bg_ref,
            z_row=Z[0],
        )
    assert exc_info.value.code == "estimator_family_mismatch"


# --------------------------------------------------------------------------- #
# 4. Out-of-fold calibration & monotonicity
# --------------------------------------------------------------------------- #


def test_oof_calibrator_is_monotone_and_round_trips_via_json() -> None:
    rng = np.random.default_rng(404)
    raw = rng.uniform(0.05, 0.95, size=80)
    y = (rng.random(80) < raw).astype(np.int64)
    cal = OofLogisticCalibrator.fit_from_oof(
        y, raw, model_family="l2_logistic_regression"
    )
    grid = np.linspace(0.01, 0.99, 50)
    mapped = cal.calibrate(grid)
    assert np.all(np.diff(mapped) > 0.0)  # strictly monotone rank-preserving

    reloaded = OofLogisticCalibrator.from_json_dict(
        json.loads(cal.to_canonical_json_bytes().decode("utf-8"))
    )
    assert reloaded.state_sha256 == cal.state_sha256
    assert np.allclose(reloaded.calibrate(grid), mapped)

    bad = cal.to_json_dict()
    bad["slope"] = -0.5
    with pytest.raises(CalibrationIntegrityError):
        OofLogisticCalibrator.from_json_dict(bad)


# --------------------------------------------------------------------------- #
# 5. Reproducibility, model selection, negative control & cohort governance
# --------------------------------------------------------------------------- #


def test_training_is_bitwise_reproducible_and_preserves_global_numpy_rng() -> None:
    records, labels = _generate_synthetic_uci45_cohort(96, seed=505, nonlinear=False)

    np.random.seed(7777)
    expected_global = np.random.random(4)

    np.random.seed(7777)
    run_a = train_research_model(
        records,
        labels,
        DA_A2_RESTING_LABS_PANEL,
        model_id="synth_cleveland_resting_labs_v0",
        development_cohort_id="synthetic_cleveland",
        development_dataset_id="DA-A2",
        synthetic_data_confirmed=True,
        config=FAST_TEST_CONFIG,
    )
    assert np.array_equal(np.random.random(4), expected_global)

    run_b = train_research_model(
        records,
        labels,
        DA_A2_RESTING_LABS_PANEL,
        model_id="synth_cleveland_resting_labs_v0",
        development_cohort_id="synthetic_cleveland",
        development_dataset_id="DA-A2",
        synthetic_data_confirmed=True,
        config=FAST_TEST_CONFIG,
    )
    assert run_a.selected_model_family == run_b.selected_model_family == "l2_logistic_regression"
    assert run_a.preprocessor.state_sha256 == run_b.preprocessor.state_sha256
    assert run_a.calibrator.state_sha256 == run_b.calibrator.state_sha256
    assert (
        run_a.internal_evaluation["inner_selected_roc_auc_mean_across_repeats"]
        == run_b.internal_evaluation["inner_selected_roc_auc_mean_across_repeats"]
    )


def test_nonlinear_cohort_selects_random_forest_and_tree_shap(tmp_path: Path) -> None:
    records, labels = _generate_synthetic_uci45_cohort(120, seed=606, nonlinear=True)
    run = train_research_model(
        records,
        labels,
        DA_A2_RESTING_LABS_PANEL,
        model_id="synth_nonlinear_rf_v0",
        development_cohort_id="synthetic_nonlinear_dev",
        development_dataset_id="DA-A2",
        synthetic_data_confirmed=True,
        config=FAST_TEST_CONFIG,
    )
    assert run.selected_model_family == "constrained_random_forest"

    bundle_dir = tmp_path / "rf_bundle"
    package_research_bundle(run, bundle_dir)
    predictor = ResearchCadPredictor.from_verified_bundle(
        bundle_dir, trusted_local_root=tmp_path
    )
    result = predictor.predict_research_only(records[0])
    assert result.model_family == "constrained_random_forest"
    assert result.explanation.method == "tree_shap_interventional"
    assert result.explanation.explained_quantity == "raw_model_score"
    assert result.explanation.scale == "raw_model_probability"
    assert result.explanation.explains_calibrated_score_directly is False
    assert result.explanation.additive_on_calibrated_probability is False
    assert result.explanation.sum_check_passed is True


def test_cohort_governance_blocks_real_data_pooling_and_overlapping_external_sets() -> None:
    dev_records, dev_labels = _generate_synthetic_uci45_cohort(80, seed=707)

    # Gate PT closed: real-data training flag rejected
    with pytest.raises(CohortGovernanceError) as exc_info:
        train_research_model(
            dev_records,
            dev_labels,
            DA_A2_RESTING_LABS_PANEL,
            model_id="blocked_real_run",
            development_cohort_id="cleveland",
            synthetic_data_confirmed=False,
            config=FAST_TEST_CONFIG,
        )
    assert exc_info.value.code == "gate_pt_closed_real_training_blocked"

    # Pooling rejected
    with pytest.raises(CohortGovernanceError) as exc_info:
        train_research_model(
            dev_records,
            dev_labels,
            DA_A2_RESTING_LABS_PANEL,
            model_id="blocked_pooled",
            development_cohort_id="cleveland+hungary",
            synthetic_data_confirmed=True,
            config=FAST_TEST_CONFIG,
        )
    assert exc_info.value.code == "cohort_pooling_prohibited"

    trained = train_research_model(
        dev_records,
        dev_labels,
        DA_A2_RESTING_LABS_PANEL,
        model_id="synth_dev_guard",
        development_cohort_id="da-a1",
        development_dataset_id="UCI-412",
        synthetic_data_confirmed=True,
        config=FAST_TEST_CONFIG,
    )

    # Same cohort rejected
    with pytest.raises(CohortGovernanceError) as exc_info:
        evaluate_locked_external_cohort(
            trained,
            dev_records,
            dev_labels,
            external_cohort_id="da-a1",
            external_dataset_id="UCI-412",
            synthetic_data_confirmed=True,
        )
    assert exc_info.value.code == "external_cohort_identical_to_development"

    # UCI-412 vs UCI-411 (same 303 patients) rejected
    with pytest.raises(CohortGovernanceError) as exc_info:
        evaluate_locked_external_cohort(
            trained,
            dev_records,
            dev_labels,
            external_cohort_id="da-b1",
            external_dataset_id="UCI-411",
            synthetic_data_confirmed=True,
        )
    assert exc_info.value.code in {"prohibited_external_cohort", "overlapping_cohort_prohibited"}

    # Suspect Statlog and non-T1 BRFSS rejected
    for bad_ext in ("statlog", "brfss_2015", "kaggle_framingham"):
        with pytest.raises(CohortGovernanceError):
            evaluate_locked_external_cohort(
                trained,
                dev_records,
                dev_labels,
                external_cohort_id=bad_ext,
                external_dataset_id=bad_ext,
                synthetic_data_confirmed=True,
            )


def test_locked_external_cohort_evaluation_never_mutates_model_and_reports_shift() -> None:
    dev_records, dev_labels = _generate_synthetic_uci45_cohort(
        96, seed=808, missing_lab_rate=0.0, logit_intercept_shift=0.4
    )
    ext_records, ext_labels = _generate_synthetic_uci45_cohort(
        80, seed=909, missing_lab_rate=0.30, logit_intercept_shift=-0.9
    )

    run = train_research_model(
        dev_records,
        dev_labels,
        DA_A2_RESTING_LABS_PANEL,
        model_id="synth_cleveland_to_hungary_v0",
        development_cohort_id="synthetic_cleveland",
        development_dataset_id="DA-A2:cleveland",
        synthetic_data_confirmed=True,
        config=FAST_TEST_CONFIG,
    )
    before_prep_sha = run.preprocessor.state_sha256
    before_cal_sha = run.calibrator.state_sha256

    ext_eval = evaluate_locked_external_cohort(
        run,
        ext_records,
        ext_labels,
        external_cohort_id="synthetic_hungary",
        external_dataset_id="DA-A2:hungary",
        synthetic_data_confirmed=True,
        n_bootstrap=100,
    )

    assert run.preprocessor.state_sha256 == before_prep_sha
    assert run.calibrator.state_sha256 == before_cal_sha
    assert ext_eval["pooled_with_development"] is False
    assert ext_eval["used_for_feature_or_model_or_threshold_selection"] is False
    assert ext_eval["external_stage_complete_records"] < ext_eval["external_total_records"]
    assert ext_eval["locked_transport_metrics"]["discrimination"]["roc_auc"] > 0.65
    assert (
        ext_eval["prevalence_shift_diagnostic"]["external_recalibration_applied_to_primary_metrics"]
        is False
    )


# --------------------------------------------------------------------------- #
# 6. Packaging, tamper rejection & end-to-end RESEARCH_ONLY inference
# --------------------------------------------------------------------------- #


def test_end_to_end_uci412_clinical_plus_core_labs_bundle_and_research_inference(
    tmp_path: Path,
) -> None:
    records, labels = _generate_synthetic_uci412_core_labs_cohort(96, seed=1010)
    run = train_research_model(
        records,
        labels,
        DA_A1_CLINICAL_CORE_LABS_PANEL,
        model_id="synth_uci412_clinical_labs_v0",
        development_cohort_id="synthetic_uci412_tehran",
        development_dataset_id="DA-A1",
        synthetic_data_confirmed=True,
        config=FAST_TEST_CONFIG,
    )

    bundle_dir = tmp_path / "uci412_labs_bundle"
    verified = package_research_bundle(run, bundle_dir)
    assert verified.serving_eligibility == "RESEARCH_ONLY"
    assert verified.approved_for_serving is False

    predictor = ResearchCadPredictor.from_verified_bundle(
        bundle_dir, trusted_local_root=tmp_path
    )
    # Record 0 has omitted optional WBC ("not_provided")
    res = predictor.predict_research_only(records[0])
    out = res.to_dict()

    assert res.serving_eligibility == "RESEARCH_ONLY"
    assert res.approved_for_serving is False
    assert res.clinical_use_authorized is False
    assert res.clinically_reliable_individual_cad_risk is False
    assert out["prediction"]["score_interpretation"] == (
        "RESEARCH_ONLY_NOT_INDIVIDUAL_CLINICAL_RISK"
    )
    assert 0.0 < res.calibrated_research_score < 1.0
    assert res.explanation.sum_check_passed is True
    assert len(res.explanation.attributions) == 23
    wbc_attr = next(a for a in res.explanation.attributions if a.feature_name == "WBC")
    assert wbc_attr.status == "missing_imputed"
    assert any("WBC (not_provided)" in lim for lim in res.limitations)
    assert any("Gate PT" in lim for lim in res.limitations)

    # Determinism across repeated calls
    res_repeat = predictor.predict_research_only(records[0])
    assert res.to_dict() == res_repeat.to_dict()


def test_bundle_tamper_symlink_overwrite_and_tracked_path_defenses(
    tmp_path: Path,
) -> None:
    records, labels = _generate_synthetic_uci45_cohort(80, seed=1111)
    run = train_research_model(
        records,
        labels,
        DA_A2_RESTING_LABS_PANEL,
        model_id="synth_tamper_guard_v0",
        development_cohort_id="synthetic_cleveland",
        synthetic_data_confirmed=True,
        config=FAST_TEST_CONFIG,
    )

    # 1. Writing inside a non-ignored repository directory is rejected
    with pytest.raises(BundleIntegrityError) as exc_info:
        package_research_bundle(run, REPO_ROOT / "ai" / "forbidden_bundle_out")
    assert exc_info.value.code == "unignored_repository_path_prohibited"
    assert not (REPO_ROOT / "ai" / "forbidden_bundle_out").exists()

    # 2. Overwriting an existing bundle directory is rejected
    base_dir = tmp_path / "clean_bundle"
    package_research_bundle(run, base_dir)
    with pytest.raises(BundleIntegrityError) as exc_info:
        package_research_bundle(run, base_dir)
    assert exc_info.value.code == "bundle_directory_already_exists"

    # 3. Single-byte corruption in any artifact file fails closed BEFORE joblib.load
    for target_file in (
        "model.joblib",
        "preprocessing.json",
        "calibration.json",
        "shap_background.json",
    ):
        corrupted_dir = tmp_path / f"corrupt_{target_file}"
        corrupted_dir.mkdir()
        for item in base_dir.iterdir():
            (corrupted_dir / item.name).write_bytes(item.read_bytes())
        raw = bytearray((corrupted_dir / target_file).read_bytes())
        raw[0] ^= 0x01
        (corrupted_dir / target_file).write_bytes(bytes(raw))
        with pytest.raises(BundleIntegrityError) as exc_info:
            ResearchCadPredictor.from_verified_bundle(
                corrupted_dir, trusted_local_root=tmp_path
            )
        assert exc_info.value.code == "file_sha256_mismatch"

    # 4. Self-declared serving approval or pooled flag in manifest fails closed
    escalated_dir = tmp_path / "escalated_bundle"
    escalated_dir.mkdir()
    for item in base_dir.iterdir():
        (escalated_dir / item.name).write_bytes(item.read_bytes())
    manifest = json.loads((escalated_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest["eligibility"]["approved_for_serving"] = True
    (escalated_dir / "manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    with pytest.raises(BundleIntegrityError) as exc_info:
        verify_research_bundle(escalated_dir)
    assert exc_info.value.code == "unauthorized_serving_claim"

    # 5. Unexpected extra file fails closed
    extra_dir = tmp_path / "extra_file_bundle"
    extra_dir.mkdir()
    for item in base_dir.iterdir():
        (extra_dir / item.name).write_bytes(item.read_bytes())
    (extra_dir / "rogue.txt").write_text("rogue", encoding="utf-8")
    with pytest.raises(BundleIntegrityError) as exc_info:
        verify_research_bundle(extra_dir)
    assert exc_info.value.code == "unexpected_bundle_directory_contents"

    # 6. Symlinked member file fails closed
    symlink_dir = tmp_path / "symlink_bundle"
    symlink_dir.mkdir()
    outside = tmp_path / "outside_cal.json"
    outside.write_bytes((base_dir / "calibration.json").read_bytes())
    for item in base_dir.iterdir():
        if item.name == "calibration.json":
            try:
                (symlink_dir / item.name).symlink_to(outside)
            except OSError:
                pytest.skip("Symlinks unavailable on platform.")
        else:
            (symlink_dir / item.name).write_bytes(item.read_bytes())
    with pytest.raises(BundleIntegrityError) as exc_info:
        verify_research_bundle(symlink_dir)
    assert exc_info.value.code == "bundle_symlink_prohibited"


def test_label_shuffle_negative_control_alarm_fails_closed() -> None:
    records, labels = _generate_synthetic_uci45_cohort(60, seed=1212)
    strict_cfg = ResearchTrainingConfig(
        protocol_id="CAI-AI1-STRICT-SHUFFLE-TEST",
        model_version="0.1.0",
        outer_folds=3,
        inner_folds=2,
        repeat_seeds=(20261025,),
        shuffle_control_seeds=(20261101,),
        shuffle_max_allowed_auroc=0.10,  # Guaranteed below chance -> forces alarm path
        lr_c_grid=(1.0,),
        rf_max_depths=(2,),
        rf_min_samples_leaf=(4,),
        rf_n_estimators=15,
        bootstrap_resamples=50,
        shap_max_background_samples=16,
    )
    with pytest.raises(CohortGovernanceError) as exc_info:
        train_research_model(
            records,
            labels,
            DA_A2_RESTING_LABS_PANEL,
            model_id="synth_shuffle_alarm",
            development_cohort_id="synthetic_cleveland",
            synthetic_data_confirmed=True,
            config=strict_cfg,
        )
    assert exc_info.value.code == "label_shuffle_leakage_alarm"


def test_ai_and_backend_packages_remain_strictly_decoupled() -> None:
    """M1c regression guard: backend never imports ai/, ai/ never imports backend or third-party shap/lime."""
    for root_pkg, forbidden_prefixes in (
        ("backend", {"ai"}),
        ("ai", {"backend", "shap", "lime"}),
    ):
        py_files = sorted((REPO_ROOT / root_pkg).rglob("*.py"))
        assert py_files
        for path in py_files:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    roots = {alias.name.split(".")[0] for alias in node.names}
                elif isinstance(node, ast.ImportFrom) and node.module:
                    roots = {node.module.split(".")[0]}
                else:
                    roots = set()
                overlap = roots & forbidden_prefixes
                assert not overlap, (
                    f"{path.relative_to(REPO_ROOT)} must not import {sorted(overlap)}"
                )


# --------------------------------------------------------------------------- #
# 7. Mandatory scientific & security regression tests (PR #52 review pass)
# --------------------------------------------------------------------------- #


class _DeserializationCanary:
    """Module-scope pickle canary proving untrusted joblib.load is never executed."""

    triggered: bool = False

    def __reduce__(self) -> tuple[Any, tuple[()]]:
        return (_trigger_deserialization_canary, ())


def _trigger_deserialization_canary() -> dict[str, str]:
    _DeserializationCanary.triggered = True
    raise RuntimeError("SECURITY VIOLATION: joblib.load executed on untrusted bundle!")


def test_cross_fitted_calibration_excludes_evaluated_observations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prove every evaluated test-fold observation is excluded from calibrator fitting."""
    import hashlib
    from sklearn.model_selection import StratifiedKFold
    import ai.training as training_mod

    records, labels = _generate_synthetic_uci45_cohort(84, seed=1313, nonlinear=False)
    X = np.vstack(
        [
            validate_clinical_record(r, DA_A2_RESTING_LABS_PANEL).as_row_array()
            for r in records
        ]
    )
    y = np.asarray(labels, dtype=np.int64)

    # 1. Spy on OofLogisticCalibrator.fit_from_oof during nested cross-fitting
    observed_fit_calls: list[tuple[str, int, str]] = []
    orig_fit = OofLogisticCalibrator.fit_from_oof

    @classmethod  # type: ignore[misc]
    def _spy_fit(
        cls: type[OofLogisticCalibrator],
        y_oof: np.ndarray,
        p_oof_raw: np.ndarray,
        **kwargs: Any,
    ) -> OofLogisticCalibrator:
        arr = np.asarray(y_oof, dtype=np.int64)
        digest = hashlib.sha256(arr.tobytes()).hexdigest()
        observed_fit_calls.append(
            (str(kwargs.get("fit_scope")), int(arr.size), digest)
        )
        return orig_fit.__func__(cls, y_oof, p_oof_raw, **kwargs)  # type: ignore[attr-defined]

    monkeypatch.setattr(OofLogisticCalibrator, "fit_from_oof", _spy_fit)

    run = train_research_model(
        records,
        labels,
        DA_A2_RESTING_LABS_PANEL,
        model_id="synth_cross_cal_proof",
        development_cohort_id="synthetic_cleveland",
        synthetic_data_confirmed=True,
        config=FAST_TEST_CONFIG,
    )

    outer_splits = list(
        StratifiedKFold(
            n_splits=FAST_TEST_CONFIG.outer_folds,
            shuffle=True,
            random_state=FAST_TEST_CONFIG.repeat_seeds[0],
        ).split(np.zeros(len(y)), y)
    )
    expected_train_digests = {
        hashlib.sha256(np.asarray(y[tr_idx], dtype=np.int64).tobytes()).hexdigest()
        for tr_idx, _ in outer_splits
    }
    inner_calls = [
        c for c in observed_fit_calls if c[0] == "INNER_CV_FOLD_CONTAINED"
    ]
    assert len(inner_calls) == FAST_TEST_CONFIG.outer_folds * 3  # dummy + LR + RF per fold
    for _, sample_count, y_digest in inner_calls:
        assert sample_count < len(y)  # Strictly smaller than full cohort
        assert y_digest in expected_train_digests  # Matches y[train_idx], zero test_idx rows

    # 2. Direct perturbation invariance: drastically changing X[test_idx] on fold 1
    #    leaves fold 1's fitted calibrator (intercept, slope) bitwise identical.
    _, fold1_test_idx = outer_splits[0]
    X_perturbed = X.copy()
    X_perturbed[fold1_test_idx, 0] = 79.0  # Extreme age on test fold only
    X_perturbed[fold1_test_idx, 3] = 195.0  # Extreme BP on test fold only
    X_perturbed[fold1_test_idx, 5] = 380.0  # Extreme chol on test fold only

    _, _, orig_fold_recs, _ = training_mod._run_single_nested_pass(
        X,
        y,
        panel=DA_A2_RESTING_LABS_PANEL,
        config=FAST_TEST_CONFIG,
        repeat_seed=FAST_TEST_CONFIG.repeat_seeds[0],
        retain_fold_models=False,
        fit_cross_calibrators=True,
    )
    _, _, pert_fold_recs, _ = training_mod._run_single_nested_pass(
        X_perturbed,
        y,
        panel=DA_A2_RESTING_LABS_PANEL,
        config=FAST_TEST_CONFIG,
        repeat_seed=FAST_TEST_CONFIG.repeat_seeds[0],
        retain_fold_models=False,
        fit_cross_calibrators=True,
    )
    assert (
        orig_fold_recs[0]["fold_calibrator"] == pert_fold_recs[0]["fold_calibrator"]
    )

    # 3. Verify strict separation of the three internal evaluation blocks
    ie = run.internal_evaluation
    assert "calibrated_selected_oof_metrics" not in ie
    assert ie["uncalibrated_nested_cv"]["post_hoc_calibration_applied"] is False
    assert (
        ie["cross_fitted_calibrated_nested_cv"][
            "each_observation_excluded_from_model_and_calibrator_fit"
        ]
        is True
    )
    assert (
        ie["cross_fitted_calibrated_nested_cv"][
            "unbiased_within_cohort_calibrated_estimate"
        ]
        is True
    )
    apparent = ie["final_development_calibrator_apparent_diagnostic"]
    assert apparent["apparent_in_calibrator_fit"] is True
    assert apparent["unbiased_calibrated_performance_estimate"] is False


def test_calibrated_log_odds_linear_shap_and_raw_tree_shap_score_alignment(
    tmp_path: Path,
) -> None:
    """Verify exact calibrated-log-odds LinearSHAP math & honest raw-score TreeSHAP alignment."""
    from scipy.special import expit

    records, labels = _generate_synthetic_uci45_cohort(
        72, seed=1414, nonlinear=False, missing_lab_rate=0.20
    )
    X = np.vstack(
        [
            validate_clinical_record(r, DA_A2_RESTING_LABS_PANEL).as_row_array()
            for r in records
        ]
    )
    y = np.asarray(labels, dtype=np.int64)
    prep = FoldSafeClinicalPreprocessor.fit(X, DA_A2_RESTING_LABS_PANEL)
    Z = prep.transform(X)
    lr = LogisticRegression(C=5.0, solver="lbfgs", max_iter=1000, random_state=21).fit(
        Z, y
    )
    # Amplify weights to also exercise extreme |raw_log_odds| > 15 without probability clipping
    lr.coef_ = lr.coef_ * 4.5
    raw_logits = lr.decision_function(Z)
    raw_probs = np.asarray(expit(raw_logits), dtype=np.float64)
    assert np.max(np.abs(raw_logits)) > 14.0

    cal = OofLogisticCalibrator.fit_from_oof(
        y,
        raw_probs,
        model_family="l2_logistic_regression",
        raw_logits=raw_logits,
    )
    assert cal.input_link == "exact_raw_log_odds"

    X_bg_raw = X[:12]
    Z_bg = prep.transform(X_bg_raw)
    bg_ref = ShapBackgroundReference(
        panel_id=prep.panel_id,
        panel_contract_sha256=prep.panel_contract_sha256,
        encoded_feature_names=prep.encoded_feature_names,
        background_matrix=Z_bg,
    )

    extreme_idx = int(np.argmax(np.abs(raw_logits)))
    for row_idx in (0, 4, extreme_idx):
        x_raw = X[row_idx]
        z_row = Z[row_idx]
        cal_expl = explain_clinical_instance(
            model_family="l2_logistic_regression",
            estimator=lr,
            preprocessor=prep,
            panel=DA_A2_RESTING_LABS_PANEL,
            background=bg_ref,
            z_row=z_row,
            calibrator=cal,
        )
        oracle_base, oracle_target, oracle_phi = exact_coalition_shapley_oracle(
            lambda Z_in: cal.transform_log_odds(lr.decision_function(Z_in)),
            prep,
            x_raw,
            X_bg_raw,
        )
        phi_vec = np.array([a.shap_value for a in cal_expl.attributions])

        assert cal_expl.explained_quantity == "calibrated_log_odds"
        assert cal_expl.scale == "calibrated_log_odds"
        assert cal_expl.explains_calibrated_score_directly is True
        assert cal_expl.additive_on_calibrated_probability is False
        assert cal_expl.linked_probability_quantity == "calibrated_research_score"
        assert abs(cal_expl.base_value - oracle_base) < 1e-12
        assert abs(cal_expl.target_prediction_on_scale - oracle_target) < 1e-12
        assert np.max(np.abs(phi_vec - oracle_phi)) < 1e-12
        expected_cal_prob = float(
            cal.calibrate_from_log_odds(float(lr.decision_function(z_row.reshape(1, -1))[0]))
        )
        assert (
            abs(float(expit(cal_expl.base_value + np.sum(phi_vec))) - expected_cal_prob)
            < 1e-14
        )

    # Constant fallback calibrator (slope == 0.0) yields exact zero calibrated attributions
    zero_cal = OofLogisticCalibrator(
        model_family="l2_logistic_regression",
        intercept=-0.35,
        slope=0.0,
        development_prevalence=0.42,
        n_oof_samples=50,
        oof_brier_before=0.24,
        oof_brier_after=0.24,
        status="IDENTITY_CONSTANT_FALLBACK",
        input_link="exact_raw_log_odds",
        fit_scope="FULL_DEVELOPMENT_OOF_FINAL",
    )
    const_expl = explain_clinical_instance(
        model_family="l2_logistic_regression",
        estimator=lr,
        preprocessor=prep,
        panel=DA_A2_RESTING_LABS_PANEL,
        background=bg_ref,
        z_row=Z[0],
        calibrator=zero_cal,
    )
    assert const_expl.base_value == -0.35
    assert const_expl.target_prediction_on_scale == -0.35
    assert all(v == 0.0 for v in const_expl.attribution_map().values())

    # End-to-end LR bundle prediction alignment check
    lr_run = train_research_model(
        records,
        labels,
        DA_A2_RESTING_LABS_PANEL,
        model_id="synth_lr_aligned",
        development_cohort_id="synthetic_cleveland",
        synthetic_data_confirmed=True,
        config=FAST_TEST_CONFIG,
    )
    assert lr_run.selected_model_family == "l2_logistic_regression"
    lr_bundle = tmp_path / "lr_aligned_bundle"
    package_research_bundle(lr_run, lr_bundle)
    lr_pred = ResearchCadPredictor.from_verified_bundle(
        lr_bundle, trusted_local_root=tmp_path
    ).predict_research_only(records[0])
    pred_dict = lr_pred.to_dict()["prediction"]
    assert pred_dict["shap_explained_quantity"] == "calibrated_log_odds"
    assert pred_dict["shap_mathematical_scale"] == "calibrated_log_odds"
    assert pred_dict["shap_explains_calibrated_score_directly"] is True
    assert pred_dict["shap_additive_on_calibrated_probability"] is False
    assert abs(pred_dict["shap_target_value_on_scale"] - lr_pred.calibrated_log_odds) < 1e-12
    assert (
        abs(float(expit(lr_pred.calibrated_log_odds)) - lr_pred.calibrated_research_score)
        < 1e-14
    )

    # Tree model with calibrator MUST NOT relabel raw-probability TreeSHAP as calibrated SHAP
    rf = RandomForestClassifier(
        n_estimators=15, max_depth=3, min_samples_leaf=3, random_state=9, n_jobs=1
    ).fit(Z, y)
    rf_cal = OofLogisticCalibrator.fit_from_oof(
        y, rf.predict_proba(Z)[:, 1], model_family="constrained_random_forest"
    )
    rf_expl = explain_clinical_instance(
        model_family="constrained_random_forest",
        estimator=rf,
        preprocessor=prep,
        panel=DA_A2_RESTING_LABS_PANEL,
        background=bg_ref,
        z_row=Z[0],
        calibrator=rf_cal,
    )
    assert rf_expl.explained_quantity == "raw_model_score"
    assert rf_expl.scale == "raw_model_probability"
    assert rf_expl.explains_calibrated_score_directly is False
    assert rf_expl.additive_on_calibrated_probability is False
    assert abs(rf_expl.target_prediction_on_scale - float(rf.predict_proba(Z[:1])[0, 1])) < 1e-12


def test_fold_dispersion_uses_compatible_per_fold_calibrators_without_epistemic_claims(
    tmp_path: Path,
) -> None:
    """Verify heterogeneous outer folds use each fold's own calibrator and honest semantics."""
    records, labels = _generate_synthetic_uci45_cohort(84, seed=1515, nonlinear=False)
    run = train_research_model(
        records,
        labels,
        DA_A2_RESTING_LABS_PANEL,
        model_id="synth_hetero_fold_test",
        development_cohort_id="synthetic_cleveland",
        synthetic_data_confirmed=True,
        config=FAST_TEST_CONFIG,
    )

    # Construct a valid heterogeneous fold ensemble: fold 1 = LR, fold 2 = RF (each with its own calibrator)
    X, y, _ = (
        np.vstack(
            [
                validate_clinical_record(r, DA_A2_RESTING_LABS_PANEL).as_row_array()
                for r in records
            ]
        ),
        np.asarray(labels, dtype=np.int64),
        None,
    )
    prep_rf = FoldSafeClinicalPreprocessor.fit(X[:60], DA_A2_RESTING_LABS_PANEL)
    Z_rf = prep_rf.transform(X[:60])
    rf_est = RandomForestClassifier(
        n_estimators=15, max_depth=3, min_samples_leaf=4, random_state=31, n_jobs=1
    ).fit(Z_rf, y[:60])
    rf_cal = OofLogisticCalibrator.fit_from_oof(
        y[:60],
        rf_est.predict_proba(Z_rf)[:, 1],
        model_family="constrained_random_forest",
        fit_scope="INNER_CV_FOLD_CONTAINED",
    )
    hetero_run = TrainedResearchRun(
        model_id=run.model_id,
        model_version=run.model_version,
        protocol_id=run.protocol_id,
        panel=run.panel,
        development_cohort_id=run.development_cohort_id,
        development_dataset_id=run.development_dataset_id,
        synthetic_only=True,
        selected_model_family=run.selected_model_family,
        selected_hyperparameters=run.selected_hyperparameters,
        preprocessor=run.preprocessor,
        estimator=run.estimator,
        calibrator=run.calibrator,
        shap_background=run.shap_background,
        fold_ensemble=(
            run.fold_ensemble[0],
            FoldEnsembleMember(
                fold_index=2,
                model_family="constrained_random_forest",
                preprocessor=prep_rf,
                estimator=rf_est,
                calibrator=rf_cal,
            ),
        ),
        internal_evaluation=run.internal_evaluation,
        negative_control=run.negative_control,
    )

    bundle_dir = tmp_path / "hetero_bundle"
    package_research_bundle(hetero_run, bundle_dir)
    predictor = ResearchCadPredictor.from_verified_bundle(
        bundle_dir, trusted_local_root=tmp_path
    )
    res = predictor.predict_research_only(records[0])
    unc = res.uncertainty

    assert (
        unc["uncertainty_semantics"]
        == "DESCRIPTIVE_OUTER_FOLD_DISPERSION_NOT_VALIDATED_UNCERTAINTY"
    )
    assert unc["validated_epistemic_uncertainty"] is False
    assert unc["validated_patient_specific_interval"] is False
    assert unc["action_threshold_validated"] is False
    assert "high_epistemic_spread_flag" not in unc
    assert unc["homogeneous_model_family"] is False
    assert unc["fold_model_families"] == [
        run.fold_ensemble[0].model_family,
        "constrained_random_forest",
    ]
    assert unc["each_fold_calibrated_by_own_training_fold_calibrator"] is True


def test_interrupted_packaging_cleanup_untrusted_bundle_rejection_and_shap_privacy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify atomic staging cleanup, HMAC/origin boundary before joblib.load, and SHAP privacy."""
    import hashlib
    import os
    import joblib
    import ai.packaging as pkg_mod

    records, labels = _generate_synthetic_uci45_cohort(72, seed=1616)
    run = train_research_model(
        records,
        labels,
        DA_A2_RESTING_LABS_PANEL,
        model_id="synth_security_guard_v0",
        development_cohort_id="synthetic_cleveland",
        synthetic_data_confirmed=True,
        config=FAST_TEST_CONFIG,
    )

    # 1. Interrupted packaging after partial file writes cleans up staging completely
    interrupted_target = tmp_path / "interrupted_bundle"
    orig_write = pkg_mod._write_atomic_private
    call_counter = {"n": 0}

    def _failing_write(path: Path, content: bytes) -> dict[str, Any]:
        call_counter["n"] += 1
        if call_counter["n"] == 4:
            raise OSError("Simulated mid-packaging disk interruption")
        return orig_write(path, content)

    with monkeypatch.context() as mp:
        mp.setattr(pkg_mod, "_write_atomic_private", _failing_write)
        with pytest.raises(OSError, match="Simulated mid-packaging"):
            package_research_bundle(run, interrupted_target)

    assert not interrupted_target.exists()
    leftover_staging = [
        p.name for p in tmp_path.iterdir() if p.name.startswith(".staging_")
    ]
    assert leftover_staging == []

    # 2. Build a legitimate signed bundle under key_a inside trusted_root
    from ai.filesystem_security import loosen_access_for_negative_test

    trusted_root = ensure_private_directory(tmp_path / "trusted_store")
    key_a = b"A" * 32
    key_b = b"B" * 32
    good_bundle = trusted_root / "good_bundle"
    package_research_bundle(run, good_bundle, signing_key=key_a)

    # Plain verify_research_bundle checks SHA-256 only -> explicitly marks NOT safe for pickle
    hash_only_desc = verify_research_bundle(good_bundle)
    assert hash_only_desc.integrity_verified_only_not_authenticated is True
    assert hash_only_desc.producer_authenticated is False
    assert hash_only_desc.safe_for_pickle_deserialization is False

    # 3. Forged malicious pickle WITH recomputed valid SHA-256 in manifest.json:
    #    verify_research_bundle passes, MUST fail verify_trusted_local_bundle /
    #    from_verified_bundle BEFORE joblib.load ever executes _DeserializationCanary!
    _DeserializationCanary.triggered = False
    forged_bundle = ensure_private_directory(
        trusted_root / "forged_pickle_valid_sha256"
    )
    for item in good_bundle.iterdir():
        dst = forged_bundle / item.name
        dst.write_bytes(item.read_bytes())
        protect_private_file(dst)

    joblib.dump(_DeserializationCanary(), forged_bundle / "model.joblib", compress=3)
    protect_private_file(forged_bundle / "model.joblib")
    evil_bytes = (forged_bundle / "model.joblib").read_bytes()
    forged_manifest = json.loads(
        (forged_bundle / "manifest.json").read_text(encoding="utf-8")
    )
    forged_manifest["files"]["model.joblib"] = {
        "sha256": hashlib.sha256(evil_bytes).hexdigest(),
        "size_bytes": len(evil_bytes),
    }
    (forged_bundle / "manifest.json").write_text(
        json.dumps(forged_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    protect_private_file(forged_bundle / "manifest.json")

    # SHA-256 check alone succeeds (proving why SHA-256 != authentication)
    unauth = verify_research_bundle(forged_bundle)
    assert unauth.safe_for_pickle_deserialization is False

    # Deserialization boundary blocks it BEFORE joblib.load runs!
    with pytest.raises(BundleIntegrityError) as exc_info:
        ResearchCadPredictor.from_verified_bundle(
            forged_bundle, trusted_local_root=trusted_root, signing_key=key_a
        )
    assert exc_info.value.code == "untrusted_bundle_producer_signature"
    assert _DeserializationCanary.triggered is False

    # 4. Wrong signing key fails closed
    with pytest.raises(BundleIntegrityError) as exc_info:
        ResearchCadPredictor.from_verified_bundle(
            good_bundle, trusted_local_root=trusted_root, signing_key=key_b
        )
    assert exc_info.value.code == "untrusted_bundle_producer_signature"

    # 5. Bundle outside trusted_local_root fails closed
    other_root = ensure_private_directory(tmp_path / "other_trusted_root")
    with pytest.raises(BundleIntegrityError) as exc_info:
        ResearchCadPredictor.from_verified_bundle(
            good_bundle, trusted_local_root=other_root, signing_key=key_a
        )
    assert exc_info.value.code == "untrusted_bundle_location"

    # 6. Permissive access controls on shap_background.json fail closed (POSIX 0644 / NTFS Users FR)
    loosen_access_for_negative_test(
        good_bundle / "shap_background.json", is_directory=False
    )
    try:
        with pytest.raises(BundleIntegrityError) as exc_info:
            verify_trusted_local_bundle(
                good_bundle, trusted_local_root=trusted_root, signing_key=key_a
            )
        assert exc_info.value.code == "insecure_sensitive_artifact_permissions"
    finally:
        protect_private_file(good_bundle / "shap_background.json")

    # 7. Non-synthetic shap_background.json is blocked while Gate PT is closed
    with pytest.raises(ExplainabilityIntegrityError) as bg_exc:
        ShapBackgroundReference.from_training_encoded(
            run.shap_background.background_matrix,
            np.zeros(len(run.shap_background.background_matrix), dtype=np.int64),
            run.preprocessor,
            synthetic_only=False,
        )
    assert bg_exc.value.code == "real_patient_shap_background_blocked_gate_pt_closed"


def test_external_evaluation_primitive_single_shot_ledger_and_real_cohort_blocks(
    tmp_path: Path,
) -> None:
    """Verify stateless primitive semantics, single-shot ledger enforcement, and real cohort blocks."""
    dev_records, dev_labels = _generate_synthetic_uci45_cohort(72, seed=1717)
    ext_records, ext_labels = _generate_synthetic_uci45_cohort(60, seed=1818)

    run = train_research_model(
        dev_records,
        dev_labels,
        DA_A2_RESTING_LABS_PANEL,
        model_id="synth_ledger_model_v0",
        development_cohort_id="synthetic_cleveland",
        development_dataset_id="DA-A2:cleveland",
        synthetic_data_confirmed=True,
        config=FAST_TEST_CONFIG,
    )

    # 1. Real Hungary and Real AngioCAD cohort IDs are hard-blocked under synthetic-only auth
    with pytest.raises(CohortGovernanceError) as exc_h:
        evaluate_locked_external_cohort(
            run,
            ext_records,
            ext_labels,
            external_cohort_id="hungary",
            external_dataset_id="DA-A2:hungary",
            synthetic_data_confirmed=True,
            n_bootstrap=40,
        )
    assert exc_h.value.code == "real_hungary_blocked_pending_gate_pt"

    with pytest.raises(CohortGovernanceError) as exc_a:
        evaluate_locked_external_cohort(
            run,
            ext_records,
            ext_labels,
            external_cohort_id="angiocad_isfahan",
            external_dataset_id="zenodo:15826856",
            synthetic_data_confirmed=True,
            n_bootstrap=40,
        )
    assert exc_a.value.code == "angiocad_blocked_pending_d021_and_gate_da"

    # 2. Stateless call without ledger explicitly declares it is NOT one-shot enforced
    stateless_res = evaluate_locked_external_cohort(
        run,
        ext_records,
        ext_labels,
        external_cohort_id="synthetic_hungary",
        external_dataset_id="DA-A2:synthetic_hungary",
        synthetic_data_confirmed=True,
        n_bootstrap=40,
    )
    assert stateless_res["one_shot_enforced_by_ledger"] is False
    assert (
        stateless_res["execution_semantics"]
        == "STATELESS_FROZEN_MODEL_EVALUATION_PRIMITIVE_NOT_ONE_SHOT_ENFORCED"
    )
    assert (
        stateless_res["participant_independence_verification"]
        == "DECLARED_COHORT_METADATA_GUARD_ONLY_NOT_PATIENT_LEVEL_PROOF"
    )

    # 3. Ledger inside tracked repo directory is prohibited
    with pytest.raises(CohortGovernanceError) as exc_lp:
        ExternalEvaluationLedger(REPO_ROOT / "ai" / "forbidden_ledger.json")
    assert exc_lp.value.code == "unignored_ledger_path_prohibited"

    # 4. Ledger-protected call enforces single-shot execution across repeated invocations
    ledger_file = tmp_path / "protected_eval_ledger.json"
    first_led = evaluate_locked_external_cohort(
        run,
        ext_records,
        ext_labels,
        external_cohort_id="synthetic_hungary",
        external_dataset_id="DA-A2:synthetic_hungary",
        synthetic_data_confirmed=True,
        one_shot_ledger_path=ledger_file,
        n_bootstrap=40,
    )
    assert first_led["one_shot_enforced_by_ledger"] is True
    assert (
        first_led["execution_semantics"] == "LOCAL_LEDGER_ENFORCED_SINGLE_EVALUATION"
    )
    assert first_led["one_shot_ledger_receipt"]["status"] == "COMPLETED"
    assert verify_access_control(
        ledger_file, expect_directory=False, strict_private=True
    ).ok

    with pytest.raises(CohortGovernanceError) as exc_dup:
        evaluate_locked_external_cohort(
            run,
            ext_records,
            ext_labels,
            external_cohort_id="synthetic_hungary",
            external_dataset_id="DA-A2:synthetic_hungary",
            synthetic_data_confirmed=True,
            one_shot_ledger_path=ledger_file,
            n_bootstrap=40,
        )
    assert exc_dup.value.code == "one_shot_external_evaluation_already_consumed"


# --------------------------------------------------------------------------- #
# 8. Windows NTFS DACL engine, Windows runtime invariants & two-phase ledger
# --------------------------------------------------------------------------- #


def test_windows_binary_sid_acl_and_dacl_policy_engine() -> None:
    """Verify MS-DTYP binary SID/ACL parsing and fail-closed NTFS DACL policy evaluation."""
    from ai.filesystem_security import (
        ACCESS_ALLOWED_ACE_TYPE,
        ACCESS_DENIED_ACE_TYPE,
        FILE_READ_DATA,
        FILE_WRITE_DATA,
        GENERIC_ALL_ACCESS,
        INHERIT_ONLY_ACE_FLAG,
        SID_BUILTIN_ADMINS,
        SID_BUILTIN_USERS,
        SID_CREATOR_OWNER,
        SID_LOCAL_SYSTEM,
        ParsedWindowsAce,
        build_windows_acl_bytes,
        build_windows_binary_sid,
        evaluate_windows_dacl_policy,
        parse_windows_acl_bytes,
        parse_windows_binary_sid,
    )

    user_sid = "S-1-5-21-2489123456-987654321-1122334455-1001"
    foreign_sid = "S-1-5-21-2489123456-987654321-1122334455-9999"
    auth_users_sid = "S-1-5-11"
    everyone_sid = "S-1-1-0"

    for s in (
        user_sid,
        foreign_sid,
        SID_LOCAL_SYSTEM,
        SID_BUILTIN_ADMINS,
        SID_BUILTIN_USERS,
        SID_CREATOR_OWNER,
        auth_users_sid,
        everyone_sid,
    ):
        assert parse_windows_binary_sid(build_windows_binary_sid(s)) == s

    private_aces = (
        ParsedWindowsAce(ACCESS_ALLOWED_ACE_TYPE, 0, GENERIC_ALL_ACCESS, user_sid),
        ParsedWindowsAce(
            ACCESS_ALLOWED_ACE_TYPE, 0, GENERIC_ALL_ACCESS, SID_LOCAL_SYSTEM
        ),
        ParsedWindowsAce(
            ACCESS_ALLOWED_ACE_TYPE, 0, GENERIC_ALL_ACCESS, SID_BUILTIN_ADMINS
        ),
        ParsedWindowsAce(
            ACCESS_ALLOWED_ACE_TYPE,
            INHERIT_ONLY_ACE_FLAG,
            GENERIC_ALL_ACCESS,
            SID_CREATOR_OWNER,
        ),
    )
    roundtrip_aces = parse_windows_acl_bytes(build_windows_acl_bytes(private_aces))
    assert roundtrip_aces == private_aces

    # 1. Strict private NTFS DACL passes for normal user and elevated Administrator owner
    ok_res = evaluate_windows_dacl_policy(
        owner_sid=user_sid,
        current_user_sid=user_sid,
        caller_is_admin=False,
        persistent_acls_supported=True,
        dacl_present=True,
        dacl_is_null=False,
        aces=roundtrip_aces,
        strict_private=True,
    )
    assert ok_res.ok is True

    elevated_res = evaluate_windows_dacl_policy(
        owner_sid=SID_BUILTIN_ADMINS,
        current_user_sid=user_sid,
        caller_is_admin=True,
        persistent_acls_supported=True,
        dacl_present=True,
        dacl_is_null=False,
        aces=roundtrip_aces,
        strict_private=True,
    )
    assert elevated_res.ok is True

    # 2. Foreign owner fails closed with 'owner' category
    foreign_owner_res = evaluate_windows_dacl_policy(
        owner_sid=foreign_sid,
        current_user_sid=user_sid,
        caller_is_admin=False,
        persistent_acls_supported=True,
        dacl_present=True,
        dacl_is_null=False,
        aces=roundtrip_aces,
        strict_private=True,
    )
    assert not foreign_owner_res.ok and foreign_owner_res.reason_category == "owner"

    # 3. Non-NTFS volume (FAT32/exFAT without persistent ACLs) fails closed
    fat_res = evaluate_windows_dacl_policy(
        owner_sid=user_sid,
        current_user_sid=user_sid,
        caller_is_admin=False,
        persistent_acls_supported=False,
        dacl_present=True,
        dacl_is_null=False,
        aces=roundtrip_aces,
        strict_private=True,
    )
    assert not fat_res.ok and fat_res.reason_category == "permissions"

    # 4. NULL or missing DACL fails closed
    null_dacl_res = evaluate_windows_dacl_policy(
        owner_sid=user_sid,
        current_user_sid=user_sid,
        caller_is_admin=False,
        persistent_acls_supported=True,
        dacl_present=True,
        dacl_is_null=True,
        aces=(),
        strict_private=True,
    )
    assert not null_dacl_res.ok and null_dacl_res.reason_category == "permissions"

    # 5. BUILTIN\Users or Everyone read access (even INHERIT_ONLY) fails strict_private
    for bad_principal, flags in (
        (SID_BUILTIN_USERS, 0),
        (everyone_sid, 0),
        (auth_users_sid, 0),
        (SID_BUILTIN_USERS, INHERIT_ONLY_ACE_FLAG),
    ):
        leaky_aces = (*roundtrip_aces, ParsedWindowsAce(ACCESS_ALLOWED_ACE_TYPE, flags, FILE_READ_DATA, bad_principal))
        leaky_res = evaluate_windows_dacl_policy(
            owner_sid=user_sid,
            current_user_sid=user_sid,
            caller_is_admin=False,
            persistent_acls_supported=True,
            dacl_present=True,
            dacl_is_null=False,
            aces=leaky_aces,
            strict_private=True,
        )
        assert not leaky_res.ok

    # 6. Default unhardened secondary drive E:\ ACL (Authenticated Users Modify) fails trusted_local_root
    e_drive_default_aces = (
        *roundtrip_aces,
        ParsedWindowsAce(
            ACCESS_ALLOWED_ACE_TYPE, 0, FILE_READ_DATA | FILE_WRITE_DATA, auth_users_sid
        ),
    )
    e_root_res = evaluate_windows_dacl_policy(
        owner_sid=user_sid,
        current_user_sid=user_sid,
        caller_is_admin=False,
        persistent_acls_supported=True,
        dacl_present=True,
        dacl_is_null=False,
        aces=e_drive_default_aces,
        strict_private=False,
    )
    assert not e_root_res.ok

    # 7. Preceding ACCESS_DENIED_ACE blocking caller read fails closed
    denied_aces = (
        ParsedWindowsAce(ACCESS_DENIED_ACE_TYPE, 0, FILE_READ_DATA, user_sid),
        *roundtrip_aces,
    )
    denied_res = evaluate_windows_dacl_policy(
        owner_sid=user_sid,
        current_user_sid=user_sid,
        caller_is_admin=False,
        persistent_acls_supported=True,
        dacl_present=True,
        dacl_is_null=False,
        aces=denied_aces,
        strict_private=True,
    )
    assert not denied_res.ok


def test_windows_runtime_paths_reparse_points_and_no_fchmod_or_st_mode_reliance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prove os.name == 'nt' flow never calls os.fchmod or trusts Unix st_mode bits."""
    import os
    import ai.filesystem_security as fs_sec
    import ai.packaging as pkg_mod

    # 1. Reserved Windows device names & unsafe basenames are blocked
    for bad_name in ("con", "con.json", "nul.txt", "prn", "com1.bin", "lpt9.dat", "bad."):
        assert fs_sec.is_valid_artifact_basename(bad_name) is False

    # 2. Simulated NTFS junction / FILE_ATTRIBUTE_REPARSE_POINT is rejected
    junc_dir = tmp_path / "simulated_ntfs_junction"
    junc_dir.mkdir()
    with monkeypatch.context() as mp:
        mp.setattr(Path, "is_junction", lambda self: self == junc_dir, raising=False)
        assert fs_sec.is_reparse_or_symlink(junc_dir) is True
        with pytest.raises(BundleIntegrityError) as j_exc:
            verify_research_bundle(junc_dir)
        assert j_exc.value.code == "invalid_bundle_directory"

    # 3. Simulate Windows runtime: os.name == "nt", NO os.fchmod attribute, and
    #    files left at 0o666 / dirs at 0o777 (matching Windows CRT stat().st_mode!).
    #    Key by (st_dev, st_ino) to model NTFS per-MFT-record Security Descriptors
    #    persisting across atomic os.replace(staging_dir, target_dir) renames.
    protected_inodes: dict[tuple[int, int], str] = {}
    touched_paths: list[Path] = []

    def _inode_key(path: Path) -> tuple[int, int]:
        st = path.stat()
        return (int(st.st_dev), int(st.st_ino))

    def _fake_win32_set_private_dacl(path: Path, *, is_directory: bool) -> None:
        # Leave POSIX mode permissive (0o666 / 0o777) to prove st_mode is NOT trusted!
        os.chmod(path, 0o777 if is_directory else 0o666)
        protected_inodes[_inode_key(path)] = "PRIVATE_D_PAI"
        touched_paths.append(path)

    def _fake_win32_verify_path_dacl(
        path: Path, *, strict_private: bool
    ) -> fs_sec.AccessControlVerificationResult:
        state = protected_inodes.get(_inode_key(path))
        if state == "PRIVATE_D_PAI":
            return fs_sec.AccessControlVerificationResult(ok=True)
        return fs_sec.AccessControlVerificationResult(
            ok=False,
            reason_category="permissions",
            detail="Missing verified NTFS D:PAI ACL in simulated Windows check.",
        )

    records, labels = _generate_synthetic_uci45_cohort(64, seed=2121)
    run = train_research_model(
        records,
        labels,
        DA_A2_RESTING_LABS_PANEL,
        model_id="synth_win_sim_v1",
        development_cohort_id="synthetic_cleveland",
        synthetic_data_confirmed=True,
        config=FAST_TEST_CONFIG,
    )

    local_appdata_dir = tmp_path / "LocalAppDataSim"
    win_root = tmp_path / "win_trusted_bundles"
    win_root.mkdir()
    protected_inodes[_inode_key(win_root)] = "PRIVATE_D_PAI"

    with monkeypatch.context() as mp:
        mp.setattr(fs_sec, "is_windows_runtime", lambda: True)
        mp.setattr(pkg_mod, "is_windows_runtime", lambda: True)
        mp.delattr(os, "fchmod", raising=False)
        mp.delenv("CARDIOASSIST_LOCAL_SIGNING_KEY_PATH", raising=False)
        mp.setenv("LOCALAPPDATA", str(local_appdata_dir))
        mp.setattr(fs_sec, "_win32_set_private_dacl", _fake_win32_set_private_dacl)
        mp.setattr(fs_sec, "_win32_verify_path_dacl", _fake_win32_verify_path_dacl)

        default_key_path = pkg_mod._default_local_signing_key_path()
        assert default_key_path == (
            local_appdata_dir / "CardioAssistAI" / "local_bundle_hmac_v1.key"
        )
        key = get_or_create_local_signing_key()
        assert len(key) == 32
        # Even though st_mode is 0o666, Windows path succeeds ONLY because NTFS DACL verified!
        assert (default_key_path.stat().st_mode & 0o077) != 0

        win_bundle = win_root / "bundle_on_ntfs"
        package_research_bundle(run, win_bundle)
        predictor = ResearchCadPredictor.from_verified_bundle(
            win_bundle, trusted_local_root=win_root
        )
        pred = predictor.predict_research_only(records[0])
        assert 0.0 < pred.calibrated_research_score < 1.0

        # The instant NTFS DACL isolation is absent (even if someone ran os.chmod(0o600)!),
        # Windows verification MUST fail closed!
        os.chmod(win_bundle / "model.joblib", 0o600)
        protected_inodes.pop(_inode_key(win_bundle / "model.joblib"))
        with pytest.raises(BundleIntegrityError) as acl_exc:
            verify_trusted_local_bundle(win_bundle, trusted_local_root=win_root)
        assert acl_exc.value.code == "insecure_sensitive_artifact_permissions"
        protected_inodes[_inode_key(win_bundle / "model.joblib")] = "PRIVATE_D_PAI"

        # Verify ExternalEvaluationLedger under simulated Windows runtime (no os.fchmod,
        # st_mode == 0o666 ignored, NTFS DACL verified)
        win_ledger_path = tmp_path / "win_ledgers" / "ntfs_ledger.json"
        ext_records, ext_labels = _generate_synthetic_uci45_cohort(52, seed=2122)
        led_res = evaluate_locked_external_cohort(
            run,
            ext_records,
            ext_labels,
            external_cohort_id="synthetic_hungary",
            external_dataset_id="DA-A2:synthetic_hungary",
            synthetic_data_confirmed=True,
            one_shot_ledger_path=win_ledger_path,
            n_bootstrap=30,
        )
        assert led_res["one_shot_ledger_receipt"]["status"] == "COMPLETED"
        assert (win_ledger_path.stat().st_mode & 0o077) != 0

        os.chmod(win_ledger_path, 0o600)
        protected_inodes.pop(_inode_key(win_ledger_path))
        with pytest.raises(CohortGovernanceError) as led_acl_exc:
            ExternalEvaluationLedger(win_ledger_path).list_entries()
        assert led_acl_exc.value.code == "insecure_ledger_permissions"
        protected_inodes[_inode_key(win_ledger_path)] = "PRIVATE_D_PAI"

    # Cleanup 0o666/0o777 test permissions inside tmp_path
    for p in (*touched_paths, win_bundle):
        if p.exists():
            os.chmod(p, 0o700 if p.is_dir() else 0o600)
    if win_bundle.exists():
        for child in win_bundle.iterdir():
            os.chmod(child, 0o600)


def test_external_evaluation_ledger_two_phase_failure_recovery_and_concurrency(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify RESERVED/COMPLETED/FAILED semantics, safe recovery, and concurrent duplicate block."""
    from concurrent.futures import ThreadPoolExecutor
    import threading
    import ai.training as tr_mod

    dev_records, dev_labels = _generate_synthetic_uci45_cohort(72, seed=2222)
    ext_records, ext_labels = _generate_synthetic_uci45_cohort(60, seed=2323)

    run_a = train_research_model(
        dev_records,
        dev_labels,
        DA_A2_RESTING_LABS_PANEL,
        model_id="synth_ledger_v2_model_a",
        development_cohort_id="synthetic_cleveland",
        development_dataset_id="DA-A2:cleveland",
        synthetic_data_confirmed=True,
        config=FAST_TEST_CONFIG,
    )
    run_b = train_research_model(
        dev_records,
        dev_labels,
        DA_A2_RESTING_LABS_PANEL,
        model_id="synth_ledger_v2_model_b",
        development_cohort_id="synthetic_cleveland",
        development_dataset_id="DA-A2:cleveland",
        synthetic_data_confirmed=True,
        config=FAST_TEST_CONFIG,
    )

    ledger_path = tmp_path / "two_phase_ledger.json"

    # 1. Failure during evaluation marks entry FAILED (NEVER COMPLETED)
    orig_eval_metrics = tr_mod.evaluate_comprehensive_metrics

    def _boom_metrics(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("Simulated mid-evaluation bootstrap crash")

    with monkeypatch.context() as mp:
        mp.setattr(tr_mod, "evaluate_comprehensive_metrics", _boom_metrics)
        with pytest.raises(RuntimeError, match="Simulated mid-evaluation"):
            evaluate_locked_external_cohort(
                run_a,
                ext_records,
                ext_labels,
                external_cohort_id="synthetic_hungary",
                external_dataset_id="DA-A2:synthetic_hungary",
                synthetic_data_confirmed=True,
                one_shot_ledger_path=ledger_path,
                n_bootstrap=30,
            )

    entries_1 = ExternalEvaluationLedger(ledger_path).list_entries()
    assert len(entries_1) == 1
    assert entries_1[0]["status"] == "FAILED"
    assert entries_1[0]["completed_at_utc"] is None
    assert entries_1[0]["failure_error_type"] == "RuntimeError"

    # 2. Retry without recover_after_failure=True fails closed
    with pytest.raises(CohortGovernanceError) as unrec_exc:
        evaluate_locked_external_cohort(
            run_a,
            ext_records,
            ext_labels,
            external_cohort_id="synthetic_hungary",
            external_dataset_id="DA-A2:synthetic_hungary",
            synthetic_data_confirmed=True,
            one_shot_ledger_path=ledger_path,
            n_bootstrap=30,
        )
    assert unrec_exc.value.code == "prior_external_evaluation_failed_recovery_required"

    # 3. Attempting recovery with a DIFFERENT model_id fails closed (anti-model-swapping!)
    with pytest.raises(CohortGovernanceError) as swap_exc:
        evaluate_locked_external_cohort(
            run_b,
            ext_records,
            ext_labels,
            external_cohort_id="synthetic_hungary",
            external_dataset_id="DA-A2:synthetic_hungary",
            synthetic_data_confirmed=True,
            one_shot_ledger_path=ledger_path,
            recover_after_failure=True,
            n_bootstrap=30,
        )
    assert swap_exc.value.code == "recovery_model_provenance_mismatch"

    # 4. Safe recovery with identical frozen run_a completes and preserves FAILED audit history
    recovered_res = evaluate_locked_external_cohort(
        run_a,
        ext_records,
        ext_labels,
        external_cohort_id="synthetic_hungary",
        external_dataset_id="DA-A2:synthetic_hungary",
        synthetic_data_confirmed=True,
        one_shot_ledger_path=ledger_path,
        recover_after_failure=True,
        n_bootstrap=30,
    )
    assert recovered_res["one_shot_ledger_receipt"]["status"] == "COMPLETED"
    assert (
        recovered_res["one_shot_ledger_receipt"]["recovered_from_reservation_id"]
        == entries_1[0]["reservation_id"]
    )
    entries_2 = ExternalEvaluationLedger(ledger_path).list_entries()
    assert [e["status"] for e in entries_2] == ["FAILED", "COMPLETED"]

    # 5. Concurrent duplicate race: two threads call evaluate_locked_external_cohort simultaneously;
    #    EXACTLY ONE succeeds and the contender fails closed!
    race_ledger_path = tmp_path / "concurrent_race_ledger.json"
    entered_metrics = threading.Event()
    release_metrics = threading.Event()

    def _gated_metrics(*args: Any, **kwargs: Any) -> dict[str, Any]:
        entered_metrics.set()
        release_metrics.wait(timeout=5.0)
        return orig_eval_metrics(*args, **kwargs)

    def _worker() -> str:
        try:
            res = evaluate_locked_external_cohort(
                run_a,
                ext_records,
                ext_labels,
                external_cohort_id="synthetic_switzerland",
                external_dataset_id="DA-A2:synthetic_switzerland",
                synthetic_data_confirmed=True,
                one_shot_ledger_path=race_ledger_path,
                n_bootstrap=30,
            )
            return str(res["one_shot_ledger_receipt"]["status"])
        except CohortGovernanceError as exc:
            return exc.code

    with monkeypatch.context() as mp:
        mp.setattr(tr_mod, "evaluate_comprehensive_metrics", _gated_metrics)
        with ThreadPoolExecutor(max_workers=2) as pool:
            fut1 = pool.submit(_worker)
            assert entered_metrics.wait(timeout=5.0)
            # Launch contender while fut1 holds an active RESERVED entry in flight!
            fut2 = pool.submit(_worker)
            contender_outcome = fut2.result(timeout=5.0)
            release_metrics.set()
            winner_outcome = fut1.result(timeout=5.0)

    assert winner_outcome == "COMPLETED"
    assert contender_outcome == "external_evaluation_currently_reserved_in_flight"
    final_race_entries = ExternalEvaluationLedger(race_ledger_path).list_entries()
    assert len(final_race_entries) == 1
    assert final_race_entries[0]["status"] == "COMPLETED"


def test_end_to_end_platform_validation_harness_cli(tmp_path: Path) -> None:
    """Execute the full 8-step maintainer validation harness inside CI."""
    from ai.validation_harness import run_end_to_end_platform_validation

    report = run_end_to_end_platform_validation(tmp_path / "harness_work")
    assert report["status"] == "PASSED"
    assert len(report["steps_passed"]) == 8

