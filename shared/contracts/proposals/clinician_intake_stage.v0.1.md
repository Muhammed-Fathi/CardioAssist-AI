# Clinician Intake Stage Contract — v0.1 Design Proposal

**Status:** DESIGN PROPOSAL ONLY — not approved, not implemented, not deployed.
**Scope:** future clinician-entered, pre-angiography intake-stage data collection.
**No endpoint path is assigned.** `clinician_intake.stage.v0.1` is a proposal
identifier, not an API version served by this repository.

This proposal is intentionally independent of the existing `/v1` OpenAPI
schemas and runtime. Its examples are fabricated synthetic software fixtures;
they are not real clinical measurements, patient records, medical advice, CAD
predictions, or evidence of model performance. The future research objective is
source-referenced, cross-sectional CAD-presence classification at a
pre-angiography decision point—not prediction of future 30-day cardiovascular
events. The fields below are candidates for engineering review, not an
approved model feature set.

## 1. Proposed envelope and stage rules

All keys and semantics here are proposed. If implemented later, the contract
must reject unknown properties rather than silently ignoring them.

| Field | Type | Required | Proposed meaning |
|---|---|---:|---|
| `contract_version` | string | yes | Exact value `clinician_intake.stage.v0.1`; unsupported versions fail explicitly. |
| `fixture_context` | string | yes in this proposal | Exact value `SYNTHETIC_ONLY`; the payload is a test fixture, not an actual patient submission. This marker is not proof of provenance. A real-data workflow would require a separately authorized contract and data-custody design. |
| `stage` | enum string | yes | One of the four stage identifiers below; it constrains the allowed feature names. |
| `features` | object | yes | Stage-eligible source values. No target, identifier, site, angiography, or monitoring fields. |
| `units` | object | yes | Exact units for present numeric fields with a declared source convention; no unit conversion. Categorical fields and `oldpeak` have no unit entry in v0.1. |
| `missing_reasons` | object | yes | Exactly one reason for every optional stage field that is absent or null; no reason for measured fields. |

`age`, `sex`, and `cp` are the required, non-null history fields at every
stage, matching the existing synthetic intake validator. Fields added by a
later stage are optional measurements: the stage records the collection
bundle, not an instruction to order a test. Every optional field in the chosen
stage is either a value, an explicit `null`, or omitted with explicit missing
semantics. A field outside the selected stage is rejected.

Supported cumulative stage bundles:

| Stage | Fields permitted in the stage | Required non-null | Optional stage measurements |
|---|---|---|---|
| `history_only` | `age`, `sex`, `cp` | `age`, `sex`, `cp` | none |
| `resting_assessment` | history + `trestbps`, `restecg` | `age`, `sex`, `cp` | `trestbps`, `restecg` |
| `resting_plus_labs` | resting + `chol`, `fbs` | `age`, `sex`, `cp` | `trestbps`, `restecg`, `chol`, `fbs` |
| `includes_exercise_tests` | labs + `thalach`, `exang`, `oldpeak`, `slope` | `age`, `sex`, `cp` | all other stage fields |

`restecg` and `trestbps` are in the resting candidate panel. Labs and exercise
tests are separate optional stages. Exercise-stage values may only be
collected when an exercise test already occurred before the intended decision
point; the form must not prompt a patient to undergo a test merely to satisfy a
model input. `thal` is excluded from this first proposal pending its own
measurement-time review.

## 2. Proposed field registry

Types and unit labels below describe a synthetic UCI-45-style source
representation. They are not a ratified clinical dictionary, ranges, or
cross-dataset harmonization. Categorical code order is fixed as shown for
encoding; the numbers represent nominal source codes and must not be treated
as an ordinal scale.

