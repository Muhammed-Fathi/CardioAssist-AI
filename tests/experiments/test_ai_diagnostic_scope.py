"""Independent scope-authorization regressions for bounded offline diagnostics.

SYNTHETIC TEST SIMULATIONS ONLY. No real bundle, dataset, patient record,
maintainer comment, or human signature is present. Git evidence is produced by
``diagnostic_fixtures.build_activation_repo`` as a genuine committed I2 -> G2 ->
A2 history; the dedicated feasibility suite in
``test_ai_diagnostic_activation_feasibility.py`` owns the full-history cases.

The production trusted registry is asserted LIFECYCLE-COHERENT rather than
empty: it must equal the literal registry committed in this checkout and hold at
most the single reviewed scope, and the fail-closed behaviour of the UNACTIVATED
(empty) and ACTIVATED (one record) states is each proven explicitly, so these
regressions are valid both before and after a registry-only activation commit.
"""
from __future__ import annotations

import ast
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace
from typing import Any, Callable

import pytest

from ai import diagnostic_inference as di
from ai import diagnostic_scope as ds
from ai.execution import RATIFIED_OPERATIONAL_SCOPE_AMENDMENTS
from ai.panels import DA_A2_RESTING_PANEL
from tests.experiments import diagnostic_fixtures as fx

REPO_ROOT = Path(__file__).resolve().parents[2]
SYNTHETIC_MANIFEST_SHA256 = "a" * 64


@pytest.fixture(scope="module")
def activation_env(tmp_path_factory: pytest.TempPathFactory) -> SimpleNamespace:
    return fx.build_activation_repo(
        tmp_path_factory.mktemp("diag_scope_activation"),
        manifest_sha256=SYNTHETIC_MANIFEST_SHA256,
    )


@pytest.fixture(scope="module")
def bundle_env(tmp_path_factory: pytest.TempPathFactory) -> SimpleNamespace:
    return fx.make_simulated_accepted_bundle(
        tmp_path_factory.mktemp("diag_scope_bundle")
    )


@pytest.fixture
def activated(
    monkeypatch: pytest.MonkeyPatch, activation_env: SimpleNamespace
) -> SimpleNamespace:
    """Install the EXACT committed A2 registry as the in-process registry."""
    monkeypatch.setattr(
        ds,
        "RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES",
        deepcopy(activation_env.committed_literal),
    )
    return activation_env


def _auth(env: SimpleNamespace) -> dict[str, Any]:
    return fx.make_authorization_doc(
        manifest_sha256=SYNTHETIC_MANIFEST_SHA256,
        g2=env.g2,
        i2=env.i2,
        a2=env.a2,
        doc_sha=env.doc_sha,
    )


