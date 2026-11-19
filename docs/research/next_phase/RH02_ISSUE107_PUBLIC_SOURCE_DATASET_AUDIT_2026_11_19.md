# Issue #107 — PUBLIC-SOURCE-ONLY dataset provenance and role audit

**Document ID:** `CAI-RH02-ISSUE107-PUBLIC-SOURCE-AUDIT-2026-11-19-v1`  
**Date:** 2026-11-19  
**Baseline:** `0835627d524dbe3c512c1f9bd0606b6bcb864f17` (`main` baseline verified by the requester); session branch `arena/26f5fc6c-cardioassist-ai`  
**Status:** `EVIDENCE_REVIEW_DRAFT_NOT_APPROVED` — **NOT APPROVED**; not a source admission, study protocol, model approval, validation result, or clinical claim  
**Machine-readable companion:** [`RH02_ISSUE107_PUBLIC_SOURCE_DATASET_AUDIT_2026_11_19.json`](RH02_ISSUE107_PUBLIC_SOURCE_DATASET_AUDIT_2026_11_19.json)  
**Canonical question register:** [`RH02_SOURCE_QUESTION_REGISTER_2026_11_19.json`](RH02_SOURCE_QUESTION_REGISTER_2026_11_19.json) — byte-identical; SHA-256 `9e3f5f9895f894fb603f90435a69d7b174b24bff291254e208cd7c2201f612d4`  
**Scope:** Q-01, Q-02, Q-09, Q-10, Q-11, Q-12 and Q-13 only.

> **Precedence.** `AGENTS.md`, `docs/DECISIONS.md`, the Master AI Completion Plan, the consolidated RH-02/RH-03 handoff merged in PR #108, and the canonical 16-question register remain controlling. This report is an evidence map and a set of **proposed** review dispositions. It changes **no** decision ID, gate, frozen protocol, dataset permission, authorization manifest, artifact hash, model, backend capability or clinical status. An unresolved question stays unresolved unless a named human reviewer records a separate decision.

## 1. Trigger, authority and hard boundaries

`gh issue view 107 --repo Muhammed-Fathi/CardioAssist-AI` returned exactly `GraphQL: Resource not accessible by integration (repository.issue)`. Under the requester's explicit fallback instruction, this document executes the complete Issue #107 public-source research scope without relying on an issue body.

This audit was conducted **PUBLIC-SOURCE-ONLY**:

- No UCI archive ZIP, workbook, processed `.data` file, raw file, or other patient dataset was downloaded, opened, hashed, read, or copied.
- No patient row, patient-level aggregate newly computed from rows, identifier, local report, protected bundle, model artifact, or locked external test outcome was accessed.
- No model was trained, tuned, scored, calibrated or evaluated; no inference path was enabled.
- No frozen protocol, feature dictionary, decision register entry, authorization template, workflow, backend contract, or `MOCK_SYNTHETIC` provider boundary was modified.
- The only aggregate missingness/record-count figures reused below are **explicitly labelled E2**, were previously recorded in reviewed repository documents from the maintainer's local read-only audit, and were **not re-derived here**. They are not a substitute for primary owner documentation or a clinical ruling.
- The completed UCI-412/AngioCAD literature investigation from PR #106 was **not repeated**. UCI-412 and UCI-411 landing pages are consulted here only for the already-registered Q-02/Q-09 relationship and threshold contrast.

Nothing in this report authorizes a dataset acquisition, a Hungary evaluation, a Cleveland model freeze, use of Statlog as an independent test set, a real-data experiment, or a patient-facing claim.

## 2. Evidence grading and source catalog

Evidence grades follow the Master Plan §15.3: **E1** = official dataset-owner documentation, original publication or registry; **E2** = reproducible local audited aggregate under a recorded scope; **E3** = peer-reviewed/reputable secondary research or a secondary transcription; **E4** = explicit inference/arithmetic from cited facts; **E5** = synthetic software fixture (none used as evidence here). A web copy of a paper is labelled by its content's grade with an explicit access limitation; a search-excerpt-only item is not presented as a fully read page.

