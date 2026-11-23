# Exact-head CI record — run 45257655655 at `579659d`

**Document ID:** CAI-RH04-CI-RECORD-579659D
**Supersedes the CI sections of** `RH04_V2_VERIFICATION_COMMANDS_2026_11_21.md`
(§8 and §9, which describe the state *before* the maintainer applied the patch).
**Status:** evidence record. No gate is closed.

---

## 0. Synchronization

The maintainer's commit was taken by fast-forward, not by rewrite:

```
local    9c94e0c83cd2958c775500d1ed592a9071d7e32e
remote   579659d036de9a5d35a083821e6aba8ec5d04f75

git merge-base --is-ancestor 9c94e0c 579659d   ->  YES (ancestor)
git merge --ff-only origin/delivery/rh04-v2-final ->  Fast-forward
```

Nothing was overwritten and no history was rewritten. The maintainer's commit is
**workflow-only**:

```
579659d ci: install required oracle and fetch trusted base reference
 .github/workflows/experiment-runner-ci.yml | 38 ++++++++++++++++++++
```

It was verified to be **byte-identical** to the authorized patch: applying
`docs/research/next_phase/ci-oracle-and-base-ref.patch` to `main`'s workflow produces
exactly the file committed at `579659d` (`diff` empty). No gap or extra hunk.

`main` unchanged at `c6a6bdee46a552a2b0d705a723c862ff8a95be4d`.

---

## 1. Run 45257655655 — actual job outcomes

| job | id | conclusion | note |
|---|---|---|---|
| RH-04 fixture diagnostic (3.12) | `137983666101` | **success** | 0.62 min, step 6 = 13.0 s |
| Synthetic experiment runner (3.11) | `137983666602` | **success** | 18.0 min, full suite |
| Synthetic experiment runner (3.12) | `137983666512` | **cancelled** | job budget exhausted at step 7 |
| *run* | — | **cancelled** | because one job was cancelled |

### Step 3 "Fetch trusted base reference" — both runners

```
3. Fetch trusted base reference   success   (3.11)
3. Fetch trusted base reference   success   (3.12)
```

### Python 3.11 — every step green

```
 7. Run synthetic experiment-runner and dataset-audit tests   success  15.4 min
 9. Run synthetic UCI-412 benchmark tests                     success   0.5 min
10. Execute the registered synthetic-only dry-run             success   1.6 min
11. Describe the proposed (unauthorized) UCI-412 protocol      success
12. Execute the registered UCI-412 synthetic-only dry-run      success
13. Verify source-material integrity                           success
14. Reject real datasets or generated artifacts                success
```

**This is the load-bearing result.** Step 7 is the step that produced
`2 failed, 2094 passed, 2 skipped` at `f78f521`. At `579659d` it returned **success**,
which by definition means **zero failures**. Both previously identified
infrastructure failures were in that step, so both are resolved in hosted CI.

### Python 3.12 — cancelled at the suite step

```
 7. Run synthetic experiment-runner and dataset-audit tests   CANCELLED  19.9 min
 8. Diagnose RH-04 fixture drift (if: failure() && 3.12)      skipped
 9-14                                                         skipped
```

Job started `20:16:36Z`, completed `20:36:52Z` = **20.27 min** against
`timeout-minutes: 20`. Step 7 alone consumed 19.9 min and was terminated. The
conclusion is `cancelled`, **not** `failure`.

Because step 7 never returned non-zero, step 8 — the diagnostic guarded by
`if: failure() && matrix.python-version == '3.12'` — was **skipped**. So the 3.12
job provides **no test result and no diagnostic result**. It is **unmeasured**, not
failed and not passing.

---

## 2. Which failures are resolved — stated exactly

| # | failure at `f78f521` | resolved? | evidence |
|---|---|---|---|
| A | `test_model_fit_matches_an_independent_mpmath_oracle` — no `mpmath` | **YES** | 3.11 step 7 success (0 failures) + controlled local experiment below |
| B | `test_child_diagnosis_does_not_modify_the_merged_classifier_surface` — no `origin/main` | **YES** | "Fetch trusted base reference" success on both runners + 3.11 step 7 success + controlled local experiment below |
| C | 3.12 diagnostic `MISMATCH_FOUND` | **NOT REPRODUCED HERE** | ran 13.0 s and passed. This is *not* a fix: the divergence is environment-dependent (see §4) |

