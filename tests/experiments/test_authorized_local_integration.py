"""Synthetic-only positive/negative integration tests for the guarded local run path.

All source rows, authorization manifests, provenance, license text, and model
outputs in this module are invented inside pytest's temporary repository. The
fake authorization profile is explicitly test-only and cannot authorize a
normal production run. On POSIX, the Windows drive-type API is simulated only
at the runtime boundary; all preflight, manifest/hash, parser, CV, and output
logic remains the production implementation.
"""
from __future__ import annotations

import csv
import ctypes
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
from types import SimpleNamespace
from typing import Any

import pytest

from research.experiments.config import (
    AUTHORIZATION_TEMPLATE_PATH,
    DEFAULT_CONFIG,
    PROTOCOL_RELATIVE_PATH,
    REPOSITORY_ROOT,
)
from research.experiments.errors import AuthorizationError, ProvenanceError, StorageProtectionError
from research.experiments.synthetic_fixtures import make_synthetic_source_bytes
import research.experiments.reporting as reporting
import research.experiments.runner as runner
import research.experiments.safety as safety


TEST_AUTHORIZATION_STATUS = "SYNTHETIC_TEST_ONLY_NOT_A_REAL_AUTHORIZATION"
TEST_AUTHORIZATION_COMMENT = "SYNTHETIC_TEST_ONLY_NOT_A_HUMAN_APPROVAL"
TEST_SIGNER = "SYNTHETIC_TEST_SIGNER_NOT_A_PERSON"
TEST_ATTESTATION = "SYNTHETIC_TEST_ONLY_NOT_A_SIGNATURE"
TEST_SIGNATURE_SEMANTICS = "SYNTHETIC_TEST_MANIFEST_IS_NOT_A_HUMAN_SIGNATURE"
TEST_PR_NUMBER = 99999
TEST_RUN_ID = "run-20261023T010203Z-a1b2c3d4"

# The protected report fingerprint function reads this exact code/protocol set.
_TEMP_REPOSITORY_FILES = (
    "research/audit/__init__.py",
    "research/audit/gate_da_authorization.json",
    "research/audit/git_safety.py",
    "research/audit/provenance.py",
    "research/audit/registry.py",
    "research/experiments/__init__.py",
    "research/experiments/__main__.py",
    "research/experiments/cli.py",
    "research/experiments/config.py",
    "research/experiments/data_adapter.py",
    "research/experiments/errors.py",
    "research/experiments/evaluation.py",
    "research/experiments/models.py",
    "research/experiments/reporting.py",
    "research/experiments/runner.py",
    "research/experiments/safety.py",
    "research/experiments/synthetic_fixtures.py",
    "research/experiments/requirements.txt",
    "research/experiments/cleveland_d047_exploratory_plan.v0.1.json",
    "research/experiments/internal_exploratory_authorization.template.json",
)


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _install_synthetic_runtime_profile(monkeypatch: pytest.MonkeyPatch, repo_root: Path) -> list[str]:
    """Exercise the real runtime guard with an isolated simulated local Windows profile.

    On POSIX, the only mocked OS boundary is `GetDriveTypeW`; the production
    runtime guard still evaluates CI/remote flags, console intent, path shape,
    reparse/symlink checks, UNC rejection, and the fixed-drive result. On actual
    Windows, all real environment/drive checks run; only pytest's stdin capture
    is bypassed (the documented standalone console probe verifies that gate).
    """
    observed_drives: list[str] = []
    production_guard = safety.enforce_local_windows_runtime

    if os.name != "nt":
        def get_drive_type(root: str) -> int:
            observed_drives.append(root)
            return 3  # DRIVE_FIXED; this is a test boundary stub, never production behavior.

        monkeypatch.setattr(
            ctypes,
            "windll",
            SimpleNamespace(kernel32=SimpleNamespace(GetDriveTypeW=get_drive_type)),
            raising=False,
        )

        def runtime_guard_for_synthetic_fixture(*, repo_root: Path) -> None:
            production_guard(
                repo_root=repo_root,
                environ={},
                platform_name="nt",
                interactive=True,
            )
    else:
        def runtime_guard_for_synthetic_fixture(*, repo_root: Path) -> None:
            # Keep the actual OS, current environment, fixed-drive API, and
            # reparse-point checks. pytest stdin capture is tested separately.
            production_guard(repo_root=repo_root, interactive=True)

    monkeypatch.setattr(safety, "enforce_local_windows_runtime", runtime_guard_for_synthetic_fixture)
    return observed_drives


