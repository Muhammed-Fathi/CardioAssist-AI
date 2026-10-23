"""Local-only runtime, authorization, provenance, and storage guards for M2c."""
from __future__ import annotations

import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from research.audit.git_safety import verify_git_ignore
from research.audit.provenance import (
    load_authorization_manifest,
    sha256_file,
    validate_official_source_url,
    verify_dataset_authorized_for_audit,
)
from research.experiments.config import (
    ALLOWED_MODEL_FAMILIES,
    ALLOWED_OPERATIONS,
    D047_AUTHORIZATION_COMMENT,
    D047_AUTHORIZATION_STATUS,
    D047_AUTHORIZING_MAINTAINER,
    D047_AUTHORIZING_MERGED_AT_UTC,
    D047_AUTHORIZING_MERGE_SHA,
    D047_AUTHORIZING_PR_NUMBER,
    D047_LOCAL_SIGNATURE_ATTESTATION,
    D047_REPORT_BANNER,
    DEFAULT_CONFIG,
    FORBIDDEN_OPERATIONS,
    PLAN_PATH,
    PROTOCOL_RELATIVE_PATH,
    REPOSITORY_ROOT,
    ExperimentConfig,
)
from research.experiments.data_adapter import sha256_bytes
from research.experiments.errors import (
    AuthorizationError,
    ProvenanceError,
    RuntimeGuardError,
    StorageProtectionError,
)

D047_AUTH_RELATIVE_PATH = PurePosixPath(
    "data/manifests/internal_exploratory_authorization.local.json"
)
D046_AUTH_RELATIVE_PATH = PurePosixPath("data/manifests/gate_da_authorization.local.json")
PROVENANCE_RELATIVE_PATH = PurePosixPath("data/manifests/provenance_manifest.json")
SOURCE_RELATIVE_PATH = PurePosixPath(DEFAULT_CONFIG.source_relative_path)
LICENSE_RELATIVE_PATH = PurePosixPath("data/manifests/licenses/uci-45-license-snapshot.txt")
OUTPUT_ROOT_RELATIVE_PATH = PurePosixPath("data/experiments")

CANONICAL_UCI_45_URL = "https://archive.ics.uci.edu/dataset/45/heart+disease"
CANONICAL_UCI_45_DOI = "10.24432/C52P4X"
EXPECTED_LICENSE_SPDX = "CC-BY-4.0"
D047_SIGNATURE_SEMANTICS = "HUMAN_ATTESTATION_FIELDS_NOT_A_CRYPTOGRAPHIC_SIGNATURE"
EXPECTED_LOCAL_PROVENANCE_STATUS = "VERIFIED"
EXPECTED_OFFICIAL_SOURCE_STATUS = "HUMAN_ATTESTED_NOT_INDEPENDENTLY_PROVEN_BY_LOCAL_HASH"
D046_AUTHORIZED_WORKFLOW_STATUS = "AUTHORIZED_FOR_LOCAL_READ_ONLY_AUDIT"
D046_DATASET_AUTHORIZED_STATUS = "AUTHORIZED_FOR_READ_ONLY_AUDIT"
D047_PROBES = (
    "data/",
    "data/raw/uci-45/processed.cleveland.data",
    "data/manifests/provenance_manifest.json",
    "data/manifests/gate_da_authorization.local.json",
    "data/manifests/internal_exploratory_authorization.local.json",
    "data/manifests/licenses/uci-45-license-snapshot.txt",
    "data/experiments/",
    "data/experiments/.d047-protection-probe",
)
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
GIT_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
SAFE_RUN_ID_RE = re.compile(r"^run-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}$")
REMOTE_ENV_NAMES = frozenset({
    "GITHUB_ACTIONS",
    "GITLAB_CI",
    "JENKINS_URL",
    "BUILD_BUILDID",
    "TF_BUILD",
    "KAGGLE_KERNEL_RUN_TYPE",
    "COLAB_RELEASE_TAG",
    "AZUREML_RUN_ID",
    "DATABRICKS_RUNTIME_VERSION",
    "CODESPACES",
    "GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN",
})


