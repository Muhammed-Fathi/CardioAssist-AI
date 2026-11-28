"""T2-R2 regressions: immutable confirmed extraction integrity.

Direct-SQL negative tests prove the database itself protects confirmed child
fields (INSERT/UPDATE/DELETE), binds children to the SAME document, freezes
STORED document digest/status/pixels, and that the canonical confirmation digest
is reconstructible from persisted rows and verified on reads/binding even if a
trigger is absent (defense in depth).
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from backend.app.term1.models import PatientProfile
from backend.app.term1.tx import read_transaction, write_transaction
from backend.app.term1_c2_documents import constants as C
from backend.app.term1_c2_documents.models import ExtractionField, MedicalDocument
from backend.app.term1_c2_documents.service import Actor, confirmation_envelope, _sha256_text

FIXTURES = Path(__file__).resolve().parents[3] / "backend" / "app" / "term1_c2_documents" / "fixtures"
CONFIRM_INPUTS = {"age": 54, "sex": 1, "cp": 2, "trestbps": 130, "restecg": 0}


@pytest.fixture
def actor_patient(client, patient, c2_app):
    with read_transaction(c2_app.state.database) as session:
        user_id = session.execute(
            select(PatientProfile.user_id).where(
                PatientProfile.patient_id == patient["patient_id"])
        ).scalar_one()
    return Actor(user_id=user_id, role="patient", patient_id=patient["patient_id"])


def _upload(service, actor):
    return service.upload(
        actor=actor, data=(FIXTURES / "resting_text.pdf").read_bytes(),
        declared_template_id=C.TEMPLATE_RESTING, declared_document_kind=C.DOC_KIND_RESTING,
        original_filename="resting_text.pdf", idempotency_key=f"up-{uuid.uuid4()}",
    )


def _extract(service, actor, document_id):
    return service.extract(actor=actor, document_id=document_id,
                           idempotency_key=f"ex-{uuid.uuid4()}")


def _confirm(service, actor, document_id, extraction_id):
    return service.confirm(
        actor=actor, document_id=document_id, extraction_id=extraction_id, extraction_version=1,
        confirmed_inputs=CONFIRM_INPUTS, units={"age": "years", "trestbps": "mmHg"},
        missing_reasons={}, confirm_fabricated_demo_inputs=True,
        idempotency_key=f"cf-{uuid.uuid4()}",
    )


def _confirmed(service, actor):
    doc = _upload(service, actor)
    ext = _extract(service, actor, doc["document_id"])
    _confirm(service, actor, doc["document_id"], ext["extraction_id"])
    return doc["document_id"], ext["extraction_id"]


def test_confirmed_child_field_update_refused(document_service, actor_patient):
    _, extraction_id = _confirmed(document_service, actor_patient)
    with pytest.raises(IntegrityError):
        with write_transaction(document_service.database) as session:
            session.execute(text(
                "UPDATE extraction_field SET confirmed_value_json='999' "
                "WHERE extraction_id=:e AND field_name='age'"), {"e": extraction_id})


def test_confirmed_child_field_delete_refused(document_service, actor_patient):
    _, extraction_id = _confirmed(document_service, actor_patient)
    with pytest.raises(IntegrityError):
        with write_transaction(document_service.database) as session:
            session.execute(text(
                "DELETE FROM extraction_field WHERE extraction_id=:e"), {"e": extraction_id})


def test_child_insert_under_confirmed_parent_refused(document_service, actor_patient):
    document_id, extraction_id = _confirmed(document_service, actor_patient)
    with pytest.raises(IntegrityError):
        with write_transaction(document_service.database) as session:
            session.execute(text(
                "INSERT INTO extraction_field (field_record_id, extraction_id, document_id, "
                "field_name, page_number, parse_status, conflict_flag, field_provenance) "
                "VALUES (:r, :e, :d, 'smoking', 1, 'PARSED', 0, 'OCR_EXTRACTED_UNCONFIRMED')"),
                {"r": str(uuid.uuid4()), "e": extraction_id, "d": document_id})


def test_draft_child_evidence_columns_immutable(document_service, actor_patient):
    doc = _upload(document_service, actor_patient)
    ext = _extract(document_service, actor_patient, doc["document_id"])
    with pytest.raises(IntegrityError):
        with write_transaction(document_service.database) as session:
            session.execute(text(
                "UPDATE extraction_field SET parsed_value_json='1' "
                "WHERE extraction_id=:e AND field_name='age'"), {"e": ext["extraction_id"]})


def test_wrong_document_child_insert_refused(document_service, actor_patient):
    doc_a = _upload(document_service, actor_patient)
    ext_a = _extract(document_service, actor_patient, doc_a["document_id"])
    doc_b = _upload(document_service, actor_patient)
    # A child referencing extraction A but document B violates the composite FK.
    with pytest.raises(IntegrityError):
        with write_transaction(document_service.database) as session:
            session.execute(text(
                "INSERT INTO extraction_field (field_record_id, extraction_id, document_id, "
                "field_name, page_number, parse_status, conflict_flag, field_provenance) "
                "VALUES (:r, :e, :d, 'age', 1, 'PARSED', 0, 'OCR_EXTRACTED_UNCONFIRMED')"),
                {"r": str(uuid.uuid4()), "e": ext_a["extraction_id"], "d": doc_b["document_id"]})


def test_confirmation_digest_reconstructible_from_persisted_children(document_service, actor_patient):
    document_id, extraction_id = _confirmed(document_service, actor_patient)
    with read_transaction(document_service.database) as session:
        fields = session.execute(
            select(ExtractionField).where(ExtractionField.extraction_id == extraction_id)
        ).scalars().all()
        envelope = confirmation_envelope(fields)
        digest = _sha256_text(envelope)
        stored = session.execute(text(
            "SELECT confirmed_values_sha256, confirmed_envelope_json FROM document_extraction "
            "WHERE extraction_id=:e"), {"e": extraction_id}).one()
        assert digest == stored[0]
        # Complete five-field set persisted (no missing row skipped).
        assert set(envelope["confirmed_inputs"]) == set(C.PANEL_FIELD_ORDER)
        assert envelope["units"]["trestbps"] == "mmHg"
        assert envelope["units"]["age"] == "years"


def test_read_verifies_digest_even_without_trigger(document_service, actor_patient):
    document_id, extraction_id = _confirmed(document_service, actor_patient)
    # Defense in depth: simulate a restored DB missing the child guard trigger,
    # tamper a confirmed child, and prove the READ still rejects via the digest.
    with write_transaction(document_service.database) as session:
        session.execute(text("DROP TRIGGER tr_extraction_field_update_guard"))
        session.execute(text(
            "UPDATE extraction_field SET confirmed_value_json='999' "
            "WHERE extraction_id=:e AND field_name='age'"), {"e": extraction_id})
    with pytest.raises(Exception) as exc:
        document_service.read_extraction(actor=actor_patient, document_id=document_id)
    assert getattr(exc.value, "code", None) == "document_integrity_mismatch"


def test_stored_document_digest_status_pixels_frozen(document_service, actor_patient):
    doc = _upload(document_service, actor_patient)
    zero_sha = "'" + "0" * 64 + "'"
    for column, value in (("content_sha256", zero_sha), ("upload_status", "'SUPERSEDED'"),
                          ("page_count", "9"), ("pixel_width", "10")):
        with pytest.raises(IntegrityError):
            with write_transaction(document_service.database) as session:
                session.execute(text(
                    f"UPDATE medical_document SET {column}={value} WHERE document_id=:d"),
                    {"d": doc["document_id"]})


def test_promotion_without_digest_or_validation_refused(document_service, actor_patient):
    # A fresh PENDING_SCAN row cannot be flipped to STORED without the verified
    # digest and validation evidence (trigger guard), so recovery cannot publish
    # an unvalidated reservation.
    import hashlib
    data = (FIXTURES / "resting_text.pdf").read_bytes()
    document_id = str(uuid.uuid4())
    from backend.app.term1_c2_documents.storage import make_storage_key
    storage_key = make_storage_key(actor_patient.patient_id, document_id)
    with write_transaction(document_service.database) as session:
        session.add(MedicalDocument(
            document_id=document_id, patient_id=actor_patient.patient_id,
            uploaded_by_user_id=actor_patient.user_id, document_kind=C.DOC_KIND_RESTING,
            fixture_template_id=C.TEMPLATE_RESTING,
            fixture_file_sha256=hashlib.sha256(data).hexdigest(),
            original_filename_sanitized="resting_text.pdf", declared_media_type=C.MEDIA_PDF,
            byte_size=len(data), page_count=0, content_sha256=None,
            storage_key=storage_key, upload_status=C.UPLOAD_PENDING_SCAN,
            created_at=document_service.clock.now_iso(),
        ))
    with pytest.raises(IntegrityError):
        with write_transaction(document_service.database) as session:
            session.execute(text(
                "UPDATE medical_document SET upload_status='STORED' WHERE document_id=:d"),
                {"d": document_id})


def test_binding_requires_confirmed_extraction_and_verified_bytes(document_service, actor_patient):
    doc = _upload(document_service, actor_patient)
    ext = _extract(document_service, actor_patient, doc["document_id"])
    # Unconfirmed extraction cannot be an OCR source binding.
    with write_transaction(document_service.database) as session:
        with pytest.raises(Exception) as exc:
            document_service.bind_assessment_document(
                session, assessment_id=str(uuid.uuid4()), patient_id=actor_patient.patient_id,
                document_id=doc["document_id"], attachment_role=C.ROLE_OCR_SOURCE,
                extraction_id=ext["extraction_id"], extraction_version=1)
        assert getattr(exc.value, "code", None) == "document_not_confirmed"
    # Confirm, then tamper the stored bytes: binding must reject on verified read.
    _confirm(document_service, actor_patient, doc["document_id"], ext["extraction_id"])
    with read_transaction(document_service.database) as session:
        storage_key = session.get(MedicalDocument, doc["document_id"]).storage_key
    final = document_service.store.root / storage_key
    final.write_bytes(b"X" * final.stat().st_size)
    with write_transaction(document_service.database) as session:
        with pytest.raises(Exception) as exc:
            document_service.bind_assessment_document(
                session, assessment_id=str(uuid.uuid4()), patient_id=actor_patient.patient_id,
                document_id=doc["document_id"], attachment_role=C.ROLE_OCR_SOURCE,
                extraction_id=ext["extraction_id"], extraction_version=1)
        assert getattr(exc.value, "code", None) == "document_integrity_mismatch"
