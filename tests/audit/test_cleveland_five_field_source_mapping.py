"""R1 — Cleveland five-field input mapping: synthetic-only validator tests.

Every fixture value below is an invented software sentinel. No dataset file is
read, no model is fitted, no CAD probability is computed anywhere in this
suite, and the validator under test is an offline research artifact that is
never imported by the backend application. These tests implement the acceptance
criteria of Gate PT doc 12 section 6 (R1) for the PROPOSED mapping
``cleveland_resting_five_field.v0.1``.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import fields as dataclass_fields
import json
from pathlib import Path

import pytest

from research.intake import cleveland_source_mapping as csm
from research.intake.cleveland_source_mapping import (
    MAPPING_FIELDS,
    MAPPING_STATUS,
    RESULT_STATE,
    MappingSpecIntegrityError,
    SourceMappingError,
    load_mapping_spec,
    review_cleveland_source_mapping,
)
from research.intake.synthetic_stage_validator import (
    FIELD_DEFINITIONS,
    MEASUREMENT_MISSING_REASONS as M2B_MEASUREMENT_REASONS,
    MISSING_REASONS as M2B_MISSING_REASONS,
    STAGE_FIELDS,
    STRUCTURAL_MISSING_REASON as M2B_STRUCTURAL_REASON,
    FieldKind,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

# Invented software sentinels (deliberately implausible measurements; never
# copied from any dataset or patient record).
SENTINEL_FEATURES = {"age": 10, "sex": 0, "cp": 3, "trestbps": 20.0, "restecg": 0}
SENTINEL_UNITS = {"age": "years", "trestbps": "mmHg"}
SENTINEL_SOURCE = {
    "source_id": "UCI-45-processed-cleveland",
    "dataset_id": "DA-A2",
    "track": "A",
}


def mapping_fixture(stage: str = "resting_assessment") -> dict:
    """A correctly coded synthetic source fixture for the requested stage."""
    bundle = {
        "history_only": ("age", "sex", "cp"),
        "resting_assessment": ("age", "sex", "cp", "trestbps", "restecg"),
    }[stage]
    return {
        "mapping_version": "cleveland_resting_five_field.v0.1",
        "synthetic": True,
        "source": dict(SENTINEL_SOURCE),
        "stage": stage,
        "features": {k: SENTINEL_FEATURES[k] for k in bundle},
        "units": {k: SENTINEL_UNITS[k] for k in bundle if k in SENTINEL_UNITS},
        "missing_reasons": {},
    }


# --------------------------------------------------------------------------
# 1. Specification artifact: versioned, PROPOSED, Cleveland NOT selected.
# --------------------------------------------------------------------------


def test_spec_file_is_versioned_and_explicitly_proposed() -> None:
    document = json.loads(csm.SPEC_PATH.read_text(encoding="utf-8"))
    assert document["schema_id"] == "cleveland_resting_five_field_input_mapping"
    assert document["schema_version"] == "0.1.0"
    assert document["mapping_id"] == "cleveland_resting_five_field.v0.1"
    assert document["status"] == "PROPOSED_NOT_APPROVED"
    assert (
        document["artifact_kind"]
        == "SYNTHETIC_ONLY_RESEARCH_INPUT_MAPPING_SPECIFICATION"
    )
    assert "PROPOSED" in document["status_statement"]
    assert "not an approved" in document["status_statement"]
    assert "SYNTHETIC" in document["status_statement"]
    assert [field["name"] for field in document["fields"]] == list(MAPPING_FIELDS)


def test_spec_states_cleveland_is_not_selected_as_final_dataset() -> None:
    document = json.loads(csm.SPEC_PATH.read_text(encoding="utf-8"))
    assert (
        document["dataset_selection_status"]
        == "CLEVELAND_NOT_SELECTED_AS_FINAL_PROJECT_DATASET"
    )
    assert "NOT been selected" in document["dataset_selection_statement"]


def test_spec_loads_and_matches_frozen_code_allowlists() -> None:
    spec = load_mapping_spec()
    assert spec.mapping_id == "cleveland_resting_five_field.v0.1"
    assert spec.status == "PROPOSED_NOT_APPROVED"
    assert tuple(field.name for field in spec.fields) == MAPPING_FIELDS
    assert spec.source_id == "UCI-45-processed-cleveland"
    assert spec.dataset_id == "DA-A2"
    assert spec.track == "A"
    assert load_mapping_spec() is spec  # cached, read-only


def test_spec_reuses_m2b_stage_validator_conventions() -> None:
    """The five shared field conventions must match the M2b prototype exactly."""
    spec = load_mapping_spec()
    assert MAPPING_FIELDS == STAGE_FIELDS["resting_assessment"]
    assert dict(csm.STAGE_FIELD_BUNDLES) == {
        stage: STAGE_FIELDS[stage] for stage in csm.SUPPORTED_STAGES
    }
    assert set(csm.MANDATORY_FIELDS) == {"age", "sex", "cp"}
    for name, definition in FIELD_DEFINITIONS.items():
        if name not in MAPPING_FIELDS:
            continue
        mapped = spec.field(name)
        assert mapped.required_stage == csm.FIELD_REQUIRED_STAGE[name]
        if definition.kind is FieldKind.CATEGORICAL:
            assert mapped.kind == "categorical"
            assert mapped.source_codes == definition.source_codes
            assert mapped.source_codes == csm.CATEGORICAL_SOURCE_CODES[name]
        else:
            assert mapped.kind == "numerical"
            assert mapped.unit == definition.unit
            assert mapped.unit == csm.NUMERIC_UNIT_TOKENS[name]
            assert definition.numeric_rule is not None
    assert csm.MISSING_REASON_VOCABULARY == M2B_MISSING_REASONS
    assert csm.MEASUREMENT_MISSING_REASONS == M2B_MEASUREMENT_REASONS
    assert csm.STRUCTURAL_MISSING_REASON == M2B_STRUCTURAL_REASON


@pytest.mark.parametrize(
    "mutation",
    [
        pytest.param(
            lambda d: d["fields"][2].__setitem__("source_codes", [1, 2, 3, 4, 5]),
            id="cp-vocabulary-extended",
        ),
        pytest.param(
            lambda d: d["fields"].append(
                {"name": "chol", "kind": "numerical", "unit": "mg/dL"}
            ),
            id="field-added",
        ),
        pytest.param(
            lambda d: d["prohibited_fields"].pop("outcome_label"),
            id="prohibited-category-removed",
        ),
        pytest.param(
            lambda d: d["prohibited_fields"]["outcome_label"].__setitem__(
                "fields", ["num", "age"]
            ),
            id="mapped-field-listed-as-prohibited",
        ),
        pytest.param(
            lambda d: d.__setitem__("status", "APPROVED"),
            id="status-upgraded",
        ),
        pytest.param(
            lambda d: d.__setitem__("dataset_selection_status", "SELECTED"),
            id="dataset-selection-status-changed",
        ),
        pytest.param(
            lambda d: d["fields"][3].__setitem__("unit", "kPa"),
            id="unit-token-changed",
        ),
        pytest.param(
            lambda d: d["no_result_contract"].__setitem__(
                "result_state", "SCORE_AVAILABLE"
            ),
            id="no-result-contract-broken",
        ),
        pytest.param(
            lambda d: d["registered_source"].__setitem__("source_id", "UCI-412"),
            id="source-swapped",
        ),
        pytest.param(
            lambda d: d["supported_stages"]["history_only"].__setitem__(
                "field_bundle", ["age", "sex"]
            ),
            id="stage-bundle-changed",
        ),
        pytest.param(
            lambda d: d["fields"][0].__setitem__(
                "required_measurement_stage", "resting_assessment"
            ),
            id="field-stage-changed",
        ),
    ],
)
def test_spec_integrity_guard_fails_closed_on_drift(mutation) -> None:
    document = json.loads(csm.SPEC_PATH.read_text(encoding="utf-8"))
    mutation(document)
    with pytest.raises(MappingSpecIntegrityError):
        csm._validate_spec_document(document)


# --------------------------------------------------------------------------
# 2. Acceptance: correctly coded synthetic source inputs.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("stage", ("history_only", "resting_assessment"))
def test_accepts_correctly_coded_synthetic_source_inputs(stage: str) -> None:
    source = mapping_fixture(stage)
    original = deepcopy(source)
    review = review_cleveland_source_mapping(source)
    assert source == original  # input is never mutated
    assert review.mapping_id == "cleveland_resting_five_field.v0.1"
    assert review.spec_status == "PROPOSED_NOT_APPROVED"
    assert review.source_id == "UCI-45-processed-cleveland"
    assert review.dataset_id == "DA-A2"
    assert review.track == "A"
    assert review.stage == stage
    assert review.stage_complete
    assert review.mapped_fields == csm.STAGE_FIELD_BUNDLES[stage]
    assert review.mapped_field_stages == tuple(
        (name, csm.FIELD_REQUIRED_STAGE[name])
        for name in csm.STAGE_FIELD_BUNDLES[stage]
    )
    assert review.missing_fields_with_reason == ()
    assert review.synthetic_only is True


def test_history_stage_with_absent_resting_fields_reports_incompleteness() -> None:
    source = mapping_fixture("resting_assessment")
    source["features"]["trestbps"] = None
    source["units"].pop("trestbps")
    source["missing_reasons"]["trestbps"] = "not_measured"
    del source["features"]["restecg"]
    source["missing_reasons"]["restecg"] = "not_provided"
    review = review_cleveland_source_mapping(source)
    assert not review.stage_complete
    assert review.mapped_fields == ("age", "sex", "cp")
    assert review.missing_fields_with_reason == (
        ("trestbps", "not_measured"),
        ("restecg", "not_provided"),
    )


def test_reviews_are_deterministic() -> None:
    first = review_cleveland_source_mapping(mapping_fixture())
    second = review_cleveland_source_mapping(mapping_fixture())
    assert first == second


# --------------------------------------------------------------------------
# 3. No-result state: no CAD probability can ever be produced.
# --------------------------------------------------------------------------


def test_complete_mapping_returns_explicit_no_result_state() -> None:
    review = review_cleveland_source_mapping(mapping_fixture())
    assert review.stage_complete is True
    assert review.result_state == "NO_RESULT_NO_CAD_PROBABILITY_COMPUTED"
    assert review.mapping_status == MAPPING_STATUS == (
        "ACCEPTED_SYNTHETIC_FIXTURE_MAPPING_ONLY"
    )


def test_incomplete_mapping_returns_the_same_no_result_state() -> None:
    source = mapping_fixture()
    source["features"]["trestbps"] = None
    source["units"].pop("trestbps")
    source["missing_reasons"]["trestbps"] = "not_available_at_time"
    review = review_cleveland_source_mapping(source)
    assert not review.stage_complete
    assert review.result_state == RESULT_STATE


def test_review_object_is_metadata_only_and_value_free() -> None:
    review = review_cleveland_source_mapping(mapping_fixture())
    text = repr(review)
    for sentinel in ("10", "20.0", "20", "3"):
        assert sentinel not in text  # no submitted values are echoed
    forbidden_name_terms = (
        "score", "probab", "predict", "risk", "infer", "classif", "diagnos",
        "outcome", "label", "value",
    )
    for field in dataclass_fields(review):
        assert not any(
            term in field.name.lower() for term in forbidden_name_terms
        ), field.name


def test_module_exposes_no_scoring_entry_point() -> None:
    forbidden_callable_terms = (
        "score", "probab", "predict", "risk", "infer", "classif", "diagnos",
    )
    for name, obj in vars(csm).items():
        if callable(obj) and not isinstance(obj, type):
            assert not any(
                term in name.lower() for term in forbidden_callable_terms
            ), name
    source = Path(csm.__file__).read_text(encoding="utf-8")
    for forbidden_import in (
        "from backend", "import backend", "sklearn", "numpy", "pandas",
        "requests", "urllib", "socket", "httpx",
    ):
        assert forbidden_import not in source


def test_validator_is_not_referenced_by_backend_or_contracts() -> None:
    targets = [REPOSITORY_ROOT / "backend", REPOSITORY_ROOT / "shared"]
    for root in targets:
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix in {".py", ".yaml", ".yml", ".json", ".md"}:
                assert "cleveland_source_mapping" not in path.read_text(
                    encoding="utf-8"
                ), path


# --------------------------------------------------------------------------
# 4. Rejection: unknown and outcome-derived fields.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "category"),
    [
        ("num", "outcome_label"),
        ("target", "outcome_label"),
        ("outcome", "outcome_label"),
        ("label", "outcome_label"),
        ("cad_label", "outcome_label"),
        ("Cath", "outcome_label"),
        ("ca", "angiography_or_post_catheterization"),
        ("LAD", "angiography_or_post_catheterization"),
        ("LCX", "angiography_or_post_catheterization"),
        ("RCA", "angiography_or_post_catheterization"),
        ("lmt", "angiography_or_post_catheterization"),
        ("ladprox", "angiography_or_post_catheterization"),
        ("rcadist", "angiography_or_post_catheterization"),
        ("cmo", "angiography_or_post_catheterization"),
        ("cday", "angiography_or_post_catheterization"),
        ("cyr", "angiography_or_post_catheterization"),
        ("stenosis_percent", "angiography_or_post_catheterization"),
        ("thal", "excluded_pending_timing_review"),
        ("id", "identifier_or_site"),
        ("ccf", "identifier_or_site"),
        ("name", "identifier_or_site"),
        ("site", "identifier_or_site"),
        ("patient_id", "identifier_or_site"),
        ("patient_ref", "identifier_or_site"),
        ("mrn", "identifier_or_site"),
        ("blood_pressure", "unregistered_field"),
        ("smoking_status", "unregistered_field"),
        ("handedness", "unregistered_field"),
    ],
)
def test_outcome_identifier_and_unknown_fields_fail_closed(
    field: str, category: str
) -> None:
    source = mapping_fixture()
    source["features"][field] = "synthetic-only"
    with pytest.raises(SourceMappingError) as error:
        review_cleveland_source_mapping(source)
    assert error.value.code == "prohibited_field"
    assert error.value.category == category
    assert "synthetic-only" not in str(error.value)  # values never echoed


def test_prohibited_field_in_units_or_reasons_map_also_fails_closed() -> None:
    for block in ("units", "missing_reasons"):
        source = mapping_fixture()
        source[block]["heart_rate_bpm"] = (
            "bpm" if block == "units" else "not_measured"
        )
        with pytest.raises(SourceMappingError) as error:
            review_cleveland_source_mapping(source)
        assert error.value.code == "prohibited_field"
        assert error.value.category == "wearable_or_track_b"


@pytest.mark.parametrize(
    "field",
    [
        "chol", "fbs", "thalach", "exang", "oldpeak", "slope",
    ],
)
def test_later_stage_uci45_fields_are_outside_this_mapping(field: str) -> None:
    source = mapping_fixture()
    source["features"][field] = 1
    with pytest.raises(SourceMappingError) as error:
        review_cleveland_source_mapping(source)
    assert error.value.code == "prohibited_field"
    assert error.value.category == "outside_mapping_scope"


@pytest.mark.parametrize(
    "field",
    [
        "Age", "Sex", "BMI", "DM", "HTN", "Current Smoker", "EX-Smoker", "FH",
        "DLP", "BP", "PR", "Typical Chest Pain", "Atypical", "Nonanginal",
        "Exertional CP", "Dyspnea",
    ],
)
def test_other_dataset_columns_are_rejected_without_harmonization(
    field: str,
) -> None:
    """UCI-412/411 columns (case-sensitive) never silently become UCI-45 fields."""
    source = mapping_fixture()
    source["features"][field] = 1
    with pytest.raises(SourceMappingError) as error:
        review_cleveland_source_mapping(source)
    assert error.value.code == "prohibited_field"
    assert error.value.category == "other_dataset_source"


# --------------------------------------------------------------------------
# 5. Rejection: ambiguous category conversions (no coercion, no crosswalk).
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sex", "male"), ("sex", "Male"), ("sex", "female"),
        ("sex", "Fmale"), ("sex", "Y"), ("sex", "N"),
        ("sex", True), ("sex", False), ("sex", 1.0), ("sex", 0.0),
        ("cp", "typical"), ("cp", "atypical angina"), ("cp", "non-anginal"),
        ("cp", "asymptomatic"), ("cp", 2.0), ("cp", True),
        ("restecg", "0"), ("restecg", "normal"), ("restecg", 1.0),
        ("restecg", True), ("restecg", "?"),
        ("cp", "?"),
    ],
)
def test_ambiguous_category_conversions_fail_closed(field: str, value) -> None:
    source = mapping_fixture()
    source["features"][field] = value
    with pytest.raises(SourceMappingError) as error:
        review_cleveland_source_mapping(source)
    assert error.value.code == "ambiguous_category_conversion"
    assert str(value) not in str(error.value)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sex", 2), ("sex", -1), ("cp", 0), ("cp", 5), ("cp", -2),
        ("restecg", 3), ("restecg", -1),
    ],
)
def test_unknown_categorical_codes_fail_closed(field: str, value: int) -> None:
    source = mapping_fixture()
    source["features"][field] = value
    with pytest.raises(SourceMappingError) as error:
        review_cleveland_source_mapping(source)
    assert error.value.code == "unknown_categorical_code"


# --------------------------------------------------------------------------
# 6. Rejection: incompatible units and missing required metadata.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "token"),
    [
        ("trestbps", "kPa"), ("trestbps", "mmhg"), ("trestbps", "mm Hg"),
        ("trestbps", "mmHg "), ("trestbps", "MMHG"), ("trestbps", "torr"),
        ("age", "yr"), ("age", "years "), ("age", "YEARS"), ("age", "months"),
    ],
)
def test_incompatible_unit_tokens_fail_closed(field: str, token: str) -> None:
    source = mapping_fixture()
    source["units"][field] = token
    with pytest.raises(SourceMappingError) as error:
        review_cleveland_source_mapping(source)
    assert error.value.code == "unit_mismatch"
    assert token not in str(error.value)


def test_missing_unit_for_measured_field_fails_closed() -> None:
    source = mapping_fixture()
    del source["units"]["trestbps"]
    with pytest.raises(SourceMappingError) as error:
        review_cleveland_source_mapping(source)
    assert error.value.code == "unit_mismatch"

    source = mapping_fixture()
    del source["units"]["age"]
    with pytest.raises(SourceMappingError) as error:
        review_cleveland_source_mapping(source)
    assert error.value.code == "unit_mismatch"


def test_extra_or_misplaced_unit_entries_fail_closed() -> None:
    categorical = mapping_fixture()
    categorical["units"]["sex"] = "none"
    with pytest.raises(SourceMappingError) as error:
        review_cleveland_source_mapping(categorical)
    assert error.value.code == "unit_mismatch"

    null_field = mapping_fixture()
    null_field["features"]["trestbps"] = None
    null_field["missing_reasons"]["trestbps"] = "not_measured"
    null_field["units"]["trestbps"] = "mmHg"
    with pytest.raises(SourceMappingError) as error:
        review_cleveland_source_mapping(null_field)
    assert error.value.code == "unit_mismatch"


@pytest.mark.parametrize(
    "remove_key",
    [
        "mapping_version", "synthetic", "source", "stage",
        "features", "units", "missing_reasons",
    ],
)
def test_missing_required_metadata_fails_closed(remove_key: str) -> None:
    source = mapping_fixture()
    del source[remove_key]
    with pytest.raises(SourceMappingError) as error:
        review_cleveland_source_mapping(source)
    assert error.value.code == "missing_required_metadata"


def test_missing_or_extra_source_provenance_fails_closed() -> None:
    source = mapping_fixture()
    del source["source"]["track"]
    with pytest.raises(SourceMappingError) as error:
        review_cleveland_source_mapping(source)
    assert error.value.code == "missing_required_metadata"

    source = mapping_fixture()
    source["source"]["device"] = "smartwatch"
    with pytest.raises(SourceMappingError) as error:
        review_cleveland_source_mapping(source)
    assert error.value.code == "malformed_payload"

    source = mapping_fixture()
    source["notes"] = "extra envelope property"
    with pytest.raises(SourceMappingError) as error:
        review_cleveland_source_mapping(source)
    assert error.value.code == "malformed_payload"


@pytest.mark.parametrize(
    "mapping_version",
    [
        "cleveland_resting_five_field.v0.2",
        "cleveland_resting_five_field",
        "clinician_intake.stage.v0.1",
        "mock_clinical_v1",
    ],
)
def test_unsupported_mapping_versions_fail_closed(mapping_version: str) -> None:
    source = mapping_fixture()
    source["mapping_version"] = mapping_version
    with pytest.raises(SourceMappingError) as error:
        review_cleveland_source_mapping(source)
    assert error.value.code == "unsupported_mapping_version"


@pytest.mark.parametrize("stage", ("resting_plus_labs", "includes_exercise_tests", ""))
def test_unsupported_stages_fail_closed(stage: str) -> None:
    source = mapping_fixture()
    source["stage"] = stage
    with pytest.raises(SourceMappingError) as error:
        review_cleveland_source_mapping(source)
    assert error.value.code == "unsupported_stage"


@pytest.mark.parametrize("synthetic", (False, None, "true", 1))
def test_non_synthetic_flags_fail_closed(synthetic) -> None:
    source = mapping_fixture()
    source["synthetic"] = synthetic
    with pytest.raises(SourceMappingError) as error:
        review_cleveland_source_mapping(source)
    assert error.value.code == "non_synthetic_input"


def test_registered_field_before_its_stage_fails_closed() -> None:
    source = mapping_fixture("history_only")
    source["features"]["trestbps"] = 20.0
    source["units"]["trestbps"] = "mmHg"
    with pytest.raises(SourceMappingError) as error:
        review_cleveland_source_mapping(source)
    assert error.value.code == "field_not_available_for_stage"


# --------------------------------------------------------------------------
# 7. Rejection: wearable / Track-B inputs.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field",
    [
        "wearable_heart_rate", "heart_rate_bpm", "steps", "spo2",
        "wearable_ecg", "hrv", "monitoring_observation",
    ],
)
def test_wearable_fields_fail_closed(field: str) -> None:
    source = mapping_fixture()
    source["features"][field] = 72
    with pytest.raises(SourceMappingError) as error:
        review_cleveland_source_mapping(source)
    assert error.value.code == "prohibited_field"
    assert error.value.category == "wearable_or_track_b"


def test_track_b_provenance_fails_closed() -> None:
    source = mapping_fixture()
    source["source"]["track"] = "B"
    with pytest.raises(SourceMappingError) as error:
        review_cleveland_source_mapping(source)
    assert error.value.code == "track_b_input_rejected"


@pytest.mark.parametrize(
    ("source_id", "dataset_id"),
    [
        ("patient-wearable-sync", "TRACK-B"),
        ("UCI-412", "DA-A1"),
        ("UCI-45-processed-hungary", "DA-A2"),
    ],
)
def test_wrong_source_provenance_fails_closed(source_id: str, dataset_id: str) -> None:
    source = mapping_fixture()
    source["source"]["source_id"] = source_id
    source["source"]["dataset_id"] = dataset_id
    with pytest.raises(SourceMappingError) as error:
        review_cleveland_source_mapping(source)
    assert error.value.code == "unsupported_source"


# --------------------------------------------------------------------------
# 8. Zero preservation versus missing data.
# --------------------------------------------------------------------------


def test_valid_categorical_zero_is_preserved_as_data() -> None:
    source = mapping_fixture()
    assert source["features"]["sex"] == 0
    assert source["features"]["restecg"] == 0
    review = review_cleveland_source_mapping(source)
    assert "sex" in review.mapped_fields
    assert "restecg" in review.mapped_fields
    assert review.missing_fields_with_reason == ()
    assert review.stage_complete


def test_zero_is_distinguished_from_missing_in_the_same_payload() -> None:
    source = mapping_fixture()
    source["features"]["trestbps"] = None  # explicit missing, not zero
    source["units"].pop("trestbps")
    source["missing_reasons"]["trestbps"] = "not_measured"
    review = review_cleveland_source_mapping(source)
    assert review.mapped_fields == ("age", "sex", "cp", "restecg")
    assert review.missing_fields_with_reason == (("trestbps", "not_measured"),)
    assert not review.stage_complete
    assert review.result_state == RESULT_STATE


@pytest.mark.parametrize("zero", (0, 0.0))
def test_measured_zero_trestbps_is_unavailable_not_valid(zero) -> None:
    source = mapping_fixture()
    source["features"]["trestbps"] = zero
    with pytest.raises(SourceMappingError) as error:
        review_cleveland_source_mapping(source)
    assert error.value.code == "zero_measurement_unavailable"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("trestbps", -1), ("trestbps", -0.5), ("age", 0), ("age", -3),
        ("age", float("nan")), ("age", float("inf")), ("age", float("-inf")),
        ("trestbps", float("nan")), ("trestbps", 10**400),
        ("age", "?"), ("trestbps", "?"), ("trestbps", "120"), ("age", True),
    ],
)
def test_invalid_numeric_values_fail_closed(field: str, value) -> None:
    source = mapping_fixture()
    source["features"][field] = value
    with pytest.raises(SourceMappingError) as error:
        review_cleveland_source_mapping(source)
    assert error.value.code == "invalid_numeric_value"


# --------------------------------------------------------------------------
# 9. Missing-reason semantics.
# --------------------------------------------------------------------------


def test_mandatory_fields_cannot_be_missing() -> None:
    omitted = mapping_fixture()
    del omitted["features"]["cp"]
    with pytest.raises(SourceMappingError) as error:
        review_cleveland_source_mapping(omitted)
    assert error.value.code == "missing_required_field"

    nullified = mapping_fixture()
    nullified["features"]["cp"] = None
    with pytest.raises(SourceMappingError) as error:
        review_cleveland_source_mapping(nullified)
    assert error.value.code == "missing_required_field"

    history = mapping_fixture("history_only")
    history["features"]["sex"] = None
    with pytest.raises(SourceMappingError) as error:
        review_cleveland_source_mapping(history)
    assert error.value.code == "missing_required_field"


def test_missing_reason_consistency_is_enforced() -> None:
    # Omitted field with a measurement reason is rejected.
    source = mapping_fixture()
    del source["features"]["restecg"]
    source["missing_reasons"]["restecg"] = "not_measured"
    with pytest.raises(SourceMappingError) as error:
        review_cleveland_source_mapping(source)
    assert error.value.code == "invalid_missing_reason"

    # Explicit null with the structural reason is rejected.
    source = mapping_fixture()
    source["features"]["restecg"] = None
    source["missing_reasons"]["restecg"] = "not_provided"
    with pytest.raises(SourceMappingError) as error:
        review_cleveland_source_mapping(source)
    assert error.value.code == "invalid_missing_reason"

    # A reason on a measured field is rejected.
    source = mapping_fixture()
    source["missing_reasons"]["age"] = "not_measured"
    with pytest.raises(SourceMappingError) as error:
        review_cleveland_source_mapping(source)
    assert error.value.code == "invalid_missing_reason"

    # An unavailable field without a reason is rejected.
    source = mapping_fixture()
    del source["features"]["restecg"]
    with pytest.raises(SourceMappingError) as error:
        review_cleveland_source_mapping(source)
    assert error.value.code == "invalid_missing_reason"

    # Unknown reason vocabulary is rejected.
    source = mapping_fixture()
    del source["features"]["restecg"]
    source["missing_reasons"]["restecg"] = "lost"
    with pytest.raises(SourceMappingError) as error:
        review_cleveland_source_mapping(source)
    assert error.value.code == "invalid_missing_reason"


def test_non_mapping_payload_shapes_fail_closed() -> None:
    with pytest.raises(SourceMappingError) as error:
        review_cleveland_source_mapping(["not", "a", "mapping"])
    assert error.value.code == "malformed_payload"

    with pytest.raises(SourceMappingError) as error:
        review_cleveland_source_mapping(
            {**mapping_fixture(), "features": ["age"]}
        )
    assert error.value.code == "malformed_payload"
