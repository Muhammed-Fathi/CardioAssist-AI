"""Synthetic/temporary negative tests for the Issue #110 decision-review validator.

The bundled deliverables are checked as read-only inputs. All tampering tests
operate on temporary copies; no patient data, real protocol, or tracked
source artifact is modified.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "scripts/validate_issue110_decision_review.py"
REVIEW = ROOT / "docs/research/next_phase/RH06_ISSUE110_CONSOLIDATED_DECISION_REVIEW_2026_11_19.json"
REPORT = ROOT / "docs/research/next_phase/RH06_ISSUE110_CONSOLIDATED_DECISION_REVIEW_2026_11_19.md"
REGISTER = ROOT / "docs/research/next_phase/RH02_SOURCE_QUESTION_REGISTER_2026_11_19.json"


def run_validator(
    review: Path = REVIEW,
    report: Path = REPORT,
    register: Path = REGISTER,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            "--review",
            str(review),
            "--report",
            str(report),
            "--canonical-register",
            str(register),
            "--validator",
            str(VALIDATOR),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def result(completed: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(completed.stdout)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_copy(tmp_path: Path, name: str, payload: object) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def test_bundled_issue110_deliverables_pass() -> None:
    completed = run_validator()
    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = result(completed)
    assert payload["status"] == "PASS"
    assert payload["counts"]["datasets"] == 8
    assert payload["counts"]["linked_questions"] == 16
    assert payload["counts"]["errors"] == 0


def test_validator_does_not_write_to_tracked_inputs() -> None:
    paths = (REVIEW, REPORT, REGISTER, VALIDATOR)
    before = [(path, digest(path), path.stat().st_mtime_ns) for path in paths]
    completed = run_validator()
    assert completed.returncode == 0, completed.stdout
    for path, expected_hash, expected_mtime in before:
        assert digest(path) == expected_hash
        assert path.stat().st_mtime_ns == expected_mtime


def test_tampered_report_fails_hash_check(tmp_path: Path) -> None:
    tampered = tmp_path / "report.md"
    tampered.write_text(REPORT.read_text(encoding="utf-8") + "\nUNAPPROVED EDIT\n", encoding="utf-8")
    completed = run_validator(report=tampered)
    assert completed.returncode == 1
    assert "report SHA-256 mismatch" in result(completed)["errors"]


def test_false_real_data_claim_fails_closed(tmp_path: Path) -> None:
    modified = json.loads(REVIEW.read_text(encoding="utf-8"))
    modified["scope"]["patient_rows_accessed"] = True
    review = write_copy(tmp_path, "review.json", modified)
    completed = run_validator(review=review)
    assert completed.returncode == 1
    assert "scope.patient_rows_accessed has an unsafe value" in result(completed)["errors"]


def test_promoted_canonical_status_fails_closed(tmp_path: Path) -> None:
    modified = json.loads(REGISTER.read_text(encoding="utf-8"))
    for question in modified["questions"]:
        if question["id"] == "Q-15":
            question["status"] = "APPROVED"
    register = write_copy(tmp_path, "register.json", modified)
    completed = run_validator(register=register)
    assert completed.returncode == 1
    errors = result(completed)["errors"]
    assert any("canonical register hash mismatch" in error for error in errors)
    assert any("Q-15 canonical register status mismatch" in error for error in errors)


def test_promoted_copied_status_fails_closed(tmp_path: Path) -> None:
    modified = json.loads(REVIEW.read_text(encoding="utf-8"))
    modified["canonical_question_statuses_unchanged"]["Q-11"] = "RESOLVED_PRIMARY_METADATA_ONLY"
    review = write_copy(tmp_path, "review.json", modified)
    completed = run_validator(review=review)
    assert completed.returncode == 1
    assert any("Q-11 copied status mismatch" in error for error in result(completed)["errors"])


def test_missing_dataset_fails_closed(tmp_path: Path) -> None:
    modified = json.loads(REVIEW.read_text(encoding="utf-8"))
    modified["datasets"] = [d for d in modified["datasets"] if d["id"] != "ANGIOCAD_P25"]
    review = write_copy(tmp_path, "review.json", modified)
    completed = run_validator(review=review)
    assert completed.returncode == 1
    assert any("eight required sources" in error for error in result(completed)["errors"])


def test_invalid_disposition_fails_closed(tmp_path: Path) -> None:
    modified = json.loads(REVIEW.read_text(encoding="utf-8"))
    for entry in modified["datasets"]:
        if entry["id"] == "UCI45_HUNGARY":
            entry["recommendation"]["primary"] = "GO_EXECUTED"
    review = write_copy(tmp_path, "review.json", modified)
    completed = run_validator(review=review)
    assert completed.returncode == 1
    assert any("recommendation.primary is invalid" in error for error in result(completed)["errors"])


def test_swapped_ai92_disposition_fails_closed(tmp_path: Path) -> None:
    modified = json.loads(REVIEW.read_text(encoding="utf-8"))
    modified["ai_9_2_blockers"]["disposition"] = "GO_FOR_REVIEW_ONLY"
    review = write_copy(tmp_path, "review.json", modified)
    completed = run_validator(review=review)
    assert completed.returncode == 1
    assert any("AI-9.2 primary recommendation" in error for error in result(completed)["errors"])


def test_swapped_ai102_disposition_fails_closed(tmp_path: Path) -> None:
    modified = json.loads(REVIEW.read_text(encoding="utf-8"))
    modified["ai_10_2_prerequisites"]["disposition"] = "GO_FOR_REVIEW_ONLY"
    review = write_copy(tmp_path, "review.json", modified)
    completed = run_validator(review=review)
    assert completed.returncode == 1
    assert any("AI-10.2 primary recommendation" in error for error in result(completed)["errors"])


def test_missing_ai102_prerequisite_fails_closed(tmp_path: Path) -> None:
    modified = json.loads(REVIEW.read_text(encoding="utf-8"))
    prereqs = modified["ai_10_2_prerequisites"]["prerequisites"]
    modified["ai_10_2_prerequisites"]["prerequisites"] = [
        p for p in prereqs if p["id"] != "frozen_cleveland_model_artifact"
    ]
    review = write_copy(tmp_path, "review.json", modified)
    completed = run_validator(review=review)
    assert completed.returncode == 1
    assert any("prerequisite set incomplete" in error for error in result(completed)["errors"])


def test_ai92_authorization_blockers_cannot_be_emptied(tmp_path: Path) -> None:
    modified = json.loads(REVIEW.read_text(encoding="utf-8"))
    modified["ai_9_2_blockers"]["categories"]["authorization"] = []
    review = write_copy(tmp_path, "review.json", modified)
    completed = run_validator(review=review)
    assert completed.returncode == 1
    assert any("authorization" in error for error in result(completed)["errors"])


def test_work_package_cannot_be_non_synthetic(tmp_path: Path) -> None:
    modified = json.loads(REVIEW.read_text(encoding="utf-8"))
    modified["rh_mapping"]["rh_04_work_packages"][0]["synthetic_only"] = False
    review = write_copy(tmp_path, "review.json", modified)
    completed = run_validator(review=review)
    assert completed.returncode == 1
    assert any("must be synthetic_only" in error for error in result(completed)["errors"])


def test_conditional_study_entry_cannot_be_flipped(tmp_path: Path) -> None:
    modified = json.loads(REVIEW.read_text(encoding="utf-8"))
    modified["conditional_study_register_entries_unchanged"]["AI-10.2"]["real_data_authorized"] = True
    review = write_copy(tmp_path, "review.json", modified)
    completed = run_validator(review=review)
    assert completed.returncode == 1
    assert any("AI-10.2 real_data_authorized altered" in error for error in result(completed)["errors"])


def test_prohibited_claim_cannot_be_asserted(tmp_path: Path) -> None:
    modified = json.loads(REVIEW.read_text(encoding="utf-8"))
    modified["prohibited_claims"]["external_validation_achieved"] = True
    review = write_copy(tmp_path, "review.json", modified)
    completed = run_validator(review=review)
    assert completed.returncode == 1
    assert any("prohibited claim asserted as true" in error for error in result(completed)["errors"])
