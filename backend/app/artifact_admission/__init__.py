"""Offline admission of research CAD model descriptors — RESEARCH_ONLY.

This package answers exactly one question: *may this described research
artifact be opened by local research tooling, and is its declared scope
internally consistent?* It never answers whether a model is scientifically
valid, clinically approved or servable.

It supports only descriptors whose feature contract is bound to the current
mock fixture schemas under the reviewed ``synthetic_fixture_input_order/v1``
admission order. It is **not** a scientific bridge for the five-feature
Cleveland D-047 predictor set; that mapping requires its own reviewed research
protocol/feature registry.

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
        AdmissionPolicy, DirectoryArtifactSource, SYNTHETIC_FIXTURE_INPUT_ORDER,
        admit_research_artifact,
    )

    decision = admit_research_artifact(
        descriptor,
        source=DirectoryArtifactSource(package_root),
        policy=AdmissionPolicy.from_shared_contracts(
            registered_targets=targets,
            # Omitting the ordered binding fails closed by design.
            input_order_policy=SYNTHETIC_FIXTURE_INPUT_ORDER,
        ),
    )
    assert decision.serving_eligibility == "RESEARCH_ONLY"
"""

from .admission import (
    CALIBRATION_INTEGRITY_EMBEDDED,
    CALIBRATION_INTEGRITY_NONE,
    CALIBRATION_INTEGRITY_VERIFIED,
    D047_NON_APPROVAL_REASON,
    DESCRIPTOR_SCHEMA_PATH,
    DESCRIPTOR_SCHEMA_VERSION,
    EMBEDDED_CALIBRATION_REASON,
    EXPLAINABILITY_CAPABILITIES,
    EXPLAINABILITY_CAPABILITY,
    EXPLAINABILITY_VERIFIED_CLAIM,
    INTERNAL_EXPLORATORY_LABEL,
    NON_APPROVAL_REASONS,
    RESEARCH_ONLY,
    SYNTHETIC_ONLY_ORDER_REASON,
    UNVERIFIED_EXPLAINABILITY_REASON,
    AdmissionDecision,
    AdmissionPolicy,
    admit_research_artifact,
    SUPPORTED_MODEL_FAMILIES,
)
from .catalog import FeatureSchemaCatalog
from .feature_order import (
    CLINICAL_APPROVED_ORDER_STATUS,
    REGISTERED_FEATURE_ORDER_POLICIES,
    SYNTHETIC_FIXTURE_INPUT_ORDER,
    SYNTHETIC_FIXTURE_ORDER_POLICY_ID,
    SYNTHETIC_FIXTURE_ORDER_POLICY_STATUS,
    FeatureOrderPolicy,
    registered_feature_order_policy,
)
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
    "CALIBRATION_INTEGRITY_EMBEDDED",
    "CLINICAL_APPROVED_ORDER_STATUS",
    "CALIBRATION_INTEGRITY_NONE",
    "CALIBRATION_INTEGRITY_VERIFIED",
    "D047_NON_APPROVAL_REASON",
    "DESCRIPTOR_SCHEMA_PATH",
    "DESCRIPTOR_SCHEMA_VERSION",
    "DirectoryArtifactSource",
    "EMBEDDED_CALIBRATION_REASON",
    "EXPLAINABILITY_CAPABILITIES",
    "EXPLAINABILITY_CAPABILITY",
    "EXPLAINABILITY_VERIFIED_CLAIM",
    "FeatureOrderPolicy",
    "FeatureSchemaCatalog",
    "INTERNAL_EXPLORATORY_LABEL",
    "InMemoryArtifactSource",
    "MAX_ARTIFACT_BYTES",
    "NON_APPROVAL_REASONS",
    "REGISTERED_FEATURE_ORDER_POLICIES",
    "RESEARCH_ONLY",
    "SUPPORTED_MODEL_FAMILIES",
    "SYNTHETIC_FIXTURE_INPUT_ORDER",
    "SYNTHETIC_FIXTURE_ORDER_POLICY_ID",
    "SYNTHETIC_FIXTURE_ORDER_POLICY_STATUS",
    "SYNTHETIC_ONLY_ORDER_REASON",
    "UNVERIFIED_EXPLAINABILITY_REASON",
    "admit_research_artifact",
    "registered_feature_order_policy",
]
