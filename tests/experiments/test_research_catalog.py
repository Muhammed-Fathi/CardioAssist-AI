"""AI-11.2 catalog is a read-only synthetic registry projection, never a loader."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

import ai.research_catalog as catalog_module
from ai.panels import REGISTERED_PANELS
from ai.research_registry import RESEARCH_MODEL_REGISTRY, registry_contract

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "export_research_model_catalog.py"


def _digest_without_checksum(document: dict) -> str:
    data = {k: v for k, v in document.items() if k != "catalog_sha256"}
    return hashlib.sha256(
        json.dumps(
            data, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def test_catalog_is_a_stable_complete_registry_projection() -> None:
    document = catalog_module.build_research_model_catalog()
    registry = registry_contract()
    keys = sorted(RESEARCH_MODEL_REGISTRY)
    assert document["schema_version"] == "cardioassist.ai.research_model_catalog/v1"
    assert document["source_registry_digest_sha256"] == registry["registry_digest_sha256"]
    assert document["entry_count"] == len(keys) == 5
    assert [e["model_key"] for e in document["entries"]] == keys
    assert document["catalog_sha256"] == _digest_without_checksum(document)
    assert catalog_module.catalog_json_bytes() == catalog_module.catalog_json_bytes()
    assert document["governance"]["approved_for_serving"] is False

    for exported in document["entries"]:
        key = exported["model_key"]
        source = RESEARCH_MODEL_REGISTRY[key]
        panel = REGISTERED_PANELS[source.panel_id]
        assert exported["registry_entry_sha256"] == source.entry_sha256
        assert exported["panel_contract_sha256"] == panel.contract_sha256
        assert exported["ordered_feature_names"] == list(panel.feature_names)
        assert exported["features"] == [f.to_contract_dict() for f in panel.fields]
        assert exported["entry_state"] == source.entry_state
        assert exported["offline_synthetic_registration_active"] == source.executable
        assert exported["non_executable_reason"] == source.non_executable_reason
        assert exported["registry_declared_capabilities"] == source.to_contract_dict()["capabilities"]
        assert exported["verified_artifact_capabilities"] is None
        assert exported["governance"]["real_data_execution_authorized"] is False
        assert exported["governance"]["clinical_use_authorized"] is False
        assert exported["governance"]["approved_for_serving"] is False
        assert exported["local_paths_disclosed"] is False


def test_only_registered_synthetic_contracts_and_one_card_reference() -> None:
    entries = catalog_module.build_research_model_catalog()["entries"]
    active = [e for e in entries if e["offline_synthetic_registration_active"]]
    blocked = [e for e in entries if not e["offline_synthetic_registration_active"]]
    assert len(active) == 2
    assert len(blocked) == 3
    assert all(e["non_executable_reason"] for e in blocked)
    cards = [e for e in entries if e["published_synthetic_model_card_reference"]]
    assert len(cards) == 1
    assert cards[0]["model_key"] == catalog_module.CARD_MODEL_KEY
    assert "linux-uci45-envelope" in cards[0]["published_synthetic_model_card_reference"]
    assert all(e["published_synthetic_model_card_reference"] is None for e in entries if e not in cards)


def test_forged_registry_approval_is_never_exported(monkeypatch) -> None:
    forged = copy.deepcopy(registry_contract())
    key = sorted(forged["entries"])[0]
    forged["entries"][key]["governance"]["approved_for_serving"] = True
    monkeypatch.setattr(catalog_module, "registry_contract", lambda: forged)
    with pytest.raises(ValueError, match="mismatch"):
        catalog_module.build_research_model_catalog()


def test_catalog_generation_does_not_load_artifacts(monkeypatch) -> None:
    # Trap the loader boundaries if a future refactor tries to use them.
    import ai.packaging as packaging
    import joblib

    def prohibited(*args, **kwargs):
        raise AssertionError("Catalog must not load an artifact.")

    monkeypatch.setattr(joblib, "load", prohibited)
    if hasattr(packaging, "load_verified_research_bundle"):
        monkeypatch.setattr(packaging, "load_verified_research_bundle", prohibited)
    payload = catalog_module.catalog_json_bytes()
    assert b"READ_ONLY_OFFLINE_SYNTHETIC_RESEARCH_DESCRIPTION" in payload
    assert b"signing_key" not in payload
    assert b"trusted_local_root" not in payload
    assert b"patient_records" not in payload
    assert b"file://" not in payload
    assert b"\\\\Users\\\\" not in payload


def test_stdout_and_exclusive_external_file_export(tmp_path: Path) -> None:
    expected = catalog_module.catalog_json_bytes()
    command = [sys.executable, "-W", "error", str(SCRIPT)]
    stdout = subprocess.run(command, cwd=ROOT, capture_output=True, check=False)
    assert stdout.returncode == 0, stdout.stderr.decode(errors="replace")
    assert stdout.stdout == expected
    assert stdout.stderr == b""

    a, b = tmp_path / "catalog-a.json", tmp_path / "catalog-b.json"
    for target in (a, b):
        export = subprocess.run(
            [*command, "--format", "json", "--output", str(target)],
            cwd=ROOT, capture_output=True, check=False,
        )
        assert export.returncode == 0, export.stderr.decode(errors="replace")
        assert export.stdout == b""
        assert target.read_bytes() == expected

    duplicate = subprocess.run(
        [*command, "--output", str(a)], cwd=ROOT, capture_output=True, check=False,
    )
    assert duplicate.returncode == 1
    assert a.read_bytes() == expected


def test_export_rejects_unknown_flags_and_repo_output() -> None:
    command = [sys.executable, "-W", "error", str(SCRIPT)]
    bad = subprocess.run([*command, "--model", "real-cad"], cwd=ROOT, capture_output=True)
    assert bad.returncode == 2
    assert bad.stdout == b""
    assert b"catalog_invalid_arguments" in bad.stderr

    attempted = ROOT / "_ai112_should_never_exist.json"
    assert not attempted.exists()
    blocked = subprocess.run(
        [*command, "--output", str(attempted)], cwd=ROOT, capture_output=True,
    )
    assert blocked.returncode == 2
    assert not attempted.exists()
