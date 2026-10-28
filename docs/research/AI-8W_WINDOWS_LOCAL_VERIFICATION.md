# AI-8W Windows Local Verification Handoff

**Scope:** Windows/NTFS regression repair for the synthetic UCI-412 AI-8 demo. This is a handoff for the maintainer's native Windows checkout; Linux tests and CI are not evidence of native NTFS ACL behavior. Do not report Windows Local Acceptance complete until the maintainer has run and recorded the checks below on the exact implementation head and again after merge.

## Root cause and correction

The default demo's `tempfile.mkdtemp()` created a temporary root but left its inherited Windows DACL untouched. `Path.mkdir()` then created `trusted_bundles` and `private_keys` as children, inheriting the resulting ACL, including an OWNER RIGHTS (`S-1-3-4`) allow ACE with mask `0x001f01ff`. Strict trusted-root verification correctly rejected that ACE before bundle deserialization. Setting `TEMP`, `TMP`, and `TMPDIR` only selected a different parent: it did not harden the newly created `mkdtemp` root or its subsequently created children, so the inherited ACE was still present.

AI-8W now applies the existing protected Windows DACL utility to automatically created temporary roots and newly created private child directories, then verifies the ACL before key or bundle contents are written. Caller-supplied existing work roots are verified without being rewritten; insecure roots fail closed. OWNER RIGHTS is not whitelisted, ACL verification is unchanged, HMAC verification and pre-deserialization checks remain in place, and no machine-wide security setting is changed. POSIX private modes and the existing trusted-root policy remain supported.

## Preconditions and clean PR-head checkout (before merge)

Run in PowerShell from a separate, clean local clone of `Muhammed-Fathi/CardioAssist-AI`. Substitute the implementation PR number for `PR_NUMBER` below. These commands fetch the pull-request head without checking out or changing the user's local `main` branch.

```powershell
$ErrorActionPreference = 'Stop'
$prNumber = PR_NUMBER

if ((git status --porcelain).Length -ne 0) { throw 'Checkout is not clean.' }
$drive = (Get-Location).Drive.Name
$filesystem = (Get-Volume -DriveLetter $drive).FileSystem
if ($filesystem -ne 'NTFS') { throw "Acceptance requires NTFS; found $filesystem." }

$expectedHead = (gh pr view $prNumber --repo Muhammed-Fathi/CardioAssist-AI --json headRefOid --jq .headRefOid).Trim()
git fetch origin "refs/pull/$prNumber/head"
$fetchedHead = (git rev-parse FETCH_HEAD).Trim()
if ($fetchedHead -ne $expectedHead) { throw "Fetched $fetchedHead, expected PR head $expectedHead." }
git switch --detach $fetchedHead
if ((git rev-parse HEAD).Trim() -ne $expectedHead) { throw 'HEAD does not equal the PR head.' }
if ((git status --porcelain).Length -ne 0) { throw 'PR checkout is not clean.' }

python --version
python -m pytest --version
git rev-parse HEAD
```

Install the repository's pinned test dependencies into the active Python 3.12 environment before test runs:

```powershell
python -m pip install -r research/experiments/requirements.txt
python -m pip install -r research/audit/requirements.txt
python -m pip install -r research/uci412/requirements.txt
python -m pip install -r backend/requirements-dev.txt
python -m pip check
```

Record each command's actual exit code. Do not count a Linux run, a skipped native test, or a successful install as a Windows acceptance pass.

## Default smoke demo (no `--work-dir`)

Run twice without changing `TEMP`, `TMP`, or `TMPDIR`. Both process exit codes must be `0`, both reports must say `12/12 stages succeeded`, and the deterministic report SHA-256 values must match.

```powershell
$default1 = & python -m ai uci412-demo --format text
$defaultExit1 = $LASTEXITCODE
$default1
if ($defaultExit1 -ne 0) { throw "Default smoke run 1 exited $defaultExit1." }
$defaultSha1 = [regex]::Match(($default1 -join "`n"), 'Report SHA-256\s*:\s*([0-9a-f]{64})').Groups[1].Value

