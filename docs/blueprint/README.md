# CardioAssist AI — Master Product & Research Blueprint (documentation set)

**Status:** This is a planning/traceability document set, not blanket
implementation authorization. Updated on 2026-10-17 to reflect D-045: the
first authorized implementation slice is M1b.1 (durable SQLite foundation on
an existing monitoring path); the React/Flutter M1a.3 integration is
deferred/resequenced, not cancelled or completed. This set does **not**
authorize work beyond M1b.1, dataset download, model training, new API
contracts, or clinical claims. Research/data/clinical approvals and all
remaining implementation authorizations stay governed by `docs/DECISIONS.md`.

**This set never duplicates authority.** Where a statement is already
governed elsewhere, this set cites the source and defers to it:

| Authority | Governs |
|---|---|
| `AGENTS.md`, `docs/DECISIONS.md` | Operating rules, decision register, pending approvals |
| `docs/phase0/PHASE0_REVIEW_DRAFT.md` (Rev. 3) | Scientific feasibility, datasets, protocol, risks, gates DA/PT |
| `docs/FEATURE_REGISTER.md` | Proposed feature register F01–F12 and its preservation rule |
| `shared/contracts/README.md` + `shared/contracts/openapi.yaml` | Approved `/v1` wire contract (M1a.1) and its open questions |
| `backend/CONTRACT_NOTES.md`, `backend/VERIFICATION.md` | Existing mock-backend behavior, A-01 technical correction (PR #7/#8 merged), remaining ambiguities and verification record |
| `docs/M1A3_INTEGRATION_HANDOFF.md` | Preserved handoff plan for deferred/resequenced M1a.3; not a current implementation authorization |
| `docs/DECISIONS.md` (D-045) | Current execution-priority ordering and authorization for M1b.1 only |
| `research/source_materials/` (PDF + speaker notes + CSV/XLSX) | Product vision (47 slides) and supervisor paper classification |
| [`docs/research/gate-da/`](../research/gate-da/README.md) | **PROPOSED** Gate DA dataset-suitability and decision package (2026-10-20): candidate matrix/ranking, leakage & target-harmonization register, Gate DA approval packet, NOT-APPROVED Gate PT outline, clinician-input feasibility, open decisions, phased handoff. Prepares P-2/P-1 decisions; authorizes no acquisition, training, schema, or contract change |

## Deliverable map (task items 1–8 + ADR)

| # | Deliverable | File |
|---|---|---|
| 1 | Master architecture and delivery blueprint | [01_MASTER_ARCHITECTURE_AND_DELIVERY_BLUEPRINT.md](01_MASTER_ARCHITECTURE_AND_DELIVERY_BLUEPRINT.md) |
| 2 | Exhaustive traceability / feature matrix | [02_FEATURE_TRACEABILITY_MATRIX.md](02_FEATURE_TRACEABILITY_MATRIX.md) |
| 3 | Milestone roadmap and dependency graph | [03_MILESTONE_ROADMAP_AND_DEPENDENCIES.md](03_MILESTONE_ROADMAP_AND_DEPENDENCIES.md) |
| 4 | Database and API integration design | [04_DATABASE_AND_API_INTEGRATION_DESIGN.md](04_DATABASE_AND_API_INTEGRATION_DESIGN.md) |
| 5 | Research methodology and approval-gate plan | [05_RESEARCH_METHODOLOGY_AND_APPROVAL_GATES.md](05_RESEARCH_METHODOLOGY_AND_APPROVAL_GATES.md) |
| 6 | Local testing and milestone acceptance matrix | [06_TESTING_AND_ACCEPTANCE_MATRIX.md](06_TESTING_AND_ACCEPTANCE_MATRIX.md) |
| 7 | Open decisions, risks, assumptions, $0-budget constraints | [07_OPEN_DECISIONS_RISKS_ASSUMPTIONS.md](07_OPEN_DECISIONS_RISKS_ASSUMPTIONS.md) |
| 8 | Current implementation status versus future scope | [08_IMPLEMENTATION_STATUS_VS_FUTURE_SCOPE.md](08_IMPLEMENTATION_STATUS_VS_FUTURE_SCOPE.md) |
| ADR | CAD optional-null JSON Schema / backend compatibility issue (A-01) — **Option A approved** (D-044); PR #7/#8 merged, technical correction complete | [ADR_001_CAD_OPTIONAL_NULL_FEATURE_VALUES.md](ADR_001_CAD_OPTIONAL_NULL_FEATURE_VALUES.md) |

## Reading order for a new developer

1. `README.md` (repo root) and `AGENTS.md` — operating rules.
2. `docs/DECISIONS.md` — decisions D-034…D-045, current M1b.1 authorization, and pending approvals/gates (including P-1…P-6).
3. This file, then **01** (architecture) → **03** (what to build when) →
   **02** (feature-by-feature detail) → **04** (data/API) → **06** (how a
   milestone is accepted) → **05** (research gates) → **07**/**08** (open
   items and honest status).
4. Before touching contracts: `shared/contracts/README.md` and
   `backend/CONTRACT_NOTES.md`, including **ADR-001**.

## Standing constraints inherited by every document in this set

- **$0 budget** (D-001): no paid services, no card-required trials.
- **MOCK ≠ AI:** all current CAD/XAI output is deterministic synthetic
  fixture data (`MOCK_SYNTHETIC`); no model has been trained and no
  performance claim exists anywhere in this project.
- **Track separation** (D-038/D-039): wearable/monitoring data never feeds
  CAD inference (`422 wearable_input_not_valid_for_cad_inference`, fixture
  F-09).
- **Gates** (Phase 0 §F-3): Gate DA before any dataset download; Gate PT
  before any model fitting/selection/tuning/evaluation. Neither is open.
- **No clinical claims** (P-4/P-5): no diagnosis, no personal risk %, no
  alert thresholds, no treatment advice, no external-validation or
  clinical-readiness claims.
- **Every milestone ends with reproducible local tests and human review**
  before merge. The agent never self-approves or self-merges.
- **No silent feature deletion** (`docs/FEATURE_REGISTER.md`): the vision is
  preserved in the traceability matrix (02); blocked items are labelled with
  the named blocker, not removed.
- **M1a.3 is deferred/resequenced by D-045, not cancelled or completed.**
  The plan remains in `docs/M1A3_INTEGRATION_HANDOFF.md`; it is not the current
  slice. M1b.1 is authorized first. React/Flutter remain thin local
  integration/demo clients.
- **D-045 execution priority:** genuine, reproducible CAD AI research and
  inference; then a complete, integration-ready FastAPI backend; then durable,
  tested database. This ordering does not waive scientific/data/clinical gates,
  authorize datasets or training, or change the `/v1` contract.
- **Research completion (M4) ≠ product completion:** full product delivery
  requires the M5 product track (F14–F17 are required deliverables, not
  optional) plus the capability/device-dependent Health Connect plan with
  simulator fallback (03 §4).
- **Clinical laboratory data boundary (binding):** wearable/monitoring data
  never feeds the existing CAD model; clinician-verified lab measurements
  become Track-A-eligible only via the six-condition checklist in 05 §2.1 —
  verification alone never implies model eligibility.
