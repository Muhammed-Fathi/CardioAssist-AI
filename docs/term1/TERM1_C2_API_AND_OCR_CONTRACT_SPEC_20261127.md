# CardioAssist-AI Term 1 — C2 + Document/OCR OpenAPI Contract & Error Spec

**Date:** 2026-11-27 (UTC / Africa/Cairo)
**Status:** `PROPOSED — NOT APPROVED, NOT DEPLOYED`
**Composition Target:** Composed additively into `/openapi.json` via `shared/contracts/term1/paths-*.yaml` (preserving legacy `shared/contracts/openapi.yaml` and all 20 frozen C1 operations)

---

## 1. Cross-Cutting Contract Rules (Inherited From C1 Closure)

Every C2 and Document/OCR operation inherits the exact C1 closure invariants verified in `TERM1_C1_HTTP_CLOSURE_EVIDENCE.md`:

1. **Authentication:** `Authorization: Bearer <session_token>`; duplicate `Authorization` headers or non-ASCII tokens → `401 authentication_required`. Accounts with `password_change_required=True` → `403 password_change_required`.
2. **Idempotency:** Every mutating POST/PUT operation below (`H1b`, `S1`, `DOC1`, `DOC5`, `DOC7`, and C3 `DOC9`) requires **exactly one** `Idempotency-Key` header (`<= 255` chars). Replay tuple: `(replay_scope="user", key_hash, actor_binding="user:<user_id>", operation="<METHOD> <template>", target_ref=<target>)`.
3. **Uniform Error Envelope & Status Discipline:**
   `{"contract_version": "v1", "error": {"code": "...", "message": "..."}}` with static per-code messages.
   **Every authenticated operation MUST declare `401`, `403`, `500`, `503`** (and `409` whenever `verify_or_activate`, `role_profile_mismatch`, idempotency, or domain state conflict is reachable). Note: `role_profile_mismatch` is strictly **`409`** (matching `errors.py::ERROR_CATALOGUE`), never `403`.
4. **Non-Enumerating IDOR (`404`):** Any attempt to access another patient's `assessment_id` or `document_id`, or a doctor accessing a patient without an active `doctor_patient_assignment`, returns **`404`** (`assessment_not_found` / `document_not_found` / `assignment_not_found`), indistinguishable from a nonexistent UUID. **`admin` role receives `403 forbidden`** on all clinical/document endpoints (no admin clinical/document access).
5. **Caching & Safe Response Headers:** Every JSON response includes `Cache-Control: no-store`, `Pragma: no-cache`. Binary content streaming (`DOC4`/`DOC8`) additionally sends `X-Content-Type-Options: nosniff`, `Content-Security-Policy: default-src 'none'`, and strict `Content-Disposition`.
6. **Legacy & M1c Guard Preservation:** No route path may contain `"research"`, `"synth"` (except existing `E6`), `"facade"`, `"artifact"`, or `"registry"`. `POST /v1/predictions/cad-tabular` and `POST /v1/monitoring/observations` stay untouched.

---

## 2. C2 Clinical Intake & Assessment Operations

| ID | Method & Path | Role & Consent | Idemp. & `target_ref` | Summary |
|---|---|---|---|---|
| **H1a** | `GET /v1/me/health-profile` | `PATIENT` (self-read allowed even if consent revoked — `OQ-H1A`) | No | Return patient's current working `health_profile` (`fields`, `provenance`, `revision_number`, `snapshot_sha256`, `updated_at`), or `404 health_profile_not_found` if not yet created. |
| **H1b** | `PUT /v1/me/health-profile` | `PATIENT`, active `synthetic_demo` consent (`403 consent_required` if revoked) | Yes (`target_ref="none"`) | Validate `da_a2_resting_v1` fields (`age`, `sex`, `cp`, optional `trestbps`, `restecg` + `units` + `missing_reasons`), reject prohibited/leakage/wearable fields, save `health_profile` + append `health_profile_revision` (`manual` provenance). Never auto-triggers AI. |
| **S1** | `POST /v1/me/assessments` | `PATIENT`, active `synthetic_demo` consent + active `assignment_id` | Yes (`target_ref="none"` — `OQ-7`) | Submit immutable assessment snapshot from either manual inputs or confirmed OCR draft (`input_mode`: `"manual"` \| `"ocr_confirmed"`), optional/required `document_bindings` (`document_id`, optional `extraction_id`), optional `reassessment_of_id` + `reason_code`. Validates panel, creates `assessment` + `assessment_document` rows, attempts inference if authorized (`A3` + `EXC-TERM1-OCR-DEMO-V1` when OCR), else `INFERENCE_UNAVAILABLE`. |
| **S2** | `GET /v1/me/assessments` | `PATIENT` (self only) | No | Paginated/ordered list of patient's own assessments (`assessment_id`, `assignment_id`, `status`, `source_provenance`, `review_decision`, `submitted_at`). **Never** includes score or explanation fields. |
| **S3** | `GET /v1/me/assessments/{assessment_id}` | `PATIENT` (owner only; `404` otherwise) | No | Detailed assessment projection: snapshot, provenance, attached documents, status, review summary, and **`research_output` ONLY when `status == 'PENDING_REVIEW'` (or post-review) AND Decision `B` is ratified**; otherwise `research_output: null` (`status-only`). |

