"""Fail-closed error types for the source-specific UCI-412 research benchmark.

Every message is written to be safe: no source cell value, patient-level
measurement, absolute local path, or row identifier may appear in a raised
message. Callers may report the exception class and message to a console or a
review record without leaking protected data.
"""
from __future__ import annotations


class Uci412Error(RuntimeError):
    """Base error for the UCI-412 research harness."""


class SchemaError(Uci412Error):
    """The registered feature dictionary, panel, or plan is internally invalid."""


class SourceFormatError(Uci412Error):
    """Source bytes do not match the exact registered UCI-412 workbook profile."""


class ProvenanceError(Uci412Error):
    """D-046 read-only provenance, license, or source byte identity failed."""


class AuthorizationError(Uci412Error):
    """The separate M3a local internal-research authorization is missing or invalid."""


class RuntimeGuardError(Uci412Error):
    """The process is not running in the permitted local Windows environment."""


class StorageProtectionError(Uci412Error):
    """Git-ignore, path-containment, or protected-output enforcement failed."""


class EvaluationError(Uci412Error):
    """The registered nested-CV procedure cannot be evaluated safely."""


class ModelNotAvailableError(Uci412Error):
    """A reserved model family was requested but is deliberately not implemented."""
