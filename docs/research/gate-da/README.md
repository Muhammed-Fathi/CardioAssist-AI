# Gate DA — CAD Dataset Suitability & Decision Package

> **CURRENT STATUS NOTE — 2026-10-22 (supersedes the historical baseline below):**
> D-046 was later human-ratified for local read-only DA-A1/DA-B1/DA-A2 audits only. Real aggregate results and limitations now appear in [the cumulative local audit report](10_m2a_uci412_uci411_evidence_and_decisions.md) (§§9–14). Historical status and “no acquisition” claims below refer to the earlier 2026-10-21 **proposal baseline**, not the current operational state. Protected original files and local audit reports remain Git-ignored. Clinical dataset suitability and Gate PT remain **NOT APPROVED**. See the [DA-A2 clinical suitability signoff packet](11_da_a2_clinical_suitability_review_packet.md), with every supervisor decision still UNFILLED. Raw Cleveland quarantined under Issue #18.



| Field | Value |
|---|---|
| Status | **PROPOSED — awaiting Gate DA decision (P-2 / D-031 / proposed D-046). Nothing in this package is approved, executed, or a dataset acquisition.** |
| Date | 2026-10-21 (updated for M2a after PR #10 merge `fb928bb96d000044c3a8617767c345555ea8c683`) |
| Starting baseline | Verified `main` = `fb928bb96d000044c3a8617767c345555ea8c683` (PR #10 merge, on top of PR #9 M1b.1 `661876cdfeeb0c22e9cdaca850552ba57c4aa52c`). PR #9 and PR #10 scopes are preserved. |
| M2a addition (2026-10-21) | Adds proposed maintainer-led Gate DA governance decision **D-046** (`PENDING HUMAN ACCEPTANCE`) and separately reviewable internal exploratory protocol proposal **D-046-EP** (`PROPOSED — NOT APPROVED`) in `docs/DECISIONS.md`; implements the $0, Python 3.12-compatible, Windows-local read-only dataset audit toolchain in `research/audit/` with synthetic fixture tests in `tests/audit/`; and documents exact Windows PowerShell handoff steps from `E:\CardioAssist_AI_GitHub_Starter` in [09_m2a_windows_local_audit_handoff.md](09_m2a_windows_local_audit_handoff.md). **No real dataset was downloaded and no model was trained.** |
| Correction (2026-10-20 review) | UCI-45 raw vs processed file identity corrected throughout: `cleveland.data` (59.2 KB) is the 76-attribute **raw** Cleveland file; `processed.cleveland.data` (≈18 KB) is the conventional 14-column benchmark and is now explicitly in the DA-A2 request with a per-file role table (document 04 §1.1), alongside processed/raw pairs for Hungary, Switzerland, and VA. H-01 now asserts **only** the verified threshold-*wording* difference (`>50%` vs `≥50%`); whether exactly-50% records exist or how they were coded is **UNVERIFIED**. UCI-411↔412 status is stated as source-supported same-cohort provenance, with row-level identity reserved as a Gate DA audit task. Facts re-verified against the official UCI dataset-45 page and `heart-disease.names` on 2026-10-20; no dataset file was downloaded. |
| Governing authorities | `AGENTS.md`; `docs/DECISIONS.md` (D-006/D-007 OPEN, D-038…D-045 APPROVED, D-046 PROPOSED/PENDING, P-1…P-6); `docs/phase0/PHASE0_REVIEW_DRAFT.md` Rev. 3 (§4, §5, §R2-4, §R2-5, §F-1…§F-6); `docs/DATA_POLICY.md`; `docs/blueprint/05_RESEARCH_METHODOLOGY_AND_APPROVAL_GATES.md`. **Where this package conflicts with those documents, those documents govern.** |
| Target (provisional) | **T1 — cross-sectional classification of angiographically defined CAD presence** (~50% diameter-narrowing threshold; exact wording is source-specific). Status **PENDING (P-1/D-006)**, not frozen. This is **not** future/30-day cardiovascular risk prediction (Phase 0 §4.1). |

## How to read this package — evidence levels

Every material claim carries one label. Do not promote a claim to a stronger
label without the stated verification step.

| Label | Meaning |
|---|---|
| **VERIFIED** | Checked in this session (2026-10-20) against the official source page or this repository (method stated). |
| **VERIFIED-PH0** | Verified against an official/primary source in Phase 0 (2026-10-16) and recorded in Phase 0 §14; **not** re-fetched this session. Must be re-snapshotted at acquisition. |
| **SOURCE-REPORTED** | As recorded in `research/source_materials/literature_review_status.csv` (supervisor screening record) or a cited paper's abstract/record. Not checked against full text or data. Never cite as project evidence. |
| **UNVERIFIED** | Not checked. Stated only to mark the gap and the step that would close it. |
| **REQUIRES APPROVAL** | Blocked on a named human gate (Gate DA/P-2, Gate PT/P-3, supervisor, clinician, or a dataset-scope decision such as D-021). |
| **PROPOSED** | Recommendation in this package. Requires human approval; not a decision. |

Supervisor-status rule (binding, D-003): **GREEN = supervisor-selected paper,
not an approved dataset.** Each dataset below still needs its own Gate DA
authorization (D-040, P-2).

## Contents

| # | Deliverable (task item) | File |
|---|---|---|
| 1 | Dataset-source and suitability matrix with traceable references | [01_dataset_source_and_suitability_matrix.md](01_dataset_source_and_suitability_matrix.md) |
| 2 | Candidate ranking with explicit eligibility criteria and limitations | [02_candidate_ranking.md](02_candidate_ranking.md) |
| 3 | Leakage and target-harmonization register | [03_leakage_and_target_harmonization_register.md](03_leakage_and_target_harmonization_register.md) |
| 4 | Gate DA approval packet (exact datasets, prerequisites, storage, verification, approval requests) | [04_gate_da_approval_packet.md](04_gate_da_approval_packet.md) |
| 5 | Proposed Gate PT research-methodology outline — **NOT APPROVED, NOT EXECUTED** | [05_gate_pt_methodology_outline_NOT_APPROVED.md](05_gate_pt_methodology_outline_NOT_APPROVED.md) |
| 6 | Clinician-input feature availability & backend integration feasibility | [06_clinician_input_and_integration_feasibility.md](06_clinician_input_and_integration_feasibility.md) |
| 7 | Decision register — unresolved scientific, access, licensing, privacy, integration questions | [07_decision_register_unresolved_questions.md](07_decision_register_unresolved_questions.md) |
| 8 | Phased handoff — the exact next authorized research task after Gate DA | [08_phased_handoff_after_gate_da.md](08_phased_handoff_after_gate_da.md) |
| 9 | M2a Windows-local read-only dataset audit handoff (`E:\CardioAssist_AI_GitHub_Starter`) | [09_m2a_windows_local_audit_handoff.md](09_m2a_windows_local_audit_handoff.md) |
| 10 | Cumulative DA-A1/DA-B1/DA-A2 real aggregate audit findings and limitations | [10_m2a_uci412_uci411_evidence_and_decisions.md](10_m2a_uci412_uci411_evidence_and_decisions.md) |
| 11 | DA-A2 clinical data suitability review packet — human decisions **UNFILLED** | [11_da_a2_clinical_suitability_review_packet.md](11_da_a2_clinical_suitability_review_packet.md) |
| 12 | Research-team sourced decisions and working strategy; supervisor reviews frozen clinical protocol, not each audit task | [12_research_team_evidence_based_decisions.md](12_research_team_evidence_based_decisions.md) |
| 13 | Evidence-reviewed engineering solution and read-only availability analysis plan | [13_engineering_dataset_solution_and_availability_audit.md](13_engineering_dataset_solution_and_availability_audit.md) |
| 14 | Completed real stage joint-availability analysis and stage-aware intake design decision | [14_real_joint_availability_and_staged_intake_decision.md](14_real_joint_availability_and_staged_intake_decision.md) |

## Headline conclusions (all PROPOSED unless labelled otherwise)

1. **No candidate is approved today.** Gate DA (P-2) and the final target
   (P-1) are both still open. This package prepares that decision; it does
   not make it.
2. **PROPOSED primary development candidates:** UCI Z-Alizadeh Sani
   (id 412) and UCI Heart Disease (id 45, Cleveland cohort first) — the only
   two candidates that simultaneously have (a) an angiographic CAD-presence
   label compatible with T1, (b) a public official source with CC BY 4.0
   stated on the official page (**VERIFIED** this session), and (c) direct
   support in the supervisor-selected (GREEN) evidence base.
3. **PROPOSED external-validation candidate:** the UCI-45 sibling cohorts
   (Hungary first, then VA Long Beach / Switzerland) evaluated under
   Strategy B, **conditional** on the target/feature/missingness
   harmonization audit in document 03. UCI-411, Statlog, Kaggle copies, and
   BRFSS/NHANES/PTB-XL are **not** independent external validation for T1
   (reasons in documents 01–03).
4. **Hard blockers that no ranking overrides:** `ca` and the UCI-45
   per-vessel fields are label-defining/angiography-derived (leakage);
   UCI-411's LAD/LCX/RCA fields define its label (leakage as T1 predictors);
   the UCI-45 `>50%` vs UCI-412 `≥50%` threshold wording differs and is
   **not yet reconciled** (the wording alone does not establish that
   exactly-50% records exist or how they were coded — H-01, document 03); Kaggle "Framingham"/CVD-70K mirrors have
   unverified provenance and **must not be acquired**; official Framingham
   is controlled-access (BioLINCC application + IRB evidence + DUA) and is
   a different (longitudinal, T4) target.
5. **No performance numbers exist for this project.** Every accuracy/AUC
   figure in this package is **SOURCE-REPORTED** from the screening record
   and is labelled as such, including the red-flag values (100%, >97%)
   that must be treated as claims to audit, never targets to beat
   (Phase 0 §3.2).

## Baseline and integrity verification performed for this package

| Check | Result (2026-10-20) |
|---|---|
| `git fetch`; `main` HEAD | `661876cdfeeb0c22e9cdaca850552ba57c4aa52c` — matches the reported PR #9 baseline exactly. No discrepancy found. |
| `python3 scripts/verify_sources.py` | **PASS** — 4/4 SHA-256 hashes OK; supervisor audit: **25 papers, 9 APPROVED_GREEN / 1 MAYBE_PINK / 6 MAYBE_ORANGE / 9 REJECTED_RED**. GREEN IDs re-read from the CSV this session: **P1, P2, P4, P5, P7, P9, P10, P14, P15** (see document 01 §2). |
| Source materials modified? | **No.** No file under `research/source_materials/` was created, modified, re-exported, or overwritten. |
| Existing test baseline (unmodified code) | Fresh venv from `backend/requirements-dev.txt` + `tests/contracts/requirements.txt`: `python -m pytest -q` → **620 passed**; `pip check` → no broken requirements. This confirms the baseline was not altered; it is not a new result for changed code (there is none). |
| Datasets downloaded / models trained | **None / none.** Official dataset pages were read as web pages only; no dataset file was fetched. (This sandbox's egress also cannot reach the dataset hosts directly — acquisition is a local, post-Gate-DA act, document 04.) |

## What this package does not do

- Does not authorize or perform dataset acquisition, model training,
  tuning, fitting, inference on real data, or performance evaluation.
- Does not change any `/v1` request/response schema, fixture, mock
  behavior, `mock_feature_*` / `mock_model_*` identifier, database
  migration, or backend/frontend code.
- Does not implement the separately approved patient-entitlement planning
  proposal (Free / Doctor Trial / Premium). That is a parallel platform
  workstream; subscription access is not clinical authorization and is
  out of scope here (see document 07, Q-INT-4).
- Does not close P-1…P-6, D-006, D-007, D-021, or any contract question
  (Q1–Q14). Unresolved items are listed, not decided, in document 07.
