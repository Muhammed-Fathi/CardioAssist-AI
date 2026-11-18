# CardioAssist AI + Research — GitHub-first completion and handoff ledger

**Prepared:** 2026-11-18  
**Record type:** docs-only operational handoff; **not** a new scientific protocol, ratification, training permission or model approval  
**Base main revision:** `60bb1b815203e38f64ee699041868674896b616c` (AI-11.2 acceptance docs PR #86 merged)  
**Live work at creation:** AI-9.1 code [PR #87](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/87), **OPEN / DRAFT** at `27fa6e57b2845d7dc4ae9ab20c17adab0a2d7733`.

> **Purpose:** One operational reference that says what remains to deliver the **research-only AI engineering work package** without redoing Gate DA, Gate PT, D-047 or M3a source/model research. Existing canonical research/gating records are authoritative. This document organizes future work; it does not supersede or grant permissions.

## 1. Standing collaboration rule — consult and record GitHub first

1. **Read before changing:** For each request, inspect `main`, the active PR SHA and `docs/research/ai_master_progress.json`; then consult the existing source-evidence and decision file(s) below. Distinguish the original review date from current PR/CI/Windows results. Avoid re-running dataset selection or training just because an older analysis is not mentioned in a new conversation.
2. **Reuse prior decisions and artifacts:** Keep frozen D-047 Cleveland and M3a UCI-412 original evidence intact. Where older Gate DA rankings and later Gate PT recommendations differ, use the documented chronology and label recommendation vs formally authorized action; never silently erase older records.
3. **Log every substantive new engineering/research result:** Put a reviewed change in its scoped code/docs PR, then record **exact source SHA, PR/merge SHA, intent, files/algorithms/data identity, test environment, commands, passed/failed/skipped results, evidence class, negative outcomes, restrictions and next action** in a PR comment and/or reviewed ledger document. Do not describe code written as tested, a PR as merged, or reported Windows results as independently executed.
4. **Keep source-sensitive files outside Git:** Do not commit real participant rows, raw or protected reports, patient-derived predictions, keys, signatures, owner permissions, local ignored manifests, or unreviewed binary model artifacts. Publish only reviewed sanitized aggregates and evidence metadata. Exact local absolute paths are neither needed in the public-facing research ledger nor a portable runbook.
5. **Close a milestone only after evidence:** GitHub CI alone is not native Windows acceptance. Check exact PR head, source integrity, negative tests, applicable native ACL test and full or explicitly partitioned suite with accurate caveats; human review and merge; smoke exact merge; then a **separate docs-only status closeout PR** updates canonical tracker. A documentation PR does not itself approve training or change protected gates.
6. **Research without unnecessary blocking:** Continue independent software engineering, source-document analysis, protocol drafting and synthetic testing while source uncertainties are investigated. Ask an independent agent for a **specific unresolved question** or cross-check, not a fresh general dataset/model search. Original source documentation may justify a narrow recommendation, but public literature alone cannot establish unavailable per-record measurement timing, controlled access rights or a human clinical authorization.
7. **Explicit status vocabulary:** `ENGINEERING_COMPLETE_SYNTHETIC_ONLY`, `INTERNAL_EXPLORATORY`, `SCIENTIFIC_HOLD`, `EXTERNAL_EVALUATION_NOT_PERFORMED`, `CLINICAL_VALIDATION_NOT_ESTABLISHED` mean different things. An academically complete research prototype may report hard scientific limits; it must not claim patient-use validation.

### Existing records to reuse (do NOT restart from scratch)

| Existing decision/evidence | Canonical record and role |
|---|---|
| Dataset options and ranking | [Gate DA 01](../gate-da/01_dataset_source_and_suitability_matrix.md), [Gate DA 02](../gate-da/02_candidate_ranking.md) — original provisional candidate analysis |
| Actual source QA and workflow decision | [Gate DA 12](../gate-da/12_research_team_evidence_based_decisions.md) / [Gate DA 14](../gate-da/14_real_joint_availability_and_staged_intake_decision.md) — recorded audited facts, engineering intake choices |
| Cleveland completed real exploratory benchmark | [Gate PT 04](../gate-pt/04_d047_first_internal_results_REVIEW_DRAFT.md) — D-047 reported real within-source aggregates; no final trained cohort model or external assessment |
| UCI-412 completed real exploratory benchmark, cross-source synthesis | [Gate PT 11](../gate-pt/11_two_dataset_scientific_evidence_synthesis_REVIEW_DRAFT.md) — M3a prior real internal results and known incomparability of AUROCs |
| Later scientific recommendation and limits | [Gate PT 15](../gate-pt/15_scientific_evidence_resolution_and_development_route_REVIEW_DRAFT.md) — Cleveland five-field Route A′ recommended **for review**; UCI-412 development route held due to source timing/definitions; Hungary conditional/locked |
| UCI-412 field-by-field open evidence | [AI-8R admissibility](../ai8r/SOURCE_ADMISSIBILITY.md) and machine register `research/uci412/schemas/ai8r_eligibility.v1.json` — 16 unverified pre-angiography timestamps; do not pretend solved |
| Operating roadmap and milestone status | [Master Completion Plan](../CARDIOASSIST_AI_MASTER_COMPLETION_PLAN.md), [AI9–12 implementation slices](AI9_AI12_EXECUTION_SLICES.md), [canonical tracker](../ai_master_progress.json) — use latest documented state, not historical milestone labels |
| Prior synthetic research handoff accepted | [AI-11.2 closeout](AI11_2_MERGE_AND_WINDOWS_ACCEPTANCE_2026_11_18.md) and [AI-11.1/AI-12.1 closeout](AI11_1_AI12_1_CLOSEOUT_2026_11_18.md) — do not rerun as if absent |

**Settled working approach, not newly chosen today:** source-specific angiography-referenced CAD presence; Cleveland five-field resting Route A′ as the **best-documented recommended research direction**, with penalized L2 logistic regression as the parsimonious baseline; constrained random forest as bounded comparator and prevalence dummy as reference. The prior **real** D-047 and M3a exploratory benchmarks already exist. Their AUROC estimates must **not** be compared across cohorts to choose the higher one, nor upgraded to external or clinical validation. UCI-412 remains a distinct 16-field research route under scientific hold; UCI-411 is not independent. Hungary stays an untouched conditional external target. No generic new dataset search is a prerequisite to the next synthetic engineering slices.

## 2. Verified stage snapshot at creation

| Scope | State at 2026-11-18; evidence boundary |
|---|---|
| AI-7 / AI-8 / AI-8W | Merged, synthetic engineering scope complete; AI-8 UCI-412 **real** model development is not thereby authorized |
| AI-8R | Locally engineering-accepted **source admissibility and fail-closed handoff**; real UCI-412 route `SCIENTIFIC_HOLD` |
| AI-11.1 / AI-11.2 / parent AI-11 | Merged and locally accepted engineering-only, read-only/synthetic route registry + catalog and offline facade; **backend `MOCK_SYNTHETIC`** |
| AI-12.1 | Merged local synthetic 8-stage reproducibility/evidence-pack work; not final research report |
| **AI-9.1 — PR #87** | **OPEN / DRAFT** and GitHub **7/7 CI jobs SUCCESS** at `27fa6e57b2845d7dc4ae9ab20c17adab0a2d7733`. Maintainer Windows focused **200 passed / 0 failed** (60.22s) on Python 3.12.9, detached clean exact-head; two external synthetic JSON reports byte-identical (SHA256 `6ebf36f021b4ddae0947a1cee508f40716be82dc47aaaa538173356c8a2f900a`), real generated report schema/digest PASS. Full native Windows suite, 8/8 security and source-integrity result **PENDING maintainer output**. **NOT merged, NOT locally accepted.** |
| AI-10.1 | **NOT STARTED**; planned locked-site **synthetic-only** ledger/refusal simulation reusing existing `evaluate_locked_external_cohort` and `ExternalEvaluationLedger`; real Hungary remains untouched |
| AI-12 final | **IN PROGRESS**; broader AI/research delivery package has not yet been accepted |
| AI-9.2 / AI-10.2 real follow-through | Conditional source/protocol/access gates; **not executed or authorized anew by this plan** |

This is an **as-of-created** snapshot, not a live-updating status dashboard. On subsequent executions, inspect canonical tracker plus active PR instead of assuming the snapshot remains current.

## 3. Next execution queue — no reset of existing dataset or model research

### P0 — close AI-9.1 on exact PR head (current)

**No new model search or real-data training.**

- Await the maintainer's **currently running** native Windows `scripts/verify_sources.py` and `scripts/validate_ai_windows_compat.py` (native **8/8**) and `python -m pytest -W error -q -ra --tb=short` full suite **on exact `27fa6e57...`**; record accurate totals, skipped statuses, exit codes and worktree cleanliness. The focused 200 PASS and two byte-identical validated JSON exports are already reported in [PR #87](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/87) and must not be requested again without a new reason.
- If any gate fails, diagnose exact log and fix on PR #87 as smallest reviewable change, rerun at new head. No merge or favorable acceptance declaration on failure.
- If all applicable gates pass, add sanitized local evidence in PR conversation, mark ready for human review, review diff and CI; maintainer decides merge. **Do not merge automatically**. Once merged, verify exact merge SHA on a new clean detached worktree, perform focused post-merge source/security/synthetic smoke; then open docs-only tracker closeout PR. Do not mark the main tracker complete just because this plan was written.
- Deliverable: documented **synthetic-only** matched Clinical vs Clinical+Labs comparison; do not claim clinical improvement even when a synthetic delta is favorable. Existing test evidence actually showed a negative synthetic ROC-AUC delta, which is acceptable and must be reported honestly.

### P1 — AI-10.1 next independent synthetic engineering PR

- Before coding, inspect `ai/training.py` external evaluation functions, ledger/locking rules and existing tests. Implement the **smallest missing** version-bound, one-shot **synthetic** locked-site simulation, avoiding a second evaluator or duplicate registry.
- Negative cases include identity overlap/duplication, panel and outcome mismatch, repeated/failed reservation, unauthorized routes, insufficient sample/classes, no test-set tuning, local file/ACL guard. Include clearly synthetic report and controls.
- CI + Windows acceptance at exact head → reviewed PR/merge → post-merge smoke → docs-only tracker closeout. **No access to or testing/tuning on actual locked Hungary records.**
- Deliverable: defensible external-assessment **method and audit trail**, **not** a real transportability result.

### P1 parallel — AI-12.2 research/graduation deliverable assembly

Build a **cross-referenced handoff**, primarily using **existing** materials:

- **Scientific question**: source-defined *cross-sectional angiographic CAD presence* in referred historical cohorts, not future 30-day risk, severity grading or patient treatment.
- **Provenance and source-role table**: Gate DA/PT decisions, Cleveland DA-A2 development/benchmark, UCI-412 independent internal benchmark, Hungary conditional locked evaluation, UCI-411 duplicate; target threshold >50% vs ≥50% never silently pooled; unresolved AngioCAD/other candidates not presumed eligible.
- **Real internal experiments**: faithfully quote and classify D-047 and M3a aggregate ROC-AUC, calibration, CV splits, negative controls, and sample-size/selection limits. The reported Cleveland 0.8271 and UCI-412 0.9107 are **not comparable cross-source**. No claim of an independently verified performance ranking or new model training.
- **Engineering evidence**: AI-7/8/8R/11 and AI-12.1 completed, with GitHub CI, maintainer Windows logs, source-hash/NTFS results, model catalog, safe synthetic demo, XAI scope and typed abstain/error handling.
- **Current AI-9 and future AI-10**: synthetic compared metrics with uncertainty caveats, conditional external validation readiness, explicit not-performed real study flags. Snapshot only after relevant PR acceptance.
- **Explainability and reporting**: SHAP stated output scale and fidelity; LIME approximation validity; no causal feature interpretation. Transparent methodology, intended population, cohort counts, leakage control, calibration diagnostics, TRIPOD+AI disclosure and PROBAST+AI limitations. Report any not-estimable outcome, no invented physician signoff.
- **Handoff contract**: public/synthetic versioned inputs/outputs and status/error schema, offline CLI reproduction, setup/dependency expectations, negative/safety test demonstration, precise repo paths and PR/SHAs. Hand off to backend/mobile teams **only the research or synthetic interface**; real serving requires a separate stage and authorization.
- **Acceptance**: a new team member can reproduce the synthetic demonstration safely and trace **every number/claim to a named report/commit**, with no private data in Git; product-level UI/OCR integration and clinical deployment are explicitly separate future work.

**No second general source review:** The scientific papers, Gate DA/PT datasets, evidence matrix, registered models and research limitations have already been reviewed. The final handoff **indexes and reconciles** them, rather than re-searching them. A targeted evidence update PR is permitted if there is a *specific* previously unanswered question material to an execution gate.

### P2 conditional — AI-9.2/AI-10.2 real scientific follow-through

- An actual clinical+labs improvement claim requires a **separate eligible same-source cohort/predictor timing evidence, registered matched plan, permission and protected local run**; AI-9.1 synthetic comparators do not activate that path.
- An actual independent Hungary or other-site claim requires the model/panel/protocol fixed **before touching** the locked cohort, participant overlap/target/feature compatibility and a separately justified sample-size/precision and authorization determination. A genuine `INSUFFICIENT_EVIDENCE` / `NO_GO` conclusion is an acceptable research result.
- **Do not rerun previous D-047 or M3a exploratory fitting** without a specifically scoped new scientific question, a new protocol and appropriate authorization. Avoid forcing a model to fit clinical claims unsupported by data.

## 4. Clear deliverable and definition of “AI + Research delivered”

There are **three deliberately separate completion labels**:

| Label | Minimum evidence needed | May it be claimed merely by synthetic CI? |
|---|---|---|
| **AI Engineering & Research Prototype HANDOFF READY** | AI-9.1 and AI-10.1 accepted synthetic engine; AI-11 existing registry/contract, AI-12.1 reproducible demo and AI-12.2 scientific/provenance/model-card/reporting pack; maintainer Windows and exact-sha GitHub checks; reproducible synthetic workflows/refusals; no missing secret/source file. | Only after specific acceptance and reproducibility, not just creation |
| **REAL SCIENTIFIC EVALUATION AVAILABLE** | Existing D-047 and M3a **internal exploratory** evidence transparently included, plus any actually permissible **new** source-specific study correctly labeled. Do not count an unperformed external test as delivered. | **No** |
| **CLINICALLY VALIDATED / PATIENT-READY AI** | Suitable external prospective/clinical evidence, credible calibration and utility in intended population, clinical and institutional governance and product safety/authorization. **Not in the current synthetic-only deliverable.** | **No** |

An academically deliverable research prototype **can be complete while documenting unresolved clinical/source evidence**. What cannot be done is relabel a missing experiment as passed, an old internal exploratory AUROC as independent validation, or an offline mock API as a deployed clinical model.

## 5. Next review after the current PowerShell logs

At next turn, check:

1. Exact PR #87 SHA unchanged (or identify and handle change), CI, merge state.
2. Maintainer's raw output: `verify_sources.py`, Windows ACL **8/8** JSON, full `pytest -W error` passed/skipped/failed/exit, final `git status`.
3. Write **only verified** sanitized results into PR #87 conversation. If success, recommend ready-for-review; if failure, small repair with test; never claim a completed gate based on final `Write-Host` alone.
4. After verified merge, run exact-merge smoke and docs-only master tracker status update. Then kick off AI-10.1 **and** AI-12.2 in separate, parallel-scoped PRs; don't defer all research documentation until the end.
5. Update this ledger only via reviewable PR as future work changes; link **the canonical tracker** rather than letting duplicate status tables drift. No automatic background progress or monitoring is implied.

**Source of truth priority:** exact merged GitHub code and reviewable PR evidence for implementation; `docs/research/ai_master_progress.json` for current milestone state; frozen decision/protocol/source records for scientific constraints; maintainer's native Windows outputs for local acceptance. An independent agent is optional for *specific evidence gaps or code review*, not a replacement for these records.
