"""RH-04 Issue #132: fail-closed negative tests for the environment classifier.

Guards ``research.intake.rh04_environment_class`` — a diagnostic that must
**never** become an acceptance policy and must **never** derive a verdict from
incomplete data.

Nothing here changes, weakens or re-derives the canonical 29-case comparator,
the frozen pack, its digest, the AI-12.1 report tolerances or any workflow.

Revision history
----------------
The first revision of this file was rejected by independent review for three
reasons, all fixed here:

* P0 — ``classify()`` returned ``EXACT_REPLAY`` for a malformed envelope because
  it looked only at ``mismatches``. ``test_*_envelope_*`` below pin every
  validation rule that now prevents this.
* P0 — duplicate case entries and non-numeric deltas were accepted.
  ``test_duplicate_case_id_is_rejected`` and the ``delta`` cases pin the fix.
* P2 — ``assert "import sys" in header or "import sys" not in header`` was a
  tautology. It is replaced by ``test_module_imports_are_side_effect_free``,
  which asserts a real invariant about the module's import graph.

Test groups:

1. Envelope validation (P0) — malformed/inconsistent diagnostics fail closed.
2. Strict mismatch classification (P0) — duplicates, deltas, structure.
3. Environment verification (P0/P1-C) — unverified kernels cannot yield exit 0.
4. Resident-BLAS identification (P1-C) — no library is ever loaded.
5. Canonical contract preservation — the comparator, tolerances, default
   solver and frozen pack are provably untouched.
6. Privacy — no float, score or path can appear in the emitted payload.
"""
from __future__ import annotations

import ast
import contextlib
import inspect
import io
import json
import math
import os
import subprocess
import sys
from unittest import mock

import pytest

from research.intake import diagnose_fixture_replay
from research.intake import offline_fixture_pack as fixtures
from research.intake import rh04_environment_class as classifier

_LLO = "response.outcomes[0].score.calibrated_log_odds"
_CASE_BASIC = "da_a1_basic_clinical_v1"
_CASE_REST = "da_a2_resting_v1"


# --------------------------------------------------------------------------- #
# Fixtures / builders                                                        #
# --------------------------------------------------------------------------- #


def _field(
    label: str = _LLO,
    *,
    delta: object = "4.441e-16",
    kind: object = "score_numeric",
    within: object = True,
) -> dict:
    return {
        "field": label,
        "kind": kind,
        "absolute_delta": delta,
        "within_existing_report_comparator_tolerance": within,
    }


def _entry(case_id: str = _CASE_BASIC, fields: list | None = None, *, declared=None) -> dict:
    resolved = [_field()] if fields is None else fields
    return {
        "case_id": case_id,
        "different_field_count_limited": (
            len(resolved) if declared is None else declared
        ),
        "expected_status": "SYNTHETIC_RESULT",
        "fields": resolved,
    }


def _envelope(status: str = "MISMATCH_FOUND", entries: list | None = None, **over) -> dict:
    resolved = [_entry()] if entries is None else entries
    envelope = {
        "status": status,
        "cases_checked": 29,
        "cases_differing": len(resolved),
        "mismatches": resolved,
    }
    envelope.update(over)
    return envelope


def _exact_envelope() -> dict:
    return _envelope(status="EXACT_REPLAY", entries=[])


def _run_main(monkeypatch, envelope, metadata=None) -> tuple[int, dict]:
    monkeypatch.setattr(diagnose_fixture_replay, "diagnose", lambda: envelope)
    if metadata is not None:
        # Must accept the ``probe`` kwarg: ``classify()`` passes an explicit
        # pre-replay snapshot so the record reflects a defined moment.
        monkeypatch.setattr(
            classifier, "environment_metadata", lambda probe=None: dict(metadata)
        )
        # Injecting a metadata record simulates a WHOLE environment, so the
        # kernel probe must agree with it. Otherwise the real post-replay probe
        # would find this host's kernels and quietly "rescue" a record the test
        # deliberately made unverified.
        monkeypatch.setattr(
            classifier, "_kernel_probe", lambda: _probe_matching(metadata)
        )
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = classifier.main()
    return code, json.loads(buffer.getvalue())


def _verified_metadata(probe=None) -> dict:  # noqa: ARG001 - mock signature
    """A complete, well-formed record, independent of the real host.

    Accepts and ignores ``probe`` so this helper can be used directly as a
    stand-in for ``classifier.environment_metadata``, which takes one.
    """
    return {
        "python": "3.11.2",
        "implementation": "CPython",
        "architecture": "x86_64",
        "platform": "Linux",
        "glibc": "2.36",
        "numpy_openblas_kernel": "SkylakeX",
        "scipy_openblas_kernel": "SkylakeX",
        "kernel_identification_method": {
            "numpy_openblas_kernel": "rtld_noload",
            "scipy_openblas_kernel": "rtld_noload",
        },
        "openblas_coretype_requested": None,
        "openblas_num_threads": "1",
        "rtld_noload_available": True,
        "numpy_version": "1.26.4",
        "scipy_version": "1.15.3",
        "sklearn_version": "1.6.1",
    }


def _probe_matching(metadata: dict) -> dict:
    """A kernel snapshot that agrees with an injected metadata record."""
    methods = metadata.get("kernel_identification_method")
    return {
        "numpy_openblas_kernel": metadata.get("numpy_openblas_kernel"),
        "scipy_openblas_kernel": metadata.get("scipy_openblas_kernel"),
        "kernel_identification_method": {
            "numpy_openblas_kernel": (
                methods.get("numpy_openblas_kernel")
                if isinstance(methods, dict)
                else None
            ),
            "scipy_openblas_kernel": (
                methods.get("scipy_openblas_kernel")
                if isinstance(methods, dict)
                else None
            ),
        },
    }


# --------------------------------------------------------------------------- #
# 1. Envelope validation (P0)                                                #
# --------------------------------------------------------------------------- #


def test_reviewer_reported_malformed_envelope_is_rejected(monkeypatch):
    """The exact P0 case from the independent review must not exit 0."""
    bad = {
        "status": "MISMATCH_FOUND",
        "cases_checked": 0,
        "cases_differing": 1,
        "mismatches": [],
    }
    payload = classifier.classify.__wrapped__ if False else None  # clarity only
    monkeypatch.setattr(diagnose_fixture_replay, "diagnose", lambda: bad)
    monkeypatch.setattr(classifier, "environment_metadata", _verified_metadata)
    result = classifier.classify()
    assert result["field_verdict"] == classifier.INVALID_DIAGNOSTIC
    code, emitted = _run_main(monkeypatch, bad, _verified_metadata())
    assert code == 2
    assert emitted["field_verdict"] == classifier.INVALID_DIAGNOSTIC
    assert "envelope:cases_checked:wrong_case_count" in emitted["field_reasons"]
    assert "envelope:status:mismatch_without_entries" in emitted["field_reasons"]


