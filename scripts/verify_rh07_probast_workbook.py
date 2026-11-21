#!/usr/bin/env python3
"""Verify RH-07 question-level PROBAST+AI intake structure only (never grades science)."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

DOC=Path("docs/research/next_phase/RH07_PROBAST_AI_QUESTION_LEVEL_WORKBOOK_2026_11_21.json")
MD=Path("docs/research/next_phase/RH07_PROBAST_AI_QUESTION_LEVEL_WORKBOOK_2026_11_21.md")
EXPECTED={"participants_and_sources":["1.1","1.2","1.3"],
 "predictors":["2.1","2.2","2.3","2.4"],
 "outcome":["3.1","3.2","3.3","3.4"]}
DEV_ANALYSIS=["4.1","4.2","4.3","4.4","4.5"]
EVAL_ANALYSIS=["4.1","4.2","4.3","4.4","4.5","4.6","4.7"]

def validate(root:Path)->dict[str,int]:
 d=json.loads((root/DOC).read_text(encoding="utf-8"))
 md=(root/MD).read_text(encoding="utf-8")
 if d["schema_id"]!="cardioassist.rh07.probast_ai_review_workbook/v1" or d["status"]!="PREASSESSMENT_WORKBOOK_NOT_FORMAL_APPRAISAL":raise ValueError("unreviewed source scope promoted")
 if d["original_reporting_standards"]!={"tripod_main_items":27,"tripod_original_subitems":52,"tripod_subitem_assessment":"NOT_PERFORMED_IN_THIS_PR","probast_overall_quality":"NOT_ASSESSED","probast_overall_evaluation_risk_of_bias":"NOT_ASSESSED"}:raise ValueError("false reporting or risk-of-bias status")
 if d["scientific_snapshot"]!={"original_claims":28,"limited_transcription_matches":9,"not_independently_verifiable":19,"pending_human_reviewer_actions":10}:raise ValueError("frozen RH-03 count drift")
 if len(d["studies"])!=2 or {s["study_id"] for s in d["studies"]}!={"D-047_CLEVELAND_HISTORICAL","M3A_UCI412_HISTORICAL"}:raise ValueError("studies missing or duplicated")
 total=apps=0
 for s in d["studies"]:
  if not (root/s["archived_source_path"]).is_file():raise ValueError("missing source report")
  wanted={(phase[:4] if phase=="DEVELOPMENT" else "EVAL")+"-"+id for phase in ("DEVELOPMENT","EVALUATION") for domain in EXPECTED for id in EXPECTED[domain]}
  wanted|={"DEV-"+i for i in DEV_ANALYSIS}
  wanted|={"EVAL-"+i for i in EVAL_ANALYSIS}
  got=[q["question_key"] for q in s["questions"]]
  if len(got)!=34 or set(got)!=wanted:raise ValueError("missing/duplicated PROBAST questions")
  for q in s["questions"]:
   if q["formal_answer"]!="NOT_ASSESSED" or q["domain_rating"]!="NOT_ASSESSED" or q["reviewer"] is not None or q["reviewed_on"] is not None:raise ValueError("fabricated assessment")
   if not q["public_evidence_observation"] or not q["unresolved_check"]:raise ValueError("missing actionable review gap")
   if f"`{q['question_key']}`" not in md:raise ValueError("missing markdown question")
   for path in q["evidence_paths"]:
    if path.startswith("/") or ".." in Path(path).parts or not (root/path).is_file():raise ValueError("missing or unsafe cited source path: "+path)
  seen=[(a["phase"],a["domain"]) for a in s["applicability"]]
  if len(seen)!=6 or len(set(seen))!=6 or set(seen)!={(p,d) for p in ("DEVELOPMENT","EVALUATION") for d in EXPECTED}:raise ValueError("missing applicability domain")
  for a in s["applicability"]:
   if a["formal_concern"]!="NOT_ASSESSED" or a["reviewer"] is not None or not a["gap"]:raise ValueError("fabricated applicability")
  total+=len(got);apps+=len(seen)
 return {"studies":len(d["studies"]),"signalling_questions":total,"applicability_items":apps}

def main()->int:
 p=argparse.ArgumentParser()
 p.add_argument("--repo-root",type=Path,default=Path(__file__).resolve().parents[1])
 args=p.parse_args()
 try:v=validate(args.repo_root)
 except (ValueError,KeyError,OSError,TypeError,json.JSONDecodeError) as e:
  print("FAIL RH-07 preassessment: "+str(e));return 1
 print("PASS RH-07 structural preassessment: "+" ".join(f"{k}={n}" for k,n in v.items()))
 print("LIMIT: no question was clinically rated or answered; does not score PROBAST+AI")
 return 0

if __name__=="__main__":raise SystemExit(main())
