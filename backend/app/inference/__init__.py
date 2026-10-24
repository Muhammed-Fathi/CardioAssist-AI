"""Internal CAD inference provider boundary (Track A only).

The runtime has exactly one active provider — ``MOCK_SYNTHETIC`` — built by
:func:`backend.app.inference.registry.build_active_provider` with no selector
argument, environment variable, settings entry or dependency-injection hook.
See ``docs/MODEL_PROVIDER_AND_ARTIFACT_ADMISSION.md``.

Track B (wearable/monitoring observations) never enters this package.
"""

from .mock_synthetic import MockSyntheticProvider
from .real_model import (
    REAL_MODEL_PROVIDER_ID,
    FailClosedRealModelProvider,
    RealModelServingNotAuthorized,
)
from .registry import ACTIVE_PROVIDER_IDS, build_active_provider
from .types import (
    CadFeature,
    CadInferenceProvider,
    CadInferenceRequest,
    CadModelBinding,
    FeatureScalar,
    MOCK_SYNTHETIC_DATA_CLASS,
    MOCK_SYNTHETIC_PROVIDER_ID,
    ProviderContractError,
)

__all__ = [
    "ACTIVE_PROVIDER_IDS",
    "CadFeature",
    "CadInferenceProvider",
    "CadInferenceRequest",
    "CadModelBinding",
    "FailClosedRealModelProvider",
    "FeatureScalar",
    "MOCK_SYNTHETIC_DATA_CLASS",
    "MOCK_SYNTHETIC_PROVIDER_ID",
    "MockSyntheticProvider",
    "ProviderContractError",
    "REAL_MODEL_PROVIDER_ID",
    "RealModelServingNotAuthorized",
    "build_active_provider",
]
