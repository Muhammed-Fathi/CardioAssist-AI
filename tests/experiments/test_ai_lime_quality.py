"""LIME explanation-quality assessment tests (AI-5.1 quality corrections).

These tests cover the separation between *generating* a LIME explanation and
*accepting* it as a trustworthy local approximation:

1. the registered quality policy and its documented, generation-independent
   thresholds;
2. the five machine-readable verdicts and their precedence;
3. real good-fidelity LR / forest explanations reaching
   ``ACCEPTABLE_LOCAL_APPROXIMATION``;
4. real low-fidelity explanations (reference-noise and non-linear-model cases)
   that must never be reported as faithful, including the "small instance
   error, poor neighborhood fidelity" trap;
5. real seed-sensitive explanations (``UNSTABLE``) and the independence of
   stability from fidelity;
6. unassessed stability never certifying an explanation;
7. raw-versus-calibrated target separation;
8. JSON serialization/round-trip of the verdict and CLI warning display;
9. unchanged exact SHAP behaviour.

All cohorts, backgrounds, estimators and bundles are synthetic and generated in
memory or inside pytest temporary directories; no real patient data is touched.
"""

from __future__ import annotations

import json
import math
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression

import ai.lime_quality as quality_mod
from ai import (
    CRITERION_FAIL,
    DA_A2_RESTING_LABS_PANEL,
    DIMENSION_FAIL,
    DIMENSION_NOT_ASSESSED,
    DIMENSION_PASS,
    ExplainabilityIntegrityError,
    FoldSafeClinicalPreprocessor,
    LIME_QUALITY_GUARD_UNRELIABLE,
    LimeConfig,
    LimeQualityEvidence,
    LimeQualityPolicy,
    LimeQualityStatus,
    OofLogisticCalibrator,
    ShapBackgroundReference,
    assess_lime_quality,
    assess_lime_stability,
    assert_comparable_explanation_scales,
    certify_lime_explanation,
    explain_clinical_instance,
    explain_clinical_instance_lime,
    explain_clinical_instance_lime_certified,
    require_acceptable_lime_quality,
    validate_cohort_records,
)
from ai.errors import AiPipelineError
from ai.validation_harness import _make_synthetic_cohort

INSTANCE = 2
STABILITY_SEEDS = (11, 12, 13)
DEFAULT_CONFIG = LimeConfig(num_perturbations=512, seed=4242)


# --------------------------------------------------------------------------- #
# Deterministic synthetic fixture
# --------------------------------------------------------------------------- #


def _fit_environment() -> SimpleNamespace:
    records, labels = _make_synthetic_cohort(180, seed=20261025)
    X, y, _ = validate_cohort_records(
        records, labels, DA_A2_RESTING_LABS_PANEL, require_synthetic=True
    )
    preprocessor = FoldSafeClinicalPreprocessor.fit(
        X, DA_A2_RESTING_LABS_PANEL
    )
    Z = preprocessor.transform(X)
    background = ShapBackgroundReference.from_training_encoded(
        Z, y, preprocessor, max_samples=32, seed=7
    )
    logistic = LogisticRegression(
        C=1.0, solver="lbfgs", max_iter=1000, random_state=7
    ).fit(Z, y)
    forest = RandomForestClassifier(
        n_estimators=24,
        max_depth=4,
        min_samples_leaf=4,
        random_state=7,
        n_jobs=1,
    ).fit(Z, y)
    # A deliberately over-flexible forest: its local behaviour is strongly
    # non-linear, so a linear surrogate cannot represent the neighborhood.
    flexible_forest = RandomForestClassifier(
        n_estimators=40,
        max_depth=None,
        min_samples_leaf=1,
        random_state=7,
        n_jobs=1,
    ).fit(Z, y)
    # A near-constant stump forest: outputs are dominated by a few steps, so the
    # surrogate coefficients are mostly sampling noise.
    stump_forest = RandomForestClassifier(
        n_estimators=3, max_depth=1, min_samples_leaf=25, random_state=7, n_jobs=1
    ).fit(Z, y)
    logistic_calibrator = OofLogisticCalibrator.fit_from_oof(
        y,
        logistic.predict_proba(Z)[:, 1],
        model_family="l2_logistic_regression",
        raw_logits=logistic.decision_function(Z),
    )
    forest_calibrator = OofLogisticCalibrator.fit_from_oof(
        y, forest.predict_proba(Z)[:, 1], model_family="constrained_random_forest"
    )
    return SimpleNamespace(
        records=records,
        X=X,
        y=y,
        Z=Z,
        preprocessor=preprocessor,
        background=background,
        logistic=logistic,
        forest=forest,
        flexible_forest=flexible_forest,
        stump_forest=stump_forest,
        logistic_calibrator=logistic_calibrator,
        forest_calibrator=forest_calibrator,
    )


