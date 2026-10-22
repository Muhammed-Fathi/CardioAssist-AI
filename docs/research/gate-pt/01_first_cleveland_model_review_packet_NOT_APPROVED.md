# Gate PT — First Real CAD Experiment: One-Decision Review Packet

**Proposal:** CAI-T1-CLEVELAND-PILOT-v0.1
**Status:** **PROPOSED — NOT APPROVED — NOT FROZEN — NO REAL MODEL TRAINING AUTHORIZED**
**Prepared:** 2026-10-23
**Single decision requested:** Approve (or decline/amend) a *bounded source-specific model-development experiment*, not every future dataset, pooled-training plan, wearable, clinician UI or clinical application.

> **This is a decision document, not a permission token.** Gate PT P-3 requires *actual supervisor sign-off* under [docs/DECISIONS.md](../../DECISIONS.md). Human maintainer review/merge of a documentation PR is **not** supervisor approval. D-046 allows read-only local data audits only. D-046-EP is not approved. The original patient-row files remain locally protected, ignored and untransmitted. Do not run fitted models before the needed signed approvals exist.

## 1. Decision recommended by research team

**GO for protocol review of ONE development cohort:** **UCI-45 processed Cleveland**, 303 source records; exact local DA-A2 audit reports 164 original target-0 and 139 original target-positive (1–4), and 303/303 joint observed values for a deliberately small resting input panel. These are **local aggregate findings**, not fitted-model measurements, proof of patient independence or guarantees of adequacy.

**Target:** Source-specific concurrent CAD *presence* (`num=0` versus `num in {1,2,3,4}`) in the historical angiography-referred cohort, NOT 30-day CAD risk, future events, angiographic severity or population prevalence. Historical UCI source speaks of >50% stenosis for source-positive labels; exactly-50% boundary equivalence to UCI-412 (>=50%) remains **unresolved**, but this **does not prevent a SOURCE-SPECIFIC Cleveland evaluation**. It **does** prohibit pooled target harmonization, unqualified cross-dataset comparison and any claim of a universal CAD label.

**Candidate predictors fixed for this first protocol:** `age, sex, cp, trestbps, restecg`. These were chosen for source availability and a possible pre-angiography clinical workflow, **not by seeing association with outcomes**. A historical dataset may not verify that every value was recorded *before* coronary angiography; intended-use timing must be signed off, and clinical deployment claims remain prohibited if that is unverified. Target `num` is **a LABEL only**, never a predictor. Exclude `ca`, `thal`, `Cath`, stenosis/vessel variables, patient IDs, site fields, wearables and any possible post-outcome information.

**Proposed operational claim:** *retrospective benchmark model development with an internal discrimination and calibration assessment*, **not** a medically validated CAD diagnostic product. If timing or sample-size review fails, mark **NO-GO FOR CLINICAL MODEL CLAIM**; a different study question needs its own amendment.

**No routine extra audit required before this narrow protocol review.** Unresolved Swiss/VA zero cholesterol, Hungary coding, and UCI-412/411 harmonization are distinct future decisions. Do not gate the Cleveland-only benchmark behind scientifically unrelated multi-site questions.

## 2. Explicit statistical feasibility check (NOT a completed sample-size justification)

Original five source fields do **not** imply five fitted regression parameters:

| Source predictor | Proposed encoding | Slope coefficients (full rank, reference-level coding) |
|---|---|---:|
| `age` | 1 continuous | 1 |
| `sex` | 2 levels, reference-coded | 1 |
| `cp` | 4 nominal levels, reference-coded | 3 |
| `trestbps` | 1 continuous | 1 |
| `restecg` | 3 nominal levels, reference-coded | 2 |
| **TOTAL (excluding intercept)** | | **8** |

At reported n=303, 139 positive and 164 negative, the nominal event-per-slope count is 139/8≈17.4 and nonevent-per-slope count is 164/8≈20.5. **These are descriptive planning ratios only, not validation of adequate sample size**, since effect sizes, expected (R^2), anticipated shrinkage, class-conditioned distributions, missingness, optimism and desired precision matter. Ridge/penalized LR may allow more stable fitting but does not manufacture extra independent samples. **Required before authorization:** complete a Riley-style binary prediction model sample-size/overfitting calculation under stated assumptions and record whether the selected complexity and 303 source samples are supportable. If expected fit cannot be defensibly estimated, show explicit sensitivity scenarios, report residual uncertainty and use exploratory—not clinical or confirmatory—claims.

