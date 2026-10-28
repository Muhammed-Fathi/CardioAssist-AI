# AI-8 — Source-Specific UCI-412 Standalone Research Model (Synthetic Only)

**Status:** technical report for the open, non-merged implementation PR
[#66](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/66) on branch
`arena/01367b08-cardioassist-ai`.
**Baseline `main` SHA:** `6ecc191800c2f505b80f97bb8261b2ed3cb36af7`.
**Primary implementation commit SHA:** `e8c0cc499c3c296579d790c15837a2825ecb9da6`.
The same PR also carries follow-up commits that add this report, the
dependency-isolated test split, and a pyflakes cleanup; none of them change the
pipeline's runtime behaviour (the deterministic report SHA-256 in §6 is
reproduced identically on the branch head).
**Classification:** engineering artifact + scientific record. **Synthetic
fixtures only — nothing in this document is clinical evidence or a performance
claim about patients.** Gate PT P-3 remains **CLOSED**, P-1 **PENDING**, P-5
**NOT MADE (prohibited)**. Do not self-approve or merge this PR.

### Revision note — final corrections in response to the PR #66 review

The blocking review identified two defects; both are fixed on this same branch
(no new PR, no rebuild, no merge). The branch head before these corrections was
`13430c7ca1f505b80f97bb8261b2ed3cb36af7`.

1. **Fail-open input-context guard (Blocker A).** The cohort validator relied
   on the shared `ai.panels` policy, which *defaults* a missing
   track/source, so a record with no `context` block could slip through. A new
   strict per-record gate `_assert_synthetic_track_a_context` now runs **first**
   for every record and fails closed on any missing/malformed context. It does
   **not** invent a second security policy: the boolean/value admission decision
   is delegated to the already-tested AI-7 route policy
   `_validate_synthetic_input_context` (the same function used by
   `ai.research_routes.resolve_route`), so the source-specific guard cannot
   quietly diverge from the route-layer contract. 27 new regression cases
   (15 test functions) prove the old fail-open path now rejects; see §3 and §10.
2. **No executable end-to-end demonstration (Blocker B).** A new
   `python -m ai uci412-demo` command runs the complete source-specific
   synthetic path as 12 observable, individually-reported stages plus a compact
   success summary, including a *genuine* invalid-input rejection through the
   real validator (not a hardcoded message), with both console and
   machine-readable JSON output. See the new §9 and the companion runbook
   `docs/research/ai8_uci412_research_demo_runbook.md`.

These corrections change **no** scientific result: the full-budget
deterministic report SHA-256 in §6 is reproduced byte-for-byte
(`99bd76f2…119688`), and no frozen/shared pipeline, governance or A3 file is
modified.

---

## 1. Scope and exact work implemented

AI-8 delivers a technically complete, medically defensible, **source-specific**
standalone research model for the UCI-412 (Z-Alizadeh Sani, repository id 412,
internal dataset id `DA-A1`) **basic clinical panel**, exercised entirely on
generated synthetic data. It is a *thin orchestration layer* over the existing,
already-reviewed `ai/` components — it introduces **no second training
framework, feature schema, calibrator, explainer or packager**.

Five deliverables, mapped to files:

| Deliverable | Artifact |
|---|---|
| A — source-specific pipeline | `ai/uci412_research.py` |
| B — research bundle round-trip | `ai/uci412_research.py` (`_package_and_load`, `load_uci412_research_predictor`) reusing `ai/packaging.py`, `ai/inference.py` |
| C — origin-labelled evaluation report | `Uci412ResearchModelReport` in `ai/uci412_research.py` |
| D — machine-readable 16-field input contract | `research/intake/schemas/uci412_basic_clinical_field_contract.v0.1.json` + stdlib validator `research/intake/uci412_field_contract.py` |
| E — AI-7 report factual corrections | `docs/research/ai7_multi_dataset_research_route_system.md` |

New public symbols are exported from `ai/__init__.py`. The ratified A3
Cleveland diagnostic registry (`ai/diagnostic_scope.py`), its exact-revision
guard, HMAC/NTFS security and offline-only authorization are **not imported,
modified or bypassed**. AI-8 is not an authorized A3 replacement. Only
`EXECUTION_PROFILE_AI1_GENERIC_V1` is ever used; the Cleveland
`EXECUTION_PROFILE_CLEVELAND_D047_FROZEN_V1` is a foreign-source profile and is
asserted absent.

## 2. Source, target definition and the non-equivalence register

