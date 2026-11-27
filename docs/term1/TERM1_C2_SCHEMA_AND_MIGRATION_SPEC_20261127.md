# CardioAssist-AI Term 1 — C2 Relational Schema, Invariants, and Additive Migration Spec

**Date:** 2026-11-27 (UTC / Africa/Cairo) — **Revision 3**
**Status:** `PROPOSED — NOT APPROVED, NOT IMPLEMENTED`
**Migration Base:** `20261126_06` (`backend/migrations/versions/20261126_06_pepper_binding.py`)
**Scope:** C2 Clinical Intake, C0 Immutable Versioned Health Profile & Separate Assessment Snapshot, C0 §7.3 Lease/Fencing Inference Persistence (`20261128_07`), and Bounded Document/OCR Intake (`20261128_08`); C3 `DOC9` boundary (`20261129_09`) documented without C2 DDL creep.

---

## 1. Compatibility Rules With C1 & `Database.verify_schema()`

1. **Zero Modification to `01`–`06`:** `20261017_01` through `20261126_06` remain byte-for-byte unchanged.
2. **Exact ORM ↔ Migration Parity & Trigger Verification:** `backend/app/storage/database.py::Database.verify_schema()` runs Alembic `compare_metadata(..., opts={"compare_type": True})` plus explicit primary-key inspection, `PRAGMA foreign_keys=ON`, `PRAGMA integrity_check`, and `PRAGMA foreign_key_check` on every startup. Every column length, nullability, PK, FK (`ondelete="RESTRICT"`), CHECK constraint, and index in the C2 SQLAlchemy models MUST match migrations `07` and `08` identically. **Additionally**, because Alembic `compare_metadata()` does not inspect SQLite triggers, `Database.verify_schema()` MUST query `sqlite_master WHERE type='trigger'` at startup and verify exact presence and normalized SQL definitions for every C2 trigger (`tr_health_profile_*`, `tr_snapshot_*`, `tr_assessment_*`, `tr_attempt_*`, `tr_result_*`, `tr_extraction_event_*`), failing closed on missing or modified triggers.
3. **RB-C1 Rollback Policy & Revision-Scoped Downgrade Guards:** Both `20261128_07` and `20261128_08` implement the exact `RB-C1` downgrade guard from `20261126_06_pepper_binding.py` **before** any DDL (`DROP TRIGGER` / `DROP TABLE`):
   - Refuse `as_sql=True` offline downgrade (`RuntimeError`).
   - `20261128_08` downgrade queries C1 (16 tables) + `07` (5 tables) + `08` (`medical_document`, `document_extraction`, `extraction_field`, `extraction_event`, `assessment_document`); if any row exists, raise `RuntimeError`.
   - `20261128_07` downgrade queries **only** tables present at revision `07` (C1 16 tables + `health_profile`, `assessment_snapshot`, `assessment`, `inference_attempt`, `inference_result`) — **never** `08` tables (which are already dropped before `07.downgrade()` runs!). On an empty database, `06 -> 07 -> 08 -> 07 -> 06 -> 07 -> 08` succeeds cleanly.
4. **No Global `patient.doctor_id`:** Consistent with `R-01`/`O-04` and C1, `health_profile`, `assessment_snapshot`, `assessment`, and `medical_document` never store a global `doctor_id`. Doctor visibility derives exclusively from `assessment.assignment_id -> doctor_patient_assignment` (where `revoked_at IS NULL`).
5. **Audit Table Extension (`workflow_audit_event`):** In C1 (`20261126_02`), `workflow_audit_event` enforces a CHECK constraint only on `outcome` (`ck_workflow_audit_outcome`), **not** on `event_type` or `subject_type` (those are enforced in `backend/app/term1/constants.py` and Python code). Thus C2 extends `constants.py` additively with C2/Document event types and subject types without altering `workflow_audit_event` DDL.

---

## 2. Entity-Relationship Overview (C1 → C2 → C3 Boundary)

