"""Structural and behavioural tests for the RH-04 NON-VOTING CI observation step.

Scope
-----
These tests cover exactly two things:

1. **The workflow wiring** in ``.github/workflows/experiment-runner-ci.yml`` —
   the observation step exists in all three intended jobs, runs in the right
   place, invokes the approved command, and does not alter the canonical test
   steps or their threadpool settings.
2. **The observer's non-voting contract** in
   ``scripts/rh04_observe_environment.py`` — its exit code can never change a
   job's result, its three classifications are distinct, and its output is
   redacted.

The classifier's own ~165 negative tests live in
``tests/experiments/test_rh04_issue132_environment_class.py`` and are reused
rather than duplicated. Those tests already cover malformed envelopes, duplicate
case ids, delta syntax, tolerance enforcement and the frozen-comparator
contract; nothing here re-implements them.

What these tests deliberately do NOT assert
-------------------------------------------
No test asserts that an observation *passes*. ``EXPECTED_SINGLE_FIELD_DELTAS``
is supplemental evidence, and the canonical Golden Replay remains the sole
authority. See ``docs/research/next_phase/RH04_ISSUE132_CI_GATE_SPEC_2026_11_21.md``.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import re
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "experiment-runner-ci.yml"
_OBSERVER = _REPO_ROOT / "scripts" / "rh04_observe_environment.py"

#: The three intended jobs. ``synthetic-runner-tests`` is a matrix job whose
#: entries are exactly the Python 3.11 and 3.12 synthetic experiment runners.
MATRIX_JOB = "synthetic-runner-tests"
DIAGNOSTIC_JOB = "rh04-fixture-diagnostic"

OBSERVATION_STEP = "Record RH-04 environment observation (non-voting)"
OBSERVATION_COMMAND = "python scripts/rh04_observe_environment.py"

#: The canonical, authoritative commands that must stay byte-identical.
CANONICAL_PYTEST = "python -m pytest tests/experiments tests/audit -q -W error"
CANONICAL_REPLAY = "python -m research.intake.diagnose_fixture_replay"


def _workflow() -> dict:
    return yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))


def _step_names(job: dict) -> list[str]:
    return [s.get("name", "") for s in job["steps"]]


def _find_step(job: dict, name: str) -> dict:
    for step in job["steps"]:
        if step.get("name") == name:
            return step
    raise AssertionError(f"step {name!r} not found in {_step_names(job)}")


def _observer():
    """Import ``scripts/rh04_observe_environment.py`` as a module."""
    spec = importlib.util.spec_from_file_location("rh04_observer", _OBSERVER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------- #
# 1. Placement: the step exists in all three intended jobs, in the right place #
# --------------------------------------------------------------------------- #


def test_workflow_parses_and_has_the_two_expected_jobs():
    workflow = _workflow()
    assert set(workflow["jobs"]) == {MATRIX_JOB, DIAGNOSTIC_JOB}


def test_matrix_job_covers_both_python_versions():
    """The matrix job is both the 3.11 and the 3.12 synthetic runner."""
    matrix = _workflow()["jobs"][MATRIX_JOB]["strategy"]["matrix"]
    assert matrix["python-version"] == ["3.11", "3.12"]


def test_observation_step_present_in_matrix_job():
    job = _workflow()["jobs"][MATRIX_JOB]
    assert _step_names(job).count(OBSERVATION_STEP) == 1


def test_observation_step_present_in_diagnostic_job():
    job = _workflow()["jobs"][DIAGNOSTIC_JOB]
    assert _step_names(job).count(OBSERVATION_STEP) == 1


def test_observation_step_invokes_the_approved_command_only():
    for job_name in (MATRIX_JOB, DIAGNOSTIC_JOB):
        job = _workflow()["jobs"][job_name]
        step = _find_step(job, OBSERVATION_STEP)
        script = step["run"]
        assert OBSERVATION_COMMAND in script
        # Nothing else may be executed in this step.
        executed = [
            line.strip()
            for line in script.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        assert executed == [OBSERVATION_COMMAND], executed


def test_observation_step_runs_after_install_and_threadpool_verification():
    for job_name in (MATRIX_JOB, DIAGNOSTIC_JOB):
        names = _step_names(_workflow()["jobs"][job_name])
        observation = names.index(OBSERVATION_STEP)
        threadpool = next(
            i for i, n in enumerate(names) if n.startswith("Verify pinned CPU numerical threadpools")
        )
        install = next(i for i, n in enumerate(names) if n.lower().startswith("install"))
        assert install < observation, names
        assert threadpool < observation, names


def test_observation_step_runs_before_the_canonical_test_step():
    """Evidence must exist even when the canonical step fails."""
    names = _step_names(_workflow()["jobs"][MATRIX_JOB])
    observation = names.index(OBSERVATION_STEP)
    canonical = names.index("Run synthetic experiment-runner and dataset-audit tests")
    assert observation < canonical

    names = _step_names(_workflow()["jobs"][DIAGNOSTIC_JOB])
    observation = names.index(OBSERVATION_STEP)
    canonical = names.index(
        "Inspect canonical 29-case synthetic replay twice (strict, metadata only)"
    )
    assert observation < canonical


# --------------------------------------------------------------------------- #
# 2. The canonical gate is untouched and stays authoritative                   #
# --------------------------------------------------------------------------- #


def test_canonical_pytest_command_is_unchanged():
    job = _workflow()["jobs"][MATRIX_JOB]
    step = _find_step(job, "Run synthetic experiment-runner and dataset-audit tests")
    assert step["run"].strip() == CANONICAL_PYTEST


def test_canonical_replay_command_is_unchanged():
    job = _workflow()["jobs"][DIAGNOSTIC_JOB]
    step = _find_step(
        job, "Inspect canonical 29-case synthetic replay twice (strict, metadata only)"
    )
    # Exactly twice, unchanged, still strict.
    assert step["run"].strip() == f"{CANONICAL_REPLAY}\n{CANONICAL_REPLAY}"


def test_canonical_test_steps_have_no_suppression_of_any_kind():
    """No skip/xfail/continue-on-error/|| true/retry around the canonical gate."""
    banned = re.compile(
        r"continue-on-error\s*:\s*true"
        r"|\|\|\s*true"
        r"|--exitfirst\s*.*--maxfail"
        r"|\bx{1,2}fail\b"
        r"|\bpytest\.skip\b"
        r"|\bpytest\.xfail\b"
        r"|--runxfail"
        r"|\bretry\b"
        r"|-k\s+['\"]?not "
        r"|--deselect"
        r"|--ignore=",
        re.IGNORECASE,
    )
    workflow = _workflow()
    for job_name, job in workflow["jobs"].items():
        for step in job["steps"]:
            haystack = f"{step.get('name','')}\n{step.get('run','')}"
            assert not banned.search(haystack), (job_name, step.get("name"))


def test_no_step_declares_continue_on_error_true():
    for job_name, job in _workflow()["jobs"].items():
        for step in job["steps"]:
            assert step.get("continue-on-error") is not True, (job_name, step.get("name"))


def test_threadpool_settings_are_unchanged():
    expected = {
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "BLIS_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
        "VECLIB_MAXIMUM_THREADS": "1",
    }
    for job_name, job in _workflow()["jobs"].items():
        assert job["env"] == expected, job_name


def test_observation_step_sets_no_environment_overrides():
    """The observer must not pin OPENBLAS_CORETYPE or any threadpool variable."""
    for job_name in (MATRIX_JOB, DIAGNOSTIC_JOB):
        step = _find_step(_workflow()["jobs"][job_name], OBSERVATION_STEP)
        assert "env" not in step
        assert "OPENBLAS_CORETYPE" not in step["run"]


def test_workflow_adds_no_tolerance_exception_or_cpu_pin():
    text = _WORKFLOW.read_text(encoding="utf-8")
    for forbidden in (
        "OPENBLAS_CORETYPE",
        "NPY_DISABLE_CPU_FEATURES",
        "avx512",
        "AVX512",
        "pytest.mark.skip",
        "pytest.mark.xfail",
        "continue-on-error: true",
        "|| true",
    ):
        assert forbidden not in text, forbidden


# --------------------------------------------------------------------------- #
# 3. The observer can never vote, and its three outcomes stay distinct         #
# --------------------------------------------------------------------------- #


def test_observer_always_exits_zero_even_on_unparseable_output(monkeypatch, capsys):
    observer = _observer()
    monkeypatch.setattr(observer, "_run_classifier", lambda *a, **k: (2, "not json", ""))
    assert observer.main() == 0


def test_observer_always_exits_zero_when_the_classifier_crashes(monkeypatch):
    observer = _observer()

    def boom(*args, **kwargs):
        raise RuntimeError("/secret/path should never be printed")

    monkeypatch.setattr(observer, "_run_classifier", boom)
    assert observer.main() == 0


def test_observer_always_exits_zero_when_summary_write_fails(monkeypatch):
    observer = _observer()
    monkeypatch.setattr(
        observer, "_run_classifier", lambda *a, **k: (0, json.dumps({}), "")
    )

    def no_write(*args, **kwargs):
        raise OSError("/secret/cannot/write")

    monkeypatch.setattr("builtins.open", no_write)
    assert observer.main() == 0


@pytest.mark.parametrize(
    "exit_code,expected",
    [
        (0, "EXACT_REPLAY"),
        (1, "EXPECTED_SINGLE_FIELD_DELTAS"),
        (2, "NON_EXACT_OR_UNVERIFIED"),
    ],
)
def test_exit_codes_map_to_distinct_classifications(exit_code, expected):
    observer = _observer()
    summary = observer.summarise({}, exit_code)
    assert summary["classification"] == expected
    assert summary["exit_code"] == exit_code


def test_the_three_classification_labels_are_pairwise_distinct():
    labels = [_observer().EXIT_CLASSIFICATIONS.get(c) for c in (0, 1, 2)]
    assert len(set(labels)) == 3
    assert None not in labels


def test_unexpected_drift_and_unverified_stay_visible(monkeypatch):
    """A non-exact observation must render distinguishably, never as success."""
    observer = _observer()
    payload = {
        "field_verdict": "UNEXPECTED_DRIFT",
        "environment_verdict": "VERIFIED_ENVIRONMENT",
        "field_reasons": ["da_a2_resting_v1:different_field_count"],
    }
    summary = observer.summarise(payload, 2)
    rendered = observer.render_summary(summary)
    assert "UNEXPECTED_DRIFT" in rendered
    assert "NON_EXACT_OR_UNVERIFIED" in rendered
    assert "da_a2_resting_v1:different_field_count" in rendered
    # And it never claims success.
    assert "EXACT_REPLAY`" not in rendered


def test_expected_single_field_deltas_is_never_described_as_success():
    observer = _observer()
    payload = {
        "field_verdict": "EXPECTED_SINGLE_FIELD_DELTAS",
        "environment_verdict": "VERIFIED_ENVIRONMENT",
        "cases_differing": 2,
    }
    rendered = observer.render_summary(observer.summarise(payload, 1))
    assert "EXPECTED_SINGLE_FIELD_DELTAS" in rendered
    assert "**not** a pass" in rendered
    assert "never a success" in rendered


def test_unverified_environment_is_distinguishable():
    observer = _observer()
    summary = observer.summarise(
        {
            "field_verdict": "EXACT_REPLAY",
            "environment_verdict": "UNVERIFIED_ENVIRONMENT",
            "environment_reasons": ["numpy_version:not_a_version"],
        },
        2,
    )
    rendered = observer.render_summary(summary)
    assert "UNVERIFIED_ENVIRONMENT" in rendered
    assert "numpy_version:not_a_version" in rendered


# --------------------------------------------------------------------------- #
# 4. Redaction: no scores, coefficients, secrets or private paths             #
# --------------------------------------------------------------------------- #

_FORBIDDEN = (
    "/secret",
    "/etc/passwd",
    "/home/",
    ".aws",
    "credentials",
    "hunter2",
    "should-never",
    "BEGIN PRIVATE KEY",
    "site-packages",
    ".so",
)


def _assert_clean(text: str, case: str) -> None:
    for fragment in _FORBIDDEN:
        assert fragment not in text, f"{case}: leaked {fragment!r}"


def test_summary_never_contains_a_path_or_secret(monkeypatch):
    observer = _observer()
    poisoned = {
        "field_verdict": "/secret/verdict",
        "environment_verdict": "/secret/env",
        "replay_verdict": "/secret/replay",
        "cases_checked": "/secret/count",
        "cases_differing": "/secret/diff",
        "differing_case_ids": ["/home/user/.aws/credentials"],
        "field_reasons": ["/secret/reason"],
        "environment_reasons": ["BEGIN PRIVATE KEY"],
        "version_drift": ["hunter2"],
        "environment": {
            "python": "/secret/python",
            "numpy_version": "/secret/numpy",
            "glibc": "/secret/glibc",
            "numpy_openblas_kernel": "/secret/kernel",
            "kernel_identification_method": {"numpy_openblas_kernel": "/secret/method"},
        },
        "kernel_snapshot": {
            "pre_replay": {"scipy_openblas_kernel": "/home/user/.aws/credentials"},
            "post_replay": {"scipy_openblas_kernel": "/home/user/.aws/credentials"},
        },
    }
    rendered = observer.render_summary(observer.summarise(poisoned, 2))
    _assert_clean(rendered, "poisoned summary")
    # Unknown verdicts are dropped rather than echoed.
    assert "redacted_unexpected_format" in rendered


def test_summary_never_contains_a_float():
    observer = _observer()
    payload = {
        "cases_checked": 29.5,
        "cases_differing": 1.0,
        "field_verdict": "EXACT_REPLAY",
        "environment_verdict": "VERIFIED_ENVIRONMENT",
        "environment": {"numpy_version": 1.26},
    }
    summary = observer.summarise(payload, 0)
    rendered = observer.render_summary(summary)

    def walk(node, path="summary"):
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{path}.{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]")
        else:
            assert not isinstance(node, float), f"float at {path}: {node!r}"

    walk(summary)
    # A float count must not survive as a number in the text either.
    assert "29.5" not in rendered
    assert "1.26," not in rendered


def test_summary_emits_only_allowlisted_keys():
    observer = _observer()
    payload = {"injected": "/secret", "another": {"deep": "/etc/passwd"}}
    summary = observer.summarise(payload, 2)
    allowed = {
        "exit_code", "classification", "field_verdict", "environment_verdict",
        "replay_verdict", "cases_checked", "cases_differing",
        "differing_case_ids", "field_reasons", "environment_reasons",
        "version_drift", "python", "numpy_version", "scipy_version",
        "sklearn_version", "glibc", "resolved_environment", "pre_replay",
        "post_replay", "classifier_stdout_parseable", "classifier_stderr_present",
    }
    assert set(summary) == allowed
    assert "injected" not in json.dumps(summary)


def test_observer_never_reports_model_scores_or_coefficients():
    """The observer is metadata-only; these keys must never appear anywhere."""
    observer = _observer()
    payload = {
        "field_verdict": "EXACT_REPLAY",
        "environment_verdict": "VERIFIED_ENVIRONMENT",
        "score": 0.8123,
        "coefficients": [0.1, 0.2],
        "intercept": 0.5,
        "slope": 1.0,
    }
    rendered = observer.render_summary(observer.summarise(payload, 0))
    for forbidden in ("score", "coefficients", "intercept", "slope", "0.8123"):
        assert forbidden not in rendered, forbidden


def test_observer_module_is_non_voting_by_construction():
    """Every return path of ``main`` yields 0, and no ``sys.exit`` overrides it."""
    source = _OBSERVER.read_text(encoding="utf-8")
    assert "raise SystemExit(main())" in source
    # `main` must contain exactly one `return` statement and it returns 0.
    body = source.split("def main()", 1)[1]
    main_body = body.split("\ndef ", 1)[0]
    returns = re.findall(r"^\s+return .+$", main_body, re.MULTILINE)
    assert returns == ["    return 0"], returns


def test_observer_command_is_exactly_the_specified_module_invocation():
    """The workflow must call the helper, which itself calls the classifier."""
    observer_source = _OBSERVER.read_text(encoding="utf-8")
    assert 'CLASSIFIER_MODULE = "research.intake.rh04_environment_class"' in observer_source


# --------------------------------------------------------------------------- #
# 5. main() must not leak through ANY stream (P0, stage A review)             #
# --------------------------------------------------------------------------- #


def _run_main_capturing(observer, monkeypatch, classifier_result=None, raises=False):
    """Call ``main()`` and capture BOTH stdout and stderr.

    The step summary path was already sanitised, but the log path was not: a
    previous revision forwarded the child's raw stdout/stderr and printed the
    raw parsed payload. GitHub Actions raw logs are as visible as the summary,
    so both streams must now be clean.
    """
    if raises:

        def boom(*args, **kwargs):
            raise RuntimeError("/secret/path/should-never-appear")

        monkeypatch.setattr(observer, "_run_classifier", boom)
    else:
        monkeypatch.setattr(
            observer, "_run_classifier", lambda *a, **k: classifier_result
        )

    # Isolate the summary file so nothing leaks to disk either.
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)

    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = observer.main()
    return code, out.getvalue(), err.getvalue()


def _assert_streams_clean(stdout_text: str, stderr_text: str, case: str) -> None:
    for stream_name, text in (("stdout", stdout_text), ("stderr", stderr_text)):
        for fragment in _FORBIDDEN:
            assert fragment not in text, (
                f"{case}: leaked {fragment!r} on {stream_name}: {text!r}"
            )


def test_main_does_not_echo_injected_payload_fields(monkeypatch):
    """A parseable payload with extra/sensitive fields must not be printed."""
    observer = _observer()
    malicious = json.dumps(
        {
            "injected": "/secret/raw-payload",
            "token": "hunter2",
            "nested": {"path": "/etc/passwd", "key": "BEGIN PRIVATE KEY"},
            "field_verdict": "EXACT_REPLAY",
            "environment_verdict": "VERIFIED_ENVIRONMENT",
            "cases_checked": 29,
            "cases_differing": 0,
        }
    )
    code, out, err = _run_main_capturing(observer, monkeypatch, (0, malicious, ""))
    assert code == 0
    _assert_streams_clean(out, err, "injected payload")
    # Sanitised evidence is still present and useful.
    assert "EXACT_REPLAY" in out
    assert "VERIFIED_ENVIRONMENT" in out


def test_main_does_not_echo_malicious_child_stderr(monkeypatch):
    """A valid payload with hostile stderr must not have that stderr forwarded."""
    observer = _observer()
    payload = json.dumps(
        {"field_verdict": "EXACT_REPLAY", "environment_verdict": "VERIFIED_ENVIRONMENT"}
    )
    code, out, err = _run_main_capturing(
        observer, monkeypatch, (0, payload, "token=/secret/stderr-dump")
    )
    assert code == 0
    _assert_streams_clean(out, err, "malicious stderr")
    # Only the closed boolean marker appears, never the text.
    assert "classifier_stderr_present" in out  # JSON evidence on stdout
    assert "stderr_present=True" in err        # fixed-format label on stderr


def test_main_does_not_echo_unparseable_stdout(monkeypatch):
    """Unparseable child stdout must be recorded as a boolean, not quoted."""
    observer = _observer()
    code, out, err = _run_main_capturing(
        observer, monkeypatch, (2, "/secret/not-json {broken", "")
    )
    assert code == 0
    _assert_streams_clean(out, err, "unparseable stdout")
    assert "stdout_parseable=False" in err
    assert "NON_EXACT_OR_UNVERIFIED" in out


def test_main_does_not_echo_when_the_classifier_raises(monkeypatch):
    """An exception message must never reach either stream."""
    observer = _observer()
    code, out, err = _run_main_capturing(observer, monkeypatch, raises=True)
    assert code == 0
    _assert_streams_clean(out, err, "classifier raised")
    assert "RuntimeError" in err
    # The exception *message* is not forwarded, only its class name.
    assert "should-never-appear" not in err


@pytest.mark.parametrize(
    "classifier_result",
    [
        (0, '{"field_verdict":"/secret","environment_verdict":"/secret"}', ""),
        (2, '{"cases_checked":"/secret","differing_case_ids":["/secret"]}', "/secret"),
        (1, '{"field_reasons":["/secret"]}', "/secret"),
        (2, "not json at all /secret", "/secret"),
    ],
)
def test_main_never_leaks_across_all_exit_codes(monkeypatch, classifier_result):
    observer = _observer()
    code, out, err = _run_main_capturing(observer, monkeypatch, classifier_result)
    assert code == 0, "the observer must remain non-voting"
    _assert_streams_clean(out, err, f"exit {classifier_result[0]}")


def test_main_emits_only_allowlisted_keys_to_stdout(monkeypatch):
    """The JSON printed to the log is the sanitised summary, nothing else."""
    observer = _observer()
    payload = json.dumps(
        {
            "field_verdict": "EXACT_REPLAY",
            "environment_verdict": "VERIFIED_ENVIRONMENT",
            "injected": "/secret",
            "score": 0.8123,
        }
    )
    code, out, err = _run_main_capturing(observer, monkeypatch, (0, payload, ""))
    assert code == 0
    printed = json.loads(out)
    allowed = {
        "exit_code", "classification", "field_verdict", "environment_verdict",
        "replay_verdict", "cases_checked", "cases_differing",
        "differing_case_ids", "field_reasons", "environment_reasons",
        "version_drift", "python", "numpy_version", "scipy_version",
        "sklearn_version", "glibc", "resolved_environment", "pre_replay",
        "post_replay", "classifier_stdout_parseable",
        "classifier_stderr_present",
    }
    assert set(printed) == allowed
    assert "injected" not in out
    assert "0.8123" not in out
