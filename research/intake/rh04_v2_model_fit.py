"""RH-04 V2 — deterministic model-fitting candidate (synthetic only).

Scope
-----
Isolated candidate development (`D-V2-6`). Synthetic inputs only. **No production
code imports this module**; a test enforces that. It does not touch the frozen V1
fixture, the default solver, or production inference.

Why this exists
---------------
Stage S1 is the only remaining source of host dependence in the V2 pack
(`RH04_V2_DETERMINISTIC_UPSTREAM_2026_11_21.md`): sklearn's L-BFGS-B moves 11 of
12 coefficients between kernels. Everything downstream of the coefficients is a
deterministic function of them.

The declared objective
----------------------
The pinned configuration (`ai/training.py`) is
``LogisticRegression(penalty="l2", solver="liblinear", C in (0.01,0.1,1,10),
class_weight=None, random_state=seed)`` with the default ``fit_intercept=True``.
The objective below was **measured**, not assumed: probing the pinned
scikit-learn 1.6.1 at three tolerances shows the gradient of

    J(w, b) = 0.5 * w'w / (C * n)
              + (1/n) * sum_i log(1 + exp(-y_i * (w'x_i + b)))
              + 0.5 * b^2 / (C * n)

falling with ``tol`` (2.82e-06 at tol=1e-4, then 1.48e-08 and flat), which is
liblinear's stopping criterion, not a wrong objective. The intercept term is
**penalised** — including it is what makes the gradient vanish; omitting it
leaves a persistent 6.4e-04 residual. This is the opposite of the calibration
objective in `ai/calibration.py`, which uses a different normalisation and an
anchor at slope 1. They are deliberately separate declarations.

Why decimal Newton
------------------
Same argument as the calibration reference: a float64 stopping rule cannot be
both reachable and meaningful, so the criterion is evaluated in software-declared
decimal arithmetic and is reachable by construction.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from typing import Final, Sequence

MODEL_FIT_PROTOCOL_ID: Final[str] = "rh04.v2.decimal-model-fit/v2"

#: The two registered execution profiles. They do **not** share an objective:
#: ``ai/training.py::_build_estimator`` selects ``liblinear`` for the frozen
#: Cleveland profile and ``lbfgs`` for the generic one, and only liblinear
#: penalises the intercept. Measured on the pinned wheel set: lbfgs leaves a
#: persistent |g_b| = 7.157e-04 if the intercept is penalised, versus 9.160e-09
#: when it is not.
PROFILE_CLEVELAND: Final[str] = "CLEVELAND_D047_FROZEN_V1"
PROFILE_GENERIC: Final[str] = "AI1_GENERIC_V1"

#: Objective declaration per profile. Rejecting an unknown profile is mandatory:
#: silently defaulting would substitute one source's objective for another's.
PROFILE_OBJECTIVES: Final[dict[str, dict[str, object]]] = {
    PROFILE_CLEVELAND: {
        "solver": "liblinear",
        "intercept_treatment": "penalised",
        "regularisation_scaling": "1/(C*n) on slope and intercept",
        "objective": (
            "0.5*||w||^2/(C*n) + mean_i log(1+exp(-y_i(w.x_i+b))) + 0.5*b^2/(C*n)"
        ),
    },
    PROFILE_GENERIC: {
        "solver": "lbfgs",
        "intercept_treatment": "unpenalised",
        "regularisation_scaling": "1/(C*n) on the slope only",
        "objective": (
            "0.5*||w||^2/(C*n) + mean_i log(1+exp(-y_i(w.x_i+b)))"
        ),
    },
}
MODEL_FIT_PRECISION: Final[int] = 50
MODEL_FIT_MAX_ITERATIONS: Final[int] = 200
#: Declared convergence criterion: max |gradient component| of the *exact*
#: objective, evaluated in decimal. Chosen after measuring the achievable floor.
MODEL_FIT_GRADIENT_TOLERANCE: Final[Decimal] = Decimal("1e-24")
#: Levenberg-style damping applied when the Newton system is near-singular.
MODEL_FIT_DAMPING: Final[Decimal] = Decimal("1e-18")


class ModelFitError(ValueError):
    """Fail-closed refusal. Never returns a partial or unverified fit."""


def declared_objective(profile: str = PROFILE_CLEVELAND) -> dict[str, object]:
    """Machine-readable declaration for one execution profile."""
    if profile not in PROFILE_OBJECTIVES:
        raise ModelFitError(
            f"unknown execution profile {profile!r}; refusing to guess an objective"
        )
    objective = PROFILE_OBJECTIVES[profile]
    return {
        "protocol_id": MODEL_FIT_PROTOCOL_ID,
        "execution_profile": profile,
        "objective": objective["objective"],
        "loss_normalisation": "mean over n samples",
        "regularisation_scaling": objective["regularisation_scaling"],
        "intercept_treatment": objective["intercept_treatment"],
        "sklearn_solver": objective["solver"],
        "class_weights": "none (class_weight=None in the pinned configuration)",
        "class_ordering": "positive class is 1; y in {-1,+1} internally",
        "feature_representation": "dense binary64, used exactly as given (no scaling)",
        "class_weights": "none (class_weight=None in both profiles)",
        "sample_weights": "unsupported; refused rather than silently ignored",
        "class_ordering": "positive class is 1; y in {-1,+1} internally",
        "feature_representation": "dense binary64, used exactly as given (no scaling)",
        "initialisation": "w=0, b=0",
        "convergence_criterion": (
            "max|grad| <= 1e-24 on the declared decimal objective"
        ),
        "precision": MODEL_FIT_PRECISION,
        "final_rounding": "single round-half-even to binary64 per parameter",
        "host_dependent_operations": "none (no BLAS, no libm, no LAPACK)",
        "solver": "Newton with Gaussian elimination on Decimal entries",
        "note": (
            "the Newton iteration is finite-precision Decimal, not exact "
            "arithmetic; 'exact' here refers to the criterion being evaluated in "
            "software arithmetic rather than to a proof of exactness"
        ),
    }


def _dec(value: float) -> Decimal:
    """Exact decimal image of a finite binary64.

    ``Decimal(float)`` is exact; ``Decimal(str(x))`` would round to the shortest
    repr and would not be the same number.
    """
    if value != value or value in (float("inf"), float("-inf")):
        raise ModelFitError("non-finite value in a declared exact computation")
    return Decimal(value)


def _sigmoid_neg(y_eta: Decimal) -> Decimal:
    """``sigmoid(-y_eta) = 1 / (1 + exp(y_eta))``, overflow-safe for either sign.

    An earlier revision had these two branches swapped, returning
    ``sigmoid(+y_eta)`` for positive arguments. The objective was unaffected (it
    uses ``_softplus_neg``), so the function appeared to converge while the
    gradient was wrong by a factor of ~n and the iteration stalled at 2.17e-01.
    """
    if y_eta > 0:
        # exp(-y_eta) is the small, safe quantity here.
        expo = _exp(-y_eta)
        return expo / (Decimal(1) + expo)
    return Decimal(1) / (Decimal(1) + _exp(y_eta))


def _exp(value: Decimal) -> Decimal:
    """Decimal exponential, keeping the operation in software arithmetic."""
    return value.exp()


def _objective_and_gradient(
    w: Sequence[Decimal],
    b: Decimal,
    rows: Sequence[Sequence[Decimal]],
    signs: Sequence[Decimal],
    inverse_penalty: Decimal,
    penalise_intercept: bool = True,
) -> tuple[Decimal, list[Decimal], Decimal]:
    """Objective and its gradient at ``(w, b)`` in declared arithmetic."""
    n = Decimal(len(rows))
    quadratic = sum((value * value for value in w), Decimal(0))
    if penalise_intercept:
        quadratic += b * b
    total = quadratic * inverse_penalty / Decimal(2)

    grad_w = [value * inverse_penalty for value in w]
    grad_b = b * inverse_penalty if penalise_intercept else Decimal(0)

    for row, sign in zip(rows, signs):
        eta = b + sum((coef * feature for coef, feature in zip(w, row)), Decimal(0))
        y_eta = sign * eta
        # log(1 + exp(-y_eta)) computed stably
        total += _softplus_neg(y_eta) / n
        # d/d(y_eta) log(1+exp(-y_eta)) = -sigmoid(-y_eta)
        factor = -_sigmoid_neg(y_eta) * sign / n
        for index, feature in enumerate(row):
            grad_w[index] += factor * feature
        grad_b += factor

    return total, grad_w, grad_b


def _softplus_neg(y_eta: Decimal) -> Decimal:
    """``log(1 + exp(-y_eta))``, stable for either sign.

    For ``y_eta > 0`` the argument is small and is summed directly. For
    ``y_eta < 0`` the naive form would overflow, so the identity
    ``log(1 + exp(-u)) = -u + log(1 + exp(u))`` is used instead. (An earlier
    revision wrote ``-u + log(1 + exp(-u))``, which silently produced *negative*
    log-losses; the objective then diverged to -6.18 instead of converging.)
    """
    if y_eta > 0:
        return (Decimal(1) + _exp(-y_eta)).ln()
    return -y_eta + (Decimal(1) + _exp(y_eta)).ln()


def _hessian(
    w: Sequence[Decimal],
    b: Decimal,
    rows: Sequence[Sequence[Decimal]],
    signs: Sequence[Decimal],
    inverse_penalty: Decimal,
    penalise_intercept: bool = True,
) -> list[list[Decimal]]:
    """Hessian of the objective in declared arithmetic."""
    dimension = len(w) + 1
    hessian = [[Decimal(0)] * dimension for _ in range(dimension)]
    hessian[dimension - 1][dimension - 1] = (
        inverse_penalty if penalise_intercept else Decimal(0)
    )
    for index in range(len(w)):
        hessian[index][index] = inverse_penalty

    n = Decimal(len(rows))
    for row, sign in zip(rows, signs):
        design = list(row) + [Decimal(1)]
        eta = b + sum((coef * feature for coef, feature in zip(w, row)), Decimal(0))
        sigmoid = _sigmoid_neg(sign * eta)
        weight = sigmoid * (Decimal(1) - sigmoid) / n
        if weight == 0:
            continue
        for i in range(dimension):
            scaled = weight * design[i]
            for j in range(i, dimension):
                hessian[i][j] += scaled * design[j]
        # mirror
        for i in range(dimension):
            for j in range(i):
                pass
    for i in range(dimension):
        for j in range(i):
            hessian[i][j] = hessian[j][i]
    return hessian


def _solve(matrix: list[list[Decimal]], rhs: list[Decimal]) -> list[Decimal]:
    """Exact Gaussian elimination with partial pivoting on Decimal entries."""
    size = len(rhs)
    augmented = [row[:] + [rhs[index]] for index, row in enumerate(matrix)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda r: abs(augmented[r][column]))
        if augmented[pivot][column] == 0:
            raise ModelFitError("singular normal equations; damping required")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        pivot_value = augmented[column][column]
        for r in range(column + 1, size):
            factor = augmented[r][column] / pivot_value
            if factor == 0:
                continue
            for c in range(column, size + 1):
                augmented[r][c] -= factor * augmented[column][c]
    solution = [Decimal(0)] * size
    for r in range(size - 1, -1, -1):
        total = augmented[r][size]
        for c in range(r + 1, size):
            total -= augmented[r][c] * solution[c]
        solution[r] = total / augmented[r][r]
    return solution


def fit_logistic_decimal(
    features: Sequence[Sequence[float]],
    labels: Sequence[int],
    *,
    c_value: float,
    profile: str = PROFILE_CLEVELAND,
    max_iterations: int = MODEL_FIT_MAX_ITERATIONS,
) -> dict[str, object]:
    """Deterministic L2 logistic fit for one declared profile.

    Fails closed; never returns a partial or unverified fit. An unknown profile
    is refused rather than defaulted, because silently choosing one would
    substitute one source's objective for another's.
    """
    if len(features) != len(labels):
        raise ModelFitError("feature/label length mismatch")
    if len(features) < 2:
        raise ModelFitError("at least two observations are required")
    width = len(features[0])
    if width == 0:
        raise ModelFitError("empty feature vector")
    if any(len(row) != width for row in features):
        raise ModelFitError("ragged feature matrix")
    if set(labels) != {0, 1}:
        raise ModelFitError("both classes are required")
    if profile not in PROFILE_OBJECTIVES:
        raise ModelFitError(
            f"unknown execution profile {profile!r}; refusing to guess an objective"
        )
    if not (c_value > 0) or c_value != c_value or c_value == float("inf"):
        raise ModelFitError("C must be strictly positive and finite")
    penalise_intercept = (
        PROFILE_OBJECTIVES[profile]["intercept_treatment"] == "penalised"
    )

    with localcontext() as context:
        context.prec = MODEL_FIT_PRECISION
        context.rounding = ROUND_HALF_EVEN

        rows = [[_dec(float(value)) for value in row] for row in features]
        signs = [Decimal(1) if int(label) == 1 else Decimal(-1) for label in labels]
        inverse_penalty = Decimal(1) / (_dec(float(c_value)) * Decimal(len(rows)))

        w = [Decimal(0)] * width
        b = Decimal(0)

        for iteration in range(max_iterations):
            objective, grad_w, grad_b = _objective_and_gradient(
                w, b, rows, signs, inverse_penalty, penalise_intercept
            )
            del objective
            worst = max(abs(value) for value in grad_w + [grad_b])
            if worst <= MODEL_FIT_GRADIENT_TOLERANCE:
                parameters = [float(value) for value in w] + [float(b)]
                return {
                    "protocol_id": MODEL_FIT_PROTOCOL_ID,
                    "execution_profile": profile,
                    "coefficients": parameters[:-1],
                    "intercept": parameters[-1],
                    "iterations": iteration,
                    "gradient_inf_norm": _decimal_text(worst),
                    "c_value": float(c_value),
                    "n_samples": len(rows),
                    "n_features": width,
                    "declared": declared_objective(profile),
                }

            hessian = _hessian(w, b, rows, signs, inverse_penalty, penalise_intercept)
            for index in range(len(hessian)):
                hessian[index][index] += MODEL_FIT_DAMPING
            step = _solve(hessian, grad_w + [grad_b])

            # Exact 1-D minimisation along the Newton direction. A value-based
            # Armijo test is deliberately *not* used: at 50 digits a converged
            # step can be smaller than the representable decrease, so a
            # "trial < current" test fails on a step that is already optimal.
            # That failure mode was measured on the calibration reference and is
            # not reintroduced here.
            w, b = _exact_line_minimisation(
                w, b, step, rows, signs, inverse_penalty, penalise_intercept
            )

    raise ModelFitError(
        f"deterministic model fit did not converge in {max_iterations} iterations"
    )


def _exact_line_minimisation(
    w: Sequence[Decimal],
    b: Decimal,
    direction: Sequence[Decimal],
    rows: Sequence[Sequence[Decimal]],
    signs: Sequence[Decimal],
    inverse_penalty: Decimal,
    penalise_intercept: bool = True,
) -> tuple[list[Decimal], Decimal]:
    """Golden-section search for the minimiser along ``direction``.

    Bracket ``[0, -1]`` in the descent sense is normalised so the step is
    ``x - t*direction``. Returns the improved point; never raises on a flat
    direction, because a flat direction means the gradient is already zero.
    """

    def at(t: Decimal) -> tuple[Decimal, list[Decimal], Decimal]:
        trial_w = [value - t * delta for value, delta in zip(w, direction)]
        trial_b = b - t * direction[-1]
        objective, _, _ = _objective_and_gradient(
            trial_w, trial_b, rows, signs, inverse_penalty, penalise_intercept
        )
        return objective, trial_w, trial_b

    inv_phi = (Decimal(5).sqrt() - Decimal(1)) / Decimal(2)
    lower, upper = Decimal(0), Decimal(1)
    c = upper - inv_phi * (upper - lower)
    d = lower + inv_phi * (upper - lower)
    f_c, _, _ = at(c)
    f_d, _, _ = at(d)
    for _ in range(200):
        if f_c < f_d:
            upper, d, f_d = d, c, f_c
            c = upper - inv_phi * (upper - lower)
            f_c, _, _ = at(c)
        else:
            lower, c, f_c = c, d, f_d
            d = lower + inv_phi * (upper - lower)
            f_d, _, _ = at(d)
        if upper - lower <= Decimal("1e-30"):
            break
    t = (lower + upper) / 2
    _, best_w, best_b = at(t)
    return best_w, best_b


def _decimal_text(value: Decimal) -> str:
    """Stable textual form, independent of float formatting."""
    return format(value, "e")
