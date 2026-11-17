"""AI-11.1 — reproducible synthetic demonstration of the research facade.

A standalone, offline, deterministic demonstration that a reader can run in
one command and that returns a machine-readable report::

    python -m ai.research_demo --format text
    python -m ai.research_demo --format json
    python -m ai.research_demo --format text --work-dir <private-ntfs-path>

Every stage exercises the *real* components through
:mod:`ai.research_registry` and :mod:`ai.research_facade`; nothing is
simulated in this module:

* one deterministic synthetic cohort from
  :func:`ai.research_routes.build_synthetic_cohort_for_route`;
* one real nested-CV training run through :func:`ai.training.train_research_model`
  using the identity registered for ``synth_ai7_da_a2_resting_v1``;
* one real signed bundle through :func:`ai.packaging.package_research_bundle`,
  verified through :func:`ai.packaging.verify_trusted_local_bundle`;
* one successful ``SYNTHETIC_RESULT`` with registered calibration, exact SHAP
  and — on request — certified LIME with its quality verdict;
* one ``ABSTAIN``, one ``UNAVAILABLE`` and a batch of ``ERROR`` refusals
  (unsupported model, wrong versions, invalid type/unit/field, missing
  required field, outcome leakage, wearable contamination, forged synthetic
  provenance, untrusted bundle, tampered artifact, foreign signing key).

This module writes only inside a private directory it creates (or the caller's
``--work-dir``), never into the repository, and removes the automatic
temporary directory afterwards. No real data, no network, no patient record.
Exits ``0`` when every stage passes and ``2`` on any fail-closed stage.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any, Final, Mapping, Sequence

from ai.errors import AiPipelineError
from ai.filesystem_security import (
    ensure_private_directory,
    protect_private_file,
)
from ai.packaging import get_or_create_local_signing_key, package_research_bundle
from ai.panels import REGISTERED_PANELS
from ai.research_facade import (
    LocalSyntheticBundleSource,
    ResearchFacadeStatus,
    ResearchFeatureRecord,
    SyntheticFixtureProvenance,
    is_registered_static_error_message,
    run_offline_research_inference_from_document,
)
from ai.research_registry import (
    REGISTRY_DIGEST_SHA256,
    RESEARCH_MODEL_REGISTRY,
    SYNTHETIC_PROVENANCE_DECLARATION,
    registry_contract,
)
from ai.research_routes import (
    build_synthetic_cohort_for_route,
    get_route_descriptor,
)
from ai.training import ResearchTrainingConfig, train_research_model

DEMO_ID: Final[str] = "cardioassist.ai.research_facade_demo/v1"
DEMO_COMMAND_TEXT: Final[str] = "python -m ai.research_demo --format text"
DEMO_COMMAND_JSON: Final[str] = "python -m ai.research_demo --format json"

#: Fixed, registered synthetic demo identity. ``model_id``/``protocol_id``/
#: ``model_version`` deliberately mirror the registry entry for
#: ``da_a2_resting_v1`` so the demonstration artifact *is* the registered
#: artifact identity rather than an ad-hoc one.
DEMO_MODEL_ID: Final[str] = "synth_ai7_da_a2_resting_v1"
DEMO_MODEL_VERSION: Final[str] = "0.1.0"
DEMO_PROTOCOL_ID: Final[str] = "CAI-AI7-SYNTHETIC-DA_A2_RESTING_V1-V1"
DEMO_ROUTE_ID: Final[str] = "da_a2_resting_v1"
DEMO_PANEL_ID: Final[str] = "da_a2_resting_v1"
DEMO_DATASET_ID: Final[str] = "DA-A2"
DEMO_GENERATOR_ID: Final[str] = (
    "ai.research_routes.build_synthetic_uci45_resting_cohort"
)
DEMO_SEED: Final[int] = 20261117
DEMO_N_ROWS: Final[int] = 96
DEMO_FIXTURE_REF: Final[str] = "synth-fixture-da-a2-resting"
EXIT_OK: Final[int] = 0
EXIT_FAIL_CLOSED: Final[int] = 2

#: Registered-but-blocked model entries and the reason each one must report.
_BLOCKED_ENTRY_CASES: Final[tuple[tuple[str, str], ...]] = (
    (
        "synth_ai7_da_a2_resting_labs_v1@0.1.0",
        "model_entry_blocked_pending_authorization",
    ),
    (
        "synth_ai7_da_a1_clinical_core_labs_v1@0.1.0",
        "model_entry_blocked_source_timing_unverified",
    ),
    (
        "synth_ai7_da_a2_hungary_locked_transportability_v1@0.1.0",
        "model_entry_locked_external_target",
    ),
)

_DEMO_TRAINING_CONFIG: Final[ResearchTrainingConfig] = ResearchTrainingConfig(
    protocol_id=DEMO_PROTOCOL_ID,
    model_version=DEMO_MODEL_VERSION,
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


class ResearchDemoError(AiPipelineError):
    """Raised when a demonstration stage does not produce its expected result."""


# --------------------------------------------------------------------------- #
# Deterministic synthetic records                                              #
# --------------------------------------------------------------------------- #


def _cohort() -> tuple[list[dict[str, Any]], list[int]]:
    route = get_route_descriptor(DEMO_ROUTE_ID)
    return build_synthetic_cohort_for_route(route, n_rows=DEMO_N_ROWS, seed=DEMO_SEED)


def _provenance() -> SyntheticFixtureProvenance:
    return SyntheticFixtureProvenance(
        declaration=SYNTHETIC_PROVENANCE_DECLARATION,
        fixture_ref=DEMO_FIXTURE_REF,
        generator_id=DEMO_GENERATOR_ID,
        seed=DEMO_SEED,
    )


def _record_from_envelope(
    envelope: Mapping[str, Any], index: int, **overrides: Any
) -> ResearchFeatureRecord:
    """Project a cohort envelope onto the facade's typed record."""
    features = dict(envelope.get("features") or {})
    units = dict(envelope.get("units") or {})
    reasons = dict(envelope.get("missing_reasons") or {})
    kwargs: dict[str, Any] = {
        "record_ref": f"demo{index:02d}",
        "features": features,
        "units": units,
        "missing_reasons": reasons,
        "acquisition_stage": "resting_assessment",
        "input_source": str(
            (envelope.get("context") or {}).get("source", "structured_synthetic_research")
        ),
        "provenance": _provenance(),
    }
    kwargs.update(overrides)
    return ResearchFeatureRecord(**kwargs)


