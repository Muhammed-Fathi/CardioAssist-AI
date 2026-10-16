"""Independent behavioural tests for the /v1 contract.

The tests in ``test_fixtures.py`` check the committed fixture pack: they
compare it against the reference implementation and assert the rules the
pack is supposed to demonstrate. That is a golden-file check, and on its own
it can only prove that the pack and the oracle agree.

This module closes that gap. Everything here is written **against the
contract text**, not against the oracle's internals:

* every ``assertions`` block declared by a fixture is executed, so the pack's
  own machine-checkable expectations are no longer decorative;
* the idempotency guarantees are driven directly against the implementation
  (a retry must not re-run inference and must not create a second audit
  event; a conflicting payload must be a 409);
* a battery of hostile inputs must produce exactly the documented status and
  error code, must never produce a score, and the code must be documented
  for that endpoint in the OpenAPI document;
* the audit-id derivation is recomputed from scratch — without importing the
  oracle's helpers — so a change of the documented rule is caught;
* the clinical-unit discipline, the null/zero rule and the non-causal
  wording are asserted directly.
"""

from __future__ import annotations

import hashlib
import json
import uuid

import pytest

from conftest import iter_strings
import reference_contract as rc

CAD = "POST /v1/predictions/cad-tabular"
MON = "POST /v1/monitoring/observations"

#: The mock audit namespace, copied literally from the contract README (§5) so
#: that this test does not depend on the oracle's own constants.
MOCK_AUDIT_NAMESPACE = uuid.UUID("9e139be5-1516-59e8-b50c-45c834786b99")

FEATURES = {
    "mock_feature_demographic_age": {"value": 58, "unit": "u_years"},
    "mock_feature_demographic_sex": {"value": "category_a", "unit": "u_category"},
}
CONTEXT = {"source": "benchmark_import", "recorded_at": "2026-10-16T09:00:00Z"}


def cad_body(features=None, **overrides):
    body = {
        "contract_version": "v1",
        "request_id": "018f3c2a-7b1e-7c4d-8f21-0000000009f0",
        "model_id": "mock_model_a_v0.1.0",
        "feature_schema_id": "mock_clinical_v1",
        "features": json.loads(json.dumps(features or FEATURES)),
        "context": json.loads(json.dumps(CONTEXT)),
    }
    body.update(overrides)
    return body


def monitoring_body(**overrides):
    body = {
        "contract_version": "v1",
        "request_id": "018f3c2a-7b1e-7c4d-8f21-0000000009f1",
        "observation": {
            "patient_ref": "pseudo_demo_001",
            "observed_at": "2026-10-16T08:30:00Z",
            "source": "simulated_wearable",
            "consent_id": "consent_mock_001",
            "metrics": [
                {"metric_id": "mock_metric_heart_rate", "value": 72, "unit": "u_rate"},
            ],
        },
    }
    body.update(overrides)
    return body


# --------------------------------------------------------------------------- #
# 1. the fixtures' own assertion blocks are executed
# --------------------------------------------------------------------------- #
def _step_bodies(fixture):
    return {step["step"]: step for step in fixture["steps"]}


