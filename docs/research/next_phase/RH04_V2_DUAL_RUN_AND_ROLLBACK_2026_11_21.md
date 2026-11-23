# Dual-run workflow and single-revert rollback — proposals

**Document ID:** CAI-RH04-DUALROLLBACK-v1
**Status:** PROPOSAL. Nothing implemented. Two V2-09/§7 planning deliverables.

---

## Part 1 — Dual-run workflow (V2-05)

### 1.1 What V2-05 asks for

An acceptance decision that rests on two independent runs, not one, so that a
single green run cannot be mistaken for reproducibility.

### 1.2 Existing repository policy this reuses

No new policy is introduced. The workflow composes mechanisms that already exist:

| mechanism | existing location | role here |
|---|---|---|
| compiled-in trust anchor | `TRUSTED_MANIFEST_SHA256` | both runs must hit the same anchor |
| fixed reference digest | `LANE_B_REFERENCE_DIGEST` | both runs must equal it |
| raw-byte pre-parse gate | `admit_from_directory` | both runs verify file identity |
| CLI non-zero exit | `main()` | machine-checkable pass/fail per run |
| sanitised JSON evidence | CLI stdout | comparable without leaking content |

### 1.3 Proposed workflow

**Run 1 — resident default environment.** No dispatch override.

**Run 2 — a *different* resident dispatch class**, recorded as measured, not as
requested.

```
R1 = python -m research.intake.rh04_v2_portable_archive <dir>
R2 = OPENBLAS_CORETYPE=<class> python -m ... <dir>
```

**Acceptance rule (all four must hold):**

1. `R1.exit == 0` and `R2.exit == 0`
2. `R1.digest == R2.digest == LANE_B_REFERENCE_DIGEST`
3. `R1.matches_reference is True` and `R2.matches_reference is True`
4. `R1.statuses == R2.statuses` (exact, not per-key)

**Failure rule.** Any of 1–4 failing is a **finding to investigate**, never a
threshold to relax. There is no agreement tolerance anywhere in this workflow, and
`R1.digest != R2.digest` is not permitted to pass as "close enough".

### 1.4 Why this is stronger than a single run

The two runs differ in exactly one variable that has historically produced
different results on the registered training path: BLAS dispatch. Lane B is
claimed to be invariant to it. If that claim is false, dual-run is the cheapest
place to find out.

### 1.5 What dual-run does not establish

It is not a substitute for a different OS, a different Python minor version, or
non-x86 hardware. Those are separate gaps, named in the evidence register.

---

## Part 2 — Single-revert rollback plan

### 2.1 The design constraint

Rollback must be **executable by one person who did not write the code**, using one
command, and must leave `main` in a state that still passes the tests `main`
already had.

Because the V2 work is additive relative to `main` (§3.1 of the SHAP remediation
document: main contains **no** `rh04_v2_*` module and **no** `rh04_v2_portable/`
fixture directory), the rollback is a plain revert with no dependency untangling.

### 2.2 Recommended rollback: revert the delivery commit

```bash
# 1. Identify the delivery commit on main.
DELIVERY=$(git log --format=%H --grep="rh04(v2): portable Lane B acceptance" -n 1 main)
test -n "$DELIVERY" || { echo "delivery commit not found"; exit 1; }

# 2. Revert it as a single commit.
git switch -c rollback/rh04-v2 main
git revert --no-edit "$DELIVERY"

# 3. Prove main's prior state is restored.
git diff --stat main HEAD          # MUST show only the reverted paths
PYTHONPATH=. python -m pytest tests/experiments/test_rh04_v2_reference.py -q \
  && echo "FAIL: V2 tests still present after revert"
```

### 2.3 Acceptance criteria for a successful rollback

| criterion | check |
|---|---|
| no V2 module remains | `test ! -e research/intake/rh04_v2_portable_archive.py` |
| no V2 fixture remains | `test ! -d research/intake/fixtures/rh04_v2_portable` |
| main's own tests still pass | focused run on a non-V2 file |
| V1 untouched | V1 pack/comparator digests unchanged |
| no production file changed | the 12 protected files still byte-identical |

### 2.4 Why not a force-push rollback

Force-pushing `main` back to `c6a6bde` would rewrite published history, break
every clone and open PR, and destroy the evidence that a defect existed. A revert
commit preserves the record and is reversible itself. Standing instruction forbids
history rewrite without explicit authorization, and it is not needed here.

### 2.5 Partial rollback (Lane B only)

If only the portable lane must be withdrawn while Lane A stays:

```bash
git revert --no-edit <lane-b-commit>   # the commit adding rh04_v2_portable_archive.py
```

This is safe **because Lane B has no inbound dependents outside the V2 work
itself**. Measured by inspecting imports at the delivery SHA:

```
importers of rh04_v2_portable_archive:
  research/intake/rh04_v2_portable_inference.py   (branch-only V2 code)
  tests/experiments/test_rh04_v2_reference.py     (branch-only V2 tests)

references under ai/ or backend/:  none
```

Both importers are themselves part of the V2 delivery, so a partial rollback must
revert them together. Nothing in the production package depends on Lane B.

### 2.6 What rollback does not do

It does not close Issue #132, does not retract the review findings, and does not
alter the acceptance ledger. It returns `main` to its pre-delivery state and
leaves the analysis intact in the PR record.
