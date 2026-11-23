"""Producer lineage for the registered synthetic development cohorts.

This module is the **single** place that knows how the two registered synthetic
producers build their development cohorts and how the training run splits them.
It exists because an earlier revision hardcoded a cohort seed that did not match
the producer, which silently invalidated every identity derived from it.

Design rules, all of them load-bearing:

* Configuration is **imported from the registered producer**, never re-typed.
  ``DEMO_SEED``, ``DEMO_N_ROWS``, ``DEMO_TRAINING_CONFIG`` and
  ``Uci412ResearchModelConfig`` are the producers' own declarations.
* The five distinct seeds are kept distinct, because collapsing them is exactly
  how the previous defect happened:

  ==================  ==========================================  ===============
  role                value (REST / BASIC)                       source
  ==================  ==========================================  ===============
  cohort generation   20261117 / 20261028                         producer const
  CV repeat seed      20261025 / 20261025                         the producers'
  inner-CV seed       repeat + 1000*fold + 10*family_offset       ``ai/training``
  full-CV seed        repeat + 90000                              ``ai/training``
  final calibration   full_cv + 333                               ``ai/training``
  SHAP background     full_cv + 4242                              ``ai/training``
  ==================  ==========================================  ===============

* The ordered feature/target identity is captured at the **training boundary** --
  i.e. after the producer's cohort builder and after the project's own cohort
  validator -- not from a re-derived descriptive summary.
* The UCI-412 held-out cohort is generated independently from
  ``config.seed + 1``; it is **not** a slice of the development array. No
  contiguous "holdout indices" are ever fabricated.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Final, Mapping

import numpy as np


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_bytes(document: Any) -> bytes:
    return (
        json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    ).encode("utf-8")


# --------------------------------------------------------------------------- #
# Registered producers, described by their own declarations                    #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ProducerSpec:
    """One registered synthetic producer's cohort and split configuration."""

    route_id: str
    builder: str
    cohort_seed: int
    n_development: int
    repeat_seed: int
    outer_folds: int
    inner_folds: int
    #: Set only when the producer generates a *separately seeded* held-out cohort.
    heldout_seed: int | None
    n_heldout: int | None
    #: The producer's forest size, read from its training configuration.
    rf_n_estimators: int = 20

    @property
    def full_cv_seed(self) -> int:
        """``ai/training.py`` full-cohort CV seed for this producer."""
        return int(self.repeat_seed) + 90000

    @property
    def calibration_seed(self) -> int:
        """Final-development OOF calibration splitter seed."""
        return self.full_cv_seed + 333

    @property
    def shap_background_seed(self) -> int:
        return self.full_cv_seed + 4242

    def inner_seed(self, fold_index: int, family_offset: int) -> int:
        """Per-family inner-CV seed for an outer fold (``ai/training.py``)."""
        return int(self.repeat_seed) + 1000 * int(fold_index) + 10 * int(family_offset)

    def as_dict(self) -> dict[str, Any]:
        return {
            "route_id": self.route_id,
            "builder": self.builder,
            "cohort_seed": int(self.cohort_seed),
            "n_development": int(self.n_development),
            "repeat_seed": int(self.repeat_seed),
            "outer_folds": int(self.outer_folds),
            "inner_folds": int(self.inner_folds),
            "heldout_seed": None if self.heldout_seed is None else int(self.heldout_seed),
            "n_heldout": None if self.n_heldout is None else int(self.n_heldout),
            "rf_n_estimators": int(self.rf_n_estimators),
        }


def _resting_spec() -> ProducerSpec:
    """The AI-7 resting demo producer, read from its own constants."""
    from ai.research_demo import DEMO_N_ROWS, DEMO_ROUTE_ID, DEMO_SEED, DEMO_TRAINING_CONFIG

    return ProducerSpec(
        route_id=DEMO_ROUTE_ID,
        builder="resting_demo",
        cohort_seed=int(DEMO_SEED),
        n_development=int(DEMO_N_ROWS),
        repeat_seed=int(DEMO_TRAINING_CONFIG.repeat_seeds[0]),
        outer_folds=int(DEMO_TRAINING_CONFIG.outer_folds),
        inner_folds=int(DEMO_TRAINING_CONFIG.inner_folds),
        heldout_seed=None,
        n_heldout=None,
        rf_n_estimators=int(DEMO_TRAINING_CONFIG.rf_n_estimators),
    )