class PreflightContext:
    """Sanitized result of successful authorization/provenance preflight."""

    __slots__ = (
        "repo_root",
        "source_path",
        "source_sha256",
        "source_size_bytes",
        "provenance_sha256",
        "d046_authorization_sha256",
        "d047_authorization_sha256",
        "license_sha256",
        "authorization",
        "current_git_commit",
        "downloaded_at_utc",
        "download_timestamp_evidence_status",
        "provenance_recorded_at_utc",
    )

    def __init__(
        self,
        *,
        repo_root: Path,
        source_path: Path,
        source_sha256: str,
        source_size_bytes: int,
        provenance_sha256: str,
        d046_authorization_sha256: str,
        d047_authorization_sha256: str,
        license_sha256: str,
        authorization: Mapping[str, Any],
        current_git_commit: str,
        downloaded_at_utc: str,
        download_timestamp_evidence_status: str,
        provenance_recorded_at_utc: str,
    ) -> None:
        self.repo_root = repo_root
        self.source_path = source_path
        self.source_sha256 = source_sha256
        self.source_size_bytes = source_size_bytes
        self.provenance_sha256 = provenance_sha256
        self.d046_authorization_sha256 = d046_authorization_sha256
        self.d047_authorization_sha256 = d047_authorization_sha256
        self.license_sha256 = license_sha256
        self.authorization = dict(authorization)
        self.current_git_commit = current_git_commit
        self.downloaded_at_utc = downloaded_at_utc
        self.download_timestamp_evidence_status = download_timestamp_evidence_status
        self.provenance_recorded_at_utc = provenance_recorded_at_utc


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise StorageProtectionError("Git safety checks could not be executed.") from exc


def _truthy_environment(value: str | None) -> bool:
    return isinstance(value, str) and value.strip().lower() in {"1", "true", "yes", "on"}


def _has_reparse_or_symlink_component(path: Path) -> bool:
    """Detect symbolic links and Windows reparse points, including on Python 3.11."""
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    parts = absolute.parts[1:] if absolute.anchor else absolute.parts
    for part in parts:
        current = current / part
        try:
            if current.is_symlink() or bool(getattr(current, "is_junction", lambda: False)()):
                return True
            if current.exists():
                attributes = getattr(current.lstat(), "st_file_attributes", 0)
                if attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
                    return True
        except OSError:
            return True
    try:
        resolved = absolute.resolve(strict=True)
    except OSError:
        return True
    return os.path.normcase(str(resolved)) != os.path.normcase(str(absolute))


def enforce_local_windows_runtime(
    *,
    repo_root: Path = REPOSITORY_ROOT,
    environ: Mapping[str, str] | None = None,
    platform_name: str | None = None,
    interactive: bool | None = None,
) -> None:
    """Allow real-data operations only on a local fixed Windows drive, never CI/cloud."""
    env = os.environ if environ is None else environ
    active_platform = os.name if platform_name is None else platform_name
    if active_platform not in {"nt", "win32"}:
        raise RuntimeGuardError(
            "Real-data preflight/run is Windows-local only; no source rows were parsed."
        )
    if _truthy_environment(env.get("CI")) or any(
        _truthy_environment(env.get(name)) for name in REMOTE_ENV_NAMES
    ):
        raise RuntimeGuardError(
            "Real-data execution is prohibited in CI, hosted notebooks, or detected remote runtimes."
        )
    if any(name.upper().startswith("ARENA") for name in env):
        raise RuntimeGuardError("Real-data execution is prohibited in Arena environments.")
    if interactive is None:
        import sys

        interactive = bool(sys.stdin.isatty())
    if not interactive:
        raise RuntimeGuardError("Real-data execution requires an interactive local Windows console.")

    root = Path(repo_root).expanduser()
    if _has_reparse_or_symlink_component(root):
        raise RuntimeGuardError("Repository paths may not contain symlinks, junctions, or Windows reparse points.")
    try:
        resolved = root.resolve(strict=True)
    except OSError as exc:
        raise RuntimeGuardError("The repository root is not a local, accessible directory.") from exc
    if not resolved.is_dir() or str(resolved).startswith("\\\\"):
        raise RuntimeGuardError("UNC/network repository paths are prohibited for real-data execution.")
    if resolved.anchor.startswith("\\\\"):
        raise RuntimeGuardError("UNC/network repository paths are prohibited for real-data execution.")

    try:
        import ctypes

        drive_type = int(ctypes.windll.kernel32.GetDriveTypeW(resolved.anchor))  # type: ignore[attr-defined]
    except Exception as exc:
        raise RuntimeGuardError("Could not verify that the repository is on a local fixed Windows drive.") from exc
    # DRIVE_FIXED = 3. Remote, removable, CD-ROM, and unknown roots fail closed.
    if drive_type != 3:
        raise RuntimeGuardError("Real-data execution requires a local fixed Windows drive (not a network drive).")


