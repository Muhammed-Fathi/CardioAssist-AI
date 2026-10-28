"""Tests for the UCI-412 source-specific 16-field input contract (AI-8, Deliverable D).

This contract is a *research intake* artifact. It validates the shape of
synthetic fixture rows only and never produces a CAD probability. Every test
here is in-memory; no workbook, patient row, or real data is read or written.
"""
from __future__ import annotations

import json
import math
from typing import Any

import pytest

from ai.panels import DA_A1_BASIC_CLINICAL_PANEL
from research.intake import uci412_field_contract as contract_module
from research.intake.uci412_field_contract import (
    ACQUISITION_CHANNELS,
    CONTRACT_ID,
    CONTRACT_PATH,
    CONTRACT_REVIEW_STATUS,
    FIELD_ORDER,
    FIELD_VERIFIED_CHANNEL,
    MAPPING_STATUSES,
    NUMERIC_BINARY_FIELDS,
    NUMERIC_MEASUREMENTS,
    RESULT_STATE,
    TEXT_BINARY_VOCABULARIES,
    FieldContractError,
    FieldContractIntegrityError,
    load_field_contract,
    review_uci412_field_contract,
)
from research.uci412.feature_schema import DEFAULT_DICTIONARY

VERIFIED = "VERIFIED_REGISTERED_SOURCE_DOMAIN"
PROPOSED = "PROPOSED_FUTURE_ACQUISITION_CHANNEL"
NOT_APPLICABLE = "NOT_APPLICABLE"


# ---------------------------------------------------------------------------
# Contract document identity and cross-system agreement
# ---------------------------------------------------------------------------


def test_contract_document_loads_with_frozen_identity():
    contract = load_field_contract()
    assert contract.contract_id == CONTRACT_ID
    assert contract.status == "PROPOSED_NOT_APPROVED"
    assert contract.source_id == "UCI-412"
    assert contract.dataset_id == "DA-A1"
    assert contract.track == "A"
    assert contract.panel_id == "da_a1_basic_clinical_v1"
    assert contract.panel_version == "1.1.0"


def test_sixteen_fields_match_registered_panel_order_exactly():
    contract = load_field_contract()
    assert tuple(contract.ordered_fields) == tuple(FIELD_ORDER)
    assert tuple(FIELD_ORDER) == tuple(DA_A1_BASIC_CLINICAL_PANEL.feature_names)
    assert len(FIELD_ORDER) == 16


def test_field_kinds_partition_the_panel_without_overlap():
    contract = load_field_contract()
    assert tuple(contract.numeric_binary_fields) == tuple(sorted(NUMERIC_BINARY_FIELDS))
    assert tuple(contract.text_binary_fields) == tuple(TEXT_BINARY_VOCABULARIES)
    assert tuple(contract.numeric_measurement_fields) == tuple(NUMERIC_MEASUREMENTS)
    partition = (
        set(contract.numeric_binary_fields)
        | set(contract.text_binary_fields)
        | set(contract.numeric_measurement_fields)
    )
    assert partition == set(FIELD_ORDER)
    assert len(partition) == 16
    assert len(NUMERIC_BINARY_FIELDS) == 6
    assert len(TEXT_BINARY_VOCABULARIES) == 6
    assert len(NUMERIC_MEASUREMENTS) == 4


def test_measurements_match_feature_dictionary_units_and_ranges():
    for field in NUMERIC_MEASUREMENTS:
        unit, low, high = NUMERIC_MEASUREMENTS[field]
        spec = DEFAULT_DICTIONARY.feature(field)
        assert spec.role == "numeric"
        assert spec.unit == unit
        assert tuple(spec.plausible_range) == (low, high)


