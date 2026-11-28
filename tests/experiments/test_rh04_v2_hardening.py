"""RH04-R23-01/02/03: fail-closed validation and evidence-publication security.

These tests exist because the Round 23 review found that the gate asked a
*different* question in each of its dispatch modes, and that its publication step
could not distinguish "I scanned and found nothing" from "I could not scan".

Every test here is a negative test first. A positive test that only proves the
happy path is satisfied by a validator that always returns True.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import pytest

from research.intake import rh04_v2_evidence_security as security
from research.intake.rh04_v2_lane_a_validation import (
    LaneAVerdict,
    check_lane_a_document,
    describe_lane_a_verdict,
    validate_lane_a_documents,
)


# --------------------------------------------------------------------------- #
# Fixtures: a minimal but structurally real Lane A document.                  #
# --------------------------------------------------------------------------- #


def _lane_a_document() -> dict:
    """A document that passes the shared predicate and records valid=True."""
    from research.intake import rh04_v2_lane_a_report as report

    ids = report.registered_case_ids()
    per_case = {case_id: "a" * 64 for case_id in ids}
    route = {
        "convergence_evidence_sha256": "a" * 64,
        "any_failure": False,
        "regeneration": {
            "regenerated_parameters": {
                "source_provenance": {"registered_producer": "da_a2_resting_v1"},
                "parameter_identity": {
                    "kind": "coefficient_vector",
                    "coefficients": [0.5] * 10,
                    "intercept": 0.1,
                    "regenerated_parameters_sha256": "b" * 64,
                },
                "archived_identity": {"archived_parameters_sha256": "c" * 64},
                "structural_integrity": {
                    "checked": True,
                    "n_coefficients": 10,
                    "n_coefficients_match_archive": True,
                },
                "archived_parameter_equality": {
                    "measured": True,
                    "exact": True,
                    "classification": "IDENTICAL",
                    "coefficient_max_abs_delta": 0.0,
                },
                "provenance_lineage_valid": {
                    "valid": True,
                    "checks": {"preprocessing_exact": {"passed": True}},
                },
            }
        },
    }
    return {
        "any_failure": False,
        "routes": {"da_a2_resting_v1": route},
        "validity": {"valid": True, "failures": [], "findings": []},
        "replay_response_identity": {
            "frozen_archive_replay": {
                "per_case_response_sha256": dict(per_case),
                "replay_responses_sha256": "d" * 64,
            },
            "fresh_model_replay": {
                "per_case_response_sha256": dict(per_case),
                "replay_responses_sha256": "e" * 64,
            },
            "fresh_and_frozen_are_equivalent": False,
        },
    }


def _break_structural_integrity(document: dict) -> dict:
    """The exact run-2 corruption Round 23 demonstrated passing the old Stage 2.

    Only `structural_integrity` changes. Every field the gate compares between
    the two regenerations is left untouched, which is why the old identity
    comparison could not see it.
    """
    params = document["routes"]["da_a2_resting_v1"]["regeneration"][
        "regenerated_parameters"
    ]
    params["structural_integrity"] = {
        "checked": False,
        "n_coefficients": 10,
        "n_coefficients_match_archive": False,
    }
    return document


# --------------------------------------------------------------------------- #
# RH04-R23-01: both regenerations are validated                              #
# --------------------------------------------------------------------------- #


def test_r23_01_clean_document_is_valid():
    verdict = check_lane_a_document(_lane_a_document(), label="run1")
    assert verdict.valid is True, verdict.failures


def test_r23_01_invalid_first_run_is_rejected():
    document = _lane_a_document()
    document["validity"] = {"valid": False, "failures": ["STRUCTURE_DRIFT"]}
    verdict = check_lane_a_document(document, label="run1")
    assert verdict.valid is False


def test_r23_01_invalid_second_run_is_rejected_with_valid_first():
    """The defect Round 23 found: run 2 was never consulted."""
    first = _lane_a_document()
    second = _lane_a_document()
    second["validity"] = {"valid": False, "failures": ["STRUCTURE_DRIFT"]}

    verdicts = validate_lane_a_documents([("run1", first), ("run2", second)])
    assert all(v.valid for v in verdicts) is False
    assert any("run2" in failure for v in verdicts for failure in v.failures)


def test_r23_01_second_run_structural_failure_with_identical_identities():
    """The precise mutation that passed before the fix.

    The two documents remain identity-identical, so a comparison-only gate sees
    nothing; only validating run 2's own content catches it.
    """
    first = _lane_a_document()
    second = _break_structural_integrity(copy.deepcopy(_lane_a_document()))

    verdicts = validate_lane_a_documents([("run1", first), ("run2", second)])
    assert verdicts[0].valid is True
    assert verdicts[1].valid is False
    assert any("structural_integrity" in f for f in verdicts[1].failures)


def test_r23_01_missing_validity_record_fails_closed():
    document = _lane_a_document()
    document.pop("validity")
    verdict = check_lane_a_document(document, label="run2")
    assert verdict.valid is False
    assert any("absent" in f for f in verdict.failures)


def test_r23_01_malformed_validity_record_fails_closed():
    for malformed in ("valid", ["valid"], 1, None):
        document = _lane_a_document()
        document["validity"] = malformed
        verdict = check_lane_a_document(document, label="run2")
        assert verdict.valid is False, f"accepted malformed validity {malformed!r}"


def test_r23_01_non_boolean_validity_values_fail_closed():
    """`1`, `"true"` and `"yes"` are refusals, not acceptances."""
    for value in (1, 0, "true", "yes", [True], {"ok": True}):
        document = _lane_a_document()
        document["validity"] = {"valid": value, "failures": []}
        verdict = check_lane_a_document(document, label="run2")
        assert verdict.valid is False, f"accepted non-boolean validity {value!r}"


def test_r23_01_fit_failure_despite_claimed_valid_verdict():
    document = _lane_a_document()
    document["any_failure"] = True
    document["validity"] = {"valid": True, "failures": []}
    verdict = check_lane_a_document(document, label="run2")
    assert verdict.valid is False
    assert any("any_failure" in f for f in verdict.failures)


def test_r23_01_any_failure_must_be_literally_false():
    for value in ("False", 0, None, [], "no"):
        document = _lane_a_document()
        document["any_failure"] = value
        verdict = check_lane_a_document(document, label="run2")
        assert verdict.valid is False, f"accepted any_failure={value!r}"


def test_r23_01_spoofed_verdict_cannot_override_broken_content():
    """Editing the verdict must not make invalid content valid."""
    document = _break_structural_integrity(_lane_a_document())
    document["validity"] = {"valid": True, "failures": []}
    verdict = check_lane_a_document(document, label="run2")
    assert verdict.valid is False, "a spoofed verdict was believed"
    assert any("structural_integrity" in f for f in verdict.failures)


def test_r23_01_every_document_is_checked_not_just_the_first():
    """One bad run must not mask a second bad run."""
    first = _lane_a_document()
    first["validity"] = {"valid": False, "failures": ["A"]}
    second = _lane_a_document()
    second["validity"] = {"valid": False, "failures": ["B"]}

    verdicts = validate_lane_a_documents([("run1", first), ("run2", second)])
    assert [v.valid for v in verdicts] == [False, False]
    summary = describe_lane_a_verdict(verdicts)
    assert "run1" in summary and "run2" in summary


def test_r23_01_missing_documents_are_a_failure():
    assert "no documents" in describe_lane_a_verdict([])


def test_r23_01_non_object_document_fails_closed():
    for value in (None, [], "doc", 7):
        verdict = check_lane_a_document(value, label="run2")
        assert verdict.valid is False


def test_r23_01_measured_difference_remains_a_finding_not_a_failure():
    """Cross-environment numerical difference must NOT become a failure.

    This is the property the amendment protects; a hardening change that made
    drift fail would contradict AMEND-v4.
    """
    document = _lane_a_document()
    params = document["routes"]["da_a2_resting_v1"]["regeneration"][
        "regenerated_parameters"
    ]
    params["archived_parameter_equality"] = {
        "measured": True,
        "exact": False,
        "classification": "WITHIN_ULP_DIAGNOSTIC",
        "coefficient_max_abs_delta": 5.551115123125783e-17,
    }
    verdict = check_lane_a_document(document, label="run1")
    assert verdict.valid is True, verdict.failures
    assert len(verdict.findings) == 1


# --------------------------------------------------------------------------- #
# RH04-R23-02: host and forced paths cannot drift apart                      #
# --------------------------------------------------------------------------- #


def test_r23_02_host_path_uses_the_same_predicate_as_forced():
    """Both paths call `check_lane_a_document`; there is no second copy of the rule.

    If this import disappears, the host path has silently regrown its own
    weaker check -- which is exactly the Round 23 defect.
    """
    source = (
        Path(__file__).resolve().parents[2]
        / ".github"
        / "workflows"
        / "rh04-dual-run-gate.yml"
    )
    assert source.is_file(), "mandatory workflow source is absent"
    text = source.read_text(encoding="utf-8")
    assert text.count("rh04_v2_lane_a_validation") >= 2, (
        "both the forced and host Lane A steps must import the shared predicate"
    )
    host_section = text.split("Lane A under host dispatch", 1)[1].split("Lane B under host", 1)[0]
    assert "check_lane_a_document" in host_section
    forced_section = text.split('"Stage 2', 1)[1].split('"Stage 3', 1)[0]
    assert "validate_lane_a_documents" in forced_section


def test_r23_02_host_validity_never_depends_on_any_failure_alone():
    document = _lane_a_document()
    document["any_failure"] = False
    document["validity"] = {"valid": False, "failures": ["STRUCTURE_DRIFT"]}
    verdict = check_lane_a_document(document, label="host")
    assert verdict.valid is False, (
        "any_failure=False was sufficient to pass; that is the R23-02 defect"
    )


# --------------------------------------------------------------------------- #
# RH04-R23-03: evidence publication security                                 #
# --------------------------------------------------------------------------- #


def _evidence_tree(tmp_path: Path, *, lane_b: bool = True) -> Path:
    root = tmp_path / "evidence"
    (root / "lane-a").mkdir(parents=True)
    if lane_b:
        (root / "lane-b").mkdir(parents=True)
    (root / "lane-a" / "run1.json").write_text(
        json.dumps({"validity": {"valid": True}, "routes": {}, "any_failure": False})
    )
    (root / "lane-a" / "run2.json").write_text(
        json.dumps({"validity": {"valid": True}, "routes": {}, "any_failure": False})
    )
    if lane_b:
        (root / "lane-b" / "observed.json").write_text(
            json.dumps({"observed_digest": "0" * 64, "verdict": "ACCEPTED"})
        )
        (root / "lane-b" / "identity.json").write_text(
            json.dumps({"observed_digest": "0" * 64, "verdict": "ACCEPTED"})
        )
    # R24-F02: the aggregate summary is the SCIENTIFIC record only. The
    # publication verdict moved to publication-status.json, which is never
    # published, so that the published summary cannot depend on publication
    # outcome. `stages` is an object and `scope_note` a string, matching the real
    # producer in the workflow.
    (root / "gate-summary.json").write_text(
        json.dumps({"stages": {}, "scope_note": "Scientific stage exit codes only."})
    )
    return root


def _scan_lane_a(root: Path):
    return security.scan_evidence(root / "lane-a", required=(), directory="lane-a")


def test_r23_03_clean_evidence_passes(tmp_path):
    root = _evidence_tree(tmp_path)
    assert security.scan_evidence(root).passed is True


def test_r23_03_forbidden_absolute_path_is_refused(tmp_path):
    root = _evidence_tree(tmp_path)
    (root / "lane-a" / "run1.json").write_text(
        json.dumps(
            {
                "validity": {"valid": True},
                "routes": {},
                "any_failure": False,
                "leak": "/home/runner/private",
            }
        )
    )
    result = security.scan_evidence(root)
    assert result.passed is False
    assert any("absolute_home_path" in f for f in result.failures)


def test_r23_03_private_key_armour_is_refused(tmp_path):
    root = _evidence_tree(tmp_path)
    (root / "lane-b" / "observed.json").write_text(
        '{"observed_digest": "0", "verdict": "ACCEPTED", "k": "BEGIN OPENSSH PRIVATE KEY"}'
    )
    result = security.scan_evidence(root)
    assert result.passed is False
    assert any("private_key" in f for f in result.failures)


def test_r23_03_credential_shaped_token_is_refused(tmp_path):
    root = _evidence_tree(tmp_path)
    (root / "lane-a" / "run1.json").write_text(
        json.dumps(
            {
                "validity": {"valid": True},
                "routes": {},
                "any_failure": False,
                "t": "ghp_" + "a" * 36,
            }
        )
    )
    result = security.scan_evidence(root)
    assert result.passed is False
    assert any("credential_token" in f for f in result.failures)


def test_r23_03_unexpected_file_type_is_refused(tmp_path):
    root = _evidence_tree(tmp_path)
    (root / "lane-a" / "bundle.pkl").write_bytes(b"\x80\x04binary")
    result = security.scan_evidence(root)
    assert result.passed is False
    assert any("allowlist" in f for f in result.failures)


def test_r23_03_scan_error_is_a_failure_not_a_pass(tmp_path, monkeypatch):
    """Inject an actual read failure at the scanner's I/O boundary on any OS."""
    root = _evidence_tree(tmp_path)
    target = root / "lane-a" / "run1.json"
    assert _scan_lane_a(root).passed is True
    original_read = Path.read_bytes
    reads = []

    def denied_read(path):
        if path == target:
            reads.append(path)
            raise PermissionError("synthetic read failure")
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", denied_read)
    result = _scan_lane_a(root)
    assert reads == [target]
    assert result.passed is False
    assert any("scan could not complete" in f for f in result.failures)


