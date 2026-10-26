# AI-2 Operational-Scope Amendment — Cleveland D-047 Local Research Artifacts

- **Decision ID:** `AI2-OPERATIONAL-SCOPE-001`
- **Governance PR:** **#54**
- **Revision:** AI-4.2 reconciliation with PR #56/main and bounded authority resolution, 2026-10-26
- **Status:** **PROPOSED / UNRATIFIED / INTERNAL EXCEPTION PROPOSED / EXTERNAL APPLICABILITY RECORD REQUIRED / NOT ACTIVATED**
- **Approval-readiness:** **READY FOR MAINTAINER AND INSTITUTIONAL APPLICABILITY REVIEW; HOLD FOR RATIFICATION AND EXECUTION**
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

### 1.1 Proposed internal-policy resolution — sole narrow D-047 exception

The internal conflict is real and must be amended, not silently reinterpreted:

- D-047 permits a maintainer-authorized, clearly labelled internal exploratory experiment while formal Gate PT P-3 remains closed.
- Before this PR, `docs/research/AI_FIRST_COMPLETION_STRATEGY.md` §5.1(2) required Gate PT **P-1 target sign-off and P-3 protocol sign-off** before running `ai/` to fit/save any real-patient model bundle or `shap_background.json` derivative on Cleveland or UCI-412.

This PR resolves that repository-policy inconsistency by amending the AI-first boundary in the same governance change. P-1/P-3 remain the AI-first rule for formal `ai/` real-data artifact work and every other `ai/` cohort, panel, evaluation, and artifact route covered by §5.1(2). This does not rewrite the separate historical D-047/D-048 exploratory-runner governance. The sole exception is `AI2-OPERATIONAL-SCOPE-001`, and only after both its governance ratification `G` and separate registry-only activation `A`:

- exactly `DA-A2` / `UCI-45 / processed.cleveland.data` and `da_a2_resting_v1` with the five predictors named above;
- exactly the frozen D-047 methodology and hash bindings in §2 and §4;
- exactly one guarded, local, native-Windows, CPU-only run;
- exactly one private `RESEARCH_ONLY` bundle and the minimum patient-derived `shap_background.json` required by that frozen pipeline, under the custody, acceptance, no-sharing, and no-inference controls below; and
- no external-cohort evaluation, additional operation, expanded reporting claim, or reuse as a general precedent.

Until `G` and `A` both exist, the pre-existing AI-first prohibition remains fully effective. The exception does not open the broader Step 9 multi-cohort program. It does not mark P-1 complete, open or close P-3, convert the pilot into formal Gate PT research, or weaken P-4/P-5. Any expansion returns to the ordinary P-1/P-3 route and requires a new decision.

This is the narrowest coherent project scientific/engineering decision because it adds persistence and a necessary training-row derivative to an already bounded internal method without adding participants, source fields, a target, a model family, a cohort, or a clinical use. Persistence nevertheless increases custody risk; private local storage and non-disclosure are controls, not proof of anonymity or external permission.

**The maintainer's required internal decision is therefore explicit:** accept or reject this exact exception and the accompanying AI-first text. Accepting it is a project-governance decision only. It is not a waiver of P-1/P-3 statuses and cannot supply supervisor, ethics, data-protection, licensing, institutional, or regulatory permission.

### 1.2 Source, license, and external-applicability determination

The following source review used metadata and legal/regulatory documents only on 2026-10-26. No patient-level file was accessed for this review. It separates what the evidence establishes from what only an authorized external or institutional body can decide.

