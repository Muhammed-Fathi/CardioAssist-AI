"""Tests for dataset parsing, null vs zero semantics, delimiters, raw-vs-processed confusion, targets, and leakage."""
from __future__ import annotations

from pathlib import Path
import zipfile

import pytest

from research.audit.exceptions import (
    FormatValidationError,
    LeakageColumnError,
    RawVsProcessedConfusionError,
    TargetOrCodingValidationError,
)
from research.audit.synthetic_fixtures import (
    build_synthetic_uci_412_rows,
    get_uci_412_headers,
    materialize_synthetic_audit_suite,
)
from research.audit.validators import (
    audit_uci_45_names_file,
    audit_uci_45_processed_file,
    audit_uci_45_raw_file,
    audit_uci_145_statlog_file,
    audit_uci_412_or_411_workbook,
    compare_uci_45_raw_and_processed,
)
from research.audit.xlsx_reader import write_synthetic_xlsx


@pytest.mark.parametrize("prefer_openpyxl", [True, False])
@pytest.mark.parametrize("include_bbb,expected_pred_count,expected_total", [(True, 55, 56), (False, 54, 55)])
def test_uci_412_workbook_parsing_and_feature_count_reconciliation(
    tmp_path: Path,
    prefer_openpyxl: bool,
    include_bbb: bool,
    expected_pred_count: int,
    expected_total: int,
) -> None:
    headers = get_uci_412_headers(include_bbb=include_bbb, include_arteries=False)
    rows = build_synthetic_uci_412_rows(headers, include_arteries=False)
    wb_path = tmp_path / "Z-Alizadeh sani dataset.xlsx"
    write_synthetic_xlsx(wb_path, [("Sheet1", headers, rows)])

    parsed = audit_uci_412_or_411_workbook(
        wb_path,
        dataset_id="DA-A1",
        prefer_openpyxl=prefer_openpyxl,
    )
    rep = parsed["report"]
    assert rep["row_count"] == 6
    rec = rep["feature_count_reconciliation"]
    assert rec["total_columns_in_sheet"] == expected_total
    assert rec["predictor_columns_count"] == expected_pred_count
    assert rec["bbb_column_present"] is include_bbb
    assert rep["class_distribution"]["raw_counts"] == {"CAD": 4, "Normal": 2}
    assert set(rep["leakage_and_availability_flags"]["echo_features_requiring_timing_ruling"]) == {
        "EF-TTE",
        "Region RWMA",
        "VHD",
    }


def test_uci_412_rejects_injected_leakage_or_unknown_columns_or_bad_targets(tmp_path: Path) -> None:
    # 1. Injecting UCI-411 LAD column into DA-A1 UCI-412 must fail closed with LeakageColumnError
    headers_with_lad = get_uci_412_headers(include_bbb=True, include_arteries=False)[:-1] + ["LAD", "Cath"]
    rows_with_lad = [r[:-1] + ["Stenotic", r[-1]] for r in build_synthetic_uci_412_rows(headers_with_lad[:-2] + ["Cath"])]
    bad_lad_path = tmp_path / "Z-Alizadeh sani dataset.xlsx"
    write_synthetic_xlsx(bad_lad_path, [("Sheet1", headers_with_lad, rows_with_lad)])
    with pytest.raises(LeakageColumnError, match="LAD"):
        audit_uci_412_or_411_workbook(bad_lad_path, dataset_id="DA-A1")

    # 2. Injecting unrecognized column fails closed with FormatValidationError
    headers_unknown = get_uci_412_headers(include_bbb=True)[:-1] + ["MysteryBiomarker", "Cath"]
    rows_unknown = [r[:-1] + [1, r[-1]] for r in build_synthetic_uci_412_rows(headers_unknown[:-2] + ["Cath"])]
    write_synthetic_xlsx(bad_lad_path, [("Sheet1", headers_unknown, rows_unknown)])
    with pytest.raises(FormatValidationError, match="Unrecognized column"):
        audit_uci_412_or_411_workbook(bad_lad_path, dataset_id="DA-A1")

    # 3. Invalid target value in Cath fails closed with TargetOrCodingValidationError
    headers_ok = get_uci_412_headers(include_bbb=True)
    rows_bad_target = build_synthetic_uci_412_rows(headers_ok)
    rows_bad_target[0][-1] = "Borderline50"
    write_synthetic_xlsx(bad_lad_path, [("Sheet1", headers_ok, rows_bad_target)])
    with pytest.raises(TargetOrCodingValidationError, match="Unexpected target category"):
        audit_uci_412_or_411_workbook(bad_lad_path, dataset_id="DA-A1")


