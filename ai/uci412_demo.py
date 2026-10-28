"""AI-8 — observable, reproducible UCI-412 synthetic research demo.

This module adds **no new training, inference, calibration or explanation
engine**. It is a thin demonstration orchestrator over the already-reviewed
AI-8 implementation in :mod:`ai.uci412_research` and the intake field contract
in :mod:`research.intake.uci412_field_contract`. A maintainer can run one
command and watch the complete source-specific synthetic path execute:

    python -m ai uci412-demo                 # fast smoke budget (default)
    python -m ai uci412-demo --budget full  # full default nested-CV budget

Both budgets are deterministic, fully offline, synthetic-only and
``RESEARCH_ONLY``. Every numeric output carries the marker
``SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE`` and every score the interpretation
``RESEARCH_ONLY_NOT_INDIVIDUAL_CLINICAL_RISK``. The invalid-input stage invokes
the real fail-closed validator; it never prints a hardcoded rejection.
"""
from __future__ import annotations

import shutil
import tempfile
from types import MappingProxyType
from typing import Any, Final, Mapping

from ai.uci412_research import (
    ORIGIN_HELD_OUT_SYNTHETIC_TEST,
    SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE,
    UCI412_PANEL_ID,
    Uci412ResearchGovernanceError,
    Uci412ResearchModelConfig,
    Uci412SyntheticModelResult,
    build_uci412_synthetic_research_model,
    validate_uci412_synthetic_cohort,
)
from ai.errors import ClinicalInputValidationError
from ai.research_routes import build_synthetic_uci412_basic_clinical_cohort
from research.intake.uci412_field_contract import (
    CONTRACT_ID,
    FIELD_ORDER,
    FIELD_VERIFIED_CHANNEL,
    NUMERIC_MEASUREMENTS,
    review_uci412_field_contract,
)

DEMO_COMMAND_SMOKE: Final[str] = "python -m ai uci412-demo"
DEMO_COMMAND_FULL: Final[str] = "python -m ai uci412-demo --budget full"
_VERIFIED: Final[str] = "VERIFIED_REGISTERED_SOURCE_DOMAIN"

# A representative SOURCE-shaped (text-token) synthetic record used to exercise
# the Deliverable D intake field contract. This is distinct from the numeric
# model-input envelopes produced by the cohort builder: it demonstrates the
# future acquisition contract and its no-result guarantee.
_SOURCE_CONTRACT_FEATURES: Final[Mapping[str, Any]] = MappingProxyType(
    {
        "Age": 53,
        "Sex": "Male",
        "BMI": 26.4,
        "DM": 0,
        "HTN": 1,
        "Current Smoker": 0,
        "EX-Smoker": 0,
        "FH": 0,
        "DLP": "N",
        "BP": 128,
        "PR": 78,
        "Typical Chest Pain": 0,
        "Atypical": "N",
        "Nonanginal": "N",
        "Exertional CP": "Y",
        "Dyspnea": "N",
    }
)


def _stage(stage: str, status: str, detail: Mapping[str, Any]) -> dict[str, Any]:
    return {"stage": stage, "status": status, "detail": dict(detail)}


def _build_source_contract_payload() -> dict[str, Any]:
    """Build a valid synthetic SOURCE-shaped payload for the intake contract."""
    return {
        "contract_version": CONTRACT_ID,
        "synthetic": True,
        "source": {"source_id": "UCI-412", "dataset_id": "DA-A1", "track": "A"},
        "feature_order": list(FIELD_ORDER),
        "features": dict(_SOURCE_CONTRACT_FEATURES),
        "units": {field: unit for field, (unit, _lo, _hi) in NUMERIC_MEASUREMENTS.items()},
        "missing_reasons": {},
        "acquisition_sources": {
            field: {
                "channel": FIELD_VERIFIED_CHANNEL[field],
                "mapping_status": _VERIFIED,
            }
            for field in FIELD_ORDER
        },
    }


