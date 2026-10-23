"""Deterministic arithmetic checks for the M2e.1 (Issue #37) sample-size review.

SCOPE NOTE — PROPOSED EXCEPTION, PENDING MAINTAINER ACCEPTANCE
Issue #37 authorises a documentation-only change. This script is not
documentation; it is retained only so that every number in document 05 can be
recomputed from the published formulae without trusting prose. Section 0.5 and
Appendix E of the review record the discrepancy and the documentation-only
fallback. If the maintainer does not accept the exception, this file should be
deleted and the PR reduced to documentation only.

WHAT THIS SCRIPT DOES NOT DO
  * it reads no project data (no /data, no source rows, no model artefacts);
  * it fits NO model, real or synthetic, and runs NO simulation;
  * it performs no experiment, no selection, no tuning, no evaluation;
  * it changes nothing under research/experiments.

It implements the binary-outcome sample-size criteria published by Riley et al.
(BMJ 2020;368:m441) and the minimum-MAPE criterion of van Smeden et al.
(Stat Methods Med Res 2019), mirroring the reference implementation in the R
package pmsampsize v1.1.3 (R/pmsampsize_bin.R), and checks them against the
published worked examples.

The C-statistic to Cox-Snell R2 conversion used by pmsampsize requires fitting
logistic regression models to simulated samples. That method is described in
the review as a documented reference only and is deliberately NOT executed
here.

Run with the Python standard library only:

    python3 scripts/verify_m2e1_sample_size.py

Exit code 0 means every check passed; any mismatch prints [FAIL] and exits 1.
"""

from __future__ import annotations

import math

# ---------------------------------------------------------------------------
# Project context (reported aggregates; no source data is read)
# ---------------------------------------------------------------------------

TOTAL = 303            # Cleveland records used by D-047
POSITIVES = 139        # num = 1..4
NEGATIVES = 164        # num = 0
PARAMETERS = 8         # age 1 + sex 1 + cp 3 + trestbps 1 + restecg 2
SHRINKAGE = 0.9        # pmsampsize default target
OPTIMISM = 0.05        # pmsampsize default: max difference in Nagelkerke R2
PRECISION = 0.05       # pmsampsize default: +/-0.05 for the outcome proportion
MAPE_TARGET = 0.05     # van Smeden / Riley default target MAPE

PREVALENCE = POSITIVES / TOTAL


# ---------------------------------------------------------------------------
# Criteria
# ---------------------------------------------------------------------------

def max_cox_snell_r2(prevalence: float) -> float:
    """Largest attainable Cox-Snell R2 for a binary outcome.

    Riley et al. BMJ 2020;368:m441:
        1 - exp(2 * [phi*ln(phi) + (1-phi)*ln(1-phi)])
    Bounded above by 0.75, attained at phi = 0.5.
    """
    phi = prevalence
    return 1.0 - math.exp(2.0 * (phi * math.log(phi) + (1.0 - phi) * math.log(1.0 - phi)))


def n_shrinkage(parameters: int, r2_cs: float, shrinkage: float = SHRINKAGE) -> float:
    """Criterion 1 (real-valued): expected uniform shrinkage at least `shrinkage`.

    n = p / ((S - 1) * ln(1 - R2_cs / S)), with R2_cs the anticipated
    (adjusted, population) Cox-Snell R2 and S the target shrinkage.
    Van Houwelingen & Le Cessie 1990; Riley 2020; pmsampsize_bin.R line 12.
    """
    if not (0.0 < shrinkage < 1.0):
        raise ValueError("shrinkage must lie in (0, 1)")
    if r2_cs >= shrinkage:
        raise ValueError("R2_cs must be below the shrinkage target (log domain)")
    return parameters / ((shrinkage - 1.0) * math.log(1.0 - r2_cs / shrinkage))


def n_shrinkage_ceiling(parameters: int, r2_cs: float, shrinkage: float = SHRINKAGE) -> int:
    """Criterion 1 as pmsampsize reports it (ceiling to whole participants)."""
    return math.ceil(n_shrinkage(parameters, r2_cs, shrinkage))


REPRESENTATION_ULPS = 8


