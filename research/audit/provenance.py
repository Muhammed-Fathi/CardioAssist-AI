"""Governance authorization checks, provenance/license verification, archive inspection, and byte-identity guards."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
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
    FORBIDDEN_SOURCE_HOSTS_SUBSTRINGS,
    OFFICIAL_UCI_HOST,
    UCI_45_UNAPPROVED_FILES,
)

AUTHORIZED_STATUS_VALUE = "AUTHORIZED_FOR_READ_ONLY_AUDIT"
PENDING_STATUS_VALUE = "PENDING_HUMAN_ACCEPTANCE"


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
    """Context manager ensuring dataset files remain strictly byte-identical before and after audit."""

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

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is not None:
            return
        for rel_label, path, _, _ in self._files:
            pre_sha, pre_size = self._pre_hashes[path]
            post_sha, post_size = sha256_file(path)
            identical = (pre_sha == post_sha) and (pre_size == post_size)
            if not identical:
                raise ProvenanceVerificationError(
                    f"BYTE-IDENTITY VIOLATION on '{rel_label}': file changed during read-only audit!"
                )
            self.snapshots.append(
                FileHashSnapshot(
                    filename=path.name,
                    relative_path=rel_label,
                    pre_sha256=pre_sha,
                    post_sha256=post_sha,
                    size_bytes=post_size,
                    byte_identical=True,
                )
            )


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


def verify_dataset_authorized_for_audit(
    auth_manifest: dict[str, Any],
    dataset_id: str,
    *,
    requested_usage_role: str = "read_only_audit",
) -> dict[str, Any]:
    """Verify a dataset has explicit human Gate DA authorization and all required D-046 metadata."""
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


def validate_provenance_manifest(
    manifest_path: Path,
    base_root: Path,
    auth_manifest: dict[str, Any],
    authorized_dataset_ids: Sequence[str],
) -> dict[str, dict[str, Any]]:
    """Validate provenance_manifest.json, license snapshots, filenames, sizes, and SHA-256 hashes."""
    if not manifest_path.exists() or not manifest_path.is_file():
        raise ProvenanceVerificationError(
            f"Provenance manifest not found at '{manifest_path}'. "
            "Record download provenance, license snapshots, and SHA-256 hashes before running the audit."
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
        if auth_manifest["datasets"][ds_id].get("authorization_status") != AUTHORIZED_STATUS_VALUE:
            raise GovernanceAuthorizationError(
                f"Provenance manifest includes dataset '{ds_id}' which is not authorized in gate_da_authorization.json."
            )
        if ds_id not in indexed_by_ds:
            continue

        ds_spec = auth_manifest["datasets"][ds_id]
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

        dl_date = str(entry.get("download_date_utc", "")).strip()
        if not dl_date or "YYYY" in dl_date.upper():
            raise ProvenanceVerificationError(f"Missing or placeholder download_date_utc for '{ds_id}'.")

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

        rel_path_str = str(entry.get("relative_path", "")).replace("\\", "/")
        file_path = (base_root / rel_path_str).resolve()
        if file_path.name != filename:
            raise ProvenanceVerificationError(
                f"Filename '{filename}' does not match basename of relative_path '{rel_path_str}'."
            )

        lic_rel_str = str(entry.get("license_snapshot_path", "")).replace("\\", "/")
        if not lic_rel_str:
            raise ProvenanceVerificationError(f"Missing license_snapshot_path for '{filename}' ({ds_id}).")
        lic_path = (base_root / lic_rel_str).resolve()
        if not lic_path.exists() or not lic_path.is_file():
            raise ProvenanceVerificationError(
                f"License snapshot file missing at '{lic_path}' for '{filename}' ({ds_id})."
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

        indexed_by_ds[ds_id][filename] = {
            **entry,
            "resolved_path": file_path,
            "verified_sha256": actual_sha,
            "verified_size_bytes": actual_size,
            "verified_license_sha256": lic_sha,
            "verified_license_size_bytes": lic_size,
        }

    # Verify all required files for each authorized dataset are present, and no unexpected files sit in local_subdir
    for ds_id in authorized_dataset_ids:
        ds_spec = auth_manifest["datasets"][ds_id]
        required_files = set(ds_spec["authorized_files"])
        present_files = set(indexed_by_ds[ds_id].keys())
        missing = sorted(required_files - present_files)
        if missing:
            raise FormatValidationError(
                f"Missing required authorized file(s) for '{ds_id}': {missing}. Failing closed."
            )

        subdir = (base_root / str(ds_spec["local_subdir"]).replace("\\", "/")).resolve()
        if subdir.exists() and subdir.is_dir():
            allowed_in_dir = required_files | set(ds_spec.get("optional_documentation_files", []))
            for item in sorted(subdir.iterdir()):
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
    """Inspect a downloaded UCI .zip archive in read-only mode before extraction."""
    if dataset_id not in auth_manifest.get("datasets", {}):
        raise GovernanceAuthorizationError(f"Unknown dataset_id '{dataset_id}'.")
    if not zip_path.exists() or not zip_path.is_file():
        raise FormatValidationError(f"Archive file does not exist: '{zip_path}'.")
    if not zipfile.is_zipfile(zip_path):
        raise FormatValidationError(f"File '{zip_path}' is not a valid ZIP archive.")

    ds_spec = auth_manifest["datasets"][dataset_id]
    required_files = set(ds_spec["authorized_files"])
    optional_files = set(ds_spec.get("optional_documentation_files", []))
    known_excluded = set(ds_spec.get("excluded_unapproved_files", [])) | set(UCI_45_UNAPPROVED_FILES)

    forbidden_extensions = {".exe", ".bat", ".cmd", ".ps1", ".vbs", ".js", ".sh", ".dll", ".so", ".py"}

    found_required: set[str] = set()
    found_optional: set[str] = set()
    flagged_excluded: list[str] = []
    unexpected_entries: list[str] = []

    archive_sha256, archive_size = sha256_file(zip_path)

    with zipfile.ZipFile(zip_path, "r") as zf:
        infos = zf.infolist()
        if not infos:
            raise ArchiveSecurityError(f"Archive '{zip_path.name}' is empty.")

        for info in infos:
            raw_name = info.filename
            if (
                raw_name.startswith("/")
                or raw_name.startswith("\\")
                or ":" in raw_name
                or ".." in PurePosixPath(raw_name.replace("\\", "/")).parts
            ):
                raise ArchiveSecurityError(
                    f"Unsafe path traversal entry '{raw_name}' detected in archive '{zip_path.name}'."
                )
            if info.is_dir():
                continue

            basename = PurePosixPath(raw_name.replace("\\", "/")).name
            suffix = Path(basename).suffix.lower()
            if suffix in forbidden_extensions:
                raise ArchiveSecurityError(
                    f"Prohibited executable/script entry '{raw_name}' found in archive '{zip_path.name}'."
                )

            if basename in required_files:
                found_required.add(basename)
            elif basename in optional_files:
                found_optional.add(basename)
            elif basename in known_excluded or (dataset_id == "DA-A2" and basename in {"Index", "bak", "WARNING"}):
                flagged_excluded.append(raw_name)
            else:
                unexpected_entries.append(raw_name)

    missing_required = sorted(required_files - found_required)
    if missing_required:
        raise ArchiveSecurityError(
            f"Archive '{zip_path.name}' for '{dataset_id}' is missing required official file(s): {missing_required}. "
            f"Unexpected entries seen: {unexpected_entries}. Stop and do not substitute repackaged files."
        )

    if unexpected_entries and dataset_id != "DA-A2":
        raise ArchiveSecurityError(
            f"Archive '{zip_path.name}' for '{dataset_id}' contains unexpected file(s): {unexpected_entries}."
        )

    return {
        "dataset_id": dataset_id,
        "archive_filename": zip_path.name,
        "archive_sha256": archive_sha256,
        "archive_size_bytes": archive_size,
        "required_files_verified": sorted(found_required),
        "optional_files_found": sorted(found_optional),
        "excluded_files_detected_do_not_extract": sorted(flagged_excluded),
        "unexpected_non_extracted_entries": sorted(unexpected_entries),
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
    download_date_utc: str | None = None,
    output_manifest_path: Path | None = None,
) -> dict[str, Any]:
    """Generate and validate a local provenance_manifest.json for human-acquired official files."""
    if not acquirer.strip() or not audit_reviewer.strip():
        raise ProvenanceVerificationError("Both 'acquirer' and 'audit_reviewer' must be non-empty strings.")

    timestamp = download_date_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    files_entries: list[dict[str, Any]] = []

    for ds_id in dataset_ids:
        verify_dataset_authorized_for_audit(auth_manifest, ds_id)
        ds_spec = auth_manifest["datasets"][ds_id]
        lic_rel = f"data/manifests/licenses/uci-{ds_spec['uci_id']}-license-snapshot.txt"
        lic_path = (base_root / lic_rel).resolve()
        if not lic_path.exists():
            raise ProvenanceVerificationError(
                f"Missing license snapshot file '{lic_path}' for {ds_id}. "
                "Save the official UCI CC BY 4.0 license snapshot before recording provenance."
            )
        lic_sha, _ = sha256_file(lic_path)

        subdir_rel = str(ds_spec["local_subdir"]).replace("\\", "/")
        for filename in ds_spec["authorized_files"]:
            rel_file = f"{subdir_rel}/{filename}"
            file_path = (base_root / rel_file).resolve()
            file_sha, file_size = sha256_file(file_path)
            files_entries.append(
                {
                    "dataset_id": ds_id,
                    "uci_id": ds_spec["uci_id"],
                    "doi": ds_spec["doi"],
                    "official_source_url": ds_spec["official_source_url"],
                    "download_method": "official_uci_human_verified_download",
                    "filename": filename,
                    "relative_path": rel_file,
                    "download_date_utc": timestamp,
                    "license_spdx": ds_spec["expected_license_spdx"],
                    "license_snapshot_path": lic_rel,
                    "license_snapshot_sha256": lic_sha,
                    "sha256": file_sha,
                    "size_bytes": file_size,
                }
            )

    manifest_doc: dict[str, Any] = {
        "schema_version": "1.0.0",
        "governance_decision_id": "D-046",
        "generated_at_utc": timestamp,
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
