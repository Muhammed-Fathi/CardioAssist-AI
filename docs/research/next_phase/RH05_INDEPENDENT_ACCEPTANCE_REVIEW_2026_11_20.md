# RH-05 — Independent synthetic reproducibility and security acceptance review

**Version:** 2026-11-20 / v1 (review draft)  
**Disposition:** ENGINEERING EVIDENCE COLLECTED; **MAINTAINER ACCEPTANCE / ISSUE CLOSEOUT PENDING**  
**Release/test SHA:** `64f34e4cb8580ced461237ffa46ba0a91e8fc1c5` (merged PR #123)  
**Evidence scope:** Synthetic-only offline research and `MOCK_SYNTHETIC` isolation. **Not clinical validity, real-data model approval, real external cohort validation, serving authorization, or sign-off on RH-03/RH-06/RH-07/RH-08.**

This document reconciles directly observed GitHub evidence with **maintainer-reported Windows terminal results**. A private complete Windows transcript was retained by the maintainer outside the repository; that transcript was **not independently ingested or authenticated** here. Never commit private logs, datasets, keys, bundles, patient records, or local paths to this PR.

## Provenance and version boundary

| Item | Evidence | Disposition |
| --- | --- | --- |
| Current baseline | GitHub `main` at `64f34e4cb8580ced461237ffa46ba0a91e8fc1c5` (PR [#123](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/123), merged) | Verified GitHub ref |
| Linux/Windows **exact-commit** comparison | Both packs generated at `09b895423171eff7569fc49dd8ceac7dfb0d43c6` (post-PR #122 main) | Compared; `MATCH` within documented fixture semantics |
| Unchanged implementation between those SHAs | `ai` tree `59b5a3b8a36dbee5f49564d0c3d6c7f9f377d30f`; `research` tree `b5dedcfc6c4048c650cd8949da273f1c1d3ac597`; `tests` tree `b229cb84e0e2011459f6a3edbf0f4e23d50750be` at **both** SHAs | GitHub tree-object inspection; PR #123 added workflow infrastructure |
| CI | [PR #123](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/123) head `0d179b6373e60d9217b94f28ff38b92a4641185f`: **8/8** GitHub check runs successful | CI is for PR head, **not falsely relabeled as a main-merge-SHA CI run** |
| Windows final test | Native Windows 3.12.9 on NTFS E: detached clean worktree at `64f34e4...` | Maintainer-reported console evidence |

This distinction matters: the cross-OS packs share an *exact* `09b8954...` Git commit, while the final Windows full-suite result is from `64f34e4...`. The reviewed `ai` / `research` / `tests` Git trees are identical across these two versions. Do **not** assert that the cross-OS packs were themselves generated at `64f34e4...`.

## RH-05 acceptance matrix

| Requirement | Verification / evidence | Result |
| --- | --- | --- |
| Native Windows Python, NTFS security and eight-stage pipeline | `python scripts/validate_ai_windows_compat.py` at final SHA; `os_name=nt`, `platform=win32`, Python **3.12.9**, `windows_ntfs_win32_security_descriptor_dacl`, eight named stages | **PASS**, 8/8, reported |
| Inherited OWNER RIGHTS SDDL/ACL refusal | Previous `test_native_windows_sddl_conversion_weakened_directory_rejection_and_restoration` **1 passed** on `09b8954...`; on final SHA native Windows `test_inherited_owner_rights_ace_is_removed_before_private_children_are_used` was selected in 220-test focused suite (Windows-only skip condition is false), while complete Windows suite also passed | **PASS** (two independent relevant controls, separate run SHA noted) |
| Source integrity and clean checkout | Four archived original file SHA-256 checks; 25-paper review classes (green 9, pink 1, orange 6, red 9); `git diff --check`; clean detached worktree | **PASS**, reported |
| Pinned Python environment | `python -m pip check`: “No broken requirements found.” | **PASS**, reported on final SHA |
| Research/refusal focused suites | Eight named Python test modules: `test_private_directory_creation_regression`, `test_research_facade`, `test_offline_fixture_pack`, `test_diagnose_fixture_replay`, `test_rh04_report_assembly`, `test_ai9_paired_synthetic`, `test_ai10_synthetic_transport`, `test_offline_research_boundary` | **220 passed, 2 skipped, 0 failed**, 100.41s, final SHA |
| Five routes, 29 actual synthetic cases, four statuses | Existing `tests/experiments/test_rh04_report_assembly.py::test_real_synthetic_run_manifest_covers_all_routes_statuses_and_ledger` runs actual 29-case replay; `test_offline_fixture_pack.py` covers negative paths. Tests included in successful focused and full runs | **PASS** for tested synthetic fixture scope |
| Fresh one-shot ledger and negative evidence | `test_rh04_report_assembly.py` module fixture calls `rh.assemble` with unique pytest temp ledger outside checkout; validates consumed-once, wrong plan, overlap, insufficient evidence, redacted aggregate and checksum; `test_ai10_synthetic_transport.py` checks ledger re-use and refusal | **PASS** for synthetic rehearsal; not actual external-site test |
| Strict Linux/Windows synthetic comparison | GitHub Actions [run 44745390366](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/44745390366) successful at **checked-out** `09b8954...` (not its workflow-trigger `64f34e4...`); original Windows evidence from same checked-out SHA; reviewed `ai.report_comparison` classification | **MATCH** for synthetic fixture behavior, 0 unsupported differences |
| Final full native Windows tests | `python -m pytest -W error -q -ra --tb=short` | **2909 passed, 3 skipped, 0 failed**, 4541.09s = 1:15:41; reported on final SHA |
| Final Windows gate & source check | `scripts/verify_sources.py`, `git diff --check` and worktree-clean checks in test wrapper | **RH05 FINAL WINDOWS TEST GATE: PASS** (reported) |

### Skip accounting — final full suite (not silently marked passed)

1. `tests/experiments/test_private_directory_creation_regression.py:30` — POSIX permission mode case skipped on Windows; native NTFS ACL preservation tested separately.
2. `tests/experiments/test_private_directory_creation_regression.py:47` — POSIX inherited ACL demonstration skipped on Windows; native NTFS inherited ACL refusal tested separately.
3. `tests/experiments/test_research_routes.py:556` — POSIX insecure ACL scenario skipped on Windows; native Windows insecure ACL refusal covered separately.

Native Windows OWNER RIGHTS test at `test_private_directory_creation_regression.py:76` **was not one of these skips**. Do not treat this count as 2912 passed.

### Exact-commit cross-OS comparison details

- **Linux** checked-out SHA `09b895423171eff7569fc49dd8ceac7dfb0d43c6`, artifact [`rh05-linux-evidence-44745390366-1`](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/44745390366), Actions artifact ID `14632901370` (14-day retention, expires 2026-12-04).
- Linux canonical evidence pack digest `c5adcc71f2c88e190d9a0852b601d24f050e56e0f9b5098f0387cab1c871292c`.
- **Windows** original canonical pack digest `47107096edd943982642a1a21137319029132cce1f05164c739aaf09c88e432e`, kept outside the repo by maintainer.
- Both packs' full commit and `ai` / `research` trees match; generated pack, legacy 8-stage digest and redacted inference preimage digest were independently validated before comparison.
- With unchanged `ai/report_comparison.py` thresholds `abs_tol=1e-12` and `rel_tol=1e-9`: **53** `within_tolerance`, **8** `environment`, **4** `artifact_bytes`, **3** `derived_digest`, **0** `invariant_mismatch` or `outside_tolerance` (68 recorded differences). Thus `fixture_behavior=MATCH`. The two example raw and calibrated scores matched exactly.
- **No byte identity assertion:** `artifact_member_hashes_equal` is false; different `.joblib` and numerical-derivative artifact bytes remain explicit. Fixture behavior MATCH is not model binary equivalence or clinical validity.

An older historical Linux reference at `b287713...` generated two strict source-tree mismatches against updated Windows code; that earlier full comparison was **DIFFERENT**, correctly. It was superseded only for *same-source synthetic* comparison by the new independent exact-SHA pair; archived evidence remains unchanged.

## Independent reproduction (Windows PowerShell 5.1)

Use a **fresh detached** NTFS worktree; do not overwrite an existing test checkout, edit inherited ACLs, reuse a consumed one-shot ledger, or write output into the repo. This is synthetic-only; no real datasets.

```powershell
$ErrorActionPreference = 'Stop'
$Sha = '64f34e4cb8580ced461237ffa46ba0a91e8fc1c5'
$Source = 'E:\CardioAssist_AI_GitHub_Starter'  # maintainer's existing clone
$Work = 'E:\CAI_RH05_CHECK_' + [guid]::NewGuid().ToString('N').Substring(0,8)
git -C $Source fetch origin main
if ($LASTEXITCODE -ne 0 -or (git -C $Source rev-parse origin/main).Trim() -ne $Sha) { throw 'Source mismatch: inspect before proceeding' }
git -C $Source worktree add --detach $Work $Sha
if ($LASTEXITCODE -ne 0) { throw 'Worktree failed' }
Set-Location $Work

$Venv = Join-Path $env:LOCALAPPDATA ('CAI-RH05-PY-' + [guid]::NewGuid().ToString('N').Substring(0,8))
py -3.12 -m venv $Venv
if ($LASTEXITCODE -ne 0) { throw 'Python venv failed' }
$Python = Join-Path $Venv 'Scripts\python.exe'
& $Python -m pip install -r research/uci412/requirements.txt -r backend/requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw 'Pinned dependencies installation failed' }
& $Python -m pip check
if ($LASTEXITCODE -ne 0) { throw 'pip check failed' }
& $Python scripts/validate_ai_windows_compat.py
if ($LASTEXITCODE -ne 0) { throw 'Native Windows 8-stage verification failed' }
& $Python -m pytest -W error -q -ra --tb=short
if ($LASTEXITCODE -ne 0) { throw 'Full suite failed' }
& $Python scripts/verify_sources.py
if ($LASTEXITCODE -ne 0) { throw 'Source verification failed' }
git diff --check
if ($LASTEXITCODE -ne 0 -or @(git status --porcelain --untracked-files=all).Count -ne 0) { throw 'Worktree not clean' }
Write-Host 'RH05 REPRODUCTION: PASS (verify actual test counts above)'
```

This example requires Python 3.12 and a genuine NTFS volume. It does not install or activate project environments in a protected folder; generated Python, ledger and bundle outputs are scoped to the test runner / outside Git. On any failure stop and report, never print a synthetic PASS.

**Linux evidence replay:** In GitHub Actions, use the merged `.github/workflows/rh05-linux-evidence.yml` workflow with `workflow_dispatch` `source_commit=09b895423171eff7569fc49dd8ceac7dfb0d43c6`, download the synthetic-only artifact, and compare it to the original Windows JSON with `ai.report_comparison.compare_report(read_report(linux), read_report(windows))` using unchanged trusted code. Do not use the built-in `ai.research_evidence --compare` historical default for this newer source.

## Release review and remaining gates

**Candidate disposition:** RH-05 **synthetic engineering/reproducibility/security checks passed on the evidence enumerated above**. Reviewer/maintainer must check this evidence summary, independently inspect private Windows transcript if needed, and decide whether Issue #121 can be closed. A docs-only acceptance PR does not rewrite any earlier test record, add a real dataset, grant clinical access, or change model behavior.

Keep **RH-03** scientific claim verification and human academic review open; **RH-06** real AI-9.2 / AI-10.2 remain `NOT_PERFORMED` / `NO-GO`; **RH-07/RH-08** final report/freeze separately gated. The final technical acceptance of synthetic RH-05 is not a substitute for any of them.

Related issue: [#121](https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/121). Source comparison evidence: GitHub Actions run [44745390366](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/44745390366).
