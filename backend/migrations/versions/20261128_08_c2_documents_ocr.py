"""C2 Track 2 — bounded document intake and local OCR (additive).

Revision ID: 20261128_08
Revises: 20261128_07
Create Date: 2026-11-28

Adds exactly five tables (``medical_document``, ``document_extraction``,
``extraction_field``, ``extraction_event``, ``assessment_document``) plus their
immutability triggers. ``down_revision`` is Track 1's ``20261128_07``; this
migration is the Track 2 contributor deliverable and is integrated after the
shared Track 1 checkpoint (see the implementation handoff document).

RB-C1: in-place downgrade is permitted only on a disposable database with no
C1, ``07`` or ``08`` state. A populated database refuses downgrade and requires a
verified backup restoration. Offline (``as_sql``) downgrade is refused.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261128_08"
down_revision: Union[str, None] = "20261128_07"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Exact trigger SQL, also exported for Database.verify_schema() startup checks.
TRIGGER_DEFINITIONS: dict[str, str] = {
    "tr_medical_document_immutable_identity": """
        CREATE TRIGGER tr_medical_document_immutable_identity
        BEFORE UPDATE ON medical_document
        BEGIN
            SELECT RAISE(ABORT, 'medical_document_identity_immutable')
            WHERE OLD.document_id != NEW.document_id
               OR OLD.patient_id != NEW.patient_id
               OR OLD.uploaded_by_user_id != NEW.uploaded_by_user_id
               OR OLD.document_kind != NEW.document_kind
               OR OLD.fixture_template_id != NEW.fixture_template_id
               OR OLD.fixture_file_sha256 != NEW.fixture_file_sha256
               OR OLD.original_filename_sanitized != NEW.original_filename_sanitized
               OR OLD.declared_media_type != NEW.declared_media_type
               OR OLD.byte_size != NEW.byte_size
               OR OLD.storage_key != NEW.storage_key
               OR OLD.created_at != NEW.created_at;
        END
    """,
    "tr_medical_document_no_delete": """
        CREATE TRIGGER tr_medical_document_no_delete
        BEFORE DELETE ON medical_document
        BEGIN
            SELECT RAISE(ABORT, 'medical_document_delete_forbidden');
        END
    """,
    "tr_extraction_confirmed_immutable": """
        CREATE TRIGGER tr_extraction_confirmed_immutable
        BEFORE UPDATE ON document_extraction
        BEGIN
            SELECT RAISE(ABORT, 'extraction_confirmed_immutable')
            WHERE OLD.is_confirmed = 1;
        END
    """,
    "tr_document_extraction_no_delete": """
        CREATE TRIGGER tr_document_extraction_no_delete
        BEFORE DELETE ON document_extraction
        BEGIN
            SELECT RAISE(ABORT, 'document_extraction_delete_forbidden');
        END
    """,
    "tr_extraction_event_no_update": """
        CREATE TRIGGER tr_extraction_event_no_update
        BEFORE UPDATE ON extraction_event
        BEGIN
            SELECT RAISE(ABORT, 'extraction_event_update_forbidden');
        END
    """,
    "tr_extraction_event_no_delete": """
        CREATE TRIGGER tr_extraction_event_no_delete
        BEFORE DELETE ON extraction_event
        BEGIN
            SELECT RAISE(ABORT, 'extraction_event_delete_forbidden');
        END
    """,
    "tr_assessment_document_no_update": """
        CREATE TRIGGER tr_assessment_document_no_update
        BEFORE UPDATE ON assessment_document
        BEGIN
            SELECT RAISE(ABORT, 'assessment_document_update_forbidden');
        END
    """,
    "tr_assessment_document_no_delete": """
        CREATE TRIGGER tr_assessment_document_no_delete
        BEFORE DELETE ON assessment_document
        BEGIN
            SELECT RAISE(ABORT, 'assessment_document_delete_forbidden');
        END
    """,
}


def upgrade() -> None:
    op.create_table(
        "medical_document",
        sa.Column("document_id", sa.String(36), primary_key=True),
        sa.Column("patient_id", sa.String(36),
                  sa.ForeignKey("patient_profile.patient_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("uploaded_by_user_id", sa.String(36),
                  sa.ForeignKey("user_account.user_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("document_kind", sa.String(48), nullable=False),
        sa.Column("fixture_template_id", sa.String(64), nullable=False),
        sa.Column("fixture_file_sha256", sa.String(64), nullable=False),
        sa.Column("original_filename_sanitized", sa.String(128), nullable=False),
        sa.Column("declared_media_type", sa.String(64), nullable=False),
        sa.Column("byte_size", sa.Integer, nullable=False),
        sa.Column("page_count", sa.Integer, nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=True),
        sa.Column("storage_key", sa.String(160), nullable=False),
        sa.Column("upload_status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("staging_key", sa.String(200), nullable=True),
        sa.Column("reclaim_at", sa.String(32), nullable=True),
        sa.Column("validated_at", sa.String(32), nullable=True),
        sa.UniqueConstraint("document_id", "patient_id", name="ux_medical_document_id_patient"),
        sa.UniqueConstraint("storage_key", name="ux_medical_document_storage_key"),
        sa.CheckConstraint(
            "document_kind IN ('RESTING_CARDIAC_DEMO_REPORT','UNRELATED_LAB_DEMO_REPORT')",
            name="ck_medical_document_kind"),
        sa.CheckConstraint(
            "upload_status IN ('PENDING_SCAN','STORED','UPLOAD_FAILED','SUPERSEDED')",
            name="ck_medical_document_upload_status"),
        sa.CheckConstraint(
            "declared_media_type IN ('application/pdf','image/png','image/jpeg')",
            name="ck_medical_document_media_type"),
        sa.CheckConstraint("byte_size >= 0 AND byte_size <= 5242880", name="ck_medical_document_byte_size"),
        sa.CheckConstraint("page_count >= 0 AND page_count <= 3", name="ck_medical_document_page_count"),
    )

    op.create_table(
        "document_extraction",
        sa.Column("extraction_id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36),
                  sa.ForeignKey("medical_document.document_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("extraction_version", sa.Integer, nullable=False),
        sa.Column("document_sha256", sa.String(64), nullable=False),
        sa.Column("extraction_mode", sa.String(24), nullable=False),
        sa.Column("template_id", sa.String(64), nullable=True),
        sa.Column("template_version", sa.String(16), nullable=True),
        sa.Column("engine_name", sa.String(48), nullable=False),
        sa.Column("engine_version", sa.String(64), nullable=False),
        sa.Column("extraction_status", sa.String(32), nullable=False),
        sa.Column("is_confirmed", sa.Boolean, nullable=False),
        sa.Column("confirmed_values_sha256", sa.String(64), nullable=True),
        sa.Column("extracted_text_bytes", sa.Integer, nullable=False),
        sa.Column("raw_text_sha256", sa.String(64), nullable=True),
        sa.Column("raw_text_excerpt_json", sa.JSON, nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("confirmed_at", sa.String(32), nullable=True),
        sa.UniqueConstraint("document_id", "extraction_version", name="ux_document_extraction_version"),
        sa.UniqueConstraint("extraction_id", "document_id", "extraction_version", name="ux_extraction_id_doc_ver"),
        sa.CheckConstraint("extraction_version >= 1", name="ck_document_extraction_version"),
        sa.CheckConstraint("extraction_mode IN ('PDF_TEXT','RASTER_OCR','FAILED')", name="ck_document_extraction_mode"),
        sa.CheckConstraint(
            "extraction_status IN ('EXTRACTED_DRAFT','NEEDS_MANUAL_REVIEW',"
            "'UNSUPPORTED_TEMPLATE','CONFIRMED_BY_PATIENT','FAILED')",
            name="ck_document_extraction_status"),
        sa.CheckConstraint("extracted_text_bytes >= 0 AND extracted_text_bytes <= 1048576",
                           name="ck_document_extraction_text_bytes"),
        sa.CheckConstraint(
            "(is_confirmed = 1 AND confirmed_values_sha256 IS NOT NULL "
            "AND confirmed_at IS NOT NULL AND extraction_status = 'CONFIRMED_BY_PATIENT') "
            "OR (is_confirmed = 0 AND confirmed_values_sha256 IS NULL "
            "AND confirmed_at IS NULL AND extraction_status != 'CONFIRMED_BY_PATIENT')",
            name="ck_document_extraction_confirmation"),
    )

    op.create_table(
        "extraction_field",
        sa.Column("field_record_id", sa.String(36), primary_key=True),
        sa.Column("extraction_id", sa.String(36),
                  sa.ForeignKey("document_extraction.extraction_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("document_id", sa.String(36),
                  sa.ForeignKey("medical_document.document_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("field_name", sa.String(64), nullable=False),
        sa.Column("page_number", sa.Integer, nullable=False),
        sa.Column("region_json", sa.JSON, nullable=True),
        sa.Column("raw_value_text", sa.String(128), nullable=True),
        sa.Column("parsed_value_json", sa.JSON, nullable=True),
        sa.Column("confirmed_value_json", sa.JSON, nullable=True),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("parse_status", sa.String(32), nullable=False),
        sa.Column("conflict_flag", sa.Boolean, nullable=False),
        sa.Column("field_provenance", sa.String(40), nullable=False),
        sa.UniqueConstraint("extraction_id", "field_name", name="ux_extraction_field_name"),
        sa.CheckConstraint("page_number >= 1 AND page_number <= 3", name="ck_extraction_field_page"),
        sa.CheckConstraint(
            "parse_status IN ('PARSED','LOW_CONFIDENCE','CONFLICT_REVIEW_REQUIRED',"
            "'INVALID_VALUE','MISSING','UNRELATED_IGNORED')",
            name="ck_extraction_field_parse_status"),
        sa.CheckConstraint(
            "field_provenance IN ('OCR_EXTRACTED_UNCONFIRMED','OCR_EXTRACTED_PATIENT_CONFIRMED',"
            "'PATIENT_ENTERED_FROM_OCR_DRAFT','UNRELATED_NON_MODEL_FIELD')",
            name="ck_extraction_field_provenance"),
    )

    op.create_table(
        "extraction_event",
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36),
                  sa.ForeignKey("medical_document.document_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("extraction_id", sa.String(36),
                  sa.ForeignKey("document_extraction.extraction_id", ondelete="RESTRICT"), nullable=True),
        sa.Column("extraction_version", sa.Integer, nullable=True),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("actor_user_id", sa.String(36),
                  sa.ForeignKey("user_account.user_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("actor_role", sa.String(16), nullable=False),
        sa.Column("field_diffs_json", sa.JSON, nullable=False),
        sa.Column("recorded_at", sa.String(32), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('UPLOADED','EXTRACTED','EXTRACTION_FAILED','PATIENT_EDITED',"
            "'PATIENT_CONFIRMED','EDITED_AND_CONFIRMED','DOCTOR_ACKNOWLEDGED')",
            name="ck_extraction_event_type"),
    )

    op.create_table(
        "assessment_document",
        sa.Column("binding_id", sa.String(36), primary_key=True),
        sa.Column("assessment_id", sa.String(36), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("document_id", sa.String(36), nullable=False),
        sa.Column("extraction_id", sa.String(36), nullable=True),
        sa.Column("extraction_version", sa.Integer, nullable=True),
        sa.Column("document_sha256_at_bind", sa.String(64), nullable=False),
        sa.Column("attachment_role", sa.String(32), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.ForeignKeyConstraint(
            ["assessment_id", "patient_id"],
            ["assessment.assessment_id", "assessment.patient_id"],
            ondelete="RESTRICT", name="fk_assessment_document_assessment"),
        sa.ForeignKeyConstraint(
            ["document_id", "patient_id"],
            ["medical_document.document_id", "medical_document.patient_id"],
            ondelete="RESTRICT", name="fk_assessment_document_document"),
        sa.ForeignKeyConstraint(
            ["extraction_id", "document_id", "extraction_version"],
            ["document_extraction.extraction_id", "document_extraction.document_id",
             "document_extraction.extraction_version"],
            ondelete="RESTRICT", name="fk_assessment_document_extraction"),
        sa.UniqueConstraint("assessment_id", "document_id", name="ux_assessment_document_pair"),
        sa.UniqueConstraint("assessment_id", "binding_id", name="ux_assessment_document_ass_binding"),
        sa.CheckConstraint(
            "attachment_role IN ('SUPPORTING_REPORT','OCR_SOURCE_REPORT','UNRELATED_LAB_ATTACHMENT')",
            name="ck_assessment_document_role"),
        sa.CheckConstraint(
            "(extraction_id IS NULL AND extraction_version IS NULL "
            "AND attachment_role != 'OCR_SOURCE_REPORT') "
            "OR (extraction_id IS NOT NULL AND extraction_version IS NOT NULL)",
            name="ck_assessment_document_extraction_pair"),
    )

    for sql in TRIGGER_DEFINITIONS.values():
        op.execute(sql)


def downgrade() -> None:
    # RB-C1: refuse offline downgrade and any populated database.
    if op.get_context().as_sql:
        raise RuntimeError(
            "C2 document downgrade requires online verification of a disposable database."
        )
    connection = op.get_bind()
    c1_tables = (
        "user_account", "doctor_profile", "patient_identity", "patient_profile",
        "identity_key_check", "session", "login_attempt", "verified_visit",
        "patient_invitation", "invitation_attempt", "doctor_patient_assignment",
        "consent_record", "invitation_redemption", "durable_idempotency",
        "workflow_audit_event", "admin_bootstrap_record",
    )
    core_07_tables = (
        "health_profile", "assessment_snapshot", "assessment",
        "inference_attempt", "inference_result",
    )
    doc_08_tables = (
        "medical_document", "document_extraction", "extraction_field",
        "extraction_event", "assessment_document",
    )
    for table in c1_tables + core_07_tables + doc_08_tables:
        if connection.execute(sa.text(f'SELECT 1 FROM "{table}" LIMIT 1')).first() is not None:
            raise RuntimeError(
                "C2 document downgrade refused: persisted state is present. "
                "Use an independently verified backup for operational rollback; "
                "in-place downgrade is supported only on disposable databases."
            )
    for name in TRIGGER_DEFINITIONS:
        op.execute(f"DROP TRIGGER IF EXISTS {name}")
    op.drop_table("assessment_document")
    op.drop_table("extraction_field")
    op.drop_table("extraction_event")
    op.drop_table("document_extraction")
    op.drop_table("medical_document")
