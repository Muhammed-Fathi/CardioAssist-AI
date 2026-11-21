# RH-04 Issue #132 — evidence matrix (machine-readable companion)

**Companion to:** [`docs/rh04-issue132-acceptance-decision.md`](../../../docs/rh04-issue132-acceptance-decision.md) (`rh04.issue132.acceptance-decision/v1`)
**Status:** `EVIDENCE_ONLY — NOT A FIXTURE, NOT A GOLDEN REFERENCE, NOT A COMPARATOR INPUT`
**Base commit:** `10bee67474b0eb9858f4ca6f298037c2f32459cc`
**Scope:** synthetic-only, research-only. No patient data, no real model output, no signing key, no clinical claim.

This file records **what was measured** and **what was not**. It intentionally contains no fitted coefficient, no observed score value and no reference digest other than the already-public frozen `PACK_SHA256`.

Vocabulary:

- `MEASURED_HERE` — executed on the environment in `environment` during this branch.
- `MEASURED_HISTORICAL` — reported in an existing GitHub run, issue comment or merged document; not re-executed here.
- `UNPROVEN` — no evidence; must not be cited as established.
- `DISPROVEN` — tested and does not hold.

---

## 1. Environment of record (`MEASURED_HERE`)

| Field | Value |
|---|---|
| OS | Debian GNU/Linux 12 (bookworm), glibc 2.36 |
| Architecture | x86-64 (Intel Xeon, exposes `avx2`, `avx512f`, `fma`) |
| Python | 3.11.2 |
| numpy | 1.26.4 |
| scipy | 1.15.3 |
| scikit-learn | 1.6.1 |
| NumPy OpenBLAS | `OpenBLAS 0.3.23.dev USE64BITINT DYNAMIC_ARCH NO_AFFINITY SkylakeX MAX_THREADS=64` |
| SciPy OpenBLAS | bundled `libscipy_openblas-68440149.so`, `DYNAMIC_ARCH`, host core `SkylakeX` |
| Thread pinning | `OPENBLAS_NUM_THREADS=1`, `OMP_NUM_THREADS=1` |
| Interpreter 3.12 | **unavailable in this sandbox** — see `G-01` |

---

## 2. Golden-replay verdicts by dispatch class (`MEASURED_HERE`)

Command: `OPENBLAS_CORETYPE=<class> OPENBLAS_NUM_THREADS=1 python -m research.intake.diagnose_fixture_replay`

| Dispatch forced | NumPy core resolved | SciPy core resolved | Verdict | Cases differing | Fields |
|---|---|---|---|---|---|
| *(unset)* | SkylakeX | SkylakeX | `EXACT_REPLAY` | 0 / 29 | — |
| `SkylakeX` | SkylakeX | SkylakeX | `EXACT_REPLAY` | 0 / 29 | — |
| `Cooperlake`¹ | Cooperlake | Cooperlake | `EXACT_REPLAY` | 0 / 29 | — |
| `Sandybridge` | Sandybridge | Sandybridge | `EXACT_REPLAY` | 0 / 29 | — |
| `Nehalem` | Nehalem | Nehalem | `EXACT_REPLAY` | 0 / 29 | — |
| `Haswell` | Haswell | Haswell | `MISMATCH_FOUND` | 2 / 29 | `da_a2_resting_v1` · `calibrated_log_odds` · 2.220e-16 (approved exception) <br> `da_a1_basic_clinical_v1` · `calibrated_log_odds` · **4.441e-16 (not excepted)** |
| `Zen` | **Haswell** (silent fallback) | **Haswell** | `MISMATCH_FOUND` | 2 / 29 | identical to `Haswell` |

¹ `Cooperlake` was exercised through the calibration-fit probe (§3), not through the full 29-case diagnostic.

**Reading:** the frozen pack is *exact* on the kernel family that generated it and drifts by exactly 1 ULP on one derived field elsewhere. No other field, status, structure or refusal changes anywhere.

---

## 3. Calibration-fit outputs by dispatch class (`MEASURED_HERE`)

Frozen golden cohort: 120 OOF observations, `clipped_logit_of_raw_probability`, `l2_anchor=1e-3`, bounds `((-15, 0.01), (15, 15))`, selected family `constrained_random_forest`. Values are reported as **hex-float equality classes**, never as decimal coefficients.

| Dispatch | SciPy L-BFGS-B `intercept` class | SciPy L-BFGS-B `slope` class | Derived `calibrated_log_odds` vs frozen (ULP) | Calibration `state_sha256` class | Portable-solver ULP vs frozen |
|---|---|---|---|---|---|
| SkylakeX | **A** (golden) | **A** (golden) | **0** | **A** | 421 754 321 |
| Cooperlake | A | A | 0 | A | — |
| Haswell | B | B | **+1** | B | 421 754 321 |
| Zen → Haswell | B | B | +1 | B | 421 754 321 |
| Sandybridge | C | C | **0** (compensating) | C | 421 754 321 |
| Nehalem | C | C | 0 | C | 421 754 321 |
| **Portable solver, any dispatch** | **single class** | **single class** | 421 754 321 (≈1.87e-7) | **single class** | — |

