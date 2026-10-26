# AI-3.1 — Proposed AI-2 Operational-Scope Amendment for the First Persistent Cleveland Research Bundle

- **Proposed amendment ID:** `CAI-AMEND-AI2-D047-PERSISTENT-RESEARCH-BUNDLE-V1`
- **Date:** 2026-10-26
- **Review baseline:** AI-2 merge `a47fbe0cb645fc4813b59672cf58d8c9100eaeb2`
- **Governance review:** PR #54, open and unmerged
- **Status:** **PROPOSED — NOT RATIFIED — NOTHING ACTIVATED — TECHNICAL ACTIVATION BLOCKER PRESENT**
- **Required output banner:** `INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED`
- **Gate status:** P-1 **PENDING**; formal Gate PT P-3 **CLOSED**; P-4 **PENDING**; P-5 **NOT MADE — prohibited**.

> This is a governance proposal and activation handoff, not an authorization. It does not populate `RATIFIED_OPERATIONAL_SCOPE_AMENDMENTS`, create or sign a local manifest, assert supervisor/ethics/institutional approval, or permit source parsing, fitting, calibration, SHAP persistence, packaging, inference, or serving. The merged registry remains empty. No patient record, source dataset, individual prediction, signing key, or private model bundle is included or requested.

## 1. Exact maintainer decision requested

The maintainer is asked to **APPROVE or REJECT only the following scoped decision**, not to give a blanket AI/data/clinical approval:

> After the technical stop condition in §4.1 has been resolved without changing the frozen D-047 methodology, authorize one controlled, Windows-local, CPU-only AI-2 execution on the already custodied DA-A2 processed Cleveland source, using `da_a2_resting_v1` and the exact bindings in §3. Permit the existing AI-1/AI-2 final development refit, cross-fitted research calibration/evaluation, and creation of at most one persistent `RESEARCH_ONLY` bundle containing the required patient-derived SHAP background. Keep the bundle and every derivative private and local. Make no formal P-1/P-3/P-4/P-5 decision and authorize no other cohort, panel, run, claim, inference, integration, or deployment.

An approval is **conditional**. It does not make the current AI-2 code protocol-compliant and must not be used for execution while §4.1 remains unresolved. Rejection or deferral leaves the existing block unchanged.

The only proposed ratification comment is:

```text
RATIFY-AI2-OPERATIONAL-SCOPE-EXPANSION
```

The comment must be written by the human maintainer on this governance PR before the human-approved merge. A merge, CI pass, agent statement, local manifest, or source hash alone is not approval. A second, registry-only activation stage after that merge is mandatory; see §7.

## 2. Governance and evidence assessment

### 2.1 What the existing records establish

- **D-047 route:** PR #31 records the repository owner's exact `AUTHORIZE-D047-INTERNAL-CLEVELAND` comment at `2026-10-22T23:06:19Z`, followed by merge `434e49a37e6e60b8b91498dde0f9d02dc1af18de` at `2026-10-22T23:06:35Z`. This supports a narrow maintainer-owned internal exploratory route on public benchmark data while formal P-3 remains closed. It is not supervisor approval.
- **D-047 protocol:** [`02_d047_internal_exploratory_cleveland_PROTOCOL_PROPOSED.md`](02_d047_internal_exploratory_cleveland_PROTOCOL_PROPOSED.md) permits a local exploratory final prototype only after the evaluation procedure is fixed, with local-only model/score custody. It does **not** explicitly authorize this AI-2 persistent bundle format or a reconstructible patient-derived SHAP background. Those are the new operations requiring this amendment.
- **Existing results:** [`04_d047_first_internal_results_REVIEW_DRAFT.md`](04_d047_first_internal_results_REVIEW_DRAFT.md) records maintainer-reported, sanitized internal aggregates from the earlier M2c runner. It expressly records **no saved final full-cohort artifact**, no external validation, unresolved calibration limits, and sample-size adequacy `NOT ASSESSED`. Therefore there is no prior model to package: this proposal necessarily involves a new fit, not merely saving an existing artifact. The earlier results must not be reused as AI-2 results or presented as clinical evidence.
- **Plan history:** the protocol blob is unchanged since D-047 ratification, but the registered plan changed before the first M2c fit. The current plan must therefore be bound by its actual hash below; it must not be described as byte-frozen at PR #31.
- **Maintainer-reported local preflight:** the AI-3.1 request reports that native Windows Git protected-storage, Cleveland D-047, and UCI-412 M3a preflights passed on merged main, including source SHA-256 and byte size, without source-row parsing or fitting. Those are useful local prerequisites, not independent evidence verified by this document and not authorization. Cleveland checks must be repeated at the eventual activation merge.