The bound panel is `da_a1_basic_clinical_v1` (feature dictionary 1.1.0), 16
ordered required columns, panel contract SHA-256
`efd51491c06d808ac3e02a62c45302dd9a57966b6f619b0c604df980ba71a208`.

The target is `t1.uci412.angiographic_cad_ge50.v1`: cross-sectional
angiographic CAD presence, `Cath = "Cad"` when diameter narrowing is
**greater than or equal to 50%** in at least one major coronary artery,
`"Normal"` otherwise. This is **related-but-not-identical** to the UCI-45/
Cleveland target `t1.uci45.angiographic_cad_gt50` which uses a strictly
**greater than 50%** boundary (`num ∈ {1,2,3,4}`). The two targets are never
treated as equivalent, pooled or cross-walked; exactly-50% records cannot be
identified in either categorical release. No cross-source AUROC comparison is
produced anywhere in this work.

UCI-412 and UCI-411 are the **same 303 participants**; UCI-411 is therefore
never an independent cohort or validation set for UCI-412. Source identity and
this overlap are recorded in the report (`same_participants_as_uci411=true`).

The unresolved-question register is preserved verbatim in the contract and is
not silently resolved: S-1 (text token spellings incl. `Fmale`), S-2 (BP
quantity/conditions; mmHg secondary-source), S-3 (PR unit `ppm` vs
beats/min), S-4 (chest-pain elicitation/mutual exclusivity), S-9 (numeric 0/1
direction is secondary-literature supported, not owner-codebook verified),
U-6 (per-field prediction time is workflow inference, not a documented fact),
H-01 (the ≥50% vs >50% target boundary difference).

## 3. Synthetic cohorts, Cleveland separation and source-specific guards

All records are produced by the existing deterministic builder
`build_synthetic_uci412_basic_clinical_cohort`. The default configuration uses
a development cohort of **n = 240** (seed `20261028`; 189 positive / 51
negative; prevalence 0.7875) and an independent held-out test cohort of
**n = 120** drawn with a **distinct seed `20261029 = seed + 1`** (89 positive /
31 negative; prevalence 0.7417). The held-out rows are never used for fitting,
calibration, model selection or threshold choice; a test asserts the two
validated feature matrices are not identical. The held-out cohort is
independent in rows but drawn from the **same generative process**, so it is
not external validation on a real or independent population.

`validate_uci412_synthetic_cohort` enforces, fail-closed and in order:

1. **strict synthetic Track A context via `_assert_synthetic_track_a_context`
   (the corrected gate).** Every record is individually checked *before* the
   shared panel validator runs. A record that is not a mapping raises
   `malformed_payload`; a record with **no `context` block raises
   `missing_input_context`** (the block is mandatory and is never defaulted to
   an empty mapping — this is the exact fail-open path the review identified);
   a non-mapping `context` raises `malformed_context`. The record's own
   `synthetic` flag and `context.track` / `context.source` / optional
   `context.real_data` are then normalised **without coercion or defaults** and
   the boolean/value admission decision is delegated to the AI-7 route policy
   `_validate_synthetic_input_context` (operation
   `END_TO_END_EXERCISE`). Any returned code — `track_not_a`,
   `unsupported_input_source`, `synthetic_declaration_missing_or_false`,
   `real_data_input_context_rejected` — raises
   `Uci412ResearchGovernanceError` with the local code
   `uci412_synthetic_context_rejected`, the shared code(s) carried in the
   message. This deliberately reuses one security policy rather than
   maintaining a second, subtly different one.
2. exact panel identity (foreign panel ids `da_a2_resting_v1`,
   `da_a2_resting_labs_v1`, `da_a1_clinical_core_labs_v1`, and any UCI-45
   envelope, rejected before the shared validator runs; no crosswalk);
3. the shared strict panel contract (field order, registered categorical
   encodings, numeric plausibility/units, explicit missingness, anti-leakage
   and anti-wearable rules) and a 16-feature width check.

The strict gate's exact admission contract is: `synthetic` must be the boolean
`true` (missing, `false`, and non-boolean `1/0/"true"/"false"/None/2` are
rejected); `context.track` must be the string `"A"` (missing, non-string and
any other track rejected); `context.source` must be the string
`"structured_synthetic_research"` (missing and any other source rejected);
`context.real_data`, **when present**, must be the boolean `false` — an absent
or explicit `null` `real_data` means "not declared" and is accepted, while
`true` and any non-boolean value are rejected. A contradictory
`synthetic=false` with a real context, and `real_data=true` under a synthetic
envelope, are both rejected.

