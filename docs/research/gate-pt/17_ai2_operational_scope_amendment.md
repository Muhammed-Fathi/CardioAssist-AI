# AI-2 Operational-Scope Amendment — Cleveland D-047 Local Research Artifacts

- **Decision ID:** `AI2-OPERATIONAL-SCOPE-001`
- **Governance PR:** **#54**
- **Revision:** AI-3.3 reconciliation with merged AI-3.2 engineering, 2026-10-26
- **Status:** **PROPOSED / UNRATIFIED / HOLD FOR AUTHORITY DECISION / NOT ACTIVATED**
- **Approval-readiness:** **READY FOR HUMAN GOVERNANCE REVIEW; NOT READY FOR RATIFICATION OR EXECUTION**
- **Gate PT:** **P-1 PENDING; P-3 CLOSED; P-4/P-5 NOT OPENED**

> This document is a governance proposal, not an authorization. PR #54 remains open and unmerged. The operational registry remains empty. No local authorization manifest is created by this proposal, and no real dataset access, fitting, packaging, inference, or activation is permitted by it.

## 1. Decision requested and express non-authorization

The requested decision is whether a future, separately activated, one-run local Cleveland pilot may add exactly these two operations to the existing D-047 internal exploratory route:

1. `persistent_model_packaging`
2. `patient_level_shap_background`

The scope is exclusively:

- dataset `DA-A2`;
- source `UCI-45 / processed.cleveland.data`;
- panel `da_a2_resting_v1` (`age`, `sex`, `cp`, `trestbps`, `restecg`);
- one guarded run on the maintainer-controlled local Windows PC, CPU only;
- private, Git-ignored output beneath `data/experiments/`; and
- aggregate-only research reporting after separate human disclosure review.

The following remain forbidden: remote upload or telemetry, any additional dataset or cohort, pooling, additional panels or features, automated or manual retry without a new human decision, real external-cohort evaluation, inference or serving, FastAPI/UI integration, clinical or patient-facing use, public sharing of patient-derived artifacts, and any claim of external validation, clinical validity, deployability, supervisor approval, ethics approval, or institutional approval.

**UCI-412 remains a later independent, non-pooled cohort.** It is not a training augmentation, and no enhanced AI-2 output may be represented as the historical D-047 result.

### 1.1 Unresolved authority inconsistency — current ratification blocker

Two repository governance statements must not be silently treated as equivalent:

- D-047 permits a maintainer-authorized, clearly labelled internal exploratory experiment while formal Gate PT P-3 remains closed.
- `docs/research/AI_FIRST_COMPLETION_STRATEGY.md` §5.1(2) separately says Gate PT **P-1 target sign-off and P-3 protocol sign-off** are required before running `ai/` to fit/save any real-patient model bundle or `shap_background.json` derivative on Cleveland or UCI-412.

AI-3.2 did not resolve that authority question; it changed engineering only. A maintainer may review and merge repository governance, but a maintainer comment or merge cannot, by itself, establish that the maintainer has authority to waive P-1/P-3 or to supply supervisor, ethics, licensing, institutional, or other external permission.

Accordingly, **PR #54 must not be ratified as an execution authorization until the authorized human governance process resolves this specific conflict**. The resolution must either:

1. obtain the required P-1/P-3 and any other applicable approvals before activation; or
2. through a competent, separately documented governance decision, amend the conflicting AI-first boundary and determine that the bounded D-047 internal exploratory exception lawfully covers these two local operations, while separately confirming all applicable supervisor, ethics, licensing, and institutional requirements.

An agent cannot make that determination. Repository ratification alone is not a substitute for it.

## 2. Verified references and immutable bindings

The following references were checked against Git objects on merged AI-3.2 main and on the current PR #54 branch. They are historical or current-object hashes, **not predictions of a future merge**.