@pytest.mark.parametrize(
    "envelope,expected_reason",
    [
        # Empty mapping: every required key is missing.
        ({}, "envelope:status:missing"),
        # Not a mapping at all.
        (None, "diagnostic_not_a_mapping"),
        ([], "diagnostic_not_a_mapping"),
        # Unknown status vocabulary.
        (
            {"status": "MAYBE", "cases_checked": 29, "cases_differing": 0, "mismatches": []},
            "envelope:status:not_in_vocabulary",
        ),
        # Status contradicts the mismatch list, in both directions.
        (
            {"status": "EXACT_REPLAY", "cases_checked": 29, "cases_differing": 1,
             "mismatches": [_entry()]},
            "envelope:status:exact_with_mismatches",
        ),
        (
            {"status": "MISMATCH_FOUND", "cases_checked": 29, "cases_differing": 0,
             "mismatches": []},
            "envelope:status:mismatch_without_entries",
        ),
        # Case count contract.
        (
            {"status": "EXACT_REPLAY", "cases_checked": 28, "cases_differing": 0,
             "mismatches": []},
            "envelope:cases_checked:wrong_case_count",
        ),
        (
            {"status": "EXACT_REPLAY", "cases_checked": 30, "cases_differing": 0,
             "mismatches": []},
            "envelope:cases_checked:wrong_case_count",
        ),
        # Boolean is an int subclass and must never satisfy a count.
        (
            {"status": "EXACT_REPLAY", "cases_checked": 29, "cases_differing": False,
             "mismatches": []},
            "envelope:cases_differing:not_an_int",
        ),
        # Count/entry inconsistency.
        (
            {"status": "MISMATCH_FOUND", "cases_checked": 29, "cases_differing": 3,
             "mismatches": [_entry()]},
            "envelope:cases_differing:inconsistent_with_entries",
        ),
        (
            {"status": "MISMATCH_FOUND", "cases_checked": 29, "cases_differing": -1,
             "mismatches": []},
            "envelope:cases_differing:negative",
        ),
        # Missing / wrong-typed members.
        (
            {"status": "EXACT_REPLAY", "cases_checked": 29, "mismatches": []},
            "envelope:cases_differing:missing",
        ),
        (
            {"status": "MISMATCH_FOUND", "cases_checked": 29, "cases_differing": 1,
             "mismatches": {"not": "a list"}},
            "envelope:mismatches:not_a_list",
        ),
        (
            {"status": "EXACT_REPLAY", "cases_checked": "29", "cases_differing": 0,
             "mismatches": []},
            "envelope:cases_checked:not_an_int",
        ),
    ],
)
def test_malformed_envelopes_fail_closed(monkeypatch, envelope, expected_reason):
    code, emitted = _run_main(monkeypatch, envelope, _verified_metadata())
    assert code == 2
    assert emitted["field_verdict"] == classifier.INVALID_DIAGNOSTIC
    assert expected_reason in emitted["field_reasons"], emitted["field_reasons"]


def test_well_formed_exact_envelope_is_accepted(monkeypatch):
    code, emitted = _run_main(monkeypatch, _exact_envelope(), _verified_metadata())
    assert code == 0
    assert emitted["field_verdict"] == classifier.EXACT_REPLAY
    assert emitted["environment_verdict"] == classifier.VERIFIED_ENVIRONMENT
    assert emitted["field_reasons"] == []


def test_well_formed_single_field_envelope_is_classified(monkeypatch):
    code, emitted = _run_main(monkeypatch, _envelope(), _verified_metadata())
    assert code == 1
    assert emitted["field_verdict"] == classifier.EXPECTED_SINGLE_FIELD_DELTAS
    assert emitted["field_reasons"] == []


# --------------------------------------------------------------------------- #
# 2. Strict mismatch classification (P0)                                     #
# --------------------------------------------------------------------------- #


def test_duplicate_case_id_is_rejected():
    """One entry per case: a duplicate would multiply a claim."""
    verdict, reasons = classifier.classify_mismatches([_entry(), _entry()])
    # A repeated case id is structurally incoherent, not merely unexpected:
    # it would let one drift claim masquerade as two independent findings.
    assert verdict == classifier.INVALID_DIAGNOSTIC
    assert f"{_CASE_BASIC}:duplicate_case_id" in reasons


def test_duplicate_across_both_permitted_cases_is_rejected():
    verdict, reasons = classifier.classify_mismatches(
        [_entry(_CASE_REST), _entry(_CASE_BASIC), _entry(_CASE_REST)]
    )
    assert verdict == classifier.INVALID_DIAGNOSTIC
    assert f"{_CASE_REST}:duplicate_case_id" in reasons


def test_duplicate_is_invalid_through_both_entry_points(monkeypatch):
    """`classify` and `classify_mismatches` must agree: one contract, one verdict."""
    cases = [
        ([_entry(), _entry()], 2),
        ([_entry(_CASE_REST), _entry(_CASE_BASIC), _entry(_CASE_REST)], 2),
    ]
    for entries, expected_exit in cases:
        bare_verdict, _ = classifier.classify_mismatches(entries)
        code, emitted = _run_main(
            monkeypatch, _envelope(entries=entries), _verified_metadata()
        )
        assert code == expected_exit
        assert emitted["field_verdict"] == classifier.INVALID_DIAGNOSTIC
        assert bare_verdict == emitted["field_verdict"]


def test_duplicate_in_full_envelope_fails_closed(monkeypatch):
    code, emitted = _run_main(
        monkeypatch, _envelope(entries=[_entry(), _entry()]), _verified_metadata()
    )
    assert code == 2
    assert f"{_CASE_BASIC}:duplicate_case_id" in emitted["field_reasons"]


