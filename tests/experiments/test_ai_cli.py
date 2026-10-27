"""Focused tests for the AI-4.1 offline research CLI (``python -m ai``).

Synthetic fixtures only: every bundle is trained in memory from the existing
``ai.validation_harness`` synthetic cohort builder and packaged exclusively
inside pytest temporary directories. No real patient record, dataset file, or
committed binary artifact is created. Real-provenance bundles are *simulated*
by re-signing a synthetic bundle's manifest with research-authorization
metadata understood by the existing packaging verifier; the underlying model
bytes remain the synthetic test model.
"""
from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import io
import math
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from typing import Any

import joblib
import pytest
from scipy.special import expit

from ai import (
    BundleIntegrityError,
    DA_A2_RESTING_LABS_PANEL,
    ResearchCadPredictor,
    ensure_private_directory,
    get_or_create_local_signing_key,
    package_research_bundle,
    protect_private_file,
    train_research_model,
    verify_trusted_local_bundle,
    write_bundle_acceptance_marker,
    write_bundle_quarantine_marker,
)
from ai.cli import (
    MAX_INPUT_BYTES,
    SYNTHETIC_DEMO_RECORD,
    assert_cli_predict_supported,
    build_panels_payload,
    bundle_provenance_assessment,
)
from ai.cli import main as cli_main
from ai.packaging import (
    ATTESTATION_SCHEME,
    BUNDLE_ACCEPTANCE_MARKER_FILENAME,
    _compute_manifest_attestation_hmac,
)
from ai.training import (
    EXECUTION_PROFILE_AI1_GENERIC_V1,
    EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1,
    ResearchTrainingConfig,
)
from ai.validation_harness import _make_synthetic_cohort

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_INPUT = REPO_ROOT / "ai" / "examples" / "synthetic_da_a2_resting_labs_v1.json"

FAST_CLI_TEST_CONFIG = ResearchTrainingConfig(
    protocol_id="CAI-AI41-CLI-TEST-V1",
    model_version="0.1.0",
    outer_folds=3,
    inner_folds=2,
    repeat_seeds=(20261025,),
    shuffle_control_seeds=(20261101,),
    lr_c_grid=(0.1, 1.0),
    rf_max_depths=(2, 3),
    rf_min_samples_leaf=(5,),
    rf_n_estimators=20,
    bootstrap_resamples=40,
    shap_max_background_samples=24,
)


@pytest.fixture
def tmp_path(tmp_path: Path) -> Path:
    """Mirror the AI pipeline suite: private-isolated pytest temp root."""
    return ensure_private_directory(tmp_path)


@pytest.fixture(scope="module")
def synthetic_bundle(tmp_path_factory: pytest.TempPathFactory) -> SimpleNamespace:
    """One shared signed synthetic bundle, trained via existing tools."""
    root = ensure_private_directory(tmp_path_factory.mktemp("ai_cli_bundle"))
    trusted_root = ensure_private_directory(root / "trusted_bundles")
    key_path = (
        ensure_private_directory(root / "private_keys") / "local_bundle_hmac_v1.key"
    )
    signing_key = get_or_create_local_signing_key(key_path)
    records, labels = _make_synthetic_cohort(72, seed=20261025)
    run = train_research_model(
        records,
        labels,
        DA_A2_RESTING_LABS_PANEL,
        model_id="synth_ai41_cli_test_v1",
        development_cohort_id="synthetic_cleveland",
        development_dataset_id="DA-A2:synthetic_cleveland",
        synthetic_data_confirmed=True,
        config=FAST_CLI_TEST_CONFIG,
    )
    bundle_dir = trusted_root / "cli_test_bundle_v1"
    descriptor = package_research_bundle(run, bundle_dir, signing_key=signing_key)
    return SimpleNamespace(
        root=root,
        trusted_root=trusted_root,
        bundle_dir=bundle_dir,
        key_path=key_path,
        signing_key=signing_key,
        descriptor=descriptor,
        model_family=run.selected_model_family,
    )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _invoke(capsys: pytest.CaptureFixture[str], argv: list[str]) -> tuple[int, str, str]:
    rc = cli_main(argv)
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


def _invoke_json(
    capsys: pytest.CaptureFixture[str], argv: list[str]
) -> tuple[int, Any, Any, str, str]:
    rc, out, err = _invoke(capsys, argv)
    out_json = json.loads(out) if out.strip() else None
    err_json = json.loads(err) if err.strip() else None
    return rc, out_json, err_json, out, err


def _predict_argv(env: Any, input_arg: str, *extra: str) -> list[str]:
    return [
        "predict",
        "--bundle-dir", str(env.bundle_dir),
        "--trusted-root", str(env.trusted_root),
        "--signing-key-path", str(env.key_path),
        "--input", input_arg,
        *extra,
    ]


def _verify_argv(env: Any, *extra: str) -> list[str]:
    return [
        "verify-bundle",
        "--bundle-dir", str(env.bundle_dir),
        "--trusted-root", str(env.trusted_root),
        "--signing-key-path", str(env.key_path),
        *extra,
    ]


def _copy_bundle(src: Path, dst: Path, *, skip: frozenset[str] = frozenset()) -> Path:
    ensure_private_directory(dst)
    for entry in sorted(src.iterdir()):
        if entry.name in skip or entry.name == BUNDLE_ACCEPTANCE_MARKER_FILENAME:
            continue
        target = dst / entry.name
        target.write_bytes(entry.read_bytes())
        protect_private_file(target)
    return dst


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


