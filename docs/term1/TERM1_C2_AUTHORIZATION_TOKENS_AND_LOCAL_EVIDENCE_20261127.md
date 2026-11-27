# CardioAssist-AI Term 1 — Candidate A Authorization Tokens & Owner-Local Evidence Procedure

**Date:** 2026-11-27 (UTC / Africa/Cairo) — **Revision 2**
**Status:** `PROPOSED — ALL GATES (A1, A2, A3, B, RD-09-TERM1-EDU-DEMO-V1, EXC-TERM1-OCR-DEMO-V1) REMAIN PENDING`
**Important:** Previous Candidate B synthetic tokens (`AUTHORIZE-TERM1-AI-B-DEV`, `ACTIVATE-TERM1-AI-B-LOCAL-DEMO`, etc. in `TERM1_AI_READINESS_MATRIX.md` §3) are **superseded and MUST NOT be posted or reused** for Candidate A. Neither this document nor any PR comment by an agent ratifies any gate.

---

## 1. Literal Target Bundle & Contract Constants (From `ai/diagnostic_scope.py`, `ai/packaging.py` & `ai/panels.py`)

All values below are verbatim from the repository (`ai/diagnostic_scope.py::RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES`, `ai/packaging.py::REQUIRED_SIBLING_FILES`, and `ai/panels.py::DA_A2_RESTING_PANEL`):

| Attribute | Exact Literal Value |
|---|---|
| `model_id` | `cai_real_da-a2_da_a2_resting_v1` |
| `model_version` | `0.2.0` |
| `protocol_id` | `CAI-D047-CLEVELAND-EXPLORATORY-V1` |
| `execution_profile` | `CLEVELAND_D047_FROZEN_V1` |
| `model_family` | `l2_logistic_regression` |
| `selected_c` | `10.0` |
| `dataset_id` | `DA-A2` |
| `panel_id` | `da_a2_resting_v1` |
| `panel_version` | `1.0.0` |
| `panel_contract_sha256` | `c18ad4cd2cf08f6fefb2e340573760da7000bc1d8eb4ad38783b873c018e57b8` |
| `ordered_feature_names` | `("age", "sex", "cp", "trestbps", "restecg")` |
| `expected_bundle_dir_name` | `cai_real_cleveland_d047_20261027T070610Z_deffa577` |
| `expected_manifest_sha256` | `089f931be27be67606b9d2622beea54208976f1743a70909029619f50a6e5d4a` |
| `expected_source_sha256` | `a74b7efa387bc9d108d7d0115d831fe9b414b29ae7124f331b622b4efa0427c8` |
| `REQUIRED_SIBLING_FILES` (`ai/packaging.py`) | `model.joblib` (contains `selected_model_family`, `execution_profile`, `estimator`, `fold_ensemble`), `preprocessing.json`, `calibration.json`, `shap_background.json`, `evaluation_summary.json`, `protocol.md` (plus `manifest.json`, `POST_RUN_ACCEPTANCE.json`, refusal on `QUARANTINED_DO_NOT_TRUST.json`) |
| Historical PR #63 / #64 baseline | `ad30acc7b05705bf45436d4be95aa1d6a616f8ed` (`G2`), `87bccd6d3ef2331f1e2b2ba8905f34366734538d` (`I2`), `2b85bdff255266d216eb25f097b3eaa49d771e34` (PR #64 offline-only merge — **never repurposed**) |

---

## 2. Draft Owner & Independent-Reviewer Ratification Tokens (`PENDING`)

None of the tokens below is active until explicitly posted by the human owner (and independent verifier for `A2`) on the corresponding stage PR after inspecting the exact code, digests, and local evidence. **`operation=verify_only` (`A2`) and `operation=activate` (`A3`) are strictly separated so `A2` verification does not depend circularly on `A3`.**

### 2.1 Gate `A1` — Candidate A Reuse Architecture, Scope Exceptions & `verify_only` Authorization

- **Preconditions:**
  1. `C2_SAFE_SCOPE` infrastructure and bounded Document/OCR specs reviewed on `delivery/term1-prototype`.
  2. Agreement on isolated local worker subprocess architecture (`POST /internal/ai/v1/verify-bundle` vs `POST /internal/ai/v1/infer`), `RD-09-TERM1-EDU-DEMO-V1`, and `EXC-TERM1-OCR-DEMO-V1` (unless `A1` specifies manual-only first).
  3. Zero modification to `ai/diagnostic_scope.py`, `ai/research_registry.py`, or `backend/app/inference/`.