def _demo_records() -> tuple[ResearchFeatureRecord, ResearchFeatureRecord]:
    records, _labels = _cohort()
    first = _record_from_envelope(records[0], 0)
    second = _record_from_envelope(records[1], 1)
    return first, second


# --------------------------------------------------------------------------- #
# Request construction                                                         #
# --------------------------------------------------------------------------- #


def _as_record_document(record: Any) -> dict[str, Any]:
    """Render one demo record as a request document.

    A raw :class:`~ai.research_facade.ResearchFeatureRecord` is projected onto
    the registered record grammar; a mapping is already such a document and is
    passed through unchanged, which is what lets the demonstration submit a
    record that (incorrectly) relies on a bare ``synthetic`` flag.
    """
    if isinstance(record, Mapping):
        return dict(record)
    provenance = record.provenance
    document: dict[str, Any] = {
        "record_ref": record.record_ref,
        "features": dict(record.features),
        "units": dict(record.units),
        "missing_reasons": dict(record.missing_reasons),
        "acquisition_stage": record.acquisition_stage,
        "input_source": record.input_source,
    }
    if provenance is not None:
        document["synthetic_provenance"] = {
            "declaration": provenance.declaration,
            "fixture_ref": provenance.fixture_ref,
            "generator_id": provenance.generator_id,
            "seed": provenance.seed,
        }
    return document


def _base_document(records: Sequence[Any], **overrides: Any) -> dict[str, Any]:
    entry = RESEARCH_MODEL_REGISTRY[f"{DEMO_MODEL_ID}@{DEMO_MODEL_VERSION}"]
    panel = REGISTERED_PANELS[DEMO_PANEL_ID]
    with_lime = bool(overrides.pop("with_lime", False))
    payload: dict[str, Any] = {
        "request_schema_version": "cardioassist.ai.research_inference_request/v1",
        "operation": "synthetic_prediction",
        "route_id": DEMO_ROUTE_ID,
        "route_version": entry.route_version,
        "model_id": DEMO_MODEL_ID,
        "model_version": DEMO_MODEL_VERSION,
        "panel_id": DEMO_PANEL_ID,
        "panel_version": panel.panel_version,
        "panel_contract_sha256": panel.contract_sha256,
        "dataset_id": DEMO_DATASET_ID,
        "records": [_as_record_document(record) for record in records],
        "exploratory_threshold": 0.5,
        "explainability": {
            "include_shap": True,
            "include_lime": with_lime,
            "lime_num_perturbations": 192,
            "lime_seed": 20261026,
        },
    }
    payload.update(overrides)
    return payload


def _base_request(
    source: LocalSyntheticBundleSource,
    records: Sequence[Any],
    **overrides: Any,
) -> Any:
    """Build one request document and run it through the facade document API.

    Every demonstration case — including the successful one — goes through the
    same registered request grammar, so the reported statuses are the statuses
    a document-facing caller would actually observe.
    """
    return run_offline_research_inference_from_document(
        _base_document(records, **overrides), model_source=source
    )


# --------------------------------------------------------------------------- #
# Stage harness                                                                #
# --------------------------------------------------------------------------- #


def _stage(name: str, detail: Mapping[str, Any]) -> dict[str, Any]:
    return {"stage": name, "status": "PASSED", "detail": dict(detail)}


