"""Rejection type for offline artifact admission.

Every rejection carries a stable machine-readable code and the offending
*field path only*. Descriptor values, artifact content, hashes, feature
values, cohort labels and any patient-related text are never echoed — a
failure path must not become a data-exfiltration or log-leak path.
"""

from __future__ import annotations


class ArtifactAdmissionError(Exception):
    """Fail-closed rejection of a research artifact descriptor."""

    def __init__(self, code: str, field: str) -> None:
        self.code = code
        self.field = field
        super().__init__(f"artifact admission rejected: {code} (field: {field})")
