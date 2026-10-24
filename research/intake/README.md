# M2b — Synthetic Stage-Aware Intake and Preprocessing (prototype only)

**Status:** Engineering proposal for independent review. This package validates
and transforms **synthetic software fixtures only**. It is not a production
endpoint, medical recommendation, model artifact, patient-record workflow, or
approved clinical contract. Gate PT P-3 remains **CLOSED**. Nothing here
updates `/v1` OpenAPI schemas, backend behavior, frontend applications,
persistence, migrations, or inference routes.

## R1 — Cleveland five-field research input mapping (PROPOSED, synthetic-only)

`cleveland_source_mapping.py` implements the versioned, explicitly **PROPOSED**
mapping specification
[`schemas/cleveland_resting_five_field_mapping.v0.1.json`](schemas/cleveland_resting_five_field_mapping.v0.1.json)
(`cleveland_resting_five_field.v0.1`, status `PROPOSED_NOT_APPROVED`) for the
five-field UCI-45 processed-Cleveland resting-assessment proposal
(`age`, `sex`, `cp`, `trestbps`, `restecg`), per
[Gate PT doc 12 §6](../../docs/research/gate-pt/12_dataset_selection_and_clinical_workflow_alignment_REVIEW_DRAFT.md)
and [doc 13](../../docs/research/gate-pt/13_r1_cleveland_five_field_input_mapping_SPECIFICATION_PROPOSED.md).

It is an offline, standard-library-only, deterministic validator for
**synthetic fixtures only**: it binds every payload to the registered source
triple (`UCI-45-processed-cleveland` / `DA-A2` / Track A) and the exact mapping
version; matches literal source codes (no label, token, boolean, float or
cross-dataset conversion); requires exact unit tokens; enforces the staged
missing-reason and zero semantics (valid categorical zero is data; a measured
`trestbps` of 0 is unavailable, per ED-DA-A2-01); rejects outcome-derived,
angiography/post-catheterization, timing-unreviewed (`thal`), identifier,
wearable/Track-B, other-dataset and out-of-scope fields with a stable category;
and returns a metadata-only review whose explicit result state is always
`NO_RESULT_NO_CAD_PROBABILITY_COMPUTED` — there is **no scoring, inference or
prediction path of any kind**. The JSON record and the frozen in-code
allowlists must agree or loading fails closed; a coherence test additionally
pins the five shared field conventions to the M2b validator below.
**Cleveland has NOT been selected as the final project dataset.**

## Implemented foundation

`synthetic_stage_validator.py` contains the exact stage allowlists, immutable
field definitions, fixed UCI-45-style categorical source-code order, positive
measurement guards, exact unit-token checks, and field-level missing reasons.
The required history fields are `age`, `sex`, and `cp`. Optional stage fields
may be explicit nulls with a measurement reason, or omitted with the distinct
`not_provided` reason. Categorical zero and `oldpeak=0` are values; zero for
`chol` or `trestbps` is rejected as a measured value. Negative `oldpeak` is
preserved and not clipped. `oldpeak` has no asserted unit in this prototype.

`synthetic_preprocessing.py` provides a model-independent, standard-library
preprocessor:

- Numerical/categorical definitions and source-code order are fixed by the
  registry, not inferred from a dataset.
- Categorical encoding is one-hot with a stable code order. Unknown integer
  codes fail by default; an explicit synthetic-test-only policy maps them to a
  separate unknown indicator, never to a known category or missing value.
- Numeric missing values are imputed with medians fit from synthetic training
  records only. Missingness bits and one-hot reason fields are retained in the
  transformed vector and its immutable metadata.
- Fitting accepts only one stage and has no holdout/evaluation input. Every
  record is validated with `synthetic: true`; labels, identifiers, sites,
  angiography fields, and wearables fail closed.
- Results are deterministic, immutable numeric vectors with no patient IDs,
  target, prediction, or explanation fields. Input objects are read-only.

The `synthetic: true` tag does not prove that data are synthetic. Never pass
real patient records, raw benchmark rows, or data-derived fixtures to this code.

## Stage bundles and candidate scope

- `history_only`: `age`, `sex`, `cp`
- `resting_assessment`: above + `trestbps`, `restecg`
- `resting_plus_labs`: above + `chol`, `fbs`
- `includes_exercise_tests`: above + `thalach`, `exang`, `oldpeak`, `slope`

The initial five-field panel is a prospective research candidate, not an
approved model feature set. Labs and exercise measurements are separate,
optional stages. The source-code conventions and units are suitable only for
these synthetic software tests; they do not establish clinical ranges,
measurement timing, or cross-dataset compatibility. `ca`, `Cath`, `num`,
`LAD`, `LCX`, `RCA`, other angiographic measurements, identifiers, site fields,
`thal`, and wearable/monitoring observations are rejected by the stage
allowlist.

## Research context

The aggregate-only real DA-A2 availability evidence and staged-intake
architecture are documented in
[`14_real_joint_availability_and_staged_intake_decision.md`](../../docs/research/gate-da/14_real_joint_availability_and_staged_intake_decision.md).
Those source availability counts are not predictive performance, a selected
feature set, or authorization to fit a model. The candidate panel remains
subject to predictor-timing review, target/source decisions, and Gate PT.

## Contract proposal — not implemented

The versioned future clinician-intake design is
[`shared/contracts/proposals/clinician_intake_stage.v0.1.md`](../../shared/contracts/proposals/clinician_intake_stage.v0.1.md).
It remains **DESIGN PROPOSAL ONLY** and is not wired into the current CAD mock
or wearable endpoint. The current `/v1/predictions/cad-tabular` MOCK/SYNTHETIC
path and `/v1/monitoring/observations` Track-B separation remain unchanged.

## Run synthetic tests only

```bash
python -m pytest tests/audit/test_synthetic_stage_intake_safety.py \
  tests/audit/test_synthetic_preprocessing.py -q -W error

# R1 Cleveland five-field source mapping (PROPOSED v0.1):
python -m pytest tests/audit/test_cleveland_five_field_source_mapping.py -q -W error
```

All examples and tests contain invented synthetic software values. There are
no new Python dependencies and no model is trained, selected, evaluated,
calibrated, explained, or served.

## How a future approved model could connect

After the maintainer and supervisor freeze an approved Gate PT protocol, a
separate model adapter could accept only the matching versioned intake schema,
apply preprocessing fitted inside each training fold, and pass the resulting
matrix to a separately approved model. Holdout data must never affect fitted
imputation or encoding parameters. The current prototype demonstrates
training/holdout separation with toy fixtures only; it is not a deployable
pipeline and contains no model interface or prediction method.

## Scientific and clinical limits

This milestone does not establish the final diagnostic target, the exactly-50%
threshold semantics, source-label compatibility, predictor timing, clinically
acceptable ranges, zero-code interpretation across sources, statistical
adequacy, calibration, external validation, fairness, or clinical utility.
Do not pool datasets or harmonize labels automatically. UCI-412 and UCI-411
represent the same 303-patient cohort; UCI-411 is not an independent sample.
Future CAD-presence classification is distinct from 30-day cardiovascular
event prediction.

**Gate PT P-3 remains CLOSED.** No real-data model fitting, feature selection,
tuning, validation, calibration, SHAP/LIME analysis, or clinical claims are
authorized. Real patient data and real dataset paths must remain outside this
repository and all unapproved services.
