"""Deterministic, clearly-labelled synthetic UCI-412 fixtures for software tests.

Every value produced here is invented for exercising the code path. Nothing in
this module is a record of a real person, a benchmark sample, or evidence of
clinical performance. Synthetic fixtures never carry real patient structure and
are never written to ``data/`` in the repository.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

import numpy as np

from research.audit.xlsx_reader import write_synthetic_xlsx
from research.uci412.config import DEFAULT_CONFIG, Uci412Config
from research.uci412.source_spec import (
    NUMERIC_BINARY_SOURCE_COLUMNS,
    SOURCE_COLUMNS,
    TARGET_COLUMN,
)

SYNTHETIC_SCOPE = "SYNTHETIC_SOFTWARE_FIXTURE_NOT_UCI_DATA"
DEFAULT_SYNTHETIC_SEED = 412303

#: Text-token binary columns. The six numeric-0/1 columns of Amendment A-1 are
#: generated separately so the fixture matches the audited source encoding: a
#: synthetic workbook that still emitted "Y"/"N" there would exercise a source
#: representation this harness now correctly refuses.
_TEXT_BINARY_COLUMNS: tuple[str, ...] = (
    "Obesity",
    "CRF",
    "CVA",
    "Airway disease",
    "Thyroid Disease",
    "CHF",
    "DLP",
    "Edema",
    "Weak Peripheral Pulse",
    "Lung rales",
    "Systolic Murmur",
    "Diastolic Murmur",
    "Typical Chest Pain",
    "Dyspnea",
    "Atypical",
    "Nonanginal",
    "Exertional CP",
    "LowTH Ang",
    "Q Wave",
    "St Elevation",
    "St Depression",
    "Tinversion",
    "LVH",
    "Poor R Progression",
    "BBB",
)

_NUMERIC_BINARY_COLUMNS: tuple[str, ...] = NUMERIC_BINARY_SOURCE_COLUMNS

_NUMERIC_RANGES: dict[str, tuple[float, float]] = {
    "Age": (30.0, 86.0),
    "Weight": (48.0, 120.0),
    "Length": (140.0, 188.0),
    "BMI": (18.1, 40.9),
    "BP": (90.0, 190.0),
    "PR": (50.0, 110.0),
    "FBS": (70.0, 300.0),
    "CR": (0.5, 2.2),
    "TG": (60.0, 380.0),
    "LDL": (50.0, 220.0),
    "HDL": (22.0, 85.0),
    "BUN": (8.0, 55.0),
    "ESR": (2.0, 55.0),
    "HB": (9.0, 18.5),
    "K": (3.2, 5.6),
    "Na": (130.0, 150.0),
    "WBC": (3200.0, 12800.0),
    "Lymph": (9.0, 49.0),
    "Neut": (34.0, 88.0),
    "PLT": (110.0, 420.0),
    "EF-TTE": (20.0, 70.0),
    "Region RWMA": (0.0, 3.0),
}


def synthetic_workbook_rows(
    *,
    config: Uci412Config = DEFAULT_CONFIG,
    seed: int = DEFAULT_SYNTHETIC_SEED,
) -> tuple[tuple[str, ...], tuple[tuple[Any, ...], ...]]:
    """Build the exact registered header row plus generated data rows."""
    rng = np.random.default_rng(int(seed))
    n = config.expected_row_count
    positives = config.expected_counts[1]
    negatives = config.expected_counts[0]
    labels = np.concatenate(
        (np.ones(positives, dtype=np.int8), np.zeros(negatives, dtype=np.int8))
    )
    rng.shuffle(labels)

    rows: list[tuple[Any, ...]] = []
    for index in range(n):
        record: dict[str, Any] = {}
        for column, (low, high) in _NUMERIC_RANGES.items():
            if column in {"Age", "Weight", "Length", "BP", "PR"}:
                record[column] = int(round(rng.uniform(low, high)))
            elif column in {"WBC", "PLT"}:
                record[column] = int(round(rng.uniform(low, high)))
            else:
                record[column] = round(float(rng.uniform(low, high)), 1)
        record["BMI"] = round(
            record["Weight"] / ((record["Length"] / 100.0) ** 2), 1
        )
        record["Region RWMA"] = int(record["Region RWMA"])
        record["Sex"] = "Male" if rng.random() < 0.72 else "Fmale"
        vector = rng.random(len(_TEXT_BINARY_COLUMNS))
        for column, probability in zip(_TEXT_BINARY_COLUMNS, vector, strict=True):
            record[column] = "Y" if probability < 0.35 else "N"
        for column in _NUMERIC_BINARY_COLUMNS:
            # Numeric 0/1, exactly the audited DA-A1 representation (Amendment A-1).
            record[column] = int(rng.integers(0, 2))
        record["Function Class"] = int(rng.integers(1, 5))
        record["VHD"] = "N" if rng.random() < 0.6 else ("Mild" if rng.random() < 0.5 else "Moderate")
        record[TARGET_COLUMN] = "Cad" if int(labels[index]) == 1 else "Normal"
        rows.append(tuple(record[column] for column in SOURCE_COLUMNS))
    return tuple(SOURCE_COLUMNS), tuple(rows)


def write_synthetic_workbook(
    path: Path,
    *,
    config: Uci412Config = DEFAULT_CONFIG,
    seed: int = DEFAULT_SYNTHETIC_SEED,
) -> Path:
    """Write a synthetic workbook for an isolated test repository; never the real path."""
    target = Path(path)
    if target.name != config.source_relative_path.rsplit("/", 1)[-1]:
        raise ValueError("Synthetic workbooks must use the exact registered file name.")
    headers, rows = synthetic_workbook_rows(config=config, seed=seed)
    write_synthetic_xlsx(
        target,
        [
            ("Sheet 1 - Table 1", headers, rows),
            ("Auxiliary", ("Note",), ()),
        ],
    )
    return target


def synthetic_rows_as_lists(rows: Sequence[Sequence[Any]]) -> list[list[Any]]:
    return [list(row) for row in rows]
