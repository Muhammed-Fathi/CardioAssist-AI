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
    {
        EXACT_REPLAY,
        EXPECTED_SINGLE_FIELD_DELTAS,
        UNEXPECTED_DRIFT,
        INVALID_DIAGNOSTIC,
        DIAGNOSTIC_REFUSED,
    }
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

#: A frozen case id is a short lowercase token. Anything else is not echoed.
_CASE_ID_PATTERN = re.compile(r"^[a-z0-9_]{1,64}$")

#: A release version such as ``1.26.4``. Rejects ``None``, ``""``, ``"lol"``.
_VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+([A-Za-z0-9.+!-]*)$")

#: ``OPENBLAS_NUM_THREADS`` must be a small non-negative integer, never free text.
_THREADS_PATTERN = re.compile(r"^[0-9]{1,4}$")

#: A reason token is ``case_id:reason`` / ``envelope:key:reason`` / ``plain``.
#: Deliberately excludes ``/``, spaces, quotes and newlines so no path, command
#: line or credential fragment can survive into the printed payload.
_SAFE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.:\[\]]{1,120}$")

#: Emitted in place of any value that does not match its allowlisted shape.
REDACTED = "redacted_unexpected_format"

#: Versions this tool's claims are scoped to (mirrors the pinned requirement
#: files). A different numeric stack is reported, never silently accepted.
PINNED_VERSIONS: Mapping[str, str] = {
    "numpy_version": "1.26.4",
    "scipy_version": "1.15.3",
    "sklearn_version": "1.6.1",
}


# --------------------------------------------------------------------------- #
# Sanitisation: nothing untrusted is ever printed verbatim                   #
# --------------------------------------------------------------------------- #

#: The complete set of keys the printed payload may contain. A closed
#: vocabulary means a poisoned envelope can never introduce a new field.
_ALLOWED_PAYLOAD_KEYS: frozenset[str] = frozenset(
    {
        "field_verdict",
        "environment_verdict",
        "field_reasons",
        "environment_reasons",
        "replay_verdict",
        "cases_checked",
        "cases_differing",
        "differing_case_ids",
        "environment",
        "kernel_snapshot",
        "version_drift",
        "comparison_policy",
        "acceptance_authority",
        "note",
        "issue",
        "exception_type",
    }
)

#: The complete set of keys the environment record may contain.
_ALLOWED_ENVIRONMENT_KEYS: frozenset[str] = frozenset(
    {
        "python",
        "implementation",
        "architecture",
        "platform",
        "glibc",
        "numpy_openblas_kernel",
        "scipy_openblas_kernel",
        "kernel_identification_method",
        "openblas_coretype_requested",
        "openblas_num_threads",
        "rtld_noload_available",
        "numpy_version",
        "scipy_version",
        "sklearn_version",
    }
)


def _safe_token(value: Any) -> str | None:
    """Return ``value`` only if it is a short allowlisted token, else ``None``.

    Reason strings are derived from *our own* validation, but they embed the
    ``case_id`` that came from the untrusted envelope, so they are sanitised
    too rather than assumed safe.
    """
    if not isinstance(value, str):
        return None
    return value if _SAFE_TOKEN_PATTERN.fullmatch(value) else None


def _safe_reasons(reasons: Sequence[str]) -> list[str]:
    """Sanitised, sorted, de-duplicated reason tokens.

    A token that fails the allowlist is replaced by :data:`REDACTED` — the
    count of findings is preserved without ever echoing the offending text.
    """
    cleaned = {_safe_token(reason) or REDACTED for reason in reasons}
    return sorted(cleaned)


def _safe_count(value: Any) -> int | None:
    """Emit an integer count only; a string/float/bool becomes ``None``.

    This is the P0 fix: a poisoned ``cases_checked="/secret"`` must not appear
    in the report even though the envelope was rejected *because* of it.
    """
    return value if _is_int(value) else None


