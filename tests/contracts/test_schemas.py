"""Tests for the JSON Schemas that back the proposed /v1 contract.

Two kinds of assertion live here:

1. *Mechanical* — the files are valid JSON Schema 2020-12, their identifiers
   are unique, and their cross-references resolve.
2. *Guard-rail* — the MOCK_ONLY schemas may not drift into pretending to be a
   validated clinical dictionary: no real clinical unit, no real dataset field
   name, no dataset provenance, and no target with a time horizon.
"""

from __future__ import annotations

import json
import re

import pytest
from jsonschema import Draft202012Validator

from conftest import REGISTRY_DIR, SCHEMAS_DIR

MOCK_SCHEMA_FILES = (
    "mock_clinical_feature_schema.v1.json",
    "mock_clinical_feature_schema.v2.json",
)

#: Real dataset / clinical field names that a MOCK_ONLY schema must not reuse,
#: because the clinical dictionaries have not passed Gate DA (Phase 0 §F-3).
FORBIDDEN_FEATURE_NAMES = {
    "ca",
    "thal",
    "oldpeak",
    "trestbps",
    "chol",
    "fbs",
    "thalach",
    "exang",
    "restecg",
    "chest_pain_type",
    "num_major_vessels_fluoroscopy",
    "thallium_stress_test_result",
    "uci_heart_14_v1",
    "z_alizadeh_sani_v1",
}

#: Substrings that would betray a clinical dataset or dictionary.
FORBIDDEN_DATASET_MARKERS = (
    "uci-45",
    "uci-412",
    "uci_45",
    "uci_412",
    "z_alizadeh",
    "z-alizadeh",
    "heart disease (id 45)",
    "cleveland",
    "mmhg",
    "mg/dl",
    "mmol",
)

PLACEHOLDER_UNIT = re.compile(r"^u_[a-z0-9_]+$")
MOCK_FEATURE_ID = re.compile(r"^mock_feature_[a-z0-9_]+$")
MOCK_METRIC_ID = re.compile(r"^mock_metric_[a-z0-9_]+$")


# --------------------------------------------------------------------------- #
# mechanical validity
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("filename", sorted(p.name for p in SCHEMAS_DIR.glob("*.json")))
def test_every_schema_file_is_a_valid_json_schema(schema_documents, filename):
    Draft202012Validator.check_schema(schema_documents[filename])


def test_schema_ids_are_unique(schema_documents):
    identifiers = [
        document["$id"]
        for document in schema_documents.values()
        if "$id" in document
    ]
    assert len(identifiers) == len(set(identifiers))


def test_every_schema_declares_its_draft_and_id(schema_documents):
    for name, document in schema_documents.items():
        assert document["$schema"] == "https://json-schema.org/draft/2020-12/schema", name
        assert document["$id"].startswith("https://cardioassist.local/contracts/v1/"), name


def test_every_schema_carries_a_contract_status(schema_documents):
    for name, document in schema_documents.items():
        assert "x-contract-status" in document, name


# --------------------------------------------------------------------------- #
# MOCK_ONLY guard-rails
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("filename", MOCK_SCHEMA_FILES)
def test_mock_schemas_are_labelled_mock_only(schema_documents, filename):
    document = schema_documents[filename]
    assert document["x-contract-status"] == "MOCK_ONLY"
    assert document["x-data-dictionary-status"] == "UNVERIFIED_PENDING_GATE_DA"
    assert document["x-clinical-semantics"] == "NOT_ESTABLISHED"
    assert document["x-dataset-provenance"].startswith("NONE")


@pytest.mark.parametrize("filename", MOCK_SCHEMA_FILES)
def test_mock_schemas_use_placeholder_units_only(schema_documents, filename):
    """No clinical unit may be asserted before the dictionary is ratified.

    Every unit token in a MOCK_ONLY schema must be a schema-local placeholder
    of the form ``u_<name>`` (Phase 0 §F-1).
    """
    document = schema_documents[filename]
    tokens = set(document["$defs"]["UnitTokens"]["enum"])
    for feature in document["properties"].values():
        for part in feature.get("allOf", []):
            unit = part.get("properties", {}).get("unit", {})
            if "const" in unit:
                tokens.add(unit["const"])
    for token in tokens:
        assert PLACEHOLDER_UNIT.match(token), f"non-placeholder unit token: {token}"


