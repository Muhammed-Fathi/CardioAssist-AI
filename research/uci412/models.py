"""Fold-local preprocessing and the bounded UCI-412 candidate model families.

The preprocessing contract mirrors the reviewed D-047 Cleveland pattern
(training-fold median/mode imputation, fixed-vocabulary reference one-hot
encoding, no variance-based or target-based selection) but is implemented
locally so the source-specific UCI-412 harness stays independent of the frozen
Cleveland module and cannot change its behaviour.

Every transform lives inside a scikit-learn ``Pipeline``. Preprocessing is
therefore fitted on the outer/inner training folds only; the module exposes
``assert_pipeline_contract`` so a runtime check can refuse any pipeline whose
structure would allow outside-fold information to reach the model.
"""
from __future__ import annotations

from typing import Any, Mapping

import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from research.uci412.config import (
    DEFAULT_CONFIG,
    RESERVED_MODEL_FAMILIES,
    Uci412Config,
)
from research.uci412.errors import ModelNotAvailableError, SchemaError
from research.uci412.source_spec import PROHIBITED_PREDICTORS

MODEL_FAMILIES: tuple[str, ...] = (
    "l2_logistic_regression",
    "constrained_random_forest",
)


class ObservedValuesGuard(BaseEstimator, TransformerMixin):
    """Fail closed when a training fold has no observed value for a column.

    Deliberately duplicated from the verified D-047 guard instead of imported so
    that the UCI-412 harness has no runtime dependency on the Cleveland module.
    """

    def fit(self, X: Any, y: Any = None) -> "ObservedValuesGuard":
        values = np.asarray(X, dtype=np.float64)
        if values.ndim != 2 or values.shape[1] == 0:
            raise SchemaError("Preprocessing received an invalid training-fold matrix.")
        if np.isnan(values).all(axis=0).any():
            raise SchemaError("A feature has no observed values in this training fold.")
        self.n_features_in_ = int(values.shape[1])
        return self

    def transform(self, X: Any) -> np.ndarray:
        values = np.asarray(X, dtype=np.float64)
        if values.ndim != 2 or values.shape[1] != self.n_features_in_:
            raise SchemaError("Preprocessing received an unexpected feature shape.")
        return values


def assert_registered_feature_names(feature_names: tuple[str, ...], config: Uci412Config = DEFAULT_CONFIG) -> None:
    """Refuse any model matrix that is not the registered panel, in order."""
    if tuple(feature_names) != tuple(config.feature_names):
        raise SchemaError("The model matrix does not match the registered primary panel order.")
    if set(feature_names) & PROHIBITED_PREDICTORS:
        raise SchemaError("A prohibited target/angiography/identifier column reached the model matrix.")


def _numeric_indices(config: Uci412Config) -> list[int]:
    return [config.feature_names.index(name) for name in config.numeric_features]


def _categorical_indices(config: Uci412Config) -> list[int]:
    return [config.feature_names.index(name) for name in config.categorical_features]


def registered_categories(config: Uci412Config = DEFAULT_CONFIG) -> list[np.ndarray]:
    """Fixed category codes per categorical feature, frozen from the schema."""
    return [
        np.asarray(sorted(config.category_code_map[name]), dtype=np.float64)
        for name in config.categorical_features
    ]


