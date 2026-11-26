# PowerShell 5.1 verification script for the Term 1 C1 backend surface (20 operations).
# Usage: powershell -ExecutionPolicy Bypass -File scripts/verify_c1_windows.ps1 -ExpectedSha <40-hex>
param([Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{40}$')][string]$ExpectedSha)
$ErrorActionPreference = 'Stop'
function Check-Exit([string]$Step, [int]$Code) {
    Write-Host "$Step (exit $Code)"
    if ($Code -ne 0) { throw "Failed: $Step. Keep the worktree and local outputs for review." }
}
function Assert-Clean {
    $changes = @(git status --porcelain --untracked-files=all)
    Check-Exit 'git status' $LASTEXITCODE
    if ($changes.Count -ne 0) { throw 'Use a clean worktree; do not delete local files.' }
}
function Run-Python {
    & $Python @args
    Check-Exit ("python " + ($args -join ' ')) $LASTEXITCODE
}
function Save-Json([string]$Name, [string[]]$Lines) {
    # Do not pipe model outputs through ConvertTo-Json or PS 5.1 Out-File.
    [IO.File]::WriteAllText((Join-Path $Out $Name), (($Lines -join "`n") + "`n"), [Text.UTF8Encoding]::new($false))
}
Set-Location -LiteralPath (Join-Path $PSScriptRoot '..')
$head = git rev-parse HEAD
Check-Exit 'git rev-parse' $LASTEXITCODE
if ($head -cne $ExpectedSha) { throw 'Unexpected HEAD.' }
Assert-Clean
$Out = Join-Path $env:LOCALAPPDATA ('C1WIN-' + [guid]::NewGuid().ToString('N').Substring(0,12))
New-Item -ItemType Directory -Path $Out -ErrorAction Stop | Out-Null
$Venv = Join-Path $Out 'v'
$Python = Join-Path $Venv 'Scripts\python.exe'
Write-Host "HEAD: $head; retained outputs: $Out"
py -3.12 -m venv $Venv
Check-Exit 'py -3.12 -m venv' $LASTEXITCODE
Run-Python --version
Run-Python -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt
Run-Python -m pip check
Run-Python -m pytest --version
# Verify the committed contract source is byte-identical and machine-readable.
Run-Python scripts/verify_sources.py
# Run the C1 backend suite with warnings-as-errors.
Run-Python -m pytest -W error -q tests/backend/c1/
Run-Python -m pytest -W error -q tests/contracts/
# Determinism: run the C1 keycheck/audit suite twice and compare exit state.
$First = Join-Path $Out 'c1-run-1.json'
$Second = Join-Path $Out 'c1-run-2.json'
Run-Python -m pytest -W error -q --tb=short tests/backend/c1/test_c1_audit_and_keycheck.py > $First
$FirstCode = $LASTEXITCODE
Run-Python -m pytest -W error -q --tb=short tests/backend/c1/test_c1_audit_and_keycheck.py > $Second
$SecondCode = $LASTEXITCODE
if ($FirstCode -ne 0 -or $SecondCode -ne 0) { throw 'C1 audit/keycheck suite did not pass on both runs.' }
if ((Get-FileHash -Algorithm SHA256 $First).Hash -ne (Get-FileHash -Algorithm SHA256 $Second).Hash) {
    throw 'C1 suite output is not byte-deterministic across runs. Preserve both outputs.'
}
Run-Python -m pytest -W error -q -ra --tb=short tests/backend/c1/ > (Join-Path $Out 'c1-full-run.txt')
$FullCode = $LASTEXITCODE
if ($FullCode -ne 0) { throw 'Full C1 backend suite did not pass.' }
git diff --check 310534e1e334ba3be4f308f5a66d88c22b5842e0 HEAD
Check-Exit 'git diff --check base..HEAD' $LASTEXITCODE
Assert-Clean
Write-Host "Completed C1 verification at $head. Record versions, counts, and the retained outputs under $Out."
