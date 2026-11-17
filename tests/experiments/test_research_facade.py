"""AI-11.1 — offline research model registry and typed inference facade tests.

These tests exercise :mod:`ai.research_registry` and :mod:`ai.research_facade`
against a *real* synthetic training run and a *real* producer-authenticated
bundle, and prove the negative cases fail closed instead of degrading:

* registry immutability, digest stability, entry lifecycle states, and the
  refusal to register any real-patient artifact or expose a mutation API;
* one successful ``SYNTHETIC_RESULT`` with registered calibration provenance,
  exact SHAP on its declared scale, and — only when requested — LIME carrying
  its quality verdict;
* ``ABSTAIN`` for a legal record with a missing optional field under the
  registered abstention policy;
* ``UNAVAILABLE`` for the registered-but-blocked contracts, which still report
  the registered route/model/panel versions they were blocked at;
* ``ERROR`` for unregistered models, wrong versions, invalid types/units/
  fields, a missing required field, outcome leakage, wearable contamination,
  forged synthetic provenance, untrusted bundle locations, a tampered
  artifact, a foreign producer key, and an absent signing key; and
* redaction and determinism guarantees: no local path, no submitted value, no
  wall-clock timing in any response, and byte-identical payloads for identical
  calls.

Everything runs on generated synthetic fixtures inside private temporary
directories. No real patient record, real bundle, or clinical claim is
involved, and nothing here authorizes serving any model.
"""
from __future__ import annotations

import copy
import dataclasses
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest

from ai.filesystem_security import ensure_private_directory, protect_private_file
from ai.panels import REGISTERED_PANELS
from ai.packaging import get_or_create_local_signing_key
from ai.research_demo import (
    DEMO_DATASET_ID,
    DEMO_MODEL_ID,
    DEMO_PANEL_ID,
    DEMO_ROUTE_ID,
    DEMO_SEED,
    ResearchFeatureRecord,
    _as_record_document,
    _base_document,
    _build_demo_bundle,
    _demo_records,
    run_research_facade_demo,
)
from ai.research_facade import (
    FACADE_ID,
    GENERIC_ERROR_CODE,
    FACADE_OPERATION,
    PIPELINE_STAGES,
    REQUEST_SCHEMA_VERSION,
    RESPONSE_SCHEMA_VERSION,
    STATUS_PRECEDENCE,
    ExplainabilityOptions,
    FacadeErrorDetail,
    LocalSyntheticBundleSource,
    ResearchFacadeStatus,
    ResearchInferenceRequest,
    ResearchInferenceResponse,
    SyntheticFixtureProvenance,
    build_request_summary,
    canonical_response_digest,
    safe_document_summary,
    is_registered_static_error_message,
    parse_feature_record,
    parse_inference_request,
    parse_synthetic_provenance,
    run_offline_research_inference,
    run_offline_research_inference_from_document,
)
from ai.research_registry import (
    ADMISSIBLE_ARTIFACT_KINDS,
    EVIDENCE_LEVEL_NOT_EVALUATED,
    EVIDENCE_LEVEL_SYNTHETIC_TEST,
    ENTRY_STATE_ACTIVE,
    ENTRY_STATE_BLOCKED_PENDING_AUTHORIZATION,
    ENTRY_STATE_BLOCKED_SOURCE_TIMING,
    ENTRY_STATE_LOCKED_EXTERNAL_TARGET,
    KNOWN_ENTRY_STATES,
    MAX_RECORDS_CEILING,
    REAL_ARTIFACT_MODEL_ID_PREFIXES,
    REGISTRY_ROUTE_IDS,
    REGISTRY_SCHEMA_VERSION,
    RESEARCH_MODEL_REGISTRY,
    SYNTHETIC_PROVENANCE_DECLARATION,
    ResearchRegistryError,
    SAFE_RECORD_REF_RE,
    get_model_entry,
    registry_contract,
    registry_digest_sha256,
    resolve_registered_model,
)
from ai.research_routes import RESEARCH_ROUTE_CATALOG


def _canonical(payload: dict) -> str:
    import hashlib
    import json as _json

    return hashlib.sha256(
        _json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
            "utf-8"
        )
    ).hexdigest()

DEMO_KEY = "synth_ai7_da_a2_resting_v1@0.1.0"
BLOCKED_PENDING_KEY = "synth_ai7_da_a2_resting_labs_v1@0.1.0"
BLOCKED_TIMING_KEY = "synth_ai7_da_a1_clinical_core_labs_v1@0.1.0"
LOCKED_EXTERNAL_KEY = "synth_ai7_da_a2_hungary_locked_transportability_v1@0.1.0"
UCI412_KEY = "synth_ai8_uci412_da_a1_basic_clinical@0.1.0"


# --------------------------------------------------------------------------- #
# Shared private artifact workspace                                            #
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="session")
def demo_bundle(tmp_path_factory: pytest.TempPathFactory) -> dict:
    """One real synthetic training run + producer-authenticated bundle."""
    root = ensure_private_directory(tmp_path_factory.mktemp("ai111_registry"))
    return _build_demo_bundle(root)


@pytest.fixture()
def source(demo_bundle: dict) -> LocalSyntheticBundleSource:
    return LocalSyntheticBundleSource(
        bundle_dir=Path(demo_bundle["bundle_dir"]),
        trusted_local_root=Path(demo_bundle["trusted_root"]),
        signing_key=demo_bundle["signing_key"],
    )


@pytest.fixture()
def records() -> tuple[ResearchFeatureRecord, ResearchFeatureRecord]:
    return _demo_records()


def call(source, documents, **overrides):
    """Run one request document through the facade's document entry point."""
    return run_offline_research_inference_from_document(
        _base_document(list(documents), **overrides), model_source=source
    )


def doc(record) -> dict:
    return _as_record_document(record)


def mutate(document: dict, **changes) -> dict:
    out = dict(document)
    out.update(changes)
    return out


def without(document: dict, *keys: str) -> dict:
    return {key: value for key, value in document.items() if key not in keys}


def with_feature(document: dict, name: str, value) -> dict:
    return mutate(document, features={**document["features"], name: value})


def without_feature(document: dict, *names: str) -> dict:
    dropped = set(names)
    return mutate(
        document,
        features={k: v for k, v in document["features"].items() if k not in dropped},
        units={k: v for k, v in document["units"].items() if k not in dropped},
    )


def error_of(response) -> FacadeErrorDetail:
    error = response.error
    if error is None and response.outcomes:
        error = response.outcomes[0].error
    assert error is not None, json.dumps(response.to_dict(), indent=2)
    return error


# --------------------------------------------------------------------------- #
# Registry contract                                                            #
# --------------------------------------------------------------------------- #


def test_registry_exposes_no_mutation_api_and_no_paths() -> None:
    import ai.research_registry as registry_module

    for forbidden in ("register", "update_entry", "deregister", "set_entry", "reload", "load"):
        assert not hasattr(registry_module, forbidden), forbidden
    contract = registry_contract()
    assert contract["mutation_api_present"] is False
    assert contract["real_artifacts_registerable"] is False
    assert contract["registry_schema_version"] == REGISTRY_SCHEMA_VERSION
    assert set(contract["admissible_artifact_kinds"]) == set(ADMISSIBLE_ARTIFACT_KINDS)
    assert contract["max_records_ceiling"] == MAX_RECORDS_CEILING
    # The registry reads nothing from disk: no filesystem path, environment
    # variable or URL appears anywhere in its published contract.
    serialized = json.dumps(contract, sort_keys=True)
    assert "\\" not in serialized
    assert str(Path.home()) not in serialized
    for forbidden in ("http://", "https://", "file://", ".venv", "AppData", "C:\\"):
        assert forbidden not in serialized, forbidden


def test_registry_entries_are_frozen_and_hash_addressed() -> None:
    entry = RESEARCH_MODEL_REGISTRY[DEMO_KEY]
    with pytest.raises(FrozenInstanceError):
        entry.model_version = "9.9.9"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        entry.entry_state = ENTRY_STATE_ACTIVE  # type: ignore[misc]
    payload = entry.to_contract_dict()
    assert len(entry.entry_sha256) == 64
    assert payload["local_paths_disclosed"] is False
    assert "signing_key" not in json.dumps(payload)
    assert entry.entry_sha256 == _canonical(entry.to_contract_dict())
    # Two different entries cannot share an entry digest.
    other = RESEARCH_MODEL_REGISTRY[BLOCKED_PENDING_KEY]
    assert other.entry_sha256 != entry.entry_sha256


def test_registry_digest_is_stable_and_over_every_entry() -> None:
    digest = registry_digest_sha256()
    assert digest == registry_contract()["registry_digest_sha256"]
    assert digest == registry_digest_sha256()
    assert len(digest) == 64
    assert set(RESEARCH_MODEL_REGISTRY) == set(registry_contract()["entries"])


def test_entry_lifecycle_states_and_capability_flags() -> None:
    states = {key: entry.entry_state for key, entry in RESEARCH_MODEL_REGISTRY.items()}
    assert states[DEMO_KEY] == ENTRY_STATE_ACTIVE
    assert states[BLOCKED_PENDING_KEY] == ENTRY_STATE_BLOCKED_PENDING_AUTHORIZATION
    assert states[BLOCKED_TIMING_KEY] == ENTRY_STATE_BLOCKED_SOURCE_TIMING
    assert states[LOCKED_EXTERNAL_KEY] == ENTRY_STATE_LOCKED_EXTERNAL_TARGET
    assert set(states.values()) <= set(KNOWN_ENTRY_STATES)
    assert {key for key, entry in RESEARCH_MODEL_REGISTRY.items() if entry.executable} == {
        DEMO_KEY,
        UCI412_KEY,
    }
    for key, entry in RESEARCH_MODEL_REGISTRY.items():
        if entry.executable:
            assert entry.non_executable_reason is None
            assert entry.evidence_level == EVIDENCE_LEVEL_SYNTHETIC_TEST
        else:
            assert entry.evidence_level == EVIDENCE_LEVEL_NOT_EVALUATED
            # A blocked entry advertises no capability and no operation power.
            assert entry.calibration_supported is False
            assert entry.shap_supported is False
            assert entry.lime_supported is False
            assert entry.approved_for_serving is False
            assert entry.clinical_use_authorized is False
            assert entry.real_data_execution_authorized is False
        assert entry.max_records_per_invocation <= MAX_RECORDS_CEILING
        assert entry.artifact_kind in ADMISSIBLE_ARTIFACT_KINDS
        assert entry.notes  # every entry states its own governance limitation


def test_every_entry_agrees_with_the_route_and_panel_registries() -> None:
    for entry in RESEARCH_MODEL_REGISTRY.values():
        assert entry.route_id in REGISTRY_ROUTE_IDS
        route = RESEARCH_ROUTE_CATALOG[entry.route_id]
        panel = REGISTERED_PANELS[entry.panel_id]
        assert entry.route_version == route.route_version
        assert entry.dataset_id == route.dataset_id
        assert entry.source_family == route.source_family
        assert entry.target_id == route.target_id
        assert entry.panel_id == route.panel_id
        assert entry.panel_contract_sha256 == route.panel_contract_sha256
        assert entry.panel_version == panel.panel_version
        assert entry.panel_contract_sha256 == panel.contract_sha256
        assert entry.execution_profile in route.supported_execution_profiles
        assert set(entry.allowed_model_families) <= set(route.allowed_model_families)
        if entry.executable:
            assert FACADE_OPERATION in entry.permitted_operations
        else:
            assert FACADE_OPERATION not in entry.permitted_operations
        assert set(entry.permitted_operations) <= set(route.permitted_operations)
        assert not (set(entry.permitted_operations) & set(route.forbidden_operations))
        assert all(name in panel.field_map for name in entry.required_acquisition_stages)


