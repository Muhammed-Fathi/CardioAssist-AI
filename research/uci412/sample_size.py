"""Planning arithmetic for the UCI-412 benchmark — deliberately not an adequacy verdict.

Only the R²-independent out-of-fold outcome-proportion criterion of Riley et al.
(2020) is computed. The shrinkage, optimism and minimum-MAPE criteria each
require an *externally anticipated* Cox–Snell R², which is a human scientific
judgement and is therefore reported as NOT ASSESSED. Events-per-parameter is
reported as a descriptive count only; it is explicitly not a justification.

The numbers here are planning thresholds under stated tolerances, derived from
the audited class counts alone. They contain no model result and cannot be used
to argue that a model is adequate or accurate.
"""
from __future__ import annotations

import math
from typing import Any

from research.uci412.config import DEFAULT_CONFIG, Uci412Config
from research.uci412.feature_schema import DEFAULT_DICTIONARY

SHRINKAGE_TARGET = 0.90
OUTCOME_PROPORTION_HALF_WIDTH = 0.05
Z_95 = 1.96


def outcome_proportion_required_n(
    prevalence: float,
    *,
    half_width: float = OUTCOME_PROPORTION_HALF_WIDTH,
) -> int:
    """Riley 2020 precision-of-the-outcome-proportion criterion (R²- and p-independent)."""
    if not (0.0 < prevalence < 1.0):
        raise ValueError("Prevalence must lie strictly between 0 and 1.")
    if half_width <= 0:
        raise ValueError("The half-width must be positive.")
    return math.ceil(((Z_95 / half_width) ** 2) * prevalence * (1.0 - prevalence))


def events_per_parameter(events: int, parameters: int) -> float:
    if parameters <= 0:
        raise ValueError("The parameter count must be positive.")
    return events / parameters


def planning_summary(
    *,
    n: int = DEFAULT_CONFIG.expected_row_count,
    events: int = DEFAULT_CONFIG.expected_counts[1],
    parameters: int | None = None,
    config: Uci412Config = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Return the R²-independent planning threshold and every non-assessed item."""
    if parameters is None:
        parameters = DEFAULT_DICTIONARY.encoded_parameter_count()
    if not (0 < events < n):
        raise ValueError("Events must lie strictly between 0 and n.")
    prevalence = events / n
    required = outcome_proportion_required_n(prevalence)
    return {
        "framework": "Riley et al. BMJ 2020 binary-outcome sample-size criteria",
        "participants": n,
        "events": events,
        "non_events": n - events,
        "outcome_prevalence": prevalence,
        "reference_coded_parameter_count": parameters,
        "events_per_parameter_descriptive_only": events_per_parameter(events, parameters),
        "events_per_parameter_is_not_a_sample_size_justification": True,
        "outcome_proportion_half_width": OUTCOME_PROPORTION_HALF_WIDTH,
        "outcome_proportion_required_n": required,
        "outcome_proportion_criterion_met": n >= required,
        "outcome_proportion_status": (
            "MET_AT_STATED_HALF_WIDTH" if n >= required else "NOT_MET_AT_STATED_HALF_WIDTH"
        ),
        "r2_dependent_criteria": {
            "shrinkage": "NOT_ASSESSED_NO_HUMAN_REVIEWED_ANTICIPATED_R2",
            "optimism": "NOT_ASSESSED_NO_HUMAN_REVIEWED_ANTICIPATED_R2",
            "minimum_mape": "NOT_ASSESSED_NO_HUMAN_REVIEWED_ANTICIPATED_R2",
        },
        "shrinkage_target_if_later_assessed": SHRINKAGE_TARGET,
        "interpretation": (
            "Planning arithmetic only. A failed outcome-proportion criterion means the internal "
            "exercise is a software/research feasibility benchmark; it cannot support a claim of "
            "clinical predictive adequacy, and the observed performance must never be used to "
            "back-derive an anticipated R²."
        ),
        "uses_observed_model_performance": False,
        "clinical_adequacy_claimed": False,
        "protocol_reference": config.experiment_id,
    }
