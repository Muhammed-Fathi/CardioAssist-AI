# CardioAssist-AI Term 1 — C2 + Document/OCR OpenAPI Contract & Error Spec

**Date:** 2026-11-27 (UTC / Africa/Cairo) — **Revision 3**
**Status:** `PROPOSED — NOT APPROVED, NOT DEPLOYED`
**Composition Target:** Composed additively into `/openapi.json` via `shared/contracts/term1/paths-*.yaml` (preserving legacy `shared/contracts/openapi.yaml` and all 20 frozen C1 operations)

---

## 1. Cross-Cutting Contract Rules (Inherited From C1 Closure)

Every C2 and Document/OCR operation inherits the exact C1 closure invariants verified in `TERM1_C1_HTTP_CLOSURE_EVIDENCE.md`:

1. **Authentication:** `Authorization: Bearer <session_token>`; duplicate `Authorization` headers or non-ASCII tokens → `401 authentication_required`. Accounts with `password_change_required=True` → `403 password_change_required`.
2. **Idempotency (`R4` / `R2-03`):** Every mutating `POST`/`PATCH` operation below (`H1b`, `S1`, `DOC1`, `DOC5`, `DOC7`, and C3 `DOC9`) requires **exactly one** `Idempotency-Key` header (`<= 255` chars). Replay tuple: `(replay_scope="user", key_hash, actor_binding="user:<user_id>", operation="<METHOD> <template>", target_ref=<target>)`.
   - `precheck()` executes **before** domain, profile, document, or consent queries.
   - `request_fingerprint` hashes strictly the **stable original request payload/headers** (never rereading mutable latest `health_profile` or `document_extraction` state).
   - **Live reauthorization on replay:** Before returning any cached `2xx` replay for `H1b`, `S1`, `DOC1`, `DOC5`, `DOC7`, or `DOC9`, the handler re-verifies active `consent_record` (`revoked_at IS NULL` -> `403 consent_required`) and active `doctor_patient_assignment` (`revoked_at IS NULL` -> `409 assignment_already_revoked`) even though `precheck()` precedes domain reads.
   - **No score replay:** `S1` is always status-only (never holds scores in `durable_idempotency`), and during concurrent worker dispatch/crash/retries, `S1` commits `durable_idempotency` atomically with `assessment` creation (`INFERENCE_UNAVAILABLE` pre-`A3` or initial `INFERENCE_RUNNING` -> synchronous result post-`A3`) without creating a second attempt or rereading mutable inputs. Live post-crash status is inspected via `S2`.
3. **Uniform Error Envelope & Status Discipline:**
   `{"contract_version": "v1", "error": {"code": "...", "message": "..."}}` with static per-code messages.
   **Every authenticated operation MUST declare `401`, `403`, `500`, `503`** (and `409` whenever `role_profile_mismatch`, idempotency, CAS/version conflict, or domain state conflict is reachable). Note: `role_profile_mismatch` is strictly **`409`** (matching `errors.py::ERROR_CATALOGUE`), never `403`. Every error code maps to **one** unique HTTP status.
4. **Admin `403` vs Non-Enumerating IDOR `404` (`R5`):**
   - `ADMIN` actors receive **`403 admin_clinical_content_forbidden`** on all clinical intake, assessment, medical document, and OCR extraction routes (zero admin access to patient clinical/document content).
   - Wrong-patient, nonexistent ID, or unassigned/revoked-doctor access on `S2`, `DOC3`, `DOC4`, `DOC5`, `DOC6`, `DOC7`, `DOC8`, `DOC9` returns **`404`** (`assessment_not_found`, `document_not_found`, `assignment_not_found`) — zero IDOR existence leakage.
5. **Caching & Safe Response Headers:** Every JSON response includes `Cache-Control: no-store`, `Pragma: no-cache`. Buffered binary downloads (`DOC4`/`DOC8`) additionally send `X-Content-Type-Options: nosniff`, `Content-Security-Policy: default-src 'none'`, and strict `Content-Disposition`.
6. **Legacy & M1c Guard Preservation:** No route path may contain `"research"`, `"synth"` (except existing `E6`), `"facade"`, `"artifact"`, or `"registry"`. `POST /v1/predictions/cad-tabular` and `POST /v1/monitoring/observations` stay untouched.

---

## 2. C2 Clinical Intake & Assessment Operations (C0 Routes Restored)

