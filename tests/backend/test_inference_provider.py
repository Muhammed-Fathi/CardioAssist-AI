"""M1c — internal CAD inference provider boundary and mock-behavior regressions.

Track A (CAD prediction) now goes through one internal provider. These tests
prove that the boundary is real, that it cannot be redirected, and that every
externally observable mock behavior (fixtures, idempotency, persistence,
Track separation, restart default) is unchanged.

Synthetic fixtures only: no dataset, model artifact or patient record is read.
"""

from __future__ import annotations

import ast
import copy
import inspect
import json
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import backend.app.inference.mock_synthetic as mock_synthetic_module
import backend.app.state as state_module
from backend.app.inference import (
    ACTIVE_PROVIDER_IDS,
    MOCK_SYNTHETIC_DATA_CLASS,
    MOCK_SYNTHETIC_PROVIDER_ID,
    REAL_MODEL_PROVIDER_ID,
    CadInferenceRequest,
    FailClosedRealModelProvider,
    MockSyntheticProvider,
    RealModelServingNotAuthorized,
    build_active_provider,
)
from backend.app.main import create_app
from backend.app.term1.openapi import SERVED_OPERATIONS

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "shared" / "contracts" / "fixtures"
INFERENCE_PACKAGE = ROOT / "backend" / "app" / "inference"
CAD = "/v1/predictions/cad-tabular"
MON = "/v1/monitoring/observations"
KEY = {"Idempotency-Key": "m1c-provider-boundary-001"}
MON_KEY = {"Idempotency-Key": "m1c-trackb-isolation-001"}


def _fixture(filename: str) -> dict:
    return json.loads((FIXTURES / filename).read_text(encoding="utf-8"))


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    return imported


# --------------------------------------------------------------------------- #
# 1. The boundary exists and only ever builds the mock implementation
# --------------------------------------------------------------------------- #


def test_active_provider_is_the_mock_synthetic_implementation(http_app):
    provider = http_app.state.mock.provider

    assert type(provider) is MockSyntheticProvider
    assert provider.provider_id == MOCK_SYNTHETIC_PROVIDER_ID == "mock_synthetic"
    assert provider.data_class == MOCK_SYNTHETIC_DATA_CLASS == "MOCK_SYNTHETIC"
    assert provider.supports_real_predictions is False


def test_provider_allowlist_contains_only_the_mock_implementation():
    assert ACTIVE_PROVIDER_IDS == frozenset({"mock_synthetic"})
    assert REAL_MODEL_PROVIDER_ID not in ACTIVE_PROVIDER_IDS


def test_provider_factory_has_no_selection_input():
    parameters = inspect.signature(build_active_provider).parameters
    assert list(parameters) == ["contracts"]
    assert all(
        parameter.kind
        in {inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY}
        for parameter in parameters.values()
    )


def test_application_has_no_provider_injection_or_configuration_hook():
    application_parameters = inspect.signature(create_app).parameters
    assert "provider" not in application_parameters
    assert "model" not in application_parameters

    state_parameters = inspect.signature(state_module.MockState).parameters
    assert "provider" not in state_parameters
    assert "model" not in state_parameters


@pytest.mark.parametrize("module", ["__init__.py", "registry.py", "mock_synthetic.py", "real_model.py", "types.py"])
def test_inference_modules_read_no_configuration_or_model_runtime(module):
    imported = _imports(INFERENCE_PACKAGE / module)
    forbidden = {
        "os",
        "pickle",
        "joblib",
        "sklearn",
        "numpy",
        "torch",
        "onnxruntime",
        "safetensors",
        "requests",
        "httpx",
        "socket",
        "subprocess",
    }
    assert not imported & forbidden


def test_runtime_import_does_not_load_the_offline_admission_module():
    probe = (
        "import sys, backend.app.main;"
        "assert 'backend.app.artifact_admission' not in sys.modules, "
        "'the Track A runtime must not import offline artifact admission'"
    )
    completed = subprocess.run(
        [sys.executable, "-c", probe], cwd=ROOT, capture_output=True, text=True
    )
    assert completed.returncode == 0, completed.stderr


def test_no_application_route_mentions_artifact_admission():
    source = inspect.getsource(create_app)
    assert "artifact" not in source
    assert "provider" not in source


def test_state_module_no_longer_reaches_the_mock_arithmetic_directly():
    assert not hasattr(state_module, "build_prediction")
    assert "mock_prediction" not in inspect.getsource(state_module).split("from .inference")[0]


