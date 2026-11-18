"""AI-12.1 uses the real, fixed synthetic run. No backend/JSON Schema deps here."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import pytest

from ai import research_demo as demo, research_evidence as evidence
from ai.report_comparison import (
    ComparisonError,
    MAX_BYTES,
    compare_report,
    read_report,
    report_bytes,
)


def sha(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    private = tmp_path_factory.mktemp("ephemeral")
    with pytest.MonkeyPatch.context() as m:
        m.setattr(tempfile, "tempdir", str(private))
        result = evidence.build_evidence_pack()
    assert list(private.iterdir()) == []  # neither bundle, tamper copy nor keys retained
    return result


def test_complete_pack_binds_actual_stage8_preimage_and_fixture(pack):
    assert pack["schema_version"] == "cardioassist.ai.synthetic_evidence_pack/v1"
    assert pack["pack_sha256"] == sha({k: v for k, v in pack.items() if k != "pack_sha256"})
    card, report, inf = pack["model_card"], pack["report"], pack["inference"]
    stages = report["stage_results"]
    assert len(stages) == 8 and report["summary"]["stages_succeeded"] == 8
    assert report["deterministic_sha256"] == sha(
        {k: report[k] for k in ("evidence_level", "stage_results", "registry_digest_sha256")}
    )
    assert stages[7]["detail"]["canonical_payload_sha256"] == sha(inf)
    records, labels = demo._cohort()
    assert card["source"]["records_and_labels_sha256"] == sha(
        {"records": records, "labels": labels}
    )
    assert card["protocol"]["training_config_sha256"] == sha(card["protocol"]["training_config"])
    assert (
        card["model"]["model_joblib_sha256"]
        == inf["artifact"]["verified_artifact_hashes"]["model.joblib"]
    )
    assert (
        card["protocol"]["bundle_protocol_md_sha256"]
        == inf["artifact"]["verified_artifact_hashes"]["protocol.md"]
    )
    assert card["route"]["sha256"] == demo.get_route_descriptor(inf["route_id"]).descriptor_sha256
    assert card["panel"]["contract_sha256"] == inf["panel_contract_sha256"]
    assert (
        card["model"]["family"]
        == inf["model_family"]
        == stages[2]["detail"]["selected_model_family"]
    )
    assert card["capabilities"] == {"calibration": True, "shap": True, "lime": True}
    assert inf["artifact"]["verification"]["producer_authenticated"]
    for r in inf["records"]:
        assert r["score"]["score_kind"] == "CALIBRATED_RESEARCH_SCORE_SYNTHETIC"
        assert r["score"]["clinical_probability_claim"] is False
        assert r["shap_explanation"]["sum_check_passed"]
        assert (
            r["lime_explanation"]["explained_quantity"]
            == r["shap_explanation"]["explained_quantity"]
        )
        assert (
            r["lime_explanation"]["quality_status"]
            == r["lime_explanation"]["explanation"]["quality"]["status"]
        )
    assert card["governance"]["gate_pt_p3"] == "CLOSED"
    assert not any(
        card["governance"][k]
        for k in (
            "clinical_use_authorized",
            "approved_for_serving",
            "real_data_execution_authorized",
        )
    )


def test_failure_evidence_is_from_actual_requests_not_predicted_defaults(pack):
    stages = pack["report"]["stage_results"]
    abstain = stages[4]["detail"]
    assert abstain["status"] == "ABSTAIN" and not abstain["score_produced"]
    assert abstain["missing_field_and_reason"] == [["trestbps", "not_provided"]]
    unavailable = stages[5]["detail"]["cases"]
    assert len(unavailable) == 3 and all(
        c["status"] == "UNAVAILABLE" and not c["score_produced"] for c in unavailable
    )
    errors = {c["case"]: c for c in stages[6]["detail"]["cases"]}
    for case in (
        "wrong_unit",
        "wrong_value_type",
        "missing_required_field",
        "wearable_derived_field",
        "forged_synthetic_flag_without_provenance",
        "real_bundle_inference_operation",
        "tampered_artifact_digest",
        "foreign_producer_key",
    ):
        assert (
            errors[case]["status"] == "ERROR"
            and errors[case]["code"]
            and not errors[case]["score_produced"]
        )
    assert pack["model_card"]["tested_refusals"]["error_cases"] == len(errors)


def test_pack_is_repeatable_and_contains_no_inputs_keys_or_paths(pack):
    assert report_bytes(evidence.build_evidence_pack()) == report_bytes(pack)
    body = json.dumps(pack)
    for forbidden in (
        '"features":',
        '"units":',
        '"background_matrix":',
        '"hmac_sha256":',
        '"key_id":',
        '"filepath":',
        "synthetic-fake-secret",
        "privatesecret123",
        str(Path.home()),
        str(Path.cwd()),
        "cardioassist_ai111_demo_",
        "BEGIN PRIVATE KEY",
    ):
        assert forbidden not in body
    assert "not_requested_by_caller" not in pack["model_card"]["example_explanations"].values()


def test_not_requested_lime_is_not_claimed_as_computed():
    pack = evidence.build_evidence_pack(with_lime=False)
    assert pack["model_card"]["capabilities"]["lime"]  # supported, not produced
    assert pack["model_card"]["example_explanations"]["lime_quality"] is None
    assert (
        pack["model_card"]["example_explanations"]["lime_absence_reason"]
        == "not_requested_by_caller"
    )
    assert all(r["lime_explanation"]["explanation"] is None for r in pack["inference"]["records"])
    assert pack["reproducibility"]["command"].endswith("--no-lime")


def test_invalid_fabricated_input_cannot_publish_partial_evidence(tmp_path, monkeypatch, capsys):
    # Deliberately corrupt only the synthetic success request (not any trust gate).
    make = demo._record_from_envelope

    def bad(envelope, index):
        return make(
            envelope, index, features={**envelope["features"], "age": "private-test-marker"}
        )

    monkeypatch.setattr(demo, "_record_from_envelope", bad)
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    assert evidence.main(["--output", str(tmp_path / "report.json")]) == 2
    assert not list(tmp_path.iterdir())
    streams = capsys.readouterr()
    assert streams.out == "" and json.loads(streams.err)["status"] == "FAIL_CLOSED"
    assert "private-test-marker" not in streams.err and str(tmp_path) not in streams.err


def test_package_exports_and_module_execution_without_warning():
    probe = """