def build_preprocessor(
    family: str,
    *,
    config: Uci412Config = DEFAULT_CONFIG,
) -> ColumnTransformer:
    """Build the registered preprocessing column transformer (unfitted)."""
    if family not in MODEL_FAMILIES:
        if family in RESERVED_MODEL_FAMILIES:
            raise ModelNotAvailableError(
                "The boosted-tree comparator is a reserved extension point and is not implemented."
            )
        raise SchemaError("Only the registered L2 logistic and constrained forest are selectable.")

    numeric_steps: list[tuple[str, Any]] = [
        ("observed_values_guard", ObservedValuesGuard()),
        ("median_imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
    ]
    if family == "l2_logistic_regression":
        numeric_steps.append(("standard_scaler", StandardScaler()))

    categorical_steps: list[tuple[str, Any]] = [
        ("observed_values_guard", ObservedValuesGuard()),
        ("mode_imputer", SimpleImputer(strategy="most_frequent", keep_empty_features=True)),
        (
            "fixed_vocabulary_one_hot",
            OneHotEncoder(
                categories=registered_categories(config),
                drop="first",
                handle_unknown="error",
                sparse_output=True,
            ),
        ),
    ]
    return ColumnTransformer(
        transformers=[
            ("numeric", Pipeline(numeric_steps), _numeric_indices(config)),
            ("categorical", Pipeline(categorical_steps), _categorical_indices(config)),
        ],
        remainder="drop",
        sparse_threshold=0.3,
    )


def build_family_estimator(
    family: str,
    *,
    random_state: int,
    config: Uci412Config = DEFAULT_CONFIG,
) -> Pipeline:
    """Construct one registered candidate as a single fold-local pipeline."""
    if family not in MODEL_FAMILIES:
        if family in RESERVED_MODEL_FAMILIES:
            raise ModelNotAvailableError(
                "The boosted-tree comparator is a reserved extension point and is not implemented."
            )
        raise SchemaError("Only the registered L2 logistic and constrained forest are selectable.")

    if family == "l2_logistic_regression":
        classifier: Any = LogisticRegression(
            penalty="l2",
            C=float(config.logistic_c_values[0]),
            solver="liblinear",
            max_iter=config.logistic_max_iter,
            random_state=int(random_state),
            n_jobs=1,
        )
    else:
        classifier = RandomForestClassifier(
            n_estimators=config.rf_n_estimators,
            max_depth=config.rf_max_depths[0],
            min_samples_leaf=config.rf_min_samples_leaf[0],
            max_features=config.rf_max_features,
            n_jobs=1,
            random_state=int(random_state),
        )

    pipeline = Pipeline(
        [("preprocess", build_preprocessor(family, config=config)), ("classifier", classifier)]
    )
    assert_pipeline_contract(pipeline, family, config=config)
    return pipeline


def family_parameter_grid(
    family: str,
    *,
    config: Uci412Config = DEFAULT_CONFIG,
) -> dict[str, list[Any]]:
    """Return the registered, bounded hyperparameter grid for one family."""
    if family == "l2_logistic_regression":
        return {"classifier__C": [float(value) for value in config.logistic_c_values]}
    if family == "constrained_random_forest":
        return {
            "classifier__max_depth": list(config.rf_max_depths),
            "classifier__min_samples_leaf": list(config.rf_min_samples_leaf),
        }
    if family in RESERVED_MODEL_FAMILIES:
        raise ModelNotAvailableError(
            "The boosted-tree comparator is a reserved extension point and is not implemented."
        )
    raise SchemaError("Only the registered L2 logistic and constrained forest are selectable.")


def make_prevalence_dummy() -> DummyClassifier:
    """Training-fold prevalence baseline; it never reads a predictor."""
    return DummyClassifier(strategy="prior")


def assert_pipeline_contract(
    pipeline: Any,
    family: str,
    *,
    config: Uci412Config = DEFAULT_CONFIG,
) -> None:
    """Structural leakage guard: the pipeline must match the registered contract.

    A pipeline that adds outside-fold transforms, changes the imputation
    statistics, replaces the fixed category vocabulary, or applies an unseen
    category policy other than fail-closed is rejected before it can be fitted.
    """
    if not isinstance(pipeline, Pipeline):
        raise SchemaError("Each candidate must be a sklearn Pipeline so all transforms are fold-local.")
    if [name for name, _ in pipeline.steps] != ["preprocess", "classifier"]:
        raise SchemaError("The candidate pipeline must have exactly preprocess and classifier steps.")

    preprocess = pipeline.named_steps["preprocess"]
    if not isinstance(preprocess, ColumnTransformer):
        raise SchemaError("The preprocess step must be a ColumnTransformer.")
    if preprocess.remainder != "drop":
        raise SchemaError("Unregistered columns must be dropped, never transformed.")
    branches = {name: (transformer, columns) for name, transformer, columns in preprocess.transformers}
    if set(branches) != {"numeric", "categorical"}:
        raise SchemaError("Only the registered numeric and categorical branches are permitted.")

    numeric_pipeline, numeric_columns = branches["numeric"]
    expected_numeric_steps = ["observed_values_guard", "median_imputer"]
    if family == "l2_logistic_regression":
        expected_numeric_steps.append("standard_scaler")
    if not isinstance(numeric_pipeline, Pipeline) or [
        name for name, _ in numeric_pipeline.steps
    ] != expected_numeric_steps:
        raise SchemaError("The numeric branch does not match the registered preprocessing steps.")
    numeric_imputer = numeric_pipeline.named_steps["median_imputer"]
    if not isinstance(numeric_imputer, SimpleImputer) or numeric_imputer.strategy != "median":
        raise SchemaError("Numeric imputation must be the training-fold median.")
    if list(numeric_columns) != _numeric_indices(config):
        raise SchemaError("The numeric branch does not use the registered numeric columns.")

    categorical_pipeline, categorical_columns = branches["categorical"]
    if not isinstance(categorical_pipeline, Pipeline) or [
        name for name, _ in categorical_pipeline.steps
    ] != ["observed_values_guard", "mode_imputer", "fixed_vocabulary_one_hot"]:
        raise SchemaError("The categorical branch does not match the registered preprocessing steps.")
    mode_imputer = categorical_pipeline.named_steps["mode_imputer"]
    if not isinstance(mode_imputer, SimpleImputer) or mode_imputer.strategy != "most_frequent":
        raise SchemaError("Categorical imputation must be the training-fold mode.")
    encoder = categorical_pipeline.named_steps["fixed_vocabulary_one_hot"]
    if not isinstance(encoder, OneHotEncoder):
        raise SchemaError("Categorical encoding must use OneHotEncoder.")
    if encoder.handle_unknown != "error":
        raise SchemaError("Unseen categories must fail closed, never be silently ignored.")
    if encoder.drop != "first":
        raise SchemaError("Categorical encoding must be reference-coded (drop='first').")
    expected_categories = registered_categories(config)
    if encoder.categories is None or len(encoder.categories) != len(expected_categories):
        raise SchemaError("The encoder vocabulary does not match the registered schema.")
    for actual, expected in zip(encoder.categories, expected_categories, strict=True):
        if not np.array_equal(np.asarray(actual, dtype=np.float64), expected):
            raise SchemaError("The encoder vocabulary does not match the registered schema.")
    if list(categorical_columns) != _categorical_indices(config):
        raise SchemaError("The categorical branch does not use the registered categorical columns.")

    classifier = pipeline.named_steps["classifier"]
    if family == "l2_logistic_regression":
        if not isinstance(classifier, LogisticRegression) or classifier.penalty != "l2":
            raise SchemaError("The registered logistic candidate must be L2-penalised.")
    elif family == "constrained_random_forest":
        if not isinstance(classifier, RandomForestClassifier):
            raise SchemaError("The registered forest candidate must be a RandomForestClassifier.")
        if classifier.n_estimators != config.rf_n_estimators:
            raise SchemaError("The forest must use the registered number of trees.")
        if classifier.n_jobs != 1:
            raise SchemaError("The forest must be single-threaded for reproducible fitting.")
        if classifier.max_features != config.rf_max_features:
            raise SchemaError("The forest must use the registered max_features.")
    else:
        raise SchemaError("Only the registered model families are selectable.")


def preprocessing_contract(config: Uci412Config = DEFAULT_CONFIG) -> Mapping[str, Any]:
    """Readable, non-secret description of the preprocessing for the run report."""
    return {
        "learned_inside_pipeline_only": True,
        "numeric_features": list(config.numeric_features),
        "categorical_features": list(config.categorical_features),
        "numeric_imputation": "median fitted on the training fold",
        "numeric_scaling": "StandardScaler fitted on the training fold (logistic family only)",
        "categorical_imputation": "most frequent value fitted on the training fold",
        "categorical_encoding": "OneHotEncoder(drop='first') with registered fixed category vocabulary",
        "unseen_category_policy": "ERROR_FAIL_CLOSED",
        "all_missing_column_policy": "SCHEMA_ERROR_FAIL_CLOSED",
        "feature_selection": "NONE",
        "global_preprocessing_before_cv": False,
        "class_weighting": "NONE",
    }
