"""RH-04: safe synthetic UCI-412 numerical stage probe (research-only).

Repeats the frozen UCI-412 route *without user files or real data* and emits
only Boolean exact-equality flags and absolute-delta magnitudes.  No fitted
parameters, patient data, model score values, paths or signing keys are printed.
This diagnostic is intentionally NOT a golden comparator or exemption.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import numpy as np

from ai.filesystem_security import ensure_private_directory
from ai.packaging import get_or_create_local_signing_key
from ai.research_facade import LocalSyntheticBundleSource, canonical_response_digest
from ai.report_comparison import ABS_TOL, REL_TOL
from ai.uci412_research import (
    Uci412ResearchModelConfig,
    build_uci412_synthetic_research_model,
)
from research.intake import offline_fixture_pack as fixtures

CASE_ID = "da_a1_basic_clinical_v1"
NUMERIC_FIELDS = (
    "raw_model_score",
    "raw_model_log_odds",
    "calibrated_research_score",
    "calibrated_log_odds",
)


def _same_float(a: object, b: object) -> bool:
    """Deliberately binary64-exact; NaNs fail and booleans cannot pass."""
    return (type(a) is float and type(b) is float
            and math.isfinite(a) and math.isfinite(b) and a.hex() == b.hex())


def _field_observations(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """No input values are included, including in exception messages."""
    out: dict[str, dict[str, Any]] = {}
    for key in NUMERIC_FIELDS:
        want, got = expected.get(key), actual.get(key)
        same = _same_float(want, got)
        finite = (type(want) is float and type(got) is float
                  and math.isfinite(want) and math.isfinite(got))
        out[key] = {"exact_binary64": same}
        if finite and not same:
            out[key]["absolute_delta"] = f"{abs(want - got):.3e}"
            out[key]["within_report_tolerance_diagnostic_only"] = math.isclose(
                want, got, abs_tol=ABS_TOL, rel_tol=REL_TOL
            )
    return out


def _stage_snapshot(root: Path, request: dict[str, Any], expected: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """One source-equivalent build and one complete verified-facade replay."""
    built = build_uci412_synthetic_research_model(
        Uci412ResearchModelConfig.fast(
            package_bundle=True,
            work_root=ensure_private_directory(root / "basic"),
        )
    )
    if (built.bundle_dir is None or built.trusted_root is None
            or built.signing_key_path is None or built.predictor is None):
        raise ValueError("synthetic_bundle_not_created")
    source = LocalSyntheticBundleSource(
        built.bundle_dir, built.trusted_root,
        get_or_create_local_signing_key(built.signing_key_path),
    )
    observed = fixtures.example(request, source)
    if (observed.get("status") != "SYNTHETIC_RESULT"
            or len(observed.get("outcomes", [])) != 1
            or not isinstance(observed["outcomes"][0].get("score"), dict)):
        raise ValueError("synthetic_output_refused_or_malformed")
    score = observed["outcomes"][0]["score"]
    cal_fit = built.run.calibrator
    cal_bundle = built.predictor._calibrator  # diagnostic-only introspection of authenticated artifact
    raw_logit = score.get("raw_model_log_odds")
    calibrated_logit = score.get("calibrated_log_odds")
    stage = {
        "selected_model_family": built.run.selected_model_family,
        "fitted_to_bundle_calibrator_intercept_exact": _same_float(
            float(cal_fit.intercept), float(cal_bundle.intercept)
        ),
        "fitted_to_bundle_calibrator_slope_exact": _same_float(
            float(cal_fit.slope), float(cal_bundle.slope)
        ),
        "calibrated_output_matches_fitted_affine_exact": (
            _same_float(
                calibrated_logit,
                float(cal_fit.transform_log_odds(raw_logit))
            ) if type(raw_logit) is float else False
        ),
        "fields_vs_immutable_fixture": _field_observations(
            expected["outcomes"][0]["score"], score
        ),
        "all_consumer_fields_exact": observed == expected,
    }
    # These numeric values remain in RAM only and are NEVER returned to the JSON emitter.
    internal = {
        "fitted_intercept": float(cal_fit.intercept),
        "fitted_slope": float(cal_fit.slope),
        "raw_logit": raw_logit,
        "calibrated_logit": calibrated_logit,
        "coef": (
            np.asarray(built.run.estimator.coef_, dtype=np.float64).copy()
            if hasattr(built.run.estimator, "coef_") else None
        ),
        "estimator_intercept": (
            np.asarray(built.run.estimator.intercept_, dtype=np.float64).copy()
            if hasattr(built.run.estimator, "intercept_") else None
        ),
    }
    return stage, internal


def _cross_build_exact(first: dict[str, Any], second: dict[str, Any]) -> dict[str, bool | None]:
    result: dict[str, bool | None] = {
        "fitted_calibrator_intercept": _same_float(first["fitted_intercept"], second["fitted_intercept"]),
        "fitted_calibrator_slope": _same_float(first["fitted_slope"], second["fitted_slope"]),
        "raw_log_odds": _same_float(first["raw_logit"], second["raw_logit"]),
        "calibrated_log_odds": _same_float(first["calibrated_logit"], second["calibrated_logit"]),
    }
    for key in ("coef", "estimator_intercept"):
        a, b = first[key], second[key]
        result["estimator_" + key] = (
            bool(np.array_equal(a, b, equal_nan=False))
            if isinstance(a, np.ndarray) and isinstance(b, np.ndarray) else None
        )
    return result


def probe() -> dict[str, Any]:
    pack = json.loads(fixtures.PACK.read_text(encoding="utf-8"))
    if (pack["bindings"] != fixtures.bindings()
            or pack["requests"] != fixtures.inputs()
            or canonical_response_digest(pack) != fixtures.PACK_SHA256
            or len(pack["cases"]) != 29):
        raise ValueError("frozen_source_integrity_failed")
    cases = [case for case in pack["cases"] if case["id"] == CASE_ID]
    if (len(cases) != 1 or cases[0]["route"] != fixtures.BASIC
            or cases[0]["edits"] or cases[0]["expected"]["status"] != "SYNTHETIC_RESULT"):
        raise ValueError("expected_synthetic_case_not_found")
    request = fixtures.materialize(pack["requests"][fixtures.BASIC], cases[0]["edits"])
    observed_stages, internals = [], []
    with TemporaryDirectory() as temporary:
        tmp = ensure_private_directory(Path(temporary))
        for i in range(2):
            stage, internal = _stage_snapshot(
                ensure_private_directory(tmp / ("trial_" + str(i))), request,
                cases[0]["expected"]
            )
            observed_stages.append(stage)
            internals.append(internal)
    comparison = _cross_build_exact(internals[0], internals[1])
    golden_exact = all(x["all_consumer_fields_exact"] for x in observed_stages)
    reproducible = all(x is not False for x in comparison.values())
    return {
        "status": "EXACT_REPLAY_AND_STAGES" if golden_exact and reproducible else "NUMERIC_DRIFT_DETECTED",
        "scope": "SYNTHETIC_ONLY_DIAGNOSTIC_NO_PATIENT_DATA",
        "case_id": CASE_ID,
        "frozen_fixture_digest_unchanged": True,
        "independent_builds": 2,
        "trials": observed_stages,
        "cross_build_exact_binary64": comparison,
        "note": "Comparison is diagnostic only; canonical fixture acceptance is untouched.",
    }


def main() -> int:
    try:
        result = probe()
    except Exception as exc:
        # Never render exception messages; an error string can include protected paths/values.
        print(json.dumps({"status": "DIAGNOSTIC_REFUSED", "exception_type": type(exc).__name__}))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0 if result["status"] == "EXACT_REPLAY_AND_STAGES" else 1


if __name__ == "__main__":
    raise SystemExit(main())
