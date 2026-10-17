"""ADR-001 Option A over HTTP: the optional-null semantics of the mock backend.

These are the wire-level checks of the approved correction. They use the
real ASGI app (never the fixture oracle) and cover **both** mock feature
schemas and **every** affected optional slot:

* an omitted optional feature and an explicitly null optional feature produce
  the same missing-feature and warning semantics;
* a required feature stays non-nullable: omitted or null is still
  ``422 missing_required_feature``;
* zero and false stay data; wrong types, invalid units and out-of-range
  values stay rejected;
* the canonical-payload hash keeps null and absent apart, so a replay is
  still a replay and a changed payload is still a 409.
"""

from __future__ import annotations

import copy

import pytest

CAD = "/v1/predictions/cad-tabular"

REQUIRED = {
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

OPTIONAL = {
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

MODEL_IDS = {
    "mock_clinical_v1": "mock_model_a_v0.1.0",
    "mock_clinical_v2": "mock_model_b_v0.1.0",
}

EVERY_OPTIONAL_SLOT = [
    (schema_id, name)
    for schema_id in ("mock_clinical_v1", "mock_clinical_v2")
    for name in OPTIONAL[schema_id]
]

EVERY_REQUIRED_SLOT = [
    (schema_id, name)
    for schema_id in ("mock_clinical_v1", "mock_clinical_v2")
    for name in REQUIRED[schema_id]
]


def body_for(schema_id, features):
    return {
        "contract_version": "v1",
        "request_id": "cccccccc-3333-4333-8333-333333333333",
        "model_id": MODEL_IDS[schema_id],
        "feature_schema_id": schema_id,
        "features": copy.deepcopy(features),
        "context": {
            "source": "benchmark_import",
            "recorded_at": "2026-10-16T10:20:00Z",
            "patient_ref": "pseudo_http_demo",
        },
    }


def key_for(label):
    return {"Idempotency-Key": f"adr-001-http-{label}"}


def contributions(response):
    return {item["feature"]: item["value"] for item in response["explanation"]["contributions"]}


# --------------------------------------------------------------------------- #
# optional features
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("schema_id,name", EVERY_OPTIONAL_SLOT)
def test_an_omitted_optional_feature_is_accepted_and_reported_as_missing(
    client, schema_id, name
):
    body = body_for(schema_id, REQUIRED[schema_id])
    response = client.post(CAD, json=body, headers=key_for(f"omitted-{schema_id}-{name}"))
    assert response.status_code == 200
    payload = response.json()
    assert name in payload["missing_features"]
    assert f"imputed_feature:{name}" in payload["warnings"]
    assert name not in contributions(payload)


@pytest.mark.parametrize("schema_id,name", EVERY_OPTIONAL_SLOT)
def test_an_explicitly_null_optional_feature_is_accepted_and_reported_as_missing(
    client, schema_id, name
):
    features = dict(REQUIRED[schema_id])
    features[name] = {"value": None, "unit": OPTIONAL[schema_id][name]["unit"]}
    body = body_for(schema_id, features)
    response = client.post(CAD, json=body, headers=key_for(f"null-{schema_id}-{name}"))
    assert response.status_code == 200
    payload = response.json()
    assert name in payload["missing_features"]
    assert f"imputed_feature:{name}" in payload["warnings"]
    assert name not in contributions(payload)


@pytest.mark.parametrize("schema_id,name", EVERY_OPTIONAL_SLOT)
def test_an_omitted_and_an_explicitly_null_optional_feature_agree(
    client, schema_id, name
):
    """The missing-feature and warning semantics are identical."""
    omitted = body_for(schema_id, REQUIRED[schema_id])
    features = dict(REQUIRED[schema_id])
    features[name] = {"value": None, "unit": OPTIONAL[schema_id][name]["unit"]}
    nulled = body_for(schema_id, features)

    first = client.post(CAD, json=omitted, headers=key_for(f"agree-omitted-{name}")).json()
    second = client.post(CAD, json=nulled, headers=key_for(f"agree-null-{name}")).json()

    assert first["missing_features"] == second["missing_features"]
    assert first["warnings"] == second["warnings"]
    assert first["score"] == second["score"]
    assert first["explanation"] == second["explanation"]
    # The identifiers may legitimately differ: the canonical payloads differ.
    assert first["audit_id"] != second["audit_id"]


@pytest.mark.parametrize("schema_id,name", EVERY_OPTIONAL_SLOT)
def test_a_zero_or_false_optional_value_is_kept_as_data(client, schema_id, name):
    slot = OPTIONAL[schema_id][name]
    features = dict(REQUIRED[schema_id])
    features[name] = {"value": 0 if slot["value"] is not True else False, "unit": slot["unit"]}
    body = body_for(schema_id, features)
    response = client.post(CAD, json=body, headers=key_for(f"zero-{schema_id}-{name}"))
    assert response.status_code == 200
    payload = response.json()
    assert name not in payload["missing_features"]
    expected = 0 if slot["value"] is not True else False
    assert contributions(payload)[name] == expected


@pytest.mark.parametrize("schema_id,name", EVERY_OPTIONAL_SLOT)
def test_a_wrong_non_null_type_is_rejected(client, schema_id, name):
    wrong = {
        "mock_feature_vital_systolic": "118",
        "mock_feature_lab_concentration": "190",
        "mock_feature_binary_flag": 1,
        "mock_feature_count": 1.5,
        "mock_feature_fraction": "0.25",
    }[name]
    features = dict(REQUIRED[schema_id])
    features[name] = {"value": wrong, "unit": OPTIONAL[schema_id][name]["unit"]}
    body = body_for(schema_id, features)
    response = client.post(CAD, json=body, headers=key_for(f"type-{schema_id}-{name}"))
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "malformed_request"


@pytest.mark.parametrize("schema_id,name", EVERY_OPTIONAL_SLOT)
def test_an_invalid_unit_is_rejected(client, schema_id, name):
    features = dict(REQUIRED[schema_id])
    features[name] = {"value": OPTIONAL[schema_id][name]["value"], "unit": "u_weight"}
    body = body_for(schema_id, features)
    response = client.post(CAD, json=body, headers=key_for(f"unit-{schema_id}-{name}"))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unit_mismatch"


@pytest.mark.parametrize(
    "schema_id,name",
    [
        (schema_id, name)
        for schema_id, name in EVERY_OPTIONAL_SLOT
        if name
        in {
            "mock_feature_vital_systolic",
            "mock_feature_lab_concentration",
            "mock_feature_count",
            "mock_feature_fraction",
        }
    ],
)
def test_a_value_outside_the_original_range_is_rejected(client, schema_id, name):
    out_of_range = {
        "mock_feature_vital_systolic": 401,
        "mock_feature_lab_concentration": 2001,
        "mock_feature_count": 101,
        "mock_feature_fraction": 2,
    }[name]
    features = dict(REQUIRED[schema_id])
    features[name] = {"value": out_of_range, "unit": OPTIONAL[schema_id][name]["unit"]}
    body = body_for(schema_id, features)
    response = client.post(CAD, json=body, headers=key_for(f"range-{schema_id}-{name}"))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "value_out_of_range"


# --------------------------------------------------------------------------- #
# required features
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("schema_id,name", EVERY_REQUIRED_SLOT)
def test_an_omitted_required_feature_is_still_rejected(client, schema_id, name):
    features = {
        feature: payload
        for feature, payload in REQUIRED[schema_id].items()
        if feature != name
    }
    body = body_for(schema_id, features)
    response = client.post(CAD, json=body, headers=key_for(f"req-omitted-{name}"))
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "missing_required_feature"
    assert error["details"][0]["feature_id"] == name


@pytest.mark.parametrize("schema_id,name", EVERY_REQUIRED_SLOT)
def test_an_explicitly_null_required_feature_is_still_rejected(client, schema_id, name):
    features = dict(REQUIRED[schema_id])
    features[name] = {"value": None, "unit": REQUIRED[schema_id][name]["unit"]}
    body = body_for(schema_id, features)
    response = client.post(CAD, json=body, headers=key_for(f"req-null-{name}"))
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "missing_required_feature"
    assert error["details"][0]["feature_id"] == name
    assert "score" not in response.json()


# --------------------------------------------------------------------------- #
# idempotency around the null/absent distinction
# --------------------------------------------------------------------------- #
def test_an_omitted_and_an_explicitly_null_payload_conflict_under_one_key(
    client, http_app
):
    """The canonical payload hash keeps null and absent apart: 409, not a replay."""
    key = {"Idempotency-Key": "adr-001-http-conflict-01"}
    omitted = body_for("mock_clinical_v1", REQUIRED["mock_clinical_v1"])
    first = client.post(CAD, json=omitted, headers=key)
    assert first.status_code == 200

    features = dict(REQUIRED["mock_clinical_v1"])
    features["mock_feature_count"] = {"value": None, "unit": "u_count"}
    nulled = body_for("mock_clinical_v1", features)
    second = client.post(CAD, json=nulled, headers=key)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "idempotency_key_conflict"
    assert second.json()["error"]["original_audit_id"] == first.json()["audit_id"]
    assert len(http_app.state.mock.audit_events) == 1
    assert http_app.state.mock.inference_count == 1


def test_a_replay_of_an_explicitly_null_payload_is_not_a_second_write(
    client, http_app
):
    key = {"Idempotency-Key": "adr-001-http-replay-0001"}
    features = dict(REQUIRED["mock_clinical_v1"])
    features["mock_feature_count"] = {"value": None, "unit": "u_count"}
    body = body_for("mock_clinical_v1", features)
    first = client.post(CAD, json=body, headers=key)
    second = client.post(CAD, json=body, headers=key)
    assert first.status_code == second.status_code == 200
    assert first.json()["idempotent_replay"] is False
    assert second.json()["idempotent_replay"] is True
    assert second.json()["audit_id"] == first.json()["audit_id"]
    assert len(http_app.state.mock.audit_events) == 1
    assert http_app.state.mock.inference_count == 1
