# CardioAssist-AI Term 1 — C2 Relational Schema, Invariants, and Additive Migration Spec

**Date:** 2026-11-27 (UTC / Africa/Cairo)
**Status:** `PROPOSED — NOT APPROVED, NOT IMPLEMENTED`
**Migration Base:** `20261126_06` (`backend/migrations/versions/20261126_06_pepper_binding.py`)
**Scope:** C2 Clinical Intake, Assessment Snapshot, Lease/Fencing Inference Persistence (`20261128_07`), and Bounded Document/OCR Intake (`20261128_08`)

---

## 1. Compatibility Rules With C1 & `Database.verify_schema()`

1. **Zero Modification to `01`–`06`:** `20261017_01` through `20261126_06` remain byte-for-byte unchanged.
2. **Exact ORM ↔ Migration Parity:** `backend/app/storage/database.py::Database.verify_schema()` runs Alembic `compare_metadata(..., opts={"compare_type": True})` plus explicit primary-key inspection, `PRAGMA foreign_keys=ON`, `PRAGMA integrity_check`, and `PRAGMA foreign_key_check` on every startup. Every column length, nullability, PK, FK (`ondelete="RESTRICT"`), CHECK constraint, and index in the C2 SQLAlchemy models MUST match migrations `07` and `08` identically.
3. **RB-C1 Rollback Policy Preservation:** Both `20261128_07` and `20261128_08` implement the exact `RB-C1` downgrade guard from `20261126_06_pepper_binding.py`:
   - Refuse `as_sql=True` offline downgrade (`RuntimeError`).
   - Query every C1 and C2 table (`LIMIT 1`); if **any** Term 1 row exists, refuse in-place downgrade (`RuntimeError`) and require verified backup restoration.
4. **No Global `patient.doctor_id`:** Consistent with `R-01`/`O-04` and C1, `health_profile`, `assessment`, and `medical_document` never store a global `doctor_id`. Doctor visibility derives exclusively from `assessment.assignment_id -> doctor_patient_assignment` (where `revoked_at IS NULL`).
5. **Audit Table Extension (`workflow_audit_event`):** In C1 (`20261126_02`), `workflow_audit_event` enforces a CHECK constraint only on `outcome` (`ck_workflow_audit_outcome`), **not** on `event_type` or `subject_type` (those are enforced in `backend/app/term1/constants.py` and Python code). Thus C2 extends `constants.py` additively with C2/Document event types and subject types without altering `workflow_audit_event` DDL.

---

## 2. Entity-Relationship Overview (C1 → C2 Additive Links)

```
C1 (Frozen)
├── patient_profile (patient_id)
│     ├── 1:1 ──> health_profile (profile_id, patient_id UNIQUE)
│     │              └── 1:N ──> health_profile_revision (revision_id)
│     ├── 1:N ──> medical_document (document_id)
│     │              ├── 1:N ──> document_extraction (extraction_id)
│     │              │              └── 1:N ──> extraction_field (field_record_id)
│     │              └── 1:N ──> extraction_event (event_id, append-only)
│     └── 1:N ──> assessment (assessment_id, assignment_id -> doctor_patient_assignment)
│                    ├── self FK (reassessment_of_id -> assessment.assessment_id)
│                    ├── 1:N ──> assessment_document (assessment_id, document_id)
│                    ├── 1:N ──> inference_attempt (attempt_id; <=1 active via partial UNIQUE)
│                    ├── 1:N ──> inference_result (result_id, append-only immutable)
│                    └── 0..1 ─> current_result_id -> inference_result.result_id (CAS pointer)
└── doctor_patient_assignment (assignment_id) & consent_record (consent_id)
```

---

## 3. Migration `20261128_07_c2_clinical_intake_inference.py`

**`down_revision = "20261126_06"`**

### 3.1 `health_profile` & `health_profile_revision`