def _check_assertions(fixture, step):
    """Execute one fixture step's declared assertions."""
    assertions = step.get("assertions", {})
    body = step["expected"]["body"]
    steps = _step_bodies(fixture)
    where = f"{fixture['fixture_id']} step {step['step']}"

    if "http_status" in assertions:
        assert step["expected"]["status"] == assertions["http_status"], where
    if "error_code" in assertions:
        assert body.get("error", {}).get("code") == assertions["error_code"], where
    if "idempotent_replay" in assertions:
        assert body.get("idempotent_replay") == assertions["idempotent_replay"], where
    if "track" in assertions:
        assert body.get("track") == assertions["track"], where
    if "validation_status" in assertions:
        assert body.get("validation_status") == assertions["validation_status"], where
    if "model_id" in assertions:
        assert body.get("model_id") == assertions["model_id"], where
    if "model_performance_ref_section" in assertions:
        assert body.get("model_performance_ref", "").endswith(
            assertions["model_performance_ref_section"]
        ), where
    if "score_type" in assertions:
        assert body.get("score", {}).get("type") == assertions["score_type"], where
    if "explanation_method" in assertions:
        assert body.get("explanation", {}).get("method") == assertions["explanation_method"], where
    if "explanation_scale" in assertions:
        assert body.get("explanation", {}).get("scale") == assertions["explanation_scale"], where
    if "explanation_synthetic" in assertions:
        assert body.get("explanation", {}).get("synthetic") == assertions["explanation_synthetic"], where
    if "missing_features_non_empty" in assertions:
        assert bool(body.get("missing_features")) is assertions["missing_features_non_empty"], where
    if "missing_features_excludes" in assertions:
        assert assertions["missing_features_excludes"] not in body.get("missing_features", []), where
    if "zero_value_is_data" in assertions:
        assert assertions["zero_value_is_data"] is True, where
        contributions = body.get("explanation", {}).get("contributions", [])
        zero_features = [
            c for c in contributions if c.get("value") == 0
        ]
        assert zero_features, f"{where}: a zero-valued feature must appear in the contributions"
    if "no_cad_output" in assertions:
        for forbidden in ("score", "target", "explanation", "model_id", "review_state"):
            assert forbidden not in body, f"{where}: {forbidden} leaked into a Track-B response"
    if "mandatory_fields_present" in assertions:
        for field in (
            "target",
            "disclaimer",
            "provenance",
            "review_state",
            "validation_status",
            "model_performance_ref",
        ):
            assert field in body, f"{where}: missing mandatory field {field}"
    if "snapshot_response_keys" in assertions:
        assert sorted(body.keys()) == sorted(fixture["mandatory_response_fields"]), where
    if "score_rendering" in assertions:
        rendering = body.get("score", {}).get("rendering", {})
        for key, value in assertions["score_rendering"].items():
            assert rendering.get(key) == value, f"{where}: rendering.{key}"
    if "shap_sum_check" in assertions:
        check = body.get("explanation", {}).get("sum_check", {})
        for key, value in assertions["shap_sum_check"].items():
            assert check.get(key) == value, f"{where}: sum_check.{key}"
    if "same_audit_id_as_step" in assertions:
        other = steps[assertions["same_audit_id_as_step"]]
        assert body["audit_id"] == other["expected"]["body"]["audit_id"], where
    if "different_audit_id_than_step" in assertions:
        other = steps[assertions["different_audit_id_than_step"]]
        assert body["audit_id"] != other["expected"]["body"]["audit_id"], where
    if "same_response_as_step" in assertions:
        other = steps[assertions["same_response_as_step"]]
        except_fields = assertions.get("except_fields", [])
        left = {k: v for k, v in body.items() if k not in except_fields}
        right = {
            k: v for k, v in other["expected"]["body"].items() if k not in except_fields
        }
        assert left == right, where
    if "deterministic_equal_to_step" in assertions:
        other = steps[assertions["deterministic_equal_to_step"]]
        for field in assertions.get("fields", []):
            assert body.get(field) == other["expected"]["body"].get(field), f"{where}: {field}"


def test_every_fixture_assertion_block_is_executed(fixtures):
    """The pack's declared expectations are machine-checked, not decorative."""
    checked = 0
    for fixture in fixtures:
        for step in fixture["steps"]:
            _check_assertions(fixture, step)
            checked += 1
    assert checked >= 30


def test_every_fixture_declares_at_least_one_assertion(fixtures):
    for fixture in fixtures:
        for step in fixture["steps"]:
            assert step.get("assertions"), f"{fixture['fixture_id']} step {step['step']}"


# --------------------------------------------------------------------------- #
# 2. idempotency behaviour, driven directly
# --------------------------------------------------------------------------- #
def test_a_retry_reuses_the_original_result_and_audit_id_without_re_inferring():
    contract = rc.ReferenceContract()
    headers = {"Idempotency-Key": "behaviour-retry-key-0000001"}
    body = cad_body()

    first_status, first = contract.handle(CAD, body, headers)
    second_status, second = contract.handle(CAD, body, headers)

    assert first_status == 200 and second_status == 200
    assert first["idempotent_replay"] is False
    assert second["idempotent_replay"] is True
    assert second["audit_id"] == first["audit_id"]
    stripped_first = {k: v for k, v in first.items() if k != "idempotent_replay"}
    stripped_second = {k: v for k, v in second.items() if k != "idempotent_replay"}
    assert stripped_first == stripped_second

    # No second inference and no second audit event.
    assert contract.inference_count == 1
    assert contract.audit_events == [first["audit_id"]]


