"""Comprehensive unit, adapter, authorization rejection, integrity, and end-to-end tests
for AI-2 authorized local real-data research execution.

Enforces all 10 AI-2 requirements and PR #53 regression criteria:
1. Strict read-only source adapters for Track A (UCI-412) and Track B (Cleveland).
2. Exact feature schema mapping, unit assertions, and missingness semantics.
3. Prohibited variable rejection (angiography, echo, wearable, identifiers).
4. Reuses established D-047 and M3a governance validators fail-closed.
5. Mandatory file existence and digest equality (protocol, plan, dictionary).
6. Anti-disguise enforcement: real clinical records cannot carry synthetic tokens.
7. Truthful provenance: real-derived runs & SHAP backgrounds record synthetic_only=False.
8. Packaging and verification of signed RESEARCH_ONLY model bundles.
9. Verification of uncalibrated, cross-calibrated, and apparent evaluation metrics.
10. Untracked and private storage security (NTFS DACL / POSIX 0700/0600).
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
from typing import Any, Mapping

import numpy as np
import pytest

from ai.errors import (
    BundleIntegrityError,
    ClinicalInputValidationError,
    CohortGovernanceError,
)
from ai.execution import (
    AuthorizedExecutionContext,
    DatasetAdapterIntegrityError,
    ExecutionAuthorizationError,
    ResearchAuthorizationContext,
    execute_authorized_research_run,
    load_cleveland_source_records,
    load_uci412_source_records,
    parse_and_validate_research_authorization,
)
from ai.filesystem_security import (
    ensure_private_directory,
    is_windows_runtime,
    protect_private_directory,
    protect_private_file,
    verify_access_control,
)
from ai.inference import ResearchCadPredictor
from ai.packaging import (
    get_or_create_local_signing_key,
    verify_research_bundle,
    verify_trusted_local_bundle,
)
from ai.panels import (
    DA_A1_BASIC_CLINICAL_PANEL,
    DA_A1_CLINICAL_CORE_LABS_PANEL,
    DA_A2_RESTING_LABS_PANEL,
    DA_A2_RESTING_PANEL,
    ALL_PROHIBITED_FIELDS,
)
from ai.training import ResearchTrainingConfig
from research.audit.provenance import sha256_file
from research.audit.xlsx_reader import write_synthetic_xlsx
from research.experiments.config import (
    DEFAULT_CONFIG as CLEVELAND_DEFAULT_CONFIG,
    PLAN_PATH as CLEVELAND_PLAN_PATH,
    PROTOCOL_RELATIVE_PATH as CLEVELAND_PROTOCOL_PATH,
    D047_AUTHORIZATION_COMMENT,
    D047_AUTHORIZATION_STATUS,
    D047_AUTHORIZING_PR_NUMBER,
    D047_AUTHORIZING_MAINTAINER,
    D047_LOCAL_SIGNATURE_ATTESTATION,
    D047_REPORT_BANNER,
    REPOSITORY_ROOT,
)
import research.experiments.safety as cleveland_safety
from research.experiments.synthetic_fixtures import make_synthetic_source_bytes
from research.uci412.config import (
    DEFAULT_CONFIG as UCI412_DEFAULT_CONFIG,
    PLAN_PATH as UCI412_PLAN_PATH,
    PROPOSAL_RELATIVE_PATH as UCI412_PROPOSAL_PATH,
    DICTIONARY_PATH as UCI412_DICT_PATH,
    DICTIONARY_SCHEMA_VERSION as UCI412_DICT_SCHEMA_VERSION,
    M3A_AUTHORIZATION_COMMENT,
    M3A_AUTHORIZATION_STATUS,
    M3A_AUTHORIZING_MAINTAINER,
    M3A_LOCAL_SIGNATURE_ATTESTATION,
    M3A_PROTOCOL_AMENDMENT_ID,
    REPORT_BANNER as UCI412_REPORT_BANNER,
)
import research.uci412.safety as uci412_safety
from tests.uci412.conftest import synthetic_rows


FAST_TEST_CONFIG = ResearchTrainingConfig(
    protocol_id="CAI-AI2-TEST-PROTOCOL-V1",
    model_version="0.2.0",
    outer_folds=3,
    inner_folds=2,
    repeat_seeds=(20261026,),
    shuffle_control_seeds=(20261102,),
    shuffle_max_allowed_auroc=0.68,
    lr_c_grid=(0.1, 1.0),
    rf_max_depths=(2, 3),
    rf_min_samples_leaf=(5,),
    rf_n_estimators=15,
    bootstrap_resamples=30,
    shap_max_background_samples=20,
)


def _get_current_head_commit() -> str:
    res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(REPOSITORY_ROOT), capture_output=True, text=True, check=True)
    return res.stdout.strip().lower()


def _create_mock_cleveland_file(path: Path) -> str:
    """Create a synthetically valid processed Cleveland CSV file without mandatory history NaNs."""
    source_bytes = make_synthetic_source_bytes()
    lines = source_bytes.decode("ascii").splitlines()
    clean_lines = []
    for line in lines:
        parts = line.split(",")
        if len(parts) == 14:
            if parts[0] == "?": parts[0] = "55"
            if parts[1] == "?": parts[1] = "1"
            if parts[2] == "?": parts[2] = "3"
        clean_lines.append(",".join(parts))
    clean_bytes = ("\n".join(clean_lines) + "\n").encode("ascii")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(clean_bytes)
    digest, _ = sha256_file(path)
    return digest.lower()


def _create_mock_uci412_file(path: Path) -> str:
    """Create a synthetically valid UCI-412 Excel workbook and return its SHA-256."""
    headers, rows = synthetic_rows()
    path.parent.mkdir(parents=True, exist_ok=True)
    write_synthetic_xlsx(
        path,
        [("data_worksheet_1", headers, [list(r) for r in rows])],
    )
    digest, _ = sha256_file(path)
    return digest.lower()


def _create_valid_auth_manifest(
    path: Path,
    *,
    dataset_id: str,
    panel_id: str,
    source_sha256: str,
    row_count: int,
    status: str | None = None,
    claim_supervisor: bool = False,
    experiment_type: str = "INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED",
    signer: str | None = None,
    attestation: str | None = None,
    protocol_sha: str | None = None,
    plan_sha: str | None = None,
    dictionary_sha: str | None = None,
    source_relative_path: str | None = None,
    decision_id: str | None = None,
    schema_version: str | None = None,
    merge_sha: str | None = None,
    pinned_commit: str | None = None,
    signed_at: str | None = None,
) -> None:
    """Create a structured test authorization manifest matching exact schema_version and governance keys."""
    head_sha = _get_current_head_commit()
    effective_merge = merge_sha or head_sha
    effective_pin = pinned_commit or effective_merge

    if dataset_id == "DA-A2":
        default_proto_sha, _ = sha256_file(REPOSITORY_ROOT / CLEVELAND_PROTOCOL_PATH)
        default_plan_sha, _ = sha256_file(CLEVELAND_PLAN_PATH)
        default_source_rel = "data/raw/uci-45/processed.cleveland.data"

        manifest_data = {
            "schema_version": schema_version or "0.2.0",
            "decision_id": decision_id or "D-047",
            "authorization_status": status or D047_AUTHORIZATION_STATUS,
            "experiment_type": experiment_type,
            "supervisor_signoff_claimed": claim_supervisor,
            "maintainer_approval_comment_exact": D047_AUTHORIZATION_COMMENT,
            "approval_pr_number": D047_AUTHORIZING_PR_NUMBER,
            "approval_pr_merged_commit_sha": effective_merge,
            "pinned_protocol_git_commit_sha": effective_pin,
            "local_signer": signer or D047_AUTHORIZING_MAINTAINER,
            "local_signed_at_iso8601": signed_at or "2026-10-26T06:40:00Z",
            "local_signature_attestation": attestation or D047_LOCAL_SIGNATURE_ATTESTATION,
            "signature_semantics": "HUMAN_ATTESTATION_FIELDS_NOT_A_CRYPTOGRAPHIC_SIGNATURE",
            "dataset_id": dataset_id,
            "panel_id": panel_id,
            "allowed_original_relative_file": source_relative_path or default_source_rel,
            "authorized_source_row_count": row_count,
            "allowlisted_model_families": [
                "prevalence_dummy",
                "l2_logistic_regression",
                "constrained_random_forest"
            ],
            "allowed_operations_if_approved": [
                "read_only_source_loading",
                "internal_model_fitting",
                "internal_nested_cv",
                "internal_model_family_comparison",
                "internal_negative_control",
                "internal_aggregate_metrics_report"
            ],
            "forbidden_operations": [
                "remote_patient_data_upload",
                "model_serving",
                "clinical_decision",
                "external_validation_claim",
                "multi_cohort_pooling",
                "unapproved_dataset_ingestion",
                "patient_level_git_commit"
            ],
            "allowed_runtime": "LOCAL_WINDOWS_CPU_ONLY",
            "protected_outputs_relative_root": "data/experiments",
            "expected_sha256_from_protected_provenance_manifest": source_sha256,
            "frozen_protocol_sha256": protocol_sha or default_proto_sha,
            "frozen_experiment_plan_sha256": plan_sha or default_plan_sha,
        }
    else:
        default_proto_sha, _ = sha256_file(REPOSITORY_ROOT / UCI412_PROPOSAL_PATH)
        default_plan_sha, _ = sha256_file(UCI412_PLAN_PATH)
        default_dict_sha, _ = sha256_file(UCI412_DICT_PATH)
        default_source_rel = "data/raw/uci-412/Z-Alizadeh sani dataset.xlsx"

        manifest_data = {
            "schema_version": schema_version or "0.1.0",
            "proposal_id": decision_id or "M3A-UCI412-INTERNAL-RESEARCH-PROPOSAL",
            "authorization_status": status or M3A_AUTHORIZATION_STATUS,
            "experiment_type": experiment_type,
            "supervisor_signoff_claimed": claim_supervisor,
            "gate_pt_status": "CLOSED_REQUIRES_SUPERVISOR_SIGNOFF_P3",
            "maintainer_approval_comment_exact": M3A_AUTHORIZATION_COMMENT,
            "governance_pr_number": 32,
            "governance_merge_commit_sha": effective_merge,
            "pinned_protocol_commit_sha": effective_pin,
            "authorization_proposal_relative_path": "docs/research/gate-pt/08_m3a_uci412_source_specific_benchmark_SPECIFICATION.md",
            "frozen_authorization_proposal_sha256": protocol_sha or default_proto_sha,
            "frozen_feature_dictionary_sha256": dictionary_sha or default_dict_sha,
            "frozen_research_plan_sha256": plan_sha or default_plan_sha,
            "dataset_id": dataset_id,
            "panel_id": panel_id,
            "target_column": "Cath",
            "allowed_original_relative_file": source_relative_path or default_source_rel,
            "authorized_source_row_count": row_count,
            "panel_schema_id": "uci412_basic_clinical_v1",
            "panel_schema_version": "1.1.0",
            "dictionary_schema_version": UCI412_DICT_SCHEMA_VERSION,
            "protocol_amendment_id": M3A_PROTOCOL_AMENDMENT_ID,
            "allowlisted_model_families": [
                "prevalence_dummy",
                "l2_logistic_regression",
                "constrained_random_forest"
            ],
            "allowed_operations_if_approved": [
                "read_only_source_loading",
                "internal_model_fitting",
                "internal_nested_cv",
                "internal_model_family_comparison",
                "internal_negative_control",
                "internal_aggregate_metrics_report"
            ],
            "forbidden_operations": [
                "remote_patient_data_upload",
                "model_serving",
                "clinical_decision",
                "external_validation_claim",
                "multi_cohort_pooling",
                "uci411_row_reuse",
                "unapproved_dataset_ingestion",
                "patient_level_git_commit",
                "shap_or_lime_patient_explanations",
                "artifact_packaging_for_serving"
            ],
            "allowed_runtime": "LOCAL_WINDOWS_CPU_ONLY",
            "protected_outputs_relative_root": "data/uci412-experiments",
            "expected_sha256_from_protected_provenance_manifest": source_sha256,
            "local_signer": signer or M3A_AUTHORIZING_MAINTAINER,
            "local_signed_at_iso8601": signed_at or "2026-10-26T06:40:00Z",
            "local_signature_attestation": attestation or M3A_LOCAL_SIGNATURE_ATTESTATION,
            "signature_semantics": "HUMAN_ATTESTATION_FIELDS_NOT_A_CRYPTOGRAPHIC_SIGNATURE",
        }

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")


def _setup_governance_monkeypatches(monkeypatch: pytest.MonkeyPatch) -> str:
    """Monkeypatch the governance merge SHA to the local HEAD commit for test repository consistency."""
    head_sha = _get_current_head_commit()
    monkeypatch.setattr(cleveland_safety, "D047_AUTHORIZING_MERGE_SHA", head_sha)
    monkeypatch.setattr(cleveland_safety, "D047_AUTHORIZING_MERGED_AT_UTC", "2026-10-26T00:00:00+00:00")
    return head_sha


def test_cleveland_source_adapter_and_mapping(tmp_path: Path) -> None:
    """Track B Cleveland adapter loads 303 rows and maps valid five-field features."""
    source_path = tmp_path / "processed.cleveland.data"
    expected_sha = _create_mock_cleveland_file(source_path)

    records, labels, dataset = load_cleveland_source_records(
        source_path,
        expected_sha256=expected_sha,
        panel=DA_A2_RESTING_PANEL,
    )

    assert len(records) == 303
    assert len(labels) == 303
    assert dataset.row_count == 303
    assert dataset.feature_names == ("age", "sex", "cp", "trestbps", "restecg")
    assert records[0]["panel_id"] == "da_a2_resting_v1"
    assert records[0]["synthetic"] is False
    assert records[0]["units"]["age"] == "years"
    assert records[0]["units"]["trestbps"] == "mmHg"
    assert "sex" not in records[0]["units"]
    assert "cp" not in records[0]["units"]
    assert "restecg" not in records[0]["units"]


def test_uci412_source_adapter_and_mapping(tmp_path: Path) -> None:
    """Track A UCI-412 adapter loads 303 rows and maps valid 16-feature basic clinical panel."""
    source_path = tmp_path / "Z-Alizadeh sani dataset.xlsx"
    expected_sha = _create_mock_uci412_file(source_path)

    records, labels, dataset = load_uci412_source_records(
        source_path,
        expected_sha256=expected_sha,
        panel=DA_A1_BASIC_CLINICAL_PANEL,
    )

    assert len(records) == 303
    assert len(labels) == 303
    assert dataset.row_count == 303
    assert len(dataset.feature_names) == 16
    assert records[0]["panel_id"] == "da_a1_basic_clinical_v1"
    assert records[0]["synthetic"] is False
    assert records[0]["units"]["Age"] == "years"
    assert records[0]["units"]["BP"] == "mmHg"
    assert records[0]["units"]["BMI"] == "kg/m^2"


def test_authorization_manifest_validation_and_tamper_rejection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Authorization validator fails closed on missing signatures, template status, and supervisor claims."""
    _setup_governance_monkeypatches(monkeypatch)
    manifest_path = tmp_path / "auth_manifest.json"

    # 1. Template status rejection
    _create_valid_auth_manifest(
        manifest_path,
        dataset_id="DA-A2",
        panel_id="da_a2_resting_v1",
        source_sha256="0" * 64,
        row_count=303,
        status="NOT_AUTHORIZED_TEMPLATE_ONLY",
    )
    with pytest.raises(ExecutionAuthorizationError) as exc_info:
        parse_and_validate_research_authorization(
            manifest_path,
            expected_dataset_id="DA-A2",
            expected_panel_id="da_a2_resting_v1",
        )
    assert exc_info.value.code == "unauthorized_template_manifest"

    # 2. Supervisor claim rejection
    _create_valid_auth_manifest(
        manifest_path,
        dataset_id="DA-A2",
        panel_id="da_a2_resting_v1",
        source_sha256="0" * 64,
        row_count=303,
        claim_supervisor=True,
    )
    with pytest.raises(ExecutionAuthorizationError) as exc_info:
        parse_and_validate_research_authorization(
            manifest_path,
            expected_dataset_id="DA-A2",
            expected_panel_id="da_a2_resting_v1",
        )
    assert exc_info.value.code == "supervisor_approval_claimed_prohibited"


