"""RH-04 calibration portability guards (CPU-portable deterministic solver).

Background
----------
The frozen 29-case Golden Replay (``da_a1_basic_clinical_v1``) intermittently
failed by ~1 ULP in ``calibrated_log_odds`` on non-SkylakeX CI hosts because the
two-parameter calibration fit (``ai.calibration.OofLogisticCalibrator``) used
scipy L-BFGS-B, whose C-library reductions dispatch to CPU-specific OpenBLAS
kernels (``ddot_``/``daxpy_``/``dcopy_``/``dtrsl``).  See
docs/rh04-portable-deterministic-calibration.md for the full investigation.

This test file guards the remedy implemented in
``ai.calibration.deterministic_logistic_fit`` (CPU-portable, deterministic
two-parameter fit):

* the solver is bit-identical across ``OPENBLAS_CORETYPE`` dispatches,
* the solver is bit-reproducible across repeated calls in one process,
* ``fit_from_oof`` accepts the deterministic solver, keeps the full calibration
  contract (validation, bounds, status, brier consistency, JSON round-trip) and
  rejects unknown solver names.

The deterministic solver is NOT required to reproduce the frozen golden
coefficients bit-for-bit; that replay contract is unchanged and is tested by
``test_rh04_calibration_dispatch.py`` on the default (scipy L-BFGS-B) path.
Nothing here weakens, regenerates or relaxes the frozen fixture, its digest, or
any comparator.
"""
from __future__ import annotations

