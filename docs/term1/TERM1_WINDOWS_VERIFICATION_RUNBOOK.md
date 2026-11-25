# CardioAssist-Term1 — C0 Stage PR Windows Verification Runbook

**Status:** `NOT_RUN` until the owner executes this block and supplies the transcript.
**Workspace:** `E:\CardioAssist-Term1-Prototype` (owner-controlled).
**PowerShell:** 5.1 compatible. Python 3.11 or 3.12 supported.
**Reviewed candidate SHA:** `a32aca29f68e5330344b7cc79e9956acdf446a2a` (PR #143 head verified by the independent reviewer). If a later corrected head is separately reviewed, the reviewer must supply the replacement SHA and this constant must be updated before execution.
**Prototype base:** `bca75b4646dbde26e495201938b7ae01ea7e0d21`.
**Supersedes for new use:** the draft `WINDOWS_LOCAL_VERIFICATION_RUNBOOK_20261125.md` clone-to-default-folder and cleanup workflow; that historical file is preserved unchanged.

## 1. Safety rules

- Verify the accepted prototype branch; never check out, reset, merge into or overwrite it during candidate verification.
- Clone only into an empty target; reuse only a clean clone with the expected origin and branch.
- No `git reset --hard`, `git clean`, `Remove-Item` of databases, destructive Alembic downgrade, or broad delete. Existing files and DBs are evidence and are left in place.
- Use a separate detached worktree for the stage PR head; fail if the worktree path already contains files rather than deleting them.
- Every native Git/Python command checks `$LASTEXITCODE`, including read-only Git verification queries.
- Verify the virtualenv interpreter, not merely the host `python`.
- Use unique disposable DBs; use a separate preservation DB for the real legacy-row preservation check.
- Record every suite independently so the inherited Python 3.11 research failure cannot prevent the remaining checks.

## 2. Complete PowerShell 5.1 C0 candidate block (`NOT_RUN`)

```powershell
$ErrorActionPreference = 'Stop'
function Get-CheckedOutput {
    param([string]$Command, [string[]]$Arguments)
    $global:LASTEXITCODE = 0
    $output = & $Command @Arguments 2>&1
    $code = $LASTEXITCODE
    if ($null -eq $code -or $code -ne 0) {
        throw "Native command failed with exit code $code : $Command $($Arguments -join ' ')"
    }
    return @($output | ForEach-Object { $_.ToString() })
}
function Invoke-Checked {
    param([string]$Command, [string[]]$Arguments)
    $global:LASTEXITCODE = 0
    & $Command @Arguments
    $code = $LASTEXITCODE
    if ($null -eq $code -or $code -ne 0) {
        throw "Native command failed with exit code $code : $Command $($Arguments -join ' ')"
    }
}
function Invoke-Suite {
    param([string]$Name, [string[]]$Arguments, [string]$LogFile)
    $global:LASTEXITCODE = 0
    $watch = [Diagnostics.Stopwatch]::StartNew()
    $code = 0
    $detail = ''
    try {
        $exe = $Arguments[0]
        $rest = @($Arguments[1..($Arguments.Count - 1)])
        & $exe @rest 2>&1 | Tee-Object -FilePath $LogFile
        $code = $LASTEXITCODE
        if ($null -eq $code) { $code = 0 }
    } catch {
        $code = 1
        $detail = $_.Exception.Message
    }
    $watch.Stop()
    $script:SuiteResults += [pscustomobject]@{
        Suite = $Name
        ExitCode = $code
        Seconds = [math]::Round($watch.Elapsed.TotalSeconds, 1)
        Detail = $detail
        Log = $LogFile
    }
}

$Target = 'E:\CardioAssist-Term1-Prototype'
$RepoUrl = 'https://github.com/Muhammed-Fathi/CardioAssist-AI.git'
$PrototypeBranch = 'delivery/term1-prototype'
$ExpectedBase = 'bca75b4646dbde26e495201938b7ae01ea7e0d21'
$StageBranch = 'arena/bdbd8a6e-cardioassist-ai'
$StageHead = 'a32aca29f68e5330344b7cc79e9956acdf446a2a'

Write-Host "PowerShell $($PSVersionTable.PSVersion); OS $([Environment]::OSVersion.VersionString)"
Write-Host "Host: $env:COMPUTERNAME; user: $env:USERNAME"

if (-not (Test-Path -LiteralPath $Target)) {
    New-Item -ItemType Directory -Path $Target | Out-Null
}
if (@(Get-ChildItem -LiteralPath $Target -Force).Count -eq 0) {
    Invoke-Checked -Command git -Arguments @(
        'clone','--single-branch','--branch',$PrototypeBranch,$RepoUrl,$Target)
}
Set-Location $Target

if (-not (Test-Path -LiteralPath .\.git)) { throw 'Target is not a Git repository.' }
$Origin = (Get-CheckedOutput -Command git -Arguments @('remote','get-url','origin'))[0].Trim()
if ($Origin -ne $RepoUrl) { throw "Unexpected origin: $Origin" }
$CurrentBranch = (Get-CheckedOutput -Command git -Arguments @('rev-parse','--abbrev-ref','HEAD'))[0].Trim()
if ($CurrentBranch -ne $PrototypeBranch) { throw "Unexpected branch: $CurrentBranch" }
$LocalBase = (Get-CheckedOutput -Command git -Arguments @('rev-parse','HEAD'))[0].Trim()
if ($LocalBase -ne $ExpectedBase) { throw "Unexpected prototype HEAD: $LocalBase" }
if (@(Get-CheckedOutput -Command git -Arguments @('status','--porcelain')).Count -gt 0) {
    throw 'Dirty prototype clone; refusing to verify.'
}
Write-Host "Verified accepted prototype branch $PrototypeBranch at $LocalBase; it will not be modified."

# Fetch the stage PR head into a separate remote-tracking ref; no checkout/merge of the prototype branch.
Invoke-Checked -Command git -Arguments @(
    'fetch','origin',"refs/heads/$StageBranch`:refs/remotes/stage/$StageBranch")
$ActualStageHead = (Get-CheckedOutput -Command git -Arguments @(
    'rev-parse',"refs/remotes/stage/$StageBranch"))[0].Trim()
if ($ActualStageHead -ne $StageHead) {
    throw "Unexpected stage head: $ActualStageHead (expected $StageHead)"
}
Invoke-Checked -Command git -Arguments @('cat-file','-e',"$StageHead^{commit}")
Invoke-Checked -Command git -Arguments @('merge-base','--is-ancestor',$ExpectedBase,$StageHead)
$Changed = @(Get-CheckedOutput -Command git -Arguments @(
    'diff','--name-only',"$ExpectedBase..$StageHead"))
if ($Changed.Count -ne 11) { throw "Expected 11 changed docs; got $($Changed.Count)" }
if (@($Changed | Where-Object { $_ -notlike 'docs/term1/*.md' }).Count -gt 0) {
    throw 'Non-documentation file found in stage diff.'
}
Write-Host "Verified stage head $StageHead: 11 docs-only files, prototype base is ancestor."

$Worktree = Join-Path $Target '.worktrees\c0-candidate'
if (Test-Path -LiteralPath $Worktree) {
    if (@(Get-ChildItem -LiteralPath $Worktree -Force).Count -gt 0) {
        throw "Worktree path exists with content; refusing to overwrite: $Worktree"
    }
} else {
    New-Item -ItemType Directory -Path $Worktree -Force | Out-Null
}
Invoke-Checked -Command git -Arguments @('worktree','add','--detach',$Worktree,$StageHead)
Set-Location $Worktree
$DetachedHead = (Get-CheckedOutput -Command git -Arguments @('rev-parse','HEAD'))[0].Trim()
if ($DetachedHead -ne $StageHead) { throw "Unexpected detached HEAD: $DetachedHead" }
if (@(Get-CheckedOutput -Command git -Arguments @('status','--porcelain')).Count -gt 0) {
    throw 'Dirty candidate worktree; refusing verification.'
}
Write-Host "Testing detached candidate revision $DetachedHead; prototype branch untouched."

$HostPy = (Get-CheckedOutput -Command python -Arguments @('--version'))[0]
if ($HostPy -notmatch 'Python 3\.(11|12)\.') { throw "Unsupported host Python: $HostPy" }
if (-not (Test-Path -LiteralPath .\.venv\Scripts\python.exe)) {
    Invoke-Checked -Command python -Arguments @('-m','venv','.venv')
}
$PyExe = (Resolve-Path -LiteralPath .\.venv\Scripts\python.exe).Path
$VenvPy = (Get-CheckedOutput -Command $PyExe -Arguments @('--version'))[0]
if ($VenvPy -notmatch 'Python 3\.(11|12)\.') { throw "Unsupported virtualenv Python: $VenvPy" }
if ($VenvPy -notmatch [regex]::Escape($HostPy.Substring(7, 3))) {
    Write-Warning "Host $HostPy and virtualenv $VenvPy differ; recording virtualenv version as authoritative."
}
Invoke-Checked -Command $PyExe -Arguments @('-m','pip','install','--upgrade','pip')
Invoke-Checked -Command $PyExe -Arguments @('-m','pip','install','-r','backend/requirements-dev.txt')
Invoke-Checked -Command $PyExe -Arguments @('-m','pip','install','-r','research/experiments/requirements.txt')
Invoke-Checked -Command $PyExe -Arguments @('-m','pip','install','-r','research/audit/requirements.txt')
Invoke-Checked -Command $PyExe -Arguments @('-m','pip','install','-r','research/uci412/requirements.txt')
Invoke-Checked -Command $PyExe -Arguments @('-m','pip','check')
Write-Host "Virtualenv interpreter: $VenvPy ($PyExe)"

New-Item -ItemType Directory -Force -Path .\var | Out-Null
$Disposable = "c0_stage_$([guid]::NewGuid().ToString('N')).sqlite3"
$Preservation = "c0_legacy_preservation_$([guid]::NewGuid().ToString('N')).sqlite3"
$env:CARDIOASSIST_DATABASE_URL = "sqlite:///./var/$Disposable"
Invoke-Checked -Command $PyExe -Arguments @('-m','alembic','upgrade','head')
Invoke-Checked -Command $PyExe -Arguments @('-m','alembic','current')
Invoke-Checked -Command $PyExe -Arguments @('-m','alembic','check')

$env:CARDIOASSIST_DATABASE_URL = "sqlite:///./var/$Preservation"
Invoke-Checked -Command $PyExe -Arguments @('-m','alembic','upgrade','head')
Invoke-Checked -Command $PyExe -Arguments @('-m','alembic','current')
Invoke-Checked -Command $PyExe -Arguments @('-m','alembic','check')

# Real legacy preservation check: write one observation through the existing route,
# rerun Alembic, and prove the monitoring row survives with the same count.
$Port = 8123
$OutLog = Join-Path $Worktree 'var\c0_service_stdout.log'
$ErrLog = Join-Path $Worktree 'var\c0_service_stderr.log'
$Service = Start-Process -FilePath $PyExe -ArgumentList @(
    '-m','uvicorn','backend.app.main:app','--host','127.0.0.1','--port',"$Port",'--workers','1'
) -PassThru -RedirectStandardOutput $OutLog -RedirectStandardError $ErrLog
try {
    $Ready = $false
    for ($i = 0; $i -lt 40; $i++) {
        if ($Service.HasExited) { throw "Service exited early; see $ErrLog" }
        try {
            $null = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/openapi.json" -TimeoutSec 2
            $Ready = $true
            break
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    if (-not $Ready) { throw "Service did not become ready; see $ErrLog" }
    $Doc = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/openapi.json"
    $Served = @($Doc.paths.PSObject.Properties.Name | Sort-Object)
    $ExpectedPaths = @('/v1/monitoring/observations','/v1/predictions/cad-tabular')
    if (($Served -join '|') -ne ($ExpectedPaths -join '|')) {
        throw "Unexpected served paths: $($Served -join ', ')"
    }
    $LegacyBody = Get-Content -Raw -LiteralPath 'shared/contracts/fixtures/F-04-monitoring-observation-valid.json'
    $LegacyResponse = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:$Port/v1/monitoring/observations" `
        -Headers @{'Idempotency-Key' = 'c0-windows-preservation-001'} `
        -ContentType 'application/json' -Body $LegacyBody
    if ($null -eq $LegacyResponse) { throw 'Legacy observation response was empty.' }
    Write-Host 'Legacy route accepted one synthetic F-04 observation on the preservation DB.'
} finally {
    if (-not $Service.HasExited) { Stop-Process -Id $Service.Id }
}
$PreservationPath = (Resolve-Path -LiteralPath (Join-Path $Worktree "var/$Preservation")).Path
$CountSql = 'import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); print(c.execute("SELECT COUNT(*) FROM monitoring_observation").fetchone()[0])'
$CountAfterWrite = [int](Get-CheckedOutput -Command $PyExe -Arguments @('-c',$CountSql,$PreservationPath))[0]
$env:CARDIOASSIST_DATABASE_URL = "sqlite:///./var/$Preservation"
Invoke-Checked -Command $PyExe -Arguments @('-m','alembic','upgrade','head')
$CountAfterUpgrade = [int](Get-CheckedOutput -Command $PyExe -Arguments @('-c',$CountSql,$PreservationPath))[0]
if ($CountAfterWrite -lt 1 -or $CountAfterWrite -ne $CountAfterUpgrade) {
    throw "Legacy preservation failed: before=$CountAfterWrite after=$CountAfterUpgrade"
}
Write-Host "Legacy preservation OK: $CountAfterUpgrade observation row(s) before and after re-upgrade."

# Test suites run independently; the inherited 3.11 research failure must not abort later checks.
$env:CARDIOASSIST_DATABASE_URL = "sqlite:///./var/$Disposable"
$script:SuiteResults = @()
Invoke-Suite -Name 'contracts+backend' -Arguments @($PyExe,'-m','pytest','tests/contracts','tests/backend','-q','-W','error') -LogFile (Join-Path $Worktree 'var\suite-contracts-backend.log')
Invoke-Suite -Name 'audit' -Arguments @($PyExe,'-m','pytest','tests/audit','-q','-W','error') -LogFile (Join-Path $Worktree 'var\suite-audit.log')
Invoke-Suite -Name 'experiments' -Arguments @($PyExe,'-m','pytest','tests/experiments','-q','-W','error') -LogFile (Join-Path $Worktree 'var\suite-experiments.log')
Invoke-Suite -Name 'uci412-research' -Arguments @($PyExe,'-m','pytest','tests/uci412','-q','-W','error') -LogFile (Join-Path $Worktree 'var\suite-uci412.log')
Invoke-Suite -Name 'source-verification' -Arguments @($PyExe,'scripts/verify_sources.py') -LogFile (Join-Path $Worktree 'var\suite-source-verification.log')
Invoke-Suite -Name 'git-diff-check' -Arguments @('git','diff','--check') -LogFile (Join-Path $Worktree 'var\suite-git-diff-check.log')

$script:SuiteResults | Format-Table -AutoSize
$InheritedAllowed = ($VenvPy -match 'Python 3\.11\.')
$NewFailures = @($script:SuiteResults | Where-Object {
    $_.ExitCode -ne 0 -and $_.Suite -ne 'uci412-research'
})
if (-not $InheritedAllowed) {
    $NewFailures += @($script:SuiteResults | Where-Object {
        $_.Suite -eq 'uci412-research' -and $_.ExitCode -ne 0
    })
}
if ($NewFailures.Count -gt 0) {
    throw "NEW_REGRESSION: $($NewFailures.Suite -join ', '). Inspect the listed logs; do not rerun to obtain a green result."
}
Write-Host 'C0 stage PR verification complete. Inherited research failure handled separately; no destructive cleanup performed.'
```

## 3. Evidence to return

Record PowerShell version, OS build, host and virtualenv Python versions, `$LocalBase`, `$ActualStageHead`, detached candidate HEAD, clean status, pip check output, both Alembic outputs, all six suite exit codes/seconds/logs, the two legacy served paths, the F-04 legacy POST response, and the preservation row counts. All fields are `NOT_RUN` until the owner supplies the transcript. Hosted Linux CI does not substitute.

## 4. Stage-specific additions after acceptance

- **C1:** run delivered auth/invitation/enrollment tests against the accepted C1 revision; smoke only endpoints shipped in that OpenAPI; two concurrent registrations with one code; logout/session invalidation; restart with preservation DB.
- **C2:** profile/provenance/state tests; adapter tests only after A3; fail-closed assertions otherwise; patient projection redaction; lease recovery with restart.
- **C3:** review/follow-up/notification tests; cross-role IDOR negatives; atomic message/notification check; read-status restart.
- **C4:** full E2E with delivered fixtures; exact-head hosted CI links for the final accepted SHA.

No deletion, reset, `git clean`, or database removal command is provided. Leave DBs and logs in `.\var` as evidence.
