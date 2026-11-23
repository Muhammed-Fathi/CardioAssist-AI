# Deterministic model fit + integrated pipeline — measured results

**Status:** isolated candidate (`D-V2-4`, `D-V2-6`), synthetic only. No production
activation, no certification, no authoritative pack regeneration.

Modules: `rh04_v2_model_fit.py` (`rh04.v2.decimal-model-fit/v1`),
`rh04_v2_integrated_candidate.py` (`rh04.v2.integrated-pipeline/v1`).

---

## 1. The declared objective — measured, not assumed

The pinned configuration (`ai/training.py`) is
`LogisticRegression(penalty="l2", solver="liblinear", C ∈ {0.01,0.1,1,10},
class_weight=None, random_state=seed)`, `fit_intercept=True` by default.

Probing the pinned scikit-learn 1.6.1 at three tolerances settled the objective:

| Assumed objective | ‖∇‖∞ at sklearn's solution |
|---|---|
| `0.5‖w‖² + C·Σ logloss` (intercept unpenalised) | **1.129e-04**, g_b 2.569e-02 |
| `0.5‖w‖² + (C/n)·Σ` | 4.899e-01 |
| `0.5‖w‖²/(C·n) + mean logloss`, intercept **unpenalised** | g_w 2.822e-06, **g_b 6.422e-04** |
| `0.5‖w‖²/(C·n) + mean logloss`, intercept **penalised** | **g_w 2.822e-06, g_b 2.226e-06** |

Only the last has both components small, and tightening `tol` drives both down
(1.478e-08 / 1.584e-08 at `tol=1e-8`, flat thereafter) — that is liblinear's
stopping rule, not a wrong objective.

**Declared objective:**

```
J(w,b) = 0.5‖w‖²/(C·n) + (1/n)Σ log(1+exp(-y_i(w·x_i+b))) + 0.5·b²/(C·n)
```

The **intercept is penalised** — the opposite of the calibration reference in
`ai/calibration.py`, which uses a different normalisation and a slope anchor at 1.
A test asserts the two objectives are never the same string, so the calibration
objective cannot be silently substituted for the model-training one.

## 2. Independent verification

Against a **separate 60-digit mpmath Newton solver** on the same inputs:

| Quantity | Δ (decimal solver − mpmath) |
|---|---|
| coef[0] | 2.52e-17 |
| coef[1] | 1.54e-17 |
| coef[2] | 8.98e-19 |
| intercept | 3.33e-19 |

Agreement is at binary64 rounding level, which is the strongest claim available.
The test is `test_model_fit_matches_an_independent_mpmath_oracle` (mpmath is used
as a **test-only** oracle, not a production dependency).

Convergence: 5 Newton iterations, `‖∇‖∞ = 5.36e-26`, against a declared criterion
of `1e-24`. sklearn agrees on the coefficients to 5.19e-08 — consistent with its
own `tol`, and **not** presented as equivalence.

## 3. Fail-closed behaviour

| Input | Behaviour |
|---|---|
| single class | `ModelFitError` |
| ragged matrix | `ModelFitError` |
| empty feature vector | `ModelFitError` |
| feature/label length mismatch | `ModelFitError` |
| `C <= 0` | `ModelFitError` |
| non-finite operand | `ModelFitError` |
| no objective decrease | `ModelFitError` |
| iteration budget exhausted | `ModelFitError` |

Hard designs all converge to `‖∇‖∞ ≤ 1e-24`: duplicated column, perfectly
correlated columns, 48/2 imbalance, features ×100, separable data, `C=0.01`,
`n=400 d=8`.

## 4. Two bugs found by measurement, not review

Both were mine and both are documented in the module so they cannot return:

1. **Inverted softplus branch.** The stable identity is
   `log(1+exp(-u)) = -u + log(1+exp(u))` for `u<0`; an earlier revision wrote
   `-u + log(1+exp(-u))`, producing **negative** log-losses. The objective
   diverged to `-6.18` instead of converging.
2. **Swapped sigmoid branches.** `_sigmoid_neg` returned `sigmoid(+u)` for `u>0`.
   The objective was unaffected (it uses softplus), so the fit *looked* like it
   converged while the gradient was wrong by ≈`n` and the iteration stalled at
   `2.17e-01`. This is precisely why the independent oracle matters: a
   self-consistent implementation would have "converged" to the wrong answer.

The Newton loop also uses **exact 1-D golden-section minimisation**, not an Armijo
test: at 50 digits a converged step can be smaller than the representable
decrease, which is the same failure mode measured on the calibration reference.

## 5. Architecture comparison — Path A vs Path B (measured)

n=200, d=10, 5 Newton iterations, then 500 exact scores:

| | Path A — synthetic refit | Path B — frozen parameters |
|---|---|---|
| Cost | **15.87 s** (fit) | **0.03 s** (load) + 0.032 s scoring |
| Reproducibility | deterministic *if* the fitter is deterministic | trivially exact; parameters are data |
| Auditability | must trust the fitter and its convergence proof | parameters are inspectable numbers |
| Security | unchanged | must protect a 265-byte integrity-bound artifact |
| Mathematical meaning | "the optimum of the declared objective" | "these exact numbers" |
| Maintenance | one more solver to keep correct | one more artifact to keep valid |

