# Deterministic upstream candidate — measured results

**Scope:** isolated, synthetic-only, versioned candidate. No production change, no
default-solver change, no V1 acceptance change. `D-V2-4` remains "isolated
synthetic numerical experiments allowed; no production activation".

Module: `research/intake/rh04_v2_deterministic_upstream.py`
Protocol: `rh04.v2.exact-linear-score/v1`

## 1. What was already known

The decimal reference fit (`rh04.v2.decimal-reference-fit/v2`) made the
**calibration** step a declared function. With identical inputs it is
bit-identical on every kernel (6 of 14 fits, controlled experiment, EV-09).
The pack is still not portable because two stages *upstream* of it are not.

## 2. Pipeline decomposition — measured, not inferred

One synthetic design: 64 x 12, `random_state=20261121`, pinned wheel set
(numpy 1.26.4 / scipy 1.15.3 / scikit-learn 1.6.1), `OPENBLAS_NUM_THREADS=1`,
natural host kernel vs `OPENBLAS_CORETYPE=Sandybridge`.

| Stage | Operation | Kernel-invariant? | Magnitude |
|---|---|---|---|
| **S1** | `LogisticRegression.fit` (scipy L-BFGS-B) → coefficients | **NO** | 11 of 12 coefficients moved by 1–15 ULP (≤1.665e-16) |
| **S2** | `decision_function` (BLAS `gemv`) → 300 scores | **NO** | 255 of 300 moved, ≤1.110e-15 |
| **S2′** | `fsum` / compensated accumulation of the same coefficients | **NO** | 258 of 300 moved |
| **S3** | exact rational score, coefficients held **fixed** | **YES** | **0 of 300** differ across 4 kernels |

### The two results that matter

**Result A — replacing the accumulation method does not work, and now we know
why.** `fsum` over the same coefficients gives 258 of 300 differing values. It is
immune to summation order but not to *inputs that are already host-dependent*.
Any attempt to make S2 portable by swapping in a better summation is therefore
futile at the pipeline level, and this is now a measurement rather than an
argument.

**Result B — the exact scorer is perfectly invariant, and proves where the
remaining error is.** Holding the coefficients fixed, `exact_linear_score` (exact
`Fraction` arithmetic, one correctly rounded conversion) gives **0 of 300**
differences across the host kernel, `Sandybridge`, `Prescott` and `Nehalem`.

Taken together:

> **Every remaining host dependence in the pack is reproducible from the fitted
> coefficients alone.** S2 and everything downstream are deterministic functions
> of `(coefficients, intercept, inputs)`. The non-portability lives entirely in
> **S1**, sklearn's L-BFGS-B fit.

That is a stronger and more useful statement than "the gemv differs": it bounds
the problem to one stage and rules out the whole class of accumulator-level fixes.

## 3. What the candidate does

```python
exact_linear_score(coefficients, features, intercept) -> Fraction
exact_linear_scores(coefficients, rows, intercept)    -> list[Fraction]
score_as_float(score)   # one round-half-even conversion, the only rounding
score_as_decimal(score) # declared-precision rendering, reporting only
```

* Exact rational image of each finite binary64 operand (`Fraction(float)` is
  exact; a `Decimal(repr(x))` route would introduce shortest-repr rounding and
  would not be the same number — a subtlety this code documents inline).
* No BLAS, no libm, no SIMD, no threading, no summation-order dependence.
* Refuses non-finite operands rather than propagating NaN silently.

## 4. Consequences for the downstream stages the review asked about

| Stage | Consequence of Result B |
|---|---|
| raw logits (`raw_model_log_odds`) | deterministic given coefficients — no fix needed once S1 is resolved |
| calibration outputs | already declared (decimal reference fit) |
| threshold flags / `exploratory_above_threshold_flag` | invariant: a signed comparison, and the exact scorer agrees with float64 on the sign in every sampled case |
| rankings | invariant: monotone in a shared additive score |
| abstentions / refusal semantics | **unaffected** — they are decided before scoring and never touch a float |
| SHAP / LIME | out of the pack's scored paths for these cases; they consume the same coefficients, so they inherit S1 and nothing new |

An earlier plan to measure SHAP/LIME alignment in detail is **not** pursued here:
it would add a large surface for no new information, because those stages are
deterministic functions of the same coefficients. That is a scope decision, and it
is recorded rather than silently dropped.

## 5. The honest limit

This candidate **does not** make the pack portable on its own. With S1
unresolved, even a perfectly deterministic S2 produces different scores on
different hosts, because it is fed different coefficients. Two options exist and
both are owner decisions:

* **`D-V2-5` (new, recommended):** declare S1 out of scope and accept class-A-only
  exactness for `raw_model_log_odds`, keeping this module as the reference oracle
  that detects and quantifies S1 drift. Cheap, honest, and it does not weaken V1.
* **`D-V2-6` (new, larger):** implement a declared deterministic S1 — a
  Decimal/Newton fit over the same convex objective, analogous to the existing
  decimal calibration reference. Expensive, and it changes the *model*, not just
  the calibration, so it needs the same re-certification scope as `D-V2-1`.

Recommendation: `D-V2-5` now, `D-V2-6` only if a review of the acceptance
contract actually requires bit-exact `raw_model_log_odds` across kernels. The
evidence does not currently require it: the 4 changed paths in the V1→V2 map are
all calibration outputs, and every refusal/threshold/ranking field is unaffected.

## 6. Reproduction

```
OPENBLAS_NUM_THREADS=1 python -m pytest tests/experiments/test_rh04_v2_reference.py \
    -q -W error -k deterministic_upstream
```

Kernel sweep:

```
for k in "" Sandybridge Prescott Nehalem; do
  OPENBLAS_CORETYPE=$k OPENBLAS_NUM_THREADS=1 \
    python -m pytest tests/experiments/test_rh04_v2_reference.py \
    -q -W error -k deterministic_upstream
done
```
