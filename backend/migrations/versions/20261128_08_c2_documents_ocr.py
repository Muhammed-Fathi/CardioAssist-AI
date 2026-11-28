"""C2 Track 2 — bounded document intake and local OCR (additive).

Revision ID: 20261128_08
Revises: 20261128_07
Create Date: 2026-11-28

Adds the six document/OCR tables, their CHECK constraints and fourteen
immutability/authorization triggers. It also replaces the 07 assessment-scope
and attempt-insert guards with integrated definitions that accept only bounded,
snapshot-backed bindings and require the complete binding set before attempt
initiation; downgrade restores the exact 07 guards. ``down_revision`` is
``20261128_07``.

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


# Exact SQL for the fourteen new document triggers, also exported for startup
# verification. The replacement for tr_assessment_scope_insert is defined
# separately below and overrides the 07 baseline under the same trigger name.
# Identity comparisons use NULL-safe ``IS NOT`` checks.
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
    # I1: every binding row must be the exact descriptor frozen into the
    # immutable assessment snapshot and may be created only in S1's authorized
    # INPUT_VALIDATED phase, before any attempt or result pointer exists.
    "tr_assessment_document_insert_guard": """
        CREATE TRIGGER tr_assessment_document_insert_guard
        BEFORE INSERT ON assessment_document
        FOR EACH ROW
        WHEN NOT EXISTS (
            SELECT 1
            FROM assessment a
            JOIN assessment_snapshot s ON s.snapshot_id = a.snapshot_id
            JOIN json_each(s.snapshot_json, '$.attached_documents') AS descriptor
            JOIN medical_document d
              ON d.document_id = NEW.document_id
             AND d.patient_id = NEW.patient_id
            WHERE a.assessment_id = NEW.assessment_id
              AND a.patient_id = NEW.patient_id
              AND a.status = 'INPUT_VALIDATED'
              AND a.reason_code IS NULL
              AND a.active_attempt_id IS NULL
              AND a.current_result_id IS NULL
              AND a.current_generation = 0
              AND NOT EXISTS (
                    SELECT 1 FROM inference_attempt i
                    WHERE i.assessment_id = a.assessment_id
              )
              AND EXISTS (
                    SELECT 1 FROM doctor_patient_assignment p
                    WHERE p.assignment_id = a.assignment_id
                      AND p.patient_id = a.patient_id
                      AND p.revoked_at IS NULL
              )
              AND EXISTS (
                    SELECT 1 FROM consent_record c
                    WHERE c.consent_id = a.consent_id
                      AND c.patient_id = a.patient_id
                      AND c.kind = 'synthetic_demo'
                      AND c.scope = 'patient_wide_synthetic_demo'
                      AND c.contract_version = 'term1-c1-v1'
                      AND c.revoked_at IS NULL
              )
              AND json_extract(descriptor.value, '$.binding_id') = NEW.binding_id
              AND json_extract(descriptor.value, '$.document_id') = NEW.document_id
              AND json_extract(descriptor.value, '$.document_sha256_at_bind')
                    = NEW.document_sha256_at_bind
              AND json_extract(descriptor.value, '$.attachment_role') = NEW.attachment_role
              AND json_extract(descriptor.value, '$.extraction_id') IS NEW.extraction_id
              AND json_extract(descriptor.value, '$.extraction_version') IS NEW.extraction_version
              AND d.upload_status = 'STORED'
              AND d.content_sha256 = NEW.document_sha256_at_bind
              AND d.fixture_file_sha256 = d.content_sha256
              AND (
                    (d.document_kind = 'RESTING_CARDIAC_DEMO_REPORT'
                     AND NEW.attachment_role IN ('SUPPORTING_REPORT','OCR_SOURCE_REPORT'))
                 OR (d.document_kind = 'UNRELATED_LAB_DEMO_REPORT'
                     AND NEW.attachment_role = 'UNRELATED_LAB_ATTACHMENT')
              )
              AND (
                    (NEW.attachment_role = 'OCR_SOURCE_REPORT'
                     AND s.source_kind = 'synthetic_demo_ocr_confirmed'
                     AND json_type(descriptor.value, '$.extraction_confirmed_at') = 'text'
                     AND json_type(descriptor.value, '$.confirmed_values_sha256') = 'text'
                     AND EXISTS (
                         SELECT 1
                         FROM document_extraction x
                         WHERE x.extraction_id = NEW.extraction_id
                           AND x.document_id = NEW.document_id
                           AND x.extraction_version = NEW.extraction_version
                           AND x.is_confirmed = 1
                           AND x.extraction_status = 'CONFIRMED_BY_PATIENT'
                           AND x.template_id = 'CAI-DEMO-RESTING-CARDIAC-REPORT-V1'
                           AND x.document_sha256 = NEW.document_sha256_at_bind
                           AND x.confirmed_at = json_extract(
                               descriptor.value, '$.extraction_confirmed_at'
                           )
                           AND x.confirmed_values_sha256 = json_extract(
                               descriptor.value, '$.confirmed_values_sha256'
                           )
                           AND x.confirmed_envelope_json IS NOT NULL
                     ))
                 OR (NEW.attachment_role != 'OCR_SOURCE_REPORT'
                     AND NEW.extraction_id IS NULL
                     AND NEW.extraction_version IS NULL
                     AND json_type(descriptor.value, '$.extraction_confirmed_at') = 'null'
                     AND json_type(descriptor.value, '$.confirmed_values_sha256') = 'null')
              )
        )
        BEGIN
            SELECT RAISE(ABORT, 'assessment_document_insert_forbidden');
        END
    """,
}

# Migration 07's insert guard intentionally allowed only empty attachment lists
# before the document tables existed. Migration 08 replaces that one guard with
# the integrated document-aware version, while retaining the literal 07 form so
# a clean downgrade restores exactly the prior schema invariant.
BASE_ASSESSMENT_SCOPE_TRIGGER_DEFINITION = """CREATE TRIGGER tr_assessment_scope_insert
BEFORE INSERT ON assessment
FOR EACH ROW
WHEN NOT EXISTS (
        SELECT 1 FROM doctor_patient_assignment a
        WHERE a.assignment_id = NEW.assignment_id
          AND a.patient_id = NEW.patient_id
          AND a.revoked_at IS NULL
    )
    OR NOT EXISTS (
        SELECT 1 FROM consent_record c
        WHERE c.consent_id = NEW.consent_id
          AND c.patient_id = NEW.patient_id
          AND c.kind = 'synthetic_demo'
          AND c.scope = 'patient_wide_synthetic_demo'
          AND c.contract_version = 'term1-c1-v1'
          AND c.revoked_at IS NULL
    )
    OR (NEW.reassessment_of_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM assessment p
        WHERE p.assessment_id = NEW.reassessment_of_id
          AND p.patient_id = NEW.patient_id
          AND p.assignment_id = NEW.assignment_id
    ))
    OR NOT EXISTS (
        SELECT 1
        FROM assessment_snapshot s
        JOIN health_profile h
          ON h.health_profile_id = s.health_profile_id
         AND h.patient_id = s.patient_id
        WHERE s.snapshot_id = NEW.snapshot_id
          AND s.patient_id = NEW.patient_id
          AND s.health_profile_id = NEW.health_profile_id
          AND s.panel_id = NEW.panel_id
          AND s.panel_version = NEW.panel_version
          AND s.source_contract_version = NEW.source_contract_version
          AND s.source_kind = NEW.source_kind
          AND s.schema_version = 'term1.c2.snapshot/v1'
          AND s.schema_sha256 = json_extract(s.snapshot_json, '$.schema_sha256')
          AND s.source_contract_version = json_extract(s.snapshot_json, '$.source_contract_version')
          AND s.source_kind = json_extract(s.snapshot_json, '$.source_kind')
          AND json_extract(s.snapshot_json, '$.assessment_id') = NEW.assessment_id
          AND json_extract(s.snapshot_json, '$.patient_id') = NEW.patient_id
          AND json_extract(s.snapshot_json, '$.assignment_id') = NEW.assignment_id
          AND json_extract(s.snapshot_json, '$.consent_id') = NEW.consent_id
          AND json_extract(s.snapshot_json, '$.health_profile_id') = NEW.health_profile_id
          AND json_extract(s.snapshot_json, '$.panel.panel_id') = s.panel_id
          AND json_extract(s.snapshot_json, '$.panel.panel_version') = s.panel_version
          AND json_extract(s.snapshot_json, '$.panel.panel_contract_sha256') = s.panel_contract_sha256
          AND json_extract(s.snapshot_json, '$.provenance.health_profile_id') = h.health_profile_id
          AND json_extract(s.snapshot_json, '$.provenance.health_profile_sha256') = h.profile_sha256
          AND h.status = 'COMPLETE'
          AND h.superseded_at IS NULL
          AND json_type(s.snapshot_json, '$.attached_documents') = 'array'
          AND json_array_length(s.snapshot_json, '$.attached_documents') = 0
    )
    OR ((NEW.reassessment_of_id IS NULL) != (NEW.reassessment_reason IS NULL))
