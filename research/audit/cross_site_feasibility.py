"""Focused, aggregate-only UCI-45 cross-site feasibility audit (Cleveland vs Hungary / VA).

Purpose: produce NEW real-source compatibility evidence for a *possible future*
Cleveland-to-Hungary or Cleveland-to-VA comparison, without fitting a model,
evaluating performance, pooling cohorts, translating source labels, altering
original files, imputing values, or inferring patient identities.

Scope discipline
----------------
* This is a read-only diagnostic within the D-046 local audit authorization for
  ``DA-A2`` (UCI-45). It parses only three conventional 14-column ``processed.*``
  cohorts (Cleveland reference; Hungary and VA comparators); the source-warned raw
  ``cleveland.data`` remains quarantined and is never opened.
* Every input file is SHA-256/byte-size verified and byte-guarded for the whole
  run. Outputs are restricted to ``data/reports/`` and are aggregate counts,
  fixed labels, and documented codes only.
* A Cleveland-vs-Hungary/VA *model or outcome comparison* is NOT authorized by
  D-046 or D-047 (Gate PT P-3 CLOSED; D-047 is Cleveland-only). This module
  therefore reports feasibility diagnostics and explicit blockers, and never
  produces a comparison result, score, or scientific claim.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from collections import Counter
from typing import Any, Mapping, Sequence

from research.audit.availability_scenarios import (
    PROCESSED_FILES,
    ZERO_UNAVAILABLE_SENSITIVITY_FIELDS,
    descriptive_panel_counts,
)
from research.audit.cli import REPO_ROOT
from research.audit.duplicates import (
    SHARED_11_PREDICTOR_NO_CA_THAL,
    SHARED_13_PREDICTOR_COLUMNS,
    compute_cross_cohort_duplicates,
    compute_exact_profile_multiset_overlap,
)
from research.audit.git_safety import verify_data_root_containment, verify_git_ignore
from research.audit.provenance import (
    ByteIdentityGuard,
    load_authorization_manifest,
    validate_and_resolve_report_output_path,
    validate_provenance_manifest,
    verify_dataset_authorized_for_audit,
    verify_global_workflow_authorized,
)
from research.audit.registry import EVIDENCE_VERIFIED, UCI_45_PROCESSED_DOMAIN_RULES
from research.audit.reporting import (
    assert_exact_keys,
    assert_int_not_bool,
    verify_report_no_patient_rows,
)
from research.audit.validators import audit_uci_45_processed_file

REPORT_SCHEMA_VERSION = "1.0.0"
REPORT_TYPE = "UCI45_CLEVELAND_VS_HUNGARY_VA_READ_ONLY_FEASIBILITY_AUDIT"
STATUS_LABEL = "READ_ONLY_DESCRIPTIVE_ONLY_NOT_TRAINING_OR_COMPARISON_AUTHORIZATION"

PREDECLARED_FIVE_FIELDS: tuple[str, ...] = ("age", "sex", "cp", "trestbps", "restecg")
CATEGORICAL_FIVE_SUBSET: tuple[str, ...] = ("sex", "cp", "restecg")
NUMERIC_FIVE_SUBSET: tuple[str, ...] = ("age", "trestbps")

REFERENCE_COHORT = "cleveland"
COMPARATOR_COHORTS: tuple[str, ...] = ("hungarian", "va")
AUDITED_COHORTS: tuple[str, ...] = (REFERENCE_COHORT,) + COMPARATOR_COHORTS
COHORTS_NOT_ASSESSED: Mapping[str, str] = {
    "switzerland": "OUT_OF_SCOPE_FOCUSED_CLEVELAND_VS_HUNGARY_AND_VA",
}

TARGET_COLUMN = "num"
TARGET_LABEL_CODES: tuple[str, ...] = ("0", "1", "2", "3", "4")
CLASS_STRATA_KEYS: tuple[str, ...] = tuple(
    f"original_target_label_{code}" for code in TARGET_LABEL_CODES
) + ("original_target_label_unclassified", "all_original_target_labels")
CATEGORICAL_CODE_KEYS: tuple[str, ...] = ("0", "1", "2", "3", "4")

AGE_BAND_LABELS: tuple[str, ...] = ("lt_1", "1_to_44", "45_to_59", "60_to_74", "75_to_89", "90_plus")
TRESTBPS_BAND_LABELS: tuple[str, ...] = (
    "lt_1",
    "1_to_89",
    "90_to_119",
    "120_to_139",
    "140_to_159",
    "160_to_179",
    "180_plus",
)

UCI_45_TARGET_RULE_TEXT = (
    "Official UCI-45 documentation (heart-disease.names, July 1988): num 0 = <50% diameter "
    "narrowing; num 1-4 = >50% diameter narrowing in any major vessel. The wording difference "
    "against other sources and the exact-50% boundary (H-01) remain UNRESOLVED, and no per-file "
    "patient-level codebook equality is assumed here."
)

UNIT_DOCUMENTED_SOURCE = (
    "UCI-45 conventional 14-attribute dictionary (heart-disease.names, July 1988) plus the "
    "official UCI-45 dataset page: age in years, trestbps in mm Hg, categorical codes as integer "
    "codebook values. Unit identity is NOT provable from file content alone."
)

IDENTITY_AND_INDEPENDENCE_WARNINGS: tuple[dict[str, str], ...] = (
    {
        "warning_id": "W-01",
        "statement": (
            "Exact-profile matches across cohorts do NOT prove patient identity. A match is a "
            "feature-vector collision in identifier-free tabular data; no identifier was read, "
            "derived, or linked, and no patient mapping is created or permitted."
        ),
    },
    {
        "warning_id": "W-02",
        "statement": (
            "Absence of exact-profile matches does NOT prove cohort independence. Different "
            "records can describe the same person under recoding, missingness, or shifted "
            "measurement, and proven independence can never be established from identifier-free "
            "data."
        ),
    },
    {
        "warning_id": "W-03",
        "statement": (
            "The five predeclared fields are coarse. Repeated ordinary clinical profiles are "
            "expected in referral cohorts, so overlap counts are not an identity or duplication "
            "rate and must not be reported as one."
        ),
    },
    {
        "warning_id": "W-04",
        "statement": (
            "Duplicate multiplicity is preserved by a minimum-multiplicity multiset intersection. "
            "Reported record pairs count combinations consistent with a profile match; they are "
            "not confirmed duplicate patients."
        ),
    },
    {
        "warning_id": "W-05",
        "statement": (
            "Availability and code-compatibility counts describe recorded source values. They are "
            "NOT model eligibility, effective sample size, transportability evidence, or a "
            "clinical suitability certificate."
        ),
    },
    {
        "warning_id": "W-06",
        "statement": (
            "No target label is translated, binarized in the source files, or otherwise rewritten. "
            "The 0-versus-1..4 grouping is an in-memory stratification rule only, and its "
            "patient-level semantic equivalence across sites remains UNVERIFIED."
        ),
    },
)

AUDIT_BLOCKERS: tuple[dict[str, str], ...] = (
    {
        "blocker_id": "B-01-TARGET-BOUNDARY",
        "summary": (
            "Target-threshold harmonization H-01 (>50% versus >=50%; exact-50% boundary) remains "
            "open, so a cross-site outcome definition cannot be frozen."
        ),
        "required_resolution": "Documented source/clinical adjudication of the 50% boundary and a recorded harmonization ruling.",
        "required_authorization": "Clinical/research-lead review; Gate PT P-1 endpoint decision.",
        "status": "OPEN",
    },
    {
        "blocker_id": "B-02-GATE-PT-CLOSED",
        "summary": (
            "Gate PT P-3 is CLOSED: no supervisor-approved protocol exists for fitting, feature "
            "selection, calibration, explanation, or model evaluation."
        ),
        "required_resolution": "Frozen protocol and supervisor sign-off recorded in the decision register.",
        "required_authorization": "Supervisor Gate PT P-3 sign-off (separate governance process).",
        "status": "OPEN",
    },
    {
        "blocker_id": "B-03-D047-SCOPE",
        "summary": (
            "D-047 covers one INTERNAL exploratory Cleveland-only experiment. It does not authorize "
            "Hungary or VA use, pooling, or any external comparison."
        ),
        "required_resolution": "A separate, explicitly scoped governance decision naming the cohorts and the permitted comparison.",
        "required_authorization": "New maintainer governance decision/amendment; not implied by this audit.",
        "status": "OPEN",
    },
    {
        "blocker_id": "B-04-RAW-CLEVELAND-QUARANTINE",
        "summary": (
            "The source-warned raw cleveland.data remains quarantined and unparsed, so reference-site "
            "raw-versus-processed correspondence cannot be re-verified here."
        ),
        "required_resolution": "Human review of the upstream integrity warning and an approved, documented parse strategy.",
        "required_authorization": "Separate maintainer review of Issue #18 evidence; no repair or transcoding by an agent.",
        "status": "OPEN",
    },
    {
        "blocker_id": "B-05-REPRESENTATION-ALIGNMENT",
        "summary": (
            "Positional raw-versus-processed discordance for Hungary/Switzerland is unresolved, so the "
            "relationship between source representations is not established."
        ),
        "required_resolution": "Aggregate-only alignment/duplication review recorded against Issues #20 and #21.",
        "required_authorization": "Maintainer scientific review of the carried-forward audit evidence.",
        "status": "OPEN",
    },
    {
        "blocker_id": "B-06-INDEPENDENCE-NOT-PROVABLE",
        "summary": (
            "Patient independence between sites cannot be proven from identifier-free tabular data, "
            "and Statlog-Cleveland recirculation (L-05) remains an open provenance risk."
        ),
        "required_resolution": "Source-provenance evidence and an explicit overlap-resolution rule for any downstream comparison.",
        "required_authorization": "Gate PT decision on overlap handling; DA-B2 remains audit-only.",
        "status": "OPEN",
    },
    {
        "blocker_id": "B-07-UNIT-IDENTITY",
        "summary": (
            "Measurement-unit identity across sites is not verifiable from file content; only "
            "heuristic plausibility diagnostics are reported."
        ),
        "required_resolution": "Primary-source unit documentation review for each retained field and site.",
        "required_authorization": "Research-lead/source verification record; not inferable from value ranges.",
        "status": "OPEN",
    },
    {
        "blocker_id": "B-08-D046-READ-ONLY-SCOPE",
        "summary": (
            "D-046 authorizes read-only dataset auditing only. This report is descriptive and does not "
            "authorize any model, metric, comparison, or clinical claim."
        ),
        "required_resolution": "None for the audit itself; downstream work needs the authorizations listed above.",
        "required_authorization": "Existing D-046 scope is sufficient for THIS audit and insufficient for any comparison.",
        "status": "ACKNOWLEDGED",
    },
)

EVIDENCE_LIMITATIONS: tuple[dict[str, str], ...] = (
    {
        "limitation_id": "L-01-PROCESSED-ONLY",
        "statement": (
            "Only conventional 14-column processed cohorts are parsed. Raw 76-attribute files are "
            "byte-guarded but not read, and raw Cleveland is quarantined."
        ),
    },
    {
        "limitation_id": "L-02-NO-PATIENT-SEMANTICS",
        "statement": (
            "Patient-level target semantics, measurement timing, and referral pathway are not "
            "verifiable from the distributed columns."
        ),
    },
    {
        "limitation_id": "L-03-ZERO-CODING",
        "statement": (
            "Zero-as-missing semantics for cholesterol and resting blood pressure rest partly on "
            "secondary documentation; the audit reports both literal and zero-unavailable counts "
            "without changing source values."
        ),
    },
    {
        "limitation_id": "L-04-UNIT-HEURISTIC",
        "statement": (
            "Unit diagnostics are range heuristics that can detect implausible scale but cannot "
            "prove unit identity or assay comparability."
        ),
    },
    {
        "limitation_id": "L-05-COARSE-PROFILES",
        "statement": (
            "Exact-profile overlap on five (and eleven/thirteen) conventional fields is coarse; zero "
            "matches and many matches are both compatible with either independence or recirculation."
        ),
    },
    {
        "limitation_id": "L-06-REPRESENTATION",
        "statement": (
            "Processed files are source representations, not additional patients; this audit does not "
            "resolve representation alignment or provenance beyond the manifest hash record."
        ),
    },
    {
        "limitation_id": "L-07-PRIVACY-SCANNER",
        "statement": (
            "The strict aggregate schema is the primary privacy control and pattern scanners are "
            "defense in depth; human maintainer inspection is still required before sharing any report."
        ),
    },
    {
        "limitation_id": "L-08-NO-SYNTHETIC-PROMOTION",
        "statement": (
            "Runs against synthetic fixtures are software tests only and are labelled as such; they "
            "are never evidence about the real cohorts."
        ),
    },
)


# ---------------------------------------------------------------------------
# Pure diagnostic primitives (unit-testable without file access)
# ---------------------------------------------------------------------------


def _as_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except ValueError:
        return None


def _original_target_code(row: Mapping[str, Any]) -> int | None:
    number = _as_number(row.get(TARGET_COLUMN))
    if number is None or not number.is_integer():
        return None
    return int(number)


def _is_unclassified_target(row: Mapping[str, Any]) -> bool:
    code = _original_target_code(row)
    return code is None or not 0 <= code <= 4


def _label_set_relation(comparator_labels: Sequence[str], reference_labels: Sequence[str]) -> str:
    """Describe how a comparator's observed original target labels relate to the reference set."""
    comp = set(comparator_labels)
    ref = set(reference_labels)
    if not comp and not ref:
        return "BOTH_CODE_SETS_EMPTY"
    if comp == ref:
        return "IDENTICAL"
    if comp and ref and comp < ref:
        return "SUBSET_OF_REFERENCE"
    if comp and ref and comp > ref:
        return "SUPERSET_OF_REFERENCE"
    if comp and ref and not (comp & ref):
        return "DISJOINT"
    return "PARTIALLY_OVERLAPPING"