| Field | JSON value type | Unit token when measured | UCI-45-style source coding / validation | Stage / availability |
|---|---|---|---|---|
| `age` | number | `years` | Positive finite value (source values are conventionally integer-like); core history field. | All stages; required. |
| `sex` | integer enum | none | UCI-45 source codes `[0, 1]` (`0` female, `1` male); this mapping is not presumed for other datasets. | All stages; required. |
| `cp` | integer enum | none | UCI-45 source codes `[1, 2, 3, 4]` (typical, atypical, non-anginal, asymptomatic); nominal, not ordinal; core history field. User-facing labels still require clinician review. | All stages; required. |
| `trestbps` | number | `mmHg` | Positive finite measurement. A value of zero is unavailable under this prototype and is rejected as a measurement. | Resting stage onward; optional. |
| `restecg` | integer enum | none | Source codes `[0, 1, 2]`; nominal. | Resting stage onward; optional. |
| `chol` | number | `mg/dL` | Positive finite measurement. A value of zero is unavailable under this prototype and is rejected as a measurement. | Lab stage onward; optional. |
| `fbs` | integer enum | none | Source codes `[0, 1]`; UCI-45 `1` denotes the documented fasting blood-sugar `>120 mg/dL` flag, not a continuous glucose measurement; zero is valid categorical data. | Lab stage onward; optional. |
| `thalach` | number | `bpm` | Positive finite measurement. | Exercise stage only; optional. |
| `exang` | integer enum | none | Source codes `[0, 1]`; zero is valid categorical data. | Exercise stage only; optional. |
| `oldpeak` | number | **not asserted** | Finite signed numeric source value. Both zero and negative values are preserved; no clipping or zero-as-missing rule. The source unit remains unresolved. | Exercise stage only; optional. |
| `slope` | integer enum | none | Source codes `[1, 2, 3]`; nominal, not ordinal. | Exercise stage only; optional. |

The `years`, `mmHg`, `mg/dL`, and `bpm` tokens are implementation conventions
for the synthetic UCI-45-style prototype. The contract does not perform unit
conversion or establish that a corresponding real-world source value is
available at a clinically acceptable time. No arbitrary maximum range is
introduced here; a future clinically reviewed dictionary must supply any
additional range constraints.

## 3. Missingness and zero semantics

Proposed missing reasons are exactly:

- `not_measured` — field was not measured;
- `not_available_at_time` — field was not available by the proposed decision time;
- `unknown` — source does not establish whether it was measured;
- `not_provided` — the optional stage field was omitted from the request.

Rules:

1. Required history fields cannot be omitted or null. An absent or null required
   field yields `422 missing_required_field`.
2. An optional field omitted from `features` must have
   `missing_reasons[field] = "not_provided"`. An optional explicit `null` must
   have one of `not_measured`, `not_available_at_time`, or `unknown`.
3. `missing_reasons` contains exactly the unavailable fields. A reason on a
   measured field, missing reason, extra reason, or `not_provided` on explicit
   null is rejected.
4. `units` contains exactly the non-null fields with declared physical units.
   A null/omitted measurement has no unit; categorical fields and `oldpeak`
   have no unit entry in v0.1. Mismatches fail; values are never converted.
5. Zero is data for source-coded categorical fields including `sex`, `restecg`,
   `fbs`, and `exang`; `oldpeak=0` is a valid numeric value. Zero for
   `trestbps` or `chol` is rejected as unavailable under this prototype rather
   than silently treated as an observed measurement. This is a conservative
   prototype safeguard, not a universal clinical coding rule; source-specific
   zero semantics remain a protocol decision.
6. Non-finite numeric values are rejected. Negative `oldpeak` is retained as
   provided for synthetic tests; its measurement meaning and unit require
   separate review. No imputation is performed by the intake contract.

## 4. Proposed error behavior

These are design-level error codes only. The current Python prototype raises a
safe `IntakeValidationError`; it is not an HTTP server and does not currently
emit any of these codes.

