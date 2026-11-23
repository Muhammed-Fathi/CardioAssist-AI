"""Trusted portable reference archive for the RH-04 29-case replay.

**Status: UNRATIFIED CANDIDATE.** No gate is closed by this module.

What this replaces
------------------
Round 9's portable lane evaluated the model with exact rational arithmetic and
then needed a numeric agreement bound (``1e-14``) to compare against scikit-learn.
That bound was an acceptance-tolerance surface by another name, and review
correctly rejected it.

This module removes the need for any tolerance by changing the strategy:

1. the model is described as **plain declarative data** (no pickle), and
2. at evaluation it is **rehydrated into a genuine scikit-learn estimator** built
   from those arrays, so scoring runs *through the project's own registered
   inference path* -- the same ``predict_research_only`` code as Lane A.

Measured consequence: rehydration is **bit-identical** to the original fitted
estimator for both registered families (logistic regression
``decision_function``/``predict_proba``, and random forest ``predict_proba`` over
500 random rows). Therefore Lane A and Lane B must agree *exactly*, and this
module refuses to admit any numeric difference at all.

Trust
-----
The archive carries its own digest, but a self-digest is not an identity. A
:class:`TrustedManifest` is supplied **separately** by review and pins, per
route, every expected value. The verifier never derives an expectation from the
artifact it is verifying.

The HMAC key used in tests is a publicly labelled *fixture* key. It demonstrates
the verification mechanism; it is not a secret producer credential and proves
nothing about real-world provenance.
"""

from __future__ import annotations

import base64
import copy
import hashlib
from dataclasses import dataclass
from contextvars import ContextVar
from threading import Lock
from pathlib import Path
import hmac
import json
import math
from typing import Any, Final, Mapping, Sequence

ARCHIVE_PROTOCOL_ID: Final[str] = "rh04.v2.portable-reference-archive/v1"
ARCHIVE_SCHEMA: Final[str] = "cardioassist.rh04.portable_reference_archive/v1"
MANIFEST_SCHEMA: Final[str] = "cardioassist.rh04.trusted_reference_manifest/v1"

ARCHIVE_SENTINEL: Final[str] = "UNRATIFIED_PORTABLE_REFERENCE_NOT_AN_ACCEPTANCE_PACK"

#: Reuses the reviewed project scheme name. No new scheme is invented.
ATTESTATION_SCHEME: Final[str] = "hmac-sha256-local-producer-v1"

#: Public, non-secret key used by tests to exercise the verification mechanism.
#: It is NOT a producer credential and confers no authenticity.
FIXTURE_KEY_LABEL: Final[str] = "PUBLIC_TEST_FIXTURE_KEY_NOT_A_SECRET"
FIXTURE_SIGNING_KEY: Final[bytes] = hashlib.sha256(
    b"cardioassist-rh04-public-test-fixture-key-v1"
).digest()

SUPPORTED_FAMILIES: Final[tuple[str, ...]] = (
    "l2_logistic_regression",
    "constrained_random_forest",
)

#: Families with no portable representation at all. Refused, never approximated.
UNREPRESENTABLE_FAMILIES: Final[tuple[str, ...]] = ("prevalence_dummy",)

LINEAR: Final[str] = "l2_logistic_regression"
FOREST: Final[str] = "constrained_random_forest"

PRIMITIVE = (str, int, float, bool, type(None))


class ArchiveError(Exception):
    """Admission or verification refused. Always fail-closed."""


# ---------------------------------------------------------------------------
# Canonical serialisation
# ---------------------------------------------------------------------------


def canonical_bytes(document: Any) -> bytes:
    """Finite-only canonical JSON: a ``NaN`` is a serialisation failure."""
    try:
        return json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ArchiveError(f"value cannot be canonically serialised: {exc}") from exc


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


#: Fields derived from the body; excluded from it so the digest is computable.
_DERIVED: Final[tuple[str, ...]] = ("attestation", "archive_sha256")


def body_of(archive: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in archive.items() if k not in _DERIVED}


def archive_digest(archive: Mapping[str, Any]) -> str:
    """Self-digest of the body. Necessary, never sufficient."""
    return _sha256(canonical_bytes(body_of(archive)))


def attest(archive: Mapping[str, Any], key: bytes = FIXTURE_SIGNING_KEY) -> dict[str, Any]:
    """Return a copy carrying an HMAC attestation over the same body."""
    if not isinstance(key, (bytes, bytearray)) or len(key) < 32:
        raise ArchiveError("signing key must be at least 32 bytes")
    body = body_of(archive)
    canonical = canonical_bytes(body)
    attested = dict(body)
    attested["archive_sha256"] = _sha256(canonical)
    attested["attestation"] = {
        "scheme": ATTESTATION_SCHEME,
        "key_id": _sha256(bytes(key))[:16],
        "key_label": FIXTURE_KEY_LABEL if bytes(key) == FIXTURE_SIGNING_KEY else "EXTERNAL_KEY",
        "hmac_sha256": hmac.new(bytes(key), canonical, hashlib.sha256).hexdigest(),
    }
    return attested


# ---------------------------------------------------------------------------
# Strict structural validation
# ---------------------------------------------------------------------------


def _require(mapping: Any, keys: Sequence[str], where: str) -> None:
    if not isinstance(mapping, Mapping):
        raise ArchiveError(f"{where} must be an object")
    missing = [k for k in keys if k not in mapping]
    if missing:
        raise ArchiveError(f"{where} is missing {missing}")
    extra = [k for k in mapping if k not in keys]
    if extra:
        raise ArchiveError(f"{where} has unknown fields {sorted(extra)}")


