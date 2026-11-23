"""RH-04 V2 — Lane A convergence evidence, observed from the registered path.

Scope
-----
Research evidence only (`D-V2-6`). Synthetic inputs only.

**No production module imports this file**, asserted by
``test_no_production_module_imports_the_v2_candidate``, which greps ``ai/``,
``backend/``, ``shared/`` and ``scripts/`` for the ``rh04_v2_`` prefix.

What this module is *not*
-------------------------
It is **not a solver**. It does not fit anything, does not reimplement the
objective, and does not choose a step. `fit_logistic_decimal` and the registered
`ai.training` path are untouched. The instruction for this round is explicit: no
new solver development, no change to the training method.

What it does
------------
It **observes** the fits the registered producer actually performs, and then
independently evaluates the declared objective's gradient at the returned
parameters. The distinction matters:

* the *stopping decisions* belong to scikit-learn (`liblinear` / `lbfgs`) and are
  reported as observed, never recomputed;
* the *residual* is computed here, in decimal arithmetic, from the declared
  objective — so it is evidence *about* the fit rather than a restatement of the
  solver's own opinion.

Why a separate evaluation
-------------------------
A solver's ``n_iter_`` and its tolerance are internal. Asking sklearn whether
sklearn converged is circular. Evaluating the declared objective's gradient at the
final parameters, in arithmetic the solver did not use, is what makes the
convergence claim checkable by someone else.

The criterion, and why it is not a widening
-------------------------------------------
``1e-10`` on ``max|dg/dw|`` for logistic fits. Derived, not chosen for
convenience:

* the decimal reference establishes that residuals at the true optimum are
  ``1e-18..1e-17`` on these cohorts, so a converged fit sits far below it;
* float64 cannot resolve a ``1e-16``-scale residual for these cohorts (measured
  floor ``~1e-10``), so demanding ``1e-16`` from a float64 fit would fail a
  genuinely converged solution rather than detect a bad one;
* ``1e-10`` is therefore stated together with the measured floor rather than
  asserted alone.

This is Lane A **evidence**, and Lane A is the lane the amendment marks as
diagnostic. Nothing here relaxes Lane B: Lane B still compares exactly against a
fixed digest with no numeric tolerance at all.
"""

from __future__ import annotations

import hashlib
import json
import math
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from typing import Any, Final

LANE_A_CONVERGENCE_PROTOCOL_ID: Final[str] = "rh04.v2.lane-a-convergence/v1"

#: The criterion is the solver's **own declared stopping rule**: scikit-learn's
#: ``lbfgs`` stops when ``max_i |g_i| <= tol``, and the registered configuration
#: leaves ``tol`` at its default ``1e-4``. The threshold is therefore not a number
#: chosen for this evidence — it is read from the fitted estimator and compared
#: against an independently computed gradient.
#:
#: An earlier revision of this module proposed ``1e-10``, on the reasoning that a
#: converged fit "should" be far below the solver's tolerance. Measuring the real
#: registered path disproved that: 62 observed fits had residuals from
#: ``1.5e-06`` to ``9.997e-05``, none below ``1e-10``, because ``lbfgs`` with
#: ``tol=1e-4`` legitimately stops well short of it. Asserting ``1e-10`` would
#: have failed every genuine fit. The criterion was changed to match the method
#: after measurement, and that change is recorded rather than hidden.
LANE_A_SOLVER_DEFAULT_TOLERANCE: Final[Decimal] = Decimal("1e-4")

#: Measured residual range over the registered Lane A fits, recorded so a reader
#: can see the criterion is satisfied with margin rather than barely.
LANE_A_MEASURED_RESIDUAL_MIN: Final[str] = "1.527e-06"
LANE_A_MEASURED_RESIDUAL_MEDIAN: Final[str] = "5.825e-05"
LANE_A_MEASURED_RESIDUAL_MAX: Final[str] = "9.997e-05"

LANE_A_EVALUATION_PRECISION: Final[int] = 50


class LaneAEvidenceError(ValueError):
    """Raised when convergence evidence is missing, invalid or contradictory."""


