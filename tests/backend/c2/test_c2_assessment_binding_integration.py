"""Integrated S1 attachment binding: fabricated manual report, atomic snapshot."""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy import select

from backend.app.term1 import constants as core
from backend.app.term1.assessments import snapshot_digest
from backend.app.term1.models import Assessment, AssessmentSnapshot
from backend.app.term1.tx import read_transaction
from backend.app.term1_c2_documents import constants as documents
from backend.app.term1_c2_documents.models import AssessmentDocument
from tests.backend.c2_core.conftest import both

FIXTURES = (
    Path(__file__).resolve().parents[3]
    / "backend"
    / "app"
    / "term1_c2_documents"
    / "fixtures"
)
FULL_INPUTS = {"age": 54.0, "sex": 0, "cp": 1, "trestbps": 130.0, "restecg": 0}
FULL_UNITS = {"age": "years", "trestbps": "mmHg"}


def test_manual_s1_preallocates_and_atomically_persists_a_relevant_report_binding(
    client, patient, c2_app
):
    token = patient["token"]
    profile_response = client.patch(
        "/v1/me/health-profile",
        headers=both(token, f"profile-{uuid.uuid4()}"),
        json={
            "contract_version": "v1",
            "panel_id": core.PANEL_ID,
            "panel_version": core.PANEL_VERSION,
            "inputs": dict(FULL_INPUTS),
            "units": dict(FULL_UNITS),
            "missing_reasons": {},
        },
    )
    assert profile_response.status_code == 200, profile_response.text
    profile_id = profile_response.json()["health_profile_id"]

    assignment_response = client.get(
        "/v1/me/assignments", headers={"Authorization": f"Bearer {token}"}
    )
    assert assignment_response.status_code == 200, assignment_response.text
    assignment_id = assignment_response.json()["assignments"][0]["assignment_id"]

    report = (FIXTURES / "resting_text.pdf").read_bytes()
    upload = client.post(
        "/v1/me/documents",
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": f"upload-{uuid.uuid4()}",
        },
        data={
            "contract_version": "v1",
            "document_kind": documents.DOC_KIND_RESTING,
            "fixture_template_id": documents.TEMPLATE_RESTING,
        },
        files={"file": ("resting_text.pdf", report, "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["document_id"]
    assert upload.json()["status"] == documents.UPLOAD_STORED

    request_body = {
        "contract_version": "v1",
        "assignment_id": assignment_id,
        "health_profile_id": profile_id,
        "panel_id": core.PANEL_ID,
        "panel_version": core.PANEL_VERSION,
        "input_mode": core.INPUT_MODE_MANUAL,
        "panel_input": {
            "inputs": dict(FULL_INPUTS),
            "units": dict(FULL_UNITS),
            "missing_reasons": {},
        },
        "ocr_source": None,
        "attached_document_ids": [document_id],
        "reassessment_of_id": None,
        "reassessment_reason": None,
    }
    assessment_key = f"assessment-{uuid.uuid4()}"
    created = client.post(
        "/v1/assessments",
        headers=both(token, assessment_key),
        json=request_body,
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["source_kind"] == core.SOURCE_KIND_MANUAL
    assert body["status"] == core.ASSESSMENT_INFERENCE_UNAVAILABLE

    # The canonical snapshot and binding row share one preallocated immutable
    # identity and the exact verified digest/role fields.
    with read_transaction(c2_app.state.database) as session:
        assessment = session.get(Assessment, body["assessment_id"])
        snapshot = session.get(AssessmentSnapshot, body["snapshot_id"])
        bindings = session.execute(
            select(AssessmentDocument).where(
                AssessmentDocument.assessment_id == body["assessment_id"]
            )
        ).scalars().all()
        assert assessment is not None and snapshot is not None
        assert len(bindings) == 1
        descriptor = snapshot.snapshot_json["attached_documents"][0]
        binding = bindings[0]
        assert descriptor == {
            "binding_id": binding.binding_id,
            "document_id": binding.document_id,
            "attachment_role": binding.attachment_role,
            "extraction_id": binding.extraction_id,
            "extraction_version": binding.extraction_version,
            "document_sha256_at_bind": binding.document_sha256_at_bind,
            "extraction_confirmed_at": None,
            "confirmed_values_sha256": None,
        }
        assert binding.document_id == document_id
        assert binding.attachment_role == documents.ROLE_SUPPORTING
        assert binding.extraction_id is None and binding.extraction_version is None
        assert binding.document_sha256_at_bind == upload.json()["content_sha256"]
        assert snapshot.snapshot_json["source_kind"] == core.SOURCE_KIND_MANUAL
        assert snapshot.snapshot_sha256 == snapshot_digest(snapshot.snapshot_json)

    # The same descriptor is verified on the score-free doctor projection.
    doctor_token = patient["chain"]["doctor"]["token"]
    detail = client.get(
        f"/v1/assessments/{body['assessment_id']}",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert detail.status_code == 200, detail.text
    projection = detail.json()
    assert projection["source_kind"] == core.SOURCE_KIND_MANUAL
    assert projection["attached_documents"] == [descriptor]
    assert projection["research_output"] is None

    # A replay returns the original status-only result and does not duplicate
    # either the assessment or its binding row.
    replay = client.post(
        "/v1/assessments", headers=both(token, assessment_key), json=request_body
    )
    assert replay.status_code == 201
    replay_body = replay.json()
    assert replay_body.pop("idempotent_replay") is True
    assert replay_body == body
    with read_transaction(c2_app.state.database) as session:
        assert len(session.execute(
            select(AssessmentDocument).where(
                AssessmentDocument.assessment_id == body["assessment_id"]
            )
        ).scalars().all()) == 1
