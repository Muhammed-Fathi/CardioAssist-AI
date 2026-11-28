# CardioAssist-AI Term 1 — C2 Shared-Interface Reconciliation Checkpoint

**Date:** 2026-11-28 (UTC / Africa/Cairo)
**Status:** `IMPLEMENTATION_CONTRACT — binding shared interface for C2 Track 1 (core assessment infrastructure) and Track 2 (documents/OCR)`
**Authorization:** owner grant `AUTHORIZE-TERM1-C2-SAFE-SCOPE-V1`
([#7232372420](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/147#issuecomment-7232372420)) at exact merged baseline
`5c96a2b9d5438b6600cf5eebebb70294fdeeadad`, bootstrapped by the append-only
reviewer record `5e763b055c51bd77e42b140642ce49a4d2524386`.
**Governing sources:** merged PR #146 delivery amendment; merged PR #147 Revision 3
design (four accepted specifications); mandatory reviewer clarifications
[#7229164710](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/147#issuecomment-7229164710)
and
[#7229713779](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/147#issuecomment-7229713779);
post-merge verification
[#7232298149](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/147#issuecomment-7232298149);
`TERM1_C2_SCHEMA_AND_MIGRATION_SPEC_20261127.md` (schema),
`TERM1_C2_API_AND_OCR_CONTRACT_SPEC_20261127.md` (API),
`TERM1_C2_FINAL_INTEGRATION_DESIGN_AND_READINESS_20261127.md` (integration),
`TERM1_C2_AUTHORIZATION_TOKENS_AND_LOCAL_EVIDENCE_20261127.md` (tokens),
`TERM1_C0_ARCHITECTURE_AND_CONTRACTS.md`, `TERM1_C2_IMPLEMENTATION_DEPENDENCY_MAP.md`
Appendix A.

This checkpoint freezes the exact shared contracts that Track 1 and Track 2 must
both consume **before either creates dependent schema or code**. It resolves every
mandatory reviewer clarification against the accepted design and the existing C1
source. It is append-only documentation: it changes no migration, route, runtime
behaviour, gate, tolerance, fixture or research workflow. `A1`, `A2`, `A3`, `B`,
`RD-09-TERM1-EDU-DEMO-V1` and `EXC-TERM1-OCR-DEMO-V1` remain **PENDING**.

---

## 0. Workstream ownership (no concurrent edits to shared files)

| Owner | Files |
|---|---|
| **Track 1 (core integrator, this branch)** | `backend/migrations/versions/20261128_07_*.py`; `backend/app/term1/{models,constants,errors,openapi,api,panel,health_profile,assessments,inference_lifecycle,c2_authz,c2_api,triggers}.py`; `backend/app/storage/database.py`; `backend/app/main.py`; `shared/contracts/term1/{c2-paths-assessment.yaml,errors.yaml,errors.v1.json}`; `shared/contracts/term1/schemas/term1_health_profile_*.json`, `term1_assessment_*.json`, `term1_me_assessments_*.json`; `docs/term1/TERM1_C2_SHARED_INTERFACE_RECONCILIATION_20261128.md`; `tests/backend/c2/**`; inventory-test updates listed in §9 |
| **Track 2 (documents/OCR)** | `backend/migrations/versions/20261128_08_*.py`; new package `backend/app/term1/documents/**` (models, storage, services, routes); `shared/contracts/term1/c2-paths-documents.yaml` (new file — **never** `paths-*.yaml`); `shared/contracts/term1/schemas/term1_doc*.json`; project-generated fixture templates; `tests/backend/c2_documents/**`; the single `python-multipart==0.0.20` pin in `backend/requirements.txt` |

Track 2 must not edit any Track 1 file above; Track 1 will not edit any Track 2
file. All shared integration points below are consumed through the interfaces
frozen here. One logical C2 stage Draft PR targets `delivery/term1-prototype`;
neither track merges anything.

---

## 1. Exact persisted document and extraction enums (Track 2 vocabulary freeze)

Adopt the **persisted schema vocabulary everywhere** (reviewer clarification 2:
adopt the schema vocabulary consistently rather than the divergent API-spec
list; no projection mapping layer exists).

| Column / concept | Closed values (persisted = served) |
|---|---|
| `medical_document.document_kind` | `RESTING_CARDIAC_DEMO_REPORT`, `UNRELATED_LAB_DEMO_REPORT` |
| `medical_document.fixture_template_id` | `CAI-DEMO-RESTING-CARDIAC-REPORT-V1`, `CAI-DEMO-UNRELATED-LABS-V1` |
| `medical_document.declared_media_type` | `application/pdf`, `image/png`, `image/jpeg` (verified against magic bytes) |
| `medical_document.upload_status` | `PENDING_SCAN`, `STORED`, `UPLOAD_FAILED`, `SUPERSEDED` |
| `document_extraction.extraction_mode` | `PDF_TEXT`, `RASTER_OCR`, `FAILED` |
| `document_extraction.extraction_status` | `EXTRACTED_DRAFT`, `UNSUPPORTED_TEMPLATE`, `NEEDS_MANUAL_REVIEW`, `CONFIRMED_BY_PATIENT`, `FAILED` (the API-spec names `PARSED_COMPLETE`/`PARTIAL_REVIEW_REQUIRED`/`WORKER_FAILED` are **not** persisted and are not served) |
| `extraction_field.parse_status` | `PARSED`, `LOW_CONFIDENCE`, `CONFLICT_REVIEW_REQUIRED`, `INVALID_VALUE`, `MISSING`, `UNRELATED_IGNORED` |
| `extraction_field.field_provenance` | `OCR_EXTRACTED_UNCONFIRMED`, `OCR_EXTRACTED_PATIENT_CONFIRMED`, `PATIENT_ENTERED_FROM_OCR_DRAFT`, `UNRELATED_NON_MODEL_FIELD` |
| `assessment_document.attachment_role` | `SUPPORTING_REPORT`, `OCR_SOURCE_REPORT`, `UNRELATED_LAB_ATTACHMENT` |
| `extraction_event.event_type` | `UPLOADED`, `EXTRACTED`, `EXTRACTION_FAILED`, `PATIENT_EDITED`, `PATIENT_CONFIRMED`, `EDITED_AND_CONFIRMED`, `DOCTOR_ACKNOWLEDGED` |
| `source_kind` (profile-free, assessment/snapshot, server-assigned only) | `synthetic_demo_patient_manual`, `synthetic_demo_ocr_confirmed` |

All additions are recorded in `backend/app/term1/constants.py` by Track 1 in the
API commit (constants are a Track 1-owned shared file; Track 2 imports, never
edits).

## 2. Assessment-document binding identity (Track 2)

Frozen from schema spec §4.4; Track 2 creates the table in `20261128_08`:

- PK `binding_id` (UUIDv4, server-generated **before** snapshot construction so
  the canonical envelope can carry it).
- Composite FKs: `(assessment_id, patient_id) -> assessment(assessment_id,
  patient_id)`; `(document_id, patient_id) -> medical_document(document_id,
  patient_id)`; `(extraction_id, document_id, extraction_version) ->
  document_extraction(extraction_id, document_id, extraction_version)` — all
  `RESTRICT`.
- `document_sha256_at_bind` NOT NULL; `attachment_role` NOT NULL (enum above);
  `created_at` NOT NULL.
- `ck_assessment_document_extraction_pair`: `(extraction_id IS NULL AND
  extraction_version IS NULL AND attachment_role != 'OCR_SOURCE_REPORT') OR
  (extraction_id IS NOT NULL AND extraction_version IS NOT NULL)`.
- `ux_assessment_document_pair` on `(assessment_id, document_id)`;
  `ux_assessment_document_ass_binding` on `(assessment_id, binding_id)`.
- Immutability triggers `tr_assessment_document_no_update` /
  `tr_assessment_document_no_delete` (`BEFORE UPDATE`/`BEFORE DELETE` →
  `RAISE(ABORT, 'assessment_document_update_forbidden')` /
  `'assessment_document_delete_forbidden'`).

**S1 integration interface (Track 2 implements, Track 1 calls after Track 2
lands; Track 1 ships the fail-closed substitute meanwhile):**

```python
# backend/app/term1/documents/bindings.py   (Track 2-owned)
def resolve_assessment_attachments(
    session, *, patient_id: str, document_ids: list[str],
) -> list[dict]:
    """0..5 unique ids -> one resolved binding descriptor per document, each with a
    server-generated binding_id. Raises ApiError 404 document_not_found for an
    unknown id, wrong owner, or upload_status != 'STORED'; 409
    document_integrity_mismatch when content_sha256 != stored digest. Insertion
    order is document_id ascending (canonical)."""

def insert_assessment_document_bindings(
    session, *, assessment_id: str, patient_id: str, resolved: list[dict],
) -> None:
    """INSERT the assessment_document rows for an already-inserted assessment."""
```

Until `backend/app/term1/documents/` exists, Track 1's S1 rejects any non-empty
`attached_document_ids` with `404 document_not_found` (zero documents can exist
before migration 08; fail closed, no IDOR oracle). Max 5 unique ids and
uniqueness are enforced by the request schema (`maxItems: 5`,
`uniqueItems: true`).

## 3. Canonical snapshot schema and confirmed-value provenance

### 3.1 Profile digest (`health_profile.profile_sha256`)

`sha256(canonical({panel_id, panel_version, schema_version, fields_json,
provenance_json}))` where

- `fields_json = {"inputs": …, "units": …, "missing_reasons": …}` (as stored),
- `provenance_json = {"source_contract_version": "term1.c2.intake/v1",
  "source_kind": "synthetic_demo_patient_manual"}` (server-assigned; `H1b` is
  strictly manual).

Canonical JSON (frozen for the whole stage, identical to
`idempotency.canonical_public`): `json.dumps(obj, sort_keys=True,
separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")`.
Recomputed and verified before an assessment pins the profile; a mismatch fails
closed with `500 internal_error`.

### 3.2 Snapshot envelope (`assessment_snapshot.snapshot_json`)

Single canonical envelope; `snapshot_sha256 = sha256(canonical(snapshot_json))`.
Frozen top-level key set (resolved by merging schema spec §3.2 with reviewer
clarification 1, which requires explicit assessment/patient/assignment/consent
identities):

```
{
  "schema_version": "term1.c2.snapshot/v1",
  "schema_sha256": <sha256 of the canonical schema-definition document, §3.4>,
  "assessment_id":  <uuid>,   "patient_id": <uuid>,
  "assignment_id":  <uuid>,   "consent_id": <uuid>,
  "health_profile_id": <uuid>,
  "panel": {"panel_id": "da_a2_resting_v1", "panel_version": "1.0.0",
            "panel_contract_sha256": "c18ad4cd2cf08f6fefb2e340573760da7000bc1d8eb4ad38783b873c018e57b8"},
  "source_contract_version": "term1.c2.intake/v1",
  "source_kind": "synthetic_demo_patient_manual" | "synthetic_demo_ocr_confirmed",
  "inputs": {…}, "units": {…}, "missing_reasons": {…},
  "provenance": {
     "source_contract_version": "term1.c2.intake/v1",
     "source_kind": <same as top-level>,
     "health_profile_id": <uuid>,
     "health_profile_sha256": <profile digest, §3.1>,
     "provenance_fields": {<field>: "patient_manual" | "ocr_confirmed", …},
     "confirmed_values_sha256": <digest, §3.3>
  },
  "attached_documents": [ <binding, sorted by (document_id, binding_id)> ]
}
```

Each `attached_documents` entry (schema spec §3.2 list; `binding_id` inclusion is
mandated by clarification 1): `{"binding_id", "document_id", "attachment_role",
"extraction_id", "extraction_version", "document_sha256_at_bind",
"extraction_confirmed_at", "confirmed_values_sha256"}`. Under Track 1 the list
is always `[]`.

Frozen helper module: `backend/app/term1/assessments.py` exports
`canonical_bytes(obj)`, `snapshot_schema_definition()` (the canonical
schema-definition document) and `snapshot_schema_sha256()`; Track 2 imports them
and must not re-derive any digest formula.

### 3.3 Confirmed-value provenance

- `provenance.provenance_fields`: one key per panel field present (non-null) in
  `inputs`; value is `patient_manual` when `source_kind =
  synthetic_demo_patient_manual`, `ocr_confirmed` when `source_kind =
  synthetic_demo_ocr_confirmed`. Homogeneous per snapshot — OCR-derived values
  are never relabelled manual (no provenance laundering).
- `provenance.confirmed_values_sha256 = sha256(canonical({"inputs", "units",
  "missing_reasons", "provenance_fields"}))` — one formula for both modes.
  The extraction-level digest defined by DOC7
  (`sha256(canonical({confirmed_inputs, units, missing_reasons,
  field_provenance}))`) is a different document and stays on the
  `document_extraction` row, carried per binding inside `attached_documents`.

### 3.4 Snapshot schema digest

`schema_sha256 = sha256(canonical_bytes(snapshot_schema_definition()))` where
`snapshot_schema_definition()` returns the frozen nested key/type document for
`term1.c2.snapshot/v1` (key set of §3.2 with each value's shape, the two
`source_kind` values, and the `attachment_role` enum). The constant lives in
`backend/app/term1/assessments.py`; both tracks import it. The definition and
its digest are asserted by Track 1 tests.

### 3.5 `panel_input` vs pinned profile (resolved)

`S1.panel_input` is the authoritative snapshot content; the pinned
`health_profile_id` binds profile **identity and digest** as provenance.
Field-level equality between `panel_input` and the profile's `fields_json` is
**not** enforced: the accepted OCR mode sources inputs from confirmed extractions
while still pinning a profile, so equality cannot be an invariant. The
assessment↔snapshot profile binding itself *is* enforced: composite FKs plus
pre-checks guarantee `assessment.health_profile_id ==
snapshot.health_profile_id` and same patient (clarification 1; same patient
alone is insufficient).

## 4. Migration ordering and model registration

```
20261017_01 → 20261126_02 … _06 (byte-for-byte unchanged, RB-C1 preserved)
           → 20261128_07_c2_clinical_intake_inference   (Track 1)
           → 20261128_08_c2_documents_ocr               (Track 2)
           → 20261129_09_c3_clinical_workflow            (C3, out of scope)
```

- `20261128_07.down_revision = "20261126_06"`;
  `20261128_08.down_revision = "20261128_07"` (Track 2 must not rebase 07).
- **Model registration:** Track 1 adds the five C2 models to
  `backend/app/term1/models.py` and appends one guarded registration hook at the
  bottom of that file:

  ```python
  if importlib.util.find_spec("backend.app.term1.documents") is not None:
      from . import documents as _c2_document_models  # noqa: F401
  ```

  Track 2 creates `backend/app/term1/documents/{__init__,models,…}.py` and is
  registered by the hook automatically. Track 2 must **not** edit
  `backend/migrations/env.py`, `backend/app/storage/database.py`, or
  `backend/app/term1/models.py`.
- **Downgrade guards (RB-C1, exact message preserved):** `07.downgrade` refuses
  `as_sql=True`, then queries the C1 sixteen tables **plus** `health_profile`,
  `assessment_snapshot`, `assessment`, `inference_attempt`, `inference_result`
  (never the 08 tables, which are already dropped at that point) and raises
  `RuntimeError("C1 downgrade refused: persisted C1 state is present. …")` before
  any `DROP TRIGGER`/`DROP TABLE`. Empty databases must complete
  `06 → 07 → 08 → 07 → 06 → 07 → 08`; populated databases must refuse with the
  schema and rows untouched. `08.downgrade` additionally queries the five 08
  tables (Track 2's guard, same message family).
- **Startup trigger verification:** `Database.verify_schema()` (sqlite only)
  queries `sqlite_master WHERE type='trigger'` and fails closed unless every
  trigger in `backend/app/term1/triggers.py::C2_TRIGGER_DEFINITIONS` is present
  with matching normalized SQL
  (`triggers.normalize_trigger_sql`: whitespace collapsed to single spaces and
  one trailing `;` removed — `sqlite_master.sql` omits the statement-final
  semicolon). Track 1
  registers the twelve 07 triggers; at integration Track 1 appends Track 2's
  trigger definitions to that dict (Track 2 asserts its own trigger SQL directly
  in its tests). Missing or modified triggers refuse startup.
- **Frozen 07 trigger names:** `tr_health_profile_immutable_update`,
  `tr_health_profile_no_delete`, `tr_snapshot_no_update`,
  `tr_snapshot_no_delete`, `tr_assessment_scope_insert`,
  `tr_assessment_pointer_insert`, `tr_assessment_pointer_update`,
  `tr_assessment_no_delete`, `tr_attempt_transition_guard`,
  `tr_attempt_no_delete`, `tr_result_no_update`, `tr_result_no_delete`.
- **Clarification-1 trigger correction:** `tr_assessment_pointer_update` checks
  `NEW.current_result_id` against `inference_result` matching **assessment_id,
  snapshot_id and generation = NEW.current_generation** (the accepted §3.3 draft
  omitted the generation bind). Normal terminal completion leaves
  `current_generation` unchanged; only lease recovery increments it, so a
  published result always equals the assessment's current generation.
  `inference_result.attempt_id` additionally carries the composite FK
  `(assessment_id, attempt_id, generation) -> inference_attempt`, binding the
  exact successful attempt.

## 5. Error catalogue additions (closed; 26 additive C2 codes)

Track 1 adds **all 26** codes below to `errors.py::ERROR_CATALOGUE`,
`shared/contracts/term1/{errors.yaml,errors.v1.json}` and
`openapi.py::ERROR_CODES` in its API commit so Track 2 never edits those shared
files. The 37 C1 codes and messages stay byte-identical. Each code keeps exactly
one status.

| Status | Codes (message verbatim from API spec §5) |
|---|---|
| `403` | `admin_clinical_content_forbidden` · `consent_required` · `ocr_inference_not_authorized` |
| `404` | `health_profile_not_found` · `assessment_not_found` · `document_not_found` · `extraction_not_found` |
| `409` | `health_profile_superseded` · `document_not_confirmed` · `document_integrity_mismatch` · `document_limit_reached` · `extraction_already_confirmed` · `extraction_version_conflict` · `stale_attempt_fenced` |
| `413` | `payload_too_large` |
| `415` | `unsupported_media_type` |
| `422` | `active_pdf_content_rejected` · `health_profile_incomplete` · `invalid_document_content` · `invalid_panel_input` · `missing_mandatory_attachment` · `missing_reason_mismatch` · `prohibited_clinical_field` · `provenance_relabeling_forbidden` · `unsupported_template_for_intake` |
| `503` | `worker_unavailable` |

Track 1 raises: `admin_clinical_content_forbidden`, `consent_required`,
`ocr_inference_not_authorized`, `health_profile_not_found`,
`assessment_not_found`, `document_not_found` (fail-closed empty-attachment
substitute), `health_profile_superseded`, `stale_attempt_fenced`,
`health_profile_incomplete`, `invalid_panel_input`,
`missing_reason_mismatch`, `prohibited_clinical_field` — plus C1 codes
(`assignment_not_found`, `assignment_already_revoked`, `role_profile_mismatch`,
`concurrency_conflict`, `validation_failed`, idempotency family). The
document/OCR codes are catalogue-only until Track 2 lands.

## 6. API and OpenAPI composition boundaries

- **Composition source split (frozen):** C1 modules remain exactly the
  `shared/contracts/term1/paths-*.yaml` files (untouched; `C1_OPERATIONS`
  stays 20). C2 modules are `shared/contracts/term1/c2-paths-*.yaml`
  (Track 1: `c2-paths-assessment.yaml`; Track 2: `c2-paths-documents.yaml`).
  `openapi.py` loads the two globs separately into `C1_OPERATIONS` /
  `C2_OPERATIONS`; `SERVED_OPERATIONS = LEGACY + C1 + C2` (22 → 27 with Track 1,
  34 after Track 2 integration). The C1 closure/conformance suites iterate
  `C1_OPERATIONS` only and remain untouched by C2 operations.
- **Schemas:** operation request/response JSON Schemas live beside the C1 ones
  in `shared/contracts/term1/schemas/` with the frozen names:
  `term1_health_profile_response.schema.json` (H1a **and** H1b 200),
  `term1_health_profile_patch_request.schema.json`,
  `term1_assessment_create_request.schema.json`,
  `term1_assessment_create_response.schema.json`,
  `term1_assessment_get_response.schema.json` (S2 — one schema covering both
  role projections; role-specific key sets are asserted by tests),
  `term1_me_assessments_response.schema.json`. Bound explicitly via
  `request_schema:` / `response_schema:` in `c2-paths-assessment.yaml`;
  runtime request validation reuses `openapi.OP_REQUEST_SCHEMA`.
- **C2 operation ids / idempotency:** `H1a GET /v1/me/health-profile`
  (authenticated, not idempotent); `H1b PATCH /v1/me/health-profile`
  (idempotent, `target_ref="none"`); `S1 POST /v1/assessments` (idempotent,
  `target_ref="none"`, OQ-7/C1 creation pattern); `S2 GET
  /v1/assessments/{assessment_id}`; `S3 GET /v1/me/assessments` (not
  idempotent). All five declare `401, 403, 409 (role_profile_mismatch),
  500, 503` plus their operation-specific statuses, exactly per API spec §2.1.
- **Tags/stage:** C2 operations are served with tag `term1-c2` and
  `x-term1-stage: C2`. `shared/contracts/openapi.yaml` (legacy) stays
  byte-identical; the composed `/openapi.json` remains the single served
  document.
- **Route names:** no route path may contain `research`, `synth` (sole
  exception remains the C1 consent path), `facade`, `artifact` or `registry`.
  The five paths are `/v1/me/health-profile`, `/v1/assessments`,
  `/v1/assessments/{assessment_id}`, `/v1/me/assessments`.

## 7. Shared transaction and authorization interfaces

- **Transactions:** every C2 route runs inside `tx.write_transaction`
  (`BEGIN IMMEDIATE`) exactly like C1, including GETs (session touch), with the
  `run_idempotent` savepoint/failure-evidence pattern for H1b and S1.
- **Idempotency:** `run_idempotent` gains one optional, additive
  `on_replay(session, actor)` callback invoked **after** `precheck()` matches a
  cached 2xx and **before** it is returned (inside the same transaction). This
  implements the mandatory live-reauthorization rule:
  - H1b replay → active consent or `403 consent_required`.
  - S1 replay → active consent (`403 consent_required`) then exact assignment:
    missing/wrong owner `404 assignment_not_found`, revoked
    `409 assignment_already_revoked`.
  Replay never rereads mutable profile/extraction state, never creates a second
  assessment or attempt, and never returns a score. C1 operations keep
  `on_replay=None` (behaviour unchanged).
- **Authorization guards — `backend/app/term1/c2_authz.py` (Track 1-owned,
  imported by Track 2):**
  - `require_clinical_patient(actor) -> PatientProfile`: `ADMIN` →
    `403 admin_clinical_content_forbidden`; non-patient → `403 forbidden`;
    missing profile row → `409 role_profile_mismatch`.
  - `require_active_consent(session, *, patient_id) -> ConsentRecord` →
    `403 consent_required` when no `revoked_at IS NULL` row exists.
  - `require_owned_assignment(session, *, assignment_id, patient_id, *, allow_revoked=False)`:
    not found/wrong owner → `404 assignment_not_found`; revoked (when live
    required) → `409 assignment_already_revoked`.
  - Consent is required for **writes** (H1b, S1, and Track 2's DOC1/DOC5/DOC7);
    **H1a self-read survives consent withdrawal** (OQ-H1A); S2/S3 reads do not
    require consent. S1 additionally requires the exact active assignment.
- **Audit:** additive event types `HEALTH_PROFILE_VERSION_CREATED`,
  `ASSESSMENT_CREATED`, `INFERENCE_ATTEMPT_TERMINATED`; additive subject types
  `health_profile`, `assessment`, `inference_attempt` (appended to
  `constants.WORKFLOW_EVENT_TYPES` / `AUDIT_SUBJECT_TYPES`; the C1 sets stay
  prefix-identical). Success rows commit in-transaction; S1/H1b authorization
  refusals record `AUTHORIZATION_DENIED` through the failure hook.
- **Panel validation:** `backend/app/term1/panel.py` is a Term-1-owned,
  stdlib-only re-declaration of the exact `da_a2_resting_v1` contract (OQ-4):
  ordered fields `("age", "sex", "cp", "trestbps", "restecg")`;
  `age`/`trestbps` finite, strictly positive, units `years`/`mmHg` exact-token;
  `sex ∈ {0,1}`, `cp ∈ {1,2,3,4}`, `restecg ∈ {0,1,2}` integers; missing
  reasons ∈ `{not_measured, not_available_at_time, unknown, not_provided}`
  with omitted optional → `not_provided` and explicit `null` → a measurement
  reason. `backend/app/main.py` never imports `ai/` (numpy) or `research/`.
  Closed prohibited-field names (lab/outcome/wearable leakage, e.g. `chol`,
  `fbs`, `thalach`, `exang`, `oldpeak`, `slope`, `spo2`, `hrv`, `ppg`,
  `step_count`, `sleep_duration`, `syntax_score`, `stenosis_percent`,
  `cath`, `lad`, `lcx`, `rca`, `num`, `target`) map to
  `422 prohibited_clinical_field`; other unknown panel keys map to
  `422 invalid_panel_input`.

## 8. SAFE_SCOPE lifecycle semantics (Track 1; also binds Track 2 tests)

- **S1 manual path (production code path, one `BEGIN IMMEDIATE`):**
  insert `assessment` as `INPUT_VALIDATED` → `begin_attempt` (insert
  `inference_attempt` `state='INFERENCE_RUNNING'`, `generation =
  assessment.current_generation`, `worker_id='disabled_stub'`, 64-hex
  `fence_token`, `lease_until = now + 300s` (P-16), `attempt_idempotency_hash =
  sha256(canonical({assessment_id, snapshot_sha256, generation,
  dispatch_kind='assessment_submit'}))`; set `active_attempt_id` +
  `status='INFERENCE_RUNNING'`) → completion CAS in the spec's mandatory order
  (clear `active_attempt_id`/set terminal status first, then terminalize the
  attempt) → final state `status='INFERENCE_UNAVAILABLE'`,
  `reason_code='real_ai_not_authorized'`, `current_result_id NULL`,
  `active_attempt_id NULL`, `current_generation` unchanged (0), one terminal
  `inference_attempt` row. No adapter is ever contacted; no mock fallback
  exists; zero `inference_result` rows are creatable by any production path
  (no success-publication function exists until A3).
- **Lifecycle module `backend/app/term1/inference_lifecycle.py`** implements the
  accepted P-16 invariants as service functions used by tests and future A3
  code: `begin_attempt`, `complete_unavailable` (fence CAS + revocation →
  `authorization_withdrawn`), `complete_abstained`, `complete_error`,
  `recover_expired` (lease `<= now` → `INFERENCE_ERROR`/`lease_expired`,
  clear pointer, increment generation **once**), and the common fence check
  raising `409 stale_attempt_fenced` on any mismatch of attempt id, assessment
  link, `active_attempt_id`, generation, running states, worker, fence token or
  `lease_until > now` — zero DB writes on rejection. **No `complete_success`
  and no result-insert function exists** (A3 gate); tests prove result
  immutability by inserting a result row with direct, clearly test-only SQL and
  then asserting `tr_result_no_update`/`tr_result_no_delete` refusal.
- **S2/S3 snapshot integrity:** both recompute `snapshot_sha256` over the stored
  `snapshot_json` on read; a mismatch fails closed with `500 internal_error`.
- **Projections (frozen key sets):**
  - S1 response (15 keys): `contract_version, assessment_id, assignment_id,
    health_profile_id, snapshot_id, snapshot_sha256, panel_id, panel_version,
    source_contract_version, source_kind, status, reason_code, attempt_id,
    review_state, created_at` — always status-only.
  - S2 patient (7 keys): `contract_version, assessment_id, status, reason_code,
    created_at, review_state, research_output` with `research_output: null`
    until A3+B (never any score/threshold/digest field, ever, pre-B).
  - S2 doctor, pre-A3 (21 keys): `contract_version, assessment_id,
    assignment_id, health_profile_id, snapshot_id, snapshot_sha256, panel_id,
    panel_version, source_contract_version, source_kind, status, reason_code,
    inputs, units, missing_reasons, attached_documents, review_state,
    review_version, research_output (null), created_at, updated_at`.
  - S3 item (10 keys): `assessment_id, assignment_id, panel_id, panel_version,
    status, reason_code, source_kind, attempt_id, review_state, created_at`;
    envelope `{contract_version, items, next_cursor}`; `limit` 1..100 default
    20; opaque `cursor = "<created_at>|<assessment_id>"` (descending
    `created_at`, tie-broken by `assessment_id`); bad cursor →
    `400 malformed_request`.
  - H1a/H1b 200 (13 keys): `contract_version, health_profile_id,
    version_number, status, panel_id, panel_version, schema_version, inputs,
    units, missing_reasons, provenance, profile_sha256, created_at`.
- **S1 validation order (frozen):** structural/schema → idempotency header →
  authenticate/`password_change_required` → identity-key activation → replay
  precheck (a cached 2xx first passes `on_replay` live reauth, then returns) →
  first execution: role gate → `input_mode` XOR (already schema-enforced) →
  `ocr_confirmed` ⇒ `403 ocr_inference_not_authorized` (SAFE_SCOPE) → consent →
  assignment → profile pin (`404`/`409 superseded`/`422 incomplete`) → panel
  validation → attachments → reassessment target scoped to
  `(patient_id, assignment_id)` (miss ⇒ `404 assessment_not_found`) → snapshot +
  assessment + terminal attempt + audit + idempotency, one transaction.
- **H1b merge semantics:** omitted keys inherit from the active version
  (explicit keys, including `null`, overwrite); on initial creation omitted
  optional keys default to `null` + `not_provided`. Reasons for fields that are
  present non-null are dropped server-side; a request that supplies a reason for
  a field it also sets non-null, an explicit `null` without a measurement
  reason, or a reason for an unknown field ⇒ `422 missing_reason_mismatch`
  (unknown/invalid reason values ⇒ `422 invalid_panel_input`). `status =
  COMPLETE` iff merged `age`, `sex`, `cp` are present, non-null and valid;
  otherwise `DRAFT`. `expected_version_number` mismatch (including "no active
  version") ⇒ `409 concurrency_conflict`. Client-supplied provenance/OCR
  reference keys (`provenance`, `source_kind`, `source_contract_version`,
  `profile_sha256`, `ocr_source`, `document_id`, `extraction_id`) ⇒
  `422 prohibited_clinical_field`.

## 9. Test-inventory updates required by the authorized additive surface

These existing pins change **only** in their exact-inventory/count assertions
(no assertion is deleted or loosened; every equality stays an equality):

| File | Pin | Becomes |
|---|---|---|
| `tests/backend/c1/test_c1_migrations.py` | head `("20261126_06",)`; `REVISION_ORDER` ends `_06`; no C2/C3 tables; `alembic_version == [("20261126_06",)]` (×2) | head `("20261128_07",)`; order ends `20261128_07`; the five 07 tables exist, C3/08 tables still absent; version `20261128_07` |
| `tests/backend/c1/test_c1_contracts.py` | `SERVED_OPERATIONS == 22`; error total `== 37` | `== 27`; `== 63` (`C1_OPERATIONS == 20`, `IDEMPOTENT_C1 == 10`, `AUTHENTICATED_C1 == 18` unchanged) |
| `tests/backend/test_openapi_http.py` | served set = legacy∪ C1, `len == 22` | served set = legacy ∪ C1 ∪ C2, `len == 27` |
| `tests/backend/test_inference_provider.py` | served-path set matched `SERVED_OPERATIONS`; `len(served) == 22` | operation inventory `len(SERVED_OPERATIONS) == 27`; unique route paths `len(served) == 26` because H1a/H1b share one path (route-set equality and forbidden-path guards unchanged) |
| `tests/backend/test_persistence.py` | fresh-migration table inventory = legacy + C1 only | inventory additionally pins the five 07 tables (08/09 tables still absent) |

`tests/contracts/**` (legacy `openapi.yaml` oracle) and every C1 closure/
conformance/idempotency/concurrency assertion are untouched.

## 10. Mandatory-clarification reconciliation index

| Clarification (#7229164710) | Where resolved |
|---|---|
| 1 — canonical envelope with explicit identities; profile match assessment↔snapshot; reassessment/identity immutability; result pointer binds generation + exact attempt; terminal write order; outcome paths; rollback; 06→07→08 tests; old migrations preserved | §3.2, §3.5, §4 (trigger correction), §8, Track 1 tests |
| 2 — freeze enums before schemas; persisted document vocabulary; confirmed state/provenance; live replay reauth; status-only creation commit; S1/S3 score-free; S2 only under A3+B; OCR gate fails closed | §1, §2, §6, §7 (`on_replay`), §8 |
| 3 — document crash/storage (PENDING_SCAN bytes+digest first, exclusive recovery, quota/consent rechecks) | Track 2 scope; binding identity and enums frozen here (§1–§2) |
| 4 — A1/A2/A3/B independent holds; SAFE_SCOPE zero artifact/rows/dispatch | §8 (no success-publication path exists) |
| 5 — OQ-H1A self-read; P-16/P-25 defaults; C2 status | §7, §4 |

## 11. Non-authorizations restated

This checkpoint authorizes nothing. No inference adapter, artifact access,
`inference_result` row, mock fallback, patient score, OCR-to-model path,
training, merge, self-ratification or C3/C4 work exists or is implied. A1, A2,
A3, B, RD-09-TERM1-EDU-DEMO-V1 and EXC-TERM1-OCR-DEMO-V1 remain PENDING.

## Dated implementation clarification — 2026-11-28 (post-review, pre-integration)

Append-only. This implementation clarification supersedes the earlier §4 statement
that Track 1 registers twelve migration-07 triggers, its incomplete frozen-name list,
and the §8 description of a successful test-only inference-result insert. It does
not rewrite accepted C0 history or relax any database constraint. Track 1 was reviewed
at `99bfe992d2273e57226535396df58933e98fc2f3`; the independent exact-parity and
SAFE_SCOPE denial-probe confirmation is recorded in [review comment #7237649631](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/149#issuecomment-7237649631).

### Migration 07 — corrected trigger inventory and result-insertion evidence

Migration `20261128_07` and `backend/app/term1/triggers.py::C2_TRIGGER_DEFINITIONS`
contain exactly fifteen Track 1 triggers, with exact SQL parity independently verified:

1. `tr_health_profile_immutable_update`
2. `tr_health_profile_no_delete`
3. `tr_snapshot_no_update`
4. `tr_snapshot_no_delete`
5. `tr_assessment_scope_insert`
6. `tr_assessment_pointer_insert`
7. `tr_assessment_pointer_update`
8. `tr_assessment_no_delete`
9. `tr_attempt_insert_guard`
10. `tr_attempt_associate_assessment`
11. `tr_attempt_transition_guard`
12. `tr_attempt_no_delete`
13. `tr_result_insert_forbidden`
14. `tr_result_no_update`
15. `tr_result_no_delete`

In SAFE_SCOPE, `tr_result_insert_forbidden` rejects every attempted
`inference_result` insertion with `inference_result_publication_not_authorized`.
The direct-SQL tests are denial probes: they assert rejection and zero result rows.
They do not demonstrate successful test-only insertion, attempt/result association,
result immutability after a successful insert, or production publication. The earlier
§8 sentence claiming a test-only row was inserted and then tested against update/delete
triggers is superseded. No result publication, adapter dispatch, private artifact
access, or mock fallback is authorized.

### Pinned Track 2 migration 08 inventory

The exact reviewed Track 2 commit is
`a9074e41ade06a7f46d4c9e67f44fefc02317e9d` on
`arena/63d9201c-cardioassist-ai`. Its migration `20261128_08` defines six document/OCR
tables:

- `medical_document`
- `document_extraction`
- `extraction_field`
- `extraction_event`
- `assessment_document`
- `document_inflight_operation`

It currently defines thirteen document/OCR triggers:

1. `tr_medical_document_immutable_identity`
2. `tr_medical_document_no_delete`
3. `tr_medical_document_stored_immutable`
4. `tr_medical_document_promotion_guard`
5. `tr_extraction_confirmed_immutable`
6. `tr_document_extraction_no_delete`
7. `tr_extraction_field_insert_guard`
8. `tr_extraction_field_update_guard`
9. `tr_extraction_field_no_delete`
10. `tr_extraction_event_no_update`
11. `tr_extraction_event_no_delete`
12. `tr_assessment_document_no_update`
13. `tr_assessment_document_no_delete`

This is the pinned handoff inventory, not a claim that Track 2 is already integrated
or that combined startup verification has passed.

### Assessment/document binding integration requirement

At the pinned Track 2 revision, `DocumentService.bind_assessment_document()` in
`backend/app/term1_c2_documents/service.py` verifies the stored document bytes but
allocates `binding_id` while constructing and inserting the binding row. The accepted
canonical snapshot contract requires each binding identity in the attachment descriptor
before canonical snapshot construction. Integration therefore must resolve and
reauthorize the exact requested documents and any confirmed OCR extraction; re-read and
verify stored bytes/digests; preallocate immutable `binding_id` values; build the ordered
canonical attachment descriptors and snapshot; insert the assessment; then persist the
same preallocated IDs and exact resolved binding fields. These operations must remain in
the appropriate atomic write transaction. Integrated verification must compare each
persisted binding with the snapshot's descriptor and identities, not require an empty
attachment list. Preserve manual-report provenance separately from confirmed OCR
provenance; OCR-derived inference remains disabled.

This clarification records implementation facts and the remaining integration contract;
it is not C2 stage acceptance, owner self-ratification, Windows evidence, hosted CI, or
a release of any A1/A2/A3/B, RD-09, OCR-inference, research, C3, or C4 hold.
