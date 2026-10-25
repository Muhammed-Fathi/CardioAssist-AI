"""Focused, aggregate-only UCI-412 source-semantics audit (``DA-A1``).

Purpose: answer **three** narrowly scoped, purely descriptive questions about the
delivered *Z-Alizadeh Sani* workbook, using the file the project has already
audited, without fitting, evaluating, pooling, translating labels, altering the
original, or emitting any patient-level value:

1. **Registered coding coverage** — for the six registered text-binary columns
   (``Sex``, ``DLP``, ``Atypical``, ``Nonanginal``, ``Exertional CP``,
   ``Dyspnea``), do all observed cells fall inside the frozen research feature
   dictionary's *registered* source vocabulary, and which registered tokens
   actually occur (counts only)?
2. **Four-field chest-pain joint census** — what is the joint distribution of
   ``Typical Chest Pain``, ``Atypical``, ``Nonanginal`` and ``Exertional CP``
   across records (aggregate counts only)?
3. **Bundled source documentation** — is inspection of the archive documentation
   permitted under the exact existing D-046 authorization? (Answer recorded as a
   fixed, code-enforced status: **no**.)

Scope discipline
----------------
* Read-only diagnostic inside the D-046 local audit authorization for ``DA-A1``.
  It parses only ``Z-Alizadeh sani dataset.xlsx`` through the *existing*
  :func:`research.audit.validators.audit_uci_412_or_411_workbook` validator, so
  header, target, leakage, missingness and duplicate validation are not
  re-implemented or weakened here.
* The frozen feature dictionary
  (``research/uci412/schemas/uci412_feature_dictionary.v1.json``) is read
  **read-only**, must be a *committed, clean* repository file, and its SHA-256 is
  recorded in the report. No dictionary, protocol, decision register, plan or
  registration file is modified by this module.
* Every input file is SHA-256/byte-size verified and byte-guarded for the whole
  run. Inputs stay in Git-ignored ``data/``; outputs are restricted to
  ``data/reports/``. Reports carry integer aggregates, fixed labels and
  **registered tokens only**: an unregistered source token is *counted* but its
  text is never echoed, so a stray identifier-like string cannot reach a report.
* No model, no feature selection, no threshold, no metric, no comparison, no
  clinical claim. Gate PT P-3 stays CLOSED; D-047/D-048 are not extended.

Why this module exists (and why it is small)
--------------------------------------------
The existing audit toolchain already validates the workbook, its target, its
missingness and its duplicates, and the existing ``research/uci412`` research
adapter computes token counts *inside* a D-048 internal-research run that is
**not authorized today**. Neither provides an *audit-scoped* token census, a
four-way descriptor census, or a registered-vocabulary coverage record. This
module adds only those three diagnostics and deliberately reuses the existing
authorization, provenance, byte-identity, parsing, output-path and privacy
controls rather than duplicating them.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
from collections import Counter
from itertools import product
from pathlib import Path
from typing import Any, Mapping, Sequence

from research.audit.cli import REPO_ROOT
from research.audit.exceptions import FormatValidationError
from research.audit.git_safety import verify_data_root_containment, verify_git_ignore
from research.audit.provenance import (
    ByteIdentityGuard,
    load_authorization_manifest,
    sha256_file,
    validate_and_resolve_report_output_path,
    validate_provenance_manifest,
    verify_dataset_authorized_for_audit,
    verify_global_workflow_authorized,
)
from research.audit.registry import EVIDENCE_VERIFIED
from research.audit.reporting import (
    assert_exact_keys,
    assert_int_not_bool,
    verify_report_no_patient_rows,
)
from research.audit.validators import audit_uci_412_or_411_workbook

REPORT_SCHEMA_VERSION = "1.0.0"
REPORT_TYPE = "UCI412_SOURCE_SEMANTICS_READ_ONLY_AGGREGATE_AUDIT"
STATUS_LABEL = "READ_ONLY_DESCRIPTIVE_ONLY_NOT_TRAINING_AUTHORIZATION"

DATASET_ID = "DA-A1"
AUTHORIZED_WORKBOOK_FILENAME = "Z-Alizadeh sani dataset.xlsx"

# Predeclared, fixed scope. Changing these tuples requires a reviewed code change,
# so the audited column set cannot be tuned after seeing any result.
TEXT_BINARY_COLUMNS: tuple[str, ...] = (
    "Sex",
    "DLP",
    "Atypical",
    "Nonanginal",
    "Exertional CP",
    "Dyspnea",
)
CHEST_PAIN_DESCRIPTOR_COLUMNS: tuple[str, ...] = (
    "Typical Chest Pain",
    "Atypical",
    "Nonanginal",
    "Exertional CP",
)
AUDITED_COLUMNS: tuple[str, ...] = tuple(
    dict.fromkeys(TEXT_BINARY_COLUMNS + CHEST_PAIN_DESCRIPTOR_COLUMNS)
)

FEATURE_DICTIONARY_RELATIVE_PATH = "research/uci412/schemas/uci412_feature_dictionary.v1.json"
EXPECTED_DICTIONARY_SCHEMA_ID = "uci412_research_feature_dictionary"

TEXT_VOCABULARY_REPRESENTATION = "REGISTERED_TEXT_VOCABULARY"
NUMERIC_BINARY_REPRESENTATION = "REGISTERED_NUMERIC_BINARY_ENCODING"

BUCKET_REGISTERED = "registered"
BUCKET_MISSING = "missing"
BUCKET_UNREGISTERED = "unregistered"

COVERAGE_ALL_CELLS = "REGISTERED_VOCABULARY_COVERS_ALL_CELLS"
COVERAGE_ALL_OBSERVED_WITH_MISSING = (
    "REGISTERED_VOCABULARY_COVERS_ALL_OBSERVED_CELLS_WITH_MISSING_CELLS"
)
COVERAGE_UNREGISTERED = "UNREGISTERED_TOKEN_OBSERVED_REQUIRES_HUMAN_REVIEW"

CELL_KEY_SEPARATOR = "/"

# Fixed cell-shape vocabulary. Only shapes are recorded, never values, so a column
# that is numeric where text was registered (or vice versa) is diagnosable without
# echoing any source string.
CELL_SHAPES: tuple[str, ...] = (
    "text",
    "integral_number",
    "non_integral_number",
    "boolean",
    "other",
)

BUNDLED_DOCUMENTATION_STATUS = "NOT_PERFORMED_NOT_AUTHORIZED_BY_D046"
BUNDLED_DOCUMENTATION_REQUIREMENT = (
    "Inspecting the archive's bundled documentation requires a new explicit human authorization "
    "that names that exact documentation file, extends the D-046 read-only audit scope, and is "
    "followed by a re-recorded provenance manifest. It is not implied by the DA-A1 workbook "
    "authorization and is not inferred here."
)

EVIDENCE_LIMITATIONS: tuple[dict[str, str], ...] = (
    {
        "id": "L-01-TOKEN-CENSUS-IS-NOT-A-CODEBOOK",
        "statement": (
            "A token census records which registered tokens occur and how often. It does not "
            "establish what the source owner meant by a token, nor that any token's clinical "
            "definition matches another dataset."
        ),
    },
    {
        "id": "L-02-JOINT-COUNTS-ARE-NOT-DEFINITIONS",
        "statement": (
            "Four-way co-occurrence counts answer whether records carry more than one registered "
            "chest-pain descriptor. They do not define the elicitation criteria of 'typical', "
            "'atypical', 'non-anginal' or 'exertional' chest pain, and they are not an angina "
            "classification."
        ),
    },
    {
        "id": "L-03-DIRECTION-IS-REGISTERED-NOT-OWNER-CONFIRMED",
        "statement": (
            "The descriptor-count distribution maps tokens through the frozen dictionary's "
            "registered codes. For the text-binary columns that direction remains "
            "SECONDARY_SOURCE_UNVERIFIED; for 'Typical Chest Pain' it is human-audited as a "
            "representation but its 0 = absent / 1 = present direction stays PROVISIONAL. The "
            "direction-free evidence is the registered-token census, not the code distribution."
        ),
    },
    {
        "id": "L-04-NO-RECORD-LEVEL-VERIFICATION",
        "statement": (
            "Every quantity is an aggregate. Nothing here verifies any individual record, its "
            "acquisition time, its label correctness, or its identity, and no per-record "
            "acquisition timing is established."
        ),
    },
    {
        "id": "L-05-SINGLE-SOURCE-FAMILY",
        "statement": (
            "This audit covers one workbook only. It performs no cross-dataset harmonization, no "
            "comparison with UCI-45 or UCI-411, and no pooling; UCI-411 remains the same 303 "
            "participants and is not touched here."
        ),
    },
    {
        "id": "L-06-SYNTHETIC-RUNS-ARE-NOT-EVIDENCE",
        "statement": (
            "A synthetic-fixture run exercises the software controls only. It is not medical "
            "evidence, not a benchmark result and not a source finding."
        ),
    },
)


# ---------------------------------------------------------------------------
# Registered source semantics (frozen dictionary, read-only)
# ---------------------------------------------------------------------------


def _verify_committed_repo_file(repo_root: Path, relative_path: str) -> Path:
    """Resolve a repository file that must be committed and clean in the working tree."""
    root = repo_root.resolve()
    candidate = root / Path(relative_path)
    if candidate.is_symlink():
        raise FormatValidationError(
            f"Registered dictionary path '{relative_path}' must not be a symlink."
        )
    resolved = candidate.resolve()
    if root != resolved and root not in resolved.parents:
        raise FormatValidationError(
            f"Registered dictionary path '{relative_path}' resolves outside the repository root."
        )
    if not resolved.is_file():
        raise FormatValidationError(
            f"Required registered dictionary '{relative_path}' is missing. Failing closed."
        )

    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", relative_path],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    if tracked.returncode != 0 or not tracked.stdout.strip():
        raise FormatValidationError(
            f"Registered dictionary '{relative_path}' is not tracked by Git. A local, unreviewed "
            "vocabulary must never define the audit's coding checks. Failing closed."
        )
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--", relative_path],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    if dirty.returncode != 0:
        raise FormatValidationError(
            f"Could not verify the committed state of '{relative_path}': {dirty.stderr.strip()}"
        )
    if dirty.stdout.strip():
        raise FormatValidationError(
            f"Registered dictionary '{relative_path}' has uncommitted local modifications "
            f"({dirty.stdout.strip()}). Review and commit any vocabulary change before auditing. "
            "Failing closed."
        )
    return resolved


def _registered_source_spec(feature: Mapping[str, Any], *, column: str) -> dict[str, Any]:
    """Extract one column's registered source representation without inventing tokens."""
    if str(feature.get("kind", "")) != "binary":
        raise FormatValidationError(
            f"STOP: registered column '{column}' is not declared binary "
            f"(kind='{feature.get('kind')}'); the predeclared audit assumes binary descriptors."
        )

    vocabulary = feature.get("vocabulary")
    encoding = feature.get("source_value_encoding")

    if isinstance(vocabulary, dict) and vocabulary:
        tokens = sorted(str(key) for key in vocabulary)
        token_to_code = {str(key): int(value) for key, value in vocabulary.items()}
        representation = TEXT_VOCABULARY_REPRESENTATION
        evidence_status = feature.get("vocabulary_evidence_status")
    elif isinstance(encoding, dict):
        absent = str(encoding.get("absent_source_value"))
        present = str(encoding.get("present_source_value"))
        if absent == present:
            raise FormatValidationError(
                f"STOP: registered numeric-binary encoding for '{column}' has identical "
                "absent/present source values."
            )
        tokens = sorted({absent, present})
        token_to_code = {
            absent: int(encoding.get("absent_model_code")),
            present: int(encoding.get("present_model_code")),
        }
        representation = NUMERIC_BINARY_REPRESENTATION
        evidence_status = encoding.get("verification_status")
    else:
        raise FormatValidationError(
            f"STOP: registered column '{column}' has neither a source vocabulary nor a registered "
            "source-value encoding. Refusing to audit an unregistered column."
        )

    if set(token_to_code.values()) != {0, 1}:
        raise FormatValidationError(
            f"STOP: registered codes for '{column}' are not binary (observed codes "
            f"{sorted(set(token_to_code.values()))})."
        )

    return {
        "column": column,
        "source_representation": representation,
        "registered_tokens": tokens,
        "registered_token_set": frozenset(tokens),
        "registered_token_to_code": token_to_code,
        "vocabulary_evidence_status": str(evidence_status),
        "dictionary_declared_kind": str(feature.get("kind")),
        "dictionary_admission": str(feature.get("admission")),
    }


