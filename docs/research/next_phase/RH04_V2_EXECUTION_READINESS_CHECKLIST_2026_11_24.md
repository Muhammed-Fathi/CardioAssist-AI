# RH-04 V2 — execution readiness checklist (round 18)

**Candidate:** the tip of `delivery/rh04-v2-final` — take the SHA from the PR
comment for round 18 and paste it into `$Candidate` in every block below.

> **This file deliberately contains no candidate SHA.** A document cannot contain
> the hash of the commit that contains it: writing the number changes the number.
> Any SHA written here would be the *previous* commit, correct at the moment of
> writing and stale by the moment of reading — which is exactly the defect this
> round was asked to fix. The synchronise block therefore verifies against the SHA
> you paste, and it fails loudly if they disagree. Treat the PR comment as the
> source of truth; this file is the procedure.

**Branch:** `delivery/rh04-v2-final` · **PR #141** Draft/Open · **main** `c6a6bdee`
**Status:** review-ready. No gate is closed (0/10). Nothing has been ratified.

This supersedes `RH04_V2_ROUND16_OWNER_EXECUTION_CHECKLIST_2026_11_21.md`, which
contained a `git reset --hard` step and a stale SHA. Both are removed.

Round 18 changed the harness, not the model. Lane B no longer fits an estimator, the
resident-library evidence no longer carries absolute paths, and Lane A reports
regenerated parameters and per-response replay identities instead of selection
metadata. The fixed Lane B digest `891d9e3b…`, the approved V1 surface, the
independent calibration evaluator, the convergence requirements and the 4×2
environment matrix are all unchanged.

---

## 0. What changed and why it was blocking

| blocker | what was wrong | what it is now |
|---|---|---|
| Patch application | the post-apply check used `--untracked-files=no`, so the newly created gate file was invisible and the two-path assertion failed on a **correct** apply | staged-diff verification; **reproduced** in a clean checkout: old check saw 1 path, new check sees 2 |
| Remote HEAD | a mismatch printed a warning and continued | a mismatch is **fatal** |
| Preview safety | a failed apply could leave a dirty tree | the apply is **transactional**: any post-apply failure reverses it |
| PyYAML | validation required it; it is not an application dependency | **standard library only**, PyYAML used as an extra parse if present |
| Lane B dispatch | inherited from a setup process / first library entry | read **inside the replay process**, every entry kept |
| Windows evidence | could credit a stale JSON | **fresh SHA-bound per-run directory**, exit codes checked immediately, stale output deleted |
| Independence claim | "independently evaluated" meant re-running the calibrator's own Jacobian | two forms **separated and labelled**; the independent one uses 50-digit decimal finite differences |
| Lane B fit | `_warm_numerics()` called `LogisticRegression.fit`, putting a model fit in an inference lane | warm-up uses BLAS/LAPACK only; a **FittingGuard** arms 4 entry points and records 0 attempts |
| Evidence paths | `filepath`, `prefix` and `sys.executable` published verbatim | sanitised to basename + SHA-256 + a non-identifying prefix kind |
| Lane A parameters | selection metadata and input hashes stood in for model parameters | **actual refit**: 10 coefficients with zero deltas / 50-tree structure exact; replay identity over the 29 responses |

---

## 1. Review before running anything

Read the round-17 PR comment and confirm you accept:

- the corrected V2-02 classification (over-criterion ≠ reportable variation);
- the corrected V2-07 test, which previously asserted the defect;
- the retraction of the v4 ledger claims for V2-02 and V2-07;
- that the calibration residual now reports **two** evidence forms rather than
  one number described as independent.

If you do not accept any of these, stop.

## 2. Synchronise (fast-forward only, no reset)

Copy-ready. Set `$Candidate` to the SHA in the PR comment for this round, then run.
Fails loudly instead of discarding work.

