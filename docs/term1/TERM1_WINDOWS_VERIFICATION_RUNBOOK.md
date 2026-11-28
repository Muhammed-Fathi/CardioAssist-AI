# CardioAssist-Term1 — C0 Stage PR Windows Verification Runbook

**Status:** `NOT_RUN` until the owner executes this block and supplies the transcript.
**Workspace:** `E:\CardioAssist-Term1-Prototype` (owner-controlled accepted prototype clone).
**Candidate worktree:** unique sibling directory outside the tracked prototype checkout.
**PowerShell:** 5.1 compatible. Python 3.11 or 3.12 supported.
**Reviewed candidate SHA:** `a32aca29f68e5330344b7cc79e9956acdf446a2a` (PR #143 head verified by the independent reviewer). The independent reviewer will supply the final exact candidate SHA after the closing publication; update `$StageHead` before execution if a different SHA is supplied.
**Prototype base:** `bca75b4646dbde26e495201938b7ae01ea7e0d21`.
**Supersedes for new use:** the draft `WINDOWS_LOCAL_VERIFICATION_RUNBOOK_20261125.md` clone-to-default-folder and cleanup workflow; that historical file is preserved unchanged.

## 1. Safety and evidence rules

- Verify the accepted prototype branch; never check out, reset, merge into or write inside it during candidate verification. The candidate is tested in a uniquely named detached worktree outside the tracked clone.
- Clone only into an empty target; reuse only a clean clone with the expected origin and branch.
- No `git reset --hard`, `git clean`, `Remove-Item` of databases, destructive Alembic downgrade, or broad delete. All logs and databases remain as evidence.
- Check `$LASTEXITCODE` for every native command, including read-only Git verification queries. Native stderr is captured as text and must not abort successful commands under PowerShell 5.1.
- Verify the virtualenv interpreter, not merely the host `python`.
- Use unique disposable and preservation databases; use the F-04 fixture's own request body and approved headers, never the whole fixture document, as the HTTP request body.
- Record every nonzero exit code and every `FAILED`/`ERROR` test line independently. Do **not** classify a failure as matching a known baseline; only the independent reviewer may do that after inspecting evidence.
- Do not record the owner's computer name or username.
- Do not claim this block was executed by Arena; status is `NOT_RUN`.

## 2. Complete PowerShell 5.1 C0 candidate block (`NOT_RUN`)

```powershell
# PowerShell 5.1: keep native stderr non-fatal; explicit exit codes are authoritative.
$ErrorActionPreference = 'Continue'
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
    & $Command @Arguments 2>&1 | Out-Null
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
    $failedLines = @(Select-String -Path $LogFile -Pattern '^(FAILED|ERROR) ' -ErrorAction SilentlyContinue |
        ForEach-Object { $_.Line })
    $script:SuiteResults += [pscustomobject]@{
        Suite = $Name
        ExitCode = $code
        Seconds = [math]::Round($watch.Elapsed.TotalSeconds, 1)
        FailingTests = $failedLines
        Detail = $detail
        Log = $LogFile
    }
}

Write-Host "PowerShell $($PSVersionTable.PSVersion); OS $([Environment]::OSVersion.VersionString)"

$Target = 'E:\CardioAssist-Term1-Prototype'
$RepoUrl = 'https://github.com/Muhammed-Fathi/CardioAssist-AI.git'
$PrototypeBranch = 'delivery/term1-prototype'
$ExpectedBase = 'bca75b4646dbde26e495201938b7ae01ea7e0d21'
$StageBranch = 'arena/bdbd8a6e-cardioassist-ai'
$StageHead = 'a32aca29f68e5330344b7cc79e9956acdf446a2a'

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

# Verify the COMMITTED candidate against the exact prototype base, not only the worktree.
Invoke-Checked -Command git -Arguments @(
    'fetch','origin',"refs/heads/$StageBranch`:refs/remotes/stage/$StageBranch")
$ActualStageHead = (Get-CheckedOutput -Command git -Arguments @(
    'rev-parse',"refs/remotes/stage/$StageBranch"))[0].Trim()
if ($ActualStageHead -ne $StageHead) {
    throw "Unexpected stage head: $ActualStageHead (expected $StageHead)"
}
Invoke-Checked -Command git -Arguments @('cat-file','-e',"$StageHead^{commit}")
Invoke-Checked -Command git -Arguments @('merge-base','--is-ancestor',$ExpectedBase,$StageHead)
$NameStatus = @(Get-CheckedOutput -Command git -Arguments @(
    'diff','--name-status',"$ExpectedBase..$StageHead"))
if ($NameStatus.Count -ne 11) {
    throw "Expected 11 committed changed files; got $($NameStatus.Count)"
}
if (@($NameStatus | Where-Object { $_ -notmatch '^A\s+docs/term1/.*\.md$' }).Count -gt 0) {
    throw 'Committed candidate diff is not exactly 11 added docs/term1 Markdown files.'
}
Invoke-Checked -Command git -Arguments @('diff','--check',"$ExpectedBase..$StageHead")
$CommittedStat = @(Get-CheckedOutput -Command git -Arguments @(
    'diff','--stat',"$ExpectedBase..$StageHead"))
Write-Host ("Committed candidate vs exact base: " + ($CommittedStat[-1]).Trim())

# Unique detached worktree OUTSIDE the tracked prototype checkout.
$Worktree = Join-Path 'E:\' ("CardioAssist-C0-Candidate-" + [guid]::NewGuid().ToString('N').Substring(0,12))
if (Test-Path -LiteralPath $Worktree) {
    if (@(Get-ChildItem -LiteralPath $Worktree -Force).Count -gt 0) {
        throw "Worktree path exists with content; refusing to overwrite: $Worktree"
    }
}
Invoke-Checked -Command git -Arguments @('worktree','add','--detach',$Worktree,$StageHead)
Set-Location $Worktree
$DetachedHead = (Get-CheckedOutput -Command git -Arguments @('rev-parse','HEAD'))[0].Trim()
if ($DetachedHead -ne $StageHead) { throw "Unexpected detached HEAD: $DetachedHead" }
if (@(Get-CheckedOutput -Command git -Arguments @('status','--porcelain')).Count -gt 0) {
    throw 'Dirty candidate worktree; refusing verification.'
}
Write-Host "Candidate worktree: $Worktree at $DetachedHead; prototype clone untouched."

$HostPy = (Get-CheckedOutput -Command python -Arguments @('--version'))[0]
if ($HostPy -notmatch 'Python 3\.(11|12)\.') { throw "Unsupported host Python: $HostPy" }
if (-not (Test-Path -LiteralPath .\.venv\Scripts\python.exe)) {
    Invoke-Checked -Command python -Arguments @('-m','venv','.venv')
}
$PyExe = (Resolve-Path -LiteralPath .\.venv\Scripts\python.exe).Path
$VenvPy = (Get-CheckedOutput -Command $PyExe -Arguments @('--version'))[0]
if ($VenvPy -notmatch 'Python 3\.(11|12)\.') { throw "Unsupported virtualenv Python: $VenvPy" }
Write-Host "Virtualenv interpreter: $VenvPy ($PyExe)"
Invoke-Checked -Command $PyExe -Arguments @('-m','pip','install','--upgrade','pip')
Invoke-Checked -Command $PyExe -Arguments @('-m','pip','install','-r','backend/requirements-dev.txt')
Invoke-Checked -Command $PyExe -Arguments @('-m','pip','install','-r','research/experiments/requirements.txt')
Invoke-Checked -Command $PyExe -Arguments @('-m','pip','install','-r','research/audit/requirements.txt')
Invoke-Checked -Command $PyExe -Arguments @('-m','pip','install','-r','research/uci412/requirements.txt')
Invoke-Checked -Command $PyExe -Arguments @('-m','pip','check')

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

# Service process, port and legacy preservation check with the real F-04 request body.
$Port = 8123
$ExistingListener = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
if ($ExistingListener.Count -gt 0) { throw "Port $Port is already in use." }
$OutLog = Join-Path $Worktree 'var\c0_service_stdout.log'
$ErrLog = Join-Path $Worktree 'var\c0_service_stderr.log'
$Service = Start-Process -FilePath $PyExe -ArgumentList @(
    '-m','uvicorn','backend.app.main:app','--host','127.0.0.1','--port',"$Port",'--workers','1'
) -PassThru -RedirectStandardOutput $OutLog -RedirectStandardError $ErrLog
try {
    if ($Service.HasExited) { throw "Service exited early; see $ErrLog" }
    $ProcInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $($Service.Id)"
    if ($ProcInfo.CommandLine -notmatch 'backend\.app\.main:app' -or
        $ProcInfo.CommandLine -notmatch "--port\s+$Port") {
        throw "Started process $($Service.Id) is not the expected uvicorn command."
    }
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
    $OwnedListener = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Where-Object { $_.OwningProcess -eq $Service.Id })
    if ($OwnedListener.Count -eq 0) {
        throw "Port $Port is not owned by the started service process $($Service.Id)."
    }
    $Doc = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/openapi.json"
    $Served = @($Doc.paths.PSObject.Properties.Name | Sort-Object)
    $ExpectedPaths = @('/v1/monitoring/observations','/v1/predictions/cad-tabular')
    if (($Served -join '|') -ne ($ExpectedPaths -join '|')) {
        throw "Unexpected served paths: $($Served -join ', ')"
    }

    # Parse the fixture and send ONLY steps[0].request.body with its approved headers.
    $Fixture = Get-Content -Raw -LiteralPath 'shared/contracts/fixtures/F-04-monitoring-observation-valid.json' |
        ConvertFrom-Json
    $Step = $Fixture.steps[0]
    if ($Fixture.endpoint -ne 'POST /v1/monitoring/observations') {
        throw "Unexpected fixture endpoint: $($Fixture.endpoint)"
    }
    $LegacyBody = $Step.request.body | ConvertTo-Json -Depth 32 -Compress
    $LegacyHeaders = @{}
    foreach ($header in $Step.request.headers.PSObject.Properties) {
        $LegacyHeaders[$header.Name] = [string]$header.Value
    }
    if (-not $LegacyHeaders.ContainsKey('Idempotency-Key')) {
        throw 'F-04 approved headers do not contain Idempotency-Key.'
    }
    $RawResponse = Invoke-WebRequest -UseBasicParsing -Method Post `
        -Uri "http://127.0.0.1:$Port/v1/monitoring/observations" `
        -Headers $LegacyHeaders -ContentType 'application/json' -Body $LegacyBody
    if ($RawResponse.StatusCode -ne [int]$Step.assertions.http_status) {
        throw "Unexpected HTTP status: $($RawResponse.StatusCode)"
    }
    $LegacyResponse = $RawResponse.Content | ConvertFrom-Json
    if ($LegacyResponse.accepted -ne $true -or $LegacyResponse.idempotent_replay -ne $false) {
        throw 'Legacy response is not a fresh accepted observation.'
    }
    if ([string]$LegacyResponse.request_id -ne [string]$Step.request.body.request_id -or
        [string]$LegacyResponse.observation_id -ne [string]$Step.expected.body.observation_id -or
        [int]$LegacyResponse.recorded_metric_count -ne 3) {
        throw 'Legacy response does not match the F-04 approved response.'
    }
    Write-Host "Legacy HTTP OK: status $($RawResponse.StatusCode), observation_id $($LegacyResponse.observation_id)."
} finally {
    if (-not $Service.HasExited) { Stop-Process -Id $Service.Id }
}

