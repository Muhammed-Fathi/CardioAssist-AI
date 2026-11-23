# RH-04 V2 — V2-06 semantics: calibration, scale, model card and manifest

**Document ID:** CAI-RH04-V2-SEMANTICS-v1
**Status:** documentation and metadata correction only. **No behaviour change, no
production activation, no change to any frozen V1 artifact.**
**Scope:** research documentation. The wording below either restates what the code
already does or corrects a description that was wrong.

---

## 0. What this clause is for

V2-06 is a **wording** gate, and it exists because an earlier draft described the
fitted quantity as "L-BFGS-B output". That is a statement about a solver, not about
what the number *means*, and it invited two errors: reading the calibrated score as
a probability, and reading the fitted criterion as the production one.

Nothing here changes a value, a threshold, a tolerance or an artifact. Both source
files named below are unchanged by this round, and the frozen V1 pack is byte-identical
to `main`.

---

## 1. Calibrated log-odds versus probability

These are different quantities on different scales, and the difference is not
cosmetic.

**Raw model log-odds** — ``raw_model_log_odds``. The fitted linear predictor
``w·x + b`` from the route's model, before calibration. Unbounded in both
directions; it is not a probability and cannot be compared to a threshold such as
0.5 without a transform.

**Calibrated log-odds** — ``calibrated_log_odds``. The raw log-odds passed through
the fitted Platt-type map

```
eta_cal = intercept + slope * eta_raw
```

This is still a log-odds, still unbounded, and **still not a probability**. It is the
scale on which the calibration was fitted and on which Shapley linearity is
preserved (`ai/calibration.py:632`).

**Calibrated research score** — ``calibrated_research_score``. The probability-scale
image of the calibrated log-odds:

```
calibrated_research_score = expit(intercept + slope * raw_log_odds)
```

This is a probability **of the model's own label on a synthetic development
cohort**. It is a *research score*. It is **not** a clinical probability, not a
patient risk, and it carries no clinical claim. The response field
``clinical_probability_claim`` is `false` for exactly this reason, and
``exploratory_threshold_clinically_validated`` is `false` alongside it.

### The mistake this section exists to prevent

Describing ``calibrated_log_odds`` as "the probability" is wrong by an expit
transform, and at the margins the error is large: a log-odds of 2.0 is a probability
of 0.88, not 2.0; a log-odds of −2.0 is 0.12, not −2.0. A reader who treats the
log-odds as a probability will also misapply the 0.5 exploratory threshold, because
``log_odds > 0.5`` and ``probability > 0.5`` select different sets of cases wherever
the log-odds falls between 0 and 0.5.

The production facade already states this correctly
(`ai/research_facade.py:632`):

> ``calibrated_research_score = expit(intercept + slope * raw_log_odds)`` on the
> calibrated log-odds scale fitted on development out-of-fold predictions;
> ``raw_model_score`` is the uncalibrated model probability.

No change is required to that text. It is reproduced here so the V2 documentation
and the shipped declaration cannot drift apart.

---

## 2. The actual fitted criterion

There are two criteria in this workstream and they must not be conflated.

### 2.1 Lane A — the registered producer

Observed from the registered path, not declared from a datasheet:

| quantity | value |
|---|---|
| estimator | `LogisticRegression(penalty="l2", solver="lbfgs", class_weight=None)` |
| declared stopping rule | stop when `max_i \|g_i\| <= tol` |
| `tol` as carried by the fitted estimator | **1e-4** (scikit-learn default) |
| observed iterations (route `da_a1`) | 6–30 across 62 fits |
| observed iterations (route `da_a2`) | 7–13 across 38 fits |
| fits that reached the iteration cap | **0 of 100** |
| independent residual, min / median / max | `1.527e-06` / `5.825e-05` / `9.997e-05` |
| all residuals within the solver's own tolerance | **yes, 100 of 100** |

The criterion is therefore **the solver's own declared stopping rule, verified by an
independent implementation**. It is not a threshold invented for the evidence.

**A correction recorded rather than hidden.** This round initially proposed `1e-10`
for Lane A, on the reasoning that a converged fit "should" sit far below the solver's
tolerance. Measurement disproved it: no observed fit reached `1e-10`, because
`lbfgs` with `tol=1e-4` legitimately stops at ~1e-5. An `1e-10` gate would have
failed all 100 genuine fits. The criterion was changed to the solver's own tolerance
**after** measuring, and the earlier value is recorded here so the change is visible
rather than silently retrofitted.

