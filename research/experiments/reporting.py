"""Aggregate-only report construction and protected local artifact writing."""
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

from research.experiments.config import (
    DEFAULT_CONFIG,
    PROTOCOL_RELATIVE_PATH,
    ExperimentConfig,
)
from research.experiments.data_adapter import ClevelandDataset, SourceBytes
from research.experiments.errors import StorageProtectionError
from research.experiments.evaluation import (
    MODEL_NAMES,
    NestedCVResult,
    NegativeControlResult,
    nested_result_to_report,
)
from research.experiments.safety import PreflightContext, verify_source_still_unchanged

REPORT_FILENAME = "report.json"
PREDICTIONS_FILENAME = "predictions.csv"
FORBIDDEN_REPORT_KEYS = frozenset({
    "patient_rows",
    "patient_records",
    "raw_rows",
    "raw_records",
    "row_values",
    "prediction_values",
    "prediction_scores",
    "per_patient_predictions",
    "identifiers",
    "patient_ids",
})


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _git(repo_root: Path, *args: str) -> str:
    import subprocess

    try:
        process = subprocess.run(
            ["git", *args],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise StorageProtectionError("Could not collect local Git reproducibility metadata.") from exc
    if process.returncode != 0:
        raise StorageProtectionError("Could not collect local Git reproducibility metadata.")
    return process.stdout.strip()


def _package_fingerprints(repo_root: Path) -> tuple[str, dict[str, str]]:
    relative_files = [
        *(Path("research/experiments") / name for name in (
            "__init__.py",
            "__main__.py",
            "cli.py",
            "config.py",
            "data_adapter.py",
            "errors.py",
            "evaluation.py",
            "models.py",
            "reporting.py",
            "runner.py",
            "safety.py",
            "synthetic_fixtures.py",
            "requirements.txt",
            "cleveland_d047_exploratory_plan.v0.1.json",
            "internal_exploratory_authorization.template.json",
        )),
        Path("research/audit/git_safety.py"),
        Path("research/audit/provenance.py"),
        Path("research/audit/registry.py"),
        PROTOCOL_RELATIVE_PATH,
    ]
    hasher = hashlib.sha256()
    per_file: dict[str, str] = {}
    for relative in sorted(set(relative_files), key=lambda p: p.as_posix()):
        path = repo_root / relative
        if path.is_symlink() or not path.is_file():
            raise StorageProtectionError("A required runner/protocol file is missing or unsafe for hashing.")
        content = path.read_bytes()
        digest = _sha256(content)
        per_file[relative.as_posix()] = digest
        hasher.update(relative.as_posix().encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(content)
        hasher.update(b"\0")
    return hasher.hexdigest(), per_file


def _software_versions() -> dict[str, str]:
    return {
        "python": sys.version.split()[0],
        "scikit_learn": sklearn.__version__,
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "joblib": joblib.__version__,
        "threadpoolctl": threadpoolctl.__version__,
    }


def _validate_aggregate_report(report: Mapping[str, Any]) -> None:
    if report.get("report_banner") != DEFAULT_CONFIG.report_banner:
        raise StorageProtectionError("Real experiment report is missing the mandatory D-047 status banner.")
    if report.get("report_type") != "INTERNAL_EXPLORATORY_AGGREGATE_REPORT":
        raise StorageProtectionError("Unexpected report type for the D-047 internal run.")
    if report.get("formal_supervisor_approval") is not False:
        raise StorageProtectionError("A report may not claim formal supervisor approval.")
    if report.get("independent_external_validation_performed") is not False:
        raise StorageProtectionError("A single-source internal run may not claim external validation.")

    def walk(value: Any) -> None:
        if isinstance(value, Mapping):
            for key, item in value.items():
                if str(key).lower() in FORBIDDEN_REPORT_KEYS:
                    raise StorageProtectionError("Aggregate report schema rejects patient-level or row-aligned content.")
                walk(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(item)

    walk(report)
    try:
        json.dumps(report, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise StorageProtectionError("Aggregate report contains non-JSON or non-finite values.") from exc


def build_real_experiment_report(
    *,
    preflight: PreflightContext,
    source_snapshot: SourceBytes,
    dataset: ClevelandDataset,
    nested: NestedCVResult,
    negative_control: NegativeControlResult,
    predictions_sha256: str,
    predictions_size_bytes: int,
    run_id: str,
    config: ExperimentConfig = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Create a metadata/aggregate report. Per-row scores are deliberately excluded."""
    if source_snapshot.sha256.lower() != preflight.source_sha256.lower():
        raise StorageProtectionError("The parsed source snapshot differs from successful D-047 preflight.")
    runner_hash, file_hashes = _package_fingerprints(preflight.repo_root)
    protocol_path = preflight.repo_root / PROTOCOL_RELATIVE_PATH
    plan_path = preflight.repo_root / Path("research/experiments/cleveland_d047_exploratory_plan.v0.1.json")
    protocol_sha = _sha256(protocol_path.read_bytes())
    plan_sha = _sha256(plan_path.read_bytes())
    if protocol_sha != preflight.authorization["frozen_protocol_sha256"]:
        raise StorageProtectionError("Frozen protocol hash changed after D-047 preflight.")
    if plan_sha != preflight.authorization["frozen_experiment_plan_sha256"]:
        raise StorageProtectionError("Frozen registered plan hash changed after D-047 preflight.")
    if nested.row_count != dataset.row_count or nested.positive_count != dataset.n_positive:
        raise StorageProtectionError("Nested-CV aggregate counts do not match the guarded source snapshot.")

    report: dict[str, Any] = {
        "report_schema_version": "0.1.0",
        "report_type": "INTERNAL_EXPLORATORY_AGGREGATE_REPORT",
        "report_banner": config.report_banner,
        "experiment_id": config.experiment_id,
        "run_id": run_id,
        "status": "INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED",
        "purpose": "Internal exploratory software/research feasibility comparison only.",
        "formal_supervisor_approval": False,
        "gate_pt_p3_status": "CLOSED",
        "clinical_or_patient_care_use_authorized": False,
        "independent_external_validation_performed": False,
        "execution": {
            "completed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "runtime": "LOCAL_WINDOWS_CPU_ONLY",
            "operating_system": platform.system(),
            "operating_system_release": platform.release(),
            "architecture": platform.machine(),
            "data_rows_read_by_agent_or_remote_ci": False,
            "remote_data_upload_or_telemetry": False,
        },
        "authorization": {
            "decision_id": "D-047",
            "maintainer_authorization_comment_exact": "AUTHORIZE-D047-INTERNAL-CLEVELAND",
            "authorization_pr_number": preflight.authorization["authorization_pr_number"],
            "authorization_merged_commit_sha": preflight.authorization["authorization_merged_commit_sha"],
            "local_signer": preflight.authorization["local_signer"],
            "local_signed_at_iso8601": preflight.authorization["local_signed_at_iso8601"],
            "local_signature_semantics": preflight.authorization["signature_semantics"],
            "d047_authorization_manifest_sha256": preflight.d047_authorization_sha256,
            "d046_read_only_authorization_manifest_sha256": preflight.d046_authorization_sha256,
            "supervisor_signoff_claimed": False,
        },
        "source": {
            "dataset_id": "DA-A2",
            "source": "UCI-45",
            "filename": "processed.cleveland.data",
            "relative_path": "data/raw/uci-45/processed.cleveland.data",
            "official_source_url": "https://archive.ics.uci.edu/dataset/45/heart+disease",
            "doi": "10.24432/C52P4X",
            "license_spdx": "CC-BY-4.0",
            "license_snapshot_sha256": preflight.license_sha256,
            "row_count": dataset.row_count,
            "mapped_target_counts": {"0": dataset.n_negative, "1": dataset.n_positive},
            "positive_prevalence": dataset.n_positive / dataset.row_count,
            "source_sha256": source_snapshot.sha256,
            "source_size_bytes": source_snapshot.size_bytes,
            "local_integrity_status": "VERIFIED_SHA256_AND_BYTE_SIZE",
            "official_source_origin_status": (
                "HUMAN_ATTESTED_NOT_INDEPENDENTLY_PROVEN_BY_LOCAL_HASH"
            ),
            "provenance_manifest_sha256": preflight.provenance_sha256,
            "downloaded_at_utc": preflight.downloaded_at_utc,
            "download_timestamp_evidence_status": preflight.download_timestamp_evidence_status,
            "provenance_manifest_recorded_at_utc": preflight.provenance_recorded_at_utc,
            "byte_identical_original_verified_before_report": True,
        },
        "reproducibility": {
            "code_git_commit_sha": preflight.current_git_commit,
            "runner_source_tree_sha256": runner_hash,
            "code_file_sha256": file_hashes,
            "pinned_protocol_git_commit_sha": preflight.authorization["pinned_protocol_git_commit_sha"],
            "protocol_sha256": protocol_sha,
            "registered_plan_sha256": plan_sha,
            "software_versions": _software_versions(),
            "cpu_only_single_threaded_estimation": True,
        },
        "registered_configuration": config.as_report_dict(),
        "results": nested_result_to_report(nested),
        "negative_control": {
            "method": "label_shuffle_nested_cv_smoke_test",
            "per_shuffle_aggregate_metrics": list(negative_control.per_shuffle),
            "summary": dict(negative_control.summary),
            "interpretation": negative_control.interpretation,
            "formal_permutation_p_value": False,
        },
        "local_artifacts": {
            "predictions_file": PREDICTIONS_FILENAME,
            "predictions_sha256": predictions_sha256,
            "predictions_size_bytes": predictions_size_bytes,
            "contains_row_aligned_source_labels_and_oof_scores": True,
            "storage_requirement": "GIT_IGNORED_LOCAL_DATA_EXPERIMENTS_ONLY_NEVER_UPLOAD_OR_COMMIT",
            "final_full_cohort_model_artifact_saved": False,
        },
        "sample_size_sensitivity": {
            "status": "NOT_ASSESSED_NO_HUMAN_REVIEWED_ANTICIPATED_COX_SNELL_R2_ASSUMPTIONS",
            "events": dataset.n_positive,
            "candidate_logistic_slope_parameters_after_reference_encoding": 8,
            "riley_style_analysis_required_before_formal_supervisor_submission": True,
            "interpretation": "NO_GO_FOR_CLINICAL_PREDICTIVE_ADEQUACY; feasibility-only if assumptions remain unavailable",
        },
        "scientific_limitations": [
            "This is a retrospective single-source UCI-45 Cleveland benchmark, not a future or 30-day event-risk study.",
            "The endpoint is source-defined historical angiography-referenced current CAD presence (num=0 versus num=1..4); it is not severity modelling.",
            "Historical predictor timing is not certified as a prospective clinical decision timepoint.",
            "The same source people recur in each outer-CV repeat; repeat-level mean/SD are descriptive, not independent samples or confidence intervals.",
            "No independent external validation, cohort pooling, clinical utility, subgroup fairness, or patient-care claim is made.",
            "The fixed 0.50 cutoff is exploratory only and was not selected from outer-fold results.",
            "Calibration diagnostics are descriptive OOF diagnostics; no recalibration was performed and small-sample calibration may be unstable.",
            "The Riley-style sample-size sensitivity analysis and human-reviewed anticipated Cox-Snell R-squared assumptions are not supplied by this runner.",
            "TRIPOD+AI and PROBAST+AI assessments remain for human research review; this report does not imply supervisor or clinician endorsement.",
            "Locally verified SHA-256 establishes byte integrity, not independent proof that bytes originated from the official UCI host.",
        ],
        "claims_boundary": {
            "internal_exploratory_results_only": True,
            "independent_external_validation": False,
            "clinical_performance_or_readiness": False,
            "supervisor_approval_or_endorsement": False,
            "patient_specific_risk_percentages": False,
            "formal_confidence_intervals": False,
        },
    }
    _validate_aggregate_report(report)
    return report


def predictions_csv_bytes(
    nested: NestedCVResult,
    *,
    y_true: np.ndarray,
    report_banner: str = DEFAULT_CONFIG.report_banner,
) -> bytes:
    """Serialize row-aligned labels/scores only for the protected local artifact."""
    buffer = io.StringIO(newline="")
    buffer.write(f"# report_banner={report_banner}\n")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow([
        "outer_repeat_seed",
        "outer_repeat_number",
        "local_source_row_ordinal",
        "binary_source_target",
        "prevalence_dummy_probability",
        "l2_logistic_probability",
        "constrained_random_forest_probability",
        "inner_selected_procedure_probability",
    ])
    for repeat_number, repeat in enumerate(nested.repeat_results, start=1):
        arrays = [repeat.predictions[name] for name in MODEL_NAMES]
        if any(array.shape != y_true.shape for array in arrays):
            raise StorageProtectionError("Row-aligned prediction artifact shape mismatch.")
        for index in range(len(y_true)):
            writer.writerow([
                repeat.outer_repeat_seed,
                repeat_number,
                index + 1,
                int(y_true[index]),
                *(format(float(array[index]), ".17g") for array in arrays),
            ])
    return buffer.getvalue().encode("utf-8")


def _write_exclusive_private_file(path: Path, content: bytes) -> None:
    """Create an output file exclusively with owner-only POSIX mode where supported."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    try:
        file_descriptor = os.open(path, flags, 0o600)
        with os.fdopen(file_descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            # Windows inherits NTFS ACLs; the local operator must protect the
            # repository/data parent ACL as documented in the handoff.
            pass
    except FileExistsError as exc:
        raise StorageProtectionError("Refusing to overwrite an existing protected run artifact.") from exc
    except OSError as exc:
        raise StorageProtectionError("Unable to write a protected local experiment artifact.") from exc


def write_real_run_outputs(
    *,
    output_dir: Path,
    preflight: PreflightContext,
    source_snapshot: SourceBytes,
    dataset: ClevelandDataset,
    nested: NestedCVResult,
    negative_control: NegativeControlResult,
    run_id: str,
    config: ExperimentConfig = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Write private aggregate report and sensitive predictions under /data/experiments only."""
    expected_parent = preflight.repo_root.resolve() / "data" / "experiments"
    if output_dir.is_symlink() or output_dir.resolve(strict=True).parent != expected_parent.resolve(strict=True):
        raise StorageProtectionError("Experiment artifacts must be written directly under ignored data/experiments.")
    if not output_dir.name.startswith("run-"):
        raise StorageProtectionError("Protected output directory has an unexpected name.")
    verify_source_still_unchanged(preflight)
    prediction_content = predictions_csv_bytes(nested, y_true=dataset.y, report_banner=config.report_banner)
    report = build_real_experiment_report(
        preflight=preflight,
        source_snapshot=source_snapshot,
        dataset=dataset,
        nested=nested,
        negative_control=negative_control,
        predictions_sha256=_sha256(prediction_content),
        predictions_size_bytes=len(prediction_content),
        run_id=run_id,
        config=config,
    )
    report_content = (json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    verify_source_still_unchanged(preflight)
    _write_exclusive_private_file(output_dir / PREDICTIONS_FILENAME, prediction_content)
    verify_source_still_unchanged(preflight)
    _write_exclusive_private_file(output_dir / REPORT_FILENAME, report_content)
    verify_source_still_unchanged(preflight)
    return {
        "report": report,
        "report_sha256": _sha256(report_content),
        "predictions_sha256": _sha256(prediction_content),
        "report_filename": REPORT_FILENAME,
        "predictions_filename": PREDICTIONS_FILENAME,
    }
