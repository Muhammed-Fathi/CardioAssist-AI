"""AI-10.1 synthetic-only demonstration of the existing locked external evaluator.

No real dataset, patient input, Hungary artifact, endpoint, or clinician-facing
provider is read here. The existing ExternalEvaluationLedger is the ONLY
single-shot authority for this fabricated exercise. The ledger is an engineering
safeguard, not evidence of participant independence or an ethical approval.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Final, Sequence

import numpy as np

from ai.errors import CohortGovernanceError
from ai.panels import DA_A2_RESTING_PANEL
from ai.research_routes import (
    OP_SYNTHETIC_EXTERNAL_EVALUATION,
    OP_SYNTHETIC_TRAINING,
    assert_route_eligible,
    build_synthetic_uci45_resting_cohort,
)
from ai.training import (
    ResearchTrainingConfig,
    evaluate_locked_external_cohort,
    train_research_model,
)

SCHEMA: Final[str] = "cardioassist.ai.synthetic_locked_site/v1"
EVIDENCE: Final[str] = "SYNTHETIC_TRANSPORT_TEST_NOT_EXTERNAL_VALIDATION"
PLAN_REF: Final[str] = "CAI-AI10.1-FABRICATED-LOCKED-SITE-V1"
PANEL_ID: Final[str] = "da_a2_resting_v1"
TARGET_ID: Final[str] = "t1.uci45.angiographic_cad_gt50.v1"
SYNTHETIC_CONTEXT: Final[dict[str, Any]] = {
    "track": "A", "source": "structured_synthetic_research", "synthetic": True,
}


def _sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"),
                   ensure_ascii=True, allow_nan=False).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class SyntheticLockedSitePlan:
    """Fixed versioned synthetic experiment definition, not a clinical protocol."""

    reference: str = PLAN_REF
    seed: int = 20261118
    n_development: int = 96
    n_external: int = 48
    bootstrap_resamples: int = 32
    panel_id: str = PANEL_ID
    panel_sha256: str = DA_A2_RESTING_PANEL.contract_sha256
    target_id: str = TARGET_ID

    def __post_init__(self) -> None:
        if self.reference != PLAN_REF or self.panel_id != PANEL_ID:
            raise ValueError("AI-10.1 synthetic protocol and panel are fixed.")
        if self.panel_sha256 != DA_A2_RESTING_PANEL.contract_sha256 or self.target_id != TARGET_ID:
            raise ValueError("Registered synthetic panel or endpoint mismatch.")
        if type(self.seed) is not int or not 1 <= self.seed < 2**31 - 20000:
            raise ValueError("Invalid bounded synthetic seed.")
        if type(self.n_development) is not int or not 60 <= self.n_development <= 400:
            raise ValueError("Invalid synthetic development cohort size.")
        if type(self.n_external) is not int or not 1 <= self.n_external <= 400:
            raise ValueError("Invalid synthetic assessment cohort size.")
        if type(self.bootstrap_resamples) is not int or not 16 <= self.bootstrap_resamples <= 250:
            raise ValueError("Invalid bootstrap resample count.")

    @property
    def sha256(self) -> str:
        return _sha(asdict(self))


def validate_fake_identities(
    development_ids: Sequence[str], external_ids: Sequence[str],
) -> dict[str, Any]:
    """Only validate locally invented identity strings: not real overlap evidence."""
    for ids in (development_ids, external_ids):
        if not ids or any(type(s) is not str or not s.startswith("ai10_fake_") for s in ids):
            raise CohortGovernanceError(
                "ai10_untrusted_fixture_ids", "Only generated synthetic fixture IDs are permitted."
            )
        if len(ids) != len(set(ids)):
            raise CohortGovernanceError(
                "ai10_duplicate_fixture_id", "Repeated synthetic fixture identity."
            )
    if set(development_ids).intersection(external_ids):
        raise CohortGovernanceError(
            "ai10_overlapping_fixture_id", "Synthetic development/test identity overlap."
        )
    return {
        "status": "GENERATED_IDS_NONOVERLAPPING_NOT_REAL_PATIENT_INDEPENDENCE",
        "development_count": len(development_ids),
        "external_count": len(external_ids),
        "development_sha256": _sha(list(development_ids)),
        "external_sha256": _sha(list(external_ids)),
        "overlap_count": 0,
    }


def _verify_registered_route() -> None:
    for operation in (OP_SYNTHETIC_TRAINING, OP_SYNTHETIC_EXTERNAL_EVALUATION):
        route = assert_route_eligible(
            dataset_id="DA-A2", panel_id=PANEL_ID, operation=operation,
            source_family="UCI-45", declared_input_context=SYNTHETIC_CONTEXT,
        )
        if route.route_id != PANEL_ID or route.panel_contract_sha256 != DA_A2_RESTING_PANEL.contract_sha256:
            raise CohortGovernanceError(
                "ai10_route_binding_mismatch", "Route or panel digest has drifted."
            )


def _fabricate(plan: SyntheticLockedSitePlan) -> tuple[Any, Any, Any, Any, dict[str, Any]]:
    dev, y_dev = build_synthetic_uci45_resting_cohort(
        plan.n_development, seed=plan.seed,
    )
    ext, y_ext = build_synthetic_uci45_resting_cohort(
        plan.n_external, seed=plan.seed + 29,
    )
    # Invented covariate shift only; labels are never changed or re-fitted.
    for record in ext:
        features = record["features"]
        features["age"] = min(83.0, float(features["age"]) + 4.0)
        features["trestbps"] = min(206.0, float(features["trestbps"]) + 7.0)
    identity = validate_fake_identities(
        [f"ai10_fake_dev_{plan.seed}_{i:05d}" for i in range(len(dev))],
        [f"ai10_fake_ext_{plan.seed}_{i:05d}" for i in range(len(ext))],
    )
    return dev, y_dev, ext, y_ext, identity


def _insufficient(plan: SyntheticLockedSitePlan, reason: str, *,
                  positives: int = 0, negatives: int = 0) -> dict[str, Any]:
    report = {
        "schema_version": SCHEMA,
        "status": "INSUFFICIENT_EVIDENCE",
        "evidence_class": EVIDENCE,
        "plan_sha256": plan.sha256,
        "n_external": plan.n_external,
        "n_positive": positives, "n_negative": negatives,
        "reason": reason, "ledger_slot_consumed": False,
        "real_data_execution_authorized": False,
        "clinical_use_authorized": False,
        "real_external_validation_performed": False,
    }
    report["sha256"] = _sha(report)
    return report


def run_ai10_synthetic_locked_site(
    *, ledger_path: Path, plan: SyntheticLockedSitePlan | None = None,
    expected_plan_sha256: str | None = None,
) -> dict[str, Any]:
    """Generate fake records, train once on development, evaluate once on test.

    Does not accept caller-provided records or real-source paths. The existing
    protected ExternalEvaluationLedger prevents duplicate assessment consumption.
    """
    plan = plan or SyntheticLockedSitePlan()
    if expected_plan_sha256 is not None and expected_plan_sha256 != plan.sha256:
        raise CohortGovernanceError(
            "ai10_plan_digest_mismatch", "The versioned study plan digest changed."
        )
    if ledger_path is None:
        raise CohortGovernanceError(
            "ai10_ledger_path_required", "Single-shot local ledger path is mandatory."
        )
    _verify_registered_route()
    if plan.n_external < 16:
        return _insufficient(plan, "too_few_synthetic_assessment_rows")

    dev, y_dev, ext, y_ext, identity = _fabricate(plan)
    positives = int(np.sum(np.asarray(y_ext) == 1))
    negatives = len(y_ext) - positives
    if min(positives, negatives) < 8:
        return _insufficient(
            plan, "too_few_synthetic_assessment_events_per_class",
            positives=positives, negatives=negatives,
        )
    cfg = ResearchTrainingConfig(
        protocol_id=PLAN_REF, outer_folds=3, inner_folds=3,
        repeat_seeds=(plan.seed,), shuffle_control_seeds=(plan.seed + 10001,),
        lr_c_grid=(0.1, 1.0), rf_max_depths=(3,),
        rf_min_samples_leaf=(5,), rf_n_estimators=20,
        bootstrap_resamples=plan.bootstrap_resamples,
        shap_max_background_samples=24,
    )
    run = train_research_model(
        dev, y_dev, DA_A2_RESTING_PANEL,
        model_id="ai10_fabricated_dev_model_v1",
        development_cohort_id=f"synthetic_ai10_dev_{plan.seed}",
        development_dataset_id="DA-A2", synthetic_data_confirmed=True,
        config=cfg,
    )
    if not run.synthetic_only or run.panel.contract_sha256 != plan.panel_sha256:
        raise CohortGovernanceError(
            "ai10_model_binding_mismatch", "Only the verified synthetic training route is admitted."
        )
    binding = {
        "model_id": run.model_id, "model_version": run.model_version,
        "protocol_id": run.protocol_id,
        "panel_sha256": run.panel.contract_sha256,
        "selected_family": run.selected_model_family,
        "preprocessor_sha256": run.preprocessor.state_sha256,
        "calibrator_sha256": run.calibrator.state_sha256,
    }
    before = _sha(binding)
    # Reuse the EXISTING two-phase atomic ledger, calibration and metric engine.
    result = evaluate_locked_external_cohort(
        run, ext, y_ext,
        external_cohort_id=f"synthetic_ai10_external_{plan.seed}",
        external_dataset_id="DA-A2", synthetic_data_confirmed=True,
        one_shot_ledger_path=Path(ledger_path),
        seed=plan.seed + 400, n_bootstrap=plan.bootstrap_resamples,
    )
    receipt = result.get("one_shot_ledger_receipt")
    if (not result.get("one_shot_enforced_by_ledger") or
            not isinstance(receipt, dict) or receipt.get("status") != "COMPLETED"):
        raise CohortGovernanceError(
            "ai10_ledger_not_completed", "Protected single-shot evaluation not completed."
        )
    if _sha({
        "model_id": run.model_id, "model_version": run.model_version,
        "protocol_id": run.protocol_id, "panel_sha256": run.panel.contract_sha256,
        "selected_family": run.selected_model_family,
        "preprocessor_sha256": run.preprocessor.state_sha256,
        "calibrator_sha256": run.calibrator.state_sha256,
    }) != before:
        raise CohortGovernanceError(
            "ai10_model_metadata_changed", "Frozen binding changed during evaluation."
        )
    unc = result["uncalibrated_transport_metrics"]
    cal = result["locked_transport_metrics"]
    report = {
        "schema_version": SCHEMA,
        "status": "SYNTHETIC_LOCKED_SITE_EXERCISE_COMPLETE",
        "evidence_class": EVIDENCE,
        "plan_reference": plan.reference, "plan_sha256": plan.sha256,
        "target_id": plan.target_id, "panel_id": plan.panel_id,
        "panel_sha256": plan.panel_sha256,
        "seed": plan.seed, "n_development": plan.n_development,
        "n_external": plan.n_external,
        "n_positive": positives, "n_negative": negatives,
        "fabricated_identity_check": identity,
        "invented_site_shift": "age +4 years and resting BP +7 mmHg (bounded)",
        "model_metadata_binding_sha256": before,
        "selected_model_family": run.selected_model_family,
        "ledger_status": "COMPLETED", "ledger_slot_consumed": True,
        "model_tuned_on_external": False,
        "uncalibrated_roc_auc": unc["discrimination"]["roc_auc"],
        "uncalibrated_brier_score": unc["proper_scoring_and_calibration"]["brier_score"],
        "transport_calibrated_roc_auc": cal["discrimination"]["roc_auc"],
        "transport_calibrated_brier_score": cal["proper_scoring_and_calibration"]["brier_score"],
        "real_hungary_accessed": False,
        "real_data_execution_authorized": False,
        "clinical_use_authorized": False,
        "real_external_validation_performed": False,
        "limitations": [
            "All individuals, labels and site differences are fabricated.",
            "Local fixture identities do NOT establish true person-level independence.",
            "A one-shot ledger is not a signed study approval or an authenticated fitted model.",
            "Metadata hash is not an estimator-weights authentication digest.",
            "No clinical transportability, discrimination or calibration claim follows.",
        ],
    }
    report["sha256"] = _sha(report)
    return report