### Controlled experiments for A and B

Each fix was tested with the fault present and absent, so the causal link is
measured rather than assumed.

**A — oracle present/absent, same interpreter, same tree:**

| condition | command | result |
|---|---|---|
| oracle absent | `pytest -k independent_mpmath_oracle` | **1 failed** — `the independent oracle is required evidence` |
| oracle installed | same | **1 passed** |

**B — base ref absent/present, real shallow single-branch clone:**

| condition | result |
|---|---|
| before fetch | `git rev-parse --verify origin/main` → `fatal: Needed a single revision`; test **1 failed** |
| after `git fetch --no-tags origin "+refs/heads/main:refs/remotes/origin/main"` | `base_ref=c6a6bdee…`; test **1 passed** |

The command in that second row is the exact command the new workflow step runs.

### Full local suite in the corrected environment

```
pytest tests/experiments tests/audit -q -W error
2098 passed, 2 skipped in 1348.80s (0:22:28)
```

`pip check` → `No broken requirements found.` Lane B digest
`891d9e3b2a332c6efc251d97fee25ed46a627ed25b2a089594057b4c9896cdc8`,
`matches_reference: true`. Protected V1 files byte-identical to `main`:
`offline_fixture_pack.py`, `fixtures/offline_io.v1.json`,
`test_offline_fixture_pack.py`, `ai/report_comparison.py`.

---

## 3. The new blocker is a job budget, not a dependency

`timeout-minutes: 20` on `synthetic-runner-tests`, measured locally at
**22m28s** for the same command in the corrected environment.

The suite grew across this workstream (2094 → 2098 passing tests, and the V2
reference module alone takes ~13 min). The job has less headroom than the suite
needs, and 3.12 is slower than 3.11 — at `f78f521` the same step failed at ≈13.6 min
on both runners; now 3.11 succeeded at 15.4 min while 3.12 hit 19.9 min.

So the infrastructure failures are fixed and a **capacity** problem is now exposed.
The honest reading: the 3.12 job did not fail, it ran out of time.

**Not changed, and deliberately not changed this round.** Raising
`timeout-minutes` is a workflow modification, and the instruction for this round is
explicitly *no workflow modifications*. Recording the measurement is the correct
action; editing the budget is a separate authorized decision, because a budget
change alters what CI proves (a suite that needs 25 min silently "passes" a 20-min
budget only if someone inflates the budget until it does).

---

## 4. Diagnostic status — a pass that must not be over-read

The diagnostic passed here in **13.0 s**. It also failed at `f78f521`
(`MISMATCH_FOUND`, 2 differing cases) and passed at `89b0a8f`, on a workflow whose
bytes were identical to `main`'s.

The status is therefore **environment-dependent and non-deterministic per run**, and
the local kernel sweep is consistent with that:

| resident kernel | differing cases |
|---|---|
| unset | 0 |
| Prescott | 2 |
| Haswell | 2 |
| Nehalem | 1 |
| Sandybridge | 1 |

A green diagnostic is one draw from a distribution that has been observed in both
states. It is **not** presented here as evidence that the V1 replay is correct, and
the earlier claim that the diagnostic was a fixed infrastructure failure remains
withdrawn.

---

## 5. What this round does not establish

| item | status |
|---|---|
| 3.12 suite result | **UNMEASURED** — cancelled at 19.9 min, no assertion output |
| 3.12 diagnostic | **not run** in run `45257655655` (skipped); passed separately in `137983666101` |
| the failing assertion, if any, on 3.12 at `579659d` | **unknown** — no logs are retrievable |
| job logs | **unreachable** — Azure blob and results-receiver both return `EOF` |
| Linux 3.12 Lane B replay locally | **not measured** — no 3.12 interpreter in this sandbox |
| native Windows | **not measured** — no host |
| V2 acceptance gates | **0 of 10 closed**; nothing ratified |

Every count above comes from the workflow/job/step API, never from log text, because
log text cannot be fetched. Counts from step 7 are quoted as **success** rather than
as a pass/fail tally: a successful pytest run means zero failures, but the exact
pass total is not visible to me and is not invented.
