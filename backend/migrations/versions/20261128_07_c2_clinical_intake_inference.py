"""C2.1 — core clinical intake and inference infrastructure.

Revision ID: 20261128_07
Revises: 20261126_06
Create Date: 2026-11-28

Authorized only by the owner grant ``AUTHORIZE-TERM1-C2-SAFE-SCOPE-V1`` at the
exact merged baseline ``5c96a2b9d5438b6600cf5eebebb70294fdeeadad`` bootstrapped
by ``5e763b055c51bd77e42b140642ce49a4d2524386`` (the verified append-only C2
workstream grant). Migrations ``20261017_01`` through ``20261126_06`` and their
data are byte-for-byte unchanged; this revision only appends the five C2 core
tables (schema-only, no seed/mock data) and their twelve immutability/consistency
triggers.

Tables (ERD of ``TERM1_C2_SCHEMA_AND_MIGRATION_SPEC_20261127`` §3):

* ``health_profile``            immutable versioned profile rows (``superseded_at``)
* ``assessment_snapshot``       one canonical snapshot envelope per assessment
* ``assessment``                submission record + C0 state/CAS pointers
* ``inference_attempt``         lease/generation/fencing record for all paths
* ``inference_result``          append-only result record (no rows until A3)

No inference adapter, artifact, mock or provider is created, referenced or
seeded by this migration; ``A1``/``A2``/``A3``/``B`` remain PENDING and
``inference_result`` stays empty under ``C2_SAFE_SCOPE``.

Downgrade preserves the RB-C1 policy of every C1 revision: refuse
``as_sql=True`` and refuse any database that still holds C1 **or C2** rows
(identical message family), before dropping a single trigger or table. On a
verified empty disposable database the guard passes and the DDL is removed in
reverse dependency order.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261128_07"
down_revision: Union[str, None] = "20261126_06"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Literal trigger statements: identical (whitespace-normalized) to
# backend/app/term1/triggers.py::C2_TRIGGER_DEFINITIONS, pinned by
# tests/backend/c2/test_c2_schema.py against a fresh upgrade's sqlite_master.
_TRIGGER_STATEMENTS: tuple[str, ...] = (
    """CREATE TRIGGER tr_health_profile_immutable_update
BEFORE UPDATE ON health_profile
FOR EACH ROW
WHEN OLD.superseded_at IS NOT NULL
  OR NEW.health_profile_id != OLD.health_profile_id
  OR NEW.patient_id != OLD.patient_id
  OR NEW.version_number != OLD.version_number
  OR NEW.panel_id != OLD.panel_id
  OR NEW.panel_version != OLD.panel_version
  OR NEW.schema_version != OLD.schema_version
  OR NEW.fields_json IS NOT OLD.fields_json
  OR NEW.provenance_json IS NOT OLD.provenance_json
  OR NEW.profile_sha256 != OLD.profile_sha256
  OR NEW.actor_user_id != OLD.actor_user_id
  OR NEW.created_at != OLD.created_at
  OR NEW.status != 'SUPERSEDED'
  OR NEW.superseded_at IS NULL
BEGIN
    SELECT RAISE(ABORT, 'health_profile_update_forbidden');
END;""",
    """CREATE TRIGGER tr_health_profile_no_delete
BEFORE DELETE ON health_profile
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'health_profile_delete_forbidden');
END;""",
    """CREATE TRIGGER tr_snapshot_no_update
BEFORE UPDATE ON assessment_snapshot
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'assessment_snapshot_update_forbidden');
END;""",
    """CREATE TRIGGER tr_snapshot_no_delete
BEFORE DELETE ON assessment_snapshot
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'assessment_snapshot_delete_forbidden');
END;""",
    """CREATE TRIGGER tr_assessment_scope_insert
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
END;""",
    """CREATE TRIGGER tr_assessment_pointer_insert
BEFORE INSERT ON assessment
FOR EACH ROW
WHEN NEW.status NOT IN ('DRAFT','INPUT_VALIDATED')
  OR NEW.reason_code IS NOT NULL
  OR NEW.active_attempt_id IS NOT NULL
  OR NEW.current_result_id IS NOT NULL
  OR NEW.current_generation != 0
  OR NEW.review_state != 'NOT_REVIEWED'
  OR NEW.review_version != 0
BEGIN
    SELECT RAISE(ABORT, 'assessment_pointer_invalid');
END;""",
    """CREATE TRIGGER tr_assessment_pointer_update