def _record(env: SimpleNamespace) -> dict[str, Any]:
    return fx.make_scope_record(
        manifest_sha256=SYNTHETIC_MANIFEST_SHA256,
        g2=env.g2,
        i2=env.i2,
        doc_sha=env.doc_sha,
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
# 1. Production registry lifecycle: unactivated AND activated states
# --------------------------------------------------------------------------- #


def _checked_in_registry_literal() -> dict[str, Any]:
    """Trusted-registry literal in the CHECKED-IN source of this checkout."""
    source = (REPO_ROOT / ds.DIAGNOSTIC_ACTIVATION_REGISTRY_RELATIVE_PATH).read_bytes()
    literal, _masked = ds._parse_committed_registry(source)
    return literal


@pytest.fixture
def registry_state(
    monkeypatch: pytest.MonkeyPatch, activation_env: SimpleNamespace
) -> Callable[[str], dict[str, Any]]:
    """Install one trusted-registry lifecycle state and return that registry.

    ``production`` is whatever this checkout really contains (empty before a
    registry-only activation, exactly one reviewed record after it);
    ``unactivated`` and ``activated_synthetic`` pin the two states explicitly so
    every lifecycle property below is proven in BOTH states, in every checkout,
    without depending on the production state and without weakening any gate.
    The activation state comes from a GENUINE committed synthetic A2 registry.
    """

    def install(state: str) -> dict[str, Any]:
        if state == "production":
            registry: dict[str, Any] = dict(ds.RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES)
        elif state == "unactivated":
            registry = {}
        elif state == "activated_synthetic":
            registry = deepcopy(activation_env.committed_literal)
        else:
            raise AssertionError(f"unknown registry lifecycle state {state!r}")
        monkeypatch.setattr(ds, "RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES", registry)
        return registry

    return install


def test_production_registry_equals_checked_in_source_and_is_scope_bounded() -> None:
    """Invariant that holds BEFORE and AFTER a registry-only activation.

    The in-process trusted registry must equal the literal registry committed in
    this checkout (no runtime injection), must never carry an unknown scope and,
    once activated, must hold exactly the single reviewed record that the
    production defence-in-depth validator accepts, bound to the frozen governance
    document path and to baselines that are NOT the frozen training ``G``/``A``.
    """
    registry = ds.RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES
    assert dict(registry) == _checked_in_registry_literal()
    assert set(registry) <= {ds.DIAGNOSTIC_SCOPE_ID}
    if not registry:
        return  # unactivated: the fail-closed proofs below cover this state
    record = ds._validated_trusted_record(
        registry[ds.DIAGNOSTIC_SCOPE_ID], scope_id=ds.DIAGNOSTIC_SCOPE_ID
    )
    assert tuple(record["approved_operations"]) == ds.DIAGNOSTIC_ALLOWED_OPERATIONS
    assert record["governance_document_relative_path"] == (
        ds.DIAGNOSTIC_GOVERNANCE_DOCUMENT_RELATIVE_PATH
    )
    frozen_training = {ds.FROZEN_TRAINING_REVISION_A, ds.FROZEN_GOVERNANCE_MERGE_G}
    assert record["governance_baseline_commit_sha"] not in frozen_training
    assert record["approved_implementation_commit_sha"] not in frozen_training
    for forbidden in (
        "approved_code_revision",
        "activation_merge_commit_sha",
        "activation_revision_commit_sha",
    ):
        assert forbidden not in record, "A2 must never be tracked (circular SHA)"


def test_unactivated_registry_fails_closed_before_any_bundle_work(
    registry_state: Callable[[str], dict[str, Any]],
    activation_env: SimpleNamespace,
    bundle_env: SimpleNamespace,
    tmp_path: Path,
) -> None:
    """EMPTY registry: refused before any bundle verification or deserialization."""
    assert registry_state("unactivated") == {}
    with pytest.raises(ds.DiagnosticScopeError) as exc:
        ds.validate_diagnostic_scope(
            {"scope_id": ds.DIAGNOSTIC_SCOPE_ID}, repo_root=activation_env.repo
        )
    assert exc.value.code == "diagnostic_scope_not_ratified"

    # Even a perfectly shaped local authorization + synthetic input cannot open
    # the interface while the independent registry is empty; no bundle check,
    # deserialization, or inference is reached.
    auth_path = fx.write_private_json(
        tmp_path / "private" / "authorization.json", _auth(activation_env)
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
                repo_root=activation_env.repo,
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


def test_activated_registry_still_enforces_authorization_and_git_evidence(
    registry_state: Callable[[str], dict[str, Any]],
    activation_env: SimpleNamespace,
    bundle_env: SimpleNamespace,
    tmp_path: Path,
) -> None:
    """POPULATED registry: no bypass of authorization, Git-history or bundle gates."""
    registry = registry_state("activated_synthetic")
    assert set(registry) == {ds.DIAGNOSTIC_SCOPE_ID}

    # 1. A ratified scope never ratifies a DIFFERENT one.
    with pytest.raises(ds.DiagnosticScopeError) as unknown:
        ds.validate_diagnostic_scope(
            {"scope_id": "CAI-SCOPE-NOT-RATIFIED-BY-ANYONE"},
            repo_root=activation_env.repo,
        )
    assert unknown.value.code == "diagnostic_scope_not_ratified"

    # 2. A bare scope id is not authorization: every local claim is still
    #    compared field-for-field against the reviewed record.
    with pytest.raises(ds.DiagnosticScopeError) as bare:
        ds.validate_diagnostic_scope(
            {"scope_id": ds.DIAGNOSTIC_SCOPE_ID}, repo_root=activation_env.repo
        )
    assert bare.value.code == "diagnostic_scope_claim_mismatch"

    # 3. The Git-history binding still applies: a wrong/stale activation
    #    revision is refused against independently resolved HEAD.
    with pytest.raises(ds.DiagnosticScopeError) as stale:
        ds.validate_diagnostic_scope(
            _deep_update(
                _auth(activation_env), {"activation_merge_commit_sha": "0" * 40}
            ),
            repo_root=activation_env.repo,
        )
    assert stale.value.code == "diagnostic_activation_revision_mismatch"

    # 4. The exact operator confirmation phrase is still required first.
    with pytest.raises(ds.DiagnosticScopeError) as no_confirmation:
        ds.authorize_diagnostic_scope(
            _auth(activation_env),
            repo_root=activation_env.repo,
            operator_confirmation=None,
        )
    assert no_confirmation.value.code == "diagnostic_operator_confirmation_required"

    # 5. A forged ratifier or a substituted bundle digest is refused BEFORE any
    #    bundle verification or deserialization is attempted.
    called: list[bool] = []

    def _boom(*_args: Any, **_kwargs: Any) -> Any:
        called.append(True)
        raise AssertionError("bundle verification must not run for a refused scope")

    for changes in (
        {"ratified_by": "FORGED RATIFIER"},
        {"bundle_identity": {"expected_manifest_sha256": "1" * 64}},
    ):
        auth = _deep_update(_auth(activation_env), changes)
        auth_path = fx.write_private_json(
            tmp_path / "activated" / "authorization.json", auth
        )
        input_path = fx.write_private_json(
            tmp_path / "activated" / "input.json", fx.make_input_doc()
        )
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
                    repo_root=activation_env.repo,
                )
            assert run_exc.value.code == "diagnostic_scope_claim_mismatch"
        finally:
            di.verify_trusted_local_bundle = original  # type: ignore[assignment]
    assert called == []


@pytest.mark.parametrize(
    "state", ["production", "unactivated", "activated_synthetic"]
)
def test_unknown_and_bare_scopes_fail_closed_in_every_registry_state(
    state: str,
    registry_state: Callable[[str], dict[str, Any]],
    activation_env: SimpleNamespace,
) -> None:
    """Unratified scopes are refused whatever the lifecycle state of the registry."""
    installed = registry_state(state)
    with pytest.raises(ds.DiagnosticScopeError) as unknown:
        ds.validate_diagnostic_scope(
            {"scope_id": "CAI-SCOPE-NOT-RATIFIED-BY-ANYONE"},
            repo_root=activation_env.repo,
        )
    assert unknown.value.code == "diagnostic_scope_not_ratified"

    # A bare scope id fails closed in every state: at the ratification gate while
    # unactivated, at the claim-comparison gate once a record is registered.
    with pytest.raises(ds.DiagnosticScopeError) as bare:
        ds.validate_diagnostic_scope(
            {"scope_id": ds.DIAGNOSTIC_SCOPE_ID}, repo_root=activation_env.repo
        )
    assert bare.value.code == (
        "diagnostic_scope_claim_mismatch"
        if installed
        else "diagnostic_scope_not_ratified"
    )


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
        "age", "sex", "cp", "trestbps", "restecg"
    )
    assert len(ds.DIAGNOSTIC_TARGET_BUNDLE["expected_ordered_feature_names"]) == 5
    assert ds.DIAGNOSTIC_INTERFACE_VERSION == (
        "cardioassist.ai.bounded_offline_diagnostic_inference/v1.1"
    )
    assert ds.DIAGNOSTIC_AUTHORIZATION_SCHEMA_VERSION == (
        "cardioassist.ai.diagnostic_authorization/v1.1"
    )


