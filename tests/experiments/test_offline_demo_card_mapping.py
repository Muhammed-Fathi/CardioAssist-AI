"""RH-04.6 consumer-card map: functional safety and source-binding checks."""
from __future__ import annotations

from copy import deepcopy
import json
import subprocess
import sys

import pytest

from research.intake import offline_demo_card_mapping as cards


def mapping_document():
    return json.loads(cards.MAPPING_PATH.read_text(encoding="utf-8"))


def fixture_pack():
    return json.loads(cards.OFFLINE_PACK_PATH.read_text(encoding="utf-8"))


def test_checked_in_mapping_validates_all_twenty_nine_offline_cases():
    document = cards.load_mapping()
    pack = fixture_pack()

    assert cards.validate(document) == 29
    assert document["persistent_warning"] == "Synthetic research fixture — not clinical"
    assert [card["case_id"] for card in document["offline_case_cards"]] == [
        case["id"] for case in pack["cases"]
    ]
    assert {card["status"] for card in document["offline_case_cards"]} == set(
        cards.OFFLINE_STATUSES
    )
    assert all(
        card["presentation_contract_id"] == cards.OFFLINE_PRESENTATION_ID
        for card in document["offline_case_cards"]
    )


def test_each_card_hashes_the_exact_safe_fixture_projection_and_status():
    document = cards.load_mapping()
    source_cases = {case["id"]: case for case in fixture_pack()["cases"]}

    for card in document["offline_case_cards"]:
        expected = source_cases[card["case_id"]]["expected"]
        assert card["status"] == expected["status"]
        assert card["expected_projection_sha256"] == cards._canonical_sha256(expected)


def test_offline_and_mock_presentations_are_explicitly_different_contracts():
    document = cards.load_mapping()
    mock = document["mock_synthetic_backend"]

    assert document["offline_research"]["presentation_contract_id"] != mock[
        "presentation_contract_id"
    ]
    assert mock["presentation_contract_id"] == cards.MOCK_PRESENTATION_ID
    assert mock["data_class"] == "MOCK_SYNTHETIC"
    assert mock["approved_http_contract"] == "POST /v1/predictions/cad-tabular"
    assert mock["offline_case_links_forbidden"] is True
    assert "score.value" not in mock["allowed_display_fields"]
    assert "outcomes.score.calibrated_research_score" not in mock["allowed_display_fields"]


