"""RH-04 Issue #132: read-only environment classification for the Golden Replay.

**This module is diagnostic only. It is not a golden comparator, not a
tolerance, not an acceptance policy, and it changes no production behaviour.**
The canonical 29-case validator (``research.intake.offline_fixture_pack``) keeps
its exact/deltas-only rules exactly as they are.

Purpose
-------
Issue #132 reported an *intermittent* failure of the frozen RH-04 Golden Replay
on ``da_a1_basic_clinical_v1`` / ``calibrated_log_odds``. The investigation
recorded in ``docs/rh04-issue132-acceptance-decision.md`` established that the
intermittency is **host heterogeneity**, not nondeterminism: the two SciPy
L-BFGS-B calibration parameters depend on the OpenBLAS dynamic-architecture
kernel that the *host CPU* selects, and the frozen reference is exact only on
the kernel family that generated it.

The historical evidence for which kernel a GitHub-hosted runner picked was
**not recorded**, which is why the same commit could fail and then pass. This
module closes that evidence gap without touching any contract: it reports the
*actually resolved* kernels (not the ``OPENBLAS_CORETYPE`` string, which can be
silently ignored or fall back — see the ``Zen`` -> ``Haswell`` observation in
the decision document), the pinned library versions, and a *classification* of
the replay it observes.

Safety
------
* Synthetic-only. No input path is accepted; nothing is read from disk except
  the reviewed in-repo fixture and the reviewed diagnostic helpers.
* No file, directory, bundle or artifact is created inside the repository.
* The emitted JSON contains **only** kernel names, library/platform versions,
  booleans, small integer counts and *magnitudes* of numeric deltas. It never
  contains a score, coefficient, intercept, slope, feature value, record, key or
  filesystem path.
* Any unexpected exception is rendered as its *type* only, because an exception
  string can embed a protected path or value.

Classification vocabulary (deliberately closed)
-----------------------------------------------
``EXACT_REPLAY``
    The frozen pack reproduced bit-for-bit.
``EXPECTED_SINGLE_FIELD_DELTAS``
    The only differences are ``calibrated_log_odds`` in the two enumerated
    executable cases, every one of them inside the pre-existing AI-12.1 report
    comparator band. This is the *expected* outcome on a non-golden dispatch
    class; it is reported, never silently accepted as a fix.
``UNEXPECTED_DRIFT``
    Anything else. Fails closed.

This module never decides acceptance. It produces evidence for a human.
"""
from __future__ import annotations

import ctypes
import glob
import json
import os
import platform
import sys
from typing import Any

# The two executable ``SYNTHETIC_RESULT`` cases whose calibrated log-odds are
# derived from the two-parameter calibration fit. ``da_a2_resting_v1`` already
# carries the single pre-existing approved comparator exception; the UCI-412
# case does not, and must not gain one from this module.
_EXPECTED_FIELDS: frozenset[tuple[str, str]] = frozenset(
    {
        ("da_a2_resting_v1", "response.outcomes[0].score.calibrated_log_odds"),
        ("da_a1_basic_clinical_v1", "response.outcomes[0].score.calibrated_log_odds"),
    }
)


def _load_openblas_kernel(package_name: str, pattern: str, symbols: tuple[str, ...]):
    """Return the resolved OpenBLAS core name for a packaged BLAS, or ``None``.

    The library is loaded only to read a diagnostic string. It is already loaded
    by the parent package in every realistic call path; the RTLD_GLOBAL dance
    below merely satisfies the ``libgfortran``/``libquadmath`` sonames that the
    wheel's own ``*.libs`` directory provides.
    """
    try:
        package = __import__(package_name)
        libs_dir = os.path.join(
            os.path.dirname(package.__file__), "..", f"{package_name}.libs"
        )
        for dependency in sorted(glob.glob(os.path.join(libs_dir, "*.so*"))):
            try:
                ctypes.CDLL(os.path.abspath(dependency), mode=ctypes.RTLD_GLOBAL)
            except OSError:
                pass
        for candidate in sorted(glob.glob(os.path.join(libs_dir, pattern))):
            library = ctypes.CDLL(os.path.abspath(candidate), mode=ctypes.RTLD_GLOBAL)
            for symbol in symbols:
                if hasattr(library, symbol):
                    getter = getattr(library, symbol)
                    getter.restype = ctypes.c_char_p
                    value = getter()
                    return value.decode("ascii", "replace") if value else None
    except (ImportError, OSError, AttributeError, ValueError):
        return None
    return None


