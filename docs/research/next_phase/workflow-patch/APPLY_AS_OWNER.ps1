<#
    RH-04 V2 - owner-applied CI patch. PowerShell 5.1 compatible.

    The Arena integration has no `workflows` scope, so it cannot push workflow
    changes: pushes touching .github/workflows are rejected and workflow_dispatch
    returns 403. This script is therefore run by the owner, who has that scope.

    WHAT CHANGED FROM THE PREVIOUS VERSION, AND WHY
      * `patch -p1 < $PatchPath` is gone. PowerShell 5.1 does not implement `<`
        redirection at all: it is a parser error, not a runtime failure. The patch
        is now applied with `git apply`, which reads the file itself.
      * The preview no longer modifies the checkout. Previously the script applied
        the patch and then asked for confirmation, so a preview left a dirty tree
        and the next run failed its own clean-tree check. Preview is now
        `git apply --check` only, which changes nothing.
      * The tree is verified again AFTER applying, so a partially applied patch
        cannot be committed.
      * Only the two known workflow paths may change. Any other path fails.

    ORDER OF OPERATIONS
      1. verify HEAD, branch, clean tree and remote HEAD;
      2. --check the patch (read-only);
      3. show the diff preview;
      4. stop here unless -Confirm;
      5. apply, verify the changed-path set, re-parse both workflows;
      6. commit and push.

    The checkout is left untouched unless -Confirm is supplied.

    Usage, from the repository root:
        powershell -ExecutionPolicy Bypass -File .\APPLY_AS_OWNER.ps1 `
            -ExpectedHead 2aee5edd6c60ad530aa3804b7833c9acfd019d9e

        powershell -ExecutionPolicy Bypass -File .\APPLY_AS_OWNER.ps1 `
            -ExpectedHead 2aee5edd6c60ad530aa3804b7833c9acfd019d9e -Confirm
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ExpectedHead,
    [string]$ExpectedBranch = "delivery/rh04-v2-final",
    [string]$RemoteName = "origin",
    [string]$PatchPath = "docs/research/next_phase/workflow-patch/rh04-ci-consolidated.patch",
    [switch]$Confirm
)

$ErrorActionPreference = "Stop"

# The only paths this patch is allowed to touch. Anything else is a red flag.
$AllowedPaths = @(
    ".github/workflows/experiment-runner-ci.yml",
    ".github/workflows/rh04-dual-run-gate.yml"
)

function Fail([string]$Message) {
    Write-Host ""
    Write-Host "FAILED: $Message" -ForegroundColor Red
    exit 1
}

function Invoke-Git([string[]]$Arguments) {
    $output = & git @Arguments 2>&1
    return @{ Output = $output; Code = $LASTEXITCODE }
}

Write-Host "== 1. verify checkout ==" -ForegroundColor Cyan

$head = (git rev-parse HEAD 2>$null)
if ($LASTEXITCODE -ne 0) { Fail "not a git checkout, or git is not on PATH." }
$head = $head.Trim()
$branch = (git rev-parse --abbrev-ref HEAD 2>$null).Trim()

Write-Host "  HEAD     : $head"
Write-Host "  expected : $ExpectedHead"
Write-Host "  branch   : $branch"
Write-Host "  expected : $ExpectedBranch"

if ($head -ne $ExpectedHead) {
    Fail "checkout is $head, expected $ExpectedHead. Refusing to patch the wrong tree."
}
if ($branch -ne $ExpectedBranch) {
    Fail "on branch '$branch', expected '$ExpectedBranch'. Refusing to patch the wrong branch."
}

# Dirty tracked files make "the patch is the only change" untrue, and make the
# changed-path check meaningless.
$dirty = @(git status --porcelain "--untracked-files=no" 2>$null)
if ($dirty.Count -gt 0) {
    Write-Host $dirty
    Fail "tracked files are dirty. Commit or stash them first."
}
Write-Host "  tracked tree is clean" -ForegroundColor Green

