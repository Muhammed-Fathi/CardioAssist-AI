"""AI-8 — source-specific UCI-412 (DA-A1) standalone research model completion.

This module is a *thin, source-specific orchestration layer* over the existing
reusable :mod:`ai` components. It deliberately introduces **no second training
framework, feature schema, calibrator, explainer or packager**: every step
delegates to the already-reviewed AI-1/AI-7 machinery.

Bound scope (synthetic only)
----------------------------
* The only admissible route/panel is the registered UCI-412 basic clinical
  panel :data:`ai.panels.DA_A1_BASIC_CLINICAL_PANEL`
  (``da_a1_basic_clinical_v1``, 16 ordered features, feature dictionary 1.1.0).
* Every record is an explicitly synthetic, Track A,
  ``structured_synthetic_research`` fixture validated through the existing
  panel contract. Real-patient data, OCR documents, wearables, Track B,
  patient uploads and clinician records are rejected fail-closed.
* There is no cross-source schema translation: a UCI-45/Cleveland record, a
  different panel, pooling, or any real-data/serving operation is rejected.
* The frozen A3 Cleveland diagnostic registry (:mod:`ai.diagnostic_scope`) is
  never imported, modified or used as a back door.

What it adds beyond the generic AI-7 route *exercise*
-----------------------------------------------------
The AI-7 :func:`ai.research_routes.execute_synthetic_route_exercise` is a
deterministic smoke exercise that treats UCI-412 as one interchangeable route.
This module produces a *standalone, source-specific, persistently packageable*
UCI-412 research model with:

1. an independent, separately-seeded synthetic held-out test cohort that is
   never used for fitting, calibration or model selection;
2. an explicitly origin-labelled metrics contract that keeps apparent,
   development-OOF (uncalibrated and cross-fitted calibrated) and held-out
   synthetic-test metrics in separate, never-merged blocks;
3. the full RESEARCH_ONLY bundle path (package -> HMAC trusted-local
   verification -> authenticated load -> offline prediction -> SHAP/LIME);
4. a deterministic, machine-readable report whose every performance block
   carries the marker ``SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE``.

Nothing here authorizes real UCI-412 fitting, real-bundle inference or
clinical serving. Gate PT (P-3) remains closed; P-1 remains pending; P-5
remains prohibited.
"""
from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final, Mapping, Sequence

import numpy as np

from ai.calibration import (
    compute_fold_prediction_dispersion,
    compute_prevalence_shift_diagnostic,
    evaluate_comprehensive_metrics,
)
from ai.errors import (
    BundleIntegrityError,
    ClinicalInputValidationError,
    CohortGovernanceError,
)
from ai.explainability import explain_clinical_instance
from ai.inference import ResearchCadPredictor, ResearchPredictionResult
from ai.lime_explainability import (
    DEFAULT_LIME_STABILITY_SEEDS,
    LimeConfig,
    explain_clinical_instance_lime_certified,
)
from ai.lime_quality import LimeQualityPolicy
from ai.packaging import (
    get_or_create_local_signing_key,
    package_research_bundle,
    verify_trusted_local_bundle,
)
from ai.panels import (
    DA_A1_BASIC_CLINICAL_PANEL,
    ResearchPanelContract,
    validate_cohort_records,
)
from ai.research_routes import (
    OP_END_TO_END_EXERCISE,
    ResearchRouteDescriptor,
    RouteResolutionError,
    assert_route_eligible,
    build_synthetic_uci412_basic_clinical_cohort,
    get_route_descriptor,
)
from ai.training import (
    EXECUTION_PROFILE_AI1_GENERIC_V1,
    FoldEnsembleMember,
    ResearchTrainingConfig,
    TrainedResearchRun,
    _estimator_input_matrix,
    _positive_proba_and_optional_logit,
    train_research_model,
)

__all__ = [
    "UCI412_DATASET_ID",
    "UCI412_SOURCE_FAMILY",
    "UCI412_ROUTE_ID",
    "UCI412_PANEL_ID",
    "SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE",
    "ORIGIN_APPARENT_FINAL_CALIBRATOR_DIAGNOSTIC",
    "ORIGIN_DEVELOPMENT_OOF_CROSS_FITTED_CALIBRATED",
    "ORIGIN_DEVELOPMENT_OOF_UNCALIBRATED",
    "ORIGIN_HELD_OUT_SYNTHETIC_TEST",
    "Uci412ResearchModelConfig",
    "Uci412ResearchModelReport",
    "Uci412SyntheticModelResult",
    "build_uci412_synthetic_research_model",
    "validate_uci412_synthetic_cohort",
    "load_uci412_research_predictor",
    "Uci412ResearchGovernanceError",
]

# --------------------------------------------------------------------------- #
# Source-specific binding constants                                          #
# --------------------------------------------------------------------------- #

UCI412_DATASET_ID: Final[str] = "DA-A1"
UCI412_SOURCE_FAMILY: Final[str] = "UCI-412"
UCI412_ROUTE_ID: Final[str] = "da_a1_basic_clinical_v1"
UCI412_PANEL_ID: Final[str] = "da_a1_basic_clinical_v1"

#: Marker that must appear on every performance block produced by this module.
SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE: Final[str] = (
    "SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE"
)

# Metric prediction-origin vocabulary. These distinct labels are never merged
# under one vague "performance" heading.
ORIGIN_DEVELOPMENT_OOF_UNCALIBRATED: Final[str] = (
    "DEVELOPMENT_OOF_UNCALIBRATED_NESTED_CV"
)
ORIGIN_DEVELOPMENT_OOF_CROSS_FITTED_CALIBRATED: Final[str] = (
    "DEVELOPMENT_OOF_CROSS_FITTED_CALIBRATED_NESTED_CV"
)
ORIGIN_APPARENT_FINAL_CALIBRATOR_DIAGNOSTIC: Final[str] = (
    "APPARENT_FINAL_CALIBRATOR_DIAGNOSTIC_NOT_UNBIASED"
)
ORIGIN_HELD_OUT_SYNTHETIC_TEST: Final[str] = (
    "HELD_OUT_INDEPENDENT_SYNTHETIC_TEST_FROZEN_MODEL"
)

