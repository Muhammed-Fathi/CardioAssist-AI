"""Reproduce every number in the M2e.1 (Issue #37) sample-size review document.

Documentation-support arithmetic ONLY. This script:
  * reads no project data (no /data, no source rows, no model artefacts);
  * fits no model to any patient data;
  * performs no experiment, no selection, no tuning, no evaluation;
  * changes nothing under research/experiments.

It re-implements the binary-outcome sample-size criteria published by
Riley et al. (BMJ 2020;368:m441) and the minimum-MAPE criterion of
van Smeden et al. (Stat Methods Med Res 2019), mirroring the reference
implementation in the R package pmsampsize v1.1.3 (R/pmsampsize_bin.R),
and checks them against the published worked examples.

Run with the Python standard library only:

    python3 scripts/verify_m2e1_sample_size.py

Add --simulate to additionally reproduce pmsampsize's C-statistic to
Cox-Snell R-squared conversion (R/cstat2rsq.R). That path needs numpy
and scipy and is optional; without them it reports SKIP.

Exit code 0 means every deterministic check passed.
"""

from __future__ import annotations

import math
import sys

# ---------------------------------------------------------------------------
# Project context (all numbers here are reported aggregates, not source data)
# ---------------------------------------------------------------------------

TOTAL = 303            # Cleveland records used by D-047
POSITIVES = 139        # num = 1..4
NEGATIVES = 164        # num = 0
PARAMETERS = 8         # age 1 + sex 1 + cp 3 + trestbps 1 + restecg 2
SHRINKAGE = 0.9        # pmsampsize default target
OPTIMISM = 0.05        # pmsampsize default: max absolute difference in R2
PRECISION = 0.05       # pmsampsize default: +/-0.05 for the outcome proportion
MAPE_TARGET = 0.05     # van Smeden / Riley default target MAPE

PREVALENCE = POSITIVES / TOTAL


# ---------------------------------------------------------------------------
# Criteria (transcriptions with provenance)
# ---------------------------------------------------------------------------

def max_cox_snell_r2(prevalence: float) -> float:
    """Largest attainable Cox-Snell R2 for a binary outcome.

    Riley et al. BMJ 2020;368:m441, equation for max(R2_cs):
        1 - exp(2 * [phi*ln(phi) + (1-phi)*ln(1-phi)])
    where phi is the outcome proportion. Bounded above by 0.75 at phi = 0.5.
    """
    phi = prevalence
    return 1.0 - math.exp(2.0 * (phi * math.log(phi) + (1.0 - phi) * math.log(1.0 - phi)))


def n_shrinkage(parameters: int, r2_cs: float, shrinkage: float = SHRINKAGE) -> int:
    """Criterion 1: expected uniform shrinkage at least `shrinkage`.

    Van Houwelingen & Le Cessie, Stat Med 1990;9:1303-1325; Riley 2020.
    n = p / ((S - 1) * ln(1 - R2_cs / S)).  Raises if S <= R2_cs.
    """
    if shrinkage <= r2_cs:
        raise ValueError(
            "shrinkage must exceed R2_cs; pmsampsize stops here for the same reason"
        )
    return math.ceil(parameters / ((shrinkage - 1.0) * math.log(1.0 - r2_cs / shrinkage)))


def n_optimism(parameters: int, r2_cs: float, prevalence: float = PREVALENCE) -> int:
    """Criterion 2: absolute optimism in Nagelkerke R2 no larger than 0.05.

    Riley 2020: s = R2_cs / (R2_cs + 0.05 * max_R2_cs), then the shrinkage
    expression with s in place of S. Uses the prevalence-only max R2_cs,
    exactly as pmsampsize_bin.R lines 19-30.
    """
    if max_cox_snell_r2(prevalence) < r2_cs:
        raise ValueError("R2_cs exceeds the maximum attainable Cox-Snell R2")
    s = r2_cs / (r2_cs + OPTIMISM * max_cox_snell_r2(prevalence))
    return math.ceil(parameters / ((s - 1.0) * math.log(1.0 - r2_cs / s)))


