"""R1 — Cleveland five-field research input mapping validator (SYNTHETIC ONLY).

This module implements the versioned, explicitly **PROPOSED** mapping
specification in ``schemas/cleveland_resting_five_field_mapping.v0.1.json``
(Gate PT doc 12 section 6, R1 "smallest next implementation task"). It
validates **synthetic software fixtures only**; it never reads a dataset file,
never touches a real patient record, performs no I/O except reading its own
specification, and contains **no scoring, inference or prediction path of any
kind**. Every accepted payload returns a mapping review whose explicit result
state is ``NO_RESULT_NO_CAD_PROBABILITY_COMPUTED``.

Offline research artifact: not imported by the backend application, not
reachable over HTTP, not wired to ``/v1``, the database, the frontends or any
model registry. A ``synthetic: true`` flag is a caller assertion about the
fixture, not proof of provenance — real records must never be passed here.

The JSON specification is the reviewable record; the frozen constants below
deliberately duplicate it (the same pattern as
``research/uci412/feature_schema.py``) so that a JSON-only edit cannot quietly
change what the validator accepts. ``load_mapping_spec`` fails closed if the
two disagree, and a test additionally proves the five shared field conventions
match the M2b ``synthetic_stage_validator`` prototype.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from math import isfinite
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

PACKAGE_ROOT: Path = Path(__file__).resolve().parent
SPEC_PATH: Path = (
    PACKAGE_ROOT / "schemas" / "cleveland_resting_five_field_mapping.v0.1.json"
)

# --- Frozen in-code duplicates of the JSON specification ------------------- #

SPEC_SCHEMA_ID: str = "cleveland_resting_five_field_input_mapping"
SPEC_SCHEMA_VERSION: str = "0.1.0"
SPEC_MAPPING_ID: str = "cleveland_resting_five_field.v0.1"
SPEC_STATUS: str = "PROPOSED_NOT_APPROVED"
SPEC_ARTIFACT_KIND: str = "SYNTHETIC_ONLY_RESEARCH_INPUT_MAPPING_SPECIFICATION"
SPEC_DATASET_SELECTION_STATUS: str = "CLEVELAND_NOT_SELECTED_AS_FINAL_PROJECT_DATASET"

REGISTERED_SOURCE: Mapping[str, str] = MappingProxyType({
    "source_id": "UCI-45-processed-cleveland",
    "dataset_id": "DA-A2",
    "track": "A",
})

#: Ordered five-field mapping panel (processed Cleveland columns 1-4 and 7).
MAPPING_FIELDS: tuple[str, ...] = ("age", "sex", "cp", "trestbps", "restecg")
#: Mandatory non-null history fields at every supported stage.
MANDATORY_FIELDS: tuple[str, ...] = ("age", "sex", "cp")
#: Stages supported by THIS mapping version (the M2b lab/exercise stages are
#: intentionally out of scope; their fields are rejected as outside_mapping_scope).
SUPPORTED_STAGES: tuple[str, ...] = ("history_only", "resting_assessment")
STAGE_FIELD_BUNDLES: Mapping[str, tuple[str, ...]] = MappingProxyType({
    "history_only": ("age", "sex", "cp"),
    "resting_assessment": ("age", "sex", "cp", "trestbps", "restecg"),
})
#: Required measurement stage per field, as documented by the specification.
FIELD_REQUIRED_STAGE: Mapping[str, str] = MappingProxyType({
    "age": "history_only",
    "sex": "history_only",
    "cp": "history_only",
    "trestbps": "resting_assessment",
    "restecg": "resting_assessment",
})
CATEGORICAL_FIELDS: tuple[str, ...] = ("sex", "cp", "restecg")
NUMERICAL_FIELDS: tuple[str, ...] = ("age", "trestbps")
CATEGORICAL_SOURCE_CODES: Mapping[str, tuple[int, ...]] = MappingProxyType({
    "sex": (0, 1),
    "cp": (1, 2, 3, 4),
    "restecg": (0, 1, 2),
})
NUMERIC_UNIT_TOKENS: Mapping[str, str] = MappingProxyType({
    "age": "years",
    "trestbps": "mmHg",
})
NUMERIC_RULES: Mapping[str, str] = MappingProxyType({
    "age": "strictly_positive",
    "trestbps": "strictly_positive",
})
#: Fields where a measured 0 is "unavailable", not a valid measurement
#: (ED-DA-A2-01 item 2). Categorical zero (sex=0, restecg=0) stays valid data.
ZERO_UNAVAILABLE_FIELDS: frozenset[str] = frozenset({"trestbps"})

MEASUREMENT_MISSING_REASONS: frozenset[str] = frozenset((
    "not_measured", "not_available_at_time", "unknown",
))
STRUCTURAL_MISSING_REASON: str = "not_provided"
MISSING_REASON_VOCABULARY: frozenset[str] = MEASUREMENT_MISSING_REASONS | {
    STRUCTURAL_MISSING_REASON,
}

#: Deterministic classification order for prohibited field names.
PROHIBITED_CATEGORY_ORDER: tuple[str, ...] = (
    "outcome_label",
    "angiography_or_post_catheterization",
    "excluded_pending_timing_review",
    "identifier_or_site",
    "wearable_or_track_b",
    "other_dataset_source",
    "outside_mapping_scope",
)
UNREGISTERED_FIELD_CATEGORY: str = "unregistered_field"

#: The no-result contract: this module can never produce a CAD probability.
RESULT_STATE: str = "NO_RESULT_NO_CAD_PROBABILITY_COMPUTED"
MAPPING_STATUS: str = "ACCEPTED_SYNTHETIC_FIXTURE_MAPPING_ONLY"

REQUIRED_PAYLOAD_KEYS: frozenset[str] = frozenset({
    "mapping_version", "synthetic", "source", "stage",
    "features", "units", "missing_reasons",
})
SOURCE_BLOCK_KEYS: frozenset[str] = frozenset({
    "source_id", "dataset_id", "track",
})


class SourceMappingError(ValueError):
    """Fail-closed validation error with a stable code; never echoes values."""

    def __init__(self, code: str, message: str, *, category: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.category = category


class MappingSpecIntegrityError(RuntimeError):
    """The JSON specification and the frozen in-code allowlists disagree."""


@dataclass(frozen=True, slots=True)
class FieldMapping:
    """One mapped field's operative rules (mirrored from the JSON record)."""

    name: str
    kind: str
    unit: str | None
    source_codes: tuple[int, ...]
    numeric_rule: str | None
    required_stage: str