def _demonstrate_invalid_input() -> dict[str, Any]:
    """Genuinely invoke the strict validator on a malformed record.

    A good synthetic fixture is mutated by dropping its explicit source
    declaration — exactly the case that previously failed open. The real
    validator must reject it; the captured code/message is reported, never a
    hardcoded string.
    """
    import copy

    records, labels = build_synthetic_uci412_basic_clinical_cohort(24, seed=20261028)
    bad_records = copy.deepcopy(records)
    bad_records[0]["context"].pop("source")
    try:
        validate_uci412_synthetic_cohort(bad_records, labels)
    except Uci412ResearchGovernanceError as exc:
        return {
            "rejected": True,
            "exception_type": type(exc).__name__,
            "error_code": exc.code,
            "error_message": exc.message,
            "mutation": "removed context.source from an otherwise valid synthetic record",
        }
    except ClinicalInputValidationError as exc:  # pragma: no cover - structural path
        return {
            "rejected": True,
            "exception_type": type(exc).__name__,
            "error_code": exc.code,
            "error_message": exc.message,
            "mutation": "removed context.source from an otherwise valid synthetic record",
        }
    # A validator that accepted the malformed record would be a security bug.
    raise Uci412ResearchGovernanceError(
        "demo_invalid_input_was_not_rejected",
        "The demo's invalid-input record was accepted; strict validation is broken.",
    )


def _config_for_budget(budget: str, work_root: Any) -> Uci412ResearchModelConfig:
    if budget == "smoke":
        return Uci412ResearchModelConfig.fast(package_bundle=True, work_root=work_root)
    if budget == "full":
        return Uci412ResearchModelConfig(package_bundle=True, work_root=work_root)
    raise ValueError(f"Unknown demo budget '{budget}'; choose 'smoke' or 'full'.")


