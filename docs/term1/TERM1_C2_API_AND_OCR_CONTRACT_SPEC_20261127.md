# CardioAssist-AI Term 1 — C2 + Document/OCR OpenAPI Contract & Error Spec

**Date:** 2026-11-27 (UTC / Africa/Cairo) — **Revision 2**
**Status:** `PROPOSED — NOT APPROVED, NOT DEPLOYED`
**Composition Target:** Composed additively into `/openapi.json` via `shared/contracts/term1/paths-*.yaml` (preserving legacy `shared/contracts/openapi.yaml` and all 20 frozen C1 operations)

---

## 1. Cross-Cutting Contract Rules (Inherited From C1 Closure)

Every C2 and Document/OCR operation inherits the exact C1 closure invariants verified in `TERM1_C1_HTTP_CLOSURE_EVIDENCE.md`:

1. **Authentication:** `Authorization: Bearer <session_token>`; duplicate `Authorization` headers or non-ASCII tokens → `401 authentication_required`. Accounts with `password_change_required=True` → `403 password_change_required`.
2. **Idempotency (`R4`):** Every mutating `POST`/`PATCH` operation below (`H1b`, `S1`, `DOC1`, `DOC5`, `DOC7`, and C3 `DOC9`) requires **exactly one** `Idempotency-Key` header (`<= 255` chars). Replay tuple: `(replay_scope="user", key_hash, actor_binding="user:<user_id>", operation="<METHOD> <template>", target_ref=<target>)`.
   - `precheck()` executes **before** domain, profile, document, or consent queries.
   - `request_fingerprint` is computed strictly over the **stable original request payload/headers** (never rereading mutable latest `health_profile` or `document_extraction` state).
   - Replaying after consent or assignment revocation re-checks active authorization and fails closed (`403 consent_required` / `409 assignment_already_revoked`).
   - Replay **never** leaks provisional scores before Decision `B` is ratified (replay response passes through the active `B` projection gate).
3. **Uniform Error Envelope & Status Discipline:**
   `{"contract_version": "v1", "error": {"code": "...", "message": "..."}}` with static per-code messages.
   **Every authenticated operation MUST declare `401`, `403`, `500`, `503`** (and `409` whenever `role_profile_mismatch`, idempotency, CAS/version conflict, or domain state conflict is reachable). Note: `role_profile_mismatch` is strictly **`409`** (matching `errors.py::ERROR_CATALOGUE`), never `403`.
4. **Admin `403` vs Non-Enumerating IDOR `404` (`R5`):**
   - `ADMIN` actors receive **`403 admin_clinical_content_forbidden`** on all clinical intake, assessment, medical document, and OCR extraction routes (zero admin access to patient clinical/document content).
   - Wrong-patient, nonexistent ID, or unassigned/revoked-doctor access on `S2`, `DOC3`, `DOC4`, `DOC5`, `DOC6`, `DOC7`, `DOC8`, `DOC9` returns **`404`** (`assessment_not_found`, `document_not_found`, `assignment_not_found`) — zero IDOR existence leakage.
5. **Caching & Safe Response Headers:** Every JSON response includes `Cache-Control: no-store`, `Pragma: no-cache`. Binary content streaming (`DOC4`/`DOC8`) additionally sends `X-Content-Type-Options: nosniff`, `Content-Security-Policy: default-src 'none'`, and strict `Content-Disposition`.
6. **Legacy & M1c Guard Preservation:** No route path may contain `"research"`, `"synth"` (except existing `E6`), `"facade"`, `"artifact"`, or `"registry"`. `POST /v1/predictions/cad-tabular` and `POST /v1/monitoring/observations` stay untouched.

---

## 2. C2 Clinical Intake & Assessment Operations (C0 Routes Restored)