def _basic_spec() -> ProducerSpec:
    """The AI-8 UCI-412 developer, read from its own configuration class."""
    from ai.uci412_research import Uci412ResearchModelConfig, _bound_route_and_panel

    config = Uci412ResearchModelConfig.fast()
    training = config.training_config()
    _descriptor, panel = _bound_route_and_panel()
    return ProducerSpec(
        route_id=panel.panel_id,
        builder="uci412_basic_clinical",
        cohort_seed=int(config.seed),
        n_development=int(config.n_development),
        repeat_seed=int(training.repeat_seeds[0]),
        outer_folds=int(training.outer_folds),
        inner_folds=int(training.inner_folds),
        # The held-out cohort is generated from its own seed, not sliced.
        heldout_seed=int(config.seed) + 1,
        n_heldout=int(config.n_test),
        rf_n_estimators=int(training.rf_n_estimators),
    )


def producer_spec(route_id: str) -> ProducerSpec:
    """Return the registered producer spec for a route."""
    specs = {spec.route_id: spec for spec in (_resting_spec(), _basic_spec())}
    if route_id not in specs:
        raise KeyError(f"no registered producer for route {route_id!r}")
    return specs[route_id]


def provenance_basis() -> dict[str, str]:
    """Where each producer's configuration is read from, for the manifest."""
    return {
        "resting_demo": (
            "ai.research_demo: DEMO_SEED, DEMO_N_ROWS, DEMO_ROUTE_ID, "
            "DEMO_TRAINING_CONFIG"
        ),
        "uci412_basic_clinical": (
            "ai.uci412_research: Uci412ResearchModelConfig.fast().seed/"
            "n_development/n_test and .training_config()"
        ),
        "split_arithmetic": "ai.training: repeat+1000*fold+10*family, +90000, +333, +4242",
    }


# --------------------------------------------------------------------------- #
# Cohort materialisation and training-boundary identity                        #
# --------------------------------------------------------------------------- #


def build_cohort(route_id: str) -> tuple[list[Any], list[int]]:
    """Materialise the producer's ordered development cohort, unvalidated."""
    spec = producer_spec(route_id)
    if spec.builder == "resting_demo":
        from ai.research_demo import _cohort

        records, labels = _cohort()
        return list(records), [int(v) for v in labels]
    from ai.uci412_research import build_synthetic_uci412_basic_clinical_cohort

    records, labels = build_synthetic_uci412_basic_clinical_cohort(
        spec.n_development, seed=spec.cohort_seed
    )
    return list(records), [int(v) for v in labels]


@dataclass(frozen=True)
class TrainingBoundary:
    """The validated, ordered feature/target matrix handed to the training run."""

    route_id: str
    X: np.ndarray
    y: np.ndarray
    feature_names: tuple[str, ...]

    @property
    def n_rows(self) -> int:
        return int(self.X.shape[0])

    @property
    def n_features(self) -> int:
        return int(self.X.shape[1])

    @property
    def n_positive(self) -> int:
        return int(self.y.sum())

    def input_sha256(self) -> str:
        """Digest over every ordered predictor value and every target value.

        Exact binary64 values are carried by ``float.hex()`` so the digest is
        platform-independent, and the ordered feature names are included so a
        column permutation cannot collide.
        """
        payload = {
            "route_id": self.route_id,
            "ordered_feature_names": list(self.feature_names),
            "n_rows": self.n_rows,
            "n_features": self.n_features,
            "n_positive": self.n_positive,
            "X_hex": [float(v).hex() for v in np.asarray(self.X, dtype=np.float64).ravel()],
            "y": [int(v) for v in np.asarray(self.y, dtype=np.int64).ravel()],
        }
        return _sha256(_canonical_bytes(payload))

    def target_sha256(self) -> str:
        """Digest over the target vector alone, for a distinct OOF target identity."""
        return _sha256(
            _canonical_bytes(
                {"route_id": self.route_id, "y": [int(v) for v in self.y.tolist()]}
            )
        )