def test_activation_template_has_no_self_referential_revision_field() -> None:
    template = ds.DIAGNOSTIC_SCOPE_ACTIVATION_TEMPLATE
    assert "governance_baseline_commit_sha" in template
    assert "approved_implementation_commit_sha" in template
    assert "governance_document_relative_path" in template
    assert "frozen_governance_document_sha256" in template
    assert "expected_manifest_sha256" in template
    assert "approved_operations" in template
    for forbidden in (
        "approved_code_revision",
        "activation_merge_commit_sha",
        "activation_revision_commit_sha",
    ):
        assert forbidden not in template, (
            f"tracked template must never contain {forbidden} (A2 circular SHA)"
        )
    assert template["governance_baseline_commit_sha"] is None
    assert template["approved_implementation_commit_sha"] is None
    assert template["expected_manifest_sha256"] is None
    assert (
        ds.DIAGNOSTIC_ACTIVATION_REGISTRY_RELATIVE_PATH
        == "ai/diagnostic_scope.py"
    )


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
    activation_env: SimpleNamespace,
) -> None:
    ds.validate_local_authorization(
        _auth(activation_env),
        operator_confirmation=ds.DIAGNOSTIC_OPERATOR_CONFIRMATION,
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
        ({"governance_baseline_commit_sha": "xyz"}, "diagnostic_git_evidence_malformed"),
        ({"approved_implementation_commit_sha": "abc"}, "diagnostic_git_evidence_malformed"),
        ({"activation_merge_commit_sha": "def"}, "diagnostic_git_evidence_malformed"),
        ({"governance_pr_number": 0}, "diagnostic_git_evidence_malformed"),
        ({"activation_registry_relative_path": "ai/other.py"}, "diagnostic_activation_registry_path_mismatch"),
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
    activation_env: SimpleNamespace,
    changes: dict[str, Any],
    expected_code: str,
) -> None:
    doc = _deep_update(_auth(activation_env), changes)
    with pytest.raises(ds.DiagnosticScopeError) as exc:
        ds.validate_local_authorization(
            doc, operator_confirmation=ds.DIAGNOSTIC_OPERATOR_CONFIRMATION
        )
    assert exc.value.code == expected_code