# The remote must be where we think it is, so the push goes to the reviewed branch.
$remoteHead = (git ls-remote $RemoteName "refs/heads/$ExpectedBranch" 2>$null) -split "\s+"
if (-not $remoteHead -or $remoteHead.Count -lt 1 -or -not $remoteHead[0]) {
    Fail "could not read $RemoteName/$ExpectedBranch from the remote."
}
Write-Host "  remote $RemoteName/$ExpectedBranch : $($remoteHead[0])"
if ($remoteHead[0] -ne $ExpectedHead) {
    Write-Host "  note: the remote is not at HEAD. That is fine if HEAD is a reviewed" -ForegroundColor Yellow
    Write-Host "        candidate you intend to push on top of." -ForegroundColor Yellow
}

Write-Host "== 2. check the patch (read-only) ==" -ForegroundColor Cyan
if (-not (Test-Path $PatchPath)) { Fail "patch not found: $PatchPath" }

# `git apply --check` reads the file directly. There is no redirection here, so it
# is valid in PowerShell 5.1, and it cannot modify the working tree.
& git apply --check --verbose $PatchPath
if ($LASTEXITCODE -ne 0) {
    Fail "the patch does not apply cleanly. Do not force it; inspect the conflict."
}
Write-Host "  the patch applies cleanly (nothing was modified)" -ForegroundColor Green

Write-Host "== 3. preview the diff ==" -ForegroundColor Cyan
# --summary and --stat read the patch itself; they do not touch the tree.
& git apply --stat $PatchPath
& git apply --numstat $PatchPath

# Paths named by the patch, checked against the allow-list before anything runs.
$patchPaths = @()
Select-String -Path $PatchPath -Pattern '^\+\+\+ b/(.+)$' | ForEach-Object {
    $patchPaths += $_.Matches[0].Groups[1].Value.Trim()
}
Write-Host "  paths in the patch: $($patchPaths -join ', ')"
foreach ($path in $patchPaths) {
    if ($AllowedPaths -notcontains $path) {
        Fail "the patch touches '$path', which is not an allowed path."
    }
}
Write-Host "  every path is allowed" -ForegroundColor Green

if (-not $Confirm) {
    Write-Host ""
    Write-Host "Nothing was modified. The patch checks clean and touches only allowed paths." -ForegroundColor Green
    Write-Host "Nothing was committed and nothing was pushed." -ForegroundColor Yellow
    Write-Host "Re-run with -Confirm to apply, commit and push." -ForegroundColor Yellow
    exit 0
}

Write-Host "== 4. apply ==" -ForegroundColor Cyan
& git apply --verbose $PatchPath
if ($LASTEXITCODE -ne 0) { Fail "apply failed after a clean check; investigate before retrying." }

# Verify what actually changed, not what we intended to change.
$changed = @(git status --porcelain "--untracked-files=no" 2>$null | ForEach-Object { $_.Substring(3).Trim() })
Write-Host "  changed: $($changed -join ', ')"
foreach ($path in $changed) {
    if ($AllowedPaths -notcontains $path) {
        Fail "apply changed '$path', which is not allowed. Reverting nothing; inspect the tree."
    }
}
if ($changed.Count -ne $AllowedPaths.Count) {
    Fail "expected $($AllowedPaths.Count) changed paths, found $($changed.Count)."
}
Write-Host "  changed-path set matches exactly" -ForegroundColor Green

Write-Host "== 5. re-parse both workflows ==" -ForegroundColor Cyan
$checkScript = @'
import sys
import yaml

