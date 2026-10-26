"""Genuine, model-faithful tabular LIME for Track A research models.

Scientific contract
-------------------
This module implements the original tabular LIME construction (Ribeiro,
Singh & Guestrin, *"Why Should I Trust You?"*, KDD 2016, §4.2) from first
principles, without an external ``lime`` dependency:

1. **Interpretable representation.** Each raw clinical/laboratory panel field
   becomes one binary interpretable feature: ``1`` means *"this field keeps the
   explained instance's value"* and ``0`` means *"this field is replaced by a
   reference value taken from the decoded training background"*.
2. **Perturbation sampling.** ``num_perturbations`` binary masks are drawn from
   a seeded ``numpy.random.Generator`` (Bernoulli 0.5 per field), plus the
   forced all-ones row (the explained instance itself). Two registered
   reference schemes are supported:

   * ``fixed_background_reference`` (default) — one reference vector, the
     decoded background median for numeric fields and the modal registered
     code for categorical fields. The estimand is precisely ``f`` evaluated
     along the instance-versus-reference axis, so the surrogate's
     variance-explained diagnostic measures the model's local *nonlinearity*
     rather than unmodelled reference-sampling noise.
   * ``sampled_background_marginals`` — a fresh reference value per field and
     perturbation row (classic marginal-sampling LIME). This injects
     irreducible reference noise that no linear surrogate can capture, so its
     weighted R^2 is systematically lower for the same model and instance; it
     is retained as a documented sensitivity comparator.

   Either way categorical perturbations only ever contain registered codes,
   numeric perturbations stay inside the registered plausibility bounds, and
   optional-missing states are preserved as an explicit third state (``NaN``
   -> training-fold imputation plus the ``<field>__missing`` indicator column).
   Measurement units are validated upstream by
   :func:`ai.panels.validate_clinical_record`; LIME re-checks categorical
   vocabularies and numeric plausibility bounds on every decoded reference and
   every perturbation row.
3. **Kernel weighting.** ``w_i = exp(-d_i^2 / kernel_width^2)`` with the
   normalized Hamming distance ``d_i = sqrt(#replaced fields) / sqrt(M)``.
4. **Weighted surrogate.** A ridge-regularized weighted least-squares linear
   model is fitted on the binary masks. The reported ``lime_weight`` of field
   ``j`` is the surrogate coefficient for that binary interpretable feature.
   The surrogate is *evaluated* at the instance (all masks = 1) and directly
   compared against an actual model call, giving a genuine local-fidelity
   diagnostic instead of a claimed identity.

Explanation generation and explanation quality are deliberately separated:
this module generates the explanation and attaches a fidelity-only
:class:`ai.lime_quality.LimeQualityAssessment`; :mod:`ai.lime_quality` owns the
registered acceptance thresholds, the five-value quality verdict, the
warnings and the "do not rely on these weights" guard. A generated explanation
is therefore never silently treated as trustworthy: without a stability report
its verdict is ``UNVERIFIED_STABILITY``, never ``ACCEPTABLE_LOCAL_APPROXIMATION``.

Explicitly **not** claimed
--------------------------
LIME is a *local linear approximation*. Unlike Shapley values it does **not**
satisfy local accuracy/efficiency, does not decompose the prediction exactly,
and is **not** interchangeable with the genuine LinearSHAP/TreeSHAP engine in
:mod:`ai.explainability`. Every explanation therefore declares
``is_exact=False``, ``additive_decomposition_claim=False`` and a
``explained_quantity``/``scale`` pair that mirrors the SHAP vocabulary so
explanations on incompatible score scales are refused by
:func:`assert_comparable_explanation_scales` rather than silently compared.

Supported model families and targets
------------------------------------
* ``l2_logistic_regression`` -> ``calibrated_log_odds`` when a compatible
  ``exact_raw_log_odds``/clipped-link ``OofLogisticCalibrator`` is supplied
  (resolved target matches the family's LinearSHAP target), otherwise
  ``raw_model_log_odds``.
* ``constrained_random_forest`` -> ``raw_model_probability`` by default
  (matches the family's TreeSHAP target). ``calibrated_log_odds`` is available
  as an explicit opt-in target; it is then flagged as not scale-comparable with
  TreeSHAP and is refused by the combined
  :class:`ai.inference.ResearchCadPredictor` result path.
* ``prevalence_dummy`` and every other family fail closed: a constant
  predictor has no identifiable local surrogate.

Privacy note
------------
``ShapBackgroundReference`` rows are decoded in memory only to draw
perturbation reference values. No decoded background value, training statistic
or patient-derived quantity is ever written into the returned explanation.
"""
from __future__ import annotations

from dataclasses import dataclass, replace as dataclass_replace
import hashlib
import json
import math
import time
from types import MappingProxyType
from typing import Any, Callable, Final, Mapping, Sequence

import numpy as np
from scipy.special import expit
from scipy.stats import rankdata
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression

from ai.calibration import OofLogisticCalibrator
from ai.errors import ExplainabilityIntegrityError
from ai.lime_quality import (
    LimeQualityAssessment,
    LimeQualityEvidence,
    LimeQualityPolicy,
    LimeQualityStatus,
    assess_lime_quality_from_evidence,
    certify_lime_explanation,
)
from ai.panels import ALL_PROHIBITED_FIELDS, ResearchPanelContract
from ai.preprocessing import FoldSafeClinicalPreprocessor
from ai.explainability import ShapBackgroundReference

LIME_METHOD: Final[str] = "tabular_lime_weighted_ridge_local_surrogate"
LIME_SCHEMA_VERSION: Final[str] = "cardioassist.ai.lime_explanation/v1"
LIME_FAMILY: Final[str] = "lime_local_approximation"

SUPPORTED_LIME_MODEL_FAMILIES: Final[frozenset[str]] = frozenset(
    {"l2_logistic_regression", "constrained_random_forest"}
)

LIME_TARGET_AUTO: Final[str] = "auto"
LIME_TARGET_RAW_MODEL_PROBABILITY: Final[str] = "raw_model_probability"
LIME_TARGET_RAW_MODEL_LOG_ODDS: Final[str] = "raw_model_log_odds"
LIME_TARGET_CALIBRATED_LOG_ODDS: Final[str] = "calibrated_log_odds"
ALLOWED_LIME_TARGETS: Final[tuple[str, ...]] = (
    LIME_TARGET_AUTO,
    LIME_TARGET_RAW_MODEL_PROBABILITY,
    LIME_TARGET_RAW_MODEL_LOG_ODDS,
    LIME_TARGET_CALIBRATED_LOG_ODDS,
)

#: Target quantity/scale pair emitted by the genuine SHAP engine per family.
SHAP_TARGET_BY_FAMILY: Final[Mapping[str, tuple[str, str]]] = {
    "l2_logistic_regression": ("calibrated_log_odds", "calibrated_log_odds"),
    "constrained_random_forest": ("raw_model_score", "raw_model_probability"),
}

#: Registered reference schemes for the "field replaced" state.
LIME_REFERENCE_FIXED_BACKGROUND: Final[str] = "fixed_background_reference"
LIME_REFERENCE_SAMPLED_MARGINALS: Final[str] = "sampled_background_marginals"
ALLOWED_LIME_REFERENCE_SCHEMES: Final[tuple[str, ...]] = (
    LIME_REFERENCE_FIXED_BACKGROUND,
    LIME_REFERENCE_SAMPLED_MARGINALS,
)

#: Seeds used when callers request stability assessment with the defaults.
DEFAULT_LIME_STABILITY_SEEDS: Final[tuple[int, ...]] = (
    20261026,
    20261027,
    20261028,
)

#: Hard resource ceilings (fail closed outside these bounds).
MIN_LIME_PERTURBATIONS: Final[int] = 64
MAX_LIME_PERTURBATIONS: Final[int] = 20_000
MAX_LIME_SCORE_BATCH: Final[int] = 8_192
MAX_LIME_PERTURBATION_CELLS: Final[int] = 5_000_000
MAX_LIME_DESIGN_CONDITION_NUMBER: Final[float] = 1e10

#: Hard numerical blow-up floor (generation guard, NOT a quality threshold).
#: A weighted regression below this effective sample size cannot be solved
#: meaningfully at all; quality acceptance is stricter and lives in
#: :class:`ai.lime_quality.LimeQualityPolicy`.
HARD_MIN_EFFECTIVE_SAMPLES: Final[float] = 3.0

LIME_INTERPRETATION_DISCLAIMER: Final[str] = (
    "LIME weights are weighted local-linear surrogate coefficients for "
    "'field keeps the explained instance's value' versus 'field takes a "
    "reference value from the decoded training background'. Under the default "
    "fixed_background_reference scheme that reference is a single fixed "
    "decoded-background vector (numeric median, categorical mode) reused by "
    "every perturbation row; under the optional sampled_background_marginals "
    "scheme each field instead draws its reference from the background "
    "marginals per perturbation row. Neither scheme samples a real patient "
    "record. LIME weights are NOT Shapley values, do NOT decompose the "
    "prediction exactly, are NOT additive in probability units, and may "
    "differ from exact SHAP attributions in magnitude and sign. They describe "
    "model sensitivity in a local perturbation neighborhood—never causality, "
    "never clinical risk, and never clinical advice."
)

