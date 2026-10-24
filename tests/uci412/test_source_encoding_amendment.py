"""Amendment A-1 — UCI-412 numeric 0/1 source encoding correction.

Every fixture here is generated in memory. No real UCI-412 byte, row, cell value
or patient-level structure is read, written, or asserted on. The aggregate counts
recorded in the feature dictionary come from the maintainer's human audit record
and are descriptive metadata, not data this test suite can or does verify.

What these tests protect:

* only the six audited columns convert numeric 0/1, and only in the registered
  direction (0 -> absent/false, 1 -> present/true);
* every other admitted categorical column keeps its registered text vocabulary;
* text tokens, booleans, non-binary/non-integral numbers, non-finite cells and
  unknown values fail closed in the six numeric columns — there is no global
  coercion anywhere;
* the executable panel, its exact order, its 16 encoded parameters, the target
  mapping, the leakage checks and the aggregate-only audit object are unchanged;
* evidence addendum E-1: the direction claim cites the peer-reviewed secondary
  source (Tao et al. 2025, Table 1) while still refusing to represent itself as
  officially codebook-confirmed;
* an authorization manifest written for the earlier dictionary/panel version
  fails closed, so the previous hash-bound signature cannot be reused.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from research.uci412 import safety
from research.uci412.adapter import sheet_from_rows, validate_workbook_structure
from research.uci412.config import (
    ALLOWED_MODEL_FAMILIES,
    ALLOWED_OPERATIONS,
    AUTHORIZATION_TEMPLATE_PATH,
    DEFAULT_CONFIG,
    FORBIDDEN_OPERATIONS,
    M3A_AUTHORIZATION_COMMENT,
    M3A_LOCAL_SIGNATURE_ATTESTATION,
    M3A_PROTOCOL_AMENDMENT_ID,
    SOURCE_ENCODING_REGISTER_ID,
)
from research.uci412.errors import AuthorizationError, SchemaError, SourceFormatError
from research.uci412.evaluation import assert_no_target_leakage
from research.uci412.feature_schema import (
    DICTIONARY_PATH,
    DICTIONARY_SCHEMA_VERSION,
    PRIMARY_PANEL_COLUMNS,
    PRIMARY_PANEL_VERSION,
    describe_panels,
    load_feature_dictionary,
)
from research.uci412.models import registered_categories
from research.uci412.runner import run_synthetic_dry_run
from research.uci412.source_spec import (
    NUMERIC_BINARY_SOURCE_COLUMNS,
    NUMERIC_BINARY_SOURCE_ENCODING_ID,
    SOURCE_COLUMNS,
    TARGET_COLUMN,
    TEXT_CATEGORICAL_SOURCE_COLUMNS,
)

from tests.uci412.conftest import dataset_from_rows, synthetic_rows

OTHER_TEXT_COLUMNS: tuple[str, ...] = TEXT_CATEGORICAL_SOURCE_COLUMNS
TEXT_TOKENS = ("Y", "N", "Yes", "No", "0", "1", "TRUE", "present")
SENTINEL = "SENTINEL_NUMERIC_BINARY_PATIENT_VALUE_5501"


def _headers_and_rows() -> tuple[tuple[str, ...], list[tuple[Any, ...]]]:
    headers, rows = synthetic_rows(DEFAULT_CONFIG)
    return headers, [tuple(row) for row in rows]


def _with_column(headers: tuple[str, ...], rows: list[tuple[Any, ...]], column: str, value: Any):
    index = headers.index(column)
    mutated = [list(row) for row in rows]
    for row in mutated:
        row[index] = value
    return [tuple(row) for row in mutated]


def _with_cell(
    headers: tuple[str, ...], rows: list[tuple[Any, ...]], column: str, value: Any, row_index: int = 0
):
    index = headers.index(column)
    mutated = [list(row) for row in rows]
    mutated[row_index][index] = value
    return [tuple(row) for row in mutated]


# --------------------------------------------------------------------------- #
# 1. The registered encoding: exactly six columns, one direction
# --------------------------------------------------------------------------- #


def test_only_the_six_audited_columns_carry_a_numeric_source_encoding() -> None:
    dictionary = load_feature_dictionary()
    assert tuple(dictionary.numeric_binary_source_columns()) == NUMERIC_BINARY_SOURCE_COLUMNS
    assert len(NUMERIC_BINARY_SOURCE_COLUMNS) == 6
    assert set(NUMERIC_BINARY_SOURCE_COLUMNS).isdisjoint(TEXT_CATEGORICAL_SOURCE_COLUMNS)

    for column in NUMERIC_BINARY_SOURCE_COLUMNS:
        spec = dictionary.feature(column)
        encoding = spec.source_value_encoding
        assert encoding is not None, column
        assert encoding.encoding_id == NUMERIC_BINARY_SOURCE_ENCODING_ID
        assert encoding.source_value_kind == "NUMERIC_BINARY_0_1"
        assert (encoding.absent_source_value, encoding.present_source_value) == (0, 1)
        assert (encoding.absent_model_code, encoding.present_model_code) == (0, 1)
        # The model-side contract is deliberately unchanged.
        assert spec.is_categorical and spec.kind == "binary"
        assert spec.codes == (0, 1)
        assert spec.vocabulary is None
        assert encoding.verification_status == (
            "HUMAN_SHA256_VERIFIED_LOCAL_READ_ONLY_AUDIT_2026-10-24"
        )
        # Retrospective text tokens are explicitly refused, not silently accepted.
        assert {"Y", "N", "Yes", "No"} <= set(encoding.legacy_tokens_rejected)
        counts = encoding.observed_aggregate_counts
        assert counts["records"] == 303 and counts["blanks"] == 0
        assert counts["0"] + counts["1"] == 303


def test_the_other_six_categoricals_keep_their_registered_vocabularies() -> None:
    dictionary = load_feature_dictionary()
    assert tuple(TEXT_CATEGORICAL_SOURCE_COLUMNS) == (
        "Sex",
        "DLP",
        "Atypical",
        "Nonanginal",
        "Exertional CP",
        "Dyspnea",
    )
    for column in TEXT_CATEGORICAL_SOURCE_COLUMNS:
        spec = dictionary.feature(column)
        assert spec.source_value_encoding is None, column
        assert spec.vocabulary, column
        assert spec.codes == (0, 1)


def test_registered_plan_binds_the_amendment_and_the_six_columns() -> None:
    assert M3A_PROTOCOL_AMENDMENT_ID == "M3A-AMENDMENT-A1"
    assert SOURCE_ENCODING_REGISTER_ID == NUMERIC_BINARY_SOURCE_ENCODING_ID
    assert DEFAULT_CONFIG.numeric_binary_source_features == NUMERIC_BINARY_SOURCE_COLUMNS
    assert set(DEFAULT_CONFIG.numeric_binary_source_features) <= set(
        DEFAULT_CONFIG.categorical_features
    )
    report = DEFAULT_CONFIG.as_report_dict()
    encoding_block = report["source_value_encoding"]
    assert encoding_block["register_id"] == NUMERIC_BINARY_SOURCE_ENCODING_ID
    assert tuple(encoding_block["numeric_binary_source_columns"]) == NUMERIC_BINARY_SOURCE_COLUMNS
    assert encoding_block["numeric_binary_semantics"] == {
        "0": "ABSENT_OR_FALSE",
        "1": "PRESENT_OR_TRUE",
    }
    assert encoding_block["global_automatic_coercion"] == "FORBIDDEN"
    assert encoding_block["encoded_parameter_count"] == 16
    assert encoding_block["protocol_amendment_id"] == "M3A-AMENDMENT-A1"


def test_every_categorical_source_column_declares_exactly_one_coding_record() -> None:
    payload = json.loads(DICTIONARY_PATH.read_text(encoding="utf-8"))
    for column, feature in payload["features"].items():
        has_vocabulary = feature["vocabulary"] is not None
        has_encoding = feature.get("source_value_encoding") is not None
        if feature["role"] == "numeric":
            # Measured values are handled by the numeric plausibility guards.
            assert not has_vocabulary and not has_encoding, column
            continue
        assert has_vocabulary != has_encoding, column
        if has_encoding:
            assert column in NUMERIC_BINARY_SOURCE_COLUMNS


# --------------------------------------------------------------------------- #
# 2. Accepted numeric values
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("column", NUMERIC_BINARY_SOURCE_COLUMNS)
def test_numeric_zero_maps_to_absent_and_one_to_present(column: str) -> None:
    headers, rows = _headers_and_rows()
    index = DEFAULT_CONFIG.feature_names.index(column)

    absent = dataset_from_rows(headers, _with_column(headers, rows, column, 0))
    assert np.all(absent.X[:, index] == 0.0)
    assert absent.audit["numeric_binary_source_value_counts"][column] == {"0": 303}

    present = dataset_from_rows(headers, _with_column(headers, rows, column, 1))
    assert np.all(present.X[:, index] == 1.0)
    assert present.audit["numeric_binary_source_value_counts"][column] == {"1": 303}


@pytest.mark.parametrize("column", NUMERIC_BINARY_SOURCE_COLUMNS)
def test_exact_float_zero_and_one_are_accepted(column: str) -> None:
    headers, rows = _headers_and_rows()
    index = DEFAULT_CONFIG.feature_names.index(column)
    for value, expected in ((0.0, 0.0), (1.0, 1.0)):
        dataset = dataset_from_rows(headers, _with_column(headers, rows, column, value))
        assert np.all(dataset.X[:, index] == expected)


def test_mixed_numeric_and_text_representation_in_one_column_fails_closed() -> None:
    headers, rows = _headers_and_rows()
    rows = _with_cell(headers, rows, "DM", 1)
    rows = _with_cell(headers, rows, "DM", "Y", row_index=1)
    with pytest.raises(SourceFormatError, match="numeric 0/1"):
        dataset_from_rows(headers, rows)


def test_blank_numeric_binary_cells_remain_documented_gaps(monkeypatch: pytest.MonkeyPatch) -> None:
    headers, rows = _headers_and_rows()
    rows = _with_cell(headers, rows, "HTN", None)
    dataset = dataset_from_rows(headers, rows)
    index = DEFAULT_CONFIG.feature_names.index("HTN")
    assert np.isnan(dataset.X[:, index]).sum() == 1
    assert dataset.audit["blank_cell_counts_by_admitted_column"]["HTN"] == 1
    assert sum(dataset.audit["numeric_binary_source_value_counts"]["HTN"].values()) == 302


# --------------------------------------------------------------------------- #
# 3. Everything else fails closed
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("column", NUMERIC_BINARY_SOURCE_COLUMNS)
@pytest.mark.parametrize("token", TEXT_TOKENS)
def test_text_tokens_are_rejected_in_numeric_binary_columns(column: str, token: str) -> None:
    headers, rows = _headers_and_rows()
    with pytest.raises(SourceFormatError, match="numeric 0/1"):
        dataset_from_rows(headers, _with_cell(headers, rows, column, token))


@pytest.mark.parametrize("column", NUMERIC_BINARY_SOURCE_COLUMNS)
@pytest.mark.parametrize("value", [True, False])
def test_boolean_cells_are_rejected_in_numeric_binary_columns(column: str, value: bool) -> None:
    headers, rows = _headers_and_rows()
    with pytest.raises(SourceFormatError, match="numeric 0/1"):
        dataset_from_rows(headers, _with_cell(headers, rows, column, value))


@pytest.mark.parametrize("column", NUMERIC_BINARY_SOURCE_COLUMNS)
@pytest.mark.parametrize("value", [2, -1, 10, 0.5, 1.5, 1.0000001, 100.0])
def test_non_binary_numbers_are_rejected(column: str, value: Any) -> None:
    headers, rows = _headers_and_rows()
    with pytest.raises(SourceFormatError, match="numeric 0/1"):
        dataset_from_rows(headers, _with_cell(headers, rows, column, value))


@pytest.mark.parametrize("column", NUMERIC_BINARY_SOURCE_COLUMNS)
@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_cells_are_rejected(column: str, value: float) -> None:
    headers, rows = _headers_and_rows()
    with pytest.raises(SourceFormatError, match="numeric 0/1"):
        dataset_from_rows(headers, _with_cell(headers, rows, column, value))


def test_numeric_binary_failures_never_echo_the_cell_value() -> None:
    headers, rows = _headers_and_rows()
    for bad in (SENTINEL, 2, True):
        with pytest.raises(SourceFormatError) as excinfo:
            dataset_from_rows(headers, _with_cell(headers, rows, "DM", bad))
        assert SENTINEL not in str(excinfo.value)
        assert SENTINEL not in repr(excinfo.value)


@pytest.mark.parametrize("column", OTHER_TEXT_COLUMNS)
def test_numeric_cells_are_still_rejected_in_text_categorical_columns(column: str) -> None:
    headers, rows = _headers_and_rows()
    for value in (1, 0, 1.0):
        with pytest.raises(SourceFormatError, match="vocabulary"):
            dataset_from_rows(headers, _with_cell(headers, rows, column, value))


@pytest.mark.parametrize("column", OTHER_TEXT_COLUMNS)
def test_text_categorical_columns_still_accept_only_registered_tokens(column: str) -> None:
    headers, rows = _headers_and_rows()
    index = DEFAULT_CONFIG.feature_names.index(column)
    vocabulary = load_feature_dictionary().feature(column).vocabulary
    assert vocabulary
    present_token = next(token for token, code in vocabulary.items() if code == 1)
    absent_token = next(token for token, code in vocabulary.items() if code == 0)
    present = dataset_from_rows(headers, _with_column(headers, rows, column, present_token))
    assert np.all(present.X[:, index] == 1.0)
    absent = dataset_from_rows(headers, _with_column(headers, rows, column, absent_token))
    assert np.all(absent.X[:, index] == 0.0)
    with pytest.raises(SourceFormatError, match="vocabulary"):
        dataset_from_rows(headers, _with_cell(headers, rows, column, SENTINEL))


def test_sex_keeps_its_documented_text_mapping() -> None:
    headers, rows = _headers_and_rows()
    index = DEFAULT_CONFIG.feature_names.index("Sex")
    male = dataset_from_rows(headers, _with_column(headers, rows, "Sex", "Male"))
    assert np.all(male.X[:, index] == 1.0)
    female = dataset_from_rows(headers, _with_column(headers, rows, "Sex", "Fmale"))
    assert np.all(female.X[:, index] == 0.0)
    with pytest.raises(SourceFormatError, match="vocabulary"):
        dataset_from_rows(headers, _with_cell(headers, rows, "Sex", "M"))


def test_no_global_numeric_conversion_exists_anywhere() -> None:
    """A numeric cell is accepted only where a registered numeric encoding exists."""
    headers, rows = _headers_and_rows()
    for column, value in (("Age", "58"), ("BP", "120"), ("BMI", "twenty"), ("DLP", 1), ("Sex", 1)):
        with pytest.raises(SourceFormatError):
            dataset_from_rows(headers, _with_cell(headers, rows, column, value))


# --------------------------------------------------------------------------- #
# 4. Frozen panel, order, parameter count, target, leakage
# --------------------------------------------------------------------------- #


def test_feature_order_and_sixteen_parameters_are_unchanged() -> None:
    dictionary = load_feature_dictionary()
    dataset = dataset_from_rows(*_headers_and_rows())

    assert DEFAULT_CONFIG.feature_names == PRIMARY_PANEL_COLUMNS
    assert len(PRIMARY_PANEL_COLUMNS) == 16
    assert dataset.feature_names == PRIMARY_PANEL_COLUMNS
    assert dataset.X.shape == (303, 16)
    assert dictionary.encoded_parameter_count() == 16
    assert len(dictionary.numeric_columns()) == 4
    assert len(dictionary.categorical_columns()) == 12
    # Every categorical input stays reference-coded on exactly two codes, so the
    # one-hot width (and therefore the parameter count) cannot have moved.
    for column in dictionary.categorical_columns():
        assert dictionary.feature(column).codes == (0, 1), column
    for categories in registered_categories(DEFAULT_CONFIG):
        assert np.array_equal(categories, np.asarray([0.0, 1.0]))


def test_schema_and_panel_versions_are_the_reviewable_amendment_versions() -> None:
    dictionary = load_feature_dictionary()
    assert DICTIONARY_SCHEMA_VERSION == "1.1.0"
    assert PRIMARY_PANEL_VERSION == "1.1.0"
    assert dictionary.schema_version == "1.1.0"
    assert dictionary.primary_panel.version == "1.1.0"
    assert DEFAULT_CONFIG.panel_version == "1.1.0"
    assert DEFAULT_CONFIG.dictionary_schema_version == "1.1.0"
    # The pre-amendment identifiers must not silently linger anywhere.
    assert "1.0.0" not in {DEFAULT_CONFIG.panel_version, DEFAULT_CONFIG.dictionary_schema_version}


def test_target_mapping_and_leakage_checks_are_unchanged() -> None:
    dataset = dataset_from_rows(*_headers_and_rows())
    assert TARGET_COLUMN == "Cath"
    assert TARGET_COLUMN not in dataset.feature_names
    assert dataset.class_counts == ((0, 87), (1, 216))
    checks = assert_no_target_leakage(dataset, config=DEFAULT_CONFIG)
    assert all(checks.values()), checks
    assert checks["target_column_not_in_features"] is True
    assert checks["target_matrix_is_separate"] is True
    assert checks["target_matches_audited_class_counts"] is True
    # No admitted numeric-binary column may be a copy of the outcome.
    for column in NUMERIC_BINARY_SOURCE_COLUMNS:
        index = dataset.feature_names.index(column)
        assert not np.array_equal(dataset.X[:, index], dataset.y.astype(float)), column


def test_audit_object_stays_aggregate_only() -> None:
    dataset = dataset_from_rows(*_headers_and_rows())
    audit = dataset.audit
    assert set(audit["observed_category_token_counts"]) == set(TEXT_CATEGORICAL_SOURCE_COLUMNS)
    assert set(audit["numeric_binary_source_value_counts"]) == set(NUMERIC_BINARY_SOURCE_COLUMNS)
    for counts in audit["numeric_binary_source_value_counts"].values():
        assert set(counts) <= {"0", "1"}
        assert all(isinstance(count, int) for count in counts.values())
    assert audit["numeric_binary_source_encoding_id"] == NUMERIC_BINARY_SOURCE_ENCODING_ID
    assert audit["numeric_binary_source_semantics"] == {
        "0": "ABSENT_OR_FALSE",
        "1": "PRESENT_OR_TRUE",
    }
    assert audit["patient_level_values_retained_in_audit_object"] is False
    assert audit["value_repair_or_row_deletion_performed"] is False
    serialized = json.dumps(audit)
    assert "rows" not in audit and "X" not in audit
    assert SENTINEL not in serialized


def test_workbook_still_requires_the_exact_registered_columns() -> None:
    headers, rows = _headers_and_rows()
    workbook = sheet_from_rows(headers, tuple(rows))
    parsed = validate_workbook_structure(workbook)
    assert parsed.header_order_matches_registered_profile is True
    assert len(SOURCE_COLUMNS) == 56


# --------------------------------------------------------------------------- #
# 5. End-to-end synthetic run
# --------------------------------------------------------------------------- #


def test_full_synthetic_dry_run_executes_on_the_corrected_encoding() -> None:
    result = run_synthetic_dry_run()
    assert result["status"] == "PASS"
    assert result["scope"] == "SYNTHETIC_SOFTWARE_FIXTURE_ONLY_NOT_A_RESEARCH_RESULT"
    assert result["source_rows_parsed_in_memory"] == 303
    assert result["real_data_path_opened"] is False
    assert result["report_or_prediction_files_written"] is False
    assert result["metrics_generated_for_medical_or_benchmark_use"] is False
    assert result["outer_repeat_count"] == 1
    assert result["fit_profile"]["real_run_requires_default_config"] is True
    assert result["synthetic_scope"] == "SYNTHETIC_SOFTWARE_FIXTURE_NOT_UCI_DATA"
    assert "status" in result["leakage_assessment"]


def test_dry_run_is_deterministic_under_the_corrected_encoding() -> None:
    headers, rows = _headers_and_rows()
    first = dataset_from_rows(headers, rows)
    second = dataset_from_rows(*_headers_and_rows())
    assert np.array_equal(first.X, second.X, equal_nan=True)
    assert np.array_equal(first.y, second.y)
    for column in NUMERIC_BINARY_SOURCE_COLUMNS:
        assert set(np.unique(first.X[:, first.feature_names.index(column)])).issubset({0.0, 1.0})


# --------------------------------------------------------------------------- #
# 6. The dictionary cannot be widened or inverted by a JSON edit
# --------------------------------------------------------------------------- #


def _tampered_dictionary(tmp_path: Path, mutate) -> Path:
    payload = json.loads(DICTIONARY_PATH.read_text(encoding="utf-8"))
    mutate(payload)
    target = tmp_path / "tampered_dictionary.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


@pytest.mark.parametrize(
    "mutate",
    [
        # Widen the numeric conversion to a text-categorical column.
        lambda payload: payload["features"]["DLP"].update(
            source_value_encoding=copy.deepcopy(
                payload["features"]["DM"]["source_value_encoding"]
            )
        ),
        # Re-register a text vocabulary for a numeric column (both codings at once).
        lambda payload: payload["features"]["DM"].update(vocabulary={"Y": 1, "N": 0}),
        # Drop the numeric encoding entirely.
        lambda payload: payload["features"]["HTN"].pop("source_value_encoding"),
        # Invert the direction.
        lambda payload: payload["features"]["DM"]["source_value_encoding"].update(
            absent_model_code=1, present_model_code=0
        ),
        # Claim a weaker evidence basis than a human audit.
        lambda payload: payload["features"]["DM"]["source_value_encoding"].update(
            verification_status="SECONDARY_LITERATURE_ONLY"
        ),
        # Accept a value other than 0/1.
        lambda payload: payload["features"]["DM"]["source_value_encoding"].update(
            present_source_value=2
        ),
        # Silently change the mapping identity.
        lambda payload: payload["features"]["DM"]["source_value_encoding"].update(
            encoding_id="numeric_binary_0_1_relaxed"
        ),
        # Remove the recorded uncertainty.
        lambda payload: payload["features"]["DM"]["source_value_encoding"].update(
            semantic_uncertainty="   "
        ),
        # Drop the aggregate audit evidence.
        lambda payload: payload["features"]["DM"]["source_value_encoding"].pop(
            "observed_aggregate_counts"
        ),
    ],
)
def test_dictionary_edits_cannot_widen_or_invert_the_encoding(
    tmp_path: Path, mutate
) -> None:
    tampered = _tampered_dictionary(tmp_path, mutate)
    with pytest.raises(SchemaError):
        load_feature_dictionary(tampered)


def test_review_description_exposes_the_amendment_without_patient_content() -> None:
    description = describe_panels()
    encoding = description["source_value_encoding"]
    assert tuple(encoding["numeric_binary_source_columns"]) == NUMERIC_BINARY_SOURCE_COLUMNS
    assert tuple(encoding["text_categorical_source_columns"]) == TEXT_CATEGORICAL_SOURCE_COLUMNS
    assert encoding["global_automatic_coercion"] == "FORBIDDEN"
    assert "M3A-AMENDMENT-A1" in encoding["amendment"]
    assert description["executable_parameter_count"] == 16
    assert SENTINEL not in json.dumps(description)


# --------------------------------------------------------------------------- #
# 7. The earlier signed authorization cannot be reused
# --------------------------------------------------------------------------- #

_PR45_ERA_MANIFEST: dict[str, Any] = {
    # Field-for-field the shape a maintainer would have signed against the
    # pre-amendment dictionary (schema 1.0.0) and panel (1.0.0). It is a
    # synthetic test fixture, not a real or simulated human signature.
    "schema_version": "0.1.0",
    "proposal_id": "M3A-UCI412-INTERNAL-RESEARCH-PROPOSAL",
    "authorization_status": "AUTHORIZED_FOR_LOCAL_INTERNAL_RESEARCH",
    "experiment_type": "INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED",
    "supervisor_signoff_claimed": False,
    "gate_pt_status": "CLOSED_REQUIRES_SUPERVISOR_SIGNOFF_P3",
    "maintainer_approval_comment_exact": M3A_AUTHORIZATION_COMMENT,
    "governance_pr_number": 45,
    "governance_merge_commit_sha": "a" * 40,
    "pinned_protocol_commit_sha": "a" * 40,
    "authorization_proposal_relative_path": (
        "docs/research/gate-pt/08_m3a_uci412_source_specific_benchmark_SPECIFICATION.md"
    ),
    "frozen_authorization_proposal_sha256": "b" * 64,
    "frozen_feature_dictionary_sha256": "c" * 64,
    "frozen_research_plan_sha256": "d" * 64,
    "dataset_id": "DA-A1",
    "target_column": "Cath",
    "allowed_original_relative_file": "data/raw/uci-412/Z-Alizadeh sani dataset.xlsx",
    "authorized_source_row_count": 303,
    "panel_schema_id": "uci412_basic_clinical_v1",
    "panel_schema_version": "1.0.0",
    "allowlisted_model_families": list(ALLOWED_MODEL_FAMILIES),
    "allowed_operations_if_approved": list(ALLOWED_OPERATIONS),
    "forbidden_operations": list(FORBIDDEN_OPERATIONS),
    "allowed_runtime": "LOCAL_WINDOWS_CPU_ONLY",
    "protected_outputs_relative_root": "data/uci412-experiments",
    "expected_sha256_from_protected_provenance_manifest": (
        "90fefd4ecdb6263b3f2a260bb2b5d3b9fa92ba35d626dd56ad8c6db5fbbad163"
    ),
    "local_signer": "Muhammed Fathi",
    "local_signed_at_iso8601": "2026-10-24T12:00:00+00:00",
    "local_signature_attestation": M3A_LOCAL_SIGNATURE_ATTESTATION,
    "signature_semantics": "HUMAN_ATTESTATION_FIELDS_NOT_A_CRYPTOGRAPHIC_SIGNATURE",
}


def _validate(manifest: dict[str, Any], tmp_path: Path) -> None:
    safety.validate_m3a_authorization(
        manifest,
        repo_root=tmp_path,
        current_git_commit="e" * 40,
        config=DEFAULT_CONFIG,
    )


def test_previous_panel_version_manifest_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(AuthorizationError, match="different panel version"):
        _validate(copy.deepcopy(_PR45_ERA_MANIFEST), tmp_path)


def test_manifest_without_the_amended_dictionary_version_fails_closed(tmp_path: Path) -> None:
    manifest = copy.deepcopy(_PR45_ERA_MANIFEST)
    manifest["panel_schema_version"] = DEFAULT_CONFIG.panel_version
    with pytest.raises(AuthorizationError, match="feature-dictionary schema version"):
        _validate(manifest, tmp_path)


def test_manifest_without_the_amendment_id_fails_closed(tmp_path: Path) -> None:
    manifest = copy.deepcopy(_PR45_ERA_MANIFEST)
    manifest["panel_schema_version"] = DEFAULT_CONFIG.panel_version
    manifest["dictionary_schema_version"] = DICTIONARY_SCHEMA_VERSION
    with pytest.raises(AuthorizationError, match="protocol amendment"):
        _validate(manifest, tmp_path)


def test_manifest_naming_the_amendment_still_needs_real_human_evidence(tmp_path: Path) -> None:
    """Passing the version gates is not authorization: the hashes and signer still bind."""
    manifest = copy.deepcopy(_PR45_ERA_MANIFEST)
    manifest["panel_schema_version"] = DEFAULT_CONFIG.panel_version
    manifest["dictionary_schema_version"] = DICTIONARY_SCHEMA_VERSION
    manifest["protocol_amendment_id"] = M3A_PROTOCOL_AMENDMENT_ID
    # The synthetic signer is not the verified maintainer, and the synthetic
    # hashes do not match this checkout: the guard must still refuse.
    with pytest.raises(AuthorizationError):
        _validate(manifest, tmp_path)


def test_checked_in_template_names_the_amendment_but_authorizes_nothing() -> None:
    template = json.loads(AUTHORIZATION_TEMPLATE_PATH.read_text(encoding="utf-8"))
    assert template["authorization_status"] != "AUTHORIZED_FOR_LOCAL_INTERNAL_RESEARCH"
    assert template["panel_schema_version"] == DEFAULT_CONFIG.panel_version == "1.1.0"
    assert template["dictionary_schema_version"] == DICTIONARY_SCHEMA_VERSION
    assert template["protocol_amendment_id"] == M3A_PROTOCOL_AMENDMENT_ID
    assert template["supervisor_signoff_claimed"] is False
    assert template["gate_pt_status"] == "CLOSED_REQUIRES_SUPERVISOR_SIGNOFF_P3"
    assert "REPLACE" in template["governance_merge_commit_sha"]
    assert safety.authorization_template_is_non_authorizing()


# --------------------------------------------------------------------------- #
# 8. Evidence addendum E-1 — peer-reviewed direction evidence, still provisional
# --------------------------------------------------------------------------- #

TAO_CITATION_ID = "TAO_2025_RCM_TABLE1"
TAO_DOI_FRAGMENT = "10.31083/RCM26204"
PROVISIONAL_STATUS = (
    "PROVISIONAL_DIRECTION_STATED_BY_PEER_REVIEWED_SECONDARY_LITERATURE_NOT_OFFICIAL_CODEBOOK"
)


def test_the_peer_reviewed_direction_source_is_registered_in_full() -> None:
    payload = json.loads(DICTIONARY_PATH.read_text(encoding="utf-8"))
    citation = payload["citations"][TAO_CITATION_ID]
    assert "Tao" in citation["reference"]
    assert "Reviews in Cardiovascular Medicine" in citation["reference"]
    assert TAO_DOI_FRAGMENT in citation["reference"]
    assert citation["status"] == "PEER_REVIEWED_SECONDARY_SOURCE_TABLE_READ"
    assert "True = 1; false = 0" in citation["supports"]
    # The honest boundary is recorded with the citation itself.
    assert "official dataset-owner" in citation["does_not_support"]
    assert "codebook" in citation["does_not_support"]


@pytest.mark.parametrize("column", NUMERIC_BINARY_SOURCE_COLUMNS)
def test_each_of_the_six_encodings_cites_the_direction_evidence(column: str) -> None:
    payload = json.loads(DICTIONARY_PATH.read_text(encoding="utf-8"))
    encoding = payload["features"][column]["source_value_encoding"]
    evidence = " ".join(encoding["semantic_evidence"])
    assert TAO_CITATION_ID in evidence
    assert TAO_DOI_FRAGMENT in evidence
    assert "True = 1; false = 0" in evidence
    # The direction is supported, and still not represented as official.
    assert "not confirmed by an official dataset-owner codebook" in encoding["semantic_interpretation"]
    assert "not been independently verified against an official codebook" in encoding[
        "semantic_uncertainty"
    ]
    assert "explicit human acceptance" in encoding["semantic_uncertainty"]


def test_the_mapping_itself_was_not_touched_by_the_evidence_addendum() -> None:
    payload = json.loads(DICTIONARY_PATH.read_text(encoding="utf-8"))
    for column in NUMERIC_BINARY_SOURCE_COLUMNS:
        encoding = payload["features"][column]["source_value_encoding"]
        assert encoding["absent_source_value"] == 0
        assert encoding["present_source_value"] == 1
        assert encoding["absent_model_code"] == 0
        assert encoding["present_model_code"] == 1
        assert encoding["encoding_id"] == "numeric_binary_0_1_v1"
        assert encoding["verification_status"] == (
            "HUMAN_SHA256_VERIFIED_LOCAL_READ_ONLY_AUDIT_2026-10-24"
        )
    # Evidence-only addendum: the contract version does not move again.
    assert payload["schema_version"] == "1.1.0"
    assert DEFAULT_CONFIG.panel_version == "1.1.0"
    assert load_feature_dictionary().encoded_parameter_count() == 16
    addendum = payload["revision_history"][-1]
    assert addendum["evidence_addendum_id"] == "M3A-AMENDMENT-A1-E1"
    assert addendum["contract_impact"].startswith("NONE")


def test_the_plan_records_direction_evidence_and_keeps_acceptance_required() -> None:
    plan = json.loads((Path("research/uci412") / "uci412_cad_research_plan.v0.1.json").read_text(
        encoding="utf-8"
    ))
    block = plan["source_encoding"]
    assert block["numeric_binary_semantics_status"] == PROVISIONAL_STATUS
    evidence = block["numeric_binary_semantics_evidence"]
    assert evidence["direction"] == TAO_CITATION_ID
    assert TAO_DOI_FRAGMENT in evidence["direction_reference"]
    assert evidence["official_dataset_owner_codebook"] == "NOT_AVAILABLE_NOT_INDEPENDENTLY_VERIFIED"
    assert evidence["explicit_human_acceptance_required"] is True
    assert plan["protocol_revision"]["evidence_addendum_id"] == "M3A-AMENDMENT-A1-E1"


def test_vocabulary_and_semantics_constants_stay_provisional() -> None:
    from research.uci412.source_spec import (
        NUMERIC_BINARY_SEMANTICS_EVIDENCE_CITATION_IDS,
        NUMERIC_BINARY_SEMANTICS_EVIDENCE_STATUS,
    )

    assert NUMERIC_BINARY_SEMANTICS_EVIDENCE_STATUS == PROVISIONAL_STATUS
    assert "OFFICIAL" in NUMERIC_BINARY_SEMANTICS_EVIDENCE_STATUS
    assert NUMERIC_BINARY_SEMANTICS_EVIDENCE_CITATION_IDS == (
        TAO_CITATION_ID,
        "HUMAN_LOCAL_READ_ONLY_AUDIT_2026_10_24",
    )
    encoding_block = DEFAULT_CONFIG.as_report_dict()["source_value_encoding"]
    assert encoding_block["numeric_binary_semantics_status"] == PROVISIONAL_STATUS
    assert encoding_block["numeric_binary_semantics_human_acceptance_required"] is True
    assert list(encoding_block["numeric_binary_semantics_evidence_citation_ids"]) == [
        TAO_CITATION_ID,
        "HUMAN_LOCAL_READ_ONLY_AUDIT_2026_10_24",
    ]


@pytest.mark.parametrize(
    "mutate",
    [
        # Claim official codebook confirmation.
        lambda plan: plan["source_encoding"]["numeric_binary_semantics_evidence"].update(
            official_dataset_owner_codebook="OFFICIALLY_CONFIRMED"
        ),
        # Drop the human-acceptance requirement.
        lambda plan: plan["source_encoding"]["numeric_binary_semantics_evidence"].update(
            explicit_human_acceptance_required=False
        ),
        # Re-label the direction evidence as something else.
        lambda plan: plan["source_encoding"]["numeric_binary_semantics_evidence"].update(
            direction="ATTRIBUTE_NAME_INFERENCE_ONLY"
        ),
        # Remove the citation from the direction reference.
        lambda plan: plan["source_encoding"]["numeric_binary_semantics_evidence"].update(
            direction_reference="no citation recorded"
        ),
        # Promote the status to "officially documented".
        lambda plan: plan["source_encoding"].update(
            numeric_binary_semantics_status="OFFICIALLY_DOCUMENTED"
        ),
        # Drop the evidence block entirely.
        lambda plan: plan["source_encoding"].pop("numeric_binary_semantics_evidence"),
    ],
)
def test_plan_cannot_claim_official_confirmation(tmp_path: Path, mutate) -> None:
    from research.uci412.config import load_registered_config

    plan = json.loads(
        (Path("research/uci412") / "uci412_cad_research_plan.v0.1.json").read_text(encoding="utf-8")
    )
    mutate(plan)
    target = tmp_path / "plan.json"
    target.write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(ValueError):
        load_registered_config(target)
