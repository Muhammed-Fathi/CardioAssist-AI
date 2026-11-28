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
integration time (Track 1 owns this file). Scope is exactly the fifteen triggers
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
    "tr_assessment_pointer_insert": """CREATE TRIGGER tr_assessment_pointer_insert
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
  OR NEW.panel_id != OLD.panel_id
  OR NEW.panel_version != OLD.panel_version
  OR NEW.source_contract_version != OLD.source_contract_version
  OR NEW.source_kind != OLD.source_kind
  OR NEW.stage_complete != OLD.stage_complete
  OR NEW.created_at IS NOT OLD.created_at
  OR NEW.review_state IS NOT OLD.review_state
  OR NEW.review_version IS NOT OLD.review_version
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
    "tr_assessment_no_delete": """CREATE TRIGGER tr_assessment_no_delete
BEFORE DELETE ON assessment
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'assessment_delete_forbidden');
END;""",
    # Every attempt insertion starts from the exact safe, authorized assessment
    # generation; the AFTER trigger binds the inserted running attempt and
    # state transition atomically so no committed orphan-running attempt exists.
    "tr_attempt_insert_guard": """CREATE TRIGGER tr_attempt_insert_guard
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
END;""",
    "tr_attempt_associate_assessment": """CREATE TRIGGER tr_attempt_associate_assessment
AFTER INSERT ON inference_attempt
FOR EACH ROW
BEGIN
    UPDATE assessment
    SET status = 'INFERENCE_RUNNING',
        active_attempt_id = NEW.attempt_id,
        updated_at = NEW.leased_at
    WHERE assessment_id = NEW.assessment_id;
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
    "tr_attempt_no_delete": """CREATE TRIGGER tr_attempt_no_delete
BEFORE DELETE ON inference_attempt
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'inference_attempt_delete_forbidden');
END;""",
    # SAFE_SCOPE has no authorized result publisher. This database guard is
    # deliberately unconditional; enabling result insertion requires a later
    # explicitly authorized migration rather than a direct SQL bypass.
    "tr_result_insert_forbidden": """CREATE TRIGGER tr_result_insert_forbidden
BEFORE INSERT ON inference_result
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'inference_result_publication_not_authorized');
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
