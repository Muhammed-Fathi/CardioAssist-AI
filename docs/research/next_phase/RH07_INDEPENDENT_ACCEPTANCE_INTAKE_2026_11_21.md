# RH-07 — independent acceptance intake and scoped evidence map (2026-11-21)

**State:** `INDEPENDENT_REVIEW_INTAKE_NOT_ACCEPTED`. This is a read-only source/evidence inventory for the *research-only graduation prototype*, **not** final manuscript, independent original-experiment verification, professional review, or clinical approval.

**Pinned main at intake:** `8d471b4b135f7c5488210e18157aab1fcc5d6495` (merged PR #127). **Controlling scientific/architecture decisions:** [merged PR #118](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/118) and `RH06_EVIDENCE_BOUNDED_RESEARCH_PROTOTYPE_DESIGN_DECISIONS_2026_11_19.md`.

**How to interpret:** An evidence path means a source or archived *reported* artifact exists for reviewer inspection. It is **never** a passed acceptance gate by itself. All 15 gates remain `EVIDENCE_LOCATED_REVIEW_REQUIRED` / independent review `PENDING`. Empty reviewer fields are intentional. The historical completion tracker has stale statuses; this document neither overwrites nor silently promotes them.

## Fifteen acceptance checks from the reviewed RH charter

| ID | Check | Linked repository evidence | Unresolved independent review question |
|---|---|---|---|
| AC-01 | Research target, population, prediction moment, non-use claims | `docs/research/next_phase/AI12_2_GRADUATION_RESEARCH_MANUSCRIPT_DRAFT_2026_11_19.md`; `docs/research/next_phase/RH06_EVIDENCE_BOUNDED_RESEARCH_PROTOTYPE_DESIGN_DECISIONS_2026_11_19.md` | Intended pre-reference moment and patient-level clinical utility are not independently established; reviewer must verify final scientific wording. |
| AC-02 | Dataset rights, provenance, overlap and admissibility | `docs/research/next_phase/RH02_RH03_CONSOLIDATED_RESEARCH_HANDOFF_2026_11_19.json`; `docs/research/next_phase/RH02_SOURCE_QUESTION_REGISTER_2026_11_19.json` | Source/rights/timing questions remain open; do not promote UCI-412, Hungary, UCI-411 or AngioCAD. |
| AC-03 | Historical D-047 and M3a numeric result provenance | `docs/research/gate-pt/04_d047_first_internal_results_REVIEW_DRAFT.md`; `docs/research/gate-pt/11_two_dataset_scientific_evidence_synthesis_REVIEW_DRAFT.md`; `docs/research/next_phase/RH03_AI12_2_AUDIT_MATRIX_2026_11_19.json` | Source-to-manuscript table values are transcribed but protected original runs were not independently rerun/attested. |
| AC-04 | Fold-safe preprocessing, training and leakage review | `ai/research_registry.py`; `docs/research/next_phase/RH03_AI12_2_INDEPENDENT_AUDIT_2026_11_19.md` | No fresh audit of protected patient-level fold assignments; code and historic protocol inspection are separate evidence. |
| AC-05 | Discrimination, calibration and uncertainty limitations | `docs/research/next_phase/AI12_2_GRADUATION_RESEARCH_MANUSCRIPT_DRAFT_2026_11_19.md`; `docs/research/gate-pt/05_m2e1_sample_size_research_ADEQUACY_REVIEW_DRAFT.md` | Dependent-repeat SD is not a CI; clinical calibration, precision, subgroup evaluation and external performance not established. |
| AC-06 | SHAP/LIME fidelity, background and non-causal interpretation | `ai/explainability.py`; `ai/lime_explainability.py`; `ai/lime_quality.py` | Offline synthetic explanation maths has software tests; no clinical causal/individual-patient explanation validated. |
| AC-07 | Source-specific field units, acquisition, refusal rules | `docs/research/next_phase/RH04_1_2_FEATURE_ACQUISITION_EVIDENCE_CROSSWALK_2026_11_19.md`; `docs/research/next_phase/RH04_OFFLINE_FIXTURE_HANDOFF.md` | UCI-412 original 16/16 acquisition times still not owner-verified; synthetic input is not prospective admissibility. |
| AC-08 | AI-9.2 labs and AI-10.2 external study dispositions | `docs/research/next_phase/RH06_EVIDENCE_BOUNDED_RESEARCH_PROTOTYPE_DESIGN_DECISIONS_2026_11_19.md`; `docs/research/next_phase/RH02_RH03_CONSOLIDATED_RESEARCH_HANDOFF_2026_11_19.json` | Real paired labs and Hungary external experiments are NO-GO/NOT_PERFORMED in current scope; no results may be inferred. |
| AC-09 | Model inventory, cards and synthetic worked I/O | `ai/research_catalog.py`; `docs/research/ai12_1/linux-uci45-envelope.v1.json`; `docs/research/next_phase/RH04_OFFLINE_FIXTURE_HANDOFF.md` | One published synthetic Cleveland card exists inside an envelope; UCI-412 synthetic and historic research models lack equivalent finalized standalone reviewed cards. |
| AC-10 | Signing, integrity, privacy, Track A/B, mock-only serving | `backend/app/inference/registry.py`; `docs/research/next_phase/RH05_INDEPENDENT_ACCEPTANCE_REVIEW_2026_11_20.md` | Existing synthetic/security evidence is source-bound; it does not authorize medical serving or rule out all deployment risks. |
| AC-11 | Exact-source CI, native Windows and reproducible demo | `docs/research/next_phase/RH05_ACCEPTANCE_MANIFEST_2026_11_20.json`; `docs/research/next_phase/RH05_INDEPENDENT_ACCEPTANCE_REVIEW_2026_11_20.md` | RH-05 accepted engineering evidence uses its own precise tested SHAs; 2909/3 Windows outcome is maintainer reported, and no final release SHA run is claimed. |
| AC-12 | 17-chapter manuscript, reporting frameworks and figures | `docs/research/next_phase/AI12_2_GRADUATION_RESEARCH_MANUSCRIPT_DRAFT_2026_11_19.md`; `docs/research/next_phase/RH03_REPORTING_CROSSWALK_2026_11_21.json` | 27 TRIPOD+AI main items are drafted, 52 subitems not finalized, PROBAST+AI not assessed, no protected ROC curves reconstructed. |
| AC-13 | Independent scientific and engineering review | `docs/research/next_phase/RH03_AI12_2_AUDIT_MATRIX_2026_11_19.json`; `docs/research/next_phase/RH03_AI12_2_INDEPENDENT_AUDIT_2026_11_19.md` | 9 source-text limited matches and 19 NOT_VERIFIABLE are not complete scientific verification; all 10 reviewer actions remain pending. |
| AC-14 | Release README, handoff and frozen source SHA | `docs/research/next_phase/AI_RESEARCH_PROTOTYPE_COMPLETION_CHARTER_2026_11_19.md`; `docs/research/next_phase/AI12_2_FINAL_REPORT_BLUEPRINT_2026_11_19.md` | RH-08 final release bundle, complete reviewed handoff and exact accepted release SHA have not been prepared/accepted. |
| AC-15 | Owned, explicit in-scope gaps and claim boundaries | `docs/research/next_phase/AI_RESEARCH_COMPLETION_TRACKER_2026_11_19.json`; `docs/research/next_phase/RH03_REPORTING_CROSSWALK_2026_11_21.md` | Tracker is a stale 2026-11-19 snapshot and cannot automatically mark milestones closed; gaps need owner/reviewer assignment and evidence decisions. |

## Immediate reviewer work

1. Inspect each linked source and its scope, not simply its presence. Distinguish committed text transcription, original experiment verification, source policy, synthetic model tests and maintainer-reported Windows evidence.
2. Author the missing approved model cards (not an inference deployment) and review the actual 5-entry registry. Use the companion [model-card inventory](RH07_MODEL_CARD_INVENTORY_2026_11_21.md).
3. Review 27 TRIPOD+AI main-item gap mappings; the original 52 subitems and formal PROBAST+AI analysis are **not** complete. Do not recast `NOT_REPORTED`, `NOT_PERFORMED` or `NOT_ASSESSED` as passes.
4. Leave the 28 scientific claim statuses (9 narrow source-text matches, 19 not independently verifiable) and 10 human review actions unchanged unless new direct evidence is actually obtained.
5. Keep PR #126's unexplained intermittent replay as a **documented unresolved cause**, not as an unobserved source bug or an excuse to weaken golden cases.
6. For RH-08, require a new versioned handoff index, source/release SHA, current CI review, a scope-correct Windows evidence plan, independent findings/dispositions and actual maintainer acceptance.

## Source custody and limits

- Source-to-manuscript numeric transcription (48/48 reported in the earlier review) is not independent protected-data reproduction or clinical validation.
- Cleveland DA-A2 D-047 and UCI-412 M3a are distinct historical internal exploratory cohorts; never pool or compare their AUROCs as a source performance contest. The threshold distinction `>50%` versus `≥50%` remains unresolved at the boundary.
- UCI-412 16-feature pre-reference acquisition chronology remains owner-unverified. Real AI-9.2 labs and AI-10.2 Hungary external evaluation remain scoped NO-GO/NOT_PERFORMED; source holds unchanged.
- Mock backend remains `MOCK_SYNTHETIC`; SHAP/LIME research explanations are model/scale-specific non-causal synthetic/offline evidence.
- No source patient records, private report files, signatures, medical approvals, original ROC curves, or real deployment claim are added here.

Machine-readable matrix: [RH07_INDEPENDENT_ACCEPTANCE_INTAKE_2026_11_21.json](RH07_INDEPENDENT_ACCEPTANCE_INTAKE_2026_11_21.json). The read-only validator `scripts/verify_rh07_acceptance_intake.py` checks the 15-row index, file existence and non-promotion constraints, not scientific truth or Git blob attestation.
