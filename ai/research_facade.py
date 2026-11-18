"""AI-11.1 — unified typed offline research inference facade (synthetic-only).

One entry point, :func:`run_offline_research_inference`, turns a typed request
into a typed response by *composing* the already-reviewed AI components. It adds
no training, scoring, calibration, explanation or packaging engine of its own:

* registry, route, panel and version binding — :mod:`ai.research_registry`
* operation and input-context eligibility — :func:`ai.research_routes.resolve_route`
* record contract (names, types, units, codes, missingness, and the prohibited
  leakage / Track-B / wearable fields) — :func:`ai.panels.validate_clinical_record`
* artifact provenance gate, run before anything is deserialized —
  :func:`ai.cli.assert_cli_predict_supported`
* bundle integrity, local producer authentication and access control —
  :func:`ai.packaging.verify_trusted_local_bundle`
* calibrator and SHAP-background re-validation — :mod:`ai.calibration`
* score, cross-fitted calibration, fold dispersion, exact SHAP, certified LIME
  and the LIME quality verdict — :class:`ai.inference.ResearchCadPredictor`

Result semantics (exactly four, never more)
-------------------------------------------
``SYNTHETIC_RESULT``
    A numeric synthetic research score was produced. It is a research score on
    a fabricated fixture, never a clinical CAD probability.
``ABSTAIN``
    The record is admissible but the registered inference policy declines to
    score it (today: a registered optional-field abstention). No score is
    produced and none is estimated.
``UNAVAILABLE``
    A registered contract that cannot currently be executed, or a capability
    the verified artifact does not provide (blocked route entry, locked
    external target, unsupported calibration). Reported with a machine-readable
    reason; never silently replaced by a raw score or a fallback model.
``ERROR``
    The request, the record, or the artifact failed a validation or security
    check: unknown identifiers, version/hash mismatch, invalid value/type/unit,
    prohibited leakage or wearable input, forged synthetic provenance,
    untrusted or tampered bundle.

Security and honesty properties enforced here
---------------------------------------------
* A caller-supplied ``"synthetic": true`` is never treated as evidence. A
  record must carry a structured fabricated-fixture declaration whose generator
  is on the entry's pinned allowlist, **and** the artifact itself must attest
  synthetic-only provenance through :mod:`ai.packaging`. Either side alone
  fails closed.
* Nothing is deserialized until
  :func:`ai.packaging.verify_trusted_local_bundle` and the provenance gate have
  passed; the predictor re-verifies before ``joblib.load``.
* Responses never contain a filesystem path, feature value, record content,
  key material, or exception text: error details are a registered code plus a
  static message plus an optional registered field name.
* No HTTP route, no new provider, no environment switch, no settings file.
  ``backend/app/`` never imports this module and ``/v1`` is unchanged.
* Calibration and SHAP/LIME are reported only when the *verified artifact*
  supports them; an unsupported calibration is reported as absent with a reason
  and the raw model probability keeps its ``NOT_CALIBRATED`` label.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import hmac
import json
import math
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Final, Mapping, Sequence

from scipy.special import expit

from ai.calibration import OofLogisticCalibrator
from ai.cli import assert_cli_predict_supported
from ai.errors import AiPipelineError, ClinicalInputValidationError
from ai.explainability import ADDITIVITY_TOLERANCE
from ai.inference import MANDATORY_LIMITATIONS, ResearchCadPredictor
from ai.lime_explainability import (
    ALLOWED_LIME_REFERENCE_SCHEMES,
    MAX_LIME_PERTURBATIONS,
    LimeConfig,
)
from ai.packaging import (
    CALIBRATION_FILENAME,
    SHAP_BG_FILENAME,
    VerifiedBundleDescriptor,
    verify_trusted_local_bundle,
)
from ai.panels import (
    REGISTERED_PANELS,
    ResearchPanelContract,
    ValidatedClinicalRecord,
    validate_clinical_record,
)
from ai.research_registry import (
    ADMISSIBLE_SYNTHETIC_PROVENANCE_DECLARATIONS,
    KNOWN_OPERATIONS,
    MAX_RECORDS_CEILING,
    RESEARCH_MODEL_REGISTRY,
    SAFE_DATASET_ID_RE,
    SHA256_RE,
    ArtifactCapabilities,
    ResearchModelEntry,
    ResearchRegistryError,
    ResolvedRegistryBinding,
    SAFE_RECORD_REF_RE,
    SYNTHETIC_PROVENANCE_DECLARATION,
    assert_artifact_identity,
    binding_for_entry,
    derive_artifact_capabilities,
    registry_digest_sha256,
    resolve_registered_model,
)
from ai.research_routes import (
    OP_SYNTHETIC_PREDICTION,
    RESEARCH_ROUTE_CATALOG,
    UCI45_RESTING_FIXTURE_BOUNDS,
    resolve_route,
)

REQUEST_SCHEMA_VERSION: Final[str] = "cardioassist.ai.research_inference_request/v1"
RESPONSE_SCHEMA_VERSION: Final[str] = "cardioassist.ai.research_inference_response/v1"
FACADE_ID: Final[str] = "cardioassist.ai.research_facade/v1"

#: Only this operation is reachable through the facade. There is deliberately no
#: real-data, external-evaluation, bundle-inference or serving operation.
FACADE_OPERATION: Final[str] = OP_SYNTHETIC_PREDICTION

SCORE_KIND_CALIBRATED: Final[str] = "CALIBRATED_RESEARCH_SCORE_SYNTHETIC"
SCORE_KIND_RAW: Final[str] = "RAW_MODEL_PROBABILITY_NOT_CALIBRATED"
SCORE_INTERPRETATION: Final[str] = "RESEARCH_ONLY_NOT_INDIVIDUAL_CLINICAL_RISK"
ACQUISITION_STAGE_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
#: Structural fallback for a refusal whose code or stage is not registered.
GENERIC_ERROR_CODE: Final[str] = "facade_internal_error"
GENERIC_ERROR_MESSAGE: Final[str] = (
    "The request was refused by a registered fail-closed check."
)
_ERROR_CODE_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9_]{2,64}$")
ARTIFACT_KIND_LABEL: Final[str] = "local_verified_synthetic_bundle"
SUPPORTED_SYNTHETIC_INPUT_SOURCE: Final[str] = "structured_synthetic_research"
SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE: Final[str] = "SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE"


class ResearchFacadeStatus(str, Enum):
    """The four and only four explicit facade outcomes."""

    SYNTHETIC_RESULT = "SYNTHETIC_RESULT"
    ABSTAIN = "ABSTAIN"
    UNAVAILABLE = "UNAVAILABLE"
    ERROR = "ERROR"

    @property
    def produced_a_score(self) -> bool:
        return self is ResearchFacadeStatus.SYNTHETIC_RESULT


#: Roll-up precedence for the response-level status (documented, deterministic).
STATUS_PRECEDENCE: Final[tuple[ResearchFacadeStatus, ...]] = (
    ResearchFacadeStatus.ERROR,
    ResearchFacadeStatus.UNAVAILABLE,
    ResearchFacadeStatus.ABSTAIN,
    ResearchFacadeStatus.SYNTHETIC_RESULT,
)

FACADE_LIMITATIONS: Final[tuple[str, ...]] = (
    "Every numeric output is a SYNTHETIC research score computed on a deliberately "
    "fabricated fixture by an offline research artifact: it is not a clinical CAD "
    "probability, not validated individual risk, and not external validation.",
    "The registry and facade are offline research tooling only: no HTTP endpoint, no "
    "provider switch, no serving entitlement, and no real-artifact path exists here.",
    "UNAVAILABLE and ABSTAIN are final answers for that request: nothing is imputed, "
    "substituted, downgraded to a fallback model, or relabelled to produce a number.",
)

#: Registry codes that mean "a registered contract exists but cannot currently
#: execute" and are therefore reported as ``UNAVAILABLE`` rather than ``ERROR``.
_UNAVAILABLE_REGISTRY_CODES: Final[frozenset[str]] = frozenset(
    {
        "model_entry_blocked_pending_authorization",
        "model_entry_blocked_source_timing_unverified",
        "model_entry_locked_external_target",
    }
)

#: Static, value-free explanations for the typed refusals this facade emits.
#:
#: Codes owned by the reused component boundaries (panel validation, bundle
#: verification, packaging, calibration, explainability) are passed through
#: *by code* — the authoritative machine-readable reason — and rendered with
#: their registered sentence where one is listed here. Any code not listed
#: falls back to one registered generic sentence. Exception text is never
#: echoed, because it can carry a submitted value or a local path.
_ERROR_MESSAGES: Final[Mapping[str, str]] = MappingProxyType(
    {
        "request_not_a_dataclass": "The facade accepts one typed request object of the registered request type.",
        "request_schema_version_unsupported": "The request carries a schema version this facade does not implement.",
        "model_source_not_allowed": "The artifact source is not the registered local synthetic bundle source.",
        "facade_operation_not_supported": "Only the registered offline synthetic prediction operation is reachable through this facade.",
        "unknown_model_entry": "No research model entry is registered for this model id and version.",
        "route_id_mismatch": "The request route id does not match the registry binding.",
        "route_version_mismatch": "The request route version does not match the registry binding.",
        "dataset_id_mismatch": "The request dataset id does not match the registry binding.",
        "panel_id_mismatch": "The request panel id does not match the registry binding.",
        "panel_version_mismatch": "The request panel version does not match the registry binding.",
        "panel_contract_hash_invalid": "The request panel contract hash is not a lowercase SHA-256 digest.",
        "panel_contract_hash_mismatch": "The request panel contract hash does not match the pinned panel contract.",
        "operation_unknown": "The requested operation is not a registered research operation.",
        "operation_not_permitted_for_model_entry": "The requested operation is not permitted for this model entry.",
        "operation_not_permitted_for_route": "The requested operation is not permitted for this route.",
        "record_count_exceeds_ceiling": "The request exceeds the registered per-invocation record ceiling.",
        "empty_record_set": "The request carries no records to evaluate.",
        "duplicate_record_ref": "Record references must be unique within one request.",
        "invalid_record_ref": "The record reference is outside the registered identifier grammar.",
        "unexpected_record_key": "The record carries a key outside the registered record grammar.",
        "synthetic_flag_is_not_provenance": "A boolean 'synthetic' flag is not admissible provenance; a fabricated-fixture declaration is required.",
        "synthetic_provenance_missing": "The record carries no synthetic fixture provenance declaration.",
        "synthetic_provenance_malformed": "The synthetic provenance block is not a mapping of registered keys.",
        "record_not_a_dataclass": "Each record must be a mapping in the registered record grammar.",
        "synthetic_provenance_declaration_unknown": "The declared provenance declaration is not the registered fabricated-fixture declaration.",
        "synthetic_provenance_generator_not_admissible": "The declared fixture generator is not on this entry's pinned generator allowlist.",
        "outside_synthetic_fixture_envelope": "A measurement lies outside the declared synthetic generator's output envelope.",
        "synthetic_provenance_seed_invalid": "The declared fixture seed is not a non-negative 63-bit integer.",
        "synthetic_provenance_fixture_ref_invalid": "The declared fixture reference is outside the registered identifier grammar.",
        "input_source_not_admissible": "The declared input source is not the registered structured synthetic research source.",
        "acquisition_stage_missing": "The record declares no acquisition stage.",
        "acquisition_stage_invalid": "The declared acquisition stage is outside the registered stage vocabulary.",
        "acquisition_stage_precedence_violation": "A supplied field originates from a later acquisition stage than the record declares.",
        "record_panel_id_mismatch": "The record panel id does not match the request panel id.",
        "bundle_verification_failed": "The artifact failed trusted-local verification; nothing was deserialized.",
        "cli_real_provenance_bundle_not_supported": "The artifact does not carry synthetic research provenance; this facade never loads or scores it.",
        "cli_execution_profile_not_supported": "The artifact execution profile is outside the synthetic research profile this facade supports.",
        "artifact_identity_mismatch": "The verified artifact does not match the registry binding for the requested version.",
        "artifact_capability_declaration_mismatch": "The verified artifact does not provide the reviewed explainability capability.",
        "artifact_unsupported_calibration": "The verified artifact provides no fitted calibrator; a raw score is reported as raw.",
        "prediction_integrity_check_failed": "The produced numbers failed a fail-closed consistency check and were withheld.",
        "explainability_options_invalid": "The requested explainability options are outside the registered bounds.",
        "explainer_unavailable": "No explanation could be produced for this record from this artifact.",
        "record_input_invalid": "The record failed the registered panel input contract.",
        "record_not_a_dataclass": "Each record must be a registered typed record object.",
        "unexpected_request_key": "The request carries a key outside the registered request grammar.",
        "unexpected_provenance_key": "The synthetic provenance block carries an unregistered key.",
        "exploratory_threshold_invalid": "The exploratory threshold must be a finite number strictly inside (0, 1).",
        "route_not_registered": "The route referenced by the registry entry is not in the route catalog.",
        "panel_unregistered": "The panel referenced by the registry entry is not in the panel registry.",
        "registry_real_artifact_not_registerable": "Real-patient research artifacts are not registerable in this synthetic-only registry.",
        "artifact_model_id_mismatch": "The verified artifact model id does not match the registry binding.",
        "artifact_model_version_mismatch": "The verified artifact model version does not match the registry binding.",
        "artifact_protocol_id_mismatch": "The verified artifact protocol id does not match the registry binding.",
        "artifact_execution_profile_mismatch": "The verified artifact execution profile does not match the registry binding.",
        "artifact_panel_id_mismatch": "The verified artifact panel id does not match the registry binding.",
        "artifact_panel_version_mismatch": "The verified artifact panel version does not match the registry binding.",
        "artifact_panel_hash_mismatch": "The verified artifact panel contract hash does not match the pinned hash.",
        "artifact_target_id_mismatch": "The verified artifact target id does not match the registry binding.",
        "artifact_feature_order_mismatch": "The verified artifact feature order does not match the registered panel order.",
        "artifact_model_family_not_allowed": "The artifact model family is not allowed for this route.",
        "artifact_model_family_unregistered": "The artifact model family has no registered explainability method.",
        "artifact_real_provenance_not_supported": "The artifact carries a real research-authorization context and is never loaded here.",
        "artifact_synthetic_provenance_absent": "The artifact does not attest synthetic-only training provenance.",
        "artifact_execution_mode_not_synthetic": "The artifact execution mode is not the synthetic research mode.",
        "artifact_serving_claim_rejected": "The artifact declares a serving or clinical-use claim, which research artifacts never make.",
        "artifact_development_dataset_mismatch": "The artifact development dataset does not match the registered route.",
        "artifact_development_cohort_not_marked_synthetic": "The artifact development cohort does not declare a synthetic cohort.",
        "artifact_pooled_cohorts_rejected": "Pooled-cohort artifacts are never admissible in this registry.",
        "artifact_bundle_schema_mismatch": "The artifact bundle schema version is not the one this registry describes.",
        "artifact_manifest_unavailable": "No verified bundle manifest was available for the identity check.",
        "artifact_shap_background_provenance_invalid": "The artifact SHAP background is not a panel-bound synthetic training derivative.",
        "artifact_explainability_method_mismatch": "The artifact explainability method does not match its registered model family.",
        "cli_non_synthetic_input_not_supported": "This offline facade accepts only declared synthetic research inputs.",
        "unregistered_panel": "The record names a panel that is not registered.",
        "malformed_payload": "The record payload does not have the registered structure.",
        "malformed_context": "The record input context does not have the registered structure.",
        "unexpected_envelope_key": "The record envelope carries an unregistered key.",
        "invalid_synthetic_flag": "The synthetic flag must be an explicit boolean.",
        "non_synthetic_input_rejected": "The record does not declare synthetic provenance; Gate PT remains closed.",
        "synthetic_disguise_in_real_record": "A synthetic flag on a real-provenance record is rejected.",
        "prohibited_leakage_or_wearable_field": "The record supplies a prohibited outcome, angiography, echocardiography, or wearable field.",
        "wearable_or_track_b_rejected": "The record declares a Track B or wearable input context, which is never a CAD predictor here.",
        "unregistered_feature_for_panel": "The record supplies a field that is not part of the registered panel.",
        "missing_required_field": "A required panel field is omitted or null.",
        "missing_reason_mismatch": "Every omitted or null optional field requires exactly one registered missing reason.",
        "invalid_missing_reason": "The supplied missing reason is not a registered missing reason.",
        "unit_keys_mismatch": "Measured fields with physical units require exact unit entries and no extra ones.",
        "unit_mismatch": "A supplied unit token does not match the registered unit for that field.",
        "invalid_numeric_value": "A supplied numeric value is not a finite real measurement.",
        "zero_measurement_unavailable": "A zero value for this field denotes an unmeasured value, not a measurement.",
        "value_out_of_plausible_range": "A supplied value is outside the registered plausibility bounds.",
        "invalid_categorical_type": "A supplied categorical value has the wrong type.",
        "unknown_categorical_code": "A supplied categorical code is not in the registered vocabulary.",
        "unknown_categorical_token": "A supplied categorical token is not in the registered vocabulary.",
        "record_unexpected_error": "The record could not be evaluated; it was refused without partial output.",
        "request_unexpected_error": "The request could not be processed; it was refused without partial output.",
        # --- codes passed through from the reused component boundaries ------- #
        # These are registered integrity/eligibility codes of ai.packaging,
        # ai.inference, ai.explainability and ai.research_routes. The code is
        # reported verbatim; the originating exception message never is.
        "untrusted_bundle_location": "The artifact is not located inside the declared trusted local root.",
        "artifact_digest_mismatch": "An artifact file does not match its recorded SHA-256 digest.",
        "artifact_content_mismatch": "An artifact file does not match its recorded content.",
        "file_size_mismatch": "An artifact file size does not match the recorded manifest entry.",
        "file_digest_mismatch": "An artifact file digest does not match the recorded manifest entry.",
        "missing_local_producer_attestation": "The artifact carries no local producer attestation; digests alone are not authenticity.",
        "untrusted_bundle_producer_signature": "The artifact producer attestation failed verification; nothing was deserialized.",
        "shap_additivity_check_failed": "The attribution values did not reproduce the score they explain, so no number was reported.",
        "file_sha256_mismatch": "An artifact file does not match the SHA-256 recorded in the verified manifest.",
        "bundle_file_missing": "An artifact file listed in the verified manifest is absent.",
        "unsafe_bundle_filename": "An artifact filename is outside the registered bundle member vocabulary.",
        "unexpected_bundle_directory_contents": "The artifact directory contains an unregistered file.",
        "bundle_symlink_prohibited": "The artifact directory contains a symbolic link, which is never followed.",
        "insecure_bundle_permissions": "The artifact file permissions are not private.",
        "insecure_trusted_root_permissions": "The trusted local root does not meet the private access-control policy.",
        "untrusted_bundle_owner": "The artifact is not owned by the current user.",
        "untrusted_root_owner": "The trusted local root is not owned by the current user.",
        "invalid_trusted_local_root": "The declared trusted local root is not an existing private directory.",
        "insecure_signing_key_permissions": "The signing key material is not privately protected.",
        "invalid_local_signing_key": "The local signing key is not a registered HMAC key.",
        "cli_non_synthetic_input_not_supported": "This offline facade accepts only declared synthetic research artifacts.",
        "cli_trusted_root_required": "A trusted local root is required before any artifact is opened.",
        "malformed_manifest_json": "The artifact manifest is not valid UTF-8 JSON.",
        "unsupported_bundle_schema": "The artifact bundle schema version is not supported.",
        "unauthorized_serving_claim": "The artifact manifest makes a serving or clinical-use claim.",
        "real_patient_bundle_blocked_gate_pt_closed": "Gate PT remains closed; real-patient artifacts are never loaded here.",
        "insecure_bundle_permissions": "The artifact directory or file permissions are not private.",
        "insecure_trusted_root_permissions": "The trusted local root does not meet the private access-control policy.",
        "bundle_not_authenticated_for_deserialization": "The artifact is not authenticated for deserialization.",
        "invalid_model_container": "The deserialized artifact container has an unexpected structure.",
        "execution_profile_container_mismatch": "The artifact execution profile is inconsistent across its own sections.",
        "model_family_container_mismatch": "The artifact model family is inconsistent across its own sections.",
        "estimator_fitted_width_mismatch": "The fitted estimator width does not match the declared profile and family.",
        "missing_fold_ensemble": "The artifact lacks its outer-fold ensemble members.",
        "missing_fold_member_calibrator": "An outer-fold ensemble member lacks its own calibrator.",
        "fold_calibrator_family_mismatch": "An outer-fold calibrator does not match its estimator family.",
        "calibrated_log_odds_explanation_misaligned": "The SHAP target does not match the calibrated score.",
        "raw_score_explanation_misaligned": "The SHAP target does not match the raw model score.",
        "lime_quality_unacceptable": "The generated LIME explanation failed the registered quality policy.",
        "lime_invalid_config": "The LIME generation configuration is outside the registered bounds.",
        "unsupported_input_source": "The declared input source is not a registered synthetic research source.",
        "track_not_a": "The declared input context is not Track A.",
        "synthetic_declaration_missing_or_false": "The declared input context does not assert a synthetic fixture.",
        "real_data_input_context_rejected": "The declared input context references real data.",
        "missing_input_context": "The record carries no declared input context.",
        "no_matching_route": "No registered route matches the declared dataset, panel and input context.",
        "ambiguous_route": "More than one route matches; the resolver refuses to guess.",
        "operation_forbidden_for_route": "The requested operation is forbidden for this route.",
        "operation_not_permitted_for_route": "The requested operation is not permitted for this route.",
        "invalid_dataset_id": "The declared dataset id is invalid.",
        "invalid_panel_id": "The declared panel id is invalid.",
        "invalid_operation": "The declared operation is invalid.",
        "unknown_operation": "The declared operation is not a registered operation.",
        "unknown_categorical_code": "A supplied categorical code is outside the registered vocabulary.",
        "unknown_categorical_token": "A supplied categorical token is outside the registered vocabulary.",
        "invalid_categorical_type": "A supplied categorical value has an invalid type.",
        "model_entry_not_executable": "This model entry is registered for contract inspection only.",
        GENERIC_ERROR_CODE: GENERIC_ERROR_MESSAGE,
    }
)

#: Codes whose refusal is about one *registered-but-blocked* contract.
_UNAVAILABLE_ROUTE_REJECTIONS: Final[frozenset[str]] = frozenset(
    {
        "operation_not_permitted_for_route",
        "operation_forbidden_for_route",
        "no_matching_route",
    }
)


# --------------------------------------------------------------------------- #
# Typed inputs                                                                 #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class SyntheticFixtureProvenance:
    """A structured claim that one record came from a fabricated fixture.

    This is an *assertion about the input*, checked against the model entry's
    pinned generator allowlist. It is never treated as evidence about the
    artifact, and it never substitutes for artifact provenance verification.
    """

    declaration: str
    fixture_ref: str
    generator_id: str
    seed: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "declaration": self.declaration,
            "fixture_ref": self.fixture_ref,
            "generator_id": self.generator_id,
            "seed": self.seed,
            "treated_as_evidence_about_artifact": False,
        }


@dataclass(frozen=True, slots=True)
class ResearchFeatureRecord:
    """One typed, panel-scoped input record submitted for research scoring."""

    record_ref: str
    features: Mapping[str, Any]
    units: Mapping[str, str] = field(default_factory=dict)
    missing_reasons: Mapping[str, str] = field(default_factory=dict)
    acquisition_stage: str | None = None
    input_source: str = "structured_synthetic_research"
    panel_id: str | None = None
    provenance: SyntheticFixtureProvenance | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "features", MappingProxyType(dict(self.features)))
        object.__setattr__(self, "units", MappingProxyType(dict(self.units)))
        object.__setattr__(
            self, "missing_reasons", MappingProxyType(dict(self.missing_reasons))
        )

    def to_panel_payload(self, panel_id: str) -> dict[str, Any]:
        """Project onto the envelope :func:`ai.panels.validate_clinical_record` accepts."""
        return {
            "synthetic": True,
            "panel_id": self.panel_id or panel_id,
            "features": dict(self.features),
            "units": dict(self.units),
            "missing_reasons": dict(self.missing_reasons),
            "context": {
                "track": "A",
                "source": self.input_source,
                "acquisition_stage": self.acquisition_stage,
            },
        }

    def route_input_context(self) -> dict[str, Any]:
        """The declared input context handed to :func:`ai.research_routes.resolve_route`."""
        return {
            "track": "A",
            "source": self.input_source,
            "synthetic": True,
        }


@dataclass(frozen=True, slots=True)
class ExplainabilityOptions:
    """Optional explanation request. Absence is an honest answer, never a guess."""

    include_shap: bool = True
    include_lime: bool = False
    lime_reference_scheme: str | None = None
    lime_num_perturbations: int | None = None
    lime_seed: int | None = None
    lime_require_acceptable_quality: bool = False

    def to_lime_config(self) -> LimeConfig | None:
        """Build the registered LIME generation config, fail closed.

        Every bound (perturbation ceiling, seed type, reference-scheme
        vocabulary, batch ceilings) is enforced by :class:`LimeConfig` itself;
        this method only translates that refusal into the facade's request
        grammar error so a caller sees one error surface for malformed options
        and never a partially-applied explanation configuration.
        """
        if not self.include_lime:
            return None
        kwargs: dict[str, Any] = {}
        if self.lime_num_perturbations is not None:
            kwargs["num_perturbations"] = self.lime_num_perturbations
        if self.lime_seed is not None:
            kwargs["seed"] = self.lime_seed
        if self.lime_reference_scheme is not None:
            kwargs["reference_scheme"] = self.lime_reference_scheme
        try:
            return LimeConfig(**kwargs)
        except AiPipelineError as exc:
            raise ResearchRegistryError(
                "explainability_options_invalid",
                "The requested LIME options are outside the registered bounds; no "
                "explanation is generated rather than one generated from defaults.",
                field="explainability",
            ) from exc

    def to_dict(self) -> dict[str, Any]:
        return {
            "include_shap": self.include_shap,
            "include_lime": self.include_lime,
            "lime_reference_scheme": (
                self.lime_reference_scheme
                if self.lime_reference_scheme is not None
                else "fixed_background_reference"
            ),
            "lime_num_perturbations": self.lime_num_perturbations,
            "lime_seed": self.lime_seed,
            "lime_require_acceptable_quality": self.lime_require_acceptable_quality,
        }


@dataclass(frozen=True, slots=True)
class LocalSyntheticBundleSource:
    """The only admissible artifact source: a local, trusted-root-bounded bundle.

    Paths exist so the existing verified loader can be reused; they are never
    copied into a response. The signing key is excluded from ``repr`` so it
    cannot leak through logs or exception traces.
    """

    bundle_dir: Path
    trusted_local_root: Path
    signing_key: bytes | None = field(default=None, repr=False, compare=False)

    @property
    def artifact_kind(self) -> str:
        return "local_verified_synthetic_bundle"

    def safe_descriptor(self) -> dict[str, Any]:
        """Path-free identity of the source (basename only, as the CLI reports)."""
        return {
            "artifact_kind": self.artifact_kind,
            "bundle_dir_name": Path(self.bundle_dir).name,
            "signing_key_provided": self.signing_key is not None,
            "remote_or_url_source_supported": False,
        }


@dataclass(frozen=True, slots=True)
class ResearchInferenceRequest:
    """Fully explicit, versioned request. Nothing about it is defaulted."""

    request_schema_version: str
    operation: str
    route_id: str
    route_version: str
    model_id: str
    model_version: str
    panel_id: str
    panel_version: str
    panel_contract_sha256: str
    dataset_id: str
    records: tuple[ResearchFeatureRecord, ...]
    model_source: LocalSyntheticBundleSource
    exploratory_threshold: float = 0.5
    explainability: ExplainabilityOptions = field(default_factory=ExplainabilityOptions)

    @property
    def record_count(self) -> int:
        return len(self.records)

    def to_safe_dict(self) -> dict[str, Any]:
        """Request summary with no record content and no filesystem path.

        The projection is *validated*, not merely copied: an identifier is
        echoed only when it resolves against the registry, route catalog, panel
        registry or operation vocabulary, and a version or hash only when it
        matches its grammar. A request constructed directly (bypassing
        :func:`parse_inference_request`) can therefore never place an
        unvalidated identifier, path or nested object in a response — such a
        value becomes ``None`` and its field name is listed in
        ``redacted_fields`` instead.

        A request cannot attest to its own validation, so this view is the
        conservative one: record references and the bundle directory basename
        are withheld (only the bounded counts are reported). The facade rebuilds
        the summary with correlation enabled for the response that a validated
        request actually produced a result for.
        """
        return build_request_summary(self)


# --------------------------------------------------------------------------- #
# Typed outputs                                                                #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class FacadeErrorDetail:
    """Typed refusal: a registered code, a static message, a registered field.

    The stored values are *normalized*, not passed through: the message is
    always the registered sentence for the code, an unregistered code becomes
    the generic code, and an unregistered stage becomes the last registered
    stage. A refusal therefore cannot carry submitted content, exception text,
    or a local path even if a caller tries to construct one that does.
    """

    code: str
    message: str
    field_name: str | None
    stage: str

    def __post_init__(self) -> None:
        code = (
            self.code
            if isinstance(self.code, str) and _ERROR_CODE_RE.fullmatch(self.code)
            else GENERIC_ERROR_CODE
        )
        stage = self.stage if self.stage in PIPELINE_STAGES else PIPELINE_STAGES[-1]
        object.__setattr__(self, "code", code)
        object.__setattr__(self, "stage", stage)
        object.__setattr__(self, "message", _ERROR_MESSAGES.get(code, GENERIC_ERROR_MESSAGE))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "field": self.field_name,
            "stage": self.stage,
            "input_values_echoed": False,
            "local_paths_echoed": False,
        }


@dataclass(frozen=True, slots=True)
class ResearchScoreBlock:
    """The numeric research output, with its scale declared next to it."""

    kind: str
    raw_model_score: float
    raw_model_log_odds: float
    calibrated_research_score: float | None
    calibrated_log_odds: float | None
    calibration_reason: str | None
    exploratory_threshold: float
    exploratory_above_threshold: bool
    threshold_clinically_validated: bool
    interpretation: str
    clinical_probability_claim: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "score_kind": self.kind,
            "raw_model_score": self.raw_model_score,
            "raw_model_log_odds": self.raw_model_log_odds,
            "calibrated_research_score": self.calibrated_research_score,
            "calibrated_log_odds": self.calibrated_log_odds,
            "calibration_reason": self.calibration_reason,
            "scale_declaration": (
                "calibrated_research_score = expit(intercept + slope * raw_log_odds) "
                "on the calibrated log-odds scale fitted on development out-of-fold "
                "predictions; raw_model_score is the uncalibrated model probability."
                if self.kind == SCORE_KIND_CALIBRATED
                else "raw_model_score is the uncalibrated model probability; no "
                "calibrated quantity is reported because the artifact provides none."
            ),
            "exploratory_threshold": self.exploratory_threshold,
            "exploratory_above_threshold_flag": self.exploratory_above_threshold,
            "exploratory_threshold_clinically_validated": self.threshold_clinically_validated,
            "score_interpretation": self.interpretation,
            "clinical_probability_claim": self.clinical_probability_claim,
        }


@dataclass(frozen=True, slots=True)
class ShapExplanationBlock:
    provided: bool
    reason: str | None
    explained_quantity: str | None
    scale: str | None
    sum_check_passed: bool | None
    max_abs_discrepancy: float | None
    method: str | None
    background_sample_count: int | None
    background_synthetic_only: bool | None
    additive_on_calibrated_probability: bool | None
    attribution_feature_names: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "provided": self.provided,
            "reason": self.reason,
            "explained_quantity": self.explained_quantity,
            "scale": self.scale,
            "method": self.method,
            "sum_check_passed": self.sum_check_passed,
            "max_abs_discrepancy": self.max_abs_discrepancy,
            "additive_on_calibrated_probability": (
                self.additive_on_calibrated_probability
            ),
            "background": {
                "sample_count": self.background_sample_count,
                "synthetic_only": self.background_synthetic_only,
                "contains_patient_records": False,
            },
            "attribution_feature_names": list(self.attribution_feature_names),
        }


@dataclass(frozen=True, slots=True)
class LimeExplanationBlock:
    provided: bool
    reason: str | None
    payload: Mapping[str, Any] | None
    quality_status: str | None
    is_reliable_for_interpretation: bool | None
    comparable_with_shap: bool | None
    explained_quantity: str | None
    scale: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provided": self.provided,
            "reason": self.reason,
            "quality_status": self.quality_status,
            "is_reliable_for_interpretation": self.is_reliable_for_interpretation,
            "comparable_with_shap_scale": self.comparable_with_shap,
            "explained_quantity": self.explained_quantity,
            "scale": self.scale,
            "is_exact_shapley": False,
            "explanation": dict(self.payload) if self.payload is not None else None,
        }


@dataclass(frozen=True, slots=True)
class RecordOutcome:
    """One record's explicit result. Exactly one of the four statuses."""

    record_ref: str
    status: ResearchFacadeStatus
    score: ResearchScoreBlock | None = None
    shap: ShapExplanationBlock | None = None
    lime: LimeExplanationBlock | None = None
    uncertainty: Mapping[str, Any] | None = None
    present_fields: tuple[str, ...] = ()
    missing_fields_with_reason: tuple[tuple[str, str], ...] = ()
    abstention_reason: str | None = None
    unavailable_reason: str | None = None
    error: FacadeErrorDetail | None = None
    evidence_level: str = "SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE"

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "record_ref": self.record_ref,
            "status": self.status.value,
            "evidence_level": self.evidence_level,
            "present_fields": list(self.present_fields),
            "missing_fields_with_reason": [
                list(pair) for pair in self.missing_fields_with_reason
            ],
            "score": self.score.to_dict() if self.score is not None else None,
            "shap_explanation": self.shap.to_dict() if self.shap is not None else None,
            "lime_explanation": self.lime.to_dict() if self.lime is not None else None,
            "fold_dispersion": (
                dict(self.uncertainty) if self.uncertainty is not None else None
            ),
            "abstention_reason": self.abstention_reason,
            "unavailable_reason": self.unavailable_reason,
            "error": self.error.to_dict() if self.error is not None else None,
        }
        if self.status is not ResearchFacadeStatus.SYNTHETIC_RESULT:
            payload["score"] = None
        return payload


