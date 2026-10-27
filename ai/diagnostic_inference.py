"""Bounded, guarded OFFLINE diagnostic inference for ONE accepted real bundle.

This module is a **development change after frozen training revision A**
(``cardioassist.ai.bounded_offline_diagnostic_inference/v1``). It is a separate
entry point (``python -m ai.diagnostic_inference``), NOT part of the general
``python -m ai`` synthetic-only CLI, which remains unchanged and still refuses
all real-provenance bundles.

Authorization order (fail closed at the first failure; no retry)
---------------------------------------------------------------
1. Exact local operator confirmation phrase (explicit human invocation).
2. Strict local operator authorization document: bounded operation, synthetic
   input declaration, offline/no-serving/no-telemetry/no-upload boundary.
3. Independent scope authorization from
   :mod:`ai.diagnostic_scope` -- an EMPTY trusted registry in production --
   plus Git evidence (ratified governance merge, frozen document bytes, clean
   approved execution revision).
4. Strict synthetic input declaration + five-feature schema validation
   (including explicit rejection of non-finite JSON numbers).
5. Existing trusted-local bundle verification via
   :func:`ai.packaging.verify_trusted_local_bundle`: local-root containment,
   platform ACLs (including Win32 NTFS DACLs), SHA-256 digests, HMAC-SHA256
   producer authentication, quarantine absence, and post-run acceptance.
6. Explicit re-verification of the acceptance marker, quarantine absence,
   exact accepted Cleveland bundle identity, manifest digest, and five-field
   panel contract.
7. Deserialization ONLY through
   :meth:`ai.inference.ResearchCadPredictor.from_verified_bundle`, which repeats
   the trusted-local verification before ``joblib.load``.
8. Prediction through ``predict_research_only`` reusing existing calibration,
   exact SHAP, and certified LIME; then independent post-hoc verification of
   score consistency, calibration, SHAP additivity, LIME fidelity/stability and
   LIME quality. Low-quality LIME feature weights are NEVER trusted or emitted.

No network, no telemetry, no uploads, no API serving, no training/tuning, no
bundle writes, and no patient data. The only inputs are explicitly fabricated
synthetic records. Output is an aggregate JSON report on stdout; no file is
written. This module is never imported by ``backend/app/``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any, Final, Mapping, Sequence

from scipy.special import expit

from ai.calibration import OofLogisticCalibrator
from ai.diagnostic_scope import (
    DIAGNOSTIC_GOVERNANCE_DOCUMENT_RELATIVE_PATH,
    DIAGNOSTIC_INTERFACE_VERSION,
    DIAGNOSTIC_MAX_RECORDS,
    DIAGNOSTIC_OPERATOR_CONFIRMATION,
    DIAGNOSTIC_SCOPE_ID,
    DIAGNOSTIC_TARGET_BUNDLE,
    DiagnosticScopeContext,
    DiagnosticScopeError,
    _parse_strict_json,
    _read_private_local_json,
    authorize_diagnostic_scope,
    load_diagnostic_authorization,
)
from ai.errors import AiPipelineError
from ai.explainability import ADDITIVITY_TOLERANCE
from ai.filesystem_security import is_reparse_or_symlink
from ai.inference import ResearchCadPredictor, ResearchPredictionResult
from ai.lime_explainability import DEFAULT_LIME_STABILITY_SEEDS, LimeConfig
from ai.lime_quality import (
    LimeQualityAssessment,
    LimeQualityPolicy,
    LimeQualityStatus,
    assess_lime_quality,
)
from ai.packaging import (
    BUNDLE_ACCEPTANCE_MARKER_FILENAME,
    BUNDLE_ACCEPTANCE_SCHEMA_VERSION,
    BUNDLE_QUARANTINE_MARKER_FILENAME,
    CALIBRATION_FILENAME,
    MANIFEST_FILENAME,
    REPOSITORY_ROOT,
    REQUIRED_SIBLING_FILES,
    VerifiedBundleDescriptor,
    verify_trusted_local_bundle,
)
from ai.panels import DA_A2_RESTING_PANEL, validate_clinical_record

DIAGNOSTIC_INPUT_SCHEMA_VERSION: Final[str] = (
    "cardioassist.ai.diagnostic_synthetic_input/v1"
)
DIAGNOSTIC_MAX_INPUT_BYTES: Final[int] = 64 * 1024
EXIT_OK: Final[int] = 0
EXIT_FAIL_CLOSED: Final[int] = 2

_INPUT_ENVELOPE_KEYS: Final[frozenset[str]] = frozenset(
    {"schema_version", "synthetic", "input_declaration", "records"}
)
_RECORD_KEYS: Final[frozenset[str]] = frozenset(
    {"synthetic", "panel_id", "features", "units", "missing_reasons", "context"}
)
_ALLOWED_BUNDLE_ENTRIES: Final[frozenset[str]] = frozenset(
    {
        MANIFEST_FILENAME,
        *REQUIRED_SIBLING_FILES,
        BUNDLE_ACCEPTANCE_MARKER_FILENAME,
    }
)

DIAGNOSTIC_LIMITATIONS: Final[tuple[str, ...]] = (
    "RESEARCH_ONLY offline diagnostic output. Not a clinical diagnosis, triage, "
    "treatment recommendation, or patient self-assessment.",
    "Scores are descriptive research outputs from a single internal Cleveland "
    "development cohort; they are NOT clinically validated individual CAD risk.",
    "SHAP attributions are exact additive decompositions on their declared "
    "scale (calibrated log-odds for this accepted l2_logistic_regression bundle), "
    "NEVER additive in calibrated probability units.",
    "LIME feature weights are local weighted-surrogate approximations, not exact "
    "Shapley values; they are emitted ONLY when the registered quality verdict is "
    "ACCEPTABLE_LOCAL_APPROXIMATION, otherwise they are suppressed entirely.",
    "Gate PT P-1 remains PENDING and P-3 remains CLOSED; no supervisor, ethics, "
    "institutional, or clinical approval is claimed.",
    "No real patient record was used as an input. All inference inputs in this "
    "interface are explicitly fabricated synthetic records.",
    "No API serving, telemetry, upload, external evaluation, retraining, tuning, "
    "or bundle modification is performed.",
)


class DiagnosticIntegrityError(AiPipelineError):
    """Raised when a diagnostic invariant (score/SHAP/LIME/identity) fails."""


def _fail(code: str, message: str, *, field: str | None = None) -> None:
    raise DiagnosticIntegrityError(code, message, field=field)


def _require(condition: bool, code: str, message: str, *, field: str | None = None) -> None:
    if not condition:
        _fail(code, message, field=field)


def _finite(value: Any, *, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise DiagnosticIntegrityError(
            "diagnostic_non_finite_value",
            f"Diagnostic output field '{field}' is not a finite number.",
            field=field,
        ) from exc
    _require(
        math.isfinite(number),
        "diagnostic_non_finite_value",
        f"Diagnostic output field '{field}' is NaN or infinite; refusing to report it.",
        field=field,
    )
    return number


def _mapping(node: Any, *, field: str) -> Mapping[str, Any]:
    _require(
        isinstance(node, Mapping),
        "diagnostic_malformed_structure",
        f"Expected a mapping at '{field}'.",
        field=field,
    )
    return node


# --------------------------------------------------------------------------- #
# Synthetic input declaration and schema
# --------------------------------------------------------------------------- #


def load_diagnostic_input(
    input_path: Path, *, repo_root: Path = REPOSITORY_ROOT
) -> list[dict[str, Any]]:
    """Parse and validate the explicitly fabricated synthetic input records."""
    doc = _read_private_local_json(
        Path(input_path),
        repo_root=Path(repo_root),
        max_bytes=DIAGNOSTIC_MAX_INPUT_BYTES,
        field="input",
    )
    _require(
        frozenset(doc) == _INPUT_ENVELOPE_KEYS,
        "diagnostic_input_envelope_invalid",
        "Diagnostic input envelope must declare exactly the registered keys.",
        field="input",
    )
    _require(
        doc.get("schema_version") == DIAGNOSTIC_INPUT_SCHEMA_VERSION,
        "diagnostic_input_schema_unsupported",
        "Unsupported diagnostic input schema version.",
        field="schema_version",
    )
    _require(
        doc.get("synthetic") is True,
        "diagnostic_input_not_declared_synthetic",
        "Diagnostic input envelope must declare 'synthetic': true.",
        field="synthetic",
    )
    declaration = _mapping(
        doc.get("input_declaration"), field="input_declaration"
    )
    _require(
        frozenset(declaration) == frozenset(
            {"origin", "contains_patient_data", "panel_id", "records_are_synthetic"}
        ),
        "diagnostic_input_declaration_invalid",
        "Input declaration must contain exactly the registered keys.",
        field="input_declaration",
    )
    _require(
        declaration.get("origin") == "EXPLICITLY_FABRICATED"
        and declaration.get("contains_patient_data") is False
        and declaration.get("records_are_synthetic") is True
        and declaration.get("panel_id") == DA_A2_RESTING_PANEL.panel_id,
        "diagnostic_input_declaration_invalid",
        "Only explicitly fabricated, non-patient synthetic records on the "
        "five-feature da_a2_resting_v1 panel are permitted.",
        field="input_declaration",
    )
    records = doc.get("records")
    _require(
        isinstance(records, list)
        and 1 <= len(records) <= DIAGNOSTIC_MAX_RECORDS,
        "diagnostic_input_record_count_invalid",
        f"Diagnostic input must contain 1..{DIAGNOSTIC_MAX_RECORDS} synthetic records.",
        field="records",
    )
    validated_records: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        _require(
            isinstance(record, Mapping),
            "diagnostic_input_record_malformed",
            "Each diagnostic input record must be a JSON object.",
            field=f"records[{index}]",
        )
        _require(
            frozenset(record) <= _RECORD_KEYS,
            "diagnostic_input_record_malformed",
            "Diagnostic input record contains unsupported top-level keys.",
            field=f"records[{index}]",
        )
        _require(
            record.get("synthetic") is True,
            "diagnostic_non_synthetic_input_rejected",
            "Every diagnostic input record must be explicitly synthetic; real or "
            "unlabeled patient records are never accepted.",
            field=f"records[{index}].synthetic",
        )
        _require(
            record.get("panel_id") == DA_A2_RESTING_PANEL.panel_id,
            "diagnostic_input_panel_mismatch",
            "Record panel_id must equal the accepted five-field panel.",
            field=f"records[{index}].panel_id",
        )
        features = _mapping(record.get("features"), field=f"records[{index}].features")
        _require(
            frozenset(features) <= frozenset(DA_A2_RESTING_PANEL.feature_names),
            "diagnostic_input_wrong_panel_schema",
            "Record features must be a subset of the exact five registered fields.",
            field=f"records[{index}].features",
        )
        _require(
            frozenset(DA_A2_RESTING_PANEL.required_names) <= frozenset(features)
            and all(
                features.get(name) is not None
                for name in DA_A2_RESTING_PANEL.required_names
            ),
            "diagnostic_input_missing_required_feature",
            "Required five-field panel measurements are absent or explicitly null.",
            field=f"records[{index}].features",
        )
        context = record.get("context", {})
        _require(
            isinstance(context, Mapping)
            and context.get("track", "A") == "A",
            "diagnostic_input_prohibited_source",
            "Track B / wearable provenance is prohibited.",
            field=f"records[{index}].context",
        )
        # Reuse the existing registered clinical-record validator BEFORE any
        # bundle verification or deserialization (units, categorical codes,
        # missing reasons, leakage fields, non-finite and boolean values).
        validate_clinical_record(record, DA_A2_RESTING_PANEL, require_synthetic=True)
        validated_records.append(dict(record))
    return validated_records


# --------------------------------------------------------------------------- #
# Accepted-bundle identity, acceptance, quarantine, and authentication
# --------------------------------------------------------------------------- #


def _read_bundle_marker(root: Path, filename: str) -> Mapping[str, Any]:
    path = root / filename
    _require(
        not is_reparse_or_symlink(path) and path.is_file(),
        "diagnostic_acceptance_marker_invalid",
        f"Required bundle custody marker '{filename}' is missing or unsafe.",
        field=filename,
    )
    try:
        marker = _parse_strict_json(path.read_bytes(), field=filename)
    except AiPipelineError:
        raise
    except OSError as exc:
        raise DiagnosticIntegrityError(
            "diagnostic_acceptance_marker_invalid",
            f"Bundle custody marker '{filename}' could not be read.",
            field=filename,
        ) from exc
    return marker


def verify_accepted_bundle_identity(
    descriptor: VerifiedBundleDescriptor, *, scope: DiagnosticScopeContext
) -> dict[str, Any]:
    """Explicitly verify provenance, acceptance, quarantine and exact identity.

    :func:`ai.packaging.verify_trusted_local_bundle` has already enforced the
    same custody gates; these explicit checks make the independent diagnostic
    contract auditable and give dedicated fail-closed error codes.
    """
    root = Path(descriptor.bundle_dir)
    manifest = descriptor.manifest
    _require(
        descriptor.producer_authenticated is True
        and descriptor.safe_for_pickle_deserialization is True
        and descriptor.integrity_verified_only_not_authenticated is False,
        "diagnostic_bundle_not_authenticated",
        "Bundle producer was not authenticated by the trusted-local HMAC/ACL path.",
        field="authentication",
    )
    _require(
        root.name == scope.expected_bundle_dir_name,
        "diagnostic_bundle_identity_mismatch",
        "Bundle directory name does not equal the single accepted Cleveland "
        "bundle identifier.",
        field="bundle_dir_name",
    )
    _require(
        not (root / BUNDLE_QUARANTINE_MARKER_FILENAME).exists(),
        "diagnostic_bundle_quarantined",
        "A quarantine marker is present; the accepted bundle must never be loaded.",
        field=BUNDLE_QUARANTINE_MARKER_FILENAME,
    )
    present = {entry.name for entry in root.iterdir()}
    _require(
        present <= _ALLOWED_BUNDLE_ENTRIES
        and BUNDLE_ACCEPTANCE_MARKER_FILENAME in present,
        "diagnostic_bundle_layout_invalid",
        "Accepted real bundle has an unexpected directory inventory or lacks "
        "its post-run acceptance marker.",
        field="bundle_layout",
    )
    marker = _read_bundle_marker(root, BUNDLE_ACCEPTANCE_MARKER_FILENAME)
    _require(
        marker.get("marker") == BUNDLE_ACCEPTANCE_MARKER_FILENAME
        and marker.get("bundle_acceptance_version") == BUNDLE_ACCEPTANCE_SCHEMA_VERSION
        and marker.get("accepted_for_loading") is True
        and marker.get("bundle_dir_name") == root.name
        and str(marker.get("expected_source_sha256", "")).strip().lower()
        == scope.expected_source_sha256,
        "diagnostic_acceptance_marker_invalid",
        "Post-run acceptance marker does not bind this accepted bundle and the "
        "ratified source SHA-256.",
        field=BUNDLE_ACCEPTANCE_MARKER_FILENAME,
    )

    manifest_path = root / MANIFEST_FILENAME
    _require(
        not is_reparse_or_symlink(manifest_path) and manifest_path.is_file(),
        "diagnostic_manifest_unreadable",
        "Verified bundle manifest is missing or unsafe.",
        field=MANIFEST_FILENAME,
    )
    manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    _require(
        manifest_sha == scope.expected_manifest_sha256,
        "diagnostic_manifest_digest_mismatch",
        "The bundle manifest digest does not equal the maintainer-pinned digest "
        "of the accepted bundle; refusing to load any other artifact.",
        field="expected_manifest_sha256",
    )

    eligibility = _mapping(manifest.get("eligibility"), field="eligibility")
    _require(
        eligibility.get("synthetic_only") is False
        and eligibility.get("execution_mode") == "INTERNAL_EXPLORATORY_RESEARCH"
        and eligibility.get("serving_eligibility") == "RESEARCH_ONLY"
        and eligibility.get("approved_for_serving") is False
        and eligibility.get("clinical_use_authorized") is False,
        "diagnostic_bundle_provenance_invalid",
        "Bundle provenance is not the accepted, non-synthetic, internal "
        "exploratory RESEARCH_ONLY artifact.",
        field="eligibility",
    )
    auth = _mapping(manifest.get("research_authorization"), field="research_authorization")
    _require(
        str(auth.get("expected_source_sha256", "")).strip().lower()
        == scope.expected_source_sha256
        and auth.get("dataset_id") == scope.expected_dataset_id
        and auth.get("panel_id") == scope.expected_panel_id
        and auth.get("governance_decision_id") == "D-047",
        "diagnostic_bundle_provenance_invalid",
        "Bundle research authorization does not bind the accepted D-047 "
        "Cleveland source, dataset, and panel.",
        field="research_authorization",
    )
    model = _mapping(manifest.get("model"), field="model")
    hyper = _mapping(model.get("selected_hyperparameters"), field="selected_hyperparameters")
    selected_c = _finite(hyper.get("C"), field="selected_hyperparameters.C")
    _require(
        model.get("model_id") == scope.expected_model_id
        and model.get("model_version") == scope.expected_model_version
        and model.get("protocol_id") == scope.expected_protocol_id
        and model.get("selected_model_family") == scope.expected_model_family
        and model.get("execution_profile") == scope.expected_execution_profile
        and set(hyper) == {"C"}
        and selected_c == scope.expected_selected_c,
        "diagnostic_bundle_identity_mismatch",
        "Bundle model identity (id/version/protocol/family/frozen D-047 "
        "profile/selected C=10.0) does not match the accepted Cleveland bundle.",
        field="model",
    )
    panel_block = _mapping(manifest.get("panel_contract"), field="panel_contract")
    panel = descriptor.panel
    _require(
        panel.panel_id == scope.expected_panel_id
        and panel.panel_id == DIAGNOSTIC_TARGET_BUNDLE["expected_panel_id"]
        and panel.contract_sha256
        == DIAGNOSTIC_TARGET_BUNDLE["expected_panel_contract_sha256"]
        and panel.feature_names
        == DIAGNOSTIC_TARGET_BUNDLE["expected_ordered_feature_names"]
        and len(panel.feature_names) == 5
        and panel_block.get("contract_sha256") == panel.contract_sha256
        and tuple(panel_block.get("ordered_feature_names", ())) == panel.feature_names,
        "diagnostic_bundle_panel_mismatch",
        "Bundle panel is not the exact five-feature da_a2_resting_v1 contract.",
        field="panel_contract",
    )
    target = _mapping(manifest.get("target"), field="target")
    _require(
        target.get("pooled_cohorts") is False,
        "diagnostic_bundle_provenance_invalid",
        "Pooled-cohort bundle is rejected.",
        field="target.pooled_cohorts",
    )
    return {
        "bundle_dir_name": root.name,
        "manifest_sha256": manifest_sha,
        "panel_id": panel.panel_id,
        "panel_contract_sha256": panel.contract_sha256,
        "ordered_feature_names": list(panel.feature_names),
        "execution_profile": str(model.get("execution_profile")),
        "selected_model_family": str(model.get("selected_model_family")),
        "selected_c": selected_c,
        "producer_authenticated": True,
        "post_run_acceptance_verified": True,
        "quarantine_marker_absent": True,
        "verified_artifact_hashes": dict(descriptor.verified_files),
    }


# --------------------------------------------------------------------------- #
# Post-hoc diagnostic verification: scores, calibration, SHAP, LIME
# --------------------------------------------------------------------------- #


def _verify_scores_and_calibration(
    result: ResearchPredictionResult,
    *,
    calibrator: OofLogisticCalibrator,
    reference: ResearchPredictionResult | None,
) -> dict[str, Any]:
    raw = _finite(result.raw_model_score, field="raw_model_score")
    raw_log_odds = _finite(result.raw_model_log_odds, field="raw_model_log_odds")
    calibrated = _finite(
        result.calibrated_research_score, field="calibrated_research_score"
    )
    cal_log_odds = _finite(result.calibrated_log_odds, field="calibrated_log_odds")
    threshold = _finite(result.exploratory_threshold, field="exploratory_threshold")
    _require(
        0.0 < raw < 1.0 and 0.0 < calibrated < 1.0 and 0.0 <= threshold <= 1.0,
        "diagnostic_score_out_of_range",
        "Research probabilities must lie strictly inside (0, 1).",
        field="prediction",
    )
    _require(
        abs(float(expit(cal_log_odds)) - calibrated) <= 1e-9
        and abs(float(expit(raw_log_odds)) - raw) <= 1e-9,
        "diagnostic_score_scale_inconsistent",
        "Log-odds and probability outputs are inconsistent under the logistic link.",
        field="prediction",
    )
    recomputed = _finite(
        calibrator.calibrated_log_odds(raw, raw_logits=raw_log_odds),
        field="recomputed_calibrated_log_odds",
    )
    _require(
        abs(recomputed - cal_log_odds) <= ADDITIVITY_TOLERANCE
        and abs(float(expit(recomputed)) - calibrated) <= 1e-9,
        "diagnostic_calibration_mismatch",
        "Reported calibrated output does not equal the verified bundle's OOF "
        "logistic calibrator applied to the raw model output.",
        field="calibration",
    )
    deterministic: bool | None = None
    if reference is not None:
        deterministic = bool(
            reference.raw_model_score == raw
            and reference.raw_model_log_odds == raw_log_odds
            and reference.calibrated_research_score == calibrated
            and reference.calibrated_log_odds == cal_log_odds
        )
        _require(
            deterministic,
            "diagnostic_score_not_deterministic",
            "Repeated inference on the same synthetic record changed the score.",
            field="determinism",
        )
    return {
        "raw_model_score": raw,
        "raw_model_log_odds": raw_log_odds,
        "calibrated_research_score": calibrated,
        "calibrated_log_odds": cal_log_odds,
        "recomputed_calibrated_log_odds": recomputed,
        "exploratory_threshold": threshold,
        "exploratory_above_threshold_flag": bool(
            result.exploratory_above_threshold_flag
        ),
        "score_interpretation": "RESEARCH_ONLY_NOT_INDIVIDUAL_CLINICAL_RISK",
        "deterministic_on_repeat": deterministic,
        "passed": True,
    }


def _verify_shap(result: ResearchPredictionResult) -> dict[str, Any]:
    explanation = result.explanation
    base = _finite(explanation.base_value, field="shap.base_value")
    target = _finite(
        explanation.target_prediction_on_scale, field="shap.target_prediction_on_scale"
    )
    linked = _finite(
        explanation.linked_probability_value, field="shap.linked_probability_value"
    )
    values = [
        _finite(item.shap_value, field=f"shap.{item.feature_name}")
        for item in explanation.attributions
    ]
    names = tuple(item.feature_name for item in explanation.attributions)
    _require(
        explanation.sum_check_passed is True
        and explanation.synthetic_placeholder is False
        and explanation.faithful_to_model_family is True
        and explanation.additive_on_calibrated_probability is False,
        "diagnostic_shap_not_exact",
        "SHAP explanation is not a verified exact, model-faithful decomposition.",
        field="explanation",
    )
    _require(
        names == DA_A2_RESTING_PANEL.feature_names and len(values) == 5,
        "diagnostic_shap_feature_set_mismatch",
        "SHAP attributions do not cover exactly the five ordered panel features.",
        field="explanation.attributions",
    )
    discrepancy = abs(base + float(sum(values)) - target)
    _require(
        discrepancy <= 1e-7,
        "diagnostic_shap_decomposition_failed",
        "base_value + sum(SHAP attributions) does not equal the declared target.",
        field="explanation.sum_check",
    )
    _require(
        explanation.explained_quantity == "calibrated_log_odds"
        and explanation.scale == "calibrated_log_odds"
        and abs(target - result.calibrated_log_odds) <= ADDITIVITY_TOLERANCE
        and abs(linked - result.calibrated_research_score) <= 1e-9,
        "diagnostic_shap_target_misaligned",
        "Exact SHAP target is not aligned to the calibrated log-odds output of "
        "the accepted l2_logistic_regression bundle.",
        field="explanation.explained_quantity",
    )
    return {
        "method": explanation.method,
        "explained_quantity": explanation.explained_quantity,
        "scale": explanation.scale,
        "additive_on_calibrated_probability": False,
        "base_value": base,
        "sum_of_attributions": float(sum(values)),
        "target_prediction_on_scale": target,
        "max_abs_discrepancy": discrepancy,
        "linked_probability_value": linked,
        "sum_check_passed": True,
        "attributions": [
            {"feature_name": item.feature_name, "shap_value": value}
            for item, value in zip(explanation.attributions, values)
        ],
        "passed": True,
    }


def _verify_lime(
    result: ResearchPredictionResult,
    *,
    lime_policy: LimeQualityPolicy,
    require_acceptable_quality: bool,
) -> dict[str, Any]:
    explanation = result.lime_explanation
    stability = result.lime_stability
    if explanation is None:
        return {
            "requested": False,
            "status": "NOT_REQUESTED",
            "feature_weights_trusted": False,
            "feature_weights": None,
            "note": (
                "No LIME evidence was generated; no LIME feature weights exist "
                "and none may be inferred."
            ),
        }
    _require(
        stability is not None,
        "diagnostic_lime_stability_missing",
        "LIME stability assessment is mandatory for a diagnostic quality verdict; "
        "no LIME weights can be trusted without it.",
        field="lime_stability",
    )
    comparability = _mapping(result.lime_comparability, field="lime_comparability")
    _require(
        comparability.get("comparable") is True,
        "diagnostic_lime_scale_mismatch",
        "LIME and exact SHAP do not target the same declared score scale.",
        field="lime_comparability",
    )
    model_at_instance = _finite(
        explanation.model_prediction_at_instance,
        field="lime.model_prediction_at_instance",
    )
    expected_target: float | None = {
        "calibrated_log_odds": result.calibrated_log_odds,
        "raw_model_score": result.raw_model_score,
        "raw_model_log_odds": result.raw_model_log_odds,
    }.get(explanation.explained_quantity)
    _require(
        expected_target is not None
        and abs(model_at_instance - float(expected_target)) <= 1e-7,
        "diagnostic_lime_target_misaligned",
        "LIME target value does not match the prediction on its declared scale.",
        field="lime.explained_quantity",
    )
    fidelity: dict[str, Any] = {}
    for name in (
        "local_fidelity_abs_error",
        "local_fidelity_relative_error",
        "neighborhood_output_weighted_sd",
        "local_fidelity_error_in_neighborhood_sigma",
        "weighted_rmse",
        "unweighted_rmse",
        "n_effective_samples",
        "design_condition_number",
        "surrogate_intercept",
        "surrogate_prediction_at_instance",
        "model_rows_scored",
        "model_call_count",
    ):
        fidelity[name] = _finite(getattr(explanation, name), field=f"lime.{name}")
    for name in ("weighted_r2", "unweighted_r2", "holdout_weighted_r2"):
        value = getattr(explanation, name)
        fidelity[name] = None if value is None else _finite(value, field=f"lime.{name}")
    weights = {
        item.feature_name: _finite(
            item.lime_weight, field=f"lime.weight.{item.feature_name}"
        )
        for item in explanation.attributions
    }
    _require(
        tuple(weights) == DA_A2_RESTING_PANEL.feature_names,
        "diagnostic_lime_feature_set_mismatch",
        "LIME weights do not cover exactly the five ordered panel features.",
        field="lime.attributions",
    )
    stability_metrics: dict[str, Any] = {}
    for name in (
        "max_feature_weight_std",
        "mean_feature_weight_std",
        "max_abs_weight_deviation_from_reference_seed",
        "min_pairwise_spearman",
        "mean_pairwise_spearman",
        "sign_agreement_fraction",
        "top_k_overlap_fraction",
        "max_local_prediction_abs_deviation",
        "max_local_fidelity_relative_error",
    ):
        stability_metrics[name] = _finite(
            getattr(stability, name), field=f"lime.stability.{name}"
        )
    _require(
        len(tuple(stability.seeds)) >= lime_policy.min_stability_seeds
        and bool(stability.per_seed_fidelity_statuses),
        "diagnostic_lime_stability_missing",
        "Registered multi-seed stability evidence is incomplete.",
        field="lime.stability.seeds",
    )
    assessment: LimeQualityAssessment = assess_lime_quality(
        explanation, policy=lime_policy, stability=stability
    )
    reliable = bool(assessment.is_reliable_for_interpretation)
    if not reliable and require_acceptable_quality:
        raise DiagnosticIntegrityError(
            "diagnostic_lime_quality_not_acceptable",
            "LIME explanation is not acceptable for interpretation "
            f"(status {assessment.status.value}); failed criteria: "
            + (", ".join(assessment.failed_criteria) or "none")
            + "; unassessed criteria: "
            + (", ".join(assessment.unassessed_criteria) or "none")
            + ". Feature weights are suppressed and must not be relied upon.",
            field="lime.quality",
        )
    quality = assessment.to_dict()
    return {
        "requested": True,
        "status": assessment.status.value,
        "feature_weights_trusted": reliable,
        "feature_weights": dict(weights) if reliable else None,
        "weights_suppression_reason": (
            None
            if reliable
            else (
                "LIME quality verdict is not "
                f"{LimeQualityStatus.ACCEPTABLE_LOCAL_APPROXIMATION.value}; "
                "weights are diagnostic-only and deliberately omitted."
            )
        ),
        "explained_quantity": explanation.explained_quantity,
        "scale": explanation.scale,
        "config_sha256": explanation.config_sha256,
        "seeds": list(stability.seeds),
        "stability_assessment": stability.stability_assessment,
        "per_seed_fidelity_statuses": list(stability.per_seed_fidelity_statuses),
        "fidelity": fidelity,
        "stability_metrics": stability_metrics,
        "comparability": dict(comparability),
        "quality": quality,
        "passed": reliable,
    }


def verify_diagnostic_result(
    *,
    result: ResearchPredictionResult,
    reference: ResearchPredictionResult | None,
    calibrator: OofLogisticCalibrator,
    lime_requested: bool,
    lime_policy: LimeQualityPolicy,
    require_acceptable_lime_quality: bool,
) -> dict[str, Any]:
    """Independently verify one prediction's score/calibration/SHAP/LIME evidence."""
    _require(
        result.serving_eligibility == "RESEARCH_ONLY"
        and result.approved_for_serving is False
        and result.clinical_use_authorized is False
        and result.clinically_reliable_individual_cad_risk is False,
        "diagnostic_serving_claim_rejected",
        "Prediction result makes an unauthorized serving or clinical claim.",
        field="governance",
    )
    _require(
        lime_requested == (result.lime_explanation is not None),
        "diagnostic_lime_request_mismatch",
        "LIME evidence presence does not match the diagnostic request.",
        field="lime",
    )
    scores = _verify_scores_and_calibration(
        result, calibrator=calibrator, reference=reference
    )
    shap = _verify_shap(result)
    lime = _verify_lime(
        result,
        lime_policy=lime_policy,
        require_acceptable_quality=require_acceptable_lime_quality,
    )
    # A final serialization gate catches non-finite values hiding in dispersion,
    # quality, or any nested structure before anything is reported.
    try:
        json.dumps(result.to_dict(), allow_nan=False, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise DiagnosticIntegrityError(
            "diagnostic_non_finite_value",
            "Serialized prediction contains a non-finite or non-JSON value.",
            field="result.to_dict",
        ) from exc
    return {
        "scores": scores,
        "shap": shap,
        "lime": lime,
        "uncertainty": dict(result.uncertainty),
        "limitations": list(DIAGNOSTIC_LIMITATIONS),
        "all_exact_checks_passed": True,
        "lime_weights_trusted": bool(lime["feature_weights_trusted"]),
    }


# --------------------------------------------------------------------------- #
# Orchestrator
# --------------------------------------------------------------------------- #


def run_offline_diagnostics(
    *,
    bundle_dir: Path,
    trusted_local_root: Path,
    authorization_path: Path,
    input_path: Path,
    operator_confirmation: str | None,
    signing_key: bytes | None = None,
    repo_root: Path = REPOSITORY_ROOT,
    with_lime: bool = True,
    lime_config: LimeConfig | None = None,
    lime_stability_seeds: Sequence[int] | None = DEFAULT_LIME_STABILITY_SEEDS,
    lime_quality_policy: LimeQualityPolicy | None = None,
    require_acceptable_lime_quality: bool = False,
) -> dict[str, Any]:
    """Run bounded offline diagnostics; fail closed before any bundle load.

    Nothing is written, no network primitive exists in this module, and the
    accepted real bundle is only ever read through the existing trusted-local
    verification and :class:`ai.inference.ResearchCadPredictor`.
    """
    # 1. Explicit human invocation. No filesystem access before this check.
    if operator_confirmation != DIAGNOSTIC_OPERATOR_CONFIRMATION:
        raise DiagnosticScopeError(
            "diagnostic_operator_confirmation_required",
            "The exact local operator confirmation phrase is required before "
            "any diagnostic document or bundle is read.",
            field="operator_confirmation",
        )

    root = Path(repo_root)
    bundle_root = Path(bundle_dir)
    trust_root = Path(trusted_local_root)
    _require(
        not is_reparse_or_symlink(bundle_root)
        and not is_reparse_or_symlink(trust_root),
        "diagnostic_untrusted_bundle_location",
        "Bundle and trusted root must not be symlinks/junctions/reparse points.",
        field="bundle_dir",
    )
    # The operator and input documents must never live inside the accepted
    # bundle directory (their presence would alter the signed inventory).
    for label, candidate in (
        ("authorization", Path(authorization_path)),
        ("input", Path(input_path)),
    ):
        try:
            inside = candidate.resolve().is_relative_to(bundle_root.resolve())
        except (OSError, ValueError):
            inside = False
        _require(
            not inside,
            "diagnostic_local_file_invalid_location",
            f"The {label} document must not be stored inside the accepted bundle.",
            field=label,
        )

    # 2/3. Local operator authorization + independent ratified scope + Git.
    authorization = load_diagnostic_authorization(
        Path(authorization_path), repo_root=root
    )
    scope = authorize_diagnostic_scope(
        authorization, repo_root=root, operator_confirmation=operator_confirmation
    )

    # 4. Synthetic-only input declaration and five-field schema.
    records = load_diagnostic_input(Path(input_path), repo_root=root)

    # 5. Existing trusted-local bundle verification (ACL / NTFS / HMAC / digest /
    #    quarantine / post-run acceptance) BEFORE any deserialization.
    descriptor = verify_trusted_local_bundle(
        bundle_root, trusted_local_root=trust_root, signing_key=signing_key
    )
    # 6. Explicit identity/acceptance/quarantine re-verification.
    identity = verify_accepted_bundle_identity(descriptor, scope=scope)

    # 7. Load through the existing predictor (it re-verifies before joblib.load).
    predictor = ResearchCadPredictor.from_verified_bundle(
        bundle_root, trusted_local_root=trust_root, signing_key=signing_key
    )
    _require(
        predictor.panel.panel_id == descriptor.panel.panel_id
        and predictor.panel.contract_sha256 == descriptor.panel.contract_sha256
        and predictor.execution_profile == scope.expected_execution_profile
        and predictor.model_family == scope.expected_model_family
        and predictor.model_id == scope.expected_model_id,
        "diagnostic_loaded_bundle_identity_mismatch",
        "Loaded predictor identity differs from the pre-verified descriptor.",
        field="predictor_identity",
    )
    calibration_doc = json.loads(
        (descriptor.bundle_dir / CALIBRATION_FILENAME).read_text(encoding="utf-8")
    )
    calibrator = OofLogisticCalibrator.from_json_dict(calibration_doc)
    active_policy = lime_quality_policy or LimeQualityPolicy()
    active_config = (
        (lime_config if lime_config is not None else LimeConfig())
        if with_lime
        else None
    )
    active_seeds = (
        tuple(lime_stability_seeds)
        if with_lime and lime_stability_seeds is not None
        else None
    )
    if with_lime:
        _require(
            active_seeds is not None
            and len(active_seeds) >= active_policy.min_stability_seeds,
            "diagnostic_lime_stability_missing",
            "Diagnostic LIME requires the registered multi-seed stability assessment.",
            field="lime_stability_seeds",
        )

    # 8. Per-record inference and independent verification.
    per_record: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        result = predictor.predict_research_only(
            record,
            lime_config=active_config,
            lime_stability_seeds=active_seeds,
            lime_quality_policy=active_policy,
            lime_require_acceptable_quality=False,
        )
        reference = predictor.predict_research_only(record)
        verified = verify_diagnostic_result(
            result=result,
            reference=reference,
            calibrator=calibrator,
            lime_requested=with_lime,
            lime_policy=active_policy,
            require_acceptable_lime_quality=require_acceptable_lime_quality,
        )
        per_record.append(
            {
                "record_index": index,
                "synthetic_input_confirmed": True,
                **verified,
            }
        )

    return {
        "status": "OK",
        "command": "offline-diagnostics",
        "interface_version": DIAGNOSTIC_INTERFACE_VERSION,
        "scope_id": DIAGNOSTIC_SCOPE_ID,
        "scope": scope.identity(),
        "bundle": identity,
        "input": {
            "schema_version": DIAGNOSTIC_INPUT_SCHEMA_VERSION,
            "records_are_synthetic": True,
            "contains_patient_data": False,
            "panel_id": DA_A2_RESTING_PANEL.panel_id,
            "record_count": len(records),
        },
        "verification": {
            "checks_applied": [
                "explicit_local_operator_authorization",
                "independent_ratified_diagnostic_scope",
                "governance_commit_ancestry_and_frozen_document_hash",
                "clean_approved_execution_revision",
                "synthetic_input_declaration_and_five_field_schema",
                "trusted_local_root_containment",
                "platform_access_control_including_ntfs_dacl",
                "sha256_integrity",
                "hmac_sha256_producer_attestation",
                "post_run_acceptance_marker",
                "quarantine_marker_absence",
                "exact_accepted_bundle_identity_and_manifest_digest",
                "score_and_calibration_consistency",
                "exact_shap_additive_decomposition",
                "lime_fidelity_stability_and_quality",
            ],
            "no_api_serving": True,
            "no_telemetry": True,
            "no_uploads": True,
            "no_bundle_writes": True,
            "no_retraining_or_tuning": True,
            "no_real_patient_inputs": True,
        },
        "records": per_record,
        "governance": {
            "serving_eligibility": "RESEARCH_ONLY",
            "approved_for_serving": False,
            "clinical_use_authorized": False,
            "gate_pt_p1": "PENDING",
            "gate_pt_p3": "CLOSED",
            "supervisor_signoff_claimed": False,
            "governance_document": DIAGNOSTIC_GOVERNANCE_DOCUMENT_RELATIVE_PATH,
        },
        "limitations": list(DIAGNOSTIC_LIMITATIONS),
    }


# --------------------------------------------------------------------------- #
# Separate CLI (never imported by ai.cli or backend/app)
# --------------------------------------------------------------------------- #


def _redact(message: str, tokens: Sequence[str]) -> str:
    redacted = message
    for token in tokens:
        if not token:
            continue
        redacted = redacted.replace(token, "<local-path>")
        redacted = redacted.replace(token.replace("\\", "/"), "<local-path>")
    return redacted


def _redaction_tokens(args: argparse.Namespace) -> tuple[str, ...]:
    tokens: set[str] = set()
    for name in (
        "bundle_dir",
        "trusted_local_root",
        "authorization",
        "input",
        "signing_key_path",
        "repo_root",
    ):
        value = getattr(args, name, None)
        if value is None:
            continue
        path = Path(value)
        candidates = [str(path)]
        try:
            candidates.append(str(path.resolve()))
        except OSError:
            pass
        # Never redact tiny tokens such as "." (repo-root shorthand): they would
        # replace every punctuation mark in an error message.
        tokens.update(t for t in candidates if len(t) >= 3)
    return tuple(sorted((t for t in tokens if t), key=len, reverse=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ai.diagnostic_inference",
        description=(
            "Bounded OFFLINE diagnostic inference on the single accepted real "
            "Cleveland bundle using explicitly fabricated synthetic records. "
            "Fails closed unless the separate diagnostic scope is independently "
            "ratified and activated. RESEARCH_ONLY; never clinical."
        ),
    )
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--trusted-root", dest="trusted_local_root", type=Path, required=True)
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--operator-confirmation", required=True)
    parser.add_argument(
        "--signing-key-path", type=Path, required=True,
        help=(
            "existing private local HMAC key; required so the interface never "
            "creates or writes a key file itself"
        ),
    )
    parser.add_argument("--repo-root", type=Path, default=REPOSITORY_ROOT)
    parser.add_argument(
        "--no-lime", action="store_true",
        help="skip genuine LIME (no LIME feature weights are then produced)",
    )
    parser.add_argument("--lime-perturbations", type=int, default=None)
    parser.add_argument("--lime-seed", type=int, default=None)
    parser.add_argument(
        "--require-acceptable-lime-quality", action="store_true",
        help="fail closed instead of suppressing low-quality LIME feature weights",
    )
    parser.add_argument(
        "--format", choices=("json",), default="json",
        help="JSON only; no patient-level or path-bearing text rendering",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Return 0 on a verified diagnostic report, 2 on any fail-closed error."""
    args = build_parser().parse_args(argv)
    tokens = _redaction_tokens(args)
    try:
        config_overrides: dict[str, Any] = {}
        if not args.no_lime:
            if args.lime_perturbations is not None:
                config_overrides["num_perturbations"] = int(args.lime_perturbations)
            if args.lime_seed is not None:
                config_overrides["seed"] = int(args.lime_seed)
        elif args.lime_perturbations is not None or args.lime_seed is not None:
            raise DiagnosticIntegrityError(
                "diagnostic_lime_flags_conflict",
                "--no-lime cannot be combined with LIME tuning flags.",
            )
        from ai.packaging import get_or_create_local_signing_key

        if not Path(args.signing_key_path).is_file():
            raise DiagnosticIntegrityError(
                "diagnostic_signing_key_missing",
                "Explicit signing-key path does not name an existing local file.",
            )
        signing_key = get_or_create_local_signing_key(Path(args.signing_key_path))
        payload = run_offline_diagnostics(
            bundle_dir=args.bundle_dir,
            trusted_local_root=args.trusted_local_root,
            authorization_path=args.authorization,
            input_path=args.input,
            operator_confirmation=args.operator_confirmation,
            signing_key=signing_key,
            repo_root=args.repo_root,
            with_lime=not args.no_lime,
            lime_config=None if args.no_lime else LimeConfig(**config_overrides),
            require_acceptable_lime_quality=bool(
                args.require_acceptable_lime_quality
            ),
        )
        print(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False))
        return EXIT_OK
    except Exception as exc:  # noqa: BLE001 - CLI boundary always fails closed
        if isinstance(exc, AiPipelineError):
            error = {
                "code": exc.code,
                "message": _redact(exc.message, tokens),
                "field": exc.field,
            }
        else:
            error = {
                "code": "diagnostic_internal_error",
                "message": (
                    f"Unexpected {type(exc).__name__}; failed closed with no "
                    "diagnostic inference result."
                ),
                "field": None,
            }
        print(
            json.dumps(
                {"status": "FAIL_CLOSED", "error": error},
                indent=2,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return EXIT_FAIL_CLOSED


__all__ = [
    "DIAGNOSTIC_INPUT_SCHEMA_VERSION",
    "DIAGNOSTIC_INTERFACE_VERSION",
    "DIAGNOSTIC_LIMITATIONS",
    "DiagnosticIntegrityError",
    "build_parser",
    "load_diagnostic_input",
    "main",
    "run_offline_diagnostics",
    "verify_accepted_bundle_identity",
    "verify_diagnostic_result",
]


if __name__ == "__main__":
    raise SystemExit(main())
