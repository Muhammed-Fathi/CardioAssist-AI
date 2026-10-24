"""Model-family, preprocessing, and structural leakage-contract tests."""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from research.uci412.config import DEFAULT_CONFIG
from research.uci412.errors import ModelNotAvailableError, SchemaError
from research.uci412.models import (
    MODEL_FAMILIES,
    assert_pipeline_contract,
    assert_registered_feature_names,
    build_family_estimator,
    build_preprocessor,
    family_parameter_grid,
    make_prevalence_dummy,
    preprocessing_contract,
    registered_categories,
)

from tests.uci412.conftest import make_dataset, small_config


def _branch(pipeline, name: str):
    """Configured (unfitted) branch from a ColumnTransformer."""
    return {key: transformer for key, transformer, _ in pipeline.named_steps["preprocess"].transformers}[name]


def test_registered_families_are_the_bounded_pair() -> None:
    assert MODEL_FAMILIES == ("l2_logistic_regression", "constrained_random_forest")
    assert "gradient_boosting_reserved" not in MODEL_FAMILIES


def test_reserved_boosted_tree_extension_point_fails_closed() -> None:
    with pytest.raises(ModelNotAvailableError):
        build_family_estimator("gradient_boosting_reserved", random_state=1)
    with pytest.raises(ModelNotAvailableError):
        family_parameter_grid("gradient_boosting_reserved")
    with pytest.raises(ModelNotAvailableError):
        build_preprocessor("gradient_boosting_reserved")


def test_unknown_family_is_rejected() -> None:
    with pytest.raises(SchemaError):
        build_family_estimator("xgboost", random_state=1)


def test_parameter_grids_are_exactly_the_registered_grids() -> None:
    assert family_parameter_grid("l2_logistic_regression") == {
        "classifier__C": [0.1, 1.0, 10.0]
    }
    assert family_parameter_grid("constrained_random_forest") == {
        "classifier__max_depth": [3, 5],
        "classifier__min_samples_leaf": [5, 10],
    }


def test_prevalence_baseline_uses_no_predictors() -> None:
    dummy = make_prevalence_dummy()
    assert dummy.strategy == "prior"
    X = np.zeros((20, 3))
    y = np.array([0] * 15 + [1] * 5)
    dummy.fit(X, y)
    probabilities = dummy.predict_proba(X)
    assert np.allclose(probabilities[:, 1], 0.25)


def test_preprocessing_statistics_are_fitted_on_the_training_rows_only() -> None:
    config = small_config()
    dataset = make_dataset(config)
    estimator = build_family_estimator("l2_logistic_regression", random_state=7, config=config)
    train_rows = np.arange(0, 200)
    estimator.fit(dataset.X[train_rows], dataset.y[train_rows])
    numeric = estimator.named_steps["preprocess"].named_transformers_["numeric"]
    imputer = numeric.named_steps["median_imputer"]
    numeric_indices = [config.feature_names.index(name) for name in config.numeric_features]
    expected = np.nanmedian(dataset.X[np.ix_(train_rows, numeric_indices)], axis=0)
    assert np.allclose(imputer.statistics_, expected)


def test_scaler_is_fitted_on_training_statistics_only() -> None:
    config = small_config()
    dataset = make_dataset(config)
    estimator = build_family_estimator("l2_logistic_regression", random_state=7, config=config)
    train_rows = np.arange(0, 150)
    estimator.fit(dataset.X[train_rows], dataset.y[train_rows])
    scaler = (
        estimator.named_steps["preprocess"]
        .named_transformers_["numeric"]
        .named_steps["standard_scaler"]
    )
    numeric_indices = [config.feature_names.index(name) for name in config.numeric_features]
    expected = np.nanmean(dataset.X[np.ix_(train_rows, numeric_indices)], axis=0)
    assert np.allclose(scaler.mean_, expected)


def test_categorical_encoder_uses_the_registered_vocabulary_not_observed_values() -> None:
    config = small_config()
    dataset = make_dataset(config)
    estimator = build_family_estimator("constrained_random_forest", random_state=3, config=config)
    # Fit on a subset that may not contain every category.
    estimator.fit(dataset.X[:120], dataset.y[:120])
    encoder = (
        estimator.named_steps["preprocess"]
        .named_transformers_["categorical"]
        .named_steps["fixed_vocabulary_one_hot"]
    )
    for actual, expected in zip(encoder.categories, registered_categories(config), strict=True):
        assert np.array_equal(np.asarray(actual, dtype=float), expected)


def test_unseen_category_fails_closed() -> None:
    config = small_config()
    dataset = make_dataset(config)
    estimator = build_family_estimator("constrained_random_forest", random_state=3, config=config)
    estimator.fit(dataset.X[:200], dataset.y[:200])
    mutated = dataset.X[:10].copy()
    categorical_index = config.feature_names.index(config.categorical_features[0])
    mutated[:, categorical_index] = 7.0
    with pytest.raises(ValueError):
        estimator.predict_proba(mutated)