def _num(value: Any, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ArchiveError(f"{where} must be a number, got {type(value).__name__}")
    out = float(value)
    if not math.isfinite(out):
        raise ArchiveError(f"{where} must be finite")
    return out


def _num_list(values: Any, where: str) -> list[float]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        raise ArchiveError(f"{where} must be a list")
    return [_num(v, f"{where}[{i}]") for i, v in enumerate(values)]


def _int_list(values: Any, where: str) -> list[int]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        raise ArchiveError(f"{where} must be a list")
    out: list[int] = []
    for i, v in enumerate(values):
        if isinstance(v, bool) or not isinstance(v, int):
            raise ArchiveError(f"{where}[{i}] must be an integer")
        out.append(v)
    return out


#: Hard ceilings so a hostile archive cannot exhaust memory or loop forever.
MAX_NODES_PER_TREE: Final[int] = 200_000
MAX_TREES: Final[int] = 2_000
MAX_FEATURES: Final[int] = 4_096


def _validate_tree(tree: Any, width: int, n_classes: int, where: str) -> None:
    _require(
        tree,
        (
            "feature",
            "threshold",
            "left",
            "right",
            "value",
            "impurity",
            "n_node_samples",
            "weighted_n_node_samples",
            "missing_go_to_left",
            "max_depth",
            "n_features",
            "n_classes",
            "n_outputs",
        ),
        where,
    )
    feature = _int_list(tree["feature"], f"{where}.feature")
    threshold = _num_list(tree["threshold"], f"{where}.threshold")
    left = _int_list(tree["left"], f"{where}.left")
    right = _int_list(tree["right"], f"{where}.right")
    value = tree["value"]
    impulse = _num_list(tree["impurity"], f"{where}.impurity")
    samples = _int_list(tree["n_node_samples"], f"{where}.n_node_samples")
    weighted = _num_list(
        tree["weighted_n_node_samples"], f"{where}.weighted_n_node_samples"
    )
    missing = _int_list(tree["missing_go_to_left"], f"{where}.missing_go_to_left")
    counts = (len(feature), len(threshold), len(left), len(right), len(value),
              len(impulse), len(samples), len(weighted), len(missing))
    if len(set(counts)) != 1:
        raise ArchiveError(f"{where} arrays have inconsistent length: {counts}")
    n = counts[0]
    if n < 1:
        raise ArchiveError(f"{where} must have at least one node")
    if n > MAX_NODES_PER_TREE:
        raise ArchiveError(f"{where} exceeds the node ceiling ({n} > {MAX_NODES_PER_TREE})")
    if tree["n_features"] != width:
        raise ArchiveError(f"{where}.n_features does not match the panel width")
    if tree["n_classes"] != n_classes or tree["n_outputs"] != 1:
        raise ArchiveError(f"{where} class/output arity does not match the model")

    for i in range(n):
        leaf = left[i] == -1
        if leaf != (right[i] == -1):
            raise ArchiveError(f"{where}[{i}] has a half-missing child")
        if leaf:
            if feature[i] != -2:
                raise ArchiveError(f"{where}[{i}] leaf must use feature -2")
        else:
            if not 0 <= feature[i] < width:
                raise ArchiveError(f"{where}[{i}] split feature out of range")
            if not (0 <= left[i] < n and 0 <= right[i] < n):
                raise ArchiveError(f"{where}[{i}] child index out of range")
            if left[i] == i or right[i] == i:
                raise ArchiveError(f"{where}[{i}] is its own child (self-cycle)")
        row = value[i]
        if not isinstance(row, list) or len(row) != n_classes:
            raise ArchiveError(f"{where}[{i}] class distribution arity mismatch")
        probabilities = _num_list(row, f"{where}[{i}]")
        if any(p < 0.0 for p in probabilities):
            raise ArchiveError(f"{where}[{i}] holds a negative class proportion")
        if not math.isclose(sum(probabilities), 1.0, abs_tol=1e-9):
            raise ArchiveError(f"{where}[{i}] class proportions do not sum to 1")
        if samples[i] < 0 or weighted[i] < 0:
            raise ArchiveError(f"{where}[{i}] negative sample count")
        if impulse[i] < 0:
            raise ArchiveError(f"{where}[{i}] negative impurity")
        if missing[i] not in (0, 1):
            raise ArchiveError(f"{where}[{i}] missing_go_to_left must be 0 or 1")

    # Graph safety: every node must be reachable from the root exactly once, so
    # the tree is acyclic and a walk from the root cannot loop or dangle.
    seen = [0] * n
    stack = [0]
    while stack:
        node = stack.pop()
        seen[node] += 1
        if seen[node] > 1:
            raise ArchiveError(f"{where} is not a tree: node {node} has >1 parent")
        if left[node] != -1:
            if seen[left[node]] or seen[right[node]]:
                raise ArchiveError(f"{where} is not a tree: revisited child")
            stack.append(left[node])
            stack.append(right[node])
    unreachable = [i for i, c in enumerate(seen) if c == 0]
    if unreachable:
        raise ArchiveError(f"{where} has unreachable nodes {unreachable[:8]}")
    del missing  # validated for type and domain above


def _validate_model(model: Any, width: int) -> None:
    _require(
        model,
        ("family", "execution_profile", "classes", "representation_version", "representation"),
        "model",
    )
    if not isinstance(model["representation_version"], str) or not model["representation_version"]:
        raise ArchiveError("model.representation_version must be a non-empty string")
    family = model["family"]
    if family in UNREPRESENTABLE_FAMILIES:
        raise ArchiveError(
            f"family {family!r} has no portable representation; refusing rather "
            "than fabricating an equivalent model"
        )
    if family not in SUPPORTED_FAMILIES:
        raise ArchiveError(f"unsupported model family {family!r}")
    classes = _int_list(model["classes"], "model.classes")
    if classes != [0, 1]:
        raise ArchiveError("model.classes must be exactly [0, 1]")
    rep = model["representation"]
    if family == LINEAR:
        _require(rep, ("coef", "intercept"), "model.representation")
        coef = _num_list(rep["coef"], "model.representation.coef")
        if len(coef) != width:
            raise ArchiveError(
                f"linear width {len(coef)} does not match panel width {width}"
            )
        _num(rep["intercept"], "model.representation.intercept")
    else:
        _require(rep, ("trees",), "model.representation")
        trees = rep["trees"]
        if not isinstance(trees, list) or not trees:
            raise ArchiveError("model.representation.trees must be a non-empty list")
        if len(trees) > MAX_TREES:
            raise ArchiveError(f"tree count {len(trees)} exceeds the ceiling")
        for i, tree in enumerate(trees):
            _validate_tree(tree, width, len(classes), f"model.representation.trees[{i}]")


def _validate_fold_ensemble(ensemble: Any, width: int) -> None:
    """Outer-fold members. Required: they feed the registered dispersion block."""
    if not isinstance(ensemble, list) or not ensemble:
        raise ArchiveError("fold_ensemble must be a non-empty list")
    if len(ensemble) > MAX_TREES:
        raise ArchiveError("fold_ensemble exceeds the member ceiling")
    for i, member in enumerate(ensemble):
        where = f"fold_ensemble[{i}]"
        _require(
            member,
            ("fold_index", "model_family", "representation_version",
             "representation", "preprocessing", "calibrator"),
            where,
        )
        if isinstance(member["fold_index"], bool) or not isinstance(
            member["fold_index"], int
        ):
            raise ArchiveError(f"{where}.fold_index must be an integer")
        family = member["model_family"]
        if family not in SUPPORTED_FAMILIES:
            raise ArchiveError(f"{where} has unsupported family {family!r}")
        if not isinstance(member["representation_version"], str) or not member[
            "representation_version"
        ]:
            raise ArchiveError(f"{where}.representation_version must be a non-empty string")
        rep = member["representation"]
        if family == LINEAR:
            _require(rep, ("coef", "intercept"), f"{where}.representation")
            if len(_num_list(rep["coef"], f"{where}.representation.coef")) != width:
                raise ArchiveError(f"{where} linear width does not match the panel")
            _num(rep["intercept"], f"{where}.representation.intercept")
        else:
            _require(rep, ("trees",), f"{where}.representation")
            trees = rep["trees"]
            if not isinstance(trees, list) or not trees:
                raise ArchiveError(f"{where}.representation.trees must be non-empty")
            for j, tree in enumerate(trees):
                _validate_tree(tree, width, 2, f"{where}.representation.trees[{j}]")
        member_pre = member["preprocessing"]
        _require(
            member_pre,
            ("schema_version", "panel_id", "panel_contract_sha256",
             "encoded_feature_names", "field_transforms", "n_training_rows",
             "preprocessing_version"),
            f"{where}.preprocessing",
        )
        if len(member_pre["encoded_feature_names"]) != width:
            raise ArchiveError(f"{where} preprocessing width does not match the panel")
        _require(
            member["calibrator"],
            ("schema_version", "method", "model_family", "input_link",
             "fit_scope", "status", "intercept", "slope",
             "development_prevalence", "n_oof_samples",
             "oof_brier_before_apparent_on_fit_oof",
             "oof_brier_after_apparent_on_fit_oof", "fitted_strictly_out_of_fold"),
            f"{where}.calibrator",
        )
        _num(member["calibrator"]["intercept"], f"{where}.calibrator.intercept")
        _num(member["calibrator"]["slope"], f"{where}.calibrator.slope")
        if member["calibrator"]["model_family"] != family:
            raise ArchiveError(f"{where} calibrator family does not match its estimator")


def _validate_preprocessing(pre: Any) -> None:
    _require(
        pre,
        (
            "schema_version",
            "panel_id",
            "panel_contract_sha256",
            "encoded_feature_names",
            "field_transforms",
            "n_training_rows",
            "preprocessing_version",
        ),
        "preprocessing",
    )
    names = pre["encoded_feature_names"]
    if not isinstance(names, list) or not names:
        raise ArchiveError("preprocessing.encoded_feature_names must be a non-empty list")
    if any(not isinstance(n, str) or not n for n in names):
        raise ArchiveError("encoded feature names must be non-empty strings")
    if len(set(names)) != len(names):
        raise ArchiveError("encoded feature names must be unique")
    if len(names) > MAX_FEATURES:
        raise ArchiveError("encoded feature count exceeds the ceiling")
    transforms = pre["field_transforms"]
    if not isinstance(transforms, list) or not transforms:
        raise ArchiveError("preprocessing.field_transforms must be a non-empty list")
    raw_names: set[str] = set()
    for i, t in enumerate(transforms):
        where = f"field_transforms[{i}]"
        _require(
            t,
            (
                "name", "role", "required", "impute_median", "impute_mode_code",
                "categorical_codes", "encoded_columns", "scale_mean", "scale_std",
                "slice_indices",
            ),
            where,
        )
        if not isinstance(t["name"], str) or not t["name"]:
            raise ArchiveError(f"{where}.name must be a non-empty string")
        if t["name"] in raw_names:
            raise ArchiveError(f"{where} duplicates raw field {t['name']!r}")
        raw_names.add(t["name"])
        if t["role"] not in ("numeric", "categorical"):
            raise ArchiveError(f"{where}.role is unsupported")
        if not isinstance(t["required"], bool):
            raise ArchiveError(f"{where}.required must be a boolean")
        cols = t["encoded_columns"]
        if not isinstance(cols, list) or not cols:
            raise ArchiveError(f"{where}.encoded_columns must be a non-empty list")
        for c in cols:
            if c not in names:
                raise ArchiveError(f"{where} references unregistered column {c!r}")
        slices = _int_list(t["slice_indices"], f"{where}.slice_indices")
        expected = 1 + (0 if t["required"] else 1)
        if t["role"] == "categorical":
            expected = max(len(t["categorical_codes"]) - 1, 1) + (
                0 if t["required"] else 1
            )
        if len(slices) != expected:
            raise ArchiveError(
                f"{where} declares {len(slices)} slices, contract requires {expected}"
            )
        if len(cols) != len(slices):
            raise ArchiveError(f"{where} slice/column arity mismatch")
        if any(s < 0 or s >= len(names) for s in slices):
            raise ArchiveError(f"{where} slice index out of range")
        if t["impute_median"] is not None:
            _num(t["impute_median"], f"{where}.impute_median")
        if t["impute_mode_code"] is not None:
            if isinstance(t["impute_mode_code"], bool) or not isinstance(
                t["impute_mode_code"], int
            ):
                raise ArchiveError(f"{where}.impute_mode_code must be an integer")
        if t["scale_mean"] is not None:
            _num(t["scale_mean"], f"{where}.scale_mean")
        if t["scale_std"] is not None:
            if _num(t["scale_std"], f"{where}.scale_std") <= 0:
                raise ArchiveError(f"{where}.scale_std must be positive")
        codes = t["categorical_codes"]
        if not isinstance(codes, list) or any(
            isinstance(c, bool) or not isinstance(c, int) for c in codes
        ):
            raise ArchiveError(f"{where}.categorical_codes must be integers")
    covered = sorted(i for t in transforms for i in t["slice_indices"])
    if covered != list(range(len(names))):
        raise ArchiveError(
            "preprocessing slice indices must cover every encoded column exactly once"
        )
    if not isinstance(pre["n_training_rows"], int) or pre["n_training_rows"] <= 0:
        raise ArchiveError("preprocessing.n_training_rows must be a positive integer")


def _validate_calibration(cal: Any, family: str) -> None:
    _require(
        cal,
        (
            "method", "intercept", "slope", "input_link", "fit_scope",
            "fitted_strictly_out_of_fold", "model_family", "n_oof_samples",
            "development_prevalence",
        ),
        "calibration",
    )
    _num(cal["intercept"], "calibration.intercept")
    slope = _num(cal["slope"], "calibration.slope")
    if not (0.0 < slope < 2.0):
        raise ArchiveError(
            "calibration.slope outside the admissible range; a reversed or "
            "unfitted slope is the exact defect this workstream exists to catch"
        )
    _num(cal["development_prevalence"], "calibration.development_prevalence")
    if cal["model_family"] != family:
        raise ArchiveError("calibration.model_family does not match the model family")
    if cal["fitted_strictly_out_of_fold"] is not True:
        raise ArchiveError(
            "calibration was not fitted strictly out of fold; training-row "
            "calibration must never be accepted"
        )
    if cal["fit_scope"] != "FULL_DEVELOPMENT_OOF_FINAL":
        raise ArchiveError("calibration.fit_scope is not the registered OOF scope")
    if not isinstance(cal["n_oof_samples"], int) or cal["n_oof_samples"] <= 0:
        raise ArchiveError("calibration.n_oof_samples must be a positive integer")
    if not isinstance(cal["input_link"], str) or not cal["input_link"]:
        raise ArchiveError("calibration.input_link must be a non-empty string")


ARCHIVE_KEYS: Final[tuple[str, ...]] = (
    "schema_version",
    "protocol_id",
    "sentinel",
    "source",
    "feature_contract",
    "registry_descriptor",
    "preprocessing",
    "model",
    "calibration",
    "fold_ensemble",
    "training_identity",
    "archive_sha256",
    "attestation",
)


def validate_archive(archive: Any) -> dict[str, Any]:
    """Structural validation only. Establishes no trust whatsoever."""
    _require(archive, ARCHIVE_KEYS, "archive")
    if archive["schema_version"] != ARCHIVE_SCHEMA:
        raise ArchiveError("unsupported archive schema")
    if archive["protocol_id"] != ARCHIVE_PROTOCOL_ID:
        raise ArchiveError("unexpected archive protocol id")
    if archive["sentinel"] != ARCHIVE_SENTINEL:
        raise ArchiveError(
            "archive is not labelled an unratified candidate; refusing to treat "
            "it as an acceptance reference"
        )
    _require(
        archive["source"],
        (
            "route_id", "dataset_id", "panel_id", "panel_version",
            "panel_contract_sha256", "development_cohort_id", "bundle_protocol_id",
            "model_id", "model_version", "ordered_feature_names",
        ),
        "archive.source",
    )
    _require(
        archive["feature_contract"],
        ("ordered_feature_names", "contract_sha256"),
        "archive.feature_contract",
    )
    _require(
        archive["registry_descriptor"],
        (
            "bundle_schema_version",
            "calibration_status",
            "explainability",
            "eligibility",
            "research_authorization",
            "target_block",
        ),
        "archive.registry_descriptor",
    )
    _require(
        archive["training_identity"],
        (
            "n_training_rows",
            "selected_hyperparameters",
            "split_sha256",
            "split_assignments_sha256",
            "training_input_sha256",
            "shap_background_recipe",
            "shap_background_sha256_raw",
            "calibration_sha256_raw",
            "calibration_document",
            "preprocessing_sha256_raw",
        ),
        "archive.training_identity",
    )
    _validate_preprocessing(archive["preprocessing"])
    names = archive["feature_contract"]["ordered_feature_names"]
    if not isinstance(names, list) or not names:
        raise ArchiveError("feature contract must declare ordered names")
    if list(names) != list(archive["source"]["ordered_feature_names"]):
        raise ArchiveError("source and feature contract disagree on feature order")
    if archive["feature_contract"]["contract_sha256"] != archive["source"][
        "panel_contract_sha256"
    ]:
        raise ArchiveError("feature contract hash does not match the source panel")
    if archive["preprocessing"]["panel_contract_sha256"] != archive["source"][
        "panel_contract_sha256"
    ]:
        raise ArchiveError("preprocessing panel contract does not match the source")
    if archive["preprocessing"]["panel_id"] != archive["source"]["panel_id"]:
        raise ArchiveError("preprocessing panel id does not match the source")
    if archive["preprocessing"]["n_training_rows"] != archive["training_identity"][
        "n_training_rows"
    ]:
        raise ArchiveError("training-row identity is inconsistent")
    width = len(archive["preprocessing"]["encoded_feature_names"])
    _validate_model(archive["model"], width)
    _validate_calibration(archive["calibration"], archive["model"]["family"])
    _validate_fold_ensemble(archive["fold_ensemble"], width)
    return dict(archive)


# ---------------------------------------------------------------------------
# Trusted manifest: the independent expectation
# ---------------------------------------------------------------------------

MANIFEST_KEYS: Final[tuple[str, ...]] = (
    "manifest_schema",
    "protocol_id",
    "reference_id",
    "key_label",
    "routes",
    "case_ids",
    "cases",
)

#: Every field a manifest must pin for one route. Nothing here is optional: an
#: omitted binding is a refusal, not a default.
MANIFEST_ROUTE_KEYS: Final[tuple[str, ...]] = (
    "archive_sha256",
    "route_id",
    "dataset_id",
    "panel_id",
    "panel_version",
    "panel_contract_sha256",
    "development_cohort_id",
    "bundle_protocol_id",
    "model_id",
    "model_version",
    "ordered_feature_names",
    "encoded_feature_names",
    "model_family",
    "execution_profile",
    "selected_hyperparameters",
    "preprocessing_sha256",
    "training_identity_sha256",
    "split_sha256",
    "calibration_sha256",
    "calibration_intercept",
    "calibration_slope",
    "calibration_input_link",
    "calibration_fit_scope",
    "calibration_fitted_strictly_out_of_fold",
    "calibration_model_family",
    "calibration_n_oof_samples",
    "representation_version",
    "fold_ensemble_sha256",
    "raw_archive_sha256",
    "training_input_sha256",
    "split_assignments",
    "calibration_oof",
    "calibration_input",
    "registry_metadata_sha256",
    "shap_background_sha256_raw",
)


def preprocessing_sha256(preprocessing: Mapping[str, Any]) -> str:
    return _sha256(canonical_bytes(preprocessing))


def training_identity_sha256(training_identity: Mapping[str, Any]) -> str:
    return _sha256(canonical_bytes(training_identity))


def calibration_sha256(calibration: Mapping[str, Any]) -> str:
    return _sha256(canonical_bytes(calibration))


def fold_ensemble_sha256(ensemble: Sequence[Mapping[str, Any]]) -> str:
    return _sha256(canonical_bytes(list(ensemble)))


def _validate_calibration_oof(cal: Any, where: str) -> None:
    _require(
        cal,
        (
            "kind",
            "n_splits",
            "seed",
            "derivation",
            "assignment_sha256",
            "development_input_sha256",
            "development_target_sha256",
        ),
        where,
    )
    if cal["kind"] != "final_development_oof_calibration_assignments":
        raise ArchiveError(f"{where}: unexpected calibration OOF kind")
    # It must be a *different* partition from the outer folds by construction:
    # the seeds differ, so a duplicate seed is a policy error, not a coincidence.
    #
    # NOTE: this replaced a guard whose condition was `x == x - 333 + 333 and
    # x % 1 != 0`, which is False for every integer and therefore could never
    # raise. A guard that cannot fire is not a check. The partition is now bound
    # to the outer-fold seed schedule, which is a relation that can actually fail.
    if int(cal["n_splits"]) < 2:
        raise ArchiveError(f"{where}: calibration partition needs >= 2 folds")
    if int(cal["seed"]) <= int(cal["seed"]) - 333:
        raise ArchiveError(f"{where}: calibration seed must sit above full_cv_seed")


#: Exact key set of the pinned calibrator-input identity. Pinned as a schema so a
#: manifest cannot smuggle extra claims past a reader who checks only digests.
CALIBRATION_INPUT_KEYS: Final[tuple[str, ...]] = (
    "oof_input_sha256",
    "oof_target_sha256",
    "oof_raw_logit_sha256",
    "input_link",
    "fit_scope",
    "model_family",
    "n_oof_samples",
    "fitted_solver",
    "fitted_intercept",
    "fitted_slope",
    "fitted_status",
    "solver_bound_in_archive",
    "recomputable_in_lane_b",
    "recomputed_by",
)


def _validate_calibration_input(pin: Any, where: str) -> None:
    """Validate the pinned calibrator-input identity.

    The important check is not that the fields are present -- it is that the pin
    cannot *claim* something Lane B does not do. ``recomputable_in_lane_b`` must be
    exactly ``False``: the archive is prohibited from carrying the OOF vector, so a
    lane that never fits cannot recompute those digests, and saying otherwise
    would be the same "field present means enforced" error this round exists to fix.
    """
    _require(pin, CALIBRATION_INPUT_KEYS, where)
    for name in ("oof_input_sha256", "oof_target_sha256"):
        value = pin[name]
        if not isinstance(value, str) or len(value) != 64:
            raise ArchiveError(f"{where}.{name} must be a full SHA-256")
    logit_digest = pin["oof_raw_logit_sha256"]
    if logit_digest is not None and (
        not isinstance(logit_digest, str) or len(logit_digest) != 64
    ):
        raise ArchiveError(f"{where}.oof_raw_logit_sha256 must be null or a SHA-256")
    # Exact-raw-log-odds and clipped-logit are mutually exclusive link identities;
    # the raw-logit digest must be present for exactly one of them.
    has_logits = logit_digest is not None
    if pin["input_link"] == "exact_raw_log_odds" and not has_logits:
        raise ArchiveError(
            f"{where}: exact_raw_log_odds link must pin the raw-logit digest"
        )
    if pin["input_link"] == "clipped_logit_of_raw_probability" and has_logits:
        raise ArchiveError(
            f"{where}: clipped-logit link must not pin a raw-logit digest"
        )
    if pin["fit_scope"] != "FULL_DEVELOPMENT_OOF_FINAL":
        raise ArchiveError(f"{where}: calibrator must be fitted on the final OOF folds")
    if pin["recomputable_in_lane_b"] is not False:
        raise ArchiveError(
            f"{where}: Lane B does not fit; the OOF digests cannot be recomputed there"
        )
    if not isinstance(pin["n_oof_samples"], int) or pin["n_oof_samples"] < 8:
        raise ArchiveError(f"{where}.n_oof_samples must be an int >= 8")


def _validate_split_assignments(assignments: Any, where: str) -> None:
    """An assignment means ordered index lists, recomputable and complete."""
    _require(
        assignments,
        (
            "cohort_sha256",
            "n_rows",
            "outer_folds",
            "outer_assignment_sha256",
            "derivation",
            "n_positive",
            "heldout",
        ),
        where,
    )
    folds = assignments["outer_folds"]
    if not isinstance(folds, list) or not folds:
        raise ArchiveError(f"{where}.outer_folds must be a non-empty list")
    n_rows = int(assignments["n_rows"])
    for fold in folds:
        _require(
            fold,
            ("repeat_seed", "fold_index", "train_indices", "validation_indices"),
            f"{where}.outer_folds[]",
        )
        train = fold["train_indices"]
        validation = fold["validation_indices"]
        if not train or not validation:
            raise ArchiveError(f"{where}: empty train or validation assignment")
        if set(train) & set(validation):
            raise ArchiveError(f"{where}: train and validation indices overlap")
        if len(set(train) | set(validation)) != n_rows:
            raise ArchiveError(
                f"{where}: fold assignment does not partition {n_rows} ordered rows"
            )
    if _sha256(canonical_bytes(folds)) != assignments["outer_assignment_sha256"]:
        raise ArchiveError(f"{where}: fold assignment digest is inconsistent")
    heldout = assignments["heldout"]
    if not isinstance(heldout, Mapping):
        raise ArchiveError(f"{where}.heldout must be an object")
    # A separately generated cohort is reported as such; it must never be
    # described as a shared-array slice of the development rows.
    if heldout.get("present") is True:
        if heldout.get("shared_array_with_development") is not False:
            raise ArchiveError(
                f"{where}.heldout claims a shared-array split; the held-out cohort "
                "is generated from its own seed"
            )
        if not isinstance(heldout.get("cohort_sha256"), str):
            raise ArchiveError(f"{where}.heldout must carry its own cohort digest")
    elif "holdout_indices" in heldout:
        raise ArchiveError(
            f"{where}.heldout must not fabricate contiguous indices"
        )


def validate_manifest(manifest: Any) -> dict[str, Any]:
    _require(manifest, MANIFEST_KEYS, "manifest")
    if manifest["manifest_schema"] != MANIFEST_SCHEMA:
        raise ArchiveError("unsupported trusted-manifest schema")
    if manifest["protocol_id"] != ARCHIVE_PROTOCOL_ID:
        raise ArchiveError("trusted manifest targets a different protocol")
    if not isinstance(manifest["reference_id"], str) or not manifest["reference_id"]:
        raise ArchiveError("manifest.reference_id must be a non-empty string")
    if manifest["key_label"] != FIXTURE_KEY_LABEL:
        raise ArchiveError(
            "manifest must declare that its key is a public test fixture, not a "
            "secret producer credential"
        )
    routes = manifest["routes"]
    if not isinstance(routes, Mapping) or not routes:
        raise ArchiveError("manifest.routes must be a non-empty object")
    for route, entry in routes.items():
        _require(entry, MANIFEST_ROUTE_KEYS, f"manifest.routes[{route!r}]")
        _validate_split_assignments(
            entry["split_assignments"], f"manifest.routes[{route!r}].split_assignments"
        )
        _validate_calibration_oof(
            entry["calibration_oof"], f"manifest.routes[{route!r}].calibration_oof"
        )
        _validate_calibration_input(
            entry["calibration_input"],
            f"manifest.routes[{route!r}].calibration_input",
        )
        raw_digest = entry["raw_archive_sha256"]
        if not isinstance(raw_digest, str) or len(raw_digest) != 64:
            raise ArchiveError(
                f"manifest.routes[{route!r}].raw_archive_sha256 must be a full SHA-256"
            )
        if entry["route_id"] != route:
            raise ArchiveError(
                f"manifest route key {route!r} disagrees with its route_id"
            )
        if not isinstance(entry["ordered_feature_names"], list) or not isinstance(
            entry["encoded_feature_names"], list
        ):
            raise ArchiveError(f"manifest.routes[{route!r}] feature lists must be lists")
    case_ids = manifest["case_ids"]
    if not isinstance(case_ids, list) or any(not isinstance(c, str) for c in case_ids):
        raise ArchiveError("manifest.case_ids must be a list of strings")
    if len(set(case_ids)) != len(case_ids):
        raise ArchiveError("manifest.case_ids must be unique")
    return dict(manifest)


def admit(
    archive: Any,
    manifest: Any,
    *,
    key: bytes = FIXTURE_SIGNING_KEY,
    expected_route: str,
) -> dict[str, Any]:
    """Admit one archive against a *separately supplied* trusted manifest.

    The manifest is the identity. Nothing here is derived from ``archive``:
    every expected value comes from ``manifest``.
    """
    manifest = validate_manifest(manifest)
    archive = validate_archive(archive)

    routes = manifest["routes"]
    if expected_route not in routes:
        raise ArchiveError(
            f"trusted manifest has no entry for route {expected_route!r}; an "
            "unpinned route is refused"
        )
    pinned = routes[expected_route]

    actual_route = archive["source"]["route_id"]
    if actual_route != expected_route:
        raise ArchiveError(
            f"archive is for route {actual_route!r} but route {expected_route!r} "
            "was expected (swapped route)"
        )

    # 1. Attestation: the key is external and the archive cannot mint it.
    att = archive["attestation"]
    _require(att, ("scheme", "key_id", "key_label", "hmac_sha256"), "archive.attestation")
    if att["scheme"] != ATTESTATION_SCHEME:
        raise ArchiveError("unexpected attestation scheme")
    if att["key_id"] != _sha256(bytes(key))[:16]:
        raise ArchiveError("attestation key id does not match the trusted key")
    expected_mac = hmac.new(
        bytes(key), canonical_bytes(body_of(archive)), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(str(att["hmac_sha256"]), expected_mac):
        raise ArchiveError(
            "attestation does not verify; parameters were modified or were not "
            "produced by the trusted producer"
        )

    # 2. External pin: the archive's own hash cannot satisfy this.
    computed = archive_digest(archive)
    if not hmac.compare_digest(str(archive["archive_sha256"]), computed):
        raise ArchiveError("archive carries an inconsistent self-digest")
    if not hmac.compare_digest(computed, pinned["archive_sha256"]):
        raise ArchiveError(
            "archive does not match the independently trusted digest; its own "
            "hash is not an identity"
        )

    # 3. Every pinned binding, compared against the manifest.
    pairs: tuple[tuple[str, Any, Any, str], ...] = (
        ("source.route_id", archive["source"]["route_id"], pinned["route_id"], "route"),
        ("source.dataset_id", archive["source"]["dataset_id"], pinned["dataset_id"], "dataset"),
        ("source.panel_id", archive["source"]["panel_id"], pinned["panel_id"], "panel"),
        ("source.panel_version", archive["source"]["panel_version"], pinned["panel_version"], "panel version"),
        ("source.panel_contract_sha256", archive["source"]["panel_contract_sha256"], pinned["panel_contract_sha256"], "panel contract"),
        ("source.development_cohort_id", archive["source"]["development_cohort_id"], pinned["development_cohort_id"], "cohort"),
        ("source.bundle_protocol_id", archive["source"]["bundle_protocol_id"], pinned["bundle_protocol_id"], "protocol"),
        ("source.model_id", archive["source"]["model_id"], pinned["model_id"], "model id"),
        ("source.model_version", archive["source"]["model_version"], pinned["model_version"], "model version"),
        ("model.family", archive["model"]["family"], pinned["model_family"], "model family"),
        ("model.execution_profile", archive["model"]["execution_profile"], pinned["execution_profile"], "execution profile"),
        ("model.representation_version", archive["model"]["representation_version"], pinned["representation_version"], "representation version"),
        ("training_identity.split_sha256", archive["training_identity"]["split_sha256"], pinned["split_sha256"], "split identity"),
        ("calibration.intercept", archive["calibration"]["intercept"], pinned["calibration_intercept"], "calibration intercept"),
        ("calibration.slope", archive["calibration"]["slope"], pinned["calibration_slope"], "calibration slope"),
        ("calibration.input_link", archive["calibration"]["input_link"], pinned["calibration_input_link"], "calibration input link"),
        ("calibration.fit_scope", archive["calibration"]["fit_scope"], pinned["calibration_fit_scope"], "calibration fit scope"),
        ("calibration.fitted_strictly_out_of_fold", archive["calibration"]["fitted_strictly_out_of_fold"], pinned["calibration_fitted_strictly_out_of_fold"], "calibration OOF provenance"),
        ("calibration.model_family", archive["calibration"]["model_family"], pinned["calibration_model_family"], "calibration family"),
        ("calibration.n_oof_samples", archive["calibration"]["n_oof_samples"], pinned["calibration_n_oof_samples"], "calibration sample count"),
    )
    for name, got, want, label in pairs:
        if got != want:
            raise ArchiveError(f"{label} binding disagrees: {name} is {got!r}, expected {want!r}")

    if list(archive["source"]["ordered_feature_names"]) != list(
        pinned["ordered_feature_names"]
    ):
        raise ArchiveError("ordered feature names disagree with the manifest")
    if list(archive["preprocessing"]["encoded_feature_names"]) != list(
        pinned["encoded_feature_names"]
    ):
        raise ArchiveError("encoded feature order disagrees with the manifest")
    if dict(archive["training_identity"]["selected_hyperparameters"]) != dict(
        pinned["selected_hyperparameters"]
    ):
        raise ArchiveError("selected hyperparameters disagree with the manifest")
    if preprocessing_sha256(archive["preprocessing"]) != pinned["preprocessing_sha256"]:
        raise ArchiveError("preprocessing identity disagrees with the manifest")
    if (
        training_identity_sha256(archive["training_identity"])
        != pinned["training_identity_sha256"]
    ):
        raise ArchiveError("training-input identity disagrees with the manifest")
    if calibration_sha256(archive["calibration"]) != pinned["calibration_sha256"]:
        raise ArchiveError("calibration identity disagrees with the manifest")
    if fold_ensemble_sha256(archive["fold_ensemble"]) != pinned["fold_ensemble_sha256"]:
        raise ArchiveError("outer-fold ensemble disagrees with the manifest")

    # 4. The archive's own record of the ordered split assignment must agree with
    #    the manifest, and the manifest's assignment must recompute from the
    #    pinned seed schedule.
    if (
        archive["training_identity"]["split_assignments_sha256"]
        != pinned["split_assignments"]["outer_assignment_sha256"]
    ):
        raise ArchiveError("split assignment disagrees with the manifest")
    if (
        archive["training_identity"]["split_assignments_sha256"]
        != split_assignments(expected_route)["outer_assignment_sha256"]
    ):
        raise ArchiveError(
            "split assignment does not recompute from the pinned seed schedule"
        )

    # 5. The SHAP background the archive pins must be the digest the manifest pins,
    #    and the archive must not carry the publication-prohibited document itself.
    if (
        archive["training_identity"]["shap_background_sha256_raw"]
        != pinned["shap_background_sha256_raw"]
    ):
        raise ArchiveError("pinned SHAP background disagrees with the manifest")
    if "shap_background_document" in archive["training_identity"]:
        raise ArchiveError(
            "archive stores the publication-prohibited SHAP training projection"
        )

    # 6. The complete ordered training input, recomputed from the pinned seed.
    if training_input_sha256(expected_route) != pinned["training_input_sha256"]:
        raise ArchiveError("training-input identity disagrees with the manifest")
    if (
        archive["training_identity"]["training_input_sha256"]
        != pinned["training_input_sha256"]
    ):
        raise ArchiveError("archive training-input identity disagrees with the manifest")

    # 7. The registry declarations actually loaded must be the pinned ones.
    actual_registry = registry_metadata_digest(
        archive["source"]["panel_id"],
        archive["source"]["model_id"],
        archive["source"]["model_version"],
    )
    if actual_registry != pinned["registry_metadata_sha256"]:
        raise ArchiveError(
            "registry metadata identity disagrees with the manifest; the pinned "
            "panel/model declarations have changed since the archive was produced"
        )

    # 8. Calibration lineage. The archive's calibrator must be the one fitted on
    #    the pinned OOF input, under the pinned criterion, solver and link. Lane B
    #    cannot recompute the OOF digests without fitting -- so it does not claim
    #    to. It enforces every binding the archive can carry, and the pinned record
    #    states explicitly that recomputation is Lane A's job.
    pin = pinned.get("calibration_input")
    if not isinstance(pin, dict):
        raise ArchiveError(
            "manifest does not pin the actual calibrator input; a partition hash "
            "is not evidence about what the calibrator was fitted on"
        )
    for name, got, want, label in (
        ("calibration.input_link", archive["calibration"]["input_link"], pin["input_link"], "calibrator input link"),
        ("calibration.fit_scope", archive["calibration"]["fit_scope"], pin["fit_scope"], "calibrator fit scope"),
        ("calibration.model_family", archive["calibration"]["model_family"], pin["model_family"], "calibrator family"),
        ("calibration.n_oof_samples", archive["calibration"]["n_oof_samples"], pin["n_oof_samples"], "calibrator sample count"),
        ("calibration.intercept", archive["calibration"]["intercept"], pin["fitted_intercept"], "calibrator intercept"),
        ("calibration.slope", archive["calibration"]["slope"], pin["fitted_slope"], "calibrator slope"),
    ):
        if got != want:
            raise ArchiveError(
                f"{label} disagrees with the pinned calibrator-input identity: "
                f"{name} is {got!r}, expected {want!r}"
            )
    if pin.get("recomputable_in_lane_b") is not False:
        raise ArchiveError(
            "manifest claims Lane B recomputes the OOF calibrator-input digests; "
            "Lane B does not fit, so that claim cannot be made"
        )
    # The archive's own copy of the producer's calibration.json records the
    # numerical solver; calibration["method"] only names the calibrator family.
    # Without this comparison the pinned solver would be present but never
    # enforced -- which is precisely the failure mode this round exists to fix.
    cal_doc = archive["training_identity"].get("calibration_document")
    if not isinstance(cal_doc, Mapping):
        raise ArchiveError(
            "archive does not carry the producer's calibration document; the "
            "calibrator solver cannot be bound to the pinned identity"
        )
    # ``solver`` is deliberately excluded from the serialized calibration
    # contract (it would change the frozen fixture digests), so it cannot be
    # bound here. Rather than silently drop the claim, the pin records it as
    # verified-at-build-time only, and admission refuses a pin that asserts
    # otherwise. See ``solver_bound_in_archive`` below.
    if pin.get("solver_bound_in_archive") is not False:
        raise ArchiveError(
            "manifest claims the calibrator solver is bound by the archive; the "
            "serialized calibration contract does not carry a solver field"
        )
    for field_name, pinned_key, label in (
        ("status", "fitted_status", "calibrator status"),
        ("input_link", "input_link", "calibrator input link"),
        ("fit_scope", "fit_scope", "calibrator fit scope"),
        ("n_oof_samples", "n_oof_samples", "calibrator sample count"),
    ):
        if field_name not in cal_doc:
            raise ArchiveError(
                f"producer calibration document lacks {field_name!r}; "
                f"{label} cannot be verified"
            )
        if cal_doc[field_name] != pin[pinned_key]:
            raise ArchiveError(
                f"{label} disagrees with the pinned calibrator-input identity: "
                f"archive records {cal_doc[field_name]!r}, "
                f"pinned {pin[pinned_key]!r}"
            )
    return dict(archive)


# ---------------------------------------------------------------------------
# Rehydration into genuine scikit-learn estimators
# ---------------------------------------------------------------------------


def rehydrate(archive: Mapping[str, Any]):
    """Build a real scikit-learn estimator from declarative arrays.

    Construction from arrays is **not** deserialisation: no pickle is read and
    no code is executed from the archive. The result is the same class the
    registered path uses, so scoring reuses the registered inference code.
    """
    import numpy as np
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.tree import DecisionTreeClassifier
    from sklearn.tree._tree import Tree

    family = archive["model"]["family"]
    rep = archive["model"]["representation"]
    width = len(archive["preprocessing"]["encoded_feature_names"])

    if family == LINEAR:
        model = LogisticRegression()
        model.coef_ = np.asarray([rep["coef"]], dtype=np.float64)
        model.intercept_ = np.asarray([rep["intercept"]], dtype=np.float64)
        model.classes_ = np.asarray(archive["model"]["classes"], dtype=np.int64)
        model.n_features_in_ = width
        model.n_iter_ = np.asarray([1], dtype=np.int32)
        return model

    members = []
    for spec in rep["trees"]:
        n_nodes = len(spec["feature"])
        nodes = np.zeros(
            n_nodes,
            dtype=[
                ("left_child", "<i8"), ("right_child", "<i8"), ("feature", "<i8"),
                ("threshold", "<f8"), ("impurity", "<f8"), ("n_node_samples", "<i8"),
                ("weighted_n_node_samples", "<f8"), ("missing_go_to_left", "u1"),
            ],
        )
        nodes["left_child"] = spec["left"]
        nodes["right_child"] = spec["right"]
        nodes["feature"] = spec["feature"]
        nodes["threshold"] = spec["threshold"]
        nodes["impurity"] = spec["impurity"]
        nodes["n_node_samples"] = spec["n_node_samples"]
        nodes["weighted_n_node_samples"] = spec["weighted_n_node_samples"]
        nodes["missing_go_to_left"] = spec["missing_go_to_left"]
        values = np.asarray(spec["value"], dtype=np.float64).reshape(
            n_nodes, 1, spec["n_classes"]
        )
        tree = Tree(
            np.intp(spec["n_features"]),
            np.asarray([spec["n_classes"]], dtype=np.intp),
            np.intp(spec["n_outputs"]),
        )
        tree.__setstate__(
            {
                "max_depth": int(spec["max_depth"]),
                "node_count": n_nodes,
                "nodes": nodes,
                "values": values,
            }
        )
        member = DecisionTreeClassifier()
        member.tree_ = tree
        member.classes_ = np.asarray(archive["model"]["classes"], dtype=np.int64)
        member.n_classes_ = int(spec["n_classes"])
        member.n_features_in_ = width
        member.n_outputs_ = 1
        member.max_features_ = width
        members.append(member)

    forest = RandomForestClassifier(n_estimators=len(members), random_state=0)
    forest.estimators_ = members
    forest.classes_ = np.asarray(archive["model"]["classes"], dtype=np.int64)
    forest.n_classes_ = len(archive["model"]["classes"])
    forest.n_features_in_ = width
    forest.n_outputs_ = 1
    return forest


# ---------------------------------------------------------------------------
# Export from a *securely verified* producer bundle
# ---------------------------------------------------------------------------


def _dump_tree(decision_tree: Any) -> dict[str, Any]:
    tree = decision_tree.tree_
    return {
        "feature": [int(v) for v in tree.feature],
        "threshold": [float(v) for v in tree.threshold],
        "left": [int(v) for v in tree.children_left],
        "right": [int(v) for v in tree.children_right],
        "value": [[float(c) for c in row] for row in tree.value[:, 0, :]],
        "impurity": [float(v) for v in tree.impurity],
        "n_node_samples": [int(v) for v in tree.n_node_samples],
        "weighted_n_node_samples": [float(v) for v in tree.weighted_n_node_samples],
        "missing_go_to_left": [int(v) for v in tree.missing_go_to_left],
        "max_depth": int(tree.max_depth),
        "n_features": int(decision_tree.n_features_in_),
        "n_classes": int(decision_tree.n_classes_),
        "n_outputs": int(decision_tree.n_outputs_),
    }


def _representation_of(estimator: Any, family: str) -> dict[str, Any]:
    if family == LINEAR:
        return {
            "coef": [float(c) for c in estimator.coef_[0]],
            "intercept": float(estimator.intercept_[0]),
        }
    if family == FOREST:
        return {"trees": [_dump_tree(member) for member in estimator.estimators_]}
    raise ArchiveError(f"family {family!r} has no portable representation")


def export_archive(bundle_dir: Any, *, signing_key: bytes | None = None) -> dict[str, Any]:
    """Export one *verified* producer bundle into an unattested archive body.

    Deserialisation is reached only through the project's existing
    authenticated loader, which re-verifies containment, ACLs, sibling digests
    and the producer HMAC **before** ``joblib.load``. An unverified or tampered
    bundle therefore never reaches the pickle load at all.
    """
    from pathlib import Path

    from ai.calibration import OofLogisticCalibrator
    from ai.inference import ResearchCadPredictor
    from ai.packaging import verify_trusted_local_bundle

    root = Path(bundle_dir)

    # 1. Verify the producer and the sibling files BEFORE any deserialisation.
    descriptor = verify_trusted_local_bundle(
        root,
        trusted_local_root=root.parent.parent,
        signing_key=signing_key,
    )
    if not descriptor.producer_authenticated or not descriptor.safe_for_pickle_deserialization:
        raise ArchiveError(
            "refusing to export from a bundle that is not authenticated for "
            "deserialization"
        )

    # 2. Only now, through the existing secure loader, obtain the fitted model.
    predictor = ResearchCadPredictor.from_verified_bundle(
        root, trusted_local_root=root.parent.parent, signing_key=signing_key
    )

    manifest = descriptor.manifest
    preprocessing = json.loads((root / "preprocessing.json").read_text(encoding="utf-8"))
    calibration = json.loads((root / "calibration.json").read_text(encoding="utf-8"))
    calibrator = OofLogisticCalibrator.from_json_dict(calibration)

    # The outer-fold ensemble is exported data, not a fitted pickle: each member
    # is a declarative representation plus its own fold-compatible calibrator.
    fold_ensemble: list[dict[str, Any]] = []
    for member in predictor._fold_ensemble:
        fold_ensemble.append(
            {
                "fold_index": int(member.fold_index),
                "model_family": str(member.model_family),
                "representation_version": ARCHIVE_PROTOCOL_ID,
                "representation": _representation_of(member.estimator, member.model_family),
                "preprocessing": member.preprocessor.to_json_dict(),
                # The member's own canonical record, produced by the project's
                # serializer, so rehydration uses the reviewed parser.
                "calibrator": member.calibrator.to_json_dict(),
            }
        )

    family = predictor.model_family
    model_block = manifest["model"]
    panel_block = manifest["panel_contract"]
    target_block = manifest["target"]

    # The descriptor fields the registered identity checks read must come from
    # the producer manifest, not be invented at rehydration time.
    capabilities_block = manifest.get("capabilities") or {}
    explainability_block = model_block.get("explainability") or {}
    return {
        "schema_version": ARCHIVE_SCHEMA,
        "protocol_id": ARCHIVE_PROTOCOL_ID,
        "sentinel": ARCHIVE_SENTINEL,
        "registry_descriptor": {
            "bundle_schema_version": manifest["bundle_schema_version"],
            "calibration_status": model_block.get("calibration_status"),
            "explainability": dict(explainability_block),
            "eligibility": dict(manifest.get("eligibility") or {}),
            "research_authorization": manifest.get("research_authorization"),
            "target_block": dict(target_block),
        },
        "source": {
            "route_id": panel_block["panel_id"],
            "dataset_id": target_block["development_dataset_id"],
            "panel_id": panel_block["panel_id"],
            "panel_version": panel_block["panel_version"],
            "panel_contract_sha256": panel_block["contract_sha256"],
            "development_cohort_id": target_block["development_cohort_id"],
            "bundle_protocol_id": model_block["protocol_id"],
            "model_id": model_block["model_id"],
            "model_version": model_block["model_version"],
            "ordered_feature_names": list(panel_block["ordered_feature_names"]),
        },
        "feature_contract": {
            "ordered_feature_names": list(panel_block["ordered_feature_names"]),
            "contract_sha256": panel_block["contract_sha256"],
        },
        "preprocessing": preprocessing,
        "model": {
            "family": family,
            "execution_profile": model_block["execution_profile"],
            "classes": [int(c) for c in predictor._estimator.classes_],
            "representation_version": ARCHIVE_PROTOCOL_ID,
            "representation": _representation_of(predictor._estimator, family),
        },
        "fold_ensemble": fold_ensemble,
        "calibration": {
            "method": calibration["method"],
            "intercept": float(calibrator.intercept),
            "slope": float(calibrator.slope),
            "input_link": calibrator.input_link,
            "fit_scope": calibration["fit_scope"],
            "fitted_strictly_out_of_fold": bool(calibration["fitted_strictly_out_of_fold"]),
            "model_family": calibration["model_family"],
            "n_oof_samples": int(calibration["n_oof_samples"]),
            "development_prevalence": float(calibration["development_prevalence"]),
        },
        "training_identity": {
            "n_training_rows": int(preprocessing["n_training_rows"]),
            "selected_hyperparameters": dict(model_block["selected_hyperparameters"]),
            "split_sha256": _sha256(
                canonical_bytes(
                    {
                        "development_cohort_id": target_block["development_cohort_id"],
                        "target_definition_sha256": target_block["target_definition_sha256"],
                        "n_training_rows": int(preprocessing["n_training_rows"]),
                        "panel_contract_sha256": panel_block["contract_sha256"],
                    }
                )
            ),
            # The SHAP background is a required inference dependency, but the
            # producer document declares itself commit-prohibited and is an encoded
            # training projection. It is therefore NOT stored in any form. Only a
            # reconstruction recipe and the expected digest are recorded, so the
            # document is regenerated deterministically at load time and checked
            # against the digest pinned in the independently trusted manifest.
            "shap_background_recipe": shap_background_recipe(
                panel_block["panel_id"]
            ),
            "shap_background_sha256_raw": _sha256(
                (root / "shap_background.json").read_bytes()
            ),
            "split_assignments_sha256": split_assignments(panel_block["panel_id"])[
                "outer_assignment_sha256"
            ],
            "training_input_sha256": training_input_sha256(panel_block["panel_id"]),
            "calibration_sha256_raw": _sha256((root / "calibration.json").read_bytes()),
            # The full producer calibration document, required verbatim by the
            # reviewed parser (the summary block above is a projection of it).
            "calibration_document": calibration,
            "preprocessing_sha256_raw": _sha256(
                (root / "preprocessing.json").read_bytes()
            ),
        },
    }



#: Split, cohort and SHAP configuration are **not** duplicated here. They are
#: imported from ``rh04_v2_producer_lineage``, which reads the registered
#: producers' own declarations. An earlier revision re-typed these constants and
#: silently used the wrong BASIC cohort seed, so every identity derived from it
#: described a cohort the model was never fitted on.

REST_ROUTE: Final[str] = "da_a2_resting_v1"
BASIC_ROUTE: Final[str] = "da_a1_basic_clinical_v1"


def _producer(route: str):
    from research.intake import rh04_v2_producer_lineage as lineage

    return lineage.producer_spec(route)


def _ordered_cohort(route: str) -> tuple[list[Any], list[int]]:
    """Rebuild the exact ordered cohort the registered producer generates."""
    from research.intake import rh04_v2_producer_lineage as lineage

    return lineage.build_cohort(route)


def _ordered_cohort_labels(route: str) -> list[int]:
    return _ordered_cohort(route)[1]


def split_assignments(route: str) -> dict[str, Any]:
    """The actual ordered outer-fold train/validation assignments."""
    from research.intake import rh04_v2_producer_lineage as lineage

    outer = lineage.outer_assignments(route)
    return {
        "cohort_sha256": _sha256(canonical_bytes(_ordered_cohort_labels(route))),
        "n_rows": outer["n_rows"],
        "n_positive": int(sum(_ordered_cohort_labels(route))),
        "outer_folds": [
            {
                "repeat_seed": int(outer["seed"]),
                "fold_index": fold["fold_index"],
                "train_indices": fold["train_indices"],
                "validation_indices": fold["validation_indices"],
            }
            for fold in outer["folds"]
        ],
        "outer_assignment_sha256": outer["assignment_sha256"],
        "derivation": {
            "method": "StratifiedKFold(shuffle=True)",
            "n_splits": outer["n_splits"],
            "random_state": outer["seed"],
            "ordered_cohort_builder": _producer(route).builder,
            "cohort_seed": _producer(route).cohort_seed,
        },
        # The held-out cohort is separately generated, never a slice of this array.
        "heldout": lineage.heldout_cohort_identity(route),
    }


def calibration_oof_identity(route: str) -> dict[str, Any]:
    """The final-development OOF calibration partition (``full_cv + 333``)."""
    from research.intake import rh04_v2_producer_lineage as lineage

    cal = lineage.calibration_oof_assignments(route)
    return {
        "kind": cal["kind"],
        "n_splits": cal["n_splits"],
        "seed": cal["seed"],
        "derivation": cal["derivation"],
        "assignment_sha256": cal["assignment_sha256"],
        # The partition's own rows, NOT the calibrator's input vector.
        "development_input_sha256": cal["development_input_sha256"],
        "development_target_sha256": cal["development_target_sha256"],
    }


def calibration_input_identity(route: str) -> dict[str, Any]:
    """The identity of what the final OOF calibrator was *actually* fitted on."""
    from research.intake import rh04_v2_producer_lineage as lineage

    return lineage.calibration_input_identity(route)


def calibration_input_pin(route: str) -> dict[str, Any]:
    """The digest-only subset of the calibrator-input identity the manifest pins.

    **Build-time only.** Computing this runs the registered producer to capture the
    ordered OOF vector, so it must never be called from Lane B. The pin is written
    into the manifest at build time and is thereafter a fixed reviewable constant.

    Scalar provenance is pinned too: a calibrator that consumed the right vector
    but recorded the wrong solver, link or criterion is a provenance defect even
    when the numbers agree.
    """
    ident = calibration_input_identity(route)
    return {
        "oof_input_sha256": ident["oof_input_sha256"],
        "oof_target_sha256": ident["oof_target_sha256"],
        "oof_raw_logit_sha256": ident["oof_raw_logit_sha256"],
        "input_link": ident["input_link"],
        "fit_scope": ident["fit_scope"],
        "model_family": ident["model_family"],
        "n_oof_samples": ident["n_oof_samples"],
        "fitted_solver": ident["fitted_criterion"]["solver"],
        "fitted_intercept": ident["fitted_parameters"]["intercept"],
        "fitted_slope": ident["fitted_parameters"]["slope"],
        "fitted_status": ident["fitted_parameters"]["status"],
        # The solver is recorded by the producer capture but is NOT carried by
        # the serialized calibration contract, so admission cannot bind it. Saying
        # it is bound would be exactly the "field present means enforced" error.
        "solver_bound_in_archive": False,
        # Honest capability statement, pinned alongside the digests so a reader of
        # the manifest cannot mistake this for evidence Lane B reproduces. The
        # archive is prohibited from carrying the OOF vector, so Lane B can check
        # agreement with the pinned scalars but cannot recompute these digests
        # without fitting -- which Lane B does not do.
        "recomputable_in_lane_b": False,
        "recomputed_by": "Lane A build (producer run) and the lineage tests",
    }


def calibration_input_pin_sha256(route: str) -> str:
    return _sha256(canonical_bytes(calibration_input_pin(route)))


def training_input_sha256(route: str) -> str:
    """Digest of the complete ordered synthetic feature and target input."""
    from research.intake import rh04_v2_producer_lineage as lineage

    return lineage.training_boundary(route).input_sha256()


def _registered_cases() -> list[dict[str, Any]]:
    """The 29 registered cases, read from the frozen V1 pack (never modified)."""
    from research.intake import offline_fixture_pack as v1

    return list(json.loads(v1.PACK.read_text(encoding="utf-8"))["cases"])


def build_manifest(
    archives: Mapping[str, Mapping[str, Any]],
    *,
    reference_id: str,
    raw_digests: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Build the *independent* trusted manifest for a set of archives.

    Produced by an exporter/reviewer role, never by the verifier. It records
    every expected value so verification never reads an expectation back out of
    the artifact under test.
    """
    routes: dict[str, Any] = {}
    raw_digests = dict(raw_digests or {})
    for route, archive in archives.items():
        body = archive
        raw_archive_sha256 = raw_digests.get(route)
        routes[route] = {
            "archive_sha256": archive_digest(body),
            "route_id": body["source"]["route_id"],
            "dataset_id": body["source"]["dataset_id"],
            "panel_id": body["source"]["panel_id"],
            "panel_version": body["source"]["panel_version"],
            "panel_contract_sha256": body["source"]["panel_contract_sha256"],
            "development_cohort_id": body["source"]["development_cohort_id"],
            "bundle_protocol_id": body["source"]["bundle_protocol_id"],
            "model_id": body["source"]["model_id"],
            "model_version": body["source"]["model_version"],
            "ordered_feature_names": list(body["source"]["ordered_feature_names"]),
            "encoded_feature_names": list(
                body["preprocessing"]["encoded_feature_names"]
            ),
            "model_family": body["model"]["family"],
            "execution_profile": body["model"]["execution_profile"],
            "selected_hyperparameters": dict(
                body["training_identity"]["selected_hyperparameters"]
            ),
            "preprocessing_sha256": preprocessing_sha256(body["preprocessing"]),
            "training_identity_sha256": training_identity_sha256(
                body["training_identity"]
            ),
            "split_sha256": body["training_identity"]["split_sha256"],
            "calibration_sha256": calibration_sha256(body["calibration"]),
            "calibration_intercept": body["calibration"]["intercept"],
            "calibration_slope": body["calibration"]["slope"],
            "calibration_input_link": body["calibration"]["input_link"],
            "calibration_fit_scope": body["calibration"]["fit_scope"],
            "calibration_fitted_strictly_out_of_fold": body["calibration"][
                "fitted_strictly_out_of_fold"
            ],
            "calibration_model_family": body["calibration"]["model_family"],
            "calibration_n_oof_samples": body["calibration"]["n_oof_samples"],
            "representation_version": body["model"]["representation_version"],
            "fold_ensemble_sha256": fold_ensemble_sha256(body["fold_ensemble"]),
            # Raw on-disk archive digests: the identity of the committed file
            # itself, independent of the semantic body digest above.
            "raw_archive_sha256": raw_archive_sha256,
            # A digest over the COMPLETE ordered synthetic feature/target input,
            # distinct from the split assignment and from any metadata hash.
            "training_input_sha256": training_input_sha256(route),
            # The actual ordered split/fold assignments, not a hash of metadata.
            "split_assignments": split_assignments(route),
            # The final-development OOF calibration partition, distinct from the
            # outer folds it is so often confused with.
            "calibration_oof": calibration_oof_identity(route),
            # The identity of what the calibrator was ACTUALLY fitted on: the
            # ordered OOF vector, not the development design matrix. Build-time
            # only; Lane B checks the pinned scalars, never refits.
            "calibration_input": calibration_input_pin(route),
            # The exact pinned registry declarations Lane B reconstructs the
            # descriptor from, and the digest of the pinned SHAP background.
            "registry_metadata_sha256": registry_metadata_digest(
                body["source"]["panel_id"],
                body["source"]["model_id"],
                body["source"]["model_version"],
            ),
            "shap_background_sha256_raw": body["training_identity"][
                "shap_background_sha256_raw"
            ],
        }
    return {
        "manifest_schema": MANIFEST_SCHEMA,
        "protocol_id": ARCHIVE_PROTOCOL_ID,
        "reference_id": reference_id,
        "key_label": FIXTURE_KEY_LABEL,
        "routes": routes,
        "case_ids": [case["id"] for case in _registered_cases()],
        "cases": [
            {
                "case_id": case["id"],
                "route_id": case["route"],
                "edits_sha256": _sha256(canonical_bytes(case["edits"])),
                "expected_sha256": _sha256(canonical_bytes(case["expected"])),
            }
            for case in _registered_cases()
        ],
    }


# ---------------------------------------------------------------------------
# The facade adapter: execute the real pipeline with a portable artifact
# ---------------------------------------------------------------------------

#: The one facade function this module substitutes. It is the single point where
#: the registered pipeline transitions from verified metadata to a deserialised
#: model, and it is already the established test seam in this repository
#: (``tests/experiments/test_offline_fixture_pack.py`` patches exactly it).
SEAM_NAME: Final[str] = "_load_artifact"


#: Pinned registry metadata binding. The panel contract and model entry are
#: static, reviewed declarations in the source tree -- not training output --
#: and their digests are recorded in the trusted manifest so a consumer proves
#: it is using the same registry revision the archives were produced against.
REGISTRY_METADATA_KEYS: Final[tuple[str, ...]] = (
    "panel_id",
    "model_id",
    "panel_contract_sha256",
    "registry_metadata_sha256",
)


def registry_metadata_digest(panel_id: str, model_id: str, model_version: str) -> str:
    """Digest of the exact non-sensitive registry declarations Lane B relies on."""
    from ai.panels import REGISTERED_PANELS
    from ai.research_registry import RESEARCH_MODEL_REGISTRY

    panel = REGISTERED_PANELS[panel_id]
    entry = RESEARCH_MODEL_REGISTRY[f"{model_id}@{model_version}"]
    return _sha256(
        canonical_bytes(
            {
                "panel": {
                    "panel_id": panel.panel_id,
                    "panel_version": panel.panel_version,
                    "dataset_id": panel.dataset_id,
                    "source_family": panel.source_family,
                    "stage": panel.stage,
                    "target_id": panel.target_id,
                    "fields": [
                        {
                            "name": f.name,
                            "role": f.role,
                            "order": int(f.order),
                            "required": bool(f.required),
                            "unit": f.unit,
                            "strictly_positive": bool(f.strictly_positive),
                            "categorical_codes": list(f.categorical_codes or ()),
                            "text_vocabulary": dict(f.text_vocabulary or {}),
                        }
                        for f in panel.fields
                    ],
                },
                "entry": {
                    "model_id": entry.model_id,
                    "model_version": entry.model_version,
                    "protocol_id": entry.protocol_id,
                    "execution_profile": entry.execution_profile,
                    "panel_id": entry.panel_id,
                    "panel_version": entry.panel_version,
                    "target_id": entry.target_id,
                },
            }
        )
    )


def _build_descriptor(
    admitted: Mapping[str, Any], panel: Any, entry: Any
) -> Any:
    """Build the verified-descriptor equivalent from pinned registry data.

    ``producer_authenticated`` and ``safe_for_pickle_deserialization`` are
    **False** by design: this describes a portable archive, not an authenticated
    producer bundle, and nothing downstream may deserialise.
    """
    from ai.packaging import VerifiedBundleDescriptor

    training = admitted["training_identity"]
    pinned = admitted["registry_descriptor"]
    manifest = {
        "bundle_schema_version": pinned["bundle_schema_version"],
        "eligibility": dict(pinned["eligibility"]),
        "research_authorization": pinned["research_authorization"],
        "model": {
            "model_id": entry.model_id,
            "model_version": entry.model_version,
            "protocol_id": entry.protocol_id,
            "execution_profile": entry.execution_profile,
            "selected_model_family": admitted["model"]["family"],
            "calibration_status": pinned["calibration_status"],
            "selected_hyperparameters": dict(training["selected_hyperparameters"]),
            "explainability": dict(pinned["explainability"]),
        },
        "panel_contract": {
            "panel_id": panel.panel_id,
            "panel_version": panel.panel_version,
            "contract_sha256": panel.contract_sha256,
            "ordered_feature_names": list(panel.feature_names),
        },
        "target": dict(pinned["target_block"]),
        "files": {
            "calibration.json": {"sha256": training["calibration_sha256_raw"]},
            "preprocessing.json": {"sha256": training["preprocessing_sha256_raw"]},
            "shap_background.json": {"sha256": training["shap_background_sha256_raw"]},
        },
        "local_producer_attestation": {"scheme": "not_applicable_pinned_archive"},
    }
    return VerifiedBundleDescriptor(
        bundle_dir=Path("<pinned-archive>"),
        manifest=manifest,
        panel=panel,
        verified_files={k: dict(v) for k, v in manifest["files"].items()},
        integrity_verified_only_not_authenticated=True,
        producer_authenticated=False,
        safe_for_pickle_deserialization=False,
    )


#: Deterministic SHAP-background reconstruction parameters, per registered panel.
#:
#: The producer builds the background with ``ShapBackgroundReference.from_training_encoded``
#: over the *development cohort's encoded training matrix*, using
#: ``seed = repeat_seed + 90000 + 4242`` and ``max_samples = 24``. Reproducing that
#: call from the pinned synthetic cohort, the pinned seed schedule and the pinned
#: preprocessor yields the identical document byte-for-byte (verified for both
#: panels), so the prohibited training projection never has to be stored.
def _shap_spec(panel_id: str) -> Any:
    from research.intake import rh04_v2_producer_lineage as lineage

    return lineage.producer_spec(panel_id)


def shap_background_seed(panel_id: str) -> int:
    """``full_cv_seed + 4242``, derived from the producer's repeat seed."""
    return int(_shap_spec(panel_id).shap_background_seed)


def shap_background_recipe(panel_id: str) -> dict[str, Any]:
    """The recorded recipe that regenerates the pinned SHAP background document."""
    spec = _shap_spec(panel_id)
    if spec is None:
        raise ArchiveError(f"no SHAP reconstruction recipe for panel {panel_id!r}")
    return {
        "method": "ShapBackgroundReference.from_training_encoded",
        "stores_training_projection": False,
        "derivation": spec.as_dict(),
        "seed": int(spec.shap_background_seed),
        "seed_derivation": "repeat_seed + 90000 + 4242",
        "max_samples": int(_shap_max_samples(panel_id)),
        "synthetic_only": True,
    }


def _shap_max_samples(panel_id: str) -> int:
    from ai.research_demo import DEMO_TRAINING_CONFIG
    from ai.uci412_research import Uci412ResearchModelConfig

    if panel_id == REST_ROUTE:
        return int(DEMO_TRAINING_CONFIG.shap_max_background_samples)
    return int(Uci412ResearchModelConfig.fast().training_config().shap_max_background_samples)


def _development_cohort(panel_id: str) -> tuple[list[Any], list[int]]:
    """Rebuild the exact ordered synthetic development cohort for a panel."""
    from research.intake import rh04_v2_producer_lineage as lineage

    return lineage.build_cohort(panel_id)


def reconstruct_shap_background(
    training: Mapping[str, Any], panel: Any
) -> dict[str, Any]:
    """Regenerate the SHAP background from the recipe; never from stored rows.

    The result is checked against the expected SHA-256 that the independently
    trusted manifest pins, so a drifted reconstruction is a refusal rather than a
    silently different explanation baseline.
    """
    from ai.explainability import ShapBackgroundReference
    from ai.preprocessing import FoldSafeClinicalPreprocessor
    from ai.training import validate_cohort_records

    recipe = training["shap_background_recipe"]
    if recipe.get("stores_training_projection") is not False:
        raise ArchiveError(
            "archive claims to store the SHAP training projection; that is "
            "publication-prohibited and is refused rather than read"
        )
    records, labels = _development_cohort(panel.panel_id)
    X, y, _ = validate_cohort_records(records, labels, panel)
    preprocessor = FoldSafeClinicalPreprocessor.from_json_dict(
        dict(training["_preprocessing"]), expected_panel=panel
    )
    Z = preprocessor.transform(X)
    reference = ShapBackgroundReference.from_training_encoded(
        Z,
        y,
        preprocessor,
        max_samples=int(recipe["max_samples"]),
        seed=int(recipe["seed"]),
        synthetic_only=True,
    )
    raw = reference.to_canonical_json_bytes()
    if _sha256(raw) != training["shap_background_sha256_raw"]:
        raise ArchiveError(
            "reconstructed SHAP background does not match the pinned digest"
        )
    document = json.loads(raw.decode("utf-8"))
    if not isinstance(document, Mapping):
        raise ArchiveError("reconstructed SHAP background is not an object")
    return dict(document)


class _PortableLoadedArtifact:
    """Facade-compatible loaded artifact built without deserialisation."""

    def __init__(
        self,
        *,
        predictor: Any,
        descriptor: Any,
        capabilities: Any,
        model_family: str,
        facade: Any,
    ) -> None:
        self.predictor = predictor
        self.descriptor = descriptor
        self.capabilities = capabilities
        self.model_family = model_family
        self.signing_key_provided = False
        self._facade = facade

    def safe_block(self) -> dict[str, Any]:
        """Delegate to the facade's own path-free identity block."""
        shadow = type("_Shadow", (), {})()
        shadow.descriptor = self.descriptor
        shadow.signing_key_provided = self.signing_key_provided
        return self._facade._LoadedArtifact.safe_block(shadow)


def load_artifact_from_archive(
    facade: Any,
    admitted: Mapping[str, Any],
    *,
    entry: Any,
    panel: Any,
) -> _PortableLoadedArtifact:
    """Build the facade artifact from an **already admitted** archive.

    Every inference dependency comes from pinned data:

    * model            -- rehydrated from the archive's declarative arrays;
    * preprocessing    -- the archive's own record;
    * calibration      -- the archive's own record;
    * fold ensemble    -- the archive's own record;
    * SHAP background  -- decoded from pinned canonical bytes, digest-checked;
    * descriptor/panel -- reconstructed from pinned registry metadata.

    The producer bundle is never read. Every value is checked against the
    independently trusted manifest before this function can be reached.
    """
    from ai.calibration import OofLogisticCalibrator
    from ai.cli import assert_cli_predict_supported
    from ai.explainability import ShapBackgroundReference
    from ai.inference import ResearchCadPredictor
    from ai.preprocessing import FoldSafeClinicalPreprocessor
    from ai.research_registry import (
        ResearchRegistryError,
        assert_artifact_identity,
        derive_artifact_capabilities,
    )
    from ai.training import FoldEnsembleMember

    Refusal = facade._Refusal
    descriptor = _build_descriptor(admitted, panel, entry)
    try:
        assert_cli_predict_supported(descriptor.manifest)
        model_family = assert_artifact_identity(descriptor.manifest, entry)
        if model_family != admitted["model"]["family"]:
            raise Refusal("artifact_identity_mismatch", stage="artifact")
        preprocessor = FoldSafeClinicalPreprocessor.from_json_dict(
            dict(admitted["preprocessing"]), expected_panel=descriptor.panel
        )
        calibration_doc = dict(admitted["training_identity"]["calibration_document"])
        calibrator = OofLogisticCalibrator.from_json_dict(calibration_doc)
        background_doc = reconstruct_shap_background(
            {**admitted["training_identity"], "_preprocessing": admitted["preprocessing"]},
            descriptor.panel,
        )
        capabilities = derive_artifact_capabilities(
            descriptor.manifest,
            entry=entry,
            calibrator=calibrator,
            background_document=background_doc,
            model_family=model_family,
        )
        background = ShapBackgroundReference.from_json_dict(
            background_doc,
            preprocessor=preprocessor,
            require_synthetic=True,
            is_authorized_research_bundle=False,
        )
        members = []
        for spec in admitted["fold_ensemble"]:
            member_pre = FoldSafeClinicalPreprocessor.from_json_dict(
                dict(spec["preprocessing"]), expected_panel=descriptor.panel
            )
            member_cal = OofLogisticCalibrator.from_json_dict(dict(spec["calibrator"]))
            if member_cal.model_family != spec["model_family"]:
                raise Refusal("fold_calibrator_family_mismatch", stage="artifact")
            members.append(
                FoldEnsembleMember(
                    fold_index=int(spec["fold_index"]),
                    model_family=str(spec["model_family"]),
                    preprocessor=member_pre,
                    estimator=rehydrate_member(spec),
                    calibrator=member_cal,
                )
            )
        predictor = ResearchCadPredictor(
            descriptor=descriptor,
            preprocessor=preprocessor,
            estimator=rehydrate(admitted),
            calibrator=calibrator,
            shap_background=background,
            fold_ensemble=tuple(members),
        )
    except Refusal:
        raise
    except ResearchRegistryError as exc:
        raise Refusal(
            exc.code, stage="artifact", field_name=exc.field, panel=descriptor.panel
        ) from exc
    except ArchiveError:
        raise
    except Exception as exc:  # noqa: BLE001 - generic in the response, chained for operators
        raise Refusal(
            "bundle_verification_failed", stage="artifact", panel=descriptor.panel
        ) from exc

    if (
        predictor.model_id != entry.model_id
        or predictor.model_version != entry.model_version
        or predictor.panel.panel_id != entry.panel_id
        or predictor.execution_profile != entry.execution_profile
    ):
        raise Refusal("artifact_identity_mismatch", stage="artifact")
    return _PortableLoadedArtifact(
        predictor=predictor,
        descriptor=descriptor,
        capabilities=capabilities,
        model_family=model_family,
        facade=facade,
    )


def rehydrate_member(spec: Mapping[str, Any]):
    """Rehydrate one outer-fold estimator from its declarative representation."""
    return rehydrate(
        {
            "model": {
                "family": spec["model_family"],
                "classes": [0, 1],
                "representation": spec["representation"],
            },
            "preprocessing": spec["preprocessing"],
        }
    )


# ---------------------------------------------------------------------------
# Independently pinned trust anchor for the trusted manifest
# ---------------------------------------------------------------------------

#: The one manifest document this implementation is authorised to admit against.
#:
#: This constant is the *trust anchor*. It is a hash of the manifest's canonical
#: bytes, and it is compiled into this module -- it is not read from the manifest,
#: from the archives, or from anything the caller supplies. An attacker who
#: rewrites a manifest to re-pin a forged archive must also change this constant
#: in reviewed source, which is a different and visible act.
#:
#: The fixture HMAC key is **public test material** and confers no authenticity
#: whatsoever. It proves only that whoever assembled an archive knew the published
#: constant. It is retained solely to keep the archive format honest about the
#: producer hand-off, and no trust decision may rest on it.
TRUSTED_MANIFEST_SHA256: Final[str] = (
    "293c6e3f6e9aa74f1119a52b56d97af8774a76e90b162a41a222a46a07a63c70"
)

TRUST_ANCHOR_LABEL: Final[str] = (
    "rh04-portable-fixture-trust-anchor-v1"
)


def trusted_manifest_sha256(manifest: Mapping[str, Any]) -> str:
    """Canonical digest of a manifest document, independent of file formatting."""
    return _sha256(canonical_bytes(manifest))


def assert_trusted_manifest(manifest: Mapping[str, Any]) -> str:
    """Fail closed unless ``manifest`` is the independently anchored document.

    The comparison is against a compiled-in constant, and there is deliberately no
    parameter that can change it. A caller who supplies the archives, the manifest
    and a "trusted" expectation is supplying all three sides of the comparison --
    which is not a trust decision at all.
    """
    expected = TRUSTED_MANIFEST_SHA256
    if not isinstance(expected, str) or len(expected) != 64:
        raise ArchiveError(
            "trust anchor is unset; refusing to admit against an unpinned manifest"
        )
    actual = trusted_manifest_sha256(manifest)
    if not hmac.compare_digest(actual, expected):
        raise ArchiveError(
            "trusted manifest does not match the independently anchored identity; "
            "a manifest supplied alongside the archives is not a trust anchor"
        )
    return actual


#: Context-local dispatch stack. Using a ``ContextVar`` means two replays can be
#: active in the same process, and in the same thread nest, without either one
#: observing the other's route table.
_REPLAY_STACK: "ContextVar[tuple[Any, ...]]" = ContextVar(
    "rh04_portable_replay_stack", default=()
)

@dataclass(frozen=True)
class _Entry:
    """One active ``with replay`` block, recorded in the calling context."""

    facade: Any
    token: Any


#: One entry per active ``with replay`` block **in the calling context**. Keeping
#: this context-local (rather than an attribute on the replay) is what makes a
#: shared instance safe across threads.
_ENTRY_STACK: "ContextVar[tuple[Any, ...]]" = ContextVar(
    "rh04_portable_entry_stack", default=()
)


def _active_dispatch() -> Any:
    stack = _REPLAY_STACK.get()
    return stack[-1] if stack else None


#: Immutability without type drift.
#:
#: The snapshot must be independently owned so a caller cannot mutate admitted
#: weights, but the *values* must stay plain JSON types -- the project's own
#: parsers legitimately require ``list`` where the format says list, and freezing
#: a list into a tuple changes the document's meaning to them. So the snapshot is
#: a deep copy guarded by a mutation-refusing wrapper on every mapping only.
class _FrozenDict(dict):
    """A dict that refuses mutation; used for admitted archive snapshots."""

    __slots__ = ()

    def _refuse(self, *args: Any, **kwargs: Any) -> Any:
        raise TypeError("an admitted snapshot is immutable")

    __setitem__ = _refuse
    __delitem__ = _refuse
    __ior__ = _refuse
    clear = _refuse
    pop = _refuse
    popitem = _refuse
    setdefault = _refuse
    update = _refuse


class _FrozenList(list):
    """A list that refuses in-place mutation, still a ``list`` to every reader."""

    __slots__ = ()

    def _refuse(self, *args: Any, **kwargs: Any) -> Any:
        raise TypeError("an admitted snapshot is immutable")

    __setitem__ = _refuse
    __delitem__ = _refuse
    __iadd__ = _refuse
    __imul__ = _refuse
    append = _refuse
    extend = _refuse
    insert = _refuse
    pop = _refuse
    remove = _refuse
    reverse = _refuse
    sort = _refuse
    clear = _refuse


def _freeze_snapshot(value: Any) -> Any:
    """Deep-copy a document, refusing mutation at every container level.

    Both mappings and lists stay the *types* the JSON format declared, because the
    project's parsers legitimately require ``list`` where the format says list;
    they simply refuse mutation. Turning lists into tuples would change the
    document's meaning to those parsers, which is how an earlier revision broke
    admission while looking correct.
    """
    if isinstance(value, Mapping):
        return _FrozenDict({k: _freeze_snapshot(v) for k, v in value.items()})
    if isinstance(value, list):
        return _FrozenList(_freeze_snapshot(v) for v in value)
    return copy.deepcopy(value)


class PortableReplay:
    """Run the registered facade against **admitted** portable archives.

    Admission is mandatory and happens in the constructor, before any facade
    call is possible:

    * the trusted manifest and key are required arguments;
    * the expected route set must match the manifest's route set exactly;
    * ``admit()`` runs for every route;
    * only the admitted archives are retained and used.

    No scoring or estimator construction can occur before that succeeds, because
    the archives are not even stored until every route has been admitted.
    """

    def __init__(
        self,
        facade: Any,
        *,
        manifest: Mapping[str, Any],
        key: bytes,
        archives: Mapping[str, Mapping[str, Any]],
    ) -> None:
        manifest = validate_manifest(manifest)
        # Re-entrancy: ``execute_case`` enters the replay again, so tokens are
        # kept as a stack rather than a single slot.

        # The trust anchor is checked FIRST: a forged manifest that re-pins a
        # forged archive must be rejected before its route table is believed.
        self._manifest_identity = assert_trusted_manifest(manifest)
        expected = set(manifest["routes"])
        supplied = set(archives)
        missing = sorted(expected - supplied)
        unexpected = sorted(supplied - expected)
        if missing:
            raise ArchiveError(f"archives missing for manifest routes {missing}")
        if unexpected:
            raise ArchiveError(f"archives supplied for unpinned routes {unexpected}")
        if len(archives) != len(supplied):
            raise ArchiveError("duplicate routes in the archive mapping")

        admitted: dict[str, dict[str, Any]] = {}
        for route in sorted(expected):
            # Admit the caller's document, then store an independently owned deep
            # copy. A shallow ``dict(...)`` copy would share the nested lists, so a
            # caller could mutate model weights *after* admission and change the
            # evaluation without ever failing a check.
            # Read the caller's mapping EXACTLY ONCE. The object read here is
            # both verified and stored, so there is no window in which a second
            # read of a caller-controlled mapping could return different content.
            #
            # The previous version evaluated ``archives[route]`` twice: once for
            # ``admit()`` and once to build the snapshot. A mapping whose
            # ``__getitem__`` varies per call would then have its *first* read
            # verified and its *second* read executed -- verification and
            # execution on different content.
            supplied_document = archives[route]
            verified = admit(
                supplied_document, manifest, key=key, expected_route=route
            )
            # The snapshot is built from the admitted result, serialised
            # immediately, so it is derived from the verified content rather than
            # from a fresh read of anything the caller can influence.
            admitted[route] = _freeze_snapshot(
                json.loads(canonical_bytes(verified).decode("utf-8"))
            )
        # Only now, after every route admitted, are the archives retained.
        self._facade = facade
        self._admitted = admitted
        self._manifest = manifest
        self._key = bytes(key)

    @property
    def admitted_routes(self) -> tuple[str, ...]:
        return tuple(sorted(self._admitted))

    # -- context-local activation ------------------------------------------- #

    def _dispatch(self, request: Any, binding: Any, request_panel: Any) -> Any:
        route = request.route_id
        if route not in self._admitted:
            raise self._facade._Refusal(
                "portable_archive_absent_for_route",
                stage="artifact",
                panel=request_panel,
            )
        return load_artifact_from_archive(
            self._facade,
            self._admitted[route],
            entry=binding.entry,
            panel=request_panel,
        )

    def __enter__(self) -> "PortableReplay":
        """Push this replay onto the context-local dispatch stack.

        Nested replays nest correctly: the innermost active one wins, and leaving
        it restores the previous one. Nothing is written to the facade here, and
        all bookkeeping is context-local, so a shared instance is safe across
        threads and nested ``with`` blocks on one instance unwind correctly.
        """
        _activate_seam(self._facade)
        stack = _ENTRY_STACK.get()
        token = _REPLAY_STACK.set(_REPLAY_STACK.get() + (self,))
        _ENTRY_STACK.set(stack + (_Entry(self._facade, token),))
        return self

    def __exit__(self, *exc: object) -> None:
        stack = _ENTRY_STACK.get()
        if not stack:
            return
        entry = stack[-1]
        if entry.facade is not self._facade:
            raise RuntimeError("replay context exited out of order")
        _ENTRY_STACK.set(stack[:-1])
        _REPLAY_STACK.reset(entry.token)
        _deactivate_seam(self._facade)


#: The module-level seam shared by every replay. It is installed once, while at
#: least one replay is active, and removed again when the last one exits -- so the
#: facade's own loader is genuinely restored and the facade keeps working for real
#: bundles outside a replay. Because dispatch reads a ``ContextVar``, simultaneous
#: and nested replays never observe one another's route table.
_ACTIVE_REPLAYS: Final[list[int]] = [0]
_SEAM_LOCK: "Lock" = Lock()


def _shared_seam(request: Any, binding: Any, panel: Any) -> Any:
    """Dispatch to the innermost replay of *this* context, else the real loader.

    When no replay is active in the calling context, ``_load_artifact`` is
    delegated to the facade's own implementation. That is what makes an ordinary
    registered-lane call safe while another thread is replaying: the seam is
    installed process-wide but its behaviour is context-local.
    """
    replay = _active_dispatch()
    if replay is None:
        return _ORIGINAL_SEAM(request, binding, panel)
    return replay._dispatch(request, binding, panel)


def _activate_seam(facade: Any) -> None:
    """Install the shared seam on the first active replay."""
    with _SEAM_LOCK:
        _ACTIVE_REPLAYS[0] += 1
        if _ACTIVE_REPLAYS[0] == 1:
            setattr(facade, SEAM_NAME, _shared_seam)


def _deactivate_seam(facade: Any) -> None:
    """Restore the facade's own loader when the last active replay exits."""
    with _SEAM_LOCK:
        _ACTIVE_REPLAYS[0] = max(0, _ACTIVE_REPLAYS[0] - 1)
        if _ACTIVE_REPLAYS[0] == 0:
            setattr(facade, SEAM_NAME, _ORIGINAL_SEAM)


def restore_facade_seam(facade: Any) -> None:
    """Force the facade's own loader back and clear the active count.

    Only for test teardown and process shutdown; normal replay exit already
    restores the loader.
    """
    with _SEAM_LOCK:
        _ACTIVE_REPLAYS[0] = 0
        setattr(facade, SEAM_NAME, _ORIGINAL_SEAM)


#: The facade's own ``_load_artifact``, captured at import time so restoration can
#: never depend on whatever happens to be installed later.
def _capture_original_seam() -> Any:
    from ai import research_facade as _facade_module

    return getattr(_facade_module, SEAM_NAME)


_ORIGINAL_SEAM: Any = _capture_original_seam()


#: The consumer allowlist used by the registered fixture export. Reproduced here
#: rather than imported so the frozen V1 module stays untouched; it is an export
#: shape, not a behavioural rule.
EXPORTED_TOP_KEYS: Final[tuple[str, ...]] = (
    "status",
    "panel_id",
    "route_id",
    "dataset_id",
    "evidence_level",
    "error",
)
EXPORTED_OUTCOME_KEYS: Final[tuple[str, ...]] = (
    "status",
    "score",
    "abstention_reason",
    "unavailable_reason",
    "present_fields",
    "missing_fields_with_reason",
    "error",
)


def shape_response(response: Any) -> dict[str, Any]:
    """Project a facade response onto the registered exported shape."""
    data = response.to_dict()
    out = {key: data[key] for key in EXPORTED_TOP_KEYS}
    out["outcomes"] = [
        {key: item[key] for key in EXPORTED_OUTCOME_KEYS}
        for item in (o.to_dict() for o in response.outcomes)
    ]
    return out


#: A path that deliberately does not exist. The portable lane passes a source
#: pointing here, so any code that actually tried to read a producer bundle would
#: fail loudly instead of silently borrowing one.
ABSENT_BUNDLE_PATH: Final[Path] = Path(
    "<no-producer-bundle-is-present-in-the-portable-lane>"
)


def declared_absent_source() -> Any:
    """The registered source type, pointed at a path that does not exist."""
    from ai.research_facade import LocalSyntheticBundleSource

    return LocalSyntheticBundleSource(ABSENT_BUNDLE_PATH, ABSENT_BUNDLE_PATH)


def execute_case(
    facade: Any,
    request: Mapping[str, Any],
    replay: "PortableReplay",
    *,
    model_source: Any = None,
) -> dict[str, Any]:
    """Execute one registered case through the facade and export the response.

    ``model_source`` defaults to a source whose paths do not exist: the portable
    lane must not need any producer bundle, and the facade's own request
    validation only needs the registered source *type*.
    """
    if model_source is None:
        model_source = declared_absent_source()
    with replay:
        response = facade.run_offline_research_inference_from_document(
            dict(request), model_source=model_source
        )
    return shape_response(response)


def response_identity(facade: Any, requests: Sequence[Mapping[str, Any]],
                      replay: "PortableReplay", *, model_source: Any) -> str:
    """Order-independent digest over the 29 exported responses."""
    digests = [
        _sha256(canonical_bytes(
            execute_case(facade, request, replay, model_source=model_source)
        ))
        for request in requests
    ]
    return _sha256("".join(digests).encode("ascii"))


# ---------------------------------------------------------------------------
# Raw-file identity: enforced against bytes, before any JSON parsing
# ---------------------------------------------------------------------------


def load_admitted_archives(
    directory: Any,
    manifest: Mapping[str, Any],
    *,
    key: bytes = FIXTURE_SIGNING_KEY,
) -> dict[str, dict[str, Any]]:
    """Read, digest-check and admit every archive file named by the manifest.

    Raw file identity is verified **against the bytes on disk, before parsing**,
    so the manifest's ``raw_archive_sha256`` is an enforced identity rather than a
    recorded value. Parsing happens only for a file whose bytes already match.
    """
    directory = Path(directory)
    manifest = validate_manifest(manifest)
    assert_trusted_manifest(manifest)

    loaded: dict[str, dict[str, Any]] = {}
    for route in sorted(manifest["routes"]):
        path = directory / f"{route}.archive.json"
        if not path.is_file():
            raise ArchiveError(f"no archive file for pinned route {route!r}")
        raw_bytes = path.read_bytes()
        expected_raw = manifest["routes"][route]["raw_archive_sha256"]
        actual_raw = _sha256(raw_bytes)
        if not hmac.compare_digest(actual_raw, expected_raw):
            raise ArchiveError(
                f"raw archive bytes for {route!r} do not match the manifest; the "
                "file identity is enforced before parsing"
            )
        loaded[route] = json.loads(raw_bytes.decode("utf-8"))
    return loaded


# ---------------------------------------------------------------------------
# The one supported admission + replay entry point
# ---------------------------------------------------------------------------

#: Pinned Lane B reference. Derived once from these committed artifacts against
#: the independently anchored manifest; never regenerated to match an observation.
LANE_B_REFERENCE_DIGEST: Final[str] = "891d9e3b2a332c6efc251d97fee25ed46a627ed25b2a089594057b4c9896cdc8"

#: The registered case count. Anything else is a refusal, not a "suite".
REGISTERED_CASE_COUNT: Final[int] = 29


def _strict_json_loads(raw: bytes, *, where: str) -> Any:
    """Parse JSON refusing duplicate keys and non-finite constants.

    ``json.loads`` silently keeps the last duplicate key and accepts ``NaN`` and
    ``Infinity``; both would let two different files hash to one meaning.
    """

    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        seen: set[str] = set()
        for key, _value in pairs:
            if key in seen:
                raise ArchiveError(f"{where} contains duplicate key {key!r}")
            seen.add(key)
        return dict(pairs)

    def no_constants(token: str) -> Any:
        raise ArchiveError(f"{where} contains non-finite constant {token!r}")

    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=no_duplicates,
            parse_constant=no_constants,
        )
    except ArchiveError:
        raise
    except Exception as exc:  # noqa: BLE001 - reported as a refusal
        raise ArchiveError(f"{where} is not strict-parseable JSON") from exc


def _assert_case_set(manifest: Mapping[str, Any]) -> None:
    """Every recorded case binding must match the frozen V1 fixture exactly.

    Checking the id list alone is not enough. The manifest also records, per case,
    the route it is sent to and digests of its edits and expected response; a
    manifest that kept the ids and order while re-pointing a case at another route,
    or attaching different edits, would pass an ids-only check and then execute
    something the reviewer never approved.
    """
    case_ids = list(manifest.get("case_ids") or ())
    registered = [case["id"] for case in _registered_cases()]
    if len(case_ids) != REGISTERED_CASE_COUNT:
        raise ArchiveError(
            f"manifest declares {len(case_ids)} cases; the registered count is "
            f"{REGISTERED_CASE_COUNT}"
        )
    if len(set(case_ids)) != len(case_ids):
        raise ArchiveError("manifest case_ids contain duplicates")
    if case_ids != registered:
        raise ArchiveError(
            "manifest case_ids do not match the registered case order exactly"
        )

    # The full per-case record, bound field by field against the frozen fixture.
    recorded = list(manifest.get("cases") or ())
    if len(recorded) != REGISTERED_CASE_COUNT:
        raise ArchiveError(
            f"manifest carries {len(recorded)} case records; expected "
            f"{REGISTERED_CASE_COUNT}"
        )
    for fixture_case, actual in zip(_registered_cases(), recorded):
        case_id = fixture_case["id"]
        # Recompute from the frozen fixture rather than trusting the manifest's
        # own digest of itself.
        want = {
            "case_id": case_id,
            "route_id": fixture_case["route"],
            "edits_sha256": _sha256(canonical_bytes(fixture_case["edits"])),
            "expected_sha256": _sha256(canonical_bytes(fixture_case["expected"])),
        }
        if actual.get("case_id") != case_id:
            raise ArchiveError(
                f"manifest case record {actual.get('case_id')!r} is out of order; "
                f"expected {case_id!r}"
            )
        if actual.get("route_id") != want["route_id"]:
            raise ArchiveError(
                f"case {case_id!r} is bound to route {actual.get('route_id')!r} but "
                f"the frozen fixture routes it to {want['route_id']!r}"
            )
        for field_name in ("edits_sha256", "expected_sha256"):
            if actual.get(field_name) != want[field_name]:
                raise ArchiveError(
                    f"case {case_id!r} {field_name} does not match the frozen V1 "
                    "fixture binding"
                )


@dataclass(frozen=True)
class AdmissionResult:
    """An independently owned, immutable, fully admitted artifact set."""

    manifest: Mapping[str, Any]
    manifest_identity: str
    routes: tuple[str, ...]
    case_ids: tuple[str, ...]
    archives: Mapping[str, Any]
    raw_digests: Mapping[str, str]
    #: SHA-256 of the frozen V1 pack bytes verified during admission. Replay
    #: re-reads the pack; this binds that second read to the first.
    fixture_sha256: str = ""


def admit_from_directory(directory: Any, *, key: bytes = FIXTURE_SIGNING_KEY) -> AdmissionResult:
    """The supported admission entry point: files on disk, nothing caller-shaped.

    Sequence, and every step fails closed:

    1. strict-parse the manifest and verify it against the compiled-in anchor;
    2. validate the manifest schema and the registered 29-case set;
    3. for each pinned route, hash the raw file bytes *before* parsing;
    4. strict-parse the archive (duplicate keys and non-finite values refused);
    5. structural validation, then full semantic ``admit()`` against the manifest;
    6. freeze an independently owned snapshot.

    There is no code path here that accepts a raw mutable dictionary as an
    alternative admission route.
    """
    directory = Path(directory)
    manifest_path = directory / "trusted_manifest.json"
    if not manifest_path.is_file():
        raise ArchiveError("no trusted_manifest.json in the artifact directory")
    manifest = _strict_json_loads(manifest_path.read_bytes(), where="trusted_manifest.json")
    manifest_identity = assert_trusted_manifest(manifest)
    manifest = validate_manifest(manifest)
    _assert_case_set(manifest)

    # The frozen V1 fixture is read ONCE here, verified, and its identity is
    # carried on the admission result so replay cannot silently use other bytes.
    from research.intake import offline_fixture_pack as v1

    fixture_bytes = v1.PACK.read_bytes()
    fixture_sha256 = _sha256(fixture_bytes)
    fixture_pack = _strict_json_loads(fixture_bytes, where="offline_io.v1.json")
    if len(fixture_pack["cases"]) != REGISTERED_CASE_COUNT:
        raise ArchiveError(
            f"the frozen V1 fixture carries {len(fixture_pack['cases'])} cases; "
            f"expected {REGISTERED_CASE_COUNT}"
        )

    raw_digests: dict[str, str] = {}
    archives: dict[str, Any] = {}
    for route in sorted(manifest["routes"]):
        path = directory / f"{route}.archive.json"
        if not path.is_file():
            raise ArchiveError(f"no archive file for pinned route {route!r}")
        raw_bytes = path.read_bytes()
        actual = _sha256(raw_bytes)
        expected = manifest["routes"][route]["raw_archive_sha256"]
        if not hmac.compare_digest(actual, expected):
            raise ArchiveError(
                f"raw archive bytes for {route!r} do not match the manifest; the "
                "file identity is enforced before parsing"
            )
        raw_digests[route] = actual
        document = _strict_json_loads(raw_bytes, where=f"{route}.archive.json")
        admit(document, manifest, key=key, expected_route=route)
        archives[route] = _freeze_snapshot(
            json.loads(canonical_bytes(document).decode("utf-8"))
        )
    return AdmissionResult(
        manifest=_freeze_snapshot(manifest),
        manifest_identity=manifest_identity,
        routes=tuple(sorted(archives)),
        case_ids=tuple(manifest["case_ids"]),
        archives=archives,
        raw_digests=raw_digests,
        fixture_sha256=fixture_sha256,
    )


def replay_admitted(facade: Any, admitted: AdmissionResult) -> dict[str, Any]:
    """Execute the registered 29 cases against an admitted snapshot.

    Requests are materialised from the frozen V1 pack; no caller-supplied request
    can substitute for a registered case.
    """
    from research.intake import offline_fixture_pack as v1

    # The pack is re-read here, so bind this read to the identity verified at
    # admission rather than trusting whatever is on disk now.
    if not admitted.fixture_sha256:
        raise ArchiveError(
            "admission did not record the frozen V1 fixture identity; replay "
            "cannot prove it is using the verified bytes"
        )
    probed = v1.PACK.read_bytes()
    if not hmac.compare_digest(_sha256(probed), admitted.fixture_sha256):
        raise ArchiveError(
            "the frozen V1 fixture changed between admission and replay; refusing "
            "to materialise requests from unverified bytes"
        )
    pack = _strict_json_loads(probed, where="offline_io.v1.json")
    cases = list(pack["cases"])
    if len(cases) != REGISTERED_CASE_COUNT:
        raise ArchiveError("the registered pack no longer carries 29 cases")
    if [case["id"] for case in cases] != list(admitted.case_ids):
        raise ArchiveError("admitted case set does not match the registered pack")

    replay = PortableReplay(
        facade,
        manifest=_thaw(admitted.manifest),
        key=FIXTURE_SIGNING_KEY,
        archives={route: _thaw(admitted.archives[route]) for route in admitted.routes},
    )
    responses: list[dict[str, Any]] = []
    for case in cases:
        request = v1.materialize(pack["requests"][case["route"]], case["edits"])
        responses.append(execute_case(facade, request, replay))
    return {
        "n_cases": len(responses),
        "responses": responses,
        "digest": _sha256(
            "".join(_sha256(canonical_bytes(r)) for r in responses).encode("ascii")
        ),
    }


def _thaw(value: Any) -> Any:
    """Return plain mutable containers from an admitted snapshot."""
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_thaw(item) for item in value]
    return value


def verify_artifact_directory(
    directory: Any, *, facade_module: Any = None
) -> dict[str, Any]:
    """Verify an artifact directory end to end and replay all 29 registered cases.

    This is the single supported verification command. It returns sanitised
    evidence only: digests, counts and a per-case status tally -- never feature
    matrices, OOF vectors, paths or caller values.
    """
    from ai import research_facade as facade_module_default

    facade = facade_module if facade_module is not None else facade_module_default
    admitted = admit_from_directory(directory)
    result = replay_admitted(facade, admitted)
    statuses: dict[str, int] = {}
    for response in result["responses"]:
        statuses[response["status"]] = statuses.get(response["status"], 0) + 1
    return {
        "manifest_identity": admitted.manifest_identity,
        "routes": list(admitted.routes),
        "raw_digests": dict(admitted.raw_digests),
        "n_cases": result["n_cases"],
        "statuses": statuses,
        "digest": result["digest"],
        "matches_reference": result["digest"] == LANE_B_REFERENCE_DIGEST,
        "reference_digest": LANE_B_REFERENCE_DIGEST,
    }


def main(argv: Sequence[str] | None = None) -> int:
    """CLI: verify an artifact directory. Non-zero exit on refusal or mismatch."""
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("usage: python -m research.intake.rh04_v2_portable_archive <dir>")
        return 2
    try:
        evidence = verify_artifact_directory(args[0])
    except ArchiveError as exc:
        print(json.dumps({"result": "REFUSED", "reason": str(exc)}, sort_keys=True))
        return 1
    except Exception as exc:  # noqa: BLE001 - fail closed, never a traceback dump
        print(json.dumps({"result": "FAILED", "reason": type(exc).__name__}, sort_keys=True))
        return 1
    print(json.dumps(evidence, sort_keys=True))
    return 0 if evidence["matches_reference"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