# Persisted observation, metric and audit verification on the preservation DB.
$PreservationPath = (Resolve-Path -LiteralPath (Join-Path $Worktree "var/$Preservation")).Path
$VerifyDbSql = @'
import sqlite3, sys
db, obs_id, req_id = sys.argv[1], sys.argv[2], sys.argv[3]
conn = sqlite3.connect(db)
rows = conn.execute(
    "SELECT record_id, observation_id, request_id FROM monitoring_observation WHERE observation_id=? AND request_id=?",
    (obs_id, req_id)).fetchall()
if len(rows) != 1:
    raise SystemExit("expected exactly one persisted observation, got %d" % len(rows))
rid = rows[0][0]
metrics = conn.execute(
    "SELECT metric_id, value_json, unit FROM monitoring_metric WHERE observation_record_id=? ORDER BY ordinal",
    (rid,)).fetchall()
audits = conn.execute(
    "SELECT request_id, event_type, path FROM audit_event WHERE observation_record_id=?",
    (rid,)).fetchall()
print("observation_rows=1 record_id=%s metric_rows=%d audit_rows=%d" % (rid, len(metrics), len(audits)))
if len(metrics) != 3 or len(audits) != 1 or audits[0][0] != req_id:
    raise SystemExit("persisted metric/audit verification failed")