| Binding | Verified value / rule |
|---|---|
| Original D-047 governance PR | #31; exact owner authorization comment `AUTHORIZE-D047-INTERNAL-CLEVELAND` |
| D-047 governance merge | `434e49a37e6e60b8b91498dde0f9d02dc1af18de` |
| D-047 protocol path | `docs/research/gate-pt/02_d047_internal_exploratory_cleveland_PROTOCOL_PROPOSED.md` |
| Protocol Git-blob SHA-256 at D-047 merge, AI-3.2 main, and this PR | `96c26829ff73893dab8ee091b2eaea1592479a1e0528ae6832651a9688ea3c86` |
| Current registered plan path | `research/experiments/cleveland_d047_exploratory_plan.v0.1.json` |
| Current registered-plan SHA-256 on AI-3.2 main and this PR | `2c441c4c44d61e2734277d3ee788ce09b5dd4cc8e54cbeff741374a428646c6a` |
| Five-field panel | `da_a2_resting_v1` |
| Panel-contract SHA-256 | `c18ad4cd2cf08f6fefb2e340573760da7000bc1d8eb4ad38783b873c018e57b8` |
| Merged AI-3.2 engineering PR | #55; head `f3c1676561c60733b878d66643484af6fb418e83`; merge `6a5466a4ddc19aa315007ead9985cfd1f4049d04` |
| Operational registry now | `RATIFIED_OPERATIONAL_SCOPE_AMENDMENTS = {}` |

The real source SHA-256 is deliberately **not** copied into this public proposal. The authorized human must bind it in the local ignored manifest from the protected provenance record; code then checks it against the actual source and D-046 provenance.

### 2.1 Future identifiers that must not be precomputed

- `G` means the future full 40-hex merge commit of governance PR #54, if and only if the human authority decision and ratification occur.
- `A` means the future full 40-hex merge commit of a separate registry-only activation PR created after `G`.
- Neither `G` nor `A` exists now. No future merge SHA, activation PR number, ratification timestamp, or final authorization-manifest signature is asserted here.
- After `G`, the reviewer must hash `git show G:docs/research/gate-pt/17_ai2_operational_scope_amendment.md` and use that exact document hash in the activation record. The current working-tree hash is not a substitute for that later check.

## 3. What D-047 already authorizes — and what it does not

D-047 remains the historical basis for the Cleveland-only internal exploratory method: read-only source loading, internal model fitting, nested CV, model-family comparison, label-shuffle negative control, and aggregate metrics. Its original PR #31 authorization and merge do not automatically ratify this AI-2 operational expansion.

This proposal does not alter the D-047 source, target, predictor set, primary nested-CV estimand, historical results, or formal P-3 status. It does not convert an internal exploratory artifact into a locked externally validated model. It also does not authorize inference merely because the merged engineering contains an offline inference implementation.

## 4. AI-3.2 engineering reconciliation

### 4.1 Historical implementation blockers now resolved in merged code

The AI-3.1 version of this proposal identified mismatches between the generic AI-1 pipeline and the registered Cleveland D-047 method. PR #55 has merged the correction. The production Cleveland configuration now selects `CLEVELAND_D047_FROZEN_V1`; generic synthetic work and UCI-412 retain `AI1_GENERIC_V1`.

| Method element | Frozen Cleveland behavior after AI-3.2 | Verification boundary |
|---|---|---|
| Logistic estimator | L2, `solver="liblinear"`, `max_iter=2000`, `class_weight=None`, `C={0.1,1,10}` | Generic AI-1 remains `lbfgs` / 1000 iterations; the profiles are not interchangeable. |
| Forest estimator | 200 trees, `max_depth={3,5}`, `min_samples_leaf={5,10}`, `max_features="sqrt"`, `class_weight=None`, one CPU job | The constrained grid and simplicity rule remain registered; no additional family is allowed. |
| Nested CV | 5 outer folds, 5 inner folds, 4 repeats; outer seeds `20261023,20261024,20261025,20261026`; ROC-AUC selection; LR preferred when the inner-AUC difference is at most `0.01` | Outer-assessment rows remain excluded from preprocessing, selection, fitting, and fold calibration. |
| Inner split seed | `outer_repeat_seed + 97 + 1009 * outer_fold_number_1_based` | Both families share the same inner splits within an outer fold. |
| Model seed | `(outer_repeat_seed + 100003 + 101 * outer_fold_number_1_based + family_offset) mod (2**32 - 1)` | Family offsets are LR `11`, RF `23`; all inner fits for a family/fold use the registered model seed, matching the original `GridSearchCV` wiring. |
| Negative control | Shuffle seeds `20262001,20262002,20262003`; each label-shuffle outer seed is the corresponding shuffle seed itself | This replaces the generic `shuffle_seed + 17` behavior only for the Cleveland profile. It remains a smoke test, not a permutation p-value. |
| Fold-local preprocessing | Training-fold median/mode imputation, LR numeric standardization, fixed source-vocabulary reference one-hot encoding | Unexpected missingness in the audited five-field source fails closed; no `not_measured` reason is invented. |
| Original RF input space | Exactly 8 columns: raw median-imputed `age`, `trestbps`, followed by drop-first one-hots for `sex`, `cp`, `restecg` | Built fold-safely from fitted preprocessing statistics; the forest no longer consumes the generic 10-column space with two always-present missingness indicators. |
| Persisted lineage and loading | The full 10-column preprocessor lineage is retained for shared serialization; `execution_profile` and fitted estimator width are checked at load | Cleveland RF prediction and grouped TreeSHAP use explicit 8-column projections and fail closed on layout or width mismatch. |

