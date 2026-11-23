<#
    RH-04 V2 — owner-applied CI patch.

    The Arena integration has no `workflows` scope, so it cannot push workflow
    changes: pushes touching .github/workflows are rejected and workflow_dispatch
    returns 403. This script is therefore run by the owner, who has that scope.

    What it does, in order:
      1. verifies the checkout is the expected delivery SHA;
      2. validates the patch with --dry-run before touching anything;
      3. applies it;
      4. re-parses both workflow files as YAML to catch a malformed apply;
      5. shows the resulting diff for review;
      6. commits and pushes only on explicit confirmation.

    Nothing is committed or pushed without -Confirm:$true.

    Usage, from the repository root:
        powershell -ExecutionPolicy Bypass -File APPLY_AS_OWNER.ps1 `
            -ExpectedHead 9c94e0c83cd2958c775500d1ed592a9071d7e32e `
            -Confirm:$true
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ExpectedHead,
    [string]$PatchPath = "docs/research/next_phase/workflow-patch/rh04-ci-consolidated.patch",
    [switch]$Confirm
)

$ErrorActionPreference = "Stop"

function Fail([string]$Message) {
    Write-Host ""
    Write-Host "FAILED: $Message" -ForegroundColor Red
    exit 1
}

Write-Host "== 1. verify checkout ==" -ForegroundColor Cyan
$head = (git rev-parse HEAD).Trim()
Write-Host "  HEAD     : $head"
Write-Host "  expected : $ExpectedHead"
if ($head -ne $ExpectedHead) {
    Fail "checkout is $head, expected $ExpectedHead. Refusing to patch the wrong tree."
}
if (git status --porcelain) {
    Fail "working tree is dirty. Commit or stash first, so the patch is the only change."
}

Write-Host "== 2. validate the patch ==" -ForegroundColor Cyan
if (-not (Test-Path $PatchPath)) { Fail "patch not found: $PatchPath" }
patch --dry-run -p1 < $PatchPath
if ($LASTEXITCODE -ne 0) {
    Fail "patch does not apply cleanly. Do not force it; inspect the conflict."
}
Write-Host "  dry-run clean" -ForegroundColor Green

Write-Host "== 3. apply ==" -ForegroundColor Cyan
patch -p1 < $PatchPath
if ($LASTEXITCODE -ne 0) { Fail "apply failed after a clean dry-run; investigate before retrying." }

Write-Host "== 4. re-parse both workflows ==" -ForegroundColor Cyan
python -c @"
import sys, yaml
for path in ('.github/workflows/experiment-runner-ci.yml',
             '.github/workflows/rh04-dual-run-gate.yml'):
    with open(path, encoding='utf-8') as handle:
        document = yaml.safe_load(handle)
    jobs = list(document['jobs'])
    print(f'{path}: jobs={jobs}')
bumped = yaml.safe_load(open('.github/workflows/experiment-runner-ci.yml', encoding='utf-8'))
timeout = bumped['jobs']['synthetic-runner-tests']['timeout-minutes']
print(f'synthetic-runner-tests timeout-minutes = {timeout}')
if timeout != 40:
    sys.exit(f'timeout is {timeout}, expected 40')
"@
if ($LASTEXITCODE -ne 0) { Fail "a workflow failed to parse, or the timeout is not 40. Do not commit." }
Write-Host "  both workflows parse; timeout is 40" -ForegroundColor Green

Write-Host "== 5. review the diff ==" -ForegroundColor Cyan
git --no-pager diff --stat
git --no-pager diff

if (-not $Confirm) {
    Write-Host ""
    Write-Host "Patch applied to the working tree but NOT committed." -ForegroundColor Yellow
    Write-Host "Nothing was pushed."
    Write-Host "Re-run with -Confirm:`$true to commit and push." -ForegroundColor Yellow
    exit 0
}

Write-Host "== 6. commit and push ==" -ForegroundColor Cyan
git add .github/workflows/experiment-runner-ci.yml .github/workflows/rh04-dual-run-gate.yml
git commit -m @"
ci(rh04): raise the synthetic-runner budget to 40 minutes and add the dual-run gate

Authorised by the maintainer for the RH-04 V2 delivery.

The budget change is a reliability fix, not a relaxation. Step 7 measured 15.4,
15.4, 15.9 and 19.9 minutes across four hosted runs of the same command, and needs
22m28s cold locally; at a 20 minute budget a slow runner cancels the step and
Python 3.12 ends up unmeasured. 40 minutes removes that intermittent
non-measurement. No tolerance, retry, skip or continue-on-error is added, and a
genuine test failure still fails the job.

The new dual-run gate implements V2-05. Stage 1 (V1 scoped), stage 2 (Lane A
classified), stage 3 (Lane B exact) and stage 4 (security and regression) each run
with if: always() and record their own exit code, so every stage publishes a result
even when another fails. A final gate step reads the codes and fails if any
mandatory stage failed; a stage that did not report at all is also a failure.
Lane A treats training failure, missing evidence and invalid output as failures and
only numerical divergence as a reportable finding. Lane B compares exactly against
891d9e3b with no numeric tolerance.
"@
if ($LASTEXITCODE -ne 0) { Fail "commit failed." }

git push origin delivery/rh04-v2-final
if ($LASTEXITCODE -ne 0) { Fail "push failed. The workflow scope may still be missing." }

Write-Host ""
Write-Host "Pushed. Read the new run's logs before drawing any conclusion." -ForegroundColor Green
Write-Host "Record: job conclusions, step 7 duration, Lane A residuals, Lane B digest."
exit 0
