"""RH-04 V2 — complete per-expected-value mapping across the 29 registered cases.

Scope
-----
Research evidence only. Synthetic inputs only.

No production module imports this file: nothing under ``ai/``, ``backend/``,
``shared/`` or ``scripts/`` references ``rh04_v2_``, which is asserted by
``test_no_production_module_imports_the_v2_candidate``. Note that this module's own
filename carries that prefix, so the grep would also catch a stray reference to the
file itself — the assertion is about the *importing* side.

What V2-03 asks for
-------------------
The original clause requires "a written mapping of every V1 expected value to its
V2 counterpart with the numeric delta". Earlier rounds produced a *case-level*
mapping ("2 of 29 cases differ"), which does not satisfy that: a case can differ in
one leaf of a deeply nested response, and a case-level count says nothing about
which value moved or by how much.

This module walks both response trees leaf by leaf and classifies **every** leaf:

``IDENTICAL``
    Present in both, equal under an exact structural comparison of the same type.
``NUMERIC_DELTA``
    Present in both, both binary64, not equal — reported with the absolute and
    relative delta. These are the values the V1→V2 change actually moves.
``STRUCTURAL_IDENTITY``
    A non-numeric leaf present in both with the same value (status strings, panel
    ids, booleans, nulls). Recorded separately so "identical" is not over-claimed.
``TYPE_CHANGE``
    Present in both with different types or shapes — a structural change, reported
    as such rather than coerced.
``MISSING_IN_V2`` / ``EXTRA_IN_V2``
    Present on one side only. A one-sided leaf is never silently dropped.

Why this is not a tolerance
---------------------------
Nothing here decides pass or fail on a numeric threshold. Lane B's acceptance is
still the exact digest ``891d9e3b…`` compared byte-for-byte. This module only
*describes* the delta between frozen V1 expectations and the V2 candidate so a
reviewer can audit every moved value. A delta being small does not make it
accepted, and the digest is never regenerated to accommodate one.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Final

V2_MAPPING_PROTOCOL_ID: Final[str] = "rh04.v2.value-mapping/v1"

IDENTICAL: Final[str] = "IDENTICAL"
NUMERIC_DELTA: Final[str] = "NUMERIC_DELTA"
STRUCTURAL_IDENTITY: Final[str] = "STRUCTURAL_IDENTITY"
TYPE_CHANGE: Final[str] = "TYPE_CHANGE"
MISSING_IN_V2: Final[str] = "MISSING_IN_V2"
EXTRA_IN_V2: Final[str] = "EXTRA_IN_V2"


def _kind(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _leaves(node: Any, prefix: str = "") -> dict[str, Any]:
    """Flatten a response tree to ``path -> leaf``.

    List indices appear as ``[i]`` so two trees with a different ordering cannot
    be compared as if they matched. An empty list records a single leaf at its own
    path, because "no outcomes" is itself a meaningful value that must not vanish
    from the mapping.
    """
    leaves: dict[str, Any] = {}
    if isinstance(node, dict):
        if not node:
            leaves[prefix or "$"] = {}
            return leaves
        for key in sorted(node):
            leaves.update(_leaves(node[key], f"{prefix}.{key}" if prefix else key))
        return leaves
    if isinstance(node, list):
        if not node:
            leaves[prefix or "$"] = []
            return leaves
        for index, item in enumerate(node):
            leaves.update(_leaves(item, f"{prefix}[{index}]"))
        return leaves
    leaves[prefix or "$"] = node
    return leaves


def _numeric_type(value: Any) -> str | None:
    """The exact JSON numeric type, or ``None`` for a non-number.

    ``bool`` is excluded deliberately: in Python ``True == 1``, so a boolean
    reaching the numeric path would compare equal to the integer 1.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    return None


