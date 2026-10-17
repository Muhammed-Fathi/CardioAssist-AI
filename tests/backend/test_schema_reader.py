"""Runtime schema-reader compatibility for ADR-001 Option A.

The approved ADR expresses an optional feature value as
``anyOf: [{"type": "null"}, <existing typed/ranged rule>]``. This module does
**not** change the committed schemas. It builds an in-memory copy of the
approved shape so that the runtime adapter can be tested before the separate
schema/fixture correction is reviewed and merged.

The acceptance rules under test are the ADR's safeguards: optional null is
"not provided", required null stays invalid, zero/false stay data, and wrong
types, invalid units and out-of-range values remain rejected.
"""

from __future__ import annotations

import copy

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from backend.app.contracts import ContractFiles, ContractViolation
from backend.app.validation import feature_rules, typed_value_rule, validate_features

CAD = "/v1/predictions/cad-tabular"
KEY = {"Idempotency-Key": "adr-001-prerequisite-key-001"}

SCHEMA_IDS = ("mock_clinical_v1", "mock_clinical_v2")

REQUIRED_VALUES = {
    "mock_feature_demographic_age": 50,
    "mock_feature_demographic_sex": "category_a",
    "mock_feature_fraction": 0.5,
}

REQUIRED_UNITS = {
    "mock_feature_demographic_age": "u_years",
    "mock_feature_demographic_sex": "u_category",
    "mock_feature_fraction": "u_fraction",
}

OPTIONAL_VALUES = {
    "mock_feature_vital_systolic": 120,
    "mock_feature_lab_concentration": 200,
    "mock_feature_binary_flag": True,
    "mock_feature_count": 3,
    "mock_feature_fraction": 0.5,
}

OPTIONAL_UNITS = {
    "mock_feature_vital_systolic": "u_pressure",
    "mock_feature_lab_concentration": "u_concentration",
    "mock_feature_binary_flag": "u_boolean",
    "mock_feature_count": "u_count",
    "mock_feature_fraction": "u_fraction",
}

ZERO_VALUES = {
    "mock_feature_vital_systolic": 0,
    "mock_feature_lab_concentration": 0,
    "mock_feature_binary_flag": False,
    "mock_feature_count": 0,
    "mock_feature_fraction": 0,
}


@pytest.fixture(scope="module")
def contracts() -> ContractFiles:
    return ContractFiles()


def corrected_schema(contracts: ContractFiles, schema_id: str) -> dict:
    """In-memory copy with the exact ADR-001 optional-slot ``anyOf`` shape."""
    schema = copy.deepcopy(contracts.feature_schemas[schema_id])
    required = set(schema["required"])
    for name, definition in schema["properties"].items():
        if name in required:
            continue
        value_rule = definition["allOf"][1]["properties"]["value"]
        assert "type" in value_rule, name
        definition["allOf"][1]["properties"]["value"] = {
            "anyOf": [{"type": "null"}, value_rule]
        }
    return schema


def feature_map(schema_id: str, **overrides) -> dict:
    features = {}
    required = ["mock_feature_demographic_age", "mock_feature_demographic_sex"]
    if schema_id == "mock_clinical_v2":
        required.append("mock_feature_fraction")
    for name in required:
        features[name] = {"value": REQUIRED_VALUES[name], "unit": REQUIRED_UNITS[name]}
    features.update(overrides)
    return features


def optional_slots(contracts: ContractFiles, schema_id: str) -> list[str]:
    schema = contracts.feature_schemas[schema_id]
    return sorted(
        name for name in schema["properties"] if name not in set(schema["required"])
    )


# --------------------------------------------------------------------------- #
# adapter mechanics
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("schema_id", SCHEMA_IDS)
def test_adapter_is_a_no_op_for_the_current_committed_schemas(contracts, schema_id):
    """The adapter must not reinterpret the schemas that are live today."""
    schema = contracts.feature_schemas[schema_id]
    for name, definition in schema["properties"].items():
        rules = feature_rules(definition)
        assert set(rules) == {"value", "unit"}, name
        assert "type" in rules["value"], name
        assert "anyOf" not in rules["value"], name


@pytest.mark.parametrize("schema_id", SCHEMA_IDS)
def test_adapter_selects_the_single_typed_alternative(contracts, schema_id):
    corrected = corrected_schema(contracts, schema_id)
    for name, definition in corrected["properties"].items():
        value_rule = feature_rules(definition)["value"]
        assert "anyOf" not in value_rule, name
        assert "type" in value_rule, name
        if name not in corrected["required"]:
            assert value_rule["type"] != "null", name


