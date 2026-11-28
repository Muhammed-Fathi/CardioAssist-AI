"""DOC1–DOC7 HTTP lifecycle over the real C1 auth + genuine OCR worker."""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path


from backend.app.term1_c2_documents import constants as C

from .conftest import requires_native_ocr

FIXTURES = Path(__file__).resolve().parents[3] / "backend" / "app" / "term1_c2_documents" / "fixtures"


def _fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _upload(client, token, name, *, kind=C.DOC_KIND_RESTING,
            template=C.TEMPLATE_RESTING, key=None, expect=201):
    data = _fixture(name)
    response = client.post(
        "/v1/me/documents",
        headers={"Authorization": f"Bearer {token}",
                 "Idempotency-Key": key or f"up-{uuid.uuid4()}"},
        data={"contract_version": "v1", "document_kind": kind,
              "fixture_template_id": template},
        files={"file": (name, data, "application/octet-stream")},
    )
    assert response.status_code == expect, response.text
    return response


def _auth(token, key=None):
    headers = {"Authorization": f"Bearer {token}"}
    if key:
        headers["Idempotency-Key"] = key
    return headers


@requires_native_ocr
def test_full_resting_lifecycle_upload_extract_confirm(client, patient):
    token = patient["token"]
    up = _upload(client, token, "resting_text.pdf")
    doc = up.json()
    assert doc["status"] == C.UPLOAD_STORED
    assert doc["document_kind"] == C.DOC_KIND_RESTING
    assert doc["page_count"] == 1
    document_id = doc["document_id"]
    assert doc["content_sha256"] == hashlib.sha256(_fixture("resting_text.pdf")).hexdigest()
    assert up.headers["Cache-Control"] == "no-store"

    # DOC2 list
    listing = client.get("/v1/me/documents", headers=_auth(token))
    assert listing.status_code == 200
    assert any(item["document_id"] == document_id for item in listing.json()["items"])

    # DOC3 read
    meta = client.get(f"/v1/me/documents/{document_id}", headers=_auth(token))
    assert meta.status_code == 200
    assert meta.json()["document_id"] == document_id

    # DOC4 content — verified bytes + hardening headers
    content = client.get(f"/v1/me/documents/{document_id}/content", headers=_auth(token))
    assert content.status_code == 200
    assert content.content == _fixture("resting_text.pdf")
    assert content.headers["X-Content-Type-Options"] == "nosniff"
    assert content.headers["Content-Security-Policy"] == "default-src 'none'"
    assert content.headers["Content-Disposition"].startswith("attachment;")
    assert content.headers["Cache-Control"] == "no-store"

    # DOC5 extract — genuine, version 1
    ext = client.post(f"/v1/me/documents/{document_id}/extract",
                      headers=_auth(token, f"ex-{uuid.uuid4()}"))
    assert ext.status_code == 200, ext.text
    extraction = ext.json()
    assert extraction["extraction_version"] == 1
    assert extraction["extraction_status"] == C.STATUS_EXTRACTED_DRAFT
    assert extraction["is_confirmed"] is False
    values = {f["field_name"]: f["typed_value_json"] for f in extraction["fields"]}
    assert values == {"age": 54, "sex": 1, "cp": 2, "trestbps": 130, "restecg": 0}
    extraction_id = extraction["extraction_id"]

    # DOC6 read extraction
    read = client.get(f"/v1/me/documents/{document_id}/extraction", headers=_auth(token))
    assert read.status_code == 200
    assert read.json()["extraction_id"] == extraction_id

    # DOC7 confirm — explicit fabricated-demo attestation
    confirm = client.post(
        f"/v1/me/documents/{document_id}/confirm",
        headers=_auth(token, f"cf-{uuid.uuid4()}"),
        json={
            "contract_version": "v1", "extraction_id": extraction_id,
            "extraction_version": 1,
            "confirmed_inputs": {"age": 54, "sex": 1, "cp": 2, "trestbps": 130, "restecg": 0},
            "units": {"age": "years", "trestbps": "mmHg"},
            "missing_reasons": {},
            "confirm_fabricated_demo_inputs": True,
        },
    )
    assert confirm.status_code == 200, confirm.text
    body = confirm.json()
    assert body["is_confirmed"] is True
    assert body["event_type"] == C.EVENT_PATIENT_CONFIRMED
    assert body["confirmed_values_sha256"]

    # The confirmed extraction is now immutable and marked CONFIRMED_BY_PATIENT.
    read2 = client.get(f"/v1/me/documents/{document_id}/extraction", headers=_auth(token))
    assert read2.json()["extraction_status"] == C.STATUS_CONFIRMED
    assert read2.json()["is_confirmed"] is True


