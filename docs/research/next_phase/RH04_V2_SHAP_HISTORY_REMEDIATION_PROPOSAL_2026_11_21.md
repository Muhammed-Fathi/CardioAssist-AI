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

## 3. Approach taken — clean delivery line from current main

### 3.1 Why the earlier `commit-tree` plan was wrong

The v2 plan proposed `git commit-tree "$FINAL_TREE" -p origin/main`, which would
have made the delivery tree **equal to the old candidate tree**. That tree predates
current main and is missing `docs/GRADUATION_DELIVERY_ROADMAP.md`; its `README.md`
also differs. Adopting it wholesale would have **deleted the permanent roadmap**
and reverted the README link.

The independent reviewer caught this. **The plan was not executed as written.**

### 3.2 What was done instead

Start from current main and add only the reviewed changes:

```bash
git checkout -B delivery/rh04-v2-final origin/main   # c6a6bde
# apply the 41 reviewed paths (40 additions, 1 modification) from the review tree
# leave README.md and docs/GRADUATION_DELIVERY_ROADMAP.md untouched
```

The reviewed work is **additive relative to main**: measured as 40 `A` and 1 `M`
against the branch's own base, and six of the reviewed files are byte-identical to
files main already had (they arrived via the merged PR #135), so they needed no
migration at all.

### 3.3 Verified results

| check | result |
|---|---|
| `README.md` vs main | **identical** |
| `docs/GRADUATION_DELIVERY_ROADMAP.md` vs main | **identical** |
| files deleted relative to main | **0** |
| files of main's modified | **0** |
| prohibited projection in tree | **absent** |
| long base64 literals in fixtures | **absent** |

### 3.4 Ancestry evidence — complete, not assumed

The review sandbox was a **shallow clone**, which would have made an ancestry
claim unsafe: `git rev-list --count HEAD` returned `2`. It was unshallowed first
(`git fetch --unshallow`), giving 495 reachable commits, and the check was then run
over the complete history:

```
reachable commits from delivery HEAD : 495
b67ed4e an ancestor of HEAD          : NO
b67ed4e an ancestor of origin/main   : NO
commits reachable from HEAD carrying shap_background_document : NONE
```

The third line is the substantive one: it is not enough that `b67ed4e` is absent
from the ancestry graph — no reachable commit reintroduces the projection.

### 3.5 PR disposition

A new **Draft** PR from `delivery/rh04-v2-final`. PR #139 stays open and unmerged
as the historical review line, cross-linked. **No force-push, no history rewrite,
no branch deletion.**

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