@pytest.mark.parametrize(
    "rule",
    [
        {"anyOf": [{"type": "null"}, {"type": "number", "minimum": 0, "maximum": 1}]},
        {"anyOf": [{"type": "number", "minimum": 0, "maximum": 1}, {"type": "null"}]},
    ],
    ids=["null-first", "typed-first"],
)
def test_adapter_accepts_only_the_exact_nullable_shape(rule):
    """Both orderings are semantically identical to the approved shape."""
    assert typed_value_rule(rule) == {"type": "number", "minimum": 0, "maximum": 1}


def test_adapter_leaves_direct_type_rules_unchanged():
    rule = {"type": "integer", "minimum": 0, "maximum": 100}
    assert typed_value_rule(rule) is rule
    assert feature_rules({"allOf": [{"properties": {"value": rule}}]})["value"] is rule


@pytest.mark.parametrize(
    "rule",
    [
        # No typed alternative.
        {"anyOf": [{"type": "null"}, {"const": 1}]},
        # Missing null alternative.
        {"anyOf": [{"type": "number"}, {"type": "string"}]},
        # Extra alternative beyond the approved pair.
        {"anyOf": [{"type": "null"}, {"type": "number"}, {"type": "string"}]},
        # Null alternative is not exactly {"type": "null"}.
        {"anyOf": [{"type": "null", "description": "not provided"}, {"type": "number"}]},
        # Non-string type (the runtime expects a single type token).
        {"anyOf": [{"type": "null"}, {"type": ["number", "null"]}]},
        # Outer constraints would be silently discarded by unwrapping.
        {"anyOf": [{"type": "null"}, {"type": "number"}], "minimum": 0},
        {"anyOf": [{"type": "null"}, {"type": "number"}], "description": "sibling"},
        # Not a list of alternatives.
        {"anyOf": {"type": "null"}},
        # More than two alternatives.
        {"anyOf": [{"type": "null"}, {"type": "number"}, {"type": "null"}]},
    ],
    ids=[
        "no-typed-alternative",
        "missing-null",
        "extra-alternative",
        "inexact-null",
        "non-string-type",
        "outer-minimum",
        "outer-description",
        "anyof-not-list",
        "three-alternatives",
    ],
)
def test_adapter_fails_closed_for_unexpected_shapes(rule):
    """Unexpected structures are not reinterpreted as the approved shape."""
    assert typed_value_rule(rule) is rule
    assert feature_rules({"allOf": [{"properties": {"value": rule}}]})["value"] is rule


# --------------------------------------------------------------------------- #
# corrected-shape semantics through the runtime validator
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("schema_id", SCHEMA_IDS)
def test_every_optional_slot_still_accepts_its_valid_non_null_value(
    contracts, schema_id
):
    corrected = corrected_schema(contracts, schema_id)
    for name in optional_slots(contracts, schema_id):
        features = feature_map(
            schema_id, **{name: {"value": OPTIONAL_VALUES[name], "unit": OPTIONAL_UNITS[name]}}
        )
        provided, missing = validate_features(contracts, corrected, features)
        assert name in provided, name
        assert name not in missing, name


@pytest.mark.parametrize("schema_id", SCHEMA_IDS)
def test_every_optional_slot_accepts_explicit_null_as_not_provided(contracts, schema_id):
    corrected = corrected_schema(contracts, schema_id)
    for name in optional_slots(contracts, schema_id):
        features = feature_map(
            schema_id, **{name: {"value": None, "unit": OPTIONAL_UNITS[name]}}
        )
        provided, missing = validate_features(contracts, corrected, features)
        assert name not in provided, name
        assert name in missing, name


@pytest.mark.parametrize("schema_id", SCHEMA_IDS)
def test_every_required_slot_remains_non_nullable(contracts, schema_id):
    corrected = corrected_schema(contracts, schema_id)
    required = contracts.feature_schemas[schema_id]["required"]
    for name in required:
        for features in (
            feature_map(schema_id, **{name: {"value": None, "unit": REQUIRED_UNITS[name]}}),
            {
                feature: payload
                for feature, payload in feature_map(schema_id).items()
                if feature != name
            },
        ):
            with pytest.raises(ContractViolation) as excinfo:
                validate_features(contracts, corrected, features)
            assert excinfo.value.status == 422
            assert excinfo.value.code == "missing_required_feature"


@pytest.mark.parametrize("schema_id", SCHEMA_IDS)
def test_zero_and_false_remain_data(contracts, schema_id):
    corrected = corrected_schema(contracts, schema_id)
    for name in optional_slots(contracts, schema_id):
        features = feature_map(
            schema_id, **{name: {"value": ZERO_VALUES[name], "unit": OPTIONAL_UNITS[name]}}
        )
        provided, missing = validate_features(contracts, corrected, features)
        assert name in provided, name
        assert name not in missing, name


