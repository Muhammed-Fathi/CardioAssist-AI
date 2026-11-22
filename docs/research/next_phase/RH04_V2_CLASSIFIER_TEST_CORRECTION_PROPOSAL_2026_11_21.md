# Proposal — separating classifier diagnosis from replay acceptance

**Status: PROPOSAL ONLY. Nothing in this document has been implemented.**
`D-V2-2` authorizes a *proposal*; the merged #136 classifier and test surface are
untouched and require separate authorization before any edit.

Two independent concerns are currently conflated. Both are real, and both were
observed on hosted CI for PR #138.

---

## Concern A — "verified environment" is not "exact replay"

### Observed

On a forced non-golden dispatch the classifier correctly reports
`VERIFIED_ENVIRONMENT` — the environment is *known* — while the canonical 29-case
replay correctly reports `1 case differing` and exits **2**.

`tests/experiments/test_rh04_issue132_environment_class.py:1168` asserts:

```python
if payload["environment_verdict"] == classifier.VERIFIED_ENVIRONMENT:
    assert payload["environment"]["scipy_openblas_kernel"] is not None
    assert classifier.exit_code(payload) in (0, 1)     # <-- fails with 2
```

The assertion encodes *"verified environment ⇒ golden outcome"*. That implication
is false: an environment can be fully identified and still not reproduce the
frozen pack. This is the entire premise of Issue #132.

### Proposed correction (narrow)

Replace the exit-code coupling with the property that was actually intended —
*identification completeness*:

```python
if payload["environment_verdict"] == classifier.VERIFIED_ENVIRONMENT:
    # The environment is identified; the outcome is whatever the replay said.
    assert payload["environment"]["scipy_openblas_kernel"] is not None
    assert payload["environment"]["numpy_openblas_kernel"] is not None
    assert classifier.exit_code(payload) == classifier.exit_code(payload)  # noqa
```

More concretely, and without weakening anything: assert that a verified
environment reports an identified kernel **and** that the exit code matches the
*field verdict*, leaving the field verdict free to be non-exact:

```python
if payload["environment_verdict"] == classifier.VERIFIED_ENVIRONMENT:
    assert payload["environment"]["scipy_openblas_kernel"] is not None
assert classifier.exit_code(payload) == CLASSIFIER_EXIT_CODE[payload["field_verdict"]]
```

### What this deliberately does not change

* The canonical Golden Replay assertion is **not** touched. A non-exact replay
  still exits non-zero and still fails.
* `test_cli_under_a_forced_dispatch_is_fail_closed_and_labelled` already asserts
  `if field_verdict == EXACT_REPLAY: returncode == 0 else: returncode != 0`. That
  is correct and stays.
* No tolerance, no skip, no approved exception.

---

## Concern B — a subprocess can die before producing JSON

### Observed on hosted CI

`test_cli_under_a_forced_dispatch_is_fail_closed_and_labelled[SkylakeX]` failed
with `json.JSONDecodeError` on **empty child stdout**. My local reproduction of
that *signature* (not of the hosted cause) with `OPENBLAS_CORETYPE=Bulldozer`:

```
returncode: -4          # negative => killed by signal
signal:      4          # SIGILL (illegal instruction)
stdout:      ''         # empty
stderr:      ''         # also empty
```

A `JSONDecodeError` on empty stdout therefore carries **no information** about
which of these happened:

| Possibility | Distinguishable today? |
|---|---|
| kernel lacked an instruction the code path required (SIGILL) | no |
| process was killed for another reason (SIGKILL / OOM) | no |
| interpreter crashed before writing (segfault) | no |
| CLI printed nothing but exited 0 (a real bug) | no |
| CLI wrote to stderr and nothing to stdout | no |
| timeout | no |

### Proposed correction (narrow, diagnostic only)

Capture the process facts *before* attempting to parse:

```python
@dataclass(frozen=True)
class ChildOutcome:
    returncode: int
    signal_number: int | None      # -returncode when negative
    timed_out: bool
    stdout_empty: bool
    stdout_parseable: bool
    stderr_present: bool           # redacted presence only, never contents
    stderr_tail: str               # already redacted by the caller


def classify_child(outcome: ChildOutcome) -> str:
    if outcome.timed_out:
        return "DIED_TIMEOUT"
    if outcome.signal_number is not None:
        return f"DIED_WITH_SIGNAL:SIG{outcome.signal_number}"
    if outcome.returncode == 0 and outcome.stdout_empty:
        return "EXITED_CLEAN_WITH_NO_OUTPUT"      # a genuine bug
    if not outcome.stdout_parseable:
        return "STDOUT_NOT_JSON"
    return "PARSED"
```

The test then reports the classification with the failure message:

```python
outcome = _cli_classified({"OPENBLAS_CORETYPE": coretype})
if outcome.kind != "PARSED":
    pytest.fail(f"child did not produce JSON: {outcome.kind} "
                f"(rc={outcome.returncode}, stderr_present={outcome.stderr_present})")
```

### Critical property

**This makes the failure *more* informative, never more permissive.** There is no
branch in which an unparseable child is treated as a pass. Every non-`PARSED`
outcome still fails; only the message changes. `DIED_WITH_SIGNAL` is deliberately
still a failure, because a reference gate must not silently accept a dead child.

### Why it must not auto-skip

A tempting "skip when the kernel cannot run the code" is exactly the silent
weakening the brief forbids. If a required runner cannot execute the workload,
that is a **visible, failing** condition about the runner, not a property of the
code under test. The proposal reports it, loudly.

---

## Sequencing

1. `D-V2-2` proposal accepted (this document).
2. Separate authorization to edit the merged #136 surface.
3. Implement both corrections in one scoped PR against `main`, with the
   `[SkylakeX]` case reproducing `DIED_WITH_SIGNAL` and still failing as a
   `pytest.fail`, plus a test proving an `EXITED_CLEAN_WITH_NO_OUTPUT` child is a
   failure.
4. Only then revisit whether the hosted `[SkylakeX]` job is diagnosable.

Until then, the hosted failure stays red and stays unexplained beyond "a child
produced no stdout for a reason that has not been captured".