@requires_native_ocr
def test_upload_idempotent_replay_returns_same_document(client, patient):
    token = patient["token"]
    key = f"up-{uuid.uuid4()}"
    first = _upload(client, token, "resting_text.pdf", key=key)
    second = _upload(client, token, "resting_text.pdf", key=key)
    assert first.json()["document_id"] == second.json()["document_id"]
    # Only one document was actually stored.
    listing = client.get("/v1/me/documents", headers=_auth(token)).json()
    assert len(listing["items"]) == 1


@requires_native_ocr
def test_extract_idempotent_replay_same_version(client, patient):
    token = patient["token"]
    document_id = _upload(client, token, "resting_text.pdf").json()["document_id"]
    key = f"ex-{uuid.uuid4()}"
    first = client.post(f"/v1/me/documents/{document_id}/extract", headers=_auth(token, key))
    second = client.post(f"/v1/me/documents/{document_id}/extract", headers=_auth(token, key))
    assert first.json()["extraction_id"] == second.json()["extraction_id"]
    assert first.json()["extraction_version"] == second.json()["extraction_version"] == 1


@requires_native_ocr
def test_reextract_creates_new_immutable_version(client, patient):
    token = patient["token"]
    document_id = _upload(client, token, "resting_text.pdf").json()["document_id"]
    v1 = client.post(f"/v1/me/documents/{document_id}/extract",
                     headers=_auth(token, f"ex-{uuid.uuid4()}")).json()
    v2 = client.post(f"/v1/me/documents/{document_id}/extract",
                     headers=_auth(token, f"ex-{uuid.uuid4()}")).json()
    assert v1["extraction_version"] == 1
    assert v2["extraction_version"] == 2
    assert v1["extraction_id"] != v2["extraction_id"]