@pytest.fixture(scope="module")
def env() -> SimpleNamespace:
    return _fit_environment()


def _explain(env: SimpleNamespace, **overrides: Any) -> Any:
    kwargs: dict[str, Any] = dict(
        model_family="l2_logistic_regression",
        estimator=env.logistic,
        preprocessor=env.preprocessor,
        panel=DA_A2_RESTING_LABS_PANEL,
        background=env.background,
        x_raw_row=env.X[INSTANCE],
        z_row=env.Z[INSTANCE],
        calibrator=env.logistic_calibrator,
        config=DEFAULT_CONFIG,
    )
    kwargs.update(overrides)
    return explain_clinical_instance_lime(**kwargs)


def _explain_certified(env: SimpleNamespace, **overrides: Any) -> tuple[Any, Any]:
    kwargs: dict[str, Any] = dict(
        model_family="l2_logistic_regression",
        estimator=env.logistic,
        preprocessor=env.preprocessor,
        panel=DA_A2_RESTING_LABS_PANEL,
        background=env.background,
        x_raw_row=env.X[INSTANCE],
        z_row=env.Z[INSTANCE],
        calibrator=env.logistic_calibrator,
        config=DEFAULT_CONFIG,
    )
    kwargs.update(overrides)
    seeds = kwargs.pop("stability_seeds", STABILITY_SEEDS)
    return explain_clinical_instance_lime_certified(
        stability_seeds=seeds, **kwargs
    )


def _evidence(**overrides: Any) -> LimeQualityEvidence:
    """Neutral evidence for pure classifier tests (no model, no data)."""
    values: dict[str, Any] = dict(
        n_features=7,
        num_perturbations=512,
        explained_quantity="raw_model_score",
        scale="raw_model_probability",
        reference_scheme="fixed_background_reference",
        model_prediction_at_instance=0.5,
        surrogate_prediction_at_instance=0.5,
        local_fidelity_abs_error=1e-4,
        local_fidelity_relative_error=2e-4,
        neighborhood_output_weighted_sd=0.1,
        local_fidelity_error_in_neighborhood_sigma=1e-3,
        weighted_r2=0.9,
        holdout_weighted_r2=0.9,
        holdout_rows=150,
        n_effective_samples=450.0,
        design_condition_number=50.0,
        max_abs_lime_weight=0.2,
        all_weights_finite=True,
        attribution_count=7,
    )
    values.update(overrides)
    return LimeQualityEvidence(**values)


