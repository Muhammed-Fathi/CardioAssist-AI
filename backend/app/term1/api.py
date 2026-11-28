"""HTTP surface for the twenty C1 operations, composed onto the legacy app.

Every route is additive: the two legacy operations keep their own handlers,
contracts, fixtures and OpenAPI source.

Request handling per operation:

1. structural validation (strict UTF-8 JSON, duplicate members, non-finite
   numbers, exact ``application/json`` media type, required headers);
2. authentication (bearer token) *inside* the business transaction, so a
   concurrently revoked session or suspended account cannot authorise a write;
3. where the operation is idempotent, actor/operation/target replay resolution;
4. the business transaction;
5. the response, with ``Cache-Control: no-store`` and no credential echoing.

Status semantics are the frozen catalogue: ``400`` malformed, ``401`` generic
authentication/invitation failure, ``403`` wrong role or temporary-password
restriction, ``404`` wrong owner, ``409`` conflict, ``422`` value failure,
``429`` rate limit.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Mapping

import jsonschema
from sqlalchemy.orm import Session

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from ..main_helpers import finite_float, reject_constant, unique_object
from . import constants, crypto, enrollment, openapi, sessions, visits
from .identity import database_is_populated, verify_or_activate
from .accounts import bootstrap_administrator, change_account_status, create_doctor
from .audit import record, record_isolated
from .errors import ApiError, api_error, error_response
from .idempotency import build_identity, precheck, remember
from .settings import SettingsError, Term1Settings, load_settings
from .timeutil import Clock
from .tx import read_transaction, write_transaction

logger = logging.getLogger("cardioassist.term1.api")

CONTRACT_VERSION = "v1"
NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}
IDEMPOTENCY_HEADER = "Idempotency-Key"

BODY_REQUIRED = frozenset(
    {
        constants.OP_LOGIN,
        constants.OP_PASSWORD,
        constants.OP_ADMIN_DOCTORS,
        constants.OP_ADMIN_STATUS,
        constants.OP_VISIT_CREATE,
        constants.OP_INVITATION_CREATE,
        constants.OP_INVITATION_REVOKE,
        constants.OP_REGISTER,
        constants.OP_LINK,
        constants.OP_ASSIGNMENT_DOCTOR_REVOKE,
        constants.OP_ASSIGNMENT_PATIENT_REVOKE,
        constants.OP_CONSENT_REVOKE,
        constants.OP_HEALTH_PROFILE_PATCH,
        constants.OP_ASSESSMENT_CREATE,
    }
)
BODY_OPTIONAL = frozenset({constants.OP_LOGOUT, constants.OP_REFRESH})

TEMP_PASSWORD_ALLOWED = frozenset(
    {constants.OP_LOGOUT, constants.OP_ME, constants.OP_PASSWORD}
)

# Idempotency and replay conflicts are rejected before any enrollment effect.
# They must not be counted as credential-guessing attempts or corrupt the
# invitation lifecycle.
ENROLLMENT_GUESSING_CODES_EXCLUDED = frozenset(
    {
        # Idempotency/replay outcomes are not credential guesses.
        # C1-R04 registration: idempotency_key_conflict was being counted
        # toward the guessing rate limit; it must be excluded.
        "idempotency_key_required",
        "idempotency_key_conflict",
        "idempotency_scope_conflict",
        "secret_not_redisclosable",
        # Authentication, authorization and infrastructure failures are not
        # invitation-credential guesses.
        "authentication_required",
        "invalid_session",
        "forbidden",
        "password_change_required",
        "identity_key_configuration_error",
        "identity_key_material_mismatch",
        "identity_key_change_unsupported",
        "identity_key_replacement_unsupported",
        "internal_error",
        "concurrency_conflict",
    }
)


class Actor:
    """An authenticated account bound to the session that authorised it."""

    __slots__ = ("account", "session_id", "token")

    def __init__(self, account, session_id: str, token: str) -> None:
        self.account = account
        self.session_id = session_id
        self.token = token


def envelope(**fields: Any) -> dict[str, Any]:
    document = {"contract_version": CONTRACT_VERSION}
    document.update(fields)
    return document


def _response(
    status: int,
    body: Mapping[str, Any],
    *,
    extra_headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    headers = dict(NO_STORE)
    if extra_headers:
        headers.update(extra_headers)
    return JSONResponse(dict(body), status_code=status, headers=headers)


def error_response_json(error: ApiError) -> JSONResponse:
    headers = dict(NO_STORE)
    if error.retry_after is not None:
        headers["Retry-After"] = str(error.retry_after)
    return JSONResponse(
        envelope(error=error_response(error)), status_code=error.status, headers=headers
    )


_INTERNAL_ERROR = api_error("internal_error")


def unexpected_failure_json(error: BaseException) -> JSONResponse:
    """Map an unexpected exception to the declared, redacted ``500`` envelope.

    Every C1 operation declares ``500 internal_error`` with a frozen JSON body.
    Without this boundary an unhandled exception escapes to the ASGI server and
    the client receives Starlette's bare ``text/plain`` "Internal Server Error"
    with no ``Cache-Control: no-store``: an undeclared media type, an undeclared
    body shape, and a caching-rule violation on the one status that most needs
    the rule.

    The body is *static*. The message comes from the frozen catalogue and never
    embeds the exception type, its text, a traceback, a submitted value or a
    resource identifier, so an internal fault cannot become a disclosure
    channel. Only a fixed metadata-only event is logged server-side; no
    exception text, traceback, SQL statement or parameter is logged.

    Response boundary only: it performs no database work and opens no
    transaction. An unexpected fault has already left the operation's own
    ``write_transaction`` block, so that block has rolled back exactly as it did
    before this boundary existed - rollback and audit atomicity are unchanged.
    Returning success is impossible here; the status is fixed at 500.
    """
    # Exception messages/tracebacks can contain SQL parameters, submitted
    # identifiers, credentials or key material. Never attach the exception
    # object (including exc_info) to the operational log.
    logger.error("term1 operation failed unexpectedly: internal_error")
    return error_response_json(_INTERNAL_ERROR)


class Term1Handler:
    """Shared plumbing: parsing, authentication, idempotency, error mapping."""

    def __init__(
        self,
        *,
        database,
        clock: Clock,
        settings: Term1Settings | None,
        source_key_for: Callable[[Request], str],
    ) -> None:
        self.database = database
        self.clock = clock
        self._settings = settings
        self._source_key_for = source_key_for

    # --- configuration ----------------------------------------------------
    def settings(self) -> Term1Settings:
        if self._settings is not None:
            return self._settings
        try:
            self._settings = load_settings()
        except SettingsError as error:
            raise api_error("identity_key_configuration_error") from error
        return self._settings

    def verify_identity_keys(self) -> None:
        """Read-only startup verification of persisted identity-key checks.

        Never activates, repairs or writes: a populated database whose key
        material no longer matches is refused instead of silently re-bound.
        """
        from .identity import database_is_populated, stored_checks, verify_startup

        if self._settings is None and not _environment_configured():
            # No operator material configured: only an empty, unused C1 database
            # may skip verification. A populated database without configured
            # material fails closed (C1-R06).
            with read_transaction(self.database) as session:
                if database_is_populated(session) or stored_checks(session):
                    raise api_error("identity_key_configuration_error")
            return
        settings = self.settings()
        with read_transaction(self.database) as session:
            verify_startup(session, settings=settings)

    # --- request parsing --------------------------------------------------
    async def body(self, request: Request, operation: str) -> dict[str, Any]:
        raw = await request.body()
        if not raw.strip():
            if operation in BODY_REQUIRED:
                raise api_error("malformed_request")
            return {}
        media_type = request.headers.get("content-type", "").partition(";")[0].strip().lower()
        if media_type != "application/json":
            raise api_error("malformed_request")
        try:
            parsed = json.loads(
                raw.decode("utf-8"),
                object_pairs_hook=unique_object,
                parse_float=finite_float,
                parse_constant=reject_constant,
            )
        except (ValueError, UnicodeError, RecursionError) as error:
            raise api_error("malformed_request") from error
        if not isinstance(parsed, dict):
            raise api_error("malformed_request")
        if parsed.get("contract_version", CONTRACT_VERSION) != CONTRACT_VERSION:
            raise api_error("malformed_request")
        # The handler defaults a missing contract_version to "v1"; normalise the
        # parsed body so the operation-specific schema (which lists
        # contract_version as required) validates against the value the service
        # actually serves (C1-R01 runtime enforcement).
        parsed["contract_version"] = CONTRACT_VERSION
        # Runtime enforcement of the operation-specific request schema (C1-R01):
        # every C1 request body must validate against its own schema from
        # shared/contracts/term1/schemas/. Anonymous and authenticated
        # operations alike; an empty body (operations that allow one) is not
        # validated here.
        schema_name = openapi.OP_REQUEST_SCHEMA.get(self._operation_key(operation))
        if schema_name is not None:
            validator = openapi.c1_request_validator(schema_name)
            schema_error = next(validator.iter_errors(parsed), None)
            if schema_error is not None:
                raise api_error("validation_failed")
        return parsed

    @staticmethod
    def _operation_key(operation: str) -> tuple[str, str]:
        method, _, path = operation.partition(" ")
        return (method.lower().strip(), path.strip())

    @staticmethod
    def idempotency_key(request: Request) -> str:
        keys = [value for value in request.headers.getlist("idempotency-key") if value.strip()]
        if not keys:
            raise api_error("idempotency_key_required")
        if len(set(keys)) != 1:
            # Two *different* keys on one request are ambiguous and rejected.
            raise api_error("idempotency_key_required")
        key = keys[0].strip()
        if len(key) > 255:
            raise api_error("malformed_request")
        return key

    @staticmethod
    def bearer(request: Request) -> str:
        # Reject duplicate Authorization headers: header smuggling via repeated
        # Authorization headers must never be silently resolved to one value
        # (C1-R02).
        auth_headers = request.headers.getlist("authorization")
        if len(auth_headers) != 1:
            raise api_error("authentication_required")
        header = auth_headers[0]
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise api_error("authentication_required")
        token = token.strip()
        # Session tokens are ASCII. A malformed or non-ASCII bearer value must
        # fail with a controlled, non-enumerating error instead of raising a
        # Unicode error that becomes an HTTP 500 (C1-R02).
        try:
            token.encode("ascii")
        except UnicodeEncodeError:
            raise api_error("authentication_required")
        return token

    def authenticate(self, session, request: Request, *, operation: str) -> Actor:
        token = self.bearer(request)
        row, account = sessions.authenticate(session, clock=self.clock, token=token)
        if account.password_change_required and operation not in TEMP_PASSWORD_ALLOWED:
            raise api_error("password_change_required")
        return Actor(account=account, session_id=row.session_id, token=token)

    # --- typed field helpers ---------------------------------------------
    @staticmethod
    def str_field(
        body: Mapping[str, Any],
        name: str,
        *,
        minimum: int = 1,
        maximum: int = 512,
        bytes_bounded: bool = True,
    ) -> str:
        value = body.get(name)
        if not isinstance(value, str):
            raise api_error("validation_failed")
        size = len(value.encode("utf-8")) if bytes_bounded else len(value)
        if size < minimum or size > maximum:
            raise api_error("validation_failed")
        return value

    @staticmethod
    def bool_field(body: Mapping[str, Any], name: str) -> bool:
        value = body.get(name)
        if not isinstance(value, bool):
            raise api_error("validation_failed")
        return value

    @staticmethod
    def int_field(
        body: Mapping[str, Any], name: str, *, minimum: int, maximum: int
    ) -> int:
        value = body.get(name)
        if isinstance(value, bool) or not isinstance(value, int):
            raise api_error("validation_failed")
        if value < minimum or value > maximum:
            raise api_error("validation_failed")
        return value

    @staticmethod
    def require_role(actor: Actor, *roles: str) -> None:
        if actor.account.role not in roles:
            raise api_error("forbidden")


# --- idempotent operation runner ----------------------------------------------
def run_idempotent(
    handler: Term1Handler,
    request: Request,
    *,
    operation: str,
    target_ref: str,
    public_fields: Mapping[str, Any],
    secret_fields: Mapping[str, str],
    run: Callable[[Any, Actor], tuple[dict[str, Any], dict[str, Any], bool]],
    anonymous_actor: str | None = None,
    failure_hook: Callable[[ApiError | None, Session | None], None] | None = None,
    status: int = 200,
    scope_kind: str = "user",
    on_replay: Callable[[Session, Actor], None] | None = None,
) -> JSONResponse:
    """One Idempotency-Key protected operation inside one write transaction.

    ``run(session, actor)`` returns ``(full_response, redacted_response,
    secret_disclosed)``. Authentication happens first inside the transaction so
    that the replay actor binding is the authenticated user, and so that a
    concurrently revoked session cannot authorize a disclosed replay.

    ``on_replay(session, actor)`` (C2, checkpoint §7) runs when a cached 2xx
    match is about to be returned, inside the same transaction, so a replay of
    H1b/S1 re-verifies live consent/assignment state first; it raises the
    same ``ApiError`` the first execution would. C1 operations pass ``None``.

    Failure hooks are invoked INSIDE the transaction (before rollback) so that
    durable attempt evidence is written under the same ``BEGIN IMMEDIATE``
    lock as the business logic. A savepoint isolates business data from failure
    evidence: on failure, business writes are rolled back to the savepoint,
    failure evidence is added, and the outer transaction commits only the
    evidence. This closes the gap where a concurrent request could slip
    between business rollback and failure recording (F2: race-safe attempt
    accounting) while ensuring failed enrollment leaves no partial account,
    assignment, consent or redemption effects.

    Operator key material is resolved inside the guarded block so that a missing
    or unusable configuration is reported as the catalogue's ``503
    identity_key_configuration_error`` envelope instead of escaping as an
    unhandled exception (HTTP 500 with a non-JSON body).
    """
    try:
        settings = handler.settings()
        raw_key = handler.idempotency_key(request)
        with write_transaction(handler.database) as session:
            nested = session.begin_nested()
            try:
                actor = handler.authenticate(session, request, operation=operation)
                # Bind before any pepper-dependent replay record can be created,
                # including doctor provisioning before the first verified visit.
                verify_or_activate(session, settings=settings, clock=handler.clock, write=True)
                session.flush()
                if anonymous_actor is not None:
                    scope = (constants.REPLAY_SCOPE_ANONYMOUS, anonymous_actor)
                else:
                    scope = (constants.REPLAY_SCOPE_USER, f"user:{actor.account.user_id}")
                identity = build_identity(
                    pepper=settings.pepper,
                    scope=scope,
                    operation=operation,
                    target_ref=target_ref,
                    raw_key=raw_key,
                    public_fields=public_fields,
                    secret_fields=secret_fields,
                )
                decision = precheck(session, clock=handler.clock, identity=identity)
                if decision.is_replay:
                    if on_replay is not None:
                        on_replay(session, actor)
                    return _response(status, envelope(**decision.body()))
                result, redacted, disclosed = run(session, actor)
                remember(
                    session,
                    clock=handler.clock,
                    identity=identity,
                    status_code=status,
                    public_response=redacted,
                    secret_disclosed=disclosed,
                )
                return _response(status, envelope(**result))
            except ApiError as error:
                # Roll back business writes to the savepoint: no partial
                # account, assignment, consent or redemption effects survive.
                nested.rollback()
                # Reset the session so objects added after the savepoint
                # rollback are tracked by the outer transaction.
                session.expire_all()
                # Record durable failure evidence inside the same transaction
                # before the lock is released.
                if failure_hook is not None:
                    failure_hook(error, session=session)
                # Return the error response directly: the outer
                # write_transaction will commit the failure evidence when it
                # exits normally (no exception propagates).
                return error_response_json(error)
    except ApiError as error:
        return error_response_json(error)


# --- route registration --------------------------------------------------------
def register_term1_routes(app: FastAPI, *, handler: Term1Handler) -> None:
    """Attach exactly the twenty C1 operations to ``app``."""

    # ============================================================== A1 login
    async def _impl_login(request: Request) -> JSONResponse:
        settings = None
        buckets = {}
        try:
            body = await handler.body(request, constants.OP_LOGIN)
            email = handler.str_field(body, "email", maximum=254)
            password = handler.str_field(body, "password", minimum=1, maximum=1024)
            settings = handler.settings()
            email_norm = crypto.normalize_email(email)
            buckets = sessions.login_buckets(
                settings.pepper,
                email_norm=email_norm,
                source_key=handler._source_key_for(request),
            )

            def run():
                # One authoritative transaction: lockout check, bounded
                # password-verification work and session issuance commit
                # together under BEGIN IMMEDIATE (tx.write_transaction).
                with write_transaction(handler.database) as session:
                    if sessions.is_locked(session, buckets, clock=handler.clock):
                        # Already locked: do not record another failure. The
                        # existing failure evidence is already durable and
                        # recording more attempts would indefinitely extend
                        # the lockout window by refreshing failure timestamps.
                        raise sessions.rate_limited_error()
                    return sessions.login(
                        session,
                        clock=handler.clock,
                        pepper=settings.pepper,
                        email=email,
                        password=password,
                        buckets=buckets,
                        settings=settings,
                    )

            # Expensive synchronous password hashing and database work run off
            # the async event loop, in a bounded threadpool, while the write
            # transaction preserves transaction integrity (C1-R05).
            result = await run_in_threadpool(run)
            return _response(200, envelope(**result))
        except ApiError as error:
            # Audit evidence for the failed attempt (survives rollback via its
            # own transaction); the attempt counter is committed inside
            # sessions.login / the lockout branch above. Never masks the
            # original error.
            record_isolated(
                handler.database,
                clock=handler.clock,
                event_type=constants.EVENT_LOGIN_FAILED,
                outcome=constants.OUTCOME_RATE_LIMITED
                if error.code == "rate_limited"
                else constants.OUTCOME_FAILED,
                subject_type=constants.SUBJECT_SESSION,
                code=error.code,
            )
            return error_response_json(error)

    # Decorator sits on the boundary wrapper, not on the implementation,
    # so no path can bypass the unexpected-failure mapping.
    @app.post("/v1/auth/login")
    async def login(request: Request) -> JSONResponse:
        try:
            return await _impl_login(request)
        except ApiError as error:
            return error_response_json(error)
        except Exception as error:  # noqa: BLE001 - mapped to declared 500
            return unexpected_failure_json(error)

    # ============================================================= A2 logout
    async def _impl_logout(request: Request) -> JSONResponse:
        try:
            await handler.body(request, constants.OP_LOGOUT)
            handler.settings()  # fail closed when operator material is unusable
            with write_transaction(handler.database) as session:
                token = handler.bearer(request)
                result = sessions.logout(session, clock=handler.clock, token=token)
            return _response(200, envelope(**result))
        except ApiError as error:
            return error_response_json(error)

    # Decorator sits on the boundary wrapper, not on the implementation,
    # so no path can bypass the unexpected-failure mapping.
    @app.post("/v1/auth/logout")
    async def logout(request: Request) -> JSONResponse:
        try:
            return await _impl_logout(request)
        except ApiError as error:
            return error_response_json(error)
        except Exception as error:  # noqa: BLE001 - mapped to declared 500
            return unexpected_failure_json(error)

    # ================================================================= A3 me
    async def _impl_me(request: Request) -> JSONResponse:
        try:
            handler.settings()  # fail closed when operator material is unusable
            with write_transaction(handler.database) as session:
                token = handler.bearer(request)
                result = sessions.current_account(session, clock=handler.clock, token=token)
            return _response(200, envelope(**result))
        except ApiError as error:
            return error_response_json(error)

    # Decorator sits on the boundary wrapper, not on the implementation,
    # so no path can bypass the unexpected-failure mapping.
    @app.get("/v1/auth/me")
    async def me(request: Request) -> JSONResponse:
        try:
            return await _impl_me(request)
        except ApiError as error:
            return error_response_json(error)
        except Exception as error:  # noqa: BLE001 - mapped to declared 500
            return unexpected_failure_json(error)

    # ============================================================ A4 refresh
    async def _impl_refresh(request: Request) -> JSONResponse:
        try:
            await handler.body(request, constants.OP_REFRESH)
            handler.settings()  # fail closed when operator material is unusable
            with write_transaction(handler.database) as session:
                token = handler.bearer(request)
                _row, account = sessions.authenticate(
                    session, clock=handler.clock, token=token, touch=False
                )
                if account.password_change_required:
                    raise api_error("password_change_required")
                result = sessions.refresh(session, clock=handler.clock, token=token)
            return _response(200, envelope(**result))
        except ApiError as error:
            return error_response_json(error)

    # Decorator sits on the boundary wrapper, not on the implementation,
    # so no path can bypass the unexpected-failure mapping.
    @app.post("/v1/auth/refresh")
    async def refresh(request: Request) -> JSONResponse:
        try:
            return await _impl_refresh(request)
        except ApiError as error:
            return error_response_json(error)
        except Exception as error:  # noqa: BLE001 - mapped to declared 500
            return unexpected_failure_json(error)

    # =========================================================== A5 password
    async def _impl_change_password(request: Request) -> JSONResponse:
        settings = None
        buckets = {}
        account = None
        try:
            body = await handler.body(request, constants.OP_PASSWORD)
            current = handler.str_field(body, "current_password", minimum=1, maximum=1024)
            new = handler.str_field(body, "new_password", minimum=1, maximum=1024)
            settings = handler.settings()
            with write_transaction(handler.database) as session:
                token = handler.bearer(request)
                _row, account = sessions.authenticate(
                    session, clock=handler.clock, token=token, touch=False
                )
                email_norm = account.email_norm
                buckets = sessions.login_buckets(
                    settings.pepper,
                    email_norm=email_norm,
                    source_key=handler._source_key_for(request),
                )
                # Consult the lockout before allowing a password-change guess:
                # repeated wrong current_password attempts must be throttled
                # like login (C1-R02).
                if sessions.is_locked(session, buckets, clock=handler.clock):
                    raise sessions.rate_limited_error()
                result = sessions.change_password(
                    session,
                    clock=handler.clock,
                    token=token,
                    current_password=current,
                    new_password=new,
                )
            return _response(200, envelope(**result))
        except ApiError as error:
            # A wrong current password is a credential attempt against the
            # authenticated account: record durable failure evidence so repeated
            # password-change guessing is throttled like login.
            if settings is not None and account is not None and error.code == "invalid_credentials":
                _record_login_failure(handler, settings, buckets, error)
            return error_response_json(error)

    # Decorator sits on the boundary wrapper, not on the implementation,
    # so no path can bypass the unexpected-failure mapping.
    @app.post("/v1/me/password")
    async def change_password(request: Request) -> JSONResponse:
        try:
            return await _impl_change_password(request)
        except ApiError as error:
            return error_response_json(error)
        except Exception as error:  # noqa: BLE001 - mapped to declared 500
            return unexpected_failure_json(error)

    # =========================================================== A6 sessions
    async def _impl_list_sessions(request: Request) -> JSONResponse:
        try:
            handler.settings()  # fail closed when operator material is unusable
            with write_transaction(handler.database) as session:
                handler.authenticate(session, request, operation=constants.OP_SESSIONS)
                result = sessions.list_sessions(session, clock=handler.clock, token=handler.bearer(request))
            return _response(200, envelope(**result))
        except ApiError as error:
            return error_response_json(error)

    # Decorator sits on the boundary wrapper, not on the implementation,
    # so no path can bypass the unexpected-failure mapping.
    @app.get("/v1/me/sessions")
    async def list_sessions(request: Request) -> JSONResponse:
        try:
            return await _impl_list_sessions(request)
        except ApiError as error:
            return error_response_json(error)
        except Exception as error:  # noqa: BLE001 - mapped to declared 500
            return unexpected_failure_json(error)

    # ============================================================= A7 revoke
    async def _impl_revoke_session(session_id: str, request: Request) -> JSONResponse:
        try:
            handler.settings()  # fail closed when operator material is unusable
            with write_transaction(handler.database) as session:
                handler.authenticate(session, request, operation=constants.OP_SESSION_REVOKE)
                result = sessions.revoke_session(
                    session, clock=handler.clock, token=handler.bearer(request), target_session_id=session_id
                )
            return _response(200, envelope(**result))
        except ApiError as error:
            return error_response_json(error)

    # Decorator sits on the boundary wrapper, not on the implementation,
    # so no path can bypass the unexpected-failure mapping.
    @app.delete("/v1/me/sessions/{session_id}")
    async def revoke_session(session_id: str, request: Request) -> JSONResponse:
        try:
            return await _impl_revoke_session(session_id, request)
        except ApiError as error:
            return error_response_json(error)
        except Exception as error:  # noqa: BLE001 - mapped to declared 500
            return unexpected_failure_json(error)

    # ========================================================== AD1 doctors
    async def _impl_admin_create_doctor(request: Request) -> JSONResponse:
        try:
            body = await handler.body(request, constants.OP_ADMIN_DOCTORS)
            email = handler.str_field(body, "email", maximum=254)
            display_name = handler.str_field(body, "display_name", minimum=1, maximum=128)
            policy = handler.str_field(body, "temp_password_policy", maximum=32)
        except ApiError as error:
            return error_response_json(error)

        def run(session, actor):
            handler.require_role(actor, constants.ROLE_ADMIN)
            result = create_doctor(
                session,
                clock=handler.clock,
                actor=actor.account,
                email=email,
                display_name=display_name,
                temp_password_policy=policy,
            )
            redacted = {"doctor_id": result["doctor_id"], "user_id": result["user_id"]}
            return result, redacted, True

        return run_idempotent(
            handler,
            request,
            operation=constants.OP_ADMIN_DOCTORS,
            target_ref="none",
            public_fields={
                "email": email,
                "display_name": display_name,
                "temp_password_policy": policy,
            },
            secret_fields={},
            run=run,
            status=201,
        )

    # Decorator sits on the boundary wrapper, not on the implementation,
    # so no path can bypass the unexpected-failure mapping.
    @app.post("/v1/admin/doctors")
    async def admin_create_doctor(request: Request) -> JSONResponse:
        try:
            return await _impl_admin_create_doctor(request)
        except ApiError as error:
            return error_response_json(error)
        except Exception as error:  # noqa: BLE001 - mapped to declared 500
            return unexpected_failure_json(error)

    # =========================================================== AD2 status
    async def _impl_admin_status(user_id: str, request: Request) -> JSONResponse:
        try:
            body = await handler.body(request, constants.OP_ADMIN_STATUS)
            status = handler.str_field(body, "status", maximum=16)
            reason = handler.str_field(body, "reason_code", maximum=64)
        except ApiError as error:
            return error_response_json(error)

        def run(session, actor):
            handler.require_role(actor, constants.ROLE_ADMIN)
            result = change_account_status(
                session,
                clock=handler.clock,
                actor=actor.account,
                target_user_id=user_id,
                status=status,
                reason_code=reason,
            )
            return result, result, False

        return run_idempotent(
            handler,
            request,
            operation=constants.OP_ADMIN_STATUS,
            target_ref=user_id,
            public_fields={"status": status, "reason_code": reason},
            secret_fields={},
            run=run,
        )

    # Decorator sits on the boundary wrapper, not on the implementation,
    # so no path can bypass the unexpected-failure mapping.
    @app.patch("/v1/admin/accounts/{user_id}/status")
    async def admin_status(user_id: str, request: Request) -> JSONResponse:
        try:
            return await _impl_admin_status(user_id, request)
        except ApiError as error:
            return error_response_json(error)
        except Exception as error:  # noqa: BLE001 - mapped to declared 500
            return unexpected_failure_json(error)

    # ============================================================= V1 visit
    async def _impl_create_visit(request: Request) -> JSONResponse:
        try:
            body = await handler.body(request, constants.OP_VISIT_CREATE)
            visit_ref = handler.str_field(body, "visit_ref", minimum=1, maximum=128)
            identifier = handler.str_field(body, "subject_identifier", maximum=64)
            asserted = handler.str_field(body, "asserted_visit_at", maximum=64)
            attestation = handler.str_field(body, "attestation_code", maximum=64)
        except ApiError as error:
            return error_response_json(error)

        def run(session, actor):
            handler.require_role(actor, constants.ROLE_DOCTOR)
            result = visits.attest_visit(
                session,
                clock=handler.clock,
                settings=handler.settings(),
                account=actor.account,
                visit_ref=visit_ref,
                subject_identifier=identifier,
                asserted_visit_at=asserted,
                attestation_code=attestation,
            )
            return result, result, False

        return run_idempotent(
            handler,
            request,
            operation=constants.OP_VISIT_CREATE,
            target_ref="none",
            public_fields={
                "visit_ref": visit_ref,
                "asserted_visit_at": asserted,
                "attestation_code": attestation,
            },
            secret_fields={"subject_identifier": identifier},
            run=run,
            status=201,
        )

    # Decorator sits on the boundary wrapper, not on the implementation,
    # so no path can bypass the unexpected-failure mapping.
    @app.post("/v1/doctor/verified-visits")
    async def create_visit(request: Request) -> JSONResponse:
        try:
            return await _impl_create_visit(request)
        except ApiError as error:
            return error_response_json(error)
        except Exception as error:  # noqa: BLE001 - mapped to declared 500
            return unexpected_failure_json(error)

    # ============================================================= V2 visit
    async def _impl_get_visit(visit_id: str, request: Request) -> JSONResponse:
        try:
            handler.settings()  # fail closed when operator material is unusable
            with write_transaction(handler.database) as session:
                actor = handler.authenticate(session, request, operation=constants.OP_VISIT_GET)
                handler.require_role(actor, constants.ROLE_DOCTOR)
                result = visits.get_visit(session, account=actor.account, visit_id=visit_id)
            return _response(200, envelope(**result))
        except ApiError as error:
            return error_response_json(error)

    # Decorator sits on the boundary wrapper, not on the implementation,
    # so no path can bypass the unexpected-failure mapping.
    @app.get("/v1/doctor/verified-visits/{visit_id}")
    async def get_visit(visit_id: str, request: Request) -> JSONResponse:
        try:
            return await _impl_get_visit(visit_id, request)
        except ApiError as error:
            return error_response_json(error)
        except Exception as error:  # noqa: BLE001 - mapped to declared 500
            return unexpected_failure_json(error)

    # ======================================================= I1 invitations
    async def _impl_create_invitation(visit_id: str, request: Request) -> JSONResponse:
        try:
            body = await handler.body(request, constants.OP_INVITATION_CREATE)
            identifier = handler.str_field(body, "subject_identifier", maximum=64)
            ttl = (
                handler.int_field(body, "ttl_seconds", minimum=3600, maximum=259200)
                if body.get("ttl_seconds") is not None
                else None
            )
        except ApiError as error:
            return error_response_json(error)

        def run(session, actor):
            handler.require_role(actor, constants.ROLE_DOCTOR)
            result = visits.issue_invitation(
                session,
                clock=handler.clock,
                settings=handler.settings(),
                account=actor.account,
                visit_id=visit_id,
                subject_identifier=identifier,
                ttl_seconds=ttl,
            )
            redacted = {key: value for key, value in result.items() if key != "access_code"}
            return result, redacted, True

        def failure_hook(error: ApiError | None, session: Session | None = None) -> None:
            # Record failed invitation attempts after rollback so evidence
            # survives even when the business transaction is rolled back
            # (C1-R07: failed subject-binding audit evidence surviving rollback).
            if error is not None and error.code == "invalid_invitation":
                if session is not None:
                    record(
                        session,
                        clock=handler.clock,
                        event_type=constants.EVENT_INVITATION_ATTEMPT_FAILED,
                        outcome=constants.OUTCOME_DENIED,
                        subject_type=constants.SUBJECT_VERIFIED_VISIT,
                        subject_id=visit_id,
                        code="invalid_invitation",
                    )
                else:
                    record_isolated(
                        handler.database,
                        clock=handler.clock,
                        event_type=constants.EVENT_INVITATION_ATTEMPT_FAILED,
                        outcome=constants.OUTCOME_DENIED,
                        subject_type=constants.SUBJECT_VERIFIED_VISIT,
                        subject_id=visit_id,
                        code="invalid_invitation",
                    )

        return run_idempotent(
            handler,
            request,
            operation=constants.OP_INVITATION_CREATE,
            target_ref=visit_id,
            public_fields={"ttl_seconds": ttl},
            secret_fields={"subject_identifier": identifier},
            run=run,
            failure_hook=failure_hook,
            status=201,
        )

    # Decorator sits on the boundary wrapper, not on the implementation,
    # so no path can bypass the unexpected-failure mapping.
    @app.post("/v1/doctor/verified-visits/{visit_id}/invitations")
    async def create_invitation(visit_id: str, request: Request) -> JSONResponse:
        try:
            return await _impl_create_invitation(visit_id, request)
        except ApiError as error:
            return error_response_json(error)
        except Exception as error:  # noqa: BLE001 - mapped to declared 500
            return unexpected_failure_json(error)

    # ====================================================== I2 revoke invite
    async def _impl_revoke_invitation(invitation_id: str, request: Request) -> JSONResponse:
        try:
            body = await handler.body(request, constants.OP_INVITATION_REVOKE)
            reason = handler.str_field(body, "reason_code", maximum=64)
        except ApiError as error:
            return error_response_json(error)

        def run(session, actor):
            handler.require_role(actor, constants.ROLE_DOCTOR)
            result = visits.revoke_invitation(
                session,
                clock=handler.clock,
                account=actor.account,
                invitation_id=invitation_id,
                reason_code=reason,
            )
            return result, result, False

        return run_idempotent(
            handler,
            request,
            operation=constants.OP_INVITATION_REVOKE,
            target_ref=invitation_id,
            public_fields={"reason_code": reason},
            secret_fields={},
            run=run,
        )

    # Decorator sits on the boundary wrapper, not on the implementation,
    # so no path can bypass the unexpected-failure mapping.
    @app.post("/v1/doctor/invitations/{invitation_id}/revoke")
    async def revoke_invitation(invitation_id: str, request: Request) -> JSONResponse:
        try:
            return await _impl_revoke_invitation(invitation_id, request)
        except ApiError as error:
            return error_response_json(error)
        except Exception as error:  # noqa: BLE001 - mapped to declared 500
            return unexpected_failure_json(error)

    # ========================================================== I3 get invite
    async def _impl_get_invitation(invitation_id: str, request: Request) -> JSONResponse:
        try:
            handler.settings()  # fail closed when operator material is unusable
            with write_transaction(handler.database) as session:
                actor = handler.authenticate(
                    session, request, operation=constants.OP_INVITATION_GET
                )
                handler.require_role(actor, constants.ROLE_DOCTOR)
                result = visits.get_invitation(
                    session, clock=handler.clock, account=actor.account, invitation_id=invitation_id
                )
            return _response(200, envelope(**result))
        except ApiError as error:
            return error_response_json(error)

    # Decorator sits on the boundary wrapper, not on the implementation,
    # so no path can bypass the unexpected-failure mapping.
    @app.get("/v1/doctor/invitations/{invitation_id}")
    async def get_invitation(invitation_id: str, request: Request) -> JSONResponse:
        try:
            return await _impl_get_invitation(invitation_id, request)
        except ApiError as error:
            return error_response_json(error)
        except Exception as error:  # noqa: BLE001 - mapped to declared 500
            return unexpected_failure_json(error)

    # ========================================================= E1 register
    async def _impl_register(request: Request) -> JSONResponse:
        try:
            body = await handler.body(request, constants.OP_REGISTER)
            access_code = handler.str_field(body, "access_code", minimum=32, maximum=256)
            identifier = handler.str_field(body, "identifier", maximum=64)
            email = handler.str_field(body, "email", maximum=254)
            password = handler.str_field(body, "password", minimum=1, maximum=1024)
            consent_ack = handler.bool_field(body, "consent_ack")
            settings = handler.settings()
        except ApiError as error:
            return error_response_json(error)

        # Independent source-based enrollment rate limiting (C1-R04):
        # separate from login lockout, keyed by enrollment_source hash.
        source_key = handler._source_key_for(request)
        enrollment_buckets = {
            "source": crypto.bucket_key_hash(
                settings.pepper, "enrollment_source", source_key
            )
        }

        actor_binding = crypto.actor_binding_anonymous(access_code)
        with read_transaction(handler.database) as lookup:
            invitation = enrollment.find_invitation_by_code(lookup, access_code)
            target_ref = invitation.invitation_id if invitation is not None else "none"

        def run(session, actor):
            # Source lockout check inside the write transaction (C1-R04).
            # Do not record another failure when already locked: the failure
            # hook records durable evidence after rollback, and recording
            # here would double-count the rate-limited attempt.
            if sessions.is_locked(session, enrollment_buckets, clock=handler.clock):
                raise sessions.rate_limited_error()
            result = enrollment.register_patient(
                session,
                clock=handler.clock,
                settings=settings,
                access_code=access_code,
                identifier=identifier,
                email=email,
                password=password,
                consent_ack=consent_ack,
            )
            redacted = {
                "user_id": result["user_id"],
                "patient_id": result["patient_id"],
                "assignment_id": result["assignment_id"],
                "subject_label": result["subject_label"],
            }
            return result, redacted, True

        def anonymous_run(session, _actor_unused):
            return run(session, None)

        def failure_hook(
            error: ApiError | None, session: Session | None = None
        ) -> None:
            _record_enrollment_failure(
                handler,
                settings=settings,
                access_code=access_code,
                target_ref=target_ref,
                code=error.code if error is not None else "internal_error",
                source_buckets=enrollment_buckets,
                session=session,
            )

        return _run_anonymous_idempotent(
            handler,
            request,
            operation=constants.OP_REGISTER,
            actor_binding=actor_binding,
            target_ref=target_ref,
            public_fields={"email": email, "consent_ack": consent_ack},
            secret_fields={
                "access_code": access_code,
                "identifier": identifier,
                "password": password,
            },
            run=anonymous_run,
            failure_hook=failure_hook,
            status=201,
        )

    # Decorator sits on the boundary wrapper, not on the implementation,
    # so no path can bypass the unexpected-failure mapping.
    @app.post("/v1/patients/register")
    async def register(request: Request) -> JSONResponse:
        try:
            return await _impl_register(request)
        except ApiError as error:
            return error_response_json(error)
        except Exception as error:  # noqa: BLE001 - mapped to declared 500
            return unexpected_failure_json(error)

    # ============================================================= E2 link
    async def _impl_link(request: Request) -> JSONResponse:
        try:
            body = await handler.body(request, constants.OP_LINK)
            access_code = handler.str_field(body, "access_code", minimum=32, maximum=256)
            identifier = handler.str_field(body, "identifier", maximum=64)
            accept = handler.bool_field(body, "accept_linking")
            settings = handler.settings()
        except ApiError as error:
            return error_response_json(error)

        # Independent source-based enrollment rate limiting for linking (C1-R04).
        source_key = handler._source_key_for(request)
        enrollment_buckets = {
            "source": crypto.bucket_key_hash(
                settings.pepper, "enrollment_source", source_key
            )
        }

        with read_transaction(handler.database) as lookup:
            invitation = enrollment.find_invitation_by_code(lookup, access_code)
            target_ref = invitation.invitation_id if invitation is not None else "none"

        def run(session, actor):
            # Source lockout check inside the write transaction (C1-R04).
            # Do not record another failure when already locked: the failure
            # hook records durable evidence after rollback.
            if sessions.is_locked(session, enrollment_buckets, clock=handler.clock):
                raise sessions.rate_limited_error()
            handler.require_role(actor, constants.ROLE_PATIENT)
            result = enrollment.link_patient(
                session,
                clock=handler.clock,
                settings=settings,
                account=actor.account,
                access_code=access_code,
                identifier=identifier,
                accept_linking=accept,
            )
            redacted = {
                "assignment_id": result["assignment_id"],
                "doctor_label": result["doctor_label"],
                "patient_id": result["patient_id"],
            }
            return result, redacted, False

        def failure_hook(
            error: ApiError | None, session: Session | None = None
        ) -> None:
            _record_enrollment_failure(
                handler,
                settings=settings,
                access_code=access_code,
                target_ref=target_ref,
                code=error.code if error is not None else "internal_error",
                source_buckets=enrollment_buckets,
                session=session,
            )

        return run_idempotent(
            handler,
            request,
            operation=constants.OP_LINK,
            target_ref=target_ref,
            public_fields={"accept_linking": accept},
            secret_fields={"access_code": access_code, "identifier": identifier},
            failure_hook=failure_hook,
            run=run,
        )

    # Decorator sits on the boundary wrapper, not on the implementation,
    # so no path can bypass the unexpected-failure mapping.
    @app.post("/v1/patients/link")
    async def link(request: Request) -> JSONResponse:
        try:
            return await _impl_link(request)
        except ApiError as error:
            return error_response_json(error)
        except Exception as error:  # noqa: BLE001 - mapped to declared 500
            return unexpected_failure_json(error)

    # ======================================================== E3 assignments
    async def _impl_my_assignments(request: Request) -> JSONResponse:
        try:
            handler.settings()  # fail closed when operator material is unusable
            with write_transaction(handler.database) as session:
                actor = handler.authenticate(
                    session, request, operation=constants.OP_ASSIGNMENTS
                )
                handler.require_role(actor, constants.ROLE_PATIENT)
                result = enrollment.list_assignments(session, account=actor.account)
            return _response(200, envelope(**result))
        except ApiError as error:
            return error_response_json(error)

    # Decorator sits on the boundary wrapper, not on the implementation,
    # so no path can bypass the unexpected-failure mapping.
    @app.get("/v1/me/assignments")
    async def my_assignments(request: Request) -> JSONResponse:
        try:
            return await _impl_my_assignments(request)
        except ApiError as error:
            return error_response_json(error)
        except Exception as error:  # noqa: BLE001 - mapped to declared 500
            return unexpected_failure_json(error)

    # ============================================ E4 doctor revoke assignment
    async def _impl_doctor_revoke_assignment(assignment_id: str, request: Request) -> JSONResponse:
        try:
            body = await handler.body(request, constants.OP_ASSIGNMENT_DOCTOR_REVOKE)
            reason = handler.str_field(body, "reason_code", maximum=64)
        except ApiError as error:
            return error_response_json(error)

        def run(session, actor):
            handler.require_role(actor, constants.ROLE_DOCTOR)
            result = enrollment.revoke_assignment_as_doctor(
                session,
                clock=handler.clock,
                account=actor.account,
                assignment_id=assignment_id,
                reason_code=reason,
            )
            return result, result, False

        return run_idempotent(
            handler,
            request,
            operation=constants.OP_ASSIGNMENT_DOCTOR_REVOKE,
            target_ref=assignment_id,
            public_fields={"reason_code": reason},
            secret_fields={},
            run=run,
        )

    # Decorator sits on the boundary wrapper, not on the implementation,
    # so no path can bypass the unexpected-failure mapping.
    @app.post("/v1/doctor/assignments/{assignment_id}/revoke")
    async def doctor_revoke_assignment(assignment_id: str, request: Request) -> JSONResponse:
        try:
            return await _impl_doctor_revoke_assignment(assignment_id, request)
        except ApiError as error:
            return error_response_json(error)
        except Exception as error:  # noqa: BLE001 - mapped to declared 500
            return unexpected_failure_json(error)

    # =========================================== E5 patient revoke assignment
    async def _impl_patient_revoke_assignment(assignment_id: str, request: Request) -> JSONResponse:
        try:
            body = await handler.body(request, constants.OP_ASSIGNMENT_PATIENT_REVOKE)
            reason = handler.str_field(body, "reason_code", maximum=64)
        except ApiError as error:
            return error_response_json(error)

        def run(session, actor):
            handler.require_role(actor, constants.ROLE_PATIENT)
            result = enrollment.revoke_assignment_as_patient(
                session,
                clock=handler.clock,
                account=actor.account,
                assignment_id=assignment_id,
                reason_code=reason,
            )
            return result, result, False

        return run_idempotent(
            handler,
            request,
            operation=constants.OP_ASSIGNMENT_PATIENT_REVOKE,
            target_ref=assignment_id,
            public_fields={"reason_code": reason},
            secret_fields={},
            run=run,
        )

    # Decorator sits on the boundary wrapper, not on the implementation,
    # so no path can bypass the unexpected-failure mapping.
    @app.post("/v1/me/assignments/{assignment_id}/revoke")
    async def patient_revoke_assignment(assignment_id: str, request: Request) -> JSONResponse:
        try:
            return await _impl_patient_revoke_assignment(assignment_id, request)
        except ApiError as error:
            return error_response_json(error)
        except Exception as error:  # noqa: BLE001 - mapped to declared 500
            return unexpected_failure_json(error)

    # ============================================================ E6 consent
    async def _impl_patient_revoke_consent(request: Request) -> JSONResponse:
        try:
            body = await handler.body(request, constants.OP_CONSENT_REVOKE)
            reason = handler.str_field(body, "reason_code", maximum=64)
        except ApiError as error:
            return error_response_json(error)

        def run(session, actor):
            handler.require_role(actor, constants.ROLE_PATIENT)
            result = enrollment.revoke_consent(
                session, clock=handler.clock, account=actor.account, reason_code=reason
            )
            return result, result, False

        return run_idempotent(
            handler,
            request,
            operation=constants.OP_CONSENT_REVOKE,
            target_ref="none",
            public_fields={"reason_code": reason},
            secret_fields={},
            run=run,
        )


    # Decorator sits on the boundary wrapper, not on the implementation,
    # so no path can bypass the unexpected-failure mapping.
    @app.post("/v1/me/consent/synthetic-demo/revoke")
    async def patient_revoke_consent(request: Request) -> JSONResponse:
        try:
            return await _impl_patient_revoke_consent(request)
        except ApiError as error:
            return error_response_json(error)
        except Exception as error:  # noqa: BLE001 - mapped to declared 500
            return unexpected_failure_json(error)

def _environment_configured() -> bool:

    from .settings import missing_variables

    return not missing_variables()


class _LoginSucceeded(Exception):
    """Internal marker: the login business effect committed."""


def _record_login_failure(handler: Term1Handler, settings, buckets, error: ApiError) -> None:
    if error.code not in {"invalid_credentials", "rate_limited"}:
        return
    # Write the attempt counter in its own transaction so a rejected attempt
    # still leaves durable evidence (C1.9). Never swallow the write error: a
    # counter-write problem must surface rather than being silently ignored.
    with write_transaction(handler.database) as session:
        # Ensure pepper binding precedes the first pepper-dependent durable
        # write (LoginAttempt.bucket_key_hash is pepper-derived).
        if not database_is_populated(session):
            verify_or_activate(session, settings=settings, clock=handler.clock, write=True)
        sessions.record_login_failure(
            session,
            clock=handler.clock,
            buckets=buckets,
            outcome="rate_limited" if error.code == "rate_limited" else "invalid",
        )
    record_isolated(
        handler.database,
        clock=handler.clock,
        event_type=constants.EVENT_LOGIN_FAILED,
        outcome=constants.OUTCOME_RATE_LIMITED
        if error.code == "rate_limited"
        else constants.OUTCOME_FAILED,
        subject_type=constants.SUBJECT_SESSION,
        code=error.code,
    )


def _record_enrollment_failure(
    handler: Term1Handler,
    *,
    settings: Term1Settings,
    access_code: str,
    target_ref: str,
    code: str,
    source_buckets: dict[str, str] | None = None,
    session: Session | None = None,
) -> None:
    """Record one audit event and applicable counters under one write lock.

    A caller-provided session owns the outer transaction after savepoint
    rollback. Never open another writer while that transaction is active.
    Non-guessing outcomes and locked retries do not mutate attempt counters.
    Failure to persist mandatory evidence propagates, rather than silently
    allowing a credential attempt to bypass the durable limits.
    """
    known = target_ref != "none"

    def _record_in_session(sess: Session) -> None:
        if code not in ENROLLMENT_GUESSING_CODES_EXCLUDED and code != "rate_limited":
            verify_or_activate(sess, settings=settings, clock=handler.clock, write=True)
            invitation = enrollment.find_invitation_by_code(sess, access_code)
            enrollment.record_failure(
                sess,
                clock=handler.clock,
                invitation=invitation,
                code_digest=crypto.unknown_code_digest(settings.pepper, access_code),
                outcome=code,
            )
            if source_buckets:
                sessions.record_login_failure(
                    sess,
                    clock=handler.clock,
                    buckets=source_buckets,
                    outcome="invalid",
                )
        record(
            sess,
            clock=handler.clock,
            event_type=constants.EVENT_INVITATION_ATTEMPT_FAILED,
            outcome=constants.OUTCOME_FAILED,
            subject_type=constants.SUBJECT_INVITATION if known else constants.SUBJECT_UNKNOWN_INVITATION,
            subject_id=target_ref if known else None,
            code=code,
            payload={"invitation_known": known, "already_locked": code == "rate_limited"},
        )

    if session is not None:
        _record_in_session(session)
    else:
        with write_transaction(handler.database) as standalone:
            _record_in_session(standalone)


def _run_anonymous_idempotent(
    handler: Term1Handler,
    request: Request,
    *,
    operation: str,
    actor_binding: str,
    target_ref: str,
    public_fields: Mapping[str, Any],
    secret_fields: Mapping[str, str],
    run: Callable[[Any, Actor | None], tuple[dict[str, Any], dict[str, Any], bool]],
    failure_hook: Callable[[ApiError | None], None],
    status: int,
) -> JSONResponse:
    """Anonymous enrollment replay, bound to the invitation verifier digest.

    As with :func:`run_idempotent`, operator key material is resolved inside the
    guarded block so an unusable configuration yields the catalogue's ``503
    identity_key_configuration_error`` instead of an unhandled HTTP 500.
    """
    try:
        settings = handler.settings()
        raw_key = handler.idempotency_key(request)
    except ApiError as error:
        return error_response_json(error)
    identity = build_identity(
        pepper=settings.pepper,
        scope=(constants.REPLAY_SCOPE_ANONYMOUS, actor_binding),
        operation=operation,
        target_ref=target_ref,
        raw_key=raw_key,
        public_fields=public_fields,
        secret_fields=secret_fields,
    )
    try:
        with write_transaction(handler.database) as session:
            nested = session.begin_nested()
            try:
                verify_or_activate(session, settings=settings, clock=handler.clock, write=True)
                session.flush()
                decision = precheck(session, clock=handler.clock, identity=identity)
                if decision.is_replay:
                    return _response(status, envelope(**decision.body()))
                result, redacted, disclosed = run(session, None)
                remember(
                    session,
                    clock=handler.clock,
                    identity=identity,
                    status_code=status,
                    public_response=redacted,
                    secret_disclosed=disclosed,
                )
                return _response(status, envelope(**result))
            except ApiError as error:
                # Roll back business writes to the savepoint: no partial
                # account, assignment, consent or redemption effects survive.
                nested.rollback()
                # Reset the session so objects added after the savepoint
                # rollback are tracked by the outer transaction.
                session.expire_all()
                # Record durable failure evidence inside the same transaction
                # before the lock is released.
                failure_hook(error, session=session)
                # Return the error response directly: the outer
                # write_transaction will commit the failure evidence when it
                # exits normally (no exception propagates).
                return error_response_json(error)
    except ApiError as error:
        return error_response_json(error)
    except Exception as error:  # pragma: no cover - defensive
        failure_hook(None)
        raise error
