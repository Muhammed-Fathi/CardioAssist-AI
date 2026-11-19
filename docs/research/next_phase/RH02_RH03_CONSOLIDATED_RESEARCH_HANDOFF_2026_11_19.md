# CardioAssist AI — Research evidence, dataset-role decisions and next-action handoff

**Document:** \`CAI-RH02-RH03-HANDOFF-2026-11-19-v1\`  
**Captured:** 2026-11-19 (GitHub read-only verification + this documentation PR)  
**Current evidence baseline:** \`main\` at \`d8a0090b1827504532a2f938f200eedcfd86af28\` — merged PR #106  
**Status:** \`EVIDENCE_SNAPSHOT_FOR_REVIEW\` — **not** acceptance, source admission, a release, or an authorization  
**Companion:** [machine-readable snapshot](RH02_RH03_CONSOLIDATED_RESEARCH_HANDOFF_2026_11_19.json)  
**Next read-only source research:** [Issue #107](https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/107)

> **Precedence:** this is a **navigation and handoff snapshot**, not an amendment. \`AGENTS.md\`, \`docs/DECISIONS.md\`, the frozen Gate DA/PT protocols, the original 25-paper supervisor classifications, \`docs/research/ai_master_progress.json\`, \`RH02_SOURCE_QUESTION_REGISTER_2026_11_19.json\`, existing hash-bound authorizations and human review authority remain controlling. Any disagreement with those records must be resolved by a separately reviewed decision. Dates, CI and SHA here apply to the specified historical commits; do not assume they are the latest when reading this file later.

## 1. Executive status — what is actually finished

**Merged research documentation and verification records:**

| PR | Content verified | GitHub state verified on 2026-11-19 | Merge SHA | Exact PR-head workflows |
|---|---|---|---|---|
| [#101](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/101) | RH-02 AngioCAD/UCI-412 metadata and ownership/canonical question consistency | MERGED | \`9606b955b5c5906031ee88de704c3825b1f8b914\` | 4/4 success as previously verified |
| [#105](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/105) | RH-03 manuscript source claim-to-text audit; 17 FR sections, 28 CL entries, synthetic validator | MERGED | \`ab613baa3de5ec7c3442f4047b1a4cc56126d624\` | 4/4 success, independently rechecked |
| [#106](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/106) | RH-02 original-author UCI-412 and AngioCAD public literature research; 2013 RCM paper and 2015 inventor patent addenda | MERGED | \`d8a0090b1827504532a2f938f200eedcfd86af28\` | 4/4 success, independently rechecked |

**RH-03 scope:** [the full 17-chapter manuscript draft](AI12_2_GRADUATION_RESEARCH_MANUSCRIPT_DRAFT_2026_11_19.md) exists, and [RH-03 matrix](RH03_AI12_2_AUDIT_MATRIX_2026_11_19.json) has 28 claims: **9 limited source/report transcription matches**, **19 \`NOT_VERIFIABLE\`**, **0 established mismatches**. All **10 human reviewer actions remain PENDING**. SHA matching and transcription are **not** independent reproduction of archived experiments, scientific reviewer acceptance, or medically verified inference.

**RH-02 scope:** [original-source investigation](RH02_UCI412_ANGIOCAD_SCIENTIFIC_EVIDENCE_INVESTIGATION_2026_11_19.md) records **22 sources** and **11 findings**, including 2012 primary clinical/ECG tables, 2013 RCM primary laboratory/echo Tables 1–2, a distinct paywalled 2013 CMPB source, later original/coauthor publications, the **2015 abandoned inventor patent application**, UCI owner metadata, AngioCAD public metadata, and clearly labelled secondary evidence. The official [16-question register](RH02_SOURCE_QUESTION_REGISTER_2026_11_19.json) and every frozen scientific hold were **left unchanged**. No owner outreach was sent by this documentation effort.

**Milestone status discipline:** [the RH completion tracker](AI_RESEARCH_COMPLETION_TRACKER_2026_11_19.json) is a **historical tracking snapshot** that still says \`RH-01 IN_PROGRESS\`, \`RH-02 IN_PROGRESS\`, \`RH-03 IN_PROGRESS\`, \`RH-04/05/07/08 PLANNED\`, and \`RH-06 CONDITIONAL_GATED\`; it has **not been revised to reflect #105/#106 merges**. Those merges support narrower evidence tasks, **not automatic stage completion**. The tracker still has **15 final acceptance checks** listed as pending review. Only a future controlled reconciliation with named reviewer decisions can revise canonical status.

**Research-only target:** audited, reproducible and scientifically honest prototype/handoff with explicit evidence limitations. This is **not** \`CLINICALLY_VALIDATED\`, \`PATIENT_READY\`, real independent external validation, new real training permission or human scientific approval.

## 2. Eight-source role matrix — do not train on every dataset

| Source/cohort | Intended role | Current evidence / constraint | Next bounded step | Present real-study status |
|---|---|---|---|---|
| **UCI-45 Cleveland / DA-A2** | Existing five-field historical D-047 internal development baseline; candidate for future independent externally tested model | Historical **303** rows, **139 positive/164 negative**; repeated nested-CV source-reported AUROC **0.8271 ± 0.0097** (four **dependent repeats**). Original \`>50%\` versus UCI-412 \`>=50%\` label edge not harmonized. Five input semantics and pre-reference-test timing require claim-grade review. | [Issue #107](https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/107): Q-01/Q-02 official field, chronology and label audits; verify protected experiment **only under separate human-authorized local process**, not via cloud agent. | Historical internal exploratory evidence documented; no independent clinical external validity or current real serving. |
| **UCI-412 Z-Alizadeh Sani / DA-A1** | Separate 16-field historical M3a internal research route; potential **conditional** matched Clinical+Labs study | Historical **303** rows (216 Cad/87 Normal), source-reported AUROC **0.9107 ± 0.0071** over four dependent repeats. **0/16** field-level owner-verified pre-angiography timings; BP/PR, 0/1, chest-pain, 54/55/56 versions unresolved. Source-defined owner metadata \`>=50%\`; original-author \`>50%\` conflicts. | Preserve [#106 evidence](RH02_UCI412_ANGIOCAD_SCIENTIFIC_EVIDENCE_INVESTIGATION_2026_11_19.md); focused owner CRF/codebook request, or separately authorized **local headers-only** audit. **Do not repeat open-ended literature hunts.** | \`SCIENTIFIC_HOLD\` on **new** real model fit/panel extension; old M3a reported aggregates not erased or elevated to clinical evidence. |
| **UCI-45 Hungary** | Candidate for **one-shot, separately authorized** locked external assessment of previously frozen Cleveland procedure/model | **Not executed**; source/person independence, target/feature equivalence, timing, missingness, sufficient precision and rights all need evidence. Synthetic AI-10.1 rehearsal is not a real Hungary test. | **Highest new-source priority:** Q-10/Q-11 source-only admissibility, lock/precision protocol, human GO/HOLD/NO-GO decision. Never use test outcomes for model tuning. | Real \`AI-10.2 NOT_PERFORMED\`; no external validation claim. |
| **UCI-45 VA Long Beach** | Source-level domain-shift/missingness or constrained stress-assessment candidate | Missingness, target and feature alignment and study precision not yet established for intended claim. | Q-13 owner/official-metadata-only suitability review; decide limited stress role or reasoned NO-GO. | Not admitted to real transport/generalization claims. |
| **UCI-45 Switzerland** | High-missingness/small-source suitability audit | Sparse/incomplete attributes may make real predictive evaluation unsuitable; no independent outcome claim verified. | Q-13 owner/official-metadata-only audit; document a valid exclusion if eligibility fails. | No real study execution. |
| **UCI-411 extension** | UCI-412 related-archive **overlap/leakage** study | Owner documentation says the same **303** UCI-412 participants and added angiography-derived LAD/LCX/RCA features. | Preserve Q-09 finding; verify release-level relationship as needed. Exclude outcome-adjacent fields from pretest predictor use. | **Unsuitable as independent validation**, not another 303 people. |
| **Statlog Heart** | Provenance and overlap check versus Cleveland | Suspected overlapping source, independence not confirmed. | Q-12 original owner/public metadata and overlap audit; no pooling or independent test claim until proven. | Conditional audit-only. |
| **AngioCAD / P25** | Modern **source-research** candidate; potential different task (angiography/video/stenosis), *not* admitted tabular Track A | Original article mentions **413 patients**; highlights mention **413 videos**; map unknown. Zenodo lists feature/label XLSX but **files not opened**. No verified pretest clinical schema, subject-level binary CAD target or licensing resolution. Third-party 377-row reanalysis is **not** owner codebook. Zenodo \`cc-by-4.0\` vs article “non-commercial” wording conflicts. | Preserve Q-14 hold; clarify rights, source-level patient/row/video mapping, schema and acquisition chronology through original-owner documentation, and separate D-021/maintainer classification decision *if ever reconsidered*. | **P25 \`REJECTED_RED\`** in original 25-paper review **and separately \`SCIENTIFIC_HOLD_NOT_ADMITTED\`** as research classification; never silently promote or download. |

**Scientific comparison warning:** Cleveland and UCI-412 are **different cohorts, predictor sets, label definitions and class fractions**. Their AUROCs must **never** be compared as a same-benchmark head-to-head result or treated as transferable individualized risk probabilities. A four-repeat population SD is **not a CI or standard error**, because the same participants are reused.

## 3. UCI-412 discovery provenance and exact limits (merged #106)

The [public evidence investigation](RH02_UCI412_ANGIOCAD_SCIENTIFIC_EVIDENCE_INVESTIGATION_2026_11_19.md) is the authoritative **research finding dossier**, not the owner workbook dictionary:

1. **2012 original-author JMSS, DOI 10.4103/2228-7477.112099:** 303 referred angiography volunteers; **37-feature** clinical/ECG precursor; \`BP\` “Blood Pressure” 90–190 and \`PR\` “Pulse Rate” 50–110 without printed units; symptom flags Yes/No. Does not certify acquisition timestamps or Yes/No-to-workbook 0/1 direction.
2. **2013 original-author RCM, DOI 10.5812/cardiovascmed.10888, PMCID PMC4253773:** independently readable **demographic Table 1** and **17-name laboratory/echo Table 2**, e.g. FBS, creatinine, TG, LDL, HDL, BUN, ESR, HB, K, Na, WBC, lymphocytes, neutrophils, PLT, EF, regional RWMA and VHD; published value ranges **differ in places from later secondary dictionaries**. The paper's 303 participants cannot be assumed a verified row-for-row join with delivered UCI 303.
3. **2013 CMPB DOI 10.1016/j.cmpb.2013.03.004, 2016 KBS and 2017 Arabasadi/coauthor:** original-author/associated publications report **303 patients, 54 features**; relevant original tables remain unread in this public review. The 2016/2017 \`>50%\` wording conflicts with the 2012/UCI \`>=50%\` edge. Neither rule should be silently mapped onto Cleveland.
4. **Original-inventor, abandoned patent application [US20150370996A1](https://patents.google.com/patent/US20150370996A1/en):** Table 1 *prints* \`BP (Blood Pressure: mmHg)\` 90–190 and \`PR (Pulse Rate) (ppm)\` 50–110. This supports **printed-token provenance only**, **not** BP subtype, clinical meaning of \`ppm\`, delivered UCI XLSX unit semantics or recording time. Its **335 patients/50 features** are an unreconciled alternative patent embodiment, **not** a revision of UCI-412's 303-person deposit. Its own performance claims are not CardioAssist results.
5. **Count reconciliation:** 2012 reported 37; 2013 RCM 17 lab/echo names; \`37+17=54\` is a **hypothesis**, not proof of the delivered schema. Owner prose/2013/2016/2017 say 54; local historical audit says **55 predictors + Cath = 56 columns**; UCI variable UI/API has 56 blank metadata entries; UCI-411 describes 59. Rhythm versus BBB, Length omission/presence and Function Class coding differ by version. **Do not alter the frozen dictionary or choose a new count from this arithmetic.**
6. **Four chest-pain flags** are published as separate Yes/No fields; their mutual exclusivity is **not established**. A secondary paper's observed constant Exertional CP is not grounds to drop the frozen route's feature.
7. **Eligibility remains 0/16 owner-verified pre-cath field timestamps**. “Algorithm to avoid angiography” is design intent, **not** evidence each recorded predictor existed before knowing the Cath outcome. Published retrospective tables, patent snippets and static UCI metadata do not substitute for a dated CRF/case-collection protocol.

**Evidence-grade boundary:** owner deposition/primary paper ≠ inventor patent (different possible cohort) ≠ secondary reprint ≠ historical locally audited aggregate ≠ synthetic software fixture. Cite sources at the claimed grade. Never infer that all records and feature codings are identical merely because multiple papers mention 303.

## 4. Official 16-question register — statuses copied, **not promoted**

Status source: [RH02_SOURCE_QUESTION_REGISTER_2026_11_19.json](RH02_SOURCE_QUESTION_REGISTER_2026_11_19.json). **Question finding grades** from #106 are separate; they must never be written as if they were the official status enum.

| ID | Official status at baseline | Minimum next decision/evidence |
|---|---|---|
| Q-01 — Cleveland 5 fields / pretest timing | \`CONDITIONAL_SOURCE_REVIEW_REQUIRED\` | Original field codebook, prediction-time assessment |
| Q-02 — UCI-45 label boundary | \`SOURCE_WORDING_RESOLVED_EQUIVALENCE_UNRESOLVED\` | Threshold/target comparisons, no silent \`>50\`↔\`>=50\` |
| Q-03 — UCI-412 threshold | \`RESOLVED_PRIMARY_METADATA_ONLY\` | Owner UCI page gives \`>=50\`; exact-50 cross-publication dispute remains |
| Q-04 — UCI-412 16-field timing | \`UNRESOLVED_SCIENTIFIC_HOLD\` | Original CRF/timing before Cath knowledge; **0/16 verified** |
| Q-05 — UCI-412 BP/PR | \`UNRESOLVED_SCIENTIFIC_HOLD\` | Owner BP subtype, PR meaning, measured units and conditions |
| Q-06 — UCI-412 binary direction | \`CONDITIONAL_SOURCE_REVIEW_REQUIRED\` | Original workbook Yes/No to 0/1 coding evidence |
| Q-07 — UCI-412 chest-pain relationships | \`UNRESOLVED_SCIENTIFIC_HOLD\` | Original elicitation/exclusivity and missingness |
| Q-08 — original 54/55 count | \`DOCUMENTED_REPOSITORY_AGGREGATE_ONLY\` | Authorized **local headers-only** version comparison; no agent patient file access |
| Q-09 — UCI-411 independence | \`UNSUITABLE_FOR_THIS_EXTERNAL_CLAIM\` | Keep same-303 cohort/leakage exclusion |
| Q-10 — Hungary eligibility | \`UNRESOLVED_SCIENTIFIC_HOLD\` | Owner-based independent eligible target/source assessment |
| Q-11 — Hungary model/site freeze | \`UNRESOLVED_SCIENTIFIC_HOLD\` | Locked one-shot protocol/permission/model SHA and precision |
| Q-12 — Statlog overlap | \`CONDITIONAL_SOURCE_REVIEW_REQUIRED\` | Original release and duplicate/overlap evidence |
| Q-13 — VA/Switzerland suitability | \`CONDITIONAL_SOURCE_REVIEW_REQUIRED\` | Official feature/target/missingness and declared limited role |
| Q-14 — AngioCAD eligibility | \`CONDITIONAL_SOURCE_REVIEW_REQUIRED\` | Owner schema/timing/license/413 patient–video mapping; P25 RED stays |
| Q-15 — AI-9.2 real labs | \`UNRESOLVED_SCIENTIFIC_HOLD\` | Matched cohort, feature timing/units, prespecified statistical design, human authorization |
| Q-16 — reporting tools | \`RESOLVED_PRIMARY_METADATA_ONLY\` | TRIPOD+AI / PROBAST+AI used correctly in report/reviewer checks |

## 5. What AI exists, what is *only* simulated, and what is blocked

| Component or claim | State | Do not claim |
|---|---|---|
| D-047 Cleveland historical internally executed research | **Source-reported historical aggregate**, model/protocol protected under its exact previous local authorization | Replicated by this research pass, externally validated, clinical risk score |
| M3a UCI-412 historical internally executed research | **Source-reported historical aggregate** | New UCI real fit authorized after #106; owner-verified 16 input timings |
| AI-7/8/8W/8R research adapters and source gates | **Merged; synthetic engineering paths and readiness present** | Patient-facing medical eligibility |
| AI-9.1 / AI-10.1 comparative and locked-site rehearsal | **Synthetic/fictional evaluation software**, not clinical findings | Real lab incremental value or real Hungary transport |
| AI-9.2 real clinical+labs comparison | **NOT_PERFORMED; conditional scientific hold** | Incremental diagnostic benefit demonstrated |
| AI-10.2 real Hungary external test | **NOT_PERFORMED; conditional scientific hold** | External validation achieved |
| SHAP and LIME | Genuine **offline research** implementations with scale/fidelity limitations; backend returns synthetic SHAP-shaped offsets | Explanation is causal or independently clinically proven |
| Versioned AI facade/catalog | Research-only synthetic examples, no authenticated real bundle serving | Five catalog entries = five deployable fitted models |
| Running FastAPI provider | **\`MOCK_SYNTHETIC\` only**, real provider intentionally fail-closed | Real clinical CAD inference activated |
| Graduation manuscript | 17 FR draft chapters, 28 indexed CL entries, 10 human-review actions **PENDING** | Final scientific/university sign-off, exact final release identity |

**Historical quantitative limitations:** Cleveland source-reported outcome-proportion adequacy target **382** at the stated half-width and MAPE criterion **459** (n=303, both unmet). UCI-412 target **315** (n=303 unmet); other R²-dependent criteria were not assessed. These refer to the **specified analysis assumptions**, not a blanket proof that no differently scoped study can ever be done. Calibration slope/CITL are descriptive and cannot establish clinical reliability.

## 6. Next work — bounded, ordered, no repeated blanket searches

**Priority 1 — finish RH-02 remaining sources:** [Issue #107](https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/107) is the executable, public-metadata-only request. Review Cleveland **Q-01/Q-02** and Hungary **Q-10/Q-11** first. Then settle **UCI-411 Q-09**, **Statlog Q-12** and **VA/Switzerland Q-13** by source-role, including a documented HOLD/NO-GO when evidence is insufficient. Only search other reputable datasets if a concrete scientific role cannot be filled. Do not repeat the #106 UCI-412/AngioCAD source hunt.

**Priority 2 — narrow owner/rights unresolved questions:** existing [Issue #102](https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/102) has **prepared but unsent** UCI-412/AngioCAD owner email drafts. After #107 source review, any necessary owner contact should ask targeted remaining CRF, units, version/labels/timing, patient/video map and rights questions. A non-response is not permission; a source author's reply is not an ethics or governance ratification.

**Priority 3 — RH-06 conditional decisions:** for **AI-9.2** (paired Clinical versus Clinical+Labs) and **AI-10.2** (locked Hungary external source), a named reviewer must reach either a **separately approved, properly executed research plan** or an **explicit reviewed HOLD/NO-GO with precise cause**. The prototype reporting package may record an honest no-go; do not relabel it “real evaluation completed.”

**Priority 4 — RH-04 and RH-05 engineering:** source-specific, versioned typed input/output/error/abstention and feature-provenance contracts; deterministic synthetic positive/refusal examples for API and later Flutter/React demo; full privacy/source-hash/security/failure tests; exact-head CI and **maintainer-native-Windows exact-release-SHA** replay. Do not broaden backend beyond \`MOCK_SYNTHETIC\` without separately governed scope.

**Priority 5 — RH-07/RH-08 handoff acceptance:** qualified scientific, statistical and engineering reviews; reconcile the **10 PENDING manuscript actions** and **15 PENDING prototype acceptance criteria** (or document their permissible explicit non-clinical dispositions); prepare frozen report/model cards, sanitized evidence, figures, source links, tests and release SHA. Only maintainer/authorized reviewers can set \`RESEARCH_PROTOTYPE_HANDOFF_ACCEPTED\` under the project criteria. A frontend demo comes **after** this AI workstream handoff and must remain mock/synthetic unless independently approved.

### Mini-checklist for future agent and maintainer sessions

- Before work: inspect live \`main\`, open PR/issue states, and the **canonical** register rather than trusting historical snapshot status.
- Deliverables: source links + exact table/section, authority grade, data/version, claim it establishes, claim it cannot establish, conflicting facts, question ID, test command/results, SHA and scoped next-action owner.
- Validation: GitHub CI completed **4/4 at the exact PR HEAD**; no invented Windows results or source row/hash checks. Document reproducibility and any paywall/owner-access limitations.
- Protected data: zero patient records in cloud or GitHub; no automatic downloads, retraining, test-set peeking, credential changes, provider activation or rewriting of signed/frozen contracts.
- Merge: agent opens **unmerged PR**; reviewer checks it; maintainer decides whether to merge. Merged documentation does **not** authorize clinical use.

## 7. Canonical navigation and evidence ownership

- [Master research and engineering roadmap](../CARDIOASSIST_AI_MASTER_COMPLETION_PLAN.md)
- [Research prototype charter](AI_RESEARCH_PROTOTYPE_COMPLETION_CHARTER_2026_11_19.md)
- [RH milestone tracker (historical snapshot)](AI_RESEARCH_COMPLETION_TRACKER_2026_11_19.json)
- [RH-01 pinned 28-claim source index](RH01_CLAIM_EVIDENCE_INDEX_2026_11_19.json)
- [RH-03 17-chapter manuscript](AI12_2_GRADUATION_RESEARCH_MANUSCRIPT_DRAFT_2026_11_19.md)
- [RH-03 28-claim evidence matrix](RH03_AI12_2_AUDIT_MATRIX_2026_11_19.json)
- [RH-03 summary of scientific review limits](RH03_AI12_2_INDEPENDENT_AUDIT_2026_11_19.md)
- [RH-02 canonical 16-question status register](RH02_SOURCE_QUESTION_REGISTER_2026_11_19.json)
- [RH-02 original-publication / patent / AngioCAD evidence packet](RH02_UCI412_ANGIOCAD_SCIENTIFIC_EVIDENCE_INVESTIGATION_2026_11_19.md)
- [RH-02 machine-readable source/findings](RH02_UCI412_ANGIOCAD_SCIENTIFIC_EVIDENCE_INVESTIGATION_2026_11_19.json)
- [AI-8R source-admissibility and 16-field scientific hold](../ai8r/SOURCE_ADMISSIBILITY.md)
- [Original literature classification register](../../research/source_materials/literature_review_status.csv)
- [Q-01/Q-02/Q-09–Q-13 future scope, Issue #107](https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/107)
- [Prepared **UNSENT** owner-evidence request drafts, Issue #102](https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/102)

**Exit rule:** this handoff is a **consolidated map of what is known and what must happen next**, not an end-state. No new model fitting, clinical sign-off, final research acceptance, rights decision or source admission is performed by creating or merging this document.