def _prepare_fake_authorized_repo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Any]:
    """Create an isolated, committed fixture repository plus ignored synthetic data/manifests."""
    repo = (tmp_path / "synthetic-authorized-repo").resolve()
    repo.mkdir(parents=True)
    (repo / ".gitignore").write_text(
        "# Test-only isolated repository. No actual dataset is stored here.\n/data/\n",
        encoding="utf-8",
    )
    for relative in _TEMP_REPOSITORY_FILES:
        source = REPOSITORY_ROOT / relative
        destination = repo / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    protocol_relative = PROTOCOL_RELATIVE_PATH.as_posix()
    protocol_copy = repo / protocol_relative
    protocol_copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REPOSITORY_ROOT / PROTOCOL_RELATIVE_PATH, protocol_copy)

    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "Synthetic integration-test fixture")
    _git(repo, "config", "user.email", "synthetic-fixture@example.invalid")
    _git(repo, "config", "core.autocrlf", "false")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "synthetic integration-test repository")
    governance_sha = _git(repo, "rev-parse", "HEAD").lower()

    # The test uses unmistakably fake authorization identities, comment,
    # timestamp, PR number and governance SHA. No real signoff is asserted.
    monkeypatch.setattr(safety, "D047_AUTHORIZATION_STATUS", TEST_AUTHORIZATION_STATUS)
    monkeypatch.setattr(safety, "D047_AUTHORIZATION_COMMENT", TEST_AUTHORIZATION_COMMENT)
    monkeypatch.setattr(safety, "D047_AUTHORIZING_MAINTAINER", TEST_SIGNER)
    monkeypatch.setattr(safety, "D047_AUTHORIZING_PR_NUMBER", TEST_PR_NUMBER)
    monkeypatch.setattr(safety, "D047_AUTHORIZING_MERGED_AT_UTC", "2020-01-01T00:00:00+00:00")
    monkeypatch.setattr(safety, "D047_AUTHORIZING_MERGE_SHA", governance_sha)
    monkeypatch.setattr(safety, "D047_LOCAL_SIGNATURE_ATTESTATION", TEST_ATTESTATION)
    monkeypatch.setattr(safety, "D047_SIGNATURE_SEMANTICS", TEST_SIGNATURE_SEMANTICS)
    runtime_drive_calls = _install_synthetic_runtime_profile(monkeypatch, repo)

    # Generate every source byte in memory from the invented fixture generator.
    # The path is under this temporary repository, never the real checkout.
    source_bytes = make_synthetic_source_bytes(seed=884047)
    source_path = repo / safety.SOURCE_RELATIVE_PATH
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_bytes(source_bytes)
    source_sha = _sha256(source_bytes)

    # D-046 fixture intentionally grants read-only audit scope only. All signer,
    # custodian and reviewer labels are synthetic test text, not human approval.
    d046 = json.loads((repo / "research/audit/gate_da_authorization.json").read_text(encoding="utf-8"))
    d046["workflow_status"] = safety.D046_AUTHORIZED_WORKFLOW_STATUS
    d046_dataset = d046["datasets"]["DA-A2"]
    d046_dataset.update({
        "authorization_status": safety.D046_DATASET_AUTHORIZED_STATUS,
        "authorized_by": "SYNTHETIC_TEST_FIXTURE_NOT_A_HUMAN_GRANT",
        "authorized_date": "2026-01-01",
        "responsible_acquirer": "SYNTHETIC_TEST_FIXTURE_NOT_A_HUMAN_GRANT",
        "audit_reviewer": "SYNTHETIC_TEST_FIXTURE_NOT_A_HUMAN_GRANT",
        "environment": "Temporary synthetic pytest repository only; not a Windows data environment",
        "purpose": "Exercise local read-only manifest validation using invented rows only.",
    })
    d046_path = repo / safety.D046_AUTH_RELATIVE_PATH
    _write_json(d046_path, d046)

    # Deliberately fake license text, with the required token solely to exercise
    # the validator. It is not a license document and grants no rights.
    license_text = (
        "SYNTHETIC TEST PLACEHOLDER ONLY; NOT A LICENSE OR SOURCE DOCUMENT.\n"
        "The text token CC BY 4.0 is present solely to exercise local validation.\n"
    )
    license_bytes = license_text.encode("utf-8")
    license_path = repo / safety.LICENSE_RELATIVE_PATH
    license_path.parent.mkdir(parents=True, exist_ok=True)
    license_path.write_bytes(license_bytes)
    license_sha = _sha256(license_bytes)

    recorded_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    provenance = {
        "governance_decision_id": "D-046",
        "acquirer": "SYNTHETIC_TEST_FIXTURE_NOT_A_HUMAN_ACQUIRER",
        "audit_reviewer": "SYNTHETIC_TEST_FIXTURE_NOT_A_HUMAN_REVIEWER",
        "manifest_recorded_at_utc": recorded_at,
        "provenance_verification_semantics": {
            "local_file_integrity_status": "VERIFIED",
            "official_source_provenance_status": safety.EXPECTED_OFFICIAL_SOURCE_STATUS,
        },
        "files": [{
            "dataset_id": "DA-A2",
            "filename": safety.SOURCE_RELATIVE_PATH.name,
            "manifest_recorded_at_utc": recorded_at,
            "downloaded_at_utc": "UNKNOWN_PENDING_HUMAN_VERIFICATION",
            "uci_id": 45,
            "doi": safety.CANONICAL_UCI_45_DOI,
            "official_source_url": safety.CANONICAL_UCI_45_URL,
            "relative_path": safety.SOURCE_RELATIVE_PATH.as_posix(),
            "local_file_integrity_status": safety.EXPECTED_LOCAL_PROVENANCE_STATUS,
            "official_source_provenance_status": safety.EXPECTED_OFFICIAL_SOURCE_STATUS,
            "license_spdx": safety.EXPECTED_LICENSE_SPDX,
            "sha256": source_sha,
            "size_bytes": len(source_bytes),
            "license_snapshot_path": safety.LICENSE_RELATIVE_PATH.as_posix(),
            "license_snapshot_sha256": license_sha,
        }],
        "test_fixture_notice": "SYNTHETIC ONLY; this is not evidence of real UCI acquisition or human provenance.",
    }
    provenance_path = repo / safety.PROVENANCE_RELATIVE_PATH
    _write_json(provenance_path, provenance)

    protocol_sha = _sha256(protocol_copy.read_bytes())
    plan_copy = repo / "research/experiments/cleveland_d047_exploratory_plan.v0.1.json"
    plan_sha = _sha256(plan_copy.read_bytes())
    signed_at = datetime.now(timezone.utc).isoformat()
    d047 = json.loads(AUTHORIZATION_TEMPLATE_PATH.read_text(encoding="utf-8"))
    d047.update({
        "authorization_status": TEST_AUTHORIZATION_STATUS,
        "maintainer_approval_comment_exact": TEST_AUTHORIZATION_COMMENT,
        "approval_pr_number": TEST_PR_NUMBER,
        "approval_pr_merged_commit_sha": governance_sha,
        "local_signer": TEST_SIGNER,
        "local_signed_at_iso8601": signed_at,
        "local_signature_attestation": TEST_ATTESTATION,
        "pinned_protocol_git_commit_sha": governance_sha,
        "frozen_protocol_sha256": protocol_sha,
        "frozen_experiment_plan_sha256": plan_sha,
        "expected_sha256_from_protected_provenance_manifest": source_sha,
        "signature_semantics": TEST_SIGNATURE_SEMANTICS,
    })
    d047_path = repo / safety.D047_AUTH_RELATIVE_PATH
    _write_json(d047_path, d047)

    return {
        "repo": repo,
        "source_path": source_path,
        "source_bytes": source_bytes,
        "source_sha": source_sha,
        "d046_path": d046_path,
        "d047_path": d047_path,
        "provenance_path": provenance_path,
        "license_path": license_path,
        "governance_sha": governance_sha,
        "protocol_sha": protocol_sha,
        "plan_sha": plan_sha,
        "runtime_drive_calls": runtime_drive_calls,
    }


