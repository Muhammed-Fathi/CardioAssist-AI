# V1 transition and retirement — prerequisites

**Status:** proposal only. **No retirement is authorized.** V1 remains a mandatory
failure until the owner authorizes otherwise, explicitly, in writing.

---

## 1. The V1 failure is real and stays recorded

Hosted run `45446417665`, all eight forced-dispatch jobs:

```
tests/experiments/test_offline_fixture_pack.py::test_golden_replay
456 passed, 1 failed
```

Reproduced locally at `73d9f9d` under forced dispatch, identical count:

| dispatch | result | first differing field |
|---|---|---|
| native (`SkylakeX`) | 457 passed | — |
| haswell | 456 passed, 1 failed | `da_a1…calibrated_log_odds`, Δ `4.441e-16` |
| prescott | 456 passed, 1 failed | `da_a2…calibrated_log_odds`, Δ `4.441e-16`, `calibrated_research_score` Δ `1.110e-16` |

**Root cause, unchanged from the Lane A finding:** the V1 pack pins *exact*
expected responses produced by a fit performed on the host that built the pack.
Any other BLAS kernel reassociates the refit and moves the calibrated score by
~1 ulp, which the strict comparator reports.

This is the *same* architectural fact as the Lane A finding. It surfaced in V1
first because V1 has been in use longer.

## 2. What is explicitly forbidden

- Editing `research/intake/offline_fixture_pack.py`, `fixtures/offline_io.v1.json`,
  or `tests/experiments/test_offline_fixture_pack.py`.
- Widening `REL_TOL` / `ABS_TOL`, adding a case or a field to the exception.
- Suppressing, skipping, xfail-ing or deselection to get green CI.
- Marking the V1 failure resolved without an owner retirement decision.

`_approved_replay_equal` already contains one narrowly-scoped, documented exception
for the Windows float case. **That exception must not be reused or extended.**

## 3. Transition principle

> The V1 failure blocks **V1 retirement**. It does **not** block the collection of
> independent V2 evidence, because V2's evidence is produced by a different
> mechanism (portable archives + registered regeneration identity) that does not
> depend on V1's golden vectors.

This is why the corrected gate reports `v1: exit 1` **and** `lane_a/lane_b/
regression/security: exit 0` in the same job, with the aggregate failing on V1
alone. That is the intended behaviour, verified locally:

```
stage1_exit=1   ← V1, real, retained
stage2_exit=0   ← Lane A validity (V2-04a)
stage3_exit=0   ← Lane B exact
stage4_exit=0
stage5_exit=0
stage6_exit=0
aggregate → FAIL, mandatory_failures = ["v1: exit 1"]
```

## 4. Retirement prerequisites

All of the following, in order. None may be inferred from a green run elsewhere.

| # | Prerequisite | Status |
|---|---|---|
| R1 | **CAI-RH04-AMEND-v4 ratified by the owner** | **not done** |
| R2 | V2 evidence collected on the full matrix: ≥3 dispatch classes × {3.11, 3.12} Linux | **partially — Linux only, 4 classes measured locally; hosted re-run pending** |
| R3 | V2 evidence on **native Windows**, independently measured | **not done** |
| R4 | Lane B exact on every matrix cell, no tolerance | **measured on 4 Linux classes; Windows pending** |
| R5 | Lane A valid on every matrix cell, with differences classified | **measured on 4 Linux classes + host; Windows pending** |
| R6 | Independent reviewer confirms R2–R5 from *hosted* evidence, not local | **not done** |
| R7 | An explicit written statement of what replaces V1's guarantee and what is lost | **this document proposes it; not ratified** |
| R8 | Owner signs the retirement decision explicitly | **not done** |

## 5. What retirement would and would not establish

**Would:** that the V1 golden-replay exactness requirement is superseded by the
V2 contract (Lane B exact against frozen artifacts; Lane A valid and classified).

**Would not:** that V1's observed behaviour was wrong, that the failure was a test
defect, or that exact cross-environment replay of a *regenerated* model is
achievable. It is not, and the amendment does not claim it.

**A necessary disclosure for the owner.** Retiring V1 removes the only check that
currently asserts exact replay of a freshly-regenerated model. V2 replaces it with
a *bounded* claim (valid regeneration + exact frozen replay), which is weaker in one
specific respect and stronger in another. R7 exists because that trade must be
stated, not implied.

## 6. Current disposition

- V1 failure: **OPEN**, mandatory, recorded, unmodified.
- V1 retirement: **NOT AUTHORIZED**.
- Issue #132: **OPEN**.
- No V1 file has been touched by any round-18/19 change — verified by
  `git diff --quiet main HEAD -- research/intake/offline_fixture_pack.py
  research/intake/fixtures/offline_io.v1.json
  tests/experiments/test_offline_fixture_pack.py`.