def test_r23_03_missing_evidence_root_is_a_failure(tmp_path):
    result = security.scan_evidence(tmp_path / "absent")
    assert result.passed is False


def test_r23_03_absent_evidence_directory_is_a_failure(tmp_path):
    root = _evidence_tree(tmp_path, lane_b=False)
    assert security.main([str(root), "--evidence-dirs", "lane-a", "lane-b"]) == 1


def test_r23_03_required_file_absent_is_a_failure(tmp_path):
    root = _evidence_tree(tmp_path)
    (root / "lane-b" / "observed.json").unlink()
    result = security.scan_evidence(root)
    assert result.passed is False
    assert any("REQUIRED evidence file is absent" in f for f in result.failures)


def test_r23_03_empty_file_is_a_failure(tmp_path):
    root = _evidence_tree(tmp_path)
    (root / "lane-a" / "run1.json").write_text("")
    result = security.scan_evidence(root)
    assert result.passed is False
    assert any("empty file" in f for f in result.failures)


def test_r23_03_malformed_json_is_a_failure(tmp_path):
    root = _evidence_tree(tmp_path)
    (root / "lane-a" / "run1.json").write_text('{"validity":')
    result = security.scan_evidence(root)
    assert result.passed is False
    assert any("not valid JSON" in f for f in result.failures)


