"""End-to-end Track A CAD AI research pipeline (RESEARCH_ONLY, offline).

This package implements the reusable, synthetic-verified AI research components
planned in ``docs/research/AI_FIRST_COMPLETION_STRATEGY.md``:
- :mod:`ai.panels` — staged clinical & routine laboratory input contracts
  (reusing ``research.intake`` and ``research.uci412.feature_schema``).
- :mod:`ai.preprocessing` — fold-contained, lineage-preserving tabular
  preprocessing with deterministic JSON state export.
- :mod:`ai.calibration` — leak-free out-of-fold logistic probability calibration,
  bootstrap confidence intervals, prevalence-shift diagnostics, and fold-
  ensemble epistemic uncertainty.
- :mod:`ai.explainability` — genuine, model-faithful Grouped Interventional
  LinearSHAP and Grouped Interventional TreeSHAP with runtime efficiency checks.
- :mod:`ai.training` — nested-CV selection, label-shuffle negative controls, and
  locked independent-cohort external evaluation with anti-pooling guards.
- :mod:`ai.packaging` — versioned ``RESEARCH_ONLY`` bundle packaging and byte-
  level pre-deserialization SHA-256 verification.
- :mod:`ai.inference` — offline ``ResearchCadPredictor`` returning score,
  uncertainty, verified SHAP attributions, and explicit clinical limitations.

Never imported by ``backend/app/``; ``MOCK_SYNTHETIC`` remains the sole active
FastAPI runtime provider while Gate PT (``P-3``) is closed.
"""
from __future__ import annotations

from ai.calibration import (
    OofLogisticCalibrator,
    compute_instance_uncertainty,
    compute_prevalence_shift_diagnostic,
    evaluate_comprehensive_metrics,
)
from ai.errors import (
    AiPipelineError,
    BundleIntegrityError,
    CalibrationIntegrityError,
    ClinicalInputValidationError,
    CohortGovernanceError,
    ExplainabilityIntegrityError,
    PreprocessingContractError,
)
from ai.explainability import (
    FaithfulShapExplanation,
    FeatureShapAttribution,
    ShapBackgroundReference,
    exact_coalition_shapley_oracle,
    explain_clinical_instance,
)
from ai.inference import ResearchCadPredictor, ResearchPredictionResult
from ai.packaging import (
    BUNDLE_SCHEMA_VERSION,
    VerifiedBundleDescriptor,
    package_research_bundle,
    verify_research_bundle,
)
from ai.panels import (
    DA_A1_BASIC_CLINICAL_PANEL,
    DA_A1_CLINICAL_CORE_LABS_PANEL,
    DA_A2_RESTING_LABS_PANEL,
    DA_A2_RESTING_PANEL,
    REGISTERED_PANELS,
    PanelFieldSpec,
    ResearchPanelContract,
    ValidatedClinicalRecord,
    get_panel_contract,
    validate_clinical_record,
    validate_cohort_records,
)
from ai.preprocessing import FoldSafeClinicalPreprocessor
from ai.training import (
    ResearchTrainingConfig,
    TrainedResearchRun,
    evaluate_locked_external_cohort,
    train_research_model,
)

__all__ = [
    "AiPipelineError",
    "BUNDLE_SCHEMA_VERSION",
    "BundleIntegrityError",
    "CalibrationIntegrityError",
    "ClinicalInputValidationError",
    "CohortGovernanceError",
    "DA_A1_BASIC_CLINICAL_PANEL",
    "DA_A1_CLINICAL_CORE_LABS_PANEL",
    "DA_A2_RESTING_LABS_PANEL",
    "DA_A2_RESTING_PANEL",
    "ExplainabilityIntegrityError",
    "FaithfulShapExplanation",
    "FeatureShapAttribution",
    "FoldSafeClinicalPreprocessor",
    "OofLogisticCalibrator",
    "PanelFieldSpec",
    "PreprocessingContractError",
    "REGISTERED_PANELS",
    "ResearchCadPredictor",
    "ResearchPanelContract",
    "ResearchPredictionResult",
    "ResearchTrainingConfig",
    "ShapBackgroundReference",
    "TrainedResearchRun",
    "ValidatedClinicalRecord",
    "VerifiedBundleDescriptor",
    "compute_instance_uncertainty",
    "compute_prevalence_shift_diagnostic",
    "evaluate_comprehensive_metrics",
    "evaluate_locked_external_cohort",
    "exact_coalition_shapley_oracle",
    "explain_clinical_instance",
    "get_panel_contract",
    "package_research_bundle",
    "train_research_model",
    "validate_clinical_record",
    "validate_cohort_records",
    "verify_research_bundle",
]