@dataclass(frozen=True, slots=True)
class ResearchInferenceResponse:
    """Immutable typed response of one facade call."""

    status: ResearchFacadeStatus
    binding: ResolvedRegistryBinding | None
    capabilities: ArtifactCapabilities | None
    outcomes: tuple[RecordOutcome, ...]
    artifact: Mapping[str, Any] | None
    error: FacadeErrorDetail | None
    request_summary: Mapping[str, Any]
    provenance: Mapping[str, Any]
    governance: Mapping[str, Any]
    limitations: tuple[str, ...]

    @property
    def counts(self) -> dict[str, int]:
        return {
            status.value: sum(1 for item in self.outcomes if item.status is status)
            for status in ResearchFacadeStatus
        }

    def to_dict(self) -> dict[str, Any]:
        binding = self.binding
        return {
            "response_schema_version": RESPONSE_SCHEMA_VERSION,
            "facade_id": FACADE_ID,
            "status": self.status.value,
            "evidence_level": (
                binding.entry.evidence_level
                if binding is not None
                else "NOT_EVALUATED_NO_SYNTHETIC_EXERCISE"
            ),
            "route_id": binding.route.route_id if binding is not None else None,
            "route_version": binding.route.route_version if binding is not None else None,
            "model_id": binding.entry.model_id if binding is not None else None,
            "model_version": binding.entry.model_version if binding is not None else None,
            "model_family": (
                self.artifact.get("selected_model_family")
                if self.artifact is not None
                else None
            ),
            "protocol_id": binding.entry.protocol_id if binding is not None else None,
            "panel_id": binding.panel.panel_id if binding is not None else None,
            "panel_version": binding.panel.panel_version if binding is not None else None,
            "panel_contract_sha256": (
                binding.panel.contract_sha256 if binding is not None else None
            ),
            "dataset_id": binding.route.dataset_id if binding is not None else None,
            "source_family": binding.route.source_family if binding is not None else None,
            "target_id": binding.route.target_id if binding is not None else None,
            "entry_state": binding.entry.entry_state if binding is not None else None,
            "registry": {
                "registry_digest_sha256": registry_digest_sha256(),
                "registry_entry_sha256": (
                    binding.entry.entry_sha256 if binding is not None else None
                ),
            },
            "counts": self.counts,
            "capabilities": (
                self.capabilities.to_dict() if self.capabilities is not None else None
            ),
            "artifact": dict(self.artifact) if self.artifact is not None else None,
            "records": [outcome.to_dict() for outcome in self.outcomes],
            "request_summary": dict(self.request_summary),
            "provenance": dict(self.provenance),
            "governance": dict(self.governance),
            "error": self.error.to_dict() if self.error is not None else None,
            "limitations": list(self.limitations),
        }

    def to_json(self, *, indent: int | None = None) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            indent=indent,
            ensure_ascii=True,
            allow_nan=False,
        )

    @property
    def response_digest_sha256(self) -> str:
        """SHA-256 over the canonical encoding of :meth:`to_dict`."""
        return canonical_response_digest(self.to_dict())