$default2 = & python -m ai uci412-demo --format text
$defaultExit2 = $LASTEXITCODE
$default2
if ($defaultExit2 -ne 0) { throw "Default smoke run 2 exited $defaultExit2." }
$defaultSha2 = [regex]::Match(($default2 -join "`n"), 'Report SHA-256\s*:\s*([0-9a-f]{64})').Groups[1].Value
if (-not $defaultSha1 -or $defaultSha1 -ne $defaultSha2) { throw "Default report hashes differ: '$defaultSha1' / '$defaultSha2'." }
"default exit codes: $defaultExit1, $defaultExit2"
"default deterministic report SHA-256: $defaultSha1"
```

## Explicit secured work path and security assertions

Use a fresh, user-local NTFS directory and secure it with the repository utility before passing it to the CLI. Save CLI JSON outside the repository; the application output itself must not disclose the path. Check authenticated bundle status and genuine malformed-input rejection from the actual report.

```powershell
$workRoot = Join-Path $env:LOCALAPPDATA ("CardioAssistAI\AI8W-" + [guid]::NewGuid().ToString('N'))
python -c "from pathlib import Path; from ai.filesystem_security import ensure_private_directory; ensure_private_directory(Path(r'$workRoot'))"
if ($LASTEXITCODE -ne 0) { throw "Could not secure explicit work root (exit $LASTEXITCODE)." }

$explicitOutput = & python -m ai uci412-demo --work-dir $workRoot --format json
$explicitExit = $LASTEXITCODE
if ($explicitExit -ne 0) { $explicitOutput; throw "Explicit-path demo exited $explicitExit." }
$report = ($explicitOutput -join "`n") | ConvertFrom-Json
$bundle = $report.stage_results | Where-Object stage -eq '10_bundle_verification' | Select-Object -ExpandProperty detail
if ($bundle.producer_authenticated -ne $true -or $bundle.safe_for_pickle_deserialization -ne $true -or $bundle.attestation_scheme -ne 'hmac-sha256-local-producer-v1') { throw 'Bundle HMAC authentication / trusted pre-deserialization verification did not pass.' }
if ($report.invalid_input_demo.rejected -ne $true -or $report.invalid_input_demo.error_code -ne 'uci412_synthetic_context_rejected') { throw 'The genuine malformed-input validator rejection did not pass.' }
if (($explicitOutput -join "`n").Contains($workRoot)) { throw 'CLI output disclosed the explicit local path.' }
"explicit-path exit code: $explicitExit"
"bundle authentication: PASS; invalid-input rejection: PASS"
```

The test suite additionally checks tampered bundle rejection before deserialization, symlink/reparse rejection, foreign-owner and unauthorized-ACE policy, and insecure existing-root rejection. Run the native inherited OWNER RIGHTS regression explicitly; on Windows/NTFS it must execute, not skip:

```powershell
python -m pytest -W error tests/experiments/test_private_directory_creation_regression.py tests/experiments/test_ai_research_pipeline.py::test_native_windows_sddl_conversion_weakened_directory_rejection_and_restoration
$nativeExit = $LASTEXITCODE
"native Windows ACL regression exit code: $nativeExit"
if ($nativeExit -ne 0) { throw 'Native Windows ACL regression failed.' }
```

## Targeted and complete repository test suites

The targeted AI-8 suite is expected to collect 98 tests on this head. Run exactly with warnings treated as errors, then the complete applicable repository suite:

```powershell
python -m pytest -W error tests/experiments/test_uci412_demo.py tests/experiments/test_uci412_research_model.py
$targetedExit = $LASTEXITCODE
"targeted AI-8 test exit code: $targetedExit"
if ($targetedExit -ne 0) { throw 'Targeted AI-8 suite failed.' }

python -m pytest -W error
$fullExit = $LASTEXITCODE
"complete repository test exit code: $fullExit"
if ($fullExit -ne 0) { throw 'Complete repository suite failed.' }

python -m pip check
$dependencyExit = $LASTEXITCODE
python scripts/verify_sources.py
$sourceExit = $LASTEXITCODE
"dependency check exit code: $dependencyExit; source verification exit code: $sourceExit"
if ($dependencyExit -ne 0 -or $sourceExit -ne 0) { throw 'Dependency/source verification failed.' }
```

Keep the raw pytest summaries. Record exact collected/pass/fail/error/skip counts, both smoke exit codes and hashes, explicit-path exit code, native ACL-test result (including whether it executed), dependency/source-check exit codes, Python/pytest versions, NTFS volume, and tested commit SHA. If any command fails or the native test skips, Windows Local Acceptance remains **NOT COMPLETE**.

## Repeat after merge

After independent review and merge, update the local `main`, verify it is clean, and record the merged SHA. Reinstall/check the pinned dependencies if the environment changed, then repeat the default demo twice, the secured explicit-path assertions, native ACL regression, targeted 98 tests, full `pytest -W error`, `pip check`, and source verification above against this merged checkout.

```powershell
git switch main
git pull --ff-only origin main
if ((git status --porcelain).Length -ne 0) { throw 'Updated main is not clean.' }
$mergedHead = (git rev-parse HEAD).Trim()
"post-merge main SHA: $mergedHead"
```

The merged-head checks are required; pre-merge PR-head results alone do not close the Windows acceptance requirement. Do not claim acceptance until the maintainer has recorded successful native results for both SHAs.
