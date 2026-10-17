"""The served API description derives from the approved files, offline."""

import ast
import json
from pathlib import Path
import subprocess
import sys

from openapi_spec_validator import validate as validate_openapi

ROOT = Path(__file__).resolve().parents[2]


def test_bundled_openapi_is_valid_and_has_exactly_the_approved_operations(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    document = response.json()
    validate_openapi(document)
    assert set(document["paths"]) == {
        "/v1/predictions/cad-tabular", "/v1/monitoring/observations"
    }
    for path, item in document["paths"].items():
        assert set(item) == {"post"}
        assert "422" in item["post"]["responses"]
        assert "HTTPValidationError" not in json.dumps(item)
    assert document["servers"] == [{
        "url": "/", "description": (
            "Relative to the deployment origin. This project is local-first at $0 "
            "(D-041); no hosted endpoint exists and none is implied by this document."
        )
    }]


def test_every_served_ref_resolves_inside_the_same_document(client):
    document = client.get("/openapi.json").json()

    def walk(node):
        if isinstance(node, dict):
            if "$ref" in node:
                ref = node["$ref"]
                assert ref.startswith("#/"), ref
                target = document
                for part in ref[2:].split("/"):
                    target = target[part.replace("~1", "/").replace("~0", "~")]
                assert target
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(document)


def test_cdn_docs_and_unapproved_api_sketches_are_not_added(client):
    for path in [
        "/docs", "/redoc", "/v1/models/current", "/v1/patients/pseudo_demo/monitoring", "/v1/audit",
    ]:
        assert client.get(path).status_code == 404


def test_preview_host_is_not_rejected(client, cad_body):
    response = client.post(
        "/v1/predictions/cad-tabular", json=cad_body,
        headers={
            "Host": "8000-synthetic-preview.e2b.app", "Idempotency-Key": "preview-host-key-001",
        },
    )
    assert response.status_code == 200


def test_backend_and_http_tests_do_not_import_the_fixture_oracle():
    for directory in (ROOT / "backend" / "app", ROOT / "tests" / "backend"):
        for path in directory.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    assert all("reference_contract" not in alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    assert "reference_contract" not in (node.module or "")
    # Contract tests may already have imported their oracle in pytest's process.
    # Verify independently that starting the server does not load that module.
    result = subprocess.run(
        [sys.executable, "-c", (
            "import sys; from backend.app.main import app; "
            "assert not any('reference_contract' in key for key in sys.modules); print('PASS')"
        )], cwd=ROOT, capture_output=True, text=True, check=True,
    )
    assert result.stdout.strip() == "PASS"
