<#
.SYNOPSIS
    RH-04 V2 native Windows verification — Lane A and Lane B.

.DESCRIPTION
    Executes the required native Windows evidence for the frozen delivery SHA.
    Reuses the repository's own requirement files, so the environment is the one
    the project declares rather than an ad-hoc set.

    What it proves, and what it does not:

      * Lane B exact replay on Windows, with the fixed digest and no tolerance.
      * Lane A convergence evidence on Windows, classified.
      * V1 scoped verification on Windows.
      * dependency, resident-library, SHA and count provenance.

    It does NOT change any artifact, tolerance, fixture or expectation. If a count
    or a digest disagrees with the pinned value it reports RED and exits non-zero;
    it never regenerates an expectation to match an observation.

.PARAMETER ExpectedHead
    The frozen delivery SHA this run is evidence for.

.PARAMETER SkipInstall
    Skip environment creation, to re-run checks in an existing environment.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File verify-native-windows.ps1 `
        -ExpectedHead 0000000000000000000000000000000000000000
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ExpectedHead,
    [string]$VenvPath = ".venv-rh04-win",
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
    $colour = switch ($Status) { "PASS" { "Green" } "FAIL" { "Red" } default { "Yellow" } }
    Write-Host ("  [{0}] {1}: {2}" -f $Status, $Check, $Detail) -ForegroundColor $colour
    if ($Status -eq "FAIL") { $script:Failures.Add("$Check — $Detail") }
}

# --------------------------------------------------------------------------- #
# 1. Repository identity                                                      #
# --------------------------------------------------------------------------- #
Write-Section "1. Repository identity"

if (-not (Test-Path ".git")) {
    Write-Host "Not a git checkout. Run this from the repository root." -ForegroundColor Red
    exit 2
}

$head = (git rev-parse HEAD).Trim()
Write-Host "  checkout HEAD : $head"
Write-Host "  expected HEAD : $ExpectedHead"

if ($head -eq $ExpectedHead) {
    Add-Result "checkout HEAD" "PASS" $head
} else {
    Add-Result "checkout HEAD" "FAIL" "checkout is $head, expected $ExpectedHead — this run is not evidence for the frozen SHA"
}

$dirty = (git status --porcelain)
if ([string]::IsNullOrWhiteSpace($dirty)) {
    Add-Result "working tree clean" "PASS" "no uncommitted changes"
} else {
    Add-Result "working tree clean" "FAIL" "uncommitted changes present; evidence would not correspond to a commit"
}

# The base reference is required by the preservation test; fetch it if absent.
git rev-parse --verify refs/remotes/origin/main 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  base ref absent; fetching origin/main" -ForegroundColor Yellow
    git fetch --no-tags origin "+refs/heads/main:refs/remotes/origin/main" | Out-Null
}
$baseRef = (git rev-parse refs/remotes/origin/main 2>$null)
if ($LASTEXITCODE -eq 0 -and $baseRef) {
    Add-Result "base reference" "PASS" $baseRef.Trim()
} else {
    Add-Result "base reference" "FAIL" "origin/main unavailable; the preservation test cannot run and must not skip"
}

Write-Host "  git version   : $((git --version))"
Write-Host "  OS            : $([System.Environment]::OSVersion.VersionString)"
Write-Host "  architecture  : $([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture)"

# --------------------------------------------------------------------------- #
# 2. Environment                                                              #
# --------------------------------------------------------------------------- #
Write-Section "2. Python environment"

if (-not $SkipInstall) {
    if (Test-Path $VenvPath) {
        Write-Host "  removing existing $VenvPath" -ForegroundColor Yellow
        Remove-Item -Recurse -Force $VenvPath
    }
    Write-Host "  creating $VenvPath"
    py -3.11 -m venv $VenvPath
    if ($LASTEXITCODE -ne 0) {
        Add-Result "venv creation" "FAIL" "py -3.11 -m venv failed; Python 3.11 is required"
        exit 2
    }
}

$activate = Join-Path $VenvPath "Scripts\Activate.ps1"
if (-not (Test-Path $activate)) {
    Add-Result "venv activation" "FAIL" "$activate not found"
    exit 2
}
. $activate

Add-Result "interpreter" "PASS" $((& python -c "import sys;print(sys.version.split()[0])"))

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
# 3. Dependency validation                                                    #
# --------------------------------------------------------------------------- #
Write-Section "3. Dependency validation"

python -m pip check | Out-Host
if ($LASTEXITCODE -eq 0) {
    Add-Result "pip check" "PASS" "no broken requirements"
} else {
    Add-Result "pip check" "FAIL" "broken requirements reported"
}

$versionsJson = python -c @"
import importlib.metadata as m, json
names = ('numpy','scipy','scikit-learn','mpmath','pytest','openpyxl','threadpoolctl')
out = {}
for n in names:
    try: out[n] = m.version(n)
    except Exception: out[n] = None
print(json.dumps(out, sort_keys=True))
"@
Add-Result "resolved versions" "PASS" $versionsJson

# Resident libraries, not requested: OPENBLAS_CORETYPE is only a request.
$residentJson = python -c @"
import json
try:
    from threadpoolctl import threadpool_info
    keys = ('internal_api','user_api','version','architecture','filepath')
    print(json.dumps([{k: e.get(k) for k in keys} for e in threadpool_info()], sort_keys=True))
except Exception as exc:
    print(json.dumps({'error': type(exc).__name__}))
"@
Add-Result "resident numerical libraries" "PASS" $residentJson

# --------------------------------------------------------------------------- #
# 4. V1 scoped verification (mandatory)                                       #
# --------------------------------------------------------------------------- #
Write-Section "4. V1 scoped verification (mandatory)"

python -m pytest tests/experiments/test_offline_fixture_pack.py `
                 tests/experiments/test_research_facade.py `
                 tests/contracts -q -W error
if ($LASTEXITCODE -eq 0) {
    Add-Result "V1 scoped suite" "PASS" "exit 0"
} else {
    Add-Result "V1 scoped suite" "FAIL" "exit $LASTEXITCODE — V1 is the mandatory lane; a failure here is not suppressible"
}

# --------------------------------------------------------------------------- #
# 5. Lane B — mandatory exact reference replay                                #
# --------------------------------------------------------------------------- #
Write-Section "5. Lane B exact reference replay (mandatory)"

$expectedDigest = "891d9e3b2a332c6efc251d97fee25ed46a627ed25b2a089594057b4c9896cdc8"
$laneBJson = python -c @"
import json, sys
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
    'digest': result['digest'],
    'expected_digest': expected_digest,
    'matches_reference': result['digest'] == expected_digest,
    'numeric_tolerance': 'none',
    'leaf_totals': document['leaf_totals'],
    'total_leaves': document['total_leaves'],
    'discrimination_proof_detected': document['discrimination_proof']['detected'],
}
print(json.dumps(verdict, indent=2, sort_keys=True))
ok = (result['digest'] == expected_digest and result['n_cases'] == 29
      and document['leaf_totals'].get('NUMERIC_DELTA', 0) == 0
      and document['discrimination_proof']['detected'] is True)
sys.exit(0 if ok else 1)
"@
Write-Host $laneBJson
if ($LASTEXITCODE -eq 0) {
    Add-Result "Lane B exact replay" "PASS" "digest matches reference, 29 cases, no numeric delta"
} else {
    Add-Result "Lane B exact replay" "FAIL" "digest or case count disagrees; expectations are NOT regenerated to match"
}

# --------------------------------------------------------------------------- #
# 6. Lane A — classified regeneration evidence                                #
# --------------------------------------------------------------------------- #
Write-Section "6. Lane A regeneration evidence (classified)"

$laneAJson = python -c @"
import json, sys
from research.intake import rh04_v2_lane_a_convergence as lane_a

exit_code = 0
report = {'lane': 'A', 'routes': {}}
for route_id in ('da_a1_basic_clinical_v1', 'da_a2_resting_v1'):
    try:
        document = lane_a.produce_lane_a_evidence(route_id)
    except Exception as exc:
        report['routes'][route_id] = {'classification': 'EVIDENCE_MISSING',
                                      'error': type(exc).__name__, 'is_failure': True}
        exit_code = 1
        continue
    report['routes'][route_id] = {
        'execution_profile': document['execution_profile'],
        'n_fits_observed': document['n_fits_observed'],
        'residual_min': document['residual_summary']['min'],
        'residual_max': document['residual_summary']['max'],
        'classifications': document['classifications'],
        'any_failure': document['any_failure'],
        'evidence_sha256': document['evidence_sha256'],
    }
    if document['any_failure']:
        exit_code = 1
print(json.dumps(report, indent=2, sort_keys=True))
sys.exit(exit_code)
"@
Write-Host $laneAJson
if ($LASTEXITCODE -eq 0) {
    Add-Result "Lane A evidence" "PASS" "all observed fits converged under the solver's own criterion"
} else {
    Add-Result "Lane A evidence" "FAIL" "training failure, missing evidence or invalid output — not acceptable variation"
}

# --------------------------------------------------------------------------- #
# 7. Result hashes                                                            #
# --------------------------------------------------------------------------- #
Write-Section "7. Result hashes and frozen-surface check"

Add-Result "Lane B digest" $(if ($laneBJson -match $expectedDigest) { "PASS" } else { "FAIL" }) `
    $(if ($laneBJson -match $expectedDigest) { $expectedDigest } else { "reference digest not found in output" })

