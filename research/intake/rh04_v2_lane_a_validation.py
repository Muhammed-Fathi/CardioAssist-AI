"""The single Lane A validity gate shared by forced and host dispatch.

**Why this module exists.** Round 23 found that the dual-run gate asked a
different question in each of its two dispatch modes:

* forced dispatch read ``document["validity"]["valid"]`` — and only from the
  *first* of its two regenerations;
* host dispatch read ``any_failure`` and never read validity at all.

Both are the same class of bug: a *recorded* claim was trusted instead of the
*content* being re-examined, and two code paths drifted apart because they were
written twice. The two green jobs in run `45778635984` were precisely the two
paths that did not enforce V2-04a.

**Design.** One function, called by both paths. It:

1. re-derives validity with ``assert_lane_a_valid`` — the module's own predicate,
   which recomputes from the evidence rather than believing the ``validity`` field,
   so a document cannot be made valid by editing its verdict;
2. then additionally demands that the *recorded* verdict be present, well-typed
   and strictly ``True`` — a document that fails its own predicate but claims
   success is internally inconsistent, and inconsistent evidence is not
   publishable;
3. checks ``any_failure is False`` by identity, not truthiness, so a fit failure
   cannot hide behind a truthy string.

**What it deliberately does not do.** It does not compare parameters to the
archive and it does not apply any tolerance. A converged regeneration whose
parameters differ from the archive by float noise is a *finding* under V2-04a and
must not fail. Cross-environment differences are never failures here.

**Semantics of `require_validity_record`.** A freshly produced document always
carries a `validity` field. Set this to `False` only when validating a document
form that predates it; the workflow always leaves it `True`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, Mapping, Sequence

from research.intake.rh04_v2_lane_a_report import assert_lane_a_valid

__all__: Final[tuple[str, ...]] = (
    "LaneAVerdict",
    "check_lane_a_document",
    "describe_lane_a_verdict",
    "LaneAValidationError",
)


class LaneAValidationError(Exception):
    """Lane A evidence is not admissible. The message is safe to print."""


@dataclass(frozen=True)
class LaneAVerdict:
    """The outcome of validating one Lane A document."""

    document_label: str
    valid: bool
    failures: tuple[str, ...]
    findings: tuple[str, ...]
    recorded_verdict: Any

    def to_record(self) -> dict[str, Any]:
        return {
            "document": self.document_label,
            "valid": self.valid,
            "failures": list(self.failures),
            "findings": list(self.findings),
            "recorded_verdict": self.recorded_verdict,
        }


def _recorded_verdict_failures(document: Mapping[str, Any]) -> list[str]:
    """Check the *recorded* verdict is present, well-typed and strictly True.

    Strictly: ``is True``. Not ``bool(x)``, not ``x == True``. ``1``, ``"true"``
    and ``"yes"`` are all refusals rather than acceptances, because a verdict that
    can be satisfied by a truthy value is a verdict that can be satisfied by a
    mistake.
    """
    failures: list[str] = []
    if "validity" not in document:
        return ["validity -- record is absent"]
    validity = document["validity"]
    if not isinstance(validity, dict):
        return [f"validity -- not an object (got {type(validity).__name__})"]
    if "valid" not in validity:
        return ["validity.valid -- field is absent"]
    recorded = validity["valid"]
    if recorded is not True:
        if isinstance(recorded, bool):
            listed = validity.get("failures")
            detail = (
                "; ".join(str(item) for item in listed)
                if isinstance(listed, list) and listed
                else "no failure list recorded"
            )
            failures.append(f"validity.valid -- recorded False ({detail})")
        else:
            failures.append(
                "validity.valid -- not a boolean "
                f"(got {type(recorded).__name__} {recorded!r})"
            )
    listed = validity.get("failures")
    if listed is not None and not isinstance(listed, list):
        failures.append(
            f"validity.failures -- not a list (got {type(listed).__name__})"
        )
    return failures


def check_lane_a_document(
    document: Any,
    *,
    label: str,
    require_validity_record: bool = True,
) -> LaneAVerdict:
    """Validate one Lane A document. Returns a verdict; never raises on content."""
    failures: list[str] = []

    if not isinstance(document, dict):
        return LaneAVerdict(
            document_label=label,
            valid=False,
            failures=(f"{label}: document is not an object",),
            findings=(),
            recorded_verdict=None,
        )

    # 1. any_failure must be literally False. A truthy string is not a pass.
    any_failure = document.get("any_failure")
    if any_failure is not False:
        failures.append(
            f"{label}: any_failure -- expected False, got "
            f"{type(any_failure).__name__} {any_failure!r}"
        )

    # 2. Recorded verdict, if required.
    if require_validity_record:
        failures.extend(f"{label}: {item}" for item in _recorded_verdict_failures(document))

    # 3. Independent re-derivation from content. This is the check that cannot be
    #    satisfied by editing the verdict, and it is the same predicate the
    #    forced-dispatch path has always used.
    recomputed = assert_lane_a_valid(document)
    failures.extend(f"{label}: {item}" for item in recomputed.get("failures") or [])

    recorded = None
    if isinstance(document.get("validity"), dict):
        recorded = document["validity"].get("valid")

    return LaneAVerdict(
        document_label=label,
        valid=not failures,
        failures=tuple(failures),
        findings=tuple(recomputed.get("findings") or []),
        recorded_verdict=recorded,
    )


def validate_lane_a_documents(
    documents: Sequence[tuple[str, Any]],
    *,
    require_validity_record: bool = True,
) -> list[LaneAVerdict]:
    """Validate several documents together.

    Every document is checked even if an earlier one fails, so one bad run cannot
    mask a second bad run. This is the property Round 23 found missing: the old
    Stage 2 stopped at the first document's verdict.
    """
    return [
        check_lane_a_document(
            document,
            label=label,
            require_validity_record=require_validity_record,
        )
        for label, document in documents
    ]


def describe_lane_a_verdict(verdicts: Sequence[LaneAVerdict]) -> str:
    """A printable, content-free summary. Never includes evidence values."""
    if not verdicts:
        return "Lane A: no documents were validated (that is itself a failure)"
    failures = [item for verdict in verdicts for item in verdict.failures]
    if failures:
        return "Lane A evidence is invalid:\n  - " + "\n  - ".join(failures)
    return "Lane A evidence is valid: " + ", ".join(
        f"{verdict.document_label} (findings={len(verdict.findings)})"
        for verdict in verdicts
    )