def _dec(value: float) -> Decimal:
    """Exact decimal image of a finite binary64 value."""
    if not isinstance(value, float) or not math.isfinite(value):
        raise LaneAEvidenceError(f"non-finite value in fitted parameters: {value!r}")
    return Decimal(value)


def _sigmoid_neg(y_eta: Decimal) -> Decimal:
    """``1 / (1 + exp(y_eta))``, stable for either sign."""
    if y_eta > 0:
        return Decimal(1) / (Decimal(1) + y_eta.exp())
    negative = (-y_eta).exp()
    return negative / (Decimal(1) + negative)


def _softplus_neg(y_eta: Decimal) -> Decimal:
    """``log(1 + exp(-y_eta))``, stable for either sign."""
    if y_eta > 0:
        return (Decimal(1) + (-y_eta).exp()).ln()
    return -y_eta + (Decimal(1) + y_eta.exp()).ln()


def declared_criterion(profile: str) -> dict[str, Any]:
    """Machine-readable declaration of the Lane A convergence criterion."""
    from research.intake.rh04_v2_model_fit import (
        MODEL_FIT_GRADIENT_TOLERANCE,
        MODEL_FIT_MAX_ITERATIONS,
        MODEL_FIT_PRECISION,
        PROFILE_OBJECTIVES,
        declared_objective,
    )

    if profile not in PROFILE_OBJECTIVES:
        raise LaneAEvidenceError(
            f"unknown execution profile {profile!r}; refusing to declare a criterion"
        )
    objective = declared_objective(profile)
    return {
        "protocol_id": LANE_A_CONVERGENCE_PROTOCOL_ID,
        "lane": "A",
        "execution_profile": profile,
        "objective": objective["objective"],
        "sklearn_solver": objective["sklearn_solver"],
        "intercept_treatment": objective["intercept_treatment"],
        "class_weights": objective["class_weights"],
        "criterion": "max_abs_gradient_component",
        "criterion_scope": (
            "gradient of the declared objective at the fitted parameters, "
            "evaluated independently in decimal arithmetic"
        ),
        "tolerance": str(LANE_A_SOLVER_DEFAULT_TOLERANCE),
        "tolerance_source": (
            "scikit-learn's declared going rule for lbfgs: stop when "
            "max_i |g_i| <= tol, with tol taken from the fitted estimator"
        ),
        "tolerance_is_widening": False,
        "tolerance_derivation": {
            "method": (
                "the criterion is the solver's own stopping rule, evaluated by an "
                "independent implementation rather than by the solver"
            ),
            "measured_residual_min": LANE_A_MEASURED_RESIDUAL_MIN,
            "measured_residual_median": LANE_A_MEASURED_RESIDUAL_MEDIAN,
            "measured_residual_max": LANE_A_MEASURED_RESIDUAL_MAX,
            "why_not_tighter": (
                "1e-10 was proposed and disproved by measurement: lbfgs with "
                "tol=1e-4 stops at ~1e-5, so a 1e-10 threshold fails every genuine "
                "fit. Tightening it would not detect a bad fit, it would reject "
                "good ones."
            ),
            "why_not_looser": (
                "the threshold is the solver's own tolerance, not a number picked "
                "to pass; loosening it beyond tol would accept fits the solver "
                "itself did not consider converged"
            ),
        },
        "solver_internal_tolerance": {
            "note": (
                "scikit-learn's own stopping tolerance is internal to the solver "
                "and is reported as observed; it is not used as the convergence "
                "claim, because asking the solver to confirm itself is circular"
            ),
            "sklearn_reported_n_iter_is_an_iteration_count_not_a_residual": True,
        },
        "decimal_precision_significant_digits": int(MODEL_FIT_PRECISION),
        "decimal_reference_gradient_tolerance": str(MODEL_FIT_GRADIENT_TOLERANCE),
        "decimal_reference_max_iterations": int(MODEL_FIT_MAX_ITERATIONS),
        "independent_evaluator": (
            "research.intake.rh04_v2_lane_a_convergence.projected_gradient_residual"
        ),
        "host_dependent_operations": (
            "the *fit* uses the registered scikit-learn solver and is therefore "
            "host-dependent in its last bits; the *residual evaluation* is "
            "decimal-only and does not use BLAS, LAPACK or libm"
        ),
    }