```
C1 (Frozen, 01-06)
├── patient_profile (patient_id)
│     ├── 1:N ──> health_profile (health_profile_id; C0 superseded_at lifecycle;
│     │              DRAFT / COMPLETE / SUPERSEDED; <=1 active WHERE superseded_at IS NULL)
│     ├── 1:N ──> medical_document (document_id; PENDING_SCAN -> STORED / UPLOAD_FAILED) [08]
│     │              ├── 1:N ──> document_extraction (extraction_id, extraction_version) [08]
│     │              │              └── 1:N ──> extraction_field (field_record_id) [08]
│     │              └── 1:N ──> extraction_event (event_id, append-only) [08]
│     ├── 1:N ──> assessment_snapshot (snapshot_id, composite FK -> health_profile) [07]
│     └── 1:N ──> assessment (assessment_id, composite FK -> assessment_snapshot & health_profile,
│                    │        assignment_id, consent_id, reason_code, review_state, review_version) [07]
│                    ├── self FK (reassessment_of_id -> assessment.assessment_id) [07]
│                    ├── 1:N ──> assessment_document (binding_id; composite FKs -> assessment,
│                    │              medical_document, document_extraction) [08]
│                    ├── 1:N ──> inference_attempt (attempt_id; <=1 INFERENCE_RUNNING) [07]
│                    ├── 1:N ──> inference_result (result_id, composite FKs -> assessment & attempt) [07]
│                    ├── 0..1 ─> active_attempt_id (trigger-enforced -> inference_attempt) [07]
│                    └── 0..1 ─> current_result_id (trigger-enforced -> inference_result) [07]
└── C3 (20261129_09_c3_clinical_workflow, per P-25):
      └── document_acknowledgement (acknowledgement_id, non-null binding_id -> assessment_document;
                                    UNIQUE(assignment_id, assessment_id, binding_id))
```

---

## 3. Migration `20261128_07_c2_clinical_intake_inference.py`

**`down_revision = "20261126_06"`**

### 3.1 `health_profile` (C0 §5.1 / §7.1 Immutable Versioned Rows with `superseded_at`)

`health_profile` uses the original C0 `superseded_at` lifecycle metadata (**no** forward `superseded_by_id` FK, avoiding circular/partial-unique ordering deadlocks). Whenever `H1b` (`PATCH /v1/me/health-profile`) updates a patient's profile inside `BEGIN IMMEDIATE`:
1. If an active row exists (`superseded_at IS NULL`), `UPDATE health_profile SET status = 'SUPERSEDED', superseded_at = :now WHERE health_profile_id = :old_id AND superseded_at IS NULL`.
2. Immediately `INSERT INTO health_profile (...)` with `version_number = old_version + 1`, `status = 'COMPLETE'|'DRAFT'`, `superseded_at = NULL`.
3. If step 2 fails for any reason, the transaction rolls back atomically — leaving the original active row intact and guaranteeing **at most one active profile row** at all times.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `health_profile_id` | `String(36)` | PK | Server-generated UUIDv4 |
| `patient_id` | `String(36)` | `FK(patient_profile.patient_id, RESTRICT)`, `NOT NULL` | Owner patient |
| `version_number` | `Integer` | `NOT NULL`, `CheckConstraint("version_number >= 1")` | Monotonic per patient (`1, 2, ...`) |
| `status` | `String(24)` | `NOT NULL` | `'DRAFT'`, `'COMPLETE'`, `'SUPERSEDED'` (`COMPLETE` iff mandatory `age`, `sex`, `cp` present) |
| `superseded_at` | `String(32)` | `NULL` | C0 lifecycle timestamp; `NULL` when active, non-null UTC ISO-8601 when `SUPERSEDED` |
| `panel_id` | `String(64)` | `NOT NULL` | `'da_a2_resting_v1'` |
| `panel_version` | `String(16)` | `NOT NULL` | `'1.0.0'` |
| `schema_version` | `String(32)` | `NOT NULL` | `'term1.c2.profile/v1'` |
| `fields_json` | `JSON` | `NOT NULL` | Canonical `{inputs, units, missing_reasons}` validated against `DA_A2_RESTING_PANEL` |
| `provenance_json` | `JSON` | `NOT NULL` | Server-assigned manual-only origin (`source_contract_version`, `source_kind='synthetic_demo_patient_manual'`) |
| `profile_sha256` | `String(64)` | `NOT NULL` | Canonical SHA-256 of `{panel_id, panel_version, schema_version, fields_json, provenance_json}` |
| `actor_user_id` | `String(36)` | `FK(user_account.user_id, RESTRICT)`, `NOT NULL` | Actor who created this version |
| `created_at` | `String(32)` | `NOT NULL` | Server UTC ISO-8601 |

**Constraints, Partial Unique Index, & Immutability Triggers on `health_profile`:**
- `UniqueConstraint("patient_id", "version_number", name="ux_health_profile_patient_version")`
- `UniqueConstraint("health_profile_id", "patient_id", name="ux_health_profile_id_patient")` (for composite same-patient FKs)
- `Index("ux_health_profile_one_active", "patient_id", unique=True, sqlite_where=text("superseded_at IS NULL"))`
- `CheckConstraint("status IN ('DRAFT','COMPLETE','SUPERSEDED')", name="ck_health_profile_status")`
- `CheckConstraint("(status = 'SUPERSEDED' AND superseded_at IS NOT NULL) OR (status IN ('DRAFT','COMPLETE') AND superseded_at IS NULL)", name="ck_health_profile_supersession")`
- **`tr_health_profile_immutable_update` (`BEFORE UPDATE ON health_profile`):** Rejects any `UPDATE` if `OLD.superseded_at IS NOT NULL`, OR if any content/identity column (`health_profile_id`, `patient_id`, `version_number`, `panel_id`, `panel_version`, `schema_version`, `fields_json`, `provenance_json`, `profile_sha256`, `actor_user_id`, `created_at`) changes, OR if `NEW.status != 'SUPERSEDED'` or `NEW.superseded_at IS NULL`. Only the lifecycle transition `active -> SUPERSEDED` is permitted.
- **`tr_health_profile_no_delete` (`BEFORE DELETE ON health_profile`):** `RAISE(ABORT, 'health_profile_delete_forbidden')`.

