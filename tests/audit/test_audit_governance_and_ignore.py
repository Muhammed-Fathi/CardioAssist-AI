"""Tests for Gate DA governance authorization, provenance/hash checks, archive safety, and git-ignore guards."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import zipfile

import pytest

from research.audit.cli import DEFAULT_AUTH_MANIFEST_PATH, REPO_ROOT, run_local_dataset_audit
from research.audit.exceptions import (
    ArchiveSecurityError,
    FormatValidationError,
    GitIgnoreProtectionError,
    GovernanceAuthorizationError,
    ProvenanceVerificationError,
)
from research.audit.git_safety import verify_data_root_containment, verify_git_ignore
from research.audit.provenance import (
    ByteIdentityGuard,
    inspect_zip_archive,
    load_authorization_manifest,
    sha256_file,
    validate_official_source_url,
    validate_provenance_manifest,
    verify_dataset_authorized_for_audit,
)
from research.audit.synthetic_fixtures import materialize_synthetic_audit_suite


def test_committed_authorization_manifest_is_pending_and_forbids_fitting() -> None:
    manifest = load_authorization_manifest(DEFAULT_AUTH_MANIFEST_PATH)
    assert manifest["governance_decision_id"] == "D-046"
    assert manifest["workflow_status"] == "PENDING_HUMAN_ACCEPTANCE"
    assert manifest["supervisor_approval_claimed"] is False
    assert manifest["model_fitting_authorized"] is False
    assert manifest["feature_selection_authorized"] is False
    assert manifest["hyperparameter_tuning_authorized"] is False
    assert manifest["performance_evaluation_authorized"] is False
    assert manifest["calibration_authorized"] is False
    assert manifest["shap_or_lime_authorized"] is False

    ep = manifest["internal_exploratory_protocol_proposal"]
    assert ep["proposal_id"] == "D-046-EP"
    assert ep["bypasses_gate_pt_p3"] is False
    assert ep["authorizes_model_fitting_in_this_pr"] is False

    for ds_id in ("DA-A1", "DA-A2", "DA-B1", "DA-B2"):
        ds = manifest["datasets"][ds_id]
        assert ds["authorization_status"] == "PENDING_HUMAN_ACCEPTANCE"
        assert ds["training_authorized"] is False
        assert ds["external_validation_authorized"] is False
        assert ds["authorized_by"] is None
        with pytest.raises(GovernanceAuthorizationError):
            verify_dataset_authorized_for_audit(manifest, ds_id)

    assert manifest["datasets"]["DA-B1"]["never_independent_cohort"] is True
    assert manifest["datasets"]["DA-B1"]["never_training_or_external_validation_by_audit_grant"] is True
    assert manifest["datasets"]["DA-B2"]["never_independent_cohort"] is True
    assert manifest["datasets"]["DA-B2"]["never_training_or_external_validation_by_audit_grant"] is True


def test_run_audit_fails_closed_when_status_is_pending_human_acceptance(tmp_path: Path) -> None:
    with pytest.raises(GovernanceAuthorizationError, match="PENDING_HUMAN_ACCEPTANCE"):
        run_local_dataset_audit(
            repo_root=REPO_ROOT,
            base_data_parent=tmp_path,
            auth_manifest_path=DEFAULT_AUTH_MANIFEST_PATH,
            allow_external_tmp_root=tmp_path,
        )


def test_authorization_rejects_missing_human_metadata_or_prohibited_roles(tmp_path: Path) -> None:
    manifest = copy.deepcopy(load_authorization_manifest(DEFAULT_AUTH_MANIFEST_PATH))
    manifest["datasets"]["DA-A1"]["authorization_status"] = "AUTHORIZED_FOR_READ_ONLY_AUDIT"
    # Missing authorized_by, authorized_date, etc.
    with pytest.raises(GovernanceAuthorizationError, match="authorized_by"):
        verify_dataset_authorized_for_audit(manifest, "DA-A1")

    # Populate all required fields
    manifest["datasets"]["DA-A1"].update(
        {
            "authorized_by": "Maintainer",
            "authorized_date": "2026-10-21",
            "responsible_acquirer": "Acquirer",
            "audit_reviewer": "Reviewer",
            "environment": "E:\\CardioAssist_AI_GitHub_Starter",
        }
    )
    verify_dataset_authorized_for_audit(manifest, "DA-A1")

    # Reject non-audit roles (e.g. training or external validation)
    with pytest.raises(GovernanceAuthorizationError, match="prohibited"):
        verify_dataset_authorized_for_audit(
            manifest,
            "DA-A1",
            requested_usage_role="model_training",
        )
    with pytest.raises(GovernanceAuthorizationError, match="prohibited"):
        verify_dataset_authorized_for_audit(
            manifest,
            "DA-B1",
            requested_usage_role="external_validation",
        )


def test_tampered_authorization_manifest_rejected(tmp_path: Path) -> None:
    base = load_authorization_manifest(DEFAULT_AUTH_MANIFEST_PATH)

    bad_sup = copy.deepcopy(base)
    bad_sup["supervisor_approval_claimed"] = True
    p1 = tmp_path / "bad_sup.json"
    p1.write_text(json.dumps(bad_sup), encoding="utf-8")
    with pytest.raises(GovernanceAuthorizationError, match="supervisor_approval_claimed"):
        load_authorization_manifest(p1)

    bad_fit = copy.deepcopy(base)
    bad_fit["model_fitting_authorized"] = True
    p2 = tmp_path / "bad_fit.json"
    p2.write_text(json.dumps(bad_fit), encoding="utf-8")
    with pytest.raises(GovernanceAuthorizationError, match="model_fitting_authorized"):
        load_authorization_manifest(p2)

    bad_b1 = copy.deepcopy(base)
    bad_b1["datasets"]["DA-B1"]["never_independent_cohort"] = False
    p3 = tmp_path / "bad_b1.json"
    p3.write_text(json.dumps(bad_b1), encoding="utf-8")
    with pytest.raises(GovernanceAuthorizationError, match="never_independent_cohort"):
        load_authorization_manifest(p3)


@pytest.mark.parametrize(
    "bad_url",
    [
        "https://www.kaggle.com/datasets/alexteboul/heart-disease",
        "https://github.com/mirror/uci-heart-disease",
        "https://zenodo.org/records/15826856",
        "http://archive.ics.uci.edu/dataset/412/z+alizadeh+sani",
        "https://archive.ics.uci.edu/dataset/999/wrong",
        "",
    ],
)
def test_unapproved_source_urls_rejected(bad_url: str) -> None:
    expected = "https://archive.ics.uci.edu/dataset/412/z+alizadeh+sani"
    with pytest.raises(ProvenanceVerificationError):
        validate_official_source_url(bad_url, expected, "DA-A1")


def test_provenance_hash_size_license_and_unapproved_file_mismatches(tmp_path: Path) -> None:
    suite = materialize_synthetic_audit_suite(tmp_path, authorize_all=True)
    auth_manifest = load_authorization_manifest(suite["auth_manifest_path"])
    prov_path = Path(suite["provenance_manifest_path"])
    base_prov = json.loads(prov_path.read_text(encoding="utf-8"))

    # 1. SHA-256 mismatch
    bad_sha = copy.deepcopy(base_prov)
    bad_sha["files"][0]["sha256"] = "0" * 64
    p_sha = tmp_path / "prov_bad_sha.json"
    p_sha.write_text(json.dumps(bad_sha), encoding="utf-8")
    with pytest.raises(ProvenanceVerificationError, match="SHA-256 mismatch"):
        validate_provenance_manifest(p_sha, tmp_path, auth_manifest, ["DA-A1"])

    # 2. Size mismatch
    bad_size = copy.deepcopy(base_prov)
    bad_size["files"][0]["size_bytes"] += 99
    p_size = tmp_path / "prov_bad_size.json"
    p_size.write_text(json.dumps(bad_size), encoding="utf-8")
    with pytest.raises(ProvenanceVerificationError, match="File size mismatch"):
        validate_provenance_manifest(p_size, tmp_path, auth_manifest, ["DA-A1"])

    # 3. License snapshot missing CC BY 4.0 wording
    lic_412 = tmp_path / "data/manifests/licenses/uci-412-license-snapshot.txt"
    orig_lic_text = lic_412.read_text(encoding="utf-8")
    lic_412.write_text("Proprietary unknown terms without Creative Commons.", encoding="utf-8")
    new_lic_sha, _ = sha256_file(lic_412)
    bad_lic = copy.deepcopy(base_prov)
    bad_lic["files"][0]["license_snapshot_sha256"] = new_lic_sha
    p_lic = tmp_path / "prov_bad_lic.json"
    p_lic.write_text(json.dumps(bad_lic), encoding="utf-8")
    with pytest.raises(ProvenanceVerificationError, match="CC BY 4.0"):
        validate_provenance_manifest(p_lic, tmp_path, auth_manifest, ["DA-A1"])
    lic_412.write_text(orig_lic_text, encoding="utf-8")

    # 4. Excluded file (new.data) placed in DA-A2 directory
    unapproved_file = tmp_path / "data/raw/uci-45/new.data"
    unapproved_file.write_text("unapproved data", encoding="utf-8")
    with pytest.raises(ArchiveSecurityError, match="new.data"):
        validate_provenance_manifest(prov_path, tmp_path, auth_manifest, ["DA-A2"])
    unapproved_file.unlink()

    # 5. Missing required file from provenance manifest (e.g. processed.cleveland.data omitted)
    missing_clev = copy.deepcopy(base_prov)
    missing_clev["files"] = [
        f for f in missing_clev["files"] if f["filename"] != "processed.cleveland.data"
    ]
    p_miss = tmp_path / "prov_missing_clev.json"
    p_miss.write_text(json.dumps(missing_clev), encoding="utf-8")
    with pytest.raises(FormatValidationError, match="processed.cleveland.data"):
        validate_provenance_manifest(p_miss, tmp_path, auth_manifest, ["DA-A2"])


def test_archive_inspector_catches_traversal_executables_and_flags_excluded(tmp_path: Path) -> None:
    auth_manifest = load_authorization_manifest(DEFAULT_AUTH_MANIFEST_PATH)

    # 1. Valid UCI-45 archive containing the 9 required files + excluded new.data & reprocessed.hungarian.data
    valid_zip = tmp_path / "heart+disease.zip"
    with zipfile.ZipFile(valid_zip, "w") as zf:
        for req_name in auth_manifest["datasets"]["DA-A2"]["authorized_files"]:
            zf.writestr(req_name, "placeholder")
        zf.writestr("new.data", "excluded")
        zf.writestr("reprocessed.hungarian.data", "excluded")

    res = inspect_zip_archive(valid_zip, "DA-A2", auth_manifest)
    assert res["passed"] is True
    assert "new.data" in res["excluded_files_detected_do_not_extract"]
    assert "reprocessed.hungarian.data" in res["excluded_files_detected_do_not_extract"]

    # 2. Path traversal entry rejected
    traversal_zip = tmp_path / "traversal.zip"
    with zipfile.ZipFile(traversal_zip, "w") as zf:
        zf.writestr("../evil.txt", "bad")
    with pytest.raises(ArchiveSecurityError, match="path traversal"):
        inspect_zip_archive(traversal_zip, "DA-A1", auth_manifest)

    # 3. Executable/script entry rejected
    exe_zip = tmp_path / "exe.zip"
    with zipfile.ZipFile(exe_zip, "w") as zf:
        zf.writestr("Z-Alizadeh sani dataset.xlsx", "ok")
        zf.writestr("run.ps1", "bad")
    with pytest.raises(ArchiveSecurityError, match="executable/script"):
        inspect_zip_archive(exe_zip, "DA-A1", auth_manifest)

    # 4. Repackaged archive missing required official filenames rejected
    repackaged_zip = tmp_path / "repackaged.zip"
    with zipfile.ZipFile(repackaged_zip, "w") as zf:
        zf.writestr("merged_heart_clean.csv", "1,2,3")
    with pytest.raises(ArchiveSecurityError, match="missing required official file"):
        inspect_zip_archive(repackaged_zip, "DA-A2", auth_manifest)


def test_byte_identity_guard_detects_in_flight_mutation(tmp_path: Path) -> None:
    f = tmp_path / "sample.data"
    f.write_bytes(b"original-bytes-123")
    sha, size = sha256_file(f)

    with ByteIdentityGuard([("sample.data", f, sha, size)]) as guard:
        assert f.read_bytes() == b"original-bytes-123"
    assert len(guard.snapshots) == 1
    assert guard.snapshots[0].byte_identical is True

    with pytest.raises(ProvenanceVerificationError, match="BYTE-IDENTITY VIOLATION"):
        with ByteIdentityGuard([("sample.data", f, sha, size)]):
            f.write_bytes(b"mutated-bytes-456")


def test_git_ignore_protection_and_data_root_containment(tmp_path: Path) -> None:
    res = verify_git_ignore(REPO_ROOT)
    assert res.passed is True
    assert len(res.tracked_files_under_data) == 0

    # Non-ignored path must fail git check-ignore
    with pytest.raises(GitIgnoreProtectionError, match="git check-ignore failed"):
        verify_git_ignore(REPO_ROOT, probe_relative_paths=("README.md",))

    # Containment inside <repo_root>/data/ succeeds
    contained = verify_data_root_containment(REPO_ROOT, REPO_ROOT / "data/raw/uci-412")
    assert contained == (REPO_ROOT / "data/raw/uci-412").resolve()

    # Path outside <repo_root>/data/ without explicit test allowance fails closed
    with pytest.raises(GitIgnoreProtectionError, match="resolves outside"):
        verify_data_root_containment(REPO_ROOT, REPO_ROOT / "research/source_materials")
    with pytest.raises(GitIgnoreProtectionError, match="resolves outside"):
        verify_data_root_containment(REPO_ROOT, tmp_path)
