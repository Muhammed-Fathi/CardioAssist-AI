# RH-04 V2 acceptance ledger — v4, final acceptance execution

**Document ID:** CAI-RH04-V2-LEDGER-v4
**Supersedes:** v3 (`RH04_V2_ACCEPTANCE_LEDGER_RECONCILED_2026_11_21.md`)
**Status:** **unratified.** No gate below is closed by this file. Issue #132 stays
**OPEN**. Zero of ten closed.

Acceptance ID meanings remain the original `docs/rh04-issue132-acceptance-decision.md`
§7 meanings. No ID is reassigned. This file records what changed since v3.

---

## 1. Change since v3

| gate | v3 | v4 | what changed |
|---|---|---|---|
| V2-01 | OPEN | **OPEN** | ratification wording prepared (§ owner packet); still owner-only |
| V2-02 | PARTIAL | **CORRECTED IN v5 — see §1a** | the earlier v4 row claimed the clause was evidenced from 100 logistic-regression fits alone; that omitted the bounded OOF calibration optimizer, which the clause explicitly includes. Corrected below. |
| V2-03 | PARTIAL | **EVIDENCED** | complete 29-case leaf-level mapping, 479 leaves, 0 numeric deltas, discrimination-proofed |
| V2-04 | NOT MET | **PARTIALLY EVIDENCED** | hosted green on 3.11 and 3.12; matrix (3 classes × 2 versions + Windows) still incomplete |
| V2-05 | PROPOSED | **PATCH PREPARED** | dual-run gate written and stage-independence tested; cannot be pushed |
| V2-06 | PARTIAL | **V2 HALF DONE** | V2-facing semantics complete; production wording still out of scope |
| V2-07 | PARTIAL | **CORRECTED IN v5 — see §1a** | the earlier v4 claim rested on a test that asserted the wrong behaviour (over-criterion residual = non-failure). Corrected below and re-mutation-verified. |
| V2-08 | SATISFIED | **SATISFIED** | unchanged; no tolerance added |
| V2-09 | LARGELY MET | **LARGELY MET** | semantics document adds non-claims |
| V2-10 | DEMONSTRATED | **DEMONSTRATED** | re-executed on final SHA `8849207`, gate included |

**Closed: 0 of 10.** "EVIDENCED" means the evidence exists and is measured. It does
not mean the gate is satisfied, because satisfaction is the owner's determination.

---

## 2. Per-gate record

### V2-01 — Owner ratification — **OPEN**
Ratification wording prepared in `RH04_V2_DECISION_REGISTER_WORDING_2026_11_24.md`,
including a proposed `docs/DECISIONS.md` entry. **That entry does not exist and this
work did not create one.** Three separable acts are proposed (architecture,
evidence acceptance, register entry), in that order.

### 1a. Correction to v4: V2-02 and V2-07 were over-claimed

**This is a correction of this ledger's own previous claim, not a new finding about
the code.** The v4 rows above stated that V2-02 and V2-07 were EVIDENCED. Both claims
were wrong, for different reasons, and both are retracted here.

**V2-02 was overstated.** The clause covers *both* fitted components: the logistic
regression **and** the bounded out-of-fold calibration optimizer. v4 measured 100
logistic-regression fits and reported the clause evidenced. The calibration optimizer
is a separate SciPy L-BFGS-B problem with its own bounds `[(-15, 15), (0.01, 15)]`,
its own stopping rules, and its own `OptimizeResult` — none of which was observed.
Observing one component cannot evidence a clause that names two.

Round 16 observes the calibration optimizer at the seam it is actually called
through (the `minimize` binding inside `ai/calibration.py`, not `scipy.optimize`,
because the import is by value):