def canonical_response_digest(payload: Mapping[str, Any]) -> str:
    """Canonical SHA-256 of a facade response payload.

    Two identical calls on identical inputs must produce identical digests: this
    is what makes a research result citable, and it is why no wall-clock field
    is ever carried in a response.
    """
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# Strict request construction (used by the demo and any programmatic caller)   #
# --------------------------------------------------------------------------- #

_RECORD_KEYS: Final[frozenset[str]] = frozenset(
    {
        "record_ref",
        "features",
        "units",
        "missing_reasons",
        "acquisition_stage",
        "input_source",
        "panel_id",
        "synthetic_provenance",
    }
)
_PROVENANCE_KEYS: Final[frozenset[str]] = frozenset(
    {"declaration", "fixture_ref", "generator_id", "seed"}
)


def _reject_mapping(name: str, payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ResearchRegistryError(
            f"{name}_malformed",
            f"'{name}' must be a mapping.",
            field=name,
        )
    return {str(key): value for key, value in payload.items()}


def parse_synthetic_provenance(payload: Any) -> SyntheticFixtureProvenance:
    if payload is None:
        raise ResearchRegistryError(
            "synthetic_provenance_missing",
            "The record carries no synthetic fixture provenance declaration; a "
            "record without one is never scored.",
            field="synthetic_provenance",
        )
    document = _reject_mapping("synthetic_provenance", payload)
    if set(document) != _PROVENANCE_KEYS:
        raise ResearchRegistryError(
            "unexpected_provenance_key",
            "The synthetic provenance block must carry exactly the registered keys.",
            field="synthetic_provenance",
        )
    declaration = document["declaration"]
    if not isinstance(declaration, str) or declaration not in (
        ADMISSIBLE_SYNTHETIC_PROVENANCE_DECLARATIONS
    ):
        raise ResearchRegistryError(
            "synthetic_provenance_declaration_unknown",
            "Only the registered deliberately-fabricated fixture declaration is admissible.",
            field="synthetic_provenance.declaration",
        )
    fixture_ref = document["fixture_ref"]
    if not isinstance(fixture_ref, str) or not SAFE_RECORD_REF_RE.fullmatch(fixture_ref):
        raise ResearchRegistryError(
            "synthetic_provenance_fixture_ref_invalid",
            "The fixture reference is outside the registered identifier grammar.",
            field="synthetic_provenance.fixture_ref",
        )
    generator_id = document["generator_id"]
    seed = document["seed"]
    if not isinstance(generator_id, str) or not re.fullmatch(
        r"^[a-z0-9][a-z0-9_.-]{0,63}$", generator_id
    ):
        raise ResearchRegistryError(
            "synthetic_provenance_generator_not_admissible",
            "The declared fixture generator identifier is invalid.",
            field="synthetic_provenance.generator_id",
        )
    if isinstance(seed, bool) or not isinstance(seed, int) or not (0 <= seed < 2**63):
        raise ResearchRegistryError(
            "synthetic_provenance_seed_invalid",
            "The declared fixture seed must be a non-negative 63-bit integer.",
            field="synthetic_provenance.seed",
        )
    return SyntheticFixtureProvenance(
        declaration=declaration,
        fixture_ref=fixture_ref,
        generator_id=generator_id,
        seed=int(seed),
    )


def parse_feature_record(payload: Mapping[str, Any]) -> ResearchFeatureRecord:
    """Parse one record document; a bare ``synthetic`` flag is refused outright."""
    if not isinstance(payload, Mapping):
        raise ResearchRegistryError(
            "record_not_a_dataclass",
            "Each record must be a mapping in the registered record grammar.",
            field="records",
        )
    document = _reject_mapping("record", payload)
    if "synthetic" in document:
        raise ResearchRegistryError(
            "synthetic_flag_is_not_provenance",
            "A boolean 'synthetic' flag is not admissible provenance. Supply the "
            "structured synthetic_provenance block instead.",
            field="synthetic",
        )
    if set(document) - _RECORD_KEYS:
        raise ResearchRegistryError(
            "unexpected_record_key",
            "The record carries a key outside the registered record grammar.",
            field="record",
        )
    record_ref = document.get("record_ref")
    if not isinstance(record_ref, str) or not SAFE_RECORD_REF_RE.fullmatch(record_ref):
        raise ResearchRegistryError(
            "invalid_record_ref",
            "The record reference is outside the registered identifier grammar.",
            field="record_ref",
        )
    features = document.get("features")
    if not isinstance(features, Mapping) or not features:
        raise ResearchRegistryError(
            "record_input_invalid",
            "A record must supply a non-empty mapping of panel feature values.",
            field="features",
        )
    units = document.get("units", {})
    missing = document.get("missing_reasons", {})
    if not isinstance(units, Mapping) or not isinstance(missing, Mapping):
        raise ResearchRegistryError(
            "record_input_invalid",
            "'units' and 'missing_reasons' must be mappings.",
            field="units",
        )
    stage = document.get("acquisition_stage")
    if stage is not None and (
        not isinstance(stage, str) or not ACQUISITION_STAGE_RE.fullmatch(stage)
    ):
        raise ResearchRegistryError(
            "acquisition_stage_invalid",
            "The declared acquisition stage is outside the registered stage vocabulary.",
            field="acquisition_stage",
        )
    input_source = document.get("input_source", "structured_synthetic_research")
    if not isinstance(input_source, str):
        raise ResearchRegistryError(
            "input_source_not_admissible",
            "The declared input source must be a string.",
            field="input_source",
        )
    panel_id = document.get("panel_id")
    if panel_id is not None and not isinstance(panel_id, str):
        raise ResearchRegistryError(
            "record_panel_id_mismatch",
            "The record panel id must be a string when supplied.",
            field="panel_id",
        )
    provenance = parse_synthetic_provenance(document.get("synthetic_provenance"))
    return ResearchFeatureRecord(
        record_ref=record_ref,
        features=dict(features),
        units={str(k): str(v) for k, v in units.items()},
        missing_reasons={str(k): str(v) for k, v in missing.items()},
        acquisition_stage=stage,
        input_source=input_source,
        panel_id=panel_id,
        provenance=provenance,
    )


def parse_inference_request(
    payload: Mapping[str, Any],
    *,
    model_source: LocalSyntheticBundleSource,
) -> ResearchInferenceRequest:
    """Parse a strict request document. Unknown keys and defaults fail closed."""
    document = _reject_mapping("request", payload)
    allowed = {
        "request_schema_version",
        "operation",
        "route_id",
        "route_version",
        "model_id",
        "model_version",
        "panel_id",
        "panel_version",
        "panel_contract_sha256",
        "dataset_id",
        "records",
        "exploratory_threshold",
        "explainability",
    }
    if document.get("request_schema_version") != REQUEST_SCHEMA_VERSION:
        raise ResearchRegistryError(
            "request_schema_version_unsupported",
            "The request schema version is not implemented by this facade.",
            field="request_schema_version",
        )
    if set(document) - allowed:
        raise ResearchRegistryError(
            "unexpected_request_key",
            "The request carries a key outside the registered request grammar.",
            field="request",
        )
    records = document.get("records")
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
        raise ResearchRegistryError(
            "empty_record_set",
            "'records' must be a non-empty sequence of record documents.",
            field="records",
        )
    # The ceiling is checked on the raw sequence *before* parsing, so an
    # oversized document cannot spend work (or memory) on per-record validation
    # before being refused.
    if len(records) > MAX_RECORDS_CEILING:
        raise ResearchRegistryError(
            "record_count_exceeds_ceiling",
            "The request exceeds the registered per-invocation record ceiling.",
            field="records",
        )
    parsed = tuple(parse_feature_record(item) for item in records)
    explainability_document = document.get("explainability")
    if explainability_document is None:
        explainability = ExplainabilityOptions()
    else:
        ex = _reject_mapping("explainability", explainability_document)
        ex_allowed = {
            "include_shap",
            "include_lime",
            "lime_reference_scheme",
            "lime_num_perturbations",
            "lime_seed",
            "lime_require_acceptable_quality",
        }
        if set(ex) - ex_allowed:
            raise ResearchRegistryError(
                "explainability_options_invalid",
                "The explainability block carries a key outside the registered grammar.",
                field="explainability",
            )
        explainability = ExplainabilityOptions(
            include_shap=bool(ex.get("include_shap", True)),
            include_lime=bool(ex.get("include_lime", False)),
            lime_reference_scheme=ex.get("lime_reference_scheme"),
            lime_num_perturbations=ex.get("lime_num_perturbations"),
            lime_seed=ex.get("lime_seed"),
            lime_require_acceptable_quality=bool(
                ex.get("lime_require_acceptable_quality", False)
            ),
        )
    threshold = document.get("exploratory_threshold", 0.5)
    if (
        isinstance(threshold, bool)
        or not isinstance(threshold, (int, float))
        or not (math.isfinite(float(threshold)) and 0.0 < float(threshold) < 1.0)
    ):
        raise ResearchRegistryError(
            "exploratory_threshold_invalid",
            "The exploratory threshold must be a finite number strictly inside (0, 1).",
            field="exploratory_threshold",
        )
    return ResearchInferenceRequest(
        request_schema_version=str(document["request_schema_version"]),
        operation=document.get("operation"),
        route_id=document.get("route_id"),
        route_version=document.get("route_version"),
        model_id=document.get("model_id"),
        model_version=document.get("model_version"),
        panel_id=document.get("panel_id"),
        panel_version=document.get("panel_version"),
        panel_contract_sha256=document.get("panel_contract_sha256"),
        dataset_id=document.get("dataset_id"),
        records=parsed,
        model_source=model_source,
        exploratory_threshold=float(threshold),
        explainability=explainability,
    )


# --------------------------------------------------------------------------- #
# Refusal plumbing                                                             #
# --------------------------------------------------------------------------- #

#: Pipeline stages a refusal can be attributed to.
PIPELINE_STAGES: Final[tuple[str, ...]] = (
    "request",
    "registry",
    "route",
    "artifact",
    "record",
    "prediction",
)

#: Envelope/context keys the record grammar itself defines. A field name is
#: echoed in an error detail only when it is a registered panel field or one of
#: these, so a caller-injected feature key — which the panel validator reports
#: verbatim — can never smuggle a path or a value into a response.
_ENVELOPE_FIELD_NAMES: Final[frozenset[str]] = frozenset(
    {
        "record_ref",
        "features",
        "units",
        "missing_reasons",
        "context",
        "panel_id",
        "synthetic",
        "acquisition_stage",
        "input_source",
        "synthetic_provenance",
        "synthetic_provenance.declaration",
        "synthetic_provenance.fixture_ref",
        "synthetic_provenance.generator_id",
        "synthetic_provenance.seed",
        "declared_input_context",
        "records",
        "record",
        "request",
        "request_schema_version",
        "operation",
        "explainability",
        "explainability.lime_reference_scheme",
        "lime_reference_scheme",
        "exploratory_threshold",
        "model_source",
        "entry_state",
        "route_id",
        "route_version",
        "model_id",
        "model_version",
        "panel_version",
        "panel_contract_sha256",
        "dataset_id",
        "operation",
        "eligibility",
        "eligibility.synthetic_only",
        "eligibility.execution_mode",
        "bundle_schema_version",
        "local_producer_attestation",
        "model.explainability.capability",
        "model.explainability.method",
        "ordered_feature_names",
        "selected_model_family",
        "research_authorization",
        "pooled_cohorts",
        "development_dataset_id",
        "development_cohort_id",
        "target_id",
        "shap_background",
        "calibration.json",
        "shap_background.json",
        "preprocessing.json",
        "execution_profile",
        "panel_contract_sha256",
        "feature",
        "field",
        "shap_sum_check",
        "shap_scale",
        "shap_explained_quantity",
        "shap_additivity",
        "raw_model_score",
        "calibrated_log_odds",
        "calibrated_research_score",
        "artifact_kind",
        "request_not_a_dataclass",
        "bundle_dir_name",
    }
)

_FIELD_NAME_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,47}$")


