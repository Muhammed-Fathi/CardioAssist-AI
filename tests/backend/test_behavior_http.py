"""HTTP behaviors not derived from the fixture-generating oracle."""

import asyncio
import copy
import hashlib
import json
import logging
import time
import uuid

import httpx
import pytest

import backend.app.state as state_module
from backend.app.main import create_app

CAD = "/v1/predictions/cad-tabular"
MON = "/v1/monitoring/observations"
KEY = {"Idempotency-Key": "http-behavior-key-001"}


def independent_digest(body):
    payload = {key: value for key, value in body.items() if key != "request_id"}
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def without_replay(body):
    return {key: value for key, value in body.items() if key != "idempotent_replay"}


@pytest.mark.parametrize("path,status", [(CAD, 200), (MON, 201)])
def test_canonical_replay_preserves_original_response_and_single_audit(
    client, http_app, cad_body, monitoring_body, path, status
):
    body = cad_body if path == CAD else monitoring_body
    # Exercise UTF-8 and nested object order, not just identical Python dicts.
    if path == CAD:
        body["features"]["mock_feature_demographic_sex"]["value"] = "synthetic_أ"
    first = client.post(path, json=body, headers=KEY)
    body["request_id"] = "cccccccc-3333-4333-8333-333333333333"
    reordered = {key: body[key] for key in reversed(body)}
    second = client.post(
        path, content=json.dumps(reordered, indent=4, ensure_ascii=False, sort_keys=True).encode("utf-8"),
        headers={"idempotency-key": KEY["Idempotency-Key"], "Content-Type": "application/json; charset=utf-8"},
    )
    third = client.post(path, json=body, headers=KEY)
    assert first.status_code == second.status_code == third.status_code == status
    assert first.json()["idempotent_replay"] is False
    assert second.json()["idempotent_replay"] is third.json()["idempotent_replay"] is True
    assert without_replay(first.json()) == without_replay(second.json()) == without_replay(third.json())
    assert second.content.replace(b'"idempotent_replay":true', b'"idempotent_replay":false', 1) == first.content
    assert first.json()["request_id"] != body["request_id"]
    state = http_app.state.mock
    assert len(state.audit_events) == 1
    assert state.inference_count == (1 if path == CAD else 0)
    if path == MON:
        assert len(http_app.state.monitoring_repository.list_observations()) == 1
        assert len(http_app.state.monitoring_repository.list_audit_events()) == 1


@pytest.mark.parametrize("path", [CAD, MON])
@pytest.mark.parametrize("mutation", ["valid_change", "invalid_unit", "invalid_version", "missing_envelope"])
def test_conflict_precedes_validation_even_for_invalid_second_payload(
    client, http_app, cad_body, monitoring_body, path, mutation
):
    body = cad_body if path == CAD else monitoring_body
    first = client.post(path, json=body, headers=KEY).json()
    if mutation == "invalid_version":
        body["contract_version"] = "v999"
    elif mutation == "missing_envelope":
        del body["features" if path == CAD else "observation"]
    else:
        item = body["features"]["mock_feature_demographic_age"] if path == CAD else body["observation"]["metrics"][0]
        item["unit" if mutation == "invalid_unit" else "value"] = "invalid-unit" if mutation == "invalid_unit" else 90
    response = client.post(path, json=body, headers=KEY)
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "idempotency_key_conflict"
    assert error["original_audit_id"] == first["audit_id" if path == CAD else "observation_id"]
    assert len(http_app.state.mock.audit_events) == 1
    assert http_app.state.mock.inference_count == (1 if path == CAD else 0)
    if path == MON:
        assert len(http_app.state.monitoring_repository.list_observations()) == 1
        assert len(http_app.state.monitoring_repository.list_audit_events()) == 1


@pytest.mark.parametrize("path", [CAD, MON])
def test_informational_request_id_is_optional_but_success_always_has_a_uuid(
    client, cad_body, monitoring_body, path
):
    body = cad_body if path == CAD else monitoring_body
    del body["request_id"]
    first = client.post(path, json=body, headers=KEY).json()
    assert str(uuid.UUID(first["request_id"])) == first["request_id"]
    second = client.post(path, json=body, headers=KEY).json()
    assert without_replay(first) == without_replay(second)
    assert second["idempotent_replay"] is True