'@
$Persisted = (Get-CheckedOutput -Command $PyExe -Arguments @(
    '-c',$VerifyDbSql,$PreservationPath,[string]$LegacyResponse.observation_id,[string]$LegacyResponse.request_id))[0]
if ($Persisted -notmatch 'metric_rows=3 audit_rows=1') {
    throw "Unexpected persisted state: $Persisted"
}
$env:CARDIOASSIST_DATABASE_URL = "sqlite:///./var/$Preservation"
Invoke-Checked -Command $PyExe -Arguments @('-m','alembic','upgrade','head')
$PersistedAfter = (Get-CheckedOutput -Command $PyExe -Arguments @(
    '-c',$VerifyDbSql,$PreservationPath,[string]$LegacyResponse.observation_id,[string]$LegacyResponse.request_id))[0]
if ($Persisted -ne $PersistedAfter) {
    throw "Legacy preservation failed: before=$Persisted after=$PersistedAfter"
}
Write-Host "Legacy preservation OK: $PersistedAfter"

# Independent suite records; no automatic inherited-failure classification.
$env:CARDIOASSIST_DATABASE_URL = "sqlite:///./var/$Disposable"
$script:SuiteResults = @()
Invoke-Suite -Name 'contracts+backend' -Arguments @($PyExe,'-m','pytest','tests/contracts','tests/backend','-q','-W','error') -LogFile (Join-Path $Worktree 'var\suite-contracts-backend.log')
Invoke-Suite -Name 'audit' -Arguments @($PyExe,'-m','pytest','tests/audit','-q','-W','error') -LogFile (Join-Path $Worktree 'var\suite-audit.log')
Invoke-Suite -Name 'experiments' -Arguments @($PyExe,'-m','pytest','tests/experiments','-q','-W','error') -LogFile (Join-Path $Worktree 'var\suite-experiments.log')
Invoke-Suite -Name 'uci412-research' -Arguments @($PyExe,'-m','pytest','tests/uci412','-q','-W','error') -LogFile (Join-Path $Worktree 'var\suite-uci412.log')
Invoke-Suite -Name 'source-verification' -Arguments @($PyExe,'scripts/verify_sources.py') -LogFile (Join-Path $Worktree 'var\suite-source-verification.log')
Invoke-Suite -Name 'git-diff-check' -Arguments @('git','diff','--check') -LogFile (Join-Path $Worktree 'var\suite-git-diff-check.log')

