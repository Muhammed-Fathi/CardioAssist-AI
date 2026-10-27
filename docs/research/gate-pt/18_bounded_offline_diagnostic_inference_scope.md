# Bounded Offline Diagnostic Inference Scope — Cleveland D-047 Accepted Bundle

- **Decision ID:** `CAI-SCOPE-BOUNDED-OFFLINE-DIAGNOSTIC-INFERENCE-CLEVELAND-D047-V1`
- **Engineering PR:** AI-6.1 (this branch; OPEN for maintainer review)
- **Status:** **PROPOSED / NOT RATIFIED / NOT ACTIVATED / NO REAL-BUNDLE INFERENCE AUTHORIZED**
- **Date:** 2026-10-27
- **Gate PT:** P-1 PENDING; P-3 CLOSED; P-4/P-5 not opened
- **Supersedes:** nothing. It **narrows, but does not reinterpret**, the inference prohibition in `17_ai2_operational_scope_amendment.md` §9, and only if separately ratified and activated as described in §5.

> This document is a governance proposal, not an authorization. No maintainer
> comment, ratification merge `G2`, activation merge `A2`, local operator
> manifest, or human signature is created or claimed by the engineering PR. The
> production diagnostic registry `ai/diagnostic_scope.py::RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES`
> is **EMPTY**. Until §5 completes, every real-bundle diagnostic invocation
> fails closed with `diagnostic_scope_not_ratified` before any bundle is verified
> or deserialized.

## 1. Why a new authorization is required

`AI2-OPERATIONAL-SCOPE-001` (ratified at `G = 7f4b7a50d7fd423914e5bd98ed2b525bddbfc627`,
activated registry-only at `A = 1c29c83cd07fcb0510ac37e185323c231b267670`) authorized
exactly two operations on real Cleveland data: `persistent_model_packaging` and
`patient_level_shap_background`. Its §9 states explicitly that **no call to
`ResearchCadPredictor`, the `python -m ai predict` path, or any serving/UI path is
permitted for this real bundle, even though trusted loading is used as an
acceptance check**. The maintainer subsequently completed exactly one guarded
real-data run at `A`; the private bundle exists only on the maintainer's Windows
workstation and passed producer authentication, HMAC/NTFS verification, and
post-run acceptance.

A training authorization is not an inference authorization. The existing
`python -m ai` CLI is intentionally synthetic-only and rejects real-provenance
bundles before `joblib.load`; that restriction must not be weakened. Diagnostic
inference on the accepted bundle therefore needs a **third, independently
authorized operation**, enforced by a **separate empty registry** and a separate
guarded interface.

## 2. Smallest technically defensible scope

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
- a clean checkout at the real activation revision `A2` (declared only in the
  ignored local operator authorization, never in tracked code), an approved
  implementation revision `I2` that is an ancestor of the governance baseline
  `G2` with only documentation changed in between, `G2` ancestry of HEAD, an
  exactly registry-only `G2 -> A2` diff, and frozen governance-document bytes
  at `G2`;
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
diagnosis, triage, or patient-facing use; public sharing of patient-derived
artifacts; external-validation, clinical-validity, deployability, supervisor,
ethics or institutional approval claims; any relaxation of the general
`python -m ai` synthetic-only CLI; any relaxation of LIME quality gating; any
automatic retry of a failed diagnostic invocation without a new human decision.

## 3. Immutable bindings and maintainer-supplied evidence

| Binding | Value |
|---|---|
| Frozen training activation revision `A` | `1c29c83cd07fcb0510ac37e185323c231b267670` |
| Ratified training governance merge `G` | `7f4b7a50d7fd423914e5bd98ed2b525bddbfc627` |
| Ratified training amendment document SHA-256 | `4c1d595534fd9a642a895cc59c01d4d81fbf5b84cf38ec3da5edcb7dd2d82890` |
| Frozen source SHA-256 | `a74b7efa387bc9d108d7d0115d831fe9b414b29ae7124f331b622b4efa0427c8` |
| Frozen protocol SHA-256 | `96c26829ff73893dab8ee091b2eaea1592479a1e0528ae6832651a9688ea3c86` |
| Accepted bundle identifier | `cai_real_cleveland_d047_20261027T070610Z_deffa577` |
| Accepted bundle `manifest.json` SHA-256 | **unknown in Arena; maintainer-supplied at activation** |

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