def test_r23_03_missing_required_key_is_a_failure(tmp_path):
    root = _evidence_tree(tmp_path)
    (root / "lane-a" / "run1.json").write_text('{"routes": {}, "any_failure": false}')
    result = security.scan_evidence(root)
    assert result.passed is False
    assert any("missing required key" in f for f in result.failures)


def test_r23_03_symlink_is_refused(tmp_path):
    root = _evidence_tree(tmp_path)
    target = root / "lane-a" / "run1.json"
    target.unlink()
    target.symlink_to("/etc/hostname")
    result = security.scan_evidence(root)
    assert result.passed is False
    assert any("symlink" in f for f in result.failures)


def test_r23_03_oversized_file_is_refused(tmp_path, monkeypatch):
    root = _evidence_tree(tmp_path)
    monkeypatch.setattr(security, "MAX_FILE_BYTES", 10)
    result = security.scan_evidence(root)
    assert result.passed is False
    assert any("exceeds" in f for f in result.failures)


def test_r23_03_failure_messages_never_contain_the_matched_text(tmp_path):
    """A leak must not become a second leak in the log or the status artifact."""
    secret = "/home/very-secret-user/private/key.pem"
    root = _evidence_tree(tmp_path)
    (root / "lane-a" / "run1.json").write_text(
        json.dumps(
            {
                "validity": {"valid": True},
                "routes": {},
                "any_failure": False,
                "leak": secret,
            }
        )
    )
    result = security.scan_evidence(root)
    rendered = json.dumps(result.to_record())
    assert secret not in rendered
    assert "very-secret-user" not in rendered
    assert "absolute_home_path" in rendered


