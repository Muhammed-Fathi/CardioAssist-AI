"""Hostile HTTP inputs, based on contract text and schemas, not the oracle."""

import copy
import json

import pytest

CAD = "/v1/predictions/cad-tabular"
MON = "/v1/monitoring/observations"
KEY = {"Idempotency-Key": "http-validation-key-001"}
DELETE = object()


def change(body, path, value):
    parts = path.split(".")
    node = body
    for part in parts[:-1]:
        node = node[int(part)] if isinstance(node, list) else node[part]
    leaf = parts[-1]
    if value is DELETE:
        del node[leaf]
    elif isinstance(node, list):
        node[int(leaf)] = copy.deepcopy(value)
    else:
        node[leaf] = copy.deepcopy(value)


def assert_error(response, status, code):
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code
    assert not {"score", "target", "explanation", "observation_id"} & response.json().keys()


CAD_ERRORS = [
    ("contract_version", "v2", 400, "unsupported_contract_version"),
    ("feature_schema_id", DELETE, 400, "malformed_request"),
    ("feature_schema_id", [], 400, "malformed_request"),
    ("feature_schema_id", "mock_not_known", 422, "unknown_feature_schema"),
    ("context", DELETE, 400, "malformed_request"),
    ("context", [], 400, "malformed_request"),
    ("features", DELETE, 400, "malformed_request"),
    ("features", [], 400, "malformed_request"),
    ("context.source", "patient_app_direct", 422, "invalid_context_source"),
    ("context.recorded_at", DELETE, 400, "malformed_request"),
    ("context.recorded_at", "not-a-time", 400, "malformed_request"),
    ("context.recorded_at", "2026-10-16T10:20:00", 400, "malformed_request"),
    ("context.patient_ref", "ordinary-identifier", 400, "malformed_request"),
    ("context.patient_ref", "pseudo_with@identifier", 400, "malformed_request"),
    ("context.extra_field", "not-allowed", 400, "malformed_request"),
    ("request_id", "not-a-uuid", 400, "malformed_request"),
    ("request_id", None, 400, "malformed_request"),
    ("model_id", [], 400, "malformed_request"),
    ("model_id", "mock_unknown", 422, "unknown_model"),
    ("model_id", "mock_model_b_v0.1.0", 422, "schema_model_mismatch"),
    ("model_id", "mock_model_e_v0.1.0", 503, "model_unavailable"),
    ("model_id", "mock_model_d_v0.1.0", 503, "model_unavailable"),
    ("features.mock_feature_demographic_age", DELETE, 422, "missing_required_feature"),
    ("features.mock_feature_demographic_age.value", None, 422, "missing_required_feature"),
    ("features.mock_feature_demographic_age.value", DELETE, 422, "missing_required_feature"),
    ("features.mock_feature_demographic_age.value", -1, 422, "value_out_of_range"),
    ("features.mock_feature_demographic_age.value", 201, 422, "value_out_of_range"),
    ("features.mock_feature_demographic_age.value", "43", 400, "malformed_request"),
    ("features.mock_feature_demographic_age.value", True, 400, "malformed_request"),
    ("features.mock_feature_demographic_age.value", 43.5, 400, "malformed_request"),
    ("features.mock_feature_demographic_age.unit", DELETE, 422, "unit_mismatch"),
    ("features.mock_feature_demographic_age.unit", "year", 422, "unit_mismatch"),
    ("features.mock_feature_demographic_age.entered_by", "unknown", 400, "malformed_request"),
    ("features.mock_feature_demographic_age.extra", True, 400, "malformed_request"),
    ("features.mock_feature_demographic_age", 43, 400, "malformed_request"),
    ("features.mock_feature_demographic_sex.value", "", 400, "malformed_request"),
    ("features.mock_feature_demographic_sex.value", "x" * 33, 400, "malformed_request"),
    ("features.mock_feature_demographic_sex.value", 0, 400, "malformed_request"),
    ("features.mock_feature_unknown", {"value": 2, "unit": "u_count"}, 422, "unknown_feature"),
    ("features.mock_feature_excluded_probe", {"value": 2, "unit": "u_count"}, 422, "feature_not_in_schema"),
    ("features.mock_feature_pending_availability_probe", {"value": 2, "unit": "u_count"}, 422, "feature_not_in_schema"),
    ("features.mock_feature_vital_systolic", {"value": 130, "unit": "mmHg"}, 422, "unit_mismatch"),
    ("features.mock_feature_lab_concentration", {"value": 8, "unit": "mg/dL"}, 422, "unit_mismatch"),
    ("features.mock_feature_binary_flag", {"value": 1, "unit": "u_boolean"}, 400, "malformed_request"),
    ("features.mock_feature_fraction", {"value": True, "unit": "u_fraction"}, 400, "malformed_request"),
    ("features.mock_feature_count", {"unit": "u_count"}, 400, "malformed_request"),
    ("features.mock_feature_count", {"value": None, "unit": "u_count", "extra": 1}, 400, "malformed_request"),
    ("unknown_top_level", True, 400, "malformed_request"),
]


