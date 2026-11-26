"""Fail-closed security validation for RH-04 gate evidence before publication.

**Why this module exists.** The gate published its evidence with
``if: always()`` and scanned it with a ``grep`` whose exit status was collapsed
into ``if grep …; then paths=1; else paths=0; fi``. Three distinct failures were
possible and none of them failed the run:

* ``grep`` exits **2** on a read error or an unreadable/absent path. The
  ``if`` treated that as *no match*, i.e. **clean**. "I could not scan" was
  indistinguishable from "I scanned and found nothing".
* A directory that does not exist is not a match, so a stage that produced no
  evidence at all produced a *passing* security result.
* Nothing checked *what kind of file* was being published, so any file that
  happened to land in ``lane-a/`` or ``lane-b/`` — a bundle, a key, a core dump,
  a 200 MB matrix — would be uploaded.

**Design decision: allowlist, not denylist.** A denylist can only catch patterns
someone thought of. This module publishes **only** the named evidence files, each
of which must parse as JSON with the expected top-level schema. Anything else in
the directory is a failure, not something to be ignored — because an unexpected
file in an evidence directory is either a bug or a leak and is not safe to
publish until a human has looked at it.

**Design decision: never publish raw content on failure.** A validator that
raises with the offending line in the message turns a leak into a *second* leak,
this time into the run log. Failures therefore report the file name, the rule
that was violated, and a count — never the matched text.

**Scope.** This validates *ordinary data-hygiene* conditions: personal absolute
paths, private-key armour, credential-shaped strings, unexpected file types,
oversized files, unreadable files. It is **not** a comprehensive sensitive-data
audit, and passing it does not certify the evidence as free of personal data.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Iterable, Mapping, Sequence

__all__: Final[tuple[str, ...]] = (
    "ALLOWED_FILES",
    "VALUE_TYPES",
    "MAX_FILE_BYTES",
    "FORBIDDEN_PATTERNS",
    "SECURITY_STATUS_FILE",
    "SecurityFailure",
    "SecurityScanResult",
    "required_files",
    "scan_evidence",
    "enforce_evidence_security",
    "write_sanitized_status",
)


#: Every file the gate is permitted to publish, with the JSON schema it must
#: satisfy. Keyed by path relative to the evidence root.
ALLOWED_FILES: Final[dict[str, frozenset[str]]] = {
    "lane-a/run1.json": frozenset({"validity", "routes", "any_failure"}),
    "lane-a/run2.json": frozenset({"validity", "routes", "any_failure"}),
    "lane-a/identity.json": frozenset({"regeneration_identical", "identities_run1"}),
    "lane-a/classified.json": frozenset({"digests", "regeneration_identical"}),
    "lane-b/observed.json": frozenset({"observed_digest", "verdict"}),
    "lane-b/identity.json": frozenset({"observed_digest", "verdict"}),
    # R24-F02: the summary is now the SCIENTIFIC record only. It carries the
    # stage exit codes and a scope note; the publication verdict moved to
    # publication-status.json, which is never published.
    "gate-summary.json": frozenset({"stages", "scope_note"}),
}

#: 8 MiB. The largest real evidence file measured at `a98dbe21` is ~48 KB zipped
#: and well under 1 MiB raw; the headroom is for the aggregate summary only.
#: Required **value types** for the keys the publication boundary relies on.
#:
#: Presence alone is not validation. `{"any_failure": "false"}` carries the key and
#: is a *truthy string*: a downstream `if not any_failure:` would read it as a
#: pass. Round 23's host fix already had to reject `any_failure` of the wrong type,
#: and the same class of defect applies here, so the check is shared rather than
#: re-implemented per caller.
#:
#: Every entry below was derived from the ACTUAL producer output in
#: `.github/workflows/rh04-dual-run-gate.yml` and `rh04_v2_lane_a_report`, not
#: guessed: `bool` for the failure flags, `dict` for the nested records, `str`
#: for digests, `list` for the resident-library list, `int` for counts. Python's
#: `bool` is a subclass of `int`, so booleans are checked with `isinstance(x, bool)`
#: exactly, never by numeric type.
VALUE_TYPES: Final[dict[str, dict[str, type]]] = {
    "lane-a/run1.json": {
        "validity": dict,
        "routes": dict,
        "any_failure": bool,
    },
    "lane-a/run2.json": {
        "validity": dict,
        "routes": dict,
        "any_failure": bool,
    },
    "lane-a/identity.json": {
        "regeneration_identical": bool,
        "identities_run1": dict,
    },
    "lane-a/classified.json": {
        "digests": dict,
        "regeneration_identical": bool,
    },
    "lane-b/observed.json": {
        "observed_digest": str,
        "verdict": str,
    },
    "lane-b/identity.json": {
        "observed_digest": str,
        "verdict": str,
    },
    "gate-summary.json": {
        "stages": dict,
        "scope_note": str,
    },
}

MAX_FILE_BYTES: Final[int] = 8 * 1024 * 1024

SECURITY_STATUS_FILE: Final[str] = "security-status.json"

#: Patterns whose presence in an *allowed* file means the file is not safe to
#: publish. Deliberately narrow and case-insensitive: broad rules generate false
#: positives that get suppressed, and a suppressed rule protects nothing.
FORBIDDEN_PATTERNS: Final[tuple[tuple[str, str], ...]] = (
    # Home directories on any platform, including the runner's own.
    ("absolute_home_path", r"/(?:home|Users)/[A-Za-z0-9._-]+"),
    # Windows drive-letter paths, which the old POSIX-only pattern missed.
    ("windows_absolute_path", r"(?<![A-Za-z0-9])[A-Za-z]:\\\\?(?:[Uu]sers|Documents and Settings|Windows)\b"),
    # Private-key armour, any flavour.
    ("private_key", r"BEGIN [A-Z ]*PRIVATE KEY"),
    # Credential-shaped strings. Placeholder-only by design: the module never
    # needs to recognise a real secret to refuse to publish one.
    ("credential_token", r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16})\b"),
    # Environment assignments that would leak a live secret into an artifact.
    ("secret_assignment", r"(?i)\b(?:aws_secret_access_key|password|passwd|api[_-]?key|secret[_-]?key)\s*[:=]\s*['\"]?[^\s'\"]{8,}"),
)

_COMPILED: Final[tuple[tuple[str, re.Pattern[str]], ...]] = tuple(
    (name, re.compile(pattern)) for name, pattern in FORBIDDEN_PATTERNS
)


class SecurityFailure(Exception):
    """Raised when evidence must not be published.

    The message is constructed from the file name, the rule name and a count.
    It never contains the matched text, for the reason given in the module
    docstring: turning a leak into a log line is still a leak.
    """


@dataclass(frozen=True)
class SecurityScanResult:
    """The outcome of a scan. Serialisable, and safe to publish."""

    passed: bool
    scanned: tuple[str, ...] = ()
    failures: tuple[str, ...] = field(default_factory=tuple)

    #: A scan that fails on every file must not print a thousand lines; the count
    #: is the signal, and the first few names are enough to start an investigation.
    MAX_REPORTED_FAILURES: Final[int] = 25

    def to_record(self) -> dict[str, Any]:
        reported = list(self.failures[: self.MAX_REPORTED_FAILURES])
        suppressed = len(self.failures) - len(reported)
        return {
            "passed": self.passed,
            "scanned": list(self.scanned),
            "failure_count": len(self.failures),
            "failures": reported,
            "failures_suppressed": suppressed,
            "note": (
                "Hygiene scan only: personal absolute paths, private-key armour, "
                "credential-shaped strings, unexpected file types, oversized or "
                "unreadable files. A pass is not a comprehensive sensitive-data "
                "audit and does not certify the evidence as free of personal data."
            ),
        }


#: Host-dispatch evidence. Named explicitly; the host job writes two documents at
#: the workspace root, so the forced-dispatch directory scan does not apply.
HOST_DOCUMENTS: Final[dict[str, frozenset[str]]] = {
    "lane-a-host.json": frozenset({"any_failure", "routes", "validity"}),
    "lane-b-host.json": frozenset({"observed_digest", "verdict"}),
}

#: The host documents are validated against the same type rules as their forced
#: counterparts: one rule, two call sites.
VALUE_TYPES.update(
    {
        "lane-a-host.json": {"any_failure": bool, "routes": dict, "validity": dict},
        "lane-b-host.json": {"observed_digest": str, "verdict": str},
    }
)


def required_files(*, include_lane_b: bool = True) -> tuple[str, ...]:
    """The allowlist subset that MUST exist for a run to be publishable."""
    names = ["lane-a/run1.json", "lane-a/run2.json", "gate-summary.json"]
    if include_lane_b:
        names += ["lane-b/observed.json", "lane-b/identity.json"]
    return tuple(names)


def _list_files(root: Path) -> list[Path]:
    """Every regular file under `root`, deterministically ordered.

    Symlinks are refused rather than followed: a symlink pointing outside the
    evidence tree would let a scan pass on content that is not what gets
    uploaded.
    """
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        for name in sorted(filenames):
            path = Path(dirpath) / name
            if path.is_symlink():
                raise SecurityFailure(
                    f"{path.relative_to(root)}: symlink in evidence tree -- refusing "
                    "to publish content that may resolve outside the tree"
                )
            found.append(path)
    return found


def check_payload(
    rel: str,
    raw: bytes,
    *,
    table: Mapping[str, frozenset[str]] | None = None,
) -> None:
    """Validate one file's bytes against the publication rules.

    Shared by the directory scan and by the publication seal, so the two cannot
    disagree about what "safe" means. Raises `SecurityFailure` carrying a
    sanitised message: file name, rule name, count. Never the matched text.
    """
    allowlist = dict(table or ALLOWED_FILES)
    key = rel
    if key not in allowlist:
        raise SecurityFailure(f"{key}: not on the evidence allowlist")
    if len(raw) == 0:
        raise SecurityFailure(f"{key}: empty file")
    if len(raw) > MAX_FILE_BYTES:
        raise SecurityFailure(f"{key}: {len(raw)} bytes exceeds the {MAX_FILE_BYTES}-byte limit")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise SecurityFailure(
            f"{key}: not valid UTF-8 -- unexpected file type in an evidence tree"
        ) from None
    for name, pattern in _COMPILED:
        hits = len(pattern.findall(text))
        if hits:
            raise SecurityFailure(
                f"{key}: forbidden content matched rule '{name}' ({hits} occurrence(s))"
            )
    try:
        document = json.loads(text)
    except json.JSONDecodeError:
        raise SecurityFailure(f"{key}: not valid JSON") from None
    if not isinstance(document, dict):
        raise SecurityFailure(f"{key}: top level is not a JSON object")
    missing = sorted(allowlist[key] - set(document))
    if missing:
        raise SecurityFailure(f"{key}: missing required key(s) {missing}")

    # Type validation. A key that is present with the wrong type is not evidence:
    # `"any_failure": "false"` is a truthy string that a naive `if not` treats as
    # a pass. Bool is checked exactly, because `isinstance(True, int)` is True.
    expected_types = VALUE_TYPES.get(key, {})
    wrong: list[str] = []
    for field_name, expected in sorted(expected_types.items()):
        if field_name not in document:
            continue  # presence is enforced by the allowlist above
        value = document[field_name]
        if expected is bool:
            ok = isinstance(value, bool)
        elif expected is int:
            ok = isinstance(value, int) and not isinstance(value, bool)
        else:
            ok = isinstance(value, expected)
        if not ok:
            wrong.append(
                f"{field_name} is {type(value).__name__}, expected {expected.__name__}"
            )
    if wrong:
        # Names the field and the two type names only -- no value is emitted, so a
        # mistyped secret cannot leak through this message.
        raise SecurityFailure(f"{key}: wrong type for " + "; ".join(wrong))


def _allowlist_key(directory: str, rel: str) -> str:
    """Map a directory-relative name onto the fully-qualified allowlist key."""
    return f"{directory}/{rel}" if directory else rel


def _check_file(
    root: Path,
    path: Path,
    *,
    require_json_schema: bool,
    directory: str = "",
) -> list[str]:
    """Validate one file. Returns failure descriptions; never returns content."""
    rel = path.relative_to(root).as_posix()
    key = _allowlist_key(directory, rel)
    if key not in ALLOWED_FILES:
        return [f"{key}: not on the evidence allowlist"]
    try:
        raw = path.read_bytes()
    except OSError as error:
        return [
            f"{key}: unreadable ({type(error).__name__}) -- scan could not complete"
        ]
    try:
        check_payload(key, raw)
    except SecurityFailure as error:
        return [str(error)]
    return []


def scan_evidence(
    root: str | Path,
    *,
    required: Sequence[str] | None = None,
    directory: str = "",
) -> SecurityScanResult:
    """Scan an evidence directory. Fails closed; never raises for content reasons.

    Returns a `SecurityScanResult` so the caller decides the exit code; callers
    that must not continue should use `enforce_evidence_security`.
    """
    root_path = Path(root)
    if not root_path.is_dir():
        return SecurityScanResult(
            passed=False,
            failures=(f"evidence root '{root_path.as_posix()}' is not a directory",),
        )

    required_names = tuple(required) if required is not None else required_files()
    failures: list[str] = []

    try:
        files = _list_files(root_path)
    except SecurityFailure as error:
        return SecurityScanResult(passed=False, failures=(str(error),))

    scanned: list[str] = []
    for path in files:
        rel = path.relative_to(root_path).as_posix()
        if rel == SECURITY_STATUS_FILE:
            # Written by this module on a previous attempt; never re-published
            # as if it were scanned evidence.
            continue
        scanned.append(_allowlist_key(directory, rel))
        failures.extend(
            _check_file(root_path, path, require_json_schema=True, directory=directory)
        )

    present = set(scanned)
    for name in required_names:
        qualified = _allowlist_key(directory, name)
        if qualified not in present:
            failures.append(f"{qualified}: REQUIRED evidence file is absent")

    return SecurityScanResult(
        passed=not failures, scanned=tuple(scanned), failures=tuple(failures)
    )


def enforce_evidence_security(
    root: str | Path,
    *,
    required: Sequence[str] | None = None,
) -> SecurityScanResult:
    """Scan, and raise `SecurityFailure` if the evidence is not publishable."""
    result = scan_evidence(root, required=required)
    if not result.passed:
        raise SecurityFailure(
            "evidence is not safe to publish: " + "; ".join(result.failures)
        )
    return result


def write_sanitized_status(
    path: str | Path, result: SecurityScanResult
) -> Path:
    """Write a status record that cannot contain unsafe raw content.

    Only booleans, allowlisted file names, and rule/count strings produced by
    this module are written. This is the only thing that may be published when
    the scan fails, so a failure can be *reported* without being *leaked*.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Belt and braces: the record itself is passed through the same scan so a
    # future edit to the message text cannot smuggle content out.
    body = json.dumps(result.to_record(), indent=2, sort_keys=True)
    for name, pattern in _COMPILED:
        if pattern.search(body):
            raise SecurityFailure(
                f"refusing to write the status record: it matches rule '{name}'"
            )
    target.write_text(body + "\n", encoding="utf-8")
    return target