def _simulate_real_provenance(manifest: dict[str, Any]) -> None:
    """Mutate a manifest dict (in place) into valid-shaped real provenance."""
    manifest["eligibility"]["synthetic_only"] = False
    manifest["eligibility"]["execution_mode"] = "INTERNAL_EXPLORATORY_RESEARCH"
    manifest["research_authorization"] = {
        "governance_decision_id": "D-047",
        "dataset_id": "DA-A2",
        "panel_id": DA_A2_RESTING_LABS_PANEL.panel_id,
        "experiment_type": "INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED",
        "source_relative_path": "synthetic-test-simulation/not-a-real-source",
        "expected_source_sha256": "a" * 64,
        "expected_source_row_count": 72,
        "authorized_by": "cli-test-synthetic-simulation",
        "authorized_date": "2026-10-26",
        "signature_attestation": "TEST SIMULATION ONLY - Gate PT P-3 CLOSED",
        "pinned_commit_sha": "b" * 40,
        "protocol_sha256": "c" * 64,
        "plan_sha256": "d" * 64,
        "dictionary_sha256": None,
        "allowed_operations": [],
        "forbidden_operations": [],
        "protected_output_root": "synthetic-test-simulation",
        "model_packaging_authorized": True,
        "patient_shap_authorized": True,
    }


def _forbid_deserialization(monkeypatch: pytest.MonkeyPatch) -> list[bool]:
    calls: list[bool] = []

    def _boom(*_args: Any, **_kwargs: Any) -> Any:
        calls.append(True)
        raise AssertionError("joblib.load must not run for this CLI invocation")

    monkeypatch.setattr("ai.inference.joblib.load", _boom)
    return calls


def _assert_prediction_faithful(payload: dict[str, Any], *, model_family: str) -> None:
    prediction = payload["prediction"]
    explanation = payload["explanation"]
    assert payload["model_family"] == model_family
    assert payload["execution_profile"] == EXECUTION_PROFILE_AI1_GENERIC_V1
    assert 0.0 < prediction["raw_model_score"] < 1.0
    assert 0.0 < prediction["calibrated_research_score"] < 1.0
    assert float(expit(prediction["calibrated_log_odds"])) == pytest.approx(
        prediction["calibrated_research_score"], abs=1e-12
    )
    # Faithful SHAP: base + sum(attributions) == target on the declared scale.
    reconstructed = explanation["base_value"] + sum(
        item["shap_value"] for item in explanation["attributions"]
    )
    assert reconstructed == pytest.approx(
        explanation["target_prediction_on_scale"], abs=1e-9
    )
    assert explanation["sum_check"]["passed"] is True
    assert explanation["additive_on_calibrated_probability"] is False
    assert prediction["shap_additive_on_calibrated_probability"] is False
    assert prediction["shap_explained_quantity"] == explanation["explained_quantity"]
    assert prediction["shap_mathematical_scale"] == explanation["scale"]
    assert [item["feature_name"] for item in explanation["attributions"]] == list(
        DA_A2_RESTING_LABS_PANEL.feature_names
    )
    if model_family == "l2_logistic_regression":
        assert explanation["explained_quantity"] == "calibrated_log_odds"
        assert explanation["scale"] == "calibrated_log_odds"
        assert explanation["explains_calibrated_score_directly"] is True
        assert explanation["target_prediction_on_scale"] == pytest.approx(
            prediction["calibrated_log_odds"], abs=1e-9
        )
        assert float(expit(reconstructed)) == pytest.approx(
            prediction["calibrated_research_score"], abs=1e-9
        )
    else:
        assert explanation["explained_quantity"] == "raw_model_score"
        assert explanation["scale"] == "raw_model_probability"
        assert explanation["explains_calibrated_score_directly"] is False
        assert explanation["target_prediction_on_scale"] == pytest.approx(
            prediction["raw_model_score"], abs=1e-9
        )
    assert payload["governance"]["serving_eligibility"] == "RESEARCH_ONLY"
    assert payload["governance"]["approved_for_serving"] is False
    assert payload["governance"]["clinical_use_authorized"] is False
    assert any("RESEARCH_ONLY" in item for item in payload["limitations"])
    lime = payload.get("lime_explanation")
    if lime is not None:
        # Genuine LIME must share the SHAP target/scale and match the actual
        # prediction quantity on that declared scale.
        assert lime["is_exact"] is False
        assert lime["is_local_approximation"] is True
        assert lime["additive_decomposition_claim"] is False
        assert lime["explained_quantity"] == explanation["explained_quantity"]
        assert lime["scale"] == explanation["scale"]
        assert payload["explanation_comparability"]["comparable"] is True
        fidelity = lime["fidelity"]
        if lime["explained_quantity"] == "calibrated_log_odds":
            expected = prediction["calibrated_log_odds"]
        elif lime["explained_quantity"] == "raw_model_score":
            expected = prediction["raw_model_score"]
        else:
            expected = prediction["raw_model_log_odds"]
        assert fidelity["model_prediction_at_instance"] == pytest.approx(
            expected, abs=1e-9
        )
        assert fidelity["local_fidelity_abs_error"] >= 0.0
        assert math.isfinite(fidelity["local_fidelity_relative_error"])
        assert fidelity["weighted_r2"] is not None
        assert len(lime["attributions"]) == len(
            DA_A2_RESTING_LABS_PANEL.feature_names
        )
        assert all(
            math.isfinite(item["lime_weight"]) for item in lime["attributions"]
        )
        assert any("LIME" in item for item in payload["limitations"])
        # Every LIME payload carries an explicit, machine-readable verdict.
        quality = lime["quality"]
        assert quality["status"] in {
            "ACCEPTABLE_LOCAL_APPROXIMATION",
            "LOW_LOCAL_FIDELITY",
            "UNSTABLE",
            "UNVERIFIED_STABILITY",
            "INVALID",
        }
        assert quality["is_reliable_for_interpretation"] is (
            quality["status"] == "ACCEPTABLE_LOCAL_APPROXIMATION"
        )
        assert quality["policy_sha256"]
        assert quality["warnings"]
        assert set(quality["dimensions"]) == {
            "numerical_validity",
            "instance_fidelity",
            "neighborhood_fidelity",
            "stability",
        }
        if not quality["is_reliable_for_interpretation"]:
            assert "DO NOT RELY" in quality["interpretation_guard"]
        assert payload["prediction"]["lime_quality_status"] == quality["status"]
        assert payload["prediction"]["lime_reliable_for_interpretation"] is (
            quality["is_reliable_for_interpretation"]
        )
        assert payload["lime_stability"]["stability_assessment"] in {
            "STABLE_WITHIN_REGISTERED_TOLERANCE",
            "SENSITIVE_TO_SEED",
        }
        assert math.isfinite(
            float(lime["fidelity"]["local_fidelity_error_in_neighborhood_sigma"])
        )


