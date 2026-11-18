# RH-01 — Source-Pinned Claim Lineage & AI-12.2 Scientific Report Intake

**Prepared:** 2026-11-19  
**Source read:** `main` at `17643b9b94170ef73848c7ff911994b2b8c0168f` (after PR #94 merge).  
**Evidence level:** read-only GitHub original-document/code verification; **not** a new patient-data analysis, a local reproduction of protected results, scientific approval, or final RH-01 acceptance.  
**Canonical companion:** [28-entry claim/source/evidence JSON](RH01_CLAIM_EVIDENCE_INDEX_2026_11_19.json) — use claim IDs `CL-001` … `CL-028` in the scientific report.  
**Predecessor:** [RH-01 25-component inventory and 10-gap matrix](RH01_SOURCE_EVIDENCE_AND_GAP_MATRIX_2026_11_19.md).  
**Milestone tracking:** [RH status/evidence tracker](AI_RESEARCH_COMPLETION_TRACKER_2026_11_19.json).

## 1. Progress verified after PR #94

- PR [#94](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/94) **MERGED** at `17643b9b94170ef73848c7ff911994b2b8c0168f` (head `51b0f2f99e8a449398789065150236cc1992d877`), with **all four GitHub Actions workflows completed SUCCESS** on that head. These are GitHub observations, not newly run Windows tests.
- Existing first-pass inventory comprises 25 research/code/source components and 10 explicitly classified gaps (with owners); completion remains **RH-01 IN_PROGRESS** until a separate reviewed closure proves lineage coverage and outstanding checks.
- The new **28-entry machine-readable evidence register** pins individual claim IDs to **original path, exact blob SHA, relevant section, evidence grade, intended report chapter/table, reviewer-needed status and mandatory limitation**.
- Code inspection establishes presence and named tests for research routes, offline four-status facade, source catalog, SHAP/LIME, synthetic labs and locked-site evaluation, and mock-only backend. No new code correctness, security or medical performance experiment was run during this audit.

## 2. Report-ready scientific facts — with strict interpretation

| Topic / claim IDs | Historical source evidence reported in repository | Mandatory interpretation |
|---|---|---|
| **Cleveland D-047 (CL-002…CL-009)** | One historical UCI-45 Cleveland cohort **303** (139 positive, 164 negative); five source input fields, eight reference-coded LR slopes; repeated nested CV outer 5×4 / inner 5; primary selected procedure AUROC **0.8271 ± 0.0097**; AUPRC **0.7712 ± 0.0193**; Brier **0.1671 ± 0.0049**; LR selected **19/20** outer folds | Aggregates are **maintainer-reported internal exploratory**, from [original review doc 04](../gate-pt/04_d047_first_internal_results_REVIEW_DRAFT.md) §§2–5. The ± is **population SD across four dependent CV repeats on the same 303 people**; not a confidence interval, standard error or external validation. Exploratory 0.5 threshold not a clinical decision threshold. |
| **Cleveland controls / calibration (CL-008…CL-010)** | Three shuffled-label controls had mean AUROC **0.4882**; selected-procedure descriptive OOF slope **0.8980** (4/4 estimable) and CITL **−0.0212**; LR and RF each 3/4 estimable slopes. Riley outcome-proportion criterion at δ=0.05 requires **382** participants; additional p=8 MAPE planning criterion requires **459** | Negative control is a smoke test **without** formal permutation p-value; some slopes are `UNSTABLE_OR_NOT_ESTIMABLE` and cannot be interpreted as zero. Calibration does not establish reliability for medical risk percentages. Riley numbers depend on the stated assumptions/tolerances, not a general blanket eligibility verdict. [Sample-size review](../gate-pt/05_m2e1_sample_size_research_ADEQUACY_REVIEW_DRAFT.md). |
| **UCI-412 M3a (CL-011…CL-015)** | Another historical source-specific **303** participants (216 `Cad`, 87 `Normal`); 16 fields, outer 5×4 / inner 5; LR/inner-selected AUROC **0.9107 ± 0.0071**, AUPRC **0.9504 ± 0.0077**, Brier **0.0995 ± 0.0043**; LR chosen **20/20** outer folds; descriptive LR calibration slope **1.0891** (4/4) and CITL **0.0206**; R²-independent outcome-proportion criterion needs **315** at stated precision | From [original synthesis doc 11](../gate-pt/11_two_dataset_scientific_evidence_synthesis_REVIEW_DRAFT.md) §§2/4–5. **Historical internal exploratory aggregates**, not a newly verified run. All ± are dependent-repeat population SD, no population CI. Reliability-bin data/free calibration intercepts not supplied. **Do not compare 0.9107 vs 0.8271 to select a model across populations.** |
| **UCI-412 source restrictions (CL-016/017)** | [AI-8R source admissibility review](../ai8r/SOURCE_ADMISSIBILITY.md) documents **zero of 16 fields with owner-verified pre-angiography timestamps**, unresolved BP/PR semantics, binary coding direction, chest-pain feature definitions; UCI-411 shares the same 303 people | `SCIENTIFIC_HOLD` on newly proposed real-data UCI-412 route/labs study. Coding plausibility or a source paper alone does not establish pre-index measurement. UCI-411 is not independent external validation. |
| **Hungary / external (CL-018/020)** | Hungary is a **conditional** candidate for one-shot frozen Cleveland transport evaluation; [original M2f review](../gate-pt/07_m2f_hungary_scientific_decision_and_conditional_protocol.md) reports historical processed sample **294** but unresolved source/individual independence, target mapping, timing, feature compatibility, missingness and precision | AI-10.1 is only an **invented-cohort locked-site software rehearsal**. The real Hungary assessment is **NOT EXECUTED** and source rights/approval and a prespecified protocol are separately required. No real external-validation result is currently substantiated. |
| **AI-9/11/12 engineering (CL-019, CL-021…CL-026)** | AI-9.1 synthetic paired labs comparison; AI-11.1 four-status offline synthetic facade; AI-11.2 descriptive five-slot catalog; AI-12.1 synthetic eight-stage demo; genuine offline SHAP and LIME with fidelity and scale rules; backend only `MOCK_SYNTHETIC` | Existing engineering software evidence is **not** clinical model performance. The research facade is not the running real-model provider. A signed synthetic bundle and mock XAI do not prove a patient-ready prediction. |

All numbers above are **quoted from previous committed project reviews** and still need final academic claim review; no original protected row, report, held-out sample or patient-level explanation has been downloaded or evaluated in this RH-01 pass.

## 3. Evidence maturity versus original source authority

A **documented local research aggregate** is legitimate historical thesis material with provenance and caveats, but it is not an independently reproduced primary output. A **GitHub source file** proves a specific implementation exists, not that it passes on the final release machine. A **GitHub CI PASS** supports exact code-test workflows only, not patient-level accuracy or independent external calibration. An **unresolved source codebook** must not be upgraded to verified because the variable looks clinically reasonable. An **approval template** grants no access and a protected dataset cannot be committed just to improve traceability.

These rules are assigned in the claim JSON with `evidence_class`, `interpretation_limit` and `review_status=PENDING_HUMAN_SCIENTIFIC_REVIEW`.

## 4. Why the manuscript cannot be finalized from the two AUROCs alone

The scientific limitations that must remain visible throughout the completed manuscript are:

1. **Different target conventions**: UCI-45 `>50%` versus UCI-412 `≥50%`; exact boundary equivalence not established.
2. **Different predictor panels and cohorts**: no paired cross-source AUROC ranking or clinical population generalization.
3. **Dependence of repeats**: 4×303 fold predictions is not 1,212 independent people; no inference from ± SD.
4. **Source chronology/selection**: historical referred cohorts, unclear predictor timing, potential index-test reference biases.
5. **Calibration missingness**: not-estimable slopes, withheld bin values and joint free intercepts; do not claim calibrated patient probabilities.
6. **Sample-size/precision gap**: Riley adequacy under specified tolerances unmet or not assessed; external transport precision not established.
7. **Actual missing studies**: new clinically meaningful labs incremental value AI-9.2 and independent real external validation AI-10.2 have not been executed/authorized in their future scopes.
8. **Governance**: Gate PT P-3 CLOSED and patient-facing real serving prohibited; no fictional supervisor signoff.

## 5. Explicit execution intake for next independent phases

### RH-02 — source evidence resolution

Prepare a **question–owner–citation–decision** table for: original UCI-412 acquisition timing, BP/PR definitions and units, six binary directions, chest-pain relations; UCI-45 time and target convention; Hungary processed-vs-raw reconciliation/overlap and precision; AngioCAD real available clinical/lab table and permissions; UCI-411 and Statlog independence. Each decision is `RESOLVED_PRIMARY`, `CONDITIONALLY_RESOLVABLE` or `HOLD/NO_GO`, with exact consequence for permitted research and scope. No new real local training, locked-set peek or forced clinical approval.

### RH-03 — first genuine AI-12.2 manuscript delivery

Draft complete, source-pinned **FR-01…FR-17** report chapters (not another outline). At minimum, FR-04/06/07/10 should initially use CL-001…CL-018 and their precise primary committed sources; FR-08/09/13/14 use CL-019…CL-026 with synthetic engineering and exact previous PR evidence; FR-11/12 must report the actual conditional study decisions, not fabricated results. All report tables/figures need versioned original source and reviewer grade. Final manuscript still requires actual independent review and final release-SHA checks; a report PR will not by itself close RH-08.

**Parallel order:** begin RH-02 metadata-only source review and RH-03 manuscript construction after the RH-01 claim index receives review. RH-01 remains IN_PROGRESS while assessing completeness and reviewer/claim validation. No code rewrite of already accepted models is implied by these documentation tasks.

## 6. Missing acceptance evidence (do NOT mark passed)

- Human review of the 28 registered claims, author/source meaning and report-ready phrasing.
- Claim ↔ code/test ↔ accepted exact PR/Windows report details for every eventual final report number/figure, including sources not yet examined at line depth.
- Original protected result verification only through approved sanitized local audit where permitted; not needed to fabricate or upload patient rows.
- Final native Windows/NTFS and synthetic E2E tests at the eventual release SHA (RH-05), not claimed here.
- Actual complete AI-12.2 manuscript and final academic QA/release review (RH-03/RH-07/RH-08).
- Source-specific GO/NO-GO and reviewer dispositions for real AI-9.2/10.2 (RH-02/RH-06).

**Current record:** source-code/document crosschecking and provenance tracking performed; final academic review, tests and patient-data experimental authorization **not performed**.