"""The eight migration-08 immutability triggers, exercised on real SQLite."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from backend.app.term1.models import PatientProfile
from backend.app.term1.tx import read_transaction, write_transaction
from backend.app.term1_c2_documents import constants as C
from backend.app.term1_c2_documents.models import ExtractionEvent, MedicalDocument
from backend.app.term1_c2_documents.service import Actor

FIXTURES = Path(__file__).resolve().parents[3] / "backend" / "app" / "term1_c2_documents" / "fixtures"


@pytest.fixture
def actor_patient(client, patient, c2_app):
    with read_transaction(c2_app.state.database) as session:
        user_id = session.execute(
            select(PatientProfile.user_id).where(
                PatientProfile.patient_id == patient["patient_id"])
        ).scalar_one()
    return Actor(user_id=user_id, role="patient", patient_id=patient["patient_id"])


def _upload_extract_confirm(service, actor):
    data = (FIXTURES / "resting_text.pdf").read_bytes()
    doc = service.upload(
        actor=actor, data=data, declared_template_id=C.TEMPLATE_RESTING,
        declared_document_kind=C.DOC_KIND_RESTING, original_filename="resting_text.pdf",
        idempotency_key=f"up-{uuid.uuid4()}",
    )
    extraction = service.extract(
        actor=actor, document_id=doc["document_id"], idempotency_key=f"ex-{uuid.uuid4()}")
    service.confirm(
        actor=actor, document_id=doc["document_id"],
        extraction_id=extraction["extraction_id"], extraction_version=1,
        confirmed_inputs={"age": 54, "sex": 1, "cp": 2, "trestbps": 130, "restecg": 0},
        units={"age": "years", "trestbps": "mmHg"}, missing_reasons={},
        confirm_fabricated_demo_inputs=True, idempotency_key=f"cf-{uuid.uuid4()}",
    )
    return doc["document_id"], extraction["extraction_id"]


def test_medical_document_identity_is_immutable(document_service, actor_patient):
    document_id, _ = _upload_extract_confirm(document_service, actor_patient)
    with pytest.raises(IntegrityError):
        with write_transaction(document_service.database) as session:
            session.execute(text(
                "UPDATE medical_document SET patient_id=:p WHERE document_id=:d"),
                {"p": str(uuid.uuid4()), "d": document_id})


def test_medical_document_cannot_be_deleted(document_service, actor_patient):
    document_id, _ = _upload_extract_confirm(document_service, actor_patient)
    with pytest.raises(IntegrityError):
        with write_transaction(document_service.database) as session:
            session.execute(text("DELETE FROM medical_document WHERE document_id=:d"),
                            {"d": document_id})


def test_confirmed_extraction_is_immutable(document_service, actor_patient):
    _, extraction_id = _upload_extract_confirm(document_service, actor_patient)
    with pytest.raises(IntegrityError):
        with write_transaction(document_service.database) as session:
            session.execute(text(
                "UPDATE document_extraction SET confirmed_values_sha256=:s "
                "WHERE extraction_id=:e"), {"s": "0" * 64, "e": extraction_id})


def test_extraction_cannot_be_deleted(document_service, actor_patient):
    _, extraction_id = _upload_extract_confirm(document_service, actor_patient)
    with pytest.raises(IntegrityError):
        with write_transaction(document_service.database) as session:
            session.execute(text("DELETE FROM document_extraction WHERE extraction_id=:e"),
                            {"e": extraction_id})


def test_extraction_event_cannot_be_updated_or_deleted(document_service, actor_patient):
    document_id, _ = _upload_extract_confirm(document_service, actor_patient)
    with read_transaction(document_service.database) as session:
        event_id = session.execute(
            select(ExtractionEvent.event_id).where(
                ExtractionEvent.document_id == document_id)
        ).scalars().first()
    with pytest.raises(IntegrityError):
        with write_transaction(document_service.database) as session:
            session.execute(text("UPDATE extraction_event SET event_type='X' WHERE event_id=:e"),
                            {"e": event_id})
    with pytest.raises(IntegrityError):
        with write_transaction(document_service.database) as session:
            session.execute(text("DELETE FROM extraction_event WHERE event_id=:e"),
                            {"e": event_id})


def test_lifecycle_status_transitions_remain_allowed(document_service, actor_patient):
    # The identity trigger must NOT block the legitimate status/digest columns.
    data = (FIXTURES / "resting_text.pdf").read_bytes()
    doc = document_service.upload(
        actor=actor_patient, data=data, declared_template_id=C.TEMPLATE_RESTING,
        declared_document_kind=C.DOC_KIND_RESTING, original_filename="resting_text.pdf",
        idempotency_key=f"up-{uuid.uuid4()}",
    )
    with write_transaction(document_service.database) as session:
        row = session.get(MedicalDocument, doc["document_id"])
        assert row.upload_status == C.UPLOAD_STORED
        assert row.content_sha256 is not None
        # A permitted lifecycle column update succeeds (no trigger abort).
        row.validated_at = document_service.clock.now_iso()