| ID | Method & Path | Role & Consent | Idemp. & `target_ref` | Summary |
|---|---|---|---|---|
| **H1a** | `GET /v1/me/health-profile` | `PATIENT` (self-read allowed even if consent revoked — `OQ-H1A`; `ADMIN` → `403`) | No | Return patient's current active immutable `health_profile` version (`health_profile_id`, `version_number`, `status`, `panel_id`, `panel_version`, `schema_version`, `fields`, `provenance`, `profile_sha256`, `created_at`), or `404 health_profile_not_found` if none created. |
| **H1b** | `PATCH /v1/me/health-profile` | `PATIENT`, active `synthetic_demo` consent (`403 consent_required` if revoked) | Yes (`target_ref="none"`) | Validate `DA_A2_RESTING_PANEL` (`panel_id="da_a2_resting_v1"`, `panel_version="1.0.0"`), reject prohibited/leakage/wearable fields, mark previous active row `SUPERSEDED`, and insert a **new immutable `health_profile` version row** (`DRAFT` or `COMPLETE`). Never mutates referenced rows; never auto-triggers AI. |
| **S1** | `POST /v1/assessments` | `PATIENT`, active `synthetic_demo` consent + active `assignment_id` | Yes (`target_ref="none"` — `OQ-7`) | Submit immutable `assessment_snapshot` + `assessment` binding exact `health_profile_id`, `panel_id`, `panel_version`, `input_mode` (`"manual"` \| `"ocr_confirmed"`), `panel_input` / `ocr_source`, `attached_document_ids`, and optional `reassessment_of_id` + `reassessment_reason`. |
| **S2** | `GET /v1/assessments/{assessment_id}` | `PATIENT` (owner) OR `DOCTOR` (active assignment owning `assessment.assignment_id`); `404` otherwise; `ADMIN` → `403` | No | Role-projected assessment detail: patient sees **status-only** before `B` (and educational `research_output` without threshold flags after `B`); assigned active doctor sees full provenance, snapshot, attached documents, raw/calibrated scores, dispersion, SHAP/LIME, `review_state`, and `review_version`. |
| **S3** | `GET /v1/me/assessments` | `PATIENT` (self only; `ADMIN` → `403`) | No | Paginated/ordered list of patient's own assessments (`assessment_id`, `assignment_id`, `panel_id`, `panel_version`, `status`, `source_kind`, `review_state`, `created_at`). **Never** includes score or explanation fields. |

### 2.1 Exact Request / Response Schemas for `H1a`, `H1b`, `S1`, `S2`, `S3` (`R1`, `R2`, `R4`)

#### `H1b`: `PATCH /v1/me/health-profile`
- **Request (`term1_health_profile_patch_request.schema.json`):**
  ```json
  {
    "contract_version": "v1",
    "panel_id": "da_a2_resting_v1",
    "panel_version": "1.0.0",
    "inputs": { "age": 54, "sex": 1, "cp": 2, "trestbps": 130, "restecg": null },
    "units": { "age": "years", "trestbps": "mmHg" },
    "missing_reasons": { "restecg": "not_measured" }
  }
  ```
- **Response (`200 OK`):**
  `{ "contract_version": "v1", "health_profile_id": "<uuid>", "version_number": 2, "status": "COMPLETE", "panel_id": "da_a2_resting_v1", "panel_version": "1.0.0", "schema_version": "term1.c2.profile/v1", "inputs": {...}, "units": {...}, "missing_reasons": {...}, "provenance": {...}, "profile_sha256": "<64-hex>", "created_at": "<iso8601>" }`
- **Reachable Error Statuses:** `400` (`malformed_request`, `idempotency_key_required`), `401` (`authentication_required`, `invalid_session`), `403` (`admin_clinical_content_forbidden`, `forbidden`, `password_change_required`, `consent_required`), `409` (`idempotency_key_conflict`, `idempotency_scope_conflict`, `role_profile_mismatch`, `concurrency_conflict`), `422` (`validation_failed`, `prohibited_clinical_field`, `invalid_panel_input`, `missing_reason_mismatch`), `500` (`internal_error`), `503` (`identity_key_configuration_error`).

#### `S1`: `POST /v1/assessments`
- **Request (`term1_assessment_create_request.schema.json`):**
  ```json
  {
    "contract_version": "v1",
    "assignment_id": "<uuid>",
    "health_profile_id": "<uuid>",
    "panel_id": "da_a2_resting_v1",
    "panel_version": "1.0.0",
    "input_mode": "manual",
    "panel_input": {
      "inputs": { "age": 54, "sex": 1, "cp": 2, "trestbps": 130, "restecg": null },
      "units": { "age": "years", "trestbps": "mmHg" },
      "missing_reasons": { "restecg": "not_measured" }
    },
    "ocr_source": null,
    "attached_document_ids": [],
    "reassessment_of_id": null,
    "reassessment_reason": null
  }
  ```
