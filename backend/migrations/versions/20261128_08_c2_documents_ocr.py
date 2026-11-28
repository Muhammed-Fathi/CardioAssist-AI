"""C2 Track 2 — bounded document intake and local OCR (additive).

Revision ID: 20261128_08
Revises: 20261128_07
Create Date: 2026-11-28

Adds the Track 2 document tables (``medical_document``, ``document_extraction``,
``extraction_field``, ``extraction_event``, ``assessment_document``) plus the
corrections-round ``document_inflight_operation`` (T2-R1 durable in-flight
ownership/lease/fence), their CHECK constraints and their immutability triggers.
``down_revision`` is Track 1's ``20261128_07``; this migration is the Track 2
contributor deliverable and is integrated after the shared Track 1 checkpoint
(see the implementation handoff document).

Corrections round (reviewer REQUEST CHANGES #7233518509):

* T2-R2 — ``extraction_field`` is protected by INSERT/UPDATE/DELETE triggers:
  confirmed children are frozen, draft OCR evidence columns are immutable, a
  child can only be inserted under an unconfirmed parent of the SAME document
  (composite FK), and provenance transitions are closed (no laundering).
  ``document_extraction.confirmed_envelope_json`` persists the exact canonical
  confirmation envelope so ``confirmed_values_sha256`` is reconstructible.
* T2-R1 — ``document_inflight_operation`` reserves the complete C1 replay
  identity with a lease owner/expiry and a monotonic fence token; STORED
  promotion is trigger-guarded (digest + validation evidence required, only
  from ``PENDING_SCAN``, stored digest frozen thereafter).
* T2-R5 — verified ``pixel_width``/``pixel_height`` metadata on
  ``medical_document``.

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
# All identity comparisons are NULL-safe (``IS NOT``) so a NULL->value or
# value->NULL mutation is rejected exactly like a value->value mutation.
TRIGGER_DEFINITIONS: dict[str, str] = {
    "tr_medical_document_immutable_identity": """
        CREATE TRIGGER tr_medical_document_immutable_identity
        BEFORE UPDATE ON medical_document
        BEGIN
            SELECT RAISE(ABORT, 'medical_document_identity_immutable')
            WHERE OLD.document_id IS NOT NEW.document_id
               OR OLD.patient_id IS NOT NEW.patient_id
               OR OLD.uploaded_by_user_id IS NOT NEW.uploaded_by_user_id
               OR OLD.document_kind IS NOT NEW.document_kind
               OR OLD.fixture_template_id IS NOT NEW.fixture_template_id
               OR OLD.fixture_file_sha256 IS NOT NEW.fixture_file_sha256
               OR OLD.original_filename_sanitized IS NOT NEW.original_filename_sanitized
               OR OLD.declared_media_type IS NOT NEW.declared_media_type
               OR OLD.byte_size IS NOT NEW.byte_size
               OR OLD.storage_key IS NOT NEW.storage_key
               OR OLD.created_at IS NOT NEW.created_at;
        END
    """,
    "tr_medical_document_no_delete": """
        CREATE TRIGGER tr_medical_document_no_delete
        BEFORE DELETE ON medical_document
        BEGIN
            SELECT RAISE(ABORT, 'medical_document_delete_forbidden');
        END
    """,
    # T2-R1/R2: once STORED, the verified digest, lifecycle status, page count
    # and pixel metadata are frozen; the stored digest must always equal the
    # reserved allowlist digest.
    "tr_medical_document_stored_immutable": """
        CREATE TRIGGER tr_medical_document_stored_immutable
        BEFORE UPDATE ON medical_document
        WHEN OLD.upload_status = 'STORED'
        BEGIN
            SELECT RAISE(ABORT, 'medical_document_stored_immutable')
            WHERE OLD.content_sha256 IS NOT NEW.content_sha256
               OR OLD.upload_status IS NOT NEW.upload_status
               OR OLD.page_count IS NOT NEW.page_count
               OR OLD.pixel_width IS NOT NEW.pixel_width
               OR OLD.pixel_height IS NOT NEW.pixel_height
               OR OLD.validated_at IS NOT NEW.validated_at;
        END
    """,
    # T2-R1: promotion to STORED is only legal from PENDING_SCAN and requires
    # the verified digest (equal to the reserved fixture digest), validation
    # evidence and a cleared staging key — recovery cannot publish an
    # unvalidated or partially staged reservation.
    "tr_medical_document_promotion_guard": """
        CREATE TRIGGER tr_medical_document_promotion_guard
        BEFORE UPDATE ON medical_document
        WHEN NEW.upload_status = 'STORED' AND OLD.upload_status != 'STORED'
        BEGIN
            SELECT RAISE(ABORT, 'medical_document_promotion_invalid')
            WHERE OLD.upload_status != 'PENDING_SCAN'
               OR NEW.content_sha256 IS NULL
               OR NEW.content_sha256 IS NOT NEW.fixture_file_sha256
               OR NEW.validated_at IS NULL
               OR NEW.staging_key IS NOT NULL;
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
    # T2-R2: a child field may only be inserted under an UNCONFIRMED parent as
    # draft OCR evidence (no pre-confirmed values, no confirmation provenance).
    "tr_extraction_field_insert_guard": """
        CREATE TRIGGER tr_extraction_field_insert_guard
        BEFORE INSERT ON extraction_field
        BEGIN
            SELECT RAISE(ABORT, 'extraction_field_parent_confirmed')
            WHERE (SELECT is_confirmed FROM document_extraction
                   WHERE extraction_id = NEW.extraction_id
                     AND document_id = NEW.document_id) = 1;
            SELECT RAISE(ABORT, 'extraction_field_insert_confirmed_forbidden')
            WHERE NEW.confirmed_value_json IS NOT NULL
               OR NEW.confirmed_unit IS NOT NULL;
            SELECT RAISE(ABORT, 'extraction_field_insert_provenance_forbidden')
            WHERE NEW.field_provenance NOT IN
                ('OCR_EXTRACTED_UNCONFIRMED','UNRELATED_NON_MODEL_FIELD');
        END
    """,
    # T2-R2: the ONLY legal child update is the patient-confirmation transition
    # while the parent is still unconfirmed. All draft OCR evidence columns are
    # immutable (NULL-safe), and the new provenance must be a confirmation
    # provenance. After the parent is confirmed every child update is refused.
    "tr_extraction_field_update_guard": """
        CREATE TRIGGER tr_extraction_field_update_guard
        BEFORE UPDATE ON extraction_field
        BEGIN
            SELECT RAISE(ABORT, 'extraction_field_confirmed_immutable')
            WHERE (SELECT is_confirmed FROM document_extraction
                   WHERE extraction_id = OLD.extraction_id
                     AND document_id = OLD.document_id) = 1;
            SELECT RAISE(ABORT, 'extraction_field_evidence_immutable')
            WHERE OLD.field_record_id IS NOT NEW.field_record_id
               OR OLD.extraction_id IS NOT NEW.extraction_id
               OR OLD.document_id IS NOT NEW.document_id
               OR OLD.field_name IS NOT NEW.field_name
               OR OLD.page_number IS NOT NEW.page_number
               OR OLD.region_json IS NOT NEW.region_json
               OR OLD.raw_value_text IS NOT NEW.raw_value_text
               OR OLD.parsed_value_json IS NOT NEW.parsed_value_json
               OR OLD.unit IS NOT NEW.unit
               OR OLD.confidence IS NOT NEW.confidence
               OR OLD.parse_status IS NOT NEW.parse_status
               OR OLD.conflict_flag IS NOT NEW.conflict_flag;
            SELECT RAISE(ABORT, 'extraction_field_provenance_forbidden')
            WHERE NEW.field_provenance NOT IN
                ('OCR_EXTRACTED_PATIENT_CONFIRMED','PATIENT_ENTERED_FROM_OCR_DRAFT');
        END
    """,
    "tr_extraction_field_no_delete": """
        CREATE TRIGGER tr_extraction_field_no_delete
        BEFORE DELETE ON extraction_field
        BEGIN
            SELECT RAISE(ABORT, 'extraction_field_delete_forbidden');
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
        sa.Column("pixel_width", sa.Integer, nullable=True),
        sa.Column("pixel_height", sa.Integer, nullable=True),
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
        sa.Column("confirmed_envelope_json", sa.JSON(none_as_null=True), nullable=True),
        sa.UniqueConstraint("document_id", "extraction_version", name="ux_document_extraction_version"),
        sa.UniqueConstraint("extraction_id", "document_id", "extraction_version", name="ux_extraction_id_doc_ver"),
        sa.UniqueConstraint("extraction_id", "document_id", name="ux_extraction_id_document"),
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
            "AND confirmed_envelope_json IS NOT NULL "
            "AND confirmed_at IS NOT NULL AND extraction_status = 'CONFIRMED_BY_PATIENT') "
            "OR (is_confirmed = 0 AND confirmed_values_sha256 IS NULL "
            "AND confirmed_envelope_json IS NULL "
            "AND confirmed_at IS NULL AND extraction_status != 'CONFIRMED_BY_PATIENT')",
            name="ck_document_extraction_confirmation"),
    )

    op.create_table(
        "extraction_field",
        sa.Column("field_record_id", sa.String(36), primary_key=True),
        sa.Column("extraction_id", sa.String(36), nullable=False),
        sa.Column("document_id", sa.String(36),
                  sa.ForeignKey("medical_document.document_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("field_name", sa.String(64), nullable=False),
        sa.Column("page_number", sa.Integer, nullable=False),
        sa.Column("region_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("raw_value_text", sa.String(128), nullable=True),
        sa.Column("parsed_value_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("confirmed_value_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("parse_status", sa.String(32), nullable=False),
        sa.Column("conflict_flag", sa.Boolean, nullable=False),
        sa.Column("field_provenance", sa.String(40), nullable=False),
        sa.Column("confirmed_unit", sa.String(32), nullable=True),
        sa.Column("missing_reason", sa.String(32), nullable=True),
        sa.ForeignKeyConstraint(
            ["extraction_id", "document_id"],
            ["document_extraction.extraction_id", "document_extraction.document_id"],
            ondelete="RESTRICT", name="fk_extraction_field_parent"),
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
        sa.CheckConstraint(
            "missing_reason IS NULL OR missing_reason IN "
            "('not_measured','not_available_at_time','unknown','not_provided')",
            name="ck_extraction_field_missing_reason"),
    )

    op.create_table(
        "extraction_event",
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36),
                  sa.ForeignKey("medical_document.document_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("extraction_id", sa.String(36), nullable=True),
        sa.Column("extraction_version", sa.Integer, nullable=True),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("actor_user_id", sa.String(36),
                  sa.ForeignKey("user_account.user_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("actor_role", sa.String(16), nullable=False),
        sa.Column("field_diffs_json", sa.JSON, nullable=False),
        sa.Column("recorded_at", sa.String(32), nullable=False),
        sa.ForeignKeyConstraint(
            ["extraction_id", "document_id", "extraction_version"],
            ["document_extraction.extraction_id", "document_extraction.document_id",
             "document_extraction.extraction_version"],
            ondelete="RESTRICT", name="fk_extraction_event_extraction"),
        sa.CheckConstraint(
            "event_type IN ('UPLOADED','EXTRACTED','EXTRACTION_FAILED','PATIENT_EDITED',"
            "'PATIENT_CONFIRMED','EDITED_AND_CONFIRMED','DOCTOR_ACKNOWLEDGED')",
            name="ck_extraction_event_type"),
        sa.CheckConstraint(
            "(extraction_id IS NULL AND extraction_version IS NULL) "
            "OR (extraction_id IS NOT NULL AND extraction_version IS NOT NULL)",
            name="ck_extraction_event_pair"),
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

    # T2-R1: durable in-flight ownership / lease / fence. Reserved in the same
    # transaction as the guarded effect; deleted in the same transaction that
    # writes the durable replay record on success.
    op.create_table(
        "document_inflight_operation",
        sa.Column("inflight_id", sa.String(36), primary_key=True),
        sa.Column("replay_scope", sa.String(16), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("actor_binding", sa.String(80), nullable=False),
        sa.Column("operation", sa.String(64), nullable=False),
        sa.Column("target_ref", sa.String(160), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("actor_user_id", sa.String(36),
                  sa.ForeignKey("user_account.user_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("patient_id", sa.String(36),
                  sa.ForeignKey("patient_profile.patient_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("document_id", sa.String(36),
                  sa.ForeignKey("medical_document.document_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("fence_token", sa.Integer, nullable=False),
        sa.Column("lease_owner", sa.String(36), nullable=False),
        sa.Column("lease_expires_at", sa.String(32), nullable=False),
        sa.Column("attempt_count", sa.Integer, nullable=False),
        sa.Column("failure_code", sa.String(64), nullable=True),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.String(32), nullable=False),
        sa.UniqueConstraint(
            "replay_scope", "key_hash", "actor_binding", "operation", "target_ref",
            name="ux_inflight_replay_identity"),
        sa.UniqueConstraint("document_id", "operation", name="ux_inflight_document_operation"),
        sa.CheckConstraint("state IN ('IN_FLIGHT','FAILED')", name="ck_inflight_state"),
        sa.CheckConstraint("fence_token >= 1", name="ck_inflight_fence_token"),
        sa.CheckConstraint("attempt_count >= 1", name="ck_inflight_attempt_count"),
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
        "extraction_event", "assessment_document", "document_inflight_operation",
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
    op.drop_table("document_inflight_operation")
    op.drop_table("assessment_document")
    op.drop_table("extraction_field")
    op.drop_table("extraction_event")
    op.drop_table("document_extraction")
    op.drop_table("medical_document")
