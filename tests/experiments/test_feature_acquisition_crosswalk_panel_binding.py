"""Live binding of the RH-04 acquisition-evidence crosswalk to the real code.

The stdlib-only crosswalk tests live in ``tests/audit`` and run in the minimal
audit CI environment (no numpy/scikit-learn). These checks need the full ``ai``
stack, so they live under ``tests/experiments`` and prove three things:

1. the crosswalk's four panel ids, versions and feature rosters are identical to
   :data:`ai.panels.REGISTERED_PANELS` — the crosswalk references the panels and
   never redefines them;
2. its five route ids, dataset/panel bindings, admissibility strings,
   authorization statuses, evaluation statuses, permitted-operation sets and
   forbidden-operation sets are identical to
   :data:`ai.research_routes.RESEARCH_ROUTE_CATALOG`;
3. its per-field UCI-412 source claims (``source_domain`` and the
   ``EXPECTED_AVAILABLE_BEFORE_ANGIOGRAPHY`` / ``PLAUSIBLE_UNVERIFIED_TIMING``
   availability class) are identical to the frozen feature dictionary 1.1.0 and
   the AI-8R eligibility register, while **no** field is treated as
   owner-verified timing (0/16).

Everything is read-only and synthetic: no dataset, workbook, patient row, model
artifact or backend route is opened.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai.panels import REGISTERED_PANELS
from ai.research_routes import (
    REAL_DATA_OR_CLINICAL_OPERATIONS,
    RESEARCH_ROUTE_CATALOG,
    VALID_EVALUATION_STATUSES,
)
from research.intake.synthetic_stage_validator import FIELD_DEFINITIONS
from research.intake.feature_acquisition_crosswalk import (
    CROSSWALK_PATH,
    FORBIDDEN_OPERATIONS_ALWAYS,
    KNOWN_OPERATIONS,
    PANEL_SPECS,
    ROUTE_ACTIVATION_STATES,
    ROUTE_SPECS,
    SOURCES,
    TIMING_STATUS_TAXONOMY,
    load_crosswalk,
    query_feature_evidence,
)
from research.uci412.feature_schema import DEFAULT_DICTIONARY, PRIMARY_PANEL_COLUMNS

REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_AUDIT_DIR = REPO_ROOT / "backend" / "app"
AI_DIR = REPO_ROOT / "ai"
AI8R_ELIGIBILITY_PATH = REPO_ROOT / "research" / "uci412" / "schemas" / "ai8r_eligibility.v1.json"
RH02_REGISTER_PATH = (
    REPO_ROOT / "docs" / "research" / "next_phase"
    / "RH02_SOURCE_QUESTION_REGISTER_2026_11_19.json"
)

#: Regression lock: the four registered panel contracts this crosswalk
#: references must not change in this evidence-only slice.
EXPECTED_PANEL_CONTRACT_SHA256 = {
    "da_a2_resting_v1": "c18ad4cd2cf08f6fefb2e340573760da7000bc1d8eb4ad38783b873c018e57b8",
    "da_a2_resting_labs_v1": "2a822095917cd7dfbadd2edc1be9537aa68322dfe8191576265623c96762584b",
    "da_a1_basic_clinical_v1": "efd51491c06d808ac3e02a62c45302dd9a57966b6f619b0c604df980ba71a208",
    "da_a1_clinical_core_labs_v1": "fe6fca9b53410b6870e2bfcb206627d70c75b64746d6f8b638191f8728c984cd",
}

UCI412_LAB_FEATURES = ("FBS", "CR", "TG", "LDL", "HDL", "HB", "WBC")
UCI45_FEATURES = ("age", "sex", "cp", "trestbps", "restecg", "chol", "fbs")


# --------------------------------------------------------------------------- #
# Panels: reference, never redefine                                           #
# --------------------------------------------------------------------------- #


def test_crosswalk_panel_ids_match_the_registered_panels_exactly() -> None:
    assert {panel.panel_id for panel in PANEL_SPECS} == set(REGISTERED_PANELS)
    crosswalk = load_crosswalk()
    assert {panel.panel_id for panel in crosswalk.panels} == set(REGISTERED_PANELS)


@pytest.mark.parametrize("panel_id", sorted(REGISTERED_PANELS))
def test_panel_version_dataset_and_feature_count_match_live_panel(panel_id: str) -> None:
    live = REGISTERED_PANELS[panel_id]
    spec = next(panel for panel in PANEL_SPECS if panel.panel_id == panel_id)
    assert spec.dataset_id == live.dataset_id
    assert spec.panel_version == live.panel_version
    assert len(spec.features) == len(live.feature_names)
    assert tuple(spec.features) == tuple(live.feature_names)
    binding = next(
        panel for panel in load_crosswalk().panels if panel.panel_id == panel_id
    )
    assert binding.dataset_id == live.dataset_id
    assert binding.panel_version == live.panel_version
    assert binding.feature_count == len(live.feature_names)


def test_feature_panel_membership_matches_live_panels() -> None:
    crosswalk = load_crosswalk()
    for feature in crosswalk.features:
        live_membership = tuple(
            panel_id
            for panel_id, panel in REGISTERED_PANELS.items()
            if panel.dataset_id == feature.dataset_id
            and feature.feature_name in panel.feature_names
        )
        assert tuple(feature.panels) == live_membership


def test_every_live_panel_feature_has_a_crosswalk_record() -> None:
    crosswalk = load_crosswalk()
    recorded = {
        (feature.dataset_id, feature.feature_name) for feature in crosswalk.features
    }
    for panel in REGISTERED_PANELS.values():
        for name in panel.feature_names:
            assert (panel.dataset_id, name) in recorded


# --------------------------------------------------------------------------- #
# Routes: activation may not drift                                            #
# --------------------------------------------------------------------------- #


def test_crosswalk_route_ids_match_the_route_catalog_exactly() -> None:
    assert set(ROUTE_SPECS) == set(RESEARCH_ROUTE_CATALOG)
    assert {route.route_id for route in load_crosswalk().routes} == set(
        RESEARCH_ROUTE_CATALOG
    )


@pytest.mark.parametrize("route_id", sorted(RESEARCH_ROUTE_CATALOG))
def test_route_binding_matches_live_route_descriptor(route_id: str) -> None:
    live = RESEARCH_ROUTE_CATALOG[route_id]
    spec = ROUTE_SPECS[route_id]
    record = load_crosswalk().route(route_id)

    assert spec["dataset_id"] == live.dataset_id
    assert spec["panel_id"] == live.panel_id
    assert record.dataset_id == live.dataset_id
    assert record.panel_id == live.panel_id
    assert live.panel_contract_sha256 == REGISTERED_PANELS[live.panel_id].contract_sha256

    assert record.prediction_time_admissibility == live.prediction_time_admissibility
    assert record.authorization_status == live.research_authorization_status
    assert record.evaluation_status == live.evaluation_status
    assert record.evaluation_status in VALID_EVALUATION_STATUSES
    assert set(record.permitted_operations) == set(live.permitted_operations)
    assert set(record.forbidden_operations) == set(live.forbidden_operations)


def test_operation_vocabulary_matches_live_catalog() -> None:
    live_operations: set[str] = set()
    for route in RESEARCH_ROUTE_CATALOG.values():
        live_operations |= set(route.permitted_operations)
        live_operations |= set(route.forbidden_operations)
    assert KNOWN_OPERATIONS == live_operations
    assert FORBIDDEN_OPERATIONS_ALWAYS == frozenset(REAL_DATA_OR_CLINICAL_OPERATIONS)


def test_blocked_routes_are_exactly_the_contract_query_only_routes() -> None:
    crosswalk = load_crosswalk()
    live_blocked = {
        route_id
        for route_id, route in RESEARCH_ROUTE_CATALOG.items()
        if set(route.permitted_operations) == {"route_contract_query"}
    }
    recorded_blocked = {
        route.route_id
        for route in crosswalk.routes
        if route.permitted_operations == ("route_contract_query",)
    }
    assert live_blocked == recorded_blocked
    assert recorded_blocked == {
        "da_a2_resting_labs_v1",
        "da_a1_clinical_core_labs_v1",
        "da_a2_hungary_locked_transportability_v1",
    }
    for record in crosswalk.routes:
        assert record.blocked is (record.route_id in live_blocked)
        assert record.activation_state in ROUTE_ACTIVATION_STATES


def test_activation_state_is_never_more_permissive_than_the_catalog() -> None:
    crosswalk = load_crosswalk()
    active = {"ACTIVE_SYNTHETIC_ONLY"}
    for record in crosswalk.routes:
        live = RESEARCH_ROUTE_CATALOG[record.route_id]
        if record.activation_state in active:
            # An "active" route may only carry operations the live catalog allows.
            assert set(record.permitted_operations) <= set(live.permitted_operations)
            assert not (set(record.permitted_operations) & REAL_DATA_OR_CLINICAL_OPERATIONS)
        else:
            assert record.permitted_operations == ("route_contract_query",)


def test_synthetic_route_exercise_stays_inside_the_crosswalk_surface() -> None:
    # The crosswalk records the same synthetic-only operation set the live
    # resolver exposes; nothing here adds a route, panel, provider or endpoint.
    synthetic_ops = {
        "synthetic_training",
        "synthetic_prediction",
        "synthetic_external_evaluation",
        "shap_attribution",
        "lime_assessment",
        "bundle_packaging",
        "synthetic_end_to_end_exercise",
    }
    for record in load_crosswalk().routes:
        assert set(record.permitted_operations) - synthetic_ops <= {"route_contract_query"}


# --------------------------------------------------------------------------- #
# Per-field source claims: dictionary, AI-8R register and RH-02 register      #
# --------------------------------------------------------------------------- #


def test_uci412_source_claims_match_the_frozen_feature_dictionary() -> None:
    crosswalk = load_crosswalk()
    for feature in crosswalk.features:
        if feature.dataset_id != "DA-A1":
            continue
        spec = DEFAULT_DICTIONARY.feature(feature.feature_name)
        claim = feature.registered_source_claim
        assert claim.source_domain == spec.source_domain
        assert (
            claim.availability_at_decision_time
            == spec.availability_at_decision_time
        )
    assert tuple(PRIMARY_PANEL_COLUMNS) == tuple(
        REGISTERED_PANELS["da_a1_basic_clinical_v1"].feature_names
    )


def test_uci412_channel_matches_registered_source_domain() -> None:
    from research.intake.feature_acquisition_crosswalk import DOMAIN_TO_CHANNEL

    for feature in load_crosswalk().features:
        if feature.dataset_id != "DA-A1":
            continue
        spec = DEFAULT_DICTIONARY.feature(feature.feature_name)
        assert feature.acquisition.channel == DOMAIN_TO_CHANNEL[spec.source_domain]
        expected_status = (
            "VERIFIED_REGISTERED_SOURCE_DOMAIN"
            if feature.feature_name in PRIMARY_PANEL_COLUMNS
            else "PROPOSED_FUTURE_ACQUISITION_CHANNEL"
        )
        assert feature.acquisition.channel_status == expected_status


def test_uci45_features_match_the_registered_stage_allowlist() -> None:
    crosswalk = load_crosswalk()
    for feature in crosswalk.features:
        if feature.dataset_id != "DA-A2":
            continue
        assert feature.feature_name in FIELD_DEFINITIONS
    assert {feature.feature_name for feature in crosswalk.features if feature.dataset_id == "DA-A2"} == set(
        UCI45_FEATURES
    )
    assert tuple(REGISTERED_PANELS["da_a2_resting_labs_v1"].feature_names) == tuple(
        UCI45_FEATURES
    )


def test_uci412_ai8r_register_keeps_all_sixteen_fields_unverified() -> None:
    document = json.loads(AI8R_ELIGIBILITY_PATH.read_text(encoding="utf-8"))
    assert document["source_id"] == "UCI-412"
    assert document["panel_id"] == "uci412_basic_clinical_v1"
    assert len(document["fields"]) == 16
    assert [field["name"] for field in document["fields"]] == list(PRIMARY_PANEL_COLUMNS)
    assert all(field["pre_angiography"] == "UNVERIFIED" for field in document["fields"])

    crosswalk = load_crosswalk()
    basic = [
        feature
        for feature in crosswalk.features
        if feature.dataset_id == "DA-A1"
        and feature.feature_name in PRIMARY_PANEL_COLUMNS
    ]
    assert len(basic) == 16
    assert all(
        feature.acquisition.timing_status
        == "UNVERIFIED_TIMING_REGISTERED_DOMAIN_CHANNEL"
        for feature in basic
    )
    assert not any(
        feature.acquisition.owner_verified_pre_angiography for feature in basic
    )


def test_rh02_timing_gap_register_confirms_zero_of_sixteen() -> None:
    document = json.loads(RH02_REGISTER_PATH.read_text(encoding="utf-8"))
    fields = document["uci412_sixteen_fields"]
    assert len(fields) == 16
    assert all(
        field["owner_verified_preangiography_timing"] is False for field in fields
    )
    assert document["round2_review"]["uci412_owner_verified_preindex_fields"] == 0
    holds = dict(load_crosswalk().holds)
    assert holds["uci412_basic_clinical_owner_verified_pre_angiography"] == "0/16"


def test_labs_features_are_registered_but_never_owner_verified() -> None:
    crosswalk = load_crosswalk()
    labs = [
        feature
        for feature in crosswalk.features
        if feature.feature_name in UCI412_LAB_FEATURES
    ]
    assert len(labs) == 7
    for feature in labs:
        assert feature.acquisition.channel_status == "PROPOSED_FUTURE_ACQUISITION_CHANNEL"
        assert feature.acquisition.timing_status == "UNVERIFIED_TIMING_PROPOSED_CHANNEL"
        assert feature.acquisition.owner_verified_pre_angiography is False
        assert "RES-UCI412-LABS-BLOCKED" in feature.restriction_ids


def test_timing_status_taxonomy_reserves_owner_verified_status_only() -> None:
    assert set(TIMING_STATUS_TAXONOMY) == {
        "UNVERIFIED_TIMING_REGISTERED_DOMAIN_CHANNEL",
        "UNVERIFIED_TIMING_PROPOSED_CHANNEL",
        "OWNER_VERIFIED_PRE_ANGIOGRAPHY",
    }
    assert query_feature_evidence(
        timing_status="OWNER_VERIFIED_PRE_ANGIOGRAPHY"
    ).to_dict()["matched_feature_count"] == 0


# --------------------------------------------------------------------------- #
# No new schema, route, endpoint or artifact                                 #
# --------------------------------------------------------------------------- #


def test_crosswalk_does_not_add_a_route_or_provider() -> None:
    # Every live route's source family resolves to the same dataset the
    # crosswalk records; no sixth route and no fifth panel exist.
    for route in RESEARCH_ROUTE_CATALOG.values():
        assert route.dataset_id == SOURCES[route.source_family]["dataset_id"]
    assert len(RESEARCH_ROUTE_CATALOG) == 5
    assert len(REGISTERED_PANELS) == 4
    assert len(SOURCES) == 2


def test_backend_and_ai_packages_never_import_the_crosswalk() -> None:
    for directory in (STATIC_AUDIT_DIR, AI_DIR):
        for path in directory.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            assert "feature_acquisition_crosswalk" not in text, path
    assert "feature_acquisition_crosswalk" not in (
        REPO_ROOT / "backend" / "app" / "main.py"
    ).read_text(encoding="utf-8")


def test_crosswalk_document_is_the_only_new_artifact_in_its_schema_dir() -> None:
    schema_dir = CROSSWALK_PATH.parent
    assert CROSSWALK_PATH in set(schema_dir.glob("*.json"))
    assert CROSSWALK_PATH.read_text(encoding="utf-8").startswith("{")


def test_registered_panel_contract_hashes_are_unchanged() -> None:
    for panel_id, expected in EXPECTED_PANEL_CONTRACT_SHA256.items():
        assert REGISTERED_PANELS[panel_id].contract_sha256 == expected


def test_frozen_contracts_and_workflows_are_untouched_by_this_slice() -> None:
    holds = dict(load_crosswalk().holds)
    assert holds["frozen_contracts_modified"] is False
    assert holds["github_workflows_modified"] is False
    assert holds["new_endpoints_added"] is False


# --------------------------------------------------------------------------- #
# Authorization scope: historical reference vs effective permission           #
# --------------------------------------------------------------------------- #


def test_historical_reference_pins_the_live_cleveland_five_field_panel() -> None:
    crosswalk = load_crosswalk()
    reference = crosswalk.authorization_references[0]
    live = REGISTERED_PANELS["da_a2_resting_v1"]
    assert reference.authorized_panel_id == live.panel_id
    assert reference.authorized_dataset_id == live.dataset_id
    assert reference.authorized_feature_names == tuple(live.feature_names)
    assert reference.authorized_feature_names == (
        "age",
        "sex",
        "cp",
        "trestbps",
        "restecg",
    )
    assert reference.authorizes_new_real_data_execution is False
    assert reference.execution_status == "COMPLETED_HISTORICAL_INTERNAL_EXPLORATORY"


def test_no_feature_outside_the_resting_roster_cites_a_historical_reference() -> None:
    crosswalk = load_crosswalk()
    for feature in crosswalk.features:
        cites_history = bool(
            feature.effective_permission.historical_authorization_reference_ids
        )
        assert cites_history is (feature.feature_name in ("age", "sex", "cp", "trestbps", "restecg"))
        if cites_history:
            assert "da_a2_resting_v1" in feature.panels
        assert (
            feature.effective_permission.real_data_execution_authorized_by_this_crosswalk
            is False
        )


def test_blocked_routes_never_export_historical_authorization() -> None:
    crosswalk = load_crosswalk()
    for route in crosswalk.routes:
        if not route.blocked:
            continue
        assert route.effective_permission.historical_authorization_reference_ids == ()
        assert route.effective_permission.effective_permission_status in {
            "NOT_AUTHORIZED",
            "SCIENTIFIC_HOLD_NEW_REAL_FIT",
        }
    hungary = crosswalk.route("da_a2_hungary_locked_transportability_v1")
    assert hungary.effective_permission.effective_permission_status == "NOT_AUTHORIZED"
    assert (
        "da_a2_resting_v1" == RESEARCH_ROUTE_CATALOG[hungary.route_id].panel_id
    )  # the route reuses the panel, which is exactly why scope must be recorded


def test_labs_features_never_resolve_to_the_historical_record() -> None:
    crosswalk = load_crosswalk()
    for name in ("chol", "fbs"):
        feature = crosswalk.feature(f"DA-A2:{name}")
        assert feature.permission_id != "PERM-UCI45-D047-HISTORICAL-REFERENCE"
        assert feature.effective_permission.effective_permission_status == (
            "NOT_AUTHORIZED"
        )
        assert feature.effective_permission.historical_authorization_reference_ids == ()
    for feature in crosswalk.features:
        if feature.dataset_id == "DA-A1":
            assert feature.permission_id == "PERM-UCI412-SCIENTIFIC-HOLD"
            assert (
                feature.effective_permission.historical_authorization_reference_ids
                == ()
            )


def test_historical_reference_evidence_path_still_resolves() -> None:
    crosswalk = load_crosswalk()
    reference = crosswalk.authorization_references[0]
    assert reference.evidence_ids == ("EV-UCI45-D047-PLAN",)
    evidence = {item.evidence_id: item for item in crosswalk.evidence}
    record = evidence["EV-UCI45-D047-PLAN"]
    assert record.evidence_class == "FROZEN_PROTOCOL_REGISTRATION"
    assert record.establishes_acquisition_timing is False
    assert (REPO_ROOT / record.reference_path).is_file()
