# AI-8 — Source-Specific UCI-412 Standalone Research Model (Synthetic Only)

**Status:** technical report for the open, non-merged implementation PR
[#66](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/66) on branch
`arena/01367b08-cardioassist-ai`.
**Baseline `main` SHA:** `6ecc191800c2f505b80f97bb8261b2ed3cb36af7`.
**Implementation commit SHA:** `e8c0cc499c3c296579d790c15837a2825ecb9da6`.
**Classification:** engineering artifact + scientific record. **Synthetic
fixtures only — nothing in this document is clinical evidence or a performance
claim about patients.** Gate PT P-3 remains **CLOSED**, P-1 **PENDING**, P-5
**NOT MADE (prohibited)**. Do not self-approve or merge this PR.

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

1. synthetic Track A context (`synthetic is True`, `track == "A"`,
   `source == "structured_synthetic_research"`);
2. exact panel identity (foreign panel ids `da_a2_resting_v1`,
   `da_a2_resting_labs_v1`, `da_a1_clinical_core_labs_v1` rejected; no
   crosswalk);
3. the shared strict panel contract (field order, registered categorical
   encodings, numeric plausibility/units, explicit missingness, anti-leakage
   and anti-wearable rules) and a 16-feature width check.

Rejected before any model work: non-synthetic records, Track B, OCR, wearable,
simulated/patient wearable, patient monitoring, patient upload, clinician
records, real-data/real-patient claims, unknown sources, empty cohorts,
malformed records/context, label-length mismatch and non-binary labels. There
is no path by which a UCI-45/Cleveland record can enter this pipeline.

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

## 9. Verification — tests, determinism and CI

* **New tests:** `tests/audit/test_uci412_field_contract.py` (44 functions →
  116 parametrized cases) and
  `tests/experiments/test_uci412_research_model.py` (42 functions → 52 cases):
  **86 new test functions / 168 collected cases**, including the required
  negative matrix — non-synthetic, Track B/OCR/wearable/patient-upload/
  real-patient sources, foreign panels and sources, wrong order/encoding/unit/
  range, prohibited acquisition channels, empty/malformed payloads, bad labels,
  plus bundle wrong-key/untrusted-root/tamper and config validation.
* **Full repository:** **2287 passed, 2 skipped** (pre-existing
  platform-specific skips) under `python -m pytest -W error`; collection totals
  2289. `git diff --check` is clean and no `.pkl/.joblib/.csv/.xlsx/.data`
  artifact is committed; all synthetic outputs are created only in private temp
  directories.
* **Determinism:** two builds from identical configs in separate roots produce
  identical report SHA-256; the hash excludes timing fields and local paths.
* **CI:** no workflow file is added or modified, so the four existing pinned
  workflows (`audit-ci`, `backend-ci`, `contracts-ci`,
  `experiment-runner-ci`) pick up the new tests automatically; nothing requires
  elevated workflow permissions. Budget for this milestone was **$0** using only
  free, pinned, offline tooling.

## 10. Status register, limitations and next steps

**IMPLEMENTED and TESTED (synthetic only):** the 16-feature source-specific
pipeline; fold-contained nested-CV selection; cross-fitted OOF calibration;
label-shuffle negative control; independently seeded held-out synthetic
evaluation with four origin-labelled blocks; SHAP additivity and LIME
fidelity/stability; the full RESEARCH_ONLY bundle round-trip with authenticated
fail-closed load; the versioned field contract and its no-result validator; the
AI-7 documentation corrections; deterministic JSON-clean reporting.

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

**Limitations.** Results characterize a deterministic synthetic software
exercise, not patients; held-out data share the development generative process;
the small sample and modest synthetic signal yield weak, near-chance held-out
discrimination; the 0.5 threshold is exploratory; fold dispersion is
descriptive, not validated uncertainty; sample size versus model complexity for
any future real study would need a Riley et al. (2021) calculation before
development.

**Next steps (each gated, none started):** human review of the field contract
and the unresolved register; a TRIPOD+AI (BMJ 2024;385:e078378) / PROBAST+AI
(BMJ 2025;388:e082505) reporting pack if a real-data study is proposed; a
separately authorized external-validation plan; only then any consideration of
clinical-readiness work (P-5, currently prohibited).

### References (standards and in-repository record only; no results fabricated)

1. 2024 ESC Guidelines for the management of chronic coronary syndromes. *Eur Heart J* 2024;45:3415–3512.
2. Collins GS, et al. TRIPOD+AI statement. *BMJ* 2024;385:e078378. doi:10.1136/bmj-2023-078378.
3. Moons KGM, et al. PROBAST+AI. *BMJ* 2025;388:e082505. doi:10.1136/bmj-2024-082505.
4. Riley RD, et al. Calculating sample size for prediction model development. *Stat Med* 2021;40:4230–4251.
5. UCI Machine Learning Repository, Z-Alizadeh Sani (id 412), doi:10.24432/C5Q31T, CC-BY-4.0 — repository landing-page metadata only; no dataset file is read by this work.
6. Tao et al. 2025, *Rev Cardiovasc Med* 26(3):26204, doi:10.31083/RCM26204 (secondary source for the 0/1 direction; not an owner codebook).
