"""Offline RESEARCH_ONLY command-line interface for the Track A AI pipeline.

Invocation (from the repository root)::

    python -m ai panels
    python -m ai verify-bundle --bundle-dir <dir> --trusted-root <dir>
    python -m ai predict --bundle-dir <dir> --trusted-root <dir> --input <json>
    python -m ai demo [--work-dir <private-dir-outside-repo>]

Design boundaries (this module adds NO new inference engine, model, or
explainability method):

- ``predict`` delegates exclusively to
  :meth:`ai.inference.ResearchCadPredictor.predict_research_only` on a bundle
  loaded through :meth:`ResearchCadPredictor.from_verified_bundle`, so the
  existing trusted-local-root containment, platform ACL verification,
  SHA-256 integrity, HMAC-SHA256 producer authentication, quarantine, and
  post-run acceptance controls all run BEFORE any ``joblib.load``.
- This CLI is a *synthetic demo* surface. Prediction is supported only for
  synthetic-provenance bundles (``eligibility.synthetic_only is True``,
  ``execution_mode == "SYNTHETIC_RESEARCH"``, no ``research_authorization``)
  under the generic ``AI1_GENERIC_V1`` execution profile, and only for inputs
  carrying ``"synthetic": true``. Real-provenance bundles remain subject to
  the separately guarded ``ai.execution`` workflow and are rejected here
  BEFORE deserialization even when they are structurally valid, accepted,
  and producer-authenticated. The frozen ``CLEVELAND_D047_FROZEN_V1``
  profile is likewise never executed or predicted with through this CLI.
- ``verify-bundle`` never deserializes anything: it only runs the existing
  :func:`ai.packaging.verify_trusted_local_bundle` (default) or
  :func:`ai.packaging.verify_research_bundle` (``--integrity-only``) checks
  and reports whether CLI prediction would be supported.
- ``demo`` reuses the synthetic fixture builder and fast research config
  shape from :mod:`ai.validation_harness`, trains through the existing
  :func:`ai.training.train_research_model`, packages/verifies/loads through
  the existing secure packaging + inference path, and predicts one fixed
  synthetic example record. With no ``--work-dir`` all artifacts live in an
  isolated temporary directory that is deleted afterwards; the demo signing
  key is always isolated inside the work directory and never touches the
  operator's default local key.
- Ordinary output (stdout/stderr) never contains local filesystem paths,
  signing-key material or locations, submitted feature values, or tracebacks.
  Bundle locations are reported by directory *name* only; artifact SHA-256
  digests (already present in the bundle manifest) are the only provenance
  identifiers printed. Failures are fail-closed with exit code ``2``.
- Strictly offline and isolated from ``backend/app/`` HTTP serving.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import math
from pathlib import Path
import platform
import shutil
import sys
import tempfile
from typing import Any, Final, Mapping, Sequence

from scipy.special import expit

from ai.errors import (
    AiPipelineError,
    BundleIntegrityError,
    ClinicalInputValidationError,
)
from ai.explainability import ADDITIVITY_TOLERANCE, METHOD_BY_MODEL_FAMILY
from ai.filesystem_security import (
    ensure_private_directory,
    is_reparse_or_symlink,
    is_windows_runtime,
)
from ai.inference import MANDATORY_LIMITATIONS, ResearchCadPredictor
from ai.packaging import (
    VerifiedBundleDescriptor,
    get_or_create_local_signing_key,
    package_research_bundle,
    verify_research_bundle,
    verify_trusted_local_bundle,
)
from ai.panels import (
    DA_A2_RESTING_LABS_PANEL,
    REGISTERED_PANELS,
    ResearchPanelContract,
)
from ai.training import (
    EXECUTION_PROFILE_AI1_GENERIC_V1,
    EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1,
    ResearchTrainingConfig,
    train_research_model,
)
from ai.validation_harness import _make_synthetic_cohort

CLI_SUPPORTED_EXECUTION_PROFILE: Final[str] = EXECUTION_PROFILE_AI1_GENERIC_V1
MAX_INPUT_BYTES: Final[int] = 1024 * 1024  # 1 MiB ceiling for one demo record
EXIT_OK: Final[int] = 0
EXIT_FAIL_CLOSED: Final[int] = 2

# Fixed SYNTHETIC example record for `demo` (mirrored in
# ai/examples/synthetic_da_a2_resting_labs_v1.json). Invented values only;
# never a real patient record.
SYNTHETIC_DEMO_RECORD: Final[Mapping[str, Any]] = {
    "synthetic": True,
    "panel_id": DA_A2_RESTING_LABS_PANEL.panel_id,
    "features": {
        "age": 54,
        "sex": 1,
        "cp": 4,
        "trestbps": 138,
        "restecg": 1,
        "chol": 235,
        "fbs": 0,
    },
    "units": {"age": "years", "trestbps": "mmHg", "chol": "mg/dL"},
    "missing_reasons": {},
}

# Verified-bundle SHAP target/scale per registered family, mirroring the
# declarations written by ai.packaging and enforced by ai.inference. Display
# metadata only; attributions themselves always come from ai.explainability.
_SHAP_SCALE_BY_FAMILY: Final[Mapping[str, tuple[str, str]]] = {
    "l2_logistic_regression": ("calibrated_log_odds", "calibrated_log_odds"),
    "constrained_random_forest": ("raw_model_score", "raw_model_probability"),
    "prevalence_dummy": ("raw_model_score", "raw_model_probability"),
}


# --------------------------------------------------------------------------- #
# Pure payload builders (unit-testable without touching the filesystem)
# --------------------------------------------------------------------------- #


def _field_payload(panel: ResearchPanelContract) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    for spec in panel.fields:
        entry = spec.to_contract_dict()
        if spec.role == "numeric":
            entry["json_input_type"] = "finite JSON number (integer or float, never boolean)"
        elif spec.text_vocabulary is not None:
            entry["json_input_type"] = (
                "integer code from categorical_codes or registered text token "
                "from text_vocabulary"
            )
        else:
            entry["json_input_type"] = "integer code from categorical_codes"
        fields.append(entry)
    return fields


def build_panels_payload(panel_id: str | None = None) -> dict[str, Any]:
    """Describe registered panels, execution-profile status, and SHAP scales."""
    panels = (
        [REGISTERED_PANELS[panel_id]]
        if panel_id is not None
        else list(REGISTERED_PANELS.values())
    )
    return {
        "status": "OK",
        "command": "panels",
        "serving_eligibility": "RESEARCH_ONLY",
        "input_envelope": {
            "allowed_top_level_keys": [
                "synthetic",
                "panel_id",
                "features",
                "units",
                "missing_reasons",
                "context",
            ],
            "synthetic": "must be JSON true; this CLI never executes real or unlabeled records",
            "panel_id": "must equal the verified bundle panel_id when present",
            "features": (
                "object keyed by field name; explicit null is allowed only for "
                "optional fields paired with a measurement missing reason"
            ),
            "units": (
                "exactly one entry per present field that declares a unit; the "
                "token must equal the field unit exactly"
            ),
            "missing_reasons": (
                "exactly one registered reason per omitted or null optional field; "
                "required fields can never be missing"
            ),
            "context": (
                "optional; track must be 'A' and the source must not be a "
                "wearable / Track B source (rejected fail-closed)"
            ),
        },
        "panels": [
            {
                **panel.to_contract_dict(),
                "contract_sha256": panel.contract_sha256,
                "ordered_feature_names": list(panel.feature_names),
                "required_feature_names": [
                    field.name for field in panel.fields if field.required
                ],
                "optional_feature_names": [
                    field.name for field in panel.fields if not field.required
                ],
                "fields": _field_payload(panel),
            }
            for panel in panels
        ],
        "execution_profiles": [
            {
                "execution_profile": EXECUTION_PROFILE_AI1_GENERIC_V1,
                "status": "SYNTHETIC_RESEARCH_PROFILE",
                "cli_predict_supported": True,
                "note": (
                    "CLI prediction additionally requires synthetic-only bundle "
                    "provenance and a synthetic input record."
                ),
            },
            {
                "execution_profile": EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1,
                "status": "FROZEN_GUARDED_NOT_CLI_SUPPORTED",
                "cli_predict_supported": False,
                "note": (
                    "Frozen D-047 profile, reachable only through the separately "
                    "guarded ai.execution workflow under ratified operational "
                    "authorization. This CLI never trains, executes, or predicts "
                    "with it."
                ),
            },
        ],
        "model_families": [
            {
                "model_family": family,
                "explainability_method": METHOD_BY_MODEL_FAMILY[family],
                "shap_explained_quantity_in_verified_bundle_prediction": (
                    _SHAP_SCALE_BY_FAMILY[family][0]
                ),
                "shap_mathematical_scale": _SHAP_SCALE_BY_FAMILY[family][1],
                "shap_additive_on_calibrated_probability": False,
            }
            for family in sorted(METHOD_BY_MODEL_FAMILY)
        ],
        "limitations": list(MANDATORY_LIMITATIONS),
    }


def bundle_provenance_assessment(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Classify bundle provenance and CLI prediction support (pure function)."""
    eligibility = manifest.get("eligibility")
    eligibility = eligibility if isinstance(eligibility, Mapping) else {}
    model_block = manifest.get("model")
    model_block = model_block if isinstance(model_block, Mapping) else {}
    synthetic_only = eligibility.get("synthetic_only") is True
    execution_mode = eligibility.get("execution_mode")
    has_research_authorization = manifest.get("research_authorization") is not None
    execution_profile = model_block.get("execution_profile")
    synthetic_research = (
        synthetic_only
        and execution_mode == "SYNTHETIC_RESEARCH"
        and not has_research_authorization
    )
    block_code: str | None = None
    block_reason: str | None = None
    if not synthetic_research:
        block_code = "cli_real_provenance_bundle_not_supported"
        block_reason = (
            "Bundle is not synthetic-provenance research output. This CLI "
            "never predicts with real-provenance bundles, even when they are "
            "structurally valid, accepted, and authenticated; they remain "
            "subject to the separately guarded operational workflow."
        )
    elif execution_profile != CLI_SUPPORTED_EXECUTION_PROFILE:
        block_code = "cli_execution_profile_not_supported"
        block_reason = (
            "Bundle execution profile is not supported by this CLI; only the "
            f"generic synthetic research profile ({CLI_SUPPORTED_EXECUTION_PROFILE}) "
            "can be used for CLI prediction."
        )
    return {
        "synthetic_only": synthetic_only,
        "execution_mode": execution_mode,
        "has_research_authorization": has_research_authorization,
        "execution_profile": execution_profile,
        "provenance_cli_compatible": block_code is None,
        "cli_block_code": block_code,
        "cli_block_reason": block_reason,
    }


