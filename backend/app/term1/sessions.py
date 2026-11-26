"""Session tokens, login/logout/refresh, password change and rate limiting.

Session model (P-03/P-04):

* 32-byte CSPRNG token, base64url with no padding, returned exactly once.
* Only ``sha256(token)`` is stored, alongside a non-identity ``session_key_id``.
* Absolute lifetime 8 h; idle lifetime 30 min, evaluated on every use.
* Refresh atomically revokes the presented token and issues a new one. Because
  rotation runs inside ``BEGIN IMMEDIATE`` and requires ``revoked_at IS NULL`` on
  the presented row, concurrent refreshes with the same token produce exactly
  one new session.

Login rate limiting (P-06/P-24) is durable and independent per account and per
source (an "account" bucket is keyed by the submitted email digest so that
unknown emails are throttled too, and a "source" bucket by a hashed client key
derived from the peer address — arbitrary ``X-Forwarded-For`` headers are never
trusted). Failed attempts are recorded outside the business transaction.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from . import constants, crypto
from .accounts import find_account_by_email, profile_id_for
from .audit import record
from .errors import ApiError, api_error
from .models import LoginAttempt, Session as SessionModel, UserAccount
from .timeutil import Clock, from_iso, to_iso


# --- durable failure counters -------------------------------------------------
def login_buckets(pepper: bytes, *, email_norm: str | None, source_key: str) -> dict[str, str]:
    buckets = {"source": crypto.bucket_key_hash(pepper, "source", source_key)}
    if email_norm:
        buckets["account"] = crypto.bucket_key_hash(pepper, "account", email_norm)
    return buckets


def count_failures(session: Session, bucket_key_hash: str, *, since: str) -> int:
    return int(
        session.execute(
            select(func.count())
            .select_from(LoginAttempt)
            .where(
                LoginAttempt.bucket_key_hash == bucket_key_hash,
                LoginAttempt.created_at > since,
            )
        ).scalar_one()
    )


def is_locked(session: Session, buckets: dict[str, str], *, clock: Clock) -> bool:
    since = to_iso(clock.now() - timedelta(seconds=constants.LOGIN_WINDOW_SECONDS))
    return any(
        count_failures(session, bucket_hash, since=since) >= constants.LOGIN_FAILURE_LIMIT
        for bucket_hash in buckets.values()
    )


def record_login_failure(
    session: Session, *, clock: Clock, buckets: dict[str, str], outcome: str
) -> None:
    now = clock.now_iso()
    for kind, bucket_hash in buckets.items():
        session.add(
            LoginAttempt(
                attempt_id=str(uuid.uuid4()),
                bucket_kind=kind,
                bucket_key_hash=bucket_hash,
                outcome=outcome,
                created_at=now,
            )
        )


def reset_login_failures(session: Session, *, pepper: bytes, email_norm: str) -> None:
    bucket_hash = crypto.bucket_key_hash(pepper, "account", email_norm)
    session.execute(delete(LoginAttempt).where(LoginAttempt.bucket_key_hash == bucket_hash))


def prune_attempts(session: Session, *, clock: Clock) -> None:
    cutoff = to_iso(clock.now() - timedelta(seconds=constants.LOGIN_ATTEMPT_RETENTION_SECONDS))
    session.execute(delete(LoginAttempt).where(LoginAttempt.created_at < cutoff))


# --- session lifecycle --------------------------------------------------------
def _issue_session(
    session: Session, *, clock: Clock, account: UserAccount
) -> tuple[SessionModel, str]:
    now = clock.now()
    token = crypto.new_session_token()
    row = SessionModel(
        session_id=str(uuid.uuid4()),
        user_id=account.user_id,
        token_verifier_sha256=crypto.session_verifier(token),
        session_key_id=constants.SESSION_KEY_ID,
        created_at=to_iso(now),
        expires_at=to_iso(now + timedelta(seconds=constants.SESSION_ABSOLUTE_SECONDS)),
        last_seen_at=to_iso(now),
        revoked_at=None,
        revoked_reason=None,
    )
    session.add(row)
    return row, token


def session_is_live(row: SessionModel, now: datetime) -> bool:
    if row.revoked_at is not None:
        return False
    if from_iso(row.expires_at) <= now:
        return False
    idle_deadline = from_iso(row.last_seen_at) + timedelta(seconds=constants.SESSION_IDLE_SECONDS)
    return idle_deadline > now


def account_is_usable(account: UserAccount | None) -> bool:
    return account is not None and account.status == constants.STATUS_ACTIVE


# Dummy, syntactically valid KDF parameters used when there is no usable
# account (unknown email, or a non-active account). Running the full bounded
# KDF against these parameters makes unknown, inactive and active accounts take
# comparable verification work, so an attacker cannot distinguish them by
# timing. The dummy verifier never matches a real password.
_DUMMY_PASSWORD_ALG = constants.PASSWORD_ALG
_DUMMY_PASSWORD_VERSION = constants.PASSWORD_KDF_VERSION
_DUMMY_PASSWORD_ITERATIONS = constants.PASSWORD_KDF_ITERATIONS
_DUMMY_PASSWORD_SALT_B64 = crypto.b64_encode(b"\x00" * constants.PASSWORD_SALT_BYTES)
_DUMMY_PASSWORD_VERIFIER_B64 = crypto.b64_encode(b"\x00" * constants.PASSWORD_KEY_BYTES)


def _kdf_params_for(account: UserAccount | None) -> dict[str, object]:
    """Return bounded, validated KDF parameters for one account attempt.

    Unknown or inactive accounts are verified against deterministic dummy
    parameters so the computational path matches an active account with a wrong
    password. Stored parameters are validated before any computation so a
    corrupted row can never trigger unbounded work.
    """
    if account is not None and account_is_usable(account):
        if (
            account.password_alg != constants.PASSWORD_ALG
            or account.password_version != constants.PASSWORD_KDF_VERSION
            or not isinstance(account.password_iterations, int)
            or account.password_iterations < 1
            or account.password_iterations > 10_000_000
        ):
            # Corrupted or unsupported parameters: fail closed without hashing.
            raise api_error("invalid_credentials")
        return {
            "alg": account.password_alg,
            "version": account.password_version,
            "iterations": account.password_iterations,
            "salt_b64": account.password_salt_b64,
            "verifier_b64": account.password_verifier_b64,
        }
    return {
        "alg": _DUMMY_PASSWORD_ALG,
        "version": _DUMMY_PASSWORD_VERSION,
        "iterations": _DUMMY_PASSWORD_ITERATIONS,
        "salt_b64": _DUMMY_PASSWORD_SALT_B64,
        "verifier_b64": _DUMMY_PASSWORD_VERIFIER_B64,
    }


def login(
    session: Session,
    *,
    clock: Clock,
    pepper: bytes,
    email: str,
    password: str,
    buckets: dict[str, str],
) -> dict[str, object]:
    """Authenticate and open a session; every failure is generic.

    Exactly one authoritative transaction: the lockout check, the bounded
    password-verification work and the session issuance all commit together.
    Unknown, inactive and active accounts perform comparable KDF work so the
    service does not enumerate accounts by timing.
    """
    email_norm = crypto.normalize_email(email)
    account = find_account_by_email(session, email_norm) if email_norm else None

    params = _kdf_params_for(account)
    password_ok = account is not None and account_is_usable(account) and crypto.verify_password(
        password,
        alg=params["alg"],
        version=params["version"],
        iterations=params["iterations"],
        salt_b64=params["salt_b64"],
        verifier_b64=params["verifier_b64"],
    )
    if not password_ok:
        # Failure counters are written by the caller in a separate transaction
        # after this one rolls back (C1.9): evidence must survive the rollback.
        raise api_error("invalid_credentials")

    assert account is not None and email_norm is not None
    row, token = _issue_session(session, clock=clock, account=account)
    account.last_login_at = clock.now_iso()
    reset_login_failures(session, pepper=pepper, email_norm=email_norm)
    record(
        session,
        clock=clock,
        event_type=constants.EVENT_LOGIN_SUCCEEDED,
        outcome=constants.OUTCOME_SUCCESS,
        subject_type=constants.SUBJECT_SESSION,
        subject_id=row.session_id,
        actor_user_id=account.user_id,
        payload={"role": account.role},
    )
    return {
        "user_id": account.user_id,
        "role": account.role,
        "profile_id": profile_id_for(session, account),
        "session_token": token,
        "expires_at": row.expires_at,
        "password_change_required": bool(account.password_change_required),
    }

    assert account is not None and email_norm is not None
    row, token = _issue_session(session, clock=clock, account=account)
    account.last_login_at = clock.now_iso()
    reset_login_failures(session, pepper=pepper, email_norm=email_norm)
    record(
        session,
        clock=clock,
        event_type=constants.EVENT_LOGIN_SUCCEEDED,
        outcome=constants.OUTCOME_SUCCESS,
        subject_type=constants.SUBJECT_SESSION,
        subject_id=row.session_id,
        actor_user_id=account.user_id,
        payload={"role": account.role},
    )
    return {
        "user_id": account.user_id,
        "role": account.role,
        "profile_id": profile_id_for(session, account),
        "session_token": token,
        "expires_at": row.expires_at,
        "password_change_required": bool(account.password_change_required),
    }


def _load_live_session(
    session: Session, *, clock: Clock, token: str, touch: bool
) -> tuple[SessionModel, UserAccount]:
    verifier = crypto.session_verifier(token)
    row = session.execute(
        select(SessionModel).where(SessionModel.token_verifier_sha256 == verifier)
    ).scalar_one_or_none()
    now = clock.now()
    if row is None or not session_is_live(row, now):
        raise api_error("invalid_session")
    account = session.execute(
        select(UserAccount).where(UserAccount.user_id == row.user_id)
    ).scalar_one_or_none()
    if not account_is_usable(account):
        raise api_error("invalid_session")
    if touch:
        row.last_seen_at = to_iso(now)
    return row, account


def authenticate(
    session: Session, *, clock: Clock, token: str, touch: bool = True
) -> tuple[SessionModel, UserAccount]:
    return _load_live_session(session, clock=clock, token=token, touch=touch)


def logout(session: Session, *, clock: Clock, token: str) -> dict[str, bool]:
    row, account = _load_live_session(session, clock=clock, token=token, touch=False)
    row.revoked_at = clock.now_iso()
    row.revoked_reason = "logout"
    record(
        session,
        clock=clock,
        event_type=constants.EVENT_LOGOUT,
        outcome=constants.OUTCOME_SUCCESS,
        subject_type=constants.SUBJECT_SESSION,
        subject_id=row.session_id,
        actor_user_id=account.user_id,
    )
    return {"revoked": True}


def refresh(session: Session, *, clock: Clock, token: str) -> dict[str, object]:
    """Rotate the presented session atomically; a stale token cannot refresh."""
    row, account = _load_live_session(session, clock=clock, token=token, touch=False)
    row.revoked_at = clock.now_iso()
    row.revoked_reason = "rotated"
    new_row, new_token = _issue_session(session, clock=clock, account=account)
    record(
        session,
        clock=clock,
        event_type=constants.EVENT_SESSION_REFRESHED,
        outcome=constants.OUTCOME_SUCCESS,
        subject_type=constants.SUBJECT_SESSION,
        subject_id=new_row.session_id,
        actor_user_id=account.user_id,
        payload={"rotated_from": row.session_id},
    )
    return {"session_token": new_token, "expires_at": new_row.expires_at}


def change_password(
    session: Session,
    *,
    clock: Clock,
    token: str,
    current_password: str,
    new_password: str,
) -> dict[str, object]:
    """Change the password, revoke every other session, never return a secret."""
    row, account = _load_live_session(session, clock=clock, token=token, touch=False)
    if not crypto.verify_password(
        current_password,
        alg=account.password_alg,
        version=account.password_version,
        iterations=account.password_iterations,
        salt_b64=account.password_salt_b64,
        verifier_b64=account.password_verifier_b64,
    ):
        raise api_error("invalid_credentials")
    if crypto.password_problem(new_password) is not None:
        raise api_error("password_policy_violation")
    if new_password.encode("utf-8") == current_password.encode("utf-8"):
        raise api_error("password_unchanged")

    kdf = crypto.hash_password(new_password)
    account.password_alg = str(kdf["password_alg"])
    account.password_version = int(kdf["password_version"])
    account.password_iterations = int(kdf["password_iterations"])
    account.password_salt_b64 = str(kdf["password_salt_b64"])
    account.password_verifier_b64 = str(kdf["password_verifier_b64"])
    account.password_changed_at = clock.now_iso()
    account.password_change_required = False

    others = session.execute(
        select(SessionModel).where(
            SessionModel.user_id == account.user_id,
            SessionModel.revoked_at.is_(None),
            SessionModel.session_id != row.session_id,
        )
    ).scalars().all()
    now = clock.now_iso()
    for other in others:
        other.revoked_at = now
        other.revoked_reason = "password_changed"
    record(
        session,
        clock=clock,
        event_type=constants.EVENT_PASSWORD_CHANGED,
        outcome=constants.OUTCOME_SUCCESS,
        subject_type=constants.SUBJECT_USER_ACCOUNT,
        subject_id=account.user_id,
        actor_user_id=account.user_id,
        payload={"revoked_other_sessions": len(others)},
    )
    return {
        "user_id": account.user_id,
        "changed_at": account.password_changed_at,
        "password_change_required": False,
        "revoked_other_sessions": len(others),
    }


def list_sessions(
    session: Session, *, clock: Clock, token: str
) -> dict[str, object]:
    current, account = _load_live_session(session, clock=clock, token=token, touch=True)
    now = clock.now()
    rows = session.execute(
        select(SessionModel)
        .where(SessionModel.user_id == account.user_id)
        .order_by(SessionModel.created_at.desc())
    ).scalars().all()
    return {
        "sessions": [
            {
                "session_id": row.session_id,
                "created_at": row.created_at,
                "expires_at": row.expires_at,
                "last_seen_at": row.last_seen_at,
                "revoked_at": row.revoked_at,
                "current": row.session_id == current.session_id,
                "active": session_is_live(row, now),
            }
            for row in rows
        ]
    }


def revoke_session(
    session: Session, *, clock: Clock, token: str, target_session_id: str
) -> dict[str, object]:
    current, account = _load_live_session(session, clock=clock, token=token, touch=True)
    row = session.execute(
        select(SessionModel).where(
            SessionModel.session_id == target_session_id,
            SessionModel.user_id == account.user_id,
        )
    ).scalar_one_or_none()
    if row is None:
        # Wrong owner and nonexistent are indistinguishable (404).
        raise api_error("not_found")
    if row.revoked_at is None:
        row.revoked_at = clock.now_iso()
        row.revoked_reason = "user_revoked"
        record(
            session,
            clock=clock,
            event_type=constants.EVENT_SESSION_REVOKED,
            outcome=constants.OUTCOME_SUCCESS,
            subject_type=constants.SUBJECT_SESSION,
            subject_id=row.session_id,
            actor_user_id=account.user_id,
            payload={"self": row.session_id == current.session_id},
        )
    return {"revoked": True, "session_id": row.session_id}


def current_account(session: Session, *, clock: Clock, token: str) -> dict[str, object]:
    _row, account = _load_live_session(session, clock=clock, token=token, touch=True)
    return {
        "user_id": account.user_id,
        "role": account.role,
        "status": account.status,
        "profile_id": profile_id_for(session, account),
        "password_change_required": bool(account.password_change_required),
    }


def rate_limited_error() -> ApiError:
    return api_error("rate_limited", retry_after=constants.LOGIN_LOCK_SECONDS)