def _age_band(value: float) -> str:
    if value < 1:
        return "lt_1"
    if value <= 44:
        return "1_to_44"
    if value <= 59:
        return "45_to_59"
    if value <= 74:
        return "60_to_74"
    if value <= 89:
        return "75_to_89"
    return "90_plus"


def _trestbps_band(value: float) -> str:
    if value < 1:
        return "lt_1"
    if value <= 89:
        return "1_to_89"
    if value <= 119:
        return "90_to_119"
    if value <= 139:
        return "120_to_139"
    if value <= 159:
        return "140_to_159"
    if value <= 179:
        return "160_to_179"
    return "180_plus"


_NUMERIC_FIELD_SPECS: Mapping[str, dict[str, Any]] = {
    "age": {
        "documented_unit": "years",
        "plausible_min_inclusive": 1.0,
        "plausible_max_inclusive": 120.0,
        "band_labels": AGE_BAND_LABELS,
        "band_function": _age_band,
        "consistent_verdict": "CONSISTENT_WITH_DOCUMENTED_YEARS_HEURISTIC",
    },
    "trestbps": {
        "documented_unit": "mm Hg",
        "plausible_min_inclusive": 1.0,
        "plausible_max_inclusive": 300.0,
        "band_labels": TRESTBPS_BAND_LABELS,
        "band_function": _trestbps_band,
        "consistent_verdict": "CONSISTENT_WITH_DOCUMENTED_MMHG_HEURISTIC",
    },
}

OVERLAP_FIELD_SETS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("PREDECLARED_FIVE_FIELD_CORE_PANEL", PREDECLARED_FIVE_FIELDS),
    ("CONVENTIONAL_11_PREDICTOR_NO_CA_THAL", tuple(SHARED_11_PREDICTOR_NO_CA_THAL)),
    ("CONVENTIONAL_13_PREDICTOR", tuple(SHARED_13_PREDICTOR_COLUMNS)),
)


