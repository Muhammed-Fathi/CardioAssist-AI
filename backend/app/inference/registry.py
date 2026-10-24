"""The single construction site for a CAD inference provider.

Hard-wired by design. There is deliberately:

* no provider identifier, mapping or callable parameter;
* no environment variable, settings file, request field or database row read;
* no dependency-injection hook on ``create_app`` or ``MockState``.

``ACTIVE_PROVIDER_IDS`` is the allowlist enforced at construction. Changing it,
or adding a second entry, requires a reviewed code change that also changes the
tests in ``tests/backend/test_inference_provider.py``.
"""

from __future__ import annotations

from ..contracts import ContractFiles
from .mock_synthetic import MockSyntheticProvider
from .types import (
    MOCK_SYNTHETIC_DATA_CLASS,
    MOCK_SYNTHETIC_PROVIDER_ID,
    CadInferenceProvider,
)

ACTIVE_PROVIDER_IDS = frozenset({MOCK_SYNTHETIC_PROVIDER_ID})


def build_active_provider(contracts: ContractFiles) -> CadInferenceProvider:
    """Return the only provider this application may use."""
    provider = MockSyntheticProvider(contracts)
    if (
        provider.provider_id not in ACTIVE_PROVIDER_IDS
        or provider.data_class != MOCK_SYNTHETIC_DATA_CLASS
        or provider.supports_real_predictions
    ):
        raise RuntimeError(
            "The active CAD inference provider must be the MOCK_SYNTHETIC provider."
        )
    return provider