def test_corrupt_xlsx_and_xxe_rejected(tmp_path: Path) -> None:
    not_a_zip = tmp_path / "Z-Alizadeh sani dataset.xlsx"
    not_a_zip.write_text("not a zip archive", encoding="utf-8")
    with pytest.raises(FormatValidationError, match="Corrupt or non-ZIP"):
        audit_uci_412_or_411_workbook(not_a_zip, dataset_id="DA-A1")

    # XML DTD / Entity bomb inside .xlsx rejected
    xxe_zip = tmp_path / "Z-Alizadeh sani dataset.xlsx"
    with zipfile.ZipFile(xxe_zip, "w") as zf:
        zf.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">]><workbook/>',
        )
    with pytest.raises(FormatValidationError, match="DTD/ENTITY"):
        audit_uci_412_or_411_workbook(xxe_zip, dataset_id="DA-A1")


def test_uci_45_missing_values_and_null_vs_zero_semantics(tmp_path: Path) -> None:
    proc_file = tmp_path / "processed.switzerland.data"
    # Row 1: chol=0 (suspicious zero, NOT missing), oldpeak=-0.5 (negative oldpeak), ca=? (missing), thal=-9.0 (sentinel)
    # Row 2: fbs=0, restecg=0, exang=0, ca=0, num=0 (all valid 0 values, NONE missing!)
    proc_file.write_text(
        "65,1,4,115,0,0,0,93,1,-0.5,2,?,-9.0,1\n"
        "52,0,2,120,210,0,0,160,0,0.0,1,0,3,0\n",
        encoding="utf-8",
    )
    parsed = audit_uci_45_processed_file(proc_file)
    rep = parsed["report"]
    assert rep["row_count"] == 2
    # Only ca (?) and thal (-9.0) in row 1 are missing; 0s in chol, fbs, sex, restecg, exang, oldpeak, ca, num are NOT missing!
    assert rep["missingness"]["total_missing_cells"] == 2
    assert rep["missingness"]["per_column_missing"]["ca"]["question_mark"] == 1
    assert rep["missingness"]["per_column_missing"]["thal"]["minus_nine_sentinel"] == 1
    assert "chol" not in rep["missingness"]["per_column_missing"]
    assert "fbs" not in rep["missingness"]["per_column_missing"]

    # chol=0 and oldpeak=-0.5 and thal -9.0 sentinel are recorded in suspicious_values
    assert rep["suspicious_values"]["chol_zero_or_nonpositive"] == 1
    assert rep["suspicious_values"]["oldpeak_negative"] == 1
    assert rep["suspicious_values"]["thal_minus_nine_sentinel"] == 1


def test_uci_45_wrong_delimiter_column_count_and_header_rejected(tmp_path: Path) -> None:
    proc_file = tmp_path / "processed.cleveland.data"

    # Semicolon delimiter rejected
    proc_file.write_text("63;1;1;145;233;1;2;150;0;2.3;3;0;6;0\n", encoding="utf-8")
    with pytest.raises(FormatValidationError, match="delimiter"):
        audit_uci_45_processed_file(proc_file)

    # Wrong column count (13 instead of 14) rejected
    proc_file.write_text("63,1,1,145,233,1,2,150,0,2.3,3,0,6\n", encoding="utf-8")
    with pytest.raises(FormatValidationError, match="13 columns"):
        audit_uci_45_processed_file(proc_file)

    # Unexpected CSV header row rejected
    proc_file.write_text(
        "age,sex,cp,trestbps,chol,fbs,restecg,thalach,exang,oldpeak,slope,ca,thal,num\n"
        "63,1,1,145,233,1,2,150,0,2.3,3,0,6,0\n",
        encoding="utf-8",
    )
    with pytest.raises(FormatValidationError, match="headerless"):
        audit_uci_45_processed_file(proc_file)


