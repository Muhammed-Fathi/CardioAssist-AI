"""Fail-closed exception hierarchy for the M2a read-only dataset audit toolchain."""
from __future__ import annotations


class AuditError(RuntimeError):
    """Base fail-closed error for all Gate DA dataset audit checks."""

    error_code: str = "audit_error"


class GovernanceAuthorizationError(AuditError):
    """Raised when an operation lacks explicit human Gate DA authorization or violates scope."""

    error_code: str = "governance_authorization_error"


class GitIgnoreProtectionError(AuditError):
    """Raised when a data path is not ignored by Git or files under /data/ are tracked."""

    error_code: str = "git_ignore_protection_error"


class ProvenanceVerificationError(AuditError):
    """Raised on unapproved source URLs, missing license snapshots, hash/size mismatch, or mutated files."""

    error_code: str = "provenance_verification_error"


class ArchiveSecurityError(AuditError):
    """Raised when an archive contains path traversal, unexpected files, or unapproved dataset variants."""

    error_code: str = "archive_security_error"


class FormatValidationError(AuditError):
    """Raised on missing files, unknown formats, corrupt files, wrong delimiters/columns, or unrecognized columns."""

    error_code: str = "format_validation_error"


class RawVsProcessedConfusionError(FormatValidationError):
    """Raised when a raw 76-attribute UCI-45 file is confused with a processed 14-column file or vice versa."""

    error_code: str = "raw_vs_processed_confusion_error"


class TargetOrCodingValidationError(AuditError):
    """Raised when target labels or categorical codings violate the documented dataset contract."""

    error_code: str = "target_or_coding_validation_error"


class LeakageColumnError(AuditError):
    """Raised when unauthorized label-defining or leakage columns appear in a dataset."""

    error_code: str = "leakage_column_error"


class PatientLevelLeakageError(AuditError):
    """Raised if any patient-level row or raw record content is detected in a generated report."""

    error_code: str = "patient_level_leakage_error"
