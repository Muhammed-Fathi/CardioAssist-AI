"""The C2 resting panel binding matches the research panel contract exactly.

This verifies the ``PANEL_CONTRACT_SHA256`` constant against the authoritative
``ai.panels.DA_A2_RESTING_PANEL.contract_sha256`` (canonical sorted-key JSON).
The research ``ai`` package ``__init__`` pulls the full calibration/sklearn chain;
this test loads ``ai.panels`` as a submodule without executing that ``__init__``
so only the test-only ``numpy==1.26.4`` pin in ``backend/requirements-dev.txt``
is required (never added to ``backend/requirements.txt``).
"""

from __future__ import annotations

import sys
import types

from backend.app.term1_c2_documents import constants as C


def _load_resting_panel():
    if "ai" not in sys.modules:
        stub = types.ModuleType("ai")
        stub.__path__ = ["ai"]  # namespace stub: skip the heavy package __init__
        sys.modules["ai"] = stub
    from ai.panels import DA_A2_RESTING_PANEL

    return DA_A2_RESTING_PANEL


def test_panel_contract_sha256_matches_authoritative_panel():
    panel = _load_resting_panel()
    assert panel.contract_sha256 == C.PANEL_CONTRACT_SHA256


def test_panel_identity_and_governance_match_constants():
    panel = _load_resting_panel()
    assert panel.panel_id == C.PANEL_ID == "da_a2_resting_v1"
    assert panel.panel_version == C.PANEL_VERSION == "1.0.0"
    assert panel.dataset_id == "DA-A2"
    assert panel.stage == "resting_assessment"
    # SAFE_SCOPE never authorizes real-data execution.
    assert panel.real_data_execution_authorized is False


def test_panel_field_order_roles_and_missingness_match():
    panel = _load_resting_panel()
    assert panel.feature_names == C.PANEL_FIELD_ORDER
    assert panel.required_names == C.MANDATORY_FIELDS
    assert panel.optional_names == C.OPTIONAL_FIELDS
    for name in C.PANEL_FIELD_ORDER:
        spec = panel.field_map[name]
        rule = C.PANEL_FIELD_RULES[name]
        assert spec.role == rule.role
        assert spec.unit == rule.unit
        if rule.role == "categorical":
            assert tuple(spec.categorical_codes) == rule.codes
