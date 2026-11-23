# RH-04 V2 — bounded final-acceptance checklist

**Document ID:** CAI-RH04-FINAL-CHECKLIST-v1
**Head:** `579659d036de9a5d35a083821e6aba8ec5d04f75` · **Base:** `main` `c6a6bdee`
· **PR #141** (Draft) · **Issue #132 OPEN**
**Status:** FOR INDEPENDENT REVIEW. Nothing here is closed. No gate is ratified.

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
| A4 | **Failure A (oracle) resolved in hosted CI** | 3.11 step 7 = `success` (0 failures) | run `45257655655` |
| A5 | **Failure B (base ref) resolved in hosted CI** | "Fetch trusted base reference" `success` on both runners; step 7 `success` | run `45257655655` |
| A6 | A4/A5 are causal, not coincidental | oracle absent → 1 failed; installed → 1 passed. No ref → 1 failed; after fetch → 1 passed | CI record §2 |
| A7 | Full local suite in corrected env | `2098 passed, 2 skipped` (22m28s) | CI record §2 |
| A8 | `pip check` clean | `No broken requirements found.` | CI record §2 |
| A9 | Lane B digest unchanged | `891d9e3b…`, `matches_reference: true` | CI record §2 |
| A10 | Protected V1 files untouched by maintainer commit | 4 files byte-identical to `main` | CI record §2 |
| A11 | V2-10 single-revert rollback on final delivery | reverted tree == `main` tree `3106bece…`; 0 V2 files; **457 V1 passed** | dual-run doc §2.4 |
| A12 | Admission mutation test discriminates | 1 traversal (fix) vs 4 (old) → `assert 4 == 1` | verification doc §7 |
| A13 | Approved-identity negative test | base request edited, IDs/edits/order preserved → refused | verification doc §7 |
| A14 | Ledger amended without reassigning IDs | 0 of 10 closed | ledger v3 |

---

## B. Blocking for final acceptance — requires a decision or an environment

### B1. Raise the 3.12 job budget — **owner decision required**

*Fact:* step 7 took **19.9 min** and was cancelled against `timeout-minutes: 20`;
locally the same command needs **22m28s**.

*Decision needed:* increase `timeout-minutes` on `synthetic-runner-tests`, or split
the suite into a separate job. Both are **workflow modifications** and were
explicitly out of scope this round.

*Consequence of doing nothing:* Python 3.12 suites remain **unmeasured** in CI, and
every run of this workflow ends `cancelled`. That is not a green check and must not
be reported as one.

*Evidence that closes it:* a run at ≥25 min budget where the 3.12 job reaches
`success` with 0 failures.

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

### B6. V2-04 — **owner decision on scope**

The original text demands `EXACT_REPLAY` across ≥3 dispatch classes × Linux 3.11/3.12
plus native Windows. Lane A cannot produce that: the frozen V1 reference diverges on
2 of 5 measured kernels, and the hosted diagnostic has been observed in **both**
states on identical workflow bytes.

*Decision needed:* ratify the two-lane amendment (V2-04a diagnostic / V2-04b
mandatory exact), or fund the full matrix against Lane A and accept it may never be
`EXACT_REPLAY`. **The matrix itself is not up for reduction.**

### B7. V2-05 dual-run window — **cannot be wired here**

The stage contract is written. Wiring it is a workflow change, and this round
forbade workflow modifications.

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
3. **A9–A10** — confirm the frozen scientific surface is untouched.
4. **B1** — decide the budget question. Without it, 3.12 stays unmeasured.
5. **B3/B4** — supply the two missing environments.
6. **B5/B6** — the two owner decisions that no amount of evidence from me can settle.

---

## E. One-paragraph honest summary

The maintainer applied the authorized patch, and it **worked**: both infrastructure
failures that were reproduced and fixed locally are now resolved in hosted CI — the
3.11 job ran the full suite to `success` with zero failures, and the base-reference
fetch step succeeded on both runners. That is a real result and it is the first time
this workflow has had a green full-suite job with the V2 tests present. But the run
as a whole is `cancelled`, not green, because the Python 3.12 job exhausted a 20-minute
budget in the suite step (19.9 min) that needs ~22.5 minutes in the corrected
environment — so 3.12 is **unmeasured**, not passing. The diagnostic passed in 13 s,
which must not be read as a fix, since the same command has now been observed both
red and green on identical workflow bytes. Zero acceptance gates are closed, nothing
is ratified, and the two decisions that remain (job budget; V2-04 scope and V2-01
ratification) are the owner's, not mine.
