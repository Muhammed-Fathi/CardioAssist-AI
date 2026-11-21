#!/usr/bin/env python3
"""RH-07 model-card identity/source guard; stdlib-only, read-only, no model execution."""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

DOC = Path("docs/research/next_phase/RH07_SOURCE_BOUND_MODEL_CARDS_DRAFT_2026_11_21.json")
MD = Path("docs/research/next_phase/RH07_SOURCE_BOUND_MODEL_CARDS_DRAFT_2026_11_21.md")
REG = Path("ai/research_registry.py")
FIXTURES = Path("research/intake/fixtures/offline_io.v1.json")
CLEVELAND_CARD = Path("docs/research/ai12_1/linux-uci45-envelope.v1.json")

def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)

def registry_entries(path: Path) -> dict[str, dict]:
    parsed = ast.parse(path.read_text(encoding="utf-8"))
    method = next(n for n in parsed.body if isinstance(n, ast.FunctionDef) and n.name == "_build_registry")
    out = {}
    for node in ast.walk(method):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_build_entry"):
            continue
        kws = {k.arg:k.value for k in node.keywords}
        mid = ast.literal_eval(kws["model_id"])
        ver = ast.literal_eval(kws["model_version"])
        route = ast.literal_eval(kws["route_id"])
        state = kws["entry_state"]
        require(isinstance(state, ast.Name), "registry state must be a named constant")
        key = mid + "@" + ver
        require(key not in out, "duplicate registry model")
        out[key] = {"model_id":mid, "model_version":ver, "route_id":route, "entry_state_symbol":state.id}
    return out

def verify(root: Path) -> dict[str,int]:
    d=json.loads((root / DOC).read_text(encoding="utf-8"))
    md=(root / MD).read_text(encoding="utf-8")
    source=registry_entries(root / REG)
    fixture=json.loads((root / FIXTURES).read_text(encoding="utf-8"))
    existing=json.loads((root / CLEVELAND_CARD).read_text(encoding="utf-8"))["model_card"]
    require(d["schema_id"] == "cardioassist.rh07.model_cards_draft/v1", "unknown schema")
    require(d["status"] == "DRAFT_SOURCE_BOUND_NOT_REVIEWER_ACCEPTED" and d["final_model_card_acceptance"] is False, "false acceptance")
    require(d["clinical_use_authorized"] is False and d["real_data_executed_in_this_work"] is False, "unsafe real/clinical claim")
    entries=d["registry_cards"]
    require(len(entries)==len(source)==5, "registry card count mismatch")
    require({x["model_key"] for x in entries} == set(source), "missing or duplicated registry card")
    for card in entries:
        key=card["model_key"]
        for field,value in source[key].items():
            require(card[field] == value, "registry identity/state mismatch " + key + ":" + field)
        route=card["route_id"]
        require(route in fixture["requests"], "missing fixture request " + route)
        request=fixture["requests"][route]
        require(request["model_id"]==card["model_id"] and request["model_version"]==card["model_version"] and request["dataset_id"]==card["dataset_id"], "fixture request identity mismatch " + key)
        golden=next((v for v in fixture["cases"] if v["id"]==route), None)
        require(golden is not None and golden["expected"]["status"]==card["fixture_expected_status"], "frozen fixture output mismatch " + key)
        active=(card["entry_state_symbol"]=="ENTRY_STATE_ACTIVE")
        require(card["classification"]==("EXECUTABLE_OFFLINE_SYNTHETIC_ONLY" if active else "NON_EXECUTABLE_CONTRACT_ONLY"), "executable class mismatch")
        require(card["may_report_synthetic_score"] is active, "false score permission")
        require(card["fixture_expected_status"]==("SYNTHETIC_RESULT" if active else "UNAVAILABLE"), "blocked route claims result")
        require(card["real_model_fitted_in_this_review"] is False and card["artifact_identity_verified_in_this_review"] is False and card["approved_for_serving"] is False and card["clinical_use_authorized"] is False and card["may_report_real_patient_probability"] is False, "unsafe card authorization/verification promotion")
        require(card["human_review"] == "PENDING", "invented reviewer")
        require(f"`{key}`" in md, "Markdown model row absent")
        for path in card["verification_sources"]:
            require((root / path).is_file(), "missing provenance file: " + path)
    uc=next(x for x in entries if x["route_id"]=="da_a1_basic_clinical_v1")
    src_uci=(root / "research/uci412/feature_schema.py").read_text(encoding="utf-8")
    ast_uci=ast.parse(src_uci)
    panel=next(n.value for n in ast_uci.body if isinstance(n,ast.AnnAssign) and isinstance(n.target,ast.Name) and n.target.id=="PRIMARY_PANEL_COLUMNS")
    require(uc["feature_order_reference"] == list(ast.literal_eval(panel)), "UCI-412 ordered panel drift")
    ca=next(x for x in entries if x["route_id"]=="da_a2_resting_v1")
    require(ca["model_id"]==existing["model"]["id"] and ca["model_version"]==existing["model"]["version"], "Cleveland fixture card identity drift")
    require(ca["feature_order_reference"] == [x["name"] for x in existing["panel"]["fields"]], "Cleveland feature order drift")
    require(all(x["feature_order_reference"] is None for x in entries if x["classification"]=="NON_EXECUTABLE_CONTRACT_ONLY"),"unverified blocked panel falsely copied")
    hist=d["historical_benchmarks"]
    require(len(hist)==2 and {x["id"] for x in hist} == {"D-047_CLEVELAND_HISTORICAL","M3A_UCI412_HISTORICAL"}, "historical studies inventory missing")
    for h in hist:
        source_text=(root / h["source_file"]).read_text(encoding="utf-8")
        require(h["n"]==303 and h["positive"]+h["negative"]==h["n"],"historical count drift")
        require(h["evidence_status"]=="MAINTAINER_REPORTED_ARCHIVED_AGGREGATES_NOT_INDEPENDENTLY_RERUN" and h["independently_verified_reexecution"] is False and h["clinical_or_external_validation"] is False and h["actual_fitted_deployable_artifact_in_public_repo"] is False, "historical evidence promoted")
        for name,value in h["metrics_maintainer_reported"].items():
            require(value in source_text, "historic reported source metric absent: "+h["id"]+":"+name)
            require(value in md, "historic document metric absent: "+h["id"]+":"+name)
    require(d["source_main_sha"] == "8f11b188f0e0326d1b06f76fc2e36eb564898ff0", "intake source SHA unexpectedly changed")
    return {"registry_cards":len(entries),"historical_cards":len(hist),"fixture_requests":len(fixture["requests"])}

def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--repo-root",type=Path,default=Path(__file__).resolve().parents[1])
    args=parser.parse_args()
    try:
        result=verify(args.repo_root)
    except (ValueError,KeyError,OSError,StopIteration,TypeError,json.JSONDecodeError,SyntaxError) as e:
        print("FAIL RH-07 model-card consistency: "+str(e))
        return 1
    print("PASS RH-07 model-card source/fixture identity: "+" ".join(f"{k}={v}" for k,v in result.items()))
    print("LIMIT: this is a mechanical source/fixture check, not original real-data rerun or medical review")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
