"""Static AI-11.2 catalog schema tests: never import the research AI runtime."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs/research/ai11_2/research-model-catalog.v1.schema.json"
)
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA)


def _example() -> dict:
    """Fabricated schema-validation object, NOT a real model or score."""
    feature = {
        "name": "synthetic_test_feature", "order": 0, "role": "numeric",
        "clinical_meaning": "Test-only fabricated feature", "required": True,
        "stage": "test", "unit": None, "categorical_codes": [],
        "text_vocabulary": None, "strictly_positive": False,
        "plausible_range": None,
    }
    governance = {
        "real_data_execution_authorized": False,
        "approved_for_serving": False,
        "clinical_use_authorized": False,
        "gate_pt_p3": "CLOSED",
        "serving_eligibility": "RESEARCH_ONLY",
    }
    entries = []
    for index in range(5):
        entries.append({
            "model_key": f"synthetic_test_{index}@0.0.1",
            "model_id": f"synthetic_test_{index}", "model_version": "0.0.1",
            "registry_entry_sha256": "a" * 64,
            "route_id": "synthetic_test_route", "route_version": "1.0.0",
            "dataset_id": "TEST", "source_family": "FAKE", "target_id": "TEST",
            "protocol_id": "TEST", "execution_profile": "TEST",
            "artifact_kind": "local_verified_synthetic_bundle",
            "entry_state": "ACTIVE_SYNTHETIC_OFFLINE",
            "non_executable_reason": None,
            "offline_synthetic_registration_active": True,
            "panel_id": "synthetic_test_panel", "panel_version": "1.0.0",
            "panel_contract_sha256": "b" * 64,
            "ordered_feature_names": ["synthetic_test_feature"],
            "features": [copy.deepcopy(feature)],
            "allowed_model_families": ["l2_logistic_regression"],
            "permitted_operations": ["route_contract_query"],
            "inference_policy": {
                "abstain_on_missing_optional": False,
                "max_records_per_invocation": 16,
                "admissible_synthetic_generators": [],
                "required_acquisition_stages": {},
            },
            "registry_declared_capabilities": {
                "calibration_supported": False, "shap_supported": False,
                "lime_supported": False,
            },
            "verified_artifact_capabilities": None,
            "evidence_level": "NOT_EVALUATED_NO_SYNTHETIC_EXERCISE",
            "published_synthetic_model_card_reference": None,
            "governance": copy.deepcopy(governance),
            "local_paths_disclosed": False,
        })
    return {
        "schema_version": "cardioassist.ai.research_model_catalog/v1",
        "catalog_version": "1.0.0",
        "source_registry_schema_version": "cardioassist.ai.research_registry/v1",
        "source_registry_version": "1.0.0",
        "source_registry_digest_sha256": "c" * 64,
        "purpose": "READ_ONLY_OFFLINE_SYNTHETIC_RESEARCH_DESCRIPTION",
        "catalog_is_artifact_authentication": False,
        "catalog_authorizes_loading_or_serving": False,
        "registry_capabilities_are_artifact_verified": False,
        "governance": governance,
        "entry_count": 5, "entries": entries,
        "catalog_sha256": "d" * 64,
    }


def test_schema_is_valid_2020_12_and_accepts_test_only_fixture() -> None:
    Draft202012Validator.check_schema(SCHEMA)
    assert VALIDATOR.is_valid(_example())


@pytest.mark.parametrize(
    "path,value",
    [
        (("schema_version",), "cardioassist.ai.research_model_catalog/v2"),
        (("entry_count",), 4),
        (("catalog_is_artifact_authentication",), True),
        (("catalog_authorizes_loading_or_serving",), True),
        (("registry_capabilities_are_artifact_verified",), True),
        (("source_registry_digest_sha256",), "not-a-sha"),
        (("governance", "approved_for_serving"), True),
        (("governance", "clinical_use_authorized"), True),
        (("entries", 0, "governance", "real_data_execution_authorized"), True),
        (("entries", 0, "entry_state"), "PRODUCTION"),
        (("entries", 0, "verified_artifact_capabilities"), {"shap": True}),
        (("entries", 0, "local_paths_disclosed"), True),
        (("entries", 0, "panel_contract_sha256"), "0"),
        (("entries", 0, "features", 0, "role"), "patient_record"),
    ],
)
def test_schema_rejects_scope_and_type_promotion(path, value) -> None:
    candidate = _example()
    parent = candidate
    for key in path[:-1]:
        parent = parent[key]
    parent[path[-1]] = value
    assert not VALIDATOR.is_valid(candidate)


def test_schema_refuses_extra_payload_fields() -> None:
    top = _example()
    top["raw_patient_rows"] = [{"sensitive": "example"}]
    assert not VALIDATOR.is_valid(top)

    nested = _example()
    nested["entries"][0]["bundle_path"] = "C:/private"
    assert not VALIDATOR.is_valid(nested)

    short = _example()
    short["entries"].pop()
    assert not VALIDATOR.is_valid(short)

    missing = _example()
    del missing["entries"][0]["registry_entry_sha256"]
    assert not VALIDATOR.is_valid(missing)
