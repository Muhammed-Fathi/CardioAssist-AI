"""Operator-supplied Term 1 secrets (environment only; never committed, P-18).

Five independent purposes:

==========================  =========================  =====================
Environment variable        Purpose                    Minimum entropy
==========================  =========================  =====================
``CARDIOASSIST_IDENTITY_MATCH_KEY``  visit/invitation HMAC  32 bytes decoded
``CARDIOASSIST_SUBJECT_KEY``         canonical subject id   32 bytes decoded
``CARDIOASSIST_PEPPER``              idempotency/fingerprints/rate buckets
``CARDIOASSIST_ADMIN_BOOTSTRAP_SECRET`` admin bootstrap   32 bytes decoded
==========================  =========================  =====================

Values are base64 (standard or urlsafe) or 64+ hex characters. Weak, missing
or duplicated material is rejected before the service starts. The identity key
id defaults to the frozen single key ``demo-v1`` and may be overridden only for
an empty disposable database (P-11).

Readiness is evaluated lazily: the legacy ``/v1`` monitoring and prediction
routes keep working without Term 1 secrets, while every Term 1 route fails
closed with ``identity_key_configuration_error`` until the environment is
configured. Startup additionally refuses to run when the database already
contains identity-key-check rows and the configured material no longer matches.
"""

from __future__ import annotations

import base64
import hashlib
import os
import re
from dataclasses import dataclass, field

MIN_KEY_BYTES = 32
DEFAULT_IDENTITY_KEY_ID = "demo-v1"
_HEX = re.compile(r"^[0-9a-fA-F]{64,}$")

ENV_IDENTITY_MATCH_KEY = "CARDIOASSIST_IDENTITY_MATCH_KEY"
ENV_SUBJECT_KEY = "CARDIOASSIST_SUBJECT_KEY"
ENV_PEPPER = "CARDIOASSIST_PEPPER"
ENV_ADMIN_BOOTSTRAP = "CARDIOASSIST_ADMIN_BOOTSTRAP_SECRET"
ENV_IDENTITY_KEY_ID = "CARDIOASSIST_IDENTITY_KEY_ID"

_REQUIRED_VARIABLES = (ENV_IDENTITY_MATCH_KEY, ENV_SUBJECT_KEY, ENV_PEPPER)


class SettingsError(RuntimeError):
    """Raised when operator key material is absent or unusable."""


def _decode_secret(variable: str, raw: str | None) -> bytes:
    if raw is None or not raw.strip():
        raise SettingsError(f"{variable} is not configured.")
    text = raw.strip()
    if _HEX.match(text):
        return bytes.fromhex(text)
    try:
        return base64.b64decode(text.replace("-", "+").replace("_", "/"), validate=True)
    except (ValueError, TypeError) as error:
        raise SettingsError(f"{variable} must be base64 or 64+ hex characters.") from error


@dataclass(frozen=True)
class Term1Settings:
    identity_match_key: bytes = field(repr=False)
    subject_key: bytes = field(repr=False)
    pepper: bytes = field(repr=False)
    admin_bootstrap_secret: bytes | None = field(default=None, repr=False)
    identity_key_id: str = DEFAULT_IDENTITY_KEY_ID

    def __post_init__(self) -> None:
        for name in ("identity_match_key", "subject_key", "pepper"):
            value: bytes = getattr(self, name)
            if len(value) < MIN_KEY_BYTES:
                raise SettingsError(
                    f"{name} must decode to at least {MIN_KEY_BYTES} bytes."
                )
        if self.admin_bootstrap_secret is not None and len(self.admin_bootstrap_secret) < MIN_KEY_BYTES:
            raise SettingsError(
                f"{ENV_ADMIN_BOOTSTRAP} must decode to at least {MIN_KEY_BYTES} bytes."
            )
        if self.identity_match_key == self.subject_key:
            raise SettingsError("The identity-match key and subject key must be distinct.")
        if self.pepper in (self.identity_match_key, self.subject_key):
            raise SettingsError("The pepper must be independent of the identity keys.")
        if not self.identity_key_id or not self.identity_key_id.isascii():
            raise SettingsError("The identity key id must be non-empty ASCII.")
        if len(self.identity_key_id) > 64:
            raise SettingsError("The identity key id must be at most 64 characters.")

    def identity_match_key_fingerprint(self) -> str:
        """Non-secret convenience digest for operator logs."""
        return hashlib.sha256(b"identity-match:" + self.identity_match_key).hexdigest()[:12]

    def require_admin_bootstrap_secret(self) -> bytes:
        if self.admin_bootstrap_secret is None:
            raise SettingsError(f"{ENV_ADMIN_BOOTSTRAP} is required for this operation.")
        return self.admin_bootstrap_secret


def load_settings(environ: dict[str, str] | None = None) -> Term1Settings:
    """Load and validate settings; raises ``SettingsError`` when unusable."""
    source = os.environ if environ is None else environ

    def variable(name: str) -> str | None:
        value = source.get(name)
        return value if value is not None else None

    identity_match_key = _decode_secret(ENV_IDENTITY_MATCH_KEY, variable(ENV_IDENTITY_MATCH_KEY))
    subject_key = _decode_secret(ENV_SUBJECT_KEY, variable(ENV_SUBJECT_KEY))
    pepper = _decode_secret(ENV_PEPPER, variable(ENV_PEPPER))
    bootstrap_raw = variable(ENV_ADMIN_BOOTSTRAP)
    bootstrap = (
        _decode_secret(ENV_ADMIN_BOOTSTRAP, bootstrap_raw)
        if bootstrap_raw is not None and bootstrap_raw.strip()
        else None
    )
    key_id = (variable(ENV_IDENTITY_KEY_ID) or DEFAULT_IDENTITY_KEY_ID).strip()
    return Term1Settings(
        identity_match_key=identity_match_key,
        subject_key=subject_key,
        pepper=pepper,
        admin_bootstrap_secret=bootstrap,
        identity_key_id=key_id,
    )


def missing_variables(environ: dict[str, str] | None = None) -> tuple[str, ...]:
    source = os.environ if environ is None else environ
    return tuple(
        name for name in _REQUIRED_VARIABLES if not (source.get(name) or "").strip()
    )