import ai, sys
assert 'ai.research_demo' not in sys.modules
assert 'ResearchDemoError' in dir(ai)
from ai import RESEARCH_FACADE_DEMO_ID, ResearchDemoError, render_research_facade_demo_text, run_research_facade_demo
from ai import research_demo as d
assert RESEARCH_FACADE_DEMO_ID == d.DEMO_ID and ResearchDemoError is d.ResearchDemoError
assert render_research_facade_demo_text is d.render_demo_text and run_research_facade_demo is d.run_research_facade_demo
"""
    subprocess.run([sys.executable, "-W", "error", "-c", probe], check=True)
    run = subprocess.run(
        [sys.executable, "-W", "error", "-m", "ai.research_demo", "--format", "json"],
        capture_output=True,
        check=True,
    )
    assert run.stderr == b"" and json.loads(run.stdout)["summary"]["stages_succeeded"] == 8


def seal(p):
    """Recompute the documented checksum domains for deliberate comparison probes."""
    r = p["report"]
    r["stage_results"][7]["detail"]["canonical_payload_sha256"] = sha(p["inference"])
    r["deterministic_sha256"] = demo.report_digest(r)
    p["pack_sha256"] = sha({k: v for k, v in p.items() if k != "pack_sha256"})
    return report_bytes(p)


def test_exact_vs_format_only_vs_small_but_observable_numeric_difference(pack):
    # Do not infer scientific source reproducibility from a dirty developer tree.
    expected = (
        "MATCH" if pack["reproducibility"]["source"]["source_trees_clean"] else "INDETERMINATE"
    )
    same = compare_report(report_bytes(pack), report_bytes(pack))
    assert (
        same["differences"] == []
        and same["exact_file_bytes_equal"]
        and same["fixture_behavior"] == expected
    )
    recoded = compare_report(
        report_bytes(pack), json.dumps(pack).encode("utf-16")
    )  # e.g. PowerShell 5.1 redirection
    assert not recoded["exact_file_bytes_equal"] and recoded["canonical_json_equal"]
    p = copy.deepcopy(pack)
    metric = p["inference"]["records"][0]["lime_explanation"]["explanation"]["fidelity"]
    metric["local_fidelity_abs_error"] += 1e-13
    d = compare_report(report_bytes(pack), seal(p))
    assert not d["canonical_json_equal"] and d["fixture_behavior"] == expected
    (measurement,) = (v for v in d["differences"] if v["kind"] != "derived_digest")
    assert (
        measurement["path"]
        == "/inference/records/0/lime_explanation/explanation/fidelity/local_fidelity_abs_error"
    )
    assert (
        measurement["peer"] == metric["local_fidelity_abs_error"]
        and measurement["absolute_delta"] > 0
    )
    assert measurement["kind"] == "within_tolerance"
    assert len(d["differences"]) == 4  # also stage 8, legacy report and pack checksums
    metric["local_fidelity_abs_error"] += 0.001
    d = compare_report(report_bytes(pack), seal(p))
    assert d["fixture_behavior"] == "DIFFERENT" and any(
        v["kind"] == "outside_tolerance" for v in d["differences"]
    )


@pytest.mark.parametrize(
    "location,value",
    [
        (("inference", "governance", "clinical_use_authorized"), 0),  # False != 0
        (("inference", "artifact", "verification", "producer_authenticated"), False),
        (("inference", "records", 0, "score", "exploratory_threshold"), 0.5 + 1e-14),
        (("report", "stage_results", 6, "detail", "cases", 0, "code"), "private-test-marker"),
        (("inference", "records", 0, "lime_explanation", "quality_status"), "UNSTABLE"),
        (("model_card", "route", "sha256"), "a" * 64),
        (("model_card", "source", "seed"), 132),
    ],
)
def test_decisions_types_thresholds_and_contracts_are_exact(pack, location, value):
    p = copy.deepcopy(pack)
    container = p
    for k in location[:-1]:
        container = container[k]
    container[location[-1]] = value
    d = compare_report(report_bytes(pack), seal(p))
    assert d["fixture_behavior"] == "DIFFERENT"
    assert any(i["path"] == "/" + "/".join(map(str, location)) for i in d["differences"])
    assert "private-test-marker" not in json.dumps(d)


def test_artifact_byte_change_is_not_claimed_as_model_equivalence(pack):
    p = copy.deepcopy(pack)
    p["inference"]["artifact"]["verified_artifact_hashes"]["model.joblib"] = p["model_card"][
        "model"
    ]["model_joblib_sha256"] = "b" * 64
    d = compare_report(report_bytes(pack), seal(p))
    assert not d["artifact_member_hashes_equal"] and not d["exact_file_bytes_equal"]
    assert {v["kind"] for v in d["differences"]} == {"artifact_bytes", "derived_digest"}
    # An old report has no preimage. Never wave through its opaque mismatch.
    d = compare_report(report_bytes(pack), report_bytes(p["report"]))
    assert d["fixture_behavior"] == "INDETERMINATE" and d["artifact_member_hashes_equal"] is None
    assert {i["path"] for i in d["differences"]} == {
        "/deterministic_sha256",
        "/stage_results/7/detail/canonical_payload_sha256",
    }


def test_bad_comparison_input_node_ids_are_bounded():
    # Collect without running setup: pytest exports the full node ID in
    # PYTEST_CURRENT_TEST, which must fit in a Windows environment variable.
    module = "tests/experiments/test_research_evidence.py"
    target = f"{module}::test_rejects_bad_comparison_input_without_echo"
    result = subprocess.run(
        [sys.executable, "-Werror", "-m", "pytest", "--collect-only", "-q", "--color=no", target],
        cwd=Path(__file__).resolve().parents[2],
        env={**os.environ, "PYTEST_ADDOPTS": ""},  # independent of outer selection/verbosity
        capture_output=True,
        text=True,
        check=True,
    )
    # Report only lengths if this regresses, never print a payload-sized ID.
    lengths = [len(line) for line in result.stdout.splitlines() if line.startswith(target + "[")]
    assert len(lengths) == 10
    assert max(lengths) < 200


@pytest.mark.parametrize(
    "bad",
    [
        pytest.param(b"{", id="truncated-json"),
        pytest.param(b"[]", id="array-not-object"),
        pytest.param(b"{}", id="empty-object"),
        pytest.param(b'{"secret-path":1,"secret-path":2}', id="duplicate-key"),
        pytest.param(b'{"x":NaN}', id="nan"),
        pytest.param(b'{"x":1e9999}', id="infinite-exponent"),
        pytest.param(b'{"x":1e-9999}', id="underflow-exponent"),
        pytest.param(b'{"x":1.123456789123456789123}', id="overprecise-float"),
        pytest.param(b" " * (MAX_BYTES + 1), id="oversized-whitespace"),
        pytest.param(b"[" * 2000 + b"]" * 2000, id="deep-nesting"),
    ],
)
def test_rejects_bad_comparison_input_without_echo(pack, bad):
    with pytest.raises(ComparisonError) as err:
        compare_report(report_bytes(pack), bad)
    assert "secret-path" not in str(err.value)


def test_unknown_keys_withheld_and_nested_checksums_verified(pack):
    p = copy.deepcopy(pack)
    p["inference"]["a/private-path"] = "private-test-marker"
    d = compare_report(report_bytes(pack), seal(p))
    assert (
        d["fixture_behavior"] == "DIFFERENT"
        and {"path": "/inference", "kind": "unexpected_fields_withheld", "count": 1}
        in d["differences"]
    )
    assert all(s not in json.dumps(d) for s in ("private-path", "private-test-marker"))
    p["inference"]["a/private-path"] = "changed"
    with pytest.raises(ComparisonError, match="pack_digest_mismatch"):
        compare_report(report_bytes(pack), report_bytes(p))
    p["pack_sha256"] = sha({k: v for k, v in p.items() if k != "pack_sha256"})
    with pytest.raises(ComparisonError, match="response_digest_mismatch"):
        compare_report(report_bytes(pack), report_bytes(p))


def test_cli_writes_only_new_json_and_refuses_other_inputs(tmp_path, pack, monkeypatch, capsys):
    monkeypatch.setattr(evidence, "build_evidence_pack", lambda **kw: pack)
    path = tmp_path / "new.json"
    assert evidence.main(["--output", str(path)]) == 0 and read_report(path) == report_bytes(pack)
    assert (
        evidence.main(["--output", str(path)]) == 2
        and json.loads(capsys.readouterr().err)["code"] == "output_already_exists"
    )
    path.write_bytes(b"private-test-marker")
    assert evidence.main(["--compare", str(path)]) == 2
    with pytest.raises(SystemExit) as error:
        evidence.main(["--input", "private-test-marker"])
    assert error.value.code == 2 and "private-test-marker" not in capsys.readouterr().err


def test_comparison_does_not_train_or_load_artifacts(pack, monkeypatch, tmp_path, capsys):
    def forbidden(**kw):
        pytest.fail("An archived JSON comparison must not fit or load a model")

    monkeypatch.setattr(evidence, "build_evidence_pack", forbidden)
    reference = tmp_path / "reference.json"
    reference.write_bytes(report_bytes(pack))
    monkeypatch.setattr(evidence, "RELEASED_EXAMPLE", reference)
    peer = tmp_path / "legacy.json"
    peer.write_bytes(report_bytes(pack["report"]))
    assert evidence.main(["--compare", str(peer)]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["scope"] == "AI-11.1_report_only" and d["exact_file_bytes_equal"]