def test_r23_03_sanitized_status_contains_no_unsafe_content(tmp_path):
    secret = "/home/very-secret-user/private/key.pem"
    root = _evidence_tree(tmp_path)
    (root / "lane-a" / "run1.json").write_text(
        json.dumps(
            {
                "validity": {"valid": True},
                "routes": {},
                "any_failure": False,
                "leak": secret,
            }
        )
    )
    result = security.scan_evidence(root)
    status = security.write_sanitized_status(tmp_path / "status.json", result)
    body = status.read_text()
    assert "very-secret-user" not in body
    assert json.loads(body)["passed"] is False


def test_r23_03_enforcement_raises_rather_than_returning_a_pass(tmp_path):
    root = _evidence_tree(tmp_path)
    (root / "lane-a" / "extra.bin").write_bytes(b"\x00")
    with pytest.raises(security.SecurityFailure):
        security.enforce_evidence_security(root)


def test_r23_03_publication_is_gated_on_the_security_verdict():
    """The upload step must depend on Stage 5, not run unconditionally."""
    source = (
        Path(__file__).resolve().parents[2]
        / ".github"
        / "workflows"
        / "rh04-dual-run-gate.yml"
    )
    assert source.is_file(), "mandatory workflow source is absent"
    text = source.read_text(encoding="utf-8")
    upload = text.split("- name: Upload sealed publication package", 1)[1].split("\n      - name:", 1)[0]
    # R24-F03: publication is keyed on the SEAL and the VERIFY, not on Stage 5
    # alone. Stage 5 says the bytes were safe when scanned; the seal says the set
    # of published bytes is the set that was validated; verify re-derives every
    # digest immediately before upload. All three must hold.
    assert "steps.security.outputs.stage5_exit == '0'" in upload
    assert "steps.seal.outputs.stage8_exit == '0'" in upload, (
        "evidence upload is not gated on the seal"
    )
    assert "steps.verify.outputs.verify_exit == '0'" in upload, (
        "evidence upload is not gated on the post-seal verification"
    )
    # And the gate deliberately does NOT depend on the aggregate, so a retained
    # V1 failure cannot suppress publication of safe V2 evidence.
    assert "steps.aggregate.outcome" not in upload
    assert "if-no-files-found: error" in upload
    # Exactly one directory is uploaded: the sealed package. An evidence glob here
    # would let a file that was never sealed ride along.
    assert "path: publication-package/" in upload
    assert "lane-a/" not in upload


