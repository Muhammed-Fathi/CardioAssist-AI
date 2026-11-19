# RH-02 — Primary-Source Admissibility and Scientific Decision Packet (Round 1)

**Document ID:** CAI-RH02-SOURCE-ADJUDICATION-2026-11-19-v1  
**Status:** `REVIEW_DRAFT_PRIMARY_SOURCE_METADATA_ONLY` — science working findings, **not** a source-admission decision, supervisor signature, training authorization or external validation.  
**Exact baseline:** GitHub `main` `897eaf61030636edae8dd5ac2ecc7dacf2870f02`, after merged [PR #95](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/95).  
**What was done:** re-read official public UCI-45/412/411 landing pages (2026-11-19), read recent journal/abstract information on AngioCAD and TRIPOD+AI/PROBAST+AI, cross-checked against committed source-admissibility/frozen Gate DA/PT decisions. **No UCI dataset download, Excel workbook, patient file, Git-ignored source, model bundle, locked Hungary set, or new experiment.** An original owner-hosted 2013 paper's full text and the underlying Zenodo AngioCAD record were **not available for full inspection** in this round; an accessible article abstract is not a verified field codebook.

**Controlling sources:** [AI-8R scientific hold](../ai8r/SOURCE_ADMISSIBILITY.md), [Gate PT doc 15 source-question adjudication](../gate-pt/15_scientific_evidence_resolution_and_development_route_REVIEW_DRAFT.md), [M2f Hungary conditional protocol](../gate-pt/07_m2f_hungary_scientific_decision_and_conditional_protocol.md), [dataset/workflow suitability](../gate-pt/12_dataset_selection_and_clinical_workflow_alignment_REVIEW_DRAFT.md), [28 original research claims](RH01_CLAIM_EVIDENCE_INDEX_2026_11_19.json), [master charter](AI_RESEARCH_PROTOTYPE_COMPLETION_CHARTER_2026_11_19.md).

## 1. Adjudication rules (no upgrading weaker evidence)

Each question gets one of these **working documentation statuses**:

- `RESOLVED_PRIMARY_METADATA_ONLY` — first-party dataset-owner page explicitly answers **only** the named dataset-level claim; does not establish record-level timing, patient identities, real model validity or consent.
- `DOCUMENTED_REPOSITORY_AGGREGATE_ONLY` — existing separately authorized maintainer-local aggregate recorded in the repo, not independently re-executed or authenticated by a public source.
- `CONDITIONAL_SOURCE_REVIEW_REQUIRED` — plausible, but must obtain an owner-issued codebook, methods/additional original dataset evidence or a named human scientific disposition before the **narrowly specified** research task.
- `UNRESOLVED_SCIENTIFIC_HOLD` — critical definition, pretest chronology, independence, adequacy or permissions cannot be demonstrated; proposed new real experiment must not start.
- `UNSUITABLE_FOR_THIS_EXTERNAL_CLAIM` — cannot serve as an *independent* validation cohort from the current known lineage, not an assertion the underlying dataset is intrinsically useless.

Authoritative source links reviewed on 2026-11-19 (metadata/documentation, not file bytes):

| Ref | Original public source | What the source can establish here |
|---|---|---|
| PS-45 | [UCI Heart Disease / dataset 45](https://archive.ics.uci.edu/dataset/45/heart+disease), DOI 10.24432/C52P4X | Names four site cohorts; documents common 14/76 field design, source `num` coding, `cp`/`trestbps`/`restecg` and historical `<50%` / `>50%` label wording |
| PS-412 | [UCI Z-Alizadeh Sani / dataset 412](https://archive.ics.uci.edu/dataset/412/z+alizadeh+sani), DOI 10.24432/C5Q31T | 303 records, official **≥50%** CAD label; says 54 features and "No" missing values; displayed field table lacks actual names, methods/units/timing |
| PS-411 | [UCI extension / dataset 411](https://archive.ics.uci.edu/dataset/411/extention+of+z+alizadeh+sani+dataset), DOI 10.24432/C5461K | 303 records; explicitly states LAD/LCX/RCA added, CAD depends on stenosis; not a fresh independent cohort |
| PS-145 | [UCI Statlog (Heart)](https://archive.ics.uci.edu/dataset/145/statlog+heart) | 270 examples; official description says similar to an existing heart database in a different form — source/person independence **not established** |
| PS-ANG | [AngioCAD public article](https://www.sciencedirect.com/science/article/pii/S0169260726001331), linked [Zenodo DOI](https://doi.org/10.5281/zenodo.15826856) | Article description reports 413 X-ray angiography videos with annotations plus clinical/demographic/laboratory data; metadata only. We **did not verify Zenodo underlying schema/files, reuse permissions or pre-index chronology** |
| PS-TRIPOD | [TRIPOD+AI 2024](https://doi.org/10.1136/bmj-2023-078378) | Reporting guidance, **not** automatic certification or an experiment protocol |
| PS-PROBAST | [PROBAST+AI 2025](https://doi.org/10.1136/bmj-2024-082505) | Quality/risk-of-bias/applicability domains: participants/data sources, predictors, outcome, analysis; **no complete source-specific rating in this round** |

**Temporal wording caution:** UCI-45's record-level `num` description explicitly describes a 0 (<50%) versus 1 (>50%) boundary; processed label data use 0 vs 1–4. These two statements do not determine the exact-50% case. UCI-412 explicitly includes ≥50%. A one-character inequality difference is **not evidence of a safely harmonized endpoint**.

## 2. Concrete scientific decisions — source question by source question

| Question | Directly established | Not established / consequence | Round-1 decision | Owner / permissible next action |
|---|---|---|---|---|
| Q-01 Cleveland exact variable meaning | UCI-45 labels `age` (years), `sex` codes, `cp` 4 categories, `trestbps` on-admission mmHg, `restecg` categories [PS-45] | Per-subject clinical availability before angiography, validity of proposed new intake workflow and referral-time measurement | `CONDITIONAL_SOURCE_REVIEW_REQUIRED` | Original Cleveland protocol, dated record-layout or Detrano original methods reviewed by scientific owner; do not equate office BP with on-admission BP |
| Q-02 Cleveland outcome identity | UCI-45 explains angiographic `num` and historic 0 vs 1–4 category distinction [PS-45] | Exact-50% edge handling and uniform core-lab interpretation across sites | `RESOLVED_PRIMARY_METADATA_ONLY` for **source wording**, `UNRESOLVED_SCIENTIFIC_HOLD` for target equivalence | Medical source adjudicator documents limited label transport; no cross-source pooling |
| Q-03 UCI-412 CAD threshold | UCI-412 explicitly defines ≥50% [PS-412] | Record-level annotation protocol, when symptoms/history were elicited, exact boundary correspondence to Cleveland | `RESOLVED_PRIMARY_METADATA_ONLY` for published threshold **only** | Preserve separate source-defined target and acknowledge difference in report |
| Q-04 UCI-412 16-feature acquisition time | No per-feature timestamp, original collection workflow, or diagnostic decision moment appears in the displayed owner table [PS-412] | **0/16 owner-verified preangiography**, post-reference-test leakage cannot be excluded | `UNRESOLVED_SCIENTIFIC_HOLD` | Original collection form/owner-signed acquisition codebook and independent research review; **no new real training** |
| Q-05 UCI-412 `BP` and `PR` | Existing registered dictionary contains one BP scalar and one PR scalar; repository's secondary sources propose plausible interpretations | BP systolic vs diastolic; PR unit `ppm` vs pulses/min; posture/resting conditions, device and source timing unverified | `UNRESOLVED_SCIENTIFIC_HOLD` | Owner field form, codebook or explicit reviewed exclusion/redesign under a newly scoped protocol |
| Q-06 Six numeric binary codes | Maintainer-local source-shape audit previously reported numeric {0,1} representation (not owner verified); 2025 secondary Table 1 suggests 0 absent/1 present | Direction and *clinical definitions* at collection are **not** official-owner verified; feature distribution alone is not proof | `CONDITIONAL_SOURCE_REVIEW_REQUIRED` | Owner meaning/direction for DM, HTN, Current Smoker, EX-Smoker, FH, Typical Chest Pain; no heuristic recoding |
| Q-07 Chest-pain flags | Recorded distinct flags in 16-field registered panel; independent UCI owner page has no field-specific definitions | Categories vs nonexclusive flags, symptom ascertainment and relation to Cleveland `cp` unverified | `UNRESOLVED_SCIENTIFIC_HOLD` for new real crosswalk | Owner question with precise examples; no collapsing and no Cleveland-to-UCI-412 automatic mapping |
| Q-08 UCI-412 feature quantity | Official owner prose says "54 features", landing page displays 56 unlabeled variable-table rows; existing protected local audit reported 55 predictors + `Cath` in workbook | Why counts differ, type/vocabulary exactness of any delivered workbook under current source version | `DOCUMENTED_REPOSITORY_AGGREGATE_ONLY` for local 55+1, plus unresolved source reconciliation | Owner file-level specification / allowed local summary audit only with exact original permission; never fabricate missing column |
| Q-09 UCI-411 independence/leakage | UCI-411 states an *extension* with LAD/LCX/RCA added, 303 records [PS-411]; repo-local audit reports shared 303 | No evidence of independent persons; angiographic artery fields are outcome-derived relative to pretest target | `UNSUITABLE_FOR_THIS_EXTERNAL_CLAIM` | Keep for source-alignment/leakage education only; never call 411 a 303-person independent validation |
| Q-10 Hungary candidate | UCI-45 lists Hungarian site [PS-45]; prior maintainer processed aggregate 294, 188/106 and five resting fields available in 292 | 294 vs historical raw ~425 counts/record identity, processed vs raw correspondence, overlap, target/reference method, predictor time/unit equivalence and acceptable precision | `UNRESOLVED_SCIENTIFIC_HOLD` for real AI-10.2 | Prespecify eligibility/identity review **without external score peeking** and obtain separate human authorization |
| Q-11 Hungary one-shot model freeze | Existing synthetic one-shot evaluator and local ledger exist (AI-10.1); they do **not** authenticate individuals or prove a real model freeze | No real Cleveland clinical-ready frozen model/external permission/specified independent sampling/uncertainty yet | `UNRESOLVED_SCIENTIFIC_HOLD` | Clinical methods owner and maintainer design locked study; no real evaluation until every gate passes |
| Q-12 Statlog overlap | UCI-145 says resembles Heart Disease in a different form [PS-145]; 270 cases | Whether any individual overlaps Cleveland and the meaning of target/measurement times | `CONDITIONAL_SOURCE_REVIEW_REQUIRED` for lineage; `UNSUITABLE_FOR_THIS_EXTERNAL_CLAIM` until independence shown | Original donor documentation; no shortcut to external-validation success |
| Q-13 VA Long Beach / Switzerland | UCI-45 names both sites; prior maintainer aggregate audit documents 200 and 123 processed records with substantial missingness | Person independence, outcome and predictor comparability, meaningful precision, original measurement timing | `CONDITIONAL_SOURCE_REVIEW_REQUIRED` only | Metadata/allowed-readonly source-suitability review; not compulsory extra training |
| Q-14 AngioCAD modern alternative | Public journal description reports 413 angiography videos and segment annotations plus some clinical/demographic/laboratory information [PS-ANG] | Official Zenodo file schema/size/license not inspected; patient-level pre-index tabular predictors, independent person count, patient binary endpoint and clinical timing unverified | `CONDITIONAL_SOURCE_REVIEW_REQUIRED`, **not admitted** | Request/source inspect original metadata, paper supplements and codebook; define separate decision whether equivalent Track A or fundamentally imaging task |
| Q-15 AI-9.2 real same-source labs value | AI-9.1 synthetic paired software runs already completed in accepted history | Same-person eligible real clinical+labs data, lab measurement chronology, missingness/adequacy, approval, prespecified fold design | `UNRESOLVED_SCIENTIFIC_HOLD` | Only new, explicitly reviewed local research protocol/authorization can permit real paired comparison |
| Q-16 Report quality vs clinical approval | Original TRIPOD+AI reporting guidance and PROBAST+AI applicability/bias methodology exist [PS-TRIPOD, PS-PROBAST] | Neither guideline confers ethics permission; full risk-of-bias judgment requires complete evidence about source and design | `RESOLVED_PRIMARY_METADATA_ONLY` for *framework applicability* | Use in report as structured transparency and "not assessable" where unresolved; never claim validated by a checklist |

### Precise field-level UCI-412 findings (16 of 16)

Every entry below is **NOT OWNER-VERIFIED PRE-ANGIOGRAPHY**; a plausible clinical collection path is not proof it was measured/recorded before the source endpoint. The supported source of this mapping is [AI-8R original panel](../ai8r/SOURCE_ADMISSIBILITY.md) and frozen `research/uci412/schemas/uci412_feature_dictionary.v1.json`; **these are registered implementation values, not an original owner field form**.

| # | Registered field | Registered representation | Evidence quality / blocking meaning |
|---|---|---|---|
| 1 | Age | numeric years | Age-at-which-time and original acquisition chronology unverified |
| 2 | Sex | source text Male/Fmale/Female as registered | Exact owner vocabulary, `Fmale` mapping and timestamp unverified |
| 3 | BMI | numeric kg/m² | Derived vs directly recorded; source time/formula not established |
| 4 | DM | numeric 0/1, **direction provisional** | Owner definition/direction and chronology missing; S-9 |
| 5 | HTN | numeric 0/1, **direction provisional** | Owner definition/direction and chronology missing; S-9 |
| 6 | Current Smoker | numeric 0/1, **direction provisional** | Ownership of "current", source direction and time missing; S-9 |
| 7 | EX-Smoker | numeric 0/1, **direction provisional** | Duration and former-history coding missing; S-9 |
| 8 | FH | numeric 0/1, **direction provisional** | Family-history threshold/direction missing; S-9 |
| 9 | DLP | Y/N/Yes/No registered text | Definition (history vs lab) and exact original tokens/time uncertain |
| 10 | BP | numeric mmHg registered | Systolic/diastolic vs other, posture/setting and source timing uncertain |
| 11 | PR | numeric beats/min registered | "ppm" ambiguity; units/device/conditions not source-confirmed |
| 12 | Typical Chest Pain | numeric 0/1, **direction provisional** | S-9 and possible overlap with other symptom flags |
| 13 | Atypical | Y/N/Yes/No registered text | Distinct symptom flag; no proof mutual exclusivity |
| 14 | Nonanginal | Y/N/Yes/No registered text | Distinct symptom flag; no proof mutual exclusivity |
| 15 | Exertional CP | Y/N/Yes/No registered text | Temporal and semantic relation to chest-pain classes unknown |
| 16 | Dyspnea | Y/N/Yes/No registered text | Original symptom assessment timing and definition unknown |

**Working conclusion:** Dataset-owner documentation newly rechecked still lacks the per-feature original time/meaning needed to lift `SCIENTIFIC_HOLD`. The 16 fields remain clinically *plausible* inputs but scientifically **unproven for a pre-catheterization model at the proposed W0 assessment**. No field dictionary/registration change is justified.

## 3. Immediate owner/source evidence requests — precise, reviewable

**Request package U-OWNER (UCI-412 authors or archive curators):**

1. Provide the original 303-record dataset **field codebook and actual case-record form** for the 16 registered fields, including collection date relative to angiography, unit, method, permitted missing tokens, and original storage format. Dataset download or row-level data is **not** requested by this question.
2. Confirm whether `BP` is systolic/diastolic/other, the device/setting and the literal unit for `PR` (including the printed `ppm` notation).
3. Confirm the semantic direction and case definition of each six numeric binary variable; confirm `Fmale` token and Y/N vocabulary.
4. Clarify whether Typical/Atypical/Nonanginal/Exertional chest pain indicators are exclusive, multiple choice, or independently elicited, and whether they were recorded **before** cath result knowledge.
5. Clarify official "54 features" prose vs delivered 55-predictor/`Cath` workbook count, and the exact-50% CAD boundary handling.

**Request package H-OWNER (UCI-45/Hungary source custodians/scientific reviewer):**

1. Identify source-origin 294 processed records versus ~425 historical raw rows, inclusion/exclusion/linkage rules, individual duplicates and whether person-level independence from Cleveland can be supported without opening the locked assessment outcomes.
2. Source-verified on-admission predictor/cath timeline, identical units/source categories, reference standard and exact-50% handling.
3. Evaluate feasibility/precision, missingness and model-freeze suitability from **prespecified source metadata**, before one-shot run; obtain explicit separate scientific protocol and governed local execution approval.

**Request package A-OWNER (AngioCAD authors/curator):**

1. Provide public metadata schema/field names, case/patient counts, permitted use/reuse license and acquisition time for the demographic/laboratory fields.
2. Clarify whether an independently adjudicated preangiography **patient-level binary** obstructive CAD endpoint exists apart from post-cath stenosis/angiography-video labels.
3. If source cannot meet these, explicitly reclassify as an **imaging/segmentation task** in the thesis, not a required extra tabular training cohort.

## 4. Conditional-study decision tree: no false GO, no fake NO-GO

**AI-9.2** can be considered only after source-level verified pretest field meanings + same-person eligible clinical and lab matrix + missingness/sample adequacy + written prespecified paired design + specifically granted local data and fit authorization. Current decision: `HOLD — NOT EXECUTED`. Synthetic AI-9.1 is not evidence of clinical lab benefit.

**AI-10.2** additionally requires person/source independence or an explicit justified restricted transport estimand, compatible target and predictor schema, test-set locking with no preselection via outcomes, adequate evaluation precision, a fully frozen Cleveland model/version, original site data rights and human-approved local run protocol. Current decision: `HOLD — NOT EXECUTED`. Synthetic AI-10.1 does not prove independent external validity.

A **reviewed NO-GO** may later be the honest disposition if no admissible evidence can be obtained; this packet does not prematurely convert `HOLD` to permanent NO-GO. If real external evaluation is an explicit supervisor/graduation requirement, an honest NO-GO is insufficient to claim that requirement was achieved; the required protocol/data must be supplied or the academic claim/scope renegotiated.

## 5. Risk-of-bias / applicability appraisal (provisional, NOT a completed PROBAST+AI review)

| Domain | Observable source limitation | Effect on thesis claims |
|---|---|---|
| Participants / sources | Historic referred selected angiography samples; original sampling and independence/era details incomplete | Referral/spectrum bias; cannot claim general Egyptian population risk accuracy |
| Predictors | UCI-412 pre-index timing unverified; coding and clinical encounter workflow ambiguous | Possible retrospective leakage/transport failure; hold new real pre-cath predictor activation |
| Outcome | UCI-45 `<50/>50` vs UCI-412 `≥50` wording, site reference standard not fully harmonized | No between-dataset ranking/pooled outcome claims |
| Analysis | Repeated nested CV on same 303 records; descriptive repeat SD not CI, small-size/calibration issues | No statistically established external performance or patient-level calibrated probabilities |

Follow [TRIPOD+AI 2024](https://doi.org/10.1136/bmj-2023-078378) for reporting and [PROBAST+AI 2025](https://doi.org/10.1136/bmj-2024-082505) for full development/evaluation appraisal **after** source facts and methods have been independently reviewed; neither is a clinical safety approval.

## 6. Required reviewer action and RH-03 integration

- Reviewer must sign **each** Q-01…Q-16 with source-level finding, date, evidence class, claim effect, and specific outstanding original authority. No global blanket "approved".
- Preserve frozen P-1/P-3/P-5 and D-046/D-047/D-048 permissions; do not edit the original dataset source files, research plans or authorization manifests in this metadata PR.
- Feed explicit source limitations and citations into manuscript chapters FR-04 (sources), FR-05 (predictors), FR-11/FR-12 (conditional studies), FR-15 (bias, ethics), FR-16 (research conclusions) and thesis Q&A.
- Before RH-02 acceptance: reviewer must verify original owner-codebook/paper availability and annotate all unresolved questions, decide conditional protocol scope, and document that no required real study has been fabricated. **This round does not close RH-02**, lift scientific hold or assert author contact.
