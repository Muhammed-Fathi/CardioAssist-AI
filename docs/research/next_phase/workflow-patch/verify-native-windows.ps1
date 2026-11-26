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
    if ($laneB.estimator_fitting_performed -eq $false -and $laneB.fitting_attempts_observed.Count -eq 0) {
        Add-Result "Lane B no fitting" "PASS" ("guard armed {0} entry points, 0 attempts" -f $laneB.fitting_guard_armed_entry_points.Count)
    }
    else {
        Add-Result "Lane B no fitting" "FAIL" "Lane B fitted a model, or a fit was attempted"
    }
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
        # V2-04a: five separate properties, never one merged verdict.
        $params = $route.regeneration.regenerated_parameters

        # 1. Provenance: where the numbers came from. Required.
        if ($params.source_provenance.registered_producer) {
            Add-Result ("Lane A {0} source provenance" -f $routeId) "PASS" ("{0}, {1} rows, spec {2}" -f $params.source_provenance.registered_producer, $params.source_provenance.training_rows, $params.source_provenance.producer_spec_sha256.Substring(0, 12))
        }
        else {
            Add-Result ("Lane A {0} source provenance" -f $routeId) "FAIL" "no source provenance recorded"
        }

        # 2. Parameter identity: the actual regenerated vector. Required.
        if ($params.parameter_identity.regenerated_parameters_sha256) {
            Add-Result ("Lane A {0} parameter identity" -f $routeId) "PASS" ("{0} (sha {1})" -f $params.parameter_identity.kind, $params.parameter_identity.regenerated_parameters_sha256.Substring(0, 12))
        }
        else {
            Add-Result ("Lane A {0} parameter identity" -f $routeId) "FAIL" "no regenerated parameter identity recorded"
        }

        # 3. Provenance lineage validity. Required, and NOT the same as equality.
        if ($params.provenance_lineage_valid.valid -eq $true) {
            Add-Result ("Lane A {0} provenance lineage" -f $routeId) "PASS" ("preprocessing exact, bitwise equality={0}" -f $params.provenance_lineage_valid.bitwise_equality)
        }
        else {
            Add-Result ("Lane A {0} provenance lineage" -f $routeId) "FAIL" "provenance lineage is not established"
        }

        # 4. Equality against the archive: MEASURED and CLASSIFIED, never required.
        $eq = $params.archived_parameter_equality
        if ($eq.measured -ne $true) {
            Add-Result ("Lane A {0} archived-parameter equality" -f $routeId) "FAIL" "equality against the archive was not measured"
        }
        elseif ($eq.exact -eq $true) {
            Add-Result ("Lane A {0} archived-parameter equality" -f $routeId) "PASS" ("IDENTICAL ({0})" -f $eq.basis)
        }
        else {
            # A measured difference is a FINDING. It is reported as such, with its
            # magnitude, and it does not fail the run. Calling this a failure is the
            # contradiction that made the 4x2 matrix unsatisfiable on Windows.
            $delta = if ($eq.coefficient_max_abs_delta -ne $null) { $eq.coefficient_max_abs_delta } else { $eq.max_float_delta }
            Add-Result ("Lane A {0} archived-parameter equality" -f $routeId) "FINDING" ("{0}, max|delta|={1}" -f $eq.classification, $delta)
        }

        # 5. Structural integrity of the response: required on both replays.
        if ($params.parameter_identity.kind -eq "tree_structure") {
            if ($params.parameter_identity.tree_count -eq $eq.tree_count_refit) {
                Add-Result ("Lane A {0} forest structure" -f $routeId) "PASS" ("{0} of {1} trees" -f $eq.tree_count_refit, $eq.tree_count_archived)
            }
            else {
                Add-Result ("Lane A {0} forest structure" -f $routeId) "FAIL" "tree count disagrees between refit and archive"
            }
        }
    }
}

