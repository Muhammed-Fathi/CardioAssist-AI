"""Reference implementation of the CardioAssist AI v1 contract semantics.

**This module is a TEST ORACLE, not a server.** It contains no HTTP layer, no
framework, no database and no model. It exists so that the fixture pack in
``shared/contracts/fixtures/`` can be checked against a single, explicit,
deterministic reading of the contract instead of against prose.

Everything here is MOCK / SYNTHETIC:

* the "model" is a hard-coded deterministic arithmetic function with no clinical
  meaning, no fitted parameters and no predictive validity;
* the "explanations" are hand-authored deterministic offsets that satisfy the
  documented margin-scale sum-check; they are **not** computed by SHAP or LIME
  from any model;
* no dataset, patient record or credential is read at any point.

Phase 0 references: §R2-6.1 (idempotency), §R2-6.2 (schemas), §R2-6.4
(response), §R2-6.5 (explanation ↔ calibrated score), §R2-6.6 (fixtures
F-01…F-12), §F-4 (wearable rejection), §F-6 (cohort-scoped calibration).
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import pathlib
import uuid
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTRACTS_DIR = REPO_ROOT / "shared" / "contracts"
SCHEMAS_DIR = CONTRACTS_DIR / "schemas"
REGISTRY_DIR = CONTRACTS_DIR / "registry"
FIXTURES_DIR = CONTRACTS_DIR / "fixtures"

CONTRACT_VERSION = "v1"

#: Frozen clock so that every mock response is byte-stable. The mock never
#: reads the wall clock.
MOCK_CLOCK = "2026-10-16T12:00:00Z"

#: Deterministic namespaces for the mock identifiers. A real implementation
#: would use random UUIDs; the mock derives them so that fixtures are
#: reproducible and a reviewer can recompute them by hand.
MOCK_AUDIT_NAMESPACE = uuid.uuid5(
    uuid.NAMESPACE_URL, "https://cardioassist.local/mock/fixtures/v1/audit"
)
MOCK_OBSERVATION_NAMESPACE = uuid.uuid5(
    uuid.NAMESPACE_URL, "https://cardioassist.local/mock/fixtures/v1/observation"
)

#: The only context sources that may reach CAD inference (Phase 0 §F-4).
VALID_CAD_SOURCES = ("benchmark_import", "clinician_entry")

#: Field names that identify wearable / monitoring content. Such a payload is
#: rejected for CAD inference before any other feature rule is applied
#: (Phase 0 §F-4, D-039).
WEARABLE_FIELD_NAMES = frozenset(
    {
        "heart_rate",
        "heart_rate_bpm",
        "hr",
        "hrv",
        "steps",
        "step_count",
        "spo2",
        "spo2_percent",
        "sleep_minutes",
        "wearable",
        "wearable_ecg",
        "ecg_waveform",
        "device_timestamp",
        "pedometer",
    }
)

#: Fallback list of wearable source tokens; the authoritative list is read from
#: the contract itself (common.schema.json -> CadInferenceSource).
DEFAULT_WEARABLE_SOURCE_TOKENS = (
    "simulated_wearable",
    "wearable_device",
    "health_connect",
    "health_kit",
    "apple_health",
    "vendor_app",
    "fitbit",
    "garmin",
    "oura",
    "whoop",
)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def load_json(path: pathlib.Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def canonical_json(value: Any) -> str:
    """Canonical JSON serialization used for the idempotency payload hash.

    UTF-8, lexicographically sorted object keys, no insignificant whitespace.
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_payload(body: Dict[str, Any]) -> str:
    """Canonical payload of a request body.

    ``request_id`` is removed: it is an informational correlation id, so a
    retry that regenerates it must still be recognised as a replay
    (Phase 0 §R2-6.1).
    """
    payload = {k: v for k, v in body.items() if k != "request_id"}
    return canonical_json(payload)


def payload_hash(body: Dict[str, Any]) -> str:
    return hashlib.sha256(canonical_payload(body).encode("utf-8")).hexdigest()