#: The only input source this synthetic orchestration accepts.
STRUCTURED_SYNTHETIC_SOURCE: Final[str] = "structured_synthetic_research"

#: Inputs that can never populate a Track A UCI-412 model input in this module.
#: This is deliberately wider than the panel-level wearable set so OCR,
#: patient-upload and real-data claims are rejected at the source-specific
#: boundary as well as at the route resolver.
PROHIBITED_INPUT_SOURCES: Final[frozenset[str]] = frozenset(
    {
        "track_b",
        "wearable",
        "simulated_wearable",
        "patient_wearable",
        "patient_monitoring",
        "patient_upload",
        "clinician_record",
        "ocr_document",
        "ocr",
        "real_data",
        "real_patient",
    }
)

#: Panels/datasets that are explicitly foreign to this source-specific module.
FOREIGN_PANEL_IDS: Final[frozenset[str]] = frozenset(
    {
        "da_a2_resting_v1",
        "da_a2_resting_labs_v1",
        "da_a1_clinical_core_labs_v1",
    }
)


class Uci412ResearchGovernanceError(CohortGovernanceError):
    """Raised when a UCI-412 source-specific governance boundary is crossed."""


# --------------------------------------------------------------------------- #
# Configuration                                                               #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class Uci412ResearchModelConfig:
    """Deterministic configuration for one standalone UCI-412 synthetic build.

    The default budget is a real nested-CV budget; tests pass a reduced
    :meth:`fast` profile. The held-out test cohort always uses a distinct seed
    (``seed + 1``) and distinct rows from the development cohort.
    """

    n_development: int = 240
    n_test: int = 120
    seed: int = 20261028
    outer_folds: int = 4
    inner_folds: int = 3
    repeat_seeds: tuple[int, ...] = (20261025,)
    shuffle_control_seeds: tuple[int, ...] = (20261101,)
    shuffle_max_allowed_auroc: float = 0.68
    bootstrap_resamples: int = 200
    shap_max_background_samples: int = 48
    lime_num_perturbations: int = 320
    exploratory_threshold: float = 0.5
    package_bundle: bool = False
    work_root: Path | None = None
    model_id: str = "synth_ai8_uci412_da_a1_basic_clinical"

    def __post_init__(self) -> None:
        if self.n_development < 16 or self.n_test < 8:
            raise ValueError("n_development >= 16 and n_test >= 8 are required.")
        if not (0.0 < self.exploratory_threshold < 1.0):
            raise ValueError("exploratory_threshold must lie in (0, 1).")
        if not (0.5 <= self.shuffle_max_allowed_auroc <= 1.0):
            raise ValueError("shuffle_max_allowed_auroc must lie in [0.5, 1].")
        if self.seed + 1 == self.seed:
            raise ValueError("Seed overflow would collide development/test cohorts.")

    @classmethod
    def fast(cls, **overrides: Any) -> "Uci412ResearchModelConfig":
        """Reduced deterministic budget for the automated test suite."""
        defaults: dict[str, Any] = dict(
            n_development=120,
            n_test=60,
            outer_folds=3,
            inner_folds=2,
            repeat_seeds=(20261025,),
            shuffle_control_seeds=(20261101,),
            bootstrap_resamples=60,
            shap_max_background_samples=24,
            lime_num_perturbations=160,
        )
        defaults.update(overrides)
        return cls(**defaults)

    def training_config(self) -> ResearchTrainingConfig:
        """Map the source-specific config onto the shared training config.

        Only the generic AI-1 execution profile is permitted; the Cleveland
        D-047 frozen profile is a foreign-source profile and is never used here.
        """
        return ResearchTrainingConfig(
            protocol_id="CAI-AI8-SYNTHETIC-UCI412-DA-A1-BASIC-CLINICAL-V1",
            model_version="0.1.0",
            outer_folds=self.outer_folds,
            inner_folds=self.inner_folds,
            repeat_seeds=tuple(self.repeat_seeds),
            shuffle_control_seeds=tuple(self.shuffle_control_seeds),
            shuffle_max_allowed_auroc=self.shuffle_max_allowed_auroc,
            bootstrap_resamples=self.bootstrap_resamples,
            shap_max_background_samples=self.shap_max_background_samples,
            exploratory_threshold=self.exploratory_threshold,
            execution_profile=EXECUTION_PROFILE_AI1_GENERIC_V1,
        )


# --------------------------------------------------------------------------- #
# Source-specific guards                                                      #
# --------------------------------------------------------------------------- #


def _bound_route_and_panel() -> tuple[ResearchRouteDescriptor, ResearchPanelContract]:
    """Resolve and bind the single admissible UCI-412 route and panel.

    Reuses the AI-7 resolver so this module cannot approve anything the route
    layer would reject, then asserts the exact source-specific identity.
    """
    try:
        descriptor = get_route_descriptor(UCI412_ROUTE_ID)
    except RouteResolutionError as exc:  # pragma: no cover - registry invariant
        raise Uci412ResearchGovernanceError(
            "uci412_route_not_registered",
            "The UCI-412 basic clinical route is not registered.",
        ) from exc
    if descriptor.dataset_id != UCI412_DATASET_ID:
        raise Uci412ResearchGovernanceError(
            "uci412_dataset_identity_mismatch",
            "The resolved route is not bound to dataset DA-A1 (UCI-412).",
        )
    if descriptor.panel_id != UCI412_PANEL_ID:
        raise Uci412ResearchGovernanceError(
            "uci412_panel_identity_mismatch",
            "The resolved route is not bound to the da_a1_basic_clinical_v1 panel.",
        )
    # Full eligibility resolution with an explicit synthetic Track A context.
    resolved = assert_route_eligible(
        dataset_id=UCI412_DATASET_ID,
        panel_id=UCI412_PANEL_ID,
        operation=OP_END_TO_END_EXERCISE,
        source_family=UCI412_SOURCE_FAMILY,
        declared_input_context={
            "track": "A",
            "source": STRUCTURED_SYNTHETIC_SOURCE,
            "synthetic": True,
            "real_data": False,
        },
    )
    panel = DA_A1_BASIC_CLINICAL_PANEL
    if resolved.panel_contract_sha256 != panel.contract_sha256:
        raise Uci412ResearchGovernanceError(
            "uci412_panel_contract_hash_mismatch",
            "Route panel hash does not match the live registered panel contract.",
        )
    return descriptor, panel