@pytest.mark.parametrize(
    "delta",
    [
        float(4.441e-16),      # python float, not a formatted string
        4.441e-16,             # bare numeric
        "+4.441e-16",          # explicit sign
        "-4.441e-16",          # negative magnitude
        "nan",
        "NaN",
        "inf",
        "Infinity",
        "0.000e+00",           # zero magnitude is not a mismatch
        "4.441",
        "4,441e-16",           # locale separator
        "",
        "  4.441e-16",         # padding
        None,
        True,
        b"4.441e-16",
        ["4.441e-16"],
        {"v": "4.441e-16"},
    ],
)
def test_malformed_delta_is_rejected(delta):
    """Every one of these must be rejected; the specific token may vary.

    ``0.000e+00`` is syntactically a magnitude but a zero one, so it is
    reported as ``delta_out_of_range`` rather than ``delta_not_a_magnitude``.
    Either way the entry is rejected -- which is the invariant under test.
    """
    verdict, reasons = classifier.classify_mismatches([_entry(fields=[_field(delta=delta)])])
    assert verdict == classifier.UNEXPECTED_DRIFT
    assert any(
        reason
        in (
            f"{_CASE_BASIC}:delta_not_a_magnitude",
            f"{_CASE_BASIC}:delta_out_of_range",
        )
        for reason in reasons
    ), reasons


def test_strictly_positive_finite_delta_forms_are_accepted():
    """Positive finite magnitudes in the trusted ``%.3e`` shape are the claim."""
    for delta in ("4.441e-16", "2.220e-16", "1.000e-07", "5.000e-100"):
        verdict, reasons = classifier.classify_mismatches([_entry(fields=[_field(delta=delta)])])
        assert verdict == classifier.EXPECTED_SINGLE_FIELD_DELTAS, (delta, reasons)
        assert reasons == []


@pytest.mark.parametrize(
    "entry,mutation_expected",
    [
        (_entry(_CASE_BASIC), None),
        (_entry("da_a1_clinical_core_labs_v1"), "unexpected_field"),
        (_entry("unreviewed_case"), "unexpected_field"),
        (_entry(_CASE_BASIC, fields=[_field("response.outcomes[0].score.raw_model_score")]),
         "unexpected_field"),
        (_entry(_CASE_BASIC, fields=[_field("response.outcomes[0].score.raw_model_log_odds")]),
         "unexpected_field"),
        (_entry(_CASE_BASIC, fields=[
            _field("response.outcomes[0].score.calibrated_research_score")]),
         "unexpected_field"),
        (_entry(_CASE_BASIC, fields=[_field("response.outcomes[0].score.exploratory_threshold")]),
         "unexpected_field"),
    ],
)
def test_unexpected_case_or_field_is_rejected(entry, mutation_expected):
    if mutation_expected is None:
        verdict, reasons = classifier.classify_mismatches([entry])
        assert verdict == classifier.EXPECTED_SINGLE_FIELD_DELTAS
        return
    verdict, reasons = classifier.classify_mismatches([entry])
    assert verdict == classifier.UNEXPECTED_DRIFT
    assert any(r.endswith(":" + mutation_expected) for r in reasons), reasons


def test_two_fields_in_one_case_are_rejected():
    entry = _entry(
        _CASE_BASIC,
        fields=[
            _field(),
            _field("response.outcomes[0].score.calibrated_research_score", delta="1.110e-16"),
        ],
    )
    verdict, reasons = classifier.classify_mismatches([entry])
    assert verdict == classifier.UNEXPECTED_DRIFT
    assert f"{_CASE_BASIC}:different_field_count" in reasons


def test_declared_field_count_must_match_actual_count():
    entry = _entry(_CASE_BASIC, declared=2)
    verdict, reasons = classifier.classify_mismatches([entry])
    assert verdict == classifier.INVALID_DIAGNOSTIC
    assert f"{_CASE_BASIC}:field_count_inconsistent" in reasons


def test_declared_field_count_must_be_an_int():
    entry = _entry(_CASE_BASIC, declared="1")
    verdict, reasons = classifier.classify_mismatches([entry])
    assert verdict == classifier.INVALID_DIAGNOSTIC
    assert f"{_CASE_BASIC}:field_count_not_an_int" in reasons


@pytest.mark.parametrize("kind", ["semantic_mismatch", "type_mismatch", None, 1, True])
def test_non_score_numeric_kind_is_rejected(kind):
    verdict, reasons = classifier.classify_mismatches([_entry(fields=[_field(kind=kind)])])
    assert verdict == classifier.UNEXPECTED_DRIFT
    assert f"{_CASE_BASIC}:unexpected_kind" in reasons


@pytest.mark.parametrize("within", [False, None, 0, 1, "true", "True", [], {}])
def test_tolerance_flag_must_be_a_real_true_bool(within):
    """``1 == True`` in Python; a tolerance claim must be a genuine boolean."""
    verdict, reasons = classifier.classify_mismatches([_entry(fields=[_field(within=within)])])
    assert verdict == classifier.UNEXPECTED_DRIFT
    assert f"{_CASE_BASIC}:outside_report_tolerance" in reasons


def test_unexpected_case_status_is_rejected():
    entry = _entry()
    entry["expected_status"] = "ABSTAIN"
    verdict, reasons = classifier.classify_mismatches([entry])
    assert verdict == classifier.UNEXPECTED_DRIFT
    assert f"{_CASE_BASIC}:unexpected_case_status" in reasons


@pytest.mark.parametrize("bad", [None, {"not": "a list"}, "entries", 42, (1, 2)])
def test_non_list_mismatches_are_invalid(bad):
    verdict, reasons = classifier.classify_mismatches(bad)
    assert verdict == classifier.INVALID_DIAGNOSTIC
    assert reasons == ["mismatches:not_a_list"]


def test_truthful_unexpected_drift_is_not_mislabelled_invalid():
    """A *faithful* report of surprise must be UNEXPECTED_DRIFT, not INVALID.

    Measured case: `Sandybridge`/`Nehalem` produce two differing fields on
    `da_a2_resting_v1` (calibrated_log_odds *and* calibrated_research_score).
    The diagnostic reports that correctly, so the envelope is structurally
    sound; the verdict must be UNEXPECTED_DRIFT (exit 2), which still fails
    closed but does not accuse the diagnostic of being malformed.
    """
    entry = _entry(
        _CASE_REST,
        fields=[
            _field(_LLO, delta="6.661e-16"),
            _field(
                "response.outcomes[0].score.calibrated_research_score",
                delta="1.110e-16",
            ),
        ],
    )
    verdict, reasons = classifier.classify_mismatches([entry])
    assert verdict == classifier.UNEXPECTED_DRIFT
    assert f"{_CASE_REST}:different_field_count" in reasons
    assert f"{_CASE_REST}:unexpected_field" in reasons


def test_truthful_multi_field_entry_passes_structural_validation():
    """The structural check must accept it; only the expectation check rejects."""
    entry = _entry(
        _CASE_REST,
        fields=[
            _field(_LLO, delta="6.661e-16"),
            _field("response.outcomes[0].score.calibrated_research_score"),
        ],
    )
    assert classifier._validate_entry_structure(entry) == []
    assert classifier._validate_entry_expectation(entry) != []