def test_raw_versus_processed_confusion_detected_both_ways(tmp_path: Path) -> None:
    suite = materialize_synthetic_audit_suite(tmp_path, authorize_all=True)
    raw_clev_bytes = (tmp_path / "data/raw/uci-45/cleveland.data").read_bytes()
    proc_clev_bytes = (tmp_path / "data/raw/uci-45/processed.cleveland.data").read_bytes()

    # 1. Supply raw 76-attribute content in processed.cleveland.data
    confused_proc = tmp_path / "processed.cleveland.data"
    confused_proc.write_bytes(raw_clev_bytes)
    with pytest.raises(RawVsProcessedConfusionError):
        audit_uci_45_processed_file(confused_proc)

    # 2. Supply processed 14-column content in cleveland.data
    confused_raw = tmp_path / "cleveland.data"
    confused_raw.write_bytes(proc_clev_bytes)
    with pytest.raises(RawVsProcessedConfusionError):
        audit_uci_45_raw_file(confused_raw)


def test_uci_45_raw_and_processed_correspondence_and_truncation_detection(tmp_path: Path) -> None:
    suite = materialize_synthetic_audit_suite(tmp_path, authorize_all=True)
    proc_p = tmp_path / "data/raw/uci-45/processed.cleveland.data"
    raw_p = tmp_path / "data/raw/uci-45/cleveland.data"
    names_p = tmp_path / "data/raw/uci-45/heart-disease.names"

    p_res = audit_uci_45_processed_file(proc_p)
    r_res = audit_uci_45_raw_file(raw_p)
    corr = compare_uci_45_raw_and_processed("cleveland", r_res, p_res)
    assert corr["row_counts_equal"] is True
    assert corr["positional_13_predictor_matches"] == 6
    assert corr["positional_14_col_exact_num_matches"] == 6

    names_res = audit_uci_45_names_file(names_p)
    assert names_res["documents_76_attributes"] is True
    assert names_res["contains_patient_rows"] is False

    # Truncated raw 76-attribute file must fail closed
    trunc_raw = tmp_path / "cleveland.data"
    trunc_raw.write_text("1 2 63 1 1 1 1", encoding="utf-8")
    with pytest.raises(FormatValidationError, match="multiple of 76"):
        audit_uci_45_raw_file(trunc_raw)


def test_unexpected_target_mappings_and_invalid_codings_rejected(tmp_path: Path) -> None:
    proc_file = tmp_path / "processed.cleveland.data"
    # Target num=5 is outside {0, 1, 2, 3, 4}
    proc_file.write_text("63,1,1,145,233,1,2,150,0,2.3,3,0,6,5\n", encoding="utf-8")
    with pytest.raises(TargetOrCodingValidationError, match="num"):
        audit_uci_45_processed_file(proc_file)

    # Invalid predictor coding cp=9 is tabulated in invalid_codings_by_column and rejected under strict_coding
    proc_file.write_text("63,1,9,145,233,1,2,150,0,2.3,3,0,6,0\n", encoding="utf-8")
    res = audit_uci_45_processed_file(proc_file, strict_coding=False)
    assert res["report"]["invalid_codings_by_column"]["cp"] == 1
    with pytest.raises(TargetOrCodingValidationError, match="cp"):
        audit_uci_45_processed_file(proc_file, strict_coding=True)

    # Statlog target coding must be {1, 2}; target=0 (UCI-45 coding) must fail closed
    stat_file = tmp_path / "heart.dat"
    stat_file.write_text("63.0 1.0 1.0 145.0 233.0 1.0 2.0 150.0 0.0 2.3 3.0 0.0 6.0 0\n", encoding="utf-8")
    with pytest.raises(TargetOrCodingValidationError, match="Statlog target coding"):
        audit_uci_145_statlog_file(stat_file)