- **Exact Draft Owner Token:**
  ```text
  AUTHORIZE-TERM1-A1-REAL-CLEVELAND-REUSE-V1: Authorize isolated local-worker adapter design (operation=verify_only vs operation=activate) and owner-local verification for historical Cleveland D-047 bundle cai_real_cleveland_d047_20261027T070610Z_deffa577 (model cai_real_da-a2_da_a2_resting_v1 v0.2.0, panel da_a2_resting_v1 v1.0.0) on delivery/term1-prototype under proposed RD-09-TERM1-EDU-DEMO-V1. Educational local demo only; no retraining, no clinical use, no Gate PT closure, no legacy mock or offline diagnostic scope change.
  ```

### 2.2 Gate `A2` — Independent Local Bundle & Same-Model Explanation Verification (`verify_only`, Zero Runtime Persistence)

- **Preconditions (must all be executed locally under `operation=verify_only` and independently verified before `A2`; agent self-claims do not satisfy `A2`):**
  1. Inspect local `manifest.json` (`schema_version == "cardioassist.ai.research_bundle/v1"`), `POST_RUN_ACCEPTANCE.json` (`cardioassist.ai.bundle_acceptance/v1`), absence of `QUARANTINED_DO_NOT_TRUST.json` (`cardioassist.ai.bundle_quarantine/v1`), NTFS DACL / private permissions, and valid `local_producer_attestation` (`hmac_sha256_v1`).
  2. Verify exact `manifest.json` SHA-256 equals `089f931be27be67606b9d2622beea54208976f1743a70909029619f50a6e5d4a`, `source_sha256` equals `a74b7efa387bc9d108d7d0115d831fe9b414b29ae7124f331b622b4efa0427c8`, and all 6 literal sibling files (`model.joblib`, `preprocessing.json`, `calibration.json`, `shap_background.json`, `evaluation_summary.json`, `protocol.md`) match `manifest.json`.
  3. Inspect exact Python / `numpy` / `scipy` / `scikit-learn` / `joblib` / `threadpoolctl` producer metadata inside `manifest.json` and compare against the isolated worker venv (`research/experiments/requirements.txt` pins: `numpy==1.26.4`, `scipy==1.15.3`, `scikit-learn==1.6.1`, `joblib==1.4.2`, `threadpoolctl==3.6.0`). Stop and report to owner if producer pins diverge.
  4. Verify same-model scores (`calibrated_research_score`, `calibrated_log_odds`), grouped LinearSHAP (`sum_check_passed == True`, `max_abs_discrepancy` within tolerance vs independent `exact_coalition_shapley_oracle`), and `LimeQualityPolicy` verdict on deterministic synthetic fixtures — plus repeatability across repeated runs, negative tamper/quarantine refusal tests, and zero clinical `inference_result` persistence.
- **Exact Draft Independent Verifier / Owner Token:**
  ```text
  VERIFY-TERM1-A2-REAL-CLEVELAND-BUNDLE-V1: Confirmed independent local verification (operation=verify_only) of cai_real_cleveland_d047_20261027T070610Z_deffa577 at commit <EXACT_40_HEX_SHA>: producer pins compatible, manifest/source and all 6 sibling SHA-256s matched, HMAC/DACL/POST_RUN_ACCEPTANCE verified, same-model score + independent LinearSHAP oracle + LIME quality repeatable, and tamper/quarantine refusals passed with zero runtime persistence. Sanitized metadata-only report attached.
  ```

### 2.3 Gate `A3` — Controlled Local-Demo Inference Activation (`operation=activate`, Bound to `A1` + `A2` + Executable Revision)

