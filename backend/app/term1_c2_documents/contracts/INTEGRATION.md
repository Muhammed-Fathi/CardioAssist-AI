# Track 2 → Track 1 integration requirements (C2 SAFE_SCOPE, DOC1–DOC7)

Status: **PROPOSED — NOT APPROVED, NOT DEPLOYED.** Track 2 supplies these modules
and artifacts on the isolated contributor branch; the core integrator (Track 1)
owns all shared-file wiring and the single integrated C2 Draft PR. Track 2 has
**not** edited any shared file (`backend/app/main.py`, `term1/api.py`,
`term1/errors.py`, `term1/openapi.py`, `term1/constants.py`, `term1/models.py`,
`migrations/env.py`, `shared/contracts/term1/**`).

Baseline: bootstrap `review/term1-c2-authorized-bootstrap` @ `5e763b0`; accepted
delivery `delivery/term1-prototype` @ `5c96a2b`. Grant
`AUTHORIZE-TERM1-C2-SAFE-SCOPE-V1` (PR #147 comment 7232372420).

## 1. Core model registration (shared)
Import the Track 2 ORM module for its registration side effect so Alembic
`compare_metadata` and startup `verify_schema` cover the six C2 tables:

```python
import backend.app.term1_c2_documents.models  # noqa: F401
```

Add it beside the existing `import backend.app.term1.models` in
`backend/migrations/env.py` and in the application wiring that registers models.
Tables: `medical_document`, `document_extraction`, `extraction_field`,
`extraction_event`, `assessment_document`, and the corrections-round
`document_inflight_operation` (T2-R1 durable in-flight ownership/lease/fence).

## 2. Migration ordering (shared chain)
* Track 1 publishes `20261128_07` (assessment core). Track 2's
  `backend/migrations/versions/20261128_08_c2_documents_ocr.py` has
  `down_revision = "20261128_07"` and is **additive** (6 tables, 13 immutability /
  guard triggers, RB-C1 downgrade guard). The corrections round added the
  `extraction_field` INSERT/UPDATE/DELETE guards, the `medical_document`
  STORED-freeze and promotion guards, the `document_inflight_operation` table,
  the `confirmed_envelope_json` / `confirmed_unit` / `missing_reason` /
  `pixel_width` / `pixel_height` columns, and composite parent/child FKs.
* Until `07` exists, `alembic upgrade head` cannot resolve the chain on the
  contributor branch. This is the expected integration dependency, not a defect.
  Track 2 tests use an explicitly labelled disposable harness (C1 `create_all` +
  migration-08 `upgrade()` applied via bound `Operations`), so the real triggers
  are exercised without alembic head resolution.
* After `07` lands, run the full `06 → 07 → 08` upgrade and `08 → 07 → 06`
  downgrade tests (the latter must refuse while any C1/07/08 table is populated,
  per the RB-C1 guard).

## 3. Application route registration (shared)
After `register_term1_routes(app, handler=term1_handler)` in `create_app`:

```python
from backend.app.term1_c2_documents.api import DocumentHandler, register_document_routes
doc_handler = DocumentHandler(database=database, term1=term1_handler)
app.state.doc = doc_handler
register_document_routes(app, handler=doc_handler)
```

`DocumentHandler` lazily builds a `DocumentService` from operator settings
(§5). For tests, inject a service via `DocumentHandler(..., service=...)`.

**Final integrated route inventory = 22 + 5 + 7 = 34 operations.** The existing
C1/legacy surface serves **22**; Track 1's shared C2 core adds **5**
(H1a/H1b/S1–S3); Track 2 adds the **7** DOC operations. The earlier "22 → 29"
figure was contributor-only (22 + 7) and is superseded: Track 1 must update the
route-count guard in `tests/backend/test_inference_provider.py` to **34** and
extend `SERVED_OPERATIONS` in `term1/openapi.py` with the five core C2 **and**
seven DOC operations. Track 2 registers exactly the seven DOC routes and does not
weaken any C1 route/security guard (verified by `test_c2_r5_api_contract.py` and
`test_c2_scope_boundary.py`).

## 4. Error catalogue + OpenAPI composition (shared)
* Merge `DOCUMENT_ERROR_CATALOGUE`
  (`backend/app/term1_c2_documents/errors.py`, 21 additive codes) into the global
  error catalogue and the composed OpenAPI. The frozen C1 catalogue (37 codes)
  is unchanged. `doc_api_error()` already falls back to the C1 catalogue for
  shared codes.
* Merge the Track 2 contract artifacts into `shared/contracts/term1/`:
  - `contracts/paths-documents.yaml` → a `paths-documents.yaml` path source;
  - `contracts/schemas/*.schema.json` → `shared/contracts/term1/schemas/`;
  - `contracts/errors.c2.yaml` / `.json` → the additive error catalogue section.
  These are generated deterministically by
  `python -m backend.app.term1_c2_documents.contracts.generate`; the contract
  test fails on drift.

## 5. Operator settings / environment (shared wiring)
Track 2 reads three operator variables (see `settings.py`); the document surface
fails closed per request (`503 worker_unavailable`) when they are absent, so the
legacy and C1 routes keep working:
* `CARDIOASSIST_PRIVATE_DOC_DIR` — absolute private blob root outside Git/web/AI
  roots (the validator refuses a root inside the repo or overlapping a configured
  AI bundle / web root);
* `CARDIOASSIST_OCR_WORKER_URL` — an **exact parsed loopback origin**
  (`http://127.0.0.1:<port>` or `http://[::1]:<port>`); `localhost`, credentials,
  paths, queries and fragments are refused (T2-R3);
* `CARDIOASSIST_OCR_IPC_TOKEN` — ≥32-char CSPRNG bearer shared with the worker,
  free of whitespace/control characters.

## 6. Isolated OCR worker deployment (operator)
Run the worker under a **separate unprivileged OS account** with a sanitized
environment (no backend secrets, no AI bundle/signing-key/research access):

```
CARDIOASSIST_OCR_IPC_TOKEN=... CARDIOASSIST_PRIVATE_DOC_DIR=... \
CARDIOASSIST_TESSERACT_CMD=... TESSDATA_PREFIX=... \
python -m backend.app.term1_c2_documents.worker --port 8765
```

`worker.verify_sanitized_env` enforces a **strict allowlist** (T2-R4): any
non-allowlisted variable — including every `CARDIOASSIST_*` secret/AI binding —
fails startup closed. The worker enforces the server-owned fixture SHA-256
manifest itself before parsing, validates exact request schemas, bounds
simultaneous parser jobs (`WORKER_MAX_CONCURRENCY`), and applies a per-socket read
deadline plus the engine's monotonic total/per-page deadline. `build_server`
refuses any non-`127.0.0.1` bind. The backend IPC client disables proxies and
refuses redirects, and validates the complete response schema + identity echoes.
Pins: `backend/requirements-ocr-worker.txt` (pdfminer.six 20250506, pypdfium2
4.30.0, Pillow 11.2.1, pytesseract 0.3.13 + resolved transitives). Native
Tesseract 5.4.1 + `eng.traineddata`. $0, no cloud/paid API.

**Windows deployment/isolation:** see the Track 2-owned
`backend/app/term1_c2_documents/WINDOWS_OCR_WORKER_RUNBOOK.md` (separate `cai-ocr`
account, backend-writer/OCR-reader NTFS DACL, reparse-point refusal, strict env,
different-account read/AI-denial checks). Native Windows checks are
**OWNER-EXECUTED** and are **not** claimed as passed from the Linux sandbox.

## 7. Assessment binding (Track 1 S1)
Track 1's S1 calls `DocumentService.bind_assessment_document(session, ...)` to
attach a confirmed OCR source or supporting report to an assessment. It enforces
same-patient ownership, STORED status, confirmed extraction + exact version for
`OCR_SOURCE_REPORT`, **re-reads and SHA-verifies the complete stored buffer**
before binding, **verifies the canonical confirmation digest** reconstructed from
the persisted child rows, and records `document_sha256_at_bind` from the verified
bytes (T2-R2). The `assessment_document` composite FK targets Track 1's
`assessment` table.

## 8. Verified panel binding
`PANEL_CONTRACT_SHA256 = c18ad4cd2cf08f6fefb2e340573760da7000bc1d8eb4ad38783b873c018e57b8`
was verified equal to `ai.panels.DA_A2_RESTING_PANEL.contract_sha256`
(`da_a2_resting_v1` v1.0.0, DA-A2, `resting_assessment`,
`real_data_execution_authorized=False`). See
`tests/backend/c2/test_c2_panel_contract.py`.

## 9. Boundaries preserved
DOC1–DOC7 only. No DOC8/DOC9/doctor acknowledgement (C3). No OCR-to-inference
(the exception is pending). No automatic assessment submission; patient
confirmation ≠ clinician verification. No AI bundle / private model access; no
inference dispatch; raw OCR values and patient-corrected values are stored
separately with honest provenance (no laundering).

## 10. Corrections round (reviewer REQUEST CHANGES #7233518509)
Targeted implementation corrections on the same contributor branch (no redesign,
no second-stage PR, no merge/self-ratify):

* **T2-R1** durable in-flight ownership/lease/fence (`document_inflight_operation`);
  DOC5 live consent + replay BEFORE dispatch; ownership-based recovery (expired
  lease) reconstructing the ORIGINAL replay identity, `UPLOADED` event and audit
  atomically with STORED promotion; fence-checked finalize; safe orphan sweep.
  Regressions: `test_c2_r1_idempotency_recovery.py`.
* **T2-R2** confirmed-child INSERT/UPDATE/DELETE triggers + composite parent FK;
  persisted canonical confirmation envelope + typed per-field units/reasons;
  digest verified on reads/binding; STORED digest/status/pixel freeze; promotion
  guard. Regressions: `test_c2_r2_extraction_integrity.py`.
* **T2-R3** portable secure open (Windows reparse-point refusal + POSIX
  containment); backend-writer/OCR-reader permissions; exact parsed loopback
  origin; no-proxy/no-redirect client; root containment; Windows runbook.
  Regressions: `test_c2_r3_portability_isolation.py`.
* **T2-R4** worker-side SHA manifest enforcement; strict env allowlist; exact
  request/response schemas + identity echoes; bounded concurrency + real
  deadlines; pre-decode pixel guards; text-overflow rejection; per-page
  provenance. Regressions: `test_c2_r4_worker_boundaries.py`.
* **T2-R5** exact multipart field/file-part names; bounded JSON; pixel metadata in
  DOC1/DOC3; strict DOC7 schema; integrated inventory **34**. Regressions:
  `test_c2_r5_api_contract.py`.

Track 1 dependencies still required for full integration: publish `20261128_07`;
register the Track 2 models; wire the seven DOC routes + five core C2 routes into
`create_app` and update the route-count guard to **34**; merge the error catalogue
and contract artifacts; run the full `06 → 07 → 08` upgrade and populated/empty
downgrade tests; execute the native Windows owner checks. The contributor branch
does not edit shared files and does not merge.
