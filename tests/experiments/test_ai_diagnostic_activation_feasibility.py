"""Genuine committed-Git-history activation feasibility for diagnostic scope.

This module proves the ACTIVATION PROCEDURE IS REALIZABLE, not merely that an
in-process registry can be injected. For every case it:

1. commits a synthetic approved implementation at I2 (copy of the real
   ``ai/diagnostic_scope.py`` with an EMPTY registry);
2. commits the ratified governance document at G2 (documentation only);
3. writes the REAL registry structure (G2, I2, document hash, synthetic
   test-only bundle manifest digest) into the tracked
   ``ai/diagnostic_scope.py`` and commits ONLY that change as A2;
4. obtains A2 from git AFTER the commit exists;
5. writes the ignored local operator authorization carrying that actual A2;
6. executes the production authorization validator at clean HEAD A2.

The in-process registry used by the validator is obtained by EXECUTING the
committed A2 source as a Python module -- i.e. the exact state the imported
module has at A2. It is not an invented dictionary. The validator additionally
reads and verifies the committed source itself, so no monkeypatch-only state
can pass. No real bundle, patient record, signature, or approval is used.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import types
from typing import Any, Callable

import pytest

from ai import diagnostic_inference as di
from ai import diagnostic_scope as ds
from ai.lime_explainability import LimeConfig
from tests.experiments import diagnostic_fixtures as fx

REPO_ROOT = Path(__file__).resolve().parents[2]
FAST_LIME = LimeConfig(num_perturbations=64, seed=4321)
FAST_LIME_SEEDS = (101, 202, 303)


@pytest.fixture(scope="module")
def bundle_env(tmp_path_factory: pytest.TempPathFactory) -> Any:
    return fx.make_simulated_accepted_bundle(
        tmp_path_factory.mktemp("diag_activation_bundle")
    )


def _committed_source_at(repo: Path, revision: str, relative_path: str) -> str:
    proc = subprocess.run(
        ["git", "show", f"{revision}:{relative_path}"],
        cwd=str(repo),
        capture_output=True,
        check=True,
    )
    return proc.stdout.decode("utf-8")


def _committed_source(repo: Path, revision: str) -> str:
    return _committed_source_at(
        repo, revision, ds.DIAGNOSTIC_ACTIVATION_REGISTRY_RELATIVE_PATH
    )


def _live_registry_from_committed_source(repo: Path, revision: str) -> dict[str, Any]:
    """Execute the ACTUAL committed A2 module and return its registry object."""
    name = "diagnostic_scope_at_a2_synthetic_test"
    module = types.ModuleType(name)
    # dataclasses resolves string annotations via sys.modules[cls.__module__].
    sys.modules[name] = module
    try:
        exec(  # noqa: S102 - intentional: prove the committed source is a valid module
            compile(
                _committed_source(repo, revision),
                f"{ds.DIAGNOSTIC_ACTIVATION_REGISTRY_RELATIVE_PATH}@{revision[:12]}",
                "exec",
            ),
            module.__dict__,
        )
    finally:
        sys.modules.pop(name, None)
    registry = module.RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES
    assert isinstance(registry, dict)
    return registry


@pytest.fixture
def activation_factory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    bundle_env: Any,
) -> Callable[..., Any]:
    counter = [0]

    def build(**kwargs: Any) -> Any:
        counter[0] += 1
        env = fx.build_activation_repo(
            tmp_path / f"activation_repo_{counter[0]}",
            manifest_sha256=bundle_env.manifest_sha256,
            **kwargs,
        )
        live = _live_registry_from_committed_source(env.repo, env.a2)
        assert live == env.committed_literal
        monkeypatch.setattr(ds, "RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES", live)
        return env

    return build


# --------------------------------------------------------------------------- #
# 1. Realizable two-commit activation: positive evidence
# --------------------------------------------------------------------------- #


def test_committed_g2_to_a2_activation_is_realizable(
    activation_factory: Callable[..., Any],
) -> None:
    env = activation_factory()

    # Three distinct, independently resolved revisions.
    assert env.i2 != env.g2 != env.a2 != env.i2
    assert env.head == env.a2

    # A2 is NOT in any tracked content: no self-referential SHA.
    tracked_record = env.committed_literal[ds.DIAGNOSTIC_SCOPE_ID]
    assert env.a2 not in repr(tracked_record)
    assert "activation_merge_commit_sha" not in tracked_record
    assert "approved_code_revision" not in tracked_record
    assert "activation_revision_commit_sha" not in tracked_record
    assert tracked_record["governance_baseline_commit_sha"] == env.g2
    assert tracked_record["approved_implementation_commit_sha"] == env.i2
    assert tracked_record["frozen_governance_document_sha256"] == env.doc_sha
    assert tracked_record["expected_manifest_sha256"] == env.auth["bundle_identity"][
        "expected_manifest_sha256"
    ]
    assert tuple(tracked_record["approved_operations"]) == (
        ds.DIAGNOSTIC_ALLOWED_OPERATIONS
    )

    # A2 is known only AFTER the commit and lives only in the ignored local doc.
    assert env.auth["activation_merge_commit_sha"] == env.a2
    assert env.auth["governance_baseline_commit_sha"] == env.g2
    assert env.auth["approved_implementation_commit_sha"] == env.i2
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", "--", "data/diagnostics/diagnostic_authorization.json"],
        cwd=str(env.repo),
        capture_output=True,
        check=False,
    )
    assert ignored.returncode == 0
    # The A2 value appears in NO tracked file at HEAD.
    for tracked in (
        ds.DIAGNOSTIC_ACTIVATION_REGISTRY_RELATIVE_PATH,
        ds.DIAGNOSTIC_GOVERNANCE_DOCUMENT_RELATIVE_PATH,
        "README.md",
    ):
        assert env.a2 not in _committed_source_at(env.repo, env.a2, tracked)

    # G2 -> A2 changes ONLY the registry file; I2 -> G2 only documentation.
    diff = subprocess.run(
        ["git", "diff", "--name-status", "--no-renames", env.g2, env.a2, "--"],
        cwd=str(env.repo),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert diff == f"M\t{ds.DIAGNOSTIC_ACTIVATION_REGISTRY_RELATIVE_PATH}"
    impl_diff = subprocess.run(
        ["git", "diff", "--name-only", "--no-renames", env.i2, env.g2, "--"],
        cwd=str(env.repo),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    assert impl_diff and all(path.startswith("docs/") for path in impl_diff)

    # The production validator accepts the complete authorization at clean HEAD.
    context = ds.authorize_diagnostic_scope(
        env.auth,
        repo_root=env.repo,
        operator_confirmation=ds.DIAGNOSTIC_OPERATOR_CONFIRMATION,
    )
    assert context.activation_merge_commit_sha == env.a2
    assert context.governance_baseline_commit_sha == env.g2
    assert context.approved_implementation_commit_sha == env.i2
    assert context.approved_operations == ds.DIAGNOSTIC_ALLOWED_OPERATIONS
    assert context.expected_manifest_sha256 == tracked_record[
        "expected_manifest_sha256"
    ]
    assert context.identity()["activation_registry_relative_path"] == (
        ds.DIAGNOSTIC_ACTIVATION_REGISTRY_RELATIVE_PATH
    )


def test_full_synthetic_diagnostic_run_at_committed_a2(
    activation_factory: Callable[..., Any],
    bundle_env: Any,
) -> None:
    """End-to-end: real A2 commit + real simulated bundle + full inference."""
    env = activation_factory()
    input_path = fx.write_private_json(
        env.repo / "data" / "diagnostics" / "diagnostic_input.json",
        fx.make_input_doc(),
    )
    report = di.run_offline_diagnostics(
        bundle_dir=bundle_env.bundle_dir,
        trusted_local_root=bundle_env.trusted_root,
        authorization_path=env.auth_path,
        input_path=input_path,
        operator_confirmation=ds.DIAGNOSTIC_OPERATOR_CONFIRMATION,
        signing_key=bundle_env.signing_key,
        repo_root=env.repo,
        lime_config=FAST_LIME,
        lime_stability_seeds=FAST_LIME_SEEDS,
    )
    assert report["status"] == "OK"
    assert report["scope"]["activation_merge_commit_sha"] == env.a2
    assert report["scope"]["governance_baseline_commit_sha"] == env.g2
    assert report["scope"]["expected_manifest_sha256"] == bundle_env.manifest_sha256
    assert report["bundle"]["manifest_sha256"] == bundle_env.manifest_sha256
    record = report["records"][0]
    assert record["all_exact_checks_passed"] is True
    assert record["lime"]["status"] == "ACCEPTABLE_LOCAL_APPROXIMATION"
    assert record["lime_weights_trusted"] is True


def test_tracked_registry_is_empty_until_a2_and_has_no_a2_field(
    activation_factory: Callable[..., Any],
) -> None:
    env = activation_factory()
    g2_literal = fx.committed_registry_literal(env.repo, env.g2)
    assert g2_literal == {}
    a2_literal = fx.committed_registry_literal(env.repo, env.a2)
    assert set(a2_literal) == {ds.DIAGNOSTIC_SCOPE_ID}
    assert env.a2 not in _committed_source(env.repo, env.a2)
    assert hashlib.sha256(
        subprocess.run(
            [
                "git",
                "show",
                f"{env.g2}:{ds.DIAGNOSTIC_GOVERNANCE_DOCUMENT_RELATIVE_PATH}",
            ],
            cwd=str(env.repo),
            capture_output=True,
            check=True,
        ).stdout
    ).hexdigest() == env.doc_sha


# --------------------------------------------------------------------------- #
# 2. Required negative cases on a genuine committed history
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("kwargs", "expected_code"),
    [
        (
            {"auth_overrides": {"activation_merge_commit_sha": "0" * 40}},
            "diagnostic_activation_revision_mismatch",
        ),
        (
            {"stale_head": True},
            "diagnostic_activation_revision_mismatch",
        ),
        (
            {"dirty_worktree": True},
            "diagnostic_worktree_not_clean",
        ),
        (
            {"extra_activation_file": True},
            "diagnostic_activation_diff_not_registry_only",
        ),
        (
            {"extra_registry_code": True},
            "diagnostic_registry_content_change_unapproved",
        ),
        (
            {"baseline_not_ancestor": True},
            "diagnostic_governance_ancestry_failed",
        ),
        (
            {
                "record_overrides": {"frozen_governance_document_sha256": "0" * 64},
                "auth_overrides": {"frozen_governance_document_sha256": "0" * 64},
            },
            "diagnostic_governance_document_hash_mismatch",
        ),
        (
            {"auth_overrides": {"scope_id": "FORGED-DIAGNOSTIC-SCOPE"}},
            "diagnostic_scope_id_mismatch",
        ),
        (
            {"auth_overrides": {"ratified_by": "FORGED RATIFIER"}},
            "diagnostic_scope_claim_mismatch",
        ),
        (
            {
                "auth_overrides": {
                    "bundle_identity": {"expected_manifest_sha256": "1" * 64}
                }
            },
            "diagnostic_scope_claim_mismatch",
        ),
        (
            {"preexisting_registry": True},
            "diagnostic_registry_baseline_not_empty",
        ),
        (
            {
                "record_overrides": {
                    "activation_merge_commit_sha": "0" * 40,
                }
            },
            "diagnostic_scope_registry_self_referential",
        ),
        (
            {"record_overrides": {"approved_code_revision": "0" * 40}},
            "diagnostic_scope_registry_self_referential",
        ),
    ],
)
def test_activation_negative_cases_on_committed_history(
    activation_factory: Callable[..., Any],
    kwargs: dict[str, Any],
    expected_code: str,
) -> None:
    env = activation_factory(**kwargs)
    with pytest.raises(ds.DiagnosticScopeError) as exc:
        ds.authorize_diagnostic_scope(
            env.auth,
            repo_root=env.repo,
            operator_confirmation=ds.DIAGNOSTIC_OPERATOR_CONFIRMATION,
        )
    assert exc.value.code == expected_code


def test_live_registry_injection_does_not_match_committed_registry(
    activation_factory: Callable[..., Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = activation_factory()
    live = dict(env.committed_literal)
    live["EXTRA_INJECTED_SCOPE"] = {"unauthorized": True}
    monkeypatch.setattr(ds, "RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES", live)
    with pytest.raises(ds.DiagnosticScopeError) as exc:
        ds.authorize_diagnostic_scope(
            env.auth,
            repo_root=env.repo,
            operator_confirmation=ds.DIAGNOSTIC_OPERATOR_CONFIRMATION,
        )
    assert exc.value.code == "diagnostic_registry_live_state_mismatch"


def test_governance_document_tampered_at_baseline_fails_closed(
    activation_factory: Callable[..., Any],
) -> None:
    env = activation_factory()
    # A separate G2 document hash in the local claim cannot override the record.
    auth = dict(env.auth)
    auth["frozen_governance_document_sha256"] = "f" * 64
    fx.write_private_json(env.auth_path, auth)
    with pytest.raises(ds.DiagnosticScopeError) as exc:
        ds.authorize_diagnostic_scope(
            auth,
            repo_root=env.repo,
            operator_confirmation=ds.DIAGNOSTIC_OPERATOR_CONFIRMATION,
        )
    assert exc.value.code == "diagnostic_scope_claim_mismatch"


def test_operator_confirmation_required_even_with_valid_committed_activation(
    activation_factory: Callable[..., Any],
) -> None:
    env = activation_factory()
    with pytest.raises(ds.DiagnosticScopeError) as exc:
        ds.authorize_diagnostic_scope(
            env.auth, repo_root=env.repo, operator_confirmation=None
        )
    assert exc.value.code == "diagnostic_operator_confirmation_required"


def test_authorization_file_schema_rejects_old_circular_field_names(
    activation_factory: Callable[..., Any],
) -> None:
    env = activation_factory()
    legacy = dict(env.auth)
    legacy.pop("governance_baseline_commit_sha")
    legacy.pop("approved_implementation_commit_sha")
    legacy["approved_code_revision"] = env.g2
    fx.write_private_json(env.auth_path, legacy)
    loaded = ds.load_diagnostic_authorization(env.auth_path, repo_root=env.repo)
    assert loaded == legacy
    with pytest.raises(ds.DiagnosticScopeError) as exc:
        ds.authorize_diagnostic_scope(
            loaded,
            repo_root=env.repo,
            operator_confirmation=ds.DIAGNOSTIC_OPERATOR_CONFIRMATION,
        )
    assert exc.value.code == "diagnostic_authorization_field_set_invalid"


def test_example_authorization_template_has_no_activation_revision_field() -> None:
    """The committed template may never contain a self-referential A2 field."""
    template = json.loads(
        (
            REPO_ROOT / "ai" / "examples" / "diagnostic_authorization.template.json"
        ).read_text(encoding="utf-8")
    )
    assert "approved_code_revision" not in template
    assert "governance_baseline_commit_sha" in template
    assert "approved_implementation_commit_sha" in template
    assert "activation_merge_commit_sha" in template
    assert "activation_registry_relative_path" in template
    # The template declares A2 as local-only evidence, not tracked ratification.
    assert template["activation_merge_commit_sha"] == "0" * 40
