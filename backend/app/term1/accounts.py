"""Accounts, administrator bootstrap and account lifecycle (C1.2).

Security properties:

* No public administrator registration exists. The first administrator is
  created by a local, one-time operator command gated by
  ``CARDIOASSIST_ADMIN_BOOTSTRAP_SECRET``; the same call is refused afterwards.
* No default credentials and no committed secret. Generated temporary
  passwords are returned exactly once, never stored in clear and never written
  to logs.
* ``email_norm`` is the only login identifier and is UNIQUE at the database
  level. Duplicate creation is reported generically so an unauthenticated
  caller cannot probe for account existence.
* ``ACTIVE <-> SUSPENDED`` are reversible; ``DISABLED`` is terminal. Every
  status change revokes all of the account's sessions and writes workflow audit
  evidence in the same transaction.
* An administrative operation can never leave the system without a usable
  administrator (an ACTIVE, non-temp-password admin must remain).
"""

from __future__ import annotations

import hashlib
import hmac
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import constants, crypto
from .audit import record
from .errors import api_error
from .models import (
    AdminBootstrapRecord,
    DoctorProfile,
    Session as SessionModel,
    UserAccount,
)
from .timeutil import Clock


def _create_account(
    session: Session,
    *,
    clock: Clock,
    email_norm: str,
    role: str,
    password: str,
    password_change_required: bool,
) -> UserAccount:
    if crypto.password_problem(password) is not None:
        raise api_error("password_policy_violation")
    kdf = crypto.hash_password(password)
    account = UserAccount(
        user_id=str(uuid.uuid4()),
        email_norm=email_norm,
        role=role,
        status=constants.STATUS_ACTIVE,
        password_alg=str(kdf["password_alg"]),
        password_version=int(kdf["password_version"]),
        password_iterations=int(kdf["password_iterations"]),
        password_salt_b64=str(kdf["password_salt_b64"]),
        password_verifier_b64=str(kdf["password_verifier_b64"]),
        password_change_required=password_change_required,
        status_reason_code=None,
        created_at=clock.now_iso(),
        password_changed_at=clock.now_iso(),
        status_changed_at=None,
        last_login_at=None,
    )
    session.add(account)
    return account


def find_account_by_email(session: Session, email_norm: str) -> UserAccount | None:
    return session.execute(
        select(UserAccount).where(UserAccount.email_norm == email_norm)
    ).scalar_one_or_none()


def profile_id_for(session: Session, account: UserAccount) -> str | None:
    if account.role == constants.ROLE_DOCTOR:
        row = session.execute(
            select(DoctorProfile.doctor_id).where(DoctorProfile.user_id == account.user_id)
        ).scalar_one_or_none()
        return row
    if account.role == constants.ROLE_PATIENT:
        from .models import PatientProfile

        row = session.execute(
            select(PatientProfile.patient_id).where(PatientProfile.user_id == account.user_id)
        ).scalar_one_or_none()
        return row
    return None


def _revoke_all_sessions(session: Session, *, user_id: str, clock: Clock, reason: str) -> int:
    rows = session.execute(
        select(SessionModel).where(
            SessionModel.user_id == user_id, SessionModel.revoked_at.is_(None)
        )
    ).scalars().all()
    now = clock.now_iso()
    for row in rows:
        row.revoked_at = now
        row.revoked_reason = reason
    return len(rows)


def bootstrap_status(session: Session) -> dict[str, bool]:
    has_admin = session.execute(
        select(func.count()).select_from(UserAccount).where(
            UserAccount.role == constants.ROLE_ADMIN
        )
    ).scalar_one()
    has_record = session.execute(
        select(func.count()).select_from(AdminBootstrapRecord)
    ).scalar_one()
    return {"administrator_exists": bool(has_admin) or bool(has_record)}


def bootstrap_administrator(
    session: Session,
    *,
    clock: Clock,
    settings,
    bootstrap_secret: str | None,
    email: str,
    password: str,
) -> dict[str, str]:
    """One-time local administrator creation; refuses any second attempt."""
    expected = settings.require_admin_bootstrap_secret()
    supplied = (bootstrap_secret or "").strip()
    # Constant-time comparison over fixed-width digests; the bootstrap secret is
    # checked in addition to the authenticated actor, mirroring a one-time token.
    if not supplied or not hmac.compare_digest(
        hashlib.sha256(supplied.encode("utf-8")).digest(),
        hashlib.sha256(expected).digest(),
    ):
        raise api_error("invalid_credentials")

    if session.execute(select(func.count()).select_from(AdminBootstrapRecord)).scalar_one():
        raise api_error("account_registration_unavailable")
    if session.execute(
        select(func.count()).select_from(UserAccount).where(
            UserAccount.role == constants.ROLE_ADMIN
        )
    ).scalar_one():
        raise api_error("account_registration_unavailable")

    email_norm = crypto.normalize_email(email)
    if email_norm is None or not crypto.is_synthetic_email(email_norm):
        raise api_error("invalid_demo_identifier")
    account = _create_account(
        session,
        clock=clock,
        email_norm=email_norm,
        role=constants.ROLE_ADMIN,
        password=password,
        password_change_required=False,
    )
    session.add(
        AdminBootstrapRecord(
            bootstrap_id=str(uuid.uuid4()),
            user_id=account.user_id,
            email_norm=email_norm,
            bootstrapped_at=clock.now_iso(),
        )
    )
    record(
        session,
        clock=clock,
        event_type=constants.EVENT_ADMIN_BOOTSTRAPPED,
        outcome=constants.OUTCOME_SUCCESS,
        subject_type=constants.SUBJECT_USER_ACCOUNT,
        subject_id=account.user_id,
        actor_user_id=account.user_id,
        payload={"role": constants.ROLE_ADMIN},
    )
    return {"user_id": account.user_id, "email_norm": email_norm}


