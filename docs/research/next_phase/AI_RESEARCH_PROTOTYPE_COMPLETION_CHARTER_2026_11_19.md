# CardioAssist AI — Research Prototype Completion Charter & Executable Workplan

**Document ID:** CAI-RH-CHARTER-2026-11-19-v1  
**Prepared:** 2026-11-19  
**State:** PROPOSED FOR MAINTAINER REVIEW (no implementation, approval or final acceptance conferred)  
**Baseline checked:** `main` @ `5786424593c5fa9387a1bf382b2233b02779de42`  
**Canonical milestone tracker:** [`docs/research/ai_master_progress.json`](../ai_master_progress.json)  
**Operational companion (machine-readable):** [AI_RESEARCH_COMPLETION_TRACKER_2026_11_19.json](AI_RESEARCH_COMPLETION_TRACKER_2026_11_19.json)  
**Evidence-writing rules:** [AI_RESEARCH_EVIDENCE_LOG_TEMPLATE_2026_11_19.md](AI_RESEARCH_EVIDENCE_LOG_TEMPLATE_2026_11_19.md)  
**Final-report blueprint:** [AI12_2_FINAL_REPORT_BLUEPRINT_2026_11_19.md](AI12_2_FINAL_REPORT_BLUEPRINT_2026_11_19.md)

> **Controlling boundaries:** [Master AI Completion Plan v1.7](../CARDIOASSIST_AI_MASTER_COMPLETION_PLAN.md), [GitHub-first Execution Ledger](AI_RESEARCH_HANDOFF_EXECUTION_LEDGER_2026_11_18.md), [AI-9–12 slices](AI9_AI12_EXECUTION_SLICES.md), `AGENTS.md`, `docs/DECISIONS.md`, frozen Gate DA/PT documents and exact security/authorization bindings. This charter adds **planning and traceability only**. In any conflict, existing governance/source/authorization records prevail. It is **not** an amendment to Gate PT P-1/P-3/P-5, D-046/D-047/D-048, A3, or medical/ethics approval.

## 1. Final target: zero unowned research-prototype delivery gaps

The user-requested finish line is a **complete, reproducible, auditable, technically tested, academically defensible _research-only AI prototype_**, delivered with a scientific report and sufficient handoff for the separate mock/synthetic backend and future UI demonstration. Completeness means **every IN-SCOPE deliverable and verification has an accepted artifact and evidence; every out-of-scope, unavailable, scientifically inadmissible or authorization-blocked study has an explicit, reviewed disposition**. It does **not** mean inventing clinical proof or pretending a blocked real experiment was done.

The intended scientific question is **source-defined cross-sectional angiography-referenced obstructive CAD presence in historical referred cohorts** at a stated pre-reference-test assessment. It is **not** future 30-day MI/mortality risk, acute triage, general-population patient risk, medical diagnosis, patient-specific treatment or deployment. Cleveland uses historical `>50%` wording; UCI-412 uses `≥50%`; exact equivalence is **not established**. Track B wearables/monitoring must never become Track A model predictors without a separately justified model/data protocol.

**Acceptance labels (never conflate):**
- `RESEARCH_PROTOTYPE_HANDOFF_ACCEPTED` — engineering and scientific **reporting/disposition** package fully reviewed and reproducible, without clinical claims.
- `INTERNAL_EXPLORATORY_EVIDENCE_DOCUMENTED` — existing scoped historical same-source D-047 / M3a aggregate records referenced with their qualifications; not a newly validated clinical model.
- `REAL_EXTERNAL_VALIDATION_COMPLETED` — **never assert** unless a separate eligible, approved, executed, reviewed locked evaluation actually exists. A reviewed `NO_GO_DOCUMENTED` is not external validation.
- `CLINICALLY_VALIDATED` / `PATIENT_READY` — outside this charter; not implied by prototype acceptance.

**Stop rule:** Do not mark final handoff complete when a required in-scope report section, runnable synthetic demo, test/reviewer record, feature contract, reproducibility instruction, evidence link, or failure disposition is missing. An unresolved clinical/source limitation may remain **explicitly documented** under a research-only claim, but a silent/unassigned blocker may not.

## 2. Current verified starting point — do not restart completed work