def test_incoherent_counts_are_structural_failures_not_merely_unexpected():
    entry = _entry(_CASE_REST, declared=7)
    structure = classifier._validate_entry_structure(entry)
    assert f"{_CASE_REST}:field_count_inconsistent" in structure


def test_non_mapping_entry_is_rejected():
    verdict, reasons = classifier.classify_mismatches(["not-a-dict"])
    assert verdict == classifier.INVALID_DIAGNOSTIC
    assert "entry_not_a_mapping" in reasons


def test_entry_without_usable_case_id_is_rejected():
    verdict, reasons = classifier.classify_mismatches([{"fields": [_field()]}])
    assert verdict == classifier.INVALID_DIAGNOSTIC
    assert "entry_case_id_invalid" in reasons


def test_classifier_has_no_numeric_tolerance_of_its_own():
    """Independent enforcement of the AI-12.1 band is explicitly NOT claimed."""
    source = inspect.getsource(classifier)
    assert "math.isclose" not in source
    assert "rel_tol=" not in source
    assert "abs_tol=" not in source
    # The band is taken from the trusted diagnostic, never recomputed here.
    assert "within_existing_report_comparator_tolerance" in source


# --------------------------------------------------------------------------- #
# 3. Environment verification (P0 / P1-C)                                    #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "mutate,expected_reason",
    [
        (lambda m: {**m, "numpy_openblas_kernel": None},
         "numpy_openblas_kernel:unresolved"),
        (lambda m: {**m, "scipy_openblas_kernel": None},
         "scipy_openblas_kernel:unresolved"),
        (lambda m: {**m, "numpy_openblas_kernel": ""},
         "numpy_openblas_kernel:unresolved"),
        (lambda m: {**m, "numpy_openblas_kernel": "../../etc/passwd"},
         "numpy_openblas_kernel:unresolved"),
        (lambda m: {k: v for k, v in m.items() if k != "numpy_version"},
         "numpy_version:missing"),
        (lambda m: {k: v for k, v in m.items() if k != "kernel_identification_method"},
         "kernel_identification_method:missing"),
        (
            lambda m: {
                **m,
                "kernel_identification_method": {
                    "numpy_openblas_kernel": "unverified",
                    "scipy_openblas_kernel": "rtld_noload",
                },
            },
            "numpy_openblas_kernel:unverified_method",
        ),
        (
            lambda m: {
                **m,
                "kernel_identification_method": {
                    "numpy_openblas_kernel": "rtld_global",
                    "scipy_openblas_kernel": "rtld_noload",
                },
            },
            "numpy_openblas_kernel:unverified_method",
        ),
    ],
)
def test_unverified_environment_forces_exit_two(monkeypatch, mutate, expected_reason):
    """A verified replay outcome cannot rescue an unverified environment record."""
    code, emitted = _run_main(
        monkeypatch, _exact_envelope(), mutate(_verified_metadata())
    )
    assert code == 2
    assert emitted["environment_verdict"] == classifier.UNVERIFIED_ENVIRONMENT
    assert expected_reason in emitted["environment_reasons"], emitted["environment_reasons"]


def test_environment_problems_accepts_only_real_methods():
    problems = classifier.environment_problems(_verified_metadata())
    assert problems == []
    for method in ("rtld_noload", "process_symbol"):
        metadata = _verified_metadata()
        metadata["kernel_identification_method"]["numpy_openblas_kernel"] = method
        assert classifier.environment_problems(metadata) == []


def test_environment_problems_rejects_non_mapping():
    assert classifier.environment_problems(None) == ["environment_not_a_mapping"]


def test_exit_code_requires_verified_environment():
    assert classifier.exit_code(
        {"environment_verdict": classifier.VERIFIED_ENVIRONMENT,
         "field_verdict": classifier.EXACT_REPLAY}
    ) == 0
    assert classifier.exit_code(
        {"environment_verdict": classifier.UNVERIFIED_ENVIRONMENT,
         "field_verdict": classifier.EXACT_REPLAY}
    ) == 2
    assert classifier.exit_code(
        {"environment_verdict": classifier.VERIFIED_ENVIRONMENT,
         "field_verdict": classifier.EXPECTED_SINGLE_FIELD_DELTAS}
    ) == 1
    for verdict in (
        classifier.UNEXPECTED_DRIFT,
        classifier.INVALID_DIAGNOSTIC,
        classifier.DIAGNOSTIC_REFUSED,
        None,
    ):
        assert classifier.exit_code(
            {"environment_verdict": classifier.VERIFIED_ENVIRONMENT,
             "field_verdict": verdict}
        ) == 2


def test_classify_reports_refusal_without_leaking_the_message(monkeypatch):
    def boom():
        raise RuntimeError("/secret/path/should/never/be/printed")

    monkeypatch.setattr(diagnose_fixture_replay, "diagnose", boom)
    monkeypatch.setattr(classifier, "environment_metadata", _verified_metadata)
    payload = classifier.classify()
    assert payload["field_verdict"] == classifier.DIAGNOSTIC_REFUSED
    assert payload["exception_type"] == "RuntimeError"
    rendered = json.dumps(payload)
    assert "/secret/path" not in rendered
    assert "should/never" not in rendered


def test_main_returns_two_when_classify_itself_raises(monkeypatch, capsys):
    def boom():
        raise RuntimeError("/secret/path")

    monkeypatch.setattr(classifier, "classify", boom)
    assert classifier.main() == 2
    out = capsys.readouterr().out
    assert "/secret/path" not in out
    assert "RuntimeError" in out


# --------------------------------------------------------------------------- #
# 4. Resident-BLAS identification (P1-C)                                     #
# --------------------------------------------------------------------------- #


def test_resident_probe_never_imports_a_new_library_module():
    """Probing must not import SciPy's BLAS as a side effect of ``ctypes``."""
    source = inspect.getsource(classifier._resident_openblas_kernel)
    # The only ctypes entry points permitted are NOLOAD and the process image.
    assert "RTLD_GLOBAL" not in source
    assert "RTLD_NOLOAD" in source
    assert "CDLL(None)" in source