### 3.2 `assessment_snapshot` (Separate Immutable Canonical Envelope per C0 §7.1–§7.2)

Created atomically before `assessment` inside `S1` (`POST /v1/assessments`). Protected by `tr_snapshot_no_update` and `tr_snapshot_no_delete` (`BEFORE UPDATE` / `BEFORE DELETE` -> `RAISE(ABORT, ...)`).

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `snapshot_id` | `String(36)` | PK | Server-generated UUIDv4 |
| `patient_id` | `String(36)` | `FK(patient_profile.patient_id, RESTRICT)`, `NOT NULL` | Owner patient |
| `health_profile_id` | `String(36)` | `NOT NULL` | Composite FK `(health_profile_id, patient_id) -> health_profile(health_profile_id, patient_id)` (`RESTRICT`) |
| `panel_id` | `String(64)` | `NOT NULL` | `'da_a2_resting_v1'` |
| `panel_version` | `String(16)` | `NOT NULL` | `'1.0.0'` |
| `panel_contract_sha256` | `String(64)` | `NOT NULL` | `'c18ad4cd2cf08f6fefb2e340573760da7000bc1d8eb4ad38783b873c018e57b8'` |
| `schema_version` | `String(32)` | `NOT NULL` | `'term1.c2.snapshot/v1'` |
| `schema_sha256` | `String(64)` | `NOT NULL` | SHA-256 of canonical `term1.c2.snapshot/v1` schema definition |
| `source_contract_version` | `String(32)` | `NOT NULL` | `'term1.c2.intake/v1'` |
| `source_kind` | `String(48)` | `NOT NULL` | Closed server-assigned enum: `'synthetic_demo_patient_manual'`, `'synthetic_demo_ocr_confirmed'` |
| `snapshot_json` | `JSON` | `NOT NULL` | **Single canonical envelope** containing: `schema_version`, `schema_sha256`, `panel` (`panel_id`, `panel_version`, `panel_contract_sha256`), `inputs`, `units`, `missing_reasons`, `provenance` (`source_contract_version`, `source_kind`, `health_profile_id`, `health_profile_sha256`, `provenance_fields`, `confirmed_values_sha256`), and sorted `attached_documents` (`binding_id`, `document_id`, `attachment_role`, `extraction_id`, `extraction_version`, `document_sha256_at_bind`, `extraction_confirmed_at`, `confirmed_values_sha256`) |
| `snapshot_sha256` | `String(64)` | `NOT NULL` | SHA-256 of canonical UTF-8 `snapshot_json` (`sort_keys=True, separators=(",",":"), allow_nan=False`) |
| `created_at` | `String(32)` | `NOT NULL` | Server UTC ISO-8601 |

**Constraints:** `UniqueConstraint("snapshot_id", "patient_id", name="ux_snapshot_id_patient")`, `CheckConstraint("source_kind IN ('synthetic_demo_patient_manual','synthetic_demo_ocr_confirmed')", name="ck_snapshot_source_kind")`.

### 3.3 `assessment`

