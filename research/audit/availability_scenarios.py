"""DA-A2 protocol-planning **descriptive** joint availability audit.

No model fit, feature selection, outcome evaluation, source modification,
imputation, exclusion, patient-level output or clinical recommendation.
The fixed measurement-stage groupings are engineering *scenarios*, NOT a
selected model feature set. Exact source files remain byte-guarded.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from research.audit.cli import REPO_ROOT
from research.audit.git_safety import verify_data_root_containment, verify_git_ignore
from research.audit.provenance import (
    ByteIdentityGuard,
    load_authorization_manifest,
    validate_provenance_manifest,
    verify_dataset_authorized_for_audit,
    verify_global_workflow_authorized,
)
from research.audit.registry import UCI_45_CONVENTIONAL_14_COLUMNS
from research.audit.validators import audit_uci_45_processed_file

# Fixed *measurement availability* snapshots independent of disease outcomes.
# They are NOT a model's chosen predictors. Do not optimize these using labels.
MEASUREMENT_STAGE_PANELS: Mapping[str, tuple[str, ...]] = {
    "history_only": ("age", "sex", "cp"),
    "resting_assessment": ("age", "sex", "cp", "trestbps", "restecg"),
    "resting_plus_labs": ("age", "sex", "cp", "trestbps", "chol", "fbs", "restecg"),
    "includes_exercise_tests": (
        "age", "sex", "cp", "trestbps", "chol", "fbs", "restecg",
        "thalach", "exang", "oldpeak", "slope",
    ),
}

# These are explicitly source-flagged implausible zeros, NOT a blanket
# conversion of legitimate binary/categorical/oldpeak zeros.
ZERO_UNAVAILABLE_SENSITIVITY_FIELDS = frozenset({"chol", "trestbps"})
PROCESSED_FILES: tuple[tuple[str, str], ...] = (
    ("cleveland", "processed.cleveland.data"),
    ("hungarian", "processed.hungarian.data"),
    ("switzerland", "processed.switzerland.data"),
    ("va", "processed.va.data"),
)


def descriptive_panel_counts(
    rows: Sequence[dict[str, Any]],
    panel: Sequence[str],
) -> dict[str, int]:
    """Count joint observed values under two *unapplied* source-coding scenarios."""
    columns = tuple(panel)
    allowed = set(UCI_45_CONVENTIONAL_14_COLUMNS[:13]) - {"ca", "thal"}
    if not columns or len(set(columns)) != len(columns) or not set(columns) <= allowed:
        raise ValueError("Only unique, non-target, non-angiographic conventional fields may be counted.")
    literal = 0
    conditional = 0
    for row in rows:
        has_recorded = all(row.get(column) is not None for column in columns)
        zero_possible_missing = any(
            column in ZERO_UNAVAILABLE_SENSITIVITY_FIELDS
            and row.get(column) == 0
            and row.get(column) is not None
            for column in columns
        )
        literal += int(has_recorded)
        conditional += int(has_recorded and not zero_possible_missing)

    if not 0 <= conditional <= literal <= len(rows):
        raise RuntimeError("STOP: Availability count invariants violated.")

    return {
        "records_screened": len(rows),
        "literal_source_coding_jointly_present": literal,
        "hypothetical_zero_unavailable_jointly_present": conditional,
        "lost_if_zero_unavailable": literal - conditional,
    }


def run_availability_audit(
    *,
    repo_root: Path = REPO_ROOT,
    base_data_parent: Path | None = None,
    auth_manifest_path: Path | None = None,
    provenance_manifest_path: Path | None = None,
    allow_external_tmp_root: Path | None = None,  # synthetic tests only
) -> dict[str, Any]:
    """Strictly authorized DA-A2 source audit, processed cohorts ONLY; results are counts."""
    root = repo_root.resolve()
    parent = (base_data_parent or root).resolve()
    auth_path = auth_manifest_path or (parent / "data/manifests/gate_da_authorization.local.json")
    prov_path = provenance_manifest_path or (parent / "data/manifests/provenance_manifest.json")
    verify_git_ignore(root)
    verify_data_root_containment(root, parent / "data", allow_external_tmp_root=allow_external_tmp_root)
    verify_data_root_containment(root, prov_path, allow_external_tmp_root=allow_external_tmp_root)
    auth = load_authorization_manifest(auth_path)
    verify_global_workflow_authorized(auth)
    verify_dataset_authorized_for_audit(auth, "DA-A2")
    if auth.get("model_fitting_authorized") is not False or auth.get("gate_pt_status") != (
        "CLOSED_REQUIRES_SUPERVISOR_SIGNOFF_P3"
    ):
        raise RuntimeError("STOP: Clinical protocol/training gate status not as required.")

    verified = validate_provenance_manifest(prov_path, parent, auth, ("DA-A2",))
    files = verified["DA-A2"]
    guard_entries: list[tuple[str, Path, str, int]] = []
    for filename, meta in sorted(files.items()):
        guard_entries.append((
            str(meta["relative_path"]),
            Path(meta["resolved_path"]),
            str(meta["verified_sha256"]),
            int(meta["verified_size_bytes"]),
        ))

    summary: dict[str, dict[str, Any]] = {}
    with ByteIdentityGuard(guard_entries):
        for cohort, processed_filename in PROCESSED_FILES:
            source_path = Path(files[processed_filename]["resolved_path"])
            parsed = audit_uci_45_processed_file(source_path)
            rows = parsed["normalized_rows"]
            expected_n = parsed["report"]["row_count"]
            if not rows or len(rows) != expected_n:
                raise RuntimeError("STOP: Processed cohort row count mismatch.")
            summary[cohort] = {
                "source_row_count": expected_n,
                "stage_availability": {
                    stage: descriptive_panel_counts(rows, columns)
                    for stage, columns in MEASUREMENT_STAGE_PANELS.items()
                },
            }
            # No patient rows escape the current scope; output contains ints and fixed labels only.

    return {
        "status": "READ_ONLY_DESCRIPTIVE_ONLY_NOT_TRAINING_AUTHORIZATION",
        "dataset_id": "DA-A2",
        "raw_cleveland_parsed": False,
        "modeled_or_transformed_data": False,
        "panels_are_not_selected_features": True,
        "source_files_byte_guarded": True,
        "hypothetical_zero_rule_applied_to_sources": False,
        "zero_sensitivity_applies_only_to": sorted(ZERO_UNAVAILABLE_SENSITIVITY_FIELDS),
        "cohorts": summary,
        "gate_pt": "CLOSED",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CardioAssist DA-A2 read-only descriptive joint availability")
    parser.add_argument("--auth-manifest", required=True, type=Path)
    parser.add_argument("--provenance-manifest", required=True, type=Path)
    args = parser.parse_args(argv)
    # Do not allow writing a report file from this CLI; stdout has fixed metadata-only schema.
    results = run_availability_audit(
        auth_manifest_path=args.auth_manifest,
        provenance_manifest_path=args.provenance_manifest,
    )
    print(json.dumps(results, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
