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
`compare_metadata` and startup `verify_schema` cover the five C2 tables:

```python
import backend.app.term1_c2_documents.models  # noqa: F401
```

Add it beside the existing `import backend.app.term1.models` in
`backend/migrations/env.py` and in the application wiring that registers models.
Tables: `medical_document`, `document_extraction`, `extraction_field`,
`extraction_event`, `assessment_document`.

## 2. Migration ordering (shared chain)
* Track 1 publishes `20261128_07` (assessment core). Track 2's
  `backend/migrations/versions/20261128_08_c2_documents_ocr.py` has
  `down_revision = "20261128_07"` and is **additive** (5 tables, 8 immutability
  triggers, RB-C1 downgrade guard).
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
The served `/v1` inventory grows from **22 to 29** operations; update the
route-count guard in `tests/backend/test_inference_provider.py` accordingly and
extend `SERVED_OPERATIONS` in `term1/openapi.py` with the seven DOC operations.

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
* `CARDIOASSIST_PRIVATE_DOC_DIR` — absolute private blob root outside Git/web roots;
* `CARDIOASSIST_OCR_WORKER_URL` — loopback-only (`http://127.0.0.1:<port>`);
* `CARDIOASSIST_OCR_IPC_TOKEN` — ≥32-char CSPRNG bearer shared with the worker.

## 6. Isolated OCR worker deployment (operator)
Run the worker under a **separate unprivileged OS account** with a sanitized
environment (no backend secrets, no AI bundle/signing-key/research access):

```
CARDIOASSIST_OCR_IPC_TOKEN=... CARDIOASSIST_PRIVATE_DOC_DIR=... \
CARDIOASSIST_TESSERACT_CMD=... TESSDATA_PREFIX=... \
python -m backend.app.term1_c2_documents.worker --port 8765
```

`worker.verify_sanitized_env` fails closed if any `CARDIOASSIST_*` secret/AI
binding is present; `build_server` refuses any non-`127.0.0.1` bind. Pins:
`backend/requirements-ocr-worker.txt` (pdfminer.six 20250506, pypdfium2 4.30.0,
Pillow 11.2.1, pytesseract 0.3.13 + resolved transitives). Native Tesseract 5.4.1
+ `eng.traineddata`. $0, no cloud/paid API.

## 7. Assessment binding (Track 1 S1)
Track 1's S1 calls `DocumentService.bind_assessment_document(session, ...)` to
attach a confirmed OCR source or supporting report to an assessment. It enforces
same-patient ownership, STORED status, confirmed extraction + exact version for
`OCR_SOURCE_REPORT`, and records `document_sha256_at_bind`. The
`assessment_document` composite FK targets Track 1's `assessment` table.

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
