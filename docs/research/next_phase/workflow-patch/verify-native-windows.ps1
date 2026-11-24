<#
.SYNOPSIS
    RH-04 V2 native Windows verification - Lane A, Lane B, V1 and targeted
    regression. PowerShell 5.1 compatible.

.DESCRIPTION
    Executes the required native Windows evidence for one frozen delivery SHA.
    Reuses the repository's own requirement files, so the environment is the one
    the project declares rather than an ad-hoc set.

    EVIDENCE INTEGRITY
      * Every run writes into a SHA-bound, per-execution evidence directory:
        .rh04-evidence-win\<short-sha>\<UTC timestamp>\. A previous run's JSON can
        never be read back as this run's result, because this run has its own
        directory and its own file names.
      * Every Python process has its exit code checked immediately. A non-zero
        exit is a failure, and the file it was supposed to write is explicitly
        removed, so nothing downstream can credit stale output.
      * Lane B uses the unified verification path
        (research.intake.rh04_v2_lane_a_report, lane-b), which replays through
        rh04_v2_portable_archive and reports the OBSERVED digest and verdict.
      * The targeted regression tests from the acceptance harness are run and
        recorded.

    IT DOES NOT change any artifact, tolerance, fixture, expectation, case count
    or frozen V1 file. If a value disagrees with the pinned value it reports RED
    and exits non-zero; it never regenerates an expectation to match an
    observation.

.PARAMETER ExpectedHead
    The frozen delivery SHA this run is evidence for.

.PARAMETER ReuseVenv
    Reuse an existing dedicated environment instead of stopping.