**Engineering discrepancy to resolve BEFORE actual model fitting:** The merged M2b.2 synthetic preprocessor uses *full* one-hot coding and mandatory missing-reason indicators for every field. That produces a different number of model columns and presumes reasons that are **not recorded in UCI-45 processed files**. It is a **software prototype, not a frozen real-data pipeline** and must NEVER be used by relabeling real source records `synthetic: true`. A future real-data pipeline needs its own approved, privacy-safe local adapter, training-fold-only fit, reference coding or explicit regularized parameterization, and an honest treatment of unobserved missingness reasons. Do not carry arbitrary synthetic missing-reason indicators into the research model: they can become site/documentation proxies.

## 3. One bounded candidate-model experiment (design choices subject to sign-off)

| Property | Pre-registration proposal |
|---|---|
| Dataset | Official UCI-45 **processed Cleveland only**, source- and hash-verified under separately signed P-3 training authorization; no raw Cleveland (quarantined) |
| Label | Preserve original source `num`; map 0→0 and 1/2/3/4→1 **only in a derived, reversible, versioned working view** after approval |
| Predictors | The five declared source fields; categoricals treated nominal, no `ca` or `thal` |
| Baselines | Training-fold prevalence dummy; L2-penalized logistic regression as primary comparator |
| Nonlinear comparator | Constrained Random Forest; **no large AutoML or deep learning sweep** at n=303 |
| Extra candidate | Boosted trees only via a **dated future amendment**, not a post-hoc choice after examining results |
| Resampling | Proposed repeated nested stratified **outer 5 × inner 5, four fixed pre-registered repeat seeds**; verify class counts/adequacy first |
| Preprocessing | For each fold, numeric imputation/scale and categorical handling learned from **training fold only**, then fixed on held-out fold; prevent imputing/encoding on full cohort before splits |
| Hyperparameters | Freeze exact finite model search spaces and iteration budget in the signed protocol; no tuning on outer folds and no choosing based on future external cohorts |
| Metrics | **Primary internal nested-CV AUROC**; also AUPRC with source prevalence, sensitivity/specificity at a pre-registered non-clinical operating point, Brier and calibration estimates **only where estimable**; report accuracy for completeness, never as the sole winner selector |
| Calibration | Strict out-of-sample/cross-fit estimate; do not fit calibrator on the same examples used to evaluate it; uncalibrated scores cannot be advertised as personal probability or “% risk” |
| CIs | Specify statistical procedure that **resamples individuals not repeated CV prediction rows**; report seed/fold variation and uncertainty, label metrics `INTERNAL_DEVELOPMENT_ONLY` |
| Leakage safeguards | Label shuffling/permutation negative control, per-fold preprocessing check, versioned hash guard for training sources, row/identity uncertainty disclosure |
| Model ranking | Compare internal discrimination plus calibration/uncertainty and simplicity; exact tie-break and model-selection logic frozen before runs; report all prespecified models including poor results |
| Execution | Windows local $0 CPU, only authorized source assets in ignored `data/`, no rows/CSV/identifiers/models derived from unapproved personal data sent to GitHub/remote agents |
| Outcome | Reproducible run log with source hash, code commit, protocol hash, seed, per-fold predictions **locally protected**, safe aggregate metrics (with vetted disclosure), model card marking limitations |

**Not an external evaluation:** Hungary/VA/Swiss are held aside; if eligible later, test a model locked beforehand under a **different site-comparability/independence protocol**. UCI-412 is a separate research study; UCI-411 is the *same participants* as 412; Statlog may overlap with Cleveland. **No pooling or external-validation claims** from this pilot.

## 4. Explicit decisions before anyone presses TRAIN

One supervisor meeting or review of this narrow packet should record the following **together**, rather than stopping the team for every technical detail:

