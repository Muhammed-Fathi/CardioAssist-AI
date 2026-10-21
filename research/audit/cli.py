"""Command-line interface and orchestration pipeline for the M2a read-only dataset audit toolchain."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile
from typing import Any, Sequence

from research.audit.duplicates import (
    compute_cross_cohort_duplicates,
    evaluate_uci_411_412_correspondence,
    investigate_statlog_cleveland_overlap,
)
from research.audit.exceptions import AuditError, GovernanceAuthorizationError
from research.audit.git_safety import verify_data_root_containment, verify_git_ignore
from research.audit.provenance import (
    AUTHORIZED_STATUS_VALUE,
    ByteIdentityGuard,
    build_provenance_manifest,
    extract_authorized_archive,
    inspect_zip_archive,
    load_authorization_manifest,
    validate_and_resolve_report_output_path,
    validate_provenance_manifest,
    verify_dataset_authorized_for_audit,
    verify_global_workflow_authorized,
)
from research.audit.registry import UNKNOWN_DOWNLOAD_TIMESTAMP
from research.audit.reporting import build_and_verify_reports
from research.audit.synthetic_fixtures import (
    SYNTHETIC_PLANTED_SENTINEL_FLOAT,
    materialize_synthetic_audit_suite,
)
from research.audit.validators import (
    audit_uci_45_names_file,
    audit_uci_45_processed_file,
    audit_uci_45_raw_file,
    audit_uci_145_statlog_file,
    audit_uci_412_or_411_workbook,
    compare_uci_45_raw_and_processed,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AUTH_MANIFEST_PATH = REPO_ROOT / "research/audit/gate_da_authorization.json"


def run_dry_run_preflight(
    *,
    repo_root: Path = REPO_ROOT,
    base_data_parent: Path | None = None,
    auth_manifest_path: Path = DEFAULT_AUTH_MANIFEST_PATH,
    allow_external_tmp_root: Path | None = None,
    json_output_path: Path | str | None = None,
    markdown_output_path: Path | str | None = None,
) -> tuple[dict[str, Any], str]:
    """Execute dry-run/preflight validation without downloading or reading any dataset files."""
    effective_parent = (base_data_parent or repo_root).resolve()
    if json_output_path is not None:
        validate_and_resolve_report_output_path(
            effective_parent,
            json_output_path,
            expected_suffix=".json",
            repo_root=repo_root,
            allow_external_tmp_root=allow_external_tmp_root,
        )
    if markdown_output_path is not None:
        validate_and_resolve_report_output_path(
            effective_parent,
            markdown_output_path,
            expected_suffix=".md",
            repo_root=repo_root,
            allow_external_tmp_root=allow_external_tmp_root,
        )

    git_res = verify_git_ignore(repo_root)
    auth_manifest = load_authorization_manifest(auth_manifest_path)

    da_b1_auth = (
        auth_manifest["datasets"]["DA-B1"].get("authorization_status") == AUTHORIZED_STATUS_VALUE
    )
    da_b2_auth = (
        auth_manifest["datasets"]["DA-B2"].get("authorization_status") == AUTHORIZED_STATUS_VALUE
    )

    cross_dups = compute_cross_cohort_duplicates({})
    corr_411 = evaluate_uci_411_412_correspondence(None, None, da_b1_authorized=da_b1_auth)
    stat_ovl = investigate_statlog_cleveland_overlap(None, None, da_b2_authorized=da_b2_auth)

    return build_and_verify_reports(
        execution_mode="DRY_RUN_PREFLIGHT",
        auth_manifest=auth_manifest,
        git_ignore_result=git_res.to_dict(),
        dataset_audits={},
        cross_cohort_duplicates=cross_dups,
        uci_411_412_correspondence=corr_411,
        uci_145_cleveland_overlap=stat_ovl,
        byte_identity_snapshots=(),
        is_synthetic_fixture_run=False,
        base_root=effective_parent,
        repo_root=repo_root,
        allow_external_tmp_root=allow_external_tmp_root,
        json_output_path=json_output_path,
        markdown_output_path=markdown_output_path,
    )


def run_local_dataset_audit(
    *,
    repo_root: Path = REPO_ROOT,
    base_data_parent: Path | None = None,
    auth_manifest_path: Path = DEFAULT_AUTH_MANIFEST_PATH,
    provenance_manifest_path: Path | None = None,
    requested_datasets: Sequence[str] | None = None,
    is_synthetic_fixture_run: bool = False,
    allow_external_tmp_root: Path | None = None,
    forbidden_substrings: Sequence[str] = (),
    json_output_path: Path | str | None = None,
    markdown_output_path: Path | str | None = None,
) -> tuple[dict[str, Any], str]:
    """Execute the full read-only local dataset audit on explicitly authorized datasets."""
    git_res = verify_git_ignore(repo_root)
    auth_manifest = load_authorization_manifest(auth_manifest_path)

    effective_parent = (base_data_parent or repo_root).resolve()
    data_dir = effective_parent / "data"
    verify_data_root_containment(
        repo_root,
        data_dir,
        allow_external_tmp_root=allow_external_tmp_root,
    )

    if requested_datasets is not None:
        target_ds_ids = list(requested_datasets)
    else:
        target_ds_ids = [
            ds_id
            for ds_id, ds_cfg in auth_manifest["datasets"].items()
            if ds_cfg.get("authorization_status") == AUTHORIZED_STATUS_VALUE
        ]

    verify_global_workflow_authorized(auth_manifest)

    if not target_ds_ids:
        raise GovernanceAuthorizationError(
            "No datasets are authorized for local audit in gate_da_authorization.json "
            "(all datasets are currently 'PENDING_HUMAN_ACCEPTANCE'). "
            "Use 'dry-run' for preflight validation, or wait for human maintainer approval."
        )

    for ds_id in target_ds_ids:
        verify_dataset_authorized_for_audit(auth_manifest, ds_id)

    prov_path = provenance_manifest_path or (effective_parent / "data/manifests/provenance_manifest.json")
    verify_data_root_containment(
        repo_root,
        prov_path,
        allow_external_tmp_root=allow_external_tmp_root,
    )
    verified_prov = validate_provenance_manifest(prov_path, effective_parent, auth_manifest, target_ds_ids)

    guard_entries: list[tuple[str, Path, str | None, int | None]] = []
    for ds_id in target_ds_ids:
        for fname, fmeta in verified_prov[ds_id].items():
            resolved_file = Path(fmeta["resolved_path"])
            resolved_lic = Path(fmeta["resolved_license_path"])
            verify_data_root_containment(
                repo_root,
                resolved_file,
                allow_external_tmp_root=allow_external_tmp_root,
            )
            verify_data_root_containment(
                repo_root,
                resolved_lic,
                allow_external_tmp_root=allow_external_tmp_root,
            )
            guard_entries.append(
                (
                    str(fmeta["relative_path"]),
                    resolved_file,
                    str(fmeta["verified_sha256"]),
                    int(fmeta["verified_size_bytes"]),
                )
            )

    dataset_audits: dict[str, Any] = {}
    all_fingerprints: list[str] = []
    cohort_14_rows_map: dict[str, Sequence[dict[str, Any]]] = {}

    uci_412_parsed: dict[str, Any] | None = None
    uci_411_parsed: dict[str, Any] | None = None
    cleveland_proc_rows: Sequence[dict[str, Any]] | None = None
    statlog_rows: Sequence[dict[str, Any]] | None = None

    with ByteIdentityGuard(guard_entries) as guard:
        # Validate report output paths inside ByteIdentityGuard before reading or writing anything
        if json_output_path is not None:
            validate_and_resolve_report_output_path(
                effective_parent,
                json_output_path,
                expected_suffix=".json",
                repo_root=repo_root,
                allow_external_tmp_root=allow_external_tmp_root,
            )
        if markdown_output_path is not None:
            validate_and_resolve_report_output_path(
                effective_parent,
                markdown_output_path,
                expected_suffix=".md",
                repo_root=repo_root,
                allow_external_tmp_root=allow_external_tmp_root,
            )

        if "DA-A1" in target_ds_ids:
            f_412 = Path(verified_prov["DA-A1"]["Z-Alizadeh sani dataset.xlsx"]["resolved_path"])
            uci_412_parsed = audit_uci_412_or_411_workbook(f_412, dataset_id="DA-A1")
            dataset_audits["DA-A1"] = uci_412_parsed["report"]
            all_fingerprints.extend(uci_412_parsed["raw_row_fingerprints"])

        if "DA-A2" in target_ds_ids:
            prov_a2 = verified_prov["DA-A2"]
            proc_reports: dict[str, Any] = {}
            raw_reports: dict[str, Any] = {}
            correspondence_reports: dict[str, Any] = {}

            cohort_pairs = (
                ("cleveland", "processed.cleveland.data", "cleveland.data"),
                ("hungarian", "processed.hungarian.data", "hungarian.data"),
                ("switzerland", "processed.switzerland.data", "switzerland.data"),
                ("va", "processed.va.data", "long-beach-va.data"),
            )
            for cohort_name, proc_fname, raw_fname in cohort_pairs:
                p_parsed = audit_uci_45_processed_file(Path(prov_a2[proc_fname]["resolved_path"]))
                r_parsed = audit_uci_45_raw_file(Path(prov_a2[raw_fname]["resolved_path"]))
                corr = compare_uci_45_raw_and_processed(cohort_name, r_parsed, p_parsed)

                proc_reports[proc_fname] = p_parsed["report"]
                raw_reports[raw_fname] = r_parsed["report"]
                correspondence_reports[cohort_name] = corr

                cohort_14_rows_map[f"DA-A2:{cohort_name}"] = p_parsed["normalized_rows"]
                if cohort_name == "cleveland":
                    cleveland_proc_rows = p_parsed["normalized_rows"]

                all_fingerprints.extend(p_parsed["raw_row_fingerprints"])
                all_fingerprints.extend(r_parsed["raw_row_fingerprints"])

            names_report = audit_uci_45_names_file(
                Path(prov_a2["heart-disease.names"]["resolved_path"])
            )
            dataset_audits["DA-A2"] = {
                "dataset_id": "DA-A2",
                "processed_cleveland_benchmark_confirmed": True,
                "processed_files": proc_reports,
                "raw_files": raw_reports,
                "raw_vs_processed_correspondence": correspondence_reports,
                "documentation_file": names_report,
                "evidence_status": "VERIFIED",
            }

        if "DA-B1" in target_ds_ids:
            f_411 = Path(verified_prov["DA-B1"]["extention of Z-Alizadeh sani dataset.xlsx"]["resolved_path"])
            uci_411_parsed = audit_uci_412_or_411_workbook(f_411, dataset_id="DA-B1")
            dataset_audits["DA-B1"] = uci_411_parsed["report"]
            all_fingerprints.extend(uci_411_parsed["raw_row_fingerprints"])

        if "DA-B2" in target_ds_ids:
            f_145 = Path(verified_prov["DA-B2"]["heart.dat"]["resolved_path"])
            stat_parsed = audit_uci_145_statlog_file(f_145)
            dataset_audits["DA-B2"] = stat_parsed["report"]
            statlog_rows = stat_parsed["normalized_rows"]
            cohort_14_rows_map["DA-B2:statlog"] = statlog_rows
            all_fingerprints.extend(stat_parsed["raw_row_fingerprints"])

        current_snapshots = guard.verify_unchanged_now()
        snapshots_dicts = [
            {
                "filename": s.filename,
                "relative_path": s.relative_path,
                "pre_sha256": s.pre_sha256,
                "post_sha256": s.post_sha256,
                "size_bytes": s.size_bytes,
                "byte_identical": s.byte_identical,
            }
            for s in current_snapshots
        ]

        cross_dups = compute_cross_cohort_duplicates(cohort_14_rows_map)
        corr_411 = evaluate_uci_411_412_correspondence(
            uci_412_parsed,
            uci_411_parsed,
            da_b1_authorized=("DA-B1" in target_ds_ids),
        )
        stat_ovl = investigate_statlog_cleveland_overlap(
            cleveland_proc_rows,
            statlog_rows,
            da_b2_authorized=("DA-B2" in target_ds_ids),
        )

        mode = "SYNTHETIC_SELF_TEST" if is_synthetic_fixture_run else "AUTHORIZED_READ_ONLY_LOCAL_AUDIT"
        report_dict, markdown_text = build_and_verify_reports(
            execution_mode=mode,
            auth_manifest=auth_manifest,
            git_ignore_result=git_res.to_dict(),
            dataset_audits=dataset_audits,
            cross_cohort_duplicates=cross_dups,
            uci_411_412_correspondence=corr_411,
            uci_145_cleveland_overlap=stat_ovl,
            byte_identity_snapshots=snapshots_dicts,
            is_synthetic_fixture_run=is_synthetic_fixture_run,
            forbidden_row_fingerprints=all_fingerprints,
            forbidden_substrings=forbidden_substrings,
            base_root=effective_parent,
            repo_root=repo_root,
            allow_external_tmp_root=allow_external_tmp_root,
            json_output_path=json_output_path,
            markdown_output_path=markdown_output_path,
        )

    return report_dict, markdown_text


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for the M2a local read-only dataset audit toolchain."""
    parser = argparse.ArgumentParser(
        prog="python -m research.audit",
        description="CardioAssist AI M2a Read-Only Local Dataset Audit Toolchain",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run preflight validation without downloading or reading any dataset files.",
    )
    subparsers = parser.add_subparsers(dest="subcommand")

    # 1. check-auth
    p_auth = subparsers.add_parser("check-auth", help="Check Gate DA governance and dataset authorization status.")
    p_auth.add_argument("--auth-manifest", type=Path, default=DEFAULT_AUTH_MANIFEST_PATH)

    # 2. verify-ignore
    subparsers.add_parser("verify-ignore", help="Verify git check-ignore protection for /data/ paths.")

    # 3. dry-run
    p_dry = subparsers.add_parser("dry-run", help="Run dry-run preflight validation without reading data.")
    p_dry.add_argument("--auth-manifest", type=Path, default=DEFAULT_AUTH_MANIFEST_PATH)
    p_dry.add_argument("--json-out", default=None, help="Relative output path under data/reports/ (*.json).")
    p_dry.add_argument("--markdown-out", default=None, help="Relative output path under data/reports/ (*.md).")

    # 4. self-test
    subparsers.add_parser(
        "self-test",
        help="Run the synthetic fixture self-test in an isolated temporary directory.",
    )

    # 5. inspect-archive
    p_zip = subparsers.add_parser(
        "inspect-archive",
        help="Inspect a downloaded official UCI .zip archive in read-only mode before extraction.",
    )
    p_zip.add_argument("--dataset-id", required=True, choices=["DA-A1", "DA-A2", "DA-B1", "DA-B2"])
    p_zip.add_argument("--zip-path", required=True, type=Path)
    p_zip.add_argument("--auth-manifest", type=Path, default=DEFAULT_AUTH_MANIFEST_PATH)

    # 6. extract-authorized-archive
    p_ext = subparsers.add_parser(
        "extract-authorized-archive",
        help=(
            "Safely extract ONLY authorized dataset files from an inspected official UCI .zip archive "
            "into data/raw/uci-<id>/ (requires --review-approval if inspect-archive reported STOP_REQUIRES_REVIEW)."
        ),
    )
    p_ext.add_argument("--dataset-id", required=True, choices=["DA-A1", "DA-A2", "DA-B1", "DA-B2"])
    p_ext.add_argument("--zip-path", required=True, type=Path)
    p_ext.add_argument(
        "--review-approval",
        default=None,
        help="Relative path to human archive review approval JSON under data/manifests/archive_reviews/.",
    )
    p_ext.add_argument("--auth-manifest", type=Path, default=DEFAULT_AUTH_MANIFEST_PATH)

    # 7. record-provenance
    p_prov = subparsers.add_parser(
        "record-provenance",
        help="Record SHA-256 hashes, sizes, and license snapshots for human-acquired official files.",
    )
    p_prov.add_argument("--datasets", nargs="+", required=True, choices=["DA-A1", "DA-A2", "DA-B1", "DA-B2"])
    p_prov.add_argument("--acquirer", required=True)
    p_prov.add_argument("--audit-reviewer", required=True)
    p_prov.add_argument(
        "--downloaded-at-utc",
        default=UNKNOWN_DOWNLOAD_TIMESTAMP,
        help=(
            "Human-attested UTC download timestamp ('YYYY-MM-DDTHH:MM:SSZ') or "
            "'UNKNOWN_PENDING_HUMAN_VERIFICATION' (default). Never conflated with manifest_recorded_at_utc."
        ),
    )
    p_prov.add_argument(
        "--environment",
        default="E:\\CardioAssist_AI_GitHub_Starter (Windows 10/11 PowerShell, Python 3.12)",
    )
    p_prov.add_argument("--auth-manifest", type=Path, default=DEFAULT_AUTH_MANIFEST_PATH)
    p_prov.add_argument(
        "--output",
        default=None,
        help="Must be omitted or 'data/manifests/provenance_manifest.json'.",
    )

    # 8. run-audit
    p_run = subparsers.add_parser(
        "run-audit",
        help="Execute read-only local dataset audit on authorized datasets in /data/raw/.",
    )
    p_run.add_argument("--datasets", nargs="*", default=None)
    p_run.add_argument("--auth-manifest", type=Path, default=DEFAULT_AUTH_MANIFEST_PATH)
    p_run.add_argument("--provenance-manifest", type=Path, default=None)
    p_run.add_argument("--json-out", default=None, help="Relative output path under data/reports/ (*.json).")
    p_run.add_argument("--markdown-out", default=None, help="Relative output path under data/reports/ (*.md).")

    args = parser.parse_args(argv)

    try:
        if args.dry_run or args.subcommand in (None, "dry-run"):
            auth_p = getattr(args, "auth_manifest", DEFAULT_AUTH_MANIFEST_PATH)
            json_o = getattr(args, "json_out", None)
            md_o = getattr(args, "markdown_out", None)
            rep, _ = run_dry_run_preflight(
                auth_manifest_path=auth_p,
                json_output_path=json_o,
                markdown_output_path=md_o,
            )
            summary = {
                "status": "OK_DRY_RUN_PREFLIGHT",
                "governance_decision_id": rep["governance_and_authorization"]["governance_decision_id"],
                "workflow_status": rep["governance_and_authorization"]["workflow_status"],
                "git_ignore_passed": rep["git_ignore_verification"]["passed"],
                "datasets_status": {
                    k: v["authorization_status"]
                    for k, v in rep["governance_and_authorization"]["datasets"].items()
                },
                "patient_level_rows_emitted": rep["safety_and_non_fitting_certification"][
                    "patient_level_rows_emitted"
                ],
            }
            print(json.dumps(summary, indent=2))
            return 0

        if args.subcommand == "check-auth":
            manifest = load_authorization_manifest(args.auth_manifest)
            out = {
                "governance_decision_id": manifest["governance_decision_id"],
                "workflow_status": manifest["workflow_status"],
                "supervisor_review_status": manifest["supervisor_review_status"],
                "supervisor_approval_claimed": manifest["supervisor_approval_claimed"],
                "gate_pt_status": manifest["gate_pt_status"],
                "internal_exploratory_proposal": manifest["internal_exploratory_protocol_proposal"]["status"],
                "model_fitting_authorized": manifest["model_fitting_authorized"],
                "datasets": {
                    ds_id: {
                        "title": ds_cfg["title"],
                        "authorization_status": ds_cfg["authorization_status"],
                        "permitted_role": ds_cfg["permitted_role"],
                        "authorized_by": ds_cfg["authorized_by"],
                        "authorized_date": ds_cfg["authorized_date"],
                    }
                    for ds_id, ds_cfg in manifest["datasets"].items()
                },
            }
            print(json.dumps(out, indent=2))
            return 0

        if args.subcommand == "verify-ignore":
            res = verify_git_ignore(REPO_ROOT)
            print(json.dumps(res.to_dict(), indent=2))
            return 0

        if args.subcommand == "self-test":
            with tempfile.TemporaryDirectory(prefix="cardioassist-m2a-selftest-") as tmp_str:
                tmp_path = Path(tmp_str)
                suite = materialize_synthetic_audit_suite(tmp_path, authorize_all=True)
                rep, _ = run_local_dataset_audit(
                    repo_root=REPO_ROOT,
                    base_data_parent=tmp_path,
                    auth_manifest_path=suite["auth_manifest_path"],
                    provenance_manifest_path=suite["provenance_manifest_path"],
                    is_synthetic_fixture_run=True,
                    allow_external_tmp_root=tmp_path,
                    forbidden_substrings=(str(SYNTHETIC_PLANTED_SENTINEL_FLOAT),),
                    json_output_path="data/reports/selftest_report.json",
                    markdown_output_path="data/reports/selftest_report.md",
                )
                print(
                    json.dumps(
                        {
                            "status": "OK_SYNTHETIC_SELF_TEST",
                            "is_synthetic_fixture_run": rep["is_synthetic_fixture_run"],
                            "audited_datasets": sorted(rep["dataset_audits"].keys()),
                            "originals_byte_identical": rep["safety_and_non_fitting_certification"][
                                "originals_byte_identical"
                            ],
                            "patient_level_rows_emitted": rep["safety_and_non_fitting_certification"][
                                "patient_level_rows_emitted"
                            ],
                        },
                        indent=2,
                    )
                )
            return 0

        if args.subcommand == "inspect-archive":
            manifest = load_authorization_manifest(args.auth_manifest)
            res_dict = inspect_zip_archive(args.zip_path, args.dataset_id, manifest)
            print(json.dumps(res_dict, indent=2))
            return 0

        if args.subcommand == "extract-authorized-archive":
            verify_git_ignore(REPO_ROOT)
            manifest = load_authorization_manifest(args.auth_manifest)
            ext_res = extract_authorized_archive(
                args.zip_path,
                args.dataset_id,
                manifest,
                base_root=REPO_ROOT,
                repo_root=REPO_ROOT,
                review_approval_path=args.review_approval,
            )
            print(json.dumps(ext_res, indent=2))
            return 0

        if args.subcommand == "record-provenance":
            verify_git_ignore(REPO_ROOT)
            manifest = load_authorization_manifest(args.auth_manifest)
            doc = build_provenance_manifest(
                REPO_ROOT,
                manifest,
                args.datasets,
                acquirer=args.acquirer,
                audit_reviewer=args.audit_reviewer,
                environment=args.environment,
                downloaded_at_utc=args.downloaded_at_utc,
                output_manifest_path=args.output,
                repo_root=REPO_ROOT,
            )
            print(
                json.dumps(
                    {
                        "status": "OK_PROVENANCE_RECORDED",
                        "files_recorded_count": len(doc["files"]),
                        "downloaded_at_utc": args.downloaded_at_utc,
                        "manifest_recorded_at_utc": doc["manifest_recorded_at_utc"],
                        "provenance_verification_semantics": doc["provenance_verification_semantics"],
                    },
                    indent=2,
                )
            )
            return 0

        if args.subcommand == "run-audit":
            rep, _ = run_local_dataset_audit(
                repo_root=REPO_ROOT,
                auth_manifest_path=args.auth_manifest,
                provenance_manifest_path=args.provenance_manifest,
                requested_datasets=args.datasets if args.datasets else None,
                json_output_path=args.json_out,
                markdown_output_path=args.markdown_out,
            )
            print(
                json.dumps(
                    {
                        "status": "OK_READ_ONLY_AUDIT_COMPLETE",
                        "audited_datasets": sorted(rep["dataset_audits"].keys()),
                        "originals_byte_identical": rep["safety_and_non_fitting_certification"][
                            "originals_byte_identical"
                        ],
                        "patient_level_rows_emitted": rep["safety_and_non_fitting_certification"][
                            "patient_level_rows_emitted"
                        ],
                    },
                    indent=2,
                )
            )
            return 0

        return 1
    except AuditError as exc:
        err_payload: dict[str, Any] = {
            "status": "FAILED_CLOSED",
            "error_code": exc.error_code,
            "message": str(exc),
        }
        if hasattr(exc, "outcome"):
            err_payload["outcome"] = getattr(exc, "outcome")
        if hasattr(exc, "archive_sha256"):
            err_payload["archive_sha256"] = getattr(exc, "archive_sha256")
        if hasattr(exc, "archive_size_bytes"):
            err_payload["archive_size_bytes"] = getattr(exc, "archive_size_bytes")
        if hasattr(exc, "excluded_files_detected"):
            err_payload["excluded_files_detected"] = getattr(exc, "excluded_files_detected")
        if hasattr(exc, "unexpected_entries_detected"):
            err_payload["unexpected_entries_detected"] = getattr(exc, "unexpected_entries_detected")
        if hasattr(exc, "archive_inventory"):
            err_payload["archive_inventory"] = getattr(exc, "archive_inventory")
        print(json.dumps(err_payload, indent=2), file=sys.stderr)
        return 2
