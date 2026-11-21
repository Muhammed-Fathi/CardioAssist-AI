# RH-03 / AI-12.2 — Round 2 public-source triangulation and claim-resolution worklist

**Date:** 2026-11-21  
**Repository baseline:** `4aeb4f33ee95d6f09311c10dc1b7829da1bb5c2f`  
**Scope:** Original dataset metadata, original-author articles, biostatistical reporting/evaluation papers, professional-society clinical guidance and professional educational videos/webinars. Public HTML/metadata only. **No datasets downloaded. No private experiment accessed. No videos watched or transcribed.**  
**Decision:** New sources give stronger **context and source-defined metadata**, but **do not upgrade** historical experiment results or unresolved individual-level data chronology. Scientific reviewer decisions remain PENDING.

This is a **new evidence-layer addendum**, not a rewrite of the previous 22-source RH-02 investigation, the formal 28-row RH-03 audit, canonical Q-01–Q-16 register or the 17-section manuscript. The companion JSON captures all 28 claims, their original audit states and precise next action. The existing audit stays **9 limited source-text matches, 19 NOT_VERIFIABLE, zero established mismatches**; 10 named reviewer actions remain PENDING. Do not report these 19 as solved by online reading.

## A. Evidence hierarchy: use all credible *types*, not equal weights

1. **Original dataset owners/donors and original study documents:** establish official field labels, nominal population/endpoint and what authors actually report. **Only original case-record forms, lineage and appropriately authorized original records can establish unreported measurement chronology or data provenance.**
2. **Original peer-reviewed methods/statistical publications:** justify scientific methods and limitations (validation, sample adequacy, calibration, risk of bias); they do **not** reproduce our old result files.
3. **Professional medical associations and university courses:** help adjudicate clinical background and appropriate workflow, but cannot authorize access to UCI patient data or overwrite original dataset labels.
4. **Official professional webinar / YouTube video pages and educational talks:** good for learning explanations and preparing the viva; their **page metadata is not a watched video or verified transcript**, and no doctor video independently proves an old dataset's exact column semantics or per-patient timing.
5. **Secondary blogs/tutorials/forum opinions:** discovery only; cite stronger original sources for any substantive manuscript claim.

**Scope/legal boundary:** ESC website explicitly says use of its guideline content in software/tools/algorithms requires a formal license. We use the publicly accessible **high-level clinical context** to distinguish tasks; **do not copy any ESC coefficient, formula, algorithm or calculator into the CardioAssist code/UI**. UCI page license language also does not override this repository's frozen protocol and authorization gates.

## B. Primary records checked and what they actually establish

