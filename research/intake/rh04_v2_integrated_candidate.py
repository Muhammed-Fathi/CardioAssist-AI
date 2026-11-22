"""RH-04 V2 — integrated deterministic pipeline candidate (synthetic only).

Scope
-----
Isolated candidate (`D-V2-4`, `D-V2-6`). **No production module imports this.**
Synthetic inputs only. The frozen V1 fixture, the default solver and production
inference are untouched.

What this integrates
--------------------
The review's item 7 asks for an end-to-end candidate that actually *uses* the
declared pieces rather than leaving the exact scorer as an unused oracle. This
module chains four declared stages:

1. **Model fit** — ``rh04_v2_model_fit`` (decimal Newton, exact gradient).
2. **Linear scoring** — ``rh04_v2_deterministic_upstream`` (exact rational).
3. **Calibration** — ``rh04_v2_reference_fit`` (decimal reference fit, the
   existing V2 candidate).
4. **Calibrated evaluation** — the affine transform and the signed threshold
   comparison, evaluated on the decimal values.

Every stage is a declared function of its inputs. The pipeline therefore has no
host-dependent operation anywhere, and the test that matters is whether repeated
runs and forced-dispatch runs agree bit for bit.

Honest scope limit
------------------
This is a *candidate*, not a replacement for `offline_io.v2.json`. It does not
regenerate an authoritative expected pack, and it deliberately does not claim
equivalence with sklearn's fit — the review forbids inferring equivalence from
small coefficient differences. What it does claim, and tests, is:

* the objective it minimises is the one it declares;
* its solution matches an independent high-precision oracle;
* the whole chain is reproducible on this host and across forced dispatches.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from typing import Any, Final, Sequence

from research.intake import rh04_v2_deterministic_upstream as upstream
from research.intake import rh04_v2_model_fit as model_fit
from research.intake import rh04_v2_reference_fit as reference_fit

INTEGRATED_CANDIDATE_ID: Final[str] = "rh04.v2.integrated-pipeline/v2"

#: Digest produced by the v1 candidate, which unpacked the calibration tuple as
#: ``(slope, offset)`` and therefore evaluated a reversed affine map. Retained as
#: historical evidence of an incorrect implementation. NEVER a reference.
HISTORICAL_REVERSED_PIPELINE_DIGEST: Final[str] = (
    "19beafb7214c8b2257064cc590c13b9bce523166d7d007e55e389a12f9189951"
)
#: The evaluation threshold used by production (`ai/inference.py`:681) — the
#: calibrated research score is compared with `>=` against this value.
RESEARCH_THRESHOLD: Final[Decimal] = Decimal("0.5")


class IntegratedPipelineError(ValueError):
    """Fail-closed refusal."""


def declared_pipeline() -> dict[str, Any]:
    """The whole chain as one machine-readable declaration."""
    return {
        "candidate_id": INTEGRATED_CANDIDATE_ID,
        "stages": [
            {"name": "model_fit", "protocol_id": model_fit.MODEL_FIT_PROTOCOL_ID},
            {
                "name": "linear_scoring",
                "protocol_id": upstream.EXACT_SCORE_PROTOCOL_ID,
            },
            {
                "name": "calibration",
                "protocol_id": reference_fit.V2_FIT_PROTOCOL_ID,
            },
            {
                "name": "calibrated_evaluation",
                "rule": "affine on decimal values; flag = (score >= 0.5)",
            },
        ],
        "host_dependent_operations": "none",
        "scope": "synthetic-only candidate; not an authoritative expected pack",
    }


def _as_decimal(value: float) -> Decimal:
    if value != value or value in (float("inf"), float("-inf")):
        raise IntegratedPipelineError("non-finite value in the declared pipeline")
    return Decimal(value)


def run_pipeline(
    features: Sequence[Sequence[float]],
    labels: Sequence[int],
    scoring_rows: Sequence[Sequence[float]],
    *,
    c_value: float = 1.0,
    l2_anchor: float = 1e-3,
) -> dict[str, Any]:
    """Fit, score, calibrate and evaluate — all in declared arithmetic."""
    if len(features) != len(labels):
        raise IntegratedPipelineError("feature/label length mismatch")

    fit = model_fit.fit_logistic_decimal(
        features, labels, c_value=c_value
    )
    coefficients = list(fit["coefficients"])
    intercept = float(fit["intercept"])

    exact_scores = upstream.exact_linear_scores(
        coefficients, scoring_rows, intercept
    )
    raw_logits = [upstream.score_as_float(score) for score in exact_scores]

    # Calibrate on the *training* rows, which is the only aligned set available.
    train_scores = upstream.exact_linear_scores(
        coefficients, features, intercept
    )
    train_logits = [upstream.score_as_float(score) for score in train_scores]

    # ``decimal_logistic_fit`` takes *labels* and *raw logits*, not probabilities.
    # It returns ``(a, b)`` where the declared objective is ``eta = a + b*logit``,
    # i.e. **a is the intercept and b is the slope**. The production contract
    # agrees: ``OofLogisticCalibrator.transform_log_odds`` is
    # ``self.intercept + self.slope * raw_logits``.
    #
    # An earlier revision unpacked this as ``slope, offset`` and then evaluated
    # ``slope * logit + offset`` -- reversed. The bug was invisible because the
    # pipeline is still deterministic when its parameters are swapped, so all
    # reproducibility tests passed. It produced digest ``19beafb7...``, which is
    # retained as historical evidence of the incorrect implementation and must
    # never be treated as a reference.
    import numpy as np

    offset, slope = reference_fit.decimal_logistic_fit(
        np.asarray([float(v) for v in labels], dtype=np.float64),
        np.asarray(train_logits, dtype=np.float64),
        l2_anchor=Decimal(_decimal_text(l2_anchor)),
        lower=reference_fit.V2_FIT_LOWER,
        upper=reference_fit.V2_FIT_UPPER,
    )

    with localcontext() as context:
        context.prec = reference_fit.V2_FIT_DECIMAL_PRECISION
        context.rounding = ROUND_HALF_EVEN
        slope_d = Decimal(slope)
        offset_d = Decimal(offset)
        calibrated_log_odds = [
            _decimal_text(slope_d * _as_decimal(value) + offset_d)
            for value in raw_logits
        ]
        calibrated_scores = [
            _decimal_text(_sigmoid_decimal(slope_d * _as_decimal(value) + offset_d))
            for value in raw_logits
        ]
        flags = [
            _as_decimal(float(score)) >= RESEARCH_THRESHOLD
            for score in calibrated_scores
        ]

    return {
        "candidate_id": INTEGRATED_CANDIDATE_ID,
        "model_fit": {
            "coefficients": coefficients,
            "intercept": intercept,
            "iterations": fit["iterations"],
            "gradient_inf_norm": fit["gradient_inf_norm"],
        },
        "calibration": {
            "slope": slope,
            "intercept": offset,
            "ordering": "intercept-first (a, b) per the declared objective",
            "contract": "intercept + slope * raw_logit",
        },
        "raw_logits": raw_logits,
        "calibrated_log_odds": calibrated_log_odds,
        "calibrated_research_scores": calibrated_scores,
        "above_threshold": flags,
        "declared": declared_pipeline(),
    }


def pipeline_digest(result: dict[str, Any]) -> str:
    """Semantic digest of a pipeline run (declaration excluded)."""
    payload = {
        key: value
        for key, value in result.items()
        if key != "declared"
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _sigmoid(value: float) -> float:
    import math

    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    exponent = math.exp(value)
    return exponent / (1.0 + exponent)


def _sigmoid_decimal(value: Decimal) -> Decimal:
    """Decimal logistic, stable for either sign; no libm."""
    if value >= 0:
        return Decimal(1) / (Decimal(1) + (-value).exp())
    exponent = value.exp()
    return exponent / (Decimal(1) + exponent)


def _decimal_text(value: float | Decimal | str) -> str:
    if isinstance(value, Decimal):
        return format(value.normalize(), "e")
    if isinstance(value, str):
        return format(Decimal(value).normalize(), "e")
    return format(Decimal(value).normalize(), "e")
