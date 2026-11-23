# SHAP history remediation — clean replacement delivery line

**Document ID:** CAI-RH04-SHAP-HISTORY-v2
**Status:** PROPOSAL. **Nothing executed.** Requires explicit maintainer approval.
**Supersedes:** v1 of this document (Round 10.3), which was written before the
repository state was re-measured.

---

## 1. The finding, stated exactly

`b67ed4e` ("enforce admission in the replay path and pin every Lane B dependency")
committed `research/intake/fixtures/rh04_v2_portable/*.archive.json` containing
`training_identity.shap_background_document` — the SHAP training projection,
stored as base64.

This is **publication-prohibited** under the standing restriction, and
`synthetic_only: true` does not override it: base64 is an encoding, not a
reclassification.

**Measured repository state at Round 10.4:**

| ref | carries the blob? |
|---|---|
| `b67ed4e` | **yes** |
| `6b0737f`, `9859e76` (later branch commits) | no — removed by `6b0737f` |
| working tree at `HEAD` | no |
| `main` (`c6a6bde`) | no — and main contains **no** V2 fixture or module at all |

So the blob's exposure is confined to this review branch. That is materially
better than the v1 document assumed, and it changes the recommendation's shape:
main was never contaminated, so **no remediation of main is required**.

## 2. Why a corrective commit is insufficient

`6b0737f` removed the document from the tree. It cannot remove it from the
branch's history: `b67ed4e` remains reachable from
`review/rh04-v2-p0-corrections-20261121`, and anything that merges that branch
would carry `b67ed4e` into main's ancestry.

The security property is *ancestry*, not working-tree content. A clean replacement
branch prevents the affected ancestry from entering main. It does **not** erase
existing copies, forks, caches or GitHub's PR object history, and this proposal
makes no such claim.

## 3. Recommended approach — Option A: clean replacement line

**Chosen because it never rewrites, never force-pushes and never deletes.**

The observation that makes this cheap: the V2 work is 100% additive relative to
`main`. `main` has no `rh04_v2_*` module and no `rh04_v2_portable/` fixture
directory. There is therefore nothing to *merge* with main — the replacement line
can simply be main plus the final tree.

### 3.1 Exact proposed Git operations

```bash
# 0. Preconditions (verify, do not assume)
cd /home/user/CardioAssist-AI
git fetch origin
test "$(git rev-parse origin/main)" = "c6a6bdee46a552a2b0d705a723c862ff8a95be4d" \
  || { echo "main moved; re-review this plan"; exit 1; }
# The affected blob must exist ONLY on the review branch.
git grep -l shap_background_document origin/main -- research/intake/fixtures/ \
  && { echo "main contaminated; this plan is insufficient"; exit 1; } || true

# 1. Capture the FINAL tree of the review branch as a tree object.
#    This is the verified corrected tree: no blob, lineage corrected, anchor pinned.
FINAL_TREE=$(git rev-parse HEAD^{tree})

# 2. Create the replacement commit whose parent is main and whose tree is FINAL.
#    No history from the review branch is inherited.
REPLACEMENT=$(git commit-tree "$FINAL_TREE" \
  -p origin/main \
  -m "rh04(v2): portable Lane B acceptance, corrected producer lineage, unified verification

Replacement delivery line. Parent is main; the tree is the complete verified
RH-04 V2 state. This line deliberately does not inherit the review branch's
history, which carried a publication-prohibited SHAP training projection at
b67ed4e.

Tree identical to the reviewed candidate tree: $(git rev-parse HEAD^{tree})
")
echo "$REPLACEMENT"

# 3. Point a NEW branch at it. The review branch is neither moved nor deleted.
git branch review/rh04-v2-final-candidate "$REPLACEMENT"

# 4. Verify before any push: identical tree, no inherited ancestry.
git diff --stat "$REPLACEMENT" HEAD          # MUST be empty
git merge-base --is-ancestor b67ed4e "$REPLACEMENT" && echo "FAIL: ancestry leaked"
git log --oneline -2 "$REPLACEMENT"

# 5. Push the new branch (not the review branch).
git push origin review/rh04-v2-final-candidate
```

### 3.2 Expected verification results