def _prevent_fit_or_parse(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []

    def must_not_run(*args: Any, **kwargs: Any) -> None:
        calls.append("unexpected")
        raise AssertionError("preflight must fail before parsing or model fitting")

    monkeypatch.setattr(runner, "_parse_processed_cleveland_bytes", must_not_run)
    monkeypatch.setattr(runner, "_run_nested_cv", must_not_run)
    monkeypatch.setattr(runner, "_run_label_shuffle_negative_control", must_not_run)
    return calls


def test_synthetic_authorized_run_completes_preflight_cv_and_protected_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _prepare_fake_authorized_repo(tmp_path, monkeypatch)
    repo = fixture["repo"]
    source_path = fixture["source_path"]
    original_source_bytes = fixture["source_bytes"]
    assert repo != REPOSITORY_ROOT and repo in source_path.parents
    assert source_path.read_bytes() == original_source_bytes

    observations: dict[str, Any] = {}
    original_reader = runner._read_source_bytes_read_only
    original_nested_cv = runner._run_nested_cv

    def record_reader(path: Path, **kwargs: Any):
        snapshot = original_reader(path, **kwargs)
        observations["source_snapshot"] = snapshot
        return snapshot

    def record_nested_cv(dataset, **kwargs):
        result = original_nested_cv(dataset, **kwargs)
        observations["nested_result"] = result
        return result

    monkeypatch.setattr(runner, "_read_source_bytes_read_only", record_reader)
    monkeypatch.setattr(runner, "_run_nested_cv", record_nested_cv)
    monkeypatch.setattr(runner, "_new_run_id", lambda: TEST_RUN_ID)

    def write_synthetic_test_report(**kwargs):
        """Never serialize the real-UCI report schema for invented fixture bytes."""
        preflight = kwargs["preflight"]
        snapshot = kwargs["source_snapshot"]
        dataset = kwargs["dataset"]
        nested = kwargs["nested"]
        negative_control = kwargs["negative_control"]
        config = kwargs["config"]
        predictions_sha256 = kwargs["predictions_sha256"]
        predictions_size_bytes = kwargs["predictions_size_bytes"]
        report = {
            "report_schema_version": "synthetic-integration-test-v1",
            "report_type": "INTERNAL_EXPLORATORY_AGGREGATE_REPORT",
            "report_banner": config.report_banner,
            "status": "SYNTHETIC_TEST_FIXTURE_ONLY_NOT_A_RESEARCH_RESULT",
            "purpose": "End-to-end software test using generated bytes; not a Cleveland or research result.",
            "formal_supervisor_approval": False,
            "independent_external_validation_performed": False,
            "execution": {
                "test_only": True,
                "real_cleveland_data_accessed": False,
                "runtime_gate_simulated_on_posix": os.name != "nt",
                "actual_platform": os.name,
            },
            "source": {
                "classification": "GENERATED_SYNTHETIC_TEST_BYTES_NOT_UCI_OR_PATIENT_DATA",
                "sha256": snapshot.sha256,
                "size_bytes": snapshot.size_bytes,
                "row_count": dataset.row_count,
                "synthetic_label_counts": {"0": dataset.n_negative, "1": dataset.n_positive},
                "original_synthetic_bytes_preserved": True,
            },
            "authorization": {
                "scope": "SYNTHETIC_TEST_FIXTURES_ONLY_NOT_REAL_D046_OR_D047_AUTHORIZATION",
                "test_signer": preflight.authorization["local_signer"],
                "test_authorization_comment": preflight.authorization["authorization_comment_exact"],
                "test_d047_manifest_sha256": preflight.d047_authorization_sha256,
                "test_d046_manifest_sha256": preflight.d046_authorization_sha256,
                "test_provenance_manifest_sha256": preflight.provenance_sha256,
                "test_source_sha256_binding": preflight.authorization["expected_source_sha256"],
                "test_protocol_sha256_binding": preflight.authorization["frozen_protocol_sha256"],
                "test_plan_sha256_binding": preflight.authorization["frozen_experiment_plan_sha256"],
                "supervisor_signoff_claimed": False,
            },
            "aggregate_results": reporting.nested_result_to_report(nested),
            "negative_control": {
                "per_shuffle_aggregate_metrics": [dict(item) for item in negative_control.per_shuffle],
                "summary": dict(negative_control.summary),
                "interpretation": negative_control.interpretation,
                "formal_permutation_p_value": False,
            },
            "local_artifacts": {
                "predictions_file": reporting.PREDICTIONS_FILENAME,
                "predictions_sha256": predictions_sha256,
                "predictions_size_bytes": predictions_size_bytes,
                "contains_only_generated_test_rows": True,
                "contains_row_aligned_labels_and_oof_scores": True,
            },
            "clinical_or_external_validation_claim": False,
        }
        reporting._validate_aggregate_report(report)
        observations["preflight"] = preflight
        observations["synthetic_report"] = report
        return report

    # Keep the actual protected output writer, exclusive file creation,
    # prediction serializer and aggregate-report guard. Substitute only a
    # test-labelled report body so no fake bytes can be described as UCI data.
    monkeypatch.setattr(reporting, "build_real_experiment_report", write_synthetic_test_report)
    run_result = runner.run_authorized_local_experiment(repo_root=repo)

    assert run_result["status"] == "INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED"
    assert run_result["clinical_or_external_validation_claim"] is False
    assert run_result["row_count"] == DEFAULT_CONFIG.expected_row_count == 303
    assert observations["preflight"].current_git_commit == fixture["governance_sha"]
    assert observations["preflight"].authorization["local_signer"] == TEST_SIGNER
    assert observations["preflight"].authorization["authorization_comment_exact"] == TEST_AUTHORIZATION_COMMENT
    assert observations["source_snapshot"].content == original_source_bytes
    assert observations["source_snapshot"].sha256 == fixture["source_sha"]
    assert observations["nested_result"].row_count == 303
    assert len(observations["nested_result"].repeat_results) == 4
    if os.name != "nt":
        assert fixture["runtime_drive_calls"] == [repo.anchor]

    output_dir = repo / Path(run_result["output_relative_directory"])
    report_path = output_dir / run_result["report_filename"]
    predictions_path = output_dir / run_result["predictions_filename"]
    assert output_dir == repo / "data/experiments" / TEST_RUN_ID
    assert report_path.is_file() and predictions_path.is_file()
    assert report_path.parent == predictions_path.parent == output_dir
    if os.name != "nt":
        assert stat.S_IMODE(output_dir.stat().st_mode) == 0o700
        assert stat.S_IMODE(report_path.stat().st_mode) == 0o600
        assert stat.S_IMODE(predictions_path.stat().st_mode) == 0o600

    report_bytes = report_path.read_bytes()
    predictions_bytes = predictions_path.read_bytes()
    report = json.loads(report_bytes.decode("utf-8"))
    assert _sha256(report_bytes) == run_result["report_sha256"]
    assert _sha256(predictions_bytes) == run_result["predictions_sha256"]
    assert report["status"] == "SYNTHETIC_TEST_FIXTURE_ONLY_NOT_A_RESEARCH_RESULT"
    assert report["source"]["classification"] == "GENERATED_SYNTHETIC_TEST_BYTES_NOT_UCI_OR_PATIENT_DATA"
    assert report["source"]["sha256"] == fixture["source_sha"]
    assert report["source"]["original_synthetic_bytes_preserved"] is True
    assert report["authorization"]["test_source_sha256_binding"] == fixture["source_sha"]
    assert report["authorization"]["test_protocol_sha256_binding"] == fixture["protocol_sha"]
    assert report["authorization"]["test_plan_sha256_binding"] == fixture["plan_sha"]
    assert report["authorization"]["test_d047_manifest_sha256"] == _sha256(fixture["d047_path"].read_bytes())
    assert report["authorization"]["test_d046_manifest_sha256"] == _sha256(fixture["d046_path"].read_bytes())
    assert report["authorization"]["test_provenance_manifest_sha256"] == _sha256(fixture["provenance_path"].read_bytes())
    assert report["local_artifacts"]["predictions_sha256"] == _sha256(predictions_bytes)
    assert "results" not in report and "patient_rows" not in report
    assert "UCI-45" not in json.dumps(report) and "official_source_url" not in report["source"]
    assert original_source_bytes not in report_bytes

    lines = predictions_bytes.decode("utf-8").splitlines()
    assert lines[0] == f"# report_banner={DEFAULT_CONFIG.report_banner}"
    prediction_rows = list(csv.DictReader(io.StringIO("\n".join(lines[1:]), newline="")))
    assert len(prediction_rows) == 4 * DEFAULT_CONFIG.expected_row_count
    assert prediction_rows[0]["local_source_row_ordinal"] == "1"
    assert prediction_rows[302]["local_source_row_ordinal"] == "303"
    assert prediction_rows[303]["outer_repeat_number"] == "2"
    assert prediction_rows[0]["binary_source_target"] in {"0", "1"}
    assert prediction_rows[0]["inner_selected_procedure_probability"]

    # The output artifacts are ignored/untracked and remain in the temporary
    # repository. No file is created in the real checkout's /data/ directory.
    assert _git(repo, "check-ignore", "--", "data/experiments/" + TEST_RUN_ID + "/report.json")
    assert _git(repo, "ls-files", "--", "data") == ""
    assert _git(repo, "status", "--porcelain", "--untracked-files=all") == ""
    assert fixture["source_path"].read_bytes() == original_source_bytes


@pytest.mark.parametrize(
    ("mutation", "error_type", "message"),
    [
        ("source", ProvenanceError, "source SHA-256"),
        ("protocol", AuthorizationError, "local protocol or registered plan differs"),
        ("plan", AuthorizationError, "local protocol or registered plan differs"),
        ("authorization", AuthorizationError, "does not bind the verified D-047 governance merge"),
    ],
)
def test_authorized_run_rejects_mutated_hash_bindings_before_parse_or_fit(
    mutation: str,
    error_type: type[Exception],
    message: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _prepare_fake_authorized_repo(tmp_path, monkeypatch)
    calls = _prevent_fit_or_parse(monkeypatch)

    if mutation == "source":
        fixture["source_path"].write_bytes(make_synthetic_source_bytes(seed=884048))
    else:
        manifest = json.loads(fixture["d047_path"].read_text(encoding="utf-8"))
        if mutation == "protocol":
            manifest["frozen_protocol_sha256"] = "0" * 64
        elif mutation == "plan":
            manifest["frozen_experiment_plan_sha256"] = "f" * 64
        elif mutation == "authorization":
            manifest["approval_pr_merged_commit_sha"] = "f" * 40
        _write_json(fixture["d047_path"], manifest)

    with pytest.raises(error_type, match=message):
        runner.run_authorized_local_experiment(repo_root=fixture["repo"])
    assert calls == []
    assert not (fixture["repo"] / "data/experiments").exists()


def test_authorized_run_rejects_dirty_git_worktree_before_parse_or_fit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _prepare_fake_authorized_repo(tmp_path, monkeypatch)
    calls = _prevent_fit_or_parse(monkeypatch)
    (fixture["repo"] / "untracked-dirty-worktree.txt").write_text("synthetic test only\n", encoding="utf-8")

    with pytest.raises(StorageProtectionError, match="worktree must be clean"):
        runner.run_authorized_local_experiment(repo_root=fixture["repo"])
    assert calls == []
    assert not (fixture["repo"] / "data/experiments").exists()