def assert_cli_predict_supported(manifest: Mapping[str, Any]) -> None:
    """Fail closed BEFORE deserialization for unsupported bundle provenance."""
    assessment = bundle_provenance_assessment(manifest)
    if assessment["cli_block_code"] is not None:
        raise BundleIntegrityError(
            str(assessment["cli_block_code"]),
            str(assessment["cli_block_reason"]),
        )


def _assert_expectations(
    *,
    panel_id: str,
    execution_profile: Any,
    model_family: Any,
    expect_panel: str | None,
    expect_profile: str | None,
    expect_model_family: str | None,
) -> None:
    checks = (
        ("panel_id", expect_panel, panel_id),
        ("execution_profile", expect_profile, execution_profile),
        ("selected_model_family", expect_model_family, model_family),
    )
    for field_name, expected, actual in checks:
        if expected is not None and expected != actual:
            raise BundleIntegrityError(
                "cli_bundle_expectation_mismatch",
                f"Verified bundle {field_name} does not match the operator-supplied expectation.",
                field=field_name,
            )


def verified_bundle_payload(
    descriptor: VerifiedBundleDescriptor, *, verification_mode: str
) -> dict[str, Any]:
    """Serialize a verification result without any local path or secret."""
    manifest = descriptor.manifest
    model_block = manifest.get("model")
    model_block = model_block if isinstance(model_block, Mapping) else {}
    assessment = bundle_provenance_assessment(manifest)
    cli_predict_supported = bool(
        assessment["provenance_cli_compatible"]
        and descriptor.safe_for_pickle_deserialization
    )
    block_reason = assessment["cli_block_reason"]
    if block_reason is None and not descriptor.safe_for_pickle_deserialization:
        block_reason = (
            "Integrity-only verification does not authenticate the bundle "
            "producer and never authorizes CLI prediction or deserialization."
        )
    return {
        "status": "VERIFIED",
        "command": "verify-bundle",
        "verification_mode": verification_mode,
        "bundle_dir_name": descriptor.bundle_dir.name,
        "bundle_schema_version": manifest.get("bundle_schema_version"),
        "generated_at_utc": manifest.get("generated_at_utc"),
        "model": {
            "model_id": model_block.get("model_id"),
            "model_version": model_block.get("model_version"),
            "protocol_id": model_block.get("protocol_id"),
            "selected_model_family": model_block.get("selected_model_family"),
            "execution_profile": model_block.get("execution_profile"),
            "explainability": model_block.get("explainability"),
        },
        "panel": {
            "panel_id": descriptor.panel.panel_id,
            "panel_version": descriptor.panel.panel_version,
            "contract_sha256": descriptor.panel.contract_sha256,
            "ordered_feature_names": list(descriptor.panel.feature_names),
            "target_id": descriptor.panel.target_id,
        },
        "authentication": {
            "producer_authenticated": descriptor.producer_authenticated,
            "safe_for_pickle_deserialization": (
                descriptor.safe_for_pickle_deserialization
            ),
            "integrity_verified_only_not_authenticated": (
                descriptor.integrity_verified_only_not_authenticated
            ),
            "checks_applied": (
                [
                    "layout_and_governance_flags",
                    "sha256_integrity",
                    "quarantine_marker_absence",
                    "post_run_acceptance_state",
                    "trusted_local_root_containment",
                    "platform_access_control",
                    "hmac_sha256_producer_attestation",
                ]
                if verification_mode == "trusted_local"
                else [
                    "layout_and_governance_flags",
                    "sha256_integrity",
                    "quarantine_marker_absence",
                    "post_run_acceptance_state",
                ]
            ),
        },
        "provenance": {
            "synthetic_only": assessment["synthetic_only"],
            "execution_mode": assessment["execution_mode"],
            "has_research_authorization": assessment["has_research_authorization"],
            "verified_artifact_hashes": dict(descriptor.verified_files),
        },
        "cli_predict_supported": cli_predict_supported,
        "cli_predict_block_reason": block_reason,
        "governance": {
            "serving_eligibility": descriptor.serving_eligibility,
            "approved_for_serving": descriptor.approved_for_serving,
            "clinical_use_authorized": descriptor.clinical_use_authorized,
        },
        "limitations": list(MANDATORY_LIMITATIONS),
    }


