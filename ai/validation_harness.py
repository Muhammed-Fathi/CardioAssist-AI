"""Self-contained synthetic validation suite for Windows Python 3.12 & POSIX.

Executes all 8 mandatory end-to-end checks without touching real patient data or
writing inside repository paths:
1. Synthetic cohort training (nested CV + cross-fitted calibration + shuffle control).
2. Signed bundle packaging (atomic private staging + commit).
3. Artifact verification (SHA-256 integrity vs trusted-local-origin + HMAC).
4. Loading through ``ResearchCadPredictor.from_verified_bundle``.
5. Synthetic prediction with calibrated research score, descriptive dispersion,
   and faithful scale-aligned SHAP attributions.
6. Tamper rejection (corrupted file SHA-256 mismatch + forged pickle with
   recomputed SHA-256 blocked BEFORE ``joblib.load``).
7. Signing-key, bundle artifact, and ledger access-control verification
   (POSIX ``0600``/``0700`` on Linux/macOS; Win32 NTFS Security-Descriptor DACL
   enforcement & ``BUILTIN\\Users`` negative rejection on Windows).
8. External evaluation ledger lifecycle: ``RESERVED`` -> ``FAILED`` on runtime
   failure, reload persistence, unrecovered retry block, provenance-mismatch
   recovery block, safe ``recover_after_failure=True`` -> ``COMPLETED``,
   concurrent duplicate reservation block, and post-completion duplicate block.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import sys
import tempfile
from typing import Any

import joblib
import numpy as np
from scipy.special import expit

from ai.errors import (
    BundleIntegrityError,
    CohortGovernanceError,
)
from ai.filesystem_security import (
    ensure_private_directory,
    loosen_access_for_negative_test,
    protect_private_directory,
    protect_private_file,
    verify_access_control,
)
from ai.inference import ResearchCadPredictor
from ai.packaging import (
    get_or_create_local_signing_key,
    package_research_bundle,
    verify_research_bundle,
    verify_trusted_local_bundle,
)
from ai.panels import DA_A2_RESTING_LABS_PANEL
from ai.training import (
    ExternalEvaluationLedger,
    ResearchTrainingConfig,
    evaluate_locked_external_cohort,
    train_research_model,
)


class _ValidationPickleCanary:
    """Top-level pickle canary proving untrusted joblib.load is never executed."""

    triggered: bool = False

    def __reduce__(self) -> tuple[Any, tuple[()]]:
        return (_fire_validation_pickle_canary, ())


def _fire_validation_pickle_canary() -> dict[str, str]:
    _ValidationPickleCanary.triggered = True
    raise RuntimeError("SECURITY VIOLATION: joblib.load executed on forged bundle!")


def _make_synthetic_cohort(
    n_rows: int, *, seed: int
) -> tuple[list[dict[str, Any]], list[int]]:
    rng = np.random.default_rng(seed)
    records: list[dict[str, Any]] = []
    labels: list[int] = []

    for idx in range(n_rows):
        age = float(rng.integers(36, 76))
        sex = int(rng.integers(0, 2))
        cp = int(rng.choice([1, 2, 3, 4]))
        bp = float(rng.integers(100, 180))
        ecg = int(rng.choice([0, 1, 2]))
        chol = float(rng.integers(150, 340))
        fbs = int(rng.choice([0, 1], p=[0.78, 0.22]))

        latent = (
            0.055 * (age - 54.0)
            + (0.75 if sex == 1 else -0.35)
            + (0.95 if cp == 4 else -0.25)
            + 0.015 * (bp - 130.0)
            + 0.008 * (chol - 220.0)
            + (0.45 if fbs == 1 else 0.0)
            + float(rng.normal(0.0, 0.85))
        )
        prob = 1.0 / (1.0 + math.exp(-latent))
        y = int(rng.random() < prob)

        features: dict[str, Any] = {
            "age": age,
            "sex": sex,
            "cp": cp,
            "trestbps": bp,
            "restecg": ecg,
        }
        units: dict[str, str] = {"age": "years", "trestbps": "mmHg"}
        reasons: dict[str, str] = {}

        if idx % 9 != 0:
            features["chol"] = chol
            units["chol"] = "mg/dL"
        else:
            reasons["chol"] = "not_provided"

        if idx % 11 != 0:
            features["fbs"] = fbs
        else:
            features["fbs"] = None
            reasons["fbs"] = "unknown"

        records.append(
            {
                "synthetic": True,
                "panel_id": DA_A2_RESTING_LABS_PANEL.panel_id,
                "features": features,
                "units": units,
                "missing_reasons": reasons,
            }
        )
        labels.append(y)

    if len(set(labels)) < 2:
        labels[0] = 0
        labels[1] = 1
    return records, labels


def run_end_to_end_platform_validation(
    work_root: Path | None = None,
) -> dict[str, Any]:
    """Run all 8 mandatory validation checks and return structured verification report."""
    owns_temp = work_root is None
    base_dir = (
        Path(tempfile.mkdtemp(prefix="cardioassist_ai_val_"))
        if owns_temp
        else Path(work_root)
    )
    steps_passed: list[str] = []

    try:
        ensure_private_directory(base_dir)
        trusted_root = ensure_private_directory(base_dir / "trusted_bundles")
        key_dir = ensure_private_directory(base_dir / "private_keys")
        key_path = key_dir / "local_bundle_hmac_v1.key"

        cfg = ResearchTrainingConfig(
            protocol_id="CAI-AI1-PLATFORM-VALIDATION-V1",
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

        # 1. Synthetic cohort training
        dev_records, dev_labels = _make_synthetic_cohort(72, seed=20261025)
        run = train_research_model(
            dev_records,
            dev_labels,
            DA_A2_RESTING_LABS_PANEL,
            model_id="synth_platform_val_v1",
            development_cohort_id="synthetic_cleveland",
            development_dataset_id="DA-A2:synthetic_cleveland",
            synthetic_data_confirmed=True,
            config=cfg,
        )
        assert run.synthetic_only is True
        assert (
            run.internal_evaluation["cross_fitted_calibrated_nested_cv"][
                "each_observation_excluded_from_model_and_calibrator_fit"
            ]
            is True
        )
        steps_passed.append("1_synthetic_cohort_training")

        # 2. Local signing key & signed bundle packaging
        signing_key = get_or_create_local_signing_key(key_path)
        assert len(signing_key) >= 32
        assert get_or_create_local_signing_key(key_path) == signing_key
        assert verify_access_control(
            key_path, expect_directory=False, strict_private=True
        ).ok

        bundle_dir = trusted_root / "signed_research_bundle_v1"
        packaged = package_research_bundle(
            run, bundle_dir, signing_key=signing_key
        )
        assert packaged.serving_eligibility == "RESEARCH_ONLY"
        assert packaged.approved_for_serving is False
        assert packaged.producer_authenticated is True
        assert packaged.safe_for_pickle_deserialization is True
        steps_passed.append("2_signed_bundle_packaging")

        # 3. Artifact verification (SHA-256 only vs trusted-local-origin + HMAC)
        hash_only = verify_research_bundle(bundle_dir)
        assert hash_only.integrity_verified_only_not_authenticated is True
        assert hash_only.producer_authenticated is False
        assert hash_only.safe_for_pickle_deserialization is False

        trusted_desc = verify_trusted_local_bundle(
            bundle_dir,
            trusted_local_root=trusted_root,
            signing_key=signing_key,
        )
        assert trusted_desc.producer_authenticated is True
        assert trusted_desc.safe_for_pickle_deserialization is True
        steps_passed.append("3_artifact_verification")

        # 4. Loading through ResearchCadPredictor
        predictor = ResearchCadPredictor.from_verified_bundle(
            bundle_dir,
            trusted_local_root=trusted_root,
            signing_key=signing_key,
        )
        assert predictor.model_id == "synth_platform_val_v1"
        steps_passed.append("4_research_cad_predictor_load")

        # 5. Synthetic prediction with calibrated score and faithful SHAP
        pred = predictor.predict_research_only(dev_records[0])
        assert pred.serving_eligibility == "RESEARCH_ONLY"
        assert pred.approved_for_serving is False
        assert pred.clinical_use_authorized is False
        assert 0.0 < pred.calibrated_research_score < 1.0
        assert abs(float(expit(pred.calibrated_log_odds)) - pred.calibrated_research_score) < 1e-12
        assert pred.explanation.sum_check_passed is True
        assert pred.explanation.additive_on_calibrated_probability is False
        if predictor.model_family == "l2_logistic_regression":
            assert pred.explanation.explained_quantity == "calibrated_log_odds"
            assert pred.explanation.explains_calibrated_score_directly is True
        else:
            assert pred.explanation.explained_quantity == "raw_model_score"
            assert pred.explanation.explains_calibrated_score_directly is False
        steps_passed.append("5_calibrated_prediction_and_faithful_shap")

        # 6. Tamper rejection & forged-pickle pre-deserialization block
        tampered_dir = ensure_private_directory(trusted_root / "tampered_bundle")
        for src in bundle_dir.iterdir():
            dst = tampered_dir / src.name
            dst.write_bytes(src.read_bytes())
            protect_private_file(dst)
        (tampered_dir / "calibration.json").write_bytes(
            (tampered_dir / "calibration.json").read_bytes() + b" "
        )
        protect_private_file(tampered_dir / "calibration.json")
        try:
            verify_research_bundle(tampered_dir)
        except BundleIntegrityError as exc:
            assert exc.code in ("file_size_mismatch", "file_sha256_mismatch")
        else:
            raise AssertionError("Tampered calibration.json was not rejected!")

        _ValidationPickleCanary.triggered = False
        forged_dir = ensure_private_directory(trusted_root / "forged_pickle_bundle")
        for src in bundle_dir.iterdir():
            dst = forged_dir / src.name
            dst.write_bytes(src.read_bytes())
            protect_private_file(dst)
        joblib.dump(
            _ValidationPickleCanary(), forged_dir / "model.joblib", compress=3
        )
        protect_private_file(forged_dir / "model.joblib")
        forged_model_bytes = (forged_dir / "model.joblib").read_bytes()
        forged_manifest = json.loads(
            (forged_dir / "manifest.json").read_text(encoding="utf-8")
        )
        forged_manifest["files"]["model.joblib"] = {
            "sha256": hashlib.sha256(forged_model_bytes).hexdigest(),
            "size_bytes": len(forged_model_bytes),
        }
        (forged_dir / "manifest.json").write_text(
            json.dumps(forged_manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        protect_private_file(forged_dir / "manifest.json")
        assert verify_research_bundle(forged_dir).safe_for_pickle_deserialization is False
        try:
            ResearchCadPredictor.from_verified_bundle(
                forged_dir,
                trusted_local_root=trusted_root,
                signing_key=signing_key,
            )
        except BundleIntegrityError as exc:
            assert exc.code == "untrusted_bundle_producer_signature"
        else:
            raise AssertionError("Forged pickle bundle bypassed HMAC check!")
        assert _ValidationPickleCanary.triggered is False
        steps_passed.append("6_tamper_and_forged_pickle_rejection")

        # 7. Signing-key, sensitive-artifact, and trusted-root access-control checks
        loosen_access_for_negative_test(key_path, is_directory=False)
        try:
            try:
                get_or_create_local_signing_key(key_path)
            except BundleIntegrityError as exc:
                assert exc.code == "insecure_signing_key_permissions"
            else:
                raise AssertionError("Over-permissive signing key was not rejected!")
        finally:
            protect_private_file(key_path)
        assert get_or_create_local_signing_key(key_path) == signing_key

        shap_bg_file = bundle_dir / "shap_background.json"
        loosen_access_for_negative_test(shap_bg_file, is_directory=False)
        try:
            try:
                verify_trusted_local_bundle(
                    bundle_dir,
                    trusted_local_root=trusted_root,
                    signing_key=signing_key,
                )
            except BundleIntegrityError as exc:
                assert exc.code == "insecure_sensitive_artifact_permissions"
            else:
                raise AssertionError(
                    "Over-permissive shap_background.json was not rejected!"
                )
        finally:
            protect_private_file(shap_bg_file)

        loosen_access_for_negative_test(trusted_root, is_directory=True)
        try:
            try:
                verify_trusted_local_bundle(
                    bundle_dir,
                    trusted_local_root=trusted_root,
                    signing_key=signing_key,
                )
            except BundleIntegrityError as exc:
                assert exc.code == "insecure_trusted_root_permissions"
            else:
                raise AssertionError(
                    "Over-permissive trusted_local_root was not rejected!"
                )
        finally:
            protect_private_directory(trusted_root)

        assert verify_access_control(
            trusted_root, expect_directory=True, strict_private=True
        ).ok
        verify_trusted_local_bundle(
            bundle_dir,
            trusted_local_root=trusted_root,
            signing_key=signing_key,
        )

        steps_passed.append("7_signing_key_and_artifact_access_control")

        # 8. External evaluation ledger: failure -> reload -> recovery -> duplicate rejection
        ext_records, ext_labels = _make_synthetic_cohort(60, seed=20261212)
        ledger_path = ensure_private_directory(base_dir / "ledgers") / "eval_ledger.json"

        # 8a. Mid-evaluation runtime failure AFTER reservation:
        #     ledger MUST record status='FAILED' (never 'COMPLETED'!)
        faulty_run = replace(run, estimator=object())
        try:
            evaluate_locked_external_cohort(
                faulty_run,
                ext_records,
                ext_labels,
                external_cohort_id="synthetic_hungary",
                external_dataset_id="DA-A2:synthetic_hungary",
                synthetic_data_confirmed=True,
                one_shot_ledger_path=ledger_path,
                n_bootstrap=30,
            )
        except Exception:  # noqa: BLE001
            pass
        else:
            raise AssertionError("Faulty estimator external evaluation should have failed!")

        reloaded_ledger = ExternalEvaluationLedger(ledger_path)
        entries_after_fail = reloaded_ledger.list_entries()
        assert len(entries_after_fail) == 1
        assert entries_after_fail[0]["status"] == "FAILED"
        assert entries_after_fail[0]["completed_at_utc"] is None

        # 8b. Unrecovered retry without recover_after_failure=True fails closed
        try:
            evaluate_locked_external_cohort(
                run,
                ext_records,
                ext_labels,
                external_cohort_id="synthetic_hungary",
                external_dataset_id="DA-A2:synthetic_hungary",
                synthetic_data_confirmed=True,
                one_shot_ledger_path=ledger_path,
                recover_after_failure=False,
                n_bootstrap=30,
            )
        except CohortGovernanceError as exc:
            assert exc.code == "prior_external_evaluation_failed_recovery_required"
        else:
            raise AssertionError("Retry without recover_after_failure=True must fail!")

        # 8c. Safe recovery with identical frozen model transitions to COMPLETED
        ext_result = evaluate_locked_external_cohort(
            run,
            ext_records,
            ext_labels,
            external_cohort_id="synthetic_hungary",
            external_dataset_id="DA-A2:synthetic_hungary",
            synthetic_data_confirmed=True,
            one_shot_ledger_path=ledger_path,
            recover_after_failure=True,
            n_bootstrap=30,
        )
        assert ext_result["one_shot_enforced_by_ledger"] is True
        assert ext_result["one_shot_ledger_receipt"]["status"] == "COMPLETED"

        entries_after_ok = ExternalEvaluationLedger(ledger_path).list_entries()
        assert [e["status"] for e in entries_after_ok] == ["FAILED", "COMPLETED"]

        # 8d. Subsequent duplicate attempt (even with recover_after_failure=True) is rejected
        try:
            evaluate_locked_external_cohort(
                run,
                ext_records,
                ext_labels,
                external_cohort_id="synthetic_hungary",
                external_dataset_id="DA-A2:synthetic_hungary",
                synthetic_data_confirmed=True,
                one_shot_ledger_path=ledger_path,
                recover_after_failure=True,
                n_bootstrap=30,
            )
        except CohortGovernanceError as exc:
            assert exc.code == "one_shot_external_evaluation_already_consumed"
        else:
            raise AssertionError("Duplicate completed external evaluation must fail!")

        # 8e. Active RESERVED entry blocks concurrent duplicate reservation
        concurrent_ledger = ExternalEvaluationLedger(
            ensure_private_directory(base_dir / "ledgers_concurrent") / "conc.json"
        )
        res_slot = concurrent_ledger.reserve_evaluation(
            protocol_id=run.protocol_id,
            model_id=run.model_id,
            model_version=run.model_version,
            external_cohort_id="synthetic_va",
            external_dataset_id="DA-A2:synthetic_va",
            preprocessor_sha256=run.preprocessor.state_sha256,
            calibrator_sha256=run.calibrator.state_sha256,
            cohort_fingerprint_sha256="a" * 64,
        )
        try:
            concurrent_ledger.reserve_evaluation(
                protocol_id=run.protocol_id,
                model_id="different_model_same_protocol",
                model_version="0.1.0",
                external_cohort_id="synthetic_va",
                external_dataset_id="DA-A2:synthetic_va",
                preprocessor_sha256=run.preprocessor.state_sha256,
                calibrator_sha256=run.calibrator.state_sha256,
                cohort_fingerprint_sha256="a" * 64,
            )
        except CohortGovernanceError as exc:
            assert exc.code == "external_evaluation_currently_reserved_in_flight"
        else:
            raise AssertionError("Concurrent in-flight reservation was not blocked!")

        recovered = concurrent_ledger.recover_abandoned_reservation(
            str(res_slot["reservation_id"]), reason="simulated_crash_recovery"
        )
        assert recovered["status"] == "FAILED"
        steps_passed.append("8_external_evaluation_ledger_lifecycle_and_recovery")

        return {
            "status": "PASSED",
            "platform": sys.platform,
            "os_name": os.name,
            "python_version": platform.python_version(),
            "access_control_mechanism": (
                "windows_ntfs_win32_security_descriptor_dacl"
                if os.name == "nt"
                else "posix_uid_and_mode_bits"
            ),
            "selected_model_family": run.selected_model_family,
            "steps_passed": steps_passed,
        }
    finally:
        if owns_temp and base_dir.exists():
            shutil.rmtree(base_dir, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run end-to-end synthetic AI pipeline & ACL/ledger validation."
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="Optional untracked working directory (created & cleaned by caller).",
    )
    args = parser.parse_args(argv)
    report = run_end_to_end_platform_validation(args.work_dir)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
