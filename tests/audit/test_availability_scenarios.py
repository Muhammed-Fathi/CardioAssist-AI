"""Synthetic-only tests: descriptive joint availability & untouched originals.

No real patient files are in the repository or CI.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from research.audit.availability_scenarios import (
    MEASUREMENT_STAGE_PANELS,
    descriptive_panel_counts,
    run_availability_audit,
)
from research.audit.cli import REPO_ROOT
from research.audit.synthetic_fixtures import materialize_synthetic_audit_suite


def test_joint_availability_and_zero_sensitivity_do_not_transform() -> None:
    rows = [
        {"age": 50, "sex": 1, "cp": 2, "trestbps": 130, "chol": 0, "fbs": 0, "restecg": 0},
        {"age": 60, "sex": 0, "cp": 3, "trestbps": 0, "chol": 200, "fbs": 0, "restecg": 1},
        {"age": 70, "sex": 1, "cp": 4, "trestbps": None, "chol": 180, "fbs": 0, "restecg": 0},
    ]
    original = [dict(row) for row in rows]

    full = descriptive_panel_counts(rows, MEASUREMENT_STAGE_PANELS["resting_plus_labs"])
    assert full == {
        "records_screened": 3,
        "literal_source_coding_jointly_present": 2,
        "hypothetical_zero_unavailable_jointly_present": 0,
        "lost_if_zero_unavailable": 2,
    }
    # Legitimate zero codes in fbs/restecg are never tagged as missing.
    history = descriptive_panel_counts(rows, MEASUREMENT_STAGE_PANELS["history_only"])
    assert history["literal_source_coding_jointly_present"] == 3
    assert history["hypothetical_zero_unavailable_jointly_present"] == 3
    assert rows == original


@pytest.mark.parametrize(
    "columns",
    [("num",), ("ca",), ("thal",), ("age", "age"), ()],
)
def test_prohibited_or_duplicate_fields_fail_closed(columns) -> None:
    with pytest.raises(ValueError):
        descriptive_panel_counts([{"age": 60}], columns)


def test_synthetic_full_provenance_quarantine_guard(tmp_path: Path) -> None:
    suite = materialize_synthetic_audit_suite(tmp_path, authorize_all=True)
    files = sorted((tmp_path / "data/raw/uci-45").iterdir())
    before = {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    result = run_availability_audit(
        repo_root=REPO_ROOT,
        base_data_parent=tmp_path,
        auth_manifest_path=Path(suite["auth_manifest_path"]),
        provenance_manifest_path=Path(suite["provenance_manifest_path"]),
        allow_external_tmp_root=tmp_path,
    )
    after = {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    assert before == after
    assert result["raw_cleveland_parsed"] is False
    assert result["modeled_or_transformed_data"] is False
    assert result["gate_pt"] == "CLOSED"
    assert set(result["cohorts"]) == {"cleveland", "hungarian", "switzerland", "va"}
    assert set(result["cohorts"]["hungarian"]["stage_availability"]) == set(MEASUREMENT_STAGE_PANELS)

    for cohort, counts in result["cohorts"].items():
        for data in counts["stage_availability"].values():
            assert 0 <= data["hypothetical_zero_unavailable_jointly_present"] <= (
                data["literal_source_coding_jointly_present"]
            ) <= counts["source_row_count"]


def test_no_real_patient_rows_in_summary(tmp_path: Path) -> None:
    suite = materialize_synthetic_audit_suite(tmp_path, authorize_all=True)
    result = run_availability_audit(
        repo_root=REPO_ROOT,
        base_data_parent=tmp_path,
        auth_manifest_path=Path(suite["auth_manifest_path"]),
        provenance_manifest_path=Path(suite["provenance_manifest_path"]),
        allow_external_tmp_root=tmp_path,
    )
    from json import dumps

    blob = dumps(result)
    assert "normalized_rows" not in blob
    assert "raw_row_fingerprints" not in blob
    assert "row_signature" not in blob
    assert "SYNTH_PATIENT_SENTINEL_99182" not in blob
