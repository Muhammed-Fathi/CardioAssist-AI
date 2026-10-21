# Proposed GitHub Actions Workflow for Audit Tests (`audit-ci.yml`)

## Why This File Is Stored Under `research/audit/ci/`

The existing repository workflows (`.github/workflows/backend-ci.yml` and `.github/workflows/frontend-ci.yml`) run `tests/contract` and `tests/backend` (plus frontend checks), and do **not** execute `tests/audit`.

Because the automated coding agent's GitHub App token does not hold the `workflows` permission required by GitHub to push changes under `.github/workflows/*`, the complete, tested workflow configuration is committed here at:

- `research/audit/ci/audit-ci.yml.example`

**Important Status Note**: Until a human maintainer with `.github/workflows` push permission installs `.github/workflows/audit-ci.yml` on the PR branch and a GitHub Actions run completes, **GitHub Actions has not yet executed `tests/audit` in remote CI** (only `Backend Contract & Test CI` runs automatically on PR #11).

---

## Maintainer Installation Procedure Before Merging PR #11 (Windows PowerShell)

> **Critical Branch Note**: `research/audit/ci/audit-ci.yml.example` exists on the PR #11 branch (`arena/a1f1816a-cardioassist-ai`), **not** on `main` prior to merge. Run these commands from a verified checkout of `arena/a1f1816a-cardioassist-ai`.

```powershell
Set-Location "E:\CardioAssist_AI_GitHub_Starter"

# 1. Fetch origin and check out the exact PR #11 branch (NOT stale main)
git fetch origin arena/a1f1816a-cardioassist-ai
git checkout arena/a1f1816a-cardioassist-ai
git pull --ff-only origin arena/a1f1816a-cardioassist-ai

# 2. Confirm local HEAD matches remote PR branch HEAD with no divergence
$localHead = (git rev-parse HEAD).Trim()
$remoteHead = (git rev-parse origin/arena/a1f1816a-cardioassist-ai).Trim()
if ($localHead -ne $remoteHead) {
    throw "STOP: Local HEAD ($localHead) diverged from origin/arena/a1f1816a-cardioassist-ai ($remoteHead)."
}
if (-not (Test-Path "research\audit\ci\audit-ci.yml.example")) {
    throw "STOP: research\audit\ci\audit-ci.yml.example not found. Confirm you are on branch arena/a1f1816a-cardioassist-ai."
}

# 3. Guard against overwriting an existing workflow file unintentionally
if (Test-Path ".github\workflows\audit-ci.yml") {
    throw "STOP: .github\workflows\audit-ci.yml already exists. Inspect it before overwriting."
}

# 4. Copy the proposed workflow into .github/workflows/audit-ci.yml
Copy-Item "research\audit\ci\audit-ci.yml.example" ".github\workflows\audit-ci.yml" -ErrorAction Stop

# 5. Run the local audit test suite to confirm everything passes before pushing
pytest tests/audit -q
python -m research.audit --dry-run
python -m research.audit self-test

# 6. Commit and push to the PR #11 branch (only after confirming no remote divergence)
git fetch origin arena/a1f1816a-cardioassist-ai
if ((git rev-parse HEAD).Trim() -ne (git rev-parse origin/arena/a1f1816a-cardioassist-ai).Trim()) {
    throw "STOP: Remote branch updated since fetch; pull/rebase before pushing."
}
git add .github/workflows/audit-ci.yml
git commit -m "ci(audit): enable GitHub Actions workflow for M2a read-only audit tests"
git push origin arena/a1f1816a-cardioassist-ai
```

### Verification Before Merge

After pushing `.github/workflows/audit-ci.yml` to `arena/a1f1816a-cardioassist-ai`:
1. Check PR #11 checks (`gh pr checks 11` or the GitHub Actions tab).
2. Verify that **`Audit Toolchain & Source Integrity CI`** runs `pytest tests/audit -q`, `python -m research.audit --dry-run`, `python -m research.audit self-test`, and `python scripts/verify_sources.py` on **both Python `3.11` and Python `3.12`** and succeeds before merging PR #11.
