"""End-to-end guarded-run integration test in an isolated synthetic repository.

The fixture repository contains generated rows only. Every human-identity field
is a clearly-labelled synthetic fixture value; this test does not create, sign,
or simulate a real authorization.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from research.uci412 import safety
from research.uci412.config import (
    ALLOWED_MODEL_FAMILIES,
    ALLOWED_OPERATIONS,
    FORBIDDEN_OPERATIONS,
    M3A_LOCAL_SIGNATURE_ATTESTATION,
    PROPOSAL_RELATIVE_PATH,
    REPOSITORY_ROOT,
)
from research.uci412.errors import (
    AuthorizationError,
    ProvenanceError,
    RuntimeGuardError,
    StorageProtectionError,
)
from research.uci412.evaluation import NegativeControlResult
from research.uci412.runner import run_authorized_local_experiment
from research.uci412.synthetic import write_synthetic_workbook

from tests.uci412.conftest import small_config

SYNTHETIC_SIGNER = "SYNTHETIC TEST FIXTURE SIGNER - NOT A HUMAN AUTHORIZATION"
COMMIT_ENV = {
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z",
}
SOURCE_RELATIVE = Path("data/raw/uci-412/Z-Alizadeh sani dataset.xlsx")


def _git(repo: Path, *args: str, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )
    return completed.stdout.strip()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _copy_package_files(repo: Path) -> None:
    shutil.copytree(
        REPOSITORY_ROOT / "research",
        repo / "research",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    for relative in ("docs/research/gate-pt", "docs/research/gate-da"):
        source = REPOSITORY_ROOT / relative
        if source.exists():
            shutil.copytree(source, repo / relative)


def _write_manifests(repo: Path, config, commit: str) -> dict[str, str]:
    source = repo / SOURCE_RELATIVE
    digest = _sha256(source)
    size = source.stat().st_size
    plan = repo / "research/uci412/uci412_cad_research_plan.v0.1.json"
    dictionary = repo / "research/uci412/schemas/uci412_feature_dictionary.v1.json"
    proposal = repo / PROPOSAL_RELATIVE_PATH

    manifests = repo / "data/manifests"
    licenses = manifests / "licenses"
    licenses.mkdir(parents=True, exist_ok=True)
    license_snapshot = licenses / "uci-412-license-snapshot.txt"
    license_snapshot.write_text(
        "Synthetic test fixture licence statement: CC BY 4.0 (Creative Commons Attribution 4.0).\n"
        "This file exists only inside an isolated test repository.\n",
        encoding="utf-8",
    )

    d046 = json.loads((repo / "research/audit/gate_da_authorization.json").read_text(encoding="utf-8"))
    d046["workflow_status"] = "AUTHORIZED_FOR_LOCAL_READ_ONLY_AUDIT"
    da_a1 = d046["datasets"]["DA-A1"]
    da_a1.update(
        {
            "authorization_status": "AUTHORIZED_FOR_READ_ONLY_AUDIT",
            "authorized_by": "SYNTHETIC TEST FIXTURE (NOT A HUMAN)",
            "authorized_date": "2026-01-01",
            "responsible_acquirer": "SYNTHETIC TEST FIXTURE (NOT A HUMAN)",
            "audit_reviewer": "SYNTHETIC TEST FIXTURE (NOT A HUMAN)",
            "environment": "SYNTHETIC TEST FIXTURE REPOSITORY",
        }
    )
    d046["supervisor_approval_claimed"] = False
    d046["gate_pt_status"] = "CLOSED_REQUIRES_SUPERVISOR_SIGNOFF_P3"
    (manifests / "gate_da_authorization.local.json").write_text(json.dumps(d046, indent=2), encoding="utf-8")

    provenance = {
        "schema_version": "1.1.0",
        "governance_decision_id": "D-046",
        "manifest_recorded_at_utc": "2026-01-01T00:00:00Z",
        "acquirer": "SYNTHETIC TEST FIXTURE (NOT A HUMAN)",
        "audit_reviewer": "SYNTHETIC TEST FIXTURE (NOT A HUMAN)",
        "environment": "SYNTHETIC TEST FIXTURE REPOSITORY",
        "files": [
            {
                "dataset_id": "DA-A1",
                "uci_id": 412,
                "doi": "10.24432/C5Q31T",
                "official_source_url": "https://archive.ics.uci.edu/dataset/412/z+alizadeh+sani",
                "download_method": "synthetic_test_fixture",
                "filename": SOURCE_RELATIVE.name,
                "relative_path": SOURCE_RELATIVE.as_posix(),
                "downloaded_at_utc": "UNKNOWN_PENDING_HUMAN_VERIFICATION",
                "manifest_recorded_at_utc": "2026-01-01T00:00:00Z",
                "download_timestamp_evidence_status": "UNVERIFIED",
                "local_file_integrity_status": "VERIFIED",
                "official_source_provenance_status": (
                    "HUMAN_ATTESTED_NOT_INDEPENDENTLY_PROVEN_BY_LOCAL_HASH"
                ),
                "license_spdx": "CC-BY-4.0",
                "license_snapshot_path": "data/manifests/licenses/uci-412-license-snapshot.txt",
                "license_snapshot_sha256": _sha256(license_snapshot),
                "sha256": digest,
                "size_bytes": size,
            }
        ],
    }
    (manifests / "provenance_manifest.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")

    m3a = {
        "schema_version": "0.1.0",
        "proposal_id": "M3A-UCI412-INTERNAL-RESEARCH-PROPOSAL",
        "authorization_status": "AUTHORIZED_FOR_LOCAL_INTERNAL_RESEARCH",
        "experiment_type": "INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED",
        "supervisor_signoff_claimed": False,
        "gate_pt_status": "CLOSED_REQUIRES_SUPERVISOR_SIGNOFF_P3",
        "maintainer_approval_comment_exact": "AUTHORIZE-M3A-UCI412-INTERNAL-RESEARCH",
        "governance_pr_number": 999,
        "governance_merge_commit_sha": commit,
        "pinned_protocol_commit_sha": commit,
        "authorization_proposal_relative_path": PROPOSAL_RELATIVE_PATH.as_posix(),
        "frozen_authorization_proposal_sha256": _sha256(proposal),
        "frozen_feature_dictionary_sha256": _sha256(dictionary),
        "frozen_research_plan_sha256": _sha256(plan),
        "dataset_id": "DA-A1",
        "target_column": "Cath",
        "allowed_original_relative_file": SOURCE_RELATIVE.as_posix(),
        "authorized_source_row_count": 303,
        "panel_schema_id": "uci412_basic_clinical_v1",
        "panel_schema_version": "1.0.0",
        "allowlisted_model_families": list(ALLOWED_MODEL_FAMILIES),
        "allowed_operations_if_approved": list(ALLOWED_OPERATIONS),
        "forbidden_operations": list(FORBIDDEN_OPERATIONS),
        "allowed_runtime": "LOCAL_WINDOWS_CPU_ONLY",
        "protected_outputs_relative_root": "data/uci412-experiments",
        "expected_sha256_from_protected_provenance_manifest": digest,
        "local_signer": SYNTHETIC_SIGNER,
        "local_signed_at_iso8601": "2026-01-02T00:00:00Z",
        "local_signature_attestation": M3A_LOCAL_SIGNATURE_ATTESTATION,
        "signature_semantics": "HUMAN_ATTESTATION_FIELDS_NOT_A_CRYPTOGRAPHIC_SIGNATURE",
    }
    (manifests / "uci412_internal_research_authorization.local.json").write_text(
        json.dumps(m3a, indent=2), encoding="utf-8"
    )
    return {
        "source_sha256": digest,
        "source_size": str(size),
        "source_path": SOURCE_RELATIVE.as_posix(),
    }


@pytest.fixture()
def authorized_repo(tmp_path: Path, monkeypatch) -> tuple[Path, Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".gitignore").write_text("/data/\n", encoding="utf-8")
    _copy_package_files(repo)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "synthetic@example.invalid")
    _git(repo, "config", "user.name", "Synthetic Test")
    _git(repo, "add", "-A", env=COMMIT_ENV)
    _git(repo, "commit", "-qm", "synthetic fixture", env=COMMIT_ENV)
    commit = _git(repo, "rev-parse", "HEAD")

    config = small_config()
    source = repo / SOURCE_RELATIVE
    source.parent.mkdir(parents=True, exist_ok=True)
    write_synthetic_workbook(source, config=config)
    details = _write_manifests(repo, config, commit)

    # Simulate the Windows-local runtime and bind the audited hash to the fixture.
    monkeypatch.setattr(safety, "enforce_local_windows_runtime", lambda **kwargs: None)
    monkeypatch.setattr(safety, "AUDITED_REFERENCE_SHA256", details["source_sha256"])
    monkeypatch.setattr(safety, "M3A_AUTHORIZING_MAINTAINER", SYNTHETIC_SIGNER)
    monkeypatch.setattr("research.uci412.runner.DEFAULT_CONFIG", config)
    return repo, source, commit


def test_authorized_run_writes_only_aggregate_and_protected_outputs(authorized_repo) -> None:
    repo, source, commit = authorized_repo
    original = source.read_bytes()
    config = small_config()
    notes = repo / "data/manifests/uci412_failed_runs.local.json"
    notes.write_text(json.dumps(["2026-01-01 preflight stopped: source hash mismatch"]), encoding="utf-8")

    result = run_authorized_local_experiment(repo_root=repo, config=config)

    assert result["status"] == "INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED"
    assert result["report_banner"] == "INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED"
    assert result["final_full_cohort_model_artifact_saved"] is False
    assert result["clinical_or_external_validation_claim"] is False
    assert result["supervisor_approval_claimed"] is False

    output_directory = repo / "data/uci412-experiments" / result["run_id"]
    report_path = output_directory / "report.json"
    predictions_path = output_directory / "predictions.csv"
    assert report_path.is_file() and predictions_path.is_file()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["report_banner"] == "INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED"
    assert report["experiment_metadata"]["git_commit_sha"] == commit
    assert report["experiment_metadata"]["research_only_validation_status"] == report["report_banner"]
    assert report["claims"] == {
        "clinical_use": False,
        "patient_facing_risk_percentage": False,
        "supervisor_approval": False,
        "publication_or_novelty": False,
        "external_validation": False,
        "patient_independence_proven": False,
        "future_event_risk_horizon": False,
    }
    assert report["cohort"]["class_counts_by_binary_label"] == {"0": 87, "1": 216}
    assert report["failed_runs"] == ["2026-01-01 preflight stopped: source hash mismatch"]
    assert report["experiment_metadata"]["failed_run_count"] == 1
    assert "source_row_index" not in report_path.read_text(encoding="utf-8")
    assert result["predictions_sha256"] == _sha256(predictions_path)
    assert len(predictions_path.read_text(encoding="utf-8").splitlines()) == 1 + 303
    assert hashlib.sha256(original).hexdigest() == report["provenance"]["source_sha256"]
    assert source.read_bytes() == original
    assert _git(repo, "status", "--porcelain", "--untracked-files=all") == ""


def test_missing_m3a_manifest_fails_before_any_parse(authorized_repo, monkeypatch) -> None:
    repo, _, _ = authorized_repo
    (repo / "data/manifests/uci412_internal_research_authorization.local.json").unlink()

    def _boom(*args, **kwargs):
        raise AssertionError("No workbook may be parsed before the authorization gate.")

    monkeypatch.setattr("research.uci412.adapter.load_authorized_dataset", _boom)
    with pytest.raises(AuthorizationError):
        run_authorized_local_experiment(repo_root=repo, config=small_config())
    assert not (repo / "data/uci412-experiments").exists()


def test_tampered_plan_hash_fails_before_any_parse(authorized_repo, monkeypatch) -> None:
    repo, _, _ = authorized_repo
    manifest_path = repo / "data/manifests/uci412_internal_research_authorization.local.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["frozen_research_plan_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    def _boom(*args, **kwargs):
        raise AssertionError("No workbook may be parsed before the frozen-hash gate.")

    monkeypatch.setattr("research.uci412.adapter.load_authorized_dataset", _boom)
    with pytest.raises(AuthorizationError):
        run_authorized_local_experiment(repo_root=repo, config=small_config())


def test_frozen_plan_edit_after_signing_blocks_the_run(authorized_repo) -> None:
    repo, _, _ = authorized_repo
    plan_path = repo / "research/uci412/uci412_cad_research_plan.v0.1.json"
    plan_path.write_text(plan_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    # An uncommitted edit is rejected by the clean-worktree gate before hashing.
    with pytest.raises((StorageProtectionError, AuthorizationError)):
        run_authorized_local_experiment(repo_root=repo, config=small_config())


def test_changed_source_bytes_fail_closed(authorized_repo) -> None:
    repo, source, _ = authorized_repo
    source.write_bytes(source.read_bytes() + b"tamper")
    with pytest.raises(ProvenanceError):
        run_authorized_local_experiment(repo_root=repo, config=small_config())


def test_tampered_provenance_hash_fails_closed(authorized_repo) -> None:
    repo, _, _ = authorized_repo
    manifest_path = repo / "data/manifests/provenance_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][0]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ProvenanceError):
        run_authorized_local_experiment(repo_root=repo, config=small_config())


def test_unratified_d046_scope_blocks_the_run(authorized_repo) -> None:
    repo, _, _ = authorized_repo
    manifest_path = repo / "data/manifests/gate_da_authorization.local.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["workflow_status"] = "PENDING_HUMAN_ACCEPTANCE"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(AuthorizationError):
        run_authorized_local_experiment(repo_root=repo, config=small_config())


def test_leakage_alarm_discards_the_run_and_writes_nothing(authorized_repo, monkeypatch) -> None:
    repo, _, _ = authorized_repo

    def _alarm(dataset, *, config):
        return NegativeControlResult(
            shuffle_seeds=config.negative_control_seeds,
            per_shuffle=(),
            summary={
                "shuffle_count": 1,
                "leakage_assessment": {
                    "status": "LEAKAGE_ALARM_IMPLAUSIBLY_HIGH_PERMUTED_LABEL_AUROC",
                    "blocking": True,
                },
            },
        )

    monkeypatch.setattr("research.uci412.runner.run_label_shuffle_negative_control", _alarm)
    with pytest.raises(RuntimeGuardError, match="leakage"):
        run_authorized_local_experiment(repo_root=repo, config=small_config())
    assert not (repo / "data/uci412-experiments").exists()


def test_authorized_outputs_are_never_tracked_by_git(authorized_repo) -> None:
    repo, _, _ = authorized_repo
    run_authorized_local_experiment(repo_root=repo, config=small_config())
    status = _git(repo, "status", "--porcelain", "--untracked-files=all")
    assert status == ""
    tracked = _git(repo, "ls-files", "data")
    assert tracked == ""


def test_second_run_cannot_overwrite_the_first(authorized_repo, monkeypatch) -> None:
    repo, _, _ = authorized_repo
    config = small_config()
    first = run_authorized_local_experiment(repo_root=repo, config=config)

    def _fixed_run_id() -> str:
        return first["run_id"]

    monkeypatch.setattr("research.uci412.runner._new_run_id", _fixed_run_id)
    with pytest.raises(Exception):
        run_authorized_local_experiment(repo_root=repo, config=config)