| ID | Method & Path | Role & Consent | Idemp. & `target_ref` | Summary |
|---|---|---|---|---|
| **H1a** | `GET /v1/me/health-profile` | `PATIENT` (self-read allowed even if consent revoked — `OQ-H1A`; `ADMIN` → `403`) | No | Return patient's current active (`superseded_at IS NULL`) immutable `health_profile` version (`health_profile_id`, `version_number`, `status`, `panel_id`, `panel_version`, `schema_version`, `inputs`, `units`, `missing_reasons`, `provenance`, `profile_sha256`, `created_at`), or `404 health_profile_not_found` if none exists. |
| **H1b** | `PATCH /v1/me/health-profile` | `PATIENT`, active `synthetic_demo` consent (`403 consent_required` if revoked) | Yes (`target_ref="none"`) | Manual-only profile update: merges omitted keys from active profile version (if any), validates `DA_A2_RESTING_PANEL`, supersedes old row (`superseded_at = now`), and inserts a new immutable `health_profile` row (`DRAFT` or `COMPLETE`). Supports optional `expected_version_number` CAS. |
| **S1** | `POST /v1/assessments` | `PATIENT`, active `synthetic_demo` consent + active `assignment_id` | Yes (`target_ref="none"` — `OQ-7`) | Submit immutable `assessment_snapshot` + `assessment` with strict `input_mode` XOR (`"manual"` vs `"ocr_confirmed"`). **Always returns status-only projection (never scores).** |
| **S2** | `GET /v1/assessments/{assessment_id}` | `PATIENT` (owner) OR `DOCTOR` (active assignment owning `assessment.assignment_id`); `404` otherwise; `ADMIN` → `403` | No | Role-projected assessment detail: patient pre-`B` is strictly status-only; patient post-`B` includes `research_output` **only** on current durable `PENDING_REVIEW` under `A3+B` (never threshold flags); doctor pre-`A3` sees status+snapshot+docs (no scores), doctor post-`A3` sees full research diagnostics. |
| **S3** | `GET /v1/me/assessments` | `PATIENT` (self only; `ADMIN` → `403`) | No | Cursor-paginated list (`limit` 1..100 default 20, `cursor`) of patient's own assessments. **Always status-only** (never scores or explanations). |

### 2.1 Complete Request / Response Schemas & Error Matrices for `H1a`, `H1b`, `S1`, `S2`, `S3` (`R2-03`)

#### `H1a`: `GET /v1/me/health-profile`
- **Request:** No body (`Authorization: Bearer <token>` only).
- **Response (`200 OK`):**
  ```json
  {
    "contract_version": "v1",
    "health_profile_id": "<uuid>",
    "version_number": 2,
    "status": "COMPLETE",
    "panel_id": "da_a2_resting_v1",
    "panel_version": "1.0.0",
    "schema_version": "term1.c2.profile/v1",
    "inputs": { "age": 54, "sex": 1, "cp": 2, "trestbps": 130, "restecg": null },
    "units": { "age": "years", "trestbps": "mmHg" },
    "missing_reasons": { "restecg": "not_measured" },
    "provenance": { "source_contract_version": "term1.c2.intake/v1", "source_kind": "synthetic_demo_patient_manual" },
    "profile_sha256": "<64-hex>",
    "created_at": "<iso8601>"
  }
  ```
- **Reachable Errors:** `401` (`authentication_required`, `invalid_session`), `403` (`admin_clinical_content_forbidden`, `forbidden`, `password_change_required`), `404` (`health_profile_not_found`), `409` (`role_profile_mismatch`), `500` (`internal_error`), `503` (`identity_key_configuration_error`).

#### `H1b`: `PATCH /v1/me/health-profile`
- **Request (`term1_health_profile_patch_request.schema.json`):**
  ```json
  {
    "contract_version": "v1",
    "panel_id": "da_a2_resting_v1",
    "panel_version": "1.0.0",
    "expected_version_number": 1,
    "inputs": { "age": 54, "sex": 1, "cp": 2, "trestbps": 130, "restecg": null },
    "units": { "age": "years", "trestbps": "mmHg" },
    "missing_reasons": { "restecg": "not_measured" }
  }
  ```
