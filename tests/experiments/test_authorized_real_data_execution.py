"""Dedicated test suite for AI-2 real-data research execution infrastructure.

Covers:
1. Source-specific synthetic adapter tests (Cleveland resting 5-field and UCI-412 basic 16-field).
2. Dataset schema and target-label consistency tests.
3. Missingness, leakage, and prohibited-feature tests (echo, LAD/LCX/RCA, wearable fields).
4. Authorization denial tests (template status, unapproved panels, missing signatures, supervisor claims).
5. Source-hash and protocol-version mismatch rejections.
6. Real-data disguised-as-synthetic rejection and synthetic-flag corruption rejection.
7. Local artifact storage security and private Git-ignored boundary enforcement.
8. Reproducible synthetic end-to-end training and offline inference test with ResearchCadPredictor.
9. Windows Python 3.12 compatibility validation.
"""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any

import numpy as np
import pytest

from ai.errors import (
    BundleIntegrityError,
    ClinicalInputValidationError,
    CohortGovernanceError,
)
from ai.execution import (
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
from research.experiments.synthetic_fixtures import make_synthetic_source_bytes
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


def _create_mock_cleveland_file(path: Path) -> str:
    """Create a synthetically valid processed Cleveland CSV file without mandatory history NaNs."""
    # Generate without '?' in age, sex, cp (columns 0, 1, 2)
    source_bytes = make_synthetic_source_bytes()
    lines = source_bytes.decode('ascii').splitlines()
    clean_lines = []
    for line in lines:
        parts = line.split(',')
        if len(parts) == 14:
            if parts[0] == '?': parts[0] = '55'
            if parts[1] == '?': parts[1] = '1'
            if parts[2] == '?': parts[2] = '3'
        clean_lines.append(','.join(parts))
    clean_bytes = ('\n'.join(clean_lines) + '\n').encode('ascii')
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
    status: str = "AUTHORIZED_FOR_LOCAL_RESEARCH",
    claim_supervisor: bool = False,
    experiment_type: str = "INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED",
) -> None:
    """Create a structured test authorization manifest."""
    manifest_data = {
        "schema_version": "1.0.0",
        "governance_decision_id": "D-047" if dataset_id == "DA-A2" else "D-048",
        "authorization_status": status,
        "experiment_type": experiment_type,
        "supervisor_signoff_claimed": claim_supervisor,
        "dataset_id": dataset_id,
        "panel_id": panel_id,
        "local_signer": "Muhammed Fathi",
        "local_signed_at_iso8601": "2026-10-26T12:00:00Z",
        "local_signature_attestation": "I explicitly authorize local research execution under Gate PT Closed boundaries.",
        "pinned_protocol_git_commit_sha": "9ca3e2cf56a637aaa03c36b22471187a15d0612c",
        "frozen_protocol_sha256": "a" * 64,
        "frozen_experiment_plan_sha256": "b" * 64,
        "frozen_feature_dictionary_sha256": "c" * 64 if dataset_id == "DA-A1" else None,
        "allowed_original_relative_file": f"data/raw/{dataset_id.lower()}/source.dat",
        "expected_source_sha256": source_sha256,
        "authorized_source_row_count": row_count,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")


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
    assert set(labels).issubset({0, 1})
    assert "num" not in records[0]["features"]
    assert "ca" not in records[0]["features"]


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
    assert records[0]["panel_id"] == "da_a1_basic_clinical_v1"
    assert records[0]["synthetic"] is False
    assert set(labels).issubset({0, 1})
    assert "Cath" not in records[0]["features"]
    assert "EF-TTE" not in records[0]["features"]


def test_authorization_manifest_validation_and_tamper_rejection(tmp_path: Path) -> None:
    """Authorization validator fails closed on missing signatures, template status, and supervisor claims."""
    manifest_path = tmp_path / "auth_manifest.json"

    # 1. Template status rejection
    _create_valid_auth_manifest(
        manifest_path,
        dataset_id="DA-A2",
        panel_id="da_a2_resting_v1",
        source_sha256="0" * 64,
        row_count=303,
        status="PROPOSED_NOT_AUTHORIZING",
    )
    with pytest.raises(ExecutionAuthorizationError) as exc_info:
        parse_and_validate_research_authorization(
            manifest_path,
            expected_dataset_id="DA-A2",
            expected_panel_id="da_a2_resting_v1",
            repo_root=tmp_path,
        )
    assert exc_info.value.code == "unauthorized_template_manifest"

    # 2. Supervisor approval claim rejection (Gate PT P-3 remains CLOSED)
    _create_valid_auth_manifest(
        manifest_path,
        dataset_id="DA-A2",
        panel_id="da_a2_resting_v1",
        source_sha256="0" * 64,
        row_count=303,
        status="AUTHORIZED_FOR_LOCAL_RESEARCH",
        claim_supervisor=True,
    )
    with pytest.raises(ExecutionAuthorizationError) as exc_info:
        parse_and_validate_research_authorization(
            manifest_path,
            expected_dataset_id="DA-A2",
            expected_panel_id="da_a2_resting_v1",
            repo_root=tmp_path,
        )
    assert exc_info.value.code == "supervisor_approval_claimed_prohibited"

    # 3. Invalid panel for dataset
    _create_valid_auth_manifest(
        manifest_path,
        dataset_id="DA-A2",
        panel_id="da_a1_basic_clinical_v1",  # Cleveland cannot use UCI-412 panel
        source_sha256="0" * 64,
        row_count=303,
        status="AUTHORIZED_FOR_LOCAL_RESEARCH",
    )
    with pytest.raises(ExecutionAuthorizationError) as exc_info:
        parse_and_validate_research_authorization(
            manifest_path,
            expected_dataset_id="DA-A2",
            expected_panel_id="da_a1_basic_clinical_v1",
            repo_root=tmp_path,
        )
    assert exc_info.value.code == "unauthorized_panel_for_dataset"


def test_source_hash_mismatch_rejection(tmp_path: Path) -> None:
    """Mutated source bytes or mismatched expected hash block execution before fitting."""
    source_path = tmp_path / "processed.cleveland.data"
    real_sha = _create_mock_cleveland_file(source_path)
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
            repo_root=tmp_path,
        )
    assert exc_info.value.code == "source_hash_mismatch"


