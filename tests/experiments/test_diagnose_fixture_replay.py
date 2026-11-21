"""RH-04 read-only, privacy-safe cross-OS replay drift diagnostics."""
from __future__ import annotations

import json
from copy import deepcopy

import pytest

from research.intake import diagnose_fixture_replay as diagnostic


def test_exact_response_has_no_differences():
    value = {"status": "SYNTHETIC_RESULT", "outcomes": [{"score": {
        "calibrated_research_score": 0.5,
    }}]}
    assert diagnostic._describe(value, value) == []


def test_only_continuous_score_is_measured_with_existing_observation_tolerance():
    before = {"outcomes": [{"score": {"calibrated_research_score": 0.5}}]}
    near = {"outcomes": [{"score": {"calibrated_research_score": 0.50000000001}}]}
    far = {"outcomes": [{"score": {"calibrated_research_score": 0.6}}]}
    diff_near = diagnostic._describe(before, near)
    diff_far = diagnostic._describe(before, far)
    assert len(diff_near) == len(diff_far) == 1
    assert diff_near[0]["kind"] == "score_numeric"
    assert diff_near[0]["within_existing_report_comparator_tolerance"] is True
    assert diff_far[0]["within_existing_report_comparator_tolerance"] is False


def test_boolean_threshold_and_semantic_fail_closed_not_tolerated():
    expected = {"status": "SYNTHETIC_RESULT", "outcomes": [{"score": {
        "exploratory_above_threshold_flag": False,
        "exploratory_threshold": 0.5,
    }}]}
    observed = {"status": "ERROR", "outcomes": [{"score": {
        "exploratory_above_threshold_flag": True,
        "exploratory_threshold": 0.50000000001,
    }}]}
    diagnostics = diagnostic._describe(expected, observed)
    assert len(diagnostics) == 3
    assert [d["kind"] for d in diagnostics].count("semantic_mismatch") == 2
    numeric = next(d for d in diagnostics if d["kind"] == "numeric_semantic")
    assert numeric["within_existing_report_comparator_tolerance"] is None


def test_unsafe_observed_values_and_extra_keys_never_echoed():
    secret = "patient-protected-key-and-absolute-path"
    expected = {"status": "SYNTHETIC_RESULT", "outcomes": []}
    observed = {"status": secret, "outcomes": [],
                secret: {"private_key": secret}}
    diff = diagnostic._describe(expected, observed)
    rendered = json.dumps(diff, sort_keys=True)
    assert secret not in rendered
    assert "private_key" not in rendered
    assert len(diff) == 2
    assert {d["kind"] for d in diff} == {
        "semantic_mismatch", "field_set_mismatch"
    }


def test_array_length_and_type_drift_do_not_expose_contents():
    got = diagnostic._describe({"outcomes": [None]},
                               {"outcomes": [{"secret": "do not print"}, None]})
    assert {d["kind"] for d in got} == {
        "array_length_mismatch", "type_mismatch"
    }
    assert "do not print" not in json.dumps(got)


def test_in_process_golden_replay_failure_reports_only_safe_field_metadata(monkeypatch):
    """Never lose the mismatching response or echo unexpected values to CI."""
    from research.intake import offline_fixture_pack as fixtures

    pack = json.loads(fixtures.PACK.read_text(encoding="utf-8"))
    first = pack["cases"][0]
    observed = deepcopy(first["expected"])
    private_canary = "untrusted-private-value-should-never-print"
    observed["status"] = private_canary
    observed[private_canary] = {"private_key": private_canary}

    # Keep the reviewed fixture bindings/digest real, but avoid model builds:
    # only the returned (fictional) response is replaced for this negative test.
    monkeypatch.setattr(fixtures, "sources", lambda root: {"blocked": None})
    monkeypatch.setattr(fixtures, "example", lambda request, source: observed)

    with pytest.raises(ValueError, match="response mismatch:") as caught:
        fixtures.validate(pack)

    message = str(caught.value)
    assert first["id"] in message
    assert "redacted_field_diff=" in message
    assert "field_set_mismatch" in message
    assert "response.status" in message
    assert private_canary not in message
    assert "private_key" not in message
