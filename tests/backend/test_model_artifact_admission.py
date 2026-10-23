"""Offline research-artifact admission checks — synthetic, non-clinical only.

Every artifact byte, protocol file and target definition in this module is an
invented placeholder created in memory or in a temporary directory. No dataset,
model artifact, protected manifest or patient record is read, written or
uploaded, and no model is fitted or served.
"""

from __future__ import annotations

import ast
import copy
import dataclasses
import hashlib
import json
import pickle
from pathlib import Path

import pytest

import backend.app.artifact_admission.sources as sources_module
from jsonschema import Draft202012Validator

from backend.app.artifact_admission import (
    D047_NON_APPROVAL_REASON,
    DESCRIPTOR_SCHEMA_VERSION,
    NON_APPROVAL_REASONS,
    RESEARCH_ONLY,
    SUPPORTED_MODEL_FAMILIES,
    AdmissionPolicy,
    ArtifactAdmissionError,
    ArtifactReferenceError,
    DirectoryArtifactSource,
    InMemoryArtifactSource,
    admit_research_artifact,
)
from backend.app.inference import FailClosedRealModelProvider, RealModelServingNotAuthorized

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "shared" / "contracts" / "schemas"
FEATURE_SCHEMA_ID = "mock_clinical_v1"
FEATURE_SCHEMA_FILE = SCHEMAS / "mock_clinical_feature_schema.v1.json"
PACKAGE = ROOT / "backend" / "app" / "artifact_admission"

# Independent expectation of the pinned MOCK_ONLY v1 feature contract, so an
# unannounced schema change fails the admission tests instead of silently
# altering an artifact's declared units or types.
FEATURE_ORDER = (
    ("mock_feature_binary_flag", "boolean", "u_boolean", False),
    ("mock_feature_count", "integer", "u_count", False),
    ("mock_feature_demographic_age", "integer", "u_years", True),
    ("mock_feature_demographic_sex", "string", "u_category", True),
    ("mock_feature_fraction", "number", "u_fraction", False),
    ("mock_feature_lab_concentration", "number", "u_concentration", False),
    ("mock_feature_vital_systolic", "number", "u_pressure", False),
)

ARTIFACT_MARKER = "SECRET-ARTIFACT-CONTENT-MUST-NOT-LEAK"
ARTIFACT_BYTES = f"{ARTIFACT_MARKER}-synthetic-non-clinical-bytes".encode("utf-8")
PREPROCESSING_BYTES = b'{"preprocessing": "synthetic-non-clinical-placeholder"}'
PROTOCOL_BYTES = b"# Synthetic non-clinical protocol placeholder for tests\n"
TARGET_ID = "synthetic-target-cad-presence-v1"
TARGET_DEFINITION = "SYNTHETIC TEST TARGET: invented label for validator tests only."
MISSING = object()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _base_descriptor() -> dict:
    return {
        "descriptor_schema_version": DESCRIPTOR_SCHEMA_VERSION,
        "artifact": {
            "artifact_id": "synthetic-research-artifact-0001",
            "artifact_version": "0.1.0",
            "artifact_type": "joblib",
            "artifact_ref": "model.joblib",
            "artifact_sha256": _sha(ARTIFACT_BYTES),
            "artifact_size_bytes": len(ARTIFACT_BYTES),
            "preprocessing_ref": "preprocessing.json",
            "preprocessing_sha256": _sha(PREPROCESSING_BYTES),
        },
        "model": {
            "model_family": "l2_logistic_regression",
            "preprocessing_version": "synthetic-prep-0.1",
            "score_type": "uncalibrated_margin",
            "calibration": {"status": "uncalibrated", "calibration_sha256": None},
            "explainability": {
                "method": "tree_shap",
                "capability": "available_in_research_harness",
            },
        },
        "feature_contract": {
            "feature_schema_id": FEATURE_SCHEMA_ID,
            "feature_schema_sha256": _sha(FEATURE_SCHEMA_FILE.read_bytes()),
            "features": [
                {
                    "name": name,
                    "order": order,
                    "value_type": value_type,
                    "unit": unit,
                    "required": required,
                }
                for order, (name, value_type, unit, required) in enumerate(FEATURE_ORDER)
            ],
        },
        "target": {
            "target_id": TARGET_ID,
            "target_definition_sha256": _sha(TARGET_DEFINITION.strip().encode("utf-8")),
            "prediction_timepoint": "synthetic_index_encounter",
            "source_cohort": {
                "cohort_id": "SYNTHETIC/NON-CLINICAL",
                "dataset_id": "SYNTHETIC",
                "pooled_cohorts": False,
            },
        },
        "provenance": {
            "protocol_id": "CAI-SYNTHETIC-ADMISSION-TEST-V0.1",
            "protocol_ref": "protocol.md",
            "protocol_sha256": _sha(PROTOCOL_BYTES),
            "experiment_id": "CAI-SYNTHETIC-ADMISSION-EXPERIMENT",
            "code_commit": "0" * 40,
            "generated_at_utc": "2026-10-23T00:00:00Z",
        },
        "eligibility": {
            "research_label": "INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED",
            "serving_status": RESEARCH_ONLY,
        },
    }


