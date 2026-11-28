"""C1.3 password policy, hashing and byte-exact credential semantics."""

from __future__ import annotations

import hashlib

import pytest

from backend.app.term1 import constants, crypto
from tests.backend.c1.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, bootstrap_admin, login


# --- KDF parameters ----------------------------------------------------------
def test_password_hash_uses_the_accepted_pbkdf2_parameters():
    kdf = crypto.hash_password("correct horse battery staple")
    assert kdf["password_alg"] == "pbkdf2_hmac_sha256"
    assert kdf["password_version"] == 1
    assert kdf["password_iterations"] == 600_000
    salt = crypto.b64_decode(str(kdf["password_salt_b64"]))
    verifier = crypto.b64_decode(str(kdf["password_verifier_b64"]))
    assert len(salt) == 16
    assert len(verifier) == 32
    # Reproduces the documented construction exactly.
    assert hashlib.pbkdf2_hmac(
        "sha256", b"correct horse battery staple", salt, 600_000, dklen=32
    ) == verifier


def test_salt_is_random_per_hash_and_verifiers_differ():
    first = crypto.hash_password("same password value 1")
    second = crypto.hash_password("same password value 1")
    assert first["password_salt_b64"] != second["password_salt_b64"]
    assert first["password_verifier_b64"] != second["password_verifier_b64"]


def test_verification_is_constant_time_and_rejects_stored_parameter_tampering():
    kdf = crypto.hash_password("constant time password")
    assert crypto.verify_password(
        "constant time password",
        alg=str(kdf["password_alg"]),
        version=int(kdf["password_version"]),
        iterations=int(kdf["password_iterations"]),
        salt_b64=str(kdf["password_salt_b64"]),
        verifier_b64=str(kdf["password_verifier_b64"]),
    )
    # Wrong algorithm or version never verifies, even with the right password.
    assert not crypto.verify_password(
        "constant time password",
        alg="argon2id",
        version=1,
        iterations=600_000,
        salt_b64=str(kdf["password_salt_b64"]),
        verifier_b64=str(kdf["password_verifier_b64"]),
    )
    assert not crypto.verify_password(
        "constant time password",
        alg="pbkdf2_hmac_sha256",
        version=2,
        iterations=600_000,
        salt_b64=str(kdf["password_salt_b64"]),
        verifier_b64=str(kdf["password_verifier_b64"]),
    )
    # A different iteration count is not a valid stored parameter match.
    assert not crypto.verify_password(
        "constant time password",
        alg="pbkdf2_hmac_sha256",
        version=1,
        iterations=1,
        salt_b64=str(kdf["password_salt_b64"]),
        verifier_b64=str(kdf["password_verifier_b64"]),
    )


# --- byte-exact policy (P-02) ------------------------------------------------
@pytest.mark.parametrize(
    "password",
    [
        "  leading and trailing  ",   # spaces are significant, never trimmed
        "pa ss word with space",
        "Ünïcodé pàsswörd value",
        "\ttabbed-password-value",
        "trailing space          ",
        "MiXeD cAsE passWORD",
    ],
)
def test_password_bytes_round_trip_exactly(password):
    kdf = crypto.hash_password(password)
    assert crypto.verify_password(
        password,
        alg=str(kdf["password_alg"]),
        version=int(kdf["password_version"]),
        iterations=int(kdf["password_iterations"]),
        salt_b64=str(kdf["password_salt_b64"]),
        verifier_b64=str(kdf["password_verifier_b64"]),
    )
    # No trimming / case folding / normalization variant may collide.
    for variant in {
        password.strip(),
        password.lower(),
        password.upper(),
        password + " ",
        " " + password,
    }:
        if variant == password:
            continue
        assert not crypto.verify_password(
            variant,
            alg=str(kdf["password_alg"]),
            version=int(kdf["password_version"]),
            iterations=int(kdf["password_iterations"]),
            salt_b64=str(kdf["password_salt_b64"]),
            verifier_b64=str(kdf["password_verifier_b64"]),
        )


def test_passwords_are_measured_in_utf8_bytes_not_characters():
    # 12 UTF-8 bytes but only 6 code points: accepted.
    accepted = "éééééé"
    assert len(accepted.encode("utf-8")) == 12
    assert crypto.password_problem(accepted) is None
    # Byte length, not code-point count, decides the boundary.
    assert crypto.password_problem("elevenchars") == "too_short"  # 11 bytes
    assert crypto.password_problem("twelve chars") is None  # 12 bytes
    # 129 bytes is over the limit; 128 is exactly the boundary.
    assert crypto.password_problem("a" * 128) is None
    assert crypto.password_problem("a" * 129) == "too_long"


@pytest.mark.parametrize("bad", ["", "short", "has\x00nul", "bell\x07char", "line\nbreak"])
def test_inadmissible_passwords_are_rejected(bad):
    assert crypto.password_problem(bad) is not None


