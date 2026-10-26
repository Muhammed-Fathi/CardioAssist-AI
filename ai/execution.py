"""Locally protected, auditable real-data execution infrastructure for AI-2.

This module bridges the validated read-only dataset adapters
(:mod:`research.uci412.adapter` and :mod:`research.experiments.data_adapter`)
to the reusable AI research pipeline (:mod:`ai.training`, :mod:`ai.panels`,
:mod:`ai.packaging`, and :mod:`ai.inference`) under strict, human-ratified,
hash-bound authorization manifests.

Operating Principles & Safeguards:
1. Established Governance Validators Reused:
   Reuses and binds the strict governance, hash, and provenance validators from
   :mod:`research.experiments.safety` (D-047) and :mod:`research.uci412.safety` (M3a).
   No arbitrary authorization status, placeholder signer, or unapproved commit can authorize fitting.
2. Mandatory File Existence and Digest Equality:
   Every frozen protocol, registered plan, and feature dictionary file MUST exist,
   be safe to read without symlinks or traversal, and match the exact ratified SHA-256 digest.
   No conditional checks silently skip hash comparisons.
3. No Generic Boolean Authorization Bypasses:
   Removed all boolean override flags (such as allow_synthetic_test_manifest or
   allow_authorized_real_data). Real model packaging and SHAP background generation
   strictly require an authentic, internally validated :class:`AuthorizedExecutionContext`.
4. Frozen Model Configuration Binding:
   Model hyperparameters, nested-CV folds (outer 4, inner 3), repeat seeds, candidate
   families, simplicity tolerances, and negative controls are bound strictly to the
   frozen registered research plans. Arbitrary custom configurations are rejected.
5. Windows Local Execution & Private Artifact Storage:
   Real runs execute only in local workstation environments (enforcing Win32 NTFS DACLs
   on Windows or private 0700/0600 POSIX permissions) and store artifacts strictly in
   private, Git-ignored locations (e.g., ``data/experiments/`` or ``data/uci412-experiments/``).
   Zero patient-level records or unredacted features escape into logs, tracebacks, or Git-tracked paths.
6. Research-Only Claims & Honest Scope:
   Every output is tagged ``INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED``. Gate PT (P-3)
   remains CLOSED. No clinical diagnostic claims, supervisor sign-offs, or external
   validation assertions are made.
"""
from __future__ import annotations

import dataclasses

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
    AuthorizedExecutionContext,
    AuthorizedExecutionContext as ResearchAuthorizationContext,
    generate_execution_verification_token,
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
    ALLOWED_MODEL_FAMILIES as CLEVELAND_ALLOWED_FAMILIES,
    ALLOWED_OPERATIONS as CLEVELAND_ALLOWED_OPERATIONS,
    FORBIDDEN_OPERATIONS as CLEVELAND_FORBIDDEN_OPERATIONS,
    REPOSITORY_ROOT,
    ExperimentConfig,
)
from research.experiments.data_adapter import (
    ClevelandDataset,
    _parse_processed_cleveland_bytes,
    _read_source_bytes_read_only,
    sha256_bytes as cleveland_sha256_bytes,
)
from research.experiments.safety import (
    OUTPUT_ROOT_RELATIVE_PATH as CLEVELAND_OUTPUT_ROOT_RELATIVE_PATH,
    validate_d047_authorization,
    enforce_local_windows_runtime as cleveland_enforce_local_windows_runtime,
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
    DICTIONARY_SCHEMA_VERSION as UCI412_DICT_SCHEMA_VERSION,
    M3A_AUTHORIZATION_COMMENT,
    M3A_AUTHORIZATION_STATUS,
    M3A_AUTHORIZING_MAINTAINER,
    M3A_LOCAL_SIGNATURE_ATTESTATION,
    M3A_PROTOCOL_AMENDMENT_ID,
    OUTPUT_ROOT_RELATIVE_PATH as UCI412_OUTPUT_ROOT_RELATIVE_PATH,
    REPORT_BANNER as UCI412_REPORT_BANNER,
    ALLOWED_MODEL_FAMILIES as UCI412_ALLOWED_FAMILIES,
    ALLOWED_OPERATIONS as UCI412_ALLOWED_OPERATIONS,
    FORBIDDEN_OPERATIONS as UCI412_FORBIDDEN_OPERATIONS,
    TARGET_COLUMN as UCI412_TARGET_COLUMN,
    Uci412Config,
)
from research.uci412.feature_schema import FeatureDictionary
from research.uci412.safety import (
    validate_m3a_authorization,
    enforce_local_windows_runtime as uci412_enforce_local_windows_runtime,
)
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


AMENDMENT_RATIFICATION_COMMENT: str = "RATIFY-AI2-OPERATIONAL-SCOPE-EXPANSION"
AMENDMENT_RATIFICATION_STATUS: str = "RATIFIED_BY_PROJECT_MAINTAINER"

