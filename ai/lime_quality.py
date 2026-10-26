"""LIME explanation-quality assessment for the research-only AI stack.

This module is deliberately **generation-free**: it never perturbs an instance,
never calls a model and never fits a surrogate. It only converts the numeric
diagnostics produced by :mod:`ai.lime_explainability` (plus an optional
seed-stability report) into an explicit, machine-readable quality verdict.

Why a separate verdict is mandatory
-----------------------------------
A weighted local surrogate can reproduce the model output *at* the explained
instance while still describing the surrounding perturbation neighborhood
poorly. Those two properties are measured by different numbers:

* ``local_fidelity_*`` — surrogate versus an actual model call at the instance.
* ``weighted_r2`` / ``holdout_weighted_r2`` — how much of the model's own
  kernel-weighted output variation the surrogate explains nearby.
* seed stability — whether the reported weights even reproduce across
  perturbation draws.

Local fidelity, neighborhood fidelity and stability are therefore *independent*
dimensions. A low local error is never evidence of good neighborhood fidelity,
and a stable approximation can still be a poor one.

Status precedence (documented, deterministic)
---------------------------------------------
1. ``INVALID`` — a numerical-validity criterion failed. Nothing may be read
   from the weights, not even descriptively.
2. ``LOW_LOCAL_FIDELITY`` — instance or neighborhood fidelity failed, or could
   not be demonstrated (an unproven fit is not accepted as a fit).
3. ``UNSTABLE`` — local fidelity passed but the weights disagree across
   registered seeds.
4. ``UNVERIFIED_STABILITY`` — local fidelity passed but no stability evidence
   was supplied and the policy requires it.
5. ``ACCEPTABLE_LOCAL_APPROXIMATION`` — every registered criterion passed. The
   explanation is *still* a local approximation: it is not an exact Shapley
   decomposition, satisfies no efficiency/local-accuracy guarantee, and is not
   causal or clinical evidence.

Threshold rationale
-------------------
The registered defaults are stated in terms of variance explained and standard
deviations rather than being tuned per fixture:

* ``min_weighted_r2 = 0.5`` — the surrogate must account for at least half of
  the kernel-weighted variance of the model's own outputs in the sampled
  neighborhood. Below that margin the linear account is weaker than the
  variation it claims to summarize.
* ``min_holdout_weighted_r2 = 0.5`` — the same bar on a seeded disjoint split,
  so the fit is not merely an in-sample artifact of one perturbation draw.
* ``max_local_fidelity_error_in_neighborhood_sigma = 0.25`` — the instance-level
  error measured in units of the model-output spread across the neighborhood,
  which keeps the criterion scale-free across probability and log-odds targets.
* ``max_local_fidelity_relative_error = 0.25`` — a coarse absolute guard
  relative to ``max(1, |f(x)|)`` for targets that are near zero.
* ``min_effective_samples = 20`` — Kish effective sample size below which a
  weighted regression has no meaningful precision.
* ``max_design_condition_number = 1e6`` — double precision carries ~16 decimal
  digits; a condition number beyond ``1e6`` costs at least six of them in the
  coefficients.
* stability: ``min_pairwise_spearman = 0.5``,
  ``sign_agreement_fraction = 0.75`` (near-zero weights legitimately flip sign),
  ``top_k_overlap_fraction = 0.6`` over the top 3 fields.

These thresholds are evaluation policy, not statistical guarantees, and they are
never relaxed at runtime to make a fixture pass.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, replace as dataclass_replace
from enum import Enum
from types import MappingProxyType
from typing import Any, Final, Mapping

from ai.errors import ExplainabilityIntegrityError

LIME_QUALITY_SCHEMA_VERSION: Final[str] = "cardioassist.ai.lime_quality/v1"
LIME_QUALITY_POLICY_VERSION: Final[str] = "cardioassist.ai.lime_quality_policy/v1"

QUALITY_DIMENSION_NUMERICAL_VALIDITY: Final[str] = "numerical_validity"
QUALITY_DIMENSION_INSTANCE_FIDELITY: Final[str] = "instance_fidelity"
QUALITY_DIMENSION_NEIGHBORHOOD_FIDELITY: Final[str] = "neighborhood_fidelity"
QUALITY_DIMENSION_STABILITY: Final[str] = "stability"
QUALITY_DIMENSIONS: Final[tuple[str, ...]] = (
    QUALITY_DIMENSION_NUMERICAL_VALIDITY,
    QUALITY_DIMENSION_INSTANCE_FIDELITY,
    QUALITY_DIMENSION_NEIGHBORHOOD_FIDELITY,
    QUALITY_DIMENSION_STABILITY,
)

DIMENSION_PASS: Final[str] = "PASS"
DIMENSION_FAIL: Final[str] = "FAIL"
DIMENSION_NOT_ASSESSED: Final[str] = "NOT_ASSESSED"

CRITERION_PASS: Final[str] = "PASS"
CRITERION_FAIL: Final[str] = "FAIL"
CRITERION_NOT_ASSESSED: Final[str] = "NOT_ASSESSED"

COMPARISON_LE: Final[str] = "<="
COMPARISON_GE: Final[str] = ">="
_COMPARISONS: Final[frozenset[str]] = frozenset({COMPARISON_LE, COMPARISON_GE})

LIME_QUALITY_GUARD_UNRELIABLE: Final[str] = (
    "DO NOT RELY ON THESE FEATURE WEIGHTS as a faithful local account of the "
    "model. This explanation is returned for diagnostic inspection only: use "
    "it to understand why the surrogate failed, not to describe model "
    "behaviour, and never as causal or clinical evidence."
)

LIME_QUALITY_GUARD_ACCEPTABLE: Final[str] = (
    "This explanation passed every registered numerical-validity, local-"
    "fidelity and seed-stability criterion. It remains a local weighted-linear "
    "approximation: not an exact Shapley decomposition, not additive in "
    "probability units, and never causal or clinical advice."
)


class LimeQualityStatus(str, Enum):
    """Registered machine-readable LIME explanation-quality verdicts."""

    ACCEPTABLE_LOCAL_APPROXIMATION = "ACCEPTABLE_LOCAL_APPROXIMATION"
    LOW_LOCAL_FIDELITY = "LOW_LOCAL_FIDELITY"
    UNSTABLE = "UNSTABLE"
    UNVERIFIED_STABILITY = "UNVERIFIED_STABILITY"
    INVALID = "INVALID"

    @property
    def is_acceptable(self) -> bool:
        return self is LimeQualityStatus.ACCEPTABLE_LOCAL_APPROXIMATION


# --------------------------------------------------------------------------- #
# Policy
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class LimeQualityPolicy:
    """Registered acceptance policy for a LIME explanation.

    Every field is an explicit acceptance threshold; none of them changes the
    explanation that was generated. Relaxing a threshold is a documented
    reviewable decision, not a silent default.
    """

    min_weighted_r2: float = 0.5
    min_holdout_weighted_r2: float = 0.5
    max_local_fidelity_error_in_neighborhood_sigma: float = 0.25
    max_local_fidelity_relative_error: float = 0.25
    min_effective_samples: float = 20.0
    max_design_condition_number: float = 1e6
    min_pairwise_spearman: float = 0.5
    sign_agreement_fraction: float = 0.75
    top_k_overlap_fraction: float = 0.6
    min_stability_seeds: int = 3
    top_k: int = 3
    require_holdout_diagnostic: bool = True
    require_stability_assessment: bool = True

    def __post_init__(self) -> None:
        numeric_fields = (
            ("min_weighted_r2", self.min_weighted_r2),
            ("min_holdout_weighted_r2", self.min_holdout_weighted_r2),
            (
                "max_local_fidelity_error_in_neighborhood_sigma",
                self.max_local_fidelity_error_in_neighborhood_sigma,
            ),
            (
                "max_local_fidelity_relative_error",
                self.max_local_fidelity_relative_error,
            ),
            ("min_effective_samples", self.min_effective_samples),
            ("max_design_condition_number", self.max_design_condition_number),
            ("min_pairwise_spearman", self.min_pairwise_spearman),
            ("sign_agreement_fraction", self.sign_agreement_fraction),
            ("top_k_overlap_fraction", self.top_k_overlap_fraction),
        )
        for name, value in numeric_fields:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ExplainabilityIntegrityError(
                    "lime_quality_invalid_policy",
                    f"Quality threshold '{name}' must be numeric.",
                    field=name,
                )
            if not math.isfinite(float(value)):
                raise ExplainabilityIntegrityError(
                    "lime_quality_invalid_policy",
                    f"Quality threshold '{name}' must be finite.",
                    field=name,
                )
        for name, value in (
            ("min_weighted_r2", self.min_weighted_r2),
            ("min_holdout_weighted_r2", self.min_holdout_weighted_r2),
        ):
            if not (-1.0 <= float(value) <= 1.0):
                raise ExplainabilityIntegrityError(
                    "lime_quality_invalid_policy",
                    f"Quality threshold '{name}' must lie within [-1, 1].",
                    field=name,
                )
        for name, value in (
            (
                "max_local_fidelity_error_in_neighborhood_sigma",
                self.max_local_fidelity_error_in_neighborhood_sigma,
            ),
            (
                "max_local_fidelity_relative_error",
                self.max_local_fidelity_relative_error,
            ),
            ("max_design_condition_number", self.max_design_condition_number),
        ):
            if float(value) <= 0.0:
                raise ExplainabilityIntegrityError(
                    "lime_quality_invalid_policy",
                    f"Quality threshold '{name}' must be strictly positive.",
                    field=name,
                )
        if float(self.min_effective_samples) < 3.0:
            raise ExplainabilityIntegrityError(
                "lime_quality_invalid_policy",
                "min_effective_samples must be >= 3.",
                field="min_effective_samples",
            )
        for name, value in (
            ("min_pairwise_spearman", self.min_pairwise_spearman),
            ("sign_agreement_fraction", self.sign_agreement_fraction),
            ("top_k_overlap_fraction", self.top_k_overlap_fraction),
        ):
            if not (-1.0 <= float(value) <= 1.0):
                raise ExplainabilityIntegrityError(
                    "lime_quality_invalid_policy",
                    f"Quality threshold '{name}' must lie within [-1, 1].",
                    field=name,
                )
        if isinstance(self.min_stability_seeds, bool) or not isinstance(
            self.min_stability_seeds, int
        ) or self.min_stability_seeds < 2:
            raise ExplainabilityIntegrityError(
                "lime_quality_invalid_policy",
                "min_stability_seeds must be an integer >= 2.",
                field="min_stability_seeds",
            )
        if isinstance(self.top_k, bool) or not isinstance(self.top_k, int) or (
            self.top_k < 1
        ):
            raise ExplainabilityIntegrityError(
                "lime_quality_invalid_policy",
                "top_k must be a positive integer.",
                field="top_k",
            )
        if not isinstance(self.require_holdout_diagnostic, bool) or not isinstance(
            self.require_stability_assessment, bool
        ):
            raise ExplainabilityIntegrityError(
                "lime_quality_invalid_policy",
                "require_holdout_diagnostic and require_stability_assessment "
                "must be booleans.",
            )

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "policy_version": LIME_QUALITY_POLICY_VERSION,
            "min_weighted_r2": float(self.min_weighted_r2),
            "min_holdout_weighted_r2": float(self.min_holdout_weighted_r2),
            "max_local_fidelity_error_in_neighborhood_sigma": float(
                self.max_local_fidelity_error_in_neighborhood_sigma
            ),
            "max_local_fidelity_relative_error": float(
                self.max_local_fidelity_relative_error
            ),
            "min_effective_samples": float(self.min_effective_samples),
            "max_design_condition_number": float(self.max_design_condition_number),
            "min_pairwise_spearman": float(self.min_pairwise_spearman),
            "sign_agreement_fraction": float(self.sign_agreement_fraction),
            "top_k_overlap_fraction": float(self.top_k_overlap_fraction),
            "min_stability_seeds": int(self.min_stability_seeds),
            "top_k": int(self.top_k),
            "require_holdout_diagnostic": bool(self.require_holdout_diagnostic),
            "require_stability_assessment": bool(
                self.require_stability_assessment
            ),
        }

    @property
    def policy_sha256(self) -> str:
        payload = json.dumps(
            self.to_json_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


# --------------------------------------------------------------------------- #
# Criteria and evidence
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class LimeQualityCriterion:
    """One evaluated acceptance criterion with its observed value and verdict."""

    name: str
    dimension: str
    observed: float | None
    threshold: float | None
    comparison: str
    outcome: str
    unit: str
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "dimension": self.dimension,
            "observed": self.observed,
            "threshold": self.threshold,
            "comparison": self.comparison,
            "outcome": self.outcome,
            "unit": self.unit,
            "rationale": self.rationale,
        }


@dataclass(frozen=True, slots=True)
class LimeQualityEvidence:
    """Neutral numeric inputs to quality assessment (no model, no data)."""

    n_features: int
    num_perturbations: int
    explained_quantity: str
    scale: str
    reference_scheme: str
    model_prediction_at_instance: float
    surrogate_prediction_at_instance: float
    local_fidelity_abs_error: float
    local_fidelity_relative_error: float
    neighborhood_output_weighted_sd: float | None
    local_fidelity_error_in_neighborhood_sigma: float | None
    weighted_r2: float | None
    holdout_weighted_r2: float | None
    holdout_rows: int
    n_effective_samples: float
    design_condition_number: float
    max_abs_lime_weight: float | None
    all_weights_finite: bool
    attribution_count: int

    @staticmethod
    def _finite_or_none(value: Any) -> float | None:
        if value is None:
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):  # pragma: no cover - defensive
            return None
        return numeric if math.isfinite(numeric) else None

    @classmethod
    def _required_scalar(cls, value: Any) -> float:
        """Missing required diagnostics become NaN, never a fabricated 0.0.

        A NaN compares False against every registered threshold, so a missing
        diagnostic always fails closed instead of looking perfect.
        """
        numeric = cls._finite_or_none(value)
        return math.nan if numeric is None else numeric

    @classmethod
    def from_explanation(cls, explanation: Any) -> "LimeQualityEvidence":
        """Build evidence from a ``FaithfulLimeExplanation``-like object."""
        attributions = tuple(getattr(explanation, "attributions", ()) or ())
        weights: list[float] = []
        for item in attributions:
            value = getattr(item, "lime_weight", None)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                weights.append(float(value))
        all_finite = bool(weights) and all(math.isfinite(v) for v in weights)
        max_abs = max((abs(v) for v in weights), default=None)
        return cls(
            n_features=int(getattr(explanation, "n_features", len(attributions))),
            num_perturbations=int(
                getattr(explanation, "num_perturbations", 0) or 0
            ),
            explained_quantity=str(getattr(explanation, "explained_quantity", "")),
            scale=str(getattr(explanation, "scale", "")),
            reference_scheme=str(getattr(explanation, "reference_scheme", "")),
            model_prediction_at_instance=cls._required_scalar(
                getattr(explanation, "model_prediction_at_instance", None)
            ),
            surrogate_prediction_at_instance=cls._required_scalar(
                getattr(explanation, "surrogate_prediction_at_instance", None)
            ),
            local_fidelity_abs_error=cls._required_scalar(
                getattr(explanation, "local_fidelity_abs_error", None)
            ),
            local_fidelity_relative_error=cls._required_scalar(
                getattr(explanation, "local_fidelity_relative_error", None)
            ),
            neighborhood_output_weighted_sd=cls._finite_or_none(
                getattr(explanation, "neighborhood_output_weighted_sd", None)
            ),
            local_fidelity_error_in_neighborhood_sigma=cls._finite_or_none(
                getattr(
                    explanation,
                    "local_fidelity_error_in_neighborhood_sigma",
                    None,
                )
            ),
            weighted_r2=cls._finite_or_none(
                getattr(explanation, "weighted_r2", None)
            ),
            holdout_weighted_r2=cls._finite_or_none(
                getattr(explanation, "holdout_weighted_r2", None)
            ),
            holdout_rows=int(getattr(explanation, "holdout_rows", 0) or 0),
            n_effective_samples=cls._required_scalar(
                getattr(explanation, "n_effective_samples", None)
            ),
            design_condition_number=float(
                cls._finite_or_none(
                    getattr(explanation, "design_condition_number", None)
                )
                or math.inf
            ),
            max_abs_lime_weight=cls._finite_or_none(max_abs),
            all_weights_finite=all_finite,
            attribution_count=len(attributions),
        )

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "LimeQualityEvidence":
        """Build evidence from the serialized ``to_dict()`` explanation payload."""
        fidelity = payload.get("fidelity", {}) or {}
        surrogate = payload.get("surrogate", {}) or {}
        sampling = payload.get("sampling", {}) or {}
        attributions = payload.get("attributions", []) or []
        weights = [
            float(item["lime_weight"])
            for item in attributions
            if isinstance(item, Mapping) and "lime_weight" in item
        ]
        all_finite = bool(weights) and all(math.isfinite(v) for v in weights)
        reference = payload.get("reference", {}) or {}
        return cls(
            n_features=int(
                len(attributions) or payload.get("n_features", 0) or 0
            ),
            num_perturbations=int(sampling.get("num_perturbations", 0) or 0),
            explained_quantity=str(payload.get("explained_quantity", "")),
            scale=str(payload.get("scale", "")),
            reference_scheme=str(reference.get("scheme", "")),
            model_prediction_at_instance=cls._required_scalar(
                fidelity.get("model_prediction_at_instance")
            ),
            surrogate_prediction_at_instance=cls._required_scalar(
                surrogate.get("surrogate_prediction_at_instance")
            ),
            local_fidelity_abs_error=cls._required_scalar(
                fidelity.get("local_fidelity_abs_error")
            ),
            local_fidelity_relative_error=cls._required_scalar(
                fidelity.get("local_fidelity_relative_error")
            ),
            neighborhood_output_weighted_sd=cls._finite_or_none(
                fidelity.get("neighborhood_output_weighted_sd")
            ),
            local_fidelity_error_in_neighborhood_sigma=cls._finite_or_none(
                fidelity.get(
                    "local_fidelity_error_in_neighborhood_sigma"
                )
            ),
            weighted_r2=cls._finite_or_none(fidelity.get("weighted_r2")),
            holdout_weighted_r2=cls._finite_or_none(
                fidelity.get("holdout_weighted_r2")
            ),
            holdout_rows=int(fidelity.get("holdout_rows", 0) or 0),
            n_effective_samples=cls._required_scalar(
                surrogate.get("n_effective_samples")
            ),
            design_condition_number=float(
                cls._finite_or_none(
                    surrogate.get("design_condition_number")
                )
                or math.inf
            ),
            max_abs_lime_weight=cls._finite_or_none(
                max((abs(v) for v in weights), default=None)
            ),
            all_weights_finite=all_finite,
            attribution_count=len(attributions),
        )


# --------------------------------------------------------------------------- #
# Assessment
# --------------------------------------------------------------------------- #


def _criterion(
    *,
    name: str,
    dimension: str,
    observed: float | None,
    threshold: float | None,
    comparison: str,
    unit: str,
    rationale: str,
    not_assessed: bool = False,
) -> LimeQualityCriterion:
    if not_assessed or observed is None or threshold is None:
        outcome = CRITERION_NOT_ASSESSED
    else:
        passed = (
            observed <= threshold
            if comparison == COMPARISON_LE
            else observed >= threshold
        )
        outcome = CRITERION_PASS if passed else CRITERION_FAIL
    return LimeQualityCriterion(
        name=name,
        dimension=dimension,
        observed=observed,
        threshold=threshold,
        comparison=comparison,
        outcome=outcome,
        unit=unit,
        rationale=rationale,
    )


_CRITERION_FIELDS: Final[tuple[str, ...]] = (
    "name",
    "dimension",
    "observed",
    "threshold",
    "comparison",
    "unit",
    "rationale",
)


def _criteria_for(
    evidence: LimeQualityEvidence,
    policy: LimeQualityPolicy,
    stability: Any | None,
) -> tuple[LimeQualityCriterion, ...]:
    """Build the registered criterion table for one explanation (declarative)."""
    # Numerical-validity criteria are always evaluable: a non-finite value is
    # itself the failure, never an excuse to skip the criterion.
    condition_number = evidence.design_condition_number
    weights_usable = (
        1.0
        if evidence.all_weights_finite
        and evidence.max_abs_lime_weight is not None
        and evidence.max_abs_lime_weight > 0.0
        else 0.0
    )
    instance_finite = (
        1.0
        if math.isfinite(evidence.model_prediction_at_instance)
        and math.isfinite(evidence.surrogate_prediction_at_instance)
        else 0.0
    )
    rows: list[tuple[Any, ...]] = [
        (
            "effective_samples",
            QUALITY_DIMENSION_NUMERICAL_VALIDITY,
            evidence.n_effective_samples,
            float(policy.min_effective_samples),
            COMPARISON_GE,
            "kish_effective_samples",
            "Weighted regression precision collapses when the kernel-weighted "
            "effective sample size is small.",
        ),
        (
            "design_condition_number",
            QUALITY_DIMENSION_NUMERICAL_VALIDITY,
            condition_number,
            float(policy.max_design_condition_number),
            COMPARISON_LE,
            "condition_number",
            "Ill-conditioned weighted normal equations destroy coefficient "
            "precision regardless of the fitted values.",
        ),
        (
            "surrogate_weights_finite_and_nonzero",
            QUALITY_DIMENSION_NUMERICAL_VALIDITY,
            weights_usable,
            1.0,
            COMPARISON_GE,
            "boolean",
            "Non-finite or all-zero coefficient vectors carry no local "
            "information (1.0 = every weight finite with a non-zero maximum).",
        ),
        (
            "instance_target_value_finite",
            QUALITY_DIMENSION_NUMERICAL_VALIDITY,
            instance_finite,
            1.0,
            COMPARISON_GE,
            "boolean",
            "Both the actual model output and the surrogate value at the "
            "instance must be finite to report any fidelity measure.",
        ),
        (
            "attribution_count_matches_feature_count",
            QUALITY_DIMENSION_NUMERICAL_VALIDITY,
            float(evidence.attribution_count),
            float(max(evidence.n_features, 1)),
            COMPARISON_GE,
            "features",
            "Every registered panel field must receive exactly one attribution "
            "or the feature lineage is incomplete.",
        ),
        (
            "local_fidelity_relative_error",
            QUALITY_DIMENSION_INSTANCE_FIDELITY,
            evidence.local_fidelity_relative_error,
            float(policy.max_local_fidelity_relative_error),
            COMPARISON_LE,
            "relative_error_vs_max_1_abs_target",
            "Absolute instance-level guard for targets close to zero; the "
            "primary instance criterion is the sigma-scaled error below.",
        ),
        (
            "local_fidelity_error_in_neighborhood_sigma",
            QUALITY_DIMENSION_INSTANCE_FIDELITY,
            evidence.local_fidelity_error_in_neighborhood_sigma,
            float(policy.max_local_fidelity_error_in_neighborhood_sigma),
            COMPARISON_LE,
            "model_output_sd_units",
            "Scale-free instance error: the surrogate must reproduce the "
            "model's own output at the explained point to within a fraction of "
            "the neighborhood's output spread.",
        ),
        (
            "weighted_r2",
            QUALITY_DIMENSION_NEIGHBORHOOD_FIDELITY,
            evidence.weighted_r2,
            float(policy.min_weighted_r2),
            COMPARISON_GE,
            "weighted_variance_explained",
            "Share of the kernel-weighted model-output variance the surrogate "
            "explains across the sampled neighborhood.",
        ),
    ]
    if policy.require_holdout_diagnostic:
        rows.append(
            (
                "holdout_weighted_r2",
                QUALITY_DIMENSION_NEIGHBORHOOD_FIDELITY,
                evidence.holdout_weighted_r2,
                float(policy.min_holdout_weighted_r2),
                COMPARISON_GE,
                "heldout_weighted_variance_explained",
                "Variance explained on a seeded disjoint split of the same "
                "neighborhood; prevents in-sample-only acceptance.",
            )
        )
    if policy.require_stability_assessment:
        seeds = tuple(getattr(stability, "seeds", ()) or ())
        rows.extend(
            [
                (
                    "stability_assessed",
                    QUALITY_DIMENSION_STABILITY,
                    float(len(seeds)) if stability is not None else None,
                    float(policy.min_stability_seeds),
                    COMPARISON_GE,
                    "registered_seeds",
                    "A verdict without repeated perturbation draws cannot "
                    "distinguish a reproducible weight from sampling noise.",
                ),
                (
                    "stability_min_pairwise_spearman",
                    QUALITY_DIMENSION_STABILITY,
                    None
                    if stability is None
                    else LimeQualityEvidence._finite_or_none(
                        getattr(stability, "min_pairwise_spearman", None)
                    ),
                    float(policy.min_pairwise_spearman),
                    COMPARISON_GE,
                    "spearman_rho",
                    "Rank agreement of the full weight vector across seeds.",
                ),
                (
                    "stability_sign_agreement_fraction",
                    QUALITY_DIMENSION_STABILITY,
                    None
                    if stability is None
                    else LimeQualityEvidence._finite_or_none(
                        getattr(stability, "sign_agreement_fraction", None)
                    ),
                    float(policy.sign_agreement_fraction),
                    COMPARISON_GE,
                    "fraction",
                    "Fraction of seed-pairs whose coefficient signs agree; "
                    "near-zero weights may legitimately flip sign, hence < 1.",
                ),
                (
                    "stability_top_k_overlap_fraction",
                    QUALITY_DIMENSION_STABILITY,
                    None
                    if stability is None
                    else LimeQualityEvidence._finite_or_none(
                        getattr(stability, "top_k_overlap_fraction", None)
                    ),
                    float(policy.top_k_overlap_fraction),
                    COMPARISON_GE,
                    "fraction",
                    "Agreement of the highest-|weight| fields across seeds, the "
                    "part of the explanation a reader actually ranks.",
                ),
            ]
        )
    return tuple(
        _criterion(**dict(zip(_CRITERION_FIELDS, row))) for row in rows
    )


def _dimension_outcomes(
    criteria: tuple[LimeQualityCriterion, ...],
) -> dict[str, str]:
    outcomes: dict[str, str] = {}
    for dimension in QUALITY_DIMENSIONS:
        relevant = [c for c in criteria if c.dimension == dimension]
        if not relevant:
            # A dimension with no criteria exists only when the policy itself
            # disabled it (e.g. require_stability_assessment=False), so it is
            # skipped rather than failed. Every other dimension always has at
            # least one registered criterion.
            outcomes[dimension] = (
                DIMENSION_PASS
                if dimension == QUALITY_DIMENSION_STABILITY
                else DIMENSION_NOT_ASSESSED
            )
        elif any(c.outcome == CRITERION_FAIL for c in relevant):
            outcomes[dimension] = DIMENSION_FAIL
        elif any(c.outcome == CRITERION_NOT_ASSESSED for c in relevant):
            outcomes[dimension] = DIMENSION_NOT_ASSESSED
        else:
            outcomes[dimension] = DIMENSION_PASS
    return outcomes


def _fmt(value: float | None, digits: int = 4) -> str:
    if value is None or not math.isfinite(float(value)):
        return "not_available"
    return f"{float(value):.{digits}f}"


def _resolve_status(dimensions: Mapping[str, str]) -> LimeQualityStatus:
    if dimensions[QUALITY_DIMENSION_NUMERICAL_VALIDITY] != DIMENSION_PASS:
        return LimeQualityStatus.INVALID
    for dimension in (
        QUALITY_DIMENSION_INSTANCE_FIDELITY,
        QUALITY_DIMENSION_NEIGHBORHOOD_FIDELITY,
    ):
        if dimensions[dimension] != DIMENSION_PASS:
            return LimeQualityStatus.LOW_LOCAL_FIDELITY
    if dimensions[QUALITY_DIMENSION_STABILITY] == DIMENSION_NOT_ASSESSED:
        return LimeQualityStatus.UNVERIFIED_STABILITY
    if dimensions[QUALITY_DIMENSION_STABILITY] == DIMENSION_FAIL:
        return LimeQualityStatus.UNSTABLE
    return LimeQualityStatus.ACCEPTABLE_LOCAL_APPROXIMATION


def _warnings_for(
    *,
    status: LimeQualityStatus,
    dimensions: Mapping[str, str],
    criteria: tuple[LimeQualityCriterion, ...],
    evidence: LimeQualityEvidence,
    stability: Any | None,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if status is LimeQualityStatus.INVALID:
        failed = [
            c.name
            for c in criteria
            if c.dimension == QUALITY_DIMENSION_NUMERICAL_VALIDITY
            and c.outcome != CRITERION_PASS
        ]
        warnings.append(
            "Numerical validity failed for: " + ", ".join(failed) + "."
        )
    if dimensions[QUALITY_DIMENSION_INSTANCE_FIDELITY] != DIMENSION_PASS:
        warnings.append(
            "Instance fidelity is insufficient: surrogate-versus-model error "
            "at the explained instance is "
            f"{_fmt(evidence.local_fidelity_abs_error, 6)} "
            f"(relative {_fmt(evidence.local_fidelity_relative_error)}, "
            "sigma-scaled "
            f"{_fmt(evidence.local_fidelity_error_in_neighborhood_sigma)})."
        )
    if dimensions[QUALITY_DIMENSION_NEIGHBORHOOD_FIDELITY] != DIMENSION_PASS:
        warnings.append(
            "Neighborhood fidelity is insufficient: the surrogate explains "
            f"weighted R^2 {_fmt(evidence.weighted_r2)} in-sample and "
            f"{_fmt(evidence.holdout_weighted_r2)} on "
            f"{evidence.holdout_rows} held-out perturbation rows. A small "
            "instance-level error does NOT imply good neighborhood fidelity."
        )
    if dimensions[QUALITY_DIMENSION_STABILITY] == DIMENSION_FAIL:
        warnings.append(
            "Seed stability failed: repeated perturbation draws disagree "
            f"(min pairwise Spearman "
            f"{_fmt(getattr(stability, 'min_pairwise_spearman', None))}, "
            "sign agreement "
            f"{_fmt(getattr(stability, 'sign_agreement_fraction', None))}, "
            "top-k overlap "
            f"{_fmt(getattr(stability, 'top_k_overlap_fraction', None))}). "
            "Stability is independent of fidelity: the same weights also fail "
            "to reproduce across seeds."
        )
    if dimensions[QUALITY_DIMENSION_STABILITY] == DIMENSION_NOT_ASSESSED:
        warnings.append(
            "Seed stability was not assessed; an unverified explanation is "
            "not accepted, and stability must be shown separately from local "
            "fidelity."
        )
    if (
        dimensions[QUALITY_DIMENSION_INSTANCE_FIDELITY] == DIMENSION_PASS
        and dimensions[QUALITY_DIMENSION_NEIGHBORHOOD_FIDELITY] != DIMENSION_PASS
    ):
        warnings.append(
            "The surrogate matches the model at the explained instance "
            f"(abs error {_fmt(evidence.local_fidelity_abs_error, 6)}) while "
            "describing the surrounding neighborhood poorly; small local "
            "prediction error must not be read as a faithful local account."
        )
    if (
        dimensions[QUALITY_DIMENSION_STABILITY] == DIMENSION_FAIL
        and dimensions[QUALITY_DIMENSION_NEIGHBORHOOD_FIDELITY] == DIMENSION_PASS
    ):
        warnings.append(
            "The surrogate fits this neighborhood but its weights are "
            "seed-sensitive; a stable approximation and a faithful "
            "approximation are different properties and both are required."
        )
    if status.is_acceptable:
        warnings.append(
            "Accepted as a local approximation only: weights remain "
            "conditional on the perturbation distribution, kernel width, "
            "ridge penalty, reference scheme and seed, and are not Shapley "
            "values."
        )
    return tuple(warnings)


def _recommended_action(status: LimeQualityStatus) -> str:
    if status is LimeQualityStatus.ACCEPTABLE_LOCAL_APPROXIMATION:
        return (
            "Report the weights as a local approximation alongside the exact "
            "SHAP explanation; never equate the two numerically or causally."
        )
    if status is LimeQualityStatus.LOW_LOCAL_FIDELITY:
        return (
            "Do not interpret the weights. Re-run with more perturbations, a "
            "smaller ridge penalty, or a reference scheme better aligned with "
            "the neighborhood under study; otherwise use the exact SHAP "
            "explanation only."
        )
    if status is LimeQualityStatus.UNSTABLE:
        return (
            "Do not interpret the weights. Report the stability diagnostics, "
            "increase perturbations, and use the exact SHAP explanation for "
            "any substantive statement."
        )
    if status is LimeQualityStatus.UNVERIFIED_STABILITY:
        return (
            "Do not certify the explanation. Assess seed stability with at "
            "least the registered minimum number of seeds before reporting."
        )
    return (
        "Discard the explanation; the surrogate is numerically invalid. "
        "Inspect the generation diagnostics rather than the weights."
    )


@dataclass(frozen=True, slots=True)
class LimeQualityAssessment:
    """Machine-readable verdict with per-criterion evidence and warnings."""

    status: LimeQualityStatus
    policy: LimeQualityPolicy
    dimensions: Mapping[str, str]
    criteria: tuple[LimeQualityCriterion, ...]
    warnings: tuple[str, ...]
    stable_explanation: bool | None
    stability_seeds: tuple[int, ...]
    stability_summary: Mapping[str, Any] | None
    evidence: LimeQualityEvidence

    @property
    def is_reliable_for_interpretation(self) -> bool:
        return self.status is LimeQualityStatus.ACCEPTABLE_LOCAL_APPROXIMATION

    @property
    def is_diagnostic_only(self) -> bool:
        return not self.is_reliable_for_interpretation

    @property
    def interpretation_guard(self) -> str:
        if self.is_reliable_for_interpretation:
            return LIME_QUALITY_GUARD_ACCEPTABLE
        return LIME_QUALITY_GUARD_UNRELIABLE

    @property
    def recommended_action(self) -> str:
        return _recommended_action(self.status)

    @property
    def failed_criteria(self) -> tuple[str, ...]:
        return tuple(
            c.name for c in self.criteria if c.outcome == CRITERION_FAIL
        )

    @property
    def unassessed_criteria(self) -> tuple[str, ...]:
        return tuple(
            c.name
            for c in self.criteria
            if c.outcome == CRITERION_NOT_ASSESSED
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": LIME_QUALITY_SCHEMA_VERSION,
            "status": self.status.value,
            "is_reliable_for_interpretation": self.is_reliable_for_interpretation,
            "is_diagnostic_only": self.is_diagnostic_only,
            "dimensions": dict(self.dimensions),
            "criteria": [c.to_dict() for c in self.criteria],
            "failed_criteria": list(self.failed_criteria),
            "unassessed_criteria": list(self.unassessed_criteria),
            "warnings": list(self.warnings),
            "interpretation_guard": self.interpretation_guard,
            "recommended_action": self.recommended_action,
            "stable_explanation": self.stable_explanation,
            "stability_seeds": list(self.stability_seeds),
            "stability_summary": (
                None
                if self.stability_summary is None
                else dict(self.stability_summary)
            ),
            "policy_sha256": self.policy.policy_sha256,
            "policy": self.policy.to_json_dict(),
        }


def _stability_summary(stability: Any) -> dict[str, Any]:
    def _safe(value: Any) -> Any:
        if isinstance(value, bool) or value is None:
            return value
        if isinstance(value, int):
            return value
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        return numeric if math.isfinite(numeric) else None

    return {
        "assessment": str(getattr(stability, "stability_assessment", "")),
        "seeds": [int(s) for s in getattr(stability, "seeds", ())],
        "top_k": int(getattr(stability, "top_k", 0) or 0),
        "min_pairwise_spearman": _safe(
            getattr(stability, "min_pairwise_spearman", None)
        ),
        "mean_pairwise_spearman": _safe(
            getattr(stability, "mean_pairwise_spearman", None)
        ),
        "sign_agreement_fraction": _safe(
            getattr(stability, "sign_agreement_fraction", None)
        ),
        "top_k_overlap_fraction": _safe(
            getattr(stability, "top_k_overlap_fraction", None)
        ),
        "max_feature_weight_std": _safe(
            getattr(stability, "max_feature_weight_std", None)
        ),
        "max_abs_weight_deviation_from_reference_seed": _safe(
            getattr(
                stability, "max_abs_weight_deviation_from_reference_seed", None
            )
        ),
        "max_local_prediction_abs_deviation": _safe(
            getattr(stability, "max_local_prediction_abs_deviation", None)
        ),
        "per_seed_fidelity_statuses": [
            str(s)
            for s in getattr(stability, "per_seed_fidelity_statuses", ())
        ],
        "runtime_seconds": _safe(getattr(stability, "runtime_seconds", None)),
    }


def assess_lime_quality_from_evidence(
    evidence: LimeQualityEvidence,
    *,
    policy: LimeQualityPolicy | None = None,
    stability: Any | None = None,
) -> LimeQualityAssessment:
    """Deterministically classify one explanation from its own diagnostics."""
    active_policy = policy if policy is not None else LimeQualityPolicy()
    criteria = _criteria_for(evidence, active_policy, stability)
    dimensions = _dimension_outcomes(criteria)
    status = _resolve_status(dimensions)
    warnings = _warnings_for(
        status=status,
        dimensions=dimensions,
        criteria=criteria,
        evidence=evidence,
        stability=stability,
    )
    stable: bool | None = None
    seeds: tuple[int, ...] = ()
    summary: Mapping[str, Any] | None = None
    if stability is not None:
        seeds = tuple(int(s) for s in getattr(stability, "seeds", ()))
        assessment = str(getattr(stability, "stability_assessment", ""))
        stable = assessment == "STABLE_WITHIN_REGISTERED_TOLERANCE"
        summary = MappingProxyType(_stability_summary(stability))
    return LimeQualityAssessment(
        status=status,
        policy=active_policy,
        dimensions=MappingProxyType(dict(dimensions)),
        criteria=criteria,
        warnings=warnings,
        stable_explanation=stable,
        stability_seeds=seeds,
        stability_summary=summary,
        evidence=evidence,
    )


@dataclass(frozen=True, slots=True)
class _StabilityEvidenceView:
    """Read-only view over a serialized stability summary."""

    seeds: tuple[int, ...]
    top_k: int
    stability_assessment: str
    min_pairwise_spearman: float | None
    mean_pairwise_spearman: float | None
    sign_agreement_fraction: float | None
    top_k_overlap_fraction: float | None
    max_feature_weight_std: float | None
    max_abs_weight_deviation_from_reference_seed: float | None
    max_local_prediction_abs_deviation: float | None
    per_seed_fidelity_statuses: tuple[str, ...]
    runtime_seconds: float | None


def _attached_stability(explanation_or_payload: Any) -> Any | None:
    """Recover the stability evidence already attached to an explanation.

    Summary numbers travel with the explanation payload, so re-assessing a
    certified explanation (or its JSON round-trip) reproduces the same verdict
    instead of silently degrading to ``UNVERIFIED_STABILITY``.
    """
    if isinstance(explanation_or_payload, Mapping):
        quality = explanation_or_payload.get("quality")
        if not isinstance(quality, Mapping):
            return None
        summary = quality.get("stability_summary")
    else:
        assessment = getattr(explanation_or_payload, "quality", None)
        summary = getattr(assessment, "stability_summary", None)
    if not isinstance(summary, Mapping):
        return None
    seeds = tuple(int(seed) for seed in summary.get("seeds", ()) or ())
    if not seeds:
        return None
    return _StabilityEvidenceView(
        seeds=seeds,
        top_k=int(summary.get("top_k", 0) or 0),
        stability_assessment=str(summary.get("assessment", "")),
        min_pairwise_spearman=LimeQualityEvidence._finite_or_none(
            summary.get("min_pairwise_spearman")
        ),
        mean_pairwise_spearman=LimeQualityEvidence._finite_or_none(
            summary.get("mean_pairwise_spearman")
        ),
        sign_agreement_fraction=LimeQualityEvidence._finite_or_none(
            summary.get("sign_agreement_fraction")
        ),
        top_k_overlap_fraction=LimeQualityEvidence._finite_or_none(
            summary.get("top_k_overlap_fraction")
        ),
        max_feature_weight_std=LimeQualityEvidence._finite_or_none(
            summary.get("max_feature_weight_std")
        ),
        max_abs_weight_deviation_from_reference_seed=(
            LimeQualityEvidence._finite_or_none(
                summary.get("max_abs_weight_deviation_from_reference_seed")
            )
        ),
        max_local_prediction_abs_deviation=(
            LimeQualityEvidence._finite_or_none(
                summary.get("max_local_prediction_abs_deviation")
            )
        ),
        per_seed_fidelity_statuses=tuple(
            str(s) for s in summary.get("per_seed_fidelity_statuses", ()) or ()
        ),
        runtime_seconds=LimeQualityEvidence._finite_or_none(
            summary.get("runtime_seconds")
        ),
    )


def assess_lime_quality(
    explanation_or_payload: Any,
    *,
    policy: LimeQualityPolicy | None = None,
    stability: Any | None = None,
) -> LimeQualityAssessment:
    """Assess a generated LIME explanation (object or serialized payload).

    ``stability`` is an optional :class:`ai.lime_explainability.LimeStabilityReport`
    (or any object exposing the same numeric attributes). When it is omitted,
    the stability evidence already attached to the explanation is reused, so
    re-assessing a certified explanation reproduces its verdict. Supplying
    stability evidence cannot improve fidelity: the dimensions are evaluated
    independently.
    """
    if isinstance(explanation_or_payload, Mapping):
        evidence = LimeQualityEvidence.from_mapping(explanation_or_payload)
    else:
        evidence = LimeQualityEvidence.from_explanation(explanation_or_payload)
    effective_stability = (
        stability
        if stability is not None
        else _attached_stability(explanation_or_payload)
    )
    return assess_lime_quality_from_evidence(
        evidence, policy=policy, stability=effective_stability
    )


def certify_lime_explanation(
    explanation: Any,
    *,
    policy: LimeQualityPolicy | None = None,
    stability: Any | None = None,
) -> Any:
    """Return a copy of ``explanation`` carrying the full quality assessment."""
    assessment = assess_lime_quality(
        explanation, policy=policy, stability=stability
    )
    try:
        return dataclass_replace(explanation, quality=assessment)
    except TypeError as exc:  # pragma: no cover - defensive
        raise ExplainabilityIntegrityError(
            "lime_quality_certification_failed",
            "Explanation object does not accept a quality assessment.",
        ) from exc


def require_acceptable_lime_quality(
    explanation_or_assessment: Any,
    *,
    stability: Any | None = None,
    policy: LimeQualityPolicy | None = None,
) -> LimeQualityAssessment:
    """Fail closed unless the LIME explanation is acceptable for interpretation."""
    if isinstance(explanation_or_assessment, LimeQualityAssessment):
        assessment = explanation_or_assessment
    else:
        assessment = assess_lime_quality(
            explanation_or_assessment, policy=policy, stability=stability
        )
    if not assessment.is_reliable_for_interpretation:
        raise ExplainabilityIntegrityError(
            "lime_quality_not_acceptable",
            "LIME explanation is not acceptable for interpretation "
            f"(status {assessment.status.value}); failed criteria: "
            + (", ".join(assessment.failed_criteria) or "none")
            + "; unassessed criteria: "
            + (", ".join(assessment.unassessed_criteria) or "none")
            + ". Feature weights must not be relied upon as a faithful local "
            "account of the model.",
        )
    return assessment


__all__ = [
    "CRITERION_FAIL",
    "CRITERION_NOT_ASSESSED",
    "CRITERION_PASS",
    "DIMENSION_FAIL",
    "DIMENSION_NOT_ASSESSED",
    "DIMENSION_PASS",
    "LIME_QUALITY_GUARD_ACCEPTABLE",
    "LIME_QUALITY_GUARD_UNRELIABLE",
    "LIME_QUALITY_POLICY_VERSION",
    "LIME_QUALITY_SCHEMA_VERSION",
    "LimeQualityAssessment",
    "LimeQualityCriterion",
    "LimeQualityEvidence",
    "LimeQualityPolicy",
    "LimeQualityStatus",
    "QUALITY_DIMENSIONS",
    "QUALITY_DIMENSION_INSTANCE_FIDELITY",
    "QUALITY_DIMENSION_NEIGHBORHOOD_FIDELITY",
    "QUALITY_DIMENSION_NUMERICAL_VALIDITY",
    "QUALITY_DIMENSION_STABILITY",
    "assess_lime_quality",
    "assess_lime_quality_from_evidence",
    "certify_lime_explanation",
    "require_acceptable_lime_quality",
]
