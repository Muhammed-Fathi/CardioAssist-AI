"""AI-10.1 schema tests use static invented fixtures and NO ML dependencies."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

SCHEMA_PATH = (
    Path(__file__).resolve().parents[2] / "docs" / "research"
    / "ai10_1" / "synthetic-locked-site.v1.schema.json"
)
HASH = "a" * 64
EVIDENCE = "SYNTHETIC_TRANSPORT_TEST_NOT_EXTERNAL_VALIDATION"


@pytest.fixture(scope="module")
def schema() -> dict:
    document = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(document)
    return document


def insufficient_fixture() -> dict:
    return {
        "schema_version": "cardioassist.ai.synthetic_locked_site/v1",
        "status": "INSUFFICIENT_EVIDENCE",
        "evidence_class": EVIDENCE,
        "plan_sha256": HASH, "sha256": HASH,
        "n_external": 7, "n_positive": 0, "n_negative": 0,
        "reason": "too_few_synthetic_assessment_rows",
        "ledger_slot_consumed": False,
        "clinical_use_authorized": False,
        "real_data_execution_authorized": False,
        "real_external_validation_performed": False,
    }


def complete_fixture() -> dict:
    return {
        "schema_version": "cardioassist.ai.synthetic_locked_site/v1",
        "status": "SYNTHETIC_LOCKED_SITE_EXERCISE_COMPLETE",
        "evidence_class": EVIDENCE,
        "sha256": HASH, "plan_sha256": HASH,
        "plan_reference": "CAI-AI10.1-FABRICATED-LOCKED-SITE-V1",
        "target_id": "t1.uci45.angiographic_cad_gt50.v1",
        "panel_id": "da_a2_resting_v1",
        "panel_sha256": HASH,
        "seed": 20261118, "n_development": 96,
        "n_external": 48, "n_positive": 35, "n_negative": 13,
        "fabricated_identity_check": {
            "status": "GENERATED_IDS_NONOVERLAPPING_NOT_REAL_PATIENT_INDEPENDENCE",
            "development_count": 96, "external_count": 48,
            "development_sha256": HASH, "external_sha256": HASH,
            "overlap_count": 0,
        },
        "invented_site_shift": "invented only",
        "model_metadata_binding_sha256": HASH,
        "selected_model_family": "l2_logistic_regression",
        "ledger_status": "COMPLETED",
        "ledger_slot_consumed": True,
        "model_tuned_on_external": False,
        "uncalibrated_roc_auc": 0.6,
        "uncalibrated_brier_score": 0.25,
        "transport_calibrated_roc_auc": 0.6,
        "transport_calibrated_brier_score": 0.24,
        "real_hungary_accessed": False,
        "clinical_use_authorized": False,
        "real_data_execution_authorized": False,
        "real_external_validation_performed": False,
        "limitations": ["Entirely fabricated contract fixture; no external clinical validation."],
    }


def test_static_report_variants_conform_to_schema(schema: dict) -> None:
    Draft202012Validator(schema).validate(insufficient_fixture())
    Draft202012Validator(schema).validate(complete_fixture())


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
    report = insufficient_fixture()
    altered = copy.deepcopy(report)
    altered[field] = wrong
    assert not Draft202012Validator(schema).is_valid(altered)


def test_schema_rejects_private_rows_and_ledger_receipts(schema: dict) -> None:
    report = insufficient_fixture()
    report["patient_ids"] = ["patient-123"]
    assert not Draft202012Validator(schema).is_valid(report)
    report.pop("patient_ids")
    report["one_shot_ledger_receipt"] = {"reservation_id": "secret"}
    assert not Draft202012Validator(schema).is_valid(report)


def test_complete_variant_rejects_wrong_panel_or_model_status(schema: dict) -> None:
    report = complete_fixture()
    report["panel_id"] = "da_a1_basic_clinical_v1"
    assert not Draft202012Validator(schema).is_valid(report)
    report = complete_fixture()
    report["ledger_status"] = "RESERVED"
    assert not Draft202012Validator(schema).is_valid(report)
