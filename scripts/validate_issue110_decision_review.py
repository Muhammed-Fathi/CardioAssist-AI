#!/usr/bin/env python3
"""Read-only validator for the Issue #110 consolidated decision review.

This script never opens a patient dataset, performs no network access, writes no
files, and does not import the application. It checks that the Markdown report
and machine-readable JSON companion are internally consistent, that the
canonical 16-question register is byte-identical to the pinned snapshot, and
that the decision review has not silently acquired an approval, a real-data
permission, or a promoted question status.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

VALIDATOR_SCHEMA_ID = "cardioassist.issue110_decision_review_validation/v1"
REVIEW_SCHEMA_ID = "cardioassist.issue110_decision_review/v1"
REVIEW_VERSION = "1.2.0"
EXPECTED_BASE_COMMIT = "d45bbd44e029d3677e99d08dd4f848d5ec29fa2f"
EXPECTED_BRANCH = "arena/252b77ec-cardioassist-ai"
EXPECTED_REGISTER_SHA256 = "9e3f5f9895f894fb603f90435a69d7b174b24bff291254e208cd7c2201f612d4"
EXPECTED_QUESTION_STATUSES = {
    "Q-01": "CONDITIONAL_SOURCE_REVIEW_REQUIRED",
    "Q-02": "SOURCE_WORDING_RESOLVED_EQUIVALENCE_UNRESOLVED",
    "Q-03": "RESOLVED_PRIMARY_METADATA_ONLY",
    "Q-04": "UNRESOLVED_SCIENTIFIC_HOLD",
    "Q-05": "UNRESOLVED_SCIENTIFIC_HOLD",
    "Q-06": "CONDITIONAL_SOURCE_REVIEW_REQUIRED",
    "Q-07": "UNRESOLVED_SCIENTIFIC_HOLD",
    "Q-08": "DOCUMENTED_REPOSITORY_AGGREGATE_ONLY",
    "Q-09": "UNSUITABLE_FOR_THIS_EXTERNAL_CLAIM",
    "Q-10": "UNRESOLVED_SCIENTIFIC_HOLD",
    "Q-11": "UNRESOLVED_SCIENTIFIC_HOLD",
    "Q-12": "CONDITIONAL_SOURCE_REVIEW_REQUIRED",
    "Q-13": "CONDITIONAL_SOURCE_REVIEW_REQUIRED",
    "Q-14": "CONDITIONAL_SOURCE_REVIEW_REQUIRED",
    "Q-15": "UNRESOLVED_SCIENTIFIC_HOLD",
    "Q-16": "RESOLVED_PRIMARY_METADATA_ONLY",
}
EXPECTED_DATASETS = {
    "UCI45_CLEVELAND",
    "UCI412_Z_ALIZADEH_SANI",
    "UCI45_HUNGARY",
    "UCI45_VA_LONG_BEACH",
    "UCI45_SWITZERLAND",
    "UCI411_EXTENSION",
    "UCI145_STATLOG",
    "ANGIOCAD_P25",
}
ALLOWED_DISPOSITIONS = {
    "GO_FOR_REVIEW_ONLY",
    "HOLD_WITH_SPECIFIC_MISSING_EVIDENCE",
    "PROPOSED_NO_GO_FOR_NAMED_ROLE",
}
AI92_BLOCKER_CATEGORIES = {"feature", "timing", "source", "protocol", "authorization"}
AI102_PREREQUISITE_KEYS = {
    "frozen_cleveland_model_artifact",
    "cleveland_development_protocol",
    "freeze_package_review",
    "endpoint_equivalence_ruling",
    "five_field_site_equivalence",
    "timing_both_sites",
    "missingness_abstention_policy",
    "raw_to_processed_target_ruling",
    "patient_level_independence",
    "one_shot_locked_protocol",
    "precision_riley_plan",
    "licensing_custody",
    "governance_authorization",
    "supervisor_protocol_approval",
}
TRIAGE_ROUTES = {"original_author_clarification", "separately_authorized_local_audits", "independent_scientific_review", "governance_human_authorization"}
REPORT_TOKENS = (
    "NOT APPROVED",
    "GO_FOR_REVIEW_ONLY",
    "HOLD_WITH_SPECIFIC_MISSING_EVIDENCE",
    "PROPOSED_NO_GO_FOR_NAMED_ROLE",
    "AI-9.2",
    "AI-10.2",
    "RH-04",
    "RH-05",
    "NOT_PERFORMED",
    "Q-15",
    "Q-10",
    "Q-11",
    "INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED",
    "P25",
    "REJECTED_RED",
    "MOCK_SYNTHETIC",
)
DATASET_TOKENS = (
    "Cleveland",
    "Hungary",
    "Statlog",
    "UCI-411",
    "UCI-412",
    "VA Long Beach",
    "Switzerland",
    "AngioCAD",
)
REPORT_REQUIRED_V11_TOKENS = (
    "UNASSESSED_DIFFERENT_ESTIMAND",
    "`chol`",
    "`fbs`",
    "2013 RCM Table 2",
    "2015 inventor patent",
    "`serum-chol`",          # v1.2 correction (review 5971501344)
    "`fasting-blood-sugar`",  # v1.2 correction (review 5971501344)
)
REPORT_FORBIDDEN_V11_PHRASES = (
    # The review-corrected claim set. Meta-mention of the correction (e.g. in
    # the v1.1/v1.2 change log) must not re-introduce the definitive claim, so
    # only the exact claim phrasings are forbidden and the meta text avoids them:
    "UCI-45 has no labs",
    "family has no labs",
    "Cleveland has no labs",
    "has **no labs**",
    "no labs anywhere",
    "Statlog has none",       # v1.2 correction (review 5971501344)
    "Statlog has no labs",    # v1.2 correction (review 5971501344)
    "Statlog has no markers",  # v1.2 correction (review 5971501344)
    "Statlog documents none",  # v1.2 correction (review 5971501344)
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
    review_path: Path,
    report_path: Path,
    register_path: Path,
    validator_path: Path,
) -> dict[str, Any]:
    errors: list[str] = []
    for path in (review_path, report_path, register_path, validator_path):
        require(path.is_file(), errors, f"missing input file: {path}")
    if errors:
        return _result("FAIL", review_path, report_path, register_path, validator_path, errors, 0, 0)

    review = load_json(review_path)
    register = load_json(register_path)
    report = report_path.read_text(encoding="utf-8")
    register_sha = sha256_file(register_path)
    review_sha = sha256_file(review_path)
    report_sha = sha256_file(report_path)
    validator_sha = sha256_file(validator_path)

    require(review.get("schema_id") == REVIEW_SCHEMA_ID, errors, "review schema_id mismatch")
    require(review.get("version") == REVIEW_VERSION, errors, "review version mismatch")
    require(
        review.get("status") == "EVIDENCE_REVIEW_DRAFT_NOT_APPROVED",
        errors,
        "review status must remain an unapproved evidence draft",
    )
    baseline = review.get("baseline", {})
    require(baseline.get("branch") == EXPECTED_BRANCH, errors, "baseline branch mismatch")
    require(baseline.get("commit") == EXPECTED_BASE_COMMIT, errors, "baseline commit mismatch")

    scope = review.get("scope", {})
    for key in (
        "public_sources_only",
        "general_dataset_literature_search_performed",
        "original_patient_datasets_downloaded",
        "patient_rows_accessed",
        "models_trained",
        "models_scored",
        "locked_external_test_outcomes_inspected",
        "frozen_protocols_modified",
        "scientific_approvals_changed",
        "real_backend_inference_enabled",
        "dataset_files_written",
        "author_emails_sent",
        "network_calls_by_validator",
    ):
        expected = key == "public_sources_only"
        require(scope.get(key) is expected, errors, f"scope.{key} has an unsafe value")
    issue_access = review.get("issue_access", {})
    require(issue_access.get("issue") == "https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/110", errors, "issue id mismatch")
    require(
        "Resource not accessible by integration" in issue_access.get("error", ""),
        errors,
        "Issue #110 403 fallback evidence is missing",
    )
    require(issue_access.get("fallback_executed") == "COMPLETE_FALLBACK_SCOPE_GIVEN_IN_REQUEST", errors, "fallback evidence marker mismatch")

    require(register_sha == EXPECTED_REGISTER_SHA256, errors, "canonical register hash mismatch")
    require(
        register.get("schema_id") == "cardioassist.rh02_source_adjudication/v1",
        errors,
        "canonical register schema mismatch",
    )
    deliverables = review.get("deliverables", {})
    require(deliverables.get("markdown_report") == report_path.name, errors, "deliverables.markdown_report filename mismatch")
    require(deliverables.get("report_sha256") == report_sha, errors, "report SHA-256 mismatch")
    require(deliverables.get("validator_sha256") == validator_sha, errors, "validator SHA-256 mismatch")
    require(deliverables.get("canonical_register_sha256") == register_sha, errors, "recorded canonical register SHA-256 mismatch")

    # Copied canonical statuses, never promoted.
    register_questions = {
        item.get("id"): item.get("status")
        for item in register.get("questions", [])
        if isinstance(item, dict)
    }
    copied = review.get("canonical_question_statuses_unchanged", {})
    for qid, expected_status in EXPECTED_QUESTION_STATUSES.items():
        require(copied.get(qid) == expected_status, errors, f"{qid} copied status mismatch or promoted")
        require(register_questions.get(qid) == expected_status, errors, f"{qid} canonical register status mismatch")
    require(set(copied) == set(EXPECTED_QUESTION_STATUSES), errors, "copied question set must be exactly Q-01..Q-16")

    datasets = review.get("datasets", [])
    dataset_ids: set[str] = set()
    for entry in datasets:
        if not isinstance(entry, dict):
            errors.append("datasets contains a non-object entry")
            continue
        did = entry.get("id")
        dataset_ids.add(did)
        require(did in EXPECTED_DATASETS, errors, f"unexpected dataset id: {did}")
        for field in (
            "title",
            "intended_role",
            "linked_questions",
            "known_facts",
            "uncertainties",
            "leakage_risks",
            "decision_requirements",
        ):
            require(bool(entry.get(field)), errors, f"{did}.{field} is empty")
        require(len(entry.get("known_facts", [])) >= 2, errors, f"{did} needs at least two known facts")
        require(len(entry.get("uncertainties", [])) >= 2, errors, f"{did} needs at least two uncertainties")
        recommendation = entry.get("recommendation", {})
        primary = recommendation.get("primary")
        require(primary in ALLOWED_DISPOSITIONS, errors, f"{did}.recommendation.primary is invalid")
        require(bool(recommendation.get("rationale")), errors, f"{did} has no recommendation rationale")
        require(bool(recommendation.get("decision_owner")), errors, f"{did} has no decision owner")
        require(bool(recommendation.get("named_role")), errors, f"{did} has no named role")
        for decision in entry.get("decision_requirements", []):
            if isinstance(decision, dict):
                require(bool(decision.get("owner")), errors, f"{did} decision has no owner")
                require(bool(decision.get("requirement")), errors, f"{did} decision has no requirement")
        for qid in entry.get("linked_questions", []):
            require(qid in EXPECTED_QUESTION_STATUSES, errors, f"{did} links invalid question: {qid}")
    require(dataset_ids == EXPECTED_DATASETS, errors, "dataset set must be the eight required sources")

    # AI-9.2 blocker inventory.
    ai92 = review.get("ai_9_2_blockers", {})
    categories = ai92.get("categories", {})
    require(set(categories) == AI92_BLOCKER_CATEGORIES, errors, "AI-9.2 must carry exactly feature/timing/source/protocol/authorization categories")
    for category, items in categories.items():
        require(isinstance(items, list) and len(items) >= 3, errors, f"AI-9.2 {category} blockers need at least three items")
        for item in items:
            require(bool(item.get("id")), errors, f"AI-9.2 {category} blocker has no id")
            require(bool(item.get("blocker")), errors, f"AI-9.2 {category} blocker has no statement")
            require(bool(item.get("evidence")), errors, f"AI-9.2 {category} blocker has no evidence link")
    require(
        ai92.get("disposition") == "PROPOSED_NO_GO_FOR_NAMED_ROLE",
        errors,
        "AI-9.2 primary recommendation must remain PROPOSED_NO_GO_FOR_NAMED_ROLE",
    )
    require(ai92.get("real_study_status") == "NOT_PERFORMED", errors, "AI-9.2 real study status must remain NOT_PERFORMED")

    # AI-10.2 prerequisite inventory.
    ai102 = review.get("ai_10_2_prerequisites", {})
    prereq_ids = {item.get("id") for item in ai102.get("prerequisites", []) if isinstance(item, dict)}
    require(AI102_PREREQUISITE_KEYS <= prereq_ids, errors, f"AI-10.2 prerequisite set incomplete: {sorted(AI102_PREREQUISITE_KEYS - prereq_ids)}")
    for item in ai102.get("prerequisites", []):
        require(bool(item.get("requirement")), errors, "AI-10.2 prerequisite has no requirement statement")
        require(bool(item.get("current_state")), errors, "AI-10.2 prerequisite has no current_state")
        require(item.get("current_state") in {"NOT_MET", "NOT_PERFORMED", "NOT_VERIFIED", "NOT_RULED", "NOT_DEFINED", "NOT_PRESPECIFIED", "NOT_ASSESSABLE", "NOT_GRANTED", "UNRESOLVED", "ABSENT", "UNCHANGED", "PROHIBITED", "AUDIT_ONLY"}, errors, f"AI-10.2 prerequisite {item.get('id')} has unknown current_state")
        require(bool(item.get("owner")), errors, "AI-10.2 prerequisite has no owner")
    require(
        ai102.get("disposition") == "HOLD_WITH_SPECIFIC_MISSING_EVIDENCE",
        errors,
        "AI-10.2 primary recommendation must remain HOLD_WITH_SPECIFIC_MISSING_EVIDENCE",
    )
    require(ai102.get("real_study_status") == "NOT_PERFORMED", errors, "AI-10.2 real study status must remain NOT_PERFORMED")

    # Triage routes.
    triage = review.get("outstanding_question_triage", {})
    routes = triage.get("routes", {})
    require(set(routes) == TRIAGE_ROUTES, errors, "triage must carry exactly the four named routes")
    for route, items in routes.items():
        require(isinstance(items, list) and len(items) >= 1, errors, f"triage route {route} is empty")

    # RH-04 / RH-05 mapping.
    rh = review.get("rh_mapping", {})
    rh04 = rh.get("rh_04_work_packages", [])
    rh05 = rh.get("rh_05_work_packages", [])
    require(len(rh04) >= 5, errors, "at least five RH-04 work packages required")
    require(len(rh05) >= 4, errors, "at least four RH-05 work packages required")
    for wp in rh04 + rh05:
        require(wp.get("synthetic_only") is True, errors, f"{wp.get('id')} must be synthetic_only")
        require(bool(wp.get("work_package")), errors, f"{wp.get('id')} has no work_package statement")
    require(bool(rh.get("not_immediate_engineering")), errors, "rh_mapping.not_immediate_engineering must list prohibited work")

    for token in REPORT_TOKENS + DATASET_TOKENS:
        require(token in report, errors, f"Markdown report is missing required token: {token}")
    for token in REPORT_REQUIRED_V11_TOKENS:
        require(token in report, errors, f"Markdown report is missing required v1.1 correction token: {token}")
    report_lower = report.lower()
    for phrase in REPORT_FORBIDDEN_V11_PHRASES:
        require(
            phrase.lower() not in report_lower,
            errors,
            f"Markdown report re-introduces the definitively false phrasing: {phrase!r}",
        )

    # v1.1 review corrections: UCI-45 chol/fbs are documented in the underlying
    # 13-predictor schema at all four sites; they are omitted from the frozen
    # five-field panel and are UNASSESSED_DIFFERENT_ESTIMAND, never admissible.
    uci45_ids = ("UCI45_CLEVELAND", "UCI45_HUNGARY", "UCI45_VA_LONG_BEACH", "UCI45_SWITZERLAND")
    for entry in datasets or []:
        if isinstance(entry, dict) and entry.get("id") in uci45_ids:
            facts = " ".join(str(fact) for fact in entry.get("known_facts", [])).lower()
            require(
                "chol" in facts and "fbs" in facts,
                errors,
                f"{entry.get('id')} known_facts no longer document chol/fbs schema acknowledgment (v1.1 correction)",
            )
    matrix = ai92.get("alternative_same_source_matrix") or []
    require(
        isinstance(matrix, list) and len(matrix) == 1,
        errors,
        "ai_9_2_blockers.alternative_same_source_matrix must contain exactly one documented entry (the UCI-45 chol/fbs estimand)",
    )
    if isinstance(matrix, list) and matrix and isinstance(matrix[0], dict):
        require(
            matrix[0].get("disposition") == "UNASSESSED_DIFFERENT_ESTIMAND",
            errors,
            "alternative_same_source_matrix entry must be UNASSESSED_DIFFERENT_ESTIMAND - never ADMISSIBLE",
        )
        require(
            "ADMISSIBLE" in (matrix[0].get("not") or []),
            errors,
            "alternative_same_source_matrix entry must explicitly exclude ADMISSIBLE",
        )

    # v1.2 review correction (review 5971501344): official UCI-145 documents
    # serum-chol / fasting-blood-sugar in its 13-feature schema. Statlog is a
    # suspected Cleveland-derived/near-duplicate source, never an admissible
    # labs panel or AI-9.2 substitute.
    statlog_entry = next(
        (
            entry
            for entry in datasets or []
            if isinstance(entry, dict) and entry.get("id") == "UCI145_STATLOG"
        ),
        None,
    )
    if statlog_entry is not None:
        statlog_facts = " ".join(str(fact) for fact in statlog_entry.get("known_facts", [])).lower()
        require(
            "serum-chol" in statlog_facts and "fasting-blood-sugar" in statlog_facts,
            errors,
            "UCI145_STATLOG known_facts no longer document the official serum-chol/fasting-blood-sugar schema acknowledgment (v1.2 correction)",
        )
    for item in categories["source"]:
        if item.get("id") == "S-1":
            blocker = str(item.get("blocker", "")).lower()
            require(
                "statlog has none" not in blocker,
                errors,
                "AI-9.2 source blocker S-1 re-introduces the definitively false Statlog no-markers claim (v1.2 correction)",
            )
            require(
                "serum-chol" in blocker and "fasting-blood-sugar" in blocker,
                errors,
                "AI-9.2 source blocker S-1 no longer acknowledges Statlog's documented serum-chol/fasting-blood-sugar markers (v1.2 correction)",
            )

    claims = review.get("prohibited_claims", {})
    require(bool(claims), errors, "prohibited_claims register is empty")
    for key, value in claims.items():
        require(value is False, errors, f"prohibited claim asserted as true: {key}")

    conditional = review.get("conditional_study_register_entries_unchanged", {})
    require(conditional.get("AI-9.2", {}).get("status") == "HOLD_NOT_EXECUTED", errors, "AI-9.2 register entry was altered")
    require(conditional.get("AI-10.2", {}).get("status") == "HOLD_NOT_EXECUTED", errors, "AI-10.2 register entry was altered")
    require(conditional.get("AI-9.2", {}).get("real_data_authorized") is False, errors, "AI-9.2 real_data_authorized altered")
    require(conditional.get("AI-10.2", {}).get("real_data_authorized") is False, errors, "AI-10.2 real_data_authorized altered")

    return _result(
        "PASS" if not errors else "FAIL",
        review_path,
        report_path,
        register_path,
        validator_path,
        errors,
        len(datasets),
        len(rh04) + len(rh05),
        report_sha=report_sha,
        review_sha=review_sha,
        validator_sha=validator_sha,
        register_sha=register_sha,
    )


def _result(
    status: str,
    review_path: Path,
    report_path: Path,
    register_path: Path,
    validator_path: Path,
    errors: list[str],
    dataset_count: int,
    work_package_count: int,
    *,
    report_sha: str = "",
    review_sha: str = "",
    validator_sha: str = "",
    register_sha: str = "",
) -> dict[str, Any]:
    return {
        "schema_id": VALIDATOR_SCHEMA_ID,
        "status": status,
        "inputs": {
            "review_json": str(review_path),
            "markdown_report": str(report_path),
            "canonical_register": str(register_path),
            "validator": str(validator_path),
        },
        "hashes": {
            "review_json_sha256": review_sha or sha256_file(review_path),
            "markdown_report_sha256": report_sha or sha256_file(report_path),
            "canonical_register_sha256": register_sha or sha256_file(register_path),
            "validator_sha256": validator_sha or sha256_file(validator_path),
        },
        "counts": {
            "datasets": dataset_count,
            "work_packages": work_package_count,
            "linked_questions": len(EXPECTED_QUESTION_STATUSES),
            "errors": len(errors),
        },
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--review",
        type=Path,
        default=root / "docs/research/next_phase/RH06_ISSUE110_CONSOLIDATED_DECISION_REVIEW_2026_11_19.json",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=root / "docs/research/next_phase/RH06_ISSUE110_CONSOLIDATED_DECISION_REVIEW_2026_11_19.md",
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
    result = validate(args.review, args.report, args.canonical_register, args.validator)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