def training_boundary(route_id: str) -> TrainingBoundary:
    """Capture the identity the training run actually consumed.

    The producer's builder supplies the records; the project's own
    ``validate_cohort_records`` performs the arrayification and the ordered field
    check. That is the exact boundary at which the training run receives ``(X, y)``.
    """
    from ai.panels import REGISTERED_PANELS
    from ai.training import validate_cohort_records

    records, labels = build_cohort(route_id)
    panel = REGISTERED_PANELS[route_id]
    X, y, _ = validate_cohort_records(records, labels, panel)
    return TrainingBoundary(
        route_id=route_id,
        X=np.asarray(X, dtype=np.float64),
        y=np.asarray(y, dtype=np.int64),
        feature_names=tuple(panel.feature_names),
    )


# --------------------------------------------------------------------------- #
# Actual split assignments consumed by the training run                        #
# --------------------------------------------------------------------------- #


def _split_folds(y: np.ndarray, n_splits: int, seed: int) -> list[dict[str, Any]]:
    from sklearn.model_selection import StratifiedKFold

    splitter = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=int(seed))
    folds = []
    for fold_index, (train_idx, test_idx) in enumerate(
        splitter.split(np.zeros(len(y)), y), start=1
    ):
        folds.append(
            {
                "fold_index": int(fold_index),
                "train_indices": [int(i) for i in train_idx],
                "validation_indices": [int(i) for i in test_idx],
            }
        )
    return folds


def outer_assignments(route_id: str) -> dict[str, Any]:
    """Actual outer-fold train/validation assignments for the training run."""
    spec = producer_spec(route_id)
    boundary = training_boundary(route_id)
    folds = _split_folds(boundary.y, spec.outer_folds, spec.repeat_seed)
    for fold in folds:
        fold["repeat_seed"] = int(spec.repeat_seed)
    return {
        "kind": "outer_fold_assignments",
        "n_rows": boundary.n_rows,
        "n_splits": int(spec.outer_folds),
        "seed": int(spec.repeat_seed),
        "folds": folds,
        "assignment_sha256": _sha256(_canonical_bytes(folds)),
    }


def calibration_oof_assignments(route_id: str) -> dict[str, Any]:
    """Actual **final-development OOF calibration** fold assignments.

    This is the splitter at ``ai/training.py`` using ``full_cv_seed + 333``. It is
    a different partition from the outer folds and is now identified separately,
    because an outer-fold digest is not evidence about the calibration split.
    """
    spec = producer_spec(route_id)
    boundary = training_boundary(route_id)
    folds = _split_folds(boundary.y, spec.outer_folds, spec.calibration_seed)
    for fold in folds:
        fold["calibration_seed"] = int(spec.calibration_seed)
    return {
        "kind": "final_development_oof_calibration_assignments",
        "n_rows": boundary.n_rows,
        "n_splits": int(spec.outer_folds),
        "seed": int(spec.calibration_seed),
        "derivation": "repeat_seed + 90000 + 333",
        "folds": folds,
        "assignment_sha256": _sha256(_canonical_bytes(folds)),
        "calibration_input_sha256": boundary.input_sha256(),
        "calibration_target_sha256": boundary.target_sha256(),
    }