def test_real_patient_artifact_ids_are_never_registerable() -> None:
    contract = registry_contract()
    assert contract["real_artifacts_registerable"] is False
    assert "real_" in REAL_ARTIFACT_MODEL_ID_PREFIXES
    for entry in RESEARCH_MODEL_REGISTRY.values():
        assert not entry.model_id.startswith(REAL_ARTIFACT_MODEL_ID_PREFIXES)
    # A request for a real-patient model id is refused as unknown: no real
    # artifact is registered, and none can be registered through this facade.
    for model_id in ("cai_real_trained_v1", "cad_real_cleveland_v1", "real_da_a1_v1"):
        with pytest.raises(ResearchRegistryError) as excinfo:
            get_model_entry(model_id, "0.1.0")
        assert excinfo.value.code == "unknown_model_entry", model_id


def test_registry_construction_guards_reject_unsound_entries() -> None:
    """White-box test of the entry builder every registered entry passed.

    There is deliberately no public registration API, so the only way to show
    that the constraints are enforced (rather than merely documented) is to
    drive the same construction-time validator with unsound inputs.
    """
    from ai.research_registry import _build_entry

    generators = ("ai.research_routes.build_synthetic_uci45_resting_cohort",)
    base = {
        "model_version": "0.1.0",
        "route_id": DEMO_ROUTE_ID,
        "entry_state": ENTRY_STATE_ACTIVE,
        "evidence_level": EVIDENCE_LEVEL_SYNTHETIC_TEST,
        "calibration_supported": True,
        "shap_supported": True,
        "lime_supported": True,
        "abstain_on_missing_optional": True,
        "admissible_synthetic_generators": generators,
    }
    for label, changes, expected_code in (
        (
            "real artifact id",
            {"model_id": "cad_real_cleveland_v1"},
            "registry_real_artifact_not_registerable",
        ),
        (
            "blocked entry claiming capabilities",
            {
                "model_id": "synth_probe_blocked_v1",
                "entry_state": ENTRY_STATE_BLOCKED_PENDING_AUTHORIZATION,
                "evidence_level": EVIDENCE_LEVEL_NOT_EVALUATED,
            },
            "registry_blocked_entry_declares_capabilities",
        ),
        (
            "empty synthetic generator allowlist",
            {"model_id": "synth_probe_nogens_v1", "admissible_synthetic_generators": ()},
            "registry_generator_allowlist_empty",
        ),
        (
            "non-bundle artifact kind",
            {"model_id": "synth_probe_url_v1", "artifact_kind": "remote_url"},
            "registry_artifact_kind_not_allowed",
        ),
        (
            "unregistered entry state",
            {"model_id": "synth_probe_state_v1", "entry_state": "READY_FOR_CLINIC"},
            "registry_unknown_entry_state",
        ),
    ):
        with pytest.raises(ResearchRegistryError) as excinfo:
            _build_entry(**{**base, **changes})
        assert excinfo.value.code == expected_code, label
    # Serving and clinical-use authority are not builder arguments at all, so an
    # entry cannot over-claim them.
    assert "approved_for_serving" not in _build_entry.__code__.co_varnames
    assert "clinical_use_authorized" not in _build_entry.__code__.co_varnames
    built = _build_entry(model_id="synth_probe_ok_v1", **base)
    assert built.approved_for_serving is False
    assert built.clinical_use_authorized is False
    assert built.real_data_execution_authorized is False
    assert built.artifact_kind in ADMISSIBLE_ARTIFACT_KINDS


def test_resolve_registered_model_rejects_every_identifier_mismatch() -> None:
    entry = RESEARCH_MODEL_REGISTRY[DEMO_KEY]
    panel = REGISTERED_PANELS[DEMO_PANEL_ID]
    base = {
        "route_id": DEMO_ROUTE_ID,
        "route_version": entry.route_version,
        "model_id": entry.model_id,
        "model_version": entry.model_version,
        "panel_id": DEMO_PANEL_ID,
        "panel_version": panel.panel_version,
        "panel_contract_sha256": panel.contract_sha256,
        "dataset_id": entry.dataset_id,
        "operation": FACADE_OPERATION,
    }
    binding = resolve_registered_model(**base)
    assert binding.entry is entry
    assert binding.panel.panel_id == DEMO_PANEL_ID
    assert binding.route.route_id == DEMO_ROUTE_ID

    for field, value, expected_code in (
        ("model_id", "synth_unregistered_v1", "unknown_model_entry"),
        ("model_version", "9.9.9", "unknown_model_entry"),
        ("route_id", "da_a2_resting_labs_v1", "route_id_mismatch"),
        ("route_version", "99.0.0", "route_version_mismatch"),
        ("dataset_id", "DA-A1", "dataset_id_mismatch"),
        ("panel_id", "da_a1_basic_clinical_v1", "panel_id_mismatch"),
        ("panel_version", "9.9.9", "panel_version_mismatch"),
        ("panel_contract_sha256", "0" * 64, "panel_contract_hash_mismatch"),
        ("operation", "real_bundle_inference", "operation_not_permitted_for_model_entry"),
    ):
        payload = dict(base)
        payload[field] = value
        with pytest.raises(ResearchRegistryError) as excinfo:
            resolve_registered_model(**payload)
        assert excinfo.value.code == expected_code, field


@pytest.mark.parametrize(
    ("key", "expected_code"),
    [
        (BLOCKED_PENDING_KEY, "model_entry_blocked_pending_authorization"),
        (BLOCKED_TIMING_KEY, "model_entry_blocked_source_timing_unverified"),
        (LOCKED_EXTERNAL_KEY, "model_entry_locked_external_target"),
    ],
)
def test_blocked_entries_refuse_before_operation_checks_but_stay_visible(
    key: str, expected_code: str
) -> None:
    entry = RESEARCH_MODEL_REGISTRY[key]
    panel = REGISTERED_PANELS[entry.panel_id]
    with pytest.raises(ResearchRegistryError) as excinfo:
        resolve_registered_model(
            route_id=entry.route_id,
            route_version=entry.route_version,
            model_id=entry.model_id,
            model_version=entry.model_version,
            panel_id=entry.panel_id,
            panel_version=panel.panel_version,
            panel_contract_sha256=panel.contract_sha256,
            dataset_id=entry.dataset_id,
            operation=FACADE_OPERATION,
        )
    error = excinfo.value
    assert error.code == expected_code
    assert error.field == "entry_state"
    # The refusal carries the entry so an UNAVAILABLE response can still name
    # the exact registered contract that is blocked.
    assert error.entry is entry


def test_locked_external_target_entry_never_admits_prediction() -> None:
    entry = RESEARCH_MODEL_REGISTRY[LOCKED_EXTERNAL_KEY]
    assert FACADE_OPERATION not in entry.permitted_operations
    assert entry.execution_profile == "CLEVELAND_D047_FROZEN_V1"
    assert entry.real_data_execution_authorized is False


# --------------------------------------------------------------------------- #
# Request grammar                                                              #
# --------------------------------------------------------------------------- #


def test_request_and_record_grammars_reject_unknown_keys(source, records) -> None:
    document = mutate(_base_document(list(records)), unexpected_key="x")
    with pytest.raises(ResearchRegistryError) as excinfo:
        parse_inference_request(document, model_source=source)
    assert excinfo.value.code == "unexpected_request_key"

    with pytest.raises(ResearchRegistryError) as excinfo:
        parse_feature_record(mutate(doc(records[0]), extra=1))
    assert excinfo.value.code == "unexpected_record_key"

    with pytest.raises(ResearchRegistryError) as excinfo:
        parse_synthetic_provenance(
            mutate(
                doc(records[0])["synthetic_provenance"],
                evidence="trust_me",
            )
        )
    assert excinfo.value.code == "unexpected_provenance_key"


def test_schema_versions_and_stage_labels_are_pinned() -> None:
    assert REQUEST_SCHEMA_VERSION.endswith("research_inference_request/v1")
    assert RESPONSE_SCHEMA_VERSION.endswith("research_inference_response/v1")
    assert FACADE_ID.endswith("research_facade/v1")
    assert PIPELINE_STAGES == (
        "request",
        "registry",
        "route",
        "artifact",
        "record",
        "prediction",
    )
    assert STATUS_PRECEDENCE[0] is ResearchFacadeStatus.ERROR
    assert list(STATUS_PRECEDENCE) == [
        ResearchFacadeStatus.ERROR,
        ResearchFacadeStatus.UNAVAILABLE,
        ResearchFacadeStatus.ABSTAIN,
        ResearchFacadeStatus.SYNTHETIC_RESULT,
    ]


def test_a_bare_synthetic_flag_is_never_accepted_as_provenance(source, records) -> None:
    forged = {
        "record_ref": "forgedflag",
        "synthetic": True,
        "features": dict(records[0].features),
        "units": dict(records[0].units),
        "missing_reasons": {},
        "acquisition_stage": "resting_assessment",
    }
    with pytest.raises(ResearchRegistryError) as excinfo:
        parse_feature_record(forged)
    assert excinfo.value.code == "synthetic_flag_is_not_provenance"
    response = call(source, [forged])
    assert response.status is ResearchFacadeStatus.ERROR
    assert error_of(response).code == "synthetic_flag_is_not_provenance"
    assert response.outcomes == ()
    assert response.to_dict()["provenance"]["synthetic_flag_alone_accepted_as_evidence"] is False


def test_provenance_parser_requires_the_registered_block() -> None:
    with pytest.raises(ResearchRegistryError) as excinfo:
        parse_synthetic_provenance(None)
    assert excinfo.value.code == "synthetic_provenance_missing"
    with pytest.raises(ResearchRegistryError) as excinfo:
        parse_synthetic_provenance({"declaration": "real_patient_data"})
    assert excinfo.value.code in {
        "synthetic_provenance_declaration_unknown",
        "unexpected_provenance_key",
        "synthetic_provenance_malformed",
    }
    with pytest.raises(ResearchRegistryError):
        parse_synthetic_provenance("not-a-block")


def test_record_ref_grammar_is_enforced(source, records) -> None:
    with pytest.raises(ResearchRegistryError):
        parse_feature_record(mutate(doc(records[0]), record_ref="../escape"))
    response = call(source, [mutate(doc(records[0]), record_ref="an absolute/path")])
    assert response.status is ResearchFacadeStatus.ERROR
    assert error_of(response).code == "invalid_record_ref"


def test_missing_model_source_refuses_before_any_filesystem_access() -> None:
    response = run_offline_research_inference_from_document(
        _base_document([doc(record) for record in _demo_records()]),
        model_source=None,  # type: ignore[arg-type]
    )
    assert response.status is ResearchFacadeStatus.ERROR
    error = error_of(response)
    assert error.code == "model_source_not_allowed"
    assert error.stage == "request"
    assert response.to_dict()["artifact"] is None


def test_remote_or_url_artifact_source_is_not_a_supported_kind() -> None:
    with pytest.raises((ResearchRegistryError, TypeError, ValueError)):
        LocalSyntheticBundleSource(bundle_url="https://example.invalid/bundle")  # type: ignore[call-arg]


