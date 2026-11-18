"""AI-11.2: read-only projection of the reviewed synthetic research registry.

A catalog is descriptive metadata, NEVER a loader, authenticator, or an
authorization. The existing offline facade owns all operational validation.
No dataset, model artifact, signing key, credential, HTTP provider, or
caller-defined model is read, imported, or selected here.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Final

from ai.panels import REGISTERED_PANELS
from ai.research_registry import RESEARCH_MODEL_REGISTRY, registry_contract

CATALOG_SCHEMA_VERSION: Final[str] = "cardioassist.ai.research_model_catalog/v1"
CATALOG_VERSION: Final[str] = "1.0.0"
CARD_REFERENCE: Final[str] = (
    "docs/research/ai12_1/linux-uci45-envelope.v1.json#model_card"
)
CARD_MODEL_KEY: Final[str] = "synth_ai7_da_a2_resting_v1@0.1.0"


def _canonical_sha256(document: dict[str, Any]) -> str:
    raw = json.dumps(
        document, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build_research_model_catalog() -> dict[str, Any]:
    """Project immutable, source-derived metadata; never inspect model bundles.

    The published card reference applies ONLY to the actual AI-12.1 fixed
    Cleveland synthetic fixture. All five slots have no artifact-verified
    capabilities in this catalog, even when the registry declares support.
    """
    original = registry_contract()
    entries: list[dict[str, Any]] = []
    for key, registered in sorted(original["entries"].items()):
        source = RESEARCH_MODEL_REGISTRY[key]
        panel = REGISTERED_PANELS[source.panel_id]
        if registered != source.to_contract_dict():
            raise ValueError("Registry entry projection mismatch.")
        if (
            registered["panel_contract_sha256"] != panel.contract_sha256
            or registered["panel_version"] != panel.panel_version
            or any(registered["governance"][flag] is not False for flag in (
                "real_data_execution_authorized",
                "approved_for_serving",
                "clinical_use_authorized",
            ))
        ):
            raise ValueError("Catalog source contract/governance mismatch.")

        entries.append({
            "model_key": key,
            "model_id": source.model_id,
            "model_version": source.model_version,
            "registry_entry_sha256": source.entry_sha256,
            "route_id": source.route_id,
            "route_version": source.route_version,
            "dataset_id": source.dataset_id,
            "source_family": source.source_family,
            "target_id": source.target_id,
            "protocol_id": source.protocol_id,
            "execution_profile": source.execution_profile,
            "artifact_kind": source.artifact_kind,
            "entry_state": source.entry_state,
            "non_executable_reason": source.non_executable_reason,
            "offline_synthetic_registration_active": source.executable,
            "panel_id": source.panel_id,
            "panel_version": source.panel_version,
            "panel_contract_sha256": panel.contract_sha256,
            "ordered_feature_names": list(panel.feature_names),
            "features": [f.to_contract_dict() for f in panel.fields],
            "allowed_model_families": list(source.allowed_model_families),
            "permitted_operations": sorted(source.permitted_operations),
            "inference_policy": registered["inference_policy"],
            "registry_declared_capabilities": registered["capabilities"],
            "verified_artifact_capabilities": None,
            "evidence_level": source.evidence_level,
            "published_synthetic_model_card_reference": (
                CARD_REFERENCE if key == CARD_MODEL_KEY else None
            ),
            "governance": {
                "real_data_execution_authorized": False,
                "approved_for_serving": False,
                "clinical_use_authorized": False,
                "gate_pt_p3": "CLOSED",
                "serving_eligibility": "RESEARCH_ONLY",
            },
            "local_paths_disclosed": False,
        })

    envelope = {
        "schema_version": CATALOG_SCHEMA_VERSION,
        "catalog_version": CATALOG_VERSION,
        "source_registry_schema_version": original["registry_schema_version"],
        "source_registry_version": original["registry_version"],
        "source_registry_digest_sha256": original["registry_digest_sha256"],
        "purpose": "READ_ONLY_OFFLINE_SYNTHETIC_RESEARCH_DESCRIPTION",
        "catalog_is_artifact_authentication": False,
        "catalog_authorizes_loading_or_serving": False,
        "registry_capabilities_are_artifact_verified": False,
        "governance": {
            "real_data_execution_authorized": False,
            "approved_for_serving": False,
            "clinical_use_authorized": False,
            "gate_pt_p3": "CLOSED",
            "serving_eligibility": "RESEARCH_ONLY",
        },
        "entry_count": len(entries),
        "entries": entries,
    }
    envelope["catalog_sha256"] = _canonical_sha256(envelope)
    return envelope


def catalog_json_bytes() -> bytes:
    """Stable UTF-8 projection; an unhashed newline is only presentation."""
    return (
        json.dumps(
            build_research_model_catalog(), indent=2,
            sort_keys=True, ensure_ascii=True, allow_nan=False,
        ) + "\n"
    ).encode("utf-8")
