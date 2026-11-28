"""DA-A2 panel contract unit tests (checkpoint §7).

The backend re-declares the research validator's rules stdlib-only; these
tests pin the frozen literals: mandatory history, units, categorical domains,
the four-term missing-reason vocabulary, the reason/unit derivation rules and
the prohibited-field union (no leakage of echo/leakage/identifier columns).
"""

from __future__ import annotations

import pytest

from backend.app.term1 import constants
from backend.app.term1.errors import ApiError
from backend.app.term1.panel import (
    CATEGORICAL_CODES,
    MANDATORY_FIELDS,
    MISSING_REASONS,
    OPTIONAL_FIELDS,
    PANEL_FIELDS,
    PROHIBITED_FIELDS,
    UNIT_FIELDS,
    normalize_panel_fields,
    panel_contract_ok,
)

FULL = {
    "age": 54.0,
    "sex": 0,
    "cp": 1,
    "trestbps": 130.0,
    "restecg": 0,
}
FULL_UNITS = {"age": "years", "trestbps": "mmHg"}


def _norm(inputs, units, reasons):
    return normalize_panel_fields(
        inputs, units, reasons, allow_absent_mandatory=False,
        strict_reasons=True,
    )


def _expect(code, fn, *args):
    with pytest.raises(ApiError) as excinfo:
        fn(*args)
    assert excinfo.value.code == code, excinfo.value.code


# --- frozen literals --------------------------------------------------------
def test_frozen_panel_contract_literals():
    assert PANEL_FIELDS == ("age", "sex", "cp", "trestbps", "restecg")
    assert MANDATORY_FIELDS == ("age", "sex", "cp")
    assert OPTIONAL_FIELDS == ("trestbps", "restecg")
    assert UNIT_FIELDS == {"age": "years", "trestbps": "mmHg"}
    assert CATEGORICAL_CODES["sex"] == frozenset({0, 1})
    assert CATEGORICAL_CODES["cp"] == frozenset({1, 2, 3, 4})
    assert CATEGORICAL_CODES["restecg"] == frozenset({0, 1, 2})
    assert MISSING_REASONS == frozenset(
        {"not_measured", "not_available_at_time", "unknown", "not_provided"}
    )
    assert constants.PANEL_ID == "da_a2_resting_v1"
    assert constants.PANEL_VERSION == "1.0.0"
    assert constants.PANEL_CONTRACT_SHA256 == (
        "c18ad4cd2cf08f6fefb2e340573760da7000bc1d8eb4ad38783b873c018e57b8"
    )
    assert panel_contract_ok("da_a2_resting_v1", "1.0.0")
    assert not panel_contract_ok("other_panel", "1.0.0")
    assert not panel_contract_ok("da_a2_resting_v1", "2.0.0")


def test_prohibited_field_union_blocks_leakage_columns():
    # Echo, UCI-45 and wearable/leakage columns must be rejected by name
    # (lower-cased literals copied from the research sources).
    for name in (
        "ef-tte", "region rwma", "vhd",            # ECHO_COLUMNS
        "chol", "fbs", "thalach", "exang",         # UCI-45 leftovers
        "oldpeak", "slope", "target", "cath",
        "lad", "lcx", "rca", "ca", "thal", "num",
        "patient_id", "patient_ref", "mrn", "ccf",
        "spo2", "hrv", "ppg", "step_count", "sleep_duration",
        "syntax_score", "stenosis_percent",
        "wearable_heart_rate", "monitoring_observation",
    ):
        assert name in PROHIBITED_FIELDS, name


# --- happy path -------------------------------------------------------------
def test_complete_panel_normalizes_and_passes_stage():
    inputs, units, reasons, stage = _norm(dict(FULL), dict(FULL_UNITS), {})
    assert inputs == FULL
    assert units == FULL_UNITS
    assert reasons == {}  # present values drop their reasons
    assert stage is True


def test_absent_optional_defaults_and_mandatory_rules():
    inputs, units, reasons, stage = _norm(
        {"age": 54.0, "sex": 1, "cp": 2}, {"age": "years"}, {}
    )
    assert stage is False
    # absent optionals become explicit nulls with the structural reason;
    # absent numerical units are dropped
    assert inputs == {
        "age": 54.0,
        "sex": 1,
        "cp": 2,
        "trestbps": None,
        "restecg": None,
    }
    assert units == {"age": "years"}
    assert reasons == {"trestbps": "not_provided", "restecg": "not_provided"}

    # explicit null mandatory value -> invalid (omit it instead)
    _expect("invalid_panel_input", _norm, {"age": None, "sex": 1, "cp": 2}, {}, {})


