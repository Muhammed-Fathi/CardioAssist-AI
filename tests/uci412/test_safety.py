"""Runtime, authorization, provenance, storage, and Git-ignore failure paths."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from research.uci412 import safety
from research.uci412.config import AUTHORIZATION_TEMPLATE_PATH, REPOSITORY_ROOT
from research.uci412.errors import (
    AuthorizationError,
    ProvenanceError,
    RuntimeGuardError,
    StorageProtectionError,
)
from research.uci412.runner import run_authorized_local_experiment
from research.uci412.safety import (
    GIT_PROTECTED_PROBES,
    load_failed_run_notes,
    M3A_AUTH_RELATIVE_PATH,
    authorization_template_is_non_authorizing,
    create_protected_run_directory,
    current_commit_and_clean_tree,
    run_preflight,
    validate_m3a_authorization,
    verify_git_protected_storage,
)
from research.uci412.source_spec import AUDITED_REFERENCE_SHA256, SOURCE_RELATIVE_PATH

from tests.uci412.conftest import small_config


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _init_repo(path: Path, gitignore: str = "/data/\n") -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / ".gitignore").write_text(gitignore, encoding="utf-8")
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "synthetic@example.invalid")
    _git(path, "config", "user.name", "Synthetic Test")
    _git(path, "add", ".gitignore")
    _git(path, "commit", "-qm", "init")
    return path


def test_repository_ignores_every_protected_uci412_path() -> None:
    verify_git_protected_storage(REPOSITORY_ROOT)
    tracked = subprocess.run(
        ["git", "ls-files", "data"],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert tracked.stdout.strip() == ""
    assert "data/raw/uci-412/Z-Alizadeh sani dataset.xlsx" in GIT_PROTECTED_PROBES
    assert "data/uci412-experiments/.m3a-protection-probe" in GIT_PROTECTED_PROBES


def test_protected_storage_fails_when_data_is_not_ignored(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo", gitignore="")
    with pytest.raises(StorageProtectionError):
        verify_git_protected_storage(repo)


def test_protected_storage_fails_when_a_data_file_is_tracked(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    (repo / "data").mkdir()
    tracked = repo / "data" / "notes.txt"
    tracked.write_text("x", encoding="utf-8")
    _git(repo, "add", "-f", "data/notes.txt")
    _git(repo, "commit", "-qm", "track data")
    with pytest.raises(StorageProtectionError):
        verify_git_protected_storage(repo)


def test_clean_tree_requirement(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    commit = current_commit_and_clean_tree(repo)
    assert len(commit) == 40
    (repo / "dirty.txt").write_text("x", encoding="utf-8")
    with pytest.raises(StorageProtectionError):
        current_commit_and_clean_tree(repo)
    (repo / "dirty.txt").unlink()
    with pytest.raises(StorageProtectionError):
        current_commit_and_clean_tree(tmp_path)


def test_checked_in_authorization_template_authorizes_nothing() -> None:
    assert authorization_template_is_non_authorizing() is True
    template = json.loads(AUTHORIZATION_TEMPLATE_PATH.read_text(encoding="utf-8"))
    with pytest.raises(AuthorizationError):
        validate_m3a_authorization(
            template,
            repo_root=REPOSITORY_ROOT,
            current_git_commit="a" * 40,
        )
    # And it cannot be mistaken for the real local manifest.
    assert not (REPOSITORY_ROOT / Path(*M3A_AUTH_RELATIVE_PATH.parts)).exists()


def test_authorization_rejects_a_placeholder_signature_even_after_status_flip() -> None:
    template = json.loads(AUTHORIZATION_TEMPLATE_PATH.read_text(encoding="utf-8"))
    template["authorization_status"] = "AUTHORIZED_FOR_LOCAL_INTERNAL_RESEARCH"
    template["experiment_type"] = "INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED"
    with pytest.raises(AuthorizationError, match="comment|signer|SHA-256|timestamp|attestation"):
        validate_m3a_authorization(
            template, repo_root=REPOSITORY_ROOT, current_git_commit="a" * 40
        )


def test_authorization_rejects_claimed_supervisor_approval() -> None:
    template = json.loads(AUTHORIZATION_TEMPLATE_PATH.read_text(encoding="utf-8"))
    template["supervisor_signoff_claimed"] = True
    with pytest.raises(AuthorizationError):
        validate_m3a_authorization(
            template, repo_root=REPOSITORY_ROOT, current_git_commit="a" * 40
        )


def test_real_run_requires_the_frozen_registered_config() -> None:
    with pytest.raises(RuntimeGuardError, match="frozen registered"):
        run_authorized_local_experiment(config=small_config())


def test_preflight_fails_closed_outside_windows_local_runtime(monkeypatch) -> None:
    def _boom(*args, **kwargs):
        raise AssertionError("No workbook may be parsed before every gate passes.")

    monkeypatch.setattr("research.uci412.adapter.load_authorized_dataset", _boom)
    monkeypatch.setattr("research.uci412.adapter.read_xlsx_workbook", _boom)
    with pytest.raises((RuntimeGuardError, StorageProtectionError)):
        run_preflight(repo_root=REPOSITORY_ROOT)


def test_preflight_never_creates_the_output_root(monkeypatch) -> None:
    output_root = REPOSITORY_ROOT / "data" / "uci412-experiments"
    existed_before = output_root.exists()
    with pytest.raises((RuntimeGuardError, StorageProtectionError, AuthorizationError, ProvenanceError)):
        run_preflight(repo_root=REPOSITORY_ROOT)
    assert output_root.exists() == existed_before


def test_source_hash_constant_is_the_audited_reference() -> None:
    assert AUDITED_REFERENCE_SHA256 == "90fefd4ecdb6263b3f2a260bb2b5d3b9fa92ba35d626dd56ad8c6db5fbbad163"
    assert len(AUDITED_REFERENCE_SHA256) == 64
    assert SOURCE_RELATIVE_PATH == "data/raw/uci-412/Z-Alizadeh sani dataset.xlsx"


def test_run_directory_requires_a_git_ignored_protected_root(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo", gitignore="")
    with pytest.raises(StorageProtectionError):
        create_protected_run_directory(repo_root=repo, run_id="run-20261024T101010Z-abcdef12")


def test_safety_module_exposes_no_authorization_writer() -> None:
    public = {name for name in dir(safety) if not name.startswith("_")}
    for forbidden in ("sign_authorization", "write_authorization", "create_manifest", "approve"):
        assert forbidden not in public


def test_failed_run_notes_are_optional_and_single_line(tmp_path: Path) -> None:
    assert load_failed_run_notes(tmp_path) == ()
    notes = tmp_path / "data/manifests/uci412_failed_runs.local.json"
    notes.parent.mkdir(parents=True)
    notes.write_text(json.dumps(["preflight stopped: hash mismatch"]), encoding="utf-8")
    assert load_failed_run_notes(tmp_path) == ("preflight stopped: hash mismatch",)
    notes.write_text(json.dumps(["two\nlines"]), encoding="utf-8")
    with pytest.raises(StorageProtectionError):
        load_failed_run_notes(tmp_path)
    notes.write_text(json.dumps({"note": "x"}), encoding="utf-8")
    with pytest.raises(StorageProtectionError):
        load_failed_run_notes(tmp_path)
    notes.write_text(json.dumps(["REPLACE_WITH_NOTE"]), encoding="utf-8")
    with pytest.raises(StorageProtectionError):
        load_failed_run_notes(tmp_path)
