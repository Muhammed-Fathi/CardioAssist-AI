"""RH-07 PROBAST+AI intake: source inventory and anti-fabrication checks."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"scripts/verify_rh07_probast_workbook.py"
DATA="docs/research/next_phase/RH07_PROBAST_AI_QUESTION_LEVEL_WORKBOOK_2026_11_21.json"
MD="docs/research/next_phase/RH07_PROBAST_AI_QUESTION_LEVEL_WORKBOOK_2026_11_21.md"
def run(root):
 return subprocess.run([sys.executable,str(SCRIPT),"--repo-root",str(root)],text=True,capture_output=True,check=False)

def copy(tmp_path):
 d=json.loads((ROOT/DATA).read_text(encoding="utf-8"))
 for src in (DATA,MD):
  p=tmp_path/src;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/src,p)
 allpaths={s["archived_source_path"] for s in d["studies"]}
 allpaths.update(x for s in d["studies"] for q in s["questions"] for x in q["evidence_paths"])
 for source in allpaths:
  p=tmp_path/source;p.parent.mkdir(parents=True,exist_ok=True);p.write_text("sanitized source fixture",encoding="utf-8")
 return d

def test_valid_unscored_68_question_two_study_index():
 r=run(ROOT)
 assert r.returncode==0,r.stdout+r.stderr
 assert "signalling_questions=68" in r.stdout and "applicability_items=12" in r.stdout

def test_false_formal_score_is_blocked(tmp_path):
 doc=copy(tmp_path);doc["studies"][0]["questions"][0]["formal_answer"]="YES"
 (tmp_path/DATA).write_text(json.dumps(doc),encoding="utf-8")
 r=run(tmp_path)
 assert r.returncode!=0 and "fabricated assessment" in r.stdout

def test_missing_question_fails_closed(tmp_path):
 doc=copy(tmp_path);doc["studies"][1]["questions"].pop()
 (tmp_path/DATA).write_text(json.dumps(doc),encoding="utf-8")
 r=run(tmp_path)
 assert r.returncode!=0 and "missing/duplicated PROBAST" in r.stdout

def test_missing_source_ref_is_rejected(tmp_path):
 doc=copy(tmp_path);doc["studies"][0]["questions"][0]["evidence_paths"][0]="docs/does-not-exist/phantom.md"
 (tmp_path/DATA).write_text(json.dumps(doc),encoding="utf-8")
 r=run(tmp_path)
 assert r.returncode!=0 and "missing or unsafe cited source" in r.stdout
