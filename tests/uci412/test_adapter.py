"""Fail-closed tests for the strict UCI-412 workbook adapter.

All rows are synthetic. Every rejection path asserts that the error message does
not echo a cell value.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from research.audit.xlsx_reader import SheetData
from research.uci412 import adapter
from research.uci412.adapter import (
    load_authorized_dataset,
    read_source_snapshot,
    sha256_bytes,
    validate_workbook_structure,
)
from research.uci412.config import DEFAULT_CONFIG
from research.uci412.errors import ProvenanceError, SourceFormatError
from research.uci412.synthetic import write_synthetic_workbook

from tests.uci412.conftest import dataset_from_rows, synthetic_rows


def _headers_and_rows() -> tuple[tuple[str, ...], list[tuple[Any, ...]]]:
    headers, rows = synthetic_rows(DEFAULT_CONFIG)
    return headers, list(rows)


def _mutated(column: str, value: Any, row_index: int = 0, *, headers=None, rows=None):
    if headers is None:
        headers, rows = _headers_and_rows()
    rows = [list(row) for row in rows]
    rows[row_index][headers.index(column)] = value
    return headers, [tuple(row) for row in rows]


def test_registered_workbook_parses_to_the_admitted_panel() -> None:
    headers, rows = _headers_and_rows()
    dataset = dataset_from_rows(headers, rows)
    assert dataset.row_count == 303
    assert dataset.X.shape == (303, 16)
    assert dataset.y.dtype == np.int8
    assert dataset.class_counts == ((0, 87), (1, 216))
    assert dataset.audit["row_count"] == 303
    assert dataset.audit["column_count"] == 56
    assert dataset.audit["value_repair_or_row_deletion_performed"] is False
    assert dataset.audit["patient_level_values_retained_in_audit_object"] is False
    assert not dataset.X.flags.writeable
    assert not dataset.y.flags.writeable


def test_audit_object_holds_aggregates_only() -> None:
    headers, rows = _headers_and_rows()
    dataset = dataset_from_rows(headers, rows)
    audit = dataset.audit
    for key in ("observed_category_token_counts", "blank_cell_counts_by_admitted_column"):
        assert isinstance(audit[key], dict)
        for value in audit[key].values():
            if isinstance(value, dict):
                assert all(isinstance(count, int) for count in value.values())
            else:
                assert isinstance(value, int)
    assert "rows" not in audit
    assert "X" not in audit


def test_blank_cells_become_fold_local_nan_and_are_counted() -> None:
    headers, rows = _headers_and_rows()
    rows = [list(row) for row in rows]
    rows[5][headers.index("BMI")] = None
    rows[6][headers.index("DM")] = None
    dataset = dataset_from_rows(headers, [tuple(row) for row in rows])
    assert np.isnan(dataset.X[:, DEFAULT_CONFIG.feature_names.index("BMI")]).sum() == 1
    assert dataset.audit["blank_cell_counts_by_admitted_column"]["BMI"] == 1
    assert dataset.audit["blank_cell_counts_by_admitted_column"]["DM"] == 1


def test_a_fully_blank_admitted_column_fails_closed() -> None:
    headers, rows = _headers_and_rows()
    rows = [list(row) for row in rows]
    for row in rows:
        row[headers.index("Age")] = None
    with pytest.raises(SourceFormatError, match="no observed values"):
        dataset_from_rows(headers, [tuple(row) for row in rows])


def test_exact_column_set_is_required() -> None:
    headers, rows = _headers_and_rows()
    with pytest.raises(SourceFormatError, match="registered UCI-412 profile"):
        dataset_from_rows(headers[:-1], [row[:-1] for row in rows])


def test_duplicate_headers_fail_closed() -> None:
    headers, rows = _headers_and_rows()
    duplicated = list(headers)
    duplicated[1] = duplicated[0]
    with pytest.raises(SourceFormatError, match="duplicate"):
        dataset_from_rows(tuple(duplicated), rows)


def test_unregistered_extra_column_fails_closed() -> None:
    headers, rows = _headers_and_rows()
    with pytest.raises(SourceFormatError, match="unregistered or prohibited"):
        dataset_from_rows(headers + ("LAD",), [row + (0,) for row in rows])


@pytest.mark.parametrize("column", ["LAD", "LCX", "RCA", "num", "ca", "id"])
def test_angiography_and_identifier_columns_are_rejected(column: str) -> None:
    headers, rows = _headers_and_rows()
    with pytest.raises(SourceFormatError):
        dataset_from_rows((*headers, column), [(*row, 0) for row in rows])


def test_label_case_and_whitespace_variants_are_rejected() -> None:
    for bad in ("CAD", "cad", "Normal ", " Cad", "Normal\n"):
        headers, rows = _mutated("Cath", bad)
        with pytest.raises(SourceFormatError, match="reviewed|whitespace"):
            dataset_from_rows(headers, rows)


@pytest.mark.parametrize("bad", [1, 1.0, None, "", "1", "0", "No", "Yes"])
def test_non_target_labels_are_rejected(bad: Any) -> None:
    headers, rows = _mutated("Cath", bad)
    with pytest.raises(SourceFormatError):
        dataset_from_rows(headers, rows)


def test_class_count_drift_is_rejected() -> None:
    headers, rows = _headers_and_rows()
    rows = [list(row) for row in rows]
    index = headers.index("Cath")
    rows[0][index] = "Cad" if rows[0][index] == "Normal" else "Normal"
    with pytest.raises(SourceFormatError, match="class counts|reviewed"):
        dataset_from_rows(headers, [tuple(r) for r in rows])


def test_row_count_drift_is_rejected() -> None:
    headers, rows = _headers_and_rows()
    with pytest.raises(SourceFormatError, match="data rows"):
        dataset_from_rows(headers, rows[:-1])


@pytest.mark.parametrize("column", ["Sex", "DM", "Typical Chest Pain", "Age"])
def test_unknown_categorical_tokens_are_rejected_without_echo(column: str) -> None:
    sentinel = "SENTINEL_PATIENT_VALUE_9931"
    headers, rows = _mutated(column, sentinel)
    with pytest.raises(SourceFormatError) as excinfo:
        dataset_from_rows(headers, rows)
    assert sentinel not in str(excinfo.value)


def test_uci45_missing_markers_are_rejected() -> None:
    for token in ("?", "-9", -9.0):
        headers, rows = _mutated("Age", token)
        with pytest.raises(SourceFormatError):
            dataset_from_rows(headers, rows)


@pytest.mark.parametrize("column,value", [("Age", "58"), ("BP", "120"), ("PR", "seventy")])
def test_text_in_numeric_columns_is_never_coerced(column: str, value: Any) -> None:
    headers, rows = _mutated(column, value)
    with pytest.raises(SourceFormatError):
        dataset_from_rows(headers, rows)


def test_numeric_token_in_a_text_categorical_column_is_rejected() -> None:
    # DLP keeps its registered text vocabulary; a bare numeric cell must not be
    # coerced into a token, and no numeric conversion is registered for it.
    headers, rows = _mutated("DLP", 1)
    with pytest.raises(SourceFormatError, match="vocabulary"):
        dataset_from_rows(headers, rows)


@pytest.mark.parametrize(
    "column,value",
    [("Age", 0), ("Age", 130), ("Age", -1), ("BMI", 3.0), ("BMI", 90.0), ("BP", 10), ("PR", 5)],
)
def test_impossible_numeric_values_are_rejected(column: str, value: Any) -> None:
    headers, rows = _mutated(column, value)
    with pytest.raises(SourceFormatError, match="plausibility"):
        dataset_from_rows(headers, rows)


def test_values_outside_the_source_reported_range_warn_without_rejecting() -> None:
    headers, rows = _mutated("Age", 95)
    dataset = dataset_from_rows(headers, rows)
    assert dataset.audit["out_of_source_reported_typical_range_counts"]["Age"] == 1
    assert dataset.row_count == 303


def test_header_reordering_is_accepted_and_recorded() -> None:
    headers, rows = _headers_and_rows()
    order = list(reversed(range(len(headers))))
    reordered_headers = tuple(headers[index] for index in order)
    reordered_rows = [tuple(row[index] for index in order) for row in rows]
    dataset = dataset_from_rows(reordered_headers, reordered_rows)
    assert dataset.audit["header_order_matches_registered_profile"] is False
    assert dataset.class_counts == ((0, 87), (1, 216))


def test_two_data_sheets_fail_closed() -> None:
    headers, rows = _headers_and_rows()
    other = SheetData(name="Second", headers=headers, rows=tuple(rows))
    from research.uci412.adapter import sheet_from_rows

    workbook = sheet_from_rows(headers, tuple(rows), other_sheets=(other,))
    with pytest.raises(SourceFormatError):
        validate_workbook_structure(workbook)


def test_header_only_auxiliary_sheet_is_tolerated() -> None:
    headers, rows = _headers_and_rows()
    from research.uci412.adapter import sheet_from_rows

    auxiliary = SheetData(name="Auxiliary", headers=("Note",), rows=())
    workbook = sheet_from_rows(headers, tuple(rows), other_sheets=(auxiliary,))
    parsed = validate_workbook_structure(workbook)
    assert parsed.other_sheet_count == 1


def test_snapshot_is_byte_stable_and_hash_bound(tmp_path: Path) -> None:
    source = write_synthetic_workbook(tmp_path / "Z-Alizadeh sani dataset.xlsx")
    original = source.read_bytes()
    digest = hashlib.sha256(original).hexdigest()
    snapshot = read_source_snapshot(
        source, expected_sha256=digest, expected_size_bytes=len(original)
    )
    assert snapshot.sha256 == digest
    assert snapshot.size_bytes == len(original)
    assert source.read_bytes() == original


def test_snapshot_rejects_hash_and_size_mismatch(tmp_path: Path) -> None:
    source = write_synthetic_workbook(tmp_path / "Z-Alizadeh sani dataset.xlsx")
    original = source.read_bytes()
    with pytest.raises(ProvenanceError, match="SHA-256"):
        read_source_snapshot(source, expected_sha256="0" * 64)
    with pytest.raises(ProvenanceError, match="byte size"):
        read_source_snapshot(
            source,
            expected_sha256=hashlib.sha256(original).hexdigest(),
            expected_size_bytes=len(original) + 1,
        )


def test_snapshot_refuses_a_renamed_copy(tmp_path: Path) -> None:
    renamed = tmp_path / "cleveland.xlsx"
    renamed.write_bytes(b"not the authorized file")
    with pytest.raises(SourceFormatError, match="exact registered"):
        read_source_snapshot(renamed, expected_sha256="0" * 64)


def test_load_authorized_dataset_reads_the_exact_hash_bound_bytes(tmp_path: Path) -> None:
    source = write_synthetic_workbook(tmp_path / "Z-Alizadeh sani dataset.xlsx")
    original = source.read_bytes()
    digest = hashlib.sha256(original).hexdigest()
    snapshot, dataset = load_authorized_dataset(
        source, expected_sha256=digest, expected_size_bytes=len(original)
    )
    assert snapshot.sha256 == digest
    assert dataset.row_count == 303
    assert source.read_bytes() == original
    assert sha256_bytes(source.read_bytes()) == digest


def test_load_authorized_dataset_rejects_a_mutated_workbook(tmp_path: Path) -> None:
    source = write_synthetic_workbook(tmp_path / "Z-Alizadeh sani dataset.xlsx")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    source.write_bytes(source.read_bytes() + b"tamper")
    with pytest.raises(ProvenanceError):
        load_authorized_dataset(source, expected_sha256=digest)


def test_parse_requires_the_registered_panel_order() -> None:
    headers, rows = _headers_and_rows()
    dataset = dataset_from_rows(headers, rows)
    with pytest.raises(SourceFormatError):
        adapter.Uci412Dataset(
            X=dataset.X,
            y=dataset.y,
            feature_names=tuple(reversed(dataset.feature_names)),
            row_count=dataset.row_count,
            class_counts=dataset.class_counts,
        )