def _read_json_no_duplicate_keys(path: Path, *, error_type: type[Exception], label: str) -> dict[str, Any]:
    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    if path.is_symlink() or not path.is_file():
        raise error_type(f"Required protected {label} is missing or unsafe.")
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicates)
    except Exception as exc:
        raise error_type(f"Protected {label} is malformed or unreadable.") from exc
    if not isinstance(value, dict):
        raise error_type(f"Protected {label} must contain one JSON object.")
    return value


def assert_no_symlink_components(repo_root: Path, relative_path: PurePosixPath | str) -> Path:
    """Reject symlinks/junctions at every component beneath the repository root."""
    relative = PurePosixPath(str(relative_path).replace("\\", "/"))
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts) or ":" in str(relative):
        raise StorageProtectionError("Protected data path must be a safe repository-relative path.")
    input_root = Path(repo_root)
    if _has_reparse_or_symlink_component(input_root):
        raise StorageProtectionError("Repository paths may not contain symlinks, junctions, or reparse points.")
    root = input_root.resolve(strict=True)
    current = root
    for part in relative.parts:
        current = current / part
        try:
            if current.is_symlink() or bool(getattr(current, "is_junction", lambda: False)()):
                raise StorageProtectionError("A protected data path contains a symlink or junction.")
            if current.exists():
                attributes = getattr(current.lstat(), "st_file_attributes", 0)
                if attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
                    raise StorageProtectionError("A protected data path contains a Windows reparse point.")
        except OSError as exc:
            raise StorageProtectionError("A protected data path could not be inspected safely.") from exc
    try:
        resolved = current.resolve(strict=False)
    except OSError as exc:
        raise StorageProtectionError("Protected data path resolution failed.") from exc
    expected = root.joinpath(*relative.parts)
    if os.path.normcase(str(resolved)) != os.path.normcase(str(expected)):
        raise StorageProtectionError("Protected data path resolves outside its exact repository location.")
    return current


def verify_git_protected_storage(repo_root: Path) -> None:
    """Require every data/manifests/raw/experiment path to be ignored and untracked."""
    try:
        verify_git_ignore(repo_root, D047_PROBES)
    except Exception as exc:
        raise StorageProtectionError(
            "Git-ignore protection failed: all /data paths must be ignored and no file under /data may be tracked."
        ) from exc
    for relative in (
        "data",
        "data/raw",
        "data/raw/uci-45",
        "data/manifests",
        "data/manifests/licenses",
        "data/experiments",
    ):
        assert_no_symlink_components(repo_root, PurePosixPath(relative))


def _valid_iso_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip() or "REPLACE" in value.upper():
        return False
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return False
    return parsed <= datetime.now(timezone.utc) + timedelta(minutes=5)


def _valid_provenance_utc_timestamp(value: Any, *, allow_unknown: bool = False) -> bool:
    if allow_unknown and value == "UNKNOWN_PENDING_HUMAN_VERIFICATION":
        return True
    if not isinstance(value, str) or not re.fullmatch(
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$", value
    ):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() == timedelta(0)