- **`health_profile`** (mutable current working baseline for one patient; one row per patient):
  - `profile_id`: `String(36)`, PK
  - `patient_id`: `String(36)`, `ForeignKey("patient_profile.patient_id", ondelete="RESTRICT")`, `NOT NULL`, `UniqueConstraint("patient_id", name="ux_health_profile_patient")`
  - `schema_version`: `String(32)`, `NOT NULL` (initially `"da_a2_resting_v1"`)
  - `revision_number`: `Integer`, `NOT NULL` (`>= 1`)
  - `fields_json`: `JSON`, `NOT NULL` (canonical `{features, units, missing_reasons}` validated against `da_a2_resting_v1`)
  - `provenance_json`: `JSON`, `NOT NULL` (field-level origin: `manual` vs `ocr_confirmed`, source `document_id`/`extraction_id` when applicable)
  - `snapshot_sha256`: `String(64)`, `NOT NULL`
  - `created_at`: `String(32)`, `NOT NULL`
  - `updated_at`: `String(32)`, `NOT NULL`
  - `CheckConstraint("revision_number >= 1", name="ck_health_profile_revision_positive")`

- **`health_profile_revision`** (append-only immutable history of every profile save):
  - `revision_id`: `String(36)`, PK
  - `profile_id`: `String(36)`, `ForeignKey("health_profile.profile_id", ondelete="RESTRICT")`, `NOT NULL`
  - `patient_id`: `String(36)`, `ForeignKey("patient_profile.patient_id", ondelete="RESTRICT")`, `NOT NULL`
  - `revision_number`: `Integer`, `NOT NULL`
  - `schema_version`: `String(32)`, `NOT NULL`
  - `fields_json`: `JSON`, `NOT NULL`
  - `provenance_json`: `JSON`, `NOT NULL`
  - `snapshot_sha256`: `String(64)`, `NOT NULL`
  - `actor_user_id`: `String(36)`, `ForeignKey("user_account.user_id", ondelete="RESTRICT")`, `NOT NULL`
  - `recorded_at`: `String(32)`, `NOT NULL`
  - `UniqueConstraint("profile_id", "revision_number", name="ux_health_profile_revision_seq")`

### 3.2 `assessment`

Immutable submission snapshot + current execution state + CAS generation/result pointers.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `assessment_id` | `String(36)` | PK | Server-generated UUIDv4 |
| `patient_id` | `String(36)` | `FK(patient_profile.patient_id, RESTRICT)`, `NOT NULL` | Submitting patient |
| `assignment_id` | `String(36)` | `FK(doctor_patient_assignment.assignment_id, RESTRICT)`, `NOT NULL` | Selected active assignment (`O-04`/`P-12`) |
| `consent_id` | `String(36)` | `FK(consent_record.consent_id, RESTRICT)`, `NOT NULL` | Active `synthetic_demo` consent at creation |
| `reassessment_of_id` | `String(36)` | `FK(assessment.assessment_id, RESTRICT)`, `NULL` | `P-15` immutable linkage |
| `reassessment_reason` | `String(128)` | `NULL` | Required iff `reassessment_of_id IS NOT NULL` |
| `panel_id` | `String(64)` | `NOT NULL` | Closed: `'da_a2_resting_v1'` |
| `panel_contract_sha256` | `String(64)` | `NOT NULL` | `'c18ad4cd2cf08f6fefb2e340573760da7000bc1d8eb4ad38783b873c018e57b8'` |
| `source_provenance` | `String(48)` | `NOT NULL` | Closed enum (`synthetic_demo_patient_manual`, `synthetic_demo_ocr_confirmed`, `clinician_verified_demo`) |
| `stage_complete` | `Boolean` | `NOT NULL` | `True` iff all 5 resting fields present; `False` if optional `trestbps`/`restecg` missing |
| `snapshot_json` | `JSON` | `NOT NULL` | Frozen canonical input `{panel_id, features, units, missing_reasons}` |
| `snapshot_sha256` | `String(64)` | `NOT NULL` | SHA-256 of canonical UTF-8 JSON (`sort_keys=True, separators=(",",":"), allow_nan=False`) |
| `provenance_json` | `JSON` | `NOT NULL` | Frozen server-assigned field provenance & document/extraction binding summary |
| `provenance_sha256` | `String(64)` | `NOT NULL` | SHA-256 of canonical UTF-8 `provenance_json` |
| `status` | `String(36)` | `NOT NULL` | Closed enum (below) |
| `current_generation` | `Integer` | `NOT NULL` | Starts at `0`; incremented on each attempt lease |
| `current_result_id` | `String(36)` | `NULL` | Logical pointer to `inference_result.result_id` (updated atomically on CAS publication; `NULL` when no published result exists — enforced via `UNIQUE` + application CAS and optional deferred/trigger check or post-creation FK if supported cleanly) |
| `submitted_at` | `String(32)` | `NOT NULL` | Server UTC ISO-8601 |
| `updated_at` | `String(32)` | `NOT NULL` | Server UTC ISO-8601 |

