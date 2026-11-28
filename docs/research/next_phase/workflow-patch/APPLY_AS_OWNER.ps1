<#
    RH-04 V2 - owner-applied CI patch. PowerShell 5.1 compatible.

    The Arena integration has no `workflows` scope, so it cannot push workflow
    changes: pushes touching .github/workflows are rejected. This script is
    therefore run by the owner, who has that scope.

    CORRECTIONS IN THIS VERSION
      * `git status --porcelain --untracked-files=no` is gone from the
        post-apply check. Verification uses the staged diff
        (`git diff --cached --name-only`), which is authoritative for what is about
        to be committed.
      * The patch now MODIFIES the installed gate rather than creating it, so it
        touches one path and the allowance list matches. Both `--untracked-files=no`
        and the staged diff report that one path, and the script asserts the exact
        set rather than only a minimum.
      * The remote HEAD must MATCH. Previously a mismatch printed a warning and
        continued, so the script would happily commit on top of a remote it had
        never verified.
      * No PyYAML requirement. Workflow validation uses a small structural check
        written in Python's standard library only, so nothing undeclared has to be
        installed on the owner's machine. If PyYAML happens to be present it is
        used as an additional check, never as a requirement.
      * The apply is transactional: if any verification fails after applying, the
        patch is reversed and the tree is returned to its pre-run state.

    PREVIEW IS READ-ONLY. Without -Confirm the script runs only read-only git
    commands and changes nothing.

    Usage, from the repository root. Preview first:
        powershell -ExecutionPolicy Bypass -File .\APPLY_AS_OWNER.ps1 `
            -ExpectedHead <candidate-sha>

    Then apply:
        powershell -ExecutionPolicy Bypass -File .\APPLY_AS_OWNER.ps1 `
            -ExpectedHead <candidate-sha> -Confirm
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

# The only paths this patch may touch, exactly.
#
# Round 18's patch created the gate and bumped the runner timeout, so it touched two
# paths. The gate was installed by the maintainer at 73d9f9d -- and immediately
# failed -- so the round-19 patch MODIFIES the installed gate and touches one path.
# `experiment-runner-ci.yml` is already at 40 minutes and is no longer part of the
# patch. This list must match the patch exactly; the assertion below enforces that.
$AllowedPaths = @(
    ".github/workflows/rh04-dual-run-gate.yml"
)

function Fail([string]$Message) {
    Write-Host ""
    Write-Host "FAILED: $Message" -ForegroundColor Red
    exit 1
}

function Remove-CreatedGateFile {
    # The gate is now a TRACKED file, so `git apply --reverse` restores it and
    # removing it would destroy the owner's installed workflow. This refuses to
    # touch a tracked file and only cleans up if the patch genuinely created an
    # untracked one, which is the round-18 shape and may still be seen if the owner
    # applies this patch to a pre-install checkout.
    $gate = ".github/workflows/rh04-dual-run-gate.yml"
    if (-not (Test-Path $gate)) { return }
    $tracked = & git ls-files --error-unmatch $gate 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  the gate file is tracked; left in place (reverse apply restored it)" -ForegroundColor Green
        return
    }
    Remove-Item -Path $gate -Force
    Write-Host "  removed the untracked gate file this script created" -ForegroundColor Green
}

function Restore-PatchPaths {
    <#
        Transactional rollback. Restores BOTH the index and the working tree for
        exactly the patch's paths, and nothing else.

        P0-04: the previous implementation ran `git apply --reverse` alone. Once
        `git add` had staged the change, reversing the working tree left the STALE
        modification in the index and added a second, unstaged reversal on top --
        `git status` then showed `MM` and the checkout was NOT as it was found. A
        --reverse after staging cannot restore a staged change: the index is a
        separate state and has to be reset explicitly.

        Order matters and is deliberate:

          1. `git reset` the paths, which un-stages them back to HEAD. Without this
             the index keeps the patch.
          2. `git checkout --` the paths, which restores the working tree from the
             now-clean index.
          3. Only remove an untracked gate file if the patch genuinely CREATED it,
             never a tracked one.

        `git reset` here is a pathspec reset, not `--hard` and not a branch reset:
        it touches only the named paths and cannot discard unrelated work.
    #>
    param([string[]]$Paths)

    Write-Host "Rolling the patch back so the checkout is left as it was found." -ForegroundColor Yellow

    $restored = $true

    # 1. Un-stage exactly the patch's paths.
    & git reset --quiet HEAD -- @Paths 2>$null
    if ($LASTEXITCODE -ne 0) { $restored = $false }

    # 2. Restore the working tree for exactly those paths.
    & git checkout --quiet -- @Paths 2>$null
    if ($LASTEXITCODE -ne 0) { $restored = $false }

    # 3. Clean up only a file this script created.
    Remove-CreatedGateFile

    # 4. Verify, rather than assume. If anything is still dirty, say so loudly:
    #    a rollback that reports success while leaving a dirty tree is worse than
    #    one that reports failure.
    $residual = @(& git status --porcelain -- @Paths 2>$null | Where-Object { $_ })
    if ($residual.Count -gt 0) { $restored = $false }

    if ($restored) {
        Write-Host "  rolled back; index and working tree are clean for the patched paths" -ForegroundColor Green
        & git status --porcelain -- @Paths
    }
    else {
        Write-Host "  AUTOMATIC ROLLBACK FAILED. The checkout is NOT clean." -ForegroundColor Red
        Write-Host "  Residual state:" -ForegroundColor Red
        & git status --porcelain
        Write-Host "  Restore manually before retrying: git reset HEAD -- <paths>; git checkout -- <paths>" -ForegroundColor Yellow
    }
    return $restored
}