def load_registered_source_semantics(repo_root: Path) -> dict[str, Any]:
    """Load the frozen dictionary read-only and register the audited columns' vocabularies."""
    path = _verify_committed_repo_file(repo_root, FEATURE_DICTIONARY_RELATIVE_PATH)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - fail closed with a clear message
        raise FormatValidationError(
            f"Registered dictionary '{FEATURE_DICTIONARY_RELATIVE_PATH}' is unreadable: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise FormatValidationError("Registered dictionary root must be a JSON object.")
    if str(payload.get("schema_id")) != EXPECTED_DICTIONARY_SCHEMA_ID:
        raise FormatValidationError(
            f"Registered dictionary schema_id '{payload.get('schema_id')}' is not "
            f"'{EXPECTED_DICTIONARY_SCHEMA_ID}'. Failing closed."
        )
    features = payload.get("features")
    if not isinstance(features, dict):
        raise FormatValidationError("Registered dictionary has no usable 'features' object.")

    missing = [column for column in AUDITED_COLUMNS if column not in features]
    if missing:
        raise FormatValidationError(
            f"Registered dictionary does not register audited column(s) {missing}. Failing closed."
        )

    columns = {
        column: _registered_source_spec(features[column], column=column)
        for column in AUDITED_COLUMNS
    }
    digest, size = sha256_file(path)
    return {
        "schema_id": str(payload.get("schema_id")),
        "schema_version": str(payload.get("schema_version")),
        "relative_path": FEATURE_DICTIONARY_RELATIVE_PATH,
        "sha256": digest,
        "size_bytes": int(size),
        "columns": columns,
        "loaded_read_only": True,
        "dictionary_modified_by_this_audit": False,
    }


# ---------------------------------------------------------------------------
# Pure diagnostic primitives (unit-testable without file access)
# ---------------------------------------------------------------------------


def source_cell_shape(value: Any) -> str:
    """Return a fixed, non-identifying shape label for one non-missing cell."""
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        numeric = float(value)
        if math.isfinite(numeric) and numeric.is_integer():
            return "integral_number"
        return "non_integral_number"
    if isinstance(value, str):
        return "text"
    return "other"


def classify_cell(value: Any, spec: Mapping[str, Any]) -> tuple[str, str]:
    """Classify one normalized cell as registered / missing / unregistered.

    Returns ``(bucket, token)``. The token is only meaningful for the registered
    bucket; an unregistered value is never returned as text, so callers cannot
    echo it into a report. Blank cells arrive as ``None`` from the existing
    validator, which maps ``''``, ``'?'`` and ``-9`` sentinels to ``None``.

    Matching is representation-aware, mirroring the registered
    ``legacy_tokens_rejected`` rule: a column registered as a text vocabulary
    accepts only text cells, and a column registered as numeric ``0/1`` accepts
    only integral numbers. A numeric ``0`` in a text column is therefore an
    unregistered cell, not a silent match.
    """
    if value is None:
        return BUCKET_MISSING, ""

    if spec["source_representation"] == NUMERIC_BINARY_REPRESENTATION:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return BUCKET_UNREGISTERED, ""
        numeric = float(value)
        if not math.isfinite(numeric) or not numeric.is_integer():
            return BUCKET_UNREGISTERED, ""
        token = str(int(numeric))
    else:
        # Exact text match only: whitespace is never stripped, because a trimmed
        # match could silently accept a different source token.
        if not isinstance(value, str):
            return BUCKET_UNREGISTERED, ""
        token = value

    if token in spec["registered_token_set"]:
        return BUCKET_REGISTERED, token
    return BUCKET_UNREGISTERED, ""


def build_registered_coding_coverage(
    rows: Sequence[Mapping[str, Any]],
    column_specs: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Count registered / missing / unregistered cells per audited column."""
    total = len(rows)
    if total <= 0:
        raise RuntimeError("STOP: no parsed records to audit.")

    columns: dict[str, dict[str, Any]] = {}
    for column in AUDITED_COLUMNS:
        spec = column_specs[column]
        registered_tokens = set(spec["registered_tokens"])
        registered_counts: Counter[str] = Counter({token: 0 for token in spec["registered_tokens"]})
        missing = 0
        unregistered = 0
        distinct_unregistered: set[str] = set()
        shape_counts: Counter[str] = Counter({shape: 0 for shape in CELL_SHAPES})

        for row in rows:
            value = row.get(column)
            bucket, token = classify_cell(value, spec)
            if bucket == BUCKET_REGISTERED:
                registered_counts[token] += 1
            elif bucket == BUCKET_MISSING:
                missing += 1
            else:
                unregistered += 1
                distinct_unregistered.add(repr(value))
            if bucket != BUCKET_MISSING:
                shape_counts[source_cell_shape(value)] += 1

        registered_total = sum(registered_counts.values())
        if registered_total + missing + unregistered != total:
            raise RuntimeError(
                f"STOP: coding-coverage partition invariant violated for column '{column}'."
            )

        observed_tokens = [token for token in spec["registered_tokens"] if registered_counts[token] > 0]
        if unregistered > 0:
            coverage_status = COVERAGE_UNREGISTERED
        elif missing > 0:
            coverage_status = COVERAGE_ALL_OBSERVED_WITH_MISSING
        else:
            coverage_status = COVERAGE_ALL_CELLS

        columns[column] = {
            "column": column,
            "source_representation": spec["source_representation"],
            "registered_tokens": list(spec["registered_tokens"]),
            "registered_token_counts": {
                token: int(registered_counts[token]) for token in spec["registered_tokens"]
            },
            "registered_cell_count": int(registered_total),
            "missing_cell_count": int(missing),
            "unregistered_cell_count": int(unregistered),
            "distinct_unregistered_value_count": len(distinct_unregistered),
            "source_cell_shape_counts": {
                shape: int(shape_counts[shape]) for shape in CELL_SHAPES
            },
            "observed_registered_tokens": observed_tokens,
            "coding_coverage_status": coverage_status,
            "vocabulary_evidence_status": spec["vocabulary_evidence_status"],
            "codes_are_not_translated_or_recoded": True,
        }

    unregistered_columns = [
        column
        for column, entry in columns.items()
        if entry["unregistered_cell_count"] > 0
    ]
    missing_columns = [
        column for column, entry in columns.items() if entry["missing_cell_count"] > 0
    ]
    return {
        "columns": columns,
        "all_observed_cells_match_registered_vocabulary": not unregistered_columns,
        "columns_with_unregistered_tokens": unregistered_columns,
        "columns_with_missing_cells": missing_columns,
        "evidence_status": EVIDENCE_VERIFIED,
    }


def build_chest_pain_joint_census(
    rows: Sequence[Mapping[str, Any]],
    column_specs: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Build the predeclared four-way chest-pain joint census from parsed rows."""
    columns = CHEST_PAIN_DESCRIPTOR_COLUMNS
    specs = [column_specs[column] for column in columns]

    token_universe = list(product(*[spec["registered_tokens"] for spec in specs]))
    token_counts: Counter[str] = Counter(
        {CELL_KEY_SEPARATOR.join(combo): 0 for combo in token_universe}
    )

    code_universe = list(
        product(
            *[
                sorted({str(code) for code in spec["registered_token_to_code"].values()})
                for spec in specs
            ]
        )
    )
    code_counts: Counter[str] = Counter(
        {CELL_KEY_SEPARATOR.join(combo): 0 for combo in code_universe}
    )

    fully_registered = 0
    with_missing = 0
    with_unregistered = 0
    descriptor_counts: Counter[int] = Counter({0: 0, 1: 0, 2: 0, 3: 0, 4: 0})

    for row in rows:
        buckets: list[str] = []
        tokens: list[str] = []
        for column, spec in zip(columns, specs):
            bucket, token = classify_cell(row.get(column), spec)
            buckets.append(bucket)
            tokens.append(token)

        if BUCKET_MISSING in buckets:
            with_missing += 1
        if BUCKET_UNREGISTERED in buckets:
            with_unregistered += 1
        if any(bucket != BUCKET_REGISTERED for bucket in buckets):
            continue

        fully_registered += 1
        token_counts[CELL_KEY_SEPARATOR.join(tokens)] += 1

        codes = [
            str(spec["registered_token_to_code"][token]) for spec, token in zip(specs, tokens)
        ]
        code_counts[CELL_KEY_SEPARATOR.join(codes)] += 1
        descriptor_counts[sum(int(code) for code in codes)] += 1

    if sum(token_counts.values()) != fully_registered:
        raise RuntimeError("STOP: registered-token joint census invariant violated.")
    if sum(code_counts.values()) != fully_registered:
        raise RuntimeError("STOP: binary-code joint census invariant violated.")
    if sum(descriptor_counts.values()) != fully_registered:
        raise RuntimeError("STOP: descriptor-count distribution invariant violated.")
    if fully_registered > len(rows):
        raise RuntimeError("STOP: joint census exceeds the parsed row count.")
    not_censused = len(rows) - fully_registered
    # Every non-censused record carries at least one missing or unregistered cell,
    # so the two (possibly overlapping) flags must cover it.
    if with_missing + with_unregistered < not_censused:
        raise RuntimeError("STOP: non-censused records lack a missing/unregistered cell flag.")
    if with_missing > len(rows) or with_unregistered > len(rows):
        raise RuntimeError("STOP: missing/unregistered record counts exceed the row count.")

    return {
        "columns": list(columns),
        "cell_key_separator": CELL_KEY_SEPARATOR,
        "cell_key_column_order": list(columns),
        "cell_universe_definition": (
            "The registered-token census enumerates the full product of each column's registered "
            "tokens, so a zero cell means no record carried that registered token combination."
        ),
        "expected_registered_token_cell_count": len(token_universe),
        "registered_token_joint_census": [
            {"cell_key": key, "count": int(token_counts[key])}
            for key in sorted(token_counts)
        ],
        "expected_binary_code_cell_count": len(code_universe),
        "registered_binary_code_joint_census": [
            {"cell_key": key, "count": int(code_counts[key])}
            for key in sorted(code_counts)
        ],
        "census_record_count": int(fully_registered),
        "records_with_any_missing_cell": int(with_missing),
        "records_with_any_unregistered_cell": int(with_unregistered),
        "records_not_censused": int(not_censused),
        "descriptor_count_distribution": {
            str(count): int(descriptor_counts[count]) for count in range(5)
        },
        "records_with_two_or_more_registered_descriptors": int(
            sum(descriptor_counts[count] for count in range(2, 5))
        ),
        "descriptor_count_basis": (
            "REGISTERED_DICTIONARY_BINARY_CODES_CODE_1_TREATED_AS_DESCRIPTOR_PRESENT_"
            "DIRECTION_NOT_OWNER_CONFIRMED"
        ),
        "census_is_direction_free": True,
        "descriptor_count_uses_registered_codes_only": True,
        "direction_evidence_status_by_column": {
            spec["column"]: spec["vocabulary_evidence_status"] for spec in specs
        },
        "evidence_status": EVIDENCE_VERIFIED,
    }


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------


def _governance_context(auth_manifest: Mapping[str, Any]) -> dict[str, Any]:
    da_a1 = auth_manifest["datasets"]["DA-A1"]
    return {
        "governance_decision_id": auth_manifest.get("governance_decision_id"),
        "workflow_status": auth_manifest.get("workflow_status"),
        "gate_pt_status": auth_manifest.get("gate_pt_status"),
        "supervisor_review_status": (
            auth_manifest.get("supervisor_review_status") or "NOT_RECORDED_IN_LOCAL_MANIFEST"
        ),
        "supervisor_approval_claimed": auth_manifest.get("supervisor_approval_claimed"),
        "model_fitting_authorized": auth_manifest.get("model_fitting_authorized"),
        "feature_selection_authorized": auth_manifest.get("feature_selection_authorized"),
        "hyperparameter_tuning_authorized": auth_manifest.get("hyperparameter_tuning_authorized"),
        "performance_evaluation_authorized": auth_manifest.get("performance_evaluation_authorized"),
        "calibration_authorized": auth_manifest.get("calibration_authorized"),
        "shap_or_lime_authorized": auth_manifest.get("shap_or_lime_authorized"),
        "audited_dataset_id": DATASET_ID,
        "dataset_authorization_status": da_a1.get("authorization_status"),
        "authorized_by": da_a1.get("authorized_by"),
        "authorized_date": da_a1.get("authorized_date"),
        "responsible_acquirer": da_a1.get("responsible_acquirer"),
        "audit_reviewer": da_a1.get("audit_reviewer"),
        "environment": da_a1.get("environment"),
        "d046_scope_determination": "WITHIN_D046_READ_ONLY_AUDIT_SCOPE",
        "d046_scope_basis": (
            "D-046 authorizes local read-only auditing of the named DA-A1 workbook: its columns, "
            "data types, codings, missingness and documented feature-count discrepancy. Aggregate "
            "token-frequency counts, registered-vocabulary coverage and a four-way joint count are "
            "descriptive coding checks on the same authorized file, with no fitting, selection, "
            "tuning, evaluation, calibration or explanation."
        ),
        "d046_scope_requires_maintainer_judgement_not_granted_by_code": True,
        "dataset_used_for_model_fitting_hyperparameter_selection_threshold_selection_"
        "calibration_or_prediction_based_evaluation": False,
    }


def build_source_semantics_report(
    *,
    rows: Sequence[Mapping[str, Any]],
    source_filename: str,
    source_relative_path: str,
    registered_semantics: Mapping[str, Any],
    governance_context: Mapping[str, Any],
    authorized_files: Sequence[str],
    excluded_unapproved_files: Sequence[str],
    byte_identity_snapshots: Sequence[Mapping[str, Any]],
    validator_row_count: int,
    is_synthetic_fixture_run: bool,
) -> dict[str, Any]:
    """Assemble the aggregate-only source-semantics report from already-parsed rows."""
    coverage = build_registered_coding_coverage(rows, registered_semantics["columns"])
    census = build_chest_pain_joint_census(rows, registered_semantics["columns"])

    text_columns = coverage["columns"]
    prior_claim_columns = list(TEXT_BINARY_COLUMNS)
    prior_claim_unregistered = any(
        text_columns[column]["unregistered_cell_count"] > 0 for column in prior_claim_columns
    )
    prior_claim_missing = any(
        text_columns[column]["missing_cell_count"] > 0 for column in prior_claim_columns
    )
    if prior_claim_unregistered:
        prior_claim_result = "NOT_CONSISTENT_WITH_PRIOR_CLAIM"
    elif prior_claim_missing:
        prior_claim_result = "CONSISTENT_WITH_PRIOR_VOCABULARY_BUT_MISSING_CELLS_OBSERVED"
    else:
        prior_claim_result = "CONSISTENT_WITH_PRIOR_CLAIM"

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
            "threshold_selected": False,
            "pooling_or_dataset_concatenation_performed": False,
            "statistical_test_performed": False,
            "patient_identity_inferred": False,
            "source_labels_translated": False,
            "source_files_modified": False,
            "values_imputed_or_recoded": False,
            "unregistered_token_text_emitted": False,
            "patient_level_rows_emitted": 0,
            "supervisor_approval_claimed": False,
            "gate_pt_bypassed": False,
            "evidence_status": EVIDENCE_VERIFIED,
        },
        "scope_and_evidence_boundary": {
            "dataset_id": DATASET_ID,
            "audited_columns": list(AUDITED_COLUMNS),
            "text_binary_columns": list(TEXT_BINARY_COLUMNS),
            "chest_pain_descriptor_columns": list(CHEST_PAIN_DESCRIPTOR_COLUMNS),
            "parsed_source_files": [source_filename],
            "workbook_validator_reused": "audit_uci_412_or_411_workbook",
            "validator_reported_row_count": int(validator_row_count),
            "rows_available_to_this_audit": int(len(rows)),
            "columns_outside_predeclared_scope_analysed": False,
            "uci_411_or_uci_412_cross_analysis_performed": False,
            "uci_45_cross_family_analysis_performed": False,
            "execution_status": (
                "SYNTHETIC_FIXTURE_EXECUTION_COMPLETED_TEST_ONLY"
                if is_synthetic_fixture_run
                else "LOCAL_READ_ONLY_EXECUTION_COMPLETED"
            ),
            "new_evidence_generated": (
                "SYNTHETIC_TEST_FIXTURES_ONLY"
                if is_synthetic_fixture_run
                else "LOCAL_AGGREGATE_EVIDENCE_GENERATED"
            ),
            "evidence_review_status": (
                "SYNTHETIC_TEST_ONLY_NOT_EVIDENCE"
                if is_synthetic_fixture_run
                else "PENDING_HUMAN_PRIVACY_AND_SCIENTIFIC_REVIEW"
            ),
            "scientific_claim_made": False,
            "evidence_status": EVIDENCE_VERIFIED,
        },
        "source_semantics": {
            "dataset_id": DATASET_ID,
            "source_filename": source_filename,
            "source_relative_path": source_relative_path,
            "audited_row_count": int(len(rows)),
            "registered_dictionary_reference": {
                "schema_id": registered_semantics["schema_id"],
                "schema_version": registered_semantics["schema_version"],
                "relative_path": registered_semantics["relative_path"],
                "sha256": registered_semantics["sha256"],
                "read_only": True,
                "modified_by_this_audit": False,
            },
            "registered_coding_coverage": coverage,
            "four_field_chest_pain_joint_census": census,
            "bundled_source_documentation_review": {
                "status": BUNDLED_DOCUMENTATION_STATUS,
                "authorized_files_for_da_a1": sorted(authorized_files),
                "excluded_unapproved_files_for_da_a1": sorted(excluded_unapproved_files),
                "documentation_file_authorized": False,
                "archive_or_document_member_opened": False,
                "documentation_file_inspected": False,
                "required_additional_authorization": BUNDLED_DOCUMENTATION_REQUIREMENT,
                "enforcing_guard": (
                    "research.audit.provenance.validate_provenance_manifest rejects any file in the "
                    "dataset directory that is not in the authorized file list, so a bundled "
                    "documentation member cannot be present during an authorized run."
                ),
                "evidence_status": EVIDENCE_VERIFIED,
            },
        },
        "input_integrity_and_privacy": {
            "git_ignore_verified": True,
            "byte_identity_guard_file_count": len(byte_identity_snapshots),
            "byte_identity_snapshots": [dict(snapshot) for snapshot in byte_identity_snapshots],
            "registered_dictionary_sha256": registered_semantics["sha256"],
            "privacy_controls": (
                "STRICT_ALLOWLISTED_AGGREGATE_SCHEMA_AS_PRIMARY_CONTROL_PLUS_SECONDARY_ROW_PATTERN_"
                "AND_FINGERPRINT_SCANNER_PLUS_REGISTERED_TOKEN_ONLY_EMISSION_HUMAN_REVIEW_REQUIRED_"
                "BEFORE_SHARING"
            ),
            "evidence_status": EVIDENCE_VERIFIED,
        },
        "evidence_limitations": [dict(item) for item in EVIDENCE_LIMITATIONS],
        "audit_summary": {
            "registered_coverage_under_test": (
                "DOC15_U4_CLAIM_ALL_CELLS_IN_THE_SIX_TEXT_BINARY_COLUMNS_ACCEPTED_BY_THE_"
                "REGISTERED_VOCABULARY"
            ),
            "registered_coverage_file_level_result": prior_claim_result,
            "text_binary_columns_with_unregistered_tokens": [
                column
                for column in prior_claim_columns
                if text_columns[column]["unregistered_cell_count"] > 0
            ],
            "chest_pain_census_record_count": int(census["census_record_count"]),
            "records_with_two_or_more_registered_descriptors": int(
                census["records_with_two_or_more_registered_descriptors"]
            ),
            "bundled_documentation_status": BUNDLED_DOCUMENTATION_STATUS,
            "questions_advanced": ["U-4", "U-5b"],
            "questions_not_resolved": ["U-5a", "U-6"],
            "human_review_required_before_any_scientific_use": True,
            "evidence_review_status": (
                "SYNTHETIC_TEST_ONLY_NOT_EVIDENCE"
                if is_synthetic_fixture_run
                else "PENDING_HUMAN_PRIVACY_AND_SCIENTIFIC_REVIEW"
            ),
            "scientific_claim_made": False,
            "evidence_status": EVIDENCE_VERIFIED,
        },
    }


