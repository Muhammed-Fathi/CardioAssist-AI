"""RH-04.1/RH-04.2 tests for the feature acquisition-evidence crosswalk.

This suite is **stdlib-only**: it must run in the minimal audit CI environment
(``openpyxl`` + ``pytest``) where numpy/scikit-learn and the ``ai`` package are
not installed. The live cross-check against ``ai.panels`` and
``ai.research_routes`` lives in
``tests/experiments/test_feature_acquisition_crosswalk_panel_binding.py``.

Every fixture here is a synthetic in-memory edit of the checked-in JSON
document. No dataset, patient row, trained model or backend route is read,
written or invoked. No CAD probability exists anywhere in this module's
surface: every query returns ``METADATA_ONLY_NO_CAD_PROBABILITY_COMPUTED``.
"""
from __future__ import annotations

import ast
from contextlib import contextmanager
import copy
import dataclasses
import json
from pathlib import Path
from typing import Any, Iterator

import pytest

from research.intake import feature_acquisition_crosswalk as crosswalk_module
from research.intake.feature_acquisition_crosswalk import (
    ACQUISITION_CHANNEL_TAXONOMY,
    CROSSWALK_BASELINE_MAIN_SHA,
    CROSSWALK_ID,
    CROSSWALK_PATH,
    CROSSWALK_SCHEMA_ID,
    CROSSWALK_SCHEMA_VERSION,
    CROSSWALK_STATUS,
    CHANNEL_STATUS_TAXONOMY,
    DISPOSITION_TAXONOMY,
    EVIDENCE_CLASS_TAXONOMY,
    EVIDENCE_REGISTER,
    EXPECTED_HOLDS,
    CrosswalkQueryError,
    CrosswalkValidationError,
    TIMING_STATUS_TAXONOMY,
    canonical_json,
    crosswalk_document_digest,
    describe_crosswalk,
    load_crosswalk,
    main,
    query_feature_evidence,
    validate_crosswalk,
)

MODULE_PATH = Path(crosswalk_module.__file__).resolve()
VERIFIED = "VERIFIED_REGISTERED_SOURCE_DOMAIN"
PROPOSED = "PROPOSED_FUTURE_ACQUISITION_CHANNEL"
TIMING_REGISTERED = "UNVERIFIED_TIMING_REGISTERED_DOMAIN_CHANNEL"
TIMING_PROPOSED = "UNVERIFIED_TIMING_PROPOSED_CHANNEL"


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


def _fresh_document() -> dict[str, Any]:
    """A mutable deep copy of the checked-in document (never mutated in place)."""
    return json.loads(CROSSWALK_PATH.read_text(encoding="utf-8"))


def _feature(document: dict[str, Any], feature_key: str) -> dict[str, Any]:
    for entry in document["features"]:
        if entry["feature_key"] == feature_key:
            return entry
    raise AssertionError(f"missing test feature {feature_key}")


def _route(document: dict[str, Any], route_id: str) -> dict[str, Any]:
    for entry in document["routes"]:
        if entry["route_id"] == route_id:
            return entry
    raise AssertionError(f"missing test route {route_id}")


@contextmanager
def _rejected(document: dict[str, Any], code: str) -> Iterator[CrosswalkValidationError]:
    with pytest.raises(CrosswalkValidationError) as excinfo:
        validate_crosswalk(document)
    assert excinfo.value.code == code, (
        f"expected error code {code!r}, got {excinfo.value.code!r}: {excinfo.value}"
    )
    yield excinfo.value


# --------------------------------------------------------------------------- #
# Positive: identity, coverage, reuse                                         #
# --------------------------------------------------------------------------- #


def test_crosswalk_loads_with_frozen_identity() -> None:
    crosswalk = load_crosswalk()
    assert crosswalk.schema_id == CROSSWALK_SCHEMA_ID
    assert crosswalk.schema_version == CROSSWALK_SCHEMA_VERSION
    assert crosswalk.crosswalk_id == CROSSWALK_ID
    assert crosswalk.status == CROSSWALK_STATUS
    assert crosswalk.status == "EVIDENCE_ONLY_NOT_APPROVED"
    assert crosswalk.baseline_main_sha == CROSSWALK_BASELINE_MAIN_SHA
    assert len(crosswalk.document_digest_sha256) == 64


def test_crosswalk_covers_exactly_four_panels_and_five_routes() -> None:
    crosswalk = load_crosswalk()
    assert [panel.panel_id for panel in crosswalk.panels] == [
        "da_a2_resting_v1",
        "da_a2_resting_labs_v1",
        "da_a1_basic_clinical_v1",
        "da_a1_clinical_core_labs_v1",
    ]
    assert [panel.feature_count for panel in crosswalk.panels] == [5, 7, 16, 23]
    assert [route.route_id for route in crosswalk.routes] == [
        "da_a2_resting_v1",
        "da_a2_resting_labs_v1",
        "da_a1_basic_clinical_v1",
        "da_a1_clinical_core_labs_v1",
        "da_a2_hungary_locked_transportability_v1",
    ]
    assert all(panel.registered_in == "ai.panels.REGISTERED_PANELS" for panel in crosswalk.panels)


def test_every_registered_feature_has_exactly_one_evidence_record() -> None:
    crosswalk = load_crosswalk()
    keys = [feature.feature_key for feature in crosswalk.features]
    assert len(keys) == len(set(keys)) == 30
    assert sorted(keys) == sorted(
        [
            *[f"DA-A1:{name}" for name in (
                "Age", "Sex", "BMI", "DM", "HTN", "Current Smoker", "EX-Smoker",
                "FH", "DLP", "BP", "PR", "Typical Chest Pain", "Atypical",
                "Nonanginal", "Exertional CP", "Dyspnea",
                "FBS", "CR", "TG", "LDL", "HDL", "HB", "WBC",
            )],
            *[f"DA-A2:{name}" for name in (
                "age", "sex", "cp", "trestbps", "restecg", "chol", "fbs",
            )],
        ]
    )


def test_feature_panel_membership_matches_panel_rosters() -> None:
    crosswalk = load_crosswalk()
    membership: dict[str, set[str]] = {}
    for feature in crosswalk.features:
        membership[feature.feature_key] = set(feature.panels)
    assert membership["DA-A2:age"] == {"da_a2_resting_v1", "da_a2_resting_labs_v1"}
    assert membership["DA-A2:chol"] == {"da_a2_resting_labs_v1"}
    assert membership["DA-A1:Age"] == {
        "da_a1_basic_clinical_v1",
        "da_a1_clinical_core_labs_v1",
    }
    assert membership["DA-A1:WBC"] == {"da_a1_clinical_core_labs_v1"}
    for panel in crosswalk.panels:
        included = {
            feature.feature_name
            for feature in crosswalk.features
            if panel.panel_id in feature.panels
        }
        assert len(included) == panel.feature_count


def test_definition_evidence_resolves_to_registered_definitional_items() -> None:
    crosswalk = load_crosswalk()
    evidence = {item.evidence_id: item for item in crosswalk.evidence}
    assert set(evidence) == set(EVIDENCE_REGISTER)
    for feature in crosswalk.features:
        assert feature.definition_evidence_ids
        for evidence_id in feature.definition_evidence_ids:
            assert evidence[evidence_id].establishes_feature_definition is True
        claim = feature.registered_source_claim
        assert claim.register_evidence_id in evidence


