"""Synthetic/temporary negative tests for the Issue #107 read-only validator.

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
VALIDATOR = ROOT / "scripts/validate_issue107_source_audit.py"
AUDIT = ROOT / "docs/research/next_phase/RH02_ISSUE107_PUBLIC_SOURCE_DATASET_AUDIT_2026_11_19.json"
REPORT = ROOT / "docs/research/next_phase/RH02_ISSUE107_PUBLIC_SOURCE_DATASET_AUDIT_2026_11_19.md"
REGISTER = ROOT / "docs/research/next_phase/RH02_SOURCE_QUESTION_REGISTER_2026_11_19.json"


def run_validator(
    audit: Path = AUDIT,
    report: Path = REPORT,
    register: Path = REGISTER,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            "--audit",
            str(audit),
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


def test_bundled_issue107_deliverables_pass() -> None:
    completed = run_validator()
    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = result(completed)
    assert payload["status"] == "PASS"
    assert payload["counts"] == {
        "datasets": 6,
        "sources": 17,
        "linked_questions": 7,
        "errors": 0,
    }


def test_validator_does_not_write_to_tracked_inputs() -> None:
    paths = (AUDIT, REPORT, REGISTER, VALIDATOR)
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
    modified = json.loads(AUDIT.read_text(encoding="utf-8"))
    modified["scope"]["patient_rows_accessed"] = True
    audit = tmp_path / "audit.json"
    audit.write_text(json.dumps(modified, indent=2), encoding="utf-8")
    completed = run_validator(audit=audit)
    assert completed.returncode == 1
    assert "scope.patient_rows_accessed has an unsafe value" in result(completed)["errors"]


def test_promoted_canonical_status_fails_closed(tmp_path: Path) -> None:
    modified = json.loads(REGISTER.read_text(encoding="utf-8"))
    for question in modified["questions"]:
        if question["id"] == "Q-10":
            question["status"] = "APPROVED"
    register = tmp_path / "register.json"
    register.write_text(json.dumps(modified, indent=2), encoding="utf-8")
    completed = run_validator(register=register)
    assert completed.returncode == 1
    errors = result(completed)["errors"]
    assert any("canonical register hash mismatch" in error for error in errors)
    assert any("Q-10 canonical register status mismatch" in error for error in errors)


def test_missing_question_link_fails_closed(tmp_path: Path) -> None:
    modified = json.loads(AUDIT.read_text(encoding="utf-8"))
    modified["question_links"] = [item for item in modified["question_links"] if item["id"] != "Q-13"]
    audit = tmp_path / "audit.json"
    audit.write_text(json.dumps(modified, indent=2), encoding="utf-8")
    completed = run_validator(audit=audit)
    assert completed.returncode == 1
    assert any("exactly Q-01" in error for error in result(completed)["errors"])
