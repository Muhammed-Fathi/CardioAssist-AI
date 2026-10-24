"""Aggregate-only report construction, protected output, and privacy guards."""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import numpy as np
import pytest

from research.uci412 import reporting
from research.uci412.config import DEFAULT_CONFIG, REPOSITORY_ROOT
from research.uci412.errors import ProvenanceError, StorageProtectionError
from research.uci412.evaluation import (
    assert_no_target_leakage,
    run_label_shuffle_negative_control,
    run_nested_cv,
)
from research.uci412.reporting import (
    FORBIDDEN_REPORT_KEYS,
    REPORT_FILENAME,
    REPORT_TYPE,
    build_run_report,
    package_fingerprints,
    predictions_csv_bytes,
    validate_aggregate_report,
    write_run_outputs,
)
from research.uci412.safety import PreflightContext, create_protected_run_directory
from research.uci412.synthetic import write_synthetic_workbook

from tests.uci412.conftest import make_dataset, small_config


@pytest.fixture(scope="module")
def smoke_run():
    config = small_config()
    dataset = make_dataset(config)
    nested = run_nested_cv(dataset, config=config)
    negative = run_label_shuffle_negative_control(dataset, config=config)
    leakage = assert_no_target_leakage(dataset, config=config)
    return config, dataset, nested, negative, leakage


@pytest.fixture(scope="module")
def synthetic_source(tmp_path_factory) -> Path:
    directory = tmp_path_factory.mktemp("uci412-source")
    return write_synthetic_workbook(directory / "Z-Alizadeh sani dataset.xlsx")


def _context(source: Path, *, repo_root: Path = REPOSITORY_ROOT) -> PreflightContext:
    content = source.read_bytes()
    digest = reporting._sha256(content)
    return PreflightContext(
        repo_root=repo_root,
        source_path=source,
        source_sha256=digest,
        source_size_bytes=len(content),
        provenance_sha256="1" * 64,
        d046_authorization_sha256="2" * 64,
        m3a_authorization_sha256="3" * 64,
        license_sha256="4" * 64,
        authorization={"local_signer": "SYNTHETIC_TEST_SIGNER_NOT_A_HUMAN"},
        current_git_commit="a" * 40,
        commit_committed_at_utc="2026-10-20T10:00:00+00:00",
        downloaded_at_utc="UNKNOWN_PENDING_HUMAN_VERIFICATION",
        download_timestamp_evidence_status="UNVERIFIED",
        provenance_recorded_at_utc="2026-10-20T11:00:00Z",
    )


def _report(smoke_run, source: Path) -> dict:
    config, dataset, nested, negative, leakage = smoke_run
    return build_run_report(
        preflight=_context(source),
        source_snapshot=reporting.SourceSnapshot(
            content=source.read_bytes(),
            sha256=reporting._sha256(source.read_bytes()),
            size_bytes=source.stat().st_size,
        ),
        dataset=dataset,
        nested=nested,
        negative_control=negative,
        leakage_checks=leakage,
        predictions_sha256="5" * 64,
        run_id="run-20261024T101010Z-abcdef12",
        config=config,
    )


def test_report_is_aggregate_only_and_fully_labelled(smoke_run, synthetic_source) -> None:
    report = _report(smoke_run, synthetic_source)
    assert report["report_banner"] == "INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED"
    assert report["report_type"] == REPORT_TYPE
    metadata = report["experiment_metadata"]
    assert metadata["experiment_id"] == DEFAULT_CONFIG.experiment_id
    assert metadata["dataset_id"] == "DA-A1"
    assert metadata["source_id"] == "UCI-412"
    assert metadata["feature_schema_version"] == DEFAULT_CONFIG.dictionary_schema_version
    assert metadata["protocol_status"] == "PROPOSED_NOT_FROZEN_NOT_SUPERVISOR_APPROVED"
    assert metadata["research_only_validation_status"] == report["report_banner"]
    assert metadata["paid_service_or_cloud_dependency"] is False
    assert report["preprocessing"]["global_preprocessing_before_cv"] is False
    assert report["claims"]["clinical_use"] is False
    assert report["model_artifact_saved"] is False
    assert report["independent_external_validation_performed"] is False


def test_report_contains_no_row_level_sequences(smoke_run, synthetic_source) -> None:
    report = _report(smoke_run, synthetic_source)
    row_count = report["cohort"]["row_count"]

    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                assert str(key).lower() not in FORBIDDEN_REPORT_KEYS
                walk(item)
        elif isinstance(value, (list, tuple)):
            assert len(value) != row_count, "A report list matches the source row count."
            for item in value:
                walk(item)

    walk(report)
    serialized = json.dumps(report)
    assert "predictions.csv" in serialized
    assert "source_row_index" not in serialized
    assert "oof_probability" not in serialized


def test_report_validation_rejects_missing_banner_and_assertions(smoke_run, synthetic_source) -> None:
    report = _report(smoke_run, synthetic_source)
    broken = dict(report)
    broken["report_banner"] = "APPROVED"
    with pytest.raises(StorageProtectionError):
        validate_aggregate_report(broken)
    broken = dict(report)
    broken["model_artifact_saved"] = True
    with pytest.raises(StorageProtectionError):
        validate_aggregate_report(broken)
    broken = dict(report)
    broken["predictions"] = {"rows": [0.1]}
    with pytest.raises(StorageProtectionError):
        validate_aggregate_report(broken)


def test_report_rejects_non_finite_values(smoke_run, synthetic_source) -> None:
    report = _report(smoke_run, synthetic_source)
    broken = dict(report)
    broken["extra"] = float("nan")
    with pytest.raises(StorageProtectionError):
        validate_aggregate_report(broken)


