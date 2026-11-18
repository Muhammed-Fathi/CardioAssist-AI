"""Offline evidence-file contract, NOT an HTTP schema or a backend provider.

Run in the existing jsonschema-equipped contract job without importing the AI
stack; tests/experiments exercises the live generator in the research-only job.
"""

import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

ROOT = Path(__file__).resolve().parents[2] / "docs/research/ai12_1"
SCHEMA = json.loads((ROOT / "evidence-pack.v1.schema.json").read_text(encoding="utf-8"))
EXAMPLE = json.loads((ROOT / "linux-example.v1.json").read_text(encoding="utf-8"))


def test_released_pack_and_standalone_card_match_versioned_schema():
    Draft202012Validator.check_schema(SCHEMA)
    Draft202012Validator(SCHEMA).validate(EXAMPLE)
    Draft202012Validator({"$defs": SCHEMA["$defs"], "$ref": "#/$defs/card"}).validate(
        EXAMPLE["model_card"]
    )


@pytest.mark.parametrize(
    "path,value",
    [
        (("schema_version",), "v0"),
        (("patient_records",), []),
        (("report", "stage_results", 4, "detail", "score_produced"), True),
        (("report", "stage_results", 6, "detail", "cases", 0, "status"), "SYNTHETIC_RESULT"),
        (("inference", "artifact", "verification", "producer_authenticated"), False),
        (("model_card", "protocol", "training_config_sha256"), "not-a-digest"),
        (("model_card", "governance", "clinical_use_authorized"), True),
        (
            ("inference", "records", 0, "shap_explanation", "additive_on_calibrated_probability"),
            True,
        ),
        (("inference", "records", 0, "lime_explanation", "is_exact_shapley"), True),
        (
            ("inference", "records", 0, "score", "score_kind"),
            "RAW_MODEL_PROBABILITY_NOT_CALIBRATED",
        ),
    ],
)
def test_schema_rejects_mislabeling_and_scope_drift(path, value):
    candidate = copy.deepcopy(EXAMPLE)
    parent = candidate
    for key in path[:-1]:
        parent = parent[key]
    parent[path[-1]] = value
    assert not Draft202012Validator(SCHEMA).is_valid(candidate)


def test_no_fake_calibration_or_unavailable_explanation():
    score = copy.deepcopy(EXAMPLE["inference"]["records"][0]["score"])
    check = Draft202012Validator({"$defs": SCHEMA["$defs"], "$ref": "#/$defs/score"})
    score.update(
        score_kind="RAW_MODEL_PROBABILITY_NOT_CALIBRATED",
        calibrated_research_score=None,
        calibrated_log_odds=None,
        calibration_reason="calibrator_status_identity_constant_fallback",
    )
    check.validate(score)
    score["calibrated_research_score"] = score["raw_model_score"]
    assert not check.is_valid(score)

    candidate = copy.deepcopy(EXAMPLE)
    lime = candidate["inference"]["records"][0]["lime_explanation"]
    lime.update(
        provided=False,
        reason="not_requested_by_caller",
        scale=None,
        quality_status=None,
        explanation=None,
        is_reliable_for_interpretation=None,
        comparable_with_shap_scale=None,
        explained_quantity=None,
    )
    Draft202012Validator(SCHEMA).validate(candidate)
    lime["quality_status"] = "ACCEPTABLE_LOCAL_APPROXIMATION"
    assert not Draft202012Validator(SCHEMA).is_valid(candidate)