| Decision | Our default | Sign-off / revision required |
|---|---|---|
| Target & purpose | source-specific, retrospective current CAD presence; no future time horizon or clinical deployment | Supervisor confirms exact target phrasing and intended population |
| Timing / field eligibility | fixed 5-input resting panel before angiography *as working concept* | Supervisor confirms appropriate retrospective intended-use wording and predictor plausibility/timing uncertainty |
| Sample-size adequacy | 303 source rows / 139 source-positive / 164 source-negative / 8 reference-coded coefficients | Document full justified method/scenarios and NO-GO if unsuitable |
| Models / CV | dummy, penalized LR, constrained RF, finite budget, nested CV | Sign off the **exact seeds, grids and CI estimator** in the final frozen revision (not supplied by this draft) |
| Missingness | preserve originals; planned cohort-specific parsing of `?` markers; train-fold-only imputation | Sign off data coding and abstention/eligibility; do not invent absent missing reasons |
| Ethics/data custody | approved local benchmark source only, no patient rows uploaded, model outputs not clinical diagnoses | Scope-specific real-data training permission, provenance and no-transfer controls |

**Supervisor decision (unfilled):** ☐ APPROVED WITH EXACT ATTACHED FROZEN PROTOCOL VERSION ☐ REVISE ☐ NO-GO

**Scientific supervisor identity/signature:** `NOT PROVIDED / NOT SIGNED`

**Protocol version, SHA-256, timestamp, approved source file hashes, and exact allowed train/evaluation actions:** `NOT FROZEN / NOT AUTHORIZED`

**Maintainer/clinical gate registry:** `P-1 PENDING; P-3 CLOSED`

Even after documentation is merged, these fields remain empty until evidence of real signoff is supplied and checked against the repository decision register. No self-signing or inferred approval.

## 5. Engineering tasks that can proceed NOW and what is gated

**NOW:** prepare a *design-only* plan for local-only model-runner boundaries and dependencies; literature/clinical predictor review; document planned grid/seeds/sample-size method; synthetic tests verifying fold-contained preprocessing and label/feature exclusions. Existing M2b.2 is already merged; do not build redundant synthetic wrappers for their own sake. Contract-intake work is **secondary** until model-training approvals are resolved.

**ONLY AFTER P-3 and named source-training authorization:** implement/freeze approved source-specific local adapter; run real model fit, feature/model comparison, calibration and SHAP; assess robustness; create a paper-ready evidence report. No fake numeric accuracies or unsupported claims.

**Separate, narrower alternative:** `D-046-EP` exploratory-governance path is *only a historical, unapproved proposal*. It cannot be invoked unless its separate amendment, prerequisites and explicit maintainer approval truly occur, and its internal results would remain **not supervisor-approved**, **not clinical evidence** and **not a replacement for P-3**. No such approval is claimed in this document.

## Evidence

- [Original UCI Heart Disease source](https://archive.ics.uci.edu/dataset/45/heart+disease): original 0–4 labels, historical 14-attribute processed Cleveland representation, current public metadata.
- [DA-A2 read-only cohort audit](../gate-da/10_m2a_uci412_uci411_evidence_and_decisions.md): source class counts, raw Cleveland quarantine and original-byte custody, human-attested local aggregates.
- [Joint completeness audit](../gate-da/14_real_joint_availability_and_staged_intake_decision.md): five-field resting availability; joint descriptive counts are NOT fitted-model evidence.
- [Full v0.1 protocol draft](../gate-da/15_ai_model_development_evaluation_protocol_DRAFT.md): candidate models, scientific caveats and multi-site restrictions.
- [TRIPOD+AI, BMJ 2024](https://doi.org/10.1136/bmj-2023-078378): transparent definitions of populations/outcomes/predictor timing, sample-size and missingness reporting.
- [PROBAST+AI, BMJ 2025](https://doi.org/10.1136/bmj-2024-082505): risk of bias/quality/applicability review.
- [Riley et al., BMJ 2020](https://doi.org/10.1136/bmj.m441): prediction-model sample size should not be declared adequate using EPV alone.
