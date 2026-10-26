"""End-to-end Track A CAD AI research pipeline (RESEARCH_ONLY, offline).

This package implements the reusable, synthetic-verified AI research components
planned in ``docs/research/AI_FIRST_COMPLETION_STRATEGY.md``:
- :mod:`ai.panels` — staged clinical & routine laboratory input contracts
  (reusing ``research.intake`` and ``research.uci412.feature_schema``).
- :mod:`ai.preprocessing` — fold-contained, lineage-preserving tabular
  preprocessing with deterministic JSON state export.
- :mod:`ai.calibration` — monotone logistic probability calibration (cross-fitted
  inner-OOF fold calibrators + development-OOF final calibrator), bootstrap CIs,
  prevalence-shift diagnostics, and descriptive outer-fold dispersion.
- :mod:`ai.explainability` — genuine, model-faithful Grouped Interventional
  LinearSHAP (exact on both ``raw_log_odds`` and ``calibrated_log_odds``) and
  Grouped Interventional TreeSHAP (exact on ``raw_model_probability``), plus
  explicit training-derivative privacy metadata on ``shap_background.json``.
- :mod:`ai.training` — nested-CV selection, cross-fitted calibration evaluation,
  label-shuffle negative controls, frozen external-cohort evaluation primitive,
  and locally protected ``ExternalEvaluationLedger`` single-shot enforcement.
- :mod:`ai.packaging` — staging-directory atomic ``RESEARCH_ONLY`` bundle
  packaging, SHA-256 integrity checks, and ``HMAC-SHA256`` + ``trusted_local_root``
  authentication BEFORE any ``joblib.load``.
- :mod:`ai.inference` — offline ``ResearchCadPredictor`` returning explicitly
  separated raw/calibrated scores, descriptive fold dispersion, aligned SHAP
  attributions, and mandatory non-clinical limitations.
- :mod:`ai.execution` — locally protected, auditable real-data execution
  controller enforcing hash-bound human research authorization manifests,
  source-specific read-only adapters, prohibited feature rejection, and Windows
  workstation private storage.

Never imported by ``backend/app/``; ``MOCK_SYNTHETIC`` remains the sole active
FastAPI runtime provider while Gate PT (``P-3``) is closed.
"""
from __future__ import annotations

from ai.calibration import (
    OofLogisticCalibrator,
    compute_fold_prediction_dispersion,
    compute_instance_uncertainty,
    compute_prevalence_shift_diagnostic,
    evaluate_comprehensive_metrics,
    safe_clipped_logit,
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
from ai.execution import (
    GUARDED_CLEVELAND_D047_OPERATOR_CONFIRMATION,
    DatasetAdapterIntegrityError,
    ExecutionAuthorizationError,
    GuardedClevelandExecutionProof,
    ResearchAuthorizationContext,
    execute_authorized_research_run,
    execute_guarded_cleveland_d047_run,
    load_cleveland_source_records,
    load_uci412_source_records,
    parse_and_validate_research_authorization,
)
from ai.explainability import (
    FaithfulShapExplanation,
    FeatureShapAttribution,
    ShapBackgroundReference,
    exact_coalition_shapley_oracle,
    explain_clinical_instance,
)
from ai.filesystem_security import (
    AccessControlVerificationResult,
    ensure_private_directory,
    protect_private_directory,
    protect_private_file,
    verify_access_control,
)
from ai.inference import ResearchCadPredictor, ResearchPredictionResult
from ai.packaging import (
    BUNDLE_ACCEPTANCE_MARKER_FILENAME,
    BUNDLE_QUARANTINE_MARKER_FILENAME,
    BUNDLE_SCHEMA_VERSION,
    VerifiedBundleDescriptor,
    get_or_create_local_signing_key,
    package_research_bundle,
    verify_research_bundle,
    verify_trusted_local_bundle,
    write_bundle_acceptance_marker,
    write_bundle_quarantine_marker,
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
    CLEVELAND_D047_RF_SPACE_VERSION,
    CLEVELAND_D047_RF_SPACE_WIDTH,
    EXECUTION_PROFILE_AI1_GENERIC_V1,
    EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1,
    ExternalEvaluationLedger,
    FoldEnsembleMember,
    ResearchTrainingConfig,
    TrainedResearchRun,
    derive_cleveland_d047_inner_seed,
    derive_cleveland_d047_model_seed,
    derive_cleveland_d047_negative_control_outer_seed,
    evaluate_locked_external_cohort,
    train_research_model,
)

__all__ = [
    "AccessControlVerificationResult",
    "AiPipelineError",
    "BUNDLE_ACCEPTANCE_MARKER_FILENAME",
    "BUNDLE_QUARANTINE_MARKER_FILENAME",
    "BUNDLE_SCHEMA_VERSION",
    "BundleIntegrityError",
    "CalibrationIntegrityError",
    "ClinicalInputValidationError",
    "CLEVELAND_D047_RF_SPACE_VERSION",
    "CLEVELAND_D047_RF_SPACE_WIDTH",
    "CohortGovernanceError",
    "DA_A1_BASIC_CLINICAL_PANEL",
    "DA_A1_CLINICAL_CORE_LABS_PANEL",
    "DA_A2_RESTING_LABS_PANEL",
    "DA_A2_RESTING_PANEL",
    "DatasetAdapterIntegrityError",
    "EXECUTION_PROFILE_AI1_GENERIC_V1",
    "EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1",
    "ExecutionAuthorizationError",
    "ExplainabilityIntegrityError",
    "ExternalEvaluationLedger",
    "FaithfulShapExplanation",
    "FeatureShapAttribution",
    "FoldEnsembleMember",
    "FoldSafeClinicalPreprocessor",
    "GUARDED_CLEVELAND_D047_OPERATOR_CONFIRMATION",
    "GuardedClevelandExecutionProof",
    "OofLogisticCalibrator",
    "PanelFieldSpec",
    "PreprocessingContractError",
    "REGISTERED_PANELS",
    "ResearchAuthorizationContext",
    "ResearchCadPredictor",
    "ResearchPanelContract",
    "ResearchPredictionResult",
    "ResearchTrainingConfig",
    "ShapBackgroundReference",
    "TrainedResearchRun",
    "ValidatedClinicalRecord",
    "VerifiedBundleDescriptor",
    "compute_fold_prediction_dispersion",
    "compute_instance_uncertainty",
    "compute_prevalence_shift_diagnostic",
    "derive_cleveland_d047_inner_seed",
    "derive_cleveland_d047_model_seed",
    "derive_cleveland_d047_negative_control_outer_seed",
    "ensure_private_directory",
    "evaluate_comprehensive_metrics",
    "evaluate_locked_external_cohort",
    "exact_coalition_shapley_oracle",
    "execute_authorized_research_run",
    "execute_guarded_cleveland_d047_run",
    "explain_clinical_instance",
    "get_or_create_local_signing_key",
    "get_panel_contract",
    "load_cleveland_source_records",
    "load_uci412_source_records",
    "package_research_bundle",
    "parse_and_validate_research_authorization",
    "protect_private_directory",
    "protect_private_file",
    "safe_clipped_logit",
    "train_research_model",
    "validate_clinical_record",
    "validate_cohort_records",
    "verify_access_control",
    "verify_research_bundle",
    "verify_trusted_local_bundle",
    "write_bundle_acceptance_marker",
    "write_bundle_quarantine_marker",
]
