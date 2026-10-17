"""Load the merged wire definitions locally; no second Pydantic API schema.

All $refs are resolved from the checked-in registry. There is no network
retriever, model loader, dataset reader or import of the contract-test oracle.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

CONTRACTS_DIR = Path(__file__).resolve().parents[2] / "shared" / "contracts"
CAD_PATH = "/v1/predictions/cad-tabular"
MONITORING_PATH = "/v1/monitoring/observations"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


class ContractViolation(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        *,
        details: list[dict[str, str]] | None = None,
        original_audit_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details or []
        self.original_audit_id = original_audit_id


class ContractFiles:
    """App-local validators and approved synthetic response wording."""

    def __init__(self) -> None:
        self.openapi = yaml.safe_load(
            (CONTRACTS_DIR / "openapi.yaml").read_text(encoding="utf-8")
        )
        self.schemas = {
            path.name: load_json(path)
            for path in sorted((CONTRACTS_DIR / "schemas").glob("*.json"))
        }
        resources = []
        for name, document in self.schemas.items():
            resource = Resource.from_contents(document, default_specification=DRAFT202012)
            resources.extend(
                [
                    (document["$id"], resource),
                    ((CONTRACTS_DIR / "schemas" / name).as_uri(), resource),
                ]
            )
        self.registry = Registry().with_resources(resources)
        self.validators = {
            name: Draft202012Validator(
                document,
                registry=self.registry,
                format_checker=Draft202012Validator.FORMAT_CHECKER,
            )
            for name, document in self.schemas.items()
        }
        self.common = self.schemas["common.schema.json"]["$defs"]
        self.version = self.common["ContractVersion"]["const"]
        self.requests = {}
        self.responses = {}
        self.success_status = {}
        self.retention_seconds = {}
        for path, item in self.openapi["paths"].items():
            operation = item["post"]
            request_ref = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
            status = next(s for s in operation["responses"] if str(s).startswith("2"))
            response_ref = operation["responses"][status]["content"]["application/json"]["schema"]["$ref"]
            self.requests[path] = self.validators[Path(request_ref).name]
            self.responses[path] = self.validators[Path(response_ref).name]
            self.success_status[path] = int(status)
            self.retention_seconds[path] = operation["x-idempotency"]["retention_hours"] * 3600

        # Schema identifiers/bindings come from the approved conditional refs,
        # not a separate backend dictionary of feature types, units or ranges.
        request_schema = self.requests[CAD_PATH].schema
        self.feature_schemas = {
            condition["if"]["properties"]["feature_schema_id"]["const"]: self.schemas[
                Path(condition["then"]["properties"]["features"]["$ref"]).name
            ]
            for condition in request_schema["allOf"]
        }
        models = load_json(CONTRACTS_DIR / "registry" / "mock_model_registry.v1.json")
        metrics = load_json(CONTRACTS_DIR / "registry" / "mock_monitoring_metrics.v1.json")
        if models["status"] != "MOCK_ONLY" or metrics["status"] != "MOCK_ONLY":
            raise RuntimeError("This backend only supports the MOCK_ONLY registries.")
        self.models = {entry["model_id"]: entry for entry in models["models"]}
        self.default_model_id = next(
            entry["model_id"] for entry in models["models"] if entry.get("is_default")
        )
        self.metrics = {entry["metric_id"]: entry for entry in metrics["metrics"]}
        self.wearable_sources = self.common["CadInferenceSource"]["x-rejected-with-422"]["tokens"]

        # Reuse approved target, disclaimer, explanation note, rendering and
        # provenance wording verbatim. These are templates, not a lookup table
        # of requests: scores/contributions are calculated for each valid input.
        self.prediction_template = self.fixture_body("F-01-cad-tabular-valid-mock-clinical-v1.json")
        self.calibrated_template = self.fixture_body("F-11b-calibrated-score-rendering.json")
        self.monitoring_template = self.fixture_body("F-04-monitoring-observation-valid.json")
        self.responses[CAD_PATH].validate(self.prediction_template)
        self.responses[CAD_PATH].validate(self.calibrated_template)
        self.responses[MONITORING_PATH].validate(self.monitoring_template)

    @staticmethod
    def fixture_body(filename: str) -> dict[str, Any]:
        return load_json(CONTRACTS_DIR / "fixtures" / filename)["steps"][0]["expected"]["body"]

    def component(self, name: str) -> Draft202012Validator:
        return self.validators["common.schema.json"].evolve(schema=self.common[name])

    @staticmethod
    def validate_structure(validator: Draft202012Validator, body: Any) -> None:
        error = next(validator.iter_errors(body), None)
        if error is not None:
            raise ContractViolation(
                400,
                "malformed_request",
                "Request body violates the structural contract.",
                details=[{"field": ".".join(map(str, error.absolute_path)) or "body"}],
            )

    def error_body(
        self,
        error: ContractViolation,
        body: Any = None,
        *,
        audit_id: str | None = None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {"code": error.code, "message": error.message}
        if error.details:
            result["details"] = error.details
        request_id = body.get("request_id") if isinstance(body, dict) else None
        # Never echo an invalid correlation id into a schema-invalid error.
        if self.component("Uuid").is_valid(request_id):
            result["request_id"] = request_id
        if audit_id is not None:
            result["audit_id"] = audit_id
        if error.original_audit_id is not None:
            result["original_audit_id"] = error.original_audit_id
        response = {"contract_version": self.version, "error": result}
        self.component("ErrorResponse").validate(response)
        return response

    def bundled_openapi(self) -> dict[str, Any]:
        """Inline the exact shared schemas for an offline /openapi.json.

        Only ref locations/base ids are rebased; no property rule is changed.
        Swagger/ReDoc CDN pages are deliberately not required by this service.
        """
        def rebase(node: Any, filename: str | None = None) -> Any:
            if isinstance(node, list):
                return [rebase(item, filename) for item in node]
            if not isinstance(node, dict):
                return node
            result = {}
            for key, value in node.items():
                if key == "$id":
                    continue  # References below become document-local pointers.
                if key == "$ref":
                    target, _, pointer = value.partition("#")
                    if target or filename:
                        name = Path(target).name if target else filename
                        value = f"#/components/schemas/{name}{pointer}"
                    result[key] = value
                else:
                    result[key] = rebase(value, filename)
            return result

        document = rebase(copy.deepcopy(self.openapi))
        document["components"]["schemas"] = {
            name: rebase(schema, name) for name, schema in self.schemas.items()
        }
        document["info"]["description"] += (
            "\nM1a.2 implementation: single-process MOCK_SYNTHETIC backend. "
            "In-memory state resets on restart. LIME is a future capability; "
            "the LIME-only mock binding returns 503 model_unavailable. "
            "Historical M1a.1 proposal metadata is retained from the merged source."
        )
        return document
