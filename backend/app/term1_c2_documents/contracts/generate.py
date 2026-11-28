"""Render the Track 2 DOC contract artifacts from the authoritative source.

Run ``python -m backend.app.term1_c2_documents.contracts.generate`` to (re)write:

* ``paths-documents.yaml``   — DOC1–DOC7 operations (C1 paths format);
* ``errors.c2.yaml`` / ``errors.c2.json`` — the additive C2 error catalogue;
* ``schemas/*.schema.json``  — request/response JSON Schemas.

Track 1 merges these into ``shared/contracts/term1/`` and the composed OpenAPI.
The generator is deterministic so the contract test can detect any drift.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from .operations import ERROR_CODES, OPERATIONS, SCHEMAS

HERE = Path(__file__).resolve().parent


def _write_json(path: Path, document: dict) -> None:
    path.write_text(json.dumps(document, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def generate() -> list[Path]:
    written: list[Path] = []

    schemas_dir = HERE / "schemas"
    schemas_dir.mkdir(exist_ok=True)
    for name, schema in SCHEMAS.items():
        target = schemas_dir / name
        _write_json(target, schema)
        written.append(target)

    paths_doc = {
        "status": "PROPOSED — NOT APPROVED, NOT DEPLOYED",
        "server": "/v1",
        "content_type": "application/json",
        "contract_version": "v1",
        "stage": "C2",
        "synthetic_data_only": True,
        "description": (
            "Track 2 C2 SAFE_SCOPE bounded document intake + genuine local OCR "
            "(DOC1–DOC7). Fabricated demo fixtures only; exact server-owned SHA-256 "
            "allowlist; isolated unprivileged OCR worker; no inference dispatch; "
            "patient confirmation is not clinician verification."
        ),
        "cross_cutting_rules": {
            "authentication": "Authorization: Bearer <session_token>; never in body/query/cookie",
            "idempotency": "Exactly one Idempotency-Key on DOC1/DOC5/DOC7",
            "ownership": "Wrong-owner reads return 404 document_not_found (no IDOR oracle)",
            "consent": "Active synthetic-demo consent re-checked on every mutating operation and replay",
            "cache": "Cache-Control: no-store on every JSON response; binary adds nosniff + CSP",
        },
        "operations": OPERATIONS,
    }
    paths_path = HERE / "paths-documents.yaml"
    paths_path.write_text(yaml.safe_dump(paths_doc, sort_keys=False, allow_unicode=True),
                          encoding="utf-8")
    written.append(paths_path)

    errors_doc = {
        "contract_version": "v1",
        "stage": "C2",
        "status": "PROPOSED — NOT APPROVED, NOT DEPLOYED",
        "source": "backend/app/term1_c2_documents/errors.py::DOCUMENT_ERROR_CATALOGUE",
        "envelope": {"contract_version": "v1", "error": {"code": "str", "message": "str"}},
        "description": (
            "Additive C2 document/OCR error catalogue. The frozen C1 catalogue "
            "(37 codes) is unchanged; these codes are merged by Track 1. Messages "
            "are static per code and never embed a submitted value or identifier."
        ),
        "codes": ERROR_CODES,
    }
    errors_yaml = HERE / "errors.c2.yaml"
    errors_yaml.write_text(yaml.safe_dump(errors_doc, sort_keys=False, allow_unicode=True),
                           encoding="utf-8")
    written.append(errors_yaml)
    errors_json = HERE / "errors.c2.json"
    _write_json(errors_json, errors_doc)
    written.append(errors_json)

    return written


if __name__ == "__main__":
    for path in generate():
        print(f"wrote {path}")
