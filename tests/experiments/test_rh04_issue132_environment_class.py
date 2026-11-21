"""RH-04 Issue #132: negative tests for the read-only environment classifier.

Guards ``research.intake.rh04_environment_class`` — a diagnostic that must
**never** become an acceptance policy. Nothing here changes, weakens or
re-derives the canonical 29-case comparator, the frozen pack, its digest, the
AI-12.1 report tolerances or any workflow.

The tests fall into four groups:

1. ``classify_mismatches`` is a pure function — it must classify exactly the two
   measured fields and reject everything else, including near-misses that a
   careless implementation would wave through (extra case, extra field, second
   field in the same case, bool deltas, out-of-band tolerance, unexpected kind).
2. The classifier module itself must not import, wrap or shadow the canonical
   replay-equality function, and must not gain a tolerance of its own.
3. The canonical comparator must be provably unchanged: the UCI-412 case still
   has **no** tolerance exception, and the Cleveland exception is still the only
   one.
4. Frozen-artifact preservation: the pack digest, case count and byte content
   are untouched by importing this diagnostic.
"""
from __future__ import annotations

import importlib
import inspect
import json
import math

import pytest

from research.intake import offline_fixture_pack as fixtures
from research.intake import rh04_environment_class as classifier

_LLO = "response.outcomes[0].score.calibrated_log_odds"


def _field(case_id: str, label: str, *, delta: str = "4.441e-16",
           kind: str = "score_numeric", within: object = True) -> dict:
    return {
        "case_id": case_id,
        "different_field_count_limited": 1,
        "expected_status": "SYNTHETIC_RESULT",
        "fields": [
            {
                "field": label,
                "kind": kind,
                "absolute_delta": delta,
                "within_existing_report_comparator_tolerance": within,
            }
        ],
    }


# --------------------------------------------------------------------------- #
# 1. Pure classification function                                            #
# --------------------------------------------------------------------------- #


def test_exact_replay_when_no_mismatches():
    verdict, reasons = classifier.classify_mismatches([])
    assert (verdict, reasons) == ("EXACT_REPLAY", [])


def test_both_measured_fields_classify_as_expected():
    verdict, reasons = classifier.classify_mismatches(
        [_field("da_a2_resting_v1", _LLO), _field("da_a1_basic_clinical_v1", _LLO)]
    )
    assert verdict == "EXPECTED_SINGLE_FIELD_DELTAS"
    assert reasons == []


@pytest.mark.parametrize("case_id", ["da_a2_resting_v1", "da_a1_basic_clinical_v1"])
def test_each_measured_field_classifies_individually(case_id):
    verdict, reasons = classifier.classify_mismatches([_field(case_id, _LLO)])
    assert verdict == "EXPECTED_SINGLE_FIELD_DELTAS"
    assert reasons == []


def test_repeated_case_entries_are_still_the_same_field():
    verdict, reasons = classifier.classify_mismatches(
        [_field("da_a1_basic_clinical_v1", _LLO), _field("da_a1_basic_clinical_v1", _LLO)]
    )
    assert (verdict, reasons) == ("EXPECTED_SINGLE_FIELD_DELTAS", [])


@pytest.mark.parametrize(
    "mutation,expected_reason",
    [
        # A third case drifting is NOT the measured evidence.
        ("other_case", "unexpected_field"),
        # The Cleveland score is exact today; a drift there is new information.
        ("calibrated_research_score", "unexpected_field"),
        # raw log-odds are upstream of the fit and must never drift.
        ("raw_model_log_odds", "unexpected_field"),
        ("raw_model_score", "unexpected_field"),
        # A threshold is a decision boundary, never a measurement.
        ("exploratory_threshold", "unexpected_field"),
    ],
)
def test_unexpected_fields_are_rejected(mutation, expected_reason):
    if mutation == "other_case":
        entry = _field("da_a1_clinical_core_labs_v1", _LLO)
    else:
        entry = _field("da_a1_basic_clinical_v1", f"response.outcomes[0].score.{mutation}")
    verdict, reasons = classifier.classify_mismatches([entry])
    assert verdict == "UNEXPECTED_DRIFT"
    # Reasons are namespaced by case id so the evidence names the failing case.
    assert any(reason.endswith(":" + expected_reason) for reason in reasons), reasons