BEFORE UPDATE ON assessment
FOR EACH ROW
WHEN NEW.assessment_id != OLD.assessment_id
  OR NEW.patient_id != OLD.patient_id
  OR NEW.health_profile_id != OLD.health_profile_id
  OR NEW.snapshot_id != OLD.snapshot_id
  OR NEW.assignment_id != OLD.assignment_id
  OR NEW.consent_id != OLD.consent_id
  OR NEW.reassessment_of_id IS NOT OLD.reassessment_of_id
  OR NEW.reassessment_reason IS NOT OLD.reassessment_reason
  OR NEW.panel_id != OLD.panel_id
  OR NEW.panel_version != OLD.panel_version
  OR NEW.source_contract_version != OLD.source_contract_version
  OR NEW.source_kind != OLD.source_kind
  OR NEW.stage_complete != OLD.stage_complete
  OR NEW.current_generation < OLD.current_generation
  OR (NEW.active_attempt_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM inference_attempt a
        WHERE a.attempt_id = NEW.active_attempt_id
          AND a.assessment_id = NEW.assessment_id
          AND a.generation = NEW.current_generation
          AND a.state = 'INFERENCE_RUNNING'
    ))
  OR (NEW.current_result_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM inference_result r
        JOIN assessment_snapshot s ON s.snapshot_id = NEW.snapshot_id
        WHERE r.result_id = NEW.current_result_id
          AND r.assessment_id = NEW.assessment_id
          AND r.snapshot_id = NEW.snapshot_id
          AND r.generation = NEW.current_generation
          AND r.snapshot_sha256 = s.snapshot_sha256
          AND r.attempt_id = (
              SELECT a.attempt_id FROM inference_attempt a
              WHERE a.assessment_id = NEW.assessment_id
                AND a.generation = NEW.current_generation
          )
    ))
  OR NOT (
       (NEW.status = OLD.status
        AND NEW.reason_code IS OLD.reason_code
        AND NEW.active_attempt_id IS OLD.active_attempt_id
        AND NEW.current_generation = OLD.current_generation
        AND NEW.current_result_id IS OLD.current_result_id)
    OR (OLD.status = 'DRAFT' AND NEW.status = 'INPUT_VALIDATED'
        AND NEW.reason_code IS NULL
        AND NEW.active_attempt_id IS NULL
        AND NEW.current_generation = OLD.current_generation
        AND NEW.current_result_id IS NULL)
    OR (OLD.status = 'INPUT_VALIDATED' AND NEW.status = 'INFERENCE_RUNNING'
        AND NEW.reason_code IS NULL
        AND NEW.active_attempt_id IS NOT NULL
        AND NEW.current_generation = OLD.current_generation
        AND NEW.current_result_id IS NULL
        AND EXISTS (
            SELECT 1 FROM doctor_patient_assignment a
            WHERE a.assignment_id = NEW.assignment_id
              AND a.patient_id = NEW.patient_id AND a.revoked_at IS NULL
        )
        AND EXISTS (
            SELECT 1 FROM consent_record c
            WHERE c.consent_id = NEW.consent_id
              AND c.patient_id = NEW.patient_id AND c.revoked_at IS NULL
              AND c.kind = 'synthetic_demo'
              AND c.scope = 'patient_wide_synthetic_demo'
              AND c.contract_version = 'term1-c1-v1'
        ))
    OR (OLD.status = 'INFERENCE_RUNNING' AND NEW.status = 'INFERENCE_SUCCEEDED'
        AND NEW.reason_code IS NULL
        AND OLD.active_attempt_id IS NOT NULL
        AND NEW.active_attempt_id IS NULL
        AND NEW.current_generation = OLD.current_generation
        AND NEW.current_result_id IS NOT NULL
        AND EXISTS (
            SELECT 1 FROM inference_attempt a
            WHERE a.attempt_id = OLD.active_attempt_id
              AND a.assessment_id = OLD.assessment_id
              AND a.generation = OLD.current_generation
              AND a.state = 'INFERENCE_RUNNING'
              AND a.lease_until > NEW.updated_at
        )
        AND EXISTS (
            SELECT 1 FROM inference_result r
            JOIN assessment_snapshot s ON s.snapshot_id = NEW.snapshot_id
            WHERE r.result_id = NEW.current_result_id
              AND r.assessment_id = NEW.assessment_id
              AND r.attempt_id = OLD.active_attempt_id
              AND r.snapshot_id = NEW.snapshot_id
              AND r.generation = NEW.current_generation
              AND r.snapshot_sha256 = s.snapshot_sha256
              AND r.schema_version = 'term1.c2.result/v1'
              AND r.panel_id = NEW.panel_id
              AND r.panel_version = NEW.panel_version
              AND r.panel_contract_sha256 = s.panel_contract_sha256
              AND r.source_contract_version = NEW.source_contract_version
              AND r.source_kind = NEW.source_kind
        )
        AND EXISTS (
            SELECT 1 FROM doctor_patient_assignment a
            WHERE a.assignment_id = NEW.assignment_id
              AND a.patient_id = NEW.patient_id AND a.revoked_at IS NULL
        )
        AND EXISTS (
            SELECT 1 FROM consent_record c
            WHERE c.consent_id = NEW.consent_id
              AND c.patient_id = NEW.patient_id AND c.revoked_at IS NULL
              AND c.kind = 'synthetic_demo'
              AND c.scope = 'patient_wide_synthetic_demo'
              AND c.contract_version = 'term1-c1-v1'
        ))
    OR (OLD.status = 'INFERENCE_RUNNING'
        AND NEW.status IN ('INFERENCE_ABSTAINED','INFERENCE_UNAVAILABLE','INFERENCE_ERROR')
        AND OLD.active_attempt_id IS NOT NULL
        AND NEW.active_attempt_id IS NULL
        AND NEW.current_result_id IS NULL
        AND EXISTS (
            SELECT 1 FROM inference_attempt a
            WHERE a.attempt_id = OLD.active_attempt_id
              AND a.assessment_id = OLD.assessment_id
              AND a.generation = OLD.current_generation
              AND a.state = 'INFERENCE_RUNNING'
              AND a.lease_until > NEW.updated_at
        )
        AND NEW.current_generation = OLD.current_generation
        AND (
             (NEW.status = 'INFERENCE_UNAVAILABLE'
              AND ((NEW.reason_code = 'real_ai_not_authorized'
                    AND EXISTS (
                        SELECT 1 FROM doctor_patient_assignment a
                        WHERE a.assignment_id = NEW.assignment_id
                          AND a.patient_id = NEW.patient_id AND a.revoked_at IS NULL
                    )
                    AND EXISTS (
                        SELECT 1 FROM consent_record c
                        WHERE c.consent_id = NEW.consent_id
                          AND c.patient_id = NEW.patient_id AND c.revoked_at IS NULL
                          AND c.kind = 'synthetic_demo'
                          AND c.scope = 'patient_wide_synthetic_demo'
                          AND c.contract_version = 'term1-c1-v1'
                    ))
                   OR (NEW.reason_code = 'authorization_withdrawn'
                    AND (NOT EXISTS (
                        SELECT 1 FROM doctor_patient_assignment a
                        WHERE a.assignment_id = NEW.assignment_id
                          AND a.patient_id = NEW.patient_id AND a.revoked_at IS NULL
                    ) OR NOT EXISTS (
                        SELECT 1 FROM consent_record c
                        WHERE c.consent_id = NEW.consent_id
                          AND c.patient_id = NEW.patient_id AND c.revoked_at IS NULL
                          AND c.kind = 'synthetic_demo'
                          AND c.scope = 'patient_wide_synthetic_demo'
                          AND c.contract_version = 'term1-c1-v1'
                    ))))
          OR (NEW.status = 'INFERENCE_ABSTAINED'
              AND NEW.reason_code = 'optional_panel_field_missing'
              AND NEW.stage_complete = 0
              AND EXISTS (
                    SELECT 1 FROM doctor_patient_assignment a
                    WHERE a.assignment_id = NEW.assignment_id
                      AND a.patient_id = NEW.patient_id AND a.revoked_at IS NULL
              )
              AND EXISTS (
                    SELECT 1 FROM consent_record c
                    WHERE c.consent_id = NEW.consent_id
                      AND c.patient_id = NEW.patient_id AND c.revoked_at IS NULL
                      AND c.kind = 'synthetic_demo'
                      AND c.scope = 'patient_wide_synthetic_demo'
                      AND c.contract_version = 'term1-c1-v1'
              ))
          OR (NEW.status = 'INFERENCE_ERROR'
              AND NEW.reason_code IN ('worker_error','malformed_worker_response',
                                      'artifact_integrity_failed')
              AND EXISTS (
                    SELECT 1 FROM doctor_patient_assignment a
                    WHERE a.assignment_id = NEW.assignment_id
                      AND a.patient_id = NEW.patient_id AND a.revoked_at IS NULL
              )
              AND EXISTS (
                    SELECT 1 FROM consent_record c
                    WHERE c.consent_id = NEW.consent_id
                      AND c.patient_id = NEW.patient_id AND c.revoked_at IS NULL
                      AND c.kind = 'synthetic_demo'
                      AND c.scope = 'patient_wide_synthetic_demo'
                      AND c.contract_version = 'term1-c1-v1'
              ))
        )))
    OR (OLD.status = 'INFERENCE_RUNNING'
        AND NEW.status IN ('INFERENCE_ERROR','INFERENCE_UNAVAILABLE')
        AND NEW.current_generation = OLD.current_generation + 1
        AND OLD.active_attempt_id IS NOT NULL
        AND NEW.active_attempt_id IS NULL
        AND NEW.current_result_id IS NULL
        AND EXISTS (
            SELECT 1 FROM inference_attempt a
            WHERE a.attempt_id = OLD.active_attempt_id
              AND a.assessment_id = OLD.assessment_id
              AND a.generation = OLD.current_generation
              AND a.state = 'INFERENCE_RUNNING'
              AND a.lease_until <= NEW.updated_at
        )
        AND ((NEW.status = 'INFERENCE_ERROR'
              AND NEW.reason_code = 'lease_expired'
              AND EXISTS (
                    SELECT 1 FROM doctor_patient_assignment a
                    WHERE a.assignment_id = NEW.assignment_id
                      AND a.patient_id = NEW.patient_id AND a.revoked_at IS NULL
              )
              AND EXISTS (
                    SELECT 1 FROM consent_record c
                    WHERE c.consent_id = NEW.consent_id
                      AND c.patient_id = NEW.patient_id AND c.revoked_at IS NULL
                      AND c.kind = 'synthetic_demo'
                      AND c.scope = 'patient_wide_synthetic_demo'
                      AND c.contract_version = 'term1-c1-v1'
              ))
          OR (NEW.status = 'INFERENCE_UNAVAILABLE'
              AND NEW.reason_code = 'authorization_withdrawn'
              AND (NOT EXISTS (
                    SELECT 1 FROM doctor_patient_assignment a
                    WHERE a.assignment_id = NEW.assignment_id
                      AND a.patient_id = NEW.patient_id AND a.revoked_at IS NULL
              ) OR NOT EXISTS (
                    SELECT 1 FROM consent_record c
                    WHERE c.consent_id = NEW.consent_id
                      AND c.patient_id = NEW.patient_id AND c.revoked_at IS NULL
                      AND c.kind = 'synthetic_demo'
                      AND c.scope = 'patient_wide_synthetic_demo'
                      AND c.contract_version = 'term1-c1-v1'
              )))))
    OR (OLD.status = 'INFERENCE_SUCCEEDED' AND NEW.status = 'PENDING_REVIEW'
        AND NEW.reason_code IS NULL
        AND NEW.active_attempt_id IS NULL
        AND NEW.current_generation = OLD.current_generation
        AND NEW.current_result_id IS OLD.current_result_id
        AND NEW.current_result_id IS NOT NULL
        AND EXISTS (
            SELECT 1 FROM inference_result r
            JOIN inference_attempt a
              ON a.assessment_id = r.assessment_id
             AND a.attempt_id = r.attempt_id
             AND a.generation = r.generation
            WHERE r.result_id = NEW.current_result_id
              AND r.assessment_id = NEW.assessment_id
              AND r.snapshot_id = NEW.snapshot_id
              AND r.generation = NEW.current_generation
              AND a.state = 'INFERENCE_SUCCEEDED'
        ))
    OR (OLD.status = 'INFERENCE_ERROR' AND NEW.status = 'INPUT_VALIDATED'
        AND NEW.reason_code IS NULL
        AND NEW.active_attempt_id IS NULL
        AND NEW.current_result_id IS NULL
        AND ((OLD.reason_code = 'lease_expired'
              AND NEW.current_generation = OLD.current_generation)
          OR (OLD.reason_code IN ('worker_error','malformed_worker_response',
                                  'artifact_integrity_failed')
              AND NEW.current_generation = OLD.current_generation + 1))
        AND EXISTS (
            SELECT 1 FROM doctor_patient_assignment a
            WHERE a.assignment_id = NEW.assignment_id
              AND a.patient_id = NEW.patient_id AND a.revoked_at IS NULL
        )
        AND EXISTS (
            SELECT 1 FROM consent_record c
            WHERE c.consent_id = NEW.consent_id
              AND c.patient_id = NEW.patient_id AND c.revoked_at IS NULL
              AND c.kind = 'synthetic_demo'
              AND c.scope = 'patient_wide_synthetic_demo'
              AND c.contract_version = 'term1-c1-v1'
        )))
