"""Read-only dataset validators for UCI-412, UCI-45 (raw & processed), UCI-411, and UCI-145 Statlog."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Sequence

from research.audit.duplicates import compute_within_dataset_duplicates
from research.audit.exceptions import (
    FormatValidationError,
    LeakageColumnError,
    RawVsProcessedConfusionError,
    TargetOrCodingValidationError,
)
from research.audit.registry import (
    EVIDENCE_VERIFIED,
    UCI_45_CATH_DATE_ATTRIBUTES,
    UCI_45_CONVENTIONAL_14_COLUMNS,
    UCI_45_FILE_ROLES,
    UCI_45_IDENTIFIER_ATTRIBUTES,
    UCI_45_PER_VESSEL_ATTRIBUTES,
    UCI_45_PROCESSED_DOMAIN_RULES,
    UCI_45_RAW_76_ATTRIBUTES,
    UCI_45_RAW_TO_CONVENTIONAL_1BASED,
    UCI_145_STATLOG_14_COLUMNS,
    UCI_411_ALLOWED_ARTERY_VALUES,
    UCI_411_ARTERY_LEAKAGE_COLUMNS,
    UCI_412_ALLOWED_TARGETS,
    UCI_412_CANONICAL_BY_NORMALIZED,
    UCI_412_ECHO_FEATURES,
    UCI_412_FEATURE_GROUPS,
    UCI_412_LAB_FEATURES,
    UCI_412_TARGET_COLUMN,
    normalize_column_key,
)
from research.audit.xlsx_reader import read_xlsx_workbook


def _is_missing_token(val: Any) -> tuple[bool, str | None]:
    """Classify whether a scalar cell value is a missing/sentinel token."""
    if val is None:
        return True, "null_or_blank"
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        if float(val) == -9.0:
            return True, "minus_nine_sentinel"
        return False, None
    s = str(val).strip()
    if s == "":
        return True, "null_or_blank"
    if s == "?":
        return True, "question_mark"
    if s in ("-9", "-9.0"):
        return True, "minus_nine_sentinel"
    return False, None


def audit_uci_412_or_411_workbook(
    file_path: Path,
    *,
    dataset_id: str,
    prefer_openpyxl: bool = True,
) -> dict[str, Any]:
    """Audit Function 1 (& 7): Validate UCI-412 or UCI-411 .xlsx workbook in read-only mode."""
    if dataset_id not in ("DA-A1", "DA-B1"):
        raise FormatValidationError(f"Unsupported workbook dataset_id '{dataset_id}'.")

    expected_filename = (
        "Z-Alizadeh sani dataset.xlsx"
        if dataset_id == "DA-A1"
        else "extention of Z-Alizadeh sani dataset.xlsx"
    )
    if file_path.name != expected_filename:
        raise FormatValidationError(
            f"Filename mismatch for '{dataset_id}': expected '{expected_filename}', got '{file_path.name}'."
        )

    wb = read_xlsx_workbook(file_path, prefer_openpyxl=prefer_openpyxl)
    non_empty_sheets = [sh for sh in wb.sheet_names if len(wb.sheets[sh].headers) > 0]
    if len(non_empty_sheets) != 1:
        raise FormatValidationError(
            f"Workbook '{file_path.name}' must contain exactly 1 non-empty data sheet; "
            f"found {len(non_empty_sheets)} ({non_empty_sheets})."
        )

    sheet = wb.sheets[non_empty_sheets[0]]
    if not sheet.rows:
        raise FormatValidationError(f"Worksheet '{sheet.name}' in '{file_path.name}' has 0 patient rows.")

    seen_norm: set[str] = set()
    column_classifications: list[dict[str, Any]] = []
    group_counts: Counter[str] = Counter()
    artery_cols_present: list[str] = []
    target_col_idx: int | None = None
    artery_col_indices: dict[str, int] = {}
    canonical_headers: list[str] = []

    norm_cath = normalize_column_key(UCI_412_TARGET_COLUMN)
    norm_arteries = {normalize_column_key(a): a for a in UCI_411_ARTERY_LEAKAGE_COLUMNS}

    for idx, raw_hdr in enumerate(sheet.headers):
        norm_key = normalize_column_key(raw_hdr)
        if norm_key in seen_norm:
            raise FormatValidationError(
                f"Duplicate column header '{raw_hdr}' in '{file_path.name}'."
            )
        seen_norm.add(norm_key)

        if norm_key == norm_cath:
            target_col_idx = idx
            canonical_headers.append(UCI_412_TARGET_COLUMN)
            column_classifications.append(
                {
                    "column_index_1based": idx + 1,
                    "header_in_file": raw_hdr,
                    "canonical_name": UCI_412_TARGET_COLUMN,
                    "group": "target_label",
                    "leakage_status": "TARGET_LABEL_L03",
                }
            )
            group_counts["target_label"] += 1
        elif norm_key in norm_arteries:
            canon_art = norm_arteries[norm_key]
            if dataset_id == "DA-A1":
                raise LeakageColumnError(
                    f"Forbidden UCI-411 artery leakage column '{raw_hdr}' ('{canon_art}') found inside "
                    f"DA-A1 (UCI-412) workbook '{file_path.name}'! Rejecting fail-closed (L-03)."
                )
            artery_cols_present.append(canon_art)
            artery_col_indices[canon_art] = idx
            canonical_headers.append(canon_art)
            column_classifications.append(
                {
                    "column_index_1based": idx + 1,
                    "header_in_file": raw_hdr,
                    "canonical_name": canon_art,
                    "group": "artery_stenosis_extension",
                    "leakage_status": "EXCLUDED_LEAKAGE_BLOCKER_L03",
                }
            )
            group_counts["artery_stenosis_extension"] += 1
        elif norm_key in UCI_412_CANONICAL_BY_NORMALIZED:
            canon_name, grp_name = UCI_412_CANONICAL_BY_NORMALIZED[norm_key]
            canonical_headers.append(canon_name)
            leak_tag = "CANDIDATE_PRE_ANGIOGRAPHY_L08"
            if canon_name in UCI_412_ECHO_FEATURES:
                leak_tag = "AUDIT_CRITICAL_ECHO_TIMING_UNVERIFIED_L08"
            elif canon_name in UCI_412_LAB_FEATURES:
                leak_tag = "PENDING_LAB_DICTIONARY_AND_TIMING_L08"
            column_classifications.append(
                {
                    "column_index_1based": idx + 1,
                    "header_in_file": raw_hdr,
                    "canonical_name": canon_name,
                    "group": grp_name,
                    "leakage_status": leak_tag,
                }
            )
            group_counts[grp_name] += 1
        else:
            # Check if a UCI-45 leakage column like 'ca' or 'num' was injected
            if norm_key in {"ca", "num", "lmt", "ladprox", "laddist", "cxmain", "rcaprox", "rcadist"}:
                raise LeakageColumnError(
                    f"Unauthorized leakage/foreign column '{raw_hdr}' found in '{file_path.name}'."
                )
            raise FormatValidationError(
                f"Unrecognized column '{raw_hdr}' at position {idx + 1} in '{file_path.name}'."
            )

    if target_col_idx is None:
        raise TargetOrCodingValidationError(
            f"Missing required target column '{UCI_412_TARGET_COLUMN}' in '{file_path.name}'."
        )

    if dataset_id == "DA-B1" and set(artery_cols_present) != set(UCI_411_ARTERY_LEAKAGE_COLUMNS):
        raise FormatValidationError(
            f"UCI-411 workbook '{file_path.name}' must include all three artery columns "
            f"{list(UCI_411_ARTERY_LEAKAGE_COLUMNS)}; found {artery_cols_present}."
        )

    predictor_count = (
        group_counts["demographic"]
        + group_counts["symptom_and_examination"]
        + group_counts["ecg"]
        + group_counts["laboratory_and_echocardiography"]
    )
    if predictor_count not in (54, 55):
        raise FormatValidationError(
            f"Workbook '{file_path.name}' has {predictor_count} predictor columns; expected 54 or 55 "
            f"(total columns seen: {len(sheet.headers)})."
        )

    has_bbb = "bbb" in seen_norm
    reconciliation = {
        "total_columns_in_sheet": len(sheet.headers),
        "predictor_columns_count": predictor_count,
        "target_columns_count": group_counts["target_label"],
        "artery_extension_columns_count": group_counts["artery_stenosis_extension"],
        "bbb_column_present": has_bbb,
        "group_counts": dict(group_counts),
        "discrepancy_explanation": (
            f"Official UCI landing page states 54 features across 4 groups. Inspected sheet '{sheet.name}' "
            f"contains {predictor_count} predictor columns (BBB present={has_bbb}) + {group_counts['target_label']} "
            f"target column ('Cath')"
            + (
                f" + {group_counts['artery_stenosis_extension']} artery columns (LAD/LCX/RCA)"
                if dataset_id == "DA-B1"
                else ""
            )
            + f" = {len(sheet.headers)} total columns."
        ),
        "evidence_status": EVIDENCE_VERIFIED,
    }

    # Inspect rows without ever storing raw patient values in the public report
    class_counts: Counter[str] = Counter()
    missing_by_col: dict[str, dict[str, int]] = {
        c: {"null_or_blank": 0, "question_mark": 0, "minus_nine_sentinel": 0}
        for c in canonical_headers
    }
    type_counts_by_col: dict[str, Counter[str]] = {c: Counter() for c in canonical_headers}
    invalid_codings_by_col: Counter[str] = Counter()
    suspicious_values_by_col: Counter[str] = Counter()

    normalized_rows: list[dict[str, Any]] = []
    raw_row_fingerprints: list[str] = []
    artery_consistent_rows = 0
    artery_inconsistent_rows = 0

    for r_idx, row_vals in enumerate(sheet.rows, start=2):
        row_dict: dict[str, Any] = {}
        fingerprint_parts: list[str] = []

        for c_idx, canon_col in enumerate(canonical_headers):
            val = row_vals[c_idx] if c_idx < len(row_vals) else None
            if val is not None:
                fingerprint_parts.append(str(val).strip())

            is_miss, miss_kind = _is_missing_token(val)
            if is_miss and miss_kind is not None:
                missing_by_col[canon_col][miss_kind] += 1
                type_counts_by_col[canon_col]["missing"] += 1
                row_dict[canon_col] = None
                if canon_col == UCI_412_TARGET_COLUMN:
                    raise TargetOrCodingValidationError(
                        f"Missing target value in '{UCI_412_TARGET_COLUMN}' at row {r_idx} of '{file_path.name}'."
                    )
                continue

            if isinstance(val, int) and not isinstance(val, bool):
                type_counts_by_col[canon_col]["integer"] += 1
            elif isinstance(val, float):
                type_counts_by_col[canon_col]["float"] += 1
            else:
                type_counts_by_col[canon_col]["string"] += 1

            row_dict[canon_col] = val

            if canon_col == UCI_412_TARGET_COLUMN:
                s_val = str(val).strip()
                if s_val not in UCI_412_ALLOWED_TARGETS:
                    raise TargetOrCodingValidationError(
                        f"Unexpected target category in '{UCI_412_TARGET_COLUMN}' at row {r_idx} of "
                        f"'{file_path.name}' (allowed: {sorted(UCI_412_ALLOWED_TARGETS)})."
                    )
                class_counts[s_val] += 1
            elif canon_col in UCI_411_ARTERY_LEAKAGE_COLUMNS:
                s_val = str(val).strip()
                if s_val not in UCI_411_ALLOWED_ARTERY_VALUES:
                    invalid_codings_by_col[canon_col] += 1
                    raise TargetOrCodingValidationError(
                        f"Unexpected artery value in '{canon_col}' at row {r_idx} of '{file_path.name}'."
                    )
            else:
                # Suspicious value checks on known clinical numeric fields
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    f_val = float(val)
                    if canon_col == "Age" and (f_val <= 0 or f_val > 120):
                        suspicious_values_by_col[canon_col] += 1
                    elif canon_col in ("BP", "PR", "Weight", "Length", "BMI", "FBS") and f_val <= 0:
                        suspicious_values_by_col[canon_col] += 1
                    elif canon_col == "EF-TTE" and (f_val <= 0 or f_val > 100):
                        suspicious_values_by_col[canon_col] += 1

        if dataset_id == "DA-B1":
            cath_val = str(row_dict.get(UCI_412_TARGET_COLUMN, "")).strip()
            any_stenotic = any(
                str(row_dict.get(art, "")).strip() in ("Stenotic", "CAD", "1")
                for art in UCI_411_ARTERY_LEAKAGE_COLUMNS
            )
            if (cath_val == "CAD" and any_stenotic) or (cath_val == "Normal" and not any_stenotic):
                artery_consistent_rows += 1
            else:
                artery_inconsistent_rows += 1

        normalized_rows.append(row_dict)
        if len(fingerprint_parts) >= 5:
            raw_row_fingerprints.append("|".join(fingerprint_parts))

    # Check for mixed numeric/string types in predictor columns
    mixed_type_columns: list[str] = []
    for c_name, t_cnt in type_counts_by_col.items():
        has_num = (t_cnt["integer"] + t_cnt["float"]) > 0
        has_str = t_cnt["string"] > 0
        if has_num and has_str:
            mixed_type_columns.append(c_name)
            invalid_codings_by_col[c_name] += t_cnt["string"]

    if mixed_type_columns:
        raise FormatValidationError(
            f"Workbook '{file_path.name}' contains mixed numeric/string values in column(s): {mixed_type_columns}."
        )

    predictor_cols = [
        c for c in canonical_headers if c != UCI_412_TARGET_COLUMN and c not in UCI_411_ARTERY_LEAKAGE_COLUMNS
    ]
    dup_summary = compute_within_dataset_duplicates(
        dataset_id,
        normalized_rows,
        predictor_cols,
        UCI_412_TARGET_COLUMN,
        has_11_shared_clinical=False,
    )

    total_missing_cells = sum(
        sum(m.values()) for m in missing_by_col.values()
    )
    cols_with_missing = {
        col: dict(m) for col, m in missing_by_col.items() if sum(m.values()) > 0
    }

    inferred_column_types: dict[str, str] = {}
    for col, t_cnt in type_counts_by_col.items():
        if t_cnt["float"] > 0:
            inferred_column_types[col] = "float"
        elif t_cnt["integer"] > 0:
            inferred_column_types[col] = "integer"
        elif t_cnt["string"] > 0:
            inferred_column_types[col] = "categorical_string"
        else:
            inferred_column_types[col] = "all_missing"

    cad_count = class_counts.get("CAD", 0)
    normal_count = class_counts.get("Normal", 0)
    total_rows = len(normalized_rows)

    report_summary = {
        "dataset_id": dataset_id,
        "filename": file_path.name,
        "sheet_names": list(wb.sheet_names),
        "inspected_sheet": sheet.name,
        "row_count": total_rows,
        "feature_count_reconciliation": reconciliation,
        "class_distribution": {
            "target_column": UCI_412_TARGET_COLUMN,
            "raw_counts": {"CAD": cad_count, "Normal": normal_count},
            "provisional_t1_binary": {
                "cad_present_1": cad_count,
                "cad_absent_0": normal_count,
                "cad_prevalence_ratio": round(cad_count / total_rows, 4) if total_rows > 0 else 0.0,
            },
        },
        "missingness": {
            "total_missing_cells": total_missing_cells,
            "columns_with_missing_count": len(cols_with_missing),
            "per_column_missing": cols_with_missing,
        },
        "inferred_column_types": inferred_column_types,
        "invalid_codings_by_column": dict(invalid_codings_by_col),
        "suspicious_values_by_column": dict(suspicious_values_by_col),
        "leakage_and_availability_flags": {
            "target_column": UCI_412_TARGET_COLUMN,
            "artery_leakage_columns_present": artery_cols_present,
            "echo_features_requiring_timing_ruling": sorted(
                c for c in canonical_headers if c in UCI_412_ECHO_FEATURES
            ),
            "lab_features_requiring_dictionary_and_timing_ruling": sorted(
                c for c in canonical_headers if c in UCI_412_LAB_FEATURES
            ),
        },
        "within_dataset_duplicates": dup_summary,
        "evidence_status": EVIDENCE_VERIFIED,
    }

    if dataset_id == "DA-B1":
        report_summary["artery_to_cath_consistency"] = {
            "consistent_rows": artery_consistent_rows,
            "inconsistent_rows": artery_inconsistent_rows,
        }

    return {
        "report": report_summary,
        "all_canonical_columns": list(canonical_headers),
        "normalized_columns": predictor_cols + [UCI_412_TARGET_COLUMN],
        "normalized_rows": normalized_rows,
        "raw_row_fingerprints": raw_row_fingerprints,
        "artery_to_cath_consistent_rows": artery_consistent_rows,
        "artery_to_cath_inconsistent_rows": artery_inconsistent_rows,
    }


def audit_uci_45_processed_file(
    file_path: Path,
    *,
    strict_coding: bool = False,
) -> dict[str, Any]:
    """Audit Functions 2, 3, 4: Validate a UCI-45 processed 14-column cohort file."""
    if file_path.name not in UCI_45_FILE_ROLES or UCI_45_FILE_ROLES[file_path.name]["format"] != "processed_14_col":
        raise FormatValidationError(
            f"File '{file_path.name}' is not a recognized UCI-45 processed 14-column cohort file."
        )

    role_meta = UCI_45_FILE_ROLES[file_path.name]
    try:
        raw_text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise FormatValidationError(f"Corrupt UTF-8 text in '{file_path.name}': {exc}") from exc

    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
    if not lines:
        raise FormatValidationError(f"Processed file '{file_path.name}' is empty.")

    # Detect raw-vs-processed confusion: if no commas and lines end with 'name' or look like 76-attr raw records
    if all("," not in ln for ln in lines[: min(10, len(lines))]):
        joined_tokens = " ".join(lines[:20]).split()
        if any(tok.lower() == "name" for tok in joined_tokens) or len(joined_tokens) >= 76:
            raise RawVsProcessedConfusionError(
                f"File '{file_path.name}' appears to contain whitespace-delimited raw 76-attribute records "
                "rather than comma-delimited 14-column processed records!"
            )
        raise FormatValidationError(
            f"File '{file_path.name}' does not use comma (',') delimiters."
        )

    missing_by_col: dict[str, dict[str, int]] = {
        c: {"null_or_blank": 0, "question_mark": 0, "minus_nine_sentinel": 0}
        for c in UCI_45_CONVENTIONAL_14_COLUMNS
    }
    invalid_codings_by_col: Counter[str] = Counter()
    suspicious_values_by_col: Counter[str] = Counter()
    raw_target_counts: Counter[int] = Counter()

    normalized_rows: list[dict[str, Any]] = []
    raw_row_fingerprints: list[str] = []

    for line_num, ln in enumerate(lines, start=1):
        if ";" in ln or "\t" in ln or "|" in ln:
            raise FormatValidationError(
                f"Wrong delimiter detected on line {line_num} of '{file_path.name}'; expected comma (',')."
            )
        parts = [p.strip() for p in ln.split(",")]
        if len(parts) == 76:
            raise RawVsProcessedConfusionError(
                f"Line {line_num} of '{file_path.name}' has 76 attributes instead of 14 processed columns!"
            )
        if len(parts) != 14:
            raise FormatValidationError(
                f"Line {line_num} of '{file_path.name}' has {len(parts)} columns; expected exactly 14."
            )

        if line_num == 1 and parts[0].lower() == "age" and parts[-1].lower() in ("num", "target"):
            raise FormatValidationError(
                f"Processed UCI-45 file '{file_path.name}' must be headerless; unexpected header row found."
            )

        row_dict: dict[str, Any] = {}
        raw_row_fingerprints.append(ln)

        for col_idx, col_name in enumerate(UCI_45_CONVENTIONAL_14_COLUMNS):
            token = parts[col_idx]
            is_miss, miss_kind = _is_missing_token(token)
            if is_miss and miss_kind is not None:
                missing_by_col[col_name][miss_kind] += 1
                row_dict[col_name] = None
                if miss_kind == "minus_nine_sentinel":
                    # In processed files, -9 / -9.0 is also noted as unrecoded raw sentinel
                    suspicious_values_by_col[f"{col_name}_minus_nine_sentinel"] += 1
                if col_name == "num":
                    raise TargetOrCodingValidationError(
                        f"Missing target value in 'num' on line {line_num} of '{file_path.name}'."
                    )
                continue

            try:
                f_val = float(token)
            except ValueError as exc:
                if col_name == "num":
                    raise TargetOrCodingValidationError(
                        f"Non-numeric target value in 'num' on line {line_num} of '{file_path.name}'."
                    ) from exc
                raise FormatValidationError(
                    f"Non-numeric token in column '{col_name}' on line {line_num} of '{file_path.name}'."
                ) from exc

            row_dict[col_name] = int(round(f_val)) if f_val.is_integer() else f_val

            if col_name in UCI_45_PROCESSED_DOMAIN_RULES:
                allowed_set = UCI_45_PROCESSED_DOMAIN_RULES[col_name]
                if f_val not in allowed_set:
                    invalid_codings_by_col[col_name] += 1
                    if col_name == "num" or strict_coding:
                        raise TargetOrCodingValidationError(
                            f"Invalid coding in column '{col_name}' on line {line_num} of '{file_path.name}'."
                        )

            if col_name == "num":
                t_int = int(round(f_val))
                raw_target_counts[t_int] += 1
                row_dict["binary_target"] = 0 if t_int == 0 else 1

            # Suspicious value rules (note: 0 is preserved as data, never treated as null/missing!)
            if col_name == "chol" and f_val <= 0:
                suspicious_values_by_col["chol_zero_or_nonpositive"] += 1
            elif col_name == "trestbps" and f_val <= 0:
                suspicious_values_by_col["trestbps_zero_or_nonpositive"] += 1
            elif col_name == "age" and (f_val <= 0 or f_val > 120):
                suspicious_values_by_col["age_out_of_plausible_range"] += 1
            elif col_name == "thalach" and (f_val <= 0 or f_val > 250):
                suspicious_values_by_col["thalach_out_of_plausible_range"] += 1
            elif col_name == "oldpeak" and f_val < 0:
                suspicious_values_by_col["oldpeak_negative"] += 1

        normalized_rows.append(row_dict)

    total_rows = len(normalized_rows)
    absent_0 = raw_target_counts.get(0, 0)
    present_1_4 = sum(cnt for k, cnt in raw_target_counts.items() if k in (1, 2, 3, 4))

    cols_with_missing = {
        col: dict(m) for col, m in missing_by_col.items() if sum(m.values()) > 0
    }
    total_missing_cells = sum(sum(m.values()) for m in missing_by_col.values())
    total_cells = total_rows * 14
    completeness_ratio = round(1.0 - (total_missing_cells / total_cells), 4) if total_cells > 0 else 0.0

    dup_summary = compute_within_dataset_duplicates(
        file_path.name,
        normalized_rows,
        UCI_45_CONVENTIONAL_14_COLUMNS[:13],
        "num",
        has_11_shared_clinical=True,
    )

    report = {
        "filename": file_path.name,
        "cohort": role_meta["cohort"],
        "format": role_meta["format"],
        "intended_role": role_meta["intended_role"],
        "conventional_14_schema_confirmed": True,
        "columns": list(UCI_45_CONVENTIONAL_14_COLUMNS),
        "documented_expected_rows": role_meta["documented_rows"],
        "row_count": total_rows,
        "class_distribution": {
            "target_column": "num",
            "raw_num_counts": {str(k): raw_target_counts.get(k, 0) for k in range(5)},
            "uses_pre_binarized_0_1_coding": all(k in (0, 1) for k in raw_target_counts.keys()),
            "provisional_t1_binary_0_vs_1_to_4": {
                "cad_absent_0": absent_0,
                "cad_present_1_to_4": present_1_4,
                "cad_prevalence_ratio": round(present_1_4 / total_rows, 4) if total_rows > 0 else 0.0,
            },
        },
        "missingness": {
            "total_missing_cells": total_missing_cells,
            "overall_cell_completeness_ratio": completeness_ratio,
            "columns_with_missing_count": len(cols_with_missing),
            "per_column_missing": cols_with_missing,
        },
        "invalid_codings_by_column": dict(invalid_codings_by_col),
        "suspicious_values": dict(suspicious_values_by_col),
        "leakage_and_availability_flags": {
            "ca_column_present_excluded_l01": True,
            "thal_column_present_pending_l06": True,
            "exercise_test_block_present_conditional_l07": ["thalach", "exang", "oldpeak", "slope"],
            "oldpeak_unit_status": "UNVERIFIED_ON_OFFICIAL_UCI_PAGE",
        },
        "within_dataset_duplicates": dup_summary,
        "evidence_status": EVIDENCE_VERIFIED,
    }

    return {
        "report": report,
        "normalized_rows": normalized_rows,
        "raw_row_fingerprints": raw_row_fingerprints,
    }


def audit_uci_45_raw_file(file_path: Path) -> dict[str, Any]:
    """Audit Functions 2 & 3: Validate a UCI-45 raw 76-attribute cohort file."""
    if file_path.name not in UCI_45_FILE_ROLES or UCI_45_FILE_ROLES[file_path.name]["format"] != "raw_76_attr":
        raise FormatValidationError(
            f"File '{file_path.name}' is not a recognized UCI-45 raw 76-attribute cohort file."
        )

    role_meta = UCI_45_FILE_ROLES[file_path.name]
    try:
        raw_text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise FormatValidationError(f"Corrupt UTF-8 text in '{file_path.name}': {exc}") from exc

    non_empty_lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
    if not non_empty_lines:
        raise FormatValidationError(f"Raw file '{file_path.name}' is empty.")

    # Detect raw-vs-processed confusion: if lines are 14 comma-separated fields
    first_comma_parts = [p.strip() for p in non_empty_lines[0].split(",")]
    if len(first_comma_parts) == 14:
        raise RawVsProcessedConfusionError(
            f"File '{file_path.name}' has 14 comma-separated columns; a processed 14-column file was "
            "supplied where a 76-attribute raw file was required!"
        )

    tokens = raw_text.split()
    if len(tokens) == 0 or len(tokens) % 76 != 0:
        raise FormatValidationError(
            f"Raw 76-attribute file '{file_path.name}' has {len(tokens)} whitespace-delimited tokens, "
            "which is not a non-empty multiple of 76 (file is truncated or corrupt)."
        )

    num_records = len(tokens) // 76
    missing_by_attr: Counter[str] = Counter()
    raw_target_counts: Counter[int] = Counter()
    vessel_value_types: Counter[str] = Counter()
    extracted_conventional_rows: list[dict[str, Any]] = []
    raw_row_fingerprints: list[str] = []

    vessel_indices_0based = {
        UCI_45_RAW_76_ATTRIBUTES.index(v_attr) for v_attr in UCI_45_PER_VESSEL_ATTRIBUTES
    }

    for rec_idx in range(num_records):
        rec_tokens = tokens[rec_idx * 76 : (rec_idx + 1) * 76]
        name_token = rec_tokens[75]
        if name_token.lower() != "name":
            raise FormatValidationError(
                f"Record {rec_idx + 1} in raw file '{file_path.name}' does not terminate with dummy 'name' "
                f"at attribute #76 (got unexpected token)."
            )

        # Fingerprint uses clinical attributes #3..#58 (never #1 id or #2 ccf)
        raw_row_fingerprints.append(" ".join(rec_tokens[2:58]))

        for attr_idx_0 in range(75):
            attr_name = UCI_45_RAW_76_ATTRIBUTES[attr_idx_0]
            tok = rec_tokens[attr_idx_0]
            is_miss, _ = _is_missing_token(tok)
            if is_miss:
                missing_by_attr[attr_name] += 1
                continue
            try:
                f_val = float(tok)
            except ValueError as exc:
                raise FormatValidationError(
                    f"Non-numeric token in raw attribute #{attr_idx_0 + 1} ('{attr_name}') "
                    f"at record {rec_idx + 1} of '{file_path.name}'."
                ) from exc

            if attr_idx_0 in vessel_indices_0based:
                if f_val in (0.0, 1.0, 2.0):
                    vessel_value_types["discrete_code_0_1_2"] += 1
                elif f_val == 50.0:
                    vessel_value_types["exact_50_numeric"] += 1
                else:
                    vessel_value_types["other_numeric"] += 1

        # Extract the 14 conventional attributes for raw<->processed correspondence check
        conv_row: dict[str, Any] = {}
        for conv_col, pos_1based in UCI_45_RAW_TO_CONVENTIONAL_1BASED.items():
            tok = rec_tokens[pos_1based - 1]
            is_miss, _ = _is_missing_token(tok)
            if is_miss:
                conv_row[conv_col] = None
                if conv_col == "num":
                    raise TargetOrCodingValidationError(
                        f"Missing target '#58 num' at record {rec_idx + 1} of '{file_path.name}'."
                    )
            else:
                f_val = float(tok)
                conv_row[conv_col] = int(round(f_val)) if f_val.is_integer() else f_val
                if conv_col == "num":
                    t_int = int(round(f_val))
                    if t_int not in (0, 1, 2, 3, 4):
                        raise TargetOrCodingValidationError(
                            f"Invalid target '#58 num' at record {rec_idx + 1} of '{file_path.name}'."
                        )
                    raw_target_counts[t_int] += 1
                    conv_row["binary_target"] = 0 if t_int == 0 else 1

        extracted_conventional_rows.append(conv_row)

    conventional_missing = {
        col: missing_by_attr[col] for col in UCI_45_CONVENTIONAL_14_COLUMNS if missing_by_attr[col] > 0
    }

    report = {
        "filename": file_path.name,
        "cohort": role_meta["cohort"],
        "format": role_meta["format"],
        "intended_role": role_meta["intended_role"],
        "raw_76_attribute_schema_confirmed": True,
        "attribute_count": 76,
        "documented_expected_rows": role_meta["documented_rows"],
        "row_count": num_records,
        "dummy_name_attribute_76_verified_all_rows": True,
        "class_distribution": {
            "target_attribute": "#58 num",
            "raw_num_counts": {str(k): raw_target_counts.get(k, 0) for k in range(5)},
            "provisional_t1_binary_0_vs_1_to_4": {
                "cad_absent_0": raw_target_counts.get(0, 0),
                "cad_present_1_to_4": sum(
                    cnt for k, cnt in raw_target_counts.items() if k in (1, 2, 3, 4)
                ),
            },
        },
        "missingness": {
            "missing_sentinel_code": "-9 / -9.0 (per heart-disease.names §9)",
            "total_missing_cells_across_76_attrs": sum(missing_by_attr.values()),
            "attributes_with_missing_count": len(missing_by_attr),
            "conventional_14_positions_missing_counts": conventional_missing,
        },
        "leakage_and_identifier_audit": {
            "identifier_attributes_excluded_l02_l12": list(UCI_45_IDENTIFIER_ATTRIBUTES),
            "cath_date_attributes_excluded_l02": list(UCI_45_CATH_DATE_ATTRIBUTES),
            "per_vessel_angiography_attributes_excluded_l02": list(UCI_45_PER_VESSEL_ATTRIBUTES),
            "per_vessel_non_missing_value_kind_counts": dict(vessel_value_types),
            "ca_attribute_44_excluded_l01": True,
            "thal_attribute_51_pending_l06": True,
        },
        "evidence_status": EVIDENCE_VERIFIED,
    }

    return {
        "report": report,
        "extracted_conventional_rows": extracted_conventional_rows,
        "raw_row_fingerprints": raw_row_fingerprints,
    }


def compare_uci_45_raw_and_processed(
    cohort: str,
    raw_parsed: dict[str, Any],
    proc_parsed: dict[str, Any],
) -> dict[str, Any]:
    """Verify row-level correspondence between a cohort's raw 76-attribute file and processed 14-column file."""
    raw_rows: Sequence[dict[str, Any]] = raw_parsed["extracted_conventional_rows"]
    proc_rows: Sequence[dict[str, Any]] = proc_parsed["normalized_rows"]

    min_len = min(len(raw_rows), len(proc_rows))
    exact_13_predictor_matches = 0
    exact_14_with_raw_num_matches = 0
    exact_14_with_binary_num_matches = 0

    for idx in range(min_len):
        r_row = raw_rows[idx]
        p_row = proc_rows[idx]
        preds_match = all(r_row.get(c) == p_row.get(c) for c in UCI_45_CONVENTIONAL_14_COLUMNS[:13])
        if preds_match:
            exact_13_predictor_matches += 1
            if r_row.get("num") == p_row.get("num"):
                exact_14_with_raw_num_matches += 1
            if r_row.get("binary_target") == p_row.get("binary_target"):
                exact_14_with_binary_num_matches += 1

    return {
        "cohort": cohort,
        "raw_row_count": len(raw_rows),
        "processed_row_count": len(proc_rows),
        "row_counts_equal": len(raw_rows) == len(proc_rows),
        "positional_13_predictor_matches": exact_13_predictor_matches,
        "positional_14_col_exact_num_matches": exact_14_with_raw_num_matches,
        "positional_14_col_binary_num_matches": exact_14_with_binary_num_matches,
        "num_recoded_to_binary_in_processed": (
            exact_14_with_binary_num_matches > exact_14_with_raw_num_matches
        ),
        "evidence_status": EVIDENCE_VERIFIED,
    }