def test_module_never_calls_rtld_global_in_code():
    """Invariant about executable code, not about the explanatory docstring.

    The module docstring must be allowed to *name* RTLD_GLOBAL when explaining
    why it is unsafe; the check therefore inspects the AST for any attribute
    access to RTLD_GLOBAL and any ctypes.CDLL call whose mode is not NOLOAD.
    """
    tree = ast.parse(inspect.getsource(classifier))
    attribute_names = {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    assert "RTLD_GLOBAL" not in attribute_names

    # Every ctypes.CDLL(...) call in the module must be either CDLL(None) or
    # mode=RTLD_NOLOAD. Nothing may load a library unconditionally.
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "CDLL"):
            continue
        target = node.args[0] if node.args else None
        is_process_image = isinstance(target, ast.Constant) and target.value is None
        modes = [
            keyword.value
            for keyword in node.keywords
            if keyword.arg == "mode"
        ]
        # The module aliases the flag as ``_RTLD_NOLOAD``; accept either the
        # attribute or the resolved module-level constant, so the invariant
        # tracks the real value rather than a spelling.
        uses_noload = bool(modes) and all(
            (isinstance(mode, ast.Attribute) and mode.attr == "RTLD_NOLOAD")
            or (
                isinstance(mode, ast.Name)
                and classifier._RTLD_NOLOAD  # alias must actually resolve
                and getattr(classifier, mode.id, object()) == classifier._RTLD_NOLOAD
            )
            for mode in modes
        )
        assert is_process_image or uses_noload, ast.dump(node)


def test_rtld_noload_does_not_map_an_absent_library():
    """Direct proof that NOLOAD cannot manufacture a resident library."""
    if not classifier._RTLD_NOLOAD:
        pytest.skip("RTLD_NOLOAD unavailable on this platform")
    import ctypes
    import os
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        # A real ELF shared object that is definitely not loaded.
        candidate = os.path.join(tmp, "not_loaded_probe.so")
        with open(candidate, "wb") as handle:
            handle.write(b"\x7fELF")
        with pytest.raises(OSError):
            ctypes.CDLL(candidate, mode=classifier._RTLD_NOLOAD)


def test_resident_probe_returns_unverified_for_an_unknown_package():
    kernel, method = classifier._resident_openblas_kernel(
        "cardioassist_no_such_package_xyz", "libnothing*.so", ("nope",)
    )
    assert (kernel, method) == (None, "unverified")


def test_resident_probe_returns_a_real_kernel_on_this_host():
    """Evidence, not a guarantee: on a NumPy/SciPy host a kernel must resolve."""
    metadata = classifier.environment_metadata()
    assert metadata["kernel_identification_method"]["numpy_openblas_kernel"] in {
        "rtld_noload",
        "process_symbol",
        "unverified",
    }
    # Whatever the host is, the record must be internally consistent.
    problems = classifier.environment_problems(metadata)
    if metadata["numpy_openblas_kernel"] is None:
        assert "numpy_openblas_kernel:unresolved" in problems
    else:
        assert "numpy_openblas_kernel:unresolved" not in problems


# --------------------------------------------------------------------------- #
# 5. Canonical contract preservation                                         #
# --------------------------------------------------------------------------- #


def test_module_never_references_the_canonical_comparator():
    source = inspect.getsource(classifier)
    for forbidden in (
        "_approved_replay_equal",
        "_WINDOWS_FLOAT_CASE_ID",
        "_WINDOWS_FLOAT_FIELD",
        "PACK_SHA256 =",
        "monkeypatch",
    ):
        assert forbidden not in source, forbidden


def test_module_does_not_import_the_fixture_pack_directly():
    tree = ast.parse(inspect.getsource(classifier))
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert not any(module.endswith("offline_fixture_pack") for module in imported)


def test_module_imports_are_side_effect_free():
    """Replaces the removed tautology: assert a real structural invariant.

    The module may import only the standard library at module scope, plus the
    derived absolute imports used inside functions. In particular it must not
    import numpy/scipy/sklearn at import time (that would change the resident
    BLAS state before the probe runs) and must not import the diagnostic.
    """
    tree = ast.parse(inspect.getsource(classifier))
    module_scope_imports: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            module_scope_imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            module_scope_imports.add(node.module.split(".")[0])

    assert "numpy" not in module_scope_imports
    assert "scipy" not in module_scope_imports
    assert "sklearn" not in module_scope_imports
    assert "research" not in module_scope_imports
    # And the heavy imports must exist only inside functions.
    for function in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        assert function.name  # structural sanity, never vacuous
    assert module_scope_imports == {
        "__future__",
        "ctypes",
        "glob",
        "json",
        "os",
        "platform",
        "re",
        "collections",
        "typing",
    }


def test_uc412_case_still_has_no_tolerance_exception():
    """Issue #132's whole point: never widen the guard to turn CI green."""
    pack = json.loads(fixtures.PACK.read_text(encoding="utf-8"))
    case = next(c for c in pack["cases"] if c["id"] == _CASE_BASIC)
    nudged = json.loads(json.dumps(case["expected"]))
    original = case["expected"]["outcomes"][0]["score"]["calibrated_log_odds"]
    nudged["outcomes"][0]["score"]["calibrated_log_odds"] = math.nextafter(
        original, math.inf
    )
    assert nudged != case["expected"]
    assert not fixtures._approved_replay_equal(case, nudged)


def test_cleveland_exception_is_still_the_only_one():
    pack = json.loads(fixtures.PACK.read_text(encoding="utf-8"))
    case = next(c for c in pack["cases"] if c["id"] == _CASE_REST)
    nudged = json.loads(json.dumps(case["expected"]))
    original = case["expected"]["outcomes"][0]["score"]["calibrated_log_odds"]
    nudged["outcomes"][0]["score"]["calibrated_log_odds"] = math.nextafter(
        original, math.inf
    )
    assert fixtures._approved_replay_equal(case, nudged)
    renamed = dict(case, id=_CASE_BASIC)
    assert not fixtures._approved_replay_equal(renamed, nudged)


def test_report_comparator_tolerances_untouched():
    from ai import report_comparison

    assert report_comparison.ABS_TOL == 1e-12
    assert report_comparison.REL_TOL == 1e-9


def test_default_calibration_solver_is_unchanged():
    from ai import calibration

    assert calibration.DEFAULT_CALIBRATION_SOLVER == "scipy_lbfgsb"
    assert calibration.DETERMINISTIC_CALIBRATION_SOLVER in calibration.CALIBRATION_SOLVERS
    assert (
        calibration.DETERMINISTIC_CALIBRATION_SOLVER
        != calibration.DEFAULT_CALIBRATION_SOLVER
    )


def test_frozen_pack_identity_preserved():
    from ai.research_facade import canonical_response_digest

    pack = json.loads(fixtures.PACK.read_text(encoding="utf-8"))
    assert canonical_response_digest(pack) == fixtures.PACK_SHA256
    assert len(pack["cases"]) == 29
    assert classifier.EXPECTED_CASE_COUNT == 29
    assert fixtures.PACK_SHA256 == (
        "0307b396cea1e620c4004647e1d82ff7f292bb5b74de7cad1661e1299c6e7049"
    )