BEGIN
    SELECT RAISE(ABORT, 'assessment_pointer_update_forbidden');
END;""",
    """CREATE TRIGGER tr_assessment_no_delete
BEFORE DELETE ON assessment
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'assessment_delete_forbidden');
END;""",
    """CREATE TRIGGER tr_attempt_transition_guard
BEFORE UPDATE ON inference_attempt
FOR EACH ROW
WHEN OLD.state != 'INFERENCE_RUNNING'
  OR NEW.attempt_id != OLD.attempt_id
  OR NEW.assessment_id != OLD.assessment_id
  OR NEW.generation != OLD.generation
  OR NEW.attempt_idempotency_hash != OLD.attempt_idempotency_hash
  OR NEW.worker_id != OLD.worker_id
  OR NEW.fence_token != OLD.fence_token
  OR NEW.leased_at != OLD.leased_at
  OR NEW.lease_until != OLD.lease_until
  OR (NEW.state != 'INFERENCE_RUNNING' AND EXISTS (
        SELECT 1 FROM assessment s WHERE s.active_attempt_id = OLD.attempt_id
    ))
  OR NEW.state = 'INFERENCE_RUNNING'
  OR NEW.completed_at IS NULL
  OR NEW.completed_at < OLD.leased_at
  OR NOT (
       (NEW.state = 'INFERENCE_SUCCEEDED'
        AND NEW.reason_code IS NULL
        AND EXISTS (
            SELECT 1 FROM assessment s
            JOIN inference_result r ON r.result_id = s.current_result_id
            WHERE s.assessment_id = OLD.assessment_id
              AND s.status IN ('INFERENCE_SUCCEEDED','PENDING_REVIEW')
              AND s.active_attempt_id IS NULL
              AND s.current_generation = OLD.generation
              AND NEW.completed_at < OLD.lease_until
              AND r.assessment_id = OLD.assessment_id
              AND r.attempt_id = OLD.attempt_id
              AND r.generation = OLD.generation
              AND r.snapshot_id = s.snapshot_id
        ))
    OR (NEW.state IN ('INFERENCE_ABSTAINED','INFERENCE_UNAVAILABLE','INFERENCE_ERROR')
        AND NEW.reason_code IS NOT NULL
        AND EXISTS (
            SELECT 1 FROM assessment s
            WHERE s.assessment_id = OLD.assessment_id
              AND s.status = NEW.state
              AND s.reason_code = NEW.reason_code
              AND s.active_attempt_id IS NULL
              AND s.current_result_id IS NULL
              AND (NEW.state != 'INFERENCE_ABSTAINED' OR s.stage_complete = 0)
              AND ((s.current_generation = OLD.generation
                    AND NEW.completed_at < OLD.lease_until)
                OR (s.current_generation = OLD.generation + 1
                    AND NEW.completed_at >= OLD.lease_until
                    AND NEW.reason_code IN ('lease_expired','authorization_withdrawn')
                    AND NEW.state IN ('INFERENCE_ERROR','INFERENCE_UNAVAILABLE')))
        )
        AND ((NEW.state = 'INFERENCE_ABSTAINED'
              AND NEW.reason_code = 'optional_panel_field_missing')
          OR (NEW.state = 'INFERENCE_UNAVAILABLE'
              AND NEW.reason_code IN ('real_ai_not_authorized','authorization_withdrawn'))
          OR (NEW.state = 'INFERENCE_ERROR'
              AND NEW.reason_code IN ('lease_expired','worker_error',
                                      'malformed_worker_response',
                                      'artifact_integrity_failed'))))
    )