- **Preconditions:** `A1` and independent `A2` both completed; `git HEAD == <A2_40_HEX_SHA>` with unaltered `ai/diagnostic_scope.py`; C2 isolated worker adapter code reviewed (`tests/backend` proving fail-closed disabled default, zero `backend.app.main` import of `ai/`, C0 §7.3 CAS fencing, and `authorization_withdrawn` handling); exact permitted `source_kind` set specified.
- **Exact Draft Owner Token (Manual + OCR-Confirmed Demo Intake):**
  ```text
  ACTIVATE-TERM1-A3-REAL-CLEVELAND-LOCAL-DEMO-V1: Ratify RD-09-TERM1-EDU-DEMO-V1 and EXC-TERM1-OCR-DEMO-V1 and authorize operation=activate on delivery/term1-prototype at commit <EXACT_40_HEX_SHA> (matching A2 commit and A1 architecture) for bundle cai_real_cleveland_d047_20261027T070610Z_deffa577 (manifest_sha256=089f931be27be67606b9d2622beea54208976f1743a70909029619f50a6e5d4a, source_sha256=a74b7efa387bc9d108d7d0115d831fe9b414b29ae7124f331b622b4efa0427c8, model=cai_real_da-a2_da_a2_resting_v1 v0.2.0) exclusively for server-assigned source_kind in {synthetic_demo_patient_manual, synthetic_demo_ocr_confirmed} via verified local provenance. Educational local demonstration only; legacy /v1/predictions/cad-tabular remains MOCK_SYNTHETIC; zero clinical use.
  ```
  *(If the owner wishes to activate manual intake before OCR-to-inference, omit `EXC-TERM1-OCR-DEMO-V1` and `synthetic_demo_ocr_confirmed` from the `A3` token; OCR remains attachment + draft confirmation only.)*

### 2.4 Gate `B` — Patient-Facing Educational Provisional Score & Explanation Display

- **Preconditions:** `A3` active; redaction tests verify status-only projection before `B`, **no `exploratory_threshold` or `exploratory_above_threshold` flag exposed to patients**, no `%` personal risk formatting, no clinical triage/recommendation wording, and `"Reviewed"` UX label paired with actual `review_state` in C3.
- **Exact Draft Owner Token:**
  ```text
  AUTHORIZE-TERM1-B-PATIENT-PROVISIONAL-SCORE-DISPLAY-V1: Authorize display of calibrated_research_score ([0,1] educational scale, never personal risk percentage and never exploratory_threshold/above-threshold flags), grouped LinearSHAP, and quality-certified LIME (or WITHHELD_QUALITY_NOT_MET) to the authenticated owner patient on S2 GET /v1/assessments/{assessment_id} at commit <EXACT_40_HEX_SHA> with the exact reviewed educational provisional notice. Not clinical care, diagnosis, or Gate PT closure.
  ```

---

## 3. Owner-Local Verification & Sanitized Evidence Procedure

When executing local verification on Windows (after `A1` and C2 code PR exist):

1. **Zero Private Artifacts in Git/CI:** Never copy `cai_real_cleveland_d047_20261027T070610Z_deffa577`, `local_bundle_hmac_v1.key`, `shap_background.json`, or private datasets into the Git working tree, `.venv`, or GitHub PR comments. Keep them under an owner-controlled NTFS-hardened folder outside the repo (e.g., `E:\CardioAssist-Local-Private\trusted_bundles\...`).
2. **Evidence To Return (Sanitized Metadata Only):**
   - Exact repo `HEAD` 40-hex SHA and clean `git status --porcelain` before/after.
   - Python version + isolated worker `pip freeze` (verifying `numpy`, `scipy`, `scikit-learn`, `joblib`, `threadpoolctl`) and `pip check`.
   - Literal bundle identity verification output (`operation=verify_only`, `bundle_dir_name`, `manifest_sha256`, `source_sha256`, all 6 sibling SHA-256s, `panel_version=1.0.0`, `panel_contract_sha256`, `producer_authenticated=True`, `post_run_acceptance=True`).
   - Aggregate/synthetic test-vector checks: `raw_model_score`, `calibrated_research_score`, `calibrated_log_odds`, `shap_sum_check_passed=True`, `shap_max_abs_discrepancy`, `lime_quality_status`, independent `A2` oracle agreement, repeatability match across 2 identical runs, and PASS for tamper/`QUARANTINED_DO_NOT_TRUST.json`/missing-key/revoked-assignment negative controls.
   - Local OCR verification output (after `DOC1`–`DOC7` exist, executed in `.venv-ocr-worker` with zero AI secret access): Tesseract version, `pdfminer.six` text-PDF extraction check + `pypdfium2`/Tesseract PNG/JPEG raster OCR check on trusted project-generated `CAI-DEMO-RESTING-CARDIAC-REPORT-V1`, `CAI-DEMO-UNRELATED-LABS-V1` non-ingestion check, conflict/low-confidence fallback check, and active-PDF/spoofed-fixture/magic-byte rejection check.
   - C1 + C2 + contracts regression counts with `-W error` and preservation DB upgrade/restart parity.
