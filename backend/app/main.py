"""Run from the repository root after `python -m alembic upgrade head`:

python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 1

CAD output remains MOCK_SYNTHETIC, produced by the single internal inference
provider (``backend/app/inference``). The legacy monitoring write path keeps its
three-table persistence and success audit.

Term 1 C1 (``backend/app/term1``) adds authentication, verified enrollment and
durable identity workflows as twenty additional ``/v1`` operations. They are
additive: the two legacy operations above are unchanged. Term 1 operator secrets
come from the environment only; when they are absent every Term 1 route fails
closed while the legacy routes keep working. The offline research-artifact
validator is still not imported by this application.
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from .contracts import CAD_PATH, MONITORING_PATH, ContractFiles, ContractViolation
from .main_helpers import finite_float, reject_constant, unique_object
from .state import MockState
from .storage.database import Database
from .storage.monitoring import MonitoringRepository
from .term1.api import Term1Handler, register_term1_routes
from .term1.c2_api import register_c2_routes
from .term1.clock_provider import clock_from
from .term1.openapi import compose_openapi
from .term1.settings import Term1Settings
from .term1.timeutil import Clock


async def _read_json(request: Request) -> Any:
    media_type = request.headers.get("content-type", "").partition(";")[0].strip().lower()
    if media_type != "application/json":
        raise ContractViolation(400, "malformed_request", "An application/json request body is required.")
    raw = await request.body()
    try:
        return json.loads(
            raw.decode("utf-8"), object_pairs_hook=unique_object,
            parse_float=finite_float, parse_constant=reject_constant,
        )
    except (ValueError, UnicodeError, RecursionError) as error:
        raise ContractViolation(400, "malformed_request", "Request body is not valid UTF-8 JSON.") from error


def _source_key(request: Request) -> str:
    """Per-source rate-limit key from the TCP peer only.

    ``X-Forwarded-For`` and friends are never trusted: a client cannot choose
    its own rate-limit bucket by inventing a header. Behind a TLS-terminating
    proxy the operator configures the single-process deployment's trusted peer
    address instead of accepting forwarded values.
    """
    client = request.client
    return client.host if client is not None and client.host else "unknown-source"


def create_app(
    *,
    clock: Callable[[], float] = time.monotonic,
    database_url: str | None = None,
    term1_settings: Term1Settings | None = None,
    term1_clock: Callable[[], object] | None = None,
) -> FastAPI:
    contracts = ContractFiles()
    database = Database(database_url)
    monitoring_repository = MonitoringRepository(database)
    state = MockState(contracts, monitoring_repository, clock=clock)
    term1_clock = Clock(clock_from(term1_clock))

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            # Do not silently create/upgrade tables at service startup.
            database.verify_schema()
            # Read-only identity-key verification. A populated database whose
            # key material no longer matches its key-check metadata refuses to
            # start. Unconfigured operator secrets are not a startup failure:
            # the legacy routes stay usable and every Term 1 route fails closed
            # with 503 identity_key_configuration_error per request.
            handler: Term1Handler | None = getattr(app.state, "term1", None)
            if handler is not None:
                handler.verify_identity_keys()
            yield
        finally:
            database.dispose()

    app = FastAPI(
        title="CardioAssist AI — MOCK_SYNTHETIC backend",
        docs_url=None, redoc_url=None,  # No CDN or external documentation assets.
        redirect_slashes=False,
        lifespan=lifespan,
    )
    app.state.mock = state
    app.state.database = database
    app.state.monitoring_repository = monitoring_repository
    app.openapi = contracts.bundled_openapi

    async def handle(request: Request, path: str) -> JSONResponse:
        body = None
        try:
            keys = request.headers.getlist("idempotency-key")
            if len(keys) > 1:
                raise ContractViolation(
                    400, "malformed_request", "Supply exactly one Idempotency-Key header.",
                    details=[{"field": "Idempotency-Key"}],
                )
            body = await _read_json(request)
            # The synchronous lock/transaction runs off the event-loop thread.
            status, response = await run_in_threadpool(
                state.execute, path, body, keys[0] if keys else None
            )
        except ContractViolation as error:
            status, response = error.status, contracts.error_body(error, body)
        except Exception:
            status, response = 500, state.internal_error(path, body)
        return JSONResponse(response, status_code=status, headers={"Cache-Control": "no-store"})

    @app.post(CAD_PATH)
    async def create_cad_prediction(request: Request) -> JSONResponse:
        return await handle(request, CAD_PATH)

    @app.post(MONITORING_PATH, status_code=201)
    async def create_monitoring_observation(request: Request) -> JSONResponse:
        return await handle(request, MONITORING_PATH)

    # Additive Term 1 C1 surface. The legacy OpenAPI document served at
    # /openapi.json is composed separately (see backend/app/term1/openapi.py).
    term1_handler = Term1Handler(
        database=database,
        clock=term1_clock,
        settings=term1_settings,
        source_key_for=_source_key,
    )
    app.state.term1 = term1_handler
    register_term1_routes(app, handler=term1_handler)
    # Additive Term 1 C2 clinical-intake surface (SAFE_SCOPE); composed into
    # the same served OpenAPI document (see backend/app/term1/openapi.py).
    register_c2_routes(app, handler=term1_handler)
    app.openapi = compose_openapi(contracts)

    return app


app = create_app()