# ---------------------------------------------------------------------------
# Strict aggregate schema validation
# ---------------------------------------------------------------------------


def _assert_str_list(value: Any, *, context: str) -> None:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"Strict report schema violation at '{context}': expected list[str].")


def _validate_coverage_columns(payload: Any, *, context: str) -> None:
    if not isinstance(payload, dict) or list(payload.keys()) != list(AUDITED_COLUMNS):
        raise ValueError(
            f"Strict report schema violation at '{context}': coverage columns must be exactly "
            f"{list(AUDITED_COLUMNS)}."
        )
    for column in AUDITED_COLUMNS:
        entry = payload[column]
        assert_exact_keys(
            entry,
            {
                "column",
                "source_representation",
                "registered_tokens",
                "registered_token_counts",
                "registered_cell_count",
                "missing_cell_count",
                "unregistered_cell_count",
                "distinct_unregistered_value_count",
                "source_cell_shape_counts",
                "observed_registered_tokens",
                "coding_coverage_status",
                "vocabulary_evidence_status",
                "codes_are_not_translated_or_recoded",
            },
            context=f"{context}.{column}",
        )
        if entry["column"] != column:
            raise ValueError(f"Strict report schema violation at '{context}.{column}': column mismatch.")
        _assert_str_list(entry["registered_tokens"], context=f"{context}.{column}.registered_tokens")
        _assert_str_list(
            entry["observed_registered_tokens"], context=f"{context}.{column}.observed_tokens"
        )
        counts = entry["registered_token_counts"]
        if not isinstance(counts, dict) or set(counts) != set(entry["registered_tokens"]):
            raise ValueError(
                f"Strict report schema violation at '{context}.{column}': token counts must cover "
                "exactly the registered tokens."
            )
        for token, count in counts.items():
            assert_int_not_bool(count, context=f"{context}.{column}.registered_token_counts.{token}")
            if count < 0:
                raise ValueError(f"Strict report schema violation at '{context}.{column}': negative count.")
        for field in (
            "registered_cell_count",
            "missing_cell_count",
            "unregistered_cell_count",
            "distinct_unregistered_value_count",
        ):
            assert_int_not_bool(entry[field], context=f"{context}.{column}.{field}")
            if entry[field] < 0:
                raise ValueError(f"Strict report schema violation at '{context}.{column}.{field}'.")
        if entry["registered_cell_count"] != sum(counts.values()):
            raise ValueError(
                f"Strict report schema violation at '{context}.{column}': registered cell count "
                "does not equal the token-count sum."
            )
        if entry["distinct_unregistered_value_count"] > entry["unregistered_cell_count"]:
            raise ValueError(
                f"Strict report schema violation at '{context}.{column}': distinct unregistered "
                "values exceed the unregistered cell count."
            )
        shapes = entry["source_cell_shape_counts"]
        if not isinstance(shapes, dict) or list(shapes.keys()) != list(CELL_SHAPES):
            raise ValueError(
                f"Strict report schema violation at '{context}.{column}': source cell shapes "
                f"must be exactly {list(CELL_SHAPES)}."
            )
        for shape, count in shapes.items():
            assert_int_not_bool(
                count, context=f"{context}.{column}.source_cell_shape_counts.{shape}"
            )
            if count < 0:
                raise ValueError(
                    f"Strict report schema violation at '{context}.{column}': negative "
                    f"'{shape}' cell count."
                )
        if sum(shapes.values()) != (
            entry["registered_cell_count"] + entry["unregistered_cell_count"]
        ):
            raise ValueError(
                f"Strict report schema violation at '{context}.{column}': source cell shapes "
                "must account for every observed (non-missing) cell."
            )
        if entry["coding_coverage_status"] not in (
            COVERAGE_ALL_CELLS,
            COVERAGE_ALL_OBSERVED_WITH_MISSING,
            COVERAGE_UNREGISTERED,
        ):
            raise ValueError(
                f"Strict report schema violation at '{context}.{column}': unknown coding coverage status."
            )
        if entry["source_representation"] not in (
            TEXT_VOCABULARY_REPRESENTATION,
            NUMERIC_BINARY_REPRESENTATION,
        ):
            raise ValueError(
                f"Strict report schema violation at '{context}.{column}': unknown source representation."
            )
        if entry["codes_are_not_translated_or_recoded"] is not True:
            raise ValueError(
                f"Strict report schema violation at '{context}.{column}': codes must not be recoded."
            )