def test_audit_id_and_hash_are_recomputed_independently(client, http_app, cad_body):
    response = client.post(CAD, json=cad_body, headers=KEY).json()
    digest = independent_digest(cad_body)
    expected = uuid.uuid5(
        uuid.UUID("9e139be5-1516-59e8-b50c-45c834786b99"),
        f"{KEY['Idempotency-Key']}|{digest}|1",
    )
    assert response["audit_id"] == str(expected)
    event = http_app.state.mock.audit_events[0]
    assert event.payload_sha256 == digest
    assert event.event_id == response["audit_id"]
    assert event.model_id == response["model_id"]
    assert not hasattr(event, "features")
    assert not hasattr(event, "patient_ref")


@pytest.mark.parametrize("path", [CAD, MON])
def test_retention_uses_monotonic_time_not_the_frozen_fixture_timestamp(
    client, http_app, monotonic_time, cad_body, monitoring_body, caplog, path
):
    body = cad_body if path == CAD else monitoring_body
    first = client.post(path, json=body, headers=KEY).json()
    monotonic_time[0] += 86400 - 0.1
    assert client.post(path, json=body, headers=KEY).json()["idempotent_replay"] is True
    monotonic_time[0] += 0.1
    with caplog.at_level(logging.INFO, logger="backend.app.state"):
        second = client.post(path, json=body, headers=KEY).json()
    id_field = "audit_id" if path == CAD else "observation_id"
    assert second["idempotent_replay"] is False
    assert second[id_field] != first[id_field]
    assert second["generated_at" if path == CAD else "received_at"] == first["generated_at" if path == CAD else "received_at"]
    assert "mock_idempotency_expired" in caplog.text
    assert KEY["Idempotency-Key"] not in caplog.text
    assert len(http_app.state.mock.audit_events) == 2
    if path == MON:
        assert len(http_app.state.monitoring_repository.list_observations()) == 2
        assert len(http_app.state.monitoring_repository.list_audit_events()) == 2


@pytest.mark.parametrize("path", [CAD, MON])
def test_expired_key_accepts_a_different_payload(client, monotonic_time, cad_body, monitoring_body, path):
    body = cad_body if path == CAD else monitoring_body
    client.post(path, json=body, headers=KEY)
    monotonic_time[0] += 86400
    if path == CAD:
        body["features"]["mock_feature_demographic_age"]["value"] = 70
    else:
        body["observation"]["metrics"][0]["value"] = 70
    response = client.post(path, json=body, headers=KEY)
    assert response.status_code == (200 if path == CAD else 201)
    assert response.json()["idempotent_replay"] is False


@pytest.mark.parametrize("first_path,second_path", [(CAD, MON), (MON, CAD)])
@pytest.mark.parametrize("same_body", [False, True])
def test_global_keys_never_replay_one_track_into_another(
    client, cad_body, monitoring_body, first_path, second_path, same_body
):
    first_body = cad_body if first_path == CAD else monitoring_body
    second_body = first_body if same_body else (cad_body if second_path == CAD else monitoring_body)
    first = client.post(first_path, json=first_body, headers=KEY).json()
    second = client.post(second_path, json=second_body, headers=KEY)
    assert second.status_code == 409
    assert second.json()["error"]["original_audit_id"] == first.get("audit_id", first.get("observation_id"))


def test_keyless_monitoring_appends_and_keeps_source_labels(client, http_app, monitoring_body):
    first = client.post(MON, json=monitoring_body).json()
    second = client.post(MON, json=monitoring_body).json()
    assert first["observation_id"] != second["observation_id"]
    assert first["idempotent_replay"] is second["idempotent_replay"] is False
    state = http_app.state.mock
    assert len(state.observations) == len(state.audit_events) == 2
    assert state.observations[first["observation_id"]]["source"] == "simulated_wearable"
    assert len(http_app.state.monitoring_repository.list_observations()) == 2
    assert len(http_app.state.monitoring_repository.list_audit_events()) == 2
    snapshot = state.observations
    snapshot.clear()
    assert len(state.observations) == 2  # Test access cannot mutate stored observations.
    assert state.inference_count == 0


@pytest.mark.parametrize("source", ["manual_entry", "simulated_wearable", "wearable_device", "vendor_app"])
def test_track_b_sources_are_monitoring_only(client, http_app, monitoring_body, source):
    monitoring_body["observation"]["source"] = source
    response = client.post(MON, json=monitoring_body, headers=KEY)
    assert response.status_code == 201
    assert not {"score", "target", "explanation", "model_id", "review_state"} & response.json().keys()
    assert http_app.state.mock.inference_count == 0