| Question | Evidence reviewed | Consequence for this exact proposal |
|---|---|---|
| What is the source? | The [official UCI Heart Disease page](https://archive.ics.uci.edu/dataset/45/heart+disease), DOI `10.24432/C52P4X`, identifies the donated 1988 database, 303 Cleveland instances, and `processed.cleveland.data`. It says names and Social Security numbers were removed/replaced with dummy values. | This supports **public, historical, direct-identifier-removed** provenance in UCI's stated sense. It does not establish irreversible anonymity, non-identifiability under every applicable law, participant consent for this new use, or an ethics exemption. The amendment uses only the five resting predictors and the already governed target; it does not restore identifiers or attempt linkage/re-identification. |
| May the licensed material be used and adapted? | UCI labels the dataset [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/legalcode). Sections 2(a)(1) and 4 permit reproduction, sharing, adaptation, and database extraction/reuse subject to the license; §3(a) requires attribution and modification notices when licensed material is shared. Section 2(b)(1) does not generally license privacy/publicity/personality rights. | **No separate copyright/database-license approval is identified for the proposed private local adaptation.** Preserve UCI/creator/DOI/license attribution in research records and any later aggregate report, and indicate modifications where applicable. CC BY 4.0 is not privacy, ethics, institutional, or regulatory clearance. This amendment authorizes no public redistribution of source rows, the bundle, SHAP background, or other patient-derived artifacts. |
| Does Egyptian PDPL necessarily disappear because the source is public and names were removed? | The [official PDPC FAQ](https://pdpc.gov.eg/) defines protected data through direct or indirect identifiability and treats health data as sensitive. Its listed exclusions do not include a general student or scientific-research exclusion. The English translation of [Law 151/2020](https://www.acc.com/sites/default/files/program-materials/upload/Data%20Protection%20Law%20-%20Egypt%20-%20EN%20-%20MBH.PDF) likewise covers electronic analysis of directly/indirectly identifiable data and includes controller/processor license-or-permit duties. The translated [Executive Regulations, Decision 816/2025](https://shehatalaw.com/wp-content/uploads/2026/01/Shehata-Partners-Publications-Data-Protection-Executive-Regulations-English.pdf), Articles 3–4, include licensing language, conditions for specified non-profit statistical/educational secondary processing (including consent, relevance, and encoding when circulating so the person cannot be identified), and AI-training safeguards. | **PDPL applicability is not self-resolved.** Public availability, identifier removal, CC BY, small sample size, non-profit status, and graduation-project status are not, individually or together, a demonstrated exemption. The proposed local-only, no-linkage, no-re-identification, no-new-transfer, private-custody design reduces exposure but does not decide whether the remaining records/derivatives are identifiable or whether a lawful basis, consent condition, license/permit, DPO, records, retention, security, or other duty applies. The one-year compliance transition ending 2026-10-31 is not relied on as permission. |
| Is this automatically exempt from Egyptian clinical-research review? | The current official [EDA Good Regulatory Oversight guideline, EDREX.GL.Bioinn.006 v5, effective 2026-07-01](https://edaegypt.gov.eg/media/2qejszxf/guideline-gcp_en-2026.pdf), read with Clinical Trials Law 214/2020 and Executive Regulation 927/2022, addresses interventional research involving human participants and non-interventional clinical trials. Its definitions include studies/experiments on human participants and non-interventional research in which participants record information about an approved intervention or health history. | This pilot proposes no recruitment, contact, intervention, current-participant measurement, or care decision; it reuses a historical public dataset. Those facts support an applicability review, **not a repository-declared exemption**. The competent institution/REC must determine whether this secondary-data AI pilot is outside that regime or requires IRB/REC or other review. Neither the earlier 2024 guideline nor a foreign “coded data” rule is used to grant an Egyptian exemption. |
| What about institutional and supervisor duties? | No institution, applicable university policy, supervisor determination, REC/IRB determination, data-protection determination, or external approval is identified in the repository evidence. P-3 remains CLOSED and `supervisor_signoff_claimed=false`. | An internal maintainer cannot infer that no institutional duty exists. A supervisor's informal assent would not substitute for an authorized REC/data-protection decision, and a maintainer's ratification would not substitute for any of them. |

The linked Egyptian statute/regulation translations are secondary English aids, not a substitute for review of the official Arabic instruments by a qualified person. This section is an issue-spotting governance record, not a legal opinion.

#### Required human decision before ratification

Before recording the ratification comment, the maintainer must **accept or reject the exact internal exception in §1.1** and, if accepting it, obtain and reference a dated written **coordinated institutional applicability record** for this exact bounded run. The institution's authorized research-compliance/ethics and data-protection/legal channels must contribute as their respective remits require; if the institution cannot decide a PDPL question, qualified Egyptian advice or PDPC guidance is required. The record must answer, without relying on this agent's conclusions:

1. **Data protection:** whether the specified source rows and private model/SHAP derivatives are anonymous/non-personal for this use or PDPL applies; if PDPL applies, the lawful basis and any consent, secondary-processing, license/permit, DPO, record, retention, security, or transfer duties, and how each is satisfied before execution.
2. **Research ethics/regulatory scope:** whether this historical public secondary-data engineering pilot is outside Law 214/2020/EDA and institutional REC/IRB review, or what review/approval/notification is required. Any required approval must actually be obtained; a requested or pending review is insufficient.
3. **Academic/institutional authority:** whether graduation-project policy requires supervisor or other approval for this internal exploratory artifact route notwithstanding closed P-3, and whether private local derivatives plus aggregate-only reporting are permitted. Any required approval must actually be obtained.
4. **Conditions and identity:** the deciding body/person, authority, date, exact scope, conditions, and evidence reference. The record must cover this run, not a generic course policy or another cohort.

A limited applicability determination or permission does not reopen P-3 or make this formal supervisor-approved research. The frozen `INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED` label and `supervisor_signoff_claimed=false` fields deny a **formal Gate PT supervisor-signoff claim**; they must not be used to deny or conceal an actual limited institutional permission. If the authorized institution requires this work to proceed as formal supervisor-approved/Gate PT research, or requires a label inconsistent with those frozen fields, this amendment is incompatible and must not be activated; that would require separate governance and engineering review outside this PR.

This is deliberately an **applicability determination first**, not an assertion that an IRB approval, PDPC license, or supervisor sign-off is always required. If the authorized record concludes that a particular approval is not required, retain that reasoned determination; if it concludes one is required, that approval becomes a precondition. No such record exists now, so external readiness remains **HOLD**. Repository ratification cannot create it.

## 2. Verified references and immutable bindings

The following references were checked against Git objects on the current PR #54 branch after merging latest main (including PRs #55 and #56). They are historical or current-object hashes, **not predictions of a future merge**.

| Binding | Verified value / rule |
|---|---|
| Original D-047 governance PR | #31; exact owner authorization comment `AUTHORIZE-D047-INTERNAL-CLEVELAND` |
| D-047 governance merge | `434e49a37e6e60b8b91498dde0f9d02dc1af18de` |
| D-047 protocol path | `docs/research/gate-pt/02_d047_internal_exploratory_cleveland_PROTOCOL_PROPOSED.md` |
| Protocol Git-blob SHA-256 at D-047 merge, merged PRs #55/#56, and this PR | `96c26829ff73893dab8ee091b2eaea1592479a1e0528ae6832651a9688ea3c86` |
| Current registered plan path | `research/experiments/cleveland_d047_exploratory_plan.v0.1.json` |
| Current registered-plan SHA-256 on merged PRs #55/#56 and this PR | `2c441c4c44d61e2734277d3ee788ce09b5dd4cc8e54cbeff741374a428646c6a` |
| Five-field panel | `da_a2_resting_v1` |
| Panel-contract SHA-256 | `c18ad4cd2cf08f6fefb2e340573760da7000bc1d8eb4ad38783b873c018e57b8` |
| Merged AI-3.2 engineering PR | #55; head `f3c1676561c60733b878d66643484af6fb418e83`; merge `6a5466a4ddc19aa315007ead9985cfd1f4049d04` |
| Merged AI-4.1 synthetic CLI PR | #56; head `5fccd2b88cb7db65328c1595532bd623e52e5703`; merge `a7dd334b5717c60290627a0959284dd4d93c3ca9` |
| AI-first boundary reconciled by this PR | `docs/research/AI_FIRST_COMPLETION_STRATEGY.md` §2.2 and §5.1(2); its future bytes are reviewed at `G`, not pre-hashed here |
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

## 4. Engineering reconciliation with merged PRs #55 and #56

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

### 4.3 PR #56 CLI is not an activation or real-execution route

Latest main includes PR #56 (`a7dd334b5717c60290627a0959284dd4d93c3ca9`). Its `python -m ai` interface provides only `panels`, `verify-bundle`, `predict`, and `demo`:

- `demo` is an isolated synthetic train-to-predict demonstration;
- `predict` accepts only synthetic-provenance `AI1_GENERIC_V1` bundles and rejects real-provenance and `CLEVELAND_D047_FROZEN_V1` prediction before bundle deserialization;
- `verify-bundle` performs integrity or trusted-local verification without deserializing the model; successful verification is not ratification, activation, acceptance of a failed run, or permission to load/predict; and
- there is no real-Cleveland `execute` command.

Accordingly, PR #56 changes neither this amendment's activation controls nor its inference prohibition. The only supported future real-Cleveland execution path remains `execute_guarded_cleveland_d047_run` after `G`, `A`, local authorization, and every preflight/custody requirement. The final trusted-local verification inside that wrapper is an acceptance check, not permission to call `ResearchCadPredictor` or the synthetic CLI for real inference.

## 5. Mandatory two-stage governance and activation sequence

### Stage 0 — current state

- PR #54 is open, unmerged, and unratified.
- The internal inconsistency is resolved **in this proposal's coordinated text**, but the exception has no effect before `G` and `A`.
- The written external/institutional applicability record required by §1.2 has not been supplied; any approvals it identifies remain outstanding.
- The production operational registry is empty.
- No registry-only activation PR exists.
- No real execution, packaging, inference, or retry is allowed.

### Stage 1 — governance merge `G`

Only after the maintainer accepts the exact §1.1 exception and the §1.2 applicability record plus every approval it requires is complete may the authorized human:

1. review the final PR #54 diff and confirm it changes exactly `docs/research/AI_FIRST_COMPLETION_STRATEGY.md` and `docs/research/gate-pt/17_ai2_operational_scope_amendment.md`, with no code, test, protocol, plan, registry, or manifest change;
2. record the exact owner comment **`RATIFY-AI2-OPERATIONAL-SCOPE-EXPANSION`** on PR #54, explicitly referencing both the accepted internal-scope decision and the written external/institutional applicability record in the review record;
3. merge PR #54 independently of any activation change; and
4. record the actual GitHub merge commit as `G`, then verify the amendment, reconciled AI-first boundary, protocol, and plan bytes at `G`.

A PR approval review, CI result, AI-3.2 merge, local manifest assertion, or operator-confirmation string is not the required ratification comment and does not replace human review.

### Stage 2 — separate registry-only activation merge `A`

After `G`, a separate activation PR may change **only** the single `RATIFIED_OPERATIONAL_SCOPE_AMENDMENTS` entry in `ai/execution.py`. It must not change either governance document, the protocol, plan, tests, training, packaging, inference, or any other file. It must be reviewed and merged separately; its actual merge commit is `A`.

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
- the amendment document hash, the reconciled AI-first exception text, and unchanged protocol/plan bindings at `G`;
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

The top-level D-047 PR/merge fields remain bound to historical PR #31. The amendment fields separately bind PR #54, `G`, and `A`; they must not be conflated. The two boolean flags do not self-authorize operations—the independent trusted registry entry and all hash/Git checks remain necessary. The `experiment_type` and `supervisor_signoff_claimed=false` values retain the limited formal-Gate-PT meaning in §1.2; they do not replace or conceal the separate applicability record. If that record requires inconsistent formal status or wording, stop rather than editing the manifest to force a fit.

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
| Internal authority | Maintainer acceptance or rejection of the exact §1.1 exception and coordinated AI-first text; P-1/P-3 statuses remain unchanged and no broader route is inferred. |
| External/institutional applicability | The dated written §1.2 record from authorized research-compliance/ethics and data-protection/legal channels, plus every approval it requires. `supervisor_signoff_claimed=false` denies formal Gate PT supervisor sign-off, not a separately documented limited permission, and is not a waiver; maintainer authority is not an external exemption. |
| License and redistribution | Preserve the verified CC BY 4.0 attribution/source/DOI/license record and modification notices where applicable; confirm institutional policy through §1.2. The license does not decide privacy or ethics, and no patient-derived artifact redistribution is authorized here. |
| GitHub ratification | Exact owner comment, comment timing, PR #54 merged state, full `G`, and independent review of the final document diff. |
| Activation review | Separate PR content review, full `A`, registry-only content, `G` ancestry, exact `G..A` diff, and equality of both governance/code-revision fields to `G`. |
| Local signature | Actual signer identity, authority, timestamp after final review/`G`/`A`, and understanding that the attestation is not a cryptographic signature. |
| Source provenance | Protected source SHA/byte size, canonical official-source attestation, D-046 authorization, and license snapshot. Hashes prove byte identity, not official origin or participant independence. |
| Native Windows environment | Supported native Windows/Python environment, CPU-only execution, dependency versions, interactive local operation, and actual Win32 NTFS owner/DACL checks. POSIX synthetic tests do not establish native Windows acceptance. |
| Custody | Private source/manifests/license snapshot/output root/signing key, no symlink/junction/reparse escape, no cloud sync or external sharing, and secure retention/disposition. |
| Run discipline | Exactly one authorized run; no new-process retry, no configuration reduction, no response-driven model/panel iteration, and human disposition of every failure. |
| Reporting | Aggregate-only disclosure review, no small-cell or row-level leakage, separate historical/enhanced estimands, honest uncertainty and limitations, and no clinical/external-validation wording. |
| Inference prohibition | No call to `ResearchCadPredictor`, PR #56 `predict`, or any serving/UI path for this real bundle under this amendment, even though trusted loading is used as an acceptance check. |

## 10. Execution-permit checklist

Every box must be satisfied by human evidence before the wrapper is invoked. The current state fails this checklist.

- [ ] Maintainer accepted the exact §1.1 exception and coordinated AI-first text; P-1/P-3 statuses remain unchanged.
- [ ] The dated §1.2 institutional applicability record is complete, and every data-protection, ethics/REC, regulatory, supervisor, or other approval it requires has actually been obtained.
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

**Internal contradiction:** **RESOLVED IN THIS PROPOSAL; NOT YET EFFECTIVE.** The coordinated AI-first and amendment text now states one rule for the `ai/` real-bundle/SHAP boundary: P-1/P-3 govern the formal route and every other `ai/` operation covered by §5.1(2), while only the exact D-047 artifact/SHAP exception can proceed through `G` → `A` without changing those gate statuses. There is no implied waiver and no broader Cleveland, Hungary, UCI-412, or AngioCAD authorization. If the maintainer rejects that text, the original prohibition remains and this proposal must not be ratified.

**External approval/applicability:** **HOLD.** UCI's CC BY 4.0 license supports private local adaptation with attribution obligations; it is not an external ethics or data-protection approval. No authorized institutional applicability record or external approval has been supplied. The remaining independently required human evidence is the exact §1.2 written determination and any approval it identifies—not an assumed blanket IRB/PDPC requirement and not a self-declared exemption.

**Exact pre-ratification decision:** the maintainer must accept the narrow internal exception and obtain/reference the coordinated institutional record answering §1.2(1)–(4). Only then may the owner record the ratification comment and merge `G`. P-1 remains PENDING and P-3 remains CLOSED throughout.

**Engineering and activation:** PR #55 resolved the verified frozen-method and guarded-wrapper implementation issues; PR #56 adds no real execution route and does not weaken those controls. The implementation is ready for final native-Windows acceptance review, **not ready to execute today**. Conditional on valid `G` and `A`, guarded execution is ready only after the local manifest, actual native Windows/Python environment, protected custody/ACLs, full preflight, and all human checks pass. Activation alone is insufficient, and any failed run requires a new human decision rather than retry. No `G` or `A` is precomputed here, and this document authorizes nothing by itself.
