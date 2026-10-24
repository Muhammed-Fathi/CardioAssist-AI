"""Orchestration for the synthetic dry-run and the guarded local UCI-412 run."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import uuid
from typing import Any

from research.uci412.adapter import (
    load_authorized_dataset,
    parse_workbook,
    sheet_from_rows,
    validate_workbook_structure,
)
from research.uci412.config import (
    DEFAULT_CONFIG,
    OUTPUT_ROOT_RELATIVE_PATH,
    REPOSITORY_ROOT,
    SMOKE_TEST_PROFILE,
    Uci412Config,
)
from research.uci412.errors import RuntimeGuardError
from research.uci412.evaluation import (
    assert_no_target_leakage,
    run_label_shuffle_negative_control,
    run_nested_cv,
    synthetic_smoke_result,
)
from research.uci412.reporting import write_run_outputs
from research.uci412.safety import (
    PreflightContext,
    create_protected_run_directory,
    load_failed_run_notes,
    run_preflight,
    verify_source_still_unchanged,
)
from research.uci412.synthetic import SYNTHETIC_SCOPE, synthetic_workbook_rows


def run_synthetic_dry_run(
    *, config: Uci412Config = SMOKE_TEST_PROFILE
) -> dict[str, Any]:
    """Exercise parsing, nested model selection, metrics, and controls on generated rows only.

    The default smoke profile keeps the registered panel, seeds scheme,
    preprocessing contract and metric set but runs a reduced fit budget so the
    dry-run is usable in CI. It is never a research result and is never the
    registered real-run configuration.
    """
    headers, rows = synthetic_workbook_rows(config=config)
    workbook = sheet_from_rows(
        headers,
        rows,
        other_sheets=(),
    )
    parsed = validate_workbook_structure(workbook, config=config)
    dataset = parse_workbook(parsed, config=config)
    leakage = assert_no_target_leakage(dataset, config=config)
    result = synthetic_smoke_result(dataset, config=config)
    result["synthetic_scope"] = SYNTHETIC_SCOPE
    result["leakage_checks"] = leakage
    result["report_or_prediction_files_written"] = False
    result["fit_profile"] = {
        "profile": "SMOKE_REDUCED_FIT_BUDGET_NOT_THE_REGISTERED_RUN",
        "outer_folds": config.outer_folds,
        "inner_folds": config.inner_folds,
        "outer_repeat_seeds": list(config.outer_repeat_seeds),
        "random_forest_trees": config.rf_n_estimators,
        "negative_control_seeds": list(config.negative_control_seeds),
        "registered_profile_cv": {
            "outer_folds": DEFAULT_CONFIG.outer_folds,
            "inner_folds": DEFAULT_CONFIG.inner_folds,
            "outer_repeat_seeds": list(DEFAULT_CONFIG.outer_repeat_seeds),
            "random_forest_trees": DEFAULT_CONFIG.rf_n_estimators,
            "negative_control_seeds": list(DEFAULT_CONFIG.negative_control_seeds),
        },
        "real_run_requires_default_config": True,
    }
    return result


def _new_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"run-{timestamp}-{uuid.uuid4().hex[:8]}"


def run_authorized_local_experiment(
    *,
    repo_root: Path = REPOSITORY_ROOT,
    config: Uci412Config = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Run the registered UCI-412 benchmark after every local gate has passed.

    This function is unusable on Linux, CI, hosted notebooks, or remote drives.
    The real workbook is parsed only after preflight has validated the D-046
    read-only chain, the separate M3a authorization, the frozen hashes, the
    Windows-local runtime, ignored storage, and the protected output directory.
    """
    if config != DEFAULT_CONFIG:
        raise RuntimeGuardError(
            "Real-data fitting requires the exact frozen registered UCI-412 configuration."
        )
    preflight: PreflightContext = run_preflight(repo_root=repo_root, config=config)

    source_snapshot, dataset = load_authorized_dataset(
        preflight.source_path,
        expected_sha256=preflight.source_sha256,
        expected_size_bytes=preflight.source_size_bytes,
        config=config,
    )
    verify_source_still_unchanged(preflight)
    leakage_checks = assert_no_target_leakage(dataset, config=config)

    nested = run_nested_cv(dataset, config=config)
    negative_control = run_label_shuffle_negative_control(dataset, config=config)
    if negative_control.summary["leakage_assessment"]["blocking"]:
        raise RuntimeGuardError(
            "The label-permutation control indicates likely target leakage; results were discarded "
            "and no report or output directory was created."
        )
    verify_source_still_unchanged(preflight)

    # The protected run directory is created only after every scientific gate and
    # the leakage control have passed, so a discarded run leaves no output behind.
    failed_runs = load_failed_run_notes(preflight.repo_root)
    run_id = _new_run_id()
    output_dir = create_protected_run_directory(repo_root=preflight.repo_root, run_id=run_id)

    outputs = write_run_outputs(
        output_dir=output_dir,
        preflight=preflight,
        source_snapshot=source_snapshot,
        dataset=dataset,
        nested=nested,
        negative_control=negative_control,
        leakage_checks=leakage_checks,
        run_id=run_id,
        failed_runs=failed_runs,
        config=config,
    )
    return {
        "status": config.report_banner,
        "report_banner": config.report_banner,
        "experiment_id": config.experiment_id,
        "run_id": run_id,
        "output_relative_directory": f"{OUTPUT_ROOT_RELATIVE_PATH}/{run_id}",
        "report_filename": outputs["report_filename"],
        "predictions_filename": outputs["predictions_filename"],
        "report_sha256": outputs["report_sha256"],
        "predictions_sha256": outputs["predictions_sha256"],
        "row_count": dataset.row_count,
        "final_full_cohort_model_artifact_saved": False,
        "clinical_or_external_validation_claim": False,
        "supervisor_approval_claimed": False,
        "failed_run_notes_carried_forward": len(failed_runs),
    }