def compare_value(path: str, left: Any, right: Any) -> dict[str, Any]:
    """Classify one leaf pair. Never coerces, never applies a threshold.

    Type strictness matters here. The previous version compared
    ``float(left) == float(right)`` and therefore reported an integer ``1`` and a
    float ``1.0`` as ``IDENTICAL``. They are different JSON values with different
    IEEE-754 representations, and a consumer that reads the artifact strictly may
    legitimately reject the change. The strict rule is: numeric leaves must match
    both in value **and** in type to count as identical; any int/float mismatch is
    a ``TYPE_CHANGE`` even when the numbers are equal.
    """
    left_kind, right_kind = _kind(left), _kind(right)
    if left_kind != right_kind:
        return {
            "path": path,
            "classification": TYPE_CHANGE,
            "v1_kind": left_kind,
            "v2_kind": right_kind,
        }

    left_numeric, right_numeric = _numeric_type(left), _numeric_type(right)
    if left_numeric is not None or right_numeric is not None:
        if left_numeric != right_numeric:
            # One side is a number of a different representation.
            return {
                "path": path,
                "classification": TYPE_CHANGE,
                "v1_kind": left_numeric,
                "v2_kind": right_numeric,
                "reason": "numeric type mismatch, no int/float coercion applied",
                "v1": left,
                "v2": right,
                "numerically_equal": left == right,
            }
        if left_numeric == "int":
            if left == right:
                return {
                    "path": path,
                    "classification": STRUCTURAL_IDENTITY,
                    "kind": "int",
                    "v1": left,
                    "v2": right,
                    "absolute_delta": 0,
                }
            return {
                "path": path,
                "classification": NUMERIC_DELTA,
                "kind": "int",
                "v1": left,
                "v2": right,
                "absolute_delta": abs(right - left),
                "relative_delta": (
                    None
                    if max(abs(left), abs(right)) == 0
                    else abs(right - left) / max(abs(left), abs(right))
                ),
                "bitwise_equal": False,
            }
        # float leaves: compare the exact IEEE-754 values, with no rounding.
        if left == right:
            return {
                "path": path,
                "classification": STRUCTURAL_IDENTITY,
                "kind": "float",
                "v1": left,
                "v2": right,
                "v1_repr": repr(left),
                "v2_repr": repr(right),
                "absolute_delta": 0.0,
            }
        absolute = abs(right - left)
        scale = max(abs(left), abs(right))
        return {
            "path": path,
            "classification": NUMERIC_DELTA,
            "kind": "float",
            "v1": left,
            "v2": right,
            "v1_repr": repr(left),
            "v2_repr": repr(right),
            "absolute_delta": absolute,
            "relative_delta": (None if scale == 0 else absolute / scale),
            "bitwise_equal": left == right,
        }

    if left_kind in {"string", "bool", "null"}:
        if left_kind == "bool":
            if left is right:
                return {
                    "path": path,
                    "classification": STRUCTURAL_IDENTITY,
                    "kind": "bool",
                    "v1": left,
                    "v2": right,
                }
            return {
                "path": path,
                "classification": TYPE_CHANGE,
                "v1": left,
                "v2": right,
                "reason": "same kind, different value",
            }
        if left == right:
            return {
                "path": path,
                "classification": STRUCTURAL_IDENTITY,
                "kind": left_kind,
                "v1": left,
                "v2": right,
            }
        return {
            "path": path,
            "classification": TYPE_CHANGE,
            "v1": left,
            "v2": right,
            "reason": "same kind, different value",
        }
    # Containers reaching here are empty ones recorded as leaves.
    return {
        "path": path,
        "classification": IDENTICAL if left == right else TYPE_CHANGE,
        "kind": left_kind,
    }


def compare_response(case_id: str, expected: Any, observed: Any) -> dict[str, Any]:
    """Full leaf-level comparison for one case."""
    left = _leaves(expected)
    right = _leaves(observed)

    entries: list[dict[str, Any]] = []
    for path in sorted(set(left) | set(right)):
        if path in left and path in right:
            entries.append(compare_value(path, left[path], right[path]))
        elif path in left:
            entries.append(
                {
                    "path": path,
                    "classification": MISSING_IN_V2,
                    "v1": left[path],
                    "v1_kind": _kind(left[path]),
                }
            )
        else:
            entries.append(
                {
                    "path": path,
                    "classification": EXTRA_IN_V2,
                    "v2": right[path],
                    "v2_kind": _kind(right[path]),
                }
            )

    counts: dict[str, int] = {}
    for entry in entries:
        counts[entry["classification"]] = counts.get(entry["classification"], 0) + 1

    numeric = [e for e in entries if e["classification"] == NUMERIC_DELTA]
    worst = max(
        numeric, key=lambda e: e["absolute_delta"], default=None
    )

    return {
        "case_id": case_id,
        "n_leaves_v1": len(left),
        "n_leaves_v2": len(right),
        "classification_counts": counts,
        "moved_value_count": len(numeric),
        "max_absolute_delta": None if worst is None else worst["absolute_delta"],
        "max_absolute_delta_path": None if worst is None else worst["path"],
        "entries": entries,
    }


