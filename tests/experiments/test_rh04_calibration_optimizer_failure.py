"""F-CAL-01: reject failed or malformed fitted calibration results."""
from types import SimpleNamespace

import numpy as np
import pytest
from scipy.optimize import minimize as real_minimize
from scipy.special import expit
from sklearn.metrics import brier_score_loss

from ai import calibration
from ai.errors import CalibrationIntegrityError


Y = np.array([0, 1, 0, 0, 1, 0, 1, 1], dtype=np.float64)
Z = np.array([-2, -1, -.5, -.2, .2, .5, 1, 2], dtype=np.float64)
P = expit(Z)


def _fit(**kwargs):
    return calibration.OofLogisticCalibrator.fit_from_oof(
        Y, P, model_family="l2_logistic_regression", raw_logits=Z, **kwargs
    )


@pytest.mark.parametrize("metadata", [
    {"success": False, "status": 1},
    {"success": True, "status": 1},
    {"success": False, "status": 0},
    {"status": 0},
    {"success": True},
    {"success": "true", "status": 0},
    {"success": 1, "status": 0},
    {"success": True, "status": False},
    {"success": True, "status": 0.0},
])
def test_optimizer_failure_is_not_fitted(monkeypatch, metadata):
    result = SimpleNamespace(x=np.array([0.2, 1.3]), **metadata)
    monkeypatch.setattr(calibration, "minimize", lambda *a, **k: result)
    with pytest.raises(CalibrationIntegrityError) as caught:
        _fit()
    assert caught.value.code == "calibration_optimizer_failed"


@pytest.mark.parametrize("params", [
    None, np.array(0.5), np.array([1.0]), np.array([0., 1., 2.]),
    np.array([[0., 1.]]), np.array([np.nan, 1.]), np.array([0., np.inf]),
    np.array([-np.inf, 1.]), np.array([0., -1.]), np.array([0., 0.]),
    np.array([0., np.nextafter(0.01, -np.inf)]),
    np.array([np.nextafter(15., np.inf), 1.]),
    np.array([np.nextafter(-15., -np.inf), 1.]),
    np.array([0., np.nextafter(15., np.inf)]),
    np.array(["0", "1"]), np.array([True, True]), np.array([0j, 1j]),
    (False, 1.), (10**1000, 1.),
])
def test_invalid_fitted_parameters_are_not_substituted(monkeypatch, params):
    result = SimpleNamespace(success=True, status=0, x=params)
    monkeypatch.setattr(calibration, "minimize", lambda *a, **k: result)
    with pytest.raises(CalibrationIntegrityError) as caught:
        _fit()
    assert caught.value.code == "invalid_fitted_calibration_parameters"


def test_missing_optimizer_parameters_are_rejected(monkeypatch):
    result = SimpleNamespace(success=True, status=0)
    monkeypatch.setattr(calibration, "minimize", lambda *a, **k: result)
    with pytest.raises(CalibrationIntegrityError) as caught:
        _fit()
    assert caught.value.code == "invalid_fitted_calibration_parameters"


@pytest.mark.parametrize("params", [(float("nan"), 1.), (0., -1.), (0., 0.), (16., 1.)])
def test_deterministic_result_does_not_bypass_parameter_guard(monkeypatch, params):
    monkeypatch.setattr(calibration, "deterministic_logistic_fit", lambda *a, **k: params)
    with pytest.raises(CalibrationIntegrityError) as caught:
        _fit(solver=calibration.DETERMINISTIC_CALIBRATION_SOLVER)
    assert caught.value.code == "invalid_fitted_calibration_parameters"


@pytest.mark.parametrize("params", [(-15., .01), (15., 15.), (-0., 1.)])
def test_exact_valid_bounds_and_values_preserved(monkeypatch, params):
    result = SimpleNamespace(success=np.bool_(True), status=np.int64(0), x=np.array(params))
    monkeypatch.setattr(calibration, "minimize", lambda *a, **k: result)
    fit = _fit()
    assert fit.status == "FITTED_OOF_MONOTONE_LOGISTIC"
    assert fit.intercept.hex() == float(params[0]).hex()
    assert fit.slope.hex() == float(params[1]).hex()


def test_valid_deterministic_result_preserved(monkeypatch):
    monkeypatch.setattr(calibration, "deterministic_logistic_fit", lambda *a, **k: (-0., 1.25))
    fit = _fit(solver=calibration.DETERMINISTIC_CALIBRATION_SOLVER)
    assert fit.intercept.hex() == (-0.).hex()
    assert fit.slope.hex() == (1.25).hex()
    assert fit.solver == calibration.DETERMINISTIC_CALIBRATION_SOLVER


@pytest.mark.parametrize("linear", [True, False])
def test_real_successful_optimizer_path_preserves_arithmetic(monkeypatch, linear):
    observed = []

    def observe(*args, **kwargs):
        assert set(kwargs) == {"x0", "jac", "method", "bounds"}
        assert kwargs["method"] == "L-BFGS-B"
        assert kwargs["bounds"] == [(-15., 15.), (.01, 15.)]
        assert np.array_equal(kwargs["x0"], np.array([0., 1.]))
        result = real_minimize(*args, **kwargs)
        assert result.success and result.status == 0
        observed.append(result.x.copy())
        return result

    monkeypatch.setattr(calibration, "minimize", observe)
    fit = calibration.OofLogisticCalibrator.fit_from_oof(
        Y, P, model_family="l2_logistic_regression" if linear else "constrained_random_forest",
        raw_logits=Z if linear else None,
    )
    assert len(observed) == 1
    a, b = map(float, observed[0])
    assert fit.intercept.hex() == a.hex()
    assert fit.slope.hex() == b.hex()
    logits = Z if linear else calibration.safe_clipped_logit(P)
    expected = float(brier_score_loss(Y.astype(np.int64), expit(a + b * logits)))
    assert fit.oof_brier_after.hex() == expected.hex()
    assert fit.status == "FITTED_OOF_MONOTONE_LOGISTIC"


@pytest.mark.parametrize("family", ["prevalence_dummy", "l2_logistic_regression"])
def test_intentional_constant_fallback_unchanged(monkeypatch, family):
    def must_not_run(*args, **kwargs):
        pytest.fail("constant fallback must not call optimizer")
    monkeypatch.setattr(calibration, "minimize", must_not_run)
    fit = calibration.OofLogisticCalibrator.fit_from_oof(
        Y, np.full_like(P, .5), model_family=family
    )
    assert fit.status == "IDENTITY_CONSTANT_FALLBACK"
    assert fit.solver == "none"
    assert fit.slope == 0.
    assert fit.n_oof_samples == len(Y)
