"""Synthetic-only regression tests for UCI-45's documented legacy archive layout.

No patient-level records or original UCI data are used by these tests.
"""
from __future__ import annotations

import json
from pathlib import Path
import zipfile

import pytest

from research.audit.exceptions import ArchiveSecurityError
from research.audit.provenance import (
    _inspect_zip_members,
    extract_authorized_archive,
    inspect_zip_archive,
)
from research.audit.registry import UCI_45_REVIEW_ONLY_HISTORICAL_MEMBERS


REQUIRED = (
    "processed.cleveland.data",
    "cleveland.data",
    "processed.hungarian.data",
    "hungarian.data",
    "processed.switzerland.data",
    "switzerland.data",
    "processed.va.data",
    "long-beach-va.data",
    "heart-disease.names",
)
EXCLUDED = ("new.data", "reprocessed.hungarian.data")
METADATA = ("Index", "WARNING", "bak")


def _auth() -> dict:
    return {
        "workflow_status": "AUTHORIZED_FOR_LOCAL_READ_ONLY_AUDIT",
        "datasets": {
            "DA-A2": {
                "title": "Synthetic archive test only",
                "uci_id": 45,
                "local_subdir": "data/raw/uci-45",
                "authorized_files": list(REQUIRED),
                "optional_documentation_files": [],
                "excluded_unapproved_files": list(EXCLUDED),
                "authorization_status": "AUTHORIZED_FOR_READ_ONLY_AUDIT",
                "authorized_by": "Synthetic maintainer",
                "authorized_date": "2026-10-22",
                "responsible_acquirer": "Synthetic maintainer",
                "audit_reviewer": "Synthetic reviewer",
                "environment": "isolated synthetic pytest temp dir",
                "purpose": "synthetic archive inspection",
                "training_authorized": False,
            }
        },
    }


def _zip(path: Path, *, extras: tuple[str, ...] = ()) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        for name in (*REQUIRED, *METADATA, *EXCLUDED, *sorted(UCI_45_REVIEW_ONLY_HISTORICAL_MEMBERS), *extras):
            zf.writestr(name, b"" if name.endswith("/") else b"synthetic-test-only")
    return path


def test_complete_historical_inventory_is_explicitly_review_gated(tmp_path: Path):
    zip_path = _zip(tmp_path / "heart+disease.zip")
    summary = _inspect_zip_members(zip_path, "DA-A2", _auth())

    assert len(summary["archive_inventory"]) == 23
    assert summary["required_files_verified"] == sorted(REQUIRED)
    assert summary["harmless_metadata_allowlist_matched"] == sorted(METADATA)
    assert summary["unexpected_entries_detected"] == []
    assert summary["excluded_files_detected"] == sorted(set(EXCLUDED) | UCI_45_REVIEW_ONLY_HISTORICAL_MEMBERS)
    nested = next(i for i in summary["archive_inventory"] if i["filename"] == "costs/Index")
    assert nested["classification"] == "review_only_historical_auxiliary_do_not_extract"

    with pytest.raises(ArchiveSecurityError, match="STOP_REQUIRES_REVIEW"):
        inspect_zip_archive(zip_path, "DA-A2", _auth())


@pytest.mark.parametrize("extra", (
    "other/",
    "costs/unknown_file",
    "arbitrary/processed.cleveland.data",
    "../escape",
    "costs/../escape",
))
def test_unsafe_or_unrecognized_nested_entries_fail_closed(tmp_path: Path, extra: str):
    archive = _zip(tmp_path / "tampered.zip", extras=(extra,))
    with pytest.raises(ArchiveSecurityError):
        _inspect_zip_members(archive, "DA-A2", _auth())


def test_unrecognized_root_member_blocks_extraction_even_with_review(tmp_path: Path):
    archive = _zip(tmp_path / "extra.zip", extras=("unapproved-extra.bin",))
    summary = _inspect_zip_members(archive, "DA-A2", _auth())
    assert summary["unexpected_entries_detected"] == ["unapproved-extra.bin"]
    with pytest.raises(ArchiveSecurityError, match="unrecognized"):
        extract_authorized_archive(archive, "DA-A2", _auth(), base_root=tmp_path)