## 4. What the engineering PR does and does not do

**Does:** add two new, separately versioned modules
(`ai/diagnostic_scope.py`, `ai/diagnostic_inference.py`,
`cardioassist.ai.bounded_offline_diagnostic_inference/v1.1`), a separate CLI entry
point, example templates, comprehensive synthetic-fixture and negative tests,
this proposal, a security/failure-mode review and a gated Windows procedure, and
replacement assertions for the two obsolete pre-activation sentinel tests. The
new registry is committed **empty**. All tests use synthetic bundles trained in
memory and re-signed with authorization-shaped metadata; no real bundle, real
dataset, real patient record, or real signature is present.

**Does not:** ratify anything; create or forge a maintainer comment, local
operator manifest, or human signature; populate either registry with a new
record; change `ai/execution.py` (the frozen `A` training registry) or
`ai/cli.py` (synthetic-only CLI); perform any real-bundle inference in Arena;
retrain, tune, regenerate, or modify the accepted bundle; or claim any new
performance, clinical, or external-validation result.

## 5. Honest separation: scope authorization (`G2`) then activation (`A2`)

Two independent human decisions are required. **Neither is taken by this PR.**

### 5.0 Three revision names with exact, non-circular meanings

| Name | Field | Where stored | Meaning |
|---|---|---|---|
| `I2` | `approved_implementation_commit_sha` | tracked registry at `A2` + ignored local authorization | The **approved implementation revision**: the reviewed diagnostic code, frozen before ratification. Must be an ancestor of (or equal to) `G2`, with only `docs/` changes between `I2` and `G2`. |
| `G2` | `governance_baseline_commit_sha` | tracked registry at `A2` + ignored local authorization | The **governance baseline**: immutable commit whose tree contains both the approved implementation and the ratified governance document. Its document bytes are bound by `frozen_governance_document_sha256`; it is the baseline of the registry-only diff. |
| `A2` | `activation_merge_commit_sha` | **ignored local operator authorization ONLY** | The **activation revision**: the registry-only commit that adds exactly one reviewed entry. Its SHA exists only after the commit and therefore CANNOT appear in any tracked file. Runtime resolves HEAD independently and requires `HEAD == A2`. |