**Closed `assessment.status` enum (`CHECK` constraint):**
- `QUEUED` (execution slot reserved, awaiting worker)
- `RUNNING` (worker actively leased)
- `PENDING_REVIEW` (only valid after durable `inference_result` CAS publication; `current_result_id IS NOT NULL`)
- `INFERENCE_UNAVAILABLE` (A3 disabled / unratified; `current_result_id IS NULL`)
- `ABSTAINED` (model/input abstention; `current_result_id IS NULL`)
- `FAILED` (worker/validation failure or lease exhausted; `current_result_id IS NULL`)
- `ABORTED_AUTHORIZATION_REVOKED` (assignment or consent revoked before completion; `current_result_id IS NULL`)

**Integrity `CHECK` constraints on `assessment`:**
- `(reassessment_of_id IS NULL AND reassessment_reason IS NULL) OR (reassessment_of_id IS NOT NULL AND reassessment_reason IS NOT NULL)`
- `current_generation >= 0`
- `(status = 'PENDING_REVIEW' AND current_result_id IS NOT NULL) OR (status <> 'PENDING_REVIEW' AND current_result_id IS NULL)` — **enforces at DB level that NO score pointer can exist unless status is `PENDING_REVIEW`!**
- `source_provenance IN ('synthetic_demo_patient_manual','synthetic_demo_ocr_confirmed','clinician_verified_demo')`
- Indexes: `ix_assessment_patient_time (patient_id, submitted_at)`, `ix_assessment_assignment_time (assignment_id, submitted_at)`, `ix_assessment_status (status)`.

> **Note on circular FK in SQLite:** Because `inference_result` holds `assessment_id FK -> assessment.assessment_id` and `assessment` holds `current_result_id`, SQLite does not support adding a cyclic FK with `ALTER TABLE` cleanly after creation without `use_alter=True` / triggers. Define `assessment.current_result_id` as `String(36) NULL` with `UniqueConstraint("current_result_id", name="ux_assessment_current_result")` + `UniqueConstraint("assessment_id", "current_result_id")` pairing, and verify integrity via `inference_result (assessment_id, result_id)` in `tx.write_transaction` + C2 migration test (or composite FK after table creation if dialect supports; keeping SQLite/SQLAlchemy `verify_schema()` 100% consistent).

### 3.3 `inference_attempt` (Lease, Fencing, Recovery)

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `attempt_id` | `String(36)` | PK | UUIDv4 |
| `assessment_id` | `String(36)` | `FK(assessment.assessment_id, RESTRICT)`, `NOT NULL` | Target assessment |
| `generation` | `Integer` | `NOT NULL` | Equals `assessment.current_generation` when leased |
| `fence_token` | `String(64)` | `NOT NULL` | 64-hex CSPRNG/HMAC token bound to this lease |
| `status` | `String(36)` | `NOT NULL` | `'QUEUED'`, `'RUNNING'`, `'SUCCEEDED'`, `'FAILED'`, `'TIMED_OUT'`, `'STALE_REJECTED'`, `'ABORTED_AUTHORIZATION_REVOKED'` |
| `worker_id` | `String(64)` | `NULL` | Local worker instance tag |
| `error_code` | `String(64)` | `NULL` | Closed error/failure code (never raw exception text) |
| `leased_at` | `String(32)` | `NOT NULL` | UTC timestamp |
| `lease_expires_at` | `String(32)` | `NOT NULL` | `leased_at + 300s` (`P-16`) |
| `completed_at` | `String(32)` | `NULL` | UTC timestamp when terminal |