MANDATORY_LIME_LIMITATIONS: Final[tuple[str, ...]] = (
    "LIME is a local weighted-linear approximation of the declared model output; it is not an exact Shapley decomposition and carries no efficiency/local-accuracy guarantee.",
    "Surrogate weights are conditional on the perturbation sampling scheme, kernel width, ridge penalty and random seed; the reported fidelity and seed-stability diagnostics quantify but never eliminate this sensitivity.",
    "Reference values are decoded-background summaries: the fixed_background_reference scheme reuses one decoded reference vector per field (numeric background median, modal registered categorical code) for every perturbation row, while the optional sampled_background_marginals scheme draws each field's reference independently from the background marginals per row. Neither preserves inter-feature correlations of the development cohort, and no perturbation row is a reconstructed real patient record (a documented distributional approximation).",
    "Feature weights describe local model sensitivity only and must never be presented as causal effects, individual CAD risk, or clinical advice.",
    "RESEARCH_ONLY output: not approved for clinical diagnosis, triage, treatment, or patient self-assessment.",
)


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class LimeConfig:
    """Deterministic LIME *generation* configuration with hard resource ceilings.

    This dataclass contains no acceptance threshold: whether a generated
    explanation is trustworthy is decided by
    :class:`ai.lime_quality.LimeQualityPolicy`, which is passed separately.
    Keeping the two apart means a permissive generation config can never
    silently relax the acceptance bar, and a strict policy can never change the
    explanation that was produced.
    """

    num_perturbations: int = 512
    seed: int = 20261026
    kernel_width: float = 0.75
    ridge_alpha: float = 1.0
    include_instance_row: bool = True
    reference_scheme: str = LIME_REFERENCE_FIXED_BACKGROUND
    with_holdout_diagnostic: bool = True
    holdout_fraction: float = 0.3
    min_holdout_rows: int = 8
    score_batch_size: int = 2_048
    max_abs_lime_weight: float | None = 1_000.0

    def __post_init__(self) -> None:
        if isinstance(self.num_perturbations, bool) or not isinstance(
            self.num_perturbations, int
        ):
            raise ExplainabilityIntegrityError(
                "lime_invalid_config",
                "num_perturbations must be an integer.",
                field="num_perturbations",
            )
        if not (
            MIN_LIME_PERTURBATIONS <= self.num_perturbations <= MAX_LIME_PERTURBATIONS
        ):
            raise ExplainabilityIntegrityError(
                "lime_invalid_config",
                "num_perturbations must lie within the registered bounded range.",
                field="num_perturbations",
            )
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or not (
            0 <= self.seed < 2**63
        ):
            raise ExplainabilityIntegrityError(
                "lime_invalid_config",
                "seed must be a non-negative 63-bit integer.",
                field="seed",
            )
        if self.reference_scheme not in ALLOWED_LIME_REFERENCE_SCHEMES:
            raise ExplainabilityIntegrityError(
                "lime_invalid_config",
                "reference_scheme is not a registered reference scheme.",
                field="reference_scheme",
            )
        for name, value in (
            ("kernel_width", self.kernel_width),
            ("ridge_alpha", self.ridge_alpha),
            ("holdout_fraction", self.holdout_fraction),
            ("max_abs_lime_weight", self.max_abs_lime_weight),
        ):
            if value is not None and not isinstance(value, (int, float)):
                raise ExplainabilityIntegrityError(
                    "lime_invalid_config",
                    f"{name} must be numeric when provided.",
                    field=name,
                )
        if not (math.isfinite(float(self.kernel_width)) and self.kernel_width > 0.0):
            raise ExplainabilityIntegrityError(
                "lime_invalid_config",
                "kernel_width must be finite and strictly positive.",
                field="kernel_width",
            )
        if not (math.isfinite(float(self.ridge_alpha)) and self.ridge_alpha >= 0.0):
            raise ExplainabilityIntegrityError(
                "lime_invalid_config",
                "ridge_alpha must be finite and non-negative.",
                field="ridge_alpha",
            )
        if not (0.0 < float(self.holdout_fraction) < 1.0):
            raise ExplainabilityIntegrityError(
                "lime_invalid_config",
                "holdout_fraction must lie strictly inside (0, 1).",
                field="holdout_fraction",
            )
        if isinstance(self.min_holdout_rows, bool) or not isinstance(
            self.min_holdout_rows, int
        ) or self.min_holdout_rows < 2:
            raise ExplainabilityIntegrityError(
                "lime_invalid_config",
                "min_holdout_rows must be an integer >= 2.",
                field="min_holdout_rows",
            )
        if isinstance(self.score_batch_size, bool) or not isinstance(
            self.score_batch_size, int
        ) or not (1 <= self.score_batch_size <= MAX_LIME_SCORE_BATCH):
            raise ExplainabilityIntegrityError(
                "lime_invalid_config",
                "score_batch_size must lie within the registered bounded range.",
                field="score_batch_size",
            )
        if self.max_abs_lime_weight is not None and not (
            math.isfinite(float(self.max_abs_lime_weight))
            and self.max_abs_lime_weight > 0.0
        ):
            raise ExplainabilityIntegrityError(
                "lime_invalid_config",
                "max_abs_lime_weight must be finite and > 0 when provided.",
                field="max_abs_lime_weight",
            )
        if not isinstance(self.include_instance_row, bool) or not isinstance(
            self.with_holdout_diagnostic, bool
        ):
            raise ExplainabilityIntegrityError(
                "lime_invalid_config",
                "include_instance_row and with_holdout_diagnostic must be booleans.",
            )

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "schema_version": LIME_SCHEMA_VERSION,
            "num_perturbations": int(self.num_perturbations),
            "seed": int(self.seed),
            "kernel_width": float(self.kernel_width),
            "ridge_alpha": float(self.ridge_alpha),
            "include_instance_row": bool(self.include_instance_row),
            "reference_scheme": str(self.reference_scheme),
            "with_holdout_diagnostic": bool(self.with_holdout_diagnostic),
            "holdout_fraction": float(self.holdout_fraction),
            "min_holdout_rows": int(self.min_holdout_rows),
            "score_batch_size": int(self.score_batch_size),
            "max_abs_lime_weight": (
                None
                if self.max_abs_lime_weight is None
                else float(self.max_abs_lime_weight)
            ),
            "mask_sampling": "bernoulli_0_5_per_field",
            "kernel": "exponential_normalized_hamming",
        }

    @property
    def config_sha256(self) -> str:
        payload = json.dumps(
            self.to_json_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


# --------------------------------------------------------------------------- #
# Explicit target definition
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class LimeTargetSpecification:
    """Mathematically explicit declaration of what LIME explains."""

    requested_target: str
    resolved_target: str
    model_family: str
    explained_quantity: str
    scale: str
    explains_calibrated_score_directly: bool
    linked_probability_quantity: str
    score_bounds: tuple[float, float] | None
    uses_calibrator: bool
    calibration_input_link: str | None
    comparable_with_family_shap_target: bool
    family_shap_target: tuple[str, str]
    note: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested_target": self.requested_target,
            "resolved_target": self.resolved_target,
            "model_family": self.model_family,
            "explained_quantity": self.explained_quantity,
            "scale": self.scale,
            "explains_calibrated_score_directly": (
                self.explains_calibrated_score_directly
            ),
            "linked_probability_quantity": self.linked_probability_quantity,
            "score_bounds": (
                None if self.score_bounds is None else list(self.score_bounds)
            ),
            "uses_calibrator": self.uses_calibrator,
            "calibration_input_link": self.calibration_input_link,
            "comparable_with_family_shap_target": (
                self.comparable_with_family_shap_target
            ),
            "family_shap_target": {
                "explained_quantity": self.family_shap_target[0],
                "scale": self.family_shap_target[1],
            },
            "note": self.note,
        }


_TARGET_KEY_TO_SCALE: Final[Mapping[str, tuple[str, str, str]]] = {
    # resolved target -> (explained_quantity, scale, linked_probability_quantity)
    LIME_TARGET_RAW_MODEL_PROBABILITY: (
        "raw_model_score",
        "raw_model_probability",
        "raw_model_score",
    ),
    LIME_TARGET_RAW_MODEL_LOG_ODDS: (
        "raw_model_log_odds",
        "raw_log_odds",
        "raw_model_score",
    ),
    LIME_TARGET_CALIBRATED_LOG_ODDS: (
        "calibrated_log_odds",
        "calibrated_log_odds",
        "calibrated_research_score",
    ),
}


def _resolve_lime_target(
    *,
    model_family: str,
    requested_target: str,
    calibrator: OofLogisticCalibrator | None,
) -> LimeTargetSpecification:
    if model_family not in SUPPORTED_LIME_MODEL_FAMILIES:
        raise ExplainabilityIntegrityError(
            "unsupported_model_family_for_lime",
            f"Model family '{model_family}' has no registered genuine LIME explainer.",
            field="model_family",
        )
    if requested_target not in ALLOWED_LIME_TARGETS:
        raise ExplainabilityIntegrityError(
            "lime_invalid_target",
            "Requested LIME target is not registered.",
            field="target",
        )
    if calibrator is not None and calibrator.model_family != model_family:
        raise ExplainabilityIntegrityError(
            "lime_incompatible_calibrator",
            "Calibrator model_family does not match the explained model family.",
        )

    if requested_target == LIME_TARGET_AUTO:
        if model_family == "l2_logistic_regression":
            resolved = (
                LIME_TARGET_CALIBRATED_LOG_ODDS
                if calibrator is not None
                else LIME_TARGET_RAW_MODEL_LOG_ODDS
            )
        else:
            resolved = LIME_TARGET_RAW_MODEL_PROBABILITY
    else:
        resolved = requested_target

    if model_family == "l2_logistic_regression":
        if resolved == LIME_TARGET_RAW_MODEL_PROBABILITY:
            raise ExplainabilityIntegrityError(
                "lime_incompatible_target_scale",
                "Probability-scale LIME is refused for the logistic model: its "
                "registered faithful target is raw/calibrated log-odds, and a "
                "probability-scale surrogate would not be comparable with exact "
                "LinearSHAP attributions.",
                field="target",
            )
        if (
            resolved == LIME_TARGET_CALIBRATED_LOG_ODDS
            and calibrator is None
        ):
            raise ExplainabilityIntegrityError(
                "lime_calibrator_required",
                "Calibrated-log-odds LIME requires an OofLogisticCalibrator.",
                field="target",
            )
    else:  # constrained_random_forest
        if resolved == LIME_TARGET_RAW_MODEL_LOG_ODDS:
            raise ExplainabilityIntegrityError(
                "lime_incompatible_target_scale",
                "Raw-log-odds LIME is refused for the forest family: the forest "
                "emits raw_model_score directly and its registered faithful "
                "target is raw_model_probability.",
                field="target",
            )
        if resolved == LIME_TARGET_CALIBRATED_LOG_ODDS:
            if calibrator is None:
                raise ExplainabilityIntegrityError(
                    "lime_calibrator_required",
                    "Calibrated-log-odds LIME requires an OofLogisticCalibrator.",
                    field="target",
                )
            if calibrator.input_link != "clipped_logit_of_raw_probability":
                raise ExplainabilityIntegrityError(
                    "lime_incompatible_calibrator",
                    "Forest calibrated-log-odds LIME requires the "
                    "'clipped_logit_of_raw_probability' calibrator link.",
                )

    explained_quantity, scale, linked_quantity = _TARGET_KEY_TO_SCALE[resolved]
    score_bounds: tuple[float, float] | None = (
        (0.0, 1.0) if resolved == LIME_TARGET_RAW_MODEL_PROBABILITY else None
    )
    family_shap_target = SHAP_TARGET_BY_FAMILY[model_family]
    if (
        model_family == "l2_logistic_regression"
        and calibrator is None
        and family_shap_target[0] == "calibrated_log_odds"
    ):
        family_shap_target = ("raw_model_log_odds", "raw_log_odds")
    comparable = (explained_quantity, scale) == family_shap_target

    if resolved == LIME_TARGET_CALIBRATED_LOG_ODDS:
        note = (
            "Target is calibrated_log_odds = intercept + slope * link(raw model "
            "output), i.e. logit(calibrated_research_score). The local surrogate "
            "approximates that calibrated log-odds output; its weights are NOT "
            "additive in probability units."
        )
    elif resolved == LIME_TARGET_RAW_MODEL_LOG_ODDS:
        note = (
            "Target is uncalibrated raw_model_log_odds = logit(raw_model_score) "
            "from the logistic estimator's exact decision function. Post-hoc "
            "calibration is NOT included, and the weights are NOT additive in "
            "probability units."
        )
    else:
        note = (
            "Target is the uncalibrated raw_model_score (mean positive-class "
            "forest probability). Post-hoc logistic calibration is nonlinear "
            "across averaged trees and is NOT part of this target; the local "
            "surrogate weights are therefore not calibrated-probability weights."
        )
    if not comparable:
        note = (
            note + " This target intentionally differs from the family's exact "
            "SHAP target, so SHAP and LIME values on this instance are NOT "
            "scale-comparable and must not be compared numerically."
        )

    return LimeTargetSpecification(
        requested_target=requested_target,
        resolved_target=resolved,
        model_family=model_family,
        explained_quantity=explained_quantity,
        scale=scale,
        explains_calibrated_score_directly=(
            resolved == LIME_TARGET_CALIBRATED_LOG_ODDS
        ),
        linked_probability_quantity=linked_quantity,
        score_bounds=score_bounds,
        uses_calibrator=calibrator is not None,
        calibration_input_link=(
            None if calibrator is None else calibrator.input_link
        ),
        comparable_with_family_shap_target=comparable,
        family_shap_target=family_shap_target,
        note=note,
    )


@dataclass(frozen=True, slots=True)
class _ScoredBatch:
    target_scores: np.ndarray
    positive_probabilities: np.ndarray