def test_missing_mandatory_is_invalid_in_strict_mode():
    _expect("invalid_panel_input", _norm, {"sex": 1, "cp": 2}, {}, {})
    # H1b's permissive mode allows the incomplete draft state
    inputs, units, reasons, stage = normalize_panel_fields(
        {"sex": 1, "cp": 2}, {}, {}, allow_absent_mandatory=True,
        strict_reasons=False,
    )
    assert stage is False
    assert inputs == {"sex": 1, "cp": 2, "trestbps": None, "restecg": None}
    assert reasons == {"trestbps": "not_provided", "restecg": "not_provided"}


def test_categorical_domains():
    _expect(
        "invalid_panel_input", _norm,
        {"age": 1.0, "sex": 2, "cp": 1, "trestbps": 1.0, "restecg": 0},
        dict(FULL_UNITS), {},
    )
    _expect(
        "invalid_panel_input", _norm,
        {"age": 1.0, "sex": 0, "cp": 9, "trestbps": 1.0, "restecg": 0},
        dict(FULL_UNITS), {},
    )
    _expect(
        "invalid_panel_input", _norm,
        {"age": 1.0, "sex": 0, "cp": 1, "trestbps": 1.0, "restecg": 3},
        dict(FULL_UNITS), {},
    )
    # booleans are not integer codes
    _expect(
        "invalid_panel_input", _norm,
        {"age": 1.0, "sex": True, "cp": 1, "trestbps": 1.0, "restecg": 0},
        dict(FULL_UNITS), {},
    )


def test_numerical_domains_and_units():
    _expect("invalid_panel_input", _norm, dict(FULL, age=-3), dict(FULL_UNITS), {})
    _expect("invalid_panel_input", _norm, dict(FULL, trestbps=0.0), dict(FULL_UNITS), {})
    _expect("invalid_panel_input", _norm, dict(FULL, age=True), dict(FULL_UNITS), {})
    _expect(
        "invalid_panel_input", _norm,
        dict(FULL), dict(FULL_UNITS, trestbps="cmHg"), {},
    )
    # Units supplied without a present numerical value are invalid.
    _expect(
        "invalid_panel_input",
        _norm,
        {"age": 54.0, "sex": 0, "cp": 1},
        {"age": "years", "trestbps": "mmHg"},
        {},
    )
    # Very large JSON integers must be a closed 422, not float overflow/500.
    _expect(
        "invalid_panel_input",
        _norm,
        {"age": 10**1000, "sex": 0, "cp": 1, "trestbps": 130.0, "restecg": 0},
        dict(FULL_UNITS),
        {},
    )


def test_reason_rules():
    # reason on a present value (strict S1 semantics)
    _expect(
        "missing_reason_mismatch", _norm,
        dict(FULL), dict(FULL_UNITS), {"age": "not_measured"},
    )
    # unknown reason token on an absent optional
    _expect(
        "invalid_panel_input", _norm,
        {"age": 54.0, "sex": 0, "cp": 1}, {"age": "years"},
        {"trestbps": "because"},
    )
    # explicit null optional with a reason keeps the reason
    inputs, units, reasons, stage = _norm(
        {"age": 54.0, "sex": 0, "cp": 1, "trestbps": None},
        {"age": "years"},
        {"trestbps": "not_measured"},
    )
    assert inputs["trestbps"] is None
    assert reasons == {"trestbps": "not_measured", "restecg": "not_provided"}
    # null optional without a measurement reason is rejected. `not_provided`
    # is reserved for structural omission and cannot describe an explicit null.
    for reason_map in ({}, {"restecg": "not_provided"}):
        _expect(
            "missing_reason_mismatch", _norm,
            {"age": 54.0, "sex": 0, "cp": 1, "restecg": None},
            {"age": "years"}, reason_map,
        )


def test_unknown_panel_fields_are_invalid():
    _expect("invalid_panel_input", _norm, dict(FULL, foo=1), dict(FULL_UNITS), {})
    _expect(
        "prohibited_clinical_field", _norm,
        dict(FULL, **{"ef-tte": 55}), dict(FULL_UNITS), {},
    )
    _expect(
        "prohibited_clinical_field", _norm,
        dict(FULL, patient_id="p-1"), dict(FULL_UNITS), {},
    )
