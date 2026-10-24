"""Local-only runtime, authorization, provenance, and storage guards.

The real-data path is deliberately unusable outside an interactive local Windows
console on a fixed local drive. It requires, in order:

1. the ratified D-046 read-only authorization and protected provenance for
   ``DA-A1`` (which permits *audit*, never fitting);
2. a separate, human-signed, hash-bound M3a internal-research authorization
   naming the exact proposal, feature dictionary, plan, source hash and file;
3. a clean committed worktree, Git-ignored ``/data/``, and a protected output
   root created only after those gates pass.

The checked-in authorization JSON is a non-authorizing template.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
from typing import Any, Mapping

from research.audit.git_safety import verify_git_ignore
from research.audit.provenance import (
    load_authorization_manifest,
    sha256_file,
    validate_provenance_manifest,
    verify_dataset_authorized_for_audit,
)
from research.experiments.safety import (  # reused, unmodified local-runtime guard
    assert_no_symlink_components,
    enforce_local_windows_runtime,
)
from research.uci412.config import (
    ALLOWED_MODEL_FAMILIES,
    ALLOWED_OPERATIONS,
    AUTHORIZATION_TEMPLATE_PATH,
    DEFAULT_CONFIG,
    FORBIDDEN_OPERATIONS,
    M3A_AUTHORIZATION_COMMENT,
    M3A_AUTHORIZATION_STATUS,
    M3A_AUTHORIZING_MAINTAINER,
    M3A_LOCAL_SIGNATURE_ATTESTATION,
    M3A_PROTOCOL_AMENDMENT_ID,
    M3A_SIGNATURE_SEMANTICS,
    OUTPUT_ROOT_RELATIVE_PATH,
    PROPOSAL_RELATIVE_PATH,
    REPORT_BANNER,
    REPOSITORY_ROOT,
    Uci412Config,
)
from research.uci412.errors import (
    AuthorizationError,
    ProvenanceError,
    RuntimeGuardError,
    StorageProtectionError,
)
from research.uci412.feature_schema import DICTIONARY_SCHEMA_VERSION
from research.uci412.source_spec import (
    AUDITED_REFERENCE_SHA256,
    DATASET_ID,
    SOURCE_RELATIVE_PATH,
    TARGET_COLUMN,
)

M3A_AUTH_RELATIVE_PATH = PurePosixPath(
    "data/manifests/uci412_internal_research_authorization.local.json"
)
D046_AUTH_RELATIVE_PATH = PurePosixPath("data/manifests/gate_da_authorization.local.json")
PROVENANCE_RELATIVE_PATH = PurePosixPath("data/manifests/provenance_manifest.json")
FAILED_RUN_NOTES_RELATIVE_PATH = PurePosixPath("data/manifests/uci412_failed_runs.local.json")
SOURCE_PATH_RELATIVE = PurePosixPath(SOURCE_RELATIVE_PATH)
OUTPUT_ROOT_RELATIVE = PurePosixPath(OUTPUT_ROOT_RELATIVE_PATH)
PROPOSAL_PATH_RELATIVE = PurePosixPath(PROPOSAL_RELATIVE_PATH.as_posix())
DICTIONARY_PATH_RELATIVE = PurePosixPath("research/uci412/schemas/uci412_feature_dictionary.v1.json")
PLAN_PATH_RELATIVE = PurePosixPath("research/uci412/uci412_cad_research_plan.v0.1.json")

M3A_MANIFEST_SCHEMA_VERSION = "0.1.0"
M3A_PROPOSAL_ID = "M3A-UCI412-INTERNAL-RESEARCH-PROPOSAL"
UCI412_UCI_ID = 412
UCI412_DOI = "10.24432/C5Q31T"
UCI412_SOURCE_URL = "https://archive.ics.uci.edu/dataset/412/z+alizadeh+sani"
LICENSE_RELATIVE_PATH = PurePosixPath(
    "data/manifests/licenses/uci-412-license-snapshot.txt"
)
D046_AUTHORIZED_WORKFLOW_STATUS = "AUTHORIZED_FOR_LOCAL_READ_ONLY_AUDIT"
D046_DATASET_AUTHORIZED_STATUS = "AUTHORIZED_FOR_READ_ONLY_AUDIT"
D046_GATE_PT_CLOSED_STATUS = "CLOSED_REQUIRES_SUPERVISOR_SIGNOFF_P3"
EXPECTED_LICENSE_SPDX = "CC-BY-4.0"
M3A_ALLOWED_RUNTIME = "LOCAL_WINDOWS_CPU_ONLY"

GIT_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
SAFE_RUN_ID_RE = re.compile(r"^run-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}$")

GIT_PROTECTED_PROBES: tuple[str, ...] = (
    "data/",
    "data/raw/uci-412/Z-Alizadeh sani dataset.xlsx",
    "data/manifests/provenance_manifest.json",
    "data/manifests/gate_da_authorization.local.json",
    "data/manifests/uci412_internal_research_authorization.local.json",
    "data/manifests/licenses/uci-412-license-snapshot.txt",
    "data/uci412-experiments/",
    "data/uci412-experiments/.m3a-protection-probe",
)


@dataclass(frozen=True, slots=True)
class PreflightContext:
    """Sanitized result of a successful authorization/provenance preflight."""

    repo_root: Path
    source_path: Path
    source_sha256: str
    source_size_bytes: int
    provenance_sha256: str
    d046_authorization_sha256: str
    m3a_authorization_sha256: str
    license_sha256: str
    authorization: Mapping[str, Any]
    current_git_commit: str
    commit_committed_at_utc: str
    downloaded_at_utc: str
    download_timestamp_evidence_status: str
    provenance_recorded_at_utc: str


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args], cwd=str(repo_root), capture_output=True, text=True, check=False
        )
    except OSError as exc:
        raise StorageProtectionError("Git safety checks could not be executed.") from exc


def _git_bytes(repo_root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    """Read Git blob content as raw bytes so hashes never depend on the locale."""
    try:
        return subprocess.run(["git", *args], cwd=str(repo_root), capture_output=True, check=False)
    except OSError as exc:
        raise StorageProtectionError("Git binary content checks could not be executed.") from exc


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
    except Exception as exc:  # noqa: BLE001 - never echo file contents
        raise error_type(f"Protected {label} is malformed or unreadable.") from exc
    if not isinstance(value, dict):
        raise error_type(f"Protected {label} must contain one JSON object.")
    return value


def _parse_iso_timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip() or "REPLACE" in value.upper():
        raise AuthorizationError("A timezone-aware local human-signature timestamp is required.")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise AuthorizationError("The recorded timestamp is not a valid ISO-8601 value.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AuthorizationError("Timestamps must include an explicit timezone offset.")
    return parsed


def _safe_path(
    repo_root: Path,
    relative: PurePosixPath,
    *,
    error_type: type[Exception],
    label: str,
) -> Path:
    """Re-raise reused containment errors as this package's own safe error types."""
    try:
        return assert_no_symlink_components(repo_root, relative)
    except Exception as exc:  # noqa: BLE001 - reused guard, safe wrapper
        raise error_type(f"Protected {label} failed containment or symlink checks.") from exc


