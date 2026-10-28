"""AI-8 — UCI-412 (DA-A1) 16-feature field-contract validator (SYNTHETIC ONLY).

This module implements the versioned, explicitly **PROPOSED** source-specific
field contract in
``schemas/uci412_basic_clinical_field_contract.v0.1.json`` (milestone AI-8,
deliverable D). It is a technical handoff for *future* application and OCR
development. It validates **synthetic software fixtures only**; it never reads
a dataset file, never touches a real patient record, performs no I/O except
reading its own contract, and contains **no scoring, inference or prediction
path of any kind**. Every accepted payload returns a review whose explicit
result state is ``NO_RESULT_NO_CAD_PROBABILITY_COMPUTED``.

Offline research artifact: not imported by the backend application, not
reachable over HTTP, not wired to ``/v1``, the database, the frontends, any
model registry or the frozen A3 diagnostic runtime.

The JSON contract is the reviewable record; the frozen constants below
deliberately duplicate its operative rules (the same pattern as
:mod:`research.intake.cleveland_source_mapping` and
:mod:`research.uci412.feature_schema`) so a JSON-only edit cannot quietly
change what the validator accepts. :func:`load_field_contract` fails closed if
the two disagree, and the test suite additionally proves every operative rule
matches the registered :data:`ai.panels.DA_A1_BASIC_CLINICAL_PANEL` contract
and feature dictionary 1.1.0.

This module is deliberately stdlib-only (no numpy/scikit-learn dependency).
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
CONTRACT_PATH: Path = (
    PACKAGE_ROOT / "schemas" / "uci412_basic_clinical_field_contract.v0.1.json"
)

# --- Frozen in-code duplicates of the JSON contract ----------------------- #

CONTRACT_SCHEMA_ID: str = "uci412_basic_clinical_field_contract"
CONTRACT_SCHEMA_VERSION: str = "0.1.0"
CONTRACT_ID: str = "uci412_basic_clinical_field_contract.v0.1"
CONTRACT_STATUS: str = "PROPOSED_NOT_APPROVED"
CONTRACT_ARTIFACT_KIND: str = "SYNTHETIC_ONLY_RESEARCH_INPUT_FIELD_CONTRACT"

REGISTERED_SOURCE: Mapping[str, Any] = MappingProxyType(
    {
        "source_id": "UCI-412",
        "dataset_id": "DA-A1",
        "track": "A",
    }
)

#: The registered 16-feature basic clinical panel, in exact contract order.
FIELD_ORDER: tuple[str, ...] = (
    "Age",
    "Sex",
    "BMI",
    "DM",
    "HTN",
    "Current Smoker",
    "EX-Smoker",
    "FH",
    "DLP",
    "BP",
    "PR",
    "Typical Chest Pain",
    "Atypical",
    "Nonanginal",
    "Exertional CP",
    "Dyspnea",
)

#: Six columns delivered as numeric 0/1 cells (Amendment A-1). Text, booleans
#: and any other integer are rejected; there is no global coercion.
NUMERIC_BINARY_FIELDS: frozenset[str] = frozenset(
    {
        "DM",
        "HTN",
        "Current Smoker",
        "EX-Smoker",
        "FH",
        "Typical Chest Pain",
    }
)
NUMERIC_BINARY_ENCODING_ID: str = "numeric_binary_0_1_v1"

#: Six columns delivered as registered text tokens.
TEXT_BINARY_VOCABULARIES: Mapping[str, Mapping[str, int]] = MappingProxyType(
    {
        "Sex": MappingProxyType({"Male": 1, "Fmale": 0, "Female": 0}),
        "DLP": MappingProxyType({"Y": 1, "N": 0, "Yes": 1, "No": 0}),
        "Atypical": MappingProxyType({"Y": 1, "N": 0, "Yes": 1, "No": 0}),
        "Nonanginal": MappingProxyType({"Y": 1, "N": 0, "Yes": 1, "No": 0}),
        "Exertional CP": MappingProxyType({"Y": 1, "N": 0, "Yes": 1, "No": 0}),
        "Dyspnea": MappingProxyType({"Y": 1, "N": 0, "Yes": 1, "No": 0}),
    }
)

#: Numeric measurement fields with exact unit and plausibility bounds.
NUMERIC_MEASUREMENTS: Mapping[str, tuple[str, float, float]] = MappingProxyType(
    {
        # field: (unit, inclusive low, inclusive high); all are strictly positive
        "Age": ("years", 1.0, 120.0),
        "BMI": ("kg/m^2", 10.0, 80.0),
        "BP": ("mmHg", 40.0, 300.0),
        "PR": ("beats/min", 20.0, 250.0),
    }
)

#: The single acquisition channel that matches each field's frozen
#: source_domain/input_owner (a verified record of the dataset's domain, not
#: a verified future application/OCR pipeline).
FIELD_VERIFIED_CHANNEL: Mapping[str, str] = MappingProxyType(
    {
        "Age": "structured_history",
        "Sex": "structured_history",
        "BMI": "measurement",
        "DM": "structured_history",
        "HTN": "structured_history",
        "Current Smoker": "structured_history",
        "EX-Smoker": "structured_history",
        "FH": "structured_history",
        "DLP": "structured_history",
        "BP": "measurement",
        "PR": "measurement",
        "Typical Chest Pain": "structured_history",
        "Atypical": "structured_history",
        "Nonanginal": "structured_history",
        "Exertional CP": "structured_history",
        "Dyspnea": "structured_history",
    }
)

ACQUISITION_CHANNELS: frozenset[str] = frozenset(
    {
        "structured_history",
        "clinician_assessment",
        "measurement",
        "laboratory_document",
    }
)
MAPPING_STATUSES: frozenset[str] = frozenset(
    {
        "VERIFIED_REGISTERED_SOURCE_DOMAIN",
        "PROPOSED_FUTURE_ACQUISITION_CHANNEL",
        "NOT_APPLICABLE",
    }
)

#: Sources that may never populate a Track A CAD model input. OCR document
#: extraction is not even a taxonomy channel in this milestone; naming it as a
#: source is rejected, as are wearable and Track B streams.
PROHIBITED_SOURCE_TOKENS: frozenset[str] = frozenset(
    {
        "track_b",
        "wearable",
        "simulated_wearable",
        "patient_wearable",
        "patient_monitoring",
        "ocr_document",
        "ocr",
        "patient_upload",
        "real_data",
        "real_patient",
    }
)

#: Wrong-source markers inherited from the UCI-412 adapter contract.
WRONG_SOURCE_TOKENS: frozenset[str] = frozenset({"?", "-9", "-9.0"})

#: The no-result contract: this module can never produce a CAD probability.
RESULT_STATE: str = "NO_RESULT_NO_CAD_PROBABILITY_COMPUTED"
CONTRACT_REVIEW_STATUS: str = "ACCEPTED_SYNTHETIC_FIXTURE_CONTRACT_ONLY"

REQUIRED_PAYLOAD_KEYS: frozenset[str] = frozenset(
    {
        "contract_version",
        "synthetic",
        "source",
        "feature_order",
        "features",
        "units",
        "missing_reasons",
        "acquisition_sources",
    }
)
SOURCE_BLOCK_KEYS: frozenset[str] = frozenset({"source_id", "dataset_id", "track"})
ACQUISITION_BLOCK_KEYS: frozenset[str] = frozenset({"channel", "mapping_status"})


class FieldContractError(ValueError):
    """Fail-closed validation error with a stable code; never echoes values."""

    def __init__(self, code: str, message: str, *, field: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.field = field


class FieldContractIntegrityError(RuntimeError):
    """The JSON contract and the frozen in-code allowlists disagree."""


@dataclass(frozen=True, slots=True)
class FieldContract:
    """Immutable view of the versioned PROPOSED field contract."""

    schema_id: str
    schema_version: str
    contract_id: str
    status: str
    artifact_kind: str
    source_id: str
    dataset_id: str
    track: str
    panel_id: str
    panel_version: str
    ordered_fields: tuple[str, ...]
    numeric_binary_fields: tuple[str, ...]
    text_binary_fields: tuple[str, ...]
    numeric_measurement_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FieldContractReview:
    """Metadata-only contract review; carries no values and no model result."""

    contract_id: str
    contract_status: str
    source_id: str
    dataset_id: str
    track: str
    reviewed_fields: tuple[str, ...]
    field_order_matches_contract: bool
    acquisition_channels: tuple[tuple[str, str, str], ...]
    proposed_only_fields: tuple[str, ...]
    result_state: str
    review_status: str
    synthetic_only: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "contract_status": self.contract_status,
            "source_id": self.source_id,
            "dataset_id": self.dataset_id,
            "track": self.track,
            "reviewed_fields": list(self.reviewed_fields),
            "field_order_matches_contract": self.field_order_matches_contract,
            "acquisition_channels": [
                {"field": f, "channel": ch, "mapping_status": st}
                for (f, ch, st) in self.acquisition_channels
            ],
            "proposed_only_fields": list(self.proposed_only_fields),
            "result_state": self.result_state,
            "review_status": self.review_status,
            "synthetic_only": self.synthetic_only,
            "cad_probability_computed": False,
        }


def _require(condition: Any, message: str) -> None:
    if not condition:
        raise FieldContractIntegrityError(message)


def _validate_spec_document(document: Mapping[str, Any]) -> None:
    """Fail closed unless the JSON record matches the frozen code allowlists."""
    _require(isinstance(document, Mapping), "Contract document must be a mapping.")
    _require(document.get("schema_id") == CONTRACT_SCHEMA_ID, "Unexpected schema id.")
    _require(
        document.get("schema_version") == CONTRACT_SCHEMA_VERSION,
        "Unexpected schema version.",
    )
    _require(document.get("contract_id") == CONTRACT_ID, "Unexpected contract id.")
    _require(document.get("status") == CONTRACT_STATUS, "Unexpected contract status.")
    _require(
        document.get("artifact_kind") == CONTRACT_ARTIFACT_KIND,
        "Unexpected artifact kind.",
    )

    source = document.get("registered_source")
    _require(isinstance(source, Mapping), "Missing registered source block.")
    for key, expected in REGISTERED_SOURCE.items():
        _require(source.get(key) == expected, f"Registered source {key} mismatch.")

    panel = document.get("panel_binding")
    _require(isinstance(panel, Mapping), "Missing panel binding block.")
    _require(panel.get("panel_id") == "da_a1_basic_clinical_v1", "Panel id mismatch.")
    _require(
        tuple(panel.get("ordered_feature_names", ())) == FIELD_ORDER,
        "Panel ordered feature names mismatch.",
    )
    _require(panel.get("encoded_parameter_count") == 16, "Parameter count mismatch.")

    target = document.get("target_binding")
    _require(isinstance(target, Mapping), "Missing target binding block.")
    _require(
        target.get("threshold_boundary") == "GREATER_THAN_OR_EQUAL_50_PERCENT",
        "Target threshold boundary must remain the UCI-412 >=50% wording.",
    )
    _require(target.get("positive_token") == "Cad", "Target positive token mismatch.")
    _require(target.get("negative_token") == "Normal", "Target negative token mismatch.")

    taxonomy = document.get("acquisition_source_taxonomy")
    _require(isinstance(taxonomy, Mapping), "Missing acquisition taxonomy block.")
    channels = tuple(entry.get("channel") for entry in taxonomy.get("channels", ()))
    _require(
        frozenset(channels) == ACQUISITION_CHANNELS and len(channels) == 4,
        "Acquisition channel taxonomy mismatch.",
    )
    _require(
        frozenset(taxonomy.get("mapping_status_vocabulary", ())) == MAPPING_STATUSES,
        "Mapping status vocabulary mismatch.",
    )

    fields = document.get("fields")
    _require(isinstance(fields, list), "Fields must be a list.")
    _require(
        tuple(field.get("source_name") for field in fields) == FIELD_ORDER,
        "Field set or order mismatch.",
    )
    _require(len(fields) == 16, "Contract must contain exactly 16 fields.")
    for index, field in enumerate(fields):
        name = field.get("source_name")
        _require(field.get("panel_position") == index, f"{name} panel position mismatch.")
        channel_status = {
            m.get("channel"): m.get("mapping_status")
            for m in field.get("acquisition_source_mapping", ())
        }
        # The channel set must be exactly the four taxonomy channels; their
        # listing order is not semantically meaningful, so it is not enforced.
        _require(
            set(channel_status) == ACQUISITION_CHANNELS,
            f"{name} acquisition channel set mismatch.",
        )
        # The single verified channel must agree with the frozen source domain.
        _require(
            channel_status.get(FIELD_VERIFIED_CHANNEL[name])
            == "VERIFIED_REGISTERED_SOURCE_DOMAIN",
            f"{name} verified acquisition channel mismatch.",
        )
        for channel, status in channel_status.items():
            _require(
                status in MAPPING_STATUSES,
                f"{name} acquisition mapping status outside vocabulary.",
            )
            if channel != FIELD_VERIFIED_CHANNEL[name]:
                _require(
                    status != "VERIFIED_REGISTERED_SOURCE_DOMAIN",
                    f"{name} carries an unverified 'verified' acquisition channel.",
                )
        encoding = field.get("source_encoding")
        _require(isinstance(encoding, Mapping), f"{name} missing source encoding.")
        if name in NUMERIC_BINARY_FIELDS:
            _require(field.get("type") == "categorical", f"{name} must be categorical.")
            _require(
                encoding.get("numeric_binary_encoding_id")
                == NUMERIC_BINARY_ENCODING_ID,
                f"{name} numeric-binary encoding id mismatch.",
            )
            _require(
                tuple(sorted(field.get("accepted_values", ()))) == (0, 1),
                f"{name} accepted values must be 0/1.",
            )
        elif name in TEXT_BINARY_VOCABULARIES:
            _require(field.get("type") == "categorical", f"{name} must be categorical.")
            _require(
                encoding.get("encoding_kind") == "text_categorical",
                f"{name} encoding kind mismatch.",
            )
            _require(
                set(field.get("accepted_values", ()))
                == set(TEXT_BINARY_VOCABULARIES[name]),
                f"{name} text vocabulary mismatch.",
            )
        else:
            unit, low, high = NUMERIC_MEASUREMENTS[name]
            _require(field.get("type") == "numeric", f"{name} must be numeric.")
            _require(
                encoding.get("encoding_kind") == "numeric_measurement",
                f"{name} encoding kind mismatch.",
            )
            _require(field.get("unit") == unit, f"{name} unit token mismatch.")
            _require(
                list(field.get("accepted_range", ())) == [low, high],
                f"{name} plausibility range mismatch.",
            )
        _require(field.get("leakage_risk") == "NONE_EXPECTED", f"{name} leakage risk mismatch.")

    no_result = document.get("no_result_contract")
    _require(isinstance(no_result, Mapping), "Missing no-result contract.")
    _require(
        no_result.get("result_state") == RESULT_STATE,
        "No-result contract result state mismatch.",
    )
    envelope = document.get("envelope_contract")
    _require(isinstance(envelope, Mapping), "Missing envelope contract.")
    _require(
        frozenset(envelope.get("required_payload_keys", ())) == REQUIRED_PAYLOAD_KEYS,
        "Envelope payload keys mismatch.",
    )


@lru_cache(maxsize=1)
def load_field_contract() -> FieldContract:
    """Load, validate and cache the versioned field contract."""
    try:
        document = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    except OSError as error:  # pragma: no cover - repository integrity failure
        raise FieldContractIntegrityError(
            "Field contract file is missing or unreadable."
        ) from error
    _validate_spec_document(document)
    return FieldContract(
        schema_id=document["schema_id"],
        schema_version=document["schema_version"],
        contract_id=document["contract_id"],
        status=document["status"],
        artifact_kind=document["artifact_kind"],
        source_id=document["registered_source"]["source_id"],
        dataset_id=document["registered_source"]["dataset_id"],
        track=document["registered_source"]["track"],
        panel_id=document["panel_binding"]["panel_id"],
        panel_version=document["panel_binding"]["panel_version"],
        ordered_fields=tuple(document["panel_binding"]["ordered_feature_names"]),
        numeric_binary_fields=tuple(sorted(NUMERIC_BINARY_FIELDS)),
        text_binary_fields=tuple(TEXT_BINARY_VOCABULARIES),
        numeric_measurement_fields=tuple(NUMERIC_MEASUREMENTS),
    )


def _is_real_int(value: Any) -> bool:
    """A true integer, never a bool (True == 1 would smuggle a code)."""
    return type(value) is int


def _finite_real(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return isfinite(value)
    except OverflowError:
        return False


def _validate_feature_value(name: str, value: Any, units: Mapping[str, Any]) -> None:
    if value is None:
        raise FieldContractError(
            "missing_required_field",
            f"Required field '{name}' cannot be null; the panel has no optional fields.",
            field=name,
        )
    if isinstance(value, str) and value.strip() in WRONG_SOURCE_TOKENS:
        raise FieldContractError(
            "wrong_source_token",
            f"Wrong-source marker supplied for '{name}'.",
            field=name,
        )
    if name in NUMERIC_BINARY_FIELDS:
        if not _is_real_int(value) or value not in (0, 1):
            raise FieldContractError(
                "invalid_numeric_binary_value",
                f"'{name}' accepts only integer 0 or 1; text, booleans and other numbers fail.",
                field=name,
            )
        if name in units:
            raise FieldContractError(
                "unit_for_binary_field",
                f"Binary field '{name}' must not carry a unit token.",
                field=name,
            )
    elif name in TEXT_BINARY_VOCABULARIES:
        vocabulary = TEXT_BINARY_VOCABULARIES[name]
        if not isinstance(value, str) or value not in vocabulary:
            raise FieldContractError(
                "unknown_categorical_token",
                f"Unregistered categorical token for '{name}'.",
                field=name,
            )
        if name in units:
            raise FieldContractError(
                "unit_for_binary_field",
                f"Categorical field '{name}' must not carry a unit token.",
                field=name,
            )
    else:
        unit, low, high = NUMERIC_MEASUREMENTS[name]
        if not _finite_real(value):
            raise FieldContractError(
                "invalid_numeric_value",
                f"Non-finite or non-numeric measurement for '{name}'.",
                field=name,
            )
        number = float(value)
        if number <= 0.0:
            raise FieldContractError(
                "zero_or_non_positive_measurement_unavailable",
                f"A zero/non-positive '{name}' is an unavailable measurement, not data.",
                field=name,
            )
        if not (low <= number <= high):
            raise FieldContractError(
                "value_out_of_plausible_range",
                f"Measurement for '{name}' is outside its registered plausibility bounds.",
                field=name,
            )
        declared = units.get(name)
        if declared != unit:
            raise FieldContractError(
                "ambiguous_or_mismatched_unit",
                f"'{name}' requires the exact unit token '{unit}'; no silent conversion is performed.",
                field=name,
            )


def review_uci412_field_contract(payload: Mapping[str, Any]) -> FieldContractReview:
    """Validate one synthetic UCI-412 acquisition-tagged fixture against the contract.

    Returns a metadata-only review whose result state is always
    ``NO_RESULT_NO_CAD_PROBABILITY_COMPUTED``. Every structural, coding, unit,
    ordering, provenance or acquisition-source violation fails closed with a
    stable :class:`FieldContractError`; error messages never echo submitted
    values.
    """
    contract = load_field_contract()

    if not isinstance(payload, Mapping):
        raise FieldContractError("malformed_payload", "Contract payload must be a mapping.")
    keys = set(payload)
    missing = REQUIRED_PAYLOAD_KEYS - keys
    if missing:
        raise FieldContractError(
            "missing_required_metadata", "Missing required payload metadata keys."
        )
    if keys != REQUIRED_PAYLOAD_KEYS:
        raise FieldContractError("malformed_payload", "Unknown payload envelope property.")

    if payload["contract_version"] != contract.contract_id:
        raise FieldContractError(
            "unsupported_contract_version", "Unsupported contract version."
        )
    if payload["synthetic"] is not True:
        raise FieldContractError(
            "non_synthetic_input", "Only explicitly synthetic fixtures are supported."
        )

    source = payload["source"]
    if not isinstance(source, Mapping):
        raise FieldContractError(
            "missing_required_metadata", "Source provenance block must be a mapping."
        )
    if set(source) != SOURCE_BLOCK_KEYS:
        raise FieldContractError("malformed_payload", "Unknown source provenance property.")
    if str(source.get("track")).lower() in PROHIBITED_SOURCE_TOKENS or source.get("track") == "B":
        raise FieldContractError(
            "track_b_or_prohibited_source",
            "Track B / wearable / OCR / real-patient sources are prohibited for Track A.",
        )
    if (
        source.get("source_id"),
        source.get("dataset_id"),
        source.get("track"),
    ) != (contract.source_id, contract.dataset_id, contract.track):
        raise FieldContractError(
            "unsupported_source",
            "Payload source does not match UCI-412 / DA-A1; no cross-dataset harmonization is registered.",
        )

    for block_name in ("features", "units", "missing_reasons", "acquisition_sources"):
        block = payload[block_name]
        if not isinstance(block, Mapping):
            raise FieldContractError("malformed_payload", f"{block_name} must be a mapping.")
        if not all(isinstance(key, str) for key in block):
            raise FieldContractError("malformed_payload", f"{block_name} keys must be strings.")

    feature_order = payload["feature_order"]
    if not isinstance(feature_order, (list, tuple)) or not all(
        isinstance(item, str) for item in feature_order
    ):
        raise FieldContractError(
            "malformed_feature_order", "feature_order must be a list of field names."
        )
    if tuple(feature_order) != FIELD_ORDER:
        raise FieldContractError(
            "incorrect_feature_order",
            "Feature order does not match the registered da_a1_basic_clinical_v1 panel order.",
        )

    features = payload["features"]
    units = payload["units"]
    reasons = payload["missing_reasons"]
    acquisition = payload["acquisition_sources"]

    referenced = set(features) | set(units) | set(reasons) | set(acquisition)
    unknown = referenced - set(FIELD_ORDER)
    if unknown:
        raise FieldContractError(
            "unregistered_field",
            "A supplied field is not part of the UCI-412 16-feature contract.",
            field=sorted(unknown)[0],
        )
    absent = [name for name in FIELD_ORDER if name not in features]
    if absent:
        raise FieldContractError(
            "missing_required_field",
            "Every one of the 16 panel fields is required and must be present.",
            field=sorted(absent)[0],
        )
    if set(features) != set(FIELD_ORDER):
        raise FieldContractError(
            "field_set_mismatch", "The feature set must be exactly the 16 registered fields."
        )
    if reasons:
        raise FieldContractError(
            "missing_reason_not_supported",
            "The basic clinical panel declares no optional fields; missing reasons are not accepted.",
        )

    # Every field needs a validated acquisition-source declaration.
    if set(acquisition) != set(FIELD_ORDER):
        raise FieldContractError(
            "acquisition_source_mismatch",
            "Every field must declare exactly one acquisition-source block.",
        )
    proposed_only: list[str] = []
    acquisition_tuples: list[tuple[str, str, str]] = []
    for name in FIELD_ORDER:
        block = acquisition[name]
        if not isinstance(block, Mapping) or set(block) != ACQUISITION_BLOCK_KEYS:
            raise FieldContractError(
                "malformed_acquisition_block",
                f"Acquisition block for '{name}' must contain channel and mapping_status only.",
                field=name,
            )
        channel = block["channel"]
        status = block["mapping_status"]
        if not isinstance(channel, str) or not isinstance(status, str):
            raise FieldContractError(
                "malformed_acquisition_block",
                f"Acquisition block for '{name}' has non-string entries.",
                field=name,
            )
        if channel.lower() in PROHIBITED_SOURCE_TOKENS:
            raise FieldContractError(
                "prohibited_acquisition_channel",
                f"Channel for '{name}' is prohibited (wearable / OCR / Track B / real patient).",
                field=name,
            )
        if channel not in ACQUISITION_CHANNELS:
            raise FieldContractError(
                "unknown_acquisition_channel",
                f"Unknown acquisition channel for '{name}'.",
                field=name,
            )
        if status not in MAPPING_STATUSES:
            raise FieldContractError(
                "unknown_mapping_status",
                f"Unknown acquisition mapping status for '{name}'.",
                field=name,
            )
        if status == "NOT_APPLICABLE":
            raise FieldContractError(
                "not_applicable_channel_used",
                f"A NOT_APPLICABLE channel cannot be the acquisition source for '{name}'.",
                field=name,
            )
        if status == "VERIFIED_REGISTERED_SOURCE_DOMAIN":
            if channel != FIELD_VERIFIED_CHANNEL[name]:
                raise FieldContractError(
                    "unverified_verified_channel",
                    f"'{name}' marks a channel verified that is not its registered source domain.",
                    field=name,
                )
        else:  # PROPOSED_FUTURE_ACQUISITION_CHANNEL
            proposed_only.append(name)
        acquisition_tuples.append((name, channel, status))

    # Units may only declare the registered measurement fields, exactly.
    expected_unit_fields = set(NUMERIC_MEASUREMENTS)
    if set(units) != expected_unit_fields:
        raise FieldContractError(
            "unit_keys_mismatch",
            "Units must be supplied for exactly the four numeric measurement fields.",
        )

    for name in FIELD_ORDER:
        _validate_feature_value(name, features[name], units)

    return FieldContractReview(
        contract_id=contract.contract_id,
        contract_status=contract.status,
        source_id=contract.source_id,
        dataset_id=contract.dataset_id,
        track=contract.track,
        reviewed_fields=tuple(FIELD_ORDER),
        field_order_matches_contract=True,
        acquisition_channels=tuple(acquisition_tuples),
        proposed_only_fields=tuple(proposed_only),
        result_state=RESULT_STATE,
        review_status=CONTRACT_REVIEW_STATUS,
        synthetic_only=True,
    )
