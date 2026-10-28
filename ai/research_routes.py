"""Source-specific research route catalog and synthetic-only orchestration layer.

AI-7: Multi-Dataset Research System Engineering.

This module implements a versioned, source-specific research route catalog and a
strict synthetic-only orchestration layer on top of the existing ``ai`` pipeline
(``ai.panels``, ``ai.preprocessing``, ``ai.training``, ``ai.calibration``,
``ai.explainability``, ``ai.lime_explainability``, ``ai.lime_quality``,
``ai.packaging`` and ``ai.inference``).

Design rules (binding on every function in this module):

* **No second feature schema or authorization source.** Route descriptors bind
  to existing ``ai.panels.REGISTERED_PANELS`` contracts by ``panel_id`` and
  re-verify the panel contract SHA-256 at resolution time.
* **Synthetic-only execution layer.** Every route in this catalog is executed
  here exclusively on deterministically generated synthetic fixtures. Real-data
  training, real external evaluation, real-bundle inference and clinical
  serving are *not permitted operations* on any route and are rejected
  fail-closed. They remain governed separately by ``ai.execution``,
  ``ai.packaging`` and ``ai.diagnostic_scope`` (the frozen A3 diagnostic
  runtime is never touched by this module).
* **No AUROC-driven source or model selection.** The resolver matches exactly
  on ``(dataset_id, panel_id, operation, declared input context)`; it never
  inspects, compares or ranks by cross-dataset performance.
* **No schema translation.** A UCI-412 input is never translated into a
  Cleveland schema (or vice versa): route matching is exact on
  ``dataset_id`` + ``panel_id`` and this module implements no crosswalk.
* **The resolver is not an authorization back door.** It can only narrow the
  set of *already synthetic-only permitted* operations; it cannot approve any
  operation that the underlying pipeline guards reject.

The catalog covers the four research routes from the multi-dataset strategy:

* Route A — DA-A2 Cleveland resting five fields (``da_a2_resting_v1``),
  synthetic-exercisable here; the accepted real D-047 bundle stays frozen at
  revision A3 and is never loaded, retrained or inferred through this layer.
* Route A (planned) — DA-A2 resting + labs seven fields
  (``da_a2_resting_labs_v1``): contract exposure only, execution blocked until
  independently authorized.
* Route B — DA-A1 UCI-412 basic clinical sixteen fields
  (``da_a1_basic_clinical_v1``), synthetic research benchmark; real-data
  execution blocked pending M3a/D-048 and Gate PT (P-3).
* Route C — DA-A1 UCI-412 clinical + core labs
  (``da_a1_clinical_core_labs_v1``): eligibility/feature contract and synthetic
  test cases only; laboratory admission unverified.
* Route D — DA-A2 Cleveland to locked Hungary transportability
  (``da_a2_hungary_locked_transportability_v1``): contract exposure only; the
  locked validation set is never trained or tuned on.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final, Mapping, Sequence

import numpy as np

from ai.calibration import (
    compute_fold_prediction_dispersion,
    compute_prevalence_shift_diagnostic,
    evaluate_comprehensive_metrics,
)
from ai.errors import CohortGovernanceError
from ai.explainability import explain_clinical_instance
from ai.inference import ResearchCadPredictor, ResearchPredictionResult
from ai.lime_explainability import (
    DEFAULT_LIME_STABILITY_SEEDS,
    LimeConfig,
    build_lime_model_target,
    explain_clinical_instance_lime_certified,
)
from ai.lime_quality import LimeQualityPolicy, require_acceptable_lime_quality
from ai.packaging import (
    VerifiedBundleDescriptor,
    get_or_create_local_signing_key,
    package_research_bundle,
    verify_trusted_local_bundle,
)
from ai.panels import (
    DA_A1_BASIC_CLINICAL_PANEL,
    DA_A1_CLINICAL_CORE_LABS_PANEL,
    DA_A2_RESTING_LABS_PANEL,
    DA_A2_RESTING_PANEL,
    REGISTERED_PANELS,
    ResearchPanelContract,
    validate_cohort_records,
)
from ai.preprocessing import FoldSafeClinicalPreprocessor
from ai.training import (
    EXECUTION_PROFILE_AI1_GENERIC_V1,
    EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1,
    FoldEnsembleMember,
    ResearchTrainingConfig,
    TrainedResearchRun,
    _estimator_input_matrix,
    _positive_proba_and_optional_logit,
    train_research_model,
)

__all__ = [
    "ADMISSIBLE_SYNTHETIC_TEST_ONLY",
    "EVAL_EXTERNAL",
    "EVAL_INTERNAL",
    "EVAL_NOT_AUTHORIZED",
    "EVAL_NOT_EVALUATED",
    "EVAL_SYNTHETIC_TEST",
    "LOCKED_EXTERNAL_TARGET_NEVER_TRAIN",
    "PLANNED_BLOCKED_PENDING_AUTHORIZATION",
    "PROPOSED_TIMING_UNVERIFIED_BLOCKED",
    "ResearchEvaluationContract",
    "ResearchRouteDescriptor",
    "ResearchRouteResult",
    "ResearchScoreDeclaration",
    "RouteEligibilityResult",
    "RouteNotExercisableError",
    "RouteResolutionError",
    "RESEARCH_ROUTE_CATALOG",
    "assert_route_eligible",
    "describe_route_catalog",
    "execute_synthetic_route_exercise",
    "get_route_descriptor",
    "resolve_route",
]

# --------------------------------------------------------------------------- #
# Operation vocabulary                                                        #
# --------------------------------------------------------------------------- #

OP_SYNTHETIC_TRAINING = "synthetic_training"
OP_SYNTHETIC_PREDICTION = "synthetic_prediction"
OP_SYNTHETIC_EXTERNAL_EVALUATION = "synthetic_external_evaluation"
OP_SHAP_ATTRIBUTION = "shap_attribution"
OP_LIME_ASSESSMENT = "lime_assessment"
OP_BUNDLE_PACKAGING = "bundle_packaging"
OP_ROUTE_CONTRACT_QUERY = "route_contract_query"
OP_END_TO_END_EXERCISE = "synthetic_end_to_end_exercise"

OP_REAL_DATA_TRAINING = "real_data_training"
OP_REAL_EXTERNAL_EVALUATION = "real_external_evaluation"
OP_REAL_BUNDLE_INFERENCE = "real_bundle_inference"
OP_CLINICAL_SERVING = "clinical_serving"

KNOWN_OPERATIONS: Final[frozenset[str]] = frozenset(
    {
        OP_SYNTHETIC_TRAINING,
        OP_SYNTHETIC_PREDICTION,
        OP_SYNTHETIC_EXTERNAL_EVALUATION,
        OP_SHAP_ATTRIBUTION,
        OP_LIME_ASSESSMENT,
        OP_BUNDLE_PACKAGING,
        OP_ROUTE_CONTRACT_QUERY,
        OP_END_TO_END_EXERCISE,
        OP_REAL_DATA_TRAINING,
        OP_REAL_EXTERNAL_EVALUATION,
        OP_REAL_BUNDLE_INFERENCE,
        OP_CLINICAL_SERVING,
    }
)

# Operations this synthetic-only orchestration layer can never permit on any
# route. They remain governed by ai.execution / ai.packaging /
# ai.diagnostic_scope and are rejected here fail-closed.
REAL_DATA_OR_CLINICAL_OPERATIONS: Final[frozenset[str]] = frozenset(
    {
        OP_REAL_DATA_TRAINING,
        OP_REAL_EXTERNAL_EVALUATION,
        OP_REAL_BUNDLE_INFERENCE,
        OP_CLINICAL_SERVING,
    }
)

# Declared input sources that are acceptable as the *source* field of a
# synthetic input context for executable synthetic operations. Anything else -
# including patient uploads, clinician records, OCR-derived patient documents,
# wearables, Track B, or real-data strings - fails closed.
SUPPORTED_SYNTHETIC_INPUT_SOURCES: Final[frozenset[str]] = frozenset(
    {"structured_synthetic_research"}
)

# Input sources that are explicitly prohibited as Track A synthetic inputs.
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
        "real_data",
        "real_patient",
    }
)

# Operations that execute synthetic work (training, prediction, artifacts) as
# opposed to read-only metadata inspection (route_contract_query).
EXECUTABLE_SYNTHETIC_OPERATIONS: Final[frozenset[str]] = frozenset(
    {
        OP_SYNTHETIC_TRAINING,
        OP_SYNTHETIC_PREDICTION,
        OP_SYNTHETIC_EXTERNAL_EVALUATION,
        OP_SHAP_ATTRIBUTION,
        OP_LIME_ASSESSMENT,
        OP_BUNDLE_PACKAGING,
        OP_END_TO_END_EXERCISE,
    }
)

# --------------------------------------------------------------------------- #
# Admissibility / authorization / evaluation status vocabulary                #
# --------------------------------------------------------------------------- #

ADMISSIBLE_SYNTHETIC_TEST_ONLY = "ADMISSIBLE_SYNTHETIC_TEST_ONLY"
PLANNED_BLOCKED_PENDING_AUTHORIZATION = "PLANNED_BLOCKED_PENDING_AUTHORIZATION"
PROPOSED_TIMING_UNVERIFIED_BLOCKED = "PROPOSED_PRE_ANGIOGRAPHY_TIMING_UNVERIFIED_BLOCKED"
LOCKED_EXTERNAL_TARGET_NEVER_TRAIN = "LOCKED_EXTERNAL_TARGET_NEVER_TRAIN_ON_LOCKED_SET"

AUTHORIZED_SYNTHETIC_ONLY_REAL_BLOCKED_GATE_PT = (
    "AUTHORIZED_SYNTHETIC_TESTS_ONLY_REAL_DATA_BLOCKED_GATE_PT"
)
ADMITTED_SUBJECT_TO_M3A_AUTHORIZATION = (
    "ADMITTED_FOR_INTERNAL_RESEARCH_SUBJECT_TO_M3A_AUTHORIZATION"
)
PROPOSED_NOT_AUTHORIZED = "PROPOSED_NOT_AUTHORIZED"

EVAL_INTERNAL = "INTERNAL"
EVAL_EXTERNAL = "EXTERNAL"
EVAL_SYNTHETIC_TEST = "SYNTHETIC_TEST"
EVAL_NOT_EVALUATED = "NOT_EVALUATED"
EVAL_NOT_AUTHORIZED = "NOT_AUTHORIZED"

VALID_EVALUATION_STATUSES: Final[frozenset[str]] = frozenset(
    {EVAL_INTERNAL, EVAL_EXTERNAL, EVAL_SYNTHETIC_TEST, EVAL_NOT_EVALUATED, EVAL_NOT_AUTHORIZED}
)

# --------------------------------------------------------------------------- #
# Errors                                                                      #
# --------------------------------------------------------------------------- #


class RouteResolutionError(CohortGovernanceError):
    """Raised when no single permitted route can be resolved for a request."""


class RouteNotExercisableError(CohortGovernanceError):
    """Raised when a route is registered but its synthetic execution is blocked."""


# --------------------------------------------------------------------------- #
# Typed route descriptor                                                      #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class ResearchRouteDescriptor:
    """Immutable, versioned description of one source-specific research route.

    The feature contract itself lives in ``ai.panels.REGISTERED_PANELS``; this
    descriptor references it by ``panel_id`` and re-verifies the contract
    SHA-256. No second schema is introduced.
    """

    route_id: str
    route_version: str
    dataset_id: str
    source_family: str
    panel_id: str
    panel_contract_sha256: str
    #: Declared external cohort target for transportability routes (``None`` for
    #: internal development routes). Used by the resolver to disambiguate routes
    #: that share a development panel/dataset (e.g. Cleveland model -> Hungary).
    declared_external_target: str | None
    target_id: str
    target_definition: str
    prediction_time_admissibility: str
    supported_execution_profiles: tuple[str, ...]
    allowed_model_families: tuple[str, ...]
    research_authorization_status: str
    permitted_operations: frozenset[str]
    forbidden_operations: frozenset[str]
    evaluation_status: str
    evidence_limitations: tuple[str, ...]
    non_equivalence_restrictions: tuple[str, ...]
    non_pooling_restrictions: tuple[str, ...]

    def _descriptor_payload(self) -> dict[str, Any]:
        return {
            "route_id": self.route_id,
            "route_version": self.route_version,
            "dataset_id": self.dataset_id,
            "source_family": self.source_family,
            "panel_id": self.panel_id,
            "panel_contract_sha256": self.panel_contract_sha256,
            "declared_external_target": self.declared_external_target,
            "target_id": self.target_id,
            "target_definition": self.target_definition,
            "prediction_time_admissibility": self.prediction_time_admissibility,
            "supported_execution_profiles": list(self.supported_execution_profiles),
            "allowed_model_families": list(self.allowed_model_families),
            "research_authorization_status": self.research_authorization_status,
            "permitted_operations": sorted(self.permitted_operations),
            "forbidden_operations": sorted(self.forbidden_operations),
            "evaluation_status": self.evaluation_status,
            # Integrity coverage must match what ``to_dict`` reports: the
            # fingerprint binds the evidence limitations, non-equivalence
            # restrictions and non-pooling restrictions so any change to those
            # bound restrictions changes the descriptor SHA-256.
            "evidence_limitations": list(self.evidence_limitations),
            "non_equivalence_restrictions": list(self.non_equivalence_restrictions),
            "non_pooling_restrictions": list(self.non_pooling_restrictions),
        }

    @property
    def descriptor_sha256(self) -> str:
        import hashlib
        import json

        payload = json.dumps(
            self._descriptor_payload(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "route_id": self.route_id,
            "route_version": self.route_version,
            "dataset_id": self.dataset_id,
            "source_family": self.source_family,
            "panel_id": self.panel_id,
            "panel_contract_sha256": self.panel_contract_sha256,
            "declared_external_target": self.declared_external_target,
            "target_id": self.target_id,
            "target_definition": self.target_definition,
            "prediction_time_admissibility": self.prediction_time_admissibility,
            "supported_execution_profiles": list(self.supported_execution_profiles),
            "allowed_model_families": list(self.allowed_model_families),
            "research_authorization_status": self.research_authorization_status,
            "permitted_operations": sorted(self.permitted_operations),
            "forbidden_operations": sorted(self.forbidden_operations),
            "evaluation_status": self.evaluation_status,
            "descriptor_sha256": self.descriptor_sha256,
            "evidence_limitations": list(self.evidence_limitations),
            "non_equivalence_restrictions": list(self.non_equivalence_restrictions),
            "non_pooling_restrictions": list(self.non_pooling_restrictions),
        }


# --------------------------------------------------------------------------- #
# Route catalog                                                               #
# --------------------------------------------------------------------------- #

_COMMON_NON_POOLING: Final[tuple[str, ...]] = (
    "Never pool UCI-412 with UCI-411: they are the same 303 participants and "
    "can never be independent datasets or mutual validation sets.",
    "Never pool Cleveland with Hungary, VA Long Beach, Switzerland or Statlog "
    "without separately approved cross-site harmonization and Gate PT sign-off.",
    "Never select a source or model family because it shows the highest "
    "cross-dataset AUROC; performance ranking is not a route-selection input.",
)

_COMMON_EVIDENCE_LIMITATIONS: Final[tuple[str, ...]] = (
    "Synthetic results are software evidence only: not CAD performance, not "
    "clinical validity, and not an external-validation result.",
    "The exploratory 0.5 cutoff is not a clinically validated decision "
    "threshold; Gate P-4 clinician wording remains pending.",
    "Target construct is cross-sectional angiographic CAD presence in a "
    "referral cohort, never a 30-day or future cardiovascular event horizon.",
)


def _descriptor(
    *,
    route_id: str,
    route_version: str,
    dataset_id: str,
    source_family: str,
    panel_id: str,
    target_id: str,
    target_definition: str,
    prediction_time_admissibility: str,
    supported_execution_profiles: Sequence[str],
    allowed_model_families: Sequence[str],
    research_authorization_status: str,
    permitted_operations: Sequence[str],
    forbidden_operations: Sequence[str] = (),
    evaluation_status: str,
    evidence_limitations: Sequence[str] = (),
    non_equivalence_restrictions: Sequence[str] = (),
    non_pooling_restrictions: Sequence[str] = (),
    declared_external_target: str | None = None,
) -> ResearchRouteDescriptor:
    panel = REGISTERED_PANELS[panel_id]
    return ResearchRouteDescriptor(
        route_id=route_id,
        route_version=route_version,
        dataset_id=dataset_id,
        source_family=source_family,
        panel_id=panel_id,
        panel_contract_sha256=panel.contract_sha256,
        declared_external_target=declared_external_target,
        target_id=target_id,
        target_definition=target_definition,
        prediction_time_admissibility=prediction_time_admissibility,
        supported_execution_profiles=tuple(supported_execution_profiles),
        allowed_model_families=tuple(allowed_model_families),
        research_authorization_status=research_authorization_status,
        permitted_operations=frozenset(permitted_operations),
        forbidden_operations=frozenset(
            list(forbidden_operations) + list(REAL_DATA_OR_CLINICAL_OPERATIONS)
        ),
        evaluation_status=evaluation_status,
        evidence_limitations=tuple(_COMMON_EVIDENCE_LIMITATIONS) + tuple(evidence_limitations),
        non_equivalence_restrictions=tuple(non_equivalence_restrictions),
        non_pooling_restrictions=tuple(_COMMON_NON_POOLING) + tuple(non_pooling_restrictions),
    )


# Route A — DA-A2 Cleveland resting five fields. The accepted real D-047 bundle
# stays frozen at revision A3; this layer only ever exercises synthetic fixtures
# on the matching panel.
DA_A2_RESTING_ROUTE = _descriptor(
    route_id="da_a2_resting_v1",
    route_version="1.0.0",
    dataset_id="DA-A2",
    source_family="UCI-45",
    panel_id="da_a2_resting_v1",
    target_id="t1.uci45.angiographic_cad_gt50.v1",
    target_definition=(
        "Cross-sectional angiographic CAD presence (num in {1,2,3,4} => >50% "
        "luminal diameter narrowing in >=1 major vessel vs 0 => <50%). "
        "UCI-412 uses a >=50% boundary; the two targets are not equivalent."
    ),
    prediction_time_admissibility=ADMISSIBLE_SYNTHETIC_TEST_ONLY,
    supported_execution_profiles=(
        EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1,
        EXECUTION_PROFILE_AI1_GENERIC_V1,
    ),
    allowed_model_families=("l2_logistic_regression", "constrained_random_forest"),
    research_authorization_status=AUTHORIZED_SYNTHETIC_ONLY_REAL_BLOCKED_GATE_PT,
    permitted_operations=[
        OP_SYNTHETIC_TRAINING,
        OP_SYNTHETIC_PREDICTION,
        OP_SYNTHETIC_EXTERNAL_EVALUATION,
        OP_SHAP_ATTRIBUTION,
        OP_LIME_ASSESSMENT,
        OP_BUNDLE_PACKAGING,
        OP_ROUTE_CONTRACT_QUERY,
        OP_END_TO_END_EXERCISE,
    ],
    evaluation_status=EVAL_SYNTHETIC_TEST,
    evidence_limitations=(
        "Five resting fields only: age, sex, cp, trestbps, restecg; no "
        "laboratory biomarkers.",
        "1980s single-center referral care (Cleveland); transport to other eras "
        "or sites is unverified.",
        "The accepted real D-047 bundle is frozen at revision A3 and is never "
        "loaded, retrained or inferred through this synthetic-only layer.",
    ),
    non_equivalence_restrictions=(
        "Not equivalent to da_a1_basic_clinical_v1: different source (UCI-45 vs "
        "UCI-412), feature set, coding and target boundary (>50% vs >=50%). "
        "No input crosswalk exists and none may be inferred here.",
    ),
)

# Route A (planned) — DA-A2 resting + labs seven fields (+ chol, + fbs).
DA_A2_RESTING_LABS_ROUTE = _descriptor(
    route_id="da_a2_resting_labs_v1",
    route_version="1.0.0",
    dataset_id="DA-A2",
    source_family="UCI-45",
    panel_id="da_a2_resting_labs_v1",
    target_id="t1.uci45.angiographic_cad_gt50.v1",
    target_definition=DA_A2_RESTING_ROUTE.target_definition,
    prediction_time_admissibility=PLANNED_BLOCKED_PENDING_AUTHORIZATION,
    supported_execution_profiles=(
        EXECUTION_PROFILE_AI1_GENERIC_V1,
        EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1,
    ),
    allowed_model_families=("l2_logistic_regression", "constrained_random_forest"),
    research_authorization_status=PROPOSED_NOT_AUTHORIZED,
    permitted_operations=[OP_ROUTE_CONTRACT_QUERY],
    evaluation_status=EVAL_NOT_EVALUATED,
    evidence_limitations=(
        "Planned chol + fbs extension; execution blocked until independently "
        "authorized. No real-data fitting or evaluation occurs in this layer.",
        "Cross-site lab availability is restrictive (e.g. 0/123 usable chol in "
        "Switzerland); staged missingness handling is unverified for real runs.",
    ),
)

# Route B — DA-A1 UCI-412 basic clinical sixteen fields.
DA_A1_BASIC_CLINICAL_ROUTE = _descriptor(
    route_id="da_a1_basic_clinical_v1",
    route_version="1.1.0",
    dataset_id="DA-A1",
    source_family="UCI-412",
    panel_id="da_a1_basic_clinical_v1",
    target_id="t1.uci412.angiographic_cad_ge50.v1",
    target_definition=(
        "Cross-sectional angiographic CAD presence (Cath='Cad' => >=50% "
        "diameter narrowing in >=1 major coronary artery vs 'Normal'). "
        "UCI-45 uses a >50% boundary; the two targets are not equivalent."
    ),
    prediction_time_admissibility=ADMISSIBLE_SYNTHETIC_TEST_ONLY,
    supported_execution_profiles=(EXECUTION_PROFILE_AI1_GENERIC_V1,),
    allowed_model_families=("l2_logistic_regression", "constrained_random_forest"),
    research_authorization_status=ADMITTED_SUBJECT_TO_M3A_AUTHORIZATION,
    permitted_operations=[
        OP_SYNTHETIC_TRAINING,
        OP_SYNTHETIC_PREDICTION,
        OP_SYNTHETIC_EXTERNAL_EVALUATION,
        OP_SHAP_ATTRIBUTION,
        OP_LIME_ASSESSMENT,
        OP_BUNDLE_PACKAGING,
        OP_ROUTE_CONTRACT_QUERY,
        OP_END_TO_END_EXERCISE,
    ],
    evaluation_status=EVAL_SYNTHETIC_TEST,
    evidence_limitations=(
        "Real-data execution remains blocked: M3a/D-048 is not authorized and "
        "Gate PT (P-3) is closed; this layer only runs synthetic fixtures.",
        "UCI-412 and UCI-411 are the same 303 participants (Z-Alizadeh Sani); "
        "never independent.",
    ),
    non_equivalence_restrictions=(
        "Not equivalent to da_a2_resting_v1: different source, panel and target "
        "boundary (>=50% vs >50%). A UCI-412 input is never translated into a "
        "Cleveland schema in this layer.",
    ),
)

# Route C — DA-A1 UCI-412 clinical + core labs (proposed, labs timing unverified).
DA_A1_CLINICAL_CORE_LABS_ROUTE = _descriptor(
    route_id="da_a1_clinical_core_labs_v1",
    route_version="1.1.0",
    dataset_id="DA-A1",
    source_family="UCI-412",
    panel_id="da_a1_clinical_core_labs_v1",
    target_id="t1.uci412.angiographic_cad_ge50.v1",
    target_definition=DA_A1_BASIC_CLINICAL_ROUTE.target_definition,
    prediction_time_admissibility=PROPOSED_TIMING_UNVERIFIED_BLOCKED,
    supported_execution_profiles=(EXECUTION_PROFILE_AI1_GENERIC_V1,),
    allowed_model_families=("l2_logistic_regression",),
    research_authorization_status=PROPOSED_NOT_AUTHORIZED,
    permitted_operations=[OP_ROUTE_CONTRACT_QUERY],
    evaluation_status=EVAL_NOT_EVALUATED,
    evidence_limitations=(
        "Laboratory fields FBS, CR, TG, LDL, HDL, HB, WBC are proposed only: "
        "pre-angiography availability and admissibility are unverified. They are "
        "not admitted to real clinical inference or real-data fitting.",
        "Synthetic test cases and the eligibility/feature contract exist here; "
        "no synthetic training exercise is offered for this route until timing "
        "is resolved at Gate PT.",
    ),
)

# Route D — DA-A2 Cleveland to locked Hungary transportability.
DA_A2_HUNGARY_LOCKED_ROUTE = _descriptor(
    route_id="da_a2_hungary_locked_transportability_v1",
    route_version="1.0.0",
    dataset_id="DA-A2",
    source_family="UCI-45",
    panel_id="da_a2_resting_v1",
    target_id="t1.uci45.angiographic_cad_gt50.v1",
    target_definition=(
        "Cleveland (DA-A2) resting model transported one-shot to the locked "
        "Hungary target site (UCI-45 Hungary, num >50%)."
    ),
    prediction_time_admissibility=LOCKED_EXTERNAL_TARGET_NEVER_TRAIN,
    supported_execution_profiles=(EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1,),
    allowed_model_families=("l2_logistic_regression",),
    research_authorization_status=PROPOSED_NOT_AUTHORIZED,
    permitted_operations=[OP_ROUTE_CONTRACT_QUERY],
    declared_external_target="Hungary_locked",
    evaluation_status=EVAL_NOT_AUTHORIZED,
    evidence_limitations=(
        "Hungary is a locked external target site: never trained or tuned on. "
        "One-shot locked evaluation requires Gate PT (P-3) plus separately "
        "approved dataset/ledger authorization.",
        "Cleveland -> Hungary transport crosses a prevalence shift (~45.9% -> "
        "~36.1% descriptive) and era/referral differences; calibration-in-the-"
        "large is unverified until executed.",
    ),
    non_pooling_restrictions=(
        "Hungary evaluation must not feed Cleveland feature selection, "
        "missingness-rule tuning, model-family choice or threshold tuning.",
    ),
)

_ALL_ROUTES: Final[tuple[ResearchRouteDescriptor, ...]] = (
    DA_A2_RESTING_ROUTE,
    DA_A2_RESTING_LABS_ROUTE,
    DA_A1_BASIC_CLINICAL_ROUTE,
    DA_A1_CLINICAL_CORE_LABS_ROUTE,
    DA_A2_HUNGARY_LOCKED_ROUTE,
)

#: Immutable, versioned research route catalog. Bound to
#: ``ai.panels.REGISTERED_PANELS``; no conflicting feature schema is introduced.
RESEARCH_ROUTE_CATALOG: Final[Mapping[str, ResearchRouteDescriptor]] = MappingProxyType(
    {route.route_id: route for route in _ALL_ROUTES}
)

# Fail closed at import time if a registered route drifts out of sync with the
# panel registry (contract hash or panel membership).
for _route in _ALL_ROUTES:
    if _route.panel_id not in REGISTERED_PANELS:
        raise RouteResolutionError(
            "route_panel_not_registered",
            f"Route '{_route.route_id}' references unregistered panel "
            f"'{_route.panel_id}'.",
        )
    if _route.panel_contract_sha256 != REGISTERED_PANELS[_route.panel_id].contract_sha256:
        raise RouteResolutionError(
            "route_panel_contract_hash_mismatch",
            f"Route '{_route.route_id}' panel contract hash does not match the "
            f"registered panel contract.",
        )
    if _route.evaluation_status not in VALID_EVALUATION_STATUSES:
        raise RouteResolutionError(
            "invalid_route_evaluation_status",
            f"Route '{_route.route_id}' has invalid evaluation status "
            f"'{_route.evaluation_status}'.",
        )


def get_route_descriptor(route_id: str) -> ResearchRouteDescriptor:
    """Return the registered route descriptor or fail closed."""
    if not isinstance(route_id, str) or route_id not in RESEARCH_ROUTE_CATALOG:
        raise RouteResolutionError(
            "unknown_route_id",
            f"Unknown research route id '{route_id}'.",
        )
    return RESEARCH_ROUTE_CATALOG[route_id]


def describe_route_catalog() -> dict[str, Any]:
    """Machine-readable catalog summary (descriptors without runtime state)."""
    return {
        "catalog_schema": "cardioassist.ai.research_routes/v1",
        "route_count": len(RESEARCH_ROUTE_CATALOG),
        "routes": {rid: route.to_dict() for rid, route in RESEARCH_ROUTE_CATALOG.items()},
    }


# --------------------------------------------------------------------------- #
# Route eligibility result                                                    #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class RouteEligibilityResult:
    """Outcome of resolving one (source, panel, operation, input context) request."""

    eligible: bool
    decision: str  # "ROUTE_RESOLVED" or "ROUTE_REJECTED"
    route: ResearchRouteDescriptor | None
    route_id: str | None
    operation: str
    rejections: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "eligible": self.eligible,
            "decision": self.decision,
            "route_id": self.route_id,
            "operation": self.operation,
            "rejections": list(self.rejections),
        }


def _context_track_source(
    declared_input_context: Mapping[str, Any] | None,
) -> tuple[Any, Any]:
    context = dict(declared_input_context or {})
    return context.get("track"), context.get("source")


def _validate_synthetic_input_context(
    *,
    declared_input_context: Mapping[str, Any] | None,
    operation: str,
) -> tuple[str, ...]:
    """Return rejection codes for a declared synthetic input context.

    Fail-closed semantics: missing, malformed, contradictory or ambiguous
    context is rejected. Real data, patient uploads, clinician records,
    OCR-derived patient documents, wearables and Track B are never executable
    synthetic inputs. The resolver does not trust a caller-controlled
    ``real_data=False`` or a source string alone as proof that the underlying
    patient data is synthetic.
    """
    rejections: list[str] = []

    if declared_input_context is None or not isinstance(declared_input_context, Mapping):
        return ("missing_input_context",)

    context = dict(declared_input_context)
    track = context.get("track")
    source = context.get("source")
    synthetic = context.get("synthetic")
    real_data = context.get("real_data")

    if operation in EXECUTABLE_SYNTHETIC_OPERATIONS:
        # Executable operations require an explicit, strictly validated
        # synthetic context.
        if track != "A":
            rejections.append("track_not_a")
        if source not in SUPPORTED_SYNTHETIC_INPUT_SOURCES:
            rejections.append("unsupported_input_source")
        if synthetic is not True:
            rejections.append("synthetic_declaration_missing_or_false")
        if real_data is True:
            rejections.append("real_data_input_context_rejected")
    else:
        # route_contract_query is metadata-only inspection: it may inspect
        # registered routes but must never authorize an executable operation.
        # Still reject clearly hostile contexts.
        if track not in (None, "A"):
            rejections.append("track_not_a")
        if source in PROHIBITED_INPUT_SOURCES:
            rejections.append("prohibited_input_source")
        if real_data is True:
            rejections.append("real_data_input_context_rejected")

    return tuple(rejections)


def resolve_route(
    *,
    dataset_id: str,
    panel_id: str,
    operation: str,
    source_family: str | None = None,
    declared_input_context: Mapping[str, Any] | None = None,
) -> RouteEligibilityResult:
    """Resolve the single permitted route for a research request.

    Fail-closed semantics: unknown datasets, unknown panels, mismatched
    dataset/panel/source combinations, unknown or ambiguous operations,
    Track-B/wearable inputs, real-data or clinical-serving operations, and any
    route-authorization mismatch all produce ``eligible=False`` with a machine
    readable rejection code. The resolver never approves an operation the
    underlying pipeline would reject and never ranks routes by performance.
    """
    rejections: list[str] = []

    if not isinstance(dataset_id, str) or not dataset_id:
        rejections.append("invalid_dataset_id")
    if not isinstance(panel_id, str) or not panel_id:
        rejections.append("invalid_panel_id")
    if not isinstance(operation, str) or not operation:
        rejections.append("invalid_operation")
    elif operation not in KNOWN_OPERATIONS:
        rejections.append("unknown_operation")

    if rejections:
        return RouteEligibilityResult(
            eligible=False,
            decision="ROUTE_REJECTED",
            route=None,
            route_id=None,
            operation=str(operation) if isinstance(operation, str) else "",
            rejections=tuple(rejections),
        )

    # Exact dataset + panel match. No cross-dataset harmonization or schema
    # translation is performed here.
    candidates = [
        route
        for route in RESEARCH_ROUTE_CATALOG.values()
        if route.dataset_id == dataset_id and route.panel_id == panel_id
    ]

    if source_family is not None:
        candidates = [
            route for route in candidates if route.source_family == source_family
        ]

    context = dict(declared_input_context or {})
    declared_external_target = (
        context.get("external_cohort_id")
        if context.get("external_cohort_id") is not None
        else context.get("declared_external_target")
    )
    if declared_external_target is not None:
        candidates = [
            route
            for route in candidates
            if route.declared_external_target == declared_external_target
        ]
    else:
        candidates = [
            route for route in candidates if route.declared_external_target is None
        ]

    if not candidates:
        return RouteEligibilityResult(
            eligible=False,
            decision="ROUTE_REJECTED",
            route=None,
            route_id=None,
            operation=operation,
            rejections=(
                "no_matching_route",
                "No registered source-specific route matches the declared "
                "dataset, panel and input context.",
            ),
        )
    if len(candidates) > 1:
        return RouteEligibilityResult(
            eligible=False,
            decision="ROUTE_REJECTED",
            route=None,
            route_id=None,
            operation=operation,
            rejections=(
                "ambiguous_route",
                "Multiple routes match the request; the resolver refuses to "
                "guess. Disambiguate via declared_input_context.",
            ),
        )

    route = candidates[0]

    # Contract binding integrity: the route's pinned panel hash must agree with
    # the live panel registry (defensive; enforced at catalog build too).
    if (
        REGISTERED_PANELS[route.panel_id].contract_sha256
        != route.panel_contract_sha256
    ):
        return RouteEligibilityResult(
            eligible=False,
            decision="ROUTE_REJECTED",
            route=route,
            route_id=route.route_id,
            operation=operation,
            rejections=(
                "panel_contract_hash_mismatch",
                "Route panel contract hash no longer matches the registered "
                "panel contract.",
            ),
        )

    if operation in route.forbidden_operations:
        return RouteEligibilityResult(
            eligible=False,
            decision="ROUTE_REJECTED",
            route=route,
            route_id=route.route_id,
            operation=operation,
            rejections=(
                "operation_forbidden_for_route",
                f"Operation '{operation}' is forbidden for route "
                f"'{route.route_id}'.",
            ),
        )
    if operation not in route.permitted_operations:
        return RouteEligibilityResult(
            eligible=False,
            decision="ROUTE_REJECTED",
            route=route,
            route_id=route.route_id,
            operation=operation,
            rejections=(
                "operation_not_permitted_for_route",
                f"Operation '{operation}' is not permitted for route "
                f"'{route.route_id}'.",
            ),
        )

    # Fail-closed back-door guard: this synthetic-only layer never authorizes
    # real-data or clinical-serving operations on any route, even if a future
    # route descriptor were to list them.
    if operation in REAL_DATA_OR_CLINICAL_OPERATIONS:
        return RouteEligibilityResult(
            eligible=False,
            decision="ROUTE_REJECTED",
            route=route,
            route_id=route.route_id,
            operation=operation,
            rejections=(
                "real_data_or_clinical_operation_not_authorized_by_route_layer",
                f"Operation '{operation}' is not authorized by the synthetic-only "
                f"route layer for route '{route.route_id}'.",
            ),
        )

    track, source = _context_track_source(context)

    # Strict synthetic input context validation: missing, malformed,
    # contradictory or ambiguous context fails closed.
    context_rejections = _validate_synthetic_input_context(
        declared_input_context=declared_input_context,
        operation=operation,
    )
    if context_rejections:
        return RouteEligibilityResult(
            eligible=False,
            decision="ROUTE_REJECTED",
            route=route,
            route_id=route.route_id,
            operation=operation,
            rejections=context_rejections,
        )

    return RouteEligibilityResult(
        eligible=True,
        decision="ROUTE_RESOLVED",
        route=route,
        route_id=route.route_id,
        operation=operation,
        rejections=(),
    )


def assert_route_eligible(
    *,
    dataset_id: str,
    panel_id: str,
    operation: str,
    source_family: str | None = None,
    declared_input_context: Mapping[str, Any] | None = None,
) -> ResearchRouteDescriptor:
    """Resolve a route and raise :class:`RouteResolutionError` on rejection."""
    result = resolve_route(
        dataset_id=dataset_id,
        panel_id=panel_id,
        operation=operation,
        source_family=source_family,
        declared_input_context=declared_input_context,
    )
    if not result.eligible:
        raise RouteResolutionError(
            "route_not_eligible",
            f"Route resolution rejected: {'; '.join(result.rejections)}",
        )
    assert result.route is not None
    return result.route


# --------------------------------------------------------------------------- #
# Synthetic cohort builders (deterministic fixtures only)                     #
# --------------------------------------------------------------------------- #

_UCI45_RESTING_UNITS: Final[Mapping[str, str]] = {"age": "years", "trestbps": "mmHg"}
_UCI412_BASIC_UNITS: Final[Mapping[str, str]] = {
    "Age": "years",
    "BMI": "kg/m^2",
    "BP": "mmHg",
    "PR": "beats/min",
}


def _logit(probability: float) -> float:
    p = min(max(float(probability), 1e-6), 1.0 - 1e-6)
    return float(np.log(p) - np.log1p(-p))


def _sigmoid(value: float) -> float:
    return float(1.0 / (1.0 + np.exp(-float(value))))


def _ensure_binary_labels(labels: Sequence[int]) -> list[int]:
    out = list(int(v) for v in labels)
    if len(set(out)) < 2:
        out[0] = 0
        out[1] = 1
    return out


def _synthetic_envelope(
    *,
    panel_id: str,
    features: Mapping[str, Any],
    units: Mapping[str, str],
    missing_reasons: Mapping[str, str],
    source: str = "structured_synthetic_research",
) -> dict[str, Any]:
    return {
        "synthetic": True,
        "panel_id": panel_id,
        "features": dict(features),
        "units": dict(units),
        "missing_reasons": dict(missing_reasons),
        "context": {"track": "A", "source": source},
    }


def build_synthetic_uci45_resting_cohort(
    n_rows: int, *, seed: int, label_prevalence_hint: float = 0.46
) -> tuple[list[dict[str, Any]], list[int]]:
    """Deterministic synthetic cohort for the da_a2_resting_v1 panel.

    All five resting fields are supplied (trestbps/restecg are optional in the
    staged contract but required here so the exercised panel is complete).
    """
    rng = np.random.default_rng(int(seed))
    records: list[dict[str, Any]] = []
    labels: list[int] = []
    for idx in range(int(n_rows)):
        age = float(rng.integers(40, 80))
        sex = int(rng.integers(0, 2))
        cp = int(rng.integers(1, 5))
        trestbps = float(rng.integers(90, 200))
        restecg = int(rng.integers(0, 3))
        latent = (
            0.04 * (age - 55.0)
            + (0.55 if sex == 1 else -0.30)
            + (0.85 if cp >= 3 else -0.20)
            + 0.01 * (trestbps - 130.0)
            + (0.40 if restecg >= 1 else 0.0)
            + float(rng.normal(0.0, 0.8))
        )
        y = int(rng.random() < _sigmoid(latent))
        records.append(
            _synthetic_envelope(
                panel_id="da_a2_resting_v1",
                features={
                    "age": age,
                    "sex": sex,
                    "cp": cp,
                    "trestbps": trestbps,
                    "restecg": restecg,
                },
                units=_UCI45_RESTING_UNITS,
                missing_reasons={},
            )
        )
        labels.append(y)
    return records, _ensure_binary_labels(labels)


def build_synthetic_uci412_basic_clinical_cohort(
    n_rows: int, *, seed: int
) -> tuple[list[dict[str, Any]], list[int]]:
    """Deterministic synthetic cohort for the da_a1_basic_clinical_v1 panel.

    All 16 basic clinical columns are supplied; none are optional in this
    panel, so no missing-reason entries are needed.
    """
    rng = np.random.default_rng(int(seed))
    records: list[dict[str, Any]] = []
    labels: list[int] = []
    for idx in range(int(n_rows)):
        age = float(rng.integers(35, 85))
        sex = int(rng.integers(0, 2))
        bmi = float(rng.uniform(18.0, 40.0))
        dm = int(rng.integers(0, 2))
        htn = int(rng.integers(0, 2))
        smoker = int(rng.integers(0, 2))
        ex_smoker = int(rng.integers(0, 2))
        fh = int(rng.integers(0, 2))
        dlp = int(rng.integers(0, 2))
        bp = float(rng.integers(85, 200))
        pr = float(rng.integers(55, 110))
        typical = int(rng.integers(0, 2))
        atypical = int(rng.integers(0, 2))
        nonanginal = int(rng.integers(0, 2))
        exertional = int(rng.integers(0, 2))
        dyspnea = int(rng.integers(0, 2))
        latent = (
            0.035 * (age - 55.0)
            + (0.5 if sex == 1 else -0.25)
            + 0.03 * (bmi - 27.0)
            + (0.7 if dm == 1 else 0.0)
            + (0.6 if htn == 1 else 0.0)
            + (0.5 if smoker == 1 else 0.0)
            + (0.3 if fh == 1 else 0.0)
            + (0.4 if dlp == 1 else 0.0)
            + 0.01 * (bp - 130.0)
            + (0.6 if typical == 1 else 0.0)
            + float(rng.normal(0.0, 0.9))
        )
        y = int(rng.random() < _sigmoid(latent))
        records.append(
            _synthetic_envelope(
                panel_id="da_a1_basic_clinical_v1",
                features={
                    "Age": age,
                    "Sex": sex,
                    "BMI": bmi,
                    "DM": dm,
                    "HTN": htn,
                    "Current Smoker": smoker,
                    "EX-Smoker": ex_smoker,
                    "FH": fh,
                    "DLP": dlp,
                    "BP": bp,
                    "PR": pr,
                    "Typical Chest Pain": typical,
                    "Atypical": atypical,
                    "Nonanginal": nonanginal,
                    "Exertional CP": exertional,
                    "Dyspnea": dyspnea,
                },
                units=_UCI412_BASIC_UNITS,
                missing_reasons={},
            )
        )
        labels.append(y)
    return records, _ensure_binary_labels(labels)


def build_synthetic_cohort_for_route(
    route: ResearchRouteDescriptor, *, n_rows: int, seed: int
) -> tuple[list[dict[str, Any]], list[int]]:
    """Build a deterministic synthetic cohort aligned to ``route.panel_id``."""
    if route.panel_id == "da_a2_resting_v1":
        return build_synthetic_uci45_resting_cohort(
            n_rows, seed=seed, label_prevalence_hint=0.46
        )
    if route.panel_id == "da_a1_basic_clinical_v1":
        return build_synthetic_uci412_basic_clinical_cohort(n_rows, seed=seed)
    raise RouteNotExercisableError(
        "route_synthetic_cohort_not_implemented",
        f"No deterministic synthetic cohort builder is registered for route "
        f"'{route.route_id}' (panel '{route.panel_id}').",
    )


# --------------------------------------------------------------------------- #
# Typed research output contracts                                             #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class ResearchScoreDeclaration:
    """One prediction's raw vs calibrated scores with explicit mathematical scales.

    A single calibrated_research_score is a research output on a development
    cohort; it is NOT a clinically validated individual CAD risk and must never
    be confused with dataset-level Accuracy.
    """

    raw_model_score: float
    raw_model_log_odds: float | None
    calibrated_research_score: float
    calibrated_log_odds: float
    score_scale_declaration: str
    exploratory_threshold: float
    exploratory_above_threshold: bool
    threshold_clinically_validated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_model_score": self.raw_model_score,
            "raw_model_log_odds": self.raw_model_log_odds,
            "calibrated_research_score": self.calibrated_research_score,
            "calibrated_log_odds": self.calibrated_log_odds,
            "score_scale_declaration": self.score_scale_declaration,
            "exploratory_threshold": self.exploratory_threshold,
            "exploratory_above_threshold": self.exploratory_above_threshold,
            "exploratory_threshold_clinically_validated": (
                self.threshold_clinically_validated
            ),
            "interpretation": "RESEARCH_ONLY_NOT_INDIVIDUAL_CLINICAL_CAD_RISK",
        }


@dataclass(frozen=True, slots=True)
class ResearchEvaluationContract:
    """Machine-readable evaluation contract for one route exercise.

    Distinguishes prediction-score output (per-instance declaration) from
    dataset-level accuracy and reports metrics together with their estimation
    method, prevalence, threshold semantics and status.
    """

    evaluation_status: str
    dataset_id: str
    panel_id: str
    panel_contract_sha256: str
    model_id: str
    model_version: str
    protocol_id: str
    outcome_definition: str
    evaluation_population: str
    development_prevalence: float
    evaluation_prevalence: float
    exploratory_threshold: float
    threshold_clinically_approved: bool
    metrics: Mapping[str, Any]
    calibration_report: Mapping[str, Any]
    fold_dispersion: Mapping[str, Any]
    shap_report: Mapping[str, Any]
    lime_report: Mapping[str, Any]
    confidence_interval_method: str | None
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluation_status": self.evaluation_status,
            "dataset_id": self.dataset_id,
            "panel_id": self.panel_id,
            "panel_contract_sha256": self.panel_contract_sha256,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "protocol_id": self.protocol_id,
            "outcome_definition": self.outcome_definition,
            "evaluation_population": self.evaluation_population,
            "development_prevalence": self.development_prevalence,
            "evaluation_prevalence": self.evaluation_prevalence,
            "exploratory_threshold": self.exploratory_threshold,
            "threshold_clinically_approved": self.threshold_clinically_approved,
            "metrics": dict(self.metrics),
            "calibration_report": dict(self.calibration_report),
            "fold_dispersion": dict(self.fold_dispersion),
            "shap_report": dict(self.shap_report),
            "lime_report": dict(self.lime_report),
            "confidence_interval_method": self.confidence_interval_method,
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True, slots=True)
class ResearchRouteResult:
    """Complete output of one synthetic route exercise.

    Separates route resolution from training, artifact loading and inference
    authorization: none of those steps is skipped or merged.
    """

    route: ResearchRouteDescriptor
    eligibility: RouteEligibilityResult
    exercise_id: str
    seed: int
    development_cohort_id: str
    development_dataset_id: str
    score_declaration: ResearchScoreDeclaration
    evaluation_contract: ResearchEvaluationContract
    shap_explanation: Any | None  # FaithfulShapExplanation (typed at runtime)
    lime_explanation: Any | None  # FaithfulLimeExplanation
    lime_stability: Any | None  # LimeStabilityReport
    bundle_round_trip: dict[str, Any] | None
    limitations: tuple[str, ...]

    @staticmethod
    def _strip_timing(node: Any) -> Any:
        """Recursively remove wall-clock timing keys so identical seeds reproduce identical payloads."""
        if isinstance(node, dict):
            return {
                key: ResearchRouteResult._strip_timing(value)
                for key, value in node.items()
                if key not in ("runtime_seconds", "runtime")
            }
        if isinstance(node, list):
            return [ResearchRouteResult._strip_timing(item) for item in node]
        return node

    def _deterministic_payload(self) -> dict[str, Any]:
        payload = {
            "route_id": self.route.route_id,
            "route_version": self.route.route_version,
            "dataset_id": self.route.dataset_id,
            "source_family": self.route.source_family,
            "panel_id": self.route.panel_id,
            "exercise_id": self.exercise_id,
            "seed": self.seed,
            "score_declaration": self.score_declaration.to_dict(),
            "evaluation_contract": self.evaluation_contract.to_dict(),
            "bundle_round_trip": self.bundle_round_trip,
            "limitations": list(self.limitations),
        }
        if self.shap_explanation is not None:
            payload["shap_explanation"] = self.shap_explanation.to_dict()
        if self.lime_explanation is not None:
            payload["lime_explanation"] = self.lime_explanation.to_dict()
            if self.lime_stability is not None:
                payload["lime_stability"] = self.lime_stability.to_dict()
        return self._strip_timing(payload)

    @property
    def deterministic_sha256(self) -> str:
        import hashlib
        import json

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
            "route": self.route.to_dict(),
            "eligibility": self.eligibility.to_dict(),
            "exercise_id": self.exercise_id,
            "seed": self.seed,
            "development_cohort_id": self.development_cohort_id,
            "development_dataset_id": self.development_dataset_id,
            "score_declaration": self.score_declaration.to_dict(),
            "evaluation_contract": self.evaluation_contract.to_dict(),
            "shap_explanation": (
                None if self.shap_explanation is None else self.shap_explanation.to_dict()
            ),
            "lime_explanation": (
                None if self.lime_explanation is None else self.lime_explanation.to_dict()
            ),
            "lime_stability": (
                None if self.lime_stability is None else self.lime_stability.to_dict()
            ),
            "bundle_round_trip": self.bundle_round_trip,
            "limitations": list(self.limitations),
            "deterministic_sha256": self.deterministic_sha256,
        }


# --------------------------------------------------------------------------- #
# Synthetic route orchestrator                                                #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class SyntheticRouteExerciseConfig:
    """Configuration for one deterministic synthetic route exercise."""

    n_development: int = 160
    n_test: int = 80
    seed: int = 20261027
    outer_folds: int = 3
    inner_folds: int = 2
    repeat_seeds: tuple[int, ...] = (20261025,)
    bootstrap_resamples: int = 150
    shap_max_background_samples: int = 32
    lime_num_perturbations: int = 256
    exploratory_threshold: float = 0.5
    shuffle_max_allowed_auroc: float = 0.68
    include_bundle_round_trip: bool = False
    work_root: Path | None = None

    def __post_init__(self) -> None:
        if self.n_development < 4 or self.n_test < 4:
            raise ValueError("n_development and n_test must be >= 4.")
        if self.exploratory_threshold <= 0.0 or self.exploratory_threshold >= 1.0:
            raise ValueError("exploratory_threshold must lie in (0, 1).")
        if not (0.5 <= self.shuffle_max_allowed_auroc <= 1.0):
            raise ValueError("shuffle_max_allowed_auroc must lie in [0.5, 1].")


def _training_config_for_route(
    route: ResearchRouteDescriptor, config: SyntheticRouteExerciseConfig
) -> ResearchTrainingConfig:
    # Both synthetic exercises use the registered generic AI-1 profile. The
    # Cleveland D-047 frozen profile (with its projected forest input space)
    # remains registered on the route descriptor and is exercised by the
    # separate frozen D-047 test path; this synthetic-only layer does not need
    # the projection machinery to demonstrate the route contract.
    execution_profile = EXECUTION_PROFILE_AI1_GENERIC_V1
    return ResearchTrainingConfig(
        protocol_id=f"CAI-AI7-SYNTHETIC-{route.route_id.upper()}-V1",
        model_version="0.1.0",
        outer_folds=config.outer_folds,
        inner_folds=config.inner_folds,
        repeat_seeds=config.repeat_seeds,
        shuffle_control_seeds=(20261101,),
        shuffle_max_allowed_auroc=config.shuffle_max_allowed_auroc,
        lr_c_grid=(0.01, 0.1, 1.0, 10.0),
        rf_max_depths=(2, 3, 4),
        rf_min_samples_leaf=(5, 10),
        rf_n_estimators=40,
        bootstrap_resamples=config.bootstrap_resamples,
        shap_max_background_samples=config.shap_max_background_samples,
        exploratory_threshold=config.exploratory_threshold,
        execution_profile=execution_profile,
    )


def _predict_on_matrix(
    run: TrainedResearchRun,
    X: np.ndarray,
) -> tuple[np.ndarray, np.ndarray | None, np.ndarray]:
    """Raw probabilities, raw log-odds (when available) and calibrated scores."""
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


def _run_bundle_round_trip(
    run: TrainedResearchRun,
    work_root: Path,
    route_id: str,
    sample_payload: Mapping[str, Any],
    panel: ResearchPanelContract,
) -> dict[str, Any]:
    """Package, verify, load and predict through the trusted-local bundle path.

    This exercises artifact loading and inference authorization on a strictly
    synthetic bundle. It never touches the accepted real Cleveland bundle and
    never engages ai.diagnostic_scope (which is frozen at A3).
    """
    trusted_root = Path(work_root) / "trusted_bundles"
    key_dir = Path(work_root) / "private_keys"
    trusted_root.mkdir(parents=True, exist_ok=True)
    key_dir.mkdir(parents=True, exist_ok=True)
    signing_key = get_or_create_local_signing_key(key_dir / "local_bundle_hmac_v1.key")

    bundle_dir = trusted_root / f"synthetic_research_bundle_{route_id}"
    packaged: VerifiedBundleDescriptor = package_research_bundle(
        run, bundle_dir, signing_key=signing_key
    )
    trusted: VerifiedBundleDescriptor = verify_trusted_local_bundle(
        bundle_dir, trusted_local_root=trusted_root, signing_key=signing_key
    )
    predictor = ResearchCadPredictor.from_verified_bundle(
        bundle_dir,
        trusted_local_root=trusted_root,
        signing_key=signing_key,
    )
    # A prediction through the loaded predictor proves inference authorization
    # boundaries (RESEARCH_ONLY, not approved for serving) end-to-end.
    pred: ResearchPredictionResult = predictor.predict_research_only(sample_payload)
    return {
        "packaged_serving_eligibility": packaged.serving_eligibility,
        "packaged_approved_for_serving": packaged.approved_for_serving,
        "producer_authenticated": trusted.producer_authenticated,
        "safe_for_pickle_deserialization": trusted.safe_for_pickle_deserialization,
        "predictor_model_id": predictor.model_id,
        "predictor_model_version": predictor.model_version,
        "predictor_model_family": predictor.model_family,
        "predictor_execution_profile": predictor.execution_profile,
        "predictor_protocol_id": predictor.protocol_id,
        "predictor_panel_id": predictor.panel.panel_id,
        "prediction_serving_eligibility": pred.serving_eligibility,
        "prediction_approved_for_serving": pred.approved_for_serving,
        "prediction_clinical_use_authorized": pred.clinical_use_authorized,
        "prediction_calibrated_research_score": float(pred.calibrated_research_score),
        "artifact_hashes": dict(trusted.verified_files),
    }


def _fold_member_prediction_for_instance(
    run: TrainedResearchRun,
    member: FoldEnsembleMember,
    X_instance_raw: np.ndarray,
    execution_profile: str,
) -> tuple[float, float]:
    """Raw + calibrated prediction for ONE fixed instance from ONE fold member.

    Uses the fold member's own preprocessor, estimator and inner-OOF-fitted
    calibrator, so the resulting spread reflects outer-fold model variation
    (different fold preprocessors/families/calibrators on the SAME instance)
    rather than between-record variation on a single final refit model.

    This honors the contract of ``compute_fold_prediction_dispersion``: each
    outer-fold model's raw score is calibrated only by that same fold's
    inner-OOF-fitted calibrator.
    """
    z_member = member.preprocessor.transform(X_instance_raw)
    E_member = _estimator_input_matrix(
        member.model_family,
        member.preprocessor,
        X_instance_raw,
        z_member,
        execution_profile,
    )
    raw, raw_logit = _positive_proba_and_optional_logit(
        member.model_family, member.estimator, E_member
    )
    cal = member.calibrator.calibrate(raw, raw_logits=raw_logit)
    return float(raw[0]), float(cal[0])


def execute_synthetic_route_exercise(
    route_id: str,
    *,
    config: SyntheticRouteExerciseConfig | None = None,
) -> ResearchRouteResult:
    """Execute one deterministic synthetic end-to-end route exercise.

    Steps: route resolution -> synthetic cohort construction -> contract
    validation -> fold-safe preprocessing -> nested-CV training + cross-fitted
    calibration -> synthetic test prediction -> SHAP -> LIME -> typed research
    output contract. Optionally a trusted-local bundle round-trip.

    Real-data training, real external evaluation, real-bundle inference and
    clinical serving are never executed by this function.
    """
    config = config or SyntheticRouteExerciseConfig()
    # Unknown route id fails closed first.
    route = get_route_descriptor(route_id)
    # Contract-only or blocked routes are not exercisable here, before any
    # context resolution can run.
    if OP_END_TO_END_EXERCISE not in route.permitted_operations:
        raise RouteNotExercisableError(
            "route_end_to_end_exercise_not_permitted",
            f"Route '{route.route_id}' is registered but its synthetic end-to-end "
            "exercise is not permitted (execution blocked or contract-only).",
        )
    # Full eligibility resolution (dataset/panel/context/operation checks).
    route = assert_route_eligible(
        dataset_id=route.dataset_id,
        panel_id=route.panel_id,
        operation=OP_END_TO_END_EXERCISE,
        source_family=route.source_family,
        declared_input_context={
            "track": "A",
            "source": "structured_synthetic_research",
            "synthetic": True,
        },
    )

    dev_records, dev_labels = build_synthetic_cohort_for_route(
        route, n_rows=config.n_development, seed=config.seed
    )
    test_records, test_labels = build_synthetic_cohort_for_route(
        route, n_rows=config.n_test, seed=config.seed + 1
    )

    panel = REGISTERED_PANELS[route.panel_id]

    X_dev, y_dev, _ = validate_cohort_records(
        dev_records, dev_labels, panel, require_synthetic=True
    )
    X_test, y_test, validated_test = validate_cohort_records(
        test_records, test_labels, panel, require_synthetic=True
    )

    run_cfg = _training_config_for_route(route, config)
    run = train_research_model(
        dev_records,
        dev_labels,
        panel,
        model_id=f"synth_ai7_{route.route_id}",
        development_cohort_id=f"synthetic:{route.dataset_id}",
        development_dataset_id=route.dataset_id,
        synthetic_data_confirmed=True,
        config=run_cfg,
    )

    # Development-OOF calibrated scores on the synthetic test set (frozen
    # preprocessor + estimator + calibrator; no refit on test data).
    p_test_raw, _raw_logits_unused, p_test_cal = _predict_on_matrix(run, X_test)
    test_prevalence = float(np.mean(y_test == 1))

    metrics = evaluate_comprehensive_metrics(
        y_test,
        p_test_cal,
        seed=config.seed,
        n_bootstrap=config.bootstrap_resamples,
        threshold=config.exploratory_threshold,
        evaluation_scope=f"SYNTHETIC_TEST_ROUTE_{route.route_id}",
    )
    prevalence_shift = compute_prevalence_shift_diagnostic(
        development_prevalence=float(run.calibrator.development_prevalence),
        external_prevalence=test_prevalence,
    )

    # Descriptive outer-fold dispersion for ONE fixed synthetic test instance
    # (the first test record). Each fold member predicts that same instance
    # using its own preprocessor, estimator and inner-OOF calibrator, so the
    # spread reflects outer-fold model variation — not between-record variation
    # on a single final refit model across different test records.
    first_test_row = X_test[:1]
    fold_raw_scores: list[float] = []
    fold_cal_scores: list[float] = []
    fold_families: list[str] = []
    for member in run.fold_ensemble:
        raw, cal = _fold_member_prediction_for_instance(
            run, member, first_test_row, run.execution_profile
        )
        fold_raw_scores.append(raw)
        fold_cal_scores.append(cal)
        fold_families.append(member.model_family)

    # Missingness is reported for the selected instance only.
    first_instance_missing = tuple(validated_test[0].missing_fields_with_reason)

    dispersion = compute_fold_prediction_dispersion(
        fold_raw_scores=fold_raw_scores,
        fold_compatible_calibrated_scores=fold_cal_scores,
        fold_model_families=fold_families,
        missing_fields_with_reason=first_instance_missing,
        total_fields=len(panel.fields),
        development_prevalence=float(run.calibrator.development_prevalence),
    )

    # Regression guard: the fold count is the number of outer-fold ensemble
    # members, never the test-set size.
    assert dispersion["fold_ensemble_count"] == len(run.fold_ensemble)

    # Score declaration for the first synthetic test instance (per-instance
    # prediction-score output, explicitly separated from dataset accuracy).
    z_first = run.preprocessor.transform(X_test[:1])[0]
    E_first = _estimator_input_matrix(
        run.selected_model_family,
        run.preprocessor,
        X_test[:1],
        z_first.reshape(1, -1),
        run.execution_profile,
    )
    first_raw, first_raw_logit = _positive_proba_and_optional_logit(
        run.selected_model_family, run.estimator, E_first
    )
    first_cal = run.calibrator.calibrate(first_raw, raw_logits=first_raw_logit)
    first_cal_log_odds = float(
        run.calibrator.calibrated_log_odds(
            float(first_raw[0]), raw_logits=(None if first_raw_logit is None else float(first_raw_logit[0]))
        )
    )
    score_declaration = ResearchScoreDeclaration(
        raw_model_score=float(first_raw[0]),
        raw_model_log_odds=(
            None if first_raw_logit is None else float(first_raw_logit[0])
        ),
        calibrated_research_score=float(first_cal[0]),
        calibrated_log_odds=first_cal_log_odds,
        score_scale_declaration=(
            "raw_model_score = estimator raw probability on the encoded panel; "
            "calibrated_research_score = expit(intercept + slope * raw_log_odds) "
            "on the calibrated log-odds scale (l2_logistic_regression) or "
            "clipped logit of raw probability (tree/dummy families)."
        ),
        exploratory_threshold=config.exploratory_threshold,
        exploratory_above_threshold=bool(first_cal[0] >= config.exploratory_threshold),
        threshold_clinically_validated=False,
    )

    # Faithful SHAP on the declared scale (calibrated log-odds for logistic;
    # raw model probability for the forest family).
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

    # Genuine tabular LIME on the same declared scale; certified against the
    # registered quality policy. A non-acceptable verdict is diagnostic only.
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

    bundle_round_trip: dict[str, Any] | None = None
    if config.include_bundle_round_trip:
        work_root = (
            config.work_root
            if config.work_root is not None
            else Path(__file__).resolve().parents[1] / "data" / ".ai7_synthetic_work"
        )
        work_root = Path(work_root)
        sample_payload = test_records[0]
        bundle_round_trip = _run_bundle_round_trip(
            run, work_root, route_id, sample_payload, panel
        )

    exercise_id = f"ai7-synthetic-{route.route_id}-{int(config.seed)}"

    limitations = tuple(
        [
            "This is a deterministic synthetic software exercise on generated "
            "fixtures: not trained on patient data and not CAD performance "
            "evidence.",
            "calibrated_research_score is not a clinically validated individual "
            "CAD risk; dataset Accuracy is not a clinical decision threshold.",
            "Outer-fold dispersion is descriptive CV split sensitivity, not "
            "validated patient-specific uncertainty.",
            f"Route '{route.route_id}' is synthetic-only in this layer: "
            "real-data training, external evaluation, bundle inference and "
            "serving remain blocked by ai.execution / ai.packaging / "
            "ai.diagnostic_scope.",
        ]
    )
    if route.prediction_time_admissibility != ADMISSIBLE_SYNTHETIC_TEST_ONLY:
        limitations = limitations + (
            f"Route admissibility: {route.prediction_time_admissibility}.",
        )

    evaluation_contract = ResearchEvaluationContract(
        evaluation_status=route.evaluation_status,
        dataset_id=route.dataset_id,
        panel_id=route.panel_id,
        panel_contract_sha256=route.panel_contract_sha256,
        model_id=run.model_id,
        model_version=run.model_version,
        protocol_id=run.protocol_id,
        outcome_definition=route.target_definition,
        evaluation_population=(
            f"Synthetic test cohort (n={config.n_test}, "
            f"prevalence={test_prevalence:.3f}) for route '{route.route_id}'"
        ),
        development_prevalence=float(run.calibrator.development_prevalence),
        evaluation_prevalence=test_prevalence,
        exploratory_threshold=config.exploratory_threshold,
        threshold_clinically_approved=False,
        metrics=metrics,
        calibration_report={
            "intercept": float(run.calibrator.intercept),
            "slope": float(run.calibrator.slope),
            "input_link": str(run.calibrator.input_link),
            "status": str(run.calibrator.status),
            "fit_scope": str(run.calibrator.fit_scope),
            "n_oof_samples": int(run.calibrator.n_oof_samples),
            "prevalence_shift": prevalence_shift,
        },
        fold_dispersion=dispersion,
        shap_report={
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
        },
        lime_report={
            "quality_status": str(lime_explanation.quality_status),
            "is_reliable_for_interpretation": bool(
                lime_explanation.is_reliable_for_interpretation
            ),
            "explained_quantity": str(lime_explanation.explained_quantity),
            "scale": str(lime_explanation.scale),
            "local_fidelity_abs_error": float(
                lime_explanation.local_fidelity_abs_error
            ),
            "local_fidelity_relative_error": float(
                lime_explanation.local_fidelity_relative_error
            ),
            "weighted_r2": (
                None if lime_explanation.weighted_r2 is None
                else float(lime_explanation.weighted_r2)
            ),
            "holdout_weighted_r2": (
                None if lime_explanation.holdout_weighted_r2 is None
                else float(lime_explanation.holdout_weighted_r2)
            ),
            "is_local_approximation": bool(lime_explanation.is_local_approximation),
            "additive_decomposition_claim": bool(
                lime_explanation.additive_decomposition_claim
            ),
        },
        confidence_interval_method=(
            metrics.get("bootstrap_95_ci", {}).get("method")
            if isinstance(metrics, Mapping)
            else None
        ),
        limitations=limitations,
    )

    return ResearchRouteResult(
        route=route,
        eligibility=RouteEligibilityResult(
            eligible=True,
            decision="ROUTE_RESOLVED",
            route=route,
            route_id=route.route_id,
            operation=OP_END_TO_END_EXERCISE,
            rejections=(),
        ),
        exercise_id=exercise_id,
        seed=int(config.seed),
        development_cohort_id=f"synthetic:{route.dataset_id}",
        development_dataset_id=route.dataset_id,
        score_declaration=score_declaration,
        evaluation_contract=evaluation_contract,
        shap_explanation=explanation,
        lime_explanation=lime_explanation,
        lime_stability=lime_stability,
        bundle_round_trip=bundle_round_trip,
        limitations=limitations,
    )
