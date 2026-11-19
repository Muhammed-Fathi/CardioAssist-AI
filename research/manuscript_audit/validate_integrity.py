"""Read-only structural/provenance checks for the AI-12.2 audit evidence pack.

This validates inventory, cross-links, line anchors, reviewer-action status and
Git object identity. It does not validate scientific meaning or rerun research.
"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = "9606b955b5c5906031ee88de704c3825b1f8b914"
DIR = "docs/research/next_phase/"
MANUSCRIPT = DIR + "AI12_2_GRADUATION_RESEARCH_MANUSCRIPT_DRAFT_2026_11_19.md"
COVERAGE = DIR + "AI12_2_MANUSCRIPT_COVERAGE_2026_11_19.json"
INDEX = DIR + "RH01_CLAIM_EVIDENCE_INDEX_2026_11_19.json"
MATRIX = DIR + "RH03_AI12_2_AUDIT_MATRIX_2026_11_19.json"
ALLOWED = {"PASS_SOURCE_MATCH", "MISMATCH", "NOT_VERIFIABLE", "OUT_OF_SCOPE"}

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

def _line_span(span: str, line_count: int) -> tuple[int, int]:
    try:
        a, b = (int(v) for v in span.split("-", 1))
    except (AttributeError, ValueError) as exc:
        raise IntegrityError(f"invalid manuscript line span: {span!r}") from exc
    if a < 1 or b < a or b > line_count:
        raise IntegrityError(f"manuscript line span out of range: {span}")
    return a, b

def validate_matrix(repo: Path = ROOT, base: str = BASE, *, coverage=None, index=None, matrix=None, manuscript_text=None, blob_resolver=None) -> dict:
    coverage = coverage if coverage is not None else _json(repo / COVERAGE)
    index = index if index is not None else _json(repo / INDEX)
    matrix = matrix if matrix is not None else _json(repo / MATRIX)
    manuscript_text = manuscript_text if manuscript_text is not None else (repo / MANUSCRIPT).read_text(encoding="utf-8")
    resolver = blob_resolver or (lambda path: _blob_sha(repo, base, path))
    lines = manuscript_text.splitlines()
    expected_fr = {f"FR-{i:02}" for i in range(1, 18)}
    expected_cl = {f"CL-{i:03}" for i in range(1, 29)}
    cov_chapters = {x.get("id"): x for x in coverage.get("report_chapters", [])}
    source_claims = {x.get("id"): x for x in index.get("claims", [])}
    chapters = {x.get("id"): x for x in matrix.get("chapters", [])}
    claims = {x.get("claim_id"): x for x in matrix.get("claims", [])}
    if set(cov_chapters) != expected_fr or set(chapters) != expected_fr:
        raise IntegrityError("coverage/matrix must contain FR-01 through FR-17 exactly once")
    if set(source_claims) != expected_cl or set(claims) != expected_cl:
        raise IntegrityError("RH-01/matrix must contain CL-001 through CL-028 exactly once")
    if len(matrix.get("claims", [])) != 28 or len(matrix.get("chapters", [])) != 17:
        raise IntegrityError("duplicate FR or CL identifiers")
    for fr, ch in chapters.items():
        a, b = _line_span(ch.get("line_span"), len(lines))
        if ch.get("source_claim_ids") != cov_chapters[fr].get("source_claim_ids"):
            raise IntegrityError(f"{fr}: claim crosswalk differs from coverage")
        if not any(lines[i-1].startswith(f"## {fr}.") for i in range(a, b+1)):
            raise IntegrityError(f"{fr}: line span does not contain its manuscript heading")
    for cid, row in claims.items():
        original = source_claims[cid]
        if row.get("indexed_claim") != original.get("statement"):
            raise IntegrityError(f"{cid}: indexed claim text mismatch")
        src = row.get("source", {})
        for key, expected in (("path", original.get("source_path")), ("pinned_blob_sha", original.get("source_blob_sha")), ("indexed_section", original.get("source_section"))):
            if src.get(key) != expected:
                raise IntegrityError(f"{cid}: source mapping mismatch for {key}")
        actual = resolver(src["path"])
        if actual != original["source_blob_sha"] or src.get("actual_blob_sha_at_base") != actual or src.get("blob_match") is not True:
            raise IntegrityError(f"{cid}: source blob mismatch")
        status = row.get("content_check", {}).get("status")
        if status not in ALLOWED:
            raise IntegrityError(f"{cid}: invalid content-check enum {status!r}")
        if not row.get("content_check", {}).get("reason_or_specific_reviewer_task"):
            raise IntegrityError(f"{cid}: missing content-check rationale")
        occurrences = row.get("manuscript_occurrences", [])
        if not occurrences:
            raise IntegrityError(f"{cid}: no manuscript occurrence/anchor")
        for occ in occurrences:
            if occ.get("chapter") not in expected_fr:
                raise IntegrityError(f"{cid}: invalid report chapter")
            a, b = _line_span(occ.get("line_span"), len(lines))
            if not any(lines[i-1].startswith(f"## {occ['chapter']}.") for i in range(a, b+1)):
                raise IntegrityError(f"{cid}: occurrence span does not contain chapter heading")
            for excerpt in occ.get("matched_report_lines", []):
                n = excerpt.get("line")
                if not isinstance(n, int) or n < a or n > b or lines[n-1].strip() != excerpt.get("text"):
                    raise IntegrityError(f"{cid}: manuscript excerpt anchor mismatch")
    expected_actions = {x.get("id"): x for x in coverage.get("reviewer_actions", [])}
    actions = {x.get("id"): x for x in matrix.get("reviewer_actions", [])}
    if len(expected_actions) != 10 or set(actions) != set(expected_actions):
        raise IntegrityError("matrix must carry all 10 reviewer actions")
    for rid, original in expected_actions.items():
        action = actions[rid]
        if action.get("task") != original.get("task") or action.get("status") != "PENDING" or action.get("status") != original.get("status") or action.get("audit_disposition") != "UNCHANGED_PENDING":
            raise IntegrityError(f"{rid}: reviewer action status/task drift")
    # Explicitly prohibit the validator from accepting a matrix that declares approval/GO.
    serialized = json.dumps(matrix).lower()
    if any(token in serialized for token in ('"clinical_go": true', '"approved_for_clinical_use": true', '"formal_acceptance": true')):
        raise IntegrityError("matrix must not assert clinical GO or formal approval")
    return {"status": "PASS", "base": base, "chapters": 17, "claims": 28, "reviewer_actions_pending": 10,
            "content_status_counts": {s: sum(r["content_check"]["status"] == s for r in claims.values()) for s in sorted(ALLOWED)},
            "scope_note": "Structural cross-link, line-anchor and Git provenance checks only; not scientific validation."}

def validate(repo: Path = ROOT, base: str = BASE) -> dict:
    return validate_matrix(repo, base)

if __name__ == "__main__":
    print(json.dumps(validate(), indent=2))