def main(argv: Sequence[str] | None = None) -> int:
    """CLI used by the workflow. Returns the exit code rather than raising."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument(
        "--evidence-dirs",
        nargs="*",
        default=["lane-a", "lane-b"],
        help="Evidence subdirectories, relative to root.",
    )
    parser.add_argument("--status-file", default=None)
    parser.add_argument(
        "--host-documents",
        action="store_true",
        help="Validate the host-dispatch evidence set (two named files).",
    )
    parser.add_argument(
        "--require-lane-b",
        dest="require_lane_b",
        action="store_true",
        default=True,
        help="Require Lane B evidence (the default).",
    )
    parser.add_argument(
        "--no-require-lane-b", dest="require_lane_b", action="store_false"
    )
    arguments = parser.parse_args(argv)

    root = Path(arguments.root)
    results: list[SecurityScanResult] = []

    if arguments.host_documents:
        failures: list[str] = []
        scanned: list[str] = []
        for name, schema in sorted(HOST_DOCUMENTS.items()):
            path = root / name
            if not path.is_file():
                failures.append(f"{name}: REQUIRED host evidence file is absent")
                continue
            if path.is_symlink():
                failures.append(f"{name}: symlink in the evidence tree")
                continue
            scanned.append(name)
            try:
                check_payload(name, path.read_bytes(), table=HOST_DOCUMENTS)
            except SecurityFailure as error:
                failures.append(str(error))
        merged = SecurityScanResult(
            passed=not failures, scanned=tuple(scanned), failures=tuple(failures)
        )
        if arguments.status_file:
            write_sanitized_status(root / arguments.status_file, merged)
        print(json.dumps(merged.to_record(), indent=2, sort_keys=True))
        return 0 if merged.passed else 1
    for directory in arguments.evidence_dirs:
        target = root / directory
        if not target.is_dir():
            results.append(
                SecurityScanResult(
                    passed=False,
                    failures=(f"{directory}: evidence directory is absent",),
                )
            )
            continue
        required = tuple(
            name[len(directory) + 1:]
            for name in required_files(include_lane_b=arguments.require_lane_b)
            if name.startswith(directory + "/")
        )
        results.append(
            scan_evidence(target, required=required, directory=directory)
        )

    merged = SecurityScanResult(
        passed=all(result.passed for result in results),
        scanned=tuple(name for result in results for name in result.scanned),
        failures=tuple(item for result in results for item in result.failures),
    )
    if arguments.status_file:
        write_sanitized_status(root / arguments.status_file, merged)
    print(json.dumps(merged.to_record(), indent=2, sort_keys=True))
    return 0 if merged.passed else 1


if __name__ == "__main__":  # pragma: no cover - exercised via the workflow
    raise SystemExit(main())
