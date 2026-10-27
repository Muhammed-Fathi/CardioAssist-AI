"""Independent scope-authorization regressions for bounded offline diagnostics.

SYNTHETIC TEST SIMULATIONS ONLY. No real bundle, dataset, patient record,
maintainer comment, or human signature is present. A ratified scope is
simulated with an in-process monkeypatched registry and a throwaway Git repo.
The production registry is asserted EMPTY.
"""
from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace
from typing import Any

import pytest

from ai import diagnostic_scope as ds
from ai import diagnostic_inference as di
from ai.execution import RATIFIED_OPERATIONAL_SCOPE_AMENDMENTS
from ai.panels import DA_A2_RESTING_PANEL
from tests.experiments import diagnostic_fixtures as fx

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def git_env(tmp_path_factory: pytest.TempPathFactory) -> SimpleNamespace:
    return fx.make_scope_git_repo(tmp_path_factory.mktemp("diag_scope_git"))


@pytest.fixture(scope="module")
def bundle_env(tmp_path_factory: pytest.TempPathFactory) -> SimpleNamespace:
    return fx.make_simulated_accepted_bundle(
        tmp_path_factory.mktemp("diag_scope_bundle")
    )


def _auth(git_env: SimpleNamespace, manifest_sha256: str) -> dict[str, Any]:
    return fx.make_authorization_doc(
        manifest_sha256=manifest_sha256,
        g_sha=git_env.g_sha,
        d_sha=git_env.d_sha,
        doc_sha=git_env.doc_sha,
    )


def _record(git_env: SimpleNamespace, manifest_sha256: str) -> dict[str, Any]:
    return fx.make_scope_record(
        manifest_sha256=manifest_sha256,
        g_sha=git_env.g_sha,
        d_sha=git_env.d_sha,
        doc_sha=git_env.doc_sha,
    )


