# CardioAssist-AI Term 1 — C2 Relational Schema, Invariants, and Additive Migration Spec

**Date:** 2026-11-27 (UTC / Africa/Cairo) — **Revision 2**
**Status:** `PROPOSED — NOT APPROVED, NOT IMPLEMENTED`
**Migration Base:** `20261126_06` (`backend/migrations/versions/20261126_06_pepper_binding.py`)
**Scope:** C2 Clinical Intake, Immutable Versioned Health Profile & Separate Assessment Snapshot, C0 §7.3 Lease/Fencing Inference Persistence (`20261128_07`), and Bounded Document/OCR Intake (`20261128_08`)

---

## 1. Compatibility Rules With C1 & `Database.verify_schema()`

1. **Zero Modification to `01`–`06`:** `20261017_01` through `20261126_06` remain byte-for-byte unchanged.
2. **Exact ORM ↔ Migration Parity:** `backend/app/storage/database.py::Database.verify_schema()` runs Alembic `compare_metadata(..., opts={"compare_type": True})` plus explicit primary-key inspection, `PRAGMA foreign_keys=ON`, `PRAGMA integrity_check`, and `PRAGMA foreign_key_check` on every startup. Every column length, nullability, PK, FK (`ondelete="RESTRICT"`), CHECK constraint, and index in the C2 SQLAlchemy models MUST match migrations `07` and `08` identically.
3. **RB-C1 Rollback Policy Preservation:** Both `20261128_07` and `20261128_08` implement the exact `RB-C1` downgrade guard from `20261126_06_pepper_binding.py`:
   - Refuse `as_sql=True` offline downgrade (`RuntimeError`).
   - Query every C1 and C2 table (`LIMIT 1`); if **any** Term 1 row exists, refuse in-place downgrade (`RuntimeError`) and require verified backup restoration.
   - `20261128_07` drops its SQLite triggers (`tr_assessment_*`) cleanly inside empty-DB `downgrade()` before dropping tables.
4. **No Global `patient.doctor_id`:** Consistent with `R-01`/`O-04` and C1, `health_profile`, `assessment_snapshot`, `assessment`, and `medical_document` never store a global `doctor_id`. Doctor visibility derives exclusively from `assessment.assignment_id -> doctor_patient_assignment` (where `revoked_at IS NULL`).
5. **Audit Table Extension (`workflow_audit_event`):** In C1 (`20261126_02`), `workflow_audit_event` enforces a CHECK constraint only on `outcome` (`ck_workflow_audit_outcome`), **not** on `event_type` or `subject_type` (those are enforced in `backend/app/term1/constants.py` and Python code). Thus C2 extends `constants.py` additively with C2/Document event types and subject types without altering `workflow_audit_event` DDL.

---

## 2. Entity-Relationship Overview (C1 → C2 Additive Links)

```
C1 (Frozen)
├── patient_profile (patient_id)
│     ├── 1:N ──> health_profile (health_profile_id; immutable versioned rows:
│     │              DRAFT / COMPLETE / SUPERSEDED; <=1 active via partial UNIQUE)
│     ├── 1:N ──> medical_document (document_id; PENDING_SCAN -> STORED / UPLOAD_FAILED)
│     │              ├── 1:N ──> document_extraction (extraction_id, extraction_version)
│     │              │              └── 1:N ──> extraction_field (field_record_id)
│     │              └── 1:N ──> extraction_event (event_id, append-only)
│     ├── 1:N ──> assessment_snapshot (snapshot_id, health_profile_id -> health_profile)
│     └── 1:N ──> assessment (assessment_id, snapshot_id -> assessment_snapshot,
│                    │        health_profile_id -> health_profile,
│                    │        assignment_id -> doctor_patient_assignment,
│                    │        consent_id -> consent_record,
│                    │        review_state, review_version)
│                    ├── self FK (reassessment_of_id -> assessment.assessment_id)
│                    ├── 1:N ──> assessment_document (assessment_id, document_id,
│                    │              extraction_id, extraction_version)
│                    ├── 1:N ──> document_acknowledgement (DOC9 assignment+extraction lock)
│                    ├── 1:N ──> inference_attempt (attempt_id; <=1 INFERENCE_RUNNING)
│                    ├── 1:N ──> inference_result (result_id, append-only immutable)
│                    ├── 0..1 ─> active_attempt_id (trigger-enforced FK -> inference_attempt)
│                    └── 0..1 ─> current_result_id (trigger-enforced FK -> inference_result)
└── doctor_patient_assignment (assignment_id) & consent_record (consent_id)
```

---

## 3. Migration `20261128_07_c2_clinical_intake_inference.py`

**`down_revision = "20261126_06"`**

### 3.1 `health_profile` (Immutable Versioned Rows per C0 §7.1–§7.2)

