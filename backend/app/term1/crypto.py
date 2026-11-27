"""Cryptographic primitives for the Term 1 C1 stage (stdlib only).

Design rules enforced here:

* Passwords are opaque UTF-8 byte strings. No trimming, Unicode normalization,
  case folding or truncation happens at any stage (P-02).
* Only verifiers/digests of one-time secrets are stored; raw tokens, access
  codes and identifiers never reach the database, logs or audit rows.
* Every HMAC use has a distinct domain-separation string, and the string is
  terminated by ``0x00`` so that ``domain`` and payload cannot be confused.
* Identity digests are 64-character lowercase hex, which also survives numeric
  formatting in CSV/report exports (see the Windows runbook defect note).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import unicodedata

from . import constants

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_HEX32 = re.compile(r"^[0-9a-f]{32}$")


# --- encodings ---------------------------------------------------------------
def b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def b64_encode(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def b64_decode(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"), validate=True)


def is_hex_digest(value: str | None, *, length: int = 64) -> bool:
    if not isinstance(value, str):
        return False
    pattern = _HEX64 if length == 64 else _HEX32
    return bool(pattern.match(value))


# --- domain-separated HMAC ---------------------------------------------------
def domain_bytes(domain: str) -> bytes:
    if not domain or not domain.isascii():
        raise ValueError("HMAC domain separators must be non-empty ASCII.")
    return domain.encode("ascii") + b"\x00"


def hmac_hex(key: bytes, domain: str, message: bytes) -> str:
    if not key:
        raise ValueError("HMAC keys must not be empty.")
    return hmac.new(key, domain_bytes(domain) + message, hashlib.sha256).hexdigest()


def constant_time_equals(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


# --- identifiers -------------------------------------------------------------
def normalize_demo_identifier(raw: str) -> str | None:
    """Normalize and validate the fictitious identifier grammar (P-09).

    Whitespace around the value is trimmed and ASCII case is folded; nothing
    else is accepted. A 14-digit national-ID-shaped value fails the closed
    regex, as does any non-ASCII input.
    """
    if not isinstance(raw, str):
        return None
    candidate = raw.strip().upper()
    if not candidate or not candidate.isascii():
        return None
    if not re.match(constants.DEMO_ID_PATTERN, candidate):
        return None
    return candidate


def identifier_match_hmac(key: bytes, normalized: str) -> str:
    return hmac_hex(key, constants.DOMAIN_IDENTITY_MATCH, normalized.encode("ascii"))


def canonical_subject_id(key: bytes, normalized: str) -> str:
    return hmac_hex(key, constants.DOMAIN_SUBJECT_CANONICAL, normalized.encode("ascii"))


def subject_label(key: bytes, normalized: str) -> str:
    """Stable, non-reversible display label for a fictitious subject."""
    digest = hmac_hex(key, constants.DOMAIN_SUBJECT_LABEL, normalized.encode("ascii"))
    return f"{constants.SUBJECT_LABEL_PREFIX}{digest[:8].upper()}"


def key_check_hash(key: bytes, purpose: str, key_id: str) -> str:
    message = purpose.encode("ascii") + b"\x00" + key_id.encode("utf-8")
    return hmac_hex(key, constants.DOMAIN_KEY_CHECK, message)


# --- emails ------------------------------------------------------------------
_ASCII_WHITESPACE = " \t\n\r\f\v"


def normalize_email(raw: str) -> str | None:
    """Canonical ``email_norm`` (P-21).

    Trim leading/trailing ASCII whitespace, apply NFKC, reject non-ASCII,
    lower-case, then enforce structural limits. Returns ``None`` when the value
    cannot be canonicalized, which callers surface as a generic failure.
    """
    if not isinstance(raw, str):
        return None
    candidate = unicodedata.normalize("NFKC", raw.strip(_ASCII_WHITESPACE)).lower()
    if not candidate or not candidate.isascii():
        return None
    if any(ord(char) < 0x20 or ord(char) == 0x7F for char in candidate):
        return None
    if candidate.count("@") != 1:
        return None
    local, _, domain = candidate.partition("@")
    if not local or len(local.encode("ascii")) > 64:
        return None
    if not domain or len(domain.encode("ascii")) > 189:
        return None
    labels = domain.split(".")
    if any(not label for label in labels):
        return None
    total = len(candidate.encode("ascii"))
    if total > 254:
        return None
    return candidate


def is_synthetic_email(email_norm: str) -> bool:
    return email_norm.endswith(constants.DEMO_EMAIL_DOMAIN) and len(email_norm) > len(
        constants.DEMO_EMAIL_DOMAIN
    )


# --- passwords ---------------------------------------------------------------
def password_problem(password: str) -> str | None:
    """Return a static reason token, or ``None`` when the password is usable."""
    if not isinstance(password, str):
        return "type"
    try:
        raw = password.encode("utf-8")
    except UnicodeEncodeError:
        return "utf8"
    if len(raw) < constants.PASSWORD_MIN_BYTES:
        return "too_short"
    if len(raw) > constants.PASSWORD_MAX_BYTES:
        return "too_long"
    for char in password:
        if ord(char) == 0 or (ord(char) < 0x20) or (0x7F <= ord(char) <= 0x9F):
            return "control_character"
    return None


def _derive(password: str, salt: bytes, iterations: int) -> bytes:
    # Opaque bytes: no strip(), no normalization, no truncation.
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations, dklen=constants.PASSWORD_KEY_BYTES
    )


def hash_password(
    password: str, *, iterations: int = constants.PASSWORD_KDF_ITERATIONS
) -> dict[str, object]:
    salt = secrets.token_bytes(constants.PASSWORD_SALT_BYTES)
    verifier = _derive(password, salt, iterations)
    return {
        "password_alg": constants.PASSWORD_ALG,
        "password_version": constants.PASSWORD_KDF_VERSION,
        "password_iterations": iterations,
        "password_salt_b64": b64_encode(salt),
        "password_verifier_b64": b64_encode(verifier),
    }


def verify_password(
    password: str,
    *,
    alg: str,
    version: int,
    iterations: int,
    salt_b64: str,
    verifier_b64: str,
) -> bool:
    if alg != constants.PASSWORD_ALG or version != constants.PASSWORD_KDF_VERSION:
        return False
    if not isinstance(iterations, int) or iterations < 1:
        return False
    try:
        salt = b64_decode(salt_b64)
        expected = b64_decode(verifier_b64)
    except (ValueError, AttributeError):
        return False
    if len(salt) != constants.PASSWORD_SALT_BYTES or len(expected) != constants.PASSWORD_KEY_BYTES:
        return False
    candidate = _derive(password, salt, iterations)
    return hmac.compare_digest(candidate, expected)


# --- one-time tokens ---------------------------------------------------------
def new_session_token() -> str:
    return b64url_encode(secrets.token_bytes(constants.SESSION_TOKEN_BYTES))


def new_invitation_code() -> str:
    return b64url_encode(secrets.token_bytes(constants.INVITATION_TOKEN_BYTES))


def new_temporary_password() -> str:
    """A generated temporary password that satisfies the byte-length policy."""
    return b64url_encode(secrets.token_bytes(24))


def session_verifier(token: str) -> str:
    """SHA-256 over the exact issued token bytes (verifier-only storage)."""
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def invitation_verifier(code: str) -> str:
    # Non-ASCII access codes must not raise a Unicode error that becomes an
    # HTTP 500: encode with replacement so the hash is deterministic and the
    # lookup simply fails to match any stored invitation (C1-R04/R06).
    return hashlib.sha256(code.encode("utf-8", "replace")).hexdigest()


def actor_binding_anonymous(access_code: str) -> str:
    """Anonymous replay actor: ``anon:<first 32 hex of sha256(access code)>``.

    The binding is derived from the submitted code rather than the invitation
    row, so replay lookup happens before any invitation-state query and a
    consumed invitation is never reopened by a replay.
    """
    return "anon:" + invitation_verifier(access_code)[:32]


def unknown_code_digest(pepper: bytes, code: str) -> str:
    return hmac_hex(pepper, constants.DOMAIN_UNKNOWN_CODE_DIGEST, code.encode("utf-8", "replace"))


# --- rate limiting and idempotency ------------------------------------------
def bucket_key_hash(key: bytes, bucket: str, value: str) -> str:
    return hmac_hex(key, constants.DOMAIN_RATE_BUCKET, f"{bucket}:{value}".encode("utf-8"))


def idempotency_key_hash(pepper: bytes, raw_key: str) -> str:
    return hmac_hex(pepper, constants.DOMAIN_IDEMPOTENCY_KEY, raw_key.encode("utf-8"))


def secret_fingerprint(pepper: bytes, field: str, value: str) -> str:
    message = field.encode("utf-8") + b"\x00" + value.encode("utf-8")
    return hmac_hex(pepper, constants.DOMAIN_SECRET_FINGERPRINT, message)


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def fingerprint_pepper_ready(pepper: bytes | None) -> bool:
    return pepper is not None and len(pepper) >= 16