@pytest.mark.parametrize("source", [
    "simulated_wearable", "wearable_device", "health_connect", "health_kit", "apple_health",
    "vendor_app", "fitbit", "garmin", "oura", "whoop",
])
def test_all_declared_wearable_sources_are_rejected_for_cad(client, http_app, cad_body, source):
    cad_body["context"]["source"] = source
    # Wearable safety code must win even when an ordinary feature is invalid.
    cad_body["features"]["mock_feature_demographic_age"]["unit"] = "bad-unit"
    response = client.post(CAD, json=cad_body, headers=KEY)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "wearable_input_not_valid_for_cad_inference"
    assert http_app.state.mock.inference_count == 0
    assert http_app.state.mock.audit_events == ()


@pytest.mark.parametrize("field", [
    "heart_rate_bpm", "steps", "wearable_ecg", "ecg_waveform", "mock_feature_wearable_hr",
    "mock_metric_heart_rate", "mock_metric_steps",
])
def test_wearable_measurement_fields_cannot_be_disguised_as_cad_features(client, cad_body, field):
    cad_body["features"][field] = {"value": 10, "unit": "u_rate"}
    response = client.post(CAD, json=cad_body, headers=KEY)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "wearable_input_not_valid_for_cad_inference"


def test_nested_wearable_payload_is_rejected_not_ignored(client, cad_body):
    cad_body["extra"] = {"nested": [{"heart_rate_bpm": 72}]}
    response = client.post(CAD, json=cad_body, headers=KEY)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "wearable_input_not_valid_for_cad_inference"


def test_monitoring_never_triggers_or_changes_cad_inference(client, http_app, cad_body, monitoring_body):
    before = client.post(CAD, json=cad_body, headers=KEY).json()
    for number in range(3):
        monitoring_body["observation"]["metrics"][0]["value"] = number
        assert client.post(MON, json=monitoring_body).status_code == 201
    assert http_app.state.mock.inference_count == 1
    after = client.post(CAD, json=cad_body, headers={"Idempotency-Key": "http-after-monitoring"}).json()
    assert after["score"] == before["score"]
    assert after["explanation"] == before["explanation"]


def test_required_null_optional_null_and_zero_are_distinct(client, cad_body):
    original = copy.deepcopy(cad_body)
    cad_body["features"]["mock_feature_demographic_age"]["value"] = None
    assert client.post(CAD, json=cad_body, headers=KEY).json()["error"]["code"] == "missing_required_feature"
    cad_body = original
    cad_body["features"]["mock_feature_count"] = {"value": None, "unit": "u_count"}
    with_null = client.post(CAD, json=cad_body, headers=KEY).json()
    assert "mock_feature_count" in with_null["missing_features"]
    assert "imputed_feature:mock_feature_count" in with_null["warnings"]
    assert "mock_feature_count" not in {c["feature"] for c in with_null["explanation"]["contributions"]}
    del cad_body["features"]["mock_feature_count"]
    absent = client.post(CAD, json=cad_body, headers={"Idempotency-Key": "http-null-vs-absent"}).json()
    assert absent["score"] == with_null["score"]
    assert absent["explanation"] == with_null["explanation"]
    cad_body["features"]["mock_feature_count"] = {"value": 0, "unit": "u_count"}
    cad_body["features"]["mock_feature_binary_flag"] = {"value": False, "unit": "u_boolean"}
    zero = client.post(CAD, json=cad_body, headers={"Idempotency-Key": "http-zero-is-data"}).json()
    contributions = {item["feature"]: item["value"] for item in zero["explanation"]["contributions"]}
    assert contributions["mock_feature_count"] == 0
    assert contributions["mock_feature_binary_flag"] is False
    assert "mock_feature_count" not in zero["missing_features"]
    assert "mock_feature_binary_flag" not in zero["missing_features"]
    # Canonicalization does NOT silently normalize null to absent or add defaults.
    assert client.post(CAD, json=cad_body, headers=KEY).status_code == 409


@pytest.mark.parametrize("value,count", [(None, 0), (0, 1), (False, 1), ("untyped_mock", 1), (0.5, 1)])
def test_reported_track_b_value_type_ambiguity_preserves_merged_behavior(
    client, http_app, monitoring_body, value, count
):
    # B-01: value_type says integer; the approved schema permits other scalars
    # and the merged reference accepts them. Do not silently ratify new types.
    monitoring_body["observation"]["metrics"] = [
        {"metric_id": "mock_metric_steps", "value": value, "unit": "u_count"}
    ]
    response = client.post(MON, json=monitoring_body, headers=KEY)
    assert response.status_code == 201
    assert response.json()["recorded_metric_count"] == count
    assert response.json()["validation"] == {"status": "accepted", "issues": []}
    stored = http_app.state.mock.observations[response.json()["observation_id"]]
    assert len(stored["metrics"]) == count