- **Exact `PATCH` & Provenance Semantics:**
  1. `expected_version_number` is optional (`null` for initial create or unpinned patch; integer `>= 1` for CAS). If supplied and `!= active.version_number`, return `409 concurrency_conflict`.
  2. **Omitted-key merge:** For an existing active profile, omitted keys in `inputs` / `units` / `missing_reasons` inherit from the prior active version; explicit keys (including `null` + `missing_reasons`) overwrite those keys. On initial creation (no prior version), omitted optional keys (`trestbps`, `restecg`) default to `null` with `missing_reasons[field] = "not_provided"`.
  3. **Draft vs Complete:** `status = "COMPLETE"` iff mandatory `age`, `sex`, and `cp` are all present and valid; otherwise `status = "DRAFT"` (stored cleanly for partial progress, rejected by `S1` with `422 health_profile_incomplete`).
  4. **Manual-only provenance honesty:** `H1b` is strictly manual (`source_kind = "synthetic_demo_patient_manual"`), rejects any client-supplied provenance/OCR reference (`422 prohibited_clinical_field`), and never auto-triggers inference. *(Honesty boundary: if a human reads values off an unattached PDF and manually types those numbers into `H1b`, no technical check can distinguish manual keystrokes from visual transcription — `source_kind` strictly records how the server received the input, making no false claim about external visual source.)*
- **Response (`200 OK`):** Same schema as `H1a` response (`200 OK` for both initial creation and version update).
- **Reachable Errors:** `400` (`malformed_request`, `idempotency_key_required`), `401` (`authentication_required`, `invalid_session`), `403` (`admin_clinical_content_forbidden`, `forbidden`, `password_change_required`, `consent_required`), `409` (`idempotency_key_conflict`, `idempotency_scope_conflict`, `role_profile_mismatch`, `concurrency_conflict`, `identity_key_material_mismatch`, `identity_key_replacement_unsupported`), `422` (`validation_failed`, `prohibited_clinical_field`, `invalid_panel_input`, `missing_reason_mismatch`), `500` (`internal_error`), `503` (`identity_key_configuration_error`).

