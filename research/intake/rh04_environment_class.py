"""RH-04 Issue #132: read-only environment classification for the Golden Replay.

**This module is diagnostic only. It is NOT a golden comparator, NOT a
tolerance, NOT an acceptance policy, and it changes no production behaviour.**
The canonical 29-case validator (``research.intake.offline_fixture_pack``) keeps
its exact/deltas-only rules exactly as they are, and remains the authoritative
gate.

Purpose
-------
Issue #132 reported an *intermittent* failure of the frozen RH-04 Golden Replay
on ``da_a1_basic_clinical_v1`` / ``calibrated_log_odds``. The investigation in
``docs/rh04-issue132-acceptance-decision.md`` measured, on one Linux x86-64
platform with forced OpenBLAS core types, that the two SciPy L-BFGS-B
calibration parameters move by about 1 ULP between some OpenBLAS
dynamic-architecture kernel classes.

The historical CI runs did **not** record which kernel each job actually used.
This module closes that evidence gap: it records the kernel of the BLAS library
that is **already resident** in the process, plus the pinned versions, and it
classifies the observed replay.

Fail-closed contract (revised after independent review)
------------------------------------------------------
The previous revision derived ``EXACT_REPLAY`` from ``mismatches == []`` alone.
A malformed diagnostic envelope such as
``{"status": "MISMATCH_FOUND", "cases_checked": 0, "cases_differing": 1,
"mismatches": []}`` therefore produced ``EXACT_REPLAY`` and exit code ``0``.

The classifier now validates the **whole envelope** before believing anything in
it: status vocabulary, exact case count, integer types, mismatch-count
consistency, status/mismatch consistency, per-entry structure, per-field
structure, delta syntax and magnitude, and the environment metadata. Anything
that does not validate yields ``INVALID_DIAGNOSTIC`` or
``UNVERIFIED_ENVIRONMENT`` and **exit code 2**. Exit code ``0`` is reachable
only from a fully validated envelope with zero mismatches *and* a fully verified
environment record.

Classification vocabulary (deliberately closed)
-----------------------------------------------
``EXACT_REPLAY``
    Validated envelope, zero mismatches.
``EXPECTED_SINGLE_FIELD_DELTAS``
    Validated envelope whose only differences are ``calibrated_log_odds`` in
    the two enumerated executable cases, exactly one difference per case, each
    a strictly positive finite ``%.3e`` magnitude that the trusted diagnostic
    itself reported as inside the pre-existing AI-12.1 report-comparator band.
    **This is recorded evidence about one environment. It is not an acceptance
    decision, not a fix, and not a CI success.**
``UNEXPECTED_DRIFT``
    Validated envelope with any difference outside the enumeration above.
``INVALID_DIAGNOSTIC``
    The envelope is missing, malformed, inconsistent or incomplete.
``UNVERIFIED_ENVIRONMENT``
    The replay outcome may be classified, but the resident-BLAS kernels could
    not be established, so no environment-qualified statement can be made.

Exit codes: ``0`` exact **and** environment verified; ``1`` classified
single-field deltas **and** environment verified (supplemental evidence only —
never wire this to a passing CI job); ``2`` everything else.

BLAS identification (P1-C)
--------------------------
Earlier revisions used ``ctypes.CDLL(path, mode=ctypes.RTLD_GLOBAL)``. That
**loads a fresh private copy** of the library when it is not already resident,
so the reported kernel could belong to a library the numerical code never used.
Measured on this platform: after ``import numpy`` the packaged OpenBLAS is
already mapped, while after ``import scipy`` SciPy's OpenBLAS is **not** mapped
until SciPy performs a BLAS/LAPACK operation; the old code then mapped six
additional segments and reported a kernel from that private copy.

The module now uses ``ctypes.RTLD_NOLOAD`` exclusively, which returns a handle
**only if the object is already loaded** and otherwise raises without mapping
anything. Each reported value also carries the method that produced it
(``rtld_noload``, ``process_symbol`` or ``unverified``) so a reader can judge
the claim. A value obtained this way is evidence about the resident library; it
is not an assertion that the library is the one a *future* call will use.

Safety
------
* Synthetic-only. No input path is accepted.
* No file, directory, bundle or artifact is created inside the repository.
* The emitted JSON contains only kernel names, versions, booleans, small
  integers, and ``%.3e`` delta magnitudes produced by the trusted diagnostic.
  It never contains a score, coefficient, intercept, slope, feature value,
  record, signing key or filesystem path.
* Any unexpected exception is rendered as its *type* only.
"""
from __future__ import annotations

