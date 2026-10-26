"""Offline RESEARCH_ONLY inference interface for Track A CAD tabular models.

Architectural, security & scientific boundaries:
- Strictly offline research tooling: NEVER imported by ``backend/app/`` and
  NEVER exposed over FastAPI ``/v1`` routes (``MOCK_SYNTHETIC`` remains the sole
  runtime HTTP provider per M1c).
- Calls :func:`ai.packaging.verify_trusted_local_bundle` BEFORE ``joblib.load``,
  requiring explicit containment in ``trusted_local_root``, strict ``0600``/``0700``
  local ownership/permissions, SHA-256 digest consistency, AND valid local
  ``HMAC-SHA256`` producer authentication.
- Explicitly distinguishes ``raw_model_score``, ``raw_model_log_odds``,
  ``calibrated_research_score``, ``calibrated_log_odds``, and the exact SHAP
  target quantity & mathematical scale—never presenting raw-model or log-odds
  SHAP attributions as additive decompositions of calibrated probability.
- Summarizes outer-fold score spread using each outer fold's own compatible
  training-fold calibrator as *descriptive fold-model dispersion*, never as
  validated patient-specific epistemic uncertainty.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Final, Mapping, Sequence

import joblib
import numpy as np
from scipy.special import expit

from ai.calibration import (
    OofLogisticCalibrator,
    compute_fold_prediction_dispersion,
    safe_clipped_logit,
)
from ai.errors import BundleIntegrityError, ExplainabilityIntegrityError
from ai.explainability import (
    ADDITIVITY_TOLERANCE,
    FaithfulShapExplanation,
    ShapBackgroundReference,
    explain_clinical_instance,
)
from ai.lime_explainability import (
    DEFAULT_LIME_STABILITY_SEEDS,
    FaithfulLimeExplanation,
    LimeConfig,
    LimeStabilityReport,
    assert_comparable_explanation_scales,
    explain_clinical_instance_lime_certified,
)
from ai.lime_quality import (
    LimeQualityPolicy,
    require_acceptable_lime_quality,
)
from ai.packaging import (
    CALIBRATION_FILENAME,
    MODEL_FILENAME,
    PREPROCESSING_FILENAME,
    SHAP_BG_FILENAME,
    VerifiedBundleDescriptor,
    verify_trusted_local_bundle,
)
from ai.panels import ResearchPanelContract, validate_clinical_record
from ai.preprocessing import FoldSafeClinicalPreprocessor
from ai.training import (
    CLEVELAND_D047_RF_SPACE_WIDTH,
    EXECUTION_PROFILE_AI1_GENERIC_V1,
    EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1,
    FoldEnsembleMember,
    _d047_project_background_to_rf_space,
    _d047_rf_column_to_raw_feature,
    _estimator_input_matrix,
)

MANDATORY_LIMITATIONS: Final[tuple[str, ...]] = (
    "RESEARCH_ONLY output: not approved for clinical diagnosis, triage, treatment, or patient self-assessment.",
    "Do NOT interpret calibrated_research_score as a clinically reliable individual CAD risk; "
    "formal Gate PT (P-1/P-3), external transportability validation, and clinician sign-off (P-4) remain required.",
    "SHAP attributions are NEVER additive in calibrated probability units: for l2_logistic_regression they sum to "
    "calibrated_log_odds = logit(calibrated_research_score); for constrained_random_forest they sum to uncalibrated raw_model_score.",
    "Outer-fold dispersion reports descriptive CV split sensitivity only—NOT validated patient-specific epistemic uncertainty or a coverage interval.",
    "Target construct is cross-sectional angiographic CAD presence in a referral cohort—NEVER a 30-day or future cardiovascular event horizon.",
    "Track B wearable/monitoring observations are not valid predictors for this model and are rejected.",
)

LIME_PREDICTION_LIMITATION: Final[str] = (
    "LIME weights are local weighted-linear surrogate approximations of the declared "
    "model output, NOT exact Shapley values: they satisfy no efficiency/local-accuracy "
    "guarantee, may differ from SHAP in magnitude and sign, and are never causal or "
    "clinical claims. Every LIME payload carries an explicit quality status; when it "
    "is not ACCEPTABLE_LOCAL_APPROXIMATION the weights must not be relied upon at all."
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
    raw_model_log_odds: float
    calibrated_research_score: float
    calibrated_log_odds: float
    exploratory_threshold: float
    exploratory_above_threshold_flag: bool
    uncertainty: Mapping[str, Any]
    explanation: FaithfulShapExplanation
    verified_artifact_hashes: Mapping[str, str]
    limitations: tuple[str, ...]
    lime_explanation: FaithfulLimeExplanation | None = None
    lime_comparability: Mapping[str, Any] | None = None
    lime_stability: LimeStabilityReport | None = None

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
                "raw_model_log_odds": self.raw_model_log_odds,
                "calibrated_research_score": self.calibrated_research_score,
                "calibrated_log_odds": self.calibrated_log_odds,
                "shap_explained_quantity": self.explanation.explained_quantity,
                "shap_mathematical_scale": self.explanation.scale,
                "shap_target_value_on_scale": (
                    self.explanation.target_prediction_on_scale
                ),
                "shap_explains_calibrated_score_directly": (
                    self.explanation.explains_calibrated_score_directly
                ),
                "shap_additive_on_calibrated_probability": (
                    self.explanation.additive_on_calibrated_probability
                ),
                "score_interpretation": "RESEARCH_ONLY_NOT_INDIVIDUAL_CLINICAL_RISK",
                "exploratory_threshold": self.exploratory_threshold,
                "exploratory_threshold_clinically_validated": False,
                "exploratory_above_threshold_flag": self.exploratory_above_threshold_flag,
                "lime_quality_status": (
                    None
                    if self.lime_explanation is None
                    else self.lime_explanation.quality_status
                ),
                "lime_reliable_for_interpretation": (
                    None
                    if self.lime_explanation is None
                    else self.lime_explanation.is_reliable_for_interpretation
                ),
            },
            "uncertainty": dict(self.uncertainty),
            "explanation": self.explanation.to_dict(),
            "lime_explanation": (
                None if self.lime_explanation is None else self.lime_explanation.to_dict()
            ),
            "lime_stability": (
                None if self.lime_stability is None else self.lime_stability.to_dict()
            ),
            "explanation_comparability": (
                None
                if self.lime_comparability is None
                else dict(self.lime_comparability)
            ),
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
                "producer_authenticated": True,
                "verified_artifact_hashes": dict(self.verified_artifact_hashes),
            },
            "limitations": list(self.limitations),
        }


def _raw_prob_and_optional_logit_single(
    family: str, estimator: Any, z_row: np.ndarray
) -> tuple[float, float | None]:
    reshaped = z_row.reshape(1, -1)
    probs = estimator.predict_proba(reshaped)
    pos_idx = list(estimator.classes_).index(1)
    p_raw = float(probs[0, pos_idx])
    if family == "l2_logistic_regression":
        raw_logit = float(estimator.decision_function(reshaped)[0])
        return p_raw, raw_logit
    return p_raw, None


_KNOWN_EXECUTION_PROFILES: Final[tuple[str, ...]] = (
    EXECUTION_PROFILE_AI1_GENERIC_V1,
    EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1,
)


def _validated_execution_profile(manifest_model: Mapping[str, Any], container: Mapping[str, Any]) -> str:
    profile = manifest_model.get("execution_profile")
    if profile not in _KNOWN_EXECUTION_PROFILES or container.get("execution_profile") != profile:
        raise BundleIntegrityError(
            "execution_profile_container_mismatch",
            "Execution profile differs across manifest and model container, or is unknown.",
        )
    return str(profile)


def _expected_estimator_width(
    family: str, preprocessor: FoldSafeClinicalPreprocessor, execution_profile: str
) -> int:
    if (
        execution_profile == EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1
        and family == "constrained_random_forest"
    ):
        return CLEVELAND_D047_RF_SPACE_WIDTH
    return preprocessor.n_encoded_features


def _validate_estimator_fitted_width(
    estimator: Any,
    family: str,
    preprocessor: FoldSafeClinicalPreprocessor,
    execution_profile: str,
) -> None:
    expected = _expected_estimator_width(family, preprocessor, execution_profile)
    fitted = int(getattr(estimator, "n_features_in_", -1))
    if fitted != expected:
        raise BundleIntegrityError(
            "estimator_fitted_width_mismatch",
            "Fitted estimator width does not match the declared execution "
            "profile and model family.",
        )


class ResearchCadPredictor:
    """Offline RESEARCH_ONLY predictor loaded exclusively from a trusted local bundle."""

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
    def execution_profile(self) -> str:
        return str(self._descriptor.manifest["model"]["execution_profile"])

    @property
    def protocol_id(self) -> str:
        return str(self._descriptor.manifest["model"]["protocol_id"])

    @property
    def model_family(self) -> str:
        return str(self._descriptor.manifest["model"]["selected_model_family"])

    def _lime_estimator_input_builder(self) -> Callable[[np.ndarray], np.ndarray]:
        """Return the exact estimator-input builder used for projected LIME.

        This is the same :func:`ai.training._estimator_input_matrix` mapping used
        for scoring and SHAP, so LIME perturbation rows are always fed to the
        estimator through the identical frozen input space.
        """

        def _builder(raw_rows: np.ndarray) -> np.ndarray:
            encoded = self._preprocessor.transform(raw_rows)
            return _estimator_input_matrix(
                self.model_family,
                self._preprocessor,
                raw_rows,
                encoded,
                self.execution_profile,
            )

        return _builder

    @classmethod
    def from_verified_bundle(
        cls,
        bundle_dir: Path,
        *,
        trusted_local_root: Path,
        signing_key: bytes | None = None,
    ) -> "ResearchCadPredictor":
        """Enforce trusted-local-origin authentication + hash integrity BEFORE ``joblib.load``."""
        verified = verify_trusted_local_bundle(
            Path(bundle_dir),
            trusted_local_root=Path(trusted_local_root),
            signing_key=signing_key,
        )
        if (
            not verified.producer_authenticated
            or not verified.safe_for_pickle_deserialization
        ):
            raise BundleIntegrityError(
                "bundle_not_authenticated_for_deserialization",
                "Refusing joblib.load on an unauthenticated bundle.",
            )
        root = verified.bundle_dir

        prep_json = json.loads(
            (root / PREPROCESSING_FILENAME).read_text(encoding="utf-8")
        )
        preprocessor = FoldSafeClinicalPreprocessor.from_json_dict(
            prep_json, expected_panel=verified.panel
        )

        cal_json = json.loads((root / CALIBRATION_FILENAME).read_text(encoding="utf-8"))
        calibrator = OofLogisticCalibrator.from_json_dict(cal_json)

        bg_json = json.loads((root / SHAP_BG_FILENAME).read_text(encoding="utf-8"))
        is_authorized_real = (
            verified.manifest.get("research_authorization") is not None
            or verified.manifest.get("eligibility", {}).get("execution_mode") == "INTERNAL_EXPLORATORY_RESEARCH"
        )
        shap_bg = ShapBackgroundReference.from_json_dict(
            bg_json,
            preprocessor=preprocessor,
            require_synthetic=True,
            is_authorized_research_bundle=is_authorized_real,
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
        declared_profile = _validated_execution_profile(
            verified.manifest["model"], container
        )
        _validate_estimator_fitted_width(
            container["estimator"], declared_family, preprocessor, declared_profile
        )

        fold_members: list[FoldEnsembleMember] = []
        for entry in container.get("fold_ensemble", ()):
            member_family = str(entry["model_family"])
            member_prep = FoldSafeClinicalPreprocessor.from_json_dict(
                entry["preprocessor_json"], expected_panel=verified.panel
            )
            if "calibrator_json" not in entry:
                raise BundleIntegrityError(
                    "missing_fold_member_calibrator",
                    "Outer-fold ensemble member lacks its own fold-compatible calibrator.",
                )
            member_cal = OofLogisticCalibrator.from_json_dict(entry["calibrator_json"])
            if member_cal.model_family != member_family:
                raise BundleIntegrityError(
                    "fold_calibrator_family_mismatch",
                    "Outer-fold calibrator model_family does not match outer-fold estimator family.",
                )
            _validate_estimator_fitted_width(
                entry["estimator"], member_family, member_prep, declared_profile
            )
            fold_members.append(
                FoldEnsembleMember(
                    fold_index=int(entry["fold_index"]),
                    model_family=member_family,
                    preprocessor=member_prep,
                    estimator=entry["estimator"],
                    calibrator=member_cal,
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
        lime_config: LimeConfig | None = None,
        lime_target: str = "auto",
        lime_stability_seeds: Sequence[int] | None = DEFAULT_LIME_STABILITY_SEEDS,
        lime_quality_policy: LimeQualityPolicy | None = None,
        lime_require_acceptable_quality: bool = False,
    ) -> ResearchPredictionResult:
        """Validate clinical/lab record and compute aligned score, dispersion & SHAP.

        When ``lime_config`` is supplied a genuine tabular LIME explanation is
        computed on the same declared model-output scale as the SHAP explanation
        and attached to the result together with a machine-readable quality
        verdict. Any scale mismatch between the two methods fails closed rather
        than returning incomparable attributions.

        ``lime_stability_seeds`` (default: three registered seeds) is assessed
        independently of fidelity so the attached verdict can reach
        ``ACCEPTABLE_LOCAL_APPROXIMATION``; pass ``None`` to skip it, which
        leaves the verdict at ``UNVERIFIED_STABILITY`` at best. Set
        ``lime_require_acceptable_quality=True`` to fail closed instead of
        returning a diagnostic-only explanation.
        """
        is_real = bool(isinstance(payload, Mapping) and payload.get("synthetic") is False)
        validated = validate_clinical_record(
            payload, self.panel, require_synthetic=not is_real
        )
        x_row = validated.as_row_array()
        z_row = self._preprocessor.transform(x_row)[0]
        e_row = _estimator_input_matrix(
            self.model_family,
            self._preprocessor,
            x_row,
            z_row.reshape(1, -1),
            self.execution_profile,
        )[0]

        raw_score, exact_raw_logit = _raw_prob_and_optional_logit_single(
            self.model_family, self._estimator, e_row
        )
        raw_log_odds = (
            exact_raw_logit
            if exact_raw_logit is not None
            else float(safe_clipped_logit(raw_score))
        )
        cal_log_odds = float(
            self._calibrator.calibrated_log_odds(
                raw_score, raw_logits=exact_raw_logit
            )
        )
        cal_score = float(expit(cal_log_odds))

        fold_raw_scores: list[float] = []
        fold_cal_scores: list[float] = []
        fold_families: list[str] = []
        for member in self._fold_ensemble:
            z_fold = member.preprocessor.transform(x_row)[0]
            e_fold = _estimator_input_matrix(
                member.model_family,
                member.preprocessor,
                x_row,
                z_fold.reshape(1, -1),
                self.execution_profile,
            )[0]
            p_fold_raw, fold_logit = _raw_prob_and_optional_logit_single(
                member.model_family, member.estimator, e_fold
            )
            p_fold_cal = float(
                member.calibrator.calibrate(p_fold_raw, raw_logits=fold_logit)
            )
            fold_raw_scores.append(p_fold_raw)
            fold_cal_scores.append(p_fold_cal)
            fold_families.append(member.model_family)

        dispersion = compute_fold_prediction_dispersion(
            fold_raw_scores,
            fold_cal_scores,
            fold_model_families=fold_families,
            missing_fields_with_reason=validated.missing_fields_with_reason,
            total_fields=len(self.panel.fields),
            development_prevalence=self._calibrator.development_prevalence,
        )

        missing_set = frozenset(
            name for name, _ in validated.missing_fields_with_reason
        )
        explanation_kwargs: dict[str, Any] = {}
        if (
            self.execution_profile == EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1
            and self.model_family == "constrained_random_forest"
        ):
            explanation_kwargs = {
                "projected_z_row": e_row,
                "projected_background": _d047_project_background_to_rf_space(
                    self._preprocessor, self._shap_background.background_matrix
                ),
                "projected_column_to_raw_feature": _d047_rf_column_to_raw_feature(
                    self._preprocessor
                ),
            }
        explanation = explain_clinical_instance(
            model_family=self.model_family,
            estimator=self._estimator,
            preprocessor=self._preprocessor,
            panel=self.panel,
            background=self._shap_background,
            z_row=z_row,
            calibrator=self._calibrator,
            missing_feature_names=missing_set,
            **explanation_kwargs,
        )

        # Fail-closed alignment check between prediction quantities and explanation target
        if explanation.explained_quantity == "calibrated_log_odds":
            if (
                not math.isfinite(explanation.target_prediction_on_scale)
                or abs(explanation.target_prediction_on_scale - cal_log_odds)
                > ADDITIVITY_TOLERANCE
                or abs(explanation.linked_probability_value - cal_score)
                > ADDITIVITY_TOLERANCE
            ):
                raise ExplainabilityIntegrityError(
                    "calibrated_log_odds_explanation_misaligned",
                    "Calibrated-log-odds SHAP target does not match calibrated_research_score.",
                )
        elif explanation.explained_quantity == "raw_model_score":
            if (
                abs(explanation.target_prediction_on_scale - raw_score)
                > ADDITIVITY_TOLERANCE
                or explanation.explains_calibrated_score_directly is not False
            ):
                raise ExplainabilityIntegrityError(
                    "raw_score_explanation_misaligned",
                    "Raw-probability SHAP target does not match raw_model_score.",
                )

        lime_explanation: FaithfulLimeExplanation | None = None
        lime_comparability: Mapping[str, Any] | None = None
        lime_stability: LimeStabilityReport | None = None
        if lime_config is not None:
            lime_builder = None
            lime_mapping = None
            if (
                self.execution_profile == EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1
                and self.model_family == "constrained_random_forest"
            ):
                lime_builder = self._lime_estimator_input_builder()
                lime_mapping = _d047_rf_column_to_raw_feature(self._preprocessor)
            lime_explanation, lime_stability = (
                explain_clinical_instance_lime_certified(
                    stability_seeds=lime_stability_seeds,
                    quality_policy=lime_quality_policy,
                    model_family=self.model_family,
                    estimator=self._estimator,
                    preprocessor=self._preprocessor,
                    panel=self.panel,
                    background=self._shap_background,
                    x_raw_row=x_row,
                    z_row=z_row,
                    calibrator=self._calibrator,
                    target=lime_target,
                    config=lime_config,
                    estimator_input_builder=lime_builder,
                    projected_column_to_raw_feature=lime_mapping,
                    missing_feature_names=missing_set,
                )
            )
            # Never compare explanations that target different score scales.
            lime_comparability = MappingProxyType(
                dict(
                    assert_comparable_explanation_scales(
                        explanation, lime_explanation
                    )
                )
            )
            if lime_explanation.explained_quantity == "calibrated_log_odds":
                expected_lime_target = cal_log_odds
            elif lime_explanation.explained_quantity == "raw_model_score":
                expected_lime_target = raw_score
            elif lime_explanation.explained_quantity == "raw_model_log_odds":
                expected_lime_target = raw_log_odds
            else:  # pragma: no cover - defensive, registry is closed
                raise ExplainabilityIntegrityError(
                    "lime_target_misaligned",
                    "LIME declared an unregistered explained quantity.",
                )
            if (
                not math.isfinite(lime_explanation.model_prediction_at_instance)
                or abs(
                    lime_explanation.model_prediction_at_instance
                    - expected_lime_target
                )
                > ADDITIVITY_TOLERANCE
            ):
                raise ExplainabilityIntegrityError(
                    "lime_target_misaligned",
                    "LIME target value does not match the prediction quantity on "
                    "its declared scale.",
                )
            if lime_require_acceptable_quality:
                require_acceptable_lime_quality(lime_explanation)

        dynamic_limitations = list(MANDATORY_LIMITATIONS)
        if lime_explanation is not None:
            dynamic_limitations.append(LIME_PREDICTION_LIMITATION)
            dynamic_limitations.append(
                "LIME quality verdict: "
                f"{lime_explanation.quality_status}"
                + (
                    " (weights are NOT reliable for interpretation; diagnostic "
                    "inspection only)."
                    if not lime_explanation.is_reliable_for_interpretation
                    else " (local approximation only)."
                )
            )
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
            raw_model_log_odds=raw_log_odds,
            calibrated_research_score=cal_score,
            calibrated_log_odds=cal_log_odds,
            exploratory_threshold=float(exploratory_threshold),
            exploratory_above_threshold_flag=bool(cal_score >= exploratory_threshold),
            uncertainty=MappingProxyType(dict(dispersion)),
            explanation=explanation,
            verified_artifact_hashes=self._descriptor.verified_files,
            limitations=tuple(dynamic_limitations),
            lime_explanation=lime_explanation,
            lime_comparability=lime_comparability,
            lime_stability=lime_stability,
        )
