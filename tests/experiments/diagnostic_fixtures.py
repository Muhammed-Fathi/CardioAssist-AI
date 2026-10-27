"""SYNTHETIC-ONLY fixture builders for the bounded diagnostic interface tests.

No real patient record, real dataset, real signing key, or real bundle is ever
read or created here. A "real-provenance accepted bundle" is simulated exactly
as in ``tests/experiments/test_ai_cli.py``: a synthetic model is trained in
memory, packaged with the existing secure packager, then its manifest is
re-signed with authorization-shaped metadata plus a post-run acceptance
sidecar. All model bytes remain the synthetic test model.

A "ratified scope" is simulated with a GENUINE committed I2 -> G2 -> A2 Git
history in a throwaway repository: the registry record is really written into
``ai/diagnostic_scope.py`` and committed at A2, and A2 is read from git only
after that commit exists. Nothing here is a human signature or approval.

Those throwaway histories are built identically in BOTH production lifecycle
states. The synthetic I2/G2 baseline registry is always constructed EXPLICITLY
EMPTY first, and only then is the synthetic A2 record written, so the same
genuine unactivated -> activated transition (and every negative control) is
exercised whether the checked-in production registry in the current checkout is
still empty or has already been activated by a registry-only commit. The
registry substitution reuses the production source parser, so the fixture can
never silently relax the "exactly one literal dict assignment" or the
"only the registry value changed" requirements.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
from typing import Any

import numpy as np

from ai.diagnostic_inference import DIAGNOSTIC_INPUT_SCHEMA_VERSION
from ai.diagnostic_scope import (
    _parse_committed_registry,
    _registry_value_span,
    DIAGNOSTIC_ACTIVATION_REGISTRY_RELATIVE_PATH,
    DIAGNOSTIC_AUTHORIZATION_SCHEMA_VERSION,
    DIAGNOSTIC_ALLOWED_OPERATIONS,
    DIAGNOSTIC_ATTESTATION_TOKENS,
    DIAGNOSTIC_GOVERNANCE_DOCUMENT_RELATIVE_PATH,
    DIAGNOSTIC_OPERATOR_CONFIRMATION,
    DIAGNOSTIC_SCOPE_ID,
    DIAGNOSTIC_TARGET_BUNDLE,
)
from ai.filesystem_security import ensure_private_directory, protect_private_file
from ai.packaging import (
    ATTESTATION_SCHEME,
    _compute_manifest_attestation_hmac,
    get_or_create_local_signing_key,
    package_research_bundle,
    write_bundle_acceptance_marker,
)
from ai.panels import DA_A2_RESTING_PANEL
from ai.training import (
    EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1,
    ResearchTrainingConfig,
    train_research_model,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

FAST_DIAGNOSTIC_CONFIG = ResearchTrainingConfig(
    protocol_id="CAI-D047-CLEVELAND-EXPLORATORY-V1",
    model_version="0.2.0",
    outer_folds=3,
    inner_folds=2,
    repeat_seeds=(20261027,),
    shuffle_control_seeds=(20261028,),
    shuffle_max_allowed_auroc=1.01,
    auc_simplicity_tolerance=1.0,  # deterministic LR selection in the fixture
    lr_c_grid=(10.0,),
    rf_max_depths=(2,),
    rf_min_samples_leaf=(5,),
    rf_n_estimators=10,
    bootstrap_resamples=20,
    shap_max_background_samples=20,
    execution_profile=EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1,
)

SYNTHETIC_GOVERNANCE_DOCUMENT = (
    "# SYNTHETIC TEST GOVERNANCE DOCUMENT (NOT A REAL RATIFICATION)\n\n"
    "This text exists only in a throwaway Git repository created by pytest.\n"
)


def make_synthetic_resting_cohort(
    n: int = 90, *, seed: int = 61061
) -> tuple[list[dict[str, Any]], list[int]]:
    """Five-field explicitly fabricated cohort with a linear CAD signal."""
    rng = np.random.default_rng(seed)
    records: list[dict[str, Any]] = []
    labels: list[int] = []
    for _ in range(n):
        age = float(rng.integers(35, 76))
        sex = int(rng.integers(0, 2))
        cp = int(rng.choice([1, 2, 3, 4]))
        trestbps = float(rng.integers(105, 175))
        restecg = int(rng.choice([0, 1, 2]))
        eta = (
            0.08 * (age - 55.0)
            + 1.1 * sex
            + (1.4 if cp == 4 else -0.6)
            + 0.025 * (trestbps - 135.0)
            + (0.5 if restecg == 1 else 0.0)
        )
        prob = 1.0 / (1.0 + np.exp(-eta))
        labels.append(int(rng.random() < prob))
        records.append(make_synthetic_record(age, sex, cp, trestbps, restecg))
    return records, labels


def make_synthetic_record(
    age: float = 54.0,
    sex: int = 1,
    cp: int = 3,
    trestbps: float = 132.0,
    restecg: int = 1,
) -> dict[str, Any]:
    return {
        "synthetic": True,
        "panel_id": DA_A2_RESTING_PANEL.panel_id,
        "features": {
            "age": age,
            "sex": sex,
            "cp": cp,
            "trestbps": trestbps,
            "restecg": restecg,
        },
        "units": {"age": "years", "trestbps": "mmHg"},
        "missing_reasons": {},
    }


def make_input_doc(records: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "schema_version": DIAGNOSTIC_INPUT_SCHEMA_VERSION,
        "synthetic": True,
        "input_declaration": {
            "origin": "EXPLICITLY_FABRICATED",
            "contains_patient_data": False,
            "panel_id": DA_A2_RESTING_PANEL.panel_id,
            "records_are_synthetic": True,
        },
        "records": list(records) if records is not None else [make_synthetic_record()],
    }


def write_private_json(path: Path, payload: Any, *, raw: str | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    ensure_private_directory(path.parent)
    path.write_text(
        raw if raw is not None else json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    protect_private_file(path)
    return path


def _resign_manifest(bundle_dir: Path, signing_key: bytes, mutate: Any) -> dict[str, Any]:
    manifest_path = bundle_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    note = manifest["local_producer_attestation"]["note"]
    mutate(manifest)
    core = {k: v for k, v in manifest.items() if k != "local_producer_attestation"}
    key_id, digest = _compute_manifest_attestation_hmac(core, signing_key)
    manifest["local_producer_attestation"] = {
        "scheme": ATTESTATION_SCHEME,
        "key_id": key_id,
        "hmac_sha256": digest,
        "note": note,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    protect_private_file(manifest_path)
    return manifest


def _simulate_accepted_real_provenance(manifest: dict[str, Any]) -> None:
    """Re-label a SYNTHETIC test bundle as accepted-real-provenance shaped."""
    target = DIAGNOSTIC_TARGET_BUNDLE
    manifest["eligibility"]["synthetic_only"] = False
    manifest["eligibility"]["execution_mode"] = "INTERNAL_EXPLORATORY_RESEARCH"
    manifest["research_authorization"] = {
        "governance_decision_id": "D-047",
        "dataset_id": target["expected_dataset_id"],
        "panel_id": target["expected_panel_id"],
        "experiment_type": "INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED",
        "source_relative_path": "SYNTHETIC_TEST_SIMULATION/not-a-real-source",
        "expected_source_sha256": target["expected_source_sha256"],
        "expected_source_row_count": 90,
        "authorized_by": "SYNTHETIC TEST SIMULATION - NO HUMAN SIGNATURE",
        "authorized_date": "2026-10-27",
        "signature_attestation": (
            "SYNTHETIC TEST SIMULATION ONLY - Gate PT P-3 CLOSED"
        ),
        "pinned_commit_sha": "a" * 40,
        "protocol_sha256": "b" * 64,
        "plan_sha256": "c" * 64,
        "dictionary_sha256": None,
        "allowed_operations": [],
        "forbidden_operations": [],
        "protected_output_root": "SYNTHETIC_TEST_SIMULATION",
        "model_packaging_authorized": True,
        "patient_shap_authorized": True,
    }
    manifest["model"]["model_id"] = target["expected_model_id"]
    manifest["model"]["model_version"] = target["expected_model_version"]
    manifest["model"]["protocol_id"] = target["expected_protocol_id"]
    manifest["model"]["selected_hyperparameters"] = {
        "C": target["expected_selected_c"]
    }


def make_simulated_accepted_bundle(
    tmp_path: Path, *, name: str | None = None, simulate_real: bool = True
) -> SimpleNamespace:
    """Train/package a synthetic D-047-profile bundle and simulate acceptance."""
    root = ensure_private_directory(tmp_path / "diagnostic_bundle_root")
    trusted_root = ensure_private_directory(root / "trusted_root")
    key_dir = ensure_private_directory(root / "private_keys")
    key_path = key_dir / "synthetic_local_bundle_hmac_v1.key"
    signing_key = get_or_create_local_signing_key(key_path)
    records, labels = make_synthetic_resting_cohort()
    run = train_research_model(
        records,
        labels,
        DA_A2_RESTING_PANEL,
        model_id=DIAGNOSTIC_TARGET_BUNDLE["expected_model_id"],
        development_cohort_id="synthetic_cleveland",
        development_dataset_id="DA-A2:synthetic_test",
        synthetic_data_confirmed=True,
        config=FAST_DIAGNOSTIC_CONFIG,
    )
    assert run.selected_model_family == "l2_logistic_regression"
    bundle_name = name or DIAGNOSTIC_TARGET_BUNDLE["expected_bundle_dir_name"]
    bundle_dir = trusted_root / bundle_name
    package_research_bundle(run, bundle_dir, signing_key=signing_key)
    if simulate_real:
        _resign_manifest(bundle_dir, signing_key, _simulate_accepted_real_provenance)
    write_bundle_acceptance_marker(
        bundle_dir,
        expected_source_sha256=DIAGNOSTIC_TARGET_BUNDLE["expected_source_sha256"],
        accepted_by="SYNTHETIC TEST SIMULATION - NO HUMAN SIGNATURE",
        detail="Synthetic post-run acceptance simulation for pytest only.",
    )
    manifest_sha256 = hashlib.sha256(
        (bundle_dir / "manifest.json").read_bytes()
    ).hexdigest()
    return SimpleNamespace(
        root=root,
        trusted_root=trusted_root,
        bundle_dir=bundle_dir,
        key_path=key_path,
        signing_key=signing_key,
        manifest_sha256=manifest_sha256,
        model_family=run.selected_model_family,
    )


def _deep_update(base: dict[str, Any], changes: dict[str, Any] | None) -> dict[str, Any]:
    out = deepcopy(base)
    for key, value in (changes or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_update(out[key], value)
        else:
            out[key] = value
    return out


def make_scope_record(
    *, manifest_sha256: str, g2: str, i2: str, doc_sha: str
) -> dict[str, Any]:
    """Tracked registry record: contains ONLY values known BEFORE A2 exists."""
    target = DIAGNOSTIC_TARGET_BUNDLE
    return {
        "governance_pr_number": 999,
        "governance_baseline_commit_sha": g2,
        "approved_implementation_commit_sha": i2,
        "governance_document_relative_path": (
            DIAGNOSTIC_GOVERNANCE_DOCUMENT_RELATIVE_PATH
        ),
        "frozen_governance_document_sha256": doc_sha,
        "ratified_by": "SYNTHETIC TEST SIMULATION - NOT A MAINTAINER",
        "ratification_comment_exact": "SYNTHETIC-TEST-SCOPE-COMMENT",
        "approved_operations": DIAGNOSTIC_ALLOWED_OPERATIONS,
        "expected_manifest_sha256": manifest_sha256,
        "expected_bundle_dir_name": target["expected_bundle_dir_name"],
        "expected_source_sha256": target["expected_source_sha256"],
        "expected_dataset_id": target["expected_dataset_id"],
        "expected_panel_id": target["expected_panel_id"],
        "expected_execution_profile": target["expected_execution_profile"],
        "expected_model_family": target["expected_model_family"],
        "expected_selected_c": target["expected_selected_c"],
        "expected_model_id": target["expected_model_id"],
        "expected_protocol_id": target["expected_protocol_id"],
        "expected_model_version": target["expected_model_version"],
    }


def make_authorization_doc(
    *, manifest_sha256: str, g2: str, i2: str, a2: str, doc_sha: str
) -> dict[str, Any]:
    """Ignored local operator authorization: A2 is known only AFTER the merge."""
    target = DIAGNOSTIC_TARGET_BUNDLE
    attestation = "_".join(DIAGNOSTIC_ATTESTATION_TOKENS)
    return {
        "schema_version": DIAGNOSTIC_AUTHORIZATION_SCHEMA_VERSION,
        "authorization_status": "AUTHORIZED_BY_LOCAL_OPERATOR",
        "scope_id": DIAGNOSTIC_SCOPE_ID,
        "governance_pr_number": 999,
        "governance_baseline_commit_sha": g2,
        "approved_implementation_commit_sha": i2,
        "activation_merge_commit_sha": a2,
        "activation_registry_relative_path": (
            DIAGNOSTIC_ACTIVATION_REGISTRY_RELATIVE_PATH
        ),
        "governance_document_relative_path": (
            DIAGNOSTIC_GOVERNANCE_DOCUMENT_RELATIVE_PATH
        ),
        "frozen_governance_document_sha256": doc_sha,
        "ratified_by": "SYNTHETIC TEST SIMULATION - NOT A MAINTAINER",
        "ratification_comment_exact": "SYNTHETIC-TEST-SCOPE-COMMENT",
        "approved_operations": list(DIAGNOSTIC_ALLOWED_OPERATIONS),
        "supervisor_signoff_claimed": False,
        "human_attestation": f"SYNTHETIC TEST SIMULATION: {attestation}",
        "bundle_identity": {
            "bundle_dir_name": target["expected_bundle_dir_name"],
            "expected_manifest_sha256": manifest_sha256,
            "expected_source_sha256": target["expected_source_sha256"],
            "expected_dataset_id": target["expected_dataset_id"],
            "expected_panel_id": target["expected_panel_id"],
            "expected_model_family": target["expected_model_family"],
            "expected_execution_profile": target["expected_execution_profile"],
            "expected_selected_c": target["expected_selected_c"],
        },
        "input_declaration": {
            "origin": "EXPLICITLY_FABRICATED",
            "contains_patient_data": False,
            "panel_id": target["expected_panel_id"],
            "records_are_synthetic": True,
        },
        "execution_boundary": {
            "offline_only": True,
            "api_serving": False,
            "telemetry": False,
            "uploads": False,
            "writes_bundle": False,
            "retraining_or_tuning": False,
            "patient_data_inputs": False,
        },
        "local_signer": "SYNTHETIC TEST SIMULATION - NO HUMAN SIGNATURE",
        "local_signed_at_iso8601": "2026-10-27T00:00:00+00:00",
        "local_signature_attestation": (
            f"SYNTHETIC TEST SIMULATION ONLY: {attestation}"
        ),
        "operator_confirmation": DIAGNOSTIC_OPERATOR_CONFIRMATION,
    }


def _write_registry_source(repo: Path, source: str) -> None:
    path = repo / DIAGNOSTIC_ACTIVATION_REGISTRY_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def _with_registry_dict(source: str, registry: dict[str, Any]) -> str:
    """Return ``source`` with ONLY the trusted-registry literal value replaced.

    The value span is located by the PRODUCTION parser
    (:func:`ai.diagnostic_scope._registry_value_span`), so this fixture
    inherits — instead of re-implementing — the exact guarantees the runtime
    activation gate depends on:

    * the source must be parseable Python holding **exactly one** top-level
      **literal ``dict``** assignment to
      ``RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES`` (``Assign`` or ``AnnAssign``);
      a computed value, a second assignment, or a missing symbol raises
      ``diagnostic_registry_source_unparsable``;
    * only the value bytes are substituted, so every other byte of the module
      (imports, comments, docstrings, guards, ``__all__``) is untouched and the
      production masked-source equality check still holds between the synthetic
      baseline and the synthetic activation commit.

    Unlike the previous empty-only regex, this works whether the checked-in
    production registry is EMPTY (an unactivated ``I``/``G`` baseline) or
    already POPULATED (an activated ``A`` revision), so the synthetic
    ``I2 -> G2 -> A2`` history can be built in both lifecycle states.
    """
    raw = source.encode("utf-8")
    _value, start, end = _registry_value_span(raw)
    replaced = raw[:start] + repr(dict(registry)).encode("utf-8") + raw[end:]
    new_source = replaced.decode("utf-8")
    # Self-check with the production parser: the substitution must read back as
    # exactly the requested plain literal registry, and nothing else moved.
    literal, masked = _parse_committed_registry(replaced)
    _original_literal, original_masked = _parse_committed_registry(raw)
    assert literal == dict(registry), (
        "the fixture must write a plain literal registry the production parser "
        "reads back unchanged"
    )
    assert masked == original_masked, (
        "the fixture must change ONLY the registry value, never other code"
    )
    return new_source


def _with_registry_record(source: str, record: dict[str, Any]) -> str:
    return _with_registry_dict(source, {DIAGNOSTIC_SCOPE_ID: record})


def committed_registry_source_literal(source: str) -> dict[str, Any]:
    """Parse the registry literal out of module SOURCE with the production parser."""
    literal, _masked = _parse_committed_registry(source.encode("utf-8"))
    return literal


def committed_registry_literal(repo: Path, revision: str) -> dict[str, Any]:
    """Parse the ACTUAL committed registry literal with the production parser."""
    proc = subprocess.run(
        [
            "git",
            "show",
            f"{revision}:{DIAGNOSTIC_ACTIVATION_REGISTRY_RELATIVE_PATH}",
        ],
        cwd=str(repo),
        capture_output=True,
        check=True,
    )
    literal, _masked = _parse_committed_registry(proc.stdout)
    return literal


def build_activation_repo(
    tmp_path: Path,
    *,
    manifest_sha256: str,
    doc_text: str = SYNTHETIC_GOVERNANCE_DOCUMENT,
    record_overrides: dict[str, Any] | None = None,
    auth_overrides: dict[str, Any] | None = None,
    baseline_not_ancestor: bool = False,
    extra_activation_file: bool = False,
    extra_registry_code: bool = False,
    preexisting_registry: bool = False,
    stale_head: bool = False,
    dirty_worktree: bool = False,
) -> SimpleNamespace:
    """Create a GENUINE committed I2 -> G2 -> A2 activation history.

    I2 freezes a copy of the reviewed implementation whose trusted registry is
    EXPLICITLY EMPTY, G2 adds only documentation (the ratified governance
    document) and keeps that empty registry, and A2 changes ONLY the single
    registry literal inside ``ai/diagnostic_scope.py`` from ``{}`` to exactly
    one record. A2 is read from git AFTER the commit exists and is placed ONLY
    in the ignored local operator authorization document. Nothing is
    self-referential.

    The empty I2/G2 baseline is constructed explicitly rather than copied from
    the checkout, so this builder reproduces the same genuine
    unactivated -> activated transition whether the production registry in the
    current checkout is empty (before activation) or already populated (after
    it). ``preexisting_registry=True`` remains the negative control that proves
    a NON-empty baseline is refused.
    """
    repo = Path(tmp_path) / "diagnostic_activation_repo"
    repo.mkdir(parents=True, exist_ok=True)

    def git(*args: str) -> str:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(repo),
            capture_output=True,
            text=True,
            check=True,
        )
        return proc.stdout.strip()

    git("init")
    git("config", "user.name", "Synthetic Test Runner")
    git("config", "user.email", "synthetic@example.test")
    (repo / ".gitignore").write_text(
        "data/\n__pycache__/\n*.pyc\n", encoding="utf-8"
    )
    original_source = (
        REPO_ROOT / DIAGNOSTIC_ACTIVATION_REGISTRY_RELATIVE_PATH
    ).read_text(encoding="utf-8")
    # Step 1: the synthetic IMPLEMENTATION/GOVERNANCE baseline is always built
    # with an EXPLICITLY EMPTY trusted registry, whatever the checked-in
    # production registry holds in this checkout. The production gate requires
    # ``baseline_literal == {}`` at G2, so the synthetic history must start from
    # the unactivated state even when the real repository is already activated.
    unactivated_source = _with_registry_dict(original_source, {})
    assert (
        committed_registry_source_literal(unactivated_source) == {}
    ), "the synthetic I2/G2 baseline registry must be explicitly empty"
    preexisting_scope = {"PREEXISTING_SCOPE": {"unauthorized": True}}
    baseline_source = (
        _with_registry_dict(unactivated_source, preexisting_scope)
        if preexisting_registry
        else unactivated_source
    )
    _write_registry_source(repo, baseline_source)
    inference_source = (REPO_ROOT / "ai" / "diagnostic_inference.py").read_text(
        encoding="utf-8"
    )
    (repo / "ai" / "diagnostic_inference.py").write_text(
        inference_source, encoding="utf-8"
    )
    (repo / "README.md").write_text(
        "synthetic approved diagnostic implementation I2\n", encoding="utf-8"
    )
    git("add", ".")
    git("commit", "-m", "I2: approved diagnostic implementation (synthetic)")
    i2 = git("rev-parse", "HEAD").lower()

    # G2: governance baseline; only documentation changes after I2.
    doc_path = repo / DIAGNOSTIC_GOVERNANCE_DOCUMENT_RELATIVE_PATH
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text(doc_text, encoding="utf-8")
    decisions = repo / "docs" / "DECISIONS.md"
    decisions.write_text("synthetic D-049 proposal (test only)\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-m", "G2: ratified governance document (synthetic)")
    g2 = git("rev-parse", "HEAD").lower()
    doc_sha = hashlib.sha256(doc_text.encode("utf-8")).hexdigest()

    # A dangling root commit exists in the object DB but is NOT an ancestor of
    # HEAD; used to prove genuine ancestry checking (not just object existence).
    tree_sha = git("write-tree")
    dangling = subprocess.run(
        ["git", "commit-tree", tree_sha, "-m", "unrelated dangling root"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip().lower()

    claimed_g2 = dangling if baseline_not_ancestor else g2
    claimed_i2 = dangling if baseline_not_ancestor else i2
    record = _deep_update(
        make_scope_record(
            manifest_sha256=manifest_sha256,
            g2=claimed_g2,
            i2=claimed_i2,
            doc_sha=doc_sha,
        ),
        record_overrides,
    )

    # A2: registry-only change, using ONLY previously known I2/G2/doc/digest.
    activated_registry: dict[str, Any] = {}
    if preexisting_registry:
        activated_registry.update(preexisting_scope)
    activated_registry[DIAGNOSTIC_SCOPE_ID] = record
    # Step 2: the synthetic ACTIVATION commit is built FROM that empty baseline
    # and changes nothing but the registry literal value.
    activated_source = _with_registry_dict(baseline_source, activated_registry)
    if extra_registry_code:
        activated_source += "\n# UNAPPROVED SECURITY LOGIC CHANGE\n"
    _write_registry_source(repo, activated_source)
    if extra_activation_file:
        (repo / "ai" / "diagnostic_inference.py").write_text(
            inference_source + "\n# UNAPPROVED INFERENCE CHANGE\n",
            encoding="utf-8",
        )
    git("add", ".")
    git("commit", "-m", "A2: registry-only diagnostic scope activation (synthetic)")
    a2 = git("rev-parse", "HEAD").lower()  # obtained AFTER the commit exists
    committed_literal = committed_registry_literal(repo, a2)

    auth = _deep_update(
        make_authorization_doc(
            manifest_sha256=manifest_sha256,
            g2=claimed_g2,
            i2=claimed_i2,
            a2=a2,
            doc_sha=doc_sha,
        ),
        auth_overrides,
    )
    auth_path = write_private_json(
        repo / "data" / "diagnostics" / "diagnostic_authorization.json", auth
    )

    if stale_head:
        git("reset", "--hard", g2)
    if dirty_worktree:
        (repo / "README.md").write_text("dirty tracked file\n", encoding="utf-8")

    return SimpleNamespace(
        repo=repo,
        i2=i2,
        g2=g2,
        a2=a2,
        dangling=dangling,
        head=git("rev-parse", "HEAD").lower(),
        doc_sha=doc_sha,
        doc_path=doc_path,
        record=record,
        auth=auth,
        auth_path=auth_path,
        committed_literal=committed_literal,
        baseline_source=baseline_source,
        activated_source=activated_source,
    )