def analytically_ceiled(real_value: float, ulps: int = REPRESENTATION_ULPS) -> int:
    """Ceiling with a guard at the scale of floating-point representation only.

    At an analytical break-even the real-valued requirement is exactly an
    integer, but ordinary evaluation can land a few ulps above it
    (303.00000000000006 for 303), and a plain ceiling then returns 304.

    The guard treats a value as analytically equal to the nearest integer when
    the gap is within `ulps` units in the last place (default 8, i.e. about
    3.6e-12 at 303 - roughly 1e-14 of a participant). That is a *representation*
    threshold, not a substantive rounding tolerance: it is twelve orders of
    magnitude below the smallest one-record shortfall discussed in the review,
    so it cannot convert an insufficient sample size into a sufficient one.
    Compare `n_shrinkage_ceiling`, which keeps the strict pmsampsize behaviour.
    """
    nearest = round(real_value)
    if abs(real_value - nearest) <= ulps * math.ulp(real_value):
        return int(nearest)
    return math.ceil(real_value)


def n_optimism(parameters: int, r2_cs: float, prevalence: float = PREVALENCE) -> int:
    """Criterion 2 (pmsampsize): optimism in Nagelkerke R2 no larger than 0.05.

    s = R2_cs / (R2_cs + 0.05 * max_R2_cs), then the criterion-1 expression
    with s in place of S (pmsampsize_bin.R lines 28-30).
    """
    maximum = max_cox_snell_r2(prevalence)
    if r2_cs > maximum:
        raise ValueError("R2_cs exceeds the maximum attainable Cox-Snell R2")
    s = r2_cs / (r2_cs + OPTIMISM * maximum)
    return math.ceil(parameters / ((s - 1.0) * math.log(1.0 - r2_cs / s)))


def n_precision(prevalence: float = PREVALENCE, half_width: float = PRECISION) -> int:
    """Criterion 3 (pmsampsize): 95% CI for the outcome proportion within +/-delta.

    n = (1.96/delta)^2 * phi * (1 - phi). Independent of R2 and of p.
    """
    return math.ceil(((1.96 / half_width) ** 2) * prevalence * (1.0 - prevalence))


def minority_proportion(phi: float) -> float:
    """Symmetry transformation for the MAPE criterion: phi* = min(phi, 1 - phi).

    The criterion is evaluated on the minority-class proportion so that a cohort
    with, say, 70% events is treated as its complementary 30% rather than as a
    qualitatively different planning problem. For this cohort phi = 0.4587 < 0.5,
    so phi* = phi and no transformation is applied (asserted in section C5).
    """
    return min(phi, 1.0 - phi)


def _mape_real(parameters: int, prevalence: float = PREVALENCE, mape: float = MAPE_TARGET) -> float:
    phi = minority_proportion(prevalence)
    return math.exp(
        (-0.508 + 0.259 * math.log(phi) + 0.504 * math.log(parameters) - math.log(mape)) / 0.544
    )


def n_mape(parameters: int, prevalence: float = PREVALENCE, mape: float = MAPE_TARGET) -> int:
    """ADDITIONAL criterion 4 (not returned by pmsampsize): minimum average MAPE.

    n = exp((-0.508 + 0.259*ln(phi*) + 0.504*ln(p) - ln(m)) / 0.544),
    with phi* the minority-class proportion. An approximation:
    van Smeden et al. 2019, stated for p <= 30.
    """
    if parameters > 30:
        raise ValueError("approximation is stated for p <= 30")
    return math.ceil(_mape_real(parameters, prevalence, mape))


# ---------------------------------------------------------------------------
# Inversions
# ---------------------------------------------------------------------------

def r2_at_n(n: float, parameters: int, shrinkage: float = SHRINKAGE) -> float:
    """Inverse of criterion 1 in R2: the R2_cs at which the real-valued n equals n."""
    return shrinkage * (1.0 - math.exp(parameters / ((shrinkage - 1.0) * n)))


def shrinkage_at_n(r2_cs: float, parameters: int = PARAMETERS, n: float = TOTAL) -> float:
    """Implicit inversion of criterion 1 in S: expected uniform shrinkage at size n.

    Solves n = p / ((S - 1) * ln(1 - R2_cs / S)) for S in (R2_cs, 1).

    This is the correct reading of criterion 1: the same anticipated adjusted
    Cox-Snell R2 that enters the sample-size equation is held fixed, and the
    shrinkage the model would actually achieve at n is recovered. A closed-form
    expression in elementary functions is not available, so the root is found
    by deterministic bisection to ~1e-14 relative precision.
    """
    if not (0.0 < r2_cs < 1.0):
        raise ValueError("R2_cs must lie in (0, 1)")
    if r2_cs >= max_cox_snell_r2(PREVALENCE):
        raise ValueError("R2_cs exceeds the maximum attainable Cox-Snell R2")

    lo, hi = r2_cs + 1e-15, 1.0 - 1e-15
    # n(S) is strictly increasing in S on (r2_cs, 1): larger target shrinkage
    # needs a larger sample, and at n fixed the achieved shrinkage is unique.
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        try:
            achieved = n_shrinkage(parameters, r2_cs, mid)
        except ValueError:
            lo = mid
            continue
        if achieved > n:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def delta_at_n(n: float, prevalence: float = PREVALENCE) -> float:
    """Half-width of the 95% CI for the outcome proportion at sample size n."""
    return 1.96 * math.sqrt(prevalence * (1.0 - prevalence) / n)