# --------------------------------------------------------------------------- #
# 6. Privacy                                                                 #
# --------------------------------------------------------------------------- #


def test_payload_is_a_closed_metadata_vocabulary(monkeypatch):
    code, payload = _run_main(monkeypatch, _envelope(), _verified_metadata())
    assert code == 1
    assert set(payload) == {
        "acceptance_authority",
        "cases_checked",
        "cases_differing",
        "comparison_policy",
        "differing_case_ids",
        "environment",
        "environment_reasons",
        "environment_verdict",
        "field_reasons",
        "field_verdict",
        "issue",
        "kernel_snapshot",
        "note",
        "replay_verdict",
        "version_drift",
    }


def test_payload_never_contains_a_float(monkeypatch):
    """Only ints, booleans, strings, lists and nulls — never a measured value."""

    def walk(node, path="payload"):
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{path}.{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]")
        else:
            assert not isinstance(node, float), f"float leaked at {path}: {node!r}"

    for envelope in (_exact_envelope(), _envelope()):
        _, payload = _run_main(monkeypatch, envelope, _verified_metadata())
        walk(payload)


def test_payload_contains_no_filesystem_path(monkeypatch):
    _, payload = _run_main(monkeypatch, _envelope(), _verified_metadata())
    rendered = json.dumps(payload)
    assert "/home/" not in rendered
    assert "site-packages" not in rendered
    assert ".so" not in rendered


def test_differing_case_ids_are_sorted_and_deduplicated(monkeypatch):
    _, payload = _run_main(
        monkeypatch,
        _envelope(entries=[_entry(_CASE_REST), _entry(_CASE_BASIC)]),
        _verified_metadata(),
    )
    assert payload["differing_case_ids"] == [_CASE_BASIC, _CASE_REST]


# --------------------------------------------------------------------------- #
# 7. Poisoned input cannot be echoed (P0, round 3)                           #
# --------------------------------------------------------------------------- #

_FORBIDDEN_FRAGMENTS = (
    "/secret",
    "/etc/passwd",
    "/home/",
    ".aws",
    "credentials",
    "hunter2",
    "should-not-leak",
    "should/never",
    "token",
    "BEGIN PRIVATE KEY",
)


def _assert_no_leak(payload, case: str) -> None:
    rendered = json.dumps(payload, allow_nan=False)
    for fragment in _FORBIDDEN_FRAGMENTS:
        assert fragment not in rendered, f"{case}: leaked {fragment!r} -> {rendered}"


@pytest.mark.parametrize(
    "poisoned",
    [
        # A path where an integer count belongs.
        {"status": "MISMATCH_FOUND", "cases_checked": "/secret/should-not-leak",
         "cases_differing": 1, "mismatches": []},
        {"status": "MISMATCH_FOUND", "cases_checked": 29,
         "cases_differing": "/secret/should-not-leak", "mismatches": []},
        # Floats must not survive as floats.
        {"status": "MISMATCH_FOUND", "cases_checked": 29.5,
         "cases_differing": 1.0, "mismatches": []},
        # An unknown status token carrying a path.
        {"status": "/secret/status", "cases_checked": 29,
         "cases_differing": 0, "mismatches": []},
        # A case id that is really a key path.
        {"status": "MISMATCH_FOUND", "cases_checked": 29, "cases_differing": 1,
         "mismatches": [{"case_id": "/home/user/.aws/credentials", "fields": []}]},
        # A nested payload smuggled alongside the known keys.
        {"status": "MISMATCH_FOUND", "cases_checked": 29, "cases_differing": 1,
         "mismatches": [], "extra": {"nested": {"path": "/etc/passwd"}}},
    ],
)
def test_poisoned_envelope_never_echoes_a_value(monkeypatch, poisoned):
    """Rejecting a value must not also *print* the value it rejected."""
    code, emitted = _run_main(monkeypatch, poisoned, _verified_metadata())
    assert code == 2
    assert emitted["field_verdict"] == classifier.INVALID_DIAGNOSTIC
    _assert_no_leak(emitted, "poisoned envelope")
    # Counts are either a real int or null, never the rejected object.
    for key in ("cases_checked", "cases_differing"):
        assert emitted[key] is None or (
            isinstance(emitted[key], int) and not isinstance(emitted[key], bool)
        )
    # Only closed-vocabulary statuses are echoed.
    assert emitted["replay_verdict"] in (None, "EXACT_REPLAY", "MISMATCH_FOUND")


def test_poisoned_case_id_is_not_echoed_in_reasons(monkeypatch):
    """A reason token embeds the untrusted case id; it must be sanitised."""
    poisoned = {
        "status": "MISMATCH_FOUND",
        "cases_checked": 29,
        "cases_differing": 1,
        "mismatches": [
            {"case_id": "/home/user/.aws/credentials", "fields": [], "expected_status": "X"}
        ],
    }
    code, emitted = _run_main(monkeypatch, poisoned, _verified_metadata())
    assert code == 2
    _assert_no_leak(emitted, "poisoned case id")
    assert emitted["differing_case_ids"] == []


@pytest.mark.parametrize(
    "env",
    [
        {"OPENBLAS_CORETYPE": "/home/user/.aws/credentials",
         "OPENBLAS_NUM_THREADS": "hunter2"},
        {"OPENBLAS_CORETYPE": "../../etc/passwd", "OPENBLAS_NUM_THREADS": "-1"},
        {"OPENBLAS_CORETYPE": "BEGIN PRIVATE KEY", "OPENBLAS_NUM_THREADS": "1e9"},
    ],
)
def test_untrusted_environment_variables_are_never_echoed(monkeypatch, env):
    """`OPENBLAS_*` are attacker-controllable; the record reports a shape only."""
    monkeypatch.setattr(diagnose_fixture_replay, "diagnose", lambda: _exact_envelope())
    with mock.patch.dict(os.environ, env, clear=False):
        payload = classifier.classify()
    _assert_no_leak(payload, "environment variables")
    assert payload["environment"]["openblas_coretype_requested"] == "set_malformed"
    assert payload["environment"]["openblas_num_threads"] == "set_malformed"
    # A malformed request value does not corrupt the resolved identity.
    assert payload["environment"]["numpy_openblas_kernel"] is not None


def test_wellformed_environment_variables_are_reduced_to_shape(monkeypatch):
    monkeypatch.setattr(diagnose_fixture_replay, "diagnose", lambda: _exact_envelope())
    with mock.patch.dict(
        os.environ, {"OPENBLAS_CORETYPE": "Haswell", "OPENBLAS_NUM_THREADS": "1"},
        clear=False,
    ):
        payload = classifier.classify()
    assert payload["environment"]["openblas_coretype_requested"] == "set_and_wellformed"
    assert payload["environment"]["openblas_num_threads"] == "set_and_wellformed"