def n_precision(prevalence: float = PREVALENCE, half_width: float = PRECISION) -> int:
    """Criterion 3: 95% CI for the outcome proportion no wider than +/-0.05.

    Riley 2020; pmsampsize_bin.R line 39: (1.96/0.05)^2 * phi * (1 - phi).
    Note: independent of the number of parameters.
    """
    return math.ceil(((1.96 / half_width) ** 2) * prevalence * (1.0 - prevalence))


def n_mape(parameters: int, prevalence: float = PREVALENCE, mape: float = MAPE_TARGET) -> int:
    """Minimum-MAPE criterion (van Smeden et al. 2019), as in Riley 2020.

    n = exp((-0.508 + 0.259*ln(phi) + 0.504*ln(p) - ln(m)) / 0.544)
    Stated by the source to apply for p <= 30.
    """
    if parameters > 30:
        raise ValueError("approximation is stated for p <= 30")
    return math.ceil(
        math.exp(
            (-0.508 + 0.259 * math.log(prevalence) + 0.504 * math.log(parameters) - math.log(mape))
            / 0.544
        )
    )


def r2_needed_for_n(n: int, parameters: int, shrinkage: float = SHRINKAGE) -> float:
    """Inverse of criterion 1: R2_cs at which the real-valued n equals `n`."""
    return shrinkage * (1.0 - math.exp(parameters / ((shrinkage - 1.0) * n)))


def delta_at_n(n: int, prevalence: float = PREVALENCE) -> float:
    """Half-width of the 95% CI for the outcome proportion at sample size n."""
    return 1.96 * math.sqrt(prevalence * (1.0 - prevalence) / n)


def mape_at_n(n: int, parameters: int, prevalence: float = PREVALENCE) -> float:
    """Inverse of the MAPE criterion: the MAPE achievable at sample size n."""
    return math.exp(
        -0.508 + 0.259 * math.log(prevalence) + 0.504 * math.log(parameters) - 0.544 * math.log(n)
    )


# ---------------------------------------------------------------------------
# Checks against published worked examples
# ---------------------------------------------------------------------------

FAILURES: list[str] = []


def check(label: str, actual, expected, tolerance: float = 0.0) -> None:
    if tolerance:
        ok = abs(float(actual) - float(expected)) <= tolerance
    else:
        ok = actual == expected
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {label}: actual={actual!r} expected={expected!r}")
    if not ok:
        FAILURES.append(label)


def published_anchors() -> None:
    print("\n== A. Published worked examples (Riley et al. BMJ 2020;368:m441) ==")
    # Example: p = 30, R2_cs = 0.05, prevalence = 0.05, S = 0.90.
    p, r2, phi = 30, 0.05, 0.05
    check("max R2_cs at prevalence 0.05", round(max_cox_snell_r2(phi), 5), 0.32769)
    check("criterion 1 n (p=30, R2=0.05, phi=0.05)", n_shrinkage(p, r2, SHRINKAGE), 5249)
    check("criterion 2 n", n_optimism(p, r2, phi), 1770)
    check("criterion 3 n", n_precision(phi), 73)
    check("final n = max of criteria", max(n_shrinkage(p, r2, SHRINKAGE), n_optimism(p, r2, phi), n_precision(phi)), 5249)
    # Minimum-MAPE worked example: p = 10, prevalence = 0.30, target MAPE = 0.05.
    check("minimum-MAPE n (p=10, phi=0.30, m=0.05)", n_mape(10, 0.30, 0.05), 461)
    check("minimum-MAPE n before ceiling", round(math.exp((-0.508 + 0.259 * math.log(0.30) + 0.504 * math.log(10) - math.log(0.05)) / 0.544), 2), 460.86, tolerance=0.01)


def structural_checks() -> None:
    print("\n== B. Structural properties of the criteria ==")
    check("max R2_cs at prevalence 0.5", round(max_cox_snell_r2(0.5), 5), 0.75)
    check("max R2_cs never exceeds 0.75", max(round(max_cox_snell_r2(i / 1000), 10) for i in range(1, 1000)) <= 0.75, True)
    check("criterion 3 independent of p (p=8)", n_precision(), 382)
    check("criterion 1 monotone decreasing in R2", n_shrinkage(8, 0.10) > n_shrinkage(8, 0.20) > n_shrinkage(8, 0.30), True)
    check("criterion 1 monotone increasing in p", n_shrinkage(6, 0.15) < n_shrinkage(8, 0.15), True)
    check("R2 ceiling error guard", _raises(lambda: n_shrinkage(8, 0.95, 0.9)), True)
    check("max R2 error guard", _raises(lambda: n_optimism(8, 0.9)), True)
    check("MAPE p<=30 guard", _raises(lambda: n_mape(31)), True)


