# RH-03 — TRIPOD+AI and PROBAST+AI research-manuscript reporting gap crosswalk (2026-11-21)

**Disposition:** item-level **draft mapping and gap register**, NOT a TRIPOD+AI compliance certificate, PROBAST+AI low-risk judgment, clinical sign-off or final scientific acceptance. The accompanying [machine-readable crosswalk](RH03_REPORTING_CROSSWALK_2026_11_21.json) records each item and gap. Original public frameworks: [TRIPOD+AI (27 main items, 52 subitems)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11019967/) and [PROBAST+AI (four domains; 16 development-quality and 18 evaluation-bias signalling questions plus six applicability items)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11931409/).

**Method and scope:** report-coverage inventory against [FR-01–FR-17](AI12_2_GRADUATION_RESEARCH_MANUSCRIPT_DRAFT_2026_11_19.md), NOT source-level reexecution of protected models, patient data, clinical assessment, or a completed full reporting checklist. Topic names below are paraphrased descriptors of each numbered TRIPOD+AI main item; every subitem requires separate final human checklist completion. `DRAFT_MAPPED` means location identified, NOT verified completeness. `PARTIAL` means known missing supporting detail. `INFORMATION_GAP` and `NOT_PERFORMED` are explicitly non-passing states.

## TRIPOD+AI — all 27 main item groups

| Item | Checklist topic (paraphrased) | Manuscript location | Mapping status | Evidence gap/action |
|---|---|---|---|---|
| 1 | Title and research scope | FR-01 | `DRAFT_MAPPED` | Title identifies retrospective angiography-referenced CAD; final institution/title approval pending. |
| 2 | Structured abstract | FR-01 | `PARTIAL` | Narrative abstract present; final TRIPOD+AI for Abstracts 13-point separate checklist not signed off. |
| 3 | Background, intended users, inequity | FR-02, FR-03, FR-15 | `PARTIAL` | Background and target cohort described; demographic inequities and care pathway impact remain unassessed (especially subitem 3c). |
| 4 | Study objectives | FR-01, FR-02 | `DRAFT_MAPPED` | Cross-sectional exploratory objectives stated; final academic review pending. |
| 5 | Data source, sampling dates | FR-04 | `PARTIAL` | Sources and roles mapped; original recruitment dates, representativeness and chronology incomplete (5b). |
| 6 | Participants and setting | FR-04 | `PARTIAL` | Referred cohorts described; full eligibility/treatment details and site-specific sampling provenance unavailable. |
| 7 | Data preparation and QC | FR-06 | `PARTIAL` | Fold-contained preprocessing described; demographic-group QC and protected-run recheck not independently demonstrated. |
| 8 | Outcome definition and assessment | FR-02, FR-04 | `PARTIAL` | Cleveland >50% and UCI-412 ≥50% retained; exact 50% boundary and blinding/assessor metadata unresolved. |
| 9 | Predictor choice and measurement | FR-05 | `PARTIAL` | Five-field and sixteen-field contracts mapped; 0/16 UCI-412 pre-angiography owner-verified timing, subjective assessor metadata unavailable. |
| 10 | Sample size justification | FR-10 | `PARTIAL` | 303 cases per cohort, historical adequacy calculations cited; selected precision criteria not met and R²-dependent items not assessed. |
| 11 | Missing-data handling | FR-06 | `PARTIAL` | Research preprocessing policy described; original protected-data missingness decisions require source/run attestation. |
| 12 | Analytical methods and validation | FR-06, FR-07, FR-10 | `PARTIAL` | Historical nested CV/preprocessing and estimands described; protected run outputs and cluster heterogeneity not newly verified, no external evaluation. |
| 13 | Class imbalance approach | FR-06, FR-07 | `INFORMATION_GAP` | Class fractions reported; complete original handling/recalibration approach not independently checked. |
| 14 | Fairness methods | FR-15 | `NOT_PERFORMED` | No source-supported subgroup fairness experiment; no fairness claim. |
| 15 | Model outputs and thresholds | FR-06, FR-08 | `PARTIAL` | Exploratory threshold and synthetic score separation documented; no clinically validated individual decision threshold. |
| 16 | Development/evaluation data differences | FR-04, FR-07 | `PARTIAL` | Source-specific cohorts and no-pooling guarded; real independent external evaluation NOT_PERFORMED. |
| 17 | Ethical review and consent | FR-15 | `INFORMATION_GAP` | No invented institution, IRB approval, consent or waiver; historical source rights and any required approvals must be documented by authorized humans. |
| 18 | Funding, COI, protocol, registration, sharing | FR-17 | `PARTIAL` | Repository provenance is given, but author declarations, financing, conflicts, registration and protected-data access terms remain to be supplied. |
| 19 | Patient and public involvement | FR-15 | `INFORMATION_GAP` | PPI involvement or explicit none declaration requires author confirmation; not invented. |
| 20 | Participant flow and baseline characteristics | FR-04, FR-07 | `PARTIAL` | 303 and historical class counts per source recorded; complete flow, missingness by characteristic and subgroup distribution not available. |
| 21 | Sample size per analytic stage | FR-06, FR-07 | `PARTIAL` | Nested folds/repeats described; complete original fold-level participant and event counts need archived provenance. |
| 22 | Full prediction-model specification | FR-06, FR-13 | `PARTIAL` | Algorithms and safe software contracts present; protected fitted artifact not public/servable; no export of patient-derived parameters. |
| 23 | Performance with uncertainty/subgroups | FR-07, FR-10 | `INFORMATION_GAP` | Historical dependent-repeat SD is not CI; no independent interval, subgroup performance or real external validation. |
| 24 | Model updating results | FR-10, FR-12 | `NOT_PERFORMED` | No real external model updating or recalibration study performed; synthetic rehearsal must not be relabeled. |
| 25 | Overall interpretation including fairness | FR-15, FR-16 | `PARTIAL` | Within-source results and limits interpreted; fairness remains unassessed and final scientific reviewer pending. |
| 26 | Limitations and transportability | FR-10, FR-15, FR-16 | `DRAFT_MAPPED` | Sources, target differences, 303-person sample, chronology, no external validity and calibration constraints explicitly discussed. |
| 27 | Input usability and next research steps | FR-13, FR-16, FR-17 | `PARTIAL` | Fail-closed synthetic handling described; no clinical workflow or real-patient user expertise validation. |

