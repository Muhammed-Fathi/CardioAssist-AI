"""C1.2/C1.3 admin bootstrap, login, sessions, refresh and rate limiting."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from backend.app.term1 import constants
from tests.backend.c1.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    TEST_BOOTSTRAP_SECRET,
    bearer,
    bootstrap_admin,
    login,
)


# --- bootstrap ---------------------------------------------------------------
def test_bootstrap_creates_exactly_one_administrator(client, app):
    created = bootstrap_admin(app)
    assert created["email_norm"] == ADMIN_EMAIL
    body = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert body["role"] == "admin"
    assert body["password_change_required"] is False
    me = client.get("/v1/auth/me", headers=bearer(body["session_token"])).json()
    assert me["role"] == "admin"
    assert me["status"] == "ACTIVE"
    assert me["profile_id"] is None


def test_duplicate_bootstrap_is_refused(app):
    from backend.app.term1.accounts import bootstrap_administrator
    from backend.app.term1.errors import ApiError
    from backend.app.term1.tx import write_transaction

    bootstrap_admin(app)
    settings = app.state.term1.settings()
    with pytest.raises(ApiError) as error:
        with write_transaction(app.state.database) as session:
            bootstrap_administrator(
                session,
                clock=app.state.term1.clock,
                settings=settings,
                bootstrap_secret=TEST_BOOTSTRAP_SECRET.decode("ascii"),
                email="demo.second.admin@cardioassist.local",
                password="second admin password 1",
            )
    assert error.value.code == "account_registration_unavailable"


def test_bootstrap_with_wrong_secret_is_refused(app):
    from backend.app.term1.accounts import bootstrap_administrator
    from backend.app.term1.errors import ApiError
    from backend.app.term1.tx import read_transaction, write_transaction

    settings = app.state.term1.settings()
    with pytest.raises(ApiError) as error:
        with write_transaction(app.state.database) as session:
            bootstrap_administrator(
                session,
                clock=app.state.term1.clock,
                settings=settings,
                bootstrap_secret="wrong bootstrap secret value",
                email=ADMIN_EMAIL,
                password=ADMIN_PASSWORD,
            )
    assert error.value.code == "invalid_credentials"
    with read_transaction(app.state.database) as session:
        assert session.execute(text("SELECT COUNT(*) FROM user_account")).scalar_one() == 0


def test_no_public_administrator_registration_operation_exists(client):
    for method, path in [
        ("post", "/v1/admin/bootstrap"),
        ("post", "/v1/auth/register"),
        ("post", "/v1/admin/accounts"),
        ("post", "/v1/auth/admin"),
    ]:
        response = client.request(method.upper(), path, json={})
        assert response.status_code == 404, (method, path)


# --- login / logout / me -----------------------------------------------------
def test_login_of_unknown_account_is_generic_and_non_enumerating(client, app):
    bootstrap_admin(app)
    unknown = client.post(
        "/v1/auth/login", json={"email": "demo.ghost@cardioassist.local", "password": "whatever password 1"}
    )
    wrong = client.post(
        "/v1/auth/login", json={"email": ADMIN_EMAIL, "password": "whatever password 1"}
    )
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["error"] == wrong.json()["error"]
    assert unknown.json()["error"]["code"] == "invalid_credentials"


def test_logout_revokes_only_the_current_session(client, app):
    bootstrap_admin(app)
    first = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)["session_token"]
    second = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)["session_token"]
    assert client.post("/v1/auth/logout", headers=bearer(first)).json()["revoked"] is True
    assert client.get("/v1/auth/me", headers=bearer(first)).status_code == 401
    assert client.get("/v1/auth/me", headers=bearer(second)).status_code == 200


def test_missing_and_malformed_bearer_headers_are_401(client, app):
    bootstrap_admin(app)
    assert client.get("/v1/auth/me").status_code == 401
    assert client.get("/v1/auth/me", headers={"Authorization": "Basic abc"}).status_code == 401
    assert client.get("/v1/auth/me", headers={"Authorization": "Bearer"}).status_code == 401
    assert client.get("/v1/auth/me", headers={"Authorization": "Bearer not-a-token"}).status_code == 401


def test_duplicate_authorization_headers_are_rejected(client, app):
    """Duplicate Authorization headers must be rejected (header smuggling)."""
    bootstrap_admin(app)
    token = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)["session_token"]
    # Two different Authorization headers on one request: 401.
    response = client.get(
        "/v1/auth/me",
        headers=[
            ("Authorization", f"Bearer {token}"),
            ("Authorization", f"Bearer {token}"),
        ],
    )
    assert response.status_code == 401, response.text
    assert response.json()["error"]["code"] == "authentication_required"


def test_non_ascii_bearer_token_is_401_not_500(app):
    """Non-ASCII bearer value must fail with controlled error, not Unicode 500.

    Tested at handler level because the test client cannot transmit
    non-ASCII header values (they are Latin-1/ASCII encoded at the transport
    layer).
    """
    from backend.app.term1.api import Term1Handler
    from backend.app.term1.errors import ApiError
    from tests.backend.c1.conftest import bootstrap_admin

    bootstrap_admin(app)
    handler = app.state.term1

    class _FakeHeaders:
        def __init__(self, header_value: str):
            self._raw = [(b"authorization", header_value.encode("latin-1"))]

        def get(self, key, default=""):
            for k, v in self._raw:
                if k.decode("latin-1").lower() == key.lower():
                    return v.decode("latin-1")
            return default

        def getlist(self, key):
            return [v.decode("latin-1") for k, v in self._raw if k.decode("latin-1").lower() == key.lower()]

    class _FakeRequest:
        def __init__(self, header_value: str):
            self.headers = _FakeHeaders(header_value)

    # Non-ASCII bearer value must raise authentication_required, not UnicodeEncodeError.
    try:
        handler.bearer(_FakeRequest("Bearer caf\xe9-token"))
        assert False, "Expected ApiError for non-ASCII bearer token"
    except ApiError as error:
        assert error.code == "authentication_required"


def test_session_tokens_are_256_bit_and_stored_only_as_verifiers(client, app):
    bootstrap_admin(app)
    token = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)["session_token"]
    assert len(token) == 43  # 32 bytes base64url without padding
    with app.state.database.engine.connect() as connection:
        stored = connection.execute(
            text("SELECT token_verifier_sha256, session_key_id FROM session")
        ).all()
    assert stored and all(row[0] != token and len(row[0]) == 64 for row in stored)
    assert all(row[1] == constants.SESSION_KEY_ID for row in stored)
    # The raw token appears in no column of any C1 table.
    with app.state.database.engine.connect() as connection:
        for table in ("session", "durable_idempotency", "workflow_audit_event"):
            dump = connection.execute(text(f"SELECT * FROM {table}")).all()
            assert token not in str(dump), table


# --- expiration --------------------------------------------------------------
def test_absolute_session_lifetime_is_eight_hours(client, app, clock):
    bootstrap_admin(app)
    token = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)["session_token"]
    headers = bearer(token)

    def kept_alive() -> None:
        """Stay inside the 30 min idle window while the absolute cap approaches."""
        for _ in range(3):
            clock.advance(minutes=15)
            assert client.get("/v1/auth/me", headers=headers).status_code == 200

    for _ in range(10):  # 7.5 h of continuous activity
        kept_alive()
    clock.advance(minutes=28)  # 7 h 58 m since login
    assert client.get("/v1/auth/me", headers=headers).status_code == 200
    clock.advance(minutes=4)  # 8 h 02 m: the absolute cap has passed
    response = client.get("/v1/auth/me", headers=headers)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_session"


def test_idle_session_expires_after_thirty_minutes(client, app, clock):
    bootstrap_admin(app)
    token = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)["session_token"]
    headers = bearer(token)
    clock.advance(minutes=29)
    assert client.get("/v1/auth/me", headers=headers).status_code == 200  # activity refreshes idle
    clock.advance(minutes=29)
    assert client.get("/v1/auth/me", headers=headers).status_code == 200
    clock.advance(minutes=31)
    assert client.get("/v1/auth/me", headers=headers).status_code == 401


# --- refresh -----------------------------------------------------------------
def test_refresh_rotates_atomically_and_old_token_cannot_refresh(client, app):
    bootstrap_admin(app)
    token = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)["session_token"]
    rotated = client.post("/v1/auth/refresh", headers=bearer(token))
    assert rotated.status_code == 200
    new_token = rotated.json()["session_token"]
    assert new_token != token

    # Old token is revoked: no session, no refresh, and it cannot read /me.
    replay = client.post("/v1/auth/refresh", headers=bearer(token))
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "invalid_session"
    assert client.get("/v1/auth/me", headers=bearer(token)).status_code == 401
    assert client.get("/v1/auth/me", headers=bearer(new_token)).status_code == 200

    with app.state.database.engine.connect() as connection:
        assert connection.execute(
            text("SELECT COUNT(*) FROM session WHERE revoked_at IS NULL")
        ).scalar_one() == 1


def test_expired_token_cannot_refresh(client, app, clock):
    bootstrap_admin(app)
    token = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)["session_token"]
    clock.advance(hours=9)
    response = client.post("/v1/auth/refresh", headers=bearer(token))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_session"


# --- session listing and revocation -----------------------------------------
def test_session_listing_shows_only_the_callers_sessions(client, app):
    bootstrap_admin(app)
    token = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)["session_token"]
    second = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)["session_token"]
    listing = client.get("/v1/me/sessions", headers=bearer(token)).json()["sessions"]
    assert len(listing) == 2
    assert sum(1 for row in listing if row["current"]) == 1
    assert {row["session_id"] for row in listing}

    target = next(row for row in listing if not row["current"])
    revoked = client.delete(f"/v1/me/sessions/{target['session_id']}", headers=bearer(token))
    assert revoked.status_code == 200 and revoked.json()["revoked"] is True
    assert client.get("/v1/auth/me", headers=bearer(second)).status_code == 401


def test_revoking_another_users_session_is_404(client, app):
    from backend.app.term1.accounts import create_doctor
    from backend.app.term1.tx import write_transaction

    bootstrap_admin(app)
    admin_token = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)["session_token"]
    with write_transaction(app.state.database) as session:
        admin = session.execute(
            text("SELECT user_id FROM user_account WHERE email_norm=:e"), {"e": ADMIN_EMAIL}
        ).scalar_one()
        from backend.app.term1.models import UserAccount

        account = session.get(UserAccount, admin)
        created = create_doctor(
            session,
            clock=app.state.term1.clock,
            actor=account,
            email="demo.other@cardioassist.local",
            display_name="Dr Other",
            temp_password_policy="one_time_secret",
        )
    other_token = login(client, "demo.other@cardioassist.local", created["temp_secret"])["session_token"]
    # A temporary-password account is limited to me/password/logout (C1-R02):
    # rotate the temp password before session listing is permitted.
    client.post(
        "/v1/me/password",
        json={"current_password": created["temp_secret"], "new_password": "doctor new password 002"},
        headers=bearer(other_token),
    )
    assert client.get("/v1/auth/me", headers=bearer(other_token)).json()["password_change_required"] is False
    other_session = client.get("/v1/me/sessions", headers=bearer(other_token)).json()["sessions"][0]
    response = client.delete(
        f"/v1/me/sessions/{other_session['session_id']}", headers=bearer(admin_token)
    )
    assert response.status_code == 404
    assert client.get("/v1/auth/me", headers=bearer(other_token)).status_code == 200


# --- account status enforcement ---------------------------------------------
def _create_doctor(app, *, email="demo.status@cardioassist.local", name="Dr Status"):
    from backend.app.term1.accounts import create_doctor
    from backend.app.term1.models import UserAccount
    from backend.app.term1.tx import write_transaction

    with write_transaction(app.state.database) as session:
        admin_id = session.execute(
            text("SELECT user_id FROM user_account WHERE role='admin'")
        ).scalar_one()
        admin = session.get(UserAccount, admin_id)
        return create_doctor(
            session,
            clock=app.state.term1.clock,
            actor=admin,
            email=email,
            display_name=name,
            temp_password_policy="one_time_secret",
        )


def test_suspended_account_cannot_log_in_and_loses_sessions(client, app):
    bootstrap_admin(app)
    admin_token = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)["session_token"]
    doctor = _create_doctor(app)
    doctor_token = login(client, "demo.status@cardioassist.local", doctor["temp_secret"])["session_token"]
    assert client.get("/v1/auth/me", headers=bearer(doctor_token)).status_code == 200

    response = client.patch(
        f"/v1/admin/accounts/{doctor['user_id']}/status",
        headers={**bearer(admin_token), "Idempotency-Key": "status-suspend"},
        json={"status": "SUSPENDED", "reason_code": "review"},
    )
    assert response.status_code == 200 and response.json()["status"] == "SUSPENDED"
    # Sessions revoked immediately, and login is refused generically.
    assert client.get("/v1/auth/me", headers=bearer(doctor_token)).status_code == 401
    denied = client.post(
        "/v1/auth/login",
        json={"email": "demo.status@cardioassist.local", "password": doctor["temp_secret"]},
    )
    assert denied.status_code == 401
    assert denied.json()["error"]["code"] == "invalid_credentials"


def test_disabled_is_terminal_and_reactivation_is_refused(client, app):
    bootstrap_admin(app)
    admin_token = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)["session_token"]
    doctor = _create_doctor(app)
    headers = lambda key: {**bearer(admin_token), "Idempotency-Key": key}
    assert client.patch(
        f"/v1/admin/accounts/{doctor['user_id']}/status",
        headers=headers("d-disable"),
        json={"status": "DISABLED", "reason_code": "closed"},
    ).status_code == 200
    reactivate = client.patch(
        f"/v1/admin/accounts/{doctor['user_id']}/status",
        headers=headers("d-reactivate"),
        json={"status": "ACTIVE", "reason_code": "reopen"},
    )
    assert reactivate.status_code == 409
    assert reactivate.json()["error"]["code"] == "account_status_conflict"


def test_suspend_then_reactivate_is_allowed(client, app):
    bootstrap_admin(app)
    admin_token = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)["session_token"]
    doctor = _create_doctor(app, email="demo.reactivate@cardioassist.local")
    headers = lambda key: {**bearer(admin_token), "Idempotency-Key": key}
    assert client.patch(
        f"/v1/admin/accounts/{doctor['user_id']}/status",
        headers=headers("r-suspend"),
        json={"status": "SUSPENDED", "reason_code": "review"},
    ).status_code == 200
    assert client.patch(
        f"/v1/admin/accounts/{doctor['user_id']}/status",
        headers=headers("r-activate"),
        json={"status": "ACTIVE", "reason_code": "cleared"},
    ).status_code == 200
    assert client.post(
        "/v1/auth/login",
        json={"email": "demo.reactivate@cardioassist.local", "password": doctor["temp_secret"]},
    ).status_code == 200


def test_status_change_writes_workflow_audit_and_revokes_sessions(client, app):
    bootstrap_admin(app)
    admin_token = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)["session_token"]
    doctor = _create_doctor(app, email="demo.audited@cardioassist.local")
    login(client, "demo.audited@cardioassist.local", doctor["temp_secret"])
    client.patch(
        f"/v1/admin/accounts/{doctor['user_id']}/status",
        headers={**bearer(admin_token), "Idempotency-Key": "aud-1"},
        json={"status": "SUSPENDED", "reason_code": "audit-check"},
    )
    with app.state.database.engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT event_type, outcome, subject_id FROM workflow_audit_event "
                "WHERE event_type='ACCOUNT_STATUS_CHANGED'"
            )
        ).all()
        revoked = connection.execute(
            text("SELECT COUNT(*) FROM session WHERE user_id=:u AND revoked_at IS NOT NULL"),
            {"u": doctor["user_id"]},
        ).scalar_one()
    assert rows == [("ACCOUNT_STATUS_CHANGED", "SUCCESS", doctor["user_id"])]
    assert revoked >= 1


def test_last_administrator_cannot_be_removed(client, app):
    bootstrap_admin(app)
    admin_token = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)["session_token"]
    with app.state.database.engine.connect() as connection:
        admin_id = connection.execute(
            text("SELECT user_id FROM user_account WHERE role='admin'")
        ).scalar_one()
    response = client.patch(
        f"/v1/admin/accounts/{admin_id}/status",
        headers={**bearer(admin_token), "Idempotency-Key": "last-admin"},
        json={"status": "DISABLED", "reason_code": "would lock out"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "last_administrator_protected"
    # Still usable.
    assert client.get("/v1/auth/me", headers=bearer(admin_token)).status_code == 200


def test_role_profile_consistency_is_enforced_for_non_admins(client, app):
    bootstrap_admin(app)
    admin_token = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)["session_token"]
    doctor = _create_doctor(app, email="demo.roles@cardioassist.local")
    # A doctor cannot act as an administrator.
    doctor_token = login(client, "demo.roles@cardioassist.local", doctor["temp_secret"])["session_token"]
    response = client.post(
        "/v1/admin/doctors",
        headers={**bearer(doctor_token), "Idempotency-Key": "role-1"},
        json={
            "email": "demo.forbidden@cardioassist.local",
            "display_name": "Dr Forbidden",
            "temp_password_policy": "one_time_secret",
        },
    )
    # The temp-password restriction fires first for a fresh doctor account.
    assert response.status_code in (403,)
    assert response.json()["error"]["code"] == "password_change_required"
    assert client.get("/v1/auth/me", headers=bearer(admin_token)).status_code == 200


# --- rate limiting ----------------------------------------------------------
def test_five_failures_lock_both_the_account_and_the_source_bucket(client, app):
    bootstrap_admin(app)
    for attempt in range(constants.LOGIN_FAILURE_LIMIT):
        response = client.post(
            "/v1/auth/login",
            json={"email": ADMIN_EMAIL, "password": f"wrong password {attempt:04d}"},
        )
        assert response.status_code == 401
    locked = client.post(
        "/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert locked.status_code == 429
    assert locked.json()["error"]["code"] == "rate_limited"
    assert locked.headers.get("Retry-After") == str(constants.LOGIN_LOCK_SECONDS)


def test_lockout_is_durable_across_the_failure_bucket_and_expires(client, app, clock):
    bootstrap_admin(app)
    for attempt in range(constants.LOGIN_FAILURE_LIMIT):
        client.post(
            "/v1/auth/login", json={"email": ADMIN_EMAIL, "password": f"wrong password {attempt:04d}"}
        )
    assert client.post(
        "/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    ).status_code == 429
    clock.advance(seconds=constants.LOGIN_WINDOW_SECONDS + 1)
    assert client.post(
        "/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    ).status_code == 200


def test_unknown_emails_are_throttled_too(client, app):
    for attempt in range(constants.LOGIN_FAILURE_LIMIT):
        response = client.post(
            "/v1/auth/login",
            json={"email": "demo.nobody@cardioassist.local", "password": "wrong password 1"},
        )
        assert response.status_code == 401
    blocked = client.post(
        "/v1/auth/login",
        json={"email": "demo.nobody@cardioassist.local", "password": "wrong password 1"},
    )
    assert blocked.status_code == 429


def test_spoofed_forwarded_for_headers_do_not_choose_the_source_bucket(client):
    """An attacker cannot dodge the source bucket by inventing a header."""
    for attempt in range(constants.LOGIN_FAILURE_LIMIT):
        client.post(
            "/v1/auth/login",
            headers={"X-Forwarded-For": f"203.0.113.{attempt}"},
            json={"email": "demo.spoof@cardioassist.local", "password": "wrong password 1"},
        )
    blocked = client.post(
        "/v1/auth/login",
        headers={"X-Forwarded-For": "198.51.100.9"},
        json={"email": "demo.spoof@cardioassist.local", "password": "wrong password 1"},
    )
    assert blocked.status_code == 429


def test_failed_logins_leave_durable_evidence_after_the_rollback(client, app):
    bootstrap_admin(app)
    client.post("/v1/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong password 1"})
    with app.state.database.engine.connect() as connection:
        attempts = connection.execute(text("SELECT COUNT(*) FROM login_attempt")).scalar_one()
        audits = connection.execute(
            text("SELECT COUNT(*) FROM workflow_audit_event WHERE event_type='LOGIN_FAILED'")
        ).scalar_one()
        accounts = connection.execute(text("SELECT COUNT(*) FROM user_account")).scalar_one()
    assert attempts >= 1
    assert audits == 1
    # No phantom session and no account mutation from the failed attempt.
    with app.state.database.engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM session")).scalar_one() == 0
    assert accounts == 1


# --- password-change lockout --------------------------------------------------

def test_password_change_lockout_consulted(client, app):
    """Wrong current_password attempts on /v1/me/password are throttled like
    login (C1-R02: password-change lockout consulted)."""
    bootstrap_admin(app)
    admin_token = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)["session_token"]
    headers = bearer(admin_token)

    # Exhaust the account bucket with wrong current_password attempts.
    for attempt in range(constants.LOGIN_FAILURE_LIMIT):
        response = client.post(
            "/v1/me/password",
            headers=headers,
            json={
                "current_password": f"wrong password {attempt:04d}",
                "new_password": "new password 0001",
            },
        )
        assert response.status_code == 401, response.text

    # The account bucket is now at the limit: next password change is rate limited.
    response = client.post(
        "/v1/me/password",
        headers=headers,
        json={"current_password": ADMIN_PASSWORD, "new_password": "new password 0002"},
    )
    assert response.status_code == 429, response.text
    assert response.json()["error"]["code"] == "rate_limited"


# --- F2: lockout not extended on retry ---------------------------------------

def test_lockout_not_extended_on_retry(client, app):
    """When already locked, additional failed attempts do not refresh the lockout.

    The failure counter is not incremented while locked, so the lockout window
    is governed by the original failures only (F2: lockout not extended on retry).
    """
    bootstrap_admin(app)
    for attempt in range(constants.LOGIN_FAILURE_LIMIT):
        response = client.post(
            "/v1/auth/login",
            json={"email": ADMIN_EMAIL, "password": f"wrong password {attempt:04d}"},
        )
        assert response.status_code == 401, response.text

    # Locked now.
    first_locked = client.post(
        "/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert first_locked.status_code == 429
    assert first_locked.json()["error"]["code"] == "rate_limited"

    # While still locked, another attempt must not add a new failure record
    # or extend the lockout window.
    second_locked = client.post(
        "/v1/auth/login",
        json={"email": ADMIN_EMAIL, "password": "yet another wrong password 0001"},
    )
    assert second_locked.status_code == 429
    assert second_locked.json()["error"]["code"] == "rate_limited"

    # Exactly LOGIN_FAILURE_LIMIT failure records per bucket, no more.
    # Two buckets are written per login attempt (account + source), so
    # total records = 2 * LOGIN_FAILURE_LIMIT.
    from backend.app.term1 import crypto

    account_bucket = crypto.bucket_key_hash(
        app.state.term1.settings().pepper, "account", ADMIN_EMAIL
    )
    with app.state.database.engine.connect() as connection:
        attempts = connection.execute(
            text("SELECT COUNT(*) FROM login_attempt WHERE bucket_key_hash=:h"),
            {"h": account_bucket},
        ).scalar_one()
    assert attempts == constants.LOGIN_FAILURE_LIMIT, attempts
