"""Structural and semantic tests for the OpenAPI document itself.

These tests assert that the proposed /v1 contract is a valid OpenAPI 3.1
document, that it exposes exactly the two M1a.1 endpoints, that every local
``$ref`` resolves, and that the error/idempotency surface is explicit.

They do not assert anything about clinical behaviour: no model, no dataset and
no clinical feature dictionary exists at this milestone.
"""

from __future__ import annotations

import json
import re

from openapi_spec_validator import validate as validate_openapi
from openapi_spec_validator.readers import read_from_filename

from conftest import CONTRACTS_DIR

EXPECTED_PATHS = {
    "/v1/predictions/cad-tabular",
    "/v1/monitoring/observations",
}

LOCAL_REF = re.compile(r"^(?P<file>[^#]+)(#(?P<pointer>.*))?$")


def _resolve_pointer(document, pointer: str):
    target = document
    for part in pointer.split("/"):
        if not part:
            continue
        part = part.replace("~1", "/").replace("~0", "~")
        target = target[part]
    return target


def _collect_refs(node, refs: list):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref" and isinstance(value, str):
                refs.append(value)
            else:
                _collect_refs(value, refs)
    elif isinstance(node, list):
        for item in node:
            _collect_refs(item, refs)
    return refs


# --------------------------------------------------------------------------- #
# document validity
# --------------------------------------------------------------------------- #
def test_openapi_document_is_valid_openapi_31():
    """The contract must be a structurally valid OpenAPI 3.1 document."""
    spec, base_uri = read_from_filename(str(CONTRACTS_DIR / "openapi.yaml"))
    validate_openapi(spec, base_uri=base_uri)


def test_openapi_declares_exactly_the_two_m1a1_paths(openapi_document):
    """M1a.1 ships two endpoints; anything else would be scope creep."""
    assert set(openapi_document["paths"]) == EXPECTED_PATHS


def test_openapi_declares_no_unversioned_path(openapi_document):
    for path in openapi_document["paths"]:
        assert path.startswith("/v1/"), f"{path} is not under the /v1 prefix"


def test_every_local_ref_resolves(openapi_document):
    """Every relative $ref must point at a file and pointer that exist."""
    refs = _collect_refs(openapi_document, [])
    assert refs, "the document declares no $ref at all"
    for ref in refs:
        if ref.startswith("#"):
            _resolve_pointer(openapi_document, ref[1:])
            continue
        match = LOCAL_REF.match(ref)
        assert match, f"unsupported $ref form: {ref}"
        target = (CONTRACTS_DIR / match.group("file")).resolve()
        assert target.is_file(), f"missing schema file for $ref: {ref}"
        document = json.loads(target.read_text(encoding="utf-8"))
        pointer = match.group("pointer")
        if pointer:
            _resolve_pointer(document, pointer)


def test_openapi_reuses_the_shared_error_envelope(openapi_document):
    """Every documented error response must use the common error envelope."""
    components = openapi_document["components"]["responses"]
    for name in (
        "BadRequest",
        "IdempotencyConflict",
        "UnprocessableEntity",
        "InternalError",
        "ModelUnavailable",
    ):
        schema = components[name]["content"]["application/json"]["schema"]
        assert schema["$ref"] == "./schemas/common.schema.json#/$defs/ErrorResponse"


def test_both_paths_declare_the_idempotency_key_header(openapi_document):
    for path, item in openapi_document["paths"].items():
        parameters = item["post"]["parameters"]
        names = [
            parameter["$ref"].split("/")[-1] for parameter in parameters
        ]
        assert "IdempotencyKey" in names or "IdempotencyKeyOptional" in names, path
        ref = next(
            parameter["$ref"]
            for parameter in parameters
            if parameter["$ref"].endswith(("IdempotencyKey", "IdempotencyKeyOptional"))
        )
        parameter = openapi_document["components"]["parameters"][ref.split("/")[-1]]
        assert parameter["name"] == "Idempotency-Key"
        assert parameter["in"] == "header"