- **Unambiguous `S1` Field & Authorization Rules (`R4`):**
  1. `health_profile_id` is **mandatory** and must reference an active `COMPLETE` `health_profile` version owned by the caller (`404 health_profile_not_found` if absent/other patient; `409 health_profile_superseded` if superseded; `422 health_profile_incomplete` if `DRAFT`).
  2. When `input_mode == "manual"`: `panel_input` is **mandatory**, `ocr_source` MUST be `null`, `attached_document_ids` holds `0..5` unique `STORED` document UUIDs owned by the caller (bound as `SUPPORTING_REPORT` or `UNRELATED_LAB_ATTACHMENT`), and server sets `source_kind = "synthetic_demo_patient_manual"`.
  3. When `input_mode == "ocr_confirmed"`: requires ratified `EXC-TERM1-OCR-DEMO-V1` (`403 ocr_inference_not_authorized` if unratified); `ocr_source = {"document_id": "<uuid>", "extraction_id": "<uuid>", "extraction_version": <int>}` is **mandatory**; server verifies the exact `extraction_id` + `extraction_version` has `is_confirmed == True` and `template_id == "CAI-DEMO-RESTING-CARDIAC-REPORT-V1"`, binds that `document_id` as `OCR_SOURCE_REPORT` (`422 missing_mandatory_attachment` if missing/mismatched), rejects any attempt to submit `input_mode == "manual"` when referencing an unconfirmed or OCR-source extraction (`422 provenance_relabeling_forbidden`), and sets `source_kind = "synthetic_demo_ocr_confirmed"`.
  4. `reassessment_reason` is required iff `reassessment_of_id` is non-null (`422 validation_failed` otherwise); `reassessment_of_id` must belong to the same `(patient_id, assignment_id)` (`404 assessment_not_found` otherwise).
  5. **Pre-`A3` vs Post-`A3` outcome:**
     - Pre-`A3` (`CARDIOASSIST_C2_AI_MODE == "disabled"`): transitions `DRAFT -> INPUT_VALIDATED -> INFERENCE_UNAVAILABLE`, creates one `inference_attempt` (`state='INFERENCE_UNAVAILABLE'`, `reason_code='real_ai_not_authorized'`), inserts **zero** `inference_result` rows, sets `active_attempt_id=null`, `current_result_id=null`, and returns `201 Created`.
     - Post-`A3`: transitions `DRAFT -> INPUT_VALIDATED -> INFERENCE_RUNNING`, creates active leased `inference_attempt` (`lease_until = now + 300s`), dispatches IPC `POST /internal/ai/v1/infer`, commits C0 §7.3 completion CAS, and returns `201 Created` (`status` in `PENDING_REVIEW`, `INFERENCE_ABSTAINED`, `INFERENCE_UNAVAILABLE`, `INFERENCE_ERROR`; `research_output` included for patient **only** if `B` is ratified and `status == 'PENDING_REVIEW'`, else `null`).
- **Response (`201 Created`):**
  `{ "contract_version": "v1", "assessment_id": "<uuid>", "assignment_id": "<uuid>", "health_profile_id": "<uuid>", "snapshot_id": "<uuid>", "snapshot_sha256": "<64-hex>", "panel_id": "da_a2_resting_v1", "panel_version": "1.0.0", "source_contract_version": "term1.c2.intake/v1", "source_kind": "...", "status": "...", "attempt_id": "<uuid>", "review_state": "NOT_REVIEWED", "research_output": null, "created_at": "<iso8601>" }`
- **Reachable Error Statuses:** `400` (`malformed_request`, `idempotency_key_required`), `401` (`authentication_required`, `invalid_session`), `403` (`admin_clinical_content_forbidden`, `forbidden`, `password_change_required`, `consent_required`, `ocr_inference_not_authorized`), `404` (`assignment_not_found`, `health_profile_not_found`, `document_not_found`, `extraction_not_found`, `assessment_not_found`), `409` (`idempotency_key_conflict`, `idempotency_scope_conflict`, `assignment_already_revoked`, `role_profile_mismatch`, `health_profile_superseded`, `document_not_confirmed`, `document_integrity_mismatch`, `identity_key_material_mismatch`, `identity_key_replacement_unsupported`, `concurrency_conflict`), `422` (`validation_failed`, `prohibited_clinical_field`, `invalid_panel_input`, `missing_reason_mismatch`, `health_profile_incomplete`, `missing_mandatory_attachment`, `provenance_relabeling_forbidden`), `500` (`internal_error`), `503` (`identity_key_configuration_error`, `worker_unavailable`).