| quantity | measured |
|---|---|
| calibration optimizations observed | **14** (7 on `da_a1_basic_clinical_v1`, 7 on `da_a2_resting_v1`) |
| solver | `scipy_lbfgsb`, bounded |
| termination | 14 of 14 `CONVERGED_PROJECTED_GRADIENT`, scipy `status = 0` |
| criterion | box-projected gradient norm ≤ the solver's declared `tol` (`1e-5`) |
| projected residual | min `4.852e-09`, max `7.996e-06` |
| iterations | 5 to 11; **0** at the iteration cap |
| independent evaluation | the calibrator's own objective re-derived from source and evaluated outside scipy |

**Two defects were found while doing this, and both are the kind that produce
plausible-looking evidence:**

1. *The observer could not see the second route.* `ai/calibration.py` does
   `from scipy.optimize import minimize`, so patching `scipy.optimize.minimize`
   works only for a module that resolves the attribute at call time. The first route
   in a process appeared to be observed and the second silently captured nothing. The
   observer now patches the binding the calibrator actually calls.
2. *The status-code table was wrong.* An iteration-capped L-BFGS-B fit returns
   `status = 1` with `"STOP: TOTAL NO. OF ITERATIONS REACHED LIMIT"` on scipy
   1.15.3, while the widely-quoted table assigns 1 to "function change converged". A
   classifier keyed on the number alone would have **passed a capped fit as
   converged**. The termination reason is now derived from the solver's own message
   and cross-checked against `success`; only the two recognised convergence tests are
   accepted and everything else is a failure.

**Box projection is load-bearing, not cosmetic.** One real `da_a2_resting_v1` fit
terminates on the lower slope bound `b = 0.01` with `raw |g| = 1.271e-02` but
`projected |g| = 4.852e-09`. Judging by the raw gradient would have failed a fit that
converged correctly in every feasible direction.

**V2-07 was overstated, and one of its tests asserted the wrong thing.** The
round-15 test `test_v2_07_failed_fit_is_a_failure_not_diagnostic_divergence` contained
this assertion:

```
# A genuine divergence below the cap is reported, and is NOT a failure.
assert result["classification"] == "DIAGNOSTIC_DIVERGENCE"
assert result["is_failure"] is False
```

for a fit whose residual exceeded its declared criterion. That encodes "failing your
own acceptance criterion is a reportable variation", which is the opposite of the
contract. A test that asserts the defect cannot detect it, so the mutation evidence
quoted in v4 was validating the wrong behaviour. The classification is corrected, the
test is corrected to assert `TRAINING_FAILED` / `is_failure=True`, and the corrected
test was re-verified against the reintroduced defect.

**The classification now distinguishes three cases**, which the earlier version
conflated:

| case | classification | failure |
|---|---|---|
| met its own declared criterion; differs numerically from another environment | `DIAGNOSTIC_DIVERGENCE` | no |
| did not meet its own declared criterion | `TRAINING_FAILED` | **yes** |
| required solver evidence missing, non-finite or malformed | `EVIDENCE_MISSING` / `OUTPUT_INVALID` | **yes** |

A missing tolerance is **never** replaced by a default. v4's classifier fell back to
a module-level `LANE_A_SOLVER_DEFAULT_TOLERANCE` when `solver_settings.tol` was
absent, so a fit that declared no criterion could be reported as converged against a
number it never declared. That fallback is removed and its absence is a failure.

**What V2-02 still is not.** Evidence is not satisfaction. Nothing here closes the
gate, and the calibration evidence is still Linux-local: it was measured on one
machine and one dispatch class, not on Windows and not across the matrix. The scope
claim remains logistic regression plus its calibration map; the random forest is a
different estimator with no gradient-based convergence test and is not covered.

### 1b. Correction to the round-16 evidence wording: independence was overstated

Round 16 described the calibration residual as "independently evaluated". That was
not accurate. The residual was computed by re-evaluating **the calibrator's own
analytic Jacobian** at the fitted point. Re-evaluating a solver's own gradient
functions confirms only that the function returns what it returns: it inherits the
same algebra, the same binary64 rounding and the same sign conventions, so an error
shared with the solver would be invisible.

The disagreement was one of **claim**, not of classification. The classification in
§1a stands, and so do the measured termination statuses, iteration counts and
projected residuals.

