"""Clean-environment OCR worker launcher (Track 2, residual P0-02).

Run as the separate ``cai-ocr`` account. The reviewer residual review #7235517859
noted that a normal logon session carries non-allowlisted variables, so launching
the worker directly would trip ``verify_sanitized_env``. This launcher builds an
**exact allowlisted environment from a protected config file** — never from the
inherited logon environment — and starts the worker with that environment block,
so no backend secret / AI binding can leak into the worker and startup passes the
strict allowlist.

Usage (owner-executed on Windows)::

    runas /user:cai-ocr "python -m backend.app.term1_c2_documents.windows_launch_worker ^
        --config C:\\ocr\\worker-config.json --port 8765"

The config JSON holds only allowlisted keys (see ``ALLOWED_ENV``). The launcher
refuses any non-allowlisted key and any missing required key, then launches
``python -m backend.app.term1_c2_documents.worker`` with the clean environment.

This module is stdlib-only and cross-platform; ``build_clean_env`` is unit-tested
on Linux. Native Windows execution is an OWNER procedure (NOT_RUN from the Linux
sandbox); see WINDOWS_OCR_WORKER_RUNBOOK.md.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# Must match worker._ALLOWED_ENV exactly (a unit test asserts this).
ALLOWED_ENV = frozenset({
    "PATH", "TESSDATA_PREFIX", "LANG", "LC_ALL",
    "CARDIOASSIST_OCR_IPC_TOKEN", "CARDIOASSIST_PRIVATE_DOC_DIR",
    "CARDIOASSIST_TESSERACT_CMD", "CARDIOASSIST_OCR_FIXTURE_MANIFEST",
    "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATHEXT",
})
REQUIRED_ENV = frozenset({
    "CARDIOASSIST_OCR_IPC_TOKEN", "CARDIOASSIST_PRIVATE_DOC_DIR",
    "CARDIOASSIST_TESSERACT_CMD", "TESSDATA_PREFIX",
})


class LauncherError(RuntimeError):
    """The launcher configuration is not a safe, clean worker environment."""


def build_clean_env(config: dict, *, os_defaults: dict | None = None) -> dict:
    """Build an exact allowlisted environment from ``config`` (never inherited).

    Refuses any non-allowlisted key and any missing required key. Minimal OS
    variables (SYSTEMROOT/WINDIR/TEMP/TMP/PATHEXT/PATH) may be supplied via
    ``os_defaults`` if absent from the config; nothing else is inherited.
    """
    if not isinstance(config, dict):
        raise LauncherError("Worker config must be a JSON object.")
    extra = sorted(set(config) - ALLOWED_ENV)
    if extra:
        raise LauncherError("Worker config carries non-allowlisted keys: " + ", ".join(extra))
    env = {k: str(v) for k, v in config.items()}
    defaults = os_defaults or {}
    for key in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATHEXT", "PATH"):
        if key not in env and key in defaults:
            env[key] = str(defaults[key])
    missing = sorted(REQUIRED_ENV - set(env))
    if missing:
        raise LauncherError("Worker config is missing required keys: " + ", ".join(missing))
    # Defence in depth: the result must be exactly within the allowlist.
    assert set(env) <= ALLOWED_ENV
    return env


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Protected worker-config.json path")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    # Only the minimal OS variables are taken from the launcher's own session; the
    # secret/operator settings come exclusively from the protected config.
    os_defaults = {k: os.environ[k] for k in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATHEXT", "PATH")
                   if k in os.environ}
    env = build_clean_env(config, os_defaults=os_defaults)
    raise SystemExit(subprocess.call(
        [sys.executable, "-m", "backend.app.term1_c2_documents.worker", "--port", str(args.port)],
        env=env,
    ))


if __name__ == "__main__":
    main()
