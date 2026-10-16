"""Contract tests for the deterministic mock fixture pack.

The pack in ``shared/contracts/fixtures/`` is the executable specification of
the proposed /v1 contract. These tests check it from several independent
angles:

* every payload validates against the committed JSON Schemas;
* every expected response is reproduced exactly by the deterministic reference
  implementation;
* the explanation sum-check, the rendering metadata, the idempotency rules and
  the Track A / Track B separation hold in the fixtures themselves;
* the pack contains no patient data, no dataset, no model artifact and no
  clinical claim.
"""

from __future__ import annotations

import re
import uuid

import pytest

from conftest import (
    FIXTURES_DIR,
    iter_strings,
    sub_validator,
    validator_for,
)
import reference_contract as rc

ENDPOINT_SCHEMAS = {
    "POST /v1/predictions/cad-tabular": {
        "request": "cad_tabular_prediction.request.schema.json",
        "response": "cad_tabular_prediction.response.schema.json",
    },
    "POST /v1/monitoring/observations": {
        "request": "monitoring_observation.request.schema.json",
        "response": "monitoring_observation.response.schema.json",
    },
}

#: Keys whose free text is allowed to discuss prohibitions and negations.
EXCLUDED_TEXT_KEYS = {
    "disclaimer",
    "note",
    "definition",
    "approval_note",
    "label",
    "prevalence_note",
}

#: Phrases that must never appear in a payload outside the excluded keys.
FORBIDDEN_CLAIM_TOKENS = (
    "30-day",
    "30 day",
    "alert",
    "statin",
    "treatment",
    "recommend",
    "diagnos",
    "risk",
)

PSEUDONYMOUS_REF = re.compile(r"^pseudo_[a-z0-9_]{1,64}$")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def fixture_ids(fixtures):
    return [fixture["fixture_id"] for fixture in fixtures]


# --------------------------------------------------------------------------- #
# pack integrity
# --------------------------------------------------------------------------- #
def test_fixture_index_matches_the_fixture_directory(fixture_index):
    listed = {entry["file"] for entry in fixture_index["fixtures"]}
    on_disk = {path.name for path in FIXTURES_DIR.glob("*.json")} - {"index.json"}
    assert listed == on_disk


def test_every_fixture_declares_mock_synthetic_data(fixtures):
    for fixture in fixtures:
        assert fixture["data_class"] == "MOCK_SYNTHETIC", fixture["fixture_id"]
        assert "MOCK / SYNTHETIC DATA" in fixture["disclaimer"], fixture["fixture_id"]
        for step in fixture["steps"]:
            body = step["expected"]["body"]
            if "disclaimer" in body:
                assert "MOCK / SYNTHETIC DATA" in body["disclaimer"], fixture["fixture_id"]


def test_fixture_pack_contains_no_identifiers_or_phi(fixtures):
    for fixture in fixtures:
        for path, text in iter_strings(fixture):
            assert not EMAIL.search(text), f"{fixture['fixture_id']}{path} looks like an email"
            if path.endswith("patient_ref"):
                assert PSEUDONYMOUS_REF.match(text), f"{fixture['fixture_id']}{path}: {text}"
            if path.endswith("consent_id"):
                # Either absent, empty (the missing-consent fixture) or a mock reference.
                assert text == "" or text.startswith("consent_mock"), (
                    f"{fixture['fixture_id']}{path}: {text}"
                )


def test_fixture_pack_declares_no_personal_data_fields(fixtures):
    """No fixture may carry a field that could hold a personal identifier."""
    forbidden = {
        "name",
        "first_name",
        "last_name",
        "email",
        "phone",
        "address",
        "ssn",
        "national_id",
        "date_of_birth",
        "dob",
        "mrn",
        "nhs_number",
    }

    def keys(node):
        if isinstance(node, dict):
            for key, value in node.items():
                yield key
                yield from keys(value)
        elif isinstance(node, list):
            for item in node:
                yield from keys(item)

    for fixture in fixtures:
        for key in keys(fixture):
            assert key.lower() not in forbidden, f"{fixture['fixture_id']}: {key}"