def test_second_field_in_the_same_case_is_rejected():
    entry = _field("da_a1_basic_clinical_v1", _LLO)
    entry["fields"].append(
        {
            "field": "response.outcomes[0].score.calibrated_research_score",
            "kind": "score_numeric",
            "absolute_delta": "1.110e-16",
            "within_existing_report_comparator_tolerance": True,
        }
    )
    entry["different_field_count_limited"] = 2
    verdict, reasons = classifier.classify_mismatches([entry])
    assert verdict == "UNEXPECTED_DRIFT"
    assert "da_a1_basic_clinical_v1:different_field_count" in reasons
    assert "da_a1_basic_clinical_v1:unexpected_field" in reasons


def test_structural_mismatch_kind_is_rejected():
    verdict, reasons = classifier.classify_mismatches(
        [_field("da_a1_basic_clinical_v1", _LLO, kind="semantic_mismatch")]
    )
    assert verdict == "UNEXPECTED_DRIFT"
    assert "da_a1_basic_clinical_v1:unexpected_kind" in reasons


@pytest.mark.parametrize("within", [False, None, 0, 1, "true", "True"])
def test_outside_or_non_boolean_tolerance_is_rejected(within):
    verdict, reasons = classifier.classify_mismatches(
        [_field("da_a1_basic_clinical_v1", _LLO, within=within)]
    )
    assert verdict == "UNEXPECTED_DRIFT"
    assert "da_a1_basic_clinical_v1:outside_report_tolerance" in reasons


def test_missing_delta_is_rejected():
    entry = _field("da_a1_basic_clinical_v1", _LLO)
    entry["fields"][0]["absolute_delta"] = None
    verdict, reasons = classifier.classify_mismatches([entry])
    assert verdict == "UNEXPECTED_DRIFT"
    assert "da_a1_basic_clinical_v1:delta_not_reported" in reasons


def test_classifier_has_no_numeric_tolerance_of_its_own():
    """The classifier must not re-implement ``isclose`` with its own numbers."""
    source = inspect.getsource(classifier)
    for forbidden in ("rel_tol=", "abs_tol="):
        assert forbidden not in source, forbidden
    assert "math.isclose" not in source


# --------------------------------------------------------------------------- #
# 2. The diagnostic must not shadow or relax the canonical contract           #
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
    """It must consume the reviewed diagnostic, not a private replay path."""
    import ast

    tree = ast.parse(inspect.getsource(classifier))
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert not any(
        module.endswith("offline_fixture_pack") for module in imported
    ), imported


def test_classifier_reports_a_refusal_instead_of_raising(monkeypatch):
    from research.intake import diagnose_fixture_replay

    def boom():
        raise RuntimeError("/secret/path/should/never/be/printed")

    monkeypatch.setattr(diagnose_fixture_replay, "diagnose", boom)
    payload = classifier.classify()
    assert payload["status"] == "DIAGNOSTIC_REFUSED"
    assert payload["exception_type"] == "RuntimeError"
    rendered = json.dumps(payload)
    assert "/secret/path" not in rendered
    assert "should/never" not in rendered


def test_classifier_emits_only_approved_metadata_keys(monkeypatch):
    """The payload must be a closed metadata vocabulary, not a value channel."""
    from research.intake import diagnose_fixture_replay

    monkeypatch.setattr(
        diagnose_fixture_replay,
        "diagnose",
        lambda: {
            "status": "MISMATCH_FOUND",
            "cases_checked": 29,
            "cases_differing": 1,
            "mismatches": [_field("da_a1_basic_clinical_v1", _LLO)],
        },
    )
    payload = classifier.classify()
    assert set(payload) == {
        "cases_checked",
        "cases_differing",
        "comparison_policy",
        "differing_case_ids",
        "environment",
        "issue",
        "note",
        "replay_verdict",
        "status",
        "unexpected_reasons",
    }
    assert set(payload["environment"]) == {
        "architecture",
        "glibc",
        "implementation",
        "numpy_openblas_kernel",
        "numpy_version",
        "openblas_coretype_requested",
        "openblas_num_threads",
        "platform",
        "python",
        "scipy_openblas_kernel",
        "scipy_version",
        "sklearn_version",
    }


def test_classifier_payload_contains_no_float_score_values(monkeypatch):
    """Only integers, booleans, strings and nulls — never a measured value."""
    from research.intake import diagnose_fixture_replay

    monkeypatch.setattr(
        diagnose_fixture_replay,
        "diagnose",
        lambda: {
            "status": "MISMATCH_FOUND",
            "cases_checked": 29,
            "cases_differing": 1,
            "mismatches": [_field("da_a1_basic_clinical_v1", _LLO)],
        },
    )

    def walk(node, path="payload"):
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{path}.{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]")
        else:
            assert not isinstance(node, float), f"float leaked at {path}: {node!r}"

    walk(classifier.classify())