def mape_at_n(n: float, parameters: int, prevalence: float = PREVALENCE) -> float:
    """MAPE actually achievable at sample size n (inverse of criterion 4)."""
    return math.exp(
        -0.508 + 0.259 * math.log(prevalence) + 0.504 * math.log(parameters) - 0.544 * math.log(n)
    )


# ---------------------------------------------------------------------------
# Check harness
# ---------------------------------------------------------------------------

FAILURES: list[str] = []
COUNT = 0


def check(label: str, actual, expected, tolerance: float = 0.0) -> None:
    global COUNT
    COUNT += 1
    if tolerance:
        ok = abs(float(actual) - float(expected)) <= tolerance
    else:
        ok = actual == expected
    print(f"[{'PASS' if ok else 'FAIL'}] {label}: actual={actual!r} expected={expected!r}")
    if not ok:
        FAILURES.append(label)


def _raises(fn) -> bool:
    try:
        fn()
    except ValueError:
        return True
    return False


def published_anchors() -> None:
    print("\n== A. Published worked examples (Riley et al. BMJ 2020;368:m441) ==")
    p, r2, phi = 30, 0.05, 0.05
    check("max R2_cs at prevalence 0.05", round(max_cox_snell_r2(phi), 5), 0.32769)
    check("criterion 1 n (p=30, R2=0.05, phi=0.05)", n_shrinkage_ceiling(p, r2, SHRINKAGE), 5249)
    check("criterion 2 n", n_optimism(p, r2, phi), 1770)
    check("criterion 3 n", n_precision(phi), 73)
    check(
        "final n = max of the three published criteria",
        max(n_shrinkage_ceiling(p, r2, SHRINKAGE), n_optimism(p, r2, phi), n_precision(phi)),
        5249,
    )
    check("additional minimum-MAPE n (p=10, phi=0.30, m=0.05)", n_mape(10, 0.30, 0.05), 461)
    check(
        "minimum-MAPE real value before ceiling",
        round(_mape_real(10, 0.30, 0.05), 2),
        460.86,
        tolerance=0.01,
    )


def structural_checks() -> None:
    print("\n== B. Structural properties ==")
    check("max R2_cs at prevalence 0.5", round(max_cox_snell_r2(0.5), 6), 0.75)
    check(
        "max R2_cs never exceeds 0.75",
        max(max_cox_snell_r2(i / 1000) for i in range(1, 1000)) <= 0.75,
        True,
    )
    check("criterion 3 is independent of p (p=3)", n_precision(), 382)
    check("criterion 3 is independent of p (p=8)", n_precision(), 382)
    check("criterion 1 decreases as R2 rises", n_shrinkage(8, 0.10) > n_shrinkage(8, 0.20) > n_shrinkage(8, 0.30), True)
    check("criterion 1 increases with p", n_shrinkage(6, 0.15) < n_shrinkage(8, 0.15), True)
    check("guard: R2 not below shrinkage target", _raises(lambda: n_shrinkage(8, 0.95, 0.9)), True)
    check("guard: R2 not above attainable maximum", _raises(lambda: n_optimism(8, 0.9)), True)
    check("guard: MAPE approximation stated range", _raises(lambda: n_mape(31)), True)


