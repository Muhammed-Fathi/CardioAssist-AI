# RH-04 Issue #132 — engineering acceptance decision for intermittent UCI-412 Golden Replay drift

**Document version:** `rh04.issue132.acceptance-decision/v1`
**Status:** `PROPOSED — NOT RATIFIED`. Decision record only. **No production behaviour, fixture, digest, comparator, tolerance or workflow file is changed by this branch.**
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

> The frozen RH-04 29-case Golden Replay is **exactly reproducible only on the OpenBLAS dynamic-architecture dispatch class that generated it** (observed: `SkylakeX`/`Cooperlake`). On other dispatch classes the derived field `response.outcomes[0].score.calibrated_log_odds` differs by 1 ULP. This is an arithmetic-order artifact of the two-parameter SciPy L-BFGS-B calibration fit, not a model, data or semantic difference.

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

| Forced `OPENBLAS_CORETYPE` | NumPy OpenBLAS core | SciPy OpenBLAS core | `python -m research.intake.diagnose_fixture_replay` | Differing fields |
|---|---|---|---|---|
| *(unset — host)* | SkylakeX | SkylakeX | `EXACT_REPLAY`, 0/29 | — |
| `Haswell` | Haswell | Haswell | `MISMATCH_FOUND`, 2/29 | `da_a2_resting_v1` 2.220e-16; `da_a1_basic_clinical_v1` **4.441e-16** |
| `SkylakeX` | SkylakeX | SkylakeX | `EXACT_REPLAY`, 0/29 | — |
| `Sandybridge` | Sandybridge | Sandybridge | `EXACT_REPLAY`, 0/29 | — |
| `Nehalem` | Nehalem | Nehalem | `EXACT_REPLAY`, 0/29 | — |
| `Zen` | Haswell¹ | Haswell¹ | `MISMATCH_FOUND` | same as `Haswell` |

¹ This OpenBLAS build has no `Zen` kernel; it falls back to `Haswell`. Recorded here because it is itself evidence that a *name* is not a *kernel* (§7.3, evidence gap `E-07`).

**Conclusion:** the two deltas in Issue #132 are reproduced exactly, byte-for-byte, and are a **pure function of the OpenBLAS dynamic-architecture dispatch class**. They are not reproduced by "Python 3.11 vs 3.12", not by thread count, and not by runner-image drift.

`tests/experiments/test_offline_fixture_pack.py::test_golden_replay` fails under `OPENBLAS_CORETYPE=Haswell` with exactly the Issue #132 message (`1 failed, 49 passed`), and `test_rh04_replay_tolerance.py` correctly refuses to extend the pre-existing Cleveland exception to the UCI-412 case. **The comparator's narrowness is working as designed.**

---

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

`np.dot` splits into at least two *equivalence classes*: `{SkylakeX, Cooperlake}` (the golden class) and `{Sandybridge, Nehalem, Haswell, Zen}`, with `Nehalem` diverging a third time at n=64/128. This is exactly the FMA/SIMD-reduction-order difference between kernels, and it is the only stage in the whole pipeline that depends on it.

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

Therefore "make the default solver portable so the frozen fixture passes everywhere" is **not a sound engineering objective**. It is mathematically unavailable without emulating one specific SIMD reduction order, which would be non-portable hardware specificity wearing a portable costume (`docs/rh04-portable-deterministic-calibration.md` §3, still correct).

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
| `E-01` | The drift is **deterministic per dispatch class**, not run-to-run. 4 repeated isolated subprocesses on the same core produce **1** distinct outcome. | §1.2, §3.2 |
| `E-02` | The exact two Issue #132 deltas (2.220e-16, 4.441e-16) are reproduced from a forced `Haswell` dispatch. | §1.2 |
| `E-03` | Exactly **one** semantic field differs in the whole 29-case pack, and only in the two `SYNTHETIC_RESULT` score cases. | §1.2 |
| `E-04` | The divergence first appears **inside** the SciPy L-BFGS-B fit; every input to it and every other pipeline stage is bit-identical across dispatches. | §2.1 |
| `E-05` | `np.dot` at L-BFGS-B's internal sizes has ≥2 dispatch equivalence classes; `math.fsum`, sequential scalar accumulation, `np.sum(a*b)` and `np.einsum` do not. | §2.2 |
| `E-06` | Tightening L-BFGS-B convergence **moves away** from the frozen value by ≈4×10⁸ ULP and does not remove dispatch dependence of the parameters. | §2.3 |
| `E-07` | The opt-in `deterministic_portable_newton` solver is **bit-identical** across 5 dispatch classes on the **real** golden cohort, and lands ≈1.87e-7 in log-odds from the frozen value. | §5.2 |
| `E-08` | Thread count does **not** matter here (`OPENBLAS_NUM_THREADS` 1/2/4 identical). | §3.2 |
| `E-09` | Every differing bundle byte is attributable to the calibration fit; estimator and preprocessing bytes are stable. | §2.4 |
| `E-10` | `OPENBLAS_CORETYPE=Zen` on this wheel silently falls back to `Haswell` — env-var *names* do not identify *kernels*. This is the same class of error that broke PR #134's `SkylakeX` pin (#134 was right to reject it). | §1.2 |

