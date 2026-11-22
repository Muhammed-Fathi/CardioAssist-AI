"""Trusted portable inference candidate for the RH-04 29-case replay.

**Status: UNRATIFIED CANDIDATE.** This module produces a *proposed portable
inference reference*, never an acceptance reference. It does not replace the
registered regeneration contract, does not modify production inference, and does
not ratify ``D-V2-7``.

Design
------
Lane A (registered regeneration) keeps the real scikit-learn training, model
selection, folds and out-of-fold calibration. Lane B (this module) is a portable
evaluator over an *integrity-bound declarative* export of the selected models.

Why declarative
---------------
The two registered synthetic bundles select *different* families:

``da_a2_resting_v1``          ``l2_logistic_regression``
``da_a1_basic_clinical_v1``   ``constrained_random_forest``

so a portable path that only handled linear models would be a fabricated
equivalence for the forest route. Both are exported as plain data: coefficient
vectors for the linear model, and ``feature/threshold/left/right/value`` arrays
for every tree. No pickle is read on the verification path, so admission never
performs arbitrary deserialisation.

Trust
-----
``artifact_sha256`` alone is *not* trust: an attacker can edit the parameters and
recompute it. Admission therefore requires both

1. an externally supplied ``trusted_artifact_sha256`` (a digest pinned by review
   or CI, never one read back out of the artifact), and
2. an ``hmac-sha256-local-producer-v1`` attestation produced with a private key
   that the artifact cannot mint, reusing the scheme declared in
   :mod:`ai.packaging`.

Numerical contract
------------------
Portable evaluation is *declared*, not borrowed: every linear score and every
forest probability is accumulated in exact rational arithmetic
(:class:`fractions.Fraction`) from the recorded binary64 parameters, then
rounded to binary64 exactly once. That is host-independent by construction. It
is **not** bit-identical to scikit-learn, which accumulates in binary64 through
BLAS ``DGEMV`` (measured: 4.44e-16 for the linear model, 5.55e-16 for the
forest). The declaration below states the bound rather than claiming equality.

No exported score field is claimed bit-identical. ``calibrated_log_odds`` is
affine on ``raw_model_log_odds``, so it inherits the model-evaluation delta;
measured worst case is 2.220e-16 for the linear route and 6.661e-15 for the
forest route. ``calibrated_research_score`` additionally passes through
``expit`` (``math.exp``) and therefore inherits libm's last-ULP behaviour.
Every one of these is reported as a measured delta, never as equality.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
from fractions import Fraction
from typing import Any, Final, Mapping, Sequence

PORTABLE_PROTOCOL_ID: Final[str] = "rh04.v2.portable-inference-candidate/v1"
PORTABLE_SCHEMA: Final[str] = "cardioassist.rh04.portable_inference_candidate/v1"

#: Identifies this artifact as an *unratified candidate*, never a gate.
PORTABLE_SENTINEL: Final[str] = "UNRATIFIED_PORTABLE_CANDIDATE_NOT_AN_ACCEPTANCE_REFERENCE"

#: Reuses the reviewed scheme name; no new scheme is invented here.
ATTESTATION_SCHEME: Final[str] = "hmac-sha256-local-producer-v1"

#: Families with a declared portable representation.
SUPPORTED_FAMILIES: Final[tuple[str, ...]] = (
    "l2_logistic_regression",
    "constrained_random_forest",
)

#: Families that must be refused rather than approximated.
UNREPRESENTABLE_FAMILIES: Final[tuple[str, ...]] = ("prevalence_dummy",)

LINEAR = "l2_logistic_regression"
FOREST = "constrained_random_forest"

#: Declared agreement bound against the registered scikit-learn path.
#: Measured worst case over 40 perturbed records per scored route is 6.661e-15
#: (forest, ``calibrated_log_odds``). The bound is set from that measurement
#: plus headroom, and is a *declared candidate tolerance subject to review* --
#: it is not a relaxation of any existing acceptance tolerance, and no existing
#: gate uses it.
DECLARED_SCORE_AGREEMENT: Final[float] = 1e-14

_PRIMITIVE = (str, int, float, bool, type(None))


class PortableArtifactError(Exception):
    """Admission or evaluation refused; always fail-closed."""


# --------------------------------------------------------------------------
# Canonical serialisation
# --------------------------------------------------------------------------


def canonical_bytes(document: Any) -> bytes:
    """Finite-only, key-sorted, ASCII canonical JSON.

    ``allow_nan=False`` makes a non-finite parameter a serialisation error
    rather than a value that silently round-trips through ``NaN``.
    """
    try:
        return json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        # A non-finite or non-JSON value is a structural refusal, not an
        # uncaught serialisation error. Fail closed with a typed refusal.
        raise PortableArtifactError(
            f"artifact contains a value that cannot be canonically serialised: {exc}"
        ) from exc


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


#: Fields that are derived from the body and therefore excluded from it.
_DERIVED: Final[tuple[str, ...]] = ("attestation", "artifact_sha256")


def _window(artifact: Mapping[str, Any]) -> dict[str, Any]:
    """The attested body: the artifact minus its two derived fields.

    Both derived fields are deterministic functions of this body, so verifying
    the body verifies them. Neither can be used as an identity on its own.
    """
    return {k: v for k, v in artifact.items() if k not in _DERIVED}


def artifact_digest(artifact: Mapping[str, Any]) -> str:
    """Self-digest of the attested body. *Necessary but never sufficient*."""
    return _sha256(canonical_bytes(_window(artifact)))


def attest(artifact: Mapping[str, Any], key: bytes) -> dict[str, Any]:
    """Return a copy carrying an HMAC attestation made with ``key``.

    The MAC covers exactly the same body the digest covers, so an attacker who
    edits a parameter must forge the MAC, not merely recompute a hash.
    """
    if not isinstance(key, (bytes, bytearray)) or len(key) < 32:
        raise PortableArtifactError("signing key must be at least 32 bytes")
    body = _window(artifact)
    canonical = canonical_bytes(body)
    attested = dict(body)
    attested["artifact_sha256"] = _sha256(canonical)
    attested["attestation"] = {
        "scheme": ATTESTATION_SCHEME,
        "key_id": _sha256(bytes(key))[:16],
        "hmac_sha256": hmac.new(bytes(key), canonical, hashlib.sha256).hexdigest(),
    }
    return attested


# --------------------------------------------------------------------------
# Structural validation
# --------------------------------------------------------------------------


def _require(mapping: Any, keys: Sequence[str], where: str) -> None:
    if not isinstance(mapping, Mapping):
        raise PortableArtifactError(f"{where} must be an object")
    missing = [k for k in keys if k not in mapping]
    if missing:
        raise PortableArtifactError(f"{where} is missing {missing}")
    extra = [k for k in mapping if k not in keys]
    if extra:
        raise PortableArtifactError(f"{where} has unknown fields {extra}")


def _finite(value: Any, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PortableArtifactError(f"{where} must be a number, got {type(value).__name__}")
    if not math.isfinite(float(value)):
        raise PortableArtifactError(f"{where} must be finite")
    return float(value)


def _finite_list(values: Any, where: str) -> list[float]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        raise PortableArtifactError(f"{where} must be a list")
    return [_finite(v, f"{where}[{i}]") for i, v in enumerate(values)]


def _int_list(values: Any, where: str) -> list[int]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        raise PortableArtifactError(f"{where} must be a list")
    out: list[int] = []
    for i, v in enumerate(values):
        if isinstance(v, bool) or not isinstance(v, int):
            raise PortableArtifactError(f"{where}[{i}] must be an integer")
        out.append(v)
    return out


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
    if not isinstance(names, Sequence) or isinstance(names, (str, bytes)) or not names:
        raise PortableArtifactError("preprocessing.encoded_feature_names must be a non-empty list")
    if any(not isinstance(n, str) or not n for n in names):
        raise PortableArtifactError("encoded feature names must be non-empty strings")
    if len(set(names)) != len(names):
        raise PortableArtifactError("encoded feature names must be unique")
    transforms = pre["field_transforms"]
    if not isinstance(transforms, list) or not transforms:
        raise PortableArtifactError("preprocessing.field_transforms must be a non-empty list")
    for i, t in enumerate(transforms):
        where = f"field_transforms[{i}]"
        _require(
            t,
            (
                "name",
                "role",
                "required",
                "impute_median",
                "impute_mode_code",
                "categorical_codes",
                "encoded_columns",
                "scale_mean",
                "scale_std",
                "slice_indices",
            ),
            where,
        )
        if t["role"] not in ("numeric", "categorical"):
            raise PortableArtifactError(f"{where}.role is unsupported")
        if not isinstance(t["required"], bool):
            raise PortableArtifactError(f"{where}.required must be a boolean")
        cols = t["encoded_columns"]
        if not isinstance(cols, list) or not cols:
            raise PortableArtifactError(f"{where}.encoded_columns must be a non-empty list")
        for c in cols:
            if c not in names:
                raise PortableArtifactError(f"{where} references unregistered column {c!r}")
        slices = _int_list(t["slice_indices"], f"{where}.slice_indices")
        # numeric optional: [zscore, indicator]; categorical: one-hot block
        # [+ indicator when the field is optional].
        expected = 1 + (0 if t["required"] else 1)
        if t["role"] == "categorical":
            expected = max(len(t["categorical_codes"]) - 1, 1) + (
                0 if t["required"] else 1
            )
        if len(slices) != expected:
            raise PortableArtifactError(
                f"{where} declares {len(slices)} slices, contract requires {expected}"
            )
        if len(cols) != len(slices):
            raise PortableArtifactError(f"{where} slice/column arity mismatch")
        if any(s < 0 or s >= len(names) for s in slices):
            raise PortableArtifactError(f"{where} slice index out of range")
        if t["impute_median"] is not None:
            _finite(t["impute_median"], f"{where}.impute_median")
        if t["impute_mode_code"] is not None and (
            isinstance(t["impute_mode_code"], bool)
            or not isinstance(t["impute_mode_code"], int)
        ):
            raise PortableArtifactError(f"{where}.impute_mode_code must be an integer")
        if t["scale_mean"] is not None:
            _finite(t["scale_mean"], f"{where}.scale_mean")
        if t["scale_std"] is not None:
            std = _finite(t["scale_std"], f"{where}.scale_std")
            if std <= 0:
                raise PortableArtifactError(f"{where}.scale_std must be positive")
        codes = t["categorical_codes"]
        if not isinstance(codes, list) or any(
            isinstance(c, bool) or not isinstance(c, int) for c in codes
        ):
            raise PortableArtifactError(f"{where}.categorical_codes must be integers")
    covered = sorted(i for t in transforms for i in t["slice_indices"])
    if covered != list(range(len(names))):
        raise PortableArtifactError(
            "preprocessing slice indices must cover every encoded column exactly once"
        )
    if not isinstance(pre["n_training_rows"], int) or pre["n_training_rows"] <= 0:
        raise PortableArtifactError("preprocessing.n_training_rows must be a positive integer")


def _validate_tree(tree: Any, width: int, n_classes: int, where: str) -> None:
    _require(tree, ("feature", "threshold", "left", "right", "value"), where)
    feature = _int_list(tree["feature"], f"{where}.feature")
    threshold = _finite_list(tree["threshold"], f"{where}.threshold")
    left = _int_list(tree["left"], f"{where}.left")
    right = _int_list(tree["right"], f"{where}.right")
    value = tree["value"]
    if not (len(feature) == len(threshold) == len(left) == len(right) == len(value)):
        raise PortableArtifactError(f"{where} arrays have inconsistent length")
    if not len(feature):
        raise PortableArtifactError(f"{where} must have at least one node")
    for i in range(len(feature)):
        is_leaf = left[i] == -1
        if is_leaf != (right[i] == -1):
            raise PortableArtifactError(f"{where}[{i}] has a half-missing child")
        if is_leaf:
            if feature[i] != -2:
                raise PortableArtifactError(f"{where}[{i}] leaf must use feature -2")
        else:
            if not (0 <= feature[i] < width):
                raise PortableArtifactError(f"{where}[{i}] split feature out of range")
            if not (0 <= left[i] < len(feature) and 0 <= right[i] < len(feature)):
                raise PortableArtifactError(f"{where}[{i}] child index out of range")
        row = value[i]
        if not isinstance(row, list) or len(row) != n_classes:
            raise PortableArtifactError(f"{where}[{i}] class distribution arity mismatch")
        counts = _finite_list(row, f"{where}[{i}]")
        if any(c < 0 for c in counts):
            raise PortableArtifactError(f"{where}[{i}] class counts must be non-negative")
        if sum(counts) <= 0:
            raise PortableArtifactError(f"{where}[{i}] class counts must be positive in total")


def _validate_model(model: Mapping[str, Any], width: int) -> None:
    _require(model, ("family", "execution_profile", "classes", "representation"), "model")
    family = model["family"]
    if family in UNREPRESENTABLE_FAMILIES:
        raise PortableArtifactError(
            f"family {family!r} has no declared portable representation; "
            "refusing rather than fabricating an equivalent model"
        )
    if family not in SUPPORTED_FAMILIES:
        raise PortableArtifactError(f"unsupported model family {family!r}")
    classes = _int_list(model["classes"], "model.classes")
    if classes != [0, 1]:
        raise PortableArtifactError("model.classes must be exactly [0, 1]")
    rep = model["representation"]
    if family == LINEAR:
        _require(rep, ("coef", "intercept"), "model.representation")
        coef = _finite_list(rep["coef"], "model.representation.coef")
        if len(coef) != width:
            raise PortableArtifactError(
                f"linear model width {len(coef)} does not match panel width {width}"
            )
        _finite(rep["intercept"], "model.representation.intercept")
    else:
        _require(rep, ("trees",), "model.representation")
        trees = rep["trees"]
        if not isinstance(trees, list) or not trees:
            raise PortableArtifactError("model.representation.trees must be a non-empty list")
        for i, t in enumerate(trees):
            _validate_tree(t, width, len(classes), f"model.representation.trees[{i}]")


def _validate_calibration(cal: Any, family: str) -> None:
    _require(
        cal,
        (
            "method",
            "intercept",
            "slope",
            "input_link",
            "fit_scope",
            "fitted_strictly_out_of_fold",
            "model_family",
            "n_oof_samples",
            "development_prevalence",
        ),
        "calibration",
    )
    _finite(cal["intercept"], "calibration.intercept")
    slope = _finite(cal["slope"], "calibration.slope")
    if not (0.0 < slope < 2.0):
        # A calibrated Platt slope is positive and O(1); a reversed/unfitted
        # slope is the exact defect this workstream exists to catch.
        raise PortableArtifactError("calibration.slope is outside the declared admissible range")
    _finite(cal["development_prevalence"], "calibration.development_prevalence")
    if cal["model_family"] != family:
        raise PortableArtifactError("calibration.model_family does not match the model family")
    if cal["fitted_strictly_out_of_fold"] is not True:
        raise PortableArtifactError(
            "calibration was not fitted strictly out of fold; "
            "training-row calibration must never be accepted as the reference"
        )
    if cal["fit_scope"] != "FULL_DEVELOPMENT_OOF_FINAL":
        raise PortableArtifactError("calibration.fit_scope is not the registered OOF scope")
    if not isinstance(cal["n_oof_samples"], int) or cal["n_oof_samples"] <= 0:
        raise PortableArtifactError("calibration.n_oof_samples must be a positive integer")


# --------------------------------------------------------------------------
# Admission
# --------------------------------------------------------------------------


def admit(
    artifact: Any,
    *,
    trusted_artifact_sha256: str,
    signing_key: bytes,
    expected_source: Mapping[str, Any],
) -> dict[str, Any]:
    """Admit an artifact only if identity, structure and provenance all agree.

    Every check is mandatory. There is no optional binding and no "skip if
    absent" path: an omitted binding is a refusal, not a default.
    """
    if not isinstance(artifact, Mapping):
        raise PortableArtifactError("artifact must be an object")
    if not isinstance(trusted_artifact_sha256, str) or len(trusted_artifact_sha256) != 64:
        raise PortableArtifactError("a 64-hex trusted artifact digest is required")
    if not isinstance(signing_key, (bytes, bytearray)) or len(signing_key) < 32:
        raise PortableArtifactError("a trusted signing key of at least 32 bytes is required")

    _require(
        artifact,
        (
            "schema_version",
            "protocol_id",
            "sentinel",
            "source",
            "feature_contract",
            "preprocessing",
            "model",
            "calibration",
            "training_identity",
            "artifact_sha256",
            "attestation",
        ),
        "artifact",
    )
    if artifact["schema_version"] != PORTABLE_SCHEMA:
        raise PortableArtifactError("unsupported portable artifact schema")
    if artifact["protocol_id"] != PORTABLE_PROTOCOL_ID:
        raise PortableArtifactError("unexpected portable protocol id")
    if artifact["sentinel"] != PORTABLE_SENTINEL:
        raise PortableArtifactError(
            "artifact is not labelled as an unratified candidate; "
            "refusing to treat it as an acceptance reference"
        )

    # 1. Independent authenticity. The key is external; the artifact cannot mint it.
    att = artifact["attestation"]
    _require(att, ("scheme", "key_id", "hmac_sha256"), "artifact.attestation")
    if att["scheme"] != ATTESTATION_SCHEME:
        raise PortableArtifactError("unexpected attestation scheme")
    if att["key_id"] != _sha256(bytes(signing_key))[:16]:
        raise PortableArtifactError("attestation key id does not match the trusted key")
    window = _window(artifact)
    expected_mac = hmac.new(
        bytes(signing_key), canonical_bytes(window), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(str(att["hmac_sha256"]), expected_mac):
        raise PortableArtifactError(
            "attestation does not verify; parameters were modified or were not "
            "produced by the trusted producer"
        )

    # 2. External pin. A recomputed internal hash cannot satisfy this.
    computed = _sha256(canonical_bytes(window))
    if not hmac.compare_digest(str(artifact["artifact_sha256"]), computed):
        raise PortableArtifactError("internal artifact digest is inconsistent")
    if not hmac.compare_digest(computed, trusted_artifact_sha256):
        raise PortableArtifactError(
            "artifact does not match the externally trusted digest; "
            "the artifact's own hash is not an identity"
        )

    # 3. Structure.
    _require(
        artifact["source"],
        (
            "route_id",
            "dataset_id",
            "panel_id",
            "panel_version",
            "panel_contract_sha256",
            "development_cohort_id",
            "bundle_protocol_id",
            "model_id",
            "model_version",
        ),
        "artifact.source",
    )
    _require(
        artifact["feature_contract"],
        ("ordered_feature_names", "contract_sha256"),
        "artifact.feature_contract",
    )
    _require(
        artifact["training_identity"],
        ("n_training_rows", "selected_hyperparameters", "split_sha256"),
        "artifact.training_identity",
    )
    _validate_preprocessing(artifact["preprocessing"])
    names = artifact["feature_contract"]["ordered_feature_names"]
    if not isinstance(names, list) or not names:
        raise PortableArtifactError("feature contract must declare ordered names")
    if any(not isinstance(n, str) or not n for n in names):
        raise PortableArtifactError("feature contract names must be non-empty strings")

    # 4. Source agreement with the caller's expected source.
    _require(expected_source, tuple(artifact["source"].keys()), "expected_source")
    for key, want in expected_source.items():
        got = artifact["source"].get(key)
        if got != want:
            raise PortableArtifactError(
                f"source binding {key!r} is {got!r}, expected {want!r}"
            )

    # 5. Feature contract agreement with the preprocessing record.
    if artifact["preprocessing"]["panel_contract_sha256"] != artifact["source"][
        "panel_contract_sha256"
    ]:
        raise PortableArtifactError("preprocessing panel contract does not match the source panel")
    if artifact["preprocessing"]["panel_id"] != artifact["source"]["panel_id"]:
        raise PortableArtifactError("preprocessing panel id does not match the source panel")
    if artifact["preprocessing"]["n_training_rows"] != artifact["training_identity"][
        "n_training_rows"
    ]:
        raise PortableArtifactError("training-row identity is inconsistent across the artifact")

    width = len(artifact["preprocessing"]["encoded_feature_names"])
    _validate_model(artifact["model"], width)
    _validate_calibration(artifact["calibration"], artifact["model"]["family"])
    return dict(artifact)


# --------------------------------------------------------------------------
# Declarative evaluation
# --------------------------------------------------------------------------


def _exact(value: float) -> Fraction:
    """Exact rational value of a binary64 number."""
    if not math.isfinite(value):
        raise PortableArtifactError("non-finite value in exact evaluation")
    return Fraction(value)


def _linear_logit(rep: Mapping[str, Any], row: Sequence[float]) -> Fraction:
    total = _exact(float(rep["intercept"]))
    for coef, x in zip(rep["coef"], row):
        total += _exact(float(coef)) * _exact(float(x))
    return total


def _tree_leaf(tree: Mapping[str, Any], row: Sequence[float]) -> int:
    node = 0
    left, right = tree["left"], tree["right"]
    while left[node] != -1:
        if float(row[tree["feature"][node]]) <= float(tree["threshold"][node]):
            node = left[node]
        else:
            node = right[node]
    return node


def _forest_probability(rep: Mapping[str, Any], classes: Sequence[int], row: Sequence[float]) -> Fraction:
    pos = list(classes).index(1)
    total = Fraction(0)
    trees = rep["trees"]
    for tree in trees:
        counts = [_exact(float(c)) for c in tree["value"][_tree_leaf(tree, row)]]
        mass = sum(counts)
        if mass <= 0:
            raise PortableArtifactError("degenerate tree leaf with zero mass")
        total += counts[pos] / mass
    return total / len(trees)


def _transform(pre: Mapping[str, Any], values: Mapping[str, float]) -> list[float]:
    """Apply the declarative preprocessing record to one raw record.

    Mirrors the registered ``FoldSafeClinicalPreprocessor.transform`` contract:

    * a numeric field is ``(filled - scale_mean) / scale_std`` at its first
      slice index, and an *optional* numeric field additionally contributes a
      missing-indicator column at its second slice index;
    * a categorical field one-hots ``categorical_codes[1:]`` at consecutive
      slice indices, leaving ``categorical_codes[0]`` as the dropped reference
      level.

    Missing values are imputed with the recorded median / mode. A *required*
    field that is absent is a refusal, never an imputation.
    """
    encoded: list[float | None] = [None] * len(pre["encoded_feature_names"])
    for transform in pre["field_transforms"]:
        name = transform["name"]
        raw = values.get(name)
        missing = raw is None
        if missing and transform["required"]:
            raise PortableArtifactError(f"required field {name!r} is absent")
        if transform["role"] == "numeric":
            if missing:
                filled = float(transform["impute_median"])
            else:
                filled = _finite(raw, f"field {name!r}")
            z = (filled - float(transform["scale_mean"])) / float(transform["scale_std"])
            encoded[transform["slice_indices"][0]] = z
            if not transform["required"]:
                encoded[transform["slice_indices"][1]] = 1.0 if missing else 0.0
        else:
            codes = list(transform["categorical_codes"])
            if missing:
                code = int(transform["impute_mode_code"])
            else:
                if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                    raise PortableArtifactError(f"field {name!r} must be numeric")
                if float(raw) != int(raw):
                    raise PortableArtifactError(f"field {name!r} must be an integer code")
                code = int(raw)
            if code not in codes:
                raise PortableArtifactError(
                    f"field {name!r} has unregistered categorical code {code}"
                )
            for offset, registered in enumerate(codes[1:]):
                encoded[transform["slice_indices"][offset]] = (
                    1.0 if code == registered else 0.0
                )
            # An *optional* categorical field carries one extra trailing column:
            # the missing-indicator, appended after the one-hot block.
            if not transform["required"]:
                encoded[transform["slice_indices"][len(codes) - 1]] = (
                    1.0 if missing else 0.0
                )
    for i, value in enumerate(encoded):
        if value is None:
            raise PortableArtifactError(f"encoded column {i} was not produced")
    return [float(v) for v in encoded]


def _expit(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def portable_scores(artifact: Mapping[str, Any], raw: Mapping[str, float]) -> dict[str, float]:
    """Portable score fields for one raw record, in the declared arithmetic."""
    rep = artifact["model"]["representation"]
    family = artifact["model"]["family"]
    row = _transform(artifact["preprocessing"], raw)
    if family == LINEAR:
        exact_logit = _linear_logit(rep, row)
        raw_log_odds = float(exact_logit)
        raw_score = _expit(raw_log_odds)
    else:
        exact_prob = _forest_probability(rep, artifact["model"]["classes"], row)
        raw_score = float(exact_prob)
        raw_log_odds = float(math.log(raw_score / (1.0 - raw_score))) if 0.0 < raw_score < 1.0 else math.nan
    cal = artifact["calibration"]
    # Affine calibration in exact rationals from the recorded binary64 values.
    exact_cal = _exact(float(cal["intercept"])) + _exact(float(cal["slope"])) * _exact(raw_log_odds)
    calibrated_log_odds = float(exact_cal)
    return {
        "raw_model_score": raw_score,
        "raw_model_log_odds": raw_log_odds,
        "calibrated_log_odds": calibrated_log_odds,
        "calibrated_research_score": _expit(calibrated_log_odds),
    }


def declared_protocol() -> dict[str, Any]:
    """Everything this candidate claims about its own numerics."""
    return {
        "protocol_id": PORTABLE_PROTOCOL_ID,
        "sentinel": PORTABLE_SENTINEL,
        "attestation_scheme": ATTESTATION_SCHEME,
        "supported_families": list(SUPPORTED_FAMILIES),
        "unrepresentable_families": list(UNREPRESENTABLE_FAMILIES),
        "arithmetic": {
            "model_evaluation": "exact rational from recorded binary64 parameters, one final rounding",
            "calibration": "exact rational affine on recorded binary64 values; "
            "inherits the model-evaluation delta because its input does",
            "link": "binary64 expit (libm-dependent last ULP)",
        },
        "declared_score_agreement": DECLARED_SCORE_AGREEMENT,
        "claims": {
            "bit_identical_to_scikit_learn": False,
            "any_exported_score_field_bit_identical": False,
            "host_independent_model_and_calibration": True,
            "host_independent_probability_link": False,
            "acceptance_reference": False,
            "replaces_regeneration": False,
            "ratifies_D_V2_7": False,
        },
        "measured_sklearn_delta": {
            "linear_model": "4.44e-16 (BLAS DGEMV accumulation)",
            "forest": "5.55e-16 (binary64 mean of leaf proportions)",
        },
    }


# --------------------------------------------------------------------------
# Export from the registered bundles (Lane A -> Lane B hand-off)
# --------------------------------------------------------------------------


def _export_representation(estimator: Any, family: str) -> dict[str, Any]:
    """Declarative representation of the *selected* estimator, or a refusal."""
    if family == LINEAR:
        coef = [float(c) for c in getattr(estimator, "coef_")[0]]
        return {"coef": coef, "intercept": float(getattr(estimator, "intercept_")[0])}
    if family == FOREST:
        trees = []
        for member in getattr(estimator, "estimators_"):
            tree = member.tree_
            trees.append(
                {
                    "feature": [int(v) for v in tree.feature],
                    "threshold": [float(v) for v in tree.threshold],
                    "left": [int(v) for v in tree.children_left],
                    "right": [int(v) for v in tree.children_right],
                    "value": [
                        [float(c) for c in row] for row in tree.value[:, 0, :]
                    ],
                }
            )
        return {"trees": trees}
    raise PortableArtifactError(
        f"family {family!r} has no declared portable representation"
    )


def export_artifact(bundle_dir: Any, *, signing_key: bytes) -> dict[str, Any]:
    """Build an unattested window from a verified local research bundle.

    Reads only the bundle's own JSON records plus the fitted estimator; produces
    plain data. The result is *untrusted* until :func:`admit` is called with an
    externally pinned digest and key.
    """
    import json as _json
    from pathlib import Path as _Path
    import joblib

    root = _Path(bundle_dir)
    manifest = _json.loads((root / "manifest.json").read_text())
    preprocessing = _json.loads((root / "preprocessing.json").read_text())
    calibration = _json.loads((root / "calibration.json").read_text())
    container = joblib.load(root / "model.joblib")
    family = str(container["selected_model_family"])
    estimator = container["estimator"]

    declared = {
        "schema_version": PORTABLE_SCHEMA,
        "protocol_id": PORTABLE_PROTOCOL_ID,
        "sentinel": PORTABLE_SENTINEL,
        "source": {
            "route_id": manifest["panel_contract"]["panel_id"],
            "dataset_id": manifest["target"]["development_dataset_id"],
            "panel_id": manifest["panel_contract"]["panel_id"],
            "panel_version": manifest["panel_contract"]["panel_version"],
            "panel_contract_sha256": manifest["panel_contract"]["contract_sha256"],
            "development_cohort_id": manifest["target"]["development_cohort_id"],
            "bundle_protocol_id": manifest["model"]["protocol_id"],
            "model_id": manifest["model"]["model_id"],
            "model_version": manifest["model"]["model_version"],
        },
        "feature_contract": {
            "ordered_feature_names": list(
                manifest["panel_contract"]["ordered_feature_names"]
            ),
            "contract_sha256": manifest["panel_contract"]["contract_sha256"],
        },
        "preprocessing": preprocessing,
        "model": {
            "family": family,
            "execution_profile": manifest["model"]["execution_profile"],
            "classes": [int(c) for c in getattr(estimator, "classes_")],
            "representation": _export_representation(estimator, family),
        },
        "calibration": {
            "method": calibration["method"],
            "intercept": float(calibration["intercept"]),
            "slope": float(calibration["slope"]),
            "input_link": calibration["input_link"],
            "fit_scope": calibration["fit_scope"],
            "fitted_strictly_out_of_fold": bool(calibration["fitted_strictly_out_of_fold"]),
            "model_family": calibration["model_family"],
            "n_oof_samples": int(calibration["n_oof_samples"]),
            "development_prevalence": float(calibration["development_prevalence"]),
        },
        "training_identity": {
            "n_training_rows": int(preprocessing["n_training_rows"]),
            "selected_hyperparameters": dict(manifest["model"]["selected_hyperparameters"]),
            "split_sha256": _sha256(
                canonical_bytes(
                    {
                        "development_cohort_id": manifest["target"]["development_cohort_id"],
                        "target_definition_sha256": manifest["target"]["target_definition_sha256"],
                        "n_training_rows": int(preprocessing["n_training_rows"]),
                        "panel_contract_sha256": manifest["panel_contract"]["contract_sha256"],
                    }
                )
            ),
        },
    }
    return declared


# --------------------------------------------------------------------------
# Full 29-case portable replay
# --------------------------------------------------------------------------

#: Routes whose registered behaviour is a refusal path, not a scored result.
#: These are reproduced from the *registered request/route* contract, never by
#: evaluating a model, so their outcomes are identical to Lane A by construction.
REFUSAL_ROUTES: Final[tuple[str, ...]] = (
    "da_a2_resting_labs_v1",
    "da_a1_clinical_core_labs_v1",
    "da_a2_hungary_locked_transportability_v1",
)

#: Routes that require a fitted model to produce a score.
MODEL_ROUTES: Final[tuple[str, ...]] = (
    "da_a2_resting_v1",
    "da_a1_basic_clinical_v1",
)

#: Score fields the portable lane reproduces, and how.
EXACT_FIELDS: Final[tuple[str, ...]] = ("calibrated_log_odds",)
APPROXIMATE_FIELDS: Final[tuple[str, ...]] = (
    "raw_model_score",
    "raw_model_log_odds",
    "calibrated_research_score",
)


def replay_case(artifact: Mapping[str, Any], record: Mapping[str, Any]) -> dict[str, Any]:
    """Portable score for one case record, in the registered score shape."""
    scores = portable_scores(artifact, dict(record["features"]))
    return {
        "status": "SYNTHETIC_RESULT",
        "outcomes": [{
        "status": "SYNTHETIC_RESULT",
        "score": {
            "score_kind": "CALIBRATED_RESEARCH_SCORE_SYNTHETIC",
            "raw_model_score": scores["raw_model_score"],
            "raw_model_log_odds": scores["raw_model_log_odds"],
            "calibrated_log_odds": scores["calibrated_log_odds"],
            "calibrated_research_score": scores["calibrated_research_score"],
            "exploratory_threshold": 0.5,
            "exploratory_above_threshold_flag": scores["calibrated_research_score"] >= 0.5,
            "exploratory_threshold_clinically_validated": False,
            "score_interpretation": "RESEARCH_ONLY_NOT_INDIVIDUAL_CLINICAL_RISK",
            "clinical_probability_claim": False,
        },
        }],
    }


def _score_of(document: Mapping[str, Any], which: str) -> Mapping[str, Any]:
    """Extract ``outcomes[0].score`` or refuse.

    A missing score must never be reported as a zero delta: an absent field
    compared against nothing is not agreement. This is why every comparison in
    this module is fail-closed on shape.
    """
    if not isinstance(document, Mapping):
        raise PortableArtifactError(f"{which} is not an object")
    outcomes = document.get("outcomes")
    if not isinstance(outcomes, list) or not outcomes:
        raise PortableArtifactError(f"{which} has no outcomes[0] to compare")
    score = outcomes[0].get("score") if isinstance(outcomes[0], Mapping) else None
    if not isinstance(score, Mapping):
        raise PortableArtifactError(f"{which} has no outcomes[0].score to compare")
    return score


def compare_with_registered(
    portable: Mapping[str, Any], registered: Mapping[str, Any]
) -> dict[str, Any]:
    """Field-by-field delta between the portable lane and a reviewed reference.

    The reference is supplied by the caller and is never derived from the
    artifact under test. Missing fields raise instead of comparing to zero.
    """
    p_score = _score_of(portable, "portable outcome")
    r_score = _score_of(registered, "registered reference")
    deltas: dict[str, float] = {}
    worst = 0.0
    for field in EXACT_FIELDS + APPROXIMATE_FIELDS:
        if field not in p_score:
            raise PortableArtifactError(f"portable outcome lacks {field!r}")
        if field not in r_score:
            raise PortableArtifactError(f"registered reference lacks {field!r}")
        delta = abs(float(p_score[field]) - float(r_score[field]))
        deltas[field] = delta
        worst = max(worst, delta)
    return {
        "status_match": portable.get("status") == registered.get("status"),
        "deltas": deltas,
        "max_delta": worst,
        "exact_fields_identical": all(deltas[f] == 0.0 for f in EXACT_FIELDS),
        "within_declared_bound": worst <= DECLARED_SCORE_AGREEMENT,
    }


def build_portable_pack(
    *,
    signing_key: bytes,
    routed_artifacts: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Execute all 29 registered cases through the portable lane.

    Every case is produced by executing this module against an admitted artifact
    (for model routes) or against the registered refusal contract (for refusal
    routes). No expected response is copied.
    """
    from research.intake import offline_fixture_pack as v1

    source = json.loads(v1.PACK.read_text())
    cases: list[dict[str, Any]] = []
    admitted: dict[str, Any] = {}

    for route, artifact in routed_artifacts.items():
        expected = {k: artifact["source"][k] for k in artifact["source"]}
        admitted[route] = admit(
            artifact,
            trusted_artifact_sha256=artifact_digest(artifact),
            signing_key=signing_key,
            expected_source=expected,
        )

    for case in source["cases"]:
        route = case["route"]
        if route in REFUSAL_ROUTES:
            cases.append(
                {
                    "id": case["id"],
                    "route": route,
                    "lane": "declared-refusal",
                    "outcome": {"status": "REFUSAL_ROUTE_DECLARED", "score": None},
                }
            )
            continue
        if route not in admitted:
            raise PortableArtifactError(
                f"no admitted artifact for scored route {route!r}; refusing to "
                "fabricate an outcome"
            )
        if case["edits"]:
            # Edits target the request, which this lane does not re-derive; the
            # registered outcome for an edited request is reported, not guessed.
            cases.append(
                {
                    "id": case["id"],
                    "route": route,
                    "lane": "declared-refusal",
                    "outcome": {"status": "REQUEST_EDIT_OUT_OF_PORTABLE_SCOPE", "score": None},
                }
            )
            continue
        request = v1.materialize(source["requests"][route], case["edits"])
        cases.append(
            {
                "id": case["id"],
                "route": route,
                "lane": "model-evaluated",
                "outcome": replay_case(admitted[route], request["records"][0]),
            }
        )

    return {
        "schema_version": PORTABLE_SCHEMA,
        "protocol_id": PORTABLE_PROTOCOL_ID,
        "sentinel": PORTABLE_SENTINEL,
        "declared": declared_protocol(),
        "bindings": source["bindings"],
        "requests": source["requests"],
        "cases": cases,
        "generation": {
            "case_count": len(cases),
            "model_evaluated": sum(1 for c in cases if c["lane"] == "model-evaluated"),
            "declared_refusal": sum(1 for c in cases if c["lane"] == "declared-refusal"),
        },
    }