def _validate_census_cells(cells: Any, *, expected: int, context: str) -> int:
    if not isinstance(cells, list) or len(cells) != expected:
        raise ValueError(
            f"Strict report schema violation at '{context}': expected {expected} census cells."
        )
    total = 0
    for index, cell in enumerate(cells):
        assert_exact_keys(cell, {"cell_key", "count"}, context=f"{context}[{index}]")
        if not isinstance(cell["cell_key"], str) or CELL_KEY_SEPARATOR not in cell["cell_key"]:
            raise ValueError(f"Strict report schema violation at '{context}[{index}].cell_key'.")
        assert_int_not_bool(cell["count"], context=f"{context}[{index}].count")
        if cell["count"] < 0:
            raise ValueError(f"Strict report schema violation at '{context}[{index}].count'.")
        total += cell["count"]
    keys = [cell["cell_key"] for cell in cells]
    if len(set(keys)) != len(keys):
        raise ValueError(f"Strict report schema violation at '{context}': duplicate cell keys.")
    return total


def validate_uci412_source_semantics_report_schema(report: Mapping[str, Any]) -> None:
    """Reject any report that is not an allowlisted, aggregate-only source-semantics report."""
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
            "source_semantics",
            "input_integrity_and_privacy",
            "evidence_limitations",
            "audit_summary",
        },
        context="report",
    )
    if report["report_type"] != REPORT_TYPE or report["status_label"] != STATUS_LABEL:
        raise ValueError("Strict report schema violation: unexpected report type or status label.")
    if report["execution_mode"] not in (
        "AUTHORIZED_READ_ONLY_LOCAL_AUDIT",
        "SYNTHETIC_FIXTURE_TEST",
    ):
        raise ValueError("Strict report schema violation: unknown execution mode.")
    if report["synthetic_disclaimer"] not in (
        "REAL_LOCAL_AGGREGATE_READ_ONLY_AUDIT_NOT_MODEL_OR_CLINICAL_EVIDENCE",
        "SYNTHETIC_SOFTWARE_TEST_FIXTURES_ONLY_NOT_MEDICAL_EVIDENCE",
    ):
        raise ValueError("Strict report schema violation: unknown synthetic disclaimer label.")

    certification = report["safety_and_scope_certification"]
    assert_exact_keys(
        certification,
        {
            "model_fitting_performed",
            "feature_selection_performed",
            "hyperparameter_tuning_performed",
            "performance_evaluation_performed",
            "calibration_performed",
            "shap_or_lime_computed",
            "threshold_selected",
            "pooling_or_dataset_concatenation_performed",
            "statistical_test_performed",
            "patient_identity_inferred",
            "source_labels_translated",
            "source_files_modified",
            "values_imputed_or_recoded",
            "unregistered_token_text_emitted",
            "patient_level_rows_emitted",
            "supervisor_approval_claimed",
            "gate_pt_bypassed",
            "evidence_status",
        },
        context="safety_and_scope_certification",
    )
    for flag, value in certification.items():
        if flag in ("patient_level_rows_emitted", "evidence_status"):
            continue
        if value is not False:
            raise ValueError(
                f"Strict report schema violation: certification flag '{flag}' must be false."
            )
    assert_int_not_bool(
        certification["patient_level_rows_emitted"],
        context="safety_and_scope_certification.patient_level_rows_emitted",
    )
    if certification["patient_level_rows_emitted"] != 0:
        raise ValueError("Strict report schema violation: patient-level rows must never be emitted.")

    governance = report["governance_and_authorization"]
    assert_exact_keys(
        governance,
        {
            "governance_decision_id",
            "workflow_status",
            "gate_pt_status",
            "supervisor_review_status",
            "supervisor_approval_claimed",
            "model_fitting_authorized",
            "feature_selection_authorized",
            "hyperparameter_tuning_authorized",
            "performance_evaluation_authorized",
            "calibration_authorized",
            "shap_or_lime_authorized",
            "audited_dataset_id",
            "dataset_authorization_status",
            "authorized_by",
            "authorized_date",
            "responsible_acquirer",
            "audit_reviewer",
            "environment",
            "d046_scope_determination",
            "d046_scope_basis",
            "d046_scope_requires_maintainer_judgement_not_granted_by_code",
            "dataset_used_for_model_fitting_hyperparameter_selection_threshold_selection_"
            "calibration_or_prediction_based_evaluation",
        },
        context="governance_and_authorization",
    )
    if governance["governance_decision_id"] != "D-046":
        raise ValueError("Strict report schema violation: governance decision must be D-046.")
    if governance["gate_pt_status"] != "CLOSED_REQUIRES_SUPERVISOR_SIGNOFF_P3":
        raise ValueError("Strict report schema violation: Gate PT must be recorded as CLOSED.")
    for flag in (
        "supervisor_approval_claimed",
        "model_fitting_authorized",
        "feature_selection_authorized",
        "hyperparameter_tuning_authorized",
        "performance_evaluation_authorized",
        "calibration_authorized",
        "shap_or_lime_authorized",
        "dataset_used_for_model_fitting_hyperparameter_selection_threshold_selection_"
        "calibration_or_prediction_based_evaluation",
    ):
        if governance[flag] is not False:
            raise ValueError(f"Strict report schema violation: '{flag}' must be false.")
    if governance["audited_dataset_id"] != DATASET_ID:
        raise ValueError("Strict report schema violation: audited dataset must be DA-A1.")

    boundary = report["scope_and_evidence_boundary"]
    assert_exact_keys(
        boundary,
        {
            "dataset_id",
            "audited_columns",
            "text_binary_columns",
            "chest_pain_descriptor_columns",
            "parsed_source_files",
            "workbook_validator_reused",
            "validator_reported_row_count",
            "rows_available_to_this_audit",
            "columns_outside_predeclared_scope_analysed",
            "uci_411_or_uci_412_cross_analysis_performed",
            "uci_45_cross_family_analysis_performed",
            "execution_status",
            "new_evidence_generated",
            "evidence_review_status",
            "scientific_claim_made",
            "evidence_status",
        },
        context="scope_and_evidence_boundary",
    )
    if boundary["audited_columns"] != list(AUDITED_COLUMNS):
        raise ValueError("Strict report schema violation: audited columns must match the predeclared set.")
    if boundary["parsed_source_files"] != [AUTHORIZED_WORKBOOK_FILENAME]:
        raise ValueError(
            "Strict report schema violation: exactly the authorized DA-A1 workbook may be parsed."
        )
    for flag in (
        "columns_outside_predeclared_scope_analysed",
        "uci_411_or_uci_412_cross_analysis_performed",
        "uci_45_cross_family_analysis_performed",
        "scientific_claim_made",
    ):
        if boundary[flag] is not False:
            raise ValueError(f"Strict report schema violation: '{flag}' must be false.")
    if (boundary["execution_status"], boundary["new_evidence_generated"], boundary["evidence_review_status"]) not in (
        (
            "SYNTHETIC_FIXTURE_EXECUTION_COMPLETED_TEST_ONLY",
            "SYNTHETIC_TEST_FIXTURES_ONLY",
            "SYNTHETIC_TEST_ONLY_NOT_EVIDENCE",
        ),
        (
            "LOCAL_READ_ONLY_EXECUTION_COMPLETED",
            "LOCAL_AGGREGATE_EVIDENCE_GENERATED",
            "PENDING_HUMAN_PRIVACY_AND_SCIENTIFIC_REVIEW",
        ),
    ):
        raise ValueError(
            "Strict report schema violation: execution/new-evidence/review statuses must be one "
            "consistent, allowlisted triple."
        )
    if boundary["workbook_validator_reused"] != "audit_uci_412_or_411_workbook":
        raise ValueError(
            "Strict report schema violation: the audit must reuse the existing workbook validator."
        )
    assert_int_not_bool(
        boundary["validator_reported_row_count"], context="scope.validator_reported_row_count"
    )
    assert_int_not_bool(
        boundary["rows_available_to_this_audit"], context="scope.rows_available_to_this_audit"
    )
    if boundary["validator_reported_row_count"] != boundary["rows_available_to_this_audit"]:
        raise ValueError(
            "Strict report schema violation: validator row count and audited row count disagree."
        )

    semantics = report["source_semantics"]
    assert_exact_keys(
        semantics,
        {
            "dataset_id",
            "source_filename",
            "source_relative_path",
            "audited_row_count",
            "registered_dictionary_reference",
            "registered_coding_coverage",
            "four_field_chest_pain_joint_census",
            "bundled_source_documentation_review",
        },
        context="source_semantics",
    )
    if semantics["dataset_id"] != DATASET_ID:
        raise ValueError("Strict report schema violation: source_semantics dataset must be DA-A1.")
    if semantics["source_filename"] != AUTHORIZED_WORKBOOK_FILENAME:
        raise ValueError("Strict report schema violation: unexpected source filename.")
    assert_int_not_bool(semantics["audited_row_count"], context="source_semantics.audited_row_count")

    dictionary = semantics["registered_dictionary_reference"]
    assert_exact_keys(
        dictionary,
        {
            "schema_id",
            "schema_version",
            "relative_path",
            "sha256",
            "read_only",
            "modified_by_this_audit",
        },
        context="source_semantics.registered_dictionary_reference",
    )
    if dictionary["schema_id"] != EXPECTED_DICTIONARY_SCHEMA_ID:
        raise ValueError("Strict report schema violation: unexpected dictionary schema id.")
    if dictionary["relative_path"] != FEATURE_DICTIONARY_RELATIVE_PATH:
        raise ValueError("Strict report schema violation: unexpected dictionary path.")
    if len(str(dictionary["sha256"])) != 64:
        raise ValueError("Strict report schema violation: dictionary SHA-256 must be 64 hex characters.")
    if dictionary["read_only"] is not True or dictionary["modified_by_this_audit"] is not False:
        raise ValueError("Strict report schema violation: dictionary must be read-only and unmodified.")

    coverage = semantics["registered_coding_coverage"]
    assert_exact_keys(
        coverage,
        {
            "columns",
            "all_observed_cells_match_registered_vocabulary",
            "columns_with_unregistered_tokens",
            "columns_with_missing_cells",
            "evidence_status",
        },
        context="source_semantics.registered_coding_coverage",
    )
    _validate_coverage_columns(
        coverage["columns"], context="source_semantics.registered_coding_coverage.columns"
    )
    for column, entry in coverage["columns"].items():
        if (
            entry["registered_cell_count"]
            + entry["missing_cell_count"]
            + entry["unregistered_cell_count"]
            != semantics["audited_row_count"]
        ):
            raise ValueError(
                f"Strict report schema violation: column '{column}' cell partition does not "
                "match the audited row count."
            )
    _assert_str_list(
        coverage["columns_with_unregistered_tokens"],
        context="source_semantics.registered_coding_coverage.columns_with_unregistered_tokens",
    )
    _assert_str_list(
        coverage["columns_with_missing_cells"],
        context="source_semantics.registered_coding_coverage.columns_with_missing_cells",
    )
    if coverage["all_observed_cells_match_registered_vocabulary"] is not (
        not coverage["columns_with_unregistered_tokens"]
    ):
        raise ValueError(
            "Strict report schema violation: "
            "all_observed_cells_match_registered_vocabulary disagrees with the "
            "unregistered-token column list."
        )

    census = semantics["four_field_chest_pain_joint_census"]
    assert_exact_keys(
        census,
        {
            "columns",
            "cell_key_separator",
            "cell_key_column_order",
            "cell_universe_definition",
            "expected_registered_token_cell_count",
            "registered_token_joint_census",
            "expected_binary_code_cell_count",
            "registered_binary_code_joint_census",
            "census_record_count",
            "records_with_any_missing_cell",
            "records_with_any_unregistered_cell",
            "records_not_censused",
            "descriptor_count_distribution",
            "records_with_two_or_more_registered_descriptors",
            "descriptor_count_basis",
            "census_is_direction_free",
            "descriptor_count_uses_registered_codes_only",
            "direction_evidence_status_by_column",
            "evidence_status",
        },
        context="source_semantics.four_field_chest_pain_joint_census",
    )
    if census["columns"] != list(CHEST_PAIN_DESCRIPTOR_COLUMNS):
        raise ValueError("Strict report schema violation: unexpected chest-pain column set.")
    for field in ("expected_registered_token_cell_count", "expected_binary_code_cell_count"):
        assert_int_not_bool(census[field], context=f"census.{field}")
    token_total = _validate_census_cells(
        census["registered_token_joint_census"],
        expected=census["expected_registered_token_cell_count"],
        context="census.registered_token_joint_census",
    )
    code_total = _validate_census_cells(
        census["registered_binary_code_joint_census"],
        expected=census["expected_binary_code_cell_count"],
        context="census.registered_binary_code_joint_census",
    )
    for field in (
        "census_record_count",
        "records_with_any_missing_cell",
        "records_with_any_unregistered_cell",
        "records_not_censused",
        "records_with_two_or_more_registered_descriptors",
    ):
        assert_int_not_bool(census[field], context=f"census.{field}")
        if census[field] < 0:
            raise ValueError(f"Strict report schema violation at 'census.{field}'.")
    if not token_total == code_total == census["census_record_count"]:
        raise ValueError(
            "Strict report schema violation: the two census totals and the census record count "
            "must agree."
        )
    if census["census_record_count"] + census["records_not_censused"] != semantics["audited_row_count"]:
        raise ValueError(
            "Strict report schema violation: censused plus non-censused records must equal the "
            "audited row count."
        )
    distribution = census["descriptor_count_distribution"]
    if not isinstance(distribution, dict) or list(distribution.keys()) != [str(i) for i in range(5)]:
        raise ValueError("Strict report schema violation: descriptor distribution keys must be 0-4.")
    for key, value in distribution.items():
        assert_int_not_bool(value, context=f"census.descriptor_count_distribution.{key}")
        if value < 0:
            raise ValueError("Strict report schema violation: negative descriptor count.")
    if sum(distribution.values()) != census["census_record_count"]:
        raise ValueError(
            "Strict report schema violation: descriptor distribution must sum to the censused records."
        )
    if census["records_with_two_or_more_registered_descriptors"] != sum(
        distribution[str(index)] for index in range(2, 5)
    ):
        raise ValueError(
            "Strict report schema violation: multi-descriptor count disagrees with the distribution."
        )
    if census["census_is_direction_free"] is not True:
        raise ValueError(
            "Strict report schema violation: the registered-token census must be marked "
            "direction-free."
        )
    if census["descriptor_count_uses_registered_codes_only"] is not True:
        raise ValueError(
            "Strict report schema violation: descriptor counts must use registered codes only."
        )
    if set(census["direction_evidence_status_by_column"]) != set(CHEST_PAIN_DESCRIPTOR_COLUMNS):
        raise ValueError(
            "Strict report schema violation: direction evidence must be recorded per chest-pain column."
        )

    documentation = semantics["bundled_source_documentation_review"]
    assert_exact_keys(
        documentation,
        {
            "status",
            "authorized_files_for_da_a1",
            "excluded_unapproved_files_for_da_a1",
            "documentation_file_authorized",
            "archive_or_document_member_opened",
            "documentation_file_inspected",
            "required_additional_authorization",
            "enforcing_guard",
            "evidence_status",
        },
        context="source_semantics.bundled_source_documentation_review",
    )
    if documentation["status"] != BUNDLED_DOCUMENTATION_STATUS:
        raise ValueError(
            "Strict report schema violation: bundled documentation status must record that it was "
            "not performed and is not authorized."
        )
    if documentation["documentation_file_authorized"] is not False:
        raise ValueError(
            "Strict report schema violation: the bundled documentation is not authorized by DA-A1."
        )
    if documentation["archive_or_document_member_opened"] is not False or (
        documentation["documentation_file_inspected"] is not False
    ):
        raise ValueError(
            "Strict report schema violation: no documentation member may be opened by this audit."
        )
    if sorted(documentation["authorized_files_for_da_a1"]) != [AUTHORIZED_WORKBOOK_FILENAME]:
        raise ValueError(
            "Strict report schema violation: DA-A1 authorizes exactly the workbook file."
        )

    integrity = report["input_integrity_and_privacy"]
    assert_exact_keys(
        integrity,
        {
            "git_ignore_verified",
            "byte_identity_guard_file_count",
            "byte_identity_snapshots",
            "registered_dictionary_sha256",
            "privacy_controls",
            "evidence_status",
        },
        context="input_integrity_and_privacy",
    )
    assert_int_not_bool(
        integrity["byte_identity_guard_file_count"],
        context="input_integrity_and_privacy.byte_identity_guard_file_count",
    )
    snapshots = integrity["byte_identity_snapshots"]
    if not isinstance(snapshots, list) or len(snapshots) != integrity["byte_identity_guard_file_count"]:
        raise ValueError(
            "Strict report schema violation: byte-identity snapshot count mismatch."
        )
    for index, snapshot in enumerate(snapshots):
        assert_exact_keys(
            snapshot,
            {
                "filename",
                "relative_path",
                "pre_sha256",
                "post_sha256",
                "size_bytes",
                "byte_identical",
            },
            context=f"input_integrity_and_privacy.byte_identity_snapshots[{index}]",
        )
        if snapshot["byte_identical"] is not True or snapshot["pre_sha256"] != snapshot["post_sha256"]:
            raise ValueError(
                "Strict report schema violation: every source file must be byte-identical."
            )
    if integrity["registered_dictionary_sha256"] != dictionary["sha256"]:
        raise ValueError(
            "Strict report schema violation: dictionary SHA-256 mismatch between report sections."
        )

    limitations = report["evidence_limitations"]
    if not isinstance(limitations, list) or not limitations:
        raise ValueError("Strict report schema violation: evidence limitations must be recorded.")
    for index, item in enumerate(limitations):
        assert_exact_keys(item, {"id", "statement"}, context=f"evidence_limitations[{index}]")

    summary = report["audit_summary"]
    assert_exact_keys(
        summary,
        {
            "registered_coverage_under_test",
            "registered_coverage_file_level_result",
            "text_binary_columns_with_unregistered_tokens",
            "chest_pain_census_record_count",
            "records_with_two_or_more_registered_descriptors",
            "bundled_documentation_status",
            "questions_advanced",
            "questions_not_resolved",
            "human_review_required_before_any_scientific_use",
            "evidence_review_status",
            "scientific_claim_made",
            "evidence_status",
        },
        context="audit_summary",
    )
    if summary["registered_coverage_file_level_result"] not in (
        "CONSISTENT_WITH_PRIOR_CLAIM",
        "CONSISTENT_WITH_PRIOR_VOCABULARY_BUT_MISSING_CELLS_OBSERVED",
        "NOT_CONSISTENT_WITH_PRIOR_CLAIM",
    ):
        raise ValueError(
            "Strict report schema violation: unexpected registered coverage result label."
        )
    if summary["chest_pain_census_record_count"] != census["census_record_count"]:
        raise ValueError("Strict report schema violation: census record count mismatch.")
    if summary["scientific_claim_made"] is not False:
        raise ValueError("Strict report schema violation: no scientific claim may be made.")


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def _md_cell(value: Any) -> str:
    return str(value).replace("|", "\\|")