Authoritative submission record + C0 §7.1–§7.3 state + `reason_code` + generation/lease/result/review CAS pointers.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `assessment_id` | `String(36)` | PK | Server-generated UUIDv4 |
| `patient_id` | `String(36)` | `FK(patient_profile.patient_id, RESTRICT)`, `NOT NULL` | Submitting patient |
| `health_profile_id` | `String(36)` | `NOT NULL` | Composite FK `(health_profile_id, patient_id) -> health_profile(health_profile_id, patient_id)` |
| `snapshot_id` | `String(36)` | `NOT NULL`, `UNIQUE` | Composite FK `(snapshot_id, patient_id) -> assessment_snapshot(snapshot_id, patient_id)` |
| `assignment_id` | `String(36)` | `FK(doctor_patient_assignment.assignment_id, RESTRICT)`, `NOT NULL` | Selected active assignment (`O-04`/`P-12`); same-patient verified by `tr_assessment_scope_insert` |
| `consent_id` | `String(36)` | `FK(consent_record.consent_id, RESTRICT)`, `NOT NULL` | Active `synthetic_demo` consent at creation; same-patient verified by `tr_assessment_scope_insert` |
| `reassessment_of_id` | `String(36)` | `FK(assessment.assessment_id, RESTRICT)`, `NULL` | `P-15` immutable linkage; same `(patient_id, assignment_id)` verified by `tr_assessment_scope_insert` |
| `reassessment_reason` | `String(128)` | `NULL` | Required iff `reassessment_of_id IS NOT NULL` |
| `panel_id` | `String(64)` | `NOT NULL` | `'da_a2_resting_v1'` |
| `panel_version` | `String(16)` | `NOT NULL` | `'1.0.0'` |
| `source_contract_version` | `String(32)` | `NOT NULL` | `'term1.c2.intake/v1'` |
| `source_kind` | `String(48)` | `NOT NULL` | `'synthetic_demo_patient_manual'` or `'synthetic_demo_ocr_confirmed'` |
| `stage_complete` | `Boolean` | `NOT NULL` | `True` iff all 5 resting fields present; `False` if optional `trestbps`/`restecg` missing |
| `status` | `String(36)` | `NOT NULL` | Closed C0 §7.1–§7.3 enum |
| `reason_code` | `String(64)` | `NULL` | Closed terminal non-success reason (`'real_ai_not_authorized'`, `'authorization_withdrawn'`, `'lease_expired'`, `'optional_panel_field_missing'`, `'worker_error'`, `'malformed_worker_response'`, `'artifact_integrity_failed'`) |
| `active_attempt_id` | `String(36)` | `NULL`, `UNIQUE` | Trigger-enforced pointer to active `INFERENCE_RUNNING` `inference_attempt` |
| `current_generation` | `Integer` | `NOT NULL` | Starts at `0`; incremented **once** per recovery/retry |
| `current_result_id` | `String(36)` | `NULL`, `UNIQUE` | Trigger-enforced pointer to published `inference_result.result_id` |
| `review_state` | `String(32)` | `NOT NULL` | C3 CAS review state: `'NOT_REVIEWED'`, `'ACCEPTED'`, `'REJECTED'`, `'REASSESSMENT_REQUESTED'` |
| `review_version` | `Integer` | `NOT NULL` | Starts at `0`; incremented atomically on C3 review CAS |
| `created_at` | `String(32)` | `NOT NULL` | Server UTC ISO-8601 |
| `updated_at` | `String(32)` | `NOT NULL` | Server UTC ISO-8601 |

**Closed `assessment.status` & `reason_code` Constraints:**
- `status IN ('DRAFT','INPUT_VALIDATED','INFERENCE_RUNNING','INFERENCE_SUCCEEDED','PENDING_REVIEW','INFERENCE_ABSTAINED','INFERENCE_UNAVAILABLE','INFERENCE_ERROR')`
- `((status IN ('INFERENCE_ABSTAINED','INFERENCE_UNAVAILABLE','INFERENCE_ERROR') AND reason_code IS NOT NULL) OR (status NOT IN ('INFERENCE_ABSTAINED','INFERENCE_UNAVAILABLE','INFERENCE_ERROR') AND reason_code IS NULL))`
- `((status = 'INFERENCE_RUNNING' AND active_attempt_id IS NOT NULL AND current_result_id IS NULL) OR (status IN ('INFERENCE_SUCCEEDED','PENDING_REVIEW') AND active_attempt_id IS NULL AND current_result_id IS NOT NULL) OR (status IN ('DRAFT','INPUT_VALIDATED','INFERENCE_ABSTAINED','INFERENCE_UNAVAILABLE','INFERENCE_ERROR') AND active_attempt_id IS NULL AND current_result_id IS NULL))`
- `UniqueConstraint("assessment_id", "assignment_id", name="ux_assessment_id_assignment")`, `UniqueConstraint("assessment_id", "patient_id", name="ux_assessment_id_patient")`, `UniqueConstraint("assessment_id", "snapshot_id", name="ux_assessment_id_snapshot")`.

**Complete Trigger Set & Atomic Transaction Ordering (`R2-02`):**
Because SQLite rejects `use_alter=True` cyclic FKs cleanly during `ALTER TABLE` / `compare_metadata`, migration `20261128_07` creates (and `Database.verify_schema()` inspects on startup):
1. `tr_assessment_scope_insert` (`BEFORE INSERT ON assessment`): verifies `assignment_id` belongs to `NEW.patient_id`, `consent_id` belongs to `NEW.patient_id`, and `reassessment_of_id` (when non-null) belongs to `(NEW.patient_id, NEW.assignment_id)`.
2. `tr_assessment_pointer_insert` (`BEFORE INSERT ON assessment`) and `tr_assessment_pointer_update` (`BEFORE UPDATE ON assessment`, firing on **every** `UPDATE`, not column-filtered):
   - Blocks mutation of `assessment_id`, `patient_id`, `health_profile_id`, `snapshot_id`, `assignment_id`, `consent_id`.
   - Blocks `NEW.current_generation < OLD.current_generation`.
   - When `NEW.active_attempt_id IS NOT NULL`, requires `EXISTS (SELECT 1 FROM inference_attempt a WHERE a.attempt_id = NEW.active_attempt_id AND a.assessment_id = NEW.assessment_id AND a.generation = NEW.current_generation AND a.state = 'INFERENCE_RUNNING')`.
   - When `NEW.current_result_id IS NOT NULL`, requires `EXISTS (SELECT 1 FROM inference_result r WHERE r.result_id = NEW.current_result_id AND r.assessment_id = NEW.assessment_id AND r.snapshot_id = NEW.snapshot_id)`.
