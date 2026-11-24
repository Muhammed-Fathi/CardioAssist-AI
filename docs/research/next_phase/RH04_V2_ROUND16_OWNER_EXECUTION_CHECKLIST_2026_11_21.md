# RH-04 V2 — round 16 owner execution checklist

**Candidate SHA:** `ba3121bbbe5f0db572c90c366aac2b8f1da5e141`
**Status:** review-ready. No gate is closed (0/10). Nothing here has been ratified.

Arena cannot push workflow files, so the CI gate exists as a patch until step 2 is
performed by the owner.

---

## 1. Review before running anything

Read the round-16 PR comment and confirm you accept:

- the corrected V2-02 classification (over-criterion ≠ reportable variation);
- the corrected V2-07 test, which previously asserted the defect;
- the retraction of the v4 ledger claims for V2-02 and V2-07.

If you do not accept any of these, stop. Do not proceed to step 2.

## 2. Apply the consolidated patch (PowerShell 5.1)

One copy-ready block. It is safe to run without `-Confirm`: it only checks and
previews, and it leaves the checkout untouched.

```powershell
Set-Location C:\path\to\CardioAssist-AI
git fetch origin
git checkout delivery/rh04-v2-final
git reset --hard ba3121bbbe5f0db572c90c366aac2b8f1da5e141

powershell -ExecutionPolicy Bypass -File `
    .\docs\research\next_phase\workflow-patch\APPLY_AS_OWNER.ps1 `
    -ExpectedHead ba3121bbbe5f0db572c90c366aac2b8f1da5e141
```

Expect `Nothing was modified` and `every path is allowed`. If anything else appears,
stop and report it.

Then apply for real:

```powershell
powershell -ExecutionPolicy Bypass -File `
    .\docs\research\next_phase\workflow-patch\APPLY_AS_OWNER.ps1 `
    -ExpectedHead ba3121bbbe5f0db572c90c366aac2b8f1da5e141 -Confirm
```

It applies, verifies the changed-path set is exactly the two workflow files,
re-parses both, then commits and pushes.

## 3. Read the gate run

The gate produces **10 jobs**: 8 matrix runs (`prescott`, `nehalem`, `sandybridge`,
`haswell` × Python 3.11/3.12) plus 2 `host` runs.

For each job record:

| field | where |
|---|---|
| conclusion | job list |
| `requested_dispatch_class` / `resident_dispatch_class` | "Record resident environment identity" |
| Lane A regeneration identical | "Stage 2" |
| Lane A identity digests | `lane-a/identity.json` artifact |
| Lane B **observed** digest and verdict | "Stage 3", `lane-b/identity.json` |
| Stage 4 regression result | "Stage 4" |

**A job whose resident class differs from its requested class is expected to fail.**
That is the guard working, not a flake. Do not retry it to green.

## 4. Native Windows verification

Only run this on an actual Windows host. It is the only thing that can support a
native-Windows claim, and no such claim exists yet.

```powershell
powershell -ExecutionPolicy Bypass -File `
    .\docs\research\next_phase\workflow-patch\verify-native-windows.ps1 `
    -ExpectedHead ba3121bbbe5f0db572c90c366aac2b8f1da5e141
```

It stops immediately on a wrong SHA or a dirty tracked tree, uses a dedicated
`.venv-rh04-win` and **never deletes** an existing directory (pass `-ReuseVenv` to
reuse one), and writes `.rh04-evidence-win\summary.json`.

## 5. Record, then decide

Record the run IDs, the per-class Lane A digests and the Lane B digest verbatim.
Then decide on ratification — the wording is in
`RH04_V2_DECISION_REGISTER_WORDING_2026_11_24.md`, with acts A/B/C kept separate.

---

## What is still not established

- native Windows execution (no Windows host has been used);
- a complete matrix *inside a single run* — this round's local measurements are
  Linux 3.11 only;
- that the gate runs at all in CI (it is a patch until step 2);
- any gate satisfaction, any merge, any clinical or production claim.

## Do not

- regenerate the Lane B digest to match an observation;
- change a tolerance, skip a stage, or retry a mandatory failure to green;
- approve the PR on the strength of this document alone.