def deterministic_offset(feature_id: str, value: Any) -> float:
    """Deterministic, non-clinical contribution offset in [-0.05, 0.05].

    The offset is derived from a SHA-256 digest of the feature id and value, so
    it is stable across runs and machines while carrying **no** direction of
    association with any real quantity. A clinical reading ("older age raises
    the score") is therefore impossible to infer from a mock fixture.
    """
    digest = hashlib.sha256(
        f"{feature_id}|{canonical_json(value)}".encode("utf-8")
    ).digest()
    steps = int.from_bytes(digest[:4], "big") % 11  # 0..10
    return round(steps * 0.01 - 0.05, 2)


def typed_value_alternative(value_schema: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return the non-null typed rule behind a feature's value constraint.

    A feature value rule is either a plain typed rule (every required slot) or
    the nullable shape approved by ADR-001 Option A (D-044)::

        {"anyOf": [{"type": "null"}, <the original typed/ranged rule>]}

    which the optional slots now use. Exactly that shape is recognised: two
    alternatives, one of them exactly ``{"type": "null"}`` and one non-null
    typed rule, and nothing beside ``anyOf``. The oracle reads the constraint
    out of the committed schema itself; it does not import the backend's
    schema reader and it does not accept any other ``anyOf`` shape.

    ``None`` is returned for a rule the oracle does not understand, so that
    the caller fails closed instead of silently skipping the type check.
    """
    if "type" in value_schema:
        return value_schema
    if set(value_schema) != {"anyOf"}:
        return None
    alternatives = value_schema["anyOf"]
    if not isinstance(alternatives, list) or len(alternatives) != 2:
        return None
    if sum(1 for alternative in alternatives if alternative == {"type": "null"}) != 1:
        return None
    typed = [alternative for alternative in alternatives if alternative != {"type": "null"}]
    if len(typed) != 1:
        return None
    rule = typed[0]
    if not isinstance(rule, dict):
        return None
    if not isinstance(rule.get("type"), str) or rule["type"] == "null":
        return None
    return rule


class ContractError(Exception):
    """A contract-level failure carrying the exact HTTP status and error code."""

    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        details: Optional[List[Dict[str, Any]]] = None,
        original_audit_id: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details or []
        self.original_audit_id = original_audit_id

    def to_response(
        self,
        request_id: Optional[str] = None,
        audit_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        error: Dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            error["details"] = self.details
        if request_id:
            error["request_id"] = request_id
        if audit_id:
            error["audit_id"] = audit_id
        if self.original_audit_id:
            error["original_audit_id"] = self.original_audit_id
        return {"contract_version": CONTRACT_VERSION, "error": error}


# --------------------------------------------------------------------------- #
# reference implementation
# --------------------------------------------------------------------------- #
class ReferenceContract:
    """Deterministic implementation of the /v1 contract semantics.

    The instance keeps the idempotency store, so a scenario can be replayed
    (same key, same payload) or conflicted (same key, different payload) exactly
    as a real deployment would.
    """

    def __init__(self) -> None:
        common = load_json(SCHEMAS_DIR / "common.schema.json")
        self.common = common
        self.feature_schemas: Dict[str, Any] = {
            "mock_clinical_v1": load_json(SCHEMAS_DIR / "mock_clinical_feature_schema.v1.json"),
            "mock_clinical_v2": load_json(SCHEMAS_DIR / "mock_clinical_feature_schema.v2.json"),
        }
        registry = load_json(REGISTRY_DIR / "mock_model_registry.v1.json")
        self.models: Dict[str, Any] = {m["model_id"]: m for m in registry["models"]}
        self.explanation_configs: Dict[str, Any] = {
            c["explanation_config_id"]: c for c in registry["explanation_configs"]
        }
        self.default_model_id = next(
            m["model_id"] for m in registry["models"] if m.get("is_default")
        )
        metrics_doc = load_json(REGISTRY_DIR / "mock_monitoring_metrics.v1.json")
        self.metrics: Dict[str, Any] = {m["metric_id"]: m for m in metrics_doc["metrics"]}

        cad_source = common["$defs"]["CadInferenceSource"]
        self.wearable_source_tokens = tuple(
            cad_source["x-rejected-with-422"]["tokens"]
        ) or DEFAULT_WEARABLE_SOURCE_TOKENS

        self._idempotency: Dict[str, Dict[str, Any]] = {}
        self._attempts: Dict[str, int] = {}
        self._keyless_attempts = 0

        #: Observable counters that make the idempotency guarantees testable:
        #: a replayed request must not perform a second inference, and it must
        #: not create a second audit event (Phase 0 §R2-6.1).
        self.inference_count = 0
        self.audit_events: List[str] = []

    # -- idempotency ------------------------------------------------------ #
    def _next_attempt(self, key: Optional[str]) -> int:
        if key is None:
            self._keyless_attempts += 1
            return self._keyless_attempts
        attempt = self._attempts.get(key, 0) + 1
        self._attempts[key] = attempt
        return attempt

    def _audit_id(self, key: Optional[str], body: Dict[str, Any], attempt: int) -> str:
        seed = f"{key or '-'}|{payload_hash(body)}|{attempt}"
        return str(uuid.uuid5(MOCK_AUDIT_NAMESPACE, seed))

    # -- Track A ----------------------------------------------------------- #
    def handle(
        self, endpoint: str, body: Any, headers: Optional[Dict[str, str]] = None
    ) -> Tuple[int, Dict[str, Any]]:
        """Dispatch an endpoint call and convert contract errors into responses."""
        try:
            if endpoint == "POST /v1/predictions/cad-tabular":
                return self.handle_cad_request(body, headers)
            if endpoint == "POST /v1/monitoring/observations":
                return self.handle_monitoring_request(body, headers)
            raise ValueError(f"Unknown endpoint: {endpoint}")
        except ContractError as error:
            request_id = body.get("request_id") if isinstance(body, dict) else None
            return error.status, error.to_response(request_id=request_id)

    def handle_cad_request(
        self, body: Any, headers: Optional[Dict[str, str]] = None
    ) -> Tuple[int, Dict[str, Any]]:
        headers = headers or {}
        key = headers.get("Idempotency-Key")

        if not isinstance(body, dict):
            raise ContractError(
                400,
                "malformed_request",
                "Request body is not a valid prediction request object.",
            )

        declared_version = body.get("contract_version", CONTRACT_VERSION)
        if declared_version != CONTRACT_VERSION:
            raise ContractError(
                400,
                "unsupported_contract_version",
                f"Contract version '{declared_version}' is not implemented by this deployment.",
                details=[
                    {
                        "field": "contract_version",
                        "expected": CONTRACT_VERSION,
                        "received": str(declared_version),
                    }
                ],
            )

        schema_id = body.get("feature_schema_id")
        if not isinstance(schema_id, str) or not schema_id:
            raise ContractError(
                400,
                "malformed_request",
                "Request body is missing 'feature_schema_id'.",
            )
        if schema_id not in self.feature_schemas:
            raise ContractError(
                422,
                "unknown_feature_schema",
                f"Unknown feature schema '{schema_id}'.",
                details=[
                    {
                        "field": "feature_schema_id",
                        "received": schema_id,
                        "expected": "one of: " + ", ".join(sorted(self.feature_schemas)),
                    }
                ],
            )

        context = body.get("context")
        if not isinstance(context, dict):
            raise ContractError(
                400,
                "malformed_request",
                "Request body is missing the 'context' object.",
            )
        features = body.get("features")
        if not isinstance(features, dict):
            raise ContractError(
                400,
                "malformed_request",
                "Request body is missing the 'features' object.",
            )

        # --- idempotency conflict check (before any semantic rule) --------- #
        # The rule is unconditional: the same Idempotency-Key with a different
        # canonical payload is a 409, whatever that payload contains. Checking
        # it here also keeps a rejected request from polluting the store
        # (Phase 0 §R2-6.1).
        digest = payload_hash(body)
        if key is not None and key in self._idempotency:
            record = self._idempotency[key]
            if record["payload_hash"] != digest:
                raise ContractError(
                    409,
                    "idempotency_key_conflict",
                    "This Idempotency-Key was already used with a different request payload.",
                    details=[
                        {
                            "field": "Idempotency-Key",
                            "expected": "an unused key, or the same key with an identical payload",
                            "received": str(key),
                        }
                    ],
                    original_audit_id=record["audit_id"],
                )

        # --- wearable rejection comes first (Phase 0 §F-4, D-039) --------- #
        self._reject_wearable(context, features)

        source = context.get("source")
        if source not in VALID_CAD_SOURCES:
            raise ContractError(
                422,
                "invalid_context_source",
                f"Context source '{source}' is not a valid CAD-inference source.",
                details=[
                    {
                        "field": "context.source",
                        "expected": " | ".join(VALID_CAD_SOURCES),
                        "received": str(source),
                    }
                ],
            )

        model_id = body.get("model_id") or self.default_model_id
        model = self.models.get(model_id)
        if model is None:
            raise ContractError(
                422,
                "unknown_model",
                f"Unknown model '{model_id}'.",
                details=[{"field": "model_id", "received": str(model_id)}],
            )
        if not model.get("artifact_available", True):
            raise ContractError(
                503,
                "model_unavailable",
                "The requested model is unavailable; no prediction was produced.",
                details=[{"field": "model_id", "received": str(model_id)}],
            )
        if model["feature_schema_id"] != schema_id:
            raise ContractError(
                422,
                "schema_model_mismatch",
                (
                    f"Model '{model_id}' is bound to feature schema "
                    f"'{model['feature_schema_id']}', not '{schema_id}'."
                ),
                details=[
                    {
                        "field": "feature_schema_id",
                        "expected": model["feature_schema_id"],
                        "received": schema_id,
                    }
                ],
            )

        schema = self.feature_schemas[schema_id]
        provided, missing_required, missing_optional = self._validate_features(
            features, schema
        )

        # --- replay of an identical payload --------------------------------- #
        # The stored response is returned verbatim; no re-inference happens and
        # no second audit event is created (Phase 0 §R2-6.1).
        if key is not None and key in self._idempotency:
            replayed = copy.deepcopy(self._idempotency[key]["response"])
            replayed["idempotent_replay"] = True
            return 200, replayed

        attempt = self._next_attempt(key)
        audit_id = self._audit_id(key, body, attempt)
        self.audit_events.append(audit_id)
        response = self._build_cad_response(
            body=body,
            model=model,
            schema=schema,
            provided=provided,
            missing_required=missing_required,
            missing_optional=missing_optional,
            audit_id=audit_id,
            request_id=body.get("request_id"),
        )
        if key is not None:
            self._idempotency[key] = {
                "payload_hash": digest,
                "response": copy.deepcopy(response),
                "audit_id": audit_id,
            }
        return 200, response

    def _reject_wearable(
        self, context: Dict[str, Any], features: Dict[str, Any]
    ) -> None:
        source = context.get("source")
        if isinstance(source, str) and source in self.wearable_source_tokens:
            raise ContractError(
                422,
                "wearable_input_not_valid_for_cad_inference",
                (
                    "Wearable or monitoring data cannot be used for CAD inference. "
                    "Use the monitoring ingestion endpoint instead."
                ),
                details=[
                    {
                        "field": "context.source",
                        "expected": " | ".join(VALID_CAD_SOURCES),
                        "received": source,
                    }
                ],
            )
        offending = sorted(
            name
            for name in features
            if name in WEARABLE_FIELD_NAMES or name.startswith("mock_feature_wearable_")
        )
        if offending:
            raise ContractError(
                422,
                "wearable_input_not_valid_for_cad_inference",
                (
                    "Wearable or monitoring data cannot be used for CAD inference. "
                    "Use the monitoring ingestion endpoint instead."
                ),
                details=[
                    {
                        "field": f"features.{name}",
                        "feature_id": name,
                        "expected": "a clinical feature declared by the feature schema",
                        "received": "wearable/monitoring field",
                    }
                    for name in offending
                ],
            )

    def _validate_features(
        self, features: Dict[str, Any], schema: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], List[str], List[str]]:
        excluded = set(schema.get("x-excluded-features", {})) | set(
            schema.get("x-pending-review-features", {})
        )
        declared = schema.get("properties", {})

        provided: Dict[str, Any] = {}
        for name, payload in features.items():
            if name in excluded:
                raise ContractError(
                    422,
                    "feature_not_in_schema",
                    f"Feature '{name}' is not part of feature schema '{schema['title']}'.",
                    details=[
                        {
                            "field": f"features.{name}",
                            "feature_id": name,
                            "expected": "a feature declared by the feature schema",
                            "received": name,
                        }
                    ],
                )
            if name not in declared:
                raise ContractError(
                    422,
                    "unknown_feature",
                    f"Unknown feature '{name}'.",
                    details=[{"field": f"features.{name}", "feature_id": name}],
                )
            if not isinstance(payload, dict):
                raise ContractError(
                    400,
                    "malformed_request",
                    f"Feature '{name}' must be an object with 'value' and 'unit'.",
                    details=[{"field": f"features.{name}"}],
                )
            expected_unit = self._expected_unit(declared[name])
            if "unit" not in payload:
                raise ContractError(
                    422,
                    "unit_mismatch",
                    f"Feature '{name}' does not declare a unit.",
                    details=[
                        {
                            "field": f"features.{name}.unit",
                            "feature_id": name,
                            "expected": expected_unit,
                            "received": "<missing>",
                        }
                    ],
                )
            if payload["unit"] != expected_unit:
                raise ContractError(
                    422,
                    "unit_mismatch",
                    f"Unit of feature '{name}' does not match the feature schema.",
                    details=[
                        {
                            "field": f"features.{name}.unit",
                            "feature_id": name,
                            "expected": expected_unit,
                            "received": str(payload["unit"]),
                        }
                    ],
                )
            value = payload.get("value")
            if value is None:
                continue  # null means "not provided"
            self._validate_value(name, value, declared[name])
            provided[name] = payload

        missing_required = [
            name for name in schema.get("required", []) if name not in provided
        ]
        if missing_required:
            raise ContractError(
                422,
                "missing_required_feature",
                "One or more required features are missing; no prediction was produced.",
                details=[
                    {
                        "field": f"features.{name}",
                        "feature_id": name,
                        "expected": "a value declared by the feature schema",
                        "received": "<missing>",
                    }
                    for name in missing_required
                ],
            )

        missing_optional = sorted(
            name
            for name in declared
            if name not in provided and name not in schema.get("required", [])
        )
        return provided, missing_required, missing_optional

    @staticmethod
    def _expected_unit(feature_definition: Dict[str, Any]) -> str:
        for part in feature_definition.get("allOf", []):
            properties = part.get("properties", {})
            unit = properties.get("unit")
            if unit and "const" in unit:
                return unit["const"]
        return ""

    @staticmethod
    def _validate_value(name: str, value: Any, definition: Dict[str, Any]) -> None:
        expected_type = None
        minimum = None
        maximum = None
        for part in definition.get("allOf", []):
            properties = part.get("properties", {})
            if "value" not in properties:
                continue  # e.g. the generic FeatureValue reference member
            value_schema = properties["value"]
            typed_rule = typed_value_alternative(value_schema)
            if typed_rule is None:
                # The oracle does not understand this value rule. Fail loudly
                # instead of silently accepting a value it cannot check.
                raise ValueError(
                    f"Feature '{name}' declares a value rule this oracle does not "
                    f"understand: {canonical_json(value_schema)}"
                )
            if "type" in typed_rule:
                expected_type = typed_rule["type"]
            if "minimum" in typed_rule:
                minimum = typed_rule["minimum"]
            if "maximum" in typed_rule:
                maximum = typed_rule["maximum"]
        if expected_type is None:
            raise ValueError(
                f"Feature '{name}' declares no typed value rule this oracle can check."
            )
        if expected_type == "integer" and not isinstance(value, int):
            raise ContractError(
                400,
                "malformed_request",
                f"Feature '{name}' must be an integer.",
                details=[{"field": f"features.{name}.value"}],
            )
        if expected_type == "number" and not isinstance(value, (int, float)):
            raise ContractError(
                400,
                "malformed_request",
                f"Feature '{name}' must be a number.",
                details=[{"field": f"features.{name}.value"}],
            )
        if expected_type == "string" and not isinstance(value, str):
            raise ContractError(
                400,
                "malformed_request",
                f"Feature '{name}' must be a string.",
                details=[{"field": f"features.{name}.value"}],
            )
        if expected_type == "boolean" and not isinstance(value, bool):
            raise ContractError(
                400,
                "malformed_request",
                f"Feature '{name}' must be a boolean.",
                details=[{"field": f"features.{name}.value"}],
            )
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if minimum is not None and value < minimum:
                raise ContractError(
                    422,
                    "value_out_of_range",
                    f"Value of feature '{name}' is outside the range declared by the feature schema.",
                    details=[
                        {
                            "field": f"features.{name}.value",
                            "feature_id": name,
                            "expected": f">= {minimum}",
                            "received": str(value),
                        }
                    ],
                )
            if maximum is not None and value > maximum:
                raise ContractError(
                    422,
                    "value_out_of_range",
                    f"Value of feature '{name}' is outside the range declared by the feature schema.",
                    details=[
                        {
                            "field": f"features.{name}.value",
                            "feature_id": name,
                            "expected": f"<= {maximum}",
                            "received": str(value),
                        }
                    ],
                )

    def _build_cad_response(
        self,
        body: Dict[str, Any],
        model: Dict[str, Any],
        schema: Dict[str, Any],
        provided: Dict[str, Any],
        missing_required: List[str],
        missing_optional: List[str],
        audit_id: str,
        request_id: Optional[str],
    ) -> Dict[str, Any]:
        # A mock "inference" happens here and only here. The counter makes it
        # observable that a replayed request performs no second inference.
        self.inference_count += 1
        base_value = float(model["base_value"])
        method = model["explanation_method"]

        contributions: List[Dict[str, Any]] = []
        for name in sorted(provided):
            payload = provided[name]
            offset = deterministic_offset(name, payload.get("value"))
            contributions.append(
                {
                    "feature": name,
                    "value": payload.get("value"),
                    "unit": payload.get("unit"),
                    "shap": offset,
                }
            )
        # Rank by magnitude (the order a UI would show); ties break on the
        # feature id so the order is fully deterministic.
        contributions.sort(key=lambda c: (-abs(float(c["shap"])), c["feature"]))
        for rank, contribution in enumerate(contributions, start=1):
            contribution["rank"] = rank

        computed_sum = base_value + sum(c["shap"] for c in contributions)
        if method == "lime":
            # A local surrogate does not decompose the margin exactly; the
            # deterministic +0.03 intercept mismatch is the documented reason
            # why the additive sum-check does not apply to LIME.
            margin = round(computed_sum + 0.03, 6)
            applicable = False
        else:
            margin = round(computed_sum, 6)
            applicable = True
        passed = abs(computed_sum - margin) <= 1e-6

        calibration = model.get("calibration")
        if calibration:
            score_value = round(
                1.0 / (1.0 + math.exp(-(calibration["slope"] * margin + calibration["intercept"]))),
                6,
            )
            score: Dict[str, Any] = {
                "value": score_value,
                "type": "calibrated_probability",
                "scale": "probability",
                "raw_margin": margin,
                "calibration": {
                    "method": calibration["method"],
                    "calibration_id": calibration["calibration_id"],
                    "cohort_context": calibration["cohort_context"],
                },
                "rendering": {
                    "display_unit": "decimal",
                    "percent_sign_allowed": False,
                    "label": "Benchmark-cohort model score (mock, synthetic). Not a personal risk.",
                    "absolute_population_probability_claim": False,
                },
            }
            margin_source = "score.raw_margin"
        else:
            score = {
                "value": margin,
                "type": "uncalibrated_score",
                "scale": "log_odds_margin",
                "rendering": {
                    "display_unit": "unitless",
                    "percent_sign_allowed": False,
                    "label": "Relative model output (uncalibrated). Not a probability.",
                    "absolute_population_probability_claim": False,
                },
            }
            margin_source = "score.value"

        explanation: Dict[str, Any] = {
            "method": method,
            "scale": model["explanation_scale"],
            "base_value": base_value,
            "contributions": contributions,
            "sum_check": {
                "applicable": applicable,
                "margin": margin,
                "computed_sum": round(computed_sum, 6),
                "tolerance": 1e-6,
                "passed": passed,
                "margin_source": margin_source,
            },
            "synthetic": True,
            "note": (
                "SYNTHETIC FIXTURE: the contribution values are hand-authored deterministic "
                "offsets, NOT computed by SHAP or LIME from any trained model — no model exists. "
                "Contributions are on the log-odds (margin) scale: base_value + sum(shap) equals "
                "the model margin. They are NOT changes in a calibrated probability and must "
                "never be displayed as percentage points of disease probability. They are "
                "associational attributions of the model output, NOT causal effects: no "
                "treatment, intervention or recommendation may be derived from them "
                "(Phase 0 §R2-5.7, §R2-6.5, §2.1)."
            ),
        }
        if method == "lime":
            explanation["local_fidelity_r2"] = 0.62
            explanation["note"] = (
                "SYNTHETIC FIXTURE: local surrogate explanation (LIME) with a fixed seed and "
                "sampling count pinned in explanation_config_id. The values are hand-authored "
                "deterministic offsets, NOT computed by LIME from any trained model — no model "
                "exists. Contributions are on the log-odds (margin) scale. They are NOT changes "
                "in a calibrated probability and must never be displayed as percentage points of "
                "disease probability. They are associational attributions of the model output, "
                "NOT causal effects: no treatment, intervention or recommendation may be derived "
                "from them. A local surrogate is not an exact additive decomposition "
                "of the margin, so the margin sum-check is reported as not applicable "
                "(Phase 0 §R2-5.7)."
            )

        warnings = [f"imputed_feature:{name}" for name in missing_optional]

        return {
            "contract_version": CONTRACT_VERSION,
            "data_class": "MOCK_SYNTHETIC",
            "track": "A",
            "request_id": request_id,
            "audit_id": audit_id,
            "idempotent_replay": False,
            "generated_at": MOCK_CLOCK,
            "model_id": model["model_id"],
            "preprocessing_id": model["preprocessing_id"],
            "calibration_id": model["calibration_id"],
            "feature_schema_id": model["feature_schema_id"],
            "explanation_config_id": model["explanation_config_id"],
            "target": {
                "id": "T1_angiographic_cad_presence",
                "definition": (
                    "PROVISIONAL and NOT APPROVED (D-006 / P-1 open): cross-sectional presence "
                    "of angiographically significant CAD in a benchmark cohort. Not a future-event "
                    "risk, not a severity score, not a per-patient probability."
                ),
                "time_horizon": "none_cross_sectional",
                "status": "provisional_pending_approval",
                "approval_note": (
                    "The scientific target is still pending research-lead and supervisor approval "
                    "(P-1). The contract carries the name of the target so that no consumer can "
                    "invent a different one."
                ),
            },
            "score": score,
            "validation_status": model["validation_status"],
            "model_performance_ref": model["model_performance_ref"],
            "explanation": explanation,
            "missing_features": missing_optional,
            "warnings": warnings,
            "provenance": {
                "training_datasets": [],
                "code_commit": "mock-fixture-pack-v1",
                "artifact_hashes": {
                    "model": model["artifact_sha256"],
                    "preprocessing": model["preprocessing_sha256"],
                    **(
                        {"calibration": model["calibration_sha256"]}
                        if model.get("calibration_sha256")
                        else {}
                    ),
                },
                "dataset_access_status": "not_applicable_no_dataset_used",
            },
            "review_state": "pending_review",
            "disclaimer": self.common["$defs"]["MockDisclaimerTrackA"]["const"],
        }

    # -- Track B ----------------------------------------------------------- #
    def handle_monitoring_request(
        self, body: Any, headers: Optional[Dict[str, str]] = None
    ) -> Tuple[int, Dict[str, Any]]:
        headers = headers or {}
        key = headers.get("Idempotency-Key")

        if not isinstance(body, dict):
            raise ContractError(
                400,
                "malformed_request",
                "Request body is not a valid monitoring observation object.",
            )
        declared_version = body.get("contract_version", CONTRACT_VERSION)
        if declared_version != CONTRACT_VERSION:
            raise ContractError(
                400,
                "unsupported_contract_version",
                f"Contract version '{declared_version}' is not implemented by this deployment.",
            )

        observation = body.get("observation")
        if not isinstance(observation, dict):
            raise ContractError(
                400,
                "malformed_request",
                "Request body is missing the 'observation' object.",
            )

        # --- idempotency conflict check (before any semantic rule) --------- #
        # Same rule as Track A: the conflict is unconditional, so it is
        # detected before the observation is validated (Phase 0 §R2-6.1).
        digest = payload_hash(body)
        if key is not None and key in self._idempotency:
            record = self._idempotency[key]
            if record["payload_hash"] != digest:
                raise ContractError(
                    409,
                    "idempotency_key_conflict",
                    "This Idempotency-Key was already used with a different request payload.",
                    original_audit_id=record["audit_id"],
                )
            replayed = copy.deepcopy(record["response"])
            replayed["idempotent_replay"] = True
            return 201, replayed

        if not observation.get("consent_id"):
            raise ContractError(
                422,
                "consent_required",
                "A monitoring observation must reference a consent record.",
                details=[{"field": "observation.consent_id"}],
            )

        metrics = observation.get("metrics")
        if not isinstance(metrics, list) or not metrics:
            raise ContractError(
                400,
                "malformed_request",
                "The observation must carry at least one metric.",
            )

        accepted_metrics: List[Dict[str, Any]] = []
        for metric in metrics:
            if not isinstance(metric, dict):
                raise ContractError(
                    400, "malformed_request", "Each metric must be an object."
                )
            metric_id = metric.get("metric_id")
            catalogue = self.metrics.get(metric_id)
            if catalogue is None:
                raise ContractError(
                    422,
                    "unknown_metric",
                    f"Unknown monitoring metric '{metric_id}'.",
                    details=[{"field": "observation.metrics.metric_id", "metric_id": str(metric_id)}],
                )
            if metric.get("unit") != catalogue["unit"]:
                raise ContractError(
                    422,
                    "unit_mismatch",
                    f"Unit of metric '{metric_id}' does not match the metric catalogue.",
                    details=[
                        {
                            "field": f"observation.metrics.{metric_id}.unit",
                            "metric_id": metric_id,
                            "expected": catalogue["unit"],
                            "received": str(metric.get("unit")),
                        }
                    ],
                )
            value = metric.get("value")
            if value is None:
                continue
            minimum = catalogue.get("minimum")
            maximum = catalogue.get("maximum")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                if (minimum is not None and value < minimum) or (
                    maximum is not None and value > maximum
                ):
                    raise ContractError(
                        422,
                        "value_out_of_range",
                        f"Value of metric '{metric_id}' is outside the catalogue range.",
                        details=[
                            {
                                "field": f"observation.metrics.{metric_id}.value",
                                "metric_id": metric_id,
                                "expected": f"{minimum}..{maximum}",
                                "received": str(value),
                            }
                        ],
                    )
            accepted_metrics.append(metric)

        attempt = self._next_attempt(key)
        observation_id = str(
            uuid.uuid5(MOCK_OBSERVATION_NAMESPACE, f"{key or '-'}|{digest}|{attempt}")
        )
        self.audit_events.append(observation_id)
        response = {
            "contract_version": CONTRACT_VERSION,
            "data_class": "MOCK_SYNTHETIC",
            "track": "B",
            "request_id": body.get("request_id"),
            "observation_id": observation_id,
            "idempotent_replay": False,
            "accepted": True,
            "received_at": MOCK_CLOCK,
            "recorded_metric_count": len(accepted_metrics),
            "validation": {"status": "accepted", "issues": []},
            "disclaimer": self.common["$defs"]["MockDisclaimerTrackB"]["const"],
        }
        if key is not None:
            self._idempotency[key] = {
                "payload_hash": digest,
                "response": copy.deepcopy(response),
                "audit_id": observation_id,
            }
        return 201, response
