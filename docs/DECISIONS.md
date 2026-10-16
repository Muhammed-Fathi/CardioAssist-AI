# Decision Register

> **Operating note (updated 2026-10-16):** Phase 0 is complete — PR #1
> (`docs: Phase 0 feasibility review and source integrity fix`, merge commit
> `0ae333f`) is merged into `main`, including
> `docs/phase0/PHASE0_REVIEW_DRAFT.md` (Rev. 3, with the final UCI
> target-label clarification: `num` supports presence classification 0 vs 1–4
> only; severity/ordinal modelling remains UNAPPROVED) and the corrected
> `research/source_materials/SOURCE_MANIFEST.sha256`. The Phase 0 report
> records its proposed decisions D-011…D-033 in its own register (§13 /
> §R2-9); to avoid ID collisions, this file's Phase 1 entries continue at
> D-034. Phase 1 additions below were recorded per explicit maintainer
> instruction and, like every change to `main`, take effect only after human
> PR review and merge. Confirmed decisions D-001…D-004 are unchanged.

## Phase 0 and earlier (D-001 … D-010)

| ID | Decision | Current status | Approver / rationale |
|---|---|---|---|
| D-001 | Project budget is $0 | CONFIRMED by project team | No mandatory paid services |
| D-002 | Use Arena Agent with GitHub repo-first workflow | CONFIRMED by project team | Persist reviewed work across sessions |
| D-003 | Supervisor paper classification follows first-tab title cell colors | CONFIRMED by project team | Green approved; pink/orange conditional; red rejected |
| D-004 | Presentation defines requirements/vision, not authoritative datasets or papers | CONFIRMED by project team | Review all scientific claims independently |
| D-005 | Private GitHub monorepo | PROPOSED | Owner/team to create and approve |
| D-006 | Precise ML prediction target and horizon | **OPEN** — pending approval P-1 | Research lead + supervisor; depends on labeled data. Track A adopted as a *track* (D-038) does not freeze the final target or the model evaluation protocol |
| D-007 | Selected datasets / redistribution and human data handling | **OPEN** — pending approvals P-2, P-3 | Research lead + supervisor; needs license review. The multi-dataset strategy (D-040) is adopted, but each dataset still requires its own acquisition authorization (Gate DA) before any download |
| D-008 | Deployment stack and model serving topology | **CONFIRMED** by maintainer 2026-10-16 | Resolved by the Phase 1 baseline: D-036 (unified versioned FastAPI backend), D-037 (backend responsibilities), D-041 (local-first modular monolith at $0) |
| D-009 | Clinically meaningful wearable integrations | **OPEN** — partially resolved | Track B monitoring architecture and the wearable→CAD-inference prohibition are approved (D-039); real wearable integrations and access-dependent features remain PENDING (P-6) |
| D-010 | Research gap / publication contribution | OPEN | Validate against accepted paper full texts and current literature; no novelty claim before the Phase 0 §F-2 / D-025 full-text verification and broader literature search |

## Phase 1 technical decision baseline — maintainer-approved (D-034 … D-043)

Recorded 2026-10-16 after the maintainer merged Phase 0 PR #1. These are
**technical/architectural directions**; they do not settle any scientific
target, dataset access, protocol, clinician-wording, or validation question
— those remain in the pending table below.