#### `S2`: `GET /v1/assessments/{assessment_id}` (Role-Projected Detail)
- **Patient Owner Projection (`role == 'PATIENT'`):**
  - Always includes: `contract_version`, `assessment_id`, `assignment_id`, `health_profile_id`, `snapshot_id`, `snapshot_sha256`, `panel_id`, `panel_version`, `source_contract_version`, `source_kind`, `status`, `attempt_id` (latest attempt ID), `review_state`, `inputs`, `units`, `missing_reasons`, `attached_documents` (`document_id`, `document_kind`, `extraction_id`, `extraction_version`, `attachment_role`), `created_at`, `updated_at`.
  - **Before `B`:** `research_output: null` (**status-only gate** — zero scores, zero log-odds, zero SHAP/LIME, zero artifact digests).
  - **After `B` (and `status in ('PENDING_REVIEW', 'INFERENCE_SUCCEEDED')`):** `research_output` contains `calibrated_research_score`, `score_scale_declaration`, `shap` (grouped LinearSHAP on `calibrated_log_odds`, `sum_check_passed`), `lime` (or `"WITHHELD_QUALITY_NOT_MET"`), `limitations`, and mandatory educational notice — **NEVER** `exploratory_threshold`, `exploratory_above_threshold`, `raw_model_score`, or training-background rows!
- **Assigned Active Doctor Projection (`role == 'DOCTOR'` with `revoked_at IS NULL`):**
  - Includes everything in patient projection plus `review_version`, `model_provenance` (`model_id`, `model_version`, `protocol_id`, `execution_profile`, `bundle_dir_name`, `manifest_sha256`, `source_sha256`, 6 sibling artifact SHA-256s), `raw_model_score`, `raw_model_log_odds`, `calibrated_research_score`, `calibrated_log_odds`, `calibration_meta`, `fold_dispersion`, `shap`, `lime`, `lime_meta`, `limitations`, and per-document OCR extraction diffs/confidences. Never exposes `shap_background.json` rows or HMAC keys.
- **Reachable Error Statuses:** `401`, `403` (`admin_clinical_content_forbidden`, `forbidden`, `password_change_required`), `404` (`assessment_not_found`), `409` (`role_profile_mismatch`), `500`, `503`.

#### `S3`: `GET /v1/me/assessments` (Patient List)
- **Response (`200 OK`):** `{ "contract_version": "v1", "items": [ { "assessment_id", "assignment_id", "panel_id", "panel_version", "status", "source_kind", "attempt_id", "review_state", "created_at" } ] }`. Never includes scores or explanations.
- **Reachable Error Statuses:** `401`, `403` (`admin_clinical_content_forbidden`, `forbidden`, `password_change_required`), `409` (`role_profile_mismatch`), `500`, `503`.

---

## 3. Bounded Document & Local OCR Operations (`DOC1`–`DOC7` in C2; `DOC8`–`DOC9` in C3)