.PARAMETER SkipInstall
    Skip environment creation and dependency installation.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\verify-native-windows.ps1 `
        -ExpectedHead <candidate-sha>
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ExpectedHead,
    [string]$VenvPath = ".venv-rh04-win",
    [switch]$ReuseVenv,
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

$script:Failures = New-Object System.Collections.Generic.List[string]
$script:Results  = New-Object System.Collections.Generic.List[object]

function Write-Section([string]$Title) {
    Write-Host ""
    Write-Host ("=" * 78) -ForegroundColor Cyan
    Write-Host $Title -ForegroundColor Cyan
    Write-Host ("=" * 78) -ForegroundColor Cyan
}

function Add-Result([string]$Check, [string]$Status, [string]$Detail) {
    $script:Results.Add([pscustomobject]@{ Check = $Check; Status = $Status; Detail = $Detail })
    if ($Status -eq "PASS") {
        Write-Host ("  [PASS] {0}: {1}" -f $Check, $Detail) -ForegroundColor Green
    }
    elseif ($Status -eq "FAIL") {
        Write-Host ("  [FAIL] {0}: {1}" -f $Check, $Detail) -ForegroundColor Red
        $script:Failures.Add(("{0} - {1}" -f $Check, $Detail))
    }
    else {
        Write-Host ("  [{0}] {1}: {2}" -f $Status, $Check, $Detail) -ForegroundColor Yellow
    }
}

# Run a Python invocation and record its exit code immediately. On failure the
# declared output file is deleted, so a stale file from an earlier run cannot be
# mistaken for this run's result.
function Invoke-PythonStep {
    param(
        [string]$Name,
        [string[]]$Arguments,
        [string]$OutputPath
    )
    Write-Host ("  running: python {0}" -f ($Arguments -join " "))
    & python @Arguments
    $code = $LASTEXITCODE
    if ($code -ne 0) {
        if ($OutputPath -and (Test-Path $OutputPath)) {
            Remove-Item -Path $OutputPath -Force -ErrorAction SilentlyContinue
        }
        Add-Result $Name "FAIL" ("python exited {0}; its output is discarded" -f $code)
        return $false
    }
    if ($OutputPath -and -not (Test-Path $OutputPath)) {
        Add-Result $Name "FAIL" ("python exited 0 but wrote no {0}" -f $OutputPath)
        return $false
    }
    Add-Result $Name "PASS" "exit 0"
    return $true
}

# --------------------------------------------------------------------------- #
# 1. Repository identity - stop immediately on a wrong SHA or dirty tree       #
# --------------------------------------------------------------------------- #
Write-Section "1. Repository identity"

if (-not (Test-Path ".git")) {
    Write-Host "Not a git checkout. Run this from the repository root." -ForegroundColor Red
    exit 2
}

$head = (& git rev-parse HEAD 2>$null)
if ($LASTEXITCODE -ne 0) {
    Write-Host "git rev-parse HEAD failed." -ForegroundColor Red
    exit 2
}
$head = $head.Trim()

Write-Host ("  checkout HEAD : {0}" -f $head)
Write-Host ("  expected HEAD : {0}" -f $ExpectedHead)

if ($head -ne $ExpectedHead) {
    Write-Host ""
    Write-Host ("  STOP: checkout is {0}, expected {1}." -f $head, $ExpectedHead) -ForegroundColor Red
    Write-Host "  No evidence can be produced for the frozen SHA from this tree." -ForegroundColor Red
    Write-Host "  Nothing else was executed." -ForegroundColor Red
    exit 2
}
Add-Result "checkout HEAD" "PASS" $head

$dirty = @(& git status --porcelain)
if ($dirty.Count -eq 0) {
    Add-Result "working tree clean" "PASS" "no uncommitted or untracked changes"
}
else {
    Write-Host $dirty
    Write-Host ""
    Write-Host "  STOP: the tree is dirty. Evidence would not correspond to a commit." -ForegroundColor Red
    Write-Host "  Nothing else was executed." -ForegroundColor Red
    exit 2
}

git rev-parse --verify refs/remotes/origin/main 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  base ref absent; fetching origin/main" -ForegroundColor Yellow
    git fetch --no-tags origin "+refs/heads/main:refs/remotes/origin/main" | Out-Null
}
$baseRef = (& git rev-parse refs/remotes/origin/main 2>$null)
if ($LASTEXITCODE -eq 0 -and $baseRef) {
    $baseRef = $baseRef.Trim()
    Add-Result "base reference" "PASS" $baseRef
}
else {
    Add-Result "base reference" "FAIL" "origin/main unavailable; the frozen-surface check cannot run and must not skip"
    Write-Host "  STOP: no trusted base reference." -ForegroundColor Red
    exit 2
}

Write-Host ("  git version  : {0}" -f (git --version))
Write-Host ("  OS           : {0}" -f ([System.Environment]::OSVersion.VersionString))
Write-Host ("  architecture : {0}" -f ([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture))

# --------------------------------------------------------------------------- #
# 2. Fresh, SHA-bound evidence directory                                      #
# --------------------------------------------------------------------------- #
Write-Section "2. Evidence directory"

$shortSha = $head.Substring(0, 12)
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$evidenceDir = Join-Path (Join-Path ".rh04-evidence-win" $shortSha) $stamp

# A fresh directory per execution. Nothing is ever reused, so no file in it can
# predate this run.
New-Item -ItemType Directory -Path $evidenceDir -Force | Out-Null
$evidenceRoot = (Resolve-Path $evidenceDir).Path
Add-Result "evidence directory" "PASS" ("fresh for this run: {0}" -f $evidenceRoot)

# Sanity: a brand-new directory must be empty.
$preexisting = @(Get-ChildItem -Path $evidenceRoot -Force)
if ($preexisting.Count -eq 0) {
    Add-Result "evidence directory empty at start" "PASS" "no file can be mistaken for this run's output"
}
else {
    Add-Result "evidence directory empty at start" "FAIL" ("{0} files were already present" -f $preexisting.Count)
    exit 2
}

$laneBPath = Join-Path $evidenceRoot "lane-b.json"
$laneAPath = Join-Path $evidenceRoot "lane-a.json"

# --------------------------------------------------------------------------- #
# 3. Environment - dedicated directory only                                   #
# --------------------------------------------------------------------------- #
Write-Section "3. Python environment"

if (-not $SkipInstall) {
    if (Test-Path $VenvPath) {
        if ($ReuseVenv) {
            Write-Host ("  reusing existing environment {0} (-ReuseVenv)" -f $VenvPath)
        }
        else {
            Add-Result "venv directory" "FAIL" ("{0} already exists; pass -ReuseVenv to reuse it, or remove it yourself" -f $VenvPath)
            Write-Host ""
            Write-Host "  STOP: refusing to delete a directory recursively. This script only" -ForegroundColor Red
            Write-Host "  creates a dedicated environment and will not remove one." -ForegroundColor Red
            exit 2
        }
    }
    else {
        Write-Host ("  creating {0}" -f $VenvPath)
        py -3.11 -m venv $VenvPath
        if ($LASTEXITCODE -ne 0) {
            Add-Result "venv creation" "FAIL" "py -3.11 -m venv failed; Python 3.11 is required"
            exit 2
        }
    }
}

$activate = Join-Path $VenvPath "Scripts\Activate.ps1"
if (-not (Test-Path $activate)) {
    Add-Result "venv activation" "FAIL" ("{0} not found" -f $activate)
    exit 2
}
. $activate

# Verify the ACTUAL interpreter, not the one that was requested.
$interpreter = (& python -c "import sys;print(sys.version.split()[0])").Trim()
$interpreterPath = (& python -c "import sys;print(sys.executable)").Trim()
Write-Host ("  interpreter : {0}" -f $interpreterPath)
if ($interpreter -like "3.11.*") {
    Add-Result "interpreter" "PASS" ("Python {0}" -f $interpreter)
}
else {
    Add-Result "interpreter" "FAIL" ("Python {0}, expected 3.11.x" -f $interpreter)
    exit 2
}

if (-not $SkipInstall) {
    Write-Host "  installing pinned dependencies from the repository's own files"
    python -m pip install --upgrade pip --quiet
    python -m pip install `
        -r research/experiments/requirements.txt `
        -r research/audit/requirements.txt `
        -r research/uci412/requirements.txt `
        -r tests/contracts/requirements.txt --quiet
    if ($LASTEXITCODE -ne 0) {
        Add-Result "dependency install" "FAIL" "pip install of the pinned requirements failed"
        exit 2
    }
    python -m pip install -r research/experiments/requirements-oracle.txt --quiet
    if ($LASTEXITCODE -ne 0) {
        Add-Result "oracle install" "FAIL" "requirements-oracle.txt failed to install"
        exit 2
    }
    Add-Result "oracle install" "PASS" "research/experiments/requirements-oracle.txt"
}

python -m pip check | Out-Host
if ($LASTEXITCODE -eq 0) {
    Add-Result "pip check" "PASS" "no broken requirements"
}
else {
    Add-Result "pip check" "FAIL" "broken requirements reported"
}

# --------------------------------------------------------------------------- #
# 4. Resident numerical libraries (full set, not a collapsed value)           #
# --------------------------------------------------------------------------- #
Write-Section "4. Resident numerical libraries"

$residentPath = Join-Path $evidenceRoot "resident.json"
$residentScript = @'
import sys
sys.path.insert(0, ".")
import json, pathlib
from research.intake import rh04_v2_lane_a_report as report

# Load and exercise NumPy's and SciPy's separate OpenBLAS builds, then read every
# resident entry. A single collapsed "architecture" would be wrong here: NumPy and
# SciPy can resolve different architectures at the same time.
report._warm_numerics()
identity = report.resident_libraries()
classes = report.dispatch_classes_of(identity)
out = {"identity": identity, "classes": classes}
pathlib.Path(sys.argv[1]).write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")
print(json.dumps(classes, indent=2, sort_keys=True))
'@
$residentScriptPath = Join-Path $evidenceRoot "_resident.py"
Set-Content -Path $residentScriptPath -Value $residentScript -Encoding ASCII
if (Invoke-PythonStep -Name "resident libraries" -Arguments @($residentScriptPath, $residentPath) -OutputPath $residentPath) {
    $resident = Get-Content -Path $residentPath -Raw | ConvertFrom-Json
    $archList = ($resident.classes.blas_architectures -join ", ")
    Add-Result "resident dispatch classes" "PASS" ("{0} (mixed: {1})" -f $archList, $resident.classes.mixed)
    if ($resident.identity.libraries.Count -lt 1) {
        Add-Result "resident library count" "FAIL" "no libraries reported; an empty list is not evidence"
    }
}

# --------------------------------------------------------------------------- #
# 5. V1 scoped verification (mandatory)                                       #
# --------------------------------------------------------------------------- #
Write-Section "5. V1 scoped verification (mandatory)"

python -m pytest tests/experiments/test_offline_fixture_pack.py `
                 tests/experiments/test_research_facade.py `
                 tests/contracts -q -W error
if ($LASTEXITCODE -eq 0) {
    Add-Result "V1 scoped suite" "PASS" "exit 0"
}
else {
    Add-Result "V1 scoped suite" "FAIL" ("exit {0}; V1 is the mandatory lane and a failure here is not suppressible" -f $LASTEXITCODE)
}

# --------------------------------------------------------------------------- #
# 6. Lane B - unified verification path, observed digest and verdict          #
# --------------------------------------------------------------------------- #
Write-Section "6. Lane B exact reference replay (mandatory)"

$expectedDigest = "891d9e3b2a332c6efc251d97fee25ed46a627ed25b2a089594057b4c9896cdc8"

# The unified entry point. It admits the archives, replays all 29 registered cases
# through the facade and records the observed digest -- inside the process that did
# the work, with its own resident library identity.
$laneBRunner = @'
import sys
sys.path.insert(0, ".")
import json, pathlib
from research.intake import rh04_v2_lane_a_report as report

document = report.produce_lane_b(sys.argv[1], "research/intake/fixtures/rh04_v2_portable")
pathlib.Path(sys.argv[2]).write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")
print(json.dumps({
    "observed_digest": document["observed_digest"],
    "verdict": document["verdict"],
    "n_cases": document["n_cases"],
    "resident_blas": document["resident_dispatch"]["blas_architectures"],
}, indent=2, sort_keys=True))
sys.exit(0 if document["verdict"] == "ACCEPTED" else 1)
'@
$laneBScriptPath = Join-Path $evidenceRoot "_lane_b.py"
Set-Content -Path $laneBScriptPath -Value $laneBRunner -Encoding ASCII

# "host" leaves dispatch to the machine, which is what native evidence should record.
$laneBOk = Invoke-PythonStep -Name "Lane B replay" -Arguments @($laneBScriptPath, "host", $laneBPath) -OutputPath $laneBPath

if ($laneBOk -and (Test-Path $laneBPath)) {
    $laneB = Get-Content -Path $laneBPath -Raw | ConvertFrom-Json
    if ($laneB.observed_digest -eq $expectedDigest) {
        Add-Result "Lane B observed digest" "PASS" $laneB.observed_digest
    }
    else {
        Add-Result "Lane B observed digest" "FAIL" ("observed {0}, expected {1}; the expectation is NOT regenerated to match" -f $laneB.observed_digest, $expectedDigest)
    }
    if ($laneB.reference_digest -eq $expectedDigest) {
        Add-Result "Lane B pinned reference" "PASS" $laneB.reference_digest
    }
    else {
        Add-Result "Lane B pinned reference" "FAIL" ("pinned reference is {0}" -f $laneB.reference_digest)
    }
    if ($laneB.verdict -eq "ACCEPTED") {
        Add-Result "Lane B verdict" "PASS" "ACCEPTED"
    }
    else {
        Add-Result "Lane B verdict" "FAIL" ("verdict is {0}" -f $laneB.verdict)
    }
    if ($laneB.n_cases -eq 29) {
        Add-Result "Lane B case count" "PASS" "29 registered cases replayed"
    }
    else {
        Add-Result "Lane B case count" "FAIL" ("{0} cases replayed, expected 29" -f $laneB.n_cases)
    }
    $laneBArch = ($laneB.resident_dispatch.blas_architectures -join ", ")
    Add-Result "Lane B resident dispatch" "PASS" ("{0} (read inside the replay process)" -f $laneBArch)
}
else {
    Add-Result "Lane B evidence" "FAIL" "no Lane B document was produced by this run"
}

# --------------------------------------------------------------------------- #
# 7. Lane A - convergence and regeneration identity                           #
# --------------------------------------------------------------------------- #
Write-Section "7. Lane A regeneration evidence"

$laneARunner = @'
import sys
sys.path.insert(0, ".")
import json, pathlib
from research.intake import rh04_v2_lane_a_report as report

document = report.produce_lane_a("host")
pathlib.Path(sys.argv[1]).write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")
summary = {
    route: {
        "any_failure": value["any_failure"],
        "logistic_regression": value["components"]["logistic_regression"]["n_observations"],
        "calibration": value["components"]["oof_calibration_optimizer"]["n_observations"],
        "model_identity": value["regeneration"]["model_identity_sha256"],
        "calibration_identity": value["regeneration"]["calibration_identity_sha256"],
        "replay_identity": value["regeneration"]["replay_identity_sha256"],
    }
    for route, value in document["routes"].items()
}
print(json.dumps(summary, indent=2, sort_keys=True))
sys.exit(0 if not document["any_failure"] else 1)
'@
$laneAScriptPath = Join-Path $evidenceRoot "_lane_a.py"
Set-Content -Path $laneAScriptPath -Value $laneARunner -Encoding ASCII

if (Invoke-PythonStep -Name "Lane A evidence" -Arguments @($laneAScriptPath, $laneAPath) -OutputPath $laneAPath) {
    $laneA = Get-Content -Path $laneAPath -Raw | ConvertFrom-Json
    foreach ($routeId in @("da_a1_basic_clinical_v1", "da_a2_resting_v1")) {
        $route = $laneA.routes.$routeId
        if ($null -eq $route) {
            Add-Result ("Lane A {0}" -f $routeId) "FAIL" "no evidence produced for this route"
            continue
        }
        $lr = $route.components.logistic_regression.n_observations
        $cal = $route.components.oof_calibration_optimizer.n_observations
        if ($lr -gt 0 -and $cal -gt 0) {
            Add-Result ("Lane A {0} observation" -f $routeId) "PASS" ("{0} model fits and {1} calibration optimizations" -f $lr, $cal)
        }
        else {
            Add-Result ("Lane A {0} observation" -f $routeId) "FAIL" ("model fits {0}, calibration {1}; both components are required" -f $lr, $cal)
        }
        if ($route.any_failure -eq $false) {
            Add-Result ("Lane A {0} classification" -f $routeId) "PASS" "no training failure, missing evidence or invalid output"
        }
        else {
            Add-Result ("Lane A {0} classification" -f $routeId) "FAIL" "a fit failed, or its evidence is missing or invalid"
        }
        Add-Result ("Lane A {0} regeneration identity" -f $routeId) "PASS" ("family={0}, calibration={1}" -f $route.regeneration.model_identity.selected_family, $route.regeneration.calibration_identity_sha256.Substring(0, 12))
    }
}

# --------------------------------------------------------------------------- #
# 8. Targeted regression tests (mandatory)                                    #
# --------------------------------------------------------------------------- #
Write-Section "8. Targeted regression"

python -m pytest tests/experiments/test_rh04_v2_reference.py `
    -q -W error -k "v2_02 or v2_03 or v2_07 or lane_a or convergence"
