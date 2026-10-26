#!/usr/bin/env python3
"""Maintainer validation CLI for Windows Python 3.12 (NTFS) & POSIX runtimes.

Usage (PowerShell from repository root on Windows):
    python scripts/validate_ai_windows_compat.py
"""
from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ai.validation_harness import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
