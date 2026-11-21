"""Mechanical RH-03 reporting verification and deliberate anchor-drift negative path."""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILES = [
    "docs/research/next_phase/AI12_2_GRADUATION_RESEARCH_MANUSCRIPT_DRAFT_2026_11_19.md",
    "docs/research/next_phase/RH03_AI12_2_AUDIT_MATRIX_2026_11_19.json",
    "docs/research/next_phase/RH03_REPORTING_CROSSWALK_2026_11_21.json",
    "docs/research/next_phase/RH03_REPORTING_CROSSWALK_2026_11_21.md",
]
VERIFY = ROOT / "scripts/verify_rh03_reporting_alignment.py"


def _run(root):
    return subprocess.run(
        [sys.executable, str(VERIFY), "--repo-root", str(root)],
        capture_output=True, text=True, check=False,
    )


def test_real_reporting_sources_have_coherent_anchors():
    result = _run(ROOT)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "claims=28" in result.stdout
    assert "tripod_main_items=27" in result.stdout
    assert "probast_domains=4" in result.stdout


def test_tampered_manuscript_anchor_is_rejected(tmp_path):
    for relative in FILES:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
    path = tmp_path / FILES[0]
    content = path.read_text(encoding="utf-8")
    assert "## FR-08." in content
    path.write_text(content.replace("## FR-08.", "## FR-XX.", 1), encoding="utf-8")
    result = _run(tmp_path)
    assert result.returncode != 0
    assert "FAIL" in result.stdout


def test_tampered_claim_status_is_rejected(tmp_path):
    for relative in FILES:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
    import json
    path = tmp_path / FILES[1]
    matrix = json.loads(path.read_text(encoding="utf-8"))
    matrix["claims"][0]["content_check"]["status"] = "PASS_SOURCE_MATCH"
    path.write_text(json.dumps(matrix, indent=2) + "\n", encoding="utf-8")
    result = _run(tmp_path)
    assert result.returncode != 0
    assert "Source-check statuses" in result.stdout
