"""RH-07 intake: conservative mechanical checks, fail-closed on review promotion."""
import json
import subprocess
import sys
from pathlib import Path
from shutil import copyfile

ROOT=Path(__file__).resolve().parents[2]
VERIFY=ROOT/"scripts"/"verify_rh07_acceptance_intake.py"
DOC="docs/research/next_phase/RH07_INDEPENDENT_ACCEPTANCE_INTAKE_2026_11_21.json"
MD="docs/research/next_phase/RH07_INDEPENDENT_ACCEPTANCE_INTAKE_2026_11_21.md"
CARDS="docs/research/next_phase/RH07_MODEL_CARD_INVENTORY_2026_11_21.md"

def _run(root):
    return subprocess.run([sys.executable,str(VERIFY),"--repo-root",str(root)],capture_output=True,text=True,check=False)

def test_review_intake_15_gates_and_source_index():
    res=_run(ROOT)
    assert res.returncode==0,res.stdout+res.stderr
    assert "acceptance_checks=15" in res.stdout

def _copy(tmp_path):
    for f in (DOC,MD,CARDS):
        target=tmp_path/f
        target.parent.mkdir(parents=True,exist_ok=True)
        copyfile(ROOT/f,target)
    src=json.loads((ROOT/DOC).read_text(encoding="utf-8"))
    for row in src["checklist"]:
        for path in row["evidence_paths"]:
            target=tmp_path/path
            target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists():
                target.write_text("read-only existence test fixture",encoding="utf-8")

def test_no_false_acceptance(tmp_path):
    _copy(tmp_path)
    path=tmp_path/DOC
    data=json.loads(path.read_text(encoding="utf-8"))
    data["checklist"][0]["independent_review"]="PASSED"
    path.write_text(json.dumps(data),encoding="utf-8")
    res=_run(tmp_path)
    assert res.returncode !=0 and "review status promoted" in res.stdout

def test_no_missing_source_path(tmp_path):
    _copy(tmp_path)
    path=tmp_path/DOC
    data=json.loads(path.read_text(encoding="utf-8"))
    data["checklist"][0]["evidence_paths"][0]="docs/phantom/does_not_exist.md"
    path.write_text(json.dumps(data),encoding="utf-8")
    res=_run(tmp_path)
    assert res.returncode !=0 and "source path absent" in res.stdout
