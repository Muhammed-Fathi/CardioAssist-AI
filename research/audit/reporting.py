"""Metadata-only audit report schema validation, report generation, output-path protection, and redaction safeguards."""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Sequence

from research.audit.exceptions import PatientLevelLeakageError
from research.audit.provenance import validate_and_resolve_report_output_path
from research.audit.registry import (
    EVIDENCE_REQUIRES_APPROVAL,
    EVIDENCE_SOURCE_REPORTED,
    EVIDENCE_UNVERIFIED,
    EVIDENCE_VERIFIED,
    FEATURE_AVAILABILITY_AND_LEAKAGE_TABLE,
    LOCAL_INTEGRITY_VERIFIED_STATUS,
    SOURCE_ORIGIN_HUMAN_ATTESTED_STATUS,
    TARGET_HARMONIZATION_SPEC,
    UCI_45_CONVENTIONAL_14_COLUMNS,
    UCI_411_ARTERY_LEAKAGE_COLUMNS,
    UCI_412_CANONICAL_BY_NORMALIZED,
    UCI_412_TARGET_COLUMN,
    VALID_EVIDENCE_LABELS,
)

FORBIDDEN_REPORT_KEYS = frozenset(
    {
        "normalized_rows",
        "extracted_conventional_rows",
        "raw_row_fingerprints",
        "patient_rows",
        "raw_rows",
        "patient_records",
        "sample_rows",
        "example_rows",
        "first_row",
        "records",
        "cell_values",
    }
)

ALLOWED_TOP_LEVEL_REPORT_KEYS = frozenset(
    {
        "report_schema_version",
        "milestone",
        "execution_mode",
        "is_synthetic_fixture_run",
        "synthetic_disclaimer",
        "evidence_labels_supported",
        "safety_and_non_fitting_certification",
        "governance_and_authorization",
        "git_ignore_verification",
        "byte_identity_snapshots",
        "dataset_audits",
        "cross_cohort_duplicate_and_overlap_analysis",
        "uci_411_412_correspondence",
        "uci_145_cleveland_overlap",
        "feature_availability_and_leakage_table",
        "target_harmonization_and_threshold_boundary",
        "source_reported_baseline_notes",
    }
)

KNOWN_UCI_412_411_COLUMNS: frozenset[str] = (
    frozenset(col for col, _ in UCI_412_CANONICAL_BY_NORMALIZED.values())
    | frozenset(UCI_411_ARTERY_LEAKAGE_COLUMNS)
    | frozenset({UCI_412_TARGET_COLUMN})
)

# Secondary safeguard regexes:
# 1. 14-column comma-delimited UCI-45 processed row
RAW_COMMA_14_LINE_RE = re.compile(
    r"(?:^|\n)\s*-?\d+(?:\.\d+)?\s*(?:,\s*(?:-?\d+(?:\.\d+)?|\?)\s*){13}(?:$|\n)"
)
# 2. 14-column whitespace-delimited UCI-145 Statlog row
RAW_SPACE_14_LINE_RE = re.compile(
    r"(?:^|\n)\s*-?\d+(?:\.\d+)?(?:\s+(?:-?\d+(?:\.\d+)?|\?)){13}\s*(?:$|\n)"
)
# 3. Non-14-column multi-token raw UCI-45 76-attribute line (8+ whitespace tokens with -9 or ending in 'name')
RAW_76_FRAGMENT_LINE_RE = re.compile(
    r"(?:^|\n)\s*(?:-?\d+(?:\.\d+)?\s+){7,}(?:name|-?\d+(?:\.\d+)?)\s*(?:$|\n)",
    re.IGNORECASE,
)
# 4. Generic >=8-column comma/semicolon/tab-delimited row of numeric/categorical values (e.g. 56-column UCI-412 row)
GENERIC_MULTI_COLUMN_ROW_RE = re.compile(
    r"(?:^|\n)\s*(?:-?\d+(?:\.\d+)?|Male|Fmale|Female|CAD|Normal|Stenotic)(?:\s*[,;\t]\s*(?:-?\d+(?:\.\d+)?|Male|Fmale|Female|CAD|Normal|Stenotic|N|Y|\?)){7,}",
    re.IGNORECASE,
)


def _assert_exact_keys(
    obj: Any,
    allowed_keys: set[str] | frozenset[str],
    *,
    optional_keys: set[str] | frozenset[str] = frozenset(),
    context: str,
) -> None:
    if not isinstance(obj, dict):
        raise PatientLevelLeakageError(
            f"Strict metadata-only report schema violation at '{context}': expected dict, got {type(obj).__name__}."
        )
    actual_keys = set(str(k) for k in obj.keys())
    unexpected = sorted(actual_keys - (set(allowed_keys) | set(optional_keys)))
    if unexpected:
        raise PatientLevelLeakageError(
            f"Strict metadata-only report schema violation at '{context}': unexpected field(s) {unexpected} rejected."
        )
    missing = sorted(set(allowed_keys) - actual_keys)
    if missing:
        raise PatientLevelLeakageError(
            f"Strict metadata-only report schema violation at '{context}': missing required field(s) {missing}."
        )


def _assert_int_not_bool(val: Any, *, context: str) -> None:
    if not isinstance(val, int) or isinstance(val, bool):
        raise PatientLevelLeakageError(
            f"Strict metadata-only report schema violation at '{context}': expected int count, got {type(val).__name__}."
        )


def _assert_num_not_bool(val: Any, *, context: str) -> None:
    if not isinstance(val, (int, float)) or isinstance(val, bool):
        raise PatientLevelLeakageError(
            f"Strict metadata-only report schema violation at '{context}': expected numeric aggregate, got {type(val).__name__}."
        )


def _validate_within_duplicates_schema(dup_obj: Any, *, context: str) -> None:
    _assert_exact_keys(
        dup_obj,
        {
            "dataset_label",
            "total_rows_screened",
            "observed_exact_full_row_duplicate_groups",
            "observed_exact_full_row_excess_records",
            "observed_exact_full_row_pairs",
            "observed_exact_predictor_duplicate_groups",
            "observed_exact_predictor_excess_records",
            "observed_exact_predictor_pairs",
            "observed_near_duplicate_candidate_pairs",
            "evidence_status",
        },
        context=context,
    )
    for count_key in (
        "total_rows_screened",
        "observed_exact_full_row_duplicate_groups",
        "observed_exact_full_row_excess_records",
        "observed_exact_full_row_pairs",
        "observed_exact_predictor_duplicate_groups",
        "observed_exact_predictor_excess_records",
        "observed_exact_predictor_pairs",
        "observed_near_duplicate_candidate_pairs",
    ):
        _assert_int_not_bool(dup_obj[count_key], context=f"{context}.{count_key}")


