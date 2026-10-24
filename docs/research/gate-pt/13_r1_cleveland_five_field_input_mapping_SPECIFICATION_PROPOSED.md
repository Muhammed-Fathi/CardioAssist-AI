# 13 — R1 Cleveland Five-Field Research Input Mapping Specification (PROPOSED)

**Prepared:** 2026-10-24 · **Base:** `main` merge of PR #48 (`791ae6e`) · **Status: PROPOSED — NOT APPROVED — SYNTHETIC-ONLY.**

> **This is a technical mapping and validation artifact only. It is NOT real CAD inference, NOT a model-selection decision, NOT a dataset-selection decision, and NOT a clinical authorization.** Gate PT **P-1 PENDING**, formal **P-3 CLOSED**, **P-5 NOT MADE — prohibited**. D-046 remains read-only audit; D-047 (Cleveland internal exploratory) and D-048/M3a (UCI-412 internal exploratory) are unchanged and do not authorize anything here.
>
> **Cleveland has NOT been selected as the final project dataset.** The machine-readable specification carries `dataset_selection_status = CLEVELAND_NOT_SELECTED_AS_FINAL_PROJECT_DATASET`, enforced by a fail-closed integrity test. Any dataset selection remains a separate human scientific decision (Gate PT docs [11](11_two_dataset_scientific_evidence_synthesis_REVIEW_DRAFT.md)–[12](12_dataset_selection_and_clinical_workflow_alignment_REVIEW_DRAFT.md)); nothing in this PR may be cited as evidence for or against any candidate.

This document implements the **R1 "smallest next implementation task"** defined by [Gate PT doc 12 §6](12_dataset_selection_and_clinical_workflow_alignment_REVIEW_DRAFT.md): a *synthetic-only, non-executable mapping specification and validator tests* for the five-field UCI-45 resting-assessment proposal (`age`, `sex`, `cp`, `trestbps`, `restecg`), as a standalone research/contract design artifact. R1's exit condition — *the reviewer can trace every accepted/rejected synthetic input to a source definition and no real score can be produced* — is demonstrated by the automated tests in §10.

## 1. Artifacts delivered by this specification

| Artifact | Path | Kind |
|---|---|---|
| Versioned mapping specification (operative record) | `research/intake/schemas/cleveland_resting_five_field_mapping.v0.1.json` | JSON, `cleveland_resting_five_field_input_mapping` **0.1.0**, status `PROPOSED_NOT_APPROVED` |
| Synthetic-only offline validator | `research/intake/cleveland_source_mapping.py` | Python, standard library only, deterministic, no I/O except reading its own spec file |
| Automated synthetic tests | `tests/audit/test_cleveland_five_field_source_mapping.py` | 167 collected pytest cases; runs inside the existing `tests/audit` CI job with no workflow change |
| UCI-412 mapping-readiness appendix (Workstream B) | [14 — UCI-412 basic-panel readiness appendix](14_r1_uci412_basic_panel_mapping_readiness_APPENDIX.md) | Documentation only; **no UCI-412 adapter is implemented or run** |

## 2. Registered source and provenance

The mapping is bound to exactly one registered source triple, checked on every payload:

| Key | Value |
|---|---|
| `source_id` | `UCI-45-processed-cleveland` |
| `dataset_id` | `DA-A2` |
| `track` | `A` |

