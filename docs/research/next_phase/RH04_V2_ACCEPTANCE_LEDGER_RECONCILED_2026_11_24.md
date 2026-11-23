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
| V2-02 | PARTIAL | **EVIDENCED** | 100 of 100 registered-path fits measured against the solver's own criterion |
| V2-03 | PARTIAL | **EVIDENCED** | complete 29-case leaf-level mapping, 479 leaves, 0 numeric deltas, discrimination-proofed |
| V2-04 | NOT MET | **PARTIALLY EVIDENCED** | hosted green on 3.11 and 3.12; matrix (3 classes × 2 versions + Windows) still incomplete |
| V2-05 | PROPOSED | **PATCH PREPARED** | dual-run gate written and stage-independence tested; cannot be pushed |
| V2-06 | PARTIAL | **V2 HALF DONE** | V2-facing semantics complete; production wording still out of scope |
| V2-07 | PARTIAL | **EVIDENCED** | missing/non-evaluable/failed-fit negatives added and mutation-verified |
| V2-08 | SATISFIED | **SATISFIED** | unchanged; no tolerance added |
| V2-09 | LARGELY MET | **LARGELY MET** | semantics document adds non-claims |
| V2-10 | DEMONSTRATED | **DEMONSTRATED** | re-run required on the final frozen SHA |

**Closed: 0 of 10.** "EVIDENCED" means the evidence exists and is measured. It does
not mean the gate is satisfied, because satisfaction is the owner's determination.

---

## 2. Per-gate record

### V2-01 — Owner ratification — **OPEN**
Ratification wording prepared in `RH04_V2_DECISION_REGISTER_WORDING_2026_11_24.md`,
including a proposed `docs/DECISIONS.md` entry. **That entry does not exist and this
work did not create one.** Three separable acts are proposed (architecture,
evidence acceptance, register entry), in that order.

### V2-02 — Solver and criterion declaration — **EVIDENCED**
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

### V2-10 — Single-revert rollback — **DEMONSTRATED on the prior SHA**
Previously demonstrated on `b276f27` (tree `3106bece…`, 0 V2 files, 457 V1 passed). It
**must be re-run on the final frozen SHA**, and it is not complete from a rollback
that predates the dual-run gate.

---

## 3. Gate summary

| Gate | Status |
|---|---|
| V2-01 | OPEN — owner only |
| V2-02 | EVIDENCED |
| V2-03 | EVIDENCED |
| V2-04 | PARTIALLY EVIDENCED — matrix incomplete |
| V2-05 | PATCH PREPARED — not applied |
| V2-06 | V2 HALF DONE — production half out of scope |
| V2-07 | EVIDENCED |
| V2-08 | SATISFIED IN SUBSTANCE |
| V2-09 | LARGELY MET |
| V2-10 | DEMONSTRATED — re-run required on final SHA |

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
