"""Database-level identity and lifecycle regression probes for C2 R1.

These tests deliberately use SQL against a freshly migrated SQLite database:
service validation alone is not accepted as proof for immutable cross-row
identity or terminal-state protections.
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from backend.app.term1.assessments import canonical_bytes, snapshot_digest
from tests.backend.c2_core.test_c2_services import (
    h1b_body,
    patch_profile,
    seed_patient,
    sql_rows,
    submit_s1,
)


def test_direct_sql_cannot_pair_a_snapshot_with_a_different_profile(client, app):
    seeded = seed_patient(app, client)
    original = submit_s1(
        client,
        seeded["token"],
        seeded["assignment_id"],
        seeded["profile"]["health_profile_id"],
    )
    assert original.status_code == 201, original.text
    assessment = sql_rows(app, "SELECT * FROM assessment")[0]._mapping
    snapshot = sql_rows(app, "SELECT * FROM assessment_snapshot")[0]._mapping

    # Create a second same-patient profile so patient-only FKs would accept it.
    next_profile = patch_profile(
        client,
        seeded["token"],
        h1b_body(
            inputs={"age": 55.0},
            units={"age": "years"},
            expected_version_number=1,
        ),
    )
    assert next_profile.status_code == 200, next_profile.text
    new_assessment_id = str(uuid.uuid4())
    new_snapshot_id = str(uuid.uuid4())
    envelope = json.loads(snapshot["snapshot_json"])
    envelope["assessment_id"] = new_assessment_id
    snapshot_json = canonical_bytes(envelope).decode("utf-8")
    snapshot_sha = snapshot_digest(envelope)

    # Snapshot remains pinned to profile v1, while the new assessment claims v2.
    # The composite FK and assessment scope trigger must reject this even though
    # both profiles and the assessment belong to the same patient.
    with pytest.raises(DBAPIError, match="assessment_scope_invalid|FOREIGN KEY"):
        with app.state.database.engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO assessment_snapshot (snapshot_id, patient_id, "
                    "health_profile_id, panel_id, panel_version, panel_contract_sha256, "
                    "schema_version, schema_sha256, source_contract_version, source_kind, "
                    "snapshot_json, snapshot_sha256, created_at) VALUES "
                    "(:snapshot_id, :patient_id, :health_profile_id, :panel_id, "
                    ":panel_version, :panel_contract_sha256, :schema_version, "
                    ":schema_sha256, :source_contract_version, :source_kind, "
                    ":snapshot_json, :snapshot_sha256, :created_at)"
                ),
                {
                    "snapshot_id": new_snapshot_id,
                    "patient_id": assessment["patient_id"],
                    "health_profile_id": snapshot["health_profile_id"],
                    "panel_id": snapshot["panel_id"],
                    "panel_version": snapshot["panel_version"],
                    "panel_contract_sha256": snapshot["panel_contract_sha256"],
                    "schema_version": snapshot["schema_version"],
                    "schema_sha256": snapshot["schema_sha256"],
                    "source_contract_version": snapshot["source_contract_version"],
                    "source_kind": snapshot["source_kind"],
                    "snapshot_json": snapshot_json,
                    "snapshot_sha256": snapshot_sha,
                    "created_at": snapshot["created_at"],
                },
            )
            connection.execute(
                text(
                    "INSERT INTO assessment (assessment_id, patient_id, "
                    "health_profile_id, snapshot_id, assignment_id, consent_id, "
                    "reassessment_of_id, reassessment_reason, panel_id, panel_version, "
                    "source_contract_version, source_kind, stage_complete, status, "
                    "reason_code, active_attempt_id, current_generation, current_result_id, "
                    "review_state, review_version, created_at, updated_at) VALUES "
                    "(:assessment_id, :patient_id, :health_profile_id, :snapshot_id, "
                    ":assignment_id, :consent_id, NULL, NULL, :panel_id, :panel_version, "
                    ":source_contract_version, :source_kind, :stage_complete, "
                    "'INPUT_VALIDATED', NULL, NULL, 0, NULL, 'NOT_REVIEWED', 0, "
                    ":created_at, :updated_at)"
                ),
                {
                    "assessment_id": new_assessment_id,
                    "patient_id": assessment["patient_id"],
                    "health_profile_id": next_profile.json()["health_profile_id"],
                    "snapshot_id": new_snapshot_id,
                    "assignment_id": assessment["assignment_id"],
                    "consent_id": assessment["consent_id"],
                    "panel_id": assessment["panel_id"],
                    "panel_version": assessment["panel_version"],
                    "source_contract_version": assessment["source_contract_version"],
                    "source_kind": assessment["source_kind"],
                    "stage_complete": assessment["stage_complete"],
                    "created_at": assessment["created_at"],
                    "updated_at": assessment["updated_at"],
                },
            )

    assert sql_rows(app, "SELECT COUNT(*) FROM assessment")[0][0] == 1
    assert sql_rows(app, "SELECT COUNT(*) FROM assessment_snapshot")[0][0] == 1


def test_direct_sql_cannot_mutate_panel_or_source_identity(client, app):
    seeded = seed_patient(app, client)
    response = submit_s1(
        client,
        seeded["token"],
        seeded["assignment_id"],
        seeded["profile"]["health_profile_id"],
    )
    assert response.status_code == 201, response.text
    assessment_id = response.json()["assessment_id"]

    for column, value in (
        ("panel_id", "tampered_panel"),
        ("source_kind", "synthetic_demo_ocr_confirmed"),
        ("source_contract_version", "tampered/v9"),
    ):
        with pytest.raises(DBAPIError, match="assessment_pointer_update_forbidden"):
            with app.state.database.engine.begin() as connection:
                connection.execute(
                    text(f"UPDATE assessment SET {column} = :value WHERE assessment_id = :id"),
                    {"value": value, "id": assessment_id},
                )

    row = sql_rows(
        app,
        "SELECT panel_id, source_kind, source_contract_version FROM assessment "
        "WHERE assessment_id = :id",
        id=assessment_id,
    )[0]
    assert row.panel_id == "da_a2_resting_v1"
    assert row.source_kind == "synthetic_demo_patient_manual"
    assert row.source_contract_version == "term1.c2.intake/v1"


def test_direct_sql_cannot_reset_a_terminal_assessment(client, app):
    seeded = seed_patient(app, client)
    response = submit_s1(
        client,
        seeded["token"],
        seeded["assignment_id"],
        seeded["profile"]["health_profile_id"],
    )
    assert response.status_code == 201, response.text
    assessment_id = response.json()["assessment_id"]

    with pytest.raises(DBAPIError, match="assessment_pointer_update_forbidden"):
        with app.state.database.engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE assessment SET status = 'INPUT_VALIDATED', reason_code = NULL, "
                    "active_attempt_id = NULL, current_result_id = NULL "
                    "WHERE assessment_id = :id"
                ),
                {"id": assessment_id},
            )

    row = sql_rows(
        app,
        "SELECT status, reason_code, current_generation FROM assessment "
        "WHERE assessment_id = :id",
        id=assessment_id,
    )[0]
    assert row.status == "INFERENCE_UNAVAILABLE"
    assert row.reason_code == "real_ai_not_authorized"
    assert row.current_generation == 0
    assert sql_rows(app, "SELECT COUNT(*) FROM inference_result")[0][0] == 0


def test_profile_integrity_verifier_rejects_tampered_fields_and_status(client, app):
    from sqlalchemy import select

    from backend.app.term1.errors import ApiError
    from backend.app.term1.health_profile import verify_profile_digest
    from backend.app.term1.models import HealthProfile
    from backend.app.term1.tx import write_transaction

    seeded = seed_patient(app, client)
    with write_transaction(app.state.database) as session:
        profile = session.execute(
            select(HealthProfile).where(
                HealthProfile.health_profile_id
                == seeded["profile"]["health_profile_id"]
            )
        ).scalar_one()
        original_fields = profile.fields_json
        original_status = profile.status

        changed_fields = dict(original_fields)
        changed_fields["inputs"] = dict(original_fields["inputs"], age=55.0)
        profile.fields_json = changed_fields
        with pytest.raises(ApiError) as excinfo:
            verify_profile_digest(profile)
        assert excinfo.value.code == "internal_error"

        profile.fields_json = original_fields
        profile.status = "DRAFT"
        with pytest.raises(ApiError) as excinfo:
            verify_profile_digest(profile)
        assert excinfo.value.code == "internal_error"

        profile.status = original_status
        verify_profile_digest(profile)


def test_direct_sql_immutability_triggers_reject_profile_snapshot_and_assessment(
    client, app
):
    seeded = seed_patient(app, client)
    response = submit_s1(
        client,
        seeded["token"],
        seeded["assignment_id"],
        seeded["profile"]["health_profile_id"],
    )
    assert response.status_code == 201, response.text
    created = response.json()

    probes = (
        (
            "health_profile_update_forbidden",
            "UPDATE health_profile SET profile_sha256 = :value "
            "WHERE health_profile_id = :id",
            {"value": "0" * 64, "id": created["health_profile_id"]},
        ),
        (
            "assessment_snapshot_update_forbidden",
            "UPDATE assessment_snapshot SET snapshot_sha256 = :value "
            "WHERE snapshot_id = :id",
            {"value": "0" * 64, "id": created["snapshot_id"]},
        ),
        (
            "assessment_snapshot_delete_forbidden",
            "DELETE FROM assessment_snapshot WHERE snapshot_id = :id",
            {"id": created["snapshot_id"]},
        ),
        (
            "assessment_delete_forbidden",
            "DELETE FROM assessment WHERE assessment_id = :id",
            {"id": created["assessment_id"]},
        ),
    )
    for trigger_message, statement, params in probes:
        with pytest.raises(DBAPIError, match=trigger_message):
            with app.state.database.engine.begin() as connection:
                connection.execute(text(statement), params)

    assert sql_rows(app, "SELECT COUNT(*) FROM assessment")[0][0] == 1
    assert sql_rows(app, "SELECT COUNT(*) FROM assessment_snapshot")[0][0] == 1
    assert sql_rows(app, "SELECT COUNT(*) FROM health_profile")[0][0] == 1


def test_direct_sql_result_rows_are_immutable(client, app):
    seeded = seed_patient(app, client)
    response = submit_s1(
        client,
        seeded["token"],
        seeded["assignment_id"],
        seeded["profile"]["health_profile_id"],
    )
    assert response.status_code == 201, response.text
    created = response.json()
    snapshot = sql_rows(
        app,
        "SELECT snapshot_sha256, panel_contract_sha256 FROM assessment_snapshot "
        "WHERE snapshot_id = :id",
        id=created["snapshot_id"],
    )[0]

    # Test-only publication-shaped row: Track 1 has no production result writer.
    result_id = str(uuid.uuid4())
    values = {
        "result_id": result_id,
        "assessment_id": created["assessment_id"],
        "attempt_id": created["attempt_id"],
        "generation": 0,
        "snapshot_id": created["snapshot_id"],
        "snapshot_sha256": snapshot.snapshot_sha256,
        "schema_version": "term1.c2.result/v1",
        "panel_id": created["panel_id"],
        "panel_version": created["panel_version"],
        "panel_contract_sha256": snapshot.panel_contract_sha256,
        "source_contract_version": created["source_contract_version"],
        "source_kind": created["source_kind"],
        "model_id": "test-only-model",
        "model_version": "0.0.0",
        "protocol_id": "test-only-protocol",
        "execution_profile": "test-only",
        "bundle_dir_name": "test-only-bundle",
        "manifest_sha256": "a" * 64,
        "source_sha256": "b" * 64,
        "model_joblib_sha256": "c" * 64,
        "preprocessing_json_sha256": "d" * 64,
        "calibration_json_sha256": "e" * 64,
        "shap_background_sha256": "f" * 64,
        "evaluation_summary_sha256": "1" * 64,
        "protocol_md_sha256": "2" * 64,
        "serving_eligibility": "RESEARCH_ONLY",
        "clinical_use_authorized": 0,
        "raw_model_score": 0.5,
        "raw_model_log_odds": 0.0,
        "calibrated_research_score": 0.5,
        "calibrated_log_odds": 0.0,
        "calibration_meta_json": "{}",
        "shap_json": "{}",
        "lime_status": "WITHHELD_QUALITY_NOT_MET",
        "lime_json": None,
        "lime_meta_json": "{}",
        "fold_dispersion_json": "{}",
        "limitations_json": "{}",
        "result_sha256": "3" * 64,
        "published_at": created["created_at"],
    }
    columns = ", ".join(values)
    parameters = ", ".join(f":{column}" for column in values)
    with app.state.database.engine.begin() as connection:
        connection.execute(
            text(
                f"INSERT INTO inference_result ({columns}) "
                f"VALUES ({parameters})"
            ),
            values,
        )

    with pytest.raises(DBAPIError, match="inference_result_update_forbidden"):
        with app.state.database.engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE inference_result SET raw_model_score = 0.6 "
                    "WHERE result_id = :id"
                ),
                {"id": result_id},
            )
    with pytest.raises(DBAPIError, match="inference_result_delete_forbidden"):
        with app.state.database.engine.begin() as connection:
            connection.execute(
                text("DELETE FROM inference_result WHERE result_id = :id"),
                {"id": result_id},
            )
    assert sql_rows(
        app,
        "SELECT raw_model_score FROM inference_result WHERE result_id = :id",
        id=result_id,
    )[0].raw_model_score == 0.5
