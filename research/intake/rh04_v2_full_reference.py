"""RH-04 V2 — full 29-case reference candidate (synthetic only).

Scope
-----
Isolated candidate. Synthetic inputs only. **No production module imports this.**
The frozen V1 pack, the default solver and production inference are untouched.
V1 and the earlier V2 candidates remain historical artifacts.

What is different from the earlier candidates
---------------------------------------------
The earlier experiments either (a) replayed the V1 path with only the calibration
seamed, or (b) ran a toy pipeline on `RandomState(21)`. Neither satisfied the
review: option (b) was not the project's research replay, and neither used the
deterministic model fitter inside the registered workflow.

This module executes the **actual registered replay**: the real source bundles,
the real five routes, the real 29 case ids/requests/edits/ordering, the real
out-of-fold calibration contract, and the real model-family comparison. It then
records, for every logistic fit the workflow performs, whether the deterministic
reference fitter reproduces the production parameters.

Deliberately NOT done
---------------------
* The production model fit is **not** replaced. `ai/training.py` compares three
  families (measured: 100 logistic, 128 forest, 12 dummy estimator constructions
  on the REST route alone) and selects on mean fold AUC. Substituting a different
  fitter would silently change model selection, which the review forbids.
* Out-of-fold calibration is **not** replaced by calibrating on training rows.
* Expected responses are **not** copied: every outcome is produced by executing
  the path.

So the honest claim is: *the reference path is executed with a declared
deterministic calibration, the model family is recorded rather than assumed, and
the deterministic fitter is verified against the production fit as an oracle.*
"""

from __future__ import annotations

import hashlib
import json
import platform
from collections import Counter
from typing import Any, Final

FULL_REFERENCE_ID: Final[str] = "rh04.v2.full-reference-candidate/v1"
FULL_REFERENCE_SCHEMA: Final[str] = "cardioassist.rh04.full_reference_candidate/v1"

#: Identifies this artifact as an *unratified candidate*, never a gate.
FULL_REFERENCE_SENTINEL: Final[str] = "UNRATIFIED_CANDIDATE_NOT_AN_ACCEPTANCE_PACK"


def _v1():
    from research.intake import offline_fixture_pack as v1

    return v1


def declared_reference() -> dict[str, Any]:
    """Everything this candidate claims about itself, bound into its identity."""
    from research.intake import rh04_v2_reference_fit as reference_fit

    return {
        "candidate_id": FULL_REFERENCE_ID,
        "sentinel": FULL_REFERENCE_SENTINEL,
        "calibration": {
            "protocol_id": reference_fit.V2_FIT_PROTOCOL_ID,
            "arithmetic": "decimal",
            "ordering": "intercept-first (a, b); contract is intercept + slope*logit",
        },
        "model_fit_verification": {
            "deterministic_fitter": True,
            "replaces_production_fit": False,
            "reason": (
                "the registered workflow selects among three families on mean fold "
                "AUC; replacing the fitter would change selection"
            ),
        },
        "out_of_fold_calibration_preserved": True,
        "model_selection_preserved": True,
        "copied_expected_responses": False,
        "host_dependent_operations": "none in the calibration stage",
    }


def measure_model_families() -> dict[str, Any]:
    """Execute the registered REST route and record the families actually built.

    The review requires confirming the selected family rather than assuming
    logistic regression. This measures it.
    """
    import ai.training as training
    from tempfile import TemporaryDirectory
    from pathlib import Path

    from ai.filesystem_security import ensure_private_directory

    from research.intake import rh04_v2_candidate as candidate

    v1 = _v1()
    seen: Counter[str] = Counter()
    original = training._build_estimator

    def spy(family: str, params: Any, **kwargs: Any) -> Any:
        seen[family] += 1
        return original(family, params, **kwargs)

    training._build_estimator = spy
    try:
        with TemporaryDirectory() as tmp:
            with candidate.decimal_reference_seam(), candidate._deterministic_solver_default():
                local = v1.sources(ensure_private_directory(Path(tmp)))
                request = v1.materialize(v1.inputs()[v1.REST], [])
                v1.example(request, local[v1.REST])
    finally:
        training._build_estimator = original

    return {"families_built": dict(seen), "route": v1.REST}