### 2.2 Is supervisor or institutional approval mandatory?

**For the exact internal exploratory operation in §1, supervisor approval is not inherently mandatory _if_ the maintainer expressly ratifies this new, separate D-047-style exception.** The maintainer cannot rely on D-047 alone: this amendment must explicitly extend the internal route to AI-2 persistent packaging and patient-derived SHAP persistence while retaining every internal-only restriction.

This conclusion requires an explicit reconciliation, not silent reinterpretation. [`AI_FIRST_COMPLETION_STRATEGY.md`](../AI_FIRST_COMPLETION_STRATEGY.md) §5.1 literally names P-1/P-3 before using `ai/` to fit/save a real-patient bundle or SHAP derivative. The narrower D-047 precedent permits maintainer-ratified internal exploratory work before supervisor review. **This PR requests a new, explicit exception for this one pilot; it does not claim that the AI-1 strategy has already been amended or that P-1/P-3 is satisfied.** Without that new maintainer ratification, the conservative existing position is that the AI-2 real bundle remains blocked and P-1/P-3 approval is required.

Supervisor and other authorized human review remains mandatory for any formal scientific target/protocol sign-off, supervisor-approved research, publication/novelty statement, external-validation claim, clinical performance or adequacy claim, patient/clinician use, serving, or deployment. No ethics or institutional approval is claimed. This document does not determine external legal, ethics, or institutional requirements; if any applies to the maintainer's setting, it must be satisfied independently and cannot be waived by this amendment.

### 2.3 Cohorts preserved

- **Initial pilot only:** `DA-A2`, UCI-45 `processed.cleveland.data`, `da_a2_resting_v1`.
- **Subsequent, separate cohort:** `DA-A1` UCI-412 remains independent, non-pooled, and outside this amendment. Its reported preflight pass activates nothing. UCI-411 is the same 303 participants as UCI-412 and is never an independent cohort.
- Hungary, Switzerland, VA Long Beach, Statlog, AngioCAD, UCI-411, every extended panel, and every pooled/external evaluation remain unauthorized.

## 3. Exact requested scope and provenance bindings

### 3.1 Dataset, target, and clinical panel

| Item | Frozen requested value |
|---|---|
| Dataset / source | `DA-A2`; official UCI-45; canonical local file `data/raw/uci-45/processed.cleveland.data` only |
| Source evidence | 303 records and 164/139 source-label counts are existing aggregate audit facts; actual source SHA-256 and byte size must match the protected D-046/D-047 local chain. The source hash is intentionally left for post-approval local verification, not guessed here. |
| Research target | Source-specific, cross-sectional angiography-referenced CAD grouping: `num=0` → 0 and `num∈{1,2,3,4}` → 1; not future/30-day risk, severity, or population screening |
| Panel | `da_a2_resting_v1`, panel version `1.0.0`, stage `resting_assessment` |
| Ordered predictors | `age`, `sex`, `cp`, `trestbps`, `restecg` |
| Panel contract SHA-256 at the review baseline | `c18ad4cd2cf08f6fefb2e340573760da7000bc1d8eb4ad38783b873c018e57b8` |
| Explicit exclusions | `num`, `ca`, `thal`, angiography/vessel/catheterization and post-outcome fields, identifiers, site, wearables, exercise/lab expansion, and every unregistered field |

