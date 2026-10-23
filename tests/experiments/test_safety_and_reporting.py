"""Fail-closed authorization/storage tests; no actual dataset or real rows."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import subprocess

import pytest

from research.experiments.config import DEFAULT_CONFIG, D047_REPORT_BANNER, REPOSITORY_ROOT
from research.experiments.errors import (
    AuthorizationError,
    RuntimeGuardError,
    StorageProtectionError,
)
from research.experiments.reporting import _validate_aggregate_report
from research.experiments.safety import (
    D047_AUTH_RELATIVE_PATH,
    create_protected_run_directory,
    enforce_local_windows_runtime,
    run_preflight,
    validate_d047_authorization,
)


def _init_ignored_test_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "synthetic-tests@example.invalid"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Synthetic Test Fixture"], cwd=path, check=True)
    (path / ".gitignore").write_text("/data/\n", encoding="utf-8")
    subprocess.run(["git", "add", ".gitignore"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-qm", "synthetic test repository"], cwd=path, check=True)
    return path


def test_checked_in_authorization_template_is_not_a_real_run_authorization() -> None:
    template = json.loads(
        (REPOSITORY_ROOT / "research/experiments/internal_exploratory_authorization.template.json")
        .read_text(encoding="utf-8")
    )
    assert template["authorization_status"] == "NOT_AUTHORIZED_TEMPLATE_ONLY"
    with pytest.raises(AuthorizationError, match="not complete"):
        validate_d047_authorization(
            template,
            repo_root=REPOSITORY_ROOT,
            current_git_commit="0" * 40,
        )


def test_real_runtime_rejects_linux_ci_arena_and_noninteractive_contexts(tmp_path: Path) -> None:
    with pytest.raises(RuntimeGuardError, match="Windows-local only"):
        enforce_local_windows_runtime(
            repo_root=tmp_path,
            platform_name="posix",
            environ={},
            interactive=True,
        )
    with pytest.raises(RuntimeGuardError, match="CI"):
        enforce_local_windows_runtime(
            repo_root=tmp_path,
            platform_name="nt",
            environ={"CI": "true"},
            interactive=True,
        )
    with pytest.raises(RuntimeGuardError, match="Arena"):
        enforce_local_windows_runtime(
            repo_root=tmp_path,
            platform_name="nt",
            environ={"ARENA_SESSION": "synthetic"},
            interactive=True,
        )
    with pytest.raises(RuntimeGuardError, match="interactive"):
        enforce_local_windows_runtime(
            repo_root=tmp_path,
            platform_name="nt",
            environ={},
            interactive=False,
        )


def test_preflight_rejects_before_any_source_parser_or_row_access(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    parsed = False

    def parser_must_not_run(*args, **kwargs):
        nonlocal parsed
        parsed = True
        raise AssertionError("source parser must not run during preflight")

    import research.experiments.data_adapter as adapter

    monkeypatch.setattr(adapter, "_parse_processed_cleveland_bytes", parser_must_not_run)
    with pytest.raises(RuntimeGuardError):
        run_preflight(repo_root=tmp_path)
    assert parsed is False
    assert not (tmp_path / "data").exists()


def test_interactive_run_command_fails_closed_without_console_confirmation(capsys: pytest.CaptureFixture[str]) -> None:
    from research.experiments.cli import main

    result = main(["run"])
    captured = capsys.readouterr()
    assert result == 2
    assert "FAIL CLOSED" in captured.err
    assert not (REPOSITORY_ROOT / "data").exists()


def test_real_runner_rejects_custom_configuration_before_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    import research.experiments.runner as runner

    def preflight_must_not_run(*args, **kwargs):
        raise AssertionError("custom configuration must fail before preflight")

    monkeypatch.setattr(runner, "run_preflight", preflight_must_not_run)
    with pytest.raises(RuntimeGuardError, match="exact frozen registered"):
        runner.run_authorized_local_experiment(config=replace(DEFAULT_CONFIG, threshold=0.4))


def test_git_ignore_output_protection_creates_only_a_unique_local_directory(tmp_path: Path) -> None:
    repo = _init_ignored_test_repo(tmp_path / "repo")
    run_dir = create_protected_run_directory(
        repo_root=repo,
        run_id="run-20261022T120000Z-1234abcd",
    )
    assert run_dir == repo / "data" / "experiments" / "run-20261022T120000Z-1234abcd"
    check = subprocess.run(
        ["git", "check-ignore", "-q", "--", "data/experiments/run-20261022T120000Z-1234abcd/report.json"],
        cwd=repo,
        check=False,
    )
    assert check.returncode == 0
    with pytest.raises(StorageProtectionError, match="Run ID"):
        create_protected_run_directory(repo_root=repo, run_id="../outside")


def test_tracked_data_path_blocks_experiment_output(tmp_path: Path) -> None:
    repo = _init_ignored_test_repo(tmp_path / "repo")
    (repo / "data").mkdir()
    (repo / "data" / "synthetic-fixture.txt").write_text("not patient data", encoding="utf-8")
    subprocess.run(["git", "add", "-f", "data/synthetic-fixture.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "tracked synthetic fixture"], cwd=repo, check=True)
    with pytest.raises(StorageProtectionError, match="Git-ignore protection"):
        create_protected_run_directory(
            repo_root=repo,
            run_id="run-20261022T120001Z-1234abcd",
        )


def test_symlinked_experiment_directory_blocks_output(tmp_path: Path) -> None:
    repo = _init_ignored_test_repo(tmp_path / "repo")
    outside = tmp_path / "outside"
    outside.mkdir()
    (repo / "data").mkdir()
    try:
        (repo / "data" / "experiments").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink creation is unavailable on this platform.")
    with pytest.raises(StorageProtectionError):
        create_protected_run_directory(
            repo_root=repo,
            run_id="run-20261022T120002Z-1234abcd",
        )
    assert list(outside.iterdir()) == []


def test_aggregate_report_guard_rejects_patient_level_or_row_aligned_content() -> None:
    report = {
        "report_banner": D047_REPORT_BANNER,
        "report_type": "INTERNAL_EXPLORATORY_AGGREGATE_REPORT",
        "formal_supervisor_approval": False,
        "independent_external_validation_performed": False,
        "aggregate_metrics": {"roc_auc": 0.5},
    }
    _validate_aggregate_report(report)
    report["patient_rows"] = []
    with pytest.raises(StorageProtectionError, match="patient-level"):
        _validate_aggregate_report(report)


def test_output_directory_name_and_report_root_are_fixed() -> None:
    assert D047_AUTH_RELATIVE_PATH.as_posix() == "data/manifests/internal_exploratory_authorization.local.json"
    assert DEFAULT_CONFIG.source_relative_path == "data/raw/uci-45/processed.cleveland.data"