def _assert_synthetic_track_a_context(record: Mapping[str, Any]) -> None:
    """Reject non-synthetic, OCR, wearable, Track B or real-data sources."""
    if not isinstance(record, Mapping):
        raise ClinicalInputValidationError(
            "malformed_payload", "UCI-412 record must be a mapping."
        )
    if record.get("synthetic") is not True:
        raise Uci412ResearchGovernanceError(
            "non_synthetic_uci412_input_rejected",
            "Only explicitly synthetic UCI-412 fixtures are accepted; Gate PT is closed.",
        )
    if record.get("panel_id") not in (None, UCI412_PANEL_ID):
        raise Uci412ResearchGovernanceError(
            "uci412_panel_id_mismatch",
            "Record panel_id does not match da_a1_basic_clinical_v1.",
        )
    context = record.get("context", {})
    if not isinstance(context, Mapping):
        raise ClinicalInputValidationError(
            "malformed_context", "UCI-412 context metadata must be a mapping."
        )
    if context.get("track", "A") != "A":
        raise Uci412ResearchGovernanceError(
            "track_b_uci412_input_rejected",
            "Track B observations are prohibited for Track A UCI-412 inference.",
        )
    source = str(context.get("source", STRUCTURED_SYNTHETIC_SOURCE)).lower()
    if source in PROHIBITED_INPUT_SOURCES or "wearable" in source or "ocr" in source:
        raise Uci412ResearchGovernanceError(
            "prohibited_uci412_input_source",
            "OCR, wearable, patient-upload or real-data sources are rejected.",
        )
    if source != STRUCTURED_SYNTHETIC_SOURCE:
        raise Uci412ResearchGovernanceError(
            "unsupported_uci412_input_source",
            "Only structured_synthetic_research fixtures are accepted.",
        )


def validate_uci412_synthetic_cohort(
    records: Sequence[Mapping[str, Any]],
    labels: Sequence[int],
) -> tuple[np.ndarray, np.ndarray, ResearchPanelContract]:
    """Validate a synthetic UCI-412 cohort against the pinned 16-feature panel.

    Enforces, in order: source-specific synthetic Track A context, the exact
    panel identity, and the existing strict panel contract (field order,
    registered categorical encodings, numeric plausibility/units, explicit
    missingness, anti-leakage and anti-wearable rules).
    """
    descriptor, panel = _bound_route_and_panel()
    if not records:
        raise ClinicalInputValidationError(
            "empty_cohort", "UCI-412 cohort must contain at least one record."
        )
    for record in records:
        _assert_synthetic_track_a_context(record)
    # Foreign-panel defence in depth: a UCI-45 envelope names a different
    # panel_id and is rejected before the shared validator runs.
    for record in records:
        declared = record.get("panel_id")
        if declared in FOREIGN_PANEL_IDS:
            raise Uci412ResearchGovernanceError(
                "cross_source_uci45_input_rejected",
                "A UCI-45/Cleveland or extended-lab panel record cannot be passed into "
                "the UCI-412 source-specific pipeline; no crosswalk exists.",
            )
    X, y, _validated = validate_cohort_records(
        records, labels, panel, require_synthetic=True
    )
    if X.shape[1] != len(panel.fields):
        raise Uci412ResearchGovernanceError(
            "uci412_feature_width_mismatch",
            "The validated UCI-412 matrix width does not match the 16-feature panel.",
        )
    return X, y, panel


# --------------------------------------------------------------------------- #
# Prediction helpers (same primitives as the shared pipeline)                #
# --------------------------------------------------------------------------- #


def _predict_frozen(
    run: TrainedResearchRun, X: np.ndarray
) -> tuple[np.ndarray, np.ndarray | None, np.ndarray]:
    """Raw probabilities, optional raw log-odds and calibrated scores."""
    Z = run.preprocessor.transform(X)
    E = _estimator_input_matrix(
        run.selected_model_family,
        run.preprocessor,
        X,
        Z,
        run.execution_profile,
    )
    p_raw, raw_logits = _positive_proba_and_optional_logit(
        run.selected_model_family, run.estimator, E
    )
    p_cal = run.calibrator.calibrate(p_raw, raw_logits=raw_logits)
    return p_raw, raw_logits, p_cal


def _fold_member_scores(
    run: TrainedResearchRun, member: FoldEnsembleMember, X_instance: np.ndarray
) -> tuple[float, float]:
    z = member.preprocessor.transform(X_instance)
    E = _estimator_input_matrix(
        member.model_family,
        member.preprocessor,
        X_instance,
        z,
        run.execution_profile,
    )
    raw, raw_logit = _positive_proba_and_optional_logit(
        member.model_family, member.estimator, E
    )
    cal = member.calibrator.calibrate(raw, raw_logits=raw_logit)
    return float(raw[0]), float(cal[0])


# --------------------------------------------------------------------------- #
# Origin-labelled metric blocks                                              #
# --------------------------------------------------------------------------- #


def _origin_header(
    origin: str, population: str
) -> dict[str, str]:
    return {
        "prediction_origin": origin,
        "evaluation_population": population,
        "evidence_marker": SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE,
        "clinical_evidence": False,
    }


def _selected_procedure_mean(
    repeats: Sequence[Mapping[str, Any]], metric_path: tuple[str, ...]
) -> float | None:
    values: list[float] = []
    for repeat in repeats:
        node: Any = repeat.get("models", {}).get("inner_selected_procedure", {})
        for key in metric_path:
            if not isinstance(node, Mapping) or key not in node:
                node = None
                break
            node = node[key]
        if isinstance(node, (int, float)):
            values.append(float(node))
    return float(np.mean(values)) if values else None