def current_commit_and_clean_tree(repo_root: Path) -> str:
    top_level = _git(repo_root, "rev-parse", "--show-toplevel")
    if top_level.returncode != 0 or os.path.normcase(
        os.path.abspath(top_level.stdout.strip())
    ) != os.path.normcase(os.path.abspath(repo_root)):
        raise StorageProtectionError("The runner is not executing from its exact Git repository root.")
    head = _git(repo_root, "rev-parse", "--verify", "HEAD^{commit}")
    commit = head.stdout.strip().lower()
    if head.returncode != 0 or not GIT_SHA_RE.fullmatch(commit):
        raise StorageProtectionError("A committed Git code version is required for a reproducible real run.")
    status = _git(repo_root, "status", "--porcelain", "--untracked-files=all")
    if status.returncode != 0 or status.stdout.strip():
        raise StorageProtectionError("The code worktree must be clean before real-data preflight/run.")
    return commit


def verify_git_protected_storage(repo_root: Path) -> None:
    """Require every protected data path to be ignored, untracked, and reparse-free."""
    try:
        verify_git_ignore(repo_root, GIT_PROTECTED_PROBES)
    except Exception as exc:  # noqa: BLE001 - re-raised with a safe message
        raise StorageProtectionError(
            "Git-ignore protection failed: all /data paths must be ignored and no file under /data "
            "may be tracked."
        ) from exc
    for relative in (
        "data",
        "data/raw",
        "data/raw/uci-412",
        "data/manifests",
        "data/manifests/licenses",
        OUTPUT_ROOT_RELATIVE_PATH,
    ):
        _safe_path(
            repo_root,
            PurePosixPath(relative),
            error_type=StorageProtectionError,
            label="data path",
        )