BEGIN
    SELECT RAISE(ABORT, 'assessment_scope_invalid');
END;"""

# Keep the exact 07 attempt guard so a clean 08 -> 07 downgrade restores it.
# Migration 08 overlays a one-to-one snapshot/binding completeness predicate
# before permitting the first inference_attempt. S1 intentionally inserts the
# assessment, then each immutable binding, then the attempt in one transaction.
BASE_ATTEMPT_INSERT_TRIGGER_DEFINITION = """CREATE TRIGGER tr_attempt_insert_guard
BEFORE INSERT ON inference_attempt
FOR EACH ROW
WHEN NEW.state != 'INFERENCE_RUNNING'
  OR NEW.reason_code IS NOT NULL
  OR NEW.completed_at IS NOT NULL
  OR NEW.worker_id != 'disabled_stub'
  OR NOT EXISTS (
        SELECT 1
        FROM assessment s
        JOIN doctor_patient_assignment a
          ON a.assignment_id = s.assignment_id
         AND a.patient_id = s.patient_id
        JOIN consent_record c
          ON c.consent_id = s.consent_id
         AND c.patient_id = s.patient_id
        WHERE s.assessment_id = NEW.assessment_id
          AND s.status = 'INPUT_VALIDATED'
          AND s.active_attempt_id IS NULL
          AND s.current_result_id IS NULL
          AND s.current_generation = NEW.generation
          AND a.revoked_at IS NULL
          AND c.revoked_at IS NULL
          AND c.kind = 'synthetic_demo'
          AND c.scope = 'patient_wide_synthetic_demo'
          AND c.contract_version = 'term1-c1-v1'
    )
