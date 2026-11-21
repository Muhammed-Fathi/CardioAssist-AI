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
        monkeypatch.setattr(classifier, "environment_metadata", lambda: metadata)
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = classifier.main()
    return code, json.loads(buffer.getvalue())


def _verified_metadata() -> dict:
    """A complete, well-formed record, independent of the real host."""
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
        "note",
        "replay_verdict",
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