Rejected before any model work: records with missing/malformed context,
non-synthetic records, Track B, OCR, wearable, simulated/patient wearable,
patient monitoring, patient upload, clinician records, real-data/real-patient
claims, unknown sources, empty cohorts, malformed records, label-length
mismatch and non-binary labels. There is no path by which a UCI-45/Cleveland
record can enter this pipeline. The 27 new strict-context regression cases
(§10) include explicit tests that a missing `context`, missing `track` and
missing `source` each fail closed, and that the rejection reuses the AI-7
policy codes.

## 4. Methods — preprocessing, nested CV, calibration and negative control

* **Fold-contained preprocessing.** All imputation/encoding is fit inside each
  training fold via the shared `FoldSafeClinicalPreprocessor`
  (`preprocessing_contract = fold_contained_json_lineage_v1`); there is no
  global imputation or value repair, and model and preprocessing versions are
  bound together.
* **Nested cross-validation model selection.** Default budget: 4 outer × 3
  inner folds over the registered candidate families
  (`constrained_random_forest`, `l2_logistic_regression`,
  `prevalence_dummy`). The deterministic default run selected
  **`constrained_random_forest`** with `max_depth=2`, `min_samples_leaf=5`.
* **Cross-fitted calibration.** Out-of-fold logistic calibration on the
  clipped-logit link of the raw probability, with one calibrator per outer
  fold. Default run: intercept **−0.86559**, slope **1.71502**, 4 cross-fitted
  per-fold calibrators, `n_oof_samples = 240`, development prevalence 0.7875.
* **Label-shuffle negative control.** Permutation seed `20261101`; permuted
  selected-procedure AUROC **0.4940**, below the leakage ceiling **0.68**; no
  alarm. A permuted AUROC at or above the ceiling raises a blocking
  `CohortGovernanceError` and discards the run.
* **Descriptive fold dispersion.** Per-instance outer-fold score spread is
  reported as descriptive split sensitivity, explicitly **not** validated
  patient-specific uncertainty (`uncertainty_semantics =
  DESCRIPTIVE_OUTER_FOLD_DISPERSION_NOT_VALIDATED_UNCERTAINTY`;
  `validated_patient_specific_interval = false`).

## 5. Deliverable D — machine-readable 16-field input contract

`uci412_basic_clinical_field_contract.v0.1.json` is a versioned, explicitly
**`PROPOSED_NOT_APPROVED`** technical handoff for future backend/OCR/mobile
intake; it is not an approved clinical intake schema and authorizes no
auto-population. Its companion `uci412_field_contract.py` is **stdlib-only**,
performs no I/O beyond reading its own contract, contains **no scoring,
inference or prediction path**, and returns a metadata-only review whose
result state is always `NO_RESULT_NO_CAD_PROBABILITY_COMPUTED`
(`cad_probability_computed = false`).

The frozen in-code allowlists duplicate the JSON rules; `load_field_contract`
fails closed (`FieldContractIntegrityError`) if the two disagree, and the test
suite proves every rule matches both the registered panel and dictionary 1.1.0.
Each of the 16 fields carries a full four-channel acquisition matrix
(`structured_history`, `clinician_assessment`, `measurement`,
`laboratory_document`) over the statuses
`VERIFIED_REGISTERED_SOURCE_DOMAIN` /
`PROPOSED_FUTURE_ACQUISITION_CHANNEL` / `NOT_APPLICABLE`, with exactly one
verified channel matching the frozen source domain (BMI/BP/PR → measurement;
all others → structured history). OCR, wearable, Track B and real-patient
sources are prohibited tokens; `?`, `-9`, `-9.0` are rejected as wrong-source
markers; all 16 fields are required (no optional/missing-reason payload); no
silent unit conversion is performed. A PROPOSED future channel is accepted but
surfaced in `proposed_only_fields` (e.g. BMI via a future structured-history
route), never hidden or treated as verified.

## 6. Deliverable C — evaluation results, separated by prediction origin

The four populations are kept in distinct, **never-merged** blocks. Every block
carries `evidence_marker = SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE` and
`clinical_evidence = false`. Numbers below are from one deterministic
**default-budget** run with bundling enabled (`Uci412ResearchModelConfig()`
defaults, `package_bundle=True`); its machine-readable report SHA-256 is
`99bd76f2b7604f793e93fd80f031ee010ce94c9b277f4f1c23339a52e8119688`. Identical
configurations reproduce the hash byte-for-byte (the only difference a
`package_bundle=False` run makes is omitting the bundle/offline sections, which
yields a different hash but identical metric values), and local filesystem
paths are excluded from the hash.

