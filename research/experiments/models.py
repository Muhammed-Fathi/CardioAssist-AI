"""Fold-local sklearn pipelines and bounded model-selection grids."""
from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from research.experiments.config import DEFAULT_CONFIG, ExperimentConfig

MODEL_FAMILIES = ("l2_logistic_regression", "constrained_random_forest")


class RejectAllMissingColumns(BaseEstimator, TransformerMixin):
    """Fail rather than inventing a zero when a training-fold column is empty."""

    def fit(self, X: Any, y: Any = None) -> "RejectAllMissingColumns":
        values = np.asarray(X, dtype=np.float64)
        if values.ndim != 2 or values.shape[1] == 0:
            raise ValueError("Preprocessing received an invalid training-fold matrix.")
        if np.isnan(values).all(axis=0).any():
            raise ValueError("A feature has no observed values in this training fold.")
        self.n_features_in_ = int(values.shape[1])
        return self

    def transform(self, X: Any) -> np.ndarray:
        values = np.asarray(X, dtype=np.float64)
        if values.ndim != 2 or values.shape[1] != self.n_features_in_:
            raise ValueError("Preprocessing received an unexpected feature shape.")
        return values


def _preprocessor(family: str, config: ExperimentConfig) -> ColumnTransformer:
    numeric_indices = [config.feature_names.index(name) for name in config.numeric_features]
    categorical_indices = [config.feature_names.index(name) for name in config.categorical_features]
    numeric_steps: list[tuple[str, Any]] = [
        ("observed_guard", RejectAllMissingColumns()),
        ("imputer", SimpleImputer(strategy="median")),
    ]
    if family == "l2_logistic_regression":
        numeric_steps.append(("scaler", StandardScaler()))

    category_codes = config.category_codes
    categories = [
        np.asarray(category_codes[name], dtype=np.float64)
        for name in config.categorical_features
    ]
    categorical_pipeline = Pipeline(
        steps=[
            ("observed_guard", RejectAllMissingColumns()),
            ("imputer", SimpleImputer(strategy="most_frequent")),
            (
                "one_hot",
                OneHotEncoder(
                    categories=categories,
                    drop="first",
                    handle_unknown="error",
                    sparse_output=True,
                    dtype=np.float64,
                ),
            ),
        ]
    )
    return ColumnTransformer(
        transformers=[
            ("numeric", Pipeline(steps=numeric_steps), numeric_indices),
            ("categorical", categorical_pipeline, categorical_indices),
        ],
        remainder="drop",
        sparse_threshold=0.3,
        verbose_feature_names_out=True,
    )


def build_family_estimator(
    family: str,
    *,
    random_state: int,
    config: ExperimentConfig = DEFAULT_CONFIG,
) -> Pipeline:
    """Create a fresh preprocessing+estimator pipeline for one candidate family."""
    if family not in MODEL_FAMILIES:
        raise ValueError("Only the registered L2 logistic and constrained forest are selectable.")
    if family == "l2_logistic_regression":
        classifier: BaseEstimator = LogisticRegression(
            solver="liblinear",
            penalty="l2",
            C=1.0,
            max_iter=config.logistic_max_iter,
            class_weight=None,
            random_state=int(random_state),
        )
    else:
        classifier = RandomForestClassifier(
            n_estimators=config.rf_n_estimators,
            max_depth=config.rf_max_depths[0],
            min_samples_leaf=config.rf_min_samples_leaf[0],
            max_features=config.rf_max_features,
            class_weight=None,
            random_state=int(random_state),
            n_jobs=1,
        )
    return Pipeline(
        steps=[
            ("preprocess", _preprocessor(family, config)),
            ("classifier", classifier),
        ]
    )


def family_parameter_grid(
    family: str,
    *,
    config: ExperimentConfig = DEFAULT_CONFIG,
) -> dict[str, list[Any]]:
    """Return a fixed, bounded grid; no CLI or manifest may expand it."""
    if family == "l2_logistic_regression":
        return {"classifier__C": list(config.logistic_c_values)}
    if family == "constrained_random_forest":
        return {
            "classifier__max_depth": list(config.rf_max_depths),
            "classifier__min_samples_leaf": list(config.rf_min_samples_leaf),
        }
    raise ValueError("Only the registered L2 logistic and constrained forest are selectable.")


def make_prevalence_dummy() -> Any:
    """Create the training-fold-only prevalence baseline (no predictors)."""
    from sklearn.dummy import DummyClassifier

    return DummyClassifier(strategy="prior")
