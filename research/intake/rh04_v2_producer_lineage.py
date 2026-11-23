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

    def dummy_calibration_seed(self, fold_index: int) -> int:
        """Inner-CV seed for the per-outer-fold dummy calibrator.

        ``ai/training.py`` derives it as ``repeat_seed + 1000*fold_index + 1``.
        The literal ``+ 1`` is the *lowest* family offset slot, which is why this
        is recorded separately: a family enumeration that does not preserve the
        declared order would silently reassign this slot.
        """
        return int(self.repeat_seed) + 1000 * int(fold_index) + 1

    def full_selection_seed(self, family_offset: int) -> int:
        """Full-development-cohort inner-selection seed (``full_cv + 10*offset``)."""
        return self.full_cv_seed + 10 * int(family_offset)

    def calibration_fold_seed(self, fold_index: int) -> int:
        """Per-fold estimator seed inside the final development-OOF calibrator."""
        return self.calibration_seed - 333 + 1000 * int(fold_index)

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
    """The **final-development OOF calibration partition** (``full_cv + 333``).

    This is a *partition* identity only: it says which rows were held out in which
    fold. It deliberately says nothing about the calibration **input**, which is
    the out-of-fold probability vector produced by that partition, not the
    development design matrix. See :func:`calibration_input_identity`.
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
        # The development-design-matrix digests are recorded under an unambiguous
        # name. They are *not* the calibrator's input; see calibration_input_identity.
        "development_input_sha256": boundary.input_sha256(),
        "development_target_sha256": boundary.target_sha256(),
    }


def _capture_producer_calibration_fit(route_id: str) -> dict[str, Any]:
    """Run the registered producer and capture the inputs its calibrator received.

    This does **not** reconstruct the calibrator's input from the development
    matrix. It drives the real registered producer and intercepts
    ``OofLogisticCalibrator.fit_from_oof`` for the single
    ``FULL_DEVELOPMENT_OOF_FINAL`` fit, so the captured arrays are literally the
    ordered OOF vector the producer fitted.

    The raw vectors are returned to the caller for digesting and are never
    written to disk or committed: only SHA-256 digests and permitted scalar
    provenance leave this function.
    """
    from ai.calibration import OofLogisticCalibrator

    captured: list[dict[str, Any]] = []
    original = OofLogisticCalibrator.fit_from_oof.__func__

    def _intercept(cls, y_oof, p_oof_raw, **kwargs):  # type: ignore[no-untyped-def]
        instance = original(cls, y_oof, p_oof_raw, **kwargs)
        if kwargs.get("fit_scope") == "FULL_DEVELOPMENT_OOF_FINAL":
            raw_logits = kwargs.get("raw_logits")
            captured.append(
                {
                    "y": np.asarray(y_oof, dtype=np.float64),
                    "p": np.asarray(p_oof_raw, dtype=np.float64),
                    "logits": (
                        None
                        if raw_logits is None
                        else np.asarray(raw_logits, dtype=np.float64)
                    ),
                    "instance": instance,
                }
            )
        return instance

    OofLogisticCalibrator.fit_from_oof = classmethod(_intercept)
    try:
        _run_registered_producer(route_id)
    finally:
        OofLogisticCalibrator.fit_from_oof = classmethod(original)

    if len(captured) != 1:
        raise RuntimeError(
            f"{route_id}: expected exactly one FULL_DEVELOPMENT_OOF_FINAL "
            f"calibrator fit from the producer, observed {len(captured)}"
        )
    return captured[0]


def _run_registered_producer(route_id: str) -> None:
    """Invoke the registered synthetic producer for a route; no parallel trainer."""
    if route_id == "da_a1_basic_clinical_v1":
        from ai.uci412_research import (
            Uci412ResearchModelConfig,
            build_uci412_synthetic_research_model,
        )

        build_uci412_synthetic_research_model(Uci412ResearchModelConfig.fast())
        return
    if route_id == "da_a2_resting_v1":
        import tempfile
        from pathlib import Path

        from ai.research_demo import _build_demo_bundle

        with tempfile.TemporaryDirectory() as work_root:
            _build_demo_bundle(Path(work_root))
        return
    raise KeyError(f"no registered producer runner for route {route_id!r}")


def _ordered_digest(values: np.ndarray, *, route_id: str, label: str) -> str:
    """Digest an ordered float vector by exact binary64 representation."""
    payload = {
        "route_id": route_id,
        "label": label,
        "n": int(values.size),
        "hex": [float(v).hex() for v in values.tolist()],
    }
    return _sha256(_canonical_bytes(payload))


def calibration_input_identity(route_id: str) -> dict[str, Any]:
    """The **actual** input identity of the fitted OOF calibrator.

    Three distinct identities are kept apart on purpose:

    ``development_input_sha256``
        The ordered development design matrix the training run consumed.
    ``partition.assignment_sha256``
        Which rows the ``full_cv_seed + 333`` splitter held out in which fold.
    ``oof_input_sha256`` (this function)
        The ordered out-of-fold probability vector that was actually fitted,
        plus the raw-logit vector where the input link carries exact log-odds.

    Hashing the development matrix and calling it ``calibration_input_sha256`` was
    wrong: a perfectly valid calibrator fit can consume a different vector from
    the same design matrix, and an attacker can change one without the other.
    """
    captured = _capture_producer_calibration_fit(route_id)
    instance = captured["instance"]
    p = np.asarray(captured["p"], dtype=np.float64)
    y = np.asarray(captured["y"], dtype=np.float64)
    logits = captured["logits"]

    return {
        "kind": "actual_oof_calibrator_input",
        "route_id": route_id,
        "n_oof_samples": int(p.size),
        "input_link": str(instance.input_link),
        "fit_scope": str(instance.fit_scope),
        "model_family": str(instance.model_family),
        "oof_input_sha256": _ordered_digest(
            p, route_id=route_id, label="oof_probability"
        ),
        "oof_target_sha256": _ordered_digest(
            y, route_id=route_id, label="oof_target"
        ),
        "oof_raw_logit_sha256": (
            None
            if logits is None
            else _ordered_digest(logits, route_id=route_id, label="oof_raw_logit")
        ),
        "fitted_criterion": {
            "objective": "mean_log_loss_plus_l2_anchor_around_slope_1",
            "l2_anchor": 1e-3,
            "solver": str(instance.solver),
            "bounds": {"intercept": [-15.0, 15.0], "slope": [0.01, 15.0]},
        },
        "fitted_parameters": {
            "intercept": float(instance.intercept),
            "slope": float(instance.slope),
            "status": str(instance.status),
        },
        "fit_statistics": {
            "development_prevalence": float(instance.development_prevalence),
            "oof_brier_before": float(instance.oof_brier_before),
            "oof_brier_after": float(instance.oof_brier_after),
        },
    }


def calibration_input_sha256(route_id: str) -> str:
    """Digest of the actual calibrator-input identity record."""
    return _sha256(_canonical_bytes(calibration_input_identity(route_id)))


def candidate_families_in_producer_order() -> tuple[str, ...]:
    """``CANDIDATE_FAMILIES`` in the order the producer actually enumerates it.

    ``ai/training.py`` builds every family offset from
    ``enumerate(CANDIDATE_FAMILIES, start=1)``. The declared order is therefore
    semantically load-bearing: it determines which inner-CV seed each family
    receives. Sorting the tuple here would swap the offsets and describe a
    training run that never happened. This function exists so that the ordering
    choice is made once, visibly, and is never re-derived by a caller.
    """
    from ai.training import CANDIDATE_FAMILIES

    return tuple(CANDIDATE_FAMILIES)


def inner_selection_identity(route_id: str) -> dict[str, Any]:
    """Inner-selection configuration and the actual inner-assignment identities.

    Family offsets follow the producer's declared ``CANDIDATE_FAMILIES`` order
    (Logistic Regression first, Random Forest second). The dummy calibrator's
    inner split uses offset slot ``+1`` and the full-development selection uses
    ``full_cv + 10*offset``; both are recorded here because both are assigned
    from the same ordering.
    """
    spec = producer_spec(route_id)
    boundary = training_boundary(route_id)
    families_in_order = candidate_families_in_producer_order()

    per_fold: list[dict[str, Any]] = []
    for fold in _split_folds(boundary.y, spec.outer_folds, spec.repeat_seed):
        y_train = boundary.y[np.asarray(fold["train_indices"], dtype=np.int64)]
        families: dict[str, Any] = {}
        for offset, family in enumerate(families_in_order, start=1):
            seed = spec.inner_seed(fold["fold_index"], offset)
            inner = _split_folds(y_train, spec.inner_folds, seed)
            families[family] = {
                "family_offset": int(offset),
                "inner_seed": int(seed),
                "assignment_sha256": _sha256(_canonical_bytes(inner)),
            }
        dummy_seed = spec.dummy_calibration_seed(fold["fold_index"])
        dummy_inner = _split_folds(y_train, spec.inner_folds, dummy_seed)
        per_fold.append(
            {
                "fold_index": int(fold["fold_index"]),
                "n_train_rows": int(len(fold["train_indices"])),
                "families": families,
                "dummy_calibration": {
                    "inner_seed": int(dummy_seed),
                    "derivation": "repeat_seed + 1000*fold + 1",
                    "assignment_sha256": _sha256(_canonical_bytes(dummy_inner)),
                    "fit_scope": "INNER_CV_FOLD_CONTAINED",
                },
            }
        )

    full_selection = {
        family: {
            "family_offset": int(offset),
            "inner_seed": int(spec.full_selection_seed(offset)),
        }
        for offset, family in enumerate(families_in_order, start=1)
    }

    return {
        "kind": "inner_selection_assignments",
        "n_splits": int(spec.inner_folds),
        "family_order": list(families_in_order),
        "family_order_basis": "ai.training.CANDIDATE_FAMILIES, declared order",
        "derivation": "repeat_seed + 1000*fold + 10*family_offset",
        "folds": per_fold,
        "full_development_selection": full_selection,
        "full_development_derivation": "full_cv_seed + 10*family_offset",
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


def selection_reproduction(route_id: str) -> dict[str, Any]:
    """Independently re-run the producer's own selection step and report it.

    Two different claims are separated here, because conflating them would
    overstate the evidence:

    **Conditional reproduction** (``estimator_lineage_proof``)
        Given the archived selected hyperparameters, the archived subset of the
        selection problem, refitting reproduces the archived parameters exactly.
        It cannot detect that a *different* candidate would have won.
    **Independent reproduction** (this function)
        Re-running the producer's selection from the producer cohort, with the
        producer's own seed schedule and its own
        ``_select_best_params_and_inner_oof`` / ``choose_model_family``, yields the
        same family with the same hyperparameters. This *can* detect a selection
        that would have chosen otherwise.

    Only the second is evidence that the archive records the winner of the real
    selection procedure. This function therefore reports which it achieves.
    """
    import ai.training as T

    spec = producer_spec(route_id)
    boundary = training_boundary(route_id)
    from ai.panels import REGISTERED_PANELS
    from ai.uci412_research import Uci412ResearchModelConfig

    panel = REGISTERED_PANELS[route_id]
    if route_id == "da_a1_basic_clinical_v1":
        config = Uci412ResearchModelConfig.fast().training_config()
    else:
        from ai.research_demo import DEMO_TRAINING_CONFIG

        config = DEMO_TRAINING_CONFIG

    families = candidate_families_in_producer_order()
    aucs: dict[str, float] = {}
    params: dict[str, dict[str, Any]] = {}
    for offset, family in enumerate(families, start=1):
        best, auc_val, _, _ = T._select_best_params_and_inner_oof(
            boundary.X,
            boundary.y,
            family=family,
            panel=panel,
            config=config,
            inner_seed=spec.full_selection_seed(offset),
        )
        params[family] = dict(best)
        aucs[family] = float(auc_val)

    selected = T.choose_model_family(aucs, tolerance=config.auc_simplicity_tolerance)
    return {
        "kind": "independent_selection_reproduction",
        "route_id": route_id,
        "selection_scope": "FULL_DEVELOPMENT_COHORT",
        "family_order": list(families),
        "simplicity_tolerance": float(config.auc_simplicity_tolerance),
        "inner_cv_roc_auc": {k: float(v) for k, v in aucs.items()},
        "best_params": params,
        "selected_family": str(selected),
        "selected_hyperparameters": params[str(selected)],
    }


#: Every archived per-tree array, with the exact dtype class sklearn uses.
#: ``value`` alone is a leaf-statistics comparison; it can match while the tree
#: topology, the split thresholds or the missing-value routing differ, which is a
#: different function even when every leaf happens to hold the same numbers.
#: ``(archived key, fitted-tree attribute or ``nodes`` field, comparison kind)``.
#: ``sklearn.tree._tree.Tree`` exposes ``children_left``/``children_right`` while
#: the serialized representation calls them ``left``/``right``; the archived keys
#: are the contract, the attribute names are an implementation detail.
_TREE_ARRAYS: Final[tuple[tuple[str, str, str], ...]] = (
    ("left", "children_left", "int"),
    ("right", "children_right", "int"),
    ("feature", "feature", "int"),
    ("threshold", "threshold", "float"),
    ("impurity", "impurity", "float"),
    ("n_node_samples", "n_node_samples", "int"),
    ("weighted_n_node_samples", "weighted_n_node_samples", "float"),
    ("missing_go_to_left", "missing_go_to_left", "int"),
    ("value", "value", "float"),
)

_TREE_SCALARS: Final[tuple[tuple[str, str], ...]] = (
    ("max_depth", "int"),
    ("n_features", "int"),
    ("n_classes", "int"),
    ("n_outputs", "int"),
)


def _compare_forest_structure(
    estimator: Any, archived_trees: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Compare complete tree structure, not just leaf values.

    Returns exact-equality verdicts per array kind so the report can state which
    structural aspect was verified, rather than collapsing everything into one
    boolean that could hide a topology-only mismatch.
    """
    n_est = len(estimator.estimators_)
    if n_est != len(archived_trees):
        return {
            "trees_exact": False,
            "tree_count": {"archived": len(archived_trees), "refit": int(n_est)},
            "structure_exact": False,
            "reason": "tree_count_mismatch",
        }

    per_array_exact: dict[str, bool] = {key: True for key, _, _ in _TREE_ARRAYS}
    per_scalar_exact: dict[str, bool] = {name: True for name, _ in _TREE_SCALARS}
    node_count_mismatch: list[int] = []
    max_float_delta = 0.0

    for index, archived_tree in enumerate(archived_trees):
        fitted = estimator.estimators_[index].tree_
        for key, attribute, kind in _TREE_ARRAYS:
            if key not in archived_tree:
                per_array_exact[key] = False
                continue
            want = np.asarray(archived_tree[key], dtype=np.float64).ravel()
            got = np.asarray(
                getattr(fitted, attribute), dtype=np.float64
            ).ravel()
            if want.shape != got.shape:
                per_array_exact[key] = False
                if key == "left" and index not in node_count_mismatch:
                    node_count_mismatch.append(index)
                continue
            if kind == "int":
                identical = np.array_equal(
                    want.astype(np.int64), got.astype(np.int64)
                )
            else:
                delta = np.abs(want - got)
                max_float_delta = max(max_float_delta, float(delta.max(initial=0.0)))
                identical = bool(np.all(delta == 0.0))
            if not identical:
                per_array_exact[key] = False
        for name, kind in _TREE_SCALARS:
            if name not in archived_tree:
                per_scalar_exact[name] = False
                continue
            want_v = int(archived_tree[name])
            got_attr = getattr(fitted, name, None)
            if got_attr is None:
                per_scalar_exact[name] = False
                continue
            # ``n_classes`` is a length-1 ndarray while ``max_depth``,
            # ``n_features`` and ``n_outputs`` are plain ints. Only a scalar or a
            # single-element array has an unambiguous integer value; anything
            # longer is not the quantity being compared and must not be coerced.
            arr = np.asarray(got_attr)
            if arr.size != 1:
                per_scalar_exact[name] = False
                continue
            got_v = int(arr.reshape(-1)[0])
            if want_v != got_v:
                per_scalar_exact[name] = False

    structure_exact = all(per_array_exact.values()) and all(
        per_scalar_exact.values()
    )
    return {
        "n_trees_compared": len(archived_trees),
        "tree_count": {"archived": len(archived_trees), "refit": int(n_est)},
        "tree_count_exact": True,
        "per_array_exact": per_array_exact,
        "per_scalar_exact": per_scalar_exact,
        "node_count_mismatch_trees": node_count_mismatch,
        "max_float_delta": float(max_float_delta),
        "structure_exact": bool(structure_exact),
        "trees_exact": bool(structure_exact),
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
        structure = _compare_forest_structure(estimator, trees)
        result.update(structure)
        result["rf_n_estimators"] = int(spec.rf_n_estimators)
        result["class_order"] = [int(v) for v in estimator.classes_.tolist()]
        result["n_features_in"] = int(estimator.n_features_in_)
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