# --------------------------------------------------------------------------- #
# 2. Existing mock HTTP behavior is preserved through the provider
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "filename",
    [
        "F-01-cad-tabular-valid-mock-clinical-v1.json",
        "F-03-missing-optional-features.json",
        "F-08-shap-sum-check.json",
        "F-11b-calibrated-score-rendering.json",
        "F-12-model-swap-same-schema.json",
    ],
)
def test_approved_fixture_responses_are_reproduced_through_the_provider(client, filename):
    fixture = _fixture(filename)
    path = fixture["endpoint"].split(" ", 1)[1]
    for step in fixture["steps"]:
        request = step["request"]
        response = client.post(path, json=request["body"], headers=request.get("headers"))
        assert response.status_code == step["expected"]["status"]
        assert response.json() == step["expected"]["body"]


def test_mock_explanation_output_is_unchanged_and_never_claimed_as_real_xai(client):
    """Correction 3: the synthetic SHAP-shaped fixture is preserved verbatim and
    is never presented as genuine TreeSHAP. No SHAP/LIME value is computed."""

    fixture = _fixture("F-08-shap-sum-check.json")
    request = fixture["steps"][0]["request"]
    response = client.post(
        "/v1/predictions/cad-tabular", json=request["body"], headers=request["headers"]
    )
    assert response.status_code == 200
    assert response.json() == fixture["steps"][0]["expected"]["body"]

    explanation = response.json()["explanation"]
    assert explanation["synthetic"] is True          # mock arithmetic, not real XAI
    assert explanation["method"] == "tree_shap"
    assert explanation["sum_check"]["passed"] is True

    # The runtime computes no SHAP/LIME library output anywhere.
    import sys

    assert "shap" not in sys.modules and "lime" not in sys.modules


def test_runtime_delegates_cad_scoring_once_through_the_provider(
    client, http_app, cad_body, monkeypatch
):
    calls = []
    real_builder = mock_synthetic_module.build_prediction

    def spy(*args, **kwargs):
        calls.append(args)
        return real_builder(*args, **kwargs)

    monkeypatch.setattr(mock_synthetic_module, "build_prediction", spy)
    response = client.post(CAD, json=cad_body, headers=KEY)

    assert response.status_code == 200
    assert len(calls) == 1
    assert http_app.state.mock.inference_count == 1


def test_provider_receives_the_narrow_typed_request_only(
    client, cad_body, monkeypatch
):
    captured = []
    original = MockSyntheticProvider.predict

    def spy(self, request):
        captured.append(request)
        return original(self, request)

    monkeypatch.setattr(MockSyntheticProvider, "predict", spy)
    response = client.post(CAD, json=cad_body, headers=KEY)
    assert response.status_code == 200

    request = captured[0]
    assert isinstance(request, CadInferenceRequest)
    assert request.model.model_id == "mock_model_a_v0.1.0"
    assert request.model.feature_schema_id == "mock_clinical_v1"
    assert {feature.name for feature in request.features} == {
        "mock_feature_demographic_age",
        "mock_feature_demographic_sex",
    }
    assert request.missing_optional == (
        "mock_feature_binary_flag",
        "mock_feature_count",
        "mock_feature_fraction",
        "mock_feature_lab_concentration",
        "mock_feature_vital_systolic",
    )
    for forbidden in ("contracts", "database", "repository", "observation", "patient"):
        assert not hasattr(request, forbidden)
        assert not hasattr(request.model, forbidden)


def test_mock_provider_is_deterministic_for_identical_typed_requests(http_app):
    from backend.app.inference import CadModelBinding

    contracts = http_app.state.mock.contracts
    entry = contracts.models["mock_model_a_v0.1.0"]
    provider = build_active_provider(contracts)
    provided = {
        "mock_feature_demographic_age": {"value": 43, "unit": "u_years"},
        "mock_feature_demographic_sex": {"value": "synthetic_category", "unit": "u_category"},
    }
    from backend.app.inference import CadFeature

    request = CadInferenceRequest(
        request_id="aaaaaaaa-1111-4111-8111-111111111111",
        audit_id="bbbbbbbb-2222-4222-8222-222222222222",
        model=CadModelBinding.from_registry_entry(entry),
        features=tuple(
            CadFeature(name, item["value"], item["unit"]) for name, item in provided.items()
        ),
        missing_optional=(),
    )

    first = provider.predict(request)
    second = provider.predict(request)

    assert first == second
    assert first["explanation"]["synthetic"] is True
    assert first["score"]["type"] == "uncalibrated_score"


def test_idempotent_replay_and_conflict_semantics_are_unchanged(client, http_app, cad_body):
    first = client.post(CAD, json=cad_body, headers=KEY)
    replay = client.post(CAD, json=cad_body, headers=KEY)

    changed = copy.deepcopy(cad_body)
    changed["features"]["mock_feature_demographic_age"]["value"] = 44
    conflict = client.post(CAD, json=changed, headers=KEY)

    assert first.status_code == replay.status_code == 200
    assert conflict.status_code == 409
    assert first.json()["idempotent_replay"] is False
    assert replay.json()["idempotent_replay"] is True
    assert conflict.json()["error"]["code"] == "idempotency_key_conflict"
    assert http_app.state.mock.inference_count == 1
    assert len(http_app.state.mock.audit_events) == 1