def test_channels_and_timing_are_separated_per_feature() -> None:
    crosswalk = load_crosswalk()
    for feature in crosswalk.features:
        assert feature.acquisition.channel in ACQUISITION_CHANNEL_TAXONOMY
        assert feature.acquisition.channel_status in CHANNEL_STATUS_TAXONOMY
        assert feature.acquisition.timing_status in TIMING_STATUS_TAXONOMY
        assert feature.acquisition.timing_derived_from_channel_status is False
        if feature.acquisition.channel_status == VERIFIED:
            assert feature.acquisition.timing_status == TIMING_REGISTERED
        else:
            assert feature.acquisition.timing_status == TIMING_PROPOSED
    counts = describe_crosswalk()["channel_status_counts"]
    assert counts == {PROPOSED: 14, VERIFIED: 16}


def test_no_feature_has_owner_verified_pre_angiography_timing() -> None:
    crosswalk = load_crosswalk()
    assert all(
        feature.acquisition.owner_verified_pre_angiography is False
        for feature in crosswalk.features
    )
    assert describe_crosswalk()["owner_verified_pre_angiography_feature_count"] == 0
    holds = dict(crosswalk.holds)
    assert holds["owner_verified_pre_angiography_feature_counts"] == {
        "UCI-45": 0,
        "UCI-412": 0,
    }
    assert holds["uci412_basic_clinical_owner_verified_pre_angiography"] == "0/16"
    uci412_basic = [
        feature
        for feature in crosswalk.features
        if feature.dataset_id == "DA-A1"
        and feature.feature_name not in {"FBS", "CR", "TG", "LDL", "HDL", "HB", "WBC"}
    ]
    assert len(uci412_basic) == 16
    assert not any(
        feature.acquisition.owner_verified_pre_angiography for feature in uci412_basic
    )


def test_scientific_holds_are_preserved_verbatim() -> None:
    holds = dict(load_crosswalk().holds)
    assert holds["gate_pt_p1_target_population_moment"] == "PENDING"
    assert holds["gate_pt_p3_formal_research"] == "CLOSED"
    assert holds["gate_pt_p5_clinical_readiness_claims"] == "NOT_MADE_PROHIBITED"
    assert holds["uci412_scientific_hold"] is True
    for flag in (
        "real_data_training_authorized",
        "real_model_artifacts_created",
        "patient_data_accessed",
        "new_endpoints_added",
        "frozen_contracts_modified",
        "github_workflows_modified",
    ):
        assert holds[flag] is False


def test_source_permissions_are_specific_and_activate_nothing() -> None:
    crosswalk = load_crosswalk()
    permissions = {item.permission_id: item for item in crosswalk.permissions}
    assert set(permissions) == {
        "PERM-UCI45-D047-HISTORICAL-REFERENCE",
        "PERM-UCI45-LABS-NOT-AUTHORIZED",
        "PERM-UCI412-SCIENTIFIC-HOLD",
    }
    assert (
        permissions["PERM-UCI45-D047-HISTORICAL-REFERENCE"].permission_status
        == "HISTORICAL_D047_SCOPE_REFERENCE_ONLY"
    )
    assert (
        permissions["PERM-UCI45-LABS-NOT-AUTHORIZED"].permission_status
        == "NOT_AUTHORIZED_OUT_OF_D047_SCOPE"
    )
    assert (
        permissions["PERM-UCI412-SCIENTIFIC-HOLD"].permission_status
        == "SCIENTIFIC_HOLD_NEW_REAL_FIT"
    )
    for permission in permissions.values():
        assert permission.real_data_execution_authorized_by_this_crosswalk is False
        assert permission.activation_by_this_artifact == "NONE"
        assert not permission.permission_status.startswith("AUTHORIZED")
    sources = {item.source_id: item for item in crosswalk.sources}
    assert sources["UCI-45"].dataset_id == "DA-A2"
    assert sources["UCI-412"].dataset_id == "DA-A1"
    assert (
        sources["UCI-45"].effective_source_permission_status
        == "NOT_AUTHORIZED_FOR_NEW_REAL_DATA"
    )
    assert (
        sources["UCI-412"].effective_source_permission_status
        == "SCIENTIFIC_HOLD_NEW_REAL_FIT"
    )
    for feature in crosswalk.features:
        assert feature.permission_id in permissions
        assert permissions[feature.permission_id].source_id == feature.source_id
        assert feature.feature_name in permissions[feature.permission_id].covered_feature_names


def test_no_exported_status_is_an_unqualified_authorization() -> None:
    crosswalk = load_crosswalk()
    statuses = [item.permission_status for item in crosswalk.permissions]
    statuses += [
        item.effective_permission.effective_permission_status
        for item in crosswalk.features
    ]
    statuses += [
        item.effective_permission.effective_permission_status for item in crosswalk.routes
    ]
    statuses += [item.effective_source_permission_status for item in crosswalk.sources]
    assert all(not status.startswith("AUTHORIZED") for status in statuses)
    raw = CROSSWALK_PATH.read_text(encoding="utf-8")
    assert "AUTHORIZED_INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED" not in raw
    assert "AUTHORIZED" not in "".join(
        status for status in statuses if not status.startswith("NOT_AUTHORIZED")
    )
    query = query_feature_evidence().to_dict()
    assert query["authorization_scope"][
        "new_real_data_authorization_granted_by_this_crosswalk"
    ] is False
    assert all(
        not route["effective_permission"]["effective_permission_status"].startswith(
            "AUTHORIZED"
        )
        for route in query["routes"]
    )


def test_chol_and_fbs_are_not_authorized_by_d047() -> None:
    crosswalk = load_crosswalk()
    permissions = {item.permission_id: item for item in crosswalk.permissions}
    reference = crosswalk.authorization_references[0]

    for feature_name in ("chol", "fbs"):
        feature = crosswalk.feature(f"DA-A2:{feature_name}")
        assert feature.permission_id == "PERM-UCI45-LABS-NOT-AUTHORIZED"
        assert feature.effective_permission.effective_permission_status == (
            "NOT_AUTHORIZED"
        )
        assert feature.effective_permission.historical_authorization_reference_ids == ()
        assert feature_name not in reference.authorized_feature_names
        assert reference.authorized_feature_names == (
            "age",
            "sex",
            "cp",
            "trestbps",
            "restecg",
        )
        permission = permissions[feature.permission_id]
        assert permission.permission_status == "NOT_AUTHORIZED_OUT_OF_D047_SCOPE"
        assert permission.historical_authorization_reference_ids == ()

        queried = query_feature_evidence(
            dataset_id="DA-A2", feature_name=feature_name
        ).to_dict()
        assert queried["matched_feature_count"] == 1
        exported = queried["features"][0]
        assert exported["effective_permission"]["effective_permission_status"] == (
            "NOT_AUTHORIZED"
        )
        assert (
            exported["effective_permission"][
                "historical_authorization_reference_ids"
            ]
            == []
        )
        assert exported["permission_id"] == "PERM-UCI45-LABS-NOT-AUTHORIZED"