| ID | Exact URL | Authority | What it directly establishes | What it cannot establish |
|---|---|---|---|---|
| `S-UCI45` | https://archive.ics.uci.edu/dataset/45/heart+disease | E1 — official owner page, retrieved 2026-11-19 | Four named sites; 303 headline instances; 13 features/14-column historical subset; `num` 0–4 with presence 0 vs 1–4; verbatim definitions for the conventional fields; `trestbps` mm Hg “on admission”; `num` 0 `<50%`, 1 `>50%`; names/SSNs replaced; “Has Missing Values? Yes”; creators; DOI `10.24432/C52P4X`; CC BY 4.0 | Per-patient acquisition timestamps, exact-50% coding, cross-site patient independence, harmonized clinical semantics, contemporary applicability |
| `S-UCI45-NAMES` | https://archive.ics.uci.edu/ml/machine-learning-databases/heart-disease/heart-disease.names | E1 — official UCI documentation, dated 22 July 1988, retrieved 2026-11-19 | Four source institutions/principal investigators; 76 raw attributes, two copies of each database, 14 used in past experiments; class vectors for all four sites (Cleveland 164/55/36/35/13; Hungary 188/37/26/28/15; Switzerland 8/48/32/30/5; VA 51/56/41/42/10); missing raw code `-9.0`; historical accuracy note ≈77% at a 0.5 probability threshold; `num` wording `<50%` / `>50%` | The delivered processed files were not opened; no per-field timestamps, no exact-50% resolution, no proof that raw and processed rows are the same people, no ethics/consent permission |
| `S-DETRANO-ABSTRACT` | https://europepmc.org/article/MED/2756873 | E1 — original peer-reviewed article abstract, *Am J Cardiol* 1989;64(5):304–310, PMID 2756873 | 303 Cleveland derivation patients; external groups of 425 Hungary, 200 VA Long Beach and 143 Zurich/Basel; prevalences 38%, 75% and 84%; calibration over-/under-prediction and conclusion limited to chest-pain syndromes/intermediate prevalence | The five-field UCI processed panel, individual timestamps, exact-50% handling, license, or identity between publication cohorts and delivered UCI files |
| `S-DETRANO-DOI` | https://doi.org/10.1016/0002-9149(89)90524-9 | E1 — DOI record for the same original paper | Bibliographic identity and publisher link | Full text was paywalled in this pass; no independent full-text page reading is claimed from this URL alone |
| `S-DETRANO-FULLTEXT-COPY` | https://www.academia.edu/4827700/International_application_of_a_new_probability_algorithm_for_the_diagnosis_of_coronary_artery_disease | E3 — third-party-hosted transcription of primary-paper text, retrieved 2026-11-19; not an owner codebook | Searchable text stating angiograms abnormal at `>50%` luminal narrowing of any major epicardial vessel; histories/examinations/noninvasive tests within six weeks before angiography; 143 Swiss patients split 58 Zurich/85 Basel in 1985 | No per-field timestamp; host is not the journal or data owner; OCR/transcription errors are possible; does not certify the delivered UCI files |
| `S-STATLOG145` | https://archive.ics.uci.edu/dataset/145/statlog+heart | E1 — official owner page, retrieved 2026-11-19 | 270 instances, 13 features; “similar” to UCI Heart Disease but “slightly different form”; target 1 absence / 2 presence; `ca`-equivalent and `thal` fields present; “Has Missing Values? No”; DOI `10.24432/C57303`; CC BY 4.0 | Independent patients, original stenosis threshold, clinical reference standard, or official declaration that it is a Cleveland subset |
| `S-STATLOG-PROJECT` | https://archive.ics.uci.edu/dataset/98/statlog+project | E1 — official UCI Statlog Project page, retrieved 2026-11-19 | European StatLog comparative project; its Heart Disease database is described as similar to the repository's earlier heart database and as 13 attributes extracted from a larger set of 75; DOI `10.24432/C5XS3B` | Exact subject lineage, Cleveland overlap, or equivalence with the current UCI-45 processed schema |
| `S-STATLOG-BOOK` | https://www.ai.rug.nl/minds/uploads/MantasRecommendedBook.pdf | E1 bibliographic / partial-access — Michie, Spiegelhalter & Taylor (eds.), *Machine Learning, Neural and Statistical Classification*, 1994; searchable copy located this pass, not fully page-read | StatLog was a European comparative classification project; its datasets were distributed as test cases for multiple methods | This specific heart file's patient provenance, target definition or overlap status; do not cite a page number that was not read |
| `S-STATLOG-ORIGIN-SECONDARY` | https://link.springer.com/content/pdf/10.1023/A:1007608224229.pdf | E3 — peer-reviewed secondary article, search excerpt only | Reports the StatLog `heart` set as 270 records from the Cleveland Clinic Foundation courtesy of R. Detrano | Full-page verification, threshold, recoding details, or proof of patient-level non-overlap |
| `S-STATLOG-OVERLAP-THESIS` | https://libres.uncg.edu/ir/ecsu/f/Brandon_Simmons_Thesis-Final.pdf | E3 — academic thesis, search excerpt only; not independently page-read | Reports a 270-record Statlog set and claims it is a proper subset of the 303-record Cleveland set (`303 = 270 + 33`) | Owner confirmation, auditable row mapping, or permission to rely on it for a project decision; treated as an overlap **hypothesis** only |
| `S-UCI411` | https://archive.ics.uci.edu/dataset/411/extention+of+z+alizadeh+sani+dataset | E1 — official owner page, retrieved 2026-11-19 | 303 patients, 59 features, explicitly an extension adding LAD/LCX/RCA; CAD if ≥50% narrowing and at least one of those arteries stenotic; only one of `LAD`, `LCX`, `RCA`, `Cath` may be used for classification; DOI `10.24432/C5461K`; CC BY 4.0 | Row-level identity with UCI-412 was not checked here; no new independent subjects |
| `S-UCI412` | https://archive.ics.uci.edu/dataset/412/z+alizadeh+sani | E1 — official owner page, retrieved 2026-11-19; used only for the existing cross-family contrast | 303 patients with ≥50% definition and 54-feature four-group description; DOI `10.24432/C5Q31T` | Any new UCI-412 finding; no repeat of the completed #106 investigation |
| `S-RILEY` | https://onlinelibrary.wiley.com/doi/abs/10.1002/sim.9025 | E1 — original methods paper, Riley et al., *Statistics in Medicine* 2021;40:4230–4251 | External-validation sizing needs target SE/CI width, validation event proportion, anticipated (mis)calibration and linear-predictor variance, and any decision thresholds; can assess adequacy of an already-collected cohort | It does not supply CardioAssist parameters or approve a study |
| `S-REPO-A2-AUDIT` | https://github.com/Muhammed-Fathi/CardioAssist-AI/blob/0835627d524dbe3c512c1f9bd0606b6bcb864f17/docs/research/gate-da/10_m2a_uci412_uci411_evidence_and_decisions.md | E2 — reviewed repository record of maintainer-local read-only aggregate audit; reused, not re-run | Site class vectors, processed missing-cell totals, per-field missing counts, one excess full-row duplicate in Hungary and VA, and the stated inference limits | E1 clinical truth or permission; no patient rows were accessed for this report |
| `S-REPO-HUNGARY-DECISION` | https://github.com/Muhammed-Fathi/CardioAssist-AI/blob/0835627d524dbe3c512c1f9bd0606b6bcb864f17/docs/research/gate-pt/07_m2f_hungary_scientific_decision_and_conditional_protocol.md | E2 — reviewed repository conditional protocol draft | 292/294 five-field joint availability (historical aggregate), strategy B recommendation, current `HOLD / NOT READY`, and named frozen-model/one-shot prerequisites | Scientific approval, a frozen protocol, or data access |
| `S-REPO-REGISTER` | https://github.com/Muhammed-Fathi/CardioAssist-AI/blob/0835627d524dbe3c512c1f9bd0606b6bcb864f17/docs/research/next_phase/RH02_SOURCE_QUESTION_REGISTER_2026_11_19.json | E2 — canonical repository status register at verified baseline | The 16 official question IDs/statuses and the explicit `PENDING` human dispositions | Any promotion of a finding into an approved status |
| `S-REPO-HANDOFF` | https://github.com/Muhammed-Fathi/CardioAssist-AI/blob/0835627d524dbe3c512c1f9bd0606b6bcb864f17/docs/research/next_phase/RH02_RH03_CONSOLIDATED_RESEARCH_HANDOFF_2026_11_19.md | E2 — PR #108 handoff snapshot | Dataset-role matrix, Hungary priority, historical evidence labels, and the prohibition on implied approval | A new source decision; the handoff explicitly says status promotion requires a separate reviewed decision |

