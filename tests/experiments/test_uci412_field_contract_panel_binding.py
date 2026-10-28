"""Live registered-panel binding for the AI-8 UCI-412 field contract.

The stdlib-only contract tests live in ``tests/audit`` and run in the minimal
audit CI environment (no numpy/scikit-learn). These checks need the full ``ai``
stack, so they live under ``tests/experiments`` and prove that the field
contract's frozen allowlists, ordering and target binding cannot drift from the
live registered :data:`ai.panels.DA_A1_BASIC_CLINICAL_PANEL`.
"""
from __future__ import annotations

import json

from ai.panels import DA_A1_BASIC_CLINICAL_PANEL
from research.intake.uci412_field_contract import (
    CONTRACT_PATH,
    FIELD_ORDER,
    NUMERIC_BINARY_FIELDS,
    NUMERIC_MEASUREMENTS,
    TEXT_BINARY_VOCABULARIES,
    load_field_contract,
)

# Regression lock for the panel contract hash that every UCI-412 bundle binds.
EXPECTED_PANEL_CONTRACT_SHA256 = (
    "efd51491c06d808ac3e02a62c45302dd9a57966b6f619b0c604df980ba71a208"
)


def test_field_order_matches_live_registered_panel_exactly():
    panel = DA_A1_BASIC_CLINICAL_PANEL
    # feature_names is the authoritative ordered allowlist; required_names is
    # an unordered collection of the same fields.
    assert tuple(FIELD_ORDER) == tuple(panel.feature_names)
    assert set(FIELD_ORDER) == set(panel.required_names)
    assert tuple(load_field_contract().ordered_fields) == tuple(panel.feature_names)
    assert len(panel.feature_names) == 16


def test_panel_identity_and_contract_hash_are_locked():
    panel = DA_A1_BASIC_CLINICAL_PANEL
    assert panel.panel_id == "da_a1_basic_clinical_v1"
    assert panel.panel_version == "1.1.0"
    assert panel.contract_sha256 == EXPECTED_PANEL_CONTRACT_SHA256
    assert len(panel.contract_sha256) == 64


def test_json_contract_panel_binding_matches_live_panel():
    document = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    binding = document["panel_binding"]
    panel = DA_A1_BASIC_CLINICAL_PANEL
    assert binding["panel_id"] == panel.panel_id
    assert binding["panel_version"] == panel.panel_version
    assert tuple(binding["ordered_feature_names"]) == tuple(panel.feature_names)
    assert binding["encoded_parameter_count"] == len(panel.feature_names)
    assert document["target_binding"]["target_id"] == panel.target_id
    assert panel.target_id == "t1.uci412.angiographic_cad_ge50.v1"


def test_measurement_units_and_ranges_match_live_panel():
    panel = DA_A1_BASIC_CLINICAL_PANEL
    for field, (unit, low, high) in NUMERIC_MEASUREMENTS.items():
        spec = panel.field_map[field]
        assert spec.role == "numeric"
        assert spec.unit == unit
        assert tuple(spec.plausible_range) == (low, high)
        assert spec.strictly_positive is True


def test_binary_encodings_match_live_panel_field_specs():
    panel = DA_A1_BASIC_CLINICAL_PANEL
    for field in NUMERIC_BINARY_FIELDS:
        spec = panel.field_map[field]
        assert spec.role == "categorical"
        assert spec.text_vocabulary is None
        assert tuple(spec.categorical_codes) == (0, 1)
    for field, vocabulary in TEXT_BINARY_VOCABULARIES.items():
        spec = panel.field_map[field]
        assert spec.role == "categorical"
        assert dict(spec.text_vocabulary) == dict(vocabulary)
        assert tuple(spec.categorical_codes) == (0, 1)


def test_every_contract_field_is_required_and_present_on_panel():
    panel = DA_A1_BASIC_CLINICAL_PANEL
    assert set(panel.optional_names) == set()
    for field in FIELD_ORDER:
        assert panel.field_map[field].required is True