def test_hungary_locked_route_is_not_authorized_by_d047() -> None:
    crosswalk = load_crosswalk()
    reference = crosswalk.authorization_references[0]
    assert reference.authorized_panel_id == "da_a2_resting_v1"
    assert reference.authorized_dataset_id == "DA-A2"

    hungary = crosswalk.route("da_a2_hungary_locked_transportability_v1")
    assert hungary.effective_permission.effective_permission_status == (
        "NOT_AUTHORIZED"
    )
    assert hungary.effective_permission.historical_authorization_reference_ids == ()
    assert (
        hungary.effective_permission.real_data_execution_authorized_by_this_crosswalk
        is False
    )
    assert hungary.blocked is True

    queried = query_feature_evidence(
        route_id="da_a2_hungary_locked_transportability_v1"
    ).to_dict()
    assert queried["matched_route_count"] == 1
    route = queried["routes"][0]
    assert route["route_id"] == "da_a2_hungary_locked_transportability_v1"
    assert route["effective_permission"]["effective_permission_status"] == (
        "NOT_AUTHORIZED"
    )
    assert route["effective_permission"]["historical_authorization_reference_ids"] == []
    assert (
        route["effective_permission"][
            "real_data_execution_authorized_by_this_crosswalk"
        ]
        is False
    )
    assert queried["authorization_scope"][
        "new_real_data_authorization_granted_by_this_crosswalk"
    ] is False
    assert all(
        "AUTHREF-D047-CLEVELAND-FIVE-FIELD"
        not in feature["effective_permission"][
            "historical_authorization_reference_ids"
        ]
        if feature["dataset_id"] == "DA-A1"
        else True
        for feature in queried["features"]
    )


def test_historical_d047_five_field_scope_is_represented_accurately() -> None:
    crosswalk = load_crosswalk()
    assert len(crosswalk.authorization_references) == 1
    reference = crosswalk.authorization_references[0]
    assert reference.reference_id == "AUTHREF-D047-CLEVELAND-FIVE-FIELD"
    assert reference.decision_id == "D-047"
    assert reference.authorized_dataset_id == "DA-A2"
    assert reference.authorized_panel_id == "da_a2_resting_v1"
    assert reference.authorized_feature_names == (
        "age",
        "sex",
        "cp",
        "trestbps",
        "restecg",
    )
    assert reference.execution_status == "COMPLETED_HISTORICAL_INTERNAL_EXPLORATORY"
    assert reference.authorizes_new_real_data_execution is False
    assert reference.historical_execution_label == (
        "INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED"
    )
    assert reference.evidence_ids == ("EV-UCI45-D047-PLAN",)
    assert "not a currently operative permission" in reference.statement
    assert "new real-data execution" in reference.statement
    assert "chol" in reference.statement and "Hungary" in reference.statement
    assert crosswalk.feature("DA-A2:age").effective_permission.to_dict() == {
        "effective_permission_status": (
            "HISTORICAL_REFERENCE_ONLY_NO_NEW_AUTHORIZATION"
        ),
        "historical_authorization_reference_ids": [
            "AUTHREF-D047-CLEVELAND-FIVE-FIELD"
        ],
        "real_data_execution_authorized_by_this_crosswalk": False,
    }

    resting_route = crosswalk.route("da_a2_resting_v1")
    assert (
        resting_route.effective_permission.effective_permission_status
        == "HISTORICAL_REFERENCE_ONLY_NO_NEW_AUTHORIZATION"
    )
    assert resting_route.effective_permission.historical_authorization_reference_ids == (
        "AUTHREF-D047-CLEVELAND-FIVE-FIELD",
    )
    assert resting_route.blocked is False
    assert "route_contract_query" in resting_route.permitted_operations
    assert dict(crosswalk.holds)["historical_d047_authorization_scope"] == (
        "CLEVELAND_FIVE_FIELD_INTERNAL_EXPLORATORY_ONLY"
    )


def test_route_operations_holds_and_timing_evidence_are_unchanged() -> None:
    crosswalk = load_crosswalk()
    expected_permitted = {
        "da_a2_resting_v1": {
            "synthetic_training",
            "synthetic_prediction",
            "synthetic_external_evaluation",
            "shap_attribution",
            "lime_assessment",
            "bundle_packaging",
            "route_contract_query",
            "synthetic_end_to_end_exercise",
        },
        "da_a1_basic_clinical_v1": {
            "synthetic_training",
            "synthetic_prediction",
            "synthetic_external_evaluation",
            "shap_attribution",
            "lime_assessment",
            "bundle_packaging",
            "route_contract_query",
            "synthetic_end_to_end_exercise",
        },
        "da_a2_resting_labs_v1": {"route_contract_query"},
        "da_a1_clinical_core_labs_v1": {"route_contract_query"},
        "da_a2_hungary_locked_transportability_v1": {"route_contract_query"},
    }
    for route in crosswalk.routes:
        assert set(route.permitted_operations) == expected_permitted[route.route_id]
        assert set(route.forbidden_operations) == {
            "real_data_training",
            "real_external_evaluation",
            "real_bundle_inference",
            "clinical_serving",
        }
    holds = dict(crosswalk.holds)
    assert holds["gate_pt_p1_target_population_moment"] == "PENDING"
    assert holds["gate_pt_p3_formal_research"] == "CLOSED"
    assert holds["gate_pt_p5_clinical_readiness_claims"] == "NOT_MADE_PROHIBITED"
    assert holds["uci412_scientific_hold"] is True
    assert holds["new_real_data_authorization_granted_by_this_crosswalk"] is False
    assert holds["owner_verified_pre_angiography_feature_counts"] == {
        "UCI-45": 0,
        "UCI-412": 0,
    }
    assert describe_crosswalk()["timing_status_counts"] == {
        "UNVERIFIED_TIMING_PROPOSED_CHANNEL": 14,
        "UNVERIFIED_TIMING_REGISTERED_DOMAIN_CHANNEL": 16,
    }
    assert all(
        feature.acquisition.owner_verified_pre_angiography is False
        for feature in crosswalk.features
    )
    assert all(
        feature.acquisition.timing_status
        != "OWNER_VERIFIED_PRE_ANGIOGRAPHY"
        for feature in crosswalk.features
    )


def test_every_feature_cites_a_registered_permission_and_restriction_set() -> None:
    crosswalk = load_crosswalk()
    restrictions = {item.restriction_id for item in crosswalk.restrictions}
    assert len(restrictions) == 9
    for feature in crosswalk.features:
        assert feature.restriction_ids
        assert set(feature.restriction_ids) <= restrictions
        assert feature.disposition in DISPOSITION_TAXONOMY
    labs_features = [
        feature
        for feature in crosswalk.features
        if feature.feature_name in {"chol", "fbs", "FBS", "CR", "TG", "LDL", "HDL", "HB", "WBC"}
    ]
    assert len(labs_features) == 9
    for feature in labs_features:
        assert feature.disposition == "EVIDENCE_RECORDED_EXTENSION_REMAINS_BLOCKED"
    for feature in crosswalk.features:
        if feature not in labs_features:
            assert feature.disposition == "EVIDENCE_RECORDED_NO_ACTIVATION_CHANGE"


def test_blocked_uci45_labs_uci412_labs_and_hungary_stay_blocked() -> None:
    crosswalk = load_crosswalk()
    blocked = {item.item_id: item for item in crosswalk.blocked_items}
    assert set(blocked) == {
        "BLOCK-UCI45-LABS-EXTENSION",
        "BLOCK-UCI412-LABS-ROUTE",
        "BLOCK-HUNGARY-LOCKED-EVALUATION",
    }
    for item in blocked.values():
        assert item.state == "BLOCKED"
        assert item.max_permitted_operation == "route_contract_query"
        route = crosswalk.route(item.route_id)
        assert route.blocked is True
        assert route.permitted_operations == ("route_contract_query",)
        assert item.reason_restriction_id in route.restriction_ids


