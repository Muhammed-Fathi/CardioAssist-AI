"""Tests for metadata-only report generation, evidence status labels, redaction guards, and CLI subcommands."""
from __future__ import annotations

import json
from pathlib import Path
import zipfile

import pytest

from research.audit.cli import main, run_dry_run_preflight, run_local_dataset_audit
from research.audit.exceptions import PatientLevelLeakageError
from research.audit.registry import (
    EVIDENCE_REQUIRES_APPROVAL,
    EVIDENCE_SOURCE_REPORTED,
    EVIDENCE_UNVERIFIED,
    EVIDENCE_VERIFIED,
)
from research.audit.reporting import verify_report_no_patient_rows
from research.audit.synthetic_fixtures import (
    SYNTHETIC_PLANTED_SENTINEL_FLOAT,
    materialize_synthetic_audit_suite,
)


def test_dry_run_preflight_report_distinguishes_all_evidence_levels(tmp_path: Path) -> None:
    json_out = tmp_path / "preflight.json"
    md_out = tmp_path / "preflight.md"
    rep, md_text = run_dry_run_preflight(json_output_path=json_out, markdown_output_path=md_out)

    assert json_out.exists()
    assert md_out.exists()
    assert rep["execution_mode"] == "DRY_RUN_PREFLIGHT"
    assert rep["safety_and_non_fitting_certification"]["model_fitting_performed"] is False
    assert rep["safety_and_non_fitting_certification"]["patient_level_rows_emitted"] == 0
    assert rep["safety_and_non_fitting_certification"]["supervisor_approval_claimed"] is False

    # Verify all four evidence labels exist in the report
    serialized = json.dumps(rep)
    for label in (
        EVIDENCE_VERIFIED,
        EVIDENCE_SOURCE_REPORTED,
        EVIDENCE_UNVERIFIED,
        EVIDENCE_REQUIRES_APPROVAL,
    ):
        assert label in serialized
        assert label in md_text

    # Verify Feature Availability & Leakage Review Table covers all required items
    leak_table = rep["feature_availability_and_leakage_table"]
    reg_ids = {r["register_id"] for r in leak_table}
    assert {"L-01", "L-02", "L-02/L-12", "L-03", "L-06", "L-07", "L-08-ECHO", "L-08-LAB", "L-08-CLIN"} <= reg_ids

    # Verify H-01 threshold wording (>50% vs >=50%) and unresolved 50% boundary status
    harm = rep["target_harmonization_and_threshold_boundary"]
    assert harm["issue_id"] == "H-01"
    assert "> 50%" in harm["uci_45_wording"]["inequality_operator"]
    assert ">= 50%" in harm["uci_412_wording"]["inequality_operator"]
    assert harm["boundary_50_percent_status"]["reconciliation_status"] == "UNRESOLVED_BOUNDARY_COMPATIBILITY"
    assert harm["boundary_50_percent_status"]["evidence_status"] == EVIDENCE_UNVERIFIED
    assert harm["boundary_50_percent_status"]["gate_pt_ruling_status"] == EVIDENCE_REQUIRES_APPROVAL


def test_full_synthetic_audit_produces_metadata_only_reports_with_zero_patient_content(
    tmp_path: Path,
) -> None:
    suite = materialize_synthetic_audit_suite(tmp_path, authorize_all=True)
    json_out = tmp_path / "audit_report.json"
    md_out = tmp_path / "audit_report.md"

    rep, md_text = run_local_dataset_audit(
        base_data_parent=tmp_path,
        auth_manifest_path=suite["auth_manifest_path"],
        provenance_manifest_path=suite["provenance_manifest_path"],
        is_synthetic_fixture_run=True,
        allow_external_tmp_root=tmp_path,
        forbidden_substrings=(str(SYNTHETIC_PLANTED_SENTINEL_FLOAT), "63,1,1,145,233"),
        json_output_path=json_out,
        markdown_output_path=md_out,
    )

    assert rep["is_synthetic_fixture_run"] is True
    assert set(rep["dataset_audits"].keys()) == {"DA-A1", "DA-A2", "DA-B1", "DA-B2"}
    assert rep["safety_and_non_fitting_certification"]["originals_byte_identical"] is True
    assert rep["safety_and_non_fitting_certification"]["patient_level_rows_emitted"] == 0

    # Ensure planted patient-level sentinel float (137.42) and raw CSV rows do NOT appear anywhere
    json_text = json_out.read_text(encoding="utf-8")
    assert str(SYNTHETIC_PLANTED_SENTINEL_FLOAT) not in json_text
    assert str(SYNTHETIC_PLANTED_SENTINEL_FLOAT) not in md_text
    assert "63,1,1,145,233" not in json_text
    assert "63,1,1,145,233" not in md_text