# --------------------------------------------------------------------------- #
# Successful synthetic inference                                               #
# --------------------------------------------------------------------------- #


def test_successful_call_returns_typed_calibrated_result(source, records) -> None:
    response = call(source, list(records))
    assert response.status is ResearchFacadeStatus.SYNTHETIC_RESULT
    assert response.error is None
    assert len(response.outcomes) == 2
    assert response.to_dict()["counts"]["SYNTHETIC_RESULT"] == 2
    outcome = response.outcomes[0]
    score = outcome.score
    assert score is not None
    assert score.kind == "CALIBRATED_RESEARCH_SCORE_SYNTHETIC"
    assert score.clinical_probability_claim is False
    assert score.threshold_clinically_validated is False
    assert score.interpretation == "RESEARCH_ONLY_NOT_INDIVIDUAL_CLINICAL_RISK"
    assert 0.0 <= score.raw_model_score <= 1.0
    assert 0.0 <= score.calibrated_research_score <= 1.0
    assert score.calibrated_log_odds is not None
    # The calibrated score must be the registered monotone map of the raw
    # log-odds — never a relabelled raw probability.
    from scipy.special import expit

    assert abs(expit(score.calibrated_log_odds) - score.calibrated_research_score) <= 1e-12
    capabilities = response.capabilities
    assert capabilities is not None
    assert capabilities.calibration_supported is True
    assert capabilities.calibrator_status == "FITTED_OOF_MONOTONE_LOGISTIC"
    assert capabilities.calibration_input_link == "exact_raw_log_odds"
    assert capabilities.calibration_fit_scope == "FULL_DEVELOPMENT_OOF_FINAL"
    assert capabilities.n_oof_samples == 96
    assert capabilities.development_prevalence == pytest.approx(0.71875)
    calibration_block = response.to_dict()["capabilities"]["calibration"]
    assert calibration_block["never_relabel_raw_score_as_calibrated"] is True
    assert calibration_block["oof_brier_before"] >= calibration_block["oof_brier_after"] - 1e-12
    assert (
        response.to_dict()["provenance"]["artifact_provenance_established_before_deserialization"]
        is True
    )


def test_success_reports_registered_binding_and_governance(source, records) -> None:
    payload = call(source, list(records)).to_dict()
    entry = RESEARCH_MODEL_REGISTRY[DEMO_KEY]
    assert payload["facade_id"] == FACADE_ID
    assert payload["response_schema_version"] == RESPONSE_SCHEMA_VERSION
    assert payload["route_id"] == DEMO_ROUTE_ID
    assert payload["model_id"] == DEMO_MODEL_ID
    assert payload["dataset_id"] == DEMO_DATASET_ID
    assert payload["protocol_id"] == entry.protocol_id
    assert payload["model_family"] == "l2_logistic_regression"
    assert payload["entry_state"] == ENTRY_STATE_ACTIVE
    assert payload["evidence_level"] == EVIDENCE_LEVEL_SYNTHETIC_TEST
    assert payload["registry"]["registry_digest_sha256"] == registry_digest_sha256()
    assert payload["registry"]["registry_entry_sha256"]
    assert payload["governance"] == {
        "serving_eligibility": "RESEARCH_ONLY",
        "approved_for_serving": False,
        "clinical_use_authorized": False,
        "real_data_execution_authorized": False,
        "http_surface_added": False,
        "provider_selection_changed": False,
        "requires_clinician_and_gate_pt_validation": True,
        "gate_pt_p3": "CLOSED",
    }
    assert payload["artifact"]["governance"]["approved_for_serving"] is False
    assert payload["artifact"]["verification"]["sha256_alone_authenticates_producer"] is False
    assert payload["artifact"]["verification"]["producer_authenticated"] is True
    assert payload["artifact"]["verification"]["safe_for_pickle_deserialization"] is True
    assert payload["artifact"]["verification"]["trusted_local_root_containment_required"] is True
    assert set(payload["artifact"]["verified_artifact_hashes"]) == {
        "model.joblib",
        "preprocessing.json",
        "calibration.json",
        "shap_background.json",
        "evaluation_summary.json",
        "protocol.md",
    }
    assert all(
        len(digest) == 64 for digest in payload["artifact"]["verified_artifact_hashes"].values()
    )
    assert "manifest.json" not in payload["artifact"]["verified_artifact_hashes"]


def test_shap_block_reports_scale_additivity_and_background_provenance(source, records) -> None:
    response = call(source, list(records))
    shap = response.outcomes[0].shap
    assert shap is not None and shap.provided is True
    assert shap.explained_quantity == "calibrated_log_odds"
    assert shap.scale == "calibrated_log_odds"
    assert shap.method == "linear_shap_interventional"
    assert shap.sum_check_passed is True
    assert shap.max_abs_discrepancy <= 1e-9
    assert shap.additive_on_calibrated_probability is False
    assert shap.background_synthetic_only is True
    assert shap.background_sample_count == 24
    assert shap.attribution_feature_names
    block = response.to_dict()["capabilities"]["explainability"]["shap"]
    assert block["background_panel_bound"] is True
    assert block["background_contains_patient_records"] is False
    assert block["background_privacy_classification"] == "SYNTHETIC_NON_PATIENT_DERIVATIVE"
    assert block["background_encoded_feature_count"] == 10


def test_shap_not_requested_is_reported_as_not_requested_not_absent(source, records) -> None:
    document = mutate(
        _base_document(list(records)),
        explainability={**_base_document(list(records))["explainability"], "include_shap": False},
    )
    response = run_offline_research_inference_from_document(document, model_source=source)
    assert response.status is ResearchFacadeStatus.SYNTHETIC_RESULT
    outcome = response.outcomes[0]
    assert outcome.score is not None
    assert outcome.shap.provided is False
    assert outcome.shap.reason == "not_requested_by_caller"
    # Capability reporting is independent of what the caller asked for.
    assert response.to_dict()["capabilities"]["explainability"]["shap"]["supported"] is True


def test_lime_is_opt_in_and_carries_its_quality_verdict(source, records) -> None:
    unasked = call(source, list(records))
    lime = unasked.outcomes[0].lime
    assert lime.provided is False
    assert lime.reason == "not_requested_by_caller"

    asked = call(source, list(records), with_lime=True)
    assert asked.status is ResearchFacadeStatus.SYNTHETIC_RESULT
    lime = asked.outcomes[0].lime
    assert lime.provided is True
    assert lime.quality_status == "ACCEPTABLE_LOCAL_APPROXIMATION"
    assert lime.is_reliable_for_interpretation is True
    assert lime.comparable_with_shap is True
    assert lime.explained_quantity == "calibrated_log_odds"
    assert lime.scale == "calibrated_log_odds"
    payload = json.dumps(asked.to_dict())
    # Wall-clock timing is excluded so a response digest is reproducible.
    assert "runtime" not in payload and "runtime_seconds" not in payload


def test_lime_declines_gracefully_when_generation_is_not_requested_but_supported(
    source, records
) -> None:
    response = call(source, list(records))
    capabilities = response.capabilities
    assert capabilities is not None and capabilities.lime_supported is True
    assert capabilities.lime_unsupported_reason is None
    assert response.outcomes[0].lime.payload is None


def test_response_is_json_clean_with_a_reproducible_digest(source, records) -> None:
    response = call(source, list(records), with_lime=True)
    payload = response.to_dict()
    round_tripped = json.loads(json.dumps(payload, sort_keys=True, allow_nan=False))
    assert round_tripped == payload
    assert response.response_digest_sha256 == canonical_response_digest(payload)
    repeat = call(source, list(records), with_lime=True)
    assert repeat.response_digest_sha256 == response.response_digest_sha256
    assert response.to_json(indent=None) != ""
    # A different request must produce a different digest.
    other = call(source, [records[1]])
    assert other.response_digest_sha256 != response.response_digest_sha256


def test_no_local_path_or_key_material_is_ever_disclosed(source, records, demo_bundle) -> None:
    response = call(source, list(records), with_lime=True)
    serialized = json.dumps(response.to_dict(), sort_keys=True)
    bundle_dir = Path(demo_bundle["bundle_dir"])
    assert str(bundle_dir) not in serialized
    assert str(Path(demo_bundle["trusted_root"])) not in serialized
    assert demo_bundle["signing_key"].decode("utf-8", "ignore") not in serialized
    artifact = response.to_dict()["artifact"]
    assert artifact["local_paths_disclosed"] is False
    assert artifact["bundle_dir_name"] == bundle_dir.name
    assert artifact["remote_or_url_source_supported"] is False
    assert artifact["signing_key_provided"] is True
    # The descriptor's own safe projection discloses only the basename.
    assert bundle_dir.name in str(source.safe_descriptor())
    assert str(bundle_dir.parent) not in str(source.safe_descriptor())


def test_governance_fields_are_read_only_and_always_false(source, records) -> None:
    payload = call(source, list(records)).to_dict()
    for block in (payload["governance"], payload["artifact"]["governance"]):
        assert block["approved_for_serving"] is False
        assert block["clinical_use_authorized"] is False
    assert payload["governance"]["http_surface_added"] is False
    assert payload["governance"]["provider_selection_changed"] is False
    assert payload["governance"]["real_data_execution_authorized"] is False
    assert payload["governance"]["gate_pt_p3"] == "CLOSED"
    assert payload["artifact"]["governance"]["serving_eligibility"] == "RESEARCH_ONLY"
    limitations = payload["limitations"]
    assert any("not" in line.lower() for line in limitations)
    assert any("synthetic" in line.lower() for line in limitations)
    # Every response carries the same non-clinical declaration, whatever it scored.
    assert any("clinical" in line.lower() for line in limitations)


# --------------------------------------------------------------------------- #
# ABSTAIN                                                                      #
# --------------------------------------------------------------------------- #


def test_registered_abstention_policy_produces_no_score(source, records) -> None:
    entry = get_model_entry(DEMO_MODEL_ID, "0.1.0")
    assert entry.abstain_on_missing_optional is True
    base = doc(records[0])
    assert "trestbps" in base["features"]
    document = mutate(
        without_feature(base, "trestbps"),
        missing_reasons={"trestbps": "not_provided"},
    )
    response = call(source, [document])
    assert response.status is ResearchFacadeStatus.ABSTAIN
    assert response.error is None
    outcome = response.outcomes[0]
    assert outcome.score is None
    assert outcome.shap is None
    assert outcome.lime is None
    assert outcome.abstention_reason == "registry_abstain_policy_optional_field_missing"
    assert outcome.missing_fields_with_reason == (("trestbps", "not_provided"),)
    assert outcome.evidence_level == EVIDENCE_LEVEL_SYNTHETIC_TEST
    assert outcome.unavailable_reason is None
    assert response.to_dict()["counts"]["ABSTAIN"] == 1
    assert response.to_dict()["capabilities"] is not None


def test_abstention_and_result_roll_up_to_abstain(source, records) -> None:
    base = doc(records[0])
    abstaining = mutate(
        without_feature(base, "trestbps"), missing_reasons={"trestbps": "not_provided"}
    )
    response = call(source, [abstaining, doc(records[1])])
    # ABSTAIN outranks SYNTHETIC_RESULT: a call is never reported as more
    # successful than its least successful record.
    assert response.status is ResearchFacadeStatus.ABSTAIN
    counts = response.to_dict()["counts"]
    assert counts["ABSTAIN"] == 1 and counts["SYNTHETIC_RESULT"] == 1