#### `S1`: `POST /v1/assessments`
- **Request (`term1_assessment_create_request.schema.json` — Strict XOR):**
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
    "attached_document_ids": ["<uuid>"],
    "reassessment_of_id": null,
    "reassessment_reason": null
  }
  ```
- **Exact Unambiguous `S1` Rules (`R2-03`):**
  1. **Active profile pin:** `health_profile_id` MUST reference caller's active (`superseded_at IS NULL`) `COMPLETE` profile (`404 health_profile_not_found`, `409 health_profile_superseded`, `422 health_profile_incomplete`).
  2. **Strict `input_mode` XOR:**
     - `input_mode == "manual"`: `panel_input` MUST be non-null and `ocr_source` MUST be `null` (`422 validation_failed` otherwise). Sets `source_kind = "synthetic_demo_patient_manual"`. `attached_document_ids` accepts `0..5` unique `STORED` caller-owned documents (`[]` permitted for standalone non-demo manual API calls; complete educational demo UI/E2E requires `>= 1` resting-vitals attachment).
     - `input_mode == "ocr_confirmed"`: requires ratified `EXC-TERM1-OCR-DEMO-V1` + `A3` (`403 ocr_inference_not_authorized` if unratified). `panel_input` MUST be `null` and `ocr_source = {"document_id": "<uuid>", "extraction_id": "<uuid>", "extraction_version": <int>}` MUST be non-null (`422 validation_failed` otherwise). Server verifies ownership, `is_confirmed == True`, and `template_id == "CAI-DEMO-RESTING-CARDIAC-REPORT-V1"`, **reads immutable confirmed typed values directly from `document_extraction` + `extraction_field` (zero caller replacement!)**, binds `ocr_source.document_id` as `OCR_SOURCE_REPORT` (`422 missing_mandatory_attachment` if absent/unconfirmed), and sets `source_kind = "synthetic_demo_ocr_confirmed"`.
  3. **Outcome & Status-Only Response (`201 Created`):**
     - Pre-`A3` (`C2_SAFE_SCOPE`): `input_mode == "manual"` persists `status = "INFERENCE_UNAVAILABLE"`, `reason_code = "real_ai_not_authorized"`, zero `inference_result` rows, zero artifact access, returning `201 Created` (and `input_mode == "ocr_confirmed"` fails `403 ocr_inference_not_authorized`).
     - Post-`A3`: dispatches worker IPC and executes C0 §7.3 completion/terminal CAS (`PENDING_REVIEW`, `INFERENCE_ABSTAINED`, `INFERENCE_UNAVAILABLE`, `INFERENCE_ERROR`).
     - **Response (`201 Created`) is ALWAYS status-only (never includes `research_output`):**
       `{ "contract_version": "v1", "assessment_id": "<uuid>", "assignment_id": "<uuid>", "health_profile_id": "<uuid>", "snapshot_id": "<uuid>", "snapshot_sha256": "<64-hex>", "panel_id": "da_a2_resting_v1", "panel_version": "1.0.0", "source_contract_version": "term1.c2.intake/v1", "source_kind": "...", "status": "...", "reason_code": null, "attempt_id": "<uuid>", "review_state": "NOT_REVIEWED", "created_at": "<iso8601>" }`
- **Reachable Errors:** `400` (`malformed_request`, `idempotency_key_required`), `401` (`authentication_required`, `invalid_session`), `403` (`admin_clinical_content_forbidden`, `forbidden`, `password_change_required`, `consent_required`, `ocr_inference_not_authorized`), `404` (`assignment_not_found`, `health_profile_not_found`, `document_not_found`, `extraction_not_found`, `assessment_not_found`), `409` (`idempotency_key_conflict`, `idempotency_scope_conflict`, `assignment_already_revoked`, `role_profile_mismatch`, `health_profile_superseded`, `document_not_confirmed`, `document_integrity_mismatch`, `identity_key_material_mismatch`, `identity_key_replacement_unsupported`, `concurrency_conflict`), `422` (`validation_failed`, `prohibited_clinical_field`, `invalid_panel_input`, `missing_reason_mismatch`, `health_profile_incomplete`, `missing_mandatory_attachment`, `provenance_relabeling_forbidden`), `500` (`internal_error`), `503` (`identity_key_configuration_error`, `worker_unavailable`).

#### `S2`: `GET /v1/assessments/{assessment_id}` (Exact Role & Gate Projections)
- **Patient Owner Projection (`role == 'PATIENT'`):**
  - **Pre-`B` (strictly status-only per C0 §8):**
    `{ "contract_version": "v1", "assessment_id": "<uuid>", "status": "...", "reason_code": "...", "created_at": "<iso8601>", "review_state": "NOT_REVIEWED", "research_output": null }` *(plus C3 clinician-authored follow-up message metadata in C3 — zero scores, zero log-odds, zero SHAP/LIME, zero artifact digests, zero internal diagnostics!)*.
  - **Post-`B` (`A3` + `B` ratified, AND `status == 'PENDING_REVIEW'` with durable `current_result_id` verified):**
    Same envelope plus `"research_output": { "calibrated_research_score": <float>, "score_scale_declaration": "...", "shap": {...}, "lime": <dict | "WITHHELD_QUALITY_NOT_MET">, "limitations": [...], "provisional_notice": "..." }` — **NEVER** `exploratory_threshold`, `exploratory_above_threshold`, `raw_model_score`, or training-background rows, and **NEVER** served if `status != 'PENDING_REVIEW'` (no stale score!).
- **Assigned Active Doctor Projection (`role == 'DOCTOR'`, active `assignment_id`):**
  - **Pre-`A3`:** `{ "contract_version": "v1", "assessment_id", "assignment_id", "health_profile_id", "snapshot_id", "snapshot_sha256", "panel_id", "panel_version", "source_contract_version", "source_kind", "status", "reason_code", "inputs", "units", "missing_reasons", "attached_documents": [...], "review_state", "review_version", "research_output": null, "created_at", "updated_at" }`.
  - **Post-`A3` (`status == 'PENDING_REVIEW'`):** adds `"research_output": { "serving_eligibility": "RESEARCH_ONLY_NOT_INDIVIDUAL_CLINICAL_RISK", "model_provenance": {...}, "raw_model_score", "raw_model_log_odds", "calibrated_research_score", "calibrated_log_odds", "calibration_meta", "fold_dispersion", "shap", "lime_status", "lime", "lime_meta", "limitations", "result_sha256" }` + per-document OCR extraction diffs/confidences. Never exposes `shap_background.json` rows or HMAC keys.
- **Reachable Errors:** `401`, `403` (`admin_clinical_content_forbidden`, `forbidden`, `password_change_required`), `404` (`assessment_not_found`), `409` (`role_profile_mismatch`), `500`, `503`.

#### `S3`: `GET /v1/me/assessments` (Paginated Status-Only List)
- **Query Params:** `limit` (`int`, `1..100`, default `20`), `cursor` (optional opaque `created_at|assessment_id` cursor).
- **Response (`200 OK`):** `{ "contract_version": "v1", "items": [ { "assessment_id", "assignment_id", "panel_id", "panel_version", "status", "reason_code", "source_kind", "attempt_id", "review_state", "created_at" } ], "next_cursor": "<str | null>" }`. Never includes scores or explanations.
- **Reachable Errors:** `400` (`malformed_request`), `401`, `403` (`admin_clinical_content_forbidden`, `forbidden`, `password_change_required`), `409` (`role_profile_mismatch`), `500`, `503`.

---

## 3. Bounded Document & Local OCR Operations (`DOC1`–`DOC7` in C2; `DOC8`–`DOC9` in C3)

| ID | Method & Path | Role & Consent | Idemp. & `target_ref` | Summary & Exact Error Codes |
|---|---|---|---|---|
| **DOC1** | `POST /v1/me/documents` | `PATIENT`, active consent (`ADMIN` → `403`) | Yes (`target_ref="none"`) | Upload one fabricated report (`multipart/form-data`: `file`, `document_kind`, `fixture_template_id`, `contract_version`). Enforces pre-parser `6 MiB` raw body cap (`413`), max `4` form fields / `1` file / `<= 64 KiB` metadata, `<= 5 MiB` file, magic bytes (`415`), server-owned **file-SHA allowlist (`CARDIOASSIST_DEMO_FIXTURE_MANIFEST`)** mapping `sha256 -> (template_id, document_kind)` (`422 invalid_document_content`), `<= 3` pages, `<= 4096x4096` px, semantic PDF check (`422 active_pdf_content_rejected`), atomic `PENDING_SCAN -> STORED` quota (`20` docs / `50 MiB`), re-checked consent at finalize, and `UPLOADED` event. Errors: `400`, `401`, `403`, `409`, `413`, `415`, `422`, `500`, `503`. |
| **DOC2** | `GET /v1/me/documents` | `PATIENT` (`ADMIN` → `403`) | No | Cursor-paginated (`limit` 1..100 default 20, `cursor`) list of caller's stored documents (`document_id`, `document_kind`, `fixture_template_id`, `original_filename_sanitized`, `declared_media_type`, `byte_size`, `page_count`, `content_sha256`, `latest_extraction_id`, `latest_extraction_version`, `latest_extraction_status`, `created_at`). Errors: `400`, `401`, `403`, `409`, `500`, `503`. |
| **DOC3** | `GET /v1/me/documents/{document_id}` | `PATIENT` (owner only; `404` otherwise; `ADMIN` → `403`) | No | Document metadata + latest extraction summary + event count. Errors: `401`, `403`, `404`, `409`, `500`, `503`. |
| **DOC4** | `GET /v1/me/documents/{document_id}/content` | `PATIENT` (owner only; `404` otherwise; `ADMIN` → `403`) | No | **Pre-header buffered SHA-256 verification:** safely opens regular file (`O_NOFOLLOW`/no reparse), reads bounded `<= 5 MiB` bytes once into memory, verifies `len(buf) == byte_size` AND `sha256(buf) == content_sha256` **BEFORE** sending any HTTP status/headers/body; on mismatch returns `409 document_integrity_mismatch` (zero bytes sent, never `200`). Errors: `401`, `403`, `404`, `409`, `500`, `503`. |
| **DOC5** | `POST /v1/me/documents/{document_id}/extract` | `PATIENT` (owner only, active consent; `404` wrong owner; `ADMIN` → `403`) | Yes (`target_ref=document_id`) | Verifies stored blob SHA-256, invokes isolated OCR worker (`POST /internal/ocr/v1/extract`) using `pdfminer.six` + `pypdfium2` (`200 DPI`) + Tesseract (`10s`/page, `30s` total, `<= 1 MiB` extracted text). Creates new `document_extraction` (`extraction_version = prior + 1`, `is_confirmed = False`), `extraction_field` rows (`NULL` typed value on low-confidence/conflict), and `EXTRACTED` event. Errors: `400`, `401`, `403`, `404`, `409`, `422`, `500`, `503`. |
| **DOC6** | `GET /v1/me/documents/{document_id}/extraction` | `PATIENT` (owner only; `404` otherwise; `ADMIN` → `403`) | No | Read latest `document_extraction` (`extraction_id`, `extraction_version`, `is_confirmed`, `extraction_status`, `template_id`, `fields[]`, `conflict_flag`, `confidence`). Errors: `401`, `403`, `404`, `409`, `500`, `503`. |
| **DOC7** | `POST /v1/me/documents/{document_id}/confirm` | `PATIENT` (owner only, active consent; `404` wrong owner; `ADMIN` → `403`) | Yes (`target_ref=document_id`) | Patient reviews/edits extracted values and submits explicit confirmation (`extraction_id`, `extraction_version`, `confirmed_inputs`, `units`, `missing_reasons`, `confirm_fabricated_demo_inputs: true`). Locks `is_confirmed = True`, stores `confirmed_values_sha256`, and appends immutable `extraction_event` (`PATIENT_CONFIRMED` / `EDITED_AND_CONFIRMED`). Rejects unrelated-lab templates (`422 unsupported_template_for_intake`) and version mismatches (`409 extraction_version_conflict`). Errors: `400`, `401`, `403`, `404`, `409`, `422`, `500`, `503`. |
| **DOC8** *(C3)* | `GET /v1/doctor/assignments/{assignment_id}/documents/{document_id}/content` | `DOCTOR` (active assignment owning an assessment that bound `document_id`; `404` otherwise; `ADMIN` → `403`) | No | Assigned doctor views bound report with the identical pre-header buffered `<= 5 MiB` SHA-256 verification (`content_sha256` & `document_sha256_at_bind`) as `DOC4` (`409 document_integrity_mismatch` before any body). Errors: `401`, `403`, `404`, `409`, `500`, `503`. |
| **DOC9** *(C3)* | `POST /v1/doctor/assignments/{assignment_id}/assessments/{assessment_id}/documents/{document_id}/acknowledge` | `DOCTOR` (active assignment owning `assessment_id` + bound `document_id`; `404` otherwise; `ADMIN` → `403`) | Yes (`target_ref=document_id`) | **Acknowledge-only semantics (never claims clinical verification of real care):** binds C3 `document_acknowledgement` inside `BEGIN IMMEDIATE` to non-null `assessment_document.binding_id` (`extraction_id`/`extraction_version` verified against `binding_id`; `409 extraction_version_conflict` on mismatch) and appends `DOCTOR_ACKNOWLEDGED` `extraction_event`. Errors: `400`, `401`, `403`, `404`, `409`, `422`, `500`, `503`. |

> **Resolved Multipart Dependency Strategy (`R5` / `F-C2-05`):** `DOC1` uses `multipart/form-data` with **one** explicit additive pin (`python-multipart==0.0.20`) added to `backend/requirements.txt` in the C2 `DOC1` stage PR. Pre-parser ASGI middleware rejects bodies `> 6 MiB` (`6,291,456` bytes) **before** `python-multipart` runs, and multipart parser config bounds parts (`<= 4` fields, `1` file, `<= 64 KiB` non-file field bytes). All other endpoints are strict `application/json`. `backend/requirements.txt` contains zero ML or OCR libraries.

### 3.1 Exact Request / Response Schemas for `DOC1`–`DOC9`

- **`DOC1` (`POST /v1/me/documents`, `201 Created`):**
  - Request (`multipart/form-data`): `contract_version="v1"`, `document_kind` (`RESTING_VITALS_REPORT` \| `UNRELATED_LAB_REPORT`), `fixture_template_id` (`CAI-DEMO-RESTING-CARDIAC-REPORT-V1` \| `CAI-DEMO-UNRELATED-LABS-V1`), `file` (binary PDF/PNG/JPEG `<= 5 MiB`).
  - Response (`201 Created`): `{ "contract_version": "v1", "document_id": "<uuid>", "status": "STORED", "document_kind": "...", "fixture_template_id": "...", "declared_media_type": "...", "byte_size": <int>, "page_count": <int|null>, "pixel_width": <int|null>, "pixel_height": <int|null>, "content_sha256": "<64-hex>", "created_at": "<iso8601>" }`.
- **`DOC2` (`GET /v1/me/documents?limit=20&cursor=...`, `200 OK`):**
  - Response: `{ "contract_version": "v1", "items": [ <DOC1 item + latest_extraction_id, latest_extraction_version, latest_extraction_status> ], "next_cursor": "<str | null>" }`.
- **`DOC3` (`GET /v1/me/documents/{document_id}`, `200 OK`):**
  - Response: `{ <DOC1 fields>, "original_filename_sanitized": "<str>", "latest_extraction": <DOC6 summary | null>, "event_count": <int> }`.
- **`DOC4` & `DOC8` (`GET .../content`, `200 OK`):**
  - Response: raw verified bytes (`Content-Type: application/pdf | image/png | image/jpeg`, `Content-Length`, `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, `Content-Security-Policy: default-src 'none'`, `Content-Disposition: attachment; filename="<sanitized>"`). Returns `409 document_integrity_mismatch` JSON **before** headers/body on length or SHA-256 mismatch.