**Critical Concurrency Indexes & Constraints:**
- `UniqueConstraint("assessment_id", "generation", name="ux_inference_attempt_assessment_gen")`
- **Partial Unique Index (active attempt invariant):**
  `Index("ux_inference_attempt_one_active", "assessment_id", unique=True, sqlite_where=text("status IN ('QUEUED','RUNNING')"))`
  Guarantees at most **one** active attempt per assessment at any moment.
- **Lease Recovery Rule (`OQ-3`):** An active attempt may be reclaimed inside `BEGIN IMMEDIATE` **iff `lease_expires_at <= clock.now_iso()`** (inclusive `<=`). Recovery marks the expired attempt `TIMED_OUT` (`completed_at = now`), increments `assessment.current_generation`, and issues a fresh `(generation + 1, new_fence_token)` row in the same atomic transaction.
- **Stale Completion Fencing:** Late worker completion checks `assessment.current_generation == attempt.generation AND attempt.fence_token == submitted_fence_token AND attempt.status IN ('QUEUED','RUNNING')`. Any mismatch fails CAS and marks the late attempt (if still open) `STALE_REJECTED` without touching `assessment.current_result_id`!

### 3.4 `inference_result` (Append-Only Immutable Result Record)

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `result_id` | `String(36)` | PK | UUIDv4 |
| `assessment_id` | `String(36)` | `FK(assessment.assessment_id, RESTRICT)`, `NOT NULL` | Parent assessment |
| `attempt_id` | `String(36)` | `FK(inference_attempt.attempt_id, RESTRICT)`, `NOT NULL`, `UNIQUE` | Exactly one result per successful attempt |
| `generation` | `Integer` | `NOT NULL` | Generation that produced this result |
| `model_id` | `String(64)` | `NOT NULL` | `'cai_real_da-a2_da_a2_resting_v1'` |
| `model_version` | `String(32)` | `NOT NULL` | `'0.2.0'` |
| `protocol_id` | `String(64)` | `NOT NULL` | `'CAI-D047-CLEVELAND-EXPLORATORY-V1'` |
| `bundle_dir_name` | `String(128)` | `NOT NULL` | `'cai_real_cleveland_d047_20261027T070610Z_deffa577'` |
| `manifest_sha256` | `String(64)` | `NOT NULL` | Verified manifest digest |
| `panel_id` | `String(64)` | `NOT NULL` | `'da_a2_resting_v1'` |
| `panel_contract_sha256` | `String(64)` | `NOT NULL` | `'c18ad4cd2cf08f6fefb2e340573760da7000bc1d8eb4ad38783b873c018e57b8'` |
| `source_provenance` | `String(48)` | `NOT NULL` | Copied from `assessment.source_provenance` |
| `serving_eligibility` | `String(32)` | `NOT NULL` | `'RESEARCH_ONLY'` (`CheckConstraint`) |
| `clinical_use_authorized` | `Boolean` | `NOT NULL` | `False` (`CheckConstraint("clinical_use_authorized = 0")`) |
| `raw_model_score` | `Float` | `NOT NULL` | Estimator probability |
| `raw_model_log_odds` | `Float` | `NULL` | Estimator logit |
| `calibrated_research_score` | `Float` | `NOT NULL` | Calibrated score on `[0, 1]` |
| `calibrated_log_odds` | `Float` | `NOT NULL` | Calibrated log-odds |
| `exploratory_threshold` | `Float` | `NOT NULL` | `0.5` |
| `exploratory_above_threshold` | `Boolean` | `NOT NULL` | `calibrated_research_score >= exploratory_threshold` |
| `calibration_meta_json` | `JSON` | `NOT NULL` | `intercept`, `slope`, `input_link`, `fit_scope`, `development_prevalence` |
| `shap_json` | `JSON` | `NOT NULL` | Grouped LinearSHAP on `calibrated_log_odds`, `sum_check_passed`, `max_abs_discrepancy` (no background rows!) |
| `lime_status` | `String(32)` | `NOT NULL` | `'CERTIFIED'` or `'UNRELIABLE_WITHHELD'` |
| `lime_json` | `JSON` | `NULL` | Present when certified; quality metrics always retained in `lime_meta_json` |
| `lime_meta_json` | `JSON` | `NOT NULL` | Fidelity/stability verdict from `ai/lime_quality.py` |
| `fold_dispersion_json` | `JSON` | `NOT NULL` | Descriptive outer-fold spread |
| `limitations_json` | `JSON` | `NOT NULL` | Fixed limitation declarations |
| `published_at` | `String(32)` | `NOT NULL` | Server UTC timestamp |

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
| `original_filename_sanitized` | `String(128)` | `NOT NULL` | Basename sanitized for display only; never used in storage path |
| `declared_media_type` | `String(64)` | `NOT NULL` | Verified against magic bytes: `'application/pdf'`, `'image/png'`, `'image/jpeg'` |
| `byte_size` | `Integer` | `NOT NULL` | `1 <= byte_size <= 5242880` (`5 MiB`) |
| `page_count` | `Integer` | `NOT NULL` | `1 <= page_count <= 3` (`1` for PNG/JPEG) |
| `content_sha256` | `String(64)` | `NOT NULL` | SHA-256 of exact stored bytes |
| `storage_relpath` | `String(160)` | `NOT NULL`, `UNIQUE` | Server-generated `<patient_id>/<document_id>.bin` |
| `upload_status` | `String(24)` | `NOT NULL` | `'STORED'`, `'SUPERSEDED'` (soft status; no destructive deletion of evidence linked to assessments) |
| `created_at` | `String(32)` | `NOT NULL` | UTC timestamp |

