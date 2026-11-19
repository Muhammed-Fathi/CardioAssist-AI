"""RH-04.5 cross-boundary regression: offline fixtures cannot become /v1 input.

This suite intentionally reads the checked-in offline fixture *document* rather
than importing ``ai`` or replaying a bundle.  The experiment suite validates
that document against the live offline registry/facade.  Keeping this bridge
stdlib-only prevents backend-only CI from acquiring research/ML dependencies.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from backend.app.inference import MOCK_SYNTHETIC_PROVIDER_ID, MockSyntheticProvider

ROOT = Path(__file__).resolve().parents[2]
CAD = "/v1/predictions/cad-tabular"
MONITORING = "/v1/monitoring/observations"
OFFLINE_PACK_PATH = ROOT / "research" / "intake" / "fixtures" / "offline_io.v1.json"
MOCK_FIXTURES = ROOT / "shared" / "contracts" / "fixtures"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _offline_pack() -> dict:
    return _json(OFFLINE_PACK_PATH)


def _offline_model_ids() -> tuple[str, ...]:
    return tuple(sorted({request["model_id"] for request in _offline_pack()["requests"].values()}))


def _materialize_offline_request(base: dict, edits: list[dict]) -> dict:
    """Apply the checked-in fixture edits without importing the ML replay helper."""
    request = copy.deepcopy(base)
    for edit in edits:
        parent = request
        for segment in edit["path"][:-1]:
            parent = parent[segment]
        field = edit["path"][-1]
        if edit["op"] == "delete":
            del parent[field]
        else:
            parent[field] = copy.deepcopy(edit["value"])
    return request


OFFLINE_MODEL_IDS = _offline_model_ids()
EXPECTED_OFFLINE_MODEL_IDS = (
    "synth_ai7_da_a1_clinical_core_labs_v1",
    "synth_ai7_da_a2_hungary_locked_transportability_v1",
    "synth_ai7_da_a2_resting_labs_v1",
    "synth_ai7_da_a2_resting_v1",
    "synth_ai8_uci412_da_a1_basic_clinical",
)


def _fixture(filename: str) -> dict:
    return _json(MOCK_FIXTURES / filename)


@pytest.mark.parametrize("model_id", OFFLINE_MODEL_IDS)
def test_every_registry_bound_offline_model_id_is_rejected_by_mock_cad(
    client, http_app, cad_body, model_id
):
    """All five IDs from the registry-bound RH-04 base requests fail before scoring."""
    assert OFFLINE_MODEL_IDS == EXPECTED_OFFLINE_MODEL_IDS
    body = copy.deepcopy(cad_body)
    body["model_id"] = model_id

    response = client.post(
        CAD,
        json=body,
        headers={"Idempotency-Key": f"rh045-offline-model-{OFFLINE_MODEL_IDS.index(model_id)}"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unknown_model"
    assert http_app.state.mock.inference_count == 0
    assert type(http_app.state.mock.provider) is MockSyntheticProvider
    assert http_app.state.mock.provider.provider_id == MOCK_SYNTHETIC_PROVIDER_ID


def test_offline_request_and_response_structures_cannot_pass_as_v1_mock_contracts(
    client, http_app
):
    """Neither side of the offline fixture pair has the mock wire envelope."""
    pack = _offline_pack()
    requests = [
        _materialize_offline_request(pack["requests"][case["route"]], case["edits"])
        for case in pack["cases"]
    ]
    payloads = requests + [case["expected"] for case in pack["cases"]]

    assert len(pack["requests"]) == 5
    assert len(requests) == len(pack["cases"]) == 29
    for index, payload in enumerate(payloads):
        assert "contract_version" not in payload
        assert "data_class" not in payload
        response = client.post(
            CAD,
            json=payload,
            headers={"Idempotency-Key": f"rh045-cross-contract-{index}"},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "malformed_request"
    assert http_app.state.mock.inference_count == 0
    assert http_app.state.mock.audit_events == ()


def test_offline_refusals_leave_mock_surface_track_isolation_and_replay_intact(
    client, http_app, cad_body
):
    """Cross-boundary failures do not perturb approved mock fixtures or Track B."""
    rejected = copy.deepcopy(cad_body)
    rejected["model_id"] = OFFLINE_MODEL_IDS[0]
    rejected_response = client.post(
        CAD,
        json=rejected,
        headers={"Idempotency-Key": "rh045-pre-fixture-offline-id"},
    )
    assert rejected_response.status_code == 422
    assert http_app.state.mock.inference_count == 0

    replay_fixture = _fixture("F-05-idempotent-replay.json")
    first_step, replay_step = replay_fixture["steps"]
    first = client.post(
        CAD, json=first_step["request"]["body"], headers=first_step["request"]["headers"]
    )
    replay = client.post(
        CAD, json=replay_step["request"]["body"], headers=replay_step["request"]["headers"]
    )
    assert first.status_code == replay.status_code == 200
    assert first.json() == first_step["expected"]["body"]
    assert replay.json() == replay_step["expected"]["body"]
    assert http_app.state.mock.inference_count == 1

    monitoring_step = _fixture("F-04-monitoring-observation-valid.json")["steps"][0]
    monitoring = client.post(
        MONITORING,
        json=monitoring_step["request"]["body"],
        headers=monitoring_step["request"]["headers"],
    )
    assert monitoring.status_code == 201
    assert monitoring.json() == monitoring_step["expected"]["body"]
    assert http_app.state.mock.inference_count == 1

    openapi = client.get("/openapi.json").json()
    assert set(openapi["paths"]) == {CAD, MONITORING}
    assert type(http_app.state.mock.provider) is MockSyntheticProvider
    assert http_app.state.mock.provider.provider_id == MOCK_SYNTHETIC_PROVIDER_ID


def test_no_offline_artifact_or_real_scoring_entrypoint_is_reachable_through_backend(
    client, http_app, cad_body
):
    """Untrusted artifact-shaped fields are neither routed, loaded, nor echoed."""
    canaries = (
        "/tmp/rh045-private-bundle",
        "rh045-signing-key-material",
        "rh045-real-model-loader",
    )
    probe = copy.deepcopy(cad_body)
    probe["model_id"] = OFFLINE_MODEL_IDS[0]
    probe["offline_research_artifact"] = {
        "bundle_dir": canaries[0],
        "signing_key": canaries[1],
        "model_loader": canaries[2],
    }
    response = client.post(
        CAD,
        json=probe,
        headers={"Idempotency-Key": "rh045-artifact-probe"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unknown_model"
    serialized = response.text
    assert not any(canary in serialized for canary in canaries)
    assert http_app.state.mock.inference_count == 0
    for path in (
        "/v1/research",
        "/v1/research/inference",
        "/v1/offline-fixtures",
        "/v1/artifacts",
        "/v1/models/real",
    ):
        assert client.post(path, json={}).status_code == 404


def test_mock_null_equivalence_does_not_erase_offline_missing_reason_distinction(
    client, http_app, cad_body
):
    """HTTP null=omission; RH-04 records must retain distinct omission/null reasons."""
    omitted = copy.deepcopy(cad_body)
    explicit_null = copy.deepcopy(cad_body)
    explicit_null["features"]["mock_feature_vital_systolic"] = {
        "value": None,
        "unit": "u_pressure",
    }
    first = client.post(
        CAD, json=omitted, headers={"Idempotency-Key": "rh045-http-omitted"}
    )
    second = client.post(
        CAD, json=explicit_null, headers={"Idempotency-Key": "rh045-http-null"}
    )
    assert first.status_code == second.status_code == 200
    first_body, second_body = first.json(), second.json()
    assert first_body["missing_features"] == second_body["missing_features"]
    assert first_body["warnings"] == second_body["warnings"]
    assert first_body["score"] == second_body["score"]
    assert first_body["audit_id"] != second_body["audit_id"]

    cases = {case["id"]: case for case in _offline_pack()["cases"]}
    omitted_case, null_case = cases["optional"], cases["optional-null"]
    assert omitted_case["expected"]["status"] == null_case["expected"]["status"] == "ABSTAIN"
    assert omitted_case["edits"][0]["op"] == "delete"
    assert null_case["edits"][0] == {
        "op": "set",
        "path": ["records", 0, "features", "trestbps"],
        "value": None,
    }
    omitted_reason = omitted_case["expected"]["outcomes"][0][
        "missing_fields_with_reason"
    ]
    null_reason = null_case["expected"]["outcomes"][0]["missing_fields_with_reason"]
    assert omitted_reason == [["trestbps", "not_provided"]]
    assert null_reason == [["trestbps", "not_measured"]]
    assert omitted_reason != null_reason
    assert http_app.state.mock.inference_count == 2