Two facts worth separating carefully:

1. `Sandybridge`/`Nehalem` produce **different parameters** (class `C`) yet the **same** derived `calibrated_log_odds`. Parameter equality is therefore *not* a valid proxy for score equality; only the derived field matters.
2. The portable solver disagrees with the frozen value by ≈4.2×10⁸ ULP **on every dispatch, identically**. That is convergence to the KKT point, not drift (§2.3 of the decision document).

### 3.1 L-BFGS-B convergence-control sweep on the same cohort (`MEASURED_HERE`)

| Configuration | Distinct `intercept` across 4 dispatches | Distinct derived value | Reproduces frozen on golden class | `‖projected grad‖∞` |
|---|---|---|---|---|
| SciPy default (production) | 3 | 2 | **YES** | 5.50e-08 |
| `ftol=1e-15` | 3 | 2 | YES | 5.50e-08 |
| `factr=1.0, pgtol=1e-12` | 3 | 2 | YES | 5.50e-08 |
| `gtol=1e-10` | 3 | **1** | **NO** (≈4.3e8 ULP) | 3.37e-10 |
| `gtol=1e-12, ftol=1e-16, maxiter=20000` | 3 | 2 | **NO** (≈4.2e8 ULP) | 7.7e-13 … 1.5e-12 |

**Reading:** there is no convergence-control setting that is simultaneously portable *and* faithful to the frozen reference. The only configuration that appears portable (`gtol=1e-10`) is far from the frozen value, i.e. it is a silent re-certification.

---

## 4. Stage attribution (`MEASURED_HERE`)

| Stage | Dispatch-stable | Measurement |
|---|---|---|
| Synthetic cohort + panel binding | YES | all 29 cases agree on every non-`calibrated_log_odds` field |
| OOF label vector `y` (n=120) | YES | single SHA-256 across 5 dispatches |
| OOF probabilities `p` | YES | single SHA-256 across 5 dispatches |
| OOF logits `safe_clipped_logit(p)` | YES | single SHA-256 across 5 dispatches |
| Random-forest tree thresholds | YES | single SHA-256 across 4 dispatches |
| Random-forest leaf values | YES | single SHA-256 across 4 dispatches |
| Random-forest `feature_importances_`, `n_estimators`, class order | YES | identical |
| **`scipy.optimize.minimize(method="L-BFGS-B")` 2-parameter fit** | **NO** | 3 parameter classes (§3) |
| Affine map `intercept + slope · raw_log_odds` | deterministic | reproduces frozen exactly from golden class |
| `expit(calibrated_log_odds)` → `calibrated_research_score` | YES | bit-identical under `Haswell` even though log-odds differed |
| Threshold flag, statuses, abstentions, provenance, SHAP/LIME, digests | YES | 29/29 identical |

### 4.1 BLAS reduction-order probe (`MEASURED_HERE`)

Distinct bit-patterns across `SkylakeX`/`Cooperlake`/`Sandybridge`/`Nehalem`/`Haswell`/`Zen`:

| Operation | n=2 | n=4 | n=8 | n=10 | n=20 | n=21 | n=64 | n=128 |
|---|---|---|---|---|---|---|---|---|
| `np.dot` (BLAS) | 1 | 2 | 1 | 2 | 2 | 2 | 3 | 3 |
| `math.fsum(products)` | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| sequential scalar loop | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| `np.sum(a*b)` | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| `np.einsum("i,i->")` | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |

Equivalence classes for `np.dot`: n≤10 → `{SkylakeX, Cooperlake}` vs `{Sandybridge, Nehalem, Haswell, Zen}`; n=64/128 → `Nehalem` separates from `{Sandybridge, Haswell, Zen}`.

**Reading:** the only BLAS-dependent operation the project relies on, at exactly the sizes Scipy's `__lbfgsb` uses, has host-dependent accumulation order. Every alternative accumulation strategy measured here is portable.

---

## 5. Bundle-artifact byte stability (`MEASURED_HERE`)

SHA-256 prefixes of bundle members produced by the same synthetic build under three dispatch classes:

| Member | SkylakeX | Haswell | Sandybridge | Stable |
|---|---|---|---|---|
| `preprocessing.json` | `0e01c35a` | `0e01c35a` | `0e01c35a` | **YES** |
| `shap_background.json` | `f9b1455d` | `f9b1455d` | `f9b1455d` | **YES** |
| `protocol.md` | `e3be6ff4` | `e3be6ff4` | `e3be6ff4` | **YES** |
| `model.joblib` | `cf71db42` | `35ac5209` | `a430c9c5` | no |
| `calibration.json` | `b1c566b4` | `2ead37b3` | `663de38a` | no |
| `evaluation_summary.json` | `bd7d4c62` | `83d5867a` | `fc928012` | no |
| `manifest.json` | `ac93f1bb` | `6664a465` | `7b690482` | no |

Localization test: with the **embedded calibrator parameters removed** from the comparison, the `model.joblib` payload is **bit-identical** across all three classes. Estimator tensors are stable; the only moving bytes are the two fitted calibration parameters (and their downstream manifestation in `evaluation_summary.json` / `manifest.json` hashes).

**Consequence:** the calibrated score is not currently a portable artifact property. No test exercises this today. Recorded as `G-06` in the decision document.

---

## 6. Historical evidence (`MEASURED_HISTORICAL`, not re-executed here)

| ID | Observation | Source |
|---|---|---|
| `H-01` | Same SHA `74d01f8`, same workflow, same runner-image tag `ubuntu24/20261116.376`, same `OPENBLAS_NUM_THREADS=1`: job FAIL (`4.441e-16`) then job PASS. Different VMs (`1000002832` vs `1000002839`). | run `44890830042`, jobs `136806043483`, `136809065781` |
| `H-02` | `OPENBLAS_CORETYPE=HASWELL` + `OPENBLAS_NUM_THREADS=1` + `NPY_DISABLE_CPU_FEATURES=AVX2,FMA3,AVX512F` **both** Python 3.11 and 3.12 jobs failed with the same two fields. | run `44896568228`, jobs `136823389344`, `136823389321` |
| `H-03` | `OPENBLAS_CORETYPE=SkylakeX` aborts before NumPy import on the hosted runner: `CPU does not expose avx512f`. | run `44901748832`, jobs `136838961519`, `136838961533` |
| `H-04` | Native Windows: exactly one differing field in 29 cases, `da_a2_resting_v1` `calibrated_log_odds`, 4.441e-16. | `docs/research/next_phase/RH047_RH048_SYNTHETIC_REPORT_ASSEMBLY.md` |
| `H-05` | PR #135 head `866372fa`: `synthetic-experiment-runner-validation` green on Python 3.11 **and** 3.12; jobs `136871347798`, `136871347695`. Dispatch class of those VMs not recorded at the time — the exact gap `G-01`/`G-03` describes. | run `44912564265` |

---

## 7. Preservation proof — frozen artifacts unchanged by this branch