def _raises(fn) -> bool:
    try:
        fn()
    except ValueError:
        return True
    return False


def project_scenario() -> None:
    print("\n== C. The D-047 scenario: n=303, 139 events, p=8 ==")
    print(f"prevalence = {PREVALENCE:.8f}   max R2_cs = {max_cox_snell_r2(PREVALENCE):.5f}")
    print(f"criterion 3 (outcome proportion) = {n_precision()}")
    print(f"criterion 4 (minimum MAPE)       = {n_mape(PARAMETERS)}")

    print("\n-- C1. Required n as a function of the (unapproved) anticipated R2_cs --")
    print(f"{'R2_cs':>7} {'R2Nag*':>7} {'n1':>6} {'n2':>6} {'n3':>5} {'B2':>5} {'final':>6} {'shortfall':>9}")
    for r2 in (0.05, 0.075, 0.10, 0.11224, 0.125, 0.14396, 0.15, 0.17006, 0.20884, 0.25, 0.30, 0.50, 0.74829):
        n1, n2, n3, b2 = n_shrinkage(PARAMETERS, r2), n_optimism(PARAMETERS, r2), n_precision(), n_mape(PARAMETERS)
        final = max(n1, n2, n3, b2)
        print(
            f"{r2:7.5f} {r2 / max_cox_snell_r2(PREVALENCE):7.4f} {n1:6d} {n2:6d} {n3:5d} {b2:5d} "
            f"{final:6d} {final - TOTAL:9d}"
        )
    print("* R2Nag-equivalent = R2_cs / max R2_cs at this prevalence (interpretation aid only).")

    print("\n-- C2. Break-even values at n=303 (what would have to be relaxed) --")
    check("delta giving n3 = 303", round(delta_at_n(303), 6), 0.056108, tolerance=5e-7)
    check("MAPE achievable at n=303, p=8", round(mape_at_n(303, 8), 6), 0.062658, tolerance=5e-7)

    print("\n-- C3. Minimum R2_cs for criterion 1 to be met at n=303 --")
    for params in range(2, 11):
        print(f"  p={params:2d}: R2_cs >= {r2_needed_for_n(TOTAL, params):.5f}")

    print("\n-- C4. Shrinkage-sensitivity of the p=8 threshold at n=303 --")
    for s in (0.80, 0.85, 0.90, 0.95):
        print(f"  S={s:.2f}: R2_cs >= {r2_needed_for_n(TOTAL, PARAMETERS, s):.5f}")

    print("\n-- C5. Predictor budget at n=303 (largest p satisfying the stated criteria) --")
    for r2 in (0.10, 0.15, 0.20884, 0.25):
        affordable_c1 = max([p for p in range(1, 21) if n_shrinkage(p, r2) <= TOTAL] or [0])
        affordable_c1c2 = max([p for p in range(1, 21) if max(n_shrinkage(p, r2), n_optimism(p, r2)) <= TOTAL] or [0])
        affordable_c123 = max([p for p in range(1, 21) if max(n_shrinkage(p, r2), n_optimism(p, r2), n_precision()) <= TOTAL] or [0])
        affordable_all = max([p for p in range(1, 21) if max(n_shrinkage(p, r2), n_optimism(p, r2), n_precision(), n_mape(p)) <= TOTAL] or [0])
        print(f"  R2_cs={r2:.5f}: C1 p<={affordable_c1}, C1+C2 p<={affordable_c1c2}, "
              f"C1+C2+C3 p<={affordable_c123}, all four p<={affordable_all}")