function Stop-WithRollback([string]$Message, [bool]$Applied) {
    Write-Host ""
    Write-Host "FAILED: $Message" -ForegroundColor Red
    if ($Applied) {
        $ok = Restore-PatchPaths -Paths $AllowedPaths
        if (-not $ok) { exit 2 }
    }
    else {
        Remove-CreatedGateFile
    }
    exit 1
}

Write-Host "== 1. verify checkout identity ==" -ForegroundColor Cyan

if (-not (Test-Path ".git")) {
    Fail "not a git checkout, or not run from the repository root."
}

& git rev-parse --git-dir | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "git is not usable in this directory." }

$head = (& git rev-parse HEAD).Trim()
$branch = (& git rev-parse --abbrev-ref HEAD).Trim()

Write-Host ("  HEAD     : {0}" -f $head)
Write-Host ("  expected : {0}" -f $ExpectedHead)
Write-Host ("  branch   : {0}" -f $branch)
Write-Host ("  expected : {0}" -f $ExpectedBranch)

if ($head -ne $ExpectedHead) {
    Fail "checkout is $head, expected $ExpectedHead. Refusing to patch the wrong tree."
}
if ($branch -ne $ExpectedBranch) {
    Fail "on branch '$branch', expected '$ExpectedBranch'. Refusing to patch the wrong branch."
}

# The tracked tree must be clean AND there must be no untracked files that could be
# mistaken for part of this patch.
$dirty = @(& git status --porcelain)
if ($dirty.Count -gt 0) {
    Write-Host $dirty
    Fail "the working tree is not clean. Commit, stash or remove these first."
}
Write-Host "  working tree is clean, including untracked files" -ForegroundColor Green

# The remote must be exactly at the reviewed commit. A mismatch is fatal, not a note:
# committing on top of an unverified remote is how an unreviewed change gets included.
$remoteLine = & git ls-remote $RemoteName ("refs/heads/{0}" -f $ExpectedBranch) 2>$null
if ($LASTEXITCODE -ne 0 -or -not $remoteLine) {
    Fail ("could not read {0}/{1} from the remote." -f $RemoteName, $ExpectedBranch)
}
$remoteHead = ($remoteLine -split "\s+")[0]
Write-Host ("  remote {0}/{1} : {2}" -f $RemoteName, $ExpectedBranch, $remoteHead)
if ($remoteHead -ne $ExpectedHead) {
    Fail ("the remote is at {0}, expected {1}. Fetch and re-check out before applying; a patch applied on top of an unverified remote cannot be reviewed." -f $remoteHead, $ExpectedHead)
}
Write-Host "  remote HEAD matches the reviewed commit" -ForegroundColor Green

Write-Host "== 2. check the patch (read-only) ==" -ForegroundColor Cyan

if (-not (Test-Path $PatchPath)) { Fail ("patch not found: {0}" -f $PatchPath) }

& git apply --check --verbose $PatchPath
if ($LASTEXITCODE -ne 0) {
    Fail "the patch does not apply cleanly. Do not force it; inspect the conflict."
}
Write-Host "  the patch applies cleanly (nothing was modified)" -ForegroundColor Green

Write-Host "== 3. preview ==" -ForegroundColor Cyan

& git apply --stat $PatchPath
& git apply --numstat $PatchPath

$patchPaths = @()
Select-String -Path $PatchPath -Pattern '^\+\+\+ b/(.+)$' | ForEach-Object {
    $patchPaths += $_.Matches[0].Groups[1].Value.Trim()
}
Write-Host ("  paths in the patch: {0}" -f ($patchPaths -join ", "))
foreach ($path in $patchPaths) {
    if ($AllowedPaths -notcontains $path) {
        Fail ("the patch touches '{0}', which is not an allowed path." -f $path)
    }
}
if ($patchPaths.Count -ne $AllowedPaths.Count) {
    Fail ("the patch touches {0} paths, expected {1}." -f $patchPaths.Count, $AllowedPaths.Count)
}
Write-Host "  every path is allowed and all expected paths are present" -ForegroundColor Green

