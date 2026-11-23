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

import hashlib
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
        archive["training_identity"],
        ("n_training_rows", "selected_hyperparameters", "split_sha256"),
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
)


def preprocessing_sha256(preprocessing: Mapping[str, Any]) -> str:
    return _sha256(canonical_bytes(preprocessing))


def training_identity_sha256(training_identity: Mapping[str, Any]) -> str:
    return _sha256(canonical_bytes(training_identity))


def calibration_sha256(calibration: Mapping[str, Any]) -> str:
    return _sha256(canonical_bytes(calibration))


def fold_ensemble_sha256(ensemble: Sequence[Mapping[str, Any]]) -> str:
    return _sha256(canonical_bytes(list(ensemble)))


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

    return {
        "schema_version": ARCHIVE_SCHEMA,
        "protocol_id": ARCHIVE_PROTOCOL_ID,
        "sentinel": ARCHIVE_SENTINEL,
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
        },
    }


def build_manifest(
    archives: Mapping[str, Mapping[str, Any]], *, reference_id: str
) -> dict[str, Any]:
    """Build the *independent* trusted manifest for a set of archives.

    Produced by an exporter/reviewer role, never by the verifier. It records
    every expected value so verification never reads an expectation back out of
    the artifact under test.
    """
    routes: dict[str, Any] = {}
    for route, archive in archives.items():
        body = archive
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
        }
    return {
        "manifest_schema": MANIFEST_SCHEMA,
        "protocol_id": ARCHIVE_PROTOCOL_ID,
        "reference_id": reference_id,
        "key_label": FIXTURE_KEY_LABEL,
        "routes": routes,
        "case_ids": [],
    }


# ---------------------------------------------------------------------------
# The facade adapter: execute the real pipeline with a portable artifact
# ---------------------------------------------------------------------------

#: The one facade function this module substitutes. It is the single point where
#: the registered pipeline transitions from verified metadata to a deserialised
#: model, and it is already the established test seam in this repository
#: (``tests/experiments/test_offline_fixture_pack.py`` patches exactly it).
SEAM_NAME: Final[str] = "_load_artifact"


class _PortableLoadedArtifact:
    """Mirror of the facade's loaded-artifact record, built without pickle."""

    def __init__(self, *, predictor: Any, descriptor: Any, capabilities: Any,
                 model_family: str, signing_key_provided: bool) -> None:
        self.predictor = predictor
        self.descriptor = descriptor
        self.capabilities = capabilities
        self.model_family = model_family
        self.signing_key_provided = signing_key_provided

    def safe_block(self) -> dict[str, Any]:
        """Reuse the project's own path-free artifact identity block.

        The block is a property of the *verified bundle descriptor*, not of how
        the estimator was obtained, so the registered implementation is reused
        unchanged rather than re-derived here.
        """
        register = getattr(self, "_safe_block_impl", None)
        if register is None:  # pragma: no cover - defensive
            raise ArchiveError("safe_block implementation was not bound")
        return register()


