# Dual-run workflow and rollback — proposals

**Document ID:** CAI-RH04-DUALROLLBACK-v2 (supersedes v1)
**Status:** PROPOSAL for V2-05, DEMONSTRATION for V2-10.

---

## Part 1 — V2-05 dual-run window

### 1.1 A correction to v1

v1 of this document proposed "two Lane B runs on different BLAS kernels" as the
dual-run window. **That does not satisfy V2-05.** V2-05 requires *both V1 and V2 to
run in CI* during the transition, until the owner retires V1. Two runs of the same
lane under different kernels are a portability check, not a dual-run window.

### 1.2 What V2-05 actually requires

> `V2-05` **Dual-run window.** Both V1 (scoped, §6) and V2 gates run in CI until
> the owner retires V1. No silent substitution.

Three properties follow directly from that text:

1. **Both gates execute.** A run in which V2 passes because V1 was skipped is not a
   dual-run window.
2. **V1 failures stay visible.** If V1 fails, the window fails. There is no
   "V2 is the new gate, so V1 is advisory" reading.
3. **Retirement is an owner act.** The window ends when the owner says so, not when
   V2 is green.

### 1.3 Proposed workflow content

A single job with four visible stages, in this order:

| # | stage | gate character | failure behaviour |
|---|---|---|---|
| 1 | **V1 scoped verification** | mandatory | fails the job |
| 2 | **Lane A diagnostic evidence** | **non-voting** | recorded, never fails the job |
| 3 | **Lane B fixed-reference exact verification** | mandatory | fails the job |
| 4 | **Security and regression checks** | mandatory | fails the job |

**Stage 2 is deliberately non-voting and this must be stated in the workflow.**
Lane A is the scientific regeneration path; its per-class numeric differences are
*findings about the environment*, not gate failures. Marking it mandatory would
either force a tolerance (forbidden) or make the gate permanently red. Marking it
silent would hide it. Non-voting-with-published-output is the only honest option,
and it must be visible in the workflow definition rather than implied.

### 1.4 Exact-head provenance

The workflow records, in its own output:

- the exact head SHA it ran against;
- the **resident** NumPy/SciPy dispatch, read from `threadpoolctl` — not the
  requested `OPENBLAS_CORETYPE`, which is a request that can be ignored;
- every exit code, and pass/fail/error/skip counts per stage.

### 1.5 What this proposal does not do

- It does **not** modify any protected workflow. That needs separate authorization.
- It does **not** retire V1.
- It introduces **no** tolerance, retry or rerun-to-green behaviour; V2-08 forbids
  new tolerance surface and V1 failures remain visible.

---

## Part 2 — V2-10 rollback: executed demonstration

### 2.1 Requirement

> `V2-10` **Rollback plan:** V2 revert must be a single revert of the pack +
> comparator + gate, leaving V1 intact and green.

### 2.2 A correction to v1

v1's plan grepped commit messages for a delivery commit and asserted
`test ! -e <path>`. Neither is evidence:

- a message search is not a stable identifier, and
- *observing that a file disappeared* says nothing about whether the revert left
  the repository in a working state.

The demonstration below uses the **exact delivery commit SHA**, executes the
revert, and then **runs the V1 checks**.

### 2.3 Demonstration (executed on a scratch branch)

Because this delivery is additive relative to `main`, reverting its single commit
must restore `main` exactly. The demonstration asserts that byte-for-byte rather
than asserting the absence of one file.

```bash
# 0. From the delivery commit.
DELIVERY=$(git rev-parse HEAD)
BASE=$(git rev-parse origin/main)

# 1. Scratch branch at the delivery commit, then revert it.
git switch -c scratch/v2-10-rollback "$DELIVERY"
git revert --no-edit "$DELIVERY"

# 2. The tree must now be IDENTICAL to main — not merely missing a file.
test "$(git rev-parse HEAD^{tree})" = "$(git rev-parse "$BASE^{tree}")"

# 3. V1 must be intact and green on the reverted tree.
PYTHONPATH=. python -m pytest tests/experiments/test_offline_fixture_pack.py \
                             tests/contracts -q
```

### 2.4 Measured result

Executed on `scratch/v2-10-rollback`, then the scratch branch was deleted.

```
delivery commit : 6349738d7b45322164a5ba4e18203d51e1e3e073
main            : c6a6bdee46a552a2b0d705a723c862ff8a95be4d
revert          : single `git revert --no-edit`, 41 files deleted

reverted tree   : 3106bece1fe0e7c09ff0635d66cc883d1ecca33e
main tree       : 3106bece1fe0e7c09ff0635d66cc883d1ecca33e
tree identical  : PASS

V1 checks on the reverted tree:
  pytest test_offline_fixture_pack.py test_research_facade.py tests/contracts
  -> 457 passed in 34.65s, exit 0
```

The tree equality is the substantive result: the revert does not merely remove V2
files, it restores `main` exactly. V1 was then executed rather than assumed green.

### 2.5 Acceptance criteria

| criterion | check |
|---|---|
| one command | a single `git revert --no-edit` |
| tree restored to main exactly | `HEAD^{tree} == main^{tree}` |
| no V2 module remains | implied by the tree equality, not asserted separately |
| V1 intact and green | V1 fixture + contract suites pass on the reverted tree |
| no history rewrite | revert adds a commit; it deletes nothing |

### 2.6 Why not force-push

Force-pushing `main` back to the pre-delivery commit would rewrite published
history, invalidate every clone and open PR, and destroy the record that the
delivery existed. A revert is reversible itself. Standing instruction forbids
history rewrite without authorization, and it is not needed.

### 2.7 What rollback does not do

It does not close Issue #132, retract findings, or alter the acceptance ledger. It
restores `main` to its pre-delivery state and leaves the analysis in the PR record.
