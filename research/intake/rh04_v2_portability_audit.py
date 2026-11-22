"""RH-04 V2 — stage-level BLAS/libm portability audit for the RH-04 replay path.

Status: **candidate audit tool, read-only**. It changes no production file, no
fixture, no comparator and no workflow. It exists to answer one question with
evidence instead of inference:

    which stages of the RH-04 synthetic replay are functions of the host's
    OpenBLAS dispatch, and which are not?

Why this tool had to exist
--------------------------
`docs/rh04-issue132-acceptance-decision.md` localised the *observed* 1-ULP drift
to "the SciPy L-BFGS-B fit" by measuring one cohort and one model family. That
statement is about the drift *that was visible in that experiment*. It is not a
general statement, and it turned out not to be one: regenerating the whole pack
with a bit-portable calibrator still produced two different packs on two
dispatch classes (measured; see
`docs/research/next_phase/RH04_V2_REPRODUCIBILITY_PROTOCOL_2026_11_21.md`).

A portable acceptance reference therefore cannot be built by replacing the
calibrator alone. It needs a per-stage map of what is dispatch-dependent. This
module measures that map directly:

* ``micro`` stages isolate single operations (``np.dot``/BLAS ``gemv``,
  ``scipy.special.expit``, ``np.log``/``np.log1p``, ``sklearn`` decision
  functions) on fixed inputs;
* ``fit`` stages compare the production float64 L-BFGS-B fit with the declared
  decimal reference fit on identical inputs;
* ``pipeline`` stages run the real ``fast()`` synthetic builds and hash only
  *observable* outputs (selected family, hyperparameters, calibrator
  parameters, serialised bundle members, internal-evaluation document).

Everything is synthetic. Nothing is printed that could identify a host, hold a
path, or carry a score belonging to a real record — the digests are one-way and
the payload carries no values.

Usage
-----
    OPENBLAS_CORETYPE=Haswell python -m research.intake.rh04_v2_portability_audit \
        --json > /tmp/audit-haswell.json
    python -m research.intake.rh04_v2_portability_audit --compare a.json b.json

``--compare`` reports, per stage, ``INVARIANT`` / ``DISPATCH_DEPENDENT`` and
exits ``1`` if any stage differs — a *reporting* exit code, not a gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
from typing import Any, Callable, Final, Mapping

AUDIT_SCHEMA_VERSION: Final[str] = "cardioassist.rh04.portability_audit/v1"


def _digest(payload: Any) -> str:
    """Canonical digest of a JSON-able value (stable across hosts)."""
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()[:16]


def _digest_floats(values: Any) -> str:
    """Digest raw binary64 bytes: catches a 1-ULP difference that JSON cannot."""
    import numpy as np

    array = np.ascontiguousarray(np.asarray(values, dtype=np.float64))
    return hashlib.sha256(array.tobytes()).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# Micro stages: single operations on fixed inputs                            #
# --------------------------------------------------------------------------- #


def _fixed_probabilities() -> Any:
    import numpy as np

    generator = np.random.default_rng(20261121)
    core = generator.beta(2.0, 5.0, size=120)
    # Explicit edge-shaped values the production path really sees.
    return np.concatenate([core, np.array([0.0, 1.0, 1e-9, 1.0 - 1e-9])])


def micro_stages() -> dict[str, str]:
    """One digest per isolated numerical operation."""
    import numpy as np
    from scipy.special import expit
    from sklearn.linear_model import LogisticRegression

    from ai.calibration import safe_clipped_logit

    stages: dict[str, str] = {}
    probabilities = _fixed_probabilities()

    # libm path used by the calibrator's input link.
    # Probabilities are clamped before the log, so this stage measures the libm
    # value and not IEEE -inf handling.
    stages["np_log"] = _digest_floats(
        np.log(np.clip(probabilities, 1e-6, 1.0 - 1e-6))
    )
    # Deliberately clamped first: log1p(-1.0) is -inf and would make this stage
    # a test of IEEE infinity handling rather than of the libm value.
    stages["np_log1p"] = _digest_floats(
        np.log1p(-np.clip(probabilities, 0.0, 1.0 - 1e-6))
    )
    stages["safe_clipped_logit"] = _digest_floats(safe_clipped_logit(probabilities))

    # expit is the map from calibrated log-odds to the research score.
    logits = safe_clipped_logit(probabilities)
    stages["scipy_expit"] = _digest_floats(expit(logits))

    # BLAS reductions at several shapes (the V1-era mechanism).
    generator = np.random.default_rng(7)
    for size in (2, 16, 64, 120, 512):
        left = generator.normal(size=size)
        right = generator.normal(size=size)
        stages[f"np_dot_{size}"] = _digest_floats(np.array([float(np.dot(left, right))]))
        stages[f"np_mean_product_{size}"] = _digest_floats(
            np.array([float(np.mean(left * right))])
        )

    # BLAS gemv/gemm path used by the linear research family's decision function.
    matrix = generator.normal(size=(120, 16))
    coefficients = generator.normal(size=16)
    decision = LogisticRegression()
    decision.classes_ = np.array([0, 1])
    decision.coef_ = coefficients.reshape(1, -1)
    decision.intercept_ = np.array([0.25])
    stages["sklearn_decision_function_gemv"] = _digest_floats(
        decision.decision_function(matrix)
    )
    stages["blas_matmul_120x16"] = _digest_floats(matrix @ coefficients)

    return stages


# --------------------------------------------------------------------------- #
# Fit stages: behaviour of the calibration fitters on identical inputs       #
# --------------------------------------------------------------------------- #


def _golden_like_fit_inputs() -> tuple[Any, Any]:
    """Deterministic OOF-like inputs with realistic separation.

    Reproduces the *shape* of the real repository cohorts (120 OOF rows,
    probabilities that are neither separable nor degenerate) without reading
    any fixture, so the stage is reproducible from the source alone.
    """
    import numpy as np

    generator = np.random.default_rng(424242)
    latent = generator.normal(-0.4, 1.1, size=120)
    probabilities = 1.0 / (1.0 + np.exp(-latent))
    labels = (generator.random(120) < probabilities).astype(float)
    if labels.sum() in (0, 120):
        labels[0], labels[1] = 0.0, 1.0
    from ai.calibration import safe_clipped_logit

    return labels, safe_clipped_logit(probabilities)


def fit_stages() -> dict[str, str]:
    """Float64 production fit vs the declared decimal reference fit."""
    from scipy.optimize import minimize
    from scipy.special import expit

    from ai.calibration import deterministic_logistic_fit
    from research.intake import rh04_v2_reference_fit as reference

    labels, logits = _golden_like_fit_inputs()
    stages: dict[str, str] = {}
    stages["fit_input_labels"] = _digest_floats(labels)
    stages["fit_input_logits"] = _digest_floats(logits)

    # Exactly the production objective and L-BFGS-B call from ai.calibration.
    def objective(params: Any) -> tuple[float, Any]:
        import numpy as np

        a, b = float(params[0]), float(params[1])
        eta = a + b * logits
        nll = float(np.mean(np.logaddexp(0.0, eta) - labels * eta))
        regularization = 0.5 * 1e-3 * (a * a + (b - 1.0) ** 2)
        diff = expit(eta) - labels
        return nll + regularization, np.array(
            [
                float(np.mean(diff)) + 1e-3 * a,
                float(np.mean(diff * logits)) + 1e-3 * (b - 1.0),
            ]
        )

    optimum = minimize(
        lambda theta: objective(theta)[0],
        x0=__import__("numpy").array([0.0, 1.0], dtype=float),
        jac=lambda theta: objective(theta)[1],
        method="L-BFGS-B",
        bounds=[(-15.0, 15.0), (0.01, 15.0)],
    )
    stages["float64_lbfgsb_parameters"] = _digest_floats(optimum.x)
    stages["float64_lbfgsb_iterations"] = _digest(int(optimum.nit))

    # The V1-era float64 "portable" solver: does it even terminate here?
    try:
        deterministic = deterministic_logistic_fit(labels, logits)
        stages["float64_deterministic_solver"] = _digest_floats(deterministic)
    except Exception as exc:  # noqa: BLE001 - the failure mode IS the finding
        stages["float64_deterministic_solver"] = "DID_NOT_CONVERGE:" + (
            "calibration_solver_did_not_converge"
            if "did_not_converge" in str(exc).lower()
            or "calibration_solver" in str(exc)
            else type(exc).__name__
        )

    # The declared decimal reference: the stage a V2 pack would pin.
    decimal_parameters = reference.decimal_logistic_fit(labels, logits)
    stages["decimal_reference_parameters"] = _digest_floats(decimal_parameters)
    stages["decimal_reference_reproducible"] = _digest(
        reference.fit_is_host_independent(labels, logits)
    )
    return stages


# --------------------------------------------------------------------------- #
# Pipeline stages: the real synthetic builds, observable only                #
# --------------------------------------------------------------------------- #


def pipeline_stages() -> dict[str, str]:
    """Hash the observable outputs of the two synthetic bundle builds."""
    import hashlib as _hashlib
    from pathlib import Path
    from tempfile import TemporaryDirectory

    from ai.filesystem_security import ensure_private_directory
    from ai.research_demo import _build_demo_bundle
    from ai.uci412_research import (
        Uci412ResearchModelConfig,
        build_uci412_synthetic_research_model,
    )

    stages: dict[str, str] = {}
    with TemporaryDirectory() as tmp:
        root = ensure_private_directory(Path(tmp))

        demo = _build_demo_bundle(ensure_private_directory(root / "rest"))
        run = demo["run"]
        stages["rest_selected_family"] = _digest(run.selected_model_family)
        stages["rest_hyperparameters"] = _digest(dict(run.selected_hyperparameters))
        stages["rest_calibrator_parameters"] = _digest_floats(
            [run.calibrator.intercept, run.calibrator.slope]
        )
        for member in (
            "calibration.json",
            "preprocessing.json",
            "shap_background.json",
            "model.joblib",
        ):
            path = Path(demo["bundle_dir"]) / member
            stages[f"rest_bundle_{member}"] = _hashlib.sha256(
                path.read_bytes()
            ).hexdigest()[:16]

        basic = build_uci412_synthetic_research_model(
            Uci412ResearchModelConfig.fast(
                package_bundle=True,
                work_root=ensure_private_directory(root / "basic"),
            )
        )
        basic_run = basic.run
        stages["basic_selected_family"] = _digest(basic_run.selected_model_family)
        stages["basic_hyperparameters"] = _digest(
            dict(basic_run.selected_hyperparameters)
        )
        stages["basic_calibrator_parameters"] = _digest_floats(
            [basic_run.calibrator.intercept, basic_run.calibrator.slope]
        )
        stages["basic_report_digest"] = _digest(
            json.loads(json.dumps(_plain(basic.report.to_dict())))
        )
        for member in ("calibration.json", "model.joblib"):
            path = Path(basic.bundle_dir) / member
            stages[f"basic_bundle_{member}"] = _hashlib.sha256(
                path.read_bytes()
            ).hexdigest()[:16]
    return stages


def _plain(value: Any) -> Any:
    """Convert mapping-proxy/deep structures into plain JSON types."""
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


# --------------------------------------------------------------------------- #
# Report / comparison                                                        #
# --------------------------------------------------------------------------- #


def environment() -> dict[str, str]:
    import numpy
    import scipy
    import sklearn

    return {
        "python_version": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "numpy": numpy.__version__,
        "scipy": scipy.__version__,
        "scikit_learn": sklearn.__version__,
        "requested_openblas_coretype": os.environ.get("OPENBLAS_CORETYPE", "(unset)"),
        "openblas_num_threads": os.environ.get("OPENBLAS_NUM_THREADS", "(unset)"),
    }


def run_audit(stages: tuple[str, ...] = ("micro", "fit", "pipeline")) -> dict[str, Any]:
    selected: dict[str, str] = {}
    if "micro" in stages:
        selected.update(micro_stages())
    if "fit" in stages:
        selected.update(fit_stages())
    if "pipeline" in stages:
        selected.update(pipeline_stages())
    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "environment": environment(),
        "stages": selected,
    }


def compare_audits(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    """Per-stage INVARIANT / DISPATCH_DEPENDENT report. Pure, testable."""
    left_stages = dict(left.get("stages") or {})
    right_stages = dict(right.get("stages") or {})
    names = sorted(set(left_stages) | set(right_stages))
    rows = []
    for name in names:
        a = left_stages.get(name, "<missing>")
        b = right_stages.get(name, "<missing>")
        rows.append(
            {
                "stage": name,
                "verdict": "INVARIANT" if a == b else "DISPATCH_DEPENDENT",
                "left": a,
                "right": b,
            }
        )
    differing = [row["stage"] for row in rows if row["verdict"] != "INVARIANT"]
    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "left_environment": left.get("environment"),
        "right_environment": right.get("environment"),
        "stages_compared": len(rows),
        "stages_differing": differing,
        "all_stages_invariant": not differing,
        "rows": rows,
    }


def _force_stage(stages: tuple[str, ...], name: str) -> Callable[[], dict[str, Any]]:
    """Small indirection kept so tests can drive a single stage."""
    return lambda: run_audit(stages=(name,))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="emit the audit JSON")
    parser.add_argument(
        "--stages",
        default="micro,fit,pipeline",
        help="comma-separated subset of micro,fit,pipeline",
    )
    parser.add_argument("--compare", nargs=2, metavar=("LEFT", "RIGHT"))
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    if args.compare:
        left = json.loads(open(args.compare[0], encoding="utf-8").read())
        right = json.loads(open(args.compare[1], encoding="utf-8").read())
        report = compare_audits(left, right)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["all_stages_invariant"] else 1

    stages = tuple(part.strip() for part in args.stages.split(",") if part.strip())
    report = run_audit(stages=stages)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