def test_r23_03_lane_b_failure_does_not_block_publication_of_lane_a_evidence():
    """A failed scientific stage still publishes its *validated* diagnostics."""
    source = (
        Path(__file__).resolve().parents[2]
        / ".github"
        / "workflows"
        / "rh04-dual-run-gate.yml"
    )
    assert source.is_file(), "mandatory workflow source is absent"
    text = source.read_text(encoding="utf-8")
    upload = text.split("- name: Upload sealed publication package", 1)[1].split("\n      - name:", 1)[0]
    # Publication is keyed on seal + verify, never on a scientific stage exit
    # code. A retained V1 failure (or a Lane B mismatch) must not suppress
    # publication of validated V2 evidence.
    assert "stage1_exit" not in upload and "stage2_exit" not in upload
    assert "stage3_exit" not in upload


def test_r23_03_mandatory_aggregate_semantics_preserved():
    """Hardening must not weaken the aggregate."""
    source = (
        Path(__file__).resolve().parents[2]
        / ".github"
        / "workflows"
        / "rh04-dual-run-gate.yml"
    )
    assert source.is_file(), "mandatory workflow source is absent"
    text = source.read_text(encoding="utf-8")
    # R2 strengthened the aggregate: the hardening suite, the seal and the
    # post-seal verification are all mandatory. A hardening or integrity failure
    # therefore fails the gate rather than passing silently.
    for required in (
        '"v1"',
        '"lane_a"',
        '"lane_b"',
        '"regression"',
        '"hardening"',
        '"security"',
        '"seal"',
        '"verify"',
    ):
        assert required in text.split("mandatory = (", 1)[1].split(")", 1)[0], (
            f"{required} is not a mandatory stage"
        )
    assert "NO_RESULT_RECORDED" in text


# --------------------------------------------------------------------------- #
# R2: the seal must validate a REAL checkout, not a tidy fixture directory.    #
#                                                                             #
# These three tests were added after the R2 self-review found that the seal     #
# was wired as `seal . ...` while the workflow runs in the repository checkout. #
# A fixture root containing only seven evidence files passed; the actual root   #
# contains `.git`, `research/` and every tracked file, all of which the seal    #
# classified as "unexpected evidence". The control failed closed on every       #
# legitimate run -- which is not a security control, it is an outage.           #
# --------------------------------------------------------------------------- #


def _publication_tree(root: Path) -> Path:
    """The real producer shape, written into `root`."""
    from research.intake import rh04_v2_publication_integrity as integrity

    (root / "lane-a").mkdir(parents=True, exist_ok=True)
    (root / "lane-b").mkdir(parents=True, exist_ok=True)
    for run in ("run1.json", "run2.json"):
        (root / "lane-a" / run).write_text(
            json.dumps(
                {"validity": {"valid": True}, "routes": {}, "any_failure": False}
            )
        )
    (root / "lane-a" / "identity.json").write_text(
        json.dumps({"regeneration_identical": True, "identities_run1": {}})
    )
    (root / "lane-a" / "classified.json").write_text(
        json.dumps({"digests": {}, "regeneration_identical": True})
    )
    for name in ("observed.json", "identity.json"):
        (root / "lane-b" / name).write_text(
            json.dumps({"observed_digest": "0" * 64, "verdict": "ACCEPTED"})
        )
    (root / "gate-summary.json").write_text(
        json.dumps({"stages": {}, "scope_note": "scientific only"})
    )
    assert integrity  # imported for its side effect: path must exist
    return root