def test_real_data_disguised_as_synthetic_rejection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """If real clinical rows contain 'synthetic: True' or disguise tokens, adapter fails closed."""
    source_path = tmp_path / "processed.cleveland.data"
    real_sha = _create_mock_cleveland_file(source_path)

    # Test prohibited field injection
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
            repo_root=tmp_path,
        )
    assert exc_info.value.code == "prohibited_field_present"


def test_end_to_end_cleveland_authorized_execution_and_inference(tmp_path: Path) -> None:
    """Track B Cleveland resting model executes end-to-end under valid authorization and produces verified bundle."""
    source_path = tmp_path / "processed.cleveland.data"
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
        repo_root=tmp_path,
    )

    assert descriptor.serving_eligibility == "RESEARCH_ONLY"
    assert descriptor.approved_for_serving is False
    assert descriptor.safe_for_pickle_deserialization is True
    assert (bundle_dir / "manifest.json").is_file()
    assert (bundle_dir / "model.joblib").is_file()
    assert (bundle_dir / "preprocessing.json").is_file()
    assert (bundle_dir / "calibration.json").is_file()
    assert (bundle_dir / "shap_background.json").is_file()
    assert (bundle_dir / "evaluation_summary.json").is_file()
    assert (bundle_dir / "protocol.md").is_file()

    # Verify bundle security and permissions
    verified_trusted = verify_trusted_local_bundle(
        bundle_dir,
        trusted_local_root=bundle_dir.parent,
        signing_key=signing_key,
    )
    assert verified_trusted.bundle_dir == bundle_dir

    # Offline predictor inference with aligned SHAP and non-clinical limitations
    predictor = ResearchCadPredictor.from_verified_bundle(
        bundle_dir,
        trusted_local_root=bundle_dir.parent,
        signing_key=signing_key,
    )
    test_patient = {
        "synthetic": True,
        "panel_id": "da_a2_resting_v1",
        "features": {
            "age": 58.0,
            "sex": 1,
            "cp": 4,
            "trestbps": 135.0,
            "restecg": 0,
        },
        "units": {"age": "years", "trestbps": "mmHg"},
        "missing_reasons": {},
    }
    pred_res = predictor.predict_research_only(test_patient)
    assert 0.0 <= pred_res.raw_model_score <= 1.0
    assert 0.0 <= pred_res.calibrated_research_score <= 1.0
    assert pred_res.serving_eligibility == "RESEARCH_ONLY"
    assert pred_res.clinical_use_authorized is False
    assert len(pred_res.explanation.attributions) == 5
    assert "RESEARCH_ONLY" in pred_res.limitations[0]


