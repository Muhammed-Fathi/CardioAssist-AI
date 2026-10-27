# Bounded Offline Diagnostic Inference Scope — Cleveland D-047 Accepted Bundle

- **Decision ID:** `CAI-SCOPE-BOUNDED-OFFLINE-DIAGNOSTIC-INFERENCE-CLEVELAND-D047-V1`
- **Approved implementation and test baseline (`I3`):** AI-6.1 implementation (PR #59, MERGED) plus the tests-only repair (PR #62, MERGED); `87bccd6d3ef2331f1e2b2ba8905f34366734538d`
- **Historical governance revision (`G2`):** `44f06091602f66078726fcc3b62b6ee1305abd83` (PR #60, owner-ratified)
- **Current milestone:** `G3` governance re-baseline, docs-only; **PROPOSED — awaiting a NEW explicit human maintainer ratification of this revision**
- **Status of the historical scope decision:** **RATIFIED AT `G2`** for implementation revision `I2` (PR #60)
- **Status of this `G3` revision:** **PROPOSED / NOT YET RATIFIED FOR `I3` / NOT ACTIVATED / NO REAL-BUNDLE INFERENCE HAS OCCURRED**
- **Date:** 2026-10-27 (`G3` revision)
- **Gate PT:** P-1 PENDING; P-3 CLOSED; P-4/P-5 not opened
- **Supersedes:** this revision supersedes the **text** of this same document as it was ratified at `G2`, for the purpose of the *next* activation only. It does **not** erase, rewrite, or derogate the historical `G2` ratification, and it **narrows, but does not reinterpret**, the inference prohibition in `17_ai2_operational_scope_amendment.md` §9.

> This document is a governance proposal for a new baseline, not an authorization.
> The historical scope decision was genuinely ratified by the repository owner in
> PR #60 (see §0.2); that ratification is a real prior decision and remains a fact
> of record. It approved the `G2` text bound to `I2` and cannot be reused as
> approval of this revised text or of the `I3` baseline. **No new maintainer
> comment, new governance merge `G3`, activation merge `A3`, local operator
> authorization, or human signature is created or claimed by this PR.** The
> production diagnostic registry
> `ai/diagnostic_scope.py::RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES` is **EMPTY** at
> `I3` and must remain **EMPTY** after `G3`. Until §5 completes with a fresh
> ratification, every real-bundle diagnostic invocation fails closed with
> `diagnostic_scope_not_ratified` before any bundle is verified or deserialized.

## 0. Revision history: what is historical, what is repaired, what is proposed

This section exists because the same narrow operation has now passed through
several distinct states. Conflating them would misrepresent history in either
direction — by pretending the PR #60 ratification never happened, or by
pretending it already covers the current code and document bytes.

### 0.1 Revision sequence

| Name | Kind | Commit | Where it came from | Exact meaning |
|---|---|---|---|---|
| `I2` | implementation revision | `40b544be79acc9099e565a0ede183e9b376a238f` | PR #59, MERGED | The reviewed bounded diagnostic implementation (`ai/diagnostic_scope.py`, `ai/diagnostic_inference.py`, interface `.../v1.1`) with the trusted registry committed **empty**. |
| `G2` | governance revision | `44f06091602f66078726fcc3b62b6ee1305abd83` | PR #60, MERGED | The docs-only governance proposal as it was actually ratified by the owner. It bound `approved_implementation_commit_sha = I2` and its own document bytes. |
| `8ee00c7` | tests-only repair (PR head) | `8ee00c7b18912f74dda17b47b743ed5732f574cf` | PR #62, MERGED via `87bccd6` | Repaired lifecycle-aware diagnostic activation regressions. Six test files. |
| `I3` | implementation/test baseline | `87bccd6d3ef2331f1e2b2ba8905f34366734538d` | PR #62 merge commit | **Current approved baseline.** Identical production runtime bytes to `I2`; only `tests/experiments/**` changed in `G2..I3`. |
| `G3` | governance revision | **not yet known** — the actual merge commit of *this* PR | this docs-only PR | The ratified-`G3` governance baseline would bind `approved_implementation_commit_sha = I3` and this document's exact committed bytes at `G3`. **PROPOSED; not yet ratified.** |
| `A3` | activation revision | **not yet known** — a future registry-only merge | future activation PR | Would add exactly one literal record to the trusted registry. Its SHA can only exist after that merge and is stored **only** in the ignored local operator authorization. |

`I3`, `G3`, `A3` are **names for a new revision sequence**, not new schema
fields. The validator, its interface version
(`cardioassist.ai.bounded_offline_diagnostic_inference/v1.1`), the authorization
schema version (`cardioassist.ai.diagnostic_authorization/v1.1`), the field names
`approved_implementation_commit_sha` / `governance_baseline_commit_sha` /
`activation_merge_commit_sha`, and every guard are **unchanged**. Nothing in
this revision renames, adds, or relaxes a tracked field.

### 0.2 The historical PR #60 ratification is a real prior decision

On 2026-10-27 the repository owner posted the exact comment
`RATIFY-BOUNDED-OFFLINE-DIAGNOSTIC-INFERENCE-SCOPE` on PR #60
(<https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/60#issuecomment-6442269752>,
author `Muhammed-Fathi`, posted 2026-10-27T12:48:25Z) and merged that PR thirteen
seconds later (2026-10-27T12:48:38Z), producing `G2 = 44f06091602f66078726fcc3b62b6ee1305abd83`. That decision
is recorded here as **historical fact**, not as a pending or never-occurring
event.

What that ratification did and did not do:

- It **did** ratify the exact §2 operation for the `G2` document text and bind
  it to implementation revision `I2`.
- It **did not** create any registry entry, activation revision, local operator
  authorization, or real-bundle inference. `A2` was never merged; the diagnostic
  registry has been empty at every merged commit, including `I3`.
- It **does not** extend to `I3`, to this revised text, or to `G3`. Because the
  approved implementation revision and this document's bytes both changed, the
  `G2` binding is no longer applicable and a **fresh** owner comment on this new
  governance PR is required (§5).

### 0.3 PR #61 is superseded for this route and must not be merged

PR #61 ("`A2` registry-only activation") was the **old** registry-only activation
candidate built on the `I2`/`G2` pair. It remains **OPEN**, is **not** part of
this route, and must **not** be merged into the `I3`/`G3` sequence: its record
would bind the superseded implementation revision `I2`, the superseded
governance baseline `G2`, and the superseded `G2` document digest. This PR does
not modify, merge, close, or otherwise touch PR #61. A future activation must
start from the actual merged `G3` (see §5.3).

### 0.4 Activation and real-bundle execution have NOT occurred

No diagnostic activation exists. No real-bundle diagnostic inference has ever
been executed under this scope, in Arena or anywhere else. The only real-bundle
work ever authorized on this artifact was the `AI2-OPERATIONAL-SCOPE-001`
training/packaging run at `A`, which explicitly prohibits inference (§1). Every
test in this repository is synthetic.

### 0.5 Relationship to doc 17 and stale status lines

`17_ai2_operational_scope_amendment.md` is retained exactly as written as the
**historical pre-ratification proposal snapshot**; its own "PROPOSED /
UNRATIFIED / NOT ACTIVATED" header describes the 2026-10-26 moment before the
`G -> A` training authorization was completed. It is not a current-status
statement about this project, and it is not edited by this PR. Status statements
in *this* document are scoped to the `G3` revision only.

## 1. Why a new authorization is required

`AI2-OPERATIONAL-SCOPE-001` (ratified at `G = 7f4b7a50d7fd423914e5bd98ed2b525bddbfc627`,
activated registry-only at `A = 1c29c83cd07fcb0510ac37e185323c231b267670`) authorized
exactly two operations on real Cleveland data: `persistent_model_packaging` and
`patient_level_shap_background`. Its §9 states explicitly that **no call to
`ResearchCadPredictor`, the `python -m ai predict` path, or any serving/UI path is
permitted for this real bundle, even though trusted loading is used as an
acceptance check**. The maintainer subsequently completed exactly one guarded
real-data run at `A`; the private bundle exists only on the maintainer's Windows
workstation. Producer authentication, trusted local bundle verification and
post-run acceptance are maintainer-reported facts, not Arena-verified evidence.

A training authorization is not an inference authorization. The existing
`python -m ai` CLI is intentionally synthetic-only and rejects real-provenance
bundles before `joblib.load`; that restriction must not be weakened. Diagnostic
inference on the accepted bundle therefore needs a **third, independently
authorized operation**, enforced by a **separate empty registry** and a separate
guarded interface.

The independent gate is still closed. The historical `G2` ratification of §2
does not open it: the trusted registry has never held a record, and a
registry-only activation bound to a superseded baseline must not be created.

## 2. Smallest technically defensible scope (unchanged by this revision)

Requested decision: permit **one** new operation,

```
offline_synthetic_input_diagnostic_inference
```

defined as bounded, local, offline, research-only diagnostic inference on the
single already-accepted bundle, using **explicitly fabricated synthetic input
records only**. The operation reuses `ResearchCadPredictor`, existing model
validation, OOF logistic calibration, exact SHAP, and genuine tabular LIME with
its registered quality policy. It adds no model, dataset, cohort, feature,
hyperparameter, target, or claim.

**Closed scope (all must hold; code fails closed otherwise):**

- one bundle: `cai_real_cleveland_d047_20261027T070610Z_deffa577` (interpreted as
  the bundle directory basename; if the accepted artifact is stored under any
  other basename, activation must NOT proceed without a new decision);
- exact `manifest.json` SHA-256 pinned in the trusted activation record;
- `DA-A2` / UCI-45 processed Cleveland (303 records), panel
  `da_a2_resting_v1` (`age`, `sex`, `cp`, `trestbps`, `restecg`; contract SHA-256
  `c18ad4cd2cf08f6fefb2e340573760da7000bc1d8eb4ad38783b873c018e57b8`);
- frozen profile `CLEVELAND_D047_FROZEN_V1`, selected `l2_logistic_regression`,
  `C = 10.0`, model id `cai_real_da-a2_da_a2_resting_v1`, protocol
  `CAI-D047-CLEVELAND-EXPLORATORY-V1`, version `0.2.0`;
- existing post-run acceptance marker binding the directory name and source
  SHA-256; no quarantine marker; trusted-local-root containment, verified
  platform ACL (including native Win32 NTFS DACL), SHA-256 digests, and
  HMAC-SHA256 producer authentication before any `joblib.load`;
- a clean checkout at the real activation revision `A3` (declared only in the
  ignored local operator authorization, never in tracked code), an approved
  implementation revision `I3` that is an ancestor of the governance baseline
  `G3` with only documentation changed in between, `G3` ancestry of HEAD, an
  exactly registry-only `G3 -> A3` diff, and frozen governance-document bytes
  at `G3`;
- explicit local operator authorization document + exact operator confirmation
  phrase on every invocation;
- at most 8 explicitly fabricated synthetic records per invocation, each
  validated against the five-field schema, finite values, registered units,
  categorical codes and missingness reasons;
- strictly offline and private: no API serving, no HTTP backend import, no
  telemetry, no uploads, no cloud SDK, no network primitive, no output file
  writes, no bundle writes, no logging of patient-derived values or local paths;
- no retraining, tuning, recalibration, packaging, regeneration, or modification
  of the accepted bundle.

**Still prohibited:** any real patient record as an *input*; any other bundle,
panel, cohort or pooled evaluation; any serving/UI/FastAPI integration; clinical
diagnosis, triage, medical decisions, or patient-facing predictions; model
sharing or public sharing of patient-derived artifacts; external-validation, clinical-validity, deployability, supervisor,
ethics or institutional approval claims; any relaxation of the general
`python -m ai` synthetic-only CLI; any relaxation of LIME quality gating; any
automatic retry of a failed diagnostic invocation without a new human decision.

This scope is **unchanged** between the `G2` and `G3` revisions. The `G3`
re-baseline changes only the approved implementation revision and the document
bytes a future activation would bind. It does not widen the operation, add a
dataset, panel, feature, or cohort, and does not extend the authorization to
UCI-412, Hungary, laboratory panels, AngioCAD, or any other route; the broader
multi-dataset strategy recorded elsewhere remains intact and outside this PR.

## 3. Immutable bindings and maintainer-supplied evidence

| Binding | Value |
|---|---|
| Frozen training activation revision `A` | `1c29c83cd07fcb0510ac37e185323c231b267670` |
| Ratified training governance merge `G` | `7f4b7a50d7fd423914e5bd98ed2b525bddbfc627` |
| Ratified training amendment document SHA-256 | `4c1d595534fd9a642a895cc59c01d4d81fbf5b84cf38ec3da5edcb7dd2d82890` |
| Frozen source SHA-256 | `a74b7efa387bc9d108d7d0115d831fe9b414b29ae7124f331b622b4efa0427c8` |
| Frozen protocol SHA-256 | `96c26829ff73893dab8ee091b2eaea1592479a1e0528ae6832651a9688ea3c86` |
| Accepted bundle identifier | `cai_real_cleveland_d047_20261027T070610Z_deffa577` |
| Accepted bundle `manifest.json` SHA-256 | `089f931be27be67606b9d2622beea54208976f1743a70909029619f50a6e5d4a` (maintainer-computed; not independently verified by Arena; **unchanged** by this re-baseline) |
| Historical approved implementation revision `I2` | `40b544be79acc9099e565a0ede183e9b376a238f` (PR #59 merge; superseded as the activation binding) |
| Historical governance baseline `G2` | `44f06091602f66078726fcc3b62b6ee1305abd83` (PR #60 merge; superseded as the activation binding) |
| Approved implementation and test baseline `I3` | `87bccd6d3ef2331f1e2b2ba8905f34366734538d` (PR #62 merge commit) |
| Governance baseline `G3` | **not yet known**; the actual merge commit of this PR, read from GitHub after the human-reviewed merge. Never precomputed here. |
| Governance document digest at `G3` | **not yet known**; SHA-256 of this file's raw committed bytes at `G3`, computed **after** the merge (§5.3). The historical digest computed for the `G2` bytes is **not** reused and is deliberately not reproduced here. |
| Activation revision `A3` | **not yet known**; exists only after the future registry-only activation merge and lives **only** in the ignored local operator authorization. |

The maintainer reports `POST_RUN_ACCEPTANCE.json` PRESENT,
`QUARANTINED_DO_NOT_TRUST.json` ABSENT, producer authentication PASSED, and
trusted local bundle verification PASSED. The supplied manifest digest is an
exact proposed binding, not permission to use a different bundle if a later
read-only Windows check disagrees. Arena has no source dataset, real bundle,
private signing key, or patient data. The existing bundle must remain unchanged.

The following are **maintainer-reported aggregate results** only. Arena did not
reproduce, recompute, or verify them and does not possess the private bundle or
patient data. They are recorded here for provenance, not as validation evidence.

| Maintainer-reported aggregate | Value |
|---|---|
| Selected model / C | `l2_logistic_regression` / `10.0` |
| Outer-fold selections | LR 19/20, RF 1/20 |
| Full-development selection CV AUROC | LR 0.8506368245951579; RF 0.8415001954064454 |
| Uncalibrated nested-CV AUROC | 0.8270913756799438 |
| Cross-fitted calibrated nested-CV AUROC | 0.8283086945078083 |
| Uncalibrated / calibrated Brier | 0.16711107041726933 / 0.16636301716903118 |
| Calibrated ECE | 0.0486638349597261 |
| Max permuted AUROC / ceiling / alarm | 0.5111861730128093 / 0.65 / false |

## 4. Completed implementation versus proposed operational permission

**Completed at `I2` (PR #59):** added two new, separately versioned modules
(`ai/diagnostic_scope.py`, `ai/diagnostic_inference.py`,
`cardioassist.ai.bounded_offline_diagnostic_inference/v1.1`), a separate CLI entry
point, example templates, comprehensive synthetic-fixture and negative tests,
this proposal, a security/failure-mode review and a gated Windows procedure, and
replacement assertions for the two obsolete pre-activation sentinel tests. The
new registry was committed **empty**.

**Repaired at `I3` (PR #62, tests only):** six files under
`tests/experiments/` were changed to make the activation regressions
lifecycle-state aware, so they stay meaningful **both** while the diagnostic
registry is empty (the actual, current state) and after a future registry-only
activation adds exactly one record:

- `tests/experiments/diagnostic_fixtures.py` now locates and replaces the
  registry value with the **production** parser (`_registry_value_span`) instead
  of an empty-registry-only regex, and self-checks that the substituted source
  reads back as exactly the requested literal with byte-identical masked source;
  the synthetic baseline is constructed with an explicitly empty registry before
  the synthetic activation commit is built.
- `tests/experiments/test_ai_diagnostic_scope.py` replaces the obsolete
  "the production diagnostic registry is empty" sentinel with lifecycle
  regressions: the in-process registry equals the checked-in literal and holds
  at most the one reviewed scope; the unactivated state still fails closed with
  `diagnostic_scope_not_ratified` before any bundle work; the activated state
  still enforces the local authorization comparison, the Git-history
  activation binding, the operator confirmation phrase and the pre-bundle
  refusals; unknown/bare scope ids fail closed in every state.
- `tests/experiments/test_ai_cli.py` and
  `tests/experiments/test_cleveland_d047_fidelity.py` replace the
  `RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES == {}` sentinels with lifecycle
  assertions (at most the single diagnostic scope; any record must authorize
  exactly `offline_synthetic_input_diagnostic_inference` and must not reuse the
  training `G`, the frozen `A`, or training governance PR #54).
- `tests/experiments/test_ai_diagnostic_inference.py` stops mutating the
  production registry in-process (`.clear()`) and uses `monkeypatch`, so the
  unactivated fail-closed CLI proof restores the real checkout state.
- `tests/experiments/test_ai_diagnostic_activation_feasibility.py`: docstring
  accuracy only.

**Verified property of `I3`:** `G2..I3` is **tests-only**
(`git diff --name-status G2 I3` lists exactly the six
`tests/experiments/*.py` files above), and `I2..I3` contains only that `G2`
documentation change plus those six test files — nothing under `ai/`,
`backend/`, `shared/`, `research/`, `scripts/`, `.github/workflows/`, or the
example templates changed. The production runtime bytes at `I3` are therefore
identical to the reviewed implementation, and
`RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES` is still `{}` at `I3`.

All tests use synthetic bundles trained in memory and re-signed with
authorization-shaped metadata; no real bundle, real dataset, real patient
record, or real signature is present.

**Evidence status, stated precisely.** At handoff it was reported that (a) the
unactivated implementation plus the repaired tests passed **2038 passed, 1
skipped**, and (b) the PR #61 production bytes plus the same repaired test
overlay passed **2038 passed, 1 skipped**; the reviewer independently confirmed
that all four GitHub workflows succeeded on PR #62's reviewed head. Those are
reported and reviewer-verified results, not runs reproduced by this docs-only
PR.

This session re-ran the suites locally in Arena (synthetic only; the production
registry empty throughout): at `I3`, `tests/experiments` gave **404 passed, 1
skipped**; on this docs-only `G3` candidate the full tree gave **2038 passed, 1
skipped** (`tests/contracts` 249, `tests/backend` 581, `tests/audit` 430,
`tests/uci412` 374, `tests/experiments` 404 + 1 skipped), and the focused
diagnostic/CLI/fidelity files gave **257 passed**. Local runs are not GitHub CI:
the actual CI result for this PR must be read from the PR's checks.

**Neither the historical `I2` approval, the `G2` ratification, the `I3` test
repair, nor this `G3` proposal grants operational permission.** This docs-only
`G3` proposal does not ratify anything; create or forge a maintainer comment,
local operator authorization, or human signature; populate either registry with
a new record; change `ai/execution.py` (the frozen `A` training registry) or
`ai/cli.py` (synthetic-only CLI); perform any real-bundle inference in Arena;
retrain, tune, regenerate, or modify the accepted bundle; or claim any new
performance, clinical, or external-validation result.

## 5. Honest separation: scope authorization (`G3`) then activation (`A3`)

Two independent human decisions are required, in this order. **Neither is taken
by the agent.** This PR proposes the first decision only for the new baseline; it
remains unratified until the maintainer explicitly accepts **this exact revised
content** after review. `I3` test-repair approval alone authorizes no diagnostic
operation. `G3` ratification alone is still insufficient to run anything.

### 5.0 Three revision names with exact, non-circular meanings

| Name | Tracked/local field (schema unchanged, still v1.1) | Where stored | Meaning |
|---|---|---|---|
| `I3` | `approved_implementation_commit_sha` | tracked registry at `A3` + ignored local authorization | The **approved implementation and test revision**: `87bccd6…`, frozen before ratification. Must be an ancestor of (or equal to) `G3`, with only `docs/` changes between `I3` and `G3`. |
| `G3` | `governance_baseline_commit_sha` | tracked registry at `A3` + ignored local authorization | The **governance baseline**: the immutable commit whose tree contains both the approved implementation and the ratified `G3` document. Its document bytes are bound by `frozen_governance_document_sha256`; it is the baseline of the registry-only diff. |
| `A3` | `activation_merge_commit_sha` | **ignored local operator authorization ONLY** | The **activation revision**: the registry-only commit that adds exactly one reviewed entry. Its SHA exists only after the commit and therefore CANNOT appear in any tracked file. Runtime resolves HEAD independently and requires `HEAD == A3`. |

The historical sequence used the same mechanism with the names `I2`/`G2`/`A2`.
The names are labels for a revision sequence; the **schema and the validator are
unchanged**. Nothing in this document asks for a new field, a new interface
version, or a code change.

**The self-reference defect that was removed.** An earlier design put
`approved_code_revision = A2` inside the tracked registry and required
`HEAD == approved_code_revision`. A commit cannot contain its own SHA-1 in its
tracked contents: writing that field changes the commit SHA. The v1.1 design
therefore has NO tracked activation field. `RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES`
contains only previously known values (`I3`, `G3`, the document hash at `G3`,
the maintainer's bundle manifest digest, the operation and bundle identity).
A tracked record containing `approved_code_revision`,
`activation_merge_commit_sha` or `activation_revision_commit_sha` is rejected
with `diagnostic_scope_registry_self_referential`. This mirrors the already
proven Cleveland D-047 `G -> A` pattern, where `A` is carried by the ignored
local authorization and checked against independently resolved HEAD.

### 5.1 Step 1 — Scope authorization for the new baseline (governance, human only)

The maintainer reviews **this final document** (and this PR's complete docs-only
diff) after the PR is open and its checks are visible, accepts or rejects the
single new operation in §2 as re-based on `I3`, and — only if accepting — posts
the exact owner ratification comment on **this new governance PR**:

```
RATIFY-BOUNDED-OFFLINE-DIAGNOSTIC-INFERENCE-SCOPE
```

Rules that must not be relaxed:

- The **same exact comment string** is used, but the PR #60 comment
  (<https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/60#issuecomment-6442269752>)
  is **not** approval of this revised text, of `I3`, or of `G3`. It is historical
  evidence for the `G2` text only.
- The agent must not post the comment, self-ratify, or merge the PR. A green CI
  run, a merge without the exact comment, or an approval of an earlier revision
  of the branch is not ratification.
- If **substantive** changes are pushed after the new comment, that comment no
  longer covers the content: review and **renewed human confirmation of the
  revised content** are required before merge.
- The exact comment, its timestamp, the PR's merged state, the full `G3` merge
  SHA, and the frozen SHA-256 of this document's bytes at `G3` are human-verified
  evidence that code cannot obtain from GitHub.

**After the merge, and only then**, the ratification is complete and the
following evidence handoff applies (§5.3).

### 5.2 Step 2 — Registry-only activation (separate future PR, human only)

A second PR, based on the **actual merged `G3`** (not on `I2`, `G2`, or `I3`),
changes **only** `ai/diagnostic_scope.py::RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES`,
adding exactly one record that binds:

- the **governance PR number** of this PR, `governance_baseline_commit_sha = G3`,
  `approved_implementation_commit_sha = I3`, the owner's `ratified_by` identity
  and `ratification_comment_exact` string;
- **NO** `approved_code_revision`, `activation_merge_commit_sha` or any other
  activation-revision field: `A3` is not knowable until after that commit is
  merged, and is supplied later only by the ignored local operator
  authorization;
- `governance_document_relative_path` (fixed by code to this file:
  `docs/research/gate-pt/18_bounded_offline_diagnostic_inference_scope.md`) and
  `frozen_governance_document_sha256` = the SHA-256 of this document's **exact
  bytes at `G3`**;
- `approved_operations = ("offline_synthetic_input_diagnostic_inference",)`;
- `expected_manifest_sha256 =
  089f931be27be67606b9d2622beea54208976f1743a70909029619f50a6e5d4a`,
  supplied by the maintainer and reconfirmed read-only on Windows before
  activation;
- the frozen bundle identity from §3 (unchanged by this re-baseline).

Before pinning those values, the maintainer must read (never modify) the
accepted `manifest.json` on Windows and confirm its
`model.model_id`, `model.model_version`, `model.protocol_id`,
`model.selected_model_family`, `model.execution_profile`,
`model.selected_hyperparameters.C`, `panel_contract.panel_id`,
`panel_contract.contract_sha256` and `panel_contract.ordered_feature_names`
equal the frozen identity in §2. Any mismatch stops activation and requires a
new human decision; the registry must not be broadened to accommodate it.

The `G3..A3` review must confirm that the ONLY changed path is
`ai/diagnostic_scope.py` and that the only change inside it is the
`RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES` value changing from `{}` to exactly one
literal record (no computed values, no other code changes). Code independently
enforces: `HEAD == A3` from the ignored local authorization; a clean tracked
worktree; `I3` ancestry of `G3` with documentation-only changes in between;
`G3` ancestry of HEAD; the `G3 -> A3` single-file diff; the strict masked-source
equality of the registry file (so activation cannot weaken any validation,
inference, CLI or security logic); the literal committed registry equalling the
in-process registry; frozen governance-document bytes at `G3`; every local
authorization claim matching the trusted record; and the exact scope/identity
bindings and custody gates. Wrong/stale `A3`, a dirty worktree, an extra changed
file, an extra code change in the registry file, missing `G3` ancestry, a wrong
document hash, a forged scope or an incorrect bundle digest all fail closed. A
genuine committed `I3 -> G3 -> A3` pytest history (not an injected dictionary
alone) exercises the complete happy path and each negative case.

**Why two steps:** ratification decides *whether* the operation may ever exist;
activation decides *which exact reviewed code revision and which exact accepted
artifact* may execute it. Bundling them would let an engineering PR silently
authorize real-bundle inference. Neither step can be simulated by a local
authorization, a CI run, an HMAC token, or a previous training authorization.

### 5.3 Exact post-merge evidence handoff (who does what, in order)

1. **This PR (`G3`) must be docs-only.** A maintainer review of
   `git diff --name-status I3 <this branch>` must show only `docs/` paths
   (`docs/DECISIONS.md`, this document, `19_…runbook.md`).
2. **The registry must still be `{}` at `G3`.** `RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES`
   is unchanged by this PR; no activation record exists at `G3`.
3. **Merge by a human only**, after the exact owner comment in §5.1. Then read
   the **actual** `G3` merge commit SHA from GitHub. Do not substitute this PR's
   head commit, and do not precompute `G3` anywhere in tracked content.
4. **Hash this document's raw committed bytes at `G3`, without newline or
   encoding conversion** — including on Windows:

   ```text
   git show G3:docs/research/gate-pt/18_bounded_offline_diagnostic_inference_scope.md > <tempfile>
   # then SHA-256 the raw bytes of <tempfile> (e.g. Get-FileHash -Algorithm SHA256)
   # equivalently, on a shell with byte-exact pipes:
   git show G3:docs/research/gate-pt/18_bounded_offline_diagnostic_inference_scope.md | sha256sum
   ```

   The value must be computed from bytes `git show` emits, not from an editor's
   saved copy. **Do not reuse the digest that was computed for the `G2` bytes**:
   this revision's content differs, so that digest is invalid. **Do not insert
   this document's own digest into this document** — the digest of `G3` bytes
   cannot appear inside the `G3` bytes it hashes.
5. **The activation PR (`A3`) starts from `G3`** and changes only the registry
   value, per §5.2.
6. **The activation record binds**: `I3`, `G3`, this governance PR's number, the
   exact `G3` document SHA-256, the owner identity and exact ratification
   comment, and the **unchanged** artifact identity (bundle basename, manifest
   SHA-256, panel contract, profile, model identity).
7. **The actual `A3` belongs only in the ignored local operator authorization**
   (`activation_merge_commit_sha`), never in a tracked file.
8. **Runtime must use a clean checkout of exactly `A3`** (`git rev-parse HEAD == A3`,
   empty `git status --porcelain --untracked-files=no`).
9. **PR #61's old record is superseded for this route** and must not be merged;
   no part of its `I2`/`G2` binding may be carried into `A3`.

## 6. Local operator authorization and human controls code cannot supply

After both steps, each invocation still requires a private, Git-ignored local
JSON document (template:
`ai/examples/diagnostic_authorization.template.json`) declaring: the ratified
scope and all `I3`/`G3`/`A3`/document-hash bindings (where `A3` is present only
here, never in tracked code), the single approved operation,
`supervisor_signoff_claimed: false`, an explicit human attestation
(`SYNTHETIC_INPUTS_ONLY`, `NO_PATIENT_DATA`, `NO_CLINICAL_USE`, `OFFLINE_ONLY`),
a named local signer and ISO-8601 timestamp, the exact bundle identity including
the pinned manifest digest, the synthetic-only input declaration, and the
offline/no-serving/no-telemetry/no-upload/no-write execution boundary. The
operator must also supply the exact confirmation phrase on the command line:

```
I_CONFIRM_BOUNDED_OFFLINE_CLEVELAND_D047_DIAGNOSTIC_INFERENCE
```

**A local authorization document is an attestation, not a cryptographic
signature.** Code cannot prove signer identity, authority, intent, GitHub comment
authenticity, PR merged state, external legal/institutional duties, license/privacy
compliance, or secure custody of the signing key and private artifacts. Those
remain human responsibilities. No such evidence is fabricated by this PR.

## 7. Execution-permit checklist (all unchecked)

- [ ] Maintainer accepted this exact `G3` revision of §2 and the §5 two-step
      separation (a NEW decision; the PR #60 comment does not satisfy it).
- [ ] Exact owner ratification comment posted on **this** governance PR for its
      final content; PR merged by a human; full `G3` and this document's bytes at
      `G3` independently verified.
- [ ] `I3` verified as an ancestor of `G3`; `I3..G3` diff verified docs-only;
      diagnostic registry verified EMPTY at `G3`.
- [ ] Governance document SHA-256 recomputed from the raw `G3` bytes (never
      reused from `G2`, never inserted into this document).
- [ ] No known applicable external legal/institutional/license duty unsatisfied.
- [ ] Separate registry-only activation PR (`A3`) started from `G3`, reviewed and
      merged; full `A3` verified; `G3..A3` diff modifies only
      `ai/diagnostic_scope.py::RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES`.
- [ ] Maintainer computed and pinned the accepted bundle's `manifest.json`
      SHA-256 on the private Windows workstation; bundle unchanged since `A`.
- [ ] Clean checkout at `A3`; `git rev-parse HEAD` equals the actual `A3`
      written into the ignored local operator authorization; `I3`/`G3`
      independently verified as ancestors; native Windows preflight/ACL/key
      custody confirmed;
      `POST_RUN_ACCEPTANCE.json` present; no quarantine marker.
- [ ] Local operator authorization attested by a human after `G3` and `A3`,
      carrying `governance_baseline_commit_sha = G3`,
      `approved_implementation_commit_sha = I3`,
      `activation_merge_commit_sha = A3`,
      `activation_registry_relative_path = ai/diagnostic_scope.py` and the
      pinned manifest digest; exact operator confirmation supplied at
      invocation.
- [ ] Input file contains only explicitly fabricated synthetic five-field records.
- [ ] **Post-run:** report inspected; LIME weights used only when
      `feature_weights_trusted` is true; no serving, sharing, clinical claim,
      upload, or automatic retry; any failure preserved for human audit.

## 8. Status and non-claims

This proposal changes **no** gate status: P-1 remains PENDING, P-3 remains
CLOSED, P-4/P-5 unopened. It is a project-internal engineering/governance
decision only, not supervisor, ethics, institutional, regulatory, or data
protection approval. It does not assert anonymity of the historical UCI-45
records or of patient-derived SHAP backgrounds, and it authorizes no
redistribution of any patient-derived artifact. The accepted bundle and the
frozen training revision `A` are preserved unchanged.

Explicitly, at `I3` and on this PR:

- **No activation exists.** `RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES` is `{}` and
  no `A2`/`A3` registry-only commit has been merged.
- **No real-bundle inference has occurred.** No diagnostic invocation on the
  accepted bundle was run in Arena or elsewhere, and none is authorized by this
  PR.
- **No model, test, workflow, example, registry, dataset, bundle, key, or local
  operator authorization file was changed** by this docs-only PR.
- **No supervisor, ethics, institutional, clinical, or external-validation
  approval is claimed**, and the broader multi-dataset AI strategy is untouched
  and outside this PR.

Until `G3` is ratified and merged, `A3` exists, and §6/§7 are satisfied, all
real-bundle inference remains disabled.
