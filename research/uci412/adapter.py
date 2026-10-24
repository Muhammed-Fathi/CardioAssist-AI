"""Strict, read-only adapter for the single authorized UCI-412 workbook.

Design rules enforced here:

* the file name, workbook shape, and complete 56-column set must match the
  registered source profile exactly; unknown, duplicate, blocked-artery, or
  identifier columns are rejected rather than ignored;
* the target is mapped only from the reviewed source tokens ``Cad``/``Normal``;
* admitted predictors are typed and vocabulary-checked with no silent numerical
  coercion, no row deletion, and no value repair;
* blanks become ``NaN`` (imputed later inside training folds only), while the
  UCI-45 missing markers ``?`` and ``-9`` are rejected as wrong-source signals;
* only aggregate metadata leaves this module: no row, cell value, or
  patient-level structure is returned or printable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import math
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from research.audit.xlsx_reader import SheetData, WorkbookData, read_xlsx_workbook
from research.uci412.config import DEFAULT_CONFIG, Uci412Config
from research.uci412.errors import ProvenanceError, SourceFormatError
from research.uci412.feature_schema import DEFAULT_DICTIONARY, FeatureDictionary, FeatureSpec
from research.uci412.source_spec import (
    MAX_SOURCE_BYTES,
    PROHIBITED_PREDICTORS,
    SOURCE_COLUMNS,
    SOURCE_FILENAME,
    TARGET_COLUMN,
    WRONG_SOURCE_TOKENS,
)


@dataclass(frozen=True, slots=True)
class SourceSnapshot:
    """Hashed byte snapshot of the protected source. Retained only locally."""

    content: bytes
    sha256: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class ParsedWorkbook:
    """Typed, already-validated workbook content (never printed or logged)."""

    sheet_name: str
    headers: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...]
    other_sheet_count: int
    header_order_matches_registered_profile: bool


@dataclass(frozen=True, slots=True)
class Uci412Dataset:
    """Target and admitted predictors in memory, plus aggregate-only audit facts."""

    X: np.ndarray
    y: np.ndarray
    feature_names: tuple[str, ...]
    row_count: int
    class_counts: tuple[tuple[int, int], ...]
    audit: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.feature_names != DEFAULT_CONFIG.feature_names:
            raise SourceFormatError("Dataset feature names do not match the registered primary panel.")
        if not isinstance(self.X, np.ndarray) or self.X.ndim != 2:
            raise SourceFormatError("Parsed feature matrix has an invalid shape.")
        if self.X.shape != (self.row_count, len(self.feature_names)):
            raise SourceFormatError("Parsed feature matrix has an unexpected column count.")
        if not isinstance(self.y, np.ndarray) or self.y.shape != (self.row_count,):
            raise SourceFormatError("Parsed target has an invalid shape.")
        if self.row_count <= 0 or not np.isin(self.y, (0, 1)).all():
            raise SourceFormatError("Parsed target must contain only mapped binary labels.")
        observed = self.X[~np.isnan(self.X)]
        if not np.isfinite(observed).all():
            raise SourceFormatError("Parsed feature matrix contains a non-finite observed value.")
        # Downstream estimators may read but cannot mutate source-derived arrays.
        self.X.setflags(write=False)
        self.y.setflags(write=False)

    @property
    def n_positive(self) -> int:
        return int(np.count_nonzero(self.y == 1))

    @property
    def n_negative(self) -> int:
        return int(np.count_nonzero(self.y == 0))


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _stat_identity(path: Path) -> tuple[int, int, int]:
    stat = path.stat()
    return (stat.st_size, stat.st_mtime_ns, stat.st_ino)


def read_source_snapshot(
    source_path: Path,
    *,
    expected_sha256: str,
    expected_size_bytes: int | None = None,
) -> SourceSnapshot:
    """Read the authorized workbook in binary read-only mode and verify its bytes.

    The function never creates, truncates, or writes to ``source_path``. It is
    deliberately not an authorization check: callers must obtain the path and
    expected hash from a validated local preflight context.
    """
    path = Path(source_path)
    if path.name != SOURCE_FILENAME:
        raise SourceFormatError("Only the exact registered UCI-412 workbook file name may be opened.")
    if path.is_symlink() or not path.is_file():
        raise ProvenanceError("The authorized UCI-412 source is missing or unsafe.")
    try:
        before = _stat_identity(path)
        size = path.stat().st_size
        if size <= 0 or size > MAX_SOURCE_BYTES:
            raise ProvenanceError("The source byte size is outside the registered workbook range.")
        with path.open("rb") as handle:
            content = handle.read()
        after = _stat_identity(path)
    except OSError as exc:
        raise ProvenanceError("Unable to read the authorized source in read-only mode.") from exc
    if before != after or after[0] != len(content):
        raise ProvenanceError("The source file changed while its read-only snapshot was being created.")
    digest = sha256_bytes(content)
    if len(expected_sha256) != 64 or digest.lower() != expected_sha256.lower():
        raise ProvenanceError("The local source SHA-256 does not match the authorized hash binding.")
    if expected_size_bytes is not None and len(content) != expected_size_bytes:
        raise ProvenanceError("The local source byte size does not match the authorized size.")
    return SourceSnapshot(content=content, sha256=digest, size_bytes=len(content))


def _normalize_header_key(name: str) -> str:
    return " ".join(name.strip().lower().replace("_", " ").replace("-", " ").split())


def validate_workbook_structure(
    workbook: WorkbookData,
    *,
    config: Uci412Config = DEFAULT_CONFIG,
) -> ParsedWorkbook:
    """Validate workbook shape and the exact registered column set."""
    data_sheets = [name for name in workbook.sheet_names if workbook.sheets[name].rows]
    if len(data_sheets) != 1:
        raise SourceFormatError(
            "The workbook must contain exactly one data-bearing worksheet; "
            f"found {len(data_sheets)}. Sheets are never merged."
        )
    sheet = workbook.sheets[data_sheets[0]]
    headers = tuple(sheet.headers)
    normalized = [_normalize_header_key(name) for name in headers]
    if len(set(normalized)) != len(normalized):
        raise SourceFormatError("The workbook contains duplicate column headers.")
    if set(headers) != set(SOURCE_COLUMNS):
        extra = sorted(set(headers) - set(SOURCE_COLUMNS))
        missing = sorted(set(SOURCE_COLUMNS) - set(headers))
        parts = []
        if missing:
            parts.append(f"missing listed columns: {missing}")
        if extra:
            parts.append(f"unregistered or prohibited columns: {extra}")
        raise SourceFormatError(
            "The workbook columns do not match the registered UCI-412 profile; " + "; ".join(parts)
        )
    if len(headers) != len(config.source_columns):
        raise SourceFormatError(
            f"The workbook has {len(headers)} columns; the registered UCI-412 profile requires "
            f"{len(config.source_columns)} (55 predictors + target)."
        )
    if set(headers) & PROHIBITED_PREDICTORS and TARGET_COLUMN not in headers:
        raise SourceFormatError("The workbook omits the reviewed target column.")
    if sheet.rows and len(sheet.rows[0]) != len(headers):
        raise SourceFormatError("A workbook row has a width that does not match the header row.")
    for row in sheet.rows:
        if len(row) != len(headers):
            raise SourceFormatError("A workbook row has a width that does not match the header row.")
    return ParsedWorkbook(
        sheet_name=data_sheets[0],
        headers=headers,
        rows=tuple(sheet.rows),
        other_sheet_count=len(workbook.sheet_names) - 1,
        header_order_matches_registered_profile=headers == config.source_columns,
    )


def _categorical_token(value: Any, *, column: str) -> str:
    """Convert a raw cell to a vocabulary token without inventing values."""
    if isinstance(value, bool):
        raise SourceFormatError(f"Unsupported boolean cell type in column '{column}'.")
    if isinstance(value, str):
        if value != value.strip():
            # Surrounding whitespace is treated as a malformed token rather than
            # silently trimmed: a trimmed match could hide a different value.
            raise SourceFormatError(
                f"Column '{column}' contains a category token with surrounding whitespace."
            )
        if not value:
            raise SourceFormatError(f"Blank categorical token in column '{column}'.")
        return value
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise SourceFormatError(f"Non-finite categorical value in column '{column}'.")
        if value.is_integer():
            return str(int(value))
        raise SourceFormatError(f"Non-integral value in categorical column '{column}'.")
    raise SourceFormatError(f"Unsupported cell type in categorical column '{column}'.")


def _numeric_value(value: Any, *, column: str) -> float:
    if isinstance(value, bool):
        raise SourceFormatError(f"Unsupported boolean cell type in numeric column '{column}'.")
    if isinstance(value, int):
        number = float(value)
    elif isinstance(value, float):
        number = value
    else:
        raise SourceFormatError(
            f"Column '{column}' requires a numeric cell; text coercion is not permitted."
        )
    if not math.isfinite(number):
        raise SourceFormatError(f"Non-finite numeric value in column '{column}'.")
    return number


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def parse_workbook(
    parsed: ParsedWorkbook,
    *,
    config: Uci412Config = DEFAULT_CONFIG,
    dictionary: FeatureDictionary = DEFAULT_DICTIONARY,
) -> Uci412Dataset:
    """Map a validated workbook into the admitted feature matrix and binary target."""
    if parsed.headers != tuple(config.source_columns) and set(parsed.headers) != set(config.source_columns):
        raise SourceFormatError("Workbook headers changed after structural validation.")
    if len(parsed.rows) != config.expected_row_count:
        raise SourceFormatError(
            f"The workbook contains {len(parsed.rows)} data rows; the audited UCI-412 cohort has "
            f"{config.expected_row_count}."
        )

    column_index = {name: index for index, name in enumerate(parsed.headers)}
    feature_specs: tuple[FeatureSpec, ...] = tuple(dictionary.feature(name) for name in config.feature_names)
    target_index = column_index[TARGET_COLUMN]

    missing_counts: dict[str, int] = {name: 0 for name in config.feature_names}
    observed_tokens: dict[str, dict[str, int]] = {
        name: {} for name in config.categorical_features
    }
    out_of_typical_range: dict[str, int] = {name: 0 for name in config.numeric_features}
    unregistered_token_warnings: dict[str, int] = {}

    x_rows: list[list[float]] = []
    y_values: list[int] = []
    for row in parsed.rows:
        target_raw = row[target_index]
        if _is_blank(target_raw):
            raise SourceFormatError("The workbook contains a blank target label.")
        if not isinstance(target_raw, str):
            raise SourceFormatError("The target column must contain the reviewed text labels only.")
        if target_raw != target_raw.strip():
            raise SourceFormatError(
                "The target column contains a label with surrounding whitespace; exact reviewed "
                "source tokens only are mapped."
            )
        target_token = target_raw
        if target_token in config.positive_source_tokens:
            mapped_target = 1
        elif target_token in config.negative_source_tokens:
            mapped_target = 0
        else:
            raise SourceFormatError(
                "The target column contains a label outside the reviewed 'Cad'/'Normal' mapping."
            )
        y_values.append(mapped_target)

        row_values: list[float] = []
        for spec in feature_specs:
            raw_value = row[column_index[spec.column]]
            if _is_blank(raw_value):
                if spec.column in missing_counts:
                    missing_counts[spec.column] += 1
                row_values.append(float("nan"))
                continue
            if isinstance(raw_value, str) and raw_value.strip() in WRONG_SOURCE_TOKENS:
                raise SourceFormatError(
                    f"Column '{spec.column}' contains a UCI-45 missing/sentinel token; this is not a "
                    "registered UCI-412 missing-value convention."
                )
            if spec.is_numeric:
                number = _numeric_value(raw_value, column=spec.column)
                if spec.plausible_range is not None:
                    low, high = spec.plausible_range
                    if not (low <= number <= high):
                        raise SourceFormatError(
                            f"Column '{spec.column}' contains a value outside its registered "
                            "plausibility guard; the source may be misaligned or have different units."
                        )
                if spec.source_reported_typical_range is not None:
                    low, high = spec.source_reported_typical_range
                    if not (low <= number <= high):
                        out_of_typical_range[spec.column] += 1
                row_values.append(number)
            else:
                token = _categorical_token(raw_value, column=spec.column)
                if spec.vocabulary is None or token not in spec.vocabulary:
                    raise SourceFormatError(
                        f"Column '{spec.column}' contains a category outside the registered vocabulary."
                    )
                observed_tokens[spec.column][token] = observed_tokens[spec.column].get(token, 0) + 1
                row_values.append(float(spec.vocabulary[token]))
        x_rows.append(row_values)

    # Registered but non-admitted columns are still checked for gross misalignment;
    # an unrecognised value there cannot change the model, so it is counted, not fatal.
    non_admitted = [name for name in parsed.headers if name not in config.feature_names and name != TARGET_COLUMN]
    for name in non_admitted:
        spec = dictionary.feature(name)
        index = column_index[name]
        for row in parsed.rows:
            raw_value = row[index]
            if _is_blank(raw_value):
                continue
            try:
                if spec.is_numeric:
                    _numeric_value(raw_value, column=name)
                else:
                    token = _categorical_token(raw_value, column=name)
                    if spec.vocabulary is None or token not in spec.vocabulary:
                        raise SourceFormatError("unregistered category")
            except SourceFormatError:
                unregistered_token_warnings[name] = unregistered_token_warnings.get(name, 0) + 1

    X = np.asarray(x_rows, dtype=np.float64)
    y = np.asarray(y_values, dtype=np.int8)

    for name, count in missing_counts.items():
        if count >= len(parsed.rows):
            raise SourceFormatError(
                f"Admitted predictor '{name}' has no observed values in the workbook."
            )

    class_counts = tuple((label, int(np.count_nonzero(y == label))) for label in (0, 1))
    expected = tuple(sorted(config.expected_class_counts))
    if class_counts != expected:
        raise SourceFormatError(
            "The mapped binary target counts do not match the audited UCI-412 class counts "
            f"({expected[1][1]} positive / {expected[0][1]} negative)."
        )

    audit = {
        "row_count": len(parsed.rows),
        "column_count": len(parsed.headers),
        "class_counts_by_binary_label": {str(label): count for label, count in class_counts},
        "data_sheet_name": parsed.sheet_name,
        "other_sheet_count": parsed.other_sheet_count,
        "header_order_matches_registered_profile": parsed.header_order_matches_registered_profile,
        "blank_cell_counts_by_admitted_column": dict(missing_counts),
        "observed_category_token_counts": {
            name: dict(counts) for name, counts in observed_tokens.items()
        },
        "out_of_source_reported_typical_range_counts": dict(out_of_typical_range),
        "non_admitted_unregistered_token_warnings": dict(unregistered_token_warnings),
        "value_repair_or_row_deletion_performed": False,
        "patient_level_values_retained_in_audit_object": False,
    }
    return Uci412Dataset(
        X=X,
        y=y,
        feature_names=config.feature_names,
        row_count=len(parsed.rows),
        class_counts=class_counts,
        audit=audit,
    )


def load_authorized_dataset(
    source_path: Path,
    *,
    expected_sha256: str,
    expected_size_bytes: int | None = None,
    config: Uci412Config = DEFAULT_CONFIG,
    dictionary: FeatureDictionary = DEFAULT_DICTIONARY,
) -> tuple[SourceSnapshot, Uci412Dataset]:
    """Snapshot, verify, parse, and re-verify the source in one read-only pass."""
    snapshot = read_source_snapshot(
        source_path,
        expected_sha256=expected_sha256,
        expected_size_bytes=expected_size_bytes,
    )
    try:
        workbook = read_xlsx_workbook(Path(source_path), prefer_openpyxl=True)
    except SourceFormatError:
        raise
    except Exception as exc:  # noqa: BLE001 - safe wrapper, no cell contents echoed
        raise SourceFormatError("The workbook could not be parsed as the registered UCI-412 file.") from exc
    parsed = validate_workbook_structure(workbook, config=config)
    dataset = parse_workbook(parsed, config=config, dictionary=dictionary)
    # Re-verify byte identity after parsing: a concurrent replacement must not
    # produce a report attributed to the authorized hash.
    reverified = read_source_snapshot(
        source_path,
        expected_sha256=expected_sha256,
        expected_size_bytes=expected_size_bytes,
    )
    if reverified.sha256 != snapshot.sha256:
        raise ProvenanceError("The source changed during parsing; no result may be accepted.")
    return snapshot, dataset


def sheet_from_rows(
    headers: tuple[str, ...],
    rows: tuple[tuple[Any, ...], ...],
    *,
    sheet_name: str = "Sheet 1 - Table 1",
    other_sheets: tuple[SheetData, ...] = (),
) -> WorkbookData:
    """Build an in-memory ``WorkbookData`` for synthetic tests and the dry-run.

    This helper performs no validation; it exists so synthetic fixtures exercise
    the same structural and value checks as a real workbook without writing an
    .xlsx file or touching protected storage.
    """
    sheets = {sheet_name: SheetData(name=sheet_name, headers=headers, rows=rows)}
    names = [sheet_name]
    for extra in other_sheets:
        if extra.name in sheets:
            raise SourceFormatError("Synthetic workbook sheet names must be unique.")
        sheets[extra.name] = extra
        names.append(extra.name)
    return WorkbookData(sheet_names=tuple(names), sheets=sheets)
