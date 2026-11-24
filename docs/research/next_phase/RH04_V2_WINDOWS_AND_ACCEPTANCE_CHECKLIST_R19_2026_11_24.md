# RH-04 V2 — remaining Windows verification and acceptance checklist

**Supersedes:** `RH04_V2_EXECUTION_READINESS_CHECKLIST_2026_11_24.md` (round 18).
**Status:** owner execution pending. **0/10 gates closed.** Nothing ratified.

---

## 0. Where things stand

| item | state |
|---|---|
| Gate run `45446417665` | **failed**, 8 of 10 jobs — retained permanently |
| Cause | implementation contradicted AMEND-v3's own §1 table |
| Corrected in candidate | Lane A validity, fresh-vs-frozen replay, Stage 2/4/6 |
| V1 failure | **real, retained, unmodified** |
| Native Windows | **not executed** |
| Ratification | **none** |

## 1. Apply the gate patch

The installed gate at `73d9f9d` is the version that failed. The candidate carries a
corrected gate as a **one-path** patch.

```powershell
Set-Location C:\path\to\CardioAssist-AI
$ErrorActionPreference = "Stop"
$Candidate = "PASTE_THE_CANDIDATE_SHA_FROM_THE_PR_COMMENT"

git fetch origin
$dirty = @(git status --porcelain)
if ($dirty.Count -gt 0) { $dirty; throw "working tree is not clean" }
git checkout delivery/rh04-v2-final
git merge --ff-only "origin/delivery/rh04-v2-final"
$head = (git rev-parse HEAD).Trim()
if ($head -ne $Candidate) { throw "HEAD is $head, expected $Candidate" }
```

**Preview first (read-only, changes nothing):**

```powershell
.\docs\research\next_phase\workflow-patch\APPLY_AS_OWNER.ps1 -ExpectedHead $Candidate
```

Expected: `every path is allowed and all expected paths are present`, then
`Nothing was modified.`

**Then apply, commit and push:**

```powershell
.\docs\research\next_phase\workflow-patch\APPLY_AS_OWNER.ps1 -ExpectedHead $Candidate -Confirm
```

The patch touches **one** path. `experiment-runner-ci.yml` is already at 40
minutes and is not part of it.

The patch modifies exactly one path:
`.github/workflows/rh04-dual-run-gate.yml`. It does **not** touch
`experiment-runner-ci.yml` (already correct at 40 minutes).

## 2. Expected gate outcome after the patch

The V1 failure is **not** fixed by this patch and must not be.

| stage | expected exit | note |
|---|---|---|
| Stage 1 V1 | **1** | 456/457 — **real failure, retained** |
| Stage 2 Lane A | **0** | validity, with findings printed |
| Stage 3 Lane B | **0** | ACCEPTED, fixed digest |
| Stage 4 regression | **0** | 61 tests now selected (was 35) |
| Stage 5 security | **0** | |
| Stage 6 classify | **0** | was `KeyError` |
| **Aggregate** | **FAIL** | `mandatory_failures = ["v1: exit 1"]` |

**A red aggregate job is the correct outcome.** The gate should fail on V1 and on
nothing else. If it goes green, something is wrong — investigate, do not celebrate.

## 3. Native Windows verification

Run only after the owner accepts that the Linux behaviour is understood.

```powershell
.\docs\research\next_phase\workflow-patch\verify-native-windows.ps1 -ExpectedHead $Candidate
```

The script now reports three statuses, not two:

- **PASS** — required and satisfied
- **FAIL** — required and not satisfied (affects exit code)
- **FINDING** — a measured difference between valid converged regenerations.
  **Does not affect the exit code.** Printed with its magnitude.

Check specifically:

| check | expected on Windows |
|---|---|
| Lane B exact vs fixed reference | **PASS** — `891d9e3b…` |
| Lane A validity | **PASS** |
| Lane A archived-parameter equality | **FINDING** for `da_a2` (expected; MSVC BLAS differs again) |
| Lane A fresh-model replay identity | **PASS**, digest distinct from Linux |
| Lane A frozen-archive replay identity | **PASS** |
| resident library evidence | no absolute paths |
| fitting guard | 4 armed, 0 attempts |

**A FINDING on Windows is the expected result, not a failure.** Reporting it as a
failure would make the Windows cell permanently unachievable.

## 4. Acceptance checklist

Owner marks each; nothing is inferred.

| # | Item | Status |
|---|---|---|
| A1 | AMEND-v4 ratified explicitly | ☐ |
| A2 | §2 split accepted (validity required, equality measured) | ☐ |
| A3 | Gate patch applied, gate re-run at the new head | ☐ |
| A4 | Aggregate fails on V1 only | ☐ |
| A5 | ≥3 dispatch classes × {3.11, 3.12} reported from **hosted** evidence | ☐ |
| A6 | Native Windows run completed, FINDINGs classified | ☐ |
| A7 | Independent reviewer confirms A5–A6 from hosted evidence | ☐ |
| A8 | V1 retirement decision taken separately (§ V1 transition) | ☐ |

## 5. Prohibited

No retry-until-green. No tolerance widening. No suppression of the V1 failure. No
merge. No self-ratification. No gate closure. No claim of Windows execution before
A6. No production activation, real-data fitting or clinical claim.
