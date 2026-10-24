"""Deterministic precision arithmetic for Gate PT document 15 (evidence-resolution report).

WHAT THIS SCRIPT DOES
  * It reproduces the R2-free "outcome proportion" precision criterion of the
    Riley-family binary-outcome framework (Riley et al., BMJ 2020;368:m441, as
    already verified in Gate PT doc 05) against counts that are *already
    published in the repository* and, for the new Hungary question, against the
    class counts published in the official UCI-45 codebook
    (heart-disease.names section 10) plus the maintainer-reported processed-file
    aggregate. No new data are read.
  * It computes an illustrative Hanley-McNeil / DeLong large-sample standard
    error for a two-class AUROC under *hypothetical* assumed AUROC values, so a
    reviewer can see the achievable precision of a future one-shot assessment
    at fixed class counts.

WHAT THIS SCRIPT DOES NOT DO
  * it reads no project data (no /data, no source rows, no model artefacts);
  * it fits NO model, real or synthetic, and runs NO simulation;
  * it performs no experiment, no selection, no tuning, no evaluation, no
    external validation and no transfer prediction;
  * it makes no performance claim: every AUROC entering the SE formula is a
    *hypothetical scenario value* (labelled SC), not a prediction, not an
    expectation derived from any observed result, and not an input to any
    decision;
  * it changes nothing under research/, docs/ or backend/.

Provenance of every input constant is stated next to it. Run with the Python
standard library only:

    python3 scripts/verify_pt15_precision_scenarios.py

Exit code 0 means every check passed; any mismatch prints [FAIL] and exits 1.
"""

from __future__ import annotations

import math

# ---------------------------------------------------------------------------
# Fixed inputs (no data are read; every number is a documented aggregate)
# ---------------------------------------------------------------------------

# Cleveland / DA-A2: published class distribution for the Cleveland cohort of
# UCI-45 (heart-disease.names §10: 164 / 55 / 36 / 35 / 13, total 303), i.e.
# 164 records with num = 0 and 139 with num = 1..4.
CLEVELAND_N = 303
CLEVELAND_POS = 139

# UCI-412 / DA-A1: maintainer-reported read-only audit aggregates
# (docs/research/gate-da/10_m2a_uci412_uci411_evidence_and_decisions.md §2;
# 216 exact "Cad", 87 exact "Normal").
UCI412_N = 303
UCI412_POS = 216

# Hungary / DA-A2 (UCI-45 sibling site): the official codebook publishes the
# raw 0..4 counts 188 / 37 / 26 / 28 / 15 = 294, and the maintainer-reported
# processed-file audit reports the same 188 negative / 106 positive split.
HUNGARY_N = 294
HUNGARY_POS = 106

# Reproducible anchors already recorded in the repository, used here only to
# show that this implementation agrees with the frozen figures:
#   * Cleveland outcome-proportion requirement 382  (Gate PT doc 05, §5)
#   * UCI-412 outcome-proportion requirement 315    (Gate PT doc 08 / doc 11 §5.2)
CLEVELAND_ANCHOR = 382
UCI412_ANCHOR = 315

Z_95 = 1.959963984540054  # two-sided 95% normal quantile
DELTA = 0.05             # pmsampsize default half-width for the outcome proportion


# ---------------------------------------------------------------------------
# R2-free outcome-proportion criterion
# ---------------------------------------------------------------------------

def outcome_proportion_n(prevalence: float, delta: float = DELTA, z: float = Z_95) -> int:
    """Records needed so the outcome proportion is estimated to +/- `delta`.

    n = (z / delta)^2 * phi * (1 - phi), rounded up -- the criterion recorded in
    Gate PT doc 05 §5 / pmsampsize's `n_precision` branch. It depends on the
    anticipated outcome proportion only, never on R2 or on model performance.
    """
    if not 0.0 < prevalence < 1.0:
        raise ValueError("prevalence must lie strictly between 0 and 1")
    if delta <= 0.0:
        raise ValueError("delta must be positive")
    return math.ceil((z / delta) ** 2 * prevalence * (1.0 - prevalence))


def delta_at_n(prevalence: float, n: int, z: float = Z_95) -> float:
    """Half-width of the 95% interval for the outcome proportion at `n` records."""
    return z * math.sqrt(prevalence * (1.0 - prevalence) / n)


# ---------------------------------------------------------------------------
# Illustrative AUROC precision at fixed class counts (Hanley-McNeil / DeLong)
# ---------------------------------------------------------------------------

def auroc_se(auc: float, n_pos: int, n_neg: int) -> float:
    """Large-sample SE of a two-class AUROC (Hanley & McNeil 1982; DeLong 1988).

    Q1 = A / (2 - A);  Q2 = 2 A^2 / (1 + A)
    SE = sqrt( [A(1-A) + (n_pos-1)(Q1-A^2) + (n_neg-1)(Q2-A^2)] / (n_pos*n_neg) )

    `auc` is a HYPOTHETICAL scenario value, not a predicted or expected result.
    The expression ignores refitting/selection uncertainty and clustering, so a
    real assessment interval would be wider, never narrower.
    """
    if not 0.5 <= auc < 1.0:
        raise ValueError("scenario AUROC must lie in [0.5, 1)")
    q1 = auc / (2.0 - auc)
    q2 = 2.0 * auc * auc / (1.0 + auc)
    numerator = (
        auc * (1.0 - auc)
        + (n_pos - 1) * (q1 - auc * auc)
        + (n_neg - 1) * (q2 - auc * auc)
    )
    return math.sqrt(numerator / (n_pos * n_neg))