if (-not $Confirm) {
    Write-Host ""
    Write-Host "Nothing was modified. The patch checks clean and touches only allowed paths." -ForegroundColor Green
    Write-Host "Re-run with -Confirm to apply, verify, commit and push." -ForegroundColor Yellow
    exit 0
}

Write-Host "== 4. apply ==" -ForegroundColor Cyan

& git apply --verbose $PatchPath
if ($LASTEXITCODE -ne 0) { Stop-WithRollback "apply failed after a clean check; investigate before retrying." $false }

# Stage first, then verify the STAGED set. `git status` with untracked files excluded
# is what broke the previous version; the index is the right source of truth because
# it is exactly what the commit will contain, and it includes added files.
& git add -- $AllowedPaths
if ($LASTEXITCODE -ne 0) { Stop-WithRollback "git add failed." $true }

$staged = @(& git diff --cached --name-only)
Write-Host ("  staged: {0}" -f ($staged -join ", "))
if ($staged.Count -ne $AllowedPaths.Count) {
    Stop-WithRollback ("expected {0} staged paths, found {1}." -f $AllowedPaths.Count, $staged.Count) $true
}
foreach ($path in $staged) {
    if ($AllowedPaths -notcontains $path) {
        Stop-WithRollback ("apply changed '{0}', which is not allowed." -f $path) $true
    }
}
foreach ($path in $AllowedPaths) {
    if ($staged -notcontains $path) {
        Stop-WithRollback ("expected path '{0}' was not staged." -f $path) $true
    }
}
Write-Host "  staged-path set matches exactly, including the newly added workflow" -ForegroundColor Green

# Nothing outside the allow-list may be modified in the working tree either.
$trackedChanges = @(& git diff --name-only)
foreach ($path in $trackedChanges) {
    if ($AllowedPaths -notcontains $path) {
        Stop-WithRollback ("the working tree changed '{0}', which is not allowed." -f $path) $true
    }
}
Write-Host "  no changes outside the allowed paths" -ForegroundColor Green

Write-Host "== 5. structural validation (no PyYAML required) ==" -ForegroundColor Cyan

# Standard library only. PyYAML is not a declared dependency of this repository's
# application requirements, so requiring it here would fail on a clean owner machine.
$checkScript = @'
import sys

REQUIRED_JOBS = {
    ".github/workflows/experiment-runner-ci.yml": ["synthetic-runner-tests"],
    ".github/workflows/rh04-dual-run-gate.yml": ["dual-run", "host-dispatch"],
}

def check_structure(path, jobs):
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()
    problems = []
    if "\t" in text:
        problems.append("contains a tab character, which YAML forbids for indentation")
    lines = text.splitlines()
    if not lines or not lines[0].startswith("name:"):
        problems.append("does not begin with a name: key")
    for job in jobs:
        if ("  " + job + ":") not in text:
            problems.append("job definition not found: " + job)
    for marker in ("on:", "jobs:", "permissions:"):
        if marker not in text:
            problems.append("missing top-level key: " + marker)
    return problems

def check_values():
    problems = []
    with open(".github/workflows/experiment-runner-ci.yml", "r", encoding="utf-8") as handle:
        runner = handle.read()
    if "timeout-minutes: 40" not in runner:
        problems.append("experiment-runner-ci.yml does not carry timeout-minutes: 40")
    with open(".github/workflows/rh04-dual-run-gate.yml", "r", encoding="utf-8") as handle:
        gate = handle.read()
    for needle in ("'3.11', '3.12'", "prescott", "nehalem", "sandybridge", "haswell"):
        if needle not in gate:
            problems.append("gate matrix is missing: " + needle)
    if gate.count("timeout-minutes: 40") < 1:
        problems.append("the gate does not carry a 40 minute timeout")
    if "891d9e3b2a332c6efc251d97fee25ed46a627ed25b2a089594057b4c9896cdc8" not in gate:
        problems.append("the gate does not pin the Lane B reference digest")
    return problems

failed = 0
for path, jobs in REQUIRED_JOBS.items():
    found = check_structure(path, jobs)
    if found:
        failed = 1
        print("STRUCTURE PROBLEM {0}: {1}".format(path, found))
    else:
        print("structure OK: {0}".format(path))

value_problems = check_values()
if value_problems:
    failed = 1
    print("VALUE PROBLEM: {0}".format(value_problems))
else:
    print("timeout is 40 in both workflows; gate matrix and digest are present")

