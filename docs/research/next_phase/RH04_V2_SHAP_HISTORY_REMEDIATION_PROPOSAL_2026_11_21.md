# SHAP publication-policy history remediation — proposal for maintainer approval

**Document ID:** CAI-RH04-SHAP-HISTORY-v1
**Status:** PROPOSAL ONLY. Nothing in this document has been executed.
**Requires:** explicit maintainer authorization before any action in §4.

---

## 1. What the policy says and what it forbids

The producer bundle's own `shap_background.json` declares, in its `privacy` block:

```json
{
  "commit_or_public_upload_prohibited": true,
  "contains_encoded_training_projections": true,
  "reconstructible_with_preprocessor_stats": true,
  "sensitive_classification": "SYNTHETIC_NON_PATIENT_DERIVATIVE",
  "synthetic_only": true
}
```

The restriction is about **publication**, not about patient data. These rows are
synthetic-cohort encoded projections, so there is no patient-privacy breach. The
control that was violated is the bundle's publication restriction, and the fact
that `synthetic_only: true` does **not** override it.

No publication exception was requested and none was granted. The document was
removed from the current tree by removal of the representation, not by relabelling
it.

## 2. Current tree status (verified)

The committed fixtures now contain **no** background document, in any encoding:

| Check | Result |
|---|---|
| `background_matrix` in any committed fixture | absent |
| `shap_background_document` in any committed fixture | absent |
| base64 of either marker | absent |
| hex of `background_matrix` | absent |
| archive declares `stores_training_projection` | `false` |

Reconstruction is deterministic and is checked against a SHA-256 pinned in the
independently anchored manifest. A drifted reconstruction is a refusal, not a
silently different baseline.

## 3. What the current tree cannot fix

**The prohibited representation remains reachable in pushed Git history.** A
normal corrective commit removes a value from `HEAD`; it does not remove it from
the objects that already reference it.

### 3.1 Affected commits

| Commit | Contains the embedded document | Notes |
|---|---|---|
| `5793192` | **no** | Round 10 feature commit — archive fixtures first appeared here without any SHAP document |
| `9cb54f6` | **no** | Round 10 docs |
| `b67ed4e` | **yes** | Round 10.1 — introduced `training_identity.shap_background_document` (base64) |
| `6b0737f` | **no** | Round 10.2 — removed it; reconstruction added |
| this round's commit | **no** | lineage/trust corrections |

Verified by inspecting the blob at
`research/intake/fixtures/rh04_v2_portable/da_a2_resting_v1.archive.json` for each
reachable commit rather than by assumption.

### 3.2 Affected refs and artifacts

| Ref / artifact | Status |
|---|---|
| `refs/heads/review/rh04-v2-p0-corrections-20261121` | contains `b67ed4e` in its ancestry |
| PR #139 | its diff history and any review comments that quote the file are affected |
| PR #139 review comments / CI logs | may retain quoted fragments; not under repository control |
| Fork/clone copies | outside this repository's control; cannot be remediated here |

### 3.3 Exposure assessment (bounded, not dismissive)

The exposed content is:

* 24 rows × 10 (REST) and 24 × 16 (BASIC) binary64 encoded values;
* derived from a **published, seed-reproducible synthetic cohort** — anyone with
  the repository can regenerate it exactly using the recipe now committed in the
  archive;
* therefore the exposure does not disclose anything that is not already derivable
  from reviewed, committed code and a public seed.

That materially reduces the *risk*. It does **not** change the *classification*:
the bundle said do not publish it, and it was published.

## 4. Options (for maintainer decision — none executed)

### Option A — publish-once correction via a fresh reference line (recommended)

Create a new, clean reference line that does not descend from `b67ed4e`, carrying
only the corrected tree, and open a replacement PR. Leave PR #139 open and
unmerged, marked as superseded, so reviewers retain the discussion.

* **Pro:** removes the object from the ancestry of everything that would be merged;
  no force-push; no destruction; nothing is rewritten in place.
* **Con:** PR #139's history still contains it; requires closing #139 rather than
  merging it, which is a maintainer decision.

### Option B — history rewrite of the review branch

Interactive rebase / filter-repo to drop `b67ed4e`'s blob, then force-push the
review branch.

* **Pro:** the branch no longer contains it.
* **Con:** a force-push on a branch with review comments invalidates review state;
  every clone keeps the old objects anyway; it is exactly the class of destructive
  action this round is not authorized to take.

### Option C — accept and document (status quo)

Record the exposure as a known, bounded, accepted residual with the risk
assessment in §3.3, and rely on the fact that the content is regenerable from
public code.

* **Pro:** zero destructive action; honest.
* **Con:** the explicit publication prohibition is knowingly left partly
  unsatisfied in history.

### Recommendation

**Option A**, with **Option C** as the documented interim state if the maintainer
prefers not to open a new PR line during review. Option B is listed for
completeness and is not recommended.

## 5. Explicit non-claims

* This document does **not** claim the prohibited content has been removed from
  history. It has not.
* A normal corrective commit **cannot** make that claim, and this round does not
  make it.
* No force-push, history rewrite, destructive deletion or remote branch removal has
  been performed or is authorized by this round.
* The current-tree removal is complete and verified; the history remediation is
  proposed and awaiting a decision.

## 6. Verification commands for a reviewer

```bash
# current tree must be clean
grep -rc "background_matrix\|shap_background_document" \
  research/intake/fixtures/rh04_v2_portable/*.json    # all zero

# which commits ever carried it
for c in $(git rev-list --all); do
  git show "$c:research/intake/fixtures/rh04_v2_portable/da_a2_resting_v1.archive.json" \
    2>/dev/null | grep -q shap_background_document && echo "AFFECTED: $c"
done

# reconstruction must reproduce the pinned producer digest
PYTHONPATH=. python -m research.intake.rh04_v2_portable_archive \
  research/intake/fixtures/rh04_v2_portable
```
