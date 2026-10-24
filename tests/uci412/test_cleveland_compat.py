"""Cleveland (D-047) regression-compatibility checks.

UCI-412 work must not alter the frozen Cleveland protocol, its panel, its seeds,
or its preprocessing contract. These tests are deliberately read-only.
"""
from __future__ import annotations

import json

import numpy as np
import pytest
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

from research.experiments.config import DEFAULT_CONFIG as CLEVELAND_CONFIG
from research.experiments.models import build_family_estimator as build_cleveland_estimator


def test_cleveland_panel_and_target_are_unchanged() -> None:
    assert CLEVELAND_CONFIG.feature_names == ("age", "sex", "cp", "trestbps", "restecg")
    assert CLEVELAND_CONFIG.target_column == "num"
    assert CLEVELAND_CONFIG.outer_folds == 5
    assert CLEVELAND_CONFIG.inner_folds == 5
    assert CLEVELAND_CONFIG.threshold == 0.5
    assert CLEVELAND_CONFIG.outer_repeat_seeds == (20261023, 20261024, 20261025, 20261026)


def test_cleveland_preprocessing_contract_still_builds() -> None:
    for family in ("l2_logistic_regression", "constrained_random_forest"):
        estimator = build_cleveland_estimator(family, random_state=20261024)
        assert isinstance(estimator, Pipeline)
        assert isinstance(estimator.named_steps["preprocess"], ColumnTransformer)


def test_cleveland_plan_file_is_a_frozen_json_protocol() -> None:
    from research.experiments.config import PLAN_PATH

    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    assert plan["protocol_id"] == "CAI-T1-D047-CLEVELAND-EXPLORATORY-V0.1"
    assert plan["cv"]["outer_folds"] == 5
    assert plan["cv"]["inner_folds"] == 5
    assert plan["cv"]["outer_repeat_seeds"] == [20261023, 20261024, 20261025, 20261026]
    assert plan["cv"]["primary_outer_assessment_metric"] == "roc_auc"
    assert plan["dataset"]["relative_file"]


def test_building_uci412_objects_does_not_touch_the_global_numpy_rng() -> None:
    from research.uci412.config import SMOKE_TEST_PROFILE
    from research.uci412.evaluation import plan_outer_folds, derive_bootstrap_seed
    from research.uci412.models import build_family_estimator

    np.random.seed(12345)
    expected = np.random.random(5)

    np.random.seed(12345)
    for family in ("l2_logistic_regression", "constrained_random_forest"):
        build_family_estimator(family, random_state=1, config=SMOKE_TEST_PROFILE)
    derive_bootstrap_seed(20261024)
    y = np.array([0] * 87 + [1] * 216)
    plan_outer_folds(y, 20261024, SMOKE_TEST_PROFILE)
    assert np.array_equal(np.random.random(5), expected)


@pytest.mark.parametrize("name", ["uci412", "experiments"])
def test_both_research_packages_coexist(name: str) -> None:
    import importlib

    module = importlib.import_module(f"research.{name}")
    assert module is not None