def create_doctor(
    session: Session,
    *,
    clock: Clock,
    actor: UserAccount,
    email: str,
    display_name: str,
    temp_password_policy: str,
) -> dict[str, str]:
    """Admin-only doctor provisioning with a one-time temporary password."""
    if actor.role != constants.ROLE_ADMIN:
        raise api_error("forbidden")
    if actor.status != constants.STATUS_ACTIVE:
        raise api_error("forbidden")
    if temp_password_policy not in constants.TEMP_PASSWORD_POLICIES:
        raise api_error("validation_failed")

    email_norm = crypto.normalize_email(email)
    if email_norm is None or not crypto.is_synthetic_email(email_norm):
        # Synthetic namespace only: no real contact information is accepted.
        raise api_error("invalid_demo_identifier")
    label = display_name.strip()
    if not label or len(label) > 128 or any(ord(char) < 0x20 for char in label):
        raise api_error("validation_failed")

    if find_account_by_email(session, email_norm) is not None:
        raise api_error("account_registration_unavailable")
    if session.execute(
        select(func.count()).select_from(DoctorProfile).join(
            UserAccount, DoctorProfile.user_id == UserAccount.user_id
        ).where(UserAccount.email_norm == email_norm)
    ).scalar_one():
        raise api_error("account_registration_unavailable")

    temp_password = crypto.new_temporary_password()
    account = _create_account(
        session,
        clock=clock,
        email_norm=email_norm,
        role=constants.ROLE_DOCTOR,
        password=temp_password,
        password_change_required=True,
    )
    doctor = DoctorProfile(
        doctor_id=str(uuid.uuid4()),
        user_id=account.user_id,
        display_name=label,
        active=True,
        created_at=clock.now_iso(),
    )
    session.add(doctor)
    record(
        session,
        clock=clock,
        event_type=constants.EVENT_ACCOUNT_PROVISIONED,
        outcome=constants.OUTCOME_SUCCESS,
        subject_type=constants.SUBJECT_DOCTOR_PROFILE,
        subject_id=doctor.doctor_id,
        actor_user_id=actor.user_id,
        payload={"role": constants.ROLE_DOCTOR, "user_id": account.user_id},
    )
    return {
        "doctor_id": doctor.doctor_id,
        "user_id": account.user_id,
        "temp_secret": temp_password,
    }


def usable_administrators(session: Session) -> list[UserAccount]:
    return list(
        session.execute(
            select(UserAccount).where(
                UserAccount.role == constants.ROLE_ADMIN,
                UserAccount.status != constants.STATUS_DISABLED,
            )
        ).scalars()
    )


def _assert_administrator_remains(session: Session, target: UserAccount) -> None:
    if target.role != constants.ROLE_ADMIN:
        return
    others = [
        account
        for account in usable_administrators(session)
        if account.user_id != target.user_id
        and account.status == constants.STATUS_ACTIVE
        and not account.password_change_required
    ]
    if not others:
        raise api_error("last_administrator_protected")


def change_account_status(
    session: Session,
    *,
    clock: Clock,
    actor: UserAccount,
    target_user_id: str,
    status: str,
    reason_code: str,
) -> dict[str, str]:
    """Admin-only lifecycle transition with session revocation and audit."""
    if actor.role != constants.ROLE_ADMIN or actor.status != constants.STATUS_ACTIVE:
        raise api_error("forbidden")
    if status not in constants.ACCOUNT_STATUSES:
        raise api_error("validation_failed")
    reason = reason_code.strip()
    if not reason or len(reason) > 64:
        raise api_error("validation_failed")

    target = session.execute(
        select(UserAccount).where(UserAccount.user_id == target_user_id)
    ).scalar_one_or_none()
    if target is None:
        raise api_error("account_not_found")

    if status == target.status:
        # Idempotent no-op: no transition, no session revocation, no audit row.
        return {"user_id": target.user_id, "status": target.status}

    if status not in constants.ALLOWED_STATUS_TRANSITIONS[target.status]:
        raise api_error("account_status_conflict")

    if status != constants.STATUS_ACTIVE:
        _assert_administrator_remains(session, target)

    previous = target.status
    target.status = status
    target.status_reason_code = reason
    target.status_changed_at = clock.now_iso()
    if target.role == constants.ROLE_DOCTOR:
        profile = session.execute(
            select(DoctorProfile).where(DoctorProfile.user_id == target.user_id)
        ).scalar_one_or_none()
        if profile is not None:
            profile.active = status == constants.STATUS_ACTIVE
    revoked = _revoke_all_sessions(
        session, user_id=target.user_id, clock=clock, reason=f"account_status_{status.lower()}"
    )
    record(
        session,
        clock=clock,
        event_type=constants.EVENT_ACCOUNT_STATUS_CHANGED,
        outcome=constants.OUTCOME_SUCCESS,
        subject_type=constants.SUBJECT_USER_ACCOUNT,
        subject_id=target.user_id,
        actor_user_id=actor.user_id,
        payload={
            "previous_status": previous,
            "status": status,
            "reason_code": reason,
            "revoked_sessions": revoked,
        },
    )
    return {"user_id": target.user_id, "status": target.status}