def _child(node, part):
    return node[int(part)] if isinstance(node, list) else node[part]


def _descriptor(*changes: tuple[str, object]) -> dict:
    document = copy.deepcopy(_base_descriptor())
    for path, value in changes:
        parts = path.split(".")
        node = document
        for part in parts[:-1]:
            node = _child(node, part)
        key = int(parts[-1]) if isinstance(node, list) else parts[-1]
        if value is MISSING:
            del node[key]
        else:
            node[key] = value
    return document


def _set_feature(index: int, key: str, value: object) -> tuple[str, object]:
    return (f"feature_contract.features.{index}.{key}", value)


@pytest.fixture(scope="module")
def policy() -> AdmissionPolicy:
    return AdmissionPolicy.from_shared_contracts(registered_targets={TARGET_ID: TARGET_DEFINITION})


@pytest.fixture
def source() -> InMemoryArtifactSource:
    return InMemoryArtifactSource(
        {
            "model.joblib": ARTIFACT_BYTES,
            "preprocessing.json": PREPROCESSING_BYTES,
            "protocol.md": PROTOCOL_BYTES,
        }
    )


def _reject(document, source, policy, code: str) -> ArtifactAdmissionError:
    with pytest.raises(ArtifactAdmissionError) as captured:
        admit_research_artifact(document, source=source, policy=policy)
    assert captured.value.code == code, str(captured.value)
    return captured.value


# --------------------------------------------------------------------------- #
# Happy path and the permanent research-only boundary
# --------------------------------------------------------------------------- #


def test_valid_synthetic_descriptor_is_admitted_for_research_only(source, policy):
    decision = admit_research_artifact(_descriptor(), source=source, policy=policy)

    assert decision.descriptor_schema_version == DESCRIPTOR_SCHEMA_VERSION
    assert decision.artifact_id == "synthetic-research-artifact-0001"
    assert decision.artifact_version == "0.1.0"
    assert decision.model_family in SUPPORTED_MODEL_FAMILIES
    assert decision.feature_schema_id == FEATURE_SCHEMA_ID
    assert decision.feature_names == tuple(item[0] for item in FEATURE_ORDER)
    assert decision.target_id == TARGET_ID
    assert decision.source_cohort_id == "SYNTHETIC/NON-CLINICAL"
    assert decision.prediction_timepoint == "synthetic_index_encounter"
    assert decision.serving_eligibility == RESEARCH_ONLY
    assert decision.approved_for_serving is False
    assert decision.verified_refs == ("model.joblib", "preprocessing.json", "protocol.md")
    assert set(NON_APPROVAL_REASONS) <= set(decision.non_approval_reasons)
    assert len(decision.descriptor_sha256) == 64


