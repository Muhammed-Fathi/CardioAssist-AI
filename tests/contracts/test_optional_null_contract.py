"""ADR-001 Option A: the optional-null semantics of the mock feature schemas.

An explicit ``null`` for an **optional** feature means "not provided" (Phase 0
§R2-6.2), so it must behave exactly like an omitted feature: the request is
accepted, the feature is reported in ``missing_features`` with its
``imputed_feature:`` warning, and it contributes nothing to the explanation.

This module is written against the **contract**, not against the oracle's
internals. It checks three independent layers for **every** affected optional
slot of **both** mock feature schemas (5 in v1, 4 in v2 — nine in total):

* the deterministic reference oracle (``reference_contract.py``);
* the committed JSON Schemas under Draft 2020-12;
* the idempotency rules of the canonical-payload hash.

Required features stay non-nullable: an omitted or an explicitly null
required feature is still ``422 missing_required_feature``.
"""

from __future__ import annotations

import copy

import pytest
from jsonschema.exceptions import ValidationError

from conftest import validator_for
import reference_contract as rc

CAD = "POST /v1/predictions/cad-tabular"

#: The two mock feature schemas and the model each one is bound to.
SCHEMA_IDS = ("mock_clinical_v1", "mock_clinical_v2")

MODEL_IDS = {
    "mock_clinical_v1": "mock_model_a_v0.1.0",
    "mock_clinical_v2": "mock_model_b_v0.1.0",
}

#: A valid, non-null value and unit for every slot of both schemas.
REQUIRED_SLOTS = {
    "mock_clinical_v1": {
        "mock_feature_demographic_age": {"value": 51, "unit": "u_years"},
        "mock_feature_demographic_sex": {"value": "category_c", "unit": "u_category"},
    },
    "mock_clinical_v2": {
        "mock_feature_demographic_age": {"value": 51, "unit": "u_years"},
        "mock_feature_demographic_sex": {"value": "category_c", "unit": "u_category"},
        "mock_feature_fraction": {"value": 0.25, "unit": "u_fraction"},
    },
}

OPTIONAL_SLOTS = {
    "mock_clinical_v1": {
        "mock_feature_vital_systolic": {"value": 118, "unit": "u_pressure"},
        "mock_feature_lab_concentration": {"value": 190, "unit": "u_concentration"},
        "mock_feature_binary_flag": {"value": True, "unit": "u_boolean"},
        "mock_feature_count": {"value": 4, "unit": "u_count"},
        "mock_feature_fraction": {"value": 0.25, "unit": "u_fraction"},
    },
    "mock_clinical_v2": {
        "mock_feature_vital_systolic": {"value": 118, "unit": "u_pressure"},
        "mock_feature_lab_concentration": {"value": 190, "unit": "u_concentration"},
        "mock_feature_binary_flag": {"value": True, "unit": "u_boolean"},
        "mock_feature_count": {"value": 4, "unit": "u_count"},
    },
}

#: Every affected optional slot, across both schema versions.
EVERY_OPTIONAL_SLOT = [
    (schema_id, name)
    for schema_id in SCHEMA_IDS
    for name in OPTIONAL_SLOTS[schema_id]
]

#: Every required slot, across both schema versions.
EVERY_REQUIRED_SLOT = [
    (schema_id, name)
    for schema_id in SCHEMA_IDS
    for name in REQUIRED_SLOTS[schema_id]
]

#: The optional numeric slots (a value of 0 is data) and the optional boolean
#: slot (a value of false is data).
EVERY_NUMERIC_OPTIONAL_SLOT = [
    (schema_id, name)
    for schema_id, name in EVERY_OPTIONAL_SLOT
    if OPTIONAL_SLOTS[schema_id][name]["value"] is not True
]
EVERY_BOOLEAN_OPTIONAL_SLOT = [
    (schema_id, name)
    for schema_id, name in EVERY_OPTIONAL_SLOT
    if OPTIONAL_SLOTS[schema_id][name]["value"] is True
]

#: A value of the wrong type for each optional slot, and the value that leaves
#: the slot's original range. The boolean slot declares no range.
WRONG_TYPE = {
    "mock_feature_vital_systolic": "118",
    "mock_feature_lab_concentration": "190",
    "mock_feature_binary_flag": 1,
    "mock_feature_count": 1.5,
    "mock_feature_fraction": "0.25",
}

OUT_OF_RANGE = {
    "mock_feature_vital_systolic": 401,
    "mock_feature_lab_concentration": 2001,
    "mock_feature_count": 101,
    "mock_feature_fraction": 2,
}

CONTEXT = {
    "source": "benchmark_import",
    "recorded_at": "2026-10-16T09:00:00Z",
    "patient_ref": "pseudo_adr001",
    "consent_id": "consent_mock_001",
}