def test_active_routes_permit_synthetic_work_only() -> None:
    crosswalk = load_crosswalk()
    active = [route for route in crosswalk.routes if route.blocked is False]
    assert {route.route_id for route in active} == {
        "da_a2_resting_v1",
        "da_a1_basic_clinical_v1",
    }
    for route in active:
        assert route.activation_state == "ACTIVE_SYNTHETIC_ONLY"
        assert route.prediction_time_admissibility == "ADMISSIBLE_SYNTHETIC_TEST_ONLY"
        for operation in route.forbidden_operations:
            assert operation in {
                "real_data_training",
                "real_external_evaluation",
                "real_bundle_inference",
                "clinical_serving",
            }
        assert "route_contract_query" in route.permitted_operations


def test_no_result_contract_states_metadata_only() -> None:
    crosswalk = load_crosswalk()
    result = query_feature_evidence()
    payload = result.to_dict()
    assert payload["result_state"] == "METADATA_ONLY_NO_CAD_PROBABILITY_COMPUTED"
    assert payload["cad_probability_computed"] is False
    assert payload["read_only"] is True
    assert payload["files_written"] is False
    assert "probability" not in canonical_json(payload["features"]).lower()
    assert all(
        "cad_probability" not in canonical_json(feature.to_dict())
        for feature in crosswalk.features
    )


def test_every_evidence_reference_path_is_repository_relative_and_present() -> None:
    crosswalk = load_crosswalk()
    for item in crosswalk.evidence:
        assert not item.reference_path.startswith("/")
        assert ".." not in item.reference_path.split("/")
        resolved = crosswalk_module.REPO_ROOT / item.reference_path
        assert resolved.is_file()


# --------------------------------------------------------------------------- #
# Positive: deterministic metadata query                                      #
# --------------------------------------------------------------------------- #


def test_query_is_deterministic_across_calls_and_reloads() -> None:
    first = canonical_json(query_feature_evidence(dataset_id="DA-A1").to_dict())
    second = canonical_json(query_feature_evidence(dataset_id="DA-A1").to_dict())
    load_crosswalk.cache_clear()
    third = canonical_json(query_feature_evidence(dataset_id="DA-A1").to_dict())
    assert first == second == third


def test_query_by_dataset_panel_route_and_feature() -> None:
    by_dataset = query_feature_evidence(dataset_id="DA-A2").to_dict()
    assert by_dataset["matched_feature_count"] == 7
    assert by_dataset["matched_route_count"] == 3  # two DA-A2 routes + Hungary
    by_panel = query_feature_evidence(panel_id="da_a1_basic_clinical_v1").to_dict()
    assert by_panel["matched_feature_count"] == 16
    by_route = query_feature_evidence(route_id="da_a2_resting_labs_v1").to_dict()
    assert by_route["filters"]["dataset_id"] == "DA-A2"
    assert by_route["filters"]["panel_id"] == "da_a2_resting_labs_v1"
    assert by_route["matched_feature_count"] == 7
    assert by_route["matched_route_count"] == 1
    by_feature = query_feature_evidence(
        dataset_id="DA-A1", feature_name="BP"
    ).to_dict()
    assert by_feature["matched_feature_count"] == 1
    assert by_feature["features"][0]["acquisition"]["channel"] == "measurement"
    assert (
        by_feature["features"][0]["acquisition"]["timing_status"]
        == TIMING_REGISTERED
    )


def test_query_filters_by_timing_and_channel_status() -> None:
    verified = query_feature_evidence(channel_status=VERIFIED).to_dict()
    assert verified["matched_feature_count"] == 16
    proposed = query_feature_evidence(channel_status=PROPOSED).to_dict()
    assert proposed["matched_feature_count"] == 14
    promoted = query_feature_evidence(
        timing_status="OWNER_VERIFIED_PRE_ANGIOGRAPHY"
    ).to_dict()
    assert promoted["matched_feature_count"] == 0
    assert promoted["features"] == []


def test_query_zero_result_is_explicit_not_an_error() -> None:
    result = query_feature_evidence(
        dataset_id="DA-A2", feature_name="Dyspnea"
    ).to_dict()
    assert result["matched_feature_count"] == 0
    assert result["result_state"] == "METADATA_ONLY_NO_CAD_PROBABILITY_COMPUTED"


def test_query_fails_closed_on_unknown_values() -> None:
    with pytest.raises(CrosswalkQueryError) as unknown_dataset:
        query_feature_evidence(dataset_id="DA-A9")
    assert unknown_dataset.value.code == "unknown_filter_value"
    with pytest.raises(CrosswalkQueryError) as unknown_panel:
        query_feature_evidence(panel_id="da_a1_labs_forever_v9")
    assert unknown_panel.value.code == "unknown_filter_value"
    with pytest.raises(CrosswalkQueryError) as unknown_route:
        query_feature_evidence(route_id="da_a1_clinical_core_labs_v2")
    assert unknown_route.value.code == "unknown_route_id"
    with pytest.raises(CrosswalkQueryError) as unknown_feature:
        query_feature_evidence(dataset_id="DA-A1", feature_name="Cath")
    assert unknown_feature.value.code == "unknown_feature_name"
    with pytest.raises(CrosswalkQueryError) as unknown_timing:
        query_feature_evidence(timing_status="VERIFIED_TIMING")
    assert unknown_timing.value.code == "unknown_filter_value"


def test_query_rejects_ambiguous_feature_name_without_dataset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The live rosters spell the Cleveland age field ``age`` and the UCI-412 one
    # ``Age``, so no live name is ambiguous. The guard is still exercised with a
    # synthetic duplicated estimator so it cannot silently rot.
    crosswalk = load_crosswalk()
    clone = dataclasses.replace(
        crosswalk.features[0], feature_key="DA-A2:Age", dataset_id="DA-A2"
    )
    fake = dataclasses.replace(crosswalk, features=crosswalk.features + (clone,))
    monkeypatch.setattr(crosswalk_module, "load_crosswalk", lambda: fake)
    with pytest.raises(CrosswalkQueryError) as ambiguous:
        query_feature_evidence(feature_name="Age")
    assert ambiguous.value.code == "ambiguous_feature_name"
    # A single-dataset name still resolves unambiguously.
    monkeypatch.undo()
    resolved = query_feature_evidence(feature_name="age").to_dict()
    assert resolved["matched_feature_count"] == 1
    assert resolved["filters"]["feature_name"] == "age"


def test_query_rejects_conflicting_route_scope() -> None:
    with pytest.raises(CrosswalkQueryError) as conflict:
        query_feature_evidence(route_id="da_a1_basic_clinical_v1", dataset_id="DA-A2")
    assert conflict.value.code == "conflicting_filters"
    with pytest.raises(CrosswalkQueryError) as panel_conflict:
        query_feature_evidence(
            route_id="da_a1_basic_clinical_v1", panel_id="da_a1_clinical_core_labs_v1"
        )
    assert panel_conflict.value.code == "conflicting_filters"


def test_describe_is_deterministic_and_counts_match_records() -> None:
    first = canonical_json(describe_crosswalk())
    second = canonical_json(describe_crosswalk())
    assert first == second
    summary = describe_crosswalk()
    assert summary["panel_count"] == 4
    assert summary["route_count"] == 5
    assert summary["blocked_item_count"] == 3
    assert summary["feature_count"] == 30
    assert sum(summary["timing_status_counts"].values()) == 30
    assert sum(summary["effective_permission_status_counts"].values()) == 30
    assert summary["effective_permission_status_counts"] == {
        "HISTORICAL_REFERENCE_ONLY_NO_NEW_AUTHORIZATION": 5,
        "NOT_AUTHORIZED": 2,
        "SCIENTIFIC_HOLD_NEW_REAL_FIT": 23,
    }
    assert summary["result_state"] == "METADATA_ONLY_NO_CAD_PROBABILITY_COMPUTED"


