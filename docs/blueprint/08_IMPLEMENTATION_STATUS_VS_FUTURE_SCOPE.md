# 08 — Current Implementation Status versus Future Scope

**Status:** Snapshot as of 2026-10-17 on `arena/ebc5fdbb-cardioassist-ai`,
baseline merge commit `6c2572c` (PR #5). Verified by re-running the full
suite locally (370 passed, `-W error`) and `scripts/verify_sources.py`
(4/4 hashes). Honesty rule: **no trained model exists; all CAD/XAI output is
deterministic synthetic fixture data (`MOCK_SYNTHETIC`).**

---

## 1. Status taxonomy recap

| Class | Meaning |
|---|---|
| **IMPLEMENTED + TESTED** | In the repo, covered by tests, human-reviewed/merged |
| **SYNTHETIC/MOCK** | Real software producing synthetic results — not AI, not clinical evidence |
| **PROPOSED** | Designed/scheduled, not built |
| **RESEARCH-GATED** | Blocked by Gate DA/PT or dataset/protocol approvals |
| **CLINICALLY-GATED** | Blocked by clinician/supervisor review |
| **ACCESS-GATED** | Blocked by hardware/accounts/vendor/controlled data |
| **PROHIBITED** | Rejected design input; will not be built as described |

## 2. Repository inventory → status

| Path | What exists | Status |
|---|---|---|
| `research/source_materials/` | 47-slide PDF, speaker notes, literature XLSX/CSV, SHA256 manifest | Source of truth (immutable); integrity verified |
| `docs/phase0/PHASE0_REVIEW_DRAFT.md` | Rev. 3 feasibility review (1,822 lines) | Merged (PR #1); governing research document |
| `docs/DECISIONS.md` | D-001…D-043 + P-1…P-6 | Merged; authoritative register |
| `docs/FEATURE_REGISTER.md` | F01–F12 proposed register | Merged; F13–F18 extensions proposed in [02](02_FEATURE_TRACEABILITY_MATRIX.md) |
| `shared/contracts/` | OpenAPI, 4 schema families (common, cad request/response, monitoring request/response, mock feature v1/v2), 2 MOCK_ONLY registries, 30 fixtures (33 steps), fixture index | **IMPLEMENTED + TESTED** (M1a.1, PR #3) — approved artifacts; A-01 pending |
| `tests/contracts/` | 136 tests + deterministic oracle `reference_contract.py` | **IMPLEMENTED + TESTED** |
| `backend/app/` (887 lines: `main.py`, `contracts.py`, `validation.py`, `mock_prediction.py`, `state.py`) | FastAPI mock server: 2 POST endpoints + bundled `/openapi.json`; in-memory idempotency (24 h), audit snapshots, inference counter | **IMPLEMENTED + TESTED + SYNTHETIC/MOCK** (M1a.2, PR #4; cleanup PR #5) |
| `tests/backend/` | 234 HTTP tests (golden bodies, validation, Track separation, replay/conflict, concurrency, expiry, failures) | **IMPLEMENTED + TESTED** |
| `.github/workflows/` | `contracts-ci.yml`, `backend-ci.yml` (installed, executing) | **IMPLEMENTED** (runs must be inspected per commit) |
| `backend/CONTRACT_NOTES.md`, `backend/VERIFICATION.md`, `backend/ci/` | Compat notes (A-01…X-01), verification records, CI notes | Documentation (merged) |
| `docs/M1A3_INTEGRATION_HANDOFF.md` | Approved plan shape for next milestone | Documentation (merged) |
| `frontend/clinician-web/`, `frontend/patient-mobile/` | Placeholder READMEs only (3 lines each) | **PROPOSED** — no code |
| `ai/` | Placeholder README | **PROPOSED** — deliberately empty until M3 |
| `infra/`, `research/experiments/` | Placeholder READMEs | **PROPOSED** |
| `docs/blueprint/` (this set) | Master blueprint docs + ADR-001 | **PROPOSED** (this PR) |

## 3. Feature status snapshot (detail: [02](02_FEATURE_TRACEABILITY_MATRIX.md))

| Capability | Implemented + tested today | Synthetic/mock today | Not built yet |
|---|---|---|---|
| CAD prediction (F01) | Contract, validation, determinism, provenance fields | Mock scoring (SHA-256-derived offsets, mock model registry A/B/C/E; D = 503) | Real trained model (M3, research-gated) |
| Explainability (F02) | Sum-check (log-odds), rendering labels, F-08 fixture | Synthetic SHAP-shaped offsets | Real TreeSHAP/LIME + stability/fidelity (M3) |
| Clinician dashboard (F03) | — | — | Thin screen (M1a.3) → full (M1b) |
| Patient app (F04) | — | — | One screen (M1a.3) → full (M1b) |
| Wearables/monitoring (F05) | Track-B ingestion, consent ref, source labelling, wearable→CAD 422 | `simulated_wearable` source (always-available fallback) | History/trends (M1b); Health Connect capability/device spike (M4, simulator fallback deliverable); vendor (P-6) |
| Reassessment/follow-up (F06) | Read-only `pending_review` state in responses | — | Validity-gated mechanics + notifications/summaries (M1b) |
| Audit/consent (F07) | In-memory events, one-per-write tests | Test-only introspection | Durable audit + consent lifecycle (M1b) |
| FHIR (F08) | — | — | Thin export (M4 opt., D-020) |
| Disease modules (F09) | — | — | Registry (M1b/M4); second module (post-M4) |
| Research workflow (F10) | Methodology documented (Phase 0 §R2-5) | — | M2 audit → M3 models → M4 write-up (research-gated) |
| Auth/RBAC (F11) | — | — | M1b |
| API & tests (F12) | **Complete for M1a scope** (370 tests, CI) | Fixture pack | Grows per milestone (contract-first) |
| History/symptoms/surveys (F13) | — | — | M1b |
| Lab OCR (F14) | — | — | M5 product track (**required** deliverable; $0 local OCR; scheduling authorization pending) |
| Extraction verification (F15) | — | — | M5 product track (**required** deliverable; verification ≠ Track-A eligibility, 05 §2.1) |
| Research-safe assistant (F16) | — | — | M5 (proposed; clinician-gated) |
| Administration (F17) | — | — | Basic M1b; console M5 |
| Persistence/deployment (F18) | In-memory state (documented) | — | SQLite M1b; PG path M4; hosting optional |

## 4. What is explicitly NOT implemented and NOT claimed

- **No real AI.** No dataset acquired, no model trained, no SHAP/LIME
  computed, no accuracy/AUC/calibration result exists in this project.
  Mock scores are synthetic and meaningless as clinical values.
- **No clinical validity.** No diagnosis, risk probability, alert
  threshold, treatment recommendation, or clinical-readiness claim exists
  or may be added (P-5 prohibited).
- **No production service.** No auth, no durable DB, no multi-process
  support, no PHI protection guarantee, no tamper-proof audit, no SLA.
- **No real wearable/device integration**, no push notifications, no
  telehealth integration, no EHR/FHIR server, no app-store release.
- **No lab-report OCR**, no admin console, no assistant — F14–F17 are
  preserved vision only.
- **No external-validation claims**; the research gap remains provisional
  (D-025).

## 5. Near-term future scope (in order)

**Research completion (M4) is not product completion.** M4 closes the
research prototype (integrated walkthrough + TRIPOD+AI write-up). The
product vision additionally requires the M5 product track (F14–F17,
required deliverables) and the capability/device-dependent Health Connect
delivery plan (simulator fallback). Neither completion implies clinical
deployment or regulatory readiness (P-5).

1. **M1a.3** (next planned; **implementation authorization pending** — do
   not start until the maintainer explicitly authorizes): thin React +
   Flutter paths vs the unchanged mock contract, per
   `docs/M1A3_INTEGRATION_HANDOFF.md`; carries A-01 etc.
2. **M1b**: persistence (SQLite→PG path), auth/RBAC, consent + durable
   audit, history/review/reassessment APIs ("M1b.1 contracts first"),
   full dashboard + full patient app, offline sync + batch ingestion,
   basic admin, module registry scaffolding. Clinician/conservative copy
   review closes what it can of P-4.
3. **M2** (after P-2): authorized dataset acquisition + read-only audit.
4. **M3** (after P-3): frozen protocol, real models, real SHAP/LIME,
   calibration, IC-3.
5. **M4** (research completion): integrated prototype, TRIPOD+AI write-up,
   optional FHIR export / Health Connect capability-device spike (with
   simulator fallback deliverable) / disposable hosted demo.
6. **M5 product track** (scheduling authorization pending; deliverables
   **required**): F14 lab OCR, F15 extraction verification, F16
   research-safe assistant (clinician-gated), F17 admin console.

## 6. Change control for this snapshot

This file is rewritten per milestone (documentation-only edits allowed);
the historical snapshots live in git history and in the merged verification
records (`backend/VERIFICATION.md`). When status rows change, the milestone
PR must update this file in the same change-set — status drift is itself a
defect.