def environment_metadata() -> dict[str, Any]:
    """Pinned, non-identifying environment record. No paths, no hostnames."""
    metadata: dict[str, Any] = {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "architecture": platform.machine(),
        "platform": platform.system(),
        "glibc": ".".join(str(part) for part in platform.libc_ver()[1:]) or None,
        "numpy_openblas_kernel": _load_openblas_kernel(
            "numpy",
            "libopenblas*.so",
            ("openblas_get_corename64_", "openblas_get_corename"),
        ),
        "scipy_openblas_kernel": _load_openblas_kernel(
            "scipy", "libscipy_openblas*.so", ("scipy_openblas_get_corename",)
        ),
        # Recorded for completeness ONLY. The resolved kernel names above are the
        # authoritative identity: a forced core type may be silently ignored.
        "openblas_coretype_requested": os.environ.get("OPENBLAS_CORETYPE"),
        "openblas_num_threads": os.environ.get("OPENBLAS_NUM_THREADS"),
    }
    for module_name in ("numpy", "scipy", "sklearn"):
        try:
            metadata[f"{module_name}_version"] = __import__(module_name).__version__
        except ImportError:  # pragma: no cover - dependency is pinned for this tool
            metadata[f"{module_name}_version"] = None
    return metadata


def classify_mismatches(mismatches: list[dict[str, Any]]) -> tuple[str, list[str]]:
    """Classify a ``diagnose_fixture_replay.diagnose()`` mismatch list.

    Returns ``(verdict, unexpected_reasons)``. Pure function: no I/O, no imports
    of the diagnostic, fully unit-testable with synthetic inputs.

    The rule is intentionally the strictest one that still describes the
    measured evidence: exactly the enumerated ``(case, field)`` pairs, exactly
    one difference per case, kind ``score_numeric``, finite numbers, and inside
    the pre-existing report comparator band. Everything else is a reason.
    """
    if not mismatches:
        return "EXACT_REPLAY", []
    reasons: list[str] = []
    for entry in mismatches:
        case_id = entry.get("case_id")
        fields = entry.get("fields") or []
        if len(fields) != 1:
            reasons.append(f"{case_id}:different_field_count")
        for field in fields:
            label = field.get("field")
            if (case_id, label) not in _EXPECTED_FIELDS:
                reasons.append(f"{case_id}:unexpected_field")
            if field.get("kind") != "score_numeric":
                reasons.append(f"{case_id}:unexpected_kind")
            if field.get("within_existing_report_comparator_tolerance") is not True:
                reasons.append(f"{case_id}:outside_report_tolerance")
            # Magnitude only: the diagnostic already formats a delta as "%.3e".
            delta = field.get("absolute_delta")
            if not isinstance(delta, str):
                reasons.append(f"{case_id}:delta_not_reported")
    if reasons:
        return "UNEXPECTED_DRIFT", sorted(set(reasons))
    return "EXPECTED_SINGLE_FIELD_DELTAS", []


def classify() -> dict[str, Any]:
    """Run the reviewed read-only replay and classify the observed outcome.

    Never raises for an expected condition; a refusal is reported as a verdict.
    """
    from research.intake import diagnose_fixture_replay

    metadata = environment_metadata()
    try:
        result = diagnose_fixture_replay.diagnose()
    except Exception as exc:  # noqa: BLE001 - never render the message
        return {
            "status": "DIAGNOSTIC_REFUSED",
            "exception_type": type(exc).__name__,
            "environment": metadata,
            "note": "Read-only classification only; the canonical comparator is unchanged.",
        }

    verdict, reasons = classify_mismatches(result.get("mismatches") or [])
    return {
        "status": verdict,
        "unexpected_reasons": reasons,
        "replay_verdict": result.get("status"),
        "cases_checked": result.get("cases_checked"),
        "cases_differing": result.get("cases_differing"),
        "differing_case_ids": sorted(
            {entry.get("case_id") for entry in (result.get("mismatches") or [])}
        ),
        "environment": metadata,
        "comparison_policy": "DIAGNOSTIC_ONLY_DOES_NOT_CHANGE_GOLDEN_ACCEPTANCE",
        "note": (
            "Read-only classification only. EXPECTED_SINGLE_FIELD_DELTAS is not a "
            "fix, an acceptance decision, or a tolerance change; the canonical "
            "29-case comparator remains unchanged and Issue #132 stays open until "
            "an owner-ratified V2 reference exists."
        ),
        "issue": 132,
    }


def main() -> int:
    try:
        payload = classify()
    except Exception as exc:  # noqa: BLE001 - see module docstring
        print(
            json.dumps(
                {"status": "DIAGNOSTIC_REFUSED", "exception_type": type(exc).__name__},
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False))
    if payload["status"] == "EXACT_REPLAY":
        return 0
    if payload["status"] == "EXPECTED_SINGLE_FIELD_DELTAS":
        # Distinct exit code: a classified, expected environment outcome is NOT
        # the same result as a bit-exact replay, and CI must be able to tell.
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