def _validate_uci_412_411_audit_schema(ds_id: str, payload: Any) -> None:
    ctx = f"dataset_audits.{ds_id}"
    _assert_exact_keys(
        payload,
        {
            "dataset_id",
            "filename",
            "sheet_names",
            "inspected_sheet",
            "row_count",
            "feature_count_reconciliation",
            "class_distribution",
            "missingness",
            "inferred_column_types",
            "invalid_codings_by_column",
            "suspicious_values_by_column",
            "leakage_and_availability_flags",
            "within_dataset_duplicates",
            "evidence_status",
        },
        optional_keys={"artery_to_cath_consistency"},
        context=ctx,
    )
    _assert_int_not_bool(payload["row_count"], context=f"{ctx}.row_count")

    rec = payload["feature_count_reconciliation"]
    _assert_exact_keys(
        rec,
        {
            "total_columns_in_sheet",
            "predictor_columns_count",
            "target_columns_count",
            "artery_extension_columns_count",
            "bbb_column_present",
            "group_counts",
            "discrepancy_explanation",
            "evidence_status",
        },
        context=f"{ctx}.feature_count_reconciliation",
    )

    cls_d = payload["class_distribution"]
    _assert_exact_keys(
        cls_d,
        {"target_column", "raw_counts", "provisional_t1_binary"},
        context=f"{ctx}.class_distribution",
    )
    _assert_exact_keys(
        cls_d["raw_counts"],
        {"CAD", "Normal"},
        context=f"{ctx}.class_distribution.raw_counts",
    )
    _assert_int_not_bool(cls_d["raw_counts"]["CAD"], context=f"{ctx}.class_distribution.raw_counts.CAD")
    _assert_int_not_bool(cls_d["raw_counts"]["Normal"], context=f"{ctx}.class_distribution.raw_counts.Normal")
    _assert_exact_keys(
        cls_d["provisional_t1_binary"],
        {"cad_present_1", "cad_absent_0", "cad_prevalence_ratio"},
        context=f"{ctx}.class_distribution.provisional_t1_binary",
    )

    miss = payload["missingness"]
    _assert_exact_keys(
        miss,
        {"total_missing_cells", "columns_with_missing_count", "per_column_missing"},
        context=f"{ctx}.missingness",
    )
    _assert_int_not_bool(miss["total_missing_cells"], context=f"{ctx}.missingness.total_missing_cells")
    _assert_int_not_bool(miss["columns_with_missing_count"], context=f"{ctx}.missingness.columns_with_missing_count")
    if not isinstance(miss["per_column_missing"], dict):
        raise PatientLevelLeakageError(f"Expected dict at '{ctx}.missingness.per_column_missing'.")
    for col_k, col_m in miss["per_column_missing"].items():
        if col_k not in KNOWN_UCI_412_411_COLUMNS:
            raise PatientLevelLeakageError(
                f"Unknown column '{col_k}' in '{ctx}.missingness.per_column_missing'."
            )
        _assert_exact_keys(
            col_m,
            {"null_or_blank", "question_mark", "minus_nine_sentinel"},
            context=f"{ctx}.missingness.per_column_missing.{col_k}",
        )
        for mk, mv in col_m.items():
            _assert_int_not_bool(mv, context=f"{ctx}.missingness.per_column_missing.{col_k}.{mk}")

    inf_types = payload["inferred_column_types"]
    if not isinstance(inf_types, dict):
        raise PatientLevelLeakageError(f"Expected dict at '{ctx}.inferred_column_types'.")
    for col_k, t_val in inf_types.items():
        if col_k not in KNOWN_UCI_412_411_COLUMNS:
            raise PatientLevelLeakageError(f"Unknown column '{col_k}' in '{ctx}.inferred_column_types'.")
        if t_val not in {"integer", "float", "categorical_string", "all_missing"}:
            raise PatientLevelLeakageError(
                f"Disallowed non-enum value '{t_val}' in '{ctx}.inferred_column_types.{col_k}'."
            )

    for count_map_key in ("invalid_codings_by_column", "suspicious_values_by_column"):
        cmap = payload[count_map_key]
        if not isinstance(cmap, dict):
            raise PatientLevelLeakageError(f"Expected dict at '{ctx}.{count_map_key}'.")
        for col_k, cnt_v in cmap.items():
            if col_k not in KNOWN_UCI_412_411_COLUMNS:
                raise PatientLevelLeakageError(f"Unknown column '{col_k}' in '{ctx}.{count_map_key}'.")
            _assert_int_not_bool(cnt_v, context=f"{ctx}.{count_map_key}.{col_k}")

    _assert_exact_keys(
        payload["leakage_and_availability_flags"],
        {
            "target_column",
            "artery_leakage_columns_present",
            "echo_features_requiring_timing_ruling",
            "lab_features_requiring_dictionary_and_timing_ruling",
        },
        context=f"{ctx}.leakage_and_availability_flags",
    )
    _validate_within_duplicates_schema(
        payload["within_dataset_duplicates"],
        context=f"{ctx}.within_dataset_duplicates",
    )
    if "artery_to_cath_consistency" in payload:
        _assert_exact_keys(
            payload["artery_to_cath_consistency"],
            {"consistent_rows", "inconsistent_rows"},
            context=f"{ctx}.artery_to_cath_consistency",
        )


