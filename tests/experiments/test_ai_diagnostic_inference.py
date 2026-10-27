"""Bounded offline diagnostic inference: synthetic-fixture and negative tests.

SYNTHETIC TEST SIMULATIONS ONLY. The "accepted real bundle" is a synthetic
model trained in memory, packaged by the existing secure packager, re-signed
with authorization-shaped metadata and given a post-run acceptance sidecar.
Arena has no access to the real private bundle or any patient data. No human
signature or maintainer approval is simulated as real: the simulated scope is
an in-process monkeypatched registry plus a throwaway Git repository.
"""
from __future__ import annotations

import dataclasses
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

import pytest
from scipy.special import expit

from ai import diagnostic_inference as di
from ai import diagnostic_scope as ds
from ai.calibration import OofLogisticCalibrator
from ai.cli import assert_cli_predict_supported, bundle_provenance_assessment
from ai.errors import BundleIntegrityError
from ai.filesystem_security import ensure_private_directory, protect_private_file
from ai.inference import ResearchCadPredictor
from ai.lime_explainability import LimeConfig
from ai.lime_quality import LimeQualityPolicy
from ai.packaging import (
    BUNDLE_ACCEPTANCE_MARKER_FILENAME,
    BUNDLE_QUARANTINE_MARKER_FILENAME,
    CALIBRATION_FILENAME,
    verify_trusted_local_bundle,
    write_bundle_quarantine_marker,
)
from ai.panels import DA_A2_RESTING_LABS_PANEL
from tests.experiments import diagnostic_fixtures as fx

REPO_ROOT = Path(__file__).resolve().parents[2]
FAST_LIME = LimeConfig(num_perturbations=64, seed=4321)
FAST_LIME_SEEDS = (101, 202, 303)


@pytest.fixture(scope="module")
def bundle_env(tmp_path_factory: pytest.TempPathFactory) -> SimpleNamespace:
    return fx.make_simulated_accepted_bundle(
        tmp_path_factory.mktemp("diag_inf_bundle")
    )


def _deep_update(base: dict[str, Any], changes: dict[str, Any] | None) -> dict[str, Any]:
    out = deepcopy(base)
    for key, value in (changes or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_update(out[key], value)
        else:
            out[key] = value
    return out


@pytest.fixture
def env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    bundle_env: SimpleNamespace,
) -> Callable[..., SimpleNamespace]:
    """Build a synthetic invocation with a GENUINE committed A2 activation.

    Every build creates a real I2 -> G2 -> A2 Git history whose tracked A2
    registry contains the requested (synthetic, test-only) bundle digest. The
    in-process registry is set from the committed A2 literal, i.e. exactly the
    state the imported module has at that revision.
    """
    counter = [0]

    def build(
        *,
        manifest_sha256: str | None = None,
        auth_changes: dict[str, Any] | None = None,
        input_doc: dict[str, Any] | None = None,
        auth_raw: str | None = None,
        input_raw: str | None = None,
        with_registry: bool = True,
        activation_kwargs: dict[str, Any] | None = None,
    ) -> SimpleNamespace:
        counter[0] += 1
        tag = f"activation_{counter[0]}"
        digest = manifest_sha256 or bundle_env.manifest_sha256
        activation = fx.build_activation_repo(
            tmp_path / tag,
            manifest_sha256=digest,
            **(activation_kwargs or {}),
        )
        monkeypatch.setattr(
            ds,
            "RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES",
            deepcopy(activation.committed_literal) if with_registry else {},
        )
        auth = _deep_update(activation.auth, auth_changes)
        private_dir = tmp_path / f"private_{counter[0]}"
        auth_path = fx.write_private_json(
            private_dir / "authorization.json", auth, raw=auth_raw
        )
        input_path = fx.write_private_json(
            private_dir / "input.json",
            input_doc if input_doc is not None else fx.make_input_doc(),
            raw=input_raw,
        )
        kwargs: dict[str, Any] = {
            "bundle_dir": bundle_env.bundle_dir,
            "trusted_local_root": bundle_env.trusted_root,
            "authorization_path": auth_path,
            "input_path": input_path,
            "operator_confirmation": ds.DIAGNOSTIC_OPERATOR_CONFIRMATION,
            "signing_key": bundle_env.signing_key,
            "repo_root": activation.repo,
            "lime_config": FAST_LIME,
            "lime_stability_seeds": FAST_LIME_SEEDS,
        }
        return SimpleNamespace(
            activation=activation,
            auth=auth,
            record=activation.record,
            auth_path=auth_path,
            input_path=input_path,
            kwargs=kwargs,
        )

    return build


