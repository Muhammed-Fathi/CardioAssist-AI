#!/usr/bin/env python3
"""Read-only RH-07 evidence intake inventory checker; not a science approval."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

PATH = Path("docs/research/next_phase/RH07_INDEPENDENT_ACCEPTANCE_INTAKE_2026_11_21.json")
MD = Path("docs/research/next_phase/RH07_INDEPENDENT_ACCEPTANCE_INTAKE_2026_11_21.md")
CARDS = Path("docs/research/next_phase/RH07_MODEL_CARD_INVENTORY_2026_11_21.md")

def verify(root: Path) -> dict[str, int]:
    doc = json.loads((root / PATH).read_text(encoding="utf-8"))
    md = (root / MD).read_text(encoding="utf-8")
    cards = (root / CARDS).read_text(encoding="utf-8")
    if doc["schema_id"] != "cardioassist.rh07.independent_acceptance_intake/v1":
        raise ValueError("schema mismatch")
    if doc["status"] != "INDEPENDENT_REVIEW_INTAKE_NOT_ACCEPTED":
        raise ValueError("false acceptance status")
    if doc["final_prototype_accepted"] is not False or doc["patient_inference_or_clinical_validation_authorized"] is not False:
        raise ValueError("unsafe approval claim")
    rows = doc["checklist"]
    wanted = [f"AC-{i:02d}" for i in range(1, 16)]
    if [r["id"] for r in rows] != wanted:
        raise ValueError("15 acceptance items missing/duplicated")
    evidence = 0
    for row in rows:
        if row["evidence_status"] != "EVIDENCE_LOCATED_REVIEW_REQUIRED" or row["independent_review"] != "PENDING":
            raise ValueError("review status promoted")
        if row["reviewer"] is not None or row["accepted_at"] is not None or not row["gap"]:
            raise ValueError("missing reviewer boundary or gap")
        if f"| {row['id']} |" not in md:
            raise ValueError("Markdown row missing")
        for path in row["evidence_paths"]:
            if path.startswith("/") or ".." in Path(path).parts or not (root / path).is_file():
                raise ValueError("source path absent or outside repository: " + path)
            evidence += 1
    claim = doc["original_claim_audit"]
    if claim != {"claims_total": 28, "limited_source_matches": 9, "not_verifiable": 19, "human_review_actions_pending": 10}:
        raise ValueError("scientific audit status drift")
    if len(doc["pending_decisions"]) < 4 or not all(x["status"] in {"PENDING_OWNER_IF_AVAILABLE","PENDING_REVIEW","INCOMPLETE","UNRESOLVED_ROOT_CAUSE","NOT_PERFORMED"} for x in doc["pending_decisions"]):
        raise ValueError("missing or promoted review decision")
    for s in ("synth_ai7_da_a2_resting_v1@0.1.0", "synth_ai8_uci412_da_a1_basic_clinical@0.1.0", "MOCK_SYNTHETIC"):
        # MOCK_SYNTHETIC is a provider boundary, not a model card itself.
        haystack = cards if not s.startswith("MOCK") else md
        if s not in haystack:
            raise ValueError("model card/serving boundary missing")
    return {"acceptance_checks":len(rows), "linked_source_paths":evidence, "pending_review_decisions":len(doc["pending_decisions"])}

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root",type=Path,default=Path(__file__).resolve().parents[1])
    args = p.parse_args()
    try:
        x = verify(args.repo_root)
    except (KeyError, ValueError, OSError, json.JSONDecodeError) as e:
        print("FAIL RH-07 intake: " + str(e))
        return 1
    print("PASS RH-07 structural evidence intake: " + " ".join(f"{k}={v}" for k,v in x.items()))
    print("LIMIT: source existence is not historical experiment reexecution, scientific acceptance or clinical permission")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