def verify_d046_da_a1_authorization(repo_root: Path) -> tuple[dict[str, Any], str]:
    """Validate the ratified D-046 read-only scope. It never authorizes fitting."""
    auth_path = _safe_path(repo_root, D046_AUTH_RELATIVE_PATH, error_type=AuthorizationError, label="D-046 manifest")
    try:
        auth = load_authorization_manifest(auth_path)
        da_a1 = verify_dataset_authorized_for_audit(
            auth, DATASET_ID, requested_usage_role="read_only_audit"
        )
    except Exception as exc:  # noqa: BLE001
        raise AuthorizationError(
            "The D-046 local read-only audit authorization for DA-A1 is missing or invalid; it "
            "cannot by itself authorize fitting."
        ) from exc
    if auth.get("workflow_status") != D046_AUTHORIZED_WORKFLOW_STATUS:
        raise AuthorizationError("D-046 is not recorded as authorized for local read-only audit.")
    if auth.get("supervisor_approval_claimed") is not False:
        raise AuthorizationError("D-046 must not claim supervisor approval.")
    if auth.get("gate_pt_status") != D046_GATE_PT_CLOSED_STATUS:
        raise AuthorizationError("Formal Gate PT P-3 must remain closed.")
    if da_a1.get("authorization_status") != D046_DATASET_AUTHORIZED_STATUS:
        raise AuthorizationError("D-046 DA-A1 is not explicitly authorized for local read-only audit.")
    if da_a1.get("training_authorized") is not False:
        raise AuthorizationError("D-046 read-only audit authorization must not enable model training.")
    sha, _ = sha256_file(auth_path)
    return auth, sha