# --------------------------------------------------------------------------- #
# UNAVAILABLE                                                                  #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("key", "expected_code"),
    [
        (BLOCKED_PENDING_KEY, "model_entry_blocked_pending_authorization"),
        (BLOCKED_TIMING_KEY, "model_entry_blocked_source_timing_unverified"),
        (LOCKED_EXTERNAL_KEY, "model_entry_locked_external_target"),
    ],
)
def test_blocked_contracts_answer_unavailable_with_registered_versions(
    source, records, key, expected_code
) -> None:
    entry = RESEARCH_MODEL_REGISTRY[key]
    panel = REGISTERED_PANELS[entry.panel_id]
    response = call(
        source,
        list(records),
        route_id=entry.route_id,
        route_version=entry.route_version,
        model_id=entry.model_id,
        model_version=entry.model_version,
        panel_id=entry.panel_id,
        panel_version=panel.panel_version,
        panel_contract_sha256=panel.contract_sha256,
        dataset_id=entry.dataset_id,
    )
    assert response.status is ResearchFacadeStatus.UNAVAILABLE
    error = error_of(response)
    assert error.code == expected_code
    assert error.stage == "registry"
    assert response.outcomes == ()
    payload = response.to_dict()
    assert payload["route_id"] == entry.route_id
    assert payload["route_version"] == entry.route_version
    assert payload["model_id"] == entry.model_id
    assert payload["panel_contract_sha256"] == entry.panel_contract_sha256
    assert payload["entry_state"] == entry.entry_state
    assert payload["evidence_level"] == EVIDENCE_LEVEL_NOT_EVALUATED
    assert payload["capabilities"] is None
    assert payload["artifact"] is None
    assert payload["registry"]["registry_entry_sha256"]


def test_unavailable_answer_carries_registered_versions_and_no_capabilities(
    source, records
) -> None:
    entry = RESEARCH_MODEL_REGISTRY[BLOCKED_PENDING_KEY]
    panel = REGISTERED_PANELS[entry.panel_id]
    response = call(
        source,
        list(records),
        route_id=entry.route_id,
        route_version=entry.route_version,
        model_id=entry.model_id,
        model_version=entry.model_version,
        panel_id=entry.panel_id,
        panel_version=panel.panel_version,
        panel_contract_sha256=panel.contract_sha256,
        dataset_id=entry.dataset_id,
    )
    payload = response.to_dict()
    assert payload["protocol_id"] == entry.protocol_id
    assert payload["target_id"] == entry.target_id
    assert payload["source_family"] == entry.source_family
    # A blocked contract never reports what it *could* do.
    assert payload["evidence_level"] == EVIDENCE_LEVEL_NOT_EVALUATED


# --------------------------------------------------------------------------- #
# ERROR — unsupported models, versions and inputs                            #
# --------------------------------------------------------------------------- #


def test_unregistered_model_id_is_an_error(source, records) -> None:
    response = call(source, list(records), model_id="synth_unregistered_v1")
    assert response.status is ResearchFacadeStatus.ERROR
    error = error_of(response)
    assert error.code == "unknown_model_entry"
    assert error.stage == "registry"
    assert response.to_dict()["artifact"] is None


@pytest.mark.parametrize(
    ("field", "value", "expected_code"),
    [
        ("route_version", "99.0.0", "route_version_mismatch"),
        ("model_version", "9.9.9", "unknown_model_entry"),
        ("panel_version", "9.9.9", "panel_version_mismatch"),
        ("panel_contract_sha256", "0" * 64, "panel_contract_hash_mismatch"),
        ("panel_contract_sha256", "NOT-A-DIGEST", "panel_contract_hash_invalid"),
        ("operation", "clinical_serving", "facade_operation_not_supported"),
        ("operation", "real_bundle_inference", "facade_operation_not_supported"),
        (
            "request_schema_version",
            "cardioassist.ai.research_inference_request/v2",
            "request_schema_version_unsupported",
        ),
        ("route_id", "da_a1_basic_clinical_v1", "route_id_mismatch"),
        ("dataset_id", "DA-A1", "dataset_id_mismatch"),
    ],
)
def test_version_identifier_and_operation_mismatches(
    source, records, field, value, expected_code
) -> None:
    response = call(source, list(records), **{field: value})
    assert response.status is ResearchFacadeStatus.ERROR
    assert error_of(response).code == expected_code


def test_wrong_panel_for_the_model_is_refused(source, records) -> None:
    labs_panel = REGISTERED_PANELS["da_a2_resting_labs_v1"]
    response = call(
        source,
        list(records),
        panel_id=labs_panel.panel_id,
        panel_version=labs_panel.panel_version,
        panel_contract_sha256=labs_panel.contract_sha256,
    )
    assert response.status is ResearchFacadeStatus.ERROR
    assert error_of(response).code == "panel_id_mismatch"


@pytest.mark.parametrize(
    ("builder", "expected_codes"),
    [
        (lambda d: with_feature(d, "chol", 210.0), ["unregistered_feature_for_panel"]),
        (lambda d: with_feature(d, "fbs", 1), ["unregistered_feature_for_panel"]),
        (
            lambda d: with_feature(d, "age", "fifty-four"),
            ["invalid_numeric_value"],
        ),
        (
            lambda d: with_feature(d, "age", float("nan")),
            ["invalid_numeric_value"],
        ),
        (
            lambda d: with_feature(d, "age", 10**12),
            ["value_out_of_plausible_range", "shap_additivity_check_failed",
             "prediction_integrity_check_failed"],
        ),
        (
            lambda d: with_feature(d, "age", True),
            ["invalid_numeric_value", "value_out_of_plausible_range"],
        ),
        (lambda d: with_feature(d, "cp", 9), ["unknown_categorical_code"]),
        (
            lambda d: with_feature(d, "sex", "M"),
            ["invalid_categorical_type", "unknown_categorical_token"],
        ),
        (lambda d: mutate(d, units={**d["units"], "trestbps": "kPa"}), ["unit_mismatch"]),
        (lambda d: mutate(d, units={}), ["unit_keys_mismatch"]),
        (lambda d: with_feature(d, "stenosis_percent", 70.0),
         ["prohibited_leakage_or_wearable_field"]),
        (lambda d: with_feature(d, "syntax_score", 22.0),
         ["prohibited_leakage_or_wearable_field", "unregistered_feature_for_panel"]),
        (lambda d: with_feature(d, "ejection_fraction", 55.0),
         ["prohibited_leakage_or_wearable_field", "unregistered_feature_for_panel"]),
        (lambda d: with_feature(d, "spo2", 97.0), ["prohibited_leakage_or_wearable_field"]),
        (lambda d: with_feature(d, "wearable_step_count", 8000),
         ["prohibited_leakage_or_wearable_field", "unregistered_feature_for_panel"]),
        (lambda d: mutate(d, input_source="patient_wearable"),
         ["input_source_not_admissible", "unsupported_input_source"]),
        (lambda d: mutate(d, input_source="real_patient_record"),
         ["input_source_not_admissible", "unsupported_input_source"]),
        (lambda d: mutate(d, input_source="uploaded_image_or_ocr"),
         ["input_source_not_admissible", "unsupported_input_source"]),
        (lambda d: mutate(d, acquisition_stage="history_only"),
         ["acquisition_stage_precedence_violation"]),
        (lambda d: mutate(d, acquisition_stage="after_angiography"),
         ["acquisition_stage_invalid"]),
        (lambda d: mutate(d, acquisition_stage=""), ["acquisition_stage_invalid"]),
        (lambda d: mutate(d, panel_id="da_a2_resting_labs_v1"),
         ["record_panel_id_mismatch"]),
    ],
)
def test_invalid_records_are_refused_with_no_score(
    source, records, builder, expected_codes
) -> None:
    response = call(source, [builder(doc(records[0]))])
    assert response.status is ResearchFacadeStatus.ERROR
    error = error_of(response)
    assert error.code in expected_codes, error.code
    assert error.stage in PIPELINE_STAGES
    # No score is reported for a refused record, whether the refusal happened
    # while parsing the request or while evaluating the record.
    assert all(outcome.score is None for outcome in response.outcomes)
    assert all(
        outcome.shap is None or not outcome.shap.provided for outcome in response.outcomes
    )


def test_missing_required_field_is_refused_without_fabricated_default(source, records) -> None:
    base = doc(records[0])
    response = call(source, [without_feature(base, "age")])
    assert response.status is ResearchFacadeStatus.ERROR
    assert error_of(response).code == "missing_required_field"
    assert response.outcomes[0].score is None
    assert response.outcomes[0].shap is None


def test_omitted_optional_field_without_a_reason_is_refused(source, records) -> None:
    base = doc(records[0])
    response = call(source, [without_feature(base, "trestbps")])
    assert response.status is ResearchFacadeStatus.ERROR
    assert error_of(response).code == "missing_reason_mismatch"


@pytest.mark.parametrize(
    "provenance_change",
    [
        ({"generator_id": "someone_elses_loader"}),
        ({"seed": "not-an-int"}),
        ({"fixture_ref": "../outside"}),
    ],
)
def test_forged_synthetic_provenance_is_refused(source, records, provenance_change) -> None:
    base = doc(records[0])
    response = call(
        source,
        [
            mutate(
                base,
                synthetic_provenance={**base["synthetic_provenance"], **provenance_change},
            )
        ],
    )
    assert response.status is ResearchFacadeStatus.ERROR
    assert error_of(response).code in {
        "synthetic_provenance_generator_not_admissible",
        "synthetic_provenance_seed_invalid",
        "synthetic_provenance_fixture_ref_invalid",
    }
    missing = call(source, [without(base, "synthetic_provenance")])
    assert error_of(missing).code == "synthetic_provenance_missing"
    wrong_declaration = call(
        source,
        [
            mutate(
                base,
                synthetic_provenance={
                    **base["synthetic_provenance"],
                    "declaration": "real_patient_derived_data",
                },
            )
        ],
    )
    assert error_of(wrong_declaration).code == "synthetic_provenance_declaration_unknown"


def test_provenance_constant_is_the_registered_one() -> None:
    assert SYNTHETIC_PROVENANCE_DECLARATION == "DELIBERATELY_FABRICATED_SYNTHETIC_FIXTURE"
    provenance = SyntheticFixtureProvenance(
        declaration=SYNTHETIC_PROVENANCE_DECLARATION,
        fixture_ref="synth-fixture-da-a2-resting",
        generator_id="ai.research_routes.build_synthetic_uci45_resting_cohort",
        seed=DEMO_SEED,
    )
    parsed = parse_synthetic_provenance(
        {
            "declaration": provenance.declaration,
            "fixture_ref": provenance.fixture_ref,
            "generator_id": provenance.generator_id,
            "seed": provenance.seed,
        }
    )
    assert parsed == provenance