def test_r2_seal_ignores_non_evidence_files_in_the_checkout(tmp_path):
    """A checkout full of non-evidence files must still seal.

    This is the regression test for the wiring defect: `seal .` runs at the
    repository root, so unrelated files are guaranteed to be present.
    """
    from research.intake import rh04_v2_publication_integrity as integrity

    root = _publication_tree(tmp_path / "checkout")
    # Simulate the checkout: a fake `.git`, a source tree, stray root files.
    (root / ".git").mkdir()
    (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    (root / "research").mkdir()
    (root / "research" / "intake.py").write_text("x = 1\n")
    (root / "README.md").write_text("# repo\n")
    (root / "pyproject.toml").write_text("[project]\n")

    sealed = integrity.seal_publication(
        root, tmp_path / "package", evidence_dirs=("lane-a", "lane-b")
    )
    published = sorted(entry.path for entry in sealed.entries)
    assert published == [
        "gate-summary.json",
        "lane-a/classified.json",
        "lane-a/identity.json",
        "lane-a/run1.json",
        "lane-a/run2.json",
        "lane-b/identity.json",
        "lane-b/observed.json",
    ]
    # Nothing from the checkout leaked into the package.
    for entry in sealed.entries:
        assert not entry.path.startswith((".git", "research", "README", "pyproject"))


def test_r2_seal_still_rejects_an_extra_file_inside_a_declared_directory(tmp_path):
    """Narrowing the surface must not narrow the check *within* the surface.

    R24-F01 was a file written into `lane-a/` after the scan. Declaring the
    directory keeps that protection: the directory is enumerated completely.
    """
    from research.intake import rh04_v2_publication_integrity as integrity

    root = _publication_tree(tmp_path / "checkout")
    (root / "lane-a" / "smuggled.json").write_text(json.dumps({"x": 1}))

    with pytest.raises(integrity.PublicationIntegrityError) as error:
        integrity.seal_publication(
            root, tmp_path / "package", evidence_dirs=("lane-a", "lane-b")
        )
    assert "smuggled.json" in str(error.value)
    assert not (tmp_path / "package").exists()


def test_r2_declared_but_absent_evidence_directory_fails_closed(tmp_path):
    """A directory the caller declares must exist. Absence is not emptiness."""
    from research.intake import rh04_v2_publication_integrity as integrity

    root = _publication_tree(tmp_path / "checkout")
    with pytest.raises(integrity.PublicationIntegrityError) as error:
        integrity.seal_publication(
            root, tmp_path / "package", evidence_dirs=("lane-a", "lane-b", "lane-c")
        )
    assert "lane-c" in str(error.value)


# --------------------------------------------------------------------------- #
# R2: presence is not validation. Wrong-typed values must be refused.          #
#                                                                             #
# `{"any_failure": "false"}` carries the required key and is a TRUTHY string:  #
# a downstream `if not any_failure:` reads it as a pass. Every expected type    #
# was derived from real producer output, and the genuine documents must still   #
# validate (asserted here, or the "fix" could reject all real evidence).        #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("relative", "field", "value"),
    [
        ("lane-a/run1.json", "any_failure", "false"),
        ("lane-a/run1.json", "any_failure", 0),
        ("lane-a/run1.json", "any_failure", None),
        ("lane-a/run1.json", "validity", []),
        ("lane-a/run2.json", "routes", "none"),
        ("lane-a/identity.json", "regeneration_identical", "true"),
        ("lane-a/classified.json", "digests", []),
        ("lane-b/observed.json", "observed_digest", None),
        ("lane-b/identity.json", "verdict", 1),
        ("gate-summary.json", "stages", []),
        ("gate-summary.json", "scope_note", True),
    ],
)
def test_r2_wrong_typed_evidence_value_is_refused(tmp_path, relative, field, value):
    """A key with the wrong type is not evidence; scan and seal must agree."""
    from research.intake import rh04_v2_publication_integrity as integrity

    root = _publication_tree(tmp_path / "checkout")
    document = json.loads((root / relative).read_text())
    document[field] = value
    (root / relative).write_text(json.dumps(document))

    # The shared scan refuses it ...
    with pytest.raises(security.SecurityFailure) as error:
        security.check_payload(relative, (root / relative).read_bytes())
    assert field in str(error.value)
    assert type(value).__name__ in str(error.value)

    # ... and so does the seal. Neither may publish it.
    with pytest.raises(integrity.PublicationIntegrityError):
        integrity.seal_publication(
            root, tmp_path / "package", evidence_dirs=("lane-a", "lane-b")
        )
    assert not (tmp_path / "package").exists()


def test_r2_true_boolean_is_not_confused_with_integer(tmp_path):
    """`isinstance(True, int)` is True; the check must still demand a bool."""
    root = _publication_tree(tmp_path / "checkout")
    document = json.loads((root / "lane-a/run1.json").read_text())
    document["any_failure"] = True
    (root / "lane-a/run1.json").write_text(json.dumps(document))
    security.check_payload("lane-a/run1.json", (root / "lane-a/run1.json").read_bytes())

    document["any_failure"] = 1  # equal in value, wrong in type
    (root / "lane-a/run1.json").write_text(json.dumps(document))
    with pytest.raises(security.SecurityFailure):
        security.check_payload(
            "lane-a/run1.json", (root / "lane-a/run1.json").read_bytes()
        )


def test_r2_genuine_producer_shape_still_validates(tmp_path):
    """The type rules must accept real evidence, not only reject attacks."""
    from research.intake import rh04_v2_publication_integrity as integrity

    root = _publication_tree(tmp_path / "checkout")
    sealed = integrity.seal_publication(
        root, tmp_path / "package", evidence_dirs=("lane-a", "lane-b")
    )
    assert len(sealed.entries) == 7
    assert integrity.verify_sealed_package(sealed.root).entries == sealed.entries


# --------------------------------------------------------------------------- #
# R2: the host path must seal only its own two documents.                     #
# --------------------------------------------------------------------------- #


