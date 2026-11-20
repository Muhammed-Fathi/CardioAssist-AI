"""Read-only RH-04 synthetic fixture replay diagnosis for cross-OS acceptance.

This diagnostic does NOT accept an input path or external data. It uses only
reviewed built-in fixtures, replays the existing synthetic generator, and
prints mismatch *field names and categories*, never submitted/observed values,
private paths, signing keys, scores or patient records. Its numerical tolerance
is diagnostic only: the canonical 29-case fixture validator is unchanged.
"""
from __future__ import annotations

import json
import math
from collections.abc import Mapping
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from ai.filesystem_security import ensure_private_directory
from ai.report_comparison import ABS_TOL, REL_TOL
from ai.research_facade import canonical_response_digest
from research.intake import offline_demo_card_mapping as cards
from research.intake import offline_fixture_pack as fixtures

MAX_DIFFS_PER_CASE = 20


def _type(value: Any) -> str:
    if value is None:
        return "null"
    if type(value) is bool:
        return "bool"
    if isinstance(value, Mapping):
        return "object"
    if isinstance(value, list):
        return "array"
    if type(value) in (int, float):
        return "number"
    if type(value) is str:
        return "string"
    return "other"


def _describe(expected: Any, observed: Any, path: str = "response") -> list[dict[str, Any]]:
    """Metadata-only diagnostics. No response *values* in the result."""
    result: list[dict[str, Any]] = []

    def visit(want: Any, got: Any, label: str) -> None:
        if len(result) >= MAX_DIFFS_PER_CASE:
            return
        wk, gk = _type(want), _type(got)
        if wk != gk:
            result.append({"field": label, "kind": "type_mismatch",
                           "expected_type": wk, "observed_type": gk})
            return
        if wk == "object":
            wanted, found = set(want), set(got)
            if wanted != found:
                # Do not reveal unexpected returned keys; they may contain secrets.
                result.append({"field": label, "kind": "field_set_mismatch",
                               "missing_count": len(wanted - found),
                               "unexpected_count": len(found - wanted)})
            for key in sorted(wanted & found):
                visit(want[key], got[key], f"{label}.{key}")
            return
        if wk == "array":
            if len(want) != len(got):
                result.append({"field": label, "kind": "array_length_mismatch",
                               "expected_length": len(want), "observed_length": len(got)})
            for idx in range(min(len(want), len(got))):
                visit(want[idx], got[idx], f"{label}[{idx}]")
            return
        if wk == "number":
            if want == got:
                return
            # Numeric deltas, never the actual frozen or observed score values.
            gap = abs(float(want) - float(got))
            allowed_score = ".score." in label and not label.endswith(
                (".exploratory_threshold",)
            )
            near = (
                math.isfinite(float(want)) and math.isfinite(float(got))
                and math.isclose(float(want), float(got),
                                 rel_tol=REL_TOL, abs_tol=ABS_TOL)
            ) if allowed_score else False
            result.append({"field": label, "kind": "score_numeric" if allowed_score else "numeric_semantic",
                           "absolute_delta": f"{gap:.3e}",
                           "within_existing_report_comparator_tolerance": near
                           if allowed_score else None})
            return
        if want != got:
            # Never print actual string, bool or null values.
            result.append({"field": label, "kind": "semantic_mismatch",
                           "value_type": wk})

    visit(expected, observed, path)
    return result


def diagnose() -> dict[str, Any]:
    """Use exact approved inputs and real synthetic replay, without writing files."""
    pack = json.loads(fixtures.PACK.read_text(encoding="utf-8"))
    if (pack["bindings"] != fixtures.bindings()
            or pack["requests"] != fixtures.inputs()
            or canonical_response_digest(pack) != fixtures.PACK_SHA256
            or cards.validate() != 29):
        raise ValueError("approved_source_integrity_failed")
    if len(pack["cases"]) != 29:
        raise ValueError("incomplete_reviewed_cases")

    mismatches: list[dict[str, Any]] = []
    with TemporaryDirectory() as temporary:
        sources = fixtures.sources(ensure_private_directory(Path(temporary)))
        for case in pack["cases"]:
            request = fixtures.materialize(pack["requests"][case["route"]], case["edits"])
            observed = fixtures.example(
                request, sources.get(case["route"], sources["blocked"])
            )
            if observed == case["expected"]:
                continue
            details = _describe(case["expected"], observed)
            mismatches.append({
                "case_id": case["id"], "expected_status": case["expected"]["status"],
                "different_field_count_limited": len(details),
                "fields": details,
            })
    return {
        "status": "EXACT_REPLAY" if not mismatches else "MISMATCH_FOUND",
        "evidence_scope": "SYNTHETIC_ONLY",
        "comparison_policy": "DIAGNOSTIC_ONLY_DOES_NOT_CHANGE_GOLDEN_ACCEPTANCE",
        "cases_checked": len(pack["cases"]),
        "cases_differing": len(mismatches),
        "mismatches": mismatches,
    }


def main() -> int:
    try:
        result = diagnose()
    except Exception as exc:
        # Do not print exception strings: they may contain protected locations.
        print(json.dumps({"status": "DIAGNOSTIC_REFUSED",
                          "exception_type": type(exc).__name__},
                         sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0 if result["status"] == "EXACT_REPLAY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
