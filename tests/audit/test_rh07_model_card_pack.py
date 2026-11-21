"""RH-07 drafted model-card pack: conservative source and safety checks."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
VERIFY=ROOT/"scripts/verify_rh07_model_card_pack.py"
DOC="docs/research/next_phase/RH07_SOURCE_BOUND_MODEL_CARDS_DRAFT_2026_11_21.json"
MD="docs/research/next_phase/RH07_SOURCE_BOUND_MODEL_CARDS_DRAFT_2026_11_21.md"
PATHS=[DOC,MD,"ai/research_registry.py","research/intake/fixtures/offline_io.v1.json","research/uci412/feature_schema.py","docs/research/ai12_1/linux-uci45-envelope.v1.json","ai/panels.py","ai/research_routes.py","ai/research_catalog.py","docs/research/gate-pt/04_d047_first_internal_results_REVIEW_DRAFT.md","docs/research/gate-pt/11_two_dataset_scientific_evidence_synthesis_REVIEW_DRAFT.md"]

def _run(root:Path):
    return subprocess.run([sys.executable,str(VERIFY),"--repo-root",str(root)],text=True,capture_output=True,check=False)

def _copy(tmp_path:Path):
    for relative in PATHS:
        target=tmp_path/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/relative,target)

def test_complete_model_card_pack():
    p=_run(ROOT)
    assert p.returncode==0,p.stdout+p.stderr
    assert "registry_cards=5" in p.stdout and "historical_cards=2" in p.stdout

def test_false_clinical_serving_is_rejected(tmp_path):
    _copy(tmp_path)
    path=tmp_path/DOC
    data=json.loads(path.read_text(encoding="utf-8"))
    data["registry_cards"][0]["approved_for_serving"]=True
    path.write_text(json.dumps(data),encoding="utf-8")
    result=_run(tmp_path)
    assert result.returncode!=0 and "unsafe card authorization" in result.stdout

def test_blocked_route_score_promotion_is_rejected(tmp_path):
    _copy(tmp_path)
    path=tmp_path/DOC
    data=json.loads(path.read_text(encoding="utf-8"))
    data["registry_cards"][2]["may_report_synthetic_score"]=True
    path.write_text(json.dumps(data),encoding="utf-8")
    result=_run(tmp_path)
    assert result.returncode!=0 and "false score permission" in result.stdout

def test_historical_result_not_promoted_to_independent_rerun(tmp_path):
    _copy(tmp_path)
    path=tmp_path/DOC
    data=json.loads(path.read_text(encoding="utf-8"))
    data["historical_benchmarks"][0]["independently_verified_reexecution"]=True
    path.write_text(json.dumps(data),encoding="utf-8")
    result=_run(tmp_path)
    assert result.returncode!=0 and "historical evidence promoted" in result.stdout
