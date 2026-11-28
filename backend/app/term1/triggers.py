"""Frozen DDL for the C2 core immutability/consistency triggers (07).

These strings are the authoritative expected definitions consumed by
``backend.app.storage.database.Database.verify_schema()`` on startup: every
trigger below must exist in ``sqlite_master`` with matching
whitespace-normalized SQL, and verification fails closed when one is missing or
modified. Migration ``20261128_07_c2_clinical_intake_inference`` creates the
same statements literally; ``tests/backend/c2/test_c2_schema.py`` pins the
fresh-upgrade ``sqlite_master`` output against this dictionary so the two can
never drift.

Track 2 appends its ``20261128_08`` trigger definitions to this dictionary at
integration time (Track 1 owns this file). Scope is exactly the twelve triggers
of migration 07; nothing here is executed by this module itself.
"""

from __future__ import annotations


def normalize_trigger_sql(sql: str) -> str:
    """Canonical comparison form for trigger DDL.

    Whitespace is collapsed to single spaces and exactly one trailing
    semicolon is removed, because ``sqlite_master.sql`` omits the final ``;``
    of the ``CREATE TRIGGER`` statement while the source definitions keep it.
    """
    collapsed = " ".join(sql.split())
    if collapsed.endswith(";"):
        collapsed = collapsed[:-1]
    return collapsed


C2_TRIGGER_DEFINITIONS: dict[str, str] = {
    # ---------------------------------------------------------------- health_profile
    "tr_health_profile_immutable_update": """CREATE TRIGGER tr_health_profile_immutable_update
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
    "tr_health_profile_no_delete": """CREATE TRIGGER tr_health_profile_no_delete
BEFORE DELETE ON health_profile
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'health_profile_delete_forbidden');
END;""",
    # ------------------------------------------------------------ assessment_snapshot
    "tr_snapshot_no_update": """CREATE TRIGGER tr_snapshot_no_update
BEFORE UPDATE ON assessment_snapshot
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'assessment_snapshot_update_forbidden');
END;""",
    "tr_snapshot_no_delete": """CREATE TRIGGER tr_snapshot_no_delete
BEFORE DELETE ON assessment_snapshot
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'assessment_snapshot_delete_forbidden');
END;""",
    # -------------------------------------------------------------------- assessment
    "tr_assessment_scope_insert": """CREATE TRIGGER tr_assessment_scope_insert
BEFORE INSERT ON assessment
FOR EACH ROW
WHEN NOT EXISTS (
        SELECT 1 FROM doctor_patient_assignment a
        WHERE a.assignment_id = NEW.assignment_id
          AND a.patient_id = NEW.patient_id
    )
    OR NOT EXISTS (
        SELECT 1 FROM consent_record c
        WHERE c.consent_id = NEW.consent_id
          AND c.patient_id = NEW.patient_id
    )
    OR (NEW.reassessment_of_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM assessment p
        WHERE p.assessment_id = NEW.reassessment_of_id
          AND p.patient_id = NEW.patient_id
          AND p.assignment_id = NEW.assignment_id
    ))
BEGIN
    SELECT RAISE(ABORT, 'assessment_scope_invalid');
END;""",
    "tr_assessment_pointer_insert": """CREATE TRIGGER tr_assessment_pointer_insert
BEFORE INSERT ON assessment
FOR EACH ROW
WHEN (NEW.active_attempt_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM inference_attempt a
        WHERE a.attempt_id = NEW.active_attempt_id
          AND a.assessment_id = NEW.assessment_id
          AND a.generation = NEW.current_generation
          AND a.state = 'INFERENCE_RUNNING'
    ))
    OR (NEW.current_result_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM inference_result r
        WHERE r.result_id = NEW.current_result_id
          AND r.assessment_id = NEW.assessment_id
          AND r.snapshot_id = NEW.snapshot_id
          AND r.generation = NEW.current_generation
    ))
BEGIN
    SELECT RAISE(ABORT, 'assessment_pointer_invalid');
END;""",
    "tr_assessment_pointer_update": """CREATE TRIGGER tr_assessment_pointer_update
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
        WHERE r.result_id = NEW.current_result_id
          AND r.assessment_id = NEW.assessment_id
          AND r.snapshot_id = NEW.snapshot_id
          AND r.generation = NEW.current_generation
    ))
BEGIN
    SELECT RAISE(ABORT, 'assessment_pointer_update_forbidden');
END;""",
    "tr_assessment_no_delete": """CREATE TRIGGER tr_assessment_no_delete
BEFORE DELETE ON assessment
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'assessment_delete_forbidden');
END;""",
    # ------------------------------------------------------------- inference_attempt
    "tr_attempt_transition_guard": """CREATE TRIGGER tr_attempt_transition_guard
BEFORE UPDATE ON inference_attempt
FOR EACH ROW
WHEN OLD.state != 'INFERENCE_RUNNING'
  OR NEW.attempt_id != OLD.attempt_id
  OR NEW.assessment_id != OLD.assessment_id
  OR NEW.generation != OLD.generation
  OR NEW.attempt_idempotency_hash != OLD.attempt_idempotency_hash
  OR NEW.worker_id != OLD.worker_id
  OR NEW.fence_token != OLD.fence_token
  OR (NEW.state != 'INFERENCE_RUNNING' AND EXISTS (
        SELECT 1 FROM assessment s WHERE s.active_attempt_id = OLD.attempt_id
    ))
BEGIN
    SELECT RAISE(ABORT, 'inference_attempt_update_forbidden');
END;""",
    "tr_attempt_no_delete": """CREATE TRIGGER tr_attempt_no_delete
BEFORE DELETE ON inference_attempt
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'inference_attempt_delete_forbidden');
END;""",
    # -------------------------------------------------------------- inference_result
    "tr_result_no_update": """CREATE TRIGGER tr_result_no_update
BEFORE UPDATE ON inference_result
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'inference_result_update_forbidden');
END;""",
    "tr_result_no_delete": """CREATE TRIGGER tr_result_no_delete
BEFORE DELETE ON inference_result
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'inference_result_delete_forbidden');
END;""",
}