def _sanitize_field(
    value: Any, panel: ResearchPanelContract | None = None
) -> str | None:
    """Echo a field name only when it is a registered identifier.

    Registered panel field names and registered envelope/context keys are
    structural metadata and are safe to report. Anything else is dropped, so an
    error detail can never carry submitted content, a filesystem path, or key
    material.
    """
    if not isinstance(value, str):
        return None
    if not _FIELD_NAME_RE.fullmatch(value):
        return None
    if value in _ENVELOPE_FIELD_NAMES:
        return value
    if panel is not None and value in panel.field_map:
        return value
    return None


# --------------------------------------------------------------------------- #
# Request-summary sanitization                                                 #
# --------------------------------------------------------------------------- #

#: Structural grammars a value must satisfy before it may be echoed into a
#: response. Identity fields additionally have to be *registered*: the
#: allowlists are the registry, route catalog, panel registry and operation
#: vocabulary, never the request. Everything else is reported as redacted by
#: field name only, so a refused request can never reflect a submitted path,
#: key, value, nested object or unregistered identifier.
_VERSION_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9]{1,4}(?:\.[0-9]{1,4}){1,3}$")

#: Upper bound on the record count reported for a request that was refused
#: before its own ceiling check could run.
_SUMMARY_RECORD_BOUND: Final[int] = MAX_RECORDS_CEILING + 1