The panel's historical source coding is preserved. No cross-dataset target harmonization or clinical timepoint certification is asserted.

### 3.2 Protocol, plan, model, and code bindings

| Binding | Required value / rule |
|---|---|
| D-047 governance evidence | PR #31; merge `434e49a37e6e60b8b91498dde0f9d02dc1af18de`; local D-047 `approval_pr_merged_commit_sha` and `pinned_protocol_git_commit_sha` remain this value |
| Frozen protocol | `docs/research/gate-pt/02_d047_internal_exploratory_cleveland_PROTOCOL_PROPOSED.md`; Git-blob SHA-256 `96c26829ff73893dab8ee091b2eaea1592479a1e0528ae6832651a9688ea3c86` |
| Registered plan | `research/experiments/cleveland_d047_exploratory_plan.v0.1.json`; Git-blob SHA-256 `2c441c4c44d61e2734277d3ee788ce09b5dd4cc8e54cbeff741374a428646c6a` |
| AI-2 review baseline | `a47fbe0cb645fc4813b59672cf58d8c9100eaeb2`; **not executable for this pilot while §4.1 is present** |
| AI-2 run identity | `CAI-D047-CLEVELAND-EXPLORATORY-V1`, model version `0.2.0`; the registered plan's distinct ID `CAI-T1-D047-CLEVELAND-EXPLORATORY-V0.1` must remain linked in the local run record, not silently treated as the same string |
| Nested evaluation | 5 outer × 5 inner stratified folds; four outer seeds `20261023, 20261024, 20261025, 20261026`; selection tolerance `0.01`; no outer-fold tuning |
| Candidates | Prevalence dummy; L2 logistic regression with `C={0.1,1,10}`; constrained RF with 200 trees, `max_depth={3,5}`, `min_samples_leaf={5,10}`, `max_features=sqrt` |
| D-047 estimator settings that must be restored/verified before activation | Logistic `solver=liblinear`, `max_iter=2000`, `class_weight=None`; registered inner/model seed derivation and label-shuffle outer seeds |
| Other existing AI-2 bounds | Three shuffle seeds `20262001, 20262002, 20262003`; shuffle leakage ceiling `0.65`; 250 bootstrap resamples; exploratory threshold `0.5`; SHAP background cap 64 |
| Final research-only operations | Existing full-development selection/refit, development-OOF logistic calibrator, separate uncalibrated and cross-fitted calibrated nested-CV summaries, apparent-calibrator diagnostic explicitly not promoted to unbiased evidence |
| Code at execution | Governance merge `G` must include the reviewed §4.1 correction. Activation merge `A` must add only the trusted registry entry. `approved_code_revision=G`; actual HEAD must independently equal `A` as specified in §7. No self-referential hash is permitted. |

No hyperparameter, fold, seed, panel, adapter, metric, or threshold change is authorized by this proposal. In particular, the AI-2 `lbfgs/1000` implementation must **not** be approved here as a silent substitute for D-047 `liblinear/2000`.

### 3.3 Permitted local research operations after every gate in this document passes

1. Hash-only source/preflight checks and read-only loading of the canonical Cleveland file.
2. One frozen-protocol internal fitting/evaluation attempt, including the registered nested CV, family comparison, label-shuffle control, cross-fitted calibration, final development refit, and aggregate-only evaluation summary.
3. Creation of at most one private persistent bundle and its mandatory patient-derived SHAP background, using a new empty output directory.
4. Local integrity, ACL, and HMAC producer verification without HTTP serving or patient-level prediction output.