def validate_d047_authorization(
    manifest: Mapping[str, Any],
    *,
    repo_root: Path,
    current_git_commit: str,
    config: ExperimentConfig = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Validate the separate local human-attested D-047 scope and frozen hashes."""
    if manifest.get("schema_version") != "0.2.0" or manifest.get("decision_id") != "D-047":
        raise AuthorizationError("Local D-047 authorization manifest version or decision ID is invalid.")
    if manifest.get("authorization_status") != D047_AUTHORIZATION_STATUS:
        raise AuthorizationError(
            "D-047 local authorization is not complete; the checked-in template does not authorize a run."
        )
    if manifest.get("experiment_type") != D047_REPORT_BANNER:
        raise AuthorizationError("D-047 local authorization has an unexpected experiment type.")
    if manifest.get("supervisor_signoff_claimed") is not False:
        raise AuthorizationError("Supervisor approval must remain unclaimed; Gate PT P-3 is closed.")
    if manifest.get("maintainer_approval_comment_exact") != D047_AUTHORIZATION_COMMENT:
        raise AuthorizationError("The exact D-047 maintainer authorization comment is not recorded locally.")
    if manifest.get("approval_pr_number") != D047_AUTHORIZING_PR_NUMBER:
        raise AuthorizationError("D-047 authorization must bind the verified governance PR #31.")
    merged_sha = manifest.get("approval_pr_merged_commit_sha")
    pinned_sha = manifest.get("pinned_protocol_git_commit_sha")
    if not isinstance(merged_sha, str) or not GIT_SHA_RE.fullmatch(merged_sha):
        raise AuthorizationError("The merged governance commit SHA is missing or malformed.")
    if merged_sha.lower() != D047_AUTHORIZING_MERGE_SHA:
        raise AuthorizationError("The local authorization does not bind the verified D-047 governance merge.")
    if not isinstance(pinned_sha, str) or pinned_sha.lower() != D047_AUTHORIZING_MERGE_SHA:
        raise AuthorizationError("The frozen protocol commit must be the verified PR #31 merge commit.")

    signer = manifest.get("local_signer")
    if not isinstance(signer, str) or signer.strip() != D047_AUTHORIZING_MAINTAINER:
        raise AuthorizationError("The named D-047 local human signer must be the verified project maintainer.")
    signed_at = manifest.get("local_signed_at_iso8601")
    if not _valid_iso_timestamp(signed_at):
        raise AuthorizationError("A timezone-aware local human-signature timestamp is required.")
    signed_at_parsed = datetime.fromisoformat(signed_at.strip().replace("Z", "+00:00"))
    governance_merged_at = datetime.fromisoformat(D047_AUTHORIZING_MERGED_AT_UTC)
    if signed_at_parsed < governance_merged_at:
        raise AuthorizationError("Local D-047 signature must post-date the verified governance PR merge.")
    if manifest.get("local_signature_attestation") != D047_LOCAL_SIGNATURE_ATTESTATION:
        raise AuthorizationError("The required local human signature attestation is missing or altered.")
    if manifest.get("signature_semantics") != D047_SIGNATURE_SEMANTICS:
        raise AuthorizationError("Unexpected local signature semantics; no cryptographic signature is claimed.")

    if manifest.get("dataset_id") != "DA-A2":
        raise AuthorizationError("Only DA-A2 is in the first internal experiment scope.")
    if manifest.get("allowed_original_relative_file") != config.source_relative_path:
        raise AuthorizationError("D-047 local authorization names an unapproved source file.")
    if manifest.get("authorized_source_row_count") != config.expected_row_count:
        raise AuthorizationError("D-047 local authorization has an unexpected source row-count bound.")
    if manifest.get("allowlisted_model_families") != list(ALLOWED_MODEL_FAMILIES):
        raise AuthorizationError("D-047 local authorization model families do not match the registered allowlist.")
    if manifest.get("allowed_operations_if_approved") != list(ALLOWED_OPERATIONS):
        raise AuthorizationError("D-047 local authorization operations do not match the registered allowlist.")
    if manifest.get("forbidden_operations") != list(FORBIDDEN_OPERATIONS):
        raise AuthorizationError("D-047 local authorization omits or alters required forbidden operations.")
    if manifest.get("allowed_runtime") != "LOCAL_WINDOWS_CPU_ONLY":
        raise AuthorizationError("D-047 local authorization must be Windows-local and CPU-only.")
    if manifest.get("protected_outputs_relative_root") != str(OUTPUT_ROOT_RELATIVE_PATH):
        raise AuthorizationError("D-047 local authorization names an unprotected output root.")

    expected_source_sha = manifest.get("expected_sha256_from_protected_provenance_manifest")
    if not isinstance(expected_source_sha, str) or not SHA256_RE.fullmatch(expected_source_sha):
        raise AuthorizationError("A full source SHA-256 from the protected provenance manifest is required.")
    protocol_sha = manifest.get("frozen_protocol_sha256")
    plan_sha = manifest.get("frozen_experiment_plan_sha256")
    if not isinstance(protocol_sha, str) or not SHA256_RE.fullmatch(protocol_sha):
        raise AuthorizationError("A frozen D-047 protocol SHA-256 is required.")
    if not isinstance(plan_sha, str) or not SHA256_RE.fullmatch(plan_sha):
        raise AuthorizationError("A frozen registered-plan SHA-256 is required.")

    if current_git_commit.lower() != current_git_commit or not GIT_SHA_RE.fullmatch(current_git_commit):
        raise AuthorizationError("The local code commit is not a valid full Git commit SHA.")
    protocol_path = assert_no_symlink_components(repo_root, PROTOCOL_RELATIVE_PATH)
    plan_path = assert_no_symlink_components(repo_root, PLAN_PATH.relative_to(REPOSITORY_ROOT).as_posix())
    try:
        actual_protocol_sha, _ = sha256_file(protocol_path)
        actual_plan_sha, _ = sha256_file(plan_path)
    except Exception as exc:
        raise AuthorizationError("Frozen protocol or experiment plan could not be hashed safely.") from exc
    if actual_protocol_sha.lower() != protocol_sha.lower() or actual_plan_sha.lower() != plan_sha.lower():
        raise AuthorizationError("The local protocol or registered plan differs from the human-frozen hash.")

    for commit_sha, label in ((merged_sha, "governance"), (pinned_sha, "protocol")):
        exists = _git(repo_root, "cat-file", "-e", f"{commit_sha}^{{commit}}")
        if exists.returncode != 0:
            raise AuthorizationError(f"The pinned {label} commit is not present in the local Git repository.")
        ancestor = _git(repo_root, "merge-base", "--is-ancestor", commit_sha, current_git_commit)
        if ancestor.returncode != 0:
            raise AuthorizationError(f"The pinned {label} commit is not an ancestor of the current code commit.")
    try:
        pinned_protocol = _git(
            repo_root,
            "show",
            f"{pinned_sha}:{PROTOCOL_RELATIVE_PATH.as_posix()}",
        )
    except Exception as exc:
        raise AuthorizationError("The frozen protocol commit could not be read from Git.") from exc
    if pinned_protocol.returncode != 0 or sha256_bytes(pinned_protocol.stdout.encode("utf-8")) != protocol_sha.lower():
        raise AuthorizationError("The protocol file at the pinned governance commit does not match its signed hash.")

    return {
        "local_signer": signer.strip(),
        "local_signed_at_iso8601": manifest["local_signed_at_iso8601"],
        "authorization_comment_exact": manifest["maintainer_approval_comment_exact"],
        "authorization_pr_number": D047_AUTHORIZING_PR_NUMBER,
        "authorization_merged_commit_sha": D047_AUTHORIZING_MERGE_SHA,
        "pinned_protocol_git_commit_sha": D047_AUTHORIZING_MERGE_SHA,
        "expected_source_sha256": expected_source_sha.lower(),
        "frozen_protocol_sha256": protocol_sha.lower(),
        "frozen_experiment_plan_sha256": plan_sha.lower(),
        "local_manifest_sha256": None,
        "signature_semantics": manifest["signature_semantics"],
    }


def _verify_d046_read_only_authorization(repo_root: Path) -> tuple[dict[str, Any], str]:
    auth_path = assert_no_symlink_components(repo_root, D046_AUTH_RELATIVE_PATH)
    try:
        auth = load_authorization_manifest(auth_path)
        da_a2 = verify_dataset_authorized_for_audit(auth, "DA-A2", requested_usage_role="read_only_audit")
    except Exception as exc:
        raise AuthorizationError(
            "D-046 local read-only audit authorization for DA-A2 is missing or invalid; it cannot authorize training."
        ) from exc
    if auth.get("workflow_status") != D046_AUTHORIZED_WORKFLOW_STATUS:
        raise AuthorizationError("D-046 global workflow is not explicitly authorized for local read-only audit.")
    if auth.get("supervisor_approval_claimed") is not False:
        raise AuthorizationError("D-046 must not claim supervisor approval.")
    if auth.get("gate_pt_status") != "CLOSED_REQUIRES_SUPERVISOR_SIGNOFF_P3":
        raise AuthorizationError("Formal Gate PT P-3 must remain closed.")
    if da_a2.get("authorization_status") != D046_DATASET_AUTHORIZED_STATUS:
        raise AuthorizationError("D-046 DA-A2 is not explicitly authorized for local read-only audit.")
    if da_a2.get("training_authorized") is not False:
        raise AuthorizationError("D-046 read-only audit authorization must not enable model training.")
    try:
        auth_sha, _ = sha256_file(auth_path)
    except Exception as exc:
        raise AuthorizationError("D-046 local authorization manifest could not be hashed.") from exc
    return auth, auth_sha


def _verify_cleveland_provenance(
    repo_root: Path,
    *,
    expected_source_sha256: str,
) -> tuple[dict[str, Any], str, str, int]:
    provenance_path = assert_no_symlink_components(repo_root, PROVENANCE_RELATIVE_PATH)
    license_path = assert_no_symlink_components(repo_root, LICENSE_RELATIVE_PATH)
    manifest = _read_json_no_duplicate_keys(
        provenance_path,
        error_type=ProvenanceError,
        label="DA-A2 source provenance manifest",
    )
    if manifest.get("governance_decision_id") != "D-046":
        raise ProvenanceError("Protected source provenance is not recorded under the D-046 audit context.")
    if not isinstance(manifest.get("acquirer"), str) or not manifest["acquirer"].strip():
        raise ProvenanceError("Protected source provenance does not name a human acquirer.")
    if not isinstance(manifest.get("audit_reviewer"), str) or not manifest["audit_reviewer"].strip():
        raise ProvenanceError("Protected source provenance does not name a human audit reviewer.")
    if not _valid_provenance_utc_timestamp(manifest.get("manifest_recorded_at_utc")):
        raise ProvenanceError("Protected source provenance has an invalid manifest-recorded UTC timestamp.")
    semantics = manifest.get("provenance_verification_semantics")
    if not isinstance(semantics, dict):
        raise ProvenanceError("Protected source provenance semantics are missing.")
    if semantics.get("local_file_integrity_status") != "VERIFIED":
        raise ProvenanceError("Protected source provenance does not claim verified local file integrity.")
    if semantics.get("official_source_provenance_status") != EXPECTED_OFFICIAL_SOURCE_STATUS:
        raise ProvenanceError("Official-source origin must remain honestly human-attested, not independently proven by hash.")
    files = manifest.get("files")
    if not isinstance(files, list):
        raise ProvenanceError("Protected source provenance has no file inventory.")
    matching = [
        entry for entry in files
        if isinstance(entry, dict)
        and entry.get("dataset_id") == "DA-A2"
        and entry.get("filename") == SOURCE_RELATIVE_PATH.name
    ]
    if len(matching) != 1:
        raise ProvenanceError("Protected provenance must contain exactly one UCI-45 processed Cleveland entry.")
    entry = matching[0]
    if not _valid_provenance_utc_timestamp(entry.get("manifest_recorded_at_utc")):
        raise ProvenanceError("Protected Cleveland provenance has an invalid record timestamp.")
    downloaded_at = entry.get("downloaded_at_utc")
    if not _valid_provenance_utc_timestamp(downloaded_at, allow_unknown=True):
        raise ProvenanceError("Protected Cleveland provenance has an invalid download timestamp.")
    if entry.get("uci_id") != 45 or entry.get("doi") != CANONICAL_UCI_45_DOI:
        raise ProvenanceError("Protected Cleveland source provenance has an unexpected UCI ID or DOI.")
    try:
        validate_official_source_url(
            str(entry.get("official_source_url", "")),
            CANONICAL_UCI_45_URL,
            "DA-A2",
        )
    except Exception as exc:
        raise ProvenanceError("Protected provenance does not identify the canonical official UCI source.") from exc
    if entry.get("relative_path") != SOURCE_RELATIVE_PATH.as_posix():
        raise ProvenanceError("Protected provenance source path is not the exact approved Cleveland file.")
    if entry.get("local_file_integrity_status") != EXPECTED_LOCAL_PROVENANCE_STATUS:
        raise ProvenanceError("Protected provenance local-integrity status is not VERIFIED.")
    if entry.get("official_source_provenance_status") != EXPECTED_OFFICIAL_SOURCE_STATUS:
        raise ProvenanceError("Protected provenance overstates or omits official-origin verification.")
    if entry.get("license_spdx") != EXPECTED_LICENSE_SPDX:
        raise ProvenanceError("Protected Cleveland license is not recorded as CC-BY-4.0.")

    provenance_source_sha = entry.get("sha256")
    if not isinstance(provenance_source_sha, str) or not SHA256_RE.fullmatch(provenance_source_sha):
        raise ProvenanceError("Protected provenance has no valid source SHA-256.")
    if provenance_source_sha.lower() != expected_source_sha256.lower():
        raise ProvenanceError("D-047 local source hash does not match D-046 protected provenance.")
    expected_size = entry.get("size_bytes")
    if type(expected_size) is not int or expected_size <= 0:
        raise ProvenanceError("Protected provenance has no valid original byte-size record.")

    if entry.get("license_snapshot_path") != LICENSE_RELATIVE_PATH.as_posix():
        raise ProvenanceError("License snapshot path is not the approved local UCI-45 license file.")
    expected_license_sha = entry.get("license_snapshot_sha256")
    if not isinstance(expected_license_sha, str) or not SHA256_RE.fullmatch(expected_license_sha):
        raise ProvenanceError("Protected provenance has no valid license snapshot SHA-256.")
    try:
        actual_license_sha, _ = sha256_file(license_path)
        license_text = license_path.read_text(encoding="utf-8", errors="strict")
    except Exception as exc:
        raise ProvenanceError("UCI-45 license snapshot is missing or unreadable.") from exc
    if actual_license_sha.lower() != expected_license_sha.lower():
        raise ProvenanceError("UCI-45 license snapshot SHA-256 does not match its protected manifest.")
    if "cc by 4.0" not in license_text.lower() and "creative commons attribution 4.0" not in license_text.lower():
        raise ProvenanceError("UCI-45 license snapshot does not state CC BY 4.0.")
    try:
        provenance_sha, _ = sha256_file(provenance_path)
    except Exception as exc:
        raise ProvenanceError("Protected source provenance manifest could not be hashed.") from exc
    return entry, provenance_sha, actual_license_sha, expected_size


def _current_commit_and_clean_tree(repo_root: Path) -> str:
    top_level = _git(repo_root, "rev-parse", "--show-toplevel")
    if top_level.returncode != 0 or os.path.normcase(os.path.abspath(top_level.stdout.strip())) != os.path.normcase(os.path.abspath(repo_root)):
        raise StorageProtectionError("The runner is not executing from its exact Git repository root.")
    head = _git(repo_root, "rev-parse", "--verify", "HEAD^{commit}")
    commit = head.stdout.strip().lower()
    if head.returncode != 0 or not GIT_SHA_RE.fullmatch(commit):
        raise StorageProtectionError("A committed Git code version is required for a reproducible real run.")
    status = _git(repo_root, "status", "--porcelain", "--untracked-files=all")
    if status.returncode != 0 or status.stdout.strip():
        raise StorageProtectionError("The code worktree must be clean before real-data preflight/run.")
    return commit


def run_preflight(
    *,
    repo_root: Path = REPOSITORY_ROOT,
    config: ExperimentConfig = DEFAULT_CONFIG,
) -> PreflightContext:
    """Validate every local gate and hash without parsing source rows or fitting."""
    input_root = Path(repo_root).expanduser()
    if _has_reparse_or_symlink_component(input_root):
        raise StorageProtectionError("Repository paths may not contain symlinks, junctions, or reparse points.")
    root = input_root.resolve(strict=True)
    enforce_local_windows_runtime(repo_root=root)
    verify_git_protected_storage(root)
    current_commit = _current_commit_and_clean_tree(root)

    d047_path = assert_no_symlink_components(root, D047_AUTH_RELATIVE_PATH)
    d047_manifest = _read_json_no_duplicate_keys(
        d047_path,
        error_type=AuthorizationError,
        label="D-047 local authorization manifest",
    )
    authorization = validate_d047_authorization(
        d047_manifest,
        repo_root=root,
        current_git_commit=current_commit,
        config=config,
    )
    d047_sha, _ = sha256_file(d047_path)
    authorization["local_manifest_sha256"] = d047_sha

    _verify_d046_read_only_authorization(root)
    d046_path = assert_no_symlink_components(root, D046_AUTH_RELATIVE_PATH)
    d046_sha, _ = sha256_file(d046_path)

    entry, provenance_sha, license_sha, expected_size = _verify_cleveland_provenance(
        root,
        expected_source_sha256=authorization["expected_source_sha256"],
    )
    source_path = assert_no_symlink_components(root, SOURCE_RELATIVE_PATH)
    try:
        resolved_source = source_path.resolve(strict=True)
        expected_source = (root / Path(*SOURCE_RELATIVE_PATH.parts)).resolve(strict=True)
        if resolved_source != expected_source:
            raise StorageProtectionError("Protected source path resolves outside its canonical location.")
        if source_path.name != "processed.cleveland.data":
            raise StorageProtectionError("Only processed.cleveland.data may be opened by the local runner.")
        source_sha, source_size = sha256_file(source_path)
    except StorageProtectionError:
        raise
    except Exception as exc:
        raise ProvenanceError("The protected Cleveland source is missing or unreadable.") from exc
    if source_sha.lower() != authorization["expected_source_sha256"]:
        raise ProvenanceError("The local source SHA-256 does not match the signed D-047 hash.")
    if source_sha.lower() != str(entry["sha256"]).lower() or source_size != expected_size:
        raise ProvenanceError("The local source bytes do not match protected D-046 provenance.")

    return PreflightContext(
        repo_root=root,
        source_path=source_path,
        source_sha256=source_sha,
        source_size_bytes=source_size,
        provenance_sha256=provenance_sha,
        d046_authorization_sha256=d046_sha,
        d047_authorization_sha256=d047_sha,
        license_sha256=license_sha,
        authorization=authorization,
        current_git_commit=current_commit,
        downloaded_at_utc=str(entry["downloaded_at_utc"]),
        download_timestamp_evidence_status=(
            "UNVERIFIED"
            if entry["downloaded_at_utc"] == "UNKNOWN_PENDING_HUMAN_VERIFICATION"
            else "SOURCE-REPORTED"
        ),
        provenance_recorded_at_utc=str(entry["manifest_recorded_at_utc"]),
    )


def verify_source_still_unchanged(context: PreflightContext) -> None:
    """Re-hash the original source without parsing or mutating it."""
    try:
        current_sha, current_size = sha256_file(context.source_path)
    except Exception as exc:
        raise ProvenanceError("The original source became missing or unreadable during the run.") from exc
    if current_sha.lower() != context.source_sha256.lower() or current_size != context.source_size_bytes:
        raise ProvenanceError("Original source byte-identity check failed; no report may be accepted.")


def create_protected_run_directory(
    *,
    repo_root: Path,
    run_id: str,
) -> Path:
    """Create a unique ignored local output directory; no arbitrary output path is accepted."""
    if not SAFE_RUN_ID_RE.fullmatch(run_id):
        raise StorageProtectionError("Run ID is not in the fixed safe format.")
    root = Path(repo_root).resolve(strict=True)
    verify_git_protected_storage(root)
    relative_root = OUTPUT_ROOT_RELATIVE_PATH
    output_root = assert_no_symlink_components(root, relative_root)
    try:
        output_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        output_root = assert_no_symlink_components(root, relative_root)
        try:
            os.chmod(output_root, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        except OSError:
            # NTFS access-control lists are inherited; preserve and review them locally.
            pass
        run_dir_rel = relative_root / run_id
        run_dir = assert_no_symlink_components(root, run_dir_rel)
        run_dir.mkdir(mode=0o700, exist_ok=False)
        resolved = run_dir.resolve(strict=True)
        expected = (root / Path(*run_dir_rel.parts)).resolve(strict=True)
        if os.path.normcase(str(resolved)) != os.path.normcase(str(expected)):
            raise StorageProtectionError("Experiment output directory escaped its protected local root.")
        try:
            os.chmod(run_dir, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        except OSError:
            # NTFS access-control lists are inherited from the local repository
            # parent; the handoff requires the human operator to protect that ACL.
            pass
        verify_git_protected_storage(root)
        return run_dir
    except FileExistsError as exc:
        raise StorageProtectionError("The generated experiment output directory already exists; refusing overwrite.") from exc
    except StorageProtectionError:
        raise
    except OSError as exc:
        raise StorageProtectionError("Unable to create a protected local experiment output directory.") from exc