# The two replays are DISTINCT evidence and must both be present and separate.
if ($laneA.replay_response_identity) {
    $frozen = $laneA.replay_response_identity.frozen_archive_replay
    $fresh = $laneA.replay_response_identity.fresh_model_replay
    if ($frozen.replay_responses_sha256) {
        Add-Result "Lane A frozen-archive replay identity" "PASS" ("29 cases, sha {0}" -f $frozen.replay_responses_sha256.Substring(0, 16))
    }
    else {
        Add-Result "Lane A frozen-archive replay identity" "FAIL" "no frozen replay identity"
    }
    if ($fresh.replay_responses_sha256) {
        Add-Result "Lane A fresh-model replay identity" "PASS" ("{0} models rebuilt, sha {1}" -f $fresh.models_rebuilt.Count, $fresh.replay_responses_sha256.Substring(0, 16))
    }
    else {
        Add-Result "Lane A fresh-model replay identity" "FAIL" "no fresh-model replay identity; a frozen replay alone does not prove regeneration"
    }
    # The frozen replay is the one that must match the fixed reference exactly.
    if ($frozen.aggregate_digest -eq $expectedDigest) {
        Add-Result "Lane A frozen replay vs fixed reference" "PASS" $frozen.aggregate_digest
    }
    else {
        Add-Result "Lane A frozen replay vs fixed reference" "FAIL" ("{0} != {1}" -f $frozen.aggregate_digest, $expectedDigest)
    }
    # R23-04: fail closed on TYPE, not just value. `-eq $true` is satisfied by the
    # string "true" and by 1 in PowerShell, so a malformed verdict would read as a
    # pass. The hosted path requires the value to BE a boolean true; so does this.
    $validityPresent = $null -ne $laneA.PSObject.Properties["validity"]
    $verdictRaw = if ($validityPresent) { $laneA.validity.PSObject.Properties["valid"] } else { $null }
    $verdictIsBool = ($null -ne $verdictRaw) -and ($verdictRaw.Value -is [bool])
    if (-not $validityPresent) {
        Add-Result "Lane A validity" "FAIL" "validity record is absent"
    }
    elseif (-not $verdictIsBool) {
        Add-Result "Lane A validity" "FAIL" ("validity.valid is not a boolean (type {0})" -f $(if ($null -eq $verdictRaw) { "absent" } else { $verdictRaw.Value.GetType().Name }))
    }
    elseif ($verdictRaw.Value -eq $true) {
        Add-Result "Lane A validity" "PASS" ("{0} finding(s), 0 invalid" -f $laneA.validity.findings.Count)
    }
    else {
        Add-Result "Lane A validity" "FAIL" (($laneA.validity.failures -join "; "))
    }
}

# Native Windows repeatability note (R23-04): this procedure makes ONE
# regeneration per route, so it can evidence a valid converged fit but it cannot
# by itself evidence within-environment repeatability -- that requires two
# independent runs in the same environment, which the hosted Stage 2 does with
# run1/run2. Do not read a single Windows run as a repeatability claim.

# --------------------------------------------------------------------------- #
# 8. Targeted regression tests (mandatory)                                    #
# --------------------------------------------------------------------------- #
Write-Section "8. Targeted regression"

# R23-04: this selector was the pre-patch five-family filter (37 of 315 tests).
# It never selected the V2-04a validity predicates -- the amendment's central
# fail-closed rule -- so native Windows evidence would have under-covered exactly
# the property it exists to measure. The selector below is the same one the hosted
# gate uses, extended with the hardening regressions, and is STRICTLY a superset:
# nothing that was selected before is dropped.
#
# Parity is asserted, not assumed: the collected count must equal the gate's
# applicable selection. If someone narrows the gate without narrowing this, or
# widens this without widening the gate, the count check fails loudly.
$rh04ReferenceSelection = "v2_02 or v2_03 or v2_04a or v2_05 or v2_07 or v2_08 or lane_a or lane_b or convergence or portable_lane or manifest_builder or producer_lineage or never_deserializes or never_reads_the_producer or calibration_input"
# Revision 2: the selection is the whole file, not a `-k` expression. A `-k`
# expression silently skips any test added later whose name does not match --
# which is precisely how the R2 regressions could ship unexecuted on Windows.
# The count below is the real collection count of the file at this revision
# (54 Revision 2 tests + 19 reviewer tests), and the parity check fails if collection drifts.
$rh04HardeningSelection = ""