# Trusted Maintainer Ratification Registry for Operational Scope Amendments.
# Each ratified operational amendment record must independently bind:
# - amendment_id: Unique amendment identifier
# - governance_pr_number: Approved governance pull request number
# - governance_merge_commit_sha: Verified 40-hex merge commit SHA in local Git history
# - approved_code_revision: Verified 40-hex executing revision SHA
# - approved_dataset_id: Pinned cohort dataset ID
# - approved_panel_id: Pinned registered panel ID
# - frozen_source_sha256: 64-hex SHA-256 of the frozen source data
# - frozen_protocol_sha256: 64-hex SHA-256 of the frozen research protocol
# - amendment_document_relative_path: Relative repository path to amendment document
# - frozen_amendment_document_sha256: 64-hex SHA-256 of the approved amendment document
# - approved_operations: Tuple of authorized operations (e.g. persistent_model_packaging)
# - ratified_by: Named project maintainer attesting to ratification
# - ratification_comment_exact: Exact maintainer ratification statement
# - protected_output_root: Restricted Git-ignored output directory root
#
# IMPORTANT: Gate PT (P-3) remains closed. Neither D-047 nor M3a grants persistent model
# packaging or patient-derived SHAP persistence for real patient data. Until a separate
# operational amendment is formally ratified by the project maintainer and recorded here,
# this registry contains NO ratified amendments, ensuring these operations remain disabled.
RATIFIED_OPERATIONAL_SCOPE_AMENDMENTS: dict[str, dict[str, Any]] = {}


