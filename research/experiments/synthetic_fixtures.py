"""Invented, deterministic software fixtures for runner tests and dry-run only.

Nothing in this module reads a filesystem dataset or represents a real patient.
The 14-column layout mirrors the registered schema solely to exercise parsing.
"""
from __future__ import annotations

import csv
import io

import numpy as np

from research.experiments.config import DEFAULT_CONFIG, ExperimentConfig
from research.experiments.data_adapter import ClevelandDataset, _parse_processed_cleveland_bytes


def make_synthetic_source_bytes(
    *,
    seed: int = 47047,
    config: ExperimentConfig = DEFAULT_CONFIG,
) -> bytes:
    """Build 303 wholly invented source-shaped rows in memory (never writes a file)."""
    rng = np.random.default_rng(seed)
    source_targets = np.asarray(
        [0] * 164 + [1] * 35 + [2] * 35 + [3] * 35 + [4] * 34,
        dtype=np.int8,
    )
    rng.shuffle(source_targets)
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")

    for row_index in range(config.expected_row_count):
        # These are random invented values for software compatibility tests;
        # they are not copied or sampled from the Cleveland dataset.
        row: list[object] = [
            int(rng.integers(30, 79)),
            int(rng.integers(0, 2)),
            int(rng.integers(1, 5)),
            int(rng.integers(90, 201)),
            int(rng.integers(100, 601)),
            int(rng.integers(0, 2)),
            int(rng.integers(0, 3)),
            int(rng.integers(70, 211)),
            int(rng.integers(0, 2)),
            round(float(rng.normal(0.5, 1.2)), 1),
            int(rng.integers(1, 4)),
            int(rng.integers(0, 4)),
            int(rng.choice([3, 6, 7])),
            int(source_targets[row_index]),
        ]
        # Missing tokens exercise fold-local numeric/categorical imputation.
        # The target is never missing; no synthetic missing-reason field exists.
        for column_index in (0, 1, 2, 3, 6):
            if rng.random() < 0.015:
                row[column_index] = "?"
        for column_index in (4, 5, 7, 8, 9, 10, 11, 12):
            if rng.random() < 0.01:
                row[column_index] = "?"
        writer.writerow(row)

    return buffer.getvalue().encode("ascii")


def make_synthetic_dataset(
    *,
    seed: int = 47047,
    config: ExperimentConfig = DEFAULT_CONFIG,
) -> ClevelandDataset:
    """Parse an in-memory generated fixture through the real schema parser."""
    return _parse_processed_cleveland_bytes(
        make_synthetic_source_bytes(seed=seed, config=config),
        config=config,
    )