def _development_origin_block(
    internal: Mapping[str, Any],
    *,
    key: str,
    origin: str,
    population: str,
    metric_paths: Mapping[str, tuple[str, ...]],
) -> dict[str, Any]:
    section = dict(internal[key])
    repeats = section.get("repeats", ())
    summary = {
        name: _selected_procedure_mean(repeats, path)
        for name, path in metric_paths.items()
    }
    return {
        **_origin_header(origin, population),
        "evaluation_design": section.get("evaluation_design", internal.get("evaluation_design")),
        "each_observation_excluded_from_model_fit": bool(
            section.get("each_observation_excluded_from_model_fit", True)
        ),
        "each_observation_excluded_from_calibrator_fit": bool(
            section.get("each_observation_excluded_from_model_and_calibrator_fit", False)
        ),
        "repeat_count": internal.get("repeat_count"),
        "n_participants": internal.get("n_participants"),
        "n_positive": internal.get("n_positive"),
        "n_negative": internal.get("n_negative"),
        "selected_model_family": internal.get("selected_model_family"),
        "outer_fold_family_selection_counts": internal.get(
            "outer_fold_family_selection_counts"
        ),
        "selected_procedure_summary_across_repeats": summary,
        "repeats": section.get("repeats"),
        "caveats": internal.get("caveats"),
    }


def _held_out_metric_block(
    *,
    run: TrainedResearchRun,
    X_test: np.ndarray,
    y_test: np.ndarray,
    n_test: int,
    test_seed: int,
    config: Uci412ResearchModelConfig,
) -> tuple[dict[str, Any], np.ndarray, np.ndarray]:
    _raw, _logits, p_cal = _predict_frozen(run, X_test)
    prevalence = float(np.mean(y_test == 1))
    metrics = evaluate_comprehensive_metrics(
        y_test,
        p_cal,
        seed=config.seed,
        n_bootstrap=config.bootstrap_resamples,
        threshold=config.exploratory_threshold,
        evaluation_scope="SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE_UCI412_HELD_OUT",
    )
    shift = compute_prevalence_shift_diagnostic(
        development_prevalence=float(run.calibrator.development_prevalence),
        external_prevalence=prevalence,
    )
    block = {
        **_origin_header(
            ORIGIN_HELD_OUT_SYNTHETIC_TEST,
            (
                f"Independent synthetic UCI-412 held-out test cohort (n={n_test}, "
                f"separate seed {test_seed}); frozen final model + development "
                "calibrator, no refit on test rows."
            ),
        ),
        "test_cohort_seed": test_seed,
        "test_cohort_id": f"synthetic:UCI-412:held_out:seed{test_seed}",
        "prevalence": prevalence,
        "class_distribution": {
            "n": int(y_test.size),
            "n_positive": int(np.sum(y_test == 1)),
            "n_negative": int(np.sum(y_test == 0)),
        },
        "metrics": metrics,
        "prevalence_shift_vs_development": shift,
        "threshold_semantics": {
            "exploratory_threshold": config.exploratory_threshold,
            "threshold_clinically_approved": False,
            "note": (
                "The 0.5 cutoff is an exploratory, unvalidated threshold (Gate P-4 "
                "pending); it is not a clinical decision rule."
            ),
        },
    }
    return block, p_cal, y_test