### 2.1 Detailed Contract Notes for `S1` (`POST /v1/me/assessments`)

- **Request Body (`term1_assessment_create_request.schema.json`):**
  - `contract_version`: `"v1"`
  - `assignment_id`: UUID string (must belong to calling patient and have `revoked_at IS NULL`; otherwise `404 assignment_not_found` — wait: if owned by patient but revoked, return `409 assignment_already_revoked`; if owned by another patient or nonexistent, `404 assignment_not_found`!).
  - `input_mode`: `"manual"` | `"ocr_confirmed"` (server derives `source_provenance`: `"synthetic_demo_patient_manual"` vs `"synthetic_demo_ocr_confirmed"` — client cannot supply arbitrary `source_provenance`!).
  - `use_saved_health_profile`: boolean (optional; if `false`, explicit `panel_input` required; if `true`, server snapshots current `health_profile` atomically; if both provided, `422 validation_failed`).
  - `panel_input`: `{panel_id: "da_a2_resting_v1", features: {...}, units: {...}, missing_reasons: {...}}` (required when `input_mode="manual"` and `use_saved_health_profile=False`).
  - `ocr_source`: `{document_id, extraction_id}` (required when `input_mode="ocr_confirmed"`; server verifies extraction status is `CONFIRMED_BY_PATIENT`, owned by caller, and binds exact `document_sha256`).
  - `attached_document_ids`: array of `0..5` unique UUIDs (all must belong to calling patient; supports manual entry + attached fabricated reports). *Note:* whether the complete demonstration flow requires `>= 1` attachment in UI vs optional at API level is configurable; API recommends allowing `0..5` attachments on manual `S1` (so manual path works independently even if OCR/uploads are unavailable) while `DOC` + E2E demo fixtures attach `>= 1` approved report!
  - `reassessment_of_id`: optional UUID (must belong to same `patient_id` and `assignment_id`; `404` otherwise) + `reassessment_reason` (required when `reassessment_of_id` set).
- **Status Codes on `S1`:**
  - `201 Created`: assessment persisted (status is `PENDING_REVIEW` if `A3` succeeded, or `INFERENCE_UNAVAILABLE` / `FAILED` / `ABSTAINED` / `ABORTED_AUTHORIZATION_REVOKED` if not; `research_output` is included in response **only** if `B` is ratified and `status == 'PENDING_REVIEW'`, else `null`!).
  - `400`: `malformed_request`, `idempotency_key_required`
  - `401`: `authentication_required`, `invalid_session`
  - `403`: `forbidden`, `password_change_required`, `consent_required`, `ocr_inference_not_authorized` (if `input_mode="ocr_confirmed"` is blocked before `EXC-TERM1-OCR-DEMO-V1` ratification; or `INFERENCE_UNAVAILABLE` if C2 safe-scope records unavailability—make explicit in `C2_SAFE_SCOPE`: allow `S1` to persist `INFERENCE_UNAVAILABLE` cleanly or reject per `OQ-1`!)
  - `404`: `assignment_not_found`, `document_not_found`, `extraction_not_found`, `assessment_not_found` (for invalid `reassessment_of_id`)
  - `409`: `idempotency_key_conflict`, `idempotency_scope_conflict`, `assignment_already_revoked`, `role_profile_mismatch`, `document_not_confirmed`, `document_integrity_mismatch`, `identity_key_material_mismatch`, `identity_key_replacement_unsupported`, `concurrency_conflict`
  - `422`: `validation_failed`, `prohibited_clinical_field`, `invalid_panel_input`, `missing_reason_mismatch`
  - `500`: `internal_error`
  - `503`: `identity_key_configuration_error`

---

## 3. Bounded Document & Local OCR Operations (`DOC1`–`DOC7` in C2; `DOC8`–`DOC9` in C3)

