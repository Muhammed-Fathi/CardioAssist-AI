"""Offline RESEARCH_ONLY inference interface for Track A CAD tabular models.

Architectural & governance boundaries:
- Strictly offline research tooling: NEVER imported by ``backend/app/`` and
  NEVER exposed over FastAPI ``/v1`` routes (``MOCK_SYNTHETIC`` remains the sole
  runtime HTTP provider per M1c).
- Calls :func:`ai.packaging.verify_research_bundle` before ``joblib.load`` so
  any modified byte, symlink, or tampered feature order fails closed prior to
  deserialization.
- Returns score, out-of-fold calibration metadata, fold-ensemble & missingness
  uncertainty, verified-additive model-faithful SHAP attributions, and explicit
  limitations. Never claims a clinically reliable individual CAD risk.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final, Mapping

import joblib
import numpy as np

from ai.calibration import OofLogisticCalibrator, compute_instance_uncertainty
from ai.errors import BundleIntegrityError
from ai.explainability import (
    FaithfulShapExplanation,
    ShapBackgroundReference,
    explain_clinical_instance,
)
from ai.packaging import (
    CALIBRATION_FILENAME,
    MODEL_FILENAME,
    PREPROCESSING_FILENAME,
    SHAP_BG_FILENAME,
    VerifiedBundleDescriptor,
    verify_research_bundle,
)
from ai.panels import ResearchPanelContract, validate_clinical_record
from ai.preprocessing import FoldSafeClinicalPreprocessor
from ai.training import FoldEnsembleMember

MANDATORY_LIMITATIONS: Final[tuple[str, ...]] = (
    "RESEARCH_ONLY output: not approved for clinical diagnosis, triage, treatment, or patient self-assessment.",
    "Do NOT interpret calibrated_research_score as a clinically reliable individual CAD risk; "
    "formal Gate PT (P-1/P-3), external transportability validation, and clinician sign-off (P-4) remain required.",
    "Target construct is cross-sectional angiographic CAD presence in a referral cohort—NEVER a 30-day or future cardiovascular event horizon.",
    "Track B wearable/monitoring observations are not valid predictors for this model and are rejected.",
)


@dataclass(frozen=True, slots=True)
class ResearchPredictionResult:
    """Immutable output of one offline RESEARCH_ONLY CAD prediction."""

    model_id: str
    model_version: str
    protocol_id: str
    model_family: str
    panel_id: str
    panel_contract_sha256: str
    raw_model_score: float
    calibrated_research_score: float
    exploratory_threshold: float
    exploratory_above_threshold_flag: bool
    uncertainty: Mapping[str, Any]
    explanation: FaithfulShapExplanation
    verified_artifact_hashes: Mapping[str, str]
    limitations: tuple[str, ...]

    @property
    def serving_eligibility(self) -> str:
        return "RESEARCH_ONLY"

    @property
    def approved_for_serving(self) -> bool:
        return False

    @property
    def clinical_use_authorized(self) -> bool:
        return False

    @property
    def clinically_reliable_individual_cad_risk(self) -> bool:
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "protocol_id": self.protocol_id,
            "model_family": self.model_family,
            "panel_id": self.panel_id,
            "panel_contract_sha256": self.panel_contract_sha256,
            "prediction": {
                "raw_model_score": self.raw_model_score,
                "calibrated_research_score": self.calibrated_research_score,
                "score_interpretation": "RESEARCH_ONLY_NOT_INDIVIDUAL_CLINICAL_RISK",
                "exploratory_threshold": self.exploratory_threshold,
                "exploratory_above_threshold_flag": self.exploratory_above_threshold_flag,
            },
            "uncertainty": dict(self.uncertainty),
            "explanation": self.explanation.to_dict(),
            "governance": {
                "serving_eligibility": self.serving_eligibility,
                "approved_for_serving": self.approved_for_serving,
                "clinical_use_authorized": self.clinical_use_authorized,
                "clinically_reliable_individual_cad_risk": (
                    self.clinically_reliable_individual_cad_risk
                ),
                "requires_clinician_and_gate_pt_validation": True,
            },
            "provenance": {
                "verified_artifact_hashes": dict(self.verified_artifact_hashes),
            },
            "limitations": list(self.limitations),
        }


def _positive_proba_single(estimator: Any, z_row: np.ndarray) -> float:
    probs = estimator.predict_proba(z_row.reshape(1, -1))
    pos_idx = list(estimator.classes_).index(1)
    return float(probs[0, pos_idx])


class ResearchCadPredictor:
    """Offline RESEARCH_ONLY predictor loaded exclusively from a verified bundle."""

    def __init__(
        self,
        *,
        descriptor: VerifiedBundleDescriptor,
        preprocessor: FoldSafeClinicalPreprocessor,
        estimator: Any,
        calibrator: OofLogisticCalibrator,
        shap_background: ShapBackgroundReference,
        fold_ensemble: tuple[FoldEnsembleMember, ...],
    ) -> None:
        self._descriptor = descriptor
        self._preprocessor = preprocessor
        self._estimator = estimator
        self._calibrator = calibrator
        self._shap_background = shap_background
        self._fold_ensemble = fold_ensemble

    @property
    def panel(self) -> ResearchPanelContract:
        return self._descriptor.panel

    @property
    def model_id(self) -> str:
        return str(self._descriptor.manifest["model"]["model_id"])

    @property
    def model_version(self) -> str:
        return str(self._descriptor.manifest["model"]["model_version"])

    @property
    def protocol_id(self) -> str:
        return str(self._descriptor.manifest["model"]["protocol_id"])

    @property
    def model_family(self) -> str:
        return str(self._descriptor.manifest["model"]["selected_model_family"])

    @classmethod
    def from_verified_bundle(cls, bundle_dir: Path) -> "ResearchCadPredictor":
        """Verify bundle integrity first, then load JSON contracts and model container."""
        verified = verify_research_bundle(Path(bundle_dir))
        root = verified.bundle_dir

        prep_json = json.loads((root / PREPROCESSING_FILENAME).read_text(encoding="utf-8"))
        preprocessor = FoldSafeClinicalPreprocessor.from_json_dict(
            prep_json, expected_panel=verified.panel
        )

        cal_json = json.loads((root / CALIBRATION_FILENAME).read_text(encoding="utf-8"))
        calibrator = OofLogisticCalibrator.from_json_dict(cal_json)

        bg_json = json.loads((root / SHAP_BG_FILENAME).read_text(encoding="utf-8"))
        shap_bg = ShapBackgroundReference.from_json_dict(
            bg_json, preprocessor=preprocessor
        )

        container = joblib.load(root / MODEL_FILENAME)
        if not isinstance(container, Mapping):
            raise BundleIntegrityError(
                "invalid_model_container",
                "Deserialized model.joblib container has unexpected structure.",
            )
        declared_family = str(verified.manifest["model"]["selected_model_family"])
        if (
            container.get("selected_model_family") != declared_family
            or calibrator.model_family != declared_family
        ):
            raise BundleIntegrityError(
                "model_family_container_mismatch",
                "Model family differs across manifest, model container, and calibrator.",
            )

        fold_members: list[FoldEnsembleMember] = []
        for entry in container.get("fold_ensemble", ()):
            member_prep = FoldSafeClinicalPreprocessor.from_json_dict(
                entry["preprocessor_json"], expected_panel=verified.panel
            )
            fold_members.append(
                FoldEnsembleMember(
                    fold_index=int(entry["fold_index"]),
                    model_family=str(entry["model_family"]),
                    preprocessor=member_prep,
                    estimator=entry["estimator"],
                )
            )
        if not fold_members:
            raise BundleIntegrityError(
                "missing_fold_ensemble",
                "Verified research bundle must contain >= 1 outer-fold ensemble member.",
            )

        return cls(
            descriptor=verified,
            preprocessor=preprocessor,
            estimator=container["estimator"],
            calibrator=calibrator,
            shap_background=shap_bg,
            fold_ensemble=tuple(fold_members),
        )

    def predict_research_only(
        self,
        payload: Mapping[str, Any],
        *,
        exploratory_threshold: float = 0.5,
    ) -> ResearchPredictionResult:
        """Validate clinical/lab record and compute RESEARCH_ONLY score, uncertainty & SHAP."""
        validated = validate_clinical_record(
            payload, self.panel, require_synthetic=True
        )
        x_row = validated.as_row_array()
        z_row = self._preprocessor.transform(x_row)[0]

        raw_score = _positive_proba_single(self._estimator, z_row)
        cal_score = float(self._calibrator.calibrate(raw_score))

        fold_cal_scores: list[float] = []
        for member in self._fold_ensemble:
            z_fold = member.preprocessor.transform(x_row)[0]
            p_fold_raw = _positive_proba_single(member.estimator, z_fold)
            fold_cal_scores.append(float(self._calibrator.calibrate(p_fold_raw)))

        uncertainty = compute_instance_uncertainty(
            fold_cal_scores,
            missing_fields_with_reason=validated.missing_fields_with_reason,
            total_fields=len(self.panel.fields),
            development_prevalence=self._calibrator.development_prevalence,
        )

        missing_set = frozenset(name for name, _ in validated.missing_fields_with_reason)
        explanation = explain_clinical_instance(
            model_family=self.model_family,
            estimator=self._estimator,
            preprocessor=self._preprocessor,
            panel=self.panel,
            background=self._shap_background,
            z_row=z_row,
            missing_feature_names=missing_set,
        )

        dynamic_limitations = list(MANDATORY_LIMITATIONS)
        if not validated.stage_complete:
            missing_desc = ", ".join(
                f"{name} ({reason})"
                for name, reason in validated.missing_fields_with_reason
            )
            dynamic_limitations.append(
                f"Incomplete optional measurement stage: {missing_desc} imputed via training-fold statistics."
            )
        if self.panel.governance_status == "PROPOSED_SYNTHETIC_ONLY_GATE_PT_REQUIRED":
            dynamic_limitations.append(
                f"Panel '{self.panel.panel_id}' includes proposed routine laboratory biomarkers "
                "awaiting Gate PT (P-3) pre-angiography timing verification."
            )

        return ResearchPredictionResult(
            model_id=self.model_id,
            model_version=self.model_version,
            protocol_id=self.protocol_id,
            model_family=self.model_family,
            panel_id=self.panel.panel_id,
            panel_contract_sha256=self.panel.contract_sha256,
            raw_model_score=raw_score,
            calibrated_research_score=cal_score,
            exploratory_threshold=float(exploratory_threshold),
            exploratory_above_threshold_flag=bool(cal_score >= exploratory_threshold),
            uncertainty=MappingProxyType(dict(uncertainty)),
            explanation=explanation,
            verified_artifact_hashes=self._descriptor.verified_files,
            limitations=tuple(dynamic_limitations),
        )
