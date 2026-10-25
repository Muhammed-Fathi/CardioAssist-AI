"""Typed, value-redacting exceptions for the RESEARCH_ONLY CAD AI pipeline.

None of these exceptions echo submitted feature values, patient records, or
file contents: only field identifiers, panel/bundle identifiers, and invariant
codes are surfaced.
"""
from __future__ import annotations


class AiPipelineError(Exception):
    """Base error for all fail-closed AI research pipeline checks."""

    def __init__(self, code: str, message: str, *, field: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field


class ClinicalInputValidationError(AiPipelineError):
    """Raised when a staged clinical or laboratory input fails contract validation."""


class PreprocessingContractError(AiPipelineError):
    """Raised when fold-contained preprocessing invariants are violated."""


class CohortGovernanceError(AiPipelineError):
    """Raised when cohort pooling, overlap, or non-synthetic execution is attempted."""


class CalibrationIntegrityError(AiPipelineError):
    """Raised when out-of-fold calibration fitting or serialization fails checks."""


class ExplainabilityIntegrityError(AiPipelineError):
    """Raised when model-faithful SHAP computation or additivity verification fails."""


class BundleIntegrityError(AiPipelineError):
    """Raised when a RESEARCH_ONLY model bundle fails pre-load integrity checks."""
