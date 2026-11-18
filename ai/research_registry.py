"""AI-11.1 — immutable, versioned offline research model/route registry.

This module is a **composition boundary, not a new pipeline**. It adds a single
small, frozen catalog that binds together the pieces that already exist and are
already reviewed:

- the source-specific route descriptors of :mod:`ai.research_routes`
  (route id/version, dataset, source family, pinned panel hash, permitted and
  forbidden operations, authorization and evaluation status);
- the versioned panel contracts of :mod:`ai.panels` (ordered feature names,
  roles, units, plausibility bounds, required/optional stage fields and the
  canonical ``contract_sha256``);
- the artifact identity, calibration and explainability declarations written
  and verified by :mod:`ai.packaging`;
- the offline predictor of :mod:`ai.inference` (which is the only object that
  can deserialize a research bundle, and only after
  :func:`ai.packaging.verify_trusted_local_bundle` has passed).

Guarantees provided here
------------------------
1. **Closed and immutable.** ``RESEARCH_MODEL_REGISTRY`` is a
   ``MappingProxyType`` built at import time from literal records. There is no
   ``register``, ``add``, ``update`` or plugin entry point, and no caller data
   (request field, environment variable, path, or JSON document) can create or
   change an entry. Unknown identifiers fail closed.
2. **Versioned.** Every entry pins ``route_version``, ``model_version``,
   ``panel_version`` and the panel ``contract_sha256``. The registry digest
   (:func:`registry_digest_sha256`) is a canonical SHA-256 over every entry
   contract plus the live route/panel catalogs it was validated against, so a
   drifting panel or route is detectable by hash alone.
3. **Self-validating.** At import each entry is checked against the live route
   and panel registries (identity, dataset, source family, target, panel hash,
   version, permitted operations, execution profile, model family). Any
   inconsistency raises :class:`ResearchRegistryError`; the module simply does
   not import.
4. **Synthetic-only.** No real-patient artifact is registerable (see
   :data:`REAL_ARTIFACT_MODEL_ID_PREFIXES`), every entry carries
   ``real_data_execution_authorized=False``, ``approved_for_serving=False`` and
   ``clinical_use_authorized=False``, and the only admissible artifact kind is
   a locally verified synthetic research bundle. Registration is a *lookup*
   entitlement for offline research inspection; it is not a serving entitlement
   and grants no data access, no Gate PT exception and no scientific claim.

Nothing in this module is imported by ``backend/app/``; ``MOCK_SYNTHETIC``
remains the only FastAPI runtime provider and the ``/v1`` contracts are
untouched.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from math import isfinite
import re
from types import MappingProxyType
from typing import Any, Final, Mapping, Sequence

from ai.errors import AiPipelineError
from ai.packaging import BUNDLE_SCHEMA_VERSION, METHOD_BY_MODEL_FAMILY
from ai.panels import REGISTERED_PANELS, ResearchPanelContract
from ai.calibration import OofLogisticCalibrator
from ai.research_routes import (
    EXECUTION_PROFILE_AI1_GENERIC_V1,
    KNOWN_OPERATIONS,
    OP_ROUTE_CONTRACT_QUERY,
    OP_SYNTHETIC_PREDICTION,
    RESEARCH_ROUTE_CATALOG,
    ResearchRouteDescriptor,
)

REGISTRY_SCHEMA_VERSION: Final[str] = "cardioassist.ai.research_registry/v1"
REGISTRY_VERSION: Final[str] = "1.0.0"
MODEL_KEY_SEPARATOR: Final[str] = "@"

#: The only artifact kind this registry can describe. A real, remote, or
#: caller-supplied loader object is not a representable artifact kind.
ARTIFACT_KIND_SYNTHETIC_BUNDLE: Final[str] = "local_verified_synthetic_bundle"
ADMISSIBLE_ARTIFACT_KINDS: Final[frozenset[str]] = frozenset(
    {ARTIFACT_KIND_SYNTHETIC_BUNDLE}
)

#: Entry lifecycle states. Only ``ACTIVE`` entries can be executed; every other
#: state is an explicit ``UNAVAILABLE`` answer with a reason, never a fallback.
ENTRY_STATE_ACTIVE: Final[str] = "ACTIVE_SYNTHETIC_OFFLINE"
ENTRY_STATE_BLOCKED_PENDING_AUTHORIZATION: Final[str] = "BLOCKED_PENDING_AUTHORIZATION"
ENTRY_STATE_BLOCKED_SOURCE_TIMING: Final[str] = "BLOCKED_SOURCE_TIMING_UNVERIFIED"
ENTRY_STATE_LOCKED_EXTERNAL_TARGET: Final[str] = "LOCKED_EXTERNAL_TARGET_NEVER_FACADE"
EXECUTABLE_ENTRY_STATES: Final[frozenset[str]] = frozenset({ENTRY_STATE_ACTIVE})
NON_EXECUTABLE_ENTRY_STATES: Final[frozenset[str]] = frozenset(
    {
        ENTRY_STATE_BLOCKED_PENDING_AUTHORIZATION,
        ENTRY_STATE_BLOCKED_SOURCE_TIMING,
        ENTRY_STATE_LOCKED_EXTERNAL_TARGET,
    }
)
KNOWN_ENTRY_STATES: Final[frozenset[str]] = EXECUTABLE_ENTRY_STATES | NON_EXECUTABLE_ENTRY_STATES

#: Evidence grade of every entry and every result produced through an entry.
EVIDENCE_LEVEL_SYNTHETIC_TEST: Final[str] = "SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE"
EVIDENCE_LEVEL_NOT_EVALUATED: Final[str] = "NOT_EVALUATED_NO_SYNTHETIC_EXERCISE"
ADMISSIBLE_EVIDENCE_LEVELS: Final[frozenset[str]] = frozenset(
    {EVIDENCE_LEVEL_SYNTHETIC_TEST, EVIDENCE_LEVEL_NOT_EVALUATED}
)

#: Capability declarations are compared against what the verified artifact
#: actually declares. These literals mirror :mod:`ai.packaging` exactly.
CALIBRATION_STATUS_SUPPORTED: Final[str] = "calibrated_out_of_fold_logistic"
CALIBRATOR_STATUS_FITTED: Final[str] = "FITTED_OOF_MONOTONE_LOGISTIC"
CALIBRATOR_STATUS_IDENTITY_FALLBACK: Final[str] = "IDENTITY_CONSTANT_FALLBACK"
EXPLAINABILITY_CAPABILITY_SUPPORTED: Final[str] = (
    "implemented_and_verified_in_research_harness"
)

#: Model-id prefixes reserved for real-patient research artifacts (the naming
#: used by ``ai.diagnostic_scope`` and the frozen Cleveland D-047 protocol). An
#: entry naming one of these is refused at construction time: such artifacts are
#: not registerable here and can never become registerable by editing a
#: document, because this registry reads no document at all. They remain outside
#: this facade and are governed by :mod:`ai.diagnostic_scope` and the
#: ``ai.execution`` authorization controller, under Gate PT (``P-3``) closed.
REAL_ARTIFACT_MODEL_ID_PREFIXES: Final[tuple[str, ...]] = (
    "cai_real_",
    "cad_real_",
    "cleveland_real_",
    "real_",
)

#: Deliberately fabricated synthetic fixtures are the only admissible input
#: provenance. ``synthetic: true`` by itself is a caller assertion, never
#: evidence — see :mod:`ai.research_facade`.
SYNTHETIC_PROVENANCE_DECLARATION: Final[str] = (
    "DELIBERATELY_FABRICATED_SYNTHETIC_FIXTURE"
)
ADMISSIBLE_SYNTHETIC_PROVENANCE_DECLARATIONS: Final[frozenset[str]] = frozenset(
    {SYNTHETIC_PROVENANCE_DECLARATION}
)

MAX_RECORDS_CEILING: Final[int] = 16
SAFE_IDENTIFIER_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
SAFE_DATASET_ID_RE: Final[re.Pattern[str]] = re.compile(r"^DA-[A-Z0-9]{1,8}$")
SAFE_RECORD_REF_RE: Final[re.compile] = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
SHA256_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")


class ResearchRegistryError(AiPipelineError):
    """Typed, value-redacting registry refusal.

    Only identifiers and invariant codes are surfaced — never a filesystem
    path, feature value, record content, or key material. A refusal that
    follows a successful entry lookup carries that :attr:`entry` so a caller
    can report the *registered* version identifiers alongside an UNAVAILABLE
    answer instead of hiding them.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        field: str | None = None,
        entry: "ResearchModelEntry | None" = None,
    ) -> None:
        super().__init__(code, message, field=field)
        self.entry = entry