@dataclass(frozen=True, slots=True)
class MappingSpec:
    """Immutable view of the versioned PROPOSED mapping specification."""

    schema_id: str
    schema_version: str
    mapping_id: str
    status: str
    artifact_kind: str
    dataset_selection_status: str
    source_id: str
    dataset_id: str
    track: str
    supported_stages: tuple[str, ...]
    stage_field_bundles: Mapping[str, tuple[str, ...]]
    fields: tuple[FieldMapping, ...]
    prohibited_fields: Mapping[str, frozenset[str]]

    def field(self, name: str) -> FieldMapping:
        for candidate in self.fields:
            if candidate.name == name:
                return candidate
        raise KeyError(name)

    def stage_fields(self, stage: str) -> tuple[str, ...]:
        return self.stage_field_bundles[stage]

    def classify_field(self, name: str) -> str:
        """Return the prohibited-field category for a non-mapping field name."""
        for category in PROHIBITED_CATEGORY_ORDER:
            if name in self.prohibited_fields[category]:
                return category
        return UNREGISTERED_FIELD_CATEGORY


def _require(condition: Any, message: str) -> None:
    if not condition:
        raise MappingSpecIntegrityError(message)


def _validate_spec_document(document: Mapping[str, Any]) -> None:
    """Fail closed unless the JSON record matches the frozen code allowlists."""
    _require(isinstance(document, Mapping), "Specification document must be a mapping.")
    _require(document.get("schema_id") == SPEC_SCHEMA_ID, "Unexpected schema id.")
    _require(document.get("schema_version") == SPEC_SCHEMA_VERSION, "Unexpected schema version.")
    _require(document.get("mapping_id") == SPEC_MAPPING_ID, "Unexpected mapping id.")
    _require(document.get("status") == SPEC_STATUS, "Unexpected specification status.")
    _require(
        document.get("artifact_kind") == SPEC_ARTIFACT_KIND,
        "Unexpected artifact kind.",
    )
    _require(
        document.get("dataset_selection_status") == SPEC_DATASET_SELECTION_STATUS,
        "Dataset-selection status must state Cleveland is NOT selected.",
    )

    source = document.get("registered_source")
    _require(isinstance(source, Mapping), "Missing registered source block.")
    for key, expected in REGISTERED_SOURCE.items():
        _require(source.get(key) == expected, f"Registered source {key} mismatch.")

    stages = document.get("supported_stages")
    _require(isinstance(stages, Mapping), "Missing supported stages.")
    _require(tuple(stages) == SUPPORTED_STAGES, "Supported stages mismatch.")
    for stage, bundle in STAGE_FIELD_BUNDLES.items():
        entry = stages.get(stage)
        _require(isinstance(entry, Mapping), f"Stage {stage} entry must be a mapping.")
        _require(
            tuple(entry.get("field_bundle", ())) == bundle,
            f"Stage {stage} field bundle mismatch.",
        )
        _require(
            tuple(entry.get("required_non_null", ())) == MANDATORY_FIELDS,
            f"Stage {stage} mandatory fields mismatch.",
        )

    fields = document.get("fields")
    _require(isinstance(fields, list), "Fields must be a list.")
    _require(
        tuple(field.get("name") for field in fields) == MAPPING_FIELDS,
        "Field set or order mismatch.",
    )
    for field in fields:
        name = field.get("name")
        _require(field.get("kind") in ("numerical", "categorical"), f"Field {name} kind.")
        _require(
            field.get("required_measurement_stage") == FIELD_REQUIRED_STAGE[name],
            f"Field {name} required stage mismatch.",
        )
        if name in CATEGORICAL_SOURCE_CODES:
            _require(field.get("kind") == "categorical", f"Field {name} must be categorical.")
            _require(
                tuple(field.get("source_codes", ())) == CATEGORICAL_SOURCE_CODES[name],
                f"Field {name} source codes mismatch.",
            )
        else:
            _require(field.get("kind") == "numerical", f"Field {name} must be numerical.")
            _require(
                field.get("unit") == NUMERIC_UNIT_TOKENS[name],
                f"Field {name} unit token mismatch.",
            )
            _require(
                field.get("numeric_rule") == NUMERIC_RULES[name],
                f"Field {name} numeric rule mismatch.",
            )

    prohibited = document.get("prohibited_fields")
    _require(isinstance(prohibited, Mapping), "Missing prohibited-field taxonomy.")
    _require(
        tuple(prohibited) == PROHIBITED_CATEGORY_ORDER,
        "Prohibited-field categories mismatch.",
    )
    mapping_field_names = frozenset(MAPPING_FIELDS)
    for category in PROHIBITED_CATEGORY_ORDER:
        entry = prohibited.get(category)
        _require(isinstance(entry, Mapping), f"Prohibited category {category} entry.")
        listed = frozenset(entry.get("fields", ()))
        _require(bool(listed), f"Prohibited category {category} must not be empty.")
        _require(
            not (listed & mapping_field_names),
            f"Prohibited category {category} overlaps mapped fields.",
        )

    missingness = document.get("missingness_semantics")
    _require(isinstance(missingness, Mapping), "Missing missingness semantics block.")
    _require(
        frozenset(missingness.get("measurement_reasons", ()))
        == MEASUREMENT_MISSING_REASONS,
        "Measurement missing reasons mismatch.",
    )
    _require(
        missingness.get("structural_reason") == STRUCTURAL_MISSING_REASON,
        "Structural missing reason mismatch.",
    )
    zero = document.get("zero_semantics")
    _require(isinstance(zero, Mapping), "Missing zero-semantics block.")
    _require(
        frozenset(zero.get("fields_where_zero_is_unavailable_not_measured", ()))
        == ZERO_UNAVAILABLE_FIELDS,
        "Zero-unavailable field set mismatch.",
    )
    no_result = document.get("no_result_contract")
    _require(isinstance(no_result, Mapping), "Missing no-result contract.")
    _require(
        no_result.get("result_state") == RESULT_STATE,
        "No-result contract result state mismatch.",
    )
    _require(
        no_result.get("mapping_status") == MAPPING_STATUS,
        "No-result contract mapping status mismatch.",
    )
    envelope = document.get("envelope_contract")
    _require(isinstance(envelope, Mapping), "Missing envelope contract.")
    _require(
        frozenset(envelope.get("required_payload_keys", ())) == REQUIRED_PAYLOAD_KEYS,
        "Envelope payload keys mismatch.",
    )
    _require(
        frozenset(envelope.get("source_block_keys", ())) == SOURCE_BLOCK_KEYS,
        "Envelope source keys mismatch.",
    )


