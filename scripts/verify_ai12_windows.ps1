# Windows PowerShell 5.1. Run in the clean DETACHED worktree, NOT the original checkout.
param([Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{40}$')][string]$ExpectedSha)
$ErrorActionPreference = 'Stop'
function Check-Exit([string]$Step, [int]$Code) {
    Write-Host "$Step (exit $Code)"
    if ($Code -ne 0) { throw "Failed: $Step. Keep the worktree and local outputs for review." }
}
function Assert-Clean {
    $changes = @(git status --porcelain --untracked-files=all)
    Check-Exit 'git status' $LASTEXITCODE
    if ($changes.Count -ne 0) { throw 'Use a new clean worktree; do not delete local files.' }
}
function Run-Python {
    & $Python @args
    Check-Exit ("python " + ($args -join ' ')) $LASTEXITCODE
}
function Save-Json([string]$Name, [string[]]$Lines) {
    # Do not pipe model outputs through ConvertTo-Json or PS 5.1 Out-File.
    [IO.File]::WriteAllText((Join-Path $Out $Name), (($Lines -join "`n") + "`n"), [Text.UTF8Encoding]::new($false))
}
if ($env:OS -ne 'Windows_NT') { throw 'This acceptance procedure requires native Windows and NTFS.' }
Set-Location -LiteralPath (Join-Path $PSScriptRoot '..')
$head = git rev-parse HEAD
Check-Exit 'git rev-parse' $LASTEXITCODE
if ($head -cne $ExpectedSha) { throw 'Unexpected HEAD.' }
git symbolic-ref -q HEAD
if ($LASTEXITCODE -ne 1) { throw 'Expected detached HEAD, not a development branch.' }
Assert-Clean
$Out = Join-Path $env:LOCALAPPDATA ('CAI12-' + [guid]::NewGuid().ToString('N').Substring(0,12))
New-Item -ItemType Directory -Path $Out -ErrorAction Stop | Out-Null
$Venv = Join-Path $Out 'v'
$Python = Join-Path $Venv 'Scripts\python.exe'
Write-Host "HEAD: $head; retained external environment and synthetic evidence: $Out"
py -3.12 -m venv $Venv
Check-Exit 'py -3.12 -m venv' $LASTEXITCODE
Run-Python --version
Run-Python -m pip install -r research/uci412/requirements.txt -r backend/requirements-dev.txt
Run-Python -m pip check
Run-Python -m pytest --version
Run-Python scripts/verify_sources.py
Run-Python scripts/validate_ai_windows_compat.py

$legacy = @(Run-Python -W error -m ai.research_demo --format json)
Save-Json 'ai11.json' $legacy
$old = ($legacy -join "`n") | ConvertFrom-Json
if ($old.status -ne 'PASSED' -or $old.summary.stages_succeeded -ne 8) { throw 'Legacy demo incomplete.' }
Write-Host "8/8 AI-11.1 demo digest: $($old.deterministic_sha256)"
$Pack = Join-Path $Out 'windows.v1.json'
$Repeat = Join-Path $Out 'repeat.v1.json'
Run-Python -W error -m ai.research_evidence --output $Pack
Run-Python -W error -m ai.research_evidence --output $Repeat
if ((Get-FileHash -Algorithm SHA256 $Pack).Hash -ne (Get-FileHash -Algorithm SHA256 $Repeat).Hash) {
    throw 'Same-machine pack bytes differ. Preserve both files.'
}
# Keep BOTH comparisons. A legacy JSON alone cannot explain a different stage-8 preimage.
$legacyDiff = @(& $Python -W error -m ai.research_evidence --compare (Join-Path $Out 'ai11.json'))
$legacyCode = $LASTEXITCODE
Save-Json 'legacy-comparison.json' $legacyDiff
$diff = @(& $Python -W error -m ai.research_evidence --compare $Pack)
$diffCode = $LASTEXITCODE
Save-Json 'field-comparison.json' $diff
Write-Host "Legacy comparison exit $legacyCode; full comparison exit $diffCode (inspect field-comparison.json)."

Run-Python -m pytest -W error -q tests/experiments/test_research_evidence.py tests/contracts/test_research_evidence_schema.py tests/experiments/test_research_facade.py tests/backend/test_inference_provider.py
# One monolithic invocation. An interrupted run is NOT a full pass. This can take over an hour.
Run-Python -m pytest -W error -q -ra --tb=short
git diff --check 83f51f67792d55634c3eca4ff150bae732f75e2b HEAD
Check-Exit 'git diff --check base..HEAD' $LASTEXITCODE
Assert-Clean
if ($legacyCode -ne 0) {
    if ($legacyCode -ne 1 -or (($legacyDiff -join "`n") | ConvertFrom-Json).fixture_behavior -ne 'INDETERMINATE') {
        throw 'Legacy comparison failed or behavior differs. Review both retained reports.'
    }
    Write-Host 'Legacy response hash differs; inspect the full-precision paired comparison, not just the digest.'
}
Check-Exit 'full synthetic fixture comparison (not artifact equivalence)' $diffCode
Write-Host "Completed synthetic engineering verification at $head. Record versions, counts, skips and differences. No clinical or real-data authority."