def auroc_half_width(auc: float, n_pos: int, n_neg: int, z: float = Z_95) -> float:
    return z * auroc_se(auc, n_pos, n_neg)


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check(label: str, actual, expected, tolerance: float = 0.0) -> None:
    ok = (
        abs(actual - expected) <= tolerance
        if isinstance(expected, float)
        else actual == expected
    )
    print(f"[{'PASS' if ok else 'FAIL'}] {label}: {actual!r} (expected {expected!r})")
    if not ok:
        raise SystemExit(1)


def anchors() -> None:
    print("--- reproducibility anchors (already published in the repository) ---")
    check(
        "Cleveland outcome-proportion n at +/-0.05",
        outcome_proportion_n(CLEVELAND_POS / CLEVELAND_N),
        CLEVELAND_ANCHOR,
    )
    check(
        "UCI-412 outcome-proportion n at +/-0.05",
        outcome_proportion_n(UCI412_POS / UCI412_N),
        UCI412_ANCHOR,
    )
    # Standard textbook anchor: phi = 0.5, delta = 0.05 -> 384.16 -> 385.
    check("phi=0.5, delta=0.05", outcome_proportion_n(0.5), 385)


def hungary_precision() -> None:
    print("\n--- Hungary (294 records; 106 positive / 188 negative) ---")
    p = HUNGARY_POS / HUNGARY_N
    print(f"outcome proportion p            = {p:.6f}  ({HUNGARY_POS}/{HUNGARY_N})")
    n_req = outcome_proportion_n(p)
    print(f"n required at +/-0.05 (95%)     = {n_req}   (shortfall {n_req - HUNGARY_N})")
    print(f"achievable half-width at n=294  = +/-{delta_at_n(p, HUNGARY_N):.4f}")
    print(f"records needed for +/-0.055     = {outcome_proportion_n(p, 0.055)}")
    check("achievable half-width is just above 0.05", delta_at_n(p, HUNGARY_N) > 0.05, True)
    check("achievable half-width is below 0.056", delta_at_n(p, HUNGARY_N) < 0.056, True)


def auroc_scenarios() -> None:
    print("\n--- illustrative AUROC precision at fixed class counts (SC = scenario) ---")
    cohorts = [
        ("Hungary  294 (106 pos / 188 neg)", HUNGARY_POS, HUNGARY_N - HUNGARY_POS),
        ("Cleveland 303 (139 pos / 164 neg)", CLEVELAND_POS, CLEVELAND_N - CLEVELAND_POS),
        ("UCI-412  303 (216 pos /  87 neg)", UCI412_POS, UCI412_N - UCI412_POS),
    ]
    aucs = [0.70, 0.75, 0.80, 0.85, 0.90]
    header = "cohort".ljust(36) + "".join(f"  A={a:.2f}" for a in aucs)
    print(header)
    for name, n_pos, n_neg in cohorts:
        row = name.ljust(36)
        for a in aucs:
            row += f"  +/-{auroc_half_width(a, n_pos, n_neg):.3f}"
        print(row)
    print("(half-widths of a 95% interval, Hanley-McNeil SE, ignoring refitting "
          "and selection uncertainty)")

    # Monotonicity / sanity checks of the SE expression.
    check("SE falls as assumed AUROC rises (Hungary)",
          auroc_se(0.90, HUNGARY_POS, HUNGARY_N - HUNGARY_POS)
          < auroc_se(0.70, HUNGARY_POS, HUNGARY_N - HUNGARY_POS), True)
    check("SE grows when the minority class shrinks (A=0.80)",
          auroc_se(0.80, 87, UCI412_N - 87) > auroc_se(0.80, HUNGARY_POS, 188), True)
    check("AUROC half-width at A=0.80, Hungary, is under 0.06",
          auroc_half_width(0.80, HUNGARY_POS, 188) < 0.06, True)


def class_counts_and_outcome_precision() -> None:
    print("\n--- class counts and achievable outcome-proportion precision ---")
    for name, n_pos, n_neg in [
        ("Cleveland", CLEVELAND_POS, CLEVELAND_N - CLEVELAND_POS),
        ("Hungary", HUNGARY_POS, HUNGARY_N - HUNGARY_POS),
        ("UCI-412", UCI412_POS, UCI412_N - UCI412_POS),
    ]:
        n = n_pos + n_neg
        p = n_pos / n
        print(f"{name:<10} positives {n_pos:3d}  negatives {n_neg:3d}  "
              f"positive fraction {p:.4f}  "
              f"achievable half-width +/-{delta_at_n(p, n):.4f}  "
              f"n needed at +/-0.05 = {outcome_proportion_n(p)}")


def main() -> int:
    anchors()
    hungary_precision()
    auroc_scenarios()
    class_counts_and_outcome_precision()
    print("\nAll checks passed. No data were read; no model was fitted; "
          "no performance was estimated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