Provenance: UCI Heart Disease (id 45, DOI 10.24432/C52P4X), processed Cleveland file, 303 records, historical (1988-era documentation) angiography-referred cohort; the five fields are columns 1–4 and 7 of the conventional processed 14-column layout ([UCI-45](https://archive.ics.uci.edu/dataset/45/heart+disease); D-047 frozen plan). The raw `cleveland.data` file (76 attributes) is quarantined and is never a source here. **The validator never reads any dataset file** — it only ever sees caller-supplied synthetic fixtures, and a `synthetic: true` flag is a caller assertion, not proof of provenance. Any other `source_id`/`dataset_id` (including UCI-412 `DA-A1`, Hungary, or a wearable sync source) fails closed with `unsupported_source`: **no cross-dataset harmonization is registered, attempted or implied.**

## 3. Field mapping (literal source coding, units, stage, provenance)

The JSON record is authoritative; the table summarizes it. Categorical codes are **nominal labels in a fixed order, never an ordinal scale**, and are matched **literally** — no coercion, no label/token translation, no crosswalk.

| Field | Literal source coding (UCI-45) | Unit token (exact, when measured) | Required measurement stage | Optionality | Valid zero? | Missingness semantics |
|---|---|---|---|---|---|---|
| `age` | Age in years; positive finite number, conventionally integer-like | `years` | `history_only` | required non-null at all supported stages | No — 0 is invalid, not missing | can never be omitted or null |
| `sex` | `0` = female, `1` = male | — (categorical) | `history_only` | required non-null | **Yes — `0` is valid data (female), never missing** | can never be omitted or null |
| `cp` | `1` typical angina, `2` atypical angina, `3` non-anginal pain, `4` asymptomatic | — (categorical) | `history_only` | required non-null | No — vocabulary starts at 1; `0` is an unknown code | can never be omitted or null |
| `trestbps` | Resting blood pressure on admission, mm Hg; single positive value | `mmHg` | `resting_assessment` | optional at resting stage | **No — a measured 0 is *unavailable*, not a value** (ED-DA-A2-01 item 2); must be `null` + reason | explicit `null` + measurement reason, or omitted + `not_provided` |
| `restecg` | `0` normal, `1` ST-T abnormality (T inversions and/or ST elevation or depression > 0.05 mV), `2` probable/definite LVH by Estes' criteria | — (categorical) | `resting_assessment` | optional at resting stage | **Yes — `0` is valid data (normal), never missing** | as `trestbps` |

Supported stages are exactly `history_only` (`age`, `sex`, `cp`) and `resting_assessment` (the five fields) — the initial-consultation and baseline-resting stages of the adopted staged-intake direction **ED-DA-A2-01** ([Gate DA 14](../gate-da/14_real_joint_availability_and_staged_intake_decision.md)). The M2b lab/exercise stages are deliberately **not** supported by this mapping version; their fields are rejected as `outside_mapping_scope`. Measurement timing relative to angiography is **not certified by the source** — stage membership is the W0 workflow *hypothesis* of doc 12 §3, nothing more, and the review reports measurement completeness, never a probability.

**Ambiguous category conversions are rejected, never performed.** Text labels (`"male"`, `"atypical"`), other-dataset tokens (`"Fmale"`, `Y`/`N`), booleans and floats (`1.0`) for categorical fields all fail with `ambiguous_category_conversion`. The UCI-412 chest-pain binaries (`Typical Chest Pain`, `Atypical`, `Nonanginal`, `Exertional CP`; exclusivity unknown, S-4) are rejected as `other_dataset_source` fields — converting four flags into one four-class `cp` value would invent rules. The UCI-412 ECG binaries (blocked panel) are likewise not convertible to `restecg`.

**Units are exact tokens; nothing is converted.** `kPa`, `mm Hg`, `mmhg` and any other token for `trestbps` fail with `unit_mismatch`, as does a missing unit for a measured field, an extra unit for a categorical/null/absent field, or a unit declared for a prohibited field.

## 4. Missingness semantics

1. Required history fields (`age`, `sex`, `cp`) can never be omitted or null → `missing_required_field`.
2. An optional stage field omitted from `features` requires exactly `missing_reasons[field] = "not_provided"`.
3. An optional explicit `null` requires exactly one measurement reason: `not_measured`, `not_available_at_time` or `unknown`.
4. Measured fields take no reason; every unavailable field takes exactly one; unknown reason strings fail.
5. The UCI-45 processed-source missing token `?` is **never passed through**: a `?` string is rejected as a value (`ambiguous_category_conversion` for categorical fields, `invalid_numeric_value` for numeric fields). A future reviewed adapter would have to translate `?` to `null` + reason; **no such adapter exists in this version**.
6. UCI-45 never recorded missingness reasons; fixture reasons describe the synthetic fixture only and support no clinical inference about any real record.

## 5. Zero semantics

Valid zero is **preserved as data and strictly distinguished from missing**, in both directions, for every field: `sex = 0` and `restecg = 0` map as measured values and never appear in `missing_fields_with_reason`; a `null` with a reason is missing and never becomes zero. For `trestbps` only, a **measured 0 is unavailable, not a value** (ED-DA-A2-01 item 2: unexplained resting BP of 0 is treated as unavailable for proposed clinical use, preserving raw codes): the validator rejects it with the dedicated `zero_measurement_unavailable` code and requires the `null` + reason representation. This is a conservative prototype safeguard, not a universal clinical coding rule. `age = 0` is invalid (not missing); `cp = 0` is an unknown code (vocabulary starts at 1).

## 6. Prohibited label-adjacent and foreign fields (fail-closed taxonomy)

Every field name outside the five-field mapping is rejected; the validator reports a stable category so each rejection is traceable to its rule (classification is exact and case-sensitive — `age` ≠ `Age`):

| Category | Fields (examples of the registered lists) | Rationale |
|---|---|---|
| `outcome_label` | `num`, `target`, `outcome`, `label`, `cad_label`, `Cath` | The angiography-referenced target and aliases are never predictors (ED-DA-A2-01 item 4) |
| `angiography_or_post_catheterization` | `ca`, `lmt`, `ladprox` … `rcadist`, `cmo`, `cday`, `cyr`, `LAD`, `LCX`, `RCA`, `stenosis_percent`, `angiography` | Fluoroscopy/raw-vessel/cath-date and UCI-411/412 outcome-defining artery columns |
| `excluded_pending_timing_review` | `thal` | Thallium imaging result; excluded from the first staged interface pending time-of-acquisition review (ED-DA-A2-01 item 4) |
| `identifier_or_site` | `id`, `ccf`, `name`, `site`, `patient_id`, `patient_ref`, `mrn` | Identifiers and site markers are never predictors |
| `wearable_or_track_b` | `wearable_heart_rate`, `heart_rate_bpm`, `steps`, `spo2`, `wearable_ecg`, `hrv`, `monitoring_observation` | One-way Track A/B separation (D-039): wearable values never reach a CAD predictor path. A payload with `track: "B"` provenance fails with `track_b_input_rejected` |
| `other_dataset_source` | `Age`, `Sex`, `BMI`, `DM`, `HTN`, `Current Smoker`, `EX-Smoker`, `FH`, `DLP`, `BP`, `PR`, `Typical Chest Pain`, `Atypical`, `Nonanginal`, `Exertional CP`, `Dyspnea` | UCI-412/411 delivered column names; no cross-dataset harmonization exists |
| `outside_mapping_scope` | `chol`, `fbs`, `thalach`, `exang`, `oldpeak`, `slope` | Registered UCI-45 fields of later optional stages; not mappable under v0.1 (not prohibited forever) |
| `unregistered_field` (fallback) | anything else | Rejection is the default; allowlisting is the exception |

A prohibited name placed in `features`, `units` **or** `missing_reasons` fails closed. Error messages and reviews never echo submitted values.

## 7. Envelope and no-result contract

The synthetic fixture envelope is exactly `{mapping_version, synthetic, source, stage, features, units, missing_reasons}` with `source = {source_id, dataset_id, track}`; unknown properties and unsupported versions (including the *design-proposal* identifier `clinician_intake.stage.v0.1` and mock schema ids) fail closed. The version string is `cleveland_resting_five_field.v0.1`.

**Every accepted payload returns a `MappingReview` whose explicit result state is `NO_RESULT_NO_CAD_PROBABILITY_COMPUTED`** — including fully stage-complete fixtures — with `mapping_status = ACCEPTED_SYNTHETIC_FIXTURE_MAPPING_ONLY` and the spec status `PROPOSED_NOT_APPROVED` echoed on the review. The review carries only: mapping identity, source triple, stage, mapped field names, per-field required stage, missing fields with reasons, completeness flag, and the two status strings. It never contains submitted values, identifiers, a probability, score, risk class, explanation or treatment text. The implementing module has **no scoring, inference or prediction entry point** (asserted by test), performs no network access, and is never imported by the backend application or referenced by `/v1` (asserted by test). **No real scoring path may be introduced downstream of this mapping without separate human authorization and a frozen protocol.**

## 8. Versioning, change control and relationship to existing artifacts

- **Versioning:** JSON `schema_version` 0.1.0 with `revision_history`; the mapping id `cleveland_resting_five_field.v0.1` must match the payload exactly. Any change to fields, codes, units, stages, taxonomy or the no-result contract is a new version with a reviewed revision entry. The validator duplicates the operative allowlists in frozen Python constants (the `research/uci412/feature_schema.py` pattern) and `load_mapping_spec()` **fails closed if the JSON and the code disagree** (11 mutation cases tested).
- **M2b prototype (`research/intake/synthetic_stage_validator.py`): unchanged and still authoritative** for the four-stage synthetic preprocessing prototype. This mapping reuses its field conventions for the five shared fields — enforced by a coherence test (kinds, codes, units, stage bundles, missing-reason vocabulary all must match) — and adds what the M2b validator deliberately does not carry: source-provenance binding, mapping versioning, the prohibited-field taxonomy and the no-result review state.
- **`clinician_intake.stage.v0.1` design proposal:** remains a separate DESIGN PROPOSAL ONLY; this mapping is not that contract, does not implement it, and assigns no endpoint path.
- **Approved `/v1` contracts, backend, database, React/Flutter clients, frozen research plans and feature dictionaries: untouched** (see §9).

## 9. Architecture integration notes

- **Where it lives:** `research/intake/` beside the existing M2b synthetic intake prototype — the same research package, same conventions, no new framework. Standard library only; no new dependency in any `requirements.txt`; no CI workflow edit (the tests are picked up by the existing `audit-toolchain-validation` job, which runs `pytest tests/audit`).
- **What it does NOT touch:** no `/v1` OpenAPI schema, endpoint or fixture; no `backend/**` code (a test asserts the module is not referenced anywhere under `backend/` or `shared/`); no database, migration or persistence; no frontend; no inference provider, model registry or artifact-admission path; no frozen protocol, registered plan or feature dictionary (`research/experiments/**`, `research/uci412/**` untouched).
- **How a future approved model could connect (not authorized here):** only after P-1/P-3 Gate PT human decisions, a separately approved versioned clinical intake contract, and a frozen protocol — a model adapter could accept the *matching approved* intake schema, apply preprocessing fitted inside training folds only, and only then produce scored output under its own governance. This mapping intentionally provides **no** such adapter, **no** feature vector, **no** imputation and **no** model interface; it is a validation-only layer whose output is a metadata-only review.
- **Track A/B separation:** enforced twice — wearable/monitoring field names are prohibited, and Track-B provenance (`track: "B"`) is rejected before any field inspection.

## 10. Acceptance criteria and test results

Command (repository root, same as CI): `python -m pytest tests/audit -q -W error` → **404 passed** (237 pre-existing + **167 new** collected cases from `test_cleveland_five_field_source_mapping.py`; Python 3.11.2, pytest 9.0.3, Linux sandbox; the CI matrix additionally covers 3.12). The audit CLI checks (`check-auth`, `verify-ignore`, `dry-run`, `self-test`) and `scripts/verify_sources.py` remain green and unaffected.

| # | Required behavior (task acceptance criterion) | Enforcing tests |
|---|---|---|
| 1 | Versioned, explicitly PROPOSED mapping specification with literal source coding, units, stage, provenance, missingness semantics, prohibited fields | `test_spec_file_is_versioned_and_explicitly_proposed`, `test_spec_states_cleveland_is_not_selected_as_final_dataset`, `test_spec_loads_and_matches_frozen_code_allowlists`, `test_spec_integrity_guard_fails_closed_on_drift` (11 mutations), `test_spec_reuses_m2b_stage_validator_conventions` |
| 2 | Accept correctly coded synthetic source inputs | `test_accepts_correctly_coded_synthetic_source_inputs` (both stages), `test_history_stage_with_absent_resting_fields_reports_incompleteness`, `test_reviews_are_deterministic` |
| 3 | Reject unknown and outcome-derived fields | `test_outcome_identifier_and_unknown_fields_fail_closed` (28 cases), `test_prohibited_field_in_units_or_reasons_map_also_fails_closed`, `test_later_stage_uci45_fields_are_outside_this_mapping`, `test_other_dataset_columns_are_rejected_without_harmonization` (16 cases) |
| 4 | Reject ambiguous category conversions | `test_ambiguous_category_conversions_fail_closed` (23 cases), `test_unknown_categorical_codes_fail_closed` (7 cases) |
| 5 | Reject incompatible units and missing required metadata | `test_incompatible_unit_tokens_fail_closed` (10 cases), `test_missing_unit_for_measured_field_fails_closed`, `test_extra_or_misplaced_unit_entries_fail_closed`, `test_missing_required_metadata_fails_closed` (7 cases), `test_missing_or_extra_source_provenance_fails_closed`, `test_unsupported_mapping_versions_fail_closed` (4 cases), `test_unsupported_stages_fail_closed`, `test_registered_field_before_its_stage_fails_closed` |
| 6 | Preserve valid zero and distinguish it from missing data | `test_valid_categorical_zero_is_preserved_as_data`, `test_zero_is_distinguished_from_missing_in_the_same_payload`, `test_measured_zero_trestbps_is_unavailable_not_valid`, `test_invalid_numeric_values_fail_closed` (13 cases) |
| 7 | Reject wearable/Track-B inputs | `test_wearable_fields_fail_closed` (7 cases), `test_track_b_provenance_fails_closed`, `test_wrong_source_provenance_fails_closed` (3 cases) |
| 8 | Return an explicit no-result state without computing CAD probabilities | `test_complete_mapping_returns_explicit_no_result_state`, `test_incomplete_mapping_returns_the_same_no_result_state`, `test_review_object_is_metadata_only_and_value_free`, `test_module_exposes_no_scoring_entry_point`, `test_validator_is_not_referenced_by_backend_or_contracts` |
| 9 | Synthetic fixtures only; deterministic | all tests use invented sentinels; `test_reviews_are_deterministic`; no I/O beyond the spec file; no warnings under `-W error` |

## 11. Explicit boundary statements

- **Cleveland has NOT been selected as the final project dataset** (machine-checked, § status banner).
- No governance status is modified: P-1 PENDING, P-3 CLOSED, P-5 prohibited; D-046 read-only, D-047 and D-048/M3a unchanged; no decision-register entry is added or changed by this PR.
- No scientific, supervisor, ethics, institutional or clinical approval is granted or implied; this PR grants nothing and its merge would grant nothing.
- No real patient data, dataset file, download, model fitting, prediction, calibration, SHAP/LIME execution, external validation or clinical claim exists in this PR.
- The five-field panel remains a prospective research candidate for a *staged data-collection* design (ED-DA-A2-01), with no demonstrated model utility asserted or tested here; its within-dataset exploratory result (doc 04) is internal evidence only and was not used to choose anything in this PR.
