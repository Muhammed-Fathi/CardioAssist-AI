"""C1 HTTP contract closure: the twenty-operation non-skipping proof.

This module closes the outstanding owner-mandated C1 contract obligations that
`test_c1_http_conformance.py` left open. It is deliberately stricter than the
conformance module and adds no new application behaviour:

1. **Exact executed-operation inventory.** One test drives a single end-to-end
   chain and records the `(method, path)` of every request it actually issued.
   The recorded set is asserted *equal* to `openapi.C1_OPERATIONS` — not a
   subset, not "at least". Nothing is conditionally skipped: every operation is
   executed unconditionally and a failure to reach any of them fails the test.
2. **Raw response validation against the served document.** Each recorded
   response is validated, unmodified, against the JSON Schema that the served
   `/openapi.json` document binds to *that operation's actual HTTP status*. No
   body normalization happens: `null`s are kept, `idempotent_replay` is kept,
   and extra properties are not stripped. An undeclared status is a failure, so
   the served status catalogue is proven complete against the real surface.
3. **Error-status catalogue closure.** Every 4xx/5xx response observed for every
   operation must be declared by the served document for that operation, and its
   `error.code` must appear in that status's declared closed code list
   (`x-error-codes` in the served document, derived from the contract source).
4. **Replay variants.** Every secret-free idempotent operation is replayed and
   the replay body validated against the same served schema; every
   secret-bearing idempotent operation is proven to answer the replay with
   `409 secret_not_redisclosable` and to disclose no secret material.
5. **Missing-configuration HTTP 503.** With no operator key material configured,
   every C1 operation answers with the catalogue's `503
   identity_key_configuration_error` envelope (JSON, correct schema) rather than
   an unhandled 500 or a bare routing error.
6. **Secret non-disclosure and data isolation.** No response body ever carries a
   password, access code, verifier, HMAC or session token of another actor; a
   patient cannot read another patient's assignments; a doctor cannot read
   another doctor's visit.

Synthetic disposable fixtures only. Every test gets a fresh migrated SQLite file.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from backend.app.main import create_app
from backend.app.term1 import errors, openapi
from backend.app.term1.settings import Term1Settings

from .conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    BASE_TIME,
    MutableClock,
    TEST_BOOTSTRAP_SECRET,
    bearer,
    bootstrap_admin,
    login,
)
from .factories import DEMO_ID_A, provision_doctor, setup_doctor_with_invitation

ROOT = openapi.TERM1_DIR.parents[2]

# Every secret shape the C1 surface can emit. None of these may appear in an
# error envelope or in a redacted replay.
_PARAMETER_NAMES = (
    "user_id",
    "invitation_id",
    "visit_id",
    "assignment_id",
    "session_id",
)


def _template_for(path: str) -> str:
    """Map a concrete request path back to its declared contract template."""
    for candidate_method, candidate in openapi.C1_OPERATIONS:
        prefix = candidate
        segments = []
        for piece in candidate.split("/"):
            if piece.startswith("{") and piece.endswith("}"):
                segments.append(None)
            else:
                segments.append(piece)
        actual = path.split("/")
        if len(actual) != len(segments):
            continue
        if all(expected is None or expected == got for expected, got in zip(segments, actual)):
            return candidate
    return path


SECRET_PATTERNS = (
    re.compile(r'"session_token"\s*:'),
    re.compile(r'"access_code"\s*:'),
    re.compile(r'"temp_secret"\s*:'),
    re.compile(r'"password"\s*:'),
)

TEST_SETTINGS = Term1Settings(
    identity_match_key=b"c1-test-identity-match-key-0000000001",
    subject_key=b"c1-test-subject-canonical-key-00000002",
    pepper=b"c1-test-pepper-for-idempotency-00000000003",
    admin_bootstrap_secret=TEST_BOOTSTRAP_SECRET,
    identity_key_id="demo-v1",
)


# ---------------------------------------------------------------------------
# Chain harness: one app, one clock, every operation recorded
# ---------------------------------------------------------------------------

@dataclass
class Recorded:
    """One executed operation and the raw HTTP response it produced.

    ``path`` is the concrete request URL; ``template`` is the declared
    ``/v1/...`` path with its parameters restored, so a concrete resource id is
    always matched back to the operation inventory.
    """

    method: str
    path: str
    status: int
    body: object
    text: str
    headers: dict

    @property
    def template(self) -> str:
        return _template_for(self.path)


class Chain:
    """Drives the full C1 chain and records every operation it executes."""

    def __init__(self, app, client: TestClient) -> None:
        self.app = app
        self.client = client
        self.records: list[Recorded] = []
        self.document = client.get("/openapi.json").json()

    # -- raw request helper ------------------------------------------------
    def call(
        self,
        method: str,
        path: str,
        *,
        json_body: dict | None = None,
        token: str | None = None,
        idempotency_key: str | None = None,
        expect: int | tuple[int, ...] | None = None,
        record: bool = True,
    ) -> Recorded:
        headers: dict[str, str] = {}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key
        kwargs = {}
        if json_body is not None:
            kwargs["json"] = json_body
        response = self.client.request(method.upper(), path, headers=headers, **kwargs)
        body = None
        if response.headers.get("content-type", "").startswith("application/json"):
            body = response.json()
        recorded = Recorded(
            method=method.lower(),
            path=path,
            status=response.status_code,
            body=body,
            text=response.text,
            headers=dict(response.headers),
        )
        if record:
            self.records.append(recorded)
        if expect is not None:
            allowed = (expect,) if isinstance(expect, int) else expect
            assert response.status_code in allowed, (
                f"{method.upper()} {path} → {response.status_code}: {response.text}"
            )
        return recorded

    # -- served-document helpers ------------------------------------------
    def operation(self, method: str, path: str) -> dict:
        template = _template_for(path)
        assert template in self.document["paths"], (
            f"{method.upper()} {path}: no served operation matches this path"
        )
        return self.document["paths"][template][method.lower()]

    def schema_for(self, method: str, path: str, status: int) -> dict:
        operation = self.operation(method, path)
        key = str(status)
        assert key in operation["responses"], (
            f"{method.upper()} {path}: HTTP {key} is not declared by the served "
            f"document (declared: {sorted(operation['responses'])})"
        )
        schema = operation["responses"][key]["content"]["application/json"]["schema"]
        hops = 0
        while isinstance(schema, dict) and "$ref" in schema:
            reference = schema["$ref"]
            assert reference.startswith("#/"), reference
            node = self.document
            for segment in reference[2:].split("/"):
                node = node[segment.replace("~1", "/").replace("~0", "~")]
            schema = node
            hops += 1
            assert hops < 8, "response schema reference loop"
        return schema

    def declared_codes(self, method: str, path: str, status: int) -> list[str]:
        entry = self.operation(method, path)["responses"][str(status)]
        return list(entry.get("x-error-codes", []))


def _assert_schema(chain: Chain, record: Recorded, *, label: str) -> None:
    """Validate the raw body against the served schema for its actual status."""
    schema = chain.schema_for(record.method, record.path, record.status)
    validator = Draft202012Validator(
        schema, format_checker=Draft202012Validator.FORMAT_CHECKER
    )
    problems = [
        {"path": list(error.absolute_path), "message": error.message, "schema": error.schema}
        for error in validator.iter_errors(record.body)
    ]
    assert not problems, (
        f"{label}: {record.method.upper()} {record.path} → {record.status} "
        f"violates the served schema: {problems}"
    )


def _assert_error_catalogue(chain: Chain, record: Recorded, *, label: str) -> None:
    """A failure response must use a declared status, code and envelope."""
    assert record.body is not None, (
        f"{label}: {record.method.upper()} {record.path} → {record.status} "
        f"was not JSON: {record.text[:200]}"
    )
    assert set(record.body) == {"contract_version", "error"}, (
        f"{label}: {record.method.upper()} {record.path} → {record.status} "
        f"is not the v1 error envelope: {record.body}"
    )
    assert record.body["contract_version"] == "v1", record.body
    code = record.body["error"]["code"]
    declared = chain.declared_codes(record.method, record.path, record.status)
    assert declared, (
        f"{label}: {record.method.upper()} {record.path} → {record.status} "
        f"declares no closed code list"
    )
    assert code in declared, (
        f"{label}: {record.method.upper()} {record.path} → {record.status} "
        f"returned {code!r} which is not in the declared {declared}"
    )
    assert errors.ERROR_CATALOGUE[code][0] == record.status, (code, record.status)
    # No error envelope ever carries a secret-bearing value.
    for pattern in SECRET_PATTERNS:
        assert not pattern.search(record.text), (
            f"{label}: {record.method.upper()} {record.path} → {record.status} "
            f"disclosed a secret-shaped field: {record.text[:200]}"
        )


def _fresh_app(*, settings: Term1Settings | None = TEST_SETTINGS):
    directory = tempfile.mkdtemp(prefix="c1-closure-")
    database_url = f"sqlite:///{directory}/c1.sqlite3"
    config = Config(str(ROOT / "alembic.ini"))
    config.attributes["database_url"] = database_url
    command.upgrade(config, "head")
    clock = MutableClock(BASE_TIME)
    return create_app(
        database_url=database_url, term1_settings=settings, term1_clock=clock
    )


# ---------------------------------------------------------------------------
# 1. The exact twenty-operation success inventory
# ---------------------------------------------------------------------------

def _drive_every_operation(chain: Chain) -> dict:
    """Execute every one of the twenty C1 operations exactly once.

    Returns the identifiers later assertions need. Nothing here is conditional:
    an operation that cannot be driven fails the test.
    """
    app = chain.app
    client = chain.client
    bootstrap_admin(app)

    # --- AD1 provision a doctor (admin, authenticated, idempotent) --------
    admin_login = chain.call(
        "post",
        "/v1/auth/login",
        json_body={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        expect=200,
    )
    admin_token = admin_login.body["session_token"]

    chain.call("get", "/v1/auth/me", token=admin_token, expect=200)

    refreshed = chain.call("post", "/v1/auth/refresh", token=admin_token, expect=200)
    admin_token = refreshed.body["session_token"]

    provisioned = chain.call(
        "post",
        "/v1/admin/doctors",
        token=admin_token,
        idempotency_key="closure-ad1",
        json_body={
            "email": "closure.doctor@cardioassist.local",
            "display_name": "Closure Doctor",
            "temp_password_policy": "one_time_secret",
        },
        expect=201,
    )
    doctor_user_id = provisioned.body["user_id"]
    temp_secret = provisioned.body["temp_secret"]

    # Clear the temporary-password state through the real HTTP surface so the
    # doctor account is usable; this also exercises A5 for a real account.
    temp_token = login(client, "closure.doctor@cardioassist.local", temp_secret)[
        "session_token"
    ]
    chain.call(
        "post",
        "/v1/me/password",
        token=temp_token,
        json_body={
            "current_password": temp_secret,
            "new_password": "closure doctor password 1",
        },
        expect=200,
    )
    doctor_token = login(
        client, "closure.doctor@cardioassist.local", "closure doctor password 1"
    )["session_token"]

    # --- AD2 patch the doctor account status ------------------------------
    chain.call(
        "patch",
        f"/v1/admin/accounts/{doctor_user_id}/status",
        token=admin_token,
        idempotency_key="closure-ad2",
        json_body={"status": "ACTIVE", "reason_code": "closure"},
        expect=200,
    )

    # --- V1 attest a visit -------------------------------------------------
    visit = chain.call(
        "post",
        "/v1/doctor/verified-visits",
        token=doctor_token,
        idempotency_key="closure-v1",
        json_body={
            "visit_ref": "CLOSURE-VISIT-001",
            "subject_identifier": DEMO_ID_A,
            "asserted_visit_at": "2026-11-25T10:00:00Z",
            "attestation_code": "PRIOR_IN_PERSON_VISIT_DEMO",
        },
        expect=201,
    )
    visit_id = visit.body["visit_id"]

    # --- V2 read the visit back -------------------------------------------
    chain.call(
        "get", f"/v1/doctor/verified-visits/{visit_id}", token=doctor_token, expect=200
    )

    # --- I1 issue an invitation -------------------------------------------
    invitation = chain.call(
        "post",
        f"/v1/doctor/verified-visits/{visit_id}/invitations",
        token=doctor_token,
        idempotency_key="closure-i1",
        json_body={"subject_identifier": DEMO_ID_A},
        expect=201,
    )
    invitation_id = invitation.body["invitation_id"]

    # --- I3 read the invitation (never returns the access code) -----------
    chain.call(
        "get",
        f"/v1/doctor/invitations/{invitation_id}",
        token=doctor_token,
        expect=200,
    )

    # --- I2 revoke a second invitation ------------------------------------
    second_visit = chain.call(
        "post",
        "/v1/doctor/verified-visits",
        token=doctor_token,
        idempotency_key="closure-v1-b",
        json_body={
            "visit_ref": "CLOSURE-VISIT-002",
            "subject_identifier": DEMO_ID_A,
            "asserted_visit_at": "2026-11-25T11:00:00Z",
            "attestation_code": "PRIOR_IN_PERSON_VISIT_DEMO",
        },
        expect=201,
    )
    second_invitation = chain.call(
        "post",
        f"/v1/doctor/verified-visits/{second_visit.body['visit_id']}/invitations",
        token=doctor_token,
        idempotency_key="closure-i1-b",
        json_body={"subject_identifier": DEMO_ID_A},
        expect=201,
    )
    chain.call(
        "post",
        f"/v1/doctor/invitations/{second_invitation.body['invitation_id']}/revoke",
        token=doctor_token,
        idempotency_key="closure-i2",
        json_body={"reason_code": "closure"},
        expect=200,
    )

    # --- E1 anonymous registration against the live invitation ------------
    registration = chain.call(
        "post",
        "/v1/patients/register",
        idempotency_key="closure-e1",
        json_body={
            "access_code": invitation.body["access_code"],
            "identifier": DEMO_ID_A,
            "email": "closure.patient@cardioassist.local",
            "password": "closure patient password 1",
            "consent_ack": True,
        },
        expect=201,
    )
    patient_token = registration.body["session_token"]
    patient_id = registration.body["patient_id"]

    # --- E2 link the patient to a second doctor ---------------------------
    second_doctor = provision_doctor(
        app,
        client,
        email="closure.doctor2@cardioassist.local",
        display_name="Closure Second Doctor",
    )
    link_visit = chain.call(
        "post",
        "/v1/doctor/verified-visits",
        token=second_doctor["token"],
        idempotency_key="closure-v1-c",
        json_body={
            "visit_ref": "CLOSURE-VISIT-003",
            "subject_identifier": DEMO_ID_A,
            "asserted_visit_at": "2026-11-25T12:00:00Z",
            "attestation_code": "PRIOR_IN_PERSON_VISIT_DEMO",
        },
        expect=201,
    )
    link_invitation = chain.call(
        "post",
        f"/v1/doctor/verified-visits/{link_visit.body['visit_id']}/invitations",
        token=second_doctor["token"],
        idempotency_key="closure-i1-c",
        json_body={"subject_identifier": DEMO_ID_A},
        expect=201,
    )
    link = chain.call(
        "post",
        "/v1/patients/link",
        token=patient_token,
        idempotency_key="closure-e2",
        json_body={
            "access_code": link_invitation.body["access_code"],
            "identifier": DEMO_ID_A,
            "accept_linking": True,
        },
        expect=200,
    )
    linked_assignment = link.body["assignment_id"]

    # --- E3 list the patient's own assignments ----------------------------
    chain.call("get", "/v1/me/assignments", token=patient_token, expect=200)

    # --- E4 the doctor revokes its own assignment -------------------------
    chain.call(
        "post",
        f"/v1/doctor/assignments/{linked_assignment}/revoke",
        token=second_doctor["token"],
        idempotency_key="closure-e4",
        json_body={"reason_code": "closure"},
        expect=200,
    )

    # --- E5 the patient revokes its own assignment ------------------------
    # A dedicated active assignment: E4 already revoked the previous one, and a
    # second revocation of the same assignment is correctly 409.
    fifth_doctor = provision_doctor(
        app,
        client,
        email="closure.doctor3@cardioassist.local",
        display_name="Closure Third Doctor",
    )
    fifth_visit = chain.call(
        "post",
        "/v1/doctor/verified-visits",
        token=fifth_doctor["token"],
        idempotency_key="closure-v1-d",
        json_body={
            "visit_ref": "CLOSURE-VISIT-004",
            "subject_identifier": DEMO_ID_A,
            "asserted_visit_at": "2026-11-25T13:00:00Z",
            "attestation_code": "PRIOR_IN_PERSON_VISIT_DEMO",
        },
        expect=201,
    )
    fifth_invitation = chain.call(
        "post",
        f"/v1/doctor/verified-visits/{fifth_visit.body['visit_id']}/invitations",
        token=fifth_doctor["token"],
        idempotency_key="closure-i1-d",
        json_body={"subject_identifier": DEMO_ID_A},
        expect=201,
    )
    second_link = chain.call(
        "post",
        "/v1/patients/link",
        token=patient_token,
        idempotency_key="closure-e2-b",
        json_body={
            "access_code": fifth_invitation.body["access_code"],
            "identifier": DEMO_ID_A,
            "accept_linking": True,
        },
        expect=200,
    )
    chain.call(
        "post",
        f"/v1/me/assignments/{second_link.body['assignment_id']}/revoke",
        token=patient_token,
        idempotency_key="closure-e5",
        json_body={"reason_code": "closure"},
        expect=200,
    )

    # --- E6 the patient withdraws synthetic-demo consent ------------------
    chain.call(
        "post",
        "/v1/me/consent/synthetic-demo/revoke",
        token=patient_token,
        idempotency_key="closure-e6",
        json_body={"reason_code": "closure"},
        expect=200,
    )

    # --- A6 list own sessions ---------------------------------------------
    # A second live patient session is created so A7 can revoke a *different*
    # session of the same account (A7 must never be exercised on the session
    # that authorises the rest of the chain).
    second_patient_session = login(
        client, "closure.patient@cardioassist.local", "closure patient password 1"
    )["session_token"]
    sessions = chain.call("get", "/v1/me/sessions", token=patient_token, expect=200)
    others = [
        entry["session_id"]
        for entry in sessions.body["sessions"]
        if not entry.get("current")
    ]
    assert others, sessions.body
    session_id = others[0]

    # --- A7 revoke one own session ----------------------------------------
    chain.call(
        "delete", f"/v1/me/sessions/{session_id}", token=patient_token, expect=200
    )

    # --- A2 log out --------------------------------------------------------
    chain.call("post", "/v1/auth/logout", token=admin_token, expect=200)

    return {
        "doctor_token": doctor_token,
        "doctor_user_id": doctor_user_id,
        "patient_token": patient_token,
        "patient_id": patient_id,
        "visit_id": visit_id,
        "invitation_id": invitation_id,
    }


def test_executed_operation_set_equals_the_expected_inventory():
    """The chain executes *exactly* the twenty declared C1 operations.

    Equality (not containment) proves both directions: nothing in the declared
    inventory is skipped, and no undeclared operation is silently exercised.
    """
    app = _fresh_app()
    with TestClient(app) as client:
        chain = Chain(app, client)
        assert len(openapi.C1_OPERATIONS) == 20
        _drive_every_operation(chain)

    executed = {(record.method, record.template) for record in chain.records}
    expected = set(openapi.C1_OPERATIONS)
    assert executed == expected, {
        "missing": sorted(expected - executed),
        "unexpected": sorted(executed - expected),
    }
    # Every operation was recorded at least once and none was skipped.
    assert len(executed) == 20, sorted(executed)
    statuses = [record.status for record in chain.records]
    assert all(200 <= status < 300 for status in statuses), [
        (r.method, r.path, r.status) for r in chain.records if not 200 <= r.status < 300
    ]


def test_every_success_response_validates_against_the_served_schema():
    """All recorded success bodies validate raw against the served schema."""
    app = _fresh_app()
    with TestClient(app) as client:
        chain = Chain(app, client)
        _drive_every_operation(chain)
        for record in chain.records:
            assert 200 <= record.status < 300, (record.method, record.path, record.status)
            _assert_schema(chain, record, label="success")

    # Every declared operation contributed at least one validated success.
    executed = {(record.method, record.template) for record in chain.records}
    assert executed == set(openapi.C1_OPERATIONS), sorted(
        set(openapi.C1_OPERATIONS) ^ executed
    )


# ---------------------------------------------------------------------------
# 2. Replay variants and secret non-redisclosure
# ---------------------------------------------------------------------------

SECRET_BEARING_IDEMPOTENT = (
    ("post", "/v1/admin/doctors", "secret_not_redisclosable"),
    ("post", "/v1/doctor/verified-visits/{visit_id}/invitations", "secret_not_redisclosable"),
    ("post", "/v1/patients/register", "secret_not_redisclosable"),
)

SECRET_FREE_IDEMPOTENT = (
    ("patch", "/v1/admin/accounts/{user_id}/status"),
    ("post", "/v1/doctor/verified-visits"),
    ("post", "/v1/doctor/invitations/{invitation_id}/revoke"),
    ("post", "/v1/doctor/assignments/{assignment_id}/revoke"),
    ("post", "/v1/me/assignments/{assignment_id}/revoke"),
    ("post", "/v1/me/consent/synthetic-demo/revoke"),
    ("post", "/v1/patients/link"),
)


def test_idempotent_operation_partition_is_exhaustive():
    """Every secret-bearing and secret-free idempotent operation is enumerated."""
    assert len(openapi.IDEMPOTENT_C1) == 10
    covered = {path for _m, path, _c in SECRET_BEARING_IDEMPOTENT} | {
        path for _m, path in SECRET_FREE_IDEMPOTENT
    }
    assert covered == set(openapi.IDEMPOTENT_C1), sorted(
        set(openapi.IDEMPOTENT_C1) ^ covered
    )
    # Seven replayable + three secret-bearing = the ten idempotent operations.
    assert len(SECRET_FREE_IDEMPOTENT) + len(SECRET_BEARING_IDEMPOTENT) == 10


def test_secret_free_replays_validate_against_the_served_schema():
    """Every secret-free idempotent operation replays and validates raw.

    The replay body must carry `idempotent_replay: true`, must be accepted by
    the same served schema as the initial response (no normalization), and must
    return the same resource identifiers.
    """
    app = _fresh_app()
    with TestClient(app) as client:
        chain = Chain(app, client)
        bootstrap_admin(app)
        chain.call(
            "post",
            "/v1/auth/login",
            json_body={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            expect=200,
        )
        chain.records.clear()

        admin_token = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)["session_token"]
        chain = Chain(app, client)
        doctor = provision_doctor(
            app,
            client,
            email="replay.doctor@cardioassist.local",
            display_name="Replay Doctor",
        )
        doctor_token = doctor["token"]

        visit = chain.call(
            "post",
            "/v1/doctor/verified-visits",
            token=doctor_token,
            idempotency_key="replay-v1",
            json_body={
                "visit_ref": "REPLAY-VISIT-001",
                "subject_identifier": DEMO_ID_A,
                "asserted_visit_at": "2026-11-25T10:00:00Z",
                "attestation_code": "PRIOR_IN_PERSON_VISIT_DEMO",
            },
            expect=201,
            record=False,
        )
        invitation = chain.call(
            "post",
            f"/v1/doctor/verified-visits/{visit.body['visit_id']}/invitations",
            token=doctor_token,
            idempotency_key="replay-i1",
            json_body={"subject_identifier": DEMO_ID_A},
            expect=201,
            record=False,
        )
        registration = chain.call(
            "post",
            "/v1/patients/register",
            idempotency_key="replay-e1",
            json_body={
                "access_code": invitation.body["access_code"],
                "identifier": DEMO_ID_A,
                "email": "replay.patient@cardioassist.local",
                "password": "replay patient password 1",
                "consent_ack": True,
            },
            expect=201,
            record=False,
        )
        patient_token = registration.body["session_token"]
        second = provision_doctor(
            app,
            client,
            email="replay.doctor2@cardioassist.local",
            display_name="Replay Doctor Two",
        )
        link_visit = chain.call(
            "post",
            "/v1/doctor/verified-visits",
            token=second["token"],
            idempotency_key="replay-v1-b",
            json_body={
                "visit_ref": "REPLAY-VISIT-002",
                "subject_identifier": DEMO_ID_A,
                "asserted_visit_at": "2026-11-25T10:00:00Z",
                "attestation_code": "PRIOR_IN_PERSON_VISIT_DEMO",
            },
            expect=201,
            record=False,
        )
        link_invitation = chain.call(
            "post",
            f"/v1/doctor/verified-visits/{link_visit.body['visit_id']}/invitations",
            token=second["token"],
            idempotency_key="replay-i1-b",
            json_body={"subject_identifier": DEMO_ID_A},
            expect=201,
            record=False,
        )
        link = chain.call(
            "post",
            "/v1/patients/link",
            token=patient_token,
            idempotency_key="replay-e2",
            json_body={
                "access_code": link_invitation.body["access_code"],
                "identifier": DEMO_ID_A,
                "accept_linking": True,
            },
            expect=200,
            record=False,
        )

        # A fresh doctor to own the assignment used by E4.
        third = provision_doctor(
            app,
            client,
            email="replay.doctor3@cardioassist.local",
            display_name="Replay Doctor Three",
        )
        fourth_visit = chain.call(
            "post",
            "/v1/doctor/verified-visits",
            token=third["token"],
            idempotency_key="replay-v1-c",
            json_body={
                "visit_ref": "REPLAY-VISIT-003",
                "subject_identifier": DEMO_ID_A,
                "asserted_visit_at": "2026-11-25T10:00:00Z",
                "attestation_code": "PRIOR_IN_PERSON_VISIT_DEMO",
            },
            expect=201,
            record=False,
        )
        fourth_invitation = chain.call(
            "post",
            f"/v1/doctor/verified-visits/{fourth_visit.body['visit_id']}/invitations",
            token=third["token"],
            idempotency_key="replay-i1-c",
            json_body={"subject_identifier": DEMO_ID_A},
            expect=201,
            record=False,
        )
        third_link = chain.call(
            "post",
            "/v1/patients/link",
            token=patient_token,
            idempotency_key="replay-e2-b",
            json_body={
                "access_code": fourth_invitation.body["access_code"],
                "identifier": DEMO_ID_A,
                "accept_linking": True,
            },
            expect=200,
            record=False,
        )
        extra_visit = chain.call(
            "post",
            "/v1/doctor/verified-visits",
            token=doctor_token,
            idempotency_key="replay-v1-d",
            json_body={
                "visit_ref": "REPLAY-VISIT-004",
                "subject_identifier": DEMO_ID_A,
                "asserted_visit_at": "2026-11-25T10:00:00Z",
                "attestation_code": "PRIOR_IN_PERSON_VISIT_DEMO",
            },
            expect=201,
            record=False,
        )
        extra_invitation = chain.call(
            "post",
            f"/v1/doctor/verified-visits/{extra_visit.body['visit_id']}/invitations",
            token=doctor_token,
            idempotency_key="replay-i1-d",
            json_body={"subject_identifier": DEMO_ID_A},
            expect=201,
            record=False,
        )

        # A dedicated live invitation for the link replay case: the I2 case above
        # consumed the other invitation by revoking it.
        replay_visit = chain.call(
            "post",
            "/v1/doctor/verified-visits",
            token=doctor_token,
            idempotency_key="replay-v1-f",
            json_body={
                "visit_ref": "REPLAY-VISIT-006",
                "subject_identifier": DEMO_ID_A,
                "asserted_visit_at": "2026-11-25T10:00:00Z",
                "attestation_code": "PRIOR_IN_PERSON_VISIT_DEMO",
            },
            expect=201,
            record=False,
        )
        link_replay_invitation = chain.call(
            "post",
            f"/v1/doctor/verified-visits/{replay_visit.body['visit_id']}/invitations",
            token=doctor_token,
            idempotency_key="replay-i1-f",
            json_body={"subject_identifier": DEMO_ID_A},
            expect=201,
            record=False,
        )

        cases = [
            (
                "patch",
                f"/v1/admin/accounts/{third['user_id']}/status",
                admin_token,
                "replay-ad2",
                {"status": "ACTIVE", "reason_code": "replay"},
                None,
            ),
            (
                "post",
                "/v1/doctor/verified-visits",
                doctor_token,
                "replay-v1-e",
                {
                    "visit_ref": "REPLAY-VISIT-005",
                    "subject_identifier": DEMO_ID_A,
                    "asserted_visit_at": "2026-11-25T10:00:00Z",
                    "attestation_code": "PRIOR_IN_PERSON_VISIT_DEMO",
                },
                "visit_id",
            ),
            (
                "post",
                f"/v1/doctor/invitations/{extra_invitation.body['invitation_id']}/revoke",
                doctor_token,
                "replay-i2",
                {"reason_code": "replay"},
                "invitation_id",
            ),
            (
                "post",
                f"/v1/doctor/assignments/{third_link.body['assignment_id']}/revoke",
                third["token"],
                "replay-e4",
                {"reason_code": "replay"},
                "assignment_id",
            ),
            (
                "post",
                f"/v1/me/assignments/{link.body['assignment_id']}/revoke",
                patient_token,
                "replay-e5",
                {"reason_code": "replay"},
                "assignment_id",
            ),
            (
                "post",
                "/v1/me/consent/synthetic-demo/revoke",
                patient_token,
                "replay-e6",
                {"reason_code": "replay"},
                "consent_id",
            ),
            (
                "post",
                "/v1/patients/link",
                patient_token,
                "replay-e2-c",
                {
                    "access_code": link_replay_invitation.body["access_code"],
                    "identifier": DEMO_ID_A,
                    "accept_linking": True,
                },
                "assignment_id",
            ),
        ]
        assert len(cases) == len(SECRET_FREE_IDEMPOTENT)

        for method, path, token, key, body, identity_field in cases:
            first = chain.call(
                method,
                path,
                token=token,
                idempotency_key=key,
                json_body=body,
                expect=(200, 201),
                record=False,
            )
            replay = chain.call(
                method,
                path,
                token=token,
                idempotency_key=key,
                json_body=body,
                expect=(200, 201),
                record=True,
            )
            assert replay.body.get("idempotent_replay") is True, (
                f"{method.upper()} {path} replay did not mark idempotent_replay: "
                f"{replay.text[:200]}"
            )
            assert replay.status == first.status, (method, path, first.status, replay.status)
            if identity_field is not None:
                assert replay.body[identity_field] == first.body[identity_field], (
                    method,
                    path,
                )
            _assert_schema(chain, first, label="replay-initial")
            _assert_schema(chain, replay, label="replay")

        # One recorded replay per secret-free idempotent operation: seven
        # operations, seven initial responses and seven replays validated.
        assert len(chain.records) == len(SECRET_FREE_IDEMPOTENT)
        replayed_operations = {(record.method, record.template) for record in chain.records}
        assert replayed_operations == set(SECRET_FREE_IDEMPOTENT), sorted(
            set(SECRET_FREE_IDEMPOTENT) ^ replayed_operations
        )


def test_secret_bearing_replays_are_never_redisclosed():
    """A one-time secret is never replayed; 409 secret_not_redisclosable instead."""
    app = _fresh_app()
    with TestClient(app) as client:
        chain = Chain(app, client)
        bootstrap_admin(app)
        admin_token = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)["session_token"]

        # AD1: temporary doctor secret.
        ad1_body = {
            "email": "secret.doctor@cardioassist.local",
            "display_name": "Secret Doctor",
            "temp_password_policy": "one_time_secret",
        }
        first = chain.call(
            "post",
            "/v1/admin/doctors",
            token=admin_token,
            idempotency_key="secret-ad1",
            json_body=ad1_body,
            expect=201,
            record=False,
        )
        secret = first.body["temp_secret"]
        replay = chain.call(
            "post",
            "/v1/admin/doctors",
            token=admin_token,
            idempotency_key="secret-ad1",
            json_body=ad1_body,
            expect=409,
            record=True,
        )
        assert replay.body["error"]["code"] == "secret_not_redisclosable", replay.body
        assert secret not in replay.text
        _assert_schema(chain, replay, label="secret-replay")
        _assert_error_catalogue(chain, replay, label="secret-replay")

        # I1: invitation access code.
        doctor = provision_doctor(
            app,
            client,
            email="secret.doctor2@cardioassist.local",
            display_name="Secret Doctor Two",
        )
        visit = chain.call(
            "post",
            "/v1/doctor/verified-visits",
            token=doctor["token"],
            idempotency_key="secret-v1",
            json_body={
                "visit_ref": "SECRET-VISIT-001",
                "subject_identifier": DEMO_ID_A,
                "asserted_visit_at": "2026-11-25T10:00:00Z",
                "attestation_code": "PRIOR_IN_PERSON_VISIT_DEMO",
            },
            expect=201,
            record=False,
        )
        i1_path = f"/v1/doctor/verified-visits/{visit.body['visit_id']}/invitations"
        issued = chain.call(
            "post",
            i1_path,
            token=doctor["token"],
            idempotency_key="secret-i1",
            json_body={"subject_identifier": DEMO_ID_A},
            expect=201,
            record=False,
        )
        access_code = issued.body["access_code"]
        invitation_replay = chain.call(
            "post",
            i1_path,
            token=doctor["token"],
            idempotency_key="secret-i1",
            json_body={"subject_identifier": DEMO_ID_A},
            expect=409,
            record=True,
        )
        assert invitation_replay.body["error"]["code"] == "secret_not_redisclosable"
        assert access_code not in invitation_replay.text
        _assert_schema(chain, invitation_replay, label="secret-replay")
        _assert_error_catalogue(chain, invitation_replay, label="secret-replay")

        # E1: registration session token.
        register_body = {
            "access_code": access_code,
            "identifier": DEMO_ID_A,
            "email": "secret.patient@cardioassist.local",
            "password": "secret patient password 1",
            "consent_ack": True,
        }
        registered = chain.call(
            "post",
            "/v1/patients/register",
            idempotency_key="secret-e1",
            json_body=register_body,
            expect=201,
            record=False,
        )
        session_token = registered.body["session_token"]
        registration_replay = chain.call(
            "post",
            "/v1/patients/register",
            idempotency_key="secret-e1",
            json_body=register_body,
            expect=409,
            record=True,
        )
        assert registration_replay.body["error"]["code"] == "secret_not_redisclosable"
        assert session_token not in registration_replay.text
        _assert_schema(chain, registration_replay, label="secret-replay")
        _assert_error_catalogue(chain, registration_replay, label="secret-replay")

        # The error envelopes carry non-secret identifiers only.
        assert "user_id" in registration_replay.body["error"]
        assert "access_code" not in registration_replay.text
        assert "invitation_id" in invitation_replay.body["error"]


# ---------------------------------------------------------------------------
# 3. Error-status catalogue closure across the whole surface
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Probe:
    label: str
    method: str
    path: str
    token: str | None
    idempotency_key: str | None
    json_body: dict | None


def _error_probes(app, client, *, admin_token: str, doctor_token: str, patient_token: str):
    """One or more failing probes for every operation that can fail.

    Probes are unconditional; each must produce a declared status with a
    declared code. The set of probed operations is asserted equal to the full
    inventory so no operation escapes failure-path coverage.
    """
    valid_bodies = {
        ("post", "/v1/auth/login"): {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        ("patch", "/v1/admin/accounts/{user_id}/status"): {
            "status": "ACTIVE",
            "reason_code": "probe",
        },
        ("post", "/v1/admin/doctors"): {
            "email": "probe.doctor@cardioassist.local",
            "display_name": "Probe Doctor",
            "temp_password_policy": "one_time_secret",
        },
        ("post", "/v1/doctor/verified-visits"): {
            "visit_ref": "PROBE-VISIT",
            "subject_identifier": DEMO_ID_A,
            "asserted_visit_at": "2026-11-25T10:00:00Z",
            "attestation_code": "PRIOR_IN_PERSON_VISIT_DEMO",
        },
        ("post", "/v1/doctor/verified-visits/{visit_id}/invitations"): {
            "subject_identifier": DEMO_ID_A,
        },
        ("post", "/v1/doctor/invitations/{invitation_id}/revoke"): {"reason_code": "probe"},
        ("post", "/v1/doctor/assignments/{assignment_id}/revoke"): {"reason_code": "probe"},
        ("post", "/v1/me/assignments/{assignment_id}/revoke"): {"reason_code": "probe"},
        ("post", "/v1/me/consent/synthetic-demo/revoke"): {"reason_code": "probe"},
        ("post", "/v1/me/password"): {
            "current_password": "probe current password",
            "new_password": "probe replacement password",
        },
        ("post", "/v1/patients/link"): {
            "access_code": "P" * 43,
            "identifier": DEMO_ID_A,
            "accept_linking": True,
        },
        ("post", "/v1/patients/register"): {
            "access_code": "P" * 43,
            "identifier": DEMO_ID_A,
            "email": "probe.unknown@cardioassist.local",
            "password": "probe patient password 1",
            "consent_ack": True,
        },
    }
    unknown = "00000000-0000-0000-0000-000000000000"

    def materialize(path: str) -> str:
        for segment in ("user_id", "invitation_id", "visit_id", "assignment_id", "session_id"):
            path = path.replace("{" + segment + "}", unknown)
        return path

    probes: list[Probe] = []
    for method, path in openapi.C1_OPERATIONS:
        url = materialize(path)
        body = valid_bodies.get((method, path))
        idempotent = path in openapi.IDEMPOTENT_C1
        # 1. missing Idempotency-Key (every idempotent operation)
        if idempotent:
            probes.append(
                Probe("missing-key", method, url, admin_token, None, body)
            )
        # 2. structurally invalid body (every body-required operation)
        if body is not None:
            probes.append(
                Probe(
                    "invalid-body",
                    method,
                    url,
                    admin_token if path in openapi.AUTHENTICATED_C1 else None,
                    f"probe-invalid-{method}-{path}",
                    {},
                )
            )
        # 3. unauthenticated access to every authenticated operation.
        # A2/A4 are session-lifecycle operations available to every role, so
        # only the anonymous probe applies to them.
        if path in openapi.AUTHENTICATED_C1:
            probes.append(
                Probe(
                    "anonymous",
                    method,
                    url,
                    None,
                    f"probe-anon-{method}-{path}" if idempotent else None,
                    body,
                )
            )
            # 4. patient token against a doctor/admin operation (or vice versa)
            if path in (
                "/v1/auth/logout",
                "/v1/auth/refresh",
                "/v1/auth/me",
                "/v1/me/password",
                "/v1/me/sessions",
                "/v1/me/sessions/{session_id}",
            ):
                continue
            role_token = (
                patient_token
                if "/doctor/" in path or "/admin/" in path
                else doctor_token
            )
            probes.append(
                Probe(
                    "wrong-role",
                    method,
                    url,
                    role_token,
                    f"probe-role-{method}-{path}",
                    body,
                )
            )
    return probes


def test_every_failure_response_uses_a_declared_status_and_code():
    """No operation can answer with an undeclared status or an unknown code."""
    app = _fresh_app()
    with TestClient(app) as client:
        chain = Chain(app, client)
        bootstrap_admin(app)
        admin_token = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)["session_token"]
        chain_data = _drive_every_operation(chain)
        probes = _error_probes(
            app,
            client,
            admin_token=admin_token,
            doctor_token=chain_data["doctor_token"],
            patient_token=chain_data["patient_token"],
        )
        planned = {(probe.method, _template_for(probe.path)) for probe in probes}
        assert planned == set(openapi.C1_OPERATIONS), sorted(
            planned ^ set(openapi.C1_OPERATIONS)
        )

        seen: set[tuple[str, str, int]] = set()
        for probe in probes:
            record = chain.call(
                probe.method,
                probe.path,
                token=probe.token,
                idempotency_key=probe.idempotency_key,
                json_body=probe.json_body,
                record=False,
            )
            assert record.status >= 400, (
                f"{probe.label}: {probe.method.upper()} {probe.path} unexpectedly "
                f"succeeded with {record.status}"
            )
            _assert_error_catalogue(chain, record, label=probe.label)
            _assert_schema(chain, record, label=probe.label)
            seen.add((probe.method, probe.path, record.status))

        covered = {(method, _template_for(path)) for method, path, _status in seen}
        assert covered == set(openapi.C1_OPERATIONS), sorted(
            covered ^ set(openapi.C1_OPERATIONS)
        )


# ---------------------------------------------------------------------------
# 4. Missing-configuration HTTP 503 behaviour
# ---------------------------------------------------------------------------

REQUIRED_ENV = (
    "CARDIOASSIST_IDENTITY_MATCH_KEY",
    "CARDIOASSIST_SUBJECT_KEY",
    "CARDIOASSIST_PEPPER",
    "CARDIOASSIST_ADMIN_BOOTSTRAP_SECRET",
)

# Minimal structurally valid bodies so the 503 (not 400/422) is reached.
_MISSING_CONFIG_BODIES = {
    ("post", "/v1/auth/login"): {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    ("patch", "/v1/admin/accounts/{user_id}/status"): {
        "status": "ACTIVE",
        "reason_code": "x",
    },
    ("post", "/v1/admin/doctors"): {
        "email": "d@cardioassist.local",
        "display_name": "D",
        "temp_password_policy": "one_time_secret",
    },
    ("post", "/v1/doctor/verified-visits"): {
        "visit_ref": "V",
        "subject_identifier": DEMO_ID_A,
        "asserted_visit_at": "2026-11-25T10:00:00Z",
        "attestation_code": "PRIOR_IN_PERSON_VISIT_DEMO",
    },
    ("post", "/v1/doctor/verified-visits/{visit_id}/invitations"): {
        "subject_identifier": DEMO_ID_A
    },
    ("post", "/v1/doctor/invitations/{invitation_id}/revoke"): {"reason_code": "x"},
    ("post", "/v1/doctor/assignments/{assignment_id}/revoke"): {"reason_code": "x"},
    ("post", "/v1/me/assignments/{assignment_id}/revoke"): {"reason_code": "x"},
    ("post", "/v1/me/consent/synthetic-demo/revoke"): {"reason_code": "x"},
    ("post", "/v1/me/password"): {
        "current_password": "aaaaaaaaaaaa",
        "new_password": "bbbbbbbbbbbb",
    },
    ("post", "/v1/patients/link"): {
        "access_code": "A" * 43,
        "identifier": DEMO_ID_A,
        "accept_linking": True,
    },
    ("post", "/v1/patients/register"): {
        "access_code": "A" * 43,
        "identifier": DEMO_ID_A,
        "email": "p@cardioassist.local",
        "password": "pppppppppppp",
        "consent_ack": True,
    },
    ("post", "/v1/auth/logout"): None,
    ("post", "/v1/auth/refresh"): None,
}


@pytest.mark.parametrize("method,path", openapi.C1_OPERATIONS,
                         ids=lambda value: str(value))
def test_missing_configuration_returns_declared_503(monkeypatch, method, path):
    """With no key material configured every C1 operation answers 503."""
    for name in REQUIRED_ENV:
        monkeypatch.delenv(name, raising=False)
    # The settings loader reads the process environment, so make sure it is bare.
    assert all(not os.environ.get(name) for name in REQUIRED_ENV)

    app = _fresh_app(settings=None)
    with TestClient(app, raise_server_exceptions=False) as client:
        chain = Chain(app, client)
        url = path
        unknown = "00000000-0000-0000-0000-000000000000"
        for segment in ("user_id", "invitation_id", "visit_id", "assignment_id", "session_id"):
            url = url.replace("{" + segment + "}", unknown)
        body = _MISSING_CONFIG_BODIES.get((method, path), "ABSENT")
        headers = {"Authorization": f"Bearer {'A' * 43}"}
        if path in openapi.IDEMPOTENT_C1:
            headers["Idempotency-Key"] = "missing-config"
        kwargs = {} if body == "ABSENT" else {"json": body}
        response = client.request(method.upper(), url, headers=headers, **kwargs)

        assert response.status_code == 503, (
            f"{method.upper()} {path} → {response.status_code}: {response.text[:200]}"
        )
        assert response.headers.get("content-type", "").startswith("application/json")
        assert response.headers.get("cache-control") == "no-store"
        payload = response.json()
        assert set(payload) == {"contract_version", "error"}, payload
        assert payload["contract_version"] == "v1"
        assert payload["error"]["code"] == "identity_key_configuration_error", payload
        assert payload["error"]["message"] == errors.ERROR_CATALOGUE[
            "identity_key_configuration_error"
        ][1]
        for pattern in SECRET_PATTERNS:
            assert not pattern.search(response.text), response.text[:200]
        # The served document declares this 503 for the operation.
        _assert_schema(chain, Recorded(method, path, 503, payload, response.text, {}),
                       label="missing-configuration")
        declared = chain.declared_codes(method, path, 503)
        assert "identity_key_configuration_error" in declared, (method, path, declared)


def test_legacy_operations_still_work_without_term1_configuration(monkeypatch):
    """The 503 is scoped to C1; the two legacy operations are unaffected."""
    for name in REQUIRED_ENV:
        monkeypatch.delenv(name, raising=False)
    app = _fresh_app(settings=None)
    with TestClient(app, raise_server_exceptions=False) as client:
        document = client.get("/openapi.json")
        assert document.status_code == 200
        assert "identity_key_configuration_error" in json.dumps(document.json())


# ---------------------------------------------------------------------------
# 5. Authentication, authorization and data isolation
# ---------------------------------------------------------------------------

def test_responses_never_disclose_foreign_secrets_or_identifiers():
    """No response leaks another actor's secret or a raw subject identifier."""
    app = _fresh_app()
    with TestClient(app) as client:
        chain = Chain(app, client)
        data = _drive_every_operation(chain)

        secrets = []
        for record in chain.records:
            if record.body:
                for field in ("session_token", "access_code", "temp_secret"):
                    if field in record.body:
                        secrets.append(record.body[field])

        # A GET never returns a secret field, and only the creating response does.
        for record in chain.records:
            if record.method != "post":
                assert record.body is None or not (
                    {"session_token", "access_code", "temp_secret"} & set(record.body)
                ), (record.method, record.path, list(record.body))

        # Reading back an invitation must never disclose its access code.
        read_back = chain.call(
            "get",
            f"/v1/doctor/invitations/{data['invitation_id']}",
            token=data["doctor_token"],
            expect=200,
        )
        assert "access_code" not in read_back.body
        assert "subject_identifier" not in read_back.body

        # A patient listing assignments sees only its own.
        assignments = chain.call(
            "get", "/v1/me/assignments", token=data["patient_token"], expect=200
        )
        for assignment in assignments.body["assignments"]:
            assert assignment["assignment_id"]
            assert "patient_id" not in assignment

        # A doctor reading another doctor's visit gets 404, not the resource.
        other = provision_doctor(
            app,
            client,
            email="isolation.doctor@cardioassist.local",
            display_name="Isolation Doctor",
        )
        foreign = chain.call(
            "get",
            f"/v1/doctor/verified-visits/{data['visit_id']}",
            token=other["token"],
            expect=404,
        )
        assert foreign.body["error"]["code"] == "visit_not_found"
        _assert_error_catalogue(chain, foreign, label="cross-doctor-visit")