def _safe_status(value: Any) -> str | None:
    """Emit only a token from the closed diagnostic vocabulary."""
    return value if isinstance(value, str) and value in DIAGNOSTIC_STATUSES else None


def _safe_case_ids(mismatches: Any) -> list[str]:
    """Echo only frozen-looking case ids, and only short ones."""
    if not isinstance(mismatches, list):
        return []
    found: set[str] = set()
    for entry in mismatches:
        if isinstance(entry, Mapping):
            case_id = entry.get("case_id")
            if isinstance(case_id, str) and _CASE_ID_PATTERN.fullmatch(case_id):
                found.add(case_id)
    return sorted(found)


def _sanitize_environment(metadata: Mapping[str, Any]) -> dict[str, Any]:
    """Project an environment record onto the closed, type-checked vocabulary.

    Version strings, kernel names and platform tokens are allowlisted; anything
    that does not match — including a path or credential smuggled into
    ``OPENBLAS_CORETYPE`` — becomes ``None`` or :data:`REDACTED`. Unknown keys
    are dropped entirely, so the printed record cannot grow.
    """
    safe: dict[str, Any] = {}
    if not isinstance(metadata, Mapping):
        return safe

    for key in ("python", "architecture", "platform", "glibc"):
        value = metadata.get(key)
        safe[key] = value if isinstance(value, str) and _VERSION_PATTERN.fullmatch(
            value
        ) or (isinstance(value, str) and _SAFE_TOKEN_PATTERN.fullmatch(value)) else None

    value = metadata.get("implementation")
    safe["implementation"] = value if value in {"CPython", "PyPy"} else None

    for key in ("numpy_openblas_kernel", "scipy_openblas_kernel"):
        value = metadata.get(key)
        safe[key] = (
            value
            if isinstance(value, str) and _KERNEL_PATTERN.fullmatch(value)
            else None
        )

    methods = metadata.get("kernel_identification_method")
    safe_methods: dict[str, str | None] = {}
    for key in ("numpy_openblas_kernel", "scipy_openblas_kernel"):
        method = methods.get(key) if isinstance(methods, Mapping) else None
        safe_methods[key] = (
            method if method in {"rtld_noload", "process_symbol", "unverified"} else None
        )
    safe["kernel_identification_method"] = safe_methods

    for key in ("numpy_version", "scipy_version", "sklearn_version"):
        value = metadata.get(key)
        safe[key] = (
            value
            if isinstance(value, str) and _VERSION_PATTERN.fullmatch(value)
            else None
        )

    # Free-text environment values are NEVER echoed. They are reduced to a
    # closed token describing only whether they looked well-formed.
    coretype = metadata.get("openblas_coretype_requested")
    safe["openblas_coretype_requested"] = (
        "set_and_wellformed"
        if isinstance(coretype, str) and _KERNEL_PATTERN.fullmatch(coretype)
        else ("set_malformed" if coretype is not None else None)
    )
    threads = metadata.get("openblas_num_threads")
    safe["openblas_num_threads"] = (
        "set_and_wellformed"
        if isinstance(threads, str) and _THREADS_PATTERN.fullmatch(threads)
        else ("set_malformed" if threads is not None else None)
    )

    rtld = metadata.get("rtld_noload_available")
    safe["rtld_noload_available"] = rtld if isinstance(rtld, bool) else None
    return safe


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