def project_scenario() -> None:
    print("\n== C. The D-047 scenario: n=303, 139 events, p=8 ==")
    print(f"event fraction = {PREVALENCE:.8f}   max R2_cs = {max_cox_snell_r2(PREVALENCE):.8f}")
    print(f"criterion 3 (outcome proportion, delta=0.05) = {n_precision()}")
    print(f"additional criterion 4 (MAPE=0.05, p=8)      = {n_mape(PARAMETERS)}")

    print("\n-- C1. Required n by anticipated R2_cs (p=8, S=0.90) --")
    print(f"{'R2_cs':>12} {'n1':>10} {'ceil':>5} {'n2':>7} {'C3':>4} {'C4':>4} {'final':>6}")
    for r2 in (0.05, 0.075, 0.10, 0.11224, 0.125, 0.144, 0.15, 0.170054, 0.20884, 0.209, 0.25, 0.30, 0.50, 0.74829):
        n1 = n_shrinkage(PARAMETERS, r2)
        print(
            f"{r2:12.8f} {n1:10.4f} {math.ceil(n1):5d} {n_optimism(PARAMETERS, r2):7d} "
            f"{n_precision():4d} {n_mape(PARAMETERS):4d} {max(math.ceil(n1), n_optimism(PARAMETERS, r2), n_precision(), n_mape(PARAMETERS)):6d}"
        )

    print("\n-- C2. Criterion-1 break-even and rounding behaviour --")
    break_even = r2_at_n(TOTAL, PARAMETERS)
    check(
        "exact C1 break-even R2_cs at n=303, p=8, S=0.90",
        round(break_even, 12),
        round(0.20884206294424718, 12),
    )
    check("R2_cs needed for n1 = 304", round(r2_at_n(304, PARAMETERS), 8), 0.20824153, tolerance=5e-9)
    check("real-valued n1 at R2_cs = 0.20884", round(n_shrinkage(8, 0.20884), 4), 303.0034)
    check("ceiling n1 at R2_cs = 0.20884", n_shrinkage_ceiling(8, 0.20884), 304)
    check("real-valued n1 at R2_cs = 0.209", round(n_shrinkage(8, 0.209), 4), 302.7380)
    check("ceiling n1 at R2_cs = 0.209", n_shrinkage_ceiling(8, 0.209), 303)
    check(
        "real-valued n1 at the exact break-even is 303",
        round(n_shrinkage(8, break_even), 6),
        303.0,
        tolerance=1e-6,
    )

    print("\n-- C3. Break-even values at n=303 --")
    check("delta giving n3 = 303", round(delta_at_n(TOTAL), 6), 0.056108, tolerance=5e-7)
    check("MAPE achievable at n=303, p=8", round(mape_at_n(TOTAL, 8), 6), 0.062658, tolerance=5e-7)

    print("\n-- C4. Predictor budget (largest p satisfying each criterion set at n=303) --")
    for r2 in (0.15, 0.20884, 0.209, 0.25):
        def affordable(*criteria) -> int:
            ok = [q for q in range(1, 21) if max(c(q) for c in criteria) <= TOTAL]
            return max(ok) if ok else 0

        c1 = lambda q: n_shrinkage_ceiling(q, r2)
        c2 = lambda q: n_optimism(q, r2)
        c3 = lambda q: n_precision()
        c4 = lambda q: n_mape(q)
        print(
            f"  R2_cs={r2:<8}: C1 p<={affordable(c1)}, C1+C2 p<={affordable(c1, c2)}, "
            f"C1+C2+C3 p<={affordable(c1, c2, c3)}, all four p<={affordable(c1, c2, c3, c4)}"
        )

    check("C1 budget at R2_cs=0.20884 is p<=7", max([q for q in range(1, 21) if n_shrinkage_ceiling(q, 0.20884) <= TOTAL]), 7)
    check("C1 budget at R2_cs=0.209 is p<=8", max([q for q in range(1, 21) if n_shrinkage_ceiling(q, 0.209) <= TOTAL]), 8)


def floating_point_edge_case() -> None:
    print("\n== D. Analytical equality versus floating-point representation ==")
    break_even = r2_at_n(TOTAL, PARAMETERS)
    real_value = n_shrinkage(PARAMETERS, break_even)
    print(f"break-even R2_cs            = {break_even!r}")
    print(f"real-valued requirement     = {real_value!r}")
    print(f"math.ceil(real_value)       = {math.ceil(real_value)}   (strict pmsampsize behaviour)")
    print(f"analytically_ceiled(value)  = {analytically_ceiled(real_value)}   (representation-aware)")
    check("strict ceiling exhibits the representational artefact", math.ceil(real_value), 304)
    check("analytical ceiling returns 303 at the break-even", analytically_ceiled(real_value), 303)
    check(
        "gap to the integer is at representation scale, not substantive scale",
        abs(real_value - 303.0) < 1e-9,
        True,
    )
    check(
        "guard width in participants is negligible",
        REPRESENTATION_ULPS * math.ulp(303.0) < 1e-9,
        True,
    )

    print("\n-- D1. The guard must not rescue genuinely insufficient sizes --")
    for r2 in (0.20884, 0.205, 0.20, 0.170054, 0.209):
        real = n_shrinkage(PARAMETERS, r2)
        print(
            f"   R2_cs={r2:<9} real={real:10.4f} strict={math.ceil(real):4d} "
            f"analytic={analytically_ceiled(real):4d}"
        )
    check("at 0.20884 both ceilings give 304", (math.ceil(n_shrinkage(8, 0.20884)), analytically_ceiled(n_shrinkage(8, 0.20884))), (304, 304))
    check("at 0.205 both ceilings give 310", (math.ceil(n_shrinkage(8, 0.205)), analytically_ceiled(n_shrinkage(8, 0.205))), (310, 310))
    check("at 0.209 both ceilings give 303", (math.ceil(n_shrinkage(8, 0.209)), analytically_ceiled(n_shrinkage(8, 0.209))), (303, 303))
    check("at 0.170054 both ceilings give 382", (math.ceil(n_shrinkage(8, 0.170054)), analytically_ceiled(n_shrinkage(8, 0.170054))), (382, 382))

    print("\n-- D2. Where the guard does and does not fire --")
    check("a value 0.5 below an integer still ceils upward", analytically_ceiled(302.5), 303)
    check("a value 1 ulp below an integer is treated as that integer", analytically_ceiled(303.0 - math.ulp(303.0)), 303)
    check("a value clearly above an integer still ceils upward", analytically_ceiled(303.01), 304)