3. `tr_assessment_no_delete` (`BEFORE DELETE ON assessment`): `RAISE(ABORT, 'assessment_delete_forbidden')`.
4. `tr_attempt_transition_guard` (`BEFORE UPDATE ON inference_attempt`) and `tr_attempt_no_delete`:
   - Forbids updating any terminal attempt (`OLD.state != 'INFERENCE_RUNNING'`).
   - Forbids mutating `attempt_id`, `assessment_id`, `generation`, `attempt_idempotency_hash`, `worker_id`, `fence_token`.
   - Forbids moving `state` out of `'INFERENCE_RUNNING'` while `EXISTS (SELECT 1 FROM assessment s WHERE s.active_attempt_id = OLD.attempt_id)`.
5. `tr_result_no_update` and `tr_result_no_delete` (`BEFORE UPDATE` / `BEFORE DELETE ON inference_result`): enforces strict append-only immutability.

**Mandatory SQL Write Order (`BEGIN IMMEDIATE`):**
- **Dispatch (`INPUT_VALIDATED -> INFERENCE_RUNNING`):** (1) `INSERT INTO inference_attempt (state='INFERENCE_RUNNING', generation=N)` -> (2) `UPDATE assessment SET status='INFERENCE_RUNNING', active_attempt_id=:attempt_id`.
- **Terminal Completion / Recovery (`INFERENCE_RUNNING -> terminal`):** (1) If `INFERENCE_SUCCEEDED`, `INSERT INTO inference_result` first -> (2) `UPDATE assessment SET status=:terminal, reason_code=:reason, active_attempt_id=NULL, current_result_id=:res_or_null, current_generation=:next_gen` -> (3) `UPDATE inference_attempt SET state=:terminal_state, reason_code=:reason, completed_at=:now`. Clearing `assessment.active_attempt_id` before transitioning `inference_attempt` satisfies both `tr_assessment_pointer_update` and `tr_attempt_transition_guard` atomically.

### 3.4 `inference_attempt` (Lease, Fencing, Idempotency & All Terminal Paths per C0 §7.3)

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `attempt_id` | `String(36)` | PK | UUIDv4 |
| `assessment_id` | `String(36)` | `FK(assessment.assessment_id, RESTRICT)`, `NOT NULL` | Target assessment |
| `generation` | `Integer` | `NOT NULL` | Equals `assessment.current_generation` when leased |
| `attempt_idempotency_hash` | `String(64)` | `NOT NULL` | SHA-256 over `(assessment_id, snapshot_sha256, generation, dispatch_kind)` |
| `worker_id` | `String(64)` | `NOT NULL` | Local worker instance ID (`'disabled_stub'` pre-`A3`) |
| `fence_token` | `String(64)` | `NOT NULL` | 64-hex CSPRNG token bound to `(attempt_id, assessment_id, generation)` |
| `state` | `String(36)` | `NOT NULL` | `'INFERENCE_RUNNING'`, `'INFERENCE_SUCCEEDED'`, `'INFERENCE_ABSTAINED'`, `'INFERENCE_UNAVAILABLE'`, `'INFERENCE_ERROR'` |
| `reason_code` | `String(64)` | `NULL` | Closed reason code |
| `leased_at` | `String(32)` | `NOT NULL` | UTC timestamp |
| `lease_until` | `String(32)` | `NOT NULL` | `leased_at + 300s` (`P-16`) |
| `completed_at` | `String(32)` | `NULL` | UTC timestamp when terminal |