No downloaded archive, local dataset path, patient row, protected report, or model artifact appears in this catalog.

## 3. Canonical question status — copied, not promoted

The status column is copied verbatim from the canonical register. “Finding” is this report's **provisional evidence disposition**, not an official status and not a human decision.

| Question | Canonical status | This report's finding | Decision owner / requirement |
|---|---|---|---|
| **Q-01** Cleveland five-field meaning and pretest timeline | `CONDITIONAL_SOURCE_REVIEW_REQUIRED` | `GO_REVIEW`: owner definitions are explicit; per-field pre-angiography timing is not | Clinical/research reviewer must obtain original acquisition documentation; no D-047 reinterpretation |
| **Q-02** UCI-45 label boundary | `SOURCE_WORDING_RESOLVED_EQUIVALENCE_UNRESOLVED` | `GO_REVIEW`: `<50%` vs `>50%` wording is primary-source verified; exact 50% and cross-family equivalence remain unknown | Endpoint adjudicator must rule on exact-50 and threshold compatibility; no silent harmonization |
| **Q-09** UCI-411 independence | `UNSUITABLE_FOR_THIS_EXTERNAL_CLAIM` | `NO_GO` for independence; `GO_REVIEW` only for overlap study | Maintain exclusion of UCI-411 as independent validation or added sample size |
| **Q-10** Hungary eligible independent cohort | `UNRESOLVED_SCIENTIFIC_HOLD` | `GO_REVIEW` for admissibility; `HOLD` for any use | Owner/site provenance, target equivalence, overlap and precision before a named scientific disposition |
| **Q-11** Hungary one-shot freeze | `UNRESOLVED_SCIENTIFIC_HOLD` | `HOLD` | Separate approved Cleveland freeze, locked protocol/model hashes, one-shot ledger and named local authorization |
| **Q-12** Statlog overlap | `CONDITIONAL_SOURCE_REVIEW_REQUIRED` | `NO_GO` as independent validation; `GO_REVIEW` for audit-only overlap | Source-donor/duplicate evidence required; no pooling or test-set use meanwhile |
| **Q-13** VA/Switzerland suitability | `CONDITIONAL_SOURCE_REVIEW_REQUIRED` | VA `HOLD` for limited stress role; Switzerland `NO_GO` for a primary locked validation, `HOLD` for descriptive suitability only | Site-specific target, missingness, precision and role decision by statistician/clinical reviewer |

## 4. Dataset findings

### 4.1 Cleveland / UCI-45 `DA-A2` — Q-01, Q-02