class LimeModelTarget:
    """Explicit model-output target backed by real estimator calls only."""

    def __init__(
        self,
        *,
        specification: LimeTargetSpecification,
        preprocessor: FoldSafeClinicalPreprocessor,
        estimator_input_builder: Callable[[np.ndarray], np.ndarray],
        estimator_input_width: int,
        column_to_raw_feature: tuple[int, ...],
        score_builder: Callable[[np.ndarray], _ScoredBatch],
        estimator_fitted_width: int,
        lineage_mode: str,
    ) -> None:
        self._specification = specification
        self._preprocessor = preprocessor
        self._builder = estimator_input_builder
        self._width = int(estimator_input_width)
        self._column_to_raw = tuple(int(v) for v in column_to_raw_feature)
        self._score_builder = score_builder
        self._fitted_width = int(estimator_fitted_width)
        self._lineage_mode = str(lineage_mode)

    @property
    def specification(self) -> LimeTargetSpecification:
        return self._specification

    @property
    def estimator_input_width(self) -> int:
        return self._width

    @property
    def estimator_fitted_width(self) -> int:
        return self._fitted_width

    @property
    def column_to_raw_feature(self) -> tuple[int, ...]:
        return self._column_to_raw

    @property
    def lineage_mode(self) -> str:
        return self._lineage_mode

    def estimator_columns_for_raw_feature(self, raw_index: int) -> tuple[int, ...]:
        return tuple(
            col for col, raw in enumerate(self._column_to_raw) if raw == raw_index
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "specification": self._specification.to_dict(),
            "estimator_input_width": self._width,
            "estimator_fitted_width": self._fitted_width,
            "feature_lineage_mode": self._lineage_mode,
            "estimator_input_column_count": len(self._column_to_raw),
        }

    def score_raw_rows(self, X_raw: np.ndarray) -> _ScoredBatch:
        """Score validated raw clinical rows through the actual estimator."""
        X = np.asarray(X_raw, dtype=np.float64)
        if X.ndim != 2 or X.shape[1] != self._preprocessor.n_raw_features:
            raise ExplainabilityIntegrityError(
                "lime_invalid_raw_matrix",
                "Raw clinical matrix column count does not match the fitted panel.",
            )
        if not np.isfinite(X[~np.isnan(X)]).all() or np.isinf(X).any():
            raise ExplainabilityIntegrityError(
                "lime_invalid_raw_matrix",
                "Raw clinical matrix contains infinite or non-finite values.",
            )
        E = np.asarray(self._builder(X), dtype=np.float64)
        if (
            E.ndim != 2
            or E.shape[0] != X.shape[0]
            or E.shape[1] != self._fitted_width
            or not np.isfinite(E).all()
        ):
            raise ExplainabilityIntegrityError(
                "lime_estimator_input_invalid",
                "Estimator input builder produced a misaligned or non-finite matrix.",
            )
        scored = self._score_builder(E)
        target_scores = np.asarray(scored.target_scores, dtype=np.float64).ravel()
        probabilities = np.asarray(
            scored.positive_probabilities, dtype=np.float64
        ).ravel()
        if (
            target_scores.shape[0] != X.shape[0]
            or probabilities.shape[0] != X.shape[0]
        ):
            raise ExplainabilityIntegrityError(
                "lime_invalid_model_output",
                "Estimator output is misaligned with the scored raw rows.",
            )
        if not np.isfinite(target_scores).all() or not np.isfinite(
            probabilities
        ).all():
            raise ExplainabilityIntegrityError(
                "lime_non_finite_model_scores",
                "Estimator produced non-finite scores for a perturbation batch.",
            )
        tolerance = 1e-12
        if np.any(probabilities < -tolerance) or np.any(probabilities > 1.0 + tolerance):
            raise ExplainabilityIntegrityError(
                "lime_invalid_model_probability",
                "Estimator produced probabilities outside [0, 1].",
            )
        probabilities = np.clip(probabilities, 0.0, 1.0)
        bounds = self._specification.score_bounds
        if bounds is not None:
            low, high = bounds
            if np.any(target_scores < low - tolerance) or np.any(
                target_scores > high + tolerance
            ):
                raise ExplainabilityIntegrityError(
                    "lime_target_out_of_declared_range",
                    "Target scores fall outside the declared mathematical range.",
                )
            target_scores = np.clip(target_scores, low, high)
        return _ScoredBatch(
            target_scores=target_scores, positive_probabilities=probabilities
        )


def _positive_probability_function(estimator: Any) -> Callable[[np.ndarray], np.ndarray]:
    classes = list(getattr(estimator, "classes_", ()))
    if 1 not in classes:
        raise ExplainabilityIntegrityError(
            "lime_estimator_missing_positive_class",
            "Fitted estimator does not expose a positive class labelled 1.",
        )
    positive_index = classes.index(1)

    def fn(E: np.ndarray) -> np.ndarray:
        probabilities = np.asarray(estimator.predict_proba(E), dtype=np.float64)
        return probabilities[:, positive_index]

    return fn


def build_lime_model_target(
    *,
    model_family: str,
    estimator: Any,
    preprocessor: FoldSafeClinicalPreprocessor,
    calibrator: OofLogisticCalibrator | None = None,
    target: str = LIME_TARGET_AUTO,
    estimator_input_builder: Callable[[np.ndarray], np.ndarray] | None = None,
    projected_column_to_raw_feature: Sequence[int] | None = None,
) -> LimeModelTarget:
    """Resolve an explicit, verified LIME target for a supported model family.

    ``estimator_input_builder`` supports projected estimator input spaces (the
    frozen Cleveland D-047 8-column forest space). Whenever a custom builder is
    supplied, ``projected_column_to_raw_feature`` is mandatory so feature
    lineage can never be silently assumed.
    """
    specification = _resolve_lime_target(
        model_family=model_family,
        requested_target=target,
        calibrator=calibrator,
    )
    if model_family == "l2_logistic_regression":
        if not isinstance(estimator, LogisticRegression):
            raise ExplainabilityIntegrityError(
                "estimator_family_mismatch",
                "Expected fitted LogisticRegression for 'l2_logistic_regression'.",
            )
    elif model_family == "constrained_random_forest":
        if not isinstance(estimator, RandomForestClassifier):
            raise ExplainabilityIntegrityError(
                "estimator_family_mismatch",
                "Expected fitted RandomForestClassifier for 'constrained_random_forest'.",
            )
    else:  # pragma: no cover - defensive; _resolve_lime_target already rejects
        raise ExplainabilityIntegrityError(
            "unsupported_model_family_for_lime",
            f"Model family '{model_family}' has no registered genuine LIME explainer.",
        )

    fitted_width = int(getattr(estimator, "n_features_in_", -1))
    if fitted_width <= 0:
        raise ExplainabilityIntegrityError(
            "lime_estimator_not_fitted",
            "Estimator does not expose a fitted input width.",
        )

    if estimator_input_builder is None:
        if projected_column_to_raw_feature is not None:
            raise ExplainabilityIntegrityError(
                "lime_projection_unexpected",
                "A projected column mapping was supplied without an estimator "
                "input builder.",
            )
        if fitted_width != preprocessor.n_encoded_features:
            raise ExplainabilityIntegrityError(
                "lime_estimator_width_lineage_mismatch",
                "Estimator was fitted on a projected input space; an explicit "
                "estimator_input_builder and projected column mapping are required.",
            )
        builder: Callable[[np.ndarray], np.ndarray] = preprocessor.transform
        column_to_raw = tuple(
            raw_index
            for raw_index, ft in enumerate(preprocessor.field_transforms)
            for _ in ft.slice_indices
        )
        lineage_mode = "full_preprocessor_encoding"
    else:
        if projected_column_to_raw_feature is None:
            raise ExplainabilityIntegrityError(
                "lime_projection_mapping_required",
                "A custom estimator input builder requires an explicit "
                "projected-column-to-raw-feature mapping for feature lineage.",
            )
        mapping = tuple(int(v) for v in projected_column_to_raw_feature)
        if len(mapping) != fitted_width:
            raise ExplainabilityIntegrityError(
                "lime_projection_mapping_mismatch",
                "Projected column mapping width does not match the fitted estimator.",
            )
        if any(v < 0 or v >= preprocessor.n_raw_features for v in mapping):
            raise ExplainabilityIntegrityError(
                "lime_projection_mapping_mismatch",
                "Projected column mapping references an unknown raw feature.",
            )
        builder = estimator_input_builder
        column_to_raw = mapping
        lineage_mode = "explicit_projection"

    if model_family == "l2_logistic_regression":

        def _lr_score_builder(E: np.ndarray) -> _ScoredBatch:
            logits = np.asarray(
                estimator.decision_function(E), dtype=np.float64
            ).ravel()
            raw_probabilities = np.asarray(expit(logits), dtype=np.float64)
            if specification.resolved_target == LIME_TARGET_RAW_MODEL_LOG_ODDS:
                return _ScoredBatch(
                    target_scores=logits, positive_probabilities=raw_probabilities
                )
            assert calibrator is not None
            calibrated = np.asarray(
                calibrator.calibrated_log_odds(
                    raw_probabilities, raw_logits=logits
                ),
                dtype=np.float64,
            )
            # The linked probability quantity for the calibrated target is the
            # calibrated probability, never the uncalibrated model score.
            return _ScoredBatch(
                target_scores=calibrated,
                positive_probabilities=np.asarray(expit(calibrated), dtype=np.float64),
            )

        score_builder = _lr_score_builder
    else:
        probability_fn = _positive_probability_function(estimator)

        def _rf_score_builder(E: np.ndarray) -> _ScoredBatch:
            probabilities = np.asarray(probability_fn(E), dtype=np.float64)
            if specification.resolved_target == LIME_TARGET_RAW_MODEL_PROBABILITY:
                return _ScoredBatch(
                    target_scores=probabilities, positive_probabilities=probabilities
                )
            assert calibrator is not None
            calibrated = np.asarray(
                calibrator.calibrated_log_odds(probabilities), dtype=np.float64
            )
            return _ScoredBatch(
                target_scores=calibrated,
                positive_probabilities=np.asarray(expit(calibrated), dtype=np.float64),
            )

        score_builder = _rf_score_builder

    return LimeModelTarget(
        specification=specification,
        preprocessor=preprocessor,
        estimator_input_builder=builder,
        estimator_input_width=len(column_to_raw),
        column_to_raw_feature=column_to_raw,
        score_builder=score_builder,
        estimator_fitted_width=fitted_width,
        lineage_mode=lineage_mode,
    )


# --------------------------------------------------------------------------- #
# Raw clinical-space decoding / validation helpers
# --------------------------------------------------------------------------- #


def _tolerance_for_range(low: float, high: float) -> float:
    return 1e-9 * max(1.0, abs(low), abs(high))


def _validate_numeric_scalar(
    value: float, spec: Any, *, error_code: str = "lime_invalid_reference_value"
) -> float:
    if not math.isfinite(value):
        raise ExplainabilityIntegrityError(
            error_code,
            f"Numeric value for '{spec.name}' is not finite.",
            field=spec.name,
        )
    if spec.strictly_positive and value <= 0.0:
        raise ExplainabilityIntegrityError(
            error_code,
            f"Numeric value for '{spec.name}' violates the strictly-positive rule.",
            field=spec.name,
        )
    if spec.plausible_range is not None:
        low, high = spec.plausible_range
        tolerance = _tolerance_for_range(float(low), float(high))
        if value < float(low) - tolerance or value > float(high) + tolerance:
            raise ExplainabilityIntegrityError(
                error_code,
                f"Numeric value for '{spec.name}' falls outside the registered "
                "plausibility bounds.",
                field=spec.name,
            )
        return float(min(max(value, float(low)), float(high)))
    return float(value)


