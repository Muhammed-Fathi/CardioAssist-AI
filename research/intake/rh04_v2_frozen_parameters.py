"""RH-04 V2 — Path B: integrity-bound frozen synthetic parameters (candidate).

Scope
-----
Isolated candidate (`D-V2-7`, **proposed** contract amendment, not ratified).
Synthetic only. No production import path.

Path A vs Path B
----------------
* **Path A** — refit the synthetic model every time. Deterministic by
  declaration, but measured at 15.87 s for a 200x10 problem.
* **Path B** — freeze the parameters as integrity-bound data and only score.
  Measured at 0.03 s.

This module implements the Path B round trip *and* the integrity checks that
make it meaningful. The point is not that freezing is faster; it is that a
frozen artifact is only usable if it can prove what it is: which source, which
feature contract, which family, which training inputs, which protocol version.

Deliberately NOT done
--------------------
Path B does **not** replace the accepted regeneration requirement. It is an
alternative architecture offered for owner review (`D-V2-7`). Until ratified,
Path A remains the only path that produces a reference.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Final

FROZEN_SCHEMA: Final[str] = "cardioassist.rh04.frozen_parameters/v1"
FROZEN_SENTINEL: Final[str] = "UNRATIFIED_PATH_B_CANDIDATE_NOT_A_PRODUCTION_ARTIFACT"

#: Fields that must be present and non-empty. A missing one is a stale artifact,
#: not an empty value.
_REQUIRED: Final[tuple[str, ...]] = (
    "schema_version",
    "sentinel",
    "source_id",
    "feature_contract_digest",
    "model_family",
    "training_profile",
    "training_input_digest",
    "split_digest",
    "coefficients",
    "intercept",
    "calibration",
    "protocol_version",
)


class FrozenParameterError(ValueError):
    """Fail-closed refusal: tampered, stale or malformed artifact."""


def _canonical(document: Any) -> bytes:
    return json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _digest(document: Any) -> str:
    return hashlib.sha256(_canonical(document)).hexdigest()


def build_frozen_artifact(
    *,
    source_id: str,
    feature_names: list[str],
    model_family: str,
    training_profile: str,
    training_rows: list[list[float]],
    training_labels: list[int],
    fold_index: list[int],
    coefficients: list[float],
    intercept: float,
    calibration: dict[str, Any],
    protocol_version: str,
) -> dict[str, Any]:
    """Assemble a frozen artifact with every binding needed to verify it later."""
    if model_family not in ("l2_logistic_regression", "prevalence_dummy"):
        # A tree ensemble has no linear coefficient vector; freezing one as if it
        # did would misrepresent the model. Refuse rather than pretend.
        raise FrozenParameterError(
            f"frozen linear parameters are not defined for family {model_family!r}"
        )
    if len(training_rows) != len(training_labels):
        raise FrozenParameterError("training row/label length mismatch")
    if len(fold_index) != len(training_rows):
        raise FrozenParameterError("fold index length mismatch")

    artifact = {
        "schema_version": FROZEN_SCHEMA,
        "sentinel": FROZEN_SENTINEL,
        "source_id": source_id,
        "feature_names": list(feature_names),
        "feature_contract_digest": _digest(list(feature_names)),
        "model_family": model_family,
        "training_profile": training_profile,
        "training_input_digest": _digest(
            {"rows": training_rows, "labels": training_labels}
        ),
        "split_digest": _digest(fold_index),
        "coefficients": list(coefficients),
        "intercept": float(intercept),
        "calibration": dict(calibration),
        "protocol_version": protocol_version,
    }
    artifact["integrity"] = _digest(artifact)
    return artifact


def verify_frozen_artifact(
    artifact: dict[str, Any],
    *,
    expected_feature_names: list[str] | None = None,
    expected_source_id: str | None = None,
    expected_protocol_version: str | None = None,
) -> None:
    """Verify integrity and every declared binding. Raises on any defect."""
    if not isinstance(artifact, dict):
        raise FrozenParameterError("artifact is not a mapping")
    missing = [name for name in _REQUIRED if name not in artifact]
    if missing:
        raise FrozenParameterError(f"stale artifact: missing {missing}")
    if artifact["sentinel"] != FROZEN_SENTINEL:
        raise FrozenParameterError("artifact is not an unratified Path B candidate")
    if artifact["schema_version"] != FROZEN_SCHEMA:
        raise FrozenParameterError("unexpected frozen schema version")

    recorded = artifact.get("integrity")
    body = {key: value for key, value in artifact.items() if key != "integrity"}
    if recorded != _digest(body):
        raise FrozenParameterError("artifact integrity mismatch (tampered)")

    if _digest(artifact["feature_names"]) != artifact["feature_contract_digest"]:
        raise FrozenParameterError("feature contract digest mismatch")

    if expected_feature_names is not None:
        if artifact["feature_names"] != list(expected_feature_names):
            raise FrozenParameterError("feature contract drift: wrong panel or order")
    if expected_source_id is not None and artifact["source_id"] != expected_source_id:
        raise FrozenParameterError("stale binding: wrong source")
    if expected_protocol_version is not None:
        if artifact["protocol_version"] != expected_protocol_version:
            raise FrozenParameterError("stale binding: wrong protocol version")

    coefficients = artifact["coefficients"]
    if not isinstance(coefficients, list) or not coefficients:
        raise FrozenParameterError("malformed coefficients")
    if len(coefficients) != len(artifact["feature_names"]):
        raise FrozenParameterError("coefficient count does not match the panel")
    for value in coefficients + [artifact["intercept"]]:
        if not isinstance(value, float) or value != value or value in (
            float("inf"),
            float("-inf"),
        ):
            raise FrozenParameterError("non-finite parameter")


def score_with_frozen(
    artifact: dict[str, Any],
    rows: list[list[float]],
    *,
    expected_feature_names: list[str] | None = None,
) -> list[float]:
    """Score through the declared exact scorer, after full verification."""
    from research.intake import rh04_v2_deterministic_upstream as upstream

    verify_frozen_artifact(artifact, expected_feature_names=expected_feature_names)
    for row in rows:
        if len(row) != len(artifact["coefficients"]):
            raise FrozenParameterError("row width does not match the frozen panel")
    return [
        upstream.score_as_float(score)
        for score in upstream.exact_linear_scores(
            artifact["coefficients"], rows, artifact["intercept"]
        )
    ]
