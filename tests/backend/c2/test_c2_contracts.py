"""Track 2 contract artifacts match the code and validate real DOC responses."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from backend.app.term1.errors import ERROR_CATALOGUE
from backend.app.term1_c2_documents import constants as C
from backend.app.term1_c2_documents.contracts import generate
from backend.app.term1_c2_documents.contracts.operations import ERROR_CODES, OPERATIONS, SCHEMAS
from backend.app.term1_c2_documents.errors import DOCUMENT_ERROR_CATALOGUE

from .conftest import requires_native_ocr

CONTRACTS = Path(__file__).resolve().parents[3] / "backend" / "app" / "term1_c2_documents" / "contracts"
FIXTURES = CONTRACTS.parent / "fixtures"


def test_generated_artifacts_are_in_sync_with_source():
    # Regenerate into memory and compare to the committed artifacts byte-for-byte.
    import tempfile
    from unittest import mock

    committed = {p.name: p.read_bytes() for p in CONTRACTS.glob("*.yaml")}
    committed.update({p.name: p.read_bytes() for p in CONTRACTS.glob("*.json")})
    committed.update({p.name: p.read_bytes() for p in (CONTRACTS / "schemas").glob("*.json")})
    with tempfile.TemporaryDirectory() as tmp:
        with mock.patch.object(generate, "HERE", Path(tmp)):
            generate.generate()
        regenerated = {p.name: p.read_bytes() for p in Path(tmp).glob("*.yaml")}
        regenerated.update({p.name: p.read_bytes() for p in Path(tmp).glob("*.json")})
        regenerated.update({p.name: p.read_bytes() for p in (Path(tmp) / "schemas").glob("*.json")})
    assert committed == regenerated


def test_error_catalogue_artifacts_match_code():
    assert ERROR_CODES == {
        code: {"status": status, "message": message}
        for code, (status, message) in DOCUMENT_ERROR_CATALOGUE.items()
    }
    yaml_doc = yaml.safe_load((CONTRACTS / "errors.c2.yaml").read_text())
    json_doc = json.loads((CONTRACTS / "errors.c2.json").read_text())
    assert yaml_doc["codes"] == ERROR_CODES
    assert json_doc["codes"] == ERROR_CODES


def test_every_doc_error_code_resolves_in_a_catalogue():
    # Each code referenced by a DOC operation must exist in the frozen C1
    # catalogue or the additive C2 catalogue (no invented codes).
    for operation in OPERATIONS:
        for response in operation["responses"]:
            for code in response.get("codes", []):
                assert code in ERROR_CATALOGUE or code in DOCUMENT_ERROR_CATALOGUE, code


def test_operation_inventory_is_exactly_doc1_through_doc7():
    assert [op["id"] for op in OPERATIONS] == [f"DOC{i}" for i in range(1, 8)]
    paths_doc = yaml.safe_load((CONTRACTS / "paths-documents.yaml").read_text())
    assert [op["id"] for op in paths_doc["operations"]] == [f"DOC{i}" for i in range(1, 8)]
    # Mutating operations are idempotent; reads are not.
    for op in OPERATIONS:
        if op["method"] == "POST":
            assert op["idempotent"] is True
        else:
            assert op["idempotent"] is False


def test_schemas_are_valid_draft2020_12():
    for name, schema in SCHEMAS.items():
        Draft202012Validator.check_schema(schema)
        on_disk = json.loads((CONTRACTS / "schemas" / name).read_text())
        assert on_disk == schema


def _validator(name):
    return Draft202012Validator(SCHEMAS[name])


def _auth(token, key=None):
    headers = {"Authorization": f"Bearer {token}"}
    if key:
        headers["Idempotency-Key"] = key
    return headers


@requires_native_ocr
def test_real_doc_responses_validate_against_schemas(client, patient):
    token = patient["token"]
    data = (FIXTURES / "resting_text.pdf").read_bytes()
    up = client.post("/v1/me/documents", headers=_auth(token, f"up-{uuid.uuid4()}"),
                     data={"contract_version": "v1", "document_kind": C.DOC_KIND_RESTING,
                           "fixture_template_id": C.TEMPLATE_RESTING},
                     files={"file": ("resting_text.pdf", data, "application/pdf")})
    assert up.status_code == 201
    _validator("term1_document_upload_response.schema.json").validate(up.json())
    document_id = up.json()["document_id"]

    listing = client.get("/v1/me/documents", headers=_auth(token))
    _validator("term1_document_list_response.schema.json").validate(listing.json())

    meta = client.get(f"/v1/me/documents/{document_id}", headers=_auth(token))
    _validator("term1_document_read_response.schema.json").validate(meta.json())

    ext = client.post(f"/v1/me/documents/{document_id}/extract",
                      headers=_auth(token, f"ex-{uuid.uuid4()}"))
    _validator("term1_document_extraction_response.schema.json").validate(ext.json())
    extraction_id = ext.json()["extraction_id"]

    read = client.get(f"/v1/me/documents/{document_id}/extraction", headers=_auth(token))
    _validator("term1_document_extraction_response.schema.json").validate(read.json())

    confirm = client.post(
        f"/v1/me/documents/{document_id}/confirm", headers=_auth(token, f"cf-{uuid.uuid4()}"),
        json={"contract_version": "v1", "extraction_id": extraction_id, "extraction_version": 1,
              "confirmed_inputs": {"age": 54, "sex": 1, "cp": 2, "trestbps": 130, "restecg": 0},
              "units": {"age": "years", "trestbps": "mmHg"}, "missing_reasons": {},
              "confirm_fabricated_demo_inputs": True})
    assert confirm.status_code == 200
    _validator("term1_document_confirm_response.schema.json").validate(confirm.json())


@requires_native_ocr
def test_confirm_request_schema_rejects_bad_payloads():
    validator = _validator("term1_document_confirm_request.schema.json")
    good = {"contract_version": "v1", "extraction_id": str(uuid.uuid4()),
            "extraction_version": 1,
            "confirmed_inputs": {"age": 54, "sex": 1, "cp": 2, "trestbps": 130, "restecg": 0},
            "units": {"age": "years", "trestbps": "mmHg"}, "missing_reasons": {},
            "confirm_fabricated_demo_inputs": True}
    validator.validate(good)
    # Attestation must be exactly true.
    bad = {**good, "confirm_fabricated_demo_inputs": False}
    assert not validator.is_valid(bad)
    # Unknown panel field is rejected by the closed schema.
    bad = {**good, "confirmed_inputs": {**good["confirmed_inputs"], "chol": 200}}
    assert not validator.is_valid(bad)