def render_uci412_source_semantics_markdown(report: Mapping[str, Any]) -> str:
    """Render a metadata-only, aggregate-only Markdown summary of the audit."""
    governance = report["governance_and_authorization"]
    boundary = report["scope_and_evidence_boundary"]
    semantics = report["source_semantics"]
    coverage = semantics["registered_coding_coverage"]
    census = semantics["four_field_chest_pain_joint_census"]
    documentation = semantics["bundled_source_documentation_review"]
    summary = report["audit_summary"]
    dictionary = semantics["registered_dictionary_reference"]

    lines: list[str] = [
        "# CardioAssist AI — UCI-412 Source-Semantics Read-Only Audit (DA-A1)",
        "",
        "> Aggregate counts only. No patient-level row, value, identifier or fingerprint appears in "
        "this report. No model was fitted, selected, tuned, calibrated, evaluated or explained.",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Execution mode | `{_md_cell(report['execution_mode'])}` |",
        f"| Status label | `{_md_cell(report['status_label'])}` |",
        f"| Governance decision | `{_md_cell(governance['governance_decision_id'])}` "
        f"(`{_md_cell(governance['workflow_status'])}`) |",
        f"| Gate PT | `{_md_cell(governance['gate_pt_status'])}` |",
        f"| Supervisor approval claimed | `{_md_cell(governance['supervisor_approval_claimed'])}` |",
        f"| D-046 scope determination | `{_md_cell(governance['d046_scope_determination'])}` |",
        f"| Audited dataset | `{_md_cell(semantics['dataset_id'])}` "
        f"(`{_md_cell(semantics['source_filename'])}`) |",
        f"| Records audited | `{semantics['audited_row_count']}` |",
        f"| Registered dictionary | `{_md_cell(dictionary['schema_id'])}` "
        f"v`{_md_cell(dictionary['schema_version'])}` |",
        f"| Dictionary SHA-256 | `{_md_cell(dictionary['sha256'])}` |",
        f"| Execution status | `{_md_cell(boundary['execution_status'])}` |",
        f"| New evidence generated | `{_md_cell(boundary['new_evidence_generated'])}` |",
        f"| Evidence review status | `{_md_cell(boundary['evidence_review_status'])}` |",
        "",
        "## 1. Registered coding coverage (predeclared audited columns)",
        "",
        "The six text-binary columns (`Sex`, `DLP`, `Atypical`, `Nonanginal`, `Exertional CP`, "
        "`Dyspnea`) are the doc-15 U-4 set; `Typical Chest Pain` is added because it participates "
        "in the four-way chest-pain census in section 2. Matching is representation-aware: a text "
        "column accepts only text cells and a numeric `0/1` column accepts only integral numbers. "
        "Registered tokens are reproduced exactly; an unregistered source value is counted only "
        "and its text is never emitted.",
        "",
        "| Column | Representation | Registered tokens observed | Missing cells | Unregistered cells | "
        "Distinct unregistered values | Status |",
        "|---|---|---|---|---|---|---|",
    ]
    for column in AUDITED_COLUMNS:
        entry = coverage["columns"][column]
        observed = ", ".join(
            f"`{_md_cell(token)}`={entry['registered_token_counts'][token]}"
            for token in entry["observed_registered_tokens"]
        ) or "none"
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{_md_cell(column)}`",
                    f"`{_md_cell(entry['source_representation'])}`",
                    observed,
                    str(entry["missing_cell_count"]),
                    str(entry["unregistered_cell_count"]),
                    str(entry["distinct_unregistered_value_count"]),
                    f"`{_md_cell(entry['coding_coverage_status'])}`",
                ]
            )
            + " |"
        )
    lines += [
        "",
        "Cell shapes (observed, non-missing cells only — no values are recorded):",
        "",
    ]
    for column in AUDITED_COLUMNS:
        shapes = coverage["columns"][column]["source_cell_shape_counts"]
        lines.append(
            f"- `{_md_cell(column)}`: "
            + ", ".join(f"{shape}={shapes[shape]}" for shape in CELL_SHAPES if shapes[shape] > 0)
        )
    lines += [
        "",
        f"- All observed cells match the registered vocabulary "
        f"(missing cells permitted): "
        f"`{coverage['all_observed_cells_match_registered_vocabulary']}`",
        f"- Columns with unregistered tokens: "
        f"`{_md_cell(coverage['columns_with_unregistered_tokens'])}`",
        f"- Doc-15 U-4 prior claim, file-level result: "
        f"`{_md_cell(summary['registered_coverage_file_level_result'])}`",
        "",
        "## 2. Four-field chest-pain joint census",
        "",
        f"Columns in key order: `{_md_cell(' / '.join(census['columns']))}`. "
        f"Cell key separator: `{_md_cell(census['cell_key_separator'])}`. "
        f"Censused records: `{census['census_record_count']}` of "
        f"`{semantics['audited_row_count']}`.",
        "",
        "### 2.1 Registered-token census (direction-free)",
        "",
        "| Cell key | Records |",
        "|---|---|",
    ]
    for cell in census["registered_token_joint_census"]:
        if cell["count"] == 0:
            continue
        lines.append(f"| `{_md_cell(cell['cell_key'])}` | {cell['count']} |")
    if all(cell["count"] == 0 for cell in census["registered_token_joint_census"]):
        lines.append("| (no record carried a fully registered combination) | 0 |")
    lines += [
        "",
        f"- Enumerated token cells: `{census['expected_registered_token_cell_count']}` "
        "(zero cells omitted above)",
        "",
        "### 2.2 Registered binary-code census and descriptor counts",
        "",
        "| Cell key | Records |",
        "|---|---|",
    ]
    for cell in census["registered_binary_code_joint_census"]:
        if cell["count"] == 0:
            continue
        lines.append(f"| `{_md_cell(cell['cell_key'])}` | {cell['count']} |")
    if all(cell["count"] == 0 for cell in census["registered_binary_code_joint_census"]):
        lines.append("| (no record carried a fully registered combination) | 0 |")
    lines += [
        "",
        "| Registered descriptors present | Records |",
        "|---|---|",
    ]
    for count in range(5):
        lines.append(f"| {count} | {census['descriptor_count_distribution'][str(count)]} |")
    lines += [
        "",
        f"- Records carrying two or more registered descriptors: "
        f"`{census['records_with_two_or_more_registered_descriptors']}`",
        f"- Records with any missing cell in the four columns: "
        f"`{census['records_with_any_missing_cell']}`",
        f"- Records with any unregistered cell in the four columns: "
        f"`{census['records_with_any_unregistered_cell']}`",
        f"- Descriptor-count basis: `{_md_cell(census['descriptor_count_basis'])}`",
        "",
        "## 3. Bundled source documentation",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Status | `{_md_cell(documentation['status'])}` |",
        f"| Documentation file authorized | `{documentation['documentation_file_authorized']}` |",
        f"| Archive or document member opened | "
        f"`{documentation['archive_or_document_member_opened']}` |",
        f"| Authorized DA-A1 files | "
        f"`{_md_cell(', '.join(documentation['authorized_files_for_da_a1']))}` |",
        "",
        f"{documentation['required_additional_authorization']}",
        "",
        "## 4. What must not be inferred",
        "",
    ]
    for item in report["evidence_limitations"]:
        lines.append(f"- **{_md_cell(item['id'])}** — {_md_cell(item['statement'])}")
    lines += [
        "",
        "## 5. Integrity and privacy",
        "",
        f"- Byte-identity guarded files: "
        f"`{report['input_integrity_and_privacy']['byte_identity_guard_file_count']}` "
        "(all byte-identical before and after the run)",
        "- Unregistered token text emitted: `False`",
        "- Patient-level rows emitted: `0`",
        "- Human privacy and scientific review is required before any excerpt is shared.",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Authorized local execution
# ---------------------------------------------------------------------------


def _assert_manifest_gates(auth_manifest: Mapping[str, Any]) -> None:
    """Fail closed unless the manifest still records a read-only, non-fitting posture."""
    if auth_manifest.get("model_fitting_authorized") is not False:
        raise RuntimeError("STOP: Authorization manifest must record model_fitting_authorized=false.")
    if auth_manifest.get("gate_pt_status") != "CLOSED_REQUIRES_SUPERVISOR_SIGNOFF_P3":
        raise RuntimeError("STOP: Gate PT must remain CLOSED_REQUIRES_SUPERVISOR_SIGNOFF_P3.")
    if auth_manifest.get("supervisor_approval_claimed") is True:
        raise RuntimeError("STOP: A supervisor-approval claim is not permitted in this audit manifest.")


def run_uci412_source_semantics_audit(
    *,
    repo_root: Path = REPO_ROOT,
    base_data_parent: Path | None = None,
    auth_manifest_path: Path | None = None,
    provenance_manifest_path: Path | None = None,
    is_synthetic_fixture_run: bool = False,
    allow_external_tmp_root: Path | None = None,
    acknowledge_read_only_scope: bool = False,
    json_output_path: Path | str | None = None,
    markdown_output_path: Path | str | None = None,
) -> tuple[dict[str, Any], str]:
    """Run the authorized read-only UCI-412 source-semantics audit; return (report, markdown)."""
    if acknowledge_read_only_scope is not True:
        raise RuntimeError(
            "STOP: --acknowledge-read-only-scope is required. The operator must confirm that this "
            "run is a D-046 read-only aggregate audit with no fitting, selection, tuning, "
            "evaluation, calibration or clinical claim."
        )

    root = repo_root.resolve()
    parent = (base_data_parent or root).resolve()
    auth_path = auth_manifest_path or (parent / "data/manifests/gate_da_authorization.local.json")
    prov_path = provenance_manifest_path or (parent / "data/manifests/provenance_manifest.json")

    verify_git_ignore(root)
    verify_data_root_containment(root, parent / "data", allow_external_tmp_root=allow_external_tmp_root)
    verify_data_root_containment(root, prov_path, allow_external_tmp_root=allow_external_tmp_root)

    auth = load_authorization_manifest(auth_path)
    verify_global_workflow_authorized(auth)
    verify_dataset_authorized_for_audit(auth, DATASET_ID)
    _assert_manifest_gates(auth)

    registered_semantics = load_registered_source_semantics(root)

    verified = validate_provenance_manifest(prov_path, parent, auth, (DATASET_ID,))
    files = verified[DATASET_ID]
    if AUTHORIZED_WORKBOOK_FILENAME not in files:
        raise FormatValidationError(
            f"STOP: provenance manifest does not record the authorized DA-A1 workbook "
            f"'{AUTHORIZED_WORKBOOK_FILENAME}'."
        )
    workbook_meta = files[AUTHORIZED_WORKBOOK_FILENAME]
    if sorted(files) != [AUTHORIZED_WORKBOOK_FILENAME]:
        raise FormatValidationError(
            "STOP: the DA-A1 provenance manifest records file(s) outside the single authorized "
            f"workbook: {sorted(files)}. Refusing to audit."
        )
    guard_entries: list[tuple[str, Path, str, int]] = [
        (
            str(meta["relative_path"]),
            Path(meta["resolved_path"]),
            str(meta["verified_sha256"]),
            int(meta["verified_size_bytes"]),
        )
        for _, meta in sorted(files.items())
    ]

    da_a1 = auth["datasets"][DATASET_ID]
    authorized_files = list(da_a1.get("authorized_files", []))
    excluded_files = list(da_a1.get("excluded_unapproved_files", []))

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

        parsed = audit_uci_412_or_411_workbook(
            Path(workbook_meta["resolved_path"]), dataset_id=DATASET_ID
        )
        rows = parsed["normalized_rows"]
        validator_row_count = int(parsed["report"]["row_count"])
        if not rows or len(rows) != validator_row_count:
            raise RuntimeError("STOP: workbook validator row count does not match parsed rows.")
        forbidden_fingerprints = list(parsed["raw_row_fingerprints"])

        snapshots = guard.verify_unchanged_now()
        report = build_source_semantics_report(
            rows=rows,
            source_filename=AUTHORIZED_WORKBOOK_FILENAME,
            source_relative_path=str(workbook_meta["relative_path"]),
            registered_semantics=registered_semantics,
            governance_context=_governance_context(auth),
            authorized_files=authorized_files,
            excluded_unapproved_files=excluded_files,
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
            validator_row_count=validator_row_count,
            is_synthetic_fixture_run=is_synthetic_fixture_run,
        )

        markdown = render_uci412_source_semantics_markdown(report)
        validate_uci412_source_semantics_report_schema(report)
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
    is_synthetic_fixture_run: bool = False,
) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m research.audit.uci412_source_semantics",
        description=(
            "Read-only, aggregate-only UCI-412 (DA-A1) source-semantics audit: registered coding "
            "coverage, four-field chest-pain joint census, and the bundled-documentation "
            "authorization status. No fitting, no metric, no clinical claim."
        ),
    )
    parser.add_argument("--auth-manifest", required=True, type=Path)
    parser.add_argument("--provenance-manifest", required=True, type=Path)
    parser.add_argument(
        "--acknowledge-read-only-scope",
        action="store_true",
        required=True,
        help=(
            "Required explicit acknowledgement that this run is a D-046 read-only aggregate audit "
            "with no fitting, selection, tuning, evaluation, calibration or clinical claim."
        ),
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=Path("data/reports/uci-412-source-semantics.json"),
        help="Report output is restricted to data/reports/<filename>.json",
    )
    parser.add_argument(
        "--markdown-out",
        type=Path,
        default=Path("data/reports/uci-412-source-semantics.md"),
        help="Report output is restricted to data/reports/<filename>.md",
    )
    args = parser.parse_args(argv)

    report, _markdown = run_uci412_source_semantics_audit(
        repo_root=repo_root,
        base_data_parent=base_data_parent,
        auth_manifest_path=args.auth_manifest,
        provenance_manifest_path=args.provenance_manifest,
        # Test-only markers: a CLI run without them is always a real local run.
        is_synthetic_fixture_run=is_synthetic_fixture_run,
        allow_external_tmp_root=allow_external_tmp_root,
        acknowledge_read_only_scope=args.acknowledge_read_only_scope,
        json_output_path=args.json_out,
        markdown_output_path=args.markdown_out,
    )
    coverage = report["source_semantics"]["registered_coding_coverage"]
    census = report["source_semantics"]["four_field_chest_pain_joint_census"]
    print(
        json.dumps(
            {
                "status_label": report["status_label"],
                "execution_status": report["scope_and_evidence_boundary"]["execution_status"],
                "records_audited": report["source_semantics"]["audited_row_count"],
                "all_observed_cells_match_registered_vocabulary": coverage[
                    "all_observed_cells_match_registered_vocabulary"
                ],
                "columns_with_unregistered_tokens": coverage["columns_with_unregistered_tokens"],
                "chest_pain_census_record_count": census["census_record_count"],
                "records_with_two_or_more_registered_descriptors": census[
                    "records_with_two_or_more_registered_descriptors"
                ],
                "bundled_documentation_status": report["source_semantics"][
                    "bundled_source_documentation_review"
                ]["status"],
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
