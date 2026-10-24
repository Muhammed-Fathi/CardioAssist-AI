"""Fail-closed placeholder for a future, separately reviewed real provider.

Nothing in this module can serve a real prediction:

* no model family, preprocessing pipeline, calibration, decision threshold or
  score interpretation is approved in this repository (P-1/P-3 remain
  PENDING/CLOSED; the D-047 run is internal exploratory work only);
* the constructor always raises, so no instance can be produced, stored in
  application state, or reached from ``build_active_provider``;
* there is no import of a model runtime, no artifact loader and no pickle /
  joblib deserialization anywhere in this package.

A future milestone replaces this module only through a reviewed change that
is bound to an artifact admitted for serving by an independent authorisation
record. Until then it stays an explicit, testable refusal.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .types import CadInferenceProvider, CadInferenceRequest

if TYPE_CHECKING:  # Offline-only type: the runtime never imports admission code.
    from ..artifact_admission import AdmissionDecision

REAL_MODEL_PROVIDER_ID = "reviewed_real_model"


class RealModelServingNotAuthorized(RuntimeError):
    """Raised for every attempt to construct or call a real-model provider."""


def _refusal() -> RealModelServingNotAuthorized:
    return RealModelServingNotAuthorized(
        "Real clinical inference is not authorized. Serving requires a separately "
        "reviewed model artifact, an independent serving authorization record and an "
        "implemented inference path; none exists in this release."
    )


class FailClosedRealModelProvider(CadInferenceProvider):
    """Never constructible; present so the refusal is explicit and testable."""

    provider_id = REAL_MODEL_PROVIDER_ID
    data_class = "REAL_MODEL_NOT_AUTHORIZED"
    supports_real_predictions = True

    def __init__(self, admission: "AdmissionDecision | None" = None) -> None:
        # A research-only admission is never sufficient, and this release has
        # no serving-eligible admission at all, so construction is refused
        # unconditionally rather than relying on the caller's argument.
        raise _refusal()

    def predict(self, request: CadInferenceRequest) -> dict[str, Any]:  # pragma: no cover
        raise _refusal()