def test_d047_internal_exploratory_label_is_never_a_deployable_model(source, policy):
    decision = admit_research_artifact(_descriptor(), source=source, policy=policy)

    assert decision.research_label == "INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED"
    assert D047_NON_APPROVAL_REASON in decision.non_approval_reasons
    assert decision.approved_for_serving is False
    assert decision.serving_eligibility == RESEARCH_ONLY


def test_successful_admission_never_grants_serving_or_clinical_approval(source, policy):
    decision = admit_research_artifact(_descriptor(), source=source, policy=policy)

    with pytest.raises(dataclasses.FrozenInstanceError):
        decision.approved_for_serving = True  # type: ignore[misc]
    with pytest.raises(TypeError):
        dataclasses.replace(decision, approved_for_serving=True)
    with pytest.raises(TypeError):
        dataclasses.replace(decision, serving_eligibility="APPROVED_FOR_SERVING")
    assert "approved_for_serving" not in {field.name for field in dataclasses.fields(decision)}


def test_research_only_admission_cannot_construct_a_real_model_provider(source, policy):
    decision = admit_research_artifact(_descriptor(), source=source, policy=policy)

    with pytest.raises(RealModelServingNotAuthorized):
        FailClosedRealModelProvider(decision)
    with pytest.raises(RealModelServingNotAuthorized):
        FailClosedRealModelProvider()


def test_decision_carries_no_artifact_content_or_training_rows(source, policy):
    decision = admit_research_artifact(_descriptor(), source=source, policy=policy)

    rendered = f"{decision!r}{decision}"
    assert ARTIFACT_MARKER not in rendered
    for absent in ("artifact_bytes", "training_rows", "rows", "patient_ref", "manifest"):
        assert not hasattr(decision, absent)
    assert all(isinstance(value, (str, bool, tuple)) for value in dataclasses.astuple(decision))


def test_admission_works_with_a_directory_source(tmp_path, policy):
    root = tmp_path / "package"
    (root / "nested").mkdir(parents=True)
    (root / "model.joblib").write_bytes(ARTIFACT_BYTES)
    (root / "nested" / "preprocessing.json").write_bytes(PREPROCESSING_BYTES)
    (root / "protocol.md").write_bytes(PROTOCOL_BYTES)

    document = _descriptor(("artifact.preprocessing_ref", "nested/preprocessing.json"))
    decision = admit_research_artifact(
        document, source=DirectoryArtifactSource(root), policy=policy
    )

    assert decision.serving_eligibility == RESEARCH_ONLY
    assert decision.verified_refs == (
        "model.joblib",
        "nested/preprocessing.json",
        "protocol.md",
    )


# --------------------------------------------------------------------------- #
# Structural rejections
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "path",
    [
        "descriptor_schema_version",
        "artifact",
        "artifact.artifact_id",
        "artifact.artifact_sha256",
        "artifact.preprocessing_sha256",
        "model",
        "model.calibration",
        "feature_contract",
        "feature_contract.feature_schema_sha256",
        "feature_contract.features",
        "target",
        "target.source_cohort",
        "target.prediction_timepoint",
        "provenance",
        "provenance.protocol_ref",
        "eligibility",
        "eligibility.serving_status",
    ],
)
def test_missing_required_field_is_rejected(path, source, policy):
    error = _reject(_descriptor((path, MISSING)), source, policy, "descriptor_schema_invalid")
    assert error.field == path


@pytest.mark.parametrize(
    "path",
    [
        "clinical_approval",
        "patient_rows",
        "artifact.clinical_clearance",
        "model.threshold",
        "feature_contract.feature_dictionary",
        "target.training_data_sha256",
        "eligibility.approved_by",
    ],
)
def test_unknown_field_is_rejected(path, source, policy):
    _reject(_descriptor((path, True)), source, policy, "descriptor_schema_invalid")


def test_unknown_descriptor_version_is_rejected(source, policy):
    _reject(
        _descriptor(("descriptor_schema_version", "artifact_descriptor/v2")),
        source,
        policy,
        "descriptor_schema_invalid",
    )