| Origin (population) | AUROC | Avg. precision | Brier | Log loss | ECE-10 |
|---|---|---|---|---|---|
| Development OOF, **uncalibrated** nested CV | 0.6562 | 0.8672 | 0.1584 | — | — |
| Development OOF, **cross-fitted calibrated** nested CV | 0.6727 | 0.8780 | 0.1567 | 0.4868 | 0.0509 |
| Apparent final-calibrator diagnostic | reported in machine-readable block; explicitly **not unbiased** | — | — | — | — |
| **Held-out independent synthetic test, frozen model** | **0.5498** | 0.7785 | 0.2014 | 0.6020 | 0.0939 |

Held-out discrimination is **weak**: AUROC 0.5498 with a stratified percentile
bootstrap 95% CI of **[0.4411, 0.6698] that includes 0.5**, exploratory
0.5-threshold accuracy 0.7083. This is reported without embellishment. On a
small synthetic sample from a generative process with deliberately modest
signal, near-chance held-out discrimination is expected and is precisely why
these figures are software/generalization mechanics rather than clinical
evidence. Descriptive held-out Cox diagnostics (not used for recalibration or
threshold selection): calibration intercept 0.7688, calibration slope 0.2104.
The prevalence-shift diagnostic (development 0.7875 → test 0.7417, absolute
difference −0.0458) explicitly records
`external_recalibration_applied_to_primary_metrics = false`; the exploratory
0.5 cutoff is flagged `threshold_clinically_approved = false`.

The two development blocks also encode the exclusion guarantees: the
uncalibrated block excludes each observation from its model fit; the
cross-fitted calibrated block additionally excludes each observation from its
calibrator fit (`each_observation_excluded_from_calibrator_fit = true`).
**No cross-source (e.g. Cleveland vs UCI-412) metric comparison exists in the
report**; a test asserts the metrics section contains no such reference.

## 7. Explainability — SHAP additivity and LIME fidelity/stability

* **SHAP.** For the selected random-forest family the explainer is Exact
  Interventional TreeSHAP on the **raw model score / raw probability scale**
  (16 attributions; 48-sample synthetic background). The additivity sum-check
  passes with maximum absolute discrepancy **3.33×10⁻¹⁶**. Because post-hoc
  logistic calibration cannot be additively decomposed in probability units,
  the report states truthfully `additive_on_calibrated_probability = false`
  and `explains_calibrated_score_directly = false`; raw-probability TreeSHAP is
  never relabelled as calibrated-probability SHAP.
* **LIME.** 320 perturbations with stability assessed over the three registered
  default seeds. Verdict `ACCEPTABLE_LOCAL_APPROXIMATION`,
  `is_reliable_for_interpretation = true`, weighted R² **0.9877**, hold-out
  weighted R² **0.9838**, local fidelity absolute/relative error **0.00224**.
  A non-acceptable verdict would be reported diagnostically rather than failing
  the pipeline, with SHAP remaining the authoritative attribution. All
  backgrounds are synthetic; no patient-derived background exists.

## 8. Deliverable B — research bundle, attestation and fail-closed load

The optional packaging path writes, entirely under a private temporary root:
six authenticated artifacts (`model.joblib`, `preprocessing.json`,
`calibration.json`, `shap_background.json`, `evaluation_summary.json`,
`protocol.md`). Packaging → HMAC trusted-local verification → authenticated
`ResearchCadPredictor` load → offline `predict_research_only` all reuse the
existing reviewed machinery. Hard, test-asserted bindings:

* `serving_eligibility = RESEARCH_ONLY`, `approved_for_serving = false`,
  `clinical_use_authorized = false`, `manifest_pooled_cohorts = false`;
* manifest panel id `da_a1_basic_clinical_v1` with panel contract SHA-256 equal
  to the live panel, 16 ordered feature names, target
  `t1.uci412.angiographic_cad_ge50.v1` and execution profile `AI1_GENERIC_V1`;
* `producer_authenticated = true`, `safe_for_pickle_deserialization = true`.