_SUMMARY_IDENTITY_FIELDS: Final[tuple[str, ...]] = (
    "request_schema_version",
    "operation",
    "route_id",
    "route_version",
    "model_id",
    "model_version",
    "panel_id",
    "panel_version",
    "panel_contract_sha256",
    "dataset_id",
)


def _plain_mapping(value: Any) -> Mapping[str, Any] | None:
    """Return ``value`` only when it is a plain ``dict``.

    Reading a refused request must not execute caller code or walk a proxy, so
    only the concrete mapping type that JSON decoding produces is introspected.
    """
    return value if type(value) is dict else None


def _echoes_field(name: str, value: Any, fields: Mapping[str, Any]) -> bool:
    """True when a raw request value is safe to place in a response summary.

    Identity fields must resolve to a *registered* entry (registry, route
    catalog, panel registry, operation vocabulary); shape fields must match
    their grammar. Any other value is withheld and named in ``redacted_fields``,
    so a refused request can never reflect a path, secret, nested object or
    unregistered identifier.
    """
    if not isinstance(value, str):
        return False
    if name == "request_schema_version":
        return value == REQUEST_SCHEMA_VERSION
    if name == "operation":
        return value in KNOWN_OPERATIONS
    if name == "route_id":
        return value in RESEARCH_ROUTE_CATALOG
    if name == "panel_id":
        return value in REGISTERED_PANELS
    if name in ("model_id", "model_version"):
        # Both halves must agree with a registered model identity, so a guessed
        # or path-shaped id/version pair is never echoed.
        return (fields.get("model_id"), fields.get("model_version")) in _registered_model_keys()
    if name in ("route_version", "panel_version"):
        return bool(_VERSION_RE.fullmatch(value))
    if name == "panel_contract_sha256":
        return bool(SHA256_RE.fullmatch(value))
    if name == "dataset_id":
        return bool(SAFE_DATASET_ID_RE.fullmatch(value))
    return False


def _registered_model_keys() -> frozenset[tuple[str, str]]:
    """The (model_id, model_version) pairs this registry actually knows."""
    return frozenset(
        (entry.model_id, entry.model_version) for entry in RESEARCH_MODEL_REGISTRY.values()
    )


def _safe_threshold(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) and 0.0 < number < 1.0 else None