- `AI-7 / AI-8 / AI-8W`: merged synthetic multi-route/Cleveland/UCI-412 software paths and Windows repair, with historical local acceptance evidence.
- `AI-8R`: engineering acceptance of guarded source-admissibility path; **SCIENTIFIC_HOLD** on new real UCI-412 model development. None of 16 predictors has owner-verified pre-angiography timing; BP, PR, chest pain and binary coding have unresolved issues.
- `AI-9.1`: real **software implementation of a synthetic-only** matched Clinical-vs-Labs evaluation; merged #87 and closeout #89. The synthetic delta does **not** establish lab value.
- `AI-10.1`: merged #90 (synthetic-only one-shot locked-site rehearsal), exact merge `5786424593c5fa9387a1bf382b2233b02779de42`. Docs-only closeout #91 is **OPEN as of charter preparation**. **Do not change the canonical tracker in this branch**; first reconcile #91.
- `AI-11.1 / AI-11.2`: synthetic-only offline registry/facade and read-only 5-entry catalog; no real serving provider.
- `AI-12.1`: reproducible synthetic E2E evidence pack; `AI-12.2` broader scientific/final handoff still outstanding.
- Historical **real internal exploratory** source reports exist for **Cleveland D-047 (303; repeated nested CV primary AUROC 0.8271 ± 0.0097)** and **UCI-412 M3a (303; repeated nested CV selected LR AUROC 0.9107 ± 0.0071)**. Both are **reported/documented aggregates**, not independently re-executed in this charter; neither is external validation. The between-source AUROCs are **not comparable for model ranking**.
- `backend/app/inference/registry.py` continues to allow **`MOCK_SYNTHETIC` only**. No real CAD serving switch is authorized.

Read the source-of-truth, not this as a self-updating status document, when work resumes. Historic ledger snapshots retain their creation-date statuses and do not override current GitHub/PR evidence.

## 3. Dataset role and disposition matrix (never train on everything)

| Cohort/source | Current role | What is allowed now | External-validation claim? |
|---|---|---|---|
| UCI-45 Cleveland / DA-A2 | Historical five-feature resting baseline and D-047 internal exploratory study | Preserve original report/frozen artifacts, audit source evidence, synthetic reproduction of contract and interface | No |
| UCI-412 Z-Alizadeh Sani / DA-A1 | Separate 16-field internal exploratory research benchmark; possible future same-source labs | Owner codebook/timing research, metadata/evidence updates, synthetic engineering; **real route SCIENTIFIC_HOLD** | No |
| UCI-45 Hungary | Proposed one-shot locked transport evaluation of a separately frozen Cleveland model | Metadata/eligibility and prespecified precision/overlap/feature/target review **without target-set peeking** | **Not executed** |
| UCI-45 VA Long Beach | Missingness/domain-shift suitability or stress-test candidate | Source/document-level audit, conditional study specification | No |
| UCI-45 Switzerland | High-missingness / small-source suitability audit | Source/document-level audit; report poor suitability when warranted | No |
| UCI-411 | Source extension/duplicate-cohort and leakage audit for UCI-412 | Confirm overlap; never independent test or source of post-outcome predictors | **No; same 303** |
| Statlog Heart | Suspected Cleveland overlap audit | Source provenance/overlap assessment; no independence assumption | No |
| AngioCAD | Modern candidate requiring original clinical-table, source-label, pre-angiography timing, person-level, rights and independent-control review | Metadata-only targeted audit; no presumptive patient-level access | No |
| Other novel source | Only if a **specific** scientific gap remains unmet | Candidate-source evidence screening against prespecified criteria | No by default |

Never silently pool datasets, relabel source outcomes, use angiography-derived features as pretest predictors, or evaluate a locked set to improve development choices. Public landing pages/licences do not override research governance or rights constraints.

## 4. Dependencies and executable milestones

The machine-readable companion carries the **live execution queue**. Status changes are evidence-bearing, reviewable commits/PRs; completion is not inferred from this plan being committed.

### RH-00 — Reconcile source of truth and close current tracking (P0)