def decode_background_to_raw_rows(
    *,
    background: ShapBackgroundReference,
    preprocessor: FoldSafeClinicalPreprocessor,
    panel: ResearchPanelContract,
) -> np.ndarray:
    """Decode stored encoded background rows back into raw clinical values.

    All decoded values are re-validated against the registered panel contract
    (categorical vocabulary, numeric plausibility bounds, strictly-positive
    rules). Any inconsistency fails closed; no decoded value is ever surfaced
    in an explanation or log message.
    """
    if (
        background.panel_id != preprocessor.panel_id
        or background.panel_contract_sha256 != preprocessor.panel_contract_sha256
        or tuple(background.encoded_feature_names)
        != tuple(preprocessor.encoded_feature_names)
    ):
        raise ExplainabilityIntegrityError(
            "lime_background_contract_mismatch",
            "SHAP/LIME background reference does not match the fitted preprocessor.",
        )
    matrix = np.asarray(background.background_matrix, dtype=np.float64)
    if (
        matrix.ndim != 2
        or matrix.shape[1] != preprocessor.n_encoded_features
        or matrix.shape[0] < 2
        or not np.isfinite(matrix).all()
    ):
        raise ExplainabilityIntegrityError(
            "lime_background_matrix_invalid",
            "Background matrix must contain >= 2 finite rows aligned to the "
            "fitted encoding.",
        )

    field_specs = panel.field_map
    if tuple(preprocessor.raw_feature_names) != tuple(panel.feature_names):
        raise ExplainabilityIntegrityError(
            "lime_panel_lineage_mismatch",
            "Preprocessor raw feature order does not match the panel contract.",
        )

    raw = np.zeros((matrix.shape[0], panel_feature_count(panel)), dtype=np.float64)
    for raw_index, ft in enumerate(preprocessor.field_transforms):
        spec = field_specs[ft.name]
        if spec.role == "numeric":
            assert ft.scale_mean is not None and ft.scale_std is not None
            z_values = matrix[:, ft.slice_indices[0]]
            decoded = z_values * float(ft.scale_std) + float(ft.scale_mean)
            if not ft.required:
                missing_column = matrix[:, ft.slice_indices[1]]
                if not np.all((missing_column == 0.0) | (missing_column == 1.0)):
                    raise ExplainabilityIntegrityError(
                        "lime_background_missing_indicator_invalid",
                        f"Missingness indicator for '{ft.name}' is not binary.",
                        field=ft.name,
                    )
                decoded = np.where(missing_column == 1.0, np.nan, decoded)
            raw[:, raw_index] = np.asarray(
                [
                    np.nan if math.isnan(value) else _validate_numeric_scalar(value, spec)
                    for value in decoded.tolist()
                ],
                dtype=np.float64,
            )
        else:
            codes = tuple(int(v) for v in ft.categorical_codes)
            one_hot_columns = [ft.slice_indices[i] for i in range(len(codes) - 1)]
            one_hot = matrix[:, one_hot_columns]
            if not np.all((one_hot == 0.0) | (one_hot == 1.0)):
                raise ExplainabilityIntegrityError(
                    "lime_background_one_hot_invalid",
                    f"One-hot block for '{ft.name}' is not binary.",
                    field=ft.name,
                )
            active = np.sum(one_hot, axis=1)
            if np.any(active > 1.0):
                raise ExplainabilityIntegrityError(
                    "lime_background_one_hot_invalid",
                    f"One-hot block for '{ft.name}' has multiple active levels.",
                    field=ft.name,
                )
            code_values = np.where(
                active == 1.0,
                np.asarray(codes[1:], dtype=np.float64)[
                    np.argmax(one_hot == 1.0, axis=1)
                ],
                float(codes[0]),
            )
            if not ft.required:
                missing_column = matrix[:, ft.slice_indices[-1]]
                if not np.all((missing_column == 0.0) | (missing_column == 1.0)):
                    raise ExplainabilityIntegrityError(
                        "lime_background_missing_indicator_invalid",
                        f"Missingness indicator for '{ft.name}' is not binary.",
                        field=ft.name,
                    )
                code_values = np.where(missing_column == 1.0, np.nan, code_values)
            raw[:, raw_index] = code_values
    return raw


def panel_feature_count(panel: ResearchPanelContract) -> int:
    """Return the ordered raw clinical feature count of ``panel``."""
    return len(panel.fields)


def _assert_panel_is_lime_eligible(panel: ResearchPanelContract) -> None:
    prohibited = set(panel.feature_names) & set(ALL_PROHIBITED_FIELDS)
    if prohibited:
        bad_field = sorted(prohibited)[0]
        raise ExplainabilityIntegrityError(
            "lime_prohibited_feature_in_panel",
            f"Panel '{panel.panel_id}' contains prohibited predictor '{bad_field}' "
            "(target leakage, angiography/echo, or wearable source).",
            field=bad_field,
        )
    if len(set(panel.feature_names)) != len(panel.feature_names):
        raise ExplainabilityIntegrityError(
            "lime_duplicate_panel_feature",
            "Panel contract contains duplicated clinical feature names.",
        )


def validate_instance_row(
    x_raw_row: np.ndarray, panel: ResearchPanelContract
) -> tuple[str, ...]:
    """Validate one raw clinical row and return per-field presence status."""
    row = np.asarray(x_raw_row, dtype=np.float64)
    if row.ndim == 2 and row.shape[0] == 1:
        row = row.ravel()
    if row.ndim != 1 or row.shape[0] != panel_feature_count(panel):
        raise ExplainabilityIntegrityError(
            "lime_invalid_instance_vector",
            "Raw instance vector is misaligned with the panel contract.",
        )
    if np.isinf(row).any():
        raise ExplainabilityIntegrityError(
            "lime_invalid_instance_vector",
            "Raw instance vector contains infinite values.",
        )
    statuses: list[str] = []
    for value, spec in zip(row.tolist(), panel.fields):
        if math.isnan(value):
            if spec.required:
                raise ExplainabilityIntegrityError(
                    "lime_missing_required_instance_value",
                    f"Required clinical field '{spec.name}' is missing.",
                    field=spec.name,
                )
            statuses.append("missing_imputed")
            continue
        if spec.role == "categorical":
            if not float(value).is_integer() or int(value) not in spec.categorical_codes:
                raise ExplainabilityIntegrityError(
                    "lime_unknown_categorical_code",
                    f"Categorical field '{spec.name}' carries an unregistered code.",
                    field=spec.name,
                )
        else:
            _validate_numeric_scalar(
                float(value), spec, error_code="lime_invalid_instance_value"
            )
        statuses.append("present")
    return tuple(statuses)


def _validate_perturbation_domain(
    X_pert: np.ndarray, panel: ResearchPanelContract
) -> None:
    if X_pert.ndim != 2 or X_pert.shape[1] != panel_feature_count(panel):
        raise ExplainabilityIntegrityError(
            "lime_invalid_perturbation_matrix",
            "Perturbation design has an unexpected shape.",
        )
    if np.isinf(X_pert).any():
        raise ExplainabilityIntegrityError(
            "lime_perturbation_domain_violation",
            "Perturbation design contains infinite values.",
        )
    for col_index, spec in enumerate(panel.fields):
        column = X_pert[:, col_index]
        missing = np.isnan(column)
        if spec.required and bool(missing.any()):
            raise ExplainabilityIntegrityError(
                "lime_perturbation_domain_violation",
                f"Required field '{spec.name}' is missing in sampled perturbations.",
                field=spec.name,
            )
        observed = column[~missing]
        if observed.size == 0:
            raise ExplainabilityIntegrityError(
                "lime_perturbation_domain_violation",
                f"Field '{spec.name}' has no observed values in the perturbation design.",
                field=spec.name,
            )
        if spec.role == "categorical":
            rounded = np.rint(observed)
            if not np.allclose(observed, rounded, rtol=0.0, atol=0.0):
                raise ExplainabilityIntegrityError(
                    "lime_perturbation_domain_violation",
                    f"Categorical field '{spec.name}' has non-integer codes.",
                    field=spec.name,
                )
            allowed = set(int(code) for code in spec.categorical_codes)
            if not set(int(v) for v in rounded.tolist()).issubset(allowed):
                raise ExplainabilityIntegrityError(
                    "lime_perturbation_domain_violation",
                    f"Categorical field '{spec.name}' has unregistered codes.",
                    field=spec.name,
                )
        else:
            if spec.strictly_positive and bool(np.any(observed <= 0.0)):
                raise ExplainabilityIntegrityError(
                    "lime_perturbation_domain_violation",
                    f"Numeric field '{spec.name}' violates the strictly-positive rule.",
                    field=spec.name,
                )
            if spec.plausible_range is not None:
                low, high = spec.plausible_range
                tolerance = _tolerance_for_range(float(low), float(high))
                if bool(
                    np.any(observed < float(low) - tolerance)
                    or np.any(observed > float(high) + tolerance)
                ):
                    raise ExplainabilityIntegrityError(
                        "lime_perturbation_domain_violation",
                        f"Numeric field '{spec.name}' falls outside registered "
                        "plausibility bounds.",
                        field=spec.name,
                    )


# --------------------------------------------------------------------------- #
# Perturbation design and weighted surrogate
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class _PerturbationDesign:
    X_raw: np.ndarray
    mask: np.ndarray
    weights: np.ndarray
    normalized_distances: np.ndarray
    reference_scheme: str
    reference_differs_from_instance: tuple[bool | None, ...]