@requires_native_ocr
def test_edit_and_confirm_records_patient_provenance(client, patient):
    token = patient["token"]
    document_id = _upload(client, token, "resting_raster.pdf").json()["document_id"]
    extraction = client.post(f"/v1/me/documents/{document_id}/extract",
                             headers=_auth(token, f"ex-{uuid.uuid4()}")).json()
    # Patient corrects trestbps from the OCR draft value 130 to 128.
    confirm = client.post(
        f"/v1/me/documents/{document_id}/confirm",
        headers=_auth(token, f"cf-{uuid.uuid4()}"),
        json={
            "contract_version": "v1", "extraction_id": extraction["extraction_id"],
            "extraction_version": 1,
            "confirmed_inputs": {"age": 54, "sex": 1, "cp": 2, "trestbps": 128, "restecg": 0},
            "units": {"age": "years", "trestbps": "mmHg"},
            "missing_reasons": {}, "confirm_fabricated_demo_inputs": True,
        },
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["event_type"] == C.EVENT_EDITED_AND_CONFIRMED
    read = client.get(f"/v1/me/documents/{document_id}/extraction", headers=_auth(token)).json()
    fields = {f["field_name"]: f for f in read["fields"]}
    # Raw OCR value preserved separately from the corrected confirmed value.
    assert fields["trestbps"]["typed_value_json"] == 130
    assert fields["trestbps"]["confirmed_value_json"] == 128
    assert fields["trestbps"]["provenance_kind"] == C.PROV_PATIENT_FROM_DRAFT
    # Unedited fields keep OCR-confirmed provenance.
    assert fields["age"]["provenance_kind"] == C.PROV_OCR_CONFIRMED


@requires_native_ocr
def test_confirm_without_attestation_refused(client, patient):
    token = patient["token"]
    document_id = _upload(client, token, "resting_text.pdf").json()["document_id"]
    extraction = client.post(f"/v1/me/documents/{document_id}/extract",
                             headers=_auth(token, f"ex-{uuid.uuid4()}")).json()
    confirm = client.post(
        f"/v1/me/documents/{document_id}/confirm",
        headers=_auth(token, f"cf-{uuid.uuid4()}"),
        json={
            "contract_version": "v1", "extraction_id": extraction["extraction_id"],
            "extraction_version": 1,
            "confirmed_inputs": {"age": 54, "sex": 1, "cp": 2, "trestbps": 130, "restecg": 0},
            "units": {"age": "years", "trestbps": "mmHg"}, "missing_reasons": {},
            "confirm_fabricated_demo_inputs": False,
        },
    )
    assert confirm.status_code == 422
    assert confirm.json()["error"]["code"] == "validation_failed"


@requires_native_ocr
def test_labs_document_cannot_be_confirmed_as_intake(client, patient):
    token = patient["token"]
    up = _upload(client, token, "labs_text.pdf", kind=C.DOC_KIND_LABS,
                 template=C.TEMPLATE_LABS)
    document_id = up.json()["document_id"]
    extraction = client.post(f"/v1/me/documents/{document_id}/extract",
                             headers=_auth(token, f"ex-{uuid.uuid4()}")).json()
    assert extraction["extraction_status"] == C.STATUS_UNSUPPORTED_TEMPLATE
    confirm = client.post(
        f"/v1/me/documents/{document_id}/confirm",
        headers=_auth(token, f"cf-{uuid.uuid4()}"),
        json={
            "contract_version": "v1", "extraction_id": extraction["extraction_id"],
            "extraction_version": 1, "confirmed_inputs": {}, "units": {},
            "missing_reasons": {}, "confirm_fabricated_demo_inputs": True,
        },
    )
    assert confirm.status_code == 422
    assert confirm.json()["error"]["code"] == "unsupported_template_for_intake"


@requires_native_ocr
def test_double_confirm_conflicts(client, patient):
    token = patient["token"]
    document_id = _upload(client, token, "resting_text.pdf").json()["document_id"]
    extraction = client.post(f"/v1/me/documents/{document_id}/extract",
                             headers=_auth(token, f"ex-{uuid.uuid4()}")).json()
    payload = {
        "contract_version": "v1", "extraction_id": extraction["extraction_id"],
        "extraction_version": 1,
        "confirmed_inputs": {"age": 54, "sex": 1, "cp": 2, "trestbps": 130, "restecg": 0},
        "units": {"age": "years", "trestbps": "mmHg"}, "missing_reasons": {},
        "confirm_fabricated_demo_inputs": True,
    }
    first = client.post(f"/v1/me/documents/{document_id}/confirm",
                        headers=_auth(token, f"cf-{uuid.uuid4()}"), json=payload)
    assert first.status_code == 200
    second = client.post(f"/v1/me/documents/{document_id}/confirm",
                         headers=_auth(token, f"cf-{uuid.uuid4()}"), json=payload)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "extraction_already_confirmed"


@requires_native_ocr
def test_confirm_version_mismatch_conflicts(client, patient):
    token = patient["token"]
    document_id = _upload(client, token, "resting_text.pdf").json()["document_id"]
    extraction = client.post(f"/v1/me/documents/{document_id}/extract",
                             headers=_auth(token, f"ex-{uuid.uuid4()}")).json()
    confirm = client.post(
        f"/v1/me/documents/{document_id}/confirm",
        headers=_auth(token, f"cf-{uuid.uuid4()}"),
        json={
            "contract_version": "v1", "extraction_id": extraction["extraction_id"],
            "extraction_version": 99,
            "confirmed_inputs": {"age": 54, "sex": 1, "cp": 2, "trestbps": 130, "restecg": 0},
            "units": {"age": "years", "trestbps": "mmHg"}, "missing_reasons": {},
            "confirm_fabricated_demo_inputs": True,
        },
    )
    assert confirm.status_code == 409
    assert confirm.json()["error"]["code"] == "extraction_version_conflict"


def test_extraction_not_found_before_extract(client, patient):
    token = patient["token"]
    document_id = _upload(client, token, "resting_text.pdf").json()["document_id"]
    read = client.get(f"/v1/me/documents/{document_id}/extraction", headers=_auth(token))
    assert read.status_code == 404
    assert read.json()["error"]["code"] == "extraction_not_found"