The evidence now records two distinguishable forms:

| form | what it is | independent |
|---|---|---|
| `solver_jacobian` | the calibrator's analytic gradient at the fitted point — what the solver's stationarity test actually used | **no**, and the record says so with the reason |
| `independent_decimal_finite_difference` | the same objective re-derived from source and differentiated by symmetric central differences in 50-digit decimal arithmetic, over the **full** in-memory OOF vector | **yes** — different algebra, different arithmetic, different code path |

Both forms are reported for all 14 observed fits and agree to machine precision.
A negative test perturbs a label and requires the independent form to move, so the
cross-check can fail rather than merely accompany the analytic value.

**Deliberately not claimed:** this is not a second solver, not an independent model
fit and not evidence about the random forest. It is a second *evaluation* of one
already-fitted objective.

### V2-02 — Solver and criterion declaration — **CORRECTED; EVIDENCE COMPLETE FOR THE REGISTERED LINUX PATH**
The registered path was **observed**, not declared from documentation:

| quantity | measured |
|---|---|
| routes observed | `da_a1_basic_clinical_v1` (62 fits), `da_a2_resting_v1` (38 fits) |
| declared solver | `lbfgs`, derived from each route's own `ResearchTrainingConfig` and cross-checked against the solver actually used |
| criterion | the solver's own stopping rule, `max_i \|g_i\| <= tol`, `tol = 1e-4` as carried by the fitted estimator |
| independent evaluation | decimal arithmetic, separate implementation, no BLAS/LAPACK/libm |
| residuals | min `1.527e-06`, median `5.825e-05`, max `9.997e-05` |
| fits at iteration cap | **0 of 100** |
| classification | 100 CONVERGED, 0 diverged, 0 failed, 0 missing, 0 invalid |

**A correction recorded rather than hidden.** This round first proposed `1e-10` for
Lane A. Measurement disproved it — no observed fit reached `1e-10`, because `lbfgs`
with `tol=1e-4` stops near `1e-5`. An `1e-10` gate would have failed all 100 genuine
fits. The criterion was changed to the solver's own tolerance *after* measuring.

**Two wrong assumptions were caught by the cross-check**, not by luck: the resting
route does **not** use `CLEVELAND_D047_FROZEN_V1` (all 38 of its fits are `lbfgs`),
and `Uci412ResearchModelConfig` has no `execution_profile` attribute. Both produced a
refusal instead of plausible-looking evidence, which is the behaviour the design
exists to produce.

### V2-03 — New pack, digest, provenance, complete delta mapping — **EVIDENCED**
Complete leaf-level mapping across all 29 cases:

| quantity | measured |
|---|---|
| cases mapped | 29 of 29 |
| leaves compared | **479** |
| `IDENTICAL` (numeric, equal) | 50 |
| `STRUCTURAL_IDENTITY` (strings, bools, nulls) | 429 |
| `NUMERIC_DELTA` | **0** |
| `TYPE_CHANGE` / `MISSING_IN_V2` / `EXTRA_IN_V2` | 0 / 0 / 0 |
| discrimination proof | a `1e-15`-relative perturbation **is** detected at the exact path |

The mapping refuses to present a partial result: it raises if the two sides do not
cover the same 29 cases. Lane B digest unchanged at `891d9e3b…`.

### V2-04 — Cross-environment matrix — **PARTIALLY EVIDENCED**
Hosted CI now has a **fully green** run: 2098 passed / 2 skipped on both Python 3.11
and 3.12, 396 UCI-412 tests passing, diagnostic green. That is strong evidence and it
is **not** the gate: the matrix requires ≥3 resident dispatch classes per Linux Python
version plus native Windows, and only one class per version has been measured there.

### V2-05 — Dual-run window — **PATCH PREPARED, NOT APPLIED**
`rh04-dual-run-gate.yml` implements four stages (V1 mandatory, Lane A classified,
Lane B mandatory, security mandatory), each with `if: always()` and its own recorded
exit code, and a final gate step that fails if any mandatory stage failed **or failed
to report**. Stage independence was tested locally: a failing Lane A left Lane B and
the others reporting, and the gate failed.

