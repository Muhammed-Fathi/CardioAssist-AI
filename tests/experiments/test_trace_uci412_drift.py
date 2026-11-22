"""Privacy and strictness tests for RH-04 UCI-412 synthetic stage probe."""
from __future__ import annotations

import json
from copy import deepcopy

from research.intake import trace_uci412_drift as probe


def _fake_score():
    return {
        "raw_model_score": 0.3,
        "raw_model_log_odds": -0.5,
        "calibrated_research_score": 0.4,
        "calibrated_log_odds": -0.7,
        "protected_value": "patient-key-DO-NOT-ECHO",
    }


def test_exact_fields_metadata_omits_values_and_unapproved_fields():
    score = _fake_score()
    result = probe._field_observations(score, score)
    assert set(result) == set(probe.NUMERIC_FIELDS)
    assert all(v["exact_binary64"] is True for v in result.values())
    assert "patient-key-DO-NOT-ECHO" not in json.dumps(result)
    assert "-0.7" not in json.dumps(result)
    assert "0.3" not in json.dumps(result)


def test_finite_low_bit_drift_detected_without_revealing_scores():
    baseline = _fake_score()
    altered = deepcopy(baseline)
    import math
    altered["calibrated_log_odds"] = math.nextafter(
        baseline["calibrated_log_odds"], -math.inf
    )
    result = probe._field_observations(baseline, altered)
    assert not result["calibrated_log_odds"]["exact_binary64"]
    assert result["calibrated_log_odds"]["within_report_tolerance_diagnostic_only"] is True
    assert "absolute_delta" in result["calibrated_log_odds"]
    assert result["raw_model_score"]["exact_binary64"]
    output = json.dumps(result)
    assert "patient-key-DO-NOT-ECHO" not in output
    assert "-0.7" not in output


def test_boolean_and_nonfinite_never_accepted_as_exact_binary64():
    assert not probe._same_float(True, 1.0)
    assert not probe._same_float(float("nan"), float("nan"))
    assert not probe._same_float(float("inf"), float("inf"))
    assert probe._same_float(0.5, 0.5)
