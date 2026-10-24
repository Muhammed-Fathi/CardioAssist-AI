"""Offline, fail-closed admission checks for research model descriptors.

Scope of this module:

* structural validation of a versioned descriptor against
  ``artifact_descriptor.v1.schema.json``;
* semantic cross-checks against the approved shared feature schemas, the
  registered research model families, an externally supplied target registry,
  a reviewed **ordered feature binding** (:mod:`feature_order`), calibration
  integrity and the declared explainability capability;
* byte-level SHA-256 and size verification -- artifact, preprocessing,
  calibration (when separate) and protocol -- through a byte-only
  :class:`~backend.app.artifact_admission.sources.ArtifactSource`.

Hard limits:

* nothing is deserialized, executed or imported from an artifact;
* a passing checksum is treated as *integrity only* and never as scientific,
  clinical or serving approval;
* a declared calibration hash is only accepted when the corresponding bytes
  were actually read and hashed; an embedded calibration may not claim an
  independently verified artifact;
* the returned :class:`AdmissionDecision` can only express
  ``serving_eligibility == "RESEARCH_ONLY"`` and ``approved_for_serving is
  False`` (both are properties, not caller-settable fields);
* the D-047 internal exploratory run is never treated as a deployable model;
* genuine TreeSHAP/LIME is not implemented in this repository, so no
  descriptor may claim verified research explainability.

This module is not imported by the FastAPI application, exposes no endpoint and
reads no request, database row or dataset.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, NoReturn

from jsonschema import Draft202012Validator

from ..canonical import canonical_json
from ..validation import feature_rules
from .catalog import FeatureSchemaCatalog
from .errors import ArtifactAdmissionError
from .feature_order import (
    CLINICAL_APPROVED_ORDER_STATUS,
    FeatureOrderPolicy,
    is_registered_definition,
    registered_feature_order_policy,
)
from .sources import ArtifactReferenceError, ArtifactSource

DESCRIPTOR_SCHEMA_PATH = Path(__file__).with_name("artifact_descriptor.v1.schema.json")
DESCRIPTOR_SCHEMA_VERSION = "artifact_descriptor/v1"
_DESCRIPTOR_VALIDATOR = Draft202012Validator(
    json.loads(DESCRIPTOR_SCHEMA_PATH.read_text(encoding="utf-8"))
)

#: Research model families registered by the committed D-047 exploratory plan.
#: Registration is not an endorsement, not a serving commitment and not a
#: statement that any of these families is scientifically preferred.
SUPPORTED_MODEL_FAMILIES: tuple[str, ...] = (
    "prevalence_dummy",
    "l2_logistic_regression",
    "constrained_random_forest",
)

#: Descriptor-declared container suffix per artifact type. The extension is a
#: consistency check only; the validator never opens the container.
ARTIFACT_TYPE_SUFFIXES: Mapping[str, tuple[str, ...]] = {
    "joblib": (".joblib",),
    "pickle": (".pkl",),
    "onnx": (".onnx",),
    "json_trees": (".json",),
    "safetensors": (".safetensors",),
}

#: A score type must be derivable from the calibration status. It can never be
#: promoted from a margin to a probability by editing the descriptor.
SCORE_TYPE_BY_CALIBRATION: Mapping[str, str] = {
    "uncalibrated": "uncalibrated_margin",
    "calibrated": "calibrated_probability",
    "not_assessed": "non_interpretable",
}

#: How calibration evidence is represented. ``separate_artifact`` bytes are
#: read and hashed here. ``embedded_in_verified_artifact`` is admitted only as
#: a non-independent claim: nothing inside the model container is opened.
CALIBRATION_REPRESENTATIONS: tuple[str, ...] = (
    "none",
    "separate_artifact",
    "embedded_in_verified_artifact",
)
CALIBRATION_INTEGRITY_VERIFIED = "VERIFIED_SEPARATE_ARTIFACT"
CALIBRATION_INTEGRITY_EMBEDDED = "EMBEDDED_NOT_INDEPENDENTLY_VERIFIED"
CALIBRATION_INTEGRITY_NONE = "NOT_APPLICABLE"

#: Truthful explanation capability per method.
#:
#: Genuine TreeSHAP/LIME is **not** implemented or verified anywhere in this
#: repository: the API returns deterministic, SHAP-*shaped* synthetic offsets
#: from ``backend/app/mock_prediction.py`` (a hash of the feature value), and
#: ``research/`` contains no ``shap``/``lime`` dependency or computation. The
#: capability vocabulary therefore distinguishes "mock fixture shape only"
#: from a future "implemented and verified" claim -- and that future claim is
#: rejected today because it would be untrue.
EXPLAINABILITY_CAPABILITIES: tuple[str, ...] = (
    "not_implemented",
    "mock_shap_shaped_fixture_only",
    "implemented_and_verified_in_research_harness",
)
EXPLAINABILITY_VERIFIED_CLAIM = "implemented_and_verified_in_research_harness"
EXPLAINABILITY_CAPABILITY: Mapping[str, str] = {
    "tree_shap": "mock_shap_shaped_fixture_only",
    "lime": "not_implemented",
    "none": "not_implemented",
}

RESEARCH_ONLY = "RESEARCH_ONLY"
SELF_DECLARED_SERVING = "APPROVED_FOR_SERVING"
INTERNAL_EXPLORATORY_LABEL = "INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED"
SYNTHETIC_LABEL = "SYNTHETIC_NON_CLINICAL"

#: Recorded on every decision so that a reviewer never has to infer intent.
NON_APPROVAL_REASONS: tuple[str, ...] = (
    "artifact_admission_is_integrity_and_scope_checking_only",
    "checksum_integrity_is_not_clinical_or_scientific_approval",
    "serving_requires_separate_independent_review_and_authorization",
    "gate_pt_p3_remains_closed_and_p1_remains_pending",
)

D047_NON_APPROVAL_REASON = "d047_internal_exploratory_run_is_not_a_deployable_model"
EMBEDDED_CALIBRATION_REASON = "calibration_embedded_in_model_not_independently_verified"
UNVERIFIED_EXPLAINABILITY_REASON = "genuine_treeshap_or_lime_not_implemented_in_repository"
SYNTHETIC_ONLY_ORDER_REASON = (
    "feature_order_policy_is_synthetic_mock_fixture_scope_only"
)


def _fail(code: str, field: str) -> NoReturn:
    raise ArtifactAdmissionError(code, field)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _target_digest(definition: str) -> str:
    return _sha256(definition.strip().encode("utf-8"))


@dataclass(frozen=True)
class AdmissionPolicy:
    """Human-supplied admission inputs.

    ``registered_targets`` maps a target id to the exact registered definition
    text, so changing target semantics without registering a new id fails
    closed. ``catalog`` pins the approved shared feature schemas.
    ``input_order_policy`` supplies the reviewed ordered feature binding; when
    it is ``None`` (the default) admission fails closed rather than inferring
    an order from schema serialization.
    """

    registered_targets: Mapping[str, str]
    catalog: FeatureSchemaCatalog
    input_order_policy: FeatureOrderPolicy | None = None

    def __post_init__(self) -> None:
        if not self.registered_targets:
            raise ValueError("AdmissionPolicy requires at least one registered target.")
        targets: dict[str, str] = {}
        for target_id, definition in self.registered_targets.items():
            if not isinstance(target_id, str) or not isinstance(definition, str):
                raise ValueError("Registered target ids and definitions must be strings.")
            if not definition.strip():
                raise ValueError("A registered target definition must not be blank.")
            targets[target_id] = definition
        # Detach from the caller's dict and make the registry read-only.
        object.__setattr__(self, "registered_targets", MappingProxyType(targets))

    @classmethod
    def from_shared_contracts(
        cls,
        *,
        registered_targets: Mapping[str, str],
        input_order_policy: FeatureOrderPolicy | None = None,
    ) -> "AdmissionPolicy":
        return cls(
            registered_targets=dict(registered_targets),
            catalog=FeatureSchemaCatalog.from_shared_contracts(),
            input_order_policy=input_order_policy,
        )


@dataclass(frozen=True)
class AdmissionDecision:
    """Research-only outcome of a successful admission check.

    ``serving_eligibility`` and ``approved_for_serving`` are read-only
    properties: no instance of this class can represent an approved deployable
    model, even if a caller constructs it directly.
    """

    descriptor_schema_version: str
    descriptor_sha256: str
    artifact_id: str
    artifact_version: str
    model_family: str
    preprocessing_version: str
    feature_schema_id: str
    feature_order_policy_id: str
    feature_order_policy_status: str
    feature_names: tuple[str, ...]
    target_id: str
    source_cohort_id: str
    dataset_id: str
    prediction_timepoint: str
    calibration_status: str
    calibration_integrity: str
    explainability_method: str
    explainability_capability: str
    research_label: str
    verified_refs: tuple[str, ...]
    non_approval_reasons: tuple[str, ...]

    @property
    def serving_eligibility(self) -> str:
        return RESEARCH_ONLY

    @property
    def approved_for_serving(self) -> bool:
        return False


def admit_research_artifact(
    descriptor: Any,
    *,
    source: ArtifactSource,
    policy: AdmissionPolicy,
) -> AdmissionDecision:
    """Validate a research artifact descriptor or raise ArtifactAdmissionError."""
    document = _validate_structure(descriptor)
    _check_eligibility(document)
    calibration_integrity = _check_model(document)
    _check_feature_contract(document, policy)
    _check_target(document, policy)
    verified_refs = _verify_bytes(document, source)

    target = document["target"]
    cohort = target["source_cohort"]
    eligibility = document["eligibility"]
    model = document["model"]
    calibration_block = model["calibration"]

    reasons = list(NON_APPROVAL_REASONS)
    if eligibility["research_label"] == INTERNAL_EXPLORATORY_LABEL:
        reasons.append(D047_NON_APPROVAL_REASON)
    # A verified-capability claim is rejected above, so every admitted decision
    # records that no genuine TreeSHAP/LIME implementation backs it.
    reasons.append(UNVERIFIED_EXPLAINABILITY_REASON)
    if calibration_integrity == CALIBRATION_INTEGRITY_EMBEDDED:
        reasons.append(EMBEDDED_CALIBRATION_REASON)
    active_order = policy.input_order_policy
    if active_order is not None and active_order.status != CLINICAL_APPROVED_ORDER_STATUS:
        reasons.append(SYNTHETIC_ONLY_ORDER_REASON)

    return AdmissionDecision(
        descriptor_schema_version=document["descriptor_schema_version"],
        descriptor_sha256=_sha256(canonical_json(document).encode("utf-8")),
        artifact_id=document["artifact"]["artifact_id"],
        artifact_version=document["artifact"]["artifact_version"],
        model_family=model["model_family"],
        preprocessing_version=model["preprocessing_version"],
        feature_schema_id=document["feature_contract"]["feature_schema_id"],
        feature_order_policy_id=active_order.policy_id if active_order else "NONE",
        feature_order_policy_status=active_order.status if active_order else "NONE",
        feature_names=_declared_order(document),
        target_id=target["target_id"],
        source_cohort_id=cohort["cohort_id"],
        dataset_id=cohort["dataset_id"],
        prediction_timepoint=target["prediction_timepoint"],
        calibration_status=calibration_block["status"],
        calibration_integrity=calibration_integrity,
        explainability_method=model["explainability"]["method"],
        explainability_capability=model["explainability"]["capability"],
        research_label=eligibility["research_label"],
        verified_refs=tuple(verified_refs),
        non_approval_reasons=tuple(reasons),
    )


def _declared_order(document: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(
        feature["name"]
        for feature in sorted(
            document["feature_contract"]["features"], key=lambda item: item["order"]
        )
    )


def _validate_structure(descriptor: Any) -> Mapping[str, Any]:
    if not isinstance(descriptor, Mapping):
        _fail("malformed_descriptor", "descriptor")
    error = next(_DESCRIPTOR_VALIDATOR.iter_errors(dict(descriptor)), None)
    if error is not None:
        # Only the path is reported: jsonschema messages can echo values.
        # For a missing member the path is completed with the schema-declared
        # property name, which is contract metadata, never descriptor content.
        parts = [str(part) for part in error.absolute_path]
        if error.validator == "required":
            instance = error.instance if isinstance(error.instance, Mapping) else {}
            absent = [name for name in error.validator_value if name not in instance]
            if absent:
                parts.append(str(absent[0]))
        _fail("descriptor_schema_invalid", ".".join(parts) or "descriptor")
    return descriptor


def _check_eligibility(document: Mapping[str, Any]) -> None:
    eligibility = document["eligibility"]
    if eligibility["serving_status"] != RESEARCH_ONLY:
        # A descriptor may never award itself a serving status; approval can
        # only come from a separate, independently reviewed authorization.
        _fail("self_declared_serving_status_not_permitted", "eligibility.serving_status")
    if eligibility["research_label"] not in {SYNTHETIC_LABEL, INTERNAL_EXPLORATORY_LABEL}:
        _fail("unsupported_research_label", "eligibility.research_label")


def _check_model(document: Mapping[str, Any]) -> str:
    """Validate model/calibration/explainability semantics.

    Returns the calibration-integrity classification for the decision record.
    """
    model = document["model"]
    if model["model_family"] not in SUPPORTED_MODEL_FAMILIES:
        _fail("unexpected_model_family", "model.model_family")

    calibration = model["calibration"]
    status = calibration["status"]
    expected_score_type = SCORE_TYPE_BY_CALIBRATION[status]
    if model["score_type"] != expected_score_type:
        _fail("score_interpretation_mismatch", "model.score_type")

    representation = calibration["representation"]
    if representation not in CALIBRATION_REPRESENTATIONS:
        # Defensive: the schema enum should make this unreachable.
        _fail("descriptor_schema_invalid", "model.calibration.representation")
    reference_fields = ("calibration_ref", "calibration_sha256", "calibration_size_bytes")
    present = [key for key in reference_fields if calibration[key] is not None]

    if status in {"uncalibrated", "not_assessed"}:
        # An uncalibrated or unassessed model must not ship calibration evidence
        # that could later be mistaken for a verified calibration.
        if representation != "none" or present:
            _fail(
                "calibration_reference_unexpected", "model.calibration.representation"
            )
        integrity = CALIBRATION_INTEGRITY_NONE
    elif representation == "separate_artifact":
        # Every field is required: the validator reads these bytes below, so a
        # partially declared separate calibration cannot be verified.
        for key in reference_fields:
            if calibration[key] is None:
                _fail("calibration_reference_missing", f"model.calibration.{key}")
        integrity = CALIBRATION_INTEGRITY_VERIFIED
    elif representation == "embedded_in_verified_artifact":
        # The model container is hashed but never opened, so an embedded
        # calibration cannot be independently verified here.
        if present:
            _fail("calibration_reference_unexpected", f"model.calibration.{present[0]}")
        integrity = CALIBRATION_INTEGRITY_EMBEDDED
    else:  # calibrated + representation "none"
        _fail("calibration_integrity_missing", "model.calibration.representation")

    explainability = model["explainability"]
    capability = explainability["capability"]
    if capability == EXPLAINABILITY_VERIFIED_CLAIM:
        # No genuine TreeSHAP/LIME implementation exists in this repository;
        # a descriptor may not assert that one does.
        _fail("explainability_claim_unsupported", "model.explainability.capability")
    expected_capability = EXPLAINABILITY_CAPABILITY[explainability["method"]]
    if capability != expected_capability:
        _fail("explainability_capability_mismatch", "model.explainability.capability")

    return integrity


def _check_feature_contract(
    document: Mapping[str, Any], policy: AdmissionPolicy
) -> None:
    contract = document["feature_contract"]
    schema_id = contract["feature_schema_id"]
    schema = policy.catalog.schemas.get(schema_id)
    if schema is None:
        _fail("unknown_feature_schema", "feature_contract.feature_schema_id")
    if policy.catalog.digests.get(schema_id) != contract["feature_schema_sha256"]:
        _fail("feature_schema_digest_mismatch", "feature_contract.feature_schema_sha256")

    declared = contract["features"]
    names = [feature["name"] for feature in declared]
    if len(set(names)) != len(names):
        _fail("duplicate_feature", "feature_contract.features")

    properties = schema.get("properties")
    if not isinstance(properties, Mapping) or not properties:
        _fail("feature_schema_unsupported", "feature_contract.feature_schema_id")
    if set(names) != set(properties):
        _fail("feature_set_mismatch", "feature_contract.features")

    # ---- ordered binding (Correction 1) ---------------------------------- #
    # Position comes from the reviewed policy, never from schema serialization.
    active = policy.input_order_policy
    if active is None:
        _fail("feature_order_policy_missing", "feature_contract.order_policy_id")

    # The supplied policy must *be* the registered, code-reviewed definition:
    # reusing a registered id with a different ordering, status, schema
    # coverage or metadata is rejected. Registration identity -- not the id
    # string alone -- is what makes a position binding trustworthy.
    registered_active = registered_feature_order_policy(active.policy_id)
    if registered_active is None:
        _fail("feature_order_policy_not_registered", "feature_contract.order_policy_id")
    if not is_registered_definition(active, registered_active):
        _fail("feature_order_policy_tampered", "feature_contract.order_policy_id")

    declared_policy_id = contract["order_policy_id"]
    if registered_feature_order_policy(declared_policy_id) is None:
        _fail("feature_order_policy_unknown", "feature_contract.order_policy_id")
    if declared_policy_id != active.policy_id:
        _fail("feature_order_policy_mismatch", "feature_contract.order_policy_id")
    # Read the order from the registered definition, never from the caller's
    # object, so a verified-identical copy and the registered policy agree.
    approved_order = registered_active.order_for(schema_id)
    if approved_order is None:
        # A schema with no registered order cannot be admitted: guessing an
        # order would silently change the model's input semantics.
        _fail("feature_order_unregistered", "feature_contract.feature_schema_id")

    orders = sorted(feature["order"] for feature in declared)
    if orders != list(range(len(declared))):
        # Duplicate, missing, negative or out-of-range indices.
        _fail("feature_order_mismatch", "feature_contract.features")

    if len(declared) != len(approved_order):
        _fail("feature_position_binding_mismatch", "feature_contract.features")
    for position, feature in enumerate(sorted(declared, key=lambda item: item["order"])):
        if feature["name"] != approved_order[position]:
            # Exchanging the order numbers of two otherwise valid features is
            # a semantic change to the model input vector: reject it.
            _fail("feature_position_binding_mismatch", "feature_contract.features")

    required = set(schema.get("required", []))

    for feature in declared:
        try:
            rules = feature_rules(properties[feature["name"]])
        except (KeyError, TypeError):
            _fail("feature_schema_unsupported", "feature_contract.feature_schema_id")
        unit_rule = rules.get("unit")
        value_rule = rules.get("value")
        if (
            not isinstance(unit_rule, Mapping)
            or not isinstance(unit_rule.get("const"), str)
            or not isinstance(value_rule, Mapping)
            or not isinstance(value_rule.get("type"), str)
        ):
            # The shared schema cannot be interpreted unambiguously: refuse
            # rather than guessing a type or a unit.
            _fail("feature_schema_unsupported", "feature_contract.feature_schema_id")
        if feature["unit"] != unit_rule["const"]:
            _fail("feature_unit_mismatch", "feature_contract.features")
        if feature["value_type"] != value_rule["type"]:
            _fail("feature_type_mismatch", "feature_contract.features")
        if feature["required"] is not (feature["name"] in required):
            _fail("feature_required_mismatch", "feature_contract.features")


def _check_target(document: Mapping[str, Any], policy: AdmissionPolicy) -> None:
    target = document["target"]
    registered = policy.registered_targets.get(target["target_id"])
    if registered is None:
        _fail("unknown_target", "target.target_id")
    if _target_digest(registered) != target["target_definition_sha256"]:
        _fail("target_definition_mismatch", "target.target_definition_sha256")
    if target["source_cohort"]["pooled_cohorts"] is not False:
        _fail("cohort_pooling_not_admitted", "target.source_cohort.pooled_cohorts")


def _read(source: ArtifactSource, ref: str, field: str) -> bytes:
    try:
        data = source.read_bytes(ref)
    except ArtifactReferenceError as error:
        _fail(error.code, field)
    if not isinstance(data, bytes) or not data:
        _fail("artifact_reference_invalid", field)
    return data


def _verify_bytes(document: Mapping[str, Any], source: ArtifactSource) -> tuple[str, ...]:
    artifact = document["artifact"]
    ref = artifact["artifact_ref"]
    suffixes = ARTIFACT_TYPE_SUFFIXES[artifact["artifact_type"]]
    if not ref.lower().endswith(suffixes):
        _fail("artifact_type_reference_mismatch", "artifact.artifact_ref")

    artifact_bytes = _read(source, ref, "artifact.artifact_ref")
    if len(artifact_bytes) != artifact["artifact_size_bytes"]:
        _fail("artifact_size_mismatch", "artifact.artifact_size_bytes")
    if _sha256(artifact_bytes) != artifact["artifact_sha256"]:
        _fail("artifact_sha256_mismatch", "artifact.artifact_sha256")

    preprocessing_bytes = _read(
        source, artifact["preprocessing_ref"], "artifact.preprocessing_ref"
    )
    if _sha256(preprocessing_bytes) != artifact["preprocessing_sha256"]:
        _fail("preprocessing_sha256_mismatch", "artifact.preprocessing_sha256")

    protocol_bytes = _read(
        source, document["provenance"]["protocol_ref"], "provenance.protocol_ref"
    )
    if _sha256(protocol_bytes) != document["provenance"]["protocol_sha256"]:
        _fail("protocol_sha256_mismatch", "provenance.protocol_sha256")

    verified = [
        ref,
        artifact["preprocessing_ref"],
        document["provenance"]["protocol_ref"],
    ]

    # ---- calibration bytes (Correction 2) --------------------------------- #
    calibration = document["model"]["calibration"]
    if calibration["representation"] == "separate_artifact":
        calibration_ref = calibration["calibration_ref"]
        other_refs = {
            artifact["artifact_ref"],
            artifact["preprocessing_ref"],
            document["provenance"]["protocol_ref"],
        }
        if calibration_ref in other_refs:
            # Reusing another verified reference would let one file stand in
            # for two independently declared artifacts.
            _fail("calibration_reference_conflict", "model.calibration.calibration_ref")
        calibration_bytes = _read(
            source, calibration_ref, "model.calibration.calibration_ref"
        )
        if len(calibration_bytes) != calibration["calibration_size_bytes"]:
            _fail(
                "calibration_size_mismatch", "model.calibration.calibration_size_bytes"
            )
        if _sha256(calibration_bytes) != calibration["calibration_sha256"]:
            # A syntactically valid but arbitrary digest cannot qualify: only
            # bytes actually read from the source can match.
            _fail(
                "calibration_sha256_mismatch", "model.calibration.calibration_sha256"
            )
        verified.append(calibration_ref)

    return tuple(verified)