def _load_artifact_from_archive(
    facade: Any,
    archive: Mapping[str, Any],
    *,
    trusted_local_root: Any,
    signing_key: bytes | None,
):
    """Stand in for ``facade._load_artifact`` using a verified portable archive.

    The registered sequence is preserved and re-executed here:

    1. verify the producer bundle (containment, ACLs, sibling digests, HMAC),
    2. synthetic-provenance / execution-profile gate,
    3. registry identity cross-check against the verified manifest,
    4. request-versus-artifact agreement,
    5. capabilities from verified JSON,
    6. **then** obtain the estimator -- here by rehydration from arrays rather
       than ``joblib.load``.

    Steps 1-5 run the project's own code unchanged. Only step 6 differs, which is
    exactly the property the portable lane is meant to establish.
    """
    from ai.calibration import OofLogisticCalibrator
    from ai.inference import ResearchCadPredictor
    from ai.packaging import (
        CALIBRATION_FILENAME,
        PREPROCESSING_FILENAME,
        SHAP_BG_FILENAME,
        verify_trusted_local_bundle,
    )
    from ai.preprocessing import FoldSafeClinicalPreprocessor
    from ai.cli import assert_cli_predict_supported
    from ai.research_registry import (
        ResearchRegistryError,
        assert_artifact_identity,
        derive_artifact_capabilities,
    )
    from ai.explainability import ShapBackgroundReference

    request = _load_artifact_from_archive._request
    binding = _load_artifact_from_archive._binding
    panel = _load_artifact_from_archive._panel
    source = request.model_source
    entry = binding.entry
    Refusal = facade._Refusal
    try:
        descriptor = verify_trusted_local_bundle(
            source.bundle_dir,
            trusted_local_root=trusted_local_root,
            signing_key=signing_key,
        )
        assert_cli_predict_supported(descriptor.manifest)
        model_family = assert_artifact_identity(descriptor.manifest, entry)
        facade._assert_request_matches_artifact(request, descriptor.manifest, entry)
        calibration_doc = facade._read_verified_json(descriptor, CALIBRATION_FILENAME)
        calibrator = OofLogisticCalibrator.from_json_dict(calibration_doc)
        capabilities = derive_artifact_capabilities(
            descriptor.manifest,
            entry=entry,
            calibrator=calibrator,
            background_document=facade._read_verified_json(descriptor, SHAP_BG_FILENAME),
            model_family=model_family,
        )
        preprocessor = FoldSafeClinicalPreprocessor.from_json_dict(
            facade._read_verified_json(descriptor, PREPROCESSING_FILENAME),
            expected_panel=descriptor.panel,
        )
        background = ShapBackgroundReference.from_json_dict(
            facade._read_verified_json(descriptor, SHAP_BG_FILENAME),
            preprocessor=preprocessor,
            require_synthetic=True,
            is_authorized_research_bundle=False,
        )
        estimator = rehydrate(archive)
        from ai.training import FoldEnsembleMember

        members = []
        for index, spec in enumerate(archive["fold_ensemble"]):
            member_pre = FoldSafeClinicalPreprocessor.from_json_dict(
                spec["preprocessing"], expected_panel=descriptor.panel
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
            estimator=estimator,
            calibrator=calibrator,
            shap_background=background,
            fold_ensemble=tuple(members),
        )
    except Refusal:
        raise
    except ResearchRegistryError as exc:
        raise Refusal(exc.code, stage="artifact", field_name=exc.field, panel=panel) from exc
    except ArchiveError:
        raise
    except Exception as exc:  # noqa: BLE001 - never leak exception text in a response
        # The response stays generic, but the cause is preserved on the exception
        # chain so an operator can diagnose it without exposing it to a caller.
        raise Refusal("bundle_verification_failed", stage="artifact", panel=panel) from exc

    if (
        predictor.model_id != entry.model_id
        or predictor.model_version != entry.model_version
        or predictor.panel.panel_id != entry.panel_id
        or predictor.execution_profile != entry.execution_profile
        or predictor.model_family != archive["model"]["family"]
    ):
        raise Refusal("artifact_identity_mismatch", stage="artifact", panel=panel)
    loaded = _PortableLoadedArtifact(
        predictor=predictor,
        descriptor=descriptor,
        capabilities=capabilities,
        model_family=model_family,
        signing_key_provided=signing_key is not None,
    )
    # Bind the registered implementation of the identity block; it only reads
    # the verified descriptor, so it is valid for a rehydrated model too.
    def _safe_block() -> dict[str, Any]:
        class _DescriptorOnly:
            descriptor = loaded.descriptor
            signing_key_provided = loaded.signing_key_provided

        return facade._LoadedArtifact.safe_block(_DescriptorOnly())  # type: ignore[arg-type]

    loaded._safe_block_impl = _safe_block
    return loaded


def _seam_adapter(facade: Any, archive: dict[str, Any]):
    """Return a drop-in replacement for ``facade._load_artifact``."""

    def load(request, binding, panel):
        _load_artifact_from_archive._request = request
        _load_artifact_from_archive._binding = binding
        _load_artifact_from_archive._panel = panel
        source = request.model_source
        return _load_artifact_from_archive(
            facade,
            archive,
            trusted_local_root=source.trusted_local_root,
            signing_key=source.signing_key,
        )

    return load


class PortableReplay:
    """Context manager: run the registered facade with a portable artifact.

    Only the model-transition seam is substituted. Request parsing, ordered
    validation, route resolution, source binding, abstention, refusal,
    unavailable and error handling all remain the facade's own code.
    """

    def __init__(self, facade: Any, archives: Mapping[str, Mapping[str, Any]]) -> None:
        self._facade = facade
        self._archives = dict(archives)
        self._original = None
        self._active_route: str | None = None

    def select(self, route: str) -> None:
        self._active_route = route

    def __enter__(self) -> "PortableReplay":
        self._original = getattr(self._facade, SEAM_NAME)

        def dispatch(request, binding, panel):
            route = request.route_id
            if route not in self._archives:
                raise self._facade._Refusal(
                    "portable_archive_absent_for_route", stage="artifact"
                )
            return _seam_adapter(self._facade, self._archives[route])(
                request, binding, panel
            )

        setattr(self._facade, SEAM_NAME, dispatch)
        return self

    def __exit__(self, *exc: object) -> None:
        setattr(self._facade, SEAM_NAME, self._original)


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


def execute_case(facade: Any, request: Mapping[str, Any], replay: "PortableReplay",
                 *, model_source: Any) -> dict[str, Any]:
    """Execute one registered case through the facade and export the response."""
    with replay:
        response = facade.run_offline_research_inference_from_document(
            dict(request), model_source=model_source
        )
    return shape_response(response)


def rehydrate_member(spec: Mapping[str, Any]):
    """Rehydrate one outer-fold estimator from its declarative representation."""
    pseudo = {
        "model": {
            "family": spec["model_family"],
            "classes": [0, 1],
            "representation": spec["representation"],
        },
        "preprocessing": spec["preprocessing"],
    }
    return rehydrate(pseudo)