@pytest.mark.parametrize("filename", MOCK_SCHEMA_FILES)
def test_mock_schemas_do_not_impersonate_a_dataset_dictionary(schema_documents, filename):
    """A MOCK_ONLY schema must not reuse a real dataset field, unit or identifier.

    The check is applied to the *identifiers* the schema declares (feature ids,
    schema id, title, provenance), not to the explanatory prose: the prose is
    allowed to say which clinical units are deliberately NOT used.
    """
    document = schema_documents[filename]
    feature_ids = set(document["properties"])
    feature_ids |= set(document.get("x-excluded-features", {}))
    feature_ids |= set(document.get("x-pending-review-features", {}))
    for feature_id in feature_ids:
        assert feature_id not in FORBIDDEN_FEATURE_NAMES, feature_id
        assert MOCK_FEATURE_ID.match(feature_id), feature_id

    identifiers = [
        document["$id"],
        document["title"],
        document.get("x-dataset-provenance", ""),
    ]
    identifiers.extend(document.get("x-required-features", []))
    identifiers.extend(feature_ids)
    for identifier in identifiers:
        lowered = identifier.lower()
        for marker in FORBIDDEN_DATASET_MARKERS:
            assert marker not in lowered, f"{filename}: identifier mentions {marker!r}"


def test_mock_schemas_declare_required_and_excluded_features(schema_documents):
    for filename in MOCK_SCHEMA_FILES:
        document = schema_documents[filename]
        assert document["required"]
        assert set(document["required"]) == set(document["x-required-features"])
        # Excluded and pending-review features are declared but not scorable.
        for feature_id in document.get("x-excluded-features", {}):
            assert feature_id not in document["properties"]
        for feature_id in document.get("x-pending-review-features", {}):
            assert feature_id not in document["properties"]


def test_monitoring_metric_catalogue_uses_placeholder_units_only():
    document = json.loads(
        (REGISTRY_DIR / "mock_monitoring_metrics.v1.json").read_text(encoding="utf-8")
    )
    assert document["status"] == "MOCK_ONLY"
    for metric in document["metrics"]:
        assert PLACEHOLDER_UNIT.match(metric["unit"]), metric
        assert MOCK_METRIC_ID.match(metric["metric_id"]), metric


def test_model_registry_declares_no_real_artifact(schema_documents):
    document = json.loads(
        (REGISTRY_DIR / "mock_model_registry.v1.json").read_text(encoding="utf-8")
    )
    assert document["status"] == "MOCK_ONLY"
    empty_sha = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    for model in document["models"]:
        assert model["artifact_sha256"] == empty_sha
        assert model["validation_status"] == "development_internal_only"
        assert model["model_performance_ref"].endswith("#internal_validation")


# --------------------------------------------------------------------------- #
# contract semantics encoded in the schemas
# --------------------------------------------------------------------------- #
def test_target_cannot_carry_a_time_horizon(schema_documents):
    target = schema_documents["common.schema.json"]["$defs"]["Target"]
    assert target["properties"]["time_horizon"]["const"] == "none_cross_sectional"
    assert target["properties"]["status"]["enum"] == ["provisional_pending_approval"]


def test_score_type_and_rendering_are_constrained(schema_documents):
    common = schema_documents["common.schema.json"]["$defs"]
    assert set(common["ScoreType"]["enum"]) == {"calibrated_probability", "uncalibrated_score"}
    rendering = common["ScoreRendering"]["properties"]
    assert rendering["absolute_population_probability_claim"]["const"] is False
    assert rendering["percent_sign_allowed"]["type"] == "boolean"
    assert "percent" in rendering["display_unit"]["enum"]  # available, but never allowed in v1


