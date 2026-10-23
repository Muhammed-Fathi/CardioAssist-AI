"""Schema and label tests using generated, invented source-shaped fixtures only."""
from __future__ import annotations

import csv
import io
from pathlib import Path

import numpy as np
import pytest

from research.experiments.config import DEFAULT_CONFIG, PROHIBITED_PREDICTORS
from research.experiments.data_adapter import (
    _parse_processed_cleveland_bytes,
    _read_source_bytes_read_only,
)
from research.experiments.errors import ProvenanceError, SourceFormatError
from research.experiments.synthetic_fixtures import make_synthetic_source_bytes


def _rows(content: bytes) -> list[list[str]]:
    return list(csv.reader(io.StringIO(content.decode("ascii"), newline="")))


def _bytes(rows: list[list[str]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerows(rows)
    return buffer.getvalue().encode("ascii")


def test_registered_schema_labels_and_five_predictor_projection() -> None:
    content = make_synthetic_source_bytes(seed=211)
    source_rows = _rows(content)
    dataset = _parse_processed_cleveland_bytes(content)

    assert len(source_rows) == DEFAULT_CONFIG.expected_row_count == 303
    assert all(len(row) == 14 for row in source_rows)
    assert dataset.feature_names == ("age", "sex", "cp", "trestbps", "restecg")
    assert dataset.X.shape == (303, 5)
    assert dataset.y.shape == (303,)
    assert dataset.binary_target_counts == ((0, 164), (1, 139))
    expected_labels = np.asarray([0 if int(row[13]) == 0 else 1 for row in source_rows])
    np.testing.assert_array_equal(dataset.y, expected_labels)
    assert set(int(row[13]) for row in source_rows) == {0, 1, 2, 3, 4}
    assert not dataset.X.flags.writeable
    assert not dataset.y.flags.writeable
    # All other source columns, including ca/thal/num, are absent from X.
    assert dataset.X.shape[1] == 5


def test_question_mark_is_missing_and_source_rows_are_not_mutated() -> None:
    content = make_synthetic_source_bytes(seed=908)
    original = bytes(content)
    dataset = _parse_processed_cleveland_bytes(content)
    assert np.isnan(dataset.X).any()
    assert content == original
    assert np.isfinite(dataset.X[~np.isnan(dataset.X)]).all()


def test_wrong_row_count_column_count_header_and_raw_schema_fail_closed() -> None:
    rows = _rows(make_synthetic_source_bytes(seed=44))

    with pytest.raises(SourceFormatError, match="row count mismatch"):
        _parse_processed_cleveland_bytes(_bytes(rows[:-1]))

    extra_column = [list(row) for row in rows]
    extra_column[0].append("synthetic_extra")
    with pytest.raises(SourceFormatError, match="exactly 14"):
        _parse_processed_cleveland_bytes(_bytes(extra_column))

    header = ["age", "sex", "cp", "trestbps", "chol", "fbs", "restecg", "thalach", "exang", "oldpeak", "slope", "ca", "thal", "num"]
    with pytest.raises(SourceFormatError):
        _parse_processed_cleveland_bytes(_bytes([header, *rows[1:]]))

    # A fabricated raw-style 76-field line cannot be confused with the processed file.
    raw_style = [list(row) for row in rows]
    raw_style[0] = ["0"] * 76
    with pytest.raises(SourceFormatError, match="exactly 14"):
        _parse_processed_cleveland_bytes(_bytes(raw_style))


def test_missing_target_unregistered_category_and_target_count_mismatch_fail() -> None:
    rows = _rows(make_synthetic_source_bytes(seed=991))
    missing_target = [list(row) for row in rows]
    missing_target[0][13] = "?"
    with pytest.raises(SourceFormatError, match="Missing target"):
        _parse_processed_cleveland_bytes(_bytes(missing_target))

    bad_category = [list(row) for row in rows]
    bad_category[0][1] = "9"
    with pytest.raises(SourceFormatError, match="vocabulary"):
        _parse_processed_cleveland_bytes(_bytes(bad_category))

    wrong_target_counts = [list(row) for row in rows]
    first_zero = next(i for i, row in enumerate(wrong_target_counts) if row[13] == "0")
    wrong_target_counts[first_zero][13] = "1"
    with pytest.raises(SourceFormatError, match="target counts"):
        _parse_processed_cleveland_bytes(_bytes(wrong_target_counts))


def test_target_leakage_angiography_identifier_and_wearable_features_are_rejected() -> None:
    base_content = make_synthetic_source_bytes(seed=17)
    prohibited = sorted(PROHIBITED_PREDICTORS)
    assert {"num", "ca", "thal", "LAD", "LCX", "RCA", "lmt", "id", "ccf", "name", "site"}.issubset(prohibited)
    assert {"wearable_heart_rate", "wearable_ecg", "steps"}.issubset(prohibited)

    for field in prohibited:
        malicious_config = DEFAULT_CONFIG.__class__(
            **{
                **{
                    name: getattr(DEFAULT_CONFIG, name)
                    for name in DEFAULT_CONFIG.__dataclass_fields__
                },
                "feature_names": (field, "sex", "cp", "trestbps", "restecg"),
            }
        )
        with pytest.raises(SourceFormatError):
            _parse_processed_cleveland_bytes(base_content, config=malicious_config)


def test_read_only_source_snapshot_rejects_hash_mismatch_and_preserves_bytes(tmp_path: Path) -> None:
    source = tmp_path / "synthetic-only-processed-cleveland.data"
    content = make_synthetic_source_bytes(seed=72)
    source.write_bytes(content)
    before_stat = source.stat()

    with pytest.raises(ProvenanceError, match="SHA-256"):
        _read_source_bytes_read_only(source, expected_sha256="0" * 64)
    assert source.read_bytes() == content

    import hashlib

    snapshot = _read_source_bytes_read_only(
        source,
        expected_sha256=hashlib.sha256(content).hexdigest(),
        expected_size_bytes=len(content),
    )
    assert snapshot.content == content
    assert snapshot.size_bytes == len(content)
    assert source.read_bytes() == content
    assert source.stat().st_mtime_ns == before_stat.st_mtime_ns


def test_error_messages_do_not_echo_untrusted_source_cells() -> None:
    rows = _rows(make_synthetic_source_bytes(seed=20))
    rows[0][0] = "SYNTHETIC_SENTINEL_NOT_A_PATIENT_VALUE"
    with pytest.raises(SourceFormatError) as exc_info:
        _parse_processed_cleveland_bytes(_bytes(rows))
    assert "SYNTHETIC_SENTINEL_NOT_A_PATIENT_VALUE" not in str(exc_info.value)
