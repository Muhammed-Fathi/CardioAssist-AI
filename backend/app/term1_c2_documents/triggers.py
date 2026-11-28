"""Migration-08 trigger definitions used by integrated startup verification.

The migration is the canonical SQL source. This module exposes its thirteen
new document triggers plus the replacement assessment-scope trigger, without
copying DDL into a second source of truth.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[3]
    / "backend"
    / "migrations"
    / "versions"
    / "20261128_08_c2_documents_ocr.py"
)


def _load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "cardioassist_c2_documents_migration_08", _MIGRATION_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("The C2 document migration trigger source is unavailable.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_MIGRATION = _load_migration()
DOCUMENT_TRIGGER_DEFINITIONS: dict[str, str] = dict(_MIGRATION.TRIGGER_DEFINITIONS)
# Migration 08 replaces one core 07 trigger under the same name so the
# assessment scope guard admits only verified, snapshot-backed DOC bindings.
ASSESSMENT_SCOPE_TRIGGER_OVERRIDE: str = (
    _MIGRATION.ASSESSMENT_SCOPE_TRIGGER_DEFINITION
)
