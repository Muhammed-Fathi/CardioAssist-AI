"""Orchestration for synthetic dry-run and guarded real local D-047 runs."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import uuid
from typing import Any

from research.experiments.config import DEFAULT_CONFIG, REPOSITORY_ROOT, ExperimentConfig
from research.experiments.data_adapter import _parse_processed_cleveland_bytes, _read_source_bytes_read_only
from research.experiments.errors import RuntimeGuardError
from research.experiments.evaluation import (
    _run_label_shuffle_negative_control,
    _run_nested_cv,
    _synthetic_smoke_result,
)
from research.experiments.safety import (
    PreflightContext,
    create_protected_run_directory,
    run_preflight,
    verify_source_still_unchanged,
)
from research.experiments.reporting import write_real_run_outputs
from research.experiments.synthetic_fixtures import make_synthetic_dataset


def run_synthetic_dry_run(*, config: ExperimentConfig = DEFAULT_CONFIG) -> dict[str, Any]:
    """Exercise parsing, nested model selection, metrics, and label-shuffle logic on generated rows only."""
    dataset = make_synthetic_dataset(config=config)
    return _synthetic_smoke_result(dataset, config=config)


def _new_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"run-{timestamp}-{uuid.uuid4().hex[:8]}"


def run_authorized_local_experiment(
    *,
    repo_root: Path = REPOSITORY_ROOT,
    config: ExperimentConfig = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Run the D-047 protocol only after all local checks and operator confirmation.

    This function is intentionally unusable on Linux, CI, hosted notebooks, or
    remote drives. It parses the real source only after ``run_preflight`` has
    validated D-047, D-046 read-only provenance, source hashes, the Windows
    local runtime, and ignored storage, and after the protected output folder
    has been created. Real runs cannot substitute custom grids, folds, seeds,
    thresholds, feature sets, or other config values for the registered plan.
    """
    if config != DEFAULT_CONFIG:
        raise RuntimeGuardError("Real-data fitting requires the exact frozen registered D-047 configuration.")
    preflight: PreflightContext = run_preflight(repo_root=repo_root, config=config)
    run_id = _new_run_id()
    output_dir = create_protected_run_directory(repo_root=preflight.repo_root, run_id=run_id)

    source_snapshot = _read_source_bytes_read_only(
        preflight.source_path,
        expected_sha256=preflight.source_sha256,
        expected_size_bytes=preflight.source_size_bytes,
    )
    if source_snapshot.sha256.lower() != preflight.authorization["expected_source_sha256"]:
        raise RuntimeError("Guarded source snapshot differs from the D-047 authorization hash.")
    # The parser is reached only after the positive local gates above. It copies
    # only the five approved predictors and binary target into process memory.
    dataset = _parse_processed_cleveland_bytes(source_snapshot.content, config=config)
    verify_source_still_unchanged(preflight)

    nested = _run_nested_cv(dataset, config=config)
    negative_control = _run_label_shuffle_negative_control(dataset, config=config)
    verify_source_still_unchanged(preflight)
    outputs = write_real_run_outputs(
        output_dir=output_dir,
        preflight=preflight,
        source_snapshot=source_snapshot,
        dataset=dataset,
        nested=nested,
        negative_control=negative_control,
        run_id=run_id,
        config=config,
    )
    return {
        "status": "INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED",
        "report_banner": config.report_banner,
        "experiment_id": config.experiment_id,
        "run_id": run_id,
        "output_relative_directory": (Path("data/experiments") / run_id).as_posix(),
        "report_filename": outputs["report_filename"],
        "predictions_filename": outputs["predictions_filename"],
        "report_sha256": outputs["report_sha256"],
        "predictions_sha256": outputs["predictions_sha256"],
        "row_count": dataset.row_count,
        "final_full_cohort_model_artifact_saved": False,
        "clinical_or_external_validation_claim": False,
    }