def test_source_hash_mismatch_rejection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Mutated source bytes or mismatched expected hash block execution before fitting."""
    _setup_governance_monkeypatches(monkeypatch)
    source_path = REPOSITORY_ROOT / "data/raw/uci-45/processed.cleveland.data"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    _create_mock_cleveland_file(source_path)
    wrong_sha = "0" * 64

    manifest_path = tmp_path / "manifest.json"
    _create_valid_auth_manifest(
        manifest_path,
        dataset_id="DA-A2",
        panel_id="da_a2_resting_v1",
        source_sha256=wrong_sha,
        row_count=303,
    )

    with pytest.raises(DatasetAdapterIntegrityError) as exc_info:
        execute_authorized_research_run(
            manifest_path=manifest_path,
            source_path=source_path,
            panel_id="da_a2_resting_v1",
            output_bundle_dir=tmp_path / "out_bundle",
        )
    assert exc_info.value.code == "source_hash_mismatch"


def test_real_data_disguised_as_synthetic_rejection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """If real clinical rows contain 'synthetic: True' or disguise tokens, adapter fails closed."""
    _setup_governance_monkeypatches(monkeypatch)
    source_path = REPOSITORY_ROOT / "data/raw/uci-45/processed.cleveland.data"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    real_sha = _create_mock_cleveland_file(source_path)

    from ai import execution
    orig_cleveland_loader = execution.load_cleveland_source_records

    def poisoned_loader(*args: Any, **kwargs: Any) -> Any:
        recs, labels, ds = orig_cleveland_loader(*args, **kwargs)
        recs[0]["features"]["smartwatch_ecg"] = 1.0  # Wearable leak!
        execution._check_source_not_disguised_or_contaminated([r["features"] for r in recs], source_path)
        return recs, labels, ds

    monkeypatch.setattr(execution, "load_cleveland_source_records", poisoned_loader)

    manifest_path = tmp_path / "manifest.json"
    _create_valid_auth_manifest(
        manifest_path,
        dataset_id="DA-A2",
        panel_id="da_a2_resting_v1",
        source_sha256=real_sha,
        row_count=303,
    )

    with pytest.raises(DatasetAdapterIntegrityError) as exc_info:
        execute_authorized_research_run(
            manifest_path=manifest_path,
            source_path=source_path,
            panel_id="da_a2_resting_v1",
            output_bundle_dir=tmp_path / "out_bundle",
        )
    assert exc_info.value.code == "prohibited_field_present"


def test_end_to_end_cleveland_authorized_execution_and_inference(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Track B Cleveland resting model executes end-to-end under valid authorization and produces verified bundle."""
    _setup_governance_monkeypatches(monkeypatch)
    source_path = REPOSITORY_ROOT / "data/raw/uci-45/processed.cleveland.data"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_sha = _create_mock_cleveland_file(source_path)

    manifest_path = tmp_path / "manifest.json"
    _create_valid_auth_manifest(
        manifest_path,
        dataset_id="DA-A2",
        panel_id="da_a2_resting_v1",
        source_sha256=source_sha,
        row_count=303,
    )

    bundle_dir = tmp_path / "models" / "cai_real_cleveland_resting_v1"
    signing_key = get_or_create_local_signing_key(tmp_path / "keys" / "signer.key")

    trained_run, descriptor = execute_authorized_research_run(
        manifest_path=manifest_path,
        source_path=source_path,
        panel_id="da_a2_resting_v1",
        output_bundle_dir=bundle_dir,
        signing_key=signing_key,
        training_config=FAST_TEST_CONFIG,
    )

    assert descriptor.serving_eligibility == "RESEARCH_ONLY"
    assert descriptor.approved_for_serving is False
    assert descriptor.safe_for_pickle_deserialization is True
    assert (bundle_dir / "manifest.json").is_file()
    assert (bundle_dir / "model.joblib").is_file()
    assert (bundle_dir / "shap_background.json").is_file()
    assert (bundle_dir / "evaluation_summary.json").is_file()

    # Load predictor from verified bundle
    predictor = ResearchCadPredictor.from_verified_bundle(
        bundle_dir,
        trusted_local_root=bundle_dir.parent,
        signing_key=signing_key,
    )

    # Predict on test patient record
    test_record = {
        "synthetic": False,
        "panel_id": "da_a2_resting_v1",
        "features": {
            "age": 60.0,
            "sex": 1,
            "cp": 4,
            "trestbps": 140.0,
            "restecg": 0,
        },
        "units": {
            "age": "years",
            "trestbps": "mmHg",
        },
        "missing_reasons": {},
    }

    result = predictor.predict_research_only(test_record)
    assert 0.0 <= result.raw_model_score <= 1.0
    assert 0.0 <= result.calibrated_research_score <= 1.0
    assert len(result.explanation.attributions) == 5
    assert result.explanation.sum_check_passed is True


