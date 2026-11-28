"""C2 HTTP boundary wrappers: H1a, H1b, S1, S2, S3.

Each route follows the frozen C1 pattern: an ``_impl_*`` function doing the
work (ApiError -> closed error envelope) behind a decorator wrapper that also
maps unexpected exceptions to the static ``500 internal_error`` envelope.
H1b and S1 run through ``run_idempotent`` (``target_ref="none"``) with the
C2 ``on_replay`` live-reauthorization hook; H1a/S2/S3 are plain authenticated
reads inside one ``BEGIN IMMEDIATE`` transaction (session touch included).

No route here can return a score: S1 is always status-only, S2 patient
projection is pre-``B`` status-only with ``research_output: null``, and the
doctor projection is pre-``A3`` (no result is ever read).
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from . import assessments, constants, health_profile
from .api import (
    Actor,
    Term1Handler,
    _response,
    envelope,
    error_response_json,
    run_idempotent,
    unexpected_failure_json,
)
from .c2_authz import (
    require_active_consent,
    require_clinical_patient,
    require_owned_assignment,
)
from .errors import ApiError
from .tx import write_transaction


def register_c2_routes(app: FastAPI, *, handler: Term1Handler) -> None:
    # ================================================== H1a current profile
    async def _impl_health_profile_get(request: Request) -> JSONResponse:
        try:
            handler.settings()  # fail closed when operator material is unusable
            with write_transaction(handler.database) as session:
                actor = handler.authenticate(
                    session, request, operation=constants.OP_HEALTH_PROFILE_GET
                )
                result = health_profile.get_health_profile(
                    session, account=actor.account
                )
            return _response(200, envelope(**result))
        except ApiError as error:
            return error_response_json(error)

    @app.get("/v1/me/health-profile")
    async def health_profile_get(request: Request) -> JSONResponse:
        try:
            return await _impl_health_profile_get(request)
        except ApiError as error:
            return error_response_json(error)
        except Exception as error:  # noqa: BLE001 - mapped to declared 500
            return unexpected_failure_json(error)

    # ================================================== H1b patch profile
    async def _impl_health_profile_patch(request: Request) -> JSONResponse:
        try:
            body = await handler.body(request, constants.OP_HEALTH_PROFILE_PATCH)
        except ApiError as error:
            return error_response_json(error)

        def run(session: Session, actor: Actor):
            result = health_profile.patch_health_profile(
                session,
                clock=handler.clock,
                account=actor.account,
                body=body,
            )
            return result, result, False

        def on_replay(session: Session, actor: Actor) -> None:
            # Live reauthorization before any cached 2xx (checkpoint §7).
            profile = require_clinical_patient(session, account=actor.account)
            require_active_consent(session, patient_id=profile.patient_id)

        return run_idempotent(
            handler,
            request,
            operation=constants.OP_HEALTH_PROFILE_PATCH,
            target_ref="none",
            public_fields=dict(body),
            secret_fields={},
            run=run,
            status=200,
            on_replay=on_replay,
        )

    @app.patch("/v1/me/health-profile")
    async def health_profile_patch(request: Request) -> JSONResponse:
        try:
            return await _impl_health_profile_patch(request)
        except ApiError as error:
            return error_response_json(error)
        except Exception as error:  # noqa: BLE001 - mapped to declared 500
            return unexpected_failure_json(error)

    # ============================================================ S1 submit
    async def _impl_assessment_create(request: Request) -> JSONResponse:
        try:
            body = await handler.body(request, constants.OP_ASSESSMENT_CREATE)
        except ApiError as error:
            return error_response_json(error)

        def run(session: Session, actor: Actor):
            result = assessments.submit_assessment(
                session,
                clock=handler.clock,
                account=actor.account,
                body=body,
            )
            return result, result, False

        def on_replay(session: Session, actor: Actor) -> None:
            # Consent first, then the exact assignment — the same operation-
            # specific live scope as the first execution (checkpoint §7).
            profile = require_clinical_patient(session, account=actor.account)
            require_active_consent(session, patient_id=profile.patient_id)
            require_owned_assignment(
                session,
                assignment_id=str(body.get("assignment_id")),
                patient_id=profile.patient_id,
            )

        return run_idempotent(
            handler,
            request,
            operation=constants.OP_ASSESSMENT_CREATE,
            target_ref="none",
            public_fields=dict(body),
            secret_fields={},
            run=run,
            status=201,
            on_replay=on_replay,
        )

    @app.post("/v1/assessments", status_code=201)
    async def assessment_create(request: Request) -> JSONResponse:
        try:
            return await _impl_assessment_create(request)
        except ApiError as error:
            return error_response_json(error)
        except Exception as error:  # noqa: BLE001 - mapped to declared 500
            return unexpected_failure_json(error)

    # ============================================================ S2 detail
    async def _impl_assessment_get(
        assessment_id: str, request: Request
    ) -> JSONResponse:
        try:
            handler.settings()
            with write_transaction(handler.database) as session:
                actor = handler.authenticate(
                    session, request, operation=constants.OP_ASSESSMENT_GET
                )
                result = assessments.get_assessment(
                    session,
                    clock=handler.clock,
                    account=actor.account,
                    assessment_id=assessment_id,
                )
            return _response(200, envelope(**result))
        except ApiError as error:
            return error_response_json(error)

    @app.get("/v1/assessments/{assessment_id}")
    async def assessment_get(assessment_id: str, request: Request) -> JSONResponse:
        try:
            return await _impl_assessment_get(assessment_id, request)
        except ApiError as error:
            return error_response_json(error)
        except Exception as error:  # noqa: BLE001 - mapped to declared 500
            return unexpected_failure_json(error)

    # ============================================================= S3 list
    async def _impl_assessments_list(request: Request) -> JSONResponse:
        try:
            handler.settings()
            with write_transaction(handler.database) as session:
                actor = handler.authenticate(
                    session, request, operation=constants.OP_ME_ASSESSMENTS
                )
                result = assessments.list_assessments(
                    session,
                    clock=handler.clock,
                    account=actor.account,
                    limit_raw=request.query_params.get("limit"),
                    cursor_raw=request.query_params.get("cursor"),
                )
            return _response(200, envelope(**result))
        except ApiError as error:
            return error_response_json(error)

    @app.get("/v1/me/assessments")
    async def assessments_list(request: Request) -> JSONResponse:
        try:
            return await _impl_assessments_list(request)
        except ApiError as error:
            return error_response_json(error)
        except Exception as error:  # noqa: BLE001 - mapped to declared 500
            return unexpected_failure_json(error)