def run_uci412_research_demo(
    *, budget: str = "smoke", work_dir: Any = None
) -> dict[str, Any]:
    """Execute the full observable UCI-412 synthetic research demonstration.

    Returns a JSON-serializable payload. When ``work_dir`` is None an isolated
    private temporary directory is created and removed afterwards; when
    provided, generated artifacts are retained under it and the caller owns the
    directory. No absolute filesystem path is included in the payload.
    """
    owns_temp = work_dir is None
    base_dir = (
        # mirrors the established CLI demo lifecycle for private artifacts
        tempfile.mkdtemp(prefix="cardioassist_ai8_uci412_demo_")
        if owns_temp
        else str(work_dir)
    )
    from pathlib import Path

    work_root = Path(base_dir)
    stages: list[dict[str, Any]] = []
    try:
        config = _config_for_budget(budget, work_root)

        # Stage 1 — deterministic synthetic cohorts (observed independently).
        dev_records, _ = build_synthetic_uci412_basic_clinical_cohort(
            config.n_development, seed=config.seed
        )
        test_records, test_labels = build_synthetic_uci412_basic_clinical_cohort(
            config.n_test, seed=config.seed + 1
        )
        stages.append(
            _stage(
                "1_synthetic_cohort_generation",
                "PASSED",
                {
                    "development_n": config.n_development,
                    "held_out_test_n": config.n_test,
                    "development_seed": config.seed,
                    "held_out_test_seed": config.seed + 1,
                    "evidence_marker": SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE,
                },
            )
        )

        # Stage 2 — route and exact 16-feature panel binding.
        result: Uci412SyntheticModelResult = build_uci412_synthetic_research_model(
            config
        )
        report = result.report
        stages.append(
            _stage(
                "2_route_and_panel_binding",
                "PASSED",
                {
                    "route_id": result.descriptor.route_id,
                    "panel_id": UCI412_PANEL_ID,
                    "ordered_feature_names": report.feature_contract["ordered_feature_names"],
                    "feature_count": report.feature_contract["feature_count"],
                    "panel_contract_sha256": report.feature_contract["contract_sha256"],
                },
            )
        )

        # Stage 3 — genuine validation through both contract layers.
        intake_review = review_uci412_field_contract(_build_source_contract_payload())
        X_test, _y_test, panel = validate_uci412_synthetic_cohort(
            test_records, test_labels
        )
        stages.append(
            _stage(
                "3_feature_contract_validation",
                "PASSED",
                {
                    "intake_contract_id": CONTRACT_ID,
                    "intake_review_status": intake_review.review_status,
                    "intake_result_state": intake_review.result_state,
                    "cad_probability_computed": intake_review.to_dict()[
                        "cad_probability_computed"
                    ],
                    "panel_validation_matrix_shape": list(X_test.shape),
                    "panel_id": panel.panel_id,
                },
            )
        )

        # Stages 4-7 — model identity, raw/calibrated scores, provenance.
        offline = report.offline_prediction
        stages.append(
            _stage(
                "4_research_model_identity",
                "PASSED",
                {
                    "model_id": report.model_binding["model_id"],
                    "model_version": report.model_binding["model_version"],
                    "selected_model_family": report.model_binding["selected_model_family"],
                    "execution_profile": report.model_binding["execution_profile"],
                    "preprocessing_contract": report.model_binding[
                        "preprocessing_contract"
                    ],
                },
            )
        )
        stages.append(
            _stage(
                "5_raw_model_score",
                "PASSED",
                {
                    "raw_model_score": offline["raw_model_score"],
                    "explained_scale": report.shap_quality["scale"],
                },
            )
        )
        stages.append(
            _stage(
                "6_calibrated_research_score",
                "PASSED",
                {
                    "calibrated_research_score": offline["calibrated_research_score"],
                    "calibrated_log_odds": offline["calibrated_log_odds"],
                    "score_interpretation": offline["score_interpretation"],
                    "threshold_clinically_approved": False,
                },
            )
        )
        stages.append(
            _stage(
                "7_prediction_provenance_and_target",
                "PASSED",
                {
                    "target_id": report.target_contract["target_id"],
                    "threshold_boundary": report.target_contract["threshold_boundary"],
                    "target_definition_sha256": report.target_contract[
                        "target_definition_sha256"
                    ],
                    "serving_eligibility": report.eligibility["serving_eligibility"],
                    "approved_for_serving": report.eligibility["approved_for_serving"],
                    "clinical_use_authorized": report.eligibility[
                        "clinical_use_authorized"
                    ],
                },
            )
        )

        # Stages 8-9 — genuine model-based SHAP and LIME diagnostics.
        shap = report.shap_quality
        lime = report.lime_quality
        stages.append(
            _stage(
                "8_shap_explanation",
                "PASSED",
                {
                    "explained_quantity": shap["explained_quantity"],
                    "scale": shap["scale"],
                    "sum_check_passed": shap["sum_check_passed"],
                    "max_abs_discrepancy": shap["max_abs_discrepancy"],
                    "additive_on_calibrated_probability": shap[
                        "additive_on_calibrated_probability"
                    ],
                    "attribution_count": shap["attribution_count"],
                },
            )
        )
        stages.append(
            _stage(
                "9_lime_explanation",
                "PASSED",
                {
                    "quality_status": lime["quality_status"],
                    "is_reliable_for_interpretation": lime[
                        "is_reliable_for_interpretation"
                    ],
                    "weighted_r2": lime["weighted_r2"],
                    "holdout_weighted_r2": lime["holdout_weighted_r2"],
                    "local_fidelity_abs_error": lime["local_fidelity_abs_error"],
                    "stability_assessed": lime["stability_assessed"],
                },
            )
        )

        # Stage 10 — authenticated RESEARCH_ONLY bundle verification.
        bundle = report.bundle_binding
        stages.append(
            _stage(
                "10_bundle_verification",
                "PASSED",
                {
                    "bundle_logical_name": bundle["bundle_logical_name"],
                    "producer_authenticated": bundle["producer_authenticated"],
                    "safe_for_pickle_deserialization": bundle[
                        "safe_for_pickle_deserialization"
                    ],
                    "serving_eligibility": bundle["serving_eligibility"],
                    "approved_for_serving": bundle["approved_for_serving"],
                    "clinical_use_authorized": bundle["clinical_use_authorized"],
                    "manifest_pooled_cohorts": bundle["manifest_pooled_cohorts"],
                    "verified_file_count": len(bundle["verified_file_hashes"]),
                    "attestation_scheme": bundle["attestation_scheme"],
                },
            )
        )

        # Stage 11 — genuine invalid-input rejection through the real guard.
        invalid = _demonstrate_invalid_input()
        stages.append(_stage("11_invalid_input_rejection", "PASSED", invalid))

        # Stage 12 — origin-labelled held-out evidence (aggregate, separate).
        held_out = report.metrics_by_origin[ORIGIN_HELD_OUT_SYNTHETIC_TEST]
        held_metrics = held_out["metrics"]
        stages.append(
            _stage(
                "12_held_out_synthetic_evidence",
                "PASSED",
                {
                    "evaluation_scope": held_metrics["evaluation_scope"],
                    "roc_auc": held_metrics["discrimination"]["roc_auc"],
                    "average_precision": held_metrics["discrimination"][
                        "average_precision"
                    ],
                    "brier_score": held_metrics["proper_scoring_and_calibration"][
                        "brier_score"
                    ],
                    "evidence_marker": held_out["evidence_marker"],
                    "not_external_clinical_validation": True,
                },
            )
        )

        succeeded = [s["stage"] for s in stages if s["status"] == "PASSED"]
        payload: dict[str, Any] = {
            "demo": "ai8_uci412_synthetic_research_demo",
            "command": DEMO_COMMAND_FULL if budget == "full" else DEMO_COMMAND_SMOKE,
            "status": "PASSED",
            "budget": budget,
            "evidence_marker": SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE,
            "research_only_interpretation": "RESEARCH_ONLY_NOT_INDIVIDUAL_CLINICAL_RISK",
            "route_id": result.descriptor.route_id,
            "panel_id": UCI412_PANEL_ID,
            "report_deterministic_sha256": report.deterministic_sha256,
            "stage_results": stages,
            "summary": {
                "stages_total": len(stages),
                "stages_succeeded": len(succeeded),
                "succeeded_stages": succeeded,
                "stages_failed": 0,
            },
            "invalid_input_demo": invalid,
            "limitations": list(report.limitations),
            "reproduction": {
                "smoke_command": DEMO_COMMAND_SMOKE,
                "full_command": DEMO_COMMAND_FULL,
                "config_seed": config.seed,
                "held_out_seed": config.seed + 1,
                "work_artifacts_retained": not owns_temp,
            },
        }
        return payload
    finally:
        if owns_temp:
            shutil.rmtree(base_dir, ignore_errors=True)