def test_all_missing_training_fold_fails_closed() -> None:
    config = small_config()
    dataset = make_dataset(config)
    mutated = dataset.X[:120].copy()
    numeric_index = config.feature_names.index(config.numeric_features[0])
    mutated[:, numeric_index] = np.nan
    estimator = build_family_estimator("l2_logistic_regression", random_state=3, config=config)
    with pytest.raises(SchemaError):
        estimator.fit(mutated, dataset.y[:120])


@pytest.mark.parametrize(
    "tamper",
    [
        lambda pipeline: _branch(pipeline, "categorical").named_steps[
            "fixed_vocabulary_one_hot"
        ].__setattr__("handle_unknown", "ignore"),
        lambda pipeline: _branch(pipeline, "categorical").named_steps[
            "fixed_vocabulary_one_hot"
        ].__setattr__("drop", None),
        lambda pipeline: _branch(pipeline, "numeric").named_steps["median_imputer"].__setattr__(
            "strategy", "mean"
        ),
        lambda pipeline: pipeline.named_steps["preprocess"].__setattr__("remainder", "passthrough"),
    ],
)
def test_pipeline_contract_rejects_tampering(tamper) -> None:
    estimator = build_family_estimator("l2_logistic_regression", random_state=1)
    tamper(estimator)
    with pytest.raises(SchemaError):
        assert_pipeline_contract(estimator, "l2_logistic_regression")


def test_pipeline_contract_rejects_an_extra_step() -> None:
    estimator = build_family_estimator("l2_logistic_regression", random_state=1)
    tampered = Pipeline([*estimator.steps, ("posthoc", make_prevalence_dummy())])
    with pytest.raises(SchemaError):
        assert_pipeline_contract(tampered, "l2_logistic_regression")


def test_contract_accepts_the_registered_pipelines() -> None:
    for family in MODEL_FAMILIES:
        estimator = build_family_estimator(family, random_state=11)
        assert isinstance(estimator, Pipeline)
        assert isinstance(estimator.named_steps["preprocess"], ColumnTransformer)
        assert isinstance(
            _branch(estimator, "categorical").named_steps["fixed_vocabulary_one_hot"],
            OneHotEncoder,
        )
        assert_pipeline_contract(estimator, family)


def test_prohibited_predictors_cannot_enter_the_matrix() -> None:
    with pytest.raises(SchemaError):
        assert_registered_feature_names(("Cath",) + DEFAULT_CONFIG.feature_names[1:])
    with pytest.raises(SchemaError):
        assert_registered_feature_names(tuple(reversed(DEFAULT_CONFIG.feature_names)))
    assert_registered_feature_names(DEFAULT_CONFIG.feature_names)


def test_reduced_fixture_config_changes_only_fit_budget_not_the_panel() -> None:
    config = small_config()
    assert config.feature_names == DEFAULT_CONFIG.feature_names
    assert config.expected_class_counts == DEFAULT_CONFIG.expected_class_counts
    assert config.threshold == DEFAULT_CONFIG.threshold
    assert config.category_codes == DEFAULT_CONFIG.category_codes
    assert config.outer_folds < DEFAULT_CONFIG.outer_folds


def test_preprocessing_contract_record_has_no_row_level_content() -> None:
    record = preprocessing_contract()
    assert record["global_preprocessing_before_cv"] is False
    assert record["learned_inside_pipeline_only"] is True
    assert record["feature_selection"] == "NONE"
    assert record["unseen_category_policy"] == "ERROR_FAIL_CLOSED"


def test_forest_is_single_threaded_and_registered() -> None:
    estimator = build_family_estimator("constrained_random_forest", random_state=5)
    forest = estimator.named_steps["classifier"]
    assert forest.n_jobs == 1
    assert forest.n_estimators == DEFAULT_CONFIG.rf_n_estimators
    assert forest.max_features == DEFAULT_CONFIG.rf_max_features


def test_logistic_regression_is_l2_penalised() -> None:
    estimator = build_family_estimator("l2_logistic_regression", random_state=5)
    classifier = estimator.named_steps["classifier"]
    assert classifier.penalty == "l2"
    assert classifier.solver == "liblinear"
    assert classifier.max_iter == DEFAULT_CONFIG.logistic_max_iter


def test_replaced_config_cannot_expand_the_grid_beyond_registered_values() -> None:
    config = replace(DEFAULT_CONFIG, logistic_c_values=(0.1,))
    assert family_parameter_grid("l2_logistic_regression", config=config) == {
        "classifier__C": [0.1]
    }
    config = replace(DEFAULT_CONFIG, rf_max_depths=(3,))
    assert family_parameter_grid("constrained_random_forest", config=config)["classifier__max_depth"] == [3]
