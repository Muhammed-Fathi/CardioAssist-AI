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

## RH-04 — Feature acquisition-evidence crosswalk (EVIDENCE ONLY, synthetic-only tests)

`feature_acquisition_crosswalk.py` implements the first engineering slice of
RH-04 (work packages RH-04-1/RH-04-2, see
[the RH-06 decision review §10.1](../../docs/research/next_phase/RH06_ISSUE110_CONSOLIDATED_DECISION_REVIEW_2026_11_19.md))
over the versioned, machine-readable record
[`schemas/feature_acquisition_evidence_crosswalk.v1.json`](schemas/feature_acquisition_evidence_crosswalk.v1.json)
(`rh04_feature_acquisition_evidence_crosswalk.v1`, schema version `1.1.0`,
status `EVIDENCE_ONLY_NOT_APPROVED`). Schema `1.1.0` is the authorization-scope
correction: it separates the **historical D-047 authorization evidence**
(original Cleveland five-field internal exploratory study only) from the
**current effective permission** of a feature, panel or route, and from the
**absence of any new real-data authorization** in this crosswalk.

It **reuses** the four registered panels (`ai.panels.REGISTERED_PANELS`) and the
five registered research routes (`ai.research_routes.RESEARCH_ROUTE_CATALOG`).
It defines no second clinical feature schema: no units, coding vocabularies,
plausible ranges, missingness rules, targets, model families, seeds or
thresholds are restated, and no new model route or endpoint exists.

For each of the 30 features registered in those four panels it separates four
questions that are routinely conflated:

| Question | Crosswalk field |
|---|---|
| Which document establishes the **original-source feature definition**? | `definition_evidence_ids` → resolved `evidence_register` entries |
| What **acquisition channel** is proposed, and on what basis? | `acquisition.channel`, `acquisition.channel_status` (`VERIFIED_REGISTERED_SOURCE_DOMAIN` / `PROPOSED_FUTURE_ACQUISITION_CHANNEL`) |
| Is the **pre-angiography measurement timing** verified? | `acquisition.timing_status`, `acquisition.owner_verified_pre_angiography`, `acquisition.timing_derived_from_channel_status` |
| What **source-specific permission and restrictions** apply? | `permission_id`, `effective_permission` (status + historical reference ids + `real_data_execution_authorized_by_this_crosswalk`), `restriction_ids`, `sources[]`, `blocked_items[]` |

### Authorization scope: historical evidence is not current permission

Schema `1.1.0` exports **no** unqualified `AUTHORIZED…` status. Three distinct
surfaces are recorded:

| Surface | Field(s) | Cleveland resting five (UCI-45) | UCI-45 `chol`/`fbs` | UCI-412 (23 features) | Hungary locked route |
|---|---|---|---|---|---|
| Historical D-047 authorization **evidence** | `authorization_references[]` (`AUTHREF-D047-CLEVELAND-FIVE-FIELD`) | recorded: `COMPLETED_HISTORICAL_INTERNAL_EXPLORATORY`, `authorizes_new_real_data_execution: false` | **not covered** | **not covered** | **not covered** (different panel) |
| Current **effective permission** | `effective_permission.effective_permission_status` | `HISTORICAL_REFERENCE_ONLY_NO_NEW_AUTHORIZATION` | `NOT_AUTHORIZED` | `SCIENTIFIC_HOLD_NEW_REAL_FIT` | `NOT_AUTHORIZED` |
| New real-data authorization from this crosswalk | `...real_data_execution_authorized_by_this_crosswalk`, `authorization_scope`, `holds` | `false` | `false` | `false` | `false` |

Permission records are scoped rather than source-wide:
`PERM-UCI45-D047-HISTORICAL-REFERENCE` (`HISTORICAL_D047_SCOPE_REFERENCE_ONLY`,
covering exactly `age`/`sex`/`cp`/`trestbps`/`restecg`),
`PERM-UCI45-LABS-NOT-AUTHORIZED` (`NOT_AUTHORIZED_OUT_OF_D047_SCOPE`, covering
`chol`/`fbs`), and `PERM-UCI412-SCIENTIFIC-HOLD`
(`SCIENTIFIC_HOLD_NEW_REAL_FIT`). D-047 itself is unchanged and every frozen
panel, route, hold and timing fact is untouched.

**`VERIFIED_REGISTERED_SOURCE_DOMAIN` is never proof of owner-verified
pre-angiography timing.** It verifies only that a proposed channel matches the
`source_domain`/`input_owner` already recorded in a frozen repository register.
The validator enforces this structurally: timing may never be derived from a
channel status, a verified channel may only carry
`UNVERIFIED_TIMING_REGISTERED_DOMAIN_CHANNEL`, the reserved
`OWNER_VERIFIED_PRE_ANGIOGRAPHY` status requires owner timing evidence, the
owner-timing evidence class list is **empty**, and the per-source
owner-verified counts are frozen at `0` and recomputed from the records.
UCI-412 therefore stays at **0/16** owner-verified pre-angiography timings.

All scientific holds are preserved and machine-checked: Gate PT P-1 `PENDING`,
P-3 `CLOSED`, P-5 `NOT_MADE_PROHIBITED`; the UCI-45 **labs extension**
(`da_a2_resting_labs_v1`), the **UCI-412 labs route**
(`da_a1_clinical_core_labs_v1`) and the **Hungary locked evaluation**
(`da_a2_hungary_locked_transportability_v1`) remain `BLOCKED` with
`route_contract_query` as their only permitted operation. Any activation,
widened permitted-operation set, removed forbidden operation, promoted
permission status, widened historical-authorization scope, extra authorization
reference or extra route fails closed.

### Read-only validator and deterministic metadata query

```bash
python -m research.intake.feature_acquisition_crosswalk validate
python -m research.intake.feature_acquisition_crosswalk describe
python -m research.intake.feature_acquisition_crosswalk query --dataset-id DA-A1 --feature-name BP
python -m research.intake.feature_acquisition_crosswalk query --route-id da_a1_clinical_core_labs_v1
```

The module is standard-library only, opens exactly one file, writes nothing,
opens no socket and imports neither the backend application nor the `ai`
package. Every query result carries
`result_state = METADATA_ONLY_NO_CAD_PROBABILITY_COMPUTED`; no score,
probability, calibration or explanation exists anywhere in this surface.

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
