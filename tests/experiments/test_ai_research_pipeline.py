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
    FoldSafeClinicalPreprocessor,
    OofLogisticCalibrator,
    PreprocessingContractError,
    ResearchCadPredictor,
    ResearchTrainingConfig,
    ShapBackgroundReference,
    evaluate_locked_external_cohort,
    exact_coalition_shapley_oracle,
    explain_clinical_instance,
    package_research_bundle,
    train_research_model,
    validate_clinical_record,
    verify_research_bundle,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

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
        assert expl.scale == "log_odds"
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
    predictor = ResearchCadPredictor.from_verified_bundle(bundle_dir)
    result = predictor.predict_research_only(records[0])
    assert result.model_family == "constrained_random_forest"
    assert result.explanation.method == "tree_shap_interventional"
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

    predictor = ResearchCadPredictor.from_verified_bundle(bundle_dir)
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
            ResearchCadPredictor.from_verified_bundle(corrupted_dir)
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