### 4.2 `document_extraction` & `extraction_field`

- **`document_extraction`**:
  - `extraction_id`: `String(36)`, PK
  - `document_id`: `String(36)`, `FK(medical_document.document_id, RESTRICT)`, `NOT NULL`
  - `document_sha256`: `String(64)`, `NOT NULL` (matches `medical_document.content_sha256` at extraction time)
  - `extraction_mode`: `String(24)`, `NOT NULL` (`'PDF_TEXT'`, `'RASTER_OCR'`, `'FAILED'`)
  - `template_id`: `String(64)`, `NULL` (`'CAI-DEMO-RESTING-CARDIAC-REPORT-V1'`, `'CAI-DEMO-UNRELATED-LABS-V1'`, or `NULL` if unrecognized)
  - `template_version`: `String(16)`, `NULL`
  - `engine_name`: `String(48)`, `NOT NULL` (e.g., `'pypdf'`, `'tesseract'`)
  - `engine_version`: `String(64)`, `NOT NULL`
  - `extraction_status`: `String(32)`, `NOT NULL` (`'EXTRACTED_DRAFT'`, `'UNSUPPORTED_TEMPLATE'`, `'NEEDS_MANUAL_REVIEW'`, `'CONFIRMED_BY_PATIENT'`, `'DOCTOR_VERIFIED'`, `'DOCTOR_REJECTED'`, `'FAILED'`)
  - `raw_text_sha256`: `String(64)`, `NULL` (digest of raw extracted text — avoids dumping large raw OCR strings in operational logs while enabling audit)
  - `raw_text_excerpt_json`: `JSON`, `NOT NULL` (bounded line/region snippet metadata for the document, never logged)
  - `created_at`: `String(32)`, `NOT NULL`
  - `confirmed_at`: `String(32)`, `NULL`