# --------------------------------------------------------------------------- #
# Report dataclass                                                            #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class Uci412ResearchModelReport:
    """Machine-readable, deterministic source-specific research report."""

    report_schema: str
    evidence_marker: str
    source_identity: Mapping[str, Any]
    route_binding: Mapping[str, Any]
    feature_contract: Mapping[str, Any]
    target_contract: Mapping[str, Any]
    model_binding: Mapping[str, Any]
    development_cohort: Mapping[str, Any]
    held_out_test_cohort: Mapping[str, Any]
    metrics_by_origin: Mapping[str, Any]
    calibration_integrity: Mapping[str, Any]
    fold_dispersion: Mapping[str, Any]
    shap_quality: Mapping[str, Any]
    lime_quality: Mapping[str, Any]
    negative_control: Mapping[str, Any]
    bundle_binding: Mapping[str, Any] | None
    offline_prediction: Mapping[str, Any] | None
    eligibility: Mapping[str, Any]
    limitations: tuple[str, ...]

    @staticmethod
    def _strip_timing(node: Any) -> Any:
        if isinstance(node, Mapping):
            return {
                key: Uci412ResearchModelReport._strip_timing(value)
                for key, value in node.items()
                if key not in ("runtime_seconds", "runtime", "generated_at_utc")
            }
        if isinstance(node, list):
            return [Uci412ResearchModelReport._strip_timing(item) for item in node]
        return node

    def _deterministic_payload(self) -> dict[str, Any]:
        return self._strip_timing(self.to_dict())

    @property
    def deterministic_sha256(self) -> str:
        payload = json.dumps(
            self._deterministic_payload(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_schema": self.report_schema,
            "evidence_marker": self.evidence_marker,
            "source_identity": dict(self.source_identity),
            "route_binding": dict(self.route_binding),
            "feature_contract": dict(self.feature_contract),
            "target_contract": dict(self.target_contract),
            "model_binding": dict(self.model_binding),
            "development_cohort": dict(self.development_cohort),
            "held_out_test_cohort": dict(self.held_out_test_cohort),
            "metrics_by_origin": dict(self.metrics_by_origin),
            "calibration_integrity": dict(self.calibration_integrity),
            "fold_dispersion": dict(self.fold_dispersion),
            "shap_quality": dict(self.shap_quality),
            "lime_quality": dict(self.lime_quality),
            "negative_control": dict(self.negative_control),
            "bundle_binding": (
                None if self.bundle_binding is None else dict(self.bundle_binding)
            ),
            "offline_prediction": (
                None if self.offline_prediction is None else dict(self.offline_prediction)
            ),
            "eligibility": dict(self.eligibility),
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True, slots=True)
class Uci412SyntheticModelResult:
    """Complete output: report plus the non-serialized run and bundle handles."""

    report: Uci412ResearchModelReport
    run: TrainedResearchRun
    descriptor: ResearchRouteDescriptor
    panel: ResearchPanelContract
    development_records: tuple[Mapping[str, Any], ...]
    test_records: tuple[Mapping[str, Any], ...]
    bundle_dir: Path | None = None
    trusted_root: Path | None = None
    signing_key_path: Path | None = None
    predictor: ResearchCadPredictor | None = None
    config: Uci412ResearchModelConfig | None = None

    def to_dict(self) -> dict[str, Any]:
        out = self.report.to_dict()
        out["report_deterministic_sha256"] = self.report.deterministic_sha256
        return out


# --------------------------------------------------------------------------- #
# Bundle path                                                                 #
# --------------------------------------------------------------------------- #


def _package_and_load(
    *,
    run: TrainedResearchRun,
    config: Uci412ResearchModelConfig,
    sample_payload: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], Path, Path, Path, ResearchCadPredictor]:
    if config.work_root is not None:
        work_root = Path(config.work_root)
    else:
        import tempfile

        work_root = Path(tempfile.mkdtemp(prefix="cai_ai8_uci412_"))
    work_root.mkdir(parents=True, exist_ok=True)
    trusted_root = work_root / "trusted_bundles"
    key_dir = work_root / "private_keys"
    trusted_root.mkdir(parents=True, exist_ok=True)
    key_dir.mkdir(parents=True, exist_ok=True)
    key_path = key_dir / "local_bundle_hmac_v1.key"
    signing_key = get_or_create_local_signing_key(key_path)

    # A unique on-disk directory per build: the packager refuses to overwrite an
    # existing bundle, and the filesystem path is deliberately kept out of the
    # deterministic report (only content hashes are reported there).
    import uuid

    bundle_dir = (
        trusted_root
        / f"synthetic_research_bundle_da_a1_basic_clinical_v1_{uuid.uuid4().hex[:12]}"
    )
    packaged = package_research_bundle(run, bundle_dir, signing_key=signing_key)
    trusted = verify_trusted_local_bundle(
        bundle_dir, trusted_local_root=trusted_root, signing_key=signing_key
    )
    if not trusted.producer_authenticated or not trusted.safe_for_pickle_deserialization:
        raise BundleIntegrityError(
            "uci412_bundle_not_authenticated",
            "The UCI-412 synthetic bundle failed trusted-local authentication.",
        )
    predictor = ResearchCadPredictor.from_verified_bundle(
        bundle_dir, trusted_local_root=trusted_root, signing_key=signing_key
    )
    if predictor.panel.panel_id != UCI412_PANEL_ID:
        raise Uci412ResearchGovernanceError(
            "uci412_loaded_bundle_panel_mismatch",
            "The loaded bundle is not bound to da_a1_basic_clinical_v1.",
        )
    prediction = predictor.predict_research_only(
        sample_payload, exploratory_threshold=config.exploratory_threshold
    )

    manifest = dict(trusted.manifest)
    bundle_binding = {
        # The on-disk bundle directory is intentionally excluded: it is a
        # machine-local path and must not influence the deterministic report
        # hash. The on-disk path is returned via Uci412SyntheticModelResult.
        "bundle_logical_name": "synthetic_research_bundle_da_a1_basic_clinical_v1",
        "bundle_schema_version": manifest.get("bundle_schema_version"),
        "producer_authenticated": bool(trusted.producer_authenticated),
        "safe_for_pickle_deserialization": bool(
            trusted.safe_for_pickle_deserialization
        ),
        "serving_eligibility": str(trusted.serving_eligibility),
        "approved_for_serving": bool(trusted.approved_for_serving),
        "clinical_use_authorized": bool(trusted.clinical_use_authorized),
        "manifest_panel_id": manifest["panel_contract"]["panel_id"],
        "manifest_panel_contract_sha256": manifest["panel_contract"]["contract_sha256"],
        "manifest_ordered_feature_names": list(
            manifest["panel_contract"]["ordered_feature_names"]
        ),
        "manifest_target_id": manifest["target"]["target_id"],
        "manifest_target_definition_sha256": manifest["target"][
            "target_definition_sha256"
        ],
        "manifest_development_dataset_id": manifest["target"]["development_dataset_id"],
        "manifest_pooled_cohorts": bool(manifest["target"]["pooled_cohorts"]),
        "manifest_model_id": manifest["model"]["model_id"],
        "manifest_model_version": manifest["model"]["model_version"],
        "manifest_protocol_id": manifest["model"]["protocol_id"],
        "manifest_model_family": manifest["model"]["selected_model_family"],
        "manifest_execution_profile": manifest["model"]["execution_profile"],
        "manifest_eligibility_execution_mode": manifest["eligibility"]["execution_mode"],
        "manifest_eligibility_synthetic_only": bool(
            manifest["eligibility"]["synthetic_only"]
        ),
        "verified_file_hashes": dict(trusted.verified_files),
        "attestation_scheme": manifest["local_producer_attestation"]["scheme"],
    }
    offline_prediction = {
        "predictor_model_id": predictor.model_id,
        "predictor_model_family": predictor.model_family,
        "predictor_panel_id": predictor.panel.panel_id,
        "serving_eligibility": prediction.serving_eligibility,
        "approved_for_serving": prediction.approved_for_serving,
        "clinical_use_authorized": prediction.clinical_use_authorized,
        "raw_model_score": float(prediction.raw_model_score),
        "calibrated_research_score": float(prediction.calibrated_research_score),
        "calibrated_log_odds": float(prediction.calibrated_log_odds),
        "shap_sum_check_passed": bool(prediction.explanation.sum_check_passed),
        "shap_explained_quantity": str(prediction.explanation.explained_quantity),
        "shap_scale": str(prediction.explanation.scale),
        "score_interpretation": "RESEARCH_ONLY_NOT_INDIVIDUAL_CLINICAL_RISK",
    }
    return (
        bundle_binding,
        offline_prediction,
        bundle_dir,
        trusted_root,
        key_path,
        predictor,
    )