expected = {
    ".github/workflows/experiment-runner-ci.yml": 40,
    ".github/workflows/rh04-dual-run-gate.yml": None,
}
for path, timeout in expected.items():
    with open(path, encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    jobs = list(document["jobs"])
    print("{0}: jobs={1}".format(path, jobs))

with open(".github/workflows/experiment-runner-ci.yml", encoding="utf-8") as handle:
    runner = yaml.safe_load(handle)
observed = runner["jobs"]["synthetic-runner-tests"]["timeout-minutes"]
print("synthetic-runner-tests timeout-minutes = {0}".format(observed))
if observed != 40:
    sys.exit("timeout is {0}, expected 40".format(observed))

with open(".github/workflows/rh04-dual-run-gate.yml", encoding="utf-8") as handle:
    gate = yaml.safe_load(handle)
matrix = gate["jobs"]["dual-run"]["strategy"]["matrix"]
versions = matrix["python-version"]
classes = matrix["dispatch-class"]
print("gate matrix: {0} python versions x {1} dispatch classes = {2} runs".format(
    len(versions), len(classes), len(versions) * len(classes)))
if len(versions) < 2 or len(classes) < 3:
    sys.exit("the gate matrix is too small to be a cross-environment run")
if gate["jobs"]["dual-run"]["timeout-minutes"] != 40:
    sys.exit("the gate timeout is not 40 minutes")
'@

$tempCheck = [System.IO.Path]::GetTempFileName()
try {
    Set-Content -Path $tempCheck -Value $checkScript -Encoding ASCII
    & python $tempCheck
    if ($LASTEXITCODE -ne 0) {
        Fail "a workflow failed to parse, or a value is not what the patch intends. Do not commit."
    }
}
finally {
    Remove-Item -Path $tempCheck -Force -ErrorAction SilentlyContinue
}
Write-Host "  both workflows parse; matrix and timeout are as intended" -ForegroundColor Green

Write-Host "== 6. commit and push ==" -ForegroundColor Cyan
$commitMessage = @"
ci(rh04): raise the synthetic-runner budget to 40 minutes and rebuild the dual-run gate

Authorised by the maintainer for the RH-04 V2 delivery.

The budget change is a reliability fix, not a relaxation. Step 7 measured 15.4,
15.4, 15.9 and 19.9 minutes across four hosted runs of the same command, and needs
22m28s cold locally; at a 20 minute budget a slow runner cancels the step and
Python 3.12 ends up unmeasured. 40 minutes removes that intermittent
non-measurement. No tolerance, retry, skip or continue-on-error is added, and a
genuine test failure still fails the job.

The dual-run gate implements V2-05 with a 4 dispatch class x 2 Python version
matrix: prescott, nehalem, sandybridge and haswell on 3.11 and 3.12, plus an
unforced host-dispatch job on both versions. The previous version ran one default
execution per Python version, which is a single class and therefore does not test
anything cross-environment. Each run reads threadpoolctl after the numerical
libraries are loaded and fails if the resident kernel is not the class it is
recorded under.

Stages: V1 scoped, Lane A regeneration identity and replay evidence, Lane B exact
replay against the fixed digest 891d9e3b, targeted regression including the
negative tests, and security. Every stage runs with if: always() and records its
own exit code, and the aggregate step fails if any mandatory stage failed or
recorded no result at all. Lane A treats training failure, missing evidence and
invalid output as failures, and only numerical divergence as a reportable finding.
Lane B compares exactly, with no numeric tolerance, and records the observed
digest and verdict rather than searching the output for the expected string.
"@

& git add -- $AllowedPaths
if ($LASTEXITCODE -ne 0) { Fail "git add failed." }

& git commit -m $commitMessage
if ($LASTEXITCODE -ne 0) { Fail "commit failed." }

& git push $RemoteName "HEAD:$ExpectedBranch"
if ($LASTEXITCODE -ne 0) {
    Fail "push failed. The workflow scope may still be missing on this credential."
}

Write-Host ""
Write-Host "Pushed to $RemoteName/$ExpectedBranch." -ForegroundColor Green
Write-Host "Read the new run's logs before drawing any conclusion."
Write-Host "Record: every job conclusion, step 7 duration, the Lane A classification"
Write-Host "tally, and the Lane B observed digest and verdict."
Write-Host ""
Write-Host "Then run verify-native-windows.ps1 -Apply for the Windows measurements."
exit 0