- **`DOC5` (`POST /v1/me/documents/{document_id}/extract`, `200 OK`) & `DOC6` (`GET /v1/me/documents/{document_id}/extraction`, `200 OK`):**
  - `DOC5` Request: `{ "contract_version": "v1" }` (empty JSON object).
  - `DOC5` / `DOC6` Response: `{ "contract_version": "v1", "document_id": "<uuid>", "extraction_id": "<uuid>", "extraction_version": <int>, "extraction_status": "PARSED_COMPLETE" | "PARTIAL_REVIEW_REQUIRED" | "UNSUPPORTED_TEMPLATE" | "WORKER_FAILED", "template_id": "<str|null>", "is_confirmed": <bool>, "confirmed_values_sha256": "<64-hex|null>", "fields": [ { "field_name", "raw_text", "typed_value_json", "unit", "confidence", "conflict_flag", "parse_status", "provenance_kind" } ], "created_at": "<iso8601>" }` (returning `404 extraction_not_found` on `DOC6` if no extraction exists yet).
- **`DOC7` (`POST /v1/me/documents/{document_id}/confirm`, `200 OK`):**
  - Request: `{ "contract_version": "v1", "extraction_id": "<uuid>", "extraction_version": <int>, "confirmed_inputs": { "age": 54, "sex": 1, "cp": 2, "trestbps": 130, "restecg": null }, "units": { "age": "years", "trestbps": "mmHg" }, "missing_reasons": { "restecg": "not_measured" }, "confirm_fabricated_demo_inputs": true }`.
  - Response: `{ "contract_version": "v1", "document_id": "<uuid>", "extraction_id": "<uuid>", "extraction_version": <int>, "is_confirmed": true, "confirmed_values_sha256": "<64-hex>", "event_type": "PATIENT_CONFIRMED" | "EDITED_AND_CONFIRMED", "confirmed_at": "<iso8601>" }`.