The logistic family intentionally remains on the full 10-column encoded representation. On complete data its two additional missingness-indicator columns are zero. Merged synthetic comparisons support rank-identical predictions with approximately 1-ulp score differences; they do **not** establish universal bit identity.

Merged same-input/same-seed/same-procedure synthetic comparisons demonstrate, on their fixtures:

- exact RF out-of-fold scores, inner-CV family AUCs, family selection, and selected hyperparameters against the original D-047 implementation;
- exact agreement of the adapted 8-column RF matrix with the original fold-local preprocessor on the tested fixture; and
- logistic agreement within the test's numerical tolerance, not a claim of universal bitwise equality.

These are software-fidelity results only. They used generated synthetic fixtures and reduced-cost test configurations where stated. They are not a real-patient rerun, do not reproduce or replace the historical D-047 AUROC, and do not establish clinical or external validity.

### 4.2 Enhanced AI-2 analyses remain distinct from D-047

The following are AI-2 additions or retained AI-2 machinery, not retroactive changes to the historical D-047 result:

- cross-fitted calibrated nested-CV metrics, reported separately from pure uncalibrated out-of-fold scores;
- full-development family/hyperparameter selection, final development refit, and final development-OOF calibrator;
- the apparent final-calibrator diagnostic, which is explicitly not an unbiased calibrated-performance estimate;
- dummy/bootstrap/leakage analyses beyond the original report;
- a persisted fold ensemble, local model bundle, and faithful SHAP artifacts; and
- AI-2-specific seeds for the added full-development selection/refit/calibration/SHAP stages.

The registered D-047 seed formulas above govern the corrected repeated nested-CV and negative-control comparisons; they must not be misdescribed as having historically specified the later full-development AI-2 additions.

The primary D-047-style internal estimate remains `uncalibrated_nested_cv` for `inner_selected_procedure`. Calibrated, apparent, bootstrap, final-refit, and SHAP outputs must be separately and truthfully labelled. Repeats reuse the same participants and never multiply sample size. No enhanced AI-2 metric may be reported as the historical D-047 AUROC (`0.8271 ± 0.0097`) or as an external-validation result.

## 5. Mandatory two-stage governance and activation sequence

### Stage 0 — current state

- PR #54 is open, unmerged, and unratified.
- The authority inconsistency in §1.1 is unresolved.
- The production operational registry is empty.
- No registry-only activation PR exists.
- No real execution, packaging, inference, or retry is allowed.

### Stage 1 — governance merge `G`

Only after the §1.1 authority decision and all applicable external requirements are resolved may the authorized human:

1. review the final PR #54 diff and confirm it changes only this amendment document;
2. record the exact owner comment **`RATIFY-AI2-OPERATIONAL-SCOPE-EXPANSION`** on PR #54, with the authority determination explicitly referenced in the review record;
3. merge PR #54 independently of any activation change; and
4. record the actual GitHub merge commit as `G`, then verify the amendment, protocol, and plan bytes at `G`.

A PR approval review, CI result, AI-3.2 merge, local manifest assertion, or operator-confirmation string is not the required ratification comment and does not replace human review.

### Stage 2 — separate registry-only activation merge `A`

After `G`, a separate activation PR may change **only** the single `RATIFIED_OPERATIONAL_SCOPE_AMENDMENTS` entry in `ai/execution.py`. It must not change the document, protocol, plan, tests, training, packaging, inference, or any other file. It must be reviewed and merged separately; its actual merge commit is `A`.

The proposed record shape is illustrative, not activated content:

```python
"CAI-AMEND-AI2-CLEVELAND-D047-V1": {
    "governance_pr_number": 54,
    "governance_merge_commit_sha": "FULL_40_HEX_G",
    "approved_code_revision": "FULL_40_HEX_G",
    "approved_dataset_id": "DA-A2",
    "approved_panel_id": "da_a2_resting_v1",
    "frozen_source_sha256": "FULL_64_HEX_SOURCE_SHA_FROM_PROTECTED_PROVENANCE",
    "frozen_protocol_sha256": "96c26829ff73893dab8ee091b2eaea1592479a1e0528ae6832651a9688ea3c86",
    "amendment_document_relative_path": "docs/research/gate-pt/17_ai2_operational_scope_amendment.md",
    "frozen_amendment_document_sha256": "FULL_64_HEX_DOCUMENT_SHA_AT_G",
    "ratified_by": "Muhammed Fathi",
    "ratification_comment_exact": "RATIFY-AI2-OPERATIONAL-SCOPE-EXPANSION",
    "approved_operations": (
        "persistent_model_packaging",
        "patient_level_shap_background",
    ),
    "protected_output_root": "data/experiments",
}
```

Before merging `A`, the human activation reviewer must independently verify:

- the exact ratification comment, PR #54 merged state, and full `G` on GitHub;
- the amendment document hash and unchanged protocol/plan bindings at `G`;
- `governance_merge_commit_sha == approved_code_revision == G` in both trusted record and local manifest;
- the activation PR changes only the intended registry entry, not merely only the filename;
- `G` is an ancestor of `A`, and the local `G..A` name-only diff is exactly `ai/execution.py`;
- the executing checkout is genuinely at full commit `A` with a clean worktree; and
- the local authorization is signed only after `G` and `A` and after the final operator review.

The wrapper can check local Git ancestry, HEAD/path consistency, a clean tracked tree, and that `G..HEAD` names only `ai/execution.py`. It cannot inspect GitHub, judge PR content, prove who signed, or establish external authority. The current validator compares manifest fields with the trusted registry record; the explicit human equality check `approved_code_revision == G` above remains mandatory and must not be replaced by an assumption about code enforcement.

## 6. Local authorization manifest after `A`

Only the authorized human may create/update the ignored file `data/manifests/internal_exploratory_authorization.local.json`. This template is non-operational until every placeholder is replaced with verified evidence and every human precondition is satisfied:

```json
{
  "schema_version": "0.2.0",
  "decision_id": "D-047",
  "authorization_status": "AUTHORIZED_FOR_LOCAL_INTERNAL_EXPLORATORY_CLEVELAND",
  "experiment_type": "INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED",
  "supervisor_signoff_claimed": false,
  "maintainer_approval_comment_exact": "AUTHORIZE-D047-INTERNAL-CLEVELAND",
  "approval_pr_number": 31,
  "approval_pr_merged_commit_sha": "434e49a37e6e60b8b91498dde0f9d02dc1af18de",
  "pinned_protocol_git_commit_sha": "434e49a37e6e60b8b91498dde0f9d02dc1af18de",
  "local_signer": "Muhammed Fathi",
  "local_signed_at_iso8601": "TIMEZONE_AWARE_TIMESTAMP_AFTER_G_A_AND_FINAL_REVIEW",
  "local_signature_attestation": "I have reviewed and authorize this exact hash-bound local D-047 internal exploratory experiment. I understand Gate PT P-3 remains CLOSED.",
  "signature_semantics": "HUMAN_ATTESTATION_FIELDS_NOT_A_CRYPTOGRAPHIC_SIGNATURE",
  "dataset_id": "DA-A2",
  "panel_id": "da_a2_resting_v1",
  "allowed_original_relative_file": "data/raw/uci-45/processed.cleveland.data",
  "authorized_source_row_count": 303,
  "allowlisted_model_families": [
    "prevalence_dummy",
    "l2_logistic_regression",
    "constrained_random_forest"
  ],
  "allowed_operations_if_approved": [
    "read_only_source_loading",
    "internal_model_fitting",
    "internal_nested_cv",
    "internal_model_family_comparison",
    "internal_negative_control",
    "internal_aggregate_metrics_report"
  ],
  "forbidden_operations": [
    "remote_patient_data_upload",
    "model_serving",
    "clinical_decision",
    "external_validation_claim",
    "multi_cohort_pooling",
    "unapproved_dataset_ingestion",
    "patient_level_git_commit"
  ],
  "allowed_runtime": "LOCAL_WINDOWS_CPU_ONLY",
  "protected_outputs_relative_root": "data/experiments",
  "expected_sha256_from_protected_provenance_manifest": "FULL_64_HEX_SOURCE_SHA_FROM_PROTECTED_PROVENANCE",
  "frozen_protocol_sha256": "96c26829ff73893dab8ee091b2eaea1592479a1e0528ae6832651a9688ea3c86",
  "frozen_experiment_plan_sha256": "2c441c4c44d61e2734277d3ee788ce09b5dd4cc8e54cbeff741374a428646c6a",
  "model_packaging_authorized": true,
  "patient_shap_authorized": true,
  "operation_scope_amendment": {
    "amendment_id": "CAI-AMEND-AI2-CLEVELAND-D047-V1",
    "ratification_status": "RATIFIED_BY_PROJECT_MAINTAINER",
    "supervisor_signoff_claimed": false,
    "ratified_by": "Muhammed Fathi",
    "ratification_comment_exact": "RATIFY-AI2-OPERATIONAL-SCOPE-EXPANSION",
    "governance_pr_number": 54,
    "governance_merge_commit_sha": "FULL_40_HEX_G",
    "approved_code_revision": "FULL_40_HEX_G",
    "activation_merge_commit_sha": "FULL_40_HEX_A",
    "approved_dataset_id": "DA-A2",
    "approved_panel_id": "da_a2_resting_v1",
    "frozen_source_sha256": "FULL_64_HEX_SOURCE_SHA_FROM_PROTECTED_PROVENANCE",
    "frozen_protocol_sha256": "96c26829ff73893dab8ee091b2eaea1592479a1e0528ae6832651a9688ea3c86",
    "amendment_document_relative_path": "docs/research/gate-pt/17_ai2_operational_scope_amendment.md",
    "frozen_amendment_document_sha256": "FULL_64_HEX_DOCUMENT_SHA_AT_G",
    "approved_operations": [
      "persistent_model_packaging",
      "patient_level_shap_background"
    ],
    "human_attestation": "HUMAN_RATIFIED_LOCAL_EXPERIMENTATION_ONLY_GATE_PT_P3_CLOSED",
    "signature_semantics": "HUMAN_ATTESTATION_FIELDS_NOT_A_CRYPTOGRAPHIC_SIGNATURE"
  }
}
```

The top-level D-047 PR/merge fields remain bound to historical PR #31. The amendment fields separately bind PR #54, `G`, and `A`; they must not be conflated. The two boolean flags do not self-authorize operations—the independent trusted registry entry and all hash/Git checks remain necessary.

## 7. Supported guarded execution interface

After—and only after—successful completion of both governance stages and every local/external precondition, the sole supported Cleveland entry point is:

```python
from pathlib import Path
from ai.execution import execute_guarded_cleveland_d047_run

repo = Path("<EXACT_REPOSITORY_ROOT>")
trained_run, verified_bundle = execute_guarded_cleveland_d047_run(
    source_path=repo / "data/raw/uci-45/processed.cleveland.data",
    manifest_path=repo / "data/manifests/internal_exploratory_authorization.local.json",
    panel_id="da_a2_resting_v1",
    output_bundle_dir=repo / "data/experiments/<NEW_NONEXISTENT_BUNDLE_DIRECTORY>",
    repo_root=repo,
    training_config=None,
    current_git_commit=None,
    operator_confirmation="I_CONFIRM_AUTHORIZED_CLEVELAND_D047_EXECUTION",
)
```

This is documentation of a future human-run interface, not a command to run now. `training_config=None` is mandatory so the frozen Cleveland profile is selected. Omitting `current_git_commit` does not omit revision binding: the wrapper uses the independently preflight-verified HEAD and binds the proof to it. If a caller supplies a revision, it must equal that actual HEAD.

Direct production invocation of `execute_authorized_research_run` for Cleveland is not supported. A caller must not construct a proof, reuse a proof, bypass preflight, monkeypatch authorization, inject a registry entry, or use a synthetic-test helper for real execution.

### 7.1 Fail-closed wrapper sequence

The merged wrapper performs the following sequence without an automatic retry loop:

1. Require the exact panel, frozen configuration, and exact operator-confirmation string.
2. Run complete D-047 preflight before source-row parsing: interactive Windows-local CPU runtime, protected storage, clean Git worktree, D-047 authorization, D-046 read-only provenance, license snapshot, canonical paths, and source byte identity.
3. Bind the supplied source and manifest to the canonical preflight paths and bind any supplied revision to the actual preflight HEAD.
4. Perform authorization-only operational-scope validation before fitting or source-row parsing; require both packaging and patient-SHAP operations from the trusted registry and confirm the source binding.
5. Independently resolve local HEAD and require it to equal both the manifest's `activation_merge_commit_sha` (`A`) and the preflight HEAD; require a clean tracked tree, `G` ancestry, and a `G..HEAD` name-only diff of exactly `ai/execution.py`.
6. Require a new, non-existent, non-symlink output directory beneath the approved root.
7. Issue a redacted process-local proof token with a one-hour TTL, bound to the exact source, manifest, output, repository, and revision. The inner execution consumes it once. Manually constructed matching proofs, expired proofs, and replayed proofs fail closed before source-row parsing or fitting.
8. Execute the inner training/packaging path exactly once with the frozen profile and preflight-verified revision.
9. Re-hash the source after execution before accepting output. Failure preserves the directory, attempts a quarantine marker, records no acceptance, and raises `QUARANTINED / NOT ACCEPTED`.
10. Verify private custody and bundle integrity through `verify_trusted_local_bundle` in pre-acceptance mode, including trusted-local containment, platform ownership/ACL checks, SHA-256 digests, and HMAC-SHA256 producer authentication. Failure likewise preserves/quarantines the output and records no acceptance.
11. Write `POST_RUN_ACCEPTANCE.json` only after both post-run source and custody checks pass. An acceptance-write failure raises `guarded_wrapper_acceptance_marker_failed`; without a valid marker the real-provenance bundle remains unloadable.
12. Re-verify through the production acceptance-required loading gate and return only if that verification succeeds.

A process-local single-use token is **not a persistent cross-process run ledger**. It does not stop a person from invoking the wrapper again in another process. The one-run restriction and no-manual-retry rule therefore remain human governance controls. Any exception, non-returning call, failed final verification, or unexpected output state is a failed run: preserve it for human audit, do not load or repair it in place, and do not retry without a new explicit human decision.

## 8. Exact bundle contents, acceptance, and quarantine

The acceptance sidecar changes the permitted directory inventory; it does **not** add an operation or broaden the two authorized capabilities.

### 8.1 Accepted real-provenance research bundle

An accepted, loadable real-provenance bundle contains exactly:

- `manifest.json`;
- the six signed/digest-bound siblings: `model.joblib`, `preprocessing.json`, `calibration.json`, `shap_background.json`, `evaluation_summary.json`, and `protocol.md`; and
- `POST_RUN_ACCEPTANCE.json`.

No other directory entry is accepted. The acceptance marker is written after packaging commits, so it is deliberately **not** listed in the manifest's signed `files` table. It is a local post-run custody sidecar, not a human signature, not independent proof of GitHub ratification, and not a cryptographic substitute for the bundle HMAC/ACL checks. It must at least bind the bundle directory name and authorized source SHA-256 and assert `accepted_for_loading: true`.

Both structural and trusted-local verification require valid post-run acceptance for real-provenance bundles. Removing the marker, altering its source binding, or failing its write leaves the bundle unloadable. Synthetic-only test bundles are not subject to this real-provenance acceptance gate.

### 8.2 Pre-acceptance and failed outputs

- Immediately after packaging, the manifest plus six siblings may exist without acceptance; that real-provenance directory is **not loadable**.
- A post-source or pre-acceptance custody failure may add `QUARANTINED_DO_NOT_TRUST.json`. A quarantined directory is never an accepted bundle and is refused before trusted loading.
- If quarantine-marker writing also fails, the original failure is surfaced, artifacts are preserved, and the absence of post-run acceptance still prevents loading.
- Acceptance-write failure preserves the directory without acceptance and without automatic retry.
- Final acceptance-required verification is mandatory. Any failed wrapper call must be treated as failed even if a marker or other artifacts are present; do not infer acceptance merely from filenames.

All model, preprocessing, calibration, background, and acceptance/quarantine artifacts remain private local research derivatives. None may be committed, uploaded, publicly shared, or used for inference under this amendment.

## 9. Human controls code cannot establish

