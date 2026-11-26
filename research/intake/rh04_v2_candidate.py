"""RH-04 V2 — candidate synthetic-only reference pack generator and validator.

Status: **candidate**. This module is *not* imported by production code, does
not touch the frozen V1 pack, and is not wired into any workflow, gate or
scoring path. It exists to make a V2 reference *provable* before any maintainer
decision is taken to adopt one.

What a "V2 reference" is here
-----------------------------
The V1 pack records the output of the pipeline with SciPy L-BFGS-B running on
whatever OpenBLAS kernel the host happened to dispatch. That reference is
therefore host-dependent (see ``docs/rh04-issue132-acceptance-decision.md``).
A V2 reference must instead be a function of a **declared algorithm**, so this
module replays the *identical* production pipeline with exactly one numerical
seam replaced:

    ``ai.calibration.deterministic_logistic_fit``  ->  ``rh04_v2_reference_fit.decimal_logistic_fit``

and selects the existing opt-in solver flag so the production code path routes
through that seam. Everything else — cohort generation, the random forest, the
preprocessor, SHAP/LIME, the facade, the response projection, the digest and the
strict comparator — is the production code, unchanged.

Consequences that must be stated plainly:

* A V2 expected value is the **KKT optimum** of the declared objective, whereas
  a V1 expected value is an **L-BFGS-B stopping artifact** (default
  ``pgtol=1e-5``). They are different numbers by construction, and the
  difference is a property of the algorithm, not of a host. The per-field
  mapping is emitted by :func:`build_mapping`.
* Adopting V2 therefore *re-certifies* every calibrated numeric field. That is
  a maintainer decision (``V2-01``), not something this module may do.
* V2 tolerance is **zero**: :func:`validate` uses strict type-and-value
  equality with no approved-exception branch. There is no analogue of the V1
  Cleveland exception.

Portability scope
-----------------
The claim tested by the harness is: *on the tested hosts and dispatch classes,
the V2 pack is reproduced bit-identically*. It is not a claim about untested
platforms, other decimal implementations, or the behaviour of ``expit`` on
untested libm builds.
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any, Final, Iterator, Mapping

import numpy as np

from ai.calibration import (
    CALIBRATION_LOWER_BOUNDS,
    CALIBRATION_UPPER_BOUNDS,
    DETERMINISTIC_CALIBRATION_SOLVER,
)
from research.intake import rh04_v2_reference_fit as reference_fit

V2_SCHEMA_VERSION: Final[str] = "cardioassist.rh04.offline_io/v2"
V2_FIXTURE_PATH: Final[Path] = (
    Path(__file__).with_name("fixtures") / "offline_io.v2.json"
)
# Filled in only after a reviewed generation run; an empty string means
# "candidate, not yet pinned". Never invent this value.
V2_PACK_SHA256: Final[str] = (
    "UNPINNED_CANDIDATE_PACK_DO_NOT_USE_AS_A_GATE"
)
# The digests actually observed for a fresh generation, keyed by OpenBLAS kernel
# class. Class A is every measured kernel except the three in class B
# (Sandybridge / Prescott / Katmai). Two classes exist because generation is an
# exact function of the reference's *inputs*, and the float64 sklearn `gemv`
# upstream of that feed is not portable — see §4-§5 of the V2 protocol.
# This is an observation, not a gate: nothing in production or CI branches on it.
V2_OBSERVED_PACK_DIGESTS: Final[dict[str, str]] = {
    "b74f781d7c7839a33c3693e53511ac4d200b8bcf5b0a38526e9a9e2b657595f2": "class-a",
    "3df8de9499e0eaafd47735462f71b75fee4941487a6d36b3a856478486789568": "class-b",
}
# The case inventory is part of the contract. Pinning it makes a *removed* case
# fail closed even though a shorter pack is still internally consistent — the
# failure mode that a pure digest cannot catch when the digest is unpinned.
# 29 cases: 5 route cases plus refusal/edit probes. Pinning the exact list makes
# a *removed* case fail closed even though a shorter pack is internally
# consistent — the failure mode a digest alone cannot catch when unpinned.
V2_EXPECTED_CASE_IDS: Final[tuple[str, ...]] = (
    "da_a2_resting_v1",
    "da_a1_basic_clinical_v1",
    "da_a2_resting_labs_v1",
    "da_a1_clinical_core_labs_v1",
    "da_a2_hungary_locked_transportability_v1",
    "wrong-panel",
    "wrong-dataset",
    "stale-hash",
    "wrong-unit",
    "bad-category",
    "bad-generator",
    "patient_wearable",
    "uploaded_image_or_ocr",
    "track_b",
    "ca",
    "Cath",
    "LAD",
    "required",
    "optional",
    "da_a1_clinical_core_labs_v1-wrong-dataset",
    "da_a1_clinical_core_labs_v1-stale-hash",
    "da_a2_hungary_locked_transportability_v1-wrong-dataset",
    "da_a2_hungary_locked_transportability_v1-stale-hash",
    "da_a2_resting_labs_v1-wrong-dataset",
    "da_a2_resting_labs_v1-stale-hash",
    "optional-null",
    "optional-null-structural-reason",
    "optional-null-no-reason",
    "required-null",
)
V2_EXPECTED_CASE_COUNT: Final[int] = len(V2_EXPECTED_CASE_IDS)


def canonical_json_bytes(document: Mapping[str, Any]) -> bytes:
    """Canonical encoding used for every V2 digest (stable across hosts)."""
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def pack_digest(pack: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(pack)).hexdigest()


@contextmanager
def decimal_reference_seam() -> Iterator[dict[str, Any]]:
    """Route the production calibrator through the decimal reference solver.

    The seam is exactly one function: ``ai.calibration.deterministic_logistic_fit``.
    The production class, its validation, its serialisation and its
    ``solver`` provenance string are all untouched; the restored function is
    the original object, so nothing leaks into an importing process.
    """
    from ai import calibration as module

    original = module.deterministic_logistic_fit
    recorded: dict[str, Any] = {"fits": 0, "parameter_sha256": None, "converged": True}

    def seam(y: np.ndarray, logits: np.ndarray, **kwargs: Any) -> tuple[float, float]:
        # The seam is a boundary between binary64 production code and the
        # declared decimal algorithm. The declared constants are DECIMAL
        # LITERALS (``Decimal("1e-3")``), never ``as_decimal(1e-3)``: the latter
        # converts the binary64 approximation of 1e-3 and would silently make the
        # reference depend on a float literal rather than on the declaration.
        recorded["fits"] += 1
        declared = {
            "l2_anchor": 1e-3,
            "lower": CALIBRATION_LOWER_BOUNDS,
            "upper": CALIBRATION_UPPER_BOUNDS,
        }
        for name, expected in declared.items():
            if name not in kwargs:
                continue
            supplied = kwargs[name]
            if name == "l2_anchor":
                if supplied != expected:
                    raise ValueError(f"V2 seam refuses a non-declared {name}")
            elif tuple(supplied) != tuple(expected):
                raise ValueError(f"V2 seam refuses a non-declared {name}")
        return reference_fit.decimal_logistic_fit(
            y,
            logits,
            l2_anchor=reference_fit.V2_FIT_L2_ANCHOR,
            lower=reference_fit.V2_FIT_LOWER,
            upper=reference_fit.V2_FIT_UPPER,
            max_iterations=reference_fit.V2_FIT_MAX_ITERATIONS,
        )

    module.deterministic_logistic_fit = seam
    try:
        yield recorded
    finally:
        module.deterministic_logistic_fit = original


@contextmanager
def _deterministic_solver_default() -> Iterator[None]:
    """Make the production calibrator default to the (seamed) deterministic solver.

    Implemented as a class-method swap on the *same* class object, so every
    alias (``ai.training`` re-imports the class, it does not copy it) observes
    the change. Restored on exit.
    """
    from ai.calibration import OofLogisticCalibrator

    original = OofLogisticCalibrator.__dict__["fit_from_oof"]

    def fit_with_declared_solver(cls, *args: Any, **kwargs: Any) -> Any:
        kwargs.setdefault("solver", DETERMINISTIC_CALIBRATION_SOLVER)
        return original.__get__(cls, OofLogisticCalibrator)(*args, **kwargs)

    OofLogisticCalibrator.fit_from_oof = classmethod(fit_with_declared_solver)
    try:
        yield
    finally:
        OofLogisticCalibrator.fit_from_oof = original


def _v1_pack() -> dict[str, Any]:
    from research.intake import offline_fixture_pack as v1

    return json.loads(v1.PACK.read_text())


def generate_candidate_pack() -> dict[str, Any]:
    """Regenerate the full 29-case reference under the declared V2 algorithm.

    Reuses the V1 *request* definitions and edit scripts verbatim: V2 changes
    the reference arithmetic, never the synthetic inputs, the routes, the edits
    or the case inventory.
    """
    from ai.filesystem_security import ensure_private_directory
    from tempfile import TemporaryDirectory

    from research.intake import offline_fixture_pack as v1

    source = _v1_pack()
    cases: list[dict[str, Any]] = []
    with TemporaryDirectory() as tmp:
        with decimal_reference_seam() as recorded, _deterministic_solver_default():
            local = v1.sources(ensure_private_directory(Path(tmp)))
            for case in source["cases"]:
                request = v1.materialize(
                    source["requests"][case["route"]], case["edits"]
                )
                actual = v1.example(
                    request, local.get(case["route"], local["blocked"])
                )
                cases.append(
                    {
                        "id": case["id"],
                        "route": case["route"],
                        "edits": deepcopy(case["edits"]),
                        "expected": actual,
                    }
                )
            fits = recorded["fits"]

    pack = {
        "schema_version": V2_SCHEMA_VERSION,
        "protocol": reference_fit.declared_protocol(),
        "bindings": source["bindings"],
        "requests": source["requests"],
        "cases": cases,
        "generation": {
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "fit_invocations": fits,
            "seam": "ai.calibration.deterministic_logistic_fit",
            "solver_selector": DETERMINISTIC_CALIBRATION_SOLVER,
            "generator": "research.intake.rh04_v2_candidate",
            "note": (
                "No host identity is recorded on purpose: the reference must be "
                "a function of the declared algorithm, not of the machine that "
                "first produced it."
            ),
        },
    }
    return pack


def validate(
    pack: Mapping[str, Any],
    *,
    expected_digest: str | None = None,
    replay: bool = True,
) -> int:
    """Strict V2 validation. No tolerances and no approved-exception branch.

    ``replay=False`` performs the structural checks only (schema, declared
    protocol, case inventory, bindings, integrity). ``replay=True`` additionally
    rebuilds every synthetic artifact and compares each case with exact
    type-and-value equality. Exact replay costs ~90 s, so the structural half is
    separated for use in fast negative tests; the full replay is exercised by
    the cold-process end-to-end test and by ``--check``.

    Returns the number of cases verified. Raises ``ValueError`` on any
    deviation — including a mismatch in a single binary64 bit.
    """
    from research.intake import offline_fixture_pack as v1

    if pack.get("schema_version") != V2_SCHEMA_VERSION:
        raise ValueError("unexpected v2 schema version")
    if pack.get("protocol") != reference_fit.declared_protocol():
        raise ValueError("declared protocol drift")
    cases = pack.get("cases")
    if not isinstance(cases, list) or len(cases) != V2_EXPECTED_CASE_COUNT:
        raise ValueError(
            f"v2 case inventory changed: expected {V2_EXPECTED_CASE_COUNT} cases"
        )
    if tuple(case.get("id") for case in cases) != V2_EXPECTED_CASE_IDS:
        raise ValueError("v2 case inventory changed: ids or order differ")
    if pack.get("bindings") != v1.bindings():
        raise ValueError("stale binding")
    if pack.get("requests") != v1.inputs():
        raise ValueError("non-fixture request")
    digest = pack_digest(pack)
    if expected_digest is not None and digest != expected_digest:
        raise ValueError("fixture integrity mismatch")
    if not V2_PACK_SHA256.startswith("UNPINNED") and digest != V2_PACK_SHA256:
        raise ValueError("fixture integrity mismatch")

    from tempfile import TemporaryDirectory

    from ai.filesystem_security import ensure_private_directory

    if not replay:
        return len(cases)
    with TemporaryDirectory() as tmp:
        with decimal_reference_seam(), _deterministic_solver_default():
            local = v1.sources(ensure_private_directory(Path(tmp)))
            for case in cases:
                request = v1.materialize(
                    pack["requests"][case["route"]], case["edits"]
                )
                actual = v1.example(
                    request, local.get(case["route"], local["blocked"])
                )
                if not v1._strict_equal(case["expected"], actual):
                    from research.intake.diagnose_fixture_replay import _describe

                    raise ValueError(
                        "response mismatch: "
                        + case["id"]
                        + "; redacted_field_diff="
                        + json.dumps(_describe(case["expected"], actual), sort_keys=True)
                    )
    return len(cases)


def build_mapping(v1_pack: Mapping[str, Any], v2_pack: Mapping[str, Any]) -> dict[str, Any]:
    """Field-by-field V1 -> V2 numeric mapping (V2-03 evidence).

    Records, for every case, which paths differ and by how much. Values are
    included because this document is a *review artifact*, not a gate; it is
    generated locally and never printed by CI.
    """
    entries: list[dict[str, Any]] = []
    by_id = {case["id"]: case for case in v2_pack["cases"]}
    for case in v1_pack["cases"]:
        other = by_id[case["id"]]
        changes: list[dict[str, Any]] = []

        def walk(left: Any, right: Any, path: str) -> None:
            if type(left) is not type(right):
                changes.append({"path": path, "kind": "type"})
                return
            if isinstance(left, dict):
                for key in sorted(set(left) | set(right)):
                    if key not in left or key not in right:
                        changes.append({"path": f"{path}.{key}", "kind": "present"})
                        continue
                    walk(left[key], right[key], f"{path}.{key}")
                return
            if isinstance(left, list):
                for index in range(min(len(left), len(right))):
                    walk(left[index], right[index], f"{path}[{index}]")
                if len(left) != len(right):
                    changes.append({"path": path, "kind": "length"})
                return
            if left != right:
                entry: dict[str, Any] = {"path": path, "kind": "value"}
                if isinstance(left, float) and isinstance(right, float):
                    entry["v1"] = repr(left)
                    entry["v2"] = repr(right)
                    entry["delta"] = right - left
                    spacing = abs(np.spacing(left)) or abs(np.spacing(right))
                    entry["delta_ulps"] = (right - left) / spacing if spacing else None
                changes.append(entry)

        walk(case["expected"], other["expected"], case["id"])
        entries.append({"id": case["id"], "changes": changes})
    return {
        "schema_version": "cardioassist.rh04.v1_to_v2_mapping/v1",
        "v1_pack_sha256": _v1_digest(),
        "v2_pack_sha256": pack_digest(v2_pack),
        "total_changed_paths": sum(len(entry["changes"]) for entry in entries),
        "cases": entries,
    }


def _v1_digest() -> str:
    from research.intake import offline_fixture_pack as v1

    return v1.PACK_SHA256


def environment_record() -> dict[str, Any]:
    """Host record emitted for *evidence*, never folded into the reference."""
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
        "requested_openblas_coretype": __import__("os").environ.get(
            "OPENBLAS_CORETYPE", "(unset)"
        ),
        "openblas_num_threads": __import__("os").environ.get(
            "OPENBLAS_NUM_THREADS", "(unset)"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    """``--check`` validates a committed candidate; ``--write`` regenerates it."""
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["--check"]:
        pack = json.loads(V2_FIXTURE_PATH.read_text())
        count = validate(pack)
        print(
            json.dumps(
                {
                    "status": "EXACT_REPLAY",
                    "cases": count,
                    "pack_sha256": pack_digest(pack),
                    "environment": environment_record(),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args[:1] == ["--write"]:
        pack = generate_candidate_pack()
        V2_FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
        V2_FIXTURE_PATH.write_text(
            json.dumps(pack, indent=2, sort_keys=True, allow_nan=False) + "\n"
        )
        print(json.dumps({"pack_sha256": pack_digest(pack)}, indent=2))
        return 0
    print("usage: python -m research.intake.rh04_v2_candidate --check|--write")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