BEGIN
    SELECT RAISE(ABORT, 'inference_attempt_insert_forbidden');
END;"""

_ATTEMPT_BINDING_COMPLETENESS_CHECK = """  OR NOT EXISTS (
        SELECT 1
        FROM assessment a
        JOIN assessment_snapshot s ON s.snapshot_id = a.snapshot_id
        WHERE a.assessment_id = NEW.assessment_id
          AND (
              SELECT COUNT(*)
              FROM json_each(s.snapshot_json, '$.attached_documents')
          ) = (
              SELECT COUNT(*) FROM assessment_document b
              WHERE b.assessment_id = a.assessment_id
          )
          AND NOT EXISTS (
              SELECT 1
              FROM json_each(s.snapshot_json, '$.attached_documents') AS descriptor
              WHERE NOT EXISTS (
                  SELECT 1 FROM assessment_document b
                  WHERE b.assessment_id = a.assessment_id
                    AND b.patient_id = a.patient_id
                    AND b.binding_id = json_extract(descriptor.value, '$.binding_id')
                    AND b.document_id = json_extract(descriptor.value, '$.document_id')
                    AND b.document_sha256_at_bind = json_extract(
                        descriptor.value, '$.document_sha256_at_bind'
                    )
                    AND b.attachment_role = json_extract(
                        descriptor.value, '$.attachment_role'
                    )
                    AND b.extraction_id IS json_extract(
                        descriptor.value, '$.extraction_id'
                    )
                    AND b.extraction_version IS json_extract(
                        descriptor.value, '$.extraction_version'
                    )
              )
          )
          AND NOT EXISTS (
              SELECT 1
              FROM assessment_document b
              WHERE b.assessment_id = a.assessment_id
                AND b.patient_id = a.patient_id
                AND NOT EXISTS (
                    SELECT 1
                    FROM json_each(s.snapshot_json, '$.attached_documents') AS descriptor
                    WHERE b.binding_id = json_extract(descriptor.value, '$.binding_id')
                      AND b.document_id = json_extract(descriptor.value, '$.document_id')
                      AND b.document_sha256_at_bind = json_extract(
                          descriptor.value, '$.document_sha256_at_bind'
                      )
                      AND b.attachment_role = json_extract(
                          descriptor.value, '$.attachment_role'
                      )
                      AND b.extraction_id IS json_extract(
                          descriptor.value, '$.extraction_id'
                      )
                      AND b.extraction_version IS json_extract(
                          descriptor.value, '$.extraction_version'
                      )
                )
          )
    )
