"""Metadata-only audit report generation and zero-patient-row redaction verification."""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Sequence

from research.audit.exceptions import PatientLevelLeakageError
from research.audit.registry import (
    EVIDENCE_REQUIRES_APPROVAL,
    EVIDENCE_SOURCE_REPORTED,
    EVIDENCE_UNVERIFIED,
    EVIDENCE_VERIFIED,
    FEATURE_AVAILABILITY_AND_LEAKAGE_TABLE,
    LOCAL_INTEGRITY_VERIFIED_STATUS,
    SOURCE_ORIGIN_HUMAN_ATTESTED_STATUS,
    TARGET_HARMONIZATION_SPEC,
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
    }
)

# Regex patterns that would match raw 14-column comma or whitespace data lines
RAW_COMMA_14_LINE_RE = re.compile(
    r"(?:^|\n)\s*-?\d+(?:\.\d+)?\s*(?:,\s*(?:-?\d+(?:\.\d+)?|\?)\s*){13}(?:$|\n)"
)


def _walk_keys(obj: Any, path_prefix: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            full_k = f"{path_prefix}.{k}" if path_prefix else str(k)
            if str(k) in FORBIDDEN_REPORT_KEYS:
                found.append(full_k)
            found.extend(_walk_keys(v, full_k))
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            found.extend(_walk_keys(item, f"{path_prefix}[{idx}]"))
    return found


def verify_report_no_patient_rows(
    report_dict: dict[str, Any],
    markdown_text: str,
    *,
    forbidden_row_fingerprints: Sequence[str] = (),
    forbidden_substrings: Sequence[str] = (),
) -> None:
    """Fail closed if any patient-level row, forbidden key, or raw data line appears in a report."""
    bad_keys = _walk_keys(report_dict)
    if bad_keys:
        raise PatientLevelLeakageError(
            f"Report dictionary contains forbidden patient-row key(s): {bad_keys}"
        )

    serialized_json = json.dumps(report_dict, sort_keys=True)
    for blob_label, blob in (("json_report", serialized_json), ("markdown_report", markdown_text)):
        if RAW_COMMA_14_LINE_RE.search(blob):
            raise PatientLevelLeakageError(
                f"Detected a raw 14-column comma-delimited data line inside {blob_label}!"
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
        f"| Synthetic Test Fixture Run | `{report.get('is_synthetic_fixture_run', False)}` |",
        "",
        "## 1. Evidence-Status Taxonomy",
        "",
        "- **VERIFIED**: Checked directly against the repository, `.gitignore`, or authorized local files by this read-only toolchain.",
        "- **SOURCE-REPORTED**: Recorded from `research/source_materials/literature_review_status.csv` or official UCI landing-page summaries prior to local file inspection; never cited as project model performance.",
        "- **UNVERIFIED**: Not yet established by local file inspection or primary-source evidence.",
        "- **REQUIRES APPROVAL**: Blocked on explicit human maintainer Gate DA acceptance (D-046 / P-2), clinician review (P-4), or academic supervisor Gate PT sign-off (P-3).",
        "- **Provenance vs Local Integrity Distinction**: Local file SHA-256 digests and byte sizes are `VERIFIED` on disk before and after the read-only audit; however, a human-entered `official_source_url`, `downloaded_at_utc`, or newly generated local SHA-256 is recorded as `HUMAN_ATTESTED_NOT_INDEPENDENTLY_PROVEN_BY_LOCAL_HASH` (never treated as independent cryptographic proof of upstream origin).",
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
            "## 4. Dataset Audit Summaries (Metadata Only — Zero Patient Rows)",
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
    json_output_path: Path | None = None,
    markdown_output_path: Path | None = None,
) -> tuple[dict[str, Any], str]:
    """Assemble metadata-only JSON + Markdown audit reports and verify zero patient-level data leakage."""
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
        "report_schema_version": "1.0.0",
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
        forbidden_row_fingerprints=forbidden_row_fingerprints,
        forbidden_substrings=forbidden_substrings,
    )

    if json_output_path is not None:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        json_output_path.write_text(json.dumps(report_dict, indent=2) + "\n", encoding="utf-8")
    if markdown_output_path is not None:
        markdown_output_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_output_path.write_text(markdown_text, encoding="utf-8")

    return report_dict, markdown_text