def test_end_to_end_uci412_authorized_execution_and_inference(tmp_path: Path) -> None:
    """Track A UCI-412 basic clinical model executes end-to-end under valid authorization and produces verified bundle."""
    source_path = tmp_path / "Z-Alizadeh sani dataset.xlsx"
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
        repo_root=tmp_path,
    )

    assert descriptor.serving_eligibility == "RESEARCH_ONLY"
    assert descriptor.approved_for_serving is False
    assert (bundle_dir / "manifest.json").is_file()
    assert (bundle_dir / "model.joblib").is_file()
    assert (bundle_dir / "shap_background.json").is_file()

    predictor = ResearchCadPredictor.from_verified_bundle(
        bundle_dir,
        trusted_local_root=bundle_dir.parent,
        signing_key=signing_key,
    )
    test_patient = {
        "synthetic": True,
        "panel_id": "da_a1_basic_clinical_v1",
        "features": {
            "Age": 55.0,
            "Sex": "Male",
            "BMI": 26.5,
            "DM": 0,
            "HTN": 1,
            "Current Smoker": 0,
            "EX-Smoker": 0,
            "FH": 0,
            "DLP": "N",
            "BP": 130.0,
            "PR": 75.0,
            "Typical Chest Pain": 1,
            "Atypical": "N",
            "Nonanginal": "N",
            "Exertional CP": "N",
            "Dyspnea": "N",
        },
        "units": {"Age": "years", "BMI": "kg/m^2", "BP": "mmHg", "PR": "beats/min"},
        "missing_reasons": {},
    }
    pred_res = predictor.predict_research_only(test_patient)
    assert 0.0 <= pred_res.calibrated_research_score <= 1.0
    assert len(pred_res.explanation.attributions) == 16


def test_missingness_reasons_and_leakage_prohibition_on_adapters(tmp_path: Path) -> None:
    """Adapters enforce explicit missingness reasons and reject leakage fields (LAD/LCX/RCA/Cath/vessels)."""
    uci_path = tmp_path / "Z-Alizadeh sani dataset.xlsx"
    uci_sha = _create_mock_uci412_file(uci_path)

    records, labels, dataset = load_uci412_source_records(
        uci_path,
        expected_sha256=uci_sha,
        panel=DA_A1_BASIC_CLINICAL_PANEL,
    )
    for rec in records:
        assert rec["panel_id"] == "da_a1_basic_clinical_v1"
        for bad in ALL_PROHIBITED_FIELDS:
            assert bad not in rec["features"]
            assert bad.lower() not in rec["features"]

    clev_path = tmp_path / "processed.cleveland.data"
    clev_sha = _create_mock_cleveland_file(clev_path)
    c_records, c_labels, c_dataset = load_cleveland_source_records(
        clev_path,
        expected_sha256=clev_sha,
        panel=DA_A2_RESTING_PANEL,
    )
    for rec in c_records:
        for bad in ALL_PROHIBITED_FIELDS:
            assert bad not in rec["features"]


def test_untracked_and_private_artifact_storage_security(tmp_path: Path) -> None:
    """Artifact bundle directory is strictly protected with private permissions."""
    bundle_dir = tmp_path / "private_research_models" / "test_bundle"
    ensure_private_directory(bundle_dir.parent)
    acl = verify_access_control(bundle_dir.parent, expect_directory=True, strict_private=True)
    assert acl.ok is True


def test_windows_python312_platform_compatibility() -> None:
    """Verify that execution infrastructure imports and types are clean on Python 3.12/Windows runtime abstractions."""
    from ai.filesystem_security import is_windows_runtime
    from ai.execution import EXECUTION_HARNESS_VERSION, MANDATORY_OUTPUT_BANNER
    assert EXECUTION_HARNESS_VERSION == "cardioassist.ai.execution_harness/v1"
    assert MANDATORY_OUTPUT_BANNER == "INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED"
    assert isinstance(is_windows_runtime(), bool)