def test_batch_rules_are_enforced(source, records) -> None:
    first, second = doc(records[0]), doc(records[1])
    duplicate = call(source, [first, first])
    assert duplicate.status is ResearchFacadeStatus.ERROR
    assert error_of(duplicate).code == "duplicate_record_ref"

    empty = call(source, [])
    assert error_of(empty).code == "empty_record_set"

    over_ceiling = [
        mutate(doc(records[0]), record_ref=f"rec{i:03d}") for i in range(MAX_RECORDS_CEILING + 1)
    ]
    response = call(source, over_ceiling)
    assert response.status is ResearchFacadeStatus.ERROR
    assert error_of(response).code == "record_count_exceeds_ceiling"
    assert response.outcomes == ()

    for entry in RESEARCH_MODEL_REGISTRY.values():
        assert 1 <= entry.max_records_per_invocation <= MAX_RECORDS_CEILING


def test_exploratory_threshold_is_validated_but_never_clinically_claimed(source, records) -> None:
    for bad in (0.0, 1.0, -1.0, float("nan"), "0.5", True):
        response = run_offline_research_inference_from_document(
            mutate(_base_document([doc(records[0])]), exploratory_threshold=bad),
            model_source=source,
        )
        assert response.status is ResearchFacadeStatus.ERROR, bad
        assert error_of(response).code == "exploratory_threshold_invalid", bad

    response = call(source, [doc(records[0])], exploratory_threshold=0.9)
    assert response.status is ResearchFacadeStatus.SYNTHETIC_RESULT
    score = response.outcomes[0].score
    assert score.exploratory_threshold == 0.9
    assert score.threshold_clinically_validated is False


def test_explainability_options_are_strictly_typed() -> None:
    # Absence of a request is never filled in with defaults.
    assert ExplainabilityOptions().to_lime_config() is None
    assert ExplainabilityOptions(include_lime=False).to_lime_config() is None
    for kwargs in (
        {"lime_reference_scheme": "made_up"},
        {"lime_num_perturbations": 10**9},
        {"lime_num_perturbations": 8},
        {"lime_seed": -5},
    ):
        with pytest.raises(ResearchRegistryError) as excinfo:
            ExplainabilityOptions(include_lime=True, **kwargs).to_lime_config()
        assert excinfo.value.code == "explainability_options_invalid", kwargs
    config = ExplainabilityOptions(
        include_lime=True, lime_num_perturbations=64, lime_seed=7
    ).to_lime_config()
    assert config is not None
    assert config.num_perturbations == 64 and config.seed == 7


def test_lime_ceiling_violation_is_a_typed_error_at_the_boundary(source, records) -> None:
    response = call(
        source,
        [doc(records[0])],
        explainability={
            "include_shap": True,
            "include_lime": True,
            "lime_num_perturbations": 10**9,
        },
    )
    assert response.status is ResearchFacadeStatus.ERROR
    error = error_of(response)
    assert error.code == "explainability_options_invalid"
    # Refused as a request error: no artifact is opened for a malformed
    # explanation request, and no partial (SHAP-only) result is returned.
    assert error.stage == "request"
    assert response.outcomes == ()
    assert response.to_dict()["artifact"] is None


def test_caller_cannot_supply_an_inline_or_remote_artifact(source, records) -> None:
    document = mutate(_base_document([doc(records[0])]), model_source="inline_artifact")
    response = run_offline_research_inference_from_document(document, model_source=source)
    assert response.status is ResearchFacadeStatus.ERROR
    assert error_of(response).code == "unexpected_request_key"


# --------------------------------------------------------------------------- #
# Untrusted and forged artifacts                                               #
# --------------------------------------------------------------------------- #


def _copy_bundle(source_dir: Path, destination: Path) -> Path:
    target = ensure_private_directory(destination)
    for item in sorted(Path(source_dir).iterdir()):
        copied = target / item.name
        shutil.copy2(item, copied)
        protect_private_file(copied)
    return target


def test_bundle_outside_the_trusted_root_is_refused(demo_bundle, records, tmp_path) -> None:
    elsewhere = ensure_private_directory(tmp_path / "elsewhere")
    moved = _copy_bundle(
        Path(demo_bundle["bundle_dir"]), elsewhere / Path(demo_bundle["bundle_dir"]).name
    )
    response = call(
        LocalSyntheticBundleSource(
            bundle_dir=moved,
            trusted_local_root=Path(demo_bundle["trusted_root"]),
            signing_key=demo_bundle["signing_key"],
        ),
        list(records),
    )
    assert response.status is ResearchFacadeStatus.ERROR
    error = error_of(response)
    assert error.stage == "artifact"
    assert response.outcomes == ()
    assert response.to_dict()["capabilities"] is None


def test_tampered_bundle_member_is_refused_before_deserialization(
    tmp_path, demo_bundle, records
) -> None:
    private = ensure_private_directory(tmp_path / "trusted_tampered")
    tampered = _copy_bundle(
        Path(demo_bundle["bundle_dir"]), private / "tampered_bundle"
    )
    for name in ("preprocessing.json", "model.joblib", "calibration.json"):
        target = tampered / name
        target.write_bytes(target.read_bytes() + b" ")
        protect_private_file(target)
        response = call(
            LocalSyntheticBundleSource(
                bundle_dir=tampered,
                trusted_local_root=private,
                signing_key=demo_bundle["signing_key"],
            ),
            list(records),
        )
        assert response.status is ResearchFacadeStatus.ERROR, name
        assert response.outcomes == (), name
        assert response.to_dict()["artifact"] is None, name
        # Nothing was deserialized, so no model-derived value can appear.
        assert "raw_model_score" not in json.dumps(response.to_dict()), name


def test_forged_manifest_governance_is_refused(tmp_path, demo_bundle, records) -> None:
    """Editing any HMAC-covered manifest field breaks producer authentication.

    There is no path by which a caller can relabel a bundle as serving-eligible
    or clinically authorized: the digest check fails first and nothing is
    deserialized.
    """
    private = ensure_private_directory(tmp_path / "trusted_forged")
    forged = _copy_bundle(Path(demo_bundle["bundle_dir"]), private / "forged_bundle")
    manifest_path = forged / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["eligibility"] = {
        **manifest["eligibility"],
        "approved_for_serving": True,
        "clinical_use_authorized": True,
        "execution_mode": "PRODUCTION",
    }
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    protect_private_file(manifest_path)
    response = call(
        LocalSyntheticBundleSource(
            bundle_dir=forged,
            trusted_local_root=private,
            signing_key=demo_bundle["signing_key"],
        ),
        list(records),
    )
    assert response.status is ResearchFacadeStatus.ERROR
    assert error_of(response).stage == "artifact"
    assert response.outcomes == ()


def test_stripped_producer_attestation_is_refused(tmp_path, demo_bundle, records) -> None:
    private = ensure_private_directory(tmp_path / "trusted_noattest")
    stripped = _copy_bundle(Path(demo_bundle["bundle_dir"]), private / "no_attestation")
    manifest_path = stripped / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("local_producer_attestation", None)
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    protect_private_file(manifest_path)
    response = call(
        LocalSyntheticBundleSource(
            bundle_dir=stripped,
            trusted_local_root=private,
            signing_key=demo_bundle["signing_key"],
        ),
        list(records),
    )
    assert response.status is ResearchFacadeStatus.ERROR
    assert response.outcomes == ()


def test_foreign_producer_key_is_refused(demo_bundle, records, tmp_path) -> None:
    key_dir = ensure_private_directory(tmp_path / "other_keys")
    foreign_key = get_or_create_local_signing_key(key_dir / "foreign_bundle_hmac_v1.key")
    response = call(
        LocalSyntheticBundleSource(
            bundle_dir=Path(demo_bundle["bundle_dir"]),
            trusted_local_root=Path(demo_bundle["trusted_root"]),
            signing_key=foreign_key,
        ),
        list(records),
    )
    assert response.status is ResearchFacadeStatus.ERROR
    assert error_of(response).code in {
        "untrusted_bundle_producer_signature",
        "bundle_verification_failed",
    }
    assert response.outcomes == ()


def test_absent_signing_key_never_authenticates_for_deserialization(
    demo_bundle, records
) -> None:
    response = call(
        LocalSyntheticBundleSource(
            bundle_dir=Path(demo_bundle["bundle_dir"]),
            trusted_local_root=Path(demo_bundle["trusted_root"]),
            signing_key=None,
        ),
        list(records),
    )
    assert response.status is ResearchFacadeStatus.ERROR
    assert error_of(response).stage == "artifact"
    assert response.to_dict()["artifact"] is None
    assert response.outcomes == ()


def test_capability_claims_are_derived_from_the_artifact_never_the_request(
    source, records
) -> None:
    fields = set(ResearchInferenceRequest.__dataclass_fields__)
    assert fields == {
        "request_schema_version",
        "operation",
        "route_id",
        "route_version",
        "model_id",
        "model_version",
        "panel_id",
        "panel_version",
        "panel_contract_sha256",
        "dataset_id",
        "records",
        "exploratory_threshold",
        "explainability",
        "model_source",
    }
    assert not any("calibrat" in name for name in fields)
    assert not any(
        name in {"approved_for_serving", "clinical_use_authorized", "serving_eligibility"}
        for name in fields
    )
    payload = call(source, list(records)).to_dict()
    assert payload["capabilities"]["calibration"]["supported"] is True
    assert payload["capabilities"]["explainability"]["lime"]["supported"] is True
    assert payload["capabilities"]["explainability"]["lime"]["computed"] is False


def _artifact_inputs(demo_bundle: dict) -> tuple[dict, object, dict]:
    """(manifest, calibrator, shap background) for the real demo bundle."""
    from ai.calibration import OofLogisticCalibrator

    bundle = Path(demo_bundle["bundle_dir"])
    manifest = copy.deepcopy(dict(demo_bundle["packaged"].manifest))
    calibrator = OofLogisticCalibrator.from_json_dict(
        json.loads((bundle / "calibration.json").read_text(encoding="utf-8"))
    )
    background = json.loads((bundle / "shap_background.json").read_text(encoding="utf-8"))
    return manifest, calibrator, dict(background)


def test_capabilities_are_derived_from_the_artifact_and_never_assumed(
    demo_bundle,
) -> None:
    """Every capability claim is re-derived from artifact content.

    These are the ways a bundle could try to look more capable than it is, each
    patched in exactly one place; the derivation must refuse or downgrade, and
    never report a capability or a provenance the artifact cannot back.
    """
    from ai.research_registry import derive_artifact_capabilities

    entry = RESEARCH_MODEL_REGISTRY[DEMO_KEY]
    manifest, calibrator, background = _artifact_inputs(demo_bundle)

    def derive(mutate_manifest=None, mutate_background=None):
        patched = copy.deepcopy(manifest)
        if mutate_manifest is not None:
            mutate_manifest(patched)
        document = copy.deepcopy(background)
        if mutate_background is not None:
            mutate_background(document)
        return derive_artifact_capabilities(
            patched,
            entry=entry,
            calibrator=calibrator,
            background_document=document,
            model_family="l2_logistic_regression",
        )

    honest = derive()
    assert honest.calibration_supported is True
    assert honest.shap_supported is True
    assert honest.lime_supported is True
    assert honest.shap_background_panel_bound is True
    assert honest.shap_background_sample_count == 24

    for label, mutation in (
        (
            "background claims to be real data",
            lambda document: document.update(
                {"privacy": {**document["privacy"], "synthetic_only": False}}
            ),
        ),
        (
            "background is bound to another panel",
            lambda document: document.update({"panel_id": "da_a2_resting_labs_v1"}),
        ),
        (
            "background hash does not match",
            lambda document: document.update({"panel_contract_sha256": "0" * 64}),
        ),
        (
            "background row count disagrees with the matrix",
            lambda document: document.update({"n_background_rows": 3}),
        ),
        (
            "background privacy block removed",
            lambda document: document.pop("privacy"),
        ),
    ):
        with pytest.raises(ResearchRegistryError) as excinfo:
            derive(mutate_background=mutation)
        assert excinfo.value.code == "artifact_shap_background_provenance_invalid", label

    # A missing or downgraded explanation capability on an executable entry is an
    # integrity failure: the entry was reviewed against an artifact that has it.
    with pytest.raises(ResearchRegistryError) as excinfo:
        derive(
            mutate_manifest=lambda patched: patched["model"]["explainability"].update(
                {"capability": "partial"}
            )
        )
    assert excinfo.value.code == "artifact_capability_declaration_mismatch"

    # A calibration status the artifact does not carry downgrades the report
    # instead of raising: the raw score stays reportable, honestly labelled.
    downgraded = derive(
        mutate_manifest=lambda patched: patched["model"].update(
            {"calibration_status": "not_calibrated"}
        )
    )
    assert downgraded.calibration_supported is False
    assert (
        downgraded.unsupported_calibration_reason
        == "artifact_declares_no_supported_calibration_status"
    )

    # The method must match the registered method for the model family.
    with pytest.raises(ResearchRegistryError) as excinfo:
        derive(
            mutate_manifest=lambda patched: patched["model"]["explainability"].update(
                {"method": "kernel_shap_explainer"}
            )
        )
    assert excinfo.value.code == "artifact_explainability_method_mismatch"


