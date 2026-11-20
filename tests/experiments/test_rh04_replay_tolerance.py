"""RH-04: one tightly-scoped cross-OS floating-point replay exception.

Frozen packs, response digests, statuses and refusal behavior remain exact.
"""
from __future__ import annotations

from copy import deepcopy
import json
import math

import pytest

from research.intake import offline_fixture_pack as fixtures


def _case(case_id: str = "da_a2_resting_v1"):
    return next(c for c in _pack()["cases"] if c["id"] == case_id)


def _pack():
    return json.loads(fixtures.PACK.read_text(encoding="utf-8"))


def _near(case):
    response = deepcopy(case["expected"])
    score = response["outcomes"][0]["score"]
    score["calibrated_log_odds"] = math.nextafter(
        score["calibrated_log_odds"], math.inf
    )
    assert score["calibrated_log_odds"] != (
        case["expected"]["outcomes"][0]["score"]["calibrated_log_odds"]
    )
    return response


def test_exact_replay_and_one_bounded_preapproved_measurement():
    case = _case()
    assert fixtures._approved_replay_equal(case, deepcopy(case["expected"]))
    response = _near(case)
    assert fixtures._approved_replay_equal(case, response)
    assert response != case["expected"]
    assert response["status"] == "SYNTHETIC_RESULT"


@pytest.mark.parametrize("mutation", [
    "large-drift", "nan", "infinity", "bool-as-number", "int-as-number",
    "other-calibrated-score", "raw-score", "threshold-value",
    "threshold-flag", "status", "outcome-status", "extra-field",
    "missing-score", "missing-outcome", "bool-as-integer",
])
def test_only_one_preapproved_float_field_may_vary(mutation):
    case = _case()
    response = _near(case)
    score = response["outcomes"][0]["score"]
    if mutation == "large-drift":
        score["calibrated_log_odds"] += 0.0001
    elif mutation == "nan":
        score["calibrated_log_odds"] = float("nan")
    elif mutation == "infinity":
        score["calibrated_log_odds"] = float("inf")
    elif mutation == "bool-as-number":
        score["calibrated_log_odds"] = True
    elif mutation == "int-as-number":
        score["calibrated_log_odds"] = 1
    elif mutation == "other-calibrated-score":
        score["calibrated_research_score"] = math.nextafter(
            score["calibrated_research_score"], math.inf
        )
    elif mutation == "raw-score":
        score["raw_model_score"] = math.nextafter(score["raw_model_score"], math.inf)
    elif mutation == "threshold-value":
        score["exploratory_threshold"] = math.nextafter(
            score["exploratory_threshold"], math.inf
        )
    elif mutation == "threshold-flag":
        score["exploratory_above_threshold_flag"] = not score[
            "exploratory_above_threshold_flag"
        ]
    elif mutation == "status":
        response["status"] = "ERROR"
    elif mutation == "outcome-status":
        response["outcomes"][0]["status"] = "ERROR"
    elif mutation == "extra-field":
        response["unapproved_result"] = "unsafe"
    elif mutation == "missing-score":
        del score["raw_model_score"]
    elif mutation == "missing-outcome":
        response["outcomes"].clear()
    elif mutation == "bool-as-integer":
        score["clinical_probability_claim"] = int(
            score["clinical_probability_claim"]
        )
    assert not fixtures._approved_replay_equal(case, response), mutation


def test_another_synthetic_route_has_no_numeric_exception():
    case = _case("da_a1_basic_clinical_v1")
    assert not fixtures._approved_replay_equal(case, _near(case))
    other = deepcopy(_case())
    other["id"] = "unreviewed_case"
    assert not fixtures._approved_replay_equal(other, _near(_case()))


def test_pinned_fixture_digest_and_expected_projection_unchanged():
    pack = _pack()
    from ai.research_facade import canonical_response_digest
    assert canonical_response_digest(pack) == fixtures.PACK_SHA256
    assert len(pack["cases"]) == 29
    assert _case()["expected"]["status"] == "SYNTHETIC_RESULT"


def test_full_validator_accepts_only_approved_drift_without_model_retraining(
    monkeypatch,
):
    """Exercise the real 29-case validator with controlled responses.

    Separate Windows/CI acceptance still exercises genuine synthetic models.
    """
    pack = _pack()
    responses = [deepcopy(c["expected"]) for c in pack["cases"]]
    first = next(i for i, c in enumerate(pack["cases"])
                 if c["id"] == "da_a2_resting_v1")
    responses[first] = _near(pack["cases"][first])
    emitted = iter(responses)
    sentinel = object()
    monkeypatch.setattr(fixtures, "sources", lambda _root: {"blocked": sentinel})
    monkeypatch.setattr(fixtures, "example", lambda _request, _source: next(emitted))
    assert fixtures.validate(pack) == 29


def test_full_validator_still_rejects_another_changed_numeric_output(monkeypatch):
    pack = _pack()
    responses = [deepcopy(c["expected"]) for c in pack["cases"]]
    first = next(i for i, c in enumerate(pack["cases"])
                 if c["id"] == "da_a2_resting_v1")
    responses[first] = _near(pack["cases"][first])
    score = responses[first]["outcomes"][0]["score"]
    score["raw_model_log_odds"] = math.nextafter(
        score["raw_model_log_odds"], math.inf
    )
    emitted = iter(responses)
    monkeypatch.setattr(fixtures, "sources", lambda _root: {"blocked": object()})
    monkeypatch.setattr(fixtures, "example", lambda _request, _source: next(emitted))
    with pytest.raises(ValueError, match="response mismatch: da_a2_resting_v1"):
        fixtures.validate(pack)
