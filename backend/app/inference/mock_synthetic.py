"""The one permitted CAD inference implementation: MOCK_SYNTHETIC.

This adapter translates the typed internal request onto the unchanged
deterministic fixture arithmetic in ``backend.app.mock_prediction``. It
performs no fitting, no artifact loading and no network access.
"""

from __future__ import annotations

from typing import Any

from ..contracts import ContractFiles
from ..mock_prediction import build_prediction
from .types import (
    MOCK_SYNTHETIC_DATA_CLASS,
    MOCK_SYNTHETIC_PROVIDER_ID,
    CadInferenceProvider,
    CadInferenceRequest,
    ProviderContractError,
)


class MockSyntheticProvider(CadInferenceProvider):
    """Deterministic, non-clinical mock scoring bound to the approved contracts."""

    provider_id = MOCK_SYNTHETIC_PROVIDER_ID
    data_class = MOCK_SYNTHETIC_DATA_CLASS
    supports_real_predictions = False

    def __init__(self, contracts: ContractFiles) -> None:
        self._contracts = contracts

    def predict(self, request: CadInferenceRequest) -> dict[str, Any]:
        binding = request.model

        # Rebuild the exact registry-shaped mapping that the merged, approved
        # fixture arithmetic expects. Nothing is recomputed or reinterpreted.
        model: dict[str, Any] = {
            "model_id": binding.model_id,
            "feature_schema_id": binding.feature_schema_id,
            "preprocessing_id": binding.preprocessing_id,
            "calibration_id": binding.calibration_id,
            "explanation_config_id": binding.explanation_config_id,
            "explanation_method": binding.explanation_method,
            "validation_status": binding.validation_status,
            "model_performance_ref": binding.model_performance_ref,
            "artifact_sha256": binding.artifact_sha256,
            "preprocessing_sha256": binding.preprocessing_sha256,
            "calibration_sha256": binding.calibration_sha256,
            "base_value": binding.base_value,
        }
        if binding.calibration is not None:
            model["calibration"] = binding.calibration
        provided = {
            feature.name: {"value": feature.value, "unit": feature.unit}
            for feature in request.features
        }
        if len(provided) != len(request.features):
            # Duplicate feature names cannot occur after contract validation;
            # fail closed rather than dropping an assertion silently.
            raise ProviderContractError("Duplicate feature names in an inference request.")
        return build_prediction(
            self._contracts,
            model,
            provided,
            list(request.missing_optional),
            request.request_id,
            request.audit_id,
        )
