"""Admission gates, ownership/authorization, consent and integrity security."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from backend.app.term1_c2_documents import constants as C
from backend.app.term1_c2_documents.admission import AdmissionError, validate_structure

FIXTURES = Path(__file__).resolve().parents[3] / "backend" / "app" / "term1_c2_documents" / "fixtures"


def _fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _auth(token, key=None):
    headers = {"Authorization": f"Bearer {token}"}
    if key:
        headers["Idempotency-Key"] = key
    return headers


def _upload_raw(client, token, data, *, filename="doc.pdf", kind=C.DOC_KIND_RESTING,
                template=C.TEMPLATE_RESTING, key=None):
    return client.post(
        "/v1/me/documents",
        headers=_auth(token, key or f"up-{uuid.uuid4()}"),
        data={"contract_version": "v1", "document_kind": kind,
              "fixture_template_id": template},
        files={"file": (filename, data, "application/octet-stream")},
    )


def _upload(client, token, name, **kw):
    return _upload_raw(client, token, _fixture(name), filename=name, **kw)


# --- size / media / allowlist gates -----------------------------------------
def test_oversized_raw_multipart_body_rejected(client, patient):
    # > 6 MiB raw body cap, enforced before multipart parsing.
    blob = b"%PDF-1.4\n" + b"A" * (C.RAW_MULTIPART_CAP_BYTES + 1024)
    response = _upload_raw(client, patient["token"], blob)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


def test_oversized_file_part_rejected(client, patient):
    # File > 5 MiB but raw body < 6 MiB: the per-file cap rejects it.
    blob = b"%PDF-1.4\n" + b"A" * (C.FILE_CAP_BYTES + 1024)
    response = _upload_raw(client, patient["token"], blob)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


def test_unsupported_media_type_rejected(client, patient):
    gif = b"GIF89a" + b"\x00" * 64
    response = _upload_raw(client, patient["token"], gif, filename="x.gif")
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_media_type"


def test_unlisted_sha_rejected_even_with_valid_magic(client, patient):
    # A byte-modified fixture is a valid PDF but not on the exact allowlist.
    data = bytearray(_fixture("resting_text.pdf"))
    data[-1] ^= 0xFF
    response = _upload_raw(client, patient["token"], bytes(data))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_document_content"


def test_forged_watermark_does_not_admit_unlisted_file(client, patient):
    # Watermark text alone never admits a file: only the exact SHA allowlist does.
    forged = (b"%PDF-1.4\n% " + C.DEMO_WATERMARK.encode() + b"\n"
              b"Template ID: CAI-DEMO-RESTING-CARDIAC-REPORT-V1\n%%EOF\n")
    response = _upload_raw(client, patient["token"], forged)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_document_content"


def test_declared_template_mismatch_rejected(client, patient):
    # Correct resting bytes but a declared labs template must be refused.
    response = _upload_raw(client, patient["token"], _fixture("resting_text.pdf"),
                           kind=C.DOC_KIND_LABS, template=C.TEMPLATE_LABS)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_document_content"


def _active_pdf() -> bytes:
    """A well-formed PDF whose catalog carries /OpenAction /JavaScript."""
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R /OpenAction << /S /JavaScript /JS (app.alert(1)) >> >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    stream = b"BT /F1 12 Tf 72 720 Td (Demo) Tj ET"
    objs.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objs) + 1}\n".encode() + b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_pos}\n%%EOF\n").encode()
    return bytes(out)


def test_active_pdf_content_rejected_by_worker_gate():
    # Defence-in-depth: even if a PDF passed admission, the worker's semantic
    # object-graph inspection refuses active/scripted catalog content.
    with pytest.raises(AdmissionError) as exc:
        validate_structure(_active_pdf(), C.MEDIA_PDF)
    assert exc.value.code == "active_pdf_content_rejected"


def test_missing_idempotency_key_on_upload(client, patient):
    response = client.post(
        "/v1/me/documents",
        headers={"Authorization": f"Bearer {patient['token']}"},
        data={"contract_version": "v1", "document_kind": C.DOC_KIND_RESTING,
              "fixture_template_id": C.TEMPLATE_RESTING},
        files={"file": ("resting_text.pdf", _fixture("resting_text.pdf"), "application/pdf")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "idempotency_key_required"


def test_duplicate_form_field_rejected(client, patient):
    # Two contract_version fields: ambiguous multipart cardinality is refused.
    token = patient["token"]
    boundary = "----dupboundary"
    parts = []
    for name, value in [("contract_version", "v1"), ("contract_version", "v1"),
                        ("document_kind", C.DOC_KIND_RESTING),
                        ("fixture_template_id", C.TEMPLATE_RESTING)]:
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n")
    body = "".join(parts).encode() + (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"r.pdf\"\r\n"
        f"Content-Type: application/pdf\r\n\r\n").encode() + _fixture("resting_text.pdf") + (
        f"\r\n--{boundary}--\r\n").encode()
    response = client.post(
        "/v1/me/documents",
        headers={**_auth(token, f"up-{uuid.uuid4()}"),
                 "Content-Type": f"multipart/form-data; boundary={boundary}"},
        content=body,
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "malformed_request"


# --- ownership / role / consent ---------------------------------------------
def test_wrong_patient_cannot_read_another_patients_document(client, patient):
    document_id = _upload(client, patient["token"], "resting_text.pdf").json()["document_id"]
    # Provision a second, distinct patient.
    chain = patient["chain"]
    _, invitation = chain["fresh_visit"](seq=1, target_identifier="DEMO-ID-002")
    from tests.backend.c1.factories import register_patient
    other = register_patient(client, invitation["access_code"],
                             identifier="DEMO-ID-002",
                             email="other.patient@cardioassist.local")
    other_token = other["session_token"]
    for path in (f"/v1/me/documents/{document_id}",
                 f"/v1/me/documents/{document_id}/content",
                 f"/v1/me/documents/{document_id}/extraction"):
        response = client.get(path, headers=_auth(other_token))
        assert response.status_code == 404, path
        assert response.json()["error"]["code"] in ("document_not_found", "extraction_not_found")
    # The second patient's list never includes the first patient's document.
    listing = client.get("/v1/me/documents", headers=_auth(other_token)).json()
    assert all(item["document_id"] != document_id for item in listing["items"])


def test_doctor_and_admin_are_refused_document_content(client, patient, c2_app):
    document_id = _upload(client, patient["token"], "resting_text.pdf").json()["document_id"]
    doctor_token = patient["doctor"]["token"]
    response = client.get("/v1/me/documents", headers=_auth(doctor_token))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    # Admin bootstrap + login.
    from tests.backend.c1.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, bootstrap_admin, login
    bootstrap_admin(c2_app)
    admin_token = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)["session_token"]
    response = client.get(f"/v1/me/documents/{document_id}", headers=_auth(admin_token))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "admin_clinical_content_forbidden"


def test_consent_withdrawal_blocks_upload_extract_confirm(client, patient):
    token = patient["token"]
    document_id = _upload(client, token, "resting_text.pdf").json()["document_id"]
    extraction = client.post(f"/v1/me/documents/{document_id}/extract",
                             headers=_auth(token, f"ex-{uuid.uuid4()}")).json()
    # Withdraw consent through the real C1 endpoint.
    revoke = client.post("/v1/me/consent/synthetic-demo/revoke",
                         headers=_auth(token, f"rv-{uuid.uuid4()}"),
                         json={"contract_version": "v1", "reason_code": "patient_withdrew"})
    assert revoke.status_code == 200, revoke.text
    # New upload refused.
    up = _upload(client, token, "resting_text.pdf")
    assert up.status_code == 403
    assert up.json()["error"]["code"] == "consent_required"
    # Extraction refused.
    ex = client.post(f"/v1/me/documents/{document_id}/extract",
                     headers=_auth(token, f"ex-{uuid.uuid4()}"))
    assert ex.status_code == 403
    assert ex.json()["error"]["code"] == "consent_required"
    # Confirmation refused.
    cf = client.post(f"/v1/me/documents/{document_id}/confirm",
                     headers=_auth(token, f"cf-{uuid.uuid4()}"),
                     json={"contract_version": "v1",
                           "extraction_id": extraction["extraction_id"],
                           "extraction_version": 1,
                           "confirmed_inputs": {"age": 54, "sex": 1, "cp": 2,
                                                "trestbps": 130, "restecg": 0},
                           "units": {"age": "years", "trestbps": "mmHg"},
                           "missing_reasons": {}, "confirm_fabricated_demo_inputs": True})
    assert cf.status_code == 403
    assert cf.json()["error"]["code"] == "consent_required"


def test_tampered_stored_file_refused_before_publication(client, patient, doc_store):
    token = patient["token"]
    doc = _upload(client, token, "resting_text.pdf").json()
    document_id = doc["document_id"]
    # Tamper the private blob on disk AFTER promotion (same length, different byte).
    storage_key = f"{patient['patient_id']}/{document_id}.bin"
    blob = bytearray(doc_store.read_verified(storage_key,
                                             expected_sha256=doc["content_sha256"],
                                             expected_size=doc["byte_size"]))
    blob[100] ^= 0xFF
    target = doc_store.root / storage_key
    target.write_bytes(bytes(blob))
    # DOC4 must verify the complete buffer BEFORE sending headers/body.
    response = client.get(f"/v1/me/documents/{document_id}/content", headers=_auth(token))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "document_integrity_mismatch"
    assert response.content == b"" or response.json()["error"]["code"] == "document_integrity_mismatch"


def test_unauthenticated_requests_refused(client):
    response = client.get("/v1/me/documents")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"
