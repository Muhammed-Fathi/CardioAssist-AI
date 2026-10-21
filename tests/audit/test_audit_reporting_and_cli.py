"""Tests for metadata-only report schema validation, redaction checks, output protection, and CLI execution."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import zipfile

import pytest

from research.audit.cli import (
    DEFAULT_AUTH_MANIFEST_PATH,
    REPO_ROOT,
    main,
    run_dry_run_preflight,
    run_local_dataset_audit,
)
from research.audit.exceptions import PatientLevelLeakageError, ProvenanceVerificationError
from research.audit.provenance import sha256_file
from research.audit.registry import (
    EVIDENCE_REQUIRES_APPROVAL,
    EVIDENCE_SOURCE_REPORTED,
    EVIDENCE_UNVERIFIED,
    EVIDENCE_VERIFIED,
    LOCAL_INTEGRITY_VERIFIED_STATUS,
    SOURCE_ORIGIN_HUMAN_ATTESTED_STATUS,
)
from research.audit.reporting import (
    render_markdown_report,
    validate_strict_metadata_report_schema,
    verify_report_no_patient_rows,
)
from research.audit.synthetic_fixtures import (
    SYNTHETIC_PLANTED_SENTINEL_FLOAT,
    materialize_synthetic_audit_suite,
)


def test_dry_run_preflight_succeeds_without_reading_datasets() -> None:
    report, md = run_dry_run_preflight()
    assert report["execution_mode"] == "DRY_RUN_PREFLIGHT"
    assert report["dataset_audits"] == {}
    assert report["safety_and_non_fitting_certification"]["model_fitting_performed"] is False
    assert report["safety_and_non_fitting_certification"]["patient_level_rows_emitted"] == 0
    assert report["safety_and_non_fitting_certification"]["supervisor_approval_claimed"] is False
    assert (
        report["safety_and_non_fitting_certification"]["local_file_integrity_status"]
        == LOCAL_INTEGRITY_VERIFIED_STATUS
    )
    assert (
        report["safety_and_non_fitting_certification"]["official_source_provenance_status"]
        == SOURCE_ORIGIN_HUMAN_ATTESTED_STATUS
    )
    assert "STRICT_METADATA_SCHEMA_AND_SECONDARY_PATTERN_SCANNER_VALIDATED" in report[
        "safety_and_non_fitting_certification"
    ]["privacy_controls_and_limitations"]

    for ds_id in ("DA-A1", "DA-A2", "DA-B1", "DA-B2"):
        ds = report["governance_and_authorization"]["datasets"][ds_id]
        assert ds["authorization_status"] == "PENDING_HUMAN_ACCEPTANCE"
        assert ds["evidence_status"] == EVIDENCE_REQUIRES_APPROVAL

    assert report["uci_411_412_correspondence"]["same_cohort_provenance_status"] == EVIDENCE_VERIFIED
    assert report["uci_411_412_correspondence"]["row_correspondence_evidence_status"] == EVIDENCE_REQUIRES_APPROVAL
    assert report["uci_145_cleveland_overlap"]["evidence_status"] == EVIDENCE_REQUIRES_APPROVAL
    assert (
        report["target_harmonization_and_threshold_boundary"]["boundary_50_percent_status"]["evidence_status"]
        == EVIDENCE_UNVERIFIED
    )
    assert report["source_reported_baseline_notes"]["evidence_status"] == EVIDENCE_SOURCE_REPORTED
    assert "REQUIRES APPROVAL" in md
    assert "SOURCE-REPORTED" in md
    assert "UNVERIFIED" in md
    assert "VERIFIED" in md


def test_synthetic_end_to_end_audit_emits_zero_patient_rows_and_preserves_byte_identity(
    tmp_path: Path,
) -> None:
    suite = materialize_synthetic_audit_suite(tmp_path, authorize_all=True)

    # Record pre-run SHA-256 of every synthetic dataset file
    pre_hashes = {
        str(p.relative_to(tmp_path)): sha256_file(p)
        for p in (tmp_path / "data/raw").rglob("*")
        if p.is_file()
    }
    assert len(pre_hashes) == 12  # 1 (412) + 9 (45) + 1 (411) + 1 (145)

    json_rel = "data/reports/synthetic_report.json"
    md_rel = "data/reports/synthetic_report.md"

    report, md = run_local_dataset_audit(
        repo_root=REPO_ROOT,
        base_data_parent=tmp_path,
        auth_manifest_path=suite["auth_manifest_path"],
        provenance_manifest_path=suite["provenance_manifest_path"],
        is_synthetic_fixture_run=True,
        allow_external_tmp_root=tmp_path,
        forbidden_substrings=(str(SYNTHETIC_PLANTED_SENTINEL_FLOAT),),
        json_output_path=json_rel,
        markdown_output_path=md_rel,
    )

    assert report["is_synthetic_fixture_run"] is True
    assert set(report["dataset_audits"].keys()) == {"DA-A1", "DA-A2", "DA-B1", "DA-B2"}
    assert report["safety_and_non_fitting_certification"]["originals_byte_identical"] is True
    assert report["safety_and_non_fitting_certification"]["patient_level_rows_emitted"] == 0

    # Verify planted unique patient sentinel float is NOT present anywhere in JSON or Markdown
    json_str = (tmp_path / json_rel).read_text(encoding="utf-8")
    md_str = (tmp_path / md_rel).read_text(encoding="utf-8")
    assert str(SYNTHETIC_PLANTED_SENTINEL_FLOAT) not in json_str
    assert str(SYNTHETIC_PLANTED_SENTINEL_FLOAT) not in md_str
    assert md_str == md

    # Verify all 12 dataset files remain byte-identical after audit
    post_hashes = {
        str(p.relative_to(tmp_path)): sha256_file(p)
        for p in (tmp_path / "data/raw").rglob("*")
        if p.is_file()
    }
    assert post_hashes == pre_hashes


def test_originals_remain_byte_identical_when_report_generation_fails(tmp_path: Path) -> None:
    """Follow-up Blocker 1: Verify dataset originals remain 100% byte-identical even when report generation fails."""
    suite = materialize_synthetic_audit_suite(tmp_path, authorize_all=True)
    pre_hashes = {
        str(p.relative_to(tmp_path)): sha256_file(p)
        for p in (tmp_path / "data/raw").rglob("*")
        if p.is_file()
    }

    # Force build_and_verify_reports to fail with PatientLevelLeakageError by passing a known report string in forbidden_substrings
    with pytest.raises(PatientLevelLeakageError):
        run_local_dataset_audit(
            repo_root=REPO_ROOT,
            base_data_parent=tmp_path,
            auth_manifest_path=suite["auth_manifest_path"],
            provenance_manifest_path=suite["provenance_manifest_path"],
            is_synthetic_fixture_run=True,
            allow_external_tmp_root=tmp_path,
            forbidden_substrings=("SYNTHETIC_SELF_TEST",),
            json_output_path="data/reports/should_not_be_written.json",
        )

    assert not (tmp_path / "data/reports/should_not_be_written.json").exists()
    post_hashes = {
        str(p.relative_to(tmp_path)): sha256_file(p)
        for p in (tmp_path / "data/raw").rglob("*")
        if p.is_file()
    }
    assert post_hashes == pre_hashes


def test_strict_metadata_report_schema_rejects_unexpected_fields_and_nested_injections(
    tmp_path: Path,
) -> None:
    """Follow-up Important: Strict allowlisted metadata-only schema rejects newly introduced nested fields or non-aggregate values."""
    suite = materialize_synthetic_audit_suite(tmp_path, authorize_all=True)
    base_rep, base_md = run_local_dataset_audit(
        repo_root=REPO_ROOT,
        base_data_parent=tmp_path,
        auth_manifest_path=suite["auth_manifest_path"],
        provenance_manifest_path=suite["provenance_manifest_path"],
        is_synthetic_fixture_run=True,
        allow_external_tmp_root=tmp_path,
    )
    validate_strict_metadata_report_schema(base_rep)

    # 1. Unexpected top-level field rejected
    bad_top = copy.deepcopy(base_rep)
    bad_top["unexpected_top_field"] = {"patient_age": 63}
    with pytest.raises(PatientLevelLeakageError, match="Strict metadata-only report schema violation"):
        verify_report_no_patient_rows(bad_top, base_md)

    # 2. Unexpected nested field inside DA-A1 audit rejected (even when key name is not in FORBIDDEN_REPORT_KEYS)
    bad_nested_a1 = copy.deepcopy(base_rep)
    bad_nested_a1["dataset_audits"]["DA-A1"]["custom_row_preview"] = {"Age": 58, "Sex": "Male", "Cath": "CAD"}
    with pytest.raises(PatientLevelLeakageError, match="Strict metadata-only report schema violation"):
        verify_report_no_patient_rows(bad_nested_a1, base_md)

    # 3. Unexpected nested field inside DA-A2 processed file summary rejected
    bad_nested_a2 = copy.deepcopy(base_rep)
    bad_nested_a2["dataset_audits"]["DA-A2"]["processed_files"]["processed.cleveland.data"][
        "custom_patient_tuple"
    ] = [63, 1, 1, 145, 233]
    with pytest.raises(PatientLevelLeakageError, match="Strict metadata-only report schema violation"):
        verify_report_no_patient_rows(bad_nested_a2, base_md)

    # 4. Disallowed free-text value injected into inferred_column_types rejected
    bad_col_type = copy.deepcopy(base_rep)
    bad_col_type["dataset_audits"]["DA-A1"]["inferred_column_types"]["Age"] = "patient_0_age_63_male"
    with pytest.raises(PatientLevelLeakageError, match="Disallowed non-enum value"):
        verify_report_no_patient_rows(bad_col_type, base_md)

    # 5. Non-integer injected into a count map rejected
    bad_count_val = copy.deepcopy(base_rep)
    bad_count_val["dataset_audits"]["DA-A1"]["suspicious_values_by_column"]["Age"] = "63,Male,140,90"
    with pytest.raises(PatientLevelLeakageError, match="expected int count"):
        verify_report_no_patient_rows(bad_count_val, base_md)


def test_secondary_redaction_scanner_catches_non_14_column_and_14_column_patient_content() -> None:
    """Follow-up Important: Secondary pattern/fingerprint scanner catches 14-col, 76-attr, and multi-column patient content."""
    clean_rep, clean_md = run_dry_run_preflight()
    verify_report_no_patient_rows(clean_rep, clean_md)

    # 1. Forbidden key in dictionary rejected
    bad_key_rep = copy.deepcopy(clean_rep)
    bad_key_rep["dataset_audits"] = {"DA-A1": {"normalized_rows": [{"age": 63}]}}
    with pytest.raises(PatientLevelLeakageError, match="forbidden patient-row key"):
        verify_report_no_patient_rows(bad_key_rep, clean_md, enforce_strict_schema=False)

    # 2. Raw 14-column comma-delimited line in Markdown rejected
    bad_md_14_comma = clean_md + "\n63.0, 1.0, 1.0, 145.0, 233.0, 1.0, 2.0, 150.0, 0.0, 2.3, 3.0, 0.0, 6.0, 0\n"
    with pytest.raises(PatientLevelLeakageError, match="14-column comma-delimited"):
        verify_report_no_patient_rows(clean_rep, bad_md_14_comma)

    # 3. Raw 14-column whitespace-delimited Statlog line in Markdown rejected
    bad_md_14_space = clean_md + "\n70.0 1.0 4.0 130.0 322.0 0.0 2.0 109.0 0.0 2.4 2.0 3.0 3.0 2\n"
    with pytest.raises(PatientLevelLeakageError, match="14-column whitespace-delimited"):
        verify_report_no_patient_rows(clean_rep, bad_md_14_space)

    # 4. Non-14-column raw 76-attribute patient record fragment in Markdown rejected
    bad_md_76_attr = clean_md + "\n1 15943882 63 1 -9 -9 -9 -9 1 145 1 233 -9 50 20 name\n"
    with pytest.raises(PatientLevelLeakageError, match="76-attribute patient record fragment"):
        verify_report_no_patient_rows(clean_rep, bad_md_76_attr)

    # 5. Non-14-column multi-column UCI-412 patient row (e.g. 10+ comma-separated clinical values) in Markdown rejected
    bad_md_412_row = clean_md + "\n58, 75, 170, Male, 25.9, N, 1, 0, 1, 0, 130, 80, 74, CAD\n"
    with pytest.raises(PatientLevelLeakageError, match="multi-column patient record line"):
        verify_report_no_patient_rows(clean_rep, bad_md_412_row)

    # 6. Row fingerprint match rejected
    fp = "58 | 75 | 170 | Male | 25.95 | N | 1 | 0"
    with pytest.raises(PatientLevelLeakageError, match="row fingerprint"):
        verify_report_no_patient_rows(
            clean_rep,
            clean_md + f"\nLeaked row: {fp}\n",
            forbidden_row_fingerprints=(fp,),
        )

    # 7. Forbidden sentinel substring rejected
    with pytest.raises(PatientLevelLeakageError, match="forbidden patient-level value substring"):
        verify_report_no_patient_rows(
            clean_rep,
            clean_md + "\n98765.4321\n",
            forbidden_substrings=("98765.4321",),
        )


def test_cli_subcommands_execute_cleanly_and_fail_closed_on_unauthorized_run(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    # 1. --dry-run
    rc_dry = main(["--dry-run"])
    assert rc_dry == 0
    out_dry = json.loads(capsys.readouterr().out)
    assert out_dry["status"] == "OK_DRY_RUN_PREFLIGHT"
    assert out_dry["patient_level_rows_emitted"] == 0

    # 2. check-auth
    rc_auth = main(["check-auth"])
    assert rc_auth == 0
    out_auth = json.loads(capsys.readouterr().out)
    assert out_auth["workflow_status"] == "PENDING_HUMAN_ACCEPTANCE"
    assert out_auth["model_fitting_authorized"] is False

    # 3. verify-ignore
    rc_ign = main(["verify-ignore"])
    assert rc_ign == 0
    out_ign = json.loads(capsys.readouterr().out)
    assert out_ign["passed"] is True

    # 4. self-test
    rc_self = main(["self-test"])
    assert rc_self == 0
    out_self = json.loads(capsys.readouterr().out)
    assert out_self["status"] == "OK_SYNTHETIC_SELF_TEST"
    assert out_self["originals_byte_identical"] is True
    assert out_self["patient_level_rows_emitted"] == 0

    # 5. run-audit fails closed when committed manifest is PENDING_HUMAN_ACCEPTANCE
    rc_run = main(["run-audit"])
    assert rc_run == 2
    err_run = json.loads(capsys.readouterr().err)
    assert err_run["status"] == "FAILED_CLOSED"
    assert err_run["error_code"] == "governance_authorization_error"

    # 6. dry-run with dangerous --json-out path fails closed with provenance_verification_error
    rc_bad_out = main(["dry-run", "--json-out", "data/raw/uci-412/Z-Alizadeh sani dataset.xlsx"])
    assert rc_bad_out == 2
    err_bad_out = json.loads(capsys.readouterr().err)
    assert err_bad_out["status"] == "FAILED_CLOSED"
    assert err_bad_out["error_code"] == "provenance_verification_error"

    # 7. extract-authorized-archive fails closed when dataset is PENDING_HUMAN_ACCEPTANCE
    dummy_zip = tmp_path / "dummy.zip"
    with zipfile.ZipFile(dummy_zip, "w") as zf:
        zf.writestr("Z-Alizadeh sani dataset.xlsx", "ok")
    rc_ext = main(
        [
            "extract-authorized-archive",
            "--dataset-id",
            "DA-A1",
            "--zip-path",
            str(dummy_zip),
        ]
    )
    assert rc_ext == 2
    err_ext = json.loads(capsys.readouterr().err)
    assert err_ext["status"] == "FAILED_CLOSED"
    assert err_ext["error_code"] == "governance_authorization_error"


def test_proposed_audit_ci_workflow_template_is_complete_and_properly_scoped() -> None:
    """Important 7 & Final Review 1/3: Verify CI workflow template, workflow name consistency, and official dataset references."""
    wf_path = REPO_ROOT / "research/audit/ci/audit-ci.yml.example"
    readme_path = REPO_ROOT / "research/audit/ci/README.md"
    handoff_path = REPO_ROOT / "docs/research/gate-da/09_m2a_windows_local_audit_handoff.md"
    assert wf_path.is_file()
    assert readme_path.is_file()
    assert handoff_path.is_file()

    wf_text = wf_path.read_text(encoding="utf-8")
    assert "name: audit-toolchain-validation" in wf_text
    assert "pytest tests/audit -q" in wf_text
    assert "python -m research.audit dry-run" in wf_text
    assert "python -m research.audit self-test" in wf_text
    assert "python scripts/verify_sources.py" in wf_text
    assert "'3.11'" in wf_text
    assert "'3.12'" in wf_text

    readme_text = readme_path.read_text(encoding="utf-8")
    assert "arena/a1f1816a-cardioassist-ai" in readme_text
    assert "git fetch origin arena/a1f1816a-cardioassist-ai" in readme_text
    assert "audit-toolchain-validation" in readme_text
    assert "Audit Toolchain & Source Integrity CI" not in readme_text

    handoff_text = handoff_path.read_text(encoding="utf-8")
    assert "audit-toolchain-validation" in handoff_text
    assert "Audit Toolchain & Source Integrity CI" not in handoff_text

    # Verify all 4 official dataset DOIs and canonical URLs in gate_da_authorization.json match the Windows handoff
    auth_manifest = json.loads(DEFAULT_AUTH_MANIFEST_PATH.read_text(encoding="utf-8"))
    for ds_id, ds_cfg in auth_manifest["datasets"].items():
        assert ds_cfg["doi"] in handoff_text, f"DOI {ds_cfg['doi']} for {ds_id} missing from Windows handoff"
        assert (
            ds_cfg["official_source_url"] in handoff_text
        ), f"Canonical URL {ds_cfg['official_source_url']} for {ds_id} missing from Windows handoff"