| HTTP (proposed) | Code | Trigger |
|---:|---|---|
| 400 | `malformed_request` | Non-object body, wrong field types, duplicate/unknown envelope properties, or malformed maps. |
| 400 | `unsupported_contract_version` | `contract_version` is not exactly `clinician_intake.stage.v0.1`. |
| 422 | `non_synthetic_fixture` | Fixture context is not `SYNTHETIC_ONLY` in this test-only proposal. |
| 422 | `unknown_stage` | Stage name is not one of the four supported values. |
| 422 | `unknown_field` | Predictor key is not in the registry, including target, identifier, site, angiography, or wearable/monitoring fields. |
| 422 | `field_not_available_for_stage` | A registered field is supplied before its declared stage. |
| 422 | `missing_required_field` | A core history value is absent or null. |
| 422 | `invalid_value` | Numeric value is non-finite, a protected zero measurement, or an invalid scalar type. |
| 422 | `unknown_category` | Integer code is outside the fixed categorical source-code set. No coercion is performed. |
| 422 | `unit_mismatch` | Missing, extra, or mismatched unit token; no conversion is attempted. |
| 422 | `missing_reason_required` | An omitted/null optional field lacks exactly one permitted reason. |
| 422 | `invalid_missing_reason` | Reason is unknown or inconsistent with omitted vs explicit-null semantics. |

Errors must not echo submitted measurement values or identifiers. The
synthetic preprocessing helper has a separately explicit test-only option to
encode an unknown integer category into a dedicated unknown indicator; it does
not change the proposed intake contract's default `unknown_category` rejection.

## 5. Synthetic-only request and response examples

These deliberately small values are invented software sentinels and are not
copied from any dataset or patient record. This is a **design example**, not a
working API request.

### Request example

```json
{
  "contract_version": "clinician_intake.stage.v0.1",
  "fixture_context": "SYNTHETIC_ONLY",
  "stage": "resting_plus_labs",
  "features": {
    "age": 10,
    "sex": 0,
    "cp": 4,
    "trestbps": 20,
    "restecg": 0,
    "chol": null,
    "fbs": 0
  },
  "units": {
    "age": "years",
    "trestbps": "mmHg"
  },
  "missing_reasons": {
    "chol": "not_measured"
  }
}
```

### Response example

```json
{
  "contract_version": "clinician_intake.stage.v0.1",
  "fixture_context": "SYNTHETIC_ONLY",
  "accepted": true,
  "stage": "resting_plus_labs",
  "present_fields": ["age", "sex", "cp", "trestbps", "restecg", "fbs"],
  "missing_fields_with_reason": [
    {"field": "chol", "reason": "not_measured"}
  ],
  "stage_complete": false,
  "prediction_status": "NO_PREDICTION_GATE_PT_CLOSED"
}
```

The response deliberately contains no submitted measurements, patient
reference, target, score, probability, explanation, or treatment text. An
invalid example should return only a safe error code and field path, never the
submitted value.

## 6. Compatibility, boundaries, and open decisions

- This artifact does not add or amend any `/v1` OpenAPI schema, endpoint,
  backend behavior, frontend screen, database migration, or model registry.
- The current `POST /v1/predictions/cad-tabular` remains the existing
  deterministic MOCK/SYNTHETIC CAD/XAI path with its placeholder schemas. This
  intake proposal is not wired to it and does not supply inputs or prediction
  outputs to it.
- `/v1/monitoring/observations` remains Track B. Wearable observations stay
  separate and are prohibited as CAD predictors. No monitoring field is
  accepted by this proposed stage allowlist.
- Future integration requires a separate maintainer authorization, a frozen
  Gate PT protocol, a versioned approved feature schema, and an explicit
  adapter contract. Any data-dependent imputation/encoding statistics must be
  fit within training folds only and then applied unchanged to their holdout;
  the current code demonstrates this rule only with fabricated synthetic
  fixtures.
- `ca`, `Cath`, `num`, `LAD`, `LCX`, `RCA`, angiographic measurements,
  identifiers, site labels, and wearable observations remain prohibited
  predictors. `thal` is excluded pending measurement-time review.
- UCI-412 and UCI-411 remain representations of the same 303-patient cohort.
  Do not pool them, count them as independent samples, or automatically
  harmonize labels. This proposal does not access either dataset.
- The scientific target remains angiography-referenced CAD presence, not a
  30-day event outcome. The initial five-field panel is only a prospective
  candidate, not a selected feature set.

**Approval boundary:** The maintainer must explicitly accept or revise this
proposal before any contract implementation is authorized. Even acceptance of
the proposal would not authorize real-patient processing, production API
changes, model fitting, or clinical use.