def _validate_uci_45_audit_schema(payload: Any) -> None:
    ctx = "dataset_audits.DA-A2"
    _assert_exact_keys(
        payload,
        {
            "dataset_id",
            "processed_cleveland_benchmark_confirmed",
            "processed_files",
            "raw_files",
            "raw_vs_processed_correspondence",
            "quarantined_raw_files",
            "documentation_file",
            "evidence_status",
        },
        context=ctx,
    )
    if not isinstance(payload["processed_files"], dict):
        raise PatientLevelLeakageError(f"Expected dict at '{ctx}.processed_files'.")
    allowed_proc_files = {
        "processed.cleveland.data",
        "processed.hungarian.data",
        "processed.switzerland.data",
        "processed.va.data",
    }
    for p_fname, p_rep in payload["processed_files"].items():
        if p_fname not in allowed_proc_files:
            raise PatientLevelLeakageError(f"Unexpected processed file key '{p_fname}' in '{ctx}.processed_files'.")
        p_ctx = f"{ctx}.processed_files.{p_fname}"
        _assert_exact_keys(
            p_rep,
            {
                "filename",
                "cohort",
                "format",
                "intended_role",
                "conventional_14_schema_confirmed",
                "columns",
                "documented_expected_rows",
                "row_count",
                "class_distribution",
                "missingness",
                "invalid_codings_by_column",
                "suspicious_values",
                "leakage_and_availability_flags",
                "within_dataset_duplicates",
                "evidence_status",
            },
            context=p_ctx,
        )
        _assert_int_not_bool(p_rep["row_count"], context=f"{p_ctx}.row_count")
        _assert_exact_keys(
            p_rep["class_distribution"],
            {"target_column", "raw_num_counts", "uses_pre_binarized_0_1_coding", "provisional_t1_binary_0_vs_1_to_4"},
            context=f"{p_ctx}.class_distribution",
        )
        _assert_exact_keys(
            p_rep["missingness"],
            {"total_missing_cells", "overall_cell_completeness_ratio", "columns_with_missing_count", "per_column_missing"},
            context=f"{p_ctx}.missingness",
        )
        for col_k, cnt_v in p_rep["invalid_codings_by_column"].items():
            if col_k not in UCI_45_CONVENTIONAL_14_COLUMNS:
                raise PatientLevelLeakageError(f"Unexpected column '{col_k}' in '{p_ctx}.invalid_codings_by_column'.")
            _assert_int_not_bool(cnt_v, context=f"{p_ctx}.invalid_codings_by_column.{col_k}")
        for susp_k, susp_v in p_rep["suspicious_values"].items():
            _assert_int_not_bool(susp_v, context=f"{p_ctx}.suspicious_values.{susp_k}")
        _validate_within_duplicates_schema(
            p_rep["within_dataset_duplicates"],
            context=f"{p_ctx}.within_dataset_duplicates",
        )

    quarantined = payload["quarantined_raw_files"]
    if not isinstance(quarantined, list) or len(quarantined) > 1:
        raise PatientLevelLeakageError("DA-A2 quarantine metadata must be a list of at most one item.")
    if quarantined:
        q = quarantined[0]
        _assert_exact_keys(
            q,
            {
                "filename", "quarantine_reason", "provenance_sha256",
                "provenance_size_bytes", "raw_parsed",
                "raw_processed_correspondence_evaluated", "evidence_status",
            },
            context=f"{ctx}.quarantined_raw_files[0]",
        )
        if q["filename"] != "cleveland.data" or q["quarantine_reason"] != (
            "SOURCE_REPORTED_INTEGRITY_CONCERN_AND_NON_UTF8_INPUT"
        ):
            raise PatientLevelLeakageError("Only documented raw Cleveland quarantine is permitted.")
        if (not isinstance(q["provenance_sha256"], str)
                or not re.fullmatch(r"[0-9a-f]{64}", q["provenance_sha256"])):
            raise PatientLevelLeakageError("Quarantine SHA-256 must be a lowercase 64-hex digest.")
        _assert_int_not_bool(q["provenance_size_bytes"], context="DA-A2 quarantined file size")
        if q["provenance_size_bytes"] <= 0:
            raise PatientLevelLeakageError("Quarantined file size must be positive.")
        if q["raw_parsed"] is not False or q["raw_processed_correspondence_evaluated"] is not False:
            raise PatientLevelLeakageError("Quarantined raw Cleveland cannot be parsed or compared.")
        if q["evidence_status"] != "REQUIRES APPROVAL" or payload["evidence_status"] != "REQUIRES APPROVAL":
            raise PatientLevelLeakageError("Partial DA-A2 audit must not be labelled VERIFIED.")
        if "cleveland.data" in payload["raw_files"] or "cleveland" in payload["raw_vs_processed_correspondence"]:
            raise PatientLevelLeakageError("Quarantined raw Cleveland cannot appear in verified raw reports.")
    else:
        if payload["evidence_status"] != "VERIFIED":
            raise PatientLevelLeakageError("Unquarantined DA-A2 audit must remain fully verified.")

    if not isinstance(payload["raw_files"], dict):
        raise PatientLevelLeakageError(f"Expected dict at '{ctx}.raw_files'.")
    allowed_raw_files = {"cleveland.data", "hungarian.data", "switzerland.data", "long-beach-va.data"}
    for r_fname, r_rep in payload["raw_files"].items():
        if r_fname not in allowed_raw_files:
            raise PatientLevelLeakageError(f"Unexpected raw file key '{r_fname}' in '{ctx}.raw_files'.")
        r_ctx = f"{ctx}.raw_files.{r_fname}"
        _assert_exact_keys(
            r_rep,
            {
                "filename",
                "cohort",
                "format",
                "intended_role",
                "raw_76_attribute_schema_confirmed",
                "attribute_count",
                "documented_expected_rows",
                "row_count",
                "dummy_name_attribute_76_verified_all_rows",
                "class_distribution",
                "missingness",
                "leakage_and_identifier_audit",
                "evidence_status",
            },
            context=r_ctx,
        )
        _assert_int_not_bool(r_rep["row_count"], context=f"{r_ctx}.row_count")

    for coh_k, coh_rep in payload["raw_vs_processed_correspondence"].items():
        if coh_k not in {"cleveland", "hungarian", "switzerland", "va"}:
            raise PatientLevelLeakageError(f"Unexpected cohort '{coh_k}' in '{ctx}.raw_vs_processed_correspondence'.")
        _assert_exact_keys(
            coh_rep,
            {
                "cohort",
                "raw_row_count",
                "processed_row_count",
                "row_counts_equal",
                "positional_13_predictor_matches",
                "positional_14_col_exact_num_matches",
                "positional_14_col_binary_num_matches",
                "num_recoded_to_binary_in_processed",
                "evidence_status",
            },
            context=f"{ctx}.raw_vs_processed_correspondence.{coh_k}",
        )

    _assert_exact_keys(
        payload["documentation_file"],
        {
            "filename",
            "format",
            "intended_role",
            "line_count",
            "documents_76_attributes",
            "documents_minus_9_missing_code",
            "contains_patient_rows",
            "evidence_status",
        },
        context=f"{ctx}.documentation_file",
    )


