"""Integrated S1 attachment binding: fabricated manual report, atomic snapshot."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError as SqlIntegrityError

from backend.app.term1 import assessments, constants as core
from backend.app.term1.assessments import snapshot_digest
from backend.app.term1.models import Assessment, AssessmentSnapshot, InferenceAttempt
from backend.app.term1.tx import read_transaction, write_transaction
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


def _manual_submission(client, patient):
    """Build one verified stored-report submission for direct trigger probes."""
    token = patient["token"]
    profile_response = client.patch(
        "/v1/me/health-profile",
        headers=both(token, f"profile-{uuid.uuid4()}"),
        json={
            "contract_version": "v1", "panel_id": core.PANEL_ID,
            "panel_version": core.PANEL_VERSION, "inputs": dict(FULL_INPUTS),
            "units": dict(FULL_UNITS), "missing_reasons": {},
        },
    )
    assert profile_response.status_code == 200, profile_response.text
    assignment_response = client.get(
        "/v1/me/assignments", headers={"Authorization": f"Bearer {token}"}
    )
    assert assignment_response.status_code == 200, assignment_response.text
    report = (FIXTURES / "resting_text.pdf").read_bytes()
    upload = client.post(
        "/v1/me/documents",
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": f"upload-{uuid.uuid4()}",
        },
        data={
            "contract_version": "v1", "document_kind": documents.DOC_KIND_RESTING,
            "fixture_template_id": documents.TEMPLATE_RESTING,
        },
        files={"file": ("resting_text.pdf", report, "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    body = {
        "contract_version": "v1",
        "assignment_id": assignment_response.json()["assignments"][0]["assignment_id"],
        "health_profile_id": profile_response.json()["health_profile_id"],
        "panel_id": core.PANEL_ID, "panel_version": core.PANEL_VERSION,
        "input_mode": core.INPUT_MODE_MANUAL,
        "panel_input": {
            "inputs": dict(FULL_INPUTS), "units": dict(FULL_UNITS),
            "missing_reasons": {},
        },
        "ocr_source": None, "attached_document_ids": [upload.json()["document_id"]],
        "reassessment_of_id": None, "reassessment_reason": None,
    }
    return token, body, upload.json()["document_id"]


def _assert_assessment_transaction_rolled_back(c2_app) -> None:
    with read_transaction(c2_app.state.database) as session:
        for model in (Assessment, AssessmentSnapshot, AssessmentDocument, InferenceAttempt):
            assert session.execute(select(func.count()).select_from(model)).scalar_one() == 0


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


@pytest.mark.parametrize(
    "mutation",
    ["binding_id", "document_id", "digest", "role", "extraction"],
)
def test_database_binding_insert_guard_rejects_descriptor_mismatch_and_rolls_back(
    client, patient, c2_app, monkeypatch, mutation
):
    token, request_body, _document_id = _manual_submission(client, patient)
    service = c2_app.state.doc.service()
    trigger_hits = []

    def insert_mismatch(session, *, assessment_id, patient_id, descriptor):
        values = {
            "binding_id": descriptor["binding_id"],
            "assessment_id": assessment_id,
            "patient_id": patient_id,
            "document_id": descriptor["document_id"],
            "extraction_id": descriptor["extraction_id"],
            "extraction_version": descriptor["extraction_version"],
            "document_sha256_at_bind": descriptor["document_sha256_at_bind"],
            "attachment_role": descriptor["attachment_role"],
            "created_at": "2026-11-28T09:00:00Z",
        }
        if mutation == "binding_id":
            values["binding_id"] = str(uuid.uuid4())
        elif mutation == "document_id":
            values["document_id"] = str(uuid.uuid4())
        elif mutation == "digest":
            values["document_sha256_at_bind"] = "0" * 64
        elif mutation == "role":
            values["attachment_role"] = documents.ROLE_UNRELATED_LAB
        elif mutation == "extraction":
            values["extraction_id"] = str(uuid.uuid4())
            values["extraction_version"] = 1
        session.add(AssessmentDocument(**values))
        try:
            session.flush()
        except SqlIntegrityError as error:
            if "assessment_document_insert_forbidden" in str(error.orig):
                trigger_hits.append(mutation)
            raise

    monkeypatch.setattr(service, "persist_assessment_document_binding", insert_mismatch)
    response = client.post(
        "/v1/assessments", headers=both(token, f"bad-{mutation}-{uuid.uuid4()}"),
        json=request_body,
    )
    assert response.status_code == 500, response.text
    assert trigger_hits == [mutation]  # the INSERT trigger, not application validation, refused it
    _assert_assessment_transaction_rolled_back(c2_app)


def test_database_rejects_an_extra_binding_before_attempt_and_rolls_back(
    client, patient, c2_app, monkeypatch
):
    token, request_body, _document_id = _manual_submission(client, patient)
    service = c2_app.state.doc.service()
    original_persist = service.persist_assessment_document_binding
    trigger_hits = []

    def insert_extra(session, *, assessment_id, patient_id, descriptor):
        original_persist(
            session, assessment_id=assessment_id, patient_id=patient_id,
            descriptor=descriptor,
        )
        session.flush()  # the valid two-phase binding is accepted first
        session.add(AssessmentDocument(
            binding_id=str(uuid.uuid4()), assessment_id=assessment_id,
            patient_id=patient_id, document_id=descriptor["document_id"],
            extraction_id=None, extraction_version=None,
            document_sha256_at_bind=descriptor["document_sha256_at_bind"],
            attachment_role=descriptor["attachment_role"],
            created_at="2026-11-28T09:00:00Z",
        ))
        try:
            session.flush()
        except SqlIntegrityError as error:
            if "assessment_document_insert_forbidden" in str(error.orig):
                trigger_hits.append("extra")
            raise

    monkeypatch.setattr(service, "persist_assessment_document_binding", insert_extra)
    response = client.post(
        "/v1/assessments", headers=both(token, f"extra-{uuid.uuid4()}"),
        json=request_body,
    )
    assert response.status_code == 500, response.text
    assert trigger_hits == ["extra"]
    _assert_assessment_transaction_rolled_back(c2_app)


def test_missing_binding_prevents_attempt_initiation_atomically(
    client, patient, c2_app, monkeypatch
):
    token, request_body, _document_id = _manual_submission(client, patient)
    service = c2_app.state.doc.service()
    monkeypatch.setattr(
        service, "persist_assessment_document_binding",
        lambda *_args, **_kwargs: None,
    )
    # Bypass the application-side completeness check to prove the DB attempt
    # trigger independently refuses initiation with a missing descriptor row.
    monkeypatch.setattr(
        assessments, "_verify_snapshot_integrity",
        lambda session, assessment: session.get(AssessmentSnapshot, assessment.snapshot_id),
    )
    original_begin = assessments.inference_lifecycle.begin_attempt
    trigger_hits = []

    def observe_attempt_insert(*args, **kwargs):
        try:
            return original_begin(*args, **kwargs)
        except SqlIntegrityError as error:
            if "inference_attempt_insert_forbidden" in str(error.orig):
                trigger_hits.append("missing")
            raise

    monkeypatch.setattr(
        assessments.inference_lifecycle, "begin_attempt", observe_attempt_insert
    )
    response = client.post(
        "/v1/assessments", headers=both(token, f"missing-{uuid.uuid4()}"),
        json=request_body,
    )
    assert response.status_code == 500, response.text
    assert trigger_hits == ["missing"]
    _assert_assessment_transaction_rolled_back(c2_app)


def test_late_binding_insert_is_rejected_after_attempt_initiation(client, patient, c2_app):
    token, request_body, _document_id = _manual_submission(client, patient)
    response = client.post(
        "/v1/assessments", headers=both(token, f"late-{uuid.uuid4()}"),
        json=request_body,
    )
    assert response.status_code == 201, response.text
    assessment_id = response.json()["assessment_id"]
    with read_transaction(c2_app.state.database) as session:
        assessment = session.get(Assessment, assessment_id)
        snapshot = session.get(AssessmentSnapshot, assessment.snapshot_id)
        descriptor = snapshot.snapshot_json["attached_documents"][0]
        existing = session.execute(
            select(AssessmentDocument).where(
                AssessmentDocument.assessment_id == assessment_id
            )
        ).scalar_one()
        values = {
            "binding_id": str(uuid.uuid4()), "assessment_id": assessment_id,
            "patient_id": existing.patient_id, "document_id": descriptor["document_id"],
            "extraction_id": descriptor["extraction_id"],
            "extraction_version": descriptor["extraction_version"],
            "document_sha256_at_bind": descriptor["document_sha256_at_bind"],
            "attachment_role": descriptor["attachment_role"],
            "created_at": "2026-11-28T09:00:00Z",
        }
    with pytest.raises(SqlIntegrityError, match="assessment_document_insert_forbidden"):
        with write_transaction(c2_app.state.database) as session:
            session.add(AssessmentDocument(**values))
            session.flush()
    with read_transaction(c2_app.state.database) as session:
        assert session.execute(
            select(func.count(AssessmentDocument.binding_id)).where(
                AssessmentDocument.assessment_id == assessment_id
            )
        ).scalar_one() == 1