- **`DOC9` *(C3)* (`POST /v1/doctor/assignments/{assignment_id}/assessments/{assessment_id}/documents/{document_id}/acknowledge`, `200 OK`):**
  - Request: `{ "contract_version": "v1", "binding_id": "<uuid>", "extraction_id": "<uuid|null>", "extraction_version": <int|null>, "note": "<optional str <= 500 chars>" }`.
  - Response: `{ "contract_version": "v1", "acknowledgement_id": "<uuid>", "assignment_id": "<uuid>", "assessment_id": "<uuid>", "document_id": "<uuid>", "binding_id": "<uuid>", "extraction_id": "<uuid|null>", "extraction_version": <int|null>, "acknowledged_at": "<iso8601>" }`.

---

## 4. Single Internal Worker IPC Protocol & `A2` Local CLI (`R2-04`, `R2-05`)

**Single IPC Protocol:** C2 uses **one** runtime worker IPC architecture — operator-started `127.0.0.1`-only loopback HTTP/JSON worker daemons (one `.venv-ai-worker` daemon, one `.venv-ocr-worker` daemon running under separate unprivileged OS accounts / NTFS DACLs with minimal sanitized environments):
- Zero external/browser access; binds strictly to `127.0.0.1`.
- Mandatory `Authorization: Bearer <CSPRNG_IPC_TOKEN>` checked via `hmac.compare_digest`.
- Strict request wall-clock deadline (`30s`) and response byte cap (`512 KiB` AI / `1 MiB` OCR).
- Startup self-check fails closed (`503`) if required trusted root / DACL / env bindings are missing or tampered.