def audit_uci_45_names_file(file_path: Path) -> dict[str, Any]:
    """Validate the official heart-disease.names documentation file."""
    if file_path.name != "heart-disease.names":
        raise FormatValidationError(f"Expected 'heart-disease.names', got '{file_path.name}'.")
    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise FormatValidationError(f"Corrupt UTF-8 text in 'heart-disease.names': {exc}") from exc

    if not text.strip():
        raise FormatValidationError("Documentation file 'heart-disease.names' is empty.")

    lowered = text.lower()
    has_76 = "76" in lowered
    has_missing_minus_9 = "-9" in lowered
    has_cleveland = "cleveland" in lowered
    if not (has_76 and has_missing_minus_9 and has_cleveland):
        raise FormatValidationError(
            "File 'heart-disease.names' is missing expected official UCI-45 documentation markers "
            "('76' attributes, 'cleveland', and '-9' missing-value note)."
        )

    return {
        "filename": file_path.name,
        "format": "documentation_text",
        "intended_role": UCI_45_FILE_ROLES["heart-disease.names"]["intended_role"],
        "line_count": len(text.splitlines()),
        "documents_76_attributes": has_76,
        "documents_minus_9_missing_code": has_missing_minus_9,
        "contains_patient_rows": False,
        "evidence_status": EVIDENCE_VERIFIED,
    }