def _stability(**overrides: Any) -> SimpleNamespace:
    values: dict[str, Any] = dict(
        seeds=STABILITY_SEEDS,
        top_k=3,
        stability_assessment="STABLE_WITHIN_REGISTERED_TOLERANCE",
        min_pairwise_spearman=0.95,
        mean_pairwise_spearman=0.97,
        sign_agreement_fraction=1.0,
        top_k_overlap_fraction=1.0,
        max_feature_weight_std=0.01,
        max_abs_weight_deviation_from_reference_seed=0.02,
        max_local_prediction_abs_deviation=0.001,
        per_seed_fidelity_statuses=("UNVERIFIED_STABILITY",) * 3,
        runtime_seconds=0.02,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


# --------------------------------------------------------------------------- #
# 1. Policy: documented, generation-independent thresholds
# --------------------------------------------------------------------------- #


def test_quality_policy_defaults_are_documented_and_generation_independent() -> None:
    policy = LimeQualityPolicy()
    payload = policy.to_json_dict()
    # Thresholds are stated in variance-explained / sigma / condition-number
    # terms; none of them is tuned per fixture.
    assert payload["min_weighted_r2"] == 0.5
    assert payload["min_holdout_weighted_r2"] == 0.5
    assert payload["max_local_fidelity_error_in_neighborhood_sigma"] == 0.25
    assert payload["max_local_fidelity_relative_error"] == 0.25
    assert payload["min_effective_samples"] == 20.0
    assert payload["max_design_condition_number"] == 1e6
    assert payload["min_pairwise_spearman"] == 0.5
    assert payload["sign_agreement_fraction"] == 0.75
    assert payload["top_k_overlap_fraction"] == 0.6
    assert payload["min_stability_seeds"] == 3
    assert payload["require_holdout_diagnostic"] is True
    assert payload["require_stability_assessment"] is True
    assert payload["policy_version"] == quality_mod.LIME_QUALITY_POLICY_VERSION

    # Deterministic digest; changing a threshold changes the digest.
    assert policy.policy_sha256 == LimeQualityPolicy().policy_sha256
    assert policy.policy_sha256 != LimeQualityPolicy(
        min_weighted_r2=0.6
    ).policy_sha256

    # Generation config carries no acceptance threshold at all.
    config_fields = set(LimeConfig.__dataclass_fields__)
    assert not config_fields & {
        "min_weighted_r2",
        "min_holdout_weighted_r2",
        "max_local_fidelity_relative_error",
        "max_design_condition_number",
        "min_effective_samples",
    }

    for invalid in (
        {"min_weighted_r2": 2.0},
        {"max_local_fidelity_relative_error": 0.0},
        {"min_effective_samples": 1.0},
        {"sign_agreement_fraction": 1.5},
        {"min_stability_seeds": 1},
        {"top_k": 0},
        {"max_design_condition_number": float("nan")},
    ):
        with pytest.raises(ExplainabilityIntegrityError) as exc_info:
            LimeQualityPolicy(**invalid)
        assert exc_info.value.code == "lime_quality_invalid_policy"


# --------------------------------------------------------------------------- #
# 2. Verdicts and precedence (pure classifier)
# --------------------------------------------------------------------------- #


def test_quality_statuses_and_precedence_are_explicit() -> None:
    acceptable = quality_mod.assess_lime_quality_from_evidence(
        _evidence(), stability=_stability()
    )
    assert acceptable.status is LimeQualityStatus.ACCEPTABLE_LOCAL_APPROXIMATION
    assert acceptable.is_reliable_for_interpretation is True
    assert acceptable.failed_criteria == ()
    assert all(
        outcome == DIMENSION_PASS
        for outcome in acceptable.dimensions.values()
    )

    invalid = quality_mod.assess_lime_quality_from_evidence(
        _evidence(design_condition_number=1e12, all_weights_finite=False),
        stability=_stability(),
    )
    assert invalid.status is LimeQualityStatus.INVALID
    assert invalid.dimensions[quality_mod.QUALITY_DIMENSION_NUMERICAL_VALIDITY] == (
        DIMENSION_FAIL
    )

    low = quality_mod.assess_lime_quality_from_evidence(
        _evidence(weighted_r2=0.2, holdout_weighted_r2=0.1),
        stability=_stability(),
    )
    assert low.status is LimeQualityStatus.LOW_LOCAL_FIDELITY

    unstable = quality_mod.assess_lime_quality_from_evidence(
        _evidence(),
        stability=_stability(
            stability_assessment="SENSITIVE_TO_SEED",
            min_pairwise_spearman=0.1,
            sign_agreement_fraction=0.4,
            top_k_overlap_fraction=0.2,
        ),
    )
    assert unstable.status is LimeQualityStatus.UNSTABLE

    unverified = quality_mod.assess_lime_quality_from_evidence(_evidence())
    assert unverified.status is LimeQualityStatus.UNVERIFIED_STABILITY
    assert unverified.dimensions[quality_mod.QUALITY_DIMENSION_STABILITY] == (
        DIMENSION_NOT_ASSESSED
    )

    # An INVALID explanation stays INVALID even if its weights happen to be
    # stable, and a LOW-fidelity explanation is never reported as merely
    # UNSTABLE: fidelity failure outranks stability failure.
    both_bad = quality_mod.assess_lime_quality_from_evidence(
        _evidence(weighted_r2=0.0, holdout_weighted_r2=0.0),
        stability=_stability(stability_assessment="SENSITIVE_TO_SEED", min_pairwise_spearman=0.0),
    )
    assert both_bad.status is LimeQualityStatus.LOW_LOCAL_FIDELITY

    # Missing holdout evidence cannot be silently accepted.
    no_holdout = quality_mod.assess_lime_quality_from_evidence(
        _evidence(holdout_weighted_r2=None, holdout_rows=0),
        stability=_stability(),
    )
    assert no_holdout.status is LimeQualityStatus.LOW_LOCAL_FIDELITY
    assert "holdout_weighted_r2" in no_holdout.unassessed_criteria

    # The documented escape hatch: without a stability requirement, a
    # fidelity-passing explanation can be accepted.
    relaxed = LimeQualityPolicy(require_stability_assessment=False)
    assert (
        quality_mod.assess_lime_quality_from_evidence(
            _evidence(), policy=relaxed
        ).status
        is LimeQualityStatus.ACCEPTABLE_LOCAL_APPROXIMATION
    )


def test_guard_text_distinguishes_acceptable_from_diagnostic_only() -> None:
    acceptable = quality_mod.assess_lime_quality_from_evidence(
        _evidence(), stability=_stability()
    )
    assert "local weighted-linear approximation" in (
        acceptable.interpretation_guard
    )
    assert "DO NOT RELY" not in acceptable.interpretation_guard

    low = quality_mod.assess_lime_quality_from_evidence(
        _evidence(weighted_r2=0.1), stability=_stability()
    )
    assert low.interpretation_guard == LIME_QUALITY_GUARD_UNRELIABLE
    assert "DO NOT RELY" in low.interpretation_guard
    assert low.is_diagnostic_only is True
    assert "Do not interpret the weights" in low.recommended_action
    assert any("Neighborhood fidelity is insufficient" in w for w in low.warnings)


# --------------------------------------------------------------------------- #
# 3. Real good-fidelity explanations
# --------------------------------------------------------------------------- #


def test_good_fidelity_logistic_explanation_is_acceptable(
    env: SimpleNamespace,
) -> None:
    explanation, stability = _explain_certified(env)
    assert explanation.explained_quantity == "calibrated_log_odds"
    assert explanation.reference_scheme == "fixed_background_reference"
    assert stability is not None
    assert stability.stability_assessment == "STABLE_WITHIN_REGISTERED_TOLERANCE"
    assert explanation.quality.status is (
        LimeQualityStatus.ACCEPTABLE_LOCAL_APPROXIMATION
    )
    assert explanation.is_reliable_for_interpretation is True
    assert explanation.quality.stability_seeds == STABILITY_SEEDS
    assert explanation.quality.stable_explanation is True
    assert float(explanation.weighted_r2) >= 0.9
    assert float(explanation.holdout_weighted_r2) >= 0.9
    assert explanation.local_fidelity_error_in_neighborhood_sigma <= 0.25
    # Explicitly a local approximation even when accepted.
    assert explanation.is_exact is False
    assert explanation.additive_decomposition_claim is False
    assert any(
        "local approximation only" in warning
        for warning in explanation.quality.warnings
    )
    require_acceptable_lime_quality(explanation)  # does not raise


def test_good_fidelity_forest_explanation_is_acceptable(
    env: SimpleNamespace,
) -> None:
    explanation, _ = _explain_certified(
        env,
        model_family="constrained_random_forest",
        estimator=env.forest,
        calibrator=None,
    )
    assert explanation.explained_quantity == "raw_model_score"
    assert explanation.scale == "raw_model_probability"
    assert explanation.quality.status is (
        LimeQualityStatus.ACCEPTABLE_LOCAL_APPROXIMATION
    )
    assert float(explanation.weighted_r2) >= 0.5
    assert float(explanation.holdout_weighted_r2) >= 0.5
    assert explanation.quality.dimensions[
        quality_mod.QUALITY_DIMENSION_NEIGHBORHOOD_FIDELITY
    ] == DIMENSION_PASS


# --------------------------------------------------------------------------- #
# 4. Real low-fidelity explanations are never labeled faithful
# --------------------------------------------------------------------------- #


def test_reference_noise_explanation_is_low_fidelity(
    env: SimpleNamespace,
) -> None:
    """Marginal reference sampling injects noise no linear surrogate can model."""
    explanation = _explain(
        env,
        model_family="constrained_random_forest",
        estimator=env.flexible_forest,
        calibrator=None,
        config=LimeConfig(
            num_perturbations=512,
            seed=4242,
            reference_scheme="sampled_background_marginals",
        ),
    )
    payload = explanation.to_dict()
    assert payload["reference"]["scheme"] == "sampled_background_marginals"
    assert payload["reference"]["reference_values_emitted"] is False
    assert all(
        item["reference_differs_from_instance_value"] is None
        for item in payload["attributions"]
    )
    assert explanation.quality.status is LimeQualityStatus.LOW_LOCAL_FIDELITY
    assert explanation.is_reliable_for_interpretation is False
    assert float(explanation.weighted_r2) < 0.5
    assert explanation.quality.dimensions[
        quality_mod.QUALITY_DIMENSION_NEIGHBORHOOD_FIDELITY
    ] == DIMENSION_FAIL
    assert any(
        "Neighborhood fidelity is insufficient" in warning
        for warning in explanation.quality.warnings
    )
    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        require_acceptable_lime_quality(explanation)
    assert exc_info.value.code == "lime_quality_not_acceptable"


def test_small_instance_error_is_not_neighborhood_fidelity(
    env: SimpleNamespace,
) -> None:
    """The classic trap: the surrogate matches f(x) yet explains the region badly.

    With very few perturbations the marginal-reference surrogate reproduces the
    model output at the explained instance almost exactly, while explaining
    roughly half of the model's own neighborhood variation. The verdict must
    follow the neighborhood, and the warning must say so explicitly.
    """
    explanation = _explain(
        env,
        config=LimeConfig(
            num_perturbations=128,
            seed=4242,
            reference_scheme="sampled_background_marginals",
        ),
    )
    assert explanation.local_fidelity_error_in_neighborhood_sigma <= 0.25
    assert explanation.quality.dimensions[
        quality_mod.QUALITY_DIMENSION_INSTANCE_FIDELITY
    ] == DIMENSION_PASS
    assert explanation.quality.dimensions[
        quality_mod.QUALITY_DIMENSION_NEIGHBORHOOD_FIDELITY
    ] == DIMENSION_FAIL
    assert explanation.quality.status is LimeQualityStatus.LOW_LOCAL_FIDELITY
    assert any(
        "small local prediction error must not be read as a faithful"
        in warning
        for warning in explanation.quality.warnings
    )


def test_nonlinear_model_explanation_is_low_fidelity_but_stable(
    env: SimpleNamespace,
) -> None:
    """A stable approximation can still be a poor one (fidelity != stability)."""
    explanation, stability = _explain_certified(
        env,
        model_family="constrained_random_forest",
        estimator=env.flexible_forest,
        calibrator=None,
        config=LimeConfig(num_perturbations=512, seed=4242),
    )
    assert stability is not None
    assert stability.stability_assessment == "STABLE_WITHIN_REGISTERED_TOLERANCE"
    assert explanation.quality.status is LimeQualityStatus.LOW_LOCAL_FIDELITY
    assert explanation.quality.stable_explanation is True
    # The failing dimension is instance fidelity, not seed stability.
    assert explanation.quality.dimensions[
        quality_mod.QUALITY_DIMENSION_STABILITY
    ] == DIMENSION_PASS
    assert explanation.quality.dimensions[
        quality_mod.QUALITY_DIMENSION_INSTANCE_FIDELITY
    ] == DIMENSION_FAIL
    assert any(
        criterion.name == "local_fidelity_error_in_neighborhood_sigma"
        and criterion.outcome == CRITERION_FAIL
        for criterion in explanation.quality.criteria
    )
    assert set(stability.per_seed_fidelity_statuses) == {"LOW_LOCAL_FIDELITY"}
    assert stability.worst_seed_fidelity_status == "LOW_LOCAL_FIDELITY"


def test_sampled_reference_scheme_reduces_neighborhood_fidelity(
    env: SimpleNamespace,
) -> None:
    """Reference-sampling noise is real and measurable, not a threshold trick."""
    fixed = _explain(env)
    sampled = _explain(
        env,
        config=LimeConfig(
            num_perturbations=512,
            seed=4242,
            reference_scheme="sampled_background_marginals",
        ),
    )
    assert float(fixed.weighted_r2) > float(sampled.weighted_r2) + 0.3
    assert fixed.quality.dimensions[
        quality_mod.QUALITY_DIMENSION_NEIGHBORHOOD_FIDELITY
    ] == DIMENSION_PASS


# --------------------------------------------------------------------------- #
# 5. Real seed-sensitive explanations
# --------------------------------------------------------------------------- #


def test_seed_sensitive_explanation_is_unstable(
    env: SimpleNamespace,
) -> None:
    """A near-constant model yields coefficient noise that flips across seeds."""
    config = LimeConfig(
        num_perturbations=64, seed=11, reference_scheme="fixed_background_reference"
    )
    stability = assess_lime_stability(
        tuple(range(11, 16)),
        model_family="constrained_random_forest",
        estimator=env.stump_forest,
        preprocessor=env.preprocessor,
        panel=DA_A2_RESTING_LABS_PANEL,
        background=env.background,
        x_raw_row=env.X[INSTANCE],
        z_row=env.Z[INSTANCE],
        config=config,
    )
    assert stability.stability_assessment == "SENSITIVE_TO_SEED"
    explanation, _ = _explain_certified(
        env,
        model_family="constrained_random_forest",
        estimator=env.stump_forest,
        calibrator=None,
        config=config,
        stability_seeds=tuple(range(11, 16)),
    )
    assert explanation.quality.status is LimeQualityStatus.UNSTABLE
    assert explanation.is_reliable_for_interpretation is False
    assert explanation.quality.dimensions[
        quality_mod.QUALITY_DIMENSION_STABILITY
    ] == DIMENSION_FAIL
    assert any(
        "Stability is independent of fidelity" in warning
        for warning in explanation.quality.warnings
    )
    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        require_acceptable_lime_quality(explanation)
    assert exc_info.value.code == "lime_quality_not_acceptable"


def test_unassessed_stability_never_certifies_an_explanation(
    env: SimpleNamespace,
) -> None:
    explanation = _explain(env)
    assert explanation.quality.status is LimeQualityStatus.UNVERIFIED_STABILITY
    assert explanation.is_reliable_for_interpretation is False
    assert explanation.quality.stability_summary is None
    assert explanation.quality.stable_explanation is None
    assert any(
        "Seed stability was not assessed" in warning
        for warning in explanation.quality.warnings
    )
    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        require_acceptable_lime_quality(explanation)
    assert exc_info.value.code == "lime_quality_not_acceptable"

    # Certification attaches, but never fabricates, stability evidence.
    certified = certify_lime_explanation(explanation)
    assert certified.quality.status is LimeQualityStatus.UNVERIFIED_STABILITY
    with pytest.raises(ExplainabilityIntegrityError):
        certify_lime_explanation(SimpleNamespace(attributions=()))


# --------------------------------------------------------------------------- #
# 6. Assessment is pure: it never changes the generated explanation
# --------------------------------------------------------------------------- #


def test_quality_assessment_never_changes_generated_weights(
    env: SimpleNamespace,
) -> None:
    strict = LimeQualityPolicy(
        min_weighted_r2=0.9999,
        min_holdout_weighted_r2=0.9999,
        max_local_fidelity_error_in_neighborhood_sigma=1e-9,
    )
    plain = _explain(env)
    strict_explanation = _explain(env, quality_policy=strict)
    assert strict_explanation.weight_map() == plain.weight_map()
    assert (
        strict_explanation.config_sha256 == plain.config_sha256
    )  # generation config unchanged
    assert strict_explanation.quality.policy.policy_sha256 == (
        strict.policy_sha256
    )
    assert strict_explanation.quality.status is (
        LimeQualityStatus.LOW_LOCAL_FIDELITY
    )
    assert plain.quality.status is LimeQualityStatus.UNVERIFIED_STABILITY

    # Reassessing the same numbers is deterministic.
    first = assess_lime_quality(plain)
    second = assess_lime_quality(plain)
    assert first.to_dict() == second.to_dict()


# --------------------------------------------------------------------------- #
# 7. JSON serialization and CLI display
# --------------------------------------------------------------------------- #


def test_quality_verdict_serializes_and_round_trips_through_json(
    env: SimpleNamespace,
) -> None:
    explanation, _ = _explain_certified(env)
    payload = explanation.to_dict()
    text = json.dumps(payload, allow_nan=False, sort_keys=True)
    restored = json.loads(text)
    quality = restored["quality"]
    assert quality["status"] == "ACCEPTABLE_LOCAL_APPROXIMATION"
    assert quality["is_reliable_for_interpretation"] is True
    assert quality["is_diagnostic_only"] is False
    assert quality["schema_version"] == quality_mod.LIME_QUALITY_SCHEMA_VERSION
    assert quality["policy_sha256"] == LimeQualityPolicy().policy_sha256
    assert quality["stability_summary"]["seeds"] == list(STABILITY_SEEDS)
    assert set(quality["dimensions"]) == set(quality_mod.QUALITY_DIMENSIONS)
    assert all(
        set(criterion) >= {"name", "dimension", "observed", "threshold",
                           "comparison", "outcome", "unit", "rationale"}
        for criterion in quality["criteria"]
    )
    assert quality["warnings"]

    # The serialized payload is itself assessable and agrees with the object.
    reassessed = assess_lime_quality(restored)
    assert reassessed.status.value == quality["status"]
    assert reassessed.failed_criteria == tuple(quality["failed_criteria"])

    # The deterministic digest excludes wall-clock runtime only, including the
    # timing recorded inside the attached stability summary.
    assert "runtime" not in explanation.deterministic_payload()
    assert "runtime_seconds" not in (
        explanation.deterministic_payload()["quality"]["stability_summary"]
    )
    repeat, _ = _explain_certified(
        env, config=LimeConfig(num_perturbations=512, seed=4242)
    )
    assert repeat.state_sha256 == explanation.state_sha256


def test_low_fidelity_payload_carries_guard_and_cli_renders_warnings(
    env: SimpleNamespace,
) -> None:
    from ai.cli import _render_lime_text

    explanation = _explain(
        env,
        model_family="constrained_random_forest",
        estimator=env.flexible_forest,
        calibrator=None,
        config=LimeConfig(
            num_perturbations=512,
            seed=4242,
            reference_scheme="sampled_background_marginals",
        ),
    )
    payload = json.loads(json.dumps(explanation.to_dict(), allow_nan=False))
    assert payload["quality"]["is_reliable_for_interpretation"] is False
    assert "DO NOT RELY" in payload["quality"]["interpretation_guard"]
    text = "\n".join(_render_lime_text(payload))
    assert "quality status: LOW_LOCAL_FIDELITY [DIAGNOSTIC ONLY]" in text
    assert "DO NOT RELY ON THESE FEATURE WEIGHTS" in text
    assert "quality warnings:" in text
    assert "do not rely on this weight" in text

    good = _explain_certified(env)[0]
    good_text = "\n".join(_render_lime_text(good.to_dict()))
    assert "quality status: ACCEPTABLE_LOCAL_APPROXIMATION" in good_text
    assert "DO NOT RELY" not in good_text
    assert "do not rely on this weight" not in good_text
    assert "seed stability: STABLE_WITHIN_REGISTERED_TOLERANCE" in good_text


def test_cli_stability_flag_resolution_fails_closed() -> None:
    from ai.cli import (
        _resolve_cli_lime_config,
        _resolve_cli_lime_stability_seeds,
    )
    from ai.lime_explainability import DEFAULT_LIME_STABILITY_SEEDS

    def args(**overrides: Any) -> SimpleNamespace:
        base = {
            "with_lime": False,
            "lime_seed": None,
            "lime_perturbations": None,
            "lime_reference_scheme": None,
            "lime_stability_seeds": None,
            "lime_no_stability": False,
            "lime_require_acceptable_quality": False,
        }
        base.update(overrides)
        return SimpleNamespace(**base)

    assert _resolve_cli_lime_config(args()) is None
    assert _resolve_cli_lime_stability_seeds(args()) is None
    assert _resolve_cli_lime_stability_seeds(
        args(with_lime=True)
    ) == DEFAULT_LIME_STABILITY_SEEDS
    assert _resolve_cli_lime_stability_seeds(
        args(with_lime=True, lime_no_stability=True)
    ) is None
    assert _resolve_cli_lime_stability_seeds(
        args(with_lime=True, lime_stability_seeds="5, 6,6")
    ) == (5, 6)

    for bad in ("", "1", "5,5", "a,b", "5,-1"):
        with pytest.raises(AiPipelineError) as exc_info:
            _resolve_cli_lime_stability_seeds(
                args(with_lime=True, lime_stability_seeds=bad)
            )
        assert exc_info.value.code == "cli_invalid_lime_stability_seeds"

    with pytest.raises(AiPipelineError) as exc_info:
        _resolve_cli_lime_config(
            args(with_lime=True, lime_stability_seeds="5,6", lime_no_stability=True)
        )
    assert exc_info.value.code == "cli_conflicting_lime_stability_flags"

    # An undecodable reference scheme fails closed at config construction.
    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        _resolve_cli_lime_config(
            args(with_lime=True, lime_reference_scheme="not_a_scheme")
        )
    assert exc_info.value.code == "lime_invalid_config"


# --------------------------------------------------------------------------- #
# 8. Calibrated versus raw target separation
# --------------------------------------------------------------------------- #


def test_raw_and_calibrated_targets_are_separately_explained_and_certified(
    env: SimpleNamespace,
) -> None:
    raw = _explain(env, target="raw_model_log_odds")
    calibrated = _explain(env, calibrator=env.logistic_calibrator)
    assert raw.explained_quantity == "raw_model_log_odds"
    assert raw.scale == "raw_log_odds"
    assert calibrated.explained_quantity == "calibrated_log_odds"
    assert calibrated.scale == "calibrated_log_odds"
    assert raw.explains_calibrated_score_directly is False
    assert calibrated.explains_calibrated_score_directly is True
    # Different mathematical outputs => different target values and weights.
    assert raw.model_prediction_at_instance != pytest.approx(
        calibrated.model_prediction_at_instance
    )
    assert raw.weight_map() != calibrated.weight_map()
    # Each verdict is computed on its own declared scale.
    assert raw.quality.evidence.scale == "raw_log_odds"
    assert calibrated.quality.evidence.scale == "calibrated_log_odds"
    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        assert_comparable_explanation_scales(raw, calibrated)
    assert exc_info.value.code == "incompatible_explanation_scales"

    # Forest: raw probability versus an explicitly calibrated log-odds target.
    forest_raw, _ = _explain_certified(
        env,
        model_family="constrained_random_forest",
        estimator=env.forest,
        calibrator=None,
    )
    forest_calibrated, _ = _explain_certified(
        env,
        model_family="constrained_random_forest",
        estimator=env.forest,
        calibrator=env.forest_calibrator,
        target="calibrated_log_odds",
    )
    assert forest_raw.explained_quantity == "raw_model_score"
    assert forest_calibrated.explained_quantity == "calibrated_log_odds"
    assert forest_calibrated.target_specification.comparable_with_family_shap_target is False
    assert forest_raw.quality.status is LimeQualityStatus.ACCEPTABLE_LOCAL_APPROXIMATION
    assert forest_calibrated.quality.status is not LimeQualityStatus.INVALID
    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        assert_comparable_explanation_scales(forest_raw, forest_calibrated)
    assert exc_info.value.code == "incompatible_explanation_scales"

    # Calibrator/target mismatches fail closed before any perturbation.
    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        _explain(env, calibrator=None, target="calibrated_log_odds")
    assert exc_info.value.code == "lime_calibrator_required"
    with pytest.raises(ExplainabilityIntegrityError) as exc_info:
        _explain(
            env,
            model_family="constrained_random_forest",
            estimator=env.forest,
            calibrator=env.logistic_calibrator,
            target="calibrated_log_odds",
        )
    assert exc_info.value.code == "lime_incompatible_calibrator"


# --------------------------------------------------------------------------- #
# 9. Exact SHAP behaviour is unchanged
# --------------------------------------------------------------------------- #


def test_exact_shap_behaviour_is_unchanged_by_lime(
    env: SimpleNamespace,
) -> None:
    kw_good_logistic = dict(
        model_family="l2_logistic_regression",
        estimator=env.logistic,
        preprocessor=env.preprocessor,
        panel=DA_A2_RESTING_LABS_PANEL,
        background=env.background,
        z_row=env.Z[INSTANCE],
        calibrator=env.logistic_calibrator,
    )
    before = explain_clinical_instance(**kw_good_logistic)
    assert before.sum_check_passed is True
    assert before.max_abs_discrepancy <= 1e-9
    assert before.explained_quantity == "calibrated_log_odds"
    assert before.additive_on_calibrated_probability is False
    before_payload = before.to_dict()

    explanation, _ = _explain_certified(env)
    after = explain_clinical_instance(**kw_good_logistic)
    after_payload = after.to_dict()
    assert after_payload == before_payload
    assert after.sum_check_passed is True
    assert after.additive_on_calibrated_probability is False

    # On the same declared scale the two explanations may be reported together,
    # but the paired note must keep LIME approximate and SHAP exact.
    comparability = assert_comparable_explanation_scales(before, explanation)
    assert comparability["comparable"] is True
    assert comparability["shared_scale"] == "calibrated_log_odds"
    assert "exact" in comparability["note"]
    assert "approximation" in comparability["note"]
    assert explanation.is_exact is False
    assert before_payload["method"].endswith("shap") or "shap" in (
        before_payload["method"]
    )
    assert before.faithful_to_model_family is True
    assert before.synthetic_placeholder is False


def test_missing_numerical_diagnostics_fail_closed_as_invalid() -> None:
    """A missing required diagnostic must never look like a perfect score."""
    assessment = quality_mod.assess_lime_quality_from_evidence(
        _evidence(n_effective_samples=math.nan),
        stability=_stability(),
    )
    assert assessment.status is LimeQualityStatus.INVALID
    assert (
        "effective_samples" in assessment.failed_criteria
    )

    nan_condition = quality_mod.assess_lime_quality_from_evidence(
        _evidence(design_condition_number=math.inf), stability=_stability()
    )
    assert nan_condition.status is LimeQualityStatus.INVALID
    assert "design_condition_number" in nan_condition.failed_criteria

    # A missing *fidelity* diagnostic is a fidelity failure, not an omission.
    missing_error = quality_mod.assess_lime_quality_from_evidence(
        _evidence(
            local_fidelity_relative_error=math.nan,
            local_fidelity_error_in_neighborhood_sigma=math.nan,
        ),
        stability=_stability(),
    )
    assert missing_error.status is LimeQualityStatus.LOW_LOCAL_FIDELITY
    assert missing_error.dimensions[
        quality_mod.QUALITY_DIMENSION_INSTANCE_FIDELITY
    ] == DIMENSION_FAIL


def test_quality_evidence_rejects_non_finite_inputs_honestly() -> None:
    evidence = _evidence(
        neighborhood_output_weighted_sd=None,
        local_fidelity_error_in_neighborhood_sigma=None,
        weighted_r2=None,
    )
    assessment = quality_mod.assess_lime_quality_from_evidence(
        evidence, stability=_stability()
    )
    assert assessment.status is LimeQualityStatus.LOW_LOCAL_FIDELITY
    assert "local_fidelity_error_in_neighborhood_sigma" in (
        assessment.unassessed_criteria
    )
    assert "weighted_r2" in assessment.unassessed_criteria
    assert all(
        criterion.outcome != CRITERION_FAIL
        for criterion in assessment.criteria
        if criterion.name == "weighted_r2"
    )
    assert any("not_available" in warning for warning in assessment.warnings)
    assert math.isfinite(
        quality_mod.assess_lime_quality_from_evidence(
            _evidence(), stability=_stability()
        ).criteria[0].observed
    )
