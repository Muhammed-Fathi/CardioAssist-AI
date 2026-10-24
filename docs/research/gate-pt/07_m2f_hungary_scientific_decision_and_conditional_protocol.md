# M2f — Hungary Scientific Decision & Conditional Evaluation Protocol

**Status:** Review draft; decision-readiness only. **NOT an experiment authorization.**
**Scope:** Whether UCI-45 Hungary could be considered later for one independent site-shift assessment of a future locked Cleveland model. No data were accessed or analyzed for this document.

> **Current disposition: CONDITIONAL CANDIDATE — NOT READY.** Working direction is strategy B (preserve Hungary for a possible one-shot assessment), subject to all gates below. This document does not authorize a Hungary model fit, comparison, evaluation, or data access.

## 1. Decision summary: two strategies

| Strategy | Scientific value | Main risk | Disposition |
|---|---|---|---|
| **A. Train and internally evaluate a separate Hungary model** | Could explore a Hungary-specific prediction model, but answers a different development question. | Uses Hungary for development and therefore cannot also serve as an independent test of the Cleveland model; introduces another model-selection path without resolving source coding, compatibility, or adequacy. | **Not selected as working direction.** Would require its own protocol, approval, and justification. |
| **B. Preserve Hungary as possible site-shift assessment of a future locked Cleveland model** | Directly asks whether the unchanged Cleveland model transports to another named UCI-45 site. | Interpretation is invalid unless target/predictor compatibility, overlap/independence, missingness, and precision are adjudicated first. | **Recommended working direction, conditional only.** No assessment is authorized or ready. |

If Hungary is intended as an independent assessment, it must not be used to choose features, preprocessing, missing-value rules, model family, hyperparameters, calibration, score threshold, or the model/version to report. Any such feedback is information from the assessment set; selecting or changing the model in response makes Hungary part of development/selection, invalidating its role as an untouched independent assessment for that selected model. A later evaluation would need a newly justified independent cohort or a clearly relabeled exploratory/development analysis and new approval. One-shot means one frozen protocol/model assessment; it does not mean suppressing prespecified quality checks or uncertainty reporting.

## 2. Evidence register and provenance

The evidence classes below are deliberately separated. “Verified source documentation” means a statement in the official public UCI-45 documentation, not verification of individual records or clinical truth. Aggregate values are carried forward from maintainer-reported audit records; they were not reproduced here.