**Input:** latest `main` and PR #91; `docs/research/ai_master_progress.json`.  
**Actions:** independent scope/diff/CI review of PR #91; maintainer review and manual merge if acceptable; verify exact merge, local applicable docs/schema checks; ensure AI-10.1 accepted engineering-only record in canonical tracker. Avoid automatic merge or stale status overwrites.  
**Exit evidence:** PR URL, head/merge SHA, actual CI, local docs/JSON parse outcomes, reviewer decision and no conflicts.  
**Blocking:** RH-01 claims of a reconciled baseline may not be made while #91 remains open/unreconciled.

### RH-01 — Existing evidence and completion inventory (P0)

**Input:** Gate DA 01/02/12/14, Gate PT 04/11/15, AI-8R, AI-7–12 evidence, commits and Windows logs.  
**Actions:** one-to-one index for every scientific claim, source, cohort, panel, evaluation, code artifact, result, model card, contract, test and associated uncertainty; check file exists/current and difference between source document, maintainer-reported aggregate, and independently reproduced test. No fresh fit/experiment. Audit current backend mock boundary and all intended input/output routes.  
**Deliverables:** versioned evidence inventory; **Gap Matrix** with `ALREADY_DONE`/`OPEN_ACTIONABLE`/`BLOCKED_WITH_NAMED_CAUSE`/`NOT_APPLICABLE_WITH_REASON`; exact owner, dependency, required artifact and next permitted action for each gap.  
**Exit:** no undocumented required work, no duplicate milestone disguised as new, every claim has link/commit/evidence grade, and no private data in Git.

### RH-02 — Targeted scientific admissibility and decision packet (P0 in parallel with RH-03)

**Questions to answer without inventing source facts:** UCI-412 owner-authored timing/codebook, BP/PR units, chest-pain definitions and six coding directions; Cleveland feature timing/target and calibration/sample-size limitations; Hungary target/panel mapping, 294-vs-425 discrepancy, missingness, independent-person overlap, locked-set precision and rights; plausible alternatives (AngioCAD only if its clinical table truly fixes a gap); UCI-411 and Statlog overlaps.  
**Allowed:** original owner papers, official codebooks, public metadata, narrow read-only audits only when within existing exact local authorization, owner inquiries and approval-ready protocols. **Not allowed:** fabricating per-patient timelines, changing frozen schemas/protocols, unlocked real-data access, testing a locked external cohort.  
**Deliverables:** question-by-question evidence/owner/citation matrix, source GO/HOLD/NO-GO rationale, conditional AI-9.2/AI-10.2 pre-registration and named sign-off dependencies.  
**Exit:** every listed question has `RESOLVED_BY_PRIMARY_EVIDENCE`, `CONDITIONALLY_RESOLVABLE`, or `UNRESOLVED/HOLD` with a **specific consequence** for the final claims. An unanswered question must never be called resolved.

### RH-03 — AI-12.2 scientific report and methods audit (P0 in parallel with RH-02)

**Actions:** consolidate source-defined hypothesis/target, cohort flow and rights, source roles, original D-047/M3a nested-CV method/result records, selection and leakage controls, sample adequacy, AUROC/AUPRC/Brier/calibration/uncertainty, negative controls, model comparisons **within** cohort only, SHAP/LIME output scale/fidelity and limitations. Separate synthetic AI-9.1/10.1 outcomes from historical real internal evidence. Reconcile conflicts explicitly.  
**Deliverables:** completed research manuscript (not just template), figure/table provenance map, references to TRIPOD+AI and PROBAST+AI disclosure/appraisal, full limitations, reproducibility and source/license appendix. Use [AI12_2_FINAL_REPORT_BLUEPRINT_2026_11_19.md](AI12_2_FINAL_REPORT_BLUEPRINT_2026_11_19.md).  
**Exit:** **every numerical value, figure and statement** points to a versioned original report and evidence classification; all applicable sections complete; no missing/unlabelled clinical claims.

### RH-04 — Research model, feature acquisition and integration handoff contracts