"""

_ATTEMPT_INSERT_GUARD_MARKER = (
    "BEGIN\n    SELECT RAISE(ABORT, 'inference_attempt_insert_forbidden');"
)
if BASE_ATTEMPT_INSERT_TRIGGER_DEFINITION.count(_ATTEMPT_INSERT_GUARD_MARKER) != 1:
    raise RuntimeError("Migration 07 attempt insert trigger changed unexpectedly.")
ATTEMPT_INSERT_TRIGGER_DEFINITION = BASE_ATTEMPT_INSERT_TRIGGER_DEFINITION.replace(
    _ATTEMPT_INSERT_GUARD_MARKER,
    _ATTEMPT_BINDING_COMPLETENESS_CHECK + _ATTEMPT_INSERT_GUARD_MARKER,
)

_SCOPE_ATTACHMENT_EMPTY_CHECK = (
    "AND json_array_length(s.snapshot_json, '$.attached_documents') = 0"
)
_SCOPE_ATTACHMENT_INTEGRATED_CHECK = """AND json_array_length(s.snapshot_json, '$.attached_documents') <= 5
          AND (
              SELECT COUNT(*) FROM json_each(s.snapshot_json, '$.attached_documents')
          ) = (
              SELECT COUNT(DISTINCT json_extract(a.value, '$.document_id'))
              FROM json_each(s.snapshot_json, '$.attached_documents') AS a
          )
          AND (
              SELECT COUNT(*) FROM json_each(s.snapshot_json, '$.attached_documents')
          ) = (
              SELECT COUNT(DISTINCT json_extract(a.value, '$.binding_id'))
              FROM json_each(s.snapshot_json, '$.attached_documents') AS a
          )
          AND NOT EXISTS (
              SELECT 1
              FROM json_each(s.snapshot_json, '$.attached_documents') AS a
              WHERE a.type != 'object'
                 OR (SELECT COUNT(*) FROM json_each(a.value)) != 8
                 OR json_type(a.value, '$.binding_id') IS NOT 'text'
                 OR json_type(a.value, '$.document_id') IS NOT 'text'
                 OR json_type(a.value, '$.attachment_role') IS NOT 'text'
                 OR json_type(a.value, '$.extraction_id') IS NULL
                 OR json_type(a.value, '$.extraction_version') IS NULL
                 OR json_type(a.value, '$.document_sha256_at_bind') IS NOT 'text'
                 OR json_type(a.value, '$.extraction_confirmed_at') IS NULL
                 OR json_type(a.value, '$.confirmed_values_sha256') IS NULL
                 OR COALESCE(json_extract(a.value, '$.attachment_role'), '') NOT IN (
                     'SUPPORTING_REPORT', 'OCR_SOURCE_REPORT',
                     'UNRELATED_LAB_ATTACHMENT'
                 )
                 OR length(json_extract(a.value, '$.document_sha256_at_bind')) != 64
                 OR json_extract(a.value, '$.document_sha256_at_bind') GLOB '*[^0-9a-f]*'
                 OR NOT EXISTS (
                     SELECT 1
                     FROM medical_document d
                     WHERE d.document_id = json_extract(a.value, '$.document_id')
                       AND d.patient_id = NEW.patient_id
                       AND d.upload_status = 'STORED'
                       AND d.content_sha256 = json_extract(a.value, '$.document_sha256_at_bind')
                       AND d.fixture_file_sha256 = d.content_sha256
                       AND (
                           (d.document_kind = 'RESTING_CARDIAC_DEMO_REPORT'
                            AND json_extract(a.value, '$.attachment_role') IN (
                                'SUPPORTING_REPORT', 'OCR_SOURCE_REPORT'
                            ))
                           OR (d.document_kind = 'UNRELATED_LAB_DEMO_REPORT'
                               AND json_extract(a.value, '$.attachment_role') =
                                   'UNRELATED_LAB_ATTACHMENT')
                       )
                 )
                 OR (
                     json_extract(a.value, '$.attachment_role') = 'OCR_SOURCE_REPORT'
                     AND (
                         json_extract(s.snapshot_json, '$.source_kind') != 'synthetic_demo_ocr_confirmed'
                         OR json_type(a.value, '$.extraction_id') IS NOT 'text'
                         OR json_type(a.value, '$.extraction_version') IS NOT 'integer'
                         OR json_extract(a.value, '$.extraction_version') < 1
                         OR json_type(a.value, '$.extraction_confirmed_at') IS NOT 'text'
                         OR json_type(a.value, '$.confirmed_values_sha256') IS NOT 'text'
                         OR NOT EXISTS (
                             SELECT 1
                             FROM document_extraction x
                             WHERE x.extraction_id = json_extract(a.value, '$.extraction_id')
                               AND x.document_id = json_extract(a.value, '$.document_id')
                               AND x.extraction_version = json_extract(a.value, '$.extraction_version')
                               AND x.is_confirmed = 1
                               AND x.extraction_status = 'CONFIRMED_BY_PATIENT'
                               AND x.template_id = 'CAI-DEMO-RESTING-CARDIAC-REPORT-V1'
                               AND x.document_sha256 = json_extract(
                                   a.value, '$.document_sha256_at_bind'
                               )
                               AND x.confirmed_at = json_extract(
                                   a.value, '$.extraction_confirmed_at'
                               )
                               AND x.confirmed_values_sha256 = json_extract(
                                   a.value, '$.confirmed_values_sha256'
                               )
                               AND x.confirmed_envelope_json IS NOT NULL
                         )
                     )
                 )
                 OR (
                     json_extract(a.value, '$.attachment_role') != 'OCR_SOURCE_REPORT'
                     AND (
                         json_type(a.value, '$.extraction_id') IS NOT 'null'
                         OR json_type(a.value, '$.extraction_version') IS NOT 'null'
                         OR json_type(a.value, '$.extraction_confirmed_at') IS NOT 'null'
                         OR json_type(a.value, '$.confirmed_values_sha256') IS NOT 'null'
                     )
                 )
          )"""

if BASE_ASSESSMENT_SCOPE_TRIGGER_DEFINITION.count(_SCOPE_ATTACHMENT_EMPTY_CHECK) != 1:
    raise RuntimeError("Migration 07 assessment scope trigger changed unexpectedly.")
ASSESSMENT_SCOPE_TRIGGER_DEFINITION = BASE_ASSESSMENT_SCOPE_TRIGGER_DEFINITION.replace(
    _SCOPE_ATTACHMENT_EMPTY_CHECK, _SCOPE_ATTACHMENT_INTEGRATED_CHECK
)


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

    # Replace the 07 assessment-scope guard after its referenced DOC tables
    # exist, and overlay the attempt guard with complete one-to-one binding-set
    # verification. Both exact 07 definitions are restored by downgrade.
    op.execute("DROP TRIGGER IF EXISTS tr_assessment_scope_insert")
    op.execute(ASSESSMENT_SCOPE_TRIGGER_DEFINITION)
    op.execute("DROP TRIGGER IF EXISTS tr_attempt_insert_guard")
    op.execute(ATTEMPT_INSERT_TRIGGER_DEFINITION)
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
    op.execute("DROP TRIGGER IF EXISTS tr_assessment_scope_insert")
    op.execute("DROP TRIGGER IF EXISTS tr_attempt_insert_guard")
    op.drop_table("document_inflight_operation")
    op.drop_table("assessment_document")
    op.drop_table("extraction_field")
    op.drop_table("extraction_event")
    op.drop_table("document_extraction")
    op.drop_table("medical_document")
    # Restore the exact pre-08 core scope and attempt guards for a valid
    # 08 -> 07 downgrade.
    op.execute(BASE_ASSESSMENT_SCOPE_TRIGGER_DEFINITION)
    op.execute(BASE_ATTEMPT_INSERT_TRIGGER_DEFINITION)