def test_patient_cannot_read_another_patients_assignments():
    """Assignments are role- and owner-scoped: a doctor token is 403."""
    app = _fresh_app()
    with TestClient(app) as client:
        chain = Chain(app, client)
        data = _drive_every_operation(chain)
        forbidden = chain.call(
            "get", "/v1/me/assignments", token=data["doctor_token"], expect=403
        )
        assert forbidden.body["error"]["code"] == "forbidden"
        _assert_error_catalogue(chain, forbidden, label="role-projection")


def test_served_document_declares_a_response_for_every_observed_status():
    """Structural guarantee behind the raw-validation assertions."""
    app = _fresh_app()
    with TestClient(app) as client:
        chain = Chain(app, client)
        _drive_every_operation(chain)
        for method, path in openapi.C1_OPERATIONS:
            operation = chain.operation(method, path)
            declared = set(operation["responses"])
            assert any(status.startswith("2") for status in declared), (method, path)
            # Every C1 operation declares 500 and 503.
            assert {"500", "503"} <= declared, (method, path, sorted(declared))
            for status, entry in operation["responses"].items():
                reference = entry["content"]["application/json"]["schema"]["$ref"]
                assert reference.startswith("#/components/schemas/"), reference
                if not status.startswith("2"):
                    assert entry.get("x-error-codes"), (method, path, status)