def build_mapping(expected_by_case: dict[str, Any], observed_by_case: dict[str, Any]) -> dict[str, Any]:
    """Assemble the complete 29-case mapping document.

    Refuses to report success for a partial mapping: if the two sides do not cover
    the same case IDs, the missing or extra case is named instead of being skipped.
    """
    expected_ids = set(expected_by_case)
    observed_ids = set(observed_by_case)
    if expected_ids != observed_ids:
        raise ValueError(
            "case sets differ; a partial mapping is not a mapping. "
            f"missing_in_v2={sorted(expected_ids - observed_ids)} "
            f"extra_in_v2={sorted(observed_ids - expected_ids)}"
        )
    if len(expected_ids) != 29:
        raise ValueError(
            f"expected 29 registered cases, found {len(expected_ids)}; refusing to "
            "present a partial mapping as complete"
        )

    cases = [
        compare_response(case_id, expected_by_case[case_id], observed_by_case[case_id])
        for case_id in sorted(expected_ids)
    ]

    totals: dict[str, int] = {}
    for case in cases:
        for classification, count in case["classification_counts"].items():
            totals[classification] = totals.get(classification, 0) + count

    moved = [case for case in cases if case["classification_counts"].get(NUMERIC_DELTA)]
    document = {
        "protocol_id": V2_MAPPING_PROTOCOL_ID,
        "n_cases": len(cases),
        "leaf_totals": totals,
        "total_leaves": sum(totals.values()),
        "cases_with_numeric_delta": len(moved),
        "cases_with_no_numeric_delta": len(cases) - len(moved),
        "cases": cases,
        "note": (
            "descriptive only; Lane B acceptance remains exact equality against "
            "the fixed reference digest, and no delta here grants acceptance"
        ),
    }
    document["mapping_sha256"] = hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return document


def mapping_with_discrimination_proof(
    expected_by_case: dict[str, Any], observed_by_case: dict[str, Any]
) -> dict[str, Any]:
    """Build the mapping and prove it can detect a moved value.

    A mapping that reports "no numeric deltas" is only meaningful if it *would*
    have reported one. This perturbs a single numeric leaf by one unit in the
    last place, re-runs the comparison, and requires the perturbation to be
    detected at the exact path. If that self-check ever fails, the "no deltas"
    result is not evidence and the function refuses to present it.
    """
    import copy

    document = build_mapping(expected_by_case, observed_by_case)

    numeric_paths: list[tuple[str, str]] = []
    for case_id, expected in expected_by_case.items():
        for path, value in _leaves(expected).items():
            if isinstance(value, float):
                numeric_paths.append((case_id, path))
    if not numeric_paths:
        raise ValueError(
            "no numeric leaves in the V1 expectations; a zero-delta result would "
            "be vacuous rather than evidence"
        )

    case_id, path = sorted(numeric_paths)[0]
    perturbed = copy.deepcopy(observed_by_case[case_id])
    cursor = perturbed
    tokens = path.replace("]", "").replace("[", ".").split(".")
    for token in tokens[:-1]:
        cursor = cursor[int(token)] if token.isdigit() else cursor[token]
    last = tokens[-1]
    original = cursor[int(last)] if last.isdigit() else cursor[last]
    adjusted = original + abs(original) * 1e-15 + 1e-18
    if last.isdigit():
        cursor[int(last)] = adjusted
    else:
        cursor[last] = adjusted

    check = compare_response(case_id, expected_by_case[case_id], perturbed)
    detected = [
        entry
        for entry in check["entries"]
        if entry["classification"] == NUMERIC_DELTA and entry["path"] == path
    ]
    if not detected:
        raise ValueError(
            f"discrimination self-check failed: a perturbed value at {path!r} was "
            "not detected, so a zero-delta mapping cannot be trusted"
        )

    document["discrimination_proof"] = {
        "perturbed_case": case_id,
        "perturbed_path": path,
        "perturbation_relative": 1e-15,
        "detected": True,
        "detected_absolute_delta": detected[0]["absolute_delta"],
        "meaning": (
            "the mapping detects a one-part-in-10^15 move, so its zero-delta "
            "result for the real comparison is a measurement rather than an "
            "artefact of a comparison that cannot see differences"
        ),
    }
    document["mapping_sha256"] = hashlib.sha256(
        json.dumps(
            {k: v for k, v in document.items() if k != "mapping_sha256"},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return document