Fail-closed behaviour is verified before `joblib.load`: a wrong signing key
raises `BundleIntegrityError` (`untrusted_bundle_producer_signature`), a bundle
outside the trusted root raises (`untrusted_bundle_location`), and mutating an
authenticated artifact raises an integrity error. The source-specific loader
re-asserts the panel binding and the RESEARCH_ONLY invariant via the trusted
descriptor. An example offline prediction on a held-out row: raw 0.7313,
calibrated research score 0.7009, calibrated log-odds 0.8515, SHAP sum-check
passing — interpreted as `RESEARCH_ONLY_NOT_INDIVIDUAL_CLINICAL_RISK`, never an
individual clinical probability.

## 9. Executable end-to-end demo (review Blocker B)

A single, documented command now runs the entire source-specific synthetic path
as an observable demonstration. It adds **no new estimator, calibrator,
explainer or security policy** — it is a thin orchestrator over the reviewed
AI-8 pipeline (`ai/uci412_demo.py`) wired into the existing `ai` CLI
(`ai/cli.py`); the module never imports `shap`, `lime` or `joblib` directly (an
AST boundary test enforces this).

**Exact command (default JSON, fast smoke budget):**

```
python -m ai uci412-demo
```

Variants: `--budget full` (the default nested-CV budget, n=240/120, 4×3 folds),
`--format text` (human console report), `--work-dir DIR` (retain the generated
private artifacts instead of using an auto-deleted temporary directory). An
invalid budget fails closed with argparse exit code 2. The complete
Windows-PowerShell and bash environment, input/output examples, artifact paths
and reproduction steps are in
[`ai8_uci412_research_demo_runbook.md`](ai8_uci412_research_demo_runbook.md).

The run reports **12 ordered stages, each individually PASSED/FAILED, followed
by a compact stage-success summary** (the summary is a distinct payload object,
not a numbered stage). Together they cover every required demonstration
element:

| # | Stage | What is observed |
|---|---|---|
| 1 | `1_synthetic_cohort_generation` | deterministic dev/test synthetic cohorts, distinct seeds, evidence marker |
| 2 | `2_route_and_panel_binding` | route id, exact 16-feature panel, ordered names, panel contract SHA-256 |
| 3 | `3_feature_contract_validation` | intake field-contract review (`NO_RESULT_NO_CAD_PROBABILITY_COMPUTED`) and panel matrix `[n,16]` |
| 4 | `4_research_model_identity` | model id/version, selected family, execution profile, preprocessing contract |
| 5 | `5_raw_model_score` | raw model score and the scale SHAP actually explains |
| 6 | `6_calibrated_research_score` | calibrated score + calibrated log-odds + `RESEARCH_ONLY` interpretation; no clinically approved threshold |
| 7 | `7_prediction_provenance_and_target` | target id/definition hash, ≥50% boundary, serving/clinical flags all false |
| 8 | `8_shap_explanation` | genuine model-based TreeSHAP, truthful `raw_model_probability` scale, sum-check, `additive_on_calibrated_probability=false` |
| 9 | `9_lime_explanation` | real LIME quality verdict, weighted R², hold-out R², local fidelity, stability |
| 10 | `10_bundle_verification` | authenticated RESEARCH_ONLY bundle, 6 verified files, `producer_authenticated=true`, `pooled_cohorts=false` |
| 11 | `11_invalid_input_rejection` | a **real** validator rejection (see below) |
| 12 | `12_held_out_synthetic_evidence` | origin-labelled held-out synthetic metrics, explicitly not external validation |
| — | `summary` | `stages_succeeded`/`stages_total`, succeeded-stage list, `stages_failed=0` |

**Genuine invalid-input rejection (not hardcoded).** Stage 11 builds an
otherwise-valid synthetic fixture, mutates it by **removing
`context.source`**, and calls the real `validate_uci412_synthetic_cohort`. The
strict guard raises `Uci412ResearchGovernanceError` with code
`uci412_synthetic_context_rejected` (shared token `unsupported_input_source`
carried in the message). The demo captures the live exception type/code/message;
if the validator ever *accepted* the malformed record, the demo itself raises
`demo_invalid_input_was_not_rejected`. The rejection payload contains no
`cad_probability` key — no result is produced for rejected intake.

**Banners and truthful labelling.** Every payload carries
`evidence_marker = SYNTHETIC_TEST_NOT_CLINICAL_EVIDENCE` and
`research_only_interpretation = RESEARCH_ONLY_NOT_INDIVIDUAL_CLINICAL_RISK`.
Synthetic outputs are never called patient risk or independent clinical
validation. Both banners also appear verbatim in the text renderer, which ends
with the explicit statement that the run is not clinical evidence and not an
individual patient's medical risk or external validation.

