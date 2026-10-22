# CardioAssist — First Internal Exploratory CAD Model Comparison

**Status:** `TEMPLATE_ONLY — NO MODEL RESULTS`  
**MANDATORY banner on every later report:** `INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED`  
**Not medical advice, not clinical validation, not a paper acceptance, not evidence of supervisor signoff.**

## 0. Registration and approvals

| Field | Value |
|---|---|
| Internal protocol ID, repository commit SHA, content hash | **NOT FILLED** |
| D-047 explicit maintainer approval / merge evidence | **NOT FILLED** |
| Source cohort and authorized local source hash (do not publish patient data) | **NOT FILLED** |
| Local signed authorization ID / protected runtime | **NOT FILLED** |
| Execution date, Python/scikit-learn library versions, code SHA | **NOT RUN** |
| P-3 formal supervisor approval | **CLOSED — no supervisor endorsement** |

**STOP:** Do not fill performance figures, fold results or feature rankings without local authorized runs. The report author must confirm no patient rows, per-patient predictions, medical identifiers or models are pasted in an external service.

## 1. Research question and population

- **Target:** historical UCI-45 processed Cleveland `num=0` vs `num=1..4`, source-defined CAD-present grouping, **not** incident disease or 30-day event risk.
- **Cohort feasibility:** locally audited 303 rows / 164 label-0 / 139 label-positive. Confirm against source locally before authorized run, never infer patient-level independence solely from rows.
- **Context/limits:** historic angiography-referred sample; measure timing, generalizability, and selection bias may be uncertain. Do not claim deployed clinical performance.

## 2. Feature and preprocessing definition

**Prespecified primary candidate panel:** `age, sex, cp, trestbps, restecg`. Explicit reference categories, data dictionary, handling of `?`, missingness and any exception must be specified here before fitting. Keep `num` strictly as the response label; ban `ca`, `thal`, catheterization/vessels, site/ID and wearables. Do not reuse synthetic-only provenance flag for source patients.

Record actual parameter count after encoding: **NOT FILLED**. Record Riley-style sample-size sensitivity assumptions and limitations: **NOT FILLED**.

## 3. Candidate models and model selection

| Method | Prespecified configuration | Actual fitted / tested? |
|---|---|---|
| Training-fold prevalence dummy | Baseline, no features | **NO** |
| Penalized logistic regression | L2 / `C={0.1,1,10}` | **NO** |
| Constrained random forest | 200 trees; max_depth 3/5; min_leaf 5/10 | **NO** |
| Nested selection procedure | Source-specific inner-CV model-family/parameter choice | **NO** |
| Label shuffle negative control | Identical safe CV procedure with shuffled labels | **NO** |

No neural net, AutoML or post-hoc new feature panel under the first approved scope.

## 4. Resampling protocol and leakage controls

Document outer 5-fold, inner 5-fold, four frozen seeds, fold-positive/fold-negative counts, **training-only** imputation/encoding/scaling, id-based holdout safeguards to extent available, fixed model selection logic, leakage negative-control behavior and stop rules. If a split cannot be created or expected input-code constraints fail, record **STOP/NO-GO** rather than repairing source observations silently.

## 5. Performance reporting — BLANK until first authorized experiment

**This table is intentionally empty.** Never enter numbers based on a mock, a previous paper, training performance or anticipated accuracy.

| Registered method | Internal AUROC | AUPRC (with prevalence) | Accuracy (secondary) | Sensitivity @0.50 (exploratory) | Specificity @0.50 | Brier / calibration | Status |
|---|---|---|---|---|---|---|---|
| Dummy | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| L2 LR | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| RF | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| Inner-selected procedure | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |

**Repeated-CV caveat:** Four repeat OOF sets share the same individuals; NEVER say `n=1212` independent evaluations or bootstrap the repeated rows naively. Report per-repeat values and honest variation, and only give formal uncertainty intervals if an appropriate estimator was frozen in advance. Calibration may be unestimable or unreliable for this small source sample; record that transparently.

## 6. Scientific quality, robustness and risks

- **Riley-style sample-size:** assumptions, anticipated model fit, shrinkage concern, parameter count, resulting sufficiency/limitations — **NOT ANALYZED**.
- **Negative control:** shuffled-label procedure, actual result, consistency with chance expectations — **NOT RUN**.
- **Potential site/documentation proxies:** missing reasons absent in source; no synthetic-only reason indicator import — **NOT ASSESSED**.
- **TRIPOD+AI reporting readiness:** **NOT ASSESSED**.
- **PROBAST+AI bias/applicability:** sample selection, predictors, outcome/timing, analysis, documentation and limits — **NOT ASSESSED**.
- **Reproducibility:** data hash, code versions, folds/seeds and exact freeze evidence — **NOT VERIFIED**.

## 7. Model choice or NO-GO

**Internal exploratory conclusion:** **NOT DETERMINED**. Record whether any model appears promising, weak or uncertain relative to dummy, with caveats on data size and site shift. This is *not* approval to deploy or select a threshold for medical care.

## 8. Next data studies (separately reviewed scope)

A future UCI-412 experiment must keep its own source-specific label/predictor dictionary; UCI-411 is an extension of the **same** 303 records and never independently validates 412. Hungary, VA, Switzerland require eligibility/target harmonization/quality and possible identity overlap checks before use. **Do not pool or declare external validation in this first report**.

## 9. Supervisor review — only after internal report is ready

Date sent / clinician reviewer / documented comments / reanalysis requested / independently approved formal study: **NONE**. Never backdate or prefill the sign-off.