### 3.2 Established by the historical record (not re-run here)

| ID | Claim | Source |
|---|---|---|
| `E-11` | Same SHA, same workflow, same runner-image tag, same `OPENBLAS_NUM_THREADS=1` produced FAIL then PASS. | Issue #132 jobs `136806043483` / `136809065781` |
| `E-12` | Pinning `OPENBLAS_CORETYPE=HASWELL` + `NPY_DISABLE_CPU_FEATURES=AVX2,FMA3,AVX512F` did **not** cure the drift. | Issue #132 comment 2026-11-21T11:01:23Z; run `44896568228` |
| `E-13` | Pinning `OPENBLAS_CORETYPE=SkylakeX` is **impossible** on the hosted runners (no `avx512f`); it aborts before NumPy import. | run `44901748832`, jobs `136838961519` / `136838961533`; PR #134 |
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

Because the two CI jobs at the same SHA in `E-11` differed with identical inputs, identical pinned thread counts, identical pinned wheels and identical runner-image tag, **dispatch class selection differs across GitHub-hosted VMs of the same runner label**. Combined with `E-01`, the intermittent symptom is fully explained by *host heterogeneity*, not by nondeterminism. This is a stronger and more useful statement than "flaky", and it is exactly what makes an environment-scoped V1 contract defensible (§6, P-4).

---

## 4. What must NOT be done (and why the obvious fixes are wrong)

| Tempting fix | Why it is rejected |
|---|---|
| Add a `da_a1_basic_clinical_v1` tolerance exception like the Cleveland one | Correct-by-tolerance, but it silently makes the reference comparison **pairwise-approximate** on the one field whose exactness the project advertises. It also cements an unportable reference instead of replacing it. Requires its own owner decision; not this PR. |
| Change `gtol`/`ftol`/`factr` | §2.3: re-certifies every golden value by ≈4×10⁸ ULP while appearing to be a "numerical tightening". The most dangerous option in the list because it *looks* principled. |
| Make the deterministic solver the default | §2.3/`E-07`: portable and correct, but disagrees with the frozen reference by ≈1.9e-7. Doing this without re-freezing silently invalidates the V1 contract; doing it with re-freezing is P-2, which needs owner re-certification. |
| Hardcode golden coefficients / a lookup table | Prohibited by Issue #132 and by `AGENTS.md` (never fabricate reference values). |
| Add an AVX-512 pin, or disable AVX-512 | `E-13`: physically impossible on the hosted runners. `E-12`: empirically ineffective. |
| Add a `pytest.skip`/`xfail` conditional on dispatch | Turns a real, informative failure into a silent hole; the whole point is that the failure is *evidence*. |
| Re-run until green | Issue #132 explicitly forbids it, and `E-01` shows it manufactures a false narrative of flakiness. |
| Raise `ABS_TOL`/`REL_TOL` in `ai/report_comparison.py` | Those are the AI-12.1 *report* comparator, used by a different contract; widening them to rescue the pack conflates two independent guarantees. |
| Blame Windows / Python 3.12 | §1.2/§3.3/`E-03` falsify this: the delta is dispatch-driven and appears on Linux too. |

---

## 5. Candidate acceptance approaches, compared

All four are legitimate engineering positions. They are compared on what the repository actually needs: a defensible, honest, *checkable* reproducibility contract for a research-only prototype, at $0, on GitHub-hosted Linux plus a human's Windows machine.

### P-1 — "Preserve legacy V1 exact replay on explicitly supported environments only"