def test_non_object_descriptor_is_rejected(source, policy):
    for document in ([], "descriptor", 7, None):
        _reject(document, source, policy, "malformed_descriptor")


# --------------------------------------------------------------------------- #
# Feature contract: no silent unit, type, order or schema changes
# --------------------------------------------------------------------------- #


def test_duplicate_feature_is_rejected(source, policy):
    document = _descriptor()
    duplicate = copy.deepcopy(document["feature_contract"]["features"][0])
    duplicate["order"] = len(document["feature_contract"]["features"])
    document["feature_contract"]["features"].append(duplicate)

    _reject(document, source, policy, "duplicate_feature")


@pytest.mark.parametrize("order", [0, 99])
def test_incompatible_feature_ordering_is_rejected(order, source, policy):
    _reject(
        _descriptor(_set_feature(1, "order", order)), source, policy, "feature_order_mismatch"
    )


def test_feature_unit_change_is_rejected(source, policy):
    _reject(
        _descriptor(_set_feature(2, "unit", "u_fraction")),
        source,
        policy,
        "feature_unit_mismatch",
    )


def test_feature_type_change_is_rejected(source, policy):
    _reject(
        _descriptor(_set_feature(2, "value_type", "number")),
        source,
        policy,
        "feature_type_mismatch",
    )


def test_feature_required_flag_change_is_rejected(source, policy):
    _reject(
        _descriptor(_set_feature(2, "required", False)),
        source,
        policy,
        "feature_required_mismatch",
    )


@pytest.mark.parametrize(
    "changes",
    [
        (("feature_contract.features.0.name", "mock_feature_not_in_schema"),),
        (("feature_contract.features.6", MISSING),),
    ],
)
def test_feature_set_must_match_the_pinned_schema(changes, source, policy):
    _reject(_descriptor(*changes), source, policy, "feature_set_mismatch")


def test_unknown_feature_schema_is_rejected(source, policy):
    _reject(
        _descriptor(("feature_contract.feature_schema_id", "mock_clinical_v9")),
        source,
        policy,
        "unknown_feature_schema",
    )


def test_feature_schema_hash_mismatch_is_rejected(source, policy):
    _reject(
        _descriptor(("feature_contract.feature_schema_sha256", "0" * 64)),
        source,
        policy,
        "feature_schema_digest_mismatch",
    )


# --------------------------------------------------------------------------- #
# Model, score interpretation and explainability
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "family", ["l1_logistic_regression", "xgboost", "neural_network", "unregistered_family"]
)
def test_unexpected_model_family_is_rejected(family, source, policy):
    _reject(
        _descriptor(("model.model_family", family)), source, policy, "unexpected_model_family"
    )


@pytest.mark.parametrize(
    "changes",
    [
        # A raw margin cannot be promoted to a probability by the descriptor.
        (
            ("model.calibration.status", "calibrated"),
            ("model.calibration.calibration_sha256", "1" * 64),
            ("model.score_type", "uncalibrated_margin"),
        ),
        # An uncalibrated model cannot declare a calibrated probability.
        (("model.score_type", "calibrated_probability"),),
        # An unassessed model cannot declare any score interpretation.
        (
            ("model.calibration.status", "not_assessed"),
            ("model.score_type", "uncalibrated_margin"),
        ),
    ],
)
def test_score_interpretation_mismatch_is_rejected(changes, source, policy):
    _reject(_descriptor(*changes), source, policy, "score_interpretation_mismatch")


def test_calibrated_status_requires_a_pinned_calibration_hash(source, policy):
    _reject(
        _descriptor(
            ("model.calibration.status", "calibrated"),
            ("model.calibration.calibration_sha256", None),
            ("model.score_type", "calibrated_probability"),
        ),
        source,
        policy,
        "calibration_reference_missing",
    )


def test_uncalibrated_status_rejects_a_calibration_hash(source, policy):
    _reject(
        _descriptor(("model.calibration.calibration_sha256", "2" * 64)),
        source,
        policy,
        "calibration_reference_unexpected",
    )


