"""Offline research-artifact admission checks — synthetic, non-clinical only.

Every artifact byte, calibration file, protocol file and target definition in
this module is an invented placeholder created in memory or in a temporary
directory. No dataset, model artifact, protected manifest or patient record is
read, written or uploaded, and no model is fitted or served. No SHAP or LIME
value is computed anywhere.
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
from jsonschema import Draft202012Validator

import backend.app.artifact_admission.sources as sources_module
from backend.app.artifact_admission import (
    CALIBRATION_INTEGRITY_EMBEDDED,
    CALIBRATION_INTEGRITY_NONE,
    CALIBRATION_INTEGRITY_VERIFIED,
    D047_NON_APPROVAL_REASON,
    DESCRIPTOR_SCHEMA_VERSION,
    EMBEDDED_CALIBRATION_REASON,
    EXPLAINABILITY_CAPABILITY,
    EXPLAINABILITY_VERIFIED_CLAIM,
    NON_APPROVAL_REASONS,
    REGISTERED_FEATURE_ORDER_POLICIES,
    RESEARCH_ONLY,
    SUPPORTED_MODEL_FAMILIES,
    SYNTHETIC_FIXTURE_INPUT_ORDER,
    SYNTHETIC_FIXTURE_ORDER_POLICY_ID,
    SYNTHETIC_FIXTURE_ORDER_POLICY_STATUS,
    SYNTHETIC_ONLY_ORDER_REASON,
    UNVERIFIED_EXPLAINABILITY_REASON,
    AdmissionPolicy,
    ArtifactAdmissionError,
    ArtifactReferenceError,
    DirectoryArtifactSource,
    FeatureOrderPolicy,
    FeatureSchemaCatalog,
    InMemoryArtifactSource,
    admit_research_artifact,
    registered_feature_order_policy,
)
from backend.app.inference import FailClosedRealModelProvider, RealModelServingNotAuthorized
from backend.app.validation import feature_rules

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "shared" / "contracts" / "schemas"
PACKAGE = ROOT / "backend" / "app" / "artifact_admission"
FEATURE_SCHEMA_ID = "mock_clinical_v1"
FEATURE_SCHEMA_FILE = SCHEMAS / "mock_clinical_feature_schema.v1.json"

# Independent expectation of the pinned MOCK_ONLY v1 feature contract, so an
# unannounced schema change fails the admission tests instead of silently
# altering an artifact's declared units or types.
FEATURE_ORDER = (
    ("mock_feature_demographic_age", "integer", "u_years", True),
    ("mock_feature_demographic_sex", "string", "u_category", True),
    ("mock_feature_vital_systolic", "number", "u_pressure", False),
    ("mock_feature_lab_concentration", "number", "u_concentration", False),
    ("mock_feature_binary_flag", "boolean", "u_boolean", False),
    ("mock_feature_count", "integer", "u_count", False),
    ("mock_feature_fraction", "number", "u_fraction", False),
)

ARTIFACT_MARKER = "SECRET-ARTIFACT-CONTENT-MUST-NOT-LEAK"
ARTIFACT_BYTES = f"{ARTIFACT_MARKER}-synthetic-non-clinical-bytes".encode("utf-8")
PREPROCESSING_BYTES = b'{"preprocessing": "synthetic-non-clinical-placeholder"}'
PROTOCOL_BYTES = b"# Synthetic non-clinical protocol placeholder for tests\n"
CALIBRATION_BYTES = b'{"calibration": "synthetic-non-clinical-platt-placeholder"}'
TARGET_ID = "synthetic-target-cad-presence-v1"
TARGET_DEFINITION = "SYNTHETIC TEST TARGET: invented label for validator tests only."
MISSING = object()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _schema_features(schema_id: str, order: tuple[str, ...]) -> list[dict]:
    """Build a descriptor feature list for ``order`` from the shared schema."""
    filename = f"mock_clinical_feature_schema.{schema_id.rsplit('_', 1)[-1]}.json"
    schema = json.loads((SCHEMAS / filename).read_text())
    required = set(schema["required"])
    features = []
    for position, name in enumerate(order):
        rules = feature_rules(schema["properties"][name])
        features.append(
            {
                "name": name,
                "order": position,
                "value_type": rules["value"]["type"],
                "unit": rules["unit"]["const"],
                "required": name in required,
            }
        )
    return features


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
            "calibration": {
                "status": "uncalibrated",
                "representation": "none",
                "calibration_ref": None,
                "calibration_sha256": None,
                "calibration_size_bytes": None,
            },
            "explainability": {
                "method": "tree_shap",
                "capability": "mock_shap_shaped_fixture_only",
            },
        },
        "feature_contract": {
            "feature_schema_id": FEATURE_SCHEMA_ID,
            "feature_schema_sha256": _sha(FEATURE_SCHEMA_FILE.read_bytes()),
            "order_policy_id": SYNTHETIC_FIXTURE_ORDER_POLICY_ID,
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


def _calibrated_descriptor() -> dict:
    return _descriptor(
        ("model.calibration.status", "calibrated"),
        ("model.calibration.representation", "separate_artifact"),
        ("model.calibration.calibration_ref", "calibration.json"),
        ("model.calibration.calibration_sha256", _sha(CALIBRATION_BYTES)),
        ("model.calibration.calibration_size_bytes", len(CALIBRATION_BYTES)),
        ("model.score_type", "calibrated_probability"),
    )


@pytest.fixture(scope="module")
def policy() -> AdmissionPolicy:
    return AdmissionPolicy.from_shared_contracts(
        registered_targets={TARGET_ID: TARGET_DEFINITION},
        input_order_policy=SYNTHETIC_FIXTURE_INPUT_ORDER,
    )


@pytest.fixture
def source() -> InMemoryArtifactSource:
    return InMemoryArtifactSource(
        {
            "model.joblib": ARTIFACT_BYTES,
            "preprocessing.json": PREPROCESSING_BYTES,
            "protocol.md": PROTOCOL_BYTES,
            "calibration.json": CALIBRATION_BYTES,
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
    assert decision.feature_order_policy_id == SYNTHETIC_FIXTURE_ORDER_POLICY_ID
    assert decision.feature_order_policy_status == SYNTHETIC_FIXTURE_ORDER_POLICY_STATUS
    assert decision.target_id == TARGET_ID
    assert decision.source_cohort_id == "SYNTHETIC/NON-CLINICAL"
    assert decision.prediction_timepoint == "synthetic_index_encounter"
    assert decision.calibration_status == "uncalibrated"
    assert decision.calibration_integrity == CALIBRATION_INTEGRITY_NONE
    assert decision.explainability_capability == "mock_shap_shaped_fixture_only"
    assert decision.serving_eligibility == RESEARCH_ONLY
    assert decision.approved_for_serving is False
    assert decision.verified_refs == ("model.joblib", "preprocessing.json", "protocol.md")
    assert set(NON_APPROVAL_REASONS) <= set(decision.non_approval_reasons)
    assert UNVERIFIED_EXPLAINABILITY_REASON in decision.non_approval_reasons
    assert SYNTHETIC_ONLY_ORDER_REASON in decision.non_approval_reasons
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
# Correction 1 — explicit ordered feature binding
# --------------------------------------------------------------------------- #


def test_fully_matching_registered_order_is_admitted(source, policy):
    decision = admit_research_artifact(_descriptor(), source=source, policy=policy)

    assert decision.feature_names == SYNTHETIC_FIXTURE_INPUT_ORDER.order_for(FEATURE_SCHEMA_ID)
    assert decision.feature_order_policy_status == "SYNTHETIC_ONLY_NOT_CLINICAL"


@pytest.mark.parametrize(
    "first, second",
    [(0, 1), (0, 6), (2, 3), (5, 6)],
)
def test_swapping_two_valid_feature_positions_is_rejected(first, second, source, policy):
    """Contiguous indices are not enough: position must match the binding."""

    document = _descriptor(
        _set_feature(first, "order", second), _set_feature(second, "order", first)
    )
    # The index set is still exactly 0..6, so only the position check can
    # catch this: it is the semantic change to the model input vector.
    orders = sorted(feature["order"] for feature in document["feature_contract"]["features"])
    assert orders == list(range(7))

    _reject(document, source, policy, "feature_position_binding_mismatch")


def test_cycling_three_feature_positions_is_rejected(source, policy):
    document = _descriptor(
        _set_feature(0, "order", 1), _set_feature(1, "order", 2), _set_feature(2, "order", 0)
    )
    _reject(document, source, policy, "feature_position_binding_mismatch")


def test_renaming_a_feature_into_another_position_is_rejected(source, policy):
    """A name swap keeps the set valid but binds the wrong feature to index 0."""

    document = _descriptor(
        _set_feature(0, "name", "mock_feature_demographic_sex"),
        _set_feature(1, "name", "mock_feature_demographic_age"),
    )
    # The name set is still valid; only the position binding can catch it.
    assert {f["name"] for f in document["feature_contract"]["features"]} == {
        item[0] for item in FEATURE_ORDER
    }
    _reject(document, source, policy, "feature_position_binding_mismatch")


@pytest.mark.parametrize(
    "changes",
    [
        # duplicate index
        (_set_feature(1, "order", 0),),
        # missing index (gap at the end)
        (_set_feature(6, "order", 7),),
        # out-of-range index
        (_set_feature(0, "order", 99),),
        # large duplicate jump
        (_set_feature(0, "order", 6),),
        # duplicate pair covering the same slot
        (_set_feature(2, "order", 5), _set_feature(5, "order", 5)),
    ],
)
def test_duplicate_missing_or_out_of_range_order_indices_are_rejected(
    changes, source, policy
):
    _reject(_descriptor(*changes), source, policy, "feature_order_mismatch")


def test_negative_order_index_is_rejected_structurally(source, policy):
    _reject(
        _descriptor(_set_feature(0, "order", -1)),
        source,
        policy,
        "descriptor_schema_invalid",
    )


def test_missing_order_policy_fails_closed(source):
    """No reviewed binding supplied means no admission, not a guessed order."""

    policy = AdmissionPolicy.from_shared_contracts(
        registered_targets={TARGET_ID: TARGET_DEFINITION}
    )
    assert policy.input_order_policy is None
    error = _reject(_base_descriptor(), source, policy, "feature_order_policy_missing")
    assert error.field == "feature_contract.order_policy_id"


def test_schema_without_a_registered_order_fails_closed(source):
    """A schema the policy does not cover cannot be admitted by inference."""

    v1_only = FeatureOrderPolicy(
        policy_id="synthetic_fixture_input_order/v1",
        status="SYNTHETIC_ONLY_NOT_CLINICAL",
        ordered_feature_names={
            FEATURE_SCHEMA_ID: SYNTHETIC_FIXTURE_INPUT_ORDER.order_for(FEATURE_SCHEMA_ID)
        },
    )
    policy = AdmissionPolicy(
        registered_targets={TARGET_ID: TARGET_DEFINITION},
        catalog=FeatureSchemaCatalog.from_shared_contracts(),
        input_order_policy=v1_only,
    )
    document = _descriptor(
        ("feature_contract.feature_schema_id", "mock_clinical_v2"),
        (
            "feature_contract.feature_schema_sha256",
            _sha((SCHEMAS / "mock_clinical_feature_schema.v2.json").read_bytes()),
        ),
        (
            "feature_contract.features",
            _schema_features(
                "mock_clinical_v2", SYNTHETIC_FIXTURE_INPUT_ORDER.order_for("mock_clinical_v1")
            ),
        ),
    )
    _reject(document, source, policy, "feature_order_unregistered")


def test_unknown_order_policy_id_is_rejected(source, policy):
    _reject(
        _descriptor(("feature_contract.order_policy_id", "fabricated_input_order/v9")),
        source,
        policy,
        "feature_order_policy_unknown",
    )


def test_descriptor_naming_a_different_registered_policy_is_rejected(source):
    alternate = FeatureOrderPolicy(
        policy_id="synthetic_fixture_input_order/v2",
        status="SYNTHETIC_ONLY_NOT_CLINICAL",
        ordered_feature_names=dict(SYNTHETIC_FIXTURE_INPUT_ORDER.ordered_feature_names),
    )
    policy = AdmissionPolicy(
        registered_targets={TARGET_ID: TARGET_DEFINITION},
        catalog=FeatureSchemaCatalog.from_shared_contracts(),
        input_order_policy=alternate,
    )
    _reject(_base_descriptor(), source, policy, "feature_order_policy_mismatch")


def test_missing_order_policy_id_field_is_rejected(source, policy):
    error = _reject(
        _descriptor(("feature_contract.order_policy_id", MISSING)),
        source,
        policy,
        "descriptor_schema_invalid",
    )
    assert error.field == "feature_contract.order_policy_id"


def test_only_the_one_reviewed_policy_is_registered():
    assert set(REGISTERED_FEATURE_ORDER_POLICIES) == {SYNTHETIC_FIXTURE_ORDER_POLICY_ID}
    policy = registered_feature_order_policy(SYNTHETIC_FIXTURE_ORDER_POLICY_ID)
    assert policy is SYNTHETIC_FIXTURE_INPUT_ORDER
    assert policy.status == "SYNTHETIC_ONLY_NOT_CLINICAL"
    assert registered_feature_order_policy("made_up/v1") is None


def test_admission_order_is_not_the_schema_serialization_order(source, policy):
    """mock_clinical_v2 declares `fraction` third; the binding places it last."""

    v2_schema = json.loads((SCHEMAS / "mock_clinical_feature_schema.v2.json").read_text())
    serialization_order = tuple(v2_schema["properties"])
    policy_order = SYNTHETIC_FIXTURE_INPUT_ORDER.order_for("mock_clinical_v2")

    assert serialization_order != policy_order
    assert serialization_order[2] == "mock_feature_fraction"
    assert policy_order[-1] == "mock_feature_fraction"

    def v2_descriptor(order):
        return _descriptor(
            ("feature_contract.feature_schema_id", "mock_clinical_v2"),
            ("feature_contract.feature_schema_sha256", _sha(
                (SCHEMAS / "mock_clinical_feature_schema.v2.json").read_bytes()
            )),
            ("feature_contract.features", _schema_features("mock_clinical_v2", order)),
        )

    # The policy order is admitted...
    decision = admit_research_artifact(v2_descriptor(policy_order), source=source, policy=policy)
    assert decision.feature_names == policy_order

    # ...while the schema's serialization order is refused as an input order.
    _reject(
        v2_descriptor(serialization_order),
        source,
        policy,
        "feature_position_binding_mismatch",
    )


def test_reordered_schema_serialization_does_not_change_the_binding(source, policy):
    """Shuffling schema `properties` must not move a single admitted position."""

    catalog = FeatureSchemaCatalog.from_shared_contracts()
    shuffled = dict(reversed(list(catalog.schemas[FEATURE_SCHEMA_ID]["properties"].items())))
    assert tuple(shuffled) != tuple(catalog.schemas[FEATURE_SCHEMA_ID]["properties"])

    reordered_catalog = FeatureSchemaCatalog(
        schemas={**catalog.schemas, FEATURE_SCHEMA_ID: {
            **catalog.schemas[FEATURE_SCHEMA_ID], "properties": shuffled
        }},
        digests=catalog.digests,
    )
    reordered_policy = AdmissionPolicy(
        registered_targets={TARGET_ID: TARGET_DEFINITION},
        catalog=reordered_catalog,
        input_order_policy=SYNTHETIC_FIXTURE_INPUT_ORDER,
    )

    decision = admit_research_artifact(
        _base_descriptor(), source=source, policy=reordered_policy
    )
    assert decision.feature_names == tuple(item[0] for item in FEATURE_ORDER)

    _reject(
        _descriptor(_set_feature(0, "order", 1), _set_feature(1, "order", 0)),
        source,
        reordered_policy,
        "feature_position_binding_mismatch",
    )


def test_feature_order_policy_rejects_malformed_registrations():
    with pytest.raises(ValueError):
        FeatureOrderPolicy(policy_id="", status="SYNTHETIC_ONLY_NOT_CLINICAL", ordered_feature_names={})
    with pytest.raises(ValueError):
        FeatureOrderPolicy(policy_id="p/v1", status="", ordered_feature_names={})
    # An empty registration is a valid object that can admit nothing: every
    # descriptor then fails closed with feature_order_unregistered.
    assert FeatureOrderPolicy(
        policy_id="p/v1", status="SYNTHETIC_ONLY_NOT_CLINICAL", ordered_feature_names={}
    ).order_for(FEATURE_SCHEMA_ID) is None
    with pytest.raises(ValueError):
        FeatureOrderPolicy(
            policy_id="p/v1",
            status="SYNTHETIC_ONLY_NOT_CLINICAL",
            ordered_feature_names={FEATURE_SCHEMA_ID: ("mock_feature_count", "mock_feature_count")},
        )
    with pytest.raises(ValueError):
        FeatureOrderPolicy(
            policy_id="p/v1",
            status="SYNTHETIC_ONLY_NOT_CLINICAL",
            ordered_feature_names={FEATURE_SCHEMA_ID: ()},
        )


# --------------------------------------------------------------------------- #
# Correction 2 — calibration integrity is actually verified
# --------------------------------------------------------------------------- #


def test_separate_calibration_artifact_is_verified_byte_for_byte(source, policy):
    decision = admit_research_artifact(_calibrated_descriptor(), source=source, policy=policy)

    assert decision.calibration_status == "calibrated"
    assert decision.calibration_integrity == CALIBRATION_INTEGRITY_VERIFIED
    assert decision.verified_refs == (
        "model.joblib",
        "preprocessing.json",
        "protocol.md",
        "calibration.json",
    )
    assert decision.serving_eligibility == RESEARCH_ONLY
    assert decision.approved_for_serving is False
    assert EMBEDDED_CALIBRATION_REASON not in decision.non_approval_reasons


@pytest.mark.parametrize(
    "changes",
    [
        (("model.calibration.calibration_sha256", "f" * 64),),
        (("model.calibration.calibration_sha256", _sha(b"some other bytes")),),
        (
            ("model.calibration.calibration_sha256", "f" * 64),
            ("model.calibration.calibration_size_bytes", len(CALIBRATION_BYTES)),
        ),
    ],
)
def test_fake_but_syntactically_valid_calibration_digest_is_rejected(changes, source, policy):
    """A 64-hex digest alone is not verified calibration integrity."""

    document = _descriptor(
        ("model.calibration.status", "calibrated"),
        ("model.calibration.representation", "separate_artifact"),
        ("model.calibration.calibration_ref", "calibration.json"),
        ("model.calibration.calibration_size_bytes", len(CALIBRATION_BYTES)),
        ("model.score_type", "calibrated_probability"),
        *changes,
    )
    assert all(
        len(str(change[1])) == 64 or isinstance(change[1], int) for change in changes
    )
    _reject(document, source, policy, "calibration_sha256_mismatch")


def test_calibration_size_mismatch_is_rejected(source, policy):
    _reject(
        _descriptor(
            ("model.calibration.status", "calibrated"),
            ("model.calibration.representation", "separate_artifact"),
            ("model.calibration.calibration_ref", "calibration.json"),
            ("model.calibration.calibration_sha256", _sha(CALIBRATION_BYTES)),
            ("model.calibration.calibration_size_bytes", len(CALIBRATION_BYTES) + 1),
            ("model.score_type", "calibrated_probability"),
        ),
        source,
        policy,
        "calibration_size_mismatch",
    )


def test_tampered_calibration_bytes_are_rejected(policy):
    tampered = InMemoryArtifactSource(
        {
            "model.joblib": ARTIFACT_BYTES,
            "preprocessing.json": PREPROCESSING_BYTES,
            "protocol.md": PROTOCOL_BYTES,
            "calibration.json": CALIBRATION_BYTES + b"tampered",
        }
    )
    _reject(_calibrated_descriptor(), tampered, policy, "calibration_size_mismatch")

    same_size_tamper = InMemoryArtifactSource(
        {
            "model.joblib": ARTIFACT_BYTES,
            "preprocessing.json": PREPROCESSING_BYTES,
            "protocol.md": PROTOCOL_BYTES,
            "calibration.json": b"X" * len(CALIBRATION_BYTES),
        }
    )
    _reject(_calibrated_descriptor(), same_size_tamper, policy, "calibration_sha256_mismatch")


@pytest.mark.parametrize(
    "changes",
    [
        (("model.calibration.calibration_ref", None),),
        (("model.calibration.calibration_sha256", None),),
        (("model.calibration.calibration_size_bytes", None),),
    ],
)
def test_separate_calibration_requires_all_reference_fields(changes, source, policy):
    _reject(
        _descriptor(
            ("model.calibration.status", "calibrated"),
            ("model.calibration.representation", "separate_artifact"),
            ("model.calibration.calibration_ref", "calibration.json"),
            ("model.calibration.calibration_sha256", _sha(CALIBRATION_BYTES)),
            ("model.calibration.calibration_size_bytes", len(CALIBRATION_BYTES)),
            ("model.score_type", "calibrated_probability"),
            *changes,
        ),
        source,
        policy,
        "calibration_reference_missing",
    )


def test_missing_calibration_file_is_rejected(policy):
    without_calibration = InMemoryArtifactSource(
        {
            "model.joblib": ARTIFACT_BYTES,
            "preprocessing.json": PREPROCESSING_BYTES,
            "protocol.md": PROTOCOL_BYTES,
        }
    )
    error = _reject(
        _calibrated_descriptor(), without_calibration, policy, "artifact_missing"
    )
    assert error.field == "model.calibration.calibration_ref"


@pytest.mark.parametrize(
    "calibration_ref",
    ["../secret.manifest.json", "/etc/passwd", "sub/../calibration.json", "C:/abs.json"],
)
def test_unsafe_calibration_reference_is_rejected_structurally(tmp_path, calibration_ref):
    """The descriptor pattern and the source both refuse an unsafe reference."""
    root = tmp_path / "package"
    root.mkdir()
    (root / "model.joblib").write_bytes(ARTIFACT_BYTES)
    (root / "preprocessing.json").write_bytes(PREPROCESSING_BYTES)
    (root / "protocol.md").write_bytes(PROTOCOL_BYTES)
    (root / "calibration.json").write_bytes(CALIBRATION_BYTES)
    (tmp_path / "secret.manifest.json").write_bytes(b'{"patient":"must-not-be-read"}')

    policy = AdmissionPolicy.from_shared_contracts(
        registered_targets={TARGET_ID: TARGET_DEFINITION},
        input_order_policy=SYNTHETIC_FIXTURE_INPUT_ORDER,
    )
    document = _descriptor(
        ("model.calibration.status", "calibrated"),
        ("model.calibration.representation", "separate_artifact"),
        ("model.calibration.calibration_ref", calibration_ref),
        ("model.calibration.calibration_sha256", _sha(b'{"patient":"must-not-be-read"}')),
        ("model.calibration.calibration_size_bytes", len(b'{"patient":"must-not-be-read"}')),
        ("model.score_type", "calibrated_probability"),
    )
    error = _reject(document, DirectoryArtifactSource(root), policy, "descriptor_schema_invalid")
    assert "must-not-be-read" not in f"{error!s}{error!r}"
    # Source-level defence is exercised directly below, independently of the
    # descriptor pattern, so neither layer is assumed to be load-bearing alone.
    source = DirectoryArtifactSource(root)
    if calibration_ref in {"../secret.manifest.json", "/etc/passwd"}:
        with pytest.raises(ArtifactReferenceError):
            source.read_bytes(calibration_ref)


def test_symlinked_calibration_file_is_rejected(tmp_path):
    root = tmp_path / "package"
    root.mkdir()
    (root / "model.joblib").write_bytes(ARTIFACT_BYTES)
    (root / "preprocessing.json").write_bytes(PREPROCESSING_BYTES)
    (root / "protocol.md").write_bytes(PROTOCOL_BYTES)
    (tmp_path / "outside.json").write_bytes(CALIBRATION_BYTES)
    (root / "calibration.json").symlink_to(tmp_path / "outside.json")

    policy = AdmissionPolicy.from_shared_contracts(
        registered_targets={TARGET_ID: TARGET_DEFINITION},
        input_order_policy=SYNTHETIC_FIXTURE_INPUT_ORDER,
    )
    _reject(
        _calibrated_descriptor(),
        DirectoryArtifactSource(root),
        policy,
        "artifact_symlink_not_permitted",
    )


def test_calibration_reference_must_not_reuse_another_verified_reference(source, policy):
    _reject(
        _descriptor(
            ("model.calibration.status", "calibrated"),
            ("model.calibration.representation", "separate_artifact"),
            ("model.calibration.calibration_ref", "model.joblib"),
            ("model.calibration.calibration_sha256", _sha(ARTIFACT_BYTES)),
            ("model.calibration.calibration_size_bytes", len(ARTIFACT_BYTES)),
            ("model.score_type", "calibrated_probability"),
        ),
        source,
        policy,
        "calibration_reference_conflict",
    )


def test_calibrated_without_a_representation_fails_closed(source, policy):
    _reject(
        _descriptor(
            ("model.calibration.status", "calibrated"),
            ("model.score_type", "calibrated_probability"),
        ),
        source,
        policy,
        "calibration_integrity_missing",
    )


@pytest.mark.parametrize("status", ["uncalibrated", "not_assessed"])
@pytest.mark.parametrize(
    "changes",
    [
        (("model.calibration.representation", "separate_artifact"),),
        (("model.calibration.representation", "embedded_in_verified_artifact"),),
        (("model.calibration.calibration_ref", "calibration.json"),),
        (("model.calibration.calibration_sha256", "a" * 64),),
        (("model.calibration.calibration_size_bytes", 10),),
    ],
)
def test_unexpected_calibration_reference_is_rejected(changes, status, source, policy):
    score_type = "uncalibrated_margin" if status == "uncalibrated" else "non_interpretable"
    _reject(
        _descriptor(
            ("model.calibration.status", status),
            ("model.score_type", score_type),
            *changes,
        ),
        source,
        policy,
        "calibration_reference_unexpected",
    )


def test_embedded_calibration_is_admitted_only_as_an_unverified_claim(source, policy):
    decision = admit_research_artifact(
        _descriptor(
            ("model.calibration.status", "calibrated"),
            ("model.calibration.representation", "embedded_in_verified_artifact"),
            ("model.score_type", "calibrated_probability"),
        ),
        source=source,
        policy=policy,
    )

    assert decision.calibration_integrity == CALIBRATION_INTEGRITY_EMBEDDED
    assert decision.calibration_integrity != CALIBRATION_INTEGRITY_VERIFIED
    assert EMBEDDED_CALIBRATION_REASON in decision.non_approval_reasons
    # Nothing was read for the embedded calibration, so no reference is claimed.
    assert "calibration.json" not in decision.verified_refs
    assert decision.serving_eligibility == RESEARCH_ONLY


def test_embedded_calibration_may_not_also_assert_a_separate_hash(source, policy):
    _reject(
        _descriptor(
            ("model.calibration.status", "calibrated"),
            ("model.calibration.representation", "embedded_in_verified_artifact"),
            ("model.calibration.calibration_sha256", _sha(CALIBRATION_BYTES)),
            ("model.score_type", "calibrated_probability"),
        ),
        source,
        policy,
        "calibration_reference_unexpected",
    )


def test_embedded_calibration_does_not_claim_artifact_bytes_verification(source, policy):
    """The model container is hashed but never opened, so 'embedded' stays unverified."""

    decision = admit_research_artifact(
        _descriptor(
            ("model.calibration.status", "calibrated"),
            ("model.calibration.representation", "embedded_in_verified_artifact"),
            ("model.score_type", "calibrated_probability"),
        ),
        source=source,
        policy=policy,
    )
    assert decision.calibration_integrity == "EMBEDDED_NOT_INDEPENDENTLY_VERIFIED"
    assert decision.approved_for_serving is False


# --------------------------------------------------------------------------- #
# Correction 3 — no unsupported real-XAI capability claims
# --------------------------------------------------------------------------- #


def test_no_descriptor_may_claim_verified_research_explainability(source, policy):
    error = _reject(
        _descriptor(
            ("model.explainability.capability", EXPLAINABILITY_VERIFIED_CLAIM),
        ),
        source,
        policy,
        "explainability_claim_unsupported",
    )
    assert error.field == "model.explainability.capability"


@pytest.mark.parametrize(
    "method, capability",
    [
        ("tree_shap", "not_implemented"),
        ("tree_shap", EXPLAINABILITY_VERIFIED_CLAIM),
        ("lime", "mock_shap_shaped_fixture_only"),
        ("lime", EXPLAINABILITY_VERIFIED_CLAIM),
        ("none", "mock_shap_shaped_fixture_only"),
        ("none", EXPLAINABILITY_VERIFIED_CLAIM),
    ],
)
def test_explainability_capability_mismatch_is_rejected(method, capability, source, policy):
    expected = (
        "explainability_claim_unsupported"
        if capability == EXPLAINABILITY_VERIFIED_CLAIM
        else "explainability_capability_mismatch"
    )
    _reject(
        _descriptor(
            ("model.explainability.method", method),
            ("model.explainability.capability", capability),
        ),
        source,
        policy,
        expected,
    )


def test_tree_shap_capability_is_truthfully_mock_shaped_only():
    assert EXPLAINABILITY_CAPABILITY["tree_shap"] == "mock_shap_shaped_fixture_only"
    assert EXPLAINABILITY_CAPABILITY["lime"] == "not_implemented"
    assert EXPLAINABILITY_CAPABILITY["none"] == "not_implemented"
    assert EXPLAINABILITY_VERIFIED_CLAIM not in set(EXPLAINABILITY_CAPABILITY.values())


def test_mock_shap_shaped_capability_is_admitted_but_flagged_unverified(source, policy):
    decision = admit_research_artifact(_descriptor(), source=source, policy=policy)

    assert decision.explainability_method == "tree_shap"
    assert decision.explainability_capability == "mock_shap_shaped_fixture_only"
    assert UNVERIFIED_EXPLAINABILITY_REASON in decision.non_approval_reasons


def test_repository_contains_no_genuine_shap_or_lime_implementation():
    """Guard for the truthful capability vocabulary used above."""

    forbidden_modules = {"shap", "lime", "shapley"}
    scanned = sorted(
        path
        for folder in ("backend", "research", "scripts")
        for path in (ROOT / folder).rglob("*.py")
        if "__pycache__" not in path.parts
    )
    assert scanned

    offenders = []
    for path in scanned:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            if {name.split(".")[0] for name in names} & forbidden_modules:
                offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == []

    for requirements in (
        ROOT / "backend" / "requirements.txt",
        ROOT / "research" / "audit" / "requirements.txt",
        ROOT / "research" / "experiments" / "requirements.txt",
    ):
        text = requirements.read_text(encoding="utf-8").lower()
        assert "shap==" not in text and "lime==" not in text


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
        "model.calibration.representation",
        "model.calibration.calibration_ref",
        "model.calibration.calibration_size_bytes",
        "feature_contract",
        "feature_contract.feature_schema_sha256",
        "feature_contract.order_policy_id",
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
        "model.calibration.calibration_verified",
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
# Feature contract: no silent unit, type or schema changes
# --------------------------------------------------------------------------- #


def test_duplicate_feature_is_rejected(source, policy):
    document = _descriptor()
    duplicate = copy.deepcopy(document["feature_contract"]["features"][0])
    duplicate["order"] = len(document["feature_contract"]["features"])
    document["feature_contract"]["features"].append(duplicate)

    _reject(document, source, policy, "duplicate_feature")


def test_feature_unit_change_is_rejected(source, policy):
    _reject(
        _descriptor(_set_feature(2, "unit", "u_fraction")),
        source,
        policy,
        "feature_unit_mismatch",
    )


def test_feature_type_change_is_rejected(source, policy):
    # mock_feature_vital_systolic is `number` in the pinned schema.
    _reject(
        _descriptor(_set_feature(2, "value_type", "integer")),
        source,
        policy,
        "feature_type_mismatch",
    )


def test_feature_required_flag_change_is_rejected(source, policy):
    _reject(
        _descriptor(_set_feature(0, "required", False)),
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
# Model, score interpretation and cohort scope
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
        # A calibrated model must not declare an uncalibrated margin...
        (("model.score_type", "uncalibrated_margin"),),
        # ...nor a non-interpretable score.
        (("model.score_type", "non_interpretable"),),
        # An unassessed model cannot declare a calibrated probability.
        (
            ("model.calibration.status", "not_assessed"),
            ("model.calibration.representation", "none"),
            ("model.calibration.calibration_ref", None),
            ("model.calibration.calibration_sha256", None),
            ("model.calibration.calibration_size_bytes", None),
            ("model.score_type", "calibrated_probability"),
        ),
    ],
)
def test_score_interpretation_mismatch_is_rejected(changes, source, policy):
    document = _descriptor(
        ("model.calibration.status", "calibrated"),
        ("model.calibration.representation", "separate_artifact"),
        ("model.calibration.calibration_ref", "calibration.json"),
        ("model.calibration.calibration_sha256", _sha(CALIBRATION_BYTES)),
        ("model.calibration.calibration_size_bytes", len(CALIBRATION_BYTES)),
        ("model.score_type", "calibrated_probability"),
        *changes,
    )
    _reject(document, source, policy, "score_interpretation_mismatch")


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
        registered_targets={TARGET_ID: "SILENTLY WIDENED TARGET SEMANTICS"},
        input_order_policy=SYNTHETIC_FIXTURE_INPUT_ORDER,
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
# Artifact bytes, references and source safety
# --------------------------------------------------------------------------- #


def test_artifact_hash_mismatch_is_rejected(source, policy):
    _reject(
        _descriptor(("artifact.artifact_sha256", "5" * 64)),
        source,
        policy,
        "artifact_sha256_mismatch",
    )


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
        "shap",
        "lime",
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


def test_calibration_rejection_does_not_echo_bytes_or_digests(caplog, source, policy):
    document = _descriptor(
        ("model.calibration.status", "calibrated"),
        ("model.calibration.representation", "separate_artifact"),
        ("model.calibration.calibration_ref", "calibration.json"),
        ("model.calibration.calibration_sha256", "9" * 64),
        ("model.calibration.calibration_size_bytes", len(CALIBRATION_BYTES)),
        ("model.score_type", "calibrated_probability"),
    )
    error = _reject(document, source, policy, "calibration_sha256_mismatch")

    rendered = f"{error!s}{error!r}"
    assert "9" * 64 not in rendered
    assert _sha(CALIBRATION_BYTES) not in rendered
    assert CALIBRATION_BYTES.decode("utf-8") not in rendered
    assert caplog.records == []


def test_order_rejection_does_not_echo_feature_positions(caplog, source, policy):
    error = _reject(
        _descriptor(_set_feature(0, "order", 1), _set_feature(1, "order", 0)),
        source,
        policy,
        "feature_position_binding_mismatch",
    )
    assert error.field == "feature_contract.features"
    assert caplog.records == []


def test_target_rejection_does_not_echo_registered_definition(caplog, source):
    sentinel = "REGISTERED-TARGET-DEFINITION-PATIENT-CONTEXT"
    policy = AdmissionPolicy.from_shared_contracts(
        registered_targets={TARGET_ID: sentinel},
        input_order_policy=SYNTHETIC_FIXTURE_INPUT_ORDER,
    )
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
# Policy, schema and template guard rails
# --------------------------------------------------------------------------- #


def test_policy_requires_a_registered_target(policy):
    with pytest.raises(ValueError):
        AdmissionPolicy(registered_targets={}, catalog=policy.catalog)
    with pytest.raises(ValueError):
        AdmissionPolicy(registered_targets={TARGET_ID: 7}, catalog=policy.catalog)
    with pytest.raises(ValueError):
        AdmissionPolicy.from_shared_contracts(registered_targets={TARGET_ID: "   "})


def test_admission_policy_has_no_implicit_order_default(policy):
    implicit = AdmissionPolicy(registered_targets={TARGET_ID: TARGET_DEFINITION}, catalog=policy.catalog)
    assert implicit.input_order_policy is None


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
    assert set(schema["properties"]["feature_contract"]["required"]) == {
        "feature_schema_id",
        "feature_schema_sha256",
        "order_policy_id",
        "features",
    }
    assert set(
        schema["properties"]["model"]["properties"]["calibration"]["required"]
    ) == {
        "status",
        "representation",
        "calibration_ref",
        "calibration_sha256",
        "calibration_size_bytes",
    }
    assert (
        schema["properties"]["model"]["properties"]["explainability"]
        ["properties"]["capability"]["enum"]
        == [
            "not_implemented",
            "mock_shap_shaped_fixture_only",
            "implemented_and_verified_in_research_harness",
        ]
    )


def test_committed_template_is_deliberately_not_admissible(policy):
    document = json.loads(
        (ROOT / "docs" / "model-admission" / "artifact_descriptor.template.json").read_text(
            encoding="utf-8"
        )
    )

    _reject(document, InMemoryArtifactSource({}), policy, "descriptor_schema_invalid")


def test_template_states_the_synthetic_order_policy_and_truthful_capability():
    document = json.loads(
        (ROOT / "docs" / "model-admission" / "artifact_descriptor.template.json").read_text(
            encoding="utf-8"
        )
    )

    assert document["feature_contract"]["order_policy_id"] == SYNTHETIC_FIXTURE_ORDER_POLICY_ID
    assert document["model"]["explainability"]["capability"] == "mock_shap_shaped_fixture_only"
    assert document["model"]["calibration"]["representation"] == "none"


def test_shared_feature_schema_is_the_only_feature_dictionary(policy):
    """The descriptor cannot introduce names, units or types of its own."""

    schema = policy.catalog.schemas[FEATURE_SCHEMA_ID]
    assert set(schema["properties"]) == {item[0] for item in FEATURE_ORDER}
    assert tuple(schema["required"]) == tuple(
        item[0] for item in FEATURE_ORDER if item[3]
    )