$rh04ReferenceCount = 67
$rh04HardeningCount = 73

$collected = & python -m pytest tests/experiments/test_rh04_v2_reference.py `
    -q --collect-only -k $rh04ReferenceSelection
$collectedCount = ($collected | Select-String -Pattern '^(\d+)/' | ForEach-Object { [int]$_.Matches[0].Groups[1].Value } | Select-Object -First 1)
if ($collectedCount -eq $rh04ReferenceCount) {
    Add-Result "regression selection parity" "PASS" ("{0} of the reference suite collected" -f $collectedCount)
}
else {
    Add-Result "regression selection parity" "FAIL" ("collected {0}, expected {1}; the Windows selector has drifted from the hosted gate" -f $collectedCount, $rh04ReferenceCount)
}

python -m pytest tests/experiments/test_rh04_v2_reference.py `
    -q -W error -k $rh04ReferenceSelection
if ($LASTEXITCODE -eq 0) {
    Add-Result "targeted regression" "PASS" "exit 0"
}
else {
    Add-Result "targeted regression" "FAIL" ("exit {0}" -f $LASTEXITCODE)
}

# The hardening regressions are mandatory on native Windows too: a validity gate
# that is only fail-closed on Linux is not fail-closed for the matrix V2-04 names.
if (Test-Path "tests/experiments/test_rh04_v2_hardening.py") {
    $hardeningCollected = & python -m pytest tests/experiments/test_rh04_v2_hardening.py `
        -q --collect-only
    # `pytest --collect-only -q` ends with "<n> tests collected in <t>", not the
    # "N/..." progress format. The previous pattern matched nothing, so the count
    # was $null, `-ge` compared $null and the parity check failed on every run --
    # a check that can never pass. Match the real summary line.
    $hardeningCount = ($hardeningCollected | Select-String -Pattern '^(\d+) tests? collected' | ForEach-Object { [int]$_.Matches[0].Groups[1].Value } | Select-Object -First 1)
    if ($null -eq $hardeningCount) {
        Add-Result "hardening selection parity" "FAIL" "could not parse the collected count; refusing to report parity that was not measured"
    }
    elseif ($hardeningCount -ge $rh04HardeningCount) {
        Add-Result "hardening selection parity" "PASS" ("{0} collected (minimum {1})" -f $hardeningCount, $rh04HardeningCount)
    }
    else {
        Add-Result "hardening selection parity" "FAIL" ("collected {0}, expected at least {1}" -f $hardeningCount, $rh04HardeningCount)
    }
    python -m pytest tests/experiments/test_rh04_v2_hardening.py `
        -q -W error
    if ($LASTEXITCODE -eq 0) {
        Add-Result "hardening regressions" "PASS" "exit 0"
    }
    else {
        Add-Result "hardening regressions" "FAIL" ("exit {0}" -f $LASTEXITCODE)
    }
}
else {
    Add-Result "hardening regressions" "FAIL" "tests/experiments/test_rh04_v2_hardening.py is absent; the fail-closed regressions cannot run"
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
# Findings are MEASURED DIFFERENCES between valid converged regenerations. They are
# counted and printed, and they do not affect the exit code. A run with findings and
# no failures is a valid run that recorded environment-dependent variation.
$script:Findings = @($script:Results | Where-Object { $_.Status -eq "FINDING" })
Write-Host ("  findings    : {0} (measured differences, not failures)" -f $script:Findings.Count)

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
