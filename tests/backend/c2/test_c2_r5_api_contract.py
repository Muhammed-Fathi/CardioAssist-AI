"""T2-R5 regressions: exact multipart contract, bounded JSON, pixel metadata,
strict DOC7 schema and the DOC route inventory.

The final integrated route inventory (existing 22 + 5 core C2 + 7 document = 34)
is assembled by Track 1's shared wiring; this contributor surface registers
exactly the seven DOC operations and does not weaken the C1 guards.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from backend.app.term1_c2_documents import constants as C

from .conftest import requires_native_ocr

FIXTURES = Path(__file__).resolve().parents[3] / "backend" / "app" / "term1_c2_documents" / "fixtures"

DOC_PATHS = {
    ("POST", "/v1/me/documents"),
    ("GET", "/v1/me/documents"),
    ("GET", "/v1/me/documents/{document_id}"),
    ("GET", "/v1/me/documents/{document_id}/content"),
    ("POST", "/v1/me/documents/{document_id}/extract"),
    ("GET", "/v1/me/documents/{document_id}/extraction"),
    ("POST", "/v1/me/documents/{document_id}/confirm"),
}


def _auth(token, key=None):
    headers = {"Authorization": f"Bearer {token}"}
    if key:
        headers["Idempotency-Key"] = key
    return headers


def _fields():
    return {"contract_version": "v1", "document_kind": C.DOC_KIND_RESTING,
            "fixture_template_id": C.TEMPLATE_RESTING}


def test_doc_route_inventory_is_exactly_seven(c2_app):
    routes = set()
    for route in c2_app.routes:
        methods = getattr(route, "methods", None) or set()
        path = getattr(route, "path", "")
        for method in methods:
            if method in ("GET", "POST") and path.startswith("/v1/me/documents"):
                routes.add((method, path))
    assert routes == DOC_PATHS


def test_extra_form_field_rejected(client, patient):
    data = (FIXTURES / "resting_text.pdf").read_bytes()
    fields = _fields()
    fields["unexpected"] = "x"
    response = client.post("/v1/me/documents", headers=_auth(patient["token"], f"up-{uuid.uuid4()}"),
                           data=fields, files={"file": ("resting_text.pdf", data, "application/pdf")})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "malformed_request"


def test_wrong_file_part_name_rejected(client, patient):
    data = (FIXTURES / "resting_text.pdf").read_bytes()
    response = client.post("/v1/me/documents", headers=_auth(patient["token"], f"up-{uuid.uuid4()}"),
                           data=_fields(),
                           files={"document": ("resting_text.pdf", data, "application/pdf")})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "malformed_request"


def test_duplicate_file_part_rejected(client, patient):
    data = (FIXTURES / "resting_text.pdf").read_bytes()
    response = client.post("/v1/me/documents", headers=_auth(patient["token"], f"up-{uuid.uuid4()}"),
                           data=_fields(),
                           files=[("file", ("a.pdf", data, "application/pdf")),
                                  ("file", ("b.pdf", data, "application/pdf"))])
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "malformed_request"


def test_json_body_over_cap_rejected(client, patient):
    document_id = str(uuid.uuid4())
    oversized = b'{"contract_version":"v1","pad":"' + b"x" * (C.JSON_BODY_CAP_BYTES + 1024) + b'"}'
    response = client.post(
        f"/v1/me/documents/{document_id}/confirm",
        headers={**_auth(patient["token"], f"cf-{uuid.uuid4()}"),
                 "Content-Type": "application/json"},
        content=oversized)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


def _confirm_body(extraction_id="x", **overrides):
    body = {
        "contract_version": "v1", "extraction_id": extraction_id, "extraction_version": 1,
        "confirmed_inputs": {"age": 54, "sex": 1, "cp": 2, "trestbps": 130, "restecg": 0},
        "units": {"age": "years", "trestbps": "mmHg"}, "missing_reasons": {},
        "confirm_fabricated_demo_inputs": True,
    }
    body.update(overrides)
    return body


def test_doc7_missing_mapping_rejected(client, patient):
    document_id = str(uuid.uuid4())
    body = _confirm_body()
    del body["units"]  # no silent default to {}
    response = client.post(f"/v1/me/documents/{document_id}/confirm",
                           headers=_auth(patient["token"], f"cf-{uuid.uuid4()}"), json=body)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "malformed_request"


def test_doc7_unknown_key_rejected(client, patient):
    document_id = str(uuid.uuid4())
    body = _confirm_body(extra="x")
    response = client.post(f"/v1/me/documents/{document_id}/confirm",
                           headers=_auth(patient["token"], f"cf-{uuid.uuid4()}"), json=body)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "malformed_request"


@requires_native_ocr
def test_doc1_response_includes_pixel_metadata(client, patient):
    png = (FIXTURES / "resting.png").read_bytes()
    response = client.post("/v1/me/documents", headers=_auth(patient["token"], f"up-{uuid.uuid4()}"),
                           data=_fields(), files={"file": ("resting.png", png, "image/png")})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["pixel_width"] and body["pixel_height"]
    assert body["pixel_width"] <= C.MAX_PIXEL_SIDE
    # A text-layer PDF carries null pixel metadata.
    pdf = (FIXTURES / "resting_text.pdf").read_bytes()
    response2 = client.post("/v1/me/documents", headers=_auth(patient["token"], f"up-{uuid.uuid4()}"),
                            data=_fields(), files={"file": ("resting_text.pdf", pdf, "application/pdf")})
    assert response2.status_code == 201
    assert response2.json()["pixel_width"] is None