# --------------------------------------------------------------------------- #
# Entry type                                                                   #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class ResearchModelEntry:
    """One reviewed offline research model slot (immutable, hash-addressed)."""

    model_id: str
    model_version: str
    route_id: str
    route_version: str
    dataset_id: str
    source_family: str
    panel_id: str
    panel_version: str
    panel_contract_sha256: str
    target_id: str
    protocol_id: str
    execution_profile: str
    artifact_kind: str
    entry_state: str
    evidence_level: str
    permitted_operations: frozenset[str]
    allowed_model_families: tuple[str, ...]
    calibration_supported: bool
    shap_supported: bool
    lime_supported: bool
    abstain_on_missing_optional: bool
    max_records_per_invocation: int
    admissible_synthetic_generators: tuple[str, ...]
    required_acquisition_stages: Mapping[str, str]
    real_data_execution_authorized: bool = False
    approved_for_serving: bool = False
    clinical_use_authorized: bool = False
    not_before: str = "AI-11.1 / Gate PT P-3 CLOSED / no serving entitlement"
    notes: tuple[str, ...] = ()

    @property
    def model_key(self) -> str:
        return f"{self.model_id}{MODEL_KEY_SEPARATOR}{self.model_version}"

    @property
    def executable(self) -> bool:
        return self.entry_state in EXECUTABLE_ENTRY_STATES

    @property
    def non_executable_reason(self) -> str | None:
        if self.executable:
            return None
        return _ENTRY_STATE_REASON.get(self.entry_state, "entry_state_unknown")

    def to_contract_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "route_id": self.route_id,
            "route_version": self.route_version,
            "dataset_id": self.dataset_id,
            "source_family": self.source_family,
            "panel_id": self.panel_id,
            "panel_version": self.panel_version,
            "panel_contract_sha256": self.panel_contract_sha256,
            "target_id": self.target_id,
            "protocol_id": self.protocol_id,
            "execution_profile": self.execution_profile,
            "artifact_kind": self.artifact_kind,
            "entry_state": self.entry_state,
            "executable": self.executable,
            "non_executable_reason": self.non_executable_reason,
            "evidence_level": self.evidence_level,
            "permitted_operations": sorted(self.permitted_operations),
            "allowed_model_families": list(self.allowed_model_families),
            "capabilities": {
                "calibration_supported": self.calibration_supported,
                "shap_supported": self.shap_supported,
                "lime_supported": self.lime_supported,
            },
            "inference_policy": {
                "abstain_on_missing_optional": self.abstain_on_missing_optional,
                "max_records_per_invocation": self.max_records_per_invocation,
                "admissible_synthetic_generators": list(
                    self.admissible_synthetic_generators
                ),
                "required_acquisition_stages": dict(
                    sorted(self.required_acquisition_stages.items())
                ),
            },
            "governance": {
                "real_data_execution_authorized": self.real_data_execution_authorized,
                "approved_for_serving": self.approved_for_serving,
                "clinical_use_authorized": self.clinical_use_authorized,
                "binding": self.not_before,
            },
            "notes": list(self.notes),
            # Contract projections never carry filesystem paths, key material,
            # or anything else a local installation would have to disclose.
            "local_paths_disclosed": False,
        }

    @property
    def entry_sha256(self) -> str:
        return _canonical_sha256(self.to_contract_dict())


_ENTRY_STATE_REASON: Final[Mapping[str, str]] = MappingProxyType(
    {
        ENTRY_STATE_BLOCKED_PENDING_AUTHORIZATION: (
            "model_entry_blocked_pending_authorization"
        ),
        ENTRY_STATE_BLOCKED_SOURCE_TIMING: (
            "model_entry_blocked_source_timing_unverified"
        ),
        ENTRY_STATE_LOCKED_EXTERNAL_TARGET: (
            "model_entry_locked_external_target"
        ),
    }
)


# --------------------------------------------------------------------------- #
# Canonical helpers                                                            #
# --------------------------------------------------------------------------- #


def _canonical_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _require_identifier(value: Any, *, code: str, message: str, field_name: str) -> str:
    if not isinstance(value, str) or not SAFE_IDENTIFIER_RE.fullmatch(value):
        raise ResearchRegistryError(code, message, field=field_name)
    return value