if ($LASTEXITCODE -eq 0) {
    Add-Result "targeted regression" "PASS" "exit 0"
}
else {
    Add-Result "targeted regression" "FAIL" ("exit {0}" -f $LASTEXITCODE)
}

# --------------------------------------------------------------------------- #
# 9. Frozen V1 surface                                                       #
# --------------------------------------------------------------------------- #
Write-Section "9. Frozen-surface check"

foreach ($file in @(
    "research/intake/offline_fixture_pack.py",
    "research/intake/fixtures/offline_io.v1.json",
    "tests/experiments/test_offline_fixture_pack.py",
    "ai/report_comparison.py"
)) {
    $baseContent = (git show ("refs/remotes/origin/main:{0}" -f $file) 2>$null | Out-String)
    if ([string]::IsNullOrWhiteSpace($baseContent)) {
        Add-Result ("frozen {0}" -f $file) "FAIL" "not present in the base reference; cannot verify"
        continue
    }
    git diff --quiet refs/remotes/origin/main -- $file
    if ($LASTEXITCODE -eq 0) {
        Add-Result ("frozen {0}" -f $file) "PASS" "byte-identical to origin/main"
    }
    else {
        Add-Result ("frozen {0}" -f $file) "FAIL" "differs from origin/main; a frozen V1 artifact must not change"
    }
}

