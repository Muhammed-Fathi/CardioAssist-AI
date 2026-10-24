"""Track A (CAD inference) internal provider types.

Track A and Track B are separate: nothing in this package is used by the
monitoring/observation write path, and no monitoring or wearable value can
reach a CAD provider (the existing 422 ``wearable_input_not_valid_for_cad_
inference`` rejection runs first).

These types are internal. They are **not** wire schemas, are not exported by
the OpenAPI document, and deliberately carry no clinical threshold, model
family, calibration or score-interpretation decision.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Mapping

# The value types the approved feature schemas admit for a single feature.
FeatureScalar = int | float | str | bool

# The only provider identity the application may construct. See registry.py.
MOCK_SYNTHETIC_PROVIDER_ID = "mock_synthetic"
MOCK_SYNTHETIC_DATA_CLASS = "MOCK_SYNTHETIC"


class ProviderContractError(RuntimeError):
    """Internal provider failure.

    Never rendered to a client: the existing handler maps unexpected
    exceptions to the approved, detail-free ``500 internal_error`` response.
    """


@dataclass(frozen=True)
class CadFeature:
    """One validated, non-null feature assertion supplied for inference."""

    name: str
    value: FeatureScalar
    unit: str


@dataclass(frozen=True)
class CadModelBinding:
    """The approved registry binding of the model that would serve a request.

    Constructed only from the checked-in MOCK_ONLY model registry that
    ``ContractFiles`` already validates. No artifact is loaded from this
    object; the hashes are the approved placeholder values.
    """

    model_id: str
    feature_schema_id: str
    preprocessing_id: str
    calibration_id: str
    explanation_config_id: str
    explanation_method: str
    validation_status: str
    model_performance_ref: str
    artifact_sha256: str
    preprocessing_sha256: str
    calibration_sha256: str | None
    base_value: float
    calibration: Mapping[str, Any] | None

    @classmethod
    def from_registry_entry(cls, entry: Mapping[str, Any]) -> "CadModelBinding":
        # Explicit key access: a registry shape change fails closed (500)
        # instead of silently producing a partially bound model.
        return cls(
            model_id=entry["model_id"],
            feature_schema_id=entry["feature_schema_id"],
            preprocessing_id=entry["preprocessing_id"],
            calibration_id=entry["calibration_id"],
            explanation_config_id=entry["explanation_config_id"],
            explanation_method=entry["explanation_method"],
            validation_status=entry["validation_status"],
            model_performance_ref=entry["model_performance_ref"],
            artifact_sha256=entry["artifact_sha256"],
            preprocessing_sha256=entry["preprocessing_sha256"],
            calibration_sha256=entry["calibration_sha256"],
            base_value=entry["base_value"],
            calibration=entry.get("calibration"),
        )


@dataclass(frozen=True)
class CadInferenceRequest:
    """Everything a provider is allowed to see for one accepted request.

    There is no contract object, no database handle, no patient record and no
    extra lookup surface here. ``request_id``/``audit_id`` are the identifiers
    the runtime already generated; ``features`` contains only validated,
    non-null assertions and ``missing_optional`` the approved imputation list.
    """

    request_id: str
    audit_id: str
    model: CadModelBinding
    features: tuple[CadFeature, ...]
    missing_optional: tuple[str, ...]


class CadInferenceProvider(ABC):
    """Narrow internal CAD inference interface.

    Implementations must be side-effect free apart from returning the
    response body, which the runtime validates against the approved response
    schema before publishing it.
    """

    provider_id: str
    data_class: str
    supports_real_predictions: bool = False

    @abstractmethod
    def predict(self, request: CadInferenceRequest) -> dict[str, Any]:
        """Return a response body for an already validated Track A request."""