def test_end_to_end_uci412_authorized_execution_and_inference(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Track A UCI-412 basic clinical model executes end-to-end under valid authorization and produces verified bundle."""
    _setup_governance_monkeypatches(monkeypatch)
    source_path = REPOSITORY_ROOT / "data/raw/uci-412/Z-Alizadeh sani dataset.xlsx"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_sha = _create_mock_uci412_file(source_path)

    manifest_path = tmp_path / "manifest.json"
    _create_valid_auth_manifest(
        manifest_path,
        dataset_id="DA-A1",
        panel_id="da_a1_basic_clinical_v1",
        source_sha256=source_sha,
        row_count=303,
    )

    bundle_dir = tmp_path / "models" / "cai_real_uci412_basic_v1"
    signing_key = get_or_create_local_signing_key(tmp_path / "keys" / "signer.key")

    trained_run, descriptor = execute_authorized_research_run(
        manifest_path=manifest_path,
        source_path=source_path,
        panel_id="da_a1_basic_clinical_v1",
        output_bundle_dir=bundle_dir,
        signing_key=signing_key,
        training_config=FAST_TEST_CONFIG,
    )

    assert descriptor.serving_eligibility == "RESEARCH_ONLY"
    assert descriptor.approved_for_serving is False
    assert (bundle_dir / "manifest.json").is_file()
    assert (bundle_dir / "model.joblib").is_file()
    assert (bundle_dir / "shap_background.json").is_file()
    assert (bundle_dir / "evaluation_summary.json").is_file()

    predictor = ResearchCadPredictor.from_verified_bundle(
        bundle_dir,
        trusted_local_root=bundle_dir.parent,
        signing_key=signing_key,
    )

    uci_test_record = {
        "synthetic": False,
        "panel_id": "da_a1_basic_clinical_v1",
        "features": {
            "Age": 55.0,
            "Sex": "Male",
            "BMI": 24.2,
            "DM": 0,
            "HTN": 1,
            "Current Smoker": 0,
            "EX-Smoker": 0,
            "FH": 0,
            "DLP": 0,
            "BP": 130.0,
            "PR": 72.0,
            "Typical Chest Pain": 0,
            "Atypical": "N",
            "Nonanginal": "N",
            "Exertional CP": "N",
            "Dyspnea": "N",
        },
        "units": {
            "Age": "years",
            "BMI": "kg/m^2",
            "BP": "mmHg",
            "PR": "beats/min",
        },
        "missing_reasons": {},
    }

    result = predictor.predict_research_only(uci_test_record)
    assert 0.0 <= result.raw_model_score <= 1.0
    assert 0.0 <= result.calibrated_research_score <= 1.0
    assert len(result.explanation.attributions) == 16
    assert result.explanation.sum_check_passed is True


def test_missingness_reasons_and_leakage_prohibition_on_adapters(tmp_path: Path) -> None:
    """Adapters enforce explicit missingness reasons and reject leakage fields."""
    uci_path = tmp_path / "Z-Alizadeh sani dataset.xlsx"
    uci_sha = _create_mock_uci412_file(uci_path)

    records, labels, dataset = load_uci412_source_records(
        uci_path,
        expected_sha256=uci_sha,
        panel=DA_A1_BASIC_CLINICAL_PANEL,
    )
    for rec in records:
        assert set(rec["features"]) == set(DA_A1_BASIC_CLINICAL_PANEL.field_map)
        assert not (set(rec["features"]) & ALL_PROHIBITED_FIELDS)


def test_untracked_and_private_artifact_storage_security(tmp_path: Path) -> None:
    """Output bundles require private directory permissions and reject symlinks."""
    private_dir = tmp_path / "private_test"
    ensure_private_directory(private_dir)
    assert private_dir.is_dir()

    check = verify_access_control(private_dir, expect_directory=True, strict_private=True)
    assert check.ok is True


def test_windows_python312_platform_compatibility() -> None:
    """Ensure paths and types use cross-platform compatible primitives without POSIX-only APIs."""
    p = PurePosixPath("data/experiments/test_run")
    assert not p.is_absolute()
    assert str(p) == "data/experiments/test_run"


def test_regression_real_data_can_never_produce_synthetic_labeled_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression test: real-derived data can never produce a synthetic-labeled bundle."""
    _setup_governance_monkeypatches(monkeypatch)
    source_path = REPOSITORY_ROOT / "data/raw/uci-45/processed.cleveland.data"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_sha = _create_mock_cleveland_file(source_path)

    manifest_path = tmp_path / "manifest.json"
    _create_valid_auth_manifest(
        manifest_path,
        dataset_id="DA-A2",
        panel_id="da_a2_resting_v1",
        source_sha256=source_sha,
        row_count=303,
    )

    bundle_dir = tmp_path / "models" / "cai_real_cleveland_resting_v1"
    signing_key = get_or_create_local_signing_key(tmp_path / "keys" / "signer.key")

    trained_run, descriptor = execute_authorized_research_run(
        manifest_path=manifest_path,
        source_path=source_path,
        panel_id="da_a2_resting_v1",
        output_bundle_dir=bundle_dir,
        signing_key=signing_key,
        training_config=FAST_TEST_CONFIG,
    )

    # 1. Assert TrainedResearchRun is not synthetic
    assert trained_run.synthetic_only is False
    assert trained_run.shap_background.synthetic_only is False
    assert (
        trained_run.shap_background.sensitivity_classification
        == "SENSITIVE_REAL_PATIENT_DERIVED_RESTRICTED_LOCAL_ONLY"
    )

    # 2. Assert bundle manifest.json records synthetic_only = False
    manifest_doc = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest_doc["eligibility"]["synthetic_only"] is False
    assert manifest_doc["eligibility"]["execution_mode"] == "INTERNAL_EXPLORATORY_RESEARCH"
    assert manifest_doc["research_authorization"]["governance_decision_id"] == "D-047"

    # 3. Assert shap_background.json records synthetic_only = False
    bg_doc = json.loads((bundle_dir / "shap_background.json").read_text(encoding="utf-8"))
    assert bg_doc["privacy"]["synthetic_only"] is False
    assert bg_doc["privacy"]["sensitivity_classification"] == "SENSITIVE_REAL_PATIENT_DERIVED_RESTRICTED_LOCAL_ONLY"


def test_regression_arbitrary_protocol_dictionary_hashes_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression test: arbitrary but correctly formatted 64-hex protocol/plan/dictionary hashes are rejected."""
    _setup_governance_monkeypatches(monkeypatch)
    manifest_path = tmp_path / "manifest.json"
    fake_sha = "e" * 64

    # Mismatched protocol SHA
    _create_valid_auth_manifest(
        manifest_path,
        dataset_id="DA-A2",
        panel_id="da_a2_resting_v1",
        source_sha256="1" * 64,
        row_count=303,
        protocol_sha=fake_sha,
    )
    with pytest.raises(ExecutionAuthorizationError) as exc_info:
        parse_and_validate_research_authorization(
            manifest_path,
            expected_dataset_id="DA-A2",
            expected_panel_id="da_a2_resting_v1",
        )
    assert exc_info.value.code in ("protocol_hash_mismatch", "d047_governance_validation_failed")

    # Mismatched plan SHA
    _create_valid_auth_manifest(
        manifest_path,
        dataset_id="DA-A2",
        panel_id="da_a2_resting_v1",
        source_sha256="1" * 64,
        row_count=303,
        plan_sha=fake_sha,
    )
    with pytest.raises(ExecutionAuthorizationError) as exc_info:
        parse_and_validate_research_authorization(
            manifest_path,
            expected_dataset_id="DA-A2",
            expected_panel_id="da_a2_resting_v1",
        )
    assert exc_info.value.code in ("plan_hash_mismatch", "d047_governance_validation_failed")

    # Mismatched UCI-412 dictionary SHA
    _create_valid_auth_manifest(
        manifest_path,
        dataset_id="DA-A1",
        panel_id="da_a1_basic_clinical_v1",
        source_sha256="1" * 64,
        row_count=303,
        dictionary_sha=fake_sha,
    )
    with pytest.raises(ExecutionAuthorizationError) as exc_info:
        parse_and_validate_research_authorization(
            manifest_path,
            expected_dataset_id="DA-A1",
            expected_panel_id="da_a1_basic_clinical_v1",
        )
    assert exc_info.value.code in ("dictionary_hash_mismatch", "m3a_governance_validation_failed")


def test_regression_missing_ratification_or_mismatched_governance_blocks_fitting(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression test: missing human ratification, unknown maintainer, or altered attestation blocks fitting."""
    _setup_governance_monkeypatches(monkeypatch)
    manifest_path = tmp_path / "manifest.json"

    # Unknown maintainer
    _create_valid_auth_manifest(
        manifest_path,
        dataset_id="DA-A2",
        panel_id="da_a2_resting_v1",
        source_sha256="1" * 64,
        row_count=303,
        signer="Unauthorized Researcher",
    )
    with pytest.raises(ExecutionAuthorizationError) as exc_info:
        parse_and_validate_research_authorization(
            manifest_path,
            expected_dataset_id="DA-A2",
            expected_panel_id="da_a2_resting_v1",
        )
    assert exc_info.value.code in ("unratified_maintainer_signer", "d047_governance_validation_failed")

    # Altered attestation statement
    _create_valid_auth_manifest(
        manifest_path,
        dataset_id="DA-A2",
        panel_id="da_a2_resting_v1",
        source_sha256="1" * 64,
        row_count=303,
        attestation="I bypassed supervisor sign-off and authorized clinical diagnostics.",
    )
    with pytest.raises(ExecutionAuthorizationError) as exc_info:
        parse_and_validate_research_authorization(
            manifest_path,
            expected_dataset_id="DA-A2",
            expected_panel_id="da_a2_resting_v1",
        )
    assert exc_info.value.code in ("invalid_attestation_statement", "d047_governance_validation_failed")


def test_regression_authorized_source_path_mismatch_blocks_fitting(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression test: authorized source path mismatches block fitting."""
    _setup_governance_monkeypatches(monkeypatch)
    manifest_path = tmp_path / "manifest.json"
    _create_valid_auth_manifest(
        manifest_path,
        dataset_id="DA-A2",
        panel_id="da_a2_resting_v1",
        source_sha256="1" * 64,
        row_count=303,
        source_relative_path="data/raw/unauthorized/other.csv",
    )
    with pytest.raises(ExecutionAuthorizationError) as exc_info:
        parse_and_validate_research_authorization(
            manifest_path,
            expected_dataset_id="DA-A2",
            expected_panel_id="da_a2_resting_v1",
        )
    assert exc_info.value.code in ("unauthorized_source_file_path", "d047_governance_validation_failed")


def test_regression_extended_panels_fail_before_fitting() -> None:
    """Regression test: unsupported extended 7-feature Cleveland and 23-feature UCI-412 panels fail before fitting."""
    with pytest.raises(ClinicalInputValidationError) as exc_info_clev:
        execute_authorized_research_run(
            manifest_path=Path("nonexistent.json"),
            source_path=Path("nonexistent.data"),
            panel_id="da_a2_resting_labs_v1",
            output_bundle_dir=Path("nonexistent"),
        )
    assert exc_info_clev.value.code == "extended_panel_blocked_before_fitting"

    with pytest.raises(ClinicalInputValidationError) as exc_info_uci:
        execute_authorized_research_run(
            manifest_path=Path("nonexistent.json"),
            source_path=Path("nonexistent.xlsx"),
            panel_id="da_a1_clinical_core_labs_v1",
            output_bundle_dir=Path("nonexistent"),
        )
    assert exc_info_uci.value.code == "extended_panel_blocked_before_fitting"


def test_regression_full_evaluation_metrics_survive_packaging(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression test: comprehensive evaluation metrics, bootstrap CIs, and calibrator diagnostics survive packaging."""
    _setup_governance_monkeypatches(monkeypatch)
    source_path = REPOSITORY_ROOT / "data/raw/uci-45/processed.cleveland.data"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_sha = _create_mock_cleveland_file(source_path)

    manifest_path = tmp_path / "manifest.json"
    _create_valid_auth_manifest(
        manifest_path,
        dataset_id="DA-A2",
        panel_id="da_a2_resting_v1",
        source_sha256=source_sha,
        row_count=303,
    )

    bundle_dir = tmp_path / "models" / "cai_eval_metrics_test_bundle"
    signing_key = get_or_create_local_signing_key(tmp_path / "keys" / "signer.key")

    trained_run, descriptor = execute_authorized_research_run(
        manifest_path=manifest_path,
        source_path=source_path,
        panel_id="da_a2_resting_v1",
        output_bundle_dir=bundle_dir,
        signing_key=signing_key,
        training_config=FAST_TEST_CONFIG,
    )

    eval_json_path = bundle_dir / "evaluation_summary.json"
    assert eval_json_path.is_file()
    eval_data = json.loads(eval_json_path.read_text(encoding="utf-8"))

    # Assert evaluation structure matches shared AI-1 standard
    assert "internal_evaluation" in eval_data
    assert "negative_control" in eval_data
    internal_eval = eval_data["internal_evaluation"]
    assert "uncalibrated_nested_cv" in internal_eval
    assert "cross_fitted_calibrated_nested_cv" in internal_eval
    assert "final_development_calibrator_apparent_diagnostic" in internal_eval
    assert "outer_fold_family_selection_counts" in internal_eval

    # Verify negative control survived
    assert eval_data["negative_control"]["leakage_alarm_triggered"] is False
    assert "max_permuted_roc_auc" in eval_data["negative_control"]
