# RH-04 Issue #132 — proposed CI classification gate (SPECIFICATION ONLY)

**Status:** `PROPOSED — NOT APPLIED`. **No workflow file is modified by this branch.**
**Companion to:** [`docs/rh04-issue132-acceptance-decision.md`](../../../docs/rh04-issue132-acceptance-decision.md) §6 Step 2 and Step 3.
**Why a separate document:** `.github/workflows/experiment-runner-ci.yml` is a frozen-adjacent file (Issue #132 forbids changing the Golden Replay workflow as part of the investigation). The gate therefore ships as a reviewable patch *text* in the follow-up implementation PR, not as an applied edit here.

---

## 1. What the gate must and must not do

| Must | Must not |
|---|---|
| Record the **resolved** OpenBLAS kernel for NumPy *and* SciPy | Trust `OPENBLAS_CORETYPE` (observed to silently fall back: `Zen` → `Haswell`) |
| Distinguish three outcomes: bit-exact, classified-expected, unexpected | Collapse them into "green" |
| Fail closed on anything not enumerated | Skip, xfail, `continue-on-error`, or re-run |
| Stay non-scoring and read-only | Rewrite, regenerate or re-derive any expected value |
| Emit only kernel names, versions, booleans, counts, delta magnitudes | Emit a score, coefficient, intercept, slope, feature value, record, key or path |
| Leave the canonical pytest step's exit code authoritative | Replace, wrap or duplicate `test_golden_replay` |

## 2. Mechanism

The gate is `research/intake/rh04_environment_class.py` (added by this branch), already implemented and tested:

```bash
python -m research.intake.rh04_environment_class
```

Exit codes (deliberately distinct, so a shell step can branch without parsing JSON):

| Exit | `status` | Meaning |
|---|---|---|
| `0` | `EXACT_REPLAY` | frozen pack reproduced bit-for-bit on this host |
| `1` | `EXPECTED_SINGLE_FIELD_DELTAS` | exactly the two enumerated `(case, field)` pairs, each inside the AI-12.1 band |
| `2` | `UNEXPECTED_DRIFT` or `DIAGNOSTIC_REFUSED` | anything else — **fail closed** |

Verified locally on this branch:

| Dispatch | `numpy_openblas_kernel` | `scipy_openblas_kernel` | `status` | exit |
|---|---|---|---|---|
| host | `SkylakeX` | `SkylakeX` | `EXACT_REPLAY` | 0 |
| `OPENBLAS_CORETYPE=Haswell` | `Haswell` | `Haswell` | `EXPECTED_SINGLE_FIELD_DELTAS` | 1 |

## 3. Proposed workflow patch (for the follow-up PR — do not apply blindly)

Add **after** `Verify pinned CPU numerical threadpools` and **before** `Run synthetic experiment-runner and dataset-audit tests`, in `synthetic-runner-tests`. Repeat verbatim in `rh04-fixture-diagnostic`.

```yaml
      # RH-04 Issue #132: record the ACTUAL OpenBLAS kernels and classify the
      # Golden Replay outcome. Read-only, non-scoring, synthetic-only.
      # Exit 0 = bit-exact; exit 1 = exactly the two documented calibrated-log-odds
      # deltas inside the pre-existing AI-12.1 band; exit 2 = fail closed.
      # This step never changes, relaxes or replaces the scoring pytest step below.
      - name: Classify RH-04 Golden Replay outcome for this host
        run: |
          set +e
          python -m research.intake.rh04_environment_class
          code=$?
          echo "RH04_CLASSIFICATION_EXIT=${code}"
          case "${code}" in
            0) echo "RH04_CLASSIFICATION=EXACT_REPLAY" >> "$GITHUB_STEP_SUMMARY"; exit 0 ;;
            1) echo "RH04_CLASSIFICATION=EXPECTED_SINGLE_FIELD_DELTAS" >> "$GITHUB_STEP_SUMMARY"; exit 0 ;;
            *) echo "RH04_CLASSIFICATION=UNEXPECTED_OR_REFUSED" >> "$GITHUB_STEP_SUMMARY"; exit 1 ;;
          esac
```

Design notes for the reviewer:

1. `set +e` exists **only** to capture the exit code of the classifier; the step's own success is then explicitly re-derived from that code. It does not weaken the scoring step.
2. **`EXPECTED_SINGLE_FIELD_DELTAS` is mapped to exit `0` for this diagnostic step only.** The scoring `pytest` step is untouched and still fails on `da_a1_basic_clinical_v1` under a non-golden dispatch. That asymmetry is the *point*: the classification is recorded as evidence, and the contract is not silently relaxed. **Shipping a green CI therefore requires an owner-approved comparator or V2 decision (§6/§7 of the decision document) — not this step.**
3. If the owner prefers CI to remain red until V2, **drop the `1)` branch**; the step then fails on any non-golden host while still recording the kernel names. Both variants are compatible with this specification; the choice is an acceptance decision, not an implementation detail.
4. The step must be added **after** dependency installation, because the kernel names are read from the installed wheels.

## 4. Negative-test requirements for the follow-up PR

Each of the following must be demonstrated to **fail** before the gate is accepted:

| # | Injected condition | Required behaviour |
|---|---|---|
| `N-01` | A third case drifts | `UNEXPECTED_DRIFT`, exit 2 |
| `N-02` | A second field drifts in `da_a1_basic_clinical_v1` | `UNEXPECTED_DRIFT`, exit 2 |
| `N-03` | A `calibrated_log_odds` delta moves outside `rel_tol=1e-9`/`abs_tol=1e-12` | `UNEXPECTED_DRIFT`, exit 2 |
| `N-04` | `PACK_SHA256` changes | canonical validator refuses before the gate runs (existing behaviour must still hold) |
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
