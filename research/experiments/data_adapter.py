"""Narrow, read-only adapter for the single approved UCI-45 processed file.

This is intentionally separate from ``research.intake``: that code is
synthetic-only and must never receive real benchmark rows. The adapter is a
pure parser plus a byte reader; the CLI only invokes it after the D-047 / D-046
local authorization, provenance, hash, Windows-runtime, and Git-ignore guards
have passed.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
import io
import math
from pathlib import Path
import numpy as np

from research.audit.registry import (
    UCI_45_CONVENTIONAL_14_COLUMNS,
    UCI_45_PROCESSED_DOMAIN_RULES,
)
from research.experiments.config import DEFAULT_CONFIG, PROHIBITED_PREDICTORS, ExperimentConfig
from research.experiments.errors import ProvenanceError, SourceFormatError


@dataclass(frozen=True, slots=True)
class ClevelandDataset:
    """In-memory target and five approved predictors; no source identifiers."""

    X: np.ndarray
    y: np.ndarray
    feature_names: tuple[str, ...]
    row_count: int
    binary_target_counts: tuple[tuple[int, int], ...]

    def __post_init__(self) -> None:
        if self.feature_names != DEFAULT_CONFIG.feature_names:
            raise SourceFormatError("Dataset feature names do not match the fixed five-field allowlist.")
        if not isinstance(self.X, np.ndarray) or self.X.ndim != 2:
            raise SourceFormatError("Parsed feature matrix has an invalid shape.")
        if self.X.shape != (self.row_count, len(DEFAULT_CONFIG.feature_names)):
            raise SourceFormatError("Parsed feature matrix has an unexpected column count.")
        if not isinstance(self.y, np.ndarray) or self.y.shape != (self.row_count,):
            raise SourceFormatError("Parsed binary target has an invalid shape.")
        if self.row_count <= 0 or not np.isin(self.y, (0, 1)).all():
            raise SourceFormatError("Parsed binary target is invalid.")
        if not np.isfinite(self.X[~np.isnan(self.X)]).all():
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


@dataclass(frozen=True, slots=True)
class SourceBytes:
    """Hashed byte snapshot. This object contains the source bytes only locally."""

    content: bytes
    sha256: str
    size_bytes: int


def sha256_bytes(content: bytes) -> str:
    import hashlib

    return hashlib.sha256(content).hexdigest()


def _read_source_bytes_read_only(
    source_path: Path,
    *,
    expected_sha256: str,
    expected_size_bytes: int | None = None,
) -> SourceBytes:
    """Read a previously authorized file in binary read-only mode and verify its bytes.

    The function never creates, truncates, or writes to ``source_path``. It is
    deliberately not an authorization check; real-run callers must obtain the
    path and expected hash only from a validated preflight context.
    """
    if source_path.is_symlink() or not source_path.is_file():
        raise ProvenanceError("The authorized processed Cleveland source is missing or unsafe.")
    try:
        before = source_path.stat()
        with source_path.open("rb") as handle:
            content = handle.read()
        after = source_path.stat()
    except OSError as exc:
        raise ProvenanceError("Unable to read the authorized source in read-only mode.") from exc
    digest = sha256_bytes(content)
    if len(expected_sha256) != 64 or digest.lower() != expected_sha256.lower():
        raise ProvenanceError("The local source SHA-256 does not match both approved manifests.")
    if expected_size_bytes is not None and len(content) != expected_size_bytes:
        raise ProvenanceError("The local source byte size does not match protected provenance.")
    # Metadata changes during a read can indicate a concurrent replacement.
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (
        after.st_size,
        after.st_mtime_ns,
        after.st_ino,
    ):
        raise ProvenanceError("The source file changed while its read-only snapshot was being created.")
    if after.st_size != len(content):
        raise ProvenanceError("The source file size changed while its read-only snapshot was being created.")
    return SourceBytes(content=content, sha256=digest, size_bytes=len(content))


def _parse_numeric_token(token: str, *, row_number: int, column_name: str) -> float:
    try:
        value = float(token)
    except (ValueError, OverflowError):
        raise SourceFormatError(
            f"Invalid numeric source token in column '{column_name}' at source row {row_number}."
        ) from None
    if not math.isfinite(value):
        raise SourceFormatError(
            f"Non-finite numeric source token in column '{column_name}' at source row {row_number}."
        )
    return value


def _parse_processed_cleveland_bytes(
    content: bytes,
    *,
    config: ExperimentConfig = DEFAULT_CONFIG,
) -> ClevelandDataset:
    """Parse a strict headerless UCI-45 processed Cleveland CSV byte snapshot.

    The source has 14 columns in the exact registered order. ``?`` becomes
    ``NaN`` for non-target columns. The ``num`` target must be one of 0..4 and
    maps to 0 for source zero, 1 for source values one through four. Only the
    five predeclared columns are copied into ``X``; ``ca``, ``thal``, all other
    columns and ``num`` itself are never model predictors.
    """
    if not isinstance(content, bytes) or not content:
        raise SourceFormatError("Source snapshot is empty or is not a byte string.")
    if config.source_columns != UCI_45_CONVENTIONAL_14_COLUMNS:
        raise SourceFormatError("Registered source column order is not the exact UCI-45 14-column schema.")
    if config.feature_names != ("age", "sex", "cp", "trestbps", "restecg"):
        raise SourceFormatError("Registered predictor allowlist is invalid.")
    if config.target_column != "num" or config.target_column in config.feature_names:
        raise SourceFormatError("The registered target may not enter the predictor matrix.")
    if PROHIBITED_PREDICTORS & set(config.feature_names):
        raise SourceFormatError("A prohibited leakage, angiography, site, identifier, or wearable field is selected.")

    try:
        text = content.decode("ascii", errors="strict")
    except UnicodeDecodeError as exc:
        raise SourceFormatError("The authorized processed source is not strict ASCII numeric CSV.") from exc

    feature_indices = tuple(config.source_columns.index(name) for name in config.feature_names)
    target_index = config.source_columns.index(config.target_column)
    categorical_domains: dict[str, set[float]] = {
        name: set(values) for name, values in UCI_45_PROCESSED_DOMAIN_RULES.items()
    }
    x_rows: list[list[float]] = []
    y_values: list[int] = []

    try:
        reader = csv.reader(io.StringIO(text, newline=""), delimiter=",", strict=True)
        for row_number, row in enumerate(reader, start=1):
            if len(row) != len(UCI_45_CONVENTIONAL_14_COLUMNS):
                raise SourceFormatError(
                    f"Expected exactly 14 source columns at row {row_number}; raw, headed, or altered schemas are rejected."
                )
            if any(not isinstance(token, str) or token.strip() == "" for token in row):
                raise SourceFormatError(f"Blank source token at row {row_number}; only '?' denotes missingness.")
            parsed: list[float] = []
            for column_name, raw_token in zip(UCI_45_CONVENTIONAL_14_COLUMNS, row, strict=True):
                token = raw_token.strip()
                if token == "?":
                    if column_name == config.target_column:
                        raise SourceFormatError(f"Missing target value at source row {row_number}.")
                    parsed.append(float("nan"))
                    continue
                value = _parse_numeric_token(token, row_number=row_number, column_name=column_name)
                domain = categorical_domains.get(column_name)
                if domain is not None and value not in domain:
                    raise SourceFormatError(
                        f"Source category outside the registered vocabulary for '{column_name}' at row {row_number}."
                    )
                if column_name in {"age", "trestbps"} and value <= 0:
                    raise SourceFormatError(
                        f"Non-positive value in approved predictor '{column_name}' at row {row_number}; no zero recoding is applied."
                    )
                parsed.append(value)

            source_target = parsed[target_index]
            if not math.isfinite(source_target) or not source_target.is_integer():
                raise SourceFormatError(f"Target 'num' is not an integer source label at row {row_number}.")
            target_int = int(source_target)
            if target_int in config.negative_source_labels:
                mapped_target = 0
            elif target_int in config.positive_source_labels:
                mapped_target = 1
            else:
                raise SourceFormatError(f"Unexpected source target category at row {row_number}.")
            x_rows.append([parsed[index] for index in feature_indices])
            y_values.append(mapped_target)
    except csv.Error as exc:
        raise SourceFormatError("Malformed CSV quoting or delimiter in the processed Cleveland source.") from exc

    if len(x_rows) != config.expected_row_count:
        raise SourceFormatError(
            f"Source row count mismatch: expected {config.expected_row_count}, found {len(x_rows)}."
        )
    labels = np.asarray(y_values, dtype=np.int8)
    counts = tuple((label, int(np.count_nonzero(labels == label))) for label in (0, 1))
    if counts != config.expected_binary_target_counts:
        raise SourceFormatError("Mapped target counts do not match the locally audited 164/139 source totals.")

    features = np.asarray(x_rows, dtype=np.float64)
    if features.shape != (config.expected_row_count, len(config.feature_names)):
        raise SourceFormatError("Parsed predictor matrix does not match the frozen five-column schema.")
    for column_index, column_name in enumerate(config.feature_names):
        if not np.isfinite(features[~np.isnan(features[:, column_index]), column_index]).all():
            raise SourceFormatError(f"Observed predictor values in '{column_name}' are non-finite.")
        if np.isnan(features[:, column_index]).all():
            raise SourceFormatError(f"Predictor '{column_name}' contains no observed source values.")
    return ClevelandDataset(
        X=features,
        y=labels,
        feature_names=config.feature_names,
        row_count=len(y_values),
        binary_target_counts=counts,
    )
