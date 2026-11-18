"""AI-10.1 locked-site rehearsal: invented fixtures only, no real data or site."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


import pytest

from ai.ai10_synthetic_transport import (
    EVIDENCE,
    SyntheticLockedSitePlan,
    _fabricate,
    _sha,
    run_ai10_synthetic_locked_site,
    validate_fake_identities,
)
from ai.errors import CohortGovernanceError
from ai.training import ExternalEvaluationLedger


def test_plan_is_immutable_and_version_bound() -> None:
    plan = SyntheticLockedSitePlan()
    assert plan.sha256 == SyntheticLockedSitePlan().sha256
    assert len(plan.sha256) == 64
    with pytest.raises(ValueError, match="panel"):
        SyntheticLockedSitePlan(panel_sha256="0" * 64)
    with pytest.raises(ValueError, match="protocol"):
        SyntheticLockedSitePlan(reference="real_hungary")
    with pytest.raises(ValueError, match="target|endpoint"):
        SyntheticLockedSitePlan(target_id="future-heart-attack")
    with pytest.raises(ValueError, match="seed"):
        SyntheticLockedSitePlan(seed=0)


def test_fake_independence_does_not_accept_duplicates_or_real_ids() -> None:
    a = ["ai10_fake_a1", "ai10_fake_a2"]
    b = ["ai10_fake_b1", "ai10_fake_b2"]
    good = validate_fake_identities(a, b)
    assert good["overlap_count"] == 0
    assert "NOT_REAL" in good["status"]
    with pytest.raises(CohortGovernanceError) as err:
        validate_fake_identities(a, ["ai10_fake_a2"])
    assert err.value.code == "ai10_overlapping_fixture_id"
    with pytest.raises(CohortGovernanceError) as err:
        validate_fake_identities(a, ["ai10_fake_b1", "ai10_fake_b1"])
    assert err.value.code == "ai10_duplicate_fixture_id"
    with pytest.raises(CohortGovernanceError) as err:
        validate_fake_identities(a, ["patient-123"])
    assert err.value.code == "ai10_untrusted_fixture_ids"


def test_generated_cohorts_have_disjoint_fake_names_and_invented_shift() -> None:
    plan = SyntheticLockedSitePlan(n_development=64, n_external=32)
    dev, y_dev, ext, y_ext, identity = _fabricate(plan)
    assert len(dev) == len(y_dev) == 64
    assert len(ext) == len(y_ext) == 32
    assert identity["overlap_count"] == 0
    assert identity["development_count"] == 64
    assert identity["external_count"] == 32
    assert _fabricate(plan)[4] == identity
    assert all(rec["synthetic"] is True for rec in dev + ext)


def test_insufficient_fabricated_external_ends_before_training_or_ledger(tmp_path: Path) -> None:
    path = tmp_path / "unused" / "one-shot.json"
    report = run_ai10_synthetic_locked_site(
        ledger_path=path, plan=SyntheticLockedSitePlan(n_external=8),
    )
    assert report["status"] == "INSUFFICIENT_EVIDENCE"
    assert report["ledger_slot_consumed"] is False
    assert report["clinical_use_authorized"] is False
    assert not path.exists()
    assert report["sha256"] == _sha({k: v for k, v in report.items() if k != "sha256"})


def test_mismatched_plan_digest_fails_before_ledger(tmp_path: Path) -> None:
    path = tmp_path / "no" / "ledger.json"
    with pytest.raises(CohortGovernanceError) as err:
        run_ai10_synthetic_locked_site(
            ledger_path=path, expected_plan_sha256="0" * 64,
        )
    assert err.value.code == "ai10_plan_digest_mismatch"
    assert not path.exists()


@pytest.fixture(scope="module")
def completed(tmp_path_factory: pytest.TempPathFactory) -> tuple[dict, Path]:
    # The protected ledger is outside the checkout, isolated, and starts absent.
    ledger = tmp_path_factory.mktemp("ai10-private") / "ledger" / "single-shot.json"
    report = run_ai10_synthetic_locked_site(
        ledger_path=ledger, plan=SyntheticLockedSitePlan(),
        expected_plan_sha256=SyntheticLockedSitePlan().sha256,
    )
    return report, ledger


def test_engine_reuses_existing_single_shot_ledger(completed: tuple[dict, Path]) -> None:
    report, ledger_path = completed
    assert report["status"] == "SYNTHETIC_LOCKED_SITE_EXERCISE_COMPLETE"
    assert report["evidence_class"] == EVIDENCE
    assert report["ledger_slot_consumed"] is True
    assert report["ledger_status"] == "COMPLETED"
    entries = ExternalEvaluationLedger(ledger_path).list_entries()
    assert len(entries) == 1
    assert entries[0]["status"] == "COMPLETED"
    assert entries[0]["result_summary_sha256"]
    with pytest.raises(CohortGovernanceError) as err:
        ExternalEvaluationLedger(ledger_path).reserve_evaluation(
            protocol_id=entries[0]["protocol_id"],
            model_id=entries[0]["model_id"],
            model_version=entries[0]["model_version"],
            external_cohort_id=entries[0]["external_cohort_id"],
            external_dataset_id=entries[0]["external_dataset_id"],
            preprocessor_sha256=entries[0]["preprocessor_sha256"],
            calibrator_sha256=entries[0]["calibrator_sha256"],
            cohort_fingerprint_sha256=entries[0]["cohort_fingerprint_sha256"],
        )
    assert err.value.code == "one_shot_external_evaluation_already_consumed"


def test_report_is_aggregate_synthetic_and_checksum_bound(completed: tuple[dict, Path]) -> None:
    report, ledger_path = completed
    assert report["n_development"] == 96
    assert report["n_external"] == 48
    assert report["n_positive"] + report["n_negative"] == 48
    assert report["model_tuned_on_external"] is False
    assert report["real_hungary_accessed"] is False
    assert report["real_external_validation_performed"] is False
    assert report["clinical_use_authorized"] is False
    assert report["real_data_execution_authorized"] is False
    assert 0 <= report["uncalibrated_roc_auc"] <= 1
    assert 0 <= report["transport_calibrated_roc_auc"] <= 1
    assert report["sha256"] == _sha({k: v for k, v in report.items() if k != "sha256"})
    serialized = json.dumps(report)
    assert str(ledger_path) not in serialized
    assert "reservation_id" not in serialized
    assert "patient-" not in serialized
    assert "synthetic_ai10_external_" not in serialized

def test_cli_refuses_file_inside_checkout_before_training() -> None:
    root = Path(__file__).resolve().parents[2]
    cli = root / "scripts" / "run_ai10_synthetic_locked_site.py"
    command = [
        sys.executable, str(cli), "--ledger", str(root / "ai10-unsafe-ledger.json"),
    ]
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False)
    assert result.returncode == 2
    assert "refused" in result.stderr
    assert not (root / "ai10-unsafe-ledger.json").exists()
