"""Versioned clinical and routine-laboratory panel contracts for Track A research.

Reuses existing repository definitions rather than duplicating them:
- UCI-45 (``DA-A2``) staged field rules come from
  :mod:`research.intake.synthetic_stage_validator`.
- UCI-412 (``DA-A1``) column metadata, units, plausible ranges, and vocabularies
  come from :mod:`research.uci412.feature_schema` and
  :mod:`research.uci412.source_spec`.

All panels enforce Track A / Track B separation, reject target/angiography/echo
leakage fields, distinguish valid zero categorical codes from unavailable zero
numeric measurements, and require explicit missingness reasons for optional
stage measurements.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from math import isfinite
from types import MappingProxyType
from typing import Any, Final, Mapping, Sequence

import numpy as np

from ai.errors import ClinicalInputValidationError
from research.intake.synthetic_stage_validator import (
    FIELD_DEFINITIONS as UCI45_FIELD_DEFINITIONS,
    MANDATORY_HISTORY as UCI45_MANDATORY_HISTORY,
    MEASUREMENT_MISSING_REASONS,
    MISSING_REASONS,
    STAGE_FIELDS as UCI45_STAGE_FIELDS,
    STRUCTURAL_MISSING_REASON,
    FieldKind,
    NumericRule,
)
from research.uci412.feature_schema import (
    DEFAULT_DICTIONARY as UCI412_DICTIONARY,
    PRIMARY_PANEL_COLUMNS as UCI412_PRIMARY_COLUMNS,
)
from research.uci412.source_spec import ECHO_COLUMNS, PROHIBITED_PREDICTORS

EXTRA_WEARABLE_OR_LEAKAGE_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "spo2",
        "hrv",
        "ppg",
        "resting_hr_wearable",
        "smartwatch_ecg",
        "step_count",
        "sleep_duration",
        "syntax_score",
        "stenosis_percent",
    }
)

ALL_PROHIBITED_FIELDS: Final[frozenset[str]] = (
    frozenset(PROHIBITED_PREDICTORS)
    | frozenset(ECHO_COLUMNS)
    | EXTRA_WEARABLE_OR_LEAKAGE_FIELDS
)

PROHIBITED_SOURCES: Final[frozenset[str]] = frozenset(
    {
        "track_b",
        "wearable",
        "simulated_wearable",
        "patient_wearable",
        "patient_monitoring",
    }
)

UCI412_CORE_ROUTINE_LAB_COLUMNS: Final[tuple[str, ...]] = (
    "FBS",
    "CR",
    "TG",
    "LDL",
    "HDL",
    "HB",
    "WBC",
)

UCI45_CLINICAL_MEANINGS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "age": "Age at pre-angiography clinical evaluation",
        "sex": "Biological sex (UCI-45 code: 0=female, 1=male)",
        "cp": "Chest-pain category (UCI-45 nominal codes 1..4)",
        "trestbps": "Resting systolic blood pressure on admission",
        "restecg": "Resting electrocardiographic classification (codes 0..2)",
        "chol": "Serum total cholesterol from laboratory panel",
        "fbs": "Fasting blood sugar > 120 mg/dL indicator (0=false, 1=true)",
    }
)


@dataclass(frozen=True, slots=True)
class PanelFieldSpec:
    """Single ordered clinical or laboratory input variable in a panel."""

    name: str
    order: int
    role: str  # "numeric" | "categorical"
    clinical_meaning: str
    required: bool
    stage: str
    unit: str | None = None
    categorical_codes: tuple[int, ...] = ()
    text_vocabulary: Mapping[str, int] | None = None
    strictly_positive: bool = False
    plausible_range: tuple[float, float] | None = None

    def to_contract_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "order": self.order,
            "role": self.role,
            "clinical_meaning": self.clinical_meaning,
            "required": self.required,
            "stage": self.stage,
            "unit": self.unit,
            "categorical_codes": list(self.categorical_codes),
            "text_vocabulary": (
                None
                if self.text_vocabulary is None
                else dict(sorted(self.text_vocabulary.items()))
            ),
            "strictly_positive": self.strictly_positive,
            "plausible_range": (
                None if self.plausible_range is None else list(self.plausible_range)
            ),
        }


@dataclass(frozen=True, slots=True)
class ResearchPanelContract:
    """Immutable ordered feature contract for a single cohort schema and stage."""

    panel_id: str
    panel_version: str
    dataset_id: str
    source_family: str
    stage: str
    governance_status: str
    real_data_execution_authorized: bool
    target_id: str
    target_definition: str
    fields: tuple[PanelFieldSpec, ...]

    @property
    def feature_names(self) -> tuple[str, ...]:
        return tuple(field.name for field in self.fields)

    @property
    def field_map(self) -> Mapping[str, PanelFieldSpec]:
        return {field.name: field for field in self.fields}

    @property
    def required_names(self) -> frozenset[str]:
        return frozenset(field.name for field in self.fields if field.required)

    @property
    def optional_names(self) -> frozenset[str]:
        return frozenset(field.name for field in self.fields if not field.required)

    def to_contract_dict(self) -> dict[str, Any]:
        return {
            "panel_id": self.panel_id,
            "panel_version": self.panel_version,
            "dataset_id": self.dataset_id,
            "source_family": self.source_family,
            "stage": self.stage,
            "governance_status": self.governance_status,
            "real_data_execution_authorized": self.real_data_execution_authorized,
            "target_id": self.target_id,
            "target_definition": self.target_definition,
            "fields": [field.to_contract_dict() for field in self.fields],
        }

    @property
    def contract_sha256(self) -> str:
        payload = json.dumps(
            self.to_contract_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class ValidatedClinicalRecord:
    """Validated single-patient synthetic/research input aligned to a panel."""

    panel_id: str
    values: tuple[float, ...]  # float64; np.nan denotes validated missing optional field
    present_fields: tuple[str, ...]
    missing_fields_with_reason: tuple[tuple[str, str], ...]
    stage_complete: bool
    synthetic: bool

    def as_row_array(self) -> np.ndarray:
        return np.asarray(self.values, dtype=np.float64)


def _build_uci45_panel(
    *,
    panel_id: str,
    stage_key: str,
) -> ResearchPanelContract:
    stage_columns = UCI45_STAGE_FIELDS[stage_key]
    specs: list[PanelFieldSpec] = []
    for idx, col in enumerate(stage_columns):
        base = UCI45_FIELD_DEFINITIONS[col]
        is_req = col in UCI45_MANDATORY_HISTORY
        field_stage = (
            "history_only"
            if col in UCI45_MANDATORY_HISTORY
            else (
                "resting_assessment"
                if col in UCI45_STAGE_FIELDS["resting_assessment"]
                else "resting_plus_labs"
            )
        )
        specs.append(
            PanelFieldSpec(
                name=col,
                order=idx,
                role="numeric" if base.kind is FieldKind.NUMERICAL else "categorical",
                clinical_meaning=UCI45_CLINICAL_MEANINGS[col],
                required=is_req,
                stage=field_stage,
                unit=base.unit,
                categorical_codes=base.source_codes,
                text_vocabulary=None,
                strictly_positive=(base.numeric_rule is NumericRule.STRICTLY_POSITIVE),
                plausible_range=None,
            )
        )
    return ResearchPanelContract(
        panel_id=panel_id,
        panel_version="1.0.0",
        dataset_id="DA-A2",
        source_family="UCI-45",
        stage=stage_key,
        governance_status="RESEARCH_PROPOSED_GATE_PT_CLOSED",
        real_data_execution_authorized=False,
        target_id="t1.uci45.angiographic_cad_gt50.v1",
        target_definition=(
            "Cross-sectional angiographic CAD presence (num in {1,2,3,4} => >50% "
            "luminal diameter narrowing in >=1 major vessel vs 0 => <50%)."
        ),
        fields=tuple(specs),
    )


def _build_uci412_panel(
    *,
    panel_id: str,
    columns: Sequence[str],
    optional_columns: frozenset[str],
    stage: str,
    governance_status: str,
) -> ResearchPanelContract:
    specs: list[PanelFieldSpec] = []
    for idx, col in enumerate(columns):
        feat = UCI412_DICTIONARY.feature(col)
        vocab = (
            None
            if feat.vocabulary is None
            else MappingProxyType(dict(feat.vocabulary))
        )
        strictly_positive = (
            feat.is_numeric
            and feat.plausible_range is not None
            and feat.plausible_range[0] > 0.0
        )
        specs.append(
            PanelFieldSpec(
                name=col,
                order=idx,
                role="numeric" if feat.is_numeric else "categorical",
                clinical_meaning=feat.clinical_meaning,
                required=col not in optional_columns,
                stage="laboratory_report" if col in optional_columns else "basic_clinical",
                unit=feat.unit,
                categorical_codes=() if feat.is_numeric else feat.codes,
                text_vocabulary=vocab,
                strictly_positive=strictly_positive,
                plausible_range=feat.plausible_range,
            )
        )
    return ResearchPanelContract(
        panel_id=panel_id,
        panel_version="1.1.0",
        dataset_id="DA-A1",
        source_family="UCI-412",
        stage=stage,
        governance_status=governance_status,
        real_data_execution_authorized=False,
        target_id="t1.uci412.angiographic_cad_ge50.v1",
        target_definition=(
            "Cross-sectional angiographic CAD presence (Cath='Cad' => >=50% "
            "diameter narrowing in >=1 major coronary artery vs 'Normal')."
        ),
        fields=tuple(specs),
    )


DA_A2_RESTING_PANEL: Final[ResearchPanelContract] = _build_uci45_panel(
    panel_id="da_a2_resting_v1",
    stage_key="resting_assessment",
)

DA_A2_RESTING_LABS_PANEL: Final[ResearchPanelContract] = _build_uci45_panel(
    panel_id="da_a2_resting_labs_v1",
    stage_key="resting_plus_labs",
)

DA_A1_BASIC_CLINICAL_PANEL: Final[ResearchPanelContract] = _build_uci412_panel(
    panel_id="da_a1_basic_clinical_v1",
    columns=UCI412_PRIMARY_COLUMNS,
    optional_columns=frozenset(),
    stage="basic_clinical",
    governance_status="ADMITTED_FOR_INTERNAL_RESEARCH_SUBJECT_TO_M3A_AUTHORIZATION",
)

DA_A1_CLINICAL_CORE_LABS_PANEL: Final[ResearchPanelContract] = _build_uci412_panel(
    panel_id="da_a1_clinical_core_labs_v1",
    columns=(*UCI412_PRIMARY_COLUMNS, *UCI412_CORE_ROUTINE_LAB_COLUMNS),
    optional_columns=frozenset(UCI412_CORE_ROUTINE_LAB_COLUMNS),
    stage="clinical_plus_routine_labs",
    governance_status="PROPOSED_SYNTHETIC_ONLY_GATE_PT_REQUIRED",
)

REGISTERED_PANELS: Final[Mapping[str, ResearchPanelContract]] = MappingProxyType(
    {
        panel.panel_id: panel
        for panel in (
            DA_A2_RESTING_PANEL,
            DA_A2_RESTING_LABS_PANEL,
            DA_A1_BASIC_CLINICAL_PANEL,
            DA_A1_CLINICAL_CORE_LABS_PANEL,
        )
    }
)


def get_panel_contract(panel_id: str) -> ResearchPanelContract:
    """Return a registered panel contract or fail closed."""
    if not isinstance(panel_id, str) or panel_id not in REGISTERED_PANELS:
        raise ClinicalInputValidationError(
            "unregistered_panel",
            "Requested clinical panel contract is not registered.",
            field="panel_id",
        )
    return REGISTERED_PANELS[panel_id]


def _is_finite_real_scalar(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return isfinite(float(value))
    except OverflowError:
        return False


def _encode_categorical_value(value: Any, spec: PanelFieldSpec) -> int:
    if isinstance(value, bool):
        raise ClinicalInputValidationError(
            "invalid_categorical_type",
            f"Boolean values are not valid categorical codes for '{spec.name}'.",
            field=spec.name,
        )
    if type(value) is int:
        if value in spec.categorical_codes:
            return value
        raise ClinicalInputValidationError(
            "unknown_categorical_code",
            f"Unregistered categorical code supplied for '{spec.name}'.",
            field=spec.name,
        )
    if isinstance(value, str) and spec.text_vocabulary is not None:
        if value in spec.text_vocabulary:
            return int(spec.text_vocabulary[value])
        raise ClinicalInputValidationError(
            "unknown_categorical_token",
            f"Unregistered categorical token supplied for '{spec.name}'.",
            field=spec.name,
        )
    raise ClinicalInputValidationError(
        "invalid_categorical_type",
        f"Invalid categorical scalar type supplied for '{spec.name}'.",
        field=spec.name,
    )


def _validate_numeric_value(value: Any, spec: PanelFieldSpec) -> float:
    if not _is_finite_real_scalar(value):
        raise ClinicalInputValidationError(
            "invalid_numeric_value",
            f"Non-finite or non-numeric measurement supplied for '{spec.name}'.",
            field=spec.name,
        )
    numeric = float(value)
    if numeric == 0.0 and spec.strictly_positive:
        raise ClinicalInputValidationError(
            "zero_measurement_unavailable",
            f"Zero measurement for '{spec.name}' denotes an unmeasured value and is rejected.",
            field=spec.name,
        )
    if spec.strictly_positive and numeric < 0.0:
        raise ClinicalInputValidationError(
            "invalid_numeric_value",
            f"Negative measurement is invalid for '{spec.name}'.",
            field=spec.name,
        )
    if spec.plausible_range is not None:
        low, high = spec.plausible_range
        if not (low <= numeric <= high):
            raise ClinicalInputValidationError(
                "value_out_of_plausible_range",
                f"Measurement for '{spec.name}' falls outside registered plausibility bounds.",
                field=spec.name,
            )
    return numeric


def validate_clinical_record(
    payload: Mapping[str, Any],
    panel: ResearchPanelContract,
    *,
    require_synthetic: bool = True,
) -> ValidatedClinicalRecord:
    """Validate one structured clinical/lab record against ``panel``."""
    if not isinstance(payload, Mapping):
        raise ClinicalInputValidationError(
            "malformed_payload",
            "Clinical input record must be a mapping.",
        )

    allowed_keys = {"synthetic", "panel_id", "features", "units", "missing_reasons", "context"}
    unknown_envelope = set(payload) - allowed_keys
    if unknown_envelope:
        raise ClinicalInputValidationError(
            "unexpected_envelope_key",
            "Clinical input contains unsupported top-level keys.",
        )

    synthetic_flag = payload.get("synthetic")
    if not require_synthetic and synthetic_flag is True:
        raise ClinicalInputValidationError(
            "synthetic_disguise_in_real_record",
            "Record carries synthetic=True but was submitted to a real-data evaluation pipeline.",
            field="synthetic",
        )
    if require_synthetic and synthetic_flag is not True:
        raise ClinicalInputValidationError(
            "non_synthetic_input_rejected",
            "Gate PT remains closed; only explicitly synthetic records are accepted here.",
            field="synthetic",
        )
    if not isinstance(synthetic_flag, bool):
        raise ClinicalInputValidationError(
            "invalid_synthetic_flag",
            "The 'synthetic' flag must be an explicit boolean.",
            field="synthetic",
        )

    declared_panel = payload.get("panel_id", panel.panel_id)
    if declared_panel != panel.panel_id:
        raise ClinicalInputValidationError(
            "panel_id_mismatch",
            "Record panel_id does not match the active model panel contract.",
            field="panel_id",
        )

    context = payload.get("context", {})
    if not isinstance(context, Mapping):
        raise ClinicalInputValidationError(
            "malformed_context",
            "Context metadata must be a mapping when provided.",
            field="context",
        )
    track = context.get("track", "A")
    source = str(context.get("source", "structured_clinical_research")).lower()
    if track != "A" or source in PROHIBITED_SOURCES or "wearable" in source:
        raise ClinicalInputValidationError(
            "wearable_or_track_b_rejected",
            "Track B / wearable observations are prohibited for Track A CAD inference.",
            field="context",
        )

    features = payload.get("features")
    units = payload.get("units", {})
    reasons = payload.get("missing_reasons", {})
    if (
        not isinstance(features, Mapping)
        or not isinstance(units, Mapping)
        or not isinstance(reasons, Mapping)
    ):
        raise ClinicalInputValidationError(
            "malformed_payload",
            "Expected mappings for 'features', 'units', and 'missing_reasons'.",
        )
    if not all(isinstance(k, str) for k in (*features.keys(), *units.keys(), *reasons.keys())):
        raise ClinicalInputValidationError(
            "malformed_payload",
            "Feature, unit, and missing-reason keys must be strings.",
        )

    supplied_names = set(features)
    prohibited_hit = supplied_names & ALL_PROHIBITED_FIELDS
    if prohibited_hit:
        bad_field = sorted(prohibited_hit)[0]
        raise ClinicalInputValidationError(
            "prohibited_leakage_or_wearable_field",
            f"Field '{bad_field}' is prohibited (target leakage, unverified echo, or wearable).",
            field=bad_field,
        )

    field_map = panel.field_map
    unexpected_features = supplied_names - set(field_map)
    if unexpected_features:
        bad_field = sorted(unexpected_features)[0]
        raise ClinicalInputValidationError(
            "unregistered_feature_for_panel",
            f"Field '{bad_field}' is not part of panel '{panel.panel_id}'.",
            field=bad_field,
        )

    null_fields = {k for k, v in features.items() if v is None}
    omitted_fields = set(field_map) - supplied_names
    missing_all = null_fields | omitted_fields

    missing_required = missing_all & panel.required_names
    if missing_required:
        bad_field = sorted(missing_required)[0]
        raise ClinicalInputValidationError(
            "missing_required_field",
            f"Required clinical field '{bad_field}' cannot be omitted or null.",
            field=bad_field,
        )

    if set(reasons) != missing_all:
        raise ClinicalInputValidationError(
            "missing_reason_mismatch",
            "Every omitted or null optional field requires exactly one missing reason.",
            field="missing_reasons",
        )
    for field_name, reason in reasons.items():
        if not isinstance(reason, str) or reason not in MISSING_REASONS:
            raise ClinicalInputValidationError(
                "invalid_missing_reason",
                f"Unsupported missing reason for '{field_name}'.",
                field=field_name,
            )
        if field_name in omitted_fields and reason != STRUCTURAL_MISSING_REASON:
            raise ClinicalInputValidationError(
                "invalid_missing_reason",
                f"Omitted optional field '{field_name}' requires reason '{STRUCTURAL_MISSING_REASON}'.",
                field=field_name,
            )
        if field_name in null_fields and reason not in MEASUREMENT_MISSING_REASONS:
            raise ClinicalInputValidationError(
                "invalid_missing_reason",
                f"Explicit null field '{field_name}' requires a measurement missing reason.",
                field=field_name,
            )

    expected_unit_fields = {
        name
        for name, spec in field_map.items()
        if name not in missing_all and spec.unit is not None
    }
    if set(units) != expected_unit_fields:
        raise ClinicalInputValidationError(
            "unit_keys_mismatch",
            "Measured fields with physical units require exact unit entries (and none for missing/unitless fields).",
            field="units",
        )
    for field_name in expected_unit_fields:
        expected_unit = field_map[field_name].unit
        if units[field_name] != expected_unit:
            raise ClinicalInputValidationError(
                "unit_mismatch",
                f"Unit token mismatch for '{field_name}' (expected '{expected_unit}').",
                field=field_name,
            )

    encoded_values: list[float] = []
    present: list[str] = []
    missing_pairs: list[tuple[str, str]] = []
    for spec in panel.fields:
        if spec.name in missing_all:
            encoded_values.append(float("nan"))
            missing_pairs.append((spec.name, reasons[spec.name]))
            continue
        raw_val = features[spec.name]
        if spec.role == "categorical":
            encoded_values.append(float(_encode_categorical_value(raw_val, spec)))
        else:
            encoded_values.append(_validate_numeric_value(raw_val, spec))
        present.append(spec.name)

    return ValidatedClinicalRecord(
        panel_id=panel.panel_id,
        values=tuple(encoded_values),
        present_fields=tuple(present),
        missing_fields_with_reason=tuple(missing_pairs),
        stage_complete=(len(missing_pairs) == 0),
        synthetic=synthetic_flag,
    )


def validate_cohort_records(
    records: Sequence[Mapping[str, Any]],
    labels: Sequence[int],
    panel: ResearchPanelContract,
    *,
    require_synthetic: bool = True,
) -> tuple[np.ndarray, np.ndarray, tuple[ValidatedClinicalRecord, ...]]:
    """Validate a sequence of clinical records and binary CAD presence labels."""
    if len(records) == 0:
        raise ClinicalInputValidationError(
            "empty_cohort",
            "Cohort must contain at least one record.",
        )
    if len(records) != len(labels):
        raise ClinicalInputValidationError(
            "label_length_mismatch",
            "Record count and binary label count must match.",
        )

    validated: list[ValidatedClinicalRecord] = []
    y_out: list[int] = []
    for label in labels:
        if type(label) is not int or label not in (0, 1):
            raise ClinicalInputValidationError(
                "invalid_binary_label",
                "Target labels must be exact binary integers 0 or 1.",
                field="target",
            )
        y_out.append(label)

    for record in records:
        validated.append(
            validate_clinical_record(record, panel, require_synthetic=require_synthetic)
        )

    X = np.vstack([item.as_row_array() for item in validated]).astype(np.float64)
    y = np.asarray(y_out, dtype=np.int64)
    if len(set(y.tolist())) < 2:
        raise ClinicalInputValidationError(
            "single_class_cohort",
            "Cohort must contain both positive (1) and negative (0) CAD labels.",
            field="target",
        )
    return X, y, tuple(validated)