@pytest.mark.parametrize("prefer_openpyxl", [True, False])
def test_uci_412_header_only_auxiliary_sheet_is_not_a_second_cohort(
    tmp_path: Path,
    prefer_openpyxl: bool,
) -> None:
    """Regress official UCI-412 shape: 303-row data sheet plus header-only 100-col sheet."""
    headers = get_uci_412_headers(include_bbb=True)
    rows = build_synthetic_uci_412_rows(headers)
    # Extra headers are metadata only; they must never become candidate predictors.
    unused_headers = headers + [f"UnusedHeader{i}" for i in range(100 - len(headers))]
    wb_path = tmp_path / "Z-Alizadeh sani dataset.xlsx"
    write_synthetic_xlsx(
        wb_path,
        [
            ("Sheet 1 - Table 1", headers, rows),
            ("Sheet1", unused_headers, []),
        ],
    )
    original_bytes = wb_path.read_bytes()

    parsed = audit_uci_412_or_411_workbook(
        wb_path, dataset_id="DA-A1", prefer_openpyxl=prefer_openpyxl
    )
    rep = parsed["report"]
    assert rep["sheet_names"] == ["Sheet 1 - Table 1", "Sheet1"]
    assert rep["inspected_sheet"] == "Sheet 1 - Table 1"
    assert rep["row_count"] == len(rows)
    assert rep["class_distribution"]["raw_counts"] == {"CAD": 4, "Normal": 2}
    assert rep["feature_count_reconciliation"]["total_columns_in_sheet"] == 56
    assert "Excluded 1 header-only and 0 fully blank worksheet(s)" in (
        rep["feature_count_reconciliation"]["discrepancy_explanation"]
    )
    assert wb_path.read_bytes() == original_bytes


@pytest.mark.parametrize("prefer_openpyxl", [True, False])
def test_uci_412_rejects_multiple_data_bearing_sheets(
    tmp_path: Path,
    prefer_openpyxl: bool,
) -> None:
    """Never pick a sheet arbitrarily or double-count records across sheets."""
    headers = get_uci_412_headers(include_bbb=True)
    rows = build_synthetic_uci_412_rows(headers)
    wb_path = tmp_path / "Z-Alizadeh sani dataset.xlsx"
    write_synthetic_xlsx(
        wb_path,
        [("Sheet 1 - Table 1", headers, rows), ("Sheet1", headers, rows[:1])],
    )

    with pytest.raises(FormatValidationError, match="exactly 1 data sheet with patient rows"):
        audit_uci_412_or_411_workbook(
            wb_path, dataset_id="DA-A1", prefer_openpyxl=prefer_openpyxl
        )


@pytest.mark.parametrize("prefer_openpyxl", [True, False])
def test_uci_412_rejects_only_header_rows_and_no_patient_cohort(
    tmp_path: Path,
    prefer_openpyxl: bool,
) -> None:
    headers = get_uci_412_headers(include_bbb=True)
    wb_path = tmp_path / "Z-Alizadeh sani dataset.xlsx"
    write_synthetic_xlsx(
        wb_path,
        [("Sheet 1 - Table 1", headers, []), ("Sheet1", headers, [])],
    )

    with pytest.raises(FormatValidationError, match="found 0"):
        audit_uci_412_or_411_workbook(
            wb_path, dataset_id="DA-A1", prefer_openpyxl=prefer_openpyxl
        )


@pytest.mark.parametrize("prefer_openpyxl", [True, False])
def test_uci_412_leakage_still_rejected_with_header_only_auxiliary_sheet(
    tmp_path: Path,
    prefer_openpyxl: bool,
) -> None:
    headers = get_uci_412_headers(include_bbb=True)
    injected_headers = headers[:-1] + ["LAD", "Cath"]
    rows = build_synthetic_uci_412_rows(injected_headers)
    wb_path = tmp_path / "Z-Alizadeh sani dataset.xlsx"
    write_synthetic_xlsx(
        wb_path,
        [("Sheet 1 - Table 1", injected_headers, rows), ("Sheet1", headers, [])],
    )

    with pytest.raises(LeakageColumnError, match="LAD"):
        audit_uci_412_or_411_workbook(
            wb_path, dataset_id="DA-A1", prefer_openpyxl=prefer_openpyxl
        )