def test_binary_encoding_agrees_with_dictionary_amendment_a1():
    for field in NUMERIC_BINARY_FIELDS:
        spec = DEFAULT_DICTIONARY.feature(field)
        assert spec.kind == "binary"
        # Amendment A-1: delivered cells are numeric 0/1, not a text vocabulary.
        assert spec.source_value_encoding is not None
        assert spec.vocabulary is None
    for field, vocabulary in TEXT_BINARY_VOCABULARIES.items():
        spec = DEFAULT_DICTIONARY.feature(field)
        assert spec.kind == "binary"
        assert spec.source_value_encoding is None
        assert set(spec.vocabulary) == set(vocabulary)


def test_raw_json_document_agrees_with_frozen_code_allowlists():
    document = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    json_fields = {entry["source_name"]: entry for entry in document["fields"]}
    assert [entry["source_name"] for entry in document["fields"]] == list(FIELD_ORDER)
    for index, field in enumerate(FIELD_ORDER):
        entry = json_fields[field]
        assert entry["panel_position"] == index
        assert entry["leakage_risk"] == "NONE_EXPECTED"
        channels = {m["channel"]: m["mapping_status"] for m in entry["acquisition_source_mapping"]}
        assert set(channels) == set(ACQUISITION_CHANNELS)
        verified = [ch for ch, status in channels.items() if status == VERIFIED]
        assert verified == [FIELD_VERIFIED_CHANNEL[field]]
        if field in NUMERIC_MEASUREMENTS:
            unit, low, high = NUMERIC_MEASUREMENTS[field]
            assert entry["type"] == "numeric"
            assert entry["unit"] == unit
            assert entry["accepted_range"] == [low, high]
        elif field in NUMERIC_BINARY_FIELDS:
            assert entry["type"] == "categorical"
            assert entry["accepted_values"] == [0, 1]
        else:
            assert entry["type"] == "categorical"
            assert set(entry["accepted_values"]) == set(TEXT_BINARY_VOCABULARIES[field])


def test_target_binding_keeps_ge50_wording_and_non_equivalence_statement():
    document = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    target = document["target_binding"]
    assert target["threshold_boundary"] == "GREATER_THAN_OR_EQUAL_50_PERCENT"
    assert target["positive_token"] == "Cad"
    assert target["negative_token"] == "Normal"
    assert "related-but-not-identical" in target["non_equivalence_statement"]
    # The Cleveland >50% boundary must never be silently substituted.
    assert "greater than or equal to 50%" in target["target_definition"]


def test_load_field_contract_fails_closed_on_tampered_document(tmp_path, monkeypatch):
    real = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    tampered = json.loads(json.dumps(real))
    tampered["schema_id"] = "uci412_basic_clinical_field_contract_TAMPERED"
    fake_path = tmp_path / "tampered_contract.json"
    fake_path.write_text(json.dumps(tampered), encoding="utf-8")
    monkeypatch.setattr(contract_module, "CONTRACT_PATH", fake_path)
    load_field_contract.cache_clear()
    with pytest.raises(FieldContractIntegrityError):
        load_field_contract()
    # Restore the real, integrity-checked contract for the rest of the suite.
    monkeypatch.undo()
    load_field_contract.cache_clear()
    assert load_field_contract().contract_id == CONTRACT_ID


def test_validator_module_has_no_scoring_surface():
    assert not hasattr(contract_module, "predict")
    assert not hasattr(contract_module, "predict_proba")


# ---------------------------------------------------------------------------
# Payload helpers (flat scalar values; separate units and acquisition blocks)
# ---------------------------------------------------------------------------


def _features() -> dict[str, Any]:
    # Only the 16 registered panel fields; no target, no angio/obstruction,
    # no outcome-derived column, no weight/height.
    return {
        "Age": 53,
        "BMI": 26.4,
        "BP": 128,
        "PR": 78,
        "Sex": "Male",
        "DM": 0,
        "HTN": 1,
        "Current Smoker": 0,
        "EX-Smoker": 0,
        "FH": 0,
        "DLP": "N",
        "Typical Chest Pain": 0,
        "Atypical": "N",
        "Nonanginal": "N",
        "Exertional CP": "Y",
        "Dyspnea": "N",
    }


def _units() -> dict[str, str]:
    return {field: NUMERIC_MEASUREMENTS[field][0] for field in NUMERIC_MEASUREMENTS}