**Actions:** audit the 5-slot synthetic catalog against panel definitions. Deliver stable request/response/status examples including `SYNTHETIC_RESULT`, `ABSTAIN`, `UNAVAILABLE`, `ERROR`; model/route/panel/source/version/hash; feature definition, unit, missingness, pre-test timing and acquisition mapping statuses (VERIFIED/PROPOSED/UNRESOLVED/REJECTED); calibrated vs raw synthetic score labeling; SHAP/LIME limitations; refusal reasons, audit/redaction and explicit Track A/Track B isolation. Distinguish OCR correctness from model eligibility.  
**Deliverables:** machine-readable, source-specific feature-to-acquisition crosswalk, sample I/O fixtures (including negative cases), API/backend/Flutter handoff, named changes still belonging to later product demo (OCR, patient/doctor UI, DB).  
**Exit:** new teammate can create **synthetic research UI/API tests without guessing feature meanings**; UCI-412 ambiguous mappings are *not* presented as clinically verified; backend remains `MOCK_SYNTHETIC`.

### RH-05 — Final deterministic reproducibility, security and demo acceptance

**Actions:** reproduce accepted AI-12.1 and applicable AI-7/8/9.1/10.1/11.1/11.2 synthetic pipelines at **exact recorded SHAs** in clean environments. Validate positive and ≥3 rejected scenarios per applicable route; route/panel mismatch, invalid value/unit, unknown/unverified provenance, tampered bundle, data leakage, missing calibration/XAI, privacy/path redaction; expected safe abstention/error; source SHA/keys separation; report schema/checksum; backend mock contract/no switch; native Windows NTFS 8/8 security where applicable.  
**Evidence:** commands, OS/Python/deps, result JSONs/digests, pass/fail/skip/exit codes, GitHub CI exact head, local Windows exact head and post-merge smoke; tracked skips have reason and compensating native tests. Never call a split suite one monolithic PASS.  
**Exit:** reproducible synthetic success/refusals, credible failure handling, negative-path evidence, no unauthorized loading, and independent re-run instructions. No protected records or signing keys in remote CI/PR.

### RH-06 — Conditional AI-9.2 and AI-10.2 real-study decisions (strict GO/NO-GO)

**AI-9.2:** a real same-source Clinical vs Clinical+Labs matched study requires verified feature definitions/units and pre-index time, target, patient pairing, adequate N/missingness, bounded protocol and approved local execution. If GO, run only approved scope, compare on same people/folds with uncertainty and calibration; if NO-GO, preserve synthetic result as synthetic and document **not performed** and precise reasons.

**AI-10.2:** a real frozen-model external evaluation requires prespecified source-/person-level independence disposition, target and feature compatibility, explicit size/precision judgment, locked model and test plan, human-approved data rights/local protocol, and one-shot no-peeking evaluator. If GO, publish only permitted sanitized evaluation; if NO-GO, state **no real external validation** and do not quietly substitute Hungary/Statlog/UCI-411.

**Exit:** each conditional study has a human-reviewed `GO_EXECUTED` with genuine admissible evidence or `NO_GO_DOCUMENTED`/`BLOCKED_WITH_NAMED_CAUSE` with exact remaining requirements. **NO-GO closes prototype planning/disposition, not the unmet scientific validation itself.** If a faculty submission requires an actual external or real labs study, a NO-GO is **not** sufficient for that additional requirement: escalate scope to the supervisor explicitly.

### RH-07 — Independent review, completeness audit and claim adjudication

**Actions:** reviewer cross-checks protocol/claim/source matrix, feature eligibility, leakage/calibration/precision, code and report consistency, access/ethics wording, model card, reproducibility evidence and limitations. Every discrepancy is addressed or labeled blocking. Faculty/clinical/ethics signatures appear only when actually given.  
**Deliverables:** reviewed issue/decision register with named reviewer, date, scope, finding, evidence, disposition; all in-scope checklist items marked accepted with proof.  
**Exit:** no open unowned prototype blocker; clinical claims explicitly prohibited; no invented clinical/ethics approval.

### RH-08 — Final AI + Research freeze and graduation handoff

**Deliverables:** final readme/navigation, frozen reviewed milestone state, report, complete figure/table/claim source index, source/license and rejected-data register, model cards, versioned contracts, repeatable synthetic example I/O, demos/runbook, CI/Windows report, audit/security and limitations, review/NO-GO packet, exact source/PR/release SHA.  
**Exit:** fresh teammate can reproduce demos and negative tests **without private datasets**, locate every report figure/number, inspect source eligibility, and distinguish historical internal real studies from synthetic engineering and unperformed external evaluation; all RH-00…RH-07 requirements satisfy their valid completion criteria. Final prototype label only after maintainer-reviewed merge, run and explicit acceptance.