def test_a_retry_that_regenerates_the_request_id_is_still_a_replay():
    """request_id is informational and is excluded from the payload hash."""
    contract = rc.ReferenceContract()
    headers = {"Idempotency-Key": "behaviour-retry-key-0000002"}
    first_status, first = contract.handle(
        CAD, cad_body(request_id="018f3c2a-7b1e-7c4d-8f21-0000000009f2"), headers
    )
    second_status, second = contract.handle(
        CAD, cad_body(request_id="018f3c2a-7b1e-7c4d-8f21-0000000009f3"), headers
    )
    assert first_status == 200 and second_status == 200
    assert second["idempotent_replay"] is True
    assert second["audit_id"] == first["audit_id"]
    assert contract.inference_count == 1


def test_a_conflicting_payload_under_the_same_key_is_a_409():
    contract = rc.ReferenceContract()
    headers = {"Idempotency-Key": "behaviour-conflict-key-00001"}
    first_status, first = contract.handle(CAD, cad_body(), headers)
    assert first_status == 200

    changed = cad_body()
    changed["features"]["mock_feature_demographic_age"] = {"value": 61, "unit": "u_years"}
    status, body = contract.handle(CAD, changed, headers)

    assert status == 409
    assert body["error"]["code"] == "idempotency_key_conflict"
    assert body["error"]["original_audit_id"] == first["audit_id"]
    # A conflict must not create an inference or an audit event.
    assert contract.inference_count == 1
    assert contract.audit_events == [first["audit_id"]]


def test_a_conflict_is_reported_even_when_the_new_payload_is_itself_invalid():
    """The documented rule is unconditional: same key + different payload -> 409."""
    contract = rc.ReferenceContract()
    headers = {"Idempotency-Key": "behaviour-conflict-key-00002"}
    assert contract.handle(CAD, cad_body(), headers)[0] == 200

    invalid = cad_body()
    invalid["features"]["mock_feature_vital_systolic"] = {"value": 142, "unit": "u_weight"}
    status, body = contract.handle(CAD, invalid, headers)

    assert status == 409
    assert body["error"]["code"] == "idempotency_key_conflict"
    assert contract.inference_count == 1


def test_a_rejected_request_does_not_occupy_its_idempotency_key():
    """A request that never produced a result must not poison the key."""
    contract = rc.ReferenceContract()
    headers = {"Idempotency-Key": "behaviour-rejected-key-00001"}
    bad = cad_body()
    bad["features"]["mock_feature_vital_systolic"] = {"value": 142, "unit": "u_weight"}
    assert contract.handle(CAD, bad, headers)[0] == 422

    # The same key with a valid payload is a first request, not a conflict.
    status, body = contract.handle(CAD, cad_body(), headers)
    assert status == 200
    assert body["idempotent_replay"] is False
    assert contract.inference_count == 1


def test_distinct_keys_produce_distinct_audit_events_but_identical_scores():
    contract = rc.ReferenceContract()
    _, first = contract.handle(CAD, cad_body(), {"Idempotency-Key": "behaviour-two-keys-000001"})
    _, second = contract.handle(CAD, cad_body(), {"Idempotency-Key": "behaviour-two-keys-000002"})
    assert first["audit_id"] != second["audit_id"]
    assert first["score"] == second["score"]
    assert first["explanation"] == second["explanation"]
    assert contract.inference_count == 2
    assert len(contract.audit_events) == 2


def test_monitoring_replay_also_reuses_the_stored_observation():
    contract = rc.ReferenceContract()
    headers = {"Idempotency-Key": "behaviour-monitor-key-000001"}
    first_status, first = contract.handle(MON, monitoring_body(), headers)
    second_status, second = contract.handle(MON, monitoring_body(), headers)
    assert first_status == 201 and second_status == 201
    assert second["observation_id"] == first["observation_id"]
    assert second["idempotent_replay"] is True
    assert len(contract.audit_events) == 1


