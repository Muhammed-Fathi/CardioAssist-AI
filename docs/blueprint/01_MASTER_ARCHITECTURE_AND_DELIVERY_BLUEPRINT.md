# 01 — Master Architecture and Delivery Blueprint

**Status:** PROPOSED planning baseline (documentation only), 2026-10-17.
Supersedes no existing document; where it restates an existing decision it
cites it and defers to it. Nothing here authorizes implementation, data
access, training, or merging.

---

## 1. Product vision (preserved in full)

CardioAssist AI is a research-oriented graduation platform for coronary
artery disease (CAD) with four preserved pillars (source:
`research/source_materials/project_presentation.pdf`, 47 slides, and
`project_presentation_speaker_notes.md`; slide numbers below are speaker-note
order):

1. **Patient experience** — a Flutter Android application (S37–S39) for
   health measures, symptoms/surveys, lifestyle context, monitoring history,
   offline use, consent controls and follow-up flows.
2. **Clinician experience** — a React + TypeScript website (S40–S41) for
   patient lists, triage-style review queues, longitudinal records and
   timelines, per-prediction explanations, monitoring views, doctor review
   and reassessment workflows.
3. **Research core (Track A)** — cross-sectional CAD classification on
   approved tabular benchmark data with real SHAP/LIME explainability,
   calibration where warranted, clinician review of every prediction, and a
   reproducible evaluation/research-reporting workflow (S28–S34, S43, S46).
4. **Monitoring core (Track B)** — patient-entered data, lab-report intake,
   and wearable/monitoring streams via a simulator-first adapter strategy
   (Android Health Connect later), kept scientifically separate from Track A
   (S15, S38–S39).

Plus the platform envelope: shared versioned FastAPI backend, persistent
database, authentication/roles/consent/audit, administration, extensible
disease modules (CAD first), FHIR-shaped interoperability, and a
local-first deployment posture (S20, S22–S27, S36, S42–S43).

**The full, feature-by-feature preservation inventory is
[02_FEATURE_TRACEABILITY_MATRIX.md](02_FEATURE_TRACEABILITY_MATRIX.md).**
No vision feature is deleted anywhere in this blueprint; blocked items carry
a named blocker (D-042 preservation rule).

Two vision tracks are **scientifically separated and never silently merged**
(binding, D-038/D-039, Phase 0 §R2-2/§F-4):

- **Track A — clinical CAD AI:** schema-validated clinical features →
  versioned preprocessing → CAD presence classifier → optional calibration →
  score + explanation → clinician review → audit. Target is (pending P-1)
  cross-sectional angiographic CAD **presence** classification only.
- **Track B — patient & wearable monitoring:** manual entry, surveys,
  lab-report extractions, simulated/real wearable observations → validated
  ingestion → history/trends → clinician monitoring views. **Track B never
  feeds Track A inference** (`422 wearable_input_not_valid_for_cad_inference`,
  contract test F-09). A future wearable-aware model is possible only as a
  separately trained, separately validated research protocol on a labeled
  dataset (Phase 0 §10.2) — none exists in the approved evidence base.

## 2. Locked technology decisions

Kept as instructed unless a documented technical problem forces a proposed
alternative (any alternative requires a new decision entry in
`docs/DECISIONS.md`):