import ctypes
import glob
import json
import os
import platform
import re
from collections.abc import Mapping, Sequence
from typing import Any

# --------------------------------------------------------------------------- #
# Closed vocabularies and structural constants                               #
# --------------------------------------------------------------------------- #

DIAGNOSTIC_STATUSES: frozenset[str] = frozenset({"EXACT_REPLAY", "MISMATCH_FOUND"})

EXACT_REPLAY: str = "EXACT_REPLAY"
EXPECTED_SINGLE_FIELD_DELTAS: str = "EXPECTED_SINGLE_FIELD_DELTAS"
UNEXPECTED_DRIFT: str = "UNEXPECTED_DRIFT"
INVALID_DIAGNOSTIC: str = "INVALID_DIAGNOSTIC"
DIAGNOSTIC_REFUSED: str = "DIAGNOSTIC_REFUSED"

VERIFIED_ENVIRONMENT: str = "VERIFIED_ENVIRONMENT"
UNVERIFIED_ENVIRONMENT: str = "UNVERIFIED_ENVIRONMENT"

FIELD_VERDICTS: frozenset[str] = frozenset(
    {EXACT_REPLAY, EXPECTED_SINGLE_FIELD_DELTAS, UNEXPECTED_DRIFT, INVALID_DIAGNOSTIC}
)
ACCEPTABLE_FIELD_VERDICTS: frozenset[str] = frozenset(
    {EXACT_REPLAY, EXPECTED_SINGLE_FIELD_DELTAS}
)

#: The reviewed pack is exactly 29 cases; anything else is a different contract.
EXPECTED_CASE_COUNT: int = 29

#: The single permitted difference per case, and only for these two cases.
_LLO = "response.outcomes[0].score.calibrated_log_odds"
_EXPECTED_FIELDS: frozenset[tuple[str, str]] = frozenset(
    {("da_a2_resting_v1", _LLO), ("da_a1_basic_clinical_v1", _LLO)}
)

#: ``research.intake.diagnose_fixture_replay._describe`` formats a delta with
#: ``f"{gap:.3e}"``. Accept exactly that shape, and nothing looser: no sign
#: prefix, no locale separators, no bare floats, no NaN/inf spellings.
_DELTA_PATTERN = re.compile(r"^[0-9]\.[0-9]{3}e[+-][0-9]{2,3}$")

#: A resolved OpenBLAS core name is a short alphanumeric token (``SkylakeX``,
#: ``Sandybridge``, ``HASWELL``, ...). Anything else is treated as unverified.
_KERNEL_PATTERN = re.compile(r"^[A-Za-z0-9_]{1,40}$")

#: Environment keys that must be present and usable for a verified record.
_REQUIRED_ENVIRONMENT_KEYS: tuple[str, ...] = (
    "numpy_openblas_kernel",
    "scipy_openblas_kernel",
    "numpy_version",
    "scipy_version",
    "python",
    "architecture",
    "platform",
)

_RTLD_NOLOAD = getattr(os, "RTLD_NOLOAD", 0)


# --------------------------------------------------------------------------- #
# Resident-BLAS identification (never loads a new copy)                       #
# --------------------------------------------------------------------------- #


def _read_symbol(library: ctypes.CDLL, symbols: Sequence[str]) -> str | None:
    for symbol in symbols:
        if hasattr(library, symbol):
            getter = getattr(library, symbol)
            getter.restype = ctypes.c_char_p
            value = getter()
            if value:
                return value.decode("ascii", "replace")
    return None