def _copy_bundle(src: Path, parent: Path, name: str) -> Path:
    dest = parent / name
    ensure_private_directory(dest)
    for entry in sorted(src.iterdir()):
        target = dest / entry.name
        target.write_bytes(entry.read_bytes())
        protect_private_file(target)
    return dest


def _manifest_sha(bundle_dir: Path) -> str:
    return hashlib.sha256((bundle_dir / "manifest.json").read_bytes()).hexdigest()


def _resigned_bundle(
    tmp_path: Path,
    bundle_env: SimpleNamespace,
    mutation: Callable[[dict[str, Any]], None],
    *,
    name: str | None = None,
) -> tuple[Path, Path, str]:
    trusted_root = ensure_private_directory(tmp_path / "trusted_root")
    dest = _copy_bundle(
        bundle_env.bundle_dir,
        trusted_root,
        name or ds.DIAGNOSTIC_TARGET_BUNDLE["expected_bundle_dir_name"],
    )
    if name is not None and name != bundle_env.bundle_dir.name:
        marker_path = dest / BUNDLE_ACCEPTANCE_MARKER_FILENAME
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        marker["bundle_dir_name"] = name
        marker_path.write_text(json.dumps(marker, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        protect_private_file(marker_path)
    fx._resign_manifest(dest, bundle_env.signing_key, mutation)
    return trusted_root, dest, _manifest_sha(dest)


def _result_and_calibrator(bundle_env: SimpleNamespace) -> SimpleNamespace:
    predictor = ResearchCadPredictor.from_verified_bundle(
        bundle_env.bundle_dir,
        trusted_local_root=bundle_env.trusted_root,
        signing_key=bundle_env.signing_key,
    )
    result = predictor.predict_research_only(
        fx.make_synthetic_record(),
        lime_config=FAST_LIME,
        lime_stability_seeds=FAST_LIME_SEEDS,
    )
    calibrator = OofLogisticCalibrator.from_json_dict(
        json.loads(
            (bundle_env.bundle_dir / CALIBRATION_FILENAME).read_text(encoding="utf-8")
        )
    )
    return SimpleNamespace(predictor=predictor, result=result, calibrator=calibrator)


def _verify(result: Any, calibrator: Any, **kwargs: Any) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "reference": None,
        "calibrator": calibrator,
        "lime_requested": True,
        "lime_policy": LimeQualityPolicy(),
        "require_acceptable_lime_quality": False,
    }
    defaults.update(kwargs)
    return di.verify_diagnostic_result(result=result, **defaults)


# --------------------------------------------------------------------------- #
# 1. Happy path: score/calibration/SHAP/LIME and no side effects
# --------------------------------------------------------------------------- #


def test_diagnostic_happy_path_verifies_scores_shap_and_certified_lime(
    env: Callable[..., SimpleNamespace], bundle_env: SimpleNamespace
) -> None:
    built = env()
    before = {
        entry.name: hashlib.sha256(entry.read_bytes()).hexdigest()
        for entry in sorted(bundle_env.bundle_dir.iterdir())
    }
    report = di.run_offline_diagnostics(**built.kwargs)

    assert report["status"] == "OK"
    assert report["interface_version"] == ds.DIAGNOSTIC_INTERFACE_VERSION
    assert report["scope"]["approved_operations"] == list(
        ds.DIAGNOSTIC_ALLOWED_OPERATIONS
    )
    assert report["bundle"]["bundle_dir_name"] == bundle_env.bundle_dir.name
    assert report["bundle"]["post_run_acceptance_verified"] is True
    assert report["bundle"]["quarantine_marker_absent"] is True
    assert report["bundle"]["manifest_sha256"] == bundle_env.manifest_sha256
    assert report["bundle"]["ordered_feature_names"] == [
        "age", "sex", "cp", "trestbps", "restecg"
    ]
    assert report["input"]["contains_patient_data"] is False
    assert report["verification"]["no_api_serving"] is True
    assert report["verification"]["no_telemetry"] is True
    assert report["verification"]["no_uploads"] is True
    assert report["governance"]["serving_eligibility"] == "RESEARCH_ONLY"
    assert report["governance"]["gate_pt_p3"] == "CLOSED"

    record = report["records"][0]
    scores = record["scores"]
    assert scores["passed"] is True and scores["deterministic_on_repeat"] is True
    assert 0.0 < scores["raw_model_score"] < 1.0
    assert 0.0 < scores["calibrated_research_score"] < 1.0
    assert scores["calibrated_research_score"] == pytest.approx(
        float(expit(scores["calibrated_log_odds"])), abs=1e-12
    )
    assert scores["recomputed_calibrated_log_odds"] == pytest.approx(
        scores["calibrated_log_odds"], abs=1e-9
    )
    shap = record["shap"]
    assert shap["passed"] is True and shap["sum_check_passed"] is True
    assert shap["explained_quantity"] == "calibrated_log_odds"
    assert shap["additive_on_calibrated_probability"] is False
    assert shap["base_value"] + shap["sum_of_attributions"] == pytest.approx(
        shap["target_prediction_on_scale"], abs=1e-7
    )
    assert [a["feature_name"] for a in shap["attributions"]] == [
        "age", "sex", "cp", "trestbps", "restecg"
    ]
    lime = record["lime"]
    assert lime["requested"] is True
    assert lime["status"] == "ACCEPTABLE_LOCAL_APPROXIMATION"
    assert lime["feature_weights_trusted"] is True
    assert set(lime["feature_weights"]) == {"age", "sex", "cp", "trestbps", "restecg"}
    assert all(math.isfinite(v) for v in lime["feature_weights"].values())
    assert len(lime["seeds"]) >= 3
    assert lime["comparability"]["comparable"] is True
    assert record["all_exact_checks_passed"] is True
    assert record["lime_weights_trusted"] is True

    serialized = json.dumps(report, allow_nan=False, sort_keys=True)
    assert str(bundle_env.bundle_dir) not in serialized
    assert str(bundle_env.key_path) not in serialized
    assert bundle_env.signing_key.hex() not in serialized
    after = {
        entry.name: hashlib.sha256(entry.read_bytes()).hexdigest()
        for entry in sorted(bundle_env.bundle_dir.iterdir())
    }
    assert after == before, "diagnostic inference must never modify the accepted bundle"


def test_no_lime_request_emits_no_lime_weights(
    env: Callable[..., SimpleNamespace]
) -> None:
    built = env()
    kwargs = dict(built.kwargs)
    kwargs["with_lime"] = False
    kwargs["lime_config"] = None
    kwargs["lime_stability_seeds"] = None
    report = di.run_offline_diagnostics(**kwargs)
    lime = report["records"][0]["lime"]
    assert lime["requested"] is False
    assert lime["feature_weights"] is None
    assert lime["feature_weights_trusted"] is False
    assert report["records"][0]["lime_weights_trusted"] is False


def test_low_quality_lime_weights_are_never_trusted(
    env: Callable[..., SimpleNamespace]
) -> None:
    built = env()
    impossible_policy = LimeQualityPolicy(min_effective_samples=1e9)
    report = di.run_offline_diagnostics(
        **{**built.kwargs, "lime_quality_policy": impossible_policy}
    )
    lime = report["records"][0]["lime"]
    assert lime["status"] != "ACCEPTABLE_LOCAL_APPROXIMATION"
    assert lime["feature_weights_trusted"] is False
    assert lime["feature_weights"] is None
    assert "deliberately omitted" in lime["weights_suppression_reason"]
    assert lime["quality"]["is_reliable_for_interpretation"] is False
    assert report["records"][0]["lime_weights_trusted"] is False

    with pytest.raises(di.DiagnosticIntegrityError) as exc:
        di.run_offline_diagnostics(
            **{
                **built.kwargs,
                "lime_quality_policy": impossible_policy,
                "require_acceptable_lime_quality": True,
            }
        )
    assert exc.value.code == "diagnostic_lime_quality_not_acceptable"


def test_lime_stability_assessment_is_mandatory(
    env: Callable[..., SimpleNamespace]
) -> None:
    built = env()
    with pytest.raises(di.DiagnosticIntegrityError) as exc:
        di.run_offline_diagnostics(**{**built.kwargs, "lime_stability_seeds": None})
    assert exc.value.code == "diagnostic_lime_stability_missing"


def test_repeated_records_are_bounded(
    env: Callable[..., SimpleNamespace]
) -> None:
    built = env()
    records = [fx.make_synthetic_record(age=40.0 + i) for i in range(3)]
    # Point the input file at the three-record envelope.
    built.input_path.write_text(
        json.dumps(fx.make_input_doc(records)), encoding="utf-8"
    )
    protect_private_file(built.input_path)
    report = di.run_offline_diagnostics(**built.kwargs)
    assert report["input"]["record_count"] == 3
    assert [r["record_index"] for r in report["records"]] == [0, 1, 2]
    assert all(r["all_exact_checks_passed"] for r in report["records"])


# --------------------------------------------------------------------------- #
# 2. Authorization / provenance gates
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("auth_changes", "expected_code"),
    [
        ({"scope_id": "UNRATIFIED-SCOPE"}, "diagnostic_scope_id_mismatch"),
        ({"authorization_status": "FORGED_APPROVAL"}, "diagnostic_authorization_not_effective"),
        ({"supervisor_signoff_claimed": True}, "diagnostic_supervisor_signoff_claimed"),
        ({"human_attestation": "unbounded"}, "diagnostic_human_attestation_invalid"),
        ({"execution_boundary": {"api_serving": True}}, "diagnostic_execution_boundary_invalid"),
        ({"execution_boundary": {"telemetry": True}}, "diagnostic_execution_boundary_invalid"),
        ({"execution_boundary": {"uploads": True}}, "diagnostic_execution_boundary_invalid"),
        ({"input_declaration": {"contains_patient_data": True}}, "diagnostic_input_declaration_invalid"),
        ({"ratified_by": "someone-else"}, "diagnostic_scope_claim_mismatch"),
    ],
)
def test_unauthorized_operator_or_provenance_fails_closed(
    env: Callable[..., SimpleNamespace],
    auth_changes: dict[str, Any],
    expected_code: str,
) -> None:
    built = env(auth_changes=auth_changes)
    with pytest.raises(ds.DiagnosticScopeError) as exc:
        di.run_offline_diagnostics(**built.kwargs)
    assert exc.value.code == expected_code


