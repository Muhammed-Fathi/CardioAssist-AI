# M2e.2 (proposed working label) — Dataset Compatibility & Independent-Assessment Readiness Review

> **`REVIEW DRAFT — DOCUMENTATION ONLY — NOT APPROVED`**
>
> **M2e.2 is a proposed working label only.** It is not an accepted milestone,
> issue, approval, or research gate. This report does not create an issue,
> change a decision register, select a validation dataset, authorize an
> experiment, or establish external validation.
>
> **As of:** 2026-10-23 (UTC)
> **Base reviewed:** `main` / `974dae6a54856b43c5e1b097c81492f07c99d8ca` (the PR #38 merge)
> **Scope:** public metadata/documentation review and synthesis of already-merged,
> aggregate-only evidence.
> **Data boundary:** this review did not access `data/**`, patient-level records,
> protected manifests, original UCI files, local audit reports, prediction
> outputs, or model artifacts. No dataset was downloaded.
>
> **Bottom line:** no source in this report is `READY`, `VALIDATED`, or
> `APPROVED` for independent assessment. The report identifies conditional
> future roles and the human evidence and decisions that would be required to
> justify one.

---

## 1. Purpose, reading guide, and non-claims

This report is the proposed post-M2e.1 readiness package for a future,
independent-dataset assessment. It answers four narrower questions:

1. What does the official public metadata say about the named UCI sources?
2. What aggregate evidence is already available in the merged Gate DA/PT
   records, and what did that evidence *not* establish?
3. Which future roles remain scientifically conceivable, subject to explicit
   conditions, without preselecting a validation dataset?
4. Which decisions and evidence must a research lead, statistician, clinician,
   data custodian, and supervisor make before any such assessment could be
   justified?

### 1.1 Disposition vocabulary

The matrix uses the following deliberately conservative dispositions. A
conditional role is not a readiness decision.

| Disposition | Meaning in this report |
|---|---|
| **VERIFIED** | Directly checked against the cited official metadata/documentation or an already-merged repository record. It is not a clinical truth claim. |
| **UNRESOLVED** | A specific question remains open, or existing evidence includes a discordance. The source is not treated as a `no`. |
| **NOT ASSESSED** | The required assessment has not been performed at the necessary level, or cannot be performed from the public metadata reviewed here. |
| **EXCLUDED FOR THIS PURPOSE** | Excluded from the proposed T1 independent-assessment role because the target construct, provenance, authorization, or known leakage risk is incompatible. This is not a universal exclusion from all future research. |
| **HUMAN DECISION REQUIRED** | Evidence and options are described, but selecting among them is a scientific, clinical, statistical, ethics, or governance act. |
| **CONDITIONAL CANDIDATE — NOT READY** | A possible future role is described only with explicit prerequisites. It is not a selected or approved cohort. |

Evidence is also labelled in prose as **OFFICIAL-METADATA**,
**REPOSITORY-VERIFIED**, **LOCAL-AGGREGATE-CARRIED-FORWARD**,
**LITERATURE-STATUS**, or **PROPOSAL**. The last three labels must not be
promoted to direct source verification.

### 1.2 Hard boundaries carried into this report

- The working endpoint is provisional **T1: cross-sectional classification of
  current angiography-referenced CAD presence**. P-1/D-006 remains pending;
  this wording is not a final clinical target.
- D-047's internal exploratory result is not external-validation evidence. Its
  internal repeated nested-CV AUROC (`0.8271 ± 0.0097`, as reported in
  [Gate PT 04](04_d047_first_internal_results_REVIEW_DRAFT.md)) must not be
  used to choose the most favourable external cohort, set an external target,
  or infer transportability.
- UCI-411 and UCI-412 are not 606 independent patients. The merged audit
  record reports 303/303 correspondence on 56 common columns, with one
  unresolved Cath/artery consistency flag.
- UCI-45 raw and processed files are representations of named cohorts, not
  additional patients. The Hungary/Switzerland positional discordance does
  not prove different patients, corruption, or clinical equivalence.
- `>50%` versus `>=50%` is a verified wording difference, not a verified
  difference in how any exact-50% patient was labelled. H-01 remains open.
- No target, feature set, imputation rule, calibration rule, overlap rule, or
  validation precision target is frozen by this document.
- No action below authorizes acquisition, fitting, feature selection, tuning,
  calibration, explanation generation, outcome evaluation, pooling, or
  external validation. The $0 budget and local custody rules remain binding.

---

## 2. Current governance and evidence baseline

### 2.1 Current status versus historical proposals

The repository contains historical proposal snapshots as well as newer
records. The following is the governing interpretation for this review.

| Item | Current status used here | Evidence / boundary |
|---|---|---|
| Main baseline | `974dae6a54856b43c5e1b097c81492f07c99d8ca`, PR #38 merge | Verified from local Git after fetching `origin/main` on 2026-10-23. |
| D-046 / P-2 | **APPROVED FOR LOCAL READ-ONLY AUDIT ONLY** for DA-A1, DA-A2, DA-B1, and DA-B2 | Current ratification in [`docs/DECISIONS.md`](../../DECISIONS.md) and the local-audit record. It does not authorize modelling, clinical suitability, or external validation. |
| P-1 / D-006 | **PENDING** | Final endpoint, target population, prediction moment, and evaluation protocol are not frozen. |
| P-3 | **CLOSED** for supervisor approval; no supervisor-approved protocol is recorded | Gate PT remains closed for formal research and model-based claims. |
| P-5 | **NOT MADE — prohibited** | No external-validation or clinical-readiness claim exists or is authorized. |
| D-047 | Existing internal exploratory route/result remains bounded as `INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED`; the decision-register entry remains `PENDING_EXPLICIT_HUMAN_RATIFICATION` | Gate PT 04 records the completed internal run, while the decision register retains its pending ratification status. This report does not reconcile, reopen, ratify, amend, or upgrade D-047. See [Gate PT 04](04_d047_first_internal_results_REVIEW_DRAFT.md) and [`docs/DECISIONS.md`](../../DECISIONS.md). |
| M2e.1 | **`NOT ASSESSED — PENDING HUMAN REVIEW`** for development sample-size adequacy | [Gate PT 05](05_m2e1_sample_size_research_ADEQUACY_REVIEW_DRAFT.md) distinguishes development sizing from future validation sizing. This report does not resolve M2e.1. |
| M2e.2 | **Proposed working label only** | No issue, milestone, approval, or decision is invented here. Issue #37 is not closed automatically. |

Several earlier Gate DA documents retain their historical proposal wording,
including “pending” audit authorization or “no acquisition” baselines. The
newer D-046 ratification and the cumulative [M2a audit record](../gate-da/10_m2a_uci412_uci411_evidence_and_decisions.md)
govern the current audit authorization. That supersession changes only the
allowed read-only audit scope; it does **not** convert any source into a
suitable training or validation cohort.

The older [`07_decision_register_unresolved_questions.md`](../gate-da/07_decision_register_unresolved_questions.md)
and [DA-A2 clinical packet](../gate-da/11_da_a2_clinical_suitability_review_packet.md)
remain useful records of unresolved clinical questions. Where their access
status predates D-046 ratification, this report uses the newer decision
register and audit record rather than silently rewriting those historical
records.

### 2.2 Canonical project-specific literature status

The canonical project-specific literature-status source is the supervisor
reviewed extraction
[`research/source_materials/literature_review_status.csv`](../../../research/source_materials/literature_review_status.csv),
not the presentation or speaker notes. The extraction records 25 papers:

- 9 `APPROVED_GREEN` (P1, P2, P4, P5, P7, P9, P10, P14, P15);
- 1 `MAYBE_PINK` (P3);
- 6 `MAYBE_ORANGE` (P6, P8, P19, P20, P21, P23); and
- 9 `REJECTED_RED` (P11, P12, P13, P16, P17, P18, P22, P24, P25).

A GREEN paper is evidence-status approval of that paper under the project
classification; it is not approval of a dataset, a license, a cohort's
independence, or a validation protocol. The extraction's dataset names and
reported metrics are therefore used only as literature-status context. No
presentation citation is used to promote a source or a performance number.

---

## 3. Independent official-source verification (metadata/documentation only)

### 3.1 Retrieval method and limitation

The four UCI landing pages and the historical UCI-45 documentation file were
read as public web pages on **2026-10-23 UTC**. The DOI links are recorded as
identifiers, not as evidence that the source is independent of another source.
No download link was followed and no dataset archive or workbook was opened.

“Directly verified” below means visible in the cited public metadata or
historical documentation. It does **not** mean that the underlying records,
patient identities, collection procedures, or row-level labels were audited.

### 3.2 Official-source ledger

| Source | Exact official metadata/documentation URL and DOI | Source date shown | Directly verified on 2026-10-23 | Limitations of the public evidence |
|---|---|---|---|---|
| **UCI-45 Heart Disease** | [UCI dataset 45](https://archive.ics.uci.edu/dataset/45/heart+disease); DOI [10.24432/C52P4X](https://doi.org/10.24432/C52P4X) | UCI page: “Donated on 6/30/1988.” Historical [`heart-disease.names`](https://archive.ics.uci.edu/ml/machine-learning-databases/heart-disease/heart-disease.names): `Date: July, 1988`, documentation dated July 22, 1988. | Four named databases: Cleveland, Hungary, Switzerland, VA Long Beach; 76 attributes with the conventional 14-column subset; source target `num` 0–4, with published experiments focused on 0 versus 1–4; public page says missing values exist; CC BY 4.0; official file names include raw cohort files and `new.data`. The historical file directly states 303/294/123/200 instances, raw 76-attribute files, 14-attribute copies, `-9.0` missing sentinel, and `num` wording `<50%` versus `>50%`. | The listing does not prove patient independence across sites or between raw/processed representations. It does not establish exact-50% cases or their coding, numeric-zero semantics, per-record measurement timing, or Statlog overlap. The official page's headline `# Instances` is 303 while the historical file enumerates four site counts; both are retained rather than silently reconciled. |
| **UCI-412 Z-Alizadeh Sani** | [UCI dataset 412](https://archive.ics.uci.edu/dataset/412/z+alizadeh+sani); DOI [10.24432/C5Q31T](https://doi.org/10.24432/C5Q31T) | UCI page: “Donated on 11/16/2017.” No collection era is stated on the landing page. | 303 instances; four feature groups (demographic, symptom and examination, ECG, laboratory and echo); CAD/Normal classification; page defines CAD as diameter narrowing `greater than or equal to 50%`; “Has Missing Values? No”; one named XLSX file; CC BY 4.0; creators Roohallah Alizadehsani, Mohamad Roshanzamir, Zahra Sani. | The landing page's variable table leaves the variable names/units effectively unpopulated and does not establish per-feature timing, referral pathway, exact clinical source, row independence, or the meaning of every delivered column. Gate DA's local aggregate record reports a 55-predictor-plus-`Cath` workbook shape, which is a source-description discrepancy requiring review; it is not rechecked here. |
| **UCI-411 Extension** | [UCI dataset 411](https://archive.ics.uci.edu/dataset/411/extention+of+z+alizadeh+sani); DOI [10.24432/C5461K](https://doi.org/10.24432/C5461K) | UCI page: “Donated on 11/16/2017.” No collection era is stated on the landing page. | 303 instances; page says the extension has 59 features and adds `LAD`, `LCX`, and `RCA`; CAD occurs when at least one is stenotic; only one of `LAD`, `LCX`, `RCA`, or `Cath` should be retained for a classification task; CAD threshold is `greater than or equal to 50%`; “Has Missing Values? No”; CC BY 4.0; same three named creators. | “Extension” and matching public metadata support a same-cohort provenance warning, but public metadata alone is not row-level identity proof. The local aggregate audit is the stronger project evidence for correspondence, yet it remains maintainer-reported and was not rerun here. The page does not establish pre-angiography timing or authorize per-artery T2 work. |
| **UCI-145 Statlog (Heart)** | [UCI dataset 145](https://archive.ics.uci.edu/dataset/145/statlog+heart); DOI [10.24432/C57303](https://doi.org/10.24432/C57303) | No donation or collection date was displayed on the landing page during this retrieval. | 270 instances; 13 features; the page describes it as similar to an existing Heart Disease database “in a slightly different form”; no missing values reported; conventional fields include exercise/test and angiography-adjacent variables; target is **absence (1) or presence (2) of heart disease**; files listed include `heart.dat`, `heart.doc`, and `Index`; CC BY 4.0. | “Similar” is not an overlap or independence demonstration. The target is not stated on this page as the UCI-45 `num` coding or as the UCI-412 `>=50%` definition. No aggregate overlap audit against Cleveland is available in the merged records reviewed here. It remains overlap investigation only. |

### 3.3 What was not verified from official metadata

The public pages do not establish, for all candidates, a common clinical
prediction timepoint, an identical target boundary, common assay units,
patient-level independence, or generalizability beyond the source's own
referral/case-mix context. Matching field names, a common UCI host, different
site names, equal row counts, or a “no missing values” page flag cannot fill
those gaps.

---

## 4. Existing issues and merged evidence: status without invention

The configured GitHub integration returned `403 Resource not accessible by
integration` for API/CLI issue retrieval in this session, and the public web
issue routes returned a GitHub `404` page. Therefore this report does **not**
quote or invent issue titles, comments, approval text, or current issue state.
The table below records only the issue relevance already preserved in merged
repository documents, plus the user-specified scope. Maintainers should use
the linked issue as the authoritative live thread.

| Issue | Traceable merged-record relevance | Current research implication |
|---|---|---|
| [#15](https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/15) | [M2a §3–4](../gate-da/10_m2a_uci412_uci411_evidence_and_decisions.md) records one unresolved UCI-411 `Cath`/artery consistency flag after 302 matches under the implemented rule; no row details were published. | Preserve both source labels and originals. Do not correct, delete, relabel, or infer a clinical diagnosis. Clinical/source adjudication remains **UNRESOLVED**. |
| [#18](https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/18) | [M2a §§9 and 14](../gate-da/10_m2a_uci412_uci411_evidence_and_decisions.md) records the upstream raw Cleveland integrity warning and quarantine. The failed strict UTF-8 parse does not identify a bad patient record or justify repair. | Raw Cleveland is quarantined for interpretation. Processed Cleveland is a conditional reference benchmark only; no raw repair, transcode, substitution, or independence claim is authorized. **UNRESOLVED.** |
| [#20](https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/20) | The merged DA-A2 correspondence record reports largely discordant positional raw-versus-processed comparisons for Hungary and Switzerland and explicitly says that row-count equality or low positional agreement does not establish different patients, corruption, or source equivalence. | Keep the issue relevant to provenance/representation review. Do not treat representations as separate cohorts, and do not infer patient mappings or data corruption from positional disagreement. **UNRESOLVED.** |
| [#29](https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/29) | The Gate PT README retains #29 as a tracked approval action. The current decision record still says P-3 is closed for supervisor approval; no issue reference is treated as a sign-off. | A tracked approval action is not approval. The frozen formal protocol and supervisor decision remain pending/closed as recorded. **HUMAN DECISION REQUIRED.** |
| [#37](https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/37) | [M2e.1](05_m2e1_sample_size_research_ADEQUACY_REVIEW_DRAFT.md) identifies #37 as the sample-size adequacy work item, records `NOT ASSESSED — PENDING HUMAN REVIEW`, and distinguishes development sizing from future validation sizing. PR #38 merged the documentation record. | M2e.1 is not resolved by this report. Do not treat conditional development calculations as a validation sample-size calculation. Do not close #37 automatically. **UNRESOLVED / HUMAN DECISION REQUIRED.** |

This access limitation is itself a verification limitation. The report relies
on the merged records for the aggregate facts above and does not imply that
issue threads were independently reviewed.

---

## 5. Preserved aggregate evidence — not rerun here

The following findings are copied as aggregate evidence from the merged
records. They are included to prevent a future reviewer from treating the
same question as an unexamined dataset fact. They are not new analyses.

### 5.1 UCI-412 / UCI-411 correspondence and leakage

`gate-da/10` reports, for the locally authorized read-only audit:

- 303 records in each workbook;
- 56 common columns compared after explicit target normalization;
- 303/303 matched rows in identical positions and 303/303 unordered matches;
- `LAD`, `LCX`, and `RCA` present only in the extension; and
- 302 matches under the implemented Cath/artery consistency rule and **one
  unresolved discordance**.

The official UCI-411 page independently describes the file as an extension of
Z-Alizadeh Sani and says CAD is defined by at least one stenotic artery. The
provenance evidence is sufficient to prohibit an independence or `n=606`
claim. The aggregate correspondence does not authorize relabelling or prove
clinical truth for the discordance.

### 5.2 UCI-45 raw-versus-processed evidence

The cumulative DA-A2 record reports these aggregate comparisons:

| Cohort | Raw rows / processed rows | Same-position exact 13-predictor agreement | Unordered 13-predictor profile match | Unordered binary-target profile match | Interpretation boundary |
|---|---:|---:|---:|---:|---|
| Cleveland | Raw quarantined / 303 | Not evaluated | Not evaluated | Not evaluated | Raw warning remains open; processed file is not an independent cohort. |
| Hungary | 294 / 294 | 1 | 293 | 293 | Consistent with a dominant ordering/representation difference and possible binary recoding; not proof of patient identity or label equivalence. |
| Switzerland | 123 / 123 | 1 | 121 | 121 | Largely positional discordance; not proof of different patients, corruption, or clinical equivalence. |
| VA Long Beach | 200 / 200 | 192 | 192 | 192 | High positional agreement with field-level differences; not proof of exact patient identity or correctness. |

The record further reports formal processed-cell missingness of 782 Hungary,
273 Switzerland, 698 VA, and 6 Cleveland (14-column processed files). The
named `ca` field is missing in 291/294 Hungary, 118/123 Switzerland, and
198/200 VA; `ca` is an angiography-derived leakage concern, not an ordinary
pre-angiography predictor. These counts do not authorize feature deletion,
zero conversion, imputation, or a complete-case claim.

### 5.3 Preserve both availability scenarios

The staged availability audit was explicitly descriptive and counted both
literal-source and zero-as-unavailable scenarios. The following conservative
scenario treats `chol=0` or `trestbps=0` as unavailable **for counting only**;
it did not change source files.

| Processed cohort | n | History (`age/sex/cp`) | Resting (+`trestbps/restecg`) | Resting + labs (+`chol/fbs`) | + exercise (`thalach/exang/oldpeak/slope`) |
|---|---:|---:|---:|---:|---:|
| Cleveland | 303 | 303 | 303 | 303 | 303 |
| Hungary | 294 | 294 | 292 | 261 | 95 |
| Switzerland | 123 | 123 | 120 | 0 | 0 |
| VA Long Beach | 200 | 200 | 143 | 100 | 64 |

Under literal-source coding, the merged record reports Switzerland 47/123 at
the lab stage and 46/123 at the exercise stage, and VA 144/200, 133/200, and
87/200 at the corresponding stages. The two scenarios are not competing
truths: the official UCI codebook does not define numeric zero as a universal
missing code, while the zero-as-unavailable scenario is a sensitivity count
retained because the source values are clinically unresolved. Neither table
is predictive completeness, a feature-selection result, or an approval.

### 5.4 Missingness, timing, and case-mix warnings

- UCI-45's official `heart-disease.names` defines `chol` in mg/dl,
  `trestbps` in mm Hg, and `oldpeak` as exercise-induced ST depression
  relative to rest, but does not state an `oldpeak` unit or a universal
  numeric-zero convention.
- The aggregate audit reports 123/123 Swiss cholesterol zeros, 49/200 VA
  cholesterol zeros, one VA resting-BP zero, and negative `oldpeak` values in
  Switzerland and VA. These are unresolved source/clinical coding questions;
  no automatic correction is permitted.
- The historical cohorts are angiography-referred/case-enriched in the
  project's working description. They are not a general-population screening
  frame. Site names and source counts do not remove selection or era shift.
- UCI-412's 54-feature landing-page description and the locally reported
  55-predictor-plus-`Cath` workbook shape are not silently reconciled. Echo,
  laboratory, symptom/examination, ECG, and treatment-adjacent timing remains
  **UNRESOLVED/NOT ASSESSED per feature**.

---

## 6. Dataset compatibility and readiness matrix

The first table is the high-level role matrix. The detailed records below
supply the requested source, population, target, timing, missingness,
provenance, licensing, evidence identifiers, and conditions. No row has a
`READY`, `VALIDATED`, or `APPROVED` disposition.

### 6.1 High-level matrix

| Candidate / source | Cohort and target summary | Independence / overlap status | Current allowed role | Future role only if all stated conditions pass | Primary disposition |
|---|---|---|---|---|---|
| **UCI-45 Cleveland** — official dataset 45; `processed.cleveland.data` reference | Historical Cleveland benchmark; source `num=0` versus `1–4` for angiographic presence; 1988 source documentation | Raw Cleveland warning; cross-source and Statlog overlap not proven absent | Development/reference benchmark for the already recorded internal exploratory context; metadata review only under existing governance | A future source-specific development/internal-evaluation protocol must resolve P-1, prediction time, leakage, raw-warning handling, sample-size adequacy, and any overlap rule | **CONDITIONAL CANDIDATE — NOT READY**; raw representation **UNRESOLVED** |
| **UCI-45 Hungary** — same official dataset family | Historical Hungarian site; processed aggregate uses a binary form; raw codebook has 0–4 `num`; 1988 source documentation | Different site name is not proof of independent patients; raw/processed identity and cross-site duplicates remain bounded by aggregate evidence | Candidate site-shift assessment only in a future protocol; no current evaluation | Locked Cleveland-source model, H-01 ruling, source-code/unit mapping, timing, missingness/abstention rule, and overlap audit must pass | **CONDITIONAL CANDIDATE — NOT READY** |
| **UCI-45 Switzerland** — same official dataset family | Historical Zurich/Swiss site; source counts 8 `num=0`, 115 nonzero in processed aggregate; 1988 source documentation | Site difference is not proof of independence; raw/processed profiles largely discordant; only eight source negatives creates severe precision concern | Descriptive site-feasibility material only; no current external-validation claim | Same conditions as Hungary plus an a priori decision that the available event/non-event counts can support the intended estimands; otherwise descriptive stress-test or no-go | **CONDITIONAL CANDIDATE — NOT READY / possibly NOT EVALUABLE** |
| **UCI-45 VA Long Beach** — same official dataset family | Historical VA Long Beach site; source counts 51 `num=0`, 149 nonzero in processed aggregate; 1988 source documentation | Site difference is not proof of independence; raw/processed agreement is not patient identity proof | Candidate site-shift assessment only in a future protocol | Same conditions as Hungary plus source-specific missing-input/abstention and unit rules; overlap must be addressed | **CONDITIONAL CANDIDATE — NOT READY** |
| **UCI-412 Z-Alizadeh Sani** — DOI `10.24432/C5Q31T` | 303-patient CAD/Normal source; official page says `>=50%`; feature groups include labs/echo; collection era not stated on landing page | Different UCI dataset ID does not prove independence from UCI-411; target wording differs from UCI-45 | Separate-source compatibility review; not an approved external cohort | Per-feature timing/units, H-01, exact source schema, leakage exclusions, source independence, and external-validation precision must be approved; a separate source-specific study may be more defensible than immediate validation | **CONDITIONAL CANDIDATE — NOT READY** |
| **UCI-411 Extension** — DOI `10.24432/C5461K` | 303-patient extension; official page says 59 features, adds `LAD/LCX/RCA`, and `>=50%` CAD | **Same cohort as UCI-412 for independence purposes**: official extension provenance plus 303/303 shared-record aggregate correspondence; one Cath/artery discordance remains open | Audit-only correspondence/leakage review; never additive sample size | Only a separately approved T2/per-artery question could consider artery fields as targets; it is not a T1 external-validation source | **EXCLUDED FOR THIS PURPOSE** as independent assessment; **UNRESOLVED** discordance |
| **UCI-145 Statlog (Heart)** — DOI `10.24432/C57303` | 270 records, 13 features; official target absence `1` / presence `2`; no missing values reported | Official “similar” wording is not independence evidence; Statlog/Cleveland overlap is unresolved | Overlap investigation only; no training or external validation | An authorized aggregate exact/near-duplicate and provenance review must pass, then a human must decide whether any residual target/feature compatibility exists | **EXCLUDED FOR THIS PURPOSE** until overlap is evidenced; **UNRESOLVED** |
| **Other Gate DA families** | BRFSS/NHANES self-report T3; Framingham incident-event T4; PTB-XL ECG-statement T5; generic CVD-70K and other mirrors; AngioCAD/per-vessel T2 or unapproved/private sources | Not interchangeable with angiographic T1; mirrors and controlled/private sources have separate provenance/access constraints | Separate-target documentation only; no T1 external assessment | Each would require a distinct endpoint, population, ethics/access, and protocol decision; no source is selected here | **EXCLUDED FOR THIS PURPOSE** as T1, or **HUMAN DECISION REQUIRED** for a separate target |

### 6.2 Common UCI-45 feature and timing baseline

The official UCI-45 metadata and `heart-disease.names` document the
conventional predictors as follows. This is a source dictionary, not a
ruling that the variables are admissible at a single clinical timepoint.

| Field(s) | Official definition / unit | Compatibility and timing status |
|---|---|---|
| `age` | Age in years | Potentially pre-angiography, but record-level timing is not documented. **HUMAN DECISION REQUIRED.** |
| `sex` | Sex, source-coded binary | Potentially pre-angiography; exact clinical definition and use wording require protocol review. **HUMAN DECISION REQUIRED.** |
| `cp` | Chest-pain type, four source categories | Symptoms/examination may precede angiography, but the ascertainment moment is not established. **HUMAN DECISION REQUIRED.** |
| `trestbps` | Resting blood pressure on admission, mm Hg | Unit directly verified; zero semantics and decision-time availability require review. **UNRESOLVED.** |
| `chol` | Serum cholesterol, mg/dl | Unit directly verified; numeric zero semantics are unresolved and site structured. **UNRESOLVED.** |
| `fbs` | Fasting blood sugar `>120 mg/dl`, binary | Definition directly verified; collection timing and missingness handling are not frozen. **HUMAN DECISION REQUIRED.** |
| `restecg` | Resting electrocardiographic result, source values 0–2 | A resting test may precede the decision, but the timing and source workflow are not certified. **HUMAN DECISION REQUIRED.** |
| `thalach`, `exang`, `oldpeak`, `slope` | Maximum heart rate, exercise-induced angina, exercise ST depression, peak-exercise ST slope | Exercise-test block; not automatically available at an initial/pre-test moment. `oldpeak` unit is not stated by the official documentation. **UNRESOLVED.** |
| `thal` | Thallium result: 3 normal, 6 fixed defect, 7 reversible defect | Stress-test-derived and timing-sensitive; not a routine-history field and not pre-cleared. **UNRESOLVED.** |
| `ca` | Number of major vessels coloured by fluoroscopy, 0–3 | Angiography-derived and label-adjacent; excluded from a proposed pre-angiography T1 input by the existing leakage guardrail. **EXCLUDED FOR THIS PURPOSE.** |
| Raw attributes 55–68 and identifiers | Cath-date fields, per-vessel angiography fields, and dummy identifiers in the historical 76-attribute list | Procedure/label components or identifiers; never T1 predictors. Raw Cleveland remains quarantined. **EXCLUDED FOR THIS PURPOSE.** |

For UCI-412/411, the official feature-group descriptions do not provide a
complete timing/unit dictionary. No UCI-45 field name may be mapped to a
412/411 field by name alone. `LAD`, `LCX`, `RCA`, and `Cath` are especially
restricted because the official 411 page says that the artery fields define
CAD and only one of them or `Cath` should be retained for classification.

### 6.3 Candidate record: UCI-45 Cleveland

- **Official source / DOI:** dataset 45, [official page](https://archive.ics.uci.edu/dataset/45/heart+disease), DOI
  `10.24432/C52P4X`; the conventional reference file is
  `processed.cleveland.data`. The raw file `cleveland.data` is a separate
  76-attribute representation of the same named cohort, not a second cohort.
- **Cohort and era:** Cleveland Clinic Foundation database; the historical
  documentation is dated July 1988 and reports 303 instances. The working
  Gate DA context is an angiography-referred diagnostic benchmark. The source
  metadata does not establish contemporary or general-population sampling.
- **Outcome:** source `num=0` means no angiographic disease and values `1–4`
  are grouped as presence for the conventional task. The historical wording
  is `<50%` for 0 and `>50%` for positive; H-01 remains unresolved against
  the `>=50%` UCI-412/411 wording.
- **Predictors and timing:** the conventional dictionary is the table in
  §6.2. `ca`, vessel/cath fields, identifiers, and post-outcome measures are
  excluded for a proposed pre-angiography T1 model. Exercise and thallium
  fields require a frozen timepoint and are not pre-cleared.
- **Missingness/completeness:** the merged processed audit reports six
  recognized missing cells in 303 rows; the favorable source-coded
  availability counts do not establish clinical measurement timing or
  validity. It is not evidence that the cohort is complete for all allowed
  future schemas.
- **Warnings and representation:** the official archive `WARNING` and the
  merged audit record place raw Cleveland in quarantine. A non-UTF-8 byte
  under the local parser does not identify a bad record or justify repair.
  Processed Cleveland is the D-047 internal benchmark, not external data.
- **Independence and future role:** current role is conditional development /
  reference benchmark only. A future protocol would need P-1/P-3,
  sample-size review, locked predictor/timepoint rules, raw-warning handling,
  and an overlap rule against other UCI-45 sites and Statlog. **No
  independent-validation role is available for the same Cleveland records.**
- **License/custody:** the official page lists CC BY 4.0. Project policy
  still requires exact authorized files, download-day provenance/license
  snapshots, local out-of-Git custody, and no raw or derived patient-level
  material in Git.

**Disposition:** `CONDITIONAL CANDIDATE — NOT READY` for the reference role;
raw integrity and clinical suitability remain `UNRESOLVED`.

### 6.4 Candidate record: UCI-45 Hungary

- **Official source / DOI:** dataset 45 and the same official metadata/codebook
  as Cleveland; raw `hungarian.data` and processed
  `processed.hungarian.data` are alternate representations.
- **Cohort and era:** Hungarian Institute of Cardiology, Budapest; historical
  documentation dated July 1988 and 294 instances. The project context is a
  historical diagnostic/angiography-referred site; the official metadata does
  not provide a modern population denominator.
- **Outcome:** raw source coding is `num=0,1,2,3,4` under the official
  codebook. The merged processed audit reports a 0/1 form with 188/106
  counts; its aggregate correspondence is consistent with raw nonzero
  binarization, but does not prove each patient's clinical label was
  equivalently recoded. H-01 remains open.
- **Predictors, units, and timing:** uses the UCI-45 conventional field names
  and units in §6.2, but raw/processed column semantics and availability at
  the frozen prediction moment must be checked source-by-source. `ca`, vessel
  fields, and other angiography-derived values remain forbidden T1 inputs.
- **Missingness/completeness:** the merged audit reports 782 recognized
  missing cells in processed 14 columns; `ca` is missing in 291/294 and
  `thal` in 266/294. Conservative stage counts are 292/294 resting,
  261/294 lab-inclusive, and 95/294 with the exercise block. These are
  descriptive denominators, not an approved input rule.
- **Warnings and representation:** same-position exact agreement was only
  1/294, while the unordered 13-predictor and binary-target profile matches
  were 293/294. This does not prove different patients, corruption, a
  particular ordering, or target equivalence. Issue #20 remains relevant.
- **Independence and future role:** a separate-site assessment is only a
  conditional future role. Site name is not patient-independence evidence;
  cross-site duplicates and provenance limits require an authorized
  aggregate-only overlap audit and a human disposition.
- **License/custody:** UCI-45 lists CC BY 4.0; the custody rules in §6.3
  apply.

**Disposition:** `CONDITIONAL CANDIDATE — NOT READY`; target, overlap,
missingness, timing, and representation are `UNRESOLVED` or
`HUMAN DECISION REQUIRED`.

### 6.5 Candidate record: UCI-45 Switzerland

- **Official source / DOI:** dataset 45; raw `switzerland.data` and processed
  `processed.switzerland.data` are alternate representations.
- **Cohort and era:** University Hospital, Zurich, Switzerland in the
  historical UCI documentation; the source file reports 123 instances and
  the July 1988 documentation date. The source is a historical diagnostic
  cohort, not a contemporary screening cohort.
- **Outcome:** historical source `num` is 0 versus 1–4 for presence, with
  the same `<50%`/`>50%` wording issue. The merged processed aggregate
  reports 8 zero-class and 115 nonzero records. This is an audit aggregate,
  not a final target-harmonization ruling.
- **Predictors, units, and timing:** UCI-45 definitions in §6.2 apply only
  as source labels; timing of exercise, thallium, laboratory, and angiography
  fields is not proven. `ca` is missing in 118/123 in the aggregate audit
  and remains a leakage field even when present.
- **Missingness/completeness:** 273 recognized missing cells are reported in
  the processed 14 columns; conservative stage counts are 120/123 resting,
  0/123 lab-inclusive, and 0/123 exercise because all 123 cholesterol zeros
  are treated as unavailable for this descriptive sensitivity scenario.
  Literal-source counts are 47/123 and 46/123 for the latter two stages.
  Both results must be preserved; neither is a clinical coding decision.
- **Warnings and representation:** same-position exact agreement was 1/123,
  unordered predictor match 121/123, and unordered binary-target profile
  match 121/123. No patient mapping, corruption diagnosis, or label repair
  follows. Issue #20 remains relevant.
- **Independence and future role:** a future site-shift evaluation is
  conditional only. The source has eight zero-class records in the processed
  aggregate, so the statistician must determine whether the intended
  discrimination/calibration precision is feasible; a descriptive stress
  test or no-go may be the scientifically correct outcome.
- **License/custody:** UCI-45 lists CC BY 4.0; the custody rules in §6.3
  apply.

**Disposition:** `CONDITIONAL CANDIDATE — NOT READY / possibly NOT
EVALUABLE`; effective missingness, target compatibility, and precision are
`UNRESOLVED`.

### 6.6 Candidate record: UCI-45 VA Long Beach

- **Official source / DOI:** dataset 45; raw `long-beach-va.data` and
  processed `processed.va.data` are alternate representations.
- **Cohort and era:** VA Medical Center, Long Beach, California; historical
  UCI documentation dated July 1988 and 200 instances. This is a historical
  referred diagnostic site, not evidence for contemporary population use.
- **Outcome:** raw source `num=0` versus 1–4 presence; the merged processed
  aggregate reports 51 zero and 149 nonzero records. H-01 remains open.
- **Predictors, units, and timing:** UCI-45 definitions in §6.2; field
  availability is site-structured and no per-record dates establish the
  intended prediction moment. Angiography-derived `ca` and vessel fields
  remain prohibited T1 inputs.
- **Missingness/completeness:** 698 recognized missing cells are reported;
  `ca` is missing in 198/200 and `thal` in 166/200. Conservative stage
  counts are 143/200 resting, 100/200 lab-inclusive, and 64/200 with the
  exercise block; literal counts are 144/200, 133/200, and 87/200. Numeric
  zero and negative-value semantics remain unresolved.
- **Warnings and representation:** same-position and unordered 13-predictor
  agreement are both 192/200. High agreement is not proof of patient
  identity, source correctness, or external independence.
- **Independence and future role:** possible future site-shift assessment
  only after overlap, target, timing, unit, missing-input and precision rules
  are approved. A site label or matching row count cannot establish
  independence.
- **License/custody:** UCI-45 lists CC BY 4.0; the custody rules in §6.3
  apply.

**Disposition:** `CONDITIONAL CANDIDATE — NOT READY`; source independence,
missingness handling, timepoint, and target compatibility remain open.

### 6.7 Candidate record: UCI-412 Z-Alizadeh Sani

- **Official source / DOI:** [UCI dataset 412](https://archive.ics.uci.edu/dataset/412/z+alizadeh+sani), DOI
  `10.24432/C5Q31T`; official page lists one XLSX, 303 instances, four
  feature groups, no missing values, and CC BY 4.0.
- **Cohort and era:** official metadata says it was collected for CAD
  diagnosis; the Gate DA literature-status/context records describe a
  single-centre Iranian referral cohort (Shahid Rajaei Hospital, Tehran),
  but that hospital/context is **SOURCE-REPORTED in project literature
  material**, not directly supplied by the UCI landing page in this pass.
  The UCI page does not state a collection era.
- **Outcome:** official page says CAD if diameter narrowing is `>=50%`,
  otherwise Normal. Gate DA's carried-forward local aggregate reports 216
  `Cad` and 87 `Normal` in the workbook, with no other/missing outcome
  values under its implemented rules. This aggregate was not rerun here.
- **Compatibility and H-01:** directly related to T1's angiographic CAD
  presence construct, but not harmonized to UCI-45's historical `>50%`
  wording. Exact-50% existence/coding is not established. It must not be
  pooled or called a common-target external cohort until H-01 is ruled.
- **Predictors, units, and timing:** the public page names groups but does
  not expose a complete dictionary/units/timing table. Echo and laboratory
  features, treatment-adjacent fields, or any post-angiography measurement
  require a per-feature availability ruling. The locally reported
  55-predictor-plus-`Cath` shape versus the page's 54-feature description is
  a compatibility question, not a reason to invent a mapping.
- **Missingness/completeness:** official page says no missing values; the
  carried-forward local audit reports zero detected cells under implemented
  rules. Neither establishes clinical measurement-stage completeness or
  correct unit semantics.
- **Warnings/provenance:** UCI-412 is source-supported as the same 303-person
  cohort as UCI-411; it has no role as an independent validation source
  against UCI-411. The one Cath/artery discordance is unresolved and no
  correction is allowed.
- **Independence and future role:** separate source-specific development or
  replication is conceivable, but a future assessment of a Cleveland-source
  model requires a human-approved H-01 ruling, a complete per-feature
  mapping, timing/units, leakage controls, independence evidence, and a
  validation precision plan. A different UCI ID is not enough.
- **License/custody:** official page lists CC BY 4.0; exact-file custody and
  no patient-level Git policy still apply.

**Disposition:** `CONDITIONAL CANDIDATE — NOT READY`; target equivalence,
feature timing/units, and intended role are `UNRESOLVED`.

### 6.8 Candidate record: UCI-411 Extension

- **Official source / DOI:** [UCI dataset 411](https://archive.ics.uci.edu/dataset/411/extention+of+z+alizadeh+sani), DOI
  `10.24432/C5461K`; 303 instances, official 59-feature description, and
  CC BY 4.0.
- **Cohort and outcome:** official page calls it an extension, adds
  `LAD/LCX/RCA`, and defines CAD as at least one stenotic artery at `>=50%`.
  These fields are label-defining for a T1 classification task; `Cath` cannot
  be treated as an ordinary predictor.
- **Independence:** official same-creators/same-instance/extension metadata
  plus the carried-forward local aggregate (303/303 common-column
  correspondence) establish a same-cohort prohibition for this purpose.
  They do not require or permit a patient-level disclosure.
- **Missingness and timing:** official page says no missing values, but the
  feature-group description does not establish when each measurement was
  recorded or its units. The added artery fields are outcome/leakage fields
  for pre-angiography T1. The one Cath/artery inconsistency remains
  **UNRESOLVED** under Issue #15.
- **Current/future role:** audit-only correspondence, leakage, and
  dictionary review. It must never be counted as an additive sample or used
  for T1 training or external validation. Only a separately human-approved
  T2/per-artery protocol could revisit its artery fields as targets; T2 is
  not approved here.
- **License/custody:** official page lists CC BY 4.0; custody policy applies.

**Disposition:** `EXCLUDED FOR THIS PURPOSE`; same-cohort status is
`VERIFIED` for planning, the single discordance is `UNRESOLVED`, and no
independent-assessment role is available.

### 6.9 Candidate record: UCI-145 Statlog (Heart)

- **Official source / DOI:** [UCI dataset 145](https://archive.ics.uci.edu/dataset/145/statlog+heart), DOI
  `10.24432/C57303`; 270 instances, 13 features, no missing values reported,
  and CC BY 4.0. The page lists `heart.dat`, `heart.doc`, and `Index`.
- **Population/era:** the official page says only that it is similar to an
  existing Heart Disease database in a slightly different form. No collection
  date, recruitment path, or independent patient roster is provided in the
  metadata reviewed here.
- **Outcome:** official target is absence (1) or presence (2) of heart
  disease. It is not automatically the UCI-45 `num` coding and the page does
  not state the UCI-412 `>=50%` angiographic boundary.
- **Predictors, units, and timing:** feature names are broadly similar to
  UCI-45, including exercise and angiography-adjacent variables, but name
  similarity does not establish the same clinical definition, unit, timing,
  or admissibility. The major-vessel field is subject to the same leakage
  concern if it reflects the angiographic reference process.
- **Independence and missingness:** “no missing values” is a source metadata
  flag, not patient-independence evidence. The Statlog/Cleveland overlap
  question is not resolved by row counts, names, or a common UCI host.
- **Current/future role:** overlap investigation only under the existing
  DA-B2 restriction. A future role would require authorized exact/near
  duplicate and provenance evidence, target/coding compatibility, feature
  timing/units, and a human decision. It is not a current development or
  external-validation cohort.
- **License/custody:** official page lists CC BY 4.0; no file acquisition or
  extraction is authorized by this report.

**Disposition:** `EXCLUDED FOR THIS PURPOSE` until independence is evidenced;
overlap and compatibility are `UNRESOLVED`.

### 6.10 Other registered dataset families: separate constructs, not T1 validation

| Family registered in Gate DA | Source-reported construct/context | T1 relationship and current disposition | Conditions for any different future role |
|---|---|---|---|
| **CDC BRFSS 2015** | Self-reported “heart disease or attack,” US telephone survey; Gate DA labels this T3 | **EXCLUDED FOR THIS PURPOSE.** Self-report and survey sampling are not angiographic T1. | A separate T3 endpoint, survey-weighted protocol, ethics/access review, and claims boundary. |
| **NHANES** | Self-reported CHD/angina/MI variables in a sampled US population; T3 | **EXCLUDED FOR THIS PURPOSE.** | Separate T3 target, survey design/weights, and protocol. |
| **Framingham Heart Study** | Longitudinal incident events; Gate DA labels this T4 and records controlled-access constraints | **EXCLUDED FOR THIS PURPOSE.** It cannot validate a cross-sectional angiographic T1 endpoint. | Separate future-event target, controlled-access/IRB/DUA route, and protocol. |
| **PTB-XL** | ECG statements without an angiographic CAD label; T5 | **EXCLUDED FOR THIS PURPOSE.** | Separate ECG target and validation question. |
| **Kaggle Framingham/CVD or merged UCI mirrors** | Provenance, target, and source custody are not established by the mirror; some are different constructs or recirculations | **EXCLUDED FOR THIS PURPOSE** and do not substitute for official constituents. | Human provenance/license decision and a target-specific protocol; no fallback is implied. |
| **AngioCAD / artery-level or private/controlled cohorts** | Different severity/per-vessel targets or access-constrained/private cohorts in the Gate DA register | **EXCLUDED FOR THIS PURPOSE** in this report; T2/private use is not approved. | Separate human scope, ethics, source, and endpoint decisions. |

These families are listed to prevent construct drift. A target-family label
(T3, T4, or T5) is not a ranking of scientific value; it is a prohibition on
calling that result T1 external validation.

---

## 7. Conditional future independent-assessment feasibility

### 7.1 No current source passes all prerequisite domains

A future external assessment would need all of the following independently
addressed:

1. **Outcome compatibility:** P-1 freezes the diagnostic endpoint and target
   population; H-01 records an evidence-based source-specific ruling. If the
   ruling is `related-but-not-identical` or `unresolved`, the result cannot be
   described as validation of one common target.
2. **Cohort independence:** patient overlap and provenance are assessed with
   privacy-preserving, aggregate-only methods where possible. Same-site,
   same-cohort, raw/processed, and recirculated rows are not counted twice.
   A different dataset ID or site name is not proof.
3. **Frozen prediction moment:** each admitted feature has a clinical
   definition, unit, coding, and evidence it was available before the target
   reference procedure. Unknown timing defaults to excluded or to a
   clearly-labelled non-clinical descriptive analysis, pending human ruling.
4. **Feature compatibility and missingness:** the mapping is source-pair
   specific. The protocol states how `?`, `-9`, zeros, negative values, and
   absent inputs are handled without changing original files. Stage-specific
   denominators and abstention/coverage rules are pre-specified.
5. **Leakage protection:** no `ca`, per-vessel stenosis, `Cath`, `LAD`, `LCX`,
   `RCA`, identifiers, post-outcome measures, or site proxies enter a
   pre-angiography T1 model. Preprocessing and any threshold/calibrator are
   frozen from development and never fitted on the assessment cohort.
6. **Case-mix and site shift:** the future claim names the referral pathway,
   era, site, outcome prevalence, missingness, and measurement system. A
   second angiography-referred cohort tests a related setting; it does not
   establish general-population, contemporary, Egyptian-outpatient, or
   screening performance.
7. **Precision feasibility:** the statistician chooses validation precision
   targets before seeing assessment results and applies an external-
   validation sample-size method. No total-n or event-count shortcut is
   adopted by this report.
8. **One-shot evaluation:** once a source is designated eligible and the
   model is locked, it is evaluated once under the frozen protocol. If it is
   used for model or feature selection, it is development data thereafter and
   cannot retain an external-validation label.

No source currently satisfies all eight domains. Thus every future role in
§6 is conditional and no source is ready.

### 7.2 Candidate-specific conditional roles (not a selection)

| Possible future assessment role | Evidence needed before a protocol could name it | If the evidence fails |
|---|---|---|
| **A UCI-45 sibling site (Hungary, VA, or Switzerland) as a site-shift assessment** | P-1 and H-01; locked model; source-pair feature/unit/timing map; overlap audit; missingness/coverage rule; site-specific event counts and precision calculation | Describe as descriptive compatibility/feasibility material or do not evaluate; never call it external validation. |
| **UCI-412 as a separate-source assessment of a locked model** | H-01 ruling; per-feature dictionary/timing/units; leakage review; independence evidence relative to development data; model/target compatibility; Riley external-validation precision inputs | Keep it a separate source-specific development/replication question or do not use it for T1 validation. |
| **UCI-411** | No condition can make it an independent UCI-412 assessment under current same-cohort evidence. A separate T2 protocol would be a different question. | Audit-only; never additive sample size or T1 external validation. |
| **UCI-145 Statlog** | Exact/near overlap and provenance investigation; target and feature coding/timing mapping; human role decision | Overlap investigation only; exclude from training/validation. |
| **A non-T1 Gate DA family** | A new, distinct target-specific protocol and all access/ethics/precision requirements | Do not re-label its construct as T1. |

This table is not a ranking. It deliberately leaves the choice of whether to
pursue assessment, and which source if any, to the human decision worksheet.

### 7.3 Validation sample size is not M2e.1 development sample size

M2e.1 addresses whether a development experiment can be judged adequate under
specified development assumptions. It remains `NOT ASSESSED — PENDING HUMAN
REVIEW`, and its conditional numbers do not authorize a study.

For future binary-outcome external validation, the relevant Riley et al.
(2021) guidance requires inputs such as:

- target standard errors or confidence-interval widths for each estimand;
- anticipated outcome proportion in the assessment population;
- anticipated model miscalibration and variance of the linear predictor in
  that population; and
- risk thresholds if net benefit is an intended estimand.

The method is designed to obtain precision for calibration (including
observed/expected and calibration slope), discrimination (C-statistic), and
possibly clinical utility, rather than to justify an arbitrary total n. The
project does not yet have a named eligible cohort, frozen target, anticipated
assessment prevalence, locked model/linear-predictor distribution, or
human-approved precision targets. Therefore **no definitive external
validation sample size is computed here**.

The eight Swiss source-negative records in the carried-forward aggregate are
an immediate feasibility warning, not a formula output. A statistician may
conclude that a conventional calibration/discrimination claim is not
estimable there; that conclusion must be made prospectively and documented,
not after inspecting favourable or unfavourable scores.

### 7.4 D-047 cannot choose the external cohort

D-047 is one internal exploratory run on the Cleveland benchmark, with
repeated resampling of the same records and no independent site. Its AUROC is
internal evidence only. It must not be used to choose Hungary, VA, Switzerland,
UCI-412, or any other cohort because it appears likely to give a favourable
result. External-cohort choice must be based on the frozen scientific
question, provenance/independence, target/timepoint compatibility, and a
pre-specified precision plan.

### 7.5 Generalizability boundary for any eventual claim

Even if a future source passes the technical gates, the likely claim would be
bounded to a named, historical, angiography-referred population and a stated
prediction moment. It would not support a general-population screening claim,
a contemporary-care claim, a 30-day event-risk claim, an Egyptian outpatient
claim, a personal calibrated probability, or a clinical deployment claim
without additional evidence and approvals.

---

## 8. Human scientific decision worksheet — all decision fields blank

This worksheet is intentionally concise. The evidence/options column is not a
decision. **Every cell in the final column is intentionally blank for the
research lead, statistician, clinician, supervisor, and maintainer.**
Completing this worksheet does not by itself authorize an experiment; the
relevant gate and data-access approvals remain required.

| Decision item | Evidence and options to review | Human decision / approval field |
|---|---|---|
| **P-1: final diagnostic endpoint and intended target population** | Working T1 is current angiography-referenced CAD presence in a named referral population, not future-event risk. Confirm or revise endpoint, population, and claim boundary. | |
| **Frozen prediction timepoint** | Choose one explicit clinical moment (for example, after the allowed history/resting measurements and before angiography). State what “available before” means. | |
| **H-01 target harmonization** | Rule UCI-45 versus UCI-412/411 as `identical`, `reconciled`, `related-but-not-identical`, or `unresolved`; address exact-50% evidence without guessing. | |
| **Per-feature timing, clinical definition, and unit** | Decide for each admitted feature: source definition, unit, coding, acquisition stage, admissibility, and missing/unavailable semantics. Unknown timing must not be silently admitted. | |
| **Leakage exclusions** | Confirm the pre-angiography exclusion of `ca`, per-vessel fields, `Cath`, `LAD/LCX/RCA`, identifiers, post-outcome variables, and site proxies. | |
| **Source independence / patient-overlap disposition** | Decide what evidence is enough for cross-site independence; adjudicate UCI-411/412 same-cohort status and the Statlog/Cleveland investigation boundary. | |
| **Whether to pursue any external-dataset assessment** | Choose pursue / defer / do not pursue, with scientific rationale. No candidate is preselected by this report. | |
| **Candidate evaluation population and intended claim** | If pursuing, name the population and the narrow claim only after target, overlap, and timing decisions. State what the result will not generalize to. | |
| **Validation precision and statistical methodology** | Select estimands (calibration, discrimination, utility if applicable), target SE/CI precision, outcome fraction assumptions, external-validation sample-size method, and one-shot analysis plan. | |
| **Relationship to M2e.1** | Keep M2e.1 development adequacy `NOT ASSESSED — PENDING HUMAN REVIEW`; decide how its unresolved status constrains any later assessment. | |
| **Ethics, data access, custody, and research-gate approvals** | Confirm named data custodian, exact authorized files, download-day license records, ethics/DUA requirements, Gate DA scope, P-1, P-3, and any P-4/P-5 claims review. | |
| **TRIPOD+AI / PROBAST+AI review ownership** | Name independent reviewers and timing. Framework use is not an approval or a substitute for the scientific gates. | |
| **Reviewer name, role, date, and recorded disposition** | File the human decision in the appropriate governed record; do not put patient-level evidence in GitHub. | |

**Carried-forward statuses that this worksheet must not change:** P-1 is
pending; P-3 remains closed for supervisor approval; P-5 remains “not made —
prohibited”; D-047 remains internal exploratory/not supervisor approved; and
M2e.1 remains not assessed pending human review.

---

## 9. Prioritized evidence-action backlog

### 9.1 Technically completed or already available (do not confuse with approval)

| Priority | Action/evidence | Status and owner boundary |
|---|---|---|
| E-01 | Verify official UCI-45, UCI-412, UCI-411, and UCI-145 metadata, DOI, displayed date/license, target wording, and limitations | **TECHNICALLY COMPLETED** in this documentation review on 2026-10-23; metadata review only, no acquisition. |
| E-02 | Preserve the 303/303 UCI-411/412 correspondence, 56 common columns, and one unresolved Cath/artery inconsistency | **COMPLETED IN MERGED AGGREGATE RECORD** ([gate-da/10](../gate-da/10_m2a_uci412_uci411_evidence_and_decisions.md)); not rerun here; no clinical adjudication. |
| E-03 | Preserve raw-Cleveland quarantine, raw/processed representation rule, positional/unordered aggregate comparisons, and both availability scenarios | **COMPLETED IN MERGED AGGREGATE RECORDS** ([gate-da/10](../gate-da/10_m2a_uci412_uci411_evidence_and_decisions.md), [gate-da/14](../gate-da/14_real_joint_availability_and_staged_intake_decision.md)); no new audit here. |
| E-04 | Preserve the distinction between D-047 internal evidence, M2e.1 development sizing, and future validation sizing | **COMPLETED AS DOCUMENTATION SYNTHESIS**; no gate or experiment status changed. |
| E-05 | Register current roles and conditions without naming a final validation dataset | **COMPLETED BY THIS REPORT**; maintainer acceptance remains required for the proposed working label and document. |

### 9.2 Unresolved clinical, methodological, provenance, or governance actions

The exact prerequisite is stated so that no action can be mistaken for a
free-standing recommendation.

| Priority | Action | Responsible reviewer/role | Exact prerequisite before action can close | Current status |
|---|---|---|---|---|
| **A1** | Freeze P-1 diagnostic endpoint, intended population, and claim boundary | Research lead + supervisor + clinician | Review official target definitions and referral context; record a dated human ruling in the Gate PT decision record. | **HUMAN DECISION REQUIRED** |
| **A2** | Freeze the prediction timepoint and per-feature admissibility | Clinician + research lead | For every proposed feature, supply source definition/unit and evidence of availability before the chosen decision; unknown timing is excluded or explicitly unresolved. | **NOT ASSESSED / HUMAN DECISION REQUIRED** |
| **A3** | Resolve H-01 (`>50%` versus `>=50%`) | Supervisor + clinician/statistician | Evidence about source case definitions and exact-50% existence/coding, or a documented `related-but-not-identical`/`unresolved` ruling. No pooling before it. | **UNRESOLVED** |
| **A4** | Adjudicate the UCI-411/412 Cath/artery discordance without altering source | Clinical/source reviewer + data custodian | Review the original source documentation under authorized local custody; publish only a privacy-reviewed aggregate decision; preserve both originals. | **UNRESOLVED — Issue #15** |
| **A5** | Resolve raw Cleveland integrity disposition | Maintainer/data custodian + research supervisor | Review the official warning and protected original; choose a documented quarantine/interpretation rule. No decoding, repair, replacement, or row deletion by this report. | **UNRESOLVED — Issue #18** |
| **A6** | Resolve Hungary/Switzerland raw-versus-processed provenance interpretation | Data auditor + statistician | A privacy-safe aggregate/order-independent audit and source-format review under D-046, followed by a human interpretation; positional disagreement alone is insufficient. | **UNRESOLVED — Issue #20** |
| **A7** | Investigate Statlog/Cleveland overlap and provenance | Authorized data custodian + research lead | Exact/near-duplicate and provenance evidence under the restricted DA-B2 scope; an explicit human disposition before any role beyond overlap investigation. | **NOT ASSESSED / UNRESOLVED** |
| **A8** | Decide whether an independent assessment should be pursued at all | Research lead + statistician + supervisor | A1–A3, A7, a frozen model/target question, and a written generalizability rationale; no choice based on D-047 performance. | **HUMAN DECISION REQUIRED** |
| **A9** | If pursued, pre-specify external-validation estimands and precision/sample size | Statistician + supervisor | Name the eligible locked model and population; supply event fraction, anticipated miscalibration/linear-predictor variance, target SE/CI widths, and any net-benefit thresholds for Riley et al. 2021. | **NOT ASSESSED** |
| **A10** | Decide missingness, zero, negative-value, and abstention policy | Clinician + statistician | A2 timing ruling plus source coding evidence for `chol=0`, `trestbps=0`, negative `oldpeak`, `?`, and `-9`; pre-register the primary and sensitivity policies before analysis. | **UNRESOLVED** |
| **A11** | Confirm data access, licensing, ethics, custody, and gate approvals | Maintainer + data custodian + research lead | Exact file inventory, download-day license snapshots, local custody, applicable ethics/DUA decision, P-1/P-3 status, and any named clinician/claims review. | **HUMAN DECISION REQUIRED** |
| **A12** | Complete independent TRIPOD+AI and formal PROBAST+AI review for any eventual study | Named independent reviewers | A frozen protocol and actual study record; reviewers answer the framework items and record their own assessment. Framework compliance cannot authorize validation. | **NOT ASSESSED** |
| **A13** | Decide the disposition of this proposed M2e.2 label/report | Maintainer | Human review of this PR/report; no automatic milestone or issue creation is implied. | **HUMAN DECISION REQUIRED** |

---

## 10. Traceability and limitations

### 10.1 Traceability map

| Report requirement | Primary record used |
|---|---|
| Governance, policies, P-1/P-3/P-5, D-047 | [`AGENTS.md`](../../../AGENTS.md), [`docs/DATA_POLICY.md`](../../DATA_POLICY.md), [`docs/DECISIONS.md`](../../DECISIONS.md), [Gate PT README](README.md) |
| UCI-45 source/target/file distinctions | [Gate DA 01](../gate-da/01_dataset_source_and_suitability_matrix.md), [Gate DA 03](../gate-da/03_leakage_and_target_harmonization_register.md), official UCI-45 page and `heart-disease.names` |
| UCI-412/411 correspondence and the one discordance | [Gate DA 10](../gate-da/10_m2a_uci412_uci411_evidence_and_decisions.md), Issue #15 link |
| Raw/processed UCI-45 evidence and Issue #18/#20 boundaries | [Gate DA 10](../gate-da/10_m2a_uci412_uci411_evidence_and_decisions.md), [Gate DA 13](../gate-da/13_engineering_dataset_solution_and_availability_audit.md), [Gate DA 14](../gate-da/14_real_joint_availability_and_staged_intake_decision.md) |
| D-047 internal-only result boundary | [Gate PT 04](04_d047_first_internal_results_REVIEW_DRAFT.md) |
| M2e.1 development sample-size status and validation distinction | [Gate PT 05](05_m2e1_sample_size_research_ADEQUACY_REVIEW_DRAFT.md) |
| Supervisor literature status | [`literature_review_status.csv`](../../../research/source_materials/literature_review_status.csv) |

### 10.2 Important limitations

1. **No underlying data access:** all UCI facts in §3 are public metadata or
   documentation. All numeric audit facts in §§4–5 are carried forward from
   merged, maintainer-reported aggregate records. This review did not rerun
   or independently reproduce them.
2. **No patient-level independence proof:** even a 303/303 correspondence or
   an unordered profile match does not disclose or prove a patient identity;
   equal row counts, site names, and feature completeness are not
   independence evidence.
3. **Source metadata are incomplete:** UCI-412/411 landing pages do not
   supply a complete per-feature timing/unit dictionary, UCI-145 does not
   supply a collection/referral description sufficient for transportability,
   and UCI-45 does not provide record-level chronology.
4. **Threshold boundary is unresolved:** official wording alone cannot show
   that an exact-50% record exists or how either source coded it.
5. **Literature status is not dataset evidence:** the supervisor extraction
   is canonical for project literature status, but its summaries are not
   full-text verification and GREEN status is not data approval.
6. **Issue-body access limitation:** the configured issue integration returned
   403/404 during this pass; live issue comments and approvals were not
   independently read. Merged records are cited instead and live issue
   threads remain the maintainer's authority.
7. **No validation precision number:** the Riley external-validation method
   needs a named locked model, target population, event fraction, anticipated
   miscalibration/linear-predictor variance, estimands, and precision targets.
   Those inputs are not independently justified or human-approved, so no
   definitive n is reported.
8. **No claim about existence elsewhere:** this review assesses registered
   candidates only. It does not claim that no suitable independent source
   exists outside this register.

---

## 11. Methodological references and retrieval record

These references are used for methodological framing, not as approvals or as
substitutes for human review. Pages were retrieved/checked on 2026-10-23 UTC
where noted.

| Reference | Direct source / publication date | Use and limitation here |
|---|---|---|
| Riley et al. (2020), *Calculating the sample size required for developing a clinical prediction model*, BMJ 368:m441, DOI `10.1136/bmj.m441` | [BMJ article](https://www.bmj.com/content/368/bmj.m441), published 2020-03-18; checked 2026-10-23 | Development sample-size framework; informs the unresolved relationship to M2e.1. It does not size a future external validation study. |
| Riley et al. (2021), *Minimum sample size for external validation of a clinical prediction model with a binary outcome*, *Statistics in Medicine* 40:4230–4251, DOI `10.1002/sim.9025` | [Open Wiley article](https://onlinelibrary.wiley.com/doi/full/10.1002/sim.9025), first published 2021-05-24; checked 2026-10-23 | External-validation precision method. It requires target SE/CI widths, validation outcome proportion, anticipated miscalibration and linear-predictor variance, and risk thresholds if net benefit is planned. No project-specific calculation is made here. |
| Collins et al. (2024), **TRIPOD+AI**, BMJ 385:e078378, DOI `10.1136/bmj-2023-078378` | [BMJ article](https://www.bmj.com/content/385/bmj-2023-078378), published 2024-04-16; checked 2026-10-23 | Reporting guidance for prediction-model studies using regression or AI. It structures future reporting; it is not a validation or approval instrument. The official page notes a correction link; this report does not claim checklist completion. |
| Moons et al. (2025), **PROBAST+AI**, BMJ 388:e082505, DOI `10.1136/bmj-2024-082505` | [BMJ article](https://www.bmj.com/content/388/bmj-2024-082505), published 2025-03-24; checked 2026-10-23 | Quality, risk-of-bias, and applicability assessment framework. This report records concerns and prerequisites only; it assigns no PROBAST+AI rating. |

---

## 12. Verification and handoff statement

- `origin/main` was fetched and matched the reviewed `HEAD` at
  `974dae6a54856b43c5e1b097c81492f07c99d8ca` before this document was written.
- Official UCI metadata/documentation pages were read on 2026-10-23 UTC;
  exact URLs, displayed dates, DOI identifiers, direct observations, and
  limitations are recorded in §3.
- The canonical literature-status CSV was used instead of the presentation.
- Existing aggregate audit evidence was reused rather than rerun. No
  `data/**`, patient-level records, protected manifests, original UCI files,
  or individual prediction outputs were accessed.
- No model fitting, simulation, external validation, pooling, row-level
  processing, new dataset acquisition, calibration, feature selection,
  SHAP/LIME, or hyperparameter tuning occurred.
- `git diff --check` and repository/CI status are to be reported by the PR
  handoff, not inferred from this document. A successful documentation PR or
  CI run must not be described as scientific approval.

**Handoff:** leave this PR open for independent human review. Do not merge or
self-approve. The maintainer decides whether the proposed M2e.2 label and this
report should be accepted, revised, or declined; any future experiment still
requires its own approved scientific protocol, data-access controls, and human
gates.