# If PyYAML happens to be installed, use it as an additional parse. Never required.
try:
    import yaml
except ImportError:
    print("note: PyYAML not installed; the structural checks above ran without it")
else:
    for path in REQUIRED_JOBS:
        with open(path, "r", encoding="utf-8") as handle:
            document = yaml.safe_load(handle)
        print("yaml parse OK: {0} jobs={1}".format(path, list(document["jobs"])))
    with open(".github/workflows/rh04-dual-run-gate.yml", "r", encoding="utf-8") as handle:
        gate_document = yaml.safe_load(handle)
    matrix = gate_document["jobs"]["dual-run"]["strategy"]["matrix"]
    combinations = len(matrix["python-version"]) * len(matrix["dispatch-class"])
    print("gate matrix: {0} combinations".format(combinations))
    if combinations < 6:
        failed = 1
        print("VALUE PROBLEM: the gate matrix is smaller than 3 classes x 2 versions")

sys.exit(failed)
'@

$tempCheck = [System.IO.Path]::GetTempFileName()
try {
    Set-Content -Path $tempCheck -Value $checkScript -Encoding ASCII
    & python $tempCheck
    if ($LASTEXITCODE -ne 0) {
        Stop-WithRollback "workflow validation failed. Do not commit." $true
    }
}
finally {
    Remove-Item -Path $tempCheck -Force -ErrorAction SilentlyContinue
}
Write-Host "  both workflows validate structurally; values are as intended" -ForegroundColor Green

Write-Host "== 6. commit and push ==" -ForegroundColor Cyan

$commitMessage = @"
ci(rh04): correct the dual-run gate's Lane A validity and stage logic

Authorised by the maintainer for the RH-04 V2 delivery.

SCOPE: this patch MODIFIES ONE ALREADY-INSTALLED FILE,
.github/workflows/rh04-dual-run-gate.yml. It does not add a workflow and it does
not touch the synthetic-runner budget. Both were already done by the maintainer at
73d9f9d, and an earlier version of this message claimed otherwise because the patch
was built before that install. The gate at 73d9f9d ran and failed; this corrects it.

WHAT WAS WRONG. The gate required Lane A parameters to be bit-for-bit equal to the
frozen archive. That holds only on the host that produced the archive: a different
BLAS kernel reassociates L-BFGS and moves the fit by 1-2 ulp, so all eight forced
dispatch jobs failed. CAI-RH04-AMEND-v3 already classified a converged regeneration
with differing parameters as a diagnostic finding, so the workflow contradicted the
document it implements.

Stage 2 now reads the module's validity verdict instead of re-deriving one from a
bit-equality proxy, and prints measured differences as findings. Stage 6 read a key
that never existed (run1_digests; Stage 2 writes identities_run1) and raised
KeyError in all eight jobs. Stage 4's filter was too narrow -- five families -- and
never selected the v2_04a validity tests, so the stage whose job is to catch a broken
validity predicate could not execute it. The filter now names the families it must
cover. At 07167b0 that selects 61 of 315 tests, up from 37; after the P0 corrections
in the same series it selects 67 of 334.

Read the selection by name, not by count: a count alone cannot tell you WHICH
families are covered, and this number moves whenever a test is added.

WHAT IS NOT CHANGED. Lane B still compares the observed digest to the fixed value
891d9e3b as a value rather than searching output for a string. The 4 dispatch class
x 2 Python version matrix is unchanged. Every stage still runs with if: always(),
records its own exit code, and the aggregate still fails if any mandatory stage
failed or recorded no result at all. No tolerance, retry, skip or
continue-on-error is added.

EXPECTED RESULT AFTER THIS PATCH: Stage 1 (V1) still exits 1. That failure is real,
is retained on purpose, and is NOT fixed here; V1 retirement is a separate owner
decision. Stages 2-6 should exit 0, and the aggregate should fail on Stage 1 alone.
"@

& git commit -m $commitMessage
if ($LASTEXITCODE -ne 0) { Fail "commit failed. The staged changes are still staged; inspect them." }

& git push $RemoteName ("HEAD:{0}" -f $ExpectedBranch)
if ($LASTEXITCODE -ne 0) {
    Fail "push failed. The workflow scope may still be missing on this credential."
}

$newHead = (& git rev-parse HEAD).Trim()
Write-Host ""
Write-Host ("Pushed {0} to {1}/{2}." -f $newHead, $RemoteName, $ExpectedBranch) -ForegroundColor Green
Write-Host "Read the new run's logs before drawing any conclusion."
Write-Host "Record: every job conclusion, the resident dispatch classes, the Lane A"
Write-Host "regeneration identities, and the Lane B observed digest and verdict."
exit 0
