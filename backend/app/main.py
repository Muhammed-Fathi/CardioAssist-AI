"""Run from the repository root:

python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 1

Synthetic/demo inputs only. No auth, durable storage or production guarantees.
"""

from __future__ import annotations

import json
import math
import time
from typing import Any, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from .contracts import CAD_PATH, MONITORING_PATH, ContractFiles, ContractViolation
from .state import MockState


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object member.")
        result[key] = value
    return result


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Non-finite JSON number.")
    return number


def _reject_constant(value: str) -> None:
    raise ValueError("Non-standard JSON numeric constant.")


async def _read_json(request: Request) -> Any:
    media_type = request.headers.get("content-type", "").partition(";")[0].strip().lower()
    if media_type != "application/json":
        raise ContractViolation(400, "malformed_request", "An application/json request body is required.")
    raw = await request.body()
    try:
        return json.loads(
            raw.decode("utf-8"), object_pairs_hook=_unique_object,
            parse_float=_finite_float, parse_constant=_reject_constant,
        )
    except (ValueError, UnicodeError, RecursionError) as error:
        raise ContractViolation(400, "malformed_request", "Request body is not valid UTF-8 JSON.") from error


def create_app(*, clock: Callable[[], float] = time.monotonic) -> FastAPI:
    contracts = ContractFiles()
    state = MockState(contracts, clock=clock)
    app = FastAPI(
        title="CardioAssist AI — MOCK_SYNTHETIC backend",
        docs_url=None, redoc_url=None,  # No CDN or external documentation assets.
        redirect_slashes=False,
    )
    app.state.mock = state
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

    return app


app = create_app()
