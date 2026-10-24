"""Versioned UCI-412 research feature dictionary and panel admission rules.

The JSON dictionary in ``schemas/`` is the reviewable record: clinical meaning,
unit, coding, source domain, availability, missing semantics, leakage risk,
owner, evidence, uncertainty, and admission status for every source column.

This module validates that record against the source profile and against the
in-code panel allowlist. The allowlist is intentionally duplicated in code so a
JSON-only edit cannot quietly admit a new predictor into an executable panel.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Final, Mapping

from research.uci412.errors import SchemaError
from research.uci412.source_spec import (
    ECHO_COLUMNS,
    LAB_COLUMNS,
    PREDICTOR_COLUMNS,
    PROHIBITED_PREDICTORS,
    SOURCE_COLUMNS,
    TARGET_COLUMN,
    column_group,
)

PACKAGE_ROOT: Final[Path] = Path(__file__).resolve().parent
DICTIONARY_PATH: Final[Path] = PACKAGE_ROOT / "schemas" / "uci412_feature_dictionary.v1.json"
DICTIONARY_SCHEMA_ID: Final[str] = "uci412_research_feature_dictionary"
DICTIONARY_SCHEMA_VERSION: Final[str] = "1.0.0"

PRIMARY_PANEL_ID: Final[str] = "uci412_basic_clinical_v1"
PRIMARY_PANEL_VERSION: Final[str] = "1.0.0"

#: Ordered executable panel. Duplicated deliberately: the JSON must agree with
#: this tuple, and any new predictor requires a reviewed code change.
PRIMARY_PANEL_COLUMNS: Final[tuple[str, ...]] = (
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

ECG_PANEL_COLUMNS: Final[tuple[str, ...]] = (
    "Q Wave",
    "St Elevation",
    "St Depression",
    "Tinversion",
    "LVH",
    "Poor R Progression",
    "BBB",
)

REGISTERED_PANELS: Final[tuple[str, ...]] = (
    PRIMARY_PANEL_ID,
    "uci412_basic_plus_resting_ecg_v1",
    "uci412_expanded_clinical_v1",
    "uci412_basic_plus_laboratory_v1",
)

EXECUTABLE_PANELS: Final[tuple[str, ...]] = (PRIMARY_PANEL_ID,)

ADMISSION_STATUSES: Final[frozenset[str]] = frozenset(
    {
        "ADMITTED_PRIMARY_PANEL",
        "REGISTERED_EXPANDED_PANEL_ONLY",
        "EXCLUDED_DERIVED_REDUNDANT",
        "EXCLUDED_ECHO_TIMING_UNVERIFIED",
        "EXCLUDED_TARGET",
    }
)

REQUIRED_FEATURE_FIELDS: Final[tuple[str, ...]] = (
    "column",
    "position",
    "group",
    "role",
    "kind",
    "clinical_meaning",
    "unit",
    "unit_evidence_status",
    "source_domain",
    "availability_at_decision_time",
    "missing_semantics",
    "leakage_risk",
    "input_owner",
    "evidence",
    "uncertainty",
    "admission",
    "panels",
    "vocabulary",
    "plausible_range",
)

NUMERIC_ROLES: Final[frozenset[str]] = frozenset({"numeric"})
CATEGORICAL_ROLES: Final[frozenset[str]] = frozenset({"categorical"})


@dataclass(frozen=True, slots=True)
class FeatureSpec:
    """One registered source column and its research metadata."""

    column: str
    position: int
    group: str
    role: str
    kind: str
    clinical_meaning: str
    unit: str | None
    unit_evidence_status: str
    source_domain: str
    availability_at_decision_time: str
    missing_semantics: str
    leakage_risk: str
    leakage_note: str | None
    input_owner: str
    evidence: tuple[str, ...]
    uncertainty: str
    admission: str
    panels: tuple[str, ...]
    exclusion_reason: str | None
    vocabulary: Mapping[str, int] | None
    plausible_range: tuple[float, float] | None
    source_reported_typical_range: tuple[float, float] | None

    @property
    def is_numeric(self) -> bool:
        return self.role in NUMERIC_ROLES

    @property
    def is_categorical(self) -> bool:
        return self.role in CATEGORICAL_ROLES

    @property
    def codes(self) -> tuple[int, ...]:
        if not self.vocabulary:
            raise SchemaError(f"Column '{self.column}' has no registered categorical vocabulary.")
        return tuple(sorted(set(int(value) for value in self.vocabulary.values())))

    def as_review_dict(self) -> dict[str, Any]:
        return {
            "column": self.column,
            "position": self.position,
            "group": self.group,
            "role": self.role,
            "kind": self.kind,
            "clinical_meaning": self.clinical_meaning,
            "unit": self.unit,
            "unit_evidence_status": self.unit_evidence_status,
            "source_domain": self.source_domain,
            "availability_at_decision_time": self.availability_at_decision_time,
            "missing_semantics": self.missing_semantics,
            "leakage_risk": self.leakage_risk,
            "leakage_note": self.leakage_note,
            "input_owner": self.input_owner,
            "evidence": list(self.evidence),
            "uncertainty": self.uncertainty,
            "admission": self.admission,
            "panels": list(self.panels),
            "exclusion_reason": self.exclusion_reason,
        }


@dataclass(frozen=True, slots=True)
class PanelSpec:
    """One registered candidate input panel."""

    panel_id: str
    version: str
    display_name: str
    status: str
    executable: bool
    intended_moment: str
    columns: tuple[str, ...]
    rationale: str
    blockers: tuple[str, ...]

    def as_review_dict(self) -> dict[str, Any]:
        return {
            "panel_id": self.panel_id,
            "version": self.version,
            "display_name": self.display_name,
            "status": self.status,
            "executable_in_this_code_commit": self.executable,
            "intended_moment": self.intended_moment,
            "columns": list(self.columns),
            "rationale": self.rationale,
            "blockers": list(self.blockers),
        }


@dataclass(frozen=True, slots=True)
class FeatureDictionary:
    """Validated feature dictionary plus the derived executable panel."""

    schema_id: str
    schema_version: str
    status: str
    features: Mapping[str, FeatureSpec]
    panels: Mapping[str, PanelSpec]

    def panel(self, panel_id: str) -> PanelSpec:
        try:
            return self.panels[panel_id]
        except KeyError as exc:
            raise SchemaError(f"Panel '{panel_id}' is not registered.") from exc

    @property
    def primary_panel(self) -> PanelSpec:
        return self.panel(PRIMARY_PANEL_ID)

    def feature(self, column: str) -> FeatureSpec:
        try:
            return self.features[column]
        except KeyError as exc:
            raise SchemaError(f"Column '{column}' is not registered in the feature dictionary.") from exc

    def executable_columns(self) -> tuple[str, ...]:
        panel = self.primary_panel
        if not panel.executable or panel.status not in {
            "ADMITTED_FOR_INTERNAL_RESEARCH_SUBJECT_TO_M3A_AUTHORIZATION"
        }:
            raise SchemaError("The primary panel is not admitted for internal research execution.")
        if panel.columns != PRIMARY_PANEL_COLUMNS:
            raise SchemaError("The primary panel columns do not match the reviewed in-code allowlist.")
        return panel.columns

    def numeric_columns(self) -> tuple[str, ...]:
        return tuple(column for column in self.executable_columns() if self.feature(column).is_numeric)

    def categorical_columns(self) -> tuple[str, ...]:
        return tuple(column for column in self.executable_columns() if self.feature(column).is_categorical)

    def category_codes(self) -> dict[str, tuple[int, ...]]:
        return {column: self.feature(column).codes for column in self.categorical_columns()}

    def encoded_parameter_count(self, columns: tuple[str, ...] | None = None) -> int:
        """Reference-coded parameter count for the named columns (see sample_size.py)."""
        selected = self.executable_columns() if columns is None else columns
        total = 0
        for column in selected:
            spec = self.feature(column)
            if spec.is_numeric:
                total += 1
            elif spec.kind == "binary":
                total += 1
            else:
                total += len(spec.codes) - 1
        return total

    def as_review_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "status": self.status,
            "executable_panel": self.primary_panel.as_review_dict(),
            "registered_blocked_panels": [
                panel.as_review_dict() for panel in self.panels.values() if not panel.executable
            ],
            "excluded_columns": [
                {
                    "column": spec.column,
                    "admission": spec.admission,
                    "reason": spec.exclusion_reason,
                }
                for spec in self.features.values()
                if not spec.panels
            ],
        }


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SchemaError(f"Registered UCI-412 feature dictionary violates an invariant: {message}")


def _as_range(value: Any, column: str) -> tuple[float, float] | None:
    if value is None:
        return None
    _require(isinstance(value, list) and len(value) == 2, f"'{column}' plausible_range shape")
    low, high = float(value[0]), float(value[1])
    _require(low < high, f"'{column}' plausible_range order")
    return (low, high)


def _build_feature(raw: Mapping[str, Any]) -> FeatureSpec:
    for field in REQUIRED_FEATURE_FIELDS:
        _require(field in raw, f"missing field '{field}'")
    column = raw["column"]
    _require(isinstance(column, str) and column in SOURCE_COLUMNS, f"unregistered column '{column}'")
    _require(raw["group"] == column_group(column), f"'{column}' group mismatch")
    _require(raw["role"] in NUMERIC_ROLES | CATEGORICAL_ROLES, f"'{column}' role")
    _require(raw["kind"] in {"continuous", "binary", "ordinal"}, f"'{column}' kind")
    _require(raw["admission"] in ADMISSION_STATUSES, f"'{column}' admission status")
    _require(isinstance(raw["evidence"], list) and raw["evidence"], f"'{column}' evidence")
    _require(isinstance(raw["uncertainty"], str) and raw["uncertainty"], f"'{column}' uncertainty")

    vocabulary = raw["vocabulary"]
    if vocabulary is not None:
        _require(isinstance(vocabulary, dict) and vocabulary, f"'{column}' vocabulary")
        codes = [int(value) for value in vocabulary.values()]
        _require(all(type(value) is int for value in codes), f"'{column}' vocabulary codes must be integers")
        if raw["kind"] == "binary":
            _require(sorted(set(codes)) == [0, 1], f"'{column}' binary codes must be 0/1")
        else:
            # Ordinal codes must stay contiguous so a registered scale cannot be
            # split by an accidentally invented level. Both the 0-based (e.g.
            # VHD: N/Mild/Moderate/Severe) and 1-based (e.g. Function Class)
            # conventions are registered in the dictionary; each must be whole.
            distinct = sorted(set(codes))
            _require(
                distinct == list(range(len(distinct)))
                or distinct == list(range(1, len(distinct) + 1)),
                f"'{column}' ordinal codes must be a contiguous zero- or one-based sequence",
            )
    if raw["role"] == "categorical":
        _require(vocabulary is not None, f"categorical '{column}' requires a registered vocabulary")

    plausible_range = _as_range(raw["plausible_range"], column)
    if raw["role"] == "numeric" and raw["admission"] == "ADMITTED_PRIMARY_PANEL":
        _require(plausible_range is not None, f"admitted numeric '{column}' requires a plausibility guard")

    panels = tuple(raw["panels"])
    _require(len(set(panels)) == len(panels), f"'{column}' duplicate panel membership")
    _require(set(panels) <= set(REGISTERED_PANELS), f"'{column}' unknown panel membership")

    return FeatureSpec(
        column=column,
        position=int(raw["position"]),
        group=str(raw["group"]),
        role=str(raw["role"]),
        kind=str(raw["kind"]),
        clinical_meaning=str(raw["clinical_meaning"]),
        unit=raw["unit"],
        unit_evidence_status=str(raw["unit_evidence_status"]),
        source_domain=str(raw["source_domain"]),
        availability_at_decision_time=str(raw["availability_at_decision_time"]),
        missing_semantics=str(raw["missing_semantics"]),
        leakage_risk=str(raw["leakage_risk"]),
        leakage_note=raw["leakage_note"],
        input_owner=str(raw["input_owner"]),
        evidence=tuple(str(item) for item in raw["evidence"]),
        uncertainty=str(raw["uncertainty"]),
        admission=str(raw["admission"]),
        panels=panels,
        exclusion_reason=raw["exclusion_reason"],
        vocabulary=(
            None if vocabulary is None else {str(key): int(value) for key, value in vocabulary.items()}
        ),
        plausible_range=plausible_range,
        source_reported_typical_range=_as_range(raw["source_reported_typical_range"], column),
    )


def load_feature_dictionary(path: Path = DICTIONARY_PATH) -> FeatureDictionary:
    """Load, validate, and freeze the registered research feature dictionary."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - message must not echo file contents
        raise SchemaError("The UCI-412 feature dictionary is missing or is not valid JSON.") from exc
    _require(isinstance(raw, dict), "dictionary root must be an object")
    _require(raw.get("schema_id") == DICTIONARY_SCHEMA_ID, "schema id")
    _require(raw.get("schema_version") == DICTIONARY_SCHEMA_VERSION, "schema version")
    _require(raw.get("source_id") == "UCI-412" and raw.get("dataset_id") == "DA-A1", "source scope")

    raw_features = raw.get("features")
    _require(isinstance(raw_features, dict), "features block")
    _require(tuple(raw_features) == SOURCE_COLUMNS, "features must follow the registered source order")
    features = {column: _build_feature(payload) for column, payload in raw_features.items()}
    _require(len(features) == len(SOURCE_COLUMNS), "one entry per source column")

    raw_panels = raw.get("panels")
    _require(isinstance(raw_panels, list) and raw_panels, "panels block")
    panels: dict[str, PanelSpec] = {}
    for payload in raw_panels:
        panel_id = str(payload.get("panel_id"))
        _require(panel_id in REGISTERED_PANELS, f"unknown panel '{panel_id}'")
        _require(panel_id not in panels, f"duplicate panel '{panel_id}'")
        columns = tuple(str(column) for column in payload.get("columns", ()))
        _require(len(set(columns)) == len(columns), f"panel '{panel_id}' duplicate columns")
        _require(set(columns) <= set(PREDICTOR_COLUMNS), f"panel '{panel_id}' unknown or target column")
        _require(not (set(columns) & PROHIBITED_PREDICTORS), f"panel '{panel_id}' contains a prohibited column")
        for column in columns:
            _require(panel_id in features[column].panels, f"'{column}' inconsistent panel membership")
        executable = bool(payload.get("executable_in_this_code_commit"))
        status = str(payload.get("status"))
        _require(
            executable == (panel_id in EXECUTABLE_PANELS),
            f"panel '{panel_id}' executable flag must match the reviewed allowlist",
        )
        _require(
            (status == "REGISTERED_BLOCKED") == (not executable),
            f"panel '{panel_id}' status/executable mismatch",
        )
        panels[panel_id] = PanelSpec(
            panel_id=panel_id,
            version=str(payload.get("version")),
            display_name=str(payload.get("display_name")),
            status=status,
            executable=executable,
            intended_moment=str(payload.get("intended_moment")),
            columns=columns,
            rationale=str(payload.get("rationale")),
            blockers=tuple(str(item) for item in payload.get("blockers", ())),
        )
    _require(tuple(panels) == REGISTERED_PANELS, "panels must be registered in the reviewed order")
    dictionary = FeatureDictionary(
        schema_id=DICTIONARY_SCHEMA_ID,
        schema_version=DICTIONARY_SCHEMA_VERSION,
        status=str(raw.get("status")),
        features=features,
        panels=panels,
    )

    _require(dictionary.primary_panel.columns == PRIMARY_PANEL_COLUMNS, "primary panel allowlist")
    _require(
        dictionary.feature(TARGET_COLUMN).admission == "EXCLUDED_TARGET"
        and TARGET_COLUMN not in dictionary.primary_panel.columns,
        "target column must be excluded from every panel",
    )
    for column in ECHO_COLUMNS:
        _require(features[column].panels == (), f"echocardiography column '{column}' must not join a panel")
    for column in features:
        spec = features[column]
        if column in LAB_COLUMNS:
            _require(
                set(spec.panels) <= {"uci412_basic_plus_laboratory_v1"},
                f"laboratory column '{column}' may only be registered in the blocked laboratory panel",
            )
        if spec.admission == "ADMITTED_PRIMARY_PANEL":
            _require(PRIMARY_PANEL_ID in spec.panels, f"admitted '{column}' missing from the primary panel")
            _require(spec.unit_evidence_status != "NOT_DOCUMENTED", f"admitted '{column}' needs a unit statement")
            _require(
                spec.availability_at_decision_time == "EXPECTED_AVAILABLE_BEFORE_ANGIOGRAPHY",
                f"admitted '{column}' must be expected at the decision moment",
            )
            _require(spec.leakage_risk == "NONE_EXPECTED", f"admitted '{column}' may not carry a leakage risk")
    for column in PRIMARY_PANEL_COLUMNS:
        _require(features[column].admission == "ADMITTED_PRIMARY_PANEL", f"'{column}' admission mismatch")
    return dictionary


DEFAULT_DICTIONARY: Final[FeatureDictionary] = load_feature_dictionary()


def describe_panels(dictionary: FeatureDictionary = DEFAULT_DICTIONARY) -> dict[str, Any]:
    """Return an aggregate, patient-free description used by the CLI ``describe`` command."""
    return {
        "source_id": "UCI-412",
        "dataset_id": "DA-A1",
        "feature_dictionary": dictionary.as_review_dict(),
        "executable_parameter_count": dictionary.encoded_parameter_count(),
        "numeric_columns": list(dictionary.numeric_columns()),
        "categorical_columns": list(dictionary.categorical_columns()),
        "declared_not_registered": [
            "All-55-predictor panel",
            "UCI-45 name harmonisation or pooling",
            "UCI-411 LAD/LCX/RCA artery outcomes",
        ],
    }