def test_report_redaction_guard_blocks_patient_row_leakage() -> None:
    clean_dict = {"summary": {"row_count": 10}}
    clean_md = "# Clean Metadata Report\n\nRow count: 10\n"
    verify_report_no_patient_rows(clean_dict, clean_md)

    # 1. Forbidden dictionary key rejected
    with pytest.raises(PatientLevelLeakageError, match="forbidden patient-row key"):
        verify_report_no_patient_rows({"normalized_rows": [{"age": 63}]}, clean_md)

    # 2. Raw 14-column comma-delimited line in Markdown rejected
    with pytest.raises(PatientLevelLeakageError, match="14-column comma-delimited"):
        verify_report_no_patient_rows(
            clean_dict,
            "# Bad Report\n63,1,1,145,233,1,2,150,0,2.3,3,0,6,0\n",
        )

    # 3. Raw row fingerprint match rejected
    with pytest.raises(PatientLevelLeakageError, match="fingerprint"):
        verify_report_no_patient_rows(
            clean_dict,
            "# Bad Report\n58|76|170|Male|26.3|130|78\n",
            forbidden_row_fingerprints=("58|76|170|Male|26.3|130|78",),
        )


def test_cli_subcommands_end_to_end(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # 1. check-auth
    rc = main(["check-auth"])
    assert rc == 0
    out_auth = json.loads(capsys.readouterr().out)
    assert out_auth["governance_decision_id"] == "D-046"
    assert out_auth["datasets"]["DA-A1"]["authorization_status"] == "PENDING_HUMAN_ACCEPTANCE"

    # 2. verify-ignore
    rc = main(["verify-ignore"])
    assert rc == 0
    out_ign = json.loads(capsys.readouterr().out)
    assert out_ign["passed"] is True

    # 3. dry-run
    dry_json = tmp_path / "cli_dry.json"
    dry_md = tmp_path / "cli_dry.md"
    rc = main(["dry-run", "--json-out", str(dry_json), "--markdown-out", str(dry_md)])
    assert rc == 0
    out_dry = json.loads(capsys.readouterr().out)
    assert out_dry["status"] == "OK_DRY_RUN_PREFLIGHT"
    assert dry_json.exists() and dry_md.exists()

    # 4. self-test
    rc = main(["self-test"])
    assert rc == 0
    out_self = json.loads(capsys.readouterr().out)
    assert out_self["status"] == "OK_SYNTHETIC_SELF_TEST"

    # 5. inspect-archive (clean vs STOP_REQUIRES_REVIEW on unexpected/excluded entries)
    z_path = tmp_path / "z_alizadeh_sani.zip"
    with zipfile.ZipFile(z_path, "w") as zf:
        zf.writestr("Z-Alizadeh sani dataset.xlsx", "dummy")
    rc = main(["inspect-archive", "--dataset-id", "DA-A1", "--zip-path", str(z_path)])
    assert rc == 0
    out_zip = json.loads(capsys.readouterr().out)
    assert out_zip["passed"] is True
    assert out_zip["outcome"] == "PASS_AUTHORIZED_CONTENTS"

    bad_z_path = tmp_path / "z_alizadeh_sani_extra.zip"
    with zipfile.ZipFile(bad_z_path, "w") as zf:
        zf.writestr("Z-Alizadeh sani dataset.xlsx", "dummy")
        zf.writestr("unexpected_extra.csv", "1,2,3")
    rc = main(["inspect-archive", "--dataset-id", "DA-A1", "--zip-path", str(bad_z_path)])
    assert rc == 2
    err_zip = json.loads(capsys.readouterr().err)
    assert err_zip["status"] == "FAILED_CLOSED"
    assert err_zip["error_code"] == "archive_security_error"
    assert "STOP_REQUIRES_REVIEW" in err_zip["message"]

    # 6. run-audit fails closed with exit code 2 when authorization status is PENDING_HUMAN_ACCEPTANCE
    rc = main(["run-audit"])
    assert rc == 2
    err_out = json.loads(capsys.readouterr().err)
    assert err_out["status"] == "FAILED_CLOSED"
    assert err_out["error_code"] == "governance_authorization_error"


def test_proposed_audit_ci_workflow_template_is_complete_and_properly_scoped() -> None:
    """Blocker 6: Verify proposed audit CI workflow template pins deps, runs tests/audit, verify_sources, and artifact guards."""
    repo_root = Path(__file__).resolve().parents[2]
    wf_path = repo_root / "research/audit/ci/audit-ci.yml.example"
    assert wf_path.exists() and wf_path.is_file()
    content = wf_path.read_text(encoding="utf-8")

    assert "python-version: ['3.11', '3.12']" in content
    assert "python -m pip install -r research/audit/requirements.txt" in content
    assert "python -m pip check" in content
    assert "python -m pytest tests/audit -q -W error" in content
    assert "python scripts/verify_sources.py" in content
    assert "find research/audit tests/audit -type f" in content
    assert "persist-credentials: false" in content
