"""Aggregate-only report construction and protected local artifact writing.

The report is the only research output intended for human review. It contains no
patient-level value: aggregates, configuration, provenance, hashes, metric
summaries and explicit limitations only. Row-aligned out-of-fold predictions are
written to the same protected local directory and must never be committed,
uploaded, pasted into an issue, or copied to a remote service.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import stat
import sys
from typing import Any, Mapping

import joblib
import numpy as np
import scipy
import sklearn
import threadpoolctl

from research.uci412.adapter import SourceSnapshot, Uci412Dataset
from research.uci412.config import (
    DEFAULT_CONFIG,
    PROPOSAL_RELATIVE_PATH,
    Uci412Config,
)
from research.uci412.errors import StorageProtectionError
from research.uci412.evaluation import (
    MODEL_NAMES,
    NegativeControlResult,
    NestedCVResult,
    nested_result_to_report,
    plan_outer_folds,
)
from research.uci412.feature_schema import DEFAULT_DICTIONARY, FeatureDictionary
from research.uci412.models import preprocessing_contract
from research.uci412.safety import PreflightContext, verify_source_still_unchanged
from research.uci412.sample_size import planning_summary

REPORT_FILENAME = "report.json"
PREDICTIONS_FILENAME = "predictions.csv"
REPORT_TYPE = "INTERNAL_EXPLORATORY_AGGREGATE_REPORT"
FORBIDDEN_REPORT_KEYS = frozenset(
    {
        "patient_rows",
        "patient_records",
        "raw_rows",
        "raw_records",
        "row_values",
        "prediction_values",
        "prediction_scores",
        "predictions",
        "row_scores",
        "score_values",
        "out_of_fold_predictions",
        "per_patient_predictions",
        "identifiers",
        "patient_ids",
        "source_rows",
    }
)

PACKAGE_FILES: tuple[str, ...] = (
    "research/uci412/__init__.py",
    "research/uci412/__main__.py",
    "research/uci412/adapter.py",
    "research/uci412/cli.py",
    "research/uci412/config.py",
    "research/uci412/errors.py",
    "research/uci412/evaluation.py",
    "research/uci412/feature_schema.py",
    "research/uci412/models.py",
    "research/uci412/reporting.py",
    "research/uci412/runner.py",
    "research/uci412/safety.py",
    "research/uci412/sample_size.py",
    "research/uci412/source_spec.py",
    "research/uci412/synthetic.py",
    "research/uci412/requirements.txt",
    "research/uci412/schemas/uci412_feature_dictionary.v1.json",
    "research/uci412/uci412_cad_research_plan.v0.1.json",
    "research/uci412/internal_research_authorization.template.json",
    "research/audit/git_safety.py",
    "research/audit/provenance.py",
    "research/audit/registry.py",
    "research/audit/xlsx_reader.py",
    PROPOSAL_RELATIVE_PATH.as_posix(),
)


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def package_fingerprints(repo_root: Path) -> tuple[str, dict[str, str]]:
    """Hash every code/protocol file that can influence the experiment."""
    hasher = hashlib.sha256()
    per_file: dict[str, str] = {}
    for relative in sorted(set(PACKAGE_FILES)):
        path = repo_root / relative
        if path.is_symlink() or not path.is_file():
            raise StorageProtectionError("A required research file is missing or unsafe for hashing.")
        content = path.read_bytes()
        per_file[relative] = _sha256(content)
        hasher.update(relative.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(content)
        hasher.update(b"\0")
    return hasher.hexdigest(), per_file


def software_versions() -> dict[str, str]:
    return {
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "scikit_learn": sklearn.__version__,
        "joblib": joblib.__version__,
        "threadpoolctl": threadpoolctl.__version__,
        "platform": platform.platform(),
    }


def validate_aggregate_report(report: Mapping[str, Any], *, config: Uci412Config = DEFAULT_CONFIG) -> None:
    if report.get("report_banner") != config.report_banner:
        raise StorageProtectionError("The research report is missing the mandatory status banner.")
    if report.get("report_type") != REPORT_TYPE:
        raise StorageProtectionError("Unexpected report type for the UCI-412 internal run.")
    for key in (
        "formal_supervisor_approval",
        "independent_external_validation_performed",
        "clinical_or_patient_care_use_authorized",
        "model_artifact_saved",
    ):
        if report.get(key) is not False:
            raise StorageProtectionError(f"The report may not assert '{key}'.")

    def walk(value: Any) -> None:
        if isinstance(value, Mapping):
            for key, item in value.items():
                if str(key).lower() in FORBIDDEN_REPORT_KEYS:
                    raise StorageProtectionError(
                        "The aggregate report schema rejects patient-level or row-aligned content."
                    )
                walk(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(item)

    walk(report)
    try:
        json.dumps(report, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise StorageProtectionError("The aggregate report contains non-JSON or non-finite values.") from exc


def build_run_report(
    *,
    preflight: PreflightContext,
    source_snapshot: SourceSnapshot,
    dataset: Uci412Dataset,
    nested: NestedCVResult,
    negative_control: NegativeControlResult,
    leakage_checks: Mapping[str, Any],
    predictions_sha256: str,
    run_id: str,
    failed_runs: tuple[str, ...] = (),
    config: Uci412Config = DEFAULT_CONFIG,
    dictionary: FeatureDictionary = DEFAULT_DICTIONARY,
) -> dict[str, Any]:
    """Assemble the aggregate-only report for one authorized local run."""
    package_sha, package_files = package_fingerprints(preflight.repo_root)
    plan_sha = package_files.get(
        "research/uci412/uci412_cad_research_plan.v0.1.json", ""
    )
    dictionary_sha = package_files.get(
        "research/uci412/schemas/uci412_feature_dictionary.v1.json", ""
    )
    proposal_sha = package_files.get(PROPOSAL_RELATIVE_PATH.as_posix(), "")

    report: dict[str, Any] = {
        "report_type": REPORT_TYPE,
        "report_banner": config.report_banner,
        "research_only_validation_status": config.report_banner,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "run_id": run_id,
        "experiment": config.as_report_dict(),
        "feature_dictionary": dictionary.as_review_dict(),
        "provenance": {
            "dataset_id": config.dataset_id,
            "source_id": config.source_id,
            "source_relative_path": config.source_relative_path,
            "source_sha256": preflight.source_sha256,
            "source_size_bytes": preflight.source_size_bytes,
            "snapshot_sha256": source_snapshot.sha256,
            "snapshot_size_bytes": source_snapshot.size_bytes,
            "protected_provenance_manifest_sha256": preflight.provenance_sha256,
            "d046_read_only_authorization_sha256": preflight.d046_authorization_sha256,
            "m3a_internal_research_authorization_sha256": preflight.m3a_authorization_sha256,
            "license_snapshot_sha256": preflight.license_sha256,
            "downloaded_at_utc": preflight.downloaded_at_utc,
            "download_timestamp_evidence_status": preflight.download_timestamp_evidence_status,
            "provenance_recorded_at_utc": preflight.provenance_recorded_at_utc,
            "source_origin_verification": "HUMAN_ATTESTED_NOT_INDEPENDENTLY_PROVEN",
        },
        "reproducibility": {
            "git_commit_sha": preflight.current_git_commit,
            "git_commit_committed_at_utc": preflight.commit_committed_at_utc,
            "package_versions": software_versions(),
            "package_fingerprint_sha256": package_sha,
            "package_file_sha256": package_files,
            "frozen_research_plan_sha256": plan_sha,
            "frozen_feature_dictionary_sha256": dictionary_sha,
            "frozen_authorization_proposal_sha256": proposal_sha,
            "m3a_authorization": dict(preflight.authorization),
        },
        "cohort": {
            "row_count": dataset.row_count,
            "class_counts_by_binary_label": {str(k): v for k, v in dataset.class_counts},
            "target_definition": "Source Cath label: 'Cad' (diameter narrowing >=50%) vs 'Normal'.",
            "single_source_cohort": True,
            "independent_cohort_claim": False,
            "uci_411_rows_used": 0,
            "other_cohorts_pooled": 0,
            "aggregate_source_audit": dict(dataset.audit),
        },
        "experiment_metadata": {
            "experiment_id": config.experiment_id,
            "dataset_id": config.dataset_id,
            "source_id": config.source_id,
            "source_relative_path": config.source_relative_path,
            "source_sha256": preflight.source_sha256,
            "source_size_bytes": preflight.source_size_bytes,
            "git_commit_sha": preflight.current_git_commit,
            "protocol_id": config.experiment_id,
            "protocol_status": config.protocol_status,
            "feature_schema_id": config.dictionary_schema_id,
            "feature_schema_version": config.dictionary_schema_version,
            "panel_id": config.panel_id,
            "panel_version": config.panel_version,
            "research_only_validation_status": config.report_banner,
            "local_cpu_only": True,
            "paid_service_or_cloud_dependency": False,
            "failed_run_count": len(failed_runs),
            "failed_runs": list(failed_runs),
        },
        "preprocessing": dict(preprocessing_contract(config)),
        "evaluation": nested_result_to_report(nested),
        "negative_control": {
            "shuffle_seeds": list(negative_control.shuffle_seeds),
            "summary": dict(negative_control.summary),
            "per_shuffle": [dict(record) for record in negative_control.per_shuffle],
            "interpretation": negative_control.interpretation,
        },
        "leakage_checks": dict(leakage_checks),
        "sample_size_planning": planning_summary(
            n=dataset.row_count, events=dataset.n_positive, config=config
        ),
        "failed_runs": list(failed_runs),
        "technical_limitations": [
            "This is a single-source internal exploratory benchmark, not external validation.",
            "Repeats reuse the same 303 participants; no pooled multi-repeat inference is valid.",
            "Participant independence cannot be proven from identifier-free data.",
            "Unit and measurement-time semantics for several source fields remain unverified.",
            "The out-of-fold bootstrap is conditional on the fitted fold models and excludes refitting variability.",
            "No model artifact is produced and nothing is approved for serving or clinical use.",
        ],
        "claims": {
            "clinical_use": False,
            "patient_facing_risk_percentage": False,
            "supervisor_approval": False,
            "publication_or_novelty": False,
            "external_validation": False,
            "patient_independence_proven": False,
            "future_event_risk_horizon": False,
        },
        "formal_supervisor_approval": False,
        "independent_external_validation_performed": False,
        "clinical_or_patient_care_use_authorized": False,
        "model_artifact_saved": False,
        "aggregate_report_contains_patient_level_values": False,
        "protected_directory_contains_row_aligned_predictions": True,
        "predictions_filename": PREDICTIONS_FILENAME,
        "predictions_sha256": predictions_sha256,
        "predictions_handling": (
            "Row-aligned out-of-fold probabilities are written only to this protected local "
            "directory. They are patient-level derivatives: never commit, upload, paste, or share them."
        ),
    }
    validate_aggregate_report(report, config=config)
    return report


def predictions_csv_bytes(
    dataset: Uci412Dataset,
    nested: NestedCVResult,
    *,
    config: Uci412Config = DEFAULT_CONFIG,
) -> bytes:
    """Serialize row-aligned out-of-fold predictions for local review only.

    One row per participant per outer repeat, with the repeat seed and the
    outer fold that produced the prediction, so the file can be audited
    against the registered fold plan without recomputation.
    """
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "source_row_index",
            "true_label",
            "outer_repeat_seed",
            "outer_fold_number",
            *(f"{model_name}_oof_probability" for model_name in MODEL_NAMES),
        ]
    )
    for repeat in nested.repeat_results:
        fold_of_row = np.full(dataset.row_count, -1, dtype=np.int64)
        for fold_number, (_, test_index) in enumerate(
            plan_outer_folds(dataset.y, repeat.outer_repeat_seed, config), start=1
        ):
            fold_of_row[test_index] = fold_number
        if np.any(fold_of_row < 0):
            raise StorageProtectionError("Prediction export found an unassigned source row.")
        for row_index in range(dataset.row_count):
            writer.writerow(
                [
                    row_index,
                    int(dataset.y[row_index]),
                    repeat.outer_repeat_seed,
                    int(fold_of_row[row_index]),
                    *(f"{repeat.predictions[name][row_index]:.10f}" for name in MODEL_NAMES),
                ]
            )
    return buffer.getvalue().encode("utf-8")


def _write_exclusive_private_file(path: Path, content: bytes) -> str:
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise StorageProtectionError(
            "A protected output file already exists; this harness never overwrites results."
        ) from exc
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass
    except Exception:
        try:
            path.unlink(missing_ok=True)
        finally:
            raise
    return _sha256(content)


def write_run_outputs(
    *,
    output_dir: Path,
    preflight: PreflightContext,
    source_snapshot: SourceSnapshot,
    dataset: Uci412Dataset,
    nested: NestedCVResult,
    negative_control: NegativeControlResult,
    leakage_checks: Mapping[str, Any],
    run_id: str,
    failed_runs: tuple[str, ...] = (),
    config: Uci412Config = DEFAULT_CONFIG,
    dictionary: FeatureDictionary = DEFAULT_DICTIONARY,
) -> dict[str, Any]:
    """Write the aggregate report and protected predictions into the run directory."""
    # Refuse to write anything if the original source is no longer byte-identical.
    verify_source_still_unchanged(preflight)
    predictions_bytes = predictions_csv_bytes(dataset, nested, config=config)
    predictions_sha = _write_exclusive_private_file(
        output_dir / PREDICTIONS_FILENAME, predictions_bytes
    )
    try:
        report = build_run_report(
            preflight=preflight,
            source_snapshot=source_snapshot,
            dataset=dataset,
            nested=nested,
            negative_control=negative_control,
            leakage_checks=leakage_checks,
            predictions_sha256=predictions_sha,
            run_id=run_id,
            failed_runs=failed_runs,
            config=config,
            dictionary=dictionary,
        )
    except Exception:
        (output_dir / PREDICTIONS_FILENAME).unlink(missing_ok=True)
        raise
    verify_source_still_unchanged(preflight)
    report_bytes = (json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    report_sha = _write_exclusive_private_file(output_dir / REPORT_FILENAME, report_bytes)
    return {
        "report_filename": REPORT_FILENAME,
        "predictions_filename": PREDICTIONS_FILENAME,
        "report_sha256": report_sha,
        "predictions_sha256": predictions_sha,
    }