def test_a_conflicting_monitoring_payload_under_the_same_key_is_a_409():
    contract = rc.ReferenceContract()
    headers = {"Idempotency-Key": "behaviour-monitor-key-000002"}
    first_status, first = contract.handle(MON, monitoring_body(), headers)
    assert first_status == 201

    changed = monitoring_body()
    changed["observation"]["metrics"][0]["value"] = 91
    status, body = contract.handle(MON, changed, headers)

    assert status == 409
    assert body["error"]["code"] == "idempotency_key_conflict"
    assert body["error"]["original_audit_id"] == first["observation_id"]
    assert len(contract.audit_events) == 1


def test_a_conflicting_monitoring_payload_is_a_409_even_when_it_is_invalid():
    """The rule is unconditional on Track B as well."""
    contract = rc.ReferenceContract()
    headers = {"Idempotency-Key": "behaviour-monitor-key-000003"}
    assert contract.handle(MON, monitoring_body(), headers)[0] == 201

    changed = monitoring_body()
    changed["observation"]["metrics"][0]["metric_id"] = "mock_metric_does_not_exist"
    status, body = contract.handle(MON, changed, headers)

    assert status == 409
    assert body["error"]["code"] == "idempotency_key_conflict"
    assert len(contract.audit_events) == 1


# --------------------------------------------------------------------------- #
# 3. the audit id is derived by the documented rule (recomputed from scratch)
# --------------------------------------------------------------------------- #
def test_audit_id_follows_the_documented_derivation_rule():
    """Recomputed independently of the oracle's own helpers."""
    contract = rc.ReferenceContract()
    headers = {"Idempotency-Key": "behaviour-audit-rule-key-0001"}
    body = cad_body()

    payload = {k: v for k, v in body.items() if k != "request_id"}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    expected = str(uuid.uuid5(MOCK_AUDIT_NAMESPACE, f"{headers['Idempotency-Key']}|{digest}|1"))

    _, response = contract.handle(CAD, body, headers)
    assert response["audit_id"] == expected