def test_accepted_calibrated_descriptor_stays_research_only(source, policy):
    document = _descriptor(
        ("model.calibration.status", "calibrated"),
        ("model.calibration.calibration_sha256", "3" * 64),
        ("model.score_type", "calibrated_probability"),
    )
    decision = admit_research_artifact(document, source=source, policy=policy)

    assert decision.serving_eligibility == RESEARCH_ONLY
    assert decision.approved_for_serving is False


@pytest.mark.parametrize(
    "changes",
    [
        # LIME and no-explanation are future capabilities; the base descriptor
        # already declares the available TreeSHAP-shaped capability.
        (("model.explainability.method", "lime"),),
        (("model.explainability.method", "none"),),
    ],
)
def test_explainability_capability_mismatch_is_rejected(changes, source, policy):
    _reject(_descriptor(*changes), source, policy, "explainability_capability_mismatch")


# --------------------------------------------------------------------------- #
# Target semantics and cohort scope
# --------------------------------------------------------------------------- #


def test_undeclared_target_change_is_rejected(source, policy):
    _reject(
        _descriptor(("target.target_definition_sha256", "4" * 64)),
        source,
        policy,
        "target_definition_mismatch",
    )


def test_unregistered_target_id_is_rejected(source, policy):
    _reject(
        _descriptor(("target.target_id", "fabricated-target-v1")), source, policy, "unknown_target"
    )


def test_registered_target_redefinition_cannot_match_an_old_descriptor(source):
    altered = AdmissionPolicy.from_shared_contracts(
        registered_targets={TARGET_ID: "SILENTLY WIDENED TARGET SEMANTICS"}
    )
    _reject(_base_descriptor(), source, altered, "target_definition_mismatch")


def test_cohort_pooling_is_not_admitted(source, policy):
    _reject(
        _descriptor(("target.source_cohort.pooled_cohorts", True)),
        source,
        policy,
        "cohort_pooling_not_admitted",
    )


# --------------------------------------------------------------------------- #
# Byte-level integrity: hashes, size and references
# --------------------------------------------------------------------------- #


def test_artifact_hash_mismatch_is_rejected(source, policy):
    _reject(
        _descriptor(("artifact.artifact_sha256", "5" * 64)),
        source,
        policy,
        "artifact_sha256_mismatch",
    )


def test_tampered_artifact_bytes_are_rejected(policy):
    tampered = InMemoryArtifactSource(
        {
            "model.joblib": ARTIFACT_BYTES + b"tampered",
            "preprocessing.json": PREPROCESSING_BYTES,
            "protocol.md": PROTOCOL_BYTES,
        }
    )
    _reject(_base_descriptor(), tampered, policy, "artifact_size_mismatch")


def test_artifact_size_mismatch_is_rejected(source, policy):
    _reject(
        _descriptor(("artifact.artifact_size_bytes", len(ARTIFACT_BYTES) + 1)),
        source,
        policy,
        "artifact_size_mismatch",
    )


def test_preprocessing_hash_mismatch_is_rejected(source, policy):
    _reject(
        _descriptor(("artifact.preprocessing_sha256", "6" * 64)),
        source,
        policy,
        "preprocessing_sha256_mismatch",
    )


def test_protocol_hash_mismatch_is_rejected(source, policy):
    _reject(
        _descriptor(("provenance.protocol_sha256", "7" * 64)),
        source,
        policy,
        "protocol_sha256_mismatch",
    )


@pytest.mark.parametrize(
    "changes",
    [
        (("artifact.artifact_type", "pickle"),),
        (("artifact.artifact_type", "onnx"),),
        (("artifact.artifact_type", "safetensors"),),
    ],
)
def test_artifact_type_and_reference_must_agree(changes, source, policy):
    _reject(_descriptor(*changes), source, policy, "artifact_type_reference_mismatch")


def test_missing_artifact_reference_is_rejected(policy):
    empty = InMemoryArtifactSource({"protocol.md": PROTOCOL_BYTES})
    _reject(_base_descriptor(), empty, policy, "artifact_missing")