@lru_cache(maxsize=1)
def load_mapping_spec() -> MappingSpec:
    """Load, validate and cache the versioned mapping specification."""
    try:
        document = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    except OSError as error:  # pragma: no cover - repository integrity failure
        raise MappingSpecIntegrityError(
            "Mapping specification file is missing or unreadable."
        ) from error
    _validate_spec_document(document)
    return MappingSpec(
        schema_id=document["schema_id"],
        schema_version=document["schema_version"],
        mapping_id=document["mapping_id"],
        status=document["status"],
        artifact_kind=document["artifact_kind"],
        dataset_selection_status=document["dataset_selection_status"],
        source_id=document["registered_source"]["source_id"],
        dataset_id=document["registered_source"]["dataset_id"],
        track=document["registered_source"]["track"],
        supported_stages=tuple(document["supported_stages"]),
        stage_field_bundles=MappingProxyType({
            stage: tuple(entry["field_bundle"])
            for stage, entry in document["supported_stages"].items()
        }),
        fields=tuple(
            FieldMapping(
                name=field["name"],
                kind=field["kind"],
                unit=field.get("unit"),
                source_codes=tuple(field.get("source_codes", ())),
                numeric_rule=field.get("numeric_rule"),
                required_stage=field["required_measurement_stage"],
            )
            for field in document["fields"]
        ),
        prohibited_fields=MappingProxyType({
            category: frozenset(entry["fields"])
            for category, entry in document["prohibited_fields"].items()
        }),
    )