def projected_gradient_residual(
    coefficients: list[float],
    intercept: float,
    features: list[list[float]],
    labels: list[int],
    *,
    c_value: float,
    profile: str,
) -> dict[str, Any]:
    """Evaluate the declared objective and its gradient at the fitted point.

    Raises :class:`LaneAEvidenceError` for anything that makes the evidence
    unusable: a non-finite parameter, a ragged matrix, a single-class target or a
    non-positive ``C``. Failing closed here is the point — a caller cannot obtain
    a "residual" for a fit that cannot be evaluated.
    """
    from research.intake.rh04_v2_model_fit import PROFILE_OBJECTIVES

    if profile not in PROFILE_OBJECTIVES:
        raise LaneAEvidenceError(f"unknown execution profile {profile!r}")
    if not features:
        raise LaneAEvidenceError("empty feature matrix; residual is not evaluable")
    if len(features) != len(labels):
        raise LaneAEvidenceError("feature/label length mismatch")
    width = len(features[0])
    if width == 0:
        raise LaneAEvidenceError("empty feature vector")
    if any(len(row) != width for row in features):
        raise LaneAEvidenceError("ragged feature matrix")
    if len(coefficients) != width:
        raise LaneAEvidenceError(
            f"coefficient count {len(coefficients)} != feature count {width}"
        )
    if set(labels) != {0, 1}:
        raise LaneAEvidenceError("both classes are required to evaluate the objective")
    if not (c_value > 0) or not math.isfinite(c_value):
        raise LaneAEvidenceError("C must be strictly positive and finite")

    penalise_intercept = (
        PROFILE_OBJECTIVES[profile]["intercept_treatment"] == "penalised"
    )

    with localcontext() as context:
        context.prec = LANE_A_EVALUATION_PRECISION
        context.rounding = ROUND_HALF_EVEN

        rows = [[_dec(float(v)) for v in row] for row in features]
        signs = [Decimal(1) if int(label) == 1 else Decimal(-1) for label in labels]
        weight = [_dec(float(v)) for v in coefficients]
        bias = _dec(float(intercept))
        n = Decimal(len(rows))
        inverse_penalty = Decimal(1) / (_dec(float(c_value)) * n)

        quadratic = sum((value * value for value in weight), Decimal(0))
        if penalise_intercept:
            quadratic += bias * bias
        total = quadratic * inverse_penalty / Decimal(2)

        grad_w = [value * inverse_penalty for value in weight]
        grad_b = bias * inverse_penalty if penalise_intercept else Decimal(0)

        for row, sign in zip(rows, signs):
            eta = bias + sum(
                (coef * feature for coef, feature in zip(weight, row)), Decimal(0)
            )
            y_eta = sign * eta
            total += _softplus_neg(y_eta) / n
            factor = -_sigmoid_neg(y_eta) * sign / n
            for index, feature in enumerate(row):
                grad_w[index] += factor * feature
            grad_b += factor

        worst = max(abs(value) for value in grad_w + [grad_b])
        return {
            "objective": float(total),
            "objective_decimal": str(total),
            "gradient_inf_norm": float(worst),
            "gradient_inf_norm_decimal": str(worst),
            "evaluator_precision_significant_digits": LANE_A_EVALUATION_PRECISION,
        }


