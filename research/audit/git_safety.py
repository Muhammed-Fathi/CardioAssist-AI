"""Git-ignore and data-directory containment checks for the M2a dataset audit toolchain."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Sequence

from research.audit.exceptions import GitIgnoreProtectionError
from research.audit.registry import EVIDENCE_VERIFIED

DEFAULT_DATA_PROBE_PATHS: tuple[str, ...] = (
    "data/",
    "data/raw/uci-412/Z-Alizadeh sani dataset.xlsx",
    "data/raw/uci-45/processed.cleveland.data",
    "data/raw/uci-45/cleveland.data",
    "data/raw/uci-45/heart-disease.names",
    "data/raw/uci-411/extention of Z-Alizadeh sani dataset.xlsx",
    "data/raw/uci-145/heart.dat",
    "data/manifests/provenance_manifest.json",
)


@dataclass(frozen=True)
class GitIgnoreCheckResult:
    """Result of verifying that /data/ paths are ignored by Git and untracked."""

    repo_root: str
    checked_paths: tuple[str, ...]
    ignore_rules_matched: tuple[str, ...]
    tracked_files_under_data: tuple[str, ...]
    passed: bool
    evidence_status: str = EVIDENCE_VERIFIED

    def to_dict(self) -> dict[str, object]:
        return {
            "repo_root": self.repo_root,
            "checked_paths": list(self.checked_paths),
            "ignore_rules_matched": list(self.ignore_rules_matched),
            "tracked_files_under_data": list(self.tracked_files_under_data),
            "passed": self.passed,
            "evidence_status": self.evidence_status,
        }


def verify_data_root_containment(
    repo_root: Path,
    target_path: Path,
    *,
    allow_external_tmp_root: Path | None = None,
) -> Path:
    """Ensure a dataset path resolves inside <repo_root>/data/ (or an explicit temporary test root)."""
    resolved_repo = repo_root.resolve()
    resolved_data_root = (resolved_repo / "data").resolve()
    resolved_target = target_path.resolve()

    if allow_external_tmp_root is not None:
        resolved_tmp = allow_external_tmp_root.resolve()
        if resolved_target == resolved_tmp or resolved_tmp in resolved_target.parents:
            return resolved_target

    if resolved_target != resolved_data_root and resolved_data_root not in resolved_target.parents:
        raise GitIgnoreProtectionError(
            f"Data path '{target_path}' resolves outside the git-ignored repository '/data/' root "
            f"('{resolved_data_root}'). Refusing to access uncontained path."
        )
    return resolved_target


def verify_git_ignore(
    repo_root: Path,
    probe_relative_paths: Sequence[str] = DEFAULT_DATA_PROBE_PATHS,
) -> GitIgnoreCheckResult:
    """Run `git check-ignore -v` and `git ls-files` to guarantee /data/ is ignored and untracked."""
    resolved_repo = repo_root.resolve()
    if not (resolved_repo / ".git").exists():
        raise GitIgnoreProtectionError(
            f"Repository root '{resolved_repo}' does not contain a .git directory; cannot verify git check-ignore."
        )

    rel_paths = tuple(probe_relative_paths) if probe_relative_paths else DEFAULT_DATA_PROBE_PATHS
    matched_rules: list[str] = []

    for rel_path in rel_paths:
        normalized_rel = rel_path.replace("\\", "/")
        proc = subprocess.run(
            ["git", "check-ignore", "-v", "--", normalized_rel],
            cwd=str(resolved_repo),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            raise GitIgnoreProtectionError(
                f"git check-ignore failed for path '{normalized_rel}' (exit {proc.returncode}). "
                "Patient-level data paths must be ignored by .gitignore before any acquisition or audit."
            )
        matched_rules.append(proc.stdout.strip().splitlines()[0])

    ls_proc = subprocess.run(
        ["git", "ls-files", "--", "data", "data/"],
        cwd=str(resolved_repo),
        capture_output=True,
        text=True,
        check=False,
    )
    if ls_proc.returncode != 0:
        raise GitIgnoreProtectionError(
            f"git ls-files failed with exit code {ls_proc.returncode}: {ls_proc.stderr.strip()}"
        )
    tracked = tuple(line.strip() for line in ls_proc.stdout.splitlines() if line.strip())
    if tracked:
        raise GitIgnoreProtectionError(
            f"Found {len(tracked)} git-tracked file(s) under /data/: {tracked[:5]}. "
            "No file under /data/ may ever be tracked by Git."
        )

    status_proc = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all", "--", "data/"],
        cwd=str(resolved_repo),
        capture_output=True,
        text=True,
        check=False,
    )
    if status_proc.returncode != 0:
        raise GitIgnoreProtectionError(
            f"git status check failed with exit code {status_proc.returncode}: {status_proc.stderr.strip()}"
        )
    unignored_lines = [line.strip() for line in status_proc.stdout.splitlines() if line.strip()]
    if unignored_lines:
        raise GitIgnoreProtectionError(
            f"git status reported unignored or staged paths under /data/ ({len(unignored_lines)} entry/entries). "
            "Aborting fail-closed."
        )

    return GitIgnoreCheckResult(
        repo_root=str(resolved_repo),
        checked_paths=rel_paths,
        ignore_rules_matched=tuple(matched_rules),
        tracked_files_under_data=tracked,
        passed=True,
        evidence_status=EVIDENCE_VERIFIED,
    )