def test_activation_revision_must_be_distinct_from_the_two_baselines(
    activation_env: SimpleNamespace,
) -> None:
    doc = _deep_update(
        _auth(activation_env),
        {"activation_merge_commit_sha": activation_env.g2},
    )
    with pytest.raises(ds.DiagnosticScopeError) as exc:
        ds.validate_local_authorization(
            doc, operator_confirmation=ds.DIAGNOSTIC_OPERATOR_CONFIRMATION
        )
    assert exc.value.code == "diagnostic_activation_revision_malformed"


def test_local_authorization_requires_explicit_confirmation_argument(
    activation_env: SimpleNamespace,
) -> None:
    with pytest.raises(ds.DiagnosticScopeError) as exc:
        ds.validate_local_authorization(
            _auth(activation_env), operator_confirmation=None
        )
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
    activation_env: SimpleNamespace,
) -> None:
    unignored = fx.write_private_json(
        activation_env.repo / "unignored_authorization.json",
        _auth(activation_env),
    )
    with pytest.raises(ds.DiagnosticScopeError) as exc:
        ds.load_diagnostic_authorization(unignored, repo_root=activation_env.repo)
    assert exc.value.code == "diagnostic_local_file_not_git_ignored"
    ignored = fx.write_private_json(
        activation_env.repo / "data" / "diagnostics" / "ignored_authorization.json",
        _auth(activation_env),
    )
    assert ds.load_diagnostic_authorization(ignored, repo_root=activation_env.repo)


# --------------------------------------------------------------------------- #
# 3. Independent ratification and trusted-record validation
# --------------------------------------------------------------------------- #


def test_ratified_scope_happy_path_returns_exact_bindings(
    activated: SimpleNamespace,
) -> None:
    context = ds.authorize_diagnostic_scope(
        _auth(activated),
        repo_root=activated.repo,
        operator_confirmation=ds.DIAGNOSTIC_OPERATOR_CONFIRMATION,
    )
    assert context.scope_id == ds.DIAGNOSTIC_SCOPE_ID
    assert context.governance_baseline_commit_sha == activated.g2
    assert context.approved_implementation_commit_sha == activated.i2
    assert context.activation_merge_commit_sha == activated.a2
    assert context.approved_operations == ds.DIAGNOSTIC_ALLOWED_OPERATIONS
    assert context.expected_manifest_sha256 == SYNTHETIC_MANIFEST_SHA256
    assert context.expected_source_sha256 == (
        ds.DIAGNOSTIC_TARGET_BUNDLE["expected_source_sha256"]
    )
    assert context.expected_selected_c == 10.0
    assert context.identity()["activation_registry_relative_path"] == (
        ds.DIAGNOSTIC_ACTIVATION_REGISTRY_RELATIVE_PATH
    )