**Original sources and authority.** [UCI-45](https://archive.ics.uci.edu/dataset/45/heart+disease) and the official [heart-disease.names](https://archive.ics.uci.edu/ml/machine-learning-databases/heart-disease/heart-disease.names) documentation are E1. The [1989 original article abstract](https://europepmc.org/article/MED/2756873) is E1; the third-party-hosted [paper transcription](https://www.academia.edu/4827700/International_application_of_a_new_probability_algorithm_for_the_diagnosis_of_coronary_artery_disease) is E3 and is used only for the six-week acquisition window and `>50%` endpoint wording.

**Cohort and source facts.** UCI lists four databases — Cleveland, Hungary, Switzerland and VA Long Beach — and credits Cleveland/VA to Robert Detrano and the other sites to Andras Jánosi, William Steinbrunn and Matthias Pfisterer. The official documentation says each database has 76 raw attributes while 14 were used in past experiments, and that two copies of each database were made. Cleveland has 303 records with class vector `164/55/36/35/13`; binarized presence is `139` positive versus `164` negative (`164 + 55 + 36 + 35 + 13 = 303`; E4 arithmetic from E1 counts). Names and social-security numbers were replaced by dummy values. UCI declares “Has Missing Values? Yes”; the historical local audit separately reported six recognized missing cells in the processed Cleveland columns (E2, not re-verified here). CC BY 4.0 is the repository license; author-attribution requests remain in the original documentation.

**Five resting fields — original definitions verbatim in substance (E1).**

| Field | Source definition | Units/code | Prediction-time finding |
|---|---|---|---|
| `age` | Age in years | years | Plausibly available before angiography, but no delivered-file timestamp |
| `sex` | Sex; `1` male, `0` female | nominal binary | Same limitation |
| `cp` | Chest pain type: `1` typical angina, `2` atypical angina, `3` non-anginal pain, `4` asymptomatic | four nominal codes | Symptom classification timing not documented per record |
| `trestbps` | Resting blood pressure in mm Hg **on admission to the hospital** | mm Hg | “On admission” is not a formal pre-angiography timestamp; admission could be the index workup, but source does not certify it |
| `restecg` | Resting electrocardiographic results: `0` normal; `1` ST-T abnormality (T inversions and/or ST elevation/depression `>0.05 mV`); `2` probable/definite LVH by Estes' criteria | three nominal codes | No reading date or relation to catheterization is supplied |

The E3 paper transcription says histories, physical examinations and all noninvasive tests were performed within six weeks **before** angiography. That supports a historical group-level pre-procedure window; it does **not** certify that the five delivered UCI codes were captured at one declared prediction moment, that `trestbps` and `restecg` came from the same encounter, or that the processed file is row-for-row the published cohort. The five-field panel remains the existing **PROPOSED_NOT_APPROVED** resting mapping, not a clinically verified acquisition contract.

**Endpoint and label interpretation.** UCI's `num` field is `0 = <50% diameter narrowing`, `1 = >50% diameter narrowing` in any major vessel, and the official experiments contrasted presence (`1,2,3,4`) with absence (`0`). The original paper transcribed at E3 calls an angiogram abnormal at `>50%` luminal narrowing of any major epicardial vessel. This is a **cross-sectional angiographic presence** target, not a 30-day or future-event outcome. Neither primary source defines a record at exactly 50%; neither establishes that UCI-45's strict `>50%` and UCI-412's `≥50%` ([UCI-412](https://archive.ics.uci.edu/dataset/412/z+alizadeh+sani)) select the same patients. Q-02 stays equivalence-unresolved.

**Historical research limitations.** The 1989 derivation used 303 patients from one referral centre and clinical/noninvasive tests; the paper's inter-site application showed clinically important calibration errors (overprediction in Hungarian and US groups, underprediction in the Swiss group) and explicitly concluded with chest-pain/intermediate-prevalence scope. The UCI documentation reports only ≈77% correct classification for a 0.5 threshold. Those figures belong to the historical algorithm and cohort; they are **not** five-field CardioAssist performance. Modern claims are further limited by the 1980s era, angiography-referral selection, small sample, dummy identifiers, undocumented per-field timing, and the `ca` leakage issue below.

**Leakage/overlap.** UCI attribute `ca` is the number of major vessels coloured by fluoroscopy and raw attributes 59–68 are the vessels defining the diagnosis; these are outcome-adjacent and prohibited as pre-test predictors. `thal` and the exercise-test block have unresolved timing. Same-named fields across the four UCI-45 sites do not prove independent people; cross-site duplicates cannot be excluded from public metadata, and identifiers were dummy-replaced.

**Recommendation — `GO_REVIEW` (source clarification only).** Continue Q-01/Q-02 owner-documentation review; do **not** treat the five-field timing or threshold as approved, do not reinterpret the historical D-047 result, and do not use Cleveland as an external test of any UCI-412 model.

**Required decisions before any new study:** (1) clinical owner ruling with dated acquisition evidence for all five fields; (2) endpoint adjudicator ruling on exact-50% and strict-vs-inclusive threshold; (3) frozen, separately approved Cleveland development protocol and documented artifact SHA if a model is ever intended for transfer; (4) source-pair overlap disposition. None is recorded as complete.

### 4.2 Hungary / UCI-45 — priority external-validation candidate — Q-10, Q-11

**Original sources and authority.** Site identity, 294-instance count and class vector `188/37/26/28/15` come from E1 [UCI-45](https://archive.ics.uci.edu/dataset/45/heart+disease) and [heart-disease.names](https://archive.ics.uci.edu/ml/machine-learning-databases/heart-disease/heart-disease.names). The [original 1989 abstract](https://europepmc.org/article/MED/2756873) is E1. The [conditional Hungary decision draft](https://github.com/Muhammed-Fathi/CardioAssist-AI/blob/0835627d524dbe3c512c1f9bd0606b6bcb864f17/docs/research/gate-pt/07_m2f_hungary_scientific_decision_and_conditional_protocol.md) and [local aggregate record](https://github.com/Muhammed-Fathi/CardioAssist-AI/blob/0835627d524dbe3c512c1f9bd0606b6bcb864f17/docs/research/gate-da/10_m2a_uci412_uci411_evidence_and_decisions.md) are E2 and are quoted, not re-executed.

**Cohort independence.** E1 sources support distinct named institutions: the original study reports a Cleveland derivation set and a separate Hungarian Institute of Cardiology test group of **425** patients (38% prevalence), while the UCI codebook lists **294** Hungarian records with 188 negative and 106 positive (`37+26+28+15=106`, E4 arithmetic). The different counts mean the delivered file must not be assumed to be the publication's full 425-patient group. UCI dummy-replaced identifiers and offers no subject linkage. Different site labels and differing marginal counts are **not** proof of patient-level independence; cross-cohort overlap with Cleveland remains a named unresolved blocker (B-04 in the E2 cross-site handoff). Public-source-only research cannot close it.

**Target compatibility.** UCI-45 supplies the same `num` coding across sibling sites, but the official wording leaves exact 50% undefined. E2 aggregate evidence says processed Hungary has only `0/1` while raw Hungary has `0–4`, with positives consistent with binarization; that is an aggregate signal, not proof that each patient's label was clinically equivalently recoded. A named clinical/research reviewer must rule on whether Cleveland and Hungary answer the same binary endpoint before any common-endpoint performance claim. Q-02/Q-10 remain unresolved.

**Five-feature availability and timing.** The official dictionary defines `age`, `sex`, `cp`, `trestbps` and `restecg` for the shared 14-column schema. E2 reports 292/294 joint observed records for the five resting fields and 782 recognized missing cells among the 14 processed columns; `ca=291`, `thal=266`, `slope=190` dominate, with one missing `trestbps` cell. These counts are descriptive denominators, **not** an approved complete-case rule and not evidence that the five values were recorded before the reference procedure. No owner-provided per-field timestamp exists. Missingness must never be silently imputed from Hungary after a model freeze.

**Licensing and custody.** UCI-45 displays CC BY 4.0 and the codebook asks publications to name each site's principal investigator. Repository policy still forbids committing patient-level files; a license is not ethics/consent approval, and no download is authorized by this report.

**Sample size / precision.** Delivered counts are 294 total, 106 positive and 188 negative from the E1 class vector. Riley et al. (E1, [DOI](https://onlinelibrary.wiley.com/doi/abs/10.1002/sim.9025)) require prespecified CI-width/SE targets, validation prevalence, anticipated calibration and linear-predictor variance, and any decision thresholds. There is no locked Cleveland artifact, no approved five-field evaluation scale, and no approved precision target; therefore no scientifically defensible adequacy verdict can be issued from N alone. Do not invent a universal minimum or reuse development sample-size work as external-validation sizing.

**Recommendation — `GO_REVIEW` for admissibility; `HOLD` for any real one-shot execution.** Hungary remains the highest-priority *candidate* for a future separately approved, frozen, one-shot assessment of a Cleveland model. It is not approved, not prepared, and not an executed external validation. AI-10.2 remains `NOT_PERFORMED`.

**Required decisions before GO:** (1) site/owner provenance and overlap disposition; (2) clinical endpoint-equivalence ruling including raw→processed coding and exact-50 handling; (3) five-field category/unit/timestamp and missingness policy; (4) a separately approved frozen Cleveland model and preprocessing pipeline with exact SHA-256; (5) statistician's written Riley-style precision decision; (6) locked one-shot protocol, named independent reviewer, and explicit governance/local data authorization. Any Hungary-driven selection after a test would destroy the one-shot interpretation and require relabelling as development.

### 4.3 Statlog (Heart) / UCI-145 — Q-12

**Provenance.** The official [UCI-145 page](https://archive.ics.uci.edu/dataset/145/statlog+heart) describes 270 records, 13 features, no missing values, target `1 = absence` / `2 = presence`, and a database “similar” to UCI Heart Disease in “slightly different form.” The [UCI Statlog Project page](https://archive.ics.uci.edu/dataset/98/statlog+project) places the file in the European StatLog comparative project and says the 13 attributes were extracted from a larger set of 75; the [1994 edited volume](https://www.ai.rug.nl/minds/uploads/MantasRecommendedBook.pdf) establishes the project's comparative purpose. A peer-reviewed [secondary article excerpt](https://link.springer.com/content/pdf/10.1023/A:1007608224229.pdf) describes the StatLog heart set as originating from the Cleveland Clinic Foundation; an academic [thesis excerpt](https://libres.uncg.edu/ir/ecsu/f/Brandon_Simmons_Thesis-Final.pdf) goes further and claims the 270 records are a proper subset of the 303 Cleveland records (`303 = 270 + 33`). The latter two are E3, not owner-confirmed, and were search-excerpt-only in this pass.

**Overlap conclusion.** The official statement of similarity plus the secondary subset claim is enough for a **suspect-duplicate** ruling and more than enough to forbid an independence claim. It is **not** enough for this agent to assert a verified patient-level mapping: no row comparison, hash join, or owner lineage confirmation was performed, and none is permitted here. Public metadata cannot establish that the 33-record difference, recoding or file version is clinically meaningful. Q-12 remains open.

**Target/feature compatibility.** The UCI-145 label is “absence/presence of heart disease” coded 1/2; no stenosis threshold or adjudication protocol is printed on the official page. It therefore cannot be silently identified with UCI-45 `num` 0 vs 1–4 or with UCI-412 `≥50%`. The feature list mirrors the conventional 13, including a fluoroscopy-derived `ca` field and `thal`; the same pre-test leakage and timing restrictions apply. “No missing values” is owner metadata about the delivered file only.

**Licensing.** CC BY 4.0 on UCI-145, with the same no-redistribution/custody rules as above. License availability does not answer provenance or independence.

**Recommendation — `NO_GO` for independent validation or pooling; `GO_REVIEW` for an authorised audit-only overlap investigation.** Statlog may remain only a lineage/duplicate-suspect case until a named reviewer accepts owner or aggregate evidence.

**Required decisions before any change:** (1) source-donor/original Statlog documentation of the heart file's donor cohort; (2) privacy-preserving exact and near-duplicate overlap analysis on shared stable fields under a separately recorded authorization; (3) explicit clinical ruling on target wording/threshold; (4) decision either to exclude permanently or relabel any analysis as sensitivity, never independent validation.

### 4.4 UCI-411 Extension — Q-09

**Relationship established by the owner.** The [UCI-411 page](https://archive.ics.uci.edu/dataset/411/extention+of+z+alizadeh+sani+dataset) says it is an extension of Z-Alizadeh Sani, contains **303** patients, adds `LAD`, `LCX` and `RCA`, and defines CAD by at least one of those arteries being stenotic at ≥50%. It explicitly instructs that only one of `LAD`, `LCX`, `RCA` or `Cath` be retained for a classification task. The [UCI-412 page](https://archive.ics.uci.edu/dataset/412/z+alizadeh+sani) describes the same 303-patient baseline with ≥50% narrowing and four feature groups. Both pages carry CC BY 4.0. No workbook or row-level comparison was performed here; the existing canonical register already records the same-cohort provenance finding (E2, [register](https://github.com/Muhammed-Fathi/CardioAssist-AI/blob/0835627d524dbe3c512c1f9bd0606b6bcb864f17/docs/research/next_phase/RH02_SOURCE_QUESTION_REGISTER_2026_11_19.json)).

**Why it cannot independently validate UCI-412.** The extension changes the feature dictionary of the **same** 303 participants; it does not add people. Counting both files as 606 patients or training on one and testing on the other would reuse the same underlying subjects, events and angiographic result. The three added artery fields plus `Cath` are components of the outcome definition and are target leakage if used as pre-test predictors. Any per-artery target would be a different, currently unapproved estimand, not a validation of the binary CAD model. Row-level 411↔412 correspondence remains a separate audit-only question; its absence does not create independence.

**Recommendation — `NO_GO` for independent validation, training addition or sample-size doubling; `GO_REVIEW` only for an explicitly authorized overlap/leakage study.** Keep Q-09's canonical status and the frozen UCI-412 holds unchanged.

**Required decisions before any change:** a recorded owner/version reconciliation and a privacy-preserving same-cohort correspondence ruling; neither would convert the extension into independent patients.

### 4.5 VA Long Beach / UCI-45 — Q-13

**Source and endpoint.** [UCI-45](https://archive.ics.uci.edu/dataset/45/heart+disease) and [heart-disease.names](https://archive.ics.uci.edu/ml/machine-learning-databases/heart-disease/heart-disease.names) identify V.A. Medical Center, Long Beach; 200 records with class vector `51/56/41/42/10` (149 positive, E4 arithmetic), and attribution to Robert Detrano. The [original abstract](https://europepmc.org/article/MED/2756873) describes a 200-patient VA test group with 75% prevalence, consistent in size and approximate prevalence with the delivered file but not proven to be the same subjects. The original endpoint was `>50%` luminal narrowing of a major epicardial vessel; UCI-45 prints the same strict wording but leaves exact-50% unresolved. This is a cross-sectional angiographic endpoint, not a future-event label.

**Missingness and feasibility.** UCI declares missing values for the dataset family. The E2 local aggregate record reports 698 recognized missing cells in the processed 14 columns (24.93%), including `ca=198/200`, `thal=166/200`, `slope=102/200`, `oldpeak=56/200` and `trestbps=56/200`. These figures were not re-derived here and cannot define a missing-data policy. The proposed five fields are present in the schema, but site-specific timestamps, units as delivered, and joint availability are unresolved. The analysis must not use `ca`, must not impute from a future locked test set, and must declare abstention versus prespecified training-fold-only preprocessing before any scoring.

**Independence and role.** A different site does not establish non-overlap with Cleveland; identifiers were dummy-replaced. Site case-mix and prevalence differ, so calibration transport is an open scientific question. Public evidence supports at most a conditionally reviewed missingness/domain-shift stress role, not a current external-validation claim. No shared endpoint/recoding ruling exists for a sibling-site comparison beyond the source wording.

**Recommendation — `HOLD` for a narrowly scoped, separately approved stress/domain-shift assessment; `NO_GO` for pooling, calibration transfer or a current validation claim.** A named statistician must first write the precision estimand and an evaluator must confirm the five-field policy; D-046 read-only permission cannot be relabelled as model-use permission.

**Required decisions:** source-pair overlap and target semantics; missingness/abstention rule; frozen model and SA; explicit governance authorization naming VA and its limited role.

### 4.6 Switzerland / UCI-45 — Q-13

**Source, subset and endpoint.** The E1 [UCI-45 page](https://archive.ics.uci.edu/dataset/45/heart+disease) / [codebook](https://archive.ics.uci.edu/ml/machine-learning-databases/heart-disease/heart-disease.names) list 123 Swiss records with class vector `8/48/32/30/5` — 115 positive and only **8** `num=0` negatives. The [original abstract](https://europepmc.org/article/MED/2756873) instead reports a 143-patient Swiss test group from Zurich and Basel with 84% prevalence; the E3 [paper transcription](https://www.academia.edu/4827700/International_application_of_a_new_probability_algorithm_for_the_diagnosis_of_coronary_artery_disease) splits those 143 as 58 Zurich/85 Basel in 1985. The delivered 123/93.5%-positive file is therefore not the full published group (E4 arithmetic from E1 counts), and neither subset identity nor site-level reference-standard details are verified. The target wording is the same UCI-45 `>50%` with the same exact-50 ambiguity.

**Missingness and precision.** UCI reports missing values. The E2 aggregate record lists 273 recognized missing cells (15.85%) in 14 columns, with `ca=118/123`, `fbs=75/123`, `thal=52/123`, `slope=17/123`, `trestbps=2/123`, and reports `chol=0` for all 123 delivered rows — physiologically implausible as a literal serum cholesterol measurement and therefore an unresolved structural-missingness/coding question, not a proven patient value or a license to recode. Only eight negatives make specificity, calibration-in-the-large and calibration-slope estimates highly imprecise for many plausible locked-model estimands. The Riley inputs are not frozen, so exact adequacy cannot be claimed; the structural precision concern is nonetheless decisive for a *primary* validation role absent a new protocol and evidence.

**Recommendation — `NO_GO` for a primary locked external validation on current evidence; `HOLD` for a descriptive source-suitability or explicitly limited stress analysis only.** A documented NO-GO is a legitimate result and must not be relabelled “real evaluation completed.”

**Required decisions:** (1) owner/version reconciliation of 123 vs 143 and Zurich/Basel attribution; (2) clinical ruling on `chol=0` and all missingness/abstention rules; (3) statistician's written precision disposition; (4) explicit reviewer decision if the only permissible output is descriptive. No model fitting or utilization of the eight negatives for tuning is authorized.

## 5. Consolidated role matrix

| Source | Independence from Cleveland model | Target compatibility | Five-field availability/timing | Precision feasibility | Primary disposition |
|---|---|---|---|---|---|
| Cleveland `DA-A2` | Development source, not its own external test | Source-defined `>50%`, exact 50 unresolved | Definitions E1; timing unverified | Historical n=303/139 positive | `GO_REVIEW` source clarification only |
| Hungary `DA-A2` | Distinct site supported; patient overlap unresolved | Same UCI-45 wording; raw→processed binary recoding needs ruling | E2 292/294 observed; timing unverified | 294/106 positive; no frozen estimand | `GO_REVIEW` admissibility; execution `HOLD` |
| Statlog `DA-B2` | Suspect duplicate; independence not established | 1/2 target, no threshold evidence | Mirrored fields; `ca` leakage; no timing | n=270; role invalid while overlap open | `NO_GO` independent; audit-only `GO_REVIEW` |
| UCI-411 `DA-B1` | Same 303 people as UCI-412 | ≥50% and artery-defined outcome | Added artery fields are outcome components | No added subjects | `NO_GO` independent |
| VA Long Beach | Distinct site supported; overlap unresolved | Source wording compatible; exact 50 open | Many missing E2 cells; timing unknown | n=200/149 positive; policy needed | `HOLD` limited stress role |
| Switzerland | Distinct site supported; overlap unresolved | Source wording compatible; subset mismatch | Severe/mysterious missingness E2 | 8 negatives; precision concern | `NO_GO` primary validation; descriptive `HOLD` |

No row in this matrix is a permission to train, evaluate, pool or deploy. Different sites, matching column names, published accuracy, and CC BY 4.0 availability are each insufficient for an independence or clinical-validity claim.

## 6. Explicit decision requirements and current gates

| Gate / decision | Owner | Current state | Required evidence before change |
|---|---|---|---|
| Q-01 five-field meaning and timing | Clinical/research reviewer + data owner | `CONDITIONAL_SOURCE_REVIEW_REQUIRED`; `PENDING` | Original records/codebook with dated, field-level pre-reference timing; reviewed acquisition contract |
| Q-02 `>50%` vs `≥50%` and exact 50 | Endpoint adjudicator | `SOURCE_WORDING_RESOLVED_EQUIVALENCE_UNRESOLVED`; `PENDING` | Source-specific threshold ruling; no silent cross-family harmonization |
| Q-09 UCI-411 independence | Scientific reviewer | `UNSUITABLE_FOR_THIS_EXTERNAL_CLAIM` | Owner/version reconciliation and overlap audit; never count 606 patients |
| Q-10 Hungary eligibility | Named clinical/scientific reviewer | `UNRESOLVED_SCIENTIFIC_HOLD`; `DEFER` default | Independence, endpoint, five-field, missingness, precision and rights bundle |
| Q-11 Hungary one-shot freeze | Maintainer + independent reviewer + local operator | `UNRESOLVED_SCIENTIFIC_HOLD`; `HOLD` | Separately approved frozen model SHA, locked protocol, one-shot ledger, local authorization; no test-set tuning |
| Q-12 Statlog overlap | Source-donor/auditor + reviewer | `CONDITIONAL_SOURCE_REVIEW_REQUIRED` | Authorized aggregate exact/near-duplicate review and donor lineage; otherwise exclusion |
| Q-13 VA/Switzerland | Statistician + clinical reviewer | `CONDITIONAL_SOURCE_REVIEW_REQUIRED` | Source-specific role, missingness/abstention, precision decision and explicit NO-GO if infeasible |
| P-1 final scientific target/protocol | Research lead + supervisor | **PENDING** | Separate human approval; this report does not reopen or close it |
| P-3 supervisor protocol approval | Supervisor | **CLOSED** | Separate frozen protocol and human sign-off; no external-validation claim without it |
| P-5 external-validation/clinical claim | Named gate owner | **NOT MADE — prohibited** | Executed, approved external study under the frozen protocol; not produced here |

## 7. Reproducible read-only validation

From the repository root at this exact tree:

```bash
python scripts/validate_issue107_source_audit.py
python -m pytest tests/audit/test_issue107_source_audit.py -q
git diff --check
```

The validator uses only the Python standard library. It opens the two deliverables plus the pinned canonical register, recomputes SHA-256 digests, checks the seven canonical statuses against the register, verifies the six dataset entries, source catalog and question links, and asserts the no-data/no-approval flags. It prints a deterministic JSON result with `status: PASS` or `FAIL`, writes nothing, opens no dataset, and makes no network request. A non-zero exit means the report or companion has drifted and must be reviewed rather than “fixed” by weakening checks.

The validator's own SHA-256 and this report's SHA-256 are recorded in the JSON companion. Any edit to either deliverable requires a reviewed regeneration of those hashes; the canonical register hash must remain `9e3f5f9895f894fb603f90435a69d7b174b24bff291254e208cd7c2201f612d4`. The repo's `scripts/verify_sources.py` source-integrity check remains the authority for tracked source materials and is separate from this documentation validator.

## 8. What this report explicitly does not do

- It does not complete, approve or reinterpret Issue #107; it implements the stated fallback scope only.
- It does not download data, read patient rows, inspect local reports, train a model, or inspect locked external outcomes.
- It does not modify `AGENTS.md`, `docs/DECISIONS.md`, the canonical register, Gate DA/PT protocols, D-046/D-047/D-048, P-1/P-3/P-5, the R1 mapping, UCI-412 dictionaries, frozen hashes, application code, backend providers, or CI.
- It does not claim a real Cleveland→Hungary evaluation, an independent external validation, a clinical probability, a publication-ready result, supervisor/ethics approval, or a dataset reuse right beyond the publicly displayed license.
- It does not promote any `PENDING` human disposition: all remain pending, and `HOLD`/`NO_GO` dispositions are provisional review recommendations, not final human decisions.

## 9. navigation

- [Master AI Completion Plan](../CARDIOASSIST_AI_MASTER_COMPLETION_PLAN.md)
- [Consolidated RH-02/RH-03 handoff](RH02_RH03_CONSOLIDATED_RESEARCH_HANDOFF_2026_11_19.md)
- [Canonical 16-question register](RH02_SOURCE_QUESTION_REGISTER_2026_11_19.json)
- [Completed UCI-412/AngioCAD evidence investigation — not repeated here](RH02_UCI412_ANGIOCAD_SCIENTIFIC_EVIDENCE_INVESTIGATION_2026_11_19.md)
- [Hungary conditional protocol draft](../gate-pt/07_m2f_hungary_scientific_decision_and_conditional_protocol.md)
- [Cross-site feasibility handoff](../gate-da/17_cross_site_feasibility_audit_handoff.md)

**Exit rule:** the scientific result of this pass is a source-evidence and decision-requirement map. Real approval remains a named human act; a documentation PR, passing validator, or green CI cannot supply it.
