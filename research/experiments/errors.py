"""Fail-closed error types for the M2c local experiment runner."""
from __future__ import annotations


class ExperimentRunnerError(RuntimeError):
    """Base error with a safe message that does not include source row values."""


class RuntimeGuardError(ExperimentRunnerError):
    """The process is not running in the permitted local Windows environment."""


class StorageProtectionError(ExperimentRunnerError):
    """Git-ignore, path-containment, or local-output protection failed."""


class AuthorizationError(ExperimentRunnerError):
    """The separate D-047 local authorization is missing, invalid, or mismatched."""


class ProvenanceError(ExperimentRunnerError):
    """D-046 read-only provenance or the hash-bound source record is invalid."""


class SourceFormatError(ExperimentRunnerError):
    """The protected source bytes do not match the exact UCI-45 processed schema."""


class EvaluationError(ExperimentRunnerError):
    """The fixed nested-CV procedure could not be evaluated safely."""
