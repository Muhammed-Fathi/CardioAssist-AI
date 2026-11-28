"""Strict typed confirmation: units, categories, missingness, prohibited fields."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from backend.app.term1_c2_documents import constants as C

FIXTURES = Path(__file__).resolve().parents[3] / "backend" / "app" / "term1_c2_documents" / "fixtures"


def _auth(token, key=None):
    headers = {"Authorization": f"Bearer {token}"}
    if key:
        headers["Idempotency-Key"] = key
    return headers


def _prepare(client, token):
    data = (FIXTURES / "resting_text.pdf").read_bytes()
    up = client.post(
        "/v1/me/documents", headers=_auth(token, f"up-{uuid.uuid4()}"),
        data={"contract_version": "v1", "document_kind": C.DOC_KIND_RESTING,
              "fixture_template_id": C.TEMPLATE_RESTING},
        files={"file": ("resting_text.pdf", data, "application/pdf")},
    )
    assert up.status_code == 201, up.text
    document_id = up.json()["document_id"]
    ext = client.post(f"/v1/me/documents/{document_id}/extract",
                      headers=_auth(token, f"ex-{uuid.uuid4()}"))
    assert ext.status_code == 200, ext.text
    return document_id, ext.json()["extraction_id"]


def _confirm(client, token, document_id, extraction_id, *, inputs, units=None,
             reasons=None, version=1):
    return client.post(
        f"/v1/me/documents/{document_id}/confirm",
        headers=_auth(token, f"cf-{uuid.uuid4()}"),
        json={"contract_version": "v1", "extraction_id": extraction_id,
              "extraction_version": version, "confirmed_inputs": inputs,
              "units": units or {}, "missing_reasons": reasons or {},
              "confirm_fabricated_demo_inputs": True},
    )


BASE_INPUTS = {"age": 54, "sex": 1, "cp": 2, "trestbps": 130, "restecg": 0}
BASE_UNITS = {"age": "years", "trestbps": "mmHg"}


def test_wrong_unit_for_trestbps_refused(client, patient):
    document_id, extraction_id = _prepare(client, patient["token"])
    response = _confirm(client, patient["token"], document_id, extraction_id,
                        inputs=BASE_INPUTS, units={"age": "years", "trestbps": "kPa"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_panel_input"


def test_wrong_unit_for_age_refused(client, patient):
    document_id, extraction_id = _prepare(client, patient["token"])
    response = _confirm(client, patient["token"], document_id, extraction_id,
                        inputs=BASE_INPUTS, units={"age": "months", "trestbps": "mmHg"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_panel_input"


@pytest.mark.parametrize("field,bad", [("sex", 2), ("cp", 0), ("cp", 5), ("restecg", 3)])
def test_invalid_category_code_refused(client, patient, field, bad):
    document_id, extraction_id = _prepare(client, patient["token"])
    inputs = {**BASE_INPUTS, field: bad}
    response = _confirm(client, patient["token"], document_id, extraction_id,
                        inputs=inputs, units=BASE_UNITS)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_panel_input"


@pytest.mark.parametrize("field,bad", [("age", 0), ("age", -5), ("trestbps", -1)])
def test_non_positive_numeric_refused(client, patient, field, bad):
    document_id, extraction_id = _prepare(client, patient["token"])
    inputs = {**BASE_INPUTS, field: bad}
    response = _confirm(client, patient["token"], document_id, extraction_id,
                        inputs=inputs, units=BASE_UNITS)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_panel_input"


def test_mandatory_field_cannot_be_missing(client, patient):
    document_id, extraction_id = _prepare(client, patient["token"])
    inputs = {**BASE_INPUTS, "age": None}
    response = _confirm(client, patient["token"], document_id, extraction_id,
                        inputs=inputs, units=BASE_UNITS, reasons={"age": "not_measured"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_panel_input"


def test_optional_missing_requires_valid_reason(client, patient):
    document_id, extraction_id = _prepare(client, patient["token"])
    inputs = {**BASE_INPUTS, "restecg": None}
    # No reason supplied.
    response = _confirm(client, patient["token"], document_id, extraction_id,
                        inputs=inputs, units=BASE_UNITS)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "missing_reason_mismatch"
    # Invalid reason vocabulary.
    response = _confirm(client, patient["token"], document_id, extraction_id,
                        inputs=inputs, units=BASE_UNITS, reasons={"restecg": "because"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "missing_reason_mismatch"


def test_optional_missing_with_valid_reason_accepted(client, patient):
    document_id, extraction_id = _prepare(client, patient["token"])
    inputs = {**BASE_INPUTS, "restecg": None}
    response = _confirm(client, patient["token"], document_id, extraction_id,
                        inputs=inputs, units=BASE_UNITS,
                        reasons={"restecg": "not_available_at_time"})
    assert response.status_code == 200, response.text
    assert response.json()["is_confirmed"] is True


def test_trestbps_zero_is_unavailable_not_numeric(client, patient):
    document_id, extraction_id = _prepare(client, patient["token"])
    inputs = {**BASE_INPUTS, "trestbps": 0}
    # ED-DA-A2-01: measured 0 means unavailable and needs a reason.
    response = _confirm(client, patient["token"], document_id, extraction_id,
                        inputs=inputs, units=BASE_UNITS,
                        reasons={"trestbps": "not_measured"})
    assert response.status_code == 200, response.text
    read = client.get(f"/v1/me/documents/{document_id}/extraction",
                      headers=_auth(patient["token"])).json()
    fields = {f["field_name"]: f for f in read["fields"]}
    assert fields["trestbps"]["confirmed_value_json"] is None


def test_prohibited_clinical_field_refused(client, patient):
    document_id, extraction_id = _prepare(client, patient["token"])
    inputs = {**BASE_INPUTS, "chol": 200}  # laboratory leakage field
    response = _confirm(client, patient["token"], document_id, extraction_id,
                        inputs=inputs, units=BASE_UNITS)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "prohibited_clinical_field"


def test_boolean_value_refused(client, patient):
    document_id, extraction_id = _prepare(client, patient["token"])
    inputs = {**BASE_INPUTS, "sex": True}
    response = _confirm(client, patient["token"], document_id, extraction_id,
                        inputs=inputs, units=BASE_UNITS)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_panel_input"