- **`extraction_field`**:
  - `field_record_id`: `String(36)`, PK
  - `extraction_id`: `String(36)`, `ForeignKey("document_extraction.extraction_id", ondelete="RESTRICT")`, `NOT NULL`
  - `document_id`: `String(36)`, `ForeignKey("medical_document.document_id, RESTRICT")`, `NOT NULL`
  - `field_name`: `String(64)`, `NOT NULL` (`'age'`, `'sex'`, `'cp'`, `'trestbps'`, `'restecg'`, or `'unrelated_lab_*'`)
  - `page_number`: `Integer`, `NOT NULL` (`>= 1`)
  - `region_json`: `JSON`, `NULL` (bounding box / line anchor if available)
  - `raw_value_text`: `String(128)`, `NULL`
  - `parsed_value_json`: `JSON`, `NULL` (typed candidate value before edit; `NULL` if low-confidence/conflict/missing)
  - `confirmed_value_json`: `JSON`, `NULL` (final patient-confirmed value)
  - `unit`: `String(32)`, `NULL`
  - `confidence`: `Float`, `NULL` (nullable if PDF text extraction has no OCR confidence)
  - `parse_status`: `String(32)`, `NOT NULL` (`'PARSED'`, `'LOW_CONFIDENCE'`, `'CONFLICT_REVIEW_REQUIRED'`, `'INVALID_VALUE'`, `'MISSING'`, `'UNRELATED_IGNORED'`)
  - `conflict_flag`: `Boolean`, `NOT NULL`
  - `field_provenance`: `String(40)`, `NOT NULL` (`'OCR_EXTRACTED_UNCONFIRMED'`, `'OCR_EXTRACTED_PATIENT_CONFIRMED'`, `'PATIENT_ENTERED_FROM_OCR_DRAFT'`, `'UNRELATED_NON_MODEL_FIELD'`)
  - `UniqueConstraint("extraction_id", "field_name", name="ux_extraction_field_name")`

### 4.3 `extraction_event` (Append-Only Provenance Audit)

- `event_id`: `String(36)`, PK
- `document_id`: `String(36)`, `FK(medical_document.document_id, RESTRICT)`, `NOT NULL`
- `extraction_id`: `String(36)`, `FK(document_extraction.extraction_id, RESTRICT)`, `NULL`
- `event_type`: `String(32)`, `NOT NULL` (`'UPLOADED'`, `'EXTRACTED'`, `'EXTRACTION_FAILED'`, `'PATIENT_EDITED'`, `'PATIENT_CONFIRMED'`, `'DOCTOR_VERIFIED'`, `'DOCTOR_REJECTED'`)
- `actor_user_id`: `String(36)`, `FK(user_account.user_id, RESTRICT)`, `NOT NULL`
- `actor_role`: `String(16)`, `NOT NULL`
- `field_diffs_json`: `JSON`, `NOT NULL`
- `recorded_at`: `String(32)`, `NOT NULL`

### 4.4 `assessment_document` (Immutable Snapshot Binding)

- `binding_id`: `String(36)`, PK
- `assessment_id`: `String(36)`, `FK(assessment.assessment_id, RESTRICT)`, `NOT NULL`
- `document_id`: `String(36)`, `FK(medical_document.document_id, RESTRICT)`, `NOT NULL`
- `extraction_id`: `String(36)`, `FK(document_extraction.extraction_id, RESTRICT)`, `NULL` (present when OCR-confirmed extraction contributed or was reviewed; `NULL` for manual-path supporting attachment without OCR)
- `document_sha256_at_bind`: `String(64)`, `NOT NULL` (pins immutable file bytes at submission time)
- `attachment_role`: `String(32)`, `NOT NULL` (`'SUPPORTING_REPORT'`, `'OCR_SOURCE_REPORT'`, `'UNRELATED_LAB_ATTACHMENT'`)
- `created_at`: `String(32)`, `NOT NULL`
- `UniqueConstraint("assessment_id", "document_id", name="ux_assessment_document_pair")`

---

## 5. Canonical Hashing & Tamper-Detection Rules

1. **Canonical JSON Encoding:**
   `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")`
   Matches `backend/app/term1/idempotency.py::canonical_public` identically.
2. **Snapshot Integrity Check:** Before spawning the AI worker (and again inside C3/C4 doctor review read checks), the service recomputes `sha256(canonical(snapshot_json))` and verifies equality with `assessment.snapshot_sha256` and `assessment.panel_contract_sha256 == DA_A2_RESTING_PANEL.contract_sha256`.
3. **Document Integrity Check:** Before OCR extraction, assessment binding, or private file download (`DOC4`/`DOC8`), the service recomputes `sha256` of the file bytes on disk and verifies equality with `medical_document.content_sha256` (and `assessment_document.document_sha256_at_bind` when bound). Any mismatch fails closed (`500 internal_error` or `409 document_integrity_mismatch` + `WORKFLOW_AUDIT_EVENT`).
