"""AI-10.1 static JSON-Schema contract checks: synthetic-only status and refusal."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from ai.ai10_synthetic_transport import (
    SyntheticLockedSitePlan,
    _insufficient,
)

SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs" / "research" / "ai10_1"
    / "synthetic-locked-site.v1.schema.json"
)


@pytest.fixture(scope="module")
def schema() -> dict:
    document = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(document)
    return document


def test_synthetic_insufficient_report_matches_strict_schema(schema: dict) -> None:
    report = _insufficient(SyntheticLockedSitePlan(n_external=7), "too_few_synthetic_assessment_rows")
    Draft202012Validator(schema).validate(report)
    assert report["ledger_slot_consumed"] is False
    assert report["real_external_validation_performed"] is False


@pytest.mark.parametrize("field,wrong", [
    ("evidence_class", "CLINICALLY_VALIDATED"),
    ("clinical_use_authorized", True),
    ("real_data_execution_authorized", True),
    ("real_external_validation_performed", True),
    ("sha256", "invalid"),
    ("status", "CLINICAL_READY"),
    ("ledger_slot_consumed", True),
])
def test_schema_refuses_scope_escalation(schema: dict, field: str, wrong: object) -> None:
    report = _insufficient(SyntheticLockedSitePlan(n_external=7), "too_few_synthetic_assessment_rows")
    altered = copy.deepcopy(report)
    altered[field] = wrong
    assert not Draft202012Validator(schema).is_valid(altered)


def test_schema_rejects_private_rows_and_ledger_receipts(schema: dict) -> None:
    report = _insufficient(SyntheticLockedSitePlan(n_external=7), "too_few_synthetic_assessment_rows")
    report["patient_ids"] = ["patient-123"]
    assert not Draft202012Validator(schema).is_valid(report)
    report.pop("patient_ids")
    report["one_shot_ledger_receipt"] = {"reservation_id": "secret"}
    assert not Draft202012Validator(schema).is_valid(report)
