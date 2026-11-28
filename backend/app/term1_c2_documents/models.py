"""Track 2 C2 document/ORM models (additive migration ``20261128_08``).

These five tables register on the same ``Base.metadata`` as the C1 models so
Alembic ``compare_metadata`` and startup verification cover them. Importing this
module is the model-registration side effect; the core integrator adds the
import to ``backend/migrations/env.py`` and the application wiring (Track 1 owns
shared registration). This module never edits C1 models.

Tables: ``medical_document``, ``document_extraction``, ``extraction_field``,
``extraction_event``, ``assessment_document``. The ``assessment_document``
composite foreign key targets Track 1's ``assessment`` table (migration ``07``);
its binding rows are written by ``S1`` (Track 1) via the supplied helper.

Additive recovery metadata (``staging_key``, ``reclaim_at``, ``validated_at``)
implements mandatory reviewer clarification #7229164710 item 3: the exact
expected digest and byte count are reserved durably before parsing, and crash
recovery has explicit staging / validation evidence rather than relying on a
nullable digest populated only at ``STORED`` or age alone.
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..storage.models import Base

_DOC_KIND_CHECK = (
    "document_kind IN ('RESTING_CARDIAC_DEMO_REPORT','UNRELATED_LAB_DEMO_REPORT')"
)
_UPLOAD_STATUS_CHECK = (
    "upload_status IN ('PENDING_SCAN','STORED','UPLOAD_FAILED','SUPERSEDED')"
)
_MEDIA_CHECK = "declared_media_type IN ('application/pdf','image/png','image/jpeg')"
_MODE_CHECK = "extraction_mode IN ('PDF_TEXT','RASTER_OCR','FAILED')"
_EXTRACTION_STATUS_CHECK = (
    "extraction_status IN ('EXTRACTED_DRAFT','NEEDS_MANUAL_REVIEW',"
    "'UNSUPPORTED_TEMPLATE','CONFIRMED_BY_PATIENT','FAILED')"
)
_PARSE_STATUS_CHECK = (
    "parse_status IN ('PARSED','LOW_CONFIDENCE','CONFLICT_REVIEW_REQUIRED',"
    "'INVALID_VALUE','MISSING','UNRELATED_IGNORED')"
)
_PROVENANCE_CHECK = (
    "field_provenance IN ('OCR_EXTRACTED_UNCONFIRMED','OCR_EXTRACTED_PATIENT_CONFIRMED',"
    "'PATIENT_ENTERED_FROM_OCR_DRAFT','UNRELATED_NON_MODEL_FIELD')"
)
_EVENT_TYPE_CHECK = (
    "event_type IN ('UPLOADED','EXTRACTED','EXTRACTION_FAILED','PATIENT_EDITED',"
    "'PATIENT_CONFIRMED','EDITED_AND_CONFIRMED','DOCTOR_ACKNOWLEDGED')"
)
_ATTACHMENT_ROLE_CHECK = (
    "attachment_role IN ('SUPPORTING_REPORT','OCR_SOURCE_REPORT','UNRELATED_LAB_ATTACHMENT')"
)


class MedicalDocument(Base):
    __tablename__ = "medical_document"
    __table_args__ = (
        UniqueConstraint("document_id", "patient_id", name="ux_medical_document_id_patient"),
        UniqueConstraint("storage_key", name="ux_medical_document_storage_key"),
        CheckConstraint(_DOC_KIND_CHECK, name="ck_medical_document_kind"),
        CheckConstraint(_UPLOAD_STATUS_CHECK, name="ck_medical_document_upload_status"),
        CheckConstraint(_MEDIA_CHECK, name="ck_medical_document_media_type"),
        CheckConstraint("byte_size >= 0 AND byte_size <= 5242880", name="ck_medical_document_byte_size"),
        CheckConstraint("page_count >= 0 AND page_count <= 3", name="ck_medical_document_page_count"),
    )

    document_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    patient_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("patient_profile.patient_id", ondelete="RESTRICT"), nullable=False
    )
    uploaded_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("user_account.user_id", ondelete="RESTRICT"), nullable=False
    )
    document_kind: Mapped[str] = mapped_column(String(48), nullable=False)
    fixture_template_id: Mapped[str] = mapped_column(String(64), nullable=False)
    fixture_file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    original_filename_sanitized: Mapped[str] = mapped_column(String(128), nullable=False)
    declared_media_type: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False)
    content_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    storage_key: Mapped[str] = mapped_column(String(160), nullable=False)
    upload_status: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    # Additive recovery metadata (clarification #3).
    staging_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reclaim_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    validated_at: Mapped[str | None] = mapped_column(String(32), nullable=True)


class DocumentExtraction(Base):
    __tablename__ = "document_extraction"
    __table_args__ = (
        UniqueConstraint("document_id", "extraction_version", name="ux_document_extraction_version"),
        UniqueConstraint(
            "extraction_id", "document_id", "extraction_version", name="ux_extraction_id_doc_ver"
        ),
        CheckConstraint("extraction_version >= 1", name="ck_document_extraction_version"),
        CheckConstraint(_MODE_CHECK, name="ck_document_extraction_mode"),
        CheckConstraint(_EXTRACTION_STATUS_CHECK, name="ck_document_extraction_status"),
        CheckConstraint(
            "extracted_text_bytes >= 0 AND extracted_text_bytes <= 1048576",
            name="ck_document_extraction_text_bytes",
        ),
        CheckConstraint(
            "(is_confirmed = 1 AND confirmed_values_sha256 IS NOT NULL "
            "AND confirmed_at IS NOT NULL AND extraction_status = 'CONFIRMED_BY_PATIENT') "
            "OR (is_confirmed = 0 AND confirmed_values_sha256 IS NULL "
            "AND confirmed_at IS NULL AND extraction_status != 'CONFIRMED_BY_PATIENT')",
            name="ck_document_extraction_confirmation",
        ),
    )

    extraction_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("medical_document.document_id", ondelete="RESTRICT"), nullable=False
    )
    extraction_version: Mapped[int] = mapped_column(Integer, nullable=False)
    document_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    extraction_mode: Mapped[str] = mapped_column(String(24), nullable=False)
    template_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    template_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    engine_name: Mapped[str] = mapped_column(String(48), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(64), nullable=False)
    extraction_status: Mapped[str] = mapped_column(String(32), nullable=False)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    confirmed_values_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    extracted_text_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_text_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw_text_excerpt_json: Mapped[object] = mapped_column(JSON, nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    confirmed_at: Mapped[str | None] = mapped_column(String(32), nullable=True)


class ExtractionField(Base):
    __tablename__ = "extraction_field"
    __table_args__ = (
        UniqueConstraint("extraction_id", "field_name", name="ux_extraction_field_name"),
        CheckConstraint("page_number >= 1 AND page_number <= 3", name="ck_extraction_field_page"),
        CheckConstraint(_PARSE_STATUS_CHECK, name="ck_extraction_field_parse_status"),
        CheckConstraint(_PROVENANCE_CHECK, name="ck_extraction_field_provenance"),
    )

    field_record_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    extraction_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("document_extraction.extraction_id", ondelete="RESTRICT"), nullable=False
    )
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("medical_document.document_id", ondelete="RESTRICT"), nullable=False
    )
    field_name: Mapped[str] = mapped_column(String(64), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    region_json: Mapped[object | None] = mapped_column(JSON, nullable=True)
    raw_value_text: Mapped[str | None] = mapped_column(String(128), nullable=True)
    parsed_value_json: Mapped[object | None] = mapped_column(JSON, nullable=True)
    confirmed_value_json: Mapped[object | None] = mapped_column(JSON, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    parse_status: Mapped[str] = mapped_column(String(32), nullable=False)
    conflict_flag: Mapped[bool] = mapped_column(Boolean, nullable=False)
    field_provenance: Mapped[str] = mapped_column(String(40), nullable=False)


class ExtractionEvent(Base):
    __tablename__ = "extraction_event"
    __table_args__ = (
        CheckConstraint(_EVENT_TYPE_CHECK, name="ck_extraction_event_type"),
    )

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("medical_document.document_id", ondelete="RESTRICT"), nullable=False
    )
    extraction_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("document_extraction.extraction_id", ondelete="RESTRICT"), nullable=True
    )
    extraction_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("user_account.user_id", ondelete="RESTRICT"), nullable=False
    )
    actor_role: Mapped[str] = mapped_column(String(16), nullable=False)
    field_diffs_json: Mapped[object] = mapped_column(JSON, nullable=False)
    recorded_at: Mapped[str] = mapped_column(String(32), nullable=False)


class AssessmentDocument(Base):
    __tablename__ = "assessment_document"
    __table_args__ = (
        ForeignKeyConstraint(
            ["assessment_id", "patient_id"],
            ["assessment.assessment_id", "assessment.patient_id"],
            ondelete="RESTRICT",
            name="fk_assessment_document_assessment",
        ),
        ForeignKeyConstraint(
            ["document_id", "patient_id"],
            ["medical_document.document_id", "medical_document.patient_id"],
            ondelete="RESTRICT",
            name="fk_assessment_document_document",
        ),
        ForeignKeyConstraint(
            ["extraction_id", "document_id", "extraction_version"],
            [
                "document_extraction.extraction_id",
                "document_extraction.document_id",
                "document_extraction.extraction_version",
            ],
            ondelete="RESTRICT",
            name="fk_assessment_document_extraction",
        ),
        UniqueConstraint("assessment_id", "document_id", name="ux_assessment_document_pair"),
        UniqueConstraint("assessment_id", "binding_id", name="ux_assessment_document_ass_binding"),
        CheckConstraint(_ATTACHMENT_ROLE_CHECK, name="ck_assessment_document_role"),
        CheckConstraint(
            "(extraction_id IS NULL AND extraction_version IS NULL "
            "AND attachment_role != 'OCR_SOURCE_REPORT') "
            "OR (extraction_id IS NOT NULL AND extraction_version IS NOT NULL)",
            name="ck_assessment_document_extraction_pair",
        ),
    )

    binding_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    assessment_id: Mapped[str] = mapped_column(String(36), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    document_id: Mapped[str] = mapped_column(String(36), nullable=False)
    extraction_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    extraction_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    document_sha256_at_bind: Mapped[str] = mapped_column(String(64), nullable=False)
    attachment_role: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)


__all__ = [
    "MedicalDocument",
    "DocumentExtraction",
    "ExtractionField",
    "ExtractionEvent",
    "AssessmentDocument",
]