def test_document_digest_binds_the_whole_document() -> None:
    document = _fresh_document()
    original = crosswalk_document_digest(document)
    assert original == load_crosswalk().document_digest_sha256
    tampered = copy.deepcopy(document)
    tampered["revision_history"][0]["change"] = "silent reword"
    assert crosswalk_document_digest(tampered) != original


def test_cli_validate_describe_and_query(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["validate"]) == 0
    validated = json.loads(capsys.readouterr().out)
    assert validated["validated"] is True
    assert validated["feature_count"] == 30

    assert main(["describe"]) == 0
    described = json.loads(capsys.readouterr().out)
    assert described["feature_count"] == 30

    assert main(["query", "--dataset-id", "DA-A1", "--feature-name", "Age"]) == 0
    queried = json.loads(capsys.readouterr().out)
    assert queried["matched_feature_count"] == 1


def test_cli_reports_validation_failure_for_tampered_document(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    tampered = _fresh_document()
    tampered["holds"]["gate_pt_p3_formal_research"] = "OPEN"
    target = tmp_path / "tampered.json"
    target.write_text(json.dumps(tampered), encoding="utf-8")
    monkeypatch.setattr(crosswalk_module, "CROSSWALK_PATH", target)
    load_crosswalk.cache_clear()
    try:
        assert main(["validate"]) == 2
        captured = capsys.readouterr()
        assert json.loads(captured.err) == {
            "validated": False,
            "code": "scientific_hold_promotion",
        }
    finally:
        monkeypatch.undo()
        load_crosswalk.cache_clear()


def test_load_crosswalk_fails_closed_on_malformed_document(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "broken.json"
    target.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(crosswalk_module, "CROSSWALK_PATH", target)
    load_crosswalk.cache_clear()
    try:
        with pytest.raises(CrosswalkValidationError) as malformed:
            load_crosswalk()
        assert malformed.value.code == "crosswalk_malformed"
    finally:
        monkeypatch.undo()
        load_crosswalk.cache_clear()


def test_module_has_no_scoring_or_network_surface() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported <= {
        "__future__",
        "argparse",
        "dataclasses",
        "functools",
        "hashlib",
        "json",
        "pathlib",
        "sys",
        "types",
        "typing",
    }, imported
    forbidden_calls = {"eval", "exec", "compile", "system", "popen", "urlopen", "socket"}
    called = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert not (called & forbidden_calls)
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "write_text" not in source.split("# Public validation entry points")[1]
    for attribute in ("write_text", "write_bytes", "mkdir", "unlink", "rename"):
        assert f".{attribute}(" not in source


def test_document_contains_no_dataset_bytes_or_patient_values() -> None:
    raw = CROSSWALK_PATH.read_text(encoding="utf-8")
    assert len(raw) < 200_000
    for token in ("<", "num=", "patient_", "MRN", "row_id"):
        assert token not in raw or token == "patient_"
    document = json.loads(raw)
    assert document["holds"]["patient_data_accessed"] is False
    assert all(
        set(feature)
        == {
            "feature_key",
            "source_id",
            "dataset_id",
            "feature_name",
            "panels",
            "definition_evidence_ids",
            "registered_source_claim",
            "acquisition",
            "permission_id",
            "effective_permission",
            "restriction_ids",
            "disposition",
        }
        for feature in document["features"]
    )


# --------------------------------------------------------------------------- #
# Fail-closed negatives: unknown fields                                       #
# --------------------------------------------------------------------------- #


def test_unknown_top_level_field_is_rejected() -> None:
    document = _fresh_document()
    document["approved_by"] = "nobody"
    with _rejected(document, "unknown_field"):
        pass


def test_missing_required_top_level_field_is_rejected() -> None:
    document = _fresh_document()
    del document["blocked_items"]
    with _rejected(document, "missing_field"):
        pass


def test_unknown_feature_field_is_rejected() -> None:
    document = _fresh_document()
    _feature(document, "DA-A1:Age")["clinically_verified"] = True
    with _rejected(document, "unknown_field"):
        pass


def test_unknown_acquisition_field_is_rejected() -> None:
    document = _fresh_document()
    _feature(document, "DA-A1:BP")["acquisition"]["timing_source"] = "owner"
    with _rejected(document, "unknown_field"):
        pass


def test_unknown_route_field_is_rejected() -> None:
    document = _fresh_document()
    _route(document, "da_a2_resting_v1")["real_data_allowed"] = True
    with _rejected(document, "unknown_field"):
        pass


def test_unknown_evidence_field_is_rejected() -> None:
    document = _fresh_document()
    document["evidence_register"][0]["owner_signature"] = "sha256:deadbeef"
    with _rejected(document, "unknown_field"):
        pass


# --------------------------------------------------------------------------- #
# Fail-closed negatives: source mismatch                                      #
# --------------------------------------------------------------------------- #


def test_feature_declaring_the_other_source_dataset_is_rejected() -> None:
    document = _fresh_document()
    feature = _feature(document, "DA-A1:Age")
    feature["dataset_id"] = "DA-A2"
    feature["feature_key"] = "DA-A2:Age"
    with _rejected(document, "source_mismatch"):
        pass


def test_feature_claiming_foreign_panels_is_rejected() -> None:
    document = _fresh_document()
    _feature(document, "DA-A2:age")["panels"] = ["da_a1_basic_clinical_v1"]
    with _rejected(document, "source_mismatch"):
        pass


def test_route_crossing_datasets_through_a_foreign_panel_is_rejected() -> None:
    document = _fresh_document()
    _route(document, "da_a2_resting_v1")["panel_id"] = "da_a1_basic_clinical_v1"
    with _rejected(document, "route_panel_mismatch"):
        pass


def test_source_block_dataset_swap_is_rejected() -> None:
    document = _fresh_document()
    source = next(item for item in document["sources"] if item["source_id"] == "UCI-412")
    source["dataset_id"] = "DA-A2"
    with _rejected(document, "source_mismatch"):
        pass


def test_registered_source_domain_claim_mismatch_is_rejected() -> None:
    document = _fresh_document()
    _feature(document, "DA-A1:BP")["registered_source_claim"]["source_domain"] = (
        "patient_history"
    )
    with _rejected(document, "source_mismatch"):
        pass


# --------------------------------------------------------------------------- #
# Fail-closed negatives: timing promotion                                     #
# --------------------------------------------------------------------------- #


def test_timing_status_promotion_is_rejected() -> None:
    document = _fresh_document()
    _feature(document, "DA-A1:Age")["acquisition"]["timing_status"] = (
        "OWNER_VERIFIED_PRE_ANGIOGRAPHY"
    )
    with _rejected(document, "timing_promotion_without_owner_evidence"):
        pass


def test_owner_verified_flag_promotion_is_rejected() -> None:
    document = _fresh_document()
    _feature(document, "DA-A1:Age")["acquisition"][
        "owner_verified_pre_angiography"
    ] = True
    with _rejected(document, "timing_promotion_without_owner_evidence"):
        pass


def test_timing_derived_from_verified_channel_is_rejected() -> None:
    document = _fresh_document()
    _feature(document, "DA-A1:BMI")["acquisition"][
        "timing_derived_from_channel_status"
    ] = True
    with _rejected(document, "timing_promotion_without_owner_evidence"):
        pass


def test_verified_channel_may_not_be_rewritten_as_owner_verified_timing() -> None:
    document = _fresh_document()
    feature = _feature(document, "DA-A1:DM")
    feature["acquisition"]["channel_status"] = VERIFIED
    feature["acquisition"]["timing_status"] = "OWNER_VERIFIED_PRE_ANGIOGRAPHY"
    with _rejected(document, "timing_promotion_without_owner_evidence"):
        pass


def test_owner_timing_evidence_class_cannot_be_introduced() -> None:
    document = _fresh_document()
    document["evidence_register"][0]["evidence_class"] = (
        "OWNER_SIGNED_ACQUISITION_CODEBOOK"
    )
    with _rejected(document, "invalid_evidence_class"):
        pass


def test_timing_capable_evidence_flag_is_rejected() -> None:
    document = _fresh_document()
    document["evidence_register"][1]["establishes_acquisition_timing"] = True
    with _rejected(document, "evidence_class_cannot_establish_timing"):
        pass


def test_owner_attested_timing_flag_is_rejected() -> None:
    document = _fresh_document()
    document["evidence_register"][2]["owner_attested_timing_evidence"] = True
    with _rejected(document, "timing_promotion_without_owner_evidence"):
        pass


def test_holds_owner_verified_count_promotion_is_rejected() -> None:
    document = _fresh_document()
    document["holds"]["owner_verified_pre_angiography_feature_counts"]["UCI-412"] = 1
    with _rejected(document, "timing_promotion_without_owner_evidence"):
        pass


def test_holds_zero_of_sixteen_statement_promotion_is_rejected() -> None:
    document = _fresh_document()
    document["holds"]["uci412_basic_clinical_owner_verified_pre_angiography"] = "16/16"
    with _rejected(document, "timing_promotion_without_owner_evidence"):
        pass


def test_timing_evidence_must_be_the_registered_gap_evidence() -> None:
    document = _fresh_document()
    _feature(document, "DA-A1:HTN")["acquisition"]["timing_evidence_ids"] = [
        "EV-UCI412-PRIMARY-OWNER"
    ]
    with _rejected(document, "evidence_set_mismatch"):
        pass


# --------------------------------------------------------------------------- #
# Fail-closed negatives: prohibited variables                                 #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "prohibited",
    [
        "Cath",
        "LAD",
        "num",
        "ca",
        "thal",
        "thalach",
        "EF-TTE",
        "wearable_ecg",
        "patient_id",
    ],
)
def test_prohibited_variable_cannot_appear_as_a_feature(prohibited: str) -> None:
    document = _fresh_document()
    clone = copy.deepcopy(_feature(document, "DA-A1:Age"))
    clone["feature_name"] = prohibited
    clone["feature_key"] = f"DA-A1:{prohibited}"
    document["features"].append(clone)
    invalid_path = f"$.features[{len(document['features']) - 1}].feature_name"
    with pytest.raises(CrosswalkValidationError) as excinfo:
        validate_crosswalk(document)
    assert excinfo.value.code in {"prohibited_feature", "unregistered_feature"}
    assert excinfo.value.path in {
        invalid_path,
        f"$.features[{len(document['features']) - 1}].feature_key",
    }


def test_unregistered_but_non_prohibited_feature_is_rejected() -> None:
    document = _fresh_document()
    clone = copy.deepcopy(_feature(document, "DA-A1:Age"))
    clone["feature_name"] = "Q Wave"
    clone["feature_key"] = "DA-A1:Q Wave"
    document["features"].append(clone)
    with _rejected(document, "unregistered_feature"):
        pass


def test_prohibited_variable_in_a_panel_roster_position_is_rejected() -> None:
    document = _fresh_document()
    feature = _feature(document, "DA-A1:DLP")
    feature["feature_name"] = "LCX"
    feature["feature_key"] = "DA-A1:LCX"
    with _rejected(document, "prohibited_feature"):
        pass


# --------------------------------------------------------------------------- #
# Fail-closed negatives: invalid status values                                #
# --------------------------------------------------------------------------- #


def test_invalid_timing_status_is_rejected() -> None:
    document = _fresh_document()
    _feature(document, "DA-A1:Age")["acquisition"]["timing_status"] = "VERIFIED"
    with _rejected(document, "invalid_timing_status"):
        pass


def test_invalid_channel_status_is_rejected() -> None:
    document = _fresh_document()
    _feature(document, "DA-A1:Age")["acquisition"]["channel_status"] = "APPROVED"
    with _rejected(document, "invalid_channel_status"):
        pass


def test_invalid_permission_status_is_rejected() -> None:
    document = _fresh_document()
    document["permissions"][0]["permission_status"] = "APPROVED_FOR_CLINICAL_USE"
    with _rejected(document, "invalid_permission_status"):
        pass


def test_invalid_activation_state_is_rejected() -> None:
    document = _fresh_document()
    _route(document, "da_a1_basic_clinical_v1")["activation_state"] = "ACTIVE_REAL_DATA"
    with _rejected(document, "invalid_activation_state"):
        pass


def test_invalid_disposition_is_rejected() -> None:
    document = _fresh_document()
    _feature(document, "DA-A1:Age")["disposition"] = "FEATURE_APPROVED"
    with _rejected(document, "invalid_disposition"):
        pass


def test_crosswalk_status_promotion_is_rejected() -> None:
    document = _fresh_document()
    document["status"] = "APPROVED"
    with _rejected(document, "status_promotion"):
        pass


def test_scientific_hold_promotion_is_rejected() -> None:
    document = _fresh_document()
    document["holds"]["gate_pt_p3_formal_research"] = "OPEN"
    with _rejected(document, "scientific_hold_promotion"):
        pass


def test_uci412_scientific_hold_lift_is_rejected() -> None:
    document = _fresh_document()
    document["holds"]["uci412_scientific_hold"] = False
    with _rejected(document, "scientific_hold_promotion"):
        pass


# --------------------------------------------------------------------------- #
# Fail-closed negatives: unauthorized route activation                        #
# --------------------------------------------------------------------------- #


def test_activating_the_uci45_labs_route_is_rejected() -> None:
    document = _fresh_document()
    route = _route(document, "da_a2_resting_labs_v1")
    route["activation_state"] = "ACTIVE_SYNTHETIC_ONLY"
    route["blocked"] = False
    route["permitted_operations"] = sorted(
        ["synthetic_training", "route_contract_query"]
    )
    with _rejected(document, "unauthorized_route_activation"):
        pass


def test_widening_uci412_labs_route_permitted_operations_is_rejected() -> None:
    document = _fresh_document()
    _route(document, "da_a1_clinical_core_labs_v1")["permitted_operations"] = [
        "route_contract_query",
        "synthetic_training",
    ]
    with _rejected(document, "unauthorized_route_activation"):
        pass


def test_narrowing_a_permitted_operation_is_also_rejected() -> None:
    document = _fresh_document()
    _route(document, "da_a2_resting_v1")["permitted_operations"] = [
        "route_contract_query"
    ]
    with _rejected(document, "unauthorized_route_activation"):
        pass


def test_permitting_a_real_data_operation_is_rejected() -> None:
    document = _fresh_document()
    _route(document, "da_a1_basic_clinical_v1")["permitted_operations"] = sorted(
        _route(document, "da_a1_basic_clinical_v1")["permitted_operations"]
        + ["real_data_training"]
    )
    with _rejected(document, "unauthorized_route_activation"):
        pass


def test_removing_a_forbidden_operation_is_rejected() -> None:
    document = _fresh_document()
    route = _route(document, "da_a2_resting_v1")
    route["forbidden_operations"] = [
        operation
        for operation in route["forbidden_operations"]
        if operation != "clinical_serving"
    ]
    with _rejected(document, "unauthorized_route_activation"):
        pass


def test_hungary_locked_route_may_not_enable_evaluation() -> None:
    document = _fresh_document()
    route = _route(document, "da_a2_hungary_locked_transportability_v1")
    route["permitted_operations"] = [
        "route_contract_query",
        "synthetic_external_evaluation",
    ]
    with _rejected(document, "unauthorized_route_activation"):
        pass


def test_sixth_route_is_rejected() -> None:
    document = _fresh_document()
    clone = copy.deepcopy(_route(document, "da_a1_basic_clinical_v1"))
    clone["route_id"] = "da_a1_basic_clinical_v2"
    document["routes"].append(clone)
    with _rejected(document, "unknown_route_id"):
        pass


def test_blocked_item_cannot_be_declared_unblocked() -> None:
    document = _fresh_document()
    document["blocked_items"][0]["state"] = "ADMISSIBLE_SYNTHETIC_TEST_ONLY"
    with _rejected(document, "unauthorized_route_activation"):
        pass


def test_blocked_item_cannot_permit_more_than_contract_query() -> None:
    document = _fresh_document()
    document["blocked_items"][1]["max_permitted_operation"] = "synthetic_training"
    with _rejected(document, "unauthorized_route_activation"):
        pass


def test_permission_cannot_authorize_real_data_execution() -> None:
    document = _fresh_document()
    document["permissions"][1][
        "real_data_execution_authorized_by_this_crosswalk"
    ] = True
    with _rejected(document, "unauthorized_activation"):
        pass


def test_permission_cannot_activate_a_scope() -> None:
    document = _fresh_document()
    document["permissions"][0]["activation_by_this_artifact"] = "D047_REACTIVATED"
    with _rejected(document, "unauthorized_activation"):
        pass


def test_route_must_keep_its_blocking_restriction() -> None:
    document = _fresh_document()
    route = _route(document, "da_a1_clinical_core_labs_v1")
    route["restriction_ids"] = [
        restriction_id
        for restriction_id in route["restriction_ids"]
        if restriction_id != "RES-UCI412-LABS-BLOCKED"
    ]
    with _rejected(document, "missing_route_restriction"):
        pass


# --------------------------------------------------------------------------- #
# Fail-closed negatives: register integrity                                   #
# --------------------------------------------------------------------------- #


def test_dangling_evidence_reference_is_rejected() -> None:
    document = _fresh_document()
    _feature(document, "DA-A1:Age")["definition_evidence_ids"] = [
        "EV-UCI412-UNKNOWN"
    ]
    with _rejected(document, "evidence_set_mismatch"):
        pass


def test_reference_path_traversal_is_rejected() -> None:
    document = _fresh_document()
    document["evidence_register"][0]["reference_path"] = "../../../etc/passwd"
    with _rejected(document, "invalid_reference_path"):
        pass


def test_reference_path_to_a_missing_document_is_rejected() -> None:
    document = _fresh_document()
    document["evidence_register"][0]["reference_path"] = "docs/research/ai8r/ABSENT.md"
    with _rejected(document, "missing_reference_document"):
        pass


def test_absolute_reference_path_is_rejected() -> None:
    document = _fresh_document()
    document["evidence_register"][0]["reference_path"] = "/etc/hosts"
    with _rejected(document, "invalid_reference_path"):
        pass


def test_duplicate_feature_key_is_rejected() -> None:
    document = _fresh_document()
    document["features"].append(copy.deepcopy(_feature(document, "DA-A1:Age")))
    with _rejected(document, "duplicate_feature_key"):
        pass


def test_missing_feature_is_rejected() -> None:
    document = _fresh_document()
    document["features"] = [
        feature
        for feature in document["features"]
        if feature["feature_key"] != "DA-A1:WBC"
    ]
    with _rejected(document, "missing_feature"):
        pass


def test_panel_cannot_be_redefined_here() -> None:
    document = _fresh_document()
    document["panels"][0]["panel_version"] = "9.9.9"
    with _rejected(document, "panel_version_mismatch"):
        pass
    document = _fresh_document()
    document["panels"][0]["registered_in"] = "research/intake/crosswalk.py"
    with _rejected(document, "panel_registry_mismatch"):
        pass


def test_feature_may_not_recite_a_foreign_permission() -> None:
    document = _fresh_document()
    _feature(document, "DA-A1:Age")["permission_id"] = (
        "PERM-UCI45-D047-HISTORICAL-REFERENCE"
    )
    with _rejected(document, "permission_mismatch"):
        pass
    document = _fresh_document()
    _feature(document, "DA-A2:chol")["permission_id"] = (
        "PERM-UCI45-D047-HISTORICAL-REFERENCE"
    )
    with _rejected(document, "permission_mismatch"):
        pass


def test_restriction_removal_from_a_feature_is_rejected() -> None:
    document = _fresh_document()
    _feature(document, "DA-A1:WBC")["restriction_ids"] = [
        "RES-UCI412-OWNER-TIMING-UNVERIFIED"
    ]
    with _rejected(document, "restriction_set_mismatch"):
        pass


def test_report_is_pinned_to_the_verified_baseline() -> None:
    document = _fresh_document()
    document["baseline_main_sha"] = "0" * 40
    with _rejected(document, "baseline_sha_mismatch"):
        pass


def test_offline_clauses_cannot_be_weakened() -> None:
    document = _fresh_document()
    document["offline_clauses"] = document["offline_clauses"][:-1]
    with _rejected(document, "offline_clause_mismatch"):
        pass


def test_no_result_contract_cannot_be_weakened() -> None:
    document = _fresh_document()
    document["no_result_contract"]["result_state"] = "CAD_PROBABILITY"
    with _rejected(document, "no_result_contract_mismatch"):
        pass


def test_taxonomy_definitions_are_frozen() -> None:
    document = _fresh_document()
    document["timing_status_taxonomy"]["OWNER_VERIFIED_PRE_ANGIOGRAPHY"] = (
        "Granted by a verified channel."
    )
    with _rejected(document, "taxonomy_definition_mismatch"):
        pass


def test_expected_holds_constant_matches_document() -> None:
    document = _fresh_document()
    assert dict(document["holds"]) == {
        key: (dict(value) if isinstance(value, dict) else value)
        for key, value in EXPECTED_HOLDS.items()
    }
    assert set(document["evidence_class_taxonomy"]) == set(EVIDENCE_CLASS_TAXONOMY)
    assert set(document["timing_status_taxonomy"]) == set(TIMING_STATUS_TAXONOMY)
    assert set(document["acquisition_channel_taxonomy"]) == set(
        ACQUISITION_CHANNEL_TAXONOMY
    )


# --------------------------------------------------------------------------- #
# Fail-closed negatives: authorization-scope widening                         #
# --------------------------------------------------------------------------- #


def test_historical_reference_cannot_be_widened_to_lab_fields() -> None:
    document = _fresh_document()
    document["authorization_references"][0]["authorized_feature_names"] = [
        "age",
        "sex",
        "cp",
        "trestbps",
        "restecg",
        "chol",
        "fbs",
    ]
    with _rejected(document, "authorization_scope_mismatch"):
        pass


def test_historical_reference_cannot_be_moved_to_another_panel_or_dataset() -> None:
    document = _fresh_document()
    document["authorization_references"][0]["authorized_panel_id"] = (
        "da_a2_resting_labs_v1"
    )
    with _rejected(document, "authorization_scope_mismatch"):
        pass
    document = _fresh_document()
    document["authorization_references"][0]["authorized_dataset_id"] = "DA-A1"
    with _rejected(document, "authorization_scope_mismatch"):
        pass


def test_historical_reference_cannot_authorize_new_execution() -> None:
    document = _fresh_document()
    document["authorization_references"][0][
        "authorizes_new_real_data_execution"
    ] = True
    with _rejected(document, "unauthorized_activation"):
        pass


def test_historical_reference_execution_status_cannot_be_reopened() -> None:
    document = _fresh_document()
    document["authorization_references"][0]["execution_status"] = (
        "ACTIVE_CURRENT_AUTHORIZATION"
    )
    with _rejected(document, "authorization_scope_mismatch"):
        pass


def test_historical_reference_label_cannot_be_rewritten() -> None:
    document = _fresh_document()
    document["authorization_references"][0]["historical_execution_label"] = (
        "SUPERVISOR_APPROVED"
    )
    with _rejected(document, "authorization_scope_mismatch"):
        pass


def test_second_authorization_reference_is_rejected() -> None:
    document = _fresh_document()
    clone = copy.deepcopy(document["authorization_references"][0])
    clone["reference_id"] = "AUTHREF-M3A-UCI412-FULL"
    document["authorization_references"].append(clone)
    with _rejected(document, "unknown_authorization_reference"):
        pass


def test_labs_permission_record_cannot_cite_the_d047_reference() -> None:
    document = _fresh_document()
    labs = next(
        item
        for item in document["permissions"]
        if item["permission_id"] == "PERM-UCI45-LABS-NOT-AUTHORIZED"
    )
    labs["historical_authorization_reference_ids"] = [
        "AUTHREF-D047-CLEVELAND-FIVE-FIELD"
    ]
    with _rejected(document, "authorization_scope_mismatch"):
        pass


def test_labs_permission_record_cannot_widen_its_covered_features() -> None:
    document = _fresh_document()
    labs = next(
        item
        for item in document["permissions"]
        if item["permission_id"] == "PERM-UCI45-LABS-NOT-AUTHORIZED"
    )
    labs["covered_feature_names"] = ["chol", "fbs", "age"]
    with _rejected(document, "authorization_scope_mismatch"):
        pass


def test_permission_record_cannot_export_an_authorized_status() -> None:
    document = _fresh_document()
    document["permissions"][0]["permission_status"] = (
        "AUTHORIZED_INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED"
    )
    with _rejected(document, "invalid_permission_status"):
        pass


def test_effective_permission_cannot_be_promoted_for_lab_features() -> None:
    document = _fresh_document()
    _feature(document, "DA-A2:chol")["effective_permission"] = {
        "effective_permission_status": "HISTORICAL_REFERENCE_ONLY_NO_NEW_AUTHORIZATION",
        "historical_authorization_reference_ids": [
            "AUTHREF-D047-CLEVELAND-FIVE-FIELD"
        ],
        "real_data_execution_authorized_by_this_crosswalk": False,
    }
    with _rejected(document, "permission_mismatch"):
        pass


def test_effective_permission_cannot_be_an_authorized_status() -> None:
    document = _fresh_document()
    _feature(document, "DA-A2:age")["effective_permission"][
        "effective_permission_status"
    ] = "AUTHORIZED_INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED"
    with _rejected(document, "invalid_effective_permission_status"):
        pass


def test_effective_permission_cannot_claim_real_data_authorization() -> None:
    document = _fresh_document()
    _feature(document, "DA-A2:age")["effective_permission"][
        "real_data_execution_authorized_by_this_crosswalk"
    ] = True
    with _rejected(document, "unauthorized_activation"):
        pass
    document = _fresh_document()
    _route(document, "da_a2_resting_v1")["effective_permission"][
        "real_data_execution_authorized_by_this_crosswalk"
    ] = True
    with _rejected(document, "unauthorized_activation"):
        pass


def test_hungary_route_cannot_cite_the_d047_reference() -> None:
    document = _fresh_document()
    _route(document, "da_a2_hungary_locked_transportability_v1")[
        "effective_permission"
    ] = {
        "effective_permission_status": "HISTORICAL_REFERENCE_ONLY_NO_NEW_AUTHORIZATION",
        "historical_authorization_reference_ids": [
            "AUTHREF-D047-CLEVELAND-FIVE-FIELD"
        ],
        "real_data_execution_authorized_by_this_crosswalk": False,
    }
    with _rejected(document, "permission_mismatch"):
        pass


def test_hungary_route_effective_status_cannot_be_promoted() -> None:
    document = _fresh_document()
    _route(document, "da_a2_hungary_locked_transportability_v1")[
        "effective_permission"
    ]["effective_permission_status"] = "AUTHORIZED_INTERNAL_EXPLORATORY"
    with _rejected(document, "invalid_effective_permission_status"):
        pass


def test_authorization_scope_cannot_grant_new_real_data_authorization() -> None:
    document = _fresh_document()
    document["authorization_scope"][
        "new_real_data_authorization_granted_by_this_crosswalk"
    ] = True
    with _rejected(document, "unauthorized_activation"):
        pass


def test_authorization_scope_statement_cannot_be_weakened() -> None:
    document = _fresh_document()
    document["authorization_scope"]["authorization_statement"] = (
        "D-047 authorizes the Cleveland study, so all Cleveland features are "
        "approved."
    )
    with _rejected(document, "authorization_scope_mismatch"):
        pass


def test_historical_scope_is_not_current_permission_flag_cannot_be_flipped() -> None:
    document = _fresh_document()
    document["authorization_scope"][
        "historical_authorization_is_not_current_permission"
    ] = False
    with _rejected(document, "authorization_scope_mismatch"):
        pass


def test_holds_cannot_grant_new_real_data_authorization() -> None:
    document = _fresh_document()
    document["holds"]["new_real_data_authorization_granted_by_this_crosswalk"] = True
    with _rejected(document, "unauthorized_activation"):
        pass


def test_holds_d047_scope_cannot_be_widened() -> None:
    document = _fresh_document()
    document["holds"]["historical_d047_authorization_scope"] = (
        "CLEVELAND_AND_LABS_INTERNAL_EXPLORATORY"
    )
    with _rejected(document, "authorization_scope_mismatch"):
        pass


def test_source_effective_permission_cannot_be_authorized() -> None:
    document = _fresh_document()
    source = next(item for item in document["sources"] if item["source_id"] == "UCI-45")
    source["effective_source_permission_status"] = (
        "AUTHORIZED_INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED"
    )
    with _rejected(document, "invalid_effective_permission_status"):
        pass


def test_feature_cannot_inherit_a_permission_that_does_not_cover_it() -> None:
    document = _fresh_document()
    # Point age at the laboratory record: the record does not cover it.
    _feature(document, "DA-A2:age")["permission_id"] = (
        "PERM-UCI45-LABS-NOT-AUTHORIZED"
    )
    with _rejected(document, "permission_mismatch"):
        pass
