# RH-04 Issue #132 — engineering acceptance decision for intermittent UCI-412 Golden Replay drift

**Document version:** `rh04.issue132.acceptance-decision/v1`
**Status:** `PROPOSED — NOT RATIFIED`. Decision record only. **No production behaviour, fixture, digest, comparator, tolerance or workflow file is changed by this branch.**
**CI status — two distinct facts, do not conflate them:**
* *Historical:* head `d271dee` had a **failing** `synthetic-experiment-runner-validation` run ([44919728501](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/44919728501)) carrying the exact Issue #132 signature on a docs-only diff. That run was **not** re-run to green, because Issue #132 forbids rerun-until-green.
* *Current:* the final head of this PR has **all workflows passing** (see the PR's own checks and the final report comment). A later commit — differing only in documentation — was green on a different VM set.

Neither fact is an acceptance claim, and neither is a "controlled experiment". See §1.3 for what the red/green pair does and does not establish.
**Scope:** research-only, synthetic-only engineering reproducibility. Not a scientific, clinical, model-performance, RH-07 or RH-08 acceptance.
**Supersedes:** nothing. It *reads* `docs/rh04-portable-deterministic-calibration.md` (merged via PR #135) and adds the acceptance decision that document explicitly declined to make.
**Base commit:** `10bee67474b0eb9858f4ca6f298037c2f32459cc` (`main`, verified `git rev-parse origin/main` on 2026-11-21).
**Issue:** [#132](https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/132) — `OPEN_REPRODUCIBILITY_DEFECT`.
**Binding constraints respected:** PR #118 RD-01…RD-10; `AGENTS.md`; `docs/DECISIONS.md` standing rules; the Issue #132 restriction list (`INTEGRITY` matrix, `I-01`…`I-12`).

---

## 0. Executive decision

| Item | Outcome |
|---|---|
| Recommended path | **P-4 — Dual contract with an explicitly-supported-environment V1 exact replay and a separately versioned, portable V2 reference** (see §6) |
| Can Issue #132 be closed now? | **NO.** The engineering decision can be *accepted* without closing the defect. #132 closes only when a V2 reference pack exists, is independently re-certified, and the owner records the transition. |
| Is the defect a scientific/clinical problem? | **No.** All drift observed is `O(1 ULP)` in one derived score field on synthetic data. No model, target, abstention, threshold, provenance, SHAP/LIME or integrity contract changes. |
| Is the defect a CI-masking problem? | **No.** It is a genuine, deterministic property of the frozen reference's original arithmetic. It is **not** run-to-run randomness (§3.2). |
| Is the frozen V1 pack wrong? | **No.** It is a *faithful* record of one specific float64 evaluation order. It is **not portable**, and its portability was never established. |
| Can a green rerun close #132? | **No.** Evidence in §3 and §5 shows the reference is reproduced by some dispatches and not others, deterministically. |

The single sentence that should appear in RH-07/RH-08 risk registers until this is resolved:

> On the **one platform tested** (Linux x86-64, glibc 2.36, Python 3.11.2, NumPy 1.26.4 / SciPy 1.15.3, OpenBLAS 0.3.23.dev), the frozen RH-04 29-case Golden Replay is reproduced **exactly** under forced dispatches `SkylakeX` and `Cooperlake` **only**. Under `Sandybridge` and `Nehalem` it drifts in **two** fields on `da_a2_resting_v1` (`calibrated_log_odds` and `calibrated_research_score`); under `Haswell` (and `Zen`, which resolves to the Haswell kernel on this wheel) it drifts in `calibrated_log_odds` on both score cases. The observed deviations are 1-ULP-scale and are consistent with an arithmetic-order effect of the two-parameter SciPy L-BFGS-B calibration fit, not with a model, data or semantic difference. **Coefficient equality, response-field equality and canonical acceptance are three different predicates** (§1.4). No claim is made for wheels, hosts or kernel classes not tested here.

---

## 1. What was actually observed, reconciled

### 1.1 Issue #132 claim, restated precisely

Issue #132 reports a **binary64 low-order drift** in the frozen 29-case Golden Replay on source-specific route `da_a1_basic_clinical_v1`, field `response.outcomes[0].score.calibrated_log_odds`:

| Run | Job | Result |
|---|---|---|
| Attempt 1, Python 3.11, same SHA | [136806043483](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/44890830042/job/136806043483) | FAIL, `absolute_delta=4.441e-16`, `response mismatch: da_a1_basic_clinical_v1` |
| Attempt 2, Python 3.11, same SHA, same runner-image tag, same `OPENBLAS_NUM_THREADS=1` | [136809065781](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/44890830042/job/136809065781) | PASS, 1626 passed |
| Prior Python 3.12 diagnostic | PR #130 | 2.220e-16 Cleveland + 4.441e-16 UCI-412, both `calibrated_log_odds` only |

Both jobs are `ubuntu-24.04` GitHub-hosted runners (`runner_name` `GitHub Actions 1000002832` vs `1000002839`; verified via the Actions jobs API, §9 command set). They are **different VMs**, so the dispatch class is the only candidate explanation for the flip.

### 1.2 Independent local reconciliation (this branch)

Reproduced on the exact base commit, Linux x86-64, Python 3.11.2, glibc 2.36, `numpy 1.26.4` / `scipy 1.15.3` / `scikit-learn 1.6.1`, `OPENBLAS_NUM_THREADS=1`:

| Forced `OPENBLAS_CORETYPE` | NumPy core | SciPy core | `diagnose_fixture_replay` | Cases differing | Canonical validator |
|---|---|---|---|---|---|
| *(unset — host)* | SkylakeX | SkylakeX | `EXACT_REPLAY`, 0/29 | — | accepts |
| `SkylakeX` | SkylakeX | SkylakeX | `EXACT_REPLAY`, 0/29 | — | accepts |
| `Cooperlake` | Cooperlake | Cooperlake | `EXACT_REPLAY`, 0/29 | — | accepts |
| `Sandybridge` | Sandybridge | Sandybridge | `MISMATCH_FOUND` | **1** (`da_a2_resting_v1`, **2 fields**) | **rejects** |
| `Nehalem` | Nehalem | Nehalem | `MISMATCH_FOUND` | **1** (`da_a2_resting_v1`, **2 fields**) | **rejects** |
| `Haswell` | Haswell | Haswell | `MISMATCH_FOUND` | **2** | **rejects** |
| `Zen` | Haswell¹ | Haswell¹ | `MISMATCH_FOUND` | 2 (as `Haswell`) | **rejects** |

¹ This OpenBLAS build has no `Zen` kernel; it falls back to `Haswell`. Recorded here because it is itself evidence that a *name* is not a *kernel*. Per-field detail is in §1.4.

> **Correction notice.** The first revision of this table reported
> `Sandybridge` and `Nehalem` as `EXACT_REPLAY, 0/29`. That was measured with a
> narrower probe that only examined the calibration fit and the *log-odds*
> field, not the full 29-case replay. Re-running the full diagnostic shows a
> **second** differing field (`calibrated_research_score`, 1.110e-16) on
> `da_a2_resting_v1`, so the canonical validator rejects those dispatches. See
> §1.4. The frozen comparator was not involved and did not change.

**Conclusion (bounded to what was measured):** the two deltas in Issue #132 are reproduced exactly, byte-for-byte, by forcing `OPENBLAS_CORETYPE=Haswell` on this one platform, and are **consistent with** a dependence on the OpenBLAS dynamic-architecture kernel selection. Within the tested matrix they were *not* reproduced by changing the interpreter version, the thread count, or `OPENBLAS_NUM_THREADS`. That is an observation about four controlled variables on one platform — **not** a proof that the dispatch class is the sole cause on every host, and not a claim about kernels or library builds not tested here.

### 1.3 Consistent with host heterogeneity — CI evidence, and what it does *not* prove

The first CI run of this branch (`d271dee`) failed with the identical signature,
and a later head differing only in documentation passed. The honest reading:

| Observation | Established? |
|---|---|
| Run `44919728501` at `d271dee`: three jobs, three VMs, two different outcomes; the Python 3.11 and 3.12 synthetic jobs drifted while the separate 3.12 diagnostic reported `EXACT_REPLAY` twice | **Yes** — that is what the run records |
| The failing jobs ran on VMs `1000003130` / `1000003133`; the passing one on `1000003131` | **Yes** |
| *Which OpenBLAS kernel* any of those jobs used | **NOT captured.** The workflows did not log it |
| That hardware was the *only* changed variable between the red and green runs | **No — this is false as an experimental claim.** The runs differ in commit (two `.md` files), wall-clock time, and unobserved runtime characteristics, and the kernel identities are unknown |
| That the two outcomes are *consistent with* the host/dispatch heterogeneity measured separately under forced dispatch (§1.2) | **Yes** — that is the supported inference |

So: the red/green pair is **consistent with** host or dispatch heterogeneity and
is *not* explained by the diff, but it is **not** a controlled experiment and it
establishes **no** kernel assignment for those jobs. Direct CI attribution
requires instrumented logs, which is exactly what the follow-up diagnostic step
(§6 Step 2) would provide — and which is **not** applied by this PR.

Two narrower points do follow:

1. The drift is **not** specific to native Windows (it fires on Linux), and it is
   **not** specific to one interpreter version (both 3.11 and 3.12 jobs drifted
   in the same run, while a different 3.12 job passed).
2. Before this branch, **none** of those jobs recorded which kernel it used.
   That is the blind spot `G-01`/`G-03` names.

The failure was left **visible and un-retried**; it was not rerun until green.
Local reproduction under a forced `Haswell` dispatch gives
`1 failed, 1676 passed, 2 skipped, 10 errors` — the same shape as Issue #132
attempt 1. See evidence matrix §9.

`tests/experiments/test_offline_fixture_pack.py::test_golden_replay` fails under `OPENBLAS_CORETYPE=Haswell` with exactly the Issue #132 message (`1 failed, 49 passed`), and `test_rh04_replay_tolerance.py` correctly refuses to extend the pre-existing Cleveland exception to the UCI-412 case. **The comparator's narrowness is working as designed.**

---

### 1.4 Coefficient equality is not response equality — corrected measurements

The reviewer identified a contradiction in the first revision: §3 reported that
`Sandybridge` and `Nehalem` fit **different calibrator parameters** from the
golden fit, while — in the earlier text — they were described as 29/29 exact.
Re-measuring the full 29-case pack per dispatch (rather than only the calibration
fit) found the earlier description was **wrong in a second, independent way**:
those dispatches are **not** 29/29 exact. They drift in **two** fields on the
Cleveland case, so the canonical validator **rejects** them. Corrected table
(`test_rh04_replay_tolerance` and `_approved_replay_equal` are unchanged; this is
a documentation correction only):

| Dispatch | `da_a2_resting_v1` (Cleveland) | `da_a1_basic_clinical_v1` (UCI-412) | Canonical 29-case validator |
|---|---|---|---|
| `SkylakeX` | exact | exact | **accepts** (0 differing) |
| `Cooperlake` | exact | exact | **accepts** (0 differing) |
| `Sandybridge` | 2 fields: `calibrated_log_odds` 6.661e-16, `calibrated_research_score` 1.110e-16 | exact | **rejects** |
| `Nehalem` | 2 fields: `calibrated_log_odds` 4.441e-16, `calibrated_research_score` 1.110e-16 | exact | **rejects** |
| `Haswell` | 1 field: `calibrated_log_odds` 2.220e-16 (**pre-approved exception**) | 1 field: `calibrated_log_odds` 4.441e-16 | **rejects** (UCI-412 not excepted) |
| `Zen` → `Haswell` | as `Haswell` | as `Haswell` | **rejects** |

What this establishes, precisely:

* **The measured exactness set is `{SkylakeX, Cooperlake}` only**, on this
  platform and wheel set. The earlier "only SkylakeX/Cooperlake" phrasing was
  therefore accidentally right about *acceptance* but wrong for the stated
  reason; the earlier "Sandybridge/Nehalem are 29/29 exact" claim is **retracted**.
* **A second, previously unrecorded drift mode exists**: `calibrated_research_score`
  can differ by 1 ULP on Cleveland for `Sandybridge`/`Nehalem`. It happens to be
  absorbed by `expit` on the `Haswell` path (where the log-odds ULP is smaller),
  which is why it was not seen earlier. This is why the classifier treats a
  two-field entry as `UNEXPECTED_DRIFT` rather than as permitted drift.
* **Coefficient equality ≠ response equality ≠ canonical acceptance.** Three
  distinct predicates, and the frozen contract constrains only the last. A test
  that compared fitted coefficients would be stricter than the contract and
  would fail on `Sandybridge`/`Nehalem` even though those are already rejected
  on the response field anyway.
* No guarantee is made for kernels, wheel builds or hosts outside this table.

### 1.5 How the BLAS kernel is identified (and why the first method was wrong)

The reviewer asked whether the diagnostic inspects the BLAS that NumPy/SciPy
actually use, rather than an additional copy. The first revision did **not**:

| Step | First revision (`RTLD_GLOBAL`) | Revised (`RTLD_NOLOAD` only) |
|---|---|---|
| After `import numpy` | OpenBLAS already mapped; reported correctly | same |
| After `import scipy`, before a BLAS/LAPACK call | SciPy's OpenBLAS **not** mapped; `CDLL(..., RTLD_GLOBAL)` **loaded a private copy** (measured: 6 new mapped segments) and reported a kernel from it | `RTLD_NOLOAD` raises `OSError` without mapping anything; reported as `unverified` |
| After a real decomposition | copy already loaded by SciPy; reported correctly | resolved from the resident object |

Consequences now enforced in code and tests:

* no `RTLD_GLOBAL` appears in executable code (AST-asserted, not prose-asserted);
* every kernel value carries `kernel_identification_method`;
* an `unverified` method forces `UNVERIFIED_ENVIRONMENT` and **exit code 2**,
  even when the replay itself was exact;
* `test_rtld_noload_does_not_map_an_absent_library` proves `NOLOAD` cannot
  manufacture a resident library.

**What this does *not* prove:** that the resident kernel is the one every later
computation will use. Dynamic dispatch may still resolve differently at call
time on some builds, and the reported name is scoped to the object that was
resident when the probe ran. See `G-08`.

## 2. Root cause, established at stage granularity

### 2.1 Where the drift enters

Measured with the existing PR #133-style stage decomposition (boolean/exactness only; no coefficient, score or path is printed in CI). "Golden" = host/SkylakeX-class dispatch.

| Stage | Dispatch-stable? | Evidence |
|---|---|---|
| Synthetic cohort generation, panel validation | **yes** | 29/29 non-score fields identical; §1.2 |
| OOF probabilities fed to the final calibrator (n=120) | **yes** | SHA-256 of the `y`, `p` and `logit(p)` arrays identical across `SkylakeX`/`Haswell`/`Sandybridge`/`Nehalem`/`Zen` |
| Random-forest estimator: `n_estimators`, thresholds, leaf values, feature importances, class order | **yes** | bit-identical arrays across 4 dispatches |
| **`scipy.optimize.minimize(..., method="L-BFGS-B")` two-parameter fit** | **NO** | 3 distinct `(intercept, slope)` pairs across 5 dispatches |
| Affine map `intercept + slope * raw_log_odds` | deterministic given inputs | reproduces the frozen value exactly from the golden-dispatch pair |
| `expit(calibrated_log_odds)` → `calibrated_research_score` | **yes within observed range** | `calibrated_research_score` was bit-identical in the `Haswell` run even though `calibrated_log_odds` differed (the ULP is below the resolution of `expit` at log-odds ≈ 2.7) |
| SHAP / LIME / threshold flag / statuses / abstentions / digests | **yes** | 29/29 cases agree on every non-`calibrated_log_odds` field |

### 2.2 Why the fit is not dispatch-stable — measured mechanism

`scipy`'s vendored `__lbfgsb` is C code whose core operations call BLAS (`dcopy_`, `ddot_`, `daxpy_`, `dscal_`) in `LINPACK`-style kernels (`dtrsl`/`dtrtrs`). At the vector sizes L-BFGS-B uses for a 2-parameter problem with `maxcor=10` (sizes 2…~110) those are **not** scalar loops.

Directly measured on this host — number of distinct bit-patterns across `SkylakeX`/`Cooperlake`/`Sandybridge`/`Nehalem`/`Haswell`/`Zen` for the *same* input vectors:

| Operation | n=2 | n=4 | n=10 | n=20 | n=64 | n=128 |
|---|---|---|---|---|---|---|
| `np.dot` (BLAS) | 1 | 2 | **2** | **2** | **3** | **3** |
| `math.fsum` of products | 1 | 1 | 1 | 1 | 1 | 1 |
| sequential scalar accumulation | 1 | 1 | 1 | 1 | 1 | 1 |
| `np.sum(a*b)` | 1 | 1 | 1 | 1 | 1 | 1 |
| `np.einsum("i,i->")` | 1 | 1 | 1 | 1 | 1 | 1 |

`np.dot` splits into at least two *equivalence classes* for the bit patterns it produces: `{SkylakeX, Cooperlake}` and `{Sandybridge, Nehalem, Haswell, Zen}`, with `Nehalem` diverging a third time at n=64/128. This is consistent with an FMA/SIMD-reduction-order difference between kernels. It is the only *stage* in the tested pipeline whose inputs were shown to be dispatch-dependent; it is **not** a claim that every kernel in a class produces identical bits, nor that this is the sole mechanism on untested hosts.

### 2.3 The frozen value is a *stopping* artifact, not the mathematical optimum

This is the most important finding for the decision, and it is **new relative to `docs/rh04-portable-deterministic-calibration.md` §3**, which only said "a stopping-criterion artifact" without measuring what that implies for candidate remedies.

On the **real** frozen golden cohort (120 OOF observations, `clipped_logit_of_raw_probability`, `l2_anchor=1e-3`, bounds `((-15, 0.01), (15, 15))`), re-fitting the identical objective under L-BFGS-B with different convergence controls, per dispatch:

| Configuration | distinct `intercept` across dispatches | distinct `calibrated_log_odds` | reproduces frozen value on any dispatch | `‖projected grad‖∞` |
|---|---|---|---|---|
| **SciPy default** (current production) | 3 | 2 | **yes on golden class, 1 ULP off otherwise** | 5.50e-08 (same on all) |
| `ftol=1e-15` | 3 | 2 | unchanged | 5.50e-08 |
| `factr=1.0, pgtol=1e-12` | 3 | 2 | unchanged (default stop is `ftol`, not `pgtol`) | 5.50e-08 |
| `gtol=1e-10` | 3 | 1 | **no** — off by ≈4.3e8 ULP | 3.37e-10 |
| `gtol=1e-12, ftol=1e-16, maxiter=20000` | 3 | 2 | **no** — off by ≈4.2e8 ULP | 7.7e-13 … 1.5e-12 |

Two consequences:

1. **Tightening L-BFGS-B convergence does not cure the drift, and it destroys the frozen reference.** `gtol=1e-10` happens to make all four dispatches agree on `calibrated_log_odds`, but at a value ≈4.3×10⁸ ULP away from the frozen constant. A `gtol` change is therefore *not* a portable fix; it is a silent re-certification of every golden value.
2. **The frozen reference is a floating-point *stop*, not an argmin.** Any solver that converges *better* necessarily disagrees with it. The opt-in `deterministic_portable_newton` solver — bit-identical across all five dispatches (§5.2) — lands ≈4.2×10⁸ ULP (≈1.87e-7 in log-odds, ≈1.1e-8 in probability) from the frozen constant, because it actually reaches the KKT point. **This is convergence, not error.**

Therefore "make the default solver portable so the frozen fixture passes everywhere" is **not attainable within the solver options tested here**: every tested configuration either stays dispatch-dependent or lands far from the frozen value. A bit-exact portable algorithm is *not* proven impossible — a software emulation of the specific SIMD reduction order and L-BFGS-B stopping path could in principle reproduce it, but it would be hardware-specific arithmetic in a portable costume (`docs/rh04-portable-deterministic-calibration.md` §3). This is a **bounded statement about five tested solver configurations on one platform and cohort**, not a theorem.

### 2.4 The drift also leaks into signed artifact bytes

Out of scope for Issue #132's *symptom*, but decisive for the choice of path (§6). Bundle content, by OpenBLAS dispatch class:

| Bundle member | `SkylakeX` | `Haswell` | `Sandybridge` |
|---|---|---|---|
| `calibration.json` | `b1c566b4…` | `2ead37b3…` | `663de38a…` |
| `model.joblib` | `cf71db42…` | `35ac5209…` | `a430c9c5…` |
| `evaluation_summary.json` | `bd7d4c62…` | `83d5867a…` | `fc928012…` |
| `manifest.json` | `ac93f1bb…` | `6664a465…` | `7b690482…` |
| `preprocessing.json` | `0e01c35a…` | identical | identical |
| `shap_background.json` | `f9b1455d…` | identical | identical |
| `protocol.md` | `e3be6ff4…` | identical | identical |

Decomposition: with the *embedded calibrator parameters removed from the comparison*, the `model.joblib` payload (random forest + fold ensemble metadata) is **bit-identical** across all three dispatches. Every differing bit in the bundle is attributable to the two-parameter calibration fit. `preprocessing.json` and `shap_background.json` — the two members that bound feature order and explainability alignment — are immune.

**Meaning:** the calibrated score is *not* a bit-reproducible artifact property today. A future real-bundle integrity, promotion or cross-machine comparison procedure that asserts byte equality of `model.joblib` or `calibration.json` would fail on a legitimate machine change. This is a latent limitation that should be recorded now (it is not currently exercised, and it does not affect `RESEARCH_ONLY` eligibility, panel binding, SHAP alignment or `verified_artifact_hashes` *within one build*).

---

## 3. Determinism classification — what is established, what is not

### 3.1 Established by experiment (this branch unless cited)

| ID | Claim | Evidence |
|---|---|---|
| `E-01` | On the tested platform, repeated isolated subprocesses on the **same** forced dispatch produced **1** distinct outcome in 4 runs. This shows the observed difference is not run-to-run random *there*; it does **not** establish global determinism, and it does not exclude unobserved runtime variation on other hosts. | §1.2, §3.2 |
| `E-02` | The exact two Issue #132 deltas (2.220e-16, 4.441e-16) are reproduced from a forced `Haswell` dispatch. | §1.2 |
| `E-03` | Across all tested dispatches, only **two** semantic fields ever differed — `calibrated_log_odds` and `calibrated_research_score` — and only inside the two `SYNTHETIC_RESULT` score cases. `Sandybridge`/`Nehalem` exhibit the second field on Cleveland; `Haswell`/`Zen` exhibit only the first. No status, refusal, structure, threshold flag, provenance or digest field ever differed. | §1.2, §1.4 |
| `E-04` | The divergence first appears **inside** the SciPy L-BFGS-B fit; every input to it and every other pipeline stage is bit-identical across dispatches. | §2.1 |
| `E-05` | `np.dot` at L-BFGS-B's internal sizes has ≥2 dispatch equivalence classes; `math.fsum`, sequential scalar accumulation, `np.sum(a*b)` and `np.einsum` do not. | §2.2 |
| `E-06` | Tightening L-BFGS-B convergence **moves away** from the frozen value by ≈4×10⁸ ULP and does not remove dispatch dependence of the parameters. | §2.3 |
| `E-07` | The opt-in `deterministic_portable_newton` solver produced **bit-identical** parameters across the 5 forced dispatch classes tested on the real golden cohort, and lands ≈1.87e-7 in log-odds from the frozen value. Scoped to this platform, wheel set and dispatch set only; not a general portability claim. | §5.2 |
| `E-08` | Thread count does **not** matter here (`OPENBLAS_NUM_THREADS` 1/2/4 identical). | §3.2 |
| `E-09` | Every differing bundle byte is attributable to the calibration fit; estimator and preprocessing bytes are stable. | §2.4 |
| `E-10` | `OPENBLAS_CORETYPE=Zen` on this wheel silently falls back to `Haswell` — env-var *names* do not identify *kernels*. This is the same class of error that broke PR #134's `SkylakeX` pin (#134 was right to reject it). | §1.2 |

### 3.2 Established by the historical record (not re-run here)

| ID | Claim | Source |
|---|---|---|
| `E-11` | Same SHA, same workflow, same runner-image tag, same `OPENBLAS_NUM_THREADS=1` produced FAIL then PASS. | Issue #132 jobs `136806043483` / `136809065781` |
| `E-12` | Pinning `OPENBLAS_CORETYPE=HASWELL` + `NPY_DISABLE_CPU_FEATURES=AVX2,FMA3,AVX512F` did **not** cure the drift. | Issue #132 comment 2026-11-21T11:01:23Z; run `44896568228` |
| `E-13` | A `OPENBLAS_CORETYPE=SkylakeX` pin **aborts before NumPy import** on the tested hosted runner (`CPU does not expose avx512f`), so that specific pin is unusable there. This is a property of the tested runner, not of all runners. | run `44901748832`, jobs `136838961519` / `136838961533`; PR #134 |
| `E-14` | Native Windows produced the same single Cleveland field delta (4.441e-16) and nothing else. | `docs/research/next_phase/RH047_RH048_SYNTHETIC_REPORT_ASSEMBLY.md` |

### 3.3 CPU/OS/math-library dependence — honestly bounded

| Aspect | Status |
|---|---|
| x86-64 Linux, glibc, NumPy 1.26.4 / SciPy 1.15.3 / scikit-learn 1.6.1, Python 3.11.2 | **measured**, 5 dispatch classes, §1.2 |
| Native Windows, same pinned wheels | **historically measured** (`E-14`), one case/field; not re-run on this branch |
| Python 3.12 | **NOT measured by this branch.** This sandbox has no 3.12 interpreter and no egress to a Python distribution host. CI (`synthetic-runner-tests` 3.11 **and** 3.12) is the only evidence, and it is green on dispatch classes that happen to match. |
| NumPy ≥2 / SciPy ≥1.16 / ARM64 / macOS Accelerate / non-glibc `libm` | **UNPROVEN.** No claim is made. `expit`, `logaddexp`, `math.exp`/`math.log1p` remain last-ULP host-dependent in principle. |
| Whether a *different* rebuild of the same OpenBLAS version picks the same kernels | **UNPROVEN**; `E-10` shows version+env name is insufficient identification |

### 3.4 The one inference that *is* justified

The two CI jobs at the same SHA in `E-11` differed with identical inputs, pinned thread counts, pinned wheels and runner-image tag. Their actual kernels were **never logged**, so a specific attribution cannot be made from those runs alone. What *is* supported is a hypothesis: the outcomes are **consistent with** host/dispatch heterogeneity of the kind measured directly under forced dispatch (§1.2), and they are **not** explained by the source diff. Calling this "flaky" would be less informative than calling it "environment-dependent, mechanism measured separately" — but it remains an inference, not a logged fact, until the diagnostic step records kernels. Direct attribution is exactly what §6 Step 2 would provide.

---

## 4. What must NOT be done (and why the obvious fixes are wrong)

| Tempting fix | Why it is rejected |
|---|---|
| Add a `da_a1_basic_clinical_v1` tolerance exception like the Cleveland one | Correct-by-tolerance, but it silently makes the reference comparison **pairwise-approximate** on the one field whose exactness the project advertises. It also cements an unportable reference instead of replacing it. Requires its own owner decision; not this PR. |
| Change `gtol`/`ftol`/`factr` | §2.3: re-certifies every golden value by ≈4×10⁸ ULP while appearing to be a "numerical tightening". The most dangerous option in the list because it *looks* principled. |
| Make the deterministic solver the default | §2.3/`E-07`: portable and correct, but disagrees with the frozen reference by ≈1.9e-7. Doing this without re-freezing silently invalidates the V1 contract; doing it with re-freezing is P-2, which needs owner re-certification. |
| Hardcode golden coefficients / a lookup table | Prohibited by Issue #132 and by `AGENTS.md` (never fabricate reference values). |
| Add an AVX-512 pin, or disable AVX-512 | `E-13`: the SkylakeX pin aborts on the tested hosted runner. `E-12`: disabling AVX-512/FMA3 was empirically ineffective. |
| Add a `pytest.skip`/`xfail` conditional on dispatch | Turns a real, informative failure into a silent hole; the whole point is that the failure is *evidence*. |
| Re-run until green | Issue #132 explicitly forbids it, and `E-01` shows it manufactures a false narrative of flakiness. |
| Raise `ABS_TOL`/`REL_TOL` in `ai/report_comparison.py` | Those are the AI-12.1 *report* comparator, used by a different contract; widening them to rescue the pack conflates two independent guarantees. |
| Blame Windows / Python 3.12 | The delta is observed on **Linux** under forced non-golden dispatch (§1.2), and both 3.11 and 3.12 CI jobs drifted in one run (§1.3). So neither the OS nor the interpreter is a sufficient explanation on the tested evidence. |

---

## 5. Candidate acceptance approaches, compared

All four are legitimate engineering positions. They are compared on what the repository actually needs: a defensible, honest, *checkable* reproducibility contract for a research-only prototype, at $0, on GitHub-hosted Linux plus a human's Windows machine.

### P-1 — "Preserve legacy V1 exact replay on explicitly supported environments only"

Keep the pack, digest, comparator, tolerances and workflow byte-identical. Record the observed replay outcome **as supplemental evidence about the environment**, without changing what the canonical gate does: the strict pytest Golden Replay remains authoritative and remains **red** on any host where it does not reproduce exactly. No environment qualification is used to excuse a failure.

- **Pros:** zero changes to frozen artifacts (strongest possible preservation proof); truthful; immediately actionable; keeps one golden and one comparator; no new fixture lifecycle.
- **Cons:** the acceptance gate is untestable on the CI hardware that actually runs it (`E-13` shows the golden class is *not reachable by pinning* on GitHub-hosted runners), so the honest contract is "may pass or fail depending on which VM we got". Leaves CI non-hermetic indefinitely; leaves the artifact-byte portability limitation (`§2.4`) unaddressed; invites exactly the "rerun until green" habit Issue #132 forbids.
- **Verdict:** necessary as a **component**, insufficient as the whole answer.

### P-2 — "Separately versioned deterministic calibration reference + formally re-certified V2 fixtures"

Introduce `cardioassist.ai.calibration/v2` fitted by the portable solver (or any solver with a *declared* convergence criterion), generate a **new** 29-case V2 pack with a **new** digest and recorded provenance, and treat V1 as frozen history.

- **Pros:** cleanest long-term state; the reference becomes a property of *declared algorithm + convergence criterion*, not of a host kernel; artifact bytes become portable; the portable solver's portability is already measured (`E-07`).
- **Cons:** the largest change — new pack, new digest, new `PACK_SHA256`, new comparator disposition, model-calibration parameters change by ≈1e-7 (semantically nil, numerically real), re-certification on the owner's Windows machine, and a documented migration window where both packs must exist. It also changes `calibration.json` semantics *by procedure*: V2 values are the true argmin, so any downstream statement like "the calibrator is the L-BFGS-B output" becomes false and must be rewritten.
- **Verdict:** the correct **destination**. Not deliverable in one step from a decision PR.

### P-3 — "Narrowly justified explicit comparator policy"

Extend `_approved_replay_equal` with a second, explicitly bounded, owner-approved exception for `da_a1_basic_clinical_v1 / calibrated_log_odds`, exactly mirroring the Cleveland precedent, with written justification and negative tests.

- **Pros:** smallest possible diff; no fixture or digest change; consistent with an existing approved precedent (`_WINDOWS_FLOAT_CASE_ID`); fully testable immediately; converts intermittent red into deterministic green with an auditable record.
- **Cons:** does **not** fix anything — it *decides to stop detecting* the thing. It also compounds: the next host may drift a different case, and each new exception widens the pairwise-approximate surface while the pack still claims exactness everywhere else. It leaves `docs/rh04-portable-deterministic-calibration.md`'s "exact Golden Replay" language technically false and leaves CI dependent on which VM was allocated.
- **Verdict:** acceptable only as a **time-boxed bridge** with an explicit expiry, never as the terminal state.

### P-4 — "Retain dual legacy/new contracts during migration" → **RECOMMENDED**

> **Revised after independent review (v2).** The first revision of this section
> described P-4 as "P-1 + P-3", which contradicted its own promise of an
> unchanged strict gate with no new comparator exception, and the original
> §6 Step 2 turned a classified failure into a diagnostic-step success. Both
> were inconsistent with the canonical contract. The policy below is the single
> authoritative statement; it replaces every earlier description of P-4.

**The immediate policy (binding, and the only policy this PR endorses):**

1. **The frozen V1 Golden Replay stays strict and unchanged.** The 29-case pack,
   canonical digest `0307b396…`, `_approved_replay_equal`, `ABS_TOL`/`REL_TOL`,
   the default SciPy L-BFGS-B solver and `.github/workflows/**` remain
   byte-identical, and the pytest Golden Replay remains an **authoritative,
   failing** gate.
2. **Environment and numerical classification is supplemental diagnostic
   evidence only.** It is recorded, versioned and reviewable; it edits no
   decision.
3. **A canonical Golden Replay failure is never converted into CI success.**
   No step maps a classified mismatch to a passing job.
4. **No new tolerance exceptions.** The pre-existing Cleveland exception is not
   extended, and P-3 is not adopted.
5. **No skip, xfail, suppression or automatic retry** of a failing test.
6. **Issue #132 stays OPEN.**
7. **V2 is implemented only in a separately reviewed, explicitly authorized
   PR** (§7).

**What P-4 therefore is, precisely:** P-1's *preservation* plus a *read-only*
diagnostic layer, with P-2 as the only declared destination. It is **not** P-3.
Under this policy a host that does not reproduce V1 exactly will see a **red**
canonical gate — that is the correct, informative outcome, and it is precisely
what the diagnostic then explains.

**Why this is the recommended path anyway:**

- It is honest *now*: the strict gate keeps its meaning, and nothing is
  redefined to make a machine's allocation look like a pass.
- It adds the missing evidence cheaply: the historical CI runs did not record
  which kernel they used, so "intermittent" could not be investigated. One
  read-only step fixes that permanently.
- It is convergent without pretending: V2 (`§7`) is the only exit, and until it
  exists the project's honest state is "V1 exactness is a measured property of
  specific environments; the strict gate stays strict".
- It preserves the maximum frozen surface (`E-03`: exactly one field, two
  cases) and keeps the failure **visible** rather than converting it into a
  tolerance or a skip.

**Explicitly rejected as a sole basis for approval:** "it makes CI green".

### 5.1 Comparison matrix

| Criterion | P-1 env-scoped V1 | P-2 V2 re-certification | P-3 comparator exception | **P-4 preserve + diagnose (recommended)** |
|---|---|---|---|---|
| Frozen V1 pack/digest/comparator untouched | ✅ | ❌ (new pack) | ⚠️ comparator edited | ✅ |
| Backward compatibility | ✅ | ⚠️ migration window | ✅ | ✅ |
| Model-calibration semantics preserved | ✅ | ⚠️ parameters move ≈1e-7 | ✅ | ✅ |
| Cross-platform reproducibility | ❌ undeclared | ✅ (bounded, `E-07`) | ❌ still host-dependent | ❌ until V2; now *measured*, not assumed |
| Fixture provenance | ✅ unchanged | ⚠️ new provenance needed | ✅ | ✅ |
| Security assertions preserved | ✅ | ✅ (must re-assert) | ⚠️ scope creep in `_approved_replay_equal` | ✅ (no comparator branch) |
| Regression impact | none | medium-high | low | **low, additive** |
| Canonical gate stays meaningful | ✅ | ✅ | ❌ masked | ✅ |
| Deliverable from a decision PR | ✅ | ❌ | ❌ (needs owner approval) | ✅ |
| Convergence to a real fix | ❌ | ✅ | ❌ | ✅ (V2 is the only exit) |

---

## 6. Recommended follow-up work (specification, not applied here)

> **This section is a specification.** No workflow file is modified by this PR.
> This PR *does* add non-documentation files:
> `research/intake/rh04_environment_class.py` (read-only diagnostic), its test
> module, and one `.gitignore` line. None changes production behaviour.

**Step 1 (owner decision, no code):** accept that V1 exactness is a *measured*
property of environments, and that the strict gate stays strict while the
diagnostic records which environment it observed. Nothing is relaxed.

**Step 2 (CI, strictly additive, must not alter any pass/fail outcome):** add
one read-only step *before* the scoring pytest step in each synthetic job. It
must:

- report the kernel of the **already-resident** BLAS only, via
  `ctypes.RTLD_NOLOAD` (or the process image), never `RTLD_GLOBAL` — the earlier
  revision's `RTLD_GLOBAL` call loaded a private copy that NumPy/SciPy had not
  used (§8 `G-08`);
- print `numpy`/`scipy`/`scikit-learn`/`glibc`/platform/Python versions and the
  two kernel names, with **no** paths, scores or keys;
- reduce the diagnostic JSON to the closed verdict vocabulary with **exit 0 only
  for a validated exact envelope with a verified environment**, exit 1 for
  classified single-field deltas, exit 2 for everything else;
- **`continue-on-error: false` is irrelevant to the gate**: the canonical pytest
  step still runs and still determines the job's result. The diagnostic step's
  exit code is recorded in the job log and step summary as evidence. If an owner
  wants the job's colour to *include* the diagnostic, the step can simply be left
  failing on exit 1; that is a policy choice, **not** a correctness one, and this
  PR does not choose it.

**Explicitly forbidden in that step:** mapping a classified mismatch to a
passing job, skipping/xfailing/retrying, editing tolerances or the comparator,
echoing numeric values.

**Step 3 (tests, negative-first):** already implemented here — see
`tests/experiments/test_rh04_issue132_environment_class.py` (101 tests, 14/14
mutation-killed). The follow-up must keep them green.

**Step 4 (documentation):** amend `docs/rh04-portable-deterministic-calibration.md`
and the RH-07/RH-08 risk registers with the §0 sentence.

**Step 5 (V2, separate PR, owner re-certification required):** see §7.

---

**Do not, in any follow-up:** change the default solver; change `ABS_TOL`/`REL_TOL`; touch `research/intake/fixtures/offline_io.v1.json`, `PACK_SHA256`, `_approved_replay_equal`'s Cleveland branch or `_WINDOWS_FLOAT_CASE_ID`/`_WINDOWS_FLOAT_FIELD`; add `pytest.skip`/`xfail`/`continue-on-error`; import PR #134's AVX-512 guards or workflow pins; activate any real-data path; or convert a canonical failure into a passing job.

### 6.1 The `docs/rh04-portable-deterministic-calibration.md` §5 options, re-judged

That document proposed "Option A — fixture re-certification" and "Option B — bounded tolerance exception". Measured evidence now ranks them:

- **Option B is weaker than presented.** It was framed as an equivalent alternative to A. It is not: it is non-convergent (§5 P-3) and, on the measured evidence, the deltas can appear in *either* executable case (`da_a2_resting_v1` at 2.220e-16 and `da_a1_basic_clinical_v1` at 4.441e-16 in the same run), so a per-case exception is a per-case lottery, not a stable boundary. P-3 is **not adopted** under the §5 policy; the diagnostic is added for evidence, not to license an exception.
- **Option A is correct but under-specified.** It does not say what makes V2 trustworthy. `E-06` supplies the missing requirement: **V2 must declare its convergence criterion**, because any criterion that is not "reach the KKT point" is host-dependent by construction. A V2 pack generated by portable-*solver* but a host-dependent-*criterion* would reproduce the exact bug in a new costume.

---

## 7. Prerequisites for the V2 (P-2) implementation PR — precise and checkable

`V2-01` **Owner ratification** of the V1→V2 transition, recorded in `docs/DECISIONS.md`, naming the accepting reviewer and this document's version.
`V2-02` **Solver + criterion declaration.** Either the hardened `deterministic_portable_newton` (whose P0 issues recorded in Issue #132 / PR #135 comment 2026-11-21T13:45:03Z must be *closed*, not merely patched: inward-gradient face pinning, Armijo sign, zero-step-with-nonzero-KKT false success, the tautological assertion, and deserialized-provenance mislabelling) or a documented alternative whose convergence test is explicitly *not* host-dependent. **The criterion is part of the contract.**
`V2-03` **New pack, new digest.** `research/intake/fixtures/offline_io.v2.json` with its own `PACK_SHA256_V2`, recorded provenance (`solver`, criterion, tolerance, generating platform, kernel names), and a written mapping from each V1 expected value to its V2 counterpart with the numeric delta. V1 files stay forever frozen.
`V2-04` **Cross-environment replay evidence** on the new pack: ≥3 dispatch classes × {Python 3.11, 3.12} on Linux, **plus native Windows**, all reporting `EXACT_REPLAY`. Deltas-only is *not* acceptable for V2 — that is the entire point.
`V2-05` **Dual-run window.** Both V1 (scoped, §6) and V2 gates run in CI until the owner retires V1. No silent substitution.
`V2-06` **Semantics re-statement.** `calibration.json` / `scale_declaration` / model cards / manifest wording must stop implying "L-BFGS-B output" and start declaring the fitted criterion. Includes the §2.4 artifact-byte statement.
`V2-07` **Negative tests first:** wrong digest, >29 cases, a drifted non-calibration field, a planted second tolerance exception, a solver-provenance regression, an unreachable-criterion (fail-closed) case, and a V1 pack byte-integrity assertion. Each must fail closed.
`V2-08` **Security parity:** `_approved_replay_equal`'s type-strictness, redaction (`_describe`), no-fallback, fail-closed ordering and refusal-path tests must all still pass, and V2 must introduce **no** new tolerance surface.
`V2-09` **Explicit non-claims.** V2 acceptance must state it is engineering reproducibility only: no clinical validity, no model-equivalence, no RH-07 science, no RH-08 release, no D-047/M3a metrics.
`V2-10` **Rollback plan:** V2 revert must be a single revert of the pack + comparator + gate, leaving V1 intact and green.

---

## 8. Unresolved evidence and residual risk

| ID | Gap | Consequence if wrong | How to close it |
|---|---|---|---|
| `G-01` | **Python 3.12 not measured by this branch** (no interpreter, no egress). CI is green at 3.11 **and** 3.12, but on unspecified dispatch classes. | Low: the drift is dispatch-driven, not version-driven (`§2.2` shows interpreter-independent arithmetic). But unproven here. | The Step-2 dispatch step, once merged, records the class for both versions permanently. |
| `G-02` | **Native Windows not re-measured.** `E-14` is the only record. | Low for #132; **medium** for V2-04, which *requires* Windows exactness. | Owner-run local `python -m research.intake.diagnose_fixture_replay` at V2 review time. **Not requested for this decision PR** — there is no unavoidable gap here. |
| `G-03` | The mapping *kernel name → float64 result* is empirical, not derived. Two dispatches named `SkylakeX` from different builds are assumed identical. | A future OpenBLAS rebuild could move the golden class. | The Step-2 step records kernel **and** library version; treat both as the identity. |
| `G-04` | Only 5 dispatch classes exercised out of the ~20 in the wheel. | A rare class may produce a delta outside the two known fields. | The fail-closed Step-2 gate is the mitigation; it will report the new class rather than hiding it. |
| `G-05` | `math.exp`/`log1p` last-ULP host dependence means even the portable solver is *not* proven bit-portable across libc/OS. | V2's cross-platform claim must be scoped to tested hosts. | V2-04 + explicit scope wording. |
| `G-06` | §2.4 artifact-byte non-portability is **not currently exercised by any test**. | Latent; would surface in any future cross-machine artifact comparison. | Record in the model-card / manifest limitation text during V2-06. |
| `G-07` | Whether the *pinned wheel set itself* (`numpy 1.26.4` → OpenBLAS `0.3.23.dev`) is bitwise reproducible from PyPI on a rebuild. | Assumed, not checked. | Out of scope; note it, don't claim it. |
| `G-08` | **BLAS identification method.** The first revision read the core name via `ctypes.CDLL(path, RTLD_GLOBAL)`, which **loads a private copy** when the library is not already resident. Measured: after `import scipy` but before any BLAS/LAPACK call, SciPy's OpenBLAS is not mapped; the old code then mapped 6 extra segments and reported a kernel from a library the numerical code had not used. **Fixed** by using `RTLD_NOLOAD` exclusively (which never maps an absent object) and recording the method per value (`rtld_noload` / `process_symbol` / `unverified`). A `unverified` kernel now forces `UNVERIFIED_ENVIRONMENT` and exit 2. **Residual limitation:** even a correctly-resolved *resident* kernel is not proof that a *later* call will use that library, and dynamic dispatch can still select a different kernel at runtime on some builds. The reported name is evidence about the resident object, not an authoritative statement about every future computation. | Reduced, not eliminated. | Prefer instrumented runs; never present the kernel name as authoritative without the method field. |

**Residual risk after P-4:** CI can still fail on a genuinely new dispatch class — *by design*, and with a report naming the class. That is strictly better than the current state and is the correct failure mode for a reproducibility claim.

---

## 9. Reproducible commands

All commands are read-only, synthetic-only, and create no repository artifacts. Replace `.venv-rh04` with any environment built from `research/experiments/requirements.txt` + `research/audit/requirements.txt` + `research/uci412/requirements.txt`.

**Setup**

```bash
python -m venv .venv-rh04
.venv-rh04/bin/python -m pip install -q --upgrade pip
.venv-rh04/bin/python -m pip install -q \
  -r research/experiments/requirements.txt \
  -r research/audit/requirements.txt \
  -r research/uci412/requirements.txt
.venv-rh04/bin/python -m pip check
```

**Baseline (host dispatch) — expect `EXACT_REPLAY`**

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  .venv-rh04/bin/python -m research.intake.diagnose_fixture_replay
```

**Reproduce Issue #132 exactly — expect `MISMATCH_FOUND`, 2 cases, the two known deltas and nothing else**

```bash
OPENBLAS_CORETYPE=Haswell OPENBLAS_NUM_THREADS=1 \
  .venv-rh04/bin/python -m research.intake.diagnose_fixture_replay   # exit 1, by design
OPENBLAS_CORETYPE=Haswell OPENBLAS_NUM_THREADS=1 \
  .venv-rh04/bin/python -m pytest \
  tests/experiments/test_offline_fixture_pack.py::test_golden_replay -q -W error
```

**Confirm the comparator's narrowness is intact — expect 49 passed / 1 failed under `Haswell`, 50 passed under the host class, and the Cleveland exception never extended**

```bash
OPENBLAS_CORETYPE=Haswell OPENBLAS_NUM_THREADS=1 \
  .venv-rh04/bin/python -m pytest \
  tests/experiments/test_offline_fixture_pack.py \
  tests/experiments/test_rh04_replay_tolerance.py -q -W error
```

**Frozen-artifact preservation proof**

```bash
sha256sum research/intake/fixtures/offline_io.v1.json
.venv-rh04/bin/python - <<'PY'
import json
from ai.research_facade import canonical_response_digest
from research.intake import offline_fixture_pack as f
p = json.loads(f.PACK.read_text())
print("canonical PACK_SHA256 =", canonical_response_digest(p))
print("declared  PACK_SHA256 =", f.PACK_SHA256)
print("cases =", len(p["cases"]))
PY
```

Expected on this branch and on `main`:

```
206418e5f15787c5048c1ebad86d107e40ad4dfcbf727feb6b08ed305e273ab9  research/intake/fixtures/offline_io.v1.json
canonical PACK_SHA256 = 0307b396cea1e620c4004647e1d82ff7f292bb5b74de7cad1661e1299c6e7049
declared  PACK_SHA256 = 0307b396cea1e620c4004647e1d82ff7f292bb5b74de7cad1661e1299c6e7049
cases = 29
```

**Identify the *actual* kernels (not the env-var name — see `E-10`)**

```bash
.venv-rh04/bin/python - <<'PY'
import ctypes, glob, os
import numpy, scipy
def core(pkg, pattern, symbols):
    d = os.path.join(os.path.dirname(pkg.__file__), "..", os.path.basename(os.path.dirname(glob.glob(
        os.path.join(os.path.dirname(pkg.__file__), "..", "*.libs", pattern))[0])))
    for dep in glob.glob(os.path.join(d, "*.so*")):
        try: ctypes.CDLL(os.path.abspath(dep), mode=ctypes.RTLD_GLOBAL)
        except OSError: pass
    lib = ctypes.CDLL(os.path.abspath(glob.glob(os.path.join(d, pattern))[0]), mode=ctypes.RTLD_GLOBAL)
    for s in symbols:
        if hasattr(lib, s):
            f = getattr(lib, s); f.restype = ctypes.c_char_p
            return f().decode()
    return None
print("numpy.openblas core :", core(numpy, "libopenblas*.so", ["openblas_get_corename64_", "openblas_get_corename"]))
print("scipy.openblas core :", core(scipy, "libscipy_openblas*.so", ["scipy_openblas_get_corename"]))
PY
```

**Full non-scoring suites (what this branch actually ran)**

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv-rh04/bin/python -m pytest \
  tests/experiments tests/audit -q -W error
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv-rh04/bin/python -m pytest \
  tests/uci412 -q -W error
.venv-rh04/bin/python -m research.experiments dry-run
.venv-rh04/bin/python -m research.uci412 dry-run
```

**Preserved-frozen-file guard (must print nothing)**

```bash
git diff --stat 10bee67474b0eb9858f4ca6f298037c2f32459cc -- \
  research/intake/fixtures research/intake/offline_fixture_pack.py \
  ai/report_comparison.py .github/workflows
```

---

## 10. Evidence matrix (condensed)

| # | Observation | Class | Environment | Established by |
|---|---|---|---|---|
| `M-01` | Host-class dispatch (`SkylakeX`) → `EXACT_REPLAY` 0/29 | **measured** | Linux x86-64, Py3.11, OpenBLAS 0.3.23.dev | this branch |
| `M-02` | `Haswell` → 2 cases differing, one field each (`calibrated_log_odds`): 2.220e-16 Cleveland (pre-approved exception, accepted) and **4.441e-16 UCI-412 (not excepted, rejected)** | **measured** | same | this branch |
| `M-03` | `Cooperlake` → `EXACT_REPLAY` 0/29; `Sandybridge`/`Nehalem` → **2 differing fields on `da_a2_resting_v1`**, canonical validator **rejects** | **measured** | same | this branch, §1.4 |
| `M-04` | `Zen` silently resolves to `Haswell` | **measured** | same | this branch |
| `M-05` | 4 repeats, same dispatch → 1 distinct outcome | **measured** | same | this branch |
| `M-06` | Threads 1/2/4 → identical | **measured** | same | this branch |
| `M-07` | `np.dot` has 2–3 dispatch equivalence classes at n=4…128; `fsum`/scalar/`einsum` have 1 | **measured** | same | this branch |
| `M-08` | OOF `y`/`p`/`logit` digests identical across 5 dispatches | **measured** | same | this branch |
| `M-09` | RF thresholds/values/importances identical across 4 dispatches | **measured** | same | this branch |
| `M-10` | Tightening L-BFGS-B → ≈4.2–4.3e8 ULP from frozen, still 3 distinct parameters | **measured** | same | this branch |
| `M-11` | Portable solver bit-identical across 5 dispatches; ≈1.87e-7 log-odds from frozen | **measured** | same | this branch |
| `M-12` | All bundle-byte differences localize to calibrator parameters | **measured** | same | this branch |
| `M-13` | Same SHA, same runner tag → FAIL then PASS | **historical** | GitHub-hosted `ubuntu-24.04` | `E-11` |
| `M-13b` | **One commit, one run, three VMs → 2 drift + 1 exact.** Reproduced prospectively on a docs-only branch head. | **measured** | GitHub-hosted `ubuntu-24.04` | §1.3, matrix §9 |
| `M-14` | `HASWELL` + `NPY_DISABLE_CPU_FEATURES` does not cure | **historical** | CI | `E-12` |
| `M-15` | `SkylakeX` pin aborts on the tested hosted runner | **historical** | CI | `E-13` |
| `M-16` | Windows: one Cleveland field, 4.441e-16 | **historical** | native Windows | `E-14` |
| `M-17` | Python 3.12 dispatch behaviour | **unproven here** | CI only | `G-01` |
| `M-18` | NumPy≥2 / SciPy≥1.16 / ARM64 / macOS / non-glibc libm | **unproven** | — | `G-05` |

---

## 11. Answers to the deliverable's explicit questions

**Which aspects of reproducibility have been experimentally established?**
On the tested platform: repeated-run stability at fixed dispatch (`E-01`); full stability of every pipeline stage except the two-parameter calibration fit (`E-04`, `M-08`, `M-09`); exactness of the frozen reference under `SkylakeX`/`Cooperlake` (`M-01`); the observed per-dispatch deviation set, which includes a **second** field on `Sandybridge`/`Nehalem` (`M-02`, `M-03`, §1.4); and the existence of a numerically portable fit under the tested conditions (`M-11`).

**Which depend on CPU/OS/math library?**
Only the L-BFGS-B fit: BLAS kernel selection → reduction order → the two fitted parameters (`M-07`, `M-10`). Consequently `calibration.json`, `model.joblib`, `evaluation_summary.json` and `manifest.json` bytes (`M-12`). Everything else — cohort, panels, preprocessor, forest, SHAP/LIME, statuses, abstentions, thresholds, route binding, digests of immutable artifacts — is dispatch-stable on tested classes.

**Which remain unproven?**
`M-17`, `M-18`, `G-03`, `G-05`, `G-07`: Python 3.12 locally, everything outside pinned NumPy/SciPy on glibc x86-64, kernel-name→result stability across library rebuilds, `libm` bit-portability, and PyPI-wheel rebuild reproducibility.

**Should #132 be closed?**
**Not by this PR.** The *engineering decision* should be accepted (owner + independent reviewer); the *defect* stays open until V2 (`V2-01`…`V2-10`) is re-certified. Closing now would assert a portability guarantee the evidence contradicts. Precise closure condition: **V2 pack merged, cross-environment `EXACT_REPLAY` evidenced (`V2-04`), V1 retired by owner decision, and this document's §0 sentence removed from the RH-07/RH-08 risk registers.** PR #133 and PR #134 should then be closed as superseded by this record (`#133` instrumentation still useful as a reference, `#134`'s hardware pin is falsified by `E-13`/`E-10`).

---

## 12. Provenance of this document

- Base: `10bee67474b0eb9858f4ca6f298037c2f32459cc`, verified equal to `origin/main` on 2026-11-21.
- Inputs read: `AGENTS.md`; `docs/DECISIONS.md` (D-045…D-049, standing rules); `docs/research/CARDIOASSIST_AI_MASTER_COMPLETION_PLAN.md`; PR #118 (RD-01…RD-10); Issue #132 + all 6 evidence comments; PRs #133, #134, #135 (bodies, diffs, review comments); `ai/calibration.py`; `ai/report_comparison.py`; `ai/uci412_research.py`; `ai/training.py`; `ai/inference.py`; `ai/packaging.py`; `research/intake/offline_fixture_pack.py`; `research/intake/diagnose_fixture_replay.py`; `tests/experiments/{test_offline_fixture_pack,test_rh04_replay_tolerance,test_rh04_calibration_portable_determinism,test_diagnose_fixture_replay}.py`; `.github/workflows/experiment-runner-ci.yml`; `docs/rh04-portable-deterministic-calibration.md`; `docs/research/next_phase/RH047_RH048_SYNTHETIC_REPORT_ASSEMBLY.md`.
- All measurements: Linux x86-64 (Xeon, AVX-512 capable), Debian 12, glibc 2.36, Python 3.11.2, `numpy==1.26.4` / `scipy==1.15.3` / `scikit-learn==1.6.1`, OpenBLAS `0.3.23.dev` (NumPy) and SciPy's bundled OpenBLAS, `OPENBLAS_NUM_THREADS=1`.
- No real dataset, patient record, real model output, signing key or protected artifact was accessed. No HTTP model serving was used. The backend remains `MOCK_SYNTHETIC` only.