Keep the pack, digest, comparator, tolerances and workflow byte-identical. Declare the exact-replay contract **environment-qualified**: it holds on dispatch class `{SkylakeX, Cooperlake}` under the pinned wheel set; elsewhere the same check is expected to report the single documented field delta and is *not* an acceptance gate.

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

Formally accept **P-1 + P-3 as one bounded, expiring migration contract**, with **P-2 as the declared destination and the only exit**:

1. **V1 is re-declared, not weakened.** The 29-case pack, canonical digest `0307b396…`, `_approved_replay_equal`, tolerances and workflow stay byte-identical. The *contract text* changes: V1 exact replay is **guaranteed** on the golden dispatch class and **expected to report exactly one documented deltas-only field** elsewhere. Nothing in V1 becomes approximate: the Cleveland precedent remains the only tolerance exception, and it is **not** extended.
2. **A dispatch-diagnostic gate replaces the ambiguous gate.** CI gains one non-scoring step that records (a) actual OpenBLAS kernel names for NumPy *and* SciPy, (b) `numpy`/`scipy`/`sklearn`/`glibc` versions, (c) the exact-replay verdict. Expected outcomes are enumerated; anything else fails closed. This converts "intermittent" into "classified".
3. **V2 is scheduled, not improvised.** P-2 has a written prerequisite list (§7) and a named owner decision that must precede any code change.
4. **The exit is explicit.** The migration contract carries an expiry condition: when the V2 pack is re-certified and merged, the V1 environment-qualification and any comparator exception are **deleted**, not retained.

Why P-4 wins:

- It is the **only** option that is both honest *now* and convergent. P-1 alone is honest but non-convergent (CI stays VM-lottery). P-3 alone converges on a non-goal (stops detecting). P-2 is convergent but cannot be executed safely from a decision PR and needs owner re-certification.
- It preserves the **maximum** number of frozen artifacts while making the *actual* observed behaviour describable in one sentence.
- It keeps the failure **visible** (`E-03`: exactly one field, two cases) instead of converting it to a skip or a tolerance.
- It creates the evidence P-2 requires. `E-06`/`E-07` are only trustworthy *because* the current fixture is exact somewhere; a V2 re-certification without the V1 comparator intact would have no anchor. That is why dual contracts are needed during migration, not just desirable.

**Explicitly rejected as a sole basis for approval:** "it makes CI green". Under P-4, a green run at the golden class and a *classified, expected* deltas-only result elsewhere are both acceptable outcomes — and an **unexpected** third outcome still fails. Greenness is a consequence, never the criterion.

### 5.1 Comparison matrix

| Criterion | P-1 environment-scoped V1 | P-2 V2 re-certification | P-3 comparator exception | **P-4 dual contract (recommended)** |
|---|---|---|---|---|
| Frozen V1 pack/digest/comparator untouched | ✅ | ❌ (new pack) | ⚠️ comparator edited | ✅ (text only) |
| Backward compatibility | ✅ | ⚠️ migration window | ✅ | ✅ |
| Model-calibration semantics preserved | ✅ | ⚠️ parameters move ≈1e-7 | ✅ | ✅ |
| Cross-platform reproducibility | ❌ undeclared | ✅ (bounded, `E-07`) | ❌ still host-dependent | ⚠️ V1 scoped, V2 planned |
| Fixture provenance | ✅ unchanged | ⚠️ new provenance needed | ✅ | ✅ |
| Security assertions preserved | ✅ | ✅ (must re-assert) | ⚠️ risk of scope creep in `_approved_replay_equal` | ✅ (no branch in the comparator) |
| Regression impact | none | medium-high | low | **low, additive** |
| Honest CI signal | ⚠️ VM-dependent | ✅ | ⚠️ masks | ✅ classified |
| Deliverable from a decision PR | ✅ | ❌ | ❌ (needs owner approval) | ✅ |
| Convergence to a real fix | ❌ | ✅ | ❌ | ✅ (V2 is the exit) |

---

## 6. Recommended path — specification for the follow-up implementation PR

> **This section is a specification, not an implementation.** No file outside `docs/` is modified by this branch.

**Step 1 (owner decision, no code):** ratify the acceptance vocabulary. The 29-case pack is `EXACT_ON_GOLDEN_DISPATCH` / `DELTAS_ONLY_ELSEWHERE`; the machine-readable expected-outcome set is the two-element set in Step 2. Nothing else changes.