| Finding | Evidence class | Meaning / limit |
|---|---|---|
| UCI-45 describes four databases (Cleveland, Hungary, Switzerland, VA Long Beach), the conventional 14-column processed form, and source target `num` coded 0–4; historical documentation describes experiments contrasting 0 with 1–4. | **Verified source documentation**: [UCI Heart Disease dataset 45](https://archive.ics.uci.edu/dataset/45/heart+disease), DOI [10.24432/C52P4X](https://doi.org/10.24432/C52P4X); historical [`heart-disease.names`](https://archive.ics.uci.edu/ml/machine-learning-databases/heart-disease/heart-disease.names). | This documents labels and dataset conventions; it does not certify site-specific reference-standard equivalence or boundary cases. The codebook's wording distinguishes `<50%` and `>50%`; exact-50% existence/coding is not established. |
| Cleveland: 303 records, 164 negative / 139 positive. Hungary: 294 records, 188 negative / 106 positive. | **Maintainer-reported aggregate evidence** ([M2a evidence](../gate-da/10_m2a_uci412_uci411_evidence_and_decisions.md); [M2e.2 review](06_m2e2_dataset_compatibility_and_independent_assessment_READINESS_REVIEW_DRAFT.md)). | Cohort counts only; not model results or proof of independent persons. |
| Hungary has all five prespecified resting fields observed in 292/294 records. | **Maintainer-reported aggregate evidence** ([M2e.2 §5.3](06_m2e2_dataset_compatibility_and_independent_assessment_READINESS_REVIEW_DRAFT.md)). | Availability count, not eligible analysis denominator, imputability, or evidence of clinical availability at a proposed timepoint. |
| Raw versus processed Hungary has 293/294 order-independent matches under the binary-target full profile; positional exact agreement was 1/294 in the earlier reported profile comparison. | **Maintainer-reported aggregate evidence** ([M2e.2 §5.2](06_m2e2_dataset_compatibility_and_independent_assessment_READINESS_REVIEW_DRAFT.md)). | Does not prove patient identity, correct row linkage, corruption, or semantic equivalence. Raw and processed files are representations, not extra cohorts. |
| Processed Hungary target contains 0/1; raw source contains 0–4. Aggregate profile correspondence is consistent with binarization. | **Maintainer-reported aggregate evidence + inference.** | Inference is not verification that every source target was correctly mapped or clinically equivalent. **UCI-45 source-specific target semantic equivalence remains unverified.** |
| Five-feature cross-site profile collisions have been reported; zero exact 11/13-feature cross-site matches have also been reported. | **Maintainer-reported aggregate evidence** ([M2e.2 §§5.2, 6.4](06_m2e2_dataset_compatibility_and_independent_assessment_READINESS_REVIEW_DRAFT.md)). | Collisions do not establish patient identity; zero exact matches do not establish cohort independence. Neither is a substitute for provenance/overlap adjudication. |
| Issues #20 and #21 track positional/provenance and broader raw/processed alignment, missingness, duplication, and target-meaning questions; Issue #29 is a tracked approval action, not approval. | **Existing repository record** ([M2e.2 §4](06_m2e2_dataset_compatibility_and_independent_assessment_READINESS_REVIEW_DRAFT.md), [Gate PT README](README.md)). | Live issue bodies/comments could not be independently retrieved during this pass because GitHub returned HTTP 403. No new issue approval or issue-body assertion is inferred. Human owners must review the live issues. |

**Inference (not a finding):** Hungary may be a useful site-shift assessment population if source compatibility and independence can be sufficiently supported. Historical site distinction, aggregate profile results, and different marginal counts alone do not establish transportability or independence.

**Outstanding human adjudication:** source-target semantics/reference standard; coding and units for each input; timing; overlap/provenance and whether independence is a defensible description; missingness policy; statistical estimands and precision feasibility; ethics/data-access conditions; supervisor protocol approval.

## 3. Conditional protocol proposal — approval required before any execution

Every item in this section is a **proposal for review**, not a frozen protocol or authorization.

### 3.1 Question, population, outcome

- **Scientific question:** In the historically documented UCI-45 Hungary source population, how does a prespecified, locked Cleveland-developed CAD-presence model perform when applied without refitting or tuning, and what uncertainty and site-shift limitations accompany its discrimination and calibration estimates?
- **Source population:** the 294-record historical Hungary cohort in UCI-45 (`processed.hungarian.data` representation), with its actual eligibility, referral mechanism, sampling, dates, and reference procedure to be confirmed from authoritative source documentation. Do not call it a contemporary or general-population sample.
- **Outcome proposal:** source-referenced current CAD presence, not future event risk. Proposed binary mapping is source `num=0` → negative (0), `num=1,2,3,4` → positive (1), matching the documented conventional UCI-45 binary contrast. Do **not** infer ordinal severity or claim a validated common endpoint from this mapping. Human source-specific review must establish that Hungary's processed 0/1 labels faithfully represent that mapping and are comparable to Cleveland's source target, including unresolved threshold/reference-standard semantics. The historical codebook wording `<50%` / `>50%` does not settle exact-50% records.
- **Prediction timepoint proposal:** a single explicitly defined pre-angiography decision point after the five resting inputs are available and before the reference procedure/outcome. This is only a design proposal: source-level chronology does not establish that these measurements preceded angiography for all records. If timing cannot be defended, revise the scientific question or DEFER; do not claim a prospective clinical decision tool.

### 3.2 Inputs, coding, units, missingness

| Canonical field | UCI-45 field / source meaning to verify | Proposal and unresolved requirements |
|---|---|---|
| `age` | Age | Confirm source representation and any unit/range/unknown conventions; map without silent recoding. |
| `sex` | Sex | Preserve source categories and verify Cleveland/Hungary coding equivalence; no assumed recode. |
| `cp` | Chest-pain type | Verify category dictionary and category-level mapping across both source representations. |
| `trestbps` | Resting blood pressure | Official source documentation identifies resting blood pressure and gives mm Hg in the UCI-45 feature description; confirm delivered-file units/coding and measurement timing at both sites. |
| `restecg` | Resting electrocardiographic result | Verify category dictionary and equivalent source coding; establish timing before proposed prediction point. |

Only these five features are proposed. No `ca`, `thal`, vessel/angiography variables, identifiers, row order, site marker, outcome-derived variables, or post-outcome information. The 292/294 joint observed count is not permission to exclude two records, impute them, or define an abstention policy. Before assessment, approve one identical preprocessing and missing-input policy for each site; document exact raw-to-canonical category maps, units, missing sentinels and handling, and reject unrecognized codes fail-closed. All fitted preprocessing must have been estimated within the Cleveland development process and frozen with the model. No Hungary-derived imputation, encoding, recoding, or thresholds.

### 3.3 Minimum evidence for endpoint and source comparability

Before GO, require a documented, human-reviewed evidence bundle containing:

1. Official UCI-45 source documentation/version and authorized file provenance for both sites; source-specific target coding and reference-standard description, with the Hungary raw 0–4 to processed 0/1 mapping established at the aggregate/source-document level and any unresolved exceptions explicitly adjudicated without exposing records.
2. A named clinical/research reviewer ruling on whether the two site outcomes answer the same binary question, including threshold wording and exact-boundary uncertainty. If equivalence cannot be substantiated, do not calculate a pooled/common-endpoint performance summary; revise to a narrower explicitly source-specific estimand or NO-GO.
3. A five-field dictionary for Cleveland and Hungary with verbatim categories, mappings, units, sentinel/missingness rules, and measurement-time evidence. Matching column names alone are insufficient.
4. An approved cohort-provenance/overlap assessment with its limitations. Use permitted aggregate evidence only; no inference of identity from feature collisions or independence from lack of exact matches. If material overlap cannot be excluded or bounded sufficiently for the intended interpretation, DEFER or NO-GO on “independent site” language.
5. A frozen population, denominator, inclusion/abstention and missing-data policy, analysis estimands, and precision plan, reviewed before any predictions/metrics are generated.

### 3.4 Cleveland model-development and artifact-freeze prerequisite

**No full-cohort Cleveland serving artifact exists.** Existing D-047 work is a Cleveland-only internal exploratory evaluation and explicitly reports no saved full-cohort model artifact ([D-047 results review](04_d047_first_internal_results_REVIEW_DRAFT.md)). It is not a serving model, does not authorize Hungary work, and cannot be relabeled as a locked assessment model.

A separate, explicitly scoped and approved model-development step must occur before a site-shift assessment. It must include, at minimum:

- approved/frozen Cleveland development protocol, dataset/use permissions, target and five-feature dictionary, timepoint, statistical adequacy review, missingness and preprocessing plan, and applicable supervisor approval (P-1/P-3); any additional maintainer governance authorization required for real-data model fitting;
- Cleveland-only development and internal evaluation under that approved plan, with all selection (including feature, algorithm, hyperparameter, calibration, threshold, and preprocessing choices) completed without Hungary data or outcomes;
- a versioned final model and preprocessing pipeline, exact feature order/category maps/units, training and source provenance, software/environment record, model specification and checksum, and explicit non-clinical research status; independent review and governance approval of the freeze package;
- a predeclared rule for missing/unrecognized inputs and the evaluation output scale. No claimed calibrated risk probability absent appropriate calibration evidence.

The freeze is for research assessment only; it does not create a serving artifact, authorize product integration, or change M1c engineering authorization.

### 3.5 One-shot assessment, estimands, and uncertainty

- Lock model, feature processing, target mapping, source inclusion rules, and protocol before accessing Hungary for assessment. Apply the frozen model once. Do not use Hungary results to change or select the model. If a protocol violation or data-quality failure is found, stop and report; any later changed analysis requires a new transparent protocol and cannot be represented as the original independent assessment.
- **Precision first, not a guessed sample size:** a statistician must specify the estimands, desired confidence-interval widths/standard errors, confidence level, anticipated outcome proportion and linear-predictor distribution/miscalibration inputs, plus any net-benefit estimand only if justified. Use a recognized external-validation sample-size/precision methodology (e.g., Riley et al. 2021) with justified inputs; assess whether the fixed available cohort can support each target. No universal numeric minimum or assumed statistical parameter is supplied here. M2e.1 development sizing is not external-validation sizing. If precision is inadequate for the intended claim, restrict to descriptive estimates or NO-GO; do not lower standards after seeing results.
- Report discrimination (at least ROC AUC, with uncertainty; any additional measure must be prespecified and justified) and calibration (calibration-in-the-large/intercept and slope and a calibration plot with uncertainty, where estimable and prespecified). State denominators, event counts, missing-input/abstention counts, source mapping and all analysis exclusions. No point estimate without uncertainty and no “validated accuracy” shorthand.
- Do not derive or present calibrated individual risk percentages unless the scale and calibration are justified for the intended population under the approved protocol. No treatment thresholds, net benefit, clinical utility, or clinical readiness claims unless separately prespecified, adequately supported, and approved.
- Report all prespecified results, including null/poor performance and limitations. Distinguish assessment precision from model performance; a successful run is not proof of independence or clinical validity.

## 4. Exact decision matrix (human review required)

“GO” below means only that the specified human gate permits proceeding to the next named research step; it is never automatic from documentation or CI. Current state is **HOLD / NOT READY**.

| Decision | Required evidence / human approval | Current state | Consequence |
|---|---|---|---|
| **GO — protocol review only** | Independent scientific review of this draft; named supervisor review of endpoint, timepoint, estimands, precision method, and population; maintainer review of scope. | **Pending.** P-1 remains **PENDING**; P-3 remains **CLOSED**. Issue #29 is a tracked action, not sign-off. | May revise protocol only. No data operation, fit, or evaluation. |
| **GO — separate Cleveland development and artifact freeze** | Explicitly approved/frozen Cleveland development protocol; statistical adequacy decision; applicable supervisor P-3 approval; separately reviewed and explicitly scoped governance authorization for model fitting; local data/access and ethics/custody approvals as applicable; independent artifact/preprocessing freeze review. | **Not met.** Existing D-047 is limited to its activated Cleveland internal exploratory scope; the results review states no full-cohort artifact. | Only after all approvals, conduct the separately authorized development/freeze step. Does not authorize Hungary assessment. |
| **GO — one-shot Hungary assessment** | All endpoint/source/predictor/units/timing/overlap evidence in §3.3; written precision-feasibility decision; final frozen protocol and locked Cleveland artifact; explicit independent governance authorization naming Hungary and assessment tasks; applicable supervisor P-3 protocol approval and data/ethics/custody permissions; named independent reviewer. | **Not met.** No Hungary comparison, model fit, or validation is authorized. | One approved, locked, one-shot assessment only; no tuning on Hungary. No claim beyond protocol-supported results. |
| **REVISE** | Any specific, resolvable deficiency: source dictionary, unit/category map, target/references, timing evidence, overlap review, missingness rule, precision target, protocol clarity, or approval record. Named reviewer assigns owner and evidence required. | **Available disposition; no approval implied.** | Amend the draft and obtain review again. Do not run analysis while revising. |
| **DEFER** | Evidence may be obtainable, but source semantics, overlap/independence, precision feasibility, required human review, or permissions remain unresolved. | **Current default.** | Preserve Hungary unused for this assessment question; no analysis. |
| **NO-GO** | Endpoint is not sufficiently comparable; independence is not defensible for the intended independent-site claim; five inputs cannot be mapped/timed consistently; approved precision targets cannot be met with the available cohort; required approvals/access are denied; or the protocol cannot be executed without Hungary-driven tuning. | **No final human NO-GO decision recorded.** | Do not conduct the proposed independent assessment. A separately designed Hungary model or descriptive source study would require its own protocol and approvals; cannot be substituted silently. |

## 5. Governance invariants and prohibitions

- **P-1 PENDING; P-3 CLOSED; P-5 prohibited.** No external-validation or clinical-readiness claim is made or authorized.
- **D-046** remains the existing **read-only audit scope**; it grants no training, model selection, performance evaluation, or Hungary comparison authority.
- **D-047** remains limited to its already activated **Cleveland internal exploratory scope**. No extension to Hungary is implied.
- **M1c** engineering authorization is unchanged and does not authorize real model inference/serving, fitting, or site assessment.
- A new Hungary comparison, model fit, or validation requires independently reviewed, explicitly scoped authorization **and** applicable supervisor protocol approval. Any separate model development/artifact freeze also requires its own approvals.
- Do not generate/sign authorizations or manifests; do not change governance status or close issues. Do not access protected local data or request it.
- No dataset download, real-data code execution, model fitting, metrics generation, API/backend change, or engineering change is part of this decision package.

## 6. References and traceability

- Official definitions: [UCI-45 dataset page](https://archive.ics.uci.edu/dataset/45/heart+disease), [historical heart-disease.names](https://archive.ics.uci.edu/ml/machine-learning-databases/heart-disease/heart-disease.names). The official page/codebook is source authority for documented predictor definitions and target coding; site-level semantic equivalence remains a human evidence question.
- Existing context reused, not duplicated: [M2a UCI-412/411 evidence and decisions](../gate-da/10_m2a_uci412_uci411_evidence_and_decisions.md); [M2a cross-site feasibility handoff](../gate-da/17_cross_site_feasibility_audit_handoff.md); [D-047 exploratory results review](04_d047_first_internal_results_REVIEW_DRAFT.md); [M2e.1 development sample-size adequacy review](05_m2e1_sample_size_research_ADEQUACY_REVIEW_DRAFT.md); [M2e.2 compatibility/readiness review](06_m2e2_dataset_compatibility_and_independent_assessment_READINESS_REVIEW_DRAFT.md).
- External-validation precision method cited for future methodological review: Riley et al. 2021, *Minimum sample size for external validation of a clinical prediction model with a binary outcome*, DOI [10.1002/sim.9025](https://doi.org/10.1002/sim.9025). Citation does not supply project-specific parameters or approval.
- Governance source of truth: [`AGENTS.md`](../../../AGENTS.md) and [`docs/DECISIONS.md`](../../DECISIONS.md). This draft changes neither.