def inner_selection_identity(route_id: str) -> dict[str, Any]:
    """Inner-selection configuration and the actual inner-assignment identities."""
    spec = producer_spec(route_id)
    boundary = training_boundary(route_id)
    from ai.training import CANDIDATE_FAMILIES

    per_fold: list[dict[str, Any]] = []
    for fold in _split_folds(boundary.y, spec.outer_folds, spec.repeat_seed):
        y_train = boundary.y[np.asarray(fold["train_indices"], dtype=np.int64)]
        families: dict[str, Any] = {}
        for offset, family in enumerate(sorted(CANDIDATE_FAMILIES), start=1):
            seed = spec.inner_seed(fold["fold_index"], offset)
            inner = _split_folds(y_train, spec.inner_folds, seed)
            families[family] = {
                "family_offset": int(offset),
                "inner_seed": int(seed),
                "assignment_sha256": _sha256(_canonical_bytes(inner)),
            }
        per_fold.append(
            {
                "fold_index": int(fold["fold_index"]),
                "n_train_rows": int(len(fold["train_indices"])),
                "families": families,
            }
        )
    return {
        "kind": "inner_selection_assignments",
        "n_splits": int(spec.inner_folds),
        "derivation": "repeat_seed + 1000*fold + 10*family_offset",
        "folds": per_fold,
        "identity_sha256": _sha256(_canonical_bytes(per_fold)),
    }


def heldout_cohort_identity(route_id: str) -> dict[str, Any]:
    """The held-out cohort, which is **separately generated**, never sliced.

    Reporting contiguous indices after the development rows would be a fabricated
    shared-array split; the producer generates it from its own seed via
    ``build_synthetic_uci412_basic_clinical_cohort(n_test, seed=config.seed + 1)``.
    """
    spec = producer_spec(route_id)
    if spec.heldout_seed is None:
        return {
            "kind": "no_separate_heldout_cohort",
            "present": False,
            "note": (
                "this producer trains on a single development cohort; there is no "
                "second array and therefore no shared-array split to report"
            ),
        }
    from ai.uci412_research import (
        build_synthetic_uci412_basic_clinical_cohort,
        validate_uci412_synthetic_cohort,
    )

    records, labels = build_synthetic_uci412_basic_clinical_cohort(
        int(spec.n_heldout), seed=int(spec.heldout_seed)
    )
    X, y, _ = validate_uci412_synthetic_cohort(list(records), list(labels))
    payload = {
        "route_id": route_id,
        "seed": int(spec.heldout_seed),
        "n_rows": int(X.shape[0]),
        "n_positive": int(np.asarray(y).sum()),
        "X_hex": [
            float(v).hex() for v in np.asarray(X, dtype=np.float64).ravel()
        ],
        "y": [int(v) for v in np.asarray(y, dtype=np.int64).ravel()],
    }
    return {
        "kind": "independently_generated_heldout_cohort",
        "present": True,
        "seed": int(spec.heldout_seed),
        "n_rows": int(X.shape[0]),
        "shared_array_with_development": False,
        "cohort_sha256": _sha256(_canonical_bytes(payload)),
    }


def full_lineage(route_id: str) -> dict[str, Any]:
    """Every recoverable producer-lineage fact for one route, digest-addressed."""
    spec = producer_spec(route_id)
    boundary = training_boundary(route_id)
    return {
        "producer": spec.as_dict(),
        "provenance_basis": provenance_basis(),
        "training_boundary": {
            "n_rows": boundary.n_rows,
            "n_features": boundary.n_features,
            "n_positive": boundary.n_positive,
            "ordered_feature_names": list(boundary.feature_names),
            "training_input_sha256": boundary.input_sha256(),
            "target_sha256": boundary.target_sha256(),
        },
        "outer_folds": outer_assignments(route_id),
        "calibration_oof": calibration_oof_assignments(route_id),
        "inner_selection": inner_selection_identity(route_id),
        "heldout": heldout_cohort_identity(route_id),
    }


