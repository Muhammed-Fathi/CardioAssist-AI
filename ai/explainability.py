"""Genuine, model-faithful Grouped Interventional SHAP engine for Track A research.

Score & scale alignment contract:
- Every explanation explicitly declares ``explained_quantity``, ``scale``,
  ``explains_calibrated_score_directly``, and
  ``additive_on_calibrated_probability`` (which is ``False`` for both log-odds
  LinearSHAP and raw-probability TreeSHAP so raw or log-odds attributions are
  NEVER misdescribed as additive decompositions of calibrated probability).
- For ``l2_logistic_regression``:
  - When paired with an ``exact_raw_log_odds`` ``OofLogisticCalibrator``
    (``eta_cal = a + b * eta_raw``), Interventional LinearSHAP is derived in
    exact closed form on ``calibrated_log_odds`` via Shapley linearity:
    ``phi_0_cal = a + b * phi_0_raw`` and ``phi_j_cal = b * phi_j_raw``.
    Thus ``phi_0_cal + sum_j phi_j_cal(x) == logit(calibrated_research_score)``
    and ``expit(phi_0_cal + sum_j phi_j_cal(x)) == calibrated_research_score``
    to machine precision, while remaining additive in *log-odds*, not probability.
  - When called without a calibrator, Interventional LinearSHAP explains
    ``raw_model_log_odds`` (``logit(raw_model_score)``).
- For ``constrained_random_forest``:
  - Exact polynomial-time Grouped Interventional TreeSHAP explains
    ``raw_model_score`` on ``raw_model_probability`` scale ONLY. Because
    post-hoc logistic calibration is nonlinear across averaged tree probabilities,
    raw-probability TreeSHAP is NEVER relabeled as calibrated-probability SHAP.
- For ``prevalence_dummy``:
  - Constant predictor with identically zero attributions on ``raw_model_score``.

Privacy contract for ``ShapBackgroundReference``:
- ``shap_background.json`` stores encoded training-cohort feature rows, which can
  be inverted back to raw clinical feature values using ``preprocessing.json``
  statistics. Whenever real patient data are involved, ``shap_background.json``
  is a sensitive patient-data derivative that must never be committed, uploaded,
  shared publicly, or loaded while Gate PT (``P-3``) is closed.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Callable, Final, Mapping, Sequence

import numpy as np
from scipy.special import expit
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier

from ai.calibration import OofLogisticCalibrator
from ai.errors import ExplainabilityIntegrityError
from ai.panels import ResearchPanelContract
from ai.preprocessing import FoldSafeClinicalPreprocessor

SHAP_BACKGROUND_SCHEMA_VERSION: Final[str] = "cardioassist.ai.shap_background/v1"
ADDITIVITY_TOLERANCE: Final[float] = 1e-9

METHOD_BY_MODEL_FAMILY: Final[Mapping[str, str]] = {
    "l2_logistic_regression": "linear_shap_interventional",
    "constrained_random_forest": "tree_shap_interventional",
    "prevalence_dummy": "constant_baseline_zero_shap",
}


@dataclass(frozen=True, slots=True)
class ShapBackgroundReference:
    """Serialized encoded background distribution for interventional Shapley values.

    Security & privacy note:
    ``background_matrix`` holds encoded training rows (z-scored continuous columns
    and reference-coded categorical/missingness indicators). Combined with
    ``preprocessing.json`` means and standard deviations, these rows are
    invertible to individual training feature profiles. Real-patient backgrounds
    are classified as ``SENSITIVE_REAL_PATIENT_DERIVED_RESTRICTED_LOCAL_ONLY``
    and blocked while Gate PT (``P-3``) is closed.
    """

    panel_id: str
    panel_contract_sha256: str
    encoded_feature_names: tuple[str, ...]
    background_matrix: np.ndarray  # shape (N_bg, P), float64
    synthetic_only: bool = True

    @property
    def sensitivity_classification(self) -> str:
        return (
            "SYNTHETIC_NON_PATIENT_DERIVATIVE"
            if self.synthetic_only
            else "SENSITIVE_REAL_PATIENT_DERIVED_RESTRICTED_LOCAL_ONLY"
        )

    @classmethod
    def from_training_encoded(
        cls,
        Z_train: np.ndarray,
        y_train: np.ndarray,
        preprocessor: FoldSafeClinicalPreprocessor,
        *,
        max_samples: int = 64,
        seed: int = 20261025,
        synthetic_only: bool = True,
    ) -> "ShapBackgroundReference":
        if not synthetic_only:
            raise ExplainabilityIntegrityError(
                "real_patient_shap_background_blocked_gate_pt_closed",
                "Gate PT (P-3) remains closed; persisting real-patient SHAP background rows is blocked.",
            )
        Z = np.asarray(Z_train, dtype=np.float64)
        y = np.asarray(y_train, dtype=np.int64)
        if Z.ndim != 2 or Z.shape[1] != preprocessor.n_encoded_features:
            raise ExplainabilityIntegrityError(
                "invalid_background_shape",
                "Background matrix column count does not match fitted preprocessor.",
            )
        if Z.shape[0] == 0 or Z.shape[0] != y.shape[0]:
            raise ExplainabilityIntegrityError(
                "invalid_background_rows",
                "Background matrix and label vector must be non-empty and aligned.",
            )

        if Z.shape[0] <= max_samples:
            selected = Z.copy()
        else:
            rng = np.random.default_rng(seed)
            pos_idx = np.flatnonzero(y == 1)
            neg_idx = np.flatnonzero(y == 0)
            n_pos = max(
                1, min(len(pos_idx), round(max_samples * len(pos_idx) / len(y)))
            )
            n_neg = max(1, min(len(neg_idx), max_samples - n_pos))
            chosen_pos = rng.choice(pos_idx, size=n_pos, replace=False)
            chosen_neg = rng.choice(neg_idx, size=n_neg, replace=False)
            chosen = np.sort(np.concatenate([chosen_pos, chosen_neg]))
            selected = Z[chosen].copy()

        return cls(
            panel_id=preprocessor.panel_id,
            panel_contract_sha256=preprocessor.panel_contract_sha256,
            encoded_feature_names=preprocessor.encoded_feature_names,
            background_matrix=selected,
            synthetic_only=bool(synthetic_only),
        )

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SHAP_BACKGROUND_SCHEMA_VERSION,
            "panel_id": self.panel_id,
            "panel_contract_sha256": self.panel_contract_sha256,
            "n_background_rows": int(self.background_matrix.shape[0]),
            "encoded_feature_names": list(self.encoded_feature_names),
            "privacy": {
                "synthetic_only": bool(self.synthetic_only),
                "contains_encoded_training_projections": True,
                "reconstructible_with_preprocessor_stats": True,
                "sensitivity_classification": self.sensitivity_classification,
                "commit_or_public_upload_prohibited": True,
                "untrusted_loading_prohibited": True,
            },
            "background_matrix": [
                [float(v) for v in row] for row in self.background_matrix.tolist()
            ],
        }

    def to_canonical_json_bytes(self) -> bytes:
        return (
            json.dumps(
                self.to_json_dict(),
                indent=2,
                sort_keys=True,
                ensure_ascii=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")

    @property
    def state_sha256(self) -> str:
        return hashlib.sha256(self.to_canonical_json_bytes()).hexdigest()

    @classmethod
    def from_json_dict(
        cls,
        payload: Mapping[str, Any],
        *,
        preprocessor: FoldSafeClinicalPreprocessor,
        require_synthetic: bool = True,
    ) -> "ShapBackgroundReference":
        if not isinstance(payload, Mapping) or (
            payload.get("schema_version") != SHAP_BACKGROUND_SCHEMA_VERSION
        ):
            raise ExplainabilityIntegrityError(
                "invalid_background_schema",
                "Unsupported or malformed SHAP background JSON schema.",
            )
        if (
            payload.get("panel_id") != preprocessor.panel_id
            or payload.get("panel_contract_sha256") != preprocessor.panel_contract_sha256
            or tuple(payload.get("encoded_feature_names", ()))
            != preprocessor.encoded_feature_names
        ):
            raise ExplainabilityIntegrityError(
                "background_contract_mismatch",
                "SHAP background reference does not match fitted preprocessor.",
            )
        privacy = payload.get("privacy")
        if (
            not isinstance(privacy, Mapping)
            or privacy.get("contains_encoded_training_projections") is not True
            or privacy.get("reconstructible_with_preprocessor_stats") is not True
            or privacy.get("commit_or_public_upload_prohibited") is not True
            or not isinstance(privacy.get("synthetic_only"), bool)
        ):
            raise ExplainabilityIntegrityError(
                "missing_background_privacy_declaration",
                "SHAP background JSON lacks mandatory training-projection privacy declarations.",
            )
        synthetic_only = bool(privacy["synthetic_only"])
        if require_synthetic and not synthetic_only:
            raise ExplainabilityIntegrityError(
                "real_patient_shap_background_blocked_gate_pt_closed",
                "Refusing to load non-synthetic patient-derived SHAP background while Gate PT is closed.",
            )

        matrix = np.asarray(payload.get("background_matrix", []), dtype=np.float64)
        if (
            matrix.ndim != 2
            or matrix.shape[0] < 1
            or matrix.shape[1] != preprocessor.n_encoded_features
            or not np.isfinite(matrix).all()
        ):
            raise ExplainabilityIntegrityError(
                "invalid_background_matrix",
                "SHAP background matrix is empty, non-finite, or misaligned.",
            )
        return cls(
            panel_id=preprocessor.panel_id,
            panel_contract_sha256=preprocessor.panel_contract_sha256,
            encoded_feature_names=preprocessor.encoded_feature_names,
            background_matrix=matrix,
            synthetic_only=synthetic_only,
        )


@dataclass(frozen=True, slots=True)
class FeatureShapAttribution:
    """Clinical-feature-level Shapley attribution."""

    feature_name: str
    clinical_meaning: str
    status: str  # "present" | "missing_imputed"
    shap_value: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_name": self.feature_name,
            "clinical_meaning": self.clinical_meaning,
            "status": self.status,
            "shap_value": self.shap_value,
        }


@dataclass(frozen=True, slots=True)
class FaithfulShapExplanation:
    """Verified additive model-specific Shapley explanation with explicit target alignment."""

    method: str
    model_family: str
    explained_quantity: str  # "calibrated_log_odds" | "raw_model_log_odds" | "raw_model_score"
    scale: str  # "calibrated_log_odds" | "raw_log_odds" | "raw_model_probability"
    explains_calibrated_score_directly: bool
    additive_on_calibrated_probability: bool
    linked_probability_quantity: str  # "calibrated_research_score" | "raw_model_score"
    linked_probability_value: float
    score_alignment_note: str
    faithful_to_model_family: bool
    synthetic_placeholder: bool
    background_sample_count: int
    base_value: float
    target_prediction_on_scale: float
    attributions: tuple[FeatureShapAttribution, ...]
    sum_check_passed: bool
    max_abs_discrepancy: float

    def attribution_map(self) -> dict[str, float]:
        return {item.feature_name: item.shap_value for item in self.attributions}

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "model_family": self.model_family,
            "explained_quantity": self.explained_quantity,
            "scale": self.scale,
            "explains_calibrated_score_directly": self.explains_calibrated_score_directly,
            "additive_on_calibrated_probability": self.additive_on_calibrated_probability,
            "linked_probability_quantity": self.linked_probability_quantity,
            "linked_probability_value": self.linked_probability_value,
            "score_alignment_note": self.score_alignment_note,
            "faithful_to_model_family": self.faithful_to_model_family,
            "synthetic_placeholder": self.synthetic_placeholder,
            "background_sample_count": self.background_sample_count,
            "base_value": self.base_value,
            "target_prediction_on_scale": self.target_prediction_on_scale,
            "sum_check": {
                "passed": self.sum_check_passed,
                "tolerance": ADDITIVITY_TOLERANCE,
                "max_abs_discrepancy": self.max_abs_discrepancy,
            },
            "attributions": [item.to_dict() for item in self.attributions],
        }


@dataclass(frozen=True, slots=True)
class _LeafPathSpec:
    """Single root-to-leaf path grouped by owning raw clinical feature."""

    leaf_value: float
    grouped_conditions: tuple[tuple[int, tuple[tuple[int, float, bool], ...]], ...]


def _extract_tree_leaf_paths(
    tree_estimator: DecisionTreeClassifier,
    col_to_raw_feature: Sequence[int],
    tree_weight: float,
) -> list[_LeafPathSpec]:
    tree = tree_estimator.tree_
    classes = list(tree_estimator.classes_)
    pos_class_pos = classes.index(1) if 1 in classes else None

    children_left = tree.children_left
    children_right = tree.children_right
    features = tree.feature
    thresholds = tree.threshold
    values = tree.value

    paths: list[_LeafPathSpec] = []

    def dfs(
        node_id: int,
        trail: list[tuple[int, float, bool]],
    ) -> None:
        left_id = int(children_left[node_id])
        right_id = int(children_right[node_id])
        if left_id == right_id:  # leaf node (-1 == -1)
            raw_counts = values[node_id, 0]
            denom = float(np.sum(raw_counts))
            if pos_class_pos is None or denom <= 0.0:
                prob_pos = 0.0
            else:
                prob_pos = float(raw_counts[pos_class_pos]) / denom
            weighted_val = prob_pos * tree_weight
            by_raw: dict[int, list[tuple[int, float, bool]]] = {}
            for col_idx, thresh, go_left in trail:
                raw_idx = col_to_raw_feature[col_idx]
                by_raw.setdefault(raw_idx, []).append((col_idx, thresh, go_left))
            grouped = tuple(
                (raw_idx, tuple(conds)) for raw_idx, conds in by_raw.items()
            )
            paths.append(
                _LeafPathSpec(leaf_value=weighted_val, grouped_conditions=grouped)
            )
            return

        col_idx = int(features[node_id])
        thresh = float(thresholds[node_id])
        trail.append((col_idx, thresh, True))
        dfs(left_id, trail)
        trail.pop()

        trail.append((col_idx, thresh, False))
        dfs(right_id, trail)
        trail.pop()

    dfs(0, [])
    return paths


def _shapley_pos_weight(p: int, q: int) -> float:
    """Exact Shapley weight +(p-1)! q! / (p+q)! for a feature in P_leaf."""
    k = p + q
    return 1.0 / (k * math.comb(k - 1, p - 1))


def _shapley_neg_weight(p: int, q: int) -> float:
    """Exact Shapley weight -p! (q-1)! / (p+q)! for a feature in N_leaf."""
    k = p + q
    return -1.0 / (k * math.comb(k - 1, p))


def _compute_grouped_interventional_tree_shap(
    estimator: RandomForestClassifier,
    z_row: np.ndarray,
    Z_bg: np.ndarray,
    preprocessor: FoldSafeClinicalPreprocessor,
) -> tuple[float, float, np.ndarray]:
    col_to_raw = [0] * preprocessor.n_encoded_features
    for raw_idx, ft in enumerate(preprocessor.field_transforms):
        for col_idx in ft.slice_indices:
            col_to_raw[col_idx] = raw_idx

    trees = list(estimator.estimators_)
    if not trees:
        raise ExplainabilityIntegrityError(
            "empty_random_forest",
            "RandomForestClassifier has no fitted decision trees.",
        )
    tree_weight = 1.0 / len(trees)
    all_paths: list[_LeafPathSpec] = []
    for tree_est in trees:
        all_paths.extend(_extract_tree_leaf_paths(tree_est, col_to_raw, tree_weight))

    # Match scikit-learn's Cython _tree.pyx split semantics bit-for-bit:
    # inputs are cast to C float (float32) and then promoted to C double (float64)
    # when compared against double node.threshold.
    z_f32 = np.asarray(z_row, dtype=np.float32).astype(np.float64)
    Z_bg_f32 = np.asarray(Z_bg, dtype=np.float32).astype(np.float64)
    n_bg = Z_bg_f32.shape[0]
    m_features = preprocessor.n_raw_features
    max_k = m_features + 1

    pos_table = np.zeros((max_k, max_k), dtype=np.float64)
    neg_table = np.zeros((max_k, max_k), dtype=np.float64)
    for p in range(1, max_k):
        for q in range(0, max_k - p):
            pos_table[p, q] = _shapley_pos_weight(p, q)
    for p in range(0, max_k):
        for q in range(1, max_k - p):
            neg_table[p, q] = _shapley_neg_weight(p, q)

    phi_accum = np.zeros(m_features, dtype=np.float64)

    for path in all_paths:
        if path.leaf_value == 0.0 or not path.grouped_conditions:
            continue

        alive_mask = np.ones(n_bg, dtype=bool)
        p_candidates: list[tuple[int, np.ndarray]] = []
        n_fixed_indices: list[int] = []
        dead = False

        for raw_idx, conds in path.grouped_conditions:
            fg_ok = True
            bg_ok = np.ones(n_bg, dtype=bool)
            for col_idx, thresh, go_left in conds:
                if go_left:
                    fg_cond = bool(z_f32[col_idx] <= thresh)
                    bg_cond = Z_bg_f32[:, col_idx] <= thresh
                else:
                    fg_cond = bool(z_f32[col_idx] > thresh)
                    bg_cond = Z_bg_f32[:, col_idx] > thresh
                fg_ok = fg_ok and fg_cond
                bg_ok &= bg_cond

            if fg_ok:
                p_candidates.append((raw_idx, ~bg_ok))
            else:
                alive_mask &= bg_ok
                if not alive_mask.any():
                    dead = True
                    break
                n_fixed_indices.append(raw_idx)

        if dead:
            continue

        alive_idx = np.flatnonzero(alive_mask)
        if alive_idx.size == 0:
            continue

        q = len(n_fixed_indices)
        if not p_candidates:
            w_neg = neg_table[0, q] * path.leaf_value * (alive_idx.size / n_bg)
            for raw_idx in n_fixed_indices:
                phi_accum[raw_idx] += w_neg
            continue

        in_p_matrix = np.vstack([bg_fails[alive_idx] for _, bg_fails in p_candidates])
        p_counts = np.sum(in_p_matrix, axis=0)

        pos_weights_per_bg = pos_table[p_counts, q] * (path.leaf_value / n_bg)
        for cand_pos, (raw_idx, _) in enumerate(p_candidates):
            active = in_p_matrix[cand_pos]
            if active.any():
                phi_accum[raw_idx] += float(np.sum(pos_weights_per_bg[active]))

        if q > 0:
            neg_weight_sum = float(np.sum(neg_table[p_counts, q])) * (
                path.leaf_value / n_bg
            )
            for raw_idx in n_fixed_indices:
                phi_accum[raw_idx] += neg_weight_sum

    pos_idx = list(estimator.classes_).index(1)
    base_val = float(np.mean(estimator.predict_proba(Z_bg)[:, pos_idx]))
    target_val = float(estimator.predict_proba(z_row.reshape(1, -1))[0, pos_idx])
    return base_val, target_val, phi_accum


def explain_clinical_instance(
    *,
    model_family: str,
    estimator: Any,
    preprocessor: FoldSafeClinicalPreprocessor,
    panel: ResearchPanelContract,
    background: ShapBackgroundReference,
    z_row: np.ndarray,
    calibrator: OofLogisticCalibrator | None = None,
    missing_feature_names: frozenset[str] = frozenset(),
) -> FaithfulShapExplanation:
    """Compute and verify a faithful Shapley explanation with explicit score/scale alignment."""
    if model_family not in METHOD_BY_MODEL_FAMILY:
        raise ExplainabilityIntegrityError(
            "unsupported_model_family_for_shap",
            f"Model family '{model_family}' has no registered faithful SHAP explainer.",
        )
    z = np.asarray(z_row, dtype=np.float64).ravel()
    if z.shape[0] != preprocessor.n_encoded_features or not np.isfinite(z).all():
        raise ExplainabilityIntegrityError(
            "invalid_instance_vector",
            "Encoded instance vector is misaligned or contains non-finite values.",
        )

    Z_bg = background.background_matrix
    method = METHOD_BY_MODEL_FAMILY[model_family]

    if model_family == "l2_logistic_regression":
        if not isinstance(estimator, LogisticRegression):
            raise ExplainabilityIntegrityError(
                "estimator_family_mismatch",
                "Expected fitted LogisticRegression for 'l2_logistic_regression'.",
            )
        coef = np.asarray(estimator.coef_, dtype=np.float64).ravel()
        intercept = float(np.asarray(estimator.intercept_, dtype=np.float64).ravel()[0])
        bg_mean = np.mean(Z_bg, axis=0)
        raw_base = float(intercept + np.dot(coef, bg_mean))
        raw_target_logit = float(estimator.decision_function(z.reshape(1, -1))[0])
        diff = z - bg_mean
        raw_phi = np.array(
            [
                float(
                    np.dot(
                        coef[list(ft.slice_indices)], diff[list(ft.slice_indices)]
                    )
                )
                for ft in preprocessor.field_transforms
            ],
            dtype=np.float64,
        )

        if calibrator is not None:
            if (
                calibrator.model_family != "l2_logistic_regression"
                or calibrator.input_link != "exact_raw_log_odds"
            ):
                raise ExplainabilityIntegrityError(
                    "incompatible_calibrator_for_calibrated_linear_shap",
                    "Calibrated-log-odds LinearSHAP requires an l2_logistic_regression "
                    "calibrator fitted with input_link='exact_raw_log_odds'.",
                )
            base_value = float(calibrator.intercept + calibrator.slope * raw_base)
            target_value = float(calibrator.transform_log_odds(raw_target_logit))
            phi = np.asarray(calibrator.slope * raw_phi, dtype=np.float64)
            explained_quantity = "calibrated_log_odds"
            scale = "calibrated_log_odds"
            explains_calibrated_score_directly = True
            linked_probability_quantity = "calibrated_research_score"
            linked_probability_value = float(expit(target_value))
            score_alignment_note = (
                "Exact Interventional LinearSHAP on calibrated_log_odds = intercept + slope * raw_log_odds; "
                "base_value + sum(attributions) == logit(calibrated_research_score) and "
                "expit(base_value + sum(attributions)) == calibrated_research_score. "
                "Attributions are additive in calibrated log-odds, NOT additive in probability units."
            )
        else:
            base_value = raw_base
            target_value = raw_target_logit
            phi = raw_phi
            explained_quantity = "raw_model_log_odds"
            scale = "raw_log_odds"
            explains_calibrated_score_directly = False
            linked_probability_quantity = "raw_model_score"
            linked_probability_value = float(expit(raw_target_logit))
            score_alignment_note = (
                "Exact Interventional LinearSHAP on uncalibrated raw_model_log_odds; "
                "base_value + sum(attributions) == logit(raw_model_score). Does NOT include "
                "post-hoc probability calibration and is NOT additive on calibrated_research_score."
            )
    elif model_family == "constrained_random_forest":
        if not isinstance(estimator, RandomForestClassifier):
            raise ExplainabilityIntegrityError(
                "estimator_family_mismatch",
                "Expected fitted RandomForestClassifier for 'constrained_random_forest'.",
            )
        base_value, target_value, phi = _compute_grouped_interventional_tree_shap(
            estimator, z, Z_bg, preprocessor
        )
        explained_quantity = "raw_model_score"
        scale = "raw_model_probability"
        explains_calibrated_score_directly = False
        linked_probability_quantity = "raw_model_score"
        linked_probability_value = float(target_value)
        score_alignment_note = (
            "Exact Interventional TreeSHAP on uncalibrated raw_model_score (mean tree probability); "
            "base_value + sum(attributions) == raw_model_score. Post-hoc logistic calibration is "
            "nonlinear across averaged trees, so these attributions do NOT sum to calibrated_research_score."
        )
    else:  # prevalence_dummy
        if not isinstance(estimator, DummyClassifier):
            raise ExplainabilityIntegrityError(
                "estimator_family_mismatch",
                "Expected fitted DummyClassifier for 'prevalence_dummy'.",
            )
        pos_idx = list(estimator.classes_).index(1)
        base_value = float(np.mean(estimator.predict_proba(Z_bg)[:, pos_idx]))
        target_value = float(estimator.predict_proba(z.reshape(1, -1))[0, pos_idx])
        phi = np.zeros(preprocessor.n_raw_features, dtype=np.float64)
        explained_quantity = "raw_model_score"
        scale = "raw_model_probability"
        explains_calibrated_score_directly = False
        linked_probability_quantity = "raw_model_score"
        linked_probability_value = float(target_value)
        score_alignment_note = (
            "Constant prevalence baseline on raw_model_score; all feature attributions are zero "
            "and are NOT additive decompositions of post-hoc calibrated probability."
        )

    reconstructed = float(base_value + np.sum(phi))
    discrepancy = abs(reconstructed - target_value)
    if not math.isfinite(discrepancy) or discrepancy > ADDITIVITY_TOLERANCE:
        raise ExplainabilityIntegrityError(
            "shap_additivity_check_failed",
            "Computed Shapley attributions failed mandatory efficiency sum check.",
        )

    attributions = tuple(
        FeatureShapAttribution(
            feature_name=spec.name,
            clinical_meaning=spec.clinical_meaning,
            status=(
                "missing_imputed" if spec.name in missing_feature_names else "present"
            ),
            shap_value=float(phi[idx]),
        )
        for idx, spec in enumerate(panel.fields)
    )

    return FaithfulShapExplanation(
        method=method,
        model_family=model_family,
        explained_quantity=explained_quantity,
        scale=scale,
        explains_calibrated_score_directly=explains_calibrated_score_directly,
        additive_on_calibrated_probability=False,
        linked_probability_quantity=linked_probability_quantity,
        linked_probability_value=linked_probability_value,
        score_alignment_note=score_alignment_note,
        faithful_to_model_family=True,
        synthetic_placeholder=False,
        background_sample_count=int(Z_bg.shape[0]),
        base_value=base_value,
        target_prediction_on_scale=target_value,
        attributions=attributions,
        sum_check_passed=True,
        max_abs_discrepancy=discrepancy,
    )


def exact_coalition_shapley_oracle(
    predict_encoded_fn: Callable[[np.ndarray], np.ndarray],
    preprocessor: FoldSafeClinicalPreprocessor,
    x_raw_row: np.ndarray,
    X_bg_raw: np.ndarray,
) -> tuple[float, float, np.ndarray]:
    """Ground-truth 2^M coalition Shapley enumeration in raw clinical feature space.

    Used by automated mathematical verification tests (for M <= 10) to prove
    that ``linear_shap_interventional`` (both uncalibrated and calibrated-log-odds)
    and ``tree_shap_interventional`` match the exact Shapley value definition over
    grouped clinical features.
    """
    x_row = np.asarray(x_raw_row, dtype=np.float64).ravel()
    X_bg = np.asarray(X_bg_raw, dtype=np.float64)
    m = x_row.shape[0]
    if m > 10:
        raise ValueError(
            "Exact 2^M coalition oracle is restricted to M <= 10 features."
        )

    coalition_values = np.zeros(1 << m, dtype=np.float64)
    for mask in range(1 << m):
        hybrid = X_bg.copy()
        for feat_idx in range(m):
            if (mask >> feat_idx) & 1:
                hybrid[:, feat_idx] = x_row[feat_idx]
        Z_hybrid = preprocessor.transform(hybrid)
        coalition_values[mask] = float(np.mean(predict_encoded_fn(Z_hybrid)))

    phi = np.zeros(m, dtype=np.float64)
    for i in range(m):
        bit = 1 << i
        acc = 0.0
        for mask in range(1 << m):
            if mask & bit:
                continue
            s_size = mask.bit_count()
            weight = 1.0 / (m * math.comb(m - 1, s_size))
            acc += weight * (coalition_values[mask | bit] - coalition_values[mask])
        phi[i] = acc

    base_val = float(coalition_values[0])
    target_val = float(coalition_values[(1 << m) - 1])
    return base_val, target_val, phi