| ID | Method & Path | Role & Consent | Idemp. & `target_ref` | Summary |
|---|---|---|---|---|
| **DOC1** | `POST /v1/me/documents` | `PATIENT`, active consent (`ADMIN` → `403`) | Yes (`target_ref="none"`) | Upload one project-generated fabricated demo report (`multipart/form-data`: `file`, `document_kind`, `fixture_template_id`, `contract_version="v1"`). Enforces **pre-parser `6 MiB` raw HTTP body cap** (`413`), `<= 5 MiB` file cap, magic-byte check (`PDF`/`PNG`/`JPEG`), project-fixture allowlist check (not watermark alone), `<= 3` pages, `<= 4096x4096` px (`<= 64 MiB` raster), semantic indirect-object active-PDF check (`422 active_pdf_content_rejected`), atomic quota (`20` docs / `50 MiB`), and `UPLOADED` event. |
| **DOC2** | `GET /v1/me/documents` | `PATIENT` (`ADMIN` → `403`) | No | List caller's own stored documents (`document_id`, `document_kind`, `fixture_template_id`, `original_filename_sanitized`, `declared_media_type`, `byte_size`, `page_count`, `content_sha256`, `latest_extraction_id`, `latest_extraction_version`, `latest_extraction_status`, `created_at`). |
| **DOC3** | `GET /v1/me/documents/{document_id}` | `PATIENT` (owner only; `404` otherwise; `ADMIN` → `403`) | No | Document metadata + latest extraction summary + provenance event count. |
| **DOC4** | `GET /v1/me/documents/{document_id}/content` | `PATIENT` (owner only; `404` otherwise; `ADMIN` → `403`) | No | **TOCTOU-free verified byte download:** streams from open FD while hashing served bytes (`sha256(served_bytes) == content_sha256`, aborting `500 document_integrity_mismatch` on mismatch). Sends `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, `Content-Security-Policy: default-src 'none'`. |
| **DOC5** | `POST /v1/me/documents/{document_id}/extract` | `PATIENT` (owner only, active consent; `404` wrong owner; `ADMIN` → `403`) | Yes (`target_ref=document_id`) | Invoke isolated OCR worker (`POST /internal/ocr/v1/extract`) using `pdfminer.six` + `pypdfium2` (`200 DPI`) + Tesseract (`10s`/page, `30s` total, `<= 1 MiB` extracted text). Creates a new `document_extraction` (`extraction_version = prior + 1`, `is_confirmed = False`), `extraction_field` rows (`NULL` typed value on low-confidence/conflict), and `EXTRACTED` event. |
| **DOC6** | `GET /v1/me/documents/{document_id}/extraction` | `PATIENT` (owner only; `404` otherwise; `ADMIN` → `403`) | No | Read latest `document_extraction` (`extraction_id`, `extraction_version`, `is_confirmed`, `extraction_status`, `template_id`, `fields[]`, `conflict_flag`, `confidence`). |
| **DOC7** | `POST /v1/me/documents/{document_id}/confirm` | `PATIENT` (owner only, active consent; `404` wrong owner; `ADMIN` → `403`) | Yes (`target_ref=document_id`) | Patient reviews/edits extracted values and submits explicit confirmation (`extraction_id`, `extraction_version`, `confirmed_inputs`, `units`, `missing_reasons`, `confirm_fabricated_demo_inputs: true`). Permanently locks `is_confirmed = True` on that version and inserts immutable `extraction_event` (`PATIENT_CONFIRMED` / `EDITED_AND_CONFIRMED`). Rejects unrelated-lab templates (`422 unsupported_template_for_intake`) and version mismatches (`409 extraction_version_conflict`). |
| **DOC8** *(C3)* | `GET /v1/doctor/assignments/{assignment_id}/documents/{document_id}/content` | `DOCTOR` (active assignment owning an assessment that bound `document_id`; `404` otherwise; `ADMIN` → `403`) | No | Assigned doctor views original report bound to patient's assessment with the same TOCTOU-free SHA-256 verification as `DOC4`. |
| **DOC9** *(C3)* | `POST /v1/doctor/assignments/{assignment_id}/assessments/{assessment_id}/documents/{document_id}/acknowledge` | `DOCTOR` (active assignment owning `assessment_id` + bound `document_id`; `404` otherwise; `ADMIN` → `403`) | Yes (`target_ref=document_id`) | Binds `document_acknowledgement` inside `BEGIN IMMEDIATE` to exact `(doctor_user_id, assignment_id, assessment_id, document_id, extraction_id, extraction_version)` and appends `DOCTOR_ACKNOWLEDGED` `extraction_event`. Rejects stale extraction versions (`409 extraction_version_conflict`) and never mutates `assessment_snapshot`. |

> **Resolved Multipart Dependency Strategy (`R5` / `F-C2-05`):** `DOC1` uses `multipart/form-data` with **one** explicit additive pin (`python-multipart==0.0.20`) added to `backend/requirements.txt` in the C2 `DOC1` stage PR. A pre-parser ASGI/middleware body-size guard enforces the `6 MiB` (`6,291,456` bytes) raw HTTP body limit **before** `python-multipart` parses form parts. All other C2 endpoints remain strict `application/json`. `backend/requirements.txt` contains zero ML or OCR libraries.

---

## 4. Internal Worker IPC Contracts (`R1`, `R5`, `R6`)

All worker IPC endpoints bind exclusively to `127.0.0.1` (`loopback`), require `Authorization: Bearer <CARDIOASSIST_AI_WORKER_IPC_TOKEN>` or `<CARDIOASSIST_OCR_WORKER_IPC_TOKEN>`, and reject external/browser callers:

1. **`POST /internal/ai/v1/verify-bundle` (AI Worker — `A2` `verify_only` mode):**
   - Inputs: `{ "operation": "verify_only", "bundle_dir", "hmac_key_path", "tamper_check": bool }`.
   - Calls `verify_trusted_local_bundle` + `ResearchCadPredictor.from_verified_bundle(..., verify_only=True)` + `POST_RUN_ACCEPTANCE.json` / `QUARANTINED_DO_NOT_TRUST.json` checks without returning clinical scores.
2. **`POST /internal/ai/v1/infer` (AI Worker — `A3` `activate` mode only):**
   - Inputs: `{ "operation": "activate", "assessment_id", "attempt_id", "generation", "fence_token", "worker_id", "snapshot_sha256", "panel_id", "panel_version", "panel_contract_sha256", "source_contract_version", "source_kind", "inputs", "units", "missing_reasons", "lime_seed" }` (zero PII, zero `patient_id`/`user_id`).
   - Output: `{ "assessment_id", "attempt_id", "generation", "fence_token", "worker_id", "status", "model_id", "model_version", "protocol_id", "execution_profile", "bundle_dir_name", "manifest_sha256", "source_sha256", "sibling_sha256s": {...}, "raw_model_score", "raw_model_log_odds", "calibrated_research_score", "calibrated_log_odds", "calibration_meta", "shap", "lime_status", "lime", "lime_meta", "fold_dispersion", "limitations", "result_sha256" }`.
3. **`POST /internal/ocr/v1/extract` (Isolated OCR Worker):**
   - Inputs: `{ "document_id", "content_sha256", "declared_media_type", "fixture_template_id", "storage_key" }` (zero access to `CARDIOASSIST_LOCAL_BUNDLE_DIR` or `local_bundle_hmac_v1.key`).
   - Enforces `10s`/page, `30s` total timeout, `<= 3` pages, `<= 4096x4096` px, `<= 64 MiB` decoded raster, and `<= 1 MiB` extracted text cap.

---

## 5. Additive C2 Error Codes (Extending C1's Closed 37-Code Catalogue)

All 37 existing C1 error codes and static messages in `backend/app/term1/errors.py::ERROR_CATALOGUE` remain **unchanged**. C2 proposes adding the following closed codes:

| Status | Code | Static Message |
|---|---|---|
| `403` | `admin_clinical_content_forbidden` | Administrators cannot access clinical intake, assessment, or medical document content. |
| `403` | `consent_required` | Active synthetic-demo consent is required for this operation. |
| `403` | `ocr_inference_not_authorized` | OCR-confirmed demo intake is not currently authorized for model inference. |
| `404` | `health_profile_not_found` | The health profile was not found. |
| `404` | `assessment_not_found` | The assessment was not found. |
| `404` | `document_not_found` | The document was not found. |
| `404` | `extraction_not_found` | The document extraction was not found. |
| `409` | `health_profile_superseded` | The referenced health profile version has already been superseded. |
| `409` | `document_not_confirmed` | The OCR extraction must be explicitly confirmed by the patient first. |
| `409` | `document_integrity_mismatch` | The stored document digest does not match the recorded immutable digest. |
| `409` | `document_limit_reached` | The maximum document count or storage quota for this account has been reached. |
| `409` | `extraction_already_confirmed` | This extraction version has already been confirmed. |
| `409` | `extraction_version_conflict` | The submitted extraction version does not match the bound extraction version. |
| `409` | `stale_attempt_fenced` | The inference attempt completion was rejected by fencing or lease expiration. |
| `413` | `payload_too_large` | The uploaded document exceeds the maximum allowed size. |
| `415` | `unsupported_media_type` | Only PDF, PNG, and JPEG documents are accepted. |
| `422` | `active_pdf_content_rejected` | The PDF contains prohibited active, scripted, or embedded content. |
| `422` | `health_profile_incomplete` | A complete health profile version is required before assessment submission. |
| `422` | `invalid_document_content` | The uploaded file failed structural, fixture-allowlist, page, or pixel validation. |
| `422` | `invalid_panel_input` | The clinical panel values, units, or missingness reasons failed validation. |
| `422` | `missing_mandatory_attachment` | OCR-assisted assessment submission requires a bound confirmed resting-vitals document. |
| `422` | `missing_reason_mismatch` | Every omitted or null optional field requires a valid missingness reason. |
| `422` | `prohibited_clinical_field` | Prohibited leakage, laboratory, or wearable fields are not permitted. |
| `422` | `provenance_relabeling_forbidden` | OCR-derived clinical values cannot be submitted as manual-only provenance. |
| `422` | `unsupported_template_for_intake` | This document template cannot be confirmed as resting-assessment intake. |
| `500` | `document_integrity_mismatch` | Document byte verification failed during transfer. |
| `503` | `worker_unavailable` | The isolated local inference or OCR worker is currently unavailable. |

*(Every authenticated C2 endpoint continues to reuse C1's `400`, `401`, `403`, `404`, `409`, `422`, `500`, `503` static catalogue entries where applicable.)*