`health_profile` stores **immutable versioned rows** (no mutable single-row override and no separate `health_profile_revision` table). Whenever `H1b` (`PATCH /v1/me/health-profile`) updates fields, the backend transitions the prior active row to `SUPERSEDED` (without altering any clinical value column on that row) and inserts a new row (`version_number + 1`). Any `health_profile` row referenced by `assessment_snapshot` is **permanently immutable**.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `health_profile_id` | `String(36)` | PK | Server-generated UUIDv4 |
| `patient_id` | `String(36)` | `FK(patient_profile.patient_id, RESTRICT)`, `NOT NULL` | Owner patient |
| `version_number` | `Integer` | `NOT NULL`, `CheckConstraint("version_number >= 1")` | Monotonic per patient (`1, 2, ...`) |
| `status` | `String(24)` | `NOT NULL` | `'DRAFT'`, `'COMPLETE'`, `'SUPERSEDED'` (`COMPLETE` iff `age`, `sex`, `cp` present) |
| `superseded_by_id` | `String(36)` | `FK(health_profile.health_profile_id, RESTRICT)`, `NULL` | Link to replacing version (`NULL` when active) |
| `panel_id` | `String(64)` | `NOT NULL` | `'da_a2_resting_v1'` |
| `panel_version` | `String(16)` | `NOT NULL` | `'1.0.0'` |
| `schema_version` | `String(32)` | `NOT NULL` | `'term1.c2.profile/v1'` |
| `fields_json` | `JSON` | `NOT NULL` | Canonical `{inputs, units, missing_reasons}` validated against `DA_A2_RESTING_PANEL` |
| `provenance_json` | `JSON` | `NOT NULL` | Field-level origin (`manual` vs `ocr_confirmed`, `document_id`, `extraction_id`, `extraction_version`) |
| `profile_sha256` | `String(64)` | `NOT NULL` | Canonical SHA-256 of `{panel_id, panel_version, schema_version, fields_json, provenance_json}` |
| `actor_user_id` | `String(36)` | `FK(user_account.user_id, RESTRICT)`, `NOT NULL` | Actor who created this version |
| `created_at` | `String(32)` | `NOT NULL` | Server UTC ISO-8601 |
| `updated_at` | `String(32)` | `NOT NULL` | Server UTC ISO-8601 (updated only when transitioning `status -> 'SUPERSEDED'` & `superseded_by_id`) |

**Constraints & Indexes on `health_profile`:**
- `UniqueConstraint("patient_id", "version_number", name="ux_health_profile_patient_version")`
- **Partial Unique Index (one active draft/complete profile per patient):**
  `Index("ux_health_profile_one_active", "patient_id", unique=True, sqlite_where=text("status IN ('DRAFT','COMPLETE')"))`
- `CheckConstraint("status IN ('DRAFT','COMPLETE','SUPERSEDED')", name="ck_health_profile_status")`
- `CheckConstraint("(status = 'SUPERSEDED' AND superseded_by_id IS NOT NULL) OR (status IN ('DRAFT','COMPLETE') AND superseded_by_id IS NULL)", name="ck_health_profile_supersession")`

### 3.2 `assessment_snapshot` (Separate Immutable Canonical Envelope per C0 §7.1–§7.2)

Created atomically before `assessment` inside `S1` (`POST /v1/assessments`). Never mutated after creation.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `snapshot_id` | `String(36)` | PK | Server-generated UUIDv4 |
| `patient_id` | `String(36)` | `FK(patient_profile.patient_id, RESTRICT)`, `NOT NULL` | Owner patient |
| `health_profile_id` | `String(36)` | `FK(health_profile.health_profile_id, RESTRICT)`, `NOT NULL` | Exact immutable profile version pinned at `S1` |
| `panel_id` | `String(64)` | `NOT NULL` | `'da_a2_resting_v1'` |
| `panel_version` | `String(16)` | `NOT NULL` | `'1.0.0'` |
| `panel_contract_sha256` | `String(64)` | `NOT NULL` | `'c18ad4cd2cf08f6fefb2e340573760da7000bc1d8eb4ad38783b873c018e57b8'` |
| `schema_version` | `String(32)` | `NOT NULL` | `'term1.c2.snapshot/v1'` |
| `source_contract_version` | `String(32)` | `NOT NULL` | `'term1.c2.intake/v1'` |
| `source_kind` | `String(48)` | `NOT NULL` | Closed server-assigned enum: `'synthetic_demo_patient_manual'`, `'synthetic_demo_ocr_confirmed'` |
| `snapshot_json` | `JSON` | `NOT NULL` | **Single canonical envelope** containing: `inputs`, `units`, `missing_reasons`, `provenance` (`source_contract_version`, `source_kind`, `health_profile_id`, `health_profile_sha256`), `panel` (`panel_id`, `panel_version`, `panel_contract_sha256`, `schema_version`), and sorted `attached_documents` (`document_id`, `extraction_id`, `extraction_version`, `document_sha256_at_bind`, `extraction_confirmed_at`) |
| `snapshot_sha256` | `String(64)` | `NOT NULL` | SHA-256 of canonical UTF-8 `snapshot_json` (`sort_keys=True, separators=(",",":"), allow_nan=False`) |
| `created_at` | `String(32)` | `NOT NULL` | Server UTC ISO-8601 |