# --------------------------------------------------------------------------- #
# Input handling (envelope pre-checks only; full clinical validation stays in
# ai.panels.validate_clinical_record via ResearchCadPredictor)
# --------------------------------------------------------------------------- #


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            raise ClinicalInputValidationError(
                "cli_duplicate_json_key",
                "Input JSON contains a duplicated object key.",
                field=str(key),
            )
        obj[key] = value
    return obj


def _reject_non_finite_constant(token: str) -> Any:
    raise ClinicalInputValidationError(
        "cli_non_finite_json_constant",
        f"Input JSON contains the non-finite constant '{token}'.",
    )


def parse_input_payload(raw: bytes) -> dict[str, Any]:
    """Parse one demo input record (strict UTF-8 JSON object, finite only)."""
    if len(raw) > MAX_INPUT_BYTES:
        raise ClinicalInputValidationError(
            "cli_input_too_large",
            "Input exceeds the single-record size ceiling for this CLI.",
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ClinicalInputValidationError(
            "cli_malformed_input_json",
            "Input is not valid UTF-8 JSON.",
        ) from exc
    try:
        payload = json.loads(
            text,
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_non_finite_constant,
        )
    except AiPipelineError:
        raise
    except (json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise ClinicalInputValidationError(
            "cli_malformed_input_json",
            "Input is not valid UTF-8 JSON.",
        ) from exc
    if not isinstance(payload, dict):
        raise ClinicalInputValidationError(
            "cli_input_must_be_json_object",
            "Input JSON must be a single clinical record object.",
        )
    return payload


def read_input_payload(input_arg: str) -> dict[str, Any]:
    """Read a demo input from a local file path, or stdin when ``-``."""
    if input_arg == "-":
        raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        return parse_input_payload(raw)
    path = Path(input_arg)
    if is_reparse_or_symlink(path):
        raise ClinicalInputValidationError(
            "cli_input_symlink_prohibited",
            "Input path must not be a symlink, junction, or reparse point.",
        )
    if not path.is_file():
        raise ClinicalInputValidationError(
            "cli_input_not_found",
            "Input path does not name an existing regular file.",
        )
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise ClinicalInputValidationError(
            "cli_input_too_large",
            "Input exceeds the single-record size ceiling for this CLI.",
        )
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ClinicalInputValidationError(
            "cli_input_not_found",
            "Input file could not be read.",
        ) from exc
    return parse_input_payload(raw)


def precheck_synthetic_envelope(
    payload: Mapping[str, Any], *, expected_panel_id: str
) -> None:
    """Cheap pre-deserialization envelope checks (synthetic flag + panel)."""
    if payload.get("synthetic") is not True:
        raise ClinicalInputValidationError(
            "cli_non_synthetic_input_not_supported",
            "This CLI accepts only synthetic demo inputs carrying "
            '"synthetic": true; real or unlabeled records are never executed here.',
            field="synthetic",
        )
    declared_panel = payload.get("panel_id", expected_panel_id)
    if declared_panel != expected_panel_id:
        raise ClinicalInputValidationError(
            "panel_id_mismatch",
            "Record panel_id does not match the verified bundle panel contract.",
            field="panel_id",
        )


# --------------------------------------------------------------------------- #
# Signing-key resolution (verify/predict never mint a key at an explicit path)
# --------------------------------------------------------------------------- #


def resolve_signing_key(signing_key_path: Path | None) -> bytes | None:
    """Load an explicit local key, or defer to the existing default key path."""
    if signing_key_path is None:
        return None
    if not Path(signing_key_path).is_file():
        raise BundleIntegrityError(
            "cli_signing_key_not_found",
            "Explicit signing-key path does not name an existing file; "
            "verify/predict never mint a new local signing key.",
        )
    return get_or_create_local_signing_key(Path(signing_key_path))


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #


def run_verify_bundle(
    *,
    bundle_dir: Path,
    trusted_root: Path | None,
    signing_key: bytes | None,
    integrity_only: bool,
    expect_panel: str | None,
    expect_profile: str | None,
    expect_model_family: str | None,
) -> dict[str, Any]:
    """Verify a bundle through existing controls; never deserializes it."""
    if integrity_only:
        descriptor = verify_research_bundle(Path(bundle_dir))
        verification_mode = "integrity_only"
    else:
        if trusted_root is None:
            raise BundleIntegrityError(
                "cli_trusted_root_required",
                "Trusted verification requires an explicit --trusted-root.",
            )
        descriptor = verify_trusted_local_bundle(
            Path(bundle_dir),
            trusted_local_root=Path(trusted_root),
            signing_key=signing_key,
        )
        verification_mode = "trusted_local"
    model_block = descriptor.manifest.get("model")
    model_block = model_block if isinstance(model_block, Mapping) else {}
    _assert_expectations(
        panel_id=descriptor.panel.panel_id,
        execution_profile=model_block.get("execution_profile"),
        model_family=model_block.get("selected_model_family"),
        expect_panel=expect_panel,
        expect_profile=expect_profile,
        expect_model_family=expect_model_family,
    )
    return verified_bundle_payload(descriptor, verification_mode=verification_mode)


def run_predict(
    *,
    bundle_dir: Path,
    trusted_root: Path,
    input_arg: str,
    signing_key: bytes | None,
    expect_panel: str | None,
    expect_profile: str | None,
    expect_model_family: str | None,
    exploratory_threshold: float,
) -> dict[str, Any]:
    """Predict one synthetic record with a verified synthetic bundle.

    Order is load-safety critical: trusted verification, provenance/profile
    policy, and synthetic-envelope pre-checks ALL complete before
    ``from_verified_bundle`` is allowed to deserialize anything.
    """
    if not math.isfinite(exploratory_threshold) or not (
        0.0 <= exploratory_threshold <= 1.0
    ):
        raise AiPipelineError(
            "cli_invalid_threshold",
            "Exploratory threshold must be a finite number in [0, 1].",
            field="threshold",
        )
    descriptor = verify_trusted_local_bundle(
        Path(bundle_dir),
        trusted_local_root=Path(trusted_root),
        signing_key=signing_key,
    )
    assert_cli_predict_supported(descriptor.manifest)
    model_block = descriptor.manifest.get("model")
    model_block = model_block if isinstance(model_block, Mapping) else {}
    _assert_expectations(
        panel_id=descriptor.panel.panel_id,
        execution_profile=model_block.get("execution_profile"),
        model_family=model_block.get("selected_model_family"),
        expect_panel=expect_panel,
        expect_profile=expect_profile,
        expect_model_family=expect_model_family,
    )

    payload = read_input_payload(input_arg)
    precheck_synthetic_envelope(payload, expected_panel_id=descriptor.panel.panel_id)

    predictor = ResearchCadPredictor.from_verified_bundle(
        Path(bundle_dir),
        trusted_local_root=Path(trusted_root),
        signing_key=signing_key,
    )
    if (
        predictor.panel.panel_id != descriptor.panel.panel_id
        or predictor.execution_profile != model_block.get("execution_profile")
        or predictor.model_family != model_block.get("selected_model_family")
    ):
        raise BundleIntegrityError(
            "cli_loaded_bundle_identity_mismatch",
            "Loaded predictor identity differs from the pre-verified descriptor.",
        )

    result = predictor.predict_research_only(
        payload, exploratory_threshold=float(exploratory_threshold)
    )
    payload_out = result.to_dict()
    payload_out["execution_profile"] = predictor.execution_profile
    payload_out["cli"] = {
        "command": "predict",
        "synthetic_input_confirmed": True,
        "bundle_dir_name": descriptor.bundle_dir.name,
        "bundle_provenance": "SYNTHETIC_RESEARCH",
        "producer_authenticated": True,
        "verification": (
            "trusted_local_root_containment+platform_access_control+"
            "sha256_integrity+hmac_sha256_attestation+acceptance_state"
        ),
    }
    return payload_out


def run_demo(*, work_dir: Path | None) -> dict[str, Any]:
    """Train, package, verify, load, and predict an isolated synthetic demo."""
    owns_temp = work_dir is None
    base_dir = (
        Path(tempfile.mkdtemp(prefix="cardioassist_ai41_demo_"))
        if owns_temp
        else Path(work_dir)
    )
    steps_passed: list[str] = []
    try:
        # Resolve the isolated demo key FIRST: its repository-containment and
        # private-directory guards run before this command creates anything
        # else inside the work directory.
        key_path = base_dir / "private_keys" / "local_bundle_hmac_v1.key"
        signing_key = get_or_create_local_signing_key(key_path)
        try:
            ensure_private_directory(base_dir)
            trusted_root = ensure_private_directory(base_dir / "trusted_bundles")
        except OSError as exc:
            raise BundleIntegrityError(
                "cli_demo_work_dir_not_private",
                "Demo work directory could not be created with verified "
                "private access control.",
            ) from exc

        config = ResearchTrainingConfig(
            protocol_id="CAI-AI41-SYNTHETIC-DEMO-V1",
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
        records, labels = _make_synthetic_cohort(72, seed=20261025)
        run = train_research_model(
            records,
            labels,
            DA_A2_RESTING_LABS_PANEL,
            model_id="synth_ai41_demo_v1",
            development_cohort_id="synthetic_cleveland",
            development_dataset_id="DA-A2:synthetic_cleveland",
            synthetic_data_confirmed=True,
            config=config,
        )
        if run.synthetic_only is not True:
            raise AiPipelineError(
                "cli_demo_invariant_failed",
                "Demo training run is not marked synthetic-only.",
            )
        steps_passed.append("1_synthetic_cohort_training")

        bundle_dir = trusted_root / "synthetic_demo_bundle_v1"
        packaged = package_research_bundle(
            run, bundle_dir, signing_key=signing_key
        )
        if not packaged.producer_authenticated or not (
            packaged.safe_for_pickle_deserialization
        ):
            raise AiPipelineError(
                "cli_demo_invariant_failed",
                "Demo bundle packaging did not produce an authenticated bundle.",
            )
        steps_passed.append("2_signed_bundle_packaging")

        descriptor = verify_trusted_local_bundle(
            bundle_dir,
            trusted_local_root=trusted_root,
            signing_key=signing_key,
        )
        assert_cli_predict_supported(descriptor.manifest)
        steps_passed.append("3_trusted_local_verification")

        predictor = ResearchCadPredictor.from_verified_bundle(
            bundle_dir,
            trusted_local_root=trusted_root,
            signing_key=signing_key,
        )
        steps_passed.append("4_research_cad_predictor_load")

        result = predictor.predict_research_only(deepcopy(dict(SYNTHETIC_DEMO_RECORD)))
        if (
            not (0.0 < result.calibrated_research_score < 1.0)
            or abs(
                float(expit(result.calibrated_log_odds))
                - result.calibrated_research_score
            )
            > 1e-12
            or result.explanation.sum_check_passed is not True
            or result.explanation.additive_on_calibrated_probability is not False
            or result.explanation.max_abs_discrepancy > ADDITIVITY_TOLERANCE
        ):
            raise AiPipelineError(
                "cli_demo_invariant_failed",
                "Demo prediction failed calibration or SHAP additivity invariants.",
            )
        steps_passed.append("5_calibrated_prediction_and_faithful_shap")

        prediction = result.to_dict()
        prediction["execution_profile"] = predictor.execution_profile
        prediction["cli"] = {
            "command": "demo",
            "synthetic_input_confirmed": True,
            "bundle_dir_name": descriptor.bundle_dir.name,
            "bundle_provenance": "SYNTHETIC_RESEARCH",
            "producer_authenticated": True,
        }
        return {
            "status": "PASSED",
            "command": "demo",
            "python_version": platform.python_version(),
            "access_control_mechanism": (
                "windows_ntfs_win32_security_descriptor_dacl"
                if is_windows_runtime()
                else "posix_uid_and_mode_bits"
            ),
            "selected_model_family": run.selected_model_family,
            "steps_passed": steps_passed,
            "bundle": verified_bundle_payload(
                descriptor, verification_mode="trusted_local"
            ),
            "prediction": prediction,
            "work_artifacts_retained": not owns_temp,
            "notes": [
                "All demo training rows and the demo input record are synthetic.",
                (
                    "The isolated demo bundle and demo signing key were deleted "
                    "with the temporary work directory."
                    if owns_temp
                    else "Demo bundle retained under the work directory "
                    "'trusted_bundles' folder; its isolated demo signing key is "
                    "under 'private_keys'. Keep both private and never commit them."
                ),
            ],
        }
    finally:
        if owns_temp and base_dir.exists():
            shutil.rmtree(base_dir, ignore_errors=True)


# --------------------------------------------------------------------------- #
# Rendering (JSON default; concise ASCII text alternative)
# --------------------------------------------------------------------------- #


def _render_panels_text(payload: Mapping[str, Any]) -> str:
    lines = ["CardioAssist AI - registered research panels (RESEARCH_ONLY)"]
    for panel in payload["panels"]:
        lines.append("")
        lines.append(
            f"Panel {panel['panel_id']} v{panel['panel_version']} "
            f"[{panel['dataset_id']} / {panel['source_family']} / {panel['stage']}]"
        )
        lines.append(f"  governance: {panel['governance_status']}")
        lines.append(
            f"  real-data execution authorized: {panel['real_data_execution_authorized']}"
        )
        lines.append(f"  target: {panel['target_id']}")
        lines.append(f"  contract sha256: {panel['contract_sha256']}")
        for field in panel["fields"]:
            unit = field["unit"] if field["unit"] is not None else "unitless"
            requirement = "required" if field["required"] else "optional"
            lines.append(
                f"  - {field['name']} ({field['role']}, {requirement}, {unit}): "
                f"{field['json_input_type']}"
            )
    lines.append("")
    lines.append("Execution profiles:")
    for profile in payload["execution_profiles"]:
        lines.append(
            f"  - {profile['execution_profile']}: {profile['status']} "
            f"(cli_predict_supported={profile['cli_predict_supported']})"
        )
    lines.append("Limitations:")
    lines.extend(f"  * {item}" for item in payload["limitations"])
    return "\n".join(lines)


def _render_verify_text(payload: Mapping[str, Any]) -> str:
    model = payload["model"]
    auth = payload["authentication"]
    lines = [
        "Bundle verification: VERIFIED (RESEARCH_ONLY)",
        f"  bundle directory name: {payload['bundle_dir_name']}",
        f"  verification mode: {payload['verification_mode']}",
        f"  model: {model['model_id']} v{model['model_version']} ({model['protocol_id']})",
        f"  selected model family: {model['selected_model_family']}",
        f"  execution profile: {model['execution_profile']}",
        f"  panel: {payload['panel']['panel_id']} v{payload['panel']['panel_version']}",
        f"  producer authenticated: {auth['producer_authenticated']}",
        f"  safe for pickle deserialization: {auth['safe_for_pickle_deserialization']}",
        f"  synthetic only: {payload['provenance']['synthetic_only']}",
        f"  CLI predict supported: {payload['cli_predict_supported']}",
    ]
    if payload["cli_predict_block_reason"]:
        lines.append(f"  CLI predict note: {payload['cli_predict_block_reason']}")
    lines.append("Limitations:")
    lines.extend(f"  * {item}" for item in payload["limitations"])
    return "\n".join(lines)


def _render_prediction_text(payload: Mapping[str, Any]) -> str:
    prediction = payload["prediction"]
    explanation = payload["explanation"]
    lines = [
        "RESEARCH_ONLY synthetic prediction (not for clinical use)",
        f"  model: {payload['model_id']} v{payload['model_version']} ({payload['protocol_id']})",
        f"  selected model family: {payload['model_family']}",
        f"  panel: {payload['panel_id']}",
        f"  execution profile: {payload['execution_profile']}",
        f"  raw model score: {prediction['raw_model_score']:.6f}",
        f"  raw model log-odds: {prediction['raw_model_log_odds']:.6f}",
        f"  calibrated research score: {prediction['calibrated_research_score']:.6f}",
        f"  calibrated log-odds: {prediction['calibrated_log_odds']:.6f}",
        f"  SHAP explained quantity: {explanation['explained_quantity']}",
        f"  SHAP mathematical scale: {explanation['scale']}",
        f"  SHAP additive on calibrated probability: {explanation['additive_on_calibrated_probability']}",
        f"  SHAP base value (on scale): {explanation['base_value']:.6f}",
        f"  SHAP target value (on scale): {explanation['target_prediction_on_scale']:.6f}",
        "  SHAP attributions (panel order, on the scale above):",
    ]
    for item in explanation["attributions"]:
        lines.append(
            f"    - {item['feature_name']} [{item['status']}]: {item['shap_value']:+.6f}"
        )
    lines.append("Limitations:")
    lines.extend(f"  * {item}" for item in payload["limitations"])
    return "\n".join(lines)


def _render_demo_text(payload: Mapping[str, Any]) -> str:
    lines = [
        "Synthetic end-to-end demo: PASSED",
        f"  selected model family: {payload['selected_model_family']}",
        f"  steps passed: {', '.join(payload['steps_passed'])}",
        f"  work artifacts retained: {payload['work_artifacts_retained']}",
        "",
        _render_prediction_text(payload["prediction"]),
    ]
    return "\n".join(lines)


def render_payload(command: str, payload: Mapping[str, Any], *, fmt: str) -> str:
    if fmt == "json":
        return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True)
    if command == "panels":
        return _render_panels_text(payload)
    if command == "verify-bundle":
        return _render_verify_text(payload)
    if command == "predict":
        return _render_prediction_text(payload)
    if command == "demo":
        return _render_demo_text(payload)
    raise AiPipelineError("cli_unknown_command", f"Unknown command '{command}'.")


# --------------------------------------------------------------------------- #
# Argument parsing and fail-closed entry point
# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ai",
        description=(
            "Offline RESEARCH_ONLY AI inference CLI (synthetic demo use only). "
            "No clinical use; real-provenance bundles and real records are "
            "never executed here."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)

    panels_cmd = commands.add_parser(
        "panels",
        help="show registered panels, required features, input types, and profile status",
    )
    panels_cmd.add_argument(
        "--panel", choices=sorted(REGISTERED_PANELS), default=None,
        help="show only this registered panel",
    )
    panels_cmd.add_argument("--format", choices=("json", "text"), default="json")

    verify_cmd = commands.add_parser(
        "verify-bundle",
        help="verify a local research bundle without deserializing it",
    )
    verify_cmd.add_argument("--bundle-dir", type=Path, required=True)
    verify_cmd.add_argument("--trusted-root", type=Path, default=None)
    verify_cmd.add_argument("--signing-key-path", type=Path, default=None)
    verify_cmd.add_argument(
        "--integrity-only", action="store_true",
        help="SHA-256 integrity only; never authenticates or authorizes loading",
    )
    verify_cmd.add_argument("--expect-panel", choices=sorted(REGISTERED_PANELS), default=None)
    verify_cmd.add_argument(
        "--expect-profile",
        choices=(EXECUTION_PROFILE_AI1_GENERIC_V1, EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1),
        default=None,
    )
    verify_cmd.add_argument(
        "--expect-model-family", choices=sorted(METHOD_BY_MODEL_FAMILY), default=None
    )
    verify_cmd.add_argument("--format", choices=("json", "text"), default="json")

    predict_cmd = commands.add_parser(
        "predict",
        help="predict one synthetic JSON record with a verified synthetic bundle",
    )
    predict_cmd.add_argument("--bundle-dir", type=Path, required=True)
    predict_cmd.add_argument("--trusted-root", type=Path, required=True)
    predict_cmd.add_argument(
        "--input", required=True,
        help="path to a synthetic JSON demo input file, or - for stdin",
    )
    predict_cmd.add_argument("--signing-key-path", type=Path, default=None)
    predict_cmd.add_argument("--expect-panel", choices=sorted(REGISTERED_PANELS), default=None)
    predict_cmd.add_argument(
        "--expect-profile",
        choices=(EXECUTION_PROFILE_AI1_GENERIC_V1, EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1),
        default=None,
    )
    predict_cmd.add_argument(
        "--expect-model-family", choices=sorted(METHOD_BY_MODEL_FAMILY), default=None
    )
    predict_cmd.add_argument("--threshold", type=float, default=0.5)
    predict_cmd.add_argument("--format", choices=("json", "text"), default="json")

    demo_cmd = commands.add_parser(
        "demo",
        help="run an isolated end-to-end synthetic training-to-prediction demo",
    )
    demo_cmd.add_argument(
        "--work-dir", type=Path, default=None,
        help="retain demo artifacts in this private directory (default: temporary, deleted)",
    )
    demo_cmd.add_argument("--format", choices=("json", "text"), default="json")

    return parser


def _collect_redaction_tokens(args: argparse.Namespace) -> tuple[str, ...]:
    """Local path spellings that must never appear in ordinary CLI output."""
    tokens: set[str] = set()
    for attr in ("bundle_dir", "trusted_root", "signing_key_path", "work_dir"):
        value = getattr(args, attr, None)
        if value is not None:
            path = Path(value)
            tokens.add(str(path))
            try:
                tokens.add(str(path.resolve()))
            except OSError:
                pass
    input_arg = getattr(args, "input", None)
    if isinstance(input_arg, str) and input_arg != "-":
        path = Path(input_arg)
        tokens.add(str(path))
        try:
            tokens.add(str(path.resolve()))
        except OSError:
            pass
    # Longest first so nested paths redact before their parents.
    return tuple(sorted((t for t in tokens if t), key=len, reverse=True))


def _redact(message: str, tokens: Sequence[str]) -> str:
    redacted = message
    for token in tokens:
        redacted = redacted.replace(token, "<local-path>")
        redacted = redacted.replace(token.replace("\\", "/"), "<local-path>")
    return redacted


def _print_failure(exc: Exception, *, tokens: Sequence[str]) -> None:
    if isinstance(exc, AiPipelineError):
        error: dict[str, Any] = {
            "code": exc.code,
            "message": _redact(exc.message, tokens),
            "field": exc.field,
        }
    else:
        error = {
            "code": "cli_internal_error",
            "message": (
                f"Unexpected {type(exc).__name__}; failed closed with no "
                "prediction or clinical claim produced."
            ),
            "field": None,
        }
    print(
        json.dumps(
            {"status": "FAIL_CLOSED", "error": error},
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
        ),
        file=sys.stderr,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run one CLI command; return 0 on success, 2 on any fail-closed error."""
    args = build_parser().parse_args(argv)
    tokens = _collect_redaction_tokens(args)
    try:
        if args.command == "panels":
            payload = build_panels_payload(args.panel)
        elif args.command == "verify-bundle":
            signing_key = (
                None
                if args.integrity_only
                else resolve_signing_key(args.signing_key_path)
            )
            payload = run_verify_bundle(
                bundle_dir=args.bundle_dir,
                trusted_root=args.trusted_root,
                signing_key=signing_key,
                integrity_only=bool(args.integrity_only),
                expect_panel=args.expect_panel,
                expect_profile=args.expect_profile,
                expect_model_family=args.expect_model_family,
            )
        elif args.command == "predict":
            payload = run_predict(
                bundle_dir=args.bundle_dir,
                trusted_root=args.trusted_root,
                input_arg=str(args.input),
                signing_key=resolve_signing_key(args.signing_key_path),
                expect_panel=args.expect_panel,
                expect_profile=args.expect_profile,
                expect_model_family=args.expect_model_family,
                exploratory_threshold=float(args.threshold),
            )
        elif args.command == "demo":
            payload = run_demo(work_dir=args.work_dir)
        else:  # pragma: no cover - argparse restricts command choices
            raise AiPipelineError(
                "cli_unknown_command", f"Unknown command '{args.command}'."
            )
        print(render_payload(str(args.command), payload, fmt=str(args.format)))
        return EXIT_OK
    except Exception as exc:  # noqa: BLE001 - CLI boundary fails closed
        _print_failure(exc, tokens=tokens)
        return EXIT_FAIL_CLOSED


if __name__ == "__main__":
    raise SystemExit(main())