@pytest.mark.parametrize(
    "ref",
    ["/etc/passwd", "../outside.txt", "sub/../model.joblib", "sub//model.joblib", "a\\b.joblib"],
)
def test_invalid_artifact_reference_is_rejected_structurally(ref, source, policy):
    _reject(
        _descriptor(("artifact.artifact_ref", ref)),
        source,
        policy,
        "descriptor_schema_invalid",
    )


@pytest.mark.parametrize(
    "ref, code",
    [
        ("../outside.txt", "artifact_reference_invalid"),
        ("/etc/passwd", "artifact_reference_invalid"),
        ("sub/../model.joblib", "artifact_reference_invalid"),
        ("link.joblib", "artifact_symlink_not_permitted"),
        ("missing.joblib", "artifact_missing"),
        ("sub", "artifact_missing"),
        ("", "artifact_reference_invalid"),
    ],
)
def test_directory_source_rejects_unsafe_references(tmp_path, ref, code):
    root = tmp_path / "package"
    (root / "sub").mkdir(parents=True)
    (root / "model.joblib").write_bytes(ARTIFACT_BYTES)
    (tmp_path / "outside.txt").write_bytes(b"outside")
    (root / "link.joblib").symlink_to(tmp_path / "outside.txt")

    with pytest.raises(ArtifactReferenceError) as captured:
        DirectoryArtifactSource(root).read_bytes(ref)
    assert captured.value.code == code


def test_directory_source_rejects_oversized_files(tmp_path, monkeypatch):
    root = tmp_path / "package"
    root.mkdir()
    (root / "model.joblib").write_bytes(b"0123456789")
    monkeypatch.setattr(sources_module, "MAX_ARTIFACT_BYTES", 4)

    with pytest.raises(ArtifactReferenceError) as captured:
        DirectoryArtifactSource(root).read_bytes("model.joblib")
    assert captured.value.code == "artifact_too_large"


def test_directory_source_never_escapes_its_root(tmp_path):
    root = tmp_path / "package"
    root.mkdir()
    (tmp_path / "secret.manifest.json").write_bytes(b'{"patient":"must-not-be-read"}')
    source = DirectoryArtifactSource(root)

    with pytest.raises(ArtifactReferenceError):
        source.read_bytes("../secret.manifest.json")


# --------------------------------------------------------------------------- #
# No deserialization, no loaders, no network, no logging
# --------------------------------------------------------------------------- #


def test_pickle_artifacts_are_hashed_without_deserialization(monkeypatch, policy):
    payload = pickle.dumps({"malicious": "object must never be loaded"})

    def forbidden(*args, **kwargs):
        raise AssertionError("artifact deserialization was attempted")

    monkeypatch.setattr(pickle, "load", forbidden)
    monkeypatch.setattr(pickle, "loads", forbidden)
    source = InMemoryArtifactSource(
        {
            "model.pkl": payload,
            "preprocessing.json": PREPROCESSING_BYTES,
            "protocol.md": PROTOCOL_BYTES,
        }
    )
    document = _descriptor(
        ("artifact.artifact_type", "pickle"),
        ("artifact.artifact_ref", "model.pkl"),
        ("artifact.artifact_sha256", _sha(payload)),
        ("artifact.artifact_size_bytes", len(payload)),
    )

    decision = admit_research_artifact(document, source=source, policy=policy)
    assert decision.serving_eligibility == RESEARCH_ONLY