| ID | Decision | Status | Approver / rationale |
|---|---|---|---|
| D-034 | The patient frontend is a **Flutter mobile application** | **APPROVED** | Maintainer (Phase 1 baseline). Flutter app is core scope per the Phase 0 preservation rule (§R2-3, C3/G6); Android-first local testing (emulator + physical device) at $0 per §R2-7.4; iOS build and store release remain out of scope |
| D-035 | The clinician frontend is a **React + TypeScript website** | **APPROVED** | Maintainer (Phase 1 baseline). Dashboard per Phase 0 §R2-7.3 (C1/C2/C4) on demo/benchmark data only; no PHI |
| D-036 | Both frontends communicate through a **unified versioned FastAPI backend** (`/v1`, one contract) | **APPROVED** | Maintainer (Phase 1 baseline). Resolves D-008's API/serving layer; contract shape per Phase 0 §R2-6, to be frozen by the M1a contract review |
| D-037 | The backend handles **authentication, authorization, patient records, monitoring, inference integration, audit logging, and clinician review** | **APPROVED** | Maintainer (Phase 1 baseline). Aligns with the Phase 0 §R2-1 unified-platform services and §R2-7.2 workstream B; prototype-grade security only (§7.5); no PHI; no regulatory-compliance claims |
| D-038 | **Track A is clinical CAD classification with SHAP/LIME explainability and clinician review** | **APPROVED** (as a track) | Maintainer (Phase 1 baseline). Adopts the Phase 0 §R2-1/§R2-2 two-track separation (D-023) and explanation rules (§R2-5.7, §R2-6.5). The final scientific target and model evaluation protocol remain **PENDING** (P-1); D-006 stays OPEN; Phase 0 T1 remains the working assumption only |
| D-039 | **Track B is patient and wearable monitoring; wearable observations must not feed CAD inference without separately validated scientific evidence** | **APPROVED** | Maintainer (Phase 1 baseline). Binding one-way rule per Phase 0 §F-4/§R2-6.2 — wearable payloads to CAD inference fail with `422 wearable_input_not_valid_for_cad_inference`; contract test F-09 enforces it. Real wearable integrations remain **PENDING** (P-6); D-009 stays OPEN |
| D-040 | The project uses a **multi-dataset research strategy with explicit compatibility, overlap, licensing, and leakage gates** | **APPROVED** (as a strategy) | Maintainer (Phase 1 baseline). Per Phase 0 §R2-4 (strategies A–D, the §R2-4.2 harmonization/leakage conditions, and the §R2-4.4 pre-download checklist). Does **not** authorize any dataset acquisition — each dataset needs its own Gate DA authorization (P-2); D-007 stays OPEN |
| D-041 | The architecture is a **local-first modular monolith**, maintaining the **$0 budget** | **APPROVED** | Maintainer (Phase 1 baseline). Resolves D-008's serving topology; consistent with D-001; microservices/Kafka/Kubernetes topology deferred per Phase 0 §7.1–§7.3; free-tier hosting remains optional and disposable (§7.4) |
| D-042 | **Flutter and React are both core project components; neither may be silently removed** | **APPROVED** | Maintainer (Phase 1 baseline). Codifies `docs/FEATURE_REGISTER.md` ("never remove a feature silently") and the Phase 0 Rev. 2 preservation rule; any future removal requires an explicit new decision entry in this register with human approval |
| D-043 | The **first implementation milestone is M1a: versioned API contracts, deterministic mock CAD/XAI responses, contract tests, and minimal integration scaffolding** | **APPROVED** | Maintainer (Phase 1 baseline). Per Phase 0 §R2-7.6 M1a: mock/simulated data only (fixtures F-01–F-12); no real models, no datasets, no training; sequence remains M1a → M1b → M2 → M3 → M4, each an independently reviewable PR |

## Pending approvals — explicitly preserved, NOT approved

The following were **not** approved by the Phase 0 merge and are **not**
approved by the baseline above. Each requires its own explicit human
sign-off before the dependent work starts.

| # | Pending approval | Status | Gate / approver |
|---|---|---|---|
| P-1 | **Final scientific target and model evaluation protocol** | PENDING | Research lead + supervisor (D-006); protocol frozen at Gate PT (Phase 0 §R2-5.1, D-024/D-032) |
| P-2 | **Individual dataset acquisition authorization (Gate DA)** | PENDING | Named human data-access authorization listing the exact datasets (D-031, Phase 0 §R2-5.1); local-only acquisition into out-of-git storage, read-only audit, no fitting/selection/tuning/evaluation; no download before it |
| P-3 | **Supervisor approval of the frozen pre-training protocol (Gate PT)** | PENDING | Supervisor sign-off after the Gate DA read-only audit, before any model fitting, feature selection, hyperparameter tuning, or performance evaluation (D-032, Phase 0 §F-3) |
| P-4 | **Clinician approval of medical explanation and safety wording** | PENDING | Named clinician reviewer (D-016/D-026); conservative-copy fallback until then; no alert thresholds or treatment-recommendation language (Phase 0 §2.1, §R2-2.1) |
| P-5 | **Any claims of external validation or clinical readiness** | NOT MADE — prohibited | Requires external validation completed under the frozen protocol; governed by the `validation_status` lifecycle and serving policy (D-033, Phase 0 §R2-5.9/§R2-6.4) and the claims discipline (§R2-5.9); internal-only models are served and labelled strictly as such |
| P-6 | **Real wearable integrations and access-dependent features** | PENDING | Named device owner, developer-account resolution at $0, and vendor approvals per Phase 0 §10 (D-019); simulated adapter only until then; wearable data never feeds CAD inference (D-039) |

## Standing rules

- Status vocabulary: **CONFIRMED** (project team), **APPROVED** (maintainer,
  this baseline), **PROPOSED**, **OPEN**, **PENDING** (awaiting a named
  human gate), **NOT MADE — prohibited** (no such claim exists anywhere in
  project materials and none may be added).
- Nothing in this register authorizes dataset downloads, model training,
  deployment, or clinical, novelty, or external-validation statements.
- Merging any PR (including the Phase 0 report) never auto-approves a
  pending item; each P-item closes only through its own recorded human
  approval.
- Phase 1 proceeds milestone-by-milestone (M1a → M1b → M2 → M3 → M4 per
  Phase 0 §R2-7.6 / §F-5), each as its own scoped, human-reviewed PR.