**Constraints:** `CheckConstraint("source_kind IN ('synthetic_demo_patient_manual','synthetic_demo_ocr_confirmed')", name="ck_snapshot_source_kind")`.

### 3.3 `assessment`

Authoritative submission record + C0 §7.1–§7.3 state + generation/lease/result/review CAS pointers.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `assessment_id` | `String(36)` | PK | Server-generated UUIDv4 |
| `patient_id` | `String(36)` | `FK(patient_profile.patient_id, RESTRICT)`, `NOT NULL` | Submitting patient |
| `health_profile_id` | `String(36)` | `FK(health_profile.health_profile_id, RESTRICT)`, `NOT NULL` | Exact immutable `health_profile` version |
| `snapshot_id` | `String(36)` | `FK(assessment_snapshot.snapshot_id, RESTRICT)`, `NOT NULL`, `UNIQUE` | Exact immutable `assessment_snapshot` |
| `assignment_id` | `String(36)` | `FK(doctor_patient_assignment.assignment_id, RESTRICT)`, `NOT NULL` | Selected active assignment (`O-04`/`P-12`) |
| `consent_id` | `String(36)` | `FK(consent_record.consent_id, RESTRICT)`, `NOT NULL` | Active `synthetic_demo` consent at creation |
| `reassessment_of_id` | `String(36)` | `FK(assessment.assessment_id, RESTRICT)`, `NULL` | `P-15` immutable linkage |
| `reassessment_reason` | `String(128)` | `NULL` | Required iff `reassessment_of_id IS NOT NULL` |
| `panel_id` | `String(64)` | `NOT NULL` | `'da_a2_resting_v1'` |
| `panel_version` | `String(16)` | `NOT NULL` | `'1.0.0'` |
| `source_contract_version` | `String(32)` | `NOT NULL` | `'term1.c2.intake/v1'` |
| `source_kind` | `String(48)` | `NOT NULL` | `'synthetic_demo_patient_manual'` or `'synthetic_demo_ocr_confirmed'` |
| `stage_complete` | `Boolean` | `NOT NULL` | `True` iff all 5 resting fields present; `False` if optional `trestbps`/`restecg` missing |
| `status` | `String(36)` | `NOT NULL` | Closed C0 §7.1–§7.3 enum (below) |
| `active_attempt_id` | `String(36)` | `NULL`, `UNIQUE` | Trigger-enforced pointer to active `INFERENCE_RUNNING` `inference_attempt` |
| `current_generation` | `Integer` | `NOT NULL` | Starts at `0`; incremented **once** per recovery/retry |
| `current_result_id` | `String(36)` | `NULL`, `UNIQUE` | Trigger-enforced pointer to published `inference_result.result_id` |
| `review_state` | `String(32)` | `NOT NULL` | C3 CAS review state: `'NOT_REVIEWED'`, `'ACCEPTED'`, `'REJECTED'`, `'REASSESSMENT_REQUESTED'` |
| `review_version` | `Integer` | `NOT NULL` | Starts at `0`; incremented atomically on C3 review CAS |
| `created_at` | `String(32)` | `NOT NULL` | Server UTC ISO-8601 |
| `updated_at` | `String(32)` | `NOT NULL` | Server UTC ISO-8601 |

**Closed `assessment.status` enum (`CHECK` constraint, C0 §7.1–§7.3 exact values):**
- `DRAFT`
- `INPUT_VALIDATED`
- `INFERENCE_RUNNING` (`active_attempt_id IS NOT NULL`, `current_result_id IS NULL`)
- `INFERENCE_SUCCEEDED` (`active_attempt_id IS NULL`, `current_result_id IS NOT NULL`)
- `PENDING_REVIEW` (`active_attempt_id IS NULL`, `current_result_id IS NOT NULL`)
- `INFERENCE_ABSTAINED` (`active_attempt_id IS NULL`, `current_result_id IS NULL`)
- `INFERENCE_UNAVAILABLE` (`active_attempt_id IS NULL`, `current_result_id IS NULL`)
- `INFERENCE_ERROR` (`active_attempt_id IS NULL`, `current_result_id IS NULL`)

