"""Tests for Gate DA governance authorization, provenance/hash/containment checks, archive safety, and git-ignore guards."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
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
    build_provenance_manifest,
    inspect_zip_archive,
    load_authorization_manifest,
    sha256_file,
    validate_official_source_url,
    validate_provenance_manifest,
    verify_dataset_authorized_for_audit,
)
from research.audit.registry import (
    EVIDENCE_SOURCE_REPORTED,
    EVIDENCE_UNVERIFIED,
    GLOBAL_AUTHORIZED_WORKFLOW_STATUS,
    LOCAL_INTEGRITY_VERIFIED_STATUS,
    SOURCE_ORIGIN_HUMAN_ATTESTED_STATUS,
    UNKNOWN_DOWNLOAD_TIMESTAMP,
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


def test_dataset_authorized_rejected_when_global_workflow_status_is_pending(tmp_path: Path) -> None:
    """Blocker 2: A dataset individually marked authorized is still rejected when global workflow_status is pending."""
    suite = materialize_synthetic_audit_suite(tmp_path, authorize_all=True)
    manifest = load_authorization_manifest(suite["auth_manifest_path"])

    # Keep DA-A1 individually authorized with full metadata, but revert global workflow_status
    manifest["workflow_status"] = "PENDING_HUMAN_ACCEPTANCE"
    pending_global_path = tmp_path / "auth_pending_global.json"
    pending_global_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    with pytest.raises(GovernanceAuthorizationError, match="Global Gate DA workflow_status"):
        verify_dataset_authorized_for_audit(manifest, "DA-A1")

    with pytest.raises(GovernanceAuthorizationError, match="Global Gate DA workflow_status"):
        build_provenance_manifest(
            tmp_path,
            manifest,
            ["DA-A1"],
            acquirer="Synthetic Test Acquirer",
            audit_reviewer="Synthetic Test Reviewer",
            environment="E:\\CardioAssist_AI_GitHub_Starter (Synthetic Test)",
        )

    with pytest.raises(GovernanceAuthorizationError, match="Global Gate DA workflow_status"):
        validate_provenance_manifest(
            Path(suite["provenance_manifest_path"]),
            tmp_path,
            manifest,
            ["DA-A1"],
        )

    with pytest.raises(GovernanceAuthorizationError, match="Global Gate DA workflow_status"):
        run_local_dataset_audit(
            repo_root=REPO_ROOT,
            base_data_parent=tmp_path,
            auth_manifest_path=pending_global_path,
            provenance_manifest_path=suite["provenance_manifest_path"],
            requested_datasets=["DA-A1"],
            is_synthetic_fixture_run=True,
            allow_external_tmp_root=tmp_path,
        )


def test_authorization_rejects_missing_human_metadata_or_prohibited_roles() -> None:
    manifest = copy.deepcopy(load_authorization_manifest(DEFAULT_AUTH_MANIFEST_PATH))
    manifest["workflow_status"] = GLOBAL_AUTHORIZED_WORKFLOW_STATUS
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


def test_provenance_path_containment_rejects_external_traversal_symlinks_and_mismatched_dirs(
    tmp_path: Path,
) -> None:
    """Blocker 1: Enforce strict containment for dataset files, license snapshots, symlinks, and subdirectories."""
    suite = materialize_synthetic_audit_suite(tmp_path, authorize_all=True)
    auth_manifest = load_authorization_manifest(suite["auth_manifest_path"])
    prov_path = Path(suite["provenance_manifest_path"])
    base_prov = json.loads(prov_path.read_text(encoding="utf-8"))

    # 1. Absolute external path in relative_path rejected
    outside_file = tmp_path / "outside_Z-Alizadeh sani dataset.xlsx"
    outside_file.write_bytes((tmp_path / "data/raw/uci-412/Z-Alizadeh sani dataset.xlsx").read_bytes())
    abs_prov = copy.deepcopy(base_prov)
    abs_prov["files"][0]["relative_path"] = str(outside_file.resolve())
    p_abs = tmp_path / "prov_abs.json"
    p_abs.write_text(json.dumps(abs_prov), encoding="utf-8")
    with pytest.raises(ProvenanceVerificationError, match="Absolute or drive-prefixed path is prohibited"):
        validate_provenance_manifest(p_abs, tmp_path, auth_manifest, ["DA-A1"])

    # 2. Windows drive-prefixed path in license_snapshot_path rejected
    win_prov = copy.deepcopy(base_prov)
    win_prov["files"][0]["license_snapshot_path"] = "E:\\outside\\uci-412-license-snapshot.txt"
    p_win = tmp_path / "prov_win.json"
    p_win.write_text(json.dumps(win_prov), encoding="utf-8")
    with pytest.raises(ProvenanceVerificationError, match="Absolute or drive-prefixed path is prohibited"):
        validate_provenance_manifest(p_win, tmp_path, auth_manifest, ["DA-A1"])

    # 3. '..' traversal in relative_path rejected
    trav_prov = copy.deepcopy(base_prov)
    trav_prov["files"][0]["relative_path"] = "data/raw/uci-412/../../../Z-Alizadeh sani dataset.xlsx"
    p_trav = tmp_path / "prov_trav.json"
    p_trav.write_text(json.dumps(trav_prov), encoding="utf-8")
    with pytest.raises(ProvenanceVerificationError, match="Path traversal"):
        validate_provenance_manifest(p_trav, tmp_path, auth_manifest, ["DA-A1"])

    # 4. '..' traversal in license_snapshot_path rejected
    trav_lic_prov = copy.deepcopy(base_prov)
    trav_lic_prov["files"][0]["license_snapshot_path"] = (
        "data/manifests/licenses/../../uci-412-license-snapshot.txt"
    )
    p_trav_lic = tmp_path / "prov_trav_lic.json"
    p_trav_lic.write_text(json.dumps(trav_lic_prov), encoding="utf-8")
    with pytest.raises(ProvenanceVerificationError, match="Path traversal"):
        validate_provenance_manifest(p_trav_lic, tmp_path, auth_manifest, ["DA-A1"])

    # 5. Mismatched local subdirectory in manifest relative_path (DA-A1 pointing into uci-45) rejected
    wrong_subdir_prov = copy.deepcopy(base_prov)
    wrong_subdir_prov["files"][0]["relative_path"] = "data/raw/uci-45/Z-Alizadeh sani dataset.xlsx"
    p_wrong_sub = tmp_path / "prov_wrong_subdir.json"
    p_wrong_sub.write_text(json.dumps(wrong_subdir_prov), encoding="utf-8")
    with pytest.raises(ProvenanceVerificationError, match="not inside the required authorized directory"):
        validate_provenance_manifest(p_wrong_sub, tmp_path, auth_manifest, ["DA-A1"])

    # 6. Mismatched license snapshot directory or filename rejected
    wrong_lic_dir_prov = copy.deepcopy(base_prov)
    wrong_lic_dir_prov["files"][0]["license_snapshot_path"] = "data/manifests/uci-412-license-snapshot.txt"
    p_wrong_lic = tmp_path / "prov_wrong_lic.json"
    p_wrong_lic.write_text(json.dumps(wrong_lic_dir_prov), encoding="utf-8")
    with pytest.raises(ProvenanceVerificationError, match="not inside the required authorized directory"):
        validate_provenance_manifest(p_wrong_lic, tmp_path, auth_manifest, ["DA-A1"])

    # 7. Tampered local_subdir in authorization manifest rejected
    bad_auth_subdir = copy.deepcopy(auth_manifest)
    bad_auth_subdir["datasets"]["DA-A1"]["local_subdir"] = "data/raw/uci-999"
    with pytest.raises(ProvenanceVerificationError, match="does not match canonical authorized directory"):
        validate_provenance_manifest(prov_path, tmp_path, bad_auth_subdir, ["DA-A1"])

    # 8. Symlink escape on dataset file rejected
    real_412 = tmp_path / "data/raw/uci-412/Z-Alizadeh sani dataset.xlsx"
    backup_412 = tmp_path / "backup_412.xlsx"
    shutil.copy2(real_412, backup_412)
    real_412.unlink()
    real_412.symlink_to(backup_412)
    try:
        with pytest.raises(ProvenanceVerificationError, match="Symlink detected"):
            validate_provenance_manifest(prov_path, tmp_path, auth_manifest, ["DA-A1"])
    finally:
        real_412.unlink()
        shutil.copy2(backup_412, real_412)

    # 9. Symlink escape on license snapshot file rejected
    real_lic = tmp_path / "data/manifests/licenses/uci-412-license-snapshot.txt"
    backup_lic = tmp_path / "backup_lic.txt"
    shutil.copy2(real_lic, backup_lic)
    real_lic.unlink()
    real_lic.symlink_to(backup_lic)
    try:
        with pytest.raises(ProvenanceVerificationError, match="Symlink detected"):
            validate_provenance_manifest(prov_path, tmp_path, auth_manifest, ["DA-A1"])
    finally:
        real_lic.unlink()
        shutil.copy2(backup_lic, real_lic)

    # 10. Absent authorized dataset directory fails closed
    uci_412_dir = tmp_path / "data/raw/uci-412"
    moved_dir = tmp_path / "moved_uci_412"
    shutil.move(str(uci_412_dir), str(moved_dir))
    try:
        with pytest.raises(ProvenanceVerificationError, match="Authorized directory 'data/raw/uci-412' .* does not exist"):
            validate_provenance_manifest(prov_path, tmp_path, auth_manifest, ["DA-A1"])
    finally:
        shutil.move(str(moved_dir), str(uci_412_dir))


def test_provenance_timestamp_and_origin_semantics(tmp_path: Path) -> None:
    """Important 5: Separate downloaded_at_utc from manifest_recorded_at_utc and distinguish local hash from origin proof."""
    suite = materialize_synthetic_audit_suite(tmp_path, authorize_all=True)
    auth_manifest = load_authorization_manifest(suite["auth_manifest_path"])

    # 1. Default build_provenance_manifest uses UNKNOWN_PENDING_HUMAN_VERIFICATION for downloaded_at_utc
    default_prov_out = tmp_path / "data/manifests/prov_default_ts.json"
    doc_default = build_provenance_manifest(
        tmp_path,
        auth_manifest,
        ["DA-A1"],
        acquirer="Named Acquirer",
        audit_reviewer="Named Reviewer",
        environment="E:\\CardioAssist_AI_GitHub_Starter",
        manifest_recorded_at_utc="2026-10-21T12:00:00Z",
        output_manifest_path=default_prov_out,
    )
    assert doc_default["manifest_recorded_at_utc"] == "2026-10-21T12:00:00Z"
    f0 = doc_default["files"][0]
    assert f0["downloaded_at_utc"] == UNKNOWN_DOWNLOAD_TIMESTAMP
    assert f0["manifest_recorded_at_utc"] == "2026-10-21T12:00:00Z"
    assert f0[" downloaded_at_utc" if False else "downloaded_at_utc"] != f0["manifest_recorded_at_utc"]
    assert f0["download_timestamp_evidence_status"] == EVIDENCE_UNVERIFIED
    assert f0["local_file_integrity_status"] == LOCAL_INTEGRITY_VERIFIED_STATUS
    assert f0["official_source_provenance_status"] == SOURCE_ORIGIN_HUMAN_ATTESTED_STATUS

    # 2. Explicit human downloaded_at_utc is preserved separately from manifest_recorded_at_utc
    explicit_prov_out = tmp_path / "data/manifests/prov_explicit_ts.json"
    doc_explicit = build_provenance_manifest(
        tmp_path,
        auth_manifest,
        ["DA-A1"],
        acquirer="Named Acquirer",
        audit_reviewer="Named Reviewer",
        environment="E:\\CardioAssist_AI_GitHub_Starter",
        downloaded_at_utc="2026-10-20T08:15:00Z",
        manifest_recorded_at_utc="2026-10-21T12:00:00Z",
        output_manifest_path=explicit_prov_out,
    )
    f_exp = doc_explicit["files"][0]
    assert f_exp["downloaded_at_utc"] == "2026-10-20T08:15:00Z"
    assert f_exp["manifest_recorded_at_utc"] == "2026-10-21T12:00:00Z"
    assert f_exp["download_timestamp_evidence_status"] == EVIDENCE_SOURCE_REPORTED
    assert f_exp["local_file_integrity_status"] == LOCAL_INTEGRITY_VERIFIED_STATUS
    assert f_exp["official_source_provenance_status"] == SOURCE_ORIGIN_HUMAN_ATTESTED_STATUS

    # 3. Attempting to claim official_source_provenance_status == "VERIFIED" is rejected
    bad_origin = copy.deepcopy(doc_explicit)
    bad_origin["files"][0]["official_source_provenance_status"] = "VERIFIED"
    p_bad_origin = tmp_path / "prov_bad_origin.json"
    p_bad_origin.write_text(json.dumps(bad_origin), encoding="utf-8")
    with pytest.raises(ProvenanceVerificationError, match="official_source_provenance_status"):
        validate_provenance_manifest(p_bad_origin, tmp_path, auth_manifest, ["DA-A1"])


def test_archive_inspector_stops_on_unexpected_extras_excluded_files_and_unsafe_paths(
    tmp_path: Path,
) -> None:
    """Blocker 3: ZIP inspection allows only authorized files + explicit harmless metadata allowlist; stops on extras/excluded."""
    auth_manifest = load_authorization_manifest(DEFAULT_AUTH_MANIFEST_PATH)

    # 1. Valid UCI-45 archive containing the 9 required files + allowlisted harmless 'Index' metadata
    clean_zip = tmp_path / "heart+disease_clean.zip"
    with zipfile.ZipFile(clean_zip, "w") as zf:
        for req_name in auth_manifest["datasets"]["DA-A2"]["authorized_files"]:
            zf.writestr(req_name, "placeholder")
        zf.writestr("Index", "harmless index metadata")

    res = inspect_zip_archive(clean_zip, "DA-A2", auth_manifest)
    assert res["passed"] is True
    assert res["outcome"] == "PASS_AUTHORIZED_CONTENTS"
    assert res["harmless_metadata_allowlist_matched"] == ["Index"]

    # 2. ZIP with all required files PLUS excluded unapproved dataset files (new.data, reprocessed.hungarian.data)
    # must fail closed with STOP_REQUIRES_REVIEW
    excluded_zip = tmp_path / "heart+disease_with_excluded.zip"
    with zipfile.ZipFile(excluded_zip, "w") as zf:
        for req_name in auth_manifest["datasets"]["DA-A2"]["authorized_files"]:
            zf.writestr(req_name, "placeholder")
        zf.writestr("new.data", "excluded")
        zf.writestr("reprocessed.hungarian.data", "excluded")

    with pytest.raises(ArchiveSecurityError, match="STOP_REQUIRES_REVIEW") as exc_excl:
        inspect_zip_archive(excluded_zip, "DA-A2", auth_manifest)
    assert getattr(exc_excl.value, "outcome", None) == "STOP_REQUIRES_REVIEW"
    assert getattr(exc_excl.value, "excluded_files_detected", None) == [
        "new.data",
        "reprocessed.hungarian.data",
    ]

    # 3. ZIP with all required files PLUS unexpected extra file on DA-A2 must also fail closed (no broad DA-A2 exception)
    extra_da_a2_zip = tmp_path / "heart+disease_with_extra.zip"
    with zipfile.ZipFile(extra_da_a2_zip, "w") as zf:
        for req_name in auth_manifest["datasets"]["DA-A2"]["authorized_files"]:
            zf.writestr(req_name, "placeholder")
        zf.writestr("unexpected_extra.csv", "1,2,3")

    with pytest.raises(ArchiveSecurityError, match="STOP_REQUIRES_REVIEW") as exc_extra:
        inspect_zip_archive(extra_da_a2_zip, "DA-A2", auth_manifest)
    assert getattr(exc_extra.value, "outcome", None) == "STOP_REQUIRES_REVIEW"
    assert getattr(exc_extra.value, "unexpected_entries_detected", None) == ["unexpected_extra.csv"]

    # 4. ZIP with all required files PLUS unexpected extra file on DA-A1 must fail closed
    extra_da_a1_zip = tmp_path / "z_alizadeh_with_extra.zip"
    with zipfile.ZipFile(extra_da_a1_zip, "w") as zf:
        zf.writestr("Z-Alizadeh sani dataset.xlsx", "ok")
        zf.writestr("bonus_notes.txt", "unexpected")
    with pytest.raises(ArchiveSecurityError, match="STOP_REQUIRES_REVIEW"):
        inspect_zip_archive(extra_da_a1_zip, "DA-A1", auth_manifest)

    # 5. Path traversal, nested path, or absolute path entries rejected
    for unsafe_entry in ("../evil.txt", "/abs/evil.txt", "C:\\evil.txt", "nested/Z-Alizadeh sani dataset.xlsx"):
        unsafe_zip = tmp_path / "unsafe.zip"
        with zipfile.ZipFile(unsafe_zip, "w") as zf:
            zf.writestr("Z-Alizadeh sani dataset.xlsx", "ok")
            zf.writestr(unsafe_entry, "bad")
        with pytest.raises(ArchiveSecurityError):
            inspect_zip_archive(unsafe_zip, "DA-A1", auth_manifest)

    # 6. Executable/script entry rejected
    exe_zip = tmp_path / "exe.zip"
    with zipfile.ZipFile(exe_zip, "w") as zf:
        zf.writestr("Z-Alizadeh sani dataset.xlsx", "ok")
        zf.writestr("run.ps1", "bad")
    with pytest.raises(ArchiveSecurityError, match="executable/script"):
        inspect_zip_archive(exe_zip, "DA-A1", auth_manifest)

    # 7. Repackaged archive missing required official filenames rejected
    repackaged_zip = tmp_path / "repackaged.zip"
    with zipfile.ZipFile(repackaged_zip, "w") as zf:
        zf.writestr("merged_heart_clean.csv", "1,2,3")
    with pytest.raises(ArchiveSecurityError, match="missing required official file"):
        inspect_zip_archive(repackaged_zip, "DA-A2", auth_manifest)


def test_byte_identity_guard_verifies_on_both_success_and_failure_paths(tmp_path: Path) -> None:
    """Important 4: Run byte-identity verification on both success and failure paths."""
    f = tmp_path / "sample.data"
    f.write_bytes(b"original-bytes-123")
    sha, size = sha256_file(f)

    # 1. Success path with untouched file
    with ByteIdentityGuard([("sample.data", f, sha, size)]) as guard_ok:
        assert f.read_bytes() == b"original-bytes-123"
    assert len(guard_ok.snapshots) == 1
    assert guard_ok.snapshots[0].byte_identical is True

    # 2. Success path with mutated file raises ProvenanceVerificationError
    with pytest.raises(ProvenanceVerificationError, match="BYTE-IDENTITY VIOLATION"):
        with ByteIdentityGuard([("sample.data", f, sha, size)]):
            f.write_bytes(b"mutated-bytes-456")
    f.write_bytes(b"original-bytes-123")

    # 3. Failure path with untouched file: post-audit hash check STILL runs and original exception propagates
    guard_fail_clean = ByteIdentityGuard([("sample.data", f, sha, size)])
    with pytest.raises(ValueError, match="simulated parser failure"):
        with guard_fail_clean:
            raise ValueError("simulated parser failure")
    assert len(guard_fail_clean.snapshots) == 1
    assert guard_fail_clean.snapshots[0].byte_identical is True

    # 4. Failure path where file is modified AND an exception is raised inside the guard:
    # post-audit hash check detects the mutation, raises ProvenanceVerificationError, and preserves original exception
    guard_fail_mutated = ByteIdentityGuard([("sample.data", f, sha, size)])
    with pytest.raises(ProvenanceVerificationError, match="BYTE-IDENTITY VIOLATION") as exc_info:
        with guard_fail_mutated:
            f.write_bytes(b"mutated-during-failing-parse")
            raise RuntimeError("inner parser crash after mutation")

    assert len(guard_fail_mutated.snapshots) == 1
    assert guard_fail_mutated.snapshots[0].byte_identical is False
    assert isinstance(exc_info.value.__cause__, RuntimeError)
    assert "inner parser crash after mutation" in str(exc_info.value)
    assert getattr(exc_info.value, "original_exception", None) is exc_info.value.__cause__


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