def mape_applicability() -> None:
    print("\n== E. Applicability domain of the additional MAPE criterion ==")
    print(f"event proportion phi        = {PREVALENCE:.8f}")
    print(f"minority proportion phi*    = {minority_proportion(PREVALENCE):.8f}")
    check("phi <= 0.5, so no symmetry transformation is required here", PREVALENCE <= 0.5, True)
    check("phi* equals phi for this cohort", minority_proportion(PREVALENCE), PREVALENCE)
    check("C4 unchanged by the transformation", n_mape(PARAMETERS), 459)

    print("\n-- E1. Symmetry behaviour (illustrative; not this cohort) --")
    for phi in (0.30, 0.458746, 0.50, 0.70):
        print(
            f"   phi={phi:.6f} phi*={minority_proportion(phi):.6f} "
            f"C4(p=8)={n_mape(8, phi)}"
        )
    check("a 70% event proportion is evaluated on 30%", round(minority_proportion(0.70), 12), 0.30)
    check("symmetry: phi and 1-phi give the same requirement", n_mape(8, 0.70), n_mape(8, 0.30))
    check("the requirement is largest at an even split", n_mape(8, 0.50) > n_mape(8, 0.30), True)

    print("\n-- E2. Stated domain and guards --")
    check("p <= 30 is enforced", _raises(lambda: n_mape(31)), True)
    check("p = 30 is inside the stated domain", isinstance(n_mape(30), int), True)


def shrinkage_inversion() -> None:
    print("\n== F. Implicit inversion of criterion 1: shrinkage achieved at n=303, p=8 ==")
    print("   n(S) = p / ((S-1) * ln(1 - R2_cs/S)) solved for S; same R2_cs as in C1.")
    print(f"{'R2_cs':>10} {'S achieved':>12} {'check n(S)':>12}")
    expected_roots = {
        0.05: 0.663180,
        0.10: 0.801798,
        0.15: 0.861910,
        0.20884206294424718: 0.900000,
        0.25: 0.917050,
        0.30: 0.932027,
    }
    for r2, target in expected_roots.items():
        s = shrinkage_at_n(r2)
        print(f"{r2:10.6f} {s:12.6f} {n_shrinkage(PARAMETERS, r2, s):12.4f}")
        check(f"achieved shrinkage at R2_cs={r2:.6f}", round(s, 6), target, tolerance=2e-6)
        check(
            f"round-trip n(S(R2_cs={r2:.6f})) = 303",
            round(n_shrinkage(PARAMETERS, r2, s), 6),
            303.0,
            tolerance=1e-3,
        )
    check(
        "shrinkage at the C1 break-even equals the target 0.90",
        round(shrinkage_at_n(0.20884206294424718), 9),
        0.9,
        tolerance=1e-6,
    )
    check(
        "naive formula 1 + p/(n ln(1-R2)) is NOT the criterion-1 inverse",
        abs((1.0 + PARAMETERS / (TOTAL * math.log(1.0 - 0.20884206294424718))) - 0.9) > 0.01,
        True,
    )


def main() -> int:
    print(__doc__)
    published_anchors()
    structural_checks()
    project_scenario()
    floating_point_edge_case()
    mape_applicability()
    shrinkage_inversion()
    print("\n== Summary ==")
    print(f"checks run: {COUNT}")
    if FAILURES:
        print(f"FAILED checks: {len(FAILURES)} -> {FAILURES}")
        return 1
    print("All deterministic checks passed. No model was fitted and no simulation was run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
