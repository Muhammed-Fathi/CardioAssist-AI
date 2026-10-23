# Gate PT — First Real CAD Experiment: One-Decision Review Packet

**Proposal:** CAI-T1-CLEVELAND-PILOT-v0.1

> **Scope update (2026-10-23):** This document is the **formal Gate PT/supervisor decision packet**, not necessarily the first operational prerequisite for a *separately ratified* internal exploratory benchmark. See [proposed D-047 / D-046-EP protocol](02_d047_internal_exploratory_cleveland_PROTOCOL_PROPOSED.md). If approved by the named human maintainer in a separate governance PR, D-047 permits strictly labelled internal experiments while formal P-3 remains CLOSED. This note **does not itself authorize fitting**. *(v0.2 status note, 2026-10-23: that separate route was subsequently ratified and **one Cleveland-only internal exploratory run has since been executed**, recorded in [document 04](04_d047_first_internal_results_REVIEW_DRAFT.md). It did not approve this packet, did not close P-3, and is not development adequacy — see [§6.A](#6a-executive-summary).)*
**Status:** **PROPOSED — NOT APPROVED — NOT FROZEN — NO REAL MODEL TRAINING AUTHORIZED**
**Prepared:** 2026-10-23 (v0.1)
**Revision:** **v0.2, 2026-10-23** — §§1–5 are preserved unchanged as the v0.1 proposal; a dated post-M2e.1/M2e.2 addendum is appended as [§6](#6-post-m2e1m2e2-supervisor-decision-addendum-2026-10-23). Base commit for this revision: `cce8340ac04092f0fedc39d55c9bbca6cda6f05a`.
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

> **Update (v0.2, 2026-10-23) — this requirement is now documented but NOT decided.** The calculation exists as documentation in [M2e.1 (document 05)](05_m2e1_sample_size_research_ADEQUACY_REVIEW_DRAFT.md): at n = 303 and φ = 139/303, the published outcome-proportion criterion requires **382** and the additional approximate MAPE criterion requires **459** at p = 8, so the published criteria are not satisfiable at 303 for any anticipated R². The review's adequacy status remains **`NOT ASSESSED — PENDING HUMAN REVIEW`**; it is a conditional methodological result, **not** a human sample-size decision and **not** a GO. Nothing in §2 above is altered by that update; see [§6.C](#6c-scientific-decision-table--blank-human-sign-off) (PT-DEC-4) for the decision that remains open.

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

### Default numerical plan for the signed revision (PROPOSED, not frozen)

To prevent endless post-hoc tuning, the research team preselects these as its **default candidate settings**; a single Gate PT review can approve them or amend them *before any result is seen*:

- Repeated stratified **5 outer folds × 5 inner folds, 4 independent repetitions**; candidate split seeds `20261023, 20261024, 20261025, 20261026` (fixed in advance). Use deterministic model seeds keyed by fold. A subject must never appear in training and outer evaluation within the same fold. Source patient identity is not verified beyond the available rows, so report residual overlap risk.
- Candidate **L2 penalized logistic regression**: `C ∈ {0.1, 1, 10}`, `class_weight=None`, `solver=liblinear`, sufficient deterministic convergence tolerance/maximum iterations documented in final config.
- Candidate **Random Forest**: `n_estimators=200`, `max_depth ∈ {3,5}`, `min_samples_leaf ∈ {5,10}`, `max_features=sqrt` with fixed random state. This limits capacity relative to the small cohort.
- Prevalence dummy is fitted **only on inner/outer training portions** and reported as a reference, never allowed to learn from evaluation labels. Numerics: median impute + scale for LR, both fitted in-fold. Nominal `cp,restecg,sex`: reference-category one-hot fit in training fold, unseen codes rejected or encoded by a frozen **source vocabulary**; never infer source categories from test data.
- **Entire model-family/hyperparameter selection occurs within each outer training split**, comparing LR/RF on inner AUROC; favor the simpler LR if inner mean AUROCs differ by no more than 0.01. The outer fold evaluates this selected procedure **once**. Report what fraction of outer folds chose each family; do **not** reselect a model by reusing outer evaluation metrics as if they were unseen independent test data.
- Prespecify source-label stratification and ROC-AUC as primary internal metric. If clinical operating-point threshold is not signed off, report sensitivity/specificity at fixed `0.5` **as an exploratory reference only**, not an operating recommendation. Other metrics: AUPRC with source prevalence, confusion counts, Brier and calibration diagnostics subject to cell-size/feasibility.
- Summarize held-out predictions within each 5-fold outer repetition, yielding **four person-level OOF replicates**; report individual repetition and mean/dispersion. Four measurements per participant are **correlated**, not four independent patients. **No formal prediction-performance 95% CI is claimed for this pilot unless an appropriate resampling estimator is pre-registered and approved.** A separately qualified untouched external cohort can later yield a participant-level bootstrap CI under its own approved protocol.
- Before fitting, reviewers must confirm numeric data-code mapping, sample-size sensitivity assumptions (including anticipated shrinkage/`R^2`), exact library versions, and whether applying reference one-hot coding consistently to penalized LR and RF is clinically/statistically defensible; record any pre-run amendments and reasons.

This is a **complete candidate finite search plan**, not a substitute for the remaining sample-size, predictor-timing and authorization checks.

## 4. Explicit decisions before anyone presses TRAIN

One supervisor meeting or review of this narrow packet should record the following **together**, rather than stopping the team for every technical detail:

| Decision | Our default | Sign-off / revision required |
|---|---|---|
| Target & purpose | source-specific, retrospective current CAD presence; no future time horizon or clinical deployment | Supervisor confirms exact target phrasing and intended population |
| Timing / field eligibility | fixed 5-input resting panel before angiography *as working concept* | Supervisor confirms appropriate retrospective intended-use wording and predictor plausibility/timing uncertainty |
| Sample-size adequacy | 303 source rows / 139 source-positive / 164 source-negative / 8 reference-coded coefficients | Document full justified method/scenarios and NO-GO if unsuitable |
| Models / CV | dummy, penalized LR, constrained RF, finite budget, nested CV | Sign off the **proposed exact seeds/grids above**, and approve an explicit *descriptive pilot uncertainty plan* or replace it with a valid pre-specified CI estimator |
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

> **Update (v0.2, 2026-10-23) — the route in the paragraph above has since been used, and this is recorded rather than reinterpreted.** D-047 was subsequently ratified through its own governance track, and **one Cleveland-only internal exploratory experiment has already been executed**; its sanitized aggregate result is recorded in [document 04](04_d047_first_internal_results_REVIEW_DRAFT.md) under the banner `INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED`. That execution:
>
> - did **not** close or satisfy P-3, P-1 or P-2, and did **not** make this packet approved;
> - remains `PENDING_EXPLICIT_HUMAN_RATIFICATION` in [`docs/DECISIONS.md`](../../DECISIONS.md);
> - is **not** a sample-size adequacy finding (M2e.1 remains `NOT ASSESSED — PENDING HUMAN REVIEW`);
> - is **not** external validation and **not** clinical evidence;
> - was not re-run, re-scored or amended here, and its protocol (`gate-pt/02`) and results (`gate-pt/04`) are untouched by this revision.
>
> The historical wording above is left intact so the earlier governance position stays auditable; the current position is stated in [§6.A](#6a-executive-summary).

---

## 6. Post-M2e.1/M2e.2 supervisor decision addendum (2026-10-23)

> **`ADDENDUM — DOCUMENTATION ONLY — NO DECISION TAKEN — NOT AN APPROVAL`**
>
> - **Added 2026-10-23 (UTC) · v0.2 · base `main` @ `cce8340ac04092f0fedc39d55c9bbca6cda6f05a`.**
> - **Why:** §§1–5 predate [04](04_d047_first_internal_results_REVIEW_DRAFT.md) (D-047 internal results), [05](05_m2e1_sample_size_research_ADEQUACY_REVIEW_DRAFT.md) (M2e.1) and [06](06_m2e2_dataset_compatibility_and_independent_assessment_READINESS_REVIEW_DRAFT.md) (M2e.2). This section records what those documents establish and which decisions remain open.
> - **Relationship to §§1–5:** §§1–5 remain the **historical v0.1 proposal** — not rewritten, reopened or retroactively amended. This section states the **current evidence position** only; the proposed protocol, the D-047 protocol, its results, the decision registers, manifests and gates are untouched.
> - **Not:** supervisor, ethics or institutional approval; a sample-size decision; external validation; a training authorization; a performance claim. No fitting, tuning, simulation, evaluation, dataset access or SHAP/LIME was performed to produce it.

### 6.0 Status carried in

| Item | Status on 2026-10-23 | Must **not** be read as |
|---|---|---|
| **P-1 / D-006** | **PENDING** — endpoint, population, prediction moment, evaluation protocol unfrozen | a settled target |
| **P-3** | **CLOSED** — no supervisor-approved protocol recorded. (The register gate table still words P-3 "PENDING"; both mean **no approval exists**.) | approval, or approval implied by a merged document |
| **P-5** | **NOT MADE — prohibited** | any external-validation or clinical-readiness claim |
| **D-047** | **executed**; `INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED`; register `PENDING_EXPLICIT_HUMAN_RATIFICATION` | supervisor-approved research, adequacy, or clinical evidence |
| **M2e.1** (05) | adequacy **`NOT ASSESSED — PENDING HUMAN REVIEW`**; conditional 382 (C3) / 459 (C4 at p = 8) vs n = 303 | a human sample-size decision, or a GO/NO-GO |
| **M2e.2** (06) | review draft; **no source is `READY`, `VALIDATED` or `APPROVED`** | a selected validation cohort |
| **H-01** | **UNRESOLVED** — `>50%` vs `≥50%` wording difference verified; exact-50% existence/coding unverified. **Scope: cross-family only** (§6.B.2) | a blocker for Cleveland-only work |
| **UCI-411 ↔ 412** | **same cohort** — 303/303 shared rows, 302/303 artery–`Cath` consistency | 606 patients, or independent validation |
| **UCI-145 Statlog** | overlap with Cleveland **UNRESOLVED** | an independent cohort |
| **Raw Cleveland** | **quarantined** (Issue #18); processed Cleveland is a conditional benchmark only | a repaired file |
| **Hungary / Switzerland / VA** | source-specific missingness (Swiss 123/123 zero cholesterol; VA 49/200; Hungary `ca` 291/294 missing) | interchangeable cohorts |

### 6.A Executive summary

**Completed:** one Cleveland-only internal exploratory experiment (document 04: 303 records, 139/164 split, repeated nested CV, pre-registered negative control); conditional Riley-style arithmetic (05); a metadata- and audit-based compatibility/readiness review (06). Gate DA audit findings are unchanged.

**Evidence that exists:** internal, single-cohort, exploratory discrimination and limited calibration aggregates; reproducible formula-level sample-size thresholds; a documented compatibility matrix; preserved audit findings on overlap, missingness, target wording and raw-file quarantine.

**Not validated.** (1) **Development adequacy is not established:** at n = 303 the published criteria require **382**, and **459** at p = 8 for the additional approximate MAPE criterion; no eligible anticipated Cox–Snell R² was identified in the examined sources; status **`NOT ASSESSED — PENDING HUMAN REVIEW`**. (2) **No independent external assessment exists or is currently possible** — no source passes all prerequisite domains, UCI-411 is the same cohort as UCI-412, Statlog overlap is unresolved, sibling sites are conditional. (3) **No publication or clinical claim is supportable** — P-5 NOT MADE, P-4 pending, no ethics/institutional approval.

**Decisions now necessary:** endpoint/population (P-1), prediction timepoint, feature admissibility, the sample-size consequence, D-047's interpretation status, data governance, evaluation design and the claim boundary — then, separately, the H-01 cross-family ruling and whether any independent-assessment programme is pursued.

### 6.B Research team's recommendation

**Recommendation (source-specific, Cleveland only):** keep the Cleveland line as a **narrowly scoped retrospective exploratory benchmark**, and ask the supervisor to settle the endpoint, timepoint, feature-admissibility and sample-size-consequence questions that would allow a *bounded* protocol to be frozen. Do not present the completed run as development adequacy, external validation, publication evidence or clinical evidence; nothing here is a training authorization.

The four categories are kept separate and **none may be promoted into another**:

| Category | What exists | Status | Does **not** support |
|---|---|---|---|
| **1. Retrospective exploratory benchmark evidence** | D-047 **[MR]** aggregates: internal AUROC 0.8271 ± 0.0097 (inner-selected), LR 0.8292, RF 0.8211, dummy 0.4947, shuffle 0.4882 | internal exploratory; one cohort; the same 303 records resampled; no formal CI claimed | adequacy, transportability, calibrated personal probability, clinical or publication claims |
| **2. Statistically and clinically adequate development evidence** | **nothing established** — 382 / 459 vs 303; no admissible anticipated R² identified | **`NOT ASSESSED — PENDING HUMAN REVIEW`** | treating 303 as sufficient, or penalisation/nested CV as a remedy |
| **3. Independent external assessment** | **none** — no source `READY`; 411/412 same cohort; Statlog overlap unresolved; validation-sizing inputs absent | `NOT ASSESSED` / `UNRESOLVED` | external-validation or clinical-readiness statements (P-5) |
| **4. Publication and clinical deployment claims** | **none** — no ethics approval, no P-4 sign-off, no locked model, no TRIPOD+AI/PROBAST+AI assessment | **NOT MADE — prohibited** | publication wording, deployment, patient-facing risk percentages |

**6.B.2 — H-01 is scoped, not general.** H-01 concerns **cross-family target compatibility** (UCI-45 `>50%` wording vs UCI-412/411 `≥50%`) and the undocumented exact-50% boundary. It is a prerequisite for any Cleveland↔412/411 comparison, cross-family pooling, or claim of a common CAD label. It is **not** a prerequisite for a Cleveland-only protocol, which can be evaluated on its own source label, and it should **not** be imposed on every UCI-45 sibling-site scenario — each sibling pair instead needs its own source-specific outcome-coding and reference-standard review (Hungary's processed 0/1 target, Switzerland's 8 source-target negatives, VA missingness).

**6.B.3 — Findings preserved unchanged:** the **411/412 same-cohort** finding (303/303; one unresolved discordance; never 606 patients); **Statlog overlap uncertainty**; **source-specific missingness** (Swiss/VA zero cholesterol, VA zero BP, Hungary `ca`/`thal`, negative `oldpeak`) as site-structured rather than random; and the **raw Cleveland quarantine** (Issue #18).

### 6.C Scientific decision table — blank human sign-off

`PT-DEC-*` are working identifiers for this addendum only — not decision-register IDs. Every decision field is intentionally blank; no agent may prefill it. Reviewer roles are **proposed responsibilities, not appointments**.

**6.C.1 — Cleveland-specific prerequisites (address first)**

| ID | Decision | Current evidence | Team recommendation | Alternatives | Consequence of approve / revise / reject | Reviewer | Decision |
|---|---|---|---|---|---|---|---|
| **PT-DEC-1** | **Endpoint and population (P-1)** | working T1: source-specific concurrent angiographic CAD presence (`num=0` vs `1..4`), historical angiography-referred cohort — not future/30-day risk; P-1 pending | Confirm T1 as the frozen endpoint **for this scoped protocol only**, claims restricted to the named historical referral population | (a) narrower descriptive aim; (b) different endpoint → reopens P-1/D-006, new protocol; (c) defer | Approve: a bounded protocol can freeze. Revise: endpoint text returns for amendment; no training. Reject: documented feasibility material only | Supervisor + research lead | ☐ |
| **PT-DEC-2** | **Prediction timepoint / intended-use wording** | working concept: after history, symptoms, resting BP and resting ECG, before angiography; per-record timing undocumented; no measurement dates in the released schema | Freeze the timepoint **as a working concept only**; describe results as a retrospective benchmark, not a prospective pre-catheterization tool | (a) "historical data, timing unverified" only; (b) restrict the panel further; (c) require timing evidence unobtainable from these sources | Approve: wording usable with the caveat. Revise: narrowed wording. Reject: benchmark description only | Supervisor + clinician | ☐ |
| **PT-DEC-3** | **Feature admissibility** | five-field resting panel `age, sex, cp, trestbps, restecg` → **p = 8**; `ca`, `thal`, `Cath`, per-vessel, identifiers, site and post-outcome fields excluded; labs/exercise block not admitted | Ratify panel and exclusions as a **pre-specified** rule (chosen on availability/timepoint, not association) | (a) collapse `cp`/`restecg` (a different registered analysis, lower p); (b) add lab/exercise fields (needs a timepoint ruling, raises p); (c) defer | Approve: p = 8 is the sizing basis. Revise: recompute the arithmetic for the new p. Reject: no admissible feature set → no protocol | Supervisor + clinician | ☐ |
| **PT-DEC-4** | **Sample-size implications and consequence** | C3 = **382** (R²-free); C4 = **459** at p = 8; both above n = 303; no eligible anticipated R² identified; adequacy `NOT ASSESSED — PENDING HUMAN REVIEW` | Record the consequence the frozen protocol already states: **internal exploratory feasibility pilot only, no predictive-adequacy claim**; an adequacy claim requires a statistician-reviewed R² or an explicit recorded relaxation | (a) documented relaxation (e.g. δ = ±0.056, MAPE ≈ 0.063 at n = 303) with who/why/when; (b) reduce p (C4 met only for p ≤ 5; C3 still fails); (c) obtain a larger eligible source via a new Gate DA decision; (d) NO-GO for any adequacy claim | Approve pilot-only: status confirmed, not upgraded. Revise toward adequacy: named inputs and a recorded relaxation required. Reject: no adequacy language anywhere | Supervisor + statistician | ☐ |
| **PT-DEC-5** | **Interpretation status of the completed D-047 run** | executed; `INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED`; register `PENDING_EXPLICIT_HUMAN_RATIFICATION`; adequacy not assessed | Ratify it **as** an internal exploratory pilot, retaining every label, and state that ratification is not validation | (a) leave pending (status quo); (b) record a documented pre-fit amendment for the five pre-fit plan-file changes; (c) require a re-run under a frozen protocol before any supervisor-level use | Approve: status stabilises; **no** claim changes. Revise: additions recorded as amendments; results not rewritten. Reject: unreviewed internal material | Maintainer + supervisor | ☐ |
| **PT-DEC-6** | **Data governance, provenance, custody** | processed Cleveland only; raw quarantined (#18); UCI DOI `10.24432/C52P4X`, CC BY 4.0; local-only custody; no patient rows in Git or remote agents | Confirm the custody model and require **frozen source hash + download-day licence snapshot + named custodian** before any further execution | (a) additional licence/provenance review; (b) independent hash attestation instead of maintainer attestation; (c) aggregate-only outputs | Approve: model stands. Revise: pause until the named artefacts exist. Reject: no further execution | Data custodian + maintainer | ☐ |
| **PT-DEC-7** | **Evaluation design and reporting limits** | repeated nested 5×5 CV, 4 pre-registered seeds; label-shuffle control; train-fold-only preprocessing; 0.50 exploratory cut-off only | Confirm **internal-only** design: no formal CI from correlated repeats; calibration only where estimable; report all prespecified models including poor ones | (a) pre-register a valid CI estimator before any further fit; (b) reduce the model budget; (c) drop the nonlinear comparator | Approve: design freezable. Revise: re-freeze before any later run. Reject: no evaluation plan | Statistician + research lead | ☐ |
| **PT-DEC-8** | **Claim boundary** | P-5 NOT MADE; P-4 pending; no ethics approval; no locked model; no formal PROBAST+AI/TRIPOD+AI assessment | Keep the boundary: no publication claim, deployment, patient-facing probability, "% risk" or diagnostic wording | (a) internal technical reporting only; (b) commission TRIPOD+AI/PROBAST+AI mapping separately; (c) separate ethics/governance submission | Approve: boundary holds. Revise: narrower only. Reject: feasibility description only | Supervisor + clinician | ☐ |

**6.C.2 — Cross-family and multi-site (separate; must not gate a Cleveland-only decision)**

| ID | Decision | Current evidence | Team recommendation | Alternatives | Consequence of approve / revise / reject | Reviewer | Decision |
|---|---|---|---|---|---|---|---|
| **PT-DEC-9** | **H-01 cross-family ruling** (only for 45↔412/411 comparison or pooling) | wording difference verified; exact-50% existence/coding unverified; dispositions limited to *identical / reconciled / related-but-not-identical / unresolved* | Record **`unresolved`**; cross-family pooling stays prohibited. Not applied to Cleveland-only work or to every sibling-site scenario | (a) `related-but-not-identical`, descriptive only; (b) seek record-level threshold evidence (not in released schemas); (c) defer | Approve: no cross-family claim, no pooling. Revise upward: needs new evidence, not preference. Reject: comparison stays prohibited | Supervisor + research lead | ☐ |
| **PT-DEC-10** | **Independent-assessment eligibility** — pursue / defer / do not pursue | no source `READY`; 411/412 same cohort; Statlog overlap unresolved; sibling sites conditional on P-1, source-specific outcome review, overlap audit, timing map, precision plan | **Defer**, and record external validation as **blocked**, not merely unstarted | (a) later sibling-site **site-shift** protocol (H-01 not applicable to that pair); (b) UCI-412 only after a declared H-01 ruling; (c) close the question | Approve defer: P-5 NOT MADE; no cohort preselected. Revise to pursue: new validation protocol and precision plan required. Reject: validation unavailable | Supervisor + data custodian | ☐ |
| **PT-DEC-11** | **Validation sizing and one-shot evaluation** | Riley 2021 inputs absent (event proportion, anticipated miscalibration, linear-predictor variance, target SEs); no locked model; Switzerland has 8 source negatives | Do **not** compute or adopt a validation sample size yet; require a named method and inputs before any cohort is designated | (a) statistician's precision plan for one named candidate; (b) narrower descriptive compatibility study instead | Approve: nothing sized or selected. Revise: validation plan drafted separately. Reject: no validation study | Statistician | ☐ |

### 6.D Explicit Go / Revise / No-Go pathways

**D.1 — Supervisor approves a narrowly scoped protocol.** Requires in sequence: a **dated, named, signed** decision bound to an **exact protocol version and SHA-256** with a register entry and approved source hashes (a merged documentation PR is not approval); a **recorded sample-size decision** (PT-DEC-4); then bounded execution inside the D-047 internal boundary under local custody rules. No claim category changes. Still **not** authorized: external-validation claims (P-5), clinical/deployment use, publication statements, new datasets, pooling, cross-family comparison, or any `/v1` serving change.

**D.2 — Supervisor requires a smaller or differently framed question.** *Smaller scope:* recompute sizing for the new p and re-freeze as a **dated amendment** — reducing p does not solve the problem, since C3 = 382 is parameter-free and C4 is met only at p ≤ 5. *Different endpoint or population:* reopens P-1/D-006; the existing run is **not** reinterpreted or re-scored, and the old record stays as it is. *Different source:* needs its own Gate DA authorization and inherits none of Cleveland's admissibility or target rulings.

**D.3 — Statistician finds the development sample size insufficient.** Adequacy remains `NOT ASSESSED — PENDING HUMAN REVIEW` or becomes an explicit **inadequate** finding; no predictive-adequacy claim either way; the D-047 run stays an internal pilot and is not re-run to look better. Permitted: record the shortfall, document a named tolerance relaxation with rationale, reduce complexity, or obtain a larger source through a new Gate DA decision. **Not permitted:** penalisation or nested resampling as a remedy; back-deriving an anticipated R² from 0.8271/0.8292 or any fold-level value; selecting the assumption that yields the desired conclusion.

**D.4 — No suitable independent evaluation cohort becomes available.** External validation is recorded as **blocked**; P-5 remains NOT MADE. Permissible outputs: an internal benchmark report, a compatibility/feasibility record, and a stated transportability limitation. **Not permitted:** relabelling the development cohort, an unvetted sibling site, UCI-411 (same cohort), Statlog (unresolved overlap) or a pooled set as "external validation". If the question cannot survive without external evidence, the honest outcome is **No-Go for the clinical claim**.

**D.5 — Additional approval and provenance requirements, recorded separately.** None is satisfied by a positive scientific review; all are **unmet** today: named supervisor signature and date on a frozen protocol with SHA-256 (**absent**); decision-register entry (**absent** — D-047 stays `PENDING_EXPLICIT_HUMAN_RATIFICATION`); recorded sample-size decision (**absent**); named source hashes, download-day licence snapshot and named custodian (**not in Git**; local protected manifest only); signed local authorization manifest (**not in Git**); clinician sign-off on wording (P-4, **pending**); any ethics/institutional approval (**none claimed**); independent TRIPOD+AI/PROBAST+AI assessment (**not performed**); anything implying external validation (**prohibited**).

### 6.E Focused supervisor meeting agenda

Only genuine human scientific, clinical, statistical or institutional judgement. **Excluded:** re-approval of completed technical audits, synthetic/mock infrastructure, ordinary documentation steps, or anything already recorded as merged evidence.

| # | Item | IDs | Lead | Output required |
|---|---|---|---|---|
| 1 | Endpoint, target population and intended-use wording | PT-DEC-1, -2 | Supervisor + clinician | Signed endpoint/population/timepoint text |
| 2 | Feature admissibility and parameter budget | PT-DEC-3 | Supervisor + clinician | Admitted/excluded list with p recorded |
| 3 | Sample-size consequence: pilot-only, documented relaxation, or statistician input | PT-DEC-4 | Statistician | Recorded adequacy decision with tolerances and rationale |
| 4 | Status of the completed internal run and its claim boundary | PT-DEC-5, -8 | Supervisor + maintainer | Ratification or rejection **as internal exploratory only** |
| 5 | Data governance, custody, provenance conditions | PT-DEC-6 | Data custodian | Confirmed custody model and required artefacts |
| 6 | Evaluation-design limits (CIs, calibration estimability, model budget) | PT-DEC-7 | Statistician | Frozen design or a pre-fit amendment list |
| 7 | Cross-family and multi-site questions — **separate session** | PT-DEC-9 to -11 | Supervisor + data custodian | H-01 ruling (`unresolved` recommended); pursue/defer/do-not-pursue |

**Sequencing:** items 1–6 in one meeting; item 7 only after Cleveland's scope is settled, so cross-family questions do not block a source-specific Cleveland decision.

### 6.F What this addendum does not do

Does not approve, freeze, sign or authorize anything (every field in §6.C is blank); does not alter §§1–5, `gate-pt/02`, `gate-pt/04`, `docs/DECISIONS.md`, any manifest, source file, gate or authorization state; does not re-run, re-score, re-analyse or re-select, and does not access data or patient records; does not select a validation dataset, compute a validation sample size, or imply external validation; does not close Issue #29, Issue #37 or any scientific-quality issue, and does not substitute for the tracked approval action.

---

## Evidence

- [M2e.1 sample-size evidence and adequacy review (document 05)](05_m2e1_sample_size_research_ADEQUACY_REVIEW_DRAFT.md): conditional 382 / 459 thresholds at n = 303, `NOT ASSESSED — PENDING HUMAN REVIEW`.
- [M2e.2 dataset compatibility and independent-assessment readiness (document 06)](06_m2e2_dataset_compatibility_and_independent_assessment_READINESS_REVIEW_DRAFT.md): no source `READY`, `VALIDATED` or `APPROVED`.
- [D-047 first internal exploratory results (document 04)](04_d047_first_internal_results_REVIEW_DRAFT.md): `INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED`.
- [D-047 internal exploratory protocol (document 02)](02_d047_internal_exploratory_cleveland_PROTOCOL_PROPOSED.md): frozen method actually executed.
- [Leakage and target-harmonization register](../gate-da/03_leakage_and_target_harmonization_register.md): H-01, L-03, L-04, L-05.
- [Cumulative Gate DA audit record](../gate-da/10_m2a_uci412_uci411_evidence_and_decisions.md): 411/412 correspondence, source-specific missingness, raw Cleveland quarantine.
- [Original UCI Heart Disease source](https://archive.ics.uci.edu/dataset/45/heart+disease): original 0–4 labels, historical 14-attribute processed Cleveland representation, current public metadata.
- [DA-A2 read-only cohort audit](../gate-da/10_m2a_uci412_uci411_evidence_and_decisions.md): source class counts, raw Cleveland quarantine and original-byte custody, human-attested local aggregates.
- [Joint completeness audit](../gate-da/14_real_joint_availability_and_staged_intake_decision.md): five-field resting availability; joint descriptive counts are NOT fitted-model evidence.
- [Full v0.1 protocol draft](../gate-da/15_ai_model_development_evaluation_protocol_DRAFT.md): candidate models, scientific caveats and multi-site restrictions.
- [TRIPOD+AI, BMJ 2024](https://doi.org/10.1136/bmj-2023-078378): transparent definitions of populations/outcomes/predictor timing, sample-size and missingness reporting.
- [PROBAST+AI, BMJ 2025](https://doi.org/10.1136/bmj-2024-082505): risk of bias/quality/applicability review.
- [Riley et al., BMJ 2020](https://doi.org/10.1136/bmj.m441): prediction-model sample size should not be declared adequate using EPV alone.