def _deep_update(base: dict[str, Any], changes: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(base)
    for key, value in changes.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_update(out[key], value)
        else:
            out[key] = value
    return out


def _install_registry(
    monkeypatch: pytest.MonkeyPatch, record: dict[str, Any]
) -> None:
    monkeypatch.setattr(
        ds,
        "RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES",
        {ds.DIAGNOSTIC_SCOPE_ID: record},
    )


# --------------------------------------------------------------------------- #
# 1. Production state: empty new registry, activated training registry, frozen A
# --------------------------------------------------------------------------- #


def test_production_diagnostic_registry_is_empty_and_fails_closed(
    git_env: SimpleNamespace,
    bundle_env: SimpleNamespace,
    tmp_path: Path,
) -> None:
    assert ds.RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES == {}
    with pytest.raises(ds.DiagnosticScopeError) as exc:
        ds.validate_diagnostic_scope(
            {"scope_id": ds.DIAGNOSTIC_SCOPE_ID}, repo_root=git_env.repo
        )
    assert exc.value.code == "diagnostic_scope_not_ratified"

    # Even a perfectly shaped local authorization + synthetic input cannot open
    # the interface while the independent registry is empty; no bundle check,
    # deserialization, or inference is reached.
    auth_path = fx.write_private_json(
        tmp_path / "private" / "authorization.json",
        _auth(git_env, bundle_env.manifest_sha256),
    )
    input_path = fx.write_private_json(
        tmp_path / "private" / "input.json", fx.make_input_doc()
    )
    called: list[bool] = []

    def _boom(*_args: Any, **_kwargs: Any) -> Any:
        called.append(True)
        raise AssertionError("bundle verification must not run without the new scope")

    original = di.verify_trusted_local_bundle
    di.verify_trusted_local_bundle = _boom  # type: ignore[assignment]
    try:
        with pytest.raises(ds.DiagnosticScopeError) as run_exc:
            di.run_offline_diagnostics(
                bundle_dir=bundle_env.bundle_dir,
                trusted_local_root=bundle_env.trusted_root,
                authorization_path=auth_path,
                input_path=input_path,
                operator_confirmation=ds.DIAGNOSTIC_OPERATOR_CONFIRMATION,
                signing_key=bundle_env.signing_key,
                repo_root=git_env.repo,
            )
        assert run_exc.value.code == "diagnostic_scope_not_ratified"
        assert called == []
    finally:
        di.verify_trusted_local_bundle = original  # type: ignore[assignment]

    with pytest.raises(ds.DiagnosticScopeError) as no_confirmation:
        di.run_offline_diagnostics(
            bundle_dir=bundle_env.bundle_dir,
            trusted_local_root=bundle_env.trusted_root,
            authorization_path=REPO_ROOT / "does-not-exist.json",
            input_path=REPO_ROOT / "does-not-exist.json",
            operator_confirmation="wrong",
        )
    assert no_confirmation.value.code == "diagnostic_operator_confirmation_required"


def test_frozen_bindings_match_activated_training_amendment_and_panel() -> None:
    training = RATIFIED_OPERATIONAL_SCOPE_AMENDMENTS[
        ds.FROZEN_TRAINING_AMENDMENT_ID
    ]
    assert ds.FROZEN_GOVERNANCE_MERGE_G == training["governance_merge_commit_sha"]
    assert ds.FROZEN_GOVERNANCE_MERGE_G == training["approved_code_revision"]
    assert (
        ds.DIAGNOSTIC_TARGET_BUNDLE["expected_source_sha256"]
        == training["frozen_source_sha256"]
    )
    assert set(training["approved_operations"]) == {
        "persistent_model_packaging",
        "patient_level_shap_background",
    }
    assert "inference" not in " ".join(training["approved_operations"])
    assert (
        ds.DIAGNOSTIC_TARGET_BUNDLE["expected_panel_contract_sha256"]
        == DA_A2_RESTING_PANEL.contract_sha256
        == "c18ad4cd2cf08f6fefb2e340573760da7000bc1d8eb4ad38783b873c018e57b8"
    )
    assert ds.DIAGNOSTIC_TARGET_BUNDLE["expected_ordered_feature_names"] == (
        "age",
        "sex",
        "cp",
        "trestbps",
        "restecg",
    )
    assert len(ds.DIAGNOSTIC_TARGET_BUNDLE["expected_ordered_feature_names"]) == 5
    assert ds.DIAGNOSTIC_INTERFACE_VERSION.startswith(
        "cardioassist.ai.bounded_offline_diagnostic_inference/v"
    )
    assert ds.DIAGNOSTIC_SCOPE_ACTIVATION_TEMPLATE["governance_pr_number"] is None
    assert ds.DIAGNOSTIC_SCOPE_ACTIVATION_TEMPLATE["expected_manifest_sha256"] is None


def test_new_code_is_post_activation_and_frozen_execution_file_is_unchanged() -> None:
    """Where A is available locally, prove the new files did not exist at A."""
    a = ds.FROZEN_TRAINING_REVISION_A
    available = subprocess.run(
        ["git", "cat-file", "-e", f"{a}^{{commit}}"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        check=False,
    )
    if available.returncode != 0:
        pytest.skip("frozen activation revision A is not present in this checkout")
    for new_file in ("ai/diagnostic_scope.py", "ai/diagnostic_inference.py"):
        probe = subprocess.run(
            ["git", "cat-file", "-e", f"{a}:{new_file}"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            check=False,
        )
        assert probe.returncode != 0, f"{new_file} must not be represented as existing at A"
    unchanged = subprocess.run(
        ["git", "diff", "--quiet", a, "--", "ai/execution.py", "ai/cli.py"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        check=False,
    )
    assert unchanged.returncode == 0, "frozen A execution registry / CLI must be preserved"


# --------------------------------------------------------------------------- #
# 2. Local operator authorization document
# --------------------------------------------------------------------------- #


def test_valid_local_authorization_passes_shape_checks(
    git_env: SimpleNamespace, bundle_env: SimpleNamespace
) -> None:
    doc = _auth(git_env, bundle_env.manifest_sha256)
    ds.validate_local_authorization(
        doc, operator_confirmation=ds.DIAGNOSTIC_OPERATOR_CONFIRMATION
    )


@pytest.mark.parametrize(
    ("changes", "expected_code"),
    [
        ({"operator_confirmation": "yes"}, "diagnostic_operator_confirmation_required"),
        ({"authorization_status": "TEMPLATE_NOT_AUTHORIZED"}, "diagnostic_authorization_not_effective"),
        ({"scope_id": "CAI-OTHER-SCOPE"}, "diagnostic_scope_id_mismatch"),
        ({"supervisor_signoff_claimed": True}, "diagnostic_supervisor_signoff_claimed"),
        ({"approved_operations": ["persistent_model_packaging"]}, "diagnostic_operations_not_bounded"),
        ({"human_attestation": "unbounded"}, "diagnostic_human_attestation_invalid"),
        ({"local_signer": ""}, "diagnostic_local_attestation_incomplete"),
        ({"local_signer": "PLACEHOLDER"}, "diagnostic_local_attestation_incomplete"),
        ({"local_signed_at_iso8601": "not-a-date"}, "diagnostic_local_attestation_incomplete"),
        ({"local_signed_at_iso8601": "2026-10-27T00:00:00"}, "diagnostic_local_attestation_incomplete"),
        ({"local_signature_attestation": "unbounded"}, "diagnostic_local_attestation_incomplete"),
        ({"governance_merge_commit_sha": "xyz"}, "diagnostic_git_evidence_malformed"),
        ({"approved_code_revision": "abc"}, "diagnostic_git_evidence_malformed"),
        ({"activation_merge_commit_sha": "def"}, "diagnostic_git_evidence_malformed"),
        ({"governance_pr_number": 0}, "diagnostic_git_evidence_malformed"),
        ({"governance_document_relative_path": "docs/other.md"}, "diagnostic_governance_document_path_mismatch"),
        ({"frozen_governance_document_sha256": "xyz"}, "diagnostic_governance_document_hash_malformed"),
        ({"ratified_by": "PLACEHOLDER"}, "diagnostic_ratification_evidence_incomplete"),
        ({"ratification_comment_exact": ""}, "diagnostic_ratification_evidence_incomplete"),
        ({"bundle_identity": {"expected_manifest_sha256": "xyz"}}, "diagnostic_bundle_identity_invalid"),
        ({"bundle_identity": {"bundle_dir_name": "another_bundle"}}, "diagnostic_bundle_identity_invalid"),
        ({"bundle_identity": {"expected_panel_id": "da_a2_resting_labs_v1"}}, "diagnostic_bundle_identity_invalid"),
        ({"bundle_identity": {"expected_selected_c": 1.0}}, "diagnostic_bundle_identity_invalid"),
        ({"input_declaration": {"contains_patient_data": True}}, "diagnostic_input_declaration_invalid"),
        ({"input_declaration": {"origin": "REAL_PATIENT_RECORDS"}}, "diagnostic_input_declaration_invalid"),
        ({"input_declaration": {"records_are_synthetic": False}}, "diagnostic_input_declaration_invalid"),
        ({"input_declaration": {"panel_id": "da_a2_resting_labs_v1"}}, "diagnostic_input_declaration_invalid"),
        ({"execution_boundary": {"offline_only": False}}, "diagnostic_execution_boundary_invalid"),
        ({"execution_boundary": {"api_serving": True}}, "diagnostic_execution_boundary_invalid"),
        ({"execution_boundary": {"telemetry": True}}, "diagnostic_execution_boundary_invalid"),
        ({"execution_boundary": {"uploads": True}}, "diagnostic_execution_boundary_invalid"),
        ({"execution_boundary": {"writes_bundle": True}}, "diagnostic_execution_boundary_invalid"),
        ({"execution_boundary": {"retraining_or_tuning": True}}, "diagnostic_execution_boundary_invalid"),
        ({"execution_boundary": {"patient_data_inputs": True}}, "diagnostic_execution_boundary_invalid"),
        ({"extra_key": True}, "diagnostic_authorization_field_set_invalid"),
        ({"execution_boundary": {"extra_key": True}}, "diagnostic_authorization_field_set_invalid"),
    ],
)
def test_local_authorization_negative_cases(
    git_env: SimpleNamespace,
    bundle_env: SimpleNamespace,
    changes: dict[str, Any],
    expected_code: str,
) -> None:
    doc = _deep_update(_auth(git_env, bundle_env.manifest_sha256), changes)
    with pytest.raises(ds.DiagnosticScopeError) as exc:
        ds.validate_local_authorization(
            doc, operator_confirmation=ds.DIAGNOSTIC_OPERATOR_CONFIRMATION
        )
    assert exc.value.code == expected_code


def test_local_authorization_requires_explicit_confirmation_argument(
    git_env: SimpleNamespace, bundle_env: SimpleNamespace
) -> None:
    doc = _auth(git_env, bundle_env.manifest_sha256)
    with pytest.raises(ds.DiagnosticScopeError) as exc:
        ds.validate_local_authorization(doc, operator_confirmation=None)
    assert exc.value.code == "diagnostic_operator_confirmation_required"


@pytest.mark.parametrize(
    ("raw", "expected_code"),
    [
        ('{"a": 1, "a": 2}', "diagnostic_duplicate_json_key"),
        ('{"a": NaN}', "diagnostic_non_finite_json_constant"),
        ('{"a": Infinity}', "diagnostic_non_finite_json_constant"),
        ('{"a": -Infinity}', "diagnostic_non_finite_json_constant"),
        ('{"a": 1e400}', "diagnostic_non_finite_local_value"),
        ('{"a":', "diagnostic_malformed_local_json"),
        ('[1, 2]', "diagnostic_malformed_local_json"),
    ],
)
def test_local_authorization_file_rejects_malformed_or_non_finite_json(
    tmp_path: Path, raw: str, expected_code: str
) -> None:
    path = fx.write_private_json(tmp_path / "private" / "authorization.json", {}, raw=raw)
    with pytest.raises(ds.DiagnosticScopeError) as exc:
        ds.load_diagnostic_authorization(
            path, repo_root=tmp_path / "other_checkout_not_this_dir"
        )
    assert exc.value.code == expected_code


def test_local_authorization_file_rejects_symlink_and_oversize(
    tmp_path: Path,
) -> None:
    target = fx.write_private_json(tmp_path / "private" / "real.json", {})
    if os.name != "nt":
        link = tmp_path / "private" / "link.json"
        link.symlink_to(target)
        with pytest.raises(ds.DiagnosticScopeError) as exc:
            ds.load_diagnostic_authorization(
                link, repo_root=tmp_path / "other_checkout_not_this_dir"
            )
        assert exc.value.code == "diagnostic_local_file_untrusted"

    big = tmp_path / "private" / "big.json"
    fx.write_private_json(big, {}, raw=" " * (ds.DIAGNOSTIC_MAX_AUTHORIZATION_BYTES + 1))
    with pytest.raises(ds.DiagnosticScopeError) as exc_big:
        ds.load_diagnostic_authorization(
            big, repo_root=tmp_path / "other_checkout_not_this_dir"
        )
    assert exc_big.value.code in {
        "diagnostic_local_file_too_large",
        "diagnostic_malformed_local_json",
    }


def test_local_authorization_file_inside_checkout_must_be_git_ignored(
    git_env: SimpleNamespace, bundle_env: SimpleNamespace
) -> None:
    unignored = fx.write_private_json(
        git_env.repo / "unignored_authorization.json",
        _auth(git_env, bundle_env.manifest_sha256),
    )
    with pytest.raises(ds.DiagnosticScopeError) as exc:
        ds.load_diagnostic_authorization(unignored, repo_root=git_env.repo)
    assert exc.value.code == "diagnostic_local_file_not_git_ignored"
    ignored = fx.write_private_json(
        git_env.repo / "data" / "diagnostics" / "ignored_authorization.json",
        _auth(git_env, bundle_env.manifest_sha256),
    )
    assert ds.load_diagnostic_authorization(ignored, repo_root=git_env.repo)


# --------------------------------------------------------------------------- #
# 3. Independent ratification, trusted record, and Git evidence
# --------------------------------------------------------------------------- #


def test_ratified_scope_happy_path_returns_exact_bindings(
    monkeypatch: pytest.MonkeyPatch,
    git_env: SimpleNamespace,
    bundle_env: SimpleNamespace,
) -> None:
    _install_registry(monkeypatch, _record(git_env, bundle_env.manifest_sha256))
    context = ds.authorize_diagnostic_scope(
        _auth(git_env, bundle_env.manifest_sha256),
        repo_root=git_env.repo,
        operator_confirmation=ds.DIAGNOSTIC_OPERATOR_CONFIRMATION,
    )
    assert context.scope_id == ds.DIAGNOSTIC_SCOPE_ID
    assert context.approved_operations == ds.DIAGNOSTIC_ALLOWED_OPERATIONS
    assert context.expected_manifest_sha256 == bundle_env.manifest_sha256
    assert context.expected_source_sha256 == (
        ds.DIAGNOSTIC_TARGET_BUNDLE["expected_source_sha256"]
    )
    assert context.expected_selected_c == 10.0
    assert "expected_bundle_dir_name" in context.identity()


@pytest.mark.parametrize(
    ("auth_changes", "expected_code"),
    [
        ({"ratified_by": "someone-else"}, "diagnostic_scope_claim_mismatch"),
        ({"ratification_comment_exact": "different"}, "diagnostic_scope_claim_mismatch"),
        ({"governance_pr_number": 1}, "diagnostic_scope_claim_mismatch"),
        ({"approved_code_revision": "0" * 40}, "diagnostic_scope_claim_mismatch"),
        ({"activation_merge_commit_sha": "0" * 40}, "diagnostic_scope_claim_mismatch"),
        ({"bundle_identity": {"expected_manifest_sha256": "0" * 64}}, "diagnostic_scope_claim_mismatch"),
        ({"frozen_governance_document_sha256": "0" * 64}, "diagnostic_scope_claim_mismatch"),
    ],
)
def test_manifest_claims_cannot_override_trusted_record(
    monkeypatch: pytest.MonkeyPatch,
    git_env: SimpleNamespace,
    bundle_env: SimpleNamespace,
    auth_changes: dict[str, Any],
    expected_code: str,
) -> None:
    _install_registry(monkeypatch, _record(git_env, bundle_env.manifest_sha256))
    doc = _deep_update(_auth(git_env, bundle_env.manifest_sha256), auth_changes)
    with pytest.raises(ds.DiagnosticScopeError) as exc:
        ds.validate_diagnostic_scope(doc, repo_root=git_env.repo)
    assert exc.value.code == expected_code


@pytest.mark.parametrize(
    ("record_changes", "expected_code"),
    [
        ({"approved_operations": ("persistent_model_packaging",)}, "diagnostic_scope_registry_entry_invalid"),
        ({"expected_panel_id": "da_a2_resting_labs_v1"}, "diagnostic_scope_registry_entry_invalid"),
        ({"expected_selected_c": 1.0}, "diagnostic_scope_registry_entry_invalid"),
        ({"expected_model_family": "constrained_random_forest"}, "diagnostic_scope_registry_entry_invalid"),
        ({"expected_source_sha256": "0" * 64}, "diagnostic_scope_registry_entry_invalid"),
        ({"expected_manifest_sha256": "PLACEHOLDER"}, "diagnostic_scope_registry_entry_invalid"),
        ({"governance_merge_commit_sha": "PLACEHOLDER"}, "diagnostic_scope_registry_entry_invalid"),
        ({"ratified_by": ""}, "diagnostic_scope_registry_entry_invalid"),
        ({"expected_model_id": "another-model"}, "diagnostic_scope_registry_entry_invalid"),
        ({"approved_code_revision": ds.FROZEN_TRAINING_REVISION_A}, "diagnostic_scope_reuses_training_activation"),
        ({"governance_merge_commit_sha": ds.FROZEN_GOVERNANCE_MERGE_G}, "diagnostic_scope_reuses_training_activation"),
    ],
)
def test_trusted_record_cannot_bind_a_different_bundle_or_operation(
    monkeypatch: pytest.MonkeyPatch,
    git_env: SimpleNamespace,
    bundle_env: SimpleNamespace,
    record_changes: dict[str, Any],
    expected_code: str,
) -> None:
    record = _deep_update(_record(git_env, bundle_env.manifest_sha256), record_changes)
    _install_registry(monkeypatch, record)
    with pytest.raises(ds.DiagnosticScopeError) as exc:
        ds.validate_diagnostic_scope(
            _auth(git_env, bundle_env.manifest_sha256), repo_root=git_env.repo
        )
    assert exc.value.code == expected_code


def test_governance_commit_absent_or_not_ancestor_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    git_env = fx.make_scope_git_repo(tmp_path / "git_missing")
    manifest_sha = "a" * 64
    record = _record(git_env, manifest_sha)
    record["governance_merge_commit_sha"] = "f" * 40
    _install_registry(monkeypatch, record)
    doc = _auth(git_env, manifest_sha)
    doc["governance_merge_commit_sha"] = "f" * 40
    with pytest.raises(ds.DiagnosticScopeError) as exc:
        ds.validate_diagnostic_scope(doc, repo_root=git_env.repo)
    assert exc.value.code == "diagnostic_governance_commit_missing"


def test_document_hash_mismatch_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    git_env = fx.make_scope_git_repo(tmp_path / "git_hash")
    manifest_sha = "b" * 64
    record = _record(git_env, manifest_sha)
    record["frozen_governance_document_sha256"] = "0" * 64
    _install_registry(monkeypatch, record)
    doc = _auth(git_env, manifest_sha)
    doc["frozen_governance_document_sha256"] = "0" * 64
    with pytest.raises(ds.DiagnosticScopeError) as exc:
        ds.validate_diagnostic_scope(doc, repo_root=git_env.repo)
    assert exc.value.code == "diagnostic_governance_document_hash_mismatch"


def test_governance_document_absent_at_merge_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    git_env = fx.make_scope_git_repo(tmp_path / "git_doc", include_doc=False)
    manifest_sha = "c" * 64
    _install_registry(monkeypatch, _record(git_env, manifest_sha))
    with pytest.raises(ds.DiagnosticScopeError) as exc:
        ds.validate_diagnostic_scope(
            _auth(git_env, manifest_sha), repo_root=git_env.repo
        )
    assert exc.value.code == "diagnostic_governance_document_missing"


def test_stale_or_dirty_execution_revision_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    git_env = fx.make_scope_git_repo(tmp_path / "git_rev")
    manifest_sha = "d" * 64
    _install_registry(monkeypatch, _record(git_env, manifest_sha))
    doc = _auth(git_env, manifest_sha)

    # Move HEAD beyond the approved revision (clean, but different code).
    extra = git_env.repo / "EXTRA.md"
    extra.write_text("post-approval change\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "."], cwd=str(git_env.repo), check=True, capture_output=True
    )
    subprocess.run(
        ["git", "commit", "-m", "unreviewed later revision"],
        cwd=str(git_env.repo), check=True, capture_output=True,
    )
    with pytest.raises(ds.DiagnosticScopeError) as stale:
        ds.validate_diagnostic_scope(doc, repo_root=git_env.repo)
    assert stale.value.code == "diagnostic_execution_revision_mismatch"

    # Restore the approved revision but dirty a tracked file.
    subprocess.run(
        ["git", "reset", "--hard", git_env.d_sha],
        cwd=str(git_env.repo), check=True, capture_output=True,
    )
    (git_env.repo / "README.md").write_text("dirty\n", encoding="utf-8")
    with pytest.raises(ds.DiagnosticScopeError) as dirty:
        ds.validate_diagnostic_scope(doc, repo_root=git_env.repo)
    assert dirty.value.code == "diagnostic_worktree_not_clean"


# --------------------------------------------------------------------------- #
# 4. Isolation: no serving, no network, no training, no CLI coupling
# --------------------------------------------------------------------------- #


def test_new_modules_have_no_network_or_mutation_imports() -> None:
    forbidden_modules = {
        "socket", "requests", "urllib", "http", "httpx", "aiohttp", "boto3",
        "smtplib", "ftplib", "paramiko", "telnetlib", "google.cloud",
    }
    forbidden_calls = {
        "train_research_model", "package_research_bundle", "joblib.dump",
        "write_bundle_acceptance_marker", "write_bundle_quarantine_marker",
        "execute_authorized_research_run", "execute_guarded_cleveland_d047_run",
        "os.system", "Popen", "urlopen",
    }
    for rel in ("ai/diagnostic_scope.py", "ai/diagnostic_inference.py"):
        tree = ast.parse((REPO_ROOT / rel).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in forbidden_modules
                    assert alias.name not in forbidden_modules
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] not in forbidden_modules
            elif isinstance(node, ast.Call):
                func = node.func
                name = (
                    func.id
                    if isinstance(func, ast.Name)
                    else (
                        f"{getattr(func.value, 'id', '')}.{func.attr}"
                        if isinstance(func, ast.Attribute)
                        else ""
                    )
                )
                assert name not in forbidden_calls


def test_general_cli_and_backend_never_import_diagnostic_interface() -> None:
    cli_tree = ast.parse((REPO_ROOT / "ai" / "cli.py").read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(cli_tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert "ai.diagnostic_inference" not in imported
    assert "ai.diagnostic_scope" not in imported
    for backend_file in (REPO_ROOT / "backend" / "app").rglob("*.py"):
        text = backend_file.read_text(encoding="utf-8")
        assert "diagnostic_inference" not in text
        assert "diagnostic_scope" not in text