def _safe_bounded_count(value: Any) -> int:
    """A record count that is a bounded non-negative int, never a hostile call.

    ``len`` is only taken on the concrete ``tuple``/``list``/``dict`` types JSON
    decoding produces; anything else reports 0 rather than introspecting.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(0, min(int(value), _SUMMARY_RECORD_BOUND))


def _summary_records(raw: Any, *, echo_refs: bool) -> tuple[int, list[str], int]:
    """(count, echoed refs, redacted-ref count) from a raw records value.

    ``echo_refs`` is set only for a response that a *validated* request produced
    a result for. A reference is caller-chosen text: even inside the registered
    grammar it can carry sensitive content (a lowercase identifier of a real
    person or record in an upstream system), so a refused request reports the
    bounded count and the count of withheld references, never the strings.
    """
    if type(raw) not in (list, tuple):
        return 0, [], 0
    count = len(raw)
    refs: list[str] = []
    redacted = 0
    for item in raw[:_SUMMARY_RECORD_BOUND]:
        candidate: Any
        if type(item) is dict:
            candidate = item.get("record_ref")
        elif type(item) is ResearchFeatureRecord:
            candidate = item.record_ref
        else:
            candidate = None
        valid = isinstance(candidate, str) and bool(SAFE_RECORD_REF_RE.fullmatch(candidate))
        if valid and echo_refs:
            refs.append(candidate)
        else:
            redacted += 1
    return min(count, _SUMMARY_RECORD_BOUND), refs, redacted


def _summary_explainability(options: Any) -> dict[str, Any]:
    """Value-free explainability shape, safe for a refused request to echo."""
    if type(options) is not ExplainabilityOptions:
        return {
            "include_shap": False,
            "include_lime": False,
            "lime_reference_scheme": None,
            "lime_num_perturbations": None,
            "lime_seed": None,
            "lime_require_acceptable_quality": False,
            "options_type_accepted": False,
        }
    scheme = options.lime_reference_scheme
    count = options.lime_num_perturbations
    seed = options.lime_seed
    return {
        "include_shap": bool(options.include_shap),
        "include_lime": bool(options.include_lime),
        "lime_reference_scheme": (
            scheme
            if isinstance(scheme, str) and scheme in ALLOWED_LIME_REFERENCE_SCHEMES
            else None
        ),
        "lime_num_perturbations": (
            int(count)
            if isinstance(count, int)
            and not isinstance(count, bool)
            and 0 <= count <= MAX_LIME_PERTURBATIONS
            else None
        ),
        "lime_seed": (
            int(seed)
            if isinstance(seed, int)
            and not isinstance(seed, bool)
            and 0 <= seed <= 2**63 - 1
            else None
        ),
        "lime_require_acceptable_quality": bool(options.lime_require_acceptable_quality),
        "options_type_accepted": True,
    }


def _summary_model_source(source: Any, *, verified: bool) -> dict[str, Any]:
    """Path-free description of the artifact source.

    ``bundle_dir_name`` is a *caller-chosen* basename, not a registered identity:
    before the source has passed the bundle trust gates it is withheld, so a
    refusal cannot confirm that a directory name existed or echo one that embeds
    a secret. It is reported only on a response whose artifact was actually
    verified against the trusted local root and producer signature.
    """
    if type(source) is not LocalSyntheticBundleSource:
        return {
            "artifact_kind": ARTIFACT_KIND_LABEL,
            "bundle_dir_name": None,
            "signing_key_provided": False,
            "remote_or_url_source_supported": False,
            "source_type_accepted": False,
        }
    descriptor = {**source.safe_descriptor(), "source_type_accepted": True}
    if not verified:
        descriptor["bundle_dir_name"] = None
    return descriptor


def build_request_summary(
    request: Any,
    *,
    fields: Mapping[str, Any] | None = None,
    verified: bool = False,
) -> dict[str, Any]:
    """Build the request summary a response may carry, for any input shape.

    Used on every path — successful and refused — so an error response can never
    be more permissive than a success: only registered identities, grammar-valid
    versions and hashes, bounded counts, grammar-valid record references and
    primitive explainability/source flags are emitted, and only as
    JSON-serializable primitives. A request that is not the registered typed
    request object is never introspected, and raw document values are only ever
    read through the ``fields`` projection that :func:`safe_document_summary`
    builds from a plain ``dict``.

    ``verified`` marks the summary of a response that a fully validated request
    produced a result for; it is the only case in which caller-chosen text —
    record references and the bundle directory basename — is echoed, because on
    that path those values have been through the registered record grammar and
    the artifact trust gates. A refusal never echoes them.
    """
    accepted = type(request) is ResearchInferenceRequest
    resolved: dict[str, Any] = {}
    if fields is not None:
        resolved.update(fields)
    elif accepted:
        for name in _SUMMARY_IDENTITY_FIELDS:
            resolved[name] = getattr(request, name)
        resolved["records"] = request.records
        resolved["exploratory_threshold"] = request.exploratory_threshold
        resolved["explainability"] = request.explainability
        resolved["model_source"] = request.model_source
    summary: dict[str, Any] = {}
    redacted: list[str] = []
    for name in _SUMMARY_IDENTITY_FIELDS:
        value = resolved.get(name)
        if _echoes_field(name, value, resolved):
            summary[name] = str(value)
        else:
            summary[name] = None
            redacted.append(name)
    count, refs, redacted_refs = _summary_records(resolved.get("records"), echo_refs=verified)
    summary["record_count"] = count
    summary["record_refs"] = refs
    summary["exploratory_threshold"] = _safe_threshold(resolved.get("exploratory_threshold"))
    summary["explainability"] = _summary_explainability(resolved.get("explainability"))
    summary["model_source"] = _summary_model_source(resolved.get("model_source"), verified=verified)
    summary["request_type_accepted"] = accepted
    summary["record_refs_redacted"] = redacted_refs
    summary["redacted_fields"] = sorted(set(redacted))
    summary["unvalidated_values_redacted"] = bool(redacted or redacted_refs) or not accepted
    summary["summary_redaction_basis"] = (
        "validated_result_correlation" if verified else "refused_request_value_free"
    )
    return summary


def _universal_refusal_summary() -> dict[str, Any]:
    """The constant, value-free summary carried when nothing can be reported.

    It has exactly the shape of every other summary, with every identifier
    ``None``, so a refusal never carries a partial or unvalidated echo and never
    differs structurally from the success-path schema.
    """
    return {
        "request_schema_version": None,
        "operation": None,
        "route_id": None,
        "route_version": None,
        "model_id": None,
        "model_version": None,
        "panel_id": None,
        "panel_version": None,
        "panel_contract_sha256": None,
        "dataset_id": None,
        "record_count": 0,
        "record_refs": [],
        "exploratory_threshold": None,
        "explainability": _summary_explainability(None),
        "model_source": _summary_model_source(None, verified=False),
        "request_type_accepted": False,
        "record_refs_redacted": 0,
        "redacted_fields": sorted(_SUMMARY_IDENTITY_FIELDS),
        "unvalidated_values_redacted": True,
        "summary_redaction_basis": "refused_request_value_free",
    }


def safe_request_summary(request: Any, *, verified: bool = False) -> dict[str, Any]:
    """``build_request_summary`` with a total failure fallback.

    Summarizing a request must never be able to raise: if the sanitizer itself
    ever fails, the response carries the constant, value-free refusal summary
    instead of escaping the boundary.
    """
    try:
        summary = build_request_summary(request, verified=verified)
        json.dumps(summary, allow_nan=False, ensure_ascii=True)
    except Exception:  # noqa: BLE001 - the boundary never leaks or re-raises
        return _universal_refusal_summary()
    return summary


def safe_document_summary(document: Any) -> dict[str, Any]:
    """Refusal summary for a request *document* that failed its grammar.

    Only a plain ``dict`` is read, only allowlisted keys are considered, and a
    value is echoed only when it passes its own registered grammar — so a
    path-shaped ``record_ref`` or a nested object is never reflected.
    """
    mapping = _plain_mapping(document)
    if mapping is None:
        return _universal_refusal_summary()
    projected: dict[str, Any] = {name: mapping.get(name) for name in _SUMMARY_IDENTITY_FIELDS}
    projected["records"] = mapping.get("records")
    projected["exploratory_threshold"] = mapping.get("exploratory_threshold")
    projected["explainability"] = mapping.get("explainability")
    return build_request_summary(None, fields=projected, verified=False)

# --------------------------------------------------------------------------- #
# Internal refusal carrier                                                     #
# --------------------------------------------------------------------------- #


class _Refusal(Exception):
    """One internal fail-closed decision, converted into a typed result.

    The carrier holds a registered code, the pipeline stage that produced it,
    and an optionally echoed *registered* field name. Exception text is never
    carried forward: only these three structural values are.
    """

    __slots__ = ("binding", "code", "detail", "status")

    def __init__(
        self,
        code: str,
        *,
        stage: str,
        field_name: Any = None,
        status: ResearchFacadeStatus = ResearchFacadeStatus.ERROR,
        panel: ResearchPanelContract | None = None,
        binding: ResolvedRegistryBinding | None = None,
    ) -> None:
        self.code = code
        self.status = status
        self.binding = binding
        self.detail = FacadeErrorDetail(
            code=code,
            message=_ERROR_MESSAGES.get(
                code, "The request was refused by a registered fail-closed check."
            ),
            field_name=_sanitize_field(field_name, panel),
            stage=stage,
        )
        super().__init__(code)


# --------------------------------------------------------------------------- #
# Request-level validation                                                     #
# --------------------------------------------------------------------------- #


def _is_exact_type(value: Any, expected: type) -> bool:
    """True only for an instance of ``expected`` itself.

    Subclasses are refused: a subclass could carry behaviour or state the
    registered request grammar says nothing about.
    """
    return isinstance(value, expected) and type(value) is expected


def _validate_request_shape(request: Any) -> ResearchInferenceRequest:
    if not _is_exact_type(request, ResearchInferenceRequest):
        raise _Refusal("request_not_a_dataclass", stage="request")
    source = request.model_source
    if not _is_exact_type(source, LocalSyntheticBundleSource):
        raise _Refusal("model_source_not_allowed", stage="request", field_name="model_source")
    if request.request_schema_version != REQUEST_SCHEMA_VERSION:
        raise _Refusal("request_schema_version_unsupported", stage="request", field_name="request_schema_version")
    if request.operation != FACADE_OPERATION:
        raise _Refusal("facade_operation_not_supported", stage="request", field_name="operation")
    if not isinstance(request.records, tuple) or not request.records:
        raise _Refusal("empty_record_set", stage="request", field_name="records")
    for record in request.records:
        if not _is_exact_type(record, ResearchFeatureRecord):
            raise _Refusal("record_not_a_dataclass", stage="record", field_name="records")
    refs = [record.record_ref for record in request.records]
    if any(not isinstance(ref, str) or not SAFE_RECORD_REF_RE.fullmatch(ref) for ref in refs):
        raise _Refusal("invalid_record_ref", stage="record", field_name="record_ref")
    if len(set(refs)) != len(refs):
        raise _Refusal("duplicate_record_ref", stage="request", field_name="records")
    if len(refs) > MAX_RECORDS_CEILING:
        raise _Refusal("record_count_exceeds_ceiling", stage="request", field_name="records")
    threshold = request.exploratory_threshold
    if (
        isinstance(threshold, bool)
        or not isinstance(threshold, (int, float))
        or not (math.isfinite(float(threshold)) and 0.0 < float(threshold) < 1.0)
    ):
        raise _Refusal(
            "exploratory_threshold_invalid", stage="request", field_name="exploratory_threshold"
        )
    options = request.explainability
    if not isinstance(options, ExplainabilityOptions) or type(options) is not ExplainabilityOptions:
        raise _Refusal("explainability_options_invalid", stage="request", field_name="explainability")
    # Every explanation option is validated at the request stage, before any
    # artifact is opened: a malformed explanation request is a request error,
    # never a partial result with SHAP but no LIME.
    try:
        options.to_lime_config()
    except ResearchRegistryError as exc:
        raise _Refusal(
            exc.code, stage="request", field_name=exc.field or "explainability"
        ) from exc
    return request


def _resolve_binding(request: ResearchInferenceRequest) -> ResolvedRegistryBinding:
    """Resolve request identifiers through the registry, fail closed.

    A registered-but-blocked entry is an ``UNAVAILABLE`` answer that still
    reports the registered route/model/panel versions; every other registry
    refusal is an ``ERROR``.
    """
    try:
        return resolve_registered_model(
            route_id=request.route_id,
            route_version=request.route_version,
            model_id=request.model_id,
            model_version=request.model_version,
            panel_id=request.panel_id,
            panel_version=request.panel_version,
            panel_contract_sha256=request.panel_contract_sha256,
            dataset_id=request.dataset_id,
            operation=request.operation,
        )
    except ResearchRegistryError as exc:
        if exc.code in _UNAVAILABLE_REGISTRY_CODES and exc.entry is not None:
            raise _Refusal(
                exc.code,
                stage="registry",
                field_name=exc.field,
                status=ResearchFacadeStatus.UNAVAILABLE,
                binding=binding_for_entry(exc.entry),
            ) from exc
        raise _Refusal(exc.code, stage="registry", field_name=exc.field) from exc


# --------------------------------------------------------------------------- #
# Artifact resolution — every check here runs before any deserialization      #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class _LoadedArtifact:
    predictor: ResearchCadPredictor
    descriptor: VerifiedBundleDescriptor
    capabilities: ArtifactCapabilities
    model_family: str
    signing_key_provided: bool = False

    def safe_block(self) -> dict[str, Any]:
        """Path-free artifact identity for the response, built from the manifest."""
        manifest = self.descriptor.manifest
        files = manifest.get("files") if isinstance(manifest.get("files"), Mapping) else {}
        model_block = manifest.get("model") if isinstance(manifest.get("model"), Mapping) else {}
        panel_block = (
            manifest.get("panel_contract")
            if isinstance(manifest.get("panel_contract"), Mapping)
            else {}
        )
        target_block = manifest.get("target") if isinstance(manifest.get("target"), Mapping) else {}
        attestation = (
            manifest.get("local_producer_attestation")
            if isinstance(manifest.get("local_producer_attestation"), Mapping)
            else {}
        )
        eligibility = (
            manifest.get("eligibility") if isinstance(manifest.get("eligibility"), Mapping) else {}
        )
        return {
            "artifact_kind": ARTIFACT_KIND_LABEL,
            "bundle_dir_name": Path(self.descriptor.bundle_dir).name,
            "signing_key_provided": self.signing_key_provided,
            "remote_or_url_source_supported": False,
            "local_paths_disclosed": False,
            "bundle_schema_version": manifest.get("bundle_schema_version"),
            "model_id": model_block.get("model_id"),
            "model_version": model_block.get("model_version"),
            "protocol_id": model_block.get("protocol_id"),
            "selected_model_family": model_block.get("selected_model_family"),
            "execution_profile": model_block.get("execution_profile"),
            "panel_id": panel_block.get("panel_id"),
            "panel_version": panel_block.get("panel_version"),
            "panel_contract_sha256": panel_block.get("contract_sha256"),
            "ordered_feature_names": list(panel_block.get("ordered_feature_names") or ()),
            "target_id": target_block.get("target_id"),
            "development_dataset_id": target_block.get("development_dataset_id"),
            "development_cohort_id": target_block.get("development_cohort_id"),
            "pooled_cohorts": bool(target_block.get("pooled_cohorts")),
            "synthetic_only_provenance": bool(eligibility.get("synthetic_only")),
            "execution_mode": eligibility.get("execution_mode"),
            "verification": {
                "producer_authenticated": bool(self.descriptor.producer_authenticated),
                "safe_for_pickle_deserialization": bool(
                    self.descriptor.safe_for_pickle_deserialization
                ),
                "integrity_verified_only_not_authenticated": bool(
                    self.descriptor.integrity_verified_only_not_authenticated
                ),
                "attestation_scheme": attestation.get("scheme"),
                "trusted_local_root_containment_required": True,
                "sha256_alone_authenticates_producer": False,
            },
            "governance": {
                "serving_eligibility": self.descriptor.serving_eligibility,
                "approved_for_serving": bool(self.descriptor.approved_for_serving),
                "clinical_use_authorized": bool(self.descriptor.clinical_use_authorized),
                "real_data_execution_authorized": False,
            },
            "verified_artifact_hashes": {
                name: (
                    str(entry.get("sha256"))
                    if isinstance(entry, Mapping)
                    else str(entry)
                )
                for name, entry in sorted(files.items())
            },
        }

def _read_verified_json(descriptor: VerifiedBundleDescriptor, filename: str) -> dict[str, Any]:
    """Read one digest-checked JSON member after re-checking its SHA-256."""
    raw = (Path(descriptor.bundle_dir) / filename).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    files = descriptor.manifest.get("files")
    recorded = files.get(filename) if isinstance(files, Mapping) else None
    expected = recorded.get("sha256") if isinstance(recorded, Mapping) else recorded
    if not isinstance(expected, str) or not hmac.compare_digest(digest, expected):
        raise _Refusal("bundle_verification_failed", stage="artifact", field_name=filename)
    document = json.loads(raw.decode("utf-8"))
    if not isinstance(document, Mapping):
        raise _Refusal("bundle_verification_failed", stage="artifact", field_name=filename)
    return dict(document)


def _load_artifact(
    request: ResearchInferenceRequest,
    binding: ResolvedRegistryBinding,
    panel: ResearchPanelContract,
) -> _LoadedArtifact:
    source = request.model_source
    entry = binding.entry
    try:
        descriptor = verify_trusted_local_bundle(
            Path(source.bundle_dir),
            trusted_local_root=Path(source.trusted_local_root),
            signing_key=source.signing_key,
        )
    except AiPipelineError as exc:
        # The registered integrity code is reported; its message never is, and
        # nothing was deserialized because verification failed first.
        raise _Refusal(exc.code, stage="artifact", field_name=exc.field, panel=panel) from exc
    except Exception:  # noqa: BLE001 - never leak exception text
        raise _Refusal("bundle_verification_failed", stage="artifact") from exc

    try:
        # 1. Existing synthetic-provenance / execution-profile gate, reused
        #    verbatim from the reviewed CLI boundary (no artifact of real
        #    provenance reaches deserialization through this facade).
        assert_cli_predict_supported(descriptor.manifest)
        # 2. Registry identity cross-check against the verified manifest.
        model_family = assert_artifact_identity(descriptor.manifest, entry)
        # 3. The request itself must agree with the artifact, not only with the registry.
        _assert_request_matches_artifact(request, descriptor.manifest, entry)
        # 4. Capabilities are derived from the artifact, never from the request.
        calibrator = OofLogisticCalibrator.from_json_dict(
            _read_verified_json(descriptor, CALIBRATION_FILENAME)
        )
        capabilities = derive_artifact_capabilities(
            descriptor.manifest,
            entry=entry,
            calibrator=calibrator,
            background_document=_read_verified_json(descriptor, SHAP_BG_FILENAME),
            model_family=model_family,
        )
        # 5. Only now is the model deserialized, and only through the existing
        #    authenticated loader (which re-verifies before ``joblib.load``).
        predictor = ResearchCadPredictor.from_verified_bundle(
            Path(source.bundle_dir),
            trusted_local_root=Path(source.trusted_local_root),
            signing_key=source.signing_key,
        )
    except ResearchRegistryError as exc:
        raise _Refusal(exc.code, stage="artifact", field_name=exc.field, panel=panel) from exc
    except AiPipelineError as exc:
        raise _Refusal(exc.code, stage="artifact", field_name=exc.field, panel=panel) from exc
    except _Refusal:
        raise
    except Exception:  # noqa: BLE001
        raise _Refusal("bundle_verification_failed", stage="artifact") from exc
    if (
        predictor.model_id != entry.model_id
        or predictor.model_version != entry.model_version
        or predictor.panel.panel_id != entry.panel_id
        or predictor.execution_profile != entry.execution_profile
    ):
        raise _Refusal("artifact_identity_mismatch", stage="artifact", panel=panel)
    return _LoadedArtifact(
        predictor=predictor,
        descriptor=descriptor,
        capabilities=capabilities,
        model_family=model_family,
        signing_key_provided=source.signing_key is not None,
    )


def _assert_request_matches_artifact(
    request: ResearchInferenceRequest,
    manifest: Mapping[str, Any],
    entry: ResearchModelEntry,
) -> None:
    """The request, the registry entry and the verified artifact must agree."""
    panel_block = manifest.get("panel_contract") if isinstance(manifest.get("panel_contract"), Mapping) else {}
    model_block = manifest.get("model") if isinstance(manifest.get("model"), Mapping) else {}
    checks: tuple[tuple[str, Any, Any], ...] = (
        ("route_version", request.route_version, entry.route_version),
        ("panel_version", request.panel_version, panel_block.get("panel_version")),
        ("panel_contract_sha256", request.panel_contract_sha256, panel_block.get("contract_sha256")),
        ("model_id", request.model_id, model_block.get("model_id")),
        ("model_version", request.model_version, model_block.get("model_version")),
    )
    for name, requested, actual in checks:
        if requested != actual:
            raise _Refusal("artifact_identity_mismatch", stage="artifact", field_name=name)


# --------------------------------------------------------------------------- #
# Record-level pipeline                                                        #
# --------------------------------------------------------------------------- #


def _validate_synthetic_provenance(
    record: ResearchFeatureRecord, entry: ResearchModelEntry
) -> None:
    provenance = record.provenance
    if provenance is None:
        raise _Refusal(
            "synthetic_provenance_missing", stage="record", field_name="synthetic_provenance"
        )
    if provenance.declaration not in ADMISSIBLE_SYNTHETIC_PROVENANCE_DECLARATIONS:
        raise _Refusal(
            "synthetic_provenance_declaration_unknown",
            stage="record",
            field_name="synthetic_provenance.declaration",
        )
    if provenance.generator_id not in entry.admissible_synthetic_generators:
        raise _Refusal(
            "synthetic_provenance_generator_not_admissible",
            stage="record",
            field_name="synthetic_provenance.generator_id",
        )
    if not isinstance(record.input_source, str) or (
        record.input_source != SUPPORTED_SYNTHETIC_INPUT_SOURCE
    ):
        raise _Refusal("input_source_not_admissible", stage="record", field_name="input_source")


def _validate_acquisition_stage(
    record: ResearchFeatureRecord, panel: ResearchPanelContract
) -> None:
    """A record may not supply a field from a later stage than it declares.

    This encodes collection order only (history < resting < laboratory); it
    encodes no clinical rule, threshold, or medical semantics.
    """
    stage = record.acquisition_stage
    if stage is None:
        raise _Refusal(
            "acquisition_stage_missing", stage="record", field_name="acquisition_stage"
        )
    if not isinstance(stage, str) or not ACQUISITION_STAGE_RE.fullmatch(stage):
        raise _Refusal(
            "acquisition_stage_invalid", stage="record", field_name="acquisition_stage"
        )
    declared_rank = _STAGE_RANK.get(stage)
    if declared_rank is None:
        raise _Refusal(
            "acquisition_stage_invalid", stage="record", field_name="acquisition_stage"
        )
    for spec in panel.fields:
        value = record.features.get(spec.name)
        if value is None:
            continue
        field_rank = _STAGE_RANK.get(spec.stage)
        if field_rank is not None and field_rank > declared_rank:
            raise _Refusal(
                "acquisition_stage_precedence_violation", stage="record", field_name=spec.name
            )


#: Ordered acquisition-stage vocabulary shared by both registered source
#: families.
_STAGE_RANK: Final[Mapping[str, int]] = MappingProxyType(
    {
        "history_only": 0,
        "basic_clinical": 0,
        "resting_assessment": 1,
        "resting_plus_labs": 2,
        "laboratory_report": 2,
    }
)


def _record_eligibility(
    request: ResearchInferenceRequest,
    binding: ResolvedRegistryBinding,
    record: ResearchFeatureRecord,
    panel: ResearchPanelContract,
) -> None:
    """Re-run the frozen route resolver on this record's own declared context."""
    result = resolve_route(
        dataset_id=binding.route.dataset_id,
        panel_id=binding.route.panel_id,
        operation=request.operation,
        source_family=binding.route.source_family,
        declared_input_context=record.route_input_context(),
    )
    if result.eligible:
        return
    first = result.rejections[0] if result.rejections else "no_matching_route"
    status = (
        ResearchFacadeStatus.UNAVAILABLE
        if first in _UNAVAILABLE_ROUTE_REJECTIONS
        else ResearchFacadeStatus.ERROR
    )
    raise _Refusal(
        first, stage="route", field_name="declared_input_context", status=status, panel=panel
    )