BEGIN
    SELECT RAISE(ABORT, 'inference_attempt_update_forbidden');
END;""",
    """CREATE TRIGGER tr_attempt_no_delete
BEFORE DELETE ON inference_attempt
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'inference_attempt_delete_forbidden');
END;""",
    """CREATE TRIGGER tr_result_no_update
BEFORE UPDATE ON inference_result
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'inference_result_update_forbidden');
END;""",
    """CREATE TRIGGER tr_result_no_delete
BEFORE DELETE ON inference_result
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'inference_result_delete_forbidden');
END;""",
)


def upgrade() -> None:
    connection = op.get_bind()

    op.create_table(
        "health_profile",
        sa.Column("health_profile_id", sa.String(length=36), nullable=False),
        sa.Column("patient_id", sa.String(length=36), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("superseded_at", sa.String(length=32), nullable=True),
        sa.Column("panel_id", sa.String(length=64), nullable=False),
        sa.Column("panel_version", sa.String(length=16), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("fields_json", sa.JSON(), nullable=False),
        sa.Column("provenance_json", sa.JSON(), nullable=False),
        sa.Column("profile_sha256", sa.String(length=64), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patient_profile.patient_id"],
            ondelete="RESTRICT",
            name="fk_health_profile_patient",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["user_account.user_id"],
            ondelete="RESTRICT",
            name="fk_health_profile_actor",
        ),
        sa.PrimaryKeyConstraint("health_profile_id"),
        sa.CheckConstraint("version_number >= 1", name="ck_health_profile_version"),
        sa.UniqueConstraint(
            "patient_id", "version_number", name="ux_health_profile_patient_version"
        ),
        sa.UniqueConstraint(
            "health_profile_id", "patient_id", name="ux_health_profile_id_patient"
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','COMPLETE','SUPERSEDED')", name="ck_health_profile_status"
        ),
        sa.CheckConstraint(
            "(status = 'SUPERSEDED' AND superseded_at IS NOT NULL) "
            "OR (status IN ('DRAFT','COMPLETE') AND superseded_at IS NULL)",
            name="ck_health_profile_supersession",
        ),
    )
    op.create_index(
        "ux_health_profile_one_active",
        "health_profile",
        ["patient_id"],
        unique=True,
        sqlite_where=sa.text("superseded_at IS NULL"),
    )

    op.create_table(
        "assessment_snapshot",
        sa.Column("snapshot_id", sa.String(length=36), nullable=False),
        sa.Column("patient_id", sa.String(length=36), nullable=False),
        sa.Column("health_profile_id", sa.String(length=36), nullable=False),
        sa.Column("panel_id", sa.String(length=64), nullable=False),
        sa.Column("panel_version", sa.String(length=16), nullable=False),
        sa.Column("panel_contract_sha256", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("schema_sha256", sa.String(length=64), nullable=False),
        sa.Column("source_contract_version", sa.String(length=32), nullable=False),
        sa.Column("source_kind", sa.String(length=48), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("snapshot_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patient_profile.patient_id"],
            ondelete="RESTRICT",
            name="fk_assessment_snapshot_patient",
        ),
        sa.ForeignKeyConstraint(
            ["health_profile_id", "patient_id"],
            ["health_profile.health_profile_id", "health_profile.patient_id"],
            ondelete="RESTRICT",
            name="fk_assessment_snapshot_profile",
        ),
        sa.PrimaryKeyConstraint("snapshot_id"),
        sa.UniqueConstraint("snapshot_id", "patient_id", name="ux_snapshot_id_patient"),
        sa.UniqueConstraint(
            "snapshot_id", "health_profile_id", "patient_id",
            name="ux_snapshot_id_profile_patient",
        ),
        sa.CheckConstraint(
            "source_kind IN ('synthetic_demo_patient_manual','synthetic_demo_ocr_confirmed')",
            name="ck_snapshot_source_kind",
        ),
        sa.CheckConstraint("json_valid(snapshot_json)", name="ck_snapshot_json_valid"),
        sa.CheckConstraint(
            "panel_id = 'da_a2_resting_v1' AND panel_version = '1.0.0' "
            "AND panel_contract_sha256 = "
            "'c18ad4cd2cf08f6fefb2e340573760da7000bc1d8eb4ad38783b873c018e57b8' "
            "AND schema_version = 'term1.c2.snapshot/v1' "
            "AND source_contract_version = 'term1.c2.intake/v1'",
            name="ck_snapshot_contract_identity",
        ),
    )

    op.create_table(
        "assessment",
        sa.Column("assessment_id", sa.String(length=36), nullable=False),
        sa.Column("patient_id", sa.String(length=36), nullable=False),
        sa.Column("health_profile_id", sa.String(length=36), nullable=False),
        sa.Column("snapshot_id", sa.String(length=36), nullable=False),
        sa.Column("assignment_id", sa.String(length=36), nullable=False),
        sa.Column("consent_id", sa.String(length=36), nullable=False),
        sa.Column("reassessment_of_id", sa.String(length=36), nullable=True),
        sa.Column("reassessment_reason", sa.String(length=128), nullable=True),
        sa.Column("panel_id", sa.String(length=64), nullable=False),
        sa.Column("panel_version", sa.String(length=16), nullable=False),
        sa.Column("source_contract_version", sa.String(length=32), nullable=False),
        sa.Column("source_kind", sa.String(length=48), nullable=False),
        sa.Column("stage_complete", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=36), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=True),
        sa.Column("active_attempt_id", sa.String(length=36), nullable=True),
        sa.Column("current_generation", sa.Integer(), nullable=False),
        sa.Column("current_result_id", sa.String(length=36), nullable=True),
        sa.Column("review_state", sa.String(length=32), nullable=False),
        sa.Column("review_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patient_profile.patient_id"],
            ondelete="RESTRICT",
            name="fk_assessment_patient",
        ),
        sa.ForeignKeyConstraint(
            ["health_profile_id", "patient_id"],
            ["health_profile.health_profile_id", "health_profile.patient_id"],
            ondelete="RESTRICT",
            name="fk_assessment_health_profile",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id", "health_profile_id", "patient_id"],
            [
                "assessment_snapshot.snapshot_id",
                "assessment_snapshot.health_profile_id",
                "assessment_snapshot.patient_id",
            ],
            ondelete="RESTRICT",
            name="fk_assessment_snapshot_profile_patient",
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id"],
            ["doctor_patient_assignment.assignment_id"],
            ondelete="RESTRICT",
            name="fk_assessment_assignment",
        ),
        sa.ForeignKeyConstraint(
            ["consent_id"],
            ["consent_record.consent_id"],
            ondelete="RESTRICT",
            name="fk_assessment_consent",
        ),
        sa.ForeignKeyConstraint(
            ["reassessment_of_id"],
            ["assessment.assessment_id"],
            ondelete="RESTRICT",
            name="fk_assessment_reassessment",
        ),
        sa.PrimaryKeyConstraint("assessment_id"),
        sa.UniqueConstraint(
            "assessment_id", "assignment_id", name="ux_assessment_id_assignment"
        ),
        sa.UniqueConstraint("assessment_id", "patient_id", name="ux_assessment_id_patient"),
        sa.UniqueConstraint("assessment_id", "snapshot_id", name="ux_assessment_id_snapshot"),
        sa.UniqueConstraint("snapshot_id", name="ux_assessment_snapshot_id"),
        sa.UniqueConstraint("active_attempt_id", name="ux_assessment_active_attempt"),
        sa.UniqueConstraint("current_result_id", name="ux_assessment_current_result"),
        sa.CheckConstraint(
            "(reassessment_of_id IS NULL AND reassessment_reason IS NULL) OR "
            "(reassessment_of_id IS NOT NULL AND reassessment_reason IS NOT NULL)",
            name="ck_assessment_reassessment_pair",
        ),
        sa.CheckConstraint(
            "panel_id = 'da_a2_resting_v1' AND panel_version = '1.0.0' "
            "AND source_contract_version = 'term1.c2.intake/v1' "
            "AND source_kind IN ('synthetic_demo_patient_manual',"
            "'synthetic_demo_ocr_confirmed')",
            name="ck_assessment_contract_identity",
        ),
        sa.CheckConstraint("current_generation >= 0", name="ck_assessment_generation"),
        sa.CheckConstraint("review_version >= 0", name="ck_assessment_review_version"),
        sa.CheckConstraint(
            "status IN ('DRAFT','INPUT_VALIDATED','INFERENCE_RUNNING',"
            "'INFERENCE_SUCCEEDED','PENDING_REVIEW','INFERENCE_ABSTAINED',"
            "'INFERENCE_UNAVAILABLE','INFERENCE_ERROR')",
            name="ck_assessment_status",
        ),
        sa.CheckConstraint(
            "((status = 'INFERENCE_ABSTAINED' "
            "AND reason_code = 'optional_panel_field_missing' "
            "AND stage_complete = 0) OR "
            "(status = 'INFERENCE_UNAVAILABLE' "
            "AND reason_code IN ('real_ai_not_authorized','authorization_withdrawn')) OR "
            "(status = 'INFERENCE_ERROR' "
            "AND reason_code IN ('lease_expired','worker_error',"
            "'malformed_worker_response','artifact_integrity_failed')) OR "
            "(status NOT IN ('INFERENCE_ABSTAINED','INFERENCE_UNAVAILABLE','INFERENCE_ERROR') "
            "AND reason_code IS NULL))",
            name="ck_assessment_status_reason",
        ),
        sa.CheckConstraint(
            "((status = 'INFERENCE_RUNNING' AND active_attempt_id IS NOT NULL "
            "AND current_result_id IS NULL) OR "
            "(status IN ('INFERENCE_SUCCEEDED','PENDING_REVIEW') "
            "AND active_attempt_id IS NULL AND current_result_id IS NOT NULL) OR "
            "(status IN ('DRAFT','INPUT_VALIDATED','INFERENCE_ABSTAINED',"
            "'INFERENCE_UNAVAILABLE','INFERENCE_ERROR') "
            "AND active_attempt_id IS NULL AND current_result_id IS NULL))",
            name="ck_assessment_pointer",
        ),
    )
    op.create_index(
        "ix_assessment_patient_created", "assessment", ["patient_id", "created_at"]
    )
    op.create_index(
        "ix_assessment_assignment_status", "assessment", ["assignment_id", "status"]
    )
    op.create_index("ix_assessment_current_result", "assessment", ["current_result_id"])

    op.create_table(
        "inference_attempt",
        sa.Column("attempt_id", sa.String(length=36), nullable=False),
        sa.Column("assessment_id", sa.String(length=36), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("attempt_idempotency_hash", sa.String(length=64), nullable=False),
        sa.Column("worker_id", sa.String(length=64), nullable=False),
        sa.Column("fence_token", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=36), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=True),
        sa.Column("leased_at", sa.String(length=32), nullable=False),
        sa.Column("lease_until", sa.String(length=32), nullable=False),
        sa.Column("completed_at", sa.String(length=32), nullable=True),
        sa.ForeignKeyConstraint(
            ["assessment_id"],
            ["assessment.assessment_id"],
            ondelete="RESTRICT",
            name="fk_inference_attempt_assessment",
        ),
        sa.PrimaryKeyConstraint("attempt_id"),
        sa.CheckConstraint("generation >= 0", name="ck_inference_attempt_generation"),
        sa.CheckConstraint("lease_until > leased_at", name="ck_inference_attempt_lease_order"),
        sa.CheckConstraint(
            "state IN ('INFERENCE_RUNNING','INFERENCE_SUCCEEDED','INFERENCE_ABSTAINED',"
            "'INFERENCE_UNAVAILABLE','INFERENCE_ERROR')",
            name="ck_inference_attempt_state",
        ),
        sa.CheckConstraint(
            "(state = 'INFERENCE_RUNNING' AND reason_code IS NULL AND completed_at IS NULL) "
            "OR (state = 'INFERENCE_SUCCEEDED' AND reason_code IS NULL "
            "AND completed_at IS NOT NULL) "
            "OR (state = 'INFERENCE_ABSTAINED' "
            "AND reason_code = 'optional_panel_field_missing' "
            "AND completed_at IS NOT NULL) "
            "OR (state = 'INFERENCE_UNAVAILABLE' "
            "AND reason_code IN ('real_ai_not_authorized','authorization_withdrawn') "
            "AND completed_at IS NOT NULL) "
            "OR (state = 'INFERENCE_ERROR' "
            "AND reason_code IN ('lease_expired','worker_error',"
            "'malformed_worker_response','artifact_integrity_failed') "
            "AND completed_at IS NOT NULL)",
            name="ck_inference_attempt_state_reason",
        ),
        sa.UniqueConstraint(
            "assessment_id", "generation", name="ux_inference_attempt_assessment_gen"
        ),
        sa.UniqueConstraint(
            "assessment_id",
            "attempt_idempotency_hash",
            name="ux_inference_attempt_idempotency",
        ),
        sa.UniqueConstraint(
            "assessment_id",
            "attempt_id",
            "generation",
            name="ux_inference_attempt_id_gen_pair",
        ),
    )
    op.create_index(
        "ux_inference_attempt_one_active",
        "inference_attempt",
        ["assessment_id"],
        unique=True,
        sqlite_where=sa.text("state = 'INFERENCE_RUNNING'"),
    )
    op.create_index(
        "ix_inference_attempt_assessment_state",
        "inference_attempt",
        ["assessment_id", "state"],
    )

    op.create_table(
        "inference_result",
        sa.Column("result_id", sa.String(length=36), nullable=False),
        sa.Column("assessment_id", sa.String(length=36), nullable=False),
        sa.Column("attempt_id", sa.String(length=36), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.String(length=36), nullable=False),
        sa.Column("snapshot_sha256", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("panel_id", sa.String(length=64), nullable=False),
        sa.Column("panel_version", sa.String(length=16), nullable=False),
        sa.Column("panel_contract_sha256", sa.String(length=64), nullable=False),
        sa.Column("source_contract_version", sa.String(length=32), nullable=False),
        sa.Column("source_kind", sa.String(length=48), nullable=False),
        sa.Column("model_id", sa.String(length=64), nullable=False),
        sa.Column("model_version", sa.String(length=32), nullable=False),
        sa.Column("protocol_id", sa.String(length=64), nullable=False),
        sa.Column("execution_profile", sa.String(length=48), nullable=False),
        sa.Column("bundle_dir_name", sa.String(length=128), nullable=False),
        sa.Column("manifest_sha256", sa.String(length=64), nullable=False),
        sa.Column("source_sha256", sa.String(length=64), nullable=False),
        sa.Column("model_joblib_sha256", sa.String(length=64), nullable=False),
        sa.Column("preprocessing_json_sha256", sa.String(length=64), nullable=False),
        sa.Column("calibration_json_sha256", sa.String(length=64), nullable=False),
        sa.Column("shap_background_sha256", sa.String(length=64), nullable=False),
        sa.Column("evaluation_summary_sha256", sa.String(length=64), nullable=False),
        sa.Column("protocol_md_sha256", sa.String(length=64), nullable=False),
        sa.Column("serving_eligibility", sa.String(length=32), nullable=False),
        sa.Column("clinical_use_authorized", sa.Boolean(), nullable=False),
        sa.Column("raw_model_score", sa.Float(), nullable=False),
        sa.Column("raw_model_log_odds", sa.Float(), nullable=True),
        sa.Column("calibrated_research_score", sa.Float(), nullable=False),
        sa.Column("calibrated_log_odds", sa.Float(), nullable=False),
        sa.Column("calibration_meta_json", sa.JSON(), nullable=False),
        sa.Column("shap_json", sa.JSON(), nullable=False),
        sa.Column("lime_status", sa.String(length=32), nullable=False),
        sa.Column("lime_json", sa.JSON(), nullable=True),
        sa.Column("lime_meta_json", sa.JSON(), nullable=False),
        sa.Column("fold_dispersion_json", sa.JSON(), nullable=False),
        sa.Column("limitations_json", sa.JSON(), nullable=False),
        sa.Column("result_sha256", sa.String(length=64), nullable=False),
        sa.Column("published_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["assessment_id", "snapshot_id"],
            ["assessment.assessment_id", "assessment.snapshot_id"],
            ondelete="RESTRICT",
            name="fk_inference_result_assessment",
        ),
        sa.ForeignKeyConstraint(
            ["assessment_id", "attempt_id", "generation"],
            ["inference_attempt.assessment_id", "inference_attempt.attempt_id",
             "inference_attempt.generation"],
            ondelete="RESTRICT",
            name="fk_inference_result_attempt",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["assessment_snapshot.snapshot_id"],
            ondelete="RESTRICT",
            name="fk_inference_result_snapshot",
        ),
        sa.PrimaryKeyConstraint("result_id"),
        sa.CheckConstraint("generation >= 0", name="ck_inference_result_generation"),
        sa.UniqueConstraint("attempt_id", name="ux_inference_result_attempt"),
        sa.UniqueConstraint(
            "assessment_id", "snapshot_id", "result_id",
            name="ux_inference_result_ass_snap_res",
        ),
        sa.CheckConstraint(
            "serving_eligibility = 'RESEARCH_ONLY'",
            name="ck_inference_result_serving_eligibility",
        ),
        sa.CheckConstraint(
            "clinical_use_authorized = 0",
            name="ck_inference_result_clinical_use",
        ),
    )

    for statement in _TRIGGER_STATEMENTS:
        op.execute(statement)

    # The C2 schema must satisfy SQLite's own integrity checks immediately.
    integrity = connection.exec_driver_sql("PRAGMA integrity_check").scalar()
    if integrity != "ok":
        raise RuntimeError(f"Migration 07 integrity check failed: {integrity}")
    fk_issues = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
    if fk_issues:
        raise RuntimeError("Migration 07 foreign key check failed.")


def downgrade() -> None:
    # RB-C1: never generate offline DDL or erase persisted C1/C2 state. The
    # guard covers the original C1 sixteen tables plus the five tables this
    # revision owns, and runs before the first DROP TRIGGER / DROP TABLE.
    if op.get_context().as_sql:
        raise RuntimeError(
            "C1 downgrade requires online verification of an unbound disposable database."
        )
    connection = op.get_bind()
    guarded_tables = (
        "user_account", "doctor_profile", "patient_identity", "patient_profile",
        "identity_key_check", "session", "login_attempt", "verified_visit",
        "patient_invitation", "invitation_attempt", "doctor_patient_assignment",
        "consent_record", "invitation_redemption", "durable_idempotency",
        "workflow_audit_event", "admin_bootstrap_record",
        "health_profile", "assessment_snapshot", "assessment",
        "inference_attempt", "inference_result",
    )
    # All names are fixed migration-owned identifiers, not user input.
    for table in guarded_tables:
        if connection.execute(sa.text(f'SELECT 1 FROM "{table}" LIMIT 1')).first() is not None:
            raise RuntimeError(
                "C1 downgrade refused: persisted C1 state is present. "
                "Use an independently verified backup for operational rollback; "
                "in-place downgrade is supported only on disposable databases "
                "without C1 state."
            )

    for name in (
        "tr_health_profile_immutable_update",
        "tr_health_profile_no_delete",
        "tr_snapshot_no_update",
        "tr_snapshot_no_delete",
        "tr_assessment_scope_insert",
        "tr_assessment_pointer_insert",
        "tr_assessment_pointer_update",
        "tr_assessment_no_delete",
        "tr_attempt_transition_guard",
        "tr_attempt_no_delete",
        "tr_result_no_update",
        "tr_result_no_delete",
    ):
        op.execute(f'DROP TRIGGER IF EXISTS "{name}"')

    # Reverse dependency order (children before parents).
    op.drop_table("inference_result")
    op.drop_table("inference_attempt")
    op.drop_table("assessment")
    op.drop_table("assessment_snapshot")
    op.drop_table("health_profile")