| Artifact | Value | Changed |
|---|---|---|
| `research/intake/fixtures/offline_io.v1.json` raw SHA-256 | `206418e5f15787c5048c1ebad86d107e40ad4dfcbf727feb6b08ed305e273ab9` | **NO** |
| `research/intake/offline_fixture_pack.py :: PACK_SHA256` | `0307b396cea1e620c4004647e1d82ff7f292bb5b74de7cad1661e1299c6e7049` | **NO** |
| Case count | 29 | **NO** |
| `_approved_replay_equal` Cleveland exception (`da_a2_resting_v1` / `calibrated_log_odds`) | unchanged, not extended | **NO** |
| `ai/report_comparison.py :: ABS_TOL, REL_TOL` | `1e-12`, `1e-9` | **NO** |
| `.github/workflows/*` | unchanged | **NO** |
| `ai/calibration.py` default solver | `scipy_lbfgsb` | **NO** |
| `OPENBLAS_CORETYPE` / AVX-512 pins | none added (PR #134 pins rejected) | **NO** |

Verification command (must print nothing):

```bash
git diff --stat 10bee67474b0eb9858f4ca6f298037c2f32459cc -- \
  research/intake/fixtures research/intake/offline_fixture_pack.py \
  ai/report_comparison.py ai/calibration.py .github/workflows
```

---

## 8. What this matrix does **not** contain

- No patient record, real dataset row, or real model output.
- No fitted coefficient, intercept, slope, or observed synthetic score in decimal form (equality classes and ULP counts only).
- No signing key, artifact path, or bundle directory.
- No claim about clinical validity, model equivalence, RH-07 science or RH-08 release.
- No claim that Python 3.12, NumPy ≥ 2, ARM64, macOS or non-glibc `libm` behave identically.
- No claim that the portable solver is bit-portable across OS/libc — only across the dispatch classes tested on this one platform.

---

## 9. Addendum — the PR #136 CI failure is itself the decisive evidence

This branch's own first CI run **failed**, and it is the single strongest piece
of evidence in this document. It is recorded here rather than hidden because it
is exactly what a *reproducibility* investigation should be able to show.

### 9.1 Observation

| Field | Value |
|---|---|
| Run | `synthetic-experiment-runner-validation`, [44919728501](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/44919728501) |
| Head | `d271deee2cd9dc4e8a14ccd670422aa108da7566` (this branch) |
| Python 3.11 job | **FAILED** at `Run synthetic experiment-runner and dataset-audit tests` |
| Python 3.12 job | **FAILED** at the same step, and again at `Diagnose RH-04 fixture drift` |
| RH-04 structural diagnostic job (3.12) | **PASSED** |
| Other three workflows | **PASSED** (`contract-validation`, `mock-backend-validation`, `audit-toolchain-validation`) |

The exact failure payload, from the same 3.12 diagnostic step that is redacted by
design:

```
response mismatch: da_a1_basic_clinical_v1; redacted_field_diff=[
  {"absolute_delta": "4.441e-16",
   "field": "response.outcomes[0].score.calibrated_log_odds",
   "kind": "score_numeric",
   "within_existing_report_comparator_tolerance": true}]
```

This is **character-for-character the Issue #132 failure**. The Python 3.11 job's
full test count was likewise `1 failed, 2 skipped, 10 errors` — the same shape as
Issue #132 attempt 1 (`1 failed, 1615 passed, 2 skipped, 10 downstream fixture-setup
errors`; the passed count is higher only because this branch adds 32 tests).

### 9.2 Falsification of "Linux CI does not reproduce this"

Crucially, the **independent** `RH-04 fixture structural drift diagnostic (Python 3.12)`
job — a different VM (`GitHub Actions 1000003131`) in the same run — reported
`EXACT_REPLAY` twice. So within **one workflow run at one commit**:

| VM | Job | Verdict |
|---|---|---|
| `1000003130` | synthetic 3.11 | drift |
| `1000003133` | synthetic 3.12 | drift |
| `1000003131` | structural diagnostic 3.12 | exact |

Three jobs, one commit, three VMs, **two different arithmetic outcomes**. This
reproduces §3.2/`E-11` *prospectively* on a brand-new commit that touches no
production code, and it independently confirms the mechanism has nothing to do
with this PR's diff.

### 9.3 Falsification of "it is Linux-only" and "it is Python-version-specific"

The two failing jobs are Python **3.11 and 3.12 on the same Linux runner label**.
The drift therefore:

- is **not** Linux-vs-Windows (it fires on Linux),
- is **not** 3.11-vs-3.12 (it fires on both, and the 3.12 diagnostic passed),
- **is** dispatch-class dependent, exactly as §1.2 predicts.

### 9.4 Reproduction under the same conditions

Reconstructed locally by forcing the failing dispatch class:

```bash
OPENBLAS_CORETYPE=Haswell OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  BLIS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  python -m pytest tests/experiments tests/audit -q -W error
# -> 1 failed, 1676 passed, 2 skipped, 10 errors
#    identical signature to the CI job and to Issue #132 attempt 1
```

And the classifier correctly names it:

```bash
OPENBLAS_CORETYPE=Haswell OPENBLAS_NUM_THREADS=1 python -m research.intake.rh04_environment_class
# status = EXPECTED_SINGLE_FIELD_DELTAS, exit 1
# numpy_openblas_kernel = Haswell, scipy_openblas_kernel = Haswell
# differing_case_ids = [da_a1_basic_clinical_v1, da_a2_resting_v1]
```

### 9.5 Why this strengthens — rather than weakens — the recommendation

1. It is **direct evidence for P-4**: the defect is real, host-dependent, and
   reproducible at will on the very CI infrastructure the project uses. Pinning,
   tighter tolerances and reruns cannot fix a property of the allocated VM.
2. It is **direct evidence that the comparator is not broken**: nothing in this
   branch's diff caused it (the same signature appears at `main`'s own history),
   and the 10 downstream errors are the same fixture-setup cascade Issue #132
   already recorded.
3. It is **direct evidence that the classification gate is needed now**: three
   jobs in one run disagreed, and before this branch **none of them recorded
   which kernel it used**. That is the exact blind spot `G-01`/`G-03` names.
4. It shows the gate's exit-code-1 branch is correctly calibrated: this run is a
   *classified, expected* outcome — not a new defect and not a pass.

**This failure is left visible and un-retried on the PR.** Re-running until green
is precisely the behaviour Issue #132 forbids, and a green rerun would destroy
the best evidence the investigation has produced.

### 9.6 Bearing on the V2 prerequisites

`V2-04` requires `EXACT_REPLAY` on ≥3 dispatch classes × {3.11, 3.12} **plus**
native Windows. The section-9 observation is why `V2-04` cannot be satisfied by
a single green CI run, and why the dispatch class must be recorded *with* every
verdict rather than inferred from the outcome.