def _resident_openblas_kernel(
    package_name: str,
    pattern: str,
    symbols: Sequence[str],
) -> tuple[str | None, str]:
    """Return ``(kernel_name, method)`` for an **already-resident** BLAS.

    ``method`` is one of ``"rtld_noload"`` (platform returned a handle for the
    already-mapped object), ``"process_symbol"`` (the symbol was resolvable in
    the current process image, so some already-loaded object exports it), or
    ``"unverified"`` (no evidence; the library is not resident, or the
    inspection failed).

    **No library is ever loaded by this function.** ``RTLD_NOLOAD`` never maps
    a new object; the ``CDLL(None)`` fallback addresses the running process
    image. If neither works the answer is honestly ``unverified``.
    """
    try:
        package = __import__(package_name)
        libs_dir = os.path.realpath(
            os.path.join(os.path.dirname(package.__file__), "..", f"{package_name}.libs")
        )
        candidates = sorted(glob.glob(os.path.join(libs_dir, pattern)))
    except (ImportError, AttributeError, OSError, TypeError, ValueError):
        return None, "unverified"

    for candidate in candidates:
        # Path 1: ask for a handle on the object only if it is already loaded.
        if _RTLD_NOLOAD:
            try:
                library = ctypes.CDLL(os.path.abspath(candidate), mode=_RTLD_NOLOAD)
            except OSError:
                library = None
            if library is not None:
                name = _read_symbol(library, symbols)
                if name:
                    return name, "rtld_noload"
        # Path 2: the symbol may already be resolvable process-wide.
        try:
            name = _read_symbol(ctypes.CDLL(None), symbols)
        except OSError:
            name = None
        if name:
            return name, "process_symbol"

    return None, "unverified"


def _init_numerical_libraries() -> None:
    """Import NumPy/SciPy so their resident state is what we then measure.

    NumPy loads its packaged OpenBLAS during import. SciPy loads its OpenBLAS
    lazily on first BLAS/LAPACK use, so after a bare ``import scipy`` the
    library may legitimately still be absent; that is reported as
    ``unverified`` rather than manufactured by loading a copy.
    """
    for module_name in ("numpy", "scipy"):
        try:
            __import__(module_name)
        except ImportError:  # pragma: no cover - pinned dependency for this tool
            pass


def environment_metadata() -> dict[str, Any]:
    """Pinned, non-identifying environment record. No paths, no hostnames."""
    _init_numerical_libraries()
    kernel_methods: dict[str, str] = {}

    numpy_kernel, numpy_method = _resident_openblas_kernel(
        "numpy",
        "libopenblas*.so",
        ("openblas_get_corename64_", "openblas_get_corename"),
    )
    kernel_methods["numpy_openblas_kernel"] = numpy_method

    scipy_kernel, scipy_method = _resident_openblas_kernel(
        "scipy", "libscipy_openblas*.so", ("scipy_openblas_get_corename",)
    )
    kernel_methods["scipy_openblas_kernel"] = scipy_method

    metadata: dict[str, Any] = {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "architecture": platform.machine(),
        "platform": platform.system(),
        "glibc": ".".join(str(part) for part in platform.libc_ver()[1:]) or None,
        "numpy_openblas_kernel": numpy_kernel,
        "scipy_openblas_kernel": scipy_kernel,
        "kernel_identification_method": kernel_methods,
        # Recorded for completeness ONLY. A requested core type may be silently
        # ignored or fall back; it is never treated as the resolved identity.
        "openblas_coretype_requested": os.environ.get("OPENBLAS_CORETYPE"),
        "openblas_num_threads": os.environ.get("OPENBLAS_NUM_THREADS"),
        "rtld_noload_available": bool(_RTLD_NOLOAD),
    }
    for module_name in ("numpy", "scipy", "sklearn"):
        try:
            metadata[f"{module_name}_version"] = __import__(module_name).__version__
        except (ImportError, AttributeError):  # pragma: no cover
            metadata[f"{module_name}_version"] = None
    return metadata


def environment_problems(metadata: Mapping[str, Any]) -> list[str]:
    """Return the reasons a metadata record cannot support an env claim.

    Empty list means the record is usable for a *supplemental* statement about
    which resident kernels produced this run. It does not certify anything
    about the machine beyond those kernels.
    """
    problems: list[str] = []
    if not isinstance(metadata, Mapping):
        return ["environment_not_a_mapping"]
    for key in _REQUIRED_ENVIRONMENT_KEYS:
        if key not in metadata:
            problems.append(f"{key}:missing")
    for key in ("numpy_openblas_kernel", "scipy_openblas_kernel"):
        value = metadata.get(key)
        if not isinstance(value, str) or not _KERNEL_PATTERN.fullmatch(value):
            problems.append(f"{key}:unresolved")
    methods = metadata.get("kernel_identification_method")
    if not isinstance(methods, Mapping):
        problems.append("kernel_identification_method:missing")
    else:
        for key in ("numpy_openblas_kernel", "scipy_openblas_kernel"):
            method = methods.get(key)
            if method not in {"rtld_noload", "process_symbol"}:
                problems.append(f"{key}:unverified_method")
    return sorted(set(problems))


