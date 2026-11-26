"""Durable, actor/operation/target-bound replay protection (C1.8).

The replay identity is the complete tuple

    (replay_scope, key_hash, actor_binding, operation, target_ref)

and lookup is *only* by that tuple. There is deliberately no query by
``key_hash`` alone, so a key presented by another actor is simply absent from
that actor's scope: no existence oracle and no cross-actor conflict.

Stored values are keyed digests and redacted response bodies:

* ``request_fingerprint`` — HMAC over the canonical secret-free request fields;
* ``secret_fingerprints_json`` — per-field HMACs for password/access-code style
  inputs (used only to detect a *changed* secret on replay);
* ``response_public_json`` — the redacted public result, never a one-time
  secret. ``secret_disclosed`` records that the original response carried one,
  so a replay returns ``409 secret_not_redisclosable``.

Ordering is frozen: identity lookup -> fingerprint comparison -> redacted replay
or secret error -> only then semantic validation and effect. A replay therefore
never re-opens a consumed invitation and never creates a second account,
assignment, consent or session.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any, Mapping

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from . import constants, crypto
from .errors import api_error
from .models import DurableIdempotency
from .timeutil import Clock, from_iso


@dataclass(frozen=True)
class ReplayKey:
    replay_scope: str
    key_hash: str
    actor_binding: str
    operation: str
    target_ref: str


@dataclass(frozen=True)
class RequestIdentity:
    """Fingerprints for one request under one Idempotency-Key."""

    replay_key: ReplayKey
    request_fingerprint: str
    secret_fingerprints: dict[str, str]
    secret_disclosed: bool
    public_body: dict[str, Any]


class ReplayDecision:
    """Outcome of a replay pre-check (``replay`` is set when already executed)."""

    def __init__(self, identity: RequestIdentity, replay: Mapping[str, Any] | None = None) -> None:
        self.identity = identity
        self.replay = replay

    @property
    def is_replay(self) -> bool:
        return self.replay is not None

    def body(self) -> dict[str, Any]:
        assert self.replay is not None
        document = {"idempotent_replay": True}
        document.update(self.replay)
        return document


def canonical_public(value: Mapping[str, Any]) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def user_scope(user_id: str) -> tuple[str, str]:
    return constants.REPLAY_SCOPE_USER, f"user:{user_id}"


def anonymous_scope(invitation_verifier_sha256: str) -> tuple[str, str]:
    return constants.REPLAY_SCOPE_ANONYMOUS, f"anon:{invitation_verifier_sha256[:32]}"


def build_identity(
    *,
    pepper: bytes,
    scope: tuple[str, str],
    operation: str,
    target_ref: str,
    raw_key: str,
    public_fields: Mapping[str, Any],
    secret_fields: Mapping[str, str] | None = None,
    secret_disclosed: bool = False,
    public_response: Mapping[str, Any] | None = None,
) -> RequestIdentity:
    """Derive the complete replay identity and keyed fingerprints."""
    secret_fields = secret_fields or {}
    request_fingerprint = crypto.hmac_hex(
        pepper,
        constants.DOMAIN_REQUEST_FINGERPRINT,
        canonical_public(dict(public_fields)).encode("utf-8"),
    )
    fingerprints = {
        field: crypto.secret_fingerprint(pepper, field, value)
        for field, value in sorted(secret_fields.items())
    }
    return RequestIdentity(
        replay_key=ReplayKey(
            replay_scope=scope[0],
            key_hash=crypto.idempotency_key_hash(pepper, raw_key),
            actor_binding=scope[1],
            operation=operation,
            target_ref=target_ref or "none",
        ),
        request_fingerprint=request_fingerprint,
        secret_fingerprints=fingerprints,
        secret_disclosed=secret_disclosed,
        public_body=dict(public_response or {}),
    )


def _row_for(session: Session, key: ReplayKey) -> DurableIdempotency | None:
    return session.execute(
        select(DurableIdempotency).where(
            DurableIdempotency.replay_scope == key.replay_scope,
            DurableIdempotency.key_hash == key.key_hash,
            DurableIdempotency.actor_binding == key.actor_binding,
            DurableIdempotency.operation == key.operation,
            DurableIdempotency.target_ref == key.target_ref,
        )
    ).scalar_one_or_none()


def _same_actor_key_elsewhere(session: Session, key: ReplayKey) -> bool:
    """True when this actor already used the key for another operation/target."""
    return (
        session.execute(
            select(DurableIdempotency.replay_id).where(
                DurableIdempotency.replay_scope == key.replay_scope,
                DurableIdempotency.key_hash == key.key_hash,
                DurableIdempotency.actor_binding == key.actor_binding,
                or_(
                    DurableIdempotency.operation != key.operation,
                    DurableIdempotency.target_ref != key.target_ref,
                ),
            ).limit(1)
        ).first()
        is not None
    )


def precheck(session: Session, *, clock: Clock, identity: RequestIdentity) -> ReplayDecision:
    """Actor-scoped replay resolution; raises on conflicts."""
    key = identity.replay_key
    row = _row_for(session, key)
    if row is None:
        if _same_actor_key_elsewhere(session, key):
            raise api_error("idempotency_scope_conflict")
        return ReplayDecision(identity)

    if from_iso(row.expires_at) <= clock.now():
        # An expired record is absent for replay purposes. A later execution
        # still has to satisfy invitation/consent/uniqueness validation.
        return ReplayDecision(identity)

    stored_secrets = row.secret_fingerprints_json or {}
    if (
        not crypto.constant_time_equals(row.request_fingerprint, identity.request_fingerprint)
        or stored_secrets != identity.secret_fingerprints
    ):
        raise api_error("idempotency_key_conflict")

    if row.secret_disclosed:
        # One-time secrets (temporary passwords, access codes, session tokens)
        # are never re-disclosed; only non-secret identifiers are returned.
        raise api_error(
            "secret_not_redisclosable",
            extra=dict(row.response_public_json or {}),
        )
    return ReplayDecision(identity, dict(row.response_public_json or {}))


def remember(
    session: Session,
    *,
    clock: Clock,
    identity: RequestIdentity,
    status_code: int,
    public_response: Mapping[str, Any],
    secret_disclosed: bool,
) -> str:
    """Persist the replay record inside the business transaction."""
    key = identity.replay_key
    replay_id = str(uuid.uuid4())
    session.add(
        DurableIdempotency(
            replay_id=replay_id,
            replay_scope=key.replay_scope,
            key_hash=key.key_hash,
            actor_binding=key.actor_binding,
            operation=key.operation,
            target_ref=key.target_ref,
            request_fingerprint=identity.request_fingerprint,
            secret_fingerprints_json=dict(identity.secret_fingerprints),
            response_public_json=dict(public_response),
            status_code=status_code,
            created_at=clock.now_iso(),
            expires_at=clock.plus(constants.IDEMPOTENCY_TTL_SECONDS),
            secret_disclosed=secret_disclosed,
        )
    )
    return replay_id