def environment_metadata(probe: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Pinned, non-identifying environment record. No paths, no hostnames.

    ``probe`` lets the caller supply an already-taken kernel snapshot so the
    record reflects a **defined moment** rather than whatever happens to be
    resident when this function is called. When omitted, a fresh probe is taken
    here; that is convenient for tests but callers with a timing requirement
    should pass one explicitly.
    """
    _init_numerical_libraries()
    snapshot = dict(probe) if isinstance(probe, Mapping) else _kernel_probe()
    methods = snapshot.get("kernel_identification_method")
    if not isinstance(methods, Mapping):
        methods = {}

    metadata: dict[str, Any] = {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "architecture": platform.machine(),
        "platform": platform.system(),
        "glibc": ".".join(str(part) for part in platform.libc_ver()[1:]) or None,
        "numpy_openblas_kernel": snapshot.get("numpy_openblas_kernel"),
        "scipy_openblas_kernel": snapshot.get("scipy_openblas_kernel"),
        "kernel_identification_method": {
            "numpy_openblas_kernel": methods.get("numpy_openblas_kernel"),
            "scipy_openblas_kernel": methods.get("scipy_openblas_kernel"),
        },
        # Recorded for completeness ONLY, and never printed verbatim: the
        # printed form is reduced to set_and_wellformed / set_malformed / null.
        # A requested core type may be silently ignored or fall back; it is
        # never treated as, or reported as, the resolved identity.
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
    about the machine beyond those kernels, and it does not validate that the
    numerical stack is the pinned one — a differing stack is reported
    separately as ``*_version:not_pinned`` and is not by itself a failure.

    The pre-review revision only checked that version keys *existed*, so
    ``numpy_version=None`` still produced ``VERIFIED_ENVIRONMENT``. Values are
    now type- and format-checked.
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

    # Versions must be usable version strings, not merely present keys.
    for key in ("numpy_version", "scipy_version"):
        value = metadata.get(key)
        if not isinstance(value, str) or not _VERSION_PATTERN.fullmatch(value):
            problems.append(f"{key}:not_a_version")

    for key in ("python", "architecture", "platform"):
        value = metadata.get(key)
        if not isinstance(value, str) or not value.strip():
            problems.append(f"{key}:blank_or_not_a_string")

    return sorted(set(problems))


def pinned_version_drift(metadata: Mapping[str, Any]) -> list[str]:
    """Report a numerical stack that differs from the pinned requirements.

    Recorded as evidence, **not** as a failure: a V1 replay on a different
    NumPy/SciPy build is precisely the situation the tool exists to describe,
    so refusing to classify it would defeat the purpose.
    """
    drift: list[str] = []
    for key, expected in PINNED_VERSIONS.items():
        observed = metadata.get(key)
        if isinstance(observed, str) and observed != expected:
            drift.append(f"{key}:not_pinned")
    return sorted(drift)


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
    kernel_snapshot: Mapping[str, Any] | None = None,
    version_drift: Sequence[str] | None = None,
    exception_type: str | None = None,
) -> dict[str, Any]:
    """Build the printed payload. Every value is sanitised, never echoed.

    The pre-review revision copied ``result["status"]``, ``cases_checked`` and
    ``cases_differing`` straight through, so an envelope rejected *for* being
    malformed could still print the malformed value (e.g. a filesystem path
    placed in ``cases_checked``). Nothing from ``result`` reaches the output
    now except values that independently satisfy a strict allowlist.
    """
    result_mapping = result if isinstance(result, Mapping) else None
    payload: dict[str, Any] = {
        "field_verdict": field_verdict if field_verdict in FIELD_VERDICTS else INVALID_DIAGNOSTIC,
        "environment_verdict": (
            environment_verdict
            if environment_verdict in {VERIFIED_ENVIRONMENT, UNVERIFIED_ENVIRONMENT}
            else UNVERIFIED_ENVIRONMENT
        ),
        "field_reasons": _safe_reasons(field_reasons),
        "environment_reasons": _safe_reasons(environment_reasons),
        "replay_verdict": (
            _safe_status(result_mapping.get("status")) if result_mapping else None
        ),
        "cases_checked": (
            _safe_count(result_mapping.get("cases_checked")) if result_mapping else None
        ),
        "cases_differing": (
            _safe_count(result_mapping.get("cases_differing")) if result_mapping else None
        ),
        "differing_case_ids": (
            _safe_case_ids(result_mapping.get("mismatches")) if result_mapping else []
        ),
        "environment": _sanitize_environment(metadata),
        "kernel_snapshot": dict(kernel_snapshot) if isinstance(kernel_snapshot, Mapping) else {},
        "version_drift": _safe_reasons(version_drift or []),
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
        # Only the exception *class name* is recorded, and only if it is a name.
        safe_exc = exception_type if (
            isinstance(exception_type, str) and _KERNEL_PATTERN.fullmatch(exception_type)
        ) else REDACTED
        payload["exception_type"] = safe_exc
    assert set(payload) <= _ALLOWED_PAYLOAD_KEYS, "payload grew beyond its vocabulary"
    return payload


def _kernel_probe() -> dict[str, Any]:
    """Read the *currently resident* kernels without loading anything."""
    numpy_kernel, numpy_method = _resident_openblas_kernel(
        "numpy",
        "libopenblas*.so",
        ("openblas_get_corename64_", "openblas_get_corename"),
    )
    scipy_kernel, scipy_method = _resident_openblas_kernel(
        "scipy", "libscipy_openblas*.so", ("scipy_openblas_get_corename",)
    )
    return {
        "numpy_openblas_kernel": numpy_kernel,
        "scipy_openblas_kernel": scipy_kernel,
        "kernel_identification_method": {
            "numpy_openblas_kernel": numpy_method,
            "scipy_openblas_kernel": scipy_method,
        },
    }


def classify() -> dict[str, Any]:
    """Run the reviewed read-only replay and classify it, fail-closed.

    Snapshot timing (revised after independent review)
    -------------------------------------------------
    The pre-review revision probed the kernels *before* calling ``diagnose()``.
    That is the wrong moment for SciPy: SciPy's OpenBLAS is mapped lazily by the
    first BLAS/LAPACK call, so a probe taken before the replay reports
    ``unverified`` — and the previous version then appeared to succeed only
    because importing ``ai.research_facade`` happened to pull in
    ``scipy.linalg`` as a transitive side effect.

    Two snapshots are now taken and labelled separately:

    ``pre_replay``  — what is resident before any replay work at all;
    ``post_replay`` — what is resident after the replay has actually used BLAS.

    ``post_replay`` is the snapshot that can support a statement about *which
    kernels produced this run*, and it is still taken with ``RTLD_NOLOAD`` /
    ``CDLL(None)``, so it never loads a copy and never weakens the replay.
    Neither snapshot is proof that the kernel named is the one every subsequent
    computation will use (see ``G-08``); both are scoped to this process.
    """
    # Snapshot 1 MUST be taken before the diagnostic module is imported at all:
    # importing ``research.intake.diagnose_fixture_replay`` pulls in
    # ``ai.research_facade``, which transitively imports ``scipy.linalg`` and
    # therefore maps SciPy's OpenBLAS. Probing after that import would report a
    # kernel that no replay work had used yet.
    pre_snapshot = _kernel_probe()

    from research.intake import diagnose_fixture_replay

    metadata = environment_metadata(probe=pre_snapshot)
    env_reasons = environment_problems(metadata)
    env_verdict = UNVERIFIED_ENVIRONMENT if env_reasons else VERIFIED_ENVIRONMENT

    try:
        result = diagnose_fixture_replay.diagnose()
    except Exception as exc:  # noqa: BLE001 - never render the message
        post_snapshot = _kernel_probe()
        return _payload(
            field_verdict=DIAGNOSTIC_REFUSED,
            environment_verdict=env_verdict,
            field_reasons=["diagnostic_raised"],
            environment_reasons=env_reasons,
            metadata=_merge_post_snapshot(metadata, post_snapshot),
            result=None,
            kernel_snapshot=_labelled_snapshots(pre_snapshot, post_snapshot),
            version_drift=pinned_version_drift(metadata),
            exception_type=type(exc).__name__,
        )

    # Snapshot 2: after the replay has exercised SciPy's BLAS for real.
    post_snapshot = _kernel_probe()
    # The *authoritative* environment record is the post-replay one: only it can
    # see a lazily loaded BLAS. ``metadata`` supplies everything except kernel
    # identity, which is adopted from ``post_snapshot``.
    merged = _merge_post_snapshot(metadata, post_snapshot)
    post_reasons = environment_problems(merged)
    env_verdict = UNVERIFIED_ENVIRONMENT if post_reasons else VERIFIED_ENVIRONMENT

    problems = _validate_envelope(result)
    if problems:
        return _payload(
            field_verdict=INVALID_DIAGNOSTIC,
            environment_verdict=env_verdict,
            field_reasons=problems,
            environment_reasons=post_reasons,
            metadata=merged,
            result=result if isinstance(result, Mapping) else None,
            kernel_snapshot=_labelled_snapshots(pre_snapshot, post_snapshot),
            version_drift=pinned_version_drift(merged),
        )

    verdict, reasons = classify_mismatches(result["mismatches"])
    return _payload(
        field_verdict=verdict,
        environment_verdict=env_verdict,
        field_reasons=reasons,
        environment_reasons=post_reasons,
        metadata=merged,
        result=result,
        kernel_snapshot=_labelled_snapshots(pre_snapshot, post_snapshot),
        version_drift=pinned_version_drift(merged),
    )


def _merge_post_snapshot(
    metadata: Mapping[str, Any], post_snapshot: Mapping[str, Any]
) -> dict[str, Any]:
    """Environment record with kernel identity taken from the post-replay probe.

    Versions and platform tokens are unchanged; only the kernel fields are
    replaced, because only the post-replay probe can see a lazily loaded BLAS.
    """
    merged = dict(metadata)
    methods = post_snapshot.get("kernel_identification_method")
    safe_methods = dict(methods) if isinstance(methods, Mapping) else {}
    declared = metadata.get("kernel_identification_method")
    # Distinguish "absent" from "present but empty": an absent map must stay
    # absent so ``environment_problems`` can still report it as missing.
    if isinstance(declared, Mapping):
        declared_methods: dict[str, Any] = dict(declared)
    else:
        declared_methods = {}

    for key in ("numpy_openblas_kernel", "scipy_openblas_kernel"):
        resolved = post_snapshot.get(key)
        if isinstance(resolved, str) and _KERNEL_PATTERN.fullmatch(resolved):
            # A real post-replay observation always wins.
            merged[key] = resolved
            merged_methods_value = safe_methods.get(key)
            if merged_methods_value in {"rtld_noload", "process_symbol"}:
                declared_methods[key] = merged_methods_value
        else:
            # Nothing observed after the replay: keep whatever the caller
            # supplied rather than destroying a usable record.
            merged[key] = metadata.get(key)
    if isinstance(declared, Mapping) or declared_methods:
        merged["kernel_identification_method"] = declared_methods
    else:
        merged.pop("kernel_identification_method", None)
    return merged


def _labelled_snapshots(
    pre_snapshot: Mapping[str, Any], post_snapshot: Mapping[str, Any]
) -> dict[str, Any]:
    """Both probes, each explicitly labelled so neither can be misread."""
    def project(snapshot: Mapping[str, Any]) -> dict[str, Any]:
        safe = _sanitize_environment(snapshot)
        return {
            "numpy_openblas_kernel": safe.get("numpy_openblas_kernel"),
            "scipy_openblas_kernel": safe.get("scipy_openblas_kernel"),
            "kernel_identification_method": safe.get("kernel_identification_method", {}),
        }

    return {
        "pre_replay": project(pre_snapshot),
        "post_replay": project(post_snapshot),
        "scope": (
            "resident objects in THIS process only; not proof of the kernel used "
            "by every later call, and not an authoritative host identity"
        ),
    }


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
