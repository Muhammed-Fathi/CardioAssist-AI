# RH-04 V2 — bounded final-acceptance checklist

**Document ID:** CAI-RH04-FINAL-CHECKLIST-v1
**Head:** `579659d036de9a5d35a083821e6aba8ec5d04f75` · **Base:** `main` `c6a6bdee`
· **PR #141** (Draft) · **Issue #132 OPEN**
**Status:** FOR INDEPENDENT REVIEW. Nothing here is closed. No gate is ratified.
**Updated 2026-11-24** — final acceptance execution: implementation completed, CI patch
prepared, Windows script prepared, ratification wording prepared. See
`RH04_V2_ACCEPTANCE_LEDGER_RECONCILED_2026_11_24.md`.

This checklist is bounded on purpose: it lists only what must be **decided or
measured** for final acceptance, who can do it, and what evidence closes it. It does
not add scope, tolerance or acceptance criteria.

---

## A. Already evidenced at `579659d` — reviewer may verify and accept

| # | item | evidence | where |
|---|---|---|---|
| A1 | Maintainer patch is byte-identical to the authorized patch | `patch -p1` output `diff` vs `579659d` file: empty | CI record §0 |
| A2 | Commit `579659d` is workflow-only, +38 lines | `git show --name-only` | CI record §0 |
| A3 | Synchronization was fast-forward; nothing overwritten | `merge-base --is-ancestor` YES | CI record §0 |
| A4 | **Failure A (oracle) resolved in hosted CI** | 3.11 step 7 = `success` (0 failures) in **two** runs | `45257655655`, `45265423136` |
| A5 | **Failure B (base ref) resolved in hosted CI** | "Fetch trusted base reference" `success` on all four runner jobs; step 7 `success` | both runs |
| A6 | A4/A5 are causal, not coincidental | oracle absent → 1 failed; installed → 1 passed. No ref → 1 failed; after fetch → 1 passed | CI record §2 |
| A7 | Full local suite in corrected env | `2098 passed, 2 skipped` (22m28s) | CI record §2 |
| A8 | `pip check` clean | `No broken requirements found.` | CI record §2 |
| A9 | Lane B digest unchanged | `891d9e3b…`, `matches_reference: true` | CI record §2 |
| A10 | Protected V1 files untouched by maintainer commit | 4 files byte-identical to `main` | CI record §2 |
| A11 | V2-10 single-revert rollback on final delivery | reverted tree == `main` tree `3106bece…`; 0 V2 files; **457 V1 passed** | dual-run doc §2.4 |
| A12 | Admission mutation test discriminates | 1 traversal (fix) vs 4 (old) → `assert 4 == 1` | verification doc §7 |
| A13 | Approved-identity negative test | base request edited, IDs/edits/order preserved → refused | verification doc §7 |
| A14 | Ledger amended without reassigning IDs | 0 of 10 closed | ledger v3 |
| A15 | **Fully green hosted run — all three jobs, including Python 3.12** | run `45265423136` at `d3c35cb`: diagnostic `success`, 3.12 `success` (15.9 min), 3.11 `success` (15.4 min) | CI record §3 |
| A16 | All four workflows at `579659d` | `contract-validation` success, `audit-toolchain-validation` success, `mock-backend-validation` success, synthetic runner cancelled (3.12 only) | API run list |
| A17 | **Fully green hosted run, both interpreters** | Python 3.11 and 3.12: 2098 passed, 2 skipped; UCI-412 396 passed each; diagnostic success; mpmath 1.4.1; base ref `c6a6bde` | reviewer-verified logs, run `45265423136` |
| A18 | Lane A convergence, observed from the registered path | 100/100 fits satisfy the solver's own rule; 0 at iteration cap; residuals 1.527e-06 … 9.997e-05 | ledger v4 §V2-02 |
| A19 | Complete per-value mapping | 29/29 cases, 479 leaves, 0 numeric deltas, discrimination proof detects 1e-15 move | ledger v4 §V2-03 |
| A20 | V2-07 negatives are mutation-verified | all three guards caught when deliberately broken | ledger v4 §V2-07 |
| A21 | V2-facing semantics corrected | calibrated log-odds ≠ probability; fitted criterion named; limitations listed | semantics document |
| A22 | CI patch prepared and validated | applies cleanly, YAML parses, timeout 20→40, dual-run gate added | `workflow-patch/` |
| A23 | Windows verification script prepared | 336 lines, parametrised by expected SHA, fails RED without regenerating | `verify-native-windows.ps1` |
| A24 | Ratification wording prepared | three separable acts, no `DECISIONS.md` entry created | decision wording document |

---

## B. Blocking for final acceptance — requires a decision or an environment

### B1. Apply the CI patch — **owner action, decision already taken**

The owner approved raising the budget to 40 minutes. The patch is prepared,
validated (`patch --dry-run` clean, both files parse) and cannot be pushed from here
because the integration has no `workflows` scope.

*Action:* run `APPLY_AS_OWNER.ps1 -Confirm:$true`.
*Evidence that closes it:* a run where `synthetic-runner-tests` completes on both
interpreters at the 40-minute budget, plus the dual-run gate's own stage table.

### B2. Read the 3.12 test output — **needs logs or a budget fix**

No log endpoint works from here (`EOF` from Azure blob and from
results-receiver). Even with a larger budget, the pass/fail tally would need either
working log access or a reviewer with one.

*Evidence that closes it:* step 7 on 3.12 reported `success` (proves 0 failures) **or**
the actual pytest summary. A `success` conclusion is sufficient for acceptance; the
tally is desirable, not required.

### B3. Python 3.12 Lane B replay, locally — **needs a 3.12 interpreter**