@pytest.mark.parametrize("prefer_openpyxl", [True, False])
def test_uci_411_header_only_auxiliary_sheet_preserves_artery_leakage_flags(
    tmp_path: Path,
    prefer_openpyxl: bool,
) -> None:
    headers = get_uci_412_headers(include_bbb=True, include_arteries=True)
    rows = build_synthetic_uci_412_rows(headers, include_arteries=True)
    wb_path = tmp_path / "extention of Z-Alizadeh sani dataset.xlsx"
    write_synthetic_xlsx(
        wb_path,
        [("Data", headers, rows), ("Headers Only", headers, [])],
    )

    rep = audit_uci_412_or_411_workbook(
        wb_path, dataset_id="DA-B1", prefer_openpyxl=prefer_openpyxl
    )["report"]
    assert rep["row_count"] == len(rows)
    assert sorted(rep["leakage_and_availability_flags"]["artery_leakage_columns_present"]) == [
        "LAD", "LCX", "RCA"
    ]


@pytest.mark.parametrize("prefer_openpyxl", [True, False])
@pytest.mark.parametrize(
    "dataset_id,filename,include_arteries",
    [
        ("DA-A1", "Z-Alizadeh sani dataset.xlsx", False),
        ("DA-B1", "extention of Z-Alizadeh sani dataset.xlsx", True),
    ],
)
def test_uci_cad_alias_explicitly_harmonized_without_source_mutation(
    tmp_path: Path,
    prefer_openpyxl: bool,
    dataset_id: str,
    filename: str,
    include_arteries: bool,
) -> None:
    """Accept only observed 'Cad' alias; count canonical labels and preserve originals."""
    headers = get_uci_412_headers(include_bbb=True, include_arteries=include_arteries)
    rows = build_synthetic_uci_412_rows(headers, include_arteries=include_arteries)
    rows[0][-1] = "Cad"
    rows[1][-1] = "Cad"
    wb_path = tmp_path / filename
    write_synthetic_xlsx(
        wb_path,
        [("Sheet 1 - Table 1", headers, rows), ("Sheet1", headers, [])],
    )
    original = wb_path.read_bytes()

    parsed = audit_uci_412_or_411_workbook(
        wb_path, dataset_id=dataset_id, prefer_openpyxl=prefer_openpyxl
    )
    rep = parsed["report"]
    assert rep["row_count"] == len(rows)
    assert rep["class_distribution"]["raw_counts"] == {"CAD": 4, "Normal": 2}
    assert all(
        row["Cath"] in {"CAD", "Normal"}
        for row in parsed["normalized_rows"]
    )
    assert parsed["normalized_rows"][0]["Cath"] == "CAD"
    assert "2 record(s) labeled 'Cad'" in (
        rep["feature_count_reconciliation"]["discrepancy_explanation"]
    )
    assert wb_path.read_bytes() == original
    if dataset_id == "DA-B1":
        assert rep["artery_to_cath_consistency"] == {
            "consistent_rows": len(rows),
            "inconsistent_rows": 0,
        }


@pytest.mark.parametrize("prefer_openpyxl", [True, False])
@pytest.mark.parametrize("bad_target", ["cad", "CaD", "positive", "0", None])
def test_uci_cad_alias_does_not_weaken_target_fail_closed_rules(
    tmp_path: Path,
    prefer_openpyxl: bool,
    bad_target: str | None,
) -> None:
    """Unknown spellings and missing target values remain prohibited."""
    headers = get_uci_412_headers(include_bbb=True)
    rows = build_synthetic_uci_412_rows(headers)
    rows[0][-1] = bad_target
    wb_path = tmp_path / "Z-Alizadeh sani dataset.xlsx"
    write_synthetic_xlsx(wb_path, [("Sheet1", headers, rows)])

    expected_error = (
        "Missing target value" if bad_target is None
        else "Unexpected target category"
    )
    with pytest.raises(TargetOrCodingValidationError, match=expected_error):
        audit_uci_412_or_411_workbook(
            wb_path, dataset_id="DA-A1", prefer_openpyxl=prefer_openpyxl
        )