| Source and issuer | Exact observable support | Important unverified item / response |
| --- | --- | --- |
| **[UCI-45 Cleveland original repository](https://archive.ics.uci.edu/dataset/45/heart)** | Four named data sites; processed Cleveland **303**; `num=0` absent and `num=1–4` present. Expanded original dictionary documents `num=0` as **<50%** and `num=1` as **>50%**, without resolving an exact **50%** case. `trestbps` is on hospital admission (mmHg) | The webpage does **not** independently establish our **139/164** local class counts, every five-feature acquisition time relative to invasive reference, or D-047 model statistics. Preserve Q-01/Q-02 and no threshold harmonization |
| **[UCI-412 Z-Alizadeh Sani original repository](https://archive.ics.uci.edu/dataset/412/z+alizadeh+sani)** | **303** case records; owner-defined `CAD` if arterial narrowing **≥50%**; explanatory description names **54 features** over demographic, clinical/examination, ECG, laboratory/echo groups | Web variable listing and count do not certify the delivered version/header (known 54/55/56 reconciliation issue), local **216/87** aggregate, **0/16** exact pre-cath times, BP systolic/diastolic meaning, PR units, six binary directions or chest-pain co-occurrences. Q-03 primary metadata resolved only; Q-04/05/06/07/08 remain as originally registered |
| **[UCI-411 original extension](https://archive.ics.uci.edu/dataset/411/extention+of+z+alizadeh+sani+dataset)** | Original UCI labels this an extension of the **303** records, with angiography-linked **LAD/LCX/RCA/Cath** additions; owner notes those reference features must be handled explicitly for their own classification tasks | Same patient source **not independent transport data**; angiography-derived columns would be leakage for a pre-angiography predictor. Keep blocked independent-external and do not translate owner's alternative task advice into our route |
| **[Alizadehsani et al., original 2013 paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC4253773/)** | Original coauthor paper describes 303 individuals referred for chest pain, laboratory and echo data for **artery-specific stenosis** analysis, and an intended reduction in unnecessary angiography | An author's high-level study objective does **not** prove each of the current delivered 16 columns has a verified timestamp before reference angiography; no owner-certified BP/PR or chest-pain encoding per the local 16-panel. The paper's artery-wise Bagging/C4.5 results are not CardioAssist M3a LR/RF results |
| **[Riley et al., BMJ part 2](https://www.bmj.com/content/384/bmj-2023-074820)** and **[part 3](https://www.bmj.com/content/384/bmj-2023-074821)** | External validation checks actual independent data, discrimination, calibration and overall fit; precision-based sample sizing should be designed using anticipated characteristics rather than universal minimum sample rules | No permission to convert repeated inner/outer CV into independent validation, and no external paper confirms the project's computed **382/459/315** numbers absent the original assumed parameters/worksheet |

**Direct correction hazard identified:** UCI-45's original expanded dictionary has distinct literal inequalities around 50%, while UCI-412's owner page explicitly uses `≥50%`. The manuscript currently keeps this distinction correctly. Do **not** erase it to present a common angiographic label.

## C. Reporting / bias appraisal sources — use to improve the manuscript, not certify it

| Source | Appropriate manuscript role | What it cannot prove |
| --- | --- | --- |
| **[TRIPOD+AI official checklist (27 items)](https://www.tripod-statement.org/content_resources_tx/downloads/)**; [EQUATOR entry](https://equator-network.org/reporting-guidelines/tripod-ai/) | FR-06 Methods; FR-07/08 Results; FR-10 uncertainty; FR-14 reproducibility; FR-15 bias; FR-17 appendices. Create an item-to-section **reporting coverage map** in next stage | Compliance/clinical quality cannot be marked PASS without a real item-by-item check; **TRIPOD-LLM** does not replace TRIPOD+AI for our tabular model |
| **[PROBAST+AI, BMJ 2025](https://www.bmj.com/content/388/bmj-2024-082505)** | Distinguish model-development process quality from internal/external **evaluation** risk of bias and applicability across **participants, predictors, outcome, analysis** | No item-level appraisal yet, no blanket low-risk rating; does not validate source-specific timing or potential leakage |
| **[ESC 2024 CCS guidelines page](https://www.escardio.org/guidelines/clinical-practice-guidelines/all-esc-practice-guidelines/chronic-coronary-syndromes)** | Compare the **real-world clinical diagnostic process** to this project's narrower *historical, retrospective research classification*; avoid implying clinical likelihood calculator equivalence | Do **not** import clinical coefficients/algorithms; website expressly requires formal license for inclusion/transformation of guideline content in software tools |

**Important:** The original D-047 and UCI-412 M3a AUROC/Brier/calibration values are **historical internal aggregates**. Nothing in these sources recomputes those numbers, proves their protected provenance, supplies inferential CIs, or establishes a cross-cohort winner.

## D. Medical teaching, doctor videos, and YouTube — admissible as *education only*

| Source | What we checked / could use | Why it remains non-adjudicative |
| --- | --- | --- |
| **[ESC Congress 2024 — Stepwise approach to suspected chronic coronary syndromes](https://esc365.escardio.org/presentation/279880)** | ESC lists a lecture by **Dr Francisco Javier Rossello**, published 31 August 2024, with a video resource. Page shows **sign-in required** to view. Good for explaining physician diagnostic workup at a viva | The actual video content/slides were **not accessed or watched**. This cannot establish field-level UCI acquisition times or licensing for a clinical decision algorithm |
| **[American College of Cardiology — AI in Clinical Practice webinar, 2025](https://www.acc.org/Education-and-Meetings/Meetings/Meeting-Items/2025/07/01/Webinar-AI-in-Clinical-Practice)** | ACC provides an **embedded YouTube recording link** and describes a TRIPOD+AI reporting session with **Gary J. Collins** and physician presenters. Useful for learning how to explain reporting quality | Webinar metadata only verified; recording **not watched/transcribed**; it does not independently verify project experiments or medical validity |
| **[ACC clinical interpretation of ESC 2024 guideline](https://www.acc.org/latest-in-cardiology/ten-points-to-remember/2024/09/01/15/01/2024-esc-guidelines-for-ccs-esc-2024)** | Professional medical synthesis for clinical presentation/differential and general intended-use wording | Secondary interpretation, not a donor codebook, not a patient-row acquisition log and not permission to copy guideline equations |

Videos are **not being cited as if they were full-text empirical evidence**. If an accessible recording plus a transcript is actually reviewed later, quote only its checkable *educational* statements with timestamp, institution and speaker; still use original owner sources for source-specific claims.

## E. RH-03 claim-by-claim next pass: high-value order

Full 28-claim triage with one next action each lives in [JSON companion](RH03_EXTERNAL_SOURCE_TRIANGULATION_2026_11_21.json). Reconcile every edit against original `RH03_AI12_2_AUDIT_MATRIX_2026_11_19.json`.

| Work package | Claims / related issues | Executable now | Boundary |
| --- | --- | --- | --- |
| **P1 — source-defined endpoint & semantics** | CL-001, CL-011, CL-016, CL-017, CL-027; Q-01–09 | Cross-check exact original UCI descriptions and original author papers; update explanatory citation/linkage where demonstrably correct; distinguish supported `SOURCE_DEFINED` from unknown `OWNER_VERIFIED_PRE_REFERENCE_TIME` | No change to 16/16 timing hold or conditional feature eligibility |
| **P2 — historical numerics audit** | CL-002–015, REVIEW-02–05 | Build one precise source-table-to-manuscript discrepancy sheet for D-047 and M3a, including AUROC/AP/Brier/selection/calibration. Tag archived records as `HISTORICAL_MAINTAINER_REPORTED`, SD not CI; authorized human may later inspect original protected aggregate | No independent run means do not label original protected metrics `INDEPENDENTLY_REPRODUCED` |
| **P3 — engineering/handoff alignment** | CL-019–026, REVIEW-06/09 | Use current merged RH-05 report: exact Windows **2909 passed, 3 OS-specific skips**, native Win32 **8/8**, source integrity. Record exact studied code SHA `64f34e4...` and docs-only merge `4aeb4f3...`. Link Linux cross-OS exact-source **09b8954...** comparison with unchanged AI/research/tests trees | This does not confer medical or academic reviewer signoff; do not relabel Linux report as generated at docs merge SHA |
| **P4 — report transparency** | CL-027–028, REVIEW-04/05/07/08/10 | Create TRIPOD+AI **27-item-to-FR** draft crosswalk, PROBAST+AI scope-and-missing-evidence table and 10-action reviewer packet | Actual academic approval remains with identified humans; no implied low-risk-of-bias judgment or reviewer signature |

**Efficient workflow:** do not reopen already closed RH-05 just to add citations; do not repeat the 75-minute Windows suite for docs-only change. Work on a separate reviewed RH-03 PR, run the existing manuscript integrity validator after **any** edits to line-anchored 17-FR content, then obtain original scientific and academic reviewer decisions for what cannot be established automatically. A source discrepancy merits a narrow follow-up investigation, not a new model.

## F. Question and reviewer status safeguards

The **16** Q-01–Q-16 research questions are reproduced by ID and unchanged canonical status in JSON; the **10** REVIEW-01–REVIEW-10 actions remain `PENDING`. Owner source outreach in Issue #102 is still **UNSENT**, and is optional for this engineering-only package.

In particular, a potentially source-verified `≥50%` UCI-412 label is not a certified per-person chronology; potential BP units from a secondary paper are not owner-certified field semantics; a new peer-reviewed paper is not a missing external cohort; and a successful full software suite is not the same as a statistically valid, clinically reviewed model.

## G. Recommended next implementation PR (narrow, additive)

**Scope:** RH-03 manuscript *alignment* after this evidence addendum: (1) add the RH-05 evidence to FR-08, FR-14, FR-17; (2) create genuine claim/source numeric comparison table, not a blanket rewrite; (3) add TRIPOD+AI reporting-item map and PROBAST+AI applicability prompts; (4) update the existing 17-FR anchored audit matrix and its validator tests together after any manuscript line shifts; (5) retain scientific holds, all unresolved questions and `NOT_PERFORMED` real studies.

**Acceptance:** 28 claim IDs still unique, all 17 FR intact, all original source Git blobs preserved and verified, tests reproducible in ordinary Python without patient data, no invented human reviews, and GitHub CI green. Report factual outcomes and remaining limits accurately.

## Related canonical records

- [Issue #103 RH-03](https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/103); [prior independent audit](RH03_AI12_2_INDEPENDENT_AUDIT_2026_11_19.md); [28-claim matrix](RH03_AI12_2_AUDIT_MATRIX_2026_11_19.json).
- [16-question register](RH02_SOURCE_QUESTION_REGISTER_2026_11_19.json); [22-source pre-existing author-literature packet](RH02_UCI412_ANGIOCAD_SCIENTIFIC_EVIDENCE_INVESTIGATION_2026_11_19.md).
- [Merged RH-05 acceptance report](RH05_INDEPENDENT_ACCEPTANCE_REVIEW_2026_11_20.md); [manifest](RH05_ACCEPTANCE_MANIFEST_2026_11_20.json); closed engineering [Issue #121](https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/121).

**Disposition:** RESEARCH TRIANGULATION EVIDENCE PREPARED FOR REVIEW, **not** RH-03 completion, not clinical validation, not new real study execution, and not an acceptance of the historical numerical claims.