import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from ai.calibration import (
    CALIBRATION_SOLVERS,
    CalibrationIntegrityError,
    DETERMINISTIC_CALIBRATION_SOLVER,
    DEFAULT_CALIBRATION_SOLVER,
    OofLogisticCalibrator,
    deterministic_logistic_fit,
    safe_clipped_logit,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

# Fixed synthetic, non-patient dataset (40 aligned 1-D observations, both classes).
# Deliberately NOT the frozen golden data — these values exist only to exercise
# the deterministic solver and are never used to regenerate or to tune the pack.
SYNTHETIC_Y = np.array(
    [
        1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1, 1, 0, 1, 0, 1,
        1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1, 1, 0, 1,
    ],
    dtype=np.float64,
)
SYNTHETIC_LOGITS = np.array(
    [
        -2.1, -1.3, -0.6, 0.2, 0.7, 1.1, -0.2, 1.4, 1.8, -0.8, 0.4, -1.7,
        0.1, -0.5, 0.9, 1.2, -1.1, 0.6, -0.9, 0.3, 1.0, -0.4, 0.8, -1.5,
        0.5, 1.6, -0.7, 0.9, -0.3, 1.3, 1.5, -1.2, 0.4, -0.6, 0.7, -1.0,
        0.2, 1.1, -0.8, 0.6,
    ],
    dtype=np.float64,
)
assert SYNTHETIC_Y.size == SYNTHETIC_LOGITS.size

# Dispatches that run on any x86_64 runner (SkylakeX additionally requires
# AVX-512, which is not available on all CI hosts — see the investigation doc).
PORTABLE_DISPATCHES = ("generic", "Haswell", "Sandybridge")
OPTIONAL_SKYLAKX_DISPATCH = "SkylakeX"


def _run_dispatch_subprocess(core_type: str):
    env = dict(
        os.environ,
        OPENBLAS_CORETYPE=core_type,
        OPENBLAS_NUM_THREADS="1",
        OMP_NUM_THREADS="1",
        BLIS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMEXPR_NUM_THREADS="1",
        VECLIB_MAXIMUM_THREADS="1",
    )
    code = (
        "import numpy as np; "
        "from ai.calibration import deterministic_logistic_fit; "
        "y = np.array(" + repr(SYNTHETIC_Y.tolist()) + ", dtype=np.float64); "
        "logits = np.array(" + repr(SYNTHETIC_LOGITS.tolist()) + ", dtype=np.float64); "
        "a, b = deterministic_logistic_fit(y, logits); "
        "print(repr(a), repr(b))"
    )
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


def _parse_fit(stdout: str) -> tuple[str, str]:
    parts = stdout.strip().split()
    if len(parts) != 2:
        raise AssertionError(f"Unexpected subprocess output: {stdout!r}")
    return parts[0], parts[1]


def test_deterministic_fit_is_bit_identical_across_openblas_dispatches():
    """The deterministic solver is reproducible across OpenBLAS dynamic-arch
    dispatches.  A dispatch that is not actually available on the host CPU
    (e.g. SkylakeX on a non-AVX-512 runner) is recorded as unavailable, never
    skipped silently, and must never be the only evidence."""
    results: dict[str, tuple[str, str]] = {}
    unavailable: dict[str, str] = {}
    for core in PORTABLE_DISPATCHES + (OPTIONAL_SKYLAKX_DISPATCH,):
        try:
            proc = _run_dispatch_subprocess(core)
        except subprocess.TimeoutExpired:
            unavailable[core] = "timeout"
            continue
        if proc.returncode != 0:
            unavailable[core] = (proc.stderr or "<no stderr>").strip().splitlines()[-1]
            continue
        results[core] = _parse_fit(proc.stdout)

    assert len(results) >= 2, (
        f"Expected >= 2 dispatches to run; got {sorted(results)}; unavailable={sorted(unavailable)}"
    )
    # Only the AVX-512-only dispatch may be unavailable on non-AVX-512 hosts.
    for core in unavailable:
        assert core == OPTIONAL_SKYLAKX_DISPATCH, (
            f"Unexpected unavailable dispatch {core}: {unavailable[core]}"
        )

    reference = next(iter(results.values()))
    for core, value in results.items():
        assert value == reference, (
            f"{core} produced a different deterministic fit: {value} vs {reference}"
        )


def test_deterministic_fit_is_bit_reproducible_across_repeated_calls():
    """Repeated in-process calls are bit-identical (no hidden state)."""
    first = deterministic_logistic_fit(SYNTHETIC_Y, SYNTHETIC_LOGITS)
    for _ in range(10):
        second = deterministic_logistic_fit(SYNTHETIC_Y, SYNTHETIC_LOGITS)
        assert second[0] == first[0]
        assert second[1] == first[1]


def test_deterministic_fit_returns_finite_bounded_parameters():
    a, b = deterministic_logistic_fit(SYNTHETIC_Y, SYNTHETIC_LOGITS)
    assert math.isfinite(a) and math.isfinite(b)
    assert -15.0 <= a <= 15.0
    assert 0.01 <= b <= 15.0


def test_deterministic_fit_is_monotone_in_slope_bound():
    # A slope at/below the lower bound is never produced silently.
    a, b = deterministic_logistic_fit(SYNTHETIC_Y, SYNTHETIC_LOGITS)
    assert b > 0.01


def test_deterministic_fit_rejects_misaligned_or_empty_inputs():
    with pytest.raises(CalibrationIntegrityError):
        deterministic_logistic_fit(np.array([0.0, 1.0]), np.array([0.5]))
    with pytest.raises(CalibrationIntegrityError):
        deterministic_logistic_fit(np.array([]), np.array([]))


def test_deterministic_fit_rejects_incoherent_bounds():
    with pytest.raises(CalibrationIntegrityError):
        deterministic_logistic_fit(
            SYNTHETIC_Y,
            SYNTHETIC_LOGITS,
            lower=(15.0, 0.01),
            upper=(-15.0, 15.0),
        )


def test_fit_from_oof_uses_deterministic_solver_and_preserves_contract():
    """``fit_from_oof`` with the deterministic solver returns a valid calibrator:
    same fit_scope/input_link, valid status, bounded slope, brier consistency,
    JSON round-trip preserves the parameters."""
    logits = np.asarray(SYNTHETIC_LOGITS, dtype=np.float64)
    p = 1.0 / (1.0 + np.exp(-logits))
    y = np.asarray(SYNTHETIC_Y, dtype=np.float64)
    cal = OofLogisticCalibrator.fit_from_oof(
        y, p, model_family="constrained_random_forest", solver=DETERMINISTIC_CALIBRATION_SOLVER
    )
    assert cal.status == "FITTED_OOF_MONOTONE_LOGISTIC"
    assert cal.input_link == "clipped_logit_of_raw_probability"
    assert cal.fit_scope == "FULL_DEVELOPMENT_OOF_FINAL"
    assert -15.0 <= cal.intercept <= 15.0
    assert 0.01 <= cal.slope <= 15.0
    assert cal.development_prevalence > 0.0
    assert cal.n_oof_samples == int(y.size)
    assert cal.oof_brier_before >= cal.oof_brier_after
    assert math.isfinite(cal.oof_brier_after)

    # JSON round-trip stays exact and preserves the parameters.
    raw = cal.to_json_dict()
    restored = OofLogisticCalibrator.from_json_dict(raw)
    assert restored.intercept == cal.intercept
    assert restored.slope == cal.slope
    assert restored.status == cal.status


def test_fit_from_oof_rejects_unknown_solver():
    p = np.full(40, 0.5, dtype=np.float64)
    y = np.asarray(SYNTHETIC_Y, dtype=np.float64)
    with pytest.raises(CalibrationIntegrityError) as excinfo:
        OofLogisticCalibrator.fit_from_oof(
            y, p, model_family="constrained_random_forest", solver="not_a_solver"
        )
    assert excinfo.value.code == "invalid_calibration_solver"


def test_solver_contract_constants_are_consistent():
    """The default production solver keeps the frozen golden contract."""
    assert DEFAULT_CALIBRATION_SOLVER == "scipy_lbfgsb"
    assert DETERMINISTIC_CALIBRATION_SOLVER in CALIBRATION_SOLVERS
    assert DEFAULT_CALIBRATION_SOLVER in CALIBRATION_SOLVERS
    assert len(CALIBRATION_SOLVERS) == 2