def _validate_uci_145_audit_schema(payload: Any) -> None:
    ctx = "dataset_audits.DA-B2"
    _assert_exact_keys(
        payload,
        {
            "dataset_id",
            "filename",
            "permitted_role",
            "never_training_or_external_validation_by_audit_grant",
            "row_count",
            "documented_expected_rows",
            "class_distribution",
            "missingness",
            "invalid_codings_by_column",
            "suspicious_values",
            "leakage_and_availability_flags",
            "within_dataset_duplicates",
            "evidence_status",
        },
        context=ctx,
    )
    _assert_int_not_bool(payload["row_count"], context=f"{ctx}.row_count")
    _validate_within_duplicates_schema(
        payload["within_dataset_duplicates"],
        context=f"{ctx}.within_dataset_duplicates",
    )


def validate_strict_metadata_report_schema(report_dict: dict[str, Any]) -> None:
    """Primary report privacy control: enforce a strict allowlisted schema of metadata and aggregate counts.

    Rejects any unexpected top-level or nested dictionary keys, unsupported object structures,
    or unapproved dataset audit payloads.
    """
    _assert_exact_keys(report_dict, ALLOWED_TOP_LEVEL_REPORT_KEYS, context="report_root")

    if not isinstance(report_dict["is_synthetic_fixture_run"], bool):
        raise PatientLevelLeakageError("report_root.is_synthetic_fixture_run must be a boolean.")

    cert = report_dict["safety_and_non_fitting_certification"]
    _assert_exact_keys(
        cert,
        {
            "model_fitting_performed",
            "feature_selection_performed",
            "hyperparameter_tuning_performed",
            "performance_evaluation_performed",
            "calibration_performed",
            "shap_or_lime_computed",
            "patient_level_rows_emitted",
            "originals_byte_identical",
            "supervisor_approval_claimed",
            "local_file_integrity_status",
            "official_source_provenance_status",
            "privacy_controls_and_limitations",
            "evidence_status",
        },
        context="safety_and_non_fitting_certification",
    )
    if cert["patient_level_rows_emitted"] != 0:
        raise PatientLevelLeakageError("safety_and_non_fitting_certification.patient_level_rows_emitted must be 0.")

    gov = report_dict["governance_and_authorization"]
    _assert_exact_keys(
        gov,
        {
            "governance_decision_id",
            "workflow_status",
            "supervisor_review_status",
            "supervisor_approval_claimed",
            "gate_pt_status",
            "internal_exploratory_protocol_proposal",
            "datasets",
        },
        context="governance_and_authorization",
    )
    if not isinstance(gov["datasets"], dict):
        raise PatientLevelLeakageError("governance_and_authorization.datasets must be a dict.")
    for ds_id, ds_meta in gov["datasets"].items():
        if ds_id not in {"DA-A1", "DA-A2", "DA-B1", "DA-B2"}:
            raise PatientLevelLeakageError(f"Unknown dataset '{ds_id}' in governance_and_authorization.datasets.")
        _assert_exact_keys(
            ds_meta,
            {
                "dataset_id",
                "uci_id",
                "title",
                "doi",
                "official_source_url",
                "authorized_files",
                "permitted_role",
                "never_independent_cohort",
                "never_training_or_external_validation_by_audit_grant",
                "authorization_status",
                "authorized_by",
                "authorized_date",
                "responsible_acquirer",
                "audit_reviewer",
                "environment",
                "evidence_status",
            },
            context=f"governance_and_authorization.datasets.{ds_id}",
        )

    _assert_exact_keys(
        report_dict["git_ignore_verification"],
        {
            "repo_root",
            "checked_paths",
            "ignore_rules_matched",
            "tracked_files_under_data",
            "passed",
            "evidence_status",
        },
        context="git_ignore_verification",
    )

    if not isinstance(report_dict["byte_identity_snapshots"], list):
        raise PatientLevelLeakageError("byte_identity_snapshots must be a list.")
    for idx, snap in enumerate(report_dict["byte_identity_snapshots"]):
        _assert_exact_keys(
            snap,
            {"filename", "relative_path", "pre_sha256", "post_sha256", "size_bytes", "byte_identical"},
            context=f"byte_identity_snapshots[{idx}]",
        )

    ds_audits = report_dict["dataset_audits"]
    if not isinstance(ds_audits, dict):
        raise PatientLevelLeakageError("dataset_audits must be a dict.")
    for ds_id, ds_payload in ds_audits.items():
        if ds_id in ("DA-A1", "DA-B1"):
            _validate_uci_412_411_audit_schema(ds_id, ds_payload)
        elif ds_id == "DA-A2":
            _validate_uci_45_audit_schema(ds_payload)
        elif ds_id == "DA-B2":
            _validate_uci_145_audit_schema(ds_payload)
        else:
            raise PatientLevelLeakageError(f"Unexpected dataset key '{ds_id}' in dataset_audits.")

    cross_dup = report_dict["cross_cohort_duplicate_and_overlap_analysis"]
    _assert_exact_keys(
        cross_dup,
        {"methods_documented", "pairwise_cross_cohort_summary", "independence_and_overlap_distinction"},
        context="cross_cohort_duplicate_and_overlap_analysis",
    )
    for idx, pair_item in enumerate(cross_dup["pairwise_cross_cohort_summary"]):
        _assert_exact_keys(
            pair_item,
            {
                "cohort_a",
                "cohort_b",
                "rows_a",
                "rows_b",
                "observed_exact_13_predictor_distinct_profiles",
                "observed_exact_13_predictor_rows_in_a",
                "observed_exact_13_predictor_rows_in_b",
                "observed_exact_11_predictor_no_ca_thal_distinct_profiles",
                "observed_exact_11_predictor_rows_in_a",
                "observed_exact_11_predictor_rows_in_b",
                "observed_near_duplicate_candidate_cross_pairs",
                "evidence_status",
            },
            context=f"cross_cohort_duplicate_and_overlap_analysis.pairwise_cross_cohort_summary[{idx}]",
        )

    corr_411 = report_dict["uci_411_412_correspondence"]
    _assert_exact_keys(
        corr_411,
        {
            "register_id",
            "same_cohort_provenance_status",
            "same_cohort_provenance_basis",
            "never_independent_cohort",
            "never_training_or_external_validation_for_uci_412",
            "sample_size_summation_prohibited",
            "da_b1_authorized",
            "row_correspondence_evaluated",
            "row_correspondence_evidence_status",
        },
        optional_keys={
            "note",
            "uci_412_row_count",
            "uci_411_row_count",
            "shared_columns_count",
            "columns_only_in_uci_411",
            "columns_only_in_uci_412",
            "positional_exact_match_count",
            "unordered_exact_match_count",
            "exact_1_to_1_positional_alignment",
            "uci_411_artery_to_cath_consistent_rows",
            "uci_411_artery_to_cath_inconsistent_rows",
        },
        context="uci_411_412_correspondence",
    )

    stat_ovl = report_dict["uci_145_cleveland_overlap"]
    _assert_exact_keys(
        stat_ovl,
        {
            "register_id",
            "never_training_or_external_validation_by_audit_grant",
            "prohibited_roles",
            "da_b2_authorized",
            "investigation_status",
            "evidence_status",
        },
        optional_keys={
            "note",
            "cleveland_row_count",
            "statlog_row_count",
            "exact_13_predictor_plus_binary_target_statlog_rows",
            "exact_13_predictor_plus_binary_target_cleveland_rows",
            "exact_13_predictor_statlog_rows",
            "exact_11_predictor_no_ca_thal_statlog_rows",
            "near_duplicate_cross_pairs",
            "statlog_exact_13_predictor_overlap_fraction",
        },
        context="uci_145_cleveland_overlap",
    )

    if not isinstance(report_dict["feature_availability_and_leakage_table"], list):
        raise PatientLevelLeakageError("feature_availability_and_leakage_table must be a list.")
    for idx, f_row in enumerate(report_dict["feature_availability_and_leakage_table"]):
        _assert_exact_keys(
            f_row,
            {
                "register_id",
                "dataset_scope",
                "feature_or_group",
                "category",
                "pre_angiography_availability",
                "ruling",
                "evidence_status",
                "notes",
            },
            context=f"feature_availability_and_leakage_table[{idx}]",
        )

    _assert_exact_keys(
        report_dict["target_harmonization_and_threshold_boundary"],
        {"issue_id", "title", "uci_45_wording", "uci_412_wording", "boundary_50_percent_status", "related_harmonization_rules"},
        context="target_harmonization_and_threshold_boundary",
    )
    _assert_exact_keys(
        report_dict["source_reported_baseline_notes"],
        {"uci_412_literature_class_balance", "paper_performance_numbers_status", "evidence_status"},
        context="source_reported_baseline_notes",
    )


