"""Synthetic-only aggregate UCI-45 raw/processed correspondence tests.

No clinical data, patient rows, or benchmark metrics are committed.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from research.audit.cli import REPO_ROOT, run_local_dataset_audit
from research.audit.exceptions import PatientLevelLeakageError
from research.audit.registry import UCI_45_CONVENTIONAL_14_COLUMNS
from research.audit.reporting import validate_strict_metadata_report_schema
from research.audit.synthetic_fixtures import materialize_synthetic_audit_suite
from research.audit.validators import (
    audit_uci_45_processed_file,
    audit_uci_45_raw_file,
    compare_uci_45_raw_and_processed,
)


def _files(tmp_path: Path) -> tuple[Path, Path]:
    materialize_synthetic_audit_suite(tmp_path, authorize_all=True)
    root = tmp_path / "data/raw/uci-45"
    return root / "cleveland.data", root / "processed.cleveland.data"


def _compare(raw: Path, processed: Path) -> dict:
    return compare_uci_45_raw_and_processed(
        "cleveland",
        audit_uci_45_raw_file(raw),
        audit_uci_45_processed_file(processed),
    )


def test_identical_synthetic_rows_match_positional_and_unordered(tmp_path: Path):
    raw, processed = _files(tmp_path)
    diag = _compare(raw, processed)
    assert diag["positional_13_predictor_matches"] == 6
    assert diag["unordered_13_predictor_multiset_matches"] == 6
    assert diag["unordered_14_col_exact_num_multiset_matches"] == 6
    assert diag["unordered_14_col_binary_num_multiset_matches"] == 6
    assert set(diag["per_feature_positional_equal_counts"]) == set(UCI_45_CONVENTIONAL_14_COLUMNS[:13])
    assert all(n == 6 for n in diag["per_feature_unordered_value_multiset_matches"].values())


def test_reordered_rows_keep_unordered_overlaps_but_lose_positional(tmp_path: Path):
    raw, processed = _files(tmp_path)
    lines = processed.read_text(encoding="utf-8").splitlines()
    lines[0], lines[-1] = lines[-1], lines[0]
    processed.write_text("\n".join(lines) + "\n", encoding="utf-8")

    diag = _compare(raw, processed)
    assert diag["positional_13_predictor_matches"] < 6
    assert diag["unordered_13_predictor_multiset_matches"] == 6
    assert diag["unordered_14_col_exact_num_multiset_matches"] == 6
    assert diag["unordered_14_col_binary_num_multiset_matches"] == 6
    assert diag["per_feature_unordered_value_multiset_matches"]["age"] == 6


def test_modified_predictor_reduces_unordered_matches(tmp_path: Path):
    raw, processed = _files(tmp_path)
    lines = processed.read_text(encoding="utf-8").splitlines()
    cells = lines[-1].split(",")
    cells[0] = str(int(cells[0]) + 11)
    lines[-1] = ",".join(cells)
    processed.write_text("\n".join(lines) + "\n", encoding="utf-8")
    diag = _compare(raw, processed)

    assert diag["unordered_13_predictor_multiset_matches"] == 5
    assert diag["unordered_14_col_exact_num_multiset_matches"] == 5
    assert diag["per_feature_unordered_value_multiset_matches"]["age"] == 5
    assert diag["per_feature_unordered_value_multiset_matches"]["sex"] == 6


def test_duplicate_counted_only_to_minimum_multiplicity(tmp_path: Path):
    raw, processed = _files(tmp_path)
    lines = processed.read_text(encoding="utf-8").splitlines()
    lines[-1] = lines[0]
    processed.write_text("\n".join(lines) + "\n", encoding="utf-8")
    diag = _compare(raw, processed)

    # Raw already contains the profile twice; processed now contains it 3x.
    assert diag["unordered_13_predictor_multiset_matches"] == 5
    assert diag["unordered_14_col_exact_num_multiset_matches"] == 5
    assert diag["unordered_13_predictor_multiset_matches"] <= 6


def test_strict_report_rejects_identity_or_bad_count_fields(tmp_path: Path):
    suite = materialize_synthetic_audit_suite(tmp_path, authorize_all=True)
    report, _ = run_local_dataset_audit(
        repo_root=REPO_ROOT,
        base_data_parent=tmp_path,
        auth_manifest_path=Path(suite["auth_manifest_path"]),
        provenance_manifest_path=Path(suite["provenance_manifest_path"]),
        requested_datasets=("DA-A2",),
        is_synthetic_fixture_run=True,
        allow_external_tmp_root=tmp_path,
    )
    validate_strict_metadata_report_schema(report)

    bad = deepcopy(report)
    corr = bad["dataset_audits"]["DA-A2"]["raw_vs_processed_correspondence"]["hungarian"]
    corr["patient_matching_pairs"] = [[1, 2]]
    with pytest.raises(PatientLevelLeakageError):
        validate_strict_metadata_report_schema(bad)

    bad = deepcopy(report)
    corr = bad["dataset_audits"]["DA-A2"]["raw_vs_processed_correspondence"]["hungarian"]
    corr["unordered_13_predictor_multiset_matches"] = corr["raw_row_count"] + 1
    with pytest.raises(PatientLevelLeakageError):
        validate_strict_metadata_report_schema(bad)

    bad = deepcopy(report)
    corr = bad["dataset_audits"]["DA-A2"]["raw_vs_processed_correspondence"]["hungarian"]
    corr["per_feature_unordered_value_multiset_matches"]["age"] = "65"
    with pytest.raises(PatientLevelLeakageError):
        validate_strict_metadata_report_schema(bad)