def expected_shrinkage() -> None:
    """Expected uniform shrinkage at the realised sample size.

    Van Houwelingen & Le Cessie, Stat Med 1990: S = (chi2 - p)/chi2 with
    chi2 = -n*ln(1 - R2_cs); equivalently S = 1 + p/(n*ln(1 - R2_cs)).
    This is the quantity criterion 1 targets, read at n = 303 instead of
    solving for n.
    """
    print("\n== E. Expected shrinkage at n=303, p=8, for a given true R2_cs ==")
    print(f"{'R2_cs':>7} {'R2Nag*':>7} {'S_expected':>10}")
    for r2 in (0.05, 0.075, 0.10, 0.11224, 0.15, 0.17006, 0.20884, 0.25, 0.30, 0.3453):
        s = 1.0 + PARAMETERS / (TOTAL * math.log(1.0 - r2))
        print(f"{r2:7.5f} {r2 / max_cox_snell_r2(PREVALENCE):7.4f} {s:10.4f}")
    check("S at R2_cs=0.20884 is 0.8873", round(1.0 + PARAMETERS / (TOTAL * math.log(1.0 - 0.20884)), 4), 0.8873)
    check("R2_cs needed for S=0.85 at n=303", round(r2_needed_for_n(TOTAL, PARAMETERS, 0.85), 5), 0.13719)


def simulate_cstat_to_r2() -> None:
    """Optional: reproduce pmsampsize::cstat2rsq (R/cstat2rsq.R)."""
    try:
        import numpy as np
        from scipy.special import expit, log_expit
        from scipy.stats import norm
    except Exception:
        print("\n== D. C-statistic to R2_cs simulation: SKIP (numpy/scipy not installed) ==")
        return

    def loglik(y, eta):
        # stable Bernoulli log-likelihood: y*eta - log(1 + exp(eta))
        return float(np.sum(y * eta + log_expit(-eta)))

    def fit(y, X):
        beta = np.zeros(X.shape[1])
        current = loglik(y, X @ beta)
        for _ in range(60):
            eta = X @ beta
            p = expit(eta)
            grad = X.T @ (y - p)
            hess = -(X.T * (p * (1.0 - p))) @ X
            step = np.linalg.solve(hess, -grad)
            # damped Newton: halve the step until the log-likelihood improves
            scale = 1.0
            while scale > 1e-6:
                candidate = beta + scale * step
                value = loglik(y, X @ candidate)
                if value > current:
                    beta, current = candidate, value
                    break
                scale /= 2.0
            else:
                break
        return -2.0 * current

    def r2_cs(y, lp):
        d_model = fit(y, np.column_stack([np.ones_like(lp), lp]))
        d_null = fit(y, np.ones((len(lp), 1)))
        return 1.0 - math.exp(-(d_null - d_model) / len(y))

    def simulate(c, prevalence, seed=123456, n=1_000_000):
        rng = np.random.default_rng(seed)
        mu = math.sqrt(2.0) * norm.ppf(c)
        n1 = int(prevalence * n)
        lp = np.concatenate([rng.normal(0, 1, n - n1), rng.normal(mu, 1, n1)])
        y = np.concatenate([np.zeros(n - n1), np.ones(n1)])
        return r2_cs(y, lp)

    print("\n== D. C-statistic to Cox-Snell R2 (pmsampsize::cstat2rsq replication) ==")
    got = simulate(0.81, 0.77)
    print(f"published example (C=0.81, prevalence=0.77): {got:.6f} vs 0.2100957")
    check("cstat2rsq reproduces the published example within 0.005", abs(got - 0.2100957) < 0.005, True)

    print("\n-- D1. Illustration only: R2_cs implied by a C-statistic at prevalence 0.4587 --")
    print("   (NOT an admissible anticipatory input for D-047; see document section 7)")
    for c in (0.69, 0.75, 0.77, 0.79, 0.82, 0.85):
        r2 = simulate(c, PREVALENCE)
        print(f"   C={c:.2f} -> R2_cs={r2:.4f} (R2Nag~{r2 / max_cox_snell_r2(PREVALENCE):.4f}), "
              f"criterion-1 n={n_shrinkage(PARAMETERS, r2)}")
def main() -> int:
    print(__doc__)
    published_anchors()
    structural_checks()
    project_scenario()
    expected_shrinkage()
    if "--simulate" in sys.argv:
        simulate_cstat_to_r2()
    print("\n== Summary ==")
    if FAILURES:
        print(f"FAILED checks: {len(FAILURES)} -> {FAILURES}")
        return 1
    print("All deterministic checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