# --------------------------------------------------------------------------- #
# panels
# --------------------------------------------------------------------------- #


def test_cli_panels_lists_contracts_profiles_and_input_types(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc, payload, err_json, _out, err = _invoke_json(capsys, ["panels"])
    assert rc == 0 and err_json is None and err == ""
    assert [p["panel_id"] for p in payload["panels"]] == [
        "da_a2_resting_v1",
        "da_a2_resting_labs_v1",
        "da_a1_basic_clinical_v1",
        "da_a1_clinical_core_labs_v1",
    ]
    assert all(p["real_data_execution_authorized"] is False for p in payload["panels"])

    labs = payload["panels"][1]
    assert labs["ordered_feature_names"] == list(DA_A2_RESTING_LABS_PANEL.feature_names)
    assert labs["required_feature_names"] == ["age", "sex", "cp"]
    assert labs["optional_feature_names"] == ["trestbps", "restecg", "chol", "fbs"]
    assert labs["contract_sha256"] == DA_A2_RESTING_LABS_PANEL.contract_sha256
    fields = {f["name"]: f for f in labs["fields"]}
    assert fields["chol"]["unit"] == "mg/dL"
    assert fields["chol"]["role"] == "numeric"
    assert "finite JSON number" in fields["age"]["json_input_type"]
    assert fields["cp"]["categorical_codes"] == [1, 2, 3, 4]
    assert "categorical_codes" in fields["cp"]["json_input_type"]

    profiles = {p["execution_profile"]: p for p in payload["execution_profiles"]}
    assert profiles[EXECUTION_PROFILE_AI1_GENERIC_V1]["cli_predict_supported"] is True
    assert (
        profiles[EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1]["cli_predict_supported"]
        is False
    )
    families = {f["model_family"]: f for f in payload["model_families"]}
    assert families["l2_logistic_regression"]["shap_mathematical_scale"] == (
        "calibrated_log_odds"
    )
    assert families["constrained_random_forest"]["shap_mathematical_scale"] == (
        "raw_model_probability"
    )
    assert all(
        f["shap_additive_on_calibrated_probability"] is False for f in families.values()
    )

    # Single-panel filter + pure builder agree; unknown panel is a usage error.
    rc_single, single, _e, _o, _s = _invoke_json(
        capsys, ["panels", "--panel", "da_a1_basic_clinical_v1"]
    )
    assert rc_single == 0
    assert [p["panel_id"] for p in single["panels"]] == ["da_a1_basic_clinical_v1"]
    assert build_panels_payload("da_a2_resting_v1")["panels"][0]["panel_id"] == (
        "da_a2_resting_v1"
    )
    with pytest.raises(SystemExit) as usage_exc:
        cli_main(["panels", "--panel", "not_a_panel"])
    assert usage_exc.value.code == 2
    capsys.readouterr()


def test_cli_panels_text_format(capsys: pytest.CaptureFixture[str]) -> None:
    rc, out, err = _invoke(capsys, ["panels", "--format", "text"])
    assert rc == 0 and err == ""
    for panel_id in (
        "da_a2_resting_v1",
        "da_a2_resting_labs_v1",
        "da_a1_basic_clinical_v1",
        "da_a1_clinical_core_labs_v1",
    ):
        assert panel_id in out
    assert EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1 in out


# --------------------------------------------------------------------------- #
# verify-bundle
# --------------------------------------------------------------------------- #


def test_cli_verify_bundle_trusted_and_integrity_only_modes(
    synthetic_bundle: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    env = synthetic_bundle
    rc, payload, err_json, out, _err = _invoke_json(capsys, _verify_argv(env))
    assert rc == 0 and err_json is None
    assert payload["status"] == "VERIFIED"
    assert payload["verification_mode"] == "trusted_local"
    assert payload["bundle_dir_name"] == "cli_test_bundle_v1"
    assert payload["model"]["model_id"] == "synth_ai41_cli_test_v1"
    assert payload["model"]["model_version"] == "0.1.0"
    assert payload["model"]["selected_model_family"] == env.model_family
    assert payload["model"]["execution_profile"] == EXECUTION_PROFILE_AI1_GENERIC_V1
    assert payload["panel"]["panel_id"] == DA_A2_RESTING_LABS_PANEL.panel_id
    assert payload["authentication"]["producer_authenticated"] is True
    assert payload["authentication"]["safe_for_pickle_deserialization"] is True
    assert payload["provenance"]["synthetic_only"] is True
    assert payload["provenance"]["verified_artifact_hashes"] == dict(
        env.descriptor.verified_files
    )
    assert payload["cli_predict_supported"] is True
    assert payload["cli_predict_block_reason"] is None
    # Ordinary output carries no local paths or key material.
    assert str(env.root) not in out
    assert str(env.key_path) not in out
    assert env.signing_key.hex() not in out

    rc_io, integrity, _e, _o, _s = _invoke_json(
        capsys,
        ["verify-bundle", "--bundle-dir", str(env.bundle_dir), "--integrity-only"],
    )
    assert rc_io == 0
    assert integrity["verification_mode"] == "integrity_only"
    assert integrity["authentication"]["producer_authenticated"] is False
    assert integrity["authentication"]["safe_for_pickle_deserialization"] is False
    assert integrity["cli_predict_supported"] is False
    assert "never authorizes" in integrity["cli_predict_block_reason"]

    # Matching operator expectations pass.
    rc_exp, _p, _e2, _o2, _s2 = _invoke_json(
        capsys,
        _verify_argv(
            env,
            "--expect-panel", DA_A2_RESTING_LABS_PANEL.panel_id,
            "--expect-profile", EXECUTION_PROFILE_AI1_GENERIC_V1,
            "--expect-model-family", env.model_family,
        ),
    )
    assert rc_exp == 0


@pytest.mark.parametrize(
    ("extra", "expected_code"),
    [
        (("--expect-panel", "da_a2_resting_v1"), "cli_bundle_expectation_mismatch"),
        (
            ("--expect-profile", EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1),
            "cli_bundle_expectation_mismatch",
        ),
    ],
)
def test_cli_verify_bundle_expectation_mismatches_fail_closed(
    synthetic_bundle: Any,
    capsys: pytest.CaptureFixture[str],
    extra: tuple[str, str],
    expected_code: str,
) -> None:
    rc, out_json, err_json, out, err = _invoke_json(
        capsys, _verify_argv(synthetic_bundle, *extra)
    )
    assert rc == 2 and out_json is None and out == ""
    assert err_json["status"] == "FAIL_CLOSED"
    assert err_json["error"]["code"] == expected_code
    assert str(synthetic_bundle.root) not in err


def test_cli_verify_bundle_wrong_family_expectation_fails_closed(
    synthetic_bundle: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    other_family = (
        "constrained_random_forest"
        if synthetic_bundle.model_family == "l2_logistic_regression"
        else "l2_logistic_regression"
    )
    rc, _o, err_json, _out, _err = _invoke_json(
        capsys,
        _verify_argv(synthetic_bundle, "--expect-model-family", other_family),
    )
    assert rc == 2
    assert err_json["error"]["code"] == "cli_bundle_expectation_mismatch"
    assert err_json["error"]["field"] == "selected_model_family"


def test_cli_verify_bundle_missing_wrong_key_and_wrong_root_fail_closed(
    synthetic_bundle: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env = synthetic_bundle

    # Missing bundle directory.
    rc, _o, err_json, _out, _e = _invoke_json(
        capsys,
        [
            "verify-bundle",
            "--bundle-dir", str(env.trusted_root / "does_not_exist"),
            "--trusted-root", str(env.trusted_root),
            "--signing-key-path", str(env.key_path),
        ],
    )
    assert rc == 2 and err_json["error"]["code"] == "invalid_bundle_directory"

    # Empty bundle directory inside the trusted root.
    empty_dir = ensure_private_directory(tmp_path / "trusted_empty" / "empty_bundle")
    rc, _o, err_json, _out, _e = _invoke_json(
        capsys,
        [
            "verify-bundle",
            "--bundle-dir", str(empty_dir),
            "--trusted-root", str(empty_dir.parent),
            "--signing-key-path", str(env.key_path),
        ],
    )
    assert rc == 2
    assert err_json["error"]["code"] == "unexpected_bundle_directory_contents"

    # Bundle copy missing a required sibling file.
    incomplete_root = ensure_private_directory(tmp_path / "trusted_incomplete")
    incomplete = _copy_bundle(
        env.bundle_dir,
        incomplete_root / "incomplete_bundle",
        skip=frozenset({"evaluation_summary.json"}),
    )
    rc, _o, err_json, _out, _e = _invoke_json(
        capsys,
        [
            "verify-bundle",
            "--bundle-dir", str(incomplete),
            "--trusted-root", str(incomplete_root),
            "--signing-key-path", str(env.key_path),
        ],
    )
    assert rc == 2
    assert err_json["error"]["code"] == "unexpected_bundle_directory_contents"

    # Wrong signing key: HMAC producer attestation must fail.
    wrong_key_path = (
        ensure_private_directory(tmp_path / "wrong_keys") / "local_bundle_hmac_v1.key"
    )
    get_or_create_local_signing_key(wrong_key_path)
    rc, _o, err_json, _out, _e = _invoke_json(
        capsys,
        [
            "verify-bundle",
            "--bundle-dir", str(env.bundle_dir),
            "--trusted-root", str(env.trusted_root),
            "--signing-key-path", str(wrong_key_path),
        ],
    )
    assert rc == 2
    assert err_json["error"]["code"] == "untrusted_bundle_producer_signature"

    # Explicit key path that does not exist: never minted by verify/predict.
    missing_key = tmp_path / "no_such.key"
    rc, _o, err_json, _out, _e = _invoke_json(
        capsys,
        [
            "verify-bundle",
            "--bundle-dir", str(env.bundle_dir),
            "--trusted-root", str(env.trusted_root),
            "--signing-key-path", str(missing_key),
        ],
    )
    assert rc == 2 and err_json["error"]["code"] == "cli_signing_key_not_found"
    assert not missing_key.exists()

    # Bundle outside the supplied trusted root.
    other_root = ensure_private_directory(tmp_path / "other_trusted_root")
    rc, _o, err_json, _out, _e = _invoke_json(
        capsys,
        [
            "verify-bundle",
            "--bundle-dir", str(env.bundle_dir),
            "--trusted-root", str(other_root),
            "--signing-key-path", str(env.key_path),
        ],
    )
    assert rc == 2 and err_json["error"]["code"] == "untrusted_bundle_location"


def test_cli_tampered_bundle_fails_closed_before_deserialization(
    synthetic_bundle: Any,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = synthetic_bundle
    tampered_root = ensure_private_directory(tmp_path / "trusted_tampered")
    tampered = _copy_bundle(env.bundle_dir, tampered_root / "tampered_bundle")
    calibration = tampered / "calibration.json"
    calibration.write_bytes(calibration.read_bytes() + b" ")
    protect_private_file(calibration)

    calls = _forbid_deserialization(monkeypatch)
    argv = [
        "--bundle-dir", str(tampered),
        "--trusted-root", str(tampered_root),
        "--signing-key-path", str(env.key_path),
    ]
    rc, _o, err_json, _out, _e = _invoke_json(capsys, ["verify-bundle", *argv])
    assert rc == 2
    assert err_json["error"]["code"] in ("file_size_mismatch", "file_sha256_mismatch")

    rc, _o, err_json, _out, _e = _invoke_json(
        capsys, ["predict", *argv, "--input", str(EXAMPLE_INPUT)]
    )
    assert rc == 2
    assert err_json["error"]["code"] in ("file_size_mismatch", "file_sha256_mismatch")
    assert calls == []


def test_cli_quarantined_bundle_fails_closed(
    synthetic_bundle: Any,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = synthetic_bundle
    root = ensure_private_directory(tmp_path / "trusted_quarantine")
    quarantined = _copy_bundle(env.bundle_dir, root / "quarantined_bundle")
    write_bundle_quarantine_marker(
        quarantined,
        reason_code="cli_test_simulated_post_run_failure",
        detail="Synthetic test simulation of a post-run custody failure.",
    )
    calls = _forbid_deserialization(monkeypatch)
    argv = [
        "--bundle-dir", str(quarantined),
        "--trusted-root", str(root),
        "--signing-key-path", str(env.key_path),
    ]
    for command_args in (["verify-bundle", *argv], ["predict", *argv, "--input", str(EXAMPLE_INPUT)]):
        rc, _o, err_json, _out, _e = _invoke_json(capsys, command_args)
        assert rc == 2
        assert err_json["error"]["code"] == "bundle_quarantined_not_accepted"
    assert calls == []


# --------------------------------------------------------------------------- #
# Real-provenance and execution-profile policy (CLI is stricter than engine)
# --------------------------------------------------------------------------- #


def test_cli_rejects_unaccepted_real_provenance_bundle(
    synthetic_bundle: Any,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = synthetic_bundle
    root = ensure_private_directory(tmp_path / "trusted_unaccepted")
    bundle = _copy_bundle(env.bundle_dir, root / "simulated_real_unaccepted")
    _resign_manifest(bundle, env.signing_key, _simulate_real_provenance)

    calls = _forbid_deserialization(monkeypatch)
    argv = [
        "--bundle-dir", str(bundle),
        "--trusted-root", str(root),
        "--signing-key-path", str(env.key_path),
    ]
    for command_args in (["verify-bundle", *argv], ["predict", *argv, "--input", str(EXAMPLE_INPUT)]):
        rc, _o, err_json, _out, _e = _invoke_json(capsys, command_args)
        assert rc == 2
        assert err_json["error"]["code"] == "bundle_post_run_acceptance_missing"
    assert calls == []


def test_cli_predict_blocks_structurally_valid_real_provenance_bundle(
    synthetic_bundle: Any,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = synthetic_bundle
    root = ensure_private_directory(tmp_path / "trusted_simulated_real")
    bundle = _copy_bundle(env.bundle_dir, root / "simulated_real_bundle")
    _resign_manifest(bundle, env.signing_key, _simulate_real_provenance)
    write_bundle_acceptance_marker(
        bundle,
        expected_source_sha256="a" * 64,
        accepted_by="cli-test-synthetic-simulation",
        detail="Synthetic simulation of recorded post-run acceptance.",
    )

    # The existing packaging layer accepts this simulated bundle as trusted...
    descriptor = verify_trusted_local_bundle(
        bundle, trusted_local_root=root, signing_key=env.signing_key
    )
    assert descriptor.producer_authenticated is True
    assert descriptor.safe_for_pickle_deserialization is True
    assessment = bundle_provenance_assessment(descriptor.manifest)
    assert assessment["synthetic_only"] is False
    assert assessment["provenance_cli_compatible"] is False
    # ...and the existing engine could load our own synthetic pickle bytes...
    predictor = ResearchCadPredictor.from_verified_bundle(
        bundle, trusted_local_root=root, signing_key=env.signing_key
    )
    assert predictor.model_id == "synth_ai41_cli_test_v1"

    # ...but the CLI reports prediction unsupported and never deserializes.
    argv = [
        "--bundle-dir", str(bundle),
        "--trusted-root", str(root),
        "--signing-key-path", str(env.key_path),
    ]
    rc, payload, _e, _out, _err = _invoke_json(capsys, ["verify-bundle", *argv])
    assert rc == 0
    assert payload["authentication"]["producer_authenticated"] is True
    assert payload["cli_predict_supported"] is False
    assert "real-provenance" in payload["cli_predict_block_reason"]

    calls = _forbid_deserialization(monkeypatch)
    rc, _o, err_json, _out, _err = _invoke_json(
        capsys, ["predict", *argv, "--input", str(EXAMPLE_INPUT)]
    )
    assert rc == 2
    assert err_json["error"]["code"] == "cli_real_provenance_bundle_not_supported"
    assert calls == []

    with pytest.raises(BundleIntegrityError) as guard_exc:
        assert_cli_predict_supported(descriptor.manifest)
    assert guard_exc.value.code == "cli_real_provenance_bundle_not_supported"


def test_cli_predict_blocks_frozen_d047_profile_bundle(
    synthetic_bundle: Any,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = synthetic_bundle

    # Pure policy check on a manifest dict.
    manifest = deepcopy(dict(env.descriptor.manifest))
    manifest["model"] = {
        **dict(manifest["model"]),
        "execution_profile": EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1,
    }
    with pytest.raises(BundleIntegrityError) as guard_exc:
        assert_cli_predict_supported(manifest)
    assert guard_exc.value.code == "cli_execution_profile_not_supported"

    # Integration check: re-signed bundle whose container + manifest both
    # declare the frozen profile is blocked by the CLI before any load.
    root = ensure_private_directory(tmp_path / "trusted_d047")
    bundle = _copy_bundle(env.bundle_dir, root / "d047_profile_bundle")
    container = joblib.load(bundle / "model.joblib")
    container["execution_profile"] = EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1
    joblib.dump(container, bundle / "model.joblib", compress=3)
    protect_private_file(bundle / "model.joblib")
    model_bytes = (bundle / "model.joblib").read_bytes()

    def _to_d047(m: dict[str, Any]) -> None:
        m["model"]["execution_profile"] = EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1
        m["files"]["model.joblib"] = {
            "sha256": hashlib.sha256(model_bytes).hexdigest(),
            "size_bytes": len(model_bytes),
        }

    _resign_manifest(bundle, env.signing_key, _to_d047)

    argv = [
        "--bundle-dir", str(bundle),
        "--trusted-root", str(root),
        "--signing-key-path", str(env.key_path),
    ]
    rc, payload, _e, _out, _err = _invoke_json(capsys, ["verify-bundle", *argv])
    assert rc == 0
    assert payload["model"]["execution_profile"] == (
        EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1
    )
    assert payload["cli_predict_supported"] is False

    calls = _forbid_deserialization(monkeypatch)
    rc, _o, err_json, _out, _err = _invoke_json(
        capsys, ["predict", *argv, "--input", str(EXAMPLE_INPUT)]
    )
    assert rc == 2
    assert err_json["error"]["code"] == "cli_execution_profile_not_supported"
    assert calls == []


def test_cli_preserves_activated_training_registry_and_never_imports_execution() -> None:
    """Post-activation sentinel: G..A changed ONLY the trusted training registry.

    The pre-activation assertion ``registry == {}`` is obsolete after PR #58.
    The security-correct expectation is that exactly the ratified, hash-bound
    training amendment is present, that it does NOT authorize inference or
    serving, and that this synthetic-only CLI still cannot import the guarded
    execution path or load a real-provenance bundle.
    """
    from ai.execution import RATIFIED_OPERATIONAL_SCOPE_AMENDMENTS
    from ai.diagnostic_scope import RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES

    amendment_id = "CAI-AMEND-AI2-CLEVELAND-D047-V1"
    governance_merge = "7f4b7a50d7fd423914e5bd98ed2b525bddbfc627"
    assert set(RATIFIED_OPERATIONAL_SCOPE_AMENDMENTS) == {amendment_id}
    record = RATIFIED_OPERATIONAL_SCOPE_AMENDMENTS[amendment_id]
    assert record["governance_pr_number"] == 54
    assert record["governance_merge_commit_sha"] == governance_merge
    assert record["approved_code_revision"] == governance_merge
    assert record["approved_dataset_id"] == "DA-A2"
    assert record["approved_panel_id"] == "da_a2_resting_v1"
    assert record["frozen_source_sha256"] == (
        "a74b7efa387bc9d108d7d0115d831fe9b414b29ae7124f331b622b4efa0427c8"
    )
    assert record["frozen_protocol_sha256"] == (
        "96c26829ff73893dab8ee091b2eaea1592479a1e0528ae6832651a9688ea3c86"
    )
    assert record["frozen_amendment_document_sha256"] == (
        "4c1d595534fd9a642a895cc59c01d4d81fbf5b84cf38ec3da5edcb7dd2d82890"
    )
    assert record["approved_operations"] == (
        "persistent_model_packaging",
        "patient_level_shap_background",
    )
    assert record["protected_output_root"] == "data/experiments"
    assert record["ratification_comment_exact"] == (
        "RATIFY-AI2-OPERATIONAL-SCOPE-EXPANSION"
    )
    # Activation of TRAINING scope never authorizes inference or serving.
    assert not any("infer" in op or "serv" in op for op in record["approved_operations"])
    assert RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES == {}

    tree = ast.parse((REPO_ROOT / "ai" / "cli.py").read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert "ai.execution" not in imported
    assert "ai.diagnostic_inference" not in imported
    assert "ai.diagnostic_scope" not in imported
    assert not {m.split(".")[0] for m in imported} & {"backend", "shap", "lime"}

    # The general CLI remains closed to real-provenance bundles even though the
    # training registry is activated.
    real_shaped_manifest = {
        "eligibility": {
            "synthetic_only": False,
            "execution_mode": "INTERNAL_EXPLORATORY_RESEARCH",
        },
        "research_authorization": {"governance_decision_id": "D-047"},
        "model": {"execution_profile": EXECUTION_PROFILE_AI1_GENERIC_V1},
    }
    assessment = bundle_provenance_assessment(real_shaped_manifest)
    assert assessment["provenance_cli_compatible"] is False
    assert assessment["cli_block_code"] == "cli_real_provenance_bundle_not_supported"
    with pytest.raises(BundleIntegrityError) as exc:
        assert_cli_predict_supported(real_shaped_manifest)
    assert exc.value.code == "cli_real_provenance_bundle_not_supported"


# --------------------------------------------------------------------------- #
# predict (happy paths)
# --------------------------------------------------------------------------- #


def test_cli_predict_synthetic_end_to_end_and_shap_additivity(
    synthetic_bundle: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    env = synthetic_bundle
    example = json.loads(EXAMPLE_INPUT.read_text(encoding="utf-8"))
    assert example == dict(SYNTHETIC_DEMO_RECORD)

    rc, payload, err_json, out, err = _invoke_json(
        capsys,
        _predict_argv(
            env,
            str(EXAMPLE_INPUT),
            "--expect-panel", DA_A2_RESTING_LABS_PANEL.panel_id,
            "--expect-profile", EXECUTION_PROFILE_AI1_GENERIC_V1,
            "--expect-model-family", env.model_family,
        ),
    )
    assert rc == 0 and err_json is None and err == ""
    assert payload["model_id"] == "synth_ai41_cli_test_v1"
    assert payload["model_version"] == "0.1.0"
    assert payload["panel_id"] == DA_A2_RESTING_LABS_PANEL.panel_id
    assert payload["cli"]["synthetic_input_confirmed"] is True
    assert payload["cli"]["bundle_provenance"] == "SYNTHETIC_RESEARCH"
    assert payload["provenance"]["producer_authenticated"] is True
    assert payload["provenance"]["verified_artifact_hashes"] == dict(
        env.descriptor.verified_files
    )
    _assert_prediction_faithful(payload, model_family=env.model_family)
    assert str(env.root) not in out
    assert str(env.key_path) not in out
    assert env.signing_key.hex() not in out


def test_cli_predict_accepts_explicitly_missing_optional_lab(
    synthetic_bundle: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env = synthetic_bundle
    payload_in = deepcopy(dict(SYNTHETIC_DEMO_RECORD))
    del payload_in["features"]["chol"]
    del payload_in["units"]["chol"]
    payload_in["missing_reasons"] = {"chol": "not_provided"}
    input_path = tmp_path / "synthetic_missing_chol.json"
    input_path.write_text(json.dumps(payload_in), encoding="utf-8")

    rc, payload, _e, _out, _err = _invoke_json(
        capsys, _predict_argv(env, str(input_path))
    )
    assert rc == 0
    statuses = {
        item["feature_name"]: item["status"]
        for item in payload["explanation"]["attributions"]
    }
    assert statuses["chol"] == "missing_imputed"
    assert any("chol" in item for item in payload["limitations"])
    _assert_prediction_faithful(payload, model_family=env.model_family)


def test_cli_predict_stdin_and_text_format(
    synthetic_bundle: Any,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = synthetic_bundle
    raw = json.dumps(dict(SYNTHETIC_DEMO_RECORD)).encode("utf-8")
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(raw)))
    rc, payload, _e, _out, _err = _invoke_json(capsys, _predict_argv(env, "-"))
    assert rc == 0
    _assert_prediction_faithful(payload, model_family=env.model_family)

    rc, out, err = _invoke(
        capsys, _predict_argv(env, str(EXAMPLE_INPUT), "--format", "text")
    )
    assert rc == 0 and err == ""
    assert "RESEARCH_ONLY" in out
    assert "raw model score:" in out
    assert "calibrated research score:" in out
    assert f"SHAP mathematical scale: {payload['explanation']['scale']}" in out
    assert payload["model_id"] in out


# --------------------------------------------------------------------------- #
# predict (invalid inputs fail closed)
# --------------------------------------------------------------------------- #


def _mutated_record(mutate: Any) -> dict[str, Any]:
    record = deepcopy(dict(SYNTHETIC_DEMO_RECORD))
    mutate(record)
    return record


@pytest.mark.parametrize(
    ("mutate", "expected_code"),
    [
        (lambda r: r["units"].__setitem__("chol", "mmol/L"), "unit_mismatch"),
        (lambda r: r["units"].pop("chol"), "unit_keys_mismatch"),
        (lambda r: r["features"].pop("age"), "missing_required_field"),
        (lambda r: r["features"].__setitem__("age", None), "missing_required_field"),
        (
            lambda r: r["features"].__setitem__("spo2", 98),
            "prohibited_leakage_or_wearable_field",
        ),
        (
            lambda r: r["features"].__setitem__("syntax_score", 12),
            "prohibited_leakage_or_wearable_field",
        ),
        (
            lambda r: r.__setitem__("context", {"track": "B"}),
            "wearable_or_track_b_rejected",
        ),
        (
            lambda r: r.__setitem__("context", {"source": "patient_wearable"}),
            "wearable_or_track_b_rejected",
        ),
        (
            lambda r: r["features"].__setitem__("mystery_feature", 1),
            "unregistered_feature_for_panel",
        ),
        (
            lambda r: r.__setitem__("panel_id", "da_a1_basic_clinical_v1"),
            "panel_id_mismatch",
        ),
        (
            lambda r: r.__setitem__("synthetic", False),
            "cli_non_synthetic_input_not_supported",
        ),
        (lambda r: r.pop("synthetic"), "cli_non_synthetic_input_not_supported"),
        (
            lambda r: r.__setitem__("synthetic", "true"),
            "cli_non_synthetic_input_not_supported",
        ),
        (
            lambda r: r["features"].__setitem__("chol", 0),
            "zero_measurement_unavailable",
        ),
        (lambda r: r["features"].__setitem__("cp", 9), "unknown_categorical_code"),
        (lambda r: r["features"].__setitem__("age", True), "invalid_numeric_value"),
        (lambda r: r["features"].__setitem__("age", "fifty"), "invalid_numeric_value"),
        (
            lambda r: (r["features"].pop("chol"), r["units"].pop("chol")),
            "missing_reason_mismatch",
        ),
        (lambda r: r.__setitem__("patient_id", "SENTINEL-ID-41"), "unexpected_envelope_key"),
    ],
)
def test_cli_predict_rejects_invalid_clinical_inputs(
    synthetic_bundle: Any,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    mutate: Any,
    expected_code: str,
) -> None:
    env = synthetic_bundle
    input_path = tmp_path / "synthetic_invalid.json"
    input_path.write_text(json.dumps(_mutated_record(mutate)), encoding="utf-8")
    rc, out_json, err_json, out, err = _invoke_json(
        capsys, _predict_argv(env, str(input_path))
    )
    assert rc == 2 and out_json is None and out == ""
    assert err_json["status"] == "FAIL_CLOSED"
    assert err_json["error"]["code"] == expected_code
    # Submitted values and local paths are never echoed in ordinary output.
    assert "SENTINEL-ID-41" not in err
    assert str(tmp_path) not in err
    assert str(env.root) not in err


def test_cli_predict_panel_mismatch_and_real_input_never_deserialize(
    synthetic_bundle: Any,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = synthetic_bundle
    calls = _forbid_deserialization(monkeypatch)

    panel_mismatch = tmp_path / "panel_mismatch.json"
    panel_mismatch.write_text(
        json.dumps(
            _mutated_record(lambda r: r.__setitem__("panel_id", "da_a2_resting_v1"))
        ),
        encoding="utf-8",
    )
    rc, _o, err_json, _out, _e = _invoke_json(
        capsys, _predict_argv(env, str(panel_mismatch))
    )
    assert rc == 2 and err_json["error"]["code"] == "panel_id_mismatch"

    real_input = tmp_path / "real_input.json"
    real_input.write_text(
        json.dumps(_mutated_record(lambda r: r.__setitem__("synthetic", False))),
        encoding="utf-8",
    )
    rc, _o, err_json, _out, _e = _invoke_json(
        capsys, _predict_argv(env, str(real_input))
    )
    assert rc == 2
    assert err_json["error"]["code"] == "cli_non_synthetic_input_not_supported"
    assert calls == []


@pytest.mark.parametrize(
    ("raw_text", "expected_code"),
    [
        ("{not json", "cli_malformed_input_json"),
        ('{"synthetic": true, "synthetic": true}', "cli_duplicate_json_key"),
        ('{"synthetic": true, "value": NaN}', "cli_non_finite_json_constant"),
        ("[1, 2, 3]", "cli_input_must_be_json_object"),
    ],
)
def test_cli_predict_rejects_malformed_input_files(
    synthetic_bundle: Any,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    raw_text: str,
    expected_code: str,
) -> None:
    input_path = tmp_path / "malformed.json"
    input_path.write_text(raw_text, encoding="utf-8")
    rc, _o, err_json, _out, _e = _invoke_json(
        capsys, _predict_argv(synthetic_bundle, str(input_path))
    )
    assert rc == 2 and err_json["error"]["code"] == expected_code


def test_cli_predict_missing_oversized_and_directory_inputs_fail_closed(
    synthetic_bundle: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env = synthetic_bundle
    rc, _o, err_json, _out, _e = _invoke_json(
        capsys, _predict_argv(env, str(tmp_path / "absent.json"))
    )
    assert rc == 2 and err_json["error"]["code"] == "cli_input_not_found"

    rc, _o, err_json, _out, _e = _invoke_json(capsys, _predict_argv(env, str(tmp_path)))
    assert rc == 2 and err_json["error"]["code"] == "cli_input_not_found"

    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b" " * (MAX_INPUT_BYTES + 1))
    rc, _o, err_json, _out, _e = _invoke_json(
        capsys, _predict_argv(env, str(oversized))
    )
    assert rc == 2 and err_json["error"]["code"] == "cli_input_too_large"

    rc, _o, err_json, _out, _e = _invoke_json(
        capsys, _predict_argv(env, str(EXAMPLE_INPUT), "--threshold", "1.5")
    )
    assert rc == 2 and err_json["error"]["code"] == "cli_invalid_threshold"


# --------------------------------------------------------------------------- #
# demo
# --------------------------------------------------------------------------- #


def test_cli_demo_retained_work_dir_then_predict(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    work_dir = tmp_path / "demo_work"
    rc, payload, err_json, out, _err = _invoke_json(
        capsys, ["demo", "--work-dir", str(work_dir)]
    )
    assert rc == 0 and err_json is None
    assert payload["status"] == "PASSED"
    assert payload["steps_passed"] == [
        "1_synthetic_cohort_training",
        "2_signed_bundle_packaging",
        "3_trusted_local_verification",
        "4_research_cad_predictor_load",
        "5_calibrated_prediction_and_faithful_shap",
        "6_local_lime_explanation",
    ]
    assert payload["work_artifacts_retained"] is True
    assert payload["bundle"]["cli_predict_supported"] is True
    _assert_prediction_faithful(
        payload["prediction"], model_family=payload["selected_model_family"]
    )
    # Ordinary output contains directory names only, never local paths.
    assert str(work_dir) not in out
    assert str(tmp_path) not in out

    bundle_dir = work_dir / "trusted_bundles" / "synthetic_demo_bundle_v1"
    key_path = work_dir / "private_keys" / "local_bundle_hmac_v1.key"
    assert bundle_dir.is_dir() and key_path.is_file()

    # The retained demo bundle works through the normal predict path.
    rc, prediction, _e, _o, _s = _invoke_json(
        capsys,
        [
            "predict",
            "--bundle-dir", str(bundle_dir),
            "--trusted-root", str(work_dir / "trusted_bundles"),
            "--signing-key-path", str(key_path),
            "--input", str(EXAMPLE_INPUT),
        ],
    )
    assert rc == 0
    _assert_prediction_faithful(
        prediction, model_family=payload["selected_model_family"]
    )

    # Re-running demo into the same work directory fails closed (no overwrite).
    rc, _o2, err_json, _out, _e2 = _invoke_json(
        capsys, ["demo", "--work-dir", str(work_dir)]
    )
    assert rc == 2
    assert err_json["error"]["code"] == "bundle_directory_already_exists"


# --------------------------------------------------------------------------- #
# Entry point, subprocess behavior, and Windows-safe source constraints
# --------------------------------------------------------------------------- #


def test_cli_module_entry_point_via_subprocess() -> None:
    panels = subprocess.run(
        [sys.executable, "-m", "ai", "panels"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=120,
    )
    assert panels.returncode == 0
    assert json.loads(panels.stdout)["status"] == "OK"

    help_run = subprocess.run(
        [sys.executable, "-m", "ai", "--help"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=120,
    )
    assert help_run.returncode == 0
    for command in ("panels", "verify-bundle", "predict", "demo"):
        assert command in help_run.stdout

    bad = subprocess.run(
        [sys.executable, "-m", "ai", "not-a-command"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=120,
    )
    assert bad.returncode == 2


def test_cli_demo_via_subprocess_uses_isolated_temporary_work_dir() -> None:
    demo = subprocess.run(
        [sys.executable, "-m", "ai", "demo"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=600,
    )
    assert demo.returncode == 0, demo.stderr
    payload = json.loads(demo.stdout)
    assert payload["status"] == "PASSED"
    assert payload["work_artifacts_retained"] is False
    _assert_prediction_faithful(
        payload["prediction"], model_family=payload["selected_model_family"]
    )
    # No temporary or user paths, key material, or tracebacks in output.
    assert "cardioassist_ai41_demo_" not in demo.stdout
    assert "Traceback" not in demo.stdout + demo.stderr


def test_cli_sources_are_windows_safe_and_engine_free(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    banned_tokens = ("chmod", "fchmod", "st_mode", "os.name", "ctypes", "S_IRWX")
    for relative in ("ai/cli.py", "ai/__main__.py"):
        source = (REPO_ROOT / relative).read_text(encoding="utf-8")
        for token in banned_tokens:
            assert token not in source, f"{relative} must not reference {token}"
        tree = ast.parse(source)
        imported_roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".")[0])
        assert not imported_roots & {"backend", "shap", "lime", "joblib"}

    cli_source = (REPO_ROOT / "ai" / "cli.py").read_text(encoding="utf-8")
    # No second inference engine or new estimators in the CLI layer.
    assert "LogisticRegression" not in cli_source
    assert "RandomForest" not in cli_source
    assert "predict_research_only" in cli_source  # delegates to existing engine

    # Windows has no os.fchmod; CLI operation must not depend on it.
    monkeypatch.delattr(os, "fchmod", raising=False)
    rc, payload, _e, _out, _err = _invoke_json(capsys, ["panels"])
    assert rc == 0 and payload["status"] == "OK"