**Concrete SQLite Cyclic-Pointer Integrity Solution (`R2`):**
Because `inference_attempt` and `inference_result` hold `assessment_id FK -> assessment.assessment_id`, adding `use_alter=True` circular foreign keys on `assessment.active_attempt_id` / `assessment.current_result_id` causes SQLite `ALTER TABLE` failures and Alembic `compare_metadata` drift in `Database.verify_schema()`. Instead, C2 enforces **strict DB-level referential integrity** using:
1. `UniqueConstraint("assessment_id", "attempt_id", name="ux_inference_attempt_assessment_pair")` and `UniqueConstraint("assessment_id", "result_id", name="ux_inference_result_assessment_pair")`.
2. **SQLite `BEFORE INSERT` and `BEFORE UPDATE OF active_attempt_id, current_result_id` triggers** (`tr_assessment_pointer_insert`, `tr_assessment_pointer_update`) in `20261128_07`:
   - If `NEW.active_attempt_id IS NOT NULL`, require `EXISTS (SELECT 1 FROM inference_attempt a WHERE a.attempt_id = NEW.active_attempt_id AND a.assessment_id = NEW.assessment_id AND a.state = 'INFERENCE_RUNNING' AND a.generation = NEW.current_generation)` else `RAISE(ABORT, 'invalid_active_attempt_pointer')`.
   - If `NEW.current_result_id IS NOT NULL`, require `EXISTS (SELECT 1 FROM inference_result r WHERE r.result_id = NEW.current_result_id AND r.assessment_id = NEW.assessment_id)` else `RAISE(ABORT, 'invalid_current_result_pointer')`.
3. `CHECK` constraint pairing `status` with pointer nullability:
   `((status = 'INFERENCE_RUNNING' AND active_attempt_id IS NOT NULL AND current_result_id IS NULL) OR (status IN ('INFERENCE_SUCCEEDED','PENDING_REVIEW') AND active_attempt_id IS NULL AND current_result_id IS NOT NULL) OR (status IN ('DRAFT','INPUT_VALIDATED','INFERENCE_ABSTAINED','INFERENCE_UNAVAILABLE','INFERENCE_ERROR') AND active_attempt_id IS NULL AND current_result_id IS NULL))`
4. `CheckConstraint("current_generation >= 0")`, `CheckConstraint("review_version >= 0")`, `CheckConstraint("review_state IN ('NOT_REVIEWED','ACCEPTED','REJECTED','REASSESSMENT_REQUESTED')")`, `CheckConstraint("source_kind IN ('synthetic_demo_patient_manual','synthetic_demo_ocr_confirmed')")`, and `(reassessment_of_id IS NULL AND reassessment_reason IS NULL) OR (reassessment_of_id IS NOT NULL AND reassessment_reason IS NOT NULL)`.
5. Indexes: `ix_assessment_patient_time (patient_id, created_at)`, `ix_assessment_assignment_time (assignment_id, created_at)`, `ix_assessment_status (status)`.

### 3.4 `inference_attempt` (Lease, Fencing, Idempotency & Recovery per C0 §7.3)

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `attempt_id` | `String(36)` | PK | UUIDv4 |
| `assessment_id` | `String(36)` | `FK(assessment.assessment_id, RESTRICT)`, `NOT NULL` | Target assessment |
| `generation` | `Integer` | `NOT NULL` | Equals `assessment.current_generation` when leased |
| `attempt_idempotency_hash` | `String(64)` | `NOT NULL` | SHA-256 over `(assessment_id, snapshot_sha256, generation, dispatch_kind)` preventing duplicate attempt creation |
| `worker_id` | `String(64)` | `NOT NULL` | Local worker instance ID (`'disabled_stub'` pre-`A3`) |
| `fence_token` | `String(64)` | `NOT NULL` | 64-hex CSPRNG token bound to `(attempt_id, assessment_id, generation)` |
| `state` | `String(36)` | `NOT NULL` | Closed C0 enum: `'INFERENCE_RUNNING'`, `'INFERENCE_SUCCEEDED'`, `'INFERENCE_ABSTAINED'`, `'INFERENCE_UNAVAILABLE'`, `'INFERENCE_ERROR'` |
| `reason_code` | `String(64)` | `NULL` | Closed reason code (e.g. `'real_ai_not_authorized'`, `'authorization_withdrawn'`, `'lease_expired'`, `'worker_error'`) |
| `leased_at` | `String(32)` | `NOT NULL` | UTC timestamp |
| `lease_until` | `String(32)` | `NOT NULL` | `leased_at + 300s` (`P-16`) |
| `completed_at` | `String(32)` | `NULL` | UTC timestamp when terminal |