# --------------------------------------------------------------------------- #
# Strict validation of the trusted diagnostic envelope                       #
# --------------------------------------------------------------------------- #


def _is_int(value: Any) -> bool:
    """``bool`` is an ``int`` subclass; a boolean must never satisfy a count."""
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_field(case_id: str, field: Any) -> list[str]:
    """Validate one ``_describe()`` field record. Returns problem tokens."""
    problems: list[str] = []
    if not isinstance(field, Mapping):
        return [f"{case_id}:field_not_a_mapping"]
    label = field.get("field")
    if not isinstance(label, str):
        problems.append(f"{case_id}:field_label_not_a_string")
        label = None
    if (case_id, label) not in _EXPECTED_FIELDS:
        problems.append(f"{case_id}:unexpected_field")
    if field.get("kind") != "score_numeric":
        problems.append(f"{case_id}:unexpected_kind")
    # Type-strict: the trusted diagnostic emits a real bool. ``1`` must fail.
    if field.get("within_existing_report_comparator_tolerance") is not True:
        problems.append(f"{case_id}:outside_report_tolerance")
    delta = field.get("absolute_delta")
    if not isinstance(delta, str) or not _DELTA_PATTERN.fullmatch(delta):
        problems.append(f"{case_id}:delta_not_a_magnitude")
    else:
        try:
            magnitude = float(delta)
        except ValueError:  # pragma: no cover - regex already excludes this
            magnitude = -1.0
        # A mismatch must be a strictly positive finite magnitude.
        if not (magnitude > 0.0 and magnitude != float("inf")):
            problems.append(f"{case_id}:delta_out_of_range")
    return problems


def _validate_entry_structure(entry: Any) -> list[str]:
    """Structural validity of one mismatch entry. Says nothing about expectations.

    The distinction matters: an envelope that faithfully reports an *unexpected*
    field is **valid** (and yields ``UNEXPECTED_DRIFT``); an envelope whose
    counts or types are incoherent is **invalid** (``INVALID_DIAGNOSTIC``).
    Conflating the two would mislabel a truthful diagnostic as broken.
    """
    if not isinstance(entry, Mapping):
        return ["entry_not_a_mapping"]
    case_id = entry.get("case_id")
    if not isinstance(case_id, str) or not case_id:
        return ["entry_case_id_invalid"]
    problems: list[str] = []
    fields = entry.get("fields")
    if not isinstance(fields, list):
        return [f"{case_id}:fields_not_a_list"]
    declared = entry.get("different_field_count_limited")
    if not _is_int(declared):
        problems.append(f"{case_id}:field_count_not_an_int")
    elif declared != len(fields):
        problems.append(f"{case_id}:field_count_inconsistent")
    for field in fields:
        if not isinstance(field, Mapping):
            problems.append(f"{case_id}:field_not_a_mapping")
    return problems


def _validate_entry_expectation(entry: Mapping[str, Any]) -> list[str]:
    """Semantic expectation for a well-formed entry: is this permitted drift?

    Everything here means "the diagnostic is telling us something we did not
    expect", never "the diagnostic is malformed".
    """
    case_id = entry.get("case_id")
    if not isinstance(case_id, str):  # pragma: no cover - structure caught it
        return []
    problems: list[str] = []
    fields = entry.get("fields")
    if not isinstance(fields, list):  # pragma: no cover - structure caught it
        return []
    # Exactly one difference per case is the entire evidentiary claim.
    if len(fields) != 1:
        problems.append(f"{case_id}:different_field_count")
    expected_status = entry.get("expected_status")
    if expected_status is not None and expected_status != "SYNTHETIC_RESULT":
        problems.append(f"{case_id}:unexpected_case_status")
    for field in fields:
        problems.extend(_validate_field(case_id, field))
    return problems