@pytest.mark.parametrize(
    ("auth_changes", "expected_code"),
    [
        ({"ratified_by": "someone-else"}, "diagnostic_scope_claim_mismatch"),
        ({"ratification_comment_exact": "different"}, "diagnostic_scope_claim_mismatch"),
        ({"governance_pr_number": 1}, "diagnostic_scope_claim_mismatch"),
        ({"governance_baseline_commit_sha": "0" * 40}, "diagnostic_scope_claim_mismatch"),
        ({"approved_implementation_commit_sha": "0" * 40}, "diagnostic_scope_claim_mismatch"),
        ({"activation_registry_relative_path": "ai/other.py"}, "diagnostic_scope_claim_mismatch"),
        ({"bundle_identity": {"expected_manifest_sha256": "0" * 64}}, "diagnostic_scope_claim_mismatch"),
        ({"frozen_governance_document_sha256": "0" * 64}, "diagnostic_scope_claim_mismatch"),
    ],
)
def test_manifest_claims_cannot_override_trusted_record(
    monkeypatch: pytest.MonkeyPatch,
    activated: SimpleNamespace,
    auth_changes: dict[str, Any],
    expected_code: str,
) -> None:
    _install_registry(monkeypatch, _record(activated))
    doc = _deep_update(_auth(activated), auth_changes)
    with pytest.raises(ds.DiagnosticScopeError) as exc:
        ds.validate_diagnostic_scope(doc, repo_root=activated.repo)
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
        ({"governance_baseline_commit_sha": "PLACEHOLDER"}, "diagnostic_scope_registry_entry_invalid"),
        ({"approved_implementation_commit_sha": "PLACEHOLDER"}, "diagnostic_scope_registry_entry_invalid"),
        ({"ratified_by": ""}, "diagnostic_scope_registry_entry_invalid"),
        ({"expected_model_id": "another-model"}, "diagnostic_scope_registry_entry_invalid"),
        ({"activation_merge_commit_sha": "0" * 40}, "diagnostic_scope_registry_self_referential"),
        ({"approved_code_revision": "0" * 40}, "diagnostic_scope_registry_self_referential"),
        ({"activation_revision_commit_sha": "0" * 40}, "diagnostic_scope_registry_self_referential"),
        ({"governance_baseline_commit_sha": ds.FROZEN_TRAINING_REVISION_A}, "diagnostic_scope_reuses_training_activation"),
        ({"approved_implementation_commit_sha": ds.FROZEN_GOVERNANCE_MERGE_G}, "diagnostic_scope_reuses_training_activation"),
    ],
)
def test_trusted_record_cannot_bind_a_different_bundle_or_operation(
    monkeypatch: pytest.MonkeyPatch,
    activation_env: SimpleNamespace,
    record_changes: dict[str, Any],
    expected_code: str,
) -> None:
    record = _deep_update(_record(activation_env), record_changes)
    _install_registry(monkeypatch, record)
    with pytest.raises(ds.DiagnosticScopeError) as exc:
        ds.validate_diagnostic_scope(
            _auth(activation_env), repo_root=activation_env.repo
        )
    assert exc.value.code == expected_code


def test_registry_source_parser_rejects_computed_or_duplicate_assignments() -> None:
    """The committed activation record must be a single plain literal dict."""
    good = (
        b"RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES: dict[str, dict[str, Any]] = {}\n"
    )
    literal, masked = ds._parse_committed_registry(good)
    assert literal == {} and masked != good
    activated_src = (
        b"RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES: dict[str, dict[str, Any]] = "
        b"{'SCOPE': {'op': 'x'}}\n"
    )
    literal2, masked2 = ds._parse_committed_registry(activated_src)
    assert literal2 == {"SCOPE": {"op": "x"}}
    assert masked == masked2, "only the literal value may differ between G2 and A2"

    with pytest.raises(ds.DiagnosticScopeError) as computed:
        ds._parse_committed_registry(
            b"RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES = dict(SCOPE={'op': 'x'})\n"
        )
    assert computed.value.code in {
        "diagnostic_registry_source_unparsable",
        "diagnostic_registry_literal_invalid",
    }
    with pytest.raises(ds.DiagnosticScopeError) as duplicate:
        ds._parse_committed_registry(good + good)
    assert duplicate.value.code == "diagnostic_registry_source_unparsable"


def test_gitignore_and_changelog_keep_activation_registry_only(
    activation_env: SimpleNamespace,
) -> None:
    """Only an activation commit populates the registry; A2 stays out of Git.

    Valid in both lifecycle states: the real checked-in registry is either still
    empty (unactivated) or holds exactly the one reviewed scope, and the
    synthetic committed history always shows the empty G2 baseline becoming
    exactly one record at A2. The private local operator authorization that is
    the ONLY place A2 may live stays Git-ignored in the real checkout.
    """
    checked_in = _checked_in_registry_literal()
    assert dict(ds.RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES) == checked_in
    assert set(checked_in) <= {ds.DIAGNOSTIC_SCOPE_ID}
    committed_at_a2 = fx.committed_registry_literal(activation_env.repo, activation_env.a2)
    assert set(committed_at_a2) == {ds.DIAGNOSTIC_SCOPE_ID}
    assert fx.committed_registry_literal(activation_env.repo, activation_env.g2) == {}
    ignored = subprocess.run(
        [
            "git",
            "check-ignore",
            "-q",
            "--",
            "data/diagnostics/diagnostic_authorization.json",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        check=False,
    )
    assert ignored.returncode == 0, (
        "the local operator authorization carrying A2 must remain Git-ignored"
    )


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