def _fixed_background_reference(
    background_raw: np.ndarray, panel: ResearchPanelContract
) -> np.ndarray:
    """Decode one registered reference value per panel field.

    Numeric fields use the finite background median (a value inside the
    registered plausibility bounds by construction); categorical fields use the
    modal registered code. Optional fields with no observed value keep the
    explicit missing state. Nothing derived here is ever emitted in an
    explanation: only the *boolean* "does this reference differ from the
    explained instance" flag leaves this function.
    """
    matrix = np.asarray(background_raw, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[1] != panel_feature_count(panel):
        raise ExplainabilityIntegrityError(
            "lime_background_matrix_invalid",
            "Decoded background matrix is not aligned to the panel contract.",
        )
    reference = np.empty(matrix.shape[1], dtype=np.float64)
    for field_index, spec in enumerate(panel.fields):
        column = matrix[:, field_index]
        finite = column[np.isfinite(column)]
        if spec.role == "numeric":
            if finite.size == 0:
                if spec.required:
                    raise ExplainabilityIntegrityError(
                        "lime_background_insufficient_reference_values",
                        f"Field '{spec.name}' has no finite background value to "
                        "use as a fixed reference.",
                        field=spec.name,
                    )
                reference[field_index] = np.nan
                continue
            reference[field_index] = _validate_numeric_scalar(
                float(np.median(finite)), spec
            )
        else:
            codes = tuple(int(code) for code in spec.categorical_codes)
            if finite.size == 0:
                if spec.required:
                    raise ExplainabilityIntegrityError(
                        "lime_background_insufficient_reference_values",
                        f"Field '{spec.name}' has no observed background code to "
                        "use as a fixed reference.",
                        field=spec.name,
                    )
                reference[field_index] = np.nan
                continue
            values, counts = np.unique(finite, return_counts=True)
            modal = int(values[int(np.argmax(counts))])
            if modal not in codes:
                raise ExplainabilityIntegrityError(
                    "lime_invalid_reference_value",
                    f"Modal code for '{spec.name}' is not a registered "
                    "categorical code.",
                    field=spec.name,
                )
            reference[field_index] = float(modal)
    return reference


def _reference_differs_from_instance(
    reference: np.ndarray,
    x_raw_row: np.ndarray,
    panel: ResearchPanelContract,
) -> tuple[bool, ...]:
    flags: list[bool] = []
    for field_index, spec in enumerate(panel.fields):
        left = float(reference[field_index])
        right = float(np.asarray(x_raw_row, dtype=np.float64).ravel()[field_index])
        left_missing = not math.isfinite(left)
        right_missing = not math.isfinite(right)
        if left_missing or right_missing:
            flags.append(bool(left_missing != right_missing))
            continue
        if spec.role == "numeric":
            tolerance = _tolerance_for_range(left, right)
            flags.append(bool(abs(left - right) > tolerance))
        else:
            flags.append(bool(int(left) != int(right)))
    return tuple(flags)


def _generate_perturbation_design(
    *,
    x_raw_row: np.ndarray,
    background_raw: np.ndarray,
    panel: ResearchPanelContract,
    config: LimeConfig,
) -> _PerturbationDesign:
    n_rows = int(config.num_perturbations)
    n_fields = panel_feature_count(panel)
    if n_rows * n_fields > MAX_LIME_PERTURBATION_CELLS:
        raise ExplainabilityIntegrityError(
            "lime_resource_limit_exceeded",
            "Requested perturbation design exceeds the registered bounded "
            "resource ceiling.",
            field="num_perturbations",
        )
    if background_raw.shape[0] < 2:
        raise ExplainabilityIntegrityError(
            "lime_background_insufficient_rows",
            "LIME requires at least two decoded background reference rows.",
        )

    rng = np.random.default_rng(int(config.seed))
    mask = rng.random((n_rows, n_fields)) < 0.5
    if config.include_instance_row:
        mask[0, :] = True

    instance_values = np.asarray(x_raw_row, dtype=np.float64).ravel()
    if config.reference_scheme == LIME_REFERENCE_FIXED_BACKGROUND:
        reference = _fixed_background_reference(background_raw, panel)
        reference_values = np.broadcast_to(reference, (n_rows, n_fields))
        reference_flags = _reference_differs_from_instance(
            reference, instance_values, panel
        )
    else:
        reference_indices = rng.integers(
            0, background_raw.shape[0], size=(n_rows, n_fields), endpoint=False
        )
        field_indices = np.arange(n_fields, dtype=np.int64)[None, :]
        reference_values = background_raw[reference_indices, field_indices]
        reference_flags = tuple(None for _ in range(n_fields))
    X_pert = np.where(mask, instance_values, reference_values)
    X_pert = np.asarray(X_pert, dtype=np.float64)

    replaced = np.sum(~mask, axis=1).astype(np.float64)
    normalized_distances = np.sqrt(replaced) / math.sqrt(float(n_fields))
    weights = np.exp(
        -np.square(normalized_distances) / (float(config.kernel_width) ** 2)
    )
    weights = np.asarray(weights, dtype=np.float64)
    if not np.isfinite(weights).all() or np.any(weights <= 0.0):
        raise ExplainabilityIntegrityError(
            "lime_invalid_kernel_weights",
            "Kernel weights must be strictly positive and finite.",
        )
    _validate_perturbation_domain(X_pert, panel)
    return _PerturbationDesign(
        X_raw=X_pert,
        mask=mask,
        weights=weights,
        normalized_distances=normalized_distances,
        reference_scheme=str(config.reference_scheme),
        reference_differs_from_instance=reference_flags,
    )


@dataclass(frozen=True, slots=True)
class _SurrogateFit:
    intercept: float
    coefficients: np.ndarray
    condition_number: float
    n_effective_samples: float


def _weighted_ridge_fit(
    mask: np.ndarray,
    scores: np.ndarray,
    weights: np.ndarray,
    *,
    ridge_alpha: float,
) -> _SurrogateFit:
    design = np.asarray(mask, dtype=np.float64)
    y = np.asarray(scores, dtype=np.float64).ravel()
    w = np.asarray(weights, dtype=np.float64).ravel()
    n_rows, n_fields = design.shape
    if y.shape[0] != n_rows or w.shape[0] != n_rows:
        raise ExplainabilityIntegrityError(
            "lime_invalid_surrogate_design",
            "Surrogate design, model scores and kernel weights are misaligned.",
        )
    if not np.isfinite(y).all() or not np.isfinite(w).all():
        raise ExplainabilityIntegrityError(
            "lime_invalid_surrogate_design",
            "Surrogate design contains non-finite scores or weights.",
        )

    total_weight = float(np.sum(w))
    if not math.isfinite(total_weight) or total_weight <= 0.0:
        raise ExplainabilityIntegrityError(
            "lime_degenerate_perturbations",
            "Total perturbation weight is not strictly positive.",
        )
    weighted_mean = (w @ design) / total_weight
    weighted_variance = (w @ np.square(design - weighted_mean)) / total_weight
    degenerate = tuple(
        int(j)
        for j, variance in enumerate(weighted_variance.tolist())
        if variance <= 1e-12
    )
    if degenerate:
        raise ExplainabilityIntegrityError(
            "lime_degenerate_perturbations",
            "At least one interpretable feature has no weighted variation in the "
            "sampled perturbation design; the surrogate coefficient is not "
            "identifiable.",
        )
    if int(np.unique(design, axis=0).shape[0]) < 2:
        raise ExplainabilityIntegrityError(
            "lime_degenerate_perturbations",
            "Perturbation design collapsed to a single distinct mask.",
        )

    augmented = np.column_stack([np.ones(n_rows), design])
    weighted_design = augmented * w[:, None]
    normal_matrix = augmented.T @ weighted_design
    penalty = np.zeros_like(normal_matrix)
    if ridge_alpha > 0.0:
        penalty[1:, 1:] = float(ridge_alpha) * np.eye(n_fields)
    system = normal_matrix + penalty
    try:
        condition_number = float(np.linalg.cond(system))
    except np.linalg.LinAlgError:  # pragma: no cover - defensive
        condition_number = math.inf
    if not math.isfinite(condition_number):
        raise ExplainabilityIntegrityError(
            "lime_ill_conditioned_surrogate",
            "Weighted surrogate normal equations are not finite.",
        )
    try:
        theta = np.linalg.solve(system, augmented.T @ (w * y))
    except np.linalg.LinAlgError as exc:  # pragma: no cover - defensive
        raise ExplainabilityIntegrityError(
            "lime_ill_conditioned_surrogate",
            "Weighted surrogate normal equations are singular.",
        ) from exc
    if not np.isfinite(theta).all():
        raise ExplainabilityIntegrityError(
            "lime_ill_conditioned_surrogate",
            "Weighted surrogate solution is not finite.",
        )

    n_effective = total_weight**2 / float(np.sum(np.square(w)))
    return _SurrogateFit(
        intercept=float(theta[0]),
        coefficients=np.asarray(theta[1:], dtype=np.float64),
        condition_number=condition_number,
        n_effective_samples=float(n_effective),
    )


def _weighted_r2(
    scores: np.ndarray, predictions: np.ndarray, weights: np.ndarray
) -> float | None:
    y = np.asarray(scores, dtype=np.float64).ravel()
    y_hat = np.asarray(predictions, dtype=np.float64).ravel()
    w = np.asarray(weights, dtype=np.float64).ravel()
    total_weight = float(np.sum(w))
    if total_weight <= 0.0:
        return None
    weighted_mean = float(np.sum(w * y) / total_weight)
    residual = float(np.sum(w * np.square(y - y_hat)))
    total = float(np.sum(w * np.square(y - weighted_mean)))
    if total <= 1e-18:
        return None
    return float(1.0 - residual / total)


def _unweighted_r2(scores: np.ndarray, predictions: np.ndarray) -> float | None:
    y = np.asarray(scores, dtype=np.float64).ravel()
    y_hat = np.asarray(predictions, dtype=np.float64).ravel()
    residual = float(np.sum(np.square(y - y_hat)))
    total = float(np.sum(np.square(y - np.mean(y))))
    if total <= 1e-18:
        return None
    return float(1.0 - residual / total)


def _weighted_rmse(
    scores: np.ndarray, predictions: np.ndarray, weights: np.ndarray
) -> float:
    y = np.asarray(scores, dtype=np.float64).ravel()
    y_hat = np.asarray(predictions, dtype=np.float64).ravel()
    w = np.asarray(weights, dtype=np.float64).ravel()
    return float(np.sqrt(np.sum(w * np.square(y - y_hat)) / float(np.sum(w))))


def _unweighted_rmse(scores: np.ndarray, predictions: np.ndarray) -> float:
    y = np.asarray(scores, dtype=np.float64).ravel()
    y_hat = np.asarray(predictions, dtype=np.float64).ravel()
    return float(np.sqrt(np.mean(np.square(y - y_hat))))


# --------------------------------------------------------------------------- #
# Explanation data model
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class FeatureLimeAttribution:
    """One clinical-feature-level local surrogate coefficient."""

    feature_name: str
    clinical_meaning: str
    role: str
    unit: str | None
    status: str  # "present" | "missing_imputed"
    encoded_columns: tuple[str, ...]
    estimator_input_columns: tuple[int, ...]
    represented_in_estimator_input: bool
    lime_weight: float
    absolute_weight_rank: int
    local_direction: str
    reference_differs_from_instance_value: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_name": self.feature_name,
            "clinical_meaning": self.clinical_meaning,
            "role": self.role,
            "unit": self.unit,
            "status": self.status,
            "encoded_columns": list(self.encoded_columns),
            "estimator_input_columns": list(self.estimator_input_columns),
            "represented_in_estimator_input": (
                self.represented_in_estimator_input
            ),
            "lime_weight": self.lime_weight,
            "absolute_weight_rank": self.absolute_weight_rank,
            "local_direction": self.local_direction,
            "reference_differs_from_instance_value": (
                self.reference_differs_from_instance_value
            ),
            "interpretation": (
                "Weighted local-linear surrogate coefficient on "
                f"'{self.feature_name}' switching from a decoded-background "
                "reference value to the explained instance's value; NOT a "
                "Shapley value and NOT causal or clinical advice."
            ),
        }