def _walk_keys(obj: Any, path_prefix: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            full_k = f"{path_prefix}.{k}" if path_prefix else str(k)
            if str(k) in FORBIDDEN_REPORT_KEYS:
                found.append(full_k)
            found.extend(_walk_keys(v, full_k))
    elif isinstance(obj, (list, tuple)):
        for idx, item in enumerate(obj):
            found.extend(_walk_keys(item, f"{path_prefix}[{idx}]"))
    elif not isinstance(obj, (str, int, float, bool, type(None))):
        found.append(f"{path_prefix}<unsupported_type:{type(obj).__name__}>")
    return found


def verify_report_no_patient_rows(
    report_dict: dict[str, Any],
    markdown_text: str,
    *,
    enforce_strict_schema: bool = True,
    forbidden_row_fingerprints: Sequence[str] = (),
    forbidden_substrings: Sequence[str] = (),
) -> None:
    """Validate report privacy controls: strict metadata schema (primary) + pattern/fingerprint scanner (secondary)."""
    if not isinstance(report_dict, dict):
        raise PatientLevelLeakageError("Report root must be a dict.")

    bad_keys = _walk_keys(report_dict)
    if bad_keys:
        raise PatientLevelLeakageError(
            f"Report dictionary contains forbidden patient-row key(s) or unsupported object type(s): {bad_keys}"
        )

    if enforce_strict_schema:
        validate_strict_metadata_report_schema(report_dict)

    serialized_json = json.dumps(report_dict, sort_keys=True)
    for blob_label, blob in (("json_report", serialized_json), ("markdown_report", markdown_text)):
        if RAW_COMMA_14_LINE_RE.search(blob):
            raise PatientLevelLeakageError(
                f"Detected a raw 14-column comma-delimited data line inside {blob_label}!"
            )
        if RAW_SPACE_14_LINE_RE.search(blob):
            raise PatientLevelLeakageError(
                f"Detected a raw 14-column whitespace-delimited data line inside {blob_label}!"
            )
        if RAW_76_FRAGMENT_LINE_RE.search(blob):
            raise PatientLevelLeakageError(
                f"Detected a multi-token raw 76-attribute patient record fragment inside {blob_label}!"
            )
        if GENERIC_MULTI_COLUMN_ROW_RE.search(blob):
            raise PatientLevelLeakageError(
                f"Detected a multi-column patient record line inside {blob_label}!"
            )
        for fp in forbidden_row_fingerprints:
            cleaned_fp = fp.strip()
            if len(cleaned_fp) >= 12 and cleaned_fp in blob:
                raise PatientLevelLeakageError(
                    f"Detected a patient-level row fingerprint inside {blob_label}! Aborting report generation."
                )
        for sub in forbidden_substrings:
            if sub and sub in blob:
                raise PatientLevelLeakageError(
                    f"Detected forbidden patient-level value substring inside {blob_label}! Aborting report generation."
                )


def render_markdown_report(report: dict[str, Any]) -> str:
    """Render a metadata-only Markdown audit report suitable for GitHub PR review."""
    mode = report.get("execution_mode", "DRY_RUN_PREFLIGHT")
    gov = report.get("governance_and_authorization", {})
    cert = report.get("safety_and_non_fitting_certification", {})
    git_chk = report.get("git_ignore_verification", {})

    lines: list[str] = [
        "# CardioAssist AI — M2a Metadata-Only Dataset Audit Report",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Execution Mode | `{mode}` |",
        f"| Governance Decision | `{gov.get('governance_decision_id', 'D-046')}` (`{gov.get('workflow_status')}`) |",
        f"| Supervisor Review Status | `{gov.get('supervisor_review_status')}` (Supervisor approval claimed: `{gov.get('supervisor_approval_claimed')}`) |",
        f"| Gate PT Status | `{gov.get('gate_pt_status')}` |",
        f"| Internal Exploratory Proposal | `{gov.get('internal_exploratory_protocol_proposal', {}).get('proposal_id')}` (`{gov.get('internal_exploratory_protocol_proposal', {}).get('status')}`) |",
        f"| Model Fitting Performed | `{cert.get('model_fitting_performed')}` |",
        f"| Patient-Level Rows Emitted | `{cert.get('patient_level_rows_emitted')}` |",
        f"| Originals Byte-Identical | `{cert.get('originals_byte_identical')}` |",
        f"| Privacy Controls & Limitations | `{cert.get('privacy_controls_and_limitations')}` |",
        f"| Synthetic Test Fixture Run | `{report.get('is_synthetic_fixture_run', False)}` |",
        "",
        "## 1. Evidence-Status Taxonomy",
        "",
        "- **VERIFIED**: Checked directly against the repository, `.gitignore`, or authorized local files by this read-only toolchain.",
        "- **SOURCE-REPORTED**: Recorded from `research/source_materials/literature_review_status.csv` or official UCI landing-page summaries prior to local file inspection; never cited as project model performance.",
        "- **UNVERIFIED**: Not yet established by local file inspection or primary-source evidence.",
        "- **REQUIRES APPROVAL**: Blocked on explicit human maintainer Gate DA acceptance (D-046 / P-2), clinician review (P-4), or academic supervisor Gate PT sign-off (P-3).",
        "- **Provenance vs Local Integrity Distinction**: Local file SHA-256 digests and byte sizes are `VERIFIED` on disk before and after the read-only audit; however, a human-entered `official_source_url`, `downloaded_at_utc`, or newly generated local SHA-256 is recorded as `HUMAN_ATTESTED_NOT_INDEPENDENTLY_PROVEN_BY_LOCAL_HASH` (never treated as independent cryptographic proof of upstream origin).",
        "- **Report Privacy Controls & Limitations**: Reports enforce a strict allowlisted metadata-only schema (`validate_strict_metadata_report_schema`) as the primary control and a multi-format pattern/fingerprint scanner (`verify_report_no_patient_rows`) as a secondary defense-in-depth safeguard. Because heuristic scanners are not a formal proof against arbitrary free-text encodings, human maintainer inspection of any generated report remains required before PR sharing.",
        "",
        "## 2. Git-Ignore and Data Custody Verification",
        "",
        f"- **Status**: `{git_chk.get('evidence_status', EVIDENCE_VERIFIED)}` (Passed: `{git_chk.get('passed')}`)",
        f"- **Tracked files under `/data/`**: `{len(git_chk.get('tracked_files_under_data', []))}`",
        "- **Matched `.gitignore` rules**:",
    ]
    for rule in git_chk.get("ignore_rules_matched", []):
        lines.append(f"  - `{rule}`")

    lines.extend(
        [
            "",
            "## 3. Proposed Gate DA Dataset Access Status (D-046)",
            "",
            "| Dataset ID | UCI ID | DOI | Permitted Role | Current Status | Training / Ext-Val Allowed? | Evidence Label |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    for ds_id, ds_info in gov.get("datasets", {}).items():
        lines.append(
            f"| `{ds_id}` | `{ds_info.get('uci_id')}` | `{ds_info.get('doi')}` | "
            f"`{ds_info.get('permitted_role')}` | **{ds_info.get('authorization_status')}** | "
            f"`False / False` | `{ds_info.get('evidence_status', EVIDENCE_REQUIRES_APPROVAL)}` |"
        )

    lines.extend(
        [
            "",
            "## 4. Dataset Audit Summaries (Aggregate Metadata Only)",
            "",
        ]
    )
    ds_audits = report.get("dataset_audits", {})
    if not ds_audits:
        lines.append(
            f"- **No dataset files were read (`{mode}`).** Real dataset acquisition and local audit remain "
            f"**{EVIDENCE_REQUIRES_APPROVAL}** until the maintainer approves D-046 and executes the Windows handoff."
        )
    else:
        for ds_id, ds_payload in ds_audits.items():
            lines.append(f"### {ds_id}")
            lines.append(f"- **Evidence Status**: `{ds_payload.get('evidence_status', EVIDENCE_VERIFIED)}`")
            if ds_id in ("DA-A1", "DA-B1"):
                rec = ds_payload.get("feature_count_reconciliation", {})
                cls_d = ds_payload.get("class_distribution", {})
                miss = ds_payload.get("missingness", {})
                dups = ds_payload.get("within_dataset_duplicates", {})
                lines.append(f"- **Filename**: `{ds_payload.get('filename')}` (Sheet: `{ds_payload.get('inspected_sheet')}`)")
                lines.append(f"- **Row Count**: `{ds_payload.get('row_count')}`")
                lines.append(
                    f"- **Feature-Count Reconciliation**: `{rec.get('total_columns_in_sheet')}` total columns "
                    f"(`{rec.get('predictor_columns_count')}` predictors, `BBB` present=`{rec.get('bbb_column_present')}`)"
                )
                lines.append(
                    f"- **Class Distribution (`Cath`)**: `{cls_d.get('raw_counts')}` "
                    f"(CAD prevalence ratio: `{cls_d.get('provisional_t1_binary', {}).get('cad_prevalence_ratio')}`)"
                )
                lines.append(
                    f"- **Missingness**: `{miss.get('total_missing_cells')}` missing cells across "
                    f"`{miss.get('columns_with_missing_count')}` column(s)"
                )
                lines.append(
                    f"- **Within-Dataset Duplicates**: exact full-row pairs=`{dups.get('observed_exact_full_row_pairs')}`, "
                    f"exact predictor pairs=`{dups.get('observed_exact_predictor_pairs')}`, "
                    f"near-duplicate candidate pairs=`{dups.get('observed_near_duplicate_candidate_pairs')}`"
                )
            elif ds_id == "DA-A2":
                lines.append(
                    f"- **`processed.cleveland.data` Conventional 14-Column Benchmark Confirmed**: "
                    f"`{ds_payload.get('processed_cleveland_benchmark_confirmed')}`"
                )
                lines.append("- **Per-File Summary**:")
                for fname, finfo in ds_payload.get("processed_files", {}).items():
                    c_dist = finfo.get("class_distribution", {}).get("provisional_t1_binary_0_vs_1_to_4", {})
                    m_info = finfo.get("missingness", {})
                    lines.append(
                        f"  - `{fname}` (`{finfo.get('intended_role')}`): rows=`{finfo.get('row_count')}`, "
                        f"CAD_absent_0=`{c_dist.get('cad_absent_0')}`, CAD_present_1_4=`{c_dist.get('cad_present_1_to_4')}`, "
                        f"missing_cells=`{m_info.get('total_missing_cells')}`, "
                        f"suspicious_counts=`{finfo.get('suspicious_values')}`"
                    )
                if ds_payload.get("quarantined_raw_files"):
                    lines.append(
                        "- **PARTIAL AUDIT — RAW CLEVELAND QUARANTINED**: "
                        "The source-warned `cleveland.data` was NOT parsed, and Cleveland "
                        "raw-to-processed correspondence was NOT evaluated. No reliability, "
                        "clinical eligibility, or training authorization is implied."
                    )
                for fname, rinfo in ds_payload.get("raw_files", {}).items():
                    m_info = rinfo.get("missingness", {})
                    lines.append(
                        f"  - `{fname}` (`{rinfo.get('intended_role')}`): rows=`{rinfo.get('row_count')}`, "
                        f"76-attr confirmed=`{rinfo.get('raw_76_attribute_schema_confirmed')}`, "
                        f"dummy `#76 name` verified=`{rinfo.get('dummy_name_attribute_76_verified_all_rows')}`, "
                        f"missing_cells_across_76=`{m_info.get('total_missing_cells_across_76_attrs')}`"
                    )
            elif ds_id == "DA-B2":
                cls_d = ds_payload.get("class_distribution", {})
                lines.append(
                    f"- **Filename**: `{ds_payload.get('filename')}` (`{ds_payload.get('permitted_role')}`)"
                )
                lines.append(
                    f"- **Row Count**: `{ds_payload.get('row_count')}`; Raw Counts: `{cls_d.get('raw_counts')}`"
                )

    corr_411 = report.get("uci_411_412_correspondence", {})
    stat_ovl = report.get("uci_145_cleveland_overlap", {})
    cross_dup = report.get("cross_cohort_duplicate_and_overlap_analysis", {})
    indep = cross_dup.get("independence_and_overlap_distinction", {})

    lines.extend(
        [
            "",
            "## 5. Duplicate Screening, Same-Cohort Provenance, and Overlap Investigation",
            "",
            f"- **Proven Independence Claim Permitted**: `{indep.get('proven_independence_claim_permitted', False)}` "
            f"(`{indep.get('evidence_status', EVIDENCE_VERIFIED)}`)",
            f"- **Scientific Rule**: {indep.get('scientific_rule')}",
            f"- **UCI-411 ↔ UCI-412 Same-Cohort Provenance (`L-04`)**: `{corr_411.get('same_cohort_provenance_status')}` "
            f"(Never independent cohort: `{corr_411.get('never_independent_cohort')}`; "
            f"Row correspondence evaluated: `{corr_411.get('row_correspondence_evaluated')}`; "
            f"Status: `{corr_411.get('row_correspondence_evidence_status')}`)",
            f"- **UCI-145 Statlog ↔ Cleveland Overlap (`L-05`)**: `{stat_ovl.get('investigation_status')}` "
            f"(DA-B2 authorized: `{stat_ovl.get('da_b2_authorized')}`; "
            f"Evidence status: `{stat_ovl.get('evidence_status')}`; "
            f"Never training/external-validation by audit grant: `{stat_ovl.get('never_training_or_external_validation_by_audit_grant')}`)",
            "",
            "## 6. Feature Availability and Leakage Review Table",
            "",
            "| Register ID | Dataset Scope | Feature / Group | Pre-Angiography Availability | Ruling | Evidence Status |",
            "|---|---|---|---|---|---|",
        ]
    )
    for row in report.get("feature_availability_and_leakage_table", []):
        lines.append(
            f"| `{row['register_id']}` | {row['dataset_scope']} | `{row['feature_or_group']}` | "
            f"`{row['pre_angiography_availability']}` | **{row['ruling']}** | `{row['evidence_status']}` |"
        )

    harm = report.get("target_harmonization_and_threshold_boundary", {})
    b50 = harm.get("boundary_50_percent_status", {})
    lines.extend(
        [
            "",
            "## 7. UCI-45 (`>50%`) vs UCI-412 (`>=50%`) Threshold Wording and 50% Boundary Status (H-01)",
            "",
            f"- **UCI-45 (`num`) Wording**: `{harm.get('uci_45_wording', {}).get('inequality_operator')}` "
            f"(`{harm.get('uci_45_wording', {}).get('wording_evidence_status')}`)",
            f"- **UCI-412 (`Cath`) Wording**: `{harm.get('uci_412_wording', {}).get('inequality_operator')}` "
            f"(`{harm.get('uci_412_wording', {}).get('wording_evidence_status')}`)",
            f"- **50% Boundary Reconciliation Status**: `{b50.get('reconciliation_status')}` "
            f"(Evidence: `{b50.get('evidence_status')}`; Gate PT Ruling: `{b50.get('gate_pt_ruling_status')}`)",
            f"- **Boundary Note**: {b50.get('explanation')}",
            "",
        ]
    )
    return "\n".join(lines)


def build_and_verify_reports(
    *,
    execution_mode: str,
    auth_manifest: dict[str, Any],
    git_ignore_result: dict[str, Any],
    dataset_audits: dict[str, Any],
    cross_cohort_duplicates: dict[str, Any],
    uci_411_412_correspondence: dict[str, Any],
    uci_145_cleveland_overlap: dict[str, Any],
    byte_identity_snapshots: Sequence[dict[str, Any]],
    is_synthetic_fixture_run: bool = False,
    forbidden_row_fingerprints: Sequence[str] = (),
    forbidden_substrings: Sequence[str] = (),
    base_root: Path | None = None,
    repo_root: Path | None = None,
    allow_external_tmp_root: Path | None = None,
    json_output_path: Path | str | None = None,
    markdown_output_path: Path | str | None = None,
) -> tuple[dict[str, Any], str]:
    """Validate output paths, assemble metadata-only JSON + Markdown reports, enforce strict schema + redaction scanner, and write outputs."""
    effective_base = (base_root or repo_root or Path(__file__).resolve().parents[2]).resolve()
    effective_repo = (repo_root or Path(__file__).resolve().parents[2]).resolve()

    resolved_json_out: Path | None = None
    resolved_md_out: Path | None = None
    if json_output_path is not None:
        resolved_json_out = validate_and_resolve_report_output_path(
            effective_base,
            json_output_path,
            expected_suffix=".json",
            repo_root=effective_repo,
            allow_external_tmp_root=allow_external_tmp_root,
        )
    if markdown_output_path is not None:
        resolved_md_out = validate_and_resolve_report_output_path(
            effective_base,
            markdown_output_path,
            expected_suffix=".md",
            repo_root=effective_repo,
            allow_external_tmp_root=allow_external_tmp_root,
        )

    datasets_gov_summary: dict[str, Any] = {}
    for ds_id, ds_cfg in auth_manifest.get("datasets", {}).items():
        status_val = ds_cfg.get("authorization_status", "PENDING_HUMAN_ACCEPTANCE")
        ev_label = (
            EVIDENCE_VERIFIED
            if (status_val == "AUTHORIZED_FOR_READ_ONLY_AUDIT" and ds_id in dataset_audits)
            else EVIDENCE_REQUIRES_APPROVAL
        )
        datasets_gov_summary[ds_id] = {
            "dataset_id": ds_id,
            "uci_id": ds_cfg.get("uci_id"),
            "title": ds_cfg.get("title"),
            "doi": ds_cfg.get("doi"),
            "official_source_url": ds_cfg.get("official_source_url"),
            "authorized_files": ds_cfg.get("authorized_files"),
            "permitted_role": ds_cfg.get("permitted_role"),
            "never_independent_cohort": ds_cfg.get("never_independent_cohort"),
            "never_training_or_external_validation_by_audit_grant": ds_cfg.get(
                "never_training_or_external_validation_by_audit_grant"
            ),
            "authorization_status": status_val,
            "authorized_by": ds_cfg.get("authorized_by"),
            "authorized_date": ds_cfg.get("authorized_date"),
            "responsible_acquirer": ds_cfg.get("responsible_acquirer"),
            "audit_reviewer": ds_cfg.get("audit_reviewer"),
            "environment": ds_cfg.get("environment"),
            "evidence_status": ev_label,
        }

    report_dict: dict[str, Any] = {
        "report_schema_version": "1.1.0",
        "milestone": "M2a",
        "execution_mode": execution_mode,
        "is_synthetic_fixture_run": is_synthetic_fixture_run,
        "synthetic_disclaimer": (
            "SYNTHETIC_SOFTWARE_TEST_ONLY_NOT_MEDICAL_OR_MODEL_EVIDENCE"
            if is_synthetic_fixture_run
            else "METADATA_ONLY_READ_ONLY_DATASET_AUDIT"
        ),
        "evidence_labels_supported": sorted(VALID_EVIDENCE_LABELS),
        "safety_and_non_fitting_certification": {
            "model_fitting_performed": False,
            "feature_selection_performed": False,
            "hyperparameter_tuning_performed": False,
            "performance_evaluation_performed": False,
            "calibration_performed": False,
            "shap_or_lime_computed": False,
            "patient_level_rows_emitted": 0,
            "originals_byte_identical": all(
                s.get("byte_identical", False) for s in byte_identity_snapshots
            )
            if byte_identity_snapshots
            else True,
            "supervisor_approval_claimed": False,
            "local_file_integrity_status": LOCAL_INTEGRITY_VERIFIED_STATUS,
            "official_source_provenance_status": SOURCE_ORIGIN_HUMAN_ATTESTED_STATUS,
            "privacy_controls_and_limitations": (
                "STRICT_METADATA_SCHEMA_AND_SECONDARY_PATTERN_SCANNER_VALIDATED_"
                "HUMAN_REVIEW_REQUIRED_BEFORE_PR_SHARING"
            ),
            "evidence_status": EVIDENCE_VERIFIED,
        },
        "governance_and_authorization": {
            "governance_decision_id": auth_manifest.get("governance_decision_id"),
            "workflow_status": auth_manifest.get("workflow_status"),
            "supervisor_review_status": auth_manifest.get("supervisor_review_status"),
            "supervisor_approval_claimed": auth_manifest.get("supervisor_approval_claimed"),
            "gate_pt_status": auth_manifest.get("gate_pt_status"),
            "internal_exploratory_protocol_proposal": auth_manifest.get(
                "internal_exploratory_protocol_proposal"
            ),
            "datasets": datasets_gov_summary,
        },
        "git_ignore_verification": git_ignore_result,
        "byte_identity_snapshots": list(byte_identity_snapshots),
        "dataset_audits": dataset_audits,
        "cross_cohort_duplicate_and_overlap_analysis": cross_cohort_duplicates,
        "uci_411_412_correspondence": uci_411_412_correspondence,
        "uci_145_cleveland_overlap": uci_145_cleveland_overlap,
        "feature_availability_and_leakage_table": [dict(r) for r in FEATURE_AVAILABILITY_AND_LEAKAGE_TABLE],
        "target_harmonization_and_threshold_boundary": TARGET_HARMONIZATION_SPEC,
        "source_reported_baseline_notes": {
            "uci_412_literature_class_balance": "216 CAD / 87 Normal (303 total) as SOURCE-REPORTED in literature.",
            "paper_performance_numbers_status": (
                "All accuracy/AUC figures in literature_review_status.csv (including P7 100% and P14 >97%) "
                "are SOURCE-REPORTED red flags to audit, never project baselines or targets."
            ),
            "evidence_status": EVIDENCE_SOURCE_REPORTED,
        },
    }

    markdown_text = render_markdown_report(report_dict)
    verify_report_no_patient_rows(
        report_dict,
        markdown_text,
        enforce_strict_schema=True,
        forbidden_row_fingerprints=forbidden_row_fingerprints,
        forbidden_substrings=forbidden_substrings,
    )

    if resolved_json_out is not None:
        resolved_json_out.write_text(json.dumps(report_dict, indent=2) + "\n", encoding="utf-8")
    if resolved_md_out is not None:
        resolved_md_out.write_text(markdown_text, encoding="utf-8")

    return report_dict, markdown_text
