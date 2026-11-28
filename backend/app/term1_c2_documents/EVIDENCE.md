# Track 2 C2 SAFE_SCOPE — genuine local OCR evidence

Status: **PROPOSED — NOT APPROVED, NOT DEPLOYED.** Synthetic fabricated fixtures
only; no real patient data. All extraction below was produced by the **real**
engines (pdfminer.six text layer; pypdfium2 + Pillow + native Tesseract raster),
never mocked or hardcoded.

## Engine + dependency pins
* Native Tesseract **5.4.1** (`/home/user/ocr-native/prefix/bin/tesseract`,
  `eng.traineddata`), built from source ($0; no cloud/paid API).
* `pdfminer.six==20250506`, `pypdfium2==4.30.0`, `Pillow==11.2.1`,
  `pytesseract==0.3.13` (see `backend/requirements-ocr-worker.txt`).
* Rasterization 200 DPI; raster fixtures 1654×2339 px; PDF page 595×842 pt.

## Actual extraction outputs (real run, all 10 allowlisted fixtures)

| File | SHA-256 (first 16) | Mode | Engine | Status | Extracted values | Mean OCR conf |
|---|---|---|---|---|---|---|
| resting_text.pdf | 636377381872fea6 | PDF_TEXT | pdfminer 20250506 | EXTRACTED_DRAFT | age 54, sex 1, cp 2, trestbps 130, restecg 0 | — (text layer) |
| resting_raster.pdf | dea8eff2c87dd78e | RASTER_OCR | tesseract 5.4.1 | EXTRACTED_DRAFT | age 54, sex 1, cp 2, trestbps 130, restecg 0 | 0.925 |
| resting.png | 1c1145621efb70b3 | RASTER_OCR | tesseract 5.4.1 | EXTRACTED_DRAFT | age 54, sex 1, cp 2, trestbps 130, restecg 0 | 0.927 |
| resting.jpg | 14febbfcb6b03ce2 | RASTER_OCR | tesseract 5.4.1 | EXTRACTED_DRAFT | age 54, sex 1, cp 2, trestbps 130, restecg 0 | 0.924 |
| resting_missing_text.pdf | c747ab5ca9771112 | PDF_TEXT | pdfminer 20250506 | NEEDS_MANUAL_REVIEW | age 54, sex 1, cp 2, trestbps 130, restecg **MISSING** | — |
| resting_conflict_text.pdf | 1ca14d1aae009471 | PDF_TEXT | pdfminer 20250506 | NEEDS_MANUAL_REVIEW | age **CONFLICT**, sex 1, cp 2, trestbps 130, restecg 0 | — |
| labs_text.pdf | aeca6572d227ce4e | PDF_TEXT | pdfminer 20250506 | UNSUPPORTED_TEMPLATE | 8 unrelated_lab_* fields, all record-only (null) | — |
| labs_raster.pdf | 3de88742db7be48a | RASTER_OCR | tesseract 5.4.1 | UNSUPPORTED_TEMPLATE | 8 unrelated_lab_* fields, all record-only (null) | 0.928 |
| labs.png | 1f3f90d890b8b51d | RASTER_OCR | tesseract 5.4.1 | UNSUPPORTED_TEMPLATE | 8 unrelated_lab_* fields, all record-only (null) | 0.926 |
| labs.jpg | d4e6394995257a4a | RASTER_OCR | tesseract 5.4.1 | UNSUPPORTED_TEMPLATE | 8 unrelated_lab_* fields, all record-only (null) | 0.933 |

The five resting fields use exact source category codes and explicit units
(`age` years, `trestbps` mmHg; `sex`/`cp`/`restecg` categorical codes). The
unrelated-lab template is recognized but **never** produces resting panel input
(`UNRELATED_IGNORED` / `UNRELATED_NON_MODEL_FIELD`, status `UNSUPPORTED_TEMPLATE`,
and DOC7 refuses it with `unsupported_template_for_intake`).

## Reproduce
```
TESSDATA_PREFIX=/home/user/ocr-native/prefix/share/tessdata \
CARDIOASSIST_TESSERACT_CMD=/home/user/ocr-native/prefix/bin/tesseract \
.venv-ocr-worker/bin/python -m pytest tests/backend/c2/ -q
```

## Test results (this branch)
* `tests/backend/c2/` — **110 passed** (genuine extraction, DOC1–DOC7 HTTP
  lifecycle, admission/security, quota + crash recovery + concurrency,
  confirmation validation, immutability triggers, worker IPC/isolation,
  contract sync, panel-contract SHA, migration-08 up/down guard, resource limits).
* C1 regression — **300 passed**; legacy backend — **406 passed** (run with the
  pending-integration migration 08 staged aside so the C1 alembic chain resolves;
  08 restored afterward). No C1/shared code was modified.
* `PANEL_CONTRACT_SHA256` verified equal to
  `ai.panels.DA_A2_RESTING_PANEL.contract_sha256`
  (`c18ad4cd2cf08f6fefb2e340573760da7000bc1d8eb4ad38783b873c018e57b8`).

## Native OCR availability
Native Tesseract is available in this sandbox, so genuine OCR ran (not NOT_RUN).
On an owner-local Windows host without it, follow the runbook in
`docs/term1/TERM1_C2_AUTHORIZATION_TOKENS_AND_LOCAL_EVIDENCE_20261127.md`; the
genuine-OCR tests are skipped with an explicit NOT_RUN marker rather than mocked.