@pytest.mark.parametrize("model_id", ["mock_model_a_v0.1.0", "mock_model_a_v0.2.0", "mock_model_c_v0.1.0"])
def test_synthetic_xai_additivity_and_claims_without_oracle(client, cad_body, model_id):
    cad_body["model_id"] = model_id
    cad_body["features"].update({
        "mock_feature_count": {"value": 19, "unit": "u_count"},
        "mock_feature_fraction": {"value": 0.37, "unit": "u_fraction"},
    })
    response = client.post(CAD, json=cad_body, headers=KEY).json()
    explanation = response["explanation"]
    score = response["score"]
    actual_sum = explanation["base_value"] + sum(c["shap"] for c in explanation["contributions"])
    margin = score["raw_margin"] if score["type"] == "calibrated_probability" else score["value"]
    check = explanation["sum_check"]
    assert actual_sum == pytest.approx(margin, abs=check["tolerance"])
    assert actual_sum == pytest.approx(check["computed_sum"], abs=check["tolerance"])
    assert check["passed"] is check["applicable"] is True
    assert explanation["method"] == "tree_shap"
    assert explanation["scale"] == "log_odds_margin"
    assert explanation["synthetic"] is True
    assert "local_fidelity_r2" not in explanation
    assert "NOT causal effects" in explanation["note"]
    assert "no treatment, intervention or recommendation" in explanation["note"]
    assert "NOT computed by SHAP or LIME" in explanation["note"]
    assert score["rendering"]["percent_sign_allowed"] is False
    assert score["rendering"]["absolute_population_probability_claim"] is False
    assert response["data_class"] == "MOCK_SYNTHETIC"
    assert response["provenance"]["training_datasets"] == []
    assert response["validation_status"] == "development_internal_only"
    assert response["model_performance_ref"].endswith("#internal_validation")
    assert response["review_state"] == "pending_review"
    assert response["target"]["status"] == "provisional_pending_approval"
    assert response["target"]["time_horizon"] == "none_cross_sectional"
    if score["type"] == "calibrated_probability":
        assert check["margin_source"] == "score.raw_margin"
        assert abs(actual_sum - score["value"]) > check["tolerance"]
        assert score["calibration"]["method"] == "mock_only"
        assert score["calibration"]["cohort_context"]["population_scope"] == "mock_synthetic_no_cohort_exists"


def test_schema_v2_requires_its_own_model_and_required_fraction(client, cad_body):
    cad_body["feature_schema_id"] = "mock_clinical_v2"
    assert client.post(CAD, json=cad_body, headers=KEY).json()["error"]["code"] == "schema_model_mismatch"
    cad_body["model_id"] = "mock_model_b_v0.1.0"
    assert client.post(CAD, json=cad_body, headers=KEY).json()["error"]["code"] == "missing_required_feature"
    cad_body["features"]["mock_feature_fraction"] = {"value": 0, "unit": "u_fraction"}
    response = client.post(CAD, json=cad_body, headers=KEY)
    assert response.status_code == 200
    assert response.json()["feature_schema_id"] == "mock_clinical_v2"
    assert response.json()["preprocessing_id"] == "mock_prep_v2"


@pytest.mark.parametrize("path,status", [(CAD, 200), (MON, 201)])
@pytest.mark.parametrize("mixed_payloads", [False, True])
def test_concurrent_http_requests_publish_one_result_and_one_audit(
    http_app, http_validators, cad_body, monitoring_body, monkeypatch, path, status, mixed_payloads
):
    calls = []
    real_builder = state_module.build_prediction

    def slow_builder(*args, **kwargs):
        calls.append(1)
        time.sleep(0.02)  # Widen the old check-then-create race window.
        return real_builder(*args, **kwargs)

    monkeypatch.setattr(state_module, "build_prediction", slow_builder)
    body = cad_body if path == CAD else monitoring_body

    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=http_app), base_url="http://testserver") as client:
            requests = []
            for number in range(16):
                payload = copy.deepcopy(body)
                payload["request_id"] = str(uuid.UUID(int=number + 1))
                if mixed_payloads and number % 2:
                    if path == CAD:
                        payload["features"]["mock_feature_demographic_age"]["value"] = 99
                    else:
                        payload["observation"]["metrics"][0]["value"] = 99
                requests.append(client.post(path, json=payload, headers=KEY))
            return await asyncio.gather(*requests)

    responses = asyncio.run(run())
    for response in responses:
        http_validators(response, path)
    accepted = [response.json() for response in responses if response.status_code == status]
    conflicts = [response for response in responses if response.status_code == 409]
    assert len(accepted) == (8 if mixed_payloads else 16)
    assert len(conflicts) == (8 if mixed_payloads else 0)
    assert sum(not item["idempotent_replay"] for item in accepted) == 1
    assert all(without_replay(item) == without_replay(accepted[0]) for item in accepted)
    assert len(http_app.state.mock.audit_events) == 1
    assert http_app.state.mock.inference_count == len(calls) == (1 if path == CAD else 0)
    assert len(http_app.state.mock.observations) == (0 if path == CAD else 1)
    if path == MON:
        assert len(http_app.state.monitoring_repository.list_observations()) == 1
        assert len(http_app.state.monitoring_repository.list_audit_events()) == 1