def validate_m3a_authorization(
    manifest: Mapping[str, Any],
    *,
    repo_root: Path,
    current_git_commit: str,
    config: Uci412Config = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Validate the separate, hash-bound M3a local internal-research authorization."""
    if manifest.get("schema_version") != M3A_MANIFEST_SCHEMA_VERSION:
        raise AuthorizationError("Local M3a authorization manifest version is invalid.")
    if manifest.get("proposal_id") != M3A_PROPOSAL_ID:
        raise AuthorizationError("Local M3a authorization does not name the reviewed proposal.")
    if manifest.get("authorization_status") != M3A_AUTHORIZATION_STATUS:
        raise AuthorizationError(
            "The M3a local authorization is not complete; the checked-in template authorizes nothing."
        )
    if manifest.get("experiment_type") != REPORT_BANNER:
        raise AuthorizationError("Local M3a authorization has an unexpected experiment type.")
    if manifest.get("supervisor_signoff_claimed") is not False:
        raise AuthorizationError("Supervisor approval must remain unclaimed; Gate PT P-3 is closed.")
    if manifest.get("gate_pt_status") != D046_GATE_PT_CLOSED_STATUS:
        raise AuthorizationError("Gate PT P-3 must not be represented as approved.")
    if manifest.get("maintainer_approval_comment_exact") != M3A_AUTHORIZATION_COMMENT:
        raise AuthorizationError("The exact M3a maintainer authorization comment is not recorded locally.")
    pr_number = manifest.get("governance_pr_number")
    if type(pr_number) is not int or pr_number <= 0:
        raise AuthorizationError("A positive governance PR number is required.")
    merge_sha = manifest.get("governance_merge_commit_sha")
    pinned_sha = manifest.get("pinned_protocol_commit_sha")
    if not isinstance(merge_sha, str) or not GIT_SHA_RE.fullmatch(merge_sha):
        raise AuthorizationError("The governance merge commit SHA is missing or malformed.")
    if not isinstance(pinned_sha, str) or pinned_sha.lower() != merge_sha.lower():
        raise AuthorizationError("The pinned protocol commit must be the governance merge commit.")
    merge_sha = merge_sha.lower()

    if manifest.get("dataset_id") != DATASET_ID:
        raise AuthorizationError("Only DA-A1 (UCI-412) is in scope for this milestone.")
    if manifest.get("allowed_original_relative_file") != SOURCE_RELATIVE_PATH:
        raise AuthorizationError("The M3a authorization names an unapproved source file.")
    if manifest.get("authorized_source_row_count") != config.expected_row_count:
        raise AuthorizationError("The M3a authorization has an unexpected source row-count bound.")
    if manifest.get("panel_schema_id") != config.panel_id:
        raise AuthorizationError("The M3a authorization does not bind the registered primary panel.")
    if manifest.get("panel_schema_version") != config.panel_version:
        raise AuthorizationError("The M3a authorization binds a different panel version.")
    # Amendment A-1: a manifest must name the amended dictionary schema and the
    # amendment itself. A manifest written before the source-encoding correction
    # therefore fails closed on three independent checks rather than being
    # silently reusable.
    if manifest.get("dictionary_schema_version") != DICTIONARY_SCHEMA_VERSION:
        raise AuthorizationError(
            "The M3a authorization does not bind the amended feature-dictionary schema version."
        )
    if manifest.get("protocol_amendment_id") != M3A_PROTOCOL_AMENDMENT_ID:
        raise AuthorizationError(
            "The M3a authorization does not bind the reviewed protocol amendment."
        )
    if manifest.get("allowlisted_model_families") != list(ALLOWED_MODEL_FAMILIES):
        raise AuthorizationError("The M3a authorization model families do not match the registered list.")
    if manifest.get("allowed_operations_if_approved") != list(ALLOWED_OPERATIONS):
        raise AuthorizationError("The M3a authorization operations do not match the registered list.")
    if manifest.get("forbidden_operations") != list(FORBIDDEN_OPERATIONS):
        raise AuthorizationError("The M3a authorization omits or alters required forbidden operations.")
    if manifest.get("allowed_runtime") != M3A_ALLOWED_RUNTIME:
        raise AuthorizationError("The M3a authorization must be Windows-local and CPU-only.")
    if manifest.get("protected_outputs_relative_root") != OUTPUT_ROOT_RELATIVE_PATH:
        raise AuthorizationError("The M3a authorization names an unprotected output root.")
    if manifest.get("target_column") != TARGET_COLUMN:
        raise AuthorizationError("The M3a authorization must bind the reviewed target column.")

    signer = manifest.get("local_signer")
    if not isinstance(signer, str) or signer.strip() != M3A_AUTHORIZING_MAINTAINER:
        raise AuthorizationError("The named local signer must be the verified project maintainer.")
    signed_at = _parse_iso_timestamp(manifest.get("local_signed_at_iso8601"))
    if signed_at > datetime.now(timezone.utc):
        raise AuthorizationError("The local signature timestamp may not be in the future.")
    if manifest.get("local_signature_attestation") != M3A_LOCAL_SIGNATURE_ATTESTATION:
        raise AuthorizationError("The required local human signature attestation is missing or altered.")
    if manifest.get("signature_semantics") != M3A_SIGNATURE_SEMANTICS:
        raise AuthorizationError("Unexpected local signature semantics; no cryptographic signature is claimed.")

    expected_source_sha = manifest.get("expected_sha256_from_protected_provenance_manifest")
    if not isinstance(expected_source_sha, str) or not SHA256_RE.fullmatch(expected_source_sha):
        raise AuthorizationError("A full source SHA-256 from protected provenance is required.")
    frozen_plan = manifest.get("frozen_research_plan_sha256")
    frozen_dictionary = manifest.get("frozen_feature_dictionary_sha256")
    frozen_proposal = manifest.get("frozen_authorization_proposal_sha256")
    for value, label in (
        (frozen_plan, "research plan"),
        (frozen_dictionary, "feature dictionary"),
        (frozen_proposal, "authorization proposal"),
    ):
        if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
            raise AuthorizationError(f"A frozen {label} SHA-256 is required.")

    if manifest.get("authorization_proposal_relative_path") != PROPOSAL_PATH_RELATIVE.as_posix():
        raise AuthorizationError("The M3a authorization binds an unexpected proposal document path.")

    if not GIT_SHA_RE.fullmatch(current_git_commit):
        raise AuthorizationError("The local code commit is not a valid full Git commit SHA.")
    for commit_sha, label in ((merge_sha, "governance"), (pinned_sha.lower(), "protocol")):
        exists = _git(repo_root, "cat-file", "-e", f"{commit_sha}^{{commit}}")
        if exists.returncode != 0:
            raise AuthorizationError(f"The pinned {label} commit is not present in the local repository.")
        ancestor = _git(repo_root, "merge-base", "--is-ancestor", commit_sha, current_git_commit)
        if ancestor.returncode != 0:
            raise AuthorizationError(f"The pinned {label} commit is not an ancestor of the current commit.")

    committed = _git(repo_root, "show", "-s", "--format=%cI", merge_sha)
    if committed.returncode != 0 or not committed.stdout.strip():
        raise AuthorizationError("The governance merge commit timestamp could not be read.")
    try:
        merged_at = datetime.fromisoformat(committed.stdout.strip())
    except ValueError as exc:
        raise AuthorizationError("The governance merge timestamp is malformed.") from exc
    if signed_at < merged_at:
        raise AuthorizationError("The local M3a signature must post-date the governance merge.")

    proposal_path = _safe_path(
        repo_root, PROPOSAL_PATH_RELATIVE, error_type=AuthorizationError, label="authorization proposal"
    )
    plan_path = _safe_path(
        repo_root, PLAN_PATH_RELATIVE, error_type=AuthorizationError, label="research plan"
    )
    dictionary_path = _safe_path(
        repo_root, DICTIONARY_PATH_RELATIVE, error_type=AuthorizationError, label="feature dictionary"
    )
    try:
        actual_proposal_sha, _ = sha256_file(proposal_path)
        actual_plan_sha, _ = sha256_file(plan_path)
        actual_dictionary_sha, _ = sha256_file(dictionary_path)
    except Exception as exc:  # noqa: BLE001
        raise AuthorizationError("The proposal, plan, or feature dictionary could not be hashed safely.") from exc
    if actual_proposal_sha.lower() != frozen_proposal.lower():
        raise AuthorizationError("The authorization proposal differs from the human-frozen hash.")
    if actual_plan_sha.lower() != frozen_plan.lower():
        raise AuthorizationError("The registered research plan differs from the human-frozen hash.")
    if actual_dictionary_sha.lower() != frozen_dictionary.lower():
        raise AuthorizationError("The feature dictionary differs from the human-frozen hash.")

    pinned_proposal = _git_bytes(repo_root, "show", f"{merge_sha}:{PROPOSAL_PATH_RELATIVE.as_posix()}")
    if pinned_proposal.returncode != 0:
        raise AuthorizationError("The proposal document is absent from the pinned governance commit.")
    from research.uci412.adapter import sha256_bytes

    if sha256_bytes(pinned_proposal.stdout) != frozen_proposal.lower():
        raise AuthorizationError("The proposal at the pinned commit does not match its signed hash.")

    return {
        "local_signer": signer.strip(),
        "local_signed_at_iso8601": manifest["local_signed_at_iso8601"],
        "authorization_comment_exact": M3A_AUTHORIZATION_COMMENT,
        "governance_pr_number": pr_number,
        "governance_merge_commit_sha": merge_sha,
        "pinned_protocol_commit_sha": pinned_sha.lower(),
        "expected_source_sha256": expected_source_sha.lower(),
        "frozen_authorization_proposal_sha256": frozen_proposal.lower(),
        "frozen_feature_dictionary_sha256": frozen_dictionary.lower(),
        "frozen_research_plan_sha256": frozen_plan.lower(),
        "dictionary_schema_version": DICTIONARY_SCHEMA_VERSION,
        "protocol_amendment_id": M3A_PROTOCOL_AMENDMENT_ID,
        "signature_semantics": M3A_SIGNATURE_SEMANTICS,
    }


def _verify_da_a1_provenance(
    repo_root: Path,
    *,
    d046_authorization: dict[str, Any],
    expected_source_sha256: str,
) -> tuple[dict[str, Any], str, str, int]:
    provenance_path = _safe_path(repo_root, PROVENANCE_RELATIVE_PATH, error_type=ProvenanceError, label="provenance manifest")
    try:
        indexed = validate_provenance_manifest(
            provenance_path,
            base_root=repo_root,
            auth_manifest=d046_authorization,
            authorized_dataset_ids=[DATASET_ID],
        )
    except Exception as exc:  # noqa: BLE001 - safe wrapper
        raise ProvenanceError(
            "The protected DA-A1 provenance/license chain is missing, inconsistent, or hash-mismatched."
        ) from exc
    entry = indexed.get(DATASET_ID, {}).get(SOURCE_PATH_RELATIVE.name)
    if not isinstance(entry, dict):
        raise ProvenanceError("Protected provenance has no entry for the authorized UCI-412 workbook.")
    if entry.get("uci_id") != UCI412_UCI_ID or entry.get("doi") != UCI412_DOI:
        raise ProvenanceError("Protected provenance has an unexpected UCI ID or DOI for DA-A1.")
    if str(entry.get("official_source_url", "")).strip() != UCI412_SOURCE_URL:
        raise ProvenanceError("Protected provenance does not identify the canonical UCI-412 source URL.")
    if entry.get("license_spdx") != EXPECTED_LICENSE_SPDX:
        raise ProvenanceError("Protected UCI-412 license is not recorded as CC-BY-4.0.")
    if entry.get("relative_path") != SOURCE_RELATIVE_PATH:
        raise ProvenanceError("Protected provenance source path is not the exact approved UCI-412 file.")
    if Path(str(entry.get("resolved_license_path", ""))).name != LICENSE_RELATIVE_PATH.name:
        raise ProvenanceError("Protected provenance names an unexpected license snapshot.")
    verified_sha = str(entry.get("verified_sha256", "")).lower()
    if verified_sha != expected_source_sha256.lower():
        raise ProvenanceError("The M3a authorization hash does not match protected D-046 provenance.")
    if verified_sha != AUDITED_REFERENCE_SHA256:
        raise ProvenanceError(
            "The local workbook bytes differ from the previously audited DA-A1 reference hash; a new "
            "audit and authorization are required before any fitting."
        )
    size = entry.get("verified_size_bytes")
    if type(size) is not int or size <= 0:
        raise ProvenanceError("Protected provenance has no valid byte size for the UCI-412 workbook.")
    provenance_sha, _ = sha256_file(provenance_path)
    license_sha, _ = sha256_file(Path(entry["resolved_license_path"]))
    return entry, provenance_sha, license_sha, size


def run_preflight(
    *,
    repo_root: Path = REPOSITORY_ROOT,
    config: Uci412Config = DEFAULT_CONFIG,
) -> PreflightContext:
    """Validate every local gate and hash without parsing workbook rows or fitting."""
    input_root = Path(repo_root).expanduser()
    root = input_root.resolve(strict=True)
    try:
        enforce_local_windows_runtime(repo_root=root)
    except Exception as exc:  # noqa: BLE001 - reused guard, safe wrapper
        raise RuntimeGuardError(
            "Real-data preflight/run is Windows-local only; no source rows were parsed."
        ) from exc
    verify_git_protected_storage(root)
    current_commit = current_commit_and_clean_tree(root)
    committed_at = _git(root, "show", "-s", "--format=%cI", current_commit)
    if committed_at.returncode != 0 or not committed_at.stdout.strip():
        raise StorageProtectionError("The current commit timestamp could not be read.")

    m3a_path = _safe_path(root, M3A_AUTH_RELATIVE_PATH, error_type=AuthorizationError, label="M3a manifest")
    m3a_manifest = _read_json_no_duplicate_keys(
        m3a_path, error_type=AuthorizationError, label="M3a local authorization manifest"
    )
    authorization = validate_m3a_authorization(
        m3a_manifest, repo_root=root, current_git_commit=current_commit, config=config
    )
    m3a_sha, _ = sha256_file(m3a_path)
    authorization = dict(authorization, local_manifest_sha256=m3a_sha)

    d046_auth, d046_sha = verify_d046_da_a1_authorization(root)
    entry, provenance_sha, license_sha, expected_size = _verify_da_a1_provenance(
        root,
        d046_authorization=d046_auth,
        expected_source_sha256=authorization["expected_source_sha256"],
    )

    source_path = _safe_path(root, SOURCE_PATH_RELATIVE, error_type=ProvenanceError, label="UCI-412 source")
    if source_path.name != SOURCE_PATH_RELATIVE.name:
        raise StorageProtectionError("Only the registered UCI-412 workbook may be opened by the runner.")
    try:
        source_sha, source_size = sha256_file(source_path)
    except Exception as exc:  # noqa: BLE001
        raise ProvenanceError("The protected UCI-412 workbook is missing or unreadable.") from exc
    if source_sha.lower() != authorization["expected_source_sha256"]:
        raise ProvenanceError("The local source SHA-256 does not match the signed M3a hash binding.")
    if source_sha.lower() != str(entry.get("sha256", "")).lower() or source_size != expected_size:
        raise ProvenanceError("The local source bytes do not match protected D-046 provenance.")

    return PreflightContext(
        repo_root=root,
        source_path=source_path,
        source_sha256=source_sha,
        source_size_bytes=source_size,
        provenance_sha256=provenance_sha,
        d046_authorization_sha256=d046_sha,
        m3a_authorization_sha256=m3a_sha,
        license_sha256=license_sha,
        authorization=authorization,
        current_git_commit=current_commit,
        commit_committed_at_utc=committed_at.stdout.strip(),
        downloaded_at_utc=str(entry.get("downloaded_at_utc")),
        download_timestamp_evidence_status=(
            "UNVERIFIED"
            if entry.get("downloaded_at_utc") == "UNKNOWN_PENDING_HUMAN_VERIFICATION"
            else "SOURCE-REPORTED"
        ),
        provenance_recorded_at_utc=str(entry.get("manifest_recorded_at_utc")),
    )


def load_failed_run_notes(repo_root: Path) -> tuple[str, ...]:
    """Load the optional operator-maintained failed-run notes for the next report.

    The file is local, Git-ignored, and read-only for the harness. It may contain
    only short operator notes about why a previous run stopped; patient-level
    content is never accepted, and a malformed file fails closed.
    """
    path = Path(repo_root) / Path(*FAILED_RUN_NOTES_RELATIVE_PATH.parts)
    if not path.exists():
        return ()
    if path.is_symlink() or not path.is_file():
        raise StorageProtectionError("The failed-run notes file must be a regular local file.")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - never echo file contents
        raise StorageProtectionError("The failed-run notes file is malformed or unreadable.") from exc
    if not isinstance(payload, list) or len(payload) > 50:
        raise StorageProtectionError("Failed-run notes must be a JSON list of at most 50 short notes.")
    notes: list[str] = []
    for item in payload:
        if not isinstance(item, str):
            raise StorageProtectionError("Every failed-run note must be a JSON string.")
        note = item.strip()
        if not note or len(note) > 200 or "REPLACE" in note.upper():
            raise StorageProtectionError("A failed-run note is empty, too long, or a placeholder.")
        if any(character in note for character in ("\n", "\r", "\t")):
            raise StorageProtectionError("Failed-run notes must be single-line strings.")
        notes.append(note)
    return tuple(notes)


def verify_source_still_unchanged(context: PreflightContext) -> None:
    """Re-hash the original source without parsing or mutating it."""
    try:
        current_sha, current_size = sha256_file(context.source_path)
    except Exception as exc:  # noqa: BLE001
        raise ProvenanceError("The original source became missing or unreadable during the run.") from exc
    if current_sha.lower() != context.source_sha256.lower() or current_size != context.source_size_bytes:
        raise ProvenanceError("Original source byte-identity check failed; no report may be accepted.")


def create_protected_run_directory(*, repo_root: Path, run_id: str) -> Path:
    """Create a unique, Git-ignored local output directory; no arbitrary path is accepted."""
    if not SAFE_RUN_ID_RE.fullmatch(run_id):
        raise StorageProtectionError("Run ID is not in the fixed safe format.")
    root = Path(repo_root).resolve(strict=True)
    verify_git_protected_storage(root)
    output_root = _safe_path(root, OUTPUT_ROOT_RELATIVE, error_type=StorageProtectionError, label="output root")
    try:
        output_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        output_root = _safe_path(root, OUTPUT_ROOT_RELATIVE, error_type=StorageProtectionError, label="output root")
        try:
            os.chmod(output_root, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        except OSError:
            pass  # NTFS ACLs are inherited; the handoff requires the human to secure them.
        run_dir_rel = OUTPUT_ROOT_RELATIVE / run_id
        run_dir = _safe_path(root, run_dir_rel, error_type=StorageProtectionError, label="run directory")
        run_dir.mkdir(mode=0o700, exist_ok=False)
        resolved = run_dir.resolve(strict=True)
        expected = (root / Path(*run_dir_rel.parts)).resolve(strict=True)
        if os.path.normcase(str(resolved)) != os.path.normcase(str(expected)):
            raise StorageProtectionError("Experiment output escaped its protected local root.")
        try:
            os.chmod(run_dir, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        except OSError:
            pass
        verify_git_protected_storage(root)
        return run_dir
    except FileExistsError as exc:
        raise StorageProtectionError(
            "The generated experiment output directory already exists; refusing overwrite."
        ) from exc
    except StorageProtectionError:
        raise
    except OSError as exc:
        raise StorageProtectionError(
            "Unable to create a protected local experiment output directory."
        ) from exc


def authorization_template_is_non_authorizing(path: Path | None = None) -> bool:
    """Return True when the checked-in template really cannot authorize a run."""
    template_path = AUTHORIZATION_TEMPLATE_PATH if path is None else Path(path)
    try:
        template = json.loads(template_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return False
    return (
        template.get("authorization_status") != M3A_AUTHORIZATION_STATUS
        and template.get("supervisor_signoff_claimed") is False
        and template.get("gate_pt_status") == D046_GATE_PT_CLOSED_STATUS
        and template.get("dataset_id") == DATASET_ID
        and template.get("allowed_original_relative_file") == SOURCE_RELATIVE_PATH
    )