Cannot be pushed: the integration has no `workflows` scope. Delivered as a patch for
the owner.

### V2-06 — Semantics re-statement — **V2 HALF DONE**
`RH04_V2_SEMANTICS_CALIBRATION_SCALE_MODELCARD_2026_11_24.md` fixes the
calibrated-log-odds-versus-probability distinction, names the actual fitted criterion
with measured residuals, and lists research-only limitations.
**Production `calibration.json`, manifest and model-card wording remain untouched** —
that is an activation change needing its own authorization.

### V2-07 — Required negative tests — **EVIDENCED**
Added and **mutation-verified** — each test was run against a deliberately broken
implementation to prove it can fail:

| test | mutation used | caught |
|---|---|---|
| missing convergence evidence → failure | missing keys default to `CONVERGED` | **yes** |
| non-evaluable fit refused | non-finite parameter allowed | **yes** |
| failed fit ≠ diagnostic divergence | cap-reached treated as divergence | **yes** |
| registered fits satisfy their own rule | — (positive evidence test) | n/a |
| no raw design matrix leaves the observer | — (payload-shape walk) | n/a |

### V2-08 — Security parity, no new tolerance — **SATISFIED IN SUBSTANCE**
Canonical comparator byte-identical to `main`. No numeric tolerance was added
anywhere in this round; Lane B remains exact. The Lane A criterion is the solver's own
declared rule, not a new acceptance tolerance.

### V2-09 — Explicit non-claims — **LARGELY MET**
The semantics document adds: synthetic-only, in-sample development calibration, no
clinical validity, no model equivalence, no SHAP/LIME reproducibility, Platt scaling
is a choice not a finding, threshold exploratory and unvalidated.

### V2-10 — Single-revert rollback — **DEMONSTRATED on the final SHA**
Re-executed on `8849207` after the V2 pack, comparator, admission corrections **and**
the prepared dual-run gate were all present. Squash `66ad0600`, single `git revert`:
reverted tree `3106bece…` == `main` tree, all V2 modules and the workflow-patch
directory gone, `.github/workflows/` identical to `main`, and the V1 suite
**executed** at **457 passed in 35.57s**.

---

## 3. Gate summary

| Gate | Status |
|---|---|
| V2-01 | OPEN — owner only |
| V2-02 | EVIDENCE COMPLETE for the registered Linux path — not the full matrix |
| V2-03 | EVIDENCED |
| V2-04 | PARTIALLY EVIDENCED — matrix incomplete |
| V2-05 | PATCH PREPARED (round 16 rebuild) — not applied |
| V2-06 | V2 HALF DONE — production half out of scope |
| V2-07 | EVIDENCE CORRECTED and re-mutation-verified — not yet reviewed |
| V2-08 | SATISFIED IN SUBSTANCE |
| V2-09 | LARGELY MET |
| V2-10 | DEMONSTRATED on final SHA `8849207` |

**Closed: 0 of 10.**

---

## 4. Execution-only blockers

| # | blocker | who |
|---|---|---|
| 1 | `workflows` scope missing — CI patch cannot be pushed | owner |
| 2 | job logs unreachable from this sandbox | owner / reviewer |
| 3 | Linux Python 3.12 Lane B replay outside CI | needs a 3.12 interpreter |
| 4 | native Windows verification | needs a Windows host; script provided |
| 5 | ≥3 resident dispatch classes per version | needs hosts / dispatch pins |
| 6 | V2-01 ratification | owner |
| 7 | V2-04 scope decision | owner |

None of these is a research question. They are execution and authorization.

---

## 5. Explicit non-claims

No clinical validity, no model equivalence, no patient readiness, no SHAP/LIME
reproducibility, no real-data fitting, no production activation. Lane B is not
bit-identical to scikit-learn and its portability is a measured property, not a
deduction from being untrained. Lane A is host-dependent and is reported as such.