The following evidence must be recorded by responsible humans; none is created or proved by this document or by a successful function call:

| Control | Required human evidence |
|---|---|
| Authority | Resolution of §1.1 by the competent governance process; no assumption that maintainer authority supersedes P-1/P-3 or external requirements. |
| Supervisor/ethics/institutional | Separate determination of applicability and any required approvals. `supervisor_signoff_claimed=false` is an honest non-claim, not a waiver. |
| License and redistribution | Confirmation that the CC BY 4.0 source terms and local institutional policy permit the intended private derivative artifacts and any later aggregate disclosure. No public artifact redistribution is authorized here. |
| GitHub ratification | Exact owner comment, comment timing, PR #54 merged state, full `G`, and independent review of the final document diff. |
| Activation review | Separate PR content review, full `A`, registry-only content, `G` ancestry, exact `G..A` diff, and equality of both governance/code-revision fields to `G`. |
| Local signature | Actual signer identity, authority, timestamp after final review/`G`/`A`, and understanding that the attestation is not a cryptographic signature. |
| Source provenance | Protected source SHA/byte size, canonical official-source attestation, D-046 authorization, and license snapshot. Hashes prove byte identity, not official origin or participant independence. |
| Native Windows environment | Supported native Windows/Python environment, CPU-only execution, dependency versions, interactive local operation, and actual Win32 NTFS owner/DACL checks. POSIX synthetic tests do not establish native Windows acceptance. |
| Custody | Private source/manifests/license snapshot/output root/signing key, no symlink/junction/reparse escape, no cloud sync or external sharing, and secure retention/disposition. |
| Run discipline | Exactly one authorized run; no new-process retry, no configuration reduction, no response-driven model/panel iteration, and human disposition of every failure. |
| Reporting | Aggregate-only disclosure review, no small-cell or row-level leakage, separate historical/enhanced estimands, honest uncertainty and limitations, and no clinical/external-validation wording. |
| Inference prohibition | No call to `ResearchCadPredictor` or any serving/UI path under this amendment, even though trusted loading is used as an acceptance check. |

## 10. Execution-permit checklist

Every box must be satisfied by human evidence before the wrapper is invoked. The current state fails this checklist.

- [ ] §1.1 authority conflict resolved by the competent human process.
- [ ] All applicable supervisor, ethics, licensing, and institutional requirements resolved without false claims.
- [ ] Exact ratification comment recorded on PR #54 and actual full `G` verified.
- [ ] Amendment/protocol/plan hashes and scientific scope verified at `G`.
- [ ] Separate registry-only activation reviewed and merged; actual full `A` verified.
- [ ] Trusted registry and manifest fields match; both governance/code-revision fields equal `G`; activation field equals `A`.
- [ ] Clean native Windows checkout at `A`; full preflight and protected storage pass.
- [ ] Source, provenance, license, local manifest, output, key, and ACL/custody checks pass.
- [ ] Frozen Cleveland profile and native synthetic/regression acceptance evidence reviewed.
- [ ] Operator confirms the one-run/no-retry scope and invokes only `execute_guarded_cleveland_d047_run`.
- [ ] Post-run source/custody checks, acceptance marker, and final verification all succeed.
- [ ] Output remains private; no inference, sharing, additional run, or clinical claim occurs.

## 11. Approval-readiness disposition

**Engineering reconciliation:** the historical AI-3.1 implementation blockers concerning solver/iterations, registered nested-CV and negative-control seeds, fold-local preprocessing, original 8-column RF space, guarded wrapper entry point, proof enforcement, post-run custody, and acceptance gating have verified merged implementations and synthetic regression coverage in PR #55.

**Governance decision:** **HOLD — NOT APPROVAL-READY FOR RATIFICATION.** The remaining blocker is not solved by AI-3.2: the AI-first P-1/P-3 requirement for real `ai/` bundles/SHAP conflicts with treating D-047's maintainer-authorized exploratory route as sufficient. That authority question must be resolved by responsible humans before PR #54 is approved as an operational amendment.

**Activation:** even after a valid governance resolution and `G`, execution remains prohibited until the separate registry-only `A`, local manifest, native Windows evidence, full preflight, custody, and final human checks are complete. No `G` or `A` is precomputed here. Gate PT P-3 remains CLOSED, P-1 remains PENDING, and this document authorizes nothing by itself.
