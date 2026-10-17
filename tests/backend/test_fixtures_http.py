"""Golden HTTP checks read committed files, not ReferenceContract output."""

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parents[2] / "shared" / "contracts" / "fixtures"
INDEX = json.loads((FIXTURES / "index.json").read_text(encoding="utf-8"))
SUPPORTED = [entry for entry in INDEX["fixtures"] if entry["fixture_id"] != "F-11c"]


@pytest.mark.parametrize("entry", SUPPORTED, ids=lambda entry: entry["fixture_id"])
def test_committed_fixture_over_http(client, entry):
    fixture = json.loads((FIXTURES / entry["file"]).read_text(encoding="utf-8"))
    path = fixture["endpoint"].split(" ", 1)[1]
    for step in fixture["steps"]:
        request = step["request"]
        response = client.post(path, json=request["body"], headers=request.get("headers"))
        assert response.status_code == step["expected"]["status"]
        assert response.json() == step["expected"]["body"]


def test_legacy_lime_fixture_is_not_a_live_computed_result(client, http_app):
    """Explicit M1a.2 restriction, NOT a skipped or rewritten M1a.1 fixture."""
    fixture = json.loads((FIXTURES / "F-11c-lime-explanation.json").read_text(encoding="utf-8"))
    request = fixture["steps"][0]["request"]
    response = client.post(
        "/v1/predictions/cad-tabular", json=request["body"], headers=request["headers"]
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "model_unavailable"
    assert "explanation" not in response.json()
    assert "local_fidelity_r2" not in response.text
    assert http_app.state.mock.inference_count == 0
    assert http_app.state.mock.audit_events == ()


def test_no_fixture_is_silently_omitted_from_http_coverage():
    assert len(SUPPORTED) == 29
    assert {entry["fixture_id"] for entry in INDEX["fixtures"]} - {
        entry["fixture_id"] for entry in SUPPORTED
    } == {"F-11c"}