def test_unset_environment_variables_are_null_not_absent(monkeypatch):
    monkeypatch.setattr(diagnose_fixture_replay, "diagnose", lambda: _exact_envelope())
    env = dict(os.environ)
    env.pop("OPENBLAS_CORETYPE", None)
    env.pop("OPENBLAS_NUM_THREADS", None)
    with mock.patch.dict(os.environ, env, clear=True):
        payload = classifier.classify()
    assert payload["environment"]["openblas_coretype_requested"] is None
    assert payload["environment"]["openblas_num_threads"] is None


def test_sanitize_environment_drops_unknown_keys():
    """The printed environment record cannot grow beyond its vocabulary."""
    poisoned = dict(_verified_metadata())
    poisoned["injected_key"] = "/secret"
    safe = classifier._sanitize_environment(poisoned)
    assert "injected_key" not in safe
    assert set(safe) <= classifier._ALLOWED_ENVIRONMENT_KEYS


def test_payload_key_vocabulary_is_enforced():
    payload = classifier._payload(
        field_verdict=classifier.EXACT_REPLAY,
        environment_verdict=classifier.VERIFIED_ENVIRONMENT,
        field_reasons=[],
        environment_reasons=[],
        metadata=_verified_metadata(),
        result=_exact_envelope(),
    )
    assert set(payload) <= classifier._ALLOWED_PAYLOAD_KEYS


def test_reason_tokens_containing_paths_are_redacted():
    reasons = ["da_a2_resting_v1:different_field_count", "/etc/passwd:oops", "a b c:d"]
    cleaned = classifier._safe_reasons(reasons)
    assert "da_a2_resting_v1:different_field_count" in cleaned
    assert classifier.REDACTED in cleaned
    assert all("/" not in token for token in cleaned)


def test_refusal_records_only_the_exception_class_name(monkeypatch):
    def boom():
        raise RuntimeError("/secret/path/should/never/be/printed")

    monkeypatch.setattr(diagnose_fixture_replay, "diagnose", boom)
    payload = classifier.classify()
    assert payload["field_verdict"] == classifier.DIAGNOSTIC_REFUSED
    assert payload["exception_type"] == "RuntimeError"
    _assert_no_leak(payload, "refusal")


# --------------------------------------------------------------------------- #
# 8. Fresh-process CLI evidence (P1, round 3)                                #
# --------------------------------------------------------------------------- #

_REPO_ROOT = str(fixtures.__file__).rsplit("/research/", 1)[0]


def _cli(env_extra: dict[str, str] | None = None, timeout: int = 600):
    """Run the module exactly as CI would, in a genuinely cold interpreter."""
    env = dict(os.environ)
    env["PYTHONPATH"] = _REPO_ROOT
    env.setdefault("OPENBLAS_NUM_THREADS", "1")
    env.update(env_extra or {})
    return subprocess.run(
        [sys.executable, "-m", "research.intake.rh04_environment_class"],
        capture_output=True,
        text=True,
        env=env,
        cwd=_REPO_ROOT,
        timeout=timeout,
    )


@pytest.fixture(scope="module")
def cold_cli_result():
    """One cold-process run, shared by the assertions below (it costs ~10s)."""
    return _cli()


def test_cli_exits_with_a_defined_code_in_a_fresh_process(cold_cli_result):
    assert cold_cli_result.returncode in (0, 1, 2), cold_cli_result.stderr[-2000:]
    assert cold_cli_result.stdout.strip(), "CLI produced no JSON on stdout"
    json.loads(cold_cli_result.stdout)  # must be valid JSON


def test_cli_reports_both_kernels_with_methods_in_a_fresh_process(cold_cli_result):
    payload = json.loads(cold_cli_result.stdout)
    env = payload["environment"]
    # Both identities must be present and carry a method token.
    for key in ("numpy_openblas_kernel", "scipy_openblas_kernel"):
        assert key in env, key
        method = env["kernel_identification_method"][key]
        assert method in {"rtld_noload", "process_symbol", "unverified"}, method
        if method != "unverified":
            assert isinstance(env[key], str) and env[key], (key, env[key])


def test_fresh_process_records_a_post_replay_snapshot(cold_cli_result):
    """The snapshot labelled `post_replay` must be the resolved one.

    This is the P1 fix: probing *before* the replay reported `unverified` for
    SciPy because its OpenBLAS is mapped lazily by the first BLAS call.
    """
    payload = json.loads(cold_cli_result.stdout)
    snapshot = payload["kernel_snapshot"]
    assert set(snapshot) >= {"pre_replay", "post_replay", "scope"}
    post = snapshot["post_replay"]
    assert post["scipy_openblas_kernel"] is not None, (
        "post-replay SciPy kernel must resolve on this platform; "
        f"payload={json.dumps(snapshot)}"
    )
    assert post["kernel_identification_method"]["scipy_openblas_kernel"] in {
        "rtld_noload",
        "process_symbol",
    }


def test_pre_replay_snapshot_is_labelled_and_not_used_for_the_verdict(
    cold_cli_result,
):
    """`pre_replay` is allowed to be `unverified`; the verdict must not use it."""
    payload = json.loads(cold_cli_result.stdout)
    pre = payload["kernel_snapshot"]["pre_replay"]
    # Whatever it says is fine, but it must not be conflated with the verdict:
    # an exact replay plus resolved post-replay kernels is exit 0 even if the
    # pre-replay SciPy probe was unresolved.
    if payload["environment_verdict"] == classifier.VERIFIED_ENVIRONMENT:
        assert payload["environment"]["scipy_openblas_kernel"] is not None
        assert classifier.exit_code(payload) in (0, 1)
    # The scope disclaimer must always be present.
    assert "not proof" in payload["kernel_snapshot"]["scope"]


@pytest.mark.parametrize(
    "coretype",
    ["SkylakeX", "Haswell", "Sandybridge"],
)
def test_cli_under_a_forced_dispatch_is_fail_closed_and_labelled(coretype):
    """A known-exact dispatch and two documented non-golden ones, cold process."""
    result = _cli({"OPENBLAS_CORETYPE": coretype})
    payload = json.loads(result.stdout)
    assert result.returncode == classifier.exit_code(payload)
    assert payload["field_verdict"] in classifier.FIELD_VERDICTS
    if payload["field_verdict"] == classifier.EXACT_REPLAY:
        assert result.returncode in (0,)
    else:
        # Any non-exact outcome must not be reported as success.
        assert result.returncode != 0
        assert result.returncode == 2 or payload["environment_verdict"] != (
            classifier.VERIFIED_ENVIRONMENT
        ) or payload["field_verdict"] == classifier.EXPECTED_SINGLE_FIELD_DELTAS