1. **`A2` Verification-Only Operation (One-Shot Local CLI, NO HTTP endpoint, NO caller path args):**
   - Executed locally by owner / independent verifier via `python -m backend.app.term1_c2.verify_local_bundle` reading **only** trusted local operator config (`CARDIOASSIST_LOCAL_TRUSTED_ROOT`, `CARDIOASSIST_LOCAL_BUNDLE_DIR`, `CARDIOASSIST_LOCAL_HMAC_KEY_PATH`) — never accepting caller-supplied paths.
   - Delegates directly to **actual** `ai/` symbols:
     - `ai.packaging.verify_trusted_local_bundle(bundle_dir, trusted_local_root=..., signing_key=...)` (checking `ATTESTATION_SCHEME == "hmac-sha256-local-producer-v1"`, DACL/POSIX perms, no symlinks/reparse, no `QUARANTINED_DO_NOT_TRUST.json`, valid `POST_RUN_ACCEPTANCE.json`).
     - `ai.inference.ResearchCadPredictor.from_verified_bundle(bundle_dir, trusted_local_root=..., signing_key=...)` (exact 3-arg signature — no invented `verify_only` kwarg).
     - `predictor.predict_research_only(payload, ...)` with adapter-constructed `payload = {"synthetic": True, "panel_id": "da_a2_resting_v1", "features": ..., "units": ..., "missing_reasons": ...}` (bounded `<= 8` synthetic vectors; handles missing optional `trestbps`/`restecg` per `ED-DA-A2-01` abstention rules), verified against independent `exact_coalition_shapley_oracle` + `LimeQualityPolicy` + tamper/quarantine refusal tests with **zero** runtime DB writes.