**The self-reference defect that was removed.** An earlier design put
`approved_code_revision = A2` inside the tracked registry and required
`HEAD == approved_code_revision`. A commit cannot contain its own SHA-1 in its
tracked contents: writing that field changes the commit SHA. The v1.1 design
therefore has NO tracked activation field. `RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES`
contains only previously known values (`I2`, `G2`, the document hash at `G2`,
the maintainer's bundle manifest digest, the operation and bundle identity).
A tracked record containing `approved_code_revision`,
`activation_merge_commit_sha` or `activation_revision_commit_sha` is rejected
with `diagnostic_scope_registry_self_referential`. This mirrors the already
proven Cleveland D-047 `G -> A` pattern, where `A` is carried by the ignored
local authorization manifest and checked against independently resolved HEAD.

**Step 1 — Scope authorization (governance, human only).** The maintainer
reviews this exact document and the engineering PR, accepts or rejects the
single new operation in §2, and — only if accepting — posts an exact owner
ratification comment on the governance PR. The proposed (NOT yet posted)
comment string is:

```
RATIFY-BOUNDED-OFFLINE-DIAGNOSTIC-INFERENCE-SCOPE
```

The governance PR is then merged, producing `G2`. The exact comment, its
timestamp, PR merged state, full `G2`, and the frozen SHA-256 of this document
at `G2` are human-verified evidence that code cannot obtain from GitHub.

**Step 2 — Registry-only activation (separate PR, human only).** A second PR,
based on the merged engineering revision, changes **only**
`ai/diagnostic_scope.py::RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES`, adding exactly
one record with:

- the governance PR number, `governance_baseline_commit_sha = G2`,
  `approved_implementation_commit_sha = I2`, exact owner comment and signer;
- **NO** `approved_code_revision`, `activation_merge_commit_sha` or any other
  activation-revision field: `A2` is not knowable until after this commit is
  merged, and is supplied later only by the ignored local operator
  authorization document;
- `governance_document_relative_path` and `frozen_governance_document_sha256`
  of this document's exact bytes at `G2`;
- `approved_operations = ("offline_synthetic_input_diagnostic_inference",)`;
- `expected_manifest_sha256` computed **by the maintainer on Windows** from the
  accepted bundle's `manifest.json` (read-only; never supplied by Arena);
- the frozen bundle identity from §3.

Before pinning those values, the maintainer must read (never modify) the
accepted `manifest.json` on Windows and confirm its
`model.model_id`, `model.model_version`, `model.protocol_id`,
`model.selected_model_family`, `model.execution_profile`,
`model.selected_hyperparameters.C`, `panel_contract.panel_id`,
`panel_contract.contract_sha256` and `panel_contract.ordered_feature_names`
equal the frozen identity in §2. Any mismatch stops activation and requires a
new human decision; the registry must not be broadened to accommodate it.

The `G2..A2` review must confirm that the ONLY changed path is
`ai/diagnostic_scope.py` and that the only change inside it is the
`RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES` value changing from `{}` to exactly one
literal record (no computed values, no other code changes). Code independently
enforces: `HEAD == A2` from the ignored local authorization; a clean tracked
worktree; `I2` ancestry of `G2` with documentation-only changes in between;
`G2` ancestry of HEAD; the `G2 -> A2` single-file diff; the strict masked-source
equality of the registry file (so activation cannot weaken any validation,
inference, CLI or security logic); the literal committed registry equalling the
in-process registry; frozen governance-document bytes at `G2`; every local
authorization claim matching the trusted record; and the exact scope/identity
bindings and custody gates. Wrong/stale `A2`, a dirty worktree, an extra changed
file, an extra code change in the registry file, missing `G2` ancestry, a wrong
document hash, a forged scope or an incorrect bundle digest all fail closed. A
genuine committed `I2 -> G2 -> A2` pytest history (not an injected dictionary
alone) exercises the complete happy path and each negative case.

**Why two steps:** ratification decides *whether* the operation may ever exist;
activation decides *which exact reviewed code revision and which exact accepted
artifact* may execute it. Bundling them would let an engineering PR silently
authorize real-bundle inference. Neither step can be simulated by a local
manifest, a CI run, an HMAC token, or a previous training authorization.

## 6. Local operator authorization and human controls code cannot supply

After both steps, each invocation still requires a private, Git-ignored local
JSON document (template:
`ai/examples/diagnostic_authorization.template.json`) declaring: the ratified
scope and all `I2`/`G2`/`A2`/document-hash bindings (where `A2` is present only
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

**A local manifest is an attestation, not a cryptographic signature.** Code
cannot prove signer identity, authority, intent, GitHub comment authenticity,
PR merged state, external legal/institutional duties, license/privacy
compliance, or secure custody of the signing key and private artifacts. Those
remain human responsibilities. No such evidence is fabricated by this PR.

## 7. Execution-permit checklist (all unchecked)

- [ ] Maintainer accepted the exact §2 operation and §5 two-step separation.
- [ ] Exact owner comment posted on the governance PR; PR merged; full `G2` and
      this document's bytes at `G2` independently verified by a human.
- [ ] No known applicable external legal/institutional/license duty unsatisfied.
- [ ] Separate registry-only activation PR reviewed and merged; full `A2`
      verified; `G2..A2` diff modifies only
      `ai/diagnostic_scope.py::RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES`.
- [ ] Maintainer computed and pinned the accepted bundle's `manifest.json`
      SHA-256 on the private Windows workstation; bundle unchanged since `A`.
- [ ] Clean checkout at `A2`; `git rev-parse HEAD` equals the actual `A2`
      written into the ignored local operator authorization; `I2`/`G2`
      independently verified as ancestors; native Windows preflight/ACL/key
      custody confirmed;
      `POST_RUN_ACCEPTANCE.json` present; no quarantine marker.
- [ ] Local operator authorization document signed/attested by a human after
      `G2` and `A2`, carrying `governance_baseline_commit_sha = G2`,
      `approved_implementation_commit_sha = I2`,
      `activation_merge_commit_sha = A2`,
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
frozen training revision `A` are preserved unchanged. Until `G2` and `A2`
exist and §6/§7 are satisfied, all real-bundle inference remains disabled.