**Deterministic, machine-readable, path-free output.** The JSON payload is
serializable with `allow_nan=False`; it contains no absolute filesystem path,
no secret and no key material (a test greps for `/home/`, `/tmp/`,
`trusted_bundles` and `.key`). Both budgets are deterministic and reproduce a
fixed `report_deterministic_sha256`:

| Budget | n dev/held | report SHA-256 | raw | calibrated | held-out AUROC / AP / Brier |
|---|---|---|---|---|---|
| smoke | 120 / 60 | `6e5707bedb3c360aa605c8e0640fbeed7fe880c1c6bfc297187200a2f35656ec` | 0.755186 | 0.738384 | 0.606019 / 0.766513 / 0.221781 |
| full | 240 / 120 | `99bd76f2b7604f793e93fd80f031ee010ce94c9b277f4f1c23339a52e8119688` | 0.731299 | 0.700888 | 0.549837 / 0.778482 / 0.201389 |

The full-budget hash is identical to the §6 evaluation hash, proving the demo
executes the same deterministic pipeline rather than a parallel
reimplementation. Smoke-budget explanation checks on the same run: SHAP
max-abs sum discrepancy 1.11×10⁻¹⁶ over 16 attributions with
`additive_on_calibrated_probability=false`; LIME weighted R² 0.925898,
hold-out R² 0.907556, local-fidelity abs error 0.000335, verdict
`ACCEPTABLE_LOCAL_APPROXIMATION`. In retained mode (`--work-dir`) the private
HMAC key and seven bundle files are written only under the caller's directory;
the default mode creates and removes its own temporary directory and sets
`work_artifacts_retained=false`.

## 10. Verification — tests, determinism and CI

* **AI-8 test inventory (four files, 220 collected cases, all passing):**
  `tests/audit/test_uci412_field_contract.py` (44 functions → 116 parametrized
  cases, **stdlib-only so it runs in the dependency-minimal audit CI job with
  numpy/scikit-learn absent**),
  `tests/experiments/test_uci412_field_contract_panel_binding.py` (6 cases,
  live registered-panel hash/order/encoding cross-check that needs the ML
  stack),
  `tests/experiments/test_uci412_research_model.py` (now **79 cases** — was 52;
  the **27 new strict-context cases** described in §3, covering missing
  context/track/source, non-boolean `synthetic`/`real_data`, contradictory
  flags, non-mapping context and AI-7 policy-code reuse, each written to fail
  against the previous fail-open implementation), and the new
  `tests/experiments/test_uci412_demo.py` (**19 cases**): the 12-stage contract,
  panel SHA equality, serving/clinical flags false, raw-scale SHAP truthfulness,
  honest LIME verdict, the genuine rejection, the no-result-on-intake guarantee,
  cross-run hash reproducibility, no-path/no-secret leakage, work-dir retention,
  full-budget n=240/120, text markers, an AST import-boundary guard, subprocess
  JSON+text execution and bad-budget exit code 2. The earlier negative matrix
  (non-synthetic, Track B/OCR/wearable/patient-upload/real-patient sources,
  foreign panels, wrong order/encoding/unit/range, prohibited channels,
  empty/malformed payloads, bad labels, bundle wrong-key/untrusted-root/tamper,
  config validation) is unchanged and green.
* **Full repository:** **2339 passed, 2 skipped** (pre-existing
  platform-specific skips) under `python -m pytest -W error`; collection totals
  2341 — the prior 2293-passing baseline plus the 46 new cases (27
  strict-context + 19 demo). `git diff --check` is clean, pyflakes reports no
  unused imports or undefined names on every changed file, and no
  `.pkl/.joblib/.csv/.xlsx/.data` artifact is committed; all synthetic outputs
  are created only in private temp directories or a caller-supplied work dir.
* **Per-workflow scopes re-created locally under `-W error` (exact results):**
  audit job `tests/audit` → **546 passed**; contracts job `tests/contracts` →
  **249 passed**; backend job `tests/backend` → **581 passed**;
  experiment-runner job `tests/experiments tests/audit` → **1135 passed,
  2 skipped**; UCI-412 job `tests/uci412` → **374 passed**. `pip check`
  reports no broken requirements. With `numpy`/`scikit-learn`/`ai` blocked at
  import time, the stdlib-only audit field-contract suite still passes
  (116 cases), proving the dependency-isolated job does not silently need the ML
  stack.