def cad_body(schema_id, features):
    """A minimal valid request for one schema version."""
    return {
        "contract_version": "v1",
        "request_id": "018f3c2a-7b1e-7c4d-8f21-0000000000a1",
        "model_id": MODEL_IDS[schema_id],
        "feature_schema_id": schema_id,
        "features": copy.deepcopy(features),
        "context": copy.deepcopy(CONTEXT),
    }


def oracle(body, headers=None):
    """Run the deterministic oracle on a fresh instance."""
    return rc.ReferenceContract().handle(CAD, body, headers or {})


def request_validator(schema_documents, registry):
    return validator_for(
        schema_documents["cad_tabular_prediction.request.schema.json"], registry
    )


# --------------------------------------------------------------------------- #
# 1. an optional feature: omitted, explicitly null, zero, false
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("schema_id,name", EVERY_OPTIONAL_SLOT)
def test_an_omitted_optional_feature_is_accepted_and_reported_as_missing(schema_id, name):
    features = dict(REQUIRED_SLOTS[schema_id])
    status, body = oracle(cad_body(schema_id, features))
    assert status == 200
    assert name in body["missing_features"]
    assert f"imputed_feature:{name}" in body["warnings"]
    assert name not in {item["feature"] for item in body["explanation"]["contributions"]}


@pytest.mark.parametrize("schema_id,name", EVERY_OPTIONAL_SLOT)
def test_an_explicitly_null_optional_feature_is_accepted_and_reported_as_missing(
    schema_id, name
):
    features = dict(REQUIRED_SLOTS[schema_id])
    features[name] = {"value": None, "unit": OPTIONAL_SLOTS[schema_id][name]["unit"]}
    status, body = oracle(cad_body(schema_id, features))
    assert status == 200
    assert name in body["missing_features"]
    assert f"imputed_feature:{name}" in body["warnings"]
    assert name not in {item["feature"] for item in body["explanation"]["contributions"]}


@pytest.mark.parametrize("schema_id,name", EVERY_OPTIONAL_SLOT)
def test_an_omitted_and_an_explicitly_null_optional_feature_are_equivalent(
    schema_id, name
):
    """Only the identifiers may differ; the semantics may not."""
    omitted = cad_body(schema_id, dict(REQUIRED_SLOTS[schema_id]))
    nulled = cad_body(schema_id, dict(REQUIRED_SLOTS[schema_id]))
    nulled["features"][name] = {
        "value": None, "unit": OPTIONAL_SLOTS[schema_id][name]["unit"]
    }
    omitted_status, omitted_body = oracle(omitted)
    null_status, null_body = oracle(nulled)
    assert omitted_status == null_status == 200
    assert omitted_body["missing_features"] == null_body["missing_features"]
    assert omitted_body["warnings"] == null_body["warnings"]
    assert omitted_body["score"] == null_body["score"]
    assert omitted_body["explanation"] == null_body["explanation"]
    # The identifiers legitimately differ: the payloads are not the same.
    assert omitted_body["audit_id"] != null_body["audit_id"]


@pytest.mark.parametrize("schema_id,name", EVERY_NUMERIC_OPTIONAL_SLOT)
def test_a_zero_optional_value_is_data_and_never_missing(schema_id, name):
    slot = OPTIONAL_SLOTS[schema_id][name]
    features = dict(REQUIRED_SLOTS[schema_id])
    features[name] = {"value": 0, "unit": slot["unit"]}
    status, body = oracle(cad_body(schema_id, features))
    assert status == 200
    assert name not in body["missing_features"]
    assert f"imputed_feature:{name}" not in body["warnings"]
    contributions = {item["feature"]: item["value"] for item in body["explanation"]["contributions"]}
    assert contributions[name] == 0


@pytest.mark.parametrize("schema_id,name", EVERY_BOOLEAN_OPTIONAL_SLOT)
def test_a_false_optional_value_is_data_and_never_missing(schema_id, name):
    """`false` is data, exactly like `0` — never a missing feature."""
    slot = OPTIONAL_SLOTS[schema_id][name]
    features = dict(REQUIRED_SLOTS[schema_id])
    features[name] = {"value": False, "unit": slot["unit"]}
    status, body = oracle(cad_body(schema_id, features))
    assert status == 200
    assert name not in body["missing_features"]
    assert f"imputed_feature:{name}" not in body["warnings"]
    contributions = {item["feature"]: item["value"] for item in body["explanation"]["contributions"]}
    assert contributions[name] is False