def _canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _expect(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise ResearchDemoError(code, message)


def _refusal_message(response: Any) -> str | None:
    """The refusal reason actually reported for ``response``, if any."""
    payload = response.to_dict()
    error = payload.get("error")
    if isinstance(error, Mapping) and error.get("message"):
        return str(error["message"])
    for record in payload.get("records") or ():
        if isinstance(record, Mapping):
            record_error = record.get("error")
            if isinstance(record_error, Mapping) and record_error.get("message"):
                return str(record_error["message"])
    return None


def _refusal_expectation(
    label: str,
    response: Any,
    *,
    status: ResearchFacadeStatus,
    codes: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Assert the typed outcome of one refusal case and report it."""
    actual_status = response.status.value
    _expect(
        actual_status == status.value,
        "demo_refusal_status_mismatch",
        f"Refusal case '{label}' returned status {actual_status}, expected {status.value}.",
    )
    error = response.error
    record_codes = [
        outcome.error.code for outcome in response.outcomes if outcome.error is not None
    ]
    emitted = error.code if error is not None else (record_codes[0] if record_codes else None)
    first_outcome = response.outcomes[0] if response.outcomes else None
    if emitted is None and first_outcome is not None:
        # ABSTAIN/UNAVAILABLE record answers carry a reason, not an error.
        emitted = (
            first_outcome.abstention_reason or first_outcome.unavailable_reason or emitted
        )
    stage = error.stage if error is not None else (
        record_codes and "record" or "record"
    )
    if codes is not None:
        _expect(
            emitted in tuple(codes),
            "demo_refusal_code_mismatch",
            f"Refusal case '{label}' returned code {emitted!r}.",
        )
    return {
        "case": label,
        "status": actual_status,
        "code": emitted,
        "field": (error.field_name if error is not None else None),
        "stage": stage,
        "message": _refusal_message(response),
        "score_produced": any(
            outcome.score is not None for outcome in response.outcomes
        ),
    }


# --------------------------------------------------------------------------- #
# Private artifact workspace                                                   #
# --------------------------------------------------------------------------- #


def _build_demo_bundle(work_root: Path) -> dict[str, Any]:
    """Train, package and verify the registered synthetic demo artifact."""
    records, labels = _cohort()
    panel = REGISTERED_PANELS[DEMO_PANEL_ID]
    run = train_research_model(
        records,
        labels,
        panel,
        model_id=DEMO_MODEL_ID,
        development_cohort_id=f"synthetic:{DEMO_DATASET_ID}",
        development_dataset_id=DEMO_DATASET_ID,
        synthetic_data_confirmed=True,
        config=_DEMO_TRAINING_CONFIG,
    )
    _expect(
        run.synthetic_only is True,
        "demo_run_not_synthetic_only",
        "The demo training run is not marked synthetic-only.",
    )
    trusted_root = ensure_private_directory(work_root / "trusted_bundles")
    key_dir = ensure_private_directory(work_root / "private_keys")
    key_path = key_dir / "local_bundle_hmac_v1.key"
    signing_key = get_or_create_local_signing_key(key_path)
    bundle_dir = trusted_root / "synthetic_research_bundle_da_a2_resting_v1"
    packaged = package_research_bundle(run, bundle_dir, signing_key=signing_key)
    return {
        "run": run,
        "panel": panel,
        "trusted_root": trusted_root,
        "bundle_dir": bundle_dir,
        "signing_key": signing_key,
        "signing_key_path": key_path,
        "packaged": packaged,
    }


def _copy_bundle_private(bundle_dir: Path, destination: Path) -> Path:
    """Copy one bundle into a private directory (for tamper demonstrations)."""
    target = ensure_private_directory(destination)
    for item in sorted(Path(bundle_dir).iterdir()):
        copied = target / item.name
        shutil.copy2(item, copied)
        protect_private_file(copied)
    return target


# --------------------------------------------------------------------------- #
# Main demonstration                                                           #
# --------------------------------------------------------------------------- #


def run_research_facade_demo(
    *, work_dir: Path | None = None, with_lime: bool = True
) -> dict[str, Any]:
    """Execute the complete offline synthetic demonstration.

    Returns a JSON-safe payload with one entry per stage. No absolute path,
    record value, or key material appears in it. When ``work_dir`` is ``None``
    an isolated private temporary directory is created and removed; when it is
    supplied the caller owns the directory and its contents are retained.
    """
    owns_temp = work_dir is None
    stages: list[dict[str, Any]] = []
    payload: dict[str, Any] = {
        "demo_id": DEMO_ID,
        "status": "RUNNING",
        "command": DEMO_COMMAND_TEXT if not owns_temp else DEMO_COMMAND_TEXT,
        "registry_digest_sha256": REGISTRY_DIGEST_SHA256,
        "registry_version": registry_contract()["registry_version"],
        "evidence_level": "SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE",
        "synthetic_only": True,
        "data_provenance": "deliberately fabricated synthetic fixtures",
        "seed": DEMO_SEED,
        "n_records_development": DEMO_N_ROWS,
    }
    base_dir: Path | None = None
    try:
        if work_dir is None:
            base_dir = ensure_private_directory(
                Path(tempfile.mkdtemp(prefix="cardioassist_ai111_demo_"))
            )
        else:
            base_dir = ensure_private_directory(Path(work_dir))
            payload["work_dir_retained"] = True

        # ---- Stage 1: registry contract ---------------------------------- #
        contract = registry_contract()
        entries = contract["entries"]
        stages.append(
            _stage(
                "1_registry_contract",
                {
                    "registry_schema_version": contract["registry_schema_version"],
                    "registry_version": contract["registry_version"],
                    "registry_digest_sha256": contract["registry_digest_sha256"],
                    "registered_model_entries": sorted(entries),
                    "executable_entries": sorted(
                        key for key, value in entries.items() if value["executable"]
                    ),
                    "blocked_entries": sorted(
                        key
                        for key, value in entries.items()
                        if not value["executable"]
                    ),
                    "real_artifacts_registerable": contract["real_artifacts_registerable"],
                    "mutation_api_present": contract["mutation_api_present"],
                    "admissible_artifact_kinds": contract["admissible_artifact_kinds"],
                },
            )
        )

        # ---- Stage 2: synthetic cohort + real training ------------------- #
        records, labels = _cohort()
        stages.append(
            _stage(
                "2_synthetic_cohort",
                {
                    "generator_id": DEMO_GENERATOR_ID,
                    "seed": DEMO_SEED,
                    "n_rows": len(records),
                    "label_prevalence": round(
                        sum(int(value) for value in labels) / max(1, len(labels)), 6
                    ),
                    "all_records_declare_synthetic_source": all(
                        record.get("synthetic") is True for record in records
                    ),
                },
            )
        )

        build = _build_demo_bundle(base_dir)
        run = build["run"]
        stages.append(
            _stage(
                "3_synthetic_training_and_bundle",
                {
                    "model_id": run.model_id,
                    "model_version": run.model_version,
                    "protocol_id": run.protocol_id,
                    "selected_model_family": run.selected_model_family,
                    "execution_profile": run.execution_profile,
                    "panel_id": run.panel.panel_id,
                    "panel_contract_sha256": run.panel.contract_sha256,
                    "synthetic_only": bool(run.synthetic_only),
                    "bundle_packaged": True,
                    "bundle_producer_authenticated": bool(
                        build["packaged"].producer_authenticated
                    ),
                    "bundle_safe_for_deserialization": bool(
                        build["packaged"].safe_for_pickle_deserialization
                    ),
                    "bundle_dir_name": Path(build["bundle_dir"]).name,
                },
            )
        )

        source = LocalSyntheticBundleSource(
            bundle_dir=Path(build["bundle_dir"]),
            trusted_local_root=Path(build["trusted_root"]),
            signing_key=build["signing_key"],
        )

        # ---- Stage 4: successful synthetic inference --------------------- #
        first, second = _demo_records()
        success = _base_request(source, [first, second], with_lime=with_lime)
        _expect(
            success.status is ResearchFacadeStatus.SYNTHETIC_RESULT,
            "demo_success_case_refused",
            "The successful synthetic inference case was refused: "
            f"{success.error.code if success.error is not None else 'see records'}.",
        )
        outcome = success.outcomes[0]
        score = outcome.score
        assert score is not None and outcome.shap is not None
        capabilities = success.capabilities
        assert capabilities is not None
        _expect(
            score.clinical_probability_claim is False
            and score.threshold_clinically_validated is False,
            "demo_overclaim",
            "A synthetic score must never claim clinical probability or a validated threshold.",
        )
        if capabilities.calibration_supported:
            _expect(
                score.calibrated_research_score is not None
                and score.kind == "CALIBRATED_RESEARCH_SCORE_SYNTHETIC",
                "demo_calibration_reporting",
                "A calibration-capable artifact must report the calibrated research score.",
            )
        else:
            _expect(
                score.calibrated_research_score is None
                and score.kind == "RAW_MODEL_PROBABILITY_NOT_CALIBRATED",
                "demo_calibration_relabeling",
                "An uncalibrated artifact must never report a calibrated-looking score.",
            )
        _expect(
            outcome.shap.provided is True
            and outcome.shap.sum_check_passed is True
            and outcome.shap.additive_on_calibrated_probability is False,
            "demo_shap_reporting",
            "The SHAP explanation must be provided with its declared scale and additivity.",
        )
        lime_detail: dict[str, Any]
        if with_lime:
            lime = outcome.lime
            assert lime is not None
            _expect(
                lime.provided is True and lime.quality_status is not None,
                "demo_lime_reporting",
                "Requested LIME must carry its quality verdict.",
            )
            lime_detail = {
                "provided": lime.provided,
                "quality_status": lime.quality_status,
                "is_reliable_for_interpretation": lime.is_reliable_for_interpretation,
                "comparable_with_shap_scale": lime.comparable_with_shap,
                "explained_quantity": lime.explained_quantity,
                "scale": lime.scale,
                "local_approximation_not_exact_shapley": True,
            }
        else:
            lime_detail = {
                "provided": False,
                "reason": "not_requested_by_caller",
            }
        stages.append(
            _stage(
                "4_successful_synthetic_inference",
                {
                    "status": success.status.value,
                    "records_evaluated": len(success.outcomes),
                    "evidence_level": success.to_dict()["evidence_level"],
                    "model_family": success.to_dict()["model_family"],
                    "score_kind": score.kind,
                    "raw_model_score": round(score.raw_model_score, 6),
                    "raw_model_log_odds": round(score.raw_model_log_odds, 6),
                    "calibrated_research_score": (
                        None
                        if score.calibrated_research_score is None
                        else round(score.calibrated_research_score, 6)
                    ),
                    "calibrated_log_odds": (
                        None
                        if score.calibrated_log_odds is None
                        else round(score.calibrated_log_odds, 6)
                    ),
                    "calibration_supported": capabilities.calibration_supported,
                    "calibration_reason": capabilities.unsupported_calibration_reason,
                    "exploratory_threshold": score.exploratory_threshold,
                    "exploratory_above_threshold_flag": score.exploratory_above_threshold,
                    "threshold_clinically_validated": score.threshold_clinically_validated,
                    "score_interpretation": score.interpretation,
                    "shap": {
                        "provided": outcome.shap.provided,
                        "explained_quantity": outcome.shap.explained_quantity,
                        "scale": outcome.shap.scale,
                        "method": outcome.shap.method,
                        "sum_check_passed": outcome.shap.sum_check_passed,
                        "background_synthetic_only": outcome.shap.background_synthetic_only,
                        "background_sample_count": outcome.shap.background_sample_count,
                    },
                    "lime": lime_detail,
                    "fold_dispersion_keys": sorted((outcome.uncertainty or {}).keys()),
                },
            )
        )

        # ---- Stage 5: ABSTAIN -------------------------------------------- #
        abstain_envelope = copy.deepcopy(records[2])
        abstain_features = dict(abstain_envelope.get("features") or {})
        abstain_units = dict(abstain_envelope.get("units") or {})
        # trestbps is an optional panel field of da_a2_resting_v1: dropping it
        # with an explicit reason is a legal record, not an error.
        abstain_features.pop("trestbps", None)
        abstain_units.pop("trestbps", None)
        abstain_record = ResearchFeatureRecord(
            record_ref="abstain01",
            features=abstain_features,
            units=abstain_units,
            missing_reasons={"trestbps": "not_provided"},
            acquisition_stage="resting_assessment",
            input_source="structured_synthetic_research",
            provenance=_provenance(),
        )
        abstain_response = _base_request(source, [abstain_record])
        stages.append(
            _stage(
                "5_abstention",
                {
                    **_refusal_expectation(
                        "optional_field_missing_under_abstention_policy",
                        abstain_response,
                        status=ResearchFacadeStatus.ABSTAIN,
                        codes=["registry_abstain_policy_optional_field_missing"],
                    ),
                    "no_score_produced": all(
                        outcome.score is None for outcome in abstain_response.outcomes
                    ),
                    "missing_field_and_reason": [
                        list(pair)
                        for pair in abstain_response.outcomes[0].missing_fields_with_reason
                    ],
                    "note": (
                        "The artifact could impute the optional field from training "
                        "statistics; the registered policy declines to score on an "
                        "imputed field instead of silently doing so."
                    ),
                },
            )
        )


        # ---- Stage 6: UNAVAILABLE (registered but blocked) --------------- #
        unavailable_cases = []
        for key, expected_code in _BLOCKED_ENTRY_CASES:
            entry = RESEARCH_MODEL_REGISTRY[key]
            entry_panel = REGISTERED_PANELS[entry.panel_id]
            response = _base_request(
                source,
                [first],
                route_id=entry.route_id,
                route_version=entry.route_version,
                model_id=entry.model_id,
                model_version=entry.model_version,
                panel_id=entry.panel_id,
                panel_version=entry_panel.panel_version,
                panel_contract_sha256=entry_panel.contract_sha256,
                dataset_id=entry.dataset_id,
            )
            unavailable_cases.append(
                _refusal_expectation(
                    f"blocked_entry_{entry.route_id}",
                    response,
                    status=ResearchFacadeStatus.UNAVAILABLE,
                    codes=[expected_code],
                )
            )
            if key == _BLOCKED_ENTRY_CASES[0][0]:
                blocked_response = response
        stages.append(
            _stage(
                "6_unavailable_contracts",
                {
                    "cases": unavailable_cases,
                    "blocked_entries_report_registered_versions": True,
                    "reported_binding_versions": {
                        "route_id": blocked_response.to_dict()["route_id"],
                        "route_version": blocked_response.to_dict()["route_version"],
                        "panel_contract_sha256": blocked_response.to_dict()[
                            "panel_contract_sha256"
                        ],
                        "evidence_level": blocked_response.to_dict()["evidence_level"],
                    },
                    "no_score_produced": all(
                        not case["score_produced"] for case in unavailable_cases
                    ),
                },
            )
        )

        # ---- Stage 7: typed ERROR refusals ------------------------------- #
        error_cases: list[dict[str, Any]] = []

        def refuse(label: str, response: Any, codes: Sequence[str]) -> None:
            error_cases.append(
                _refusal_expectation(
                    label,
                    response,
                    status=ResearchFacadeStatus.ERROR,
                    codes=codes,
                )
            )

        refuse(
            "unregistered_model_entry",
            _base_request(source, [first], model_id="synth_unregistered_v1"),
            ["unknown_model_entry"],
        )
        refuse(
            "wrong_route_version",
            _base_request(source, [first], route_version="99.0.0"),
            ["route_version_mismatch"],
        )
        refuse(
            "wrong_model_version",
            _base_request(source, [first], model_version="9.9.9"),
            ["unknown_model_entry"],
        )
        refuse(
            "wrong_panel_hash",
            _base_request(source, [first], panel_contract_sha256="0" * 64),
            ["panel_contract_hash_mismatch"],
        )
        refuse(
            "wrong_panel_version",
            _base_request(source, [first], panel_version="9.9.9"),
            ["panel_version_mismatch"],
        )
        refuse(
            "forbidden_real_or_serving_operation",
            _base_request(source, [first], operation="clinical_serving"),
            ["facade_operation_not_supported"],
        )
        refuse(
            "real_bundle_inference_operation",
            _base_request(source, [first], operation="real_bundle_inference"),
            ["facade_operation_not_supported"],
        )

        def mutate_record(record: Any, **changes: Any) -> dict[str, Any]:
            document = _as_record_document(record)
            document.update(changes)
            return document

        features = dict(first.features)
        refuse(
            "field_not_in_panel",
            _base_request(
                source,
                [mutate_record(first, features={**features, "chol": 210.0})],
            ),
            ["unregistered_feature_for_panel"],
        )
        refuse(
            "wrong_value_type",
            _base_request(
                source,
                [mutate_record(first, features={**features, "age": "fifty-four"})],
            ),
            ["invalid_numeric_value"],
        )
        refuse(
            "unknown_categorical_code",
            _base_request(
                source,
                [mutate_record(first, features={**features, "cp": 9})],
            ),
            ["unknown_categorical_code"],
        )
        units = dict(first.units)
        refuse(
            "wrong_unit",
            _base_request(
                source,
                [mutate_record(first, units={**units, "trestbps": "kPa"})],
            ),
            ["unit_mismatch"],
        )
        refuse(
            "missing_unit_entry",
            _base_request(
                source,
                [mutate_record(first, units={k: v for k, v in units.items() if k != "age"})],
            ),
            ["unit_keys_mismatch"],
        )
        refuse(
            "missing_required_field",
            _base_request(
                source,
                [
                    mutate_record(
                        first,
                        features={k: v for k, v in features.items() if k != "age"},
                        units={k: v for k, v in units.items() if k != "age"},
                    )
                ],
            ),
            ["missing_required_field"],
        )
        refuse(
            "optional_field_without_missing_reason",
            _base_request(
                source,
                [
                    mutate_record(
                        first,
                        features={k: v for k, v in features.items() if k != "trestbps"},
                        units={k: v for k, v in units.items() if k != "trestbps"},
                        missing_reasons={},
                    )
                ],
            ),
            ["missing_reason_mismatch"],
        )
        refuse(
            "outcome_leakage_field",
            _base_request(
                source,
                [mutate_record(first, features={**features, "stenosis_percent": 70.0})],
            ),
            ["prohibited_leakage_or_wearable_field"],
        )
        refuse(
            "angiography_reference_standard_field",
            _base_request(
                source,
                [mutate_record(first, features={**features, "syntax_score": 22.0})],
            ),
            ["prohibited_leakage_or_wearable_field"],
        )
        refuse(
            "wearable_contamination_source",
            _base_request(
                source,
                [mutate_record(first, input_source="patient_wearable")],
            ),
            ["input_source_not_admissible", "unsupported_input_source",
             "wearable_or_track_b_rejected"],
        )
        refuse(
            "wearable_derived_field",
            _base_request(
                source,
                [mutate_record(first, features={**features, "spo2": 97.0})],
            ),
            ["prohibited_leakage_or_wearable_field"],
        )
        refuse(
            "forged_synthetic_flag_without_provenance",
            _base_request(
                source,
                [
                    {
                        "record_ref": "forgedflag",
                        "synthetic": True,
                        "features": dict(features),
                        "units": dict(units),
                        "missing_reasons": {},
                        "acquisition_stage": "resting_assessment",
                    }
                ],
            ),
            ["synthetic_flag_is_not_provenance"],
        )
        refuse(
            "missing_provenance_block",
            _base_request(
                source,
                [
                    {
                        key: value
                        for key, value in _as_record_document(first).items()
                        if key != "synthetic_provenance"
                    }
                ],
            ),
            ["synthetic_provenance_missing"],
        )
        refuse(
            "unknown_fixture_generator",
            _base_request(
                source,
                [
                    mutate_record(
                        first,
                        synthetic_provenance={
                            "declaration": SYNTHETIC_PROVENANCE_DECLARATION,
                            "fixture_ref": "externally-supposed",
                            "generator_id": "someone_elses_loader",
                            "seed": 1,
                        },
                    )
                ],
            ),
            ["synthetic_provenance_generator_not_admissible"],
        )
        refuse(
            "record_from_earlier_acquisition_stage",
            _base_request(
                source,
                [mutate_record(first, acquisition_stage="history_only")],
            ),
            ["acquisition_stage_precedence_violation"],
        )
        refuse(
            "unregistered_acquisition_stage",
            _base_request(
                source,
                [mutate_record(first, acquisition_stage="post_reference_test")],
            ),
            ["acquisition_stage_invalid"],
        )
        refuse(
            "duplicate_record_references",
            _base_request(source, [first, first]),
            ["duplicate_record_ref"],
        )
        refuse(
            "empty_request",
            _base_request(source, []),
            ["empty_record_set"],
        )

        # Artifact trust refusals.
        refuse(
            "bundle_outside_trusted_root",
            _base_request(
                LocalSyntheticBundleSource(
                    bundle_dir=Path(build["bundle_dir"]),
                    trusted_local_root=ensure_private_directory(base_dir / "wrong_trusted_root"),
                    signing_key=build["signing_key"],
                ),
                [first],
            ),
            ["bundle_verification_failed", "bundle_not_within_trusted_local_root",
             "bundle_outside_trusted_root", "untrusted_bundle_location", "bundle_path_invalid"],
        )
        tampered_dir = _copy_bundle_private(
            Path(build["bundle_dir"]), base_dir / "trusted_bundles" / "tampered_bundle"
        )
        tampered_file = tampered_dir / "preprocessing.json"
        tampered_file.write_bytes(tampered_file.read_bytes() + b" ")
        protect_private_file(tampered_file)
        refuse(
            "tampered_artifact_digest",
            _base_request(
                LocalSyntheticBundleSource(
                    bundle_dir=tampered_dir,
                    trusted_local_root=Path(build["trusted_root"]),
                    signing_key=build["signing_key"],
                ),
                [first],
            ),
            ["artifact_digest_mismatch", "artifact_content_mismatch", "file_size_mismatch",
             "file_digest_mismatch", "bundle_digest_mismatch", "bundle_verification_failed"],
        )
        foreign_key_dir = ensure_private_directory(base_dir / "private_keys_other")
        foreign_key = get_or_create_local_signing_key(
            foreign_key_dir / "foreign_bundle_hmac_v1.key"
        )
        refuse(
            "foreign_producer_key",
            _base_request(
                LocalSyntheticBundleSource(
                    bundle_dir=Path(build["bundle_dir"]),
                    trusted_local_root=Path(build["trusted_root"]),
                    signing_key=foreign_key,
                ),
                [first],
            ),
            ["untrusted_bundle_producer_signature", "bundle_verification_failed"],
        )
        stages.append(
            _stage(
                "7_typed_error_refusals",
                {
                    "cases": error_cases,
                    "case_count": len(error_cases),
                    "any_case_produced_a_score": any(case["score_produced"] for case in error_cases),
                    "distinct_codes": sorted({str(case["code"]) for case in error_cases}),
                },
            )
        )
        _expect(
            not any(case["score_produced"] for case in error_cases),
            "demo_refusal_produced_score",
            "A refusal case produced a score.",
        )
        _expect(
            len(error_cases) >= 20,
            "demo_refusal_coverage_short",
            "The demonstration must exercise the full refusal matrix.",
        )

        # ---- Stage 8: determinism and redaction -------------------------- #
        repeat = _base_request(source, [first, second], with_lime=with_lime)
        first_digest = _canonical_sha256(success.to_dict())
        second_digest = _canonical_sha256(repeat.to_dict())
        _expect(
            first_digest == second_digest,
            "demo_nondeterministic",
            "Two identical facade calls produced different payloads.",
        )
        serialized = json.dumps(
            [
                success.to_dict(),
                abstain_response.to_dict(),
                blocked_response.to_dict(),
            ],
            allow_nan=False,
        )
        needles = {
            "local_path": str(base_dir),
            "bundle_path": str(Path(build["bundle_dir"])),
            "signing_key": build["signing_key"].decode("utf-8", "ignore"),
        }
        leaks = sorted(name for name, needle in needles.items() if needle and needle in serialized)
        _expect(not leaks, "demo_path_or_secret_leak", f"A response disclosed {leaks}.")
        # Every refusal reason must be one of the registered static strings: a
        # dynamic message could carry a submitted value or a local path.
        refusal_cases = [
            case
            for stage in stages
            for case in (stage["detail"].get("cases") or [])
        ]
        messages = sorted(
            {
                str(case["message"])
                for case in refusal_cases
                if case.get("message") is not None
            }
        )
        _expect(
            bool(messages)
            and all(is_registered_static_error_message(message) for message in messages),
            "demo_unregistered_error_message",
            "A refusal carried a message outside the registered static catalogue.",
        )
        _expect(
            len(messages) >= 5,
            "demo_refusal_message_coverage_short",
            "The refusal cases did not exercise a representative set of reasons.",
        )
        stages.append(
            _stage(
                "8_determinism_and_redaction",
                {
                    "repeat_payload_match": True,
                    "canonical_payload_sha256": first_digest,
                    "local_paths_disclosed": False,
                    "signing_key_material_disclosed": False,
                    "refusal_messages_registered_static": True,
                    "distinct_refusal_messages": len(messages),
                    "refusal_cases_checked": len(refusal_cases),
                    "responses_json_clean": True,
                },
            )
        )

        payload["status"] = "PASSED"
    except Exception as exc:  # noqa: BLE001 - boundary reports a typed failure
        payload["status"] = "FAIL_CLOSED"
        payload["failure"] = {
            "type": (exc.code if isinstance(exc, AiPipelineError) else type(exc).__name__),
            "message": (
                exc.message if isinstance(exc, AiPipelineError) else "Demonstration failed closed."
            ),
            "field": getattr(exc, "field", None),
        }
    finally:
        if owns_temp and base_dir is not None and base_dir.exists():
            shutil.rmtree(base_dir, ignore_errors=True)

    payload["stage_results"] = stages
    payload["summary"] = {
        "stages_total": len(stages),
        "stages_succeeded": sum(1 for stage in stages if stage["status"] == "PASSED"),
        "stages_failed": sum(1 for stage in stages if stage["status"] != "PASSED"),
        "statuses_exercised": sorted(
            {
                *(stage["detail"].get("status") for stage in stages if "status" in stage["detail"]),
                *[
                    case["status"]
                    for stage in stages
                    for case in stage["detail"].get("cases", [])
                ],
            }
        ),
    }
    payload["deterministic_sha256"] = _canonical_sha256(
        {
            "stage_results": stages,
            "evidence_level": payload["evidence_level"],
            "registry_digest_sha256": REGISTRY_DIGEST_SHA256,
        }
    )
    payload["claim_level"] = "ENGINEERING_READY / SYNTHETIC_TEST_ONLY"
    payload["not_claimed"] = [
        "clinical validity or diagnostic accuracy",
        "externally validated individual risk probability",
        "authorization to serve any model",
        "real-data training or real-data evaluation",
    ]
    return payload


def render_demo_text(payload: Mapping[str, Any]) -> str:
    """Render the demo payload as a short human-readable report."""
    lines: list[str] = [
        "=" * 78,
        "CardioAssist AI — AI-11.1 offline research registry & facade demonstration",
        "=" * 78,
        f"status: {payload.get('status')}",
        f"registry: v{payload.get('registry_version')} "
        f"digest {str(payload.get('registry_digest_sha256'))[:16]}…",
        f"evidence level: {payload.get('evidence_level')}",
        f"claim level: {payload.get('claim_level')}",
        "-" * 78,
    ]
    for stage in payload.get("stage_results", []):
        detail = stage["detail"]
        lines.append(f"[{stage['status']}] {stage['stage']}")
        for key, value in detail.items():
            if isinstance(value, (str, int, float, bool, type(None))):
                rendered = (
                    value if not isinstance(value, float) else round(value, 6)
                )
                lines.append(f"    - {key}: {rendered}")
            elif isinstance(value, Mapping):
                lines.append(f"    - {key}:")
                for sub_key, sub_value in value.items():
                    if isinstance(sub_value, (str, int, float, bool, type(None))):
                        lines.append(
                            f"        - {sub_key}: "
                            f"{round(sub_value, 6) if isinstance(sub_value, float) else sub_value}"
                        )
            elif isinstance(value, Sequence) and all(
                isinstance(item, Mapping) for item in value
            ) and value:
                lines.append(f"    - {key}:")
                for item in value:
                    if "case" in item:
                        lines.append(
                            "        - {case}: {status} {code}".format(**item)
                        )
            else:
                lines.append(f"    - {key}: {list(value) if isinstance(value, Sequence) else value}")
    summary = payload.get("summary", {})
    lines.extend(
        [
            "-" * 78,
            f"stages: {summary.get('stages_succeeded')}/{summary.get('stages_total')} succeeded",
            f"statuses exercised: {', '.join(summary.get('statuses_exercised') or [])}",
            f"deterministic payload sha256: {payload.get('deterministic_sha256')}",
        ]
    )
    if payload.get("failure"):
        lines.append(f"failure: {payload['failure']}")
    lines.extend(
        [
            "All inputs are deliberately fabricated synthetic fixtures; every number",
            "is a RESEARCH_ONLY synthetic research score — not clinical evidence, not",
            "an individual patient's CAD risk, and not a serving authorization.",
            "=" * 78,
        ]
    )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m ai.research_demo",
        description=(
            "Offline RESEARCH_ONLY demonstration of the AI-11.1 research registry "
            "and typed facade. Synthetic fixtures only; real bundles, real records "
            "and clinical use are never reachable here."
        ),
    )
    parser.add_argument("--format", choices=("json", "text"), default="json")
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="retain demo artifacts in this private directory (default: temporary, deleted)",
    )
    parser.add_argument(
        "--no-lime",
        action="store_true",
        help="skip the (optional) LIME explanation stage",
    )
    args = parser.parse_args(argv)
    try:
        payload = run_research_facade_demo(
            work_dir=args.work_dir, with_lime=not args.no_lime
        )
    except Exception as exc:  # noqa: BLE001 - CLI boundary fails closed
        print(
            json.dumps(
                {
                    "status": "FAIL_CLOSED",
                    "error": {
                        "code": getattr(exc, "code", "research_demo_internal_error"),
                        "message": "Demonstration failed closed with no synthetic result produced.",
                    },
                },
                indent=2,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return EXIT_FAIL_CLOSED
    rendered = (
        render_demo_text(payload)
        if args.format == "text"
        else json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False)
    )
    print(rendered)
    return EXIT_OK if payload["status"] == "PASSED" else EXIT_FAIL_CLOSED


__all__ = [
    "DEMO_ID",
    "ResearchDemoError",
    "main",
    "render_demo_text",
    "run_research_facade_demo",
]


if __name__ == "__main__":
    raise SystemExit(main())