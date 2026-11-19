#!/usr/bin/env python3
"""Read-only validator for the Issue #107 public-source dataset audit.

This script never opens a patient dataset, performs no network access, writes no
files, and does not import the application. It checks that the Markdown report
and machine-readable JSON companion are internally consistent, that the
canonical 16-question register is byte-identical to the pinned snapshot, and
that the audit has not silently acquired an approval or real-data permission.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

VALIDATOR_SCHEMA_ID = "cardioassist.issue107_source_audit_validation/v1"
AUDIT_SCHEMA_ID = "cardioassist.issue107_public_source_audit/v1"
AUDIT_VERSION = "1.0.0"
EXPECTED_BASE_COMMIT = "0835627d524dbe3c512c1f9bd0606b6bcb864f17"
EXPECTED_BRANCH = "arena/26f5fc6c-cardioassist-ai"
EXPECTED_REGISTER_SHA256 = "9e3f5f9895f894fb603f90435a69d7b174b24bff291254e208cd7c2201f612d4"
EXPECTED_QUESTION_STATUSES = {
    "Q-01": "CONDITIONAL_SOURCE_REVIEW_REQUIRED",
    "Q-02": "SOURCE_WORDING_RESOLVED_EQUIVALENCE_UNRESOLVED",
    "Q-09": "UNSUITABLE_FOR_THIS_EXTERNAL_CLAIM",
    "Q-10": "UNRESOLVED_SCIENTIFIC_HOLD",
    "Q-11": "UNRESOLVED_SCIENTIFIC_HOLD",
    "Q-12": "CONDITIONAL_SOURCE_REVIEW_REQUIRED",
    "Q-13": "CONDITIONAL_SOURCE_REVIEW_REQUIRED",
}
EXPECTED_DATASETS = {
    "UCI45_CLEVELAND",
    "UCI45_HUNGARY",
    "UCI145_STATLOG",
    "UCI411_EXTENSION",
    "UCI45_VA_LONG_BEACH",
    "UCI45_SWITZERLAND",
}
ALLOWED_PRIMARY_RECOMMENDATIONS = {"GO_REVIEW", "HOLD", "NO_GO"}
REPORT_TOKENS = (
    "PUBLIC-SOURCE-ONLY",
    "NOT APPROVED",
    "Q-01",
    "Q-02",
    "Q-09",
    "Q-10",
    "Q-11",
    "Q-12",
    "Q-13",
)
DATASET_TOKENS = (
    "Cleveland",
    "Hungary",
    "Statlog",
    "UCI-411",
    "VA Long Beach",
    "Switzerland",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def require(condition: bool, errors: list[str], message: str) -> None:
    if not condition:
        errors.append(message)


def validate(
    audit_path: Path,
    report_path: Path,
    register_path: Path,
    validator_path: Path,
) -> dict[str, Any]:
    errors: list[str] = []
    for path in (audit_path, report_path, register_path, validator_path):
        require(path.is_file(), errors, f"missing input file: {path}")
    if errors:
        return _result("FAIL", audit_path, report_path, register_path, validator_path, errors, 0, 0, 0)

    audit = load_json(audit_path)
    register = load_json(register_path)
    report = report_path.read_text(encoding="utf-8")
    register_sha = sha256_file(register_path)
    audit_sha = sha256_file(audit_path)
    report_sha = sha256_file(report_path)
    validator_sha = sha256_file(validator_path)

    require(audit.get("schema_id") == AUDIT_SCHEMA_ID, errors, "audit schema_id mismatch")
    require(audit.get("version") == AUDIT_VERSION, errors, "audit version mismatch")
    require(
        audit.get("status") == "EVIDENCE_REVIEW_DRAFT_NOT_APPROVED",
        errors,
        "audit status must remain an unapproved evidence draft",
    )
    baseline = audit.get("baseline", {})
    require(baseline.get("branch") == EXPECTED_BRANCH, errors, "baseline branch mismatch")
    require(baseline.get("commit") == EXPECTED_BASE_COMMIT, errors, "baseline commit mismatch")

    scope = audit.get("scope", {})
    for key in (
        "public_sources_only",
        "original_patient_datasets_downloaded",
        "patient_rows_accessed",
        "models_trained",
        "locked_external_test_outcomes_inspected",
        "frozen_protocols_modified",
        "scientific_approvals_changed",
        "real_backend_inference_enabled",
        "dataset_files_written",
    ):
        expected = key == "public_sources_only"
        require(scope.get(key) is expected, errors, f"scope.{key} has an unsafe value")
    issue_access = audit.get("issue_access", {})
    require(
        "Resource not accessible by integration" in issue_access.get("error", ""),
        errors,
        "Issue #107 403 fallback evidence is missing",
    )

    require(register_sha == EXPECTED_REGISTER_SHA256, errors, "canonical register hash mismatch")
    require(
        register.get("schema_id") == "cardioassist.rh02_source_adjudication/v1",
        errors,
        "canonical register schema mismatch",
    )
    deliverables = audit.get("deliverables", {})
    require(
        deliverables.get("markdown_report") == report_path.name,
        errors,
        "deliverables.markdown_report filename mismatch",
    )
    require(deliverables.get("report_sha256") == report_sha, errors, "report SHA-256 mismatch")
    require(deliverables.get("validator_sha256") == validator_sha, errors, "validator SHA-256 mismatch")
    require(
        deliverables.get("canonical_register_sha256") == register_sha,
        errors,
        "recorded canonical register SHA-256 mismatch",
    )

    register_questions = {
        item.get("id"): item.get("status")
        for item in register.get("questions", [])
        if isinstance(item, dict)
    }
    question_links = audit.get("question_links", [])
    linked_ids: set[str] = set()
    for item in question_links:
        if not isinstance(item, dict):
            errors.append("question_links contains a non-object entry")
            continue
        qid = item.get("id")
        linked_ids.add(qid)
        require(qid in EXPECTED_QUESTION_STATUSES, errors, f"unexpected question id: {qid}")
        require(
            item.get("canonical_status") == EXPECTED_QUESTION_STATUSES.get(qid),
            errors,
            f"{qid} canonical status was changed or copied incorrectly",
        )
        require(
            register_questions.get(qid) == EXPECTED_QUESTION_STATUSES.get(qid),
            errors,
            f"{qid} canonical register status mismatch",
        )
        require(bool(item.get("datasets")), errors, f"{qid} has no linked datasets")
        require(bool(item.get("decision_requirement")), errors, f"{qid} has no decision requirement")
    require(
        linked_ids == set(EXPECTED_QUESTION_STATUSES),
        errors,
        "linked questions must be exactly Q-01, Q-02, Q-09, Q-10, Q-11, Q-12 and Q-13",
    )

    catalog = audit.get("source_catalog", [])
    catalog_ids: set[str] = set()
    for source in catalog:
        if not isinstance(source, dict):
            errors.append("source_catalog contains a non-object entry")
            continue
        sid = source.get("id")
        require(isinstance(sid, str) and bool(sid), errors, "source catalog entry has no id")
        require(sid not in catalog_ids, errors, f"duplicate source id: {sid}")
        catalog_ids.add(sid)
        url = source.get("url", "")
        require(isinstance(url, str) and url.startswith("https://"), errors, f"{sid} URL is not https")
        require(source.get("authority") in {"E1", "E2", "E3", "E4", "E5"}, errors, f"{sid} authority invalid")
        require(bool(source.get("establishes")), errors, f"{sid} has no establishes statement")
        require(bool(source.get("limits")), errors, f"{sid} has no limits statement")
        require(url in report, errors, f"{sid} URL is absent from the Markdown report")

    datasets = audit.get("datasets", [])
    dataset_ids: set[str] = set()
    for entry in datasets:
        if not isinstance(entry, dict):
            errors.append("datasets contains a non-object entry")
            continue
        did = entry.get("id")
        dataset_ids.add(did)
        require(did in EXPECTED_DATASETS, errors, f"unexpected dataset id: {did}")
        for field in ("title", "original_sources", "known_facts", "uncertainties", "leakage_risks", "decision_requirements"):
            require(bool(entry.get(field)), errors, f"{did}.{field} is empty")
        require(len(entry.get("known_facts", [])) >= 2, errors, f"{did} needs at least two known facts")
        require(len(entry.get("uncertainties", [])) >= 2, errors, f"{did} needs at least two uncertainties")
        require(len(entry.get("leakage_risks", [])) >= 1, errors, f"{did} needs at least one leakage risk")
        for source in entry.get("original_sources", []):
            require(source in catalog_ids, errors, f"{did} references unknown source id: {source}")
        for qid in entry.get("linked_questions", []):
            require(qid in EXPECTED_QUESTION_STATUSES, errors, f"{did} links invalid question: {qid}")
        recommendation = entry.get("recommendation", {})
        primary = recommendation.get("primary")
        require(
            primary in ALLOWED_PRIMARY_RECOMMENDATIONS,
            errors,
            f"{did}.recommendation.primary is invalid",
        )
        require(bool(recommendation.get("rationale")), errors, f"{did} has no recommendation rationale")
        require(bool(recommendation.get("decision_owner")), errors, f"{did} has no decision owner")
        for decision in entry.get("decision_requirements", []):
            if isinstance(decision, dict):
                require(bool(decision.get("owner")), errors, f"{did} decision has no owner")
                require(bool(decision.get("requirement")), errors, f"{did} decision has no requirement")
    require(dataset_ids == EXPECTED_DATASETS, errors, "dataset set does not match required six datasets")

    for token in REPORT_TOKENS + DATASET_TOKENS:
        require(token in report, errors, f"Markdown report is missing required token: {token}")

    claims = audit.get("prohibited_claims", {})
    require(bool(claims), errors, "prohibited_claims register is empty")
    for key, value in claims.items():
        require(value is False, errors, f"prohibited claim asserted as true: {key}")

    return _result(
        "PASS" if not errors else "FAIL",
        audit_path,
        report_path,
        register_path,
        validator_path,
        errors,
        len(datasets),
        len(catalog),
        len(question_links),
        report_sha=report_sha,
        audit_sha=audit_sha,
        validator_sha=validator_sha,
        register_sha=register_sha,
    )


def _result(
    status: str,
    audit_path: Path,
    report_path: Path,
    register_path: Path,
    validator_path: Path,
    errors: list[str],
    dataset_count: int,
    source_count: int,
    question_count: int,
    *,
    report_sha: str = "",
    audit_sha: str = "",
    validator_sha: str = "",
    register_sha: str = "",
) -> dict[str, Any]:
    return {
        "schema_id": VALIDATOR_SCHEMA_ID,
        "status": status,
        "inputs": {
            "audit_json": str(audit_path),
            "markdown_report": str(report_path),
            "canonical_register": str(register_path),
            "validator": str(validator_path),
        },
        "hashes": {
            "audit_json_sha256": audit_sha or sha256_file(audit_path),
            "markdown_report_sha256": report_sha or sha256_file(report_path),
            "canonical_register_sha256": register_sha or sha256_file(register_path),
            "validator_sha256": validator_sha or sha256_file(validator_path),
        },
        "counts": {
            "datasets": dataset_count,
            "sources": source_count,
            "linked_questions": question_count,
            "errors": len(errors),
        },
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--audit",
        type=Path,
        default=root / "docs/research/next_phase/RH02_ISSUE107_PUBLIC_SOURCE_DATASET_AUDIT_2026_11_19.json",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=root / "docs/research/next_phase/RH02_ISSUE107_PUBLIC_SOURCE_DATASET_AUDIT_2026_11_19.md",
    )
    parser.add_argument(
        "--canonical-register",
        type=Path,
        default=root / "docs/research/next_phase/RH02_SOURCE_QUESTION_REGISTER_2026_11_19.json",
    )
    parser.add_argument(
        "--validator",
        type=Path,
        default=Path(__file__).resolve(),
    )
    args = parser.parse_args(argv)
    result = validate(args.audit, args.report, args.canonical_register, args.validator)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