def test_unfitted_calibrator_is_reported_as_absent_not_relabelled(demo_bundle) -> None:
    """An identity/constant-fallback calibrator never produces a calibrated label."""
    import dataclasses

    from ai.calibration import OofLogisticCalibrator
    from ai.research_registry import derive_artifact_capabilities

    entry = RESEARCH_MODEL_REGISTRY[DEMO_KEY]
    manifest, calibrator, background = _artifact_inputs(demo_bundle)
    identity = dataclasses.replace(calibrator, status="IDENTITY_CONSTANT_FALLBACK")
    capabilities = derive_artifact_capabilities(
        manifest,
        entry=entry,
        calibrator=identity,
        background_document=background,
        model_family="l2_logistic_regression",
    )
    assert capabilities.calibration_supported is False
    assert capabilities.unsupported_calibration_reason == "calibrator_status_identity_constant_fallback"
    assert capabilities.oof_brier_after is None or capabilities.oof_brier_before is not None
    # An unregistered calibrator status is equally non-reportable.
    unregistered = dataclasses.replace(calibrator, status="SOMETHING_NEW")
    assert (
        derive_artifact_capabilities(
            manifest,
            entry=entry,
            calibrator=unregistered,
            background_document=background,
            model_family="l2_logistic_regression",
        ).unsupported_calibration_reason
        == "calibrator_status_unregistered"
    )
    assert OofLogisticCalibrator is not None


def test_real_provenance_or_foreign_profile_artifact_is_refused_before_load(
    demo_bundle,
) -> None:
    """The reused CLI provenance gate is the facade's first artifact check.

    These manifests are the *verified* bundle's own document with one field
    changed, which is exactly what the gate must catch before any
    deserialization: a real-provenance artifact and a non-research execution
    profile are both refused here, and the facade maps the refusal to ``ERROR``
    without echoing the gate's message.
    """
    from ai.cli import assert_cli_predict_supported
    from ai.errors import BundleIntegrityError

    manifest = copy.deepcopy(dict(demo_bundle["packaged"].manifest))
    assert_cli_predict_supported(manifest)  # the honest artifact passes
    for label, patch, expected_code in (
        (
            "synthetic-only declaration removed",
            lambda m: m["eligibility"].update({"synthetic_only": False}),
            "cli_real_provenance_bundle_not_supported",
        ),
        (
            "eligibility block absent",
            lambda m: m.pop("eligibility"),
            "cli_real_provenance_bundle_not_supported",
        ),
        (
            "real research-authorization context",
            lambda m: m.update({"research_authorization": {"experiment_id": "X"}}),
            "cli_real_provenance_bundle_not_supported",
        ),
        (
            "non-research execution profile",
            lambda m: m["model"].update({"execution_profile": "PRODUCTION_V1"}),
            "cli_execution_profile_not_supported",
        ),
    ):
        patched = copy.deepcopy(manifest)
        patch(patched)
        with pytest.raises(BundleIntegrityError) as excinfo:
            assert_cli_predict_supported(patched)
        assert excinfo.value.code == expected_code, label


def test_identity_gate_refuses_a_bundle_that_is_not_the_registered_one(
    demo_bundle,
) -> None:
    """A correctly produced bundle for a *different* identity is refused."""
    from ai.research_registry import assert_artifact_identity

    manifest = copy.deepcopy(dict(demo_bundle["packaged"].manifest))
    entry = RESEARCH_MODEL_REGISTRY[DEMO_KEY]
    assert assert_artifact_identity(manifest, entry) == "l2_logistic_regression"
    for label, path, value, expected_code in (
        (
            "model id",
            ("model", "model_id"),
            "synth_something_else_v1",
            "artifact_model_id_mismatch",
        ),
        (
            "model version",
            ("model", "model_version"),
            "9.9.9",
            "artifact_model_version_mismatch",
        ),
        (
            "protocol",
            ("model", "protocol_id"),
            "CAI-AI7-SYNTHETIC-OTHER-V9",
            "artifact_protocol_id_mismatch",
        ),
        (
            "panel hash",
            ("panel_contract", "contract_sha256"),
            "0" * 64,
            "artifact_panel_hash_mismatch",
        ),
        (
            "feature order",
            ("panel_contract", "ordered_feature_names"),
            ["sex", "age", "cp"],
            "artifact_feature_order_mismatch",
        ),
        (
            "development cohort is not marked synthetic",
            ("target", "development_cohort_id"),
            "real:uci-45",
            "artifact_development_cohort_not_marked_synthetic",
        ),
        (
            "pooled cohorts",
            ("target", "pooled_cohorts"),
            True,
            "artifact_pooled_cohorts_rejected",
        ),
        (
            "serving claim",
            ("eligibility", "approved_for_serving"),
            True,
            "artifact_serving_claim_rejected",
        ),
        (
            "execution profile",
            ("model", "execution_profile"),
            "PRODUCTION",
            "artifact_execution_profile_mismatch",
        ),
        (
            "model family outside the entry",
            ("model", "selected_model_family"),
            "unreviewed_gradient_boosting",
            "artifact_model_family_not_allowed",
        ),
    ):
        patched = copy.deepcopy(manifest)
        node = patched
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value
        with pytest.raises(ResearchRegistryError) as excinfo:
            assert_artifact_identity(patched, entry)
        assert excinfo.value.code == expected_code, (label, excinfo.value.code)
    # An empty manifest is a refusal, never a permissive default.
    with pytest.raises(ResearchRegistryError):
        assert_artifact_identity({}, entry)


# --------------------------------------------------------------------------- #
# Redaction, typing and boundary guarantees                                   #
# --------------------------------------------------------------------------- #


def test_refusal_messages_are_always_registered_static_strings(source, records) -> None:
    responses = [
        call(source, list(records), model_id="synth_unregistered_v1"),
        call(source, [mutate(doc(records[0]), units={**doc(records[0])["units"], "trestbps": "kPa"})]),
        call(source, [{"record_ref": "x", "synthetic": True}]),
        call(source, [mutate(doc(records[0]), input_source="real_patient_record")]),
        call(source, []),
    ]
    messages = []
    for response in responses:
        payload = response.to_dict()
        if payload["error"]:
            messages.append(payload["error"]["message"])
        for record in payload["records"]:
            if record["error"]:
                messages.append(record["error"]["message"])
    assert messages
    for message in messages:
        assert is_registered_static_error_message(message), message
        for needle in ("fifty-four", "kPa", "real_patient_record", "/", "\\"):
            assert needle not in message


def test_error_detail_never_echoes_a_submitted_field_name(source, records) -> None:
    sneaky = "C:\\Users\\victim\\Desktop\\secret.json"
    document = with_feature(doc(records[0]), sneaky, 1.0)
    response = call(source, [document])
    assert response.status is ResearchFacadeStatus.ERROR
    detail = error_of(response)
    assert detail.code == "unregistered_feature_for_panel"
    assert detail.field_name is None
    assert sneaky not in json.dumps(response.to_dict())


def test_error_detail_is_typed_immutable_and_cannot_carry_text() -> None:
    detail = FacadeErrorDetail(
        code="unit_mismatch",
        message="A supplied unit does not match the registered unit for that field.",
        field_name="trestbps",
        stage="record",
    )
    assert detail.to_dict() == {
        "code": "unit_mismatch",
        "message": "A supplied unit token does not match the registered unit for that field.",
        "field": "trestbps",
        "stage": "record",
        "input_values_echoed": False,
        "local_paths_echoed": False,
    }
    # The stored message is always the registered sentence for the code: a
    # caller (or a bug) cannot smuggle exception text into a refusal.
    smuggled = FacadeErrorDetail(
        code="unit_mismatch",
        message="/home/user/private/bundle/model.joblib exploded on trestbps=mmHg",
        field_name="trestbps",
        stage="record",
    )
    assert smuggled.message == detail.message
    assert smuggled.to_dict() == detail.to_dict()
    # An unregistered code or stage falls back instead of being echoed.
    weird = FacadeErrorDetail(
        code="../../etc/passwd", message="x", field_name=None, stage="whatever"
    )
    assert weird.code == GENERIC_ERROR_CODE
    assert weird.stage == PIPELINE_STAGES[-1]
    assert is_registered_static_error_message(weird.message)
    # A detail with no field name says so explicitly rather than omitting the
    # key, so "nothing echoed" is distinguishable from "not reported".
    assert FacadeErrorDetail(
        code="unit_mismatch", message="", field_name=None, stage="request"
    ).to_dict()["field"] is None
    with pytest.raises(FrozenInstanceError):
        detail.stage = "prediction"  # type: ignore[misc]


def test_the_facade_boundary_never_raises(source) -> None:
    for payload in ({}, {"records": []}, None, "not-a-mapping", [{}], 7):
        response = run_offline_research_inference_from_document(payload, model_source=source)
        assert response.status in set(ResearchFacadeStatus)
        assert response.error is not None
        assert response.outcomes == ()
        json.dumps(response.to_dict(), allow_nan=False)


def test_typed_object_api_works_without_a_document(source, records) -> None:
    request = ResearchInferenceRequest(
        request_schema_version=REQUEST_SCHEMA_VERSION,
        operation=FACADE_OPERATION,
        route_id=DEMO_ROUTE_ID,
        route_version=RESEARCH_MODEL_REGISTRY[DEMO_KEY].route_version,
        model_id=DEMO_MODEL_ID,
        model_version="0.1.0",
        panel_id=DEMO_PANEL_ID,
        panel_version=REGISTERED_PANELS[DEMO_PANEL_ID].panel_version,
        panel_contract_sha256=REGISTERED_PANELS[DEMO_PANEL_ID].contract_sha256,
        dataset_id=DEMO_DATASET_ID,
        records=_demo_records(),
        exploratory_threshold=0.5,
        explainability=ExplainabilityOptions(),
        model_source=source,
    )
    response = run_offline_research_inference(request)
    assert response.status is ResearchFacadeStatus.SYNTHETIC_RESULT
    parsed = parse_inference_request(
        _base_document(
            list(records),
            explainability={"include_shap": True, "include_lime": False},
        ),
        model_source=source,
    )
    documented = run_offline_research_inference(parsed).to_dict()
    typed = response.to_dict()
    # Same record and same artifact: identical numbers, explanations and
    # capabilities through either entry point (the request summaries may differ
    # only in caller-supplied option defaults).
    assert typed["records"] == documented["records"]
    assert typed["capabilities"] == documented["capabilities"]
    assert typed["registry"] == documented["registry"]
    assert isinstance(request.records[0], ResearchFeatureRecord)
    assert isinstance(request.records[0].provenance, SyntheticFixtureProvenance)


