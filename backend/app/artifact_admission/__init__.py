"""Offline admission of research CAD model descriptors — RESEARCH_ONLY.

This package answers exactly one question: *may this described research
artifact be opened by local research tooling, and is its declared scope
internally consistent?* It never answers whether a model is scientifically
valid, clinically approved or servable.

What it deliberately does not do:

* no artifact deserialization (no ``pickle``, ``joblib``, ``onnxruntime``,
  ``sklearn``, ``torch`` or ``numpy`` import anywhere in the package);
* no dataset, training-row, patient-record or protected-manifest access;
* no network access;
* no FastAPI route, middleware or startup hook;
* no environment variable, settings file or registry mutation that could
  promote a research artifact to serving.

Usage (offline CLI/notebook or tests only)::

    from backend.app.artifact_admission import (
        AdmissionPolicy, DirectoryArtifactSource, admit_research_artifact,
    )

    decision = admit_research_artifact(
        descriptor,
        source=DirectoryArtifactSource(package_root),
        policy=AdmissionPolicy.from_shared_contracts(registered_targets=targets),
    )
    assert decision.serving_eligibility == "RESEARCH_ONLY"
"""

from .admission import (
    D047_NON_APPROVAL_REASON,
    DESCRIPTOR_SCHEMA_PATH,
    DESCRIPTOR_SCHEMA_VERSION,
    INTERNAL_EXPLORATORY_LABEL,
    NON_APPROVAL_REASONS,
    RESEARCH_ONLY,
    AdmissionDecision,
    AdmissionPolicy,
    admit_research_artifact,
    SUPPORTED_MODEL_FAMILIES,
)
from .catalog import FeatureSchemaCatalog
from .errors import ArtifactAdmissionError
from .sources import (
    MAX_ARTIFACT_BYTES,
    ArtifactReferenceError,
    ArtifactSource,
    DirectoryArtifactSource,
    InMemoryArtifactSource,
)

__all__ = [
    "AdmissionDecision",
    "AdmissionPolicy",
    "ArtifactAdmissionError",
    "ArtifactReferenceError",
    "ArtifactSource",
    "D047_NON_APPROVAL_REASON",
    "DESCRIPTOR_SCHEMA_PATH",
    "DESCRIPTOR_SCHEMA_VERSION",
    "DirectoryArtifactSource",
    "FeatureSchemaCatalog",
    "INTERNAL_EXPLORATORY_LABEL",
    "InMemoryArtifactSource",
    "MAX_ARTIFACT_BYTES",
    "NON_APPROVAL_REASONS",
    "RESEARCH_ONLY",
    "SUPPORTED_MODEL_FAMILIES",
    "admit_research_artifact",
]