**Constraints & All Outcome Paths (`R2-02`):**
- `UniqueConstraint("assessment_id", "generation", name="ux_inference_attempt_assessment_gen")`
- `UniqueConstraint("assessment_id", "attempt_idempotency_hash", name="ux_inference_attempt_idempotency")`
- `UniqueConstraint("assessment_id", "attempt_id", "generation", name="ux_inference_attempt_id_gen_pair")`
- `Index("ux_inference_attempt_one_active", "assessment_id", unique=True, sqlite_where=text("state = 'INFERENCE_RUNNING'"))`
- **All CAS-validated outcome transitions (inside `BEGIN IMMEDIATE`):**
  1. **Common Fence Check (first):** `attempt_id`, `assessment_id`, `assessment.active_attempt_id == attempt_id`, `attempt.generation == assessment.current_generation`, `attempt.state == 'INFERENCE_RUNNING'`, `assessment.status == 'INFERENCE_RUNNING'`, `attempt.worker_id`, `attempt.fence_token`, and strictly `attempt.lease_until > now_iso`. Any mismatch fails (`409 stale_attempt_fenced`) with zero DB writes.
  2. **Mid-flight revocation (`INFERENCE_UNAVAILABLE`):** If assignment (`revoked_at IS NOT NULL`) or referenced `consent_id` (`revoked_at IS NOT NULL`) or `A3` authorization was withdrawn, transition `assessment` & `attempt` to `INFERENCE_UNAVAILABLE` (`reason_code = 'authorization_withdrawn'`), clear `active_attempt_id = NULL`, `current_result_id = NULL`, zero `inference_result` rows.
  3. **Optional resting-field abstention (`INFERENCE_ABSTAINED`):** When `DA_A2_RESTING_PANEL` / `ED-DA-A2-01` abstains (e.g., missing optional `trestbps`/`restecg` under abstention policy), transition `assessment` & `attempt` to `INFERENCE_ABSTAINED` (`reason_code = 'optional_panel_field_missing'`), `current_result_id = NULL`.
  4. **Worker/malformed-response/digest error (`INFERENCE_ERROR`):** If worker times out, returns malformed JSON, fails `result_sha256`/sibling-digest/echo verification, or reports runtime error, transition `assessment` & `attempt` to `INFERENCE_ERROR` (`reason_code = 'malformed_worker_response' | 'artifact_integrity_failed' | 'worker_error'`), `current_result_id = NULL`, zero `inference_result` rows.
  5. **Authorized success (`INFERENCE_SUCCEEDED -> PENDING_REVIEW`):** Insert immutable `inference_result`, clear `active_attempt_id = NULL`, set `current_result_id = result.result_id`, set `assessment.status = 'PENDING_REVIEW'`, mark `attempt.state = 'INFERENCE_SUCCEEDED'`.
  6. **Lease expiry recovery (`<= now()`):** Scans `state = 'INFERENCE_RUNNING' AND lease_until <= clock.now_iso()`, sets `assessment.status = 'INFERENCE_ERROR'`, `reason_code = 'lease_expired'`, `active_attempt_id = NULL`, increments `current_generation` **once**, and marks `attempt.state = 'INFERENCE_ERROR'`.

### 3.5 `inference_result` (Append-Only Immutable Result Record with Full Scientific & Binding Digest)

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `result_id` | `String(36)` | PK | UUIDv4 |
| `assessment_id` | `String(36)` | `NOT NULL` | Composite FK `(assessment_id, snapshot_id) -> assessment(assessment_id, snapshot_id)` (`RESTRICT`) |
| `attempt_id` | `String(36)` | `NOT NULL`, `UNIQUE` | Composite FK `(assessment_id, attempt_id, generation) -> inference_attempt(assessment_id, attempt_id, generation)` (`RESTRICT`) |
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
| `result_sha256` | `String(64)` | `NOT NULL` | Canonical SHA-256 over **all** stored binding and scientific fields (see §5.3) |
| `published_at` | `String(32)` | `NOT NULL` | Server UTC timestamp |

`UniqueConstraint("assessment_id", "snapshot_id", "result_id", name="ux_inference_result_ass_snap_res")` enables the SQLite trigger integrity check on `assessment.current_result_id`.

---

## 4. Migration `20261128_08_c2_documents_ocr.py` (+ C3 `DOC9` Boundary)

**`down_revision = "20261128_07"`**