def render_uci412_demo_text(payload: Mapping[str, Any]) -> str:
    """Render the machine-readable demo payload as a concise console report."""
    lines: list[str] = []
    lines.append("=" * 78)
    lines.append("CardioAssist AI-8 — UCI-412 synthetic research demo")
    lines.append("=" * 78)
    lines.append(f"Command            : {payload['command']}  (budget={payload['budget']})")
    lines.append(f"Overall status     : {payload['status']}")
    lines.append(f"Route / panel      : {payload['route_id']} / {payload['panel_id']}")
    lines.append(f"Evidence marker    : {payload['evidence_marker']}")
    lines.append(f"Score meaning      : {payload['research_only_interpretation']}")
    lines.append(f"Report SHA-256     : {payload['report_deterministic_sha256']}")
    lines.append("-" * 78)
    for stage in payload["stage_results"]:
        lines.append(f"[{stage['status']}] {stage['stage']}")
        for key, value in stage["detail"].items():
            rendered = value
            if isinstance(value, float):
                rendered = f"{value:.6f}"
            lines.append(f"    - {key}: {rendered}")
    lines.append("-" * 78)
    summary = payload["summary"]
    lines.append(
        f"Summary: {summary['stages_succeeded']}/{summary['stages_total']} stages succeeded"
    )
    invalid = payload["invalid_input_demo"]
    lines.append(
        "Invalid input genuinely rejected: "
        f"{invalid['exception_type']} ({invalid['error_code']})"
    )
    lines.append("All data are synthetic fixtures; this is not clinical evidence and")
    lines.append("not an individual patient's medical risk or external validation.")
    lines.append("=" * 78)
    return "\n".join(lines)