def test_main_exit_codes_are_distinct(monkeypatch, capsys):
    """EXACT=0, classified-expected=1, unexpected/refused=2 — never conflated."""
    from research.intake import diagnose_fixture_replay

    monkeypatch.setattr(
        diagnose_fixture_replay,
        "diagnose",
        lambda: {"status": "EXACT_REPLAY", "cases_checked": 29,
                 "cases_differing": 0, "mismatches": []},
    )
    assert classifier.main() == 0
    capsys.readouterr()

    monkeypatch.setattr(
        diagnose_fixture_replay,
        "diagnose",
        lambda: {"status": "MISMATCH_FOUND", "cases_checked": 29,
                 "cases_differing": 1,
                 "mismatches": [_field("da_a1_basic_clinical_v1", _LLO)]},
    )
    assert classifier.main() == 1
    capsys.readouterr()

    monkeypatch.setattr(
        diagnose_fixture_replay,
        "diagnose",
        lambda: {"status": "MISMATCH_FOUND", "cases_checked": 29,
                 "cases_differing": 1,
                 "mismatches": [_field("da_a2_resting_labs_v1", _LLO)]},
    )
    assert classifier.main() == 2


# --------------------------------------------------------------------------- #
# 3. Canonical comparator must remain exactly as frozen                      #
# --------------------------------------------------------------------------- #


def test_uc412_case_still_has_no_tolerance_exception():
    """The whole point of Issue #132: do not widen the guard to turn CI green."""
    pack = json.loads(fixtures.PACK.read_text(encoding="utf-8"))
    case = next(c for c in pack["cases"] if c["id"] == "da_a1_basic_clinical_v1")
    score = case["expected"]["outcomes"][0]["score"]
    nudged = json.loads(json.dumps(case["expected"]))
    nudged["outcomes"][0]["score"]["calibrated_log_odds"] = math.nextafter(
        score["calibrated_log_odds"], math.inf
    )
    assert nudged != case["expected"]
    assert not fixtures._approved_replay_equal(case, nudged)


def test_cleveland_exception_is_still_the_only_one():
    pack = json.loads(fixtures.PACK.read_text(encoding="utf-8"))
    case = next(c for c in pack["cases"] if c["id"] == "da_a2_resting_v1")
    nudged = json.loads(json.dumps(case["expected"]))
    nudged["outcomes"][0]["score"]["calibrated_log_odds"] = math.nextafter(
        case["expected"]["outcomes"][0]["score"]["calibrated_log_odds"], math.inf
    )
    assert fixtures._approved_replay_equal(case, nudged)
    # ... and the exception does not transfer to a renamed case.
    renamed = dict(case, id="da_a1_basic_clinical_v1")
    assert not fixtures._approved_replay_equal(renamed, nudged)


def test_report_comparator_tolerances_untouched():
    from ai import report_comparison

    assert report_comparison.ABS_TOL == 1e-12
    assert report_comparison.REL_TOL == 1e-9


def test_default_calibration_solver_is_unchanged():
    from ai import calibration

    assert calibration.DEFAULT_CALIBRATION_SOLVER == "scipy_lbfgsb"
    assert calibration.DETERMINISTIC_CALIBRATION_SOLVER in calibration.CALIBRATION_SOLVERS
    assert calibration.DETERMINISTIC_CALIBRATION_SOLVER != calibration.DEFAULT_CALIBRATION_SOLVER


# --------------------------------------------------------------------------- #
# 4. Frozen artifacts untouched                                             #
# --------------------------------------------------------------------------- #


def test_frozen_pack_identity_preserved():
    from ai.research_facade import canonical_response_digest

    pack = json.loads(fixtures.PACK.read_text(encoding="utf-8"))
    assert canonical_response_digest(pack) == fixtures.PACK_SHA256
    assert len(pack["cases"]) == 29
    assert fixtures.PACK_SHA256 == (
        "0307b396cea1e620c4004647e1d82ff7f292bb5b74de7cad1661e1299c6e7049"
    )


def test_classifier_is_importable_without_heavy_dependencies():
    """It must stay a thin diagnostic: no sklearn/scipy import at module scope."""
    source = inspect.getsource(importlib.import_module("research.intake.rh04_environment_class"))
    header = source.split('"""', 2)[-1]
    for forbidden in ("import sklearn", "import scipy", "from scipy", "from sklearn"):
        assert forbidden not in header, forbidden
    assert "import sys" in header or "import sys" not in header  # sys is allowed