def estimator_lineage_proof(route_id: str, archive: Mapping[str, Any]) -> dict[str, Any]:
    """Independently refit from the producer cohort and compare to the archive.

    This is the strongest available lineage evidence: it does not read the
    archive's own claim, it re-runs the producer's final fit from the producer's
    cohort and the producer's own seed arithmetic, then compares the resulting
    parameters against the archived ones.

    The archive cannot make this agree by construction, because the refit depends
    on the cohort seed and the final-fit seed, both derived from producer sources.
    """
    from ai.panels import REGISTERED_PANELS
    from ai.preprocessing import FoldSafeClinicalPreprocessor

    spec = producer_spec(route_id)
    boundary = training_boundary(route_id)
    panel = REGISTERED_PANELS[route_id]

    refit_preprocessor = FoldSafeClinicalPreprocessor.fit(boundary.X, panel)
    archived_preprocessor = dict(archive["preprocessing"])
    preprocessing_exact = (
        refit_preprocessor.to_json_dict() == archived_preprocessor
    )

    family = str(archive["model"]["family"])
    params = dict(archive["training_identity"]["selected_hyperparameters"])
    Z = refit_preprocessor.transform(boundary.X)
    final_seed = spec.full_cv_seed + 9999
    representation = dict(archive["model"]["representation"])
    result: dict[str, Any] = {
        "route_id": route_id,
        "preprocessing_exact": preprocessing_exact,
        "final_fit_seed": int(final_seed),
        "final_fit_seed_derivation": "repeat_seed + 90000 + 9999",
        "model_family": family,
        "selected_hyperparameters": params,
    }

    if family == "l2_logistic_regression":
        from sklearn.linear_model import LogisticRegression

        estimator = LogisticRegression(
            penalty="l2",
            C=float(params["C"]),
            solver="lbfgs",
            max_iter=1000,
            random_state=int(final_seed),
        )
        estimator.fit(Z, boundary.y)
        archived_coef = np.asarray(representation["coef"], dtype=np.float64)
        archived_intercept = float(representation["intercept"])
        coef_max_delta = float(np.max(np.abs(archived_coef - estimator.coef_[0])))
        intercept_delta = float(abs(archived_intercept - float(estimator.intercept_[0])))
        result.update(
            {
                "coefficient_max_abs_delta": coef_max_delta,
                "intercept_abs_delta": intercept_delta,
                "coefficients_exact": coef_max_delta == 0.0 and intercept_delta == 0.0,
            }
        )
    elif family == "constrained_random_forest":
        from sklearn.ensemble import RandomForestClassifier

        estimator = RandomForestClassifier(
            n_estimators=int(spec.rf_n_estimators),
            max_depth=int(params["max_depth"]),
            min_samples_leaf=int(params["min_samples_leaf"]),
            max_features="sqrt",
            class_weight=None,
            random_state=int(final_seed),
            n_jobs=1,
        )
        estimator.fit(Z, boundary.y)
        trees = representation["trees"]
        mismatched = 0
        first_delta = 0.0
        for index, spec_tree in enumerate(trees):
            refit_tree = estimator.estimators_[index].tree_
            archived_values = np.asarray(spec_tree["value"], dtype=np.float64).ravel()
            if refit_tree.value.ravel().shape != archived_values.shape:
                mismatched += 1
                continue
            delta = float(np.max(np.abs(refit_tree.value.ravel() - archived_values)))
            first_delta = max(first_delta, delta) if index == 0 else first_delta
            if delta != 0.0:
                mismatched += 1
        result.update(
            {
                "n_trees_compared": len(trees),
                "trees_mismatched": int(mismatched),
                "first_tree_value_max_abs_delta": float(first_delta),
                "trees_exact": mismatched == 0,
            }
        )
    else:
        result["note"] = "no refit proof implemented for this model family"

    result["lineage_established"] = bool(preprocessing_exact) and bool(
        result.get("coefficients_exact") is True or result.get("trees_exact") is True
    )
    return result


def lineage_sha256(route_id: str) -> str:
    """Digest of the complete lineage record -- the manifest's lineage identity."""
    return _sha256(_canonical_bytes(full_lineage(route_id)))


__all__: Final[tuple[str, ...]] = (
    "ProducerSpec",
    "TrainingBoundary",
    "build_cohort",
    "calibration_oof_assignments",
    "full_lineage",
    "heldout_cohort_identity",
    "inner_selection_identity",
    "estimator_lineage_proof",
    "lineage_sha256",
    "outer_assignments",
    "producer_spec",
    "provenance_basis",
    "training_boundary",
)
