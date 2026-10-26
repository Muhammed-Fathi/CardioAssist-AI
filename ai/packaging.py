"""Versioned RESEARCH_ONLY artifact bundle packaging, atomic staging, privacy
controls, and trusted-local-origin pre-deserialization verification.

Security, privacy & scientific invariants:
1. **Atomic staging-directory commit & guaranteed failure cleanup:**
   :func:`package_research_bundle` writes all sibling files into a private
   temporary staging directory next to ``bundle_dir`` (POSIX ``0700`` / Windows
   protected NTFS ``D:PAI`` user-only DACL), applies and verifies strict private
   access controls on every file (POSIX ``0600`` / Windows NTFS user-only DACL,
   including ``model.joblib`` and ``shap_background.json``), verifies the staged
   bundle, and commits via atomic ``os.replace``. Any failure or interruption
   deletes the staging directory so partial bundles never remain on disk.
2. **SHA-256 integrity != producer authenticity:**
   :func:`verify_research_bundle` checks layout, governance flags, contract
   hashes, and file SHA-256 digests, returning
   ``producer_authenticated=False`` / ``safe_for_pickle_deserialization=False``.
   Because ``joblib.load`` executes pickle bytecode and an untrusted author can
   recompute valid SHA-256 digests around a malicious ``model.joblib``,
   deserialization MUST pass :func:`verify_trusted_local_bundle`, which enforces:
   - containment inside an explicit user-owned ``trusted_local_root`` outside
     tracked Git paths,
   - strict local user ownership and verified POSIX permissions (Linux/macOS) or
     verified NTFS Security-Descriptor DACLs (Windows, never trusting
     ``os.chmod`` or ``stat.st_mode`` bits), and
   - constant-time ``HMAC-SHA256`` verification against the local producer
     signing key BEFORE ``joblib.load`` is called.
3. **Training-projection privacy (``shap_background.json``):**
   ``shap_background.json`` stores encoded training-record projections that are
   reconstructible with ``preprocessing.json`` summary statistics. Real-patient
   backgrounds are blocked while Gate PT (``P-3``) is closed and marked
   non-redistributable / prohibited from commit or public upload.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import tempfile
from types import MappingProxyType
from typing import Any, Final, Mapping

import joblib

from ai.errors import BundleIntegrityError
from ai.explainability import METHOD_BY_MODEL_FAMILY, SHAP_BACKGROUND_SCHEMA_VERSION
from ai.filesystem_security import (
    SAFE_ARTIFACT_BASENAME_RE,
    ensure_private_directory,
    has_reparse_between,
    is_reparse_or_symlink,
    is_strictly_within_directory,
    is_valid_artifact_basename,
    is_windows_runtime,
    paths_equal_platform,
    protect_private_directory,
    relative_posix_if_within_directory,
    verify_access_control,
    write_new_private_file,
)
from ai.panels import ResearchPanelContract, get_panel_contract
from ai.training import TrainedResearchRun

REPOSITORY_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
BUNDLE_SCHEMA_VERSION: Final[str] = "cardioassist.ai.research_bundle/v1"
ATTESTATION_SCHEME: Final[str] = "hmac-sha256-local-producer-v1"
SAFE_BASENAME_RE: Final[re.Pattern[str]] = SAFE_ARTIFACT_BASENAME_RE
MAX_BUNDLE_FILE_BYTES: Final[int] = 64 * 1024 * 1024  # 64 MiB ceiling
MIN_SIGNING_KEY_BYTES: Final[int] = 32

MANIFEST_FILENAME: Final[str] = "manifest.json"
MODEL_FILENAME: Final[str] = "model.joblib"
PREPROCESSING_FILENAME: Final[str] = "preprocessing.json"
CALIBRATION_FILENAME: Final[str] = "calibration.json"
SHAP_BG_FILENAME: Final[str] = "shap_background.json"
EVALUATION_FILENAME: Final[str] = "evaluation_summary.json"
PROTOCOL_FILENAME: Final[str] = "protocol.md"

REQUIRED_SIBLING_FILES: Final[tuple[str, ...]] = (
    MODEL_FILENAME,
    PREPROCESSING_FILENAME,
    CALIBRATION_FILENAME,
    SHAP_BG_FILENAME,
    EVALUATION_FILENAME,
    PROTOCOL_FILENAME,
)

SENSITIVE_PRIVATE_FILES: Final[frozenset[str]] = frozenset(
    {
        MODEL_FILENAME,
        SHAP_BG_FILENAME,
    }
)

FORBIDDEN_SUMMARY_KEYS: Final[frozenset[str]] = frozenset(
    {
        "patient_rows",
        "patient_records",
        "raw_rows",
        "raw_records",
        "row_values",
        "predictions",
        "prediction_scores",
        "out_of_fold_predictions",
        "patient_ids",
        "source_rows",
        "background_matrix",
    }
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _target_sha256(definition: str) -> str:
    return _sha256(definition.strip().encode("utf-8"))


def _default_local_signing_key_path() -> Path:
    override = os.environ.get("CARDIOASSIST_LOCAL_SIGNING_KEY_PATH")
    if override:
        return Path(override)
    if is_windows_runtime():
        local_appdata = os.environ.get("LOCALAPPDATA", "").strip()
        base = (
            Path(local_appdata)
            if local_appdata
            else (Path.home() / "AppData" / "Local")
        )
        return base / "CardioAssistAI" / "local_bundle_hmac_v1.key"
    return Path.home() / ".cache" / "cardioassist_ai" / "local_bundle_hmac_v1.key"


def _validate_signing_key_bytes(key: bytes) -> bytes:
    if not isinstance(key, (bytes, bytearray)) or len(key) < MIN_SIGNING_KEY_BYTES:
        raise BundleIntegrityError(
            "invalid_local_signing_key",
            f"Local producer signing key must be >= {MIN_SIGNING_KEY_BYTES} bytes.",
        )
    return bytes(key)


def get_or_create_local_signing_key(key_path: Path | None = None) -> bytes:
    """Load or atomically initialize a user-private local HMAC signing key.

    Enforces POSIX ``0600`` + UID ownership on Linux/macOS and verified NTFS
    ``D:PAI`` user-only DACL isolation on Windows (never trusting ``os.chmod``
    or CRT ``st_mode`` bits on Windows).
    """
    path = Path(key_path) if key_path is not None else _default_local_signing_key_path()
    if is_reparse_or_symlink(path):
        raise BundleIntegrityError(
            "symlink_signing_key_prohibited",
            "Local signing key path must not be a symlink, junction, or reparse point.",
        )
    _assert_not_in_unignored_repo_path(path, error_code="unignored_signing_key_prohibited")

    parent = path.parent
    if is_reparse_or_symlink(parent):
        raise BundleIntegrityError(
            "symlink_signing_key_prohibited",
            "Local signing key parent directory must not be a symlink or junction.",
        )
    if not parent.exists():
        try:
            ensure_private_directory(parent)
        except OSError as exc:
            raise BundleIntegrityError(
                "insecure_signing_key_permissions",
                f"Failed to create private directory for local signing key: {exc}",
            ) from exc

    if not path.exists():
        secret_bytes = secrets.token_bytes(32)
        try:
            write_new_private_file(path, secret_bytes)
        except FileExistsError:
            pass
        except OSError as exc:
            raise BundleIntegrityError(
                "insecure_signing_key_permissions",
                f"Failed to initialize private local signing key: {exc}",
            ) from exc

    if is_reparse_or_symlink(path) or not path.is_file():
        raise BundleIntegrityError(
            "invalid_signing_key_file",
            "Local signing key must be a regular non-symlink file.",
        )
    key_acl = verify_access_control(
        path, expect_directory=False, strict_private=True
    )
    if not key_acl.ok:
        if key_acl.reason_category == "owner":
            raise BundleIntegrityError(
                "untrusted_signing_key_owner",
                f"Local signing key file is not owned by a trusted local owner: {key_acl.detail}",
            )
        raise BundleIntegrityError(
            "insecure_signing_key_permissions",
            f"Local signing key file failed private access-control verification: {key_acl.detail}",
        )
    return _validate_signing_key_bytes(path.read_bytes())


def _compute_manifest_attestation_hmac(
    manifest_core: Mapping[str, Any], key: bytes
) -> tuple[str, str]:
    checked_key = _validate_signing_key_bytes(key)
    key_id = _sha256(checked_key)[:16]
    canonical = json.dumps(
        manifest_core,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    digest = hmac.new(checked_key, canonical, hashlib.sha256).hexdigest()
    return key_id, digest


def _assert_not_in_unignored_repo_path(target: Path, *, error_code: str) -> None:
    rel_posix = relative_posix_if_within_directory(target, REPOSITORY_ROOT)
    if rel_posix is None:
        return
    probe = subprocess.run(
        ["git", "check-ignore", "-q", "--", rel_posix],
        cwd=str(REPOSITORY_ROOT),
        check=False,
    )
    if probe.returncode != 0:
        raise BundleIntegrityError(
            error_code,
            "Refusing to place or trust model artifacts inside a non-ignored repository path.",
        )


def _ensure_safe_output_path(bundle_dir: Path) -> Path:
    if bundle_dir.exists() or is_reparse_or_symlink(bundle_dir):
        raise BundleIntegrityError(
            "bundle_directory_already_exists",
            "Refusing to overwrite an existing artifact bundle directory.",
        )
    _assert_not_in_unignored_repo_path(
        bundle_dir, error_code="unignored_repository_path_prohibited"
    )
    parent = bundle_dir.parent
    if is_reparse_or_symlink(parent):
        raise BundleIntegrityError(
            "bundle_symlink_prohibited",
            "Bundle parent directory must not be a symlink, junction, or reparse point.",
        )
    if not parent.exists():
        try:
            ensure_private_directory(parent)
        except OSError as exc:
            raise BundleIntegrityError(
                "insecure_bundle_permissions",
                f"Failed to prepare private parent directory for bundle: {exc}",
            ) from exc
    resolved_parent = parent.resolve()
    target = resolved_parent / bundle_dir.name
    if target.exists() or is_reparse_or_symlink(target):
        raise BundleIntegrityError(
            "bundle_directory_already_exists",
            "Refusing to overwrite an existing artifact bundle directory.",
        )
    return target


def _assert_aggregate_only(summary: Mapping[str, Any]) -> None:
    def _walk(node: Any) -> None:
        if isinstance(node, Mapping):
            for k, v in node.items():
                if str(k).lower() in FORBIDDEN_SUMMARY_KEYS:
                    raise BundleIntegrityError(
                        "patient_level_key_in_summary",
                        "Evaluation summary must not contain row-aligned or patient-level keys.",
                    )
                _walk(v)
        elif isinstance(node, (list, tuple)):
            for item in node:
                _walk(item)

    _walk(summary)
    try:
        json.dumps(summary, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise BundleIntegrityError(
            "non_finite_summary_value",
            "Evaluation summary contains non-JSON or non-finite values.",
        ) from exc


def _write_atomic_private(path: Path, content: bytes) -> dict[str, Any]:
    try:
        write_new_private_file(path, content)
    except OSError as exc:
        raise BundleIntegrityError(
            "private_artifact_write_or_acl_failed",
            f"Failed to write and verify private bundle file '{path.name}': {exc}",
            field=path.name,
        ) from exc
    return {
        "sha256": _sha256(content),
        "size_bytes": len(content),
    }


@dataclass(frozen=True, slots=True)
class VerifiedBundleDescriptor:
    """Result of bundle inspection.

    Note: ``verify_research_bundle`` sets ``producer_authenticated=False`` and
    ``safe_for_pickle_deserialization=False`` because SHA-256 self-consistency
    does NOT authenticate an untrusted bundle author. Only
    ``verify_trusted_local_bundle`` sets ``safe_for_pickle_deserialization=True``.
    """

    bundle_dir: Path
    manifest: Mapping[str, Any]
    panel: ResearchPanelContract
    verified_files: Mapping[str, str]
    serving_eligibility: str = "RESEARCH_ONLY"
    approved_for_serving: bool = False
    clinical_use_authorized: bool = False
    integrity_verified_only_not_authenticated: bool = True
    producer_authenticated: bool = False
    safe_for_pickle_deserialization: bool = False


_INTERNAL_EXEC_SECRET: bytes = secrets.token_bytes(32)


def generate_execution_verification_token(
    *,
    decision_id: str,
    dataset_id: str,
    panel_id: str,
    experiment_type: str,
    source_rel_path: str,
    source_sha256: str,
    row_count: int,
    pinned_commit: str,
    protocol_sha: str,
    plan_sha: str,
    dictionary_sha: str | None,
    signer: str,
    signed_at: str,
    attestation: str,
    allowed_operations: tuple[str, ...],
    forbidden_operations: tuple[str, ...],
    protected_output_root: str,
) -> str:
    """Issue a cryptographically verifiable token binding all governance decision, source, and scope parameters."""
    payload = json.dumps({
        "decision_id": decision_id,
        "dataset_id": dataset_id,
        "panel_id": panel_id,
        "experiment_type": experiment_type,
        "source_rel_path": source_rel_path,
        "source_sha256": source_sha256.lower(),
        "row_count": row_count,
        "pinned_commit": pinned_commit.lower(),
        "protocol_sha": protocol_sha.lower(),
        "plan_sha": plan_sha.lower(),
        "dictionary_sha": dictionary_sha.lower() if dictionary_sha else None,
        "signer": signer,
        "signed_at": signed_at,
        "attestation": attestation,
        "allowed_operations": sorted(allowed_operations),
        "forbidden_operations": sorted(forbidden_operations),
        "protected_output_root": protected_output_root,
    }, sort_keys=True)
    return hmac.new(_INTERNAL_EXEC_SECRET, payload.encode("utf-8"), hashlib.sha256).hexdigest()


@dataclass(frozen=True, slots=True)
class AuthorizedExecutionContext:
    """Narrowly scoped, internally validated execution context for authorized research runs.

    Requires an authentic, internally issued cryptographic verification token
    created only when established governance validators have ratified the run.
    Arbitrary caller-instantiated contexts without an authentic internal token
    fail closed.

    Note: The internal token authenticates that governance validation succeeded
    within this execution process; it is NOT independent evidence of human scientific
    approval, which is established exclusively by the ratified PR merge and signed attestation.
    """
    governance_decision_id: str
    dataset_id: str
    panel_id: str
    experiment_type: str
    source_relative_path: str
    expected_source_sha256: str
    expected_source_row_count: int
    authorized_by: str
    authorized_date: str
    signature_attestation: str
    pinned_commit_sha: str
    protocol_sha256: str
    plan_sha256: str
    dictionary_sha256: str | None
    allowed_operations: tuple[str, ...]
    forbidden_operations: tuple[str, ...]
    protected_output_root: str
    governance_details: Mapping[str, Any]
    verification_token: str = ""
    model_packaging_authorized: bool = False
    patient_shap_authorized: bool = False

    def verify_authenticity(self) -> bool:
        """Verify that this context was issued through established governance validation with matching scope."""
        if not self.verification_token:
            return False
        expected = generate_execution_verification_token(
            decision_id=self.governance_decision_id,
            dataset_id=self.dataset_id,
            panel_id=self.panel_id,
            experiment_type=self.experiment_type,
            source_rel_path=self.source_relative_path,
            source_sha256=self.expected_source_sha256,
            row_count=self.expected_source_row_count,
            pinned_commit=self.pinned_commit_sha,
            protocol_sha=self.protocol_sha256,
            plan_sha=self.plan_sha256,
            dictionary_sha=self.dictionary_sha256,
            signer=self.authorized_by,
            signed_at=self.authorized_date,
            attestation=self.signature_attestation,
            allowed_operations=self.allowed_operations,
            forbidden_operations=self.forbidden_operations,
            protected_output_root=self.protected_output_root,
        )
        return hmac.compare_digest(expected, self.verification_token)

    def to_manifest_dict(self) -> dict[str, Any]:
        return {
            "governance_decision_id": self.governance_decision_id,
            "dataset_id": self.dataset_id,
            "panel_id": self.panel_id,
            "experiment_type": self.experiment_type,
            "source_relative_path": self.source_relative_path,
            "expected_source_sha256": self.expected_source_sha256,
            "expected_source_row_count": self.expected_source_row_count,
            "authorized_by": self.authorized_by,
            "authorized_date": self.authorized_date,
            "signature_attestation": self.signature_attestation,
            "pinned_commit_sha": self.pinned_commit_sha,
            "protocol_sha256": self.protocol_sha256,
            "plan_sha256": self.plan_sha256,
            "dictionary_sha256": self.dictionary_sha256,
            "allowed_operations": list(self.allowed_operations),
            "forbidden_operations": list(self.forbidden_operations),
            "protected_output_root": self.protected_output_root,
            "model_packaging_authorized": self.model_packaging_authorized,
            "patient_shap_authorized": self.patient_shap_authorized,
        }


def package_research_bundle(
    trained_run: TrainedResearchRun,
    bundle_dir: Path,
    *,
    external_evaluation: Mapping[str, Any] | None = None,
    generated_at_utc: str | None = None,
    signing_key: bytes | None = None,
    authorization_context: AuthorizedExecutionContext | None = None,
) -> VerifiedBundleDescriptor:
    """Stage, sign, verify, and atomically commit a RESEARCH_ONLY model bundle."""
    is_real = not trained_run.synthetic_only or not trained_run.shap_background.synthetic_only
    if is_real:
        if authorization_context is None or not isinstance(authorization_context, AuthorizedExecutionContext):
            raise BundleIntegrityError(
                "real_patient_artifact_packaging_blocked_gate_pt_closed",
                "Gate PT (P-3) remains closed; packaging real-patient model or SHAP background "
                "artifacts requires an explicit, verified AuthorizedExecutionContext.",
            )
        if not authorization_context.verify_authenticity():
            raise BundleIntegrityError(
                "unauthorized_or_forged_context",
                "AuthorizedExecutionContext failed cryptographic governance token verification; "
                "arbitrary caller-instantiated contexts are rejected.",
            )
        if not authorization_context.model_packaging_authorized:
            raise BundleIntegrityError(
                "model_packaging_operation_not_authorized",
                f"Governance decision '{authorization_context.governance_decision_id}' does not explicitly authorize "
                "persistent real-data model packaging without a separately ratified protocol amendment.",
            )
        if authorization_context.experiment_type != "INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED":
            raise BundleIntegrityError(
                "invalid_authorization_experiment_type",
                "Authorized research packaging requires experiment_type 'INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED'.",
            )
        if authorization_context.dataset_id != trained_run.panel.dataset_id:
            raise BundleIntegrityError(
                "dataset_authorization_mismatch",
                "Authorization dataset does not match trained run panel dataset.",
            )
        if authorization_context.panel_id != trained_run.panel.panel_id:
            raise BundleIntegrityError(
                "panel_authorization_mismatch",
                "Authorization panel does not match trained run panel.",
            )

    target_dir = _ensure_safe_output_path(Path(bundle_dir))
    active_key = (
        _validate_signing_key_bytes(signing_key)
        if signing_key is not None
        else get_or_create_local_signing_key()
    )

    timestamp = generated_at_utc or datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    eval_doc: dict[str, Any] = {
        "internal_evaluation": dict(trained_run.internal_evaluation),
        "negative_control": dict(trained_run.negative_control),
        "external_evaluation": (
            None if external_evaluation is None else dict(external_evaluation)
        ),
    }
    _assert_aggregate_only(eval_doc)

    staging_dir = Path(
        tempfile.mkdtemp(
            prefix=f".staging_{target_dir.name}_",
            dir=str(target_dir.parent),
        )
    )
    committed = False
    try:
        try:
            protect_private_directory(staging_dir)
        except OSError as exc:
            raise BundleIntegrityError(
                "insecure_bundle_permissions",
                f"Failed to lock down temporary staging directory: {exc}",
            ) from exc
        staging_acl = verify_access_control(
            staging_dir, expect_directory=True, strict_private=True
        )
        if not staging_acl.ok:
            raise BundleIntegrityError(
                "insecure_bundle_permissions",
                f"Temporary staging directory failed private access-control check: {staging_acl.detail}",
            )

        model_payload = {
            "selected_model_family": trained_run.selected_model_family,
            "estimator": trained_run.estimator,
            "fold_ensemble": [
                {
                    "fold_index": member.fold_index,
                    "model_family": member.model_family,
                    "preprocessor_json": member.preprocessor.to_json_dict(),
                    "calibrator_json": member.calibrator.to_json_dict(),
                    "estimator": member.estimator,
                }
                for member in trained_run.fold_ensemble
            ],
        }
        mem_buf = io.BytesIO()
        joblib.dump(model_payload, mem_buf, compress=3)
        model_bytes = mem_buf.getvalue()

        prep_bytes = trained_run.preprocessor.to_canonical_json_bytes()
        cal_bytes = trained_run.calibrator.to_canonical_json_bytes()
        shap_bytes = trained_run.shap_background.to_canonical_json_bytes()
        eval_bytes = (
            json.dumps(
                eval_doc, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False
            )
            + "\n"
        ).encode("utf-8")

        if trained_run.selected_model_family == "l2_logistic_regression":
            xai_explained_qty = "calibrated_log_odds"
            xai_scale = "calibrated_log_odds"
        else:
            xai_explained_qty = "raw_model_score"
            xai_scale = "raw_model_probability"

        protocol_md = (
            f"# Research Protocol Manifest — {trained_run.protocol_id}\n\n"
            f"- **Model ID:** `{trained_run.model_id}` (`v{trained_run.model_version}`)\n"
            f"- **Panel Contract:** `{trained_run.panel.panel_id}` (`{trained_run.panel.contract_sha256}`)\n"
            f"- **Selected Family:** `{trained_run.selected_model_family}`\n"
            f"- **SHAP Target & Scale:** `{xai_explained_qty}` (`{xai_scale}`; additive on calibrated probability = `false`)\n"
            f"- **Development Cohort:** `{trained_run.development_cohort_id}` (`{trained_run.development_dataset_id}`)\n"
            f"- **Serving Eligibility:** `RESEARCH_ONLY` (`approved_for_serving = false`)\n"
            f"- **Security & Privacy:** `shap_background.json` holds encoded training rows; commit/public upload and untrusted `joblib.load` are prohibited.\n"
            f"- **Limitation:** Not clinically validated; never interpret research scores as individual clinical CAD risk.\n"
        ).encode("utf-8")

        file_records: dict[str, dict[str, Any]] = {
            MODEL_FILENAME: _write_atomic_private(
                staging_dir / MODEL_FILENAME, model_bytes
            ),
            PREPROCESSING_FILENAME: _write_atomic_private(
                staging_dir / PREPROCESSING_FILENAME, prep_bytes
            ),
            CALIBRATION_FILENAME: _write_atomic_private(
                staging_dir / CALIBRATION_FILENAME, cal_bytes
            ),
            SHAP_BG_FILENAME: _write_atomic_private(
                staging_dir / SHAP_BG_FILENAME, shap_bytes
            ),
            EVALUATION_FILENAME: _write_atomic_private(
                staging_dir / EVALUATION_FILENAME, eval_bytes
            ),
            PROTOCOL_FILENAME: _write_atomic_private(
                staging_dir / PROTOCOL_FILENAME, protocol_md
            ),
        }

        manifest_core: dict[str, Any] = {
            "bundle_schema_version": BUNDLE_SCHEMA_VERSION,
            "generated_at_utc": timestamp,
            "model": {
                "model_id": trained_run.model_id,
                "model_version": trained_run.model_version,
                "protocol_id": trained_run.protocol_id,
                "selected_model_family": trained_run.selected_model_family,
                "selected_hyperparameters": dict(trained_run.selected_hyperparameters),
                "calibration_status": "calibrated_out_of_fold_logistic",
                "explainability": {
                    "method": METHOD_BY_MODEL_FAMILY[trained_run.selected_model_family],
                    "explained_quantity": xai_explained_qty,
                    "scale": xai_scale,
                    "additive_on_calibrated_probability": False,
                    "capability": "implemented_and_verified_in_research_harness",
                },
            },
            "panel_contract": {
                "panel_id": trained_run.panel.panel_id,
                "panel_version": trained_run.panel.panel_version,
                "contract_sha256": trained_run.panel.contract_sha256,
                "ordered_feature_names": list(trained_run.panel.feature_names),
            },
            "target": {
                "target_id": trained_run.panel.target_id,
                "target_definition_sha256": _target_sha256(
                    trained_run.panel.target_definition
                ),
                "development_cohort_id": trained_run.development_cohort_id,
                "development_dataset_id": trained_run.development_dataset_id,
                "pooled_cohorts": False,
            },
            "research_authorization": (
                authorization_context.to_manifest_dict() if authorization_context is not None else None
            ),
            "eligibility": {
                "serving_eligibility": "RESEARCH_ONLY",
                "approved_for_serving": False,
                "clinical_use_authorized": False,
                "synthetic_only": bool(trained_run.synthetic_only),
                "execution_mode": "SYNTHETIC_RESEARCH" if trained_run.synthetic_only else "INTERNAL_EXPLORATORY_RESEARCH",
            },
            "privacy_and_security": {
                "sha256_verifies_integrity_not_producer_authenticity": True,
                "joblib_deserialization_requires_trusted_local_origin": True,
                "shap_background_contains_encoded_training_projections": True,
                "shap_background_reconstructible_with_preprocessor_stats": True,
                "commit_or_public_upload_prohibited": True,
            },
            "files": file_records,
        }

        key_id, hmac_hex = _compute_manifest_attestation_hmac(manifest_core, active_key)
        manifest = {
            **manifest_core,
            "local_producer_attestation": {
                "scheme": ATTESTATION_SCHEME,
                "key_id": key_id,
                "hmac_sha256": hmac_hex,
                "note": (
                    "Authenticates local producer possession of signing_key; plain SHA-256 "
                    "digests in 'files' detect accidental corruption only and NEVER make "
                    "untrusted pickle/joblib bundles safe."
                ),
            },
        }
        manifest_bytes = (
            json.dumps(
                manifest, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False
            )
            + "\n"
        ).encode("utf-8")
        _write_atomic_private(staging_dir / MANIFEST_FILENAME, manifest_bytes)

        # Validate complete staged bundle BEFORE exposing target_dir
        verify_trusted_local_bundle(
            staging_dir,
            trusted_local_root=target_dir.parent,
            signing_key=active_key,
        )

        if target_dir.exists() or is_reparse_or_symlink(target_dir):
            raise BundleIntegrityError(
                "bundle_directory_already_exists",
                "Refusing to overwrite an existing artifact bundle directory.",
            )
        os.replace(staging_dir, target_dir)
        committed = True
        try:
            protect_private_directory(target_dir)
        except OSError as exc:
            shutil.rmtree(target_dir, ignore_errors=True)
            raise BundleIntegrityError(
                "insecure_bundle_permissions",
                f"Failed to verify private permissions on committed bundle directory: {exc}",
            ) from exc
    finally:
        if not committed and staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)

    return verify_trusted_local_bundle(
        target_dir,
        trusted_local_root=target_dir.parent,
        signing_key=active_key,
    )


def _read_safe_regular_file(root: Path, filename: str) -> bytes:
    if not is_valid_artifact_basename(filename):
        raise BundleIntegrityError(
            "unsafe_bundle_filename",
            f"Unsafe artifact filename '{filename}' rejected.",
            field=filename,
        )
    candidate = root / filename
    if is_reparse_or_symlink(candidate):
        raise BundleIntegrityError(
            "bundle_symlink_prohibited",
            f"Symlinked or reparse-point bundle member '{filename}' is prohibited.",
            field=filename,
        )
    if not candidate.is_file():
        raise BundleIntegrityError(
            "bundle_file_missing",
            f"Required bundle file '{filename}' is missing.",
            field=filename,
        )
    resolved = candidate.resolve()
    if not paths_equal_platform(resolved.parent, root.resolve()):
        raise BundleIntegrityError(
            "bundle_path_traversal_detected",
            f"Bundle file '{filename}' escaped bundle directory.",
            field=filename,
        )
    size = resolved.stat().st_size
    if size <= 0 or size > MAX_BUNDLE_FILE_BYTES:
        raise BundleIntegrityError(
            "bundle_file_size_invalid",
            f"Bundle file '{filename}' violates byte size limits.",
            field=filename,
        )
    return resolved.read_bytes()


def verify_research_bundle(
    bundle_dir: Path,
) -> VerifiedBundleDescriptor:
    """Verify structural layout, governance flags, privacy metadata, and SHA-256 digests.

    IMPORTANT SECURITY BOUNDARY:
    Passing :func:`verify_research_bundle` proves internal hash consistency ONLY.
    It does NOT authenticate an untrusted bundle producer and does NOT authorize
    calling ``joblib.load`` on ``model.joblib``. Call
    :func:`verify_trusted_local_bundle` before any pickle/joblib deserialization.
    """
    root = Path(bundle_dir)
    if is_reparse_or_symlink(root) or not root.is_dir():
        raise BundleIntegrityError(
            "invalid_bundle_directory",
            "Bundle root must be an existing non-symlink, non-reparse directory.",
        )

    present_entries = {entry.name for entry in root.iterdir()}
    expected_entries = {MANIFEST_FILENAME, *REQUIRED_SIBLING_FILES}
    if present_entries != expected_entries:
        raise BundleIntegrityError(
            "unexpected_bundle_directory_contents",
            "Bundle directory contains missing or unexpected files.",
        )

    manifest_raw = _read_safe_regular_file(root, MANIFEST_FILENAME)
    try:
        manifest = json.loads(manifest_raw.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise BundleIntegrityError(
            "malformed_manifest_json",
            "Bundle manifest.json is not valid UTF-8 JSON.",
        ) from exc

    if not isinstance(manifest, Mapping) or (
        manifest.get("bundle_schema_version") != BUNDLE_SCHEMA_VERSION
    ):
        raise BundleIntegrityError(
            "unsupported_bundle_schema",
            "Unsupported or missing bundle_schema_version in manifest.json.",
        )

    eligibility = manifest.get("eligibility", {})
    if (
        not isinstance(eligibility, Mapping)
        or eligibility.get("serving_eligibility") != "RESEARCH_ONLY"
        or eligibility.get("approved_for_serving") is not False
        or eligibility.get("clinical_use_authorized") is not False
    ):
        raise BundleIntegrityError(
            "unauthorized_serving_claim",
            "Bundle manifest makes an unauthorized serving or clinical-use claim.",
            field="eligibility",
        )
    # A non-synthetic bundle must have an authentic, internally complete research_authorization record
    auth_doc = manifest.get("research_authorization")
    has_valid_auth = False
    if auth_doc is not None and isinstance(auth_doc, Mapping):
        gov_id = auth_doc.get("governance_decision_id")
        exp_type = auth_doc.get("experiment_type")
        signer = auth_doc.get("authorized_by")
        sig_attest = auth_doc.get("signature_attestation")
        pinned_commit = auth_doc.get("pinned_commit_sha")
        proto_sha = auth_doc.get("protocol_sha256")
        plan_sha = auth_doc.get("plan_sha256")
        if (
            gov_id in ("D-047", "D-048", "M3A-UCI412-INTERNAL-RESEARCH-PROPOSAL")
            and exp_type == "INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED"
            and isinstance(signer, str) and len(signer.strip()) > 0
            and isinstance(sig_attest, str) and "CLOSED" in sig_attest
            and isinstance(pinned_commit, str) and len(pinned_commit) == 40
            and isinstance(proto_sha, str) and len(proto_sha) == 64
            and isinstance(plan_sha, str) and len(plan_sha) == 64
        ):
            has_valid_auth = True

    if eligibility.get("synthetic_only") is not True and not has_valid_auth:
        raise BundleIntegrityError(
            "real_patient_bundle_blocked_gate_pt_closed",
            "Gate PT (P-3) remains closed; non-synthetic patient-derived bundles are rejected unless authorized.",
            field="eligibility.synthetic_only",
        )

    priv_sec = manifest.get("privacy_and_security", {})
    if (
        not isinstance(priv_sec, Mapping)
        or priv_sec.get("sha256_verifies_integrity_not_producer_authenticity")
        is not True
        or priv_sec.get("joblib_deserialization_requires_trusted_local_origin")
        is not True
        or priv_sec.get("commit_or_public_upload_prohibited") is not True
    ):
        raise BundleIntegrityError(
            "missing_security_or_privacy_declaration",
            "Bundle manifest lacks mandatory security and training-derivative privacy flags.",
            field="privacy_and_security",
        )

    target = manifest.get("target", {})
    if not isinstance(target, Mapping) or target.get("pooled_cohorts") is not False:
        raise BundleIntegrityError(
            "pooled_cohort_bundle_rejected",
            "Bundles asserting pooled cohorts are rejected.",
            field="target.pooled_cohorts",
        )

    panel_block = manifest.get("panel_contract", {})
    if not isinstance(panel_block, Mapping):
        raise BundleIntegrityError(
            "missing_panel_contract",
            "Bundle manifest lacks panel_contract metadata.",
        )
    panel = get_panel_contract(str(panel_block.get("panel_id", "")))
    if (
        panel_block.get("contract_sha256") != panel.contract_sha256
        or tuple(panel_block.get("ordered_feature_names", ())) != panel.feature_names
    ):
        raise BundleIntegrityError(
            "panel_contract_hash_or_order_mismatch",
            "Bundle panel hash or feature order does not match the registered contract.",
            field="panel_contract",
        )

    if target.get("target_id") != panel.target_id or target.get(
        "target_definition_sha256"
    ) != _target_sha256(panel.target_definition):
        raise BundleIntegrityError(
            "target_definition_mismatch",
            "Bundle target definition hash does not match the registered panel target.",
            field="target",
        )

    model_block = manifest.get("model", {})
    family = str(model_block.get("selected_model_family", ""))
    if family not in METHOD_BY_MODEL_FAMILY:
        raise BundleIntegrityError(
            "unsupported_model_family",
            "Bundle declares an unregistered research model family.",
            field="model.selected_model_family",
        )
    xai_block = model_block.get("explainability", {})
    if (
        not isinstance(xai_block, Mapping)
        or xai_block.get("method") != METHOD_BY_MODEL_FAMILY[family]
        or xai_block.get("additive_on_calibrated_probability") is not False
    ):
        raise BundleIntegrityError(
            "unfaithful_explainability_declaration",
            "Declared explainability method or calibrated-additivity flag is invalid.",
            field="model.explainability",
        )

    declared_files = manifest.get("files")
    if not isinstance(declared_files, Mapping) or set(declared_files) != set(
        REQUIRED_SIBLING_FILES
    ):
        raise BundleIntegrityError(
            "manifest_files_table_invalid",
            "Manifest files table does not list the exact required bundle files.",
            field="files",
        )

    verified_digests: dict[str, str] = {}
    sibling_bytes: dict[str, bytes] = {}
    for filename in REQUIRED_SIBLING_FILES:
        meta = declared_files[filename]
        if not isinstance(meta, Mapping):
            raise BundleIntegrityError(
                "manifest_file_entry_invalid",
                f"Invalid manifest entry for '{filename}'.",
                field=filename,
            )
        content = _read_safe_regular_file(root, filename)
        if len(content) != int(meta.get("size_bytes", -1)):
            raise BundleIntegrityError(
                "file_size_mismatch",
                f"Byte size mismatch detected for '{filename}'.",
                field=filename,
            )
        actual_sha = _sha256(content)
        if actual_sha != str(meta.get("sha256", "")):
            raise BundleIntegrityError(
                "file_sha256_mismatch",
                f"SHA-256 integrity mismatch detected for '{filename}'.",
                field=filename,
            )
        verified_digests[filename] = actual_sha
        sibling_bytes[filename] = content

    # Inspect shap_background.json privacy classification prior to any model load
    try:
        bg_doc = json.loads(sibling_bytes[SHAP_BG_FILENAME].decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise BundleIntegrityError(
            "malformed_shap_background_json",
            "shap_background.json is not valid UTF-8 JSON.",
            field=SHAP_BG_FILENAME,
        ) from exc
    bg_priv = bg_doc.get("privacy") if isinstance(bg_doc, Mapping) else None
    if (
        not isinstance(bg_doc, Mapping)
        or bg_doc.get("schema_version") != SHAP_BACKGROUND_SCHEMA_VERSION
        or not isinstance(bg_priv, Mapping)
        or bg_priv.get("contains_encoded_training_projections") is not True
        or bg_priv.get("reconstructible_with_preprocessor_stats") is not True
        or bg_priv.get("commit_or_public_upload_prohibited") is not True
    ):
        raise BundleIntegrityError(
            "missing_shap_background_privacy_metadata",
            "shap_background.json lacks mandatory training-data-derivative privacy metadata.",
            field=SHAP_BG_FILENAME,
        )
    if bg_priv.get("synthetic_only") is not True and not has_valid_auth:
        raise BundleIntegrityError(
            "sensitive_real_background_blocked_gate_pt_closed",
            "shap_background.json contains non-synthetic patient-derived rows while Gate PT is closed unless authorized.",
            field=SHAP_BG_FILENAME,
        )

    return VerifiedBundleDescriptor(
        bundle_dir=root.resolve(),
        manifest=MappingProxyType(dict(manifest)),
        panel=panel,
        verified_files=MappingProxyType(verified_digests),
        integrity_verified_only_not_authenticated=True,
        producer_authenticated=False,
        safe_for_pickle_deserialization=False,
    )


def verify_trusted_local_bundle(
    bundle_dir: Path,
    *,
    trusted_local_root: Path,
    signing_key: bytes | None = None,
) -> VerifiedBundleDescriptor:
    """Enforce trusted-local-origin containment, platform-verified ownership &
    access controls (POSIX mode/UID on Linux/macOS; Win32 NTFS Security-Descriptor
    DACL inspection on Windows), and HMAC-SHA256 producer authentication BEFORE
    ``joblib.load`` can be invoked.
    """
    verified = verify_research_bundle(bundle_dir)

    trust_root = Path(trusted_local_root)
    if is_reparse_or_symlink(trust_root) or not trust_root.is_dir():
        raise BundleIntegrityError(
            "invalid_trusted_local_root",
            "trusted_local_root must be an existing non-symlink, non-reparse directory.",
        )
    _assert_not_in_unignored_repo_path(
        trust_root, error_code="unignored_trusted_root_prohibited"
    )
    resolved_trust_root = trust_root.resolve()
    resolved_bundle = verified.bundle_dir

    root_acl = verify_access_control(
        resolved_trust_root,
        expect_directory=True,
        strict_private=is_windows_runtime(),
    )
    if not root_acl.ok:
        if root_acl.reason_category == "owner":
            raise BundleIntegrityError(
                "untrusted_root_owner",
                f"trusted_local_root is not owned by a trusted local owner: {root_acl.detail}",
            )
        raise BundleIntegrityError(
            "insecure_trusted_root_permissions",
            f"trusted_local_root failed access-control verification: {root_acl.detail}",
        )

    if not is_strictly_within_directory(resolved_bundle, resolved_trust_root):
        raise BundleIntegrityError(
            "untrusted_bundle_location",
            "Refusing to deserialize bundle outside trusted_local_root.",
        )
    if has_reparse_between(resolved_bundle, resolved_trust_root):
        raise BundleIntegrityError(
            "bundle_symlink_prohibited",
            "Refusing to deserialize bundle reached across a symlink, junction, or reparse point.",
        )
    _assert_not_in_unignored_repo_path(
        resolved_bundle, error_code="unignored_repository_path_prohibited"
    )

    bundle_acl = verify_access_control(
        resolved_bundle,
        expect_directory=True,
        strict_private=is_windows_runtime(),
    )
    if not bundle_acl.ok:
        if bundle_acl.reason_category == "owner":
            raise BundleIntegrityError(
                "untrusted_bundle_owner",
                f"Bundle directory is not owned by a trusted local owner: {bundle_acl.detail}",
            )
        raise BundleIntegrityError(
            "insecure_bundle_permissions",
            f"Bundle directory failed access-control verification: {bundle_acl.detail}",
        )

    for fname in (MANIFEST_FILENAME, *REQUIRED_SIBLING_FILES):
        is_sensitive = fname in SENSITIVE_PRIVATE_FILES
        file_acl = verify_access_control(
            resolved_bundle / fname,
            expect_directory=False,
            strict_private=is_sensitive or is_windows_runtime(),
        )
        if not file_acl.ok:
            if file_acl.reason_category == "owner":
                raise BundleIntegrityError(
                    "untrusted_bundle_owner",
                    f"Bundle file '{fname}' is not owned by a trusted local owner: {file_acl.detail}",
                    field=fname,
                )
            err_code = (
                "insecure_sensitive_artifact_permissions"
                if is_sensitive
                else "insecure_bundle_permissions"
            )
            raise BundleIntegrityError(
                err_code,
                f"Bundle file '{fname}' failed private access-control verification: {file_acl.detail}",
                field=fname,
            )

    attestation = verified.manifest.get("local_producer_attestation")
    if (
        not isinstance(attestation, Mapping)
        or attestation.get("scheme") != ATTESTATION_SCHEME
        or not isinstance(attestation.get("hmac_sha256"), str)
        or not isinstance(attestation.get("key_id"), str)
    ):
        raise BundleIntegrityError(
            "missing_local_producer_attestation",
            "Bundle lacks local_producer_attestation; SHA-256 digests alone cannot "
            "authenticate untrusted joblib/pickle artifacts.",
            field="local_producer_attestation",
        )

    active_key = (
        _validate_signing_key_bytes(signing_key)
        if signing_key is not None
        else get_or_create_local_signing_key()
    )
    manifest_core = {
        k: v
        for k, v in verified.manifest.items()
        if k != "local_producer_attestation"
    }
    expected_key_id, expected_hmac = _compute_manifest_attestation_hmac(
        manifest_core, active_key
    )
    if not hmac.compare_digest(
        str(attestation["key_id"]), expected_key_id
    ) or not hmac.compare_digest(str(attestation["hmac_sha256"]), expected_hmac):
        raise BundleIntegrityError(
            "untrusted_bundle_producer_signature",
            "Bundle HMAC producer attestation failed verification; refusing joblib.load.",
            field="local_producer_attestation",
        )

    return VerifiedBundleDescriptor(
        bundle_dir=verified.bundle_dir,
        manifest=verified.manifest,
        panel=verified.panel,
        verified_files=verified.verified_files,
        serving_eligibility=verified.serving_eligibility,
        approved_for_serving=verified.approved_for_serving,
        clinical_use_authorized=verified.clinical_use_authorized,
        integrity_verified_only_not_authenticated=False,
        producer_authenticated=True,
        safe_for_pickle_deserialization=True,
    )