def test_track_a_requires_idempotency_and_track_b_makes_it_optional(openapi_document):
    track_a = openapi_document["paths"]["/v1/predictions/cad-tabular"]["post"]
    track_b = openapi_document["paths"]["/v1/monitoring/observations"]["post"]
    assert track_a["x-idempotency"]["required"] is True
    assert track_b["x-idempotency"]["required"] is False


def test_idempotency_contract_documents_replay_and_conflict(openapi_document):
    track_a = openapi_document["paths"]["/v1/predictions/cad-tabular"]["post"]
    idempotency = track_a["x-idempotency"]
    assert "replay" in idempotency and "conflict" in idempotency
    assert idempotency["retention_hours"] == 24
    assert "canonical" in idempotency["canonical_payload"].lower()


def test_both_paths_document_explicit_error_responses(openapi_document):
    for path, item in openapi_document["paths"].items():
        responses = item["post"]["responses"]
        assert "400" in responses, path
        assert "422" in responses, path
        assert "500" in responses, path
    assert "409" in openapi_document["paths"]["/v1/predictions/cad-tabular"]["post"]["responses"]
    assert "503" in openapi_document["paths"]["/v1/predictions/cad-tabular"]["post"]["responses"]


def test_every_documented_error_code_exists_in_the_catalogue(openapi_document, schema_documents):
    catalogue = set(schema_documents["common.schema.json"]["$defs"]["ErrorCode"]["enum"])
    for path, item in openapi_document["paths"].items():
        for status, codes in item["post"]["x-error-codes"].items():
            for code in codes:
                assert code in catalogue, f"{path} {status}: unknown error code {code}"


def test_openapi_states_that_the_package_is_mock_synthetic_data(openapi_document):
    blob = json.dumps(openapi_document)
    assert "MOCK / SYNTHETIC DATA" in blob
    assert "PROPOSED" in openapi_document["info"]["description"]


def test_openapi_does_not_expose_a_risk_or_alert_field(openapi_document):
    """No risk horizon, alert level or treatment field may appear in the API."""
    forbidden = {
        "risk",
        "risk_score",
        "risk_level",
        "30_day_risk",
        "alert",
        "alert_level",
        "ci_95",
        "confidence_interval",
        "treatment",
        "recommendation",
        "diagnosis",
    }

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                yield key
                yield from walk(value)
        elif isinstance(node, list):
            for item in node:
                yield from walk(item)

    for key in walk(openapi_document):
        assert key.lower() not in forbidden, f"forbidden API field name: {key}"


def test_openapi_targets_are_tagged_by_track(openapi_document):
    for path, item in openapi_document["paths"].items():
        tags = item["post"]["tags"]
        expected = "track-a" if "predictions" in path else "track-b"
        assert tags == [expected], path


def test_openapi_body_schemas_point_at_the_shared_schema_files(openapi_document):
    """The OpenAPI document and the JSON Schemas must not drift apart."""
    expected = {
        "/v1/predictions/cad-tabular": (
            "./schemas/cad_tabular_prediction.request.schema.json",
            "./schemas/cad_tabular_prediction.response.schema.json",
        ),
        "/v1/monitoring/observations": (
            "./schemas/monitoring_observation.request.schema.json",
            "./schemas/monitoring_observation.response.schema.json",
        ),
    }
    for path, item in openapi_document["paths"].items():
        post = item["post"]
        request_ref = post["requestBody"]["content"]["application/json"]["schema"]["$ref"]
        success_status = "200" if "predictions" in path else "201"
        response_ref = post["responses"][success_status]["content"]["application/json"][
            "schema"
        ]["$ref"]
        assert (request_ref, response_ref) == expected[path], path


def test_openapi_declares_the_two_success_statuses(openapi_document):
    assert "200" in openapi_document["paths"]["/v1/predictions/cad-tabular"]["post"]["responses"]
    assert "201" in openapi_document["paths"]["/v1/monitoring/observations"]["post"]["responses"]