def test_mock_card_selects_only_the_reviewed_f01_static_example():
    document = cards.load_mapping()
    binding = document["mock_synthetic_backend"]["approved_mock_fixture"]

    assert binding == {
        "fixture_id": "F-01",
        "file": "F-01-cad-tabular-valid-mock-clinical-v1.json",
        "endpoint": "POST /v1/predictions/cad-tabular",
        "expected_http_status": 200,
        "model_id": "mock_model_a_v0.1.0",
        "feature_schema_id": "mock_clinical_v1",
        "data_class": "MOCK_SYNTHETIC",
        "static_display_only": True,
    }
    assert document["source_digests"]["mock_f01_fixture_bytes_sha256"] == cards._bytes_sha256(
        cards.MOCK_STATIC_FIXTURE_PATH
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda doc: doc["source_digests"].__setitem__(
            "offline_fixture_pack_canonical_sha256", "0" * 64
        ),
        lambda doc: doc["offline_case_cards"].pop(),
        lambda doc: doc["offline_case_cards"][0].__setitem__(
            "presentation_contract_id", cards.MOCK_PRESENTATION_ID
        ),
        lambda doc: doc["offline_case_cards"][0].__setitem__("status", "ERROR"),
        lambda doc: doc["offline_research"]["status_rules"]["SYNTHETIC_RESULT"][
            "allowed_display_fields"
        ].__setitem__(0, "records.features"),
        lambda doc: doc["mock_synthetic_backend"]["allowed_display_fields"].append(
            "score.value"
        ),
        lambda doc: doc["source_digests"].__setitem__(
            "mock_f01_fixture_bytes_sha256", "0" * 64
        ),
        lambda doc: doc["mock_synthetic_backend"]["approved_mock_fixture"].__setitem__(
            "fixture_id", "F-404"
        ),
        lambda doc: doc["mock_synthetic_backend"]["approved_mock_fixture"].__setitem__(
            "file", "F-01b-cad-tabular-valid-mock-clinical-v2.json"
        ),
        lambda doc: doc["mock_synthetic_backend"]["approved_mock_fixture"].__setitem__(
            "file", "../../outside-fixture.json"
        ),
        lambda doc: doc["mock_synthetic_backend"]["approved_mock_fixture"].__setitem__(
            "model_id", "mock_model_b_v0.1.0"
        ),
        lambda doc: doc["mock_synthetic_backend"]["approved_mock_fixture"].__setitem__(
            "feature_schema_id", "mock_clinical_v2"
        ),
        lambda doc: doc["mock_synthetic_backend"]["approved_mock_fixture"].__setitem__(
            "static_display_only", False
        ),
        lambda doc: doc["mock_synthetic_backend"]["approved_mock_fixture"].__setitem__(
            "expected_http_status", 503
        ),
        lambda doc: doc.__setitem__("persistent_warning", "Synthetic research fixture"),
    ],
    ids=(
        "stale-source-digest",
        "missing-case",
        "offline-case-routed-to-mock",
        "case-status-drift",
        "raw-feature-field-allowlisted",
        "mock-score-value-allowlisted",
        "f01-digest-corrupted",
        "unknown-mock-fixture-id",
        "mock-fixture-file-swapped",
        "mock-fixture-path-traversal",
        "mock-fixture-model-swapped",
        "mock-fixture-schema-swapped",
        "mock-fixture-not-static",
        "mock-fixture-status-altered",
        "warning-removed",
    ),
)
def test_validator_fails_closed_for_stale_unsafe_or_cross_contract_mapping(mutate):
    document = deepcopy(mapping_document())
    mutate(document)

    with pytest.raises(cards.DemoCardMappingError):
        cards.validate(document)


def test_validator_rejects_corrupted_f01_response_binding(monkeypatch):
    """A changed approved-example response cannot silently relabel the mock card."""
    read_json = cards._read_json

    def corrupted_read_json(path):
        document = read_json(path)
        if path == cards.MOCK_STATIC_FIXTURE_PATH:
            document["steps"][0]["expected"]["body"]["data_class"] = "NOT_MOCK_SYNTHETIC"
        return document

    monkeypatch.setattr(cards, "_read_json", corrupted_read_json)
    with pytest.raises(cards.DemoCardMappingError):
        cards.validate(mapping_document())


def test_status_rules_define_exactly_four_safe_outcomes_and_refusal_behaviors():
    document = cards.load_mapping()
    rules = document["offline_research"]["status_rules"]

    assert tuple(rules) == cards.OFFLINE_STATUSES
    for status, rule in rules.items():
        assert tuple(rule["allowed_display_fields"]) == cards.STATUS_ALLOWED_FIELDS[status]
        assert tuple(rule["refusal_reason_fields"]) == cards.STATUS_REFUSAL_REASON_FIELDS[
            status
        ]
        assert rule["blocked_state_behavior"]
        assert rule["error_behavior"]
        assert rule["numeric_rendering"]
        for allowed in rule["allowed_display_fields"]:
            assert not any(
                cards._paths_overlap(allowed, forbidden)
                for forbidden in cards.FORBIDDEN_DISPLAY_FIELDS
            )


def test_validator_is_standalone_and_does_not_require_the_research_ml_stack():
    completed = subprocess.run(
        [sys.executable, "-m", "research.intake.offline_demo_card_mapping"],
        cwd=cards.REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert completed.stdout.strip() == "29 offline demo cards verified: 1.0.1"

    isolated = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import research.intake.offline_demo_card_mapping as mapping; "
                "assert mapping.validate() == 29; "
                "assert not any(name == 'ai' or name.startswith('ai.') for name in sys.modules); "
                "assert not any(name == 'backend' or name.startswith('backend.') for name in sys.modules); "
                "print('STDLIB_ONLY')"
            ),
        ],
        cwd=cards.REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert isolated.stdout.strip() == "STDLIB_ONLY"