def test_fixtures_never_name_a_dataset_or_a_real_artifact(fixtures):
    for fixture in fixtures:
        for path, text in iter_strings(fixture):
            lowered = text.lower()
            assert "uci-45" not in lowered
            assert "uci-412" not in lowered
            assert "z_alizadeh" not in lowered
            if path.endswith("training_datasets"):
                continue


def test_track_a_fixtures_declare_no_training_dataset(fixtures):
    for fixture in fixtures:
        for step in fixture["steps"]:
            body = step["expected"]["body"]
            provenance = body.get("provenance")
            if provenance is None:
                continue
            assert provenance["training_datasets"] == [], fixture["fixture_id"]
            assert (
                provenance["dataset_access_status"] == "not_applicable_no_dataset_used"
            ), fixture["fixture_id"]


def test_claims_discipline_no_risk_alert_or_treatment_language(fixtures):
    for fixture in fixtures:
        for step in fixture["steps"]:
            for path, text in iter_strings(step["expected"]["body"]):
                key = path.rsplit(".", 1)[-1]
                if key in EXCLUDED_TEXT_KEYS:
                    continue
                lowered = text.lower()
                for token in FORBIDDEN_CLAIM_TOKENS:
                    assert token not in lowered, f"{fixture['fixture_id']}{path}: {token!r}"


# --------------------------------------------------------------------------- #
# schema conformance
# --------------------------------------------------------------------------- #
def test_every_success_fixture_validates_against_its_schemas(
    fixtures, schema_documents, registry
):
    for fixture in fixtures:
        endpoint = fixture["endpoint"]
        for step in fixture["steps"]:
            status = step["expected"]["status"]
            if status >= 400:
                continue
            request_validator = validator_for(
                schema_documents[ENDPOINT_SCHEMAS[endpoint]["request"]], registry
            )
            response_validator = validator_for(
                schema_documents[ENDPOINT_SCHEMAS[endpoint]["response"]], registry
            )
            request_validator.validate(step["request"]["body"])
            response_validator.validate(step["expected"]["body"])


def test_every_error_fixture_validates_against_the_error_envelope(
    fixtures, schema_documents, registry
):
    error_validator = sub_validator(
        schema_documents["common.schema.json"], registry, "#/$defs/ErrorResponse"
    )
    seen = 0
    for fixture in fixtures:
        for step in fixture["steps"]:
            if step["expected"]["status"] < 400:
                continue
            seen += 1
            error_validator.validate(step["expected"]["body"])
    assert seen >= 8, "the pack must cover the client-triggerable error codes"


def test_every_error_code_is_documented_for_its_endpoint(
    fixtures, openapi_document
):
    documented = {}
    for path, item in openapi_document["paths"].items():
        endpoint = f"POST {path}"
        for status, codes in item["post"]["x-error-codes"].items():
            for code in codes:
                documented.setdefault((endpoint, code), set()).add(int(status))
    for fixture in fixtures:
        for step in fixture["steps"]:
            status = step["expected"]["status"]
            if status < 400:
                continue
            code = step["expected"]["body"]["error"]["code"]
            key = (fixture["endpoint"], code)
            assert key in documented, f"{code} is not documented for {fixture['endpoint']}"
            assert status in documented[key], f"{code} is documented with a different status"


def test_the_whole_error_catalogue_is_covered(fixtures, fixture_index, schema_documents):
    """Every catalogue code is either fixture-covered or explicitly server-side."""
    catalogue = set(schema_documents["common.schema.json"]["$defs"]["ErrorCode"]["enum"])
    covered = {
        step["expected"]["body"]["error"]["code"]
        for fixture in fixtures
        for step in fixture["steps"]
        if step["expected"]["status"] >= 400
    }
    server_side = set(fixture_index["server_side_only_error_codes"])
    assert covered | server_side == catalogue
    assert not (covered & server_side)