@pytest.mark.parametrize("schema_id,name", EVERY_OPTIONAL_SLOT)
def test_a_wrong_non_null_type_is_rejected(schema_id, name):
    features = dict(REQUIRED_SLOTS[schema_id])
    features[name] = {"value": WRONG_TYPE[name], "unit": OPTIONAL_SLOTS[schema_id][name]["unit"]}
    status, body = oracle(cad_body(schema_id, features))
    assert status == 400
    assert body["error"]["code"] == "malformed_request"
    assert "score" not in body


@pytest.mark.parametrize("schema_id,name", EVERY_OPTIONAL_SLOT)
def test_an_invalid_unit_is_rejected(schema_id, name):
    features = dict(REQUIRED_SLOTS[schema_id])
    features[name] = {"value": OPTIONAL_SLOTS[schema_id][name]["value"], "unit": "u_weight"}
    status, body = oracle(cad_body(schema_id, features))
    assert status == 422
    assert body["error"]["code"] == "unit_mismatch"
    assert "score" not in body


@pytest.mark.parametrize(
    "schema_id,name",
    [(schema_id, name) for schema_id, name in EVERY_OPTIONAL_SLOT if name in OUT_OF_RANGE],
)
def test_a_value_outside_the_original_range_is_rejected(schema_id, name):
    features = dict(REQUIRED_SLOTS[schema_id])
    features[name] = {"value": OUT_OF_RANGE[name], "unit": OPTIONAL_SLOTS[schema_id][name]["unit"]}
    status, body = oracle(cad_body(schema_id, features))
    assert status == 422
    assert body["error"]["code"] == "value_out_of_range"
    assert "score" not in body


@pytest.mark.parametrize("schema_id,name", EVERY_OPTIONAL_SLOT)
def test_a_previously_valid_optional_value_is_unchanged(schema_id, name):
    """The correction must not change what a valid non-null value does."""
    features = dict(REQUIRED_SLOTS[schema_id])
    features[name] = copy.deepcopy(OPTIONAL_SLOTS[schema_id][name])
    status, body = oracle(cad_body(schema_id, features))
    assert status == 200
    assert name not in body["missing_features"]
    contributions = {item["feature"]: item["value"] for item in body["explanation"]["contributions"]}
    assert contributions[name] == OPTIONAL_SLOTS[schema_id][name]["value"]


# --------------------------------------------------------------------------- #
# 2. a required feature: omitted and explicitly null stay rejections
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("schema_id,name", EVERY_REQUIRED_SLOT)
def test_an_omitted_required_feature_is_still_rejected(schema_id, name):
    features = {
        feature: payload
        for feature, payload in REQUIRED_SLOTS[schema_id].items()
        if feature != name
    }
    status, body = oracle(cad_body(schema_id, features))
    assert status == 422
    assert body["error"]["code"] == "missing_required_feature"
    assert body["error"]["details"][0]["feature_id"] == name
    assert "score" not in body


@pytest.mark.parametrize("schema_id,name", EVERY_REQUIRED_SLOT)
def test_an_explicitly_null_required_feature_is_still_rejected(schema_id, name):
    features = dict(REQUIRED_SLOTS[schema_id])
    features[name] = {"value": None, "unit": REQUIRED_SLOTS[schema_id][name]["unit"]}
    status, body = oracle(cad_body(schema_id, features))
    assert status == 422
    assert body["error"]["code"] == "missing_required_feature"
    assert body["error"]["details"][0]["feature_id"] == name
    assert "score" not in body


# --------------------------------------------------------------------------- #
# 3. the same matrix under Draft 2020-12
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("schema_id,name", EVERY_OPTIONAL_SLOT)
def test_the_omitted_and_the_null_optional_feature_are_schema_valid(
    schema_id, name, schema_documents, registry
):
    validator = request_validator(schema_documents, registry)
    validator.validate(cad_body(schema_id, dict(REQUIRED_SLOTS[schema_id])))
    nulled = cad_body(schema_id, dict(REQUIRED_SLOTS[schema_id]))
    nulled["features"][name] = {
        "value": None, "unit": OPTIONAL_SLOTS[schema_id][name]["unit"]
    }
    validator.validate(nulled)


@pytest.mark.parametrize("schema_id,name", EVERY_OPTIONAL_SLOT)
def test_the_schema_rejects_a_wrong_type_an_invalid_unit_and_an_out_of_range_value(
    schema_id, name, schema_documents, registry
):
    validator = request_validator(schema_documents, registry)
    unit = OPTIONAL_SLOTS[schema_id][name]["unit"]

    wrong_type = cad_body(schema_id, dict(REQUIRED_SLOTS[schema_id]))
    wrong_type["features"][name] = {"value": WRONG_TYPE[name], "unit": unit}
    with pytest.raises(ValidationError):
        validator.validate(wrong_type)

    wrong_unit = cad_body(schema_id, dict(REQUIRED_SLOTS[schema_id]))
    wrong_unit["features"][name] = {"value": OPTIONAL_SLOTS[schema_id][name]["value"], "unit": "u_weight"}
    with pytest.raises(ValidationError):
        validator.validate(wrong_unit)

    if name in OUT_OF_RANGE:
        out_of_range = cad_body(schema_id, dict(REQUIRED_SLOTS[schema_id]))
        out_of_range["features"][name] = {"value": OUT_OF_RANGE[name], "unit": unit}
        with pytest.raises(ValidationError):
            validator.validate(out_of_range)