| check | expected |
|---|---|
| `git diff --stat $REPLACEMENT HEAD` | empty output |
| `git rev-parse $REPLACEMENT^{tree}` | equals `HEAD^{tree}` |
| `git merge-base --is-ancestor b67ed4e $REPLACEMENT` | exits **1** (not an ancestor) |
| `git rev-list --count $REPLACEMENT` | `git rev-list --count origin/main` + 1 (in a full clone) |
| `git grep shap_background_document $REPLACEMENT` | no match |
| fixture SHA-256s | unchanged from §5 |

The commit message embeds the tree SHA so the equivalence claim is auditable
after the fact without trusting this document.

**Measured caveat.** The review sandbox clone is **shallow**
(`.git/shallow` present, `origin/main` depth 1), so `--count` reported
`main=1, probe=2` there. That is a property of the checkout, not of the
replacement line. A reviewer running the plan in a full clone should expect the
true main depth plus one. The dry-run probe performed in this sandbox produced:

```
HEAD tree:   d426178add19da32b2a278ed4d4639637c362055
probe commit: c46b63666da3ea1a1163b060aa0812962ccc1365
git diff --stat probe HEAD      -> (empty)
is b67ed4e an ancestor?         -> NO
```

so the tree-equivalence and ancestry properties are verified, and the count
expectation is the only item that depends on clone depth.

### 3.3 PR disposition

1. Open a **new Draft PR** from `review/rh04-v2-final-candidate` into `main`.
2. Cross-link it from #139 and label #139
   `superseded-by-clean-delivery-line` — **do not close #139**, and do not delete
   the branch; both are the evidence record.
3. Issue **#132 stays OPEN**. Nothing in this remediation closes a gate.

### 3.4 Evidence preservation

Required before the new PR is opened, so that the reviewed history is not lost:

- `git bundle create rh04-review-line.bundle review/rh04-v2-p0-corrections-20261121`
  archived **outside** the repository (not committed);
- the existing PR #139 comments and review thread remain untouched;
- this document records `b67ed4e` by SHA so the finding is reproducible.

## 4. Options considered and rejected

**Option B — force-push / rebase the review branch.** Would rewrite published
history, break every existing reference in PR #139, and would still leave the blob
in forks and caches. Standing instruction forbids it without explicit
authorization, and it does not achieve the goal. **Not recommended.**

**Option C — revert commit.** A revert removes content from the tip's tree but
leaves `b67ed4e` in ancestry. It solves nothing that the current state does not
already solve. **Not recommended.**

## 5. Reference identity that must be preserved

The replacement tree must verify to exactly these values, because they are the
independently reviewed acceptance reference:

| item | value |
|---|---|
| Lane B digest | `891d9e3b2a332c6efc251d97fee25ed46a627ed25b2a089594057b4c9896cdc8` |
| semantic archive digest (BASIC) | `33be3035dba8d7360b8fadddb749e0a4bdd08c48d095dd1bd7e21b1c8a72fd8a` |
| semantic archive digest (REST) | `ee893f159f4f16474b216671289ca538b09a302e162d9d1a25ae34628fb930fa` |
| raw BASIC | `58a50a14ca83e9f3e34f95c8bd809594b798695e3c2d6594193ce3c8179dfc77` (523,747 B) |
| raw REST | `a77182ad3e098374dabd306e427affa4d715fc6a4c005eee5509a90d365a0c25` (154,735 B) |
| manifest (raw file) | `d33ada4f3cd7db6d4cb6c64465ecc84d566f23bb78faaa1c3eae85eec166ba38` (31,772 B) |
| trust anchor (canonical) | `293c6e3f6e9aa74f1119a52b56d97af8774a76e90b162a41a222a46a07a63c70` |

Verification command after the replacement branch exists:

```bash
PYTHONPATH=. python -m research.intake.rh04_v2_portable_archive \
  research/intake/fixtures/rh04_v2_portable
# expect: matches_reference true, digest 891d9e3b...
```

## 6. What this remediation does not claim

- It does not erase `b67ed4e` from GitHub, forks, clones or caches.
- It does not modify or delete PR #139 or its history.
- It does not delete the review branch.
- It does not close any gate or complete RH-04.
- It does not grant a policy exception. The blob was prohibited and remains
  recorded as having been published on a non-main branch.

**Explicit maintainer approval is required before step 2 is executed.**
