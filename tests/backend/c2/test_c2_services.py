"""C2 clinical-intake service tests: H1a, H1b, S1, S2, S3 (checkpoint §9).

End-to-end through the HTTP routes on a fresh Alembic database (head
``20261128_07``): authorization matrices, immutable versioning, the canonical
snapshot digest, the SAFE_SCOPE terminal state with zero result rows, role
projections, cursor pagination, and the C2 idempotency replay rules
(live consent/assignment revalidation before any cached 2xx).
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import jsonschema
from sqlalchemy import text

from backend.app.term1.health_profile import canonical_bytes
from tests.backend.c1.factories import (
    clean_doctor,
    register_patient,
    setup_doctor_with_invitation,
)
from tests.backend.c2.conftest import both, idem

SCHEMA_DIR = Path(__file__).resolve().parents[3] / "shared" / "contracts" / "term1" / "schemas"

FULL_INPUTS = {"age": 54.0, "sex": 0, "cp": 1, "trestbps": 130.0, "restecg": 0}
FULL_UNITS = {"age": "years", "trestbps": "mmHg"}


def assert_response_schema(body: dict, filename: str) -> None:
    schema = json.loads((SCHEMA_DIR / filename).read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(
        schema, format_checker=jsonschema.FormatChecker()
    ).validate(body)


def h1b_body(**overrides) -> dict:
    body = {
        "contract_version": "v1",
        "panel_id": "da_a2_resting_v1",
        "panel_version": "1.0.0",
        "inputs": dict(FULL_INPUTS),
        "units": dict(FULL_UNITS),
        "missing_reasons": {},
    }
    body.update(overrides)
    return body


def s1_body(assignment_id: str, health_profile_id: str, **overrides) -> dict:
    body = {
        "contract_version": "v1",
        "assignment_id": assignment_id,
        "health_profile_id": health_profile_id,
        "panel_id": "da_a2_resting_v1",
        "panel_version": "1.0.0",
        "input_mode": "manual",
        "panel_input": {
            "inputs": dict(FULL_INPUTS),
            "units": dict(FULL_UNITS),
            "missing_reasons": {},
        },
        "ocr_source": None,
        "attached_document_ids": [],
        "reassessment_of_id": None,
        "reassessment_reason": None,
    }
    body.update(overrides)
    return body


def patch_profile(client, token, body, *, key=None):
    return client.patch(
        "/v1/me/health-profile",
        headers=both(token, key or f"h1b-{uuid.uuid4()}"),
        json=body,
    )


def seed_patient(
    app,
    client,
    *,
    email: str = "demo.patient@cardioassist.local",
    identifier: str = "DEMO-ID-001",
    with_profile: bool = True,
) -> dict:
    chain = setup_doctor_with_invitation(app, client, identifier=identifier)
    registration = register_patient(
        client, chain["invitation"]["access_code"], identifier=identifier, email=email
    )
    token = registration["session_token"]
    profile = None
    if with_profile:
        response = patch_profile(client, token, h1b_body())
        assert response.status_code == 200, response.text
        profile = response.json()
    return {
        "token": token,
        "user_id": registration["user_id"],
        "patient_id": registration["patient_id"],
        "assignment_id": registration["assignment_id"],
        "profile": profile,
        "chain": chain,
    }


def seed_another_patient(
    client, chain, *, email: str, identifier: str, with_profile: bool = True
) -> dict:
    """Second patient under the SAME doctor via a fresh visit + invitation."""
    _visit, invitation = chain["fresh_visit"](0, identifier)
    registration = register_patient(
        client, invitation["access_code"], identifier=identifier, email=email
    )
    token = registration["session_token"]
    profile = None
    if with_profile:
        response = patch_profile(client, token, h1b_body())
        assert response.status_code == 200, response.text
        profile = response.json()
    return {
        "token": token,
        "user_id": registration["user_id"],
        "patient_id": registration["patient_id"],
        "assignment_id": registration["assignment_id"],
        "profile": profile,
    }


def sql_rows(app, sql: str, **params):
    with app.state.database.engine.connect() as connection:
        return connection.execute(text(sql), params).all()


def submit_s1(client, token, assignment_id, profile_id, *, key=None, **overrides):
    return client.post(
        "/v1/assessments",
        headers=both(token, key or f"s1-{uuid.uuid4()}"),
        json=s1_body(assignment_id, profile_id, **overrides),
    )


# ===========================================================================
# H1a — current health profile
# ===========================================================================


def test_h1a_404_before_any_profile(client, app):
    seeded = seed_patient(app, client, with_profile=False)
    response = client.get(
        "/v1/me/health-profile",
        headers={"Authorization": f"Bearer {seeded['token']}"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "health_profile_not_found"


def test_h1a_requires_authentication(client):
    assert client.get("/v1/me/health-profile").status_code == 401


def test_h1a_returns_the_frozen_13_key_projection(client, app):
    seeded = seed_patient(app, client)
    response = client.get(
        "/v1/me/health-profile",
        headers={"Authorization": f"Bearer {seeded['token']}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert_response_schema(body, "term1_health_profile_response.schema.json")
    assert set(body) == {
        "contract_version",
        "health_profile_id",
        "version_number",
        "status",
        "panel_id",
        "panel_version",
        "schema_version",
        "inputs",
        "units",
        "missing_reasons",
        "provenance",
        "profile_sha256",
        "created_at",
    }
    assert body["status"] == "COMPLETE"
    assert body["schema_version"] == "term1.c2.profile/v1"
    assert body["panel_id"] == "da_a2_resting_v1"
    assert body["panel_version"] == "1.0.0"
    assert body["version_number"] == 1
    assert body["inputs"] == FULL_INPUTS
    assert body["units"] == FULL_UNITS
    assert body["provenance"] == {
        "source_contract_version": "term1.c2.intake/v1",
        "source_kind": "synthetic_demo_patient_manual",
    }
    assert len(body["profile_sha256"]) == 64


def test_h1a_admin_forbidden_and_doctor_forbidden(client, app):
    seeded = seed_patient(app, client)
    from tests.backend.c1.conftest import bootstrap_admin, login
    from tests.backend.c2.conftest import ADMIN_EMAIL, ADMIN_PASSWORD

    bootstrap_admin(app)
    admin_token = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)["session_token"]
    response = client.get(
        "/v1/me/health-profile", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "admin_clinical_content_forbidden"

    doctor_token = seeded["chain"]["doctor"]["token"]
    response = client.get(
        "/v1/me/health-profile", headers={"Authorization": f"Bearer {doctor_token}"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_h1a_self_read_survives_consent_withdrawal(client, app):
    seeded = seed_patient(app, client)
    revoke = client.post(
        "/v1/me/consent/synthetic-demo/revoke",
        headers=both(seeded["token"], f"revoke-{uuid.uuid4()}"),
        json={"reason_code": "patient_revoked_demo"},
    )
    assert revoke.status_code == 200, revoke.text
    response = client.get(
        "/v1/me/health-profile",
        headers={"Authorization": f"Bearer {seeded['token']}"},
    )
    assert response.status_code == 200


# ===========================================================================
# H1b — manual patch, immutable versions
# ===========================================================================


def test_h1b_creates_v1_then_supersedes_into_v2_with_merge(client, app):
    seeded = seed_patient(app, client)
    token = seeded["token"]

    # v1 was created by the seed; patch only restecg -> v2 merges the rest.
    response = patch_profile(
        client,
        token,
        h1b_body(
            inputs={"restecg": None},
            units={},
            missing_reasons={"restecg": "not_measured"},
            expected_version_number=1,
        ),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert_response_schema(body, "term1_health_profile_response.schema.json")
    assert body["version_number"] == 2
    assert body["status"] == "DRAFT"  # restecg was nullified by the patch
    assert body["inputs"]["age"] == 54.0  # inherited
    assert body["inputs"]["restecg"] is None
    assert body["missing_reasons"] == {"restecg": "not_measured"}
    assert body["units"] == FULL_UNITS  # derived, unchanged
    assert body["health_profile_id"] != seeded["profile"]["health_profile_id"]

    rows = sql_rows(
        app,
        "SELECT status, superseded_at, version_number FROM health_profile "
        "WHERE patient_id = :pid ORDER BY version_number",
        pid=seeded["patient_id"],
    )
    assert len(rows) == 2
    assert rows[0].status == "SUPERSEDED" and rows[0].superseded_at is not None
    assert rows[1].status == "DRAFT" and rows[1].superseded_at is None


def test_h1b_expected_version_cas_conflict(client, app):
    seeded = seed_patient(app, client)
    response = patch_profile(
        client, seeded["token"], h1b_body(expected_version_number=7)
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "concurrency_conflict"
    # no new version was written
    rows = sql_rows(
        app,
        "SELECT version_number FROM health_profile WHERE patient_id = :pid",
        pid=seeded["patient_id"],
    )
    assert len(rows) == 1


def test_h1b_draft_status_when_mandatory_history_incomplete(client, app):
    seeded = seed_patient(app, client, with_profile=False)
    response = patch_profile(
        client,
        seeded["token"],
        h1b_body(inputs={"age": 61.0, "sex": 1, "cp": 2}, units={"age": "years"}),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "DRAFT"
    assert body["missing_reasons"] == {
        "trestbps": "not_provided",
        "restecg": "not_provided",
    }


def test_h1b_rejects_unknown_and_prohibited_panel_keys(client, app):
    seeded = seed_patient(app, client)
    response = patch_profile(
        client, seeded["token"], h1b_body(inputs={"ef-tte": 55}, units={})
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "prohibited_clinical_field"

    response = patch_profile(
        client, seeded["token"], h1b_body(inputs={"mystery": 1}, units={})
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_panel_input"


def test_h1b_rejects_client_supplied_provenance_keys(client, app):
    seeded = seed_patient(app, client)
    provenance_values = {
        "source_kind": "synthetic_demo_ocr_confirmed",
        "provenance": {"source_kind": "synthetic_demo_ocr_confirmed"},
        "profile_sha256": "a" * 64,
        "ocr_source": {"document_id": str(uuid.uuid4())},
        "source_contract_version": "attacker/v9",
    }
    for key, value in provenance_values.items():
        response = patch_profile(
            client, seeded["token"], h1b_body(**{key: value})
        )
        assert response.status_code == 422, (key, response.text)
        assert response.json()["error"]["code"] == "prohibited_clinical_field", key


def test_h1b_reason_and_unit_rules(client, app):
    seeded = seed_patient(app, client)
    # reason resent for a present value
    response = patch_profile(
        client,
        seeded["token"],
        h1b_body(missing_reasons={"age": "not_measured"}),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "missing_reason_mismatch"
    # wrong unit token for a present numerical field
    response = patch_profile(
        client, seeded["token"], h1b_body(units={"trestbps": "cmHg"})
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_panel_input"
    # explicit null on a mandatory history field
    response = patch_profile(
        client, seeded["token"], h1b_body(inputs=dict(FULL_INPUTS, age=None))
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_panel_input"


def test_h1b_requires_consent_and_rejects_admin(client, app):
    seeded = seed_patient(app, client, with_profile=False)
    revoke = client.post(
        "/v1/me/consent/synthetic-demo/revoke",
        headers=both(seeded["token"], f"revoke-{uuid.uuid4()}"),
        json={"reason_code": "patient_revoked_demo"},
    )
    assert revoke.status_code == 200
    response = patch_profile(client, seeded["token"], h1b_body())
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "consent_required"

    from tests.backend.c1.conftest import bootstrap_admin, login
    from tests.backend.c2.conftest import ADMIN_EMAIL, ADMIN_PASSWORD

    bootstrap_admin(app)
    admin_token = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)["session_token"]
    response = patch_profile(client, admin_token, h1b_body())
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "admin_clinical_content_forbidden"


def test_h1b_idempotent_replay_is_cached_then_revalidated(client, app):
    seeded = seed_patient(app, client, with_profile=False)
    token = seeded["token"]
    key = f"h1b-replay-{uuid.uuid4()}"
    first = patch_profile(client, token, h1b_body(), key=key)
    assert first.status_code == 200, first.text

    replay = patch_profile(client, token, h1b_body(), key=key)
    assert replay.status_code == 200
    replayed = replay.json()
    assert replayed.pop("idempotent_replay") is True  # frozen C1 replay marker
    assert replayed == first.json()

    # After consent withdrawal the cached 2xx must NOT be served: the replay
    # path re-checks live consent inside the transaction (checkpoint §7).
    revoke = client.post(
        "/v1/me/consent/synthetic-demo/revoke",
        headers=both(token, f"revoke-{uuid.uuid4()}"),
        json={"reason_code": "patient_revoked_demo"},
    )
    assert revoke.status_code == 200
    replay_after = patch_profile(client, token, h1b_body(), key=key)
    assert replay_after.status_code == 403
    assert replay_after.json()["error"]["code"] == "consent_required"


# ===========================================================================
# S1 — immutable assessment submission (SAFE_SCOPE)
# ===========================================================================


def test_s1_creates_snapshot_attempt_and_terminal_unavailable(client, app):
    seeded = seed_patient(app, client)
    response = submit_s1(
        client, seeded["token"], seeded["assignment_id"],
        seeded["profile"]["health_profile_id"],
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert_response_schema(body, "term1_assessment_create_response.schema.json")
    assert set(body) == {
        "contract_version",
        "assessment_id",
        "assignment_id",
        "health_profile_id",
        "snapshot_id",
        "snapshot_sha256",
        "panel_id",
        "panel_version",
        "source_contract_version",
        "source_kind",
        "status",
        "reason_code",
        "attempt_id",
        "review_state",
        "created_at",
    }
    # SAFE_SCOPE terminal state: never a score, never a success state.
    assert body["status"] == "INFERENCE_UNAVAILABLE"
    assert body["reason_code"] == "real_ai_not_authorized"
    assert body["review_state"] == "NOT_REVIEWED"
    assert body["source_kind"] == "synthetic_demo_patient_manual"

    counts = {
        table: sql_rows(app, f"SELECT COUNT(*) FROM {table}")[0][0]
        for table in (
            "assessment",
            "assessment_snapshot",
            "inference_attempt",
            "inference_result",
        )
    }
    assert counts["assessment"] == 1
    assert counts["assessment_snapshot"] == 1
    assert counts["inference_attempt"] == 1
    assert counts["inference_result"] == 0  # zero result rows, ever

    assessment = sql_rows(
        app,
        "SELECT status, reason_code, active_attempt_id, current_generation, "
        "review_state, stage_complete FROM assessment",
    )[0]
    assert assessment.status == "INFERENCE_UNAVAILABLE"
    assert assessment.reason_code == "real_ai_not_authorized"
    assert assessment.active_attempt_id is None
    assert assessment.current_generation == 0
    assert assessment.review_state == "NOT_REVIEWED"
    assert bool(assessment.stage_complete) is True

    attempt = sql_rows(
        app,
        "SELECT state, reason_code, worker_id, fence_token, completed_at "
        "FROM inference_attempt",
    )[0]
    assert attempt.state == "INFERENCE_UNAVAILABLE"
    assert attempt.reason_code == "real_ai_not_authorized"
    assert attempt.worker_id == "disabled_stub"
    assert attempt.completed_at is not None

    # Snapshot digest: sha256(canonical(snapshot_json)) == stored digest.
    snapshot = sql_rows(
        app, "SELECT snapshot_json, snapshot_sha256, source_kind FROM assessment_snapshot"
    )[0]
    envelope = json.loads(snapshot.snapshot_json)
    assert snapshot.source_kind == "synthetic_demo_patient_manual"
    import hashlib

    assert (
        hashlib.sha256(canonical_bytes(envelope)).hexdigest()
        == snapshot.snapshot_sha256
        == body["snapshot_sha256"]
    )
    assert envelope["inputs"] == FULL_INPUTS
    assert envelope["source_kind"] == "synthetic_demo_patient_manual"
    assert envelope["panel"]["panel_contract_sha256"] == (
        "c18ad4cd2cf08f6fefb2e340573760da7000bc1d8eb4ad38783b873c018e57b8"
    )
    assert envelope["attached_documents"] == []

    events = {
        row[0]
        for row in sql_rows(app, "SELECT event_type FROM workflow_audit_event")
    }
    assert {"ASSESSMENT_CREATED", "INFERENCE_ATTEMPT_TERMINATED"} <= events


def test_s1_replay_same_body_and_key_conflict_on_changed_body(client, app):
    seeded = seed_patient(app, client)
    key = f"s1-replay-{uuid.uuid4()}"
    first = submit_s1(
        client, seeded["token"], seeded["assignment_id"],
        seeded["profile"]["health_profile_id"], key=key,
    )
    assert first.status_code == 201, first.text

    replay = submit_s1(
        client, seeded["token"], seeded["assignment_id"],
        seeded["profile"]["health_profile_id"], key=key,
    )
    assert replay.status_code == 201
    assert replay.json()["assessment_id"] == first.json()["assessment_id"]

    # Same key, different payload -> idempotency conflict, no second row.
    changed = submit_s1(
        client, seeded["token"], seeded["assignment_id"],
        seeded["profile"]["health_profile_id"], key=key,
        panel_input={
            "inputs": dict(FULL_INPUTS, age=55.0),
            "units": dict(FULL_UNITS),
            "missing_reasons": {},
        },
    )
    assert changed.status_code == 409
    assert changed.json()["error"]["code"] == "idempotency_key_conflict"
    assert sql_rows(app, "SELECT COUNT(*) FROM assessment")[0][0] == 1

    # A fresh key creates a second assessment.
    second = submit_s1(
        client, seeded["token"], seeded["assignment_id"],
        seeded["profile"]["health_profile_id"],
    )
    assert second.status_code == 201
    assert second.json()["assessment_id"] != first.json()["assessment_id"]


def test_s1_input_mode_xor_gates(client, app):
    seeded = seed_patient(app, client)
    assignment = seeded["assignment_id"]
    profile_id = seeded["profile"]["health_profile_id"]
    token = seeded["token"]

    response = submit_s1(
        client, token, assignment, profile_id, input_mode="ocr_confirmed"
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ocr_inference_not_authorized"

    response = submit_s1(
        client, token, assignment, profile_id,
        panel_input=None, ocr_source={"document_id": str(uuid.uuid4())},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"

    response = submit_s1(
        client, token, assignment, profile_id,
        ocr_source={"document_id": str(uuid.uuid4())},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"

    # no rows were written by the gated attempts
    assert sql_rows(app, "SELECT COUNT(*) FROM assessment")[0][0] == 0


def test_s1_consent_assignment_and_role_gates(client, app):
    seeded = seed_patient(app, client)
    assignment = seeded["assignment_id"]
    profile_id = seeded["profile"]["health_profile_id"]
    token = seeded["token"]

    # unknown assignment -> 404 (identical shape to a foreign one)
    response = submit_s1(client, token, str(uuid.uuid4()), profile_id)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "assignment_not_found"

    # revoked consent -> 403 before anything else is written
    revoke_consent = client.post(
        "/v1/me/consent/synthetic-demo/revoke",
        headers=both(token, f"revoke-{uuid.uuid4()}"),
        json={"reason_code": "patient_revoked_demo"},
    )
    assert revoke_consent.status_code == 200
    response = submit_s1(client, token, assignment, profile_id)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "consent_required"
    assert sql_rows(app, "SELECT COUNT(*) FROM assessment")[0][0] == 0


def test_s1_reassignment_revocation_gate_and_replay(client, app):
    seeded = seed_patient(app, client, with_profile=False)
    # fresh patient with consent + assignment, but create profile first
    profile_resp = patch_profile(
        client, seeded["token"], h1b_body()
    )
    profile_id = profile_resp.json()["health_profile_id"]
    key = f"s1-revoke-{uuid.uuid4()}"
    first = submit_s1(
        client, seeded["token"], seeded["assignment_id"], profile_id, key=key
    )
    assert first.status_code == 201, first.text

    revoke = client.post(
        f"/v1/me/assignments/{seeded['assignment_id']}/revoke",
        headers=both(seeded["token"], f"asg-revoke-{uuid.uuid4()}"),
        json={"reason_code": "patient_revoked_demo"},
    )
    assert revoke.status_code == 200, revoke.text

    # fresh submission on the revoked assignment -> 409
    response = submit_s1(
        client, seeded["token"], seeded["assignment_id"], profile_id
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "assignment_already_revoked"

    # replay of the successful pre-revocation submission revalidates the
    # assignment live and fails with the same conflict (checkpoint §7).
    replay = submit_s1(
        client, seeded["token"], seeded["assignment_id"], profile_id, key=key
    )
    assert replay.status_code == 409
    assert replay.json()["error"]["code"] == "assignment_already_revoked"


def test_s1_profile_pin_states(client, app):
    seeded = seed_patient(app, client, with_profile=False)
    token = seeded["token"]
    assignment = seeded["assignment_id"]

    # unknown profile id -> 404
    response = submit_s1(client, token, assignment, str(uuid.uuid4()))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "health_profile_not_found"

    # existing but DRAFT profile -> 422 health_profile_incomplete
    draft = patch_profile(
        client, token, h1b_body(inputs={"age": 61.0}, units={"age": "years"})
    )
    assert draft.status_code == 200, draft.text
    draft_id = draft.json()["health_profile_id"]
    assert draft.json()["status"] == "DRAFT"
    response = submit_s1(client, token, assignment, draft_id)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "health_profile_incomplete"

    # COMPLETE profile pinned, then superseded by a new version -> 409
    complete = patch_profile(client, token, h1b_body())
    complete_id = complete.json()["health_profile_id"]
    assert complete.json()["status"] == "COMPLETE"
    next_version = patch_profile(
        client, token, h1b_body(expected_version_number=complete.json()["version_number"])
    )
    assert next_version.status_code == 200
    response = submit_s1(client, token, assignment, complete_id)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "health_profile_superseded"


def test_s1_panel_and_attachment_gates(client, app):
    seeded = seed_patient(app, client)
    token = seeded["token"]
    assignment = seeded["assignment_id"]
    profile_id = seeded["profile"]["health_profile_id"]

    response = submit_s1(
        client, token, assignment, profile_id,
        panel_input={
            "inputs": dict(FULL_INPUTS, **{"patient_id": "leak"}),
            "units": dict(FULL_UNITS),
            "missing_reasons": {},
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "prohibited_clinical_field"

    response = submit_s1(
        client, token, assignment, profile_id,
        panel_input={
            "inputs": {"sex": 1, "cp": 1},  # missing mandatory age
            "units": {},
            "missing_reasons": {},
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_panel_input"

    response = submit_s1(
        client, token, assignment, profile_id,
        panel_input={
            "inputs": dict(FULL_INPUTS),
            "units": dict(FULL_UNITS),
            "missing_reasons": {"age": "not_measured"},
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "missing_reason_mismatch"

    # attachments fail closed until Track 2's document tables exist
    response = submit_s1(
        client, token, assignment, profile_id,
        attached_document_ids=[str(uuid.uuid4())],
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "document_not_found"
    assert sql_rows(app, "SELECT COUNT(*) FROM assessment")[0][0] == 0


def test_s1_reassessment_rules(client, app):
    seeded = seed_patient(app, client)
    token = seeded["token"]
    assignment = seeded["assignment_id"]
    profile_id = seeded["profile"]["health_profile_id"]

    # reason without parent -> 422
    response = submit_s1(
        client, token, assignment, profile_id, reassessment_reason="repeat"
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"

    # unknown parent (scoped to this patient+assignment) -> 404
    response = submit_s1(
        client, token, assignment, profile_id,
        reassessment_of_id=str(uuid.uuid4()), reassessment_reason="repeat",
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "assessment_not_found"

    # parent without reason -> 422
    first = submit_s1(client, token, assignment, profile_id)
    assert first.status_code == 201
    parent_id = first.json()["assessment_id"]
    response = submit_s1(
        client, token, assignment, profile_id, reassessment_of_id=parent_id
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"

    # valid reassessment links to the parent
    response = submit_s1(
        client, token, assignment, profile_id,
        reassessment_of_id=parent_id, reassessment_reason="new_vitals",
    )
    assert response.status_code == 201, response.text
    row = sql_rows(
        app,
        "SELECT reassessment_of_id, reassessment_reason FROM assessment "
        "WHERE assessment_id = :aid",
        aid=response.json()["assessment_id"],
    )[0]
    assert row.reassessment_of_id == parent_id
    assert row.reassessment_reason == "new_vitals"


def test_s1_admin_and_doctor_are_forbidden(client, app):
    seeded = seed_patient(app, client)
    from tests.backend.c1.conftest import bootstrap_admin, login
    from tests.backend.c2.conftest import ADMIN_EMAIL, ADMIN_PASSWORD

    bootstrap_admin(app)
    admin_token = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)["session_token"]
    response = submit_s1(
        client, admin_token, seeded["assignment_id"],
        seeded["profile"]["health_profile_id"],
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "admin_clinical_content_forbidden"

    doctor_token = seeded["chain"]["doctor"]["token"]
    response = submit_s1(
        client, doctor_token, seeded["assignment_id"],
        seeded["profile"]["health_profile_id"],
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_s1_empty_body_is_malformed(client, app):
    seeded = seed_patient(app, client)
    response = client.post(
        "/v1/assessments",
        headers=both(seeded["token"], f"s1-empty-{uuid.uuid4()}"),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "malformed_request"


def test_s1_stage_complete_false_is_allowed(client, app):
    seeded = seed_patient(app, client)
    response = submit_s1(
        client, seeded["token"], seeded["assignment_id"],
        seeded["profile"]["health_profile_id"],
        panel_input={
            "inputs": {"age": 54.0, "sex": 0, "cp": 1},
            "units": {"age": "years"},
            "missing_reasons": {},
        },
    )
    assert response.status_code == 201, response.text
    row = sql_rows(app, "SELECT stage_complete FROM assessment")[0]
    assert bool(row.stage_complete) is False


# ===========================================================================
# S2 — role-projected detail
# ===========================================================================


def _first_assessment_id(client, app, seeded) -> str:
    response = submit_s1(
        client, seeded["token"], seeded["assignment_id"],
        seeded["profile"]["health_profile_id"],
    )
    assert response.status_code == 201, response.text
    return response.json()["assessment_id"]


def test_s2_patient_projection_is_status_only(client, app):
    seeded = seed_patient(app, client)
    assessment_id = _first_assessment_id(client, app, seeded)
    response = client.get(
        f"/v1/assessments/{assessment_id}",
        headers={"Authorization": f"Bearer {seeded['token']}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert_response_schema(body, "term1_assessment_get_response.schema.json")
    assert set(body) == {
        "contract_version",
        "assessment_id",
        "status",
        "reason_code",
        "created_at",
        "review_state",
        "research_output",
    }
    assert body["research_output"] is None
    assert body["status"] == "INFERENCE_UNAVAILABLE"
    assert body["reason_code"] == "real_ai_not_authorized"
    assert "inputs" not in body and "scores" not in body


def test_s2_doctor_projection_sees_snapshot_but_never_scores(client, app):
    seeded = seed_patient(app, client)
    assessment_id = _first_assessment_id(client, app, seeded)
    doctor_token = seeded["chain"]["doctor"]["token"]
    response = client.get(
        f"/v1/assessments/{assessment_id}",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert_response_schema(body, "term1_assessment_get_response.schema.json")
    assert set(body) == {
        "contract_version",
        "assessment_id",
        "assignment_id",
        "health_profile_id",
        "snapshot_id",
        "snapshot_sha256",
        "panel_id",
        "panel_version",
        "source_contract_version",
        "source_kind",
        "status",
        "reason_code",
        "inputs",
        "units",
        "missing_reasons",
        "attached_documents",
        "review_state",
        "review_version",
        "research_output",
        "created_at",
        "updated_at",
    }
    assert body["inputs"] == FULL_INPUTS
    assert body["units"] == FULL_UNITS
    assert body["attached_documents"] == []
    assert body["research_output"] is None
    assert body["review_state"] == "NOT_REVIEWED"
    assert body["review_version"] == 0


def test_s2_authorization_matrix(client, app):
    seeded = seed_patient(app, client)
    assessment_id = _first_assessment_id(client, app, seeded)

    # unknown id and foreign id are the identical 404
    for bad_id in (str(uuid.uuid4()),):
        response = client.get(
            f"/v1/assessments/{bad_id}",
            headers={"Authorization": f"Bearer {seeded['token']}"},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "assessment_not_found"

    # a different doctor with no assignment gets the identical 404
    other_doctor = clean_doctor(
        app, client, email="other.doctor@cardioassist.local",
        display_name="Dr Other",
    )
    response = client.get(
        f"/v1/assessments/{assessment_id}",
        headers={"Authorization": f"Bearer {other_doctor['token']}"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "assessment_not_found"

    # ADMIN -> 403 clinical-content block
    from tests.backend.c1.conftest import bootstrap_admin, login
    from tests.backend.c2.conftest import ADMIN_EMAIL, ADMIN_PASSWORD

    bootstrap_admin(app)
    admin_token = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)["session_token"]
    response = client.get(
        f"/v1/assessments/{assessment_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "admin_clinical_content_forbidden"


def test_s2_revoked_assignment_loses_doctor_access(client, app):
    seeded = seed_patient(app, client)
    assessment_id = _first_assessment_id(client, app, seeded)
    doctor_token = seeded["chain"]["doctor"]["token"]

    revoke = client.post(
        f"/v1/doctor/assignments/{seeded['assignment_id']}/revoke",
        headers=both(doctor_token, f"doc-revoke-{uuid.uuid4()}"),
        json={"reason_code": "doctor_revoked_demo"},
    )
    assert revoke.status_code == 200, revoke.text

    response = client.get(
        f"/v1/assessments/{assessment_id}",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "assessment_not_found"


def test_s2_snapshot_integrity_fails_closed(client, app):
    seeded = seed_patient(app, client)
    assessment_id = _first_assessment_id(client, app, seeded)

    # The assessment_snapshot immutability trigger rejects any SQL UPDATE, so
    # tamper in memory only: the digest recomputation must fail closed before
    # anything could be persisted (and the row is restored for a clean commit).
    import pytest
    from sqlalchemy import select

    from backend.app.term1.assessments import _verify_snapshot_integrity
    from backend.app.term1.errors import ApiError
    from backend.app.term1.models import Assessment, AssessmentSnapshot
    from backend.app.term1.tx import write_transaction

    with write_transaction(app.state.database) as session:
        snapshot = session.execute(select(AssessmentSnapshot)).scalar_one()
        assessment = session.execute(
            select(Assessment).where(Assessment.assessment_id == assessment_id)
        ).scalar_one()
        original = snapshot.snapshot_json
        tampered = dict(original)
        tampered["inputs"] = dict(original["inputs"], age=999.0)
        snapshot.snapshot_json = tampered
        with pytest.raises(ApiError) as excinfo:
            _verify_snapshot_integrity(session, assessment)
        assert excinfo.value.code == "internal_error"
        snapshot.snapshot_json = original  # discard the in-memory tamper

    # the untouched row still serves normally
    response = client.get(
        f"/v1/assessments/{assessment_id}",
        headers={"Authorization": f"Bearer {seeded['token']}"},
    )
    assert response.status_code == 200


# ===========================================================================
# S3 — patient status-only list
# ===========================================================================


def test_s3_empty_list(client, app):
    seeded = seed_patient(app, client)
    response = client.get(
        "/v1/me/assessments",
        headers={"Authorization": f"Bearer {seeded['token']}"},
    )
    assert response.status_code == 200
    assert_response_schema(response.json(), "term1_me_assessments_response.schema.json")
    assert response.json() == {
        "contract_version": "v1",
        "items": [],
        "next_cursor": None,
    }


def test_s3_status_only_items_and_cursor_pagination(client, app, clock):
    seeded = seed_patient(app, client)
    token = seeded["token"]
    created = []
    for _ in range(3):
        response = submit_s1(
            client, token, seeded["assignment_id"],
            seeded["profile"]["health_profile_id"],
        )
        assert response.status_code == 201, response.text
        created.append(response.json()["assessment_id"])
        clock.advance(minutes=1)

    # newest first, frozen item shape, never scores or inputs
    response = client.get(
        "/v1/me/assessments?limit=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    page1 = response.json()
    assert_response_schema(page1, "term1_me_assessments_response.schema.json")
    assert len(page1["items"]) == 2
    assert page1["next_cursor"] is not None
    assert [item["assessment_id"] for item in page1["items"]] == created[::-1][:2]
    for item in page1["items"]:
        assert set(item) == {
            "assessment_id",
            "assignment_id",
            "panel_id",
            "panel_version",
            "status",
            "reason_code",
            "source_kind",
            "attempt_id",
            "review_state",
            "created_at",
        }
        assert item["status"] == "INFERENCE_UNAVAILABLE"
        assert item["reason_code"] == "real_ai_not_authorized"
        assert "inputs" not in item and "research_output" not in item

    from urllib.parse import quote

    response = client.get(
        f"/v1/me/assessments?limit=2&cursor={quote(page1['next_cursor'], safe='')}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    page2 = response.json()
    assert_response_schema(page2, "term1_me_assessments_response.schema.json")
    assert len(page2["items"]) == 1
    assert page2["next_cursor"] is None
    assert page2["items"][0]["assessment_id"] == created[0]
    seen = [i["assessment_id"] for i in page1["items"]] + [
        i["assessment_id"] for i in page2["items"]
    ]
    assert len(seen) == len(set(seen)) == 3


def test_s3_limit_and_cursor_validation(client, app):
    seeded = seed_patient(app, client)
    headers = {"Authorization": f"Bearer {seeded['token']}"}
    for query in (
        "limit=0",
        "limit=101",
        "limit=abc",
        "cursor=garbage",              # no created_at|id separator
        "cursor=nope|nope",            # unparseable created_at
        "cursor=2026-11-28T09:00:00Z", # missing assessment_id part
    ):
        response = client.get(f"/v1/me/assessments?{query}", headers=headers)
        assert response.status_code == 400, (query, response.text)
        assert response.json()["error"]["code"] == "malformed_request", query


def test_s3_scoping_and_role_gates(client, app):
    seeded = seed_patient(app, client)
    response = submit_s1(
        client, seeded["token"], seeded["assignment_id"],
        seeded["profile"]["health_profile_id"],
    )
    assert response.status_code == 201

    # a second patient sees an empty list, never foreign rows
    other = seed_another_patient(
        client,
        seeded["chain"],
        email="other.patient@cardioassist.local",
        identifier="DEMO-ID-002",
    )
    response = client.get(
        "/v1/me/assessments",
        headers={"Authorization": f"Bearer {other['token']}"},
    )
    assert response.status_code == 200
    assert response.json()["items"] == []

    # doctor and admin are forbidden
    response = client.get(
        "/v1/me/assessments",
        headers={"Authorization": f"Bearer {seeded['chain']['doctor']['token']}"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"

    from tests.backend.c1.conftest import bootstrap_admin, login
    from tests.backend.c2.conftest import ADMIN_EMAIL, ADMIN_PASSWORD

    bootstrap_admin(app)
    admin_token = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)["session_token"]
    response = client.get(
        "/v1/me/assessments", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "admin_clinical_content_forbidden"
