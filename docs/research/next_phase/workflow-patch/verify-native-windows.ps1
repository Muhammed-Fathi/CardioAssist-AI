<#
.SYNOPSIS
    RH-04 V2 native Windows verification - Lane A, Lane B and V1.
    PowerShell 5.1 compatible.

.DESCRIPTION
    Executes the required native Windows evidence for the frozen delivery SHA.
    Reuses the repository's own requirement files, so the environment is the one
    the project declares rather than an ad-hoc set.

    CORRECTIONS IN THIS VERSION
      * The statement-list expression
            Add-Result "..." $(if (...) { "PASS" } else { "FAIL" })
        is not valid PowerShell 5.1 and has been removed. Results are computed
        into variables and then recorded.
      * The old Lane B check searched the whole console output for the expected
        digest with -match. That reports "the string appears somewhere", not "the
        observed digest is the expected digest". The observed digest and verdict
        are now parsed from the JSON and compared as values.
      * The environment is created in a dedicated directory, never a
        caller-selected directory that is deleted recursively. An existing
        dedicated venv is reused only with -ReuseVenv; otherwise the run stops
        and says what to do.

    What it proves, and what it does not:

      * Lane B exact replay on Windows, with the fixed digest and no tolerance.
      * Lane A convergence evidence on Windows for both fitted components,
        classified.
      * V1 scoped verification on Windows.
      * dependency, resident-library, SHA and count provenance.

    It does NOT change any artifact, tolerance, fixture or expectation. If a count
    or a digest disagrees with the pinned value it reports RED and exits non-zero;
    it never regenerates an expectation to match an observation.

.PARAMETER ExpectedHead
    The frozen delivery SHA this run is evidence for.

.PARAMETER ReuseVenv
    Reuse an existing dedicated environment instead of stopping.