def test_explanation_scale_is_log_odds_only(schema_documents):
    explanation = schema_documents["common.schema.json"]["$defs"]["Explanation"]
    assert explanation["properties"]["scale"]["const"] == "log_odds_margin"
    assert set(explanation["properties"]["method"]["enum"]) == {"tree_shap", "lime"}


def test_lime_requires_a_local_fidelity_and_treeshap_forbids_it(schema_documents):
    explanation = schema_documents["common.schema.json"]["$defs"]["Explanation"]
    condition = explanation["allOf"][0]
    assert condition["if"]["properties"]["method"]["const"] == "lime"
    assert condition["then"]["required"] == ["local_fidelity_r2"]
    assert condition["else"]["not"]["required"] == ["local_fidelity_r2"]


def test_sum_check_is_mandatory_and_declares_applicability(schema_documents):
    sum_check = schema_documents["common.schema.json"]["$defs"]["ExplanationSumCheck"]
    assert "applicable" in sum_check["required"]
    assert set(sum_check["properties"]["margin_source"]["enum"]) == {
        "score.value",
        "score.raw_margin",
    }


def test_monitoring_response_carries_no_track_a_output(schema_documents):
    """A Track-B resource may never contain a Track-A output (D-039)."""
    response = schema_documents["monitoring_observation.response.schema.json"]
    properties = set(response["properties"])
    for forbidden in ("score", "target", "explanation", "model_id", "review_state"):
        assert forbidden not in properties


def test_track_a_response_requires_the_mandatory_fields(schema_documents):
    response = schema_documents["cad_tabular_prediction.response.schema.json"]
    required = set(response["required"])
    for field in (
        "contract_version",
        "data_class",
        "track",
        "request_id",
        "audit_id",
        "idempotent_replay",
        "model_id",
        "preprocessing_id",
        "calibration_id",
        "feature_schema_id",
        "explanation_config_id",
        "target",
        "score",
        "validation_status",
        "model_performance_ref",
        "explanation",
        "missing_features",
        "warnings",
        "provenance",
        "review_state",
        "disclaimer",
    ):
        assert field in required, field


def test_uncalibrated_model_must_serve_an_uncalibrated_score(schema_documents):
    response = schema_documents["cad_tabular_prediction.response.schema.json"]
    condition = response["allOf"][2]
    assert condition["if"]["properties"]["calibration_id"]["const"] == "none"
    assert (
        condition["then"]["properties"]["score"]["properties"]["type"]["const"]
        == "uncalibrated_score"
    )


def test_internal_only_model_cannot_reference_an_external_validation_section(schema_documents):
    response = schema_documents["cad_tabular_prediction.response.schema.json"]
    condition = response["allOf"][1]
    assert condition["if"]["properties"]["validation_status"]["const"] == "development_internal_only"
    assert condition["then"]["properties"]["model_performance_ref"]["pattern"] == "#internal_validation$"


def test_mock_responses_must_carry_the_exact_disclaimer(schema_documents):
    common = schema_documents["common.schema.json"]["$defs"]
    for key in ("MockDisclaimerTrackA", "MockDisclaimerTrackB"):
        text = common[key]["const"]
        assert text.startswith("MOCK / SYNTHETIC DATA")
        assert "not a medical diagnosis" in text
        assert "not a validated clinical output" in text
        assert "No model has been trained" in text


def test_error_catalogue_covers_the_phase0_codes(schema_documents):
    codes = set(schema_documents["common.schema.json"]["$defs"]["ErrorCode"]["enum"])
    required = {
        "malformed_request",
        "unknown_feature",
        "unit_mismatch",
        "value_out_of_range",
        "schema_model_mismatch",
        "wearable_input_not_valid_for_cad_inference",
        "idempotency_key_conflict",
        "model_unavailable",
        "internal_error",
        "missing_required_feature",
        "feature_not_in_schema",
    }
    assert required <= codes