def _validate_record(
    record: ResearchFeatureRecord,
    entry: ResearchModelEntry,
    panel: ResearchPanelContract,
    request: ResearchInferenceRequest,
) -> ValidatedClinicalRecord:
    _validate_synthetic_provenance(record, entry)
    if record.panel_id is not None and record.panel_id != request.panel_id:
        raise _Refusal("record_panel_id_mismatch", stage="record", field_name="panel_id")
    _validate_acquisition_stage(record, panel)
    try:
        validated = validate_clinical_record(
            record.to_panel_payload(request.panel_id), panel, require_synthetic=True
        )
    except ClinicalInputValidationError as exc:
        raise _Refusal(exc.code, stage="record", field_name=exc.field, panel=panel) from exc
    except (ValueError, TypeError) as exc:
        raise _Refusal("record_input_invalid", stage="record") from exc

    # This route admits one fabricated generator. Check the envelope of its
    # draws *after* panel validation, not the plausibility of a patient value.
    if entry.route_id == "da_a2_resting_v1":
        fields = panel.field_map
        for name, (low, high) in UCI45_RESTING_FIXTURE_BOUNDS.items():
            if name not in validated.present_fields:
                continue  # A legal missing optional measurement is handled by the abstention policy.
            if not low <= validated.values[fields[name].order] <= high:
                raise _Refusal(
                    "outside_synthetic_fixture_envelope", stage="record", field_name=name, panel=panel
                )
    return validated


def _score_record(
    request: ResearchInferenceRequest,
    binding: ResolvedRegistryBinding,
    panel: ResearchPanelContract,
    artifact: _LoadedArtifact,
    record: ResearchFeatureRecord,
) -> RecordOutcome:
    entry = binding.entry
    # Defense in depth: the request-level check already enforced the global
    # ceiling, and import-time registry validation guarantees every entry's
    # own ceiling is <= that ceiling. This is the per-entry policy hook, so a
    # future entry may register a stricter limit than the facade-wide one.
    if len(request.records) > entry.max_records_per_invocation:
        raise _Refusal("record_count_exceeds_ceiling", stage="record", field_name="records")
    _record_eligibility(request, binding, record, panel)
    validated = _validate_record(record, entry, panel, request)

    if entry.abstain_on_missing_optional and not validated.stage_complete:
        # A registered inference policy, not a data error: the underlying
        # fold-safe preprocessor *could* impute a training median, and this
        # entry deliberately refuses to score on an imputed optional field at
        # inference time. No score is produced and none is estimated.
        return RecordOutcome(
            record_ref=record.record_ref,
            status=ResearchFacadeStatus.ABSTAIN,
            abstention_reason="registry_abstain_policy_optional_field_missing",
            present_fields=validated.present_fields,
            missing_fields_with_reason=validated.missing_fields_with_reason,
            evidence_level=entry.evidence_level,
        )

    try:
        prediction = artifact.predictor.predict_research_only(
            record.to_panel_payload(request.panel_id),
            exploratory_threshold=request.exploratory_threshold,
            lime_config=_lime_config_for(request, artifact, panel),
            lime_require_acceptable_quality=(
                request.explainability.lime_require_acceptable_quality
            ),
        )
    except _Refusal:
        raise
    except AiPipelineError as exc:
        raise _Refusal(exc.code, stage="prediction", field_name=exc.field, panel=panel) from exc
    except (ValueError, TypeError) as exc:
        raise _Refusal("record_unexpected_error", stage="prediction") from exc

    capabilities = artifact.capabilities
    _assert_prediction_consistency(prediction, capabilities)

    return RecordOutcome(
        record_ref=record.record_ref,
        status=ResearchFacadeStatus.SYNTHETIC_RESULT,
        score=ResearchScoreBlock(
            kind=(
                SCORE_KIND_CALIBRATED
                if capabilities.calibration_supported
                else SCORE_KIND_RAW
            ),
            raw_model_score=float(prediction.raw_model_score),
            raw_model_log_odds=float(prediction.raw_model_log_odds),
            calibrated_research_score=(
                float(prediction.calibrated_research_score)
                if capabilities.calibration_supported
                else None
            ),
            calibrated_log_odds=(
                float(prediction.calibrated_log_odds)
                if capabilities.calibration_supported
                else None
            ),
            calibration_reason=capabilities.unsupported_calibration_reason,
            exploratory_threshold=float(prediction.exploratory_threshold),
            exploratory_above_threshold=bool(prediction.exploratory_above_threshold_flag),
            threshold_clinically_validated=False,
            interpretation=SCORE_INTERPRETATION,
            clinical_probability_claim=False,
        ),
        shap=_shap_block(request, capabilities, prediction),
        lime=_lime_block(request, capabilities, prediction),
        uncertainty=dict(prediction.uncertainty),
        present_fields=validated.present_fields,
        missing_fields_with_reason=validated.missing_fields_with_reason,
        evidence_level=entry.evidence_level,
    )


def _lime_config_for(
    request: ResearchInferenceRequest, artifact: _LoadedArtifact, panel: ResearchPanelContract
) -> LimeConfig | None:
    """Build the LIME generation config only when the artifact can support it."""
    if not request.explainability.include_lime:
        return None
    if not artifact.capabilities.lime_supported:
        return None
    try:
        return request.explainability.to_lime_config()
    except AiPipelineError as exc:
        raise _Refusal(exc.code, stage="prediction", panel=panel) from exc


def _assert_prediction_consistency(
    prediction: Any, capabilities: ArtifactCapabilities
) -> None:
    """Withhold any numeric output that fails a fail-closed consistency check."""
    explanation = prediction.explanation
    if (
        explanation.sum_check_passed is not True
        or float(explanation.max_abs_discrepancy) > ADDITIVITY_TOLERANCE
    ):
        raise _Refusal(
            "prediction_integrity_check_failed", stage="prediction", field_name="shap_sum_check"
        )
    if (
        explanation.explained_quantity != capabilities.shap_explained_quantity
        or explanation.scale != capabilities.shap_scale
    ):
        raise _Refusal(
            "prediction_integrity_check_failed", stage="prediction", field_name="shap_scale"
        )
    if explanation.additive_on_calibrated_probability is not False:
        # SHAP is additive on the declared scale (calibrated log-odds for the
        # logistic family, raw model probability for tree families) and never
        # on calibrated probability. A change here is an integrity failure.
        raise _Refusal(
            "prediction_integrity_check_failed", stage="prediction", field_name="shap_additivity"
        )
    raw = float(prediction.raw_model_score)
    if not (0.0 <= raw <= 1.0) or not math.isfinite(raw):
        raise _Refusal(
            "prediction_integrity_check_failed", stage="prediction", field_name="raw_model_score"
        )
    if capabilities.calibration_supported:
        calibrated = float(prediction.calibrated_research_score)
        log_odds = float(prediction.calibrated_log_odds)
        if (
            not (0.0 <= calibrated <= 1.0)
            or not math.isfinite(log_odds)
            or abs(float(expit(log_odds)) - calibrated) > 1e-12
        ):
            raise _Refusal(
                "prediction_integrity_check_failed",
                stage="prediction",
                field_name="calibrated_log_odds",
            )


def _shap_block(
    request: ResearchInferenceRequest, capabilities: ArtifactCapabilities, prediction: Any
) -> ShapExplanationBlock:
    explanation = prediction.explanation
    common: dict[str, Any] = {
        "explained_quantity": capabilities.shap_explained_quantity,
        "scale": capabilities.shap_scale,
        "method": capabilities.shap_method,
        "background_sample_count": capabilities.shap_background_sample_count,
        "background_synthetic_only": capabilities.shap_background_synthetic_only,
        "additive_on_calibrated_probability": capabilities.shap_additive_on_calibrated_probability,
    }
    if not request.explainability.include_shap:
        return ShapExplanationBlock(
            provided=False, reason="not_requested_by_caller", sum_check_passed=None,
            max_abs_discrepancy=None, **common,
        )
    return ShapExplanationBlock(
        provided=True,
        reason=None,
        sum_check_passed=bool(explanation.sum_check_passed),
        max_abs_discrepancy=float(explanation.max_abs_discrepancy),
        explained_quantity=explanation.explained_quantity,
        scale=explanation.scale,
        method=explanation.method,
        background_sample_count=int(explanation.background_sample_count),
        background_synthetic_only=capabilities.shap_background_synthetic_only,
        additive_on_calibrated_probability=bool(explanation.additive_on_calibrated_probability),
        attribution_feature_names=tuple(item.feature_name for item in explanation.attributions),
    )