2. **`POST /internal/ai/v1/infer` (AI Worker Daemon — `A3` `activate` Mode Only):**
   - **Request:** `{ "assessment_id", "attempt_id", "generation", "fence_token", "worker_id", "snapshot_sha256", "panel_id", "panel_version", "panel_contract_sha256", "source_contract_version", "source_kind", "inputs", "units", "missing_reasons", "lime_seed" }` (zero PII, zero `patient_id`/`user_id`).
   - **Response (echoes every identity/binding field so backend verifies exact match before CAS):** `{ "assessment_id", "attempt_id", "generation", "fence_token", "worker_id", "snapshot_sha256", "panel_id", "panel_version", "panel_contract_sha256", "source_contract_version", "source_kind", "status", "reason_code", "model_id", "model_version", "protocol_id", "execution_profile", "bundle_dir_name", "manifest_sha256", "source_sha256", "sibling_sha256s": {...}, "raw_model_score", "raw_model_log_odds", "calibrated_research_score", "calibrated_log_odds", "calibration_meta", "shap", "lime_status", "lime", "lime_meta", "fold_dispersion", "limitations", "result_sha256" }`.
3. **`POST /internal/ocr/v1/extract` (Isolated OCR Worker Daemon — Separate OS Account):**
   - **Environment isolation:** Runs under separate unprivileged OS user with zero NTFS/POSIX read ACLs on `CARDIOASSIST_LOCAL_BUNDLE_DIR` or `local_bundle_hmac_v1.key`, minimal sanitized `env` (`PATH`, `TESSDATA_PREFIX`, `LANG` only — zero `CARDIOASSIST_*` backend secrets).
   - **Request:** `{ "document_id", "content_sha256", "declared_media_type", "fixture_template_id", "storage_key" }`.
   - Enforces `10s`/page, `30s` total timeout, `<= 3` pages, `<= 4096x4096` px, `<= 64 MiB` decoded raster, and `<= 1 MiB` extracted text cap.

---

## 5. Additive C2 Error Codes (Unique Status-Per-Code Catalogue)

All 37 existing C1 error codes and static messages in `backend/app/term1/errors.py::ERROR_CATALOGUE` remain **unchanged**. Each additive C2 code maps to **exactly one** HTTP status:

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
| `503` | `worker_unavailable` | The isolated local inference or OCR worker is currently unavailable. |

*(Every authenticated C2 endpoint continues to reuse C1's `400`, `401`, `403`, `404`, `409`, `422`, `500`, `503` static catalogue entries where applicable.)*