def _acquisition() -> dict[str, dict[str, str]]:
    return {
        field: {"channel": FIELD_VERIFIED_CHANNEL[field], "mapping_status": VERIFIED}
        for field in FIELD_ORDER
    }


def _payload() -> dict[str, Any]:
    return {
        "contract_version": CONTRACT_ID,
        "synthetic": True,
        "source": {"source_id": "UCI-412", "dataset_id": "DA-A1", "track": "A"},
        "feature_order": list(FIELD_ORDER),
        "features": _features(),
        "units": _units(),
        "missing_reasons": {},
        "acquisition_sources": _acquisition(),
    }


def _review(payload: dict[str, Any]):
    return review_uci412_field_contract(payload)


# ---------------------------------------------------------------------------
# Happy path and no-result guarantee
# ---------------------------------------------------------------------------


def test_valid_synthetic_payload_is_accepted_and_never_scores():
    review = _review(_payload())
    assert review.review_status == CONTRACT_REVIEW_STATUS
    assert review.result_state == RESULT_STATE
    assert review.field_order_matches_contract is True
    assert review.synthetic_only is True
    assert tuple(review.reviewed_fields) == tuple(FIELD_ORDER)
    assert review.proposed_only_fields == ()
    serialized = review.to_dict()
    assert serialized["cad_probability_computed"] is False
    assert serialized["result_state"] == RESULT_STATE
    json.dumps(serialized)  # metadata-only review is JSON serializable


def test_proposed_future_bmi_channel_is_surfaced_not_hidden():
    payload = _payload()
    payload["acquisition_sources"]["BMI"] = {
        "channel": "structured_history",
        "mapping_status": PROPOSED,
    }
    review = _review(payload)
    assert review.review_status == CONTRACT_REVIEW_STATUS
    assert review.proposed_only_fields == ("BMI",)
    assert review.to_dict()["cad_probability_computed"] is False


def test_sex_legacy_fmale_and_female_spellings_are_both_accepted():
    payload = _payload()
    for token in ("Fmale", "Female"):
        payload["features"]["Sex"] = token
        assert _review(payload).review_status == CONTRACT_REVIEW_STATUS


# ---------------------------------------------------------------------------
# Envelope and provenance rejections
# ---------------------------------------------------------------------------


def test_missing_envelope_key_is_rejected():
    payload = _payload()
    del payload["feature_order"]
    with pytest.raises(FieldContractError, match="Missing required payload metadata"):
        _review(payload)


def test_unknown_envelope_key_is_rejected():
    payload = _payload()
    payload["cad_probability"] = 0.42
    with pytest.raises(FieldContractError, match="Unknown payload envelope property"):
        _review(payload)


def test_wrong_contract_version_is_rejected():
    payload = _payload()
    payload["contract_version"] = "uci412_basic_clinical_field_contract.v9.9"
    with pytest.raises(FieldContractError, match="Unsupported contract version"):
        _review(payload)


def test_non_synthetic_payload_is_rejected():
    payload = _payload()
    payload["synthetic"] = False
    with pytest.raises(FieldContractError, match="synthetic fixtures"):
        _review(payload)


@pytest.mark.parametrize(
    "source_block",
    [
        {"source_id": "UCI-45", "dataset_id": "DA-A1", "track": "A"},
        {"source_id": "UCI-412", "dataset_id": "DA-U9", "track": "A"},
        {"source_id": "UCI-412", "dataset_id": "DA-A1", "track": "C"},
    ],
)
def test_foreign_source_identity_is_rejected(source_block):
    payload = _payload()
    payload["source"] = source_block
    with pytest.raises(FieldContractError, match="no cross-dataset harmonization"):
        _review(payload)


@pytest.mark.parametrize("track", ["B", "wearable", "track_b", "ocr", "real_patient"])
def test_prohibited_track_and_source_tokens_are_rejected(track):
    payload = _payload()
    payload["source"] = {"source_id": "UCI-412", "dataset_id": "DA-A1", "track": track}
    with pytest.raises(FieldContractError, match="prohibited"):
        _review(payload)


