"""Deterministic fixture arithmetic only — NOT a model or an XAI library.

The SHA-256 offsets reproduce the approved pack's synthetic, non-clinical
semantics for arbitrary valid mock inputs. No fitting, SHAP/LIME computation,
dataset access, prediction validity or clinical direction is implied.

This module is reachable only through
:class:`backend.app.inference.mock_synthetic.MockSyntheticProvider`, which is
the single CAD inference provider the application can construct. It is not a
provider itself and must not be called from runtime state directly.
"""

from __future__ import annotations

import copy
import hashlib
import math
from typing import Any

from .canonical import canonical_json
from .contracts import ContractFiles


def synthetic_offset(feature_id: str, value: Any) -> float:
    digest = hashlib.sha256(f"{feature_id}|{canonical_json(value)}".encode("utf-8")).digest()
    return round((int.from_bytes(digest[:4], "big") % 11) * 0.01 - 0.05, 2)


def build_prediction(
    contracts: ContractFiles,
    model: dict[str, Any],
    provided: dict[str, Any],
    missing_optional: list[str],
    request_id: str,
    audit_id: str,
) -> dict[str, Any]:
    if model["explanation_method"] != "tree_shap":
        raise RuntimeError("Only synthetic SHAP-shaped offsets are implemented.")
    calibration = model.get("calibration")
    template = contracts.calibrated_template if calibration else contracts.prediction_template
    response = copy.deepcopy(template)
    for field in (
        "model_id", "preprocessing_id", "calibration_id", "feature_schema_id",
        "explanation_config_id", "validation_status", "model_performance_ref",
    ):
        response[field] = model[field]
    contributions = [
        {
            "feature": name, "value": item["value"], "unit": item["unit"],
            "shap": synthetic_offset(name, item["value"]),
        }
        for name, item in sorted(provided.items())
    ]
    contributions.sort(key=lambda item: (-abs(item["shap"]), item["feature"]))
    for rank, contribution in enumerate(contributions, 1):
        contribution["rank"] = rank
    base_value = float(model["base_value"])
    computed_sum = base_value + sum(item["shap"] for item in contributions)
    margin = round(computed_sum, 6)
    score = response["score"]
    if calibration:
        score["value"] = round(
            1 / (1 + math.exp(-(calibration["slope"] * margin + calibration["intercept"]))), 6
        )
        score["raw_margin"] = margin
        score["calibration"] = {
            key: copy.deepcopy(calibration[key])
            for key in ("method", "calibration_id", "cohort_context")
        }
    else:
        score["value"] = margin
    explanation = response["explanation"]
    explanation.update(
        base_value=base_value,
        contributions=contributions,
        synthetic=True,
        sum_check={
            "applicable": True,
            "margin": margin,
            "computed_sum": round(computed_sum, 6),
            "tolerance": 1e-6,
            "passed": abs(computed_sum - margin) <= 1e-6,
            "margin_source": "score.raw_margin" if calibration else "score.value",
        },
    )
    response.update(
        request_id=request_id,
        audit_id=audit_id,
        idempotent_replay=False,
        missing_features=missing_optional,
        warnings=[f"imputed_feature:{name}" for name in missing_optional],
    )
    response["provenance"]["artifact_hashes"] = {
        "model": model["artifact_sha256"], "preprocessing": model["preprocessing_sha256"],
        **({"calibration": model["calibration_sha256"]} if model.get("calibration_sha256") else {}),
    }
    return response