def test_package_imports_no_deserializer_network_or_logging_module():
    forbidden = {
        "pickle",
        "joblib",
        "sklearn",
        "numpy",
        "torch",
        "onnxruntime",
        "safetensors",
        "requests",
        "httpx",
        "socket",
        "subprocess",
        "logging",
        "os",
    }
    for path in sorted(PACKAGE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert not imported & forbidden, f"{path.name} imports {imported & forbidden}"


# --------------------------------------------------------------------------- #
# Failure paths never leak descriptor contents, artifact bytes or identifiers
# --------------------------------------------------------------------------- #


def test_structural_rejection_does_not_echo_descriptor_values(caplog, source, policy):
    sentinel = "PATIENT-JOHN-DOE-0042-MRN-999-888"
    error = _reject(
        _descriptor(("artifact.artifact_id", sentinel)), source, policy, "descriptor_schema_invalid"
    )

    rendered = f"{error!s}{error!r}"
    assert sentinel not in rendered
    assert "PATIENT" not in rendered
    assert caplog.records == []


def test_hash_rejection_does_not_echo_artifact_bytes_or_identifiers(caplog, source, policy):
    error = _reject(
        _descriptor(("artifact.artifact_sha256", "8" * 64)),
        source,
        policy,
        "artifact_sha256_mismatch",
    )

    rendered = f"{error!s}{error!r}"
    assert ARTIFACT_MARKER not in rendered
    assert _sha(ARTIFACT_BYTES) not in rendered
    assert "8" * 64 not in rendered
    assert caplog.records == []


def test_target_rejection_does_not_echo_registered_definition(caplog, source):
    sentinel = "REGISTERED-TARGET-DEFINITION-PATIENT-CONTEXT"
    policy = AdmissionPolicy.from_shared_contracts(registered_targets={TARGET_ID: sentinel})
    error = _reject(_base_descriptor(), source, policy, "target_definition_mismatch")

    rendered = f"{error!s}{error!r}"
    assert sentinel not in rendered
    assert caplog.records == []


def test_eligibility_rejections_are_explicit_and_value_free(source, policy):
    error = _reject(
        _descriptor(("eligibility.serving_status", "APPROVED_FOR_SERVING")),
        source,
        policy,
        "self_declared_serving_status_not_permitted",
    )
    assert error.field == "eligibility.serving_status"
    assert "APPROVED_FOR_SERVING" not in f"{error!s}{error!r}"


# --------------------------------------------------------------------------- #
# Policy and catalogue guard rails
# --------------------------------------------------------------------------- #


def test_policy_requires_a_registered_target(policy):
    with pytest.raises(ValueError):
        AdmissionPolicy(registered_targets={}, catalog=policy.catalog)
    with pytest.raises(ValueError):
        AdmissionPolicy(registered_targets={TARGET_ID: 7}, catalog=policy.catalog)
    with pytest.raises(ValueError):
        AdmissionPolicy.from_shared_contracts(registered_targets={TARGET_ID: "   "})


def test_descriptor_schema_is_versioned_and_closed():
    schema = json.loads(
        (PACKAGE / "artifact_descriptor.v1.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)

    assert schema["$id"].endswith("artifact_descriptor.v1.schema.json")
    assert schema["additionalProperties"] is False
    assert schema["properties"]["descriptor_schema_version"]["const"] == DESCRIPTOR_SCHEMA_VERSION
    assert set(schema["required"]) == {
        "descriptor_schema_version",
        "artifact",
        "model",
        "feature_contract",
        "target",
        "provenance",
        "eligibility",
    }
    assert (
        schema["properties"]["eligibility"]["properties"]["serving_status"]["enum"]
        == ["RESEARCH_ONLY", "APPROVED_FOR_SERVING"]
    )


def test_committed_template_is_deliberately_not_admissible(policy):
    document = json.loads(
        (ROOT / "docs" / "model-admission" / "artifact_descriptor.template.json").read_text(
            encoding="utf-8"
        )
    )

    _reject(document, InMemoryArtifactSource({}), policy, "descriptor_schema_invalid")


def test_shared_feature_schema_is_the_only_feature_dictionary(policy):
    """The descriptor cannot introduce names, units or types of its own."""

    schema = policy.catalog.schemas[FEATURE_SCHEMA_ID]
    assert set(schema["properties"]) == {item[0] for item in FEATURE_ORDER}
    assert tuple(schema["required"]) == tuple(
        item[0] for item in FEATURE_ORDER if item[3]
    )