def load_uci412_research_predictor(
    bundle_dir: Path,
    *,
    trusted_local_root: Path,
    signing_key: bytes | None = None,
) -> ResearchCadPredictor:
    """Authenticated, fail-closed load of a UCI-412 RESEARCH_ONLY bundle.

    Reuses :class:`ai.inference.ResearchCadPredictor` and additionally asserts
    the loaded bundle is bound to the UCI-412 basic clinical panel and remains
    ``RESEARCH_ONLY``. Unauthenticated or tampered bundles raise before
    ``joblib.load``.
    """
    predictor = ResearchCadPredictor.from_verified_bundle(
        Path(bundle_dir),
        trusted_local_root=Path(trusted_local_root),
        signing_key=signing_key,
    )
    if predictor.panel.panel_id != UCI412_PANEL_ID:
        raise Uci412ResearchGovernanceError(
            "uci412_loaded_bundle_panel_mismatch",
            "The loaded bundle is not bound to da_a1_basic_clinical_v1.",
        )
    # ResearchCadPredictor carries no serving surface of its own; its trusted
    # VerifiedBundleDescriptor is the authoritative eligibility record. Assert
    # the RESEARCH_ONLY invariant explicitly so a future serving path cannot
    # silently change the boundary.
    descriptor = predictor._descriptor
    if (
        descriptor.approved_for_serving
        or descriptor.clinical_use_authorized
        or descriptor.serving_eligibility != "RESEARCH_ONLY"
    ):
        raise Uci412ResearchGovernanceError(
            "uci412_serving_claim_rejected",
            "A UCI-412 research bundle can never be serving-eligible.",
        )
    return predictor


# --------------------------------------------------------------------------- #
# Main entry point                                                             #
# --------------------------------------------------------------------------- #


