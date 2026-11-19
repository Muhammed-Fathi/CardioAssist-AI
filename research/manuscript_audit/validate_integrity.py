"""Read-only integrity checks for the AI-12.2 scientific manuscript evidence pack.

Checks repository object provenance and structural coverage only. It does not
judge scientific truth, access datasets, execute research, or alter files.
"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = "9606b955b5c5906031ee88de704c3825b1f8b914"
MANUSCRIPT = "docs/research/next_phase/AI12_2_GRADUATION_RESEARCH_MANUSCRIPT_DRAFT_2026_11_19.md"
COVERAGE = "docs/research/next_phase/AI12_2_MANUSCRIPT_COVERAGE_2026_11_19.json"
INDEX = "docs/research/next_phase/RH01_CLAIM_EVIDENCE_INDEX_2026_11_19.json"

class IntegrityError(ValueError):
    pass

def _json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntegrityError(f"cannot read valid JSON {path}: {exc}") from exc

def _blob_sha(repo: Path, revision: str, path: str) -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", f"{revision}:{path}"], cwd=repo, text=True, stderr=subprocess.DEVNULL).strip()
    except (subprocess.CalledProcessError, OSError) as exc:
        raise IntegrityError(f"source absent at {revision}: {path}") from exc

def validate(repo: Path = ROOT, base: str = BASE) -> dict:
    manuscript = repo / MANUSCRIPT
    coverage = _json(repo / COVERAGE)
    index = _json(repo / INDEX)
    if not manuscript.is_file():
        raise IntegrityError(f"missing manuscript: {MANUSCRIPT}")
    chapters = coverage.get("report_chapters", [])
    claims = index.get("claims", [])
    if len(chapters) != 17 or {c.get("id") for c in chapters} != {f"FR-{i:02}" for i in range(1,18)}:
        raise IntegrityError("coverage must enumerate FR-01 through FR-17 exactly once")
    if len(claims) != 28 or {c.get("id") for c in claims} != {f"CL-{i:03}" for i in range(1,29)}:
        raise IntegrityError("evidence index must enumerate CL-001 through CL-028 exactly once")
    text = manuscript.read_text(encoding="utf-8")
    missing = [c["id"] for c in chapters if c["id"] not in text]
    if missing:
        raise IntegrityError(f"manuscript missing chapter identifiers: {missing}")
    checked = []
    for claim in claims:
        path, expected = claim.get("source_path"), claim.get("source_blob_sha")
        if not path or not expected or len(expected) != 40:
            raise IntegrityError(f"{claim.get('id')}: missing/malformed pinned source")
        actual = _blob_sha(repo, base, path)
        if actual != expected:
            raise IntegrityError(f"{claim['id']}: pinned blob mismatch ({expected} != {actual})")
        checked.append({"claim_id": claim["id"], "path": path, "blob_sha": actual})
    return {"status": "PASS", "base": base, "chapters": len(chapters), "claims": len(checked), "sources": checked,
            "scope_note": "Integrity/provenance and structural coverage only; not scientific validation."}

if __name__ == "__main__":
    print(json.dumps(validate(), indent=2))
