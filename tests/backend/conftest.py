"""Independent HTTP clients/validators; never import the fixture oracle.

Every POST response from the test client is checked against the shared schema
AND the endpoint's documented status/code catalogue, including failure cases.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest
import yaml
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from backend.app.main import create_app

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "shared" / "contracts"
CAD = "/v1/predictions/cad-tabular"
MON = "/v1/monitoring/observations"


@pytest.fixture(scope="session")
def http_validators():
    schemas = {
        path.name: json.loads(path.read_text(encoding="utf-8"))
        for path in (CONTRACTS / "schemas").glob("*.json")
    }
    registry = Registry().with_resources(
        (document["$id"], Resource.from_contents(document, default_specification=DRAFT202012))
        for document in schemas.values()
    )
    common = schemas["common.schema.json"]
    error_schema = {"$ref": common["$id"] + "#/$defs/ErrorResponse"}
    spec = yaml.safe_load((CONTRACTS / "openapi.yaml").read_text(encoding="utf-8"))
    validators = {}
    for path, item in spec["paths"].items():
        operation = item["post"]
        success = next(s for s in operation["responses"] if str(s).startswith("2"))
        filename = Path(operation["responses"][success]["content"]["application/json"]["schema"]["$ref"]).name
        validators[path] = Draft202012Validator(
            schemas[filename], registry=registry,
            format_checker=Draft202012Validator.FORMAT_CHECKER,
        )
    error_validator = Draft202012Validator(
        error_schema, registry=registry, format_checker=Draft202012Validator.FORMAT_CHECKER
    )

    def check(response, path):
        operation = spec["paths"][path]["post"]
        assert str(response.status_code) in operation["responses"], response.text
        assert response.headers["content-type"].startswith("application/json")
        if response.status_code >= 400:
            body = response.json()
            error_validator.validate(body)
            assert body["error"]["code"] in operation["x-error-codes"][str(response.status_code)]
        else:
            validators[path].validate(response.json())

    return check


class SchemaCheckingClient(TestClient):
    def __init__(self, app, check, **kwargs):
        super().__init__(app, **kwargs)
        self.check = check

    def request(self, method, url, **kwargs):
        response = super().request(method, url, **kwargs)
        path = urlsplit(str(url)).path
        if method.upper() == "POST" and path in {CAD, MON}:
            self.check(response, path)
        return response


@pytest.fixture
def monotonic_time():
    return [1000.0]


@pytest.fixture
def http_app(monotonic_time):
    return create_app(clock=lambda: monotonic_time[0])


@pytest.fixture
def client(http_app, http_validators):
    with SchemaCheckingClient(http_app, http_validators) as client:
        yield client


@pytest.fixture
def cad_body():
    # Deliberately not a committed fixture profile, and not built by the oracle.
    return {
        "contract_version": "v1",
        "request_id": "aaaaaaaa-1111-4111-8111-111111111111",
        "feature_schema_id": "mock_clinical_v1",
        "features": {
            "mock_feature_demographic_age": {"value": 43, "unit": "u_years"},
            "mock_feature_demographic_sex": {"value": "synthetic_category", "unit": "u_category"},
        },
        "context": {
            "source": "benchmark_import", "recorded_at": "2026-10-16T10:20:00Z",
            "patient_ref": "pseudo_http_demo",
        },
    }


@pytest.fixture
def monitoring_body():
    return {
        "contract_version": "v1",
        "request_id": "bbbbbbbb-2222-4222-8222-222222222222",
        "observation": {
            "patient_ref": "pseudo_http_demo",
            "observed_at": "2026-10-16T10:25:00Z",
            "source": "simulated_wearable",
            "source_detail": "synthetic HTTP test adapter, no device",
            "consent_id": "consent_mock_http_demo",
            "metrics": [{"metric_id": "mock_metric_heart_rate", "value": 64, "unit": "u_rate"}],
        },
    }