**Critical Concurrency Indexes & Constraints:**
- `UniqueConstraint("assessment_id", "generation", name="ux_inference_attempt_assessment_gen")`
- `UniqueConstraint("assessment_id", "attempt_idempotency_hash", name="ux_inference_attempt_idempotency")`
- `UniqueConstraint("assessment_id", "attempt_id", name="ux_inference_attempt_assessment_pair")`
- **Partial Unique Index (active attempt invariant):**
  `Index("ux_inference_attempt_one_active", "assessment_id", unique=True, sqlite_where=text("state = 'INFERENCE_RUNNING'"))`
- **C0 §7.3 Atomic Completion CAS (`BEGIN IMMEDIATE`):**
  Completion succeeds **only** if ALL conditions hold:
  1. `attempt.attempt_id == submitted.attempt_id` AND `attempt.assessment_id == submitted.assessment_id`
  2. `assessment.active_attempt_id == attempt.attempt_id` AND `attempt.generation == assessment.current_generation`
  3. `attempt.state == 'INFERENCE_RUNNING'` AND `assessment.status == 'INFERENCE_RUNNING'`
  4. `attempt.worker_id == submitted.worker_id` AND `attempt.fence_token == submitted.fence_token`
  5. **strictly `attempt.lease_until > now_iso`**
  6. active `doctor_patient_assignment` (`revoked_at IS NULL`) AND exact referenced `consent_record` (`revoked_at IS NULL`)
  7. active `A3` authorization + verified `snapshot_sha256` & `result_sha256` + all 6 sibling artifact SHA-256 digests.
  - If (1)–(5) pass but (6) fails (revoked assignment or referenced consent), transition attempt to `INFERENCE_UNAVAILABLE` (`reason_code = 'authorization_withdrawn'`), clear `assessment.active_attempt_id = NULL`, keep `current_result_id = NULL`, set `assessment.status = 'INFERENCE_UNAVAILABLE'`, and write **zero** `inference_result` rows.
  - If any of (1)–(5) fails, reject (`409 stale_attempt_fenced`) with **zero** row mutations.
- **Lease Recovery Rule (`<= now()`):** Scans `state = 'INFERENCE_RUNNING' AND lease_until <= clock.now_iso()` (inclusive `<=`). Inside `BEGIN IMMEDIATE`, marks attempt `INFERENCE_ERROR` (`reason_code = 'lease_expired'`, `completed_at = now`), clears `assessment.active_attempt_id = NULL`, transitions `assessment.status = 'INFERENCE_ERROR'`, and increments `assessment.current_generation` **once** (no double increment, no automatic retry).

