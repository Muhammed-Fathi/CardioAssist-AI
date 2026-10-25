"""Versioned RESEARCH_ONLY artifact bundle packaging and byte-level verification.

Security & scientific invariants:
1. Bundles cannot be written into tracked Git paths (must reside outside the
   repository root, e.g., ``tmp_path``, or inside a git-ignored directory such
   as ``data/``). Existing directories are never overwritten.
2. ``manifest.json`` binds exact SHA-256 digests and byte lengths for every
   sibling artifact (``model.joblib``, ``preprocessing.json``,
   ``calibration.json``, ``shap_background.json``, ``evaluation_summary.json``,
   ``protocol.md``) plus the panel contract SHA-256, ordered feature list, and
   target definition SHA-256.
3. ``verify_research_bundle`` performs pure byte-level and structural validation
   BEFORE any ``joblib.load`` deserialization can occur: symlinks, path
   traversal, unexpected files, tampered bytes, altered feature orders, cohort
   pooling flags, or ``approved_for_serving=True`` claims fail closed.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from types import MappingProxyType
from typing import Any, Final, Mapping

import joblib

from ai.errors import BundleIntegrityError
from ai.explainability import METHOD_BY_MODEL_FAMILY
from ai.panels import ResearchPanelContract, get_panel_contract
from ai.training import TrainedResearchRun

REPOSITORY_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
BUNDLE_SCHEMA_VERSION: Final[str] = "cardioassist.ai.research_bundle/v1"
SAFE_BASENAME_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9][a-z0-9._-]{1,63}$")
MAX_BUNDLE_FILE_BYTES: Final[int] = 64 * 1024 * 1024  # 64 MiB ceiling

MANIFEST_FILENAME: Final[str] = "manifest.json"
MODEL_FILENAME: Final[str] = "model.joblib"
PREPROCESSING_FILENAME: Final[str] = "preprocessing.json"
CALIBRATION_FILENAME: Final[str] = "calibration.json"
SHAP_BG_FILENAME: Final[str] = "shap_background.json"
EVALUATION_FILENAME: Final[str] = "evaluation_summary.json"
PROTOCOL_FILENAME: Final[str] = "protocol.md"

REQUIRED_SIBLING_FILES: Final[tuple[str, ...]] = (
    MODEL_FILENAME,
    PREPROCESSING_FILENAME,
    CALIBRATION_FILENAME,
    SHAP_BG_FILENAME,
    EVALUATION_FILENAME,
    PROTOCOL_FILENAME,
)

FORBIDDEN_SUMMARY_KEYS: Final[frozenset[str]] = frozenset(
    {
        "patient_rows",
        "patient_records",
        "raw_rows",
        "raw_records",
        "row_values",
        "predictions",
        "prediction_scores",
        "out_of_fold_predictions",
        "patient_ids",
        "source_rows",
    }
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _target_sha256(definition: str) -> str:
    return _sha256(definition.strip().encode("utf-8"))


def _ensure_safe_output_path(bundle_dir: Path) -> Path:
    resolved_parent = bundle_dir.parent.resolve()
    target = resolved_parent / bundle_dir.name
    if bundle_dir.exists() or bundle_dir.is_symlink():
        raise BundleIntegrityError(
            "bundle_directory_already_exists",
            "Refusing to overwrite an existing artifact bundle directory.",
        )

    try:
        rel = target.relative_to(REPOSITORY_ROOT.resolve())
    except ValueError:
        rel = None

    if rel is not None:
        probe = subprocess.run(
            ["git", "check-ignore", "-q", "--", rel.as_posix()],
            cwd=str(REPOSITORY_ROOT),
            check=False,
        )
        if probe.returncode != 0:
            raise BundleIntegrityError(
                "unignored_repository_path_prohibited",
                "Refusing to write model artifacts inside a non-ignored repository path.",
            )
    return target


def _assert_aggregate_only(summary: Mapping[str, Any]) -> None:
    def _walk(node: Any) -> None:
        if isinstance(node, Mapping):
            for k, v in node.items():
                if str(k).lower() in FORBIDDEN_SUMMARY_KEYS:
                    raise BundleIntegrityError(
                        "patient_level_key_in_summary",
                        "Evaluation summary must not contain row-aligned or patient-level keys.",
                    )
                _walk(v)
        elif isinstance(node, (list, tuple)):
            for item in node:
                _walk(item)

    _walk(summary)
    try:
        json.dumps(summary, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise BundleIntegrityError(
            "non_finite_summary_value",
            "Evaluation summary contains non-JSON or non-finite values.",
        ) from exc


def _write_atomic_private(path: Path, content: bytes) -> dict[str, Any]:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(content)
        handle.flush()
    return {
        "sha256": _sha256(content),
        "size_bytes": len(content),
    }


@dataclass(frozen=True, slots=True)
class VerifiedBundleDescriptor:
    """Result of passing all byte-level and contract checks on a bundle directory."""

    bundle_dir: Path
    manifest: Mapping[str, Any]
    panel: ResearchPanelContract
    verified_files: Mapping[str, str]
    serving_eligibility: str = "RESEARCH_ONLY"
    approved_for_serving: bool = False
    clinical_use_authorized: bool = False


def package_research_bundle(
    trained_run: TrainedResearchRun,
    bundle_dir: Path,
    *,
    external_evaluation: Mapping[str, Any] | None = None,
    generated_at_utc: str | None = None,
) -> VerifiedBundleDescriptor:
    """Write an atomic, self-verifying RESEARCH_ONLY model bundle."""
    target_dir = _ensure_safe_output_path(Path(bundle_dir))
    target_dir.mkdir(parents=True, exist_ok=False)

    timestamp = generated_at_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    eval_doc: dict[str, Any] = {
        "internal_evaluation": dict(trained_run.internal_evaluation),
        "negative_control": dict(trained_run.negative_control),
        "external_evaluation": (
            None if external_evaluation is None else dict(external_evaluation)
        ),
    }
    _assert_aggregate_only(eval_doc)

    # Serialize model container to bytes in memory via temporary file descriptor inside target_dir
    model_payload = {
        "selected_model_family": trained_run.selected_model_family,
        "estimator": trained_run.estimator,
        "fold_ensemble": [
            {
                "fold_index": member.fold_index,
                "model_family": member.model_family,
                "preprocessor_json": member.preprocessor.to_json_dict(),
                "estimator": member.estimator,
            }
            for member in trained_run.fold_ensemble
        ],
    }
    model_path = target_dir / MODEL_FILENAME
    joblib.dump(model_payload, model_path, compress=3)
    model_bytes = model_path.read_bytes()

    prep_bytes = trained_run.preprocessor.to_canonical_json_bytes()
    cal_bytes = trained_run.calibrator.to_canonical_json_bytes()
    shap_bytes = trained_run.shap_background.to_canonical_json_bytes()
    eval_bytes = (
        json.dumps(eval_doc, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")
    protocol_md = (
        f"# Research Protocol Manifest — {trained_run.protocol_id}\n\n"
        f"- **Model ID:** `{trained_run.model_id}` (`v{trained_run.model_version}`)\n"
        f"- **Panel Contract:** `{trained_run.panel.panel_id}` (`{trained_run.panel.contract_sha256}`)\n"
        f"- **Selected Family:** `{trained_run.selected_model_family}`\n"
        f"- **Development Cohort:** `{trained_run.development_cohort_id}` (`{trained_run.development_dataset_id}`)\n"
        f"- **Serving Eligibility:** `RESEARCH_ONLY` (`approved_for_serving = false`)\n"
        f"- **Limitation:** Not clinically validated; never interpret research scores as individual clinical CAD risk.\n"
    ).encode("utf-8")

    file_records: dict[str, dict[str, Any]] = {
        MODEL_FILENAME: {
            "sha256": _sha256(model_bytes),
            "size_bytes": len(model_bytes),
        },
        PREPROCESSING_FILENAME: _write_atomic_private(
            target_dir / PREPROCESSING_FILENAME, prep_bytes
        ),
        CALIBRATION_FILENAME: _write_atomic_private(
            target_dir / CALIBRATION_FILENAME, cal_bytes
        ),
        SHAP_BG_FILENAME: _write_atomic_private(
            target_dir / SHAP_BG_FILENAME, shap_bytes
        ),
        EVALUATION_FILENAME: _write_atomic_private(
            target_dir / EVALUATION_FILENAME, eval_bytes
        ),
        PROTOCOL_FILENAME: _write_atomic_private(
            target_dir / PROTOCOL_FILENAME, protocol_md
        ),
    }

    manifest = {
        "bundle_schema_version": BUNDLE_SCHEMA_VERSION,
        "generated_at_utc": timestamp,
        "model": {
            "model_id": trained_run.model_id,
            "model_version": trained_run.model_version,
            "protocol_id": trained_run.protocol_id,
            "selected_model_family": trained_run.selected_model_family,
            "selected_hyperparameters": dict(trained_run.selected_hyperparameters),
            "calibration_status": "calibrated_out_of_fold_logistic",
            "explainability": {
                "method": METHOD_BY_MODEL_FAMILY[trained_run.selected_model_family],
                "capability": "implemented_and_verified_in_research_harness",
            },
        },
        "panel_contract": {
            "panel_id": trained_run.panel.panel_id,
            "panel_version": trained_run.panel.panel_version,
            "contract_sha256": trained_run.panel.contract_sha256,
            "ordered_feature_names": list(trained_run.panel.feature_names),
        },
        "target": {
            "target_id": trained_run.panel.target_id,
            "target_definition_sha256": _target_sha256(
                trained_run.panel.target_definition
            ),
            "development_cohort_id": trained_run.development_cohort_id,
            "development_dataset_id": trained_run.development_dataset_id,
            "pooled_cohorts": False,
        },
        "eligibility": {
            "serving_eligibility": "RESEARCH_ONLY",
            "approved_for_serving": False,
            "clinical_use_authorized": False,
            "synthetic_only": bool(trained_run.synthetic_only),
        },
        "files": file_records,
    }
    manifest_bytes = (
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")
    _write_atomic_private(target_dir / MANIFEST_FILENAME, manifest_bytes)

    return verify_research_bundle(target_dir)


def _read_safe_regular_file(root: Path, filename: str) -> bytes:
    if not SAFE_BASENAME_RE.match(filename):
        raise BundleIntegrityError(
            "unsafe_bundle_filename",
            f"Unsafe artifact filename '{filename}' rejected.",
            field=filename,
        )
    candidate = root / filename
    if candidate.is_symlink():
        raise BundleIntegrityError(
            "bundle_symlink_prohibited",
            f"Symlinked bundle member '{filename}' is prohibited.",
            field=filename,
        )
    if not candidate.is_file():
        raise BundleIntegrityError(
            "bundle_file_missing",
            f"Required bundle file '{filename}' is missing.",
            field=filename,
        )
    resolved = candidate.resolve()
    if resolved.parent != root.resolve():
        raise BundleIntegrityError(
            "bundle_path_traversal_detected",
            f"Bundle file '{filename}' escaped bundle directory.",
            field=filename,
        )
    size = resolved.stat().st_size
    if size <= 0 or size > MAX_BUNDLE_FILE_BYTES:
        raise BundleIntegrityError(
            "bundle_file_size_invalid",
            f"Bundle file '{filename}' violates byte size limits.",
            field=filename,
        )
    return resolved.read_bytes()


def verify_research_bundle(bundle_dir: Path) -> VerifiedBundleDescriptor:
    """Verify structure, governance flags, contract hashes, and SHA-256 digests."""
    root = Path(bundle_dir)
    if root.is_symlink() or not root.is_dir():
        raise BundleIntegrityError(
            "invalid_bundle_directory",
            "Bundle root must be an existing non-symlink directory.",
        )

    present_entries = {entry.name for entry in root.iterdir()}
    expected_entries = {MANIFEST_FILENAME, *REQUIRED_SIBLING_FILES}
    if present_entries != expected_entries:
        raise BundleIntegrityError(
            "unexpected_bundle_directory_contents",
            "Bundle directory contains missing or unexpected files.",
        )

    manifest_raw = _read_safe_regular_file(root, MANIFEST_FILENAME)
    try:
        manifest = json.loads(manifest_raw.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise BundleIntegrityError(
            "malformed_manifest_json",
            "Bundle manifest.json is not valid UTF-8 JSON.",
        ) from exc

    if not isinstance(manifest, Mapping) or (
        manifest.get("bundle_schema_version") != BUNDLE_SCHEMA_VERSION
    ):
        raise BundleIntegrityError(
            "unsupported_bundle_schema",
            "Unsupported or missing bundle_schema_version in manifest.json.",
        )

    eligibility = manifest.get("eligibility", {})
    if (
        not isinstance(eligibility, Mapping)
        or eligibility.get("serving_eligibility") != "RESEARCH_ONLY"
        or eligibility.get("approved_for_serving") is not False
        or eligibility.get("clinical_use_authorized") is not False
    ):
        raise BundleIntegrityError(
            "unauthorized_serving_claim",
            "Bundle manifest makes an unauthorized serving or clinical-use claim.",
            field="eligibility",
        )

    target = manifest.get("target", {})
    if not isinstance(target, Mapping) or target.get("pooled_cohorts") is not False:
        raise BundleIntegrityError(
            "pooled_cohort_bundle_rejected",
            "Bundles asserting pooled cohorts are rejected.",
            field="target.pooled_cohorts",
        )

    panel_block = manifest.get("panel_contract", {})
    if not isinstance(panel_block, Mapping):
        raise BundleIntegrityError(
            "missing_panel_contract",
            "Bundle manifest lacks panel_contract metadata.",
        )
    panel = get_panel_contract(str(panel_block.get("panel_id", "")))
    if (
        panel_block.get("contract_sha256") != panel.contract_sha256
        or tuple(panel_block.get("ordered_feature_names", ())) != panel.feature_names
    ):
        raise BundleIntegrityError(
            "panel_contract_hash_or_order_mismatch",
            "Bundle panel hash or feature order does not match the registered contract.",
            field="panel_contract",
        )

    if target.get("target_id") != panel.target_id or target.get(
        "target_definition_sha256"
    ) != _target_sha256(panel.target_definition):
        raise BundleIntegrityError(
            "target_definition_mismatch",
            "Bundle target definition hash does not match the registered panel target.",
            field="target",
        )

    model_block = manifest.get("model", {})
    family = str(model_block.get("selected_model_family", ""))
    if family not in METHOD_BY_MODEL_FAMILY:
        raise BundleIntegrityError(
            "unsupported_model_family",
            "Bundle declares an unregistered research model family.",
            field="model.selected_model_family",
        )
    xai_block = model_block.get("explainability", {})
    if (
        not isinstance(xai_block, Mapping)
        or xai_block.get("method") != METHOD_BY_MODEL_FAMILY[family]
    ):
        raise BundleIntegrityError(
            "unfaithful_explainability_declaration",
            "Declared explainability method does not match selected model family.",
            field="model.explainability.method",
        )

    declared_files = manifest.get("files")
    if not isinstance(declared_files, Mapping) or set(declared_files) != set(
        REQUIRED_SIBLING_FILES
    ):
        raise BundleIntegrityError(
            "manifest_files_table_invalid",
            "Manifest files table does not list the exact required bundle files.",
            field="files",
        )

    verified_digests: dict[str, str] = {}
    for filename in REQUIRED_SIBLING_FILES:
        meta = declared_files[filename]
        if not isinstance(meta, Mapping):
            raise BundleIntegrityError(
                "manifest_file_entry_invalid",
                f"Invalid manifest entry for '{filename}'.",
                field=filename,
            )
        content = _read_safe_regular_file(root, filename)
        if len(content) != int(meta.get("size_bytes", -1)):
            raise BundleIntegrityError(
                "file_size_mismatch",
                f"Byte size mismatch detected for '{filename}'.",
                field=filename,
            )
        actual_sha = _sha256(content)
        if actual_sha != str(meta.get("sha256", "")):
            raise BundleIntegrityError(
                "file_sha256_mismatch",
                f"SHA-256 integrity mismatch detected for '{filename}'.",
                field=filename,
            )
        verified_digests[filename] = actual_sha

    return VerifiedBundleDescriptor(
        bundle_dir=root.resolve(),
        manifest=MappingProxyType(dict(manifest)),
        panel=panel,
        verified_files=MappingProxyType(verified_digests),
    )