def _require_sha256(value: Any, *, code: str, message: str, field_name: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise ResearchRegistryError(code, message, field=field_name)
    return value


# --------------------------------------------------------------------------- #
# Entry construction + import-time validation                                  #
# --------------------------------------------------------------------------- #


def _build_entry(
    *,
    model_id: str,
    model_version: str,
    route_id: str,
    artifact_kind: str = ARTIFACT_KIND_SYNTHETIC_BUNDLE,
    entry_state: str,
    evidence_level: str,
    calibration_supported: bool,
    shap_supported: bool,
    lime_supported: bool,
    abstain_on_missing_optional: bool,
    admissible_synthetic_generators: tuple[str, ...],
    notes: tuple[str, ...] = (),
    protocol_id: str | None = None,
    max_records_per_invocation: int = MAX_RECORDS_CEILING,
) -> ResearchModelEntry:
    """Build one entry and validate it against the live registries immediately.

    Any missing identifier is *derived* from the pinned route descriptor, never
    invented: the route catalog is the single source of truth for dataset,
    source family, target, panel id and panel hash.
    """
    if not isinstance(route_id, str) or route_id not in RESEARCH_ROUTE_CATALOG:
        raise ResearchRegistryError(
            "registry_route_unregistered",
            "Registry entry references a route that is not in the frozen route catalog.",
            field="route_id",
        )
    route = RESEARCH_ROUTE_CATALOG[route_id]
    if not isinstance(model_id, str) or model_id in ("",):
        raise ResearchRegistryError(
            "registry_invalid_model_id", "Registry entry model_id is invalid.", field="model_id"
        )
    for prefix in REAL_ARTIFACT_MODEL_ID_PREFIXES:
        if model_id.startswith(prefix):
            raise ResearchRegistryError(
                "registry_real_artifact_not_registerable",
                "Real-patient research artifacts cannot be registered in this "
                "synthetic-only registry; they remain outside this facade and "
                "are governed by ai.diagnostic_scope.",
                field="model_id",
            )
    if artifact_kind not in ADMISSIBLE_ARTIFACT_KINDS:
        raise ResearchRegistryError(
            "registry_artifact_kind_not_allowed",
            "Only a locally verified synthetic research bundle is a representable artifact kind.",
            field="artifact_kind",
        )
    if entry_state not in KNOWN_ENTRY_STATES:
        raise ResearchRegistryError(
            "registry_unknown_entry_state",
            "Registry entry state is not one of the registered lifecycle states.",
            field="entry_state",
        )
    if evidence_level not in ADMISSIBLE_EVIDENCE_LEVELS:
        raise ResearchRegistryError(
            "registry_evidence_level_not_allowed",
            "Registry entry evidence level is not a registered synthetic research grade.",
            field="evidence_level",
        )
    if route.panel_id not in REGISTERED_PANELS:
        raise ResearchRegistryError(
            "registry_panel_unregistered",
            "Registry entry route panel is not present in the panel registry.",
            field="panel_id",
        )
    panel = REGISTERED_PANELS[route.panel_id]

    required_stages = {spec.name: spec.stage for spec in panel.fields if spec.required}
    resolved_protocol = protocol_id or f"CAI-AI111-UNSPECIFIED-{route_id.upper()}-V1"
    # The generic synthetic profile is the only profile this offline layer can
    # execute. A contract-only entry keeps the profile its frozen route
    # actually declares, so the registry never invents a capability.
    resolved_profile = (
        EXECUTION_PROFILE_AI1_GENERIC_V1
        if EXECUTION_PROFILE_AI1_GENERIC_V1 in route.supported_execution_profiles
        else route.supported_execution_profiles[0]
    )

    entry = ResearchModelEntry(
        model_id=model_id,
        model_version=model_version,
        route_id=route.route_id,
        route_version=route.route_version,
        dataset_id=route.dataset_id,
        source_family=route.source_family,
        panel_id=panel.panel_id,
        panel_version=panel.panel_version,
        panel_contract_sha256=route.panel_contract_sha256,
        target_id=route.target_id,
        protocol_id=resolved_protocol,
        execution_profile=resolved_profile,
        artifact_kind=artifact_kind,
        entry_state=entry_state,
        evidence_level=evidence_level,
        permitted_operations=frozenset(
            {OP_ROUTE_CONTRACT_QUERY}
            if not entry_state in EXECUTABLE_ENTRY_STATES
            else {OP_ROUTE_CONTRACT_QUERY, OP_SYNTHETIC_PREDICTION}
        ),
        allowed_model_families=tuple(route.allowed_model_families),
        calibration_supported=calibration_supported,
        shap_supported=shap_supported,
        lime_supported=lime_supported,
        abstain_on_missing_optional=abstain_on_missing_optional,
        max_records_per_invocation=max_records_per_invocation,
        admissible_synthetic_generators=admissible_synthetic_generators,
        required_acquisition_stages=MappingProxyType(dict(required_stages)),
        notes=notes,
    )
    _validate_entry(entry, route=route, panel=panel)
    return entry


def _validate_entry(
    entry: ResearchModelEntry,
    *,
    route: ResearchRouteDescriptor,
    panel: ResearchPanelContract,
) -> None:
    """Fail closed if an entry ever drifts from the catalogs it pins."""
    if entry.panel_contract_sha256 != panel.contract_sha256:
        raise ResearchRegistryError(
            "registry_panel_hash_mismatch",
            "Registry entry panel hash no longer matches the registered panel contract.",
            field="panel_contract_sha256",
        )
    if entry.panel_version != panel.panel_version:
        raise ResearchRegistryError(
            "registry_panel_version_mismatch",
            "Registry entry panel version does not match the registered panel contract.",
            field="panel_version",
        )
    if entry.route_version != route.route_version:
        raise ResearchRegistryError(
            "registry_route_version_mismatch",
            "Registry entry route version does not match the frozen route descriptor.",
            field="route_version",
        )
    if (entry.dataset_id, entry.source_family) != (route.dataset_id, route.source_family):
        raise ResearchRegistryError(
            "registry_dataset_or_source_mismatch",
            "Registry entry dataset/source family does not match the route descriptor.",
            field="dataset_id",
        )
    if entry.target_id != route.target_id:
        raise ResearchRegistryError(
            "registry_target_mismatch",
            "Registry entry target id does not match the route descriptor.",
            field="target_id",
        )
    if entry.execution_profile not in route.supported_execution_profiles:
        raise ResearchRegistryError(
            "registry_execution_profile_unsupported",
            "Registry entry execution profile is not supported by the route.",
            field="execution_profile",
        )
    for family in entry.allowed_model_families:
        if family not in METHOD_BY_MODEL_FAMILY:
            raise ResearchRegistryError(
                "registry_model_family_unregistered",
                "Registry entry declares a model family with no registered SHAP method.",
                field="allowed_model_families",
            )
    for operation in entry.permitted_operations:
        if operation not in KNOWN_OPERATIONS:
            raise ResearchRegistryError(
                "registry_operation_unknown",
                "Registry entry permits an operation that is not a registered operation.",
                field="permitted_operations",
            )
        if operation not in route.permitted_operations:
            raise ResearchRegistryError(
                "registry_operation_not_permitted_by_route",
                "Registry entry permits an operation the frozen route does not permit.",
                field="permitted_operations",
            )
        if operation in route.forbidden_operations:
            raise ResearchRegistryError(
                "registry_operation_forbidden_by_route",
                "Registry entry permits an operation the frozen route forbids.",
                field="permitted_operations",
            )
    if entry.entry_state in EXECUTABLE_ENTRY_STATES:
        if OP_SYNTHETIC_PREDICTION not in entry.permitted_operations:
            raise ResearchRegistryError(
                "registry_active_entry_missing_prediction_operation",
                "An executable registry entry must permit synthetic prediction.",
                field="entry_state",
            )
    else:
        if OP_SYNTHETIC_PREDICTION in entry.permitted_operations:
            raise ResearchRegistryError(
                "registry_blocked_entry_must_not_be_executable",
                "A non-executable registry entry must not permit synthetic prediction.",
                field="entry_state",
            )
        if entry.evidence_level != EVIDENCE_LEVEL_NOT_EVALUATED:
            raise ResearchRegistryError(
                "registry_blocked_entry_evidence_mismatch",
                "A non-executable registry entry must report NOT_EVALUATED.",
                field="evidence_level",
            )
    for name in (entry.model_id, entry.route_id, entry.panel_id):
        _require_identifier(
            name,
            code="registry_invalid_identifier",
            message="Registry entry carries an identifier outside the safe identifier grammar.",
            field_name="model_id",
        )
    if not isinstance(entry.dataset_id, str) or not SAFE_DATASET_ID_RE.fullmatch(
        entry.dataset_id
    ):
        raise ResearchRegistryError(
            "registry_invalid_dataset_id",
            "Registry entry dataset id is outside the registered dataset grammar.",
            field="dataset_id",
        )
    _require_sha256(
        entry.panel_contract_sha256,
        code="registry_invalid_panel_hash",
        message="Registry entry panel hash is not a lowercase SHA-256 digest.",
        field_name="panel_contract_sha256",
    )
    if entry.real_data_execution_authorized or entry.approved_for_serving or (
        entry.clinical_use_authorized
    ):
        raise ResearchRegistryError(
            "registry_authorization_overclaim",
            "No registry entry may claim real-data execution, serving approval or clinical use.",
            field="governance",
        )
    if not (
        1 <= entry.max_records_per_invocation <= MAX_RECORDS_CEILING
    ):
        raise ResearchRegistryError(
            "registry_record_ceiling_invalid",
            "Registry entry record ceiling is outside the permitted bound.",
            field="max_records_per_invocation",
        )
    if entry.entry_state in EXECUTABLE_ENTRY_STATES:
        if not entry.calibration_supported or not entry.shap_supported:
            raise ResearchRegistryError(
                "registry_capability_declaration_incomplete",
                "An executable entry must declare its calibration and SHAP capability "
                "explicitly; the facade never infers support from the request.",
                field="capabilities",
            )
        if not entry.admissible_synthetic_generators:
            raise ResearchRegistryError(
                "registry_generator_allowlist_empty",
                "Every executable entry must pin a non-empty synthetic fixture generator allowlist.",
                field="admissible_synthetic_generators",
            )
    else:
        if (
            entry.calibration_supported
            or entry.shap_supported
            or entry.lime_supported
            or entry.admissible_synthetic_generators
        ):
            raise ResearchRegistryError(
                "registry_blocked_entry_declares_capabilities",
                "A non-executable entry may not advertise reportable capabilities or "
                "admissible fixture generators: nothing can be produced through it.",
                field="capabilities",
            )
    for generator in entry.admissible_synthetic_generators:
        _require_identifier(
            generator,
            code="registry_invalid_generator_id",
            message="Registry entry names an invalid synthetic fixture generator identifier.",
            field_name="admissible_synthetic_generators",
        )


def _build_registry() -> Mapping[str, ResearchModelEntry]:
    entries = (
        _build_entry(
            model_id="synth_ai7_da_a2_resting_v1",
            model_version="0.1.0",
            route_id="da_a2_resting_v1",
            protocol_id="CAI-AI7-SYNTHETIC-DA_A2_RESTING_V1-V1",
            entry_state=ENTRY_STATE_ACTIVE,
            evidence_level=EVIDENCE_LEVEL_SYNTHETIC_TEST,
            calibration_supported=True,
            shap_supported=True,
            lime_supported=True,
            abstain_on_missing_optional=True,
            admissible_synthetic_generators=(
                "ai.research_routes.build_synthetic_uci45_resting_cohort",
            ),
            notes=(
                "Artifact is the deterministic synthetic AI-7 route exercise output for da_a2_resting_v1.",
                "Five resting fields only (age, sex, cp, trestbps, restecg); trestbps/restecg are optional "
                "panel fields, and this entry abstains instead of silently imputing them at inference time.",
            ),
        ),
        _build_entry(
            model_id="synth_ai8_uci412_da_a1_basic_clinical",
            model_version="0.1.0",
            route_id="da_a1_basic_clinical_v1",
            protocol_id="CAI-AI8-SYNTHETIC-UCI412-DA-A1-BASIC-CLINICAL-V1",
            entry_state=ENTRY_STATE_ACTIVE,
            evidence_level=EVIDENCE_LEVEL_SYNTHETIC_TEST,
            calibration_supported=True,
            shap_supported=True,
            lime_supported=True,
            abstain_on_missing_optional=False,
            admissible_synthetic_generators=(
                "ai.research_routes.build_synthetic_uci412_basic_clinical_cohort",
            ),
            notes=(
                "Artifact is the deterministic synthetic AI-8 standalone UCI-412 research model.",
                "All 16 basic clinical panel fields are required by the panel contract: there is no "
                "optional-field abstention to take on this entry.",
                "Real UCI-412 research execution remains subject to M3a/D-048 and Gate PT P-3.",
            ),
        ),
        _build_entry(
            model_id="synth_ai7_da_a2_resting_labs_v1",
            model_version="0.1.0",
            route_id="da_a2_resting_labs_v1",
            entry_state=ENTRY_STATE_BLOCKED_PENDING_AUTHORIZATION,
            evidence_level=EVIDENCE_LEVEL_NOT_EVALUATED,
            calibration_supported=False,
            shap_supported=False,
            lime_supported=False,
            abstain_on_missing_optional=True,
            admissible_synthetic_generators=(),
            notes=(
                "Contract-only registration: the AI-7 route marks this planned chol+fbs extension "
                "PLANNED_BLOCKED_PENDING_AUTHORIZATION, so no inference is reachable through it.",
            ),
        ),
        _build_entry(
            model_id="synth_ai7_da_a1_clinical_core_labs_v1",
            model_version="0.1.0",
            route_id="da_a1_clinical_core_labs_v1",
            entry_state=ENTRY_STATE_BLOCKED_SOURCE_TIMING,
            evidence_level=EVIDENCE_LEVEL_NOT_EVALUATED,
            calibration_supported=False,
            shap_supported=False,
            lime_supported=False,
            abstain_on_missing_optional=True,
            admissible_synthetic_generators=(),
            notes=(
                "Seven routine laboratory fields have unverified pre-angiography availability; the "
                "route descriptor blocks the synthetic exercise until Gate PT resolves the timing.",
            ),
        ),
        _build_entry(
            model_id="synth_ai7_da_a2_hungary_locked_transportability_v1",
            model_version="0.1.0",
            route_id="da_a2_hungary_locked_transportability_v1",
            entry_state=ENTRY_STATE_LOCKED_EXTERNAL_TARGET,
            evidence_level=EVIDENCE_LEVEL_NOT_EVALUATED,
            calibration_supported=False,
            shap_supported=False,
            lime_supported=False,
            abstain_on_missing_optional=False,
            admissible_synthetic_generators=(),
            notes=(
                "Hungary is a locked one-shot external target: it is never trained or tuned on, and "
                "locked-set evaluation is not reachable through this offline facade.",
            ),
        ),
    )
    registry: dict[str, ResearchModelEntry] = {}
    for entry in entries:
        if entry.model_key in registry:
            raise ResearchRegistryError(
                "registry_duplicate_model_key",
                "Two registry entries share one model key.",
                field="model_id",
            )
        registry[entry.model_key] = entry
    return MappingProxyType(dict(registry))


RESEARCH_MODEL_REGISTRY: Final[Mapping[str, ResearchModelEntry]] = _build_registry()

#: Route ids that have at least one registry entry (contract inspection only).
REGISTRY_ROUTE_IDS: Final[frozenset[str]] = frozenset(
    entry.route_id for entry in RESEARCH_MODEL_REGISTRY.values()
)

#: The immutable digest of the registry content itself, computed after
#: validation so it cannot be set by a caller.
def _compute_registry_digest() -> str:
    payload = {
        "registry_schema_version": REGISTRY_SCHEMA_VERSION,
        "registry_version": REGISTRY_VERSION,
        "bundle_schema_version": BUNDLE_SCHEMA_VERSION,
        "route_catalog_digest_sha256": _canonical_sha256(
            {
                route_id: {
                    "route_version": route.route_version,
                    "panel_id": route.panel_id,
                    "panel_contract_sha256": route.panel_contract_sha256,
                    "permitted_operations": sorted(route.permitted_operations),
                    "forbidden_operations": sorted(route.forbidden_operations),
                    "evaluation_status": route.evaluation_status,
                }
                for route_id, route in sorted(RESEARCH_ROUTE_CATALOG.items())
            }
        ),
        "panel_registry_digest_sha256": _canonical_sha256(
            {
                panel_id: {
                    "panel_version": panel.panel_version,
                    "contract_sha256": panel.contract_sha256,
                }
                for panel_id, panel in sorted(REGISTERED_PANELS.items())
            }
        ),
        "entries": {key: entry.to_contract_dict() for key, entry in sorted(RESEARCH_MODEL_REGISTRY.items())},
    }
    return _canonical_sha256(payload)


REGISTRY_DIGEST_SHA256: Final[str] = _compute_registry_digest()


# --------------------------------------------------------------------------- #
# Public read API                                                             #
# --------------------------------------------------------------------------- #


def get_model_entry(model_id: str, model_version: str) -> ResearchModelEntry:
    """Return one registered entry, or fail closed with a typed refusal."""
    if not isinstance(model_id, str) or not isinstance(model_version, str):
        raise ResearchRegistryError(
            "unknown_model_entry",
            "Model identity must be supplied as two strings; nothing was looked up.",
            field="model_id",
        )
    key = f"{model_id}{MODEL_KEY_SEPARATOR}{model_version}"
    entry = RESEARCH_MODEL_REGISTRY.get(key)
    if entry is None:
        raise ResearchRegistryError(
            "unknown_model_entry",
            "No research model entry is registered for this model id and version. "
            "The registry accepts no runtime plugins, paths, or caller-supplied descriptors.",
            field="model_id",
        )
    return entry


def binding_for_entry(entry: ResearchModelEntry) -> ResolvedRegistryBinding:
    """Rebuild the (entry, route, panel) binding of an already-resolved entry.

    Used to report the *registered* identifiers alongside an UNAVAILABLE
    refusal, where the entry itself resolved but execution is blocked.
    """
    route = RESEARCH_ROUTE_CATALOG[entry.route_id]
    panel = REGISTERED_PANELS[entry.panel_id]
    return ResolvedRegistryBinding(entry=entry, route=route, panel=panel)


def registry_contract() -> dict[str, Any]:
    """Return the full registry as a JSON-safe, path-free contract document."""
    return {
        "registry_schema_version": REGISTRY_SCHEMA_VERSION,
        "registry_version": REGISTRY_VERSION,
        "registry_digest_sha256": REGISTRY_DIGEST_SHA256,
        "bundle_schema_version": BUNDLE_SCHEMA_VERSION,
        "admissible_artifact_kinds": sorted(ADMISSIBLE_ARTIFACT_KINDS),
        "known_entry_states": sorted(KNOWN_ENTRY_STATES),
        "executable_entry_states": sorted(EXECUTABLE_ENTRY_STATES),
        "evidence_levels": sorted(ADMISSIBLE_EVIDENCE_LEVELS),
        "max_records_ceiling": MAX_RECORDS_CEILING,
        "synthetic_provenance_declaration": SYNTHETIC_PROVENANCE_DECLARATION,
        "real_artifacts_registerable": False,
        "mutation_api_present": False,
        "entries": {
            key: entry.to_contract_dict()
            for key, entry in sorted(RESEARCH_MODEL_REGISTRY.items())
        },
    }


def registry_digest_sha256() -> str:
    """Return the canonical SHA-256 digest of the registry contract."""
    return REGISTRY_DIGEST_SHA256


@dataclass(frozen=True, slots=True)
class ResolvedRegistryBinding:
    """The three mutually verified contracts behind one accepted request."""

    entry: ResearchModelEntry
    route: ResearchRouteDescriptor
    panel: ResearchPanelContract

    def to_dict(self) -> dict[str, Any]:
        return {
            "registry_schema_version": REGISTRY_SCHEMA_VERSION,
            "registry_version": REGISTRY_VERSION,
            "registry_digest_sha256": REGISTRY_DIGEST_SHA256,
            "model_key": self.entry.model_key,
            "route_id": self.route.route_id,
            "route_version": self.route.route_version,
            "dataset_id": self.route.dataset_id,
            "source_family": self.route.source_family,
            "target_id": self.route.target_id,
            "panel_id": self.panel.panel_id,
            "panel_version": self.panel.panel_version,
            "panel_contract_sha256": self.panel.contract_sha256,
            "entry_state": self.entry.entry_state,
            "evidence_level": self.entry.evidence_level,
        }


def resolve_registered_model(
    *,
    route_id: str,
    route_version: str,
    model_id: str,
    model_version: str,
    panel_id: str,
    panel_version: str,
    panel_contract_sha256: str,
    dataset_id: str,
    operation: str,
) -> ResolvedRegistryBinding:
    """Resolve one request into a fully cross-verified (entry, route, panel) binding.

    Every identifier supplied by the caller must agree with the registry entry,
    with the frozen route descriptor and with the live panel contract. Any
    disagreement is a typed refusal; there is no defaulting, no "latest
    version", and no fuzzy matching.
    """
    entry = get_model_entry(model_id, model_version)

    if not isinstance(route_id, str) or route_id != entry.route_id:
        raise ResearchRegistryError(
            "route_id_mismatch",
            "Requested route id is not the route this model entry is registered against.",
            field="route_id",
        )
    if not isinstance(route_version, str) or route_version != entry.route_version:
        raise ResearchRegistryError(
            "route_version_mismatch",
            "Requested route version does not match the registered route version.",
            field="route_version",
        )
    if not isinstance(dataset_id, str) or dataset_id != entry.dataset_id:
        raise ResearchRegistryError(
            "dataset_id_mismatch",
            "Requested dataset id does not match the route's source-specific dataset.",
            field="dataset_id",
        )
    if not isinstance(panel_id, str) or panel_id != entry.panel_id:
        raise ResearchRegistryError(
            "panel_id_mismatch",
            "Requested panel id does not match the panel contract this entry is bound to.",
            field="panel_id",
        )
    if not isinstance(panel_version, str) or panel_version != entry.panel_version:
        raise ResearchRegistryError(
            "panel_version_mismatch",
            "Requested panel version does not match the registered panel contract version.",
            field="panel_version",
        )
    if not isinstance(panel_contract_sha256, str) or not SHA256_RE.fullmatch(
        panel_contract_sha256
    ):
        raise ResearchRegistryError(
            "panel_contract_hash_invalid",
            "Requested panel contract hash is not a lowercase SHA-256 digest.",
            field="panel_contract_sha256",
        )
    if panel_contract_sha256 != entry.panel_contract_sha256:
        raise ResearchRegistryError(
            "panel_contract_hash_mismatch",
            "Requested panel contract hash does not match the hash pinned by the registry entry.",
            field="panel_contract_sha256",
        )
    if not entry.executable:
        # A registered-but-blocked contract answers UNAVAILABLE with its
        # registered versions attached, before any operation-specific check:
        # nothing about the request can unblock it here.
        raise ResearchRegistryError(
            str(entry.non_executable_reason),
            "This model entry is registered for contract inspection only and is "
            "not executable in this offline research facade.",
            field="entry_state",
            entry=entry,
        )
    if not isinstance(operation, str) or operation not in KNOWN_OPERATIONS:
        raise ResearchRegistryError(
            "operation_unknown",
            "Requested operation is not a registered research operation.",
            field="operation",
        )
    if operation not in entry.permitted_operations:
        raise ResearchRegistryError(
            "operation_not_permitted_for_model_entry",
            "Requested operation is not permitted for this registered model entry.",
            field="operation",
        )

    route = RESEARCH_ROUTE_CATALOG.get(entry.route_id)
    if route is None:  # pragma: no cover - guarded at import time
        raise ResearchRegistryError(
            "route_not_registered",
            "The route referenced by the registry entry is not present in the route catalog.",
            field="route_id",
        )
    panel = REGISTERED_PANELS.get(entry.panel_id)
    if panel is None:  # pragma: no cover - guarded at import time
        raise ResearchRegistryError(
            "panel_unregistered",
            "The panel referenced by the registry entry is not present in the panel registry.",
            field="panel_id",
        )
    if panel.contract_sha256 != entry.panel_contract_sha256:
        raise ResearchRegistryError(
            "panel_contract_hash_mismatch",
            "The live panel contract no longer matches the hash pinned by the registry.",
            field="panel_contract_sha256",
        )
    if operation not in route.permitted_operations or operation in route.forbidden_operations:
        raise ResearchRegistryError(
            "operation_not_permitted_for_route",
            "The frozen route descriptor does not permit this operation.",
            field="operation",
        )
    return ResolvedRegistryBinding(entry=entry, route=route, panel=panel)


# --------------------------------------------------------------------------- #
# Verified-artifact cross-checks (pre-deserialization)                         #
# --------------------------------------------------------------------------- #

#: Manifest keys checked against the registry entry. Every value is compared
#: against the verified bundle manifest — never against a caller declaration.
_MANIFEST_IDENTITY_CHECKS: Final[tuple[tuple[str, str, str], ...]] = (
    ("model.model_id", "model_id", "artifact_model_id_mismatch"),
    ("model.model_version", "model_version", "artifact_model_version_mismatch"),
    ("model.protocol_id", "protocol_id", "artifact_protocol_id_mismatch"),
    ("model.execution_profile", "execution_profile", "artifact_execution_profile_mismatch"),
    ("panel_contract.panel_id", "panel_id", "artifact_panel_id_mismatch"),
    ("panel_contract.panel_version", "panel_version", "artifact_panel_version_mismatch"),
    ("panel_contract.contract_sha256", "panel_contract_sha256", "artifact_panel_hash_mismatch"),
    ("target.target_id", "target_id", "artifact_target_id_mismatch"),
)


def _manifest_lookup(manifest: Mapping[str, Any], dotted: str) -> Any:
    node: Any = manifest
    for part in dotted.split("."):
        if not isinstance(node, Mapping) or part not in node:
            return None
        node = node[part]
    return node


def assert_artifact_identity(
    manifest: Mapping[str, Any], entry: ResearchModelEntry
) -> str:
    """Cross-check a verified bundle manifest against a registry entry.

    Returns the artifact's declared model family after checking every pinned
    identifier. Runs strictly on the already-verified ``manifest.json``
    document, i.e. before any ``joblib.load``.
    """
    if not isinstance(manifest, Mapping):
        raise ResearchRegistryError(
            "artifact_manifest_unavailable",
            "No verified bundle manifest was available for the identity check.",
            field="manifest",
        )
    if manifest.get("bundle_schema_version") != BUNDLE_SCHEMA_VERSION:
        raise ResearchRegistryError(
            "artifact_bundle_schema_mismatch",
            "Bundle schema version does not match the schema this registry describes.",
            field="bundle_schema_version",
        )
    for dotted, attribute, code in _MANIFEST_IDENTITY_CHECKS:
        actual = _manifest_lookup(manifest, dotted)
        expected = getattr(entry, attribute)
        if actual != expected:
            raise ResearchRegistryError(
                code,
                f"The verified artifact does not match the registry binding for '{attribute}'.",
                field=attribute,
            )
    ordered = _manifest_lookup(manifest, "panel_contract.ordered_feature_names")
    entry_panel = REGISTERED_PANELS.get(entry.panel_id)
    if entry_panel is None or list(ordered or []) != list(entry_panel.feature_names):
        raise ResearchRegistryError(
            "artifact_feature_order_mismatch",
            "The artifact's ordered feature list does not match the registered panel order.",
            field="ordered_feature_names",
        )
    model_family = _manifest_lookup(manifest, "model.selected_model_family")
    if model_family not in entry.allowed_model_families:
        raise ResearchRegistryError(
            "artifact_model_family_not_allowed",
            "The artifact's selected model family is not allowed for this route.",
            field="selected_model_family",
        )
    if model_family not in METHOD_BY_MODEL_FAMILY:
        raise ResearchRegistryError(
            "artifact_model_family_unregistered",
            "The artifact's model family has no registered explainability method.",
            field="selected_model_family",
        )
    if manifest.get("research_authorization") is not None:
        raise ResearchRegistryError(
            "artifact_real_provenance_not_supported",
            "The artifact carries a real research-authorization context; this "
            "synthetic-only registry and facade never load or score it.",
            field="research_authorization",
        )
    eligibility = manifest.get("eligibility")
    if not isinstance(eligibility, Mapping) or eligibility.get("synthetic_only") is not True:
        raise ResearchRegistryError(
            "artifact_synthetic_provenance_absent",
            "The artifact does not attest synthetic-only training provenance; a "
            "caller assertion can never substitute for artifact provenance.",
            field="eligibility.synthetic_only",
        )
    if eligibility.get("execution_mode") != "SYNTHETIC_RESEARCH":
        raise ResearchRegistryError(
            "artifact_execution_mode_not_synthetic",
            "The artifact execution mode is not the synthetic research mode.",
            field="eligibility.execution_mode",
        )
    if (
        eligibility.get("approved_for_serving") is not False
        or eligibility.get("clinical_use_authorized") is not False
        or eligibility.get("serving_eligibility") != "RESEARCH_ONLY"
    ):
        raise ResearchRegistryError(
            "artifact_serving_claim_rejected",
            "The artifact declares a serving or clinical-use claim; research artifacts never do.",
            field="eligibility",
        )
    if _manifest_lookup(manifest, "target.development_dataset_id") != entry.dataset_id:
        raise ResearchRegistryError(
            "artifact_development_dataset_mismatch",
            "The artifact development dataset does not match the registered route dataset.",
            field="development_dataset_id",
        )
    development_cohort = _manifest_lookup(manifest, "target.development_cohort_id")
    if not isinstance(development_cohort, str) or not development_cohort.startswith(
        "synthetic:"
    ):
        raise ResearchRegistryError(
            "artifact_development_cohort_not_marked_synthetic",
            "The artifact development cohort identity does not declare a synthetic cohort.",
            field="development_cohort_id",
        )
    if _manifest_lookup(manifest, "target.pooled_cohorts") is not False:
        raise ResearchRegistryError(
            "artifact_pooled_cohorts_rejected",
            "Pooled-cohort artifacts are never admissible in this registry.",
            field="pooled_cohorts",
        )
    return str(model_family)


@dataclass(frozen=True, slots=True)
class ArtifactCapabilities:
    """What the *verified artifact* can actually report — never caller-declared."""

    calibration_supported: bool
    calibration_status: str
    calibrator_status: str
    calibration_input_link: str | None
    calibration_fit_scope: str | None
    development_prevalence: float | None
    n_oof_samples: int | None
    oof_brier_before: float | None
    oof_brier_after: float | None
    unsupported_calibration_reason: str | None
    shap_supported: bool
    shap_method: str | None
    shap_explained_quantity: str | None
    shap_scale: str | None
    shap_additive_on_calibrated_probability: bool
    shap_background_sample_count: int | None
    shap_background_synthetic_only: bool | None
    shap_background_panel_bound: bool
    shap_background_encoded_feature_count: int | None
    lime_supported: bool
    lime_unsupported_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "calibration": {
                "supported": self.calibration_supported,
                "artifact_declared_status": self.calibration_status,
                "calibrator_status": self.calibrator_status,
                "input_link": self.calibration_input_link,
                "fit_scope": self.calibration_fit_scope,
                "development_prevalence": self.development_prevalence,
                "n_oof_samples": self.n_oof_samples,
                "oof_brier_before": self.oof_brier_before,
                "oof_brier_after": self.oof_brier_after,
                "reason": self.unsupported_calibration_reason,
                "never_relabel_raw_score_as_calibrated": True,
            },
            "explainability": {
                "shap": {
                    "supported": self.shap_supported,
                    "method": self.shap_method,
                    "explained_quantity": self.shap_explained_quantity,
                    "scale": self.shap_scale,
                    "additive_on_calibrated_probability": (
                        self.shap_additive_on_calibrated_probability
                    ),
                    "background_sample_count": self.shap_background_sample_count,
                    "background_synthetic_only": self.shap_background_synthetic_only,
                    "background_panel_bound": self.shap_background_panel_bound,
                    "background_encoded_feature_count": (
                        self.shap_background_encoded_feature_count
                    ),
                    "background_privacy_classification": (
                        "SYNTHETIC_NON_PATIENT_DERIVATIVE"
                    ),
                    "background_contains_patient_records": False,
                },
                "lime": {
                    "supported": self.lime_supported,
                    "computed": False,
                    "reason": self.lime_unsupported_reason,
                },
            },
        }