# --------------------------------------------------------------------------- #
# reference implementation
# --------------------------------------------------------------------------- #
def test_fixture_matches_the_reference_implementation(fixtures):
    for fixture in fixtures:
        contract = rc.ReferenceContract()
        for step in fixture["steps"]:
            status, body = contract.handle(
                fixture["endpoint"], step["request"]["body"], step["request"].get("headers")
            )
            assert status == step["expected"]["status"], (
                f"{fixture['fixture_id']} step {step['step']}: status {status} != {step['expected']['status']}"
            )
            assert body == step["expected"]["body"], (
                f"{fixture['fixture_id']} step {step['step']}: body mismatch"
            )


def test_audit_ids_are_reproducible_from_the_documented_rule(fixtures):
    """The mock audit id is derived, not random, so a reviewer can recompute it."""
    for fixture in fixtures:
        attempts: dict = {}
        for step in fixture["steps"]:
            body = step["expected"]["body"]
            if step["expected"]["status"] != 200:
                continue
            if body.get("idempotent_replay"):
                # A replay returns the stored audit id; no new attempt is made.
                continue
            key = (step["request"].get("headers") or {}).get("Idempotency-Key")
            attempts[key] = attempts.get(key, 0) + 1
            expected = str(
                uuid.uuid5(
                    rc.MOCK_AUDIT_NAMESPACE,
                    f"{key or '-'}|{rc.payload_hash(step['request']['body'])}|{attempts[key]}",
                )
            )
            assert body["audit_id"] == expected, f"{fixture['fixture_id']} step {step['step']}"


# --------------------------------------------------------------------------- #
# explanation semantics
# --------------------------------------------------------------------------- #
def test_explanation_sum_check_holds_in_every_fixture(fixtures):
    for fixture in fixtures:
        for step in fixture["steps"]:
            body = step["expected"]["body"]
            explanation = body.get("explanation")
            if explanation is None:
                continue
            check = explanation["sum_check"]
            computed = explanation["base_value"] + sum(
                contribution["shap"] for contribution in explanation["contributions"]
            )
            if check["applicable"]:
                assert check["passed"] is True, fixture["fixture_id"]
                assert abs(computed - check["margin"]) <= check["tolerance"], fixture["fixture_id"]
                assert abs(computed - check["computed_sum"]) <= 1e-9, fixture["fixture_id"]
                if check["margin_source"] == "score.value":
                    assert body["score"]["value"] == pytest.approx(check["margin"])
                else:
                    assert body["score"]["raw_margin"] == pytest.approx(check["margin"])
            else:
                # A local surrogate is not an exact decomposition: the check is
                # reported as not applicable instead of silently passing.
                assert check["passed"] is False, fixture["fixture_id"]
                assert explanation["method"] == "lime", fixture["fixture_id"]


def test_explanations_are_never_presented_as_probability_changes(fixtures):
    for fixture in fixtures:
        for step in fixture["steps"]:
            body = step["expected"]["body"]
            explanation = body.get("explanation")
            if explanation is None:
                continue
            assert explanation["scale"] == "log_odds_margin", fixture["fixture_id"]
            assert explanation["synthetic"] is True, fixture["fixture_id"]
            note = explanation["note"].lower()
            assert "synthetic fixture" in note, fixture["fixture_id"]
            assert "not computed by" in note, fixture["fixture_id"]
            assert "from any trained model" in note, fixture["fixture_id"]
            assert "not changes in a calibrated probability" in note, fixture["fixture_id"]
            assert "never be displayed as percentage points" in note, fixture["fixture_id"]