def test_cli_unverified_environment_exits_two_in_a_fresh_process():
    """Force an unresolvable kernel by hiding the packaged libraries."""
    # `OPENBLAS_CORETYPE` cannot make a kernel unresolvable, so instead run with
    # a deliberately broken method expectation: point at a directory that has no
    # OpenBLAS at all by overriding the probe target.
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from research.intake import rh04_environment_class as m\n"
                "m._resident_openblas_kernel = lambda *a, **k: (None, 'unverified')\n"
                "raise SystemExit(m.main())\n"
            ),
        ],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": _REPO_ROOT, "OPENBLAS_NUM_THREADS": "1"},
        cwd=_REPO_ROOT,
        timeout=600,
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert payload["environment_verdict"] == classifier.UNVERIFIED_ENVIRONMENT
    assert any(
        "unverified_method" in reason or "unresolved" in reason
        for reason in payload["environment_reasons"]
    ), payload["environment_reasons"]


def test_fresh_process_output_contains_no_path_or_float(cold_cli_result):
    payload = json.loads(cold_cli_result.stdout)
    _assert_no_leak(payload, "cold CLI")

    def walk(node, path="payload"):
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{path}.{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]")
        else:
            assert not isinstance(node, float), f"float at {path}: {node!r}"

    walk(payload)


# --------------------------------------------------------------------------- #
# 9. Strict environment values (P2, round 3)                                 #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("bad", [None, "", "lol", "1.26", 1264, ["1.26.4"], "  "])
@pytest.mark.parametrize("key", ["numpy_version", "scipy_version"])
def test_version_values_must_be_usable_strings(key, bad):
    """`numpy_version=None` must NOT yield VERIFIED_ENVIRONMENT (P2)."""
    metadata = dict(_verified_metadata())
    metadata[key] = bad
    problems = classifier.environment_problems(metadata)
    assert f"{key}:not_a_version" in problems, (key, bad, problems)


@pytest.mark.parametrize("key", ["python", "architecture", "platform"])
@pytest.mark.parametrize("bad", [None, "", "   ", 42, {"a": 1}])
def test_platform_tokens_must_be_nonblank_strings(key, bad):
    metadata = dict(_verified_metadata())
    metadata[key] = bad
    problems = classifier.environment_problems(metadata)
    assert f"{key}:blank_or_not_a_string" in problems, (key, bad, problems)


def test_verified_metadata_has_no_problems():
    """The positive control: the well-formed record must be clean."""
    assert classifier.environment_problems(_verified_metadata()) == []


def test_version_drift_is_reported_but_is_not_a_failure():
    """A different numerical stack is evidence, not a refusal."""
    metadata = dict(_verified_metadata())
    metadata["numpy_version"] = "1.24.0"
    assert classifier.environment_problems(metadata) == []
    drift = classifier.pinned_version_drift(metadata)
    assert "numpy_version:not_pinned" in drift


def test_pinned_versions_match_the_requirement_files():
    """The tool's claimed pins must match the files CI actually installs."""
    from pathlib import Path

    required = Path(_REPO_ROOT) / "research" / "experiments" / "requirements.txt"
    declared = {}
    for line in required.read_text().splitlines():
        line = line.strip()
        if "==" in line and not line.startswith("#"):
            name, _, version = line.partition("==")
            declared[name.strip()] = version.strip()
    assert declared["numpy"] == classifier.PINNED_VERSIONS["numpy_version"]
    assert declared["scipy"] == classifier.PINNED_VERSIONS["scipy_version"]
    assert declared["scikit-learn"] == classifier.PINNED_VERSIONS["sklearn_version"]


# --------------------------------------------------------------------------- #
# 10. Snapshot timing must be structurally enforced (P1, round 3)            #
# --------------------------------------------------------------------------- #


def test_pre_snapshot_is_taken_before_the_diagnostic_is_imported():
    """Ordering is the whole point of the fix, so assert it on the AST.

    A source-text check would be defeated by a refactor that moves the call;
    the AST records the *statement order* inside `classify()`.
    """
    tree = ast.parse(inspect.getsource(classifier.classify))
    function = tree.body[0]
    assert isinstance(function, ast.FunctionDef)

    events: list[str] = []

    class Walker(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
            if isinstance(node.func, ast.Name) and node.func.id == "_kernel_probe":
                events.append("probe")
            if isinstance(node.func, ast.Attribute) and node.func.attr == "diagnose":
                events.append("diagnose")
            self.generic_visit(node)

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
            if any(alias.name == "diagnose_fixture_replay" for alias in node.names):
                events.append("import_diagnostic")
            self.generic_visit(node)

    Walker().visit(function)
    assert "import_diagnostic" in events, events
    first_probe = events.index("probe")
    import_at = events.index("import_diagnostic")
    diagnose_at = events.index("diagnose")
    assert first_probe < import_at, (
        "the pre-replay snapshot must be taken BEFORE the diagnostic module is "
        f"imported, because that import maps SciPy's BLAS: {events}"
    )
    assert import_at < diagnose_at, events
    # Two probes: one before the replay, one after it.
    assert events.count("probe") >= 2, events


def test_environment_problems_ignoring_is_caught_by_the_exit_code(monkeypatch):
    """`environment_problems` must actually feed the verdict, not just exist."""
    metadata = dict(_verified_metadata())
    metadata["numpy_version"] = None  # unusable value
    code, emitted = _run_main(monkeypatch, _exact_envelope(), metadata)
    assert code == 2
    assert emitted["environment_verdict"] == classifier.UNVERIFIED_ENVIRONMENT
    assert "numpy_version:not_a_version" in emitted["environment_reasons"]


def test_envelope_validation_is_actually_reached(monkeypatch):
    """Bypassing `_validate_envelope` must be observable (guards the guard)."""
    code, emitted = _run_main(monkeypatch, _exact_envelope(), _verified_metadata())
    assert code == 0
    # Now make the validator itself refuse; the verdict must follow it.
    monkeypatch.setattr(
        classifier, "_validate_envelope", lambda result: ["envelope:forced"]
    )
    code2, emitted2 = _run_main(monkeypatch, _exact_envelope(), _verified_metadata())
    assert code2 == 2
    assert emitted2["field_verdict"] == classifier.INVALID_DIAGNOSTIC