def test_internal_error_is_audited_safe_and_does_not_consume_key(client, http_app, cad_body, monkeypatch, caplog):
    def broken(*args, **kwargs):
        raise RuntimeError("PRIVATE-INTERNAL-DETAIL-MUST-NOT-LEAK")

    with monkeypatch.context() as patch:
        patch.setattr(state_module, "build_prediction", broken)
        response = client.post(CAD, json=cad_body, headers=KEY)
    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "internal_error"
    assert "PRIVATE-INTERNAL-DETAIL" not in response.text + caplog.text
    assert "Traceback" not in response.text
    assert http_app.state.mock.audit_events[0].event_id == error["audit_id"]
    assert http_app.state.mock.audit_events[0].event_type == "internal_error"
    accepted = client.post(CAD, json=cad_body, headers=KEY)
    assert accepted.status_code == 200
    assert accepted.json()["idempotent_replay"] is False
    assert http_app.state.mock.inference_count == 1
    assert len(http_app.state.mock.audit_events) == 2


@pytest.mark.parametrize("path", [CAD, MON])
def test_schema_invalid_server_output_is_not_published_or_cached(
    client, http_app, cad_body, monitoring_body, path
):
    body = cad_body if path == CAD else monitoring_body
    validators = http_app.state.mock.contracts.responses
    original = validators[path]

    class BrokenValidator:
        def validate(self, body):
            raise RuntimeError("simulated response-schema validation failure")

    validators[path] = BrokenValidator()
    try:
        response = client.post(path, json=body, headers=KEY)
    finally:
        validators[path] = original
    assert response.status_code == 500
    assert http_app.state.mock.observations == {}
    assert http_app.state.mock.inference_count == 0
    if path == MON:
        assert http_app.state.monitoring_repository.list_observations() == ()
        assert http_app.state.monitoring_repository.list_audit_events() == ()
    accepted = client.post(path, json=body, headers=KEY)
    assert accepted.status_code == (200 if path == CAD else 201)
    assert accepted.json()["idempotent_replay"] is False
    if path == MON:
        assert len(http_app.state.monitoring_repository.list_observations()) == 1
        assert len(http_app.state.monitoring_repository.list_audit_events()) == 1


def test_reopening_app_resets_runtime_state_but_monitoring_records_survive(
    client, http_app, http_validators, cad_body, monitoring_body, migrated_database_url
):
    client.post(CAD, json=cad_body, headers=KEY)
    monitoring_key = {"Idempotency-Key": "restart-monitor-write"}
    first = client.post(MON, json=monitoring_body, headers=monitoring_key)
    assert first.status_code == 201
    assert len(http_app.state.monitoring_repository.list_observations()) == 1
    assert len(http_app.state.monitoring_repository.list_audit_events()) == 1

    # Runtime idempotency/audit snapshots still reset; the database does not.
    restarted = create_app(database_url=migrated_database_url)
    assert restarted.state.mock.audit_events == ()
    assert restarted.state.mock.observations == {}
    assert restarted.state.mock.inference_count == 0
    persisted = restarted.state.monitoring_repository.list_observations()
    assert len(persisted) == 1
    assert persisted[0].metrics[0].value == 64
    assert len(restarted.state.monitoring_repository.list_audit_events()) == 1

    # Q8 remains open: the current 24-hour key cache is process-local. A retry
    # after restart is accepted again; the storage UUID keeps both rows distinct
    # even though the existing deterministic public observation id repeats.
    from fastapi.testclient import TestClient
    with TestClient(restarted) as other:
        response = other.post(MON, json=monitoring_body, headers=monitoring_key)
    http_validators(response, MON)
    assert response.status_code == 201
    assert response.json()["idempotent_replay"] is False
    reopened_rows = http_app.state.monitoring_repository.list_observations()
    assert len(reopened_rows) == 2
    assert reopened_rows[0].observation_id == reopened_rows[1].observation_id
    assert len(http_app.state.monitoring_repository.list_audit_events()) == 2