def test_training_scope_alone_does_not_authorize_inference(
    env: Callable[..., SimpleNamespace]
) -> None:
    """Empty new registry: training amendment + acceptance marker are insufficient."""
    built = env(with_registry=False)
    with pytest.raises(ds.DiagnosticScopeError) as exc:
        di.run_offline_diagnostics(**built.kwargs)
    assert exc.value.code == "diagnostic_scope_not_ratified"


def test_wrong_signing_key_and_untrusted_root_fail_closed(
    env: Callable[..., SimpleNamespace], tmp_path: Path
) -> None:
    built = env()
    with pytest.raises(BundleIntegrityError) as bad_key:
        di.run_offline_diagnostics(**{**built.kwargs, "signing_key": b"x" * 32})
    assert bad_key.value.code in {
        "untrusted_bundle_producer_signature",
        "missing_local_producer_attestation",
    }
    ensure_private_directory(tmp_path / "unrelated_root")
    with pytest.raises(BundleIntegrityError) as bad_root:
        di.run_offline_diagnostics(
            **{**built.kwargs, "trusted_local_root": tmp_path / "unrelated_root"}
        )
    assert bad_root.value.code == "untrusted_bundle_location"


def test_quarantine_absent_acceptance_and_tampered_marker_fail_closed(
    env: Callable[..., SimpleNamespace],
    bundle_env: SimpleNamespace,
    tmp_path: Path,
) -> None:
    quarantine_root, quarantine_dir, quarantine_sha = _resigned_bundle(
        tmp_path / "quarantine_case", bundle_env, lambda m: None
    )
    write_bundle_quarantine_marker(
        quarantine_dir,
        reason_code="synthetic_test_quarantine",
        detail="Synthetic post-run failure simulation.",
    )
    built = env(
        manifest_sha256=quarantine_sha,
    )
    with pytest.raises(BundleIntegrityError) as quarantined:
        di.run_offline_diagnostics(
            **{
                **built.kwargs,
                "bundle_dir": quarantine_dir,
                "trusted_local_root": quarantine_root,
            }
        )
    assert quarantined.value.code == "bundle_quarantined_not_accepted"

    missing_root, missing_dir, missing_sha = _resigned_bundle(
        tmp_path / "missing_acceptance_case", bundle_env, lambda m: None
    )
    (missing_dir / BUNDLE_ACCEPTANCE_MARKER_FILENAME).unlink()
    built_missing = env(
        manifest_sha256=missing_sha,
    )
    with pytest.raises(BundleIntegrityError) as no_marker:
        di.run_offline_diagnostics(
            **{
                **built_missing.kwargs,
                "bundle_dir": missing_dir,
                "trusted_local_root": missing_root,
            }
        )
    assert no_marker.value.code == "bundle_post_run_acceptance_missing"

    # Even if the packaging-level gate were bypassed for pre-acceptance custody
    # inspection, the diagnostic interface's OWN explicit layout check refuses.
    descriptor = verify_trusted_local_bundle(
        missing_dir,
        trusted_local_root=missing_root,
        signing_key=bundle_env.signing_key,
        _require_post_run_acceptance=False,
    )
    context = ds.validate_diagnostic_scope(
        built_missing.auth, repo_root=built_missing.kwargs["repo_root"]
    )
    with pytest.raises(di.DiagnosticIntegrityError) as explicit:
        di.verify_accepted_bundle_identity(descriptor, scope=context)
    assert explicit.value.code == "diagnostic_bundle_layout_invalid"

    tampered_root, tampered_dir, tampered_sha = _resigned_bundle(
        tmp_path / "tampered_marker_case", bundle_env, lambda m: None
    )
    marker_path = tampered_dir / BUNDLE_ACCEPTANCE_MARKER_FILENAME
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    marker["expected_source_sha256"] = "0" * 64
    marker_path.write_text(json.dumps(marker, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    protect_private_file(marker_path)
    built_tampered = env(
        manifest_sha256=tampered_sha,
    )
    with pytest.raises(BundleIntegrityError) as bad_marker:
        di.run_offline_diagnostics(
            **{
                **built_tampered.kwargs,
                "bundle_dir": tampered_dir,
                "trusted_local_root": tampered_root,
            }
        )
    assert bad_marker.value.code == "bundle_post_run_acceptance_mismatch"


def test_exact_bundle_identity_and_manifest_digest_mismatch_fail_closed(
    env: Callable[..., SimpleNamespace],
    bundle_env: SimpleNamespace,
    tmp_path: Path,
) -> None:
    wrong_sha = "0" * 64
    built = env(
        manifest_sha256=wrong_sha,
    )
    with pytest.raises(di.DiagnosticIntegrityError) as digest_exc:
        di.run_offline_diagnostics(**built.kwargs)
    assert digest_exc.value.code == "diagnostic_manifest_digest_mismatch"

    mutations: list[tuple[str, Callable[[dict[str, Any]], None], str]] = [
        (
            "model_id",
            lambda m: m["model"].update(model_id="another_model"),
            "diagnostic_bundle_identity_mismatch",
        ),
        (
            "selected_c",
            lambda m: m["model"].update(selected_hyperparameters={"C": 1.0}),
            "diagnostic_bundle_identity_mismatch",
        ),
        (
            "execution_profile",
            lambda m: m["model"].update(execution_profile="AI1_GENERIC_V1"),
            "diagnostic_bundle_identity_mismatch",
        ),
        (
            "real_provenance_flag",
            lambda m: m["eligibility"].update(synthetic_only=True),
            "diagnostic_bundle_provenance_invalid",
        ),
    ]
    for index, (_label, mutation, expected_code) in enumerate(mutations):
        root, dest, new_sha = _resigned_bundle(
            tmp_path / f"identity_case_{index}", bundle_env, mutation
        )
        built_mutated = env(
            manifest_sha256=new_sha,
        )
        with pytest.raises(Exception) as raised:
            di.run_offline_diagnostics(
                **{
                    **built_mutated.kwargs,
                    "bundle_dir": dest,
                    "trusted_local_root": root,
                }
            )
        assert getattr(raised.value, "code", None) == expected_code

    renamed_root, renamed_dir, renamed_sha = _resigned_bundle(
        tmp_path / "renamed_case",
        bundle_env,
        lambda m: None,
        name="different_accepted_bundle",
    )
    built_renamed = env(
        manifest_sha256=renamed_sha,
    )
    with pytest.raises(di.DiagnosticIntegrityError) as renamed:
        di.run_offline_diagnostics(
            **{
                **built_renamed.kwargs,
                "bundle_dir": renamed_dir,
                "trusted_local_root": renamed_root,
            }
        )
    assert renamed.value.code == "diagnostic_bundle_identity_mismatch"


def test_synthetic_provenance_bundle_is_not_the_accepted_real_bundle(
    env: Callable[..., SimpleNamespace],
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    synthetic_bundle = fx.make_simulated_accepted_bundle(
        tmp_path_factory.mktemp("diag_synthetic_only_bundle"), simulate_real=False
    )
    built = env(
        manifest_sha256=synthetic_bundle.manifest_sha256,
    )
    with pytest.raises(di.DiagnosticIntegrityError) as exc:
        di.run_offline_diagnostics(
            **{
                **built.kwargs,
                "bundle_dir": synthetic_bundle.bundle_dir,
                "trusted_local_root": synthetic_bundle.trusted_root,
                "signing_key": synthetic_bundle.signing_key,
            }
        )
    assert exc.value.code == "diagnostic_bundle_provenance_invalid"


def test_wrong_registered_panel_in_descriptor_fails_closed(
    env: Callable[..., SimpleNamespace], bundle_env: SimpleNamespace
) -> None:
    built = env()
    descriptor = verify_trusted_local_bundle(
        bundle_env.bundle_dir,
        trusted_local_root=bundle_env.trusted_root,
        signing_key=bundle_env.signing_key,
    )
    wrong_panel = dataclasses.replace(descriptor, panel=DA_A2_RESTING_LABS_PANEL)
    context = ds.validate_diagnostic_scope(built.auth, repo_root=built.kwargs["repo_root"])
    with pytest.raises(di.DiagnosticIntegrityError) as exc:
        di.verify_accepted_bundle_identity(wrong_panel, scope=context)
    assert exc.value.code == "diagnostic_bundle_panel_mismatch"


# --------------------------------------------------------------------------- #
# 3. Synthetic input declaration and schema
# --------------------------------------------------------------------------- #


def _mutate_record(changes: dict[str, Any]) -> dict[str, Any]:
    doc = fx.make_input_doc()
    doc["records"][0] = _deep_update(doc["records"][0], changes)
    return doc


@pytest.mark.parametrize(
    ("input_doc", "input_raw", "expected_code"),
    [
        (_deep_update(fx.make_input_doc(), {"synthetic": False}), None,
         "diagnostic_input_not_declared_synthetic"),
        (_deep_update(fx.make_input_doc(), {"input_declaration": {"records_are_synthetic": False}}), None,
         "diagnostic_input_declaration_invalid"),
        (_deep_update(fx.make_input_doc(), {"input_declaration": {"contains_patient_data": True}}), None,
         "diagnostic_input_declaration_invalid"),
        (_deep_update(fx.make_input_doc(), {"input_declaration": {"panel_id": "da_a2_resting_labs_v1"}}), None,
         "diagnostic_input_declaration_invalid"),
        (_mutate_record({"synthetic": False}), None,
         "diagnostic_non_synthetic_input_rejected"),
        (_mutate_record({"panel_id": "da_a2_resting_labs_v1"}), None,
         "diagnostic_input_panel_mismatch"),
        (_mutate_record({"features": {"chol": 200}}), None,
         "diagnostic_input_wrong_panel_schema"),
        (_mutate_record({"features": {"spo2": 98}}), None,
         "diagnostic_input_wrong_panel_schema"),
        (_mutate_record({"context": {"track": "B", "source": "wearable"}}), None,
         "diagnostic_input_prohibited_source"),
        (_mutate_record({"features": {"age": None}}), None,
         "diagnostic_input_missing_required_feature"),
        (_mutate_record({"features": {"age": True}}), None,
         "invalid_numeric_value"),
        (_mutate_record({"units": {"age": "months"}}), None,
         "unit_mismatch"),
        (fx.make_input_doc([fx.make_synthetic_record() for _ in range(ds.DIAGNOSTIC_MAX_RECORDS + 1)]), None,
         "diagnostic_input_record_count_invalid"),
        (None, '{"a": 1, "a": 2}', "diagnostic_duplicate_json_key"),
        (None, '{"a": NaN}', "diagnostic_non_finite_json_constant"),
        (None, '{"a": 1e400}', "diagnostic_non_finite_local_value"),
        (None, "not-json", "diagnostic_malformed_local_json"),
    ],
)
def test_malformed_wrong_panel_or_non_finite_inputs_fail_closed(
    env: Callable[..., SimpleNamespace],
    input_doc: dict[str, Any] | None,
    input_raw: str | None,
    expected_code: str,
) -> None:
    built = env(input_doc=input_doc, input_raw=input_raw)
    with pytest.raises(Exception) as exc:
        di.run_offline_diagnostics(**built.kwargs)
    assert getattr(exc.value, "code", None) == expected_code


def test_non_finite_feature_value_in_valid_envelope_fails_closed(
    env: Callable[..., SimpleNamespace]
) -> None:
    doc = fx.make_input_doc()
    raw = json.dumps(doc).replace('"age": 54.0', '"age": 1e400')
    assert "1e400" in raw
    built = env(input_raw=raw)
    with pytest.raises(ds.DiagnosticScopeError) as exc:
        di.run_offline_diagnostics(**built.kwargs)
    assert exc.value.code == "diagnostic_non_finite_local_value"


def test_wrong_panel_is_rejected_before_any_bundle_verification(
    env: Callable[..., SimpleNamespace], monkeypatch: pytest.MonkeyPatch
) -> None:
    built = env(input_doc=_mutate_record({"features": {"chol": 200}}))
    called: list[bool] = []

    def _boom(*_args: Any, **_kwargs: Any) -> Any:
        called.append(True)
        raise AssertionError("bundle verification must not run for an invalid input")

    monkeypatch.setattr(di, "verify_trusted_local_bundle", _boom)
    with pytest.raises(di.DiagnosticIntegrityError) as exc:
        di.run_offline_diagnostics(**built.kwargs)
    assert exc.value.code == "diagnostic_input_wrong_panel_schema"
    assert called == []


def test_load_diagnostic_input_accepts_registered_optional_missing_field(
    tmp_path: Path,
) -> None:
    record = fx.make_synthetic_record()
    del record["features"]["trestbps"]
    del record["units"]["trestbps"]
    record["missing_reasons"] = {"trestbps": "not_provided"}
    path = fx.write_private_json(
        tmp_path / "private" / "input.json", fx.make_input_doc([record])
    )
    records = di.load_diagnostic_input(
        path, repo_root=tmp_path / "other_checkout_not_this_dir"
    )
    assert len(records) == 1
    assert records[0]["missing_reasons"]["trestbps"] == "not_provided"


# --------------------------------------------------------------------------- #
# 4. Independent post-hoc verification of scores / SHAP / LIME
# --------------------------------------------------------------------------- #


def test_independent_verifier_rejects_non_finite_and_inconsistent_scores(
    bundle_env: SimpleNamespace,
) -> None:
    ctx = _result_and_calibrator(bundle_env)
    assert _verify(ctx.result, ctx.calibrator)["all_exact_checks_passed"] is True

    cases: list[tuple[Any, str]] = [
        (
            dataclasses.replace(ctx.result, calibrated_research_score=float("nan")),
            "diagnostic_non_finite_value",
        ),
        (
            dataclasses.replace(ctx.result, raw_model_log_odds=float("inf")),
            "diagnostic_non_finite_value",
        ),
        (
            dataclasses.replace(ctx.result, calibrated_log_odds=0.0),
            "diagnostic_score_scale_inconsistent",
        ),
        (
            dataclasses.replace(
                ctx.result, uncertainty={"descriptive": float("nan")}
            ),
            "diagnostic_non_finite_value",
        ),
        (
            dataclasses.replace(
                ctx.result,
                explanation=dataclasses.replace(
                    ctx.result.explanation, sum_check_passed=False
                ),
            ),
            "diagnostic_shap_not_exact",
        ),
        (
            dataclasses.replace(
                ctx.result,
                explanation=dataclasses.replace(
                    ctx.result.explanation,
                    base_value=ctx.result.explanation.base_value + 1.0,
                ),
            ),
            "diagnostic_shap_decomposition_failed",
        ),
        (
            dataclasses.replace(
                ctx.result,
                explanation=dataclasses.replace(
                    ctx.result.explanation, explained_quantity="raw_model_score"
                ),
            ),
            "diagnostic_shap_target_misaligned",
        ),
        (
            dataclasses.replace(ctx.result, lime_explanation=None),
            "diagnostic_lime_request_mismatch",
        ),
        (
            dataclasses.replace(ctx.result, lime_stability=None),
            "diagnostic_lime_stability_missing",
        ),
        (
            dataclasses.replace(ctx.result, lime_comparability={"comparable": False}),
            "diagnostic_lime_scale_mismatch",
        ),
    ]
    for result, expected_code in cases:
        with pytest.raises(di.DiagnosticIntegrityError) as exc:
            _verify(result, ctx.calibrator)
        assert exc.value.code == expected_code


def test_independent_verifier_rejects_miscalibrated_output(
    bundle_env: SimpleNamespace,
) -> None:
    ctx = _result_and_calibrator(bundle_env)

    class _WrongCalibrator:
        def calibrated_log_odds(self, *_args: Any, **_kwargs: Any) -> float:
            return ctx.result.calibrated_log_odds + 1.0

    with pytest.raises(di.DiagnosticIntegrityError) as exc:
        _verify(ctx.result, _WrongCalibrator())
    assert exc.value.code == "diagnostic_calibration_mismatch"


def test_independent_verifier_rejects_non_finite_lime_weight(
    bundle_env: SimpleNamespace,
) -> None:
    ctx = _result_and_calibrator(bundle_env)
    lime = ctx.result.lime_explanation
    assert lime is not None
    bad_attributions = (
        dataclasses.replace(lime.attributions[0], lime_weight=float("nan")),
        *lime.attributions[1:],
    )
    result = dataclasses.replace(
        ctx.result,
        lime_explanation=dataclasses.replace(lime, attributions=bad_attributions),
    )
    with pytest.raises(di.DiagnosticIntegrityError) as exc:
        _verify(result, ctx.calibrator)
    assert exc.value.code == "diagnostic_non_finite_value"


# --------------------------------------------------------------------------- #
# 5. Separate CLI and general-CLI preservation
# --------------------------------------------------------------------------- #


def test_diagnostic_cli_happy_path_and_fail_closed_output(
    env: Callable[..., SimpleNamespace],
    bundle_env: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    built = env()
    argv = [
        "--bundle-dir", str(built.kwargs["bundle_dir"]),
        "--trusted-root", str(built.kwargs["trusted_local_root"]),
        "--authorization", str(built.kwargs["authorization_path"]),
        "--input", str(built.kwargs["input_path"]),
        "--operator-confirmation", ds.DIAGNOSTIC_OPERATOR_CONFIRMATION,
        "--signing-key-path", str(bundle_env.key_path),
        "--repo-root", str(built.kwargs["repo_root"]),
        "--lime-perturbations", "64",
        "--lime-seed", "4321",
    ]
    rc = di.main(argv)
    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["status"] == "OK"
    assert payload["records"][0]["all_exact_checks_passed"] is True
    assert str(built.kwargs["bundle_dir"]) not in captured.out

    # Empty registry -> fail-closed structured error, no report, no path leakage.
    ds.RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES.clear()
    rc_bad = di.main(argv)
    captured_bad = capsys.readouterr()
    assert rc_bad == 2
    error = json.loads(captured_bad.err)
    assert error["status"] == "FAIL_CLOSED"
    assert error["error"]["code"] == "diagnostic_scope_not_ratified"
    assert str(built.kwargs["bundle_dir"]) not in captured_bad.err


def test_authorization_template_is_explicitly_non_authorizing() -> None:
    template = json.loads(
        (REPO_ROOT / "ai" / "examples" / "diagnostic_authorization.template.json").read_text(
            encoding="utf-8"
        )
    )
    assert template["authorization_status"] == "TEMPLATE_NOT_AUTHORIZED"
    with pytest.raises(ds.DiagnosticScopeError) as exc:
        ds.validate_local_authorization(
            template, operator_confirmation=ds.DIAGNOSTIC_OPERATOR_CONFIRMATION
        )
    assert exc.value.code == "diagnostic_authorization_not_effective"


def test_example_synthetic_input_file_is_valid(tmp_path: Path) -> None:
    doc = json.loads(
        (
            REPO_ROOT
            / "ai"
            / "examples"
            / "diagnostic_synthetic_records_da_a2_resting_v1.json"
        ).read_text(encoding="utf-8")
    )
    path = fx.write_private_json(tmp_path / "private" / "input.json", doc)
    records = di.load_diagnostic_input(
        path, repo_root=tmp_path / "other_checkout_not_this_dir"
    )
    assert len(records) == 2
    assert all(record["synthetic"] is True for record in records)
    assert all(
        set(record["features"]) == {"age", "sex", "cp", "trestbps", "restecg"}
        for record in records
    )


def test_cli_redaction_never_removes_punctuation_for_dot_repo_root() -> None:
    import argparse

    args = argparse.Namespace(
        bundle_dir=None,
        trusted_local_root=None,
        authorization=None,
        input=None,
        signing_key_path=None,
        repo_root=Path("."),
    )
    tokens = di._redaction_tokens(args)
    assert "." not in tokens
    assert di._redact("Scope not ratified. No bundle loaded.", tokens) == (
        "Scope not ratified. No bundle loaded."
    )


def test_general_synthetic_cli_still_refuses_real_provenance_bundle(
    bundle_env: SimpleNamespace,
) -> None:
    descriptor = verify_trusted_local_bundle(
        bundle_env.bundle_dir,
        trusted_local_root=bundle_env.trusted_root,
        signing_key=bundle_env.signing_key,
    )
    assessment = bundle_provenance_assessment(descriptor.manifest)
    assert assessment["cli_block_code"] == "cli_real_provenance_bundle_not_supported"
    assert assessment["provenance_cli_compatible"] is False
    with pytest.raises(BundleIntegrityError) as exc:
        assert_cli_predict_supported(descriptor.manifest)
    assert exc.value.code == "cli_real_provenance_bundle_not_supported"