* **Determinism:** two builds from identical configs in separate roots produce
  identical report SHA-256; the hash excludes timing fields and local paths, and
  the smoke/full demo hashes in §9 reproduce across processes.
* **CI (reported truthfully, never assumed):** no workflow file is added or
  modified, so the four existing pinned workflows (`audit-ci`, `backend-ci`,
  `contracts-ci`, `experiment-runner-ci`) pick up the new tests automatically;
  nothing requires elevated workflow permissions. The PR #66 human review
  attested **4/4 workflows green on the parent head `13430c7`**. The automation
  token available here receives **HTTP 403** on the check-runs/statuses API, so
  the remote status of the new correction commit cannot be independently polled
  from this environment; the per-scope results above are the local re-creation
  of every workflow's pytest invocation, and the authoritative remote result
  must be read directly on the PR. Budget for this milestone was **$0** using
  only free, pinned, offline tooling.

## 11. Status register, limitations and next steps

### 11.1 The three statuses are distinct and must not be collapsed

* **Engineering-complete on synthetic data — ESTABLISHED.** The source-specific
  UCI-412 synthetic route, the strict fail-closed input-context guard and the
  executable demo are implemented and verified by automated tests
  (§10). This is a software/correctness statement about deterministic synthetic
  fixtures only.
* **Research-scientifically evaluated on real data — NOT ESTABLISHED.** No real
  UCI-412 record has ever entered the pipeline; every metric in §6 is a property
  of a generative process, not of patients. This status can only be reached
  after human-authorized real-data work behind Gate PT P-3, with the reporting
  and sample-size discipline named below.
* **Clinically validated — NOT ESTABLISHED (and not currently permitted).** No
  individual clinical probability, clinical utility, net-benefit or
  external-validation claim is made or supportable; Gate P-5 is prohibited. The
  calibrated research score is explicitly
  `RESEARCH_ONLY_NOT_INDIVIDUAL_CLINICAL_RISK`.

### 11.2 Evidence and authorization register

**IMPLEMENTED and TESTED (synthetic only):** the 16-feature source-specific
pipeline; the corrected strict synthetic Track A context guard that delegates
its admission decision to the AI-7 route policy and fails closed on missing
context/track/source (27 new regression cases); fold-contained nested-CV
selection; cross-fitted OOF calibration; label-shuffle negative control;
independently seeded held-out synthetic evaluation with four origin-labelled
blocks; SHAP additivity and LIME fidelity/stability; the full RESEARCH_ONLY
bundle round-trip with authenticated fail-closed load; the versioned field
contract and its no-result validator; the AI-7 documentation corrections; the
executable `uci412-demo` command with console + JSON output and a genuine
invalid-input rejection (19 new tests); deterministic JSON-clean reporting.

**PROPOSED (not approved, no authorization granted):** the field contract
itself and every future application/OCR acquisition mapping; BMI via any
non-measurement channel; the human-authorization handoff for any future real
UCI-412 work (which would require the exact activation comment
`AUTHORIZE-M3A-UCI412-INTERNAL-RESEARCH`, a human merge and a git-ignored local
manifest — none of which exists).

**UNVERIFIED / deliberately not claimed:** every clinical performance claim;
per-field prediction-time availability; BP/PR units and measured quantity;
chest-pain semantics; the S-9 binary direction; external or cross-population
validity; any clinical utility or net benefit; real-bundle inference and
serving. Real UCI-412 fitting remains blocked by Gate PT P-3.

### 11.3 Limitations

Results characterize a deterministic synthetic software exercise, not patients;
held-out data share the development generative process; the small sample and
modest synthetic signal yield weak, near-chance held-out discrimination; the
0.5 threshold is exploratory; fold dispersion is descriptive, not validated
uncertainty; sample size versus model complexity for any future real study would
need a Riley et al. (2021) calculation before development. The demo does not
widen this execution scope — it exercises the same synthetic-only path and
cannot accept or score real patient input.

### 11.4 Alignment with the Master Completion Plan (v1.2)

The plan keeps engineering completion, research evaluation and clinical
validation separate and names AI-8's two P1 package blockers (the context-guard
bug and the missing runnable demo). Row-by-row status against its elements:

| Master-Plan element | Plan expectation | AI-8 status on this PR |
|---|---|---|
| Source-specific research route | AI-7 route resolution reused, no second framework; UCI-412 kept separate from Cleveland/UCI-411 | **IMPLEMENTED / TESTED (synthetic)** — binds the registered UCI-412 route via the shared machinery; Cleveland profile asserted absent; no pooling/crosswalk |
| 16-field input contract | P1 blocker: a pinned, versioned basic-clinical intake contract with fail-closed validation | **IMPLEMENTED as artifact, PROPOSED_NOT_APPROVED for intake** — v0.1 JSON + stdlib no-result validator; authorizes no auto-population |
| Calibration and evaluation | Fold-contained nested CV, cross-fitted calibration, origin-separated metrics, no leakage | **IMPLEMENTED / TESTED (synthetic)** — four never-merged blocks, OOF calibration, negative control; real-data evaluation **not started** |
| SHAP / LIME explainability | Truthful explained scale, additivity, real fidelity/quality verdict | **IMPLEMENTED / TESTED (synthetic)** — raw-scale TreeSHAP with `additive_on_calibrated_probability=false`; LIME verdict with measured fidelity/stability |
| Authenticated research bundle | RESEARCH_ONLY, producer-authenticated, fail-closed load, cannot enable serving | **IMPLEMENTED / TESTED** — HMAC trusted-local bundle, wrong-key/root/tamper rejected, serving/clinical flags hard-false |
| Runnable visible demo | §16 checklist: one documented reproducible command, negative case, labelled scores, SHAP+LIME scale/quality, bundle integrity, no real data/keys | **IMPLEMENTED / TESTED** — `python -m ai uci412-demo`, 12 stages + summary, genuine rejection, JSON+text, runbook (the plan's P1 demo blocker) |
| Real UCI-412 model | A model fit on authorized real UCI-412 data | **NOT STARTED — BLOCKED by Gate PT P-3**; no real data in the repo; remains the plan's gated next milestone |
| Clinical probability / validation | Clinically valid individual risk; external validation; P-5 | **NOT ESTABLISHED / PROHIBITED** — research scores are never individual clinical risk; no external validation (UCI-411 is the same 303 participants) |

### 11.5 Smallest useful next real-data milestone (no broad synthetic-only work)

The smallest step that produces genuinely new *research* evidence — rather than
more synthetic machinery — is a **human-authorized, single-cohort real UCI-412
feasibility reproduction that reuses the frozen pipeline unchanged**:

1. a human issues the exact activation comment
   `AUTHORIZE-M3A-UCI412-INTERNAL-RESEARCH`, merges the authorization and
   supplies a git-ignored local data manifest (none exists today), with the real
   dataset kept out of version control and no PHI or key committed;
2. the existing, already-reviewed pipeline is run **without code changes** on the
   real 303-record basic-clinical panel to verify the 16-field contract parses
   the real source with no silent unit/encoding coercion (resolving the S-1–S-9/
   U-6 register against the actual files);
3. it emits the first **origin-labelled real-data metrics block** under the same
   fold-containment and cross-fitted calibration rules, alongside a pre-specified
   Riley et al. (2021) sample-size adequacy check for the candidate complexity.

This is deliberately *not* external validation (UCI-411 is the same
participants), not model serving and not clinical validation; it cannot be
started without the human authorization and a compliant data-handling path.
Other gated, not-started steps remain: human review of the field contract and
the unresolved register; a TRIPOD+AI (BMJ 2024;385:e078378) / PROBAST+AI
(BMJ 2025;388:e082505) reporting pack for any real-data study; a separately
authorized external-validation plan; only then any consideration of
clinical-readiness work (P-5, currently prohibited).

### References (standards and in-repository record only; no results fabricated)

1. 2024 ESC Guidelines for the management of chronic coronary syndromes. *Eur Heart J* 2024;45:3415–3512.
2. Collins GS, et al. TRIPOD+AI statement. *BMJ* 2024;385:e078378. doi:10.1136/bmj-2023-078378.
3. Moons KGM, et al. PROBAST+AI. *BMJ* 2025;388:e082505. doi:10.1136/bmj-2024-082505.
4. Riley RD, et al. Calculating sample size for prediction model development. *Stat Med* 2021;40:4230–4251.
5. UCI Machine Learning Repository, Z-Alizadeh Sani (id 412), doi:10.24432/C5Q31T, CC-BY-4.0 — repository landing-page metadata only; no dataset file is read by this work.
6. Tao et al. 2025, *Rev Cardiovasc Med* 26(3):26204, doi:10.31083/RCM26204 (secondary source for the 0/1 direction; not an owner codebook).