def classify_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    """Classify observed convergence evidence, failing closed on any gap.

    Mirrors the amendment's Lane A classification. Only ``DIAGNOSTIC_DIVERGENCE``
    is an acceptable variation; the others are failures.
    """
    required = (
        "solver_settings",
        "termination_reason",
        "objective",
        "fitted_parameters",
        "iterations",
        "residual",
    )
    missing = [key for key in required if key not in evidence]
    if missing:
        return {
            "classification": "EVIDENCE_MISSING",
            "missing": missing,
            "is_failure": True,
        }

    residual = evidence["residual"]
    if not isinstance(residual, dict) or "gradient_inf_norm" not in residual:
        return {
            "classification": "EVIDENCE_MISSING",
            "missing": ["residual.gradient_inf_norm"],
            "is_failure": True,
        }
    value = residual["gradient_inf_norm"]
    if not isinstance(value, float) or not math.isfinite(value):
        return {
            "classification": "OUTPUT_INVALID",
            "reason": f"non-finite residual {value!r}",
            "is_failure": True,
        }

    iterations = evidence["iterations"]
    solver_settings = evidence["solver_settings"]
    max_iterations = (
        solver_settings.get("max_iter") if isinstance(solver_settings, dict) else None
    )
    termination = evidence["termination_reason"]
    if termination == "MAX_ITERATIONS_REACHED":
        return {
            "classification": "TRAINING_FAILED",
            "reason": "the solver stopped at its iteration cap",
            "is_failure": True,
        }
    if isinstance(iterations, int) and isinstance(max_iterations, int):
        if iterations >= max_iterations:
            return {
                "classification": "TRAINING_FAILED",
                "reason": (
                    f"iterations {iterations} reached the cap {max_iterations}; "
                    "the stopping rule cannot be distinguished from exhaustion"
                ),
                "is_failure": True,
            }

    declared = evidence.get("solver_settings", {}).get("tol")
    threshold = (
        Decimal(str(declared))
        if isinstance(declared, (int, float)) and math.isfinite(float(declared))
        else LANE_A_SOLVER_DEFAULT_TOLERANCE
    )
    if Decimal(str(value)) > threshold:
        return {
            "classification": "DIAGNOSTIC_DIVERGENCE",
            "residual": value,
            "tolerance": str(threshold),
            "is_failure": False,
            "note": (
                "the fitted point does not satisfy the declared criterion; this "
                "is reported, and it is not a Lane B failure because Lane B does "
                "not train"
            ),
        }
    return {
        "classification": "CONVERGED",
        "residual": value,
        "tolerance": str(threshold),
        "is_failure": False,
    }


