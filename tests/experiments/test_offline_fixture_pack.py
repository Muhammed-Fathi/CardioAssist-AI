"""RH-04 offline consumer fixtures; no endpoint or external data source."""

import json

import pytest

from ai import research_facade as facade
from ai.filesystem_security import ensure_private_directory
from research.intake import offline_fixture_pack as fixtures


def pack():
    return json.loads(fixtures.PACK.read_text())


def test_golden_replay():
    assert fixtures.validate(pack()) == 19
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


@pytest.mark.parametrize(
    "route,reason",
    [
        ("da_a2_resting_labs_v1", "model_entry_blocked_pending_authorization"),
        ("da_a1_clinical_core_labs_v1", "model_entry_blocked_source_timing_unverified"),
        (
            "da_a2_hungary_locked_transportability_v1",
            "model_entry_locked_external_target",
        ),
    ],
)
def test_blocked_before_artifact_access(tmp_path, monkeypatch, route, reason):
    monkeypatch.setattr(
        facade,
        "_load_artifact",
        lambda *a, **kw: pytest.fail("blocked artifact access"),
    )
    source = facade.LocalSyntheticBundleSource(tmp_path / "absent", tmp_path)
    response = facade.run_offline_research_inference_from_document(
        pack()["requests"][route], model_source=source
    )
    assert response.status is facade.ResearchFacadeStatus.UNAVAILABLE
    assert response.error.code == reason
    assert not response.outcomes and response.artifact is None


@pytest.fixture(scope="module")
def disposable_sources(tmp_path_factory):
    return fixtures.sources(
        ensure_private_directory(tmp_path_factory.mktemp("pack_tamper"))
    )


@pytest.mark.parametrize("route", sorted(fixtures.ACTIVE))
def test_tampering_redacted_and_no_fallback(route, disposable_sources):
    source = disposable_sources[route]
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