def test_r2_host_seal_uses_root_documents_not_evidence_directories(tmp_path):
    """Host evidence is two root documents; `lane-a/` does not exist there."""
    from research.intake import rh04_v2_publication_integrity as integrity

    root = tmp_path / "host"
    root.mkdir()
    (root / "lane-a-host.json").write_text(
        json.dumps(
            {"any_failure": False, "routes": {}, "validity": {"valid": True}}
        )
    )
    (root / "lane-b-host.json").write_text(
        json.dumps({"observed_digest": "0" * 64, "verdict": "ACCEPTED"})
    )
    # A leftover status file in the same directory must not be sealed.
    (root / "security-status-host.json").write_text(json.dumps({"passed": True}))
    (root / "README.md").write_text("# checkout\n")

    table = {
        key: schema
        for key, schema in integrity.HOST_PUBLICATION_ALLOWLIST.items()
    }
    sealed = integrity.seal_publication(
        root,
        tmp_path / "package",
        allowlist=table,
        required=tuple(table),
        evidence_dirs=(),
    )
    assert sorted(entry.path for entry in sealed.entries) == [
        "lane-a-host.json",
        "lane-b-host.json",
    ]


def test_r2_host_seal_refuses_wrong_typed_any_failure(tmp_path):
    """The host path had its own weaker `any_failure` check in Round 23."""
    from research.intake import rh04_v2_publication_integrity as integrity

    root = tmp_path / "host"
    root.mkdir()
    (root / "lane-a-host.json").write_text(
        json.dumps({"any_failure": "false", "routes": {}, "validity": {}})
    )
    (root / "lane-b-host.json").write_text(
        json.dumps({"observed_digest": "0" * 64, "verdict": "ACCEPTED"})
    )
    with pytest.raises(integrity.PublicationIntegrityError) as error:
        integrity.seal_publication(
            root,
            tmp_path / "package",
            allowlist=integrity.HOST_PUBLICATION_ALLOWLIST,
            required=tuple(integrity.HOST_PUBLICATION_ALLOWLIST),
            evidence_dirs=(),
        )
    assert "any_failure" in str(error.value)


# Reviewer R24-F08/F09/F10: actual workflow boundaries. These portable tests
# inspect the exact installed step and execute the actual embedded Python
# aggregate without requiring a Bash installation on native Windows.
def _review_workflow_text():
    return (Path(__file__).resolve().parents[2] / ".github/workflows/rh04-dual-run-gate.yml").read_text(encoding="utf-8")


def _review_workflow_step(text, name):
    import re
    match = re.search(r"^      - name: " + re.escape(name) + r"\n(.*?)(?=^      - name: |^  host-dispatch:|\Z)", text, re.M | re.S)
    assert match, name
    return match.group(1)


def test_reviewer_f08_all_producer_exits_are_enforced():
    text = _review_workflow_text()
    a = _review_workflow_step(text, '"Stage 2 - Lane A regeneration and replay identity (mandatory)"')
    b = _review_workflow_step(text, '"Stage 3 - Lane B exact replay vs fixed reference (mandatory)"')
    assert 'run_code=$?' in a and 'producer_exit=$run_code' in a
    assert a.index('stage2_exit=%s') < a.index("python - <<'PY'")
    assert 'producer_exit=$?' in b
    assert b.index('stage3_exit=%s') < b.index("python - <<'PY'")
    for name in ('Lane A under host dispatch', 'Lane B under host dispatch'):
        step = _review_workflow_step(text, name)
        assert '| tee' not in step and 'exit "$producer_exit"' in step


@pytest.mark.parametrize('field,value,expected', [
    ('RH04_V1', '0', 0), ('RH04_V1', '1', 1),
    ('RH04_LANE_A', '17', 1), ('RH04_LANE_B', '23', 1),
    ('RH04_HARDENING', '', 1), ('RH04_SECURITY', '1', 1),
    ('RH04_SEAL', '', 1), ('RH04_VERIFY', '1', 1),
    ('RH04_VERIFY', ' 0', 1), ('RH04_VERIFY', 'not-a-code', 1),
    ('RH04_VERIFY', '256', 1),
])
def test_reviewer_f09_actual_aggregate(field, value, expected, tmp_path):
    import subprocess
    import sys
    import textwrap
    text = _review_workflow_text()
    name = '"Aggregate - fail if any mandatory stage failed"'
    step = _review_workflow_step(text, name)
    # The gate must actually run after all dependent steps and exit nonzero.
    assert text.index('id: seal') < text.index('id: verify') < text.index('id: aggregate')
    assert 'exit "$code"' in step
    assert 'continue-on-error' not in step
    assert 'if: always()' in step
    source = textwrap.dedent(step.split("python - <<'PY'\n", 1)[1].split('\n          PY', 1)[0])
    source = source.replace('${{ matrix.python-version }}', '3.11').replace('${{ matrix.dispatch-class }}', 'prescott')
    env = dict(os.environ, **{f'RH04_{key}': '0' for key in ('V1','LANE_A','LANE_B','REGRESSION','HARDENING','SECURITY','CLASSIFY','SUMMARY','SEAL','VERIFY')})
    env[field] = value
    result = subprocess.run([sys.executable, '-c', source], cwd=tmp_path, env=env, capture_output=True, text=True)
    assert (result.returncode != 0) == bool(expected), result.stderr
    record = json.loads((tmp_path / 'publication-status.json').read_text())
    assert record['all_mandatory_stages_passed'] is (expected == 0)
    if expected:
        assert any(item.startswith(field[5:].lower() + ':') for item in record['mandatory_failures'])


