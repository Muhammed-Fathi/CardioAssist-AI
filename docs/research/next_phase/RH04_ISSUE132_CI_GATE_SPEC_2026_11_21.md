# RH-04 Issue #132 — proposed CI **observation** step (SPECIFICATION ONLY)

**Status:** `PROPOSED — NOT APPLIED`. **No workflow file is modified by this branch.**
**Nature: NON-VOTING OBSERVATION.** This document specifies a step that records
evidence and nothing else. It is **not** a gate: it cannot pass or fail a job,
and it must not be described as "failing closed" at the CI level, because at that
level it never fails at all. The *classifier* fails closed (exit 2); the *CI
step* records the classifier's output and always succeeds.
**Companion to:** [`docs/rh04-issue132-acceptance-decision.md`](../../../docs/rh04-issue132-acceptance-decision.md) §6 Step 2 and Step 3.
**Why a separate document:** `.github/workflows/experiment-runner-ci.yml` is a frozen-adjacent file (Issue #132 forbids changing the Golden Replay workflow as part of the investigation). The step therefore ships as a reviewable patch *text* in the follow-up implementation PR, not as an applied edit here.

---

## 0. Observation, not enforcement — read this first

Two different things are easy to conflate, and the first revision of this
document did conflate them:

| Layer | Fails closed? | Can it change a job result? |
|---|---|---|
| `research/intake/rh04_environment_class.py` (the classifier) | **Yes** — exit `2` on anything unenumerated, malformed or unverified | No: it is an ordinary command |
| The proposed CI step (below) | **No** — it deliberately exits `0` for every classifier outcome | **No** |

So this proposal does **not** fail closed *in CI*, and it does not claim to. Its
entire purpose is to leave a durable record of which resident kernels a job used,
because the historical failure could not be attributed for exactly the lack of
that record. The canonical `pytest tests/experiments tests/audit` step remains
the sole pass/fail authority and is **not modified**.

If an owner later wants a step that can *fail* a job on unexpected environment
observations, that is a **different, explicitly authorized** piece of work — a
voting diagnostic gate. It is not this document, and this document must not be
read as proposing it implicitly. See §7.

## 1. What the step must and must not do

| Must | Must not |
|---|---|
| Record the **resolved** OpenBLAS kernel for NumPy *and* SciPy | Trust `OPENBLAS_CORETYPE` (measured silent fallbacks: `Cooperlake` → SciPy `SkylakeX`; `Atom` → NumPy `Nehalem`; `Zen` → SciPy `Haswell`) |
| Distinguish three outcomes: bit-exact, classified-expected, unexpected | Collapse them into "green" *or* let any of them change the canonical job result |
| Make the **classifier** fail closed (exit 2) on anything not enumerated | Describe the **CI step** as fail-closed: the step always exits 0 by design |
| Be labelled explicitly as **non-voting observation** in the step name and summary | Use skip, xfail, `continue-on-error`, `|| true` or re-run **to keep the canonical Golden Replay step green** |
| Stay non-scoring and read-only | Rewrite, regenerate or re-derive any expected value |
| Emit only kernel names, versions, booleans, counts, delta magnitudes | Emit a score, coefficient, intercept, slope, feature value, record, key or path |
| Leave the canonical pytest step's exit code authoritative | Replace, wrap or duplicate `test_golden_replay` |

## 2. Mechanism

The tool is `research/intake/rh04_environment_class.py` (added by this branch), already implemented and tested:

```bash
python -m research.intake.rh04_environment_class
```

Exit codes (deliberately distinct, so a shell step can branch without parsing JSON):

| Exit | `status` | Meaning |
|---|---|---|
| `0` | `EXACT_REPLAY` | frozen pack reproduced bit-for-bit on this host |
| `1` | `EXPECTED_SINGLE_FIELD_DELTAS` | a validated envelope with exactly the enumerated mismatch, each reported inside the AI-12.1 band — **supplemental evidence, never a pass** |
| `2` | `UNEXPECTED_DRIFT`, `INVALID_DIAGNOSTIC`, `DIAGNOSTIC_REFUSED`, or `UNVERIFIED_ENVIRONMENT` | anything else — **fail closed** |

Verified locally on this branch:

| Dispatch | `numpy_openblas_kernel` | `scipy_openblas_kernel` | `status` | exit |
|---|---|---|---|---|
| host | `SkylakeX` | `SkylakeX` | `EXACT_REPLAY` | 0 |
| `OPENBLAS_CORETYPE=Haswell` | `Haswell` | `Haswell` | `EXPECTED_SINGLE_FIELD_DELTAS` | 1 |

## 3. Proposed workflow patch (for the follow-up PR — do not apply blindly)

> **Revised after independent review.** The first revision mapped the
> classifier's "classified deltas" exit code to `exit 0` for the diagnostic
> step, which contradicted the promise that the canonical gate stays strict and
> that no P-3 comparator policy is adopted. Under the §5 policy of the decision
> document, **no step may convert a canonical Golden Replay failure into CI
> success.** The diagnostic is strictly additive evidence.

Add **after** `Verify pinned CPU numerical threadpools` and **before** `Run
synthetic experiment-runner and dataset-audit tests`, in `synthetic-runner-tests`.
Repeat verbatim in `rh04-fixture-diagnostic`.

```yaml
      # RH-04 Issue #132: record the ACTUAL resident OpenBLAS kernels and the
      # classified replay outcome. Read-only, non-scoring, synthetic-only.
      # Exit 0 = exact + verified env; 1 = classified single-field deltas
      # (supplemental evidence, NOT a pass); 2 = fail closed.
      # This step does NOT and MUST NOT decide the job's result: the canonical
      # pytest Golden Replay step below remains authoritative and unchanged.
      - name: Record RH-04 environment and replay classification
        run: |
          set +e
          python -m research.intake.rh04_environment_class
          code=$?
          echo "RH04_CLASSIFICATION_EXIT=${code}" >> "$GITHUB_STEP_SUMMARY"
          case "${code}" in
            0) verdict=EXACT_REPLAY ;;
            1) verdict=EXPECTED_SINGLE_FIELD_DELTAS ;;
            *) verdict=INVALID_OR_UNVERIFIED ;;
          esac
          echo "RH04_CLASSIFICATION=${verdict}" >> "$GITHUB_STEP_SUMMARY"
          echo "RH04_NOTE=non-voting observation; canonical pytest gate unchanged" >> "$GITHUB_STEP_SUMMARY"
          exit 0
```

Design notes for the reviewer:

1. **The diagnostic step never votes.** Every classified outcome — including
   exit 2 — is a *datum*, not a test result, so the step records it and then
   exits 0. Deliberately, it uses **no** `continue-on-error` and **no**
   `|| true`: those would suppress a *failure*, whereas this step has no
   pass/fail semantics to suppress. The canonical
   `pytest tests/experiments tests/audit` step remains the sole authority, and
   it is byte-identical to `main`.
2. **This is deliberately weaker than "fail the job if unexpected drift".** The
   reason is that a workflow change of that kind would alter the pass/fail
   semantics of a frozen-adjacent CI file, which this decision PR is explicitly
   not authorized to do. An owner may later choose to promote the diagnostic to
   a voting gate; that is a policy decision requiring its own review (§7).
3. `set +e` exists only to capture the exit code before the final `exit 0`; the
   canonical step is unaffected.
4. The step must run **after** dependency installation, because the kernel names
   are read from the installed wheels, and **before** the scoring step, so the
   evidence exists even when the scoring step fails.
5. `RTLD_NOLOAD` only. The first revision used `RTLD_GLOBAL`, which loaded a
   private BLAS copy that the numerical code had not used (decision document
   `G-08`).

## 4. Negative-test requirements for the follow-up PR

Each of the following must be demonstrated to **fail** before the step is accepted:

| # | Injected condition | Required behaviour |
|---|---|---|
| `N-01` | A third case drifts | `UNEXPECTED_DRIFT`, exit 2 |
| `N-02` | A second field drifts in `da_a1_basic_clinical_v1` | `UNEXPECTED_DRIFT`, exit 2 |
| `N-03` | A `calibrated_log_odds` delta moves outside `rel_tol=1e-9`/`abs_tol=1e-12` | `UNEXPECTED_DRIFT`, exit 2 |
| `N-04` | `PACK_SHA256` changes | canonical validator refuses independently (existing behaviour must still hold) |
| `N-05` | Case count ≠ 29 | canonical validator refuses |
| `N-06` | A boolean/tolerance field is emitted as `0`/`1` instead of `true`/`false` | `UNEXPECTED_DRIFT` (type strictness, not truthiness) |
| `N-07` | The classifier raises | `DIAGNOSTIC_REFUSED`, exit 2, no exception text in output |
| `N-08` | A `pytest.skip`/`xfail` is introduced around `test_golden_replay` | existing suite count/behaviour changes — review must catch it |
| `N-09` | `_approved_replay_equal` gains a UCI-412 branch | `test_uc412_case_still_has_no_tolerance_exception` fails |
| `N-10` | `ABS_TOL`/`REL_TOL` widened | `test_report_comparator_tolerances_untouched` fails |

`N-01`…`N-07`, `N-09`, `N-10` are already covered by `tests/experiments/test_rh04_issue132_environment_class.py` on this branch. `N-08` is a review obligation, not a test.

## 5. What this specification deliberately excludes

- No `OPENBLAS_CORETYPE` pin of any kind (PR #134's `SkylakeX` pin is falsified: `CPU does not expose avx512f`).
- No `NPY_DISABLE_CPU_FEATURES` guard (PR #134; measured ineffective under `HASWELL` in run `44896568228`).
- No AVX-512 preflight, no hardware assertion, no conditional skip.
- No change to `OPENBLAS_NUM_THREADS`/`OMP_NUM_THREADS` (measured irrelevant: 1/2/4 identical).
- No change to `research/intake/fixtures/offline_io.v1.json`, `PACK_SHA256`, `ai/report_comparison.py`, `ai/calibration.py`, or the scoring step.

## 7. What a *voting* gate would additionally require (NOT proposed here)

Recorded so that the difference is explicit and cannot be adopted by accident.
A step that is allowed to fail a job on environment observations needs, at
minimum:

1. An owner decision that a non-`SkylakeX` SciPy kernel should block a merge,
   which is a **workflow policy change**, not a documentation change.
2. Its own PR that modifies `.github/workflows/*`, explicitly authorized.
3. Proof that the canonical Golden Replay step is untouched and still
   authoritative — i.e. the new gate is *additive*, never a replacement.
4. A deliberate answer to the failure mode this document avoids: on the present
   hosted runners, a non-`SkylakeX` SciPy kernel is common (measured here for
   `Haswell`, `Zen`, `Sandybridge`, `Nehalem`, `Atom`, `Prescott`), so a voting
   gate would be red far more often than green. That may be the correct policy,
   but it must be chosen knowingly, not slipped in as a "diagnostic".

This branch proposes **none** of the above. It records evidence only.
