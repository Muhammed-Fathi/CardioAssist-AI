# Full 29-case reference candidate — results and corrected evidence

**Status:** unratified candidate. Synthetic only. No production activation, no
certification, no pinned acceptance pack. `FULL_REFERENCE_SENTINEL =
"UNRATIFIED_CANDIDATE_NOT_AN_ACCEPTANCE_PACK"`.

Module: `research/intake/rh04_v2_full_reference.py`
(`rh04.v2.full-reference-candidate/v1`).

---

## 1. The calibration-ordering defect (P0-01) — confirmed, severe

`decimal_logistic_fit` returns `(a, b)` with the declared objective
`eta = a + b*logit`: **`a` is the intercept, `b` is the slope**. The production
contract agrees — `OofLogisticCalibrator.transform_log_odds` is
`self.intercept + self.slope * raw_logits`.

The integrated candidate unpacked it as `slope, offset` and then evaluated
`slope*logit + offset`. Measured on the recorded 60×5 fixture:

| | value |
|---|---|
| returned `a` (intercept) | `0.004188982810775449` |
| returned `b` (slope) | `1.1249169603284037` |
| correct calibrated log-odds[0:3] | −0.508477, 0.936736, 0.337145 |
| reversed calibrated log-odds[0:3] | 1.123008, 1.128390, 1.126157 |
| **max |correct − reversed|** | **4.262104** |

A slope of 1.1249 was being used as 0.0042. The calibrated reference was wrong
across the board.

**Why every test passed anyway:** a parameter swap does not break determinism. All
reproducibility, cross-kernel and byte-stability tests were satisfied by a
confidently wrong reference. This is the same failure class as the two solver
bugs found earlier, and it is the strongest argument in this workstream for
verifying against an *external* contract rather than internal consistency.

**Regression pin:** `test_calibration_order_matches_the_production_calibrator`
constructs the real `OofLogisticCalibrator` dataclass and requires
`np.array_equal` with `intercept + slope*raw`. A second test requires the fit
tuple to land near `(0, 1)` on perfectly-calibrated inputs.

### Digest history (explicit, not silently updated)

| Version | Digest | Meaning |
|---|---|---|
| v1 | `19beafb7…` | **REVERSED parameters — incorrect.** Historical evidence only, never a reference. |
| v2a | `5ff6ce16…` | ordering fixed, before provenance fields were added |
| v2b | `fb6c87b9…` | current |

## 2. Two source-specific objectives (P0-02)

`ai/training.py::_build_estimator` selects **liblinear** for
`CLEVELAND_D047_FROZEN_V1` and **lbfgs** for `AI1_GENERIC_V1`. Only liblinear
penalises the intercept. Measured on the pinned wheel set:

| assumption | ‖∇‖∞ at the sklearn solution |
|---|---|
| lbfgs, intercept **unpenalised** | g_w 1.261e-08, **g_b 9.160e-09** |
| lbfgs, intercept **penalised** | g_w 1.261e-08, **g_b 7.157e-04** |

Both objectives are now declared separately and selected by profile:

| profile | solver | intercept | objective |
|---|---|---|---|
| `CLEVELAND_D047_FROZEN_V1` | liblinear | **penalised** | `0.5‖w‖²/(C·n) + mean logloss + 0.5b²/(C·n)` |
| `AI1_GENERIC_V1` | lbfgs | **unpenalised** | `0.5‖w‖²/(C·n) + mean logloss` |