| ID | Method & Path | Role & Consent | Idemp. & `target_ref` | Summary |
|---|---|---|---|---|
| **DOC1** | `POST /v1/me/documents` | `PATIENT`, active consent | Yes (`target_ref="none"`) | Upload one fabricated demo report (`multipart/form-data`: `file`, `document_kind`, `contract_version="v1"`). Enforces `<= 5 MiB`, magic-byte check (`PDF`/`PNG`/`JPEG`), `<= 3` pages, `<= 4096x4096` pixels, active-PDF rejection, max `20` active docs per patient. Stores privately + records `UPLOADED` event. |
| **DOC2** | `GET /v1/me/documents` | `PATIENT` (self only) | No | List caller's own uploaded documents (`document_id`, `document_kind`, `original_filename_sanitized`, `declared_media_type`, `byte_size`, `page_count`, `content_sha256`, `latest_extraction_status`, `created_at`). |
| **DOC3** | `GET /v1/me/documents/{document_id}` | `PATIENT` (owner only; `404` otherwise) | No | Document metadata + latest extraction summary + provenance event count. |
| **DOC4** | `GET /v1/me/documents/{document_id}/content` | `PATIENT` (owner only; `404` otherwise) | No | Stream verified file bytes from private store after recomputing SHA-256 (`Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, `Content-Security-Policy: default-src 'none'`). |
| **DOC5** | `POST /v1/me/documents/{document_id}/extract` | `PATIENT` (owner only, active consent) | Yes (`target_ref=document_id`) | Run real local PDF-text / Tesseract raster OCR against `CAI-DEMO-RESTING-CARDIAC-REPORT-V1` or `CAI-DEMO-UNRELATED-LABS-V1`. Persists `document_extraction`, `extraction_field` rows (raw value, parsed value or `NULL` on low-confidence/conflict, confidence, locator), and `EXTRACTED` event. **Never** auto-confirms or mutates `health_profile`. |
| **DOC6** | `GET /v1/me/documents/{document_id}/extraction` | `PATIENT` (owner only; `404` otherwise) | No | Read extraction status, template match, per-field candidate values, confidence, conflict flags, and current confirmation state. |
| **DOC7** | `POST /v1/me/documents/{document_id}/confirm` | `PATIENT` (owner only, active consent) | Yes (`target_ref=document_id`) | Patient reviews/edits extracted draft values and submits explicit confirmation (`extraction_id`, `confirmed_fields`, `units`, `missing_reasons`, `confirm_fabricated_demo_inputs: true`, optional `update_health_profile: bool`). Records `PATIENT_EDITED`/`PATIENT_CONFIRMED` `extraction_event` with diffs. Rejects unrelated-lab templates (`422 unsupported_template_for_intake`). |
| **DOC8** *(C3)* | `GET /v1/doctor/assignments/{assignment_id}/documents/{document_id}/content` | `DOCTOR` (active assignment owning an assessment that bound `document_id`; `404` otherwise) | No | Assigned doctor views original uploaded report bound to patient's assessment. |
| **DOC9** *(C3)* | `POST /v1/doctor/assignments/{assignment_id}/documents/{document_id}/verify` | `DOCTOR` (active assignment; `404` otherwise) | Yes (`target_ref=document_id`) | Doctor records `DOCTOR_VERIFIED` or `DOCTOR_REJECTED` with `reason_code` in `extraction_event` (never mutates already published `assessment.snapshot_json`). |

> **Multipart note for `DOC1` (`POST /v1/me/documents`):** Unlike JSON-only C1 routes, `DOC1` accepts `multipart/form-data` with a bounded file field (`file`) and metadata fields (`document_kind`, `contract_version`), enforces `Content-Length` + streaming byte cap (`5 MiB`) *before* buffering in memory, and uses `Idempotency-Key` keyed on `(document_kind, original_filename_sanitized, content_sha256)`. All other C2 routes remain strict `application/json`. If `python-multipart` is added to `backend/requirements.txt` for `DOC1`, document and pin its exact version in the C2 stage PR.

---

## 4. Additive C2 Error Codes (Extending C1's Closed 37-Code Catalogue)

All 37 existing C1 error codes and static messages in `backend/app/term1/errors.py::ERROR_CATALOGUE` remain **unchanged**. C2 proposes adding the following closed codes:

| Status | Code | Static Message |
|---|---|---|
| `403` | `consent_required` | Active synthetic-demo consent is required for this operation. |
| `403` | `ocr_inference_not_authorized` | OCR-confirmed demo intake is not currently authorized for model inference. |
| `404` | `health_profile_not_found` | The health profile was not found. |
| `404` | `assessment_not_found` | The assessment was not found. |
| `404` | `document_not_found` | The document was not found. |
| `404` | `extraction_not_found` | The document extraction was not found. |
| `409` | `document_not_confirmed` | The OCR extraction must be explicitly confirmed by the patient first. |
| `409` | `document_integrity_mismatch` | The stored document digest does not match the recorded immutable digest. |
| `409` | `document_limit_reached` | The maximum number of stored documents for this account has been reached. |
| `409` | `extraction_already_confirmed` | This extraction has already been confirmed. |
| `413` | `payload_too_large` | The uploaded document exceeds the maximum allowed size. |
| `415` | `unsupported_media_type` | Only PDF, PNG, and JPEG documents are accepted. |
| `422` | `invalid_document_content` | The uploaded file failed structural, page, pixel, or safety validation. |
| `422` | `invalid_panel_input` | The clinical panel values, units, or missingness reasons failed validation. |
| `422` | `missing_reason_mismatch` | Every omitted or null optional field requires a valid missingness reason. |
| `422` | `prohibited_clinical_field` | Prohibited leakage, laboratory, or wearable fields are not permitted. |
| `422` | `unsupported_template_for_intake` | This document template cannot be confirmed as resting-assessment intake. |

*(Every authenticated C2 endpoint continues to reuse C1's `400`, `401`, `403`, `404`, `409`, `422`, `500`, `503` static catalogue entries where applicable.)*