def test_unknown_source_block_property_is_rejected():
    payload = _payload()
    payload["source"]["cohort_id"] = "synthetic_fixture"
    with pytest.raises(FieldContractError, match="Unknown source provenance property"):
        _review(payload)


# ---------------------------------------------------------------------------
# Feature-set and ordering rejections
# ---------------------------------------------------------------------------


def test_wrong_feature_order_is_rejected():
    payload = _payload()
    payload["feature_order"] = list(reversed(FIELD_ORDER))
    with pytest.raises(FieldContractError, match="Feature order does not match"):
        _review(payload)


def test_extra_feature_order_entry_is_rejected():
    payload = _payload()
    payload["feature_order"].append("Weight")
    with pytest.raises(FieldContractError, match="Feature order does not match"):
        _review(payload)


def test_unregistered_field_is_rejected():
    payload = _payload()
    payload["features"]["Weight"] = 80
    with pytest.raises(FieldContractError, match="not part of the UCI-412 16-feature contract"):
        _review(payload)


def test_missing_required_field_is_rejected():
    payload = _payload()
    del payload["features"]["Age"]
    with pytest.raises(FieldContractError, match="16 panel fields is required"):
        _review(payload)


def test_missing_reason_block_must_be_empty_on_this_panel():
    payload = _payload()
    payload["missing_reasons"] = {"BP": "question_mark_in_source_workbook"}
    with pytest.raises(FieldContractError, match="missing reasons are not accepted"):
        _review(payload)


# ---------------------------------------------------------------------------
# Numeric binary rejections (Amendment A-1 encoding contract)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("field", sorted(NUMERIC_BINARY_FIELDS))
@pytest.mark.parametrize("bad_value", [True, False, "1", "0", 1.0, 2, -1, None])
def test_numeric_binary_rejects_non_canonical_integer(field, bad_value):
    payload = _payload()
    payload["features"][field] = bad_value
    with pytest.raises(FieldContractError):
        _review(payload)


# ---------------------------------------------------------------------------
# Text binary rejections
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("field", list(TEXT_BINARY_VOCABULARIES))
def test_text_binary_unknown_token_is_rejected(field):
    payload = _payload()
    payload["features"][field] = "maybe"
    with pytest.raises(FieldContractError, match="Unregistered categorical token"):
        _review(payload)


@pytest.mark.parametrize("field", list(TEXT_BINARY_VOCABULARIES))
def test_text_binary_numeric_value_is_rejected(field):
    payload = _payload()
    payload["features"][field] = 1
    with pytest.raises(FieldContractError, match="Unregistered categorical token"):
        _review(payload)


# ---------------------------------------------------------------------------
# Numeric measurement rejections (no silent unit conversion)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field,bad_value",
    [
        ("Age", 0),
        ("Age", 121),
        ("BMI", 9.9),
        ("BMI", 80.1),
        ("BP", 39),
        ("BP", 301),
        ("PR", 19),
        ("PR", 251),
    ],
)
def test_measurement_out_of_range_is_rejected(field, bad_value):
    payload = _payload()
    payload["features"][field] = bad_value
    with pytest.raises(FieldContractError):
        _review(payload)


@pytest.mark.parametrize(
    "field,bad_value",
    [("Age", math.nan), ("BMI", math.inf), ("BP", -math.inf)],
)
def test_measurement_non_finite_is_rejected(field, bad_value):
    payload = _payload()
    payload["features"][field] = bad_value
    with pytest.raises(FieldContractError, match="Non-finite or non-numeric"):
        _review(payload)


def test_measurement_dict_instead_of_scalar_is_rejected():
    payload = _payload()
    payload["features"]["BP"] = {"value": 128, "unit": "mmHg"}
    with pytest.raises(FieldContractError, match="Non-finite or non-numeric"):
        _review(payload)