#: Keys that record wall-clock timing; stripped so a response digest is
#: reproducible for a fixed input (the payload is a research record, not a
#: performance trace).
_TIMING_KEYS: Final[frozenset[str]] = frozenset(
    {
        "runtime",
        "runtime_seconds",
        "wall_clock_seconds",
        "elapsed_seconds",
        "duration_seconds",
    }
)


def _strip_timing(value: Any) -> Any:
    """Return ``value`` with every nested timing entry removed."""
    if isinstance(value, Mapping):
        return {
            key: _strip_timing(item)
            for key, item in value.items()
            if key not in _TIMING_KEYS
        }
    if isinstance(value, tuple):
        return tuple(_strip_timing(item) for item in value)
    if isinstance(value, list):
        return [_strip_timing(item) for item in value]
    return value


def _lime_block(
    request: ResearchInferenceRequest, capabilities: ArtifactCapabilities, prediction: Any
) -> LimeExplanationBlock:
    if not request.explainability.include_lime:
        return LimeExplanationBlock(
            provided=False,
            reason=(
                "not_requested_by_caller"
                if capabilities.lime_supported
                else (capabilities.lime_unsupported_reason or "lime_not_supported_by_artifact")
            ),
            payload=None,
            quality_status=None,
            is_reliable_for_interpretation=None,
            comparable_with_shap=None,
            explained_quantity=None,
            scale=None,
        )
    explanation = prediction.lime_explanation
    if explanation is None:
        return LimeExplanationBlock(
            provided=False,
            reason=capabilities.lime_unsupported_reason or "explainer_unavailable",
            payload=None,
            quality_status=None,
            is_reliable_for_interpretation=None,
            comparable_with_shap=None,
            explained_quantity=None,
            scale=None,
        )
    payload = _strip_timing(explanation.to_dict())
    comparability = prediction.lime_comparability
    return LimeExplanationBlock(
        provided=True,
        reason=None,
        payload=payload,
        quality_status=explanation.quality_status,
        is_reliable_for_interpretation=bool(explanation.is_reliable_for_interpretation),
        comparable_with_shap=(
            bool(comparability.get("comparable"))
            if isinstance(comparability, Mapping)
            else None
        ),
        explained_quantity=explanation.explained_quantity,
        scale=explanation.scale,
    )


# --------------------------------------------------------------------------- #
# Public entry point                                                           #
# --------------------------------------------------------------------------- #


def run_offline_research_inference(
    request: ResearchInferenceRequest,
) -> ResearchInferenceResponse:
    """Execute one offline synthetic research inference call, fail closed.

    Validation, provenance and security failures never raise: each becomes an
    explicit typed :class:`ResearchInferenceResponse` whose status is one of
    ``SYNTHETIC_RESULT``, ``ABSTAIN``, ``UNAVAILABLE`` or ``ERROR``.
    """
    binding: ResolvedRegistryBinding | None = None
    capabilities: ArtifactCapabilities | None = None
    artifact_block: Mapping[str, Any] | None = None
    outcomes: tuple[RecordOutcome, ...] = ()
    refusal: FacadeErrorDetail | None = None
    forced: ResearchFacadeStatus | None = None
    summary_source: Any = request
    try:
        validated_request = _validate_request_shape(request)
        # From here the summary describes a request that satisfied the registered
        # grammar; before it, the raw (untrusted) object is what is summarized.
        summary_source = validated_request
        binding = _resolve_binding(validated_request)
        panel = binding.panel
        artifact = _load_artifact(validated_request, binding, panel)
        capabilities = artifact.capabilities
        artifact_block = artifact.safe_block()
        outcomes = tuple(
            _run_with_record_refusal(validated_request, binding, panel, artifact, record)
            for record in validated_request.records
        )
    except _Refusal as exc:
        refusal = exc.detail
        if exc.binding is not None:
            binding = exc.binding
        forced = exc.status
    except Exception:  # noqa: BLE001 - the boundary never leaks internals
        refusal = _Refusal("request_unexpected_error", stage="request").detail
        forced = ResearchFacadeStatus.ERROR

    status = forced if forced is not None else _roll_up(outcomes)
    # The summary is built once the status is known, because what a response may
    # disclose depends on it: caller-chosen text (record references, the bundle
    # directory basename) is reported only on the response a fully validated and
    # verified request produced a result for. Every refusal is value-free.
    safe_summary: Mapping[str, Any] = safe_request_summary(
        summary_source, verified=status.produced_a_score
    )
    provenance = {
        "input_provenance": SYNTHETIC_PROVENANCE_DECLARATION,
        "input_provenance_basis": (
            "caller declaration, checked against the entry's pinned synthetic "
            "fixture generator allowlist"
        ),
        "artifact_provenance": (
            "verified synthetic research bundle"
            if artifact_block is not None
            else "not established"
        ),
        "artifact_provenance_established_before_deserialization": artifact_block is not None,
        "synthetic_flag_alone_accepted_as_evidence": False,
        "registry_digest_sha256": registry_digest_sha256(),
    }
    governance = {
        "serving_eligibility": "RESEARCH_ONLY",
        "approved_for_serving": False,
        "clinical_use_authorized": False,
        "real_data_execution_authorized": False,
        "http_surface_added": False,
        "provider_selection_changed": False,
        "requires_clinician_and_gate_pt_validation": True,
        "gate_pt_p3": "CLOSED",
    }
    limitations = list(FACADE_LIMITATIONS)
    if artifact_block is not None:
        limitations = [*limitations, *MANDATORY_LIMITATIONS]
    if capabilities is not None and not capabilities.calibration_supported:
        limitations = [
            *limitations,
            "No calibrated probability is reported for this call: the verified "
            "artifact provides no fitted out-of-fold calibrator, and a raw model "
            "probability is never relabelled as calibrated.",
        ]
    return ResearchInferenceResponse(
        status=status,
        binding=binding,
        capabilities=capabilities,
        outcomes=outcomes,
        artifact=artifact_block,
        error=refusal,
        request_summary=safe_summary,
        provenance=provenance,
        governance=governance,
        limitations=tuple(limitations),
    )


def _document_refusal_response(
    exc: ResearchRegistryError, *, document: Any
) -> ResearchInferenceResponse:
    """Convert a request-document parse refusal into a typed response."""
    binding: ResolvedRegistryBinding | None = None
    status = ResearchFacadeStatus.ERROR
    if exc.code in _UNAVAILABLE_REGISTRY_CODES and exc.entry is not None:
        status = ResearchFacadeStatus.UNAVAILABLE
        binding = binding_for_entry(exc.entry)
    return ResearchInferenceResponse(
        status=status,
        binding=binding,
        capabilities=None,
        outcomes=(),
        artifact=None,
        error=FacadeErrorDetail(
            code=exc.code,
            message=_ERROR_MESSAGES.get(exc.code, GENERIC_ERROR_MESSAGE),
            field_name=_sanitize_field(exc.field),
            stage="request",
        ),
        request_summary=safe_document_summary(document),
        provenance={
            "input_provenance": SYNTHETIC_PROVENANCE_DECLARATION,
            "input_provenance_basis": "not established: the request document was refused",
            "artifact_provenance": "not established",
            "artifact_provenance_established_before_deserialization": False,
            "synthetic_flag_alone_accepted_as_evidence": False,
            "registry_digest_sha256": registry_digest_sha256(),
        },
        governance={
            "serving_eligibility": "RESEARCH_ONLY",
            "approved_for_serving": False,
            "clinical_use_authorized": False,
            "real_data_execution_authorized": False,
            "http_surface_added": False,
            "provider_selection_changed": False,
            "requires_clinician_and_gate_pt_validation": True,
            "gate_pt_p3": "CLOSED",
        },
        limitations=FACADE_LIMITATIONS,
    )


def run_offline_research_inference_from_document(
    payload: Mapping[str, Any],
    *,
    model_source: LocalSyntheticBundleSource,
) -> ResearchInferenceResponse:
    """Parse-and-run entry point for document-shaped (e.g. JSON) callers.

    The registered request grammar is validated first, and a malformed document
    becomes an explicit typed ``ERROR`` response rather than an exception, so a
    document-facing caller sees the same four statuses everywhere. No artifact
    is touched for a document that fails to parse.
    """
    try:
        request = parse_inference_request(payload, model_source=model_source)
    except ResearchRegistryError as exc:
        return _document_refusal_response(exc, document=payload)
    return run_offline_research_inference(request)


def _run_with_record_refusal(
    request: ResearchInferenceRequest,
    binding: ResolvedRegistryBinding,
    panel: ResearchPanelContract,
    artifact: _LoadedArtifact,
    record: ResearchFeatureRecord,
) -> RecordOutcome:
    """Isolate one record's refusal so a bad record cannot void the others."""
    try:
        return _score_record(request, binding, panel, artifact, record)
    except _Refusal as exc:
        return RecordOutcome(
            record_ref=record.record_ref,
            status=exc.status,
            error=exc.detail,
            unavailable_reason=(
                exc.detail.code if exc.status is ResearchFacadeStatus.UNAVAILABLE else None
            ),
            evidence_level=binding.entry.evidence_level,
        )
    except Exception:  # noqa: BLE001
        return RecordOutcome(
            record_ref=record.record_ref,
            status=ResearchFacadeStatus.ERROR,
            error=_Refusal("record_unexpected_error", stage="record").detail,
            evidence_level=binding.entry.evidence_level,
        )


def _roll_up(outcomes: Sequence[RecordOutcome]) -> ResearchFacadeStatus:
    """Deterministic response status: the highest-precedence record status.

    ``ERROR`` dominates ``UNAVAILABLE``, which dominates ``ABSTAIN``, which
    dominates ``SYNTHETIC_RESULT``: a request is never reported as more
    successful than its least successful record.
    """
    if not outcomes:
        return ResearchFacadeStatus.ERROR
    present = {outcome.status for outcome in outcomes}
    for candidate in STATUS_PRECEDENCE:
        if candidate in present:
            return candidate
    return ResearchFacadeStatus.ERROR  # pragma: no cover - every status is listed


def is_registered_static_error_message(message: str) -> bool:
    """True when ``message`` is one of the facade's static refusal reasons.

    Refusal text is always selected from this closed catalogue, never built from
    request content, so a caller can verify programmatically that no submitted
    value or local path was echoed back.
    """
    return isinstance(message, str) and message in _STATIC_ERROR_MESSAGE_SET


_STATIC_ERROR_MESSAGE_SET: Final[frozenset[str]] = frozenset(_ERROR_MESSAGES.values())


__all__ = [
    "FACADE_ID",
    "FACADE_LIMITATIONS",
    "FACADE_OPERATION",
    "GENERIC_ERROR_CODE",
    "GENERIC_ERROR_MESSAGE",
    "PIPELINE_STAGES",
    "REQUEST_SCHEMA_VERSION",
    "RESPONSE_SCHEMA_VERSION",
    "STATUS_PRECEDENCE",
    "SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE",
    "ExplainabilityOptions",
    "FacadeErrorDetail",
    "LimeExplanationBlock",
    "LocalSyntheticBundleSource",
    "RecordOutcome",
    "ResearchFacadeStatus",
    "ResearchFeatureRecord",
    "ResearchInferenceRequest",
    "ResearchInferenceResponse",
    "ResearchScoreBlock",
    "ShapExplanationBlock",
    "SyntheticFixtureProvenance",
    "canonical_response_digest",
    "is_registered_static_error_message",
    "parse_feature_record",
    "parse_inference_request",
    "parse_synthetic_provenance",
    "run_offline_research_inference",
    "run_offline_research_inference_from_document",
    "build_request_summary",
    "safe_document_summary",
    "safe_request_summary",
]