```powershell
Set-Location C:\path\to\CardioAssist-AI
$ErrorActionPreference = "Stop"

$Candidate = "PASTE_THE_CANDIDATE_SHA_FROM_THE_PR_COMMENT"

git fetch origin
if ($LASTEXITCODE -ne 0) { throw "fetch failed" }

$dirty = @(git status --porcelain)
if ($dirty.Count -gt 0) {
    $dirty
    throw "working tree is not clean; commit, stash or remove these first"
}

git checkout delivery/rh04-v2-final
if ($LASTEXITCODE -ne 0) { throw "checkout of delivery/rh04-v2-final failed" }

# Fast-forward only. Never a reset.
git merge --ff-only "origin/delivery/rh04-v2-final"
if ($LASTEXITCODE -ne 0) { throw "not a fast-forward; inspect before continuing" }

$head = (git rev-parse HEAD).Trim()
if ($head -ne $Candidate) {
    throw "HEAD is $head, expected $Candidate. Stop."
}
Write-Host "synchronised at $head" -ForegroundColor Green
```

## 3. Preview the patch (changes nothing)

```powershell
powershell -ExecutionPolicy Bypass -File `
    .\docs\research\next_phase\workflow-patch\APPLY_AS_OWNER.ps1 `
    -ExpectedHead $Candidate
```

Expected: `working tree is clean`, `remote HEAD matches the reviewed commit`,
`the patch applies cleanly (nothing was modified)`, `every path is allowed and all
expected paths are present`, then `Nothing was modified`.

Anything else: stop and report it.

## 4. Apply, verify, commit, push

```powershell
powershell -ExecutionPolicy Bypass -File `
    .\docs\research\next_phase\workflow-patch\APPLY_AS_OWNER.ps1 `
    -ExpectedHead $Candidate -Confirm
```

It applies, stages both paths, verifies the **staged** set is exactly the two
workflow files (including the newly added one), validates both workflows without
PyYAML, then commits and pushes `HEAD:delivery/rh04-v2-final`.

If any verification fails after applying, it reverses the patch and exits non-zero.

## 4a. Verified hosted baseline (before this round)

Run `45335320935` on `92b43cb`, tested merge checkout
`92fb7c8bb764f082d93570ac549da838e381de01`, all four hosted workflows succeeded:
**2122 passed, 2 skipped, 0 failed** on both Python 3.11 and 3.12, 396 UCI-412 tests
passed, structural diagnostic succeeded. This is the baseline the gate run below is
compared against; it is not evidence for the gate itself, which has never run.

## 5. Read the gate run

10 jobs: 8 matrix (`prescott`, `nehalem`, `sandybridge`, `haswell` × 3.11/3.12)
plus 2 unforced `host` runs.

| field | where |
|---|---|
| conclusion | job list |
| `requested_dispatch_class`, `resident_dispatch.blas_architectures` | Stage 2 / Stage 3 logs |
| `regeneration_identical` | Stage 2 |
| model / calibration / replay identity digests | `lane-a/identity.json` artifact |
| regenerated-parameter digests, coefficient deltas, structure exactness | `lane-a/identity.json` (`identities_run1`) |
| replay response digest over all 29 responses | `lane-a/identity.json` (`replay_responses_sha256`) |
| Lane B **observed** digest and verdict | Stage 3, `lane-b/identity.json` |

A job whose resident class differs from its requested class **is expected to fail**.
That is the guard working. Do not retry it to green.

## 6. Native Windows verification

Only on an actual Windows host. Nothing here supports a native-Windows claim yet.

```powershell
powershell -ExecutionPolicy Bypass -File `
    .\docs\research\next_phase\workflow-patch\verify-native-windows.ps1 `
    -ExpectedHead $Candidate
```

Stops immediately on a wrong SHA or dirty tree. Creates a dedicated
`.venv-rh04-win` and never deletes an existing directory (`-ReuseVenv` to reuse).
Writes to `.rh04-evidence-win\<short-sha>\<UTC stamp>\`, which must be empty at
start, and emits `summary.json`.

## 7. Record, then decide

Record the run IDs, resident dispatch sets, Lane A identity digests and the Lane B
digest verbatim. Ratification wording is in
`RH04_V2_DECISION_REGISTER_WORDING_2026_11_24.md`, acts A/B/C kept separate.

---

## What is still not established

- native Windows execution — no Windows host has been used;
- a single run covering the whole matrix; round-17 local measurements are Linux
  3.11 only;
- that the gate runs in CI — it is a patch until §4;
- any gate satisfaction, merge, clinical or production claim.

## Do not

- regenerate the Lane B digest to match an observation;
- change a tolerance, skip a stage, or retry a mandatory failure to green;
- use `git reset --hard` on this branch;
- approve the PR on the strength of this document alone.