# --------------------------------------------------------------------------- #
# 4. hostile-input battery
# --------------------------------------------------------------------------- #
HOSTILE_CAD_INPUTS = [
    ("body is an array", ["not", "a", "request"], 400, "malformed_request"),
    ("body is a string", "not-a-request", 400, "malformed_request"),
    ("body is null", None, 400, "malformed_request"),
    (
        "feature_schema_id is missing",
        {k: v for k, v in cad_body().items() if k != "feature_schema_id"},
        400,
        "malformed_request",
    ),
    (
        "feature_schema_id is not a string",
        cad_body(feature_schema_id=17),
        400,
        "malformed_request",
    ),
    (
        "feature_schema_id is unknown",
        cad_body(feature_schema_id="mock_clinical_v99"),
        422,
        "unknown_feature_schema",
    ),
    (
        "context is missing",
        {k: v for k, v in cad_body().items() if k != "context"},
        400,
        "malformed_request",
    ),
    (
        "features are missing",
        {k: v for k, v in cad_body().items() if k != "features"},
        400,
        "malformed_request",
    ),
    ("features are not an object", cad_body(features=["a"]), 400, "malformed_request"),
    (
        "contract version is not implemented",
        cad_body(contract_version="v2"),
        400,
        "unsupported_contract_version",
    ),
    (
        "a wearable context source",
        cad_body(context={**CONTEXT, "source": "simulated_wearable"}),
        422,
        "wearable_input_not_valid_for_cad_inference",
    ),
    (
        "a vendor context source",
        cad_body(context={**CONTEXT, "source": "fitbit"}),
        422,
        "wearable_input_not_valid_for_cad_inference",
    ),
    (
        "a wearable measurement field in the payload",
        cad_body(
            features={**FEATURES, "heart_rate_bpm": {"value": 72, "unit": "u_rate"}}
        ),
        422,
        "wearable_input_not_valid_for_cad_inference",
    ),
    (
        "a wearable-prefixed feature id",
        cad_body(
            features={**FEATURES, "mock_feature_wearable_hr": {"value": 72, "unit": "u_rate"}}
        ),
        422,
        "wearable_input_not_valid_for_cad_inference",
    ),
    (
        "an inadmissible context source",
        cad_body(context={**CONTEXT, "source": "patient_app_direct"}),
        422,
        "invalid_context_source",
    ),
    (
        "an empty context source",
        cad_body(context={**CONTEXT, "source": ""}),
        422,
        "invalid_context_source",
    ),
    ("an unknown model", cad_body(model_id="mock_model_nope"), 422, "unknown_model"),
    (
        "a model bound to another feature schema",
        cad_body(model_id="mock_model_b_v0.1.0"),
        422,
        "schema_model_mismatch",
    ),
    (
        "an unavailable model artifact",
        cad_body(model_id="mock_model_e_v0.1.0"),
        503,
        "model_unavailable",
    ),
    (
        "a feature excluded from the schema",
        cad_body(
            features={**FEATURES, "mock_feature_excluded_probe": {"value": 1, "unit": "u_count"}}
        ),
        422,
        "feature_not_in_schema",
    ),
    (
        "a feature pending the availability audit",
        cad_body(
            features={
                **FEATURES,
                "mock_feature_pending_availability_probe": {"value": 1, "unit": "u_count"},
            }
        ),
        422,
        "feature_not_in_schema",
    ),
    (
        "an undeclared feature",
        cad_body(features={**FEATURES, "mock_feature_unknown": {"value": 1, "unit": "u_count"}}),
        422,
        "unknown_feature",
    ),
    (
        "a feature without a unit",
        cad_body(
            features={
                **FEATURES,
                "mock_feature_vital_systolic": {"value": 142},
            }
        ),
        422,
        "unit_mismatch",
    ),
    (
        "a feature with a wrong unit",
        cad_body(
            features={
                **FEATURES,
                "mock_feature_vital_systolic": {"value": 142, "unit": "u_weight"},
            }
        ),
        422,
        "unit_mismatch",
    ),
    (
        "a clinical unit against a MOCK_ONLY schema",
        cad_body(
            features={
                **FEATURES,
                "mock_feature_vital_systolic": {"value": 142, "unit": "mmHg"},
            }
        ),
        422,
        "unit_mismatch",
    ),
    (
        "a value outside the declared range",
        cad_body(
            features={**FEATURES, "mock_feature_demographic_age": {"value": 500, "unit": "u_years"}}
        ),
        422,
        "value_out_of_range",
    ),
    (
        "a value of the wrong type",
        cad_body(
            features={**FEATURES, "mock_feature_demographic_age": {"value": "58", "unit": "u_years"}}
        ),
        400,
        "malformed_request",
    ),
    (
        "a required feature is absent",
        cad_body(features={"mock_feature_demographic_sex": FEATURES["mock_feature_demographic_sex"]}),
        422,
        "missing_required_feature",
    ),
    (
        "a required feature is null",
        cad_body(
            features={
                "mock_feature_demographic_age": {"value": None, "unit": "u_years"},
                "mock_feature_demographic_sex": FEATURES["mock_feature_demographic_sex"],
            }
        ),
        422,
        "missing_required_feature",
    ),
]

HOSTILE_MONITORING_INPUTS = [
    ("body is an array", ["nope"], 400, "malformed_request"),
    (
        "observation is missing",
        {k: v for k, v in monitoring_body().items() if k != "observation"},
        400,
        "malformed_request",
    ),
    (
        "consent reference is missing",
        monitoring_body(
            observation={
                **monitoring_body()["observation"],
                "consent_id": "",
            }
        ),
        422,
        "consent_required",
    ),
    (
        "metrics are empty",
        monitoring_body(observation={**monitoring_body()["observation"], "metrics": []}),
        400,
        "malformed_request",
    ),
    (
        "an unknown metric",
        monitoring_body(
            observation={
                **monitoring_body()["observation"],
                "metrics": [{"metric_id": "mock_metric_nope", "value": 1, "unit": "u_count"}],
            }
        ),
        422,
        "unknown_metric",
    ),
    (
        "a metric with a wrong unit",
        monitoring_body(
            observation={
                **monitoring_body()["observation"],
                "metrics": [{"metric_id": "mock_metric_heart_rate", "value": 72, "unit": "u_count"}],
            }
        ),
        422,
        "unit_mismatch",
    ),
    (
        "a metric value outside the catalogue range",
        monitoring_body(
            observation={
                **monitoring_body()["observation"],
                "metrics": [{"metric_id": "mock_metric_heart_rate", "value": 9000, "unit": "u_rate"}],
            }
        ),
        422,
        "value_out_of_range",
    ),
    (
        "a contract version that is not implemented",
        monitoring_body(contract_version="v2"),
        400,
        "unsupported_contract_version",
    ),
]


