#!/usr/bin/env python3
"""Read-only, stdlib-only RH-03 reporting/anchor regression verifier.

This verifies mechanical coherence, NOT numerical truth, approval, or the
original Git blobs: those are distinct evidence/reviewer procedures.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

DOC = Path("docs/research/next_phase")
MANUSCRIPT = DOC / "AI12_2_GRADUATION_RESEARCH_MANUSCRIPT_DRAFT_2026_11_19.md"
AUDIT = DOC / "RH03_AI12_2_AUDIT_MATRIX_2026_11_19.json"
CROSSWALK = DOC / "RH03_REPORTING_CROSSWALK_2026_11_21.json"
CROSSWALK_MD = DOC / "RH03_REPORTING_CROSSWALK_2026_11_21.md"

def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)

def verify(root: Path) -> dict[str, int]:
    lines = (root / MANUSCRIPT).read_text(encoding="utf-8").split("\n")
    audit = json.loads((root / AUDIT).read_text(encoding="utf-8"))
    report = json.loads((root / CROSSWALK).read_text(encoding="utf-8"))
    crosswalk_md = (root / CROSSWALK_MD).read_text(encoding="utf-8")

    # Existing RH-03 claim excerpts contain frozen manuscript line anchors.
    require(len(lines) == 335, "Manuscript line anchors shifted; refresh the audit atomically")
    chapters = re.findall(r"^## (FR-\d{2})\.", "\n".join(lines), flags=re.MULTILINE)
    expected_chapters = [f"FR-{i:02d}" for i in range(1, 18)]
    require(chapters == expected_chapters, "FR-01..FR-17 headings changed")
    require(len(audit["chapters"]) == 17, "Audit chapter count changed")

    for chapter in audit["chapters"]:
        header = chapter["section_heading"]
        match = re.search(r"manuscript:(\d+): (.+)$", header)
        require(match is not None, f"Unrecognized audit section heading: {header}")
        n = int(match.group(1))
        require(0 < n <= len(lines) and lines[n - 1] == match.group(2),
                f"Audit heading drift at {n}")

    claims = audit["claims"]
    require(len(claims) == 28, "Expected exactly 28 scientific claims")
    require({c["claim_id"] for c in claims} ==
            {f"CL-{i:03d}" for i in range(1, 29)}, "Claim IDs differ")
    count = Counter(c["content_check"]["status"] for c in claims)
    require(count == Counter({"PASS_SOURCE_MATCH": 9, "NOT_VERIFIABLE": 19}),
            "Source-check statuses were promoted or changed")
    require(len(audit["reviewer_actions"]) == 10, "Review action count changed")
    for action in audit["reviewer_actions"]:
        require(action.get("status") == "PENDING", "Reviewer action promoted")
    excerpt_count = 0
    for claim in claims:
        for entry in claim.get("manuscript_occurrences", []):
            for ex in entry.get("matched_report_lines", []):
                n = ex["line"]
                require(1 <= n <= len(lines) and lines[n - 1] == ex["text"],
                        f"Stale audit excerpt {claim['claim_id']} at manuscript line {n}")
                excerpt_count += 1

    info = report["tripod_ai"]
    require(info["main_item_count"] == 27 and info["subitems_original_checklist_count"] == 52,
            "TRIPOD+AI checklist size metadata changed")
    items = info["main_items"]
    require(len(items) == 27 and [x["item_id"] for x in items] ==
            [str(i) for i in range(1, 28)], "TRIPOD+AI item inventory missing/duplicated")
    require(len(report["probast_ai"]["domains"]) == 4, "PROBAST+AI four domains missing")
    expected_domains = {"participants_and_data_sources", "predictors", "outcome", "analysis"}
    require({d["domain"] for d in report["probast_ai"]["domains"]} ==
            expected_domains, "PROBAST+AI domains drifted")
    for item in items:
        require(item["status"] in {"DRAFT_MAPPED", "PARTIAL", "INFORMATION_GAP", "NOT_PERFORMED"},
                f"Unsupported unreviewed crosswalk status for item {item['item_id']}")
        require(item["manuscript_sections"] and
                set(item["manuscript_sections"]).issubset(set(expected_chapters)),
                f"Bad chapter reference for item {item['item_id']}")
        require(f"| {item['item_id']} |" in crosswalk_md,
                f"Markdown crosswalk missing item {item['item_id']}")
    require(report["canonical_audit_preservation"]["claim_status_counts"] ==
            {"PASS_SOURCE_MATCH": 9, "NOT_VERIFIABLE": 19, "MISMATCH": 0},
            "Crosswalk must preserve limited transcription audit")
    require(report["canonical_audit_preservation"]["review_actions_pending"] == 10,
            "Crosswalk reviewer status must remain pending")
    require(report["canonical_audit_preservation"]["research_questions"] == 16,
            "Research question inventory changed")
    require(report["rh05_test_provenance"]["source_sha"] ==
            "64f34e4cb8580ced461237ffa46ba0a91e8fc1c5",
            "RH-05 Windows provenance SHA drift")
    require(report["rh05_test_provenance"]["cross_os_exact_comparison_sha"] ==
            "09b895423171eff7569fc49dd8ceac7dfb0d43c6",
            "RH-05 cross-OS source provenance SHA drift")
    require(report["rh05_test_provenance"]["clinical_validation"] is False,
            "Research-only clinical boundary misclassified")
    require("TRIPOD+AI" in crosswalk_md and "PROBAST+AI" in crosswalk_md,
            "Missing reporting frameworks")
    require("2909 passed" in "\n".join(lines) and "RH-05" in "\n".join(lines),
            "RH-05 engineering acceptance not integrated into manuscript")
    return {"chapters": len(chapters), "claims": len(claims), "review_actions": 10,
            "tripod_main_items": len(items), "probast_domains": 4,
            "anchored_excerpts": excerpt_count}

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        result = verify(args.repo_root)
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
        print(f"FAIL: RH-03 reporting/anchor check: {exc}")
        return 1
    print("PASS: RH-03 reporting/anchor mechanical check "
          + " ".join(f"{key}={value}" for key, value in result.items()))
    print("LIMIT: no historic numeric rerun, clinical validation or reviewer acceptance")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
