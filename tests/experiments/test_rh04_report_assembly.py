"""RH-04.7/.8: tested glue, not a second model/ledger implementation."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from ai.research_facade import canonical_response_digest
from research import report_assembly as rh



# These sources carry deliberately raw-byte SHA-256 bindings. On Windows,
# core.autocrlf may otherwise rewrite LF to CRLF in a new checkout even while
# GitHub/Linux CI stays green. Match the committed bytes, not parsed JSON/YAML.
BYTE_BOUND_SOURCES = (
    "research/intake/fixtures/offline_io.v1.json",
    "research/intake/fixtures/offline_demo_cards.v1.json",
    "shared/contracts/openapi.yaml",
    "shared/contracts/fixtures/index.json",
    "shared/contracts/registry/mock_model_registry.v1.json",
    "shared/contracts/fixtures/F-01-cad-tabular-valid-mock-clinical-v1.json",
    "research/schemas/rh04_synthetic_report.v1.schema.json",
)


@pytest.mark.parametrize("relative_path", BYTE_BOUND_SOURCES)
def test_native_checkout_preserves_reviewed_source_bytes(relative_path: str):
    attr = subprocess.run(
        ["git", "check-attr", "eol", "--", relative_path],
        cwd=rh.ROOT, capture_output=True, text=True, check=True,
    )
    assert attr.stdout.strip().endswith(": eol: lf"), (
        f"Missing LF checkout policy for {relative_path}: {attr.stdout!r}"
    )
    expected = subprocess.run(
        ["git", "show", f"HEAD:{relative_path}"],
        cwd=rh.ROOT, capture_output=True, check=True,
    ).stdout
    actual = (rh.ROOT / relative_path).read_bytes()
    assert actual == expected, (
        f"Checkout bytes differ from reviewed Git blob for {relative_path}; "
        "recreate a fresh worktree with the current .gitattributes."
    )


@pytest.fixture(scope="module")
def produced(tmp_path_factory: pytest.TempPathFactory) -> tuple[dict, Path]:
    # One genuine 29-case replay, AI-12.1 demo and AI-10.1 evaluation.
    # Ledger is freshly created OUTSIDE the Git checkout by the native engine.
    root = tmp_path_factory.mktemp("rh04-report-private")
    path = root / "ledger" / "one-shot.json"
    doc = rh.assemble(ledger_path=path)
    return doc, path


def _reseal(doc: dict) -> dict:
    doc["report_sha256"] = canonical_response_digest({
        k: v for k, v in doc.items() if k != "report_sha256"
    })
    return doc


def test_real_synthetic_run_manifest_covers_all_routes_statuses_and_ledger(produced):
    doc, ledger_path = produced
    rh.validate(doc)
    assert ledger_path.is_file()
    assert doc["facade"]["cases_validated_by_actual_replay"] == 29
    assert len(doc["facade"]["cases"]) == 29
    assert len(doc["facade"]["routes"]) == 5
    assert len(doc["facade"]["blocked_routes"]) == 3
    assert set(c["status"] for c in doc["facade"]["cases"]) == set(rh.STATUS_ORDER)
    assert all(c["expected_projection_sha256"] and c["structural_sha256"]
               for c in doc["facade"]["cases"])
    assert doc["ai12_evidence"]["stages_passed"] == 8
    assert doc["ai10_ledger"]["ledger_entries"] == 1
    assert doc["ai10_ledger"]["protected_ledger_status"] == "COMPLETED"
    assert doc["ai10_ledger"]["replay_refusal"] == "one_shot_external_evaluation_already_consumed"
    assert doc["ai10_ledger"]["plan_refusal"] == "ai10_plan_digest_mismatch"
    assert doc["ai10_ledger"]["overlap_refusal"] == "ai10_overlapping_fixture_id"
    assert doc["ai10_ledger"]["insufficient_status"] == "INSUFFICIENT_EVIDENCE"
    assert doc["ai10_ledger"]["real_external_validation_performed"] is False
    assert doc["real_studies"] == {"AI-9.2": rh.NO_GO, "AI-10.2": rh.NO_GO}


@pytest.mark.parametrize("field,bad", [
    ("status", "REAL_EXTERNAL_VALIDATION_COMPLETED"),
    ("evidence_grade", "CLINICAL"),
    ("mock_backend", "REAL_MODEL"),
    ("source_commit", "0" * 40),
])
def test_relabeling_or_stale_source_fails_even_with_recomputed_checksum(produced, field, bad):
    doc = _reseal(copy.deepcopy(produced[0]))
    doc[field] = bad
    _reseal(doc)
    with pytest.raises(ValueError):
        rh.validate(doc)


def test_tampered_checksum_case_digest_and_unknown_fields_fail(produced):
    doc = copy.deepcopy(produced[0])
    doc["ai10_ledger"]["ledger_entries"] = 22
    with pytest.raises(ValueError, match="integrity"):
        rh.validate(doc)
    doc = copy.deepcopy(produced[0])
    doc["facade"]["cases"][0]["structural_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="integrity"):
        rh.validate(doc)
    _reseal(doc)
    with pytest.raises(ValueError, match="binding"):
        rh.validate(doc)
    doc = _reseal(copy.deepcopy(produced[0]))
    doc["feature_value"] = 1234
    _reseal(doc)
    with pytest.raises(ValueError, match="structure"):
        rh.validate(doc)


def test_refusal_must_never_display_a_score(produced):
    doc = copy.deepcopy(produced[0])
    blocked = next(c for c in doc["facade"]["cases"] if c["status"] == "UNAVAILABLE")
    blocked["score_allowed"] = True
    _reseal(doc)
    with pytest.raises(ValueError):
        rh.validate(doc)


def test_private_key_path_echo_or_false_real_study_fails(produced):
    doc = copy.deepcopy(produced[0])
    doc["limitations"][0] = "private_key=C:/private/secret"
    _reseal(doc)
    with pytest.raises(ValueError, match="Unsafe|Disallowed"):
        rh.validate(doc)
    doc = copy.deepcopy(produced[0])
    doc["real_studies"]["AI-10.2"] = "COMPLETED"
    _reseal(doc)
    with pytest.raises(ValueError):
        rh.validate(doc)


def test_report_is_aggregate_redacted_and_same_environment_digest(produced):
    doc, ledger_path = produced
    body = rh.report_bytes(doc)
    assert body == rh.report_bytes(doc)
    assert hashlib.sha256(body).hexdigest() == hashlib.sha256(rh.report_bytes(doc)).hexdigest()
    assert doc["report_sha256"] == canonical_response_digest({
        k: v for k, v in doc.items() if k != "report_sha256"
    })
    for secret in (
        str(ledger_path), "patient_ref", "record_ref", "signing_key",
        "reservation_id", "external_cohort_id", "raw_model_score", "medical_advice",
    ):
        assert secret not in body.decode("ascii")
    assert doc["source_bindings"]["fixture_canonical_sha256"] == rh.fixtures.PACK_SHA256


def test_validator_cli_and_path_refusals(produced, tmp_path: Path):
    doc, _ = produced
    saved = tmp_path / "report.json"
    saved.write_bytes(rh.report_bytes(doc))
    cmd = [sys.executable, "-m", "research.report_assembly", "--validate", str(saved)]
    result = subprocess.run(cmd, cwd=rh.ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "VALID_SYNTHETIC_REPORT" in result.stdout

    # Parser refuses checkout writes before running any synthetic training.
    inside = rh.ROOT / "rh04-unsafe-ledger.json"
    cmd = [
        sys.executable, "-m", "research.report_assembly",
        "--ledger", str(inside), "--output", str(tmp_path / "unused.json"),
    ]
    rejected = subprocess.run(cmd, cwd=rh.ROOT, capture_output=True, text=True)
    assert rejected.returncode == 2
    assert '"code":"rh04_report_refused"' in rejected.stderr
    assert not inside.exists()
    assert not (tmp_path / "unused.json").exists()
    assert rh.main(["--validate", str(saved), "--with-lime"]) == 2

    bad = tmp_path / "duplicate.json"
    bad.write_text('{"schema_version":"first","schema_version":"second"}')
    assert rh.main(["--validate", str(bad)]) == 2


def test_missing_external_new_file_guard(tmp_path: Path):
    existing = tmp_path / "existing.json"
    existing.write_text("{}")
    with pytest.raises(ValueError):
        rh._fresh_external_path(existing, "ledger")
    with pytest.raises(ValueError):
        rh._fresh_external_path(rh.ROOT / "report.json", "output")