### 4.1 `medical_document`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `document_id` | `String(36)` | PK | UUIDv4 |
| `patient_id` | `String(36)` | `FK(patient_profile.patient_id, RESTRICT)`, `NOT NULL` | Owner patient |
| `uploaded_by_user_id` | `String(36)` | `FK(user_account.user_id, RESTRICT)`, `NOT NULL` | Uploader actor |
| `document_kind` | `String(48)` | `NOT NULL` | `'RESTING_CARDIAC_DEMO_REPORT'` or `'UNRELATED_LAB_DEMO_REPORT'` |
| `fixture_template_id` | `String(64)` | `NOT NULL` | Server-verified allowlist template ID (`'CAI-DEMO-RESTING-CARDIAC-REPORT-V1'`, `'CAI-DEMO-UNRELATED-LABS-V1'`) |
| `fixture_file_sha256` | `String(64)` | `NOT NULL` | Actual uploaded file SHA-256 matched against server-owned fixture manifest (`sha256 -> template_id, document_kind`) **before** storage/parser |
| `original_filename_sanitized` | `String(128)` | `NOT NULL` | Basename sanitized for display only; never used in storage path |
| `declared_media_type` | `String(64)` | `NOT NULL` | Verified against magic bytes: `'application/pdf'`, `'image/png'`, `'image/jpeg'` |
| `byte_size` | `Integer` | `NOT NULL` | `0 <= byte_size <= 5242880` (`<= 5 MiB`; reserved bytes count against total patient quota including `PENDING_SCAN`/`STORED`/`SUPERSEDED`/unreclaimed `UPLOAD_FAILED`) |
| `page_count` | `Integer` | `NOT NULL` | `0 <= page_count <= 3` (`>= 1` when `'STORED'`) |
| `content_sha256` | `String(64)` | `NULL` | Non-null SHA-256 of exact stored bytes once `'STORED'` (equals `fixture_file_sha256`) |
| `storage_key` | `String(160)` | `NOT NULL`, `UNIQUE` | Server-generated `<patient_id>/<document_id>.bin` |
| `upload_status` | `String(24)` | `NOT NULL` | `'PENDING_SCAN'`, `'STORED'`, `'UPLOAD_FAILED'`, `'SUPERSEDED'` |
| `created_at` | `String(32)` | `NOT NULL` | UTC timestamp |

`UniqueConstraint("document_id", "patient_id", name="ux_medical_document_id_patient")` enables same-patient composite FK checks in `assessment_document`.

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
  - `is_confirmed`: `Boolean`, `NOT NULL` (starts `False`; becomes `True` only on `DOC7`, permanently locking this version via `tr_extraction_confirmed_immutable`)
  - `confirmed_values_sha256`: `String(64)`, `NULL` (non-null canonical SHA-256 of `{confirmed_inputs, units, missing_reasons, field_provenance}` once `is_confirmed = True`)
  - `extracted_text_bytes`: `Integer`, `NOT NULL` (`0 <= extracted_text_bytes <= 1048576` — `1 MiB` aggregate limit)
  - `raw_text_sha256`: `String(64)`, `NULL`
  - `raw_text_excerpt_json`: `JSON`, `NOT NULL` (bounded line/region snippet metadata, never logged)
  - `created_at`: `String(32)`, `NOT NULL`
  - `confirmed_at`: `String(32)`, `NULL`
  - `UniqueConstraint("document_id", "extraction_version", name="ux_document_extraction_version")`
  - `UniqueConstraint("extraction_id", "document_id", "extraction_version", name="ux_extraction_id_doc_ver")`

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

Protected by `BEFORE UPDATE` / `BEFORE DELETE` immutability triggers (`tr_extraction_event_no_update`, `tr_extraction_event_no_delete`).
- `event_id`: `String(36)`, PK
- `document_id`: `String(36)`, `FK(medical_document.document_id, RESTRICT)`, `NOT NULL`
- `extraction_id`: `String(36)`, `FK(document_extraction.extraction_id, RESTRICT)`, `NULL`
- `extraction_version`: `Integer`, `NULL`
- `event_type`: `String(32)`, `NOT NULL` (`'UPLOADED'`, `'EXTRACTED'`, `'EXTRACTION_FAILED'`, `'PATIENT_EDITED'`, `'PATIENT_CONFIRMED'`, `'EDITED_AND_CONFIRMED'`, `'DOCTOR_ACKNOWLEDGED'`)
- `actor_user_id`: `String(36)`, `FK(user_account.user_id, RESTRICT)`, `NOT NULL`
- `actor_role`: `String(16)`, `NOT NULL`
- `field_diffs_json`: `JSON`, `NOT NULL`
- `recorded_at`: `String(32)`, `NOT NULL`

### 4.4 `assessment_document` (Immutable C2 Binding) & C3 `document_acknowledgement` Boundary (`R2-01`)

- **`assessment_document`** (created in `20261128_08`; protected by `BEFORE UPDATE` / `BEFORE DELETE` triggers):
  - `binding_id`: `String(36)`, PK
  - `assessment_id`: `String(36)`, `NOT NULL`
  - `patient_id`: `String(36)`, `NOT NULL` (Composite FK `(assessment_id, patient_id) -> assessment(assessment_id, patient_id)`)
  - `document_id`: `String(36)`, `NOT NULL` (Composite FK `(document_id, patient_id) -> medical_document(document_id, patient_id)`)
  - `extraction_id`: `String(36)`, `NULL`
  - `extraction_version`: `Integer`, `NULL` (Composite FK `(extraction_id, document_id, extraction_version) -> document_extraction(extraction_id, document_id, extraction_version)`)
  - `document_sha256_at_bind`: `String(64)`, `NOT NULL`
  - `attachment_role`: `String(32)`, `NOT NULL` (`'SUPPORTING_REPORT'`, `'OCR_SOURCE_REPORT'`, `'UNRELATED_LAB_ATTACHMENT'`)
  - `created_at`: `String(32)`, `NOT NULL`
  - `CheckConstraint("(extraction_id IS NULL AND extraction_version IS NULL AND attachment_role != 'OCR_SOURCE_REPORT') OR (extraction_id IS NOT NULL AND extraction_version IS NOT NULL)", name="ck_assessment_document_extraction_pair")`
  - `UniqueConstraint("assessment_id", "document_id", name="ux_assessment_document_pair")`
  - `UniqueConstraint("assessment_id", "binding_id", name="ux_assessment_document_ass_binding")`