@pytest.mark.parametrize(
    "label,body,status,code",
    HOSTILE_CAD_INPUTS,
    ids=[case[0] for case in HOSTILE_CAD_INPUTS],
)
def test_hostile_cad_inputs_produce_the_documented_error(label, body, status, code):
    contract = rc.ReferenceContract()
    key = "hostile-cad-" + hashlib.sha256(label.encode()).hexdigest()[:16]
    actual_status, response = contract.handle(CAD, body, {"Idempotency-Key": key})
    assert actual_status == status, label
    assert response["error"]["code"] == code, label
    # A rejected request never yields an inference output.
    for forbidden in ("score", "target", "explanation"):
        assert forbidden not in response, label
    assert contract.inference_count == 0, label


@pytest.mark.parametrize(
    "label,body,status,code",
    HOSTILE_MONITORING_INPUTS,
    ids=[case[0] for case in HOSTILE_MONITORING_INPUTS],
)
def test_hostile_monitoring_inputs_produce_the_documented_error(label, body, status, code):
    contract = rc.ReferenceContract()
    key = "hostile-mon-" + hashlib.sha256(label.encode()).hexdigest()[:16]
    actual_status, response = contract.handle(MON, body, {"Idempotency-Key": key})
    assert actual_status == status, label
    assert response["error"]["code"] == code, label
    for forbidden in ("score", "target", "explanation"):
        assert forbidden not in response, label


def test_every_hostile_input_code_is_documented_for_its_endpoint(openapi_document):
    """The error catalogue and the OpenAPI must agree with the behaviour."""
    documented = {}
    for path, item in openapi_document["paths"].items():
        endpoint = f"POST {path}"
        for status, codes in item["post"]["x-error-codes"].items():
            for code in codes:
                documented.setdefault((endpoint, code), set()).add(int(status))

    for endpoint, cases in ((CAD, HOSTILE_CAD_INPUTS), (MON, HOSTILE_MONITORING_INPUTS)):
        for label, _body, status, code in cases:
            assert (endpoint, code) in documented, f"{label}: {code} is not documented"
            assert status in documented[(endpoint, code)], f"{label}: {code} status mismatch"


# --------------------------------------------------------------------------- #
# 5. contract rules that the fixture pack does not exercise on its own
# --------------------------------------------------------------------------- #
def test_a_null_value_is_treated_as_not_provided():
    contract = rc.ReferenceContract()
    body = cad_body(
        features={
            "mock_feature_demographic_age": {"value": None, "unit": "u_years"},
            "mock_feature_demographic_sex": FEATURES["mock_feature_demographic_sex"],
        }
    )
    status, response = contract.handle(CAD, body, {})
    assert status == 422
    assert response["error"]["code"] == "missing_required_feature"


def test_a_zero_value_is_data_and_is_never_conflated_with_missing():
    contract = rc.ReferenceContract()
    body = cad_body(
        features={
            **FEATURES,
            "mock_feature_count": {"value": 0, "unit": "u_count"},
        }
    )
    status, response = contract.handle(CAD, body, {})
    assert status == 200
    assert "mock_feature_count" not in response["missing_features"]
    contributions = {
        c["feature"]: c["value"] for c in response["explanation"]["contributions"]
    }
    assert contributions["mock_feature_count"] == 0


def test_a_clinical_unit_is_rejected_by_the_mock_feature_schema(schema_documents, registry):
    """The placeholder-unit discipline is enforced by the schema, not by convention."""
    from conftest import validator_for
    from jsonschema.exceptions import ValidationError

    validator = validator_for(
        schema_documents["cad_tabular_prediction.request.schema.json"], registry
    )
    body = cad_body(
        features={
            **FEATURES,
            "mock_feature_vital_systolic": {"value": 142, "unit": "mmHg"},
        }
    )
    with pytest.raises(ValidationError) as excinfo:
        validator.validate(body)
    # The failure must be about the unit token, not about something incidental.
    assert "unit" in str(excinfo.value).lower() or "u_pressure" in str(excinfo.value)
    assert "unit" in " ".join(str(part) for part in excinfo.value.path)


