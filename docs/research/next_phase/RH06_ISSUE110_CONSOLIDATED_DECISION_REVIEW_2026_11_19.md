# Issue #110 — Consolidated scientific decision-review for the eight-dataset portfolio and the conditional AI-9.2 / AI-10.2 studies

**Document ID:** `CAI-RH06-ISSUE110-DECISION-REVIEW-2026-11-19-v1.2`
**Change log / review response:** v1.2 (2026-11-19) — addresses PR #111 review `5971501344`. Corrects the Statlog (UCI-145) source characterization: the official UCI-145 owner page (E1) lists `serum-chol` (serum cholesterol, mg/dL) and `fasting-blood-sugar` (binary fasting blood sugar >120 mg/dL) in its 13-feature schema; the prior report claimed Statlog included no such markers, which was false. Fix scope: §4.7 known facts, §6.2 S-1 wording, Appendix A `S-STATLOG145`, validator v1.2 guard and regression tests. **Unchanged:** Statlog's `PROPOSED_NO_GO_FOR_NAMED_ROLE` for independent validation/pooling, Q-12 status, all P-gates, D-046/D-047/D-048, P25, `NOT_PERFORMED` states, and every frozen artifact.
**Prior review response:** v1.1 (2026-11-19) — addresses PR #111 review `5971292942`. Corrects the UCI-45 source characterization: the underlying 13-predictor UCI-45 schema **does document `chol` (serum cholesterol, mg/dL) and `fbs` (binary fasting blood sugar >120 mg/dL)** at all four sites; the prior report incorrectly treated this family as having no biochemical/laboratory fields whatsoever. Fixed: §4.1–§4.5 known-facts rows, §4.2 heading/named role, §4.9 matrix, §5 table, §6.1 F-2 (units scoped to the **2013 RCM Table 2 itself**; the 2015 inventor patent prints some lab/echo units but is a distinct 335-person/50-feature embodiment, not verification of UCI-412's workbook), §6.2 S-1/S-5, new §6.2.1 (`UNASSESSED_DIFFERENT_ESTIMAND`), Appendix A source row, §12.1 validator summary. **No canonical status, P-gate, D-048, P25, study HOLD, `NOT_PERFORMED` state, frozen panel, protocol, dictionary, tracker or workflow was changed.**
**Date:** 2026-11-19
**Baseline:** `main` at `d45bbd44e029d3677e99d08dd4f848d5ec29fa2f` (merge of PR #109, verified `git log --oneline -3`; branch `arena/252b77ec-cardioassist-ai`, clean tree at preparation)
**Status:** `EVIDENCE_REVIEW_DRAFT_NOT_APPROVED` — decision-**review**, **not** a decision, source admission, protocol, study authorization, validation result or clinical claim
**Machine-readable companion:** [`RH06_ISSUE110_CONSOLIDATED_DECISION_REVIEW_2026_11_19.json`](RH06_ISSUE110_CONSOLIDATED_DECISION_REVIEW_2026_11_19.json)
**Read-only validator:** [`scripts/validate_issue110_decision_review.py`](../../../scripts/validate_issue110_decision_review.py)
**Canonical question register:** [`RH02_SOURCE_QUESTION_REGISTER_2026_11_19.json`](RH02_SOURCE_QUESTION_REGISTER_2026_11_19.json) — byte-identical, SHA-256 `9e3f5f9895f894fb603f90435a69d7b174b24bff291254e208cd7c2201f612d4`; **no status in it was changed, promoted or rewritten by this document**

> **Precedence.** `AGENTS.md`, `docs/DECISIONS.md`, the Master AI Completion Plan (`docs/research/CARDIOASSIST_AI_MASTER_COMPLETION_PLAN.md`), the consolidated RH-02/RH-03 handoff merged in PR #108, the canonical 16-question register, the 25-paper supervisor classification and every hash-bound local authorization remain controlling. This report consolidates **already-merged public-source evidence**; it is a set of **proposed** review recommendations for named human reviewers. It changes **no** decision ID, gate, frozen protocol, dictionary, authorization manifest, artifact hash, model, backend capability, tracker entry or clinical status. An unresolved question stays unresolved unless a named human reviewer records a separate decision.

## 1. Trigger, authority and hard boundaries

`gh issue view 110 --repo Muhammed-Fathi/CardioAssist-AI` and `gh api repos/Muhammed-Fathi/CardioAssist-AI/issues/110` both returned **`Resource not accessible by integration` (HTTP 403)**. Under the requester's explicit fallback instruction (in the same request that named this issue), this document executes the **complete fallback scope** without relying on an issue body:

1. Consolidate the research evidence for **all eight datasets** into a source-by-source scientific decision-review matrix — §4, §5.
2. For **AI-9.2 Clinical + Labs**, identify the exact feature, timing, source, protocol and authorization blockers — §6.
3. For **AI-10.2 Cleveland → Hungary**, identify all prerequisites, especially the absence of an approved frozen full-cohort Cleveland model, source compatibility, independence, one-shot protocol and precision — §7.
4. For each proposed study, distinguish `GO_FOR_REVIEW_ONLY`, `HOLD_WITH_SPECIFIC_MISSING_EVIDENCE` and `PROPOSED_NO_GO_FOR_NAMED_ROLE` — §4, §5, §8. **These are recommendations to named human reviewers, never approvals, and never executions.**
5. Identify which outstanding questions require **original-author clarification**, **separately authorized local audits** or **independent scientific review** — §9.
6. Map unresolved work to **RH-04 and RH-05**, explicitly identifying engineering tasks that can proceed immediately using synthetic data — §10.
7. Produce this comprehensive Markdown decision-review report and a JSON companion with evidence references, owners, blockers and next actions — deliverables of this PR.

**Hard boundaries preserved throughout** (same discipline as PRs #106, #108 and #109):

- **No** patient dataset, workbook, archive, raw or processed `.data`/`.xlsx` file was downloaded, opened, hashed, read or copied. Zero bytes of patient-level material are in this PR.
- **No** patient row, patient-level aggregate newly computed from rows, identifier, local report, protected bundle, model artifact or locked external test outcome was accessed. The E2 figures quoted below are **carried forward from already-merged repository documents** (PRs #106/#108/#109 and the E2 audits they cite) and were **not re-derived**.
- **No** model was trained, tuned, scored, calibrated or evaluated; no inference path was enabled; the backend remains `MOCK_SYNTHETIC` only.
- **No** frozen protocol, feature dictionary, decision register entry, authorization template, workflow, `/v1` contract, R1 mapping or UCI-412 source dictionary was modified.
- **No** general dataset literature search was performed — this consolidation deliberately reuses only the merged evidence base (#106, #107/#109, #108) and frozen repository records.
- **No** author or owner email was sent; Issue #102 (unsent owner-letter drafts) remains unsent and outreach is not claimed.
- **No** scientific approval, gate change, register-status change, `P-1`/`P-3`/`P-5` change, or `RESEARCH_PROTOTYPE_HANDOFF_ACCEPTED` claim is made or implied.
- GitHub Issues access returned **HTTP 403 for this issue**; this fallback is the requester-authorized scope, not an inference about the issue body.

## 2. How this relates to RH-04, RH-05 and RH-06

`AI_RESEARCH_COMPLETION_TRACKER_2026_11_19.json` (historical snapshot; **not revised by this PR**) lists **RH-04** (*Versioned source-specific research-only feature and integration contracts*, status `PLANNED`), **RH-05** (*Deterministic synthetic reproducibility and Windows/CI security acceptance*, status `PLANNED`) and **RH-06** (*Conditional AI-9.2 labs and AI-10.2 external real-study dispositions*, status `CONDITIONAL_GATED`).

- RH-06 per the [charter](AI_RESEARCH_PROTOTYPE_COMPLETION_CHARTER_2026_11_19.md): *"each conditional study has a human-reviewed `GO_EXECUTED` with genuine admissible evidence or `NO_GO_DOCUMENTED`/`BLOCKED_WITH_NAMED_CAUSE` with exact remaining requirements."* **This document is not RH-06 execution.** It supplies the consolidated evidence and proposed dispositions so that a named human reviewer/maintainer/supervisor can later record `GO_EXECUTED`, `NO_GO_DOCUMENTED` or `BLOCKED_WITH_NAMED_CAUSE` honestly. No such disposition is recorded here, and none is authorized by this PR.
- RH-04 and RH-05 are **engineering** milestones. Section 10 maps unresolved scientific work onto them and lists the synthetic-only engineering tasks that can proceed immediately without any scientific approval.
- RH-03 (manuscript audit), RH-07 (independent review) and RH-08 (freeze/handoff) are out of scope for this PR except for cross-references.

## 3. Evidence base, grading and provenance

Evidence grades (Master Plan §15.3): **E1** official dataset-owner documentation, original publication or registry; **E2** reproducible local audited aggregate under a recorded scope (carried forward, never re-derived here); **E3** peer-reviewed/reputable secondary research or secondary transcription; **E4** explicit inference/arithmetic from cited facts; **E5** synthetic software fixture (used only to describe software state, never as scientific evidence).

This consolidation reuses, and does not extend, these merged records:

| Ref | Record | Authority | Merged in |
|---|---|---|---|
| [R-HANDOFF] | [RH02_RH03_CONSOLIDATED_RESEARCH_HANDOFF_2026_11_19.md](RH02_RH03_CONSOLIDATED_RESEARCH_HANDOFF_2026_11_19.md) (+ `.json`) | E2 (navigation snapshot) | PR #108 (`0835627d524dbe3c512c1f9bd0606b6bcb864f17`) |
| [R-ISSUE107] | [RH02_ISSUE107_PUBLIC_SOURCE_DATASET_AUDIT_2026_11_19.md](RH02_ISSUE107_PUBLIC_SOURCE_DATASET_AUDIT_2026_11_19.md) (+ `.json`) | E1+E2+E3+E4 per its source catalog | PR #109 (`d45bbd44e029d3677e99d08dd4f848d5ec29fa2f`) |
| [R-UCI412] | [RH02_UCI412_ANGIOCAD_SCIENTIFIC_EVIDENCE_INVESTIGATION_2026_11_19.md](RH02_UCI412_ANGIOCAD_SCIENTIFIC_EVIDENCE_INVESTIGATION_2026_11_19.md) (+ `.json`) | E1+E2+E3+E4 per its source catalog | PR #106 (`d8a0090b1827504532a2f938f200eedcfd86af28`) |
| [R-REGISTER] | [RH02_SOURCE_QUESTION_REGISTER_2026_11_19.json](RH02_SOURCE_QUESTION_REGISTER_2026_11_19.json) | E2 canonical statuses | unchanged (SHA-256 pinned above) |
| [R-M2F] | [../gate-pt/07_m2f_hungary_scientific_decision_and_conditional_protocol.md](../gate-pt/07_m2f_hungary_scientific_decision_and_conditional_protocol.md) | E2 review draft, not approval | repository record |
| [R-M2E2] | [../gate-pt/06_m2e2_dataset_compatibility_and_independent_assessment_READINESS_REVIEW_DRAFT.md](../gate-pt/06_m2e2_dataset_compatibility_and_independent_assessment_READINESS_REVIEW_DRAFT.md) | E2 review draft | repository record |
| [R-M2E1] | [../gate-pt/05_m2e1_sample_size_research_ADEQUACY_REVIEW_DRAFT.md](../gate-pt/05_m2e1_sample_size_research_ADEQUACY_REVIEW_DRAFT.md) | E2 review draft | repository record |
| [M-PLAN] | [../CARDIOASSIST_AI_MASTER_COMPLETION_PLAN.md](../CARDIOASSIST_AI_MASTER_COMPLETION_PLAN.md) | Plan (not authority for facts) | merged via PR #67 |
| [CHARTER] | [AI_RESEARCH_PROTOTYPE_COMPLETION_CHARTER_2026_11_19.md](AI_RESEARCH_PROTOTYPE_COMPLETION_CHARTER_2026_11_19.md) | Working charter | repository record |
| [LEDGER] | [AI_RESEARCH_HANDOFF_EXECUTION_LEDGER_2026_11_18.md](AI_RESEARCH_HANDOFF_EXECUTION_LEDGER_2026_11_18.md) | E2 engineering record | repository record |
| [TRACKER] | [AI_RESEARCH_COMPLETION_TRACKER_2026_11_19.json](AI_RESEARCH_COMPLETION_TRACKER_2026_11_19.json) | Historical tracker snapshot (stale by design; unchanged) | repository record |
| [DECISIONS] | [../../DECISIONS.md](../../DECISIONS.md) | Governance source of truth | merged history |

**Cross-cohort warning (carried forward from [R-HANDOFF] §2):** Cleveland and UCI-412 are *different cohorts, predictor sets, label definitions and class fractions*. Their AUROCs must never be compared as a same-benchmark head-to-head result or treated as transferable individualized risk probabilities. A four-repeat population SD is **not** a confidence interval or standard error.

## 4. The eight-dataset source-by-source scientific decision-review matrix

Disposition vocabulary (recommended, never assigned by this agent):

- **`GO_FOR_REVIEW_ONLY`** — the named human reviewer may proceed to *review* the narrow question stated; no data operation, fit or evaluation follows from this recommendation.
- **`HOLD_WITH_SPECIFIC_MISSING_EVIDENCE`** — the named role is scientifically plausible but is blocked on listed, specific evidence; execution stays `NOT_PERFORMED`/`NOT_AUTHORIZED`.
- **`PROPOSED_NO_GO_FOR_NAMED_ROLE`** — on current evidence the named role should be rejected (or remains rejected) for the stated purpose; a differently-scoped future proposal requires its own protocol and review.

Legend for question links: statuses are **copied unchanged** from [R-REGISTER]; see Appendix B for the full pinned table.

### 4.1 UCI-45 Cleveland / DA-A2 — existing development baseline; external-model *source* candidate

| Aspect | Finding |
|---|---|
| Sources | `S-UCI45`, `S-UCI45-NAMES`, `S-DETRANO-ABSTRACT`, `S-DETRANO-FULLTEXT-COPY` (E1/E3); local D-047 record (E2, not re-executed); `S-REPO-A2-AUDIT` (E2) |
| Known (E1/E2) | 303 headline instances; class vector `164/55/36/35/13` → **139 positive / 164 negative** under 0 vs 1–4 binarization (E4). `trestbps` documented as resting blood pressure *on admission* in mm Hg. `num` 0 `<50%`, 1 `>50%`; exact-50 undefined. Age/sex/cp/trestbps/restecg definitions explicit. The official UCI-45 schema (owner page and `heart-disease.names`, E1) **also documents `chol` (serum cholesterol, mg/dL) and `fbs` (binary fasting blood sugar >120 mg/dL)** among the standard 13 predictors/14 fields of the underlying source; both are **omitted from CardioAssist's frozen D-047 five-field resting panel** and are `UNASSESSED_DIFFERENT_ESTIMAND` for any study (see §6.2.1). Historical internal exploratory result (D-047, `INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED`): source-reported repeated nested-CV AUROC **0.8271 ± 0.0097** (four dependent repeats). Outcome-proportion adequacy targets **382** and MAPE criterion **459** both unmet at n=303. |
| Unverified | Dated per-field pre-reference timing (Q-01, `CONDITIONAL_SOURCE_REVIEW_REQUIRED`); exact-50 / strict-vs-inclusive equivalence (Q-02, `SOURCE_WORDING_RESOLVED_EQUIVALENCE_UNRESOLVED`); six-week group-level window exists only in an E3 transcription, not per-field clocks; cross-site patient overlap cannot be excluded (dummy identifiers); raw↔processed identity. |
| Leakage | `ca` (fluoroscopy), `thal`, `exang`, `oldpeak`, `slope` are outcome-adjacent/invasive-procedure-adjacent; the proposed public-panel role uses only the five resting fields; identifiers and row order never predictors. |
| Named role | Development baseline for a **possible** future frozen external assessment of the Cleveland model; **not** its own external test. |
| Disposition | `GO_FOR_REVIEW_ONLY` (source clarification: Q-01/Q-02 codebook/timing review) · **`HOLD_WITH_SPECIFIC_MISSING_EVIDENCE`** for any new development/freeze role — blocked on timing/threshold rulings, approved development protocol and a full-cohort frozen artifact SHA. **`PROPOSED_NO_GO_FOR_NAMED_ROLE`** for any patient-serving use, threshold tuning, or external-validity claim. |
| Owner | Clinical/research reviewer + endpoint adjudicator; maintainer + supervisor for any protocol/authorization act |

### 4.2 UCI-412 Z-Alizadeh Sani / DA-A1 — separate 16-field M3a route; only currently investigated same-source Clinical+Labs pairing

| Aspect | Finding |
|---|---|
| Sources | `OA-2012-JMSS` (E1, DOI 10.4103/2228-7477.112099), `OA-2013-RCM` (E1, PMC4253773), `OA-2013-CMPB` (E1 abstract, paywalled Table 1), `OA-2016-KBS`, `OA-2017-ARABASADI` (E1 snippets), `OA-2015-USPAT` (E1 inventor-printed tokens; 335-patient/50-feature abandoned embodiment), `PS412`/`OA-2017-MENDELEY` (owner metadata, E1), `OA-2013-RCM-TABLE2` (E1); local M3a record (E2, not re-executed) |
| Known (E1/E2) | 303 participants (216 Cad/87 Normal); owner page **≥50%**; 54-feature owner prose; historical M3a repeated nested-CV AUROC **0.9107 ± 0.0071** (four dependent repeats); sample-size target **315** unmet; local historical audit: **55 predictors + Cath = 56 columns**; 17 named lab/echo fields in original-author Table 2 (token-level 17/17 correspondence, **not** a workbook audit); 2012 design intent "avoid angiography"; S-9 six 0/1 fields provisionally 1=present (secondary support, not owner-certified). |
| Unverified | **0/16** owner-verified pre-angiography predictor timestamps (Q-04, `UNRESOLVED_SCIENTIFIC_HOLD`); BP quantity/unit semantics (Q-05, `UNRESOLVED_SCIENTIFIC_HOLD`; inventor patent prints `mmHg` 90–190 and `ppm` 50–110 — provenance only, not verified xlsx binding, not systolic, not a meaning for `ppm`); chest-pain exclusivity (Q-07, `UNRESOLVED_SCIENTIFIC_HOLD`); 0/1 direction (Q-06, `CONDITIONAL_SOURCE_REVIEW_REQUIRED`); 54 vs 55 vs 56 vs patent 50/335 (Q-08, `DOCUMENTED_REPOSITORY_AGGREGATE_ONLY` — do not choose); exact-50 edge and 2016/2017 `>50%` conflict (Q-03, `RESOLVED_PRIMARY_METADATA_ONLY`). |
| Leakage | `Cath`/`LAD`/`LCX`/`RCA` outcome-derived; echo (EF, RWMA) and labs plausibly same-admission workup — timing unresolved, not licensed as pre-outcome; no field may be promoted on plausibility. |
| Named role | Conditional source for a **future** same-source Clinical vs Clinical+Labs paired study — **the only candidate lab-pairing source currently investigated and registered (the 17-name laboratory/echo extension), and currently inadmissible for it** (see §6). This restriction is about the investigated/registered labs extension only; it is **not** a claim that UCI-45 lacks biochemical markers (see §6.2.1). Not a validation of Cleveland; not pooled with anything. |
| Disposition | **`HOLD_WITH_SPECIFIC_MISSING_EVIDENCE`** (new real fit / panel extension / labs arm: 0/16 timing, unresolved Q-04/Q-05/Q-06/Q-07/Q-08, M3a inadequacy, D-048 unratified) · **`PROPOSED_NO_GO_FOR_NAMED_ROLE`** for AI-9.2 execution now (#106 `D-UCI-TIME` forbidden action) · `GO_FOR_REVIEW_ONLY` for owner CRF/codebook clarification and the (never inferred) M3a packet re-review only. |
| Owner | Named scientific reviewer + maintainer; owner/curator via unsent Issue #102 drafts (if maintainer elects to send); D-048 named human decision if M3a is ever reconsidered |

### 4.3 UCI-45 Hungary — highest-priority *candidate* locked external assessment

| Aspect | Finding |
|---|---|
| Sources | `S-UCI45`, `S-UCI45-NAMES`, `S-DETRANO-ABSTRACT` (E1); [R-M2F], [R-M2E2], E2 aggregate record (class vector `188/37/26/28/15` → **294 records, 188 negative / 106 positive**, E4 arithmetic; **425**-patient Hungarian group in the 1989 abstract) |
| Known (E1/E2) | Distinct named institutions (Hungarian Institute of Cardiology). Processed target 0/1; raw 0–4 with correspondence consistent with binarization (E2; **not** proof of per-patient equivalence). Joint five-field availability **292/294**; **782** missing cells in the 14 processed columns (`ca=291`, `thal=266`, `slope=190`, one missing `trestbps`). Processed whole-row excess duplicate: **1**; VA: **1** (never auto-delete/merge). Raw↔processed order-independent profile overlap **293/294**, positional agreement **1/294** — neither proves identity nor independence. The shared UCI-45 schema documents `chol` and `fbs` at this site too (with major missingness/source-specific quality concerns); neither marker is part of any authorized study or the frozen panel (§6.2.1). |
| Unverified | Patient-level independence from Cleveland (Q-10, `UNRESOLVED_SCIENTIFIC_HOLD`); endpoint/raw→processed equivalence and exact-50 (Q-02); per-field timing; one missing `trestbps` and missingness policy; 294-vs-425 delivered subset identity; precision for any prespecified estimand (Q-11, `UNRESOLVED_SCIENTIFIC_HOLD`). |
| Leakage | Same CA/thal/exercise leakage block as Cleveland; must not be used for any selection. |
| Named role | **One-shot, separately authorized** locked external assessment of a *previously frozen* Cleveland model. Never a development source; never "re-used to tune". Synthetic AI-10.1 rehearsal is not evidence about real Hungary. |
| Disposition | `GO_FOR_REVIEW_ONLY` (inadmissibility/admissibility review: provenance, overlap, endpoint rule) · **`HOLD_WITH_SPECIFIC_MISSING_EVIDENCE`** for any one-shot execution — see §7 (**all** prerequisites open) · `PROPOSED_NO_GO_FOR_NAMED_ROLE` for Hungary as a validation claim, a Hungary-specific fitted model, or any pooling. **AI-10.2 remains `NOT_PERFORMED`.** |
| Owner | Maintainer + independent scientific reviewer + statistician + local operator; supervisor for P-3-grade protocol sign-off |

### 4.4 UCI-45 VA Long Beach — conditional limited stress role only

| Aspect | Finding |
|---|---|
| Sources | `S-UCI45`, `S-UCI45-NAMES`, `S-DETRANO-ABSTRACT` (E1); E2 aggregate record (698 missing cells, 24.93%; `ca=198/200`, `thal=166/200`, `slope=102/200`, `oldpeak=56/200`, `trestbps=56/200`; 1 excess full-row duplicate) |
| Known (E1) | Class vector `51/56/41/42/10` → **200 records, 149 positive** (E4). Detrano 1989: 200-patient VA test group, 75% prevalence — consistent in size and approximate prevalence, not proven identical people. Endpoint wording compatible at source level; exact-50 unresolved. The shared UCI-45 schema documents `chol` and `fbs` at this site as well; neither marker is part of any authorized study or the frozen panel (§6.2.1). |
| Unverified | Timing/units for the five fields; joint availability; patient overlap; chol/oldpeak policy; precision for any stress-assessment claim (Riley inputs not frozen). |
| Named role | At most a **narrowly scoped, separately approved domain-shift/missingness stress assessment**; never pooling, calibration transfer, or current external-validation claim. |
| Disposition | **`HOLD_WITH_SPECIFIC_MISSING_EVIDENCE`** for a limited stress role (statistician precision estimand + evaluator five-field policy + named-role governance authorization) · **`PROPOSED_NO_GO_FOR_NAMED_ROLE`** for pooling / calibration-transfer / validation claims · `GO_FOR_REVIEW_ONLY` for the Q-13 suitability review itself. |
| Owner | Statistician + clinical reviewer + maintainer |

### 4.5 UCI-45 Switzerland — descriptive/high-missingness source; not a validation cohort

| Aspect | Finding |
|---|---|
| Sources | `S-UCI45`, `S-UCI45-NAMES`, `S-DETRANO-ABSTRACT`, `S-DETRANO-FULLTEXT-COPY` (E1/E3); E2 aggregate record (273 missing cells, 15.85%; `ca=118/123`, `fbs=75/123`, `thal=52/123`, `slope=17/123`, `trestbps=2/123`; **`chol=0` in all 123 rows** — physiologically implausible; unresolved structural-missingness/coding question, not a proven value and not a recoding license) |
| Known (E1) | Class vector `8/48/32/30/5` → **123 records, 115 positive, 8 `num=0` negatives** (E4). Original paper: 143 Zurich/Basel (58/85, 1985), 84% prevalence — delivered file is not the full published group (E4 arithmetic). Target wording same UCI-45 strict `>50%`; exact-50 unresolved. The shared UCI-45 schema documents `chol` (all 123 delivered rows report `chol=0`, an unresolved structural-coding question, not a proven value) and `fbs` (75/123 missing per E2); neither marker is part of any authorized study or the frozen panel (§6.2.1). |
| Unverified | 123-vs-143 reconciliation; Zurich/Basel attribution; `chol=0` structural coding; site reference-standard equivalence; per-field timing. |
| Precision | **8 negatives** make specificity and calibration-in-the-large/slope highly imprecise for many plausible locked estimands; Riley inputs unfrozen — no exact adequacy verdict can be claimed, but structural insufficiency for a *primary* validation role is decisive on current evidence. |
| Named role | Source-suitability/descriptive documentation only. |
| Disposition | **`PROPOSED_NO_GO_FOR_NAMED_ROLE`** for any primary locked external validation · **`HOLD_WITH_SPECIFIC_MISSING_EVIDENCE`** for a descriptive or explicitly limited stress analysis (owner/version reconciliation, `chol=0` clinical ruling, statistician precision disposition, reviewer decision that only descriptive outputs are permissible) · `GO_FOR_REVIEW_ONLY` for the Q-13 audit. |
| Owner | Statistician + clinical reviewer + maintainer |

### 4.6 UCI-411 Extension / DA-B1 — same people as UCI-412; audit/leakage study only

| Aspect | Finding |
|---|---|
| Sources | `S-UCI411`, `S-UCI412` (E1); [R-UCI412]; D-046/DA-B1 clause (E2 governance text) |
| Known (E1) | Owner states **303 patients**, **59 features**, adds angiography-derived `LAD`, `LCX`, `RCA`; CAD iff ≥50% narrowing and ≥1 artery stenotic; instruction that **only one of `LAD`/`LCX`/`RCA`/`Cath`** may be used for classification; CC BY 4.0; DOI `10.24432/C5461K`. |
| Unverified | Row-level 411↔412 correspondence (never audited here; would be audit-only work); no new subjects exist by construction. |
| Named role | Overlap/leakage audit of the UCI-412 family; **never** independent validation, training addition or n=606. |
| Disposition | **`PROPOSED_NO_GO_FOR_NAMED_ROLE`** for independence / validation / pooling / sample-size doubling · **`GO_FOR_REVIEW_ONLY`** for an explicitly authorized overlap/correspondence audit (Q-09, `UNSUITABLE_FOR_THIS_EXTERNAL_CLAIM` — unchanged) · `HOLD_WITH_SPECIFIC_MISSING_EVIDENCE` for any same-cohort leakage study until separately authorized. |
| Owner | Scientific reviewer; any audit requires its own written scope; DA-B1 remains audit-only by governance |

### 4.7 Statlog Heart / UCI-145 / DA-B2 — overlap-suspect; audit-only

| Aspect | Finding |
|---|---|
| Sources | `S-STATLOG145`, `S-STATLOG-PROJECT` (E1); `S-STATLOG-BOOK` (E1 partial); `S-STATLOG-ORIGIN-SECONDARY`, `S-STATLOG-OVERLAP-THESIS` (E3, search-excerpt-only); [R-ISSUE107] |
| Known (E1) | 270 records, 13 features, target `1 = absence` / `2 = presence`, "Has Missing Values? No", official wording "similar" to UCI Heart Disease in "slightly different form"; DOI `10.24432/C57303`, CC BY 4.0. The official UCI-145 feature list (E1) **includes `serum-chol` (serum cholesterol, mg/dL) and `fasting-blood-sugar` (binary fasting blood sugar >120 mg/dL)** — their presence in the schema is not pre-angiography timestamp verification and does not make the set a validated labs panel. E3: StatLog set described as Cleveland Clinic Foundation-sourced (Detrano); thesis reports proper-subset hypothesis `303 = 270 + 33`. |
| Unverified | Owner declaration of lineage; row-level or hash-level overlap; threshold (no stenosis threshold printed); recoding; the 33-record difference. |
| Named role | Overlap/provenance suspect only. "Similar" + E3 subset hypothesis forbid independence claims; they do **not** verify a mapping. |
| Disposition | **`PROPOSED_NO_GO_FOR_NAMED_ROLE`** for independent validation, pooling, or any external-test use · **`GO_FOR_REVIEW_ONLY`** for an authorised audit-only overlap investigation (Q-12, `CONDITIONAL_SOURCE_REVIEW_REQUIRED`) · `HOLD_WITH_SPECIFIC_MISSING_EVIDENCE` for lineage adjudication until owner/donor documentation or aggregate audit exists. |
| Owner | Source-donor/auditor + named scientific reviewer |

### 4.8 AngioCAD / P25 — not admitted; not a tabular Track A source

| Aspect | Finding |
|---|---|
| Sources | `PSANG`/`P3C` (2026 MRS028 article; E1 abstract + highlights, counts **413 patients** / **413 videos**), `PSANG_ZENODO` + `OA-2026-ZENODO` (E1 metadata; feature/label XLSX **never opened**), `P3B` (summary page), `S2`-class secondary reanalysis (constructed `>50%` label, 377 rows, STEMI-49% mix; **not** an owner codebook), `OA-2015-USPAT` comparative embodiment (335/50, unreconciled); supervisor sheet P25 `REJECTED_RED` (E2) |
| Known (E1/E3) | Article: **413 patients** with structured clinical data + angiography video sequences; highlights: **413 videos**; retrospective Shahid Chamran ethics; data availability via Zenodo DOI `10.5281/zenodo.15826856`; declared instrument CC BY 4.0 vs article wording "non-commercial" — **conflicting rights texts**; rights governed by neither text as a grant of permission for this project. |
| Unverified | Patient↔video↔row mapping (unknown); schema of Features/Labels XLSX (files unopened); pretest clinical-lab chronology; subject-level binary CAD target; whether 413 is patients or videos in every table; STEMI/NSTEMI case mix; third-party 377-row reanalysis provenance; reuse rights (CC BY vs "non-commercial" wording conflict). |
| Named role | **Not admitted to Track A** (tabular, cross-sectional angiography-referenced CAD). Any future imaging/ACS-mix line would need its own protocol, estimand and leakage controls (Gensini grades, stenosis, presentation) — a different task. |
| Disposition | **`PROPOSED_NO_GO_FOR_NAMED_ROLE`** for tabular Track A / M3a / AI-9.2 / any pooling or substitution · **`GO_FOR_REVIEW_ONLY`** solely for a **curator/owner clarification letter** (schema, patient–video map, chronology, rights-text conflict) with **zero download** · `HOLD_WITH_SPECIFIC_MISSING_EVIDENCE` for any future admission — and the register keeps P25 `REJECTED_RED` and `SCIENTIFIC_HOLD_NOT_ADMITTED` regardless. |
| Owner | Maintainer + supervisor (classification colour is the supervisor's, never the agent's); curator clarification only if the maintainer elects to send one |

### 4.9 Compact cross-source matrix

| # | Source (role) | N (class) | Independence | Target | Five-field availability/timing | Precision feasibility | Primary disposition (recommendation) |
|---|---|---|---|---|---|---|---|
| 1 | Cleveland DA-A2 (development baseline) | 303 (139+/164−) | Development source | `>50%`, exact-50 open | E1 definitions; timing unverified | Targets 382/459 unmet at n=303 | `GO_FOR_REVIEW_ONLY` review; `HOLD_WITH_SPECIFIC_MISSING_EVIDENCE` for freeze; `PROPOSED_NO_GO_FOR_NAMED_ROLE` for serving |
| 2 | UCI-412 DA-A1 (M3a; investigated/registered 17-name lab+echo pairing) | 303 (216 Cad/87 Normal) | Single source | `≥50%` (owner) / `>50%` (2016/2017) | Definitions partial; 0/16 timing; units unverified | Target 315 unmet | `HOLD_WITH_SPECIFIC_MISSING_EVIDENCE`; AI-9.2 `PROPOSED_NO_GO_FOR_NAMED_ROLE` now |
| 3 | Hungary (locked external candidate) | 294 (106+/188−) | Distinct site; patient overlap unresolved | UCI-45 wording; raw→processed open | 292/294 observed; timing unverified | No frozen estimand; unassessed | `GO_FOR_REVIEW_ONLY` review; `HOLD_WITH_SPECIFIC_MISSING_EVIDENCE` for one-shot; AI-10.2 `NOT_PERFORMED` |
| 4 | VA Long Beach (limited stress?) | 200 (149+) | Distinct site; overlap unresolved | Compatible wording; exact-50 open | Many missing (E2); timing unknown | Unassessed | `HOLD_WITH_SPECIFIC_MISSING_EVIDENCE` stress; `PROPOSED_NO_GO_FOR_NAMED_ROLE` for pooling/validation |
| 5 | Switzerland (descriptive?) | 123 (115+/8−) | Distinct site; overlap unresolved | Compatible wording; subset mismatch | Severe/strange missingness (`chol=0`×123) | 8 negatives — infeasible for primary role | `PROPOSED_NO_GO_FOR_NAMED_ROLE` primary validation; `HOLD_WITH_SPECIFIC_MISSING_EVIDENCE` descriptive |
| 6 | UCI-411 DA-B1 (overlap/leakage only) | 303 (same people) | None — same cohort | `≥50%` + artery-defined | Adds outcome-derived fields | No added subjects | `PROPOSED_NO_GO_FOR_NAMED_ROLE` independence; `GO_FOR_REVIEW_ONLY` audit-only |
| 7 | Statlog DA-B2 (overlap-suspect) | 270 | Suspect duplicate | 1/2, no threshold evidence | Mirrored; `ca` leakage | Role invalid while overlap open | `PROPOSED_NO_GO_FOR_NAMED_ROLE` independent; `GO_FOR_REVIEW_ONLY` audit-only |
| 8 | AngioCAD P25 (not admitted) | 413? (unverified) | Unknown | Video/artery stenosis + clinical/lab | Unknown schema/chronology | Unassessed | `PROPOSED_NO_GO_FOR_NAMED_ROLE` Track A; `GO_FOR_REVIEW_ONLY` curator letter, zero download |

**No row authorizes training, evaluation, pooling, download or deployment.** Same column names, CC BY 4.0, published accuracy and different site names are each insufficient for independence, compatibility or validity claims.

## 5. The two named conditional studies at a glance

| | AI-9.2 — same-source Clinical vs Clinical+Labs paired incremental value | AI-10.2 — frozen Cleveland → Hungary locked external assessment |
|---|---|---|
| Intended question | Do routine labs add discrimination **and** calibration over the clinical panel in the same source, same people, same folds? | Does a previously frozen Cleveland five-field model transport, unchanged, to the Hungary cohort? |
| Only candidate source(s) for the investigated/registered labs extension | UCI-412 (the 17-name clinical+lab/echo for the same 303); UCI-45's documented `chol`/`fbs` are a different, unassessed estimand (§6.2.1) | UCI-45 Hungary (`processed.hungarian.data`, 294 records) |
| Software readiness | AI-9.1 synthetic-only paired harness MERGED (PR #87, `b21ca074e9ef609894354e6d0327c4b7cc717093`); synthetic results ≠ clinical evidence | AI-10.1 synthetic-only locked-site rehearsal MERGED (PR #90, `5786424593c5fa9387a1bf382b2233b02779de42`); synthetic ≠ external validation |
| Real study status | **`NOT_PERFORMED`; conditional scientific hold; `HOLD_NOT_EXECUTED` register entry** | **`NOT_PERFORMED`; conditional scientific hold; `HOLD_NOT_EXECUTED` register entry** |
| Blocking theme | §6 — feature semantics/timing, source inadmissibility, protocol and authorization all open | §7 — no frozen full-cohort Cleveland artifact; compatibility, independence, one-shot protocol, precision all open |
| Recommendation | **`PROPOSED_NO_GO_FOR_NAMED_ROLE`** for execution now; `GO_FOR_REVIEW_ONLY` for protocol review only; `HOLD_WITH_SPECIFIC_MISSING_EVIDENCE` for any future re-proposal | **`HOLD_WITH_SPECIFIC_MISSING_EVIDENCE`** (review-only `GO_FOR_REVIEW_ONLY` for protocol revise); `PROPOSED_NO_GO_FOR_NAMED_ROLE` for any immediate execution; real execution stays unauthorized |
| Governance state | P-1 PENDING; P-3 not granted; D-048 unratified; register Q-15 `UNRESOLVED_SCIENTIFIC_HOLD` | P-1 PENDING; P-3 not granted; D-046 read-only scope only; register Q-10/Q-11 `UNRESOLVED_SCIENTIFIC_HOLD` |
| Exit path | Named reviewer + protocol + separate authorization; else documented honest `NO_GO_DOCUMENTED` | Named reviewer + frozen artifact + protocol + authorization; else documented honest `NO_GO_DOCUMENTED` |

Per the [R-HANDOFF] §6 Priority 3, a named reviewer must reach either a separately approved, properly executed research plan or an explicit reviewed HOLD/NO-GO with a precise cause. **This report supplies the precise causes; it is not the decision.**

## 6. AI-9.2 Clinical + Labs — exact blocker inventory

The intended AI-9.2 study (Master Plan §8; AI9_AI12_EXECUTION_SLICES "AI-9.2 / AI-10.2 / AI-12.2"; [CHARTER] RH-06; register Q-15) is a real same-source, same-person paired comparison of a clinical-only panel against a clinical+labs panel. Every blocker below is **specific, evidence-linked and currently open**. None may be waived by engineering convenience.

### 6.1 Feature blockers (what exactly is wrong with "labs")

| ID | Blocker | Evidence |
|---|---|---|
| F-1 | The 17 laboratory/echo field names exist only as an **original-author published table** (2013 RCM Table 2: FBS, Cr, TG, LDL, HDL, BUN, ESR, HB, K, Na, WBC, Lymph, Neut, PLT, EF(%), Region with RWMA, VHD). They are **not** a certified workbook header list; 17/17 **token-level** correspondence with the frozen dictionary is not a header audit. | [R-UCI412] §2.4; `OA-2013-RCM` E1 |
| F-2 | **No printed units in the original-author 2013 RCM Table 2 itself**, except EF(%). The **2015 inventor patent application** does print *some* laboratory/echo units (and BP `mmHg`, PR `ppm`), but it is a **335-person/50-feature distinct embodiment** — **not** verification of UCI-412's delivered 303-row XLSX units, lab timing or clinical correctness; **units must not be transferred between those sources without evidence**. Secondary/frozen ranges disagree in places (TG paper 37–1050 vs dict 50–400; PLT 25–742 vs 100–450; K 3.0–6.6 vs 3.0–6.0; WBC 3700–18000 vs 2000–15000; ESR 1–90 vs 0–60). Frozen secondary units (`mg/dL`, `mm/hr`, …) must not be treated as original-author units. | [R-UCI412] §2.4 (Table 2 compare); §2.5 (patent) |
| F-3 | `Cr`/`CR` glossed **"C, Creatine"** in the paper footnote — not verified as serum creatinine; no assay method, unit or specimen timing; no BUN/creatinine ratio semantics. | [R-UCI412] §2.4 |
| F-4 | **EF(%)** is echocardiographic, **Region with RWMA** has a **blank range** in the paper (0.620 ± 1.133 mean only) and frozen coding `0–3` conflicts with the paper's implied `0–4`; **VHD** is ordinal Normal/Mild/Moderate/Severe with the original note that **patients with known or predominant valvular heart disease were excluded** — case-mix selection, not a free predictor. **No** claim may treat echo fields as routine "labs". | [R-UCI412] §2.4 |
| F-5 | No owner confirmation of **missing-value sentinels or codes** in labs (raw files use `-9.0`; processed use `?`); lab-specific missingness rate per field is unknown (E2 audits covered the 14-column/16-field sets; labs were not a certified separate audit). Abstention vs impute policy undefinable. | [R-ISSUE107] source limits; [R-UCI412] |
| F-6 | **Six binary clinical predictors** (DM, HTN, Current Smoker, EX-Smoker, FH, Typical Chest Pain) remain **S-9 provisional** (1=present) — supported by 2012 history definitions + secondary literature only, never owner-certified. Any labs-augmented model inherits this unresolved encoding. | [R-UCI412]; Amendment A-1; register Q-06 |
| F-7 | **0/16 owner-verified pre-angiography timestamps** on the clinical panel (register Q-04); labs have **no per-field clocks at all** — and the 2013 RCM paper explicitly frames labs/echo as the inputs to a *per-artery* LAD/LCX/RCA prediction study, with same-admission workup fully compatible with its text. Timing is not merely unproven; it is unprovable from current public evidence. | [R-UCI412] §5; register Q-04 |
| F-8 | Estimand feasibility: matched paired delta (ΔAUROC / ΔBrier) at **n=303** against the already-unmet basic-panel target of **315** (M3a sample-size review); no adequacy estimate exists for the incremental-value estimand; R²-dependent criteria were never assessed. | [R-HANDOFF] §5; [R-M2E1] |

### 6.2 Source blockers (why there is no eligible pairing cohort)

| ID | Blocker | Evidence |
|---|---|---|
| S-1 | **UCI-412 is the only currently investigated and registered same-source clinical+labs pairing** — specifically its 17-name laboratory/echo extension. It is under `SCIENTIFIC_HOLD` for new real fitting; #106 records `D-UCI-TIME` (permitted: owner CRF request; **forbidden**: new real UCI-412 training / AI-9.2). The UCI-45 family (Cleveland/Hungary/VA/Switzerland) **does document two biochemical markers in the underlying 13-predictor schema** — `chol` (serum cholesterol, mg/dL) and `fbs` (binary fasting blood sugar >120 mg/dL) — which CardioAssist's frozen D-047 five-field resting panel omits; this is a **different, unassessed estimand**, not a labs pairing (§6.2.1), and it carries no timing, validity or admissibility evidence. Statlog (UCI-145) **also includes** `serum-chol` (serum cholesterol, mg/dL) and `fasting-blood-sugar` (binary fasting blood sugar >120 mg/dL) in its official 13-feature schema — but it is a suspected Cleveland-derived/near-duplicate source with uncertified target/lineage/timing, so it is **not** a verified labs panel, pre-angiography-timestamped evidence, or a permissible AI-9.2 substitute, and remains **`PROPOSED_NO_GO_FOR_NAMED_ROLE`** for independent validation/pooling (audit-only lineage review only, §4.7). AngioCAD's schema is unopened and not admitted. | [R-UCI412] §9–10; [R-ISSUE107] §§4.2–4.6; UCI-45 owner page / `heart-disease.names` (E1); UCI-145 owner page (E1) |
| S-2 | The 303 in 2012 JMSS, 2013 RCM, 2013 CMPB, the 2015 patent embodiment (**335**/50), and the UCI/Mendeley workbooks are **not proven to be the same rows**; `37 + 17 = 54` is an explicit **hypothesis**, not adopted. A labs arm cannot rest on an unverified row join. | [R-UCI412] §§2.3–2.4, §3.2 |
| S-3 | **UCI-411** adds outcome-derived artery fields to the same 303 — not independent, not labs for AI-9.2; **0 added people**. | [R-ISSUE107] §4.4 |
| S-4 | 2013 **CMPB Table 1** (names/units/ranges) is **unread** (paywalled); 2016/2017 original tables unread; absence of a lab codebook in accessible materials ≠ its non-existence, but until read/obtained the study is blocked. | [R-UCI412] §14 |
| S-5 | No sub-cohort with **verified** pre-outcome labs + a target-compatible label exists inside the portfolio: UCI-412's labs fail §6.1, and UCI-45's documented `chol`/`fbs` are **not verified pre-angiography markers**, are omitted from the frozen D-047 five-field panel, and are `UNASSESSED_DIFFERENT_ESTIMAND` (§6.2.1). No other reputable source may be substituted without a fresh, separately reviewed suitability pass (not performed here, per scope). | scope of this PR; UCI-45 owner page / `heart-disease.names` (E1) |

### 6.2.1 UCI-45 limited biochemical markers (`chol`, `fbs`) — `UNASSESSED_DIFFERENT_ESTIMAND`, not an AI-9.2 route

To keep the source matrix accurate:

- The **official UCI-45 owner page** (`https://archive.ics.uci.edu/dataset/45/heart+disease`, DOI `10.24432/C52P4X`) and the official `heart-disease.names` codebook (E1) explicitly list **`chol` = serum cholesterol in mg/dL** and **`fbs` = binary indicator of fasting blood sugar >120 mg/dL** among the standard 13 predictors/14 fields of the underlying 13-predictor UCI-45 source. The same documented schema underlies the Hungary/VA/Swiss sibling files — with **major missingness and source-specific quality concerns** (e.g., Switzerland `ca=118/123`, `fbs=75/123`, and `chol=0` in all 123 delivered rows, an unresolved structural-missingness/coding question, not a proven patient value and not a recoding license).
- These two markers are therefore **in the UCI-45 source**. They are **not** part of CardioAssist's frozen **D-047 five-field resting panel** (`age`, `sex`, `cp`, `trestbps`, `restecg`), no CardioAssist panel, dictionary, route or protocol admits them, and nothing in this document or its authorization basis invents or implies such admission.
- A hypothetical UCI-45 **limited-biochemical-marker** comparison would be a **different, much narrower estimand** than (a) the currently investigated/registered **UCI-412 17-name laboratory/echo extension** (§6.1, §6.2 S-1 to S-4) and (b) AI-9.2's intended routine-labs paired question. It is **not investigated, not authorized, not validated as pre-angiography collection, not a replacement for AI-9.2, not a new workstream, and not an excuse for training or for changing the frozen D-047 five-field route**. Any such study would require, at minimum: its own written protocol with the estimand, target/threshold rulings (exact-50 / `>50%` unresolved), a missingness/abstention policy covering the structural anomalies, units and semantics evidence for both fields, pre-angiography availability evidence, sample-size/precision justification, named independent scientific review, and a **separately scoped governance authorization naming UCI-45 and those fields**.
- Disposition: **`UNASSESSED_DIFFERENT_ESTIMAND`** — documented here for factual precision; it is **not** `ADMISSIBLE`, it proposes **no** study, it opens **no** workstream, and it performs **no** data access. It also does **not** weaken the §6 conclusion: neither AI-9.2 nor any limited-biochemical-marker variant has an approved executable real-data path today.

### 6.3 Protocol blockers (nothing runnable exists)

| ID | Blocker | Evidence |
|---|---|---|
| PR-1 | **No approved/prespecified real-data incremental-value protocol.** AI-9.1 is synthetic-only; its report is software evidence. M3a's registered plan has **no labs arm** — the laboratory panel is *registered but blocked* in D-048's scope. | `ai_master_progress.json` AI-9/AI-9.1; D-048 §data boundary; [LEDGER] |
| PR-2 | Frozen feature dictionary `uci412_research_feature_dictionary` **1.1.0** and panel `uci412_basic_clinical_v1` **1.1.0** contain **no** admissible labs panel; adding one = a new human-reviewed amendment (never silent), new hashes, new manifest — none exists, none is prepared here. | `research/uci412/schemas/uci412_feature_dictionary.v1.json`; [R-HANDOFF] §3.5 |
| PR-3 | No prespecified **paired design**: same-people folds, matched clinical-only vs clinical+labs, fold-local preprocessing/imputation/calibration, paired ΔAUROC/ΔBrier with max-statistic or paired-bootstrap uncertainty, missingness denominators, and a feasibility gate. AI-9.1 implements exactly this **synthetically**; no real counterpart is registered. | AI9_AI12_EXECUTION_SLICES; `research/intake`; PR #87 |
| PR-4 | No **missingness/abstention rule** for labs; no handling for `chol=0`-style structural codes anywhere relevant; no sensitivity-analysis spec; no leakage/negative-control registration for labs (labs are the classic same-admission leakage path). | [R-ISSUE107] §4.6 caution; [R-M2E2] |
| PR-5 | No **TRIPOD+AI / PROBAST+AI** appraisal of a labs-augmented protocol; no named scientific reviewer disposition; P-1 PENDING. Q-16 guidance exists but does not grant approval. | DECISIONS P-1/P-4; register Q-16 |
| PR-6 | **Calibration**: no labs-arm calibration plan (slope/intercept/CITL), no decision-curve or threshold analysis — and no claim may be made either way; the study cannot "discover" its own analysis plan after seeing outcomes. | Master Plan §1; [CHARTER] RH-06 |

### 6.4 Authorization blockers (who may say yes, and no one has)

| ID | Blocker | Evidence |
|---|---|---|
| A-1 | **P-1 PENDING** (final scientific target/protocol). **P-3 not granted** — DECISIONS.md register records `PENDING`; the research corpus consistently records Gate PT as **CLOSED** for formal supervisor-approved research. Either reading forbids this study today. **P-5 NOT MADE — prohibited.** | DECISIONS.md gates table; AGENTS.md; [R-HANDOFF] |
| A-2 | **D-047** (activated Cleveland-only internal exploratory, five-field, `INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED`) **cannot** be relabeled to UCI-412 or to labs. | AGENTS.md D-047 section; D-047 activation record |
| A-3 | **D-048** (M3a UCI-412) remains **`PROPOSED_NOT_AUTHORIZED`**: requires `AUTHORIZE-M3A-UCI412-INTERNAL-RESEARCH` comment + human-approved merge + new locally signed hash-bound manifest; and even a ratified D-048 covers the **basic 16-field panel only** — labs remain *registered but blocked*. | DECISIONS.md D-048; AGENTS.md M3a A-1 section |
| A-4 | Register conditional-studies entry: **AI-9.2 `HOLD_NOT_EXECUTED`, `real_data_authorized=false`, `real_experiment_completed=false`** — unchanged by this PR. Q-15 `UNRESOLVED_SCIENTIFIC_HOLD`; all `human_scientific_disposition` fields `PENDING`. | [R-REGISTER] |
| A-5 | **AGENTS.md**: "AI-9 routine-labs comparison and any real-model fit/serving remain blocked until their separate evidence and authorization gates are satisfied." No gate is satisfied. | AGENTS.md; Master Plan §8 AI-9 exit criteria |
| A-6 | **No ethics/institutional approval** recorded; CC BY 4.0 on UCI-412 is a licence for reuse of the deposit, not consent for clinical research, not an accuracy claim, and not permission to change this project's gates. | [R-ISSUE107]; licence vs permission boundary |
| A-7 | No named human reviewer has recorded `GO_EXECUTED` (or any) disposition; this PR records none. | process, this document |

### 6.5 AI-9.2 disposition

**Recommendation: `PROPOSED_NO_GO_FOR_NAMED_ROLE` for "real same-source clinical vs clinical+labs paired incremental-value execution" until every §6 blocker is closed by named humans; `HOLD_WITH_SPECIFIC_MISSING_EVIDENCE` as the study's standing disposition; `GO_FOR_REVIEW_ONLY` for protocol review of an explicitly re-scoped future proposal.** AI-9.1 remains a synthetic software result inside a review pack. The honest completion statement for AI-9.2 today: **`NOT_PERFORMED` — not failed, not pending-data, simply not executed and not authorized; incremental diagnostic benefit of labs is `NOT ESTABLISHED`.**

## 7. AI-10.2 Cleveland → Hungary — prerequisite inventory

The intended AI-10.2 study (register Q-10/Q-11; [R-M2F] conditional protocol; Master Plan §8 AI-10; [CHARTER] RH-06) is a locked, one-shot assessment of a **previously frozen** Cleveland five-field model on the historical Hungary cohort. Every prerequisite is currently open. The three-stage GO ladder in [R-M2F] §4 (protocol review → Cleveland development + artifact freeze → one-shot assessment) structures the list; no stage is complete.

### 7.1 The frozen Cleveland model prerequisite (the gating absence)

| ID | Requirement | Current state |
|---|---|---|
| M-1 | **No approved, frozen, full-cohort Cleveland serving/assessment artifact exists.** The D-047 internal exploratory run explicitly produced **no saved full-cohort model artifact** (its results review says so). AI-10.1 is a synthetic rehearsal. There is nothing to "transport" yet. | **NOT MET** — blocking everything downstream |
| M-2 | Approved/frozen Cleveland **development protocol** (target `num=0` vs `1–4`, five-field dictionary, prediction timepoint, statistical adequacy, missingness + preprocessing plan, supervisor/consensus sign-off as applicable, maintainer governance authorization for real fitting). D-047 covers only its narrow activated internal-exploratory scope. | **NOT MET** — P-1 PENDING, P-3 not granted |
| M-3 | Cleveland-only development and internal evaluation under that protocol; **all** selection (features, algorithm, hyperparameters, calibration, threshold, preprocessing) completed **without any Hungary data or outcomes**. | **NOT PERFORMED** |
| M-4 | **Freeze package**: versioned final model + preprocessing pipeline; exact feature order/category maps/units; training and source provenance (hashes); software/environment record; model specification + checksum; **independent review and governance approval of the freeze**. No such package exists; frozen D-047 guards must not be repurposed to fabricate one. | **NOT MET** |
| M-5 | Predeclared rule for missing/unrecognized inputs at assessment time and the output scale; **no calibrated individual risk percentages** may be presented absent approved calibration evidence. | **NOT DEFINED** |

### 7.2 Source compatibility prerequisites (Hungary must answer the same question)

| ID | Requirement | Current state |
|---|---|---|
| C-1 | **Endpoint equivalence ruling**: UCI-45 wording (`<50%` vs `>50%`, exact-50 undefined) as applied at *both* sites; raw `0–4` → processed `0/1` recoding equivalence; no common-endpoint claim until a named adjudicator rules. Q-02 stays `SOURCE_WORDING_RESOLVED_EQUIVALENCE_UNRESOLVED`. | **NOT RULED** |
| C-2 | **Five-field dictionary equivalence** across sites: age, sex, cp, trestbps, restecg — representation, units, categories, and reference-standard equivalence per site; `trestbps` mm Hg "on admission" documented (E1) but delivered-file semantics per site unverified. | **NOT VERIFIED** |
| C-3 | **Pre-reference timing both sites**: six-week group-level window (E3-only transcription) is not per-field clocks; no owner CRF; if timing cannot be defended, revise the question or DEFER — do not claim a prospective clinical tool. Q-01 `CONDITIONAL_SOURCE_REVIEW_REQUIRED`. | **UNRESOLVED** |
| C-4 | **Missingness/abstention policy**: 292/294 joint five-field availability (one `trestbps` missing); 782 missing cells overall; `ca`/`thal`/`slope` dominate and are unusable; **no post-freeze imputation**; abstention defined pre-unblinding. | **NOT DEFINED as approved policy** |
| C-5 | **Target-mapping ruling** incl. raw `0–4` → processed `0/1` at Hungary; aggregate profile correspondence (293/294 order-independent) is not per-patient proof; 1 excess full-row duplicate must be handled by prespecified rule, never deletion. | **NOT RULED** |
| C-6 | **Licence/custody**: CC BY 4.0 display + codebook citation request; repository policy forbids committing patient files; no acquisition authorized by any of this. | **AUDIT-ONLY; no download authorized** |

### 7.3 Independence prerequisites (site-shift is meaningless without them)

| ID | Requirement | Current state |
|---|---|---|
| I-1 | **Patient-level independence disposition** Cleveland↔Hungary: distinct institutions supported (E1) but dummy-replaced identifiers, the **425** (published 1989 Hungary test group) vs **294** (delivered) discrepancy, reported aggregate profile collisions, and **1 excess full-row duplicate** leave independence **unproven**. B-04 in the cross-site handoff names this explicitly. | **UNRESOLVED** — Q-10 |
| I-2 | Same for Cleveland↔VA and Cleveland↔Switzerland (only relevant if scope expands); Statlog suspect-duplicate must never enter any pool or comparison. | **UNRESOLVED** — Q-12/Q-13 |
| I-3 | UCI-411 never counts toward independence for UCI-412 (same 303); irrelevant to Hungary but binding on the portfolio. | **UNRESOLVED by policy** — Q-09 |
| I-4 | If independence cannot be defended for the intended independent-site claim, the honest disposition is NO-GO or relabel as development/exploratory — never a "validated" external claim. | **A NO-GO requires a named human decision; not recorded here** |

### 7.4 One-shot protocol prerequisites (lock before touching Hungary)

| ID | Requirement | Current state |
|---|---|---|
| O-1 | **Locked protocol** before any Hungary outcome access: model, preprocessing, target mapping, inclusion/abstention rules, estimands, analysis plan; **one-shot** application; ledger (`research/experiments` synthetic ledger exists; real ledger not authorized). | **NOT APPROVED / NOT CREATED** |
| O-2 | **No test-set tuning** of any kind — model, threshold, calibration, preprocessing, features, sampling. Any Hungary-driven change ⇒ Hungary becomes development; the assessment is void and any future repeat requires a newly justified, separately approved cohort. | **PROHIBITED** — enforced by process, not just policy |
| O-3 | **Prespecified estimands**: discrimination (AUROC + uncertainty; additional prespecified measures only) and calibration (intercept/slope + plot where estimable); denominators, event counts, abstentions, exclusions reported; null results reported as such. | **NOT PRESPECIFIED** |
| O-4 | **One-shot failure semantics**: protocol violation/data-quality failure ⇒ stop and report; later changed analysis = new protocol, never "the independent assessment". AI-10.1's ledger rehearsal demonstrates mechanics only. | **NOT APPROVED** |
| O-5 | **Named independent reviewer** + maintainer + local operator + supervisor-grade protocol approval (P-3-grade) — none recorded. D-046 stays read-only; D-047 stays Cleveland-only. | **ABSENT** |

### 7.5 Precision prerequisites (Riley et al. 2021, *Stat Med* 40:4230–4251)

| ID | Requirement | Current state |
|---|---|---|
| P-1* | Prespecified **validation estimand(s)** with target standard errors / CI widths and confidence level (not a universal N). | **NOT PRESPECIFIED** |
| P-2* | Validation **event proportion**: Hungary 106/294 = **36.1%** (E4); CIs will be wide for AUROC and calibration-slope at this n; must be computed from protocol inputs, not guessed. | **NOT ASSESSED** |
| P-3* | Anticipated **linear-predictor distribution / miscalibration** inputs (from Cleveland development only, never from Hungary) to set the required N; then judge the fixed 294-cohort against targets. | **NOT ASSESSABLE** — no frozen Cleveland model exists (§7.1) |
| P-4* | Any **decision-threshold / net-benefit** estimand only if justified and separately approved; none is. | **NOT PROPOSED** |
| P-5* | M2e.1's development sizing (Cleveland 382/459 unmet) is **not** external-validation sizing and must not be reused as such; no "adequate N = 250" heuristics. | **RULED OUT by method** |
| P-6* | If precision is inadequate for the intended claim ⇒ restrict to descriptive estimates or **NO-GO**; standards may not be lowered after seeing results. | **BINDING** |

*(P-numbering here is local to this section; it does not touch the governance `P-1…P-6` gates.)*

### 7.6 Authorization prerequisites

| ID | Requirement | Current state |
|---|---|---|
| G-1 | **Explicit governance authorization naming Hungary** and the assessment tasks (maintainer), separate from D-046 (read-only) and D-047 (Cleveland-only exploratory). | **ABSENT** |
| G-2 | **Supervisor P-3-grade protocol approval** for the frozen evaluation protocol (endpoint, timepoint, estimands, precision method, population) — DECISIONS.md register records P-3 `PENDING`; research corpus records Gate PT **CLOSED**; either reading = not granted. P-1 PENDING. P-5 prohibited for any clinical/external-validity claim. | **NOT GRANTED** |
| G-3 | **Data/ethics/custody permissions**: no download without named authorization; no patient rows in Git/CI/cloud; local-only execution by the human operator under hash-bound manifest. | **ABSENT** |
| G-4 | **Named independent reviewer** for the assessment report; report publishes only permitted sanitized aggregates; no claim beyond protocol-supported results. | **ABSENT** |
| G-5 | Register Q-10/Q-11 stay `UNRESOLVED_SCIENTIFIC_HOLD`; `human_scientific_disposition` stays `PENDING`; AI-10.2 stays `HOLD_NOT_EXECUTED`. | **UNCHANGED by this PR** |

### 7.7 AI-10.2 disposition

**Recommendation: `HOLD_WITH_SPECIFIC_MISSING_EVIDENCE` — specifically all of §7.1–§7.6 — as the standing disposition; `GO_FOR_REVIEW_ONLY` solely for protocol *review* of a re-scoped future proposal (i.e., "REVISE/DEFER" in [R-M2F] §4 terms); `PROPOSED_NO_GO_FOR_NAMED_ROLE` for any immediate execution, any tuning-on-Hungary, any Hungary-fitted model, or any claim phrased as "external validation achieved". A documented human NO-GO would be a legitimate, valuable result closing prototype disposition — it would **not** establish the science, and a faculty requirement for an actual external study would then require explicit escalation to the supervisor ([CHARTER] RH-06).** AI-10.2 remains **`NOT_PERFORMED`**.

## 8. Study-by-study disposition summary (recommendations for named human reviewers)

| # | Proposed study / named role | Disposition (recommendation only) | Minimal evidence to move the disposition | Owner | Next action |
|---|---|---|---|---|---|
| S-01 | AI-9.2 real paired Clinical vs Clinical+Labs (UCI-412) | `PROPOSED_NO_GO_FOR_NAMED_ROLE` now; standing `HOLD_WITH_SPECIFIC_MISSING_EVIDENCE` | Owner CRF/codebook (units, Cr/"Creatine", EF(%), RWMA, VHD); 0/16 timing resolution; S-9 owner certification or explicit bounded decision; approved incremental-value protocol; separate governance authorization; adequacy for the paired estimand | Named clinical/scientific reviewer + maintainer + (if pursued) supervisor | Do not execute. Human reviewer may record `NO_GO_DOCUMENTED` with §6 causes, or demand specific evidence and re-review |
| S-02 | AI-10.2 frozen Cleveland → Hungary one-shot | `HOLD_WITH_SPECIFIC_MISSING_EVIDENCE` (review-only GO for protocol revise) | §7.1 M-1..M-5 (frozen artifact package) first; then §7.2/§7.3 rulings; then §7.4/§7.5 protocol+precision; then §7.6 authorization chain | Maintainer + independent reviewer + statistician + local operator + supervisor | Do not execute. Maintainer may route the [R-M2F] draft for review, revise, or record `BLOCKED_WITH_NAMED_CAUSE` |
| S-03 | Cleveland full-cohort development + freeze (prerequisite S-02) | `HOLD_WITH_SPECIFIC_MISSING_EVIDENCE` | Q-01/Q-02 closure; approved development protocol; D-047-grade governance authorization for full-cohort fitting; adequacy review acceptance | Maintainer + supervisor + named reviewer | Documentation-only preparation possible; no fitting authorized |
| S-04 | UCI-412 M3a (basic panel) re-activation | `HOLD_WITH_SPECIFIC_MISSING_EVIDENCE` | D-048 named human decision + new M3a-A1 manifest; 0/16 stays unresolved — execution only as internal exploratory, never clinical | Maintainer (named decision) | Preserve current holds; no agent action |
| S-05 | UCI-411 overlap/leakage audit | `GO_FOR_REVIEW_ONLY` (only if separately authorized) | Written scope: aggregate/row-correspondence audit under existing audit toolchain; DA-B1 never independent | Maintainer + scientific reviewer | Await maintainer decision; default is no action |
| S-06 | Statlog overlap investigation | `GO_FOR_REVIEW_ONLY` (audit-only) | Donor/original Statlog lineage documentation; authorized exact/near-duplicate aggregate audit; target ruling | Source-donor/auditor + reviewer | Await authorization; default exclusion |
| S-07 | VA Long Beach limited stress assessment | `HOLD_WITH_SPECIFIC_MISSING_EVIDENCE` (or `GO_FOR_REVIEW_ONLY` of the stress-role question) | Statistician precision estimand; evaluator five-field policy; VA-named governance authorization; missingness/abstention rule | Statistician + clinical reviewer + maintainer | Await evidence; no execution |
| S-08 | Switzerland descriptive source audit | `HOLD_WITH_SPECIFIC_MISSING_EVIDENCE` | 123-vs-143 reconciliation; `chol=0` ruling; precision disposition; descriptive-only output decision | Statistician + clinical reviewer | Await evidence; no execution |
| S-09 | AngioCAD curator clarification letter | `GO_FOR_REVIEW_ONLY` (zero download) | Maintainer decision to send; targeted questions (schema, patient↔video map, chronology, rights conflict); P25 stays `REJECTED_RED` | Maintainer (+ supervisor if classification revisited) | Optional; unsent as of this PR |
| S-10 | Hungary as fitted model / validation / pooling; Switzerland primary; Statlog external; UCI-411 validation; AngioCAD Track A | `PROPOSED_NO_GO_FOR_NAMED_ROLE` (all) | A *different* protocol with its own review; nothing short of that | Named reviewers | Do not propose or perform |

**None of these is an approval. GO_FOR_REVIEW_ONLY ≠ GO_EXECUTED. HOLD ≠ permanent NO-GO. PROPOSED_NO_GO ≠ a human NO-GO decision.** The only legitimate recording acts belong to named humans, separately from this PR.

## 9. Outstanding questions triaged by who must answer them

All canonical statuses below are **copied unchanged** from [R-REGISTER] (SHA-256 pinned in the header). `PENDING` means no human disposition is recorded; it is not a queue position and never becomes an approval by silence or non-response.

### 9.1 Route O — original-author / owner clarification required (letters; Issue #102 drafts remain unsent)

| Q | Question (abbreviated) | Canonical status | What only the owner/authors can answer | If unanswered or unobtainable |
|---|---|---|---|---|
| Q-03 | UCI-412 ≥50% threshold | `RESOLVED_PRIMARY_METADATA_ONLY` | Why 2016/2017 papers say `>50%`; whether any record sits at exactly 50; which text governs the delivered deposit | Keep owner-page ≥50% as source-defined; never harmonize with UCI-45; exact-50 stays unresolved |
| Q-04 | UCI-412 16-field pre-angiography timing | `UNRESOLVED_SCIENTIFIC_HOLD` | Original CRF / collection chronology with clocks vs angiography for all 16 fields | No pretest modelling claim; AI-9.2 stays blocked; M3a stays internal-exploratory at best |
| Q-05 | UCI-412 BP and PR semantics | `UNRESOLVED_SCIENTIFIC_HOLD` | SBP vs DBP vs MAP; mmHg unit binding; device/posture/conditions; `ppm` token (vs bpm); workbook binding of patent Table 1 | BP/PR stay `PARTIALLY_SUPPORTED` provenance only; never map to `trestbps`; never mark units VERIFIED |
| Q-06 | UCI-412 binary direction (six flags) | `CONDITIONAL_SOURCE_REVIEW_REQUIRED` | Owner statement that 0/1 (or Y/N→0/1) means absent/present for DM, HTN, smokers, FH, Typical Chest Pain | S-9 stays provisional; no recoding; Amendment A-1 unverified leg stays unverified |
| Q-07 | UCI-412 chest-pain exclusivity | `UNRESOLVED_SCIENTIFIC_HOLD` | Whether Typical/Atypical/Nonanginal/Exertional CP are mutually exclusive Yes/No flags, their missingness, and their recording moment | Keep flags as delivered; secondary "Exertional CP constant" is a hypothesis, not grounds to drop a feature |
| Q-08 | UCI-412 54 vs 55 vs 56 (vs patent 50/335) | `DOCUMENTED_REPOSITORY_AGGREGATE_ONLY` | Owner-authoritative file version + schema reconciliation (2012 JMSS 37 precursor; 2013 RCM 17 lab/echo; CMPB 54 prose; patent 50/335 abandoned; local 55+Cath=56; UCI UI 56 blank rows; 411 says 59) | Do not choose a count; dictionary stays as registered; count never becomes evidence of identity |
| Q-15 | AI-9.2 labs evidence | `UNRESOLVED_SCIENTIFIC_HOLD` | CRF + lab units + Cr/"Creatine" alias + assay/timing + missing codes | AI-9.2 stays `PROPOSED_NO_GO_FOR_NAMED_ROLE`; synthetic AI-9.1 stays software-only |
| — | AI-9.2 labs semantics (units, EF(%), RWMA 0–4 vs 0–3, VHD exclusion note, Cr gloss) | (within Q-15 scope) | Same owner channel: lab codebook / collection form | Echo fields never silently treated as routine labs |
| — | Hungary subset identity (294 delivered vs 425 published; raw `-9.0` vs processed `?`; recoding rule) | (within Q-10 scope) | Hungarian site owner / UCI curator statement | Per-patient equivalence unproven; endpoint equivalence not claimable |
| Q-14 | AngioCAD schema/rights/patient–video map | `CONDITIONAL_SOURCE_REVIEW_REQUIRED` | Curator: Feature/Labels schema, 413 patients vs 413 videos reconciliation, clinical chronology, subject-level binary CAD rule, which rights text governs | P25 stays `REJECTED_RED` + `SCIENTIFIC_HOLD_NOT_ADMITTED`; zero download |
| — | S-9 tip support | (Amendment A-1) | Owner or a first-party codebook restating `True = 1; false = 0` | A-1 stays provisional; a human must explicitly accept any change it ever gets |

### 9.2 Route L — separately authorized local audits required (read-only, hash-bound, exact scope in writing)

Each item needs its **own** written authorization naming files, purpose, operator, environment, hash verification and aggregate-only outputs. None is authorized by this PR. Never patient rows, never git, never re-derivation of published counts.

| Q | Audit that is admissible in principle | Canonical status | Exact ceiling | Status of authorization today |
|---|---|---|---|---|
| Q-07 | Aggregate-only distinct-value count / joint-flag counts of `Exertional CP` on the hash-pinned local source | `UNRESOLVED_SCIENTIFIC_HOLD` | Uniqueness/constancy description only; never basis to alter panel/dictionary | **Not granted** |
| Q-08 | Headers-only (names/counts) version comparison of UCI-412 deposit vs local hash-pinned file | `DOCUMENTED_REPOSITORY_AGGREGATE_ONLY` | File-version reconciliation at schema level; no values, no fitting | **Not granted** |
| Q-09 | 1:1 row-correspondence check of UCI-411 against UCI-412 (order/identity of the same 303) | `UNSUITABLE_FOR_THIS_EXTERNAL_CLAIM` | Correspondence statement only; never independence | **Not granted** |
| Q-12 | Exact and near-duplicate overlap analysis Statlog vs Cleveland on shared stable fields (aggregate, privacy-preserving) | `CONDITIONAL_SOURCE_REVIEW_REQUIRED` | Overlap disposition feeding a human accept/reject; never a pooling decision | **Not granted** |
| Q-01 | Cleveland five-field joint availability / missingness recount on the hash-pinned local processed file (already aggregate-audited; would need re-authorization to repeat) | `CONDITIONAL_SOURCE_REVIEW_REQUIRED` | Denominators only; never timing inference | **Not granted** |
| Q-10 | Hungary five-field joint availability and duplicate recount (descriptive confirmation of the 292/294 figure) | `UNRESOLVED_SCIENTIFIC_HOLD` | Descriptive denominators; never independence inference | **Not granted** |
| — | M2e.2 follow-ups (target distribution, per-column missingness report) | (within Q-10/Q-02 scope) | Aggregate-only; never row listings | **Not granted** |

Non-response, partial response or a CC BY 4.0 label is **never** an audit authorization, an ethics approval or an accuracy certificate.

### 9.3 Route R — independent scientific review required (named humans; the agent is structurally unable to supply this)

| Q | Question | Canonical status | Reviewer (competency, not identity) | Output expected |
|---|---|---|---|---|
| Q-02 | UCI-45 label boundary `>50%` vs `≥50%`, exact-50 | `SOURCE_WORDING_RESOLVED_EQUIVALENCE_UNRESOLVED` | Clinical endpoint adjudicator (cardiology-experienced) | Written equivalence ruling per source; no silent harmonization |
| Q-04 | Timing adjudication (after owner CRF, if any) | `UNRESOLVED_SCIENTIFIC_HOLD` | Scientific reviewer + clinical reviewer | Per-field VERIFIED/PROPOSED/UNRESOLVED timing register |
| Q-10 | Hungary eligibility (independence, endpoint, five-field, missingness, precision, rights bundle) | `UNRESOLVED_SCIENTIFIC_HOLD` | Named clinical/scientific reviewer | GO_REVIEW-admissible packet or NO-GO with cause |
| Q-11 | Hungary one-shot freeze (protocol + artifact + precision + authorization chain) | `UNRESOLVED_SCIENTIFIC_HOLD` | Maintainer + independent reviewer + statistician + local operator | Locked one-shot protocol or `BLOCKED_WITH_NAMED_CAUSE` |
| Q-13 | VA / Switzerland suitability for a *declared limited role* | `CONDITIONAL_SOURCE_REVIEW_REQUIRED` | Statistician + clinical reviewer | Written role ruling incl. NO-GO reasons |
| Q-14 | AngioCAD admission question (only if ever reconsidered) | `CONDITIONAL_SOURCE_REVIEW_REQUIRED` | Maintainer + supervisor (classification colour) | P25 decision stands unless named human changes it |
| Q-15 | AI-9.2 paired-study design + disposition | `UNRESOLVED_SCIENTIFIC_HOLD` | Named scientific reviewer (+ statistician) | `GO_EXECUTED` (only after authorization) or `NO_GO_DOCUMENTED` |
| Q-16 | TRIPOD+AI / PROBAST+AI structured appraisal of any realized protocol | `RESOLVED_PRIMARY_METADATA_ONLY` (guidance) | Expert assessor | Appraisal of the source-specific protocol; not a checklist certificate |
| — | Full-cohort Cleveland freeze-package review (§7.1 M-4) | (pre-approval step) | Independent reviewer + governance approver | Freeze acceptance or rejection with reasons |
| — | Manuscript 10 PENDING reviewer actions; 15 PENDING prototype acceptance criteria | (RH-03/RH-07) | Faculty/scientific reviewers | Named dispositions; no invented sign-off |
| — | Sample-size adequacy acceptance (Cleveland 382/459 unmet; M3a 315 unmet) | (review drafts) | Statistician + supervisor | Written adequacy/inadequacy decision per estimand |

### 9.4 Route G — governance/human-authorization acts required (no amount of evidence substitutes)

| Act | Owner | Consequence of absence |
|---|---|---|
| Ratify or reject any re-scoped AI-9.2 protocol (new D-decision) | Maintainer (+ supervisor as applicable) | Study remains `PROPOSED_NO_GO_FOR_NAMED_ROLE` |
| Authorize full-cohort Cleveland development fitting (new D-decision) | Maintainer + supervisor-grade approval | S-02/S-03 stay blocked; no frozen artifact ever exists |
| Authorize Hungary one-shot assessment (new D-decision naming Hungary + tasks) | Maintainer + supervisor-grade approval + local operator manifest | AI-10.2 stays `NOT_PERFORMED` |
| Ratify M3a (D-048) or explicitly decline it | Maintainer named human act | UCI-412 stays `SCIENTIFIC_HOLD` |
| Change P-1/P-3/P-4/P-5/P-6 or any register status | Named humans per DECISIONS.md | Nothing changes; this PR changes none |

## 10. Mapping unresolved work to RH-04 and RH-05 — what can proceed now with synthetic data

RH-04 (*Versioned source-specific research-only feature and integration contracts*) and RH-05 (*Deterministic synthetic reproducibility and Windows/CI security acceptance*) are **engineering** milestones. They may — and per the Master Plan §8.1 "Track 1/Track 3 hard rule" should — proceed **without** waiting for scientific gates, **strictly on synthetic fixtures**. They must never launder scientific holds into "implemented", and nothing below creates a real path.

### 10.1 RH-04 — candidate work packages (all synthetic-only; no scientific approval implied)

| ID | Work package | Output | Depends on | Scientific gate touched? |
|---|---|---|---|---|
| RH-04-1 | **Feature acquisition-status taxonomy as code**: extend/verify a typed enum `VERIFIED / PROPOSED / UNRESOLVED / REJECTED` attached to every feature in the route catalog; default `UNRESOLVED`; unknown values fail closed | `research/` (or `ai/`) schema + tests | Existing R1 spec pattern (`research/intake/schemas/cleveland_resting_five_field_mapping.v0.1.json`, `PROPOSED_NOT_APPROVED`) | No — encodes unresolved as unresolved |
| RH-04-2 | **Feature→acquisition crosswalk**: machine-readable JSON for all 8 sources' registered panels (Cleveland 5-field; UCI-412 16-field; UCI-412 labs stub marked `REJECTED`-for-use/`UNRESOLVED`), with unit, timing, provenance-source, missingness, `pre_test_available` tri-state, and per-field disposition | JSON + schema + validator | RH-04-1 | No — every lab/timing field stays UNRESOLVED |
| RH-04-3 | **Synthetic I/O fixtures incl. negatives** per route: valid five-field payload; wrong unit (e.g., `trestbps` in kPa); wrong provenance (Track-B payload → `422`-equivalent refusal); outcome-derived field injection (`ca`, `LAD`) → refusal; missing required feature → `UNAVAILABLE`; stale/unknown panel hash → `ERROR`; categorical out-of-vocabulary → fail closed; optional explicit-null optional feature → accepted-as-absent (D-044 precedent) | `tests/` fixtures | RH-04-1/2 | No |
| RH-04-4 | **Typed response examples + refusal taxonomy**: `SYNTHETIC_RESULT`, `ABSTAIN`, `UNAVAILABLE`, `ERROR` with reason codes, no input echo, no path/secret leakage; synthetic-vs-calibrated labeling enforced (never a raw score re-labeled "calibrated") | Docs + schema + tests | Existing `MOCK_SYNTHETIC` boundary | No |
| RH-04-5 | **Backend handoff note + mock-contract regression**: document how `/v1` keeps mock-only; Track A/Track B one-way rule intact; **zero** new endpoints; additive schemas only if any; contract tests F-09 class | Docs + tests | RH-04-3/4 | No |
| RH-04-6 | **Flutter/React demo handoff mapping**: fixture names → demo screens; explicit "synthetic, not clinical" banner requirement; no real scoring switch | Handoff doc | RH-04-3 | No |
| RH-04-7 | **MCP/CLI report pack**: deterministic synthetic report generator (study-shaped, values all labelled synthetic) reusing AI-12.1 evidence-pack schema — useful for the §12.2 manuscript limitation language | `research/` report builder + tests | RH-04-3 | No |
| RH-04-8 | **Evidence-ledger stub for locked-site flows**: `ExternalEvaluationLedger` rehearsal JSON for the *synthetic* Hungary analog (AI-10.1 already merged); document that real use requires §7 approvals — code must not be able to load real data | Doc + tests | AI-10.1 | No |

### 10.2 RH-05 — candidate work packages (all synthetic-only)

| ID | Work package | Output | Depends on |
|---|---|---|---|
| RH-05-1 | **Reproducibility matrix**: per accepted synthetic pipeline (AI-7 routes, AI-8/8W/8R demo, AI-9.1 harness, AI-10.1 rehearsal, AI-11.x catalog/facade, AI-12.1 E2E) — exact commands, OS/Python/deps, pass/fail/skip exit codes; never a monolithic PASS claim | Matrix doc + JSON | none (documents existing runs) |
| RH-05-2 | **≥3 rejected scenarios per route as automated tests** (route/panel mismatch; invalid value/unit; unknown provenance; tampered HMAC/bundle; missing calibration/XAI; path-redaction; leakage-field injection) | `tests/` additions | RH-04-3 |
| RH-05-3 | **Exact-SHA synthetic rerun** of one pinned route in a clean venv; record digests; tracked-skip register with reasons and compensating native tests | Report (maintainer-native Windows for final replay) | RH-05-1 |
| RH-05-4 | **Deterministic demo re-run + checksum** of AI-12.1-style evidence pack; verify byte-stability excluding timestamps | Report + checksum | RH-05-1 |
| RH-05-5 | **Windows replay checklist** for the maintainer (exact commands, `pip check`, source-integrity, security steps 8/8 as previously recorded) — agent does **not** run native Windows | Checklist doc | none |
| RH-05-6 | **Governance-evidence validator CI proposal**: this PR's `scripts/validate_issue110_decision_review.py` as a *proposed* (patch-only, not applied — workflows are untouched in this branch) required check for evidence PRs | `.patch` proposal | this PR |

### 10.3 Explicitly NOT immediate engineering (scientific/governance gates bind)

- Activating or modifying any real provider; real artifact deserialization; new `/v1` endpoint or environment switch; removing `MOCK_SYNTHETIC` fail-closed paths.
- Any edit to frozen protocols, the feature dictionary, the R1 mapping, source `.data` files, authorization templates, or `.github/workflows/*`.
- Running/fitting anything on Cleveland/Hungary/UCI-412/any real cohort; locked-set access of any kind; M3a re-activation; labs panel unblocking.
- Marking RH-04/RH-05/06 `ACCEPTED`; revising the historical tracker; editing register statuses; claiming Windows acceptance.

### 10.4 Sequencing and dependency honesty

`RH-02 (evidence) → RH-06 (dispositions, human) → RH-03 refresh → RH-07 review → RH-08 freeze`, with `RH-04 → RH-05` **in parallel and unblocked by RH-06**. RH-06's honest NO-GOs (§8) feed RH-03/RH-07 wording; they do not gate synthetic engineering. **No synthetic progress may be presented as scientific progress.** Every RH-04/05 artifact carries the banner: *software evidence only; synthetic; not clinical; no real evaluation performed or implied.*

## 11. Risks, misreadings and non-claims (read before quoting this PR)

1. **Decision-review ≠ decision.** Nothing here approves, admits, recolors P25, lifts a hold, narrows P-1/P-3/P-5, or records any human disposition. All `GO_*`/`HOLD_*`/`PROPOSED_NO_GO_*` strings are *recommendations for named reviewers*.
2. **Recommendation drift.** Reviewers may accept, reject or re-scope any row. A rejection does not falsify the evidence catalog; a non-response leaves every status `PENDING` — which forbids the named action, it never licenses it.
3. **E2 figures are reused, not re-derived.** Recounting them requires a new written local authorization; quoting them requires this caveat.
4. **Austere claims.** No AUROC, calibration, adequacy or validation statement in this document is a new result; all quantitative mentions are historical source-reported aggregates with their dependent-repeats caveat.
5. **Cross-source comparison prohibition.** Cleveland 0.8271 ± 0.0097 vs UCI-412 0.9107 ± 0.0071 must never be headline-compared; different cohorts, predictors, labels, class fractions.
6. **External-validation vocabulary.** No sentence here may be quoted as "external validation achieved/ongoing". AI-9.2/AI-10.2 are `NOT_PERFORMED`.
7. **Licence ≠ permission.** CC BY 4.0 on UCI sources grants reuse of the deposit under its terms; it grants no ethics approval, no clinical accuracy and no governance gate passage; repository policy still forbids patient files in Git/CI/cloud.
8. **Issue-access reality.** Issue #110 itself was unread (HTTP 403). This fallback scope was executed exactly as instructed; if the issue body contains additional or different requirements, a maintainer must say so explicitly and this document must be amended under review.
9. **Tracker truth.** `AI_RESEARCH_COMPLETION_TRACKER_2026_11_19.json` remains a stale historical snapshot (`RH-01…RH-08` states unchanged by this PR); only a reviewed reconciliation PR may update it.
10. **PII/secrets.** Zero patient-level material, tokens, paths to protected bundles or manifests are included; nothing here is an authorization template.
11. **Date-dependence.** Counts (e.g., 292/294, 782, 698, 273 cells; n=303; 106/294 prevalence) are as recorded in the merged E2/E1 sources on 2026-11-19; they are not re-audited and do not change by restatement.
12. **No author contact.** No email was drafted, sent or scheduled; Issue #102 remains the unsent-draft holder.

## 12. Validation performed on this deliverable

- `python3 scripts/validate_issue110_decision_review.py` — deterministic, stdlib-only, read-only; prints `status: PASS/FAIL`; opens only this report, its JSON companion and the pinned canonical register; recomputes SHA-256 digests; **writes nothing, opens no dataset, makes no network call**. See §12.1.
- `python -m pytest tests/audit/test_issue110_decision_review.py -q` — bundled PASS case + temporary-copy negative tests (hash drift, unsafe real-data flag, promoted register status, missing dataset, invalid disposition, missing question link).
- `python -m pytest tests/audit -q` — full audit suite (regression check; must remain green).
- `python3 scripts/verify_sources.py` — four tracked source hashes + 25-paper census must remain `9 green / 1 pink / 6 orange / 9 red`.
- `git diff --check` — whitespace/conflict-marker check.
- Validator and report hashes are recorded inside the JSON companion (self-referential hash handled exactly as the Issue #107 precedent: validator hash recorded post-hoc by the validator's own run).

### 12.1 What the validator checks (summary)

`cardioassist.issue110_decision_review_validation/v1` verifies: schema/version/status (`EVIDENCE_REVIEW_DRAFT_NOT_APPROVED`); safe scope flags (no data/model/approval/backend flags ever true); HTTP-403 fallback evidence present; eight dataset entries with required fields and allowed dispositions; AI-9.2 blocker categories (feature/timing/source/protocol/authorization) each non-empty and specific; AI-10.2 prerequisite set (frozen artifact, development protocol, freeze package, endpoint equivalence, five-field equivalence, independence, missingness, one-shot lock, precision, authorization chain); triage routes O/L/R/G non-empty; RH-04/RH-05 work packages present with synthetic-only framing; canonical register SHA-256 pin and all 16 copied statuses; report token coverage (all eight sources, both studies, disposition vocabulary, RH-04/RH-05, `NOT APPROVED`); **`chol`/`fbs`/`UNASSESSED_DIFFERENT_ESTIMAND` presence (v1.1)**; **absence of the definitively false no-labs claim phrasings (v1.1)**; **F-2 units scoped to the 2013 RCM Table 2 itself (v1.1)**; **`serum-chol`/`fasting-blood-sugar` acknowledgment and Statlog S-1 correction (v1.2)**; **absence of definitive Statlog no-markers claim phrasings (v1.2)**; `prohibited_claims` all `false`.

## 13. Next actions and owners (none executed by this PR)

| # | Action | Owner | Suggested sequencing |
|---|---|---|---|
| N-1 | Maintainer review of this PR; request changes or approve-for-merge | Maintainer | Immediate |
| N-2 | Named scientific reviewer records dispositions for S-01…S-10 (any) | Named reviewer | After review |
| N-3 | If the maintainer elects owner contact: finalize and send the Issue #102 letters (UCI-412 CRF/codebook; AngioCAD curator) | Maintainer | Optional; independent |
| N-4 | If the maintainer elects audit-only work: written authorization for Q-07/Q-08/Q-09/Q-12 audits (Route L) | Maintainer + auditor | Optional; independent |
| N-5 | Rework [R-M2F] conditional protocol draft per reviewer findings, or record `DEFER`/`NO-GO_DOCUMENTED` for AI-10.2 | Maintainer + named reviewer | After N-2 |
| N-6 | Rework / explicitly park AI-9.2 with a named disposition | Maintainer + named reviewer | After N-2 |
| N-7 | Open the RH-04 synthetic work packages (§10.1) as one bounded PR each | Arena/maintainer | Parallel now |
| N-8 | Open the RH-05 reproducibility matrix + rejected-path tests PR | Arena/maintainer | After RH-04 contracts |
| N-9 | RH-03 manuscript refresh to carry AI-9.2/AI-10.2 `NOT_PERFORMED` language verbatim | Arena (docs-only) | After N-5/N-6 |
| N-10 | Tracker reconciliation (RH-01/02/03 states) **only** via a reviewed PR; never fold into this PR | Maintainer | Separate |
| N-11 | If any blocker closes: new evidence PR citing it; this document then requires a reviewed revision (hash regeneration) | Maintainer + reviewer | As events occur |
| N-12 | Escalation for faculty requirements: if a real external/labs study is mandatory for submission, the supervisor must be told explicitly that current evidence = `NOT_PERFORMED` | Maintainer + supervisor | Before any submission claim |

## Appendix A — Evidence reference index (pinned to this PR's baseline)

| Ref | Path / URL | Grade | Role |
|---|---|---|---|
| [R-UCI412] | `docs/research/next_phase/RH02_UCI412_ANGIOCAD_SCIENTIFIC_EVIDENCE_INVESTIGATION_2026_11_19.md` (+`.json`) | E1/E2/E3/E4 | UCI-412 + AngioCAD dossier (167-field tables; 0/16; S-9; P25) |
| [R-ISSUE107] | `docs/research/next_phase/RH02_ISSUE107_PUBLIC_SOURCE_DATASET_AUDIT_2026_11_19.md` (+`.json`) | E1/E2/E3/E4 | Six-dataset public audit (Cleveland, Hungary, Statlog, UCI-411, VA, Switzerland) |
| [R-HANDOFF] | `docs/research/next_phase/RH02_RH03_CONSOLIDATED_RESEARCH_HANDOFF_2026_11_19.md` (+`.json`) | E2 | Eight-source role matrix; RH priorities; prohibited comparisons |
| [R-REGISTER] | `docs/research/next_phase/RH02_SOURCE_QUESTION_REGISTER_2026_11_19.json` | E2 | Canonical 16 questions; statuses copied, never promoted |
| [R-M2F] | `docs/research/gate-pt/07_m2f_hungary_scientific_decision_and_conditional_protocol.md` | E2 | Conditional Hungary protocol; GO ladder; frozen-model prerequisite |
| [R-M2E2] | `docs/research/gate-pt/06_m2e2_dataset_compatibility_and_independent_assessment_READINESS_REVIEW_DRAFT.md` | E2 | Hungary/cross-site compatibility readiness; E2 aggregate source |
| [R-M2E1] | `docs/research/gate-pt/05_m2e1_sample_size_research_ADEQUACY_REVIEW_DRAFT.md` | E2 | Development sample-size review (382/459); not external-validation sizing |
| [M-PLAN] | `docs/research/CARDIOASSIST_AI_MASTER_COMPLETION_PLAN.md` | Plan | Milestones AI-9/AI-10; Track 1/3 hard rule; §3 strategy table |
| [CHARTER] | `docs/research/next_phase/AI_RESEARCH_PROTOTYPE_COMPLETION_CHARTER_2026_11_19.md` | Charter | RH-04/05/06 actions; RH-06 exit criteria |
| [TRACKER] | `docs/research/next_phase/AI_RESEARCH_COMPLETION_TRACKER_2026_11_19.json` | Historical | RH states; RH-06 `CONDITIONAL_GATED`; not revised |
| [PROGRESS] | `docs/research/ai_master_progress.json` | E2 | AI-9/AI-9.1/AI-10/AI-10.1/AI-9.2/AI-10.2 statuses |
| [DECISIONS] | `docs/DECISIONS.md` | Governance | D-046/D-047/D-048 scope text; P-1..P-6 gates |
| [LEDGER] | `docs/research/next_phase/AI_RESEARCH_HANDOFF_EXECUTION_LEDGER_2026_11_18.md` | E2 | AI-9.2/AI-10.2 conditional lines; synthetic-only boundaries |
| [AGENTS] | `AGENTS.md` | Governance | Milestone authorization text; labs blocked; mock-only backend |
| `OA-2012-JMSS` | https://doi.org/10.4103/2228-7477.112099 | E1 | 2012 original clinical/ECG paper; BP/PR no units; ≥50% `Cath` |
| `OA-2013-RCM` | https://pmc.ncbi.nlm.nih.gov/articles/PMC4253773/ | E1 | 2013 lab/echo Table 2; 303; per-artery framing; no units but EF(%) |
| `OA-2013-CMPB` | https://doi.org/10.1016/j.cmpb.2013.03.004 | E1(abstract) | 303 patients, 54 features, ≥/> threshold conflict surfaces here/2016/2017 |
| `OA-2015-USPAT` | https://patents.google.com/patent/US20150370996A1/en | E1 (inventor-printed) | BP mmHg 90–190; PR ppm 50–110; 335-pt/50-feat abandoned embodiment; not UCI-412 |
| `S-UCI45` | https://archive.ics.uci.edu/dataset/45/heart+disease | E1 | Four sites; `num` 0–4; `trestbps` on admission mm Hg; DOI 10.24432/C52P4X |
| `S-UCI45-CHOL-FBS` | https://archive.ics.uci.edu/dataset/45/heart+disease ; https://archive.ics.uci.edu/ml/machine-learning-databases/heart-disease/heart-disease.names | E1 | Underlying 13-predictor UCI-45 schema lists `chol` (serum cholesterol, mg/dL) and `fbs` (binary fasting blood sugar >120 mg/dL); both omitted from CardioAssist's frozen D-047 five-field resting panel; `UNASSESSED_DIFFERENT_ESTIMAND` (§6.2.1); timing/admissibility unverified |
| `S-UCI45-NAMES` | https://archive.ics.uci.edu/ml/machine-learning-databases/heart-disease/heart-disease.names | E1 | Class vectors (Cleveland/Hungary/Switzerland/VA); `-9.0` raw missing code |
| `S-DETRANO-ABSTRACT` | https://europepmc.org/article/MED/2756873 | E1 | 1989 original: 303 Cleveland; Hungary 425; VA 200; Swiss 143; prevalences |
| `S-DETRANO-FULLTEXT-COPY` | https://www.academia.edu/4827700/International_application_of_a_new_probability_algorithm_for_the_diagnosis_of_coronary_artery_disease | E3 | >50% wording; six-week group window; 58 Zurich + 85 Basel 1985 |
| `S-STATLOG145` | https://archive.ics.uci.edu/dataset/145/statlog+heart | E1 | 270/13 features; 1/2 target; "similar … slightly different form"; features include `serum-chol` (mg/dL) and `fasting-blood-sugar` (>120 mg/dL binary) |
| `S-STATLOG-ORIGIN-SECONDARY` | https://link.springer.com/content/pdf/10.1023/A:1007608224229.pdf | E3 | StatLog heart described as Cleveland Clinic Foundation-sourced |
| `S-STATLOG-OVERLAP-THESIS` | https://libres.uncg.edu/ir/ecsu/f/Brandon_Simmons_Thesis-Final.pdf | E3 | Proper-subset hypothesis 303 = 270 + 33 |
| `S-UCI411` | https://archive.ics.uci.edu/dataset/411/extention+of+z+alizadeh+sani+dataset | E1 | Same 303; +LAD/LCX/RCA; ≥50% artery-defined; one-of-LAD/LCX/RCA/Cath rule |
| `S-UCI412` | https://archive.ics.uci.edu/dataset/412/z+alizadeh+sani | E1 | ≥50%; 303; 54-feature prose; DOI 10.24432/C5Q31T |
| `S-RILEY` | https://onlinelibrary.wiley.com/doi/abs/10.1002/sim.9025 | E1 | External-validation sizing methodology (2021) |
| `PSANG` | https://www.sciencedirect.com/science/article/pii/S0169260726001331 | E1 | 2026 MRS028: 413 patients / 413 videos; retrospective Chamran; rights conflict |
| `PSANG_ZENODO` | https://doi.org/10.5281/zenodo.15826856 | E1 | Feature/label XLSX listed; **never opened**; CC BY 4.0 vs article "non-commercial" |
| `S-REPO-A2-AUDIT` | pinned E2 path in [R-ISSUE107] | E2 | Processed missing-cell totals; per-site duplicate excess (Hungary 1, VA 1) |
| [R-UCI412] manifest | `research/uci412/schemas/uci412_feature_dictionary.v1.json` | Contract | Frozen 16-field dictionary 1.1.0 — unchanged; labs panel not admissible |

## Appendix B — Canonical 16-question register, copied unchanged

SHA-256 `9e3f5f9895f894fb603f90435a69d7b174b24bff291254e208cd7c2201f612d4`. Copied at `2026-11-19` for developer navigation only; **the register file was not opened for writing**.

| ID | Canonical status | Human disposition |
|---|---|---|
| Q-01 | `CONDITIONAL_SOURCE_REVIEW_REQUIRED` | PENDING |
| Q-02 | `SOURCE_WORDING_RESOLVED_EQUIVALENCE_UNRESOLVED` | PENDING |
| Q-03 | `RESOLVED_PRIMARY_METADATA_ONLY` | PENDING |
| Q-04 | `UNRESOLVED_SCIENTIFIC_HOLD` | PENDING |
| Q-05 | `UNRESOLVED_SCIENTIFIC_HOLD` | PENDING |
| Q-06 | `CONDITIONAL_SOURCE_REVIEW_REQUIRED` | PENDING |
| Q-07 | `UNRESOLVED_SCIENTIFIC_HOLD` | PENDING |
| Q-08 | `DOCUMENTED_REPOSITORY_AGGREGATE_ONLY` | PENDING |
| Q-09 | `UNSUITABLE_FOR_THIS_EXTERNAL_CLAIM` | PENDING |
| Q-10 | `UNRESOLVED_SCIENTIFIC_HOLD` | PENDING |
| Q-11 | `UNRESOLVED_SCIENTIFIC_HOLD` | PENDING |
| Q-12 | `CONDITIONAL_SOURCE_REVIEW_REQUIRED` | PENDING |
| Q-13 | `CONDITIONAL_SOURCE_REVIEW_REQUIRED` | PENDING |
| Q-14 | `CONDITIONAL_SOURCE_REVIEW_REQUIRED` | PENDING |
| Q-15 | `UNRESOLVED_SCIENTIFIC_HOLD` | PENDING |
| Q-16 | `RESOLVED_PRIMARY_METADATA_ONLY` | PENDING |

Register conditional studies (unchanged): **AI-9.2 `HOLD_NOT_EXECUTED`** (`real_data_authorized=false`, `real_experiment_completed=false`); **AI-10.2 `HOLD_NOT_EXECUTED`** (likewise).

Governance gates (unchanged): **P-1 PENDING** · **P-2 APPROVED FOR D-046 LOCAL READ-ONLY AUDIT SCOPE ONLY** · **P-3 PENDING in DECISIONS.md / treated as CLOSED (not granted) throughout the research corpus** · **P-4 PENDING** · **P-5 NOT MADE — prohibited** · **P-6 PENDING**.

Decision states (unchanged): **D-046** read-only audit scope only · **D-047** Cleveland-only internal exploratory (activated; `INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED`) · **D-048** `PROPOSED_NOT_AUTHORIZED` · **DA-A1/A2** audit-only, no fitting · **DA-B1/B2** audit-only, never independent cohorts · **P25** `REJECTED_RED` and **`SCIENTIFIC_HOLD_NOT_ADMITTED`**.

Tracker (unchanged): RH-00/01 reconciled-with-review pending; RH-02/RH-03 `IN_PROGRESS`; RH-04/RH-05 `PLANNED`; RH-06 `CONDITIONAL_GATED`; RH-07 `PLANNED`; RH-08 `PLANNED`. `RESEARCH_PROTOTYPE_HANDOFF_ACCEPTED`: **not claimed**.

## Appendix C — Fallback-scope traceability matrix

| Fallback item | Where addressed | Key result |
|---|---|---|
| 1. Eight-dataset evidence consolidated into source-by-source decision-review matrix | §4, §4.1–§4.9 | 8/8 sources; per-source sources/facts/uncertainties/leakage/role/disposition/owner |
| 2. AI-9.2 exact feature/timing/source/protocol/authorization blockers | §6.1–§6.4 | 8 feature, 8 source, 6 protocol, 7 authorization, 5 timing-linked items, all evidence-linked |
| 3. AI-10.2 all prerequisites (frozen Cleveland model, compatibility, independence, one-shot, precision) | §7.1–§7.6 | 5 model + 6 compatibility + 4 independence + 5 one-shot + 6 precision + 5 authorization items |
| 4. `GO_FOR_REVIEW_ONLY` / `HOLD_WITH_SPECIFIC_MISSING_EVIDENCE` / `PROPOSED_NO_GO_FOR_NAMED_ROLE` per proposed study | §4.9, §5, §8 | S-01…S-10; explicitly recommendations, never approvals |
| 5. Outstanding questions: original-author clarification / separately authorized local audits / independent scientific review | §9.1 (Route O), §9.2 (Route L), §9.3 (Route R), §9.4 (Route G) | 12 + 7 + 10 + 5 items; all human-owned |
| 6. Unresolved work mapped to RH-04/RH-05; immediate synthetic-data engineering identified | §10.1–§10.4 | 8 RH-04 + 6 RH-05 packages; prohibited list; sequencing |
| 7. Comprehensive Markdown + JSON companion with evidence references, owners, blockers, next actions | this file + `.json` companion | companion validated by `scripts/validate_issue110_decision_review.py` |

**Exit rule.** This document is a consolidated map of what must happen next, not an end state. No new model fitting, clinical sign-off, final research acceptance, rights decision, source admission or gate change is performed by creating or merging it.

**Bottom line.** The portfolio is **evidence-rich and decision-poor**: eight sources, zero approvals, two conditional studies both `NOT_PERFORMED`, and a short, named list of human acts standing between today and any real research claim. The correct next move is review — not data, not training.