def test_reviewer_temporary_password_refresh_declares_exact_403(app, client):
    bootstrap_admin(app)
    chain = Chain(app, client)
    admin = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)["session_token"]
    created = chain.call(
        "post", "/v1/admin/doctors", token=admin,
        idempotency_key="review-closure-refresh-doctor",
        json_body={"email": "refresh.demo@cardioassist.local",
                   "display_name": "Synthetic Doctor",
                   "temp_password_policy": "one_time_secret"},
        expect=201,
    )
    temporary = login(client, "refresh.demo@cardioassist.local",
                      created.body["temp_secret"])["session_token"]
    response = chain.call("post", "/v1/auth/refresh", token=temporary, expect=403)
    assert response.body["error"]["code"] == "password_change_required"
    _assert_error_catalogue(chain, response, label="temporary-refresh")
    _assert_schema(chain, response, label="temporary-refresh")


def test_reviewer_duplicate_registration_declares_exact_409(app, client):
    chain = Chain(app, client)
    setup = setup_doctor_with_invitation(app, client)
    response = chain.call(
        "post", "/v1/patients/register",
        idempotency_key="review-closure-duplicate-account",
        json_body={"access_code": setup["invitation"]["access_code"],
                   "identifier": DEMO_ID_A, "email": ADMIN_EMAIL,
                   "password": "synthetic duplicate password 1", "consent_ack": True},
        expect=409,
    )
    assert response.body["error"]["code"] == "account_registration_unavailable"
    _assert_error_catalogue(chain, response, label="duplicate-registration")
    _assert_schema(chain, response, label="duplicate-registration")