def test_status_enum_is_exactly_the_four_registered_results() -> None:
    assert {status.value for status in ResearchFacadeStatus} == {
        "SYNTHETIC_RESULT",
        "ABSTAIN",
        "UNAVAILABLE",
        "ERROR",
    }
    assert ResearchFacadeStatus.SYNTHETIC_RESULT.produced_a_score is True
    for status in (
        ResearchFacadeStatus.ABSTAIN,
        ResearchFacadeStatus.UNAVAILABLE,
        ResearchFacadeStatus.ERROR,
    ):
        assert status.produced_a_score is False


# --------------------------------------------------------------------------- #
# Malformed-input redaction: the no-echo guarantee under hostile input         #
# --------------------------------------------------------------------------- #

#: Markers that must never reappear anywhere in a refusal payload. Each one is
#: deliberately placed where a naive implementation would `str()`-echo the raw
#: value (a summary built from `getattr`, or from `record.get("record_ref")`).
SECRET_STRINGS = (
    "synthetic-fake-secret",
    "secret_bundle",
    "nested-secret",
    "hostile-introspection",
    "C:\\Users\\victim",
    "/home/leak",
    "..\\..\\windows",
)


class Hostile:
    """Any attribute or item access raises: introspection must not be attempted."""

    def __getattr__(self, name: str):
        raise RuntimeError("hostile-introspection")

    def __getitem__(self, key):
        raise RuntimeError("hostile-introspection")

    def to_dict(self):
        raise RuntimeError("hostile-introspection")

    def safe_descriptor(self):
        raise RuntimeError("hostile-introspection")


def _assert_clean(response) -> dict:
    """Serialize a refusal and assert it carries neither secrets nor NaN/Infinity."""
    payload = response.to_dict()
    text = json.dumps(payload, allow_nan=False, ensure_ascii=True, sort_keys=True)
    for needle in SECRET_STRINGS:
        assert needle not in text, f"{needle!r} leaked into {text[:400]}"
    for needle in ("NaN", "Infinity"):
        assert needle not in text, f"{needle} reached the serializer"
    return payload


def test_a_path_shaped_record_ref_in_a_refused_document_is_never_echoed(source, records) -> None:
    """Reviewer repro 1: wrong schema version + a Windows-path ``record_ref``."""
    document = mutate(
        _base_document(
            [
                {
                    "record_ref": "C:\\synthetic-fake-secret\\key.txt",
                    "note": "nested-secret",
                }
            ]
        ),
        request_schema_version="cardioassist.ai.research_inference_request/v0",
    )
    assert document["records"][0]["record_ref"].startswith("C:\\")
    response = run_offline_research_inference_from_document(document, model_source=source)
    assert response.status is ResearchFacadeStatus.ERROR
    detail = error_of(response)
    assert detail.code == "request_schema_version_unsupported"
    assert detail.stage == "request"
    assert response.outcomes == ()
    payload = _assert_clean(response)
    summary = payload["request_summary"]
    # Structure is reported, values are not: one refused record, nothing echoed.
    assert summary["record_count"] == 1
    assert summary["record_refs"] == []
    assert summary["record_refs_redacted"] == 1
    assert isinstance(summary["redacted_fields"], list)
    assert summary["unvalidated_values_redacted"] is True
    assert is_registered_static_error_message(detail.message)


def test_a_nested_mapping_record_ref_is_typed_error_and_never_reflected(
    source, records
) -> None:
    """Reviewer repro 2: a nested object where a reference string belongs."""
    document = _base_document([records[0]])
    document["records"][0]["record_ref"] = {
        "path": "/home/leak/secret_bundle.json",
        "note": "nested-secret",
    }
    response = run_offline_research_inference_from_document(document, model_source=source)
    assert response.status is ResearchFacadeStatus.ERROR
    detail = error_of(response)
    assert detail.code == "invalid_record_ref"
    payload = _assert_clean(response)
    assert payload["request_summary"]["record_refs"] == []
    assert payload["request_summary"]["record_refs_redacted"] == 1
    assert canonical_response_digest(payload)


def test_an_oversized_or_oddly_shaped_record_list_is_bounded(source, records) -> None:
    """No per-record work, and no introspection, before the ceiling refusal."""
    document = mutate(
        _base_document([doc(records[0])]),
        records=[Hostile() for _ in range(2048)],
    )
    response = run_offline_research_inference_from_document(document, model_source=source)
    assert response.status is ResearchFacadeStatus.ERROR
    assert error_of(response).code == "record_count_exceeds_ceiling"
    payload = _assert_clean(response)
    assert 0 <= payload["request_summary"]["record_count"] <= MAX_RECORDS_CEILING + 1
    assert payload["request_summary"]["record_refs"] == []

    for odd in ({"path": "/home/leak/secret_bundle.json"}, "C:\\synthetic-fake-secret", 7, None):
        refused = run_offline_research_inference_from_document(
            mutate(_base_document([doc(records[0])]), records=odd), model_source=source
        )
        assert refused.status is ResearchFacadeStatus.ERROR
        assert error_of(refused).code == "empty_record_set"
        clean = _assert_clean(refused)
        assert clean["request_summary"]["record_count"] == 0


def test_a_path_shaped_or_unregistered_model_identity_is_not_echoed(source, records) -> None:
    """Reviewer repro 3: valid-shaped document, unvalidated identifiers."""
    for field, value in (
        ("model_id", "/home/leak/secret_bundle.json"),
        ("model_id", "C:\\synthetic-fake-secret\\model.json"),
        ("model_version", "1.0.0-nested-secret"),
        ("route_id", "..\\..\\windows\\route"),
        ("panel_id", "/home/leak/panel"),
        ("panel_contract_sha256", "z" * 64),
        ("dataset_id", "DA-../../leak"),
        ("request_schema_version", "v9-nested-secret"),
    ):
        response = call(source, [doc(records[0])], **{field: value})
        assert response.status is ResearchFacadeStatus.ERROR, (field, response.status)
        payload = _assert_clean(response)
        summary = payload["request_summary"]
        assert summary[field] is None, (field, summary[field])
        assert field in summary["redacted_fields"]
        # The registered counterpart of the pair is withheld too, so a refusal
        # never leaks "this half is real" as an oracle.
        if field == "model_id":
            assert summary["model_version"] is None
            assert "model_version" in summary["redacted_fields"]
        # A refused request never reaches the artifact, whatever the summary says.
        assert payload["artifact"] is None and response.outcomes == ()

    # A guessed-but-well-formed id is withheld for the same reason: it is not
    # registered, so echoing it would only confirm the caller's guess.
    refused = call(source, [doc(records[0])], model_id="synth_unregistered_v1")
    assert _assert_clean(refused)["request_summary"]["model_id"] is None


def test_ordinary_registered_identifiers_and_refs_are_still_echoed(source, records) -> None:
    """The fix must not blind the summary: valid ids keep their diagnostic value."""
    parsed = parse_inference_request(_base_document(list(records)), model_source=source)
    summary = build_request_summary(parsed)
    entry = RESEARCH_MODEL_REGISTRY[DEMO_KEY]
    panel = REGISTERED_PANELS[DEMO_PANEL_ID]
    assert summary["request_schema_version"] == REQUEST_SCHEMA_VERSION
    assert summary["operation"] == FACADE_OPERATION
    assert summary["route_id"] == DEMO_ROUTE_ID
    assert summary["route_version"] == entry.route_version
    assert summary["model_id"] == DEMO_MODEL_ID
    assert summary["model_version"] == entry.model_version
    assert summary["panel_id"] == DEMO_PANEL_ID
    assert summary["panel_version"] == panel.panel_version
    assert summary["panel_contract_sha256"] == panel.contract_sha256
    assert summary["dataset_id"] == DEMO_DATASET_ID
    assert summary["record_count"] == len(records)
    assert summary["record_refs"] == [record.record_ref for record in records]
    assert all(SAFE_RECORD_REF_RE.fullmatch(ref) for ref in summary["record_refs"])
    assert summary["redacted_fields"] == []
    assert summary["record_refs_redacted"] == 0
    assert summary["unvalidated_values_redacted"] is False
    assert summary["request_type_accepted"] is True
    assert summary["exploratory_threshold"] == 0.5
    # The same projection the response carries, and a success is not more
    # permissive than it used to be: only the redaction bookkeeping is added.
    response = run_offline_research_inference(parsed)
    assert response.status is ResearchFacadeStatus.SYNTHETIC_RESULT
    assert response.to_dict()["request_summary"] == summary
    assert summary["model_source"]["source_type_accepted"] is True
    assert summary["explainability"]["options_type_accepted"] is True


def test_a_malformed_typed_request_still_serializes_to_value_free_json(
    source, records
) -> None:
    """Reviewer repro 4: ``to_json()`` on a request that never passed the grammar."""
    hostile_ref = "C:\\synthetic-fake-secret\\key.txt"
    request = ResearchInferenceRequest(
        request_schema_version="v9-nested-secret",
        operation="not_an_operation",
        route_id="/home/leak/secret_bundle.json",
        route_version="../..",
        model_id="evil",
        model_version="1",
        panel_id="P",
        panel_version="p",
        panel_contract_sha256="zz",
        dataset_id="DA-!!nested-secret",
        records=(
            dataclasses.replace(parse_feature_record(doc(records[0])), record_ref=hostile_ref),
        ),
        exploratory_threshold=float("nan"),
        model_source=source,
    )
    summary_text = json.dumps(
        request.to_safe_dict(), sort_keys=True, ensure_ascii=True, allow_nan=False
    )
    for needle in SECRET_STRINGS:
        assert needle not in summary_text
    assert "NaN" not in summary_text
    summary = json.loads(summary_text)
    assert summary["record_refs"] == []
    assert summary["record_refs_redacted"] == 1
    assert summary["unvalidated_values_redacted"] is True
    assert summary["request_type_accepted"] is True
    assert summary["exploratory_threshold"] is None
    assert sorted(summary["redacted_fields"]) == [
        "dataset_id",
        "model_id",
        "model_version",
        "operation",
        "panel_contract_sha256",
        "panel_id",
        "panel_version",
        "request_schema_version",
        "route_id",
        "route_version",
    ]
    # The same request through the typed entry point is a typed refusal whose
    # whole payload — not only its summary — is JSON-clean and value-free.
    response = run_offline_research_inference(request)
    assert response.status is ResearchFacadeStatus.ERROR
    assert response.outcomes == ()
    assert response.binding is None
    text = response.to_json()
    for needle in SECRET_STRINGS:
        assert needle not in text
    payload = json.loads(text)
    assert payload["request_summary"] == summary
    assert payload["artifact"] is None
    assert is_registered_static_error_message(payload["error"]["message"])
    # A response built from a summary of a hostile object also serializes: the
    # fallback is reached before the serializer, not by chance.
    orphan = ResearchInferenceResponse(
        status=ResearchFacadeStatus.ERROR,
        binding=None,
        capabilities=None,
        outcomes=(),
        artifact=None,
        error=FacadeErrorDetail(
            code=GENERIC_ERROR_CODE, message="", field_name=None, stage="request"
        ),
        request_summary=safe_document_summary(Hostile()),
        provenance={},
        governance={},
        limitations=(),
    )
    assert json.loads(orphan.to_json())["request_summary"]["unvalidated_values_redacted"] is True
    assert canonical_response_digest(orphan.to_dict())