| Criterion | A | B |
|---|---|---|
| runtime | ✗ 530× slower | ✓ |
| reproducibility | ✓ (by declaration) | ✓ (by construction) |
| auditability | ✓ | ✓ simpler |
| mathematical meaning | ✓ stronger | weaker (no optimality claim) |
| security surface | ✓ smaller | ✗ new protected artifact |
| maintenance | ✓ no artifact | ✓ no solver |

**Recommendation — the smallest defensible design:** **Path B for the accepted
reference, Path A retained as the oracle that validates it.** Concretely: freeze
the synthetic parameters as integrity-bound reference data, and keep the refit as
an independent check that the frozen numbers are the declared optimum. This
satisfies the existing contract (exact replay of an exact reference) without
adding a second production solver, and it keeps a mathematical meaning attached to
the frozen values rather than "whatever we measured once".

This is a **recommendation for owner review**, not a substitution of the current
regeneration requirement. Replacing regeneration requires an explicit contract
amendment, which is `D-V2-7` below.

## 6. Integrated pipeline — end-to-end reproducibility

`run_pipeline` chains all four declared stages and is reproducible **bit for bit
across forced dispatches**:

```
host         19beafb7214c8b2257064cc590c13b9bce523166d7d007e55e389a12f9189951
Sandybridge  19beafb7214c8b2257064cc590c13b9bce523166d7d007e55e389a12f9189951
Prescott     19beafb7214c8b2257064cc590c13b9bce523166d7d007e55e389a12f9189951
Nehalem      19beafb7214c8b2257064cc590c13b9bce523166d7d007e55e389a12f9189951
```

This is the first end-to-end result in the whole V2 workstream that is
**independent of the resident BLAS kernel** — because no stage calls BLAS.

## 7. Downstream chain audit (item 8) — inspected, not assumed

| Stage | Actual implementation | Determinism |
|---|---|---|
| threshold flag | `ai/inference.py:681`: `cal_score >= exploratory_threshold` | signed comparison on the **calibrated** score; no float accumulation |
| rankings | monotone in a shared additive score | invariant |
| abstention / refusal | decided **before** scoring; never touches a float | invariant |
| SHAP / LIME | not in the 29-case replay paths for these cases; they consume the same coefficients | inherit S1, add nothing new |

Boundary evidence: only **2** of the pack's cases carry a calibrated score, and
none is within 0.05 of the 0.5 threshold, so the flag is not at risk in the
current pack. The exact scorer preserves the sign at 1e-12 from zero and returns
exactly `0.0` for an exact cancellation.

Detailed SHAP/LIME alignment measurement is **declined with a reason**, not
dropped: those stages are deterministic functions of the same coefficients, so
measuring them would restate §5 of the upstream document without adding
information.

## 8. New decisions raised

| ID | Question |
|---|---|
| `D-V2-5` | *(superseded by the recommendation above)* — do not adopt class-A-only exactness as the final answer |
| `D-V2-6` | **answered by this work**: a deterministic model fit exists and matches an independent oracle |
| `D-V2-7` | **new** — adopt Path B (frozen synthetic parameters + refit oracle) as the reference architecture, replacing the regeneration requirement? This is a contract amendment and needs explicit owner approval. |

---

## Native Windows verification — copy-ready PowerShell

Prepared for the owner/reviewer (review item 11). This cannot be executed in the
Linux sandbox, so it is provided rather than claimed.

```powershell
# 1. Clone and check out the exact candidate
git clone https://github.com/Muhammed-Fathi/CardioAssist-AI.git
cd CardioAssist-AI
git fetch origin review/rh04-v2-p0-corrections-20261121
git checkout 1aa0b28b72c9d7a65b6cdab9ccb92789c51e4ac9   # PR #139 head

# 2. Isolated environment, pinned deps only
py -3.12 -m venv .venv-rh04
.\.venv-rh04\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r research/experiments/requirements.txt
python -m pip install -r research/audit/requirements.txt
python -m pip check

# 3. Record what is actually resident (do NOT trust OPENBLAS_CORETYPE)
python -c "from threadpoolctl import threadpool_info; import json; print(json.dumps([dict(x) for x in threadpool_info()], indent=1))"

# 4. The deterministic pipeline must reproduce this digest exactly:
python -c @"
import numpy as np
from research.intake.rh04_v2_integrated_candidate import run_pipeline, pipeline_digest
rng = np.random.RandomState(21)
X = rng.randn(60,5); y = (rng.rand(60) < 0.5).astype(int); Z = rng.randn(30,5)
r = run_pipeline([[float(v) for v in a] for a in X], [int(v) for v in y],
                 [[float(v) for v in a] for a in Z])
print(pipeline_digest(r))
"@
# EXPECTED: 19beafb7214c8b2257064cc590c13b9bce523166d7d007e55e389a12f9189951

# 5. V2 candidate suite
python -m pytest tests/experiments/test_rh04_v2_reference.py -q -W error

# 6. Independent Oracle check (optional, test-only dependency)
python -m pip install mpmath==1.4.1
python -m pytest tests/experiments/test_rh04_v2_reference.py -q -k mpmath_oracle
```

**What to report back:** step 3's resident kernel list, step 4's digest, and the
pass/fail counts from steps 5-6. If step 4 differs from the expected digest, that
is a genuine portability finding — report it, do not adjust the expectation.
