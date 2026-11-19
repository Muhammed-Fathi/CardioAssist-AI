"""RH-04 offline fixture replay. No user records, bundle paths or keys accepted."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

from ai.filesystem_security import ensure_private_directory
from ai.packaging import get_or_create_local_signing_key
from ai.panels import REGISTERED_PANELS
from ai.research_demo import (
    _as_record_document,
    _base_document,
    _build_demo_bundle,
    _demo_records,
    _record_from_envelope,
)
from ai.research_facade import (
    LocalSyntheticBundleSource,
    RESPONSE_SCHEMA_VERSION,
    ResearchFacadeStatus,
    canonical_response_digest,
    run_offline_research_inference_from_document,
)
from ai.research_registry import RESEARCH_MODEL_REGISTRY, registry_digest_sha256
from ai.research_routes import (
    RESEARCH_ROUTE_CATALOG,
    build_synthetic_uci412_basic_clinical_cohort,
)
from ai.uci412_research import (
    Uci412ResearchModelConfig,
    build_uci412_synthetic_research_model,
)
from research.intake.feature_acquisition_crosswalk import load_crosswalk

PACK = Path(__file__).with_name("fixtures") / "offline_io.v1.json"
REST = "da_a2_resting_v1"
BASIC = "da_a1_basic_clinical_v1"
ACTIVE = {REST, BASIC}


def inputs():
    """Materialize exclusively registered generator output or non-scoring probes."""
    bases = {}
    for entry in RESEARCH_MODEL_REGISTRY.values():
        route = RESEARCH_ROUTE_CATALOG[entry.route_id]
        panel = REGISTERED_PANELS[route.panel_id]
        if (
            entry.executable != (route.route_id in ACTIVE)
            or entry.panel_contract_sha256 != panel.contract_sha256
            or entry.panel_contract_sha256 != route.panel_contract_sha256
        ):
            raise ValueError("registry permission or panel drift")
        if route.route_id == REST:
            record = _as_record_document(_demo_records()[0])
        elif route.route_id == BASIC:
            rows, _ = build_synthetic_uci412_basic_clinical_cohort(16, seed=42)
            record = _as_record_document(
                _record_from_envelope(rows[0], 0, acquisition_stage="basic_clinical")
            )
            record["synthetic_provenance"].update(
                generator_id=entry.admissible_synthetic_generators[0],
                seed=42,
                fixture_ref="rh04_basic",
            )
        else:
            record = _as_record_document(
                _demo_records()[0]
            )  # grammar-valid refusal probe only
        bases[route.route_id] = _base_document(
            [record],
            **{
                key: getattr(entry, key)
                for key in (
                    "route_id",
                    "route_version",
                    "model_id",
                    "model_version",
                    "panel_id",
                    "panel_version",
                    "dataset_id",
                    "panel_contract_sha256",
                )
            },
        )
    return bases


def bindings():
    walk = load_crosswalk()
    if walk.schema_version != "1.1.0":
        raise ValueError("unsupported crosswalk")
    return {
        "version": "1.0.0",
        "crosswalk_sha256": walk.document_digest_sha256,
        "crosswalk_version": walk.schema_version,
        "registry_sha256": registry_digest_sha256(),
        "response_schema": RESPONSE_SCHEMA_VERSION,
        "route_sha256": {
            k: v.descriptor_sha256 for k, v in RESEARCH_ROUTE_CATALOG.items()
        },
    }


def sources(root):
    demo = _build_demo_bundle(ensure_private_directory(root / "rest"))
    basic = build_uci412_synthetic_research_model(
        Uci412ResearchModelConfig.fast(
            package_bundle=True, work_root=ensure_private_directory(root / "basic")
        )
    )
    return {
        "blocked": LocalSyntheticBundleSource(root / "absent", root),
        REST: LocalSyntheticBundleSource(
            demo["bundle_dir"], demo["trusted_root"], demo["signing_key"]
        ),
        BASIC: LocalSyntheticBundleSource(
            basic.bundle_dir,
            basic.trusted_root,
            get_or_create_local_signing_key(basic.signing_key_path),
        ),
    }


def materialize(base, edits):
    request = deepcopy(base)
    for path, value in edits:
        parent = request
        for key in path[:-1]:
            parent = parent[key]
        if value is None:
            del parent[path[-1]]
        else:
            parent[path[-1]] = value
    return request


def example(request, source):
    response = run_offline_research_inference_from_document(
        request, model_source=source
    )
    data = response.to_dict()
    if response.status is not ResearchFacadeStatus.SYNTHETIC_RESULT:
        if any(
            any(x is not None for x in (o.score, o.shap, o.lime, o.uncertainty))
            for o in response.outcomes
        ):
            raise ValueError("refusal carried result data")
    # Explicit consumer allowlist: never export artifact metadata or input echoes.
    out = {
        k: data[k]
        for k in (
            "status",
            "panel_id",
            "route_id",
            "dataset_id",
            "evidence_level",
            "error",
        )
    }
    out["outcomes"] = [
        {
            k: item[k]
            for k in (
                "status",
                "score",
                "abstention_reason",
                "unavailable_reason",
                "present_fields",
                "missing_fields_with_reason",
                "error",
            )
        }
        for item in (o.to_dict() for o in response.outcomes)
    ]
    return out


def validate(pack):
    if pack["bindings"] != bindings() or pack["requests"] != inputs():
        raise ValueError("stale binding or non-fixture request")
    # Only the shipped, reviewed edits may reach the facade, not arbitrary local data.
    if canonical_response_digest(pack) != PACK_SHA256:
        raise ValueError("fixture integrity mismatch")
    with TemporaryDirectory() as tmp:
        local = sources(ensure_private_directory(Path(tmp)))
        for case in pack["cases"]:
            route = case["route"]
            request = materialize(pack["requests"][route], case["edits"])
            actual = example(request, local.get(route, local["blocked"]))
            if actual != case["expected"]:
                raise ValueError("response mismatch: " + case["id"])
    return len(pack["cases"])


PACK_SHA256 = "6c628c6d2e99cfab08036818c6b6a3231c19f2aecac3fb512273baea8110d346"

if __name__ == "__main__":
    print(
        f"{validate(json.loads(PACK.read_text()))} offline examples verified: {PACK_SHA256}"
    )
