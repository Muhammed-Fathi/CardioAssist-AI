# CardioAssist AI — Graduation delivery roadmap and acceptance register

**Document ID:** CAI-GRAD-ROADMAP-v1  
**Prepared:** 2026-11-22  
**State:** Maintainer-requested planning record; pending PR review/merge. No new scientific or implementation authorization.  
**Verified main baseline:** `5549b3169541fdd3896b05dc4e4c1b40f18b778d`

## 1. Purpose and authority

Finish a defensible, reproducible research-only AI prototype, then review the existing application integration and prepare graduation delivery. This is the operational order and index of evidence, not a replacement for the existing canonical records:

- [Agent instructions](../AGENTS.md) and [decision register](DECISIONS.md).
- [Master AI completion plan](research/CARDIOASSIST_AI_MASTER_COMPLETION_PLAN.md) and [canonical AI progress](research/ai_master_progress.json).
- [RH completion charter](research/next_phase/AI_RESEARCH_PROTOTYPE_COMPLETION_CHARTER_2026_11_19.md), [RH execution tracker](research/next_phase/AI_RESEARCH_COMPLETION_TRACKER_2026_11_19.json), [evidence template](research/next_phase/AI_RESEARCH_EVIDENCE_LOG_TEMPLATE_2026_11_19.md).
- [Merged RH-06 decisions RD-01–RD-10](research/next_phase/RH06_EVIDENCE_BOUNDED_RESEARCH_PROTOTYPE_DESIGN_DECISIONS_2026_11_19.md) (PR #118).
- [RH-04 Issue #132 decision record and V2-01–V2-10](rh04-issue132-acceptance-decision.md).
- [Application blueprint](blueprint/) and existing API, persistence and integration contracts.

In conflicts, the controlling decisions, authorization and scientific source records prevail. No roadmap row authorizes work by itself. Each next implementation slice requires maintainer scope authorization. No change to any existing gate, decision, threshold, dataset or API is made by this document. Existing historical tracker statuses are not silently overwritten: reconcile them with verified evidence in the appropriate closeout PR.

## 2. Execution order and exit gates

Acceptance order: **RH-04 → RH-05 → RH-03 → RH-07 → RH-08 → application integration → system acceptance → graduation delivery.** Read-only scientific research, evidence inventory, and eligible reporting can run in parallel, but final acceptance follows dependency order. RH-00/01/02/06 are existing foundations; reconcile their canonical status and residual gaps rather than restart completed work.

| ID | Current planning status | Deliverable and exit gate | Correct evidence destination |
| --- | --- | --- | --- |
| RH-00 | EXISTING EVIDENCE; RECONCILE | GitHub baseline, reconciled tracker and closeout evidence; no stale status claims | RH-00 reconciliation + canonical tracker |
| RH-01 | EXISTING EVIDENCE; RECONCILE | Source-bound claim inventory, gap dispositions, evidence grades and privacy | RH-01 evidence index and gap matrix |
| RH-02 | EXISTING EVIDENCE; RECONCILE | Eight source roles, scientific admissibility and documented holds/no-go; unresolved facts never treated as verified | RH-02 source registers and audit docs |
| RH-06 | DESIGN MERGED, SCOPED | PR #118 RD-01–RD-10 design decisions; preserve scientific boundaries; not clinical or final prototype acceptance | RH-06 decision record, governed decision register |
| RH-04 | CURRENT / IN_PROGRESS | Correct source-specific synthetic full 29-case reference, reproducible OOF methodology, strict identity, fail-closed replay, source/route contracts; complete V2-01–10 incl. owner ratification and retirement before closing #132 | RH-04 protocol/fixtures/tests/mapping, acceptance record, issue #132 |
| RH-05 | PARTIAL EVIDENCE / FINAL VERIFICATION PENDING | Exact candidate SHA Linux 3.11/3.12 and native Windows; resolved kernels, full regression, artifact signing, tamper/refusal, leakage/privacy/security, dependency checks | RH-05 acceptance manifest and independent review; platform logs |
| RH-03 | DRAFT MATERIAL / FINAL REVIEW PENDING | Finish manuscript and methods audit (17 chapters and 28-claim inventory to reconcile); original source citations, figures, evidence grades, within-cohort metrics, limitations and exact implementation alignment | RH-03 manuscript, claim/figure provenance, AI-12.2 blueprint |
| RH-07 | PARTIAL EVIDENCE / ACCEPTANCE PENDING | Review all 15 acceptance criteria, model cards, TRIPOD+AI reporting, PROBAST+AI question/applicability workbook, sample adequacy, calibration and explainability evidence; explicit unresolved and NOT_ASSESSED dispositions | RH-07 acceptance intake, model cards, appraisal workbooks |
| RH-08 | PENDING | Freeze exact accepted release; final manuscript, runnable offline demo, reproducibility/install instructions, release/rollback manifest, evidence ledger; no silent gaps | RH-08 final handoff, release manifest, canonical tracker |
| APP-01 | PLANNED / SEPARATE AUTHORIZATION | Audit existing backend, durable DB and thin clients; reconcile D-045 priority and M1a.3 status; propose bounded implementation slices only after inventory. Versioned API contracts, auth/RBAC, persistence/migrations where separately authorized, input/error handling and mock integration tests | Existing blueprint/contract/architecture docs, backend and client tests, scoped ADRs |
| APP-02 | PLANNED / SEPARATE AUTHORIZATION | System workflow and product acceptance: approved roles, permissions, safe UI states, no stale results, synthetic end-to-end scenarios, privacy, performance and deployment constraints | System acceptance matrix, integration/security evidence, scoped issues |
| GRAD-01 | PLANNED | Final SRS, ERD, use case, sequence, activity, class and architecture diagrams as applicable; reproducible demo, presentation, installation, defense questions and traceable release | Graduation delivery index, diagrams and presentation sources, release link |

RH-08 acceptance target: `RESEARCH_PROTOTYPE_HANDOFF_ACCEPTED`. This is never `CLINICALLY_VALIDATED` or `PATIENT_READY`. APP-01/02 are planning aliases, not new approved milestones or API/clinical scope.

## 3. Current checkpoint — RH-04

Verified GitHub state at preparation:

| Record | Exact head / state | Disposition |
| --- | --- | --- |
| #118 | [Merged design decisions](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/118) | Preserve RD-01–10 |
| #136 | [Merged P4 decision](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/136) | V2 proposal not ratified |
| #137 | `729a610b796c17c830c6c80286c5a0d41a55cac1`, draft/open | No merge; distinct forced-dispatch diagnostic unresolved |
| #138 | `2469dc6063545e7b936e19c609bafc0bd64572d2`, draft/open | historical V2 candidate |
| #139 | `091b26cb2c223262553ba5b78c1995dfcdb14821`, draft/open | current candidate; REQUEST CHANGES in independent chat review; not a posted GitHub review |
| #132 | [Open reproducibility issue](https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/132) | close only after complete accepted V2, owner V1 retirement and RH-07/08 risk reconciliation |

Previous #139 head `1aa0b28b72c9d7a65b6cdab9ccb92789c51e4ac9`: [hosted CI run 45036540649](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/45036540649), both synthetic jobs 1889 passed/2 skipped plus UCI-412 396 passed each; separate V1 diagnostic failed (two calibrated-log-odds deltas). These results do not certify `091b26c`. At independent review no exact-head workflow/check runs were returned. Arena reports 113 local candidate tests passed; not independently executed. The small integrated numerical experiment is not full 29-case replay. Preserve its historical digest as experimental evidence, not an accepted reference.

### RH-04 immediate acceptance backlog

- [ ] Correct intercept/slope ordering in integrated calibration; verify against independent calculations.
- [ ] Declare and test distinct Cleveland liblinear (penalized intercept) and UCI-412 generic lbfgs (unpenalized intercept) objectives and actual profile configuration.
- [ ] Integrate actual synthetic cohorts, source-specific preprocessing, registered model selection/folds and out-of-fold calibration; preserve selected family semantics, all five routes and all 29 executed responses.
- [ ] Compare deterministic refitting (Path A, research oracle) and integrity-bound frozen synthetic parameters (Path B, proposed fast inference); no silent replacement of regeneration or D-V2-7 ratification.
- [ ] Complete independent mathematical oracle, negative tests, raw/semantic digest and source/protocol/provenance binding; no silent oracle or preservation skips.
- [ ] Correct separate child diagnostic helper: both environment and field verdict, actual exit policy, schema, signals/timeouts, fail-closed malformed payloads; no canonical acceptance weakening.
- [ ] Report real downstream boundary/tie/refusal behavior, distinguish SHAP/LIME evidence outside exported replay fields.
- [ ] Verify exact candidate SHA, actual resident dispatch classes (at least three × Linux Python 3.11/3.12), native Windows, all EXACT_REPLAY; correct PowerShell and sanitized evidence.
- [ ] Review V2-01–10 individually, dual-run evidence, owner ratification/retirement, rollback and risk register updates; resolve #133/#134/#137/#138/#139 dispositions with owner. Issue #132 stays open until its actual closure requirements are met.

## 4. Quality workflow (every slice)

1. ChatGPT: independent repository inspection, primary-source research when relevant, technical specification, exact scope, risks and measurable acceptance criteria.
2. Arena: read controlling records and verify base SHA; independently research as needed; implement only authorized scope in isolated branch; negative-first tests and full relevant regression; draft PR with exact evidence.
3. ChatGPT: independent source/diff/code/math/science/security review, actual hosted logs on exact head SHA; independently reproduce key checks where possible. Distinguish agent reports, verified hosted evidence, local execution and unverified claims.
4. Remediate defects on reviewable commits; no self-approval, self-merge, hidden skips, tolerance widening, rerun-to-green, forced CPU pin or unrelated scope expansion. Non-blocking findings go to the proper issue/stage.
5. Owner: explicit review and approval/merge; required domain/governance sign-offs remain separate. Do not fabricate any signature or approval.
6. Verify actual merge SHA and post-merge checks; record acceptance evidence in canonical stage files and update this register in a reviewable PR. Start next slice only under appropriate authorization.

## 5. Evidence recording and register maintenance

This roadmap is an index, not a second competing scientific truth or automated gate. On each accepted increment update its canonical stage documents and applicable tracker, then add a dated row below linking the evidence. Use the existing RH evidence template; preserve prior entries and distinguish current state from historical snapshots. No invented percentage completion.

Each entry must specify: stage/task ID, scope, owner/implementer/reviewer roles, exact base/head/merge SHAs, PR/issue URL, changed files and canonical artifact paths, exact test commands and counts (including skip/failure reasons), workflow/job URLs and platform/library provenance, source citations for scientific claims, negative tests, limitations and unresolved risks, actual acceptance decision/owner record, post-merge checks and next permitted step. For unavailable evidence state NOT_RUN or UNVERIFIED with specific reason and next owner. Do not store private data, raw patient rows, credentials or local sensitive paths.

Use distinct states: PLANNED, IN_PROGRESS, IMPLEMENTED, TESTED, REQUEST_CHANGES, READY_FOR_OWNER_REVIEW, MERGED_NOT_YET_ACCEPTED, ACCEPTED (only with evidence), BLOCKED_WITH_NAMED_CAUSE, NOT_APPLICABLE_WITH_REASON. One green suite or a merged docs PR does not confer final acceptance.

| Date | Stage / slice | Evidence and status | Remaining action |
| --- | --- | --- | --- |
| 2026-11-22 | Roadmap baseline | main `5549b3169541fdd3896b05dc4e4c1b40f18b778d`; this planning record only | Owner review/merge of roadmap; continue RH-04 corrections |
| 2026-11-22 | RH-04 #139 | [PR #139](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/139), head `091b26cb2c223262553ba5b78c1995dfcdb14821`; REQUEST_CHANGES, no exact-head CI verified | Correct calibration, profiles, actual 29-case path and acceptance evidence |

## 6. Non-negotiable research and product boundaries

Budget $0. Source-defined historical cross-sectional angiography-referenced CAD, not future-event risk, diagnosis or treatment. Cleveland five-field and UCI-412 16-field routes remain distinct; preserve >50% vs ≥50% definitions and all eight source roles, no pooling or assumed overlap independence. Preserve RD-01–10, D-046/47/48, existing DA/PT gates and holds. AI-9.2 real paired labs and AI-10.2 real external validation remain NO-GO / NOT_PERFORMED in the current scope. No new real-data fitting, raw patient data, clinical serving or unauthorized dataset access. Public primary-source research can resolve documented questions; it cannot invent source chronology, patient-level facts or specialist approval. Existing D-047/M3a historical internal records retain their limitations.

Backend remains MOCK_SYNTHETIC; offline research stays separate and cannot be served to patients. Future app work is scoped and approved separately. No paid services or clinical deployment claim. Final delivery may document reviewed scientific limits, but cannot hide missing in-scope engineering evidence.
