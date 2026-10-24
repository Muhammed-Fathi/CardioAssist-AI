"""Canonical, versioned description of the UCI-412 (DA-A1) source file.

Only public metadata and maintainer-reported aggregate audit facts are recorded
here. No patient-level value, row, or hash of a patient record exists in this
repository. Exact source column names come from the UCI-412/411 public column
structure documented in ``research/audit/registry.py``; exact workbook header
spelling and column order remain unverified until a local human audit confirms
them (see ``docs/research/gate-pt/08_m3a_uci412_source_specific_benchmark_SPECIFICATION.md``).

Amendment A-1 (2026-10-24, ``docs/research/gate-pt/10_m3a_uci412_source_encoding_AMENDMENT_A1.md``)
records the maintainer-executed, SHA-256-verified read-only audit of all 303
records: six admitted categorical predictors carry **numeric** ``0``/``1`` cells
rather than the previously *assumed* ``Y``/``N``/``Yes``/``No`` text tokens. The
six are enumerated in ``NUMERIC_BINARY_SOURCE_COLUMNS`` and are the **only**
columns for which any numeric-to-code source conversion is permitted. Every
other admitted categorical predictor keeps its registered text vocabulary.
"""
from __future__ import annotations

from typing import Final

from research.audit.registry import (
    UCI_412_ECHO_FEATURES,
    UCI_412_FEATURE_GROUPS,
    UCI_412_LAB_FEATURES,
    UCI_412_TARGET_COLUMN,
)

DATASET_ID: Final[str] = "DA-A1"
SOURCE_ID: Final[str] = "UCI-412"
SOURCE_TITLE: Final[str] = "Z-Alizadeh Sani (UCI Machine Learning Repository, id 412)"

SOURCE_FILENAME: Final[str] = "Z-Alizadeh sani dataset.xlsx"
SOURCE_RELATIVE_PATH: Final[str] = "data/raw/uci-412/Z-Alizadeh sani dataset.xlsx"
CANONICAL_SOURCE_URL: Final[str] = "https://archive.ics.uci.edu/dataset/412/z+alizadeh+sani"
CANONICAL_DOI: Final[str] = "10.24432/C5Q31T"
LICENSE_SPDX: Final[str] = "CC-BY-4.0"

#: SHA-256 of the exact workbook bytes recorded by the maintainer's 2026-10-22
#: local read-only D-046 audit. It is an integrity cross-check only: local
#: provenance must independently verify the file actually used for a run.
AUDITED_REFERENCE_SHA256: Final[str] = (
    "90fefd4ecdb6263b3f2a260bb2b5d3b9fa92ba35d626dd56ad8c6db5fbbad163"
)

EXPECTED_ROW_COUNT: Final[int] = 303
EXPECTED_POSITIVE_COUNT: Final[int] = 216  # source token 'Cad'
EXPECTED_NEGATIVE_COUNT: Final[int] = 87  # source token 'Normal'

#: A 120 KB workbook is the real source; anything this large is not the file
#: this harness was written for and is rejected before parsing.
MAX_SOURCE_BYTES: Final[int] = 8 * 1024 * 1024

SOURCE_PROFILE_ID: Final[str] = "uci412_da_a1_workbook_profile_v1"

#: The 55 predictor columns observed in the delivered DA-A1 workbook, in the
#: group order published by UCI, followed by the target column.
#:
#: The official landing page describes "54 features" across four groups, while
#: the maintainer's local audit observed 55 predictors plus ``Cath`` with ``BBB``
#: present. Both facts are registered verbatim; the discrepancy is documented,
#: not silently resolved.
SOURCE_COLUMNS: Final[tuple[str, ...]] = (
    *UCI_412_FEATURE_GROUPS["demographic"],
    *UCI_412_FEATURE_GROUPS["symptom_and_examination"],
    *UCI_412_FEATURE_GROUPS["ecg"],
    *UCI_412_FEATURE_GROUPS["laboratory_and_echocardiography"],
    UCI_412_TARGET_COLUMN,
)

PREDICTOR_COLUMNS: Final[tuple[str, ...]] = SOURCE_COLUMNS[:-1]
TARGET_COLUMN: Final[str] = UCI_412_TARGET_COLUMN
ECHO_COLUMNS: Final[frozenset[str]] = UCI_412_ECHO_FEATURES
LAB_COLUMNS: Final[frozenset[str]] = UCI_412_LAB_FEATURES

#: Columns that must never be read as predictors in any panel.
#:
#: ``Cath`` is the outcome; ``LAD``/``LCX``/``RCA`` exist only in UCI-411 and
#: define the same angiographic outcome (L-03); the remaining names are UCI-45
#: or identifier/administrative fields that must never appear in this workbook.
PROHIBITED_PREDICTORS: Final[frozenset[str]] = frozenset(
    {
        TARGET_COLUMN,
        "LAD",
        "LCX",
        "RCA",
        "num",
        "ca",
        "thal",
        "lmt",
        "ladprox",
        "laddist",
        "diag",
        "cxmain",
        "ramus",
        "om1",
        "om2",
        "rcaprox",
        "rcadist",
        "cmo",
        "cday",
        "cyr",
        "id",
        "ccf",
        "name",
        "site",
        "patient_id",
        "patient_ref",
        "mrn",
        "wearable_heart_rate",
        "heart_rate_bpm",
        "steps",
        "wearable_ecg",
        "monitoring_observation",
    }
)