**Step 2 (CI, non-scoring):** add one step, *before* the scoring pytest step, to each of the three synthetic jobs and both Python versions. It must:
- read the **actual** kernel names via `scipy.libs.libscipy_openblas*.so::scipy_openblas_get_corename` and `numpy.libs.libopenblas*.so::openblas_get_corename64_` (not the `OPENBLAS_CORETYPE` string — see `E-10`);
- print `numpy`/`scipy`/`scikit-learn`/`glibc`/`platform` versions, Python version, and the two kernel names, with **no** paths, scores or keys;
- run `python -m research.intake.diagnose_fixture_replay`, capture its JSON, and reduce it to a verdict: `EXACT_REPLAY` → pass; `MISMATCH_FOUND` with *exactly* the `{da_a2_resting_v1, da_a1_basic_clinical_v1} × calibrated_log_odds × within_existing_report_comparator_tolerance: true` field set and nothing else → pass with an annotation; anything else → **fail**;
- never parse, rewrite or echo numeric values.

**Step 3 (tests, negative-first):** a new test module must fail if:
- any mismatch appears that is not one of the two enumerated fields;
- any enumerated field's `within_existing_report_comparator_tolerance` is `false`;
- the delta grows beyond the AI-12.1 band (`rel_tol=1e-9`, `abs_tol=1e-12`);
- `PACK_SHA256` changes;
- `len(cases) != 29`;
- `_approved_replay_equal` gains a second case/field branch.

**Step 4 (documentation):** amend `docs/rh04-portable-deterministic-calibration.md` and the RH-07/RH-08 risk registers with the §0 sentence and the classification table.

**Step 5 (V2, separate PR, owner re-certification required):** see §7 prerequisites.

**Do not, in that PR:** change the default solver; change `ABS_TOL`/`REL_TOL`; touch `research/intake/fixtures/offline_io.v1.json`, `PACK_SHA256`, `_approved_replay_equal`'s Cleveland branch or `_WINDOWS_FLOAT_CASE_ID`/`_WINDOWS_FLOAT_FIELD`; add `pytest.skip`/`xfail`/`continue-on-error`; import PR #134's AVX-512 guards or workflow pins; activate any real-data path.

### 6.1 The `docs/rh04-portable-deterministic-calibration.md` §5 options, re-judged

That document proposed "Option A — fixture re-certification" and "Option B — bounded tolerance exception". Measured evidence now ranks them:

- **Option B is weaker than presented.** It was framed as an equivalent alternative to A. It is not: it is non-convergent (§5 P-3) and, on the measured evidence, the deltas can appear in *either* executable case (`da_a2_resting_v1` at 2.220e-16 and `da_a1_basic_clinical_v1` at 4.441e-16 in the same run), so a per-case exception is a per-case lottery, not a stable boundary. P-3 must be time-boxed and paired with the dispatch diagnostic, which is what P-4 does.
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
| `M-02` | `Haswell` → 2 cases, 2.220e-16 + 4.441e-16, one field each | **measured** | same | this branch |
| `M-03` | `Sandybridge`, `Nehalem`, `Cooperlake` → `EXACT_REPLAY` | **measured** | same | this branch |
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
| `M-14` | `HASWELL` + `NPY_DISABLE_CPU_FEATURES` does not cure | **historical** | CI | `E-12` |
| `M-15` | `SkylakeX` pin impossible on hosted runners | **historical** | CI | `E-13` |
| `M-16` | Windows: one Cleveland field, 4.441e-16 | **historical** | native Windows | `E-14` |
| `M-17` | Python 3.12 dispatch behaviour | **unproven here** | CI only | `G-01` |
| `M-18` | NumPy≥2 / SciPy≥1.16 / ARM64 / macOS / non-glibc libm | **unproven** | — | `G-05` |

---

## 11. Answers to the deliverable's explicit questions

**Which aspects of reproducibility have been experimentally established?**
Additive-in-ULP determinism per dispatch class (`E-01`); full stability of every pipeline stage except the two-parameter calibration fit (`E-04`, `M-08`, `M-09`); exactness of the frozen reference on the golden class (`M-01`); the *maximum* magnitude of the deviation on any tested class (`M-02`: 1 ULP, one field, two cases); and the existence of a portable fit (`M-11`).

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