### 3.5 `inference_result` (Append-Only Immutable Result Record with Full Digest Binding)

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `result_id` | `String(36)` | PK | UUIDv4 |
| `assessment_id` | `String(36)` | `FK(assessment.assessment_id, RESTRICT)`, `NOT NULL` | Parent assessment |
| `attempt_id` | `String(36)` | `FK(inference_attempt.attempt_id, RESTRICT)`, `NOT NULL`, `UNIQUE` | Exactly one result per `INFERENCE_SUCCEEDED` attempt |
| `generation` | `Integer` | `NOT NULL` | Generation that produced this result |
| `snapshot_id` | `String(36)` | `FK(assessment_snapshot.snapshot_id, RESTRICT)`, `NOT NULL` | Snapshot evaluated |
| `snapshot_sha256` | `String(64)` | `NOT NULL` | Must equal `assessment_snapshot.snapshot_sha256` |
| `schema_version` | `String(32)` | `NOT NULL` | `'term1.c2.result/v1'` |
| `panel_id` | `String(64)` | `NOT NULL` | `'da_a2_resting_v1'` |
| `panel_version` | `String(16)` | `NOT NULL` | `'1.0.0'` |
| `panel_contract_sha256` | `String(64)` | `NOT NULL` | `'c18ad4cd2cf08f6fefb2e340573760da7000bc1d8eb4ad38783b873c018e57b8'` |
| `source_contract_version` | `String(32)` | `NOT NULL` | `'term1.c2.intake/v1'` |
| `source_kind` | `String(48)` | `NOT NULL` | Copied from `assessment.source_kind` |
| `model_id` | `String(64)` | `NOT NULL` | `'cai_real_da-a2_da_a2_resting_v1'` |
| `model_version` | `String(32)` | `NOT NULL` | `'0.2.0'` |
| `protocol_id` | `String(64)` | `NOT NULL` | `'CAI-D047-CLEVELAND-EXPLORATORY-V1'` |
| `execution_profile` | `String(48)` | `NOT NULL` | `'CLEVELAND_D047_FROZEN_V1'` |
| `bundle_dir_name` | `String(128)` | `NOT NULL` | `'cai_real_cleveland_d047_20261027T070610Z_deffa577'` |
| `manifest_sha256` | `String(64)` | `NOT NULL` | `'089f931be27be67606b9d2622beea54208976f1743a70909029619f50a6e5d4a'` |
| `source_sha256` | `String(64)` | `NOT NULL` | `'a74b7efa387bc9d108d7d0115d831fe9b414b29ae7124f331b622b4efa0427c8'` |
| `model_joblib_sha256` | `String(64)` | `NOT NULL` | Sibling `model.joblib` SHA-256 |
| `preprocessing_json_sha256` | `String(64)` | `NOT NULL` | Sibling `preprocessing.json` SHA-256 |
| `calibration_json_sha256` | `String(64)` | `NOT NULL` | Sibling `calibration.json` SHA-256 |
| `shap_background_sha256` | `String(64)` | `NOT NULL` | Sibling `shap_background.json` SHA-256 |
| `evaluation_summary_sha256` | `String(64)` | `NOT NULL` | Sibling `evaluation_summary.json` SHA-256 |
| `protocol_md_sha256` | `String(64)` | `NOT NULL` | Sibling `protocol.md` SHA-256 |
| `serving_eligibility` | `String(32)` | `NOT NULL` | `'RESEARCH_ONLY'` (`CheckConstraint`) |
| `clinical_use_authorized` | `Boolean` | `NOT NULL` | `False` (`CheckConstraint("clinical_use_authorized = 0")`) |
| `raw_model_score` | `Float` | `NOT NULL` | Estimator probability |
| `raw_model_log_odds` | `Float` | `NULL` | Estimator logit |
| `calibrated_research_score` | `Float` | `NOT NULL` | Calibrated score on `[0, 1]` |
| `calibrated_log_odds` | `Float` | `NOT NULL` | Calibrated log-odds |
| `calibration_meta_json` | `JSON` | `NOT NULL` | `intercept`, `slope`, `input_link`, `fit_scope`, `development_prevalence` |
| `shap_json` | `JSON` | `NOT NULL` | Grouped LinearSHAP on `calibrated_log_odds`, `sum_check_passed`, `max_abs_discrepancy` (zero background rows!) |
| `lime_status` | `String(32)` | `NOT NULL` | `'CERTIFIED'` or `'WITHHELD_QUALITY_NOT_MET'` |
| `lime_json` | `JSON` | `NULL` | Present iff `lime_status == 'CERTIFIED'` |
| `lime_meta_json` | `JSON` | `NOT NULL` | Fidelity/stability verdict from `ai/lime_quality.py` |
| `fold_dispersion_json` | `JSON` | `NOT NULL` | Descriptive outer-fold spread |
| `limitations_json` | `JSON` | `NOT NULL` | Fixed limitation declarations |
| `result_sha256` | `String(64)` | `NOT NULL` | Canonical SHA-256 over scores, explanations, snapshot digest, and artifact/provenance bindings |
| `published_at` | `String(32)` | `NOT NULL` | Server UTC timestamp |

`UniqueConstraint("assessment_id", "result_id", name="ux_inference_result_assessment_pair")` enables the SQLite trigger integrity check on `assessment.current_result_id`. Note that no `exploratory_threshold` or `exploratory_above_threshold` columns are surfaced to patients.

---

## 4. Migration `20261128_08_c2_documents_ocr.py`

**`down_revision = "20261128_07"`**

### 4.1 `medical_document`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `document_id` | `String(36)` | PK | UUIDv4 |
| `patient_id` | `String(36)` | `FK(patient_profile.patient_id, RESTRICT)`, `NOT NULL` | Owner patient |
| `uploaded_by_user_id` | `String(36)` | `FK(user_account.user_id, RESTRICT)`, `NOT NULL` | Uploader actor |
| `document_kind` | `String(48)` | `NOT NULL` | `'RESTING_CARDIAC_DEMO_REPORT'` or `'UNRELATED_LAB_DEMO_REPORT'` |
| `fixture_template_id` | `String(64)` | `NOT NULL` | Verified project fixture allowlist template ID (`'CAI-DEMO-RESTING-CARDIAC-REPORT-V1'`, `'CAI-DEMO-UNRELATED-LABS-V1'`) |
| `fixture_manifest_sha256` | `String(64)` | `NOT NULL` | SHA-256 matching project-generated fixture allowlist entry |
| `original_filename_sanitized` | `String(128)` | `NOT NULL` | Basename sanitized for display only; never used in storage path |
| `declared_media_type` | `String(64)` | `NOT NULL` | Verified against magic bytes: `'application/pdf'`, `'image/png'`, `'image/jpeg'` |
| `byte_size` | `Integer` | `NOT NULL` | `0 <= byte_size <= 5242880` (`0` allowed only while `upload_status = 'PENDING_SCAN'`; `>= 1` when `'STORED'`) |
| `page_count` | `Integer` | `NOT NULL` | `0 <= page_count <= 3` (`>= 1` when `'STORED'`) |
| `content_sha256` | `String(64)` | `NULL` | Non-null SHA-256 of exact stored bytes once `'STORED'` |
| `storage_key` | `String(160)` | `NOT NULL`, `UNIQUE` | Server-generated `<patient_id>/<document_id>.bin` |
| `upload_status` | `String(24)` | `NOT NULL` | `'PENDING_SCAN'`, `'STORED'`, `'UPLOAD_FAILED'`, `'SUPERSEDED'` (quota reservation checks `upload_status IN ('PENDING_SCAN','STORED')`) |
| `created_at` | `String(32)` | `NOT NULL` | UTC timestamp |

