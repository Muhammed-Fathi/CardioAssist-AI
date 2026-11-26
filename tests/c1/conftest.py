"""Fixtures for the Term 1 C1 suite.

Design rules for these tests:

* every test gets a fresh disposable SQLite file migrated with Alembic;
* operator secrets are deterministic test values supplied through the app
  factory (never a real secret, never a committed key);
* the Term 1 clock is a mutable list so tests can advance time exactly;
* race tests open *independent* engines/connections, not a shared session.
"""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.term1.settings import Term1Settings

ROOT = Path(__file__).resolve().parents[2]

# Deterministic, obviously fake test key material (32+ bytes each, all distinct).
TEST_IDENTITY_MATCH_KEY = b"c1-test-identity-match-key-0000000001"
TEST_SUBJECT_KEY = b"c1-test-subject-canonical-key-00000002"
TEST_PEPPER = b"c1-test-pepper-for-idempotency-00000000003"
TEST_BOOTSTRAP_SECRET = b"c1-test-admin-bootstrap-secret-000000000004"

BASE_TIME = datetime(2026, 11, 26, 9, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="session")
def test_settings() -> Term1Settings:
    return Term1Settings(
        identity_match_key=TEST_IDENTITY_MATCH_KEY,
        subject_key=TEST_SUBJECT_KEY,
        pepper=TEST_PEPPER,
        admin_bootstrap_secret=TEST_BOOTSTRAP_SECRET,
        identity_key_id="demo-v1",
    )


def alembic_config(database_url: str) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.attributes["database_url"] = database_url
    return config


def upgrade(database_url: str, revision: str = "head") -> None:
    command.upgrade(alembic_config(database_url), revision)


def downgrade(database_url: str, revision: str) -> None:
    command.downgrade(alembic_config(database_url), revision)


def alembic_check(database_url: str) -> None:
    command.check(alembic_config(database_url))


@pytest.fixture
def database_url(tmp_path) -> str:
    return f"sqlite:///{(tmp_path / 'c1.sqlite3').as_posix()}"


@pytest.fixture
def migrated_url(database_url) -> str:
    upgrade(database_url)
    return database_url


class MutableClock:
    """Wall-clock stand-in that only moves when a test moves it."""

    def __init__(self, start: datetime = BASE_TIME) -> None:
        self.current = start

    def __call__(self) -> datetime:
        return self.current

    def advance(self, **kwargs) -> datetime:
        self.current = self.current + timedelta(**kwargs)
        return self.current

    def set(self, moment: datetime) -> datetime:
        self.current = moment
        return self.current


@pytest.fixture
def clock() -> MutableClock:
    return MutableClock()


@pytest.fixture
def app_factory(migrated_url, clock, test_settings):
    """Build an application bound to the migrated database and test clock."""

    def build(**overrides):
        kwargs = {
            "database_url": migrated_url,
            "term1_settings": test_settings,
            "term1_clock": clock,
        }
        kwargs.update(overrides)
        return create_app(**kwargs)

    return build


@pytest.fixture
def app(app_factory):
    return app_factory()


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


# --- helpers -----------------------------------------------------------------
ADMIN_EMAIL = "demo.admin@cardioassist.local"
ADMIN_PASSWORD = "admin demo password 001"


def b64(secret: bytes) -> str:
    return base64.b64encode(secret).decode("ascii")


def bootstrap_admin(app, *, email=ADMIN_EMAIL, password=ADMIN_PASSWORD):
    """Create the administrator directly through the bootstrap path.

    Idempotent so helpers can call it defensively without creating a second
    administrator (which the service would refuse anyway).
    """
    from backend.app.term1.accounts import bootstrap_administrator
    from backend.app.term1.timeutil import Clock
    from backend.app.term1.tx import read_transaction, write_transaction

    settings = app.state.term1.settings()
    from backend.app.term1.accounts import bootstrap_status

    with read_transaction(app.state.database) as session:
        if bootstrap_status(session)["administrator_exists"]:
            return {"user_id": None, "email_norm": email, "already_present": True}
    with write_transaction(app.state.database) as session:
        return bootstrap_administrator(
            session,
            clock=app.state.term1.clock,
            settings=settings,
            bootstrap_secret=TEST_BOOTSTRAP_SECRET.decode("ascii"),
            email=email,
            password=password,
        )


def login(client, email: str, password: str) -> dict:
    response = client.post(
        "/v1/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def idem(key: str) -> dict:
    return {"Idempotency-Key": key}


def both(token: str, key: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Idempotency-Key": key}