def _validate_entry(entry: Any) -> list[str]:
    """Full validation (structure + expectation). Used by ``classify_mismatches``."""
    structure = _validate_entry_structure(entry)
    if structure:
        return structure
    return _validate_entry_expectation(entry)


def _validate_envelope(result: Any) -> list[str]:
    """Validate the whole ``diagnose()`` envelope before trusting any part.

    This is the P0 fix: a verdict must never be derived from ``mismatches``
    alone. Returns problem tokens; empty means structurally sound.
    """
    if not isinstance(result, Mapping):
        return ["diagnostic_not_a_mapping"]
    problems: list[str] = []

    for key in ("status", "cases_checked", "cases_differing", "mismatches"):
        if key not in result:
            problems.append(f"envelope:{key}:missing")

    status = result.get("status")
    if not isinstance(status, str) or status not in DIAGNOSTIC_STATUSES:
        problems.append("envelope:status:not_in_vocabulary")

    checked = result.get("cases_checked")
    if not _is_int(checked):
        problems.append("envelope:cases_checked:not_an_int")
    elif checked != EXPECTED_CASE_COUNT:
        problems.append("envelope:cases_checked:wrong_case_count")

    differing = result.get("cases_differing")
    if not _is_int(differing):
        problems.append("envelope:cases_differing:not_an_int")
    elif differing < 0:
        problems.append("envelope:cases_differing:negative")

    mismatches = result.get("mismatches")
    if not isinstance(mismatches, list):
        problems.append("envelope:mismatches:not_a_list")
        return problems

    if _is_int(differing) and differing != len(mismatches):
        problems.append("envelope:cases_differing:inconsistent_with_entries")

    # Status must agree with the mismatch list, in both directions.
    if status in DIAGNOSTIC_STATUSES:
        if status == "EXACT_REPLAY" and mismatches:
            problems.append("envelope:status:exact_with_mismatches")
        if status == "MISMATCH_FOUND" and not mismatches:
            problems.append("envelope:status:mismatch_without_entries")

    seen: set[str] = set()
    for entry in mismatches:
        problems.extend(_validate_entry_structure(entry))
        if isinstance(entry, Mapping):
            case_id = entry.get("case_id")
            if isinstance(case_id, str):
                if case_id in seen:
                    # One entry per case: duplicates would multiply a claim.
                    problems.append(f"{case_id}:duplicate_case_id")
                seen.add(case_id)
    return problems


def classify_mismatches(mismatches: Any) -> tuple[str, list[str]]:
    """Classify a bare mismatch list (kept for focused unit testing).

    Production callers must use :func:`classify`, which validates the whole
    envelope first. This helper applies the same per-entry rules and rejects
    duplicates, so it can never widen what :func:`classify` accepts.
    """
    if not isinstance(mismatches, list):
        return INVALID_DIAGNOSTIC, ["mismatches:not_a_list"]
    if not mismatches:
        return EXACT_REPLAY, []
    structural: list[str] = []
    semantic: list[str] = []
    seen: set[str] = set()
    for entry in mismatches:
        entry_problems = _validate_entry_structure(entry)
        structural.extend(entry_problems)
        # Only a structurally sound entry can be judged against expectations;
        # running the semantic pass on a broken entry would raise or double-count.
        if not entry_problems:
            semantic.extend(_validate_entry_expectation(entry))
        if isinstance(entry, Mapping):
            case_id = entry.get("case_id")
            if isinstance(case_id, str):
                if case_id in seen:
                    # A repeated case id is incoherent *structure*, not merely
                    # an unexpected value: it would multiply one claim into two.
                    structural.append(f"{case_id}:duplicate_case_id")
                seen.add(case_id)
    if structural:
        return INVALID_DIAGNOSTIC, sorted(set(structural + semantic))
    if semantic:
        return UNEXPECTED_DRIFT, sorted(set(semantic))
    return EXPECTED_SINGLE_FIELD_DELTAS, []


# --------------------------------------------------------------------------- #
# Public classification                                                      #
# --------------------------------------------------------------------------- #