A preflight failure before source-row parsing may be corrected and repeated. A leakage alarm, disappointing result, or desire to improve performance ends the attempt; no tuning or repeat-for-better-results is allowed. A failure after fitting begins requires maintainer review before any retry. The two registry operations must be exactly, and in this order:

```text
persistent_model_packaging
patient_level_shap_background
```

Both are required. `_execute_shared_training_pipeline` constructs the SHAP background before packaging, and the bundle format requires `shap_background.json`; a packaging-only or synthetic-background substitution is not an executable or faithful alternative.

## 4. Activation review and genuine blockers

### 4.1 **BLOCKING — AI-2 does not exactly implement the frozen D-047 method**

At the AI-2 review baseline:

| Method element | Frozen D-047 protocol/plan | Current shared AI trainer |
|---|---|---|
| Logistic solver / iteration limit | `liblinear` / `2000` (`gate-pt/02`; registered plan) | `lbfgs` / `1000` (`ai/training.py`, `_build_estimator`) |
| Inner-CV seed | `outer_repeat_seed + 97 + 1009*outer_fold_number` | `repeat_seed + 1000*fold_idx + 10*family_offset` |
| Outer-fit model seed | `outer_repeat_seed + 100003 + 101*outer_fold_number + family_offset`, with LR/RF offsets 11/23 | `repeat_seed + 5000*fold_idx + family_offset` |
| Label-shuffle outer seed | Corresponding label-shuffle seed | `shuffle_seed + 17` |

`assert_training_config_approved` compares dataclass fields but does not bind these solver and seed-derivation differences. The shared preprocessor also emits optional-field missingness indicators, while the D-047 plan forbids inventing unrecorded missing reasons. The audited Cleveland panel is complete, so that particular path is not expected to fire, but it must not be used to fabricate a `not_measured` reason for an undocumented source `?` value.

**Required disposition:** stop before ratification/activation. A separately reviewed engineering correction must make the actual Cleveland execution path conform to the unchanged D-047 protocol/plan and add synthetic regression evidence for solver, seeds, negative-control split seeds, and missingness semantics. That correction must not alter the protocol, either cohort's source adapter, dataset, panel, grids, UCI-412 behavior, or this governance scope. Alternatively, any proposal to retain the different AI-2 method is a separate methodology amendment outside AI-3.1 and cannot be inferred from this operational approval.

### 4.2 Registry circularity and code-revision limitation

The empty `RATIFIED_OPERATIONAL_SCOPE_AMENDMENTS` is an intentional authorization block, not a defect. A non-circular activation is possible only with two distinct commits:

- `G`: the human-ratified governance merge containing this exact document and the corrected code. Its SHA and the document's Git-blob SHA-256 become knowable only **after** merge.
- `A`: the later human-reviewed activation merge containing only the trusted registry entry. It is impossible for a committed registry entry to contain `A` as its own `approved_code_revision` without a self-reference.

Therefore `approved_code_revision` must be `G`, never a guessed future `A`; the amendment-document hash must be computed from `git show G:<path>`, not from a CRLF working-tree conversion or written into this proposal beforehand.

There is also a real implementation limitation: `validate_operation_scope_amendment` compares the manifest's `approved_code_revision` with the trusted record but does **not** compare it with `current_git_commit` or independently validate that code revision. The sequence in §7 therefore makes the additional local field `activation_merge_commit_sha=A` and the clean-HEAD/registry-only-diff checks mandatory. These are compensating activation controls, not a claim that AI-2 currently enforces HEAD equality. If those checks are not performed, or if strict native enforcement is required instead, activation remains blocked pending a separately reviewed code correction.

### 4.3 Required wrapper around the AI-2 entry point

`execute_authorized_research_run` must not be invoked as a standalone replacement for the D-047 preflight. The AI-2 entry point itself does not run the complete D-046 provenance/license/byte-size preflight and does not re-hash the Cleveland source after fitting/packaging. The local sequence must therefore:

1. run `research.experiments.safety.run_preflight` immediately beforehand;
2. validate the operation amendment and activation merge before source-row parsing;
3. retain the returned `PreflightContext`; and
4. call `verify_source_still_unchanged(context)` after execution and before accepting the bundle.

A post-execution mismatch makes the bundle **QUARANTINED / NOT ACCEPTED**; it must not be loaded, shared, or used. Do not delete evidence or retry automatically.

### 4.4 Non-blocking but explicit limitations

- The first bundle requires both new fitting and SHAP persistence; there is no saved D-047 model to reuse.
- Sample-size adequacy remains `NOT ASSESSED`; n=303 and penalization/nested CV do not establish predictive adequacy.
- Existing preflight success does not prove Windows ACLs, the final activation commit, or future source integrity; those checks remain mandatory.
- UCI-412 needs its own later authorization and activation record. Nothing in this Cleveland packet carries over.

## 5. Persistent bundle, SHAP privacy, and Windows-only custody

### 5.1 Permitted location and contents

The only permitted bundle location is a **new, unique child** of:

```text
data/experiments/
```

Use a safe basename such as `cai-da-a2-resting-v1-<UTC timestamp>-<random suffix>`; never overwrite an existing directory. The canonical local authorization manifest remains:

```text
data/manifests/internal_exploratory_authorization.local.json
```

The bundle contains only the existing AI-2 layout: `manifest.json`, `model.joblib`, `preprocessing.json`, `calibration.json`, `shap_background.json`, `evaluation_summary.json`, and `protocol.md`. It must remain `RESEARCH_ONLY`, with `approved_for_serving=false` and `clinical_use_authorized=false`.

The local HMAC key is not an authorization signature. If the default key mechanism is used, its location is `%LOCALAPPDATA%\CardioAssistAI\local_bundle_hmac_v1.key`; it must remain private, outside Git, and must never be printed, copied into chat, or uploaded. SHA-256 alone does not make `joblib` safe; only the existing trusted-local-root + ACL + HMAC verification path may precede any future deserialization. No deserialization or individual inference is part of this activation.

### 5.2 Patient-derived SHAP background

`shap_background.json` contains up to 64 encoded training-row projections. With `preprocessing.json`, continuous values can be reconstructed. It is therefore **sensitive real-patient-derived data**, not an anonymous aggregate and not safe for public sharing. The following are mandatory:

- local-only custody with `commit_or_public_upload_prohibited=true` and truthful `synthetic_only=false` classification;
- no substitution of synthetic rows, no suppression of privacy metadata, and no extraction of row values into logs/reports;
- no SHAP background in GitHub, Arena, email, tickets, chat, cloud drives, experiment trackers, or published supplements;
- aggregate-only evaluation summaries; no individual predictions, row-aligned scores, patient identifiers, or local private paths in review evidence.

### 5.3 Access controls

Before execution, the maintainer/data custodian must verify on native Windows:

- repository and `data/` are on a local fixed NTFS drive, outside OneDrive/SharePoint/Dropbox/other sync or backup folders, with no symlink/junction/reparse component;
- `/data/` and every required child are Git-ignored and untracked;
- source, manifests, license snapshot, output root, bundle directory/files, and signing-key directory/file have effective private ACLs; broad `Users`, `Everyone`, or `Authenticated Users` access is not acceptable;
- bundle/private-key DACLs are protected and limited to the current authorized Windows user plus required `SYSTEM` and `Administrators`, with ownership and `FILE_PERSISTENT_ACLS` verified by the existing AI-2 Win32 checks.

Do not blindly reset ACLs on an existing data tree. Any remediation is a custodian action and must be re-verified. Keep the machine local/offline for execution; no telemetry, hosted notebook, CI, remote agent, or network drive is permitted.

## 6. Explicitly prohibited uses and claim limits

Even after successful activation, this amendment prohibits:

- FastAPI/backend/frontend integration, real provider registration, HTTP serving, patient/clinician display, alerts, diagnosis, treatment, triage, screening, or any clinical decision;
- individual or personal risk percentages, a clinical threshold, or interpreting exploratory `0.5` as an operating point;
- external validation, transportability, superiority, calibration adequacy, sample-size adequacy, clinical readiness, publication, novelty, regulatory, or deployment claims;
- pooling or evaluating UCI-412/UCI-411, Hungary, Switzerland, VA, Statlog, AngioCAD, or any other cohort;
- extended Cleveland labs, UCI-412 panels, wearables, new features, new models, AutoML, threshold tuning, or result-driven reruns;
- committing/uploading source rows, manifests, predictions, SHAP rows, keys, bundles, sensitive logs, or private path details;
- treating HMAC, SHA-256, a merged PR, or a bundle descriptor as scientific, supervisor, ethics, or clinical approval.

The only defensible claim after a successful run would be: **“One hash-bound, private, internal exploratory research bundle was produced on the named historical Cleveland cohort under the frozen protocol; it is not externally validated, supervisor-approved, clinically adequate, or deployable.”** Even that statement requires local verification of successful completion; this proposal makes no such claim now.

## 7. Fail-closed two-stage activation sequence

### Prerequisite before Stage 1 — resolve, do not waive, §4.1

A separate human-reviewed engineering change must restore exact D-047 method fidelity and pass synthetic regressions. No real source may be used. Recompute and record the non-sensitive code/protocol/plan bindings. If the protocol or plan changes, stop: this amendment no longer matches and must be revised rather than activated.

### Stage 1 — independent human governance approval and merge (`G`)

1. Confirm the §4.1 correction is merged and this proposal still names the exact dataset, panel, operations, and unchanged protocol/plan.
2. The human maintainer independently reviews the PR and writes exactly `RATIFY-AI2-OPERATIONAL-SCOPE-EXPANSION`. No agent may write it on the maintainer's behalf.
3. The maintainer performs the human-approved merge. Record the full merge SHA as `G` and verify on GitHub: exact comment body, repository-owner association, comment timestamp, merged state, and merge SHA. Do not infer approval from reviewers, CI, or merge alone.
4. From the merged Git object, compute this document's SHA-256 using raw `git show G:docs/research/gate-pt/17_ai2_operational_scope_amendment.md` bytes. Verify the protocol and plan hashes in §3.2 against the `G` blobs. Any mismatch stops activation. The local D-047 manifest must separately match the actual on-disk protocol/plan bytes required by `run_preflight`; if Windows EOL conversion makes those working-tree bytes differ from the Git blobs, stop and use a reviewed, clean LF-preserving checkout rather than editing or renormalizing files after preflight.
5. **Do not execute yet.** No registry entry existed when this governance decision was reviewed.

### Stage 2 — post-approval trusted registry activation (`A`), local attestation, preflight, then execution

1. **Only after Stage 1 is independently recorded and verified**, prepare a separate activation PR adding one entry to `RATIFIED_OPERATIONAL_SCOPE_AMENDMENTS`. It must bind:
   - `amendment_id`: the ID at the top of this document;
   - `governance_pr_number`: this governance PR's actual number;
   - `governance_merge_commit_sha`: `G`;
   - `approved_code_revision`: `G` (the reviewed code baseline, not a self-referential `A`);
   - `approved_dataset_id`: `DA-A2`; `approved_panel_id`: `da_a2_resting_v1`;
   - `frozen_source_sha256`: the exact non-sensitive 64-hex value independently read by the maintainer from the protected local provenance and rechecked against the source; never a placeholder;
   - `frozen_protocol_sha256`: the §3.2 protocol Git-blob hash;
   - `amendment_document_relative_path`: this document's repository-relative path;
   - `frozen_amendment_document_sha256`: the `G` Git-blob hash from Stage 1;
   - `approved_operations`: exactly the two operations in §3.3, in that order;
   - `ratified_by`: `Muhammed Fathi`; `ratification_comment_exact`: the exact Stage 1 comment;
   - `ratification_status`: `RATIFIED_BY_PROJECT_MAINTAINER`; `supervisor_signoff_claimed`: `false`;
   - `human_attestation`: `HUMAN_RATIFIED_LOCAL_EXPERIMENTATION_ONLY_GATE_PT_P3_CLOSED`;
   - `signature_semantics`: `HUMAN_ATTESTATION_FIELDS_NOT_A_CRYPTOGRAPHIC_SIGNATURE`;
   - `protected_output_root`: `data/experiments`.
