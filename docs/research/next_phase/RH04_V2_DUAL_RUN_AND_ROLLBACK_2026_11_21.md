# Dual-run window (V2-05) and rollback (V2-10) — v3

**Document ID:** CAI-RH04-DUALROLLBACK-v3 (supersedes v1 and v2)
**Status:** PROPOSAL for V2-05; DEMONSTRATION for V2-10, repeated on the final
delivery version.

---

## Part 1 — V2-05 dual-run window

### 1.1 Requirement

> `V2-05` **Dual-run window.** Both V1 (scoped, §6) and V2 gates run in CI until
> the owner retires V1. No silent substitution.

### 1.2 Corrections to earlier proposals

| earlier claim | status |
|---|---|
| v1: "two Lane B runs on different BLAS kernels" | **wrong** — that is a portability check, not a dual-run window |
| v2: "Lane A diagnostic stage, non-voting" | **incomplete** — right that divergence is diagnostic, wrong to imply *any* Lane A outcome is acceptable |

### 1.3 Proposed stage contract

Four stages, in order. Each reports its result **even when an earlier stage
fails** (`if: always()` at the reporting step, while the gate step itself keeps
its own exit code). Mandatory failures stay visible and are never suppressed.

| # | stage | gate character | must report |
|---|---|---|---|
| 1 | **V1 scoped verification** | mandatory | pass/fail counts, exit code |
| 2 | **Lane A regeneration evidence** | **classified** (see below) | optimality evidence, classification, per-class results |
| 3 | **Lane B fixed-reference exact replay** | mandatory | digest, per-class match, exit code |
| 4 | **Security and regression checks** | mandatory | counts, exit code |

### 1.4 Lane A is "classified", not "non-voting"

The earlier wording let *any* Lane A outcome through as diagnostic. That is wrong.
Stage 2 classifies its result into exactly one of:

- `DIAGNOSTIC_DIVERGENCE` — converged, valid status, numbers differ → **report,
  does not fail the job**
- `TRAINING_FAILED` — did not converge or status is not the success value →
  **fails the job**
- `EVIDENCE_MISSING` — no objective, gradient norm, iterations or parameters →
  **fails the job**
- `OUTPUT_INVALID` — malformed, non-finite or structurally wrong →
  **fails the job**

Only the first is acceptable variation. The other three are failures and must be
reported as such; presenting them as diagnostic noise is the failure mode this
stage exists to prevent.

### 1.5 Provenance recorded per run

Exact head SHA, base SHA, Python version, installed dependency versions, and the
**resident** NumPy/SciPy dispatch read from `threadpoolctl` — never the requested
`OPENBLAS_CORETYPE`, which is a request that can be silently ignored.

### 1.6 Constraints

- Does not retire V1.
- Introduces no tolerance, retry or rerun-to-green.
- Uses existing official GitHub Actions with least-privilege permissions.
- Protected-workflow changes require separate authorization; the amendment packet
  does not itself authorize them.

---

## Part 2 — V2-10 rollback, repeated on the final delivery version

### 2.1 Why the earlier demonstration is not sufficient

A rollback demonstrated **before** the V2 pack, comparator and CI gate were
integrated does not exercise those components. V2-10 is not satisfied by a revert
that predates them. The earlier demonstration is therefore retained as **historical
evidence only** and repeated below on the current delivery head.

### 2.2 Method

Single revert of the exact delivery commit, restore the intended baseline, then
**execute** the applicable V1 checks rather than inferring success from a missing
file.

```bash
DELIVERY=$(git rev-parse HEAD)          # exact delivery commit
BASE=$(git rev-parse origin/main)       # intended preserved baseline

git switch -c scratch/v2-10-final "$DELIVERY"
git revert --no-edit "$DELIVERY"

test "$(git rev-parse HEAD^{tree})" = "$(git rev-parse "$BASE^{tree}")"
PYTHONPATH=. python -m pytest \
  tests/experiments/test_offline_fixture_pack.py \
  tests/experiments/test_research_facade.py \
  tests/contracts -q
```

### 2.3 Acceptance criteria

| criterion | check |
|---|---|
| one command | single `git revert --no-edit` |
| baseline restored exactly | reverted `HEAD^{tree}` == `main^{tree}` |
| V1 intact and green | V1 fixture + facade + contract suites **execute** and pass |
| V2 pack/comparator/gate removed | implied by tree equality |
| no history rewrite | revert adds a commit |

### 2.4 Measured result

Recorded in §2.5 of the delivery PR body and in
`RH04_V2_VERIFICATION_COMMANDS_2026_11_21.md`. The demonstration is executed
against the final delivery head, after the workflow gate and the admission
corrections are present.

### 2.5 What rollback does not do

Does not close Issue #132, retract findings, or alter the ledger. Restores `main`
to its pre-delivery state; the analysis remains in the PR record.
