# M2b — Synthetic Stage-Aware Intake Safety (prototype only)

**Status:** Engineering proposal for independent review. **No production endpoint, medical recommendation, model artifact, patient records, or real-data processing.** Gate PT P-3 remains CLOSED. This module does **not** update any existing OpenAPI version, backend mock, React/Flutter screen, persistence or inference route.

## Why this small implementation exists

The merged real local DA-A2 descriptive audit found that a five-input *resting-assessment* source panel is jointly recorded in 303/303 Cleveland, 292/294 Hungary, 120/123 Switzerland and 143/200 VA cases (under the explicit hypothetical zero-unavailable measurement rule). Source data availability is **not** predictive accuracy, case representativeness or justification to use those variables in a fitted model. The [research protocol v0.1](../../docs/research/gate-da/15_ai_model_development_evaluation_protocol_DRAFT.md) specifies these fields as *prospective candidates for a separate signed clinical protocol*, not yet selected training features.

The object in `synthetic_stage_validator.py` validates **synthetic data and field-level formatting only**; it does not inspect cohort labels, rank inputs, fit preprocessing, or approve an ML schema. It is never invoked by the existing `/v1/predictions/cad-tabular` API.

## Controlled stage bundles

- `history_only`: age (years), sex (source 0/1), cp (source 1–4)
- `resting_assessment`: above + trestbps (mmHg) + restecg (source 0–2)
- `resting_plus_labs`: above + chol (mg/dL) + fbs (source 0/1)
- `includes_exercise_tests`: above + thalach (bpm) + exang (0/1) + oldpeak (signed numeric) + slope (1–3)

The synthetic fixture must specify an explicit `synthetic: true` flag and exact `stage`, `features`, `units`, and `missing_reasons` keys. At least the three basic history fields must be non-null. An optional field with `None` requires an explicit reason (`not_measured`, `not_available_at_time`, `unknown`) and no unit. Positive physiological measurements must not silently receive zero as a clinical measurement; however categorical zero and `oldpeak=0` are valid, and negative oldpeak remains allowed rather than auto-clipped. Submitted units must match the explicitly named source conventions. The validator does **not** perform unit conversions, imputation, value repair or prediction.

**Hard rejection:** `ca`, `thal`, `num`, `Cath`, `LAD`, `LCX`, `RCA`, patient identifiers, site labels, monitoring/wearable fields, unexpected feature names, and fields from a later stage all fail closed by an exact per-stage allowlist. Messages do not echo submitted values.

**Safety:** The returned immutable `SyntheticIntakeReview` includes **field names, missing reasons, completeness and fixed `NO_PREDICTION_GATE_PT_CLOSED` status only**. It contains no submitted numerical/categorical measurements, CAD score, feature ranking, explanation, patient ID or record-level data. Passing `synthetic=true` alone does not prove input data are actually synthetic; the caller must **never feed real patient data** into this prototype.

## Run synthetic unit tests only

```powershell
& "E:\CardioAssist_PR11_Audit_Venv\Scripts\python.exe" -m pytest tests/audit/test_synthetic_stage_intake_safety.py -q -W error
```

GitHub audit-toolchain CI runs this under supported Python versions. All examples and tests contain invented, synthetic fixture values. There are no new dependencies, source dataset reads, or model fitting.

## Next engineering slice (requires its own authorization and review)

Propose a versioned stage-aware intake JSON Schema and contract fixtures for the clinician website, independent of the current MOCK_SYNTHETIC CAD prediction endpoint and the wearable/monitoring track; approval of this stand-alone Python prototype does **not** automatically approve an API change or a production patient-data flow.

## Verification status

This prototype supports **PP-02** (synthetic-only safety validation) from [protocol draft §Implementation work packages](../../docs/research/gate-da/15_ai_model_development_evaluation_protocol_DRAFT.md). Statistical adequacy, clinical predictor timing, source-target harmonization, evidence-based zero coding, model training, external validation, calibration and medical UI copy remain separate unapproved decisions.