$script:SuiteResults | Select-Object Suite,ExitCode,Seconds,Log | Format-Table -AutoSize
foreach ($result in $script:SuiteResults) {
    if ($result.ExitCode -ne 0) {
        Write-Host "NONZERO: $($result.Suite) exit=$($result.ExitCode) log=$($result.Log)"
        foreach ($failed in $result.FailingTests) { Write-Host "  $failed" }
    }
}
Write-Host 'All nonzero exits and failing tests recorded. Only the independent reviewer may classify any failure as matching the known baseline.'
Write-Host 'No destructive cleanup performed; logs, worktree and databases remain for evidence.'
```

## 3. Evidence to return

Record PowerShell version, OS build, host and virtualenv Python versions, `$LocalBase`, `$ActualStageHead`, committed diff check/stat, detached worktree path and HEAD, clean status, port ownership/process verification, pip check output, both Alembic outputs, F-04 HTTP status and response fields, persisted observation/metric/audit verification, exact served paths, and every suite exit code, log path and `FAILED`/`ERROR` line. Do not classify failures in the transcript. All fields are `NOT_RUN` until supplied by the owner; hosted Linux CI does not substitute.

## 4. Stage-specific additions after acceptance

- **C1:** run delivered auth/invitation/enrollment tests against the accepted C1 revision; smoke only endpoints shipped in that OpenAPI; two concurrent registrations with one code; logout/session invalidation; restart with preservation DB.
- **C2:** profile/provenance/state tests; adapter tests only after A3; fail-closed assertions otherwise; patient projection redaction; lease recovery with restart.
- **C3:** review/follow-up/notification tests; cross-role IDOR negatives; atomic message/notification check; read-status restart.
- **C4:** full E2E with delivered fixtures; exact-head hosted CI links for the final accepted SHA.

No deletion, reset, `git clean`, or database removal command is provided. The only process stopped is the one started by this script.