def build_target_code_compatibility(
    rows: Sequence[Mapping[str, Any]],
    *,
    cohort: str,
    reference_label_counts: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    """Summarize a cohort's ORIGINAL target codes without translating or rewriting any label."""
    label_counts: dict[str, int] = {code: 0 for code in TARGET_LABEL_CODES}
    missing_target = 0
    outside_domain = 0

    for row in rows:
        raw_value = row.get(TARGET_COLUMN)
        code = _original_target_code(row)
        if raw_value is None:
            missing_target += 1
        elif code is None or not 0 <= code <= 4:
            outside_domain += 1
        else:
            label_counts[str(code)] += 1

    observed_labels = [code for code in TARGET_LABEL_CODES if label_counts[code] > 0]
    absent = label_counts["0"]
    present = sum(label_counts[code] for code in TARGET_LABEL_CODES[1:])
    unclassified = missing_target + outside_domain

    if len(rows) != absent + present + unclassified:
        raise RuntimeError("STOP: Target-code partition invariant violated.")

    is_reference = cohort == REFERENCE_COHORT
    if reference_label_counts is None:
        reference_labels = observed_labels
    else:
        reference_labels = [
            code for code in TARGET_LABEL_CODES if int(reference_label_counts.get(code, 0)) > 0
        ]

    relation = "REFERENCE_COHORT" if is_reference else _label_set_relation(observed_labels, reference_labels)
    only_in_comparator = sorted(set(observed_labels) - set(reference_labels), key=int)
    only_in_reference = sorted(set(reference_labels) - set(observed_labels), key=int)

    degenerate = absent == 0 or present == 0
    if outside_domain > 0:
        status = "BLOCKED_UNDOCUMENTED_TARGET_CODE"
    elif degenerate and is_reference:
        status = "BLOCKED_DEGENERATE_SINGLE_CLASS_TARGET_IN_REFERENCE_COHORT"
    elif degenerate:
        status = "BLOCKED_DEGENERATE_SINGLE_CLASS_TARGET_IN_COMPARATOR"
    elif is_reference:
        status = "REFERENCE_COHORT_ORIGINAL_LABEL_BASELINE"
    elif relation == "IDENTICAL":
        status = "DERIVED_BINARY_RULE_WELL_DEFINED_CODEBOOK_IDENTICAL_TO_REFERENCE"
    else:
        status = "DERIVED_BINARY_RULE_WELL_DEFINED_CODEBOOK_DIFFERENCE_REQUIRES_REVIEW"

    pre_binarized = bool(observed_labels) and set(observed_labels) <= {"0", "1"}

    return {
        "target_column": TARGET_COLUMN,
        "cohort": cohort,
        "is_reference_cohort": is_reference,
        "record_count": len(rows),
        "original_target_label_counts": label_counts,
        "observed_original_target_labels": observed_labels,
        "missing_target_value_count": missing_target,
        "target_codes_outside_documented_domain_count": outside_domain,
        "unclassified_target_record_count": unclassified,
        "uses_pre_binarized_0_1_coding": pre_binarized,
        "derived_binary_counts": {
            "original_label_0_absent": absent,
            "original_labels_1_to_4_present": present,
        },
        "derived_binary_rule": (
            "IN_MEMORY_STRATIFICATION_ONLY: original label 0 => absent; original labels 1-4 => present. "
            "Source labels are retained and never rewritten."
        ),
        "documented_source_target_rule": UCI_45_TARGET_RULE_TEXT,
        "reference_cohort": REFERENCE_COHORT,
        "reference_observed_original_target_labels": [
            code for code in TARGET_LABEL_CODES if code in set(reference_labels)
        ],
        "observed_target_label_set_relation": relation,
        "target_labels_only_in_comparator": only_in_comparator,
        "target_labels_only_in_reference": only_in_reference,
        "compatibility_status": status,
        "semantic_equivalence_status": "UNVERIFIED_PENDING_H01_AND_GATE_PT",
        "patient_level_target_semantics_verified": False,
        "downstream_comparison_authorized": False,
        "evidence_status": EVIDENCE_VERIFIED,
    }


def _summarize_stratum(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    record_count = len(rows)
    per_field_observed = {
        field: sum(1 for row in rows if row.get(field) is not None)
        for field in PREDECLARED_FIVE_FIELDS
    }
    trestbps_zero = sum(1 for row in rows if row.get("trestbps") == 0 and row.get("trestbps") is not None)
    all_literal = sum(
        1
        for row in rows
        if all(row.get(field) is not None for field in PREDECLARED_FIVE_FIELDS)
    )
    all_zero_rule = sum(
        1
        for row in rows
        if all(row.get(field) is not None for field in PREDECLARED_FIVE_FIELDS)
        and row.get("trestbps") != 0
    )
    missing_any = sum(
        1
        for row in rows
        if any(row.get(field) is None for field in PREDECLARED_FIVE_FIELDS)
    )

    if not (0 <= all_zero_rule <= all_literal <= record_count):
        raise RuntimeError("STOP: Joint availability invariant violated.")
    if all_literal + missing_any != record_count:
        raise RuntimeError("STOP: Joint missingness partition invariant violated.")
    for field, observed in per_field_observed.items():
        if not 0 <= observed <= record_count:
            raise RuntimeError(f"STOP: Availability count out of range for field '{field}'.")

    return {
        "record_count": record_count,
        "per_field_observed_count": per_field_observed,
        "trestbps_zero_count": trestbps_zero,
        "all_five_fields_observed_literal": all_literal,
        "all_five_fields_observed_zero_trestbps_unavailable": all_zero_rule,
        "joint_availability_lost_under_zero_rule": all_literal - all_zero_rule,
        "at_least_one_of_five_fields_missing_literal": missing_any,
    }


def build_class_conditional_availability(
    rows: Sequence[Mapping[str, Any]],
    *,
    cohort: str,
) -> dict[str, Any]:
    """Class-conditional availability of the five predeclared fields, retaining original labels.

    Strata are the ORIGINAL target labels 0-4 plus an unclassified stratum, so the
    strata partition the cohort exactly. Counts are availability counts, not model
    eligibility or effective sample size.
    """
    strata_defs: list[tuple[str, Sequence[Mapping[str, Any]]]] = []
    for code in TARGET_LABEL_CODES:
        strata_defs.append(
            (
                f"original_target_label_{code}",
                [row for row in rows if _original_target_code(row) == int(code)],
            )
        )
    strata_defs.append(
        (
            "original_target_label_unclassified",
            [row for row in rows if _is_unclassified_target(row)],
        )
    )
    strata_defs.append(("all_original_target_labels", list(rows)))

    strata = {key: _summarize_stratum(value) for key, value in strata_defs}
    if set(strata) != set(CLASS_STRATA_KEYS):
        raise RuntimeError("STOP: Unexpected class-availability strata keys.")

    classified_total = sum(
        strata[f"original_target_label_{code}"]["record_count"] for code in TARGET_LABEL_CODES
    )
    unclassified_total = strata["original_target_label_unclassified"]["record_count"]
    if classified_total + unclassified_total != len(rows):
        raise RuntimeError("STOP: Class-conditional strata do not partition the cohort.")

    cross_check = descriptive_panel_counts(rows, PREDECLARED_FIVE_FIELDS)
    all_stratum = strata["all_original_target_labels"]
    if (
        cross_check["literal_source_coding_jointly_present"]
        != all_stratum["all_five_fields_observed_literal"]
        or cross_check["hypothetical_zero_unavailable_jointly_present"]
        != all_stratum["all_five_fields_observed_zero_trestbps_unavailable"]
    ):
        raise RuntimeError(
            "STOP: Class-conditional joint counts disagree with the existing availability module."
        )

    return {
        "cohort": cohort,
        "fields": list(PREDECLARED_FIVE_FIELDS),
        "zero_unavailable_rule_applies_only_to": sorted(ZERO_UNAVAILABLE_SENSITIVITY_FIELDS),
        "zero_rule_is_descriptive_sensitivity_only": True,
        "source_values_modified": False,
        "strata": strata,
        "cross_checked_with_existing_availability_module": True,
        "evidence_status": EVIDENCE_VERIFIED,
    }


def build_categorical_code_compatibility(
    rows: Sequence[Mapping[str, Any]],
    *,
    cohort: str,
) -> dict[str, Any]:
    """Report observed code sets and documented-domain conformance without translating codes."""
    fields: dict[str, dict[str, Any]] = {}
    for field in CATEGORICAL_FIVE_SUBSET:
        documented = sorted(int(value) for value in UCI_45_PROCESSED_DOMAIN_RULES[field])
        counts: Counter[str] = Counter({code: 0 for code in CATEGORICAL_CODE_KEYS})
        missing = 0
        outside_domain = 0
        for row in rows:
            value = _as_number(row.get(field))
            if value is None:
                missing += 1
            elif value.is_integer() and int(value) in documented:
                counts[str(int(value))] += 1
            else:
                outside_domain += 1

        observed_codes = [code for code in CATEGORICAL_CODE_KEYS if counts[code] > 0]
        if sum(counts.values()) + missing + outside_domain != len(rows):
            raise RuntimeError(f"STOP: Categorical code partition invariant violated for '{field}'.")

        fields[field] = {
            "documented_domain_codes": [str(value) for value in documented],
            "observed_codes": observed_codes,
            "observed_code_counts": {code: int(counts[code]) for code in CATEGORICAL_CODE_KEYS},
            "missing_count": missing,
            "codes_outside_documented_domain_count": outside_domain,
            "documented_domain_conformance": "CONFORMING" if outside_domain == 0 else "NONCONFORMING",
        }

    return {
        "cohort": cohort,
        "fields": fields,
        "codes_are_not_translated_or_recoded": True,
        "documented_domain_source": (
            "UCI-45 conventional attribute codebook as encoded in the existing audit domain rules "
            "(sex 0/1, cp 1-4, restecg 0-2); absence of an observed code is not evidence of a "
            "different codebook."
        ),
        "evidence_status": EVIDENCE_VERIFIED,
    }


def build_measurement_unit_diagnostics(
    rows: Sequence[Mapping[str, Any]],
    *,
    cohort: str,
) -> dict[str, Any]:
    """Heuristic range diagnostics for the numeric predeclared fields; never a unit proof."""
    fields: dict[str, dict[str, Any]] = {}
    for field in NUMERIC_FIVE_SUBSET:
        spec = _NUMERIC_FIELD_SPECS[field]
        band_labels: tuple[str, ...] = spec["band_labels"]
        band_counts: Counter[str] = Counter({label: 0 for label in band_labels})
        band_function = spec["band_function"]
        missing = 0
        zero_or_negative = 0
        implausible = 0
        observed_values: list[float] = []

        for row in rows:
            value = _as_number(row.get(field))
            if value is None:
                missing += 1
                continue
            observed_values.append(value)
            band_counts[band_function(value)] += 1
            if value <= 0:
                zero_or_negative += 1
            if value < spec["plausible_min_inclusive"] or value > spec["plausible_max_inclusive"]:
                implausible += 1

        if sum(band_counts.values()) + missing != len(rows):
            raise RuntimeError(f"STOP: Unit band partition invariant violated for '{field}'.")

        if not observed_values:
            verdict = "NOT_ASSESSABLE_NO_OBSERVED_VALUES"
        elif field == "trestbps" and zero_or_negative > 0:
            verdict = "IMPLAUSIBLE_ZERO_OR_NEGATIVE_PRESENT_REQUIRES_SOURCE_CODING_REVIEW"
        elif field == "trestbps" and all(value < 30 for value in observed_values):
            verdict = "SUSPECT_UNIT_SCALE_MISMATCH_REQUIRES_SOURCE_REVIEW"
        elif implausible > 0:
            verdict = "IMPLAUSIBLE_VALUE_PRESENT_REQUIRES_SOURCE_REVIEW"
        else:
            verdict = str(spec["consistent_verdict"])

        fields[field] = {
            "documented_unit": spec["documented_unit"],
            "plausible_range_inclusive": (
                f"{int(spec['plausible_min_inclusive'])}-{int(spec['plausible_max_inclusive'])}"
            ),
            "band_labels": list(band_labels),
            "band_counts": {label: int(band_counts[label]) for label in band_labels},
            "observed_value_count": len(observed_values),
            "missing_count": missing,
            "zero_or_negative_count": zero_or_negative,
            "implausible_value_count": implausible,
            "unit_verdict": verdict,
            "unit_verdict_basis": "HEURISTIC_RANGE_CHECK_NOT_PROOF_OF_UNIT_IDENTITY",
        }

    return {
        "cohort": cohort,
        "fields": fields,
        "documented_unit_source": UNIT_DOCUMENTED_SOURCE,
        "unit_identity_provable_from_file_content": False,
        "evidence_status": EVIDENCE_VERIFIED,
    }


def _unit_comparability_status(reference_verdict: str, comparator_verdict: str) -> str:
    if reference_verdict.startswith("CONSISTENT") and comparator_verdict.startswith("CONSISTENT"):
        return "BOTH_CONSISTENT_WITH_DOCUMENTED_UNIT_HEURISTIC"
    if "NOT_ASSESSABLE" in (reference_verdict, comparator_verdict):
        return "NOT_ASSESSABLE"
    return "REQUIRES_HUMAN_SOURCE_UNIT_REVIEW"


def _five_field_joint_availability(strata: Mapping[str, Any]) -> dict[str, dict[str, int]]:
    """Extract joint five-field availability counts for a cohort from its class strata."""
    all_stratum = strata["all_original_target_labels"]
    label_0 = strata["original_target_label_0"]

    def _sum_present(field_name: str) -> int:
        return sum(
            int(strata[f"original_target_label_{code}"][field_name])
            for code in TARGET_LABEL_CODES[1:]
        )

    return {
        "all_records": {
            "literal": int(all_stratum["all_five_fields_observed_literal"]),
            "zero_trestbps_unavailable": int(
                all_stratum["all_five_fields_observed_zero_trestbps_unavailable"]
            ),
        },
        "original_label_0": {
            "literal": int(label_0["all_five_fields_observed_literal"]),
            "zero_trestbps_unavailable": int(
                label_0["all_five_fields_observed_zero_trestbps_unavailable"]
            ),
        },
        "original_labels_1_to_4": {
            "literal": _sum_present("all_five_fields_observed_literal"),
            "zero_trestbps_unavailable": _sum_present(
                "all_five_fields_observed_zero_trestbps_unavailable"
            ),
        },
    }


def build_cross_site_compatibility_summary(
    cohort_diagnostics: Mapping[str, Mapping[str, Any]],
    *,
    near_duplicate_counts: Mapping[str, int],
) -> list[dict[str, Any]]:
    """Per-comparator categorical/unit compatibility summary; explicitly non-statistical."""
    summary: list[dict[str, Any]] = []
    reference = cohort_diagnostics[REFERENCE_COHORT]

    for comparator in COMPARATOR_COHORTS:
        other = cohort_diagnostics[comparator]
        target = other["target_code_compatibility"]

        categorical: dict[str, dict[str, Any]] = {}
        for field in CATEGORICAL_FIVE_SUBSET:
            reference_field = reference["categorical_code_compatibility"]["fields"][field]
            comparator_field = other["categorical_code_compatibility"]["fields"][field]
            reference_codes = list(reference_field["observed_codes"])
            comparator_codes = list(comparator_field["observed_codes"])
            relation = _label_set_relation(comparator_codes, reference_codes)
            if (
                reference_field["documented_domain_conformance"] != "CONFORMING"
                or comparator_field["documented_domain_conformance"] != "CONFORMING"
            ):
                status = "BLOCKED_UNDOCUMENTED_CODE_REQUIRES_SOURCE_REVIEW"
            elif relation == "IDENTICAL":
                status = "IDENTICAL_OBSERVED_CODE_SET"
            elif relation == "SUBSET_OF_REFERENCE":
                status = "OBSERVED_CODE_SET_SUBSET_OF_REFERENCE"
            elif relation == "SUPERSET_OF_REFERENCE":
                status = "OBSERVED_CODE_SET_SUPERSET_OF_REFERENCE"
            elif relation == "DISJOINT":
                status = "DISJOINT_OBSERVED_CODE_SETS_REQUIRES_REVIEW"
            else:
                status = "DIFFERING_OBSERVED_CODE_SETS_REQUIRES_REVIEW"
            categorical[field] = {
                "reference_observed_codes": reference_codes,
                "comparator_observed_codes": comparator_codes,
                "codes_absent_in_reference": sorted(set(comparator_codes) - set(reference_codes), key=int),
                "codes_absent_in_comparator": sorted(set(reference_codes) - set(comparator_codes), key=int),
                "observed_code_set_relation": relation,
                "compatibility_status": status,
            }

        units: dict[str, dict[str, Any]] = {}
        for field in NUMERIC_FIVE_SUBSET:
            reference_verdict = reference["measurement_unit_diagnostics"]["fields"][field]["unit_verdict"]
            comparator_verdict = other["measurement_unit_diagnostics"]["fields"][field]["unit_verdict"]
            units[field] = {
                "reference_unit_verdict": reference_verdict,
                "comparator_unit_verdict": comparator_verdict,
                "unit_comparability_status": _unit_comparability_status(
                    reference_verdict, comparator_verdict
                ),
                "unit_identity_status": "NOT_PROVABLE_FROM_FILE_CONTENT",
            }

        categorical_blocked = any(
            entry["compatibility_status"].startswith("BLOCKED") for entry in categorical.values()
        )
        units_need_review = any(
            entry["unit_comparability_status"] not in ("BOTH_CONSISTENT_WITH_DOCUMENTED_UNIT_HEURISTIC",)
            for entry in units.values()
        )
        if target["compatibility_status"].startswith("BLOCKED") or categorical_blocked:
            status = "BLOCKED_BY_COHORT_LEVEL_FINDING"
        elif units_need_review:
            status = "DESCRIPTIVE_COMPATIBILITY_ASSESSED_UNIT_REVIEW_REQUIRED"
        else:
            status = "DESCRIPTIVE_COMPATIBILITY_ASSESSED_WITH_OPEN_BLOCKERS"

        summary.append(
            {
                "comparator_cohort": comparator,
                "reference_cohort": REFERENCE_COHORT,
                "target_code_compatibility_status": target["compatibility_status"],
                "observed_target_label_set_relation": target["observed_target_label_set_relation"],
                "categorical_code_compatibility": categorical,
                "measurement_unit_comparability": units,
                "five_field_joint_availability": {
                    "reference_cohort": _five_field_joint_availability(
                        reference["class_conditional_field_availability"]["strata"]
                    ),
                    "comparator_cohort": _five_field_joint_availability(
                        other["class_conditional_field_availability"]["strata"]
                    ),
                    "interpretation": (
                        "AVAILABILITY_COUNTS_ARE_NOT_EFFECTIVE_SAMPLE_SIZE_OR_MODEL_ELIGIBILITY"
                    ),
                },
                "near_duplicate_candidate_cross_pairs_11_feature_rule": int(
                    near_duplicate_counts.get(comparator, 0)
                ),
                "cross_site_compatibility_status": status,
                "statistical_comparison_performed": False,
                "model_or_performance_comparison_performed": False,
                "clinical_or_transportability_claim_made": False,
                "evidence_status": EVIDENCE_VERIFIED,
            }
        )
    return summary


def build_exact_profile_overlap_checks(
    cohort_rows: Mapping[str, Sequence[Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    """Aggregate-only exact-profile overlap with duplicate multiplicity for each field set."""
    reference_rows = cohort_rows[REFERENCE_COHORT]
    checks: list[dict[str, Any]] = []
    for comparator in COMPARATOR_COHORTS:
        comparator_rows = cohort_rows[comparator]
        for field_set_label, fields in OVERLAP_FIELD_SETS:
            overlap = compute_exact_profile_multiset_overlap(
                reference_rows, comparator_rows, fields
            )
            checks.append(
                {
                    "comparison_id": f"cleveland_vs_{comparator}:{field_set_label}",
                    "reference_cohort": REFERENCE_COHORT,
                    "comparator_cohort": comparator,
                    "field_set_label": field_set_label,
                    "fields_compared": list(fields),
                    "fields_compared_count": len(fields),
                    "reference_row_count": len(reference_rows),
                    "comparator_row_count": len(comparator_rows),
                    "distinct_matching_profiles": int(overlap["distinct_matching_profiles"]),
                    "matched_rows_in_reference": int(overlap["matched_rows_in_a"]),
                    "matched_rows_in_comparator": int(overlap["matched_rows_in_b"]),
                    "record_pairs_consistent_with_profile_match": int(
                        overlap["record_pairs_consistent_with_profile_match"]
                    ),
                    "max_profile_multiplicity_in_reference": int(
                        overlap["max_profile_multiplicity_in_a"]
                    ),
                    "max_profile_multiplicity_in_comparator": int(
                        overlap["max_profile_multiplicity_in_b"]
                    ),
                    "multiplicity_rule": str(overlap["multiplicity_rule"]),
                    "profile_values_emitted": False,
                    "identity_inference_permitted": False,
                    "evidence_status": EVIDENCE_VERIFIED,
                }
            )
    return checks


def _governance_context(auth_manifest: Mapping[str, Any]) -> dict[str, Any]:
    da_a2 = auth_manifest["datasets"]["DA-A2"]
    return {
        "governance_decision_id": auth_manifest.get("governance_decision_id"),
        "workflow_status": auth_manifest.get("workflow_status"),
        "gate_pt_status": auth_manifest.get("gate_pt_status"),
        "supervisor_review_status": (
            auth_manifest.get("supervisor_review_status") or "NOT_RECORDED_IN_LOCAL_MANIFEST"
        ),
        "supervisor_approval_claimed": auth_manifest.get("supervisor_approval_claimed"),
        "model_fitting_authorized": auth_manifest.get("model_fitting_authorized"),
        "audited_dataset_id": "DA-A2",
        "dataset_authorization_status": da_a2.get("authorization_status"),
        "authorized_by": da_a2.get("authorized_by"),
        "authorized_date": da_a2.get("authorized_date"),
        "responsible_acquirer": da_a2.get("responsible_acquirer"),
        "audit_reviewer": da_a2.get("audit_reviewer"),
        "environment": da_a2.get("environment"),
        "d046_scope_determination": "WITHIN_D046_READ_ONLY_AUDIT_SCOPE",
        "d046_scope_basis": (
            "D-046 authorizes local read-only suitability auditing of the named DA-A2 files with no "
            "model fitting, feature selection, tuning, performance evaluation, calibration, or "
            "explanation. Aggregate compatibility, availability, and overlap diagnostics computed "
            "from those files stay inside that permission."
        ),
        "downstream_comparison_within_this_authorization": False,
        "additional_authorization_required_for_downstream_comparison": True,
        "additional_authorization_required": (
            "A model or outcome comparison across Cleveland and Hungary/VA requires a separate "
            "explicitly scoped governance decision plus a frozen Gate PT protocol with supervisor "
            "P-3 sign-off; D-047 is Cleveland-only and cannot be extended by inference."
        ),
    }


def build_feasibility_report(
    *,
    cohort_rows: Mapping[str, Sequence[Mapping[str, Any]]],
    source_filenames: Mapping[str, str],
    governance_context: Mapping[str, Any],
    byte_identity_snapshots: Sequence[Mapping[str, Any]],
    is_synthetic_fixture_run: bool,
) -> dict[str, Any]:
    """Assemble the aggregate-only structured feasibility report from already-parsed rows."""
    missing_cohorts = [cohort for cohort in AUDITED_COHORTS if cohort not in cohort_rows]
    if missing_cohorts:
        raise ValueError(f"Missing parsed cohort(s): {missing_cohorts}")

    reference_target = build_target_code_compatibility(
        cohort_rows[REFERENCE_COHORT], cohort=REFERENCE_COHORT
    )
    reference_label_counts = reference_target["original_target_label_counts"]

    cohort_diagnostics: dict[str, dict[str, Any]] = {}
    for cohort in AUDITED_COHORTS:
        rows = cohort_rows[cohort]
        cohort_diagnostics[cohort] = {
            "cohort": cohort,
            "source_filename": source_filenames[cohort],
            "dataset_id": "DA-A2",
            "row_count": len(rows),
            "target_code_compatibility": build_target_code_compatibility(
                rows, cohort=cohort, reference_label_counts=reference_label_counts
            ),
            "class_conditional_field_availability": build_class_conditional_availability(
                rows, cohort=cohort
            ),
            "categorical_code_compatibility": build_categorical_code_compatibility(
                rows, cohort=cohort
            ),
            "measurement_unit_diagnostics": build_measurement_unit_diagnostics(rows, cohort=cohort),
            "parsed_from_conventional_14_columns_only": True,
            "evidence_status": EVIDENCE_VERIFIED,
        }

    near_duplicate_counts: dict[str, int] = {}
    for comparator in COMPARATOR_COHORTS:
        cross_dups = compute_cross_cohort_duplicates(
            {
                f"DA-A2:{REFERENCE_COHORT}": list(cohort_rows[REFERENCE_COHORT]),
                f"DA-A2:{comparator}": list(cohort_rows[comparator]),
            }
        )
        pair_summary = cross_dups["pairwise_cross_cohort_summary"][0]
        near_duplicate_counts[comparator] = int(
            pair_summary["observed_near_duplicate_candidate_cross_pairs"]
        )

    cross_site_summary = build_cross_site_compatibility_summary(
        cohort_diagnostics, near_duplicate_counts=near_duplicate_counts
    )
    overlap_checks = build_exact_profile_overlap_checks(cohort_rows)

    blocking_cohort_names = [
        entry["comparator_cohort"]
        for entry in cross_site_summary
        if entry["target_code_compatibility_status"].startswith("BLOCKED")
        or any(
            code_entry["compatibility_status"].startswith("BLOCKED")
            for code_entry in entry["categorical_code_compatibility"].values()
        )
    ]

    overall_status = (
        "DESCRIPTIVE_AUDIT_INCOMPLETE_COHORT_BLOCKING_FINDINGS_PRESENT"
        if blocking_cohort_names
        else "DESCRIPTIVE_AUDIT_COMPLETE_DOWNSTREAM_COMPARISON_BLOCKED"
    )

    return {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "report_type": REPORT_TYPE,
        "status_label": STATUS_LABEL,
        "milestone": "PROPOSED_FOCUSED_AUDIT_NOT_AN_ACCEPTED_MILESTONE",
        "execution_mode": (
            "SYNTHETIC_FIXTURE_TEST" if is_synthetic_fixture_run else "AUTHORIZED_READ_ONLY_LOCAL_AUDIT"
        ),
        "is_synthetic_fixture_run": is_synthetic_fixture_run,
        "synthetic_disclaimer": (
            "SYNTHETIC_SOFTWARE_TEST_FIXTURES_ONLY_NOT_MEDICAL_EVIDENCE"
            if is_synthetic_fixture_run
            else "REAL_LOCAL_AGGREGATE_READ_ONLY_AUDIT_NOT_MODEL_OR_CLINICAL_EVIDENCE"
        ),
        "governance_and_authorization": dict(governance_context),
        "safety_and_scope_certification": {
            "model_fitting_performed": False,
            "feature_selection_performed": False,
            "hyperparameter_tuning_performed": False,
            "performance_evaluation_performed": False,
            "calibration_performed": False,
            "shap_or_lime_computed": False,
            "pooling_or_dataset_concatenation_performed": False,
            "statistical_test_performed": False,
            "patient_identity_inferred": False,
            "source_labels_translated": False,
            "source_files_modified": False,
            "zeros_or_missing_values_imputed": False,
            "raw_cleveland_parsed": False,
            "raw_46_or_76_attribute_files_parsed": False,
            "patient_level_rows_emitted": 0,
            "supervisor_approval_claimed": False,
            "gate_pt_bypassed": False,
            "evidence_status": EVIDENCE_VERIFIED,
        },
        "scope_and_evidence_boundary": {
            "reference_cohort": REFERENCE_COHORT,
            "comparator_cohorts": list(COMPARATOR_COHORTS),
            "audited_cohorts": list(AUDITED_COHORTS),
            "cohorts_not_assessed": dict(COHORTS_NOT_ASSESSED),
            "predeclared_fields": list(PREDECLARED_FIVE_FIELDS),
            "categorical_fields_assessed": list(CATEGORICAL_FIVE_SUBSET),
            "numeric_fields_assessed": list(NUMERIC_FIVE_SUBSET),
            "overlap_field_sets": [label for label, _ in OVERLAP_FIELD_SETS],
            "parsed_source_files": [source_filenames[cohort] for cohort in AUDITED_COHORTS],
            "proven_independence_claim_permitted": False,
            "raw_cleveland_quarantine": (
                "The source-warned raw cleveland.data is never opened by this audit; only its "
                "provenance hash and byte size are verified."
            ),
            "new_evidence_generated": (
                "SYNTHETIC_TEST_FIXTURES_ONLY"
                if is_synthetic_fixture_run
                else "LOCAL_AGGREGATE_ONLY_PENDING_MAINTAINER_EXECUTION_AND_PRIVACY_REVIEW"
            ),
            "scientific_claim_made": False,
            "evidence_status": EVIDENCE_VERIFIED,
        },
        "cohorts": cohort_diagnostics,
        "cross_site_compatibility_summary": cross_site_summary,
        "exact_profile_overlap_checks": overlap_checks,
        "identity_and_independence_warnings": [dict(item) for item in IDENTITY_AND_INDEPENDENCE_WARNINGS],
        "blockers": [dict(item) for item in AUDIT_BLOCKERS],
        "evidence_limitations": [dict(item) for item in EVIDENCE_LIMITATIONS],
        "input_integrity_and_privacy": {
            "git_ignore_verified": True,
            "byte_identity_guard_file_count": len(byte_identity_snapshots),
            "byte_identity_snapshots": [dict(snapshot) for snapshot in byte_identity_snapshots],
            "raw_cleveland_parsed": False,
            "privacy_controls": (
                "STRICT_ALLOWLISTED_AGGREGATE_SCHEMA_AS_PRIMARY_CONTROL_PLUS_SECONDARY_ROW_PATTERN_"
                "AND_FINGERPRINT_SCANNER_HUMAN_REVIEW_REQUIRED_BEFORE_SHARING"
            ),
            "evidence_status": EVIDENCE_VERIFIED,
        },
        "feasibility_summary": {
            "reference_cohort": REFERENCE_COHORT,
            "comparator_cohorts": list(COMPARATOR_COHORTS),
            "predeclared_fields": list(PREDECLARED_FIVE_FIELDS),
            "target_code_compatibility_status_by_comparator": {
                comparator: cohort_diagnostics[comparator]["target_code_compatibility"][
                    "compatibility_status"
                ]
                for comparator in COMPARATOR_COHORTS
            },
            "cohorts_with_blocking_findings": blocking_cohort_names,
            "overall_status": overall_status,
            "downstream_comparison_authorization_status": (
                "NOT_AUTHORIZED_GATE_PT_CLOSED_D047_SCOPE_CLEVELAND_ONLY"
            ),
            "blocker_count": len(AUDIT_BLOCKERS),
            "evidence_limitation_count": len(EVIDENCE_LIMITATIONS),
            "human_scientific_review_required_before_any_downstream_comparison": True,
            "evidence_status": EVIDENCE_VERIFIED,
        },
    }


# ---------------------------------------------------------------------------
# Strict aggregate-only schema validation (primary privacy control)
# ---------------------------------------------------------------------------


def _assert_str_list(value: Any, *, context: str) -> None:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"Strict cross-site report schema violation at '{context}': expected list of strings.")


def _assert_int_map(value: Any, expected_keys: Sequence[str], *, context: str) -> None:
    assert_exact_keys(value, set(expected_keys), context=context)
    for key in expected_keys:
        assert_int_not_bool(value[key], context=f"{context}.{key}")


def _validate_target_code_compatibility(payload: Any, *, context: str, cohort: str) -> None:
    assert_exact_keys(
        payload,
        {
            "target_column",
            "cohort",
            "is_reference_cohort",
            "record_count",
            "original_target_label_counts",
            "observed_original_target_labels",
            "missing_target_value_count",
            "target_codes_outside_documented_domain_count",
            "unclassified_target_record_count",
            "uses_pre_binarized_0_1_coding",
            "derived_binary_counts",
            "derived_binary_rule",
            "documented_source_target_rule",
            "reference_cohort",
            "reference_observed_original_target_labels",
            "observed_target_label_set_relation",
            "target_labels_only_in_comparator",
            "target_labels_only_in_reference",
            "compatibility_status",
            "semantic_equivalence_status",
            "patient_level_target_semantics_verified",
            "downstream_comparison_authorized",
            "evidence_status",
        },
        context=context,
    )
    if payload["target_column"] != TARGET_COLUMN:
        raise ValueError(f"Strict cross-site report schema violation at '{context}': unexpected target column.")
    if payload["cohort"] != cohort:
        raise ValueError(f"Strict cross-site report schema violation at '{context}': cohort mismatch.")
    for key in (
        "record_count",
        "missing_target_value_count",
        "target_codes_outside_documented_domain_count",
        "unclassified_target_record_count",
    ):
        assert_int_not_bool(payload[key], context=f"{context}.{key}")
    _assert_int_map(
        payload["original_target_label_counts"],
        TARGET_LABEL_CODES,
        context=f"{context}.original_target_label_counts",
    )
    _assert_int_map(
        payload["derived_binary_counts"],
        ("original_label_0_absent", "original_labels_1_to_4_present"),
        context=f"{context}.derived_binary_counts",
    )
    _assert_str_list(payload["observed_original_target_labels"], context=f"{context}.observed_original_target_labels")
    _assert_str_list(
        payload["reference_observed_original_target_labels"],
        context=f"{context}.reference_observed_original_target_labels",
    )
    _assert_str_list(
        payload["target_labels_only_in_comparator"], context=f"{context}.target_labels_only_in_comparator"
    )
    _assert_str_list(
        payload["target_labels_only_in_reference"], context=f"{context}.target_labels_only_in_reference"
    )
    if payload["patient_level_target_semantics_verified"] is not False:
        raise ValueError(f"Strict cross-site report schema violation at '{context}': patient-level semantics cannot be claimed.")
    if payload["downstream_comparison_authorized"] is not False:
        raise ValueError(f"Strict cross-site report schema violation at '{context}': comparison cannot be authorized here.")


def _validate_class_conditional_availability(payload: Any, *, context: str) -> None:
    assert_exact_keys(
        payload,
        {
            "cohort",
            "fields",
            "zero_unavailable_rule_applies_only_to",
            "zero_rule_is_descriptive_sensitivity_only",
            "source_values_modified",
            "strata",
            "cross_checked_with_existing_availability_module",
            "evidence_status",
        },
        context=context,
    )
    if list(payload["fields"]) != list(PREDECLARED_FIVE_FIELDS):
        raise ValueError(f"Strict cross-site report schema violation at '{context}': unexpected fields.")
    if payload["source_values_modified"] is not False:
        raise ValueError(f"Strict cross-site report schema violation at '{context}': source modification claimed.")
    assert_exact_keys(payload["strata"], set(CLASS_STRATA_KEYS), context=f"{context}.strata")
    for stratum_key in CLASS_STRATA_KEYS:
        stratum_ctx = f"{context}.strata.{stratum_key}"
        stratum = payload["strata"][stratum_key]
        assert_exact_keys(
            stratum,
            {
                "record_count",
                "per_field_observed_count",
                "trestbps_zero_count",
                "all_five_fields_observed_literal",
                "all_five_fields_observed_zero_trestbps_unavailable",
                "joint_availability_lost_under_zero_rule",
                "at_least_one_of_five_fields_missing_literal",
            },
            context=stratum_ctx,
        )
        for key in (
            "record_count",
            "trestbps_zero_count",
            "all_five_fields_observed_literal",
            "all_five_fields_observed_zero_trestbps_unavailable",
            "joint_availability_lost_under_zero_rule",
            "at_least_one_of_five_fields_missing_literal",
        ):
            assert_int_not_bool(stratum[key], context=f"{stratum_ctx}.{key}")
        _assert_int_map(
            stratum["per_field_observed_count"],
            PREDECLARED_FIVE_FIELDS,
            context=f"{stratum_ctx}.per_field_observed_count",
        )


def _validate_categorical_code_compatibility(payload: Any, *, context: str) -> None:
    assert_exact_keys(
        payload,
        {
            "cohort",
            "fields",
            "codes_are_not_translated_or_recoded",
            "documented_domain_source",
            "evidence_status",
        },
        context=context,
    )
    assert_exact_keys(payload["fields"], set(CATEGORICAL_FIVE_SUBSET), context=f"{context}.fields")
    for field in CATEGORICAL_FIVE_SUBSET:
        field_ctx = f"{context}.fields.{field}"
        field_payload = payload["fields"][field]
        assert_exact_keys(
            field_payload,
            {
                "documented_domain_codes",
                "observed_codes",
                "observed_code_counts",
                "missing_count",
                "codes_outside_documented_domain_count",
                "documented_domain_conformance",
            },
            context=field_ctx,
        )
        _assert_str_list(field_payload["documented_domain_codes"], context=f"{field_ctx}.documented_domain_codes")
        _assert_str_list(field_payload["observed_codes"], context=f"{field_ctx}.observed_codes")
        _assert_int_map(
            field_payload["observed_code_counts"], CATEGORICAL_CODE_KEYS, context=f"{field_ctx}.observed_code_counts"
        )
        assert_int_not_bool(field_payload["missing_count"], context=f"{field_ctx}.missing_count")
        assert_int_not_bool(
            field_payload["codes_outside_documented_domain_count"],
            context=f"{field_ctx}.codes_outside_documented_domain_count",
        )


def _validate_measurement_unit_diagnostics(payload: Any, *, context: str) -> None:
    assert_exact_keys(
        payload,
        {
            "cohort",
            "fields",
            "documented_unit_source",
            "unit_identity_provable_from_file_content",
            "evidence_status",
        },
        context=context,
    )
    if payload["unit_identity_provable_from_file_content"] is not False:
        raise ValueError(f"Strict cross-site report schema violation at '{context}': unit identity cannot be claimed.")
    assert_exact_keys(payload["fields"], set(NUMERIC_FIVE_SUBSET), context=f"{context}.fields")
    for field in NUMERIC_FIVE_SUBSET:
        field_ctx = f"{context}.fields.{field}"
        spec = _NUMERIC_FIELD_SPECS[field]
        field_payload = payload["fields"][field]
        assert_exact_keys(
            field_payload,
            {
                "documented_unit",
                "plausible_range_inclusive",
                "band_labels",
                "band_counts",
                "observed_value_count",
                "missing_count",
                "zero_or_negative_count",
                "implausible_value_count",
                "unit_verdict",
                "unit_verdict_basis",
            },
            context=field_ctx,
        )
        _assert_str_list(field_payload["band_labels"], context=f"{field_ctx}.band_labels")
        _assert_int_map(
            field_payload["band_counts"], tuple(spec["band_labels"]), context=f"{field_ctx}.band_counts"
        )
        for key in (
            "observed_value_count",
            "missing_count",
            "zero_or_negative_count",
            "implausible_value_count",
        ):
            assert_int_not_bool(field_payload[key], context=f"{field_ctx}.{key}")
        if field_payload["unit_verdict_basis"] != "HEURISTIC_RANGE_CHECK_NOT_PROOF_OF_UNIT_IDENTITY":
            raise ValueError(f"Strict cross-site report schema violation at '{field_ctx}': missing heuristic disclaimer.")


def validate_cross_site_report_schema(report: Mapping[str, Any]) -> None:
    """Enforce the strict allowlisted aggregate-only schema of this focused report family."""
    assert_exact_keys(
        report,
        {
            "report_schema_version",
            "report_type",
            "status_label",
            "milestone",
            "execution_mode",
            "is_synthetic_fixture_run",
            "synthetic_disclaimer",
            "governance_and_authorization",
            "safety_and_scope_certification",
            "scope_and_evidence_boundary",
            "cohorts",
            "cross_site_compatibility_summary",
            "exact_profile_overlap_checks",
            "identity_and_independence_warnings",
            "blockers",
            "evidence_limitations",
            "input_integrity_and_privacy",
            "feasibility_summary",
        },
        context="cross_site_report_root",
    )
    if not isinstance(report["is_synthetic_fixture_run"], bool):
        raise ValueError("Strict cross-site report schema violation: is_synthetic_fixture_run must be a boolean.")
    if report["report_type"] != REPORT_TYPE or report["status_label"] != STATUS_LABEL:
        raise ValueError("Strict cross-site report schema violation: report type or status label changed.")

    cert = report["safety_and_scope_certification"]
    assert_exact_keys(
        cert,
        {
            "model_fitting_performed",
            "feature_selection_performed",
            "hyperparameter_tuning_performed",
            "performance_evaluation_performed",
            "calibration_performed",
            "shap_or_lime_computed",
            "pooling_or_dataset_concatenation_performed",
            "statistical_test_performed",
            "patient_identity_inferred",
            "source_labels_translated",
            "source_files_modified",
            "zeros_or_missing_values_imputed",
            "raw_cleveland_parsed",
            "raw_46_or_76_attribute_files_parsed",
            "patient_level_rows_emitted",
            "supervisor_approval_claimed",
            "gate_pt_bypassed",
            "evidence_status",
        },
        context="safety_and_scope_certification",
    )
    for key, value in cert.items():
        if key == "patient_level_rows_emitted":
            assert_int_not_bool(value, context=f"safety_and_scope_certification.{key}")
            if value != 0:
                raise ValueError("Strict cross-site report schema violation: patient_level_rows_emitted must be 0.")
        elif key == "evidence_status":
            continue
        elif value is not False:
            raise ValueError(
                f"Strict cross-site report schema violation: '{key}' must be False in this read-only diagnostic."
            )

    gov = report["governance_and_authorization"]
    assert_exact_keys(
        gov,
        {
            "governance_decision_id",
            "workflow_status",
            "gate_pt_status",
            "supervisor_review_status",
            "supervisor_approval_claimed",
            "model_fitting_authorized",
            "audited_dataset_id",
            "dataset_authorization_status",
            "authorized_by",
            "authorized_date",
            "responsible_acquirer",
            "audit_reviewer",
            "environment",
            "d046_scope_determination",
            "d046_scope_basis",
            "downstream_comparison_within_this_authorization",
            "additional_authorization_required_for_downstream_comparison",
            "additional_authorization_required",
        },
        context="governance_and_authorization",
    )
    if gov["downstream_comparison_within_this_authorization"] is not False:
        raise ValueError("Strict cross-site report schema violation: downstream comparison cannot be in scope.")
    if gov["additional_authorization_required_for_downstream_comparison"] is not True:
        raise ValueError("Strict cross-site report schema violation: downstream authorization gate must remain explicit.")

    scope = report["scope_and_evidence_boundary"]
    assert_exact_keys(
        scope,
        {
            "reference_cohort",
            "comparator_cohorts",
            "audited_cohorts",
            "cohorts_not_assessed",
            "predeclared_fields",
            "categorical_fields_assessed",
            "numeric_fields_assessed",
            "overlap_field_sets",
            "parsed_source_files",
            "proven_independence_claim_permitted",
            "raw_cleveland_quarantine",
            "new_evidence_generated",
            "scientific_claim_made",
            "evidence_status",
        },
        context="scope_and_evidence_boundary",
    )
    if list(scope["comparator_cohorts"]) != list(COMPARATOR_COHORTS):
        raise ValueError("Strict cross-site report schema violation: comparator cohort set changed.")
    if list(scope["predeclared_fields"]) != list(PREDECLARED_FIVE_FIELDS):
        raise ValueError("Strict cross-site report schema violation: predeclared field set changed.")
    if scope["scientific_claim_made"] is not False:
        raise ValueError("Strict cross-site report schema violation: scientific claims are not permitted.")
    if scope["proven_independence_claim_permitted"] is not False:
        raise ValueError("Strict cross-site report schema violation: independence cannot be claimed.")

    cohorts = report["cohorts"]
    assert_exact_keys(cohorts, set(AUDITED_COHORTS), context="cohorts")
    for cohort in AUDITED_COHORTS:
        cohort_ctx = f"cohorts.{cohort}"
        payload = cohorts[cohort]
        assert_exact_keys(
            payload,
            {
                "cohort",
                "source_filename",
                "dataset_id",
                "row_count",
                "target_code_compatibility",
                "class_conditional_field_availability",
                "categorical_code_compatibility",
                "measurement_unit_diagnostics",
                "parsed_from_conventional_14_columns_only",
                "evidence_status",
            },
            context=cohort_ctx,
        )
        assert_int_not_bool(payload["row_count"], context=f"{cohort_ctx}.row_count")
        _validate_target_code_compatibility(
            payload["target_code_compatibility"], context=f"{cohort_ctx}.target_code_compatibility", cohort=cohort
        )
        _validate_class_conditional_availability(
            payload["class_conditional_field_availability"],
            context=f"{cohort_ctx}.class_conditional_field_availability",
        )
        _validate_categorical_code_compatibility(
            payload["categorical_code_compatibility"], context=f"{cohort_ctx}.categorical_code_compatibility"
        )
        _validate_measurement_unit_diagnostics(
            payload["measurement_unit_diagnostics"], context=f"{cohort_ctx}.measurement_unit_diagnostics"
        )

    summary = report["cross_site_compatibility_summary"]
    if not isinstance(summary, list) or len(summary) != len(COMPARATOR_COHORTS):
        raise ValueError("Strict cross-site report schema violation: unexpected cross-site summary length.")
    for idx, entry in enumerate(summary):
        entry_ctx = f"cross_site_compatibility_summary[{idx}]"
        assert_exact_keys(
            entry,
            {
                "comparator_cohort",
                "reference_cohort",
                "target_code_compatibility_status",
                "observed_target_label_set_relation",
                "categorical_code_compatibility",
                "measurement_unit_comparability",
                "five_field_joint_availability",
                "near_duplicate_candidate_cross_pairs_11_feature_rule",
                "cross_site_compatibility_status",
                "statistical_comparison_performed",
                "model_or_performance_comparison_performed",
                "clinical_or_transportability_claim_made",
                "evidence_status",
            },
            context=entry_ctx,
        )
        for key in (
            "statistical_comparison_performed",
            "model_or_performance_comparison_performed",
            "clinical_or_transportability_claim_made",
        ):
            if entry[key] is not False:
                raise ValueError(f"Strict cross-site report schema violation at '{entry_ctx}.{key}': must be False.")
        assert_int_not_bool(
            entry["near_duplicate_candidate_cross_pairs_11_feature_rule"],
            context=f"{entry_ctx}.near_duplicate_candidate_cross_pairs_11_feature_rule",
        )
        assert_exact_keys(
            entry["categorical_code_compatibility"],
            set(CATEGORICAL_FIVE_SUBSET),
            context=f"{entry_ctx}.categorical_code_compatibility",
        )
        for field in CATEGORICAL_FIVE_SUBSET:
            field_ctx = f"{entry_ctx}.categorical_code_compatibility.{field}"
            assert_exact_keys(
                entry["categorical_code_compatibility"][field],
                {
                    "reference_observed_codes",
                    "comparator_observed_codes",
                    "codes_absent_in_reference",
                    "codes_absent_in_comparator",
                    "observed_code_set_relation",
                    "compatibility_status",
                },
                context=field_ctx,
            )
            for key in (
                "reference_observed_codes",
                "comparator_observed_codes",
                "codes_absent_in_reference",
                "codes_absent_in_comparator",
            ):
                _assert_str_list(entry["categorical_code_compatibility"][field][key], context=f"{field_ctx}.{key}")
        joint = entry["five_field_joint_availability"]
        assert_exact_keys(
            joint,
            {"reference_cohort", "comparator_cohort", "interpretation"},
            context=f"{entry_ctx}.five_field_joint_availability",
        )
        for cohort_key in ("reference_cohort", "comparator_cohort"):
            block = joint[cohort_key]
            assert_exact_keys(
                block,
                {"all_records", "original_label_0", "original_labels_1_to_4"},
                context=f"{entry_ctx}.five_field_joint_availability.{cohort_key}",
            )
            for subgroup in ("all_records", "original_label_0", "original_labels_1_to_4"):
                _assert_int_map(
                    block[subgroup],
                    ("literal", "zero_trestbps_unavailable"),
                    context=f"{entry_ctx}.five_field_joint_availability.{cohort_key}.{subgroup}",
                )
        assert_exact_keys(
            entry["measurement_unit_comparability"],
            set(NUMERIC_FIVE_SUBSET),
            context=f"{entry_ctx}.measurement_unit_comparability",
        )
        for field in NUMERIC_FIVE_SUBSET:
            field_ctx = f"{entry_ctx}.measurement_unit_comparability.{field}"
            assert_exact_keys(
                entry["measurement_unit_comparability"][field],
                {
                    "reference_unit_verdict",
                    "comparator_unit_verdict",
                    "unit_comparability_status",
                    "unit_identity_status",
                },
                context=field_ctx,
            )
            if entry["measurement_unit_comparability"][field]["unit_identity_status"] != (
                "NOT_PROVABLE_FROM_FILE_CONTENT"
            ):
                raise ValueError(f"Strict cross-site report schema violation at '{field_ctx}': unit identity claimed.")

    overlaps = report["exact_profile_overlap_checks"]
    if not isinstance(overlaps, list) or len(overlaps) != len(COMPARATOR_COHORTS) * len(OVERLAP_FIELD_SETS):
        raise ValueError("Strict cross-site report schema violation: unexpected overlap-check length.")
    expected_field_set_labels = {label for label, _ in OVERLAP_FIELD_SETS}
    for idx, entry in enumerate(overlaps):
        entry_ctx = f"exact_profile_overlap_checks[{idx}]"
        assert_exact_keys(
            entry,
            {
                "comparison_id",
                "reference_cohort",
                "comparator_cohort",
                "field_set_label",
                "fields_compared",
                "fields_compared_count",
                "reference_row_count",
                "comparator_row_count",
                "distinct_matching_profiles",
                "matched_rows_in_reference",
                "matched_rows_in_comparator",
                "record_pairs_consistent_with_profile_match",
                "max_profile_multiplicity_in_reference",
                "max_profile_multiplicity_in_comparator",
                "multiplicity_rule",
                "profile_values_emitted",
                "identity_inference_permitted",
                "evidence_status",
            },
            context=entry_ctx,
        )
        if entry["field_set_label"] not in expected_field_set_labels:
            raise ValueError(f"Strict cross-site report schema violation at '{entry_ctx}': unexpected field set.")
        if entry["reference_cohort"] != REFERENCE_COHORT or entry["comparator_cohort"] not in COMPARATOR_COHORTS:
            raise ValueError(f"Strict cross-site report schema violation at '{entry_ctx}': unexpected cohort pair.")
        _assert_str_list(entry["fields_compared"], context=f"{entry_ctx}.fields_compared")
        for key in (
            "fields_compared_count",
            "reference_row_count",
            "comparator_row_count",
            "distinct_matching_profiles",
            "matched_rows_in_reference",
            "matched_rows_in_comparator",
            "record_pairs_consistent_with_profile_match",
            "max_profile_multiplicity_in_reference",
            "max_profile_multiplicity_in_comparator",
        ):
            assert_int_not_bool(entry[key], context=f"{entry_ctx}.{key}")
        if entry["profile_values_emitted"] is not False:
            raise ValueError(f"Strict cross-site report schema violation at '{entry_ctx}': profile values emitted.")
        if entry["identity_inference_permitted"] is not False:
            raise ValueError(f"Strict cross-site report schema violation at '{entry_ctx}': identity inference permitted.")

    for list_key, id_key in (
        ("identity_and_independence_warnings", "warning_id"),
        ("blockers", "blocker_id"),
        ("evidence_limitations", "limitation_id"),
    ):
        entries = report[list_key]
        if not isinstance(entries, list) or not entries:
            raise ValueError(f"Strict cross-site report schema violation: '{list_key}' must be a non-empty list.")
        for idx, item in enumerate(entries):
            item_ctx = f"{list_key}[{idx}]"
            if list_key == "identity_and_independence_warnings":
                assert_exact_keys(item, {id_key, "statement"}, context=item_ctx)
            elif list_key == "blockers":
                assert_exact_keys(
                    item,
                    {id_key, "summary", "required_resolution", "required_authorization", "status"},
                    context=item_ctx,
                )
            else:
                assert_exact_keys(item, {id_key, "statement"}, context=item_ctx)
            if not isinstance(item[id_key], str) or not item[id_key].strip():
                raise ValueError(f"Strict cross-site report schema violation at '{item_ctx}': missing identifier.")

    integrity = report["input_integrity_and_privacy"]
    assert_exact_keys(
        integrity,
        {
            "git_ignore_verified",
            "byte_identity_guard_file_count",
            "byte_identity_snapshots",
            "raw_cleveland_parsed",
            "privacy_controls",
            "evidence_status",
        },
        context="input_integrity_and_privacy",
    )
    assert_int_not_bool(
        integrity["byte_identity_guard_file_count"], context="input_integrity_and_privacy.byte_identity_guard_file_count"
    )
    if integrity["raw_cleveland_parsed"] is not False:
        raise ValueError("Strict cross-site report schema violation: raw Cleveland must remain unparsed.")
    if not isinstance(integrity["byte_identity_snapshots"], list) or not integrity["byte_identity_snapshots"]:
        raise ValueError("Strict cross-site report schema violation: byte-identity snapshots are required.")
    for idx, snapshot in enumerate(integrity["byte_identity_snapshots"]):
        snapshot_ctx = f"input_integrity_and_privacy.byte_identity_snapshots[{idx}]"
        assert_exact_keys(
            snapshot,
            {"filename", "relative_path", "pre_sha256", "post_sha256", "size_bytes", "byte_identical"},
            context=snapshot_ctx,
        )
        assert_int_not_bool(snapshot["size_bytes"], context=f"{snapshot_ctx}.size_bytes")
        if snapshot["byte_identical"] is not True:
            raise ValueError(f"Strict cross-site report schema violation at '{snapshot_ctx}': originals not byte-identical.")

    summary_block = report["feasibility_summary"]
    assert_exact_keys(
        summary_block,
        {
            "reference_cohort",
            "comparator_cohorts",
            "predeclared_fields",
            "target_code_compatibility_status_by_comparator",
            "cohorts_with_blocking_findings",
            "overall_status",
            "downstream_comparison_authorization_status",
            "blocker_count",
            "evidence_limitation_count",
            "human_scientific_review_required_before_any_downstream_comparison",
            "evidence_status",
        },
        context="feasibility_summary",
    )
    _assert_str_list(summary_block["cohorts_with_blocking_findings"], context="feasibility_summary.cohorts_with_blocking_findings")
    assert_exact_keys(
        summary_block["target_code_compatibility_status_by_comparator"],
        set(COMPARATOR_COHORTS),
        context="feasibility_summary.target_code_compatibility_status_by_comparator",
    )
    assert_int_not_bool(summary_block["blocker_count"], context="feasibility_summary.blocker_count")
    assert_int_not_bool(
        summary_block["evidence_limitation_count"], context="feasibility_summary.evidence_limitation_count"
    )
    if summary_block["downstream_comparison_authorization_status"] != (
        "NOT_AUTHORIZED_GATE_PT_CLOSED_D047_SCOPE_CLEVELAND_ONLY"
    ):
        raise ValueError("Strict cross-site report schema violation: downstream status wording changed.")
    if summary_block["human_scientific_review_required_before_any_downstream_comparison"] is not True:
        raise ValueError("Strict cross-site report schema violation: human review gate must remain required.")


# ---------------------------------------------------------------------------
# Markdown rendering (aggregate-only)
# ---------------------------------------------------------------------------


def _md_codes(codes: Sequence[str]) -> str:
    return ", ".join(f"`{code}`" for code in codes) if codes else "(none)"


def render_cross_site_markdown(report: Mapping[str, Any]) -> str:
    """Render the focused feasibility report as aggregate-only Markdown."""
    gov = report["governance_and_authorization"]
    cert = report["safety_and_scope_certification"]
    scope = report["scope_and_evidence_boundary"]
    summary = report["feasibility_summary"]

    lines: list[str] = [
        "# CardioAssist AI — UCI-45 Cross-Site Feasibility Audit (Read-Only, Aggregate-Only)",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Report Type | `{report['report_type']}` |",
        f"| Status Label | `{report['status_label']}` |",
        f"| Execution Mode | `{report['execution_mode']}` |",
        f"| Evidence Scope | `{report['synthetic_disclaimer']}` |",
        f"| Governance Decision | `{gov['governance_decision_id']}` (`{gov['workflow_status']}`) |",
        f"| Gate PT Status | `{gov['gate_pt_status']}` |",
        f"| Supervisor Approval Claimed | `{gov['supervisor_approval_claimed']}` |",
        f"| Model Fitting Performed | `{cert['model_fitting_performed']}` |",
        f"| Statistical Test Performed | `{cert['statistical_test_performed']}` |",
        f"| Patient-Level Rows Emitted | `{cert['patient_level_rows_emitted']}` |",
        f"| Raw Cleveland Parsed | `{cert['raw_cleveland_parsed']}` |",
        f"| Overall Feasibility Status | `{summary['overall_status']}` |",
        "",
        "## 1. Authorization Scope Determination",
        "",
        f"- **D-046 scope determination**: `{gov['d046_scope_determination']}`",
        f"- **Basis**: {gov['d046_scope_basis']}",
        f"- **Downstream comparison inside this authorization**: `{gov['downstream_comparison_within_this_authorization']}`",
        f"- **Additional authorization required**: {gov['additional_authorization_required']}",
        "",
        "## 2. Declared Scope and Predeclared Fields",
        "",
        f"- **Reference cohort**: `{scope['reference_cohort']}`",
        f"- **Comparator cohorts**: {_md_codes(scope['comparator_cohorts'])}",
        f"- **Predeclared fields** (fixed before execution): {_md_codes(scope['predeclared_fields'])}",
        f"- **Cohorts not assessed**: {_md_codes(list(scope['cohorts_not_assessed'].keys()))}",
        f"- **Overlap field sets**: {_md_codes(scope['overlap_field_sets'])}",
        f"- **Parsed source files**: {_md_codes(scope['parsed_source_files'])}",
        f"- **Proven independence claim permitted**: `{scope['proven_independence_claim_permitted']}`",
        f"- **Raw Cleveland**: {scope['raw_cleveland_quarantine']}",
        "",
        "## 3. Source-Specific Target-Code Compatibility (original labels retained)",
        "",
        "| Cohort | Original label counts (num 0-4) | Unclassified | Uses 0/1-only coding | Relation | Compatibility status |",
        "|---|---|---|---|---|---|",
    ]

    for cohort in AUDITED_COHORTS:
        target = report["cohorts"][cohort]["target_code_compatibility"]
        counts = target["original_target_label_counts"]
        count_text = " / ".join(f"`{code}`={counts[code]}" for code in TARGET_LABEL_CODES)
        lines.append(
            f"| `{cohort}` | {count_text} | `{target['unclassified_target_record_count']}` | "
            f"`{target['uses_pre_binarized_0_1_coding']}` | `{target['observed_target_label_set_relation']}` | "
            f"`{target['compatibility_status']}` |"
        )

    lines.extend(
        [
            "",
            "The documented rule is reported, not applied to source files: "
            f"{UCI_45_TARGET_RULE_TEXT}",
            "",
            "## 4. Class-Conditional Availability of the Five Predeclared Fields",
            "",
            "Counts are records with the field observed, stratified by the ORIGINAL target label. "
            "The zero-unavailable variant is a descriptive sensitivity rule for source-flagged "
            "zero blood pressure only; no source value is changed.",
            "",
        ]
    )

    for cohort in AUDITED_COHORTS:
        availability = report["cohorts"][cohort]["class_conditional_field_availability"]
        lines.extend(
            [
                f"### {cohort}",
                "",
                "| Stratum | Records | age | sex | cp | trestbps | restecg | All five (literal) | All five (zero rule) |",
                "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for stratum_key in CLASS_STRATA_KEYS:
            stratum = availability["strata"][stratum_key]
            observed = stratum["per_field_observed_count"]
            lines.append(
                f"| `{stratum_key}` | {stratum['record_count']} | {observed['age']} | {observed['sex']} | "
                f"{observed['cp']} | {observed['trestbps']} | {observed['restecg']} | "
                f"{stratum['all_five_fields_observed_literal']} | "
                f"{stratum['all_five_fields_observed_zero_trestbps_unavailable']} |"
            )
        lines.append("")

    lines.extend(
        [
            "## 5. Categorical Code Compatibility",
            "",
            "| Cohort | Field | Documented domain | Observed codes | Outside domain | Conformance |",
            "|---|---|---|---|---:|---|",
        ]
    )
    for cohort in AUDITED_COHORTS:
        fields = report["cohorts"][cohort]["categorical_code_compatibility"]["fields"]
        for field in CATEGORICAL_FIVE_SUBSET:
            entry = fields[field]
            lines.append(
                f"| `{cohort}` | `{field}` | {_md_codes(entry['documented_domain_codes'])} | "
                f"{_md_codes(entry['observed_codes'])} | {entry['codes_outside_documented_domain_count']} | "
                f"`{entry['documented_domain_conformance']}` |"
            )

    lines.extend(
        [
            "",
            "## 6. Measurement-Unit Diagnostics (heuristic, never a unit identity proof)",
            "",
            "| Cohort | Field | Documented unit | Observed | Zero/negative | Implausible | Unit verdict |",
            "|---|---|---|---:|---:|---:|---|",
        ]
    )
    for cohort in AUDITED_COHORTS:
        fields = report["cohorts"][cohort]["measurement_unit_diagnostics"]["fields"]
        for field in NUMERIC_FIVE_SUBSET:
            entry = fields[field]
            lines.append(
                f"| `{cohort}` | `{field}` | `{entry['documented_unit']}` | {entry['observed_value_count']} | "
                f"{entry['zero_or_negative_count']} | {entry['implausible_value_count']} | `{entry['unit_verdict']}` |"
            )

    lines.extend(["", "### 6.1 Value-Band Counts", ""])
    for cohort in AUDITED_COHORTS:
        fields = report["cohorts"][cohort]["measurement_unit_diagnostics"]["fields"]
        for field in NUMERIC_FIVE_SUBSET:
            entry = fields[field]
            bands = " / ".join(f"`{label}`={entry['band_counts'][label]}" for label in entry["band_labels"])
            lines.append(f"- `{cohort}` / `{field}`: {bands}; missing=`{entry['missing_count']}`")

    lines.extend(
        [
            "",
            "## 7. Cross-Site Compatibility Summary (descriptive only)",
            "",
        ]
    )
    for entry in report["cross_site_compatibility_summary"]:
        lines.append(f"### Cleveland vs `{entry['comparator_cohort']}`")
        lines.append("")
        lines.append(f"- **Target-code status**: `{entry['target_code_compatibility_status']}`")
        lines.append(f"- **Observed target-label relation**: `{entry['observed_target_label_set_relation']}`")
        lines.append(f"- **Cross-site compatibility status**: `{entry['cross_site_compatibility_status']}`")
        lines.append(
            "- **Near-duplicate candidate cross pairs (11-feature rule)**: "
            f"`{entry['near_duplicate_candidate_cross_pairs_11_feature_rule']}`"
        )
        joint = entry["five_field_joint_availability"]
        lines.append(
            "  - Five-field joint availability (literal / zero-BP-unavailable): "
            f"reference all=`{joint['reference_cohort']['all_records']['literal']}`/"
            f"`{joint['reference_cohort']['all_records']['zero_trestbps_unavailable']}`, "
            f"comparator all=`{joint['comparator_cohort']['all_records']['literal']}`/"
            f"`{joint['comparator_cohort']['all_records']['zero_trestbps_unavailable']}`, "
            f"reference label-0=`{joint['reference_cohort']['original_label_0']['literal']}`, "
            f"comparator label-0=`{joint['comparator_cohort']['original_label_0']['literal']}`, "
            f"reference label-1..4=`{joint['reference_cohort']['original_labels_1_to_4']['literal']}`, "
            f"comparator label-1..4=`{joint['comparator_cohort']['original_labels_1_to_4']['literal']}` "
            f"(`{joint['interpretation']}`)"
        )
        for field, code_entry in entry["categorical_code_compatibility"].items():
            lines.append(
                f"  - `{field}`: reference {_md_codes(code_entry['reference_observed_codes'])}, "
                f"comparator {_md_codes(code_entry['comparator_observed_codes'])}, "
                f"relation `{code_entry['observed_code_set_relation']}`, status `{code_entry['compatibility_status']}`"
            )
        for field, unit_entry in entry["measurement_unit_comparability"].items():
            lines.append(
                f"  - `{field}` unit comparability: `{unit_entry['unit_comparability_status']}` "
                f"(`{unit_entry['unit_identity_status']}`)"
            )
        lines.append("")

    lines.extend(
        [
            "## 8. Privacy-Safe Exact-Profile Overlap (duplicate multiplicity preserved)",
            "",
            "| Comparison | Field set | Fields | Matching profiles | Rows (ref) | Rows (cmp) | Record pairs | Max multiplicity (ref/cmp) |",
            "|---|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    for entry in report["exact_profile_overlap_checks"]:
        lines.append(
            f"| `{entry['comparison_id']}` | `{entry['field_set_label']}` | {entry['fields_compared_count']} | "
            f"{entry['distinct_matching_profiles']} | {entry['matched_rows_in_reference']} | "
            f"{entry['matched_rows_in_comparator']} | {entry['record_pairs_consistent_with_profile_match']} | "
            f"{entry['max_profile_multiplicity_in_reference']} / {entry['max_profile_multiplicity_in_comparator']} |"
        )

    lines.extend(["", "## 9. Identity and Independence Warnings", ""])
    for warning in report["identity_and_independence_warnings"]:
        lines.append(f"- **`{warning['warning_id']}`** — {warning['statement']}")

    lines.extend(["", "## 10. Blockers to Any Future Cross-Site Comparison", ""])
    for blocker in report["blockers"]:
        lines.append(
            f"- **`{blocker['blocker_id']}`** (`{blocker['status']}`) — {blocker['summary']} "
            f"*Required resolution:* {blocker['required_resolution']} "
            f"*Required authorization:* {blocker['required_authorization']}"
        )

    lines.extend(["", "## 11. Evidence Limitations", ""])
    for limitation in report["evidence_limitations"]:
        lines.append(f"- **`{limitation['limitation_id']}`** — {limitation['statement']}")

    integrity = report["input_integrity_and_privacy"]
    lines.extend(
        [
            "",
            "## 12. Input Integrity and Privacy Controls",
            "",
            f"- **Byte-guarded files**: `{integrity['byte_identity_guard_file_count']}` (all byte-identical: "
            f"`{all(s['byte_identical'] for s in integrity['byte_identity_snapshots'])}`)",
            f"- **Raw Cleveland parsed**: `{integrity['raw_cleveland_parsed']}`",
            f"- **Privacy controls**: `{integrity['privacy_controls']}`",
            "",
            "## 13. How to Run This Audit Locally (maintainer machine only)",
            "",
            "```powershell",
            "python -m research.audit.cross_site_feasibility --auth-manifest data/manifests/gate_da_authorization.local.json --provenance-manifest data/manifests/provenance_manifest.json --json-out data/reports/uci-45-cross-site-feasibility.json --markdown-out data/reports/uci-45-cross-site-feasibility.md",
            "```",
            "",
            "Share only the aggregate report after human privacy review. Do not commit, paste, or upload "
            "dataset files, local manifests, or row-level values.",
            "",
        ]
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Authorized local execution
# ---------------------------------------------------------------------------


def _processed_filename_map() -> dict[str, str]:
    mapping = {cohort: filename for cohort, filename in PROCESSED_FILES}
    missing = [cohort for cohort in AUDITED_COHORTS if cohort not in mapping]
    if missing:
        raise RuntimeError(f"STOP: Missing processed-file mapping for cohort(s): {missing}")
    return mapping


def _assert_manifest_gates(auth_manifest: Mapping[str, Any]) -> None:
    """Fail closed unless the manifest still records a read-only, non-fitting posture."""
    if auth_manifest.get("model_fitting_authorized") is not False:
        raise RuntimeError("STOP: Authorization manifest must record model_fitting_authorized=false.")
    if auth_manifest.get("gate_pt_status") != "CLOSED_REQUIRES_SUPERVISOR_SIGNOFF_P3":
        raise RuntimeError("STOP: Gate PT must remain CLOSED_REQUIRES_SUPERVISOR_SIGNOFF_P3.")
    if auth_manifest.get("supervisor_approval_claimed") is True:
        raise RuntimeError("STOP: A supervisor-approval claim is not permitted in this audit manifest.")


def run_cross_site_feasibility_audit(
    *,
    repo_root: Path = REPO_ROOT,
    base_data_parent: Path | None = None,
    auth_manifest_path: Path | None = None,
    provenance_manifest_path: Path | None = None,
    is_synthetic_fixture_run: bool = False,
    allow_external_tmp_root: Path | None = None,
    json_output_path: Path | str | None = None,
    markdown_output_path: Path | str | None = None,
) -> tuple[dict[str, Any], str]:
    """Run the authorized read-only cross-site feasibility audit; return (report, markdown)."""
    root = repo_root.resolve()
    parent = (base_data_parent or root).resolve()
    auth_path = auth_manifest_path or (parent / "data/manifests/gate_da_authorization.local.json")
    prov_path = provenance_manifest_path or (parent / "data/manifests/provenance_manifest.json")

    verify_git_ignore(root)
    verify_data_root_containment(root, parent / "data", allow_external_tmp_root=allow_external_tmp_root)
    verify_data_root_containment(root, prov_path, allow_external_tmp_root=allow_external_tmp_root)

    auth = load_authorization_manifest(auth_path)
    verify_global_workflow_authorized(auth)
    verify_dataset_authorized_for_audit(auth, "DA-A2")
    _assert_manifest_gates(auth)

    verified = validate_provenance_manifest(prov_path, parent, auth, ("DA-A2",))
    files = verified["DA-A2"]
    guard_entries: list[tuple[str, Path, str, int]] = [
        (
            str(meta["relative_path"]),
            Path(meta["resolved_path"]),
            str(meta["verified_sha256"]),
            int(meta["verified_size_bytes"]),
        )
        for _, meta in sorted(files.items())
    ]

    filename_by_cohort = _processed_filename_map()
    source_filenames = {
        cohort: filename_by_cohort[cohort] for cohort in AUDITED_COHORTS
    }

    forbidden_fingerprints: list[str] = []
    with ByteIdentityGuard(guard_entries) as guard:
        # Lock output destinations before any dataset file is opened.
        if json_output_path is not None:
            validate_and_resolve_report_output_path(
                parent,
                json_output_path,
                expected_suffix=".json",
                repo_root=root,
                allow_external_tmp_root=allow_external_tmp_root,
            )
        if markdown_output_path is not None:
            validate_and_resolve_report_output_path(
                parent,
                markdown_output_path,
                expected_suffix=".md",
                repo_root=root,
                allow_external_tmp_root=allow_external_tmp_root,
            )

        cohort_rows: dict[str, list[dict[str, Any]]] = {}
        for cohort in AUDITED_COHORTS:
            filename = source_filenames[cohort]
            parsed = audit_uci_45_processed_file(Path(files[filename]["resolved_path"]))
            rows = parsed["normalized_rows"]
            if not rows or len(rows) != parsed["report"]["row_count"]:
                raise RuntimeError(f"STOP: Processed cohort row count mismatch for '{filename}'.")
            cohort_rows[cohort] = rows
            forbidden_fingerprints.extend(parsed["raw_row_fingerprints"])

        snapshots = guard.verify_unchanged_now()
        report = build_feasibility_report(
            cohort_rows=cohort_rows,
            source_filenames=source_filenames,
            governance_context=_governance_context(auth),
            byte_identity_snapshots=[
                {
                    "filename": snapshot.filename,
                    "relative_path": snapshot.relative_path,
                    "pre_sha256": snapshot.pre_sha256,
                    "post_sha256": snapshot.post_sha256,
                    "size_bytes": snapshot.size_bytes,
                    "byte_identical": snapshot.byte_identical,
                }
                for snapshot in snapshots
            ],
            is_synthetic_fixture_run=is_synthetic_fixture_run,
        )

        markdown = render_cross_site_markdown(report)
        validate_cross_site_report_schema(report)
        verify_report_no_patient_rows(
            dict(report),
            markdown,
            enforce_strict_schema=False,
            forbidden_row_fingerprints=forbidden_fingerprints,
        )

        # Write only after both privacy controls have passed.
        if json_output_path is not None:
            resolved_json = validate_and_resolve_report_output_path(
                parent,
                json_output_path,
                expected_suffix=".json",
                repo_root=root,
                allow_external_tmp_root=allow_external_tmp_root,
            )
            resolved_json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        if markdown_output_path is not None:
            resolved_md = validate_and_resolve_report_output_path(
                parent,
                markdown_output_path,
                expected_suffix=".md",
                repo_root=root,
                allow_external_tmp_root=allow_external_tmp_root,
            )
            resolved_md.write_text(markdown, encoding="utf-8")

    return report, markdown


def main(
    argv: Sequence[str] | None = None,
    *,
    repo_root: Path = REPO_ROOT,
    base_data_parent: Path | None = None,
    allow_external_tmp_root: Path | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m research.audit.cross_site_feasibility",
        description=(
            "Read-only, aggregate-only UCI-45 cross-site feasibility audit "
            "(Cleveland vs Hungary/VA). No fitting, no comparison result, no clinical claim."
        ),
    )
    parser.add_argument("--auth-manifest", required=True, type=Path)
    parser.add_argument("--provenance-manifest", required=True, type=Path)
    parser.add_argument(
        "--json-out",
        type=Path,
        default=Path("data/reports/uci-45-cross-site-feasibility.json"),
        help="Report output is restricted to data/reports/<filename>.json",
    )
    parser.add_argument(
        "--markdown-out",
        type=Path,
        default=Path("data/reports/uci-45-cross-site-feasibility.md"),
        help="Report output is restricted to data/reports/<filename>.md",
    )
    args = parser.parse_args(argv)

    report, _markdown = run_cross_site_feasibility_audit(
        repo_root=repo_root,
        base_data_parent=base_data_parent,
        auth_manifest_path=args.auth_manifest,
        provenance_manifest_path=args.provenance_manifest,
        allow_external_tmp_root=allow_external_tmp_root,
        json_output_path=args.json_out,
        markdown_output_path=args.markdown_out,
    )
    summary = report["feasibility_summary"]
    print(
        json.dumps(
            {
                "status_label": report["status_label"],
                "overall_status": summary["overall_status"],
                "cohorts_with_blocking_findings": summary["cohorts_with_blocking_findings"],
                "blocker_count": summary["blocker_count"],
                "evidence_limitation_count": summary["evidence_limitation_count"],
                "json_out": str(args.json_out),
                "markdown_out": str(args.markdown_out),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