@pytest.mark.parametrize("path,value,status,code", CAD_ERRORS)
def test_cad_validation_and_rejected_key_reuse(client, http_app, cad_body, path, value, status, code):
    valid = copy.deepcopy(cad_body)
    change(cad_body, path, value)
    response = client.post(CAD, json=cad_body, headers=KEY)
    assert_error(response, status, code)
    assert http_app.state.mock.audit_events == ()
    assert http_app.state.mock.inference_count == 0
    accepted = client.post(CAD, json=valid, headers=KEY)
    assert accepted.status_code == 200
    assert accepted.json()["idempotent_replay"] is False


MONITORING_ERRORS = [
    ("contract_version", "v99", 400, "unsupported_contract_version"),
    ("observation", DELETE, 400, "malformed_request"),
    ("observation", [], 400, "malformed_request"),
    ("observation.consent_id", DELETE, 422, "consent_required"),
    ("observation.consent_id", "", 422, "consent_required"),
    ("observation.consent_id", None, 422, "consent_required"),
    ("observation.consent_id", 123, 400, "malformed_request"),
    ("observation.consent_id", "x" * 129, 400, "malformed_request"),
    ("observation.patient_ref", DELETE, 400, "malformed_request"),
    ("observation.patient_ref", "not_pseudonymous", 400, "malformed_request"),
    ("observation.observed_at", "yesterday", 400, "malformed_request"),
    ("observation.observed_at", DELETE, 400, "malformed_request"),
    ("observation.source", DELETE, 400, "malformed_request"),
    ("observation.source", "benchmark_import", 400, "malformed_request"),
    ("observation.source_detail", "x" * 201, 400, "malformed_request"),
    ("observation.metrics", [], 400, "malformed_request"),
    ("observation.metrics", {}, 400, "malformed_request"),
    ("observation.metrics", DELETE, 400, "malformed_request"),
    ("observation.metrics.0", "scalar", 400, "malformed_request"),
    ("observation.metrics.0.metric_id", "mock_metric_unknown", 422, "unknown_metric"),
    ("observation.metrics.0.metric_id", {}, 422, "unknown_metric"),
    ("observation.metrics.0.unit", "bpm", 422, "unit_mismatch"),
    ("observation.metrics.0.unit", DELETE, 422, "unit_mismatch"),
    ("observation.metrics.0.value", 301, 422, "value_out_of_range"),
    ("observation.metrics.0.value", -1, 422, "value_out_of_range"),
    ("observation.metrics.0.value", DELETE, 400, "malformed_request"),
    ("observation.metrics.0.value", [], 400, "malformed_request"),
    ("observation.metrics.0.value", {}, 400, "malformed_request"),
    ("observation.metrics.0.recorded_at", "invalid-time", 400, "malformed_request"),
    ("observation.metrics.0.quality_note", "x" * 201, 400, "malformed_request"),
    ("observation.metrics.0.extra", True, 400, "malformed_request"),
    ("request_id", "invalid", 400, "malformed_request"),
    ("observation.score", 0.3, 400, "malformed_request"),
    ("model_id", "mock_model_a_v0.1.0", 400, "malformed_request"),
]