### Dependency order and concurrency

`RH-00 → RH-01 → (RH-02 || RH-03) → RH-04 → RH-05 → RH-07 → RH-08`. RH-06 source/protocol GO/NO-GO can begin after RH-02 and its **permitted** outcomes feed RH-03 and RH-07. Do not make conditional real-data access a hidden dependency for synthetic engineering. Final report RH-03 is updated after RH-06 dispositions before RH-08 freeze.

## 5. Non-optional acceptance matrix for an academically complete prototype

Every item must have a source/artifact, actual check, reviewer and closure entry in the evidence tracker:

1. Exact research objective, population, pre-index prediction moment, limitations and non-use claims.
2. Every dataset/alternative assigned a role, access/license/provenance, mismatch, overlap and eligibility disposition.
3. Original historical D-047 / M3a design, data counts, metrics and provenance faithfully characterized, without cross-source score ranking.
4. Folds, feature engineering, missingness, tuning/calibration and leakage controls independently inspectable.
5. Calibration/discrimination/uncertainty/small-sample limits explicitly reported, including not estimable or unassessed.
6. SHAP/LIME scale, background provenance, fidelity/stability limits and non-causality.
7. Source-specific features, timing, units, versions, OCR/acquisition mapping, allowed/abstain behavior.
8. AI-9.2 and AI-10.2 decisions recorded as eligible authorized experiments or non-fabricated NO-GO; no silent unperformed study.
9. Machine-readable model inventory, contracts, non-sensitive worked input/output and explanatory refusal samples.
10. Safe local signing/integrity/ACL, synthetic-only provider, strict Track A/B split, privacy and source checks.
11. Exact-head PR CI + Windows run evidence (including skips), reproducible E2E and negative-path demos.
12. Actual completed AI-12.2 scientific report with source-linked figures/tables, TRIPOD+AI/PROBAST+AI limitations.
13. Independent review and issue closure, no invented human medical approvals.
14. Final README/contents/release provenance and complete backend+UI **research-only** handoff.
15. Every remaining scientific/clinical limitation has explicit evidence, owner, impact and research claim restriction. **No unowned, unstated in-scope work.**

## 6. Working rules for ChatGPT, Arena and maintainer

**ChatGPT/research review:** independently inspect repository/source and owner-authored evidence; define small acceptance criteria and review Arena's diffs/results. **Arena:** implement one bounded branch/PR; use only synthetic/non-sensitive fixtures remotely; report exact code, tests, failure conditions and commands; no blanket authorization or clinical claim. **Maintainer:** run appropriate isolated Windows checks, review PR, decide merge and enter observed results. **Named clinical/scientific reviewer:** adjudicate medical semantics/claim scope and gate-dependent approvals only within their actual authority.

For every milestone use this transaction: **(a)** verify current main/PR/decision documents; **(b)** scope + implementation PR; **(c)** exact PR-head CI, targeted/negative/security tests; **(d)** maintainer Windows validation; **(e)** human review/merge; **(f)** exact-merge smoke; **(g)** separate docs-only evidence/`ai_master_progress.json` closeout. Keep this separate machine execution tracker synchronized by reviewed PRs; never mark future results as observed now.

**Secrets policy:** never commit patient-level rows, individual explanations or predictions, raw/protected reports, credentials, local authorization manifests, keys, sensitive paths or unreviewed bundles. PR evidence uses sanitized aggregates, contract examples, hashes, passed/failed/skipped summaries and source citations.

## 7. Next executable task

**P0 / RH-00**: review PR [#91](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/91), verify its source head/CI and two-file docs-only scope, and have the maintainer merge it *only after review*. Then begin **RH-01 exact-source evidence and completion inventory** using [this charter](AI_RESEARCH_PROTOTYPE_COMPLETION_CHARTER_2026_11_19.md) and the machine tracker; no new fitting.

**This charter itself is not evidence of execution or final acceptance.**