def test_a_mock_feature_schema_can_never_be_served_as_a_production_payload(
    schema_documents, registry
):
    """A response scored against a mock schema must declare MOCK_SYNTHETIC."""
    from conftest import validator_for
    from jsonschema.exceptions import ValidationError

    validator = validator_for(
        schema_documents["cad_tabular_prediction.response.schema.json"], registry
    )
    contract = rc.ReferenceContract()
    _, response = contract.handle(CAD, cad_body(), {})
    assert response["feature_schema_id"].startswith("mock_")
    assert response["data_class"] == "MOCK_SYNTHETIC"

    tampered = dict(response)
    tampered["data_class"] = "PRODUCTION_INTERNAL"
    with pytest.raises(ValidationError) as excinfo:
        validator.validate(tampered)
    assert "data_class" in str(excinfo.value)
    assert "data_class" in " ".join(str(part) for part in excinfo.value.path)


def test_explanations_state_that_they_are_not_causal(fixtures):
    """Contributions are attributions, not causal effects, and never advice."""
    for fixture in fixtures:
        for step in fixture["steps"]:
            explanation = step["expected"]["body"].get("explanation")
            if explanation is None:
                continue
            note = explanation["note"].lower()
            assert "not causal effects" in note, fixture["fixture_id"]
            assert "no treatment, intervention or recommendation" in note, fixture["fixture_id"]
            assert "not changes in a calibrated probability" in note, fixture["fixture_id"]


@pytest.mark.parametrize(
    "model_id,method",
    [
        ("mock_model_a_v0.1.0", "tree_shap"),
        ("mock_model_d_v0.1.0", "lime"),
    ],
)
def test_live_explanations_carry_the_non_causal_and_non_probability_wording(model_id, method):
    """The rule is bound to the implementation, not only to the golden files."""
    contract = rc.ReferenceContract()
    status, response = contract.handle(CAD, cad_body(model_id=model_id), {})
    assert status == 200
    explanation = response["explanation"]
    assert explanation["method"] == method
    note = explanation["note"].lower()
    assert "not computed by" in note
    assert "from any trained model" in note
    assert "not changes in a calibrated probability" in note
    assert "never be displayed as percentage points" in note
    assert "not causal effects" in note
    assert "no treatment, intervention or recommendation" in note


def test_live_uncalibrated_response_carries_the_forbidden_percentage_rendering():
    contract = rc.ReferenceContract()
    status, response = contract.handle(CAD, cad_body(), {})
    assert status == 200
    assert response["calibration_id"] == "none"
    assert response["score"]["type"] == "uncalibrated_score"
    assert response["score"]["scale"] == "log_odds_margin"
    rendering = response["score"]["rendering"]
    assert rendering["percent_sign_allowed"] is False
    assert rendering["display_unit"] == "unitless"
    assert rendering["absolute_population_probability_claim"] is False


def test_live_calibrated_response_carries_cohort_context_and_no_population_claim():
    contract = rc.ReferenceContract()
    status, response = contract.handle(
        CAD, cad_body(model_id="mock_model_c_v0.1.0"), {}
    )
    assert status == 200
    score = response["score"]
    assert score["type"] == "calibrated_probability"
    assert score["scale"] == "probability"
    assert "raw_margin" in score
    context = score["calibration"]["cohort_context"]
    assert context["absolute_population_probability_claim"] is False
    assert score["rendering"]["percent_sign_allowed"] is False
    # The explanation still decomposes the margin, never the probability.
    check = response["explanation"]["sum_check"]
    assert check["margin_source"] == "score.raw_margin"
    assert check["margin"] == pytest.approx(score["raw_margin"])


def test_explanations_carry_no_action_or_advice_text(fixtures):
    """No contribution may be rendered as a recommendation (Phase 0 §2.1)."""
    forbidden = ("recommend", "statin", "treat", "therapy", "should be", "consider")
    for fixture in fixtures:
        for step in fixture["steps"]:
            explanation = step["expected"]["body"].get("explanation")
            if explanation is None:
                continue
            for path, text in iter_strings(explanation):
                if path.endswith("note"):
                    continue  # the note is the prohibition itself
                lowered = text.lower()
                for token in forbidden:
                    assert token not in lowered, f"{fixture['fixture_id']}{path}: {token}"
