"""C2 served-OpenAPI contract tests (checkpoint §9).

The five C2 clinical-intake operations are composed into the served
``/openapi.json`` from ``c2-paths-assessment.yaml`` + the C2 request/response
schemas, with the frozen authentication/idempotency flags, error matrices
resolvable against the closed 63-code catalogue, and score-free response
shapes (``research_output`` always null, SAFE_SCOPE status-only S1).
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import yaml

from backend.app.term1 import constants, errors, openapi

ROOT = Path(__file__).resolve().parents[3]
TERM1_DIR = ROOT / "shared" / "contracts" / "term1"
SCHEMA_DIR = TERM1_DIR / "schemas"

C2_OPS = {
    ("get", "/v1/me/health-profile"),
    ("patch", "/v1/me/health-profile"),
    ("post", "/v1/assessments"),
    ("get", "/v1/assessments/{assessment_id}"),
    ("get", "/v1/me/assessments"),
}

FORBIDDEN_PATH_MARKERS = ("research", "synth", "facade", "artifact", "registry")


def _c2_module() -> dict:
    return yaml.safe_load((TERM1_DIR / "c2-paths-assessment.yaml").read_text())


def _served_document() -> dict:
    from backend.app.main import create_app

    return create_app().openapi()


def _ops(document: dict) -> set[tuple[str, str]]:
    return {
        (method, path)
        for path, item in document["paths"].items()
        for method in item
        if method in {"get", "post", "put", "patch", "delete"}
    }


# --- composition ------------------------------------------------------------


def test_c2_operations_are_composed_into_the_served_document():
    document = _served_document()
    served = _ops(document)
    assert C2_OPS <= served
    assert served == set(openapi.SERVED_OPERATIONS)
    assert len(served) == 27  # 2 legacy + 20 C1 + 5 C2
    assert set(openapi.C2_OPERATIONS) == C2_OPS
    assert set(openapi.C1_OPERATIONS).isdisjoint(C2_OPS)
    assert set(openapi.LEGACY_OPERATIONS).isdisjoint(C2_OPS)


def test_c2_paths_carry_no_forbidden_markers():
    for method, path in C2_OPS:
        for marker in FORBIDDEN_PATH_MARKERS:
            assert marker not in path.lower(), (path, marker)


def test_c2_auth_and_idempotency_flags_are_frozen():
    authenticated_paths = {path for _, path in C2_OPS}
    idempotent_ops = {
        ("patch", "/v1/me/health-profile"),
        ("post", "/v1/assessments"),
    }
    idempotent_paths = {path for _, path in idempotent_ops}
    assert openapi.AUTHENTICATED_C2 == authenticated_paths
    # The helper frozenset is path-level by design; the operation-level check
    # below pins which method on a shared path actually requires the header.
    assert openapi.IDEMPOTENT_C2 == idempotent_paths
    document = _served_document()
    for method, path in C2_OPS:
        operation = document["paths"][path][method]
        assert operation.get("security") == [{"bearerAuth": []}], (method, path)
        has_idempotency_key = any(
            parameter.get("name") == "Idempotency-Key"
            for parameter in operation.get("parameters", [])
        )
        assert has_idempotency_key is ((method, path) in idempotent_ops), (method, path)


def test_c2_parameters_and_schema_bindings():
    document = _served_document()

    s2 = document["paths"]["/v1/assessments/{assessment_id}"]["get"]
    assert any(
        p.get("name") == "assessment_id" and p.get("in") == "path"
        for p in s2.get("parameters", [])
    )
    assert "term1_assessment_get_response.schema.json" in json.dumps(s2)

    s3 = document["paths"]["/v1/me/assessments"]["get"]
    query_names = {p.get("name") for p in s3.get("parameters", []) if p.get("in") == "query"}
    assert query_names == {"limit", "cursor"}
    assert "term1_me_assessments_response.schema.json" in json.dumps(s3)

    h1a = document["paths"]["/v1/me/health-profile"]["get"]
    assert "term1_health_profile_response.schema.json" in json.dumps(h1a)

    h1b = document["paths"]["/v1/me/health-profile"]["patch"]
    assert "term1_health_profile_patch_request.schema.json" in json.dumps(h1b)
    assert "term1_health_profile_response.schema.json" in json.dumps(h1b)

    s1 = document["paths"]["/v1/assessments"]["post"]
    assert "term1_assessment_create_request.schema.json" in json.dumps(s1)
    assert "term1_assessment_create_response.schema.json" in json.dumps(s1)


# --- closed error matrices --------------------------------------------------


def test_every_c2_error_matrix_code_is_in_the_closed_catalogue():
    module = _c2_module()
    assert module["status"] == "PROPOSED — NOT APPROVED, NOT DEPLOYED"
    declared: set[str] = set()
    for op in module["operations"]:
        assert op["id"] in {"H1a", "H1b", "S1", "S2", "S3"}
        for response in op["responses"]:
            for code in response.get("codes", []):
                assert code in errors.ERROR_CATALOGUE, (op["id"], code)
                assert (
                    str(errors.ERROR_CATALOGUE[code][0]) == str(response["status"])
                ), (op["id"], code, response["status"])
                declared.add(code)
    # Every C2-specific code appears in at least one C2 operation matrix.
    c2_codes = {
        code
        for code in errors.ERROR_CATALOGUE
        if code
        in {
            "admin_clinical_content_forbidden",
            "consent_required",
            "ocr_inference_not_authorized",
            "health_profile_not_found",
            "assessment_not_found",
            "document_not_found",
            "extraction_not_found",
            "health_profile_superseded",
            "document_not_confirmed",
            "document_integrity_mismatch",
            "document_limit_reached",
            "extraction_already_confirmed",
            "extraction_version_conflict",
            "stale_attempt_fenced",
            "payload_too_large",
            "unsupported_media_type",
            "active_pdf_content_rejected",
            "health_profile_incomplete",
            "invalid_document_content",
            "invalid_panel_input",
            "missing_mandatory_attachment",
            "missing_reason_mismatch",
            "prohibited_clinical_field",
            "provenance_relabeling_forbidden",
            "unsupported_template_for_intake",
            "worker_unavailable",
        }
    }
    assert len(c2_codes) == 26
    # clinical-intake codes are reachable from this module; document/OCR codes
    # belong to Track 2's c2-paths-documents.yaml (added later).
    track2_only = {
        "document_limit_reached",
        "extraction_already_confirmed",
        "extraction_version_conflict",
        "stale_attempt_fenced",
        "payload_too_large",
        "unsupported_media_type",
        "active_pdf_content_rejected",
        "invalid_document_content",
        "missing_mandatory_attachment",
        "provenance_relabeling_forbidden",
        "unsupported_template_for_intake",
    }
    assert (c2_codes - track2_only) <= declared


# --- frozen response shapes -------------------------------------------------


def _schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text())


def test_c2_schemas_are_valid_draft_2020_12():
    for name in (
        "term1_health_profile_patch_request.schema.json",
        "term1_health_profile_response.schema.json",
        "term1_assessment_create_request.schema.json",
        "term1_assessment_create_response.schema.json",
        "term1_assessment_get_response.schema.json",
        "term1_me_assessments_response.schema.json",
    ):
        jsonschema.Draft202012Validator.check_schema(_schema(name))


def test_request_schemas_are_closed_and_service_owned_for_domain_codes():
    h1b = _schema("term1_health_profile_patch_request.schema.json")
    assert h1b["additionalProperties"] is False
    # panel maps stay open at the schema layer so the service can report
    # prohibited_clinical_field / invalid_panel_input precisely
    for key in ("inputs", "units", "missing_reasons"):
        assert h1b["properties"][key]["type"] == "object"
        assert "additionalProperties" not in h1b["properties"][key]
    # provenance/OCR reference keys pass the schema and are rejected by the
    # service with 422 prohibited_clinical_field (API spec §2.1)
    for key in (
        "source_kind",
        "source_contract_version",
        "provenance",
        "profile_sha256",
        "ocr_source",
        "document_id",
        "extraction_id",
    ):
        assert key in h1b["properties"]

    s1 = _schema("term1_assessment_create_request.schema.json")
    assert s1["additionalProperties"] is False
    assert s1["properties"]["input_mode"]["enum"] == ["manual", "ocr_confirmed"]
    assert "additionalProperties" not in s1["properties"]["panel_input"]["properties"]["inputs"]


def test_response_schemas_pin_the_safe_scope_shapes():
    create = _schema("term1_assessment_create_response.schema.json")
    assert create["properties"]["status"]["const"] == "INFERENCE_UNAVAILABLE"
    assert create["properties"]["reason_code"]["const"] == "real_ai_not_authorized"
    assert create["properties"]["review_state"]["const"] == "NOT_REVIEWED"
    assert create["properties"]["source_kind"]["const"] == constants.SOURCE_KIND_MANUAL
    assert set(create["required"]) == {
        "contract_version",
        "assessment_id",
        "assignment_id",
        "health_profile_id",
        "snapshot_id",
        "snapshot_sha256",
        "panel_id",
        "panel_version",
        "source_contract_version",
        "source_kind",
        "status",
        "reason_code",
        "attempt_id",
        "review_state",
        "created_at",
    }

    detail = _schema("term1_assessment_get_response.schema.json")
    assert detail["properties"]["research_output"] == {"type": "null"}
    assert detail["properties"]["source_kind"]["enum"] == list(constants.SOURCE_KINDS)
    assert "research_output" in detail["required"]

    listing = _schema("term1_me_assessments_response.schema.json")
    item = listing["properties"]["items"]["items"]
    assert "research_output" not in item["properties"]
    assert "inputs" not in item["properties"]
    assert item["properties"]["source_kind"]["enum"] == list(constants.SOURCE_KINDS)
    assert set(item["required"]) == {
        "assessment_id",
        "assignment_id",
        "panel_id",
        "panel_version",
        "status",
        "reason_code",
        "source_kind",
        "attempt_id",
        "review_state",
        "created_at",
    }

    profile = _schema("term1_health_profile_response.schema.json")
    assert set(profile["required"]) == {
        "contract_version",
        "health_profile_id",
        "version_number",
        "status",
        "panel_id",
        "panel_version",
        "schema_version",
        "inputs",
        "units",
        "missing_reasons",
        "provenance",
        "profile_sha256",
        "created_at",
    }
    assert profile["properties"]["schema_version"]["const"] == "term1.c2.profile/v1"
    provenance = profile["properties"]["provenance"]
    assert provenance["required"] == ["source_contract_version", "source_kind"]
    assert (
        provenance["properties"]["source_contract_version"]["const"]
        == constants.SOURCE_CONTRACT_VERSION
    )
    assert provenance["properties"]["source_kind"]["const"] == constants.SOURCE_KIND_MANUAL


def test_panel_identity_literals_match_the_authorization_token():
    # OQ-4 / authorization-token table: the frozen contract hash.
    assert constants.PANEL_CONTRACT_SHA256 == (
        "c18ad4cd2cf08f6fefb2e340573760da7000bc1d8eb4ad38783b873c018e57b8"
    )
    assert constants.PANEL_ID == "da_a2_resting_v1"
    assert constants.PANEL_VERSION == "1.0.0"
    assert constants.SNAPSHOT_SCHEMA_VERSION == "term1.c2.snapshot/v1"
    assert constants.PROFILE_SCHEMA_VERSION == "term1.c2.profile/v1"
    assert constants.SOURCE_CONTRACT_VERSION == "term1.c2.intake/v1"
    assert constants.LEASE_SECONDS == 300
    assert constants.WORKER_ID_DISABLED == "disabled_stub"