def derive_artifact_capabilities(
    manifest: Mapping[str, Any],
    *,
    entry: ResearchModelEntry,
    calibrator: OofLogisticCalibrator,
    background_document: Mapping[str, Any],
    model_family: str,
) -> ArtifactCapabilities:
    """Derive reportable capabilities from the artifact, then compare with the entry.

    ``calibration_supported`` is true only when the artifact declares the
    out-of-fold logistic calibration status **and** the deserialized-payload
    calibrator reports the fitted monotone status. A constant/identity fallback
    calibrator is therefore reported as *not calibrated* with a reason, and the
    raw model probability is never relabelled as a calibrated score.
    """
    declared_calibration = str(_manifest_lookup(manifest, "model.calibration_status") or "")
    calibrator_status = str(calibrator.status)
    calibration_reason: str | None = None
    if declared_calibration != CALIBRATION_STATUS_SUPPORTED:
        calibration_reason = "artifact_declares_no_supported_calibration_status"
    elif calibrator_status == CALIBRATOR_STATUS_IDENTITY_FALLBACK:
        calibration_reason = "calibrator_status_identity_constant_fallback"
    elif calibrator_status != CALIBRATOR_STATUS_FITTED:
        calibration_reason = "calibrator_status_unregistered"
    calibration_supported = calibration_reason is None

    xai = _manifest_lookup(manifest, "model.explainability")
    xai = xai if isinstance(xai, Mapping) else {}
    capability = str(xai.get("capability") or "")
    shap_supported = capability == EXPLAINABILITY_CAPABILITY_SUPPORTED
    expected_method = METHOD_BY_MODEL_FAMILY.get(model_family)
    declared_method = xai.get("method")
    if not shap_supported or shap_supported != entry.shap_supported:
        # An executable entry is registered against a reviewed artifact that
        # must carry verified SHAP: its absence is an integrity failure, not a
        # degraded-but-reportable answer.
        raise ResearchRegistryError(
            "artifact_capability_declaration_mismatch",
            "The verified artifact does not provide the explainability capability "
            "this registry entry was reviewed against.",
            field="model.explainability.capability",
        )
    if expected_method is not None and declared_method not in (None, expected_method):
        raise ResearchRegistryError(
            "artifact_explainability_method_mismatch",
            "The artifact explainability method does not match the registered method for its model family.",
            field="model.explainability.method",
        )
    shap_reason: str | None = None

    # The SHAP background is a *training derivative*: its own recorded privacy
    # block, not the caller, decides whether it may be described as synthetic.
    background_privacy = background_document.get("privacy")
    background_privacy = (
        background_privacy if isinstance(background_privacy, Mapping) else {}
    )
    matrix = background_document.get("background_matrix")
    declared_rows = background_document.get("n_background_rows")
    background_rows = len(matrix) if isinstance(matrix, Sequence) else None
    background_panel_sha = background_document.get("panel_contract_sha256")
    if (
        background_privacy.get("synthetic_only") is not True
        or background_panel_sha != entry.panel_contract_sha256
        or background_document.get("panel_id") != entry.panel_id
        or background_rows is None
        or declared_rows != background_rows
    ):
        raise ResearchRegistryError(
            "artifact_shap_background_provenance_invalid",
            "The artifact SHAP background is not a panel-bound synthetic training derivative.",
            field="shap_background",
        )

    def _finite(value: Any) -> float | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        number = float(value)
        return number if isfinite(number) else None

    lime_supported = shap_supported and entry.lime_supported
    if not shap_supported:
        lime_reason = shap_reason
    elif not entry.lime_supported:
        lime_reason = "model_entry_does_not_advertise_lime"
    else:
        lime_reason = None

    return ArtifactCapabilities(
        calibration_supported=calibration_supported,
        calibration_status=declared_calibration,
        calibrator_status=calibrator_status,
        calibration_input_link=str(calibrator.input_link),
        calibration_fit_scope=str(calibrator.fit_scope),
        development_prevalence=_finite(calibrator.development_prevalence),
        n_oof_samples=int(calibrator.n_oof_samples),
        oof_brier_before=_finite(calibrator.oof_brier_before),
        oof_brier_after=_finite(calibrator.oof_brier_after),
        unsupported_calibration_reason=calibration_reason,
        shap_supported=shap_supported,
        shap_method=None if shap_reason else str(declared_method or expected_method or ""),
        shap_explained_quantity=None if shap_reason else _as_optional_str(xai.get("explained_quantity")),
        shap_scale=None if shap_reason else _as_optional_str(xai.get("scale")),
        shap_additive_on_calibrated_probability=bool(
            xai.get("additive_on_calibrated_probability") is True
        ),
        shap_background_sample_count=background_rows,
        shap_background_synthetic_only=True,
        shap_background_panel_bound=True,
        shap_background_encoded_feature_count=(
            len(background_document.get("encoded_feature_names") or ())
            if isinstance(background_document.get("encoded_feature_names"), Sequence)
            else None
        ),
        lime_supported=lime_supported,
        lime_unsupported_reason=lime_reason,
    )