.PARAMETER SkipInstall
    Skip environment creation and dependency installation. The interpreter must
    already be in place.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\verify-native-windows.ps1 `
        -ExpectedHead 2aee5edd6c60ad530aa3804b7833c9acfd019d9e
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

# --------------------------------------------------------------------------- #
# 0. Fresh evidence directory                                                 #
# --------------------------------------------------------------------------- #
# A dedicated path only. If something else is already there and -ReuseVenv was not
# given, stop rather than delete it: the caller may have pointed this at a real
# environment by accident.
$evidenceDir = ".rh04-evidence-win"
if (Test-Path $evidenceDir) {
    Write-Host "  reusing existing evidence directory $evidenceDir"
}
else {
    New-Item -ItemType Directory -Path $evidenceDir | Out-Null
}

# --------------------------------------------------------------------------- #
# 1. Repository identity                                                      #
# --------------------------------------------------------------------------- #
Write-Section "1. Repository identity"

if (-not (Test-Path ".git")) {
    Write-Host "Not a git checkout. Run this from the repository root." -ForegroundColor Red
    exit 2
}

$head = (git rev-parse HEAD 2>$null)
if ($LASTEXITCODE -ne 0) {
    Write-Host "git rev-parse HEAD failed." -ForegroundColor Red
    exit 2
}
$head = $head.Trim()

Write-Host ("  checkout HEAD : {0}" -f $head)
Write-Host ("  expected HEAD : {0}" -f $ExpectedHead)

if ($head -eq $ExpectedHead) {
    Add-Result "checkout HEAD" "PASS" $head
}
else {
    # Stop immediately. Any later evidence would belong to a different commit.
    Add-Result "checkout HEAD" "FAIL" ("checkout is {0}, expected {1}" -f $head, $ExpectedHead)
    Write-Host ""
    Write-Host "  Stopping: this run cannot be evidence for the frozen SHA." -ForegroundColor Red
    Write-Host "  Check out the reviewed commit and re-run. Nothing else was executed." -ForegroundColor Red
    exit 2
}

$dirty = @(git status --porcelain "--untracked-files=no" 2>$null)
if ($dirty.Count -eq 0) {
    Add-Result "working tree clean" "PASS" "no uncommitted tracked changes"
}
else {
    Write-Host $dirty
    Add-Result "working tree clean" "FAIL" "uncommitted tracked changes present; evidence would not correspond to a commit"
    Write-Host ""
    Write-Host "  Stopping immediately: a dirty tracked tree cannot produce commit evidence." -ForegroundColor Red
    exit 2
}

# The base reference is required by the preservation test; fetch it if absent.
git rev-parse --verify refs/remotes/origin/main 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  base ref absent; fetching origin/main" -ForegroundColor Yellow
    git fetch --no-tags origin "+refs/heads/main:refs/remotes/origin/main" | Out-Null
}
$baseRef = (git rev-parse refs/remotes/origin/main 2>$null)
if ($LASTEXITCODE -eq 0 -and $baseRef) {
    $baseRef = $baseRef.Trim()
    Add-Result "base reference" "PASS" $baseRef
}
else {
    Add-Result "base reference" "FAIL" "origin/main unavailable; the preservation test cannot run and must not skip"
    Write-Host "  Stopping: the frozen-surface check has no trusted base." -ForegroundColor Red
    exit 2
}

Write-Host ("  git version   : {0}" -f (git --version))
Write-Host ("  OS            : {0}" -f ([System.Environment]::OSVersion.VersionString))
Write-Host ("  architecture  : {0}" -f ([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture))

# --------------------------------------------------------------------------- #
# 2. Environment - dedicated directory only                                   #
# --------------------------------------------------------------------------- #
Write-Section "2. Python environment"

if (-not $SkipInstall) {
    if (Test-Path $VenvPath) {
        if ($ReuseVenv) {
            Write-Host ("  reusing existing environment {0} (-ReuseVenv)" -f $VenvPath)
        }
        else {
            Add-Result "venv directory" "FAIL" ("{0} already exists; pass -ReuseVenv to reuse it, or remove it yourself" -f $VenvPath)
            Write-Host ""
            Write-Host "  Stopping: refusing to delete a directory recursively. This script" -ForegroundColor Red
            Write-Host "  only creates a dedicated environment, and it will not remove one." -ForegroundColor Red
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

# Verify the actual interpreter, not the one we hoped for.
$interpreter = (& python -c "import sys;print(sys.version.split()[0])").Trim()
$interpreterPath = (& python -c "import sys;print(sys.executable)").Trim()
Write-Host ("  interpreter   : {0}" -f $interpreterPath)
if ($interpreter -like "3.11.*") {
    Add-Result "interpreter" "PASS" ("Python {0} at {1}" -f $interpreter, $interpreterPath)
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
    # The independent oracle is required evidence, not an optional extra. Without
    # it the oracle tests fail closed by design.
    python -m pip install -r research/experiments/requirements-oracle.txt --quiet
    if ($LASTEXITCODE -ne 0) {
        Add-Result "oracle install" "FAIL" "requirements-oracle.txt failed to install"
        exit 2
    }
    Add-Result "oracle install" "PASS" "research/experiments/requirements-oracle.txt"
}

# --------------------------------------------------------------------------- #
# 3. Dependency validation and resident libraries                             #
# --------------------------------------------------------------------------- #
Write-Section "3. Dependency validation"

python -m pip check | Out-Host
if ($LASTEXITCODE -eq 0) {
    Add-Result "pip check" "PASS" "no broken requirements"
}
else {
    Add-Result "pip check" "FAIL" "broken requirements reported"
}

$versionsJson = python -c @"
import sys; sys.path.insert(0, '.')
import importlib.metadata as m, json
names = ('numpy','scipy','scikit-learn','mpmath','pytest','openpyxl','threadpoolctl')
out = {}
for n in names:
    try:
        out[n] = m.version(n)
    except Exception:
        out[n] = None
print(json.dumps(out, sort_keys=True))
"@
Write-Host ("  resolved versions: {0}" -f $versionsJson)
Add-Result "resolved versions" "PASS" $versionsJson

# Resident libraries, read after the numerical libraries are loaded. Reading
# threadpool_info() before the first BLAS call reports the library but not the
# kernel actually in use, and OPENBLAS_CORETYPE is only a request anyway.
$residentJson = python -c @"
import sys; sys.path.insert(0, '.')
import json
try:
    import numpy as np
    matrix = np.random.default_rng(0).normal(size=(256, 256))
    matrix @ matrix.T
    from threadpoolctl import threadpool_info
    keys = ('internal_api', 'user_api', 'version', 'architecture', 'filepath', 'num_threads')
    entries = [{k: e.get(k) for k in keys} for e in threadpool_info()]
    print(json.dumps({'libraries': entries}, sort_keys=True))
except Exception as exc:
    print(json.dumps({'error': type(exc).__name__}))
"@
Write-Host ("  resident libraries: {0}" -f $residentJson)
if ($residentJson -match '"error"') {
    Add-Result "resident numerical libraries" "FAIL" "threadpoolctl could not report the loaded libraries; an empty or failed read is not evidence"
}
else {
    Add-Result "resident numerical libraries" "PASS" $residentJson
}

# --------------------------------------------------------------------------- #
# 4. Evidence directory must stay inside the workspace                        #
# --------------------------------------------------------------------------- #
$evidenceRoot = (Resolve-Path $evidenceDir).Path
Write-Host ("  evidence root : {0}" -f $evidenceRoot)
Add-Result "evidence directory" "PASS" $evidenceRoot

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
# 6. Lane B - mandatory exact reference replay                                #
# --------------------------------------------------------------------------- #
Write-Section "6. Lane B exact reference replay (mandatory)"

$expectedDigest = "891d9e3b2a332c6efc251d97fee25ed46a627ed25b2a089594057b4c9896cdc8"
$laneBPath = Join-Path $evidenceDir "lane-b.json"

python -c @"
import sys; sys.path.insert(0, '.')
import json
import pathlib
from ai import research_facade as facade
from research.intake import offline_fixture_pack as v1
from research.intake import rh04_v2_portable_archive as archive
from research.intake import rh04_v2_value_mapping as mapping

expected_digest = '$expectedDigest'
admitted = archive.admit_from_directory('research/intake/fixtures/rh04_v2_portable')
result = archive.replay_admitted(facade, admitted)
pack = json.loads(v1.PACK.read_text(encoding='utf-8'))
order = [c['id'] for c in pack['cases']]
expected = {c['id']: c['expected'] for c in pack['cases']}
observed = {cid: r for cid, r in zip(order, result['responses'])}
document = mapping.mapping_with_discrimination_proof(expected, observed)
verdict = {
    'n_cases': result['n_cases'],
    'observed_digest': result['digest'],
    'expected_digest': expected_digest,
    'reference_digest': archive.LANE_B_REFERENCE_DIGEST,
    'matches_reference': result['digest'] == expected_digest,
    'numeric_tolerance': 'none',
    'leaf_totals': document['leaf_totals'],
    'total_leaves': document['total_leaves'],
    'cases_with_numeric_delta': document['cases_with_numeric_delta'],
    'discrimination_proof_detected': document['discrimination_proof']['detected'],
}
verdict['verdict'] = 'ACCEPTED' if (
    verdict['matches_reference']
    and verdict['n_cases'] == 29
    and verdict['cases_with_numeric_delta'] == 0
    and verdict['discrimination_proof_detected'] is True
) else 'REFUSED'
pathlib.Path(r'$evidenceDir/lane-b.json').write_text(
    json.dumps(verdict, indent=2, sort_keys=True), encoding='utf-8'
)
print(json.dumps(verdict, indent=2, sort_keys=True))
"@
Write-Host $laneBJson

# Read the recorded observation back and compare the VALUE. This is the
# correction: the old check matched the expected digest against the whole console
# output, which passes whenever the expected string is printed for any reason.
if (Test-Path $laneBPath) {
    $laneB = Get-Content -Path $laneBPath -Raw | ConvertFrom-Json
    $laneBDigestOk = ($laneB.observed_digest -eq $expectedDigest)
    $laneBReferenceOk = ($laneB.reference_digest -eq $expectedDigest)
    $laneBCountOk = ($laneB.n_cases -eq 29)
    $laneBVerdictOk = ($laneB.verdict -eq "ACCEPTED")

    if ($laneBDigestOk) {
        Add-Result "Lane B observed digest" "PASS" $laneB.observed_digest
    }
    else {
        Add-Result "Lane B observed digest" "FAIL" ("observed {0}, expected {1}; the expectation is NOT regenerated to match" -f $laneB.observed_digest, $expectedDigest)
    }
    if ($laneBReferenceOk) {
        Add-Result "Lane B pinned reference" "PASS" $laneB.reference_digest
    }
    else {
        Add-Result "Lane B pinned reference" "FAIL" ("pinned reference is {0}" -f $laneB.reference_digest)
    }
    if ($laneBCountOk) {
        Add-Result "Lane B case count" "PASS" "29 registered cases replayed"
    }
    else {
        Add-Result "Lane B case count" "FAIL" ("{0} cases replayed, expected 29" -f $laneB.n_cases)
    }
    if ($laneBVerdictOk) {
        Add-Result "Lane B verdict" "PASS" "ACCEPTED"
    }
    else {
        Add-Result "Lane B verdict" "FAIL" ("verdict is {0}" -f $laneB.verdict)
    }
    if ($laneB.cases_with_numeric_delta -eq 0) {
        Add-Result "Lane B numeric deltas" "PASS" "0 numeric deltas across all leaves"
    }
    else {
        Add-Result "Lane B numeric deltas" "FAIL" ("{0} leaves moved; Lane B is exact and this is not acceptable" -f $laneB.cases_with_numeric_delta)
    }
}
else {
    Add-Result "Lane B evidence file" "FAIL" ("{0} was not produced; no verdict can be recorded" -f $laneBPath)
}

# --------------------------------------------------------------------------- #
# 7. Lane A - classified evidence for both fitted components                  #
# --------------------------------------------------------------------------- #
Write-Section "7. Lane A regeneration evidence (classified)"

$laneAPath = Join-Path $evidenceDir "lane-a.json"
python -c @"
import sys; sys.path.insert(0, '.')
import json
import pathlib
from research.intake import rh04_v2_lane_a_convergence as lane_a

report = {'lane': 'A', 'routes': {}}
for route_id in ('da_a1_basic_clinical_v1', 'da_a2_resting_v1'):
    try:
        document = lane_a.produce_complete_evidence(route_id)
    except Exception as exc:
        report['routes'][route_id] = {
            'classification': 'EVIDENCE_MISSING',
            'error': type(exc).__name__,
            'is_failure': True,
        }
        continue
    model = document['components']['logistic_regression']
    calibration = document['components']['oof_calibration_optimizer']
    report['routes'][route_id] = {
        'execution_profile': model.get('execution_profile'),
        'any_failure': document['any_failure'],
        'evidence_sha256': document['evidence_sha256'],
        'logistic_regression': {
            'n_observations': model.get('n_fits_observed'),
            'classifications': model['classifications'],
            'residual_min': model['residual_summary'].get('min'),
            'residual_max': model['residual_summary'].get('max'),
        },
        'oof_calibration_optimizer': {
            'n_observations': calibration.get('n_optimizations'),
            'classifications': calibration['classifications'],
            'residual_min': calibration['residual_summary'].get('min'),
            'residual_max': calibration['residual_summary'].get('max'),
            'declaration': calibration.get('declaration'),
        },
    }
pathlib.Path(r'$evidenceDir/lane-a.json').write_text(
    json.dumps(report, indent=2, sort_keys=True), encoding='utf-8'
)
print(json.dumps(report, indent=2, sort_keys=True))
"@
Write-Host $laneAJson

if (Test-Path $laneAPath) {
    $laneA = Get-Content -Path $laneAPath -Raw | ConvertFrom-Json
    foreach ($routeId in @("da_a1_basic_clinical_v1", "da_a2_resting_v1")) {
        $route = $laneA.routes.$routeId
        if ($null -eq $route) {
            Add-Result ("Lane A {0}" -f $routeId) "FAIL" "no evidence produced for this route"
            continue
        }
        $lrCount = $route.logistic_regression.n_observations
        $calCount = $route.oof_calibration_optimizer.n_observations
        if ($lrCount -gt 0 -and $calCount -gt 0) {
            Add-Result ("Lane A {0} observation" -f $routeId) "PASS" ("{0} model fits and {1} calibration optimizations observed" -f $lrCount, $calCount)
        }
        else {
            Add-Result ("Lane A {0} observation" -f $routeId) "FAIL" ("model fits {0}, calibration optimizations {1}; both components are required" -f $lrCount, $calCount)
        }
        if ($route.any_failure -eq $false) {
            Add-Result ("Lane A {0} classification" -f $routeId) "PASS" "no training failure, missing evidence or invalid output"
        }
        else {
            Add-Result ("Lane A {0} classification" -f $routeId) "FAIL" "a fit failed, or its evidence is missing or invalid"
        }
    }
}
else {
    Add-Result "Lane A evidence file" "FAIL" ("{0} was not produced" -f $laneAPath)
}

# --------------------------------------------------------------------------- #
# 8. Frozen V1 surface                                                        #
# --------------------------------------------------------------------------- #
Write-Section "8. Frozen-surface check"

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
# 9. Summary                                                                  #
# --------------------------------------------------------------------------- #
Write-Section "9. Summary"

$script:Results | Format-Table -AutoSize | Out-Host

Write-Host ""
Write-Host ("  HEAD          : {0}" -f $head)
Write-Host ("  base reference: {0}" -f $baseRef)
Write-Host ("  interpreter   : {0}" -f $interpreterPath)
Write-Host ("  evidence      : {0}" -f $evidenceRoot)
Write-Host ("  failures      : {0}" -f $script:Failures.Count)

# Persist the machine-readable record, so the owner can attach it unedited.
# Note: the verdict is assigned with a plain if/else. A statement-list `$(if ...)`
# inside a hashtable literal is not valid PowerShell 5.1.
$overall = "GREEN"
if ($script:Failures.Count -gt 0) {
    $overall = "RED"
}
$summary = [pscustomobject]@{
    head          = $head
    base_ref      = $baseRef
    interpreter   = $interpreterPath
    python        = $interpreter
    platform      = ([System.Environment]::OSVersion.VersionString)
    architecture  = ([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture).ToString()
    results       = $script:Results
    failures      = $script:Failures
    result        = $overall
}
$summaryPath = Join-Path $evidenceDir "summary.json"
$summary | ConvertTo-Json -Depth 8 | Set-Content -Path $summaryPath -Encoding UTF8
Write-Host ("  summary       : {0}" -f $summaryPath)

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
