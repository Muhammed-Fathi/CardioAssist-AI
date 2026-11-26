"""Stable identity keys with persisted non-secret key-check metadata (C1.4).

Two independent operator secrets are bound to the database:

* the *identity-match* key produces ``identifier_hmac`` values on visits, on
  invitations and on ``patient_identity`` rows;
* the *subject* key produces the blind, key-version-independent
  ``canonical_subject_id`` and the public ``subject_label``.

Both are verified against ``identity_key_check`` rows before any identity-
related write. The check value is
``HMAC(key, 'identity-key-check/v1' || 0x00 || purpose || 0x00 || key_id)``;
it is a verification value, not secret material, and no raw key is stored.

Consequences enforced here:

* replacing key material while keeping the same key id is detected, because the
  recomputed check no longer matches the stored row;
* a missing check row on an otherwise populated database fails closed;
* a key id that differs from the stored one is a replacement attempt and is
  refused on a populated database (``demo-v2`` is not implemented, P-11);
* every failure is a closed error code, never a partial write.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import constants, crypto
from .errors import api_error
from .models import (
    DurableIdempotency,
    IdentityKeyCheck,
    InvitationAttempt,
    LoginAttempt,
    PatientIdentity,
    PatientInvitation,
    VerifiedVisit,
)
from .settings import Term1Settings
from .timeutil import Clock

_POPULATED_PROBE_TABLES = (
    PatientIdentity,
    VerifiedVisit,
    PatientInvitation,
    InvitationAttempt,
    LoginAttempt,
    DurableIdempotency,
)


@dataclass(frozen=True)
class IdentityBinding:
    """Server-computed identity digests for one normalized fictitious id."""

    identifier_key_id: str
    identifier_hmac: str
    canonical_subject_id: str
    subject_label: str


def compute_binding(settings: Term1Settings, normalized_identifier: str) -> IdentityBinding:
    return IdentityBinding(
        identifier_key_id=settings.identity_key_id,
        identifier_hmac=crypto.identifier_match_hmac(
            settings.identity_match_key, normalized_identifier
        ),
        canonical_subject_id=crypto.canonical_subject_id(
            settings.subject_key, normalized_identifier
        ),
        subject_label=crypto.subject_label(settings.subject_key, normalized_identifier),
    )


def _expected_checks(settings: Term1Settings) -> dict[str, str]:
    return {
        constants.IDENTITY_MATCH_PURPOSE: crypto.key_check_hash(
            settings.identity_match_key,
            constants.IDENTITY_MATCH_PURPOSE,
            settings.identity_key_id,
        ),
        constants.SUBJECT_CANONICAL_PURPOSE: crypto.key_check_hash(
            settings.subject_key, constants.SUBJECT_CANONICAL_PURPOSE, settings.identity_key_id
        ),
        constants.PEPPER_PURPOSE: crypto.key_check_hash(
            settings.pepper, constants.PEPPER_PURPOSE, settings.identity_key_id
        ),
    }


def database_is_populated(session: Session) -> bool:
    for model in _POPULATED_PROBE_TABLES:
        if session.execute(select(func.count()).select_from(model)).scalar_one():
            return True
    return False


def has_identity_activity(session: Session) -> bool:
    for model in _POPULATED_PROBE_TABLES:
        if session.execute(select(func.count()).select_from(model)).scalar_one():
            return True
    return False


def stored_checks(session: Session) -> dict[str, list[IdentityKeyCheck]]:
    rows = session.execute(select(IdentityKeyCheck)).scalars().all()
    grouped: dict[str, list[IdentityKeyCheck]] = {}
    for row in rows:
        grouped.setdefault(row.purpose, []).append(row)
    return grouped


def verify_or_activate(
    session: Session,
    *,
    settings: Term1Settings,
    clock: Clock,
    write: bool,
) -> None:
    """Verify key material; on an empty database optionally record the checks.

    ``write=False`` is the read-only startup path: it verifies and refuses, but
    never inserts. ``write=True`` activates the check rows the first time a
    database is used, before the first identity-related write.
    """
    expected = _expected_checks(settings)
    grouped = stored_checks(session)
    activity = has_identity_activity(session)
    now = clock.now_iso()

    for purpose, expected_hash in expected.items():
        rows = grouped.get(purpose, [])
        if not rows:
            if activity or grouped:
                # Existing activity or partial binding metadata must not be silently repaired: fail closed
                # rather than silently re-binding possibly different material.
                raise api_error("identity_key_material_mismatch")
            if not write:
                raise api_error("identity_key_material_mismatch")
            session.add(
                IdentityKeyCheck(
                    check_id=str(uuid.uuid4()),
                    purpose=purpose,
                    key_id=settings.identity_key_id,
                    key_check_hash=expected_hash,
                    alg=constants.IDENTITY_KEY_ALG,
                    created_at=now,
                    activated_at=now,
                    retired_at=None,
                )
            )
            continue

        active = [row for row in rows if row.retired_at is None]
        # Exactly one active key-check row per purpose: zero means unbound,
        # more than one means the binding is ambiguous. Both fail closed.
        if len(active) != 1:
            raise api_error("identity_key_material_mismatch")
        row = active[0]
        if row.key_id != settings.identity_key_id:
            # Configured key id is not the active key id for this purpose.
            if activity:
                raise api_error("identity_key_replacement_unsupported")
            raise api_error("identity_key_material_mismatch")
        if not crypto.constant_time_equals(row.key_check_hash, expected_hash):
            # Same key id, changed material: replacement under an unchanged id
            # is detected and refused.
            raise api_error("identity_key_material_mismatch")



def verify_startup(session: Session, *, settings: Term1Settings) -> None:
    """Read-only startup verification (never activates or repairs)."""
    grouped = stored_checks(session)
    activity = has_identity_activity(session)
    if not grouped:
        # No check rows bound yet: only safe when there is no identity activity.
        # A populated database whose key material was never bound fails closed.
        if activity:
            raise api_error("identity_key_material_mismatch")
        return
    expected = _expected_checks(settings)
    for purpose, expected_hash in expected.items():
        rows = [row for row in grouped.get(purpose, []) if row.retired_at is None]
        if len(rows) != 1:
            raise api_error("identity_key_material_mismatch")
        row = rows[0]
        if row.key_id != settings.identity_key_id:
            raise api_error("identity_key_replacement_unsupported")
        if not crypto.constant_time_equals(row.key_check_hash, expected_hash):
            raise api_error("identity_key_material_mismatch")