def _as_optional_str(value: Any) -> str | None:
    return None if value is None else str(value)


__all__ = [
    "ADMISSIBLE_ARTIFACT_KINDS",
    "ARTIFACT_KIND_SYNTHETIC_BUNDLE",
    "CALIBRATION_STATUS_SUPPORTED",
    "CALIBRATOR_STATUS_FITTED",
    "CALIBRATOR_STATUS_IDENTITY_FALLBACK",
    "EVIDENCE_LEVEL_NOT_EVALUATED",
    "EVIDENCE_LEVEL_SYNTHETIC_TEST",
    "EXECUTABLE_ENTRY_STATES",
    "KNOWN_ENTRY_STATES",
    "MAX_RECORDS_CEILING",
    "NON_EXECUTABLE_ENTRY_STATES",
    "REGISTRY_SCHEMA_VERSION",
    "REGISTRY_VERSION",
    "REGISTRY_DIGEST_SHA256",
    "REGISTRY_ROUTE_IDS",
    "RESEARCH_MODEL_REGISTRY",
    "ArtifactCapabilities",
    "ENTRY_STATE_ACTIVE",
    "ENTRY_STATE_BLOCKED_PENDING_AUTHORIZATION",
    "ENTRY_STATE_BLOCKED_SOURCE_TIMING",
    "ENTRY_STATE_LOCKED_EXTERNAL_TARGET",
    "ResearchModelEntry",
    "ResearchRegistryError",
    "ResolvedRegistryBinding",
    "SYNTHETIC_PROVENANCE_DECLARATION",
    "assert_artifact_identity",
    "binding_for_entry",
    "derive_artifact_capabilities",
    "get_model_entry",
    "registry_contract",
    "registry_digest_sha256",
    "resolve_registered_model",
]
