"""Single-process, prototype-only state. EVERYTHING resets on restart.

One lock covers conflict/replay lookup, validation, mock inference, response
validation, observation storage and audit publication. No await occurs inside
that transaction. Multiple Uvicorn workers/replicas are NOT supported.
"""

from __future__ import annotations

import copy
import logging
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable

from .contracts import CAD_PATH, ContractFiles, ContractViolation
from .mock_prediction import build_prediction, payload_hash
from .validation import validate_cad, validate_monitoring

logger = logging.getLogger(__name__)
AUDIT_NAMESPACE = uuid.UUID("9e139be5-1516-59e8-b50c-45c834786b99")
OBSERVATION_NAMESPACE = uuid.uuid5(
    uuid.NAMESPACE_URL, "https://cardioassist.local/mock/fixtures/v1/observation"
)
REQUEST_NAMESPACE = uuid.uuid5(
    uuid.NAMESPACE_URL, "https://cardioassist.local/mock/backend/v1/request"
)


@dataclass(frozen=True)
class AuditEvent:
    """Test-visible metadata, not a persistent/compliant/tamper-proof audit log."""

    event_id: str
    event_type: str
    path: str
    request_id: str | None = None
    payload_sha256: str | None = None
    model_id: str | None = None


@dataclass(frozen=True)
class IdempotencyRecord:
    path: str
    payload_sha256: str
    status: int
    response: dict[str, Any]
    result_id: str
    created_at: float


class MockState:
    def __init__(
        self, contracts: ContractFiles, *, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.contracts = contracts
        self._clock = clock
        self._lock = threading.RLock()
        # Global key namespace matches the merged reference implementation.
        # Route identity is also checked: never replay one track into another.
        self._idempotency: dict[str, IdempotencyRecord] = {}
        self._attempts: dict[str, int] = {}
        self._keyless_attempts = 0
        self._audit_events: list[AuditEvent] = []
        self._observations: dict[str, dict[str, Any]] = {}
        self._inference_count = 0

    @property
    def audit_events(self) -> tuple[AuditEvent, ...]:
        with self._lock:
            return tuple(self._audit_events)

    @property
    def inference_count(self) -> int:
        with self._lock:
            return self._inference_count

    @property
    def observations(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return copy.deepcopy(self._observations)

    def execute(
        self, path: str, body: Any, key: str | None
    ) -> tuple[int, dict[str, Any]]:
        if not isinstance(body, dict):
            noun = "prediction request" if path == CAD_PATH else "monitoring observation"
            raise ContractViolation(400, "malformed_request", f"Request body is not a valid {noun} object.")
        required = self.contracts.openapi["paths"][path]["post"]["x-idempotency"]["required"]
        if (key is None and required) or (
            key is not None and not self.contracts.component("IdempotencyKey").is_valid(key)
        ):
            raise ContractViolation(
                400, "malformed_request", "A valid Idempotency-Key header is required for this write.",
                details=[{"field": "Idempotency-Key"}],
            )
        try:
            digest = payload_hash(body)
        except (ValueError, UnicodeError, RecursionError) as error:
            raise ContractViolation(
                400, "malformed_request", "Request body cannot be canonicalized as UTF-8 JSON."
            ) from error
        with self._lock:
            now = self._clock()
            previous = self._idempotency.get(key) if key is not None else None
            if previous is not None:
                ttl = self.contracts.retention_seconds[previous.path]
                if now - previous.created_at >= ttl:
                    del self._idempotency[key]
                    logger.info(
                        "mock_idempotency_expired path=%s result_id=%s",
                        previous.path, previous.result_id,
                    )
                    previous = None
            # The active task and OpenAPI explicitly require unconditional
            # conflict precedence, including an invalid second semantic payload.
            # Parsing/object/header failures necessarily happen before hashing.
            if previous is not None:
                if previous.path != path or previous.payload_sha256 != digest:
                    raise ContractViolation(
                        409, "idempotency_key_conflict",
                        "This Idempotency-Key was already used with a different request payload.",
                        details=[{
                            "field": "Idempotency-Key",
                            "expected": "an unused key, or the same key with an identical payload",
                            "received": key,
                        }] if path == CAD_PATH else None,
                        original_audit_id=previous.result_id,
                    )
                response = copy.deepcopy(previous.response)
                response["idempotent_replay"] = True
                return previous.status, response

            if path == CAD_PATH:
                model, provided, missing = validate_cad(self.contracts, body)
            else:
                recorded_count = validate_monitoring(self.contracts, body)

            # Assign an attempt only after acceptance; even a 500 below does
            # not consume a key or advance its successful-result identifier.
            attempt = self._attempts.get(key, 0) + 1 if key is not None else self._keyless_attempts + 1
            seed = f"{key or '-'}|{digest}|{attempt}"
            request_id = body.get("request_id", str(uuid.uuid5(REQUEST_NAMESPACE, f"{path}|{seed}")))
            namespace = AUDIT_NAMESPACE if path == CAD_PATH else OBSERVATION_NAMESPACE
            result_id = str(uuid.uuid5(namespace, seed))
            if path == CAD_PATH:
                response = build_prediction(self.contracts, model, provided, missing, request_id, result_id)
                event = AuditEvent(
                    result_id, "prediction_created", path, request_id, digest, model["model_id"]
                )
            else:
                response = copy.deepcopy(self.contracts.monitoring_template)
                response.update(
                    request_id=request_id, observation_id=result_id,
                    idempotent_replay=False, recorded_metric_count=recorded_count,
                )
                event = AuditEvent(result_id, "observation_recorded", path, request_id, digest)
            self.contracts.responses[path].validate(response)
            status = self.contracts.success_status[path]
            record = IdempotencyRecord(path, digest, status, copy.deepcopy(response), result_id, now)
            observation = None
            if path != CAD_PATH:
                observation = copy.deepcopy(body["observation"])
                observation["metrics"] = [
                    metric for metric in observation["metrics"] if metric["value"] is not None
                ]

            # Publish only after response construction AND schema validation.
            if key is not None:
                self._idempotency[key] = record
                self._attempts[key] = attempt
            else:
                self._keyless_attempts = attempt
            if path == CAD_PATH:
                self._inference_count += 1
            else:
                self._observations[result_id] = observation
            self._audit_events.append(event)
            return status, response

    def internal_error(self, path: str, body: Any) -> dict[str, Any]:
        audit_id = str(uuid.uuid4())
        request_id = body.get("request_id") if isinstance(body, dict) else None
        if not self.contracts.component("Uuid").is_valid(request_id):
            request_id = None
        with self._lock:
            self._audit_events.append(AuditEvent(audit_id, "internal_error", path, request_id))
        # No request bodies, header keys, raw measurements or exception details
        # in the log/client response. This is not a production audit facility.
        logger.error("mock_internal_error audit_id=%s path=%s", audit_id, path)
        return self.contracts.error_body(
            ContractViolation(
                500, "internal_error", "The request could not be completed because of an internal error."
            ),
            body, audit_id=audit_id,
        )