def test_uncalibrated_scores_carry_forbidden_percentage_rendering(fixtures):
    for fixture in fixtures:
        for step in fixture["steps"]:
            body = step["expected"]["body"]
            score = body.get("score")
            if score is None or score["type"] != "uncalibrated_score":
                continue
            rendering = score["rendering"]
            assert rendering["percent_sign_allowed"] is False, fixture["fixture_id"]
            assert rendering["display_unit"] == "unitless", fixture["fixture_id"]
            assert rendering["absolute_population_probability_claim"] is False
            assert body["calibration_id"] == "none", fixture["fixture_id"]


def test_calibrated_scores_carry_cohort_context_and_no_population_claim(fixtures):
    seen = 0
    for fixture in fixtures:
        for step in fixture["steps"]:
            body = step["expected"]["body"]
            score = body.get("score")
            if score is None or score["type"] != "calibrated_probability":
                continue
            seen += 1
            assert score["scale"] == "probability"
            assert 0.0 <= score["value"] <= 1.0
            assert "raw_margin" in score
            context = score["calibration"]["cohort_context"]
            assert context["absolute_population_probability_claim"] is False
            assert context["population_scope"] in {
                "benchmark_cohort_only_not_general_population",
                "mock_synthetic_no_cohort_exists",
            }
            assert score["rendering"]["percent_sign_allowed"] is False
    assert seen >= 1, "the pack must exercise the calibrated branch of the contract"


def test_calibrated_scores_keep_the_margin_sum_check_on_the_raw_margin(fixtures):
    for fixture in fixtures:
        for step in fixture["steps"]:
            body = step["expected"]["body"]
            score = body.get("score")
            if score is None or score["type"] != "calibrated_probability":
                continue
            check = body["explanation"]["sum_check"]
            assert check["margin_source"] == "score.raw_margin"
            assert check["margin"] == pytest.approx(score["raw_margin"])


# --------------------------------------------------------------------------- #
# response discipline
# --------------------------------------------------------------------------- #
def test_mandatory_track_a_fields_are_present(fixtures, schema_documents):
    required = set(
        schema_documents["cad_tabular_prediction.response.schema.json"]["required"]
    )
    for fixture in fixtures:
        for step in fixture["steps"]:
            body = step["expected"]["body"]
            if "score" not in body:
                continue
            assert required <= set(body), f"{fixture['fixture_id']}: {required - set(body)}"


def test_model_performance_ref_matches_the_validation_status(fixtures):
    for fixture in fixtures:
        for step in fixture["steps"]:
            body = step["expected"]["body"]
            if "validation_status" not in body:
                continue
            assert body["validation_status"] == "development_internal_only"
            assert body["model_performance_ref"].endswith("#internal_validation")


def test_target_is_cross_sectional_and_marked_provisional(fixtures):
    for fixture in fixtures:
        for step in fixture["steps"]:
            body = step["expected"]["body"]
            target = body.get("target")
            if target is None:
                continue
            assert target["time_horizon"] == "none_cross_sectional"
            assert target["status"] == "provisional_pending_approval"
            assert target["id"] == "T1_angiographic_cad_presence"


def test_monitoring_responses_carry_no_track_a_output(fixtures):
    for fixture in fixtures:
        if fixture["track"] != "B":
            continue
        for step in fixture["steps"]:
            body = step["expected"]["body"]
            if "track" in body:
                assert body["track"] == "B", fixture["fixture_id"]
            for forbidden in ("score", "target", "explanation", "model_id", "review_state"):
                assert forbidden not in body, f"{fixture['fixture_id']}: {forbidden}"


def test_every_response_declares_its_track(fixtures):
    for fixture in fixtures:
        for step in fixture["steps"]:
            body = step["expected"]["body"]
            if "track" in body:
                assert body["track"] == fixture["track"], fixture["fixture_id"]


# --------------------------------------------------------------------------- #
# idempotency, determinism, separation
# --------------------------------------------------------------------------- #
def test_idempotent_replay_returns_the_stored_response(fixtures):
    replay = next(f for f in fixtures if f["fixture_id"] == "F-05")
    first, second = replay["steps"]
    assert first["expected"]["body"]["idempotent_replay"] is False
    assert second["expected"]["body"]["idempotent_replay"] is True
    assert second["expected"]["body"]["audit_id"] == first["expected"]["body"]["audit_id"]
    stripped_first = {k: v for k, v in first["expected"]["body"].items() if k != "idempotent_replay"}
    stripped_second = {k: v for k, v in second["expected"]["body"].items() if k != "idempotent_replay"}
    assert stripped_first == stripped_second