An unknown profile raises rather than defaulting, and each profile is verified
against *its own* pinned sklearn solver (agreement ≈5e-08, i.e. sklearn's `tol`).

## 3. The full 29-case reference (P0-03)

### What it does

Executes the registered replay for all 29 cases: the real source bundles, the real
five routes, the real case ids/requests/edits/ordering, the **preserved**
out-of-fold calibration contract, and the **preserved** model-selection
methodology.

### What it deliberately does not do

The production model fit is **not** replaced. The review warned against assuming
logistic regression, and measurement confirms why — instrumenting
`_build_estimator` on the REST route alone:

```
estimators built: {l2_logistic_regression: 100,
                   constrained_random_forest: 128,
                   prevalence_dummy: 12}
```

Three families are genuinely constructed and compared. Substituting a different
fitter would change model selection, so the deterministic fitter is used as an
**oracle** (`measure_model_families`, profile tests), not as a replacement.

Expected responses are **not** copied: every outcome is produced by calling the
real entry point.

### Results

Generated twice in ~117 s each, **identical semantic digest** `aea7d6179f32f272…`,
14 fit invocations, 29 cases.

### V1 → candidate mapping (item 7)

**2 of 29 cases changed**, exactly the 4 calibrated score paths:

| case | differing paths |
|---|---|
| `da_a2_resting_v1` | `outcomes[0].score.calibrated_log_odds`, `.calibrated_research_score` |
| `da_a1_basic_clinical_v1` | same two paths |

Everything else — all refusal, abstention, unavailable and error semantics — is
byte-identical to V1. This matches the earlier V2 candidate, as it should: both
apply the same decimal calibration seam to the same path.

## 4. Cross-environment evidence (item 10) — requested ≠ resident

Cold-process runs, full-reference generation, resident kernels read from
threadpoolctl:

| requested | NumPy resident | SciPy resident | semantic digest |
|---|---|---|---|
| *(unset)* | SkylakeX 0.3.23.dev | SkylakeX 0.3.28 | `aea7d617…` |
| `Sandybridge` | Sandybridge 0.3.23.dev | Sandybridge 0.3.28 | `3366be81…` |
| **`Prescott`** | **Prescott** 0.3.23.dev | **Katmai** 0.3.28 | `3366be81…` |
| `Nehalem` | Nehalem 0.3.23.dev | Nehalem 0.3.28 | `aea7d617…` |

**Two findings the reviewer specifically predicted:**

1. **A request is not a fact.** Requesting `Prescott` resolved NumPy to Prescott
   but SciPy to **Katmai** — a different kernel entirely. Any experiment that
   records only `OPENBLAS_CORETYPE` as the environment is wrong.
2. **Four requests are not four environments.** There are two distinct resolved
   numerical classes here, not four: `Sandybridge`/`Prescott` collapse to one
   digest, `Nehalem` collapses onto the host class.

And the honest consequence: **the full reference is NOT kernel-invariant.** It
inherits the V1 kernel sensitivity because it preserves the real production fit
and model selection. Only the *isolated* integrated pipeline
(`19beafb7…`/`fb6c87b9…` family) is kernel-invariant, because it calls no BLAS.
Claiming the full reference is portable would be false.

## 5. Path A vs Path B (item 5)

| | Path A refit | Path B frozen |
|---|---|---|
| cost | **23.59 s** fit + 0.052 s score | **0.056 s** load+verify+score |
| artifact | none | 1049 bytes |
| replay | reference | **exact equality with Path A** |

Path B round trip verifies source, feature contract (including order), family,
training inputs, split, protocol version, and artifact integrity; it refuses
tampered parameters, a wrong source, a wrong protocol version, a reordered panel
and a missing binding, and it refuses to freeze a family that has no linear
parameter vector (a forest is not a linear model).

**`D-V2-7` remains proposed and unratified.** Path A is still the only path that
produces a reference.

## 6. What is still not measured

| Item | Status |
|---|---|
| Python 3.12 | **NOT MEASURED** in this sandbox |
| Native Windows | **NOT MEASURED** |
| Third distinct resolved class beyond these two | **NOT FOUND** locally |
| SHAP / LIME | outside the 29-case exported fields; separate RH-07 evidence needed |

## 7. Native Windows verification — corrected

The previous instructions checked out `1aa0b28`, which **does not contain** this
candidate. Corrected, for the delivered commit `3e4a138`:

```powershell
git clone https://github.com/Muhammed-Fathi/CardioAssist-AI.git
cd CardioAssist-AI
git fetch origin review/rh04-v2-p0-corrections-20261121
git checkout 3e4a1387f3cc4891ce06fa0203f6627555733253
git rev-parse HEAD   # MUST print 3e4a1387f3cc4891ce06fa0203f6627555733253

py -3.12 -m venv .venv-rh04
.\.venv-rh04\Scripts\Activate.ps1
python -m pip install -r research/experiments/requirements.txt
python -m pip install -r research/audit/requirements.txt
python -m pip install -r research/experiments/requirements-oracle.txt
python -m pip check

# Resident kernels, REDACTED (no filesystem paths, no build hashes)
python -c @"
from threadpoolctl import threadpool_info
for x in threadpool_info() or []:
    print({k: x.get(k) for k in ('internal_api','architecture','version','num_threads')})
"@

# Full 29-case candidate (about 2 minutes)
python -c @"
from research.intake import rh04_v2_full_reference as FR
pack = FR.generate_full_reference()
print('semantic:', FR.semantic_digest(pack))
print('cases:', len(pack['cases']))
"@
# EXPECTED on a class-A host: aea7d6179f32f272cbad53be2814e33a13bf4c65cc861a9dfd5af50346484a60
# A DIFFERENT digest is a PORTABILITY FINDING: report it. Never regenerate the
# expectation from your own run.

python -m pytest tests/experiments/test_rh04_v2_reference.py -q -W error
```

The canonical test suite and the negative tests must both be run; a failure is
reported, not adjusted.