### 4.2 `document_extraction` & `extraction_field`

- **`document_extraction`**:
  - `extraction_id`: `String(36)`, PK
  - `document_id`: `String(36)`, `FK(medical_document.document_id, RESTRICT)`, `NOT NULL`
  - `extraction_version`: `Integer`, `NOT NULL` (`>= 1`; immutable once `is_confirmed = True`)
  - `document_sha256`: `String(64)`, `NOT NULL` (matches `medical_document.content_sha256`)
  - `extraction_mode`: `String(24)`, `NOT NULL` (`'PDF_TEXT'`, `'RASTER_OCR'`, `'FAILED'`)
  - `template_id`: `String(64)`, `NULL` (`'CAI-DEMO-RESTING-CARDIAC-REPORT-V1'`, `'CAI-DEMO-UNRELATED-LABS-V1'`, or `NULL`)
  - `template_version`: `String(16)`, `NULL`
  - `engine_name`: `String(48)`, `NOT NULL` (`'pdfminer'`, `'tesseract'`)
  - `engine_version`: `String(64)`, `NOT NULL`
  - `extraction_status`: `String(32)`, `NOT NULL` (`'EXTRACTED_DRAFT'`, `'UNSUPPORTED_TEMPLATE'`, `'NEEDS_MANUAL_REVIEW'`, `'CONFIRMED_BY_PATIENT'`, `'FAILED'`)
  - `is_confirmed`: `Boolean`, `NOT NULL` (starts `False`; becomes `True` only on `DOC6`, permanently locking this version)
  - `extracted_text_bytes`: `Integer`, `NOT NULL` (`0 <= extracted_text_bytes <= 1048576` — `1 MiB` aggregate limit)
  - `raw_text_sha256`: `String(64)`, `NULL`
  - `raw_text_excerpt_json`: `JSON`, `NOT NULL` (bounded line/region snippet metadata, never logged)
  - `created_at`: `String(32)`, `NOT NULL`
  - `confirmed_at`: `String(32)`, `NULL`
  - `UniqueConstraint("document_id", "extraction_version", name="ux_document_extraction_version")`

- **`extraction_field`**:
  - `field_record_id`: `String(36)`, PK
  - `extraction_id`: `String(36)`, `ForeignKey("document_extraction.extraction_id", ondelete="RESTRICT")`, `NOT NULL`
  - `document_id`: `String(36)`, `ForeignKey("medical_document.document_id, RESTRICT")`, `NOT NULL`
  - `field_name`: `String(64)`, `NOT NULL` (`'age'`, `'sex'`, `'cp'`, `'trestbps'`, `'restecg'`, or `'unrelated_lab_*'`)
  - `page_number`: `Integer`, `NOT NULL` (`1 <= page_number <= 3`)
  - `region_json`: `JSON`, `NULL`
  - `raw_value_text`: `String(128)`, `NULL`
  - `parsed_value_json`: `JSON`, `NULL` (`NULL` if low-confidence/conflict/missing)
  - `confirmed_value_json`: `JSON`, `NULL`
  - `unit`: `String(32)`, `NULL`
  - `confidence`: `Float`, `NULL`
  - `parse_status`: `String(32)`, `NOT NULL` (`'PARSED'`, `'LOW_CONFIDENCE'`, `'CONFLICT_REVIEW_REQUIRED'`, `'INVALID_VALUE'`, `'MISSING'`, `'UNRELATED_IGNORED'`)
  - `conflict_flag`: `Boolean`, `NOT NULL`
  - `field_provenance`: `String(40)`, `NOT NULL` (`'OCR_EXTRACTED_UNCONFIRMED'`, `'OCR_EXTRACTED_PATIENT_CONFIRMED'`, `'PATIENT_ENTERED_FROM_OCR_DRAFT'`, `'UNRELATED_NON_MODEL_FIELD'`)
  - `UniqueConstraint("extraction_id", "field_name", name="ux_extraction_field_name")`

### 4.3 `extraction_event` (Append-Only Provenance Audit)