def test_idempotency_conflict_is_reported_with_409(fixtures):
    conflict = next(f for f in fixtures if f["fixture_id"] == "F-06")
    second = conflict["steps"][1]
    assert second["expected"]["status"] == 409
    error = second["expected"]["body"]["error"]
    assert error["code"] == "idempotency_key_conflict"
    assert error["original_audit_id"] == conflict["steps"][0]["expected"]["body"]["audit_id"]


def test_identical_inputs_produce_identical_scores(fixtures):
    determinism = next(f for f in fixtures if f["fixture_id"] == "F-07")
    first, second = determinism["steps"]
    for field in ("score", "explanation", "model_id", "target"):
        assert first["expected"]["body"][field] == second["expected"]["body"][field]
    assert first["expected"]["body"]["audit_id"] != second["expected"]["body"]["audit_id"]
    assert first["expected"]["body"]["idempotent_replay"] is False
    assert second["expected"]["body"]["idempotent_replay"] is False


def test_wearable_payloads_are_rejected_for_cad_inference(fixtures):
    wearable = [f for f in fixtures if f["fixture_id"] in {"F-09a", "F-09b"}]
    assert len(wearable) == 2
    for fixture in wearable:
        step = fixture["steps"][0]
        assert step["expected"]["status"] == 422
        assert (
            step["expected"]["body"]["error"]["code"]
            == "wearable_input_not_valid_for_cad_inference"
        )
        assert "score" not in step["expected"]["body"]


def test_monitoring_accepts_wearable_sources(fixtures):
    """Track B is the only route by which wearable data may enter the platform."""
    valid = next(f for f in fixtures if f["fixture_id"] == "F-04a")
    source = valid["steps"][0]["request"]["body"]["observation"]["source"]
    assert source == "simulated_wearable"
    assert valid["steps"][0]["expected"]["status"] == 201


# --------------------------------------------------------------------------- #
# coverage of the Phase 0 fixture list
# --------------------------------------------------------------------------- #
def test_phase0_fixture_ids_are_fully_covered(fixtures):
    """Phase 0 §R2-6.6 lists F-01…F-12; every one must be covered."""
    covered = set()
    for fixture in fixtures:
        covered.update(fixture["covers_phase0_fixture_ids"])
    expected = {f"F-{index:02d}" for index in range(1, 13)}
    assert expected <= covered, f"uncovered: {sorted(expected - covered)}"


def test_phase0_coverage_map_is_consistent_with_the_fixtures(fixtures, fixture_index):
    for entry in fixture_index["fixtures"]:
        fixture = next(f for f in fixtures if f["fixture_id"] == entry["fixture_id"])
        assert entry["covers_phase0_fixture_ids"] == fixture["covers_phase0_fixture_ids"]
        assert entry["expected_status"] == fixture["steps"][0]["expected"]["status"]
        if entry["expected_status"] >= 400:
            assert entry["error_code"] == fixture["steps"][0]["expected"]["body"]["error"]["code"]
        else:
            assert entry["error_code"] is None


def test_mandatory_field_snapshot_fixture_matches_the_schema(fixtures, schema_documents):
    """F-10 pins the exact key set of a Track-A response."""
    snapshot = next(f for f in fixtures if f["fixture_id"] == "F-10")
    body = snapshot["steps"][0]["expected"]["body"]
    required = set(
        schema_documents["cad_tabular_prediction.response.schema.json"]["required"]
    )
    assert set(snapshot["mandatory_response_fields"]) == set(body.keys())
    assert set(snapshot["mandatory_response_fields"]) == required