**Important subitem constraints:** TRIPOD+AI's 52 subitems include separate detail for sampling dates, predictor chronology, fairness, assessor/blinding, subgroups, model specification, calibration/discrimination with intervals, ethics, funding/COI, open science and public involvement. This main-item crosswalk is a starting inventory, **not** a replacement for the original 52-subitem checklist and not a claim of its completion. Subitem-level completion and actual manuscript page numbers remain a reviewer action.

## PROBAST+AI — domain concerns, WITHOUT assigning a risk rating

| Domain | Relevant FR chapters | Evidence issue | Development quality / evaluation risk |
|---|---|---|---|
| participants and data sources | FR-02, FR-04, FR-15 | Historical referred 303-person source cohorts lack fully verified recruitment/selection and representative use-population context. | `NOT_ASSESSED` / `NOT_ASSESSED` |
| predictors | FR-05, FR-15 | 16/16 UCI-412 original-field pre-reference timing unverified; avoid using angiography-derived features as predictors. | `NOT_ASSESSED` / `NOT_ASSESSED` |
| outcome | FR-02, FR-04 | Original source target boundaries differ (>50% versus ≥50%); adjudication and exact boundary need source-specific review. | `NOT_ASSESSED` / `NOT_ASSESSED` |
| analysis | FR-06, FR-07, FR-10, FR-15 | Repeat-CV descriptive SDs not confidence intervals; complete original-run audit, precision, sample size and generalization remain unverified. | `NOT_ASSESSED` / `NOT_ASSESSED` |

PROBAST+AI's **development-quality** and **model-evaluation risk-of-bias** assessments are distinct workflows. This register does not answer its 34 signalling questions or six applicability items and therefore makes **no overall or domain risk-of-bias, quality, or applicability certification**. The outcome- and predictor-timing uncertainties are particularly material. Its analysis domain is not an independent applicability domain; no artificial analysis-domain applicability score has been added.

## Source-to-claim and reproducibility rules

- RH-03 pinned independent audit remains **28 claims**: **9 limited source-text transcription matches**, **19 NOT_VERIFIABLE**, zero established mismatches; **16** registered research questions and **10 PENDING** human review actions stay unchanged. Original source excerpt comparison and numeric recomputation are different kinds of evidence.
- Cleveland DA-A2 historical 303 (139/164), D-047 primary AUROC **0.8271 ± 0.0097**; UCI-412 historical 303 (216/87), M3a primary AUROC **0.9107 ± 0.0071**. These are maintainer-reported exploratory aggregate SDs across four dependent repeated-CV runs, **not verified clinical probabilities, confidence intervals, or cross-cohort rankings**.
- Original UCI-45 label source describes `>50%`; UCI-412 original describes `≥50%`; the exact boundary is not silently harmonized. No owner-certified timestamp evidence has established pre-angiography availability of the UCI-412 16-field panel.
- [RH-05 Windows/security acceptance](RH05_INDEPENDENT_ACCEPTANCE_REVIEW_2026_11_20.md) is closed as engineering evidence by [Issue #121](https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/121). Its final Windows test SHA is `64f34e4cb8580ced461237ffa46ba0a91e8fc1c5`; reported full Windows **2909 passed / 3 skipped**, NTFS **8/8**. Its exact-source Linux/Windows synthetic comparison uses the DIFFERENT `09b895423171eff7569fc49dd8ceac7dfb0d43c6` and is behavioral match, not byte equality. Do not reattribute those runs to this documentation PR.
- Merged [RD-01–RD-10 decisions](RH06_EVIDENCE_BOUNDED_RESEARCH_PROTOTYPE_DESIGN_DECISIONS_2026_11_19.md) keep AI-9.2/AI-10.2 real studies **NO-GO for current prototype scope**, while permitting completion of the research-only demonstrator without inventing approvals. Research backend remains `MOCK_SYNTHETIC` only. This document changes no real model or medical serving permission.

## Outstanding owner/reviewer work

Finish the original 52-subitem TRIPOD+AI worksheet with verified page/section references and explicit `NOT_REPORTED` where evidence is absent; perform any authorized original-output source attestation for numeric tables; complete a genuine structured PROBAST+AI application only if required and feasible; preserve the 10 human review actions and 16 source questions without state promotion. Once accepted, proceed to RH-07 independent review and RH-08 evidence/release freeze. **No final manuscript or clinical acceptance is declared here.**