@dataclass(frozen=True, slots=True)
class MappingReview:
    """Metadata-only mapping result; carries no values and no result of any kind."""

    mapping_id: str
    spec_status: str
    source_id: str
    dataset_id: str
    track: str
    stage: str
    mapped_fields: tuple[str, ...]
    mapped_field_stages: tuple[tuple[str, str], ...]
    missing_fields_with_reason: tuple[tuple[str, str], ...]
    stage_complete: bool
    mapping_status: str
    result_state: str
    synthetic_only: bool


def _finite_real(value: Any) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return isfinite(value)
    except OverflowError:
        return False


def review_cleveland_source_mapping(payload: Mapping[str, Any]) -> MappingReview:
    """Validate one synthetic Cleveland-shaped source fixture against the mapping.

    Accepts only correctly coded, correctly provenanced synthetic fixtures and
    returns a metadata-only review whose result state is always
    ``NO_RESULT_NO_CAD_PROBABILITY_COMPUTED``. Everything else fails closed
    with a stable error code; error messages never echo submitted values.
    """
    spec = load_mapping_spec()

    if not isinstance(payload, Mapping):
        raise SourceMappingError("malformed_payload", "Source mapping payload must be a mapping.")
    keys = set(payload)
    if REQUIRED_PAYLOAD_KEYS - keys:
        raise SourceMappingError(
            "missing_required_metadata", "Missing required payload metadata keys."
        )
    if keys != REQUIRED_PAYLOAD_KEYS:
        raise SourceMappingError("malformed_payload", "Unknown payload envelope property.")

    if payload["mapping_version"] != spec.mapping_id:
        raise SourceMappingError(
            "unsupported_mapping_version", "Unsupported mapping version."
        )
    if payload["synthetic"] is not True:
        raise SourceMappingError(
            "non_synthetic_input", "Only explicitly synthetic fixtures are supported."
        )

    source = payload["source"]
    if not isinstance(source, Mapping):
        raise SourceMappingError(
            "missing_required_metadata", "Source provenance block must be a mapping."
        )
    source_keys = set(source)
    if SOURCE_BLOCK_KEYS - source_keys:
        raise SourceMappingError(
            "missing_required_metadata", "Missing source provenance keys."
        )
    if source_keys != SOURCE_BLOCK_KEYS:
        raise SourceMappingError(
            "malformed_payload", "Unknown source provenance property."
        )
    if source["track"] == "B":
        raise SourceMappingError(
            "track_b_input_rejected",
            "Track B (monitoring/wearable) input is not valid for this Track A mapping.",
        )
    if (
        source["source_id"],
        source["dataset_id"],
        source["track"],
    ) != (spec.source_id, spec.dataset_id, spec.track):
        raise SourceMappingError(
            "unsupported_source",
            "Payload source does not match the registered mapping source; "
            "no cross-dataset harmonization is registered.",
        )

    stage = payload["stage"]
    if not isinstance(stage, str) or stage not in spec.supported_stages:
        raise SourceMappingError(
            "unsupported_stage", "Unknown or unsupported stage for this mapping."
        )

    features = payload["features"]
    units = payload["units"]
    reasons = payload["missing_reasons"]
    for name, block in (
        ("features", features),
        ("units", units),
        ("missing_reasons", reasons),
    ):
        if not isinstance(block, Mapping):
            raise SourceMappingError(
                "malformed_payload", f"{name} must be a mapping."
            )
        if not all(isinstance(key, str) for key in block):
            raise SourceMappingError(
                "malformed_payload", f"{name} keys must be strings."
            )

    stage_fields = spec.stage_fields(stage)
    referenced = set(features) | set(units) | set(reasons)
    for field in sorted(referenced):
        if field not in MAPPING_FIELDS:
            raise SourceMappingError(
                "prohibited_field",
                "Field is not part of this mapping.",
                category=spec.classify_field(field),
            )
    out_of_stage = referenced - set(stage_fields)
    if out_of_stage:
        raise SourceMappingError(
            "field_not_available_for_stage",
            "Field is registered in this mapping but not in the selected stage.",
        )

    missing_mandatory = [
        field for field in MANDATORY_FIELDS
        if field not in features or features[field] is None
    ]
    if missing_mandatory:
        raise SourceMappingError(
            "missing_required_field",
            "Mandatory history fields must be present and non-null.",
        )

    null_fields = {
        field for field in stage_fields
        if field in features and features[field] is None
    }
    absent_fields = {
        field for field in stage_fields
        if field not in features
    }
    unavailable = null_fields | absent_fields
    if set(reasons) != unavailable:
        raise SourceMappingError(
            "invalid_missing_reason",
            "Every unavailable stage field needs exactly one reason; "
            "measured fields take none.",
        )
    for field, reason in reasons.items():
        if not isinstance(reason, str) or reason not in MISSING_REASON_VOCABULARY:
            raise SourceMappingError(
                "invalid_missing_reason", "Unsupported missing-value reason."
            )
        if field in absent_fields and reason != STRUCTURAL_MISSING_REASON:
            raise SourceMappingError(
                "invalid_missing_reason",
                "An omitted field requires the not_provided reason.",
            )
        if field in null_fields and reason not in MEASUREMENT_MISSING_REASONS:
            raise SourceMappingError(
                "invalid_missing_reason",
                "A null measurement requires an explicit measurement reason.",
            )

    measured = {
        field for field in stage_fields
        if field in features and features[field] is not None
    }
    measured_with_unit = {
        field for field in measured if spec.field(field).unit is not None
    }
    if set(units) != measured_with_unit:
        raise SourceMappingError(
            "unit_mismatch",
            "Measured fields with declared units require exact unit keys; "
            "categorical, unitless, null and absent fields take none.",
        )
    for field in sorted(measured_with_unit):
        if units[field] != spec.field(field).unit:
            raise SourceMappingError(
                "unit_mismatch", "Unit mismatch; no unit conversion is performed."
            )

    for definition in spec.fields:
        if definition.name not in measured:
            continue
        value = features[definition.name]
        if definition.kind == "categorical":
            if type(value) is not int:
                raise SourceMappingError(
                    "ambiguous_category_conversion",
                    "Categorical source codes must be literal integers; no label, "
                    "token, boolean, float or cross-dataset conversion is performed.",
                )
            if value not in definition.source_codes:
                raise SourceMappingError(
                    "unknown_categorical_code",
                    "Integer code is outside the fixed source-code vocabulary.",
                )
        else:
            if not _finite_real(value):
                raise SourceMappingError(
                    "invalid_numeric_value",
                    "Numerical values must be finite real numbers; source missing "
                    "tokens such as '?' are never passed through.",
                )
            if value == 0 and definition.name in ZERO_UNAVAILABLE_FIELDS:
                raise SourceMappingError(
                    "zero_measurement_unavailable",
                    "A measured zero is unavailable for this field; represent it "
                    "as null with a missing reason, never as a zero value.",
                )
            if value <= 0:
                raise SourceMappingError(
                    "invalid_numeric_value",
                    "Nonpositive value is not a valid measurement.",
                )

    present = tuple(
        definition.name for definition in spec.fields if definition.name in measured
    )
    missing = tuple(
        (definition.name, reasons[definition.name])
        for definition in spec.fields
        if definition.name in unavailable
    )
    return MappingReview(
        mapping_id=spec.mapping_id,
        spec_status=spec.status,
        source_id=spec.source_id,
        dataset_id=spec.dataset_id,
        track=spec.track,
        stage=stage,
        mapped_fields=present,
        mapped_field_stages=tuple(
            (definition.name, definition.required_stage)
            for definition in spec.fields
            if definition.name in measured
        ),
        missing_fields_with_reason=missing,
        stage_complete=not unavailable,
        mapping_status=MAPPING_STATUS,
        result_state=RESULT_STATE,
        synthetic_only=True,
    )
