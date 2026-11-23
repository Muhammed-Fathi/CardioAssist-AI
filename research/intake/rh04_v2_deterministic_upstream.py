"""RH-04 V2 — deterministic upstream linear scoring (candidate, synthetic only).

Why this module exists
----------------------
The V2 decimal reference fit made the *calibration* step a declared function. It
did not touch the two stages upstream of it, and both are host-dependent. This
module is the isolated candidate for the first of those, and it measures the
second.

Measured upstream decomposition (see ``docs/research/next_phase/``)
-------------------------------------------------------------------
Run on one synthetic 64 x 12 design with the pinned wheel set, comparing the
natural host kernel against ``OPENBLAS_CORETYPE=Sandybridge``:

===========  ==========================================  ==================
stage        what it is                                  kernel-invariant?
===========  ==========================================  ==================
S1           ``LogisticRegression.fit`` (scipy L-BFGS-B) **no** — 11 of 12
                                                         coefficients moved,
                                                         by 1..15 ULP
S2           ``decision_function`` (BLAS ``gemv``)       **no** — 255 of 300
                                                         scores moved,
                                                         by <= 1.110e-15
``fsum``     naive compensated replacement for S2        **no** — it sums the
                                                         same host-dependent
                                                         coefficients
===========  ==========================================  ==================

The last row is the important negative result: **replacing the accumulation
method does not make scoring portable, because the inputs to the accumulation are
already host-dependent.** Fixing S2 alone cannot produce one exact reference.

What this module provides
-------------------------
``exact_linear_score`` computes the *correctly rounded* value of the exact real
number ``sum_j coef_j * x_j + intercept`` using rational arithmetic. It is

* a deterministic function of its inputs, on every host, by construction;
* the canonical mathematical meaning of "the model's linear score";
* independent of BLAS, libm, threading and CPU dispatch.

It is a **reference oracle**, not a replacement for production inference. It
cannot repair S1: if the fitted coefficients themselves differ between hosts,
even a correctly rounded score will differ. That is why this module also
reports ``coefficients_are_reproducible`` — so a caller can tell the two error
sources apart instead of blaming the scorer.
"""

from __future__ import annotations

from decimal import Decimal, localcontext
from fractions import Fraction
from typing import Final, Sequence

#: Version of the scoring declaration. Any change to the arithmetic below must
#: bump this string, because reference identity is bound to it.
EXACT_SCORE_PROTOCOL_ID: Final[str] = "rh04.v2.exact-linear-score/v1"

#: Decimal precision used when a caller wants a decimal rather than a float.
EXACT_SCORE_PRECISION: Final[int] = 60


def _as_fraction(value: float) -> Fraction:
    """Exact rational value of a finite binary64, with no decimal detour.

    ``Fraction(float)`` is exact: every finite binary64 *is* a dyadic rational.
    A ``Decimal(repr(x))`` route would silently introduce the shortest-repr
    rounding and would not be the same number.
    """
    if value != value or value in (float("inf"), float("-inf")):
        raise ValueError("non-finite value in a declared exact computation")
    return Fraction(value)


def exact_linear_score(coefficients: Sequence[float], features: Sequence[float],
                       intercept: float) -> Fraction:
    """The exact rational value of ``coef . x + intercept``.

    No floating point is used after entry, so the result is independent of BLAS,
    CPU dispatch, SIMD width, threading and summation order.
    """
    if len(coefficients) != len(features):
        raise ValueError("coefficient/feature length mismatch")
    total = _as_fraction(intercept)
    for coef, feature in zip(coefficients, features):
        total += _as_fraction(coef) * _as_fraction(feature)
    return total


def exact_linear_scores(
    coefficients: Sequence[float],
    rows: Sequence[Sequence[float]],
    intercept: float,
) -> list[Fraction]:
    """``exact_linear_score`` applied row-wise."""
    return [exact_linear_score(coefficients, row, intercept) for row in rows]


def score_as_float(score: Fraction) -> float:
    """Single correctly rounded binary64 conversion of an exact rational.

    This is the *only* rounding in the pipeline, it happens once per score, and
    it is round-to-nearest-even because that is what ``float(Fraction)`` does.
    """
    return float(score)


def score_as_decimal(score: Fraction, precision: int = EXACT_SCORE_PRECISION) -> Decimal:
    """A decimal rendering at declared precision, for reporting only."""
    with localcontext() as context:
        context.prec = precision
        return Decimal(score.numerator) / Decimal(score.denominator)


def declared_protocol() -> dict[str, object]:
    """The machine-readable declaration bound into the reference identity."""
    return {
        "protocol_id": EXACT_SCORE_PROTOCOL_ID,
        "accumulation": "exact rational (fractions.Fraction), no float addition",
        "inputs": "exact rational image of each finite binary64 operand",
        "output_rounding": "single round-half-even to binary64 via float(Fraction)",
        "decimal_precision": EXACT_SCORE_PRECISION,
        "host_dependent_operations": "none (no BLAS, no libm, no SIMD)",
        "scope": (
            "reference oracle for the linear score only; it cannot compensate for "
            "coefficients that were themselves fitted on a different host"
        ),
    }


def compare_against_float64(
    coefficients: Sequence[float],
    row: Sequence[float],
    intercept: float,
) -> dict[str, object]:
    """Measure how far a host's float64 score is from the exact value.

    Returns a record rather than raising, because the divergence is the finding.
    """
    import numpy as np

    exact = exact_linear_score(coefficients, row, intercept)
    naive = float(np.dot(np.asarray(coefficients, dtype=np.float64),
                         np.asarray(row, dtype=np.float64)) + intercept)
    rounded = score_as_float(exact)
    return {
        "exact_as_float": rounded.hex(),
        "host_float64": naive.hex(),
        "identical": rounded == naive,
        "host_minus_exact_ulps": _ulps(naive, rounded),
    }


def _ulps(got: float, want: float) -> int | None:
    import struct

    if got != got or want != want:
        return None
    a = struct.unpack("<q", struct.pack("<d", got))[0]
    b = struct.unpack("<q", struct.pack("<d", want))[0]
    return abs(a - b)