- **`document_acknowledgement` (`DOC9` — C3 Migration `20261129_09_c3_clinical_workflow` per `P-25`, NOT in C2 `08`):**
  To eliminate SQLite `NULL != NULL` duplicate bypasses on manual attachments (`extraction_id IS NULL`), `DOC9` keys uniqueness strictly on **non-null** `assessment_document.binding_id`:
  - `acknowledgement_id`: `String(36)`, PK
  - `doctor_user_id`: `String(36)`, `FK(user_account.user_id, RESTRICT)`, `NOT NULL`
  - `assignment_id`: `String(36)`, `NOT NULL` (Composite FK `(assessment_id, assignment_id) -> assessment(assessment_id, assignment_id)`)
  - `assessment_id`: `String(36)`, `NOT NULL`
  - `binding_id`: `String(36)`, `NOT NULL` (Composite FK `(assessment_id, binding_id) -> assessment_document(assessment_id, binding_id)`)
  - `acknowledged_at`: `String(32)`, `NOT NULL`
  - `UniqueConstraint("assignment_id", "assessment_id", "binding_id", name="ux_doc_ack_non_null_binding")` (guarantees duplicate acknowledgements fail with `IntegrityError` for **both** OCR-extracted and manual `NULL`-extraction attachments!)
  - `BEFORE INSERT` trigger `tr_doc_ack_doctor_scope` verifying `doctor_user_id` resolves to `doctor_patient_assignment.doctor_id` for `NEW.assignment_id`.

---

## 5. Canonical Hashing & Tamper-Detection Rules (`R2-02`)

1. **Canonical JSON Encoding:**
   `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")`
   Matches `backend/app/term1/idempotency.py::canonical_public` identically.
2. **Complete Snapshot Integrity Check (Publish & Read):**
   `assessment_snapshot.snapshot_sha256` binds **every** canonical envelope key: `schema_version`, `schema_sha256`, `panel` (`panel_id`, `panel_version`, `panel_contract_sha256`), `inputs`, `units`, `missing_reasons`, `provenance` (`source_contract_version`, `source_kind`, `health_profile_id`, `health_profile_sha256`, `provenance_fields`, `confirmed_values_sha256`), and sorted `attached_documents` (`binding_id`, `document_id`, `attachment_role`, `extraction_id`, `extraction_version`, `document_sha256_at_bind`, `extraction_confirmed_at`, `confirmed_values_sha256`). Verified before worker dispatch and on `S2`/C3 reads.
3. **Complete Result Integrity Check (Publish & Read):**
   `inference_result.result_sha256` is computed over canonical JSON containing **all** stored binding and scientific fields: `assessment_id`, `attempt_id`, `generation`, `snapshot_id`, `snapshot_sha256`, `schema_version`, `panel_id`, `panel_version`, `panel_contract_sha256`, `source_contract_version`, `source_kind`, `model_id`, `model_version`, `protocol_id`, `execution_profile`, `bundle_dir_name`, `manifest_sha256`, `source_sha256`, `model_joblib_sha256`, `preprocessing_json_sha256`, `calibration_json_sha256`, `shap_background_sha256`, `evaluation_summary_sha256`, `protocol_md_sha256`, `serving_eligibility`, `clinical_use_authorized`, `raw_model_score`, `raw_model_log_odds`, `calibrated_research_score`, `calibrated_log_odds`, `calibration_meta_json`, `shap_json`, `lime_status`, `lime_json`, `lime_meta_json`, `fold_dispersion_json`, and `limitations_json`. Verified inside completion CAS **before** committing `current_result_id` and re-verified on `S2` reads.
4. **TOCTOU-Free Document Integrity Check:**
   During upload (`DOC1`), OCR extraction (`DOC5`), assessment binding (`S1`), and buffered download (`DOC4`/`DOC8`), the service verifies `sha256(exact_bytes) == medical_document.content_sha256` (and `assessment_document.document_sha256_at_bind`) **before** publishing metadata or HTTP headers (`409 document_integrity_mismatch` + `WORKFLOW_AUDIT_EVENT`).