- `event_id`: `String(36)`, PK
- `document_id`: `String(36)`, `FK(medical_document.document_id, RESTRICT)`, `NOT NULL`
- `extraction_id`: `String(36)`, `FK(document_extraction.extraction_id, RESTRICT)`, `NULL`
- `extraction_version`: `Integer`, `NULL`
- `event_type`: `String(32)`, `NOT NULL` (`'UPLOADED'`, `'EXTRACTED'`, `'EXTRACTION_FAILED'`, `'PATIENT_EDITED'`, `'PATIENT_CONFIRMED'`, `'EDITED_AND_CONFIRMED'`, `'DOCTOR_ACKNOWLEDGED'`)
- `actor_user_id`: `String(36)`, `FK(user_account.user_id, RESTRICT)`, `NOT NULL`
- `actor_role`: `String(16)`, `NOT NULL`
- `field_diffs_json`: `JSON`, `NOT NULL`
- `recorded_at`: `String(32)`, `NOT NULL`

### 4.4 `assessment_document` & `document_acknowledgement` (`DOC9`)

- **`assessment_document`** (Immutable Snapshot Binding):
  - `binding_id`: `String(36)`, PK
  - `assessment_id`: `String(36)`, `FK(assessment.assessment_id, RESTRICT)`, `NOT NULL`
  - `document_id`: `String(36)`, `FK(medical_document.document_id, RESTRICT)`, `NOT NULL`
  - `extraction_id`: `String(36)`, `FK(document_extraction.extraction_id, RESTRICT)`, `NULL` (mandatory & confirmed for `OCR_SOURCE_REPORT`)
  - `extraction_version`: `Integer`, `NULL` (pinned whenever `extraction_id IS NOT NULL`)
  - `document_sha256_at_bind`: `String(64)`, `NOT NULL`
  - `attachment_role`: `String(32)`, `NOT NULL` (`'SUPPORTING_REPORT'`, `'OCR_SOURCE_REPORT'`, `'UNRELATED_LAB_ATTACHMENT'`)
  - `created_at`: `String(32)`, `NOT NULL`
  - `UniqueConstraint("assessment_id", "document_id", name="ux_assessment_document_pair")`

- **`document_acknowledgement`** (Append-Only `DOC9` Doctor Lock):
  - `acknowledgement_id`: `String(36)`, PK
  - `doctor_user_id`: `String(36)`, `FK(user_account.user_id, RESTRICT)`, `NOT NULL`
  - `assignment_id`: `String(36)`, `FK(doctor_patient_assignment.assignment_id, RESTRICT)`, `NOT NULL`
  - `assessment_id`: `String(36)`, `FK(assessment.assessment_id, RESTRICT)`, `NOT NULL`
  - `document_id`: `String(36)`, `FK(medical_document.document_id, RESTRICT)`, `NOT NULL`
  - `extraction_id`: `String(36)`, `FK(document_extraction.extraction_id, RESTRICT)`, `NULL`
  - `extraction_version`: `Integer`, `NULL`
  - `acknowledged_at`: `String(32)`, `NOT NULL`
  - `UniqueConstraint("assignment_id", "assessment_id", "document_id", "extraction_id", "extraction_version", name="ux_doc_ack_exact_version")`

---

## 5. Canonical Hashing & Tamper-Detection Rules

1. **Canonical JSON Encoding:**
   `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")`
   Matches `backend/app/term1/idempotency.py::canonical_public` identically.
2. **Snapshot Integrity Check:** Before dispatching to the AI worker (and again inside C3/C4 doctor review read checks), the service recomputes `sha256(canonical(snapshot_json))` and verifies equality with `assessment_snapshot.snapshot_sha256`, `assessment_snapshot.panel_contract_sha256 == DA_A2_RESTING_PANEL.contract_sha256`, and `assessment_snapshot.panel_version == "1.0.0"`.
3. **Result Integrity Check:** Before updating `assessment.current_result_id`, the backend verifies `inference_result.result_sha256` against canonical `(snapshot_sha256, schema_version, panel_id, panel_version, panel_contract_sha256, source_contract_version, source_kind, model_id, model_version, manifest_sha256, source_sha256, all 6 sibling file SHA-256s, calibrated_research_score, calibrated_log_odds, shap_json, lime_status, lime_json)`.
4. **TOCTOU-Free Document Integrity Check:** During upload (`DOC1`), OCR extraction (`DOC4`), assessment binding (`S1`), and private download (`DOC3`/`DOC7`), the service computes `sha256` directly over the **opened/streamed bytes** and verifies equality with `medical_document.content_sha256` (and `assessment_document.document_sha256_at_bind`). Any mismatch aborts the transfer (`500 document_integrity_mismatch` + `WORKFLOW_AUDIT_EVENT`).