def _payload(
    *,
    field_verdict: str,
    environment_verdict: str,
    field_reasons: Sequence[str],
    environment_reasons: Sequence[str],
    metadata: Mapping[str, Any],
    result: Mapping[str, Any] | None,
    exception_type: str | None = None,
) -> dict[str, Any]:
    differing_case_ids: list[str] = []
    if isinstance(result, Mapping):
        mismatches = result.get("mismatches")
        if isinstance(mismatches, list):
            ids = {
                entry.get("case_id")
                for entry in mismatches
                if isinstance(entry, Mapping) and isinstance(entry.get("case_id"), str)
            }
            differing_case_ids = sorted(ids)
    payload: dict[str, Any] = {
        "field_verdict": field_verdict,
        "environment_verdict": environment_verdict,
        "field_reasons": sorted(set(field_reasons)),
        "environment_reasons": sorted(set(environment_reasons)),
        "replay_verdict": result.get("status") if isinstance(result, Mapping) else None,
        "cases_checked": result.get("cases_checked") if isinstance(result, Mapping) else None,
        "cases_differing": (
            result.get("cases_differing") if isinstance(result, Mapping) else None
        ),
        "differing_case_ids": differing_case_ids,
        "environment": dict(metadata),
        "comparison_policy": "DIAGNOSTIC_ONLY_DOES_NOT_CHANGE_GOLDEN_ACCEPTANCE",
        "acceptance_authority": "canonical_29_case_comparator_unchanged",
        "note": (
            "Read-only supplemental evidence. EXPECTED_SINGLE_FIELD_DELTAS records "
            "what one environment produced; it is not an acceptance decision, not a "
            "fix, and not a CI success. The canonical strict Golden Replay gate is "
            "unchanged and remains authoritative. Issue #132 stays open until an "
            "owner-ratified V2 reference exists."
        ),
        "issue": 132,
    }
    if exception_type is not None:
        payload["exception_type"] = exception_type
    return payload


def classify() -> dict[str, Any]:
    """Run the reviewed read-only replay and classify it, fail-closed.

    Never raises for an expected condition; a refusal is reported as a verdict.
    """
    from research.intake import diagnose_fixture_replay

    metadata = environment_metadata()
    env_reasons = environment_problems(metadata)
    env_verdict = UNVERIFIED_ENVIRONMENT if env_reasons else VERIFIED_ENVIRONMENT

    try:
        result = diagnose_fixture_replay.diagnose()
    except Exception as exc:  # noqa: BLE001 - never render the message
        return _payload(
            field_verdict=DIAGNOSTIC_REFUSED,
            environment_verdict=env_verdict,
            field_reasons=["diagnostic_raised"],
            environment_reasons=env_reasons,
            metadata=metadata,
            result=None,
            exception_type=type(exc).__name__,
        )

    problems = _validate_envelope(result)
    if problems:
        return _payload(
            field_verdict=INVALID_DIAGNOSTIC,
            environment_verdict=env_verdict,
            field_reasons=problems,
            environment_reasons=env_reasons,
            metadata=metadata,
            result=result if isinstance(result, Mapping) else None,
        )

    verdict, reasons = classify_mismatches(result["mismatches"])
    return _payload(
        field_verdict=verdict,
        environment_verdict=env_verdict,
        field_reasons=reasons,
        environment_reasons=env_reasons,
        metadata=metadata,
        result=result,
    )


def exit_code(payload: Mapping[str, Any]) -> int:
    """Map a payload to an exit code. ``0`` requires verified everything.

    ``1`` marks classified single-field deltas: supplemental evidence for a
    human. **A CI job must not treat ``1`` as success**; the canonical strict
    Golden Replay gate stays authoritative and stays red on such a host.
    """
    if payload.get("environment_verdict") != VERIFIED_ENVIRONMENT:
        return 2
    verdict = payload.get("field_verdict")
    if verdict == EXACT_REPLAY:
        return 0
    if verdict == EXPECTED_SINGLE_FIELD_DELTAS:
        return 1
    return 2


def main() -> int:
    try:
        payload = classify()
    except Exception as exc:  # noqa: BLE001 - see module docstring
        print(
            json.dumps(
                {"status": DIAGNOSTIC_REFUSED, "exception_type": type(exc).__name__},
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False))
    return exit_code(payload)


if __name__ == "__main__":
    raise SystemExit(main())