| Layer | Decision | Source | Notes |
|---|---|---|---|
| Patient app | **Flutter** (Android-first) | D-034 | Local emulator + one physical device at $0; iOS/store release out of scope (D-019/D-030) |
| Clinician site | **React + TypeScript** | D-035 | Vite-class pinned toolchain; relative `/v1` URLs; dev-server proxy to backend |
| Backend | **Python FastAPI modular monolith**, versioned `/v1` | D-036, D-041 | One deployable process; module boundaries without network boundaries |
| Persistence | **SQLite for local development**, documented **PostgreSQL migration path** | Task-locked 2026-10-17 (extends Phase 0 §7.2 "SQLite for zero-setup dev") | No database exists yet — see [04](04_DATABASE_AND_API_INTEGRATION_DESIGN.md); persistence is an M1b deliverable |
| Contracts | OpenAPI 3 + JSON Schema 2020-12, fixtures + tests in `shared/contracts/` | M1a.1 (PR #3), D-043 | Approved artifacts change only via a reviewed change-set (see ADR-001) |
| AI | Tabular models + **real** TreeSHAP/LIME at research time; deterministic **mock** until Gate PT | D-038, Phase 0 §R2-5 | `ai/` remains empty until M3 |
| Infrastructure | **Free/local-first, $0** | D-001, D-041 | No mandatory paid services; hosted demo optional + disposable (Phase 0 §7.4) |

Explicitly **deferred** (not deleted) per Phase 0 §7.3: Kafka/streaming,
WebSocket push (replaced by polling/near-real-time REST in the prototype),
Redis/Feast feature store, InfluxDB, Kong, Kubernetes/Terraform/ArgoCD,
Go/Rust microservices, MLflow. Revisit only with a measured need and a named
maintainer.

## 3. System architecture and module boundaries

```
┌──────────────────────────── single deployable (FastAPI, Python 3.11+) ────────────────────────────┐
│ api/            versioned REST /v1, request validation, error envelope, idempotency dispatch       │
│ identity/       authentication, sessions/tokens, roles (patient/clinician/researcher/admin)        │
│ records/        patient profiles, medical history, symptoms, surveys, clinical feature sets       │
│ documents/      lab-report upload (image/PDF), OCR extraction, field edits, verification workflow │
│ inference/      model registry loader (model_id + preprocessing_id + calibration_id), scoring stub│
│ explanation/    SHAP/LIME integration (real, M3+), explanation DTOs + fidelity metadata (M3+)     │
│ ingestion/      Track-B monitoring: manual + simulated-wearable observations, units, consent refs │
│ review/         clinician review states, reassessment-validity rules, follow-up tasks             │
│ notifications/  in-app notification records + follow-up summaries (no unvalidated alerting)       │
│ audit/          append-only event log (actor, action, entity, model ids, hashes, timestamps)      │
│ registry/       disease-module registry (CAD first), feature-schema/model/config artifact registry│
│ admin/          user provisioning, role assignment, registry maintenance, system health           │
└──────────────┬────────────────────────────────────────────────────────────────────────────────────┘
               │ SQL (SQLAlchemy/Alembic-class; SQLite dev → PostgreSQL path, 04)
        ┌──────▼───────┐
        │  SQLite (dev) │  ← planned M1b; today all state is in-memory and resets on restart
        └──────────────┘
   clinician-web (React+TS) ——— same /v1 contract ——— patient app (Flutter, Android)
```

Module rules (enforced from M1b onward; the current mock backend predates
them and is exempt until persistence lands):

1. Modules communicate through explicit service interfaces or the SQL layer
   they own; **no cross-module table access** (Phase 0 §7.2 monolith
   discipline).
2. Every externally visible write emits exactly one audit event; audit rows
   are append-only (no UPDATE/DELETE privileges on the audit table).
3. The model is a versioned artifact **outside git**, loaded by `model_id`;
   artifact hash + training-dataset ids + code commit travel with every
   prediction (provenance, Phase 0 §8.1).
4. Simulated wearable input enters through the same ingestion API as manual
   entry, labelled `source=simulated_wearable`; it can never reach
   `inference/` (D-039, §F-4).
5. New disease modules plug into `registry/` + `inference/` + `review/`
   without changing platform services (Phase 0 §R2-2.3); they may not share
   CAD scores, thresholds, or claims.

## 4. Authentication and authorization plan (prototype grade)

Planned for **M1b** (the merged M1a.2 backend is explicitly unauthenticated;
M1a.3 clients use synthetic refs — `docs/M1A3_INTEGRATION_HANDOFF.md`). This
deviation from Phase 0 M1a's original "login/RBAC thin proof" wording is a
documented scope refinement made by the maintainer's M1a.2/M1a.3
authorizations; the milestone authorization for M1b must re-confirm it.

- **Credentials:** local accounts only; passwords hashed with argon2 or
  bcrypt via a maintained library; secrets via environment variables, never
  committed (Phase 0 §7.5).
- **Sessions:** short-lived signed tokens (JWT-class) + refresh or server
  sessions — exact scheme chosen at M1b design review; no third-party IdP
  (keeps $0 and local-first).
- **Roles (RBAC): `patient`, `clinician`, `researcher`, `admin`.**
  Planned matrix (to be test-pinned at M1b):

  | Capability | patient | clinician | researcher | admin |
  |---|---|---|---|---|
  | Own profile/history/consent | ✔ | read (assigned patients) | ✖ | ✔ |
  | Enter own measures/surveys/lab uploads | ✔ | ✖ | ✖ | ✖ |
  | View assigned patients + timelines | ✖ | ✔ | pseudonymized datasets only | ✔ |
  | CAD inference submit (clinical features) | ✖ | ✔ | benchmark_import only | ✖ |
  | Review actions (accept/reject/reassess) | ✖ | ✔ | ✖ | ✖ |
  | Read audit of own/assigned actions | limited | ✔ | metadata only | ✔ |
  | User/registry administration | ✖ | ✖ | ✖ | ✔ |

- **Patient identity:** pseudonymous `patient_ref` at the API boundary;
  linkage table stays server-side; `patient_ref` denylist against
  identifier-shaped values (open question Q12 — privacy review).
- **Consent:** explicit consent records (type, scope, version, granted/
  revoked timestamps) referenced by ingestions (`consent_id`); consent state
  changes are audit events. The prototype records consent **references**;
  full lifecycle enforcement is M1b and remains subject to a privacy review.
- **What is never claimed:** HIPAA/GDPR/ISO/FDA compliance, production
  security, multi-tenant isolation, or tamper-proof auditing. Prototype
  security only (Phase 0 §7.5).

## 5. Data provenance model (three layers)

1. **Value provenance (Track A/B inputs):** every feature/metric assertion
   carries `value`, `unit`, optional `entered_by`/`source`
   (`manual_entry | benchmark_import | clinician_entry | simulated_wearable`
   — valid CAD-inference sources are exactly `benchmark_import` and
   `clinician_entry`), and `recorded_at`. Null = not provided; 0/false are
   data (contract semantics).
2. **Prediction provenance:** every prediction response carries
   `model_id`, `preprocessing_id`, `calibration_id`, `feature_schema_id`,
   `training_datasets` (ids + hashes), `code_commit`, `validation_status`
   lifecycle (`development_internal_only → externally_evaluated →
   externally_calibrated`), plus the request payload hash and `audit_id`
   (Phase 0 §R2-6.4, §F-5).
3. **Document-extraction provenance (lab reports, M5):** each extracted
   field stores the source document hash, page/region locator, OCR engine +
   version + confidence, raw extracted text, edited value, editor identity,
   and verification state (`extracted → edited → confirmed_by_patient →
   verified_by_clinician`). Only verified fields may enter clinical feature
   sets; unverified fields are visually labelled everywhere.

Audit events (append-only) tie the three layers together: one event per
accepted logical write (prediction, observation, review action, consent
change, extraction verification), carrying ids and hashes — **not** raw
clinical values in the event payload (current mock behavior preserved).

## 6. Offline / sync considerations (Flutter, M1b+)

- **Outbox pattern:** the patient app queues logical writes locally with a
  client-generated `Idempotency-Key` per logical write; retries reuse the
  key; a changed payload uses a new key (contract rule; 409 conflict
  semantics are the server-side guard).
- **Batch sync:** a batch observation-ingestion endpoint is an identified
  contract gap (Q11) for M1b; it must preserve per-write idempotency keys,
  per-item acceptance/rejection results, and one audit event per accepted
  write. Until it exists, M1a.3's single-observation endpoint is the only
  supported write.
- **Conflict rules:** server is source of truth; no client-side merge of
  measurement values; time is client `observed_at` + server `recorded_at`.
- **Scope limits of the prototype:** no cross-device live sync, no push
  delivery guarantees, no offline CAD inference (patients never see Track-A
  scores), no wearable background sync until a real adapter exists (P-6).
  `Workmanager`-style background sync is a *future* implementation detail,
  not a milestone commitment.

## 7. Delivery principles

1. **Contract-first:** wire behavior changes land as contract + fixture +
   tests in the same change-set (ADR process; ADR-001 is the template).
2. **Milestone = scoped PR + reproducible local tests + human review.**
   Each milestone ends with the documented test commands green and a named
   human reviewer approving before merge. The agent never self-merges
   (AGENTS.md).
3. **Mock honesty:** until Gate PT + M3, every screen and response that
   resembles a clinical result carries the MOCK/SYNTHETIC disclaimer and
   `validation_status: development_internal_only`; synthetic SHAP-shaped
   offsets are labelled as such and are **not** computed SHAP (and must
   never be described as real model explanations).
4. **Safety copy is gated:** target wording, score rendering labels and any
   symptom-safety text require clinician review (P-4); until then,
   conservative fallback copy only; no thresholds/alerts/treatment language.
5. **Traceability:** implementation PRs cite the feature IDs (F01–F18) and
   milestone exit criteria from [02](02_FEATURE_TRACEABILITY_MATRIX.md) /
   [06](06_TESTING_AND_ACCEPTANCE_MATRIX.md).
6. **Budget:** $0 everywhere (D-001); see
   [07](07_OPEN_DECISIONS_RISKS_ASSUMPTIONS.md) §5 for the free-tier
   inventory.

## 8. What this blueprint explicitly does NOT authorize

Datasets acquisition (Gate DA), model fitting/selection/evaluation (Gate PT),
schema edits (including ADR-001's patch), clinical wording approval,
real wearable adapters, production auth claims, deployment beyond local
testing, or any performance/clinical statement. Those remain with the named
human gates (P-1 … P-6) and `docs/DECISIONS.md`.