# --------------------------------------------------------------------------- #
# 10. Summary                                                                 #
# --------------------------------------------------------------------------- #
Write-Section "10. Summary"

$script:Results | Format-Table -AutoSize | Out-Host

Write-Host ""
Write-Host ("  HEAD        : {0}" -f $head)
Write-Host ("  base        : {0}" -f $baseRef)
Write-Host ("  interpreter : {0}" -f $interpreterPath)
Write-Host ("  evidence    : {0}" -f $evidenceRoot)
Write-Host ("  failures    : {0}" -f $script:Failures.Count)

$overall = "GREEN"
if ($script:Failures.Count -gt 0) {
    $overall = "RED"
}
$summary = [pscustomobject]@{
    head         = $head
    base_ref     = $baseRef
    interpreter  = $interpreterPath
    python       = $interpreter
    platform     = ([System.Environment]::OSVersion.VersionString)
    architecture = ([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture).ToString()
    evidence_dir = $evidenceRoot
    results      = $script:Results
    failures     = $script:Failures
    result       = $overall
}
$summaryPath = Join-Path $evidenceRoot "summary.json"
$summary | ConvertTo-Json -Depth 8 | Set-Content -Path $summaryPath -Encoding UTF8
Write-Host ("  summary     : {0}" -f $summaryPath)

if ($script:Failures.Count -gt 0) {
    Write-Host ""
    Write-Host "  RESULT: RED" -ForegroundColor Red
    foreach ($failure in $script:Failures) {
        Write-Host ("    - {0}" -f $failure) -ForegroundColor Red
    }
    Write-Host ""
    Write-Host "  Record this output verbatim. Do not adjust a tolerance, fixture," -ForegroundColor Yellow
    Write-Host "  expectation or case count to turn this green." -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "  RESULT: GREEN - all native Windows checks passed" -ForegroundColor Green
Write-Host "  Record this output verbatim as the native Windows evidence." -ForegroundColor Green
exit 0