def validate_operation_scope_amendment(
    amendment: Mapping[str, Any] | None,
    *,
    dataset_id: str,
    panel_id: str,
    source_sha256: str,
    protocol_sha256: str,
    current_git_commit: str,
    repo_root: Path,
) -> tuple[bool, bool]:
    """Validate a separate, human-ratified operational scope amendment against trusted approval evidence.

    Enforces that persistent real model artifact packaging and patient-derived
    SHAP backgrounds are NEVER enabled by caller-supplied boolean flags,
    in-process HMAC tokens, older D-047/M3a training authorizations alone, or
    self-declared unratified manifest documents.

    Requires independent approval evidence and Git repository verification:
    - Verifies amendment is bound to an independently ratified maintainer approval record.
    - Verifies all scope parameters (PR, merge commit, code revision, dataset, panel,
      source SHA-256, protocol SHA-256, amendment doc path, amendment doc SHA-256,
      signer, and comment) match the trusted ratification record, not merely manifest claims.
    - Verifies the referenced governance merge commit exists in trusted local Git history.
    - Verifies the governance commit is an ancestor of the executing code revision.
    - Verifies the exact frozen amendment document exists at that commit in Git.
    - Verifies that the amendment document's SHA-256 exactly matches the approved record.
    - Rejects nonexistent, unratified, or fabricated PR/merge evidence.

    Returns:
        (packaging_authorized: bool, patient_shap_authorized: bool)
    """
    if amendment is None:
        return False, False

    if not isinstance(amendment, Mapping):
        raise ExecutionAuthorizationError(
            "malformed_operation_amendment",
            "The operation_scope_amendment must be a structured mapping.",
            field="operation_scope_amendment",
        )

    amendment_id = str(amendment.get("amendment_id", "")).strip()
    if not amendment_id:
        raise ExecutionAuthorizationError(
            "missing_amendment_id",
            "Operation amendment must specify an amendment_id.",
            field="operation_scope_amendment.amendment_id",
        )

    # 1. Independent trusted approval binding:
    # Must match an independently ratified operational scope amendment record
    # approved by the project maintainer. Caller-supplied manifest values alone cannot authorize operations.
    if amendment_id not in RATIFIED_OPERATIONAL_SCOPE_AMENDMENTS:
        raise ExecutionAuthorizationError(
            "unratified_operational_amendment_id",
            f"Operation amendment '{amendment_id}' is not present in the trusted maintainer ratification registry. "
            "Persistent packaging and patient-derived SHAP persistence remain disabled.",
            field="operation_scope_amendment.amendment_id",
        )

    trusted_record = RATIFIED_OPERATIONAL_SCOPE_AMENDMENTS[amendment_id]

    # Verify that the trusted record independently binds required scope
    trusted_pr = trusted_record.get("governance_pr_number")
    trusted_merge = str(trusted_record.get("governance_merge_commit_sha", "")).strip().lower()
    trusted_code_rev = str(trusted_record.get("approved_code_revision", "")).strip().lower()
    trusted_dataset = str(trusted_record.get("approved_dataset_id", "")).strip()
    trusted_panel = str(trusted_record.get("approved_panel_id", "")).strip()
    trusted_source_sha = str(trusted_record.get("frozen_source_sha256", "")).strip().lower()
    trusted_proto_sha = str(trusted_record.get("frozen_protocol_sha256", "")).strip().lower()
    trusted_doc_rel = str(trusted_record.get("amendment_document_relative_path", "")).strip()
    trusted_doc_sha = str(trusted_record.get("frozen_amendment_document_sha256", "")).strip().lower()
    trusted_signer = str(trusted_record.get("ratified_by", "")).strip()
    trusted_comment = str(trusted_record.get("ratification_comment_exact", "")).strip()
    trusted_ops = tuple(trusted_record.get("approved_operations", ()))

    # Compare manifest claims against trusted record
    if amendment.get("governance_pr_number") != trusted_pr:
        raise ExecutionAuthorizationError(
            "amendment_pr_mismatch",
            f"Manifest PR number '{amendment.get('governance_pr_number')}' does not match trusted record '{trusted_pr}'.",
            field="operation_scope_amendment.governance_pr_number",
        )
    if str(amendment.get("governance_merge_commit_sha", "")).strip().lower() != trusted_merge:
        raise ExecutionAuthorizationError(
            "amendment_merge_commit_mismatch",
            f"Manifest merge commit does not match trusted record '{trusted_merge}'.",
            field="operation_scope_amendment.governance_merge_commit_sha",
        )
    if str(amendment.get("approved_code_revision", "")).strip().lower() != trusted_code_rev:
        raise ExecutionAuthorizationError(
            "amendment_code_revision_mismatch",
            f"Manifest approved_code_revision does not match trusted record '{trusted_code_rev}'.",
            field="operation_scope_amendment.approved_code_revision",
        )
    if str(amendment.get("approved_dataset_id", "")).strip() != trusted_dataset or dataset_id != trusted_dataset:
        raise ExecutionAuthorizationError(
            "amendment_dataset_mismatch",
            f"Cohort/dataset '{dataset_id}' does not match trusted ratified scope '{trusted_dataset}'.",
            field="operation_scope_amendment.approved_dataset_id",
        )
    if str(amendment.get("approved_panel_id", "")).strip() != trusted_panel or panel_id != trusted_panel:
        raise ExecutionAuthorizationError(
            "amendment_panel_mismatch",
            f"Panel '{panel_id}' does not match trusted ratified scope '{trusted_panel}'.",
            field="operation_scope_amendment.approved_panel_id",
        )
    if str(amendment.get("frozen_source_sha256", "")).strip().lower() != trusted_source_sha or source_sha256.lower() != trusted_source_sha:
        raise ExecutionAuthorizationError(
            "amendment_source_sha_mismatch",
            "Source SHA-256 does not match trusted ratified scope.",
            field="operation_scope_amendment.frozen_source_sha256",
        )
    if str(amendment.get("frozen_protocol_sha256", "")).strip().lower() != trusted_proto_sha or protocol_sha256.lower() != trusted_proto_sha:
        raise ExecutionAuthorizationError(
            "amendment_protocol_sha_mismatch",
            "Protocol SHA-256 does not match trusted ratified scope.",
            field="operation_scope_amendment.frozen_protocol_sha256",
        )
    if str(amendment.get("amendment_document_relative_path", "")).strip() != trusted_doc_rel:
        raise ExecutionAuthorizationError(
            "amendment_document_path_mismatch",
            f"Amendment document path does not match trusted record '{trusted_doc_rel}'.",
            field="operation_scope_amendment.amendment_document_relative_path",
        )
    if str(amendment.get("frozen_amendment_document_sha256", "")).strip().lower() != trusted_doc_sha:
        raise ExecutionAuthorizationError(
            "amendment_document_hash_mismatch",
            f"Amendment document hash does not match trusted record '{trusted_doc_sha}'.",
            field="operation_scope_amendment.frozen_amendment_document_sha256",
        )
    if str(amendment.get("ratified_by", "")).strip() != trusted_signer:
        raise ExecutionAuthorizationError(
            "unratified_amendment_signer",
            f"Signer does not match trusted record '{trusted_signer}'.",
            field="operation_scope_amendment.ratified_by",
        )
    if str(amendment.get("ratification_comment_exact", "")).strip() != trusted_comment:
        raise ExecutionAuthorizationError(
            "unratified_amendment_comment",
            f"Ratification comment does not match trusted record '{trusted_comment}'.",
            field="operation_scope_amendment.ratification_comment_exact",
        )
    if tuple(amendment.get("approved_operations", ())) != trusted_ops:
        raise ExecutionAuthorizationError(
            "amendment_operations_mismatch",
            "Approved operations list does not match trusted ratified operations.",
            field="operation_scope_amendment.approved_operations",
        )

    # 2. Reject template / unratified status
    status = str(amendment.get("ratification_status", "")).strip()
    if status != AMENDMENT_RATIFICATION_STATUS:
        raise ExecutionAuthorizationError(
            "unratified_operation_amendment",
            f"Operation amendment status '{status}' is not ratified by project maintainer.",
            field="operation_scope_amendment.ratification_status",
        )

    # 3. Enforce supervisor approval guard: Gate PT P-3 remains closed!
    if amendment.get("supervisor_signoff_claimed") is not False:
        raise ExecutionAuthorizationError(
            "supervisor_approval_claimed_prohibited",
            "Supervisor sign-off cannot be claimed; Gate PT P-3 remains CLOSED.",
            field="operation_scope_amendment.supervisor_signoff_claimed",
        )

    # 4. Check human attestation
    attest = str(amendment.get("human_attestation", "")).strip()
    if "GATE_PT_P3_CLOSED" not in attest or "HUMAN_RATIFIED" not in attest:
        raise ExecutionAuthorizationError(
            "invalid_amendment_attestation",
            "Operational amendment human attestation statement is invalid or altered.",
            field="operation_scope_amendment.human_attestation",
        )

    # 5. Independent Git verification of the governance merge commit:
    # 5a. Merge commit must exist in local Git repository
    cat_check = subprocess.run(
        ["git", "cat-file", "-e", f"{trusted_merge}^{{commit}}"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if cat_check.returncode != 0:
        raise ExecutionAuthorizationError(
            "amendment_commit_not_found_in_git",
            f"The operational amendment governance commit '{trusted_merge}' is not present in local Git history.",
            field="operation_scope_amendment.governance_merge_commit_sha",
        )

    # 5b. Merge commit must be an ancestor of the executing code commit
    ancestor_check = subprocess.run(
        ["git", "merge-base", "--is-ancestor", trusted_merge, current_git_commit],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if ancestor_check.returncode != 0:
        raise ExecutionAuthorizationError(
            "amendment_commit_not_ancestor",
            f"The operational amendment governance commit '{trusted_merge}' is not an ancestor of current code commit '{current_git_commit}'.",
            field="operation_scope_amendment.governance_merge_commit_sha",
        )

    # 5c. Amendment document must exist at the pinned governance commit and match hash
    doc_git = subprocess.run(
        ["git", "show", f"{trusted_merge}:{trusted_doc_rel}"],
        cwd=str(repo_root),
        capture_output=True,
        check=False,
    )
    if doc_git.returncode != 0:
        raise ExecutionAuthorizationError(
            "amendment_document_absent_from_git_commit",
            f"Amendment document '{trusted_doc_rel}' is absent from governance commit '{trusted_merge}'.",
            field="operation_scope_amendment.amendment_document_relative_path",
        )

    actual_doc_sha = hashlib.sha256(doc_git.stdout).hexdigest().lower()
    if actual_doc_sha != trusted_doc_sha:
        raise ExecutionAuthorizationError(
            "amendment_document_hash_mismatch",
            f"Amendment document at commit '{trusted_merge}' has SHA-256 '{actual_doc_sha}', expected '{trusted_doc_sha}'.",
            field="operation_scope_amendment.frozen_amendment_document_sha256",
        )

    packaging_auth = "persistent_model_packaging" in trusted_ops
    shap_auth = "patient_level_shap_background" in trusted_ops

    return packaging_auth, shap_auth


def get_approved_training_config(dataset_id: str) -> ResearchTrainingConfig:
    """Return the frozen, approved ResearchTrainingConfig corresponding to the ratified research protocol."""
    if dataset_id == TRACK_B_CLEVELAND_SOURCE_ID:
        return ResearchTrainingConfig(
            protocol_id="CAI-D047-CLEVELAND-EXPLORATORY-V1",
            model_version="0.2.0",
            outer_folds=CLEVELAND_DEFAULT_CONFIG.outer_folds,
            inner_folds=CLEVELAND_DEFAULT_CONFIG.inner_folds,
            repeat_seeds=CLEVELAND_DEFAULT_CONFIG.outer_repeat_seeds,
            shuffle_control_seeds=CLEVELAND_DEFAULT_CONFIG.negative_control_seeds,
            auc_simplicity_tolerance=CLEVELAND_DEFAULT_CONFIG.auc_equivalence_tolerance,
            lr_c_grid=CLEVELAND_DEFAULT_CONFIG.logistic_c_values,
            rf_max_depths=CLEVELAND_DEFAULT_CONFIG.rf_max_depths,
            rf_min_samples_leaf=CLEVELAND_DEFAULT_CONFIG.rf_min_samples_leaf,
            rf_n_estimators=CLEVELAND_DEFAULT_CONFIG.rf_n_estimators,
            exploratory_threshold=CLEVELAND_DEFAULT_CONFIG.threshold,
        )
    elif dataset_id == TRACK_A_UCI412_SOURCE_ID:
        return ResearchTrainingConfig(
            protocol_id="CAI-M3A-UCI412-BENCHMARK-V1",
            model_version="0.2.0",
            outer_folds=UCI412_DEFAULT_CONFIG.outer_folds,
            inner_folds=UCI412_DEFAULT_CONFIG.inner_folds,
            repeat_seeds=UCI412_DEFAULT_CONFIG.outer_repeat_seeds,
            shuffle_control_seeds=UCI412_DEFAULT_CONFIG.negative_control_seeds,
            auc_simplicity_tolerance=UCI412_DEFAULT_CONFIG.auc_equivalence_tolerance,
            lr_c_grid=UCI412_DEFAULT_CONFIG.logistic_c_values,
            rf_max_depths=UCI412_DEFAULT_CONFIG.rf_max_depths,
            rf_min_samples_leaf=UCI412_DEFAULT_CONFIG.rf_min_samples_leaf,
            rf_n_estimators=UCI412_DEFAULT_CONFIG.rf_n_estimators,
            exploratory_threshold=UCI412_DEFAULT_CONFIG.threshold,
        )
    else:
        raise ExecutionAuthorizationError("unsupported_dataset_id", f"No approved training protocol for dataset '{dataset_id}'.")


def assert_training_config_approved(
    dataset_id: str,
    training_config: ResearchTrainingConfig | None,
) -> ResearchTrainingConfig:
    """Verify that training_config exactly matches the frozen approved protocol without deviation.

    Enforces mandatory dataclass equality across every field (CV folds, repeat seeds,
    negative control seeds, shuffle_max_allowed_auroc, bootstrap_resamples,
    shap_max_background_samples, exploratory_threshold, hyperparameter grids, etc.).
    """
    approved = get_approved_training_config(dataset_id)
    if training_config is None:
        return approved

    # Compare every field in ResearchTrainingConfig dataclass
    mismatches = []
    for f in dataclasses.fields(ResearchTrainingConfig):
        val_test = getattr(training_config, f.name)
        val_approved = getattr(approved, f.name)
        if isinstance(val_test, (list, tuple)) or isinstance(val_approved, (list, tuple)):
            if tuple(val_test) != tuple(val_approved):
                mismatches.append(f"{f.name} ({val_test} != {val_approved})")
        else:
            if val_test != val_approved:
                mismatches.append(f"{f.name} ({val_test} != {val_approved})")

    if mismatches:
        raise ExecutionAuthorizationError(
            "unapproved_training_configuration_deviation",
            f"Training configuration differs from approved protocol for '{dataset_id}': {', '.join(mismatches)}. "
            "Custom configurations, reduced test profiles, and hyperparameter deviations are prohibited on real data "
            "without a separately authorized protocol amendment.",
        )
    return approved


def parse_and_validate_research_authorization(
    manifest_path: Path,
    *,
    expected_dataset_id: str,
    expected_panel_id: str,
    repo_root: Path = REPOSITORY_ROOT,
    current_git_commit: str | None = None,
) -> AuthorizedExecutionContext:
    """Strictly validate a local research authorization manifest using established governance validators.

    Fails closed on:
    - Missing files, symlinks, or reparse points.
    - Template / unratified files (e.g. status containing PROPOSED, PENDING, or NOT_AUTHORIZED).
    - Arbitrary or unapproved authorization status.
    - Mismatched human ratification evidence (signer, attestation, PR/decision metadata).
    - Missing or unreadable protocol, plan, or dictionary files on disk.
    - Mismatched protocol, plan, or dictionary digests compared against frozen on-disk files.
    - Unapproved dataset or panel IDs (extended panels fail before fitting).
    - Missing or placeholder signer, commit SHA, or hash bindings.
    - Storage inside unignored repository directories.
    - Supervisor approval claims (Gate PT P-3 remains CLOSED).
    """
    if is_reparse_or_symlink(manifest_path):
        raise ExecutionAuthorizationError("symlink_rejected", "Authorization manifest cannot be a symlink or reparse point.")

    _check_path_git_ignored(manifest_path, repo_root)
    manifest = _read_json_no_dups(manifest_path)

    # 1. Reject template or unratified status immediately
    auth_status = str(manifest.get("authorization_status", "")).strip()
    is_template = (
        "TEMPLATE" in auth_status.upper()
        or "PROPOSED" in auth_status.upper()
        or "NOT_AUTHORIZED" in auth_status.upper()
        or "PENDING" in auth_status.upper()
    )
    if is_template:
        raise ExecutionAuthorizationError(
            "unauthorized_template_manifest",
            f"Authorization manifest has status '{auth_status}', which does NOT authorize execution.",
            field="authorization_status",
        )

    # 2. Enforce supervisor approval guard: Gate PT P-3 must remain closed!
    if manifest.get("supervisor_signoff_claimed") is not False:
        raise ExecutionAuthorizationError(
            "supervisor_approval_claimed_prohibited",
            "Supervisor sign-off cannot be claimed; Gate PT P-3 remains CLOSED.",
            field="supervisor_signoff_claimed",
        )

    exp_type = str(manifest.get("experiment_type", "")).strip()
    if exp_type != MANDATORY_OUTPUT_BANNER:
        raise ExecutionAuthorizationError(
            "invalid_experiment_type",
            f"Expected experiment_type '{MANDATORY_OUTPUT_BANNER}', got '{exp_type}'.",
            field="experiment_type",
        )

    dataset_id = str(manifest.get("dataset_id", "")).strip()
    if dataset_id != expected_dataset_id:
        raise ExecutionAuthorizationError(
            "dataset_id_mismatch",
            f"Manifest dataset_id '{dataset_id}' does not match expected '{expected_dataset_id}'.",
            field="dataset_id",
        )

    panel_id = str(manifest.get("panel_id") or manifest.get("panel_schema_id") or "").strip()
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

    # 3. Determine current git commit for ancestry and commit check
    commit = current_git_commit
    if commit is None:
        try:
            head_proc = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
            )
            if head_proc.returncode == 0 and GIT_SHA_RE.fullmatch(head_proc.stdout.strip()):
                commit = head_proc.stdout.strip().lower()
        except Exception:
            commit = None

    if commit is None:
        # Fallback to pinned commit if Git checkout query is unavailable
        commit = str(manifest.get("pinned_protocol_git_commit_sha") or manifest.get("pinned_protocol_commit_sha") or "").strip().lower()

    # 4. Faithfully reuse established governance validators
    gov_details: dict[str, Any] = {}
    if dataset_id == TRACK_B_CLEVELAND_SOURCE_ID:
        # Mandatory file existence checks
        protocol_path = (repo_root / CLEVELAND_PROTOCOL_PATH) if (repo_root / CLEVELAND_PROTOCOL_PATH).exists() else (REPOSITORY_ROOT / CLEVELAND_PROTOCOL_PATH)
        plan_path = CLEVELAND_PLAN_PATH if CLEVELAND_PLAN_PATH.exists() else (REPOSITORY_ROOT / "research/experiments/cleveland_d047_exploratory_plan.v0.1.json")
        if not protocol_path.is_file():
            raise ExecutionAuthorizationError("protocol_file_missing", f"Required protocol file missing: {protocol_path}")
        if not plan_path.is_file():
            raise ExecutionAuthorizationError("plan_file_missing", f"Required experiment plan file missing: {plan_path}")

        actual_proto_sha, _ = sha256_file(protocol_path)
        actual_plan_sha, _ = sha256_file(plan_path)

        # Call established validate_d047_authorization
        try:
            gov_details = validate_d047_authorization(
                manifest,
                repo_root=repo_root,
                current_git_commit=commit,
                config=CLEVELAND_DEFAULT_CONFIG,
            )
        except Exception as exc:
            raise ExecutionAuthorizationError("d047_governance_validation_failed", str(exc)) from exc

        # Mandatory digest equality check against on-disk files
        proto_sha = str(manifest.get("frozen_protocol_sha256", "")).lower()
        plan_sha = str(manifest.get("frozen_experiment_plan_sha256", "")).lower()
        if proto_sha != actual_proto_sha.lower():
            raise ExecutionAuthorizationError(
                "protocol_hash_mismatch",
                f"Protocol hash '{proto_sha}' does not match actual on-disk file digest '{actual_proto_sha}'.",
            )
        if plan_sha != actual_plan_sha.lower():
            raise ExecutionAuthorizationError(
                "plan_hash_mismatch",
                f"Plan hash '{plan_sha}' does not match actual on-disk file digest '{actual_plan_sha}'.",
            )

        source_rel = str(manifest.get("allowed_original_relative_file", "")).strip()
        if source_rel != "data/raw/uci-45/processed.cleveland.data":
            raise ExecutionAuthorizationError(
                "unauthorized_source_file_path",
                f"Source relative path '{source_rel}' does not match approved Cleveland path.",
            )

        signer = str(manifest.get("local_signer", "")).strip()
        signed_at = str(manifest.get("local_signed_at_iso8601", "")).strip()
        attestation = str(manifest.get("local_signature_attestation", "")).strip()
        source_sha = str(manifest.get("expected_sha256_from_protected_provenance_manifest") or manifest.get("expected_source_sha256", "")).strip().lower()
        row_count = int(manifest.get("authorized_source_row_count", 0))

        pinned_commit = str(manifest.get("pinned_protocol_git_commit_sha", "")).lower()
        allowed_ops = tuple(manifest.get("allowed_operations_if_approved", ()))
        forbidden_ops = tuple(manifest.get("forbidden_operations", ()))
        out_root = str(manifest.get("protected_outputs_relative_root", "data/experiments"))

        # Explicitly validate separate human-ratified operation scope amendment
        # (Reject caller-supplied boolean flags or unratified additions)
        op_amendment = manifest.get("operation_scope_amendment")
        packaging_auth, shap_auth = validate_operation_scope_amendment(
            op_amendment,
            dataset_id=dataset_id,
            panel_id=panel_id,
            source_sha256=source_sha,
            protocol_sha256=proto_sha,
            current_git_commit=commit,
            repo_root=repo_root,
        )

        token = generate_execution_verification_token(
            decision_id="D-047",
            dataset_id=dataset_id,
            panel_id=panel_id,
            experiment_type=exp_type,
            source_rel_path=source_rel,
            source_sha256=source_sha,
            row_count=row_count,
            pinned_commit=pinned_commit,
            protocol_sha=proto_sha,
            plan_sha=plan_sha,
            dictionary_sha=None,
            signer=signer,
            signed_at=signed_at,
            attestation=attestation,
            allowed_operations=allowed_ops,
            forbidden_operations=forbidden_ops,
            protected_output_root=out_root,
            model_packaging_authorized=packaging_auth,
            patient_shap_authorized=shap_auth,
        )
        return AuthorizedExecutionContext(
            governance_decision_id="D-047",
            dataset_id=dataset_id,
            panel_id=panel_id,
            experiment_type=exp_type,
            source_relative_path=source_rel,
            expected_source_sha256=source_sha,
            expected_source_row_count=row_count,
            authorized_by=signer,
            authorized_date=signed_at,
            signature_attestation=attestation,
            pinned_commit_sha=pinned_commit,
            protocol_sha256=proto_sha,
            plan_sha256=plan_sha,
            dictionary_sha256=None,
            allowed_operations=allowed_ops,
            forbidden_operations=forbidden_ops,
            protected_output_root=out_root,
            governance_details=gov_details,
            verification_token=token,
            model_packaging_authorized=packaging_auth,
            patient_shap_authorized=shap_auth,
        )

    elif dataset_id == TRACK_A_UCI412_SOURCE_ID:
        # Mandatory file existence checks
        proposal_path = (repo_root / UCI412_PROPOSAL_PATH) if (repo_root / UCI412_PROPOSAL_PATH).exists() else (REPOSITORY_ROOT / UCI412_PROPOSAL_PATH)
        plan_path = UCI412_PLAN_PATH if UCI412_PLAN_PATH.exists() else (REPOSITORY_ROOT / "research/uci412/uci412_cad_research_plan.v0.1.json")
        dict_path = UCI412_DICT_PATH if UCI412_DICT_PATH.exists() else (REPOSITORY_ROOT / "research/uci412/schemas/uci412_feature_dictionary.v1.json")
        if not proposal_path.is_file():
            raise ExecutionAuthorizationError("proposal_file_missing", f"Required proposal file missing: {proposal_path}")
        if not plan_path.is_file():
            raise ExecutionAuthorizationError("plan_file_missing", f"Required research plan file missing: {plan_path}")
        if not dict_path.is_file():
            raise ExecutionAuthorizationError("dictionary_file_missing", f"Required feature dictionary file missing: {dict_path}")

        actual_prop_sha, _ = sha256_file(proposal_path)
        actual_plan_sha, _ = sha256_file(plan_path)
        actual_dict_sha, _ = sha256_file(dict_path)

        # Call established validate_m3a_authorization
        try:
            gov_details = validate_m3a_authorization(
                manifest,
                repo_root=repo_root,
                current_git_commit=commit,
                config=UCI412_DEFAULT_CONFIG,
            )
        except Exception as exc:
            raise ExecutionAuthorizationError("m3a_governance_validation_failed", str(exc)) from exc

        # Mandatory digest equality checks
        prop_sha = str(manifest.get("frozen_authorization_proposal_sha256", "")).lower()
        plan_sha = str(manifest.get("frozen_research_plan_sha256", "")).lower()
        dict_sha = str(manifest.get("frozen_feature_dictionary_sha256", "")).lower()
        if prop_sha != actual_prop_sha.lower():
            raise ExecutionAuthorizationError(
                "proposal_hash_mismatch",
                f"Proposal hash '{prop_sha}' does not match actual on-disk file digest '{actual_prop_sha}'.",
            )
        if plan_sha != actual_plan_sha.lower():
            raise ExecutionAuthorizationError(
                "plan_hash_mismatch",
                f"Plan hash '{plan_sha}' does not match actual on-disk file digest '{actual_plan_sha}'.",
            )
        if dict_sha != actual_dict_sha.lower():
            raise ExecutionAuthorizationError(
                "dictionary_hash_mismatch",
                f"Dictionary hash '{dict_sha}' does not match actual on-disk file digest '{actual_dict_sha}'.",
            )

        source_rel = str(manifest.get("allowed_original_relative_file", "")).strip()
        if source_rel != "data/raw/uci-412/Z-Alizadeh sani dataset.xlsx":
            raise ExecutionAuthorizationError(
                "unauthorized_source_file_path",
                f"Source relative path '{source_rel}' does not match approved UCI-412 path.",
            )

        signer = str(manifest.get("local_signer", "")).strip()
        signed_at = str(manifest.get("local_signed_at_iso8601", "")).strip()
        attestation = str(manifest.get("local_signature_attestation", "")).strip()
        source_sha = str(manifest.get("expected_sha256_from_protected_provenance_manifest") or manifest.get("expected_source_sha256", "")).strip().lower()
        row_count = int(manifest.get("authorized_source_row_count", 0))

        pinned_commit = str(manifest.get("pinned_protocol_commit_sha", "")).lower()
        allowed_ops = tuple(manifest.get("allowed_operations_if_approved", ()))
        forbidden_ops = tuple(manifest.get("forbidden_operations", ()))
        out_root = str(manifest.get("protected_outputs_relative_root", "data/uci412-experiments"))

        # Explicitly validate separate human-ratified operation scope amendment
        # (Reject caller-supplied boolean flags or unratified additions)
        op_amendment = manifest.get("operation_scope_amendment")
        packaging_auth, shap_auth = validate_operation_scope_amendment(
            op_amendment,
            dataset_id=dataset_id,
            panel_id=panel_id,
            source_sha256=source_sha,
            protocol_sha256=actual_prop_sha,
            current_git_commit=commit,
            repo_root=repo_root,
        )

        token = generate_execution_verification_token(
            decision_id="M3A-UCI412-INTERNAL-RESEARCH-PROPOSAL",
            dataset_id=dataset_id,
            panel_id=panel_id,
            experiment_type=exp_type,
            source_rel_path=source_rel,
            source_sha256=source_sha,
            row_count=row_count,
            pinned_commit=pinned_commit,
            protocol_sha=prop_sha,
            plan_sha=plan_sha,
            dictionary_sha=dict_sha,
            signer=signer,
            signed_at=signed_at,
            attestation=attestation,
            allowed_operations=allowed_ops,
            forbidden_operations=forbidden_ops,
            protected_output_root=out_root,
            model_packaging_authorized=packaging_auth,
            patient_shap_authorized=shap_auth,
        )
        return AuthorizedExecutionContext(
            governance_decision_id="M3A-UCI412-INTERNAL-RESEARCH-PROPOSAL",
            dataset_id=dataset_id,
            panel_id=panel_id,
            experiment_type=exp_type,
            source_relative_path=source_rel,
            expected_source_sha256=source_sha,
            expected_source_row_count=row_count,
            authorized_by=signer,
            authorized_date=signed_at,
            signature_attestation=attestation,
            pinned_commit_sha=pinned_commit,
            protocol_sha256=prop_sha,
            plan_sha256=plan_sha,
            dictionary_sha256=dict_sha,
            allowed_operations=allowed_ops,
            forbidden_operations=forbidden_ops,
            protected_output_root=out_root,
            governance_details=gov_details,
            verification_token=token,
            model_packaging_authorized=packaging_auth,
            patient_shap_authorized=shap_auth,
        )

    raise ExecutionAuthorizationError("unsupported_dataset_id", f"Dataset '{dataset_id}' has no established governance validator.")


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
    training_config: ResearchTrainingConfig | None = None,
    signing_key: bytes | None = None,
    current_git_commit: str | None = None,
) -> tuple[TrainedResearchRun, VerifiedBundleDescriptor]:
    """Execute authorized real-data research training and atomic bundle packaging.

    Enforces all AI-2 requirements:
    1. Isolated source-specific adapter for UCI-412 consultation or Cleveland resting.
    2. Reuses existing read-only parsers without code duplication.
    3. Verifies source hashes, row counts, dictionaries, and missingness semantics.
    4. Rejects angiography-derived, post-outcome, echo, or wearable variables.
    5. Reuses established D-047/M3a governance validators fail-closed.
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

    # 0. Enforce Windows-local fixed-drive and CPU-only runtime guards BEFORE source reading or fitting.
    # Production execution NEVER skips runtime guards regardless of environment variables or protocol names.
    if panel.dataset_id == TRACK_B_CLEVELAND_SOURCE_ID:
        cleveland_enforce_local_windows_runtime(repo_root=repo_root)
    else:
        uci412_enforce_local_windows_runtime(repo_root=repo_root)

    # 1. Authorize manifest through established governance validators
    auth = parse_and_validate_research_authorization(
        manifest_path,
        expected_dataset_id=panel.dataset_id,
        expected_panel_id=panel_id,
        repo_root=repo_root,
        current_git_commit=current_git_commit,
    )

    # 2. Check canonical source path equality
    expected_canonical_source = repo_root / auth.source_relative_path
    if source_path.resolve() != expected_canonical_source.resolve():
        raise ExecutionAuthorizationError(
            "source_path_mismatch",
            f"Actual source path '{source_path}' does not resolve to the authorized canonical path '{expected_canonical_source}'.",
        )

    # 3. Check source path containment, non-symlink status and verify SHA-256 matches manifest
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

    # 4. Verify output path containment and Git-ignore status
    if is_reparse_or_symlink(output_bundle_dir):
        raise ExecutionAuthorizationError("symlink_output_rejected", "Output directory cannot be a symlink or reparse point.")
    _check_path_git_ignored(output_bundle_dir, repo_root)

    # Output root must be strictly contained under the approved research output root
    # (e.g. data/experiments for Cleveland or data/uci412-experiments for UCI-412)
    expected_rel_root = CLEVELAND_OUTPUT_ROOT_RELATIVE_PATH if auth.dataset_id == TRACK_B_CLEVELAND_SOURCE_ID else UCI412_OUTPUT_ROOT_RELATIVE_PATH
    expected_root_path = (repo_root / expected_rel_root).resolve()

    # Check path-component-aware containment
    resolved_output = output_bundle_dir.resolve()
    try:
        rel_to_authorized = resolved_output.relative_to(expected_root_path)
    except ValueError:
        raise ExecutionAuthorizationError(
            "unapproved_output_location",
            f"Output directory '{resolved_output}' is not contained within the approved research output root '{expected_root_path}'.",
        )

    # Check for symlink/reparse anywhere in parent hierarchy down to output_bundle_dir
    curr = resolved_output.parent
    while curr != expected_root_path.parent and curr != curr.parent:
        if is_reparse_or_symlink(curr):
            raise ExecutionAuthorizationError("symlink_in_output_path", f"Path component '{curr}' is a symlink or reparse point.")
        curr = curr.parent

    ensure_private_directory(output_bundle_dir.parent)

    # 5. Bind training configuration to frozen authorized research protocol without deviation
    effective_training_config = assert_training_config_approved(auth.dataset_id, training_config)

    # 6. Load source-specific records via narrow read-only adapter
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

    # 7. Run validate_cohort_records(..., require_synthetic=False) to enforce exact feature names, order, shape, and units
    X_val, y_val, _ = validate_cohort_records(
        records,
        labels,
        panel,
        require_synthetic=False,
    )

    # 8. Fit research model using the shared AI-1 training pipeline
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
        config=effective_training_config,
        synthetic_only=False,  # Truthful real provenance mode!
        authorization_context=auth,
    )

    # 9. Package atomic bundle with truthful real provenance mode
    active_key = signing_key if signing_key is not None else get_or_create_local_signing_key()

    verified_descriptor = package_research_bundle(
        trained_run,
        output_bundle_dir,
        signing_key=active_key,
        authorization_context=auth,
    )

    return trained_run, verified_descriptor