def test_a_hostile_request_object_is_never_introspected(source) -> None:
    """A non-request object handed to either entry point yields a typed refusal."""
    for candidate in (Hostile(), object(), 7, "not-a-mapping", None):
        response = run_offline_research_inference_from_document(candidate, model_source=source)
        assert response.status is ResearchFacadeStatus.ERROR
        detail = error_of(response)
        reported = detail.to_dict()
        assert reported["input_values_echoed"] is False
        assert reported["local_paths_echoed"] is False
        clean = _assert_clean(response)
        summary = safe_document_summary(candidate)
        assert clean["request_summary"] == summary
        # Nothing can be reported about an object that is not a request at all.
        for field in (
            "route_id",
            "model_id",
            "model_version",
            "panel_id",
            "panel_version",
            "panel_contract_sha256",
            "dataset_id",
            "operation",
            "request_schema_version",
            "route_version",
        ):
            assert summary[field] is None, field
        assert summary["request_type_accepted"] is False
        assert summary["unvalidated_values_redacted"] is True
        assert summary["record_count"] == 0


def test_a_rejected_model_source_argument_echoes_no_path(source, records) -> None:
    """The *artifact source* is caller-supplied too, and equally unechoed."""
    document = _base_document([doc(records[0])])
    hostile_sources = (
        Hostile(),
        "/home/leak/secret_bundle.json",
        "C:\\synthetic-fake-secret\\bundle",
        {"bundle_dir": "/home/leak/secret_bundle.json", "signing_key": "nested-secret"},
        None,
    )
    for candidate in hostile_sources:
        response = run_offline_research_inference_from_document(document, model_source=candidate)
        assert response.status is ResearchFacadeStatus.ERROR
        assert error_of(response).code == "model_source_not_allowed"
        summary = _assert_clean(response)["request_summary"]
        assert summary["model_source"]["source_type_accepted"] is False
        assert summary["model_source"]["bundle_dir_name"] is None
        assert summary["model_source"]["signing_key_provided"] is False
    # The accepted source still reports its registered, path-free descriptor.
    accepted = run_offline_research_inference_from_document(document, model_source=source)
    assert accepted.to_dict()["request_summary"]["model_source"] == {
        **source.safe_descriptor(),
        "source_type_accepted": True,
    }
    descriptor = json.dumps(accepted.to_dict()["request_summary"]["model_source"])
    assert "bundle_dir\"" not in descriptor and "trusted_local_root" not in descriptor
    assert "/" not in descriptor and "\\" not in descriptor


def test_the_summary_schema_is_identical_on_success_and_on_every_refusal(
    source, records
) -> None:
    """One summary shape everywhere, built only from JSON primitives."""
    success = run_offline_research_inference(
        parse_inference_request(_base_document(list(records)), model_source=source)
    ).to_dict()["request_summary"]

    def walk(value) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                assert isinstance(key, str) and len(key) <= 64
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        else:
            assert value is None or isinstance(value, (bool, int, float, str)), type(value)
            if isinstance(value, str):
                assert len(value) <= 128

    walk(success)
    refusals = [
        call(source, [doc(records[0])], model_id="evil-nested-secret"),
        run_offline_research_inference_from_document(Hostile(), model_source=source),
        run_offline_research_inference_from_document(
            _base_document([{"record_ref": "/home/leak/x"}]), model_source=source
        ),
        run_offline_research_inference(
            ResearchInferenceRequest(
                request_schema_version="x",
                operation="x",
                route_id="x",
                route_version="x",
                model_id="x",
                model_version="x",
                panel_id="x",
                panel_version="x",
                panel_contract_sha256="x",
                dataset_id="x",
                records=(),
                model_source=source,
            )
        ),
    ]
    assert refusals
    for response in refusals:
        assert response.status in {
            ResearchFacadeStatus.ERROR,
            ResearchFacadeStatus.UNAVAILABLE,
            ResearchFacadeStatus.ABSTAIN,
        }
        summary = response.to_dict()["request_summary"]
        assert set(summary) == set(success), json.dumps(sorted(set(summary) ^ set(success)))
        assert set(summary["explainability"]) == set(success["explainability"])
        assert set(summary["model_source"]) == set(success["model_source"])
        walk(summary)
        _assert_clean(response)


# --------------------------------------------------------------------------- #
# Package surface and the surrounding safety boundary                        #
# --------------------------------------------------------------------------- #


def test_public_api_is_exported_from_the_ai_package() -> None:
    import ai

    for name in (
        "RESEARCH_MODEL_REGISTRY",
        "resolve_registered_model",
        "registry_contract",
        "registry_digest_sha256",
        "run_offline_research_inference",
        "run_offline_research_inference_from_document",
        "ResearchFacadeStatus",
        "ResearchInferenceRequest",
        "ResearchInferenceResponse",
        "run_research_facade_demo",
    ):
        assert hasattr(ai, name), name
        assert name in ai.__all__, name


def test_the_new_modules_import_without_side_effects(tmp_path) -> None:
    import subprocess
    import sys

    script = (
        "import sys, pathlib;"
        "import ai.research_registry as r;"
        "assert not [m for m in sys.modules if m.startswith(('fastapi','uvicorn','requests'))];"
        "print(r.registry_digest_sha256())"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, cwd=str(Path(__file__).resolve().parents[2])
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == registry_digest_sha256()


def test_no_http_surface_or_contract_change_is_introduced() -> None:
    """No web/HTTP dependency, no route, no artifact left behind in the tree.

    Only import lines are scanned: the module docstrings deliberately *name*
    FastAPI and ``/v1`` in order to record that those surfaces are untouched.
    """
    root = Path(__file__).resolve().parents[2]
    for relative in ("ai/research_facade.py", "ai/research_registry.py", "ai/research_demo.py"):
        lines = (root / relative).read_text(encoding="utf-8").splitlines()
        imports = " ".join(
            line.strip() for line in lines if re.match(r"^\s*(import|from)\s", line)
        )
        for forbidden in (
            "fastapi",
            "APIRouter",
            "uvicorn",
            "starlette",
            "pydantic",
            "requests",
            "httpx",
            "socket",
            "urllib",
            "aiohttp",
        ):
            assert forbidden not in imports, (relative, forbidden)
        assert not any(line.startswith(("@app.", "@router.", "@bp.")) for line in lines)
    # No application module reaches into the research facade, so nothing can
    # route a live request to it: the backend keeps exactly its own mock path.
    offenders = []
    for path in sorted((root / "backend").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "research_facade" in text or "research_registry" in text:
            offenders.append(str(path.relative_to(root)))
    assert offenders == []
    # And the synthetic-only tree contains no model or dataset artifact, which is
    # the same invariant the CI job enforces by filesystem scan.
    prohibited_suffixes = {
        ".joblib", ".pkl", ".pt", ".pth", ".onnx", ".h5", ".parquet", ".csv",
        ".xlsx", ".sqlite", ".db",
    }
    stray = [
        str(path.relative_to(root))
        for directory in ("ai", "tests", "shared")
        for path in (root / directory).rglob("*")
        if path.is_file() and path.suffix in prohibited_suffixes
    ]
    assert stray == []


def test_backend_and_diagnostic_boundaries_are_untouched() -> None:
    """This facade adds no provider, no serving path and no diagnostic scope."""
    from backend.app.inference.registry import ACTIVE_PROVIDER_IDS
    from backend.app.inference.types import MOCK_SYNTHETIC_PROVIDER_ID
    from ai.diagnostic_scope import (
        DIAGNOSTIC_REGISTRY_SYMBOL,
        RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES,
    )

    # The application still resolves exactly one provider: the mock synthetic one.
    assert ACTIVE_PROVIDER_IDS == frozenset({MOCK_SYNTHETIC_PROVIDER_ID})
    # The separately ratified diagnostic-inference registry gained nothing from
    # this work: no synthetic research model entry is a ratified diagnostic
    # scope, and no synthetic facade artifact kind appears in it.
    assert DIAGNOSTIC_REGISTRY_SYMBOL == "RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES"
    for key, entry in RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES.items():
        assert not key.startswith("SYNTH")
        model_id = str(entry.get("model_id", ""))
        assert not model_id.startswith("synth_"), key
    for registered in RESEARCH_MODEL_REGISTRY.values():
        assert registered.model_id not in json.dumps(RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES)
        assert registered.approved_for_serving is False


def test_demo_reports_all_four_statuses_and_passes(tmp_path) -> None:
    payload = run_research_facade_demo(work_dir=ensure_private_directory(tmp_path / "demo"))
    assert payload.get("failure") is None
    assert payload["status"] == "PASSED"
    assert {stage["status"] for stage in payload["stage_results"]} == {"PASSED"}
    assert [stage["stage"] for stage in payload["stage_results"]] == [
        "1_registry_contract",
        "2_synthetic_cohort",
        "3_synthetic_training_and_bundle",
        "4_successful_synthetic_inference",
        "5_abstention",
        "6_unavailable_contracts",
        "7_typed_error_refusals",
        "8_determinism_and_redaction",
    ]
    exercised = set(payload["summary"]["statuses_exercised"])
    assert exercised == {status.value for status in ResearchFacadeStatus}
    refusal_cases = [
        case
        for stage in payload["stage_results"]
        for case in (stage["detail"].get("cases") or [])
    ]
    assert len(refusal_cases) >= 30
    assert not any(case["score_produced"] for case in refusal_cases)
    assert payload["deterministic_sha256"]
    assert payload["evidence_level"] == "SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE"
    assert payload["synthetic_only"] is True
    assert payload["not_claimed"]
    assert str(tmp_path) not in json.dumps(payload)


def test_demo_is_deterministic_across_runs(tmp_path) -> None:
    a = run_research_facade_demo(
        work_dir=ensure_private_directory(tmp_path / "a"), with_lime=False
    )
    b = run_research_facade_demo(
        work_dir=ensure_private_directory(tmp_path / "b"), with_lime=False
    )
    assert a["deterministic_sha256"] == b["deterministic_sha256"]
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_demo_cli_exit_codes(tmp_path) -> None:
    from ai.research_demo import EXIT_OK, main

    assert main(["--format", "text", "--no-lime", "--work-dir", str(tmp_path)]) == EXIT_OK
    assert any(Path(tmp_path).rglob("*"))
    assert main(["--format", "json", "--no-lime"]) == EXIT_OK


def test_demo_text_render_is_path_free(tmp_path, capsys) -> None:
    from ai.research_demo import main

    assert main(["--format", "text"]) == 0
    printed = capsys.readouterr().out
    assert "SYNTHETIC_RESULT" in printed and "UNAVAILABLE" in printed
    assert str(tmp_path) not in printed