def test_reviewer_f09_host_gate_propagates_security_failure():
    step = _review_workflow_step(_review_workflow_text(), '"Host - fail closed unless security, seal and verify all passed"')
    assert step.rstrip().endswith('exit 1')
    assert "printf 'host_gate_exit=1\\n'" in step
    assert all(f'[ "${key}" = "0" ]' in step for key in ('SEC','SEAL','VER'))


def test_reviewer_f10_no_raw_summary_and_security_gates_publication():
    text = _review_workflow_text()
    upload = _review_workflow_step(text, 'Upload sealed publication package')
    assert all(f"steps.{step}.outputs.{output} == '0'" in upload for step, output in (('security','stage5_exit'),('seal','stage8_exit'),('verify','verify_exit')))
    assert 'steps.v1' not in upload and 'steps.aggregate' not in upload
    summary = _review_workflow_step(text, 'Publish per-class summary')
    assert 'cat lane-' not in summary
    assert 'INVALID_OR_MISSING' in summary
    assert text.index('id: verify') < text.index('- name: Upload sealed publication package') < text.index('- name: Publish per-class summary')


def test_reviewer_f11_rewritten_manifest_is_not_a_trusted_seal(tmp_path):
    import hashlib
    from research.intake import rh04_v2_publication_integrity as integrity
    root = _publication_tree(tmp_path / 'checkout')
    package = integrity.seal_publication(root, tmp_path / 'package')
    trusted = package.digest
    target = package.root / 'lane-a/run1.json'
    value = json.loads(target.read_text())
    value['synthetic_marker'] = 'BEGIN PRIVATE KEY'
    target.write_text(json.dumps(value))
    raw = target.read_bytes()
    manifest = json.loads((package.root / integrity.MANIFEST_NAME).read_text())
    for entry in manifest['files']:
        if entry['path'] == 'lane-a/run1.json':
            entry['sha256'] = hashlib.sha256(raw).hexdigest()
            entry['bytes'] = len(raw)
    (package.root / integrity.MANIFEST_NAME).write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    (package.root / integrity.MANIFEST_DIGEST_NAME).write_bytes(''.join(f"{e['sha256']}  {e['path']}\n" for e in manifest['files']).encode())
    assert package.digest == trusted
    with pytest.raises(integrity.PublicationIntegrityError, match='trusted seal digest'):
        integrity.verify_sealed_package(package.root, expected_digest=trusted)
    # Even an unanchored inspection must re-check the bytes' content rules.
    with pytest.raises(integrity.PublicationIntegrityError, match='content rejected'):
        integrity.verify_sealed_package(package.root)


@pytest.mark.parametrize('mutation', ['missing_sums', 'extra_member', 'missing_member'])
def test_reviewer_f11_complete_package_required(tmp_path, mutation):
    from research.intake import rh04_v2_publication_integrity as integrity
    root = _publication_tree(tmp_path / 'checkout')
    package = integrity.seal_publication(root, tmp_path / 'package')
    if mutation == 'missing_sums':
        (package.root / integrity.MANIFEST_DIGEST_NAME).write_text('')
    elif mutation == 'extra_member':
        (package.root / 'extra.json').write_text('{}')
    else:
        (package.root / 'lane-a/run1.json').unlink()
    with pytest.raises(integrity.PublicationIntegrityError):
        integrity.verify_sealed_package(package.root, expected_digest=package.digest)


def test_reviewer_f11_workflow_wires_original_seal_digest():
    text = _review_workflow_text()
    for seal_id, verify_name in (
        ('seal', '"Verify sealed package integrity (mandatory)"'),
        ('host_seal', '"Host - verify sealed package integrity (mandatory)"'),
    ):
        step = _review_workflow_step(text, verify_name)
        assert f'steps.{seal_id}.outputs.package_digest' in step
        assert '--expected-digest "$EXPECTED_PACKAGE_DIGEST"' in step
    assert text.count('--github-output "$GITHUB_OUTPUT"') == 2