#: Exact source target tokens (case sensitive, as recorded by the local audit).
TARGET_POSITIVE_TOKENS: Final[tuple[str, ...]] = ("Cad",)
TARGET_NEGATIVE_TOKENS: Final[tuple[str, ...]] = ("Normal",)

#: Amendment A-1 — the **exhaustive** set of admitted predictors whose delivered
#: cells are numeric ``0``/``1`` instead of text tokens.
#:
#: Evidence (recorded by the maintainer's human-executed, read-only, SHA-256
#: verified local audit of 2026-10-24 over all 303 source records and all 12
#: admitted categorical predictors; the workbook bytes were verified identical
#: before and after the audit):
#:
#: * ``DM`` 0/1 = 213/90, ``HTN`` 124/179, ``Current Smoker`` 240/63,
#:   ``EX-Smoker`` 293/10, ``FH`` 255/48, ``Typical Chest Pain`` 139/164;
#:   no blanks in any of the six.
#: * The remaining six admitted categorical predictors (``Sex``, ``DLP``,
#:   ``Atypical``, ``Nonanginal``, ``Exertional CP``, ``Dyspnea``) hold
#:   registered values in 303/303 records.
#: * Secondary literature describes these six attributes as binary 0/1
#:   (``https://doi.org/10.3390/electronics11030315`` Table 1;
#:   ``https://pmc.ncbi.nlm.nih.gov/articles/PMC7037941/``).
#: * Dataset identity: ``https://doi.org/10.24432/C5Q31T``.
#:
#: This is supporting evidence, not an official per-column codebook: the UCI
#: landing page documents no per-field coding (see doc 08 §5.5). The audit
#: establishes the *representation* (numeric 0/1); the *direction*
#: (0 = absent/false, 1 = present/true) is a provisional, explicitly reviewed
#: inference recorded in the feature dictionary and the amendment document.
#:
#: Duplicated here in code — like ``PRIMARY_PANEL_COLUMNS`` — so a JSON-only
#: dictionary edit can never widen or narrow the numeric-conversion allowlist.
NUMERIC_BINARY_SOURCE_COLUMNS: Final[tuple[str, ...]] = (
    "DM",
    "HTN",
    "Current Smoker",
    "EX-Smoker",
    "FH",
    "Typical Chest Pain",
)

#: Identifier of the only permitted numeric-to-code source conversion. A single
#: fixed id keeps the mapping auditable: the adapter has no other numeric
#: categorical path, and no global automatic coercion exists anywhere.
NUMERIC_BINARY_SOURCE_ENCODING_ID: Final[str] = "numeric_binary_0_1_v1"
NUMERIC_BINARY_SOURCE_ENCODING_KIND: Final[str] = "NUMERIC_BINARY_0_1"
NUMERIC_BINARY_SOURCE_SEMANTICS: Final[tuple[tuple[int, str], ...]] = (
    (0, "ABSENT_OR_FALSE"),
    (1, "PRESENT_OR_TRUE"),
)

#: Columns whose registered text vocabularies are preserved unchanged. Recorded
#: as an explicit positive statement so "the other six keep their vocabulary" is
#: a checkable fact rather than an omission.
TEXT_CATEGORICAL_SOURCE_COLUMNS: Final[tuple[str, ...]] = (
    "Sex",
    "DLP",
    "Atypical",
    "Nonanginal",
    "Exertional CP",
    "Dyspnea",
)

#: Tokens that indicate the wrong source file rather than a missing value.
#: ``?`` is the UCI-45 missing marker and ``-9`` its raw numeric sentinel.
WRONG_SOURCE_TOKENS: Final[frozenset[str]] = frozenset({"?", "-9", "-9.0"})

SOURCE_DATA_SHEET_HINT: Final[str] = "Sheet 1 - Table 1"

#: Aggregate facts that an authorized run re-checks before modelling. They are
#: integrity assertions, not model inputs or clinical claims.
EXPECTED_CLASS_COUNTS: Final[tuple[tuple[int, int], ...]] = (
    (0, EXPECTED_NEGATIVE_COUNT),
    (1, EXPECTED_POSITIVE_COUNT),
)


def column_group(column: str) -> str:
    """Return the published UCI feature group for a registered column."""
    if column == TARGET_COLUMN:
        return "target_label"
    for group, columns in UCI_412_FEATURE_GROUPS.items():
        if column in columns:
            return group
    raise KeyError(f"'{column}' is not a registered UCI-412 source column.")
