"""Governance authorization checks, provenance/license verification, archive inspection, and byte-identity guards."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any, Sequence
from urllib.parse import urlparse
import zipfile

from research.audit.exceptions import (
    ArchiveSecurityError,
    FormatValidationError,
    GovernanceAuthorizationError,
    ProvenanceVerificationError,
)
from research.audit.registry import (
    DATASET_AUTHORIZED_STATUS,
    EVIDENCE_SOURCE_REPORTED,
    EVIDENCE_UNVERIFIED,
    FORBIDDEN_SOURCE_HOSTS_SUBSTRINGS,
    GLOBAL_AUTHORIZED_WORKFLOW_STATUS,
    LOCAL_INTEGRITY_VERIFIED_STATUS,
    OFFICIAL_UCI_HOST,
    PENDING_HUMAN_ACCEPTANCE_STATUS,
    SOURCE_ORIGIN_HUMAN_ATTESTED_STATUS,
    UCI_45_UNAPPROVED_FILES,
    UCI_ARCHIVE_HARMLESS_METADATA_ALLOWLIST,
    UNKNOWN_DOWNLOAD_TIMESTAMP,
)

AUTHORIZED_STATUS_VALUE = DATASET_AUTHORIZED_STATUS
PENDING_STATUS_VALUE = PENDING_HUMAN_ACCEPTANCE_STATUS
ISO_UTC_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
APPROVED_LICENSE_DIR_POSIX = PurePosixPath("data/manifests/licenses")


def sha256_file(path: Path) -> tuple[str, int]:
    """Compute SHA-256 hex digest and exact byte size of a file in read-only mode."""
    if not path.exists() or not path.is_file():
        raise FormatValidationError(f"Required file does not exist: '{path}'")
    digest = hashlib.sha256()
    total_bytes = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(65536)
            if not chunk:
                break
            digest.update(chunk)
            total_bytes += len(chunk)
    return digest.hexdigest(), total_bytes


def _validate_safe_relative_posix_path(raw_path: str, *, field_name: str) -> PurePosixPath:
    """Validate that a manifest path is strictly relative and contains no traversal or drive prefixes."""
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ProvenanceVerificationError(f"Missing or empty path in '{field_name}'.")
    if "\x00" in raw_path:
        raise ProvenanceVerificationError(f"Null byte prohibited in '{field_name}'.")

    stripped = raw_path.strip()
    if (
        stripped.startswith("/")
        or stripped.startswith("\\")
        or stripped.startswith("~")
        or ":" in stripped
        or Path(stripped).is_absolute()
    ):
        raise ProvenanceVerificationError(
            f"Absolute or drive-prefixed path is prohibited in '{field_name}': '{raw_path}'."
        )

    normalized = stripped.replace("\\", "/")
    raw_segments = normalized.split("/")
    for seg in raw_segments:
        if seg in ("", ".", ".."):
            raise ProvenanceVerificationError(
                f"Path traversal or empty/dot segment is prohibited in '{field_name}': '{raw_path}'."
            )

    posix_path = PurePosixPath(normalized)
    if posix_path.is_absolute() or ".." in posix_path.parts or "." in posix_path.parts:
        raise ProvenanceVerificationError(
            f"Unsafe relative path in '{field_name}': '{raw_path}'."
        )
    return posix_path


def _verify_no_symlinks_under_base(
    base_root: Path,
    rel_posix: PurePosixPath,
    *,
    field_name: str,
) -> Path:
    """Walk every path prefix under base_root and reject any symlink component."""
    if base_root.is_symlink():
        raise ProvenanceVerificationError(
            f"Base root '{base_root}' is a symlink; refusing path resolution for '{field_name}'."
        )
    current = base_root
    for part in rel_posix.parts:
        current = current / part
        if current.is_symlink():
            raise ProvenanceVerificationError(
                f"Symlink detected at '{current}' while resolving '{field_name}' ('{rel_posix}'). "
                "Symlinks escaping or redirecting authorized data directories are prohibited."
            )
    return current


def _verify_existing_contained_directory(
    base_root: Path,
    expected_dir_posix: PurePosixPath,
    *,
    context_label: str,
) -> Path:
    """Ensure an authorized directory exists under base_root, has no symlinks, and resolves in place."""
    unres_dir = _verify_no_symlinks_under_base(base_root, expected_dir_posix, field_name=context_label)
    if not unres_dir.exists() or not unres_dir.is_dir():
        raise ProvenanceVerificationError(
            f"Authorized directory '{expected_dir_posix}' ({context_label}) does not exist at '{unres_dir}'. "
            "Failing closed."
        )
    resolved_base = base_root.resolve()
    resolved_dir = unres_dir.resolve()
    if resolved_base not in resolved_dir.parents:
        raise ProvenanceVerificationError(
            f"Authorized directory '{expected_dir_posix}' resolves outside base root '{resolved_base}'."
        )
    expected_resolved = (resolved_base / Path(*expected_dir_posix.parts)).resolve()
    if resolved_dir != expected_resolved:
        raise ProvenanceVerificationError(
            f"Authorized directory '{expected_dir_posix}' resolved to unexpected path '{resolved_dir}' "
            f"(expected '{expected_resolved}')."
        )
    return resolved_dir


def _verify_contained_file_in_directory(
    base_root: Path,
    raw_rel_path: str,
    *,
    expected_dir_posix: PurePosixPath,
    expected_filename: str,
    field_name: str,
) -> Path:
    """Ensure a manifest file path resolves directly inside expected_dir_posix with exact filename and no symlinks."""
    rel_posix = _validate_safe_relative_posix_path(raw_rel_path, field_name=field_name)
    resolved_expected_dir = _verify_existing_contained_directory(
        base_root,
        expected_dir_posix,
        context_label=f"{field_name} parent directory",
    )

    if rel_posix.name != expected_filename:
        raise ProvenanceVerificationError(
            f"Path '{raw_rel_path}' in '{field_name}' does not match expected filename '{expected_filename}'."
        )
    if rel_posix.parent != expected_dir_posix:
        raise ProvenanceVerificationError(
            f"Path '{raw_rel_path}' in '{field_name}' is not inside the required authorized directory "
            f"'{expected_dir_posix}' (got parent '{rel_posix.parent}')."
        )

    unres_file = _verify_no_symlinks_under_base(base_root, rel_posix, field_name=field_name)
    if not unres_file.exists() or not unres_file.is_file():
        raise ProvenanceVerificationError(
            f"File '{raw_rel_path}' in '{field_name}' does not exist at '{unres_file}'."
        )

    resolved_file = unres_file.resolve()
    if resolved_file.parent != resolved_expected_dir or resolved_file.name != expected_filename:
        raise ProvenanceVerificationError(
            f"Resolved file path '{resolved_file}' for '{field_name}' escapes authorized directory "
            f"'{resolved_expected_dir}'."
        )
    return resolved_file


def _validate_iso_utc_timestamp(value: str, *, field_name: str, allow_unknown: bool = False) -> str:
    """Validate an ISO-8601 UTC timestamp (or UNKNOWN_PENDING_HUMAN_VERIFICATION when allowed)."""
    if not isinstance(value, str) or not value.strip():
        raise ProvenanceVerificationError(f"Missing or empty timestamp in '{field_name}'.")
    cleaned = value.strip()
    if allow_unknown and cleaned == UNKNOWN_DOWNLOAD_TIMESTAMP:
        return cleaned
    if "YYYY" in cleaned.upper() or not ISO_UTC_TIMESTAMP_RE.match(cleaned):
        allowed_msg = (
            f"ISO-8601 UTC timestamp ('YYYY-MM-DDTHH:MM:SSZ') or '{UNKNOWN_DOWNLOAD_TIMESTAMP}'"
            if allow_unknown
            else "ISO-8601 UTC timestamp ('YYYY-MM-DDTHH:MM:SSZ')"
        )
        raise ProvenanceVerificationError(
            f"Invalid timestamp '{value}' in '{field_name}'; expected {allowed_msg}."
        )
    return cleaned


@dataclass(frozen=True)
class FileHashSnapshot:
    """Pre- and post-audit byte-identity record for a single dataset file."""

    filename: str
    relative_path: str
    pre_sha256: str
    post_sha256: str
    size_bytes: int
    byte_identical: bool


class ByteIdentityGuard:
    """Context manager ensuring dataset files remain strictly byte-identical on both success and failure paths."""

    def __init__(self, files: Sequence[tuple[str, Path, str | None, int | None]]) -> None:
        self._files = list(files)
        self._pre_hashes: dict[Path, tuple[str, int]] = {}
        self.snapshots: list[FileHashSnapshot] = []

    def __enter__(self) -> "ByteIdentityGuard":
        for rel_label, path, expected_sha, expected_size in self._files:
            actual_sha, actual_size = sha256_file(path)
            if actual_size <= 0:
                raise FormatValidationError(f"File '{rel_label}' is empty (0 bytes).")
            if expected_sha is not None and actual_sha.lower() != expected_sha.lower():
                raise ProvenanceVerificationError(
                    f"SHA-256 mismatch for '{rel_label}': expected {expected_sha}, got {actual_sha}."
                )
            if expected_size is not None and actual_size != expected_size:
                raise ProvenanceVerificationError(
                    f"File size mismatch for '{rel_label}': expected {expected_size} bytes, got {actual_size} bytes."
                )
            self._pre_hashes[path] = (actual_sha, actual_size)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        mutation_messages: list[str] = []
        for rel_label, path, _, _ in self._files:
            pre_sha, pre_size = self._pre_hashes[path]
            try:
                post_sha, post_size = sha256_file(path)
            except Exception as hash_exc:
                self.snapshots.append(
                    FileHashSnapshot(
                        filename=path.name,
                        relative_path=rel_label,
                        pre_sha256=pre_sha,
                        post_sha256="MISSING_OR_UNREADABLE",
                        size_bytes=0,
                        byte_identical=False,
                    )
                )
                mutation_messages.append(
                    f"BYTE-IDENTITY VIOLATION on '{rel_label}': file became missing or unreadable during audit ({hash_exc})!"
                )
                continue

            identical = (pre_sha == post_sha) and (pre_size == post_size)
            self.snapshots.append(
                FileHashSnapshot(
                    filename=path.name,
                    relative_path=rel_label,
                    pre_sha256=pre_sha,
                    post_sha256=post_sha,
                    size_bytes=post_size,
                    byte_identical=identical,
                )
            )
            if not identical:
                mutation_messages.append(
                    f"BYTE-IDENTITY VIOLATION on '{rel_label}': file changed during read-only audit "
                    f"(pre_sha256={pre_sha[:12]}..., post_sha256={post_sha[:12]}..., "
                    f"pre_size={pre_size}, post_size={post_size})!"
                )

        if mutation_messages:
            joined = " ".join(mutation_messages)
            if exc_val is not None:
                err = ProvenanceVerificationError(
                    f"{joined} (detected on failure path after {type(exc_val).__name__}: {exc_val})"
                )
                err.original_exception = exc_val  # type: ignore[attr-defined]
                raise err from exc_val
            raise ProvenanceVerificationError(joined)

        return False


def load_authorization_manifest(path: Path) -> dict[str, Any]:
    """Load and validate the structure and standing constraints of gate_da_authorization.json."""
    if not path.exists() or not path.is_file():
        raise GovernanceAuthorizationError(f"Authorization manifest missing at '{path}'.")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise GovernanceAuthorizationError(f"Malformed JSON in authorization manifest '{path}': {exc}") from exc

    if not isinstance(data, dict):
        raise GovernanceAuthorizationError("Authorization manifest root must be a JSON object.")

    if data.get("governance_decision_id") != "D-046":
        raise GovernanceAuthorizationError(
            f"Unexpected governance_decision_id '{data.get('governance_decision_id')}'; expected 'D-046'."
        )
    if data.get("supervisor_approval_claimed") is not False:
        raise GovernanceAuthorizationError(
            "Governance violation: supervisor_approval_claimed must be false (supervisor review is deferred, never fabricated)."
        )
    for forbidden_flag in (
        "model_fitting_authorized",
        "feature_selection_authorized",
        "hyperparameter_tuning_authorized",
        "performance_evaluation_authorized",
        "calibration_authorized",
        "shap_or_lime_authorized",
    ):
        if data.get(forbidden_flag) is not False:
            raise GovernanceAuthorizationError(
                f"Governance violation: '{forbidden_flag}' must be false in Gate DA authorization."
            )

    datasets = data.get("datasets")
    if not isinstance(datasets, dict) or set(datasets.keys()) != {"DA-A1", "DA-A2", "DA-B1", "DA-B2"}:
        raise GovernanceAuthorizationError(
            "Authorization manifest must define exact dataset entries for DA-A1, DA-A2, DA-B1, and DA-B2."
        )

    for ds_id, ds_cfg in datasets.items():
        if not isinstance(ds_cfg, dict):
            raise GovernanceAuthorizationError(f"Dataset entry '{ds_id}' must be a JSON object.")
        if ds_cfg.get("training_authorized") is not False or ds_cfg.get("external_validation_authorized") is not False:
            raise GovernanceAuthorizationError(
                f"Dataset '{ds_id}' cannot authorize model training or external validation in Gate DA."
            )
        if ds_id in ("DA-B1", "DA-B2"):
            if ds_cfg.get("never_training_or_external_validation_by_audit_grant") is not True:
                raise GovernanceAuthorizationError(
                    f"Dataset '{ds_id}' must enforce never_training_or_external_validation_by_audit_grant=true."
                )
            if ds_cfg.get("never_independent_cohort") is not True:
                raise GovernanceAuthorizationError(
                    f"Dataset '{ds_id}' must enforce never_independent_cohort=true."
                )
    return data


def verify_global_workflow_authorized(auth_manifest: dict[str, Any]) -> None:
    """Require global workflow_status to be AUTHORIZED_FOR_LOCAL_READ_ONLY_AUDIT."""
    workflow_status = auth_manifest.get("workflow_status")
    if workflow_status != GLOBAL_AUTHORIZED_WORKFLOW_STATUS:
        raise GovernanceAuthorizationError(
            f"Global Gate DA workflow_status is '{workflow_status}' "
            f"(required: '{GLOBAL_AUTHORIZED_WORKFLOW_STATUS}'). "
            "No local dataset audit or provenance recording may proceed until the human maintainer "
            "explicitly accepts D-046 and updates workflow_status."
        )


def verify_dataset_authorized_for_audit(
    auth_manifest: dict[str, Any],
    dataset_id: str,
    *,
    requested_usage_role: str = "read_only_audit",
) -> dict[str, Any]:
    """Verify global workflow_status AND dataset-level Gate DA authorization and required D-046 metadata."""
    datasets = auth_manifest.get("datasets", {})
    if dataset_id not in datasets:
        raise GovernanceAuthorizationError(
            f"Dataset '{dataset_id}' is not in the Gate DA scope (only DA-A1, DA-A2, DA-B1, DA-B2 exist)."
        )

    if requested_usage_role != "read_only_audit":
        raise GovernanceAuthorizationError(
            f"Usage role '{requested_usage_role}' is prohibited for '{dataset_id}'. "
            "Gate DA permits read-only dataset audit only; training and external validation are forbidden."
        )

    # Enforce global Gate DA workflow_status before dataset-level status
    verify_global_workflow_authorized(auth_manifest)

    ds_cfg = datasets[dataset_id]
    status = ds_cfg.get("authorization_status")
    if status != AUTHORIZED_STATUS_VALUE:
        raise GovernanceAuthorizationError(
            f"Dataset '{dataset_id}' ({ds_cfg.get('title')}) is NOT authorized for local audit "
            f"(current status: '{status}'; required: '{AUTHORIZED_STATUS_VALUE}'). "
            "Human maintainer review and explicit sign-off are required before data acquisition or audit."
        )

    required_fields = (
        "authorized_by",
        "authorized_date",
        "responsible_acquirer",
        "audit_reviewer",
        "environment",
        "purpose",
    )
    for field_name in required_fields:
        val = ds_cfg.get(field_name)
        if not isinstance(val, str) or not val.strip() or "REPLACE" in val.upper():
            raise GovernanceAuthorizationError(
                f"Dataset '{dataset_id}' is marked '{AUTHORIZED_STATUS_VALUE}' but required D-046 sign-off "
                f"field '{field_name}' is missing or placeholder."
            )

    return ds_cfg


def validate_official_source_url(url: str, expected_url: str, dataset_id: str) -> None:
    """Fail closed if a source URL is not an official HTTPS UCI URL or points to a mirror/Kaggle."""
    if not isinstance(url, str) or not url.strip():
        raise ProvenanceVerificationError(f"Missing official_source_url for '{dataset_id}'.")

    lowered = url.strip().lower()
    for forbidden in FORBIDDEN_SOURCE_HOSTS_SUBSTRINGS:
        if forbidden in lowered:
            raise ProvenanceVerificationError(
                f"Unapproved source URL '{url}' for '{dataset_id}': mirror/third-party host '{forbidden}' is prohibited."
            )

    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or parsed.netloc.lower() != OFFICIAL_UCI_HOST:
        raise ProvenanceVerificationError(
            f"Unapproved source URL '{url}' for '{dataset_id}': must use https://{OFFICIAL_UCI_HOST}/..."
        )

    if url.strip().rstrip("/") != expected_url.strip().rstrip("/"):
        raise ProvenanceVerificationError(
            f"Source URL '{url}' for '{dataset_id}' does not match canonical official URL '{expected_url}'."
        )


def _expected_dataset_dir_posix(ds_id: str, ds_spec: dict[str, Any]) -> PurePosixPath:
    """Return and validate the canonical local_subdir ('data/raw/uci-<id>') for a dataset."""
    uci_id = int(ds_spec["uci_id"])
    canonical_posix = PurePosixPath(f"data/raw/uci-{uci_id}")
    configured_posix = _validate_safe_relative_posix_path(
        str(ds_spec.get("local_subdir", "")),
        field_name=f"{ds_id}.local_subdir",
    )
    if configured_posix != canonical_posix:
        raise ProvenanceVerificationError(
            f"Dataset '{ds_id}' local_subdir '{configured_posix}' does not match canonical authorized "
            f"directory '{canonical_posix}'."
        )
    return canonical_posix


def validate_provenance_manifest(
    manifest_path: Path,
    base_root: Path,
    auth_manifest: dict[str, Any],
    authorized_dataset_ids: Sequence[str],
) -> dict[str, dict[str, Any]]:
    """Validate provenance_manifest.json, strict path containment, license snapshots, sizes, and SHA-256 hashes."""
    verify_global_workflow_authorized(auth_manifest)
    for ds_id in authorized_dataset_ids:
        verify_dataset_authorized_for_audit(auth_manifest, ds_id)

    if not manifest_path.exists() or not manifest_path.is_file():
        raise ProvenanceVerificationError(
            f"Provenance manifest not found at '{manifest_path}'. "
            "Record download provenance, license snapshots, and SHA-256 hashes before running the audit."
        )
    if manifest_path.is_symlink():
        raise ProvenanceVerificationError(
            f"Provenance manifest path '{manifest_path}' must not be a symlink."
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ProvenanceVerificationError(f"Invalid JSON in provenance manifest '{manifest_path}': {exc}") from exc

    if not isinstance(manifest, dict):
        raise ProvenanceVerificationError("Provenance manifest root must be a JSON object.")

    acquirer = manifest.get("acquirer")
    if not isinstance(acquirer, str) or not acquirer.strip() or "REPLACE" in acquirer.upper():
        raise ProvenanceVerificationError("Provenance manifest must name a valid human 'acquirer'.")

    manifest_recorded_at = _validate_iso_utc_timestamp(
        str(manifest.get("manifest_recorded_at_utc", "")),
        field_name="manifest_recorded_at_utc",
        allow_unknown=False,
    )

    # Ensure each target dataset's authorized local_subdir exists and is contained before inspecting files
    resolved_ds_dirs: dict[str, Path] = {}
    for ds_id in authorized_dataset_ids:
        ds_spec = auth_manifest["datasets"][ds_id]
        expected_dir_posix = _expected_dataset_dir_posix(ds_id, ds_spec)
        resolved_ds_dirs[ds_id] = _verify_existing_contained_directory(
            base_root,
            expected_dir_posix,
            context_label=f"{ds_id} authorized directory",
        )

    # Ensure approved license snapshot directory exists and is contained
    _verify_existing_contained_directory(
        base_root,
        APPROVED_LICENSE_DIR_POSIX,
        context_label="approved license snapshot directory",
    )

    files_list = manifest.get("files")
    if not isinstance(files_list, list) or not files_list:
        raise ProvenanceVerificationError("Provenance manifest must contain a non-empty 'files' array.")

    indexed_by_ds: dict[str, dict[str, dict[str, Any]]] = {ds_id: {} for ds_id in authorized_dataset_ids}

    for entry in files_list:
        if not isinstance(entry, dict):
            raise ProvenanceVerificationError("Each entry in provenance manifest 'files' must be a JSON object.")
        ds_id = str(entry.get("dataset_id", ""))
        if ds_id not in auth_manifest["datasets"]:
            raise ProvenanceVerificationError(f"Provenance manifest references unknown dataset_id '{ds_id}'.")

        verify_dataset_authorized_for_audit(auth_manifest, ds_id)

        if ds_id not in indexed_by_ds:
            continue

        ds_spec = auth_manifest["datasets"][ds_id]
        expected_dir_posix = _expected_dataset_dir_posix(ds_id, ds_spec)

        validate_official_source_url(
            str(entry.get("official_source_url", "")),
            str(ds_spec["official_source_url"]),
            ds_id,
        )

        if str(entry.get("doi", "")).strip() != str(ds_spec["doi"]).strip():
            raise ProvenanceVerificationError(
                f"DOI mismatch for '{ds_id}': expected '{ds_spec['doi']}', got '{entry.get('doi')}'."
            )
        if int(entry.get("uci_id", -1)) != int(ds_spec["uci_id"]):
            raise ProvenanceVerificationError(
                f"UCI ID mismatch for '{ds_id}': expected {ds_spec['uci_id']}, got {entry.get('uci_id')}."
            )
        if str(entry.get("license_spdx", "")).strip() != "CC-BY-4.0":
            raise ProvenanceVerificationError(
                f"License mismatch for '{ds_id}': expected 'CC-BY-4.0', got '{entry.get('license_spdx')}'."
            )

        downloaded_at_utc = _validate_iso_utc_timestamp(
            str(entry.get("downloaded_at_utc", "")),
            field_name=f"{ds_id}.downloaded_at_utc",
            allow_unknown=True,
        )
        entry_recorded_at_utc = _validate_iso_utc_timestamp(
            str(entry.get("manifest_recorded_at_utc", "")),
            field_name=f"{ds_id}.manifest_recorded_at_utc",
            allow_unknown=False,
        )

        # Enforce honest distinction between locally verified file integrity and human-attested source provenance
        local_integrity_status = str(entry.get("local_file_integrity_status", LOCAL_INTEGRITY_VERIFIED_STATUS)).strip()
        if local_integrity_status != LOCAL_INTEGRITY_VERIFIED_STATUS:
            raise ProvenanceVerificationError(
                f"Invalid local_file_integrity_status '{local_integrity_status}' for '{ds_id}'; "
                f"expected '{LOCAL_INTEGRITY_VERIFIED_STATUS}'."
            )
        source_origin_status = str(
            entry.get("official_source_provenance_status", SOURCE_ORIGIN_HUMAN_ATTESTED_STATUS)
        ).strip()
        if source_origin_status != SOURCE_ORIGIN_HUMAN_ATTESTED_STATUS:
            raise ProvenanceVerificationError(
                f"Invalid official_source_provenance_status '{source_origin_status}' for '{ds_id}'. "
                "A human-entered source URL and locally computed SHA-256 must be marked "
                f"'{SOURCE_ORIGIN_HUMAN_ATTESTED_STATUS}', never claimed as independent proof of upstream origin."
            )

        filename = str(entry.get("filename", "")).strip()
        allowed_files = set(ds_spec.get("authorized_files", [])) | set(ds_spec.get("optional_documentation_files", []))
        excluded_files = set(ds_spec.get("excluded_unapproved_files", [])) | set(UCI_45_UNAPPROVED_FILES)
        if filename in excluded_files:
            raise ProvenanceVerificationError(
                f"File '{filename}' in '{ds_id}' is explicitly unapproved / excluded by Gate DA."
            )
        if filename not in allowed_files:
            raise ProvenanceVerificationError(
                f"File '{filename}' is not in the authorized file list for '{ds_id}': {sorted(allowed_files)}."
            )
        if filename in indexed_by_ds[ds_id]:
            raise ProvenanceVerificationError(
                f"Duplicate provenance manifest entry for file '{filename}' in '{ds_id}'."
            )

        rel_path_str = str(entry.get("relative_path", ""))
        file_path = _verify_contained_file_in_directory(
            base_root,
            rel_path_str,
            expected_dir_posix=expected_dir_posix,
            expected_filename=filename,
            field_name=f"{ds_id}:{filename}.relative_path",
        )

        expected_lic_filename = f"uci-{ds_spec['uci_id']}-license-snapshot.txt"
        lic_rel_str = str(entry.get("license_snapshot_path", ""))
        lic_path = _verify_contained_file_in_directory(
            base_root,
            lic_rel_str,
            expected_dir_posix=APPROVED_LICENSE_DIR_POSIX,
            expected_filename=expected_lic_filename,
            field_name=f"{ds_id}:{filename}.license_snapshot_path",
        )

        lic_sha, lic_size = sha256_file(lic_path)
        expected_lic_sha = str(entry.get("license_snapshot_sha256", "")).strip()
        if not expected_lic_sha or lic_sha.lower() != expected_lic_sha.lower():
            raise ProvenanceVerificationError(
                f"License snapshot SHA-256 mismatch for '{lic_rel_str}': expected '{expected_lic_sha}', got '{lic_sha}'."
            )
        lic_text = lic_path.read_text(encoding="utf-8", errors="strict")
        if ("cc by 4.0" not in lic_text.lower()) and ("creative commons attribution 4.0" not in lic_text.lower()):
            raise ProvenanceVerificationError(
                f"License snapshot '{lic_rel_str}' does not contain verified 'CC BY 4.0' / "
                "'Creative Commons Attribution 4.0' license statement."
            )

        expected_sha = str(entry.get("sha256", "")).strip()
        expected_size = entry.get("size_bytes")
        if len(expected_sha) != 64 or not isinstance(expected_size, int) or expected_size <= 0:
            raise ProvenanceVerificationError(
                f"Invalid sha256 or size_bytes in provenance manifest for '{filename}'."
            )
        actual_sha, actual_size = sha256_file(file_path)
        if actual_sha.lower() != expected_sha.lower():
            raise ProvenanceVerificationError(
                f"SHA-256 mismatch for '{filename}': manifest recorded {expected_sha}, actual file is {actual_sha}."
            )
        if actual_size != expected_size:
            raise ProvenanceVerificationError(
                f"File size mismatch for '{filename}': manifest recorded {expected_size} bytes, actual is {actual_size} bytes."
            )

        dl_ts_evidence = (
            EVIDENCE_UNVERIFIED
            if downloaded_at_utc == UNKNOWN_DOWNLOAD_TIMESTAMP
            else EVIDENCE_SOURCE_REPORTED
        )

        indexed_by_ds[ds_id][filename] = {
            **entry,
            "downloaded_at_utc": downloaded_at_utc,
            "manifest_recorded_at_utc": entry_recorded_at_utc,
            "manifest_top_level_recorded_at_utc": manifest_recorded_at,
            "download_timestamp_evidence_status": dl_ts_evidence,
            "local_file_integrity_status": LOCAL_INTEGRITY_VERIFIED_STATUS,
            "official_source_provenance_status": SOURCE_ORIGIN_HUMAN_ATTESTED_STATUS,
            "resolved_path": file_path,
            "resolved_license_path": lic_path,
            "verified_sha256": actual_sha,
            "verified_size_bytes": actual_size,
            "verified_license_sha256": lic_sha,
            "verified_license_size_bytes": lic_size,
        }

    # Verify all required files for each authorized dataset are present, and no unexpected files or symlinks sit in local_subdir
    for ds_id in authorized_dataset_ids:
        ds_spec = auth_manifest["datasets"][ds_id]
        required_files = set(ds_spec["authorized_files"])
        present_files = set(indexed_by_ds[ds_id].keys())
        missing = sorted(required_files - present_files)
        if missing:
            raise FormatValidationError(
                f"Missing required authorized file(s) for '{ds_id}': {missing}. Failing closed."
            )

        subdir = resolved_ds_dirs[ds_id]
        allowed_in_dir = required_files | set(ds_spec.get("optional_documentation_files", []))
        for item in sorted(subdir.iterdir()):
            if item.is_symlink():
                raise ProvenanceVerificationError(
                    f"Symlink '{item.name}' found inside authorized dataset directory '{subdir}' for '{ds_id}'."
                )
            if not item.is_file():
                raise ArchiveSecurityError(
                    f"Unexpected subdirectory or special file '{item.name}' found in dataset directory '{subdir}' "
                    f"for '{ds_id}'."
                )
            if item.name not in allowed_in_dir:
                raise ArchiveSecurityError(
                    f"Unexpected or unapproved file '{item.name}' found in dataset directory '{subdir}' "
                    f"for '{ds_id}'. Only {sorted(allowed_in_dir)} are authorized."
                )

    return indexed_by_ds


def inspect_zip_archive(
    zip_path: Path,
    dataset_id: str,
    auth_manifest: dict[str, Any],
) -> dict[str, Any]:
    """Inspect a downloaded UCI .zip archive in read-only mode before extraction.

    Fails closed with ArchiveSecurityError (STOP_REQUIRES_REVIEW) if the archive:
    - contains unsafe path traversal, absolute paths, drive letters, subdirectories, or symlinks;
    - contains executable or script files;
    - is missing any required authorized file for the dataset;
    - contains any excluded/unapproved dataset file (e.g. new.data, reprocessed.hungarian.data);
    - contains any unexpected extra file not in the explicit harmless archive metadata allowlist.
    """
    if dataset_id not in auth_manifest.get("datasets", {}):
        raise GovernanceAuthorizationError(f"Unknown dataset_id '{dataset_id}'.")
    if not zip_path.exists() or not zip_path.is_file():
        raise FormatValidationError(f"Archive file does not exist: '{zip_path}'.")
    if not zipfile.is_zipfile(zip_path):
        raise FormatValidationError(f"File '{zip_path}' is not a valid ZIP archive.")

    ds_spec = auth_manifest["datasets"][dataset_id]
    required_files = set(ds_spec["authorized_files"])
    optional_files = set(ds_spec.get("optional_documentation_files", []))
    known_excluded_dataset_files = set(ds_spec.get("excluded_unapproved_files", [])) | set(UCI_45_UNAPPROVED_FILES)
    harmless_metadata_allowlist = UCI_ARCHIVE_HARMLESS_METADATA_ALLOWLIST.get(dataset_id, frozenset())

    forbidden_extensions = {".exe", ".bat", ".cmd", ".ps1", ".vbs", ".js", ".sh", ".dll", ".so", ".py"}

    found_required: set[str] = set()
    found_optional: set[str] = set()
    harmless_metadata_found: list[str] = []
    flagged_excluded: list[str] = []
    unexpected_entries: list[str] = []

    archive_sha256, archive_size = sha256_file(zip_path)

    with zipfile.ZipFile(zip_path, "r") as zf:
        infos = zf.infolist()
        if not infos:
            raise ArchiveSecurityError(f"Archive '{zip_path.name}' is empty.")

        for info in infos:
            raw_name = info.filename
            normalized_entry = raw_name.replace("\\", "/")
            posix_parts = PurePosixPath(normalized_entry).parts

            if (
                raw_name.startswith("/")
                or raw_name.startswith("\\")
                or ":" in raw_name
                or ".." in posix_parts
                or "." in posix_parts
            ):
                raise ArchiveSecurityError(
                    f"Unsafe path traversal entry '{raw_name}' detected in archive '{zip_path.name}'."
                )

            # Check POSIX symlink file mode bit (0o120000) in external_attr
            unix_mode = (info.external_attr >> 16) & 0o170000
            if unix_mode == 0o120000:
                raise ArchiveSecurityError(
                    f"Unsafe symlink entry '{raw_name}' detected in archive '{zip_path.name}'."
                )

            if info.is_dir():
                raise ArchiveSecurityError(
                    f"STOP_REQUIRES_REVIEW: Unexpected directory entry '{raw_name}' in archive '{zip_path.name}'."
                )

            if len(posix_parts) != 1:
                raise ArchiveSecurityError(
                    f"Unsafe or unexpected nested path '{raw_name}' detected in archive '{zip_path.name}'."
                )

            basename = posix_parts[0]
            suffix = Path(basename).suffix.lower()
            if suffix in forbidden_extensions:
                raise ArchiveSecurityError(
                    f"Prohibited executable/script entry '{raw_name}' found in archive '{zip_path.name}'."
                )

            if basename in required_files:
                found_required.add(basename)
            elif basename in optional_files:
                found_optional.add(basename)
            elif basename in harmless_metadata_allowlist:
                harmless_metadata_found.append(raw_name)
            elif basename in known_excluded_dataset_files:
                flagged_excluded.append(raw_name)
            else:
                unexpected_entries.append(raw_name)

    missing_required = sorted(required_files - found_required)
    if missing_required:
        raise ArchiveSecurityError(
            f"STOP_REQUIRES_REVIEW: Archive '{zip_path.name}' for '{dataset_id}' is missing required official "
            f"file(s): {missing_required}. Unexpected entries seen: {sorted(unexpected_entries)}. "
            "Stop and do not substitute repackaged files."
        )

    if flagged_excluded or unexpected_entries:
        err = ArchiveSecurityError(
            f"STOP_REQUIRES_REVIEW: Archive '{zip_path.name}' for '{dataset_id}' differs from the authorized "
            f"dataset file list. Excluded/unapproved dataset file(s) present: {sorted(flagged_excluded)}; "
            f"unexpected extra entry/entries present: {sorted(unexpected_entries)}. "
            "Stop and review before extracting any file."
        )
        err.outcome = "STOP_REQUIRES_REVIEW"  # type: ignore[attr-defined]
        err.excluded_files_detected = sorted(flagged_excluded)  # type: ignore[attr-defined]
        err.unexpected_entries_detected = sorted(unexpected_entries)  # type: ignore[attr-defined]
        raise err

    return {
        "dataset_id": dataset_id,
        "archive_filename": zip_path.name,
        "archive_sha256": archive_sha256,
        "archive_size_bytes": archive_size,
        "outcome": "PASS_AUTHORIZED_CONTENTS",
        "required_files_verified": sorted(found_required),
        "optional_files_found": sorted(found_optional),
        "harmless_metadata_allowlist_matched": sorted(harmless_metadata_found),
        "excluded_files_detected": [],
        "unexpected_entries_detected": [],
        "passed": True,
    }


def build_provenance_manifest(
    base_root: Path,
    auth_manifest: dict[str, Any],
    dataset_ids: Sequence[str],
    *,
    acquirer: str,
    audit_reviewer: str,
    environment: str,
    downloaded_at_utc: str = UNKNOWN_DOWNLOAD_TIMESTAMP,
    manifest_recorded_at_utc: str | None = None,
    output_manifest_path: Path | None = None,
) -> dict[str, Any]:
    """Generate and validate a local provenance_manifest.json for human-acquired official files.

    Separates `downloaded_at_utc` (human-attested acquisition time or UNKNOWN_PENDING_HUMAN_VERIFICATION)
    from `manifest_recorded_at_utc` (automatically generated when the manifest is recorded), and
    explicitly distinguishes locally verified file integrity (`VERIFIED`) from human-attested
    official-source provenance (`HUMAN_ATTESTED_NOT_INDEPENDENTLY_PROVEN_BY_LOCAL_HASH`).
    """
    if not acquirer.strip() or not audit_reviewer.strip():
        raise ProvenanceVerificationError("Both 'acquirer' and 'audit_reviewer' must be non-empty strings.")

    verify_global_workflow_authorized(auth_manifest)

    recorded_ts = _validate_iso_utc_timestamp(
        manifest_recorded_at_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        field_name="manifest_recorded_at_utc",
        allow_unknown=False,
    )
    validated_dl_ts = _validate_iso_utc_timestamp(
        downloaded_at_utc,
        field_name="downloaded_at_utc",
        allow_unknown=True,
    )
    dl_ts_evidence = (
        EVIDENCE_UNVERIFIED
        if validated_dl_ts == UNKNOWN_DOWNLOAD_TIMESTAMP
        else EVIDENCE_SOURCE_REPORTED
    )

    files_entries: list[dict[str, Any]] = []

    for ds_id in dataset_ids:
        verify_dataset_authorized_for_audit(auth_manifest, ds_id)
        ds_spec = auth_manifest["datasets"][ds_id]
        expected_dir_posix = _expected_dataset_dir_posix(ds_id, ds_spec)
        _verify_existing_contained_directory(
            base_root,
            expected_dir_posix,
            context_label=f"{ds_id} authorized directory",
        )

        expected_lic_filename = f"uci-{ds_spec['uci_id']}-license-snapshot.txt"
        lic_rel = f"{APPROVED_LICENSE_DIR_POSIX.as_posix()}/{expected_lic_filename}"
        lic_path = _verify_contained_file_in_directory(
            base_root,
            lic_rel,
            expected_dir_posix=APPROVED_LICENSE_DIR_POSIX,
            expected_filename=expected_lic_filename,
            field_name=f"{ds_id}.license_snapshot_path",
        )
        lic_sha, _ = sha256_file(lic_path)

        subdir_rel = expected_dir_posix.as_posix()
        for filename in ds_spec["authorized_files"]:
            rel_file = f"{subdir_rel}/{filename}"
            file_path = _verify_contained_file_in_directory(
                base_root,
                rel_file,
                expected_dir_posix=expected_dir_posix,
                expected_filename=filename,
                field_name=f"{ds_id}:{filename}.relative_path",
            )
            file_sha, file_size = sha256_file(file_path)
            files_entries.append(
                {
                    "dataset_id": ds_id,
                    "uci_id": ds_spec["uci_id"],
                    "doi": ds_spec["doi"],
                    "official_source_url": ds_spec["official_source_url"],
                    "download_method": "official_uci_human_attested_download",
                    "filename": filename,
                    "relative_path": rel_file,
                    "downloaded_at_utc": validated_dl_ts,
                    "manifest_recorded_at_utc": recorded_ts,
                    "download_timestamp_evidence_status": dl_ts_evidence,
                    "local_file_integrity_status": LOCAL_INTEGRITY_VERIFIED_STATUS,
                    "official_source_provenance_status": SOURCE_ORIGIN_HUMAN_ATTESTED_STATUS,
                    "license_spdx": ds_spec["expected_license_spdx"],
                    "license_snapshot_path": lic_rel,
                    "license_snapshot_sha256": lic_sha,
                    "sha256": file_sha,
                    "size_bytes": file_size,
                }
            )

    manifest_doc: dict[str, Any] = {
        "schema_version": "1.1.0",
        "governance_decision_id": "D-046",
        "manifest_recorded_at_utc": recorded_ts,
        "provenance_verification_semantics": {
            "local_file_integrity_status": LOCAL_INTEGRITY_VERIFIED_STATUS,
            "official_source_provenance_status": SOURCE_ORIGIN_HUMAN_ATTESTED_STATUS,
            "explanation": (
                "Local SHA-256 digests and byte sizes are VERIFIED directly on disk before and after the read-only "
                "audit. However, a human-entered official_source_url, downloaded_at_utc, or newly generated local "
                "SHA-256 is human-attested provenance metadata and is NOT treated as independent cryptographic proof "
                "of upstream origin."
            ),
        },
        "acquirer": acquirer.strip(),
        "audit_reviewer": audit_reviewer.strip(),
        "environment": environment.strip(),
        "files": files_entries,
    }

    target_out = output_manifest_path or (base_root / "data/manifests/provenance_manifest.json")
    target_out.parent.mkdir(parents=True, exist_ok=True)
    target_out.write_text(json.dumps(manifest_doc, indent=2) + "\n", encoding="utf-8")

    # Verify the written manifest immediately
    validate_provenance_manifest(target_out, base_root, auth_manifest, dataset_ids)
    return manifest_doc
