# C1 Native Windows Verification Runbook

**Scope:** Term 1 C1 backend surface (20 operations) on native Windows / NTFS.
**Status:** NOT_RUN (awaiting native Windows execution)

## Purpose

Verify that the C1 backend surface behaves identically on native Windows as it
does on Linux, using only pinned dependencies and a clean detached worktree.
This is the Windows acceptance gate for F5.

## Prerequisites

- Native Windows (Windows_NT). This script does NOT run under WSL, Linux, or
  macOS.
- Python 3.12 available as `py -3.12`.
- Git on PATH.
- A clean detached worktree at the exact commit listed below.

## Procedure

Run from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify_c1_windows.ps1 `
  -ExpectedSha <40-hex-commit-sha>
```

The script:

1. Asserts `OS == Windows_NT` (fails on non-Windows).
2. Asserts detached HEAD at `<ExpectedSha>` (exact 40-hex SHA).
3. Asserts a clean worktree (`git status --porcelain` empty).
4. Creates a fresh Python 3.12 venv under `%LOCALAPPDATA%\C1WIN-<guid>`.
5. Installs `backend/requirements.txt` + `backend/requirements-dev.txt`.
6. Runs `pip check` (dependency consistency).
7. Runs `scripts/verify_sources.py` (source-file SHA256 + supervisor audit).
8. Runs `tests/backend/c1/` with `-W error` (20 C1 operations + migrations).
9. Runs `tests/contracts/` with `-W error` (306 contract tests).
10. Runs `test_c1_audit_and_keycheck.py` twice, asserting byte-identical
    output (determinism).
11. Runs the full C1 suite once more and asserts exit code 0.
12. Asserts `git diff --check` against the base commit `310534e1`.
13. Asserts a clean worktree again after all runs.
14. Retains all outputs under `%LOCALAPPDATA%\C1WIN-<guid>\`.

## Expected outcomes

| Step | Expected result |
|------|-----------------|
| venv creation | exit 0 |
| pip install | exit 0, no conflicts |
| pip check | exit 0 |
| verify_sources.py | all SHA256 + supervisor statuses OK |
| C1 backend suite | all tests pass, `-W error` |
| Contract suite | 306 tests pass, `-W error` |
| Determinism check | byte-identical output across two runs |
| Full C1 re-run | exit 0 |
| Worktree clean | before and after all runs |

## Failure handling

- Any non-zero exit aborts the script with `throw`.
- Local outputs under `%LOCALAPPDATA%\C1WIN-<guid>\` are retained for review.
- Do NOT delete the worktree or the retained outputs on failure.

## Related artifacts

- `scripts/verify_c1_windows.ps1` — the PowerShell verification script (this runbook's automation).
- `scripts/verify_ai12_windows.ps1` — the sibling AI-12 research Windows verification (different scope).
- `backend/requirements.txt` — pinned C1 runtime dependencies.
- `backend/requirements-dev.txt` — pinned C1 dev/test dependencies.
- `tests/backend/c1/` — C1 backend test suite (20 operations).
- `tests/contracts/` — contract conformance suite (306 tests).
