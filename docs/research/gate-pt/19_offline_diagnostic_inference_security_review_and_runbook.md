# AI-6.1 — Security & Failure-Mode Review, and Gated Windows-Local Runbook

- **Companion scope document:** `18_bounded_offline_diagnostic_inference_scope.md` (`G3` revision)
- **Interface version:** `cardioassist.ai.bounded_offline_diagnostic_inference/v1.1` (unchanged)
- **Engineering state:** implementation complete at `I2` (PR #59, merged); test
  regressions repaired at `I3` (PR #62, merged, tests only); validator, guard
  inventory and failure-mode controls unchanged by the repair.
- **Governance state:** historical scope decision **RATIFIED AT `G2`** for `I2`
  (PR #60, exact owner comment
  `RATIFY-BOUNDED-OFFLINE-DIAGNOSTIC-INFERENCE-SCOPE`); the `G3` re-baseline that
  binds this runbook to `I3` is **PROPOSED and NOT YET RATIFIED**. See the
  companion document §0.
- **Operational status:** **real-bundle execution NOT AUTHORIZED and NEVER
  PERFORMED**. No activation revision (`A2`/`A3`) has been merged; the new scope
  registry `RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES` is `{}` at `I3` and must remain
  `{}` at `G3`. This runbook is deliberately inoperable until the two human
  decisions in the companion document are taken for the new baseline.

## 1. Trust boundaries and control map

| # | Threat / failure mode | Control (existing unless marked NEW) | Fail-closed code (examples) | Test evidence |
|---|---|---|---|---|
| 1 | Training amendment silently reused as inference authorization | NEW independent registry `RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES`, checked before any bundle work; lifecycle tests assert it holds at most one separately ratified scope (empty today) and that the unactivated state fails closed | `diagnostic_scope_not_ratified` | `test_training_scope_alone_does_not_authorize_inference`, `test_production_registry_equals_checked_in_source_and_is_scope_bounded`, `test_unactivated_registry_fails_closed_before_any_bundle_work` |
| 2 | Self-declared local manifest treated as ratification | NEW field-for-field comparison with reviewed registry entry + independently resolved `HEAD == A3`, `I3` ancestor of `G3` with docs-only changes, `G3` ancestor of HEAD, frozen document bytes at `G3`, clean tracked worktree | `diagnostic_scope_claim_mismatch`, `diagnostic_activation_revision_mismatch`, `diagnostic_governance_baseline_missing`, `diagnostic_governance_ancestry_failed`, `diagnostic_governance_document_hash_mismatch`, `diagnostic_worktree_not_clean` | `test_manifest_claims_cannot_override_trusted_record`, `test_activated_registry_still_enforces_authorization_and_git_evidence`, `test_activation_negative_cases_on_committed_history` |
| 3 | Registry entry broadened to another bundle/operation | NEW defence-in-depth validation of the trusted record itself against frozen identity constants and the single approved operation | `diagnostic_scope_registry_entry_invalid` | `test_trusted_record_cannot_bind_a_different_bundle_or_operation` |
| 4 | Missing/ambiguous human invocation | NEW exact operator confirmation phrase + strict local authorization document (status, attestation tokens, signer, timestamp, declarations, execution boundary) | `diagnostic_operator_confirmation_required`, `diagnostic_authorization_not_effective`, `diagnostic_human_attestation_invalid`, `diagnostic_execution_boundary_invalid` | `test_unauthorized_operator_or_provenance_fails_closed`, `test_local_authorization_negative_cases` |
| 5 | Symlink/junction/reparse escape, unignored repo file, oversized or malformed local JSON | NEW strict local-file reader: regular non-reparse file, size ceiling, duplicate-key rejection, `parse_constant` rejection, explicit finite-tree walk (catches `1e400`), Git-ignored when inside checkout | `diagnostic_local_file_untrusted`, `diagnostic_local_file_not_git_ignored`, `diagnostic_duplicate_json_key`, `diagnostic_non_finite_json_constant`, `diagnostic_non_finite_local_value` | `test_local_authorization_file_rejects_malformed_or_non_finite_json`, `test_local_authorization_file_rejects_symlink_and_oversize` |
| 6 | Real patient record disguised as synthetic input | NEW envelope + per-record declaration, exact five-field panel, reuse of `validate_clinical_record(require_synthetic=True)` before any bundle verification | `diagnostic_non_synthetic_input_rejected`, `diagnostic_input_wrong_panel_schema`, `diagnostic_input_panel_mismatch`, `diagnostic_input_missing_required_feature`, `invalid_numeric_value`, `unit_mismatch` | `test_malformed_wrong_panel_or_non_finite_inputs_fail_closed`, `test_wrong_panel_is_rejected_before_any_bundle_verification` |
| 7 | Untrusted/corrupt bundle; malicious pickle; wrong key/root | `verify_trusted_local_bundle`: containment, Win32 NTFS DACL / POSIX ownership, SHA-256 digests, HMAC-SHA256 producer authentication, layout, quarantine fast path | `untrusted_bundle_producer_signature`, `untrusted_bundle_location`, `bundle_symlink_prohibited`, `file_sha256_mismatch` | `test_wrong_signing_key_and_untrusted_root_fail_closed` plus existing packaging suites |
| 8 | Unaccepted, quarantined, renamed, substituted, or pre-acceptance bundle | post-run acceptance gate in packaging + NEW explicit re-verification of marker schema/version/`accepted_for_loading`/directory/source binding, quarantine absence, inventory, pinned `manifest.json` digest, full model/panel/provenance identity | `bundle_post_run_acceptance_missing`, `bundle_post_run_acceptance_mismatch`, `bundle_quarantined_not_accepted`, `diagnostic_bundle_layout_invalid`, `diagnostic_manifest_digest_mismatch`, `diagnostic_bundle_identity_mismatch`, `diagnostic_bundle_provenance_invalid`, `diagnostic_bundle_panel_mismatch` | `test_quarantine_absent_acceptance_and_tampered_marker_fail_closed`, `test_exact_bundle_identity_and_manifest_digest_mismatch_fail_closed`, `test_wrong_registered_panel_in_descriptor_fails_closed` |
| 9 | Bundle modified or re-signed for another purpose; retraining/tuning | read-only path; NEW modules contain no training/packaging/marker-write calls; byte-for-byte bundle hash check before/after a run | `diagnostic_loaded_bundle_identity_mismatch` | `test_diagnostic_happy_path_verifies_scores_shap_and_certified_lime`, `test_new_modules_have_no_network_or_mutation_imports` |
| 10 | Misreported score, broken calibration, or fake "exact" SHAP | NEW independent recomputation from the verified `calibration.json`, logistic-link checks, repeat-prediction determinism, exact SHAP additivity/target/feature-set checks | `diagnostic_non_finite_value`, `diagnostic_score_scale_inconsistent`, `diagnostic_calibration_mismatch`, `diagnostic_score_not_deterministic`, `diagnostic_shap_not_exact`, `diagnostic_shap_decomposition_failed`, `diagnostic_shap_target_misaligned` | `test_independent_verifier_rejects_non_finite_and_inconsistent_scores`, `test_independent_verifier_rejects_miscalibrated_output` |
| 11 | Low-fidelity, unstable, or non-finite LIME weights presented as trustworthy | certified LIME + stability on registered seeds + `assess_lime_quality`; weights emitted **only** for `ACCEPTABLE_LOCAL_APPROXIMATION`, otherwise suppressed; optional strict fail-closed mode | `diagnostic_lime_stability_missing`, `diagnostic_lime_scale_mismatch`, `diagnostic_lime_target_misaligned`, `diagnostic_lime_quality_not_acceptable`, `diagnostic_non_finite_value` | `test_low_quality_lime_weights_are_never_trusted`, `test_lime_stability_assessment_is_mandatory`, `test_independent_verifier_rejects_non_finite_lime_weight` |
| 12 | Serving, telemetry, upload, network egress, or backend coupling | NEW modules use no network imports/calls; never imported by `backend/app/`; general `python -m ai` CLI unchanged and still rejects real-provenance bundles; output is stdout JSON only, no file writes | `cli_real_provenance_bundle_not_supported` (general CLI) | `test_new_modules_have_no_network_or_mutation_imports`, `test_general_cli_and_backend_never_import_diagnostic_interface`, `test_general_synthetic_cli_still_refuses_real_provenance_bundle` |
| 13 | Local paths, key material, or patient-derived values leaked in errors/output | typed value-redacting errors, CLI path redaction, aggregate-only report (no input feature values, no background rows, no local paths, SHA-256 digests only) | n/a | `test_diagnostic_happy_path_verifies_scores_shap_and_certified_lime`, `test_diagnostic_cli_happy_path_and_fail_closed_output` |
| 14 | New code represented as part of frozen `A`; training governance `G`/`A` reused as diagnostic ratification | separate version string, separate files, frozen `ai/execution.py` and `ai/cli.py` untouched; trusted record refuses `G`/`A` (and training governance PR #54) as its `I3`/`G3` baselines; regression test checks `A` lacks the new files when `A` is locally available | `diagnostic_scope_reuses_training_activation` | `test_new_code_is_post_activation_and_frozen_execution_file_is_unchanged`, `test_frozen_bindings_match_activated_training_amendment_and_panel`, `test_trusted_record_cannot_bind_a_different_bundle_or_operation` |
| 15 | **Circular self-referential activation SHA** (`A3` in its own tracked registry) | v1.1 stores NO activation revision in tracked code: registry holds only `I3`/`G3`/doc hash/manifest digest; `A3` lives only in the ignored local operator authorization and is checked against `git rev-parse HEAD` | `diagnostic_scope_registry_self_referential`, `diagnostic_activation_revision_malformed`, `diagnostic_activation_revision_mismatch` | `test_committed_g2_to_a2_activation_is_realizable`, `test_activation_template_has_no_self_referential_revision_field`, `test_activation_negative_cases_on_committed_history` |
| 16 | Activation commit smuggles training/inference/CLI/security changes, or a runtime registry injection | `G3 -> A3` diff must be exactly `M ai/diagnostic_scope.py`; committed sources at `G3`/`A3` are AST-parsed, the single registry literal is masked and ALL remaining bytes must be identical; `G3` registry must be `{}`; `A3` registry must contain exactly one scope; literal committed registry must equal the in-process registry | `diagnostic_activation_diff_not_registry_only`, `diagnostic_registry_content_change_unapproved`, `diagnostic_registry_baseline_not_empty`, `diagnostic_registry_activation_not_single_scope`, `diagnostic_registry_live_state_mismatch`, `diagnostic_registry_source_unparsable`, `diagnostic_registry_literal_invalid` | `test_full_synthetic_diagnostic_run_at_committed_a2`, `test_live_registry_injection_does_not_match_committed_registry`, `test_registry_source_parser_rejects_computed_or_duplicate_assignments` |
| 17 | Obsolete **training-registry** "registry must be empty" CI sentinels | These sentinels belong to the FROZEN TRAINING registry (`ai/execution.py::RATIFIED_OPERATIONAL_SCOPE_AMENDMENTS`, activated at `A` by PR #58), not to the diagnostic registry. They were replaced (not deleted or skipped) by post-activation security assertions: exactly the one ratified training amendment with its frozen hash bindings, no inference/serving operation, and the wrapper still requiring the operator confirmation. The **diagnostic** registry's lifecycle is asserted separately by the lifecycle tests listed in §1.1. | n/a | `test_cli_preserves_activated_training_registry_and_never_imports_execution`, `test_ratified_operational_registry_is_exactly_activated_training_amendment` |

### 1.1 Lifecycle-state-aware diagnostic regressions (repair merged at `I3`, PR #62)

Rows 1, 2 and 17 previously cited evidence that no longer describes the suite: one
named test (`test_production_diagnostic_registry_is_empty_and_fails_closed`) was
**replaced**, and one row described the new diagnostic registry as "empty" as an
unconditional post-activation assertion. The merged test repair (PR #62,
`8ee00c7`, tests only, six files under `tests/experiments/`) makes the diagnostic
activation regressions meaningful in **both** lifecycle states:

- **Unactivated (the actual state today):** the production registry is `{}`, and
  any attempt to reach bundle verification or inference fails closed with
  `diagnostic_scope_not_ratified` before any bundle work — asserted by
  `test_unactivated_registry_fails_closed_before_any_bundle_work`.
- **Activated (the future state after a registry-only merge):** the registry holds
  exactly the one separately ratified scope, whose record must pass the
  production trusted-record validation, bind the frozen governance-document path,
  authorize exactly `offline_synthetic_input_diagnostic_inference`, never reuse
  the frozen training `G`/`A` pair, and carry no self-referential activation
  field — asserted by
  `test_production_registry_equals_checked_in_source_and_is_scope_bounded`,
  `test_activated_registry_still_enforces_authorization_and_git_evidence` and
  `test_gitignore_and_changelog_keep_activation_registry_only`.
- **Every state:** unknown and bare scope ids fail closed
  (`test_unknown_and_bare_scopes_fail_closed_in_every_registry_state`), and the
  training-registry sentinels (`row 17`) additionally assert in both states that
  no diagnostic record may reuse the training governance merge `G`, the frozen
  activation revision `A`, or training governance PR #54.

The synthetic-history fixture now locates the registry assignment with the
**production** parser and self-checks that the substituted source reads back as
exactly the requested literal with byte-identical masked source, so the fixture
can no longer drift from the production activation guard. The activation
feasibility tests still build a genuine empty-registry baseline before the
synthetic activation commit, which keeps the "pre-existing non-empty baseline is
refused" negative control intact.

Two naming caveats, so the evidence is read correctly: the synthetic-history test
names (`test_committed_g2_to_a2_activation_is_realizable`,
`test_full_synthetic_diagnostic_run_at_committed_a2`) use `g2`/`a2` as **generic
historical labels** for "governance baseline" and "activation revision"; the same
code path verifies the `I3 -> G3 -> A3` sequence because the names are not schema
fields. No test was deleted, skipped, xfailed, or weakened by the repair.

### Honest limitations

- A local operator manifest is an **attestation**, not a cryptographic signature.
  Code cannot verify human identity, authority, intent, or GitHub evidence.
- Code verifies local Git consistency only (commit existence, ancestry, bytes,
  clean HEAD, strict registry-only diff). PR merged state, exact owner comment,
  review quality, and the human judgement that the one registry record is the
  intended activation remain human-only. The v1.1 committed-history pytest
  proves the procedure is realizable; it does not prove any human approval.
- Win32 NTFS DACL verification is performed by the existing platform API path on
  native Windows; Arena tests simulate POSIX permissions and cannot prove
  Windows behaviour.
- HMAC authenticity is only as strong as the maintainer's private signing key
  custody. The manifest digest pinned at activation is maintainer-supplied and
  was not computed in Arena.
- SHAP backgrounds are patient-derived training projections. No background
  values, training rows, or input feature values are emitted by the report, and
  no artifact sharing is authorized.
- SHAP is additive on **calibrated log-odds**, never on calibrated probability.
  LIME is a local surrogate with no efficiency guarantee. Neither is a clinical
  or causal claim; outer-fold dispersion is descriptive CV sensitivity, not
  patient-specific uncertainty.

## 2. Windows-local diagnostic procedure — EXECUTE ONLY AFTER §5 OF THE SCOPE DOCUMENT

> **Currently blocked.** `RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES` is `{}` at `I3`
> and must still be `{}` at `G3`: no activation revision exists, no real-bundle
> inference has ever been executed, and `G3` itself is **PROPOSED, not yet
> ratified**. Once an activation exists, step 6 below fails closed with
> `diagnostic_scope_not_ratified` unless that activation is real. Do not create a
> fake registry entry, reuse the training authorization, reuse the PR #60
> ratification comment as approval of the `G3` text, or edit the bundle to make
> it pass.

Prerequisites: a **fresh** exact owner ratification comment on the new governance
PR and its human merge (`G3`), a separate merged registry-only activation (`A3`),
a native Windows workstation with the private accepted bundle, Python 3.11/3.12
with `research/experiments/requirements.txt`, the same private local HMAC signing
key used at `A`, a clean checkout at the activation revision `A3`, and human
completion of the §7 checklist in the companion document. The PR #61 activation
candidate is superseded for this route and must not be used.

PowerShell, from the repository root (replace only the bracketed placeholders;
never paste key material into a shared terminal or log):

```powershell
# 1. Human scope authorization I3/G3 and registry-only activation A3 are MERGED.
#    A3 is NOT in any tracked file. Read its actual SHA here, AFTER the merge,
#    then paste it into the ignored local authorization document in step 3.
#    G3 and I3 must be ancestors of HEAD; the G3..HEAD diff must be registry-only.
git rev-parse HEAD                       # this is A3 -> activation_merge_commit_sha
git status --porcelain --untracked-files=no   # must print nothing
git log --oneline -5
git diff --name-status G3..HEAD         # must be exactly: M  ai/diagnostic_scope.py

# 2. Read-only identification of the accepted bundle. Do NOT modify, copy into
#    Git, re-sign, or re-package anything. The digest is maintainer evidence
#    that must equal expected_manifest_sha256 in the activated registry.
$bundle = '[PRIVATE_PATH]\cai_real_cleveland_d047_20261027T070610Z_deffa577'
(Get-FileHash -Algorithm SHA256 "$bundle\manifest.json").Hash.ToLowerInvariant()
Test-Path "$bundle\POST_RUN_ACCEPTANCE.json"          # must be True
Test-Path "$bundle\QUARANTINED_DO_NOT_TRUST.json"    # must be False
$m = Get-Content "$bundle\manifest.json" -Raw | ConvertFrom-Json
$m.model.model_id                 # cai_real_da-a2_da_a2_resting_v1
$m.model.selected_model_family    # l2_logistic_regression
$m.model.execution_profile        # CLEVELAND_D047_FROZEN_V1
$m.model.selected_hyperparameters.C                        # 10.0
$m.panel_contract.panel_id        # da_a2_resting_v1
$m.panel_contract.ordered_feature_names                   # age sex cp trestbps restecg
# Any mismatch stops activation; a new human decision is required.

# 3. Create a PRIVATE, Git-ignored local operator authorization document from
#    ai/examples/diagnostic_authorization.template.json. Fill every placeholder:
#    governance_baseline_commit_sha = G3 (the actual governance merge),
#    approved_implementation_commit_sha = I3, activation_merge_commit_sha = the
#    actual A3 from step 1 (local-only), activation_registry_relative_path =
#    ai/diagnostic_scope.py, plus the human-verified governance PR number,
#    exact owner comment, the document SHA-256 recomputed from the raw G3 bytes
#    (never reused from G2), and the manifest-hash values; a real signer and a
#    post-G3/A3 timestamp; the exact attestation; and the exact operator
#    confirmation phrase. This is a human attestation, not a cryptographic
#    signature; no approval may be invented and no A3 value belongs in Git.
#    Save it, e.g., under data\diagnostics\ (ignored by .gitignore).
New-Item -ItemType Directory -Force .\data\diagnostics | Out-Null
notepad .\data\diagnostics\diagnostic_authorization.json

# 4. Create explicitly fabricated synthetic input records (never patient data).
#    Copy ai/examples/diagnostic_synthetic_records_da_a2_resting_v1.json and
#    edit only the invented values if desired. Keep "synthetic": true everywhere.
Copy-Item .\ai\examples\diagnostic_synthetic_records_da_a2_resting_v1.json `
          .\data\diagnostics\diagnostic_input.json

# 5. Install pinned CPU-only dependencies in the existing private venv.
python -m pip install -r research/experiments/requirements.txt
python -m pip check

# 6. Run ONE bounded offline diagnostic invocation. Everything is local; the
#    command writes no files and never contacts a network service.
python -m ai.diagnostic_inference `
  --bundle-dir "$bundle" `
  --trusted-root '[PRIVATE_PARENT_PATH]' `
  --signing-key-path '[PRIVATE_SIGNING_KEY_PATH]' `
  --authorization '.\data\diagnostics\diagnostic_authorization.json' `
  --input '.\data\diagnostics\diagnostic_input.json' `
  --repo-root '.' `
  --operator-confirmation 'I_CONFIRM_BOUNDED_OFFLINE_CLEVELAND_D047_DIAGNOSTIC_INFERENCE' `
  --require-acceptable-lime-quality
```

**Interpreting the result.**

- Exit code `2` / `{"status":"FAIL_CLOSED", ...}`: preserve the error code and
  local evidence for human audit. Do **not** retry automatically, edit the
  bundle, relax a registry field, or suppress a check. A repeated diagnostic
  invocation requires a new explicit human decision.
- Exit code `0` / `"status":"OK"`: verify `scope` reports
  `governance_baseline_commit_sha` (G3), `approved_implementation_commit_sha`
  (I3) and `activation_merge_commit_sha` (A3, the resolved HEAD), plus
  `bundle.manifest_sha256`,
  `bundle.post_run_acceptance_verified`, `bundle.quarantine_marker_absent`, and
  per-record `all_exact_checks_passed`. Confirm `scores.recomputed_calibrated_log_odds`
  equals `scores.calibrated_log_odds`, and `shap.sum_check_passed` is true on the
  calibrated-log-odds scale.
- LIME: use `lime.feature_weights` **only** when
  `lime.feature_weights_trusted` is `true` and
  `lime.status == ACCEPTABLE_LOCAL_APPROXIMATION`. Otherwise the weights are
  deliberately `null`; treat them as unusable. With
  `--require-acceptable-lime-quality` the invocation fails closed instead of
  returning a diagnostic-only low-quality explanation.
- The report is RESEARCH_ONLY, contains no patient record, and is not a clinical
  result. Do not serve it, upload it, or share patient-derived artifacts. If a
  private local copy of the report is needed, redirect stdout with
  `| Out-File -FilePath .\data\diagnostics\report.json -Encoding utf8` into a
  Git-ignored location; the interface itself writes nothing.

## 3. Arena execution statement

Arena did **not** access, hash, verify, load, or run inference on the real
bundle; did not see any patient record or the private signing key; did not
ratify, sign, or activate any scope; and did not reproduce the
maintainer-supplied aggregate results. All test evidence is synthetic: in-memory
cohorts, simulated accepted bundles, and **genuine committed `I2 -> G2 -> A2`
Git histories in throwaway repositories** whose tracked `A2` registry is really
parsed and verified (the same code path verifies any `I3 -> G3 -> A3` sequence;
the `g2`/`a2` suffixes are generic labels, not schema fields).

The `G3` re-baseline PR itself is docs-only: it changed no production code, no
test, no workflow, no example, no registry value, no dataset or bundle, no key,
and no local operator authorization, and it produced no real-bundle inference.
The production registry is `{}` on this branch, exactly as at `I3` and `G2`. The
PR #60 ratification is recorded as the historical decision it was; this PR does
not claim a new ratification, an activation, or a real-bundle run.