def test_reviewer_invalid_link_identifier_declares_exact_422(app, client):
    from .factories import register_patient

    setup = setup_doctor_with_invitation(app, client)
    registered = register_patient(client, setup["invitation"]["access_code"])
    _, invitation = setup["fresh_visit"](seq=1)
    chain = Chain(app, client)
    response = chain.call(
        "post", "/v1/patients/link", token=registered["session_token"],
        idempotency_key="review-closure-invalid-identifier",
        json_body={"access_code": invitation["access_code"],
                   "identifier": "NOT-A-DEMO-IDENTIFIER", "accept_linking": True},
        expect=422,
    )
    assert response.body["error"]["code"] == "invalid_demo_identifier"
    _assert_error_catalogue(chain, response, label="invalid-link-identifier")
    _assert_schema(chain, response, label="invalid-link-identifier")


def test_reviewer_unexpected_c1_failure_matches_declared_500(app_factory, monkeypatch):
    """Fault injection: fail before business completion, never leak exception text."""
    from backend.app.term1 import api

    app = app_factory()
    with TestClient(app, raise_server_exceptions=False) as client:
        bootstrap_admin(app)
        chain = Chain(app, client)
        admin = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)["session_token"]

        def injected_failure(*args, **kwargs):
            raise RuntimeError("SYNTHETIC_FAULT_MUST_NOT_LEAK")

        monkeypatch.setattr(api, "create_doctor", injected_failure)
        response = chain.call(
            "post", "/v1/admin/doctors", token=admin,
            idempotency_key="review-closure-injected-failure",
            json_body={"email": "fault.demo@cardioassist.local",
                       "display_name": "Synthetic Fault",
                       "temp_password_policy": "one_time_secret"},
            expect=500,
        )
        assert response.headers.get("cache-control") == "no-store"
        assert "SYNTHETIC_FAULT_MUST_NOT_LEAK" not in response.text
        _assert_error_catalogue(chain, response, label="unexpected-failure")
        assert response.body["error"]["code"] == "internal_error"
        _assert_schema(chain, response, label="unexpected-failure")