@pytest.mark.parametrize("path,value,status,code", MONITORING_ERRORS)
def test_monitoring_validation_and_rejected_key_reuse(
    client, http_app, monitoring_body, path, value, status, code
):
    valid = copy.deepcopy(monitoring_body)
    change(monitoring_body, path, value)
    response = client.post(MON, json=monitoring_body, headers=KEY)
    assert_error(response, status, code)
    assert http_app.state.mock.audit_events == ()
    assert http_app.state.mock.observations == {}
    accepted = client.post(MON, json=valid, headers=KEY)
    assert accepted.status_code == 201
    assert accepted.json()["idempotent_replay"] is False


@pytest.mark.parametrize("path", [CAD, MON])
@pytest.mark.parametrize("body", [None, [], "string", 7, True])
def test_non_object_bodies_are_contract_400s(client, path, body):
    assert_error(client.post(path, content=json.dumps(body), headers={**KEY, "Content-Type": "application/json"}), 400, "malformed_request")


@pytest.mark.parametrize("path", [CAD, MON])
@pytest.mark.parametrize("raw", [
    b"", b"{", b"{not-json}", b'{"x":1,"x":2}', b'{"x":{"n":1,"n":2}}',
    b"NaN", b"Infinity", b"-Infinity", b"1e309", b"\xff", b"[" * 1100 + b"]" * 1100,
    b'{"unpaired_surrogate":"\\ud800"}',
])
def test_malformed_json_is_not_fastapis_default_422(client, path, raw):
    response = client.post(path, content=raw, headers={**KEY, "Content-Type": "application/json"})
    assert_error(response, 400, "malformed_request")


@pytest.mark.parametrize("path", [CAD, MON])
@pytest.mark.parametrize("key", ["", "short", "x" * 129, "has space in key", "has/slash", "comma,key"])
def test_invalid_idempotency_header(client, cad_body, monitoring_body, path, key):
    body = cad_body if path == CAD else monitoring_body
    assert_error(client.post(path, json=body, headers={"Idempotency-Key": key}), 400, "malformed_request")


@pytest.mark.parametrize("path", [CAD, MON])
def test_duplicate_idempotency_headers_are_rejected(client, cad_body, monitoring_body, path):
    body = cad_body if path == CAD else monitoring_body
    headers = [("Idempotency-Key", "first-valid-key"), ("idempotency-key", "second-valid-key")]
    assert_error(client.post(path, json=body, headers=headers), 400, "malformed_request")


def test_track_a_requires_a_key_and_track_b_does_not(client, cad_body, monitoring_body):
    assert_error(client.post(CAD, json=cad_body), 400, "malformed_request")
    assert client.post(MON, json=monitoring_body).status_code == 201


@pytest.mark.parametrize("path", [CAD, MON])
def test_wrong_content_type_is_a_documented_error(client, cad_body, monitoring_body, path):
    body = cad_body if path == CAD else monitoring_body
    response = client.post(path, content=json.dumps(body), headers={**KEY, "Content-Type": "text/plain"})
    assert_error(response, 400, "malformed_request")


def test_monitoring_metric_limit_and_atomic_batch_validation(client, http_app, monitoring_body):
    observation = monitoring_body["observation"]
    metric = observation["metrics"][0]
    observation["metrics"] = [copy.deepcopy(metric) for _ in range(101)]
    assert_error(client.post(MON, json=monitoring_body, headers=KEY), 400, "malformed_request")
    assert http_app.state.mock.observations == {}
    observation["metrics"] = [metric, {"metric_id": "mock_metric_steps", "value": -1, "unit": "u_count"}]
    assert_error(client.post(MON, json=monitoring_body, headers=KEY), 422, "value_out_of_range")
    assert http_app.state.mock.observations == {}
    assert http_app.state.mock.audit_events == ()
    observation["metrics"] = [copy.deepcopy(metric) for _ in range(100)]
    response = client.post(MON, json=monitoring_body, headers=KEY)
    assert response.status_code == 201
    assert response.json()["recorded_metric_count"] == 100
