"""SYNTHETIC-ONLY fixture builders for the bounded diagnostic interface tests.

No real patient record, real dataset, real signing key, or real bundle is ever
read or created here. A "real-provenance accepted bundle" is simulated exactly
as in ``tests/experiments/test_ai_cli.py``: a synthetic model is trained in
memory, packaged with the existing secure packager, then its manifest is
re-signed with authorization-shaped metadata plus a post-run acceptance
sidecar. All model bytes remain the synthetic test model.

Similarly, a "ratified scope" is simulated with an isolated throwaway Git
repository and a monkeypatched in-process registry whose values are labelled
SYNTHETIC TEST SIMULATION. Nothing here is a human signature or approval.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
from typing import Any

import numpy as np

from ai.diagnostic_inference import DIAGNOSTIC_INPUT_SCHEMA_VERSION
from ai.diagnostic_scope import (
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


def make_scope_git_repo(
    tmp_path: Path,
    *,
    doc_text: str = SYNTHETIC_GOVERNANCE_DOCUMENT,
    include_doc: bool = True,
) -> SimpleNamespace:
    """Create G2 (governance) -> D (approved execution revision), clean HEAD."""
    repo = Path(tmp_path) / "diagnostic_scope_repo"
    repo.mkdir(parents=True, exist_ok=True)

    def git(*args: str) -> str:
        proc = subprocess.run(
            ["git", *args], cwd=str(repo), capture_output=True, text=True, check=True
        )
        return proc.stdout.strip()

    git("init")
    git("config", "user.name", "Synthetic Test Runner")
    git("config", "user.email", "synthetic@example.test")
    (repo / ".gitignore").write_text("data/\n", encoding="utf-8")
    doc_path = repo / DIAGNOSTIC_GOVERNANCE_DOCUMENT_RELATIVE_PATH
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    if include_doc:
        doc_path.write_text(doc_text, encoding="utf-8")
    (repo / "README.md").write_text("synthetic governance baseline G2\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-m", "synthetic governance G2 (not a real ratification)")
    g_sha = git("rev-parse", "HEAD").lower()
    doc_sha = hashlib.sha256(doc_text.encode("utf-8")).hexdigest()
    (repo / "README.md").write_text(
        "synthetic approved execution revision D\n", encoding="utf-8"
    )
    git("add", ".")
    git("commit", "-m", "synthetic development revision D")
    d_sha = git("rev-parse", "HEAD").lower()
    return SimpleNamespace(
        repo=repo, g_sha=g_sha, d_sha=d_sha, doc_sha=doc_sha, doc_path=doc_path
    )


def make_authorization_doc(
    *,
    manifest_sha256: str,
    g_sha: str,
    d_sha: str,
    doc_sha: str,
) -> dict[str, Any]:
    target = DIAGNOSTIC_TARGET_BUNDLE
    attestation = "_".join(DIAGNOSTIC_ATTESTATION_TOKENS)
    return {
        "schema_version": DIAGNOSTIC_AUTHORIZATION_SCHEMA_VERSION,
        "authorization_status": "AUTHORIZED_BY_LOCAL_OPERATOR",
        "scope_id": DIAGNOSTIC_SCOPE_ID,
        "governance_pr_number": 999,
        "governance_merge_commit_sha": g_sha,
        "approved_code_revision": d_sha,
        "activation_merge_commit_sha": d_sha,
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


def make_scope_record(
    *, manifest_sha256: str, g_sha: str, d_sha: str, doc_sha: str
) -> dict[str, Any]:
    target = DIAGNOSTIC_TARGET_BUNDLE
    return {
        "governance_pr_number": 999,
        "governance_merge_commit_sha": g_sha,
        "approved_code_revision": d_sha,
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