def build_uci412_synthetic_research_model(
    config: Uci412ResearchModelConfig | None = None,
) -> Uci412SyntheticModelResult:
    """Build the complete standalone UCI-412 synthetic research model.

    Full path: synthetic UCI-412 records -> registered panel validation ->
    fold-safe nested-CV training with cross-fitted calibration and a
    label-shuffle negative control -> independent held-out synthetic-test
    evaluation -> SHAP/LIME -> (optionally) RESEARCH_ONLY bundle packaging,
    trusted verification, authenticated offline prediction -> machine-readable
    origin-labelled report.
    """
    config = config or Uci412ResearchModelConfig()
    descriptor, panel = _bound_route_and_panel()

    test_seed = config.seed + 1
    dev_records, dev_labels = build_synthetic_uci412_basic_clinical_cohort(
        config.n_development, seed=config.seed
    )
    test_records, test_labels = build_synthetic_uci412_basic_clinical_cohort(
        config.n_test, seed=test_seed
    )

    # Source-specific validation (also proves the cohorts are disjoint by seed
    # construction and bound to exactly the 16-feature UCI-412 panel).
    X_dev, y_dev, _ = validate_uci412_synthetic_cohort(dev_records, dev_labels)
    X_test, y_test, _ = validate_uci412_synthetic_cohort(test_records, test_labels)

    run = train_research_model(
        list(dev_records),
        list(dev_labels),
        panel,
        model_id=config.model_id,
        development_cohort_id=f"synthetic:UCI-412:development:seed{config.seed}",
        development_dataset_id=UCI412_DATASET_ID,
        synthetic_data_confirmed=True,
        config=config.training_config(),
    )

    # --- Origin-labelled metrics ---------------------------------------- #
    internal = dict(run.internal_evaluation)
    population_dev = (
        f"Synthetic UCI-412 development cohort (n={config.n_development}, "
        f"seed {config.seed}); repeated nested CV out-of-fold predictions."
    )
    uncal_block = _development_origin_block(
        internal,
        key="uncalibrated_nested_cv",
        origin=ORIGIN_DEVELOPMENT_OOF_UNCALIBRATED,
        population=population_dev,
        metric_paths={
            "roc_auc": ("discrimination", "roc_auc"),
            "average_precision": ("discrimination", "average_precision"),
            "brier_score": ("proper_scoring_and_calibration", "brier_score"),
        },
    )
    cross_block = _development_origin_block(
        internal,
        key="cross_fitted_calibrated_nested_cv",
        origin=ORIGIN_DEVELOPMENT_OOF_CROSS_FITTED_CALIBRATED,
        population=population_dev,
        metric_paths={
            "roc_auc": ("discrimination", "roc_auc"),
            "average_precision": ("discrimination", "average_precision"),
            "brier_score": ("proper_scoring_and_calibration", "brier_score"),
            "expected_calibration_error_10bin": (
                "proper_scoring_and_calibration",
                "expected_calibration_error_10bin",
            ),
            "log_loss": ("proper_scoring_and_calibration", "log_loss"),
        },
    )
    apparent = dict(internal["final_development_calibrator_apparent_diagnostic"])
    apparent_block = {
        **_origin_header(
            ORIGIN_APPARENT_FINAL_CALIBRATOR_DIAGNOSTIC,
            (
                f"Synthetic UCI-412 development cohort (n={config.n_development}); "
                "apparent resubstitution on the OOF scores used to fit the final "
                "calibrator after full-cohort family selection."
            ),
        ),
        "apparent_in_calibrator_fit": bool(apparent.get("apparent_in_calibrator_fit")),
        "unbiased_calibrated_performance_estimate": False,
        "warning": apparent.get("warning"),
        "metrics": apparent.get("metrics"),
    }
    held_out_block, _p_cal, _y = _held_out_metric_block(
        run=run,
        X_test=X_test,
        y_test=y_test,
        n_test=config.n_test,
        test_seed=test_seed,
        config=config,
    )

    metrics_by_origin = MappingProxyType(
        {
            ORIGIN_DEVELOPMENT_OOF_UNCALIBRATED: uncal_block,
            ORIGIN_DEVELOPMENT_OOF_CROSS_FITTED_CALIBRATED: cross_block,
            ORIGIN_APPARENT_FINAL_CALIBRATOR_DIAGNOSTIC: apparent_block,
            ORIGIN_HELD_OUT_SYNTHETIC_TEST: held_out_block,
        }
    )

    # --- Calibration integrity ------------------------------------------- #
    calibration_integrity = {
        "calibration_status": "calibrated_out_of_fold_logistic",
        "input_link": str(run.calibrator.input_link),
        "intercept": float(run.calibrator.intercept),
        "slope": float(run.calibrator.slope),
        "fit_scope": str(run.calibrator.fit_scope),
        "status": str(run.calibrator.status),
        "n_oof_samples": int(run.calibrator.n_oof_samples),
        "development_prevalence": float(run.calibrator.development_prevalence),
        "cross_fitted_per_fold_calibrators": len(run.fold_ensemble),
        "calibration_binding_matches_model_family": bool(
            all(
                member.calibrator.model_family == member.model_family
                for member in run.fold_ensemble
            )
        ),
        "evidence_marker": SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE,
    }

    # --- Per-instance fold dispersion (ensemble count, never test size) - #
    first_row = X_test[:1]
    fold_raw: list[float] = []
    fold_cal: list[float] = []
    fold_families: list[str] = []
    for member in run.fold_ensemble:
        raw, cal = _fold_member_scores(run, member, first_row)
        fold_raw.append(raw)
        fold_cal.append(cal)
        fold_families.append(member.model_family)
    dispersion = compute_fold_prediction_dispersion(
        fold_raw_scores=fold_raw,
        fold_compatible_calibrated_scores=fold_cal,
        fold_model_families=fold_families,
        missing_fields_with_reason=(),
        total_fields=len(panel.fields),
        development_prevalence=float(run.calibrator.development_prevalence),
    )
    if dispersion["fold_ensemble_count"] != len(run.fold_ensemble):
        raise Uci412ResearchGovernanceError(
            "uci412_fold_dispersion_count_error",
            "Fold dispersion count must equal the outer-fold ensemble size.",
        )

    # --- SHAP and LIME on one held-out instance -------------------------- #
    z_first = run.preprocessor.transform(X_test[:1])[0]
    explanation = explain_clinical_instance(
        model_family=run.selected_model_family,
        estimator=run.estimator,
        preprocessor=run.preprocessor,
        panel=panel,
        background=run.shap_background,
        z_row=z_first,
        calibrator=run.calibrator,
        missing_feature_names=frozenset(),
    )
    if not explanation.sum_check_passed:
        raise Uci412ResearchGovernanceError(
            "uci412_shap_additivity_failure",
            "SHAP additivity sum-check failed for the UCI-412 model.",
        )
    shap_quality = {
        "explained_quantity": str(explanation.explained_quantity),
        "scale": str(explanation.scale),
        "sum_check_passed": bool(explanation.sum_check_passed),
        "max_abs_discrepancy": float(explanation.max_abs_discrepancy),
        "additive_on_calibrated_probability": bool(
            explanation.additive_on_calibrated_probability
        ),
        "explains_calibrated_score_directly": bool(
            explanation.explains_calibrated_score_directly
        ),
        "faithful_to_model_family": bool(explanation.faithful_to_model_family),
        "background_sample_count": int(explanation.background_sample_count),
        "attribution_count": len(explanation.attributions),
        "evidence_marker": SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE,
    }

    lime_policy = LimeQualityPolicy()
    lime_config = LimeConfig(
        num_perturbations=config.lime_num_perturbations, seed=config.seed
    )
    lime_explanation, lime_stability = explain_clinical_instance_lime_certified(
        stability_seeds=DEFAULT_LIME_STABILITY_SEEDS,
        quality_policy=lime_policy,
        model_family=run.selected_model_family,
        estimator=run.estimator,
        preprocessor=run.preprocessor,
        panel=panel,
        background=run.shap_background,
        x_raw_row=X_test[0],
        z_row=z_first,
        calibrator=run.calibrator,
        target="auto",
        config=lime_config,
        missing_feature_names=frozenset(),
    )
    lime_quality = {
        "quality_status": str(lime_explanation.quality_status),
        "is_reliable_for_interpretation": bool(
            lime_explanation.is_reliable_for_interpretation
        ),
        "explained_quantity": str(lime_explanation.explained_quantity),
        "scale": str(lime_explanation.scale),
        "local_fidelity_abs_error": float(lime_explanation.local_fidelity_abs_error),
        "local_fidelity_relative_error": float(
            lime_explanation.local_fidelity_relative_error
        ),
        "weighted_r2": (
            None
            if lime_explanation.weighted_r2 is None
            else float(lime_explanation.weighted_r2)
        ),
        "holdout_weighted_r2": (
            None
            if lime_explanation.holdout_weighted_r2 is None
            else float(lime_explanation.holdout_weighted_r2)
        ),
        "is_local_approximation": bool(lime_explanation.is_local_approximation),
        "stability_assessed": lime_stability is not None,
        "evidence_marker": SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE,
        "note": (
            "A non-acceptable LIME verdict is diagnostic, not a pipeline failure; "
            "the status is reported truthfully and the SHAP explanation remains the "
            "authoritative attribution."
        ),
    }

    # --- Optional full bundle path --------------------------------------- #
    bundle_binding: dict[str, Any] | None = None
    offline_prediction: dict[str, Any] | None = None
    bundle_dir: Path | None = None
    trusted_root: Path | None = None
    key_path: Path | None = None
    predictor: ResearchCadPredictor | None = None
    if config.package_bundle:
        (
            bundle_binding,
            offline_prediction,
            bundle_dir,
            trusted_root,
            key_path,
            predictor,
        ) = _package_and_load(
            run=run,
            config=config,
            sample_payload=test_records[0],
        )
        # Hard binding assertions on the persisted artifact.
        if bundle_binding["manifest_panel_contract_sha256"] != panel.contract_sha256:
            raise Uci412ResearchGovernanceError(
                "uci412_bundle_feature_contract_hash_mismatch",
                "Persisted bundle feature-contract hash does not match the panel.",
            )
        if bundle_binding["manifest_target_id"] != panel.target_id:
            raise Uci412ResearchGovernanceError(
                "uci412_bundle_target_binding_mismatch",
                "Persisted bundle target id does not match the registered target.",
            )
        if bundle_binding["manifest_pooled_cohorts"]:
            raise Uci412ResearchGovernanceError(
                "uci412_bundle_pooling_flag_rejected",
                "A UCI-412 bundle must never declare pooled cohorts.",
            )
        if (
            bundle_binding["approved_for_serving"]
            or bundle_binding["clinical_use_authorized"]
            or bundle_binding["serving_eligibility"] != "RESEARCH_ONLY"
        ):
            raise Uci412ResearchGovernanceError(
                "uci412_bundle_serving_claim_rejected",
                "A UCI-412 research bundle must remain RESEARCH_ONLY.",
            )

    # --- Negative control ------------------------------------------------ #
    negative_control = {
        "label_shuffle_seeds": list(run.negative_control["shuffle_seeds"]),
        "permuted_selected_roc_aucs": list(
            run.negative_control["permuted_selected_roc_aucs"]
        ),
        "max_permuted_roc_auc": float(run.negative_control["max_permuted_roc_auc"]),
        "leakage_ceiling": float(run.negative_control["ceiling"]),
        "leakage_alarm_triggered": bool(
            run.negative_control["leakage_alarm_triggered"]
        ),
        "interpretation": (
            "Label-permutation negative control; a max AUROC at or above the "
            "ceiling raises a blocking leakage alarm and discards the run."
        ),
        "evidence_marker": SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE,
    }

    limitations = (
        "Deterministic synthetic software exercise on generated UCI-412-shaped "
        "fixtures: not trained on patient data and not CAD performance evidence.",
        "Held-out metrics measure generalization to an independent synthetic "
        "cohort drawn from the same generative process, not external validation "
        "on a real or independent population.",
        "calibrated_research_score is not a clinically validated individual CAD "
        "risk and the exploratory 0.5 threshold is not a clinical decision rule.",
        "Outer-fold dispersion is descriptive CV split sensitivity, not validated "
        "patient-specific uncertainty.",
        "UCI-412 source semantics remain partly unresolved (BP quantity, PR unit, "
        "chest-pain definitions, numeric-binary direction S-9, per-field timing); "
        "see the field contract unresolved-question register.",
        "Real UCI-412 fitting, real-bundle inference and clinical serving remain "
        "blocked by Gate PT (P-3 closed); this module authorizes none of them.",
    )

    report = Uci412ResearchModelReport(
        report_schema="cardioassist.ai.uci412_research_report/v1",
        evidence_marker=SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE,
        source_identity=MappingProxyType(
            {
                "dataset_id": UCI412_DATASET_ID,
                "source_family": UCI412_SOURCE_FAMILY,
                "source_id": "UCI-412",
                "source_title": "Z-Alizadeh Sani (UCI Machine Learning Repository id 412)",
                "source_doi": "10.24432/C5Q31T",
                "license_spdx": "CC-BY-4.0",
                "same_participants_as_uci411": True,
                "synthetic_only": True,
            }
        ),
        route_binding=MappingProxyType(
            {
                "route_id": descriptor.route_id,
                "route_version": descriptor.route_version,
                "route_descriptor_sha256": descriptor.descriptor_sha256,
                "research_authorization_status": descriptor.research_authorization_status,
                "evaluation_status": descriptor.evaluation_status,
            }
        ),
        feature_contract=MappingProxyType(
            {
                "panel_id": panel.panel_id,
                "panel_version": panel.panel_version,
                "contract_sha256": panel.contract_sha256,
                "ordered_feature_names": list(panel.feature_names),
                "feature_count": len(panel.fields),
                "field_order_is_contract": True,
                "field_contract_artifact": (
                    "research/intake/schemas/"
                    "uci412_basic_clinical_field_contract.v0.1.json"
                ),
            }
        ),
        target_contract=MappingProxyType(
            {
                "target_id": panel.target_id,
                "target_definition": panel.target_definition,
                "threshold_boundary": "GREATER_THAN_OR_EQUAL_50_PERCENT",
                "target_definition_sha256": hashlib.sha256(
                    panel.target_definition.encode("utf-8")
                ).hexdigest(),
                "non_equivalence_with_uci45": (
                    "UCI-412 >=50% vs UCI-45 >50%; related-but-not-identical; "
                    "never pooled or cross-walked."
                ),
            }
        ),
        model_binding=MappingProxyType(
            {
                "model_id": run.model_id,
                "model_version": run.model_version,
                "protocol_id": run.protocol_id,
                "selected_model_family": run.selected_model_family,
                "selected_hyperparameters": dict(run.selected_hyperparameters),
                "execution_profile": run.execution_profile,
                "preprocessing_contract": "fold_contained_json_lineage_v1",
                "model_and_preprocessing_version_bound": True,
            }
        ),
        development_cohort=MappingProxyType(
            {
                "cohort_id": f"synthetic:UCI-412:development:seed{config.seed}",
                "dataset_id": UCI412_DATASET_ID,
                "seed": config.seed,
                "n": int(y_dev.size),
                "n_positive": int(np.sum(y_dev == 1)),
                "n_negative": int(np.sum(y_dev == 0)),
                "prevalence": float(np.mean(y_dev == 1)),
            }
        ),
        held_out_test_cohort=MappingProxyType(
            {
                "cohort_id": f"synthetic:UCI-412:held_out:seed{test_seed}",
                "dataset_id": UCI412_DATASET_ID,
                "seed": test_seed,
                "n": int(y_test.size),
                "n_positive": int(np.sum(y_test == 1)),
                "n_negative": int(np.sum(y_test == 0)),
                "prevalence": float(np.mean(y_test == 1)),
                "independent_from_development": True,
            }
        ),
        metrics_by_origin=metrics_by_origin,
        calibration_integrity=MappingProxyType(calibration_integrity),
        fold_dispersion=MappingProxyType(dict(dispersion)),
        shap_quality=MappingProxyType(shap_quality),
        lime_quality=MappingProxyType(lime_quality),
        negative_control=MappingProxyType(negative_control),
        bundle_binding=(
            None if bundle_binding is None else MappingProxyType(bundle_binding)
        ),
        offline_prediction=(
            None if offline_prediction is None else MappingProxyType(offline_prediction)
        ),
        eligibility=MappingProxyType(
            {
                "serving_eligibility": "RESEARCH_ONLY",
                "approved_for_serving": False,
                "clinical_use_authorized": False,
                "gate_pt_p3": "CLOSED",
                "gate_pt_p1": "PENDING",
                "gate_pt_p5": "NOT_MADE_PROHIBITED",
                "real_data_authorized": False,
            }
        ),
        limitations=limitations,
    )

    return Uci412SyntheticModelResult(
        report=report,
        run=run,
        descriptor=descriptor,
        panel=panel,
        development_records=tuple(dev_records),
        test_records=tuple(test_records),
        bundle_dir=bundle_dir,
        trusted_root=trusted_root,
        signing_key_path=key_path,
        predictor=predictor,
        config=config,
    )