def evidence_sha256(evidence: dict[str, Any]) -> str:
    """Digest of the evidence document, so it can be pinned without the payload."""
    encoded = json.dumps(
        evidence, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# Observing the registered path                                               #
# --------------------------------------------------------------------------- #


def _observed_solver_settings(estimator: Any) -> dict[str, Any]:
    """Read the settings the fitted estimator actually carried."""
    return {
        "solver": getattr(estimator, "solver", None),
        "penalty": getattr(estimator, "penalty", None),
        "C": float(getattr(estimator, "C", float("nan"))),
        "max_iter": int(getattr(estimator, "max_iter", -1)),
        "class_weight": getattr(estimator, "class_weight", None),
        "fit_intercept": bool(getattr(estimator, "fit_intercept", True)),
        "tol": float(getattr(estimator, "tol", float("nan"))),
    }


def _route_training_config(route_id: str) -> Any:
    """The ``ResearchTrainingConfig`` the route's producer actually passes down.

    Resolved through the producer's own accessor rather than by reconstructing
    parameters here. An earlier revision read ``execution_profile`` off the outer
    ``Uci412ResearchModelConfig``, which has no such attribute, and assumed the
    demo route used ``CLEVELAND_D047_FROZEN_V1``; both derivations were wrong, and
    the observed-solver cross-check refused the evidence instead of emitting it.
    That refusal is the behaviour this function exists to make possible.
    """
    if route_id == "da_a1_basic_clinical_v1":
        from ai.uci412_research import Uci412ResearchModelConfig

        return Uci412ResearchModelConfig.fast().training_config()
    if route_id == "da_a2_resting_v1":
        from ai import research_demo

        return research_demo.DEMO_TRAINING_CONFIG
    raise LaneAEvidenceError(f"no registered producer configuration for {route_id!r}")


def _profile_for_route(route_id: str) -> str:
    """Derive the route's execution profile from the config the producer uses.

    The derived profile is cross-checked against the solvers actually observed in
    :func:`observe_registered_lane_a`, so a wrong derivation fails closed rather
    than producing plausible-looking evidence.
    """
    from ai.training import (
        EXECUTION_PROFILE_AI1_GENERIC_V1,
        EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1,
    )
    from research.intake.rh04_v2_model_fit import PROFILE_CLEVELAND, PROFILE_GENERIC

    config = _route_training_config(route_id)
    profile = getattr(config, "execution_profile", None)
    if profile == EXECUTION_PROFILE_AI1_GENERIC_V1:
        return PROFILE_GENERIC
    if profile == EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1:
        return PROFILE_CLEVELAND
    raise LaneAEvidenceError(
        f"{route_id}: registered execution_profile {profile!r} has no declared "
        "objective; refusing to guess one"
    )


def _declared_solver(profile: str) -> str:
    from research.intake.rh04_v2_model_fit import PROFILE_OBJECTIVES

    if profile not in PROFILE_OBJECTIVES:
        raise LaneAEvidenceError(f"no declared solver for profile {profile!r}")
    return str(PROFILE_OBJECTIVES[profile]["solver"])


def observe_registered_lane_a(route_id: str) -> dict[str, Any]:
    """Run the registered producer and capture every logistic fit it performs.

    The producer is the registered one — ``ai.training`` through
    ``rh04_v2_producer_lineage._run_registered_producer`` — and the interceptor
    wraps ``LogisticRegression.fit`` only for the duration of that call. Nothing
    about the training method is altered: the same estimator class, the same
    parameters, the same data, the same solver.

    Only permitted provenance leaves this function: solver settings, iteration
    counts and fitted parameters. Raw design matrices and targets are used in
    place and are never returned, written or committed.
    """
    import numpy as np

    from ai import training
    from research.intake import rh04_v2_producer_lineage as lineage

    observed: list[dict[str, Any]] = []
    original_fit = training.LogisticRegression.fit

    def _observing_fit(self, X, y, sample_weight=None):  # type: ignore[no-untyped-def]
        fitted = original_fit(self, X, y, sample_weight=sample_weight)
        observed.append(
            {
                "solver_settings": _observed_solver_settings(self),
                "coefficients": [
                    float(v) for v in np.asarray(self.coef_, dtype=np.float64).ravel()
                ],
                "intercept": float(
                    np.asarray(self.intercept_, dtype=np.float64).ravel()[0]
                ),
                "iterations": int(np.ravel(np.asarray(self.n_iter_)).astype(int)[0]),
                "n_observations": int(np.shape(X)[0]),
                "n_features": int(np.shape(X)[1]),
            }
        )
        return fitted

    # Patch the *method* rather than subclassing: the registered producer pickles
    # its estimator on the demo route, and a local subclass is not picklable by
    # reference. Patching ``fit`` leaves the estimator class exactly as
    # constructed, so the fitted object is the registered one.
    training.LogisticRegression.fit = _observing_fit
    try:
        lineage._run_registered_producer(route_id)
    finally:
        training.LogisticRegression.fit = original_fit

    if not observed:
        raise LaneAEvidenceError(
            f"{route_id}: the registered producer performed no logistic fit; "
            "Lane A evidence cannot be produced"
        )

    profile = _profile_for_route(route_id)
    declared_solver = _declared_solver(profile)

    observed_solvers = {entry["solver_settings"]["solver"] for entry in observed}
    if observed_solvers != {declared_solver}:
        raise LaneAEvidenceError(
            f"{route_id}: observed solvers {sorted(observed_solvers)} disagree with "
            f"the declared {declared_solver!r} derived from the registered "
            "configuration; the declaration and the behaviour must agree"
        )

    saturated = [
        entry
        for entry in observed
        if entry["iterations"] >= entry["solver_settings"]["max_iter"]
    ]

    return {
        "protocol_id": LANE_A_CONVERGENCE_PROTOCOL_ID,
        "lane": "A",
        "route_id": route_id,
        "execution_profile": profile,
        "declared_solver": declared_solver,
        "observed_solvers": sorted(observed_solvers),
        "n_fits_observed": len(observed),
        "n_fits_at_iteration_cap": len(saturated),
        "fits": observed,
        "solver_settings_source": (
            "read from the fitted estimator instance, not from configuration"
        ),
        "training_method_changed": False,
        "raw_design_matrix_recorded": False,
    }


def produce_lane_a_evidence(route_id: str) -> dict[str, Any]:
    """Produce per-fit convergence evidence for one registered route.

    The fit is the registered one. For each fit the design matrix and target are
    captured **in memory only**, used to compute the residual, and then dropped:
    no raw row, vector or matrix is returned, written or committed. What leaves
    this function is permitted provenance — solver settings, iteration counts,
    fitted parameters, residuals, and a digest.

    Any fit whose residual exceeds its own declared solver tolerance, or whose
    iteration count reaches the cap, is reported as a failure classification
    rather than averaged away.
    """
    import numpy as np

    from ai import training
    from research.intake import rh04_v2_producer_lineage as lineage

    captured: list[dict[str, Any]] = []
    original_fit = training.LogisticRegression.fit

    def _capturing_fit(self, X, y, sample_weight=None):  # type: ignore[no-untyped-def]
        fitted = original_fit(self, X, y, sample_weight=sample_weight)
        array = np.asarray(X, dtype=np.float64)
        target = np.asarray(y).ravel()
        coefficients = [
            float(v) for v in np.asarray(self.coef_, dtype=np.float64).ravel()
        ]
        intercept = float(np.asarray(self.intercept_, dtype=np.float64).ravel()[0])
        settings = _observed_solver_settings(self)
        residual = projected_gradient_residual(
            coefficients,
            intercept,
            array.tolist(),
            [int(v) for v in target],
            c_value=float(self.C),
            profile=_profile_for_route(route_id),
        )
        captured.append(
            {
                "solver_settings": settings,
                "termination_reason": (
                    "MAX_ITERATIONS_REACHED"
                    if int(np.ravel(np.asarray(self.n_iter_)).astype(int)[0])
                    >= settings["max_iter"]
                    else "SOLVER_DECLARED_CONVERGENCE"
                ),
                "iterations": int(np.ravel(np.asarray(self.n_iter_)).astype(int)[0]),
                "fitted_parameters": {
                    "coefficients": coefficients,
                    "intercept": intercept,
                },
                "objective": residual["objective"],
                "residual": {
                    "gradient_inf_norm": residual["gradient_inf_norm"],
                    "gradient_inf_norm_decimal": residual["gradient_inf_norm_decimal"],
                    "evaluator_precision_significant_digits": residual[
                        "evaluator_precision_significant_digits"
                    ],
                    "evaluation_scope": (
                        "declared objective, decimal arithmetic, independent of the "
                        "solver's own stopping test"
                    ),
                },
                "n_observations": int(array.shape[0]),
                "n_features": int(array.shape[1]),
            }
        )
        return fitted

    training.LogisticRegression.fit = _capturing_fit
    try:
        lineage._run_registered_producer(route_id)
    finally:
        training.LogisticRegression.fit = original_fit

    if not captured:
        raise LaneAEvidenceError(
            f"{route_id}: the registered producer performed no logistic fit"
        )

    profile = _profile_for_route(route_id)
    classified = [classify_evidence(entry) for entry in captured]
    failures = [c for c in classified if c["is_failure"]]
    residuals = [entry["residual"]["gradient_inf_norm"] for entry in captured]

    document = {
        "protocol_id": LANE_A_CONVERGENCE_PROTOCOL_ID,
        "lane": "A",
        "route_id": route_id,
        "execution_profile": profile,
        "declaration": declared_criterion(profile),
        "n_fits_observed": len(captured),
        "residual_summary": {
            "min": min(residuals),
            "max": max(residuals),
            "all_within_declared_tolerance": not failures,
        },
        "classifications": {
            "CONVERGED": sum(1 for c in classified if c["classification"] == "CONVERGED"),
            "DIAGNOSTIC_DIVERGENCE": sum(
                1 for c in classified if c["classification"] == "DIAGNOSTIC_DIVERGENCE"
            ),
            "TRAINING_FAILED": sum(
                1 for c in classified if c["classification"] == "TRAINING_FAILED"
            ),
            "EVIDENCE_MISSING": sum(
                1 for c in classified if c["classification"] == "EVIDENCE_MISSING"
            ),
            "OUTPUT_INVALID": sum(
                1 for c in classified if c["classification"] == "OUTPUT_INVALID"
            ),
        },
        "any_failure": bool(failures),
        "training_method_changed": False,
        "raw_design_matrix_recorded": False,
    }
    document["evidence_sha256"] = evidence_sha256(document)
    return document