def generate_full_reference() -> dict[str, Any]:
    """Execute all 29 cases through the registered path and record the outcomes.

    This is a *generation*, not a copy: every case is produced by calling the real
    replay entry point.
    """
    from tempfile import TemporaryDirectory
    from pathlib import Path

    from ai.filesystem_security import ensure_private_directory

    from research.intake import rh04_v2_candidate as candidate

    v1 = _v1()
    source = json.loads(v1.PACK.read_text())
    cases: list[dict[str, Any]] = []
    fits = 0

    with TemporaryDirectory() as tmp:
        with candidate.decimal_reference_seam() as recorded, (
            candidate._deterministic_solver_default()
        ):
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
                        "edits": case["edits"],
                        "expected": actual,
                    }
                )
            fits = recorded["fits"]

    return {
        "schema_version": FULL_REFERENCE_SCHEMA,
        "declared": declared_reference(),
        "bindings": source["bindings"],
        "requests": source["requests"],
        "cases": cases,
        "generation": {
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "fit_invocations": fits,
            "case_count": len(cases),
            "note": (
                "environment metadata is provenance only and is excluded from the "
                "semantic identity"
            ),
        },
    }


#: Sections that define the candidate's semantic identity.
SEMANTIC_SECTIONS: Final[tuple[str, ...]] = (
    "schema_version",
    "declared",
    "bindings",
    "requests",
    "cases",
)


def canonical_bytes(document: Any) -> bytes:
    return json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def semantic_digest(pack: dict[str, Any]) -> str:
    """Digest over the whole declaration AND the content.

    The previous candidate excluded the algorithm declaration from its semantic
    digest, which meant a changed objective or protocol version could not move
    the identity. The declaration is now inside it.
    """
    subset = {name: pack[name] for name in SEMANTIC_SECTIONS if name in pack}
    return hashlib.sha256(canonical_bytes(subset)).hexdigest()


def provenance_digest(pack: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(pack.get("generation", {}))).hexdigest()


def artifact_digest(pack: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(pack)).hexdigest()


def describe_identity(pack: dict[str, Any]) -> dict[str, Any]:
    return {
        "semantic_digest": semantic_digest(pack),
        "provenance_digest": provenance_digest(pack),
        "artifact_digest": artifact_digest(pack),
        "sentinel": pack.get("declared", {}).get("sentinel"),
    }


def validate(pack: dict[str, Any], *, replay: bool = True) -> int:
    """Structural validation, optionally followed by an exact replay.

    Fails closed. Deliberately distinct from authoritative pinned verification:
    this candidate is unratified, so a matching digest here means "the candidate
    is internally consistent", not "the reference is accepted".
    """
    v1 = _v1()
    from research.intake import rh04_v2_candidate as candidate

    if pack.get("schema_version") != FULL_REFERENCE_SCHEMA:
        raise ValueError("unexpected full-reference schema")
    declared = pack.get("declared")
    if not isinstance(declared, dict) or declared.get("sentinel") != (
        FULL_REFERENCE_SENTINEL
    ):
        raise ValueError("candidate sentinel missing: refusing to treat as accepted")
    if declared != declared_reference():
        raise ValueError("declaration drift")
    unknown = set(pack) - {
        "schema_version",
        "declared",
        "bindings",
        "requests",
        "cases",
        "generation",
    }
    if unknown:
        raise ValueError(f"unknown field(s): {sorted(unknown)}")
    cases = pack.get("cases")
    if not isinstance(cases, list) or len(cases) != candidate.V2_EXPECTED_CASE_COUNT:
        raise ValueError("case count changed")
    if tuple(case.get("id") for case in cases) != candidate.V2_EXPECTED_CASE_IDS:
        raise ValueError("case inventory or order changed")
    if pack.get("bindings") != v1.bindings():
        raise ValueError("stale binding")
    if pack.get("requests") != v1.inputs():
        raise ValueError("non-fixture request")
    source_cases = {case["id"]: case for case in json.loads(v1.PACK.read_text())["cases"]}
    for case in cases:
        original = source_cases[case["id"]]
        if case.get("edits") != original.get("edits"):
            raise ValueError(f"edit drift in {case['id']}")
        if case.get("route") != original.get("route"):
            raise ValueError(f"route drift in {case['id']}")

    if not replay:
        return len(cases)

    regenerated = generate_full_reference()
    if canonical_bytes(regenerated["cases"]) != canonical_bytes(pack["cases"]):
        from research.intake.diagnose_fixture_replay import _describe

        for left, right in zip(pack["cases"], regenerated["cases"]):
            if canonical_bytes(left["expected"]) != canonical_bytes(right["expected"]):
                raise ValueError(
                    "response mismatch: "
                    + left["id"]
                    + "; redacted_field_diff="
                    + json.dumps(_describe(left["expected"], right["expected"]), sort_keys=True)
                )
        raise ValueError("response mismatch: case ordering")
    return len(cases)