def test_measurement_non_positive_value_is_rejected():
    payload = _payload()
    payload["features"]["PR"] = 0
    with pytest.raises(FieldContractError, match="unavailable measurement"):
        _review(payload)


def test_measurement_wrong_unit_is_rejected_without_conversion():
    payload = _payload()
    payload["units"]["BP"] = "kPa"
    with pytest.raises(FieldContractError, match="no silent conversion"):
        _review(payload)


def test_missing_unit_declaration_is_rejected():
    payload = _payload()
    del payload["units"]["BP"]
    with pytest.raises(FieldContractError, match="exactly the four numeric measurement"):
        _review(payload)


def test_unit_declared_on_binary_field_is_rejected():
    payload = _payload()
    payload["units"]["DM"] = "flag"
    with pytest.raises(FieldContractError, match="exactly the four numeric measurement"):
        _review(payload)


def test_legacy_question_mark_and_minus_nine_tokens_are_rejected():
    payload = _payload()
    payload["features"]["BP"] = "?"
    with pytest.raises(FieldContractError, match="Wrong-source marker"):
        _review(payload)
    payload["features"]["BP"] = "-9"
    with pytest.raises(FieldContractError, match="Wrong-source marker"):
        _review(payload)
    payload["features"]["BP"] = -9
    with pytest.raises(FieldContractError):  # numeric -9 is non-positive -> rejected
        _review(payload)


# ---------------------------------------------------------------------------
# Acquisition-channel governance
# ---------------------------------------------------------------------------


def test_acquisition_block_must_cover_exactly_sixteen_fields():
    payload = _payload()
    del payload["acquisition_sources"]["BP"]
    with pytest.raises(FieldContractError, match="exactly one acquisition-source block"):
        _review(payload)


def test_plain_string_acquisition_declaration_is_rejected():
    payload = _payload()
    payload["acquisition_sources"]["BP"] = "measurement"
    with pytest.raises(FieldContractError, match="channel and mapping_status only"):
        _review(payload)


def test_unknown_acquisition_channel_is_rejected():
    payload = _payload()
    payload["acquisition_sources"]["BP"] = {"channel": "fax_machine", "mapping_status": PROPOSED}
    with pytest.raises(FieldContractError, match="Unknown acquisition channel"):
        _review(payload)


def test_prohibited_ocr_channel_is_rejected():
    payload = _payload()
    payload["acquisition_sources"]["DM"] = {"channel": "ocr", "mapping_status": PROPOSED}
    with pytest.raises(FieldContractError, match="prohibited"):
        _review(payload)


def test_not_applicable_channel_cannot_supply_data():
    payload = _payload()
    payload["acquisition_sources"]["Sex"] = {
        "channel": "laboratory_document",
        "mapping_status": NOT_APPLICABLE,
    }
    with pytest.raises(FieldContractError, match="NOT_APPLICABLE channel cannot"):
        _review(payload)


def test_unverified_channel_marked_verified_is_rejected():
    payload = _payload()
    # BP's verified domain is measurement; structured_history is N/A.
    payload["acquisition_sources"]["BP"] = {
        "channel": "structured_history",
        "mapping_status": VERIFIED,
    }
    with pytest.raises(FieldContractError, match="not its registered source domain"):
        _review(payload)


def test_unknown_mapping_status_is_rejected():
    payload = _payload()
    payload["acquisition_sources"]["DM"]["mapping_status"] = "CONFIRMED_BY_OCR"
    with pytest.raises(FieldContractError, match="Unknown acquisition mapping status"):
        _review(payload)


def test_mapping_status_vocabulary_is_the_three_registered_states():
    assert set(MAPPING_STATUSES) == {VERIFIED, PROPOSED, NOT_APPLICABLE}


# ---------------------------------------------------------------------------
# Structural payload rejection
# ---------------------------------------------------------------------------


def test_payload_that_is_not_a_mapping_is_rejected():
    with pytest.raises(FieldContractError, match="payload must be a mapping"):
        review_uci412_field_contract([("Age", 1)])  # type: ignore[arg-type]
