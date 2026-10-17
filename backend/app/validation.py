"""Contract-coded semantic checks followed by the shared structural validators.

No clinical thresholds live here. Every allowed unit/range/required feature
comes from shared/contracts; all quantities are placeholder MOCK_ONLY slots.
"""

from __future__ import annotations

import copy
from typing import Any

from jsonschema import Draft202012Validator

from .contracts import CAD_PATH, MONITORING_PATH, ContractFiles, ContractViolation

VALID_CAD_SOURCES = ("benchmark_import", "clinician_entry")
# Approved reference implementation's wearable-field denylist (Phase 0 F-4).
WEARABLE_FIELDS = frozenset(
    {
        "heart_rate", "heart_rate_bpm", "hr", "hrv", "steps", "step_count",
        "spo2", "spo2_percent", "sleep_minutes", "wearable", "wearable_ecg",
        "ecg_waveform", "device_timestamp", "pedometer",
    }
)


def validate_version(contracts: ContractFiles, path: str, body: dict[str, Any]) -> None:
    version = body.get("contract_version", contracts.version)
    if version != contracts.version:
        raise ContractViolation(
            400,
            "unsupported_contract_version",
            f"Contract version '{version}' is not implemented by this deployment.",
            details=[{
                "field": "contract_version", "expected": contracts.version, "received": str(version)
            }] if path == CAD_PATH else None,
        )


def reject_wearable(contracts: ContractFiles, body: dict[str, Any]) -> None:
    source = body["context"].get("source")
    message = (
        "Wearable or monitoring data cannot be used for CAD inference. "
        "Use the monitoring ingestion endpoint instead."
    )
    if isinstance(source, str) and source in contracts.wearable_sources:
        raise ContractViolation(
            422, "wearable_input_not_valid_for_cad_inference", message,
            details=[{
                "field": "context.source", "expected": " | ".join(VALID_CAD_SOURCES),
                "received": source,
            }],
        )
    # Include actual Track-B catalogue ids, not just generic measurement names.
    # Scan keys throughout the body so nesting a wearable field cannot bypass
    # the safety-specific rejection and turn it into a generic schema failure.
    pending = [("", body)]
    offending = []
    while pending:
        prefix, node = pending.pop()
        if isinstance(node, dict):
            for name, value in node.items():
                field = f"{prefix}.{name}" if prefix else name
                if (name in WEARABLE_FIELDS or name in contracts.metrics
                        or name.startswith("mock_feature_wearable_")
                        or (not prefix and name in {"observation", "metrics"})):
                    offending.append((field, name))
                pending.append((field, value))
        elif isinstance(node, list):
            pending.extend((f"{prefix}.{i}", value) for i, value in enumerate(node))
    if offending:
        raise ContractViolation(
            422, "wearable_input_not_valid_for_cad_inference", message,
            details=[{
                "field": field, "feature_id": name,
                "expected": "a clinical feature declared by the feature schema",
                "received": "wearable/monitoring field",
            } for field, name in sorted(offending)],
        )


def typed_value_rule(rule: dict[str, Any]) -> dict[str, Any]:
    """Return the non-null typed alternative of a feature value rule.

    ADR-001 Option A represents an optional feature value as
    ``anyOf: [{"type": "null"}, <original typed/ranged rule>]``. The runtime
    has always skipped explicit nulls before type checking, so it only needs
    the typed alternative for non-null values. Rules that already declare a
    direct ``type`` (the current schemas, and every required slot) are
    returned unchanged. An unsupported shape is also returned unchanged so
    that this adapter cannot silently broaden validation.
    """
    if "type" in rule:
        return rule
    alternatives = rule.get("anyOf")
    if not isinstance(alternatives, list):
        return rule
    typed = [
        alternative
        for alternative in alternatives
        if isinstance(alternative, dict) and alternative.get("type") != "null"
    ]
    if len(typed) == 1 and "type" in typed[0]:
        return typed[0]
    return rule


def feature_rules(definition: dict[str, Any]) -> dict[str, Any]:
    rules: dict[str, Any] = {}
    for part in definition["allOf"]:
        rules.update(part.get("properties", {}))
    value_rule = rules.get("value")
    if isinstance(value_rule, dict):
        rules["value"] = typed_value_rule(value_rule)
    return rules


