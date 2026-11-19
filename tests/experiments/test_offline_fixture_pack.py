"""RH-04 offline consumer fixtures; no endpoint or external data source."""

import json
from dataclasses import replace

from ai.research_demo import _copy_bundle_private

import pytest

from ai import research_facade as facade
from ai.filesystem_security import ensure_private_directory
from research.intake import offline_fixture_pack as fixtures


def pack():
    return json.loads(fixtures.PACK.read_text())


def test_golden_replay():
    assert fixtures.validate(pack()) == 29
    assert {c["expected"]["status"] for c in pack()["cases"]} == {
        s.value for s in facade.ResearchFacadeStatus
    }


@pytest.mark.parametrize("part", ["binding", "generator output", "case", "oracle"])
def test_fail_closed_before_bundle_build(part, monkeypatch):
    doc = pack()
    if part == "binding":
        doc["bindings"]["crosswalk_sha256"] = "0" * 64
    elif part == "generator output":
        doc["requests"][fixtures.REST]["records"][0]["features"]["age"] += 1
    elif part == "case":
        doc["cases"].pop()
    else:
        doc["cases"][0]["expected"]["status"] = "UNAVAILABLE"
    monkeypatch.setattr(fixtures, "sources", lambda *_: pytest.fail("unexpected build"))
    with pytest.raises(ValueError):
        fixtures.validate(doc)


@pytest.mark.parametrize("route", sorted(fixtures.RESEARCH_ROUTE_CATALOG))
def test_distinct_negative_requests_per_route(route):
    doc = pack()
    negatives = {
        json.dumps(
            fixtures.materialize(doc["requests"][route], case["edits"]), sort_keys=True
        )
        for case in doc["cases"]
        if case["route"] == route
        and case["expected"]["status"] in {"UNAVAILABLE", "ABSTAIN", "ERROR"}
    }
    assert len(negatives) == {fixtures.REST: 13, fixtures.BASIC: 5}.get(route, 3)


def assert_refusal(response, source):
    assert response.status is not facade.ResearchFacadeStatus.SYNTHETIC_RESULT
    for outcome in response.outcomes:
        assert outcome.status is not facade.ResearchFacadeStatus.SYNTHETIC_RESULT
        assert all(
            v is None
            for v in (outcome.score, outcome.shap, outcome.lime, outcome.uncertainty)
        )
    text = json.dumps(response.to_dict())
    for token in (
        '"features":',
        '"units":',
        '"raw_model_score":',
        '"calibrated_research_score":',
        str(source.trusted_local_root),
        source.signing_key.hex(),
        "probe-sensitive-ref",
    ):
        assert token not in text


BLOCKED_REASONS = {
    "da_a2_resting_labs_v1": "model_entry_blocked_pending_authorization",
    "da_a1_clinical_core_labs_v1": "model_entry_blocked_source_timing_unverified",
    "da_a2_hungary_locked_transportability_v1": "model_entry_locked_external_target",
}


@pytest.mark.parametrize(
    "case",
    [c for c in pack()["cases"] if c["route"] not in fixtures.ACTIVE],
    ids=lambda c: c["id"],
)
def test_blocked_before_artifact_access(tmp_path, monkeypatch, case):
    monkeypatch.setattr(
        facade,
        "_load_artifact",
        lambda *a, **kw: pytest.fail("blocked artifact access"),
    )
    source = facade.LocalSyntheticBundleSource(
        tmp_path / "absent", tmp_path, b"not-a-signing-key"
    )
    route = case["route"]
    status, reason = {
        route: ("UNAVAILABLE", BLOCKED_REASONS[route]),
        route + "-wrong-dataset": ("ERROR", "dataset_id_mismatch"),
        route + "-stale-hash": ("ERROR", "panel_contract_hash_mismatch"),
    }[case["id"]]
    request = fixtures.materialize(pack()["requests"][route], case["edits"])
    request["records"][0]["synthetic_provenance"]["fixture_ref"] = "probe-sensitive-ref"
    response = facade.run_offline_research_inference_from_document(
        request, model_source=source
    )
    assert (response.status.value, response.error.code, response.error.stage) == (
        status,
        reason,
        "registry",
    )
    assert not response.outcomes and response.artifact is None
    assert_refusal(response, source)


@pytest.mark.parametrize(
    "edit",
    [
        [["x"], None],
        {"op": "set", "path": ["x"]},
        {"op": "delete", "path": ["x"], "value": None},
        {"op": "unset", "path": ["x"]},
    ],
)
def test_ambiguous_edits_rejected(edit):
    with pytest.raises(ValueError):
        fixtures.materialize({"x": 1}, [edit])


@pytest.mark.parametrize(
    "case_id,field,present,reason,code",
    [
        ("optional", "trestbps", False, "not_provided", None),
        ("optional-null", "trestbps", True, "not_measured", None),
        (
            "optional-null-structural-reason",
            "trestbps",
            True,
            "not_provided",
            "invalid_missing_reason",
        ),
        ("optional-null-no-reason", "trestbps", True, None, "missing_reason_mismatch"),
        ("required-null", "age", True, None, "missing_required_field"),
    ],
)
def test_missingness_through_facade(
    disposable_sources, case_id, field, present, reason, code
):
    doc = pack()
    case = next(c for c in doc["cases"] if c["id"] == case_id)
    request = fixtures.materialize(doc["requests"][fixtures.REST], case["edits"])
    record = request["records"][0]
    assert (field in record["features"]) is present
    assert record["features"].get(field) is None
    assert record["missing_reasons"] == ({field: reason} if reason else {})
    record["synthetic_provenance"]["fixture_ref"] = "probe-sensitive-ref"
    source = disposable_sources[fixtures.REST]
    response = facade.run_offline_research_inference_from_document(
        request, model_source=source
    )
    assert_refusal(response, source)
    (outcome,) = response.outcomes
    if code:
        assert response.status.value == "ERROR" and outcome.error.code == code
    else:
        assert response.status.value == "ABSTAIN"
        assert (
            outcome.abstention_reason
            == "registry_abstain_policy_optional_field_missing"
        )
        assert dict(outcome.missing_fields_with_reason) == {field: reason}


@pytest.fixture(scope="module")
def disposable_sources(tmp_path_factory):
    return fixtures.sources(
        ensure_private_directory(tmp_path_factory.mktemp("pack_tamper"))
    )


@pytest.mark.parametrize("route", sorted(fixtures.ACTIVE))
def test_tampering_redacted_and_no_fallback(route, disposable_sources, tmp_path):
    source = disposable_sources[route]
    root = ensure_private_directory(tmp_path / "trusted")
    source = replace(
        source,
        bundle_dir=_copy_bundle_private(source.bundle_dir, root / "copy"),
        trusted_local_root=root,
    )
    model = source.bundle_dir / "model.joblib"
    with model.open("ab") as f:
        f.write(b"fixture-integrity-canary")
    response = facade.run_offline_research_inference_from_document(
        pack()["requests"][route], model_source=source
    )
    assert response.status is facade.ResearchFacadeStatus.ERROR
    assert response.outcomes == () and response.artifact is None
    text = json.dumps(response.to_dict())
    for forbidden in (
        str(source.bundle_dir.parent),
        source.signing_key.hex(),
        "fixture-integrity-canary",
        "raw_model_score",
        "shap_explanation",
        "lime_explanation",
    ):
        assert forbidden not in text