2. The activation PR must change only that registry entry—no protocol, plan, adapter, trainer, panel, test expectation, backend, frontend, inventory, or gate change. The maintainer reviews and merges it; record the actual merge SHA as `A` and independently verify it on GitHub.
3. Check out `A` cleanly. Verify `G` is an ancestor of `A`, `git diff --name-only G..A` contains only `ai/execution.py`, and human review of that diff confirms only the registry entry changed. Any other change stops activation.
4. The maintainer—not an agent—updates and newly attests the ignored local D-047 manifest. Keep every established D-047 field and allowlist unchanged, add `panel_id=da_a2_resting_v1`, and add an `operation_scope_amendment` matching the trusted registry field-for-field. Do not use top-level packaging/SHAP booleans as authority. Add the local compensating field `operation_scope_amendment.activation_merge_commit_sha=A`; it is not a substitute for Stage 1 evidence. The local signature date must follow the relevant human approvals. Never commit or share this manifest.
5. Repeat all non-sensitive checks in §8 at `A`. Any failure means stop before source-row parsing.
6. Only after every check passes, the data custodian may invoke `execute_authorized_research_run` from an interactive local Windows console with:
   - `source_path=<repo>/data/raw/uci-45/processed.cleveland.data`;
   - `manifest_path=<repo>/data/manifests/internal_exploratory_authorization.local.json`;
   - `panel_id=da_a2_resting_v1`;
   - `output_bundle_dir=<repo>/data/experiments/<new-safe-unique-name>`;
   - `repo_root=<repo>`; `training_config=None` (mandatory frozen default);
   - the private local signing mechanism, never a key supplied through chat/command logs;
   - `current_git_commit=A` only after independently verifying actual clean HEAD is `A`.
   The wrapper must first repeat `run_preflight`, amendment validation, HEAD/ancestry/registry-only-diff checks, require both authorized operation flags, and obtain an explicit local human confirmation. Only then may it call the AI-2 entry point.
7. Immediately after return, call `verify_source_still_unchanged` with the pre-execution context and verify the private bundle through the existing trusted-local ACL/HMAC path. Record locally only sanitized completion status, code/protocol/panel IDs, and aggregate review status. Do not print or transmit performance, predictions, SHAP rows, key material, or the bundle. Any exception or source mismatch means no accepted bundle and no automatic retry.

## 8. Exact non-sensitive local evidence to check before first execution

The maintainer must inspect these locally and share only PASS/FAIL or already-public commit/document identifiers if review is needed:

| Evidence | Required local result |
|---|---|
| GitHub Stage 1 approval | Exact owner comment, actual governance PR number, merged state, and full `G`; comment precedes activation |
| GitHub Stage 2 activation | Human-reviewed registry-only PR, merged state, and full `A`; entry was created only after Stage 1 verification |
| Executing revision | Clean checkout HEAD exactly `A`; `G` ancestor of `A`; `approved_code_revision=G`; local `activation_merge_commit_sha=A`; no dirty tracked files |
| Amendment bytes | Raw `G` blob SHA-256 matches trusted registry and local amendment; no working-tree CRLF hash substitution |
| Protocol/plan/code fidelity | `G` Git blobs match §3.2; the local manifest separately matches actual on-disk protocol/plan bytes; any EOL mismatch stops; §4.1 correction is present; no protocol/plan/panel/adapter/grid/seed change outside the reviewed correction |
| D-047 evidence | PR #31/merge `434e49a…`; unchanged D-047 allowlists; new local human attestation for this expanded operation |
| D-046/provenance chain | Valid local read-only authorization, exactly one canonical Cleveland record, official-source human-attestation status preserved, CC BY 4.0 snapshot/hash valid |
| Source byte identity | Existing preflight returns `PREFLIGHT_PASS`; source SHA-256 and byte size match protected provenance, local manifest, and registry; no source rows parsed by this check |
| Git/storage protection | `python -m research.audit verify-ignore` and `python -m research.experiments preflight` pass; no tracked `/data/` files; no reparse points |
| Windows custody | Interactive native Windows, local fixed NTFS, non-sync location, effective private ACL/ownership checks pass for all paths in §5.3 |
| Environment | Python 3.12, pinned dependencies, `python -m pip check` passes; versions recorded locally without private paths |
| Synthetic safety evidence | `python -m pytest tests/experiments/test_ai_research_pipeline.py tests/experiments/test_authorized_real_data_execution.py -q -W error` and `python scripts/validate_ai_windows_compat.py` pass using only synthetic/temporary fixtures |
| Authorization-only AI-2 check | `parse_and_validate_research_authorization(..., expected_dataset_id="DA-A2", expected_panel_id="da_a2_resting_v1", current_git_commit=A)` returns an authentic context with both operation authorizations true; no fitting or source-row parsing |
| Final operator check | New non-existent bundle path; both operations confirmed; no other cohort/panel; explicit local confirmation; post-run source-recheck wrapper ready |

Never send the underlying source, provenance/manifest contents, individual predictions, ACL-identifying local details, signing keys, or bundle to an agent for these checks. A missing or uncertain item is a stop result, not a request to bypass a guard.

## 9. Human fields intentionally unsigned and unratified

| Field | Status in this proposal |
|---|---|
| Maintainer operational-scope decision | **NOT MADE** |
| Ratification comment / author / timestamp | **NOT RECORDED** |
| Governance PR number and merge `G` | **PR #54 ASSIGNED; MAINTAINER DECISION AND MERGE `G` PENDING ACTUAL HUMAN ACTION** |
| Activation PR and merge `A` | **PENDING ACTUAL HUMAN ACTION** |
| Registry entry | **ABSENT — MUST REMAIN EMPTY IN THIS PR** |
| Source SHA-256 binding for the future registry | **PENDING LOCAL HUMAN VERIFICATION — NO PLACEHOLDER IS VALID** |
| Local manifest, signer, date, and attestation | **NOT CREATED / NOT SIGNED** |
| §4.1 engineering correction and synthetic evidence | **NOT PRESENT IN THIS DOCUMENTATION PR** |
| P-1 target/protocol sign-off | **PENDING / NOT MADE** |
| P-3 supervisor approval | **CLOSED / NOT OBTAINED** |
| P-4 clinical wording approval | **PENDING / NOT MADE** |
| P-5 external/clinical claims | **NOT MADE — prohibited** |
| Ethics/institutional approval | **NOT CLAIMED / NOT DETERMINED HERE** |
| Real execution, bundle, SHAP persistence, inference, serving | **NOT PERFORMED / NOT AUTHORIZED BY THIS DOCUMENT** |

## 10. Actions remaining blocked after this review PR

- Ratification itself while the maintainer has not made the exact scoped decision.
- Any registry entry before verified Stage 1 approval and merge.
- Activation while §4.1 or the required activation-revision controls remain unresolved.
- Creating/signing local manifests by an agent, fitting, calibration, SHAP generation/persistence, packaging, inference, or serving.
- UCI-412 execution and every other cohort/panel, pooling, external evaluation, publication, performance adequacy, and all clinical/deployment gates.
