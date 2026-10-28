# AI-8 UCI-412 Research Demo — Runnable Runbook

**Status:** engineering demonstration for the open AI-8 PR
[#66](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/66).
**Classification:** `SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE`. Every input row is
generated in-process; no patient record, workbook, real bundle or secret is
read. Every score is a `RESEARCH_ONLY_NOT_INDIVIDUAL_CLINICAL_RISK` value, not a
medical probability. The demo cannot enable clinical serving.

---

## 1. What the demo proves

A single command runs the complete source-specific UCI-412 synthetic path and
prints an observable, reproducible result. It adds **no new training or
inference engine** — `ai/uci412_demo.py` orchestrates the existing
`ai/uci412_research.py` build and the Deliverable D intake validator.

The 12 reported stages map to the required demonstration sequence:

| Stage | Demonstration requirement |
|---|---|
| `1_synthetic_cohort_generation` | Deterministic synthetic UCI-412 records (separate dev/test seeds) |
| `2_route_and_panel_binding` | Selected route and the exact ordered 16-feature panel + contract hash |
| `3_feature_contract_validation` | Sample validated through the intake field contract and the panel contract |
| `4_research_model_identity` | Model id, version, selected family and execution profile |
| `5_raw_model_score` | Raw model score and the scale SHAP explains |
| `6_calibrated_research_score` | Calibrated research score + calibrated log-odds + interpretation |
| `7_prediction_provenance_and_target` | Target id/definition hash, serving eligibility flags |
| `8_shap_explanation` | Genuine model-based SHAP, true explained scale, additivity check |
| `9_lime_explanation` | LIME quality verdict, fidelity and stability |
| `10_bundle_verification` | Authenticated RESEARCH_ONLY bundle status and artifact count |
| `11_invalid_input_rejection` | A real validator rejection (not a hardcoded message) |
| `12_held_out_synthetic_evidence` | Held-out synthetic metrics, explicitly not external validation |

## 2. Environment and dependencies

Python 3.11/3.12. Create an isolated environment and install the pinned
experiment + audit + UCI-412 requirements (the demo also runs the backend/
contract pins used by the full CI matrix, but the demo itself only needs the
experiment stack):

### Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r research/experiments/requirements.txt `
                      -r research/audit/requirements.txt `
                      -r research/uci412/requirements.txt
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r research/experiments/requirements.txt \
                      -r research/audit/requirements.txt \
                      -r research/uci412/requirements.txt
```

The demo is strictly offline (no network, no paid service, budget **$0**).

## 3. Exact commands

From the repository root, with the virtual environment active:

```bash
# Fast smoke demo (default): reduced nested-CV budget, ~5-15 seconds
python -m ai uci412-demo

# Human-readable console report instead of JSON
python -m ai uci412-demo --format text

# Full default nested-CV budget (4 outer x 3 inner folds, n=240/120), ~30-60 s
python -m ai uci412-demo --budget full

# Retain the generated private artifacts instead of using an auto-deleted temp dir
python -m ai uci412-demo --work-dir "$HOME/ai8_demo_private" --format text
```

Windows PowerShell equivalents use the same flags; quote the work directory:

```powershell
python -m ai uci412-demo --format text
python -m ai uci412-demo --budget full --work-dir "$env:USERPROFILE\ai8_demo_private"
```

An unknown `--budget` value is rejected by argparse with exit code `2`. Any
fail-closed pipeline error also returns exit code `2` and emits a
`FAIL_CLOSED` JSON object on stderr; success returns `0`.

## 4. Example input structure

The demo constructs two distinct, clearly-labelled synthetic inputs.

**(a) Model-input envelope** produced by the registered cohort builder
(`build_synthetic_uci412_basic_clinical_cohort`); this is the shape validated by
the strict per-record context guard and the panel contract:

```json
{
  "synthetic": true,
  "panel_id": "da_a1_basic_clinical_v1",
  "features": {
    "Age": 53.0, "Sex": 1, "BMI": 26.4, "DM": 0, "HTN": 1,
    "Current Smoker": 0, "EX-Smoker": 0, "FH": 0, "DLP": 1,
    "BP": 128.0, "PR": 78.0, "Typical Chest Pain": 0,
    "Atypical": 0, "Nonanginal": 0, "Exertional CP": 1, "Dyspnea": 0
  },
  "units": {"Age": "years", "BMI": "kg/m^2", "BP": "mmHg", "PR": "beats/min"},
  "missing_reasons": {},
  "context": {"track": "A", "source": "structured_synthetic_research"}
}
```

**(b) Source-shaped intake payload** for the Deliverable D field contract
(text tokens for the six text-binary fields, bare 0/1 integers for the six
numeric-binary fields, and an explicit acquisition-channel declaration). It is
accepted as a fixture but returns
`NO_RESULT_NO_CAD_PROBABILITY_COMPUTED` — the intake contract never scores.

The strict context contract requires, with no defaults: top-level boolean
`synthetic=true`; a mapping `context` containing exactly `track="A"` and
`source="structured_synthetic_research"`; and optional
`context.real_data` that, when present, must be the boolean `false`.

## 5. Example output structure

### Console (`--format text`)

Deterministic smoke-budget output (abbreviated):

```
==============================================================================
CardioAssist AI-8 — UCI-412 synthetic research demo
==============================================================================
Command            : python -m ai uci412-demo  (budget=smoke)
Overall status     : PASSED
Route / panel      : da_a1_basic_clinical_v1 / da_a1_basic_clinical_v1
Evidence marker    : SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE
Score meaning      : RESEARCH_ONLY_NOT_INDIVIDUAL_CLINICAL_RISK
Report SHA-256     : 6e5707be...
------------------------------------------------------------------------------
[PASSED] 3_feature_contract_validation
    - intake_review_status: ACCEPTED_SYNTHETIC_FIXTURE_CONTRACT_ONLY
    - intake_result_state: NO_RESULT_NO_CAD_PROBABILITY_COMPUTED
    - cad_probability_computed: False
    - panel_validation_matrix_shape: [60, 16]
[PASSED] 5_raw_model_score
    - raw_model_score: 0.755186
    - explained_scale: raw_model_probability
[PASSED] 6_calibrated_research_score
    - calibrated_research_score: 0.738384
    - calibrated_log_odds: 1.037588
    - score_interpretation: RESEARCH_ONLY_NOT_INDIVIDUAL_CLINICAL_RISK
[PASSED] 8_shap_explanation
    - explained_quantity: raw_model_score
    - scale: raw_model_probability
    - sum_check_passed: True
    - additive_on_calibrated_probability: False
    - attribution_count: 16
[PASSED] 9_lime_explanation
    - quality_status: ACCEPTABLE_LOCAL_APPROXIMATION
    - is_reliable_for_interpretation: True
    - stability_assessed: True
[PASSED] 11_invalid_input_rejection
    - rejected: True
    - error_code: uci412_synthetic_context_rejected
...
Summary: 12/12 stages succeeded
```

### Machine-readable (`--format json`, default)

Top-level keys: `demo`, `command`, `status`, `budget`, `evidence_marker`,
`research_only_interpretation`, `route_id`, `panel_id`,
`report_deterministic_sha256`, `stage_results` (the 12 ordered stages above),
`summary`, `invalid_input_demo`, `limitations`, `reproduction`. The JSON is
finite (serializable with `allow_nan=False`) and contains **no absolute
filesystem path, signing-key material or traceback**.

## 6. Expected artifacts and paths

* **Default (no `--work-dir`):** an isolated private temporary directory is
  created and **deleted when the demo finishes**; nothing remains on disk.
* **With `--work-dir <dir>`:** artifacts are retained under
  `<dir>/private_keys/local_bundle_hmac_v1.key` and
  `<dir>/trusted_bundles/synthetic_research_bundle_da_a1_basic_clinical_v1_<id>/`
  containing six authenticated files: `model.joblib`, `preprocessing.json`,
  `calibration.json`, `shap_background.json`, `evaluation_summary.json`,
  `protocol.md`, plus `manifest.json`. Keep this directory private; never commit
  it (it is git-ignored / outside the repository by convention).
* The console/JSON output references bundles only by logical name and SHA-256
  hashes, never by absolute path.

## 7. Reproducing the results

Both budgets are deterministic. The smoke profile uses development seed
`20261028` and held-out seed `20261029` (`seed + 1`). Running
`python -m ai uci412-demo` twice produces the same
`report_deterministic_sha256`; the full budget likewise reproduces its hash.
Timing fields and local paths are excluded from the hash. A regression test
(`test_demo_is_reproducible_across_separate_runs`) asserts this.

## 8. The invalid-input check is a genuine rejection

Stage 11 takes an otherwise valid synthetic record, removes its explicit
`context.source`, and calls the real
`validate_uci412_synthetic_cohort` guard. The guard — which reuses the tested
AI-7 `_validate_synthetic_input_context` policy — raises
`Uci412ResearchGovernanceError` with code
`uci412_synthetic_context_rejected` and rejection token
`unsupported_input_source`. The demo captures and reports the actual exception;
it does not print a hardcoded rejection. The same guard rejects missing
context/track/source, `real_data=true`, non-boolean flags, Track B, OCR,
wearable, patient-upload and clinician-record sources.

## 9. Software demo vs real clinical evidence

* All rows are synthetic software fixtures; the held-out cohort is drawn from
  the **same generative process** as development and is **not** independent
  external clinical validation (`not_external_clinical_validation: true`).
* SHAP for the selected tree model honestly explains the **raw model score on
  the raw probability scale** (`additive_on_calibrated_probability=false`); it
  is never relabelled as a calibrated-probability decomposition or a causal
  claim.
* LIME prints its actual quality verdict and fidelity numbers; a non-acceptable
  verdict would be reported, not hidden.
* A calibrated research score is not a patient-specific clinical probability;
  calibration on real populations remains unestablished.
* The bundle stays `RESEARCH_ONLY` with `approved_for_serving=false`,
  `clinical_use_authorized=false` and `pooled_cohorts=false`. Gate PT P-3 stays
  closed; this demo authorizes no real-data run.

## 10. Smoke vs full budget

| | `smoke` (default) | `full` (`--budget full`) |
|---|---|---|
| Development / held-out n | 120 / 60 | 240 / 120 |
| Outer x inner folds | 3 x 2 | 4 x 3 |
| Purpose | fast, deterministic software check | full default nested-CV exercise |
| Evidence grade | E5 synthetic fixture | E5 synthetic fixture |

Neither budget produces clinical evidence; the distinction is computational
budget only, not scientific validity.