def validate_features(
    contracts: ContractFiles, schema: dict[str, Any], features: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    declared = schema["properties"]
    excluded = set(schema["x-excluded-features"]) | set(schema["x-pending-review-features"])
    provided = {}
    for name, payload in features.items():
        field = f"features.{name}"
        if name in excluded:
            raise ContractViolation(
                422, "feature_not_in_schema",
                f"Feature '{name}' is not part of feature schema '{schema['title']}'.",
                details=[{
                    "field": field, "feature_id": name,
                    "expected": "a feature declared by the feature schema", "received": name,
                }],
            )
        if name not in declared:
            raise ContractViolation(
                422, "unknown_feature", f"Unknown feature '{name}'.",
                details=[{"field": field, "feature_id": name}],
            )
        if not isinstance(payload, dict):
            raise ContractViolation(
                400, "malformed_request", f"Feature '{name}' must be an object with 'value' and 'unit'.",
                details=[{"field": field}],
            )
        rules = feature_rules(declared[name])
        expected_unit = rules["unit"]["const"]
        if "unit" not in payload or payload["unit"] != expected_unit:
            message = (
                f"Feature '{name}' does not declare a unit." if "unit" not in payload
                else f"Unit of feature '{name}' does not match the feature schema."
            )
            raise ContractViolation(
                422, "unit_mismatch", message,
                details=[{
                    "field": field + ".unit", "feature_id": name, "expected": expected_unit,
                    "received": str(payload.get("unit", "<missing>")),
                }],
            )
        value = payload.get("value")
        if value is None:
            continue  # Missing/null required values are handled below, never imputed.
        value_rule = rules["value"]
        kind = value_rule["type"]
        if not Draft202012Validator.TYPE_CHECKER.is_type(value, kind):
            article = "an" if kind == "integer" else "a"
            raise ContractViolation(
                400, "malformed_request", f"Feature '{name}' must be {article} {kind}.",
                details=[{"field": field + ".value"}],
            )
        if kind in {"integer", "number"}:
            for keyword, operator in (("minimum", ">="), ("maximum", "<=")):
                limit = value_rule.get(keyword)
                outside = limit is not None and (
                    value < limit if keyword == "minimum" else value > limit
                )
                if outside:
                    raise ContractViolation(
                        422, "value_out_of_range",
                        f"Value of feature '{name}' is outside the range declared by the feature schema.",
                        details=[{
                            "field": field + ".value", "feature_id": name,
                            "expected": f"{operator} {limit}", "received": str(value),
                        }],
                    )
        provided[name] = payload

    missing_required = [name for name in schema["required"] if name not in provided]
    if missing_required:
        raise ContractViolation(
            422, "missing_required_feature",
            "One or more required features are missing; no prediction was produced.",
            details=[{
                "field": f"features.{name}", "feature_id": name,
                "expected": "a value declared by the feature schema", "received": "<missing>",
            } for name in missing_required],
        )
    missing_optional = sorted(set(declared) - set(provided) - set(schema["required"]))
    # The prose/null semantics and schema allOf constraints disagree. Validate
    # null wrappers too (including required value/unit and extra fields), then
    # omit only explicit optional nulls from a validation COPY. The original
    # request remains untouched, including for canonical-payload hashing.
    wrapper_validator = Draft202012Validator(schema["$defs"]["FeatureValue"])
    for name, payload in features.items():
        if name not in provided:
            contracts.validate_structure(wrapper_validator, payload)
    return provided, missing_optional


def validate_cad(
    contracts: ContractFiles, body: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    validate_version(contracts, CAD_PATH, body)
    schema_id = body.get("feature_schema_id")
    if not isinstance(schema_id, str) or not schema_id:
        raise ContractViolation(400, "malformed_request", "Request body is missing 'feature_schema_id'.")
    if schema_id not in contracts.feature_schemas:
        raise ContractViolation(
            422, "unknown_feature_schema", f"Unknown feature schema '{schema_id}'.",
            details=[{
                "field": "feature_schema_id", "received": schema_id,
                "expected": "one of: " + ", ".join(sorted(contracts.feature_schemas)),
            }],
        )
    for name in ("context", "features"):
        if not isinstance(body.get(name), dict):
            raise ContractViolation(400, "malformed_request", f"Request body is missing the '{name}' object.")
    reject_wearable(contracts, body)
    source = body["context"].get("source")
    if source not in VALID_CAD_SOURCES:
        raise ContractViolation(
            422, "invalid_context_source", f"Context source '{source}' is not a valid CAD-inference source.",
            details=[{
                "field": "context.source", "expected": " | ".join(VALID_CAD_SOURCES),
                "received": str(source),
            }],
        )
    model_id = body.get("model_id", contracts.default_model_id)
    if not isinstance(model_id, str):
        raise ContractViolation(400, "malformed_request", "model_id must be a string.")
    model = contracts.models.get(model_id)
    if model is None:
        raise ContractViolation(
            422, "unknown_model", f"Unknown model '{model_id}'.",
            details=[{"field": "model_id", "received": model_id}],
        )
    if not model.get("artifact_available", True) or model["explanation_method"] != "tree_shap":
        # LIME remains a future integration. Never serve F-11c's invented R².
        raise ContractViolation(
            503, "model_unavailable", "The requested model is unavailable; no prediction was produced.",
            details=[{"field": "model_id", "received": model_id}],
        )
    if model["feature_schema_id"] != schema_id:
        raise ContractViolation(
            422, "schema_model_mismatch",
            f"Model '{model_id}' is bound to feature schema '{model['feature_schema_id']}', not '{schema_id}'.",
            details=[{
                "field": "feature_schema_id", "expected": model["feature_schema_id"], "received": schema_id,
            }],
        )
    schema = contracts.feature_schemas[schema_id]
    provided, missing_optional = validate_features(contracts, schema, body["features"])
    normalized = copy.deepcopy(body)
    normalized["features"] = provided
    contracts.validate_structure(contracts.requests[CAD_PATH], normalized)
    return model, provided, missing_optional


def validate_monitoring(contracts: ContractFiles, body: dict[str, Any]) -> int:
    validate_version(contracts, MONITORING_PATH, body)
    observation = body.get("observation")
    if not isinstance(observation, dict):
        raise ContractViolation(400, "malformed_request", "Request body is missing the 'observation' object.")
    if not observation.get("consent_id"):
        raise ContractViolation(
            422, "consent_required", "A monitoring observation must reference a consent record.",
            details=[{"field": "observation.consent_id"}],
        )
    metrics = observation.get("metrics")
    if not isinstance(metrics, list) or not metrics:
        raise ContractViolation(400, "malformed_request", "The observation must carry at least one metric.")
    recorded_count = 0
    for metric in metrics:
        if not isinstance(metric, dict):
            raise ContractViolation(400, "malformed_request", "Each metric must be an object.")
        metric_id = metric.get("metric_id")
        catalogue = contracts.metrics.get(metric_id) if isinstance(metric_id, str) else None
        if catalogue is None:
            raise ContractViolation(
                422, "unknown_metric", f"Unknown monitoring metric '{metric_id}'.",
                details=[{"field": "observation.metrics.metric_id", "metric_id": str(metric_id)}],
            )
        field = f"observation.metrics.{metric_id}"
        if metric.get("unit") != catalogue["unit"]:
            raise ContractViolation(
                422, "unit_mismatch", f"Unit of metric '{metric_id}' does not match the metric catalogue.",
                details=[{
                    "field": field + ".unit", "metric_id": metric_id, "expected": catalogue["unit"],
                    "received": str(metric.get("unit")),
                }],
            )
        value = metric.get("value")
        if value is None:
            continue
        # Preserve the merged wire schema + reference behavior. The catalogue's
        # value_type disagrees with the permitted string/boolean wire values;
        # tightening this requires review (backend/CONTRACT_NOTES.md, B-01).
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            minimum, maximum = catalogue["minimum"], catalogue["maximum"]
            if value < minimum or value > maximum:
                raise ContractViolation(
                    422, "value_out_of_range", f"Value of metric '{metric_id}' is outside the catalogue range.",
                    details=[{
                        "field": field + ".value", "metric_id": metric_id,
                        "expected": f"{minimum}..{maximum}", "received": str(value),
                    }],
                )
        recorded_count += 1
    contracts.validate_structure(contracts.requests[MONITORING_PATH], body)
    return recorded_count
