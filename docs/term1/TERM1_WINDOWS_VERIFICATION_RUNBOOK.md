# CardioAssist-Term1 — Stage-Based Windows PowerShell Verification Runbook

**Status:** corrected procedure; `NOT_RUN` until the owner executes it and supplies output.
**Workspace:** `E:\CardioAssist-Term1-Prototype` (owner-controlled).
**PowerShell:** 5.1 compatible. Python 3.11 or 3.12 supported.
**Supersedes for new use:** the draft `WINDOWS_LOCAL_VERIFICATION_RUNBOOK_20261125.md` clone-to-default-folder and cleanup workflow; that historical file is preserved unchanged.

## 1. Safety rules

- Never overwrite a non-empty directory; reuse only a verified clean clone of the expected branch.
- No `git reset --hard`, `git clean`, `Remove-Item` of databases, destructive Alembic downgrade against owner data, or broad delete.
- Every native command checks `$LASTEXITCODE` explicitly; `$ErrorActionPreference='Stop'` alone is insufficient.
- Use a unique disposable DB per test run; use a separate preservation DB for upgrade/restart evidence.
- Never commit or upload `.env`, secrets, DB files, logs containing credentials, identifiers, or model artifacts.
- Do not invent API commands: stage-specific smoke uses only endpoints and fixtures actually shipped at that stage's exact head.

## 2. Reusable helper and verified clone

```powershell
$ErrorActionPreference = 'Stop'
function Invoke-Checked {
    param([string]$Command, [string[]]$Arguments)
    & $Command @Arguments
    $code = $LASTEXITCODE
    if ($null -eq $code -or $code -ne 0) {
        throw "Native command failed with exit code $code : $Command $($Arguments -join ' ')"
    }
}

$Target = 'E:\CardioAssist-Term1-Prototype'
$RepoUrl = 'https://github.com/Muhammed-Fathi/CardioAssist-AI.git'
$Branch = 'delivery/term1-prototype'
$ExpectedHead = '<PASTE_EXACT_ACCEPTED_STAGE_HEAD_SHA>'
# For C0 baseline only, before any accepted stage commit, use:
# $ExpectedHead = 'bca75b4646dbde26e495201938b7ae01ea7e0d21'

if (-not (Test-Path -LiteralPath $Target)) {
    New-Item -ItemType Directory -Path $Target | Out-Null
    Invoke-Checked -Command git -Arguments @('clone','--single-branch','--branch',$Branch,$RepoUrl,$Target)
} else {
    $Items = @(Get-ChildItem -LiteralPath $Target -Force)
    if ($Items.Count -eq 0) {
        Invoke-Checked -Command git -Arguments @('clone','--single-branch','--branch',$Branch,$RepoUrl,$Target)
    }
}
Set-Location $Target

$Origin = (git remote get-url origin).Trim()
if ($Origin -ne $RepoUrl) { throw "Unexpected origin: $Origin" }
$CurrentBranch = (git rev-parse --abbrev-ref HEAD).Trim()
if ($CurrentBranch -ne $Branch) { throw "Unexpected branch: $CurrentBranch" }

if (git status --porcelain) { throw 'Dirty worktree; refusing to update or verify.' }
Invoke-Checked -Command git -Arguments @('fetch','origin',$Branch)
Invoke-Checked -Command git -Arguments @('merge','--ff-only',"origin/$Branch")

$ActualHead = (git rev-parse HEAD).Trim()
if ($ActualHead -ne $ExpectedHead) { throw "Unexpected HEAD: $ActualHead" }
if (git status --porcelain) { throw 'Dirty worktree after update; refusing verification.' }
Write-Host "Verified $Branch at $ActualHead"
```

## 3. Python and pinned dependencies

```powershell
$Py = & python --version 2>&1
if ($Py -notmatch 'Python 3\.(11|12)\.') { throw "Unsupported Python: $Py" }
if (-not (Test-Path .\.venv\Scripts\python.exe)) {
    Invoke-Checked -Command python -Arguments @('-m','venv','.venv')
}
$PyExe = (Resolve-Path .\.venv\Scripts\python.exe).Path
Invoke-Checked -Command $PyExe -Arguments @('-m','pip','install','--upgrade','pip')
Invoke-Checked -Command $PyExe -Arguments @('-m','pip','install','-r','backend/requirements-dev.txt')
Invoke-Checked -Command $PyExe -Arguments @('-m','pip','check')
```

For any full-suite run, also install the research pins before `pip check`:

```powershell
Invoke-Checked -Command $PyExe -Arguments @('-m','pip','install','-r','research/experiments/requirements.txt')
Invoke-Checked -Command $PyExe -Arguments @('-m','pip','install','-r','research/audit/requirements.txt')
Invoke-Checked -Command $PyExe -Arguments @('-m','pip','install','-r','research/uci412/requirements.txt')
Invoke-Checked -Command $PyExe -Arguments @('-m','pip','check')
```

## 4. Databases: unique disposable and preservation

```powershell
New-Item -ItemType Directory -Force .\var | Out-Null
$SafeBranch = $CurrentBranch -replace '[^A-Za-z0-9_-]','_'
$Disposable = "term1_${SafeBranch}_$([guid]::NewGuid().ToString('N')).sqlite3"
$env:CARDIOASSIST_DATABASE_URL = "sqlite:///./var/$Disposable"
Invoke-Checked -Command $PyExe -Arguments @('-m','alembic','upgrade','head')
Invoke-Checked -Command $PyExe -Arguments @('-m','alembic','current')
Invoke-Checked -Command $PyExe -Arguments @('-m','alembic','check')

# Separate preservation/restart DB (create once; do not delete):
$env:CARDIOASSIST_DATABASE_URL = 'sqlite:///./var/term1_upgrade_preservation.sqlite3'
Invoke-Checked -Command $PyExe -Arguments @('-m','alembic','upgrade','head')
Invoke-Checked -Command $PyExe -Arguments @('-m','alembic','current')
Invoke-Checked -Command $PyExe -Arguments @('-m','alembic','check')
```

## 5. Exact tests and repository checks

```powershell
$env:CARDIOASSIST_DATABASE_URL = "sqlite:///./var/$Disposable"
Invoke-Checked -Command $PyExe -Arguments @('-m','pytest','tests/contracts','tests/backend','-q','-W','error')
Invoke-Checked -Command $PyExe -Arguments @('-m','pytest','tests/audit','-q','-W','error')
Invoke-Checked -Command $PyExe -Arguments @('-m','pytest','tests/experiments','-q','-W','error')
Invoke-Checked -Command $PyExe -Arguments @('-m','pytest','tests/uci412','-q','-W','error')
Invoke-Checked -Command $PyExe -Arguments @('scripts/verify_sources.py')
Invoke-Checked -Command git -Arguments @('diff','--check')
```

Do not replace these exact paths with a broad `pytest -k` expression. Record exact pass/fail/skip counts and exit codes. The inherited Python 3.11 research failure is expected in the baseline; report it, do not suppress it.

## 6. Complete C0 baseline block (`NOT_RUN`)

The blocks in §§2–5 with `$ExpectedHead = 'bca75b4646dbde26e495201938b7ae01ea7e0d21'`, followed by this smoke check, constitute the complete runnable C0 baseline. It uses only existing functionality; no future API command is invented.

```powershell
# Start the current existing service in another PowerShell window with the same DB env var:
#   & $PyExe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1
$Doc = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/openapi.json'
$Paths = @($Doc.paths.PSObject.Properties.Name | Sort-Object)
$Expected = @('/v1/monitoring/observations','/v1/predictions/cad-tabular')
if (($Paths -join '|') -ne ($Expected -join '|')) { throw "Unexpected served paths: $($Paths -join ', ')" }
Write-Host 'C0 baseline OK: exactly the two legacy operations are served.'
```

C0 evidence fields: PowerShell version, OS build, Python version, `$ActualHead`, clean status, pip check output, Alembic outputs, all pytest summaries, source verification, `git diff --check`, `/openapi.json` result. All are `NOT_RUN` until supplied by the owner.

## 7. Stage-specific additions (after the relevant stage is accepted)

- **C1:** run the delivered auth/invitation/enrollment tests; smoke only the endpoints and fixtures shipped in the accepted C1 OpenAPI; two concurrent registrations with one code; logout/session invalidation; restart with preservation DB.
- **C2:** run delivered assessment/provenance/state tests; adapter tests only if Decision A is ratified; fail-closed assertions otherwise; patient projection redaction; lease recovery test with restart.
- **C3:** review/follow-up/notification tests; cross-role IDOR negatives; atomic message/notification check; read-status restart.
- **C4:** full E2E with the delivered fixture script; exact-head hosted CI links for the final SHA; no new repository or merge.

No deletion or cleanup command is provided: leave disposable DBs in `.\var` for evidence and let the owner manage them outside the repository.
