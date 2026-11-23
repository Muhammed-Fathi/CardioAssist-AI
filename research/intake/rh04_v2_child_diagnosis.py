"""RH-04 V2 — child-process diagnosis before JSON decoding (proposal implementation).

Scope
-----
Self-contained helper module. It **does not modify** the merged #136 classifier or
its tests (`test_rh04_issue132_environment_class.py` is byte-identical to `main`).
It exists so the proposed correction in
`RH04_V2_CLASSIFIER_TEST_CORRECTION_PROPOSAL_2026_11_21.md` is executable and
reviewable rather than prose.

Why
---
The hosted Python 3.11 job failed
``test_cli_under_a_forced_dispatch_is_fail_closed_and_labelled[SkylakeX]`` with
``JSONDecodeError`` on **empty child stdout**. Locally, forcing an incompatible
kernel reproduces that signature exactly::

    returncode -4        # negative => killed by a signal
    signal      4        # SIGILL
    stdout      ''       # empty
    stderr      ''       # ALSO empty

So a ``JSONDecodeError`` on empty stdout carries no information at all about
which of several very different things happened. This module classifies *before*
decoding, and every non-parsed outcome remains a **failure**.

Exit status is deliberately NOT derived from ``field_verdict`` alone. The existing
classifier also requires ``VERIFIED_ENVIRONMENT``, and mapping from one field
would silently change semantics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Final, Mapping

#: The existing classifier's verdict tokens (mirrored, not imported, so this
#: module cannot drag the production classifier into a test-only path).
INVALID_DIAGNOSTIC: Final[str] = "INVALID_DIAGNOSTIC"
DIAGNOSTIC_REFUSED: Final[str] = "DIAGNOSTIC_REFUSED"
VERIFIED_ENVIRONMENT: Final[str] = "VERIFIED_ENVIRONMENT"
UNVERIFIED_ENVIRONMENT: Final[str] = "UNVERIFIED_ENVIRONMENT"
EXACT_REPLAY: Final[str] = "EXACT_REPLAY"
#: The canonical classifier's *classified* delta verdict. An earlier revision of
#: this helper mapped ``MISMATCH_FOUND`` to exit 1, which is wrong: exit 1 means
#: "these deltas are the documented ones", not "something mismatched".
EXPECTED_SINGLE_FIELD_DELTAS: Final[str] = "EXPECTED_SINGLE_FIELD_DELTAS"
#: Mirrors ``rh04_environment_class.UNEXPECTED_DRIFT``. The canonical classifier
#: uses this token, not ``MISMATCH_FOUND``; using the wrong name would have made
#: the helper and the classifier disagree without either being obviously wrong.
UNEXPECTED_DRIFT: Final[str] = "UNEXPECTED_DRIFT"

KIND_PARSED: Final[str] = "PARSED"
KIND_TIMEOUT: Final[str] = "DIED_TIMEOUT"
KIND_SIGNAL: Final[str] = "DIED_WITH_SIGNAL"
KIND_CLEAN_NO_OUTPUT: Final[str] = "EXITED_CLEAN_WITH_NO_OUTPUT"
KIND_NONZERO_NO_PAYLOAD: Final[str] = "EXITED_NONZERO_WITHOUT_VALID_PAYLOAD"
KIND_INVALID_JSON: Final[str] = "STDOUT_NOT_JSON"
KIND_INVALID_SCHEMA: Final[str] = "JSON_WITH_INVALID_SCHEMA"

#: Signal names we can render without importing ``signal`` (which is fine, but
#: keeps the report stable across platforms).
_SIGNAL_NAMES: Final[dict[int, str]] = {
    4: "SIGILL",
    6: "SIGABRT",
    8: "SIGFPE",
    9: "SIGKILL",
    11: "SIGSEGV",
    15: "SIGTERM",
}

#: Environment verdicts the canonical classifier can emit.
_KNOWN_ENVIRONMENT_VERDICTS: Final[frozenset[str]] = frozenset(
    {VERIFIED_ENVIRONMENT, UNVERIFIED_ENVIRONMENT}
)

#: Field verdicts the canonical classifier can emit. ``INVALID_DIAGNOSTIC`` and
#: ``DIAGNOSTIC_REFUSED`` are real canonical refusals and must be classified
#: (both imply exit 2), so they belong here; anything outside this set is an
#: unknown verdict and is rejected outright.
_KNOWN_FIELD_VERDICTS: Final[frozenset[str]] = frozenset(
    {
        EXACT_REPLAY,
        EXPECTED_SINGLE_FIELD_DELTAS,
        UNEXPECTED_DRIFT,
        INVALID_DIAGNOSTIC,
        DIAGNOSTIC_REFUSED,
    }
)

#: Fields a valid classifier payload must expose. Missing ones are a schema error.
_REQUIRED_FIELDS: Final[tuple[str, ...]] = (
    "environment_verdict",
    "field_verdict",
    "environment",
)


class ChildDiagnosisError(Exception):
    """A child process produced an inconsistent or unusable diagnosis."""


@dataclass(frozen=True)
class ChildOutcome:
    """Everything knowable about a child process, captured before decoding."""

    returncode: int
    stdout: str
    stderr_present: bool
    timed_out: bool = False
    extra: Mapping[str, Any] = field(default_factory=dict)

    @property
    def signal_number(self) -> int | None:
        """POSIX convention: a negative return code means it was signalled."""
        return -self.returncode if self.returncode < 0 else None

    @property
    def stdout_empty(self) -> bool:
        return not self.stdout.strip()

    def redacted_summary(self) -> str:
        """A description safe to print: no child output, no paths, no secrets."""
        signal_number = self.signal_number
        signal_name = _SIGNAL_NAMES.get(signal_number or -1, "UNKNOWN")
        return (
            f"returncode={self.returncode}"
            f" signal={signal_number}({signal_name})"
            f" timed_out={self.timed_out}"
            f" stdout_empty={self.stdout_empty}"
            f" stderr_present={self.stderr_present}"
        )


def classify_child(outcome: ChildOutcome) -> tuple[str, dict[str, Any] | None]:
    """Classify a child outcome. Returns ``(kind, payload)``.

    ``payload`` is non-``None`` **only** for :data:`KIND_PARSED`. Every other kind
    is a failure the caller must report; there is no branch in which an
    unparseable or abnormally terminated child is treated as success.
    """
    import json

    if outcome.timed_out:
        return KIND_TIMEOUT, None
    if outcome.signal_number is not None:
        return KIND_SIGNAL, None
    if outcome.stdout_empty:
        if outcome.returncode == 0:
            return KIND_CLEAN_NO_OUTPUT, None
        return KIND_NONZERO_NO_PAYLOAD, None
    try:
        payload = json.loads(outcome.stdout)
    except json.JSONDecodeError:
        return KIND_INVALID_JSON, None
    if not isinstance(payload, dict):
        return KIND_INVALID_SCHEMA, None
    if any(name not in payload for name in _REQUIRED_FIELDS):
        return KIND_INVALID_SCHEMA, None
    # Presence is not enough: wrong types and unknown verdicts are also invalid.
    if not isinstance(payload["environment"], dict):
        return KIND_INVALID_SCHEMA, None
    if not isinstance(payload["environment_verdict"], str):
        return KIND_INVALID_SCHEMA, None
    if not isinstance(payload["field_verdict"], str):
        return KIND_INVALID_SCHEMA, None
    if payload["environment_verdict"] not in {
        VERIFIED_ENVIRONMENT,
        UNVERIFIED_ENVIRONMENT,
    }:
        return KIND_INVALID_SCHEMA, None
    if payload["field_verdict"] not in _KNOWN_FIELD_VERDICTS:
        return KIND_INVALID_SCHEMA, None
    return KIND_PARSED, payload


#: The existing classifier's exit-code policy, restated independently so a
#: ``field_verdict``-only mapping cannot creep in. Both dimensions matter.
def expected_exit_code(environment_verdict: str, field_verdict: str) -> int:
    """Independently derived expectation for the (environment, field) grid.

    * An *unverified* environment is exit 2 regardless of the field verdict: the
      run cannot claim a verified reading of a machine it could not identify.
    * A verified environment with an exact replay is exit 0.
    * A verified environment with *classified* single-field deltas is exit 1.
      ``UNEXPECTED_DRIFT`` is **not** that case and must be exit 2.
    * A verified environment with anything else (including an unexpected
      mismatch) is exit 2.
    """
    # Both verdicts are validated here, not by the caller. An unknown verdict
    # must never fall through to a numeric expectation.
    if environment_verdict not in _KNOWN_ENVIRONMENT_VERDICTS:
        raise ValueError(f"unknown environment verdict {environment_verdict!r}")
    if field_verdict not in _KNOWN_FIELD_VERDICTS:
        raise ValueError(f"unknown field verdict {field_verdict!r}")
    if environment_verdict != VERIFIED_ENVIRONMENT:
        return 2
    if field_verdict == EXACT_REPLAY:
        return 0
    if field_verdict == EXPECTED_SINGLE_FIELD_DELTAS:
        return 1
    return 2


def verify_child_return_code(payload: Mapping[str, Any], actual_rc: int) -> int:
    """Compare a child's *actual* return code with the independently derived one.

    Rejects an inconsistent child: a child that claims a verdict but exits with
    a code the policy does not imply is a failure, never a pass. The canonical
    classifier's own ``exit_code`` is untouched; this is a separate check.
    """
    if isinstance(actual_rc, bool) or not isinstance(actual_rc, int):
        raise ValueError("child return code must be an integer")
    environment_verdict = payload.get("environment_verdict")
    field_verdict = payload.get("field_verdict")
    expected = expected_exit_code(environment_verdict, field_verdict)
    if actual_rc != expected:
        raise ChildDiagnosisError(
            f"child return code {actual_rc} is inconsistent with the declared "
            f"verdicts (expected {expected})"
        )
    return expected


def failure_message(kind: str, outcome: ChildOutcome) -> str:
    """A failing assertion message that never contains raw child output."""
    return (
        f"child did not produce a usable classifier payload: {kind} "
        f"({outcome.redacted_summary()})"
    )