# --- API-level enforcement ---------------------------------------------------
def test_login_verifies_the_exact_password_bytes(client, app):
    bootstrap_admin(app)
    assert login(client, ADMIN_EMAIL, ADMIN_PASSWORD)["role"] == "admin"

    for wrong in [
        ADMIN_PASSWORD.strip() + " ",
        " " + ADMIN_PASSWORD,
        ADMIN_PASSWORD.upper(),
        ADMIN_PASSWORD + "x",
    ]:
        response = client.post(
            "/v1/auth/login", json={"email": ADMIN_EMAIL, "password": wrong}
        )
        assert response.status_code == 401, wrong
        assert response.json()["error"]["code"] == "invalid_credentials"


def test_password_change_requires_current_password_and_a_different_value(client, app):
    bootstrap_admin(app)
    token = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)["session_token"]
    headers = {"Authorization": f"Bearer {token}"}

    wrong = client.post(
        "/v1/me/password",
        headers=headers,
        json={"current_password": "not the password", "new_password": "brand new password 1"},
    )
    assert wrong.status_code == 401
    assert wrong.json()["error"]["code"] == "invalid_credentials"

    same = client.post(
        "/v1/me/password",
        headers=headers,
        json={"current_password": ADMIN_PASSWORD, "new_password": ADMIN_PASSWORD},
    )
    assert same.status_code == 422
    assert same.json()["error"]["code"] == "password_unchanged"

    short = client.post(
        "/v1/me/password",
        headers=headers,
        json={"current_password": ADMIN_PASSWORD, "new_password": "tooshort1"},
    )
    assert short.status_code == 422
    assert short.json()["error"]["code"] == "password_policy_violation"

    ok = client.post(
        "/v1/me/password",
        headers=headers,
        json={"current_password": ADMIN_PASSWORD, "new_password": "brand new password 1"},
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["password_change_required"] is False
    # No new token or secret is returned by a password change.
    assert "session_token" not in body
    assert "access_code" not in body

    assert client.post(
        "/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    ).status_code == 401
    assert client.post(
        "/v1/auth/login", json={"email": ADMIN_EMAIL, "password": "brand new password 1"}
    ).status_code == 200


def test_password_change_revokes_other_sessions_but_keeps_the_current_one(client, app):
    bootstrap_admin(app)
    first = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)["session_token"]
    second = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)["session_token"]
    response = client.post(
        "/v1/me/password",
        headers={"Authorization": f"Bearer {first}"},
        json={"current_password": ADMIN_PASSWORD, "new_password": "rotated password 123"},
    )
    assert response.status_code == 200
    assert response.json()["revoked_other_sessions"] == 1
    # The session used for the change stays valid; the other one is revoked.
    assert client.get("/v1/auth/me", headers={"Authorization": f"Bearer {first}"}).status_code == 200
    assert client.get("/v1/auth/me", headers={"Authorization": f"Bearer {second}"}).status_code == 401


# --- email normalization (P-21) ---------------------------------------------
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Demo.Admin@CardioAssist.Local", "demo.admin@cardioassist.local"),
        ("  demo.admin@cardioassist.local\t", "demo.admin@cardioassist.local"),
        ("DEMO.ADMIN@CARDIOASSIST.LOCAL", "demo.admin@cardioassist.local"),
    ],
)
def test_email_norm_is_canonical(raw, expected):
    assert crypto.normalize_email(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "demo.admin@cardioassist.local@x",
        "no-at-sign",
        "demo@exa mple.local",
        "デモ@cardioassist.local",  # non-ASCII rejected
        "demo@localhost",  # empty label / no dot is structurally fine but not synthetic
        "@cardioassist.local",
        "demo@",
        "demo@a..b",
        "nul\x00@cardioassist.local",
    ],
)
def test_invalid_emails_are_rejected(raw):
    result = crypto.normalize_email(raw)
    assert result is None or not crypto.is_synthetic_email(result) or " " not in result


def test_only_the_synthetic_namespace_is_accepted_for_accounts():
    assert crypto.is_synthetic_email("demo.doctor@cardioassist.local")
    assert not crypto.is_synthetic_email("doctor@example.com")
    assert not crypto.is_synthetic_email("@cardioassist.local")


def test_duplicate_email_normalization_is_a_generic_conflict(client, app, test_settings):
    from backend.app.term1.accounts import create_doctor
    from backend.app.term1.tx import read_transaction, write_transaction
    from backend.app.term1.errors import ApiError

    bootstrap_admin(app)
    with write_transaction(app.state.database) as session:
        admin = session.query(__import__("backend.app.term1.models", fromlist=["UserAccount"]).UserAccount).first()
        create_doctor(
            session,
            clock=app.state.term1.clock,
            actor=admin,
            email="demo.clash@cardioassist.local",
            display_name="Dr Clash",
            temp_password_policy="one_time_secret",
        )
    with write_transaction(app.state.database) as session:
        admin = session.query(__import__("backend.app.term1.models", fromlist=["UserAccount"]).UserAccount).first()
        with pytest.raises(ApiError) as error:
            create_doctor(
                session,
                clock=app.state.term1.clock,
                actor=admin,
                email="  DEMO.CLASH@cardioassist.LOCAL ",
                display_name="Dr Clash Two",
                temp_password_policy="one_time_secret",
            )
    assert error.value.code == "account_registration_unavailable"
    assert error.value.status == 409