```bash
python3.12 -m venv .venv-rh04-312
. .venv-rh04-312/bin/activate
python -m pip install -r research/uci412/requirements.txt \
                       -r research/experiments/requirements-oracle.txt \
                       -r tests/contracts/requirements.txt
python -m pip check
python -m pytest tests/experiments/test_rh04_v2_reference.py -q
python -m research.intake.rh04_v2_portable_archive research/intake/fixtures/rh04_v2_portable
```

Expect 278 passed and digest `891d9e3b…` with `matches_reference: true`.
**Not measured** — no 3.12 interpreter in this sandbox.

### B4. Native Windows — **needs a Windows host**

```powershell
py -3.11 -m venv .venv-rh04
.\.venv-rh04\Scripts\Activate.ps1
python -m pip install -r research\uci412\requirements.txt `
                       -r research\experiments\requirements-oracle.txt `
                       -r tests\contracts\requirements.txt
python -m pip check
python -m pytest tests\experiments\test_rh04_v2_reference.py -q
python -m research.intake.rh04_v2_portable_archive research\intake\fixtures\rh04_v2_portable
```

**Not measured** — no Windows host. Required by V2-04a/b, which the amendment
retains verbatim.

### B5. V2-01 owner ratification — **owner only**

Requires a `docs/DECISIONS.md` entry naming the accepting reviewer and the decision
document version. I cannot ratify my own work, and no such entry exists.

### B6. V2-04 — **owner decision on scope (direction approved, matrix still open)**

The original text demands `EXACT_REPLAY` across ≥3 dispatch classes × Linux 3.11/3.12
plus native Windows. Lane A cannot produce that: the frozen V1 reference diverges on
2 of 5 measured kernels, and the hosted diagnostic has been observed in **both**
states on identical workflow bytes.

*Direction approved:* the owner approved the two-lane direction in CAI-RH04-AMEND-v3
and directed that the complete cross-environment matrix be preserved. Ratification
wording is prepared in `RH04_V2_DECISION_REGISTER_WORDING_2026_11_24.md`.

*Still outstanding:* the matrix itself. ≥3 resident dispatch classes per Linux Python
version plus native Windows has not been executed, so V2-04a and V2-04b remain
partially evidenced. **The matrix is not reduced.**

### B7. V2-05 dual-run window — **patch prepared, needs owner push**

`rh04-dual-run-gate.yml` is written and its stage independence was tested locally
(a failing Lane A left the other stages reporting and the gate failed). Applying it
requires the same owner action as B1.

### B8. V2-06 — **activation change, out of scope**

Production `calibration.json`, `scale_declaration`, model cards and manifest wording
are untouched by design.

### B9. Two smaller V2 gaps

- **V2-03:** per-expected-value delta table across all 29 cases is still missing.
- **V2-07:** remaining item is the unreachable-criterion negative test, reconciled in
  the amendment as unreachable *by construction* in Lane B.

---

## C. Explicitly out of bounds — do not do these to close a gate

| forbidden | why |
|---|---|
| `continue-on-error`, `if: always()`, retry loops on step 7 | hides the failure; no-go |
| raising the budget **only** to convert red to green without measuring 3.12 | the measurement is the point |
| editing the diagnostic's expectation to match a run | forbidden by standing rules |
| adding a numeric tolerance to the diagnostic | forbidden; V2-08 no new tolerance |
| skipping the mpmath test when the oracle is absent | the test's fail-closed behaviour is the evidence |
| deleting or weakening `test_child_diagnosis_does_not_modify_…` | it is the preservation guarantee |
| merging #141 or closing #132 | owner act only |

---

## D. Suggested review order

1. **A1–A3** — confirm the maintainer's commit is what was authorized and nothing was
   overwritten.
2. **A4–A6** — confirm both infrastructure failures are resolved and that the causal
   experiments actually demonstrate the fix.
3. **A15** — note that `d3c35cb` is a **fully green run**: all three jobs including
   Python 3.12. This is the strongest single piece of CI evidence in the delivery.
4. **A9–A10** — confirm the frozen scientific surface is untouched.
5. **B1** — decide the run-time margin question. It is reliability, not correctness.
6. **B3/B4** — supply the two missing environments.
7. **B5/B6** — the two owner decisions that no amount of evidence from me can settle.

---

## E. One-paragraph honest summary

The maintainer applied the authorized patch and it **worked**. Both infrastructure
failures are resolved in hosted CI: the full suite passed on Python 3.11 in two
separate runs with zero failures, the base-reference fetch succeeded on every runner
job, and each fix was additionally confirmed by a controlled experiment with the
fault present and absent. Then a follow-up run at `d3c35cb` came back **fully green** —
all three jobs, including **Python 3.12 at 15.9 min** — which is the strongest CI
evidence in this delivery and the first time this workflow has passed end to end with
the V2 tests present.

One observation needs care rather than celebration: the same suite step measured
15.4, 15.4, 15.9 and 19.9 minutes across four runs, and the 19.9 one was cancelled
against a 20-minute budget. So 3.12 is **not** systematically broken — it passed — but
the margin is thin enough that a slow runner can leave it unmeasured, which must be
reported as unmeasured rather than assumed green. That is a reliability decision for
the owner, not a defect I should paper over by editing a workflow.

The 3.12 diagnostic passed in 13 s, which is still **not** a fix: the same command has
now been observed red and green on identical workflow bytes, consistent with the
measured kernel dependence. Zero acceptance gates are closed, nothing is ratified, and
the two decisions that remain — the run-time margin and V2-04 scope plus V2-01
ratification — are the owner's, not mine.
