# AI-6.1 — Security & Failure-Mode Review, and Gated Windows-Local Runbook

- **Companion scope proposal:** `18_bounded_offline_diagnostic_inference_scope.md`
- **Interface version:** `cardioassist.ai.bounded_offline_diagnostic_inference/v1`
- **Status:** engineering complete; **real-bundle execution NOT AUTHORIZED**. The
  new scope registry is empty. This runbook is deliberately inoperable until the
  two human decisions in the companion document are taken.

## 1. Trust boundaries and control map

| # | Threat / failure mode | Control (existing unless marked NEW) | Fail-closed code (examples) | Test evidence |
|---|---|---|---|---|
| 1 | Training amendment silently reused as inference authorization | NEW empty registry `RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES`, checked before any bundle work | `diagnostic_scope_not_ratified` | `test_training_scope_alone_does_not_authorize_inference`, `test_production_diagnostic_registry_is_empty_and_fails_closed` |
| 2 | Self-declared local manifest treated as ratification | NEW field-for-field comparison with reviewed registry entry + Git ancestry, frozen document bytes at `G2`, clean HEAD == approved revision | `diagnostic_scope_claim_mismatch`, `diagnostic_governance_commit_missing`, `diagnostic_governance_document_hash_mismatch`, `diagnostic_execution_revision_mismatch`, `diagnostic_worktree_not_clean` | `test_manifest_claims_cannot_override_trusted_record`, `test_stale_or_dirty_execution_revision_fails_closed` |
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
| 14 | New code represented as part of frozen `A`; training governance `G`/`A` reused as diagnostic ratification | separate version string, separate files, frozen `ai/execution.py` and `ai/cli.py` untouched; trusted record refuses `G`/`A` as its governance merge or approved revision; regression test checks `A` lacks the new files when `A` is locally available | `diagnostic_scope_reuses_training_activation` | `test_new_code_is_post_activation_and_frozen_execution_file_is_unchanged`, `test_frozen_bindings_match_activated_training_amendment_and_panel`, `test_trusted_record_cannot_bind_a_different_bundle_or_operation` |
| 15 | Obsolete "registry must be empty" CI sentinels | replaced (not deleted/skipped) with activated-registry security assertions: exactly the ratified record, frozen hash bindings, no inference/serving operation, empty new diagnostic registry, wrapper still requires operator confirmation | n/a | `test_cli_preserves_activated_training_registry_and_never_imports_execution`, `test_ratified_operational_registry_is_exactly_activated_training_amendment` |

### Honest limitations

- A local operator manifest is an **attestation**, not a cryptographic signature.
  Code cannot verify human identity, authority, intent, or GitHub evidence.
- Code verifies local Git consistency only (commit existence, ancestry, bytes,
  clean HEAD). PR merged state, exact owner comment, review quality, and
  `G2..A2` content review remain human-only.
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

> **Currently blocked.** `RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES` is empty, so step
> 6 below will fail closed with `diagnostic_scope_not_ratified`. Do not create a
> fake registry entry, reuse the training authorization, or edit the bundle to
> make it pass.

Prerequisites: native Windows workstation with the private accepted bundle,
Python 3.11/3.12 with `research/experiments/requirements.txt`, the same private
local HMAC signing key used at `A`, a clean checkout at the activation revision
`A2`, and human completion of the §7 checklist in the companion document.

PowerShell, from the repository root (replace only the bracketed placeholders;
never paste key material into a shared terminal or log):

```powershell
# 1. Human scope authorization G2 and registry-only activation A2 are MERGED.
#    Confirm the checked-out, clean revision equals the registry's
#    approved_code_revision (A2). No uncommitted tracked changes are allowed.
git rev-parse HEAD
git status --porcelain --untracked-files=no

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
#    ai/examples/diagnostic_authorization.template.json. Fill every placeholder
#    with the human-verified G2/A2/PR/comment/document-hash/manifest-hash values,
#    a real signer and post-G2/A2 timestamp, the exact attestation, and the
#    exact operator confirmation phrase. This is a human attestation, not a
#    cryptographic signature; no approval may be invented.
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
- Exit code `0` / `"status":"OK"`: verify `scope`, `bundle.manifest_sha256`,
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
maintainer-supplied aggregate results. All CI evidence is synthetic: in-memory
cohorts, simulated accepted bundles, throwaway Git repositories, and
in-process monkeypatched registries clearly labelled SYNTHETIC TEST SIMULATION.