def test_approved_selective_extraction_never_extracts_historical_members(tmp_path: Path):
    archive = _zip(tmp_path / "heart+disease.zip")
    summary = _inspect_zip_members(archive, "DA-A2", _auth())
    output_dir = tmp_path / "data" / "raw" / "uci-45"
    output_dir.mkdir(parents=True)
    review_dir = tmp_path / "data" / "manifests" / "archive_reviews"
    review_dir.mkdir(parents=True)

    relative_review = "data/manifests/archive_reviews/uci-45-archive-review.json"
    doc = {
        "governance_decision_id": "D-046",
        "dataset_id": "DA-A2",
        "review_outcome": "APPROVED_SELECTIVE_EXTRACTION_OF_AUTHORIZED_FILES_ONLY",
        "reviewed_by": "Synthetic test reviewer",
        "reviewed_at_utc": "2026-10-22T13:00:00Z",
        "archive_filename": summary["archive_filename"],
        "archive_sha256": summary["archive_sha256"],
        "archive_size_bytes": summary["archive_size_bytes"],
        "reviewed_archive_inventory": sorted(i["filename"] for i in summary["archive_inventory"]),
        "excluded_historical_files_acknowledged_do_not_extract": summary["excluded_files_detected"],
        "authorized_files_approved_for_extraction": summary["required_files_verified"],
    }
    review_path = tmp_path / relative_review
    review_path.write_text(json.dumps(doc), encoding="utf-8")
    result = extract_authorized_archive(
        archive,
        "DA-A2",
        _auth(),
        base_root=tmp_path,
        repo_root=tmp_path,
        review_approval_path=relative_review,
    )

    assert result["status"] == "OK_AUTHORIZED_FILES_EXTRACTED"
    assert result["human_archive_review_verified"] is True
    assert len(result["extracted_files"]) == 9
    assert {p.name for p in output_dir.iterdir()} == set(REQUIRED)
    assert not (output_dir / "costs").exists()
    assert not (output_dir / "Index").exists()
    assert not (output_dir / "new.data").exists()
    assert result["excluded_files_skipped"] == summary["excluded_files_detected"]

    with pytest.raises(ArchiveSecurityError, match="Refusing to overwrite"):
        extract_authorized_archive(
            archive, "DA-A2", _auth(),
            base_root=tmp_path, repo_root=tmp_path,
            review_approval_path=relative_review,
        )


@pytest.mark.parametrize("tamper", ("archive_sha256", "reviewed_archive_inventory",
                                     "excluded_historical_files_acknowledged_do_not_extract",
                                     "authorized_files_approved_for_extraction"))
def test_review_approval_requires_exact_archive_and_exclusions(tmp_path: Path, tamper: str):
    archive = _zip(tmp_path / "heart+disease.zip")
    summary = _inspect_zip_members(archive, "DA-A2", _auth())
    (tmp_path / "data" / "raw" / "uci-45").mkdir(parents=True)
    review_dir = tmp_path / "data" / "manifests" / "archive_reviews"
    review_dir.mkdir(parents=True)
    doc = {
        "governance_decision_id": "D-046",
        "dataset_id": "DA-A2",
        "review_outcome": "APPROVED_SELECTIVE_EXTRACTION_OF_AUTHORIZED_FILES_ONLY",
        "reviewed_by": "Synthetic test reviewer",
        "reviewed_at_utc": "2026-10-22T13:00:00Z",
        "archive_filename": summary["archive_filename"],
        "archive_sha256": summary["archive_sha256"],
        "archive_size_bytes": summary["archive_size_bytes"],
        "reviewed_archive_inventory": sorted(i["filename"] for i in summary["archive_inventory"]),
        "excluded_historical_files_acknowledged_do_not_extract": summary["excluded_files_detected"],
        "authorized_files_approved_for_extraction": summary["required_files_verified"],
    }
    doc[tamper] = "00" * 32 if tamper == "archive_sha256" else []
    path = review_dir / "uci-45-archive-review.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ArchiveSecurityError):
        extract_authorized_archive(
            archive, "DA-A2", _auth(), base_root=tmp_path, repo_root=tmp_path,
            review_approval_path="data/manifests/archive_reviews/uci-45-archive-review.json",
        )
    assert list((tmp_path / "data" / "raw" / "uci-45").iterdir()) == []
