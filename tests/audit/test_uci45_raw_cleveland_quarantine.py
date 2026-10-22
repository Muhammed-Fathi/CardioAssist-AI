"""Synthetic-only regression tests for opt-in DA-A2 raw Cleveland quarantine.

Never uses real UCI or patient-level data, and never trains a model.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from research.audit.cli import REPO_ROOT, run_local_dataset_audit
from research.audit.exceptions import FormatValidationError, GovernanceAuthorizationError
from research.audit.reporting import validate_strict_metadata_report_schema
from research.audit.synthetic_fixtures import materialize_synthetic_audit_suite


def _fixture(tmp_path: Path, *, invalid_utf8: bool = True) -> dict:
    suite = materialize_synthetic_audit_suite(tmp_path, authorize_all=True)
    if invalid_utf8:
        raw = tmp_path / "data/raw/uci-45/cleveland.data"
        with raw.open("ab") as f:
            f.write(b"\x8e")
        prov = Path(suite["provenance_manifest_path"])
        doc = json.loads(prov.read_text(encoding="utf-8"))
        for item in doc["files"]:
            if item["dataset_id"] == "DA-A2" and item["filename"] == "cleveland.data":
                b = raw.read_bytes()
                item["sha256"] = hashlib.sha256(b).hexdigest()
                item["size_bytes"] = len(b)
        prov.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return suite


def _run(tmp_path: Path, suite: dict, *, quarantine: bool, datasets=("DA-A2",)):
    return run_local_dataset_audit(
        repo_root=REPO_ROOT,
        base_data_parent=tmp_path,
        auth_manifest_path=Path(suite["auth_manifest_path"]),
        provenance_manifest_path=Path(suite["provenance_manifest_path"]),
        requested_datasets=datasets,
        is_synthetic_fixture_run=True,
        allow_external_tmp_root=tmp_path,
        quarantine_raw_cleveland=quarantine,
    )


def test_default_rejects_source_warned_non_utf8_raw_cleveland(tmp_path: Path):
    suite = _fixture(tmp_path)
    with pytest.raises(FormatValidationError, match="Corrupt UTF-8 text in 'cleveland.data'"):
        _run(tmp_path, suite, quarantine=False)


def test_explicit_quarantine_yields_only_flagged_partial_report(tmp_path: Path):
    suite = _fixture(tmp_path)
    report, md = _run(tmp_path, suite, quarantine=True)
    validate_strict_metadata_report_schema(report)

    a2 = report["dataset_audits"]["DA-A2"]
    assert a2["evidence_status"] == "REQUIRES APPROVAL"
    assert len(a2["quarantined_raw_files"]) == 1
    q = a2["quarantined_raw_files"][0]
    assert q["filename"] == "cleveland.data"
    assert q["raw_parsed"] is False
    assert q["raw_processed_correspondence_evaluated"] is False
    assert len(q["provenance_sha256"]) == 64
    assert "cleveland.data" not in a2["raw_files"]
    assert "cleveland" not in a2["raw_vs_processed_correspondence"]
    assert len(a2["processed_files"]) == 4
    assert len(a2["raw_files"]) == 3
    assert len(a2["raw_vs_processed_correspondence"]) == 3
    assert "PARTIAL AUDIT" in md
    assert report["safety_and_non_fitting_certification"]["originals_byte_identical"] is True
    assert report["safety_and_non_fitting_certification"]["patient_level_rows_emitted"] == 0
    assert report["safety_and_non_fitting_certification"]["model_fitting_performed"] is False


@pytest.mark.parametrize("datasets", [("DA-A1",), ("DA-A1", "DA-A2"), None])
def test_quarantine_requires_exact_da_a2_scope(tmp_path: Path, datasets):
    suite = _fixture(tmp_path, invalid_utf8=False)
    with pytest.raises(GovernanceAuthorizationError, match="explicitly scope"):
        _run(tmp_path, suite, quarantine=True, datasets=datasets)


def test_healthy_synthetic_raw_remains_parsed_without_opt_in(tmp_path: Path):
    suite = _fixture(tmp_path, invalid_utf8=False)
    report, _ = _run(tmp_path, suite, quarantine=False)
    a2 = report["dataset_audits"]["DA-A2"]
    assert a2["quarantined_raw_files"] == []
    assert a2["evidence_status"] == "VERIFIED"
    assert len(a2["raw_files"]) == 4
    assert len(a2["raw_vs_processed_correspondence"]) == 4
