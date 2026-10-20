# 04 — Database and API Integration Design

**Status:** The full M1b schema/API design below remains **PROPOSED**; its first
small persistence slice, M1b.1, is **IMPLEMENTED + TESTED locally** in this
change-set. The database is configured as SQLite by default and created only
by explicit Alembic migrations. The existing contract/fixture artifacts are
unchanged. Exact as-built entities and intentional deferrals are listed in
§1.1; the larger ERD is the future M1b target, not the current schema.

---

## 1. Persistence principles

1. **SQLite for local development** (zero-setup, $0), with a **documented
   PostgreSQL migration path** (task-locked 2026-10-17; consistent with
   Phase 0 §7.2's "SQLite for zero-setup dev").
2. One SQL layer used by the modular monolith (Phase 0 §7.2 rules); module
   ownership of tables enforced by convention + review (no cross-module
   table access).
3. **Persistence must not change wire behavior.** The approved contract
   fixture pack and existing backend regression behavior, plus migration/
   storage tests, are the regression gate. M1b.1
   makes accepted monitoring records and their success-audit metadata durable;
   idempotency remains process-local because Q8's durable-store decision is
   still open.
4. Raw datasets, model weights, lab documents and PHI stay **out of git**
   (`docs/DATA_POLICY.md`); the configurable SQLite file and sidecars are
   git-ignored. Inputs in this prototype remain synthetic/demo-only.
5. Migrations are explicit, versioned and reversible. Fresh-upgrade,
   downgrade/re-upgrade and metadata consistency checks use disposable test
   databases; no migration is run destructively against a developer database.

### 1.1 M1b.1 as-built scope (IMPLEMENTED + TESTED locally)

| Entity | M1b.1 behavior | Explicit boundary |
|---|---|---|
| `monitoring_observation` | Durable row written by the existing `POST /v1/monitoring/observations`; private UUID PK, indexed public `observation_id`, request id, opaque `patient_ref`/`consent_id`, source, timestamp. | Public ID is not unique because current process-local deterministic IDs can repeat after restart. `patient_ref` and `consent_id` are not FKs: the endpoint has no patient/consent lookup. |
| `monitoring_metric` | One child row for each non-null metric; FK to its observation, unique `(observation_record_id, ordinal)`, preserving duplicates/order/current scalar behavior. | Null stays “not measured” and is omitted; no `UNIQUE(observation, metric_id)` because B-04 permits repeated IDs. |
| `audit_event` | One metadata-only success event per accepted monitoring write, inserted in the same transaction; unique FK to its observation. Application has insert/read paths only. | Error-event snapshots remain in memory; SQLite does not provide PostgreSQL GRANT/REVOKE permissions. No audit/history HTTP API. |

These three tables and their Alembic migration are the only entities in this
slice. `PatientProfile`, `ConsentRecord`, `idempotency_record`, auth/RBAC,
Track-A prediction/feature-set, history/review, document, registry and other
M1b tables remain **DEFERRED**. The opaque consent reference keeps the current
non-empty-only validation; no consent grant is created or inferred. Durable
idempotency remains deferred until Q8 is reviewed. This scope distinction is
intentional; it preserves the current contract while still providing real,
transactional monitoring storage.

## 2. Full M1b target ERD (PROPOSED; not all entities are implemented)

````
                                 ┌────────────────────┐
                                 │    user_account     │
                                 │ PK user_id          │
                                 │    email/username   │
                                 │    password_hash    │
                                 │    status           │
                                 └─────────┬──────────┘
                        ┌──────────────────┼──────────────────┐
                        │1                 │1                 │1
                        │                  │                  │
              ┌─────────▼────────┐  ┌──────▼───────┐  ┌───────▼────────┐
              │ clinician_profile│  │patient_profile│  │ admin/research │
              │ PK clinician_id  │  │ PK patient_id │  │  (role on      │
              │ FK user_id       │  │ FK user_id    │  │   user_account)│
              └─────────┬────────┘  │ patient_ref*  │  └────────────────┘
                        │           └──┬────────┬──┘
                        │              │        │
      assigned patients │              │        │
   (clinician_patient)  │              │        │
                        │              │        │
   ┌────────────────────▼──┐   ┌───────▼──────┐ │  ┌──────────────────────┐
   │ review_action         │   │ consent_record│ │  │ lab_document         │
   │ PK review_action_id   │   │ PK consent_id │ │  │ PK document_id       │
   │ FK prediction_result  │   │ FK patient_id │ │  │ FK patient_id        │
   │ FK clinician_id       │   │ type/scope    │ │  │ sha256, mime, storage│
   │ decision, reason_code │   │ granted_at    │ │  │ uploaded_by, status  │
   │ note, created_at      │   │ revoked_at    │ │  └──────────┬───────────┘
   └────────────────────▲──┘   └──────────────┘ │             │1
                        │                       │             │
                        │1                      │      ┌──────▼───────────┐
   ┌────────────────────┴──────────┐            │      │ extraction_field │
   │ prediction_result             │            │      │ PK field_id      │
   │ PK prediction_id (=audit_id)  │            │      │ FK document_id   │
   │ FK patient_id (nullable)      │            │      │ name, raw_text   │
   │ FK clinical_feature_set_id    │◄───────────┘      │ value, unit      │
   │ model_id, preprocessing_id,   │  feature values   │ page/region      │
   │ calibration_id,               │  carry entered_by │ ocr_engine, conf │
   │ feature_schema_id,            │  + source         │ edited_value     │
   │ target_id, score_value,       │                   │ edit_history[]   │
   │ score_type, validation_status │                   │ state (extracted→│
   │ explanation_json,             │                   │  edited→confirmed│
   │ missing_features, warnings    │                   │  →verified/rej.) │
   │ payload_hash, idempotency_key │                   │ verified_by,     │
   │ reassessment_reason (null)    │                   │  verified_at     │
   │ created_at                    │                   └──────────────────┘
   └────────────────────▲──────────┘
                        │ generated from (manual entry and, ONLY when the
                        │ 05 §2.1 eligibility checklist passes, verified lab fields)
   ┌────────────────────┴──────────────────────────────────────────────┐
   │ clinical_feature_set                                              │
   │ PK feature_set_id · FK patient_id · feature_schema_id             │
   │ source ∈ {benchmark_import, clinician_entry} · entered_by         │
   │ features_json (value/unit per feature) · confirmed_at             │
   └────────────────────▲──────────────────────────────────────────────┘
                        │
   ┌────────────────────┴──────────┐   ┌──────────────────────────────┐
   │ survey_response /             │   │ monitoring_observation        │
   │ medical_history_entry /       │   │ PK observation_id             │
   │ symptom_entry                 │   │ FK patient_id (via patient_ref│
   │ PK entry_id · FK patient_id   │   │  resolved server-side)        │
   │ kind, instrument_version,     │   │ observed_at, source,          │
   │ payload_json, recorded_at     │   │ consent_id (FK, required)     │
   └───────────────────────────────┘   │ recorded_at, idempotency_key  │
                                       └──────────────┬───────────────┘
                                                      │1
                                       ┌──────────────▼───────────────┐
                                       │ monitoring_metric            │
                                       │ PK metric_row_id             │
                                       │ FK observation_id            │
                                       │ metric_id, value, unit       │
                                       └──────────────────────────────┘

   ┌────────────────────────┐  ┌───────────────────────┐  ┌─────────────────────────┐
   │ audit_event (append-   │  │ idempotency_record    │  │ model_artifact_registry │
   │  only)                 │  │ PK idempotency_key    │  │ PK model_id             │
   │ PK audit_id            │  │ route, payload_hash   │  │ preprocessing_id,       │
   │ actor_user_id, action, │  │ response_snapshot     │  │ calibration_id,         │
   │ entity_type, entity_id,│  │ original_result_id    │  │ feature_schema_id,      │
   │ model_ids, hashes,     │  │ created_at, expires_at│  │ training_datasets_json, │
   │ created_at             │  └───────────────────────┘  │ artifact_sha256,        │
   │ append-only in app code│                             │ code_commit,            │
   └────────────────────────┘                             │ validation_status       │
                                                          └─────────────────────────┘
   ┌────────────────────────┐  ┌───────────────────────┐  ┌─────────────────────────┐
   │ follow_up_task /       │  │ content_item          │  │ disease_module          │
   │ notification_record    │  │ (F16 static content,  │  │ (F09 registry: target,  │
   │ (F06)                  │  │  versioned, approved_ │  │  schema id, review      │
   └────────────────────────┘  │  by)                  │  │  workflow)              │
                               └───────────────────────┘  └─────────────────────────┘
````

In the full target schema, `patient_ref` (wire) maps server-side to an
internal `patient_id`. **That mapping is not implemented in M1b.1:** the
existing monitoring request stores its synthetic `patient_ref` and
`consent_id` as opaque strings, because the endpoint does not resolve either
to a master record. `audit_id` remains the mock prediction's public result id;
Track-A prediction persistence is deferred.

**Laboratory-data boundary (binding, [05 §2.1](05_RESEARCH_METHODOLOGY_AND_APPROVAL_GATES.md)):**
`extraction_field` rows are Track-B document records. The
`extraction_field → clinical_feature_set` edge represents *recording* a
feature-set member **only** when every eligibility condition (approved
feature-schema membership, target support, intended prediction time, unit
conformity, complete provenance, validation protocol) holds for the
approved model version — **verification alone never implies model
eligibility**, and no feature mapping is invented (real schemas come from
Gate DA dictionary work, Q1). Wearable/monitoring metrics have **no edge**
to `clinical_feature_set` or `prediction_result`; the API rejects wearable
sources for CAD inference with `422 wearable_input_not_valid_for_cad_inference`
(F-09), permanently.

## 3. Full table catalog and current status

| Module | Tables | Current status / notes |
|---|---|---|
| identity | `user_account`, `role_assignment`, `session_token` | **DEFERRED** — no auth/RBAC in M1b.1. |
| records | `patient_profile`, `clinician_profile`, `clinician_patient`, `medical_history_entry`, `symptom_entry`, `survey_definition`, `survey_response`, `clinical_feature_set` | **DEFERRED** — patient/consent linking is not invented from the current opaque references. |
| documents | `lab_document`, `extraction_field`, `verification_event` | **DEFERRED** to M5 (F14/F15); synthetic samples only when authorized. |
| inference | `prediction_result`, `model_artifact_registry` | **DEFERRED** — CAD remains mock; no prediction rows/models are stored in M1b.1. |
| ingestion | `monitoring_observation`, `monitoring_metric` | **IMPLEMENTED + TESTED** for the existing monitoring POST. Metric rows have an observation FK and ordinal uniqueness; null metrics are omitted; duplicate metric IDs remain accepted. `patient_ref` and `consent_id` are opaque strings for now. |
| review | `review_action`, `reassessment_request`, `follow_up_task`, `notification_record`, `visit_summary` | **DEFERRED** — F06 rules and routes require later approval/contract-first work. |
| audit | `audit_event` | **IMPLEMENTED + TESTED** for successful monitoring writes only. Append-only application layer, one row per observation in the same transaction. SQLite cannot enforce PostgreSQL-style `UPDATE`/`DELETE` grants; no such permissions are claimed. Error events remain in-memory. |
| platform | `idempotency_record`, `content_item`, `disease_module` | **DEFERRED**. The 24-hour monotonic idempotency runtime behavior remains implemented/tested in RAM; Q8's formal retention/store-of-record decision stays **OPEN**. |

## 4. SQLite → PostgreSQL migration path (documented rules)

| Concern | Rule |
|---|---|
| Portability | Use SQLAlchemy 2.x (or equivalent) with Alembic migrations written against the common dialect subset; no SQLite-only SQL in application code (review checklist item) |
| Identifiers | Store UUIDs as canonical `CHAR(36)` text (portable) or native UUID on PG via a single documented mapping; never mix |
| JSON columns | Use `JSON` type with text-serialized JSON; avoid SQLite `->>` operators in queries; parse in Python (PG offers `JSONB` later as an optimization, not a semantic change) |
| Booleans | SQLAlchemy `Boolean` (both backends); never 0/1 integers on the wire |
| Date/time | Store UTC ISO-8601 or naive-UTC datetimes consistently; never local time |
| Concurrency | SQLite: single writer and `WAL` mode. If durable idempotency is separately authorized, use an explicit write transaction (e.g. `BEGIN IMMEDIATE`) plus tested uniqueness; M1b.1 stores no idempotency rows. PostgreSQL locking/constraints require separate PG tests; parity is not claimed |
| Migrations | Alembic up/down per change; CI runs the suite on SQLite always; a **PG compatibility job** (local `postgres` service or container) runs the same suite before any non-local deployment (target: M4) |
| Audit append-only | Enforced in application code on both backends (insert-only service methods; no update/delete paths). **SQLite has no GRANT/REVOKE**, so table permissions cannot enforce this there; on PostgreSQL add `REVOKE UPDATE, DELETE ON audit_event` (plus optional triggers) as defense-in-depth — never claim SQLite provides PG-style permission enforcement |
| Cutover | Export/import script for SQLite→PG (synthetic/demo-only data); requires a separately authorized/tested migration slice; no zero-downtime claim |
| What we never introduce without a measured need | Redis, InfluxDB, Kafka, ORM caches (Phase 0 §7.3) |

## 5. API integration map

### 5.1 Existing approved surface (do not change without ADR + approval)

| Method/Path | Track | Status | Clients |
|---|---|---|---|
| `POST /v1/predictions/cad-tabular` | A | Mock, IMPLEMENTED; **not persisted in M1b.1** | Tests; clients are thin local integrations, M1a.3 deferred/resequenced |
| `POST /v1/monitoring/observations` | B | Mock, IMPLEMENTED; **durably persists observation + non-null metrics + success audit in M1b.1 SQLite** | Tests; no history/read route is added |
| `GET /openapi.json` | — | IMPLEMENTED (self-contained) | codegen + tests |

Behavioral summary: idempotency (24 h retention — **implemented & tested
runtime behavior**, read from the merged OpenAPI; the *formal* approval of
the window and the durable store of record is Q8, pending; replay =
original response + flag;
409 conflict before semantic validation per G-02 ruling), error envelope
(`400 malformed_request`, `409 idempotency_key_conflict`, `422` family incl.
`wearable_input_not_valid_for_cad_inference`, `503 model_unavailable`/schema
mismatch), deterministic synthetic scores/SHAP-shaped offsets, optional-null =
missing (backend; the schema side was corrected under ADR-001 Option A — D-044 — PR #8 merged; A-01 technical correction complete), Track-B scalars permissive
(B-01 open), Track-B replay = 201 (B-02 open), global key namespace with
route guard (B-03), null/count semantics (B-04), deterministic correlation id
(G-01). Full detail: `shared/contracts/README.md`, `backend/CONTRACT_NOTES.md`.

### 5.2 Planned surface (all PROPOSED — each needs a contract-first change-set)

| Method/Path (proposal) | Track | Milestone | Purpose | Notes |
|---|---|---|---|---|
| `POST /v1/auth/login`, `POST /v1/auth/refresh`, `POST /v1/auth/logout` | Platform | M1b | Sessions/tokens | New error codes for auth failure need catalogue review (Q13-class) |
| `GET /v1/patients`, `GET /v1/patients/{id}` | A/B | M1b | Clinician list/detail | RBAC-scoped; pseudonymized for researcher role |
| `GET /v1/patients/{id}/timeline` | A/B | M1b | Longitudinal record | Read model over predictions + observations + review actions |
| `GET /v1/predictions/{id}` | A | M1b | Prediction replay/read | Needed because today only the POST response exposes a result |
| `POST /v1/predictions/{id}/review-actions` | A | M1b | accept / reject / reassessment_requested | Idempotent; audited; reason codes; read-only `pending_review` today |
| `POST /v1/predictions/{id}/reassess` | A | M1b | Validity-gated re-score | Server enforces §R2-2.2 triggers; `reassessment_reason` labelled |
| `POST /v1/monitoring/observations/batch` | B | M1b | **Proposed batch-submission** endpoint for offline sync (Q11) | Preserves per-write idempotency keys; per-item results; subject to contract-first approval (§6) |
| `GET /v1/monitoring/observations` | B | M1b | **Proposed history-read** endpoint (history/trends) | Pagination; source labels; subject to contract-first approval (§6) |
| `GET/POST/PATCH /v1/consents` | Platform | M1b | Consent lifecycle | Grant/revoke audited |
| `GET /v1/me/...` history & profile | B | M1b | Patient self views | Own data only |
| `POST /v1/documents/lab-reports` (multipart) | B | M5 | F14 upload | sha256 + type/size validation; audited metadata only |
| `GET/PATCH /v1/documents/lab-reports/{id}/fields...`, `POST .../verify` | B→A (gated) | M5 | F15 review workflow | Provenance + state machine; 409 on conflicting edits; `verify` records data trust only — promotion into a Track-A-bound feature set is a separate eligibility-checked operation (05 §2.1) |
| `GET /v1/content/...` (static safety/lifestyle), assistant endpoints | A/B | M5 | F16 | Clinician-approved content only; citations mandatory |
| `GET /v1/exports/fhir` | Platform | M4 opt. | F08 thin export | D-020 first; research-serialization label |
| Admin endpoints (users, registry) | Platform | M1b/M5 | F17 | Admin role only; audited |

### 5.3 Integration map by client

````
Flutter (patient)                        React (clinician)
  auth → /v1/auth/*                        auth → /v1/auth/*
  measures/surveys → /v1/me/*,             list → /v1/patients
    /v1/monitoring/observations            record → /v1/patients/{id}, /timeline
  lab upload → /v1/documents/* (M5)        predict → /v1/predictions/cad-tabular
  history → /v1/monitoring/observations    review → /v1/predictions/{id}/review-actions
  consent → /v1/consents                   monitoring → /v1/monitoring/observations (read)
        │                                        │
        └───────────────► /v1 (single FastAPI modular monolith) ◄──────────┘
                              │                    │
                       SQLite (dev) / PG       model artifacts
                       audit_event (append)    (out of git, M3+)
````

Browser code uses **relative `/v1/...` URLs** (dev-server proxy); Flutter
uses `API_BASE_URL` via `--dart-define` (M1a.3 handoff §2–3).

## 6. Contract-change protocol (binding for every new endpoint)

1. Write/extend JSON Schema + OpenAPI + fixtures **first** (new fixture IDs
   continue the F-xx series; index.json updated).
2. Contract tests for request validation, response shape, error catalogue,
   idempotency semantics, determinism where applicable.
3. For any edit to *approved* artifacts: an ADR (template: ADR-001) +
   maintainer decision recorded in `docs/DECISIONS.md`.
4. Server implementation reuses the checked-in schemas at runtime (M1a.2
   rule: no parallel hand-maintained request models).
5. Breaking wire changes require `/v2` + migration note (D-036).

## 7. Provenance & audit schema (cross-cutting)

- Every `prediction_result` row stores the full provenance tuple
  (`model_id`, `preprocessing_id`, `calibration_id`, `feature_schema_id`,
  `training_datasets` hashes, `code_commit`, `validation_status`).
- Every `extraction_field` keeps raw + edited values + engine/confidence +
  verifier identity (F15). Verification state records data trustworthiness
  only; Track-A model eligibility is a separate, stricter condition
  ([05 §2.1](05_RESEARCH_METHODOLOGY_AND_APPROVAL_GATES.md)) and is never
  implied by the verification event.
- The existing runtime keeps one in-memory audit snapshot per accepted write
  across both tracks; replays emit none; conflicts and validation failures emit
  none; unexpected 500s have an in-memory error audit id only. In M1b.1, an
  accepted monitoring write additionally creates one durable, metadata-only
  `audit_event` row in the same transaction. CAD success events and error
  events are not durably audited by this slice.
- Idempotency request/response snapshots remain in memory. A replay preserves
  the original response verbatim except `idempotent_replay`; Q8's durable
  idempotency store policy remains open.
