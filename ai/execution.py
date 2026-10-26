"""Locally protected, auditable real-data execution infrastructure for AI-2.

This module bridges the validated read-only dataset adapters
(:mod:`research.uci412.adapter` and :mod:`research.experiments.data_adapter`)
to the reusable AI research pipeline (:mod:`ai.training`, :mod:`ai.panels`,
:mod:`ai.packaging`, and :mod:`ai.inference`) under strict, human-ratified,
hash-bound authorization manifests.

Operating Principles & Safeguards:
1. Hard Synthetic Blocks Preservation:
   The existing synthetic hard blocks in ``ai.panels``, ``ai.training``, and
   ``ai.packaging`` remain fail-closed when called directly. Real-data execution
   is allowed ONLY through this explicitly verified, audit-logged execution
   controller (:class:`AuthorizedExecutionHarness`) after validating a local,
   private, Git-ignored, human-signed authorization manifest and verifying
   that byte-identical dataset files match approved SHA-256 provenance manifests.
2. Anti-Disguise & Provenance Verification:
   Real clinical data disguised as synthetic (or vice versa) is strictly rejected:
   input records are parsed strictly via read-only source adapters with verified
   source hashes, correct dictionary versions, explicit permitted feature sets,
   target mappings, and missingness semantics.
3. Prohibited Feature Rejection:
   Any catheterization/angiography variables (LAD, LCX, RCA, Cath), post-outcome
   measurements, unverified echocardiography variables (EF-TTE, Region RWMA, VHD),
   or wearable/smartwatch/sensor signals (Track B) are unconditionally blocked.
4. Human Ratification Required:
   Manifest templates (e.g. status containing PROPOSED or NOT_AUTHORIZED)
   never authorize execution. Real data fitting requires an explicit, timezone-aware
   locally signed manifest binding the verified git commit, protocol hash, plan hash,
   and source hash.
5. Windows Local Execution & Private Artifact Storage:
   Real runs execute only in local workstation environments (enforcing Win32 NTFS DACLs
   on Windows or private 0700/0600 POSIX permissions) and store artifacts strictly in
   private, Git-ignored locations (e.g., ``data/research-bundles/`` or user-specified
   local roots). No patient-level records or unredacted features escape into logs,
   tracebacks, or Git-tracked paths.
6. Research-Only Claims & Honest Scope:
   Every output is tagged ``INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED``. Gate PT (P-3)
   remains CLOSED. No clinical diagnostic claims, supervisor sign-offs, or external
   validation assertions are made.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
from typing import Any, Final, Mapping, Sequence

import numpy as np

from ai.calibration import OofLogisticCalibrator, evaluate_comprehensive_metrics
from ai.errors import (
    AiPipelineError,
    BundleIntegrityError,
    ClinicalInputValidationError,
    CohortGovernanceError,
)
from ai.explainability import ShapBackgroundReference
from ai.filesystem_security import (
    ensure_private_directory,
    is_reparse_or_symlink,
    is_strictly_within_directory,
    is_windows_runtime,
    paths_equal_platform,
    protect_private_directory,
    protect_private_file,
    relative_posix_if_within_directory,
    verify_access_control,
)
from ai.packaging import (
    get_or_create_local_signing_key,
    package_research_bundle,
    verify_trusted_local_bundle,
    VerifiedBundleDescriptor,
)
from ai.panels import (
    DA_A1_BASIC_CLINICAL_PANEL,
    DA_A1_CLINICAL_CORE_LABS_PANEL,
    DA_A2_RESTING_LABS_PANEL,
    DA_A2_RESTING_PANEL,
    ALL_PROHIBITED_FIELDS,
    REGISTERED_PANELS,
    PanelFieldSpec,
    ResearchPanelContract,
    validate_clinical_record,
    validate_cohort_records,
)
from ai.preprocessing import FoldSafeClinicalPreprocessor
from ai.training import (
    ResearchTrainingConfig,
    TrainedResearchRun,
    _execute_shared_training_pipeline,
    _validate_cohort_provenance_token,
)
from research.audit.provenance import sha256_file
from research.experiments.config import (
    DEFAULT_CONFIG as CLEVELAND_DEFAULT_CONFIG,
    PLAN_PATH as CLEVELAND_PLAN_PATH,
    PROTOCOL_RELATIVE_PATH as CLEVELAND_PROTOCOL_PATH,
    PROHIBITED_PREDICTORS as CLEVELAND_PROHIBITED,
    D047_AUTHORIZATION_COMMENT,
    D047_AUTHORIZATION_STATUS,
    D047_AUTHORIZING_PR_NUMBER,
    D047_AUTHORIZING_MERGE_SHA,
    D047_AUTHORIZING_MAINTAINER,
    D047_LOCAL_SIGNATURE_ATTESTATION,
    D047_REPORT_BANNER,
    REPOSITORY_ROOT,
)
from research.experiments.data_adapter import (
    ClevelandDataset,
    _parse_processed_cleveland_bytes,
    _read_source_bytes_read_only,
    sha256_bytes as cleveland_sha256_bytes,
)
from research.uci412.adapter import (
    ParsedWorkbook,
    SourceSnapshot as Uci412SourceSnapshot,
    Uci412Dataset,
    load_authorized_dataset as uci412_load_authorized_dataset,
    parse_workbook as uci412_parse_workbook,
    validate_workbook_structure as uci412_validate_workbook_structure,
)
from research.uci412.config import (
    DEFAULT_CONFIG as UCI412_DEFAULT_CONFIG,
    DEFAULT_DICTIONARY as UCI412_DEFAULT_DICTIONARY,
    PLAN_PATH as UCI412_PLAN_PATH,
    PROPOSAL_RELATIVE_PATH as UCI412_PROPOSAL_PATH,
    DICTIONARY_PATH as UCI412_DICT_PATH,
    M3A_AUTHORIZATION_COMMENT,
    M3A_AUTHORIZATION_STATUS,
    M3A_AUTHORIZING_MAINTAINER,
    M3A_LOCAL_SIGNATURE_ATTESTATION,
    M3A_PROTOCOL_AMENDMENT_ID,
    REPORT_BANNER as UCI412_REPORT_BANNER,
    Uci412Config,
)
from research.uci412.feature_schema import FeatureDictionary
from research.uci412.source_spec import PROHIBITED_PREDICTORS as UCI412_PROHIBITED

EXECUTION_HARNESS_VERSION: Final[str] = "cardioassist.ai.execution_harness/v1"
MANDATORY_OUTPUT_BANNER: Final[str] = "INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED"
GIT_SHA_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-fA-F]{40}$")
SHA256_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-fA-F]{64}$")

TRACK_A_UCI412_SOURCE_ID: Final[str] = "DA-A1"
TRACK_B_CLEVELAND_SOURCE_ID: Final[str] = "DA-A2"

# Allowed dataset / panel combinations for internal exploratory research
AUTHORIZED_REAL_PANELS: Final[Mapping[str, frozenset[str]]] = {
    TRACK_A_UCI412_SOURCE_ID: frozenset({"da_a1_basic_clinical_v1"}),
    TRACK_B_CLEVELAND_SOURCE_ID: frozenset({"da_a2_resting_v1"}),
}

BLOCKED_EXTENDED_PANELS: Final[frozenset[str]] = frozenset({
    "da_a2_resting_labs_v1",         # 7-feature Cleveland resting+labs panel
    "da_a1_clinical_core_labs_v1",   # 23-feature UCI-412 clinical+core-labs panel
})

PROHIBITED_REAL_DATA_DISGUISE_TOKENS: Final[tuple[str, ...]] = (
    "synthetic_patient",
    "mock_synthetic_override",
    "bypass_gate_pt",
    "force_real",
)


class ExecutionAuthorizationError(AiPipelineError):
    """Raised when an explicit real-data execution authorization check fails."""


class DatasetAdapterIntegrityError(AiPipelineError):
    """Raised when source-specific dataset parsing or provenance verification fails."""


@dataclass(frozen=True, slots=True)
class ResearchAuthorizationContext:
    """Validated, locally bound human research authorization."""

    manifest_path: Path
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
    is_template: bool


def _read_json_no_dups(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ExecutionAuthorizationError("manifest_missing", f"Authorization manifest not found: {path}")
    raw = path.read_bytes()
    try:
        def _check_dups(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            res: dict[str, Any] = {}
            for k, v in pairs:
                if k in res:
                    raise ExecutionAuthorizationError("duplicate_json_key", f"Duplicate key '{k}' in {path}")
                res[k] = v
            return res
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_check_dups)
    except Exception as exc:
        if isinstance(exc, ExecutionAuthorizationError):
            raise
        raise ExecutionAuthorizationError("malformed_json", f"Failed to parse JSON manifest at {path}: {exc}") from exc


def _check_path_git_ignored(path: Path, repo_root: Path = REPOSITORY_ROOT) -> None:
    """Verify that path is within repo_root and is Git-ignored, or is strictly outside repo_root."""
    rel = relative_posix_if_within_directory(path, repo_root)
    if rel is not None:
        git_dir = repo_root / ".git"
        if git_dir.exists():
            probe = subprocess.run(
                ["git", "check-ignore", "-q", "--", rel],
                cwd=str(repo_root),
                check=False,
            )
            if probe.returncode != 0:
                raise ExecutionAuthorizationError(
                    "unignored_sensitive_path",
                    f"Path '{rel}' is inside git checkout but is NOT ignored by .gitignore.",
                    field=rel,
                )


def parse_and_validate_research_authorization(
    manifest_path: Path,
    *,
    expected_dataset_id: str,
    expected_panel_id: str,
    repo_root: Path = REPOSITORY_ROOT,
    allow_synthetic_test_manifest: bool = False,
) -> ResearchAuthorizationContext:
    """Strictly validate a local research authorization manifest.

    Fails closed on:
    - Missing files, symlinks, or reparse points.
    - Template / unratified files (e.g. status containing PROPOSED, PENDING, or NOT_AUTHORIZED).
    - Mismatched human ratification evidence (signer, attestation, PR/decision metadata).
    - Mismatched protocol, plan, or dictionary digests compared against frozen on-disk files.
    - Unapproved dataset or panel IDs (extended panels fail before fitting).
    - Missing or placeholder signer, commit SHA, or hash bindings.
    - Storage inside unignored repository directories.
    - Supervisor approval claims (Gate PT P-3 remains CLOSED).
    """
    if is_reparse_or_symlink(manifest_path):
        raise ExecutionAuthorizationError("symlink_rejected", "Authorization manifest cannot be a symlink or reparse point.")

    _check_path_git_ignored(manifest_path, repo_root)
    data = _read_json_no_dups(manifest_path)

    auth_status = str(data.get("authorization_status", "")).strip()
    is_template = (
        "TEMPLATE" in auth_status.upper()
        or "PROPOSED" in auth_status.upper()
        or "NOT_AUTHORIZED" in auth_status.upper()
        or "PENDING" in auth_status.upper()
    )
    if is_template and not allow_synthetic_test_manifest:
        raise ExecutionAuthorizationError(
            "unauthorized_template_manifest",
            f"Authorization manifest has status '{auth_status}', which does NOT authorize execution.",
            field="authorization_status",
        )

    # Supervisor claim guard: Gate PT P-3 must remain closed!
    if data.get("supervisor_signoff_claimed") is not False:
        raise ExecutionAuthorizationError(
            "supervisor_approval_claimed_prohibited",
            "Supervisor sign-off cannot be claimed; Gate PT P-3 remains CLOSED.",
            field="supervisor_signoff_claimed",
        )

    exp_type = str(data.get("experiment_type", "")).strip()
    if exp_type != MANDATORY_OUTPUT_BANNER:
        raise ExecutionAuthorizationError(
            "invalid_experiment_type",
            f"Expected experiment_type '{MANDATORY_OUTPUT_BANNER}', got '{exp_type}'.",
            field="experiment_type",
        )

    dataset_id = str(data.get("dataset_id", "")).strip()
    if dataset_id != expected_dataset_id:
        raise ExecutionAuthorizationError(
            "dataset_id_mismatch",
            f"Manifest dataset_id '{dataset_id}' does not match expected '{expected_dataset_id}'.",
            field="dataset_id",
        )

    panel_id = str(data.get("panel_id") or data.get("panel_schema_id") or "").strip()
    if panel_id != expected_panel_id:
        raise ExecutionAuthorizationError(
            "panel_id_mismatch",
            f"Manifest panel_id '{panel_id}' does not match expected '{expected_panel_id}'.",
            field="panel_id",
        )

    if panel_id in BLOCKED_EXTENDED_PANELS:
        raise ExecutionAuthorizationError(
            "extended_panel_blocked_before_fitting",
            f"Extended panel '{panel_id}' is registered but explicitly blocked pending independent implementation and scientific approval.",
            field="panel_id",
        )

    if dataset_id not in AUTHORIZED_REAL_PANELS or panel_id not in AUTHORIZED_REAL_PANELS[dataset_id]:
        raise ExecutionAuthorizationError(
            "unauthorized_panel_for_dataset",
            f"Panel '{panel_id}' is not authorized for real data execution on dataset '{dataset_id}'.",
            field="panel_id",
        )

    signer = str(data.get("local_signer", "")).strip()
    if not signer or "REPLACE" in signer.upper():
        raise ExecutionAuthorizationError("missing_signer", "Manifest missing local human signer name.", field="local_signer")

    signed_at = str(data.get("local_signed_at_iso8601", "")).strip()
    if not signed_at or "REPLACE" in signed_at.upper():
        raise ExecutionAuthorizationError("missing_signed_at", "Manifest missing local signature ISO-8601 timestamp.", field="local_signed_at_iso8601")

    attestation = str(data.get("local_signature_attestation", "")).strip()
    if not attestation or "REPLACE" in attestation.upper():
        raise ExecutionAuthorizationError("missing_attestation", "Manifest missing required signature attestation string.", field="local_signature_attestation")

    commit_sha = str(data.get("pinned_protocol_git_commit_sha") or data.get("pinned_protocol_commit_sha") or "").strip()
    if not GIT_SHA_RE.fullmatch(commit_sha):
        raise ExecutionAuthorizationError("invalid_commit_sha", "Manifest missing valid 40-character hex commit SHA.", field="pinned_protocol_git_commit_sha")

    proto_sha = str(data.get("frozen_protocol_sha256") or data.get("frozen_authorization_proposal_sha256") or "").strip()
    if not SHA256_RE.fullmatch(proto_sha):
        raise ExecutionAuthorizationError("invalid_protocol_sha", "Manifest missing valid 64-character hex protocol SHA-256.", field="frozen_protocol_sha256")

    plan_sha = str(data.get("frozen_experiment_plan_sha256") or data.get("frozen_research_plan_sha256") or "").strip()
    if not SHA256_RE.fullmatch(plan_sha):
        raise ExecutionAuthorizationError("invalid_plan_sha", "Manifest missing valid 64-character hex plan SHA-256.", field="frozen_experiment_plan_sha256")

    dict_sha = data.get("frozen_feature_dictionary_sha256")
    if dict_sha is not None:
        dict_sha = str(dict_sha).strip()
        if not SHA256_RE.fullmatch(dict_sha):
            raise ExecutionAuthorizationError("invalid_dict_sha", "Manifest feature dictionary SHA-256 is invalid.", field="frozen_feature_dictionary_sha256")

    source_rel = str(data.get("allowed_original_relative_file", "")).strip()
    source_sha = str(data.get("expected_sha256_from_protected_provenance_manifest") or data.get("expected_source_sha256") or "").strip()
    if not SHA256_RE.fullmatch(source_sha):
        raise ExecutionAuthorizationError("invalid_source_sha", "Manifest missing valid 64-character hex source SHA-256.", field="expected_source_sha256")

    row_count = int(data.get("authorized_source_row_count", 0))
    if row_count <= 0:
        raise ExecutionAuthorizationError("invalid_row_count", "Manifest authorized_source_row_count must be > 0.", field="authorized_source_row_count")

    # Verify on-disk file digests for protocol, plan, dictionary, and exact source-path
    if dataset_id == TRACK_B_CLEVELAND_SOURCE_ID:
        expected_protocol_path = repo_root / CLEVELAND_PROTOCOL_PATH
        expected_plan_path = CLEVELAND_PLAN_PATH
        if expected_protocol_path.exists():
            actual_proto, _ = sha256_file(expected_protocol_path)
            if proto_sha.lower() != actual_proto.lower():
                raise ExecutionAuthorizationError(
                    "protocol_hash_mismatch",
                    f"Manifest protocol SHA-256 '{proto_sha}' does not match actual on-disk file digest '{actual_proto}'.",
                    field="frozen_protocol_sha256",
                )
        if expected_plan_path.exists():
            actual_plan, _ = sha256_file(expected_plan_path)
            if plan_sha.lower() != actual_plan.lower():
                raise ExecutionAuthorizationError(
                    "plan_hash_mismatch",
                    f"Manifest plan SHA-256 '{plan_sha}' does not match actual on-disk file digest '{actual_plan}'.",
                    field="frozen_experiment_plan_sha256",
                )
        # Verify human ratification evidence
        if signer != D047_AUTHORIZING_MAINTAINER:
            raise ExecutionAuthorizationError(
                "unratified_maintainer_signer",
                f"Signer '{signer}' is not the authorized maintainer '{D047_AUTHORIZING_MAINTAINER}'.",
                field="local_signer",
            )
        if attestation != D047_LOCAL_SIGNATURE_ATTESTATION:
            raise ExecutionAuthorizationError(
                "invalid_attestation_statement",
                "Signature attestation does not match the ratified D-047 attestation text.",
                field="local_signature_attestation",
            )
        if source_rel != "data/raw/uci-45/processed.cleveland.data":
            raise ExecutionAuthorizationError(
                "unauthorized_source_file_path",
                f"Source path '{source_rel}' is not the approved Cleveland source path.",
                field="allowed_original_relative_file",
            )

    elif dataset_id == TRACK_A_UCI412_SOURCE_ID:
        expected_proposal_path = repo_root / UCI412_PROPOSAL_PATH
        expected_plan_path = UCI412_PLAN_PATH
        expected_dict_path = UCI412_DICT_PATH
        if expected_proposal_path.exists():
            actual_prop, _ = sha256_file(expected_proposal_path)
            if proto_sha.lower() != actual_prop.lower():
                raise ExecutionAuthorizationError(
                    "proposal_hash_mismatch",
                    f"Manifest proposal SHA-256 '{proto_sha}' does not match actual on-disk file digest '{actual_prop}'.",
                    field="frozen_authorization_proposal_sha256",
                )
        if expected_plan_path.exists():
            actual_plan, _ = sha256_file(expected_plan_path)
            if plan_sha.lower() != actual_plan.lower():
                raise ExecutionAuthorizationError(
                    "plan_hash_mismatch",
                    f"Manifest plan SHA-256 '{plan_sha}' does not match actual on-disk file digest '{actual_plan}'.",
                    field="frozen_research_plan_sha256",
                )
        if expected_dict_path.exists() and dict_sha:
            actual_dict, _ = sha256_file(expected_dict_path)
            if dict_sha.lower() != actual_dict.lower():
                raise ExecutionAuthorizationError(
                    "dictionary_hash_mismatch",
                    f"Manifest dictionary SHA-256 '{dict_sha}' does not match actual on-disk file digest '{actual_dict}'.",
                    field="frozen_feature_dictionary_sha256",
                )
        if signer != M3A_AUTHORIZING_MAINTAINER:
            raise ExecutionAuthorizationError(
                "unratified_maintainer_signer",
                f"Signer '{signer}' is not the authorized maintainer '{M3A_AUTHORIZING_MAINTAINER}'.",
                field="local_signer",
            )
        if attestation != M3A_LOCAL_SIGNATURE_ATTESTATION:
            raise ExecutionAuthorizationError(
                "invalid_attestation_statement",
                "Signature attestation does not match the ratified M3a attestation text.",
                field="local_signature_attestation",
            )
        if source_rel != "data/raw/uci-412/Z-Alizadeh sani dataset.xlsx":
            raise ExecutionAuthorizationError(
                "unauthorized_source_file_path",
                f"Source path '{source_rel}' is not the approved UCI-412 workbook path.",
                field="allowed_original_relative_file",
            )

    return ResearchAuthorizationContext(
        manifest_path=manifest_path,
        governance_decision_id=str(data.get("decision_id") or data.get("governance_decision_id") or data.get("proposal_id")),
        dataset_id=dataset_id,
        panel_id=panel_id,
        experiment_type=exp_type,
        source_relative_path=source_rel,
        expected_source_sha256=source_sha.lower(),
        expected_source_row_count=row_count,
        authorized_by=signer,
        authorized_date=signed_at,
        signature_attestation=attestation,
        pinned_commit_sha=commit_sha.lower(),
        protocol_sha256=proto_sha.lower(),
        plan_sha256=plan_sha.lower(),
        dictionary_sha256=dict_sha.lower() if dict_sha else None,
        is_template=is_template,
    )


def _check_source_not_disguised_or_contaminated(
    features: Sequence[Mapping[str, Any]],
    source_path: Path,
) -> None:
    """Ensure raw patient records do not carry mock/synthetic disguise tokens or prohibited variables."""
    for row_idx, row in enumerate(features):
        prohibited_in_row = set(row) & ALL_PROHIBITED_FIELDS
        if prohibited_in_row:
            bad_field = sorted(prohibited_in_row)[0]
            raise DatasetAdapterIntegrityError(
                "prohibited_field_present",
                f"Prohibited feature '{bad_field}' detected in raw source record at row {row_idx}.",
            )
        for k, v in row.items():
            if isinstance(v, str):
                v_lower = v.lower()
                for token in PROHIBITED_REAL_DATA_DISGUISE_TOKENS:
                    if token in v_lower:
                        raise DatasetAdapterIntegrityError(
                            "disguised_or_contaminated_record",
                            f"Prohibited disguise or contamination token '{token}' detected in row {row_idx}, column '{k}'.",
                        )


def load_cleveland_source_records(
    source_path: Path,
    *,
    expected_sha256: str,
    panel: ResearchPanelContract,
    config: Any = CLEVELAND_DEFAULT_CONFIG,
) -> tuple[list[dict[str, Any]], list[int], ClevelandDataset]:
    """Load Cleveland processed.cleveland.data via read-only adapter and map to panel records."""
    if panel.panel_id == "da_a2_resting_labs_v1":
        raise DatasetAdapterIntegrityError(
            "extended_panel_blocked_before_fitting",
            "The 7-feature Cleveland resting+labs panel is registered but blocked pending authorized adapters.",
        )
    if panel.panel_id != "da_a2_resting_v1":
        raise DatasetAdapterIntegrityError("unsupported_cleveland_panel", f"Panel {panel.panel_id} not supported for Cleveland.")

    source_snapshot = _read_source_bytes_read_only(
        source_path,
        expected_sha256=expected_sha256,
        expected_size_bytes=None,
    )
    dataset = _parse_processed_cleveland_bytes(source_snapshot.content, config=config)

    records: list[dict[str, Any]] = []
    labels: list[int] = [int(val) for val in dataset.y]

    for i in range(dataset.row_count):
        row_feat: dict[str, Any] = {}
        units: dict[str, str] = {}
        missing_reasons: dict[str, str] = {}

        for j, col_name in enumerate(dataset.feature_names):
            val = float(dataset.X[i, j])
            if math.isnan(val):
                row_feat[col_name] = None
                missing_reasons[col_name] = "not_measured"
            else:
                f_spec = panel.field_map[col_name]
                if f_spec.role == "categorical":
                    row_feat[col_name] = int(val)
                else:
                    row_feat[col_name] = float(val)
                if f_spec.unit is not None:
                    units[f_spec.name] = f_spec.unit

        rec = {
            "synthetic": False,
            "panel_id": panel.panel_id,
            "features": row_feat,
            "units": units,
            "missing_reasons": missing_reasons,
        }
        records.append(rec)

    _check_source_not_disguised_or_contaminated(
        [r["features"] for r in records], source_path
    )
    return records, labels, dataset


def load_uci412_source_records(
    source_path: Path,
    *,
    expected_sha256: str,
    panel: ResearchPanelContract,
    config: Uci412Config = UCI412_DEFAULT_CONFIG,
    dictionary: FeatureDictionary = UCI412_DEFAULT_DICTIONARY,
) -> tuple[list[dict[str, Any]], list[int], Uci412Dataset]:
    """Load UCI-412 workbook via read-only adapter and map to panel records."""
    if panel.panel_id == "da_a1_clinical_core_labs_v1":
        raise DatasetAdapterIntegrityError(
            "extended_panel_blocked_before_fitting",
            "The 23-feature UCI-412 clinical+core-labs panel is registered but blocked pending predictor-timing and governance approval.",
        )
    if panel.panel_id != "da_a1_basic_clinical_v1":
        raise DatasetAdapterIntegrityError("unsupported_uci412_panel", f"Panel {panel.panel_id} not supported for UCI-412.")

    snapshot, dataset = uci412_load_authorized_dataset(
        source_path,
        expected_sha256=expected_sha256,
        config=config,
        dictionary=dictionary,
    )

    records: list[dict[str, Any]] = []
    labels: list[int] = [int(val) for val in dataset.y]

    for i in range(dataset.row_count):
        row_feat: dict[str, Any] = {}
        units: dict[str, str] = {}
        missing_reasons: dict[str, str] = {}

        for j, col_name in enumerate(dataset.feature_names):
            val = float(dataset.X[i, j])
            f_spec = panel.field_map[col_name]
            if math.isnan(val):
                row_feat[col_name] = None
                missing_reasons[col_name] = "not_measured"
            else:
                if f_spec.role == "categorical":
                    row_feat[col_name] = int(val)
                else:
                    row_feat[col_name] = float(val)
                if f_spec.unit is not None:
                    units[f_spec.name] = f_spec.unit

        rec = {
            "synthetic": False,
            "panel_id": panel.panel_id,
            "features": row_feat,
            "units": units,
            "missing_reasons": missing_reasons,
        }
        records.append(rec)

    _check_source_not_disguised_or_contaminated(
        [r["features"] for r in records], source_path
    )
    return records, labels, dataset


def execute_authorized_research_run(
    *,
    source_path: Path,
    manifest_path: Path,
    panel_id: str,
    output_bundle_dir: Path,
    repo_root: Path = REPOSITORY_ROOT,
    training_config: ResearchTrainingConfig = ResearchTrainingConfig(),
    signing_key: bytes | None = None,
    allow_synthetic_test_manifest: bool = False,
) -> tuple[TrainedResearchRun, VerifiedBundleDescriptor]:
    """Execute authorized real-data research training and atomic bundle packaging.

    Enforces all AI-2 requirements:
    1. Isolated source-specific adapter for UCI-412 consultation or Cleveland resting.
    2. Reuses existing read-only parsers without code duplication.
    3. Verifies source hashes, row counts, dictionaries, and missingness semantics.
    4. Rejects angiography-derived, post-outcome, echo, or wearable variables.
    5. Enforces hash-bound locally protected authorization manifest.
    6. Keeps P-1/P-3 and D-047/D-048 boundaries intact.
    7. Runs locally on CPU without remote telemetry.
    8. Writes outputs only to explicitly authorized private, Git-ignored paths.
    9. Generates aggregate-only evaluation report and signed private model bundle.
    10. Reuses AI-1 training pipeline directly without divergent reimplementations.
    """
    if panel_id not in REGISTERED_PANELS:
        raise ClinicalInputValidationError("unregistered_panel", f"Panel '{panel_id}' is not registered.")
    panel = REGISTERED_PANELS[panel_id]

    if panel_id in BLOCKED_EXTENDED_PANELS:
        raise ClinicalInputValidationError(
            "extended_panel_blocked_before_fitting",
            f"Extended panel '{panel_id}' is blocked before fitting until authorized.",
        )

    # 1. Authorize manifest
    auth = parse_and_validate_research_authorization(
        manifest_path,
        expected_dataset_id=panel.dataset_id,
        expected_panel_id=panel_id,
        repo_root=repo_root,
        allow_synthetic_test_manifest=allow_synthetic_test_manifest,
    )

    # 2. Check source path containment and verify SHA-256 matches manifest
    if is_reparse_or_symlink(source_path):
        raise DatasetAdapterIntegrityError("source_symlink_rejected", "Source path cannot be a symlink or reparse point.")
    _check_path_git_ignored(source_path, repo_root)

    actual_source_sha, _ = sha256_file(source_path)
    actual_source_sha = actual_source_sha.lower()
    if actual_source_sha != auth.expected_source_sha256:
        raise DatasetAdapterIntegrityError(
            "source_hash_mismatch",
            f"Actual source SHA-256 '{actual_source_sha}' does not match authorization '{auth.expected_source_sha256}'.",
        )

    # 3. Verify output path containment and Git-ignore status
    _check_path_git_ignored(output_bundle_dir, repo_root)
    ensure_private_directory(output_bundle_dir.parent)

    # 4. Load source-specific records via narrow read-only adapter
    if auth.dataset_id == TRACK_A_UCI412_SOURCE_ID:
        records, labels, raw_dataset = load_uci412_source_records(
            source_path,
            expected_sha256=auth.expected_source_sha256,
            panel=panel,
        )
    elif auth.dataset_id == TRACK_B_CLEVELAND_SOURCE_ID:
        records, labels, raw_dataset = load_cleveland_source_records(
            source_path,
            expected_sha256=auth.expected_source_sha256,
            panel=panel,
        )
    else:
        raise DatasetAdapterIntegrityError("unsupported_dataset_id", f"Dataset '{auth.dataset_id}' not supported.")

    if len(records) != auth.expected_source_row_count:
        raise DatasetAdapterIntegrityError(
            "row_count_mismatch",
            f"Loaded {len(records)} rows; expected {auth.expected_source_row_count}.",
        )

    # 5. Run validate_cohort_records(..., require_synthetic=False) to enforce exact feature names, order, shape, and units
    X_val, y_val, _ = validate_cohort_records(
        records,
        labels,
        panel,
        require_synthetic=False,
    )

    # 6. Fit research model using the shared AI-1 training pipeline
    model_id = f"cai_real_{auth.dataset_id.lower()}_{panel.panel_id}"
    dev_cohort = f"real_{auth.dataset_id.lower()}_authorized"
    dev_dataset = f"{auth.dataset_id}:real_authorized"

    trained_run = _execute_shared_training_pipeline(
        X_val,
        y_val,
        panel,
        model_id=model_id,
        dev_cohort=dev_cohort,
        dev_dataset=dev_dataset,
        config=training_config,
        synthetic_only=False,  # Truthful real provenance mode!
    )

    # 7. Package atomic bundle with truthful real provenance mode
    active_key = signing_key if signing_key is not None else get_or_create_local_signing_key()
    auth_ctx_dict = {
        "governance_decision_id": auth.governance_decision_id,
        "dataset_id": auth.dataset_id,
        "panel_id": auth.panel_id,
        "experiment_type": auth.experiment_type,
        "source_relative_path": auth.source_relative_path,
        "expected_source_sha256": auth.expected_source_sha256,
        "expected_source_row_count": auth.expected_source_row_count,
        "authorized_by": auth.authorized_by,
        "authorized_date": auth.authorized_date,
        "signature_attestation": auth.signature_attestation,
        "pinned_commit_sha": auth.pinned_commit_sha,
        "protocol_sha256": auth.protocol_sha256,
        "plan_sha256": auth.plan_sha256,
        "dictionary_sha256": auth.dictionary_sha256,
    }

    verified_descriptor = package_research_bundle(
        trained_run,
        output_bundle_dir,
        signing_key=active_key,
        authorized_real_data=True,
        authorization_context=auth_ctx_dict,
    )

    return trained_run, verified_descriptor