@dataclass(frozen=True, slots=True)
class FaithfulLimeExplanation:
    """Verified local LIME explanation with explicit target, fidelity and cost."""

    method: str
    method_family: str
    is_exact: bool
    is_local_approximation: bool
    additive_decomposition_claim: bool
    model_family: str
    explained_quantity: str
    scale: str
    explains_calibrated_score_directly: bool
    linked_probability_quantity: str
    linked_probability_value: float
    score_alignment_note: str
    interpretation_note: str
    score_bounds: tuple[float, float] | None
    target_specification: LimeTargetSpecification
    background_sample_count: int
    background_synthetic_only: bool
    background_reference_mode: str
    reference_scheme: str
    sampling_scheme: str
    seed: int
    num_perturbations: int
    kernel: str
    kernel_width: float
    ridge_alpha: float
    surrogate_intercept: float
    surrogate_prediction_at_instance: float
    model_prediction_at_instance: float
    local_fidelity_abs_error: float
    local_fidelity_relative_error: float
    neighborhood_output_weighted_sd: float
    local_fidelity_error_in_neighborhood_sigma: float
    weighted_r2: float | None
    unweighted_r2: float | None
    holdout_weighted_r2: float | None
    holdout_rows: int
    weighted_rmse: float
    unweighted_rmse: float
    n_effective_samples: float
    design_condition_number: float
    model_rows_scored: int
    model_call_count: int
    perturbation_matrix_bytes: int
    score_batch_size: int
    runtime_seconds: float
    config_sha256: str
    quality: LimeQualityAssessment
    attributions: tuple[FeatureLimeAttribution, ...]
    limitations: tuple[str, ...] = MANDATORY_LIME_LIMITATIONS

    def weight_map(self) -> dict[str, float]:
        return {item.feature_name: item.lime_weight for item in self.attributions}

    @property
    def quality_status(self) -> str:
        return self.quality.status.value

    @property
    def is_reliable_for_interpretation(self) -> bool:
        return self.quality.is_reliable_for_interpretation

    def certify(
        self,
        *,
        stability: Any | None = None,
        policy: LimeQualityPolicy | None = None,
    ) -> "FaithfulLimeExplanation":
        """Return a copy carrying the full (stability-inclusive) assessment."""
        return certify_lime_explanation(
            self, stability=stability, policy=policy
        )

    def deterministic_payload(self) -> dict[str, Any]:
        """Deterministic explanation payload (excludes wall-clock runtime).

        Wall-clock timing is the only non-deterministic content, at both the
        explanation level and inside the attached stability summary; removing
        both keeps ``state_sha256`` bitwise reproducible for the same seed and
        configuration.
        """
        payload = self.to_dict()
        payload.pop("runtime", None)
        quality = payload.get("quality")
        if isinstance(quality, dict):
            summary = quality.get("stability_summary")
            if isinstance(summary, dict):
                summary.pop("runtime_seconds", None)
        return payload

    @property
    def state_sha256(self) -> str:
        payload = json.dumps(
            self.deterministic_payload(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": LIME_SCHEMA_VERSION,
            "method": self.method,
            "method_family": self.method_family,
            "is_exact": self.is_exact,
            "is_local_approximation": self.is_local_approximation,
            "additive_decomposition_claim": self.additive_decomposition_claim,
            "model_family": self.model_family,
            "explained_quantity": self.explained_quantity,
            "scale": self.scale,
            "explains_calibrated_score_directly": (
                self.explains_calibrated_score_directly
            ),
            "linked_probability_quantity": self.linked_probability_quantity,
            "linked_probability_value": self.linked_probability_value,
            "score_alignment_note": self.score_alignment_note,
            "interpretation_note": self.interpretation_note,
            "score_bounds": (
                None if self.score_bounds is None else list(self.score_bounds)
            ),
            "target_specification": self.target_specification.to_dict(),
            "background": {
                "sample_count": self.background_sample_count,
                "synthetic_only": self.background_synthetic_only,
                "reference_mode": self.background_reference_mode,
                "contains_background_values_in_output": False,
            },
            "reference": {
                "scheme": self.reference_scheme,
                "reference_values_emitted": False,
                "note": (
                    "Fixed-background references are decoded training-background "
                    "marginals (numeric median / modal registered code); sampled "
                    "marginal references are drawn per field and perturbation "
                    "row. Neither the values nor any training statistic is "
                    "emitted."
                ),
            },
            "sampling": {
                "scheme": self.sampling_scheme,
                "seed": self.seed,
                "num_perturbations": self.num_perturbations,
                "kernel": self.kernel,
                "kernel_width": self.kernel_width,
                "mask_on_probability": 0.5,
            },
            "surrogate": {
                "estimator": "ridge_regularized_weighted_least_squares",
                "design": "binary_instance_match_mask_with_intercept",
                "ridge_alpha": self.ridge_alpha,
                "intercept": self.surrogate_intercept,
                "n_effective_samples": self.n_effective_samples,
                "design_condition_number": self.design_condition_number,
                "surrogate_prediction_at_instance": (
                    self.surrogate_prediction_at_instance
                ),
            },
            "fidelity": {
                "model_prediction_at_instance": self.model_prediction_at_instance,
                "local_fidelity_abs_error": self.local_fidelity_abs_error,
                "local_fidelity_relative_error": self.local_fidelity_relative_error,
                "neighborhood_output_weighted_sd": (
                    self.neighborhood_output_weighted_sd
                ),
                "local_fidelity_error_in_neighborhood_sigma": (
                    self.local_fidelity_error_in_neighborhood_sigma
                ),
                "weighted_r2": self.weighted_r2,
                "unweighted_r2": self.unweighted_r2,
                "holdout_weighted_r2": self.holdout_weighted_r2,
                "holdout_rows": self.holdout_rows,
                "weighted_rmse": self.weighted_rmse,
                "unweighted_rmse": self.unweighted_rmse,
                "interpretation": (
                    "Local fidelity compares the fitted surrogate's evaluation at "
                    "the explained instance with an actual model call at the same "
                    "instance. Weighted R^2/RMSE summarize surrogate fit over the "
                    "kernel-weighted perturbation sample; the holdout value is "
                    "computed on a seeded disjoint split. A small instance error "
                    "alone is NOT evidence of neighborhood fidelity - see the "
                    "quality assessment for the verdict."
                ),
            },
            "runtime": {
                "wall_clock_seconds": self.runtime_seconds,
                "model_rows_scored": self.model_rows_scored,
                "model_call_count": self.model_call_count,
                "perturbation_matrix_bytes": self.perturbation_matrix_bytes,
                "score_batch_size": self.score_batch_size,
            },
            "config_sha256": self.config_sha256,
            "quality": self.quality.to_dict(),
            "attributions": [item.to_dict() for item in self.attributions],
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True, slots=True)
class LimeStabilityReport:
    """Seed-sensitivity diagnostics for one LIME request.

    ``stability_assessment`` describes **weight agreement across seeds only**.
    It is not a fidelity judgment: every per-seed explanation carries its own
    fidelity status in ``per_seed_fidelity_statuses``, and a seed-stable set of
    weights can still be a poor local account of the model.
    """

    seeds: tuple[int, ...]
    reference_seed: int
    n_features: int
    top_k: int
    feature_weight_mean_abs: tuple[float, ...]
    feature_weight_std: tuple[float, ...]
    max_feature_weight_std: float
    mean_feature_weight_std: float
    max_abs_weight_deviation_from_reference_seed: float
    mean_abs_weight_deviation_from_reference_seed: float
    min_pairwise_spearman: float
    mean_pairwise_spearman: float
    sign_agreement_fraction: float
    top_k_overlap_fraction: float
    max_local_prediction_abs_deviation: float
    min_weighted_r2: float | None
    max_local_fidelity_relative_error: float
    runtime_seconds: float
    stability_assessment: str
    criteria: Mapping[str, float]
    per_seed_fidelity_statuses: tuple[str, ...] = ()
    worst_seed_fidelity_status: str = ""
    quality_policy_sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        def _safe(value: float | None) -> float | None:
            if value is None:
                return None
            numeric = float(value)
            return numeric if math.isfinite(numeric) else None

        return {
            "method": LIME_METHOD,
            "seeds": list(self.seeds),
            "reference_seed": self.reference_seed,
            "n_features": self.n_features,
            "top_k": self.top_k,
            "feature_weight_mean_abs": [_safe(v) for v in self.feature_weight_mean_abs],
            "feature_weight_std": [_safe(v) for v in self.feature_weight_std],
            "max_feature_weight_std": _safe(self.max_feature_weight_std),
            "mean_feature_weight_std": _safe(self.mean_feature_weight_std),
            "max_abs_weight_deviation_from_reference_seed": _safe(self.max_abs_weight_deviation_from_reference_seed),
            "mean_abs_weight_deviation_from_reference_seed": _safe(self.mean_abs_weight_deviation_from_reference_seed),
            "min_pairwise_spearman": _safe(self.min_pairwise_spearman),
            "mean_pairwise_spearman": _safe(self.mean_pairwise_spearman),
            "sign_agreement_fraction": _safe(self.sign_agreement_fraction),
            "top_k_overlap_fraction": _safe(self.top_k_overlap_fraction),
            "max_local_prediction_abs_deviation": _safe(self.max_local_prediction_abs_deviation),
            "min_weighted_r2": _safe(self.min_weighted_r2),
            "max_local_fidelity_relative_error": _safe(self.max_local_fidelity_relative_error),
            "runtime_seconds": self.runtime_seconds,
            "stability_assessment": self.stability_assessment,
            "criteria": dict(self.criteria),
            "per_seed_fidelity_statuses": list(self.per_seed_fidelity_statuses),
            "worst_seed_fidelity_status": self.worst_seed_fidelity_status,
            "quality_policy_sha256": self.quality_policy_sha256,
            "scope_note": (
                "stability_assessment covers weight agreement across seeds "
                "only; fidelity is reported per seed and never inferred from "
                "stability."
            ),
        }


# --------------------------------------------------------------------------- #
# Public explanation entry point
# --------------------------------------------------------------------------- #


def _assert_lime_scope(
    *,
    preprocessor: FoldSafeClinicalPreprocessor,
    panel: ResearchPanelContract,
) -> None:
    if (
        preprocessor.panel_id != panel.panel_id
        or preprocessor.panel_contract_sha256 != panel.contract_sha256
    ):
        raise ExplainabilityIntegrityError(
            "lime_panel_lineage_mismatch",
            "Preprocessor is not bound to the requested panel contract.",
        )
    _assert_panel_is_lime_eligible(panel)


def _quality_evidence(
    *,
    panel: ResearchPanelContract,
    design: _PerturbationDesign,
    specification: LimeTargetSpecification,
    model_at_instance: float,
    surrogate_at_instance: float,
    absolute_error: float,
    relative_error: float,
    neighborhood_sd: float,
    fidelity_error_in_sigma: float,
    weighted_r2: float | None,
    holdout_r2: float | None,
    holdout_rows: int,
    effective_samples: float,
    condition_number: float,
    coefficients: np.ndarray,
    attribution_count: int,
) -> LimeQualityEvidence:
    """Assemble the neutral numeric evidence consumed by the quality policy."""
    weights = np.asarray(coefficients, dtype=np.float64).ravel()
    return LimeQualityEvidence(
        n_features=panel_feature_count(panel),
        num_perturbations=int(design.mask.shape[0]),
        explained_quantity=specification.explained_quantity,
        scale=specification.scale,
        reference_scheme=design.reference_scheme,
        model_prediction_at_instance=float(model_at_instance),
        surrogate_prediction_at_instance=float(surrogate_at_instance),
        local_fidelity_abs_error=float(absolute_error),
        local_fidelity_relative_error=float(relative_error),
        neighborhood_output_weighted_sd=float(neighborhood_sd),
        local_fidelity_error_in_neighborhood_sigma=float(
            fidelity_error_in_sigma
        ),
        weighted_r2=weighted_r2,
        holdout_weighted_r2=holdout_r2,
        holdout_rows=int(holdout_rows),
        n_effective_samples=float(effective_samples),
        design_condition_number=float(condition_number),
        max_abs_lime_weight=float(np.max(np.abs(weights))) if weights.size else None,
        all_weights_finite=bool(weights.size) and bool(np.isfinite(weights).all()),
        attribution_count=int(attribution_count),
    )


def explain_clinical_instance_lime(
    *,
    model_family: str,
    estimator: Any,
    preprocessor: FoldSafeClinicalPreprocessor,
    panel: ResearchPanelContract,
    background: ShapBackgroundReference,
    x_raw_row: np.ndarray,
    z_row: np.ndarray | None = None,
    calibrator: OofLogisticCalibrator | None = None,
    target: str = LIME_TARGET_AUTO,
    config: LimeConfig | None = None,
    estimator_input_builder: Callable[[np.ndarray], np.ndarray] | None = None,
    projected_column_to_raw_feature: Sequence[int] | None = None,
    missing_feature_names: frozenset[str] = frozenset(),
    quality_policy: LimeQualityPolicy | None = None,
    stability: Any | None = None,
) -> FaithfulLimeExplanation:
    """Compute a genuine tabular LIME explanation with a quality verdict.

    The returned explanation is backed exclusively by actual estimator calls on
    the perturbation design; no synthetic or fabricated weight is produced.
    ``z_row`` (the preprocessor encoding of ``x_raw_row``) is optional but, when
    supplied, is verified against ``preprocessor.transform`` to prove feature
    lineage end-to-end.

    Poor numerical fidelity never fabricates a good explanation and never
    silently returns one either: the attached ``quality`` assessment carries a
    machine-readable status, per-criterion evidence and, whenever the surrogate
    is not acceptable, an explicit "do not rely on these weights" guard. Pass
    ``stability`` (a :class:`LimeStabilityReport`) to obtain a stability-aware
    verdict in the same object; without it the verdict is
    ``UNVERIFIED_STABILITY`` at best.
    """
    started = time.perf_counter()
    active_config = config if config is not None else LimeConfig()
    active_policy = quality_policy if quality_policy is not None else LimeQualityPolicy()
    _assert_lime_scope(preprocessor=preprocessor, panel=panel)
    statuses = validate_instance_row(x_raw_row, panel)
    row = np.asarray(x_raw_row, dtype=np.float64).ravel()

    if z_row is not None:
        encoded = np.asarray(z_row, dtype=np.float64).ravel()
        expected = preprocessor.transform(row.reshape(1, -1))[0]
        if (
            encoded.shape[0] != preprocessor.n_encoded_features
            or not np.isfinite(encoded).all()
            or not np.allclose(encoded, expected, rtol=0.0, atol=1e-12)
        ):
            raise ExplainabilityIntegrityError(
                "lime_instance_lineage_mismatch",
                "Provided encoded instance vector does not match the fitted "
                "preprocessor transformation of the raw clinical row.",
            )

    target_model = build_lime_model_target(
        model_family=model_family,
        estimator=estimator,
        preprocessor=preprocessor,
        calibrator=calibrator,
        target=target,
        estimator_input_builder=estimator_input_builder,
        projected_column_to_raw_feature=projected_column_to_raw_feature,
    )
    specification = target_model.specification

    background_raw = decode_background_to_raw_rows(
        background=background, preprocessor=preprocessor, panel=panel
    )
    design = _generate_perturbation_design(
        x_raw_row=row,
        background_raw=background_raw,
        panel=panel,
        config=active_config,
    )

    # Actual model calls only: the perturbation design is scored chunk by chunk
    # so peak memory stays bounded regardless of the requested sample count.
    n_rows = int(design.X_raw.shape[0])
    scored_targets = np.empty(n_rows, dtype=np.float64)
    scored_probabilities = np.empty(n_rows, dtype=np.float64)
    model_call_count = 0
    batch_size = int(active_config.score_batch_size)
    for start in range(0, n_rows, batch_size):
        stop = min(start + batch_size, n_rows)
        batch = target_model.score_raw_rows(design.X_raw[start:stop])
        scored_targets[start:stop] = batch.target_scores
        scored_probabilities[start:stop] = batch.positive_probabilities
        model_call_count += 1

    total_weight = float(np.sum(design.weights))
    weighted_mean = float(np.sum(design.weights * scored_targets) / total_weight)
    weighted_spread = float(
        np.sum(design.weights * np.square(scored_targets - weighted_mean))
    )
    if not math.isfinite(weighted_spread) or weighted_spread <= 1e-18:
        raise ExplainabilityIntegrityError(
            "lime_degenerate_model_output",
            "Model output is constant across all sampled perturbations; no "
            "identifiable local surrogate exists.",
        )

    fit = _weighted_ridge_fit(
        design.mask,
        scored_targets,
        design.weights,
        ridge_alpha=float(active_config.ridge_alpha),
    )
    if fit.condition_number > MAX_LIME_DESIGN_CONDITION_NUMBER:
        raise ExplainabilityIntegrityError(
            "lime_ill_conditioned_surrogate",
            "Weighted surrogate normal equations exceed the hard numerical "
            "blow-up ceiling; no coefficient is representable.",
        )
    if active_config.max_abs_lime_weight is not None and bool(
        np.any(np.abs(fit.coefficients) > float(active_config.max_abs_lime_weight))
    ):
        raise ExplainabilityIntegrityError(
            "lime_unbounded_surrogate_weight",
            "At least one local surrogate coefficient exceeds the registered "
            "sanity bound.",
        )

    surrogate_predictions = fit.intercept + design.mask.astype(np.float64) @ fit.coefficients
    surrogate_at_instance = float(fit.intercept + np.sum(fit.coefficients))

    instance_batch = target_model.score_raw_rows(row.reshape(1, -1))
    model_at_instance = float(instance_batch.target_scores[0])
    linked_probability = float(instance_batch.positive_probabilities[0])

    absolute_error = abs(surrogate_at_instance - model_at_instance)
    relative_error = absolute_error / max(1.0, abs(model_at_instance))
    if not math.isfinite(absolute_error) or not math.isfinite(relative_error):
        raise ExplainabilityIntegrityError(
            "lime_invalid_local_fidelity",
            "Local fidelity diagnostics are not finite.",
        )

    neighborhood_sd = math.sqrt(weighted_spread / total_weight)
    if not math.isfinite(neighborhood_sd) or neighborhood_sd <= 0.0:
        raise ExplainabilityIntegrityError(
            "lime_degenerate_model_output",
            "Model output has no weighted variation across the perturbation "
            "neighborhood; no local fidelity ratio is defined.",
        )
    fidelity_error_in_sigma = absolute_error / neighborhood_sd

    weighted_r2 = _weighted_r2(scored_targets, surrogate_predictions, design.weights)
    unweighted_r2 = _unweighted_r2(scored_targets, surrogate_predictions)

    holdout_r2: float | None = None
    holdout_rows = 0
    if active_config.with_holdout_diagnostic:
        holdout_rng = np.random.default_rng(int(active_config.seed) + 1)
        permutation = holdout_rng.permutation(n_rows)
        n_holdout = int(round(float(active_config.holdout_fraction) * n_rows))
        n_holdout = max(min(int(active_config.min_holdout_rows), n_rows - 1), n_holdout)
        n_fit = n_rows - n_holdout
        if (
            n_holdout >= int(active_config.min_holdout_rows)
            and n_fit >= panel_feature_count(panel) + int(active_config.min_holdout_rows)
        ):
            fit_idx = permutation[:n_fit]
            hold_idx = permutation[n_fit:]
            diagnostic_fit = _weighted_ridge_fit(
                design.mask[fit_idx],
                scored_targets[fit_idx],
                design.weights[fit_idx],
                ridge_alpha=float(active_config.ridge_alpha),
            )
            holdout_predictions = (
                diagnostic_fit.intercept
                + design.mask[hold_idx].astype(np.float64)
                @ diagnostic_fit.coefficients
            )
            holdout_r2 = _weighted_r2(
                scored_targets[hold_idx],
                holdout_predictions,
                design.weights[hold_idx],
            )
            holdout_rows = int(hold_idx.shape[0])

    effective_samples = fit.n_effective_samples
    if effective_samples < HARD_MIN_EFFECTIVE_SAMPLES:
        raise ExplainabilityIntegrityError(
            "lime_insufficient_effective_samples",
            "Kernel-weighted effective sample size is below the hard identifiability "
            "floor; the surrogate cannot be solved.",
        )

    absolute_weights = np.abs(fit.coefficients)
    order = sorted(
        range(len(absolute_weights)),
        key=lambda index: (-float(absolute_weights[index]), index),
    )
    ranks = {int(field_index): rank + 1 for rank, field_index in enumerate(order)}

    attributions: list[FeatureLimeAttribution] = []
    for field_index, spec in enumerate(panel.fields):
        ft = preprocessor.field_transforms[field_index]
        weight = float(fit.coefficients[field_index])
        estimator_columns = target_model.estimator_columns_for_raw_feature(field_index)
        if weight > 1e-12:
            direction = "increases_declared_target"
        elif weight < -1e-12:
            direction = "decreases_declared_target"
        else:
            direction = "no_local_surrogate_effect"
        attributions.append(
            FeatureLimeAttribution(
                feature_name=spec.name,
                clinical_meaning=spec.clinical_meaning,
                role=spec.role,
                unit=spec.unit,
                status=statuses[field_index],
                encoded_columns=tuple(ft.encoded_columns),
                estimator_input_columns=tuple(int(v) for v in estimator_columns),
                represented_in_estimator_input=bool(estimator_columns),
                lime_weight=weight,
                absolute_weight_rank=int(ranks[field_index]),
                local_direction=direction,
                reference_differs_from_instance_value=(
                    design.reference_differs_from_instance[field_index]
                ),
            )
        )

    if specification.resolved_target == LIME_TARGET_CALIBRATED_LOG_ODDS:
        score_alignment_note = (
            "Target is calibrated_log_odds: the local surrogate approximates "
            "logit(calibrated_research_score). LIME weights are local surrogate "
            "coefficients on that log-odds scale; they are NOT additive in "
            "probability units and NOT Shapley values."
        )
    elif specification.resolved_target == LIME_TARGET_RAW_MODEL_LOG_ODDS:
        score_alignment_note = (
            "Target is raw_model_log_odds: the local surrogate approximates "
            "logit(raw_model_score) from the exact logistic decision function. "
            "It does NOT include post-hoc calibration and is NOT additive in "
            "probability units."
        )
    else:
        score_alignment_note = (
            "Target is raw_model_score (raw_model_probability): the local "
            "surrogate approximates the uncalibrated mean forest probability. "
            "Post-hoc logistic calibration is not part of this target."
        )
    if not specification.comparable_with_family_shap_target:
        score_alignment_note = score_alignment_note + (
            " These LIME weights are not on the same scale as this family's "
            "exact SHAP attributions and must never be compared with them."
        )

    runtime_seconds = float(time.perf_counter() - started)
    perturbation_bytes = int(design.X_raw.nbytes + design.mask.nbytes)

    # Quality is assessed from the same numbers that are reported, so the
    # verdict can never drift from the published diagnostics.
    quality = assess_lime_quality_from_evidence(
        _quality_evidence(
            panel=panel,
            design=design,
            specification=specification,
            model_at_instance=model_at_instance,
            surrogate_at_instance=surrogate_at_instance,
            absolute_error=float(absolute_error),
            relative_error=float(relative_error),
            neighborhood_sd=float(neighborhood_sd),
            fidelity_error_in_sigma=float(fidelity_error_in_sigma),
            weighted_r2=weighted_r2,
            holdout_r2=holdout_r2,
            holdout_rows=int(holdout_rows),
            effective_samples=float(effective_samples),
            condition_number=float(fit.condition_number),
            coefficients=fit.coefficients,
            attribution_count=len(attributions),
        ),
        policy=active_policy,
        stability=stability,
    )

    return FaithfulLimeExplanation(
        method=LIME_METHOD,
        method_family=LIME_FAMILY,
        is_exact=False,
        is_local_approximation=True,
        additive_decomposition_claim=False,
        model_family=model_family,
        explained_quantity=specification.explained_quantity,
        scale=specification.scale,
        explains_calibrated_score_directly=(
            specification.explains_calibrated_score_directly
        ),
        linked_probability_quantity=specification.linked_probability_quantity,
        linked_probability_value=linked_probability,
        score_alignment_note=score_alignment_note,
        interpretation_note=LIME_INTERPRETATION_DISCLAIMER,
        score_bounds=specification.score_bounds,
        target_specification=specification,
        background_sample_count=int(background_raw.shape[0]),
        background_synthetic_only=bool(background.synthetic_only),
        background_reference_mode=design.reference_scheme,
        reference_scheme=design.reference_scheme,
        sampling_scheme=(
            "bernoulli_0_5_masks_plus_forced_instance_row"
            if active_config.include_instance_row
            else "bernoulli_0_5_masks_only"
        ),
        seed=int(active_config.seed),
        num_perturbations=int(n_rows),
        kernel="exponential_normalized_hamming",
        kernel_width=float(active_config.kernel_width),
        ridge_alpha=float(active_config.ridge_alpha),
        surrogate_intercept=float(fit.intercept),
        surrogate_prediction_at_instance=surrogate_at_instance,
        model_prediction_at_instance=model_at_instance,
        local_fidelity_abs_error=float(absolute_error),
        local_fidelity_relative_error=float(relative_error),
        neighborhood_output_weighted_sd=float(neighborhood_sd),
        local_fidelity_error_in_neighborhood_sigma=float(
            fidelity_error_in_sigma
        ),
        weighted_r2=weighted_r2,
        unweighted_r2=unweighted_r2,
        holdout_weighted_r2=holdout_r2,
        holdout_rows=int(holdout_rows),
        weighted_rmse=_weighted_rmse(
            scored_targets, surrogate_predictions, design.weights
        ),
        unweighted_rmse=_unweighted_rmse(scored_targets, surrogate_predictions),
        n_effective_samples=float(effective_samples),
        design_condition_number=float(fit.condition_number),
        model_rows_scored=int(n_rows + 1),
        model_call_count=int(model_call_count + 1),
        perturbation_matrix_bytes=perturbation_bytes,
        score_batch_size=int(active_config.score_batch_size),
        runtime_seconds=runtime_seconds,
        config_sha256=active_config.config_sha256,
        quality=quality,
        attributions=tuple(attributions),
    )
    return explanation


def assert_comparable_explanation_scales(
    shap_explanation: Any, lime_explanation: Any
) -> dict[str, Any]:
    """Fail closed when SHAP and LIME targets are not on the same scale.

    Both objects are accessed structurally (``explained_quantity``, ``scale``,
    ``linked_probability_quantity``) so this guard works for
    :class:`ai.explainability.FaithfulShapExplanation` without importing it.
    """
    shap_quantity = getattr(shap_explanation, "explained_quantity", None)
    shap_scale = getattr(shap_explanation, "scale", None)
    shap_linked = getattr(shap_explanation, "linked_probability_quantity", None)
    lime_quantity = getattr(lime_explanation, "explained_quantity", None)
    lime_scale = getattr(lime_explanation, "scale", None)
    lime_linked = getattr(lime_explanation, "linked_probability_quantity", None)
    if (
        shap_quantity is None
        or shap_scale is None
        or lime_quantity is None
        or lime_scale is None
    ):
        raise ExplainabilityIntegrityError(
            "incompatible_explanation_scales",
            "Cannot verify score-scale comparability for an explanation that "
            "does not declare its explained quantity and scale.",
        )
    if (
        shap_quantity != lime_quantity
        or shap_scale != lime_scale
        or shap_linked != lime_linked
    ):
        raise ExplainabilityIntegrityError(
            "incompatible_explanation_scales",
            "SHAP and LIME explanations target different quantities/scales and "
            "must not be compared numerically.",
        )
    return {
        "comparable": True,
        "shared_explained_quantity": lime_quantity,
        "shared_scale": lime_scale,
        "shared_linked_probability_quantity": lime_linked,
        "shap_method": getattr(shap_explanation, "method", None),
        "lime_method": getattr(lime_explanation, "method", None),
        "note": (
            "Both explanations target the same declared model-output quantity, "
            "but SHAP is an exact additive Shapley method while LIME is a local "
            "weighted surrogate approximation. Equal scale does not imply equal "
            "or interchangeable attributions."
        ),
    }


#: Severity ordering used to summarise per-seed fidelity statuses (worst first).
_FIDELITY_SEVERITY: Final[Mapping[str, int]] = MappingProxyType(
    {
        LimeQualityStatus.INVALID.value: 0,
        LimeQualityStatus.LOW_LOCAL_FIDELITY.value: 1,
        LimeQualityStatus.UNSTABLE.value: 2,
        LimeQualityStatus.UNVERIFIED_STABILITY.value: 3,
        LimeQualityStatus.ACCEPTABLE_LOCAL_APPROXIMATION.value: 4,
    }
)


def _spearman_correlation(first: np.ndarray, second: np.ndarray) -> float:
    a = np.asarray(first, dtype=np.float64).ravel()
    b = np.asarray(second, dtype=np.float64).ravel()
    if a.shape != b.shape or a.size < 2:
        return math.nan
    if float(np.ptp(a)) <= 1e-15 or float(np.ptp(b)) <= 1e-15:
        return 1.0 if np.allclose(a, b) else math.nan
    ranked_a = rankdata(a)
    ranked_b = rankdata(b)
    corr = float(np.corrcoef(ranked_a, ranked_b)[0, 1])
    return corr if math.isfinite(corr) else math.nan


def assess_lime_stability(
    seeds: Sequence[int],
    *,
    config: LimeConfig | None = None,
    top_k: int = 3,
    policy: LimeQualityPolicy | None = None,
    **explain_kwargs: Any,
) -> LimeStabilityReport:
    """Run the same LIME request across seeds and quantify weight stability.

    Only weight agreement is measured here. Each repeated explanation is
    generated independently and carries its own fidelity-only quality status,
    which is reported per seed so stability and fidelity are never conflated.
    """
    active_policy = policy if policy is not None else LimeQualityPolicy()
    seed_tuple = tuple(int(seed) for seed in seeds)
    if len(seed_tuple) < 2:
        raise ExplainabilityIntegrityError(
            "lime_stability_requires_multiple_seeds",
            "Stability assessment requires at least two distinct seeds.",
            field="seeds",
        )
    if len(set(seed_tuple)) != len(seed_tuple):
        raise ExplainabilityIntegrityError(
            "lime_stability_duplicate_seed",
            "Stability assessment seeds must be distinct.",
            field="seeds",
        )
    if any(seed < 0 for seed in seed_tuple):
        raise ExplainabilityIntegrityError(
            "lime_invalid_config",
            "Stability assessment seeds must be non-negative.",
            field="seeds",
        )
    base_config = config if config is not None else LimeConfig()
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
        raise ExplainabilityIntegrityError(
            "lime_invalid_config",
            "top_k must be a positive integer.",
            field="top_k",
        )

    started = time.perf_counter()
    explanations: list[FaithfulLimeExplanation] = []
    for seed in seed_tuple:
        active = dataclass_replace(base_config, seed=seed)
        explanations.append(
            explain_clinical_instance_lime(
                config=active, quality_policy=active_policy, **explain_kwargs
            )
        )
    runtime_seconds = float(time.perf_counter() - started)

    names = tuple(item.feature_name for item in explanations[0].attributions)
    weights = np.asarray(
        [[item.lime_weight for item in explanation.attributions] for explanation in explanations],
        dtype=np.float64,
    )
    n_seeds, n_features = weights.shape
    for explanation in explanations:
        if tuple(item.feature_name for item in explanation.attributions) != names:
            raise ExplainabilityIntegrityError(
                "lime_stability_feature_mismatch",
                "Repeated LIME runs produced different feature orderings.",
            )

    reference = weights[0]
    deviations = np.abs(weights - reference[None, :])
    max_abs_deviation = float(np.max(deviations))
    mean_abs_deviation = float(np.mean(deviations))
    feature_std = np.std(weights, axis=0, ddof=0)
    max_feature_std = float(np.max(feature_std))
    mean_feature_std = float(np.mean(feature_std))

    spearman_values: list[float] = []
    for first in range(n_seeds):
        for second in range(first + 1, n_seeds):
            value = _spearman_correlation(weights[first], weights[second])
            if math.isfinite(value):
                spearman_values.append(value)
    if spearman_values:
        min_spearman = float(np.min(spearman_values))
        mean_spearman = float(np.mean(spearman_values))
    else:
        min_spearman = math.nan
        mean_spearman = math.nan

    tolerance = 1e-12
    agreement_hits = 0
    agreement_total = 0
    for row_index in range(n_seeds):
        for field_index in range(n_features):
            reference_value = reference[field_index]
            value = weights[row_index, field_index]
            same_sign = (
                (reference_value > tolerance and value > tolerance)
                or (reference_value < -tolerance and value < -tolerance)
                or (
                    abs(reference_value) <= tolerance
                    and abs(value) <= tolerance
                )
            )
            agreement_hits += int(same_sign)
            agreement_total += 1
    sign_agreement = (
        float(agreement_hits) / float(agreement_total) if agreement_total else math.nan
    )

    effective_k = min(int(top_k), n_features)
    reference_top = set(
        np.argsort(-np.abs(reference), kind="stable")[:effective_k].tolist()
    )
    overlaps: list[float] = []
    for row_index in range(n_seeds):
        top = set(
            np.argsort(-np.abs(weights[row_index]), kind="stable")[
                :effective_k
            ].tolist()
        )
        overlaps.append(len(top & reference_top) / float(effective_k))
    top_k_overlap = float(np.mean(overlaps)) if overlaps else math.nan

    local_predictions = np.asarray(
        [explanation.surrogate_prediction_at_instance for explanation in explanations],
        dtype=np.float64,
    )
    max_local_deviation = float(
        np.max(np.abs(local_predictions - local_predictions[0]))
    )
    weighted_r2_values = [
        float(explanation.weighted_r2)
        for explanation in explanations
        if explanation.weighted_r2 is not None
    ]
    min_weighted_r2 = min(weighted_r2_values) if weighted_r2_values else None
    max_fidelity_error = float(
        max(
            explanation.local_fidelity_relative_error
            for explanation in explanations
        )
    )

    criteria = {
        "min_pairwise_spearman": float(active_policy.min_pairwise_spearman),
        "sign_agreement_fraction": float(
            active_policy.sign_agreement_fraction
        ),
        "top_k_overlap_fraction": float(active_policy.top_k_overlap_fraction),
    }
    stable = bool(
        math.isfinite(min_spearman)
        and min_spearman >= criteria["min_pairwise_spearman"]
        and math.isfinite(sign_agreement)
        and sign_agreement >= criteria["sign_agreement_fraction"]
        and math.isfinite(top_k_overlap)
        and top_k_overlap >= criteria["top_k_overlap_fraction"]
    )
    assessment = (
        "STABLE_WITHIN_REGISTERED_TOLERANCE" if stable else "SENSITIVE_TO_SEED"
    )
    per_seed_statuses = tuple(
        explanation.quality.status.value for explanation in explanations
    )
    worst_seed_status = str(
        max(
            per_seed_statuses,
            key=lambda value: _FIDELITY_SEVERITY.get(
                value, len(_FIDELITY_SEVERITY)
            ),
        )
    )

    return LimeStabilityReport(
        seeds=seed_tuple,
        reference_seed=seed_tuple[0],
        n_features=int(n_features),
        top_k=int(effective_k),
        feature_weight_mean_abs=tuple(
            float(v) for v in np.mean(np.abs(weights), axis=0)
        ),
        feature_weight_std=tuple(float(v) for v in feature_std),
        max_feature_weight_std=max_feature_std,
        mean_feature_weight_std=mean_feature_std,
        max_abs_weight_deviation_from_reference_seed=max_abs_deviation,
        mean_abs_weight_deviation_from_reference_seed=mean_abs_deviation,
        min_pairwise_spearman=min_spearman,
        mean_pairwise_spearman=mean_spearman,
        sign_agreement_fraction=sign_agreement,
        top_k_overlap_fraction=top_k_overlap,
        max_local_prediction_abs_deviation=max_local_deviation,
        min_weighted_r2=min_weighted_r2,
        max_local_fidelity_relative_error=max_fidelity_error,
        runtime_seconds=runtime_seconds,
        stability_assessment=assessment,
        criteria=MappingProxyType(dict(criteria)),
        per_seed_fidelity_statuses=per_seed_statuses,
        worst_seed_fidelity_status=worst_seed_status,
        quality_policy_sha256=active_policy.policy_sha256,
    )


def explain_clinical_instance_lime_certified(
    *,
    stability_seeds: Sequence[int] | None = DEFAULT_LIME_STABILITY_SEEDS,
    quality_policy: LimeQualityPolicy | None = None,
    **explain_kwargs: Any,
) -> tuple[FaithfulLimeExplanation, LimeStabilityReport | None]:
    """Generate one LIME explanation and certify it against the quality policy.

    The stability assessment (when requested) is generated independently and
    then folded into the explanation's quality verdict, so the caller receives
    one object whose ``quality`` field is complete. Passing
    ``stability_seeds=None`` deliberately leaves the verdict at
    ``UNVERIFIED_STABILITY`` at best.
    """
    active_policy = quality_policy if quality_policy is not None else LimeQualityPolicy()
    config = explain_kwargs.get("config")
    explanation = explain_clinical_instance_lime(
        quality_policy=active_policy, **explain_kwargs
    )
    if stability_seeds is None:
        return explanation, None
    seeds = tuple(int(seed) for seed in stability_seeds)
    if len(seeds) < 2:
        return explanation, None
    stability = assess_lime_stability(
        seeds,
        config=config,
        policy=active_policy,
        top_k=int(active_policy.top_k),
        **{k: v for k, v in explain_kwargs.items() if k != "config"},
    )
    return explanation.certify(stability=stability, policy=active_policy), stability


__all__ = [
    "ALLOWED_LIME_REFERENCE_SCHEMES",
    "ALLOWED_LIME_TARGETS",
    "FaithfulLimeExplanation",
    "FeatureLimeAttribution",
    "LIME_FAMILY",
    "LIME_METHOD",
    "LIME_REFERENCE_FIXED_BACKGROUND",
    "LIME_REFERENCE_SAMPLED_MARGINALS",
    "LIME_SCHEMA_VERSION",
    "DEFAULT_LIME_STABILITY_SEEDS",
    "LimeConfig",
    "LimeModelTarget",
    "LimeStabilityReport",
    "LimeTargetSpecification",
    "MANDATORY_LIME_LIMITATIONS",
    "SUPPORTED_LIME_MODEL_FAMILIES",
    "assert_comparable_explanation_scales",
    "assess_lime_stability",
    "build_lime_model_target",
    "decode_background_to_raw_rows",
    "explain_clinical_instance_lime",
    "explain_clinical_instance_lime_certified",
    "validate_instance_row",
]