### 2.2 Lane B — the portable reference

Lane B does not fit anything, so it has no convergence criterion to declare. Its
acceptance rule is exact equality against the fixed reference digest

```
891d9e3b2a332c6efc251d97fee25ed46a627ed25b2a089594057b4c9896cdc8
```

with **no numeric tolerance**. Stating a "criterion" for Lane B would be a category
error; the honest statement is that Lane B is either byte-exact or refused.

### 2.3 The decimal reference fit (not the registered path)

`rh04_v2_model_fit.py` and `rh04_v2_reference_fit.py` implement decimal-arithmetic
reference fits used as *evidence*, with declared gradient tolerances (`1e-24`) and
box-KKT residuals (`1e-16`, measured floor `1e-18`). **These are not the production
solver and are not Lane A.** Presenting their tolerances as the fitted criterion of
the registered model would be the "isolated oracle as producer provenance" error
this workstream has already had to correct once.

---

## 3. Scale declaration

The `scale_declaration` field states, per score kind:

* **calibrated kind** — the score is `expit(intercept + slope * raw_log_odds)` on the
  calibrated log-odds scale, fitted on development out-of-fold predictions; the raw
  score is the uncalibrated model probability;
* **uncalibrated kind** — only the uncalibrated probability is reported, because the
  artifact provides no calibration.

The declaration is a property of the response, not of the model card alone, so a
consumer reading one response cannot mistake which scale they hold.

---

## 4. Model card wording

Corrections applied to the V2-facing description (the RH-07 source-bound drafts in
`docs/research/next_phase/RH07_*` are **not modified** by this round):

1. **"L-BFGS-B output" is withdrawn** as a description of the reported quantity.
   The reported quantity is a calibrated log-odds and, on the probability scale, a
   research score. The solver that produced the raw coefficients is `lbfgs`; naming
   it describes how the number was computed, not what it means.
2. **"Probability" is qualified everywhere it appears.** It is a probability of the
   model's own label on a synthetic development cohort, explicitly not a patient
   risk. The `clinical_probability_claim: false` field is the machine-readable form
   of that qualification.
3. **The exploratory threshold is declared unvalidated.** `0.5` is an exploratory
   cut on a synthetic cohort; `exploratory_threshold_clinically_validated` is `false`
   and no clinical decision may consume it.
4. **The fitted criterion is named as the solver's stopping rule**, with the
   measured residual range, rather than described as "converged".

### What is explicitly out of scope

* Production `calibration.json`, the production manifest text and `DECISIONS.md` are
  **not edited** by this round. Editing shipped production wording is an activation
  change and needs its own authorization.
* RH-07 model cards are **not** rewritten here; they belong to a different
  workstream and have their own gate.
* No artifact byte changes, so the Lane B digest is untouched.

---

## 5. Research-only limitations

Stated plainly, because the calibration vocabulary is where over-claiming usually
starts:

* **Synthetic only.** Every cohort is synthetic. `evidence_level` is
  `SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE`.
* **Calibration is in-sample to the development cohort.** The map is fitted on
  development out-of-fold predictions; it is not validated on any external
  population, and no external calibration evidence exists.
* **No clinical validity.** No discrimination, calibration-in-the-large, or decision
  curve has been estimated on real patients, and none is claimed.
* **No model equivalence.** Lane B is not bit-identical to scikit-learn; it is exact
  against its own fixed reference.
* **No SHAP/LIME reproducibility claim.** Fixed coefficients do not imply it.
* **Platt scaling is a choice, not a finding.** The slope/intercept map is the
  registered method; other calibrators were not evaluated.
* **The threshold is exploratory.** 0.5 was not tuned on real outcomes and is not
  clinically validated.

---

## 6. What V2-06 does not close

This document completes the **V2-facing** semantics correction. It does **not**
close V2-06, because the clause also reaches production wording, and production
wording is out of scope:

| item | state |
|---|---|
| V2-facing calibrated-log-odds vs probability distinction | **done** (this document) |
| V2-facing fitted-criterion statement, with measured residuals | **done** |
| explicit research-only limitations | **done** |
| production `calibration.json` / manifest / model-card wording | **not done — activation change, needs authorization** |
| RH-07 model cards | **not done — separate workstream** |

V2-06 therefore remains open with its production half explicitly deferred, rather
than being reported as satisfied on the half that was convenient.