def test_predictions_export_is_row_aligned_and_complete(smoke_run) -> None:
    config, dataset, nested, _, _ = smoke_run
    payload = predictions_csv_bytes(dataset, nested, config=config)
    lines = payload.decode("utf-8").splitlines()
    expected = 1 + dataset.row_count * len(nested.repeat_results)
    assert len(lines) == expected
    header = lines[0].split(",")
    assert header[:4] == ["source_row_index", "true_label", "outer_repeat_seed", "outer_fold_number"]
    assert set(header[4:]) == {
        "prevalence_dummy_oof_probability",
        "l2_logistic_regression_oof_probability",
        "constrained_random_forest_oof_probability",
        "inner_selected_procedure_oof_probability",
    }
    first = lines[1].split(",")
    assert first[0] == "0"
    assert first[1] in {"0", "1"}
    assert 1 <= int(first[3]) <= config.outer_folds


def test_write_run_outputs_creates_private_files_and_refuses_overwrite(
    smoke_run, synthetic_source, tmp_path
) -> None:
    config, dataset, nested, negative, leakage = smoke_run
    output_dir = tmp_path / "run"
    output_dir.mkdir()
    context = _context(synthetic_source)
    first = write_run_outputs(
        output_dir=output_dir,
        preflight=context,
        source_snapshot=reporting.SourceSnapshot(
            content=synthetic_source.read_bytes(),
            sha256=reporting._sha256(synthetic_source.read_bytes()),
            size_bytes=synthetic_source.stat().st_size,
        ),
        dataset=dataset,
        nested=nested,
        negative_control=negative,
        leakage_checks=leakage,
        run_id="run-20261024T101010Z-abcdef12",
        config=config,
    )
    report_path = output_dir / REPORT_FILENAME
    assert report_path.is_file()
    assert first["report_sha256"] == reporting._sha256(report_path.read_bytes())
    persisted = json.loads(report_path.read_text(encoding="utf-8"))
    assert persisted["report_banner"] == config.report_banner
    if os.name == "posix":
        assert stat.S_IMODE(report_path.stat().st_mode) == 0o600

    with pytest.raises(StorageProtectionError):
        write_run_outputs(
            output_dir=output_dir,
            preflight=context,
            source_snapshot=reporting.SourceSnapshot(
                content=synthetic_source.read_bytes(),
                sha256=reporting._sha256(synthetic_source.read_bytes()),
                size_bytes=synthetic_source.stat().st_size,
            ),
            dataset=dataset,
            nested=nested,
            negative_control=negative,
            leakage_checks=leakage,
            run_id="run-20261024T101010Z-abcdef12",
            config=config,
        )


def test_write_run_outputs_rejects_a_changed_source(
    smoke_run, synthetic_source, tmp_path
) -> None:
    config, dataset, nested, negative, leakage = smoke_run
    from dataclasses import replace

    context = replace(
        _context(synthetic_source),
        source_path=tmp_path / "Z-Alizadeh sani dataset.xlsx",
    )
    context.source_path.write_bytes(synthetic_source.read_bytes() + b"changed")
    with pytest.raises(ProvenanceError):
        write_run_outputs(
            output_dir=tmp_path,
            preflight=context,
            source_snapshot=reporting.SourceSnapshot(
                content=b"x", sha256="0" * 64, size_bytes=1
            ),
            dataset=dataset,
            nested=nested,
            negative_control=negative,
            leakage_checks=leakage,
            run_id="run-20261024T101010Z-abcdef12",
            config=config,
        )


def test_package_fingerprints_cover_every_research_file() -> None:
    digest, per_file = package_fingerprints(REPOSITORY_ROOT)
    assert len(digest) == 64
    assert "research/uci412/adapter.py" in per_file
    assert "research/uci412/schemas/uci412_feature_dictionary.v1.json" in per_file
    assert (
        "docs/research/gate-pt/08_m3a_uci412_source_specific_benchmark_SPECIFICATION.md"
        in per_file
    )
    assert all(len(value) == 64 for value in per_file.values())


def test_package_fingerprints_fail_on_a_missing_file(tmp_path) -> None:
    with pytest.raises(StorageProtectionError):
        package_fingerprints(tmp_path)


def test_software_versions_are_recorded() -> None:
    versions = reporting.software_versions()
    assert {"python", "numpy", "scipy", "scikit_learn"}.issubset(versions)


def test_protected_run_directory_is_unique_and_git_ignored(tmp_path) -> None:
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".gitignore").write_text("/data/\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Synthetic Test"], cwd=repo, check=True)
    subprocess.run(["git", "add", ".gitignore"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)

    run_directory = create_protected_run_directory(
        repo_root=repo, run_id="run-20261024T101010Z-abcdef12"
    )
    assert run_directory.is_dir()
    assert run_directory.parent.parent.name == "data"
    if os.name == "posix":
        assert stat.S_IMODE(run_directory.stat().st_mode) & 0o077 == 0
    with pytest.raises(StorageProtectionError):
        create_protected_run_directory(repo_root=repo, run_id="run-20261024T101010Z-abcdef12")
    for bad in ("../escape", "run-1", "run-20261024T101010Z-ABCDEF12", "run-20261024T101010Z-abcdef123"):
        with pytest.raises(StorageProtectionError):
            create_protected_run_directory(repo_root=repo, run_id=bad)


def test_samples_rows_are_never_serialized_to_the_report(smoke_run, synthetic_source) -> None:
    config, dataset, nested, negative, leakage = smoke_run
    report = _report(smoke_run, synthetic_source)
    probe = f"{float(dataset.X[0, 0]):.10f}"
    assert probe not in json.dumps(report)
    assert np.isfinite(dataset.X[0, 0])