@pytest.mark.parametrize("schema_id,name", EVERY_REQUIRED_SLOT)
def test_the_schema_still_rejects_an_omitted_or_a_null_required_feature(
    schema_id, name, schema_documents, registry
):
    validator = request_validator(schema_documents, registry)
    omitted = cad_body(
        schema_id,
        {
            feature: payload
            for feature, payload in REQUIRED_SLOTS[schema_id].items()
            if feature != name
        },
    )
    with pytest.raises(ValidationError):
        validator.validate(omitted)

    nulled = cad_body(schema_id, dict(REQUIRED_SLOTS[schema_id]))
    nulled["features"][name] = {"value": None, "unit": REQUIRED_SLOTS[schema_id][name]["unit"]}
    with pytest.raises(ValidationError):
        validator.validate(nulled)


# --------------------------------------------------------------------------- #
# 4. idempotency around the null/absent distinction
# --------------------------------------------------------------------------- #
def test_an_omitted_and_an_explicitly_null_payload_are_distinct_for_the_hash():
    """The canonical payload hash keeps null and absent apart."""
    omitted = cad_body("mock_clinical_v1", dict(REQUIRED_SLOTS["mock_clinical_v1"]))
    nulled = cad_body("mock_clinical_v1", dict(REQUIRED_SLOTS["mock_clinical_v1"]))
    nulled["features"]["mock_feature_count"] = {"value": None, "unit": "u_count"}
    assert rc.payload_hash(omitted) != rc.payload_hash(nulled)
    # request_id is informational and never part of the hash.
    same = cad_body("mock_clinical_v1", dict(REQUIRED_SLOTS["mock_clinical_v1"]))
    same["request_id"] = "018f3c2a-7b1e-7c4d-8f21-0000000000a2"
    assert rc.payload_hash(same) == rc.payload_hash(omitted)


def test_the_same_key_with_an_omitted_and_a_null_payload_is_a_conflict():
    """One key, two different canonical payloads: the existing 409."""
    contract = rc.ReferenceContract()
    headers = {"Idempotency-Key": "adr-001-contract-conflict-01"}
    omitted = cad_body("mock_clinical_v1", dict(REQUIRED_SLOTS["mock_clinical_v1"]))
    status, first = contract.handle(CAD, omitted, headers)
    assert status == 200
    assert first["idempotent_replay"] is False

    nulled = cad_body("mock_clinical_v1", dict(REQUIRED_SLOTS["mock_clinical_v1"]))
    nulled["features"]["mock_feature_count"] = {"value": None, "unit": "u_count"}
    status, conflict = contract.handle(CAD, nulled, headers)
    assert status == 409
    assert conflict["error"]["code"] == "idempotency_key_conflict"
    assert conflict["error"]["original_audit_id"] == first["audit_id"]
    # A conflict performs no inference and creates no audit event.
    assert contract.inference_count == 1
    assert contract.audit_events == [first["audit_id"]]


def test_a_replay_of_a_null_payload_is_not_a_second_write():
    """Same key + identical payload: the stored response, no second write."""
    contract = rc.ReferenceContract()
    headers = {"Idempotency-Key": "adr-001-contract-replay-0001"}
    body = cad_body("mock_clinical_v1", dict(REQUIRED_SLOTS["mock_clinical_v1"]))
    body["features"]["mock_feature_count"] = {"value": None, "unit": "u_count"}
    first_status, first = contract.handle(CAD, body, headers)
    second_status, second = contract.handle(CAD, body, headers)
    assert first_status == second_status == 200
    assert first["idempotent_replay"] is False
    assert second["idempotent_replay"] is True
    assert second["audit_id"] == first["audit_id"]
    assert contract.inference_count == 1
    assert contract.audit_events == [first["audit_id"]]


def test_the_oracle_stays_deterministic_across_the_null_and_omitted_forms():
    """Two independent runs of the same request agree byte for byte."""
    for schema_id in SCHEMA_IDS:
        body = cad_body(schema_id, dict(REQUIRED_SLOTS[schema_id]))
        _, first = oracle(body)
        _, second = oracle(body)
        assert first == second