# The frozen V1 artifacts must be byte-identical to the base reference.
foreach ($file in @(
    "research/intake/offline_fixture_pack.py",
    "research/intake/fixtures/offline_io.v1.json",
    "tests/experiments/test_offline_fixture_pack.py",
    "ai/report_comparison.py"
)) {
    $baseHash = (git show "refs/remotes/origin/main:$file" 2>$null | Out-String)
    if ([string]::IsNullOrWhiteSpace($baseHash)) {
        Add-Result "frozen $file" "FAIL" "not present in the base reference; cannot verify"
        continue
    }
    $same = (git diff --quiet refs/remotes/origin/main -- $file; $LASTEXITCODE -eq 0)
    if ($same) {
        Add-Result "frozen $file" "PASS" "byte-identical to origin/main"
    } else {
        Add-Result "frozen $file" "FAIL" "differs from origin/main — a frozen V1 artifact must not change"
    }
}

# --------------------------------------------------------------------------- #
# 8. Summary                                                                  #
# --------------------------------------------------------------------------- #
Write-Section "8. Summary"

$script:Results | Format-Table -AutoSize | Out-Host

Write-Host ""
Write-Host ("  HEAD          : {0}" -f $head)
Write-Host ("  base reference: {0}" -f $baseRef)
Write-Host ("  failures      : {0}" -f $script:Failures.Count)

if ($script:Failures.Count -gt 0) {
    Write-Host ""
    Write-Host "  RESULT: RED" -ForegroundColor Red
    foreach ($failure in $script:Failures) { Write-Host "    - $failure" -ForegroundColor Red }
    Write-Host ""
    Write-Host "  Record this output verbatim. Do not adjust a tolerance, fixture," -ForegroundColor Yellow
    Write-Host "  expectation or case count to turn this green." -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "  RESULT: GREEN — all native Windows checks passed" -ForegroundColor Green
Write-Host "  Record this output verbatim as the native Windows evidence." -ForegroundColor Green
exit 0