# --------------------------------------------------------------------------- #
# 3. Track A / Track B separation and persistence are unchanged
# --------------------------------------------------------------------------- #


def test_track_b_observations_never_invoke_the_cad_provider(
    client, http_app, monitoring_body, monkeypatch
):
    calls = []
    monkeypatch.setattr(
        MockSyntheticProvider, "predict", lambda self, request: calls.append(request)
    )

    response = client.post(MON, json=monitoring_body, headers=MON_KEY)

    assert response.status_code == 201
    assert calls == []
    assert http_app.state.mock.inference_count == 0
    assert http_app.state.mock.audit_events[0].event_type == "observation_recorded"
    assert http_app.state.mock.audit_events[0].model_id is None
    assert len(http_app.state.monitoring_repository.list_observations()) == 1
    assert len(http_app.state.monitoring_repository.list_audit_events()) == 1
    assert not {"score", "explanation", "target"} & response.json().keys()


def test_wearable_payload_cannot_reach_the_provider(client, http_app, cad_body, monkeypatch):
    calls = []
    monkeypatch.setattr(
        MockSyntheticProvider, "predict", lambda self, request: calls.append(request)
    )

    wearable_source = copy.deepcopy(cad_body)
    wearable_source["context"]["source"] = "simulated_wearable"
    assert (
        client.post(
            CAD,
            json=wearable_source,
            headers={"Idempotency-Key": "m1c-wearable-source-001"},
        ).status_code
        == 422
    )

    wearable_field = copy.deepcopy(cad_body)
    wearable_field["features"]["heart_rate_bpm"] = {"value": 61, "unit": "u_rate"}
    response = client.post(
        CAD, json=wearable_field, headers={"Idempotency-Key": "m1c-wearable-field-001"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "wearable_input_not_valid_for_cad_inference"
    assert calls == []
    assert http_app.state.mock.inference_count == 0


def test_monitoring_replay_stays_durable_and_idempotent(client, http_app, monitoring_body):
    first = client.post(MON, json=monitoring_body, headers=MON_KEY)
    replay = client.post(MON, json=monitoring_body, headers=MON_KEY)

    assert first.status_code == replay.status_code == 201
    assert replay.json()["idempotent_replay"] is True
    assert len(http_app.state.monitoring_repository.list_observations()) == 1
    assert len(http_app.state.monitoring_repository.list_audit_events()) == 1
    assert http_app.state.mock.inference_count == 0


# --------------------------------------------------------------------------- #
# 4. No research-only or real-model provider can be activated
# --------------------------------------------------------------------------- #


def test_the_offline_research_layer_added_no_provider_and_no_route(http_app):
    """AI-11.1's single-provider invariant, asserted at runtime where it can be.

    The experiment layer (``tests/experiments/test_research_facade.py``) checks
    the same boundary by static source inspection only, because the synthetic
    experiment CI environment installs exactly the research / audit / uci412
    pins — no FastAPI, no SQLAlchemy, no PyYAML. Importing a backend runtime
    module from that directory would give the experiment layer a dependency its
    environment deliberately does not have, so the dynamic assertion lives here,
    with the backend tests that provision it. Nothing about the invariant itself
    is weaker for the move: the allowlist, the construction guard and the route
    surface are all checked against the live application.
    """
    import backend.app.inference.registry as registry

    assert registry.ACTIVE_PROVIDER_IDS == frozenset({MOCK_SYNTHETIC_PROVIDER_ID})
    assert REAL_MODEL_PROVIDER_ID not in registry.ACTIVE_PROVIDER_IDS

    provider = build_active_provider(http_app.state.mock.contracts)
    assert type(provider) is MockSyntheticProvider
    assert http_app.state.mock.provider.provider_id == MOCK_SYNTHETIC_PROVIDER_ID

    # The mock prediction and monitoring operations keep their exact paths, and
    # no research, synthetic-facade, artifact or model-serving route was added
    # beside them. The served /v1 surface is the frozen C1 inventory: the two
    # legacy operations plus twenty additive Term 1 C1 operations.
    paths = sorted({str(getattr(route, "path", "")) for route in http_app.routes})
    served = {path for path in paths if path.startswith("/v1")}
    assert {CAD, MON} <= served
    assert served == {path for _method, path in SERVED_OPERATIONS}
    assert len(served) == 22
    # C1 consent withdrawal is a patient-wide consent operation, not a synthetic
    # research facade, so it is the single allowed exception to the "synth"
    # substring guard. Every other forbidden marker remains fully guarded.
    consent_path = "/v1/me/consent/synthetic-demo/revoke"
    for forbidden in ("research", "synth", "facade", "artifact", "registry"):
        offenders = [
            path
            for path in paths
            if forbidden in path.lower() and not (forbidden == "synth" and path == consent_path)
        ]
        assert not offenders, (forbidden, offenders)


def test_the_serving_runtime_never_imports_the_offline_research_layer():
    """A fresh interpreter proves the boundary, independent of test order."""
    probe = (
        "import sys, backend.app.main;"
        "offenders = [m for m in sys.modules if m == 'ai' or m.startswith('ai.')];"
        "assert not offenders, 'serving runtime imported the offline research layer'"
    )
    completed = subprocess.run(
        [sys.executable, "-c", probe], cwd=ROOT, capture_output=True, text=True
    )
    assert completed.returncode == 0, completed.stderr


def test_real_model_provider_cannot_be_constructed_or_called(cad_body):
    with pytest.raises(RealModelServingNotAuthorized):
        FailClosedRealModelProvider()
    with pytest.raises(RealModelServingNotAuthorized):
        FailClosedRealModelProvider(None)

    orphan = object.__new__(FailClosedRealModelProvider)
    with pytest.raises(RealModelServingNotAuthorized):
        orphan.predict(None)


def test_provider_factory_guard_rejects_a_non_mock_provider(monkeypatch):
    import backend.app.inference.registry as registry

    class Impostor:
        provider_id = REAL_MODEL_PROVIDER_ID
        data_class = "REAL_MODEL"
        supports_real_predictions = True

    monkeypatch.setattr(registry, "MockSyntheticProvider", lambda contracts: Impostor())
    with pytest.raises(RuntimeError, match="MOCK_SYNTHETIC"):
        registry.build_active_provider(object())


@pytest.mark.parametrize(
    "index, model_id",
    list(
        enumerate(
            [
                "reviewed_real_model",
                "synthetic-research-artifact-0001",
                "d047_cleveland_exploratory_model",
                "mock_model_unregistered_v0.1.0",
            ]
        )
    ),
)
def test_research_models_are_not_addressable_through_the_api(
    client, http_app, cad_body, index, model_id
):
    body = copy.deepcopy(cad_body)
    body["model_id"] = model_id
    response = client.post(CAD, json=body, headers={"Idempotency-Key": f"m1c-unregistered-{index}"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unknown_model"
    assert http_app.state.mock.inference_count == 0
    assert type(http_app.state.mock.provider) is MockSyntheticProvider


def test_environment_configuration_cannot_select_a_provider(monkeypatch, migrated_database_url):
    for name in (
        "CARDIOASSIST_MODEL_PROVIDER",
        "CARDIOASSIST_MODEL_PATH",
        "CARDIOASSIST_REAL_MODEL",
        "CARDIOASSIST_MODEL_ID",
        "MODEL_PROVIDER",
        "MODEL_PATH",
    ):
        monkeypatch.setenv(name, "reviewed_real_model")

    app = create_app(database_url=migrated_database_url)

    assert type(app.state.mock.provider) is MockSyntheticProvider
    assert app.state.mock.provider.provider_id == MOCK_SYNTHETIC_PROVIDER_ID
    assert app.state.mock.contracts.default_model_id == "mock_model_a_v0.1.0"
    app.state.database.dispose()


# --------------------------------------------------------------------------- #
# 5. MOCK_SYNTHETIC remains the default after a restart
# --------------------------------------------------------------------------- #


def test_mock_synthetic_remains_the_default_after_restart(
    client, http_app, http_validators, cad_body, migrated_database_url
):
    first = client.post(CAD, json=cad_body, headers=KEY)
    assert first.status_code == 200
    assert first.json()["model_id"] == "mock_model_a_v0.1.0"
    assert first.json()["provenance"]["artifact_hashes"] == {
        "model": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "preprocessing": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    }
    assert first.json()["provenance"]["dataset_access_status"] == (
        "not_applicable_no_dataset_used"
    )

    restarted = create_app(database_url=migrated_database_url)
    assert type(restarted.state.mock.provider) is MockSyntheticProvider
    assert restarted.state.mock.provider.provider_id == MOCK_SYNTHETIC_PROVIDER_ID
    assert restarted.state.mock.inference_count == 0
    assert restarted.state.mock.contracts.default_model_id == "mock_model_a_v0.1.0"

    with TestClient(restarted) as other:
        response = other.post(CAD, json=cad_body, headers=KEY)
    http_validators(response, CAD)
    assert response.status_code == 200
    assert response.json()["model_id"] == "mock_model_a_v0.1.0"
    assert restarted.state.mock.inference_count == 1