def audit_uci_145_statlog_file(file_path: Path) -> dict[str, Any]:
    """Audit Function 4 & 8: Validate UCI-145 Statlog heart.dat (when DA-B2 is authorized)."""
    if file_path.name != "heart.dat":
        raise FormatValidationError(f"Expected 'heart.dat' for DA-B2, got '{file_path.name}'.")
    try:
        raw_text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise FormatValidationError(f"Corrupt UTF-8 text in 'heart.dat': {exc}") from exc

    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
    if not lines:
        raise FormatValidationError("Statlog file 'heart.dat' is empty.")

    missing_by_col: Counter[str] = Counter()
    invalid_codings_by_col: Counter[str] = Counter()
    suspicious_values_by_col: Counter[str] = Counter()
    raw_class_counts: Counter[int] = Counter()
    normalized_rows: list[dict[str, Any]] = []
    raw_row_fingerprints: list[str] = []

    for line_num, ln in enumerate(lines, start=1):
        if "," in ln or ";" in ln:
            raise FormatValidationError(
                f"Wrong delimiter on line {line_num} of 'heart.dat'; Statlog heart.dat is whitespace-delimited."
            )
        parts = ln.split()
        if len(parts) != 14:
            raise FormatValidationError(
                f"Line {line_num} of 'heart.dat' has {len(parts)} columns; expected 14."
            )

        raw_row_fingerprints.append(ln)
        row_dict: dict[str, Any] = {}

        for col_idx, col_name in enumerate(UCI_145_STATLOG_14_COLUMNS):
            tok = parts[col_idx]
            is_miss, _ = _is_missing_token(tok)
            if is_miss:
                missing_by_col[col_name] += 1
                row_dict[col_name] = None
                if col_name == "class":
                    raise TargetOrCodingValidationError(
                        f"Missing target in 'class' on line {line_num} of 'heart.dat'."
                    )
                continue
            try:
                f_val = float(tok)
            except ValueError as exc:
                raise FormatValidationError(
                    f"Non-numeric token in '{col_name}' on line {line_num} of 'heart.dat'."
                ) from exc

            row_dict[col_name] = int(round(f_val)) if f_val.is_integer() else f_val
            if col_name == "class":
                c_int = int(round(f_val))
                if c_int not in (1, 2):
                    raise TargetOrCodingValidationError(
                        f"Invalid Statlog target coding on line {line_num} of 'heart.dat' "
                        "(expected 1=absence or 2=presence)."
                    )
                raw_class_counts[c_int] += 1
                row_dict["binary_target"] = 0 if c_int == 1 else 1
            elif col_name in UCI_45_PROCESSED_DOMAIN_RULES:
                if f_val not in UCI_45_PROCESSED_DOMAIN_RULES[col_name]:
                    invalid_codings_by_col[col_name] += 1

            if col_name == "chol" and f_val <= 0:
                suspicious_values_by_col["chol_zero_or_nonpositive"] += 1
            elif col_name == "oldpeak" and f_val < 0:
                suspicious_values_by_col["oldpeak_negative"] += 1

        normalized_rows.append(row_dict)

    dup_summary = compute_within_dataset_duplicates(
        "DA-B2:heart.dat",
        normalized_rows,
        UCI_145_STATLOG_14_COLUMNS[:13],
        "class",
        has_11_shared_clinical=True,
    )

    total_rows = len(normalized_rows)
    absence_1 = raw_class_counts.get(1, 0)
    presence_2 = raw_class_counts.get(2, 0)

    report = {
        "dataset_id": "DA-B2",
        "filename": file_path.name,
        "permitted_role": "AUDIT_ONLY_DUPLICATE_OVERLAP_INVESTIGATION",
        "never_training_or_external_validation_by_audit_grant": True,
        "row_count": total_rows,
        "documented_expected_rows": 270,
        "class_distribution": {
            "target_column": "class",
            "coding_note": "1 = absence of heart disease, 2 = presence of heart disease (H-04)",
            "raw_counts": {"1_absence": absence_1, "2_presence": presence_2},
            "mapped_binary_counts": {
                "cad_absent_0": absence_1,
                "cad_present_1": presence_2,
                "cad_prevalence_ratio": round(presence_2 / total_rows, 4) if total_rows > 0 else 0.0,
            },
        },
        "missingness": {
            "total_missing_cells": sum(missing_by_col.values()),
            "per_column_missing": dict(missing_by_col),
        },
        "invalid_codings_by_column": dict(invalid_codings_by_col),
        "suspicious_values": dict(suspicious_values_by_col),
        "leakage_and_availability_flags": {
            "ca_column_present_excluded_l01": True,
            "thal_column_present_pending_l06": True,
        },
        "within_dataset_duplicates": dup_summary,
        "evidence_status": EVIDENCE_VERIFIED,
    }

    return {
        "report": report,
        "normalized_rows": normalized_rows,
        "raw_row_fingerprints": raw_row_fingerprints,
    }
