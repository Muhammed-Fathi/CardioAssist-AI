"""Test fixtures for the source-specific UCI-412 research harness.

Every dataset used by these tests is generated in memory. No real UCI-412 row,
file, or patient-level value is read, written, or asserted on.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from research.uci412.adapter import (
    Uci412Dataset,
    parse_workbook,
    sheet_from_rows,
    validate_workbook_structure,
)
from research.uci412.config import DEFAULT_CONFIG, Uci412Config
from research.uci412.synthetic import synthetic_workbook_rows


def small_config() -> Uci412Config:
    """Registered-shape config with far fewer fits, for software tests only."""
    return replace(
        DEFAULT_CONFIG,
        outer_folds=3,
        inner_folds=3,
        outer_repeat_seeds=(20261024,),
        rf_n_estimators=20,
        rf_max_depths=(3,),
        bootstrap_resamples=40,
        calibration_bins=3,
        negative_control_seeds=(20262004,),
    )


def synthetic_rows(
    config: Uci412Config | None = None,
) -> tuple[tuple[str, ...], list[tuple[Any, ...]]]:
    active = config or DEFAULT_CONFIG
    headers, rows = synthetic_workbook_rows(config=active)
    return headers, [tuple(row) for row in rows]


def dataset_from_rows(
    headers: tuple[str, ...],
    rows: list[tuple[Any, ...]] | tuple[tuple[Any, ...], ...],
    *,
    config: Uci412Config | None = None,
    other_sheets: tuple[Any, ...] = (),
) -> Uci412Dataset:
    active = config or DEFAULT_CONFIG
    workbook = sheet_from_rows(headers, tuple(tuple(row) for row in rows), other_sheets=other_sheets)
    parsed = validate_workbook_structure(workbook, config=active)
    return parse_workbook(parsed, config=active)


def make_dataset(config: Uci412Config | None = None) -> Uci412Dataset:
    active = config or small_config()
    headers, rows = synthetic_rows(active)
    return dataset_from_rows(headers, rows, config=active)


@pytest.fixture(scope="session")
def session_dataset() -> Uci412Dataset:
    return make_dataset(small_config())


@pytest.fixture()
def config() -> Uci412Config:
    return small_config()


@pytest.fixture()
def dataset(config: Uci412Config) -> Uci412Dataset:
    return make_dataset(config)