@pytest.mark.parametrize(
    "schema_id,name,value,status,code",
    [
        ("mock_clinical_v1", "mock_feature_vital_systolic", "120", 400, "malformed_request"),
        ("mock_clinical_v1", "mock_feature_count", 1.5, 400, "malformed_request"),
        ("mock_clinical_v1", "mock_feature_binary_flag", 1, 400, "malformed_request"),
        ("mock_clinical_v1", "mock_feature_fraction", "0.5", 400, "malformed_request"),
        ("mock_clinical_v1", "mock_feature_vital_systolic", 401, 422, "value_out_of_range"),
        ("mock_clinical_v1", "mock_feature_lab_concentration", 2001, 422, "value_out_of_range"),
        ("mock_clinical_v1", "mock_feature_count", 101, 422, "value_out_of_range"),
        ("mock_clinical_v1", "mock_feature_fraction", 2, 422, "value_out_of_range"),
        ("mock_clinical_v2", "mock_feature_count", -1, 422, "value_out_of_range"),
        ("mock_clinical_v2", "mock_feature_binary_flag", "true", 400, "malformed_request"),
    ],
)
def test_invalid_non_null_values_are_not_broadened(
    contracts, schema_id, name, value, status, code
):
    corrected = corrected_schema(contracts, schema_id)
    features = feature_map(
        schema_id, **{name: {"value": value, "unit": OPTIONAL_UNITS[name]}}
    )
    with pytest.raises(ContractViolation) as excinfo:
        validate_features(contracts, corrected, features)
    assert excinfo.value.status == status
    assert excinfo.value.code == code
    assert excinfo.value.details[0]["field"] == f"features.{name}.value"


@pytest.mark.parametrize("schema_id", SCHEMA_IDS)
def test_invalid_units_are_not_broadened(contracts, schema_id):
    corrected = corrected_schema(contracts, schema_id)
    features = feature_map(
        schema_id,
        **{
            "mock_feature_vital_systolic": {"value": 120, "unit": "u_weight"},
        },
    )
    with pytest.raises(ContractViolation) as excinfo:
        validate_features(contracts, corrected, features)
    assert excinfo.value.status == 422
    assert excinfo.value.code == "unit_mismatch"


# --------------------------------------------------------------------------- #
# the same acceptance matrix under Draft 2020-12
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("schema_id", SCHEMA_IDS)
def test_corrected_shape_under_draft_2020_12(contracts, schema_id):
    corrected = corrected_schema(contracts, schema_id)
    validator = Draft202012Validator(corrected)

    for name in optional_slots(contracts, schema_id):
        validator.validate(
            feature_map(schema_id, **{name: {"value": None, "unit": OPTIONAL_UNITS[name]}})
        )
        validator.validate(
            feature_map(
                schema_id, **{name: {"value": OPTIONAL_VALUES[name], "unit": OPTIONAL_UNITS[name]}}
            )
        )
        absent = feature_map(schema_id)
        assert name not in absent
        validator.validate(absent)

    with pytest.raises(ValidationError):
        validator.validate(
            feature_map(
                schema_id,
                **{
                    "mock_feature_vital_systolic": {"value": 401, "unit": "u_pressure"}
                },
            )
        )
    for name in contracts.feature_schemas[schema_id]["required"]:
        with pytest.raises(ValidationError):
            validator.validate(
                feature_map(schema_id, **{name: {"value": None, "unit": REQUIRED_UNITS[name]}})
            )


# --------------------------------------------------------------------------- #
# full HTTP path with the future shape, without changing committed schemas
# --------------------------------------------------------------------------- #
def test_http_path_uses_the_adapter_for_non_null_and_null_optional_values(
    client, http_app, cad_body
):
    state = http_app.state.mock
    state.contracts.feature_schemas["mock_clinical_v1"] = corrected_schema(
        state.contracts, "mock_clinical_v1"
    )

    cad_body["features"]["mock_feature_count"] = {"value": 7, "unit": "u_count"}
    accepted = client.post(CAD, json=cad_body, headers=KEY)
    assert accepted.status_code == 200
    assert "mock_feature_count" not in accepted.json()["missing_features"]

    cad_body["features"]["mock_feature_count"] = {"value": None, "unit": "u_count"}
    with_null = client.post(
        CAD, json=cad_body, headers={"Idempotency-Key": "adr-001-prerequisite-null"}
    )
    assert with_null.status_code == 200
    body = with_null.json()
    assert "mock_feature_count" in body["missing_features"]
    assert "imputed_feature:mock_feature_count" in body["warnings"]
    assert "mock_feature_count" not in {
        contribution["feature"] for contribution in body["explanation"]["contributions"]
    }
