# 15 — CardioAssist AI: Model Development & Evaluation Protocol, Pre-registration Draft

**Protocol ID:** CAI-T1-PRETRAIN-V0.1
**Prepared:** 2026-10-22
**Version:** DRAFT; not frozen and not approved
**Allowed activities now:** literature review, manuscript/protocol design, documentation, synthetic tests, and D-046-authorized read-only descriptive audits
**Forbidden now:** fitting/feature selection/tuning/validation/evaluation/calibration/SHAP/LIME on real patient data. Gate PT P-3 stays **CLOSED**. `D-046-EP` is proposed, **not approved**.

**Evidence hierarchy:** local maintainer-reported *aggregate-only* UCI audit observations (not independent third-party replication); public dataset source documentation; independent methods research; team design choices marked **PROPOSED**. Dataset auditing is not medical validation.

## Executive scientific decision and why

**R-MD-01 — Proposed primary experiment:** **develop a leakage-restricted, pre-angiography CAD-presence classification benchmark using only processed Cleveland**, in a source-specific diagnostic population. Do **not** simultaneously concatenate Cleveland, other UCI-45 sites, UCI-412 and UCI-411. The first purpose is an interpretable and reproducible **internal prediction-model development/evaluation experiment**, **not** a validated medical service or calibrated 30-day risk predictor.

**R-MD-02 — Proposed primary intake schema:** use the fixed **resting-assessment, five-raw-field panel** `age, sex, cp, trestbps, restecg` as a **pre-specified candidate model-input set**, contingent on clinical measurement-time agreement. This was chosen prospectively from leakage/availability and workflow considerations, **not from model outcomes or data-driven feature ranking**. No model is trained; the input choice still requires Gate PT clinical protocol freeze. Caveat: five raw field names may encode more than five parameters after one-hot encoding; n=303 does **not** automatically establish adequate statistical sample size or predictive accuracy.

**R-MD-03 — Secondary scoped experiments**, not additions to primary sample:
- Within Cleveland, **pre-specified lab-augmented** panel `age,sex,cp,trestbps,restecg,chol,fbs` only if laboratory results precede the decision moment; compare as a secondary exploratory complexity/availability trade-off. An exercise-stage 11-feature panel is an optional *separately registered exploratory* scenario only when actual testing is already available; it must not be forced on patients for ML.
- **UCI-412 Z-Alizadeh Sani** is a **separate 303-patient source-specific development/replication question**, with `Cath` as prospective diagnostic outcome and a separately justified input dictionary. Do not automatically map its 55 workbook predictor columns to UCI-45 names, select from them by trial-and-error, or count UCI-411 extension as 303 new records.
- **Hungary, VA, Switzerland** are **candidate site-shift tests** of an *unchanged, locked* Cleveland-source model only after label compatibility, predictor code/unit definitions, site differences, and patient independence pass explicit pre-registration checks. Hungary contains a historically binarized processed target and 293/294 order-independent Raw/Processed predictor-plus-binary profile overlap; **that observation does not establish a common cross-site target**. Switzerland has only 8 source-target-negative records; a conventional discrimination claim may be very imprecise, so a descriptive evaluation or NO-GO is an acceptable scientific outcome.
- **Statlog UCI-145** is **not authorized for acquisition** under current D-046 and may overlap with Cleveland. It is not an independent cohort and is excluded until new scoped authorization and identity/provenance verification.
- **No pooled development, patient-count summation or independent-external-validation claim now**. Pooling is a conditional future amendment after site/target harmonization, overlap and transportability are evidenced. We report negative as well as positive findings.

The protocol compares **source-specific current angiography-defined CAD presence**, not future cardiac events. UCI-45 codes 0 versus 1–4; UCI-412 defines CAD with diameter narrowing **>=50%** and the historical UCI-45 dictionary describes **<50%** versus **>50%**. Existence and coding of exactly-50% cases are not established. Thus H-01 remains OPEN; no cross-dataset outcome harmonization can be assumed.

## Real audit facts influencing feasibility (local aggregate evidence; NOT model results)

| Source | n | Source outcome: no CAD / CAD | Jointly complete history | Jointly complete resting 5-field panel | Jointly complete 7-field labs panel, zero-unavailable scenario | Consequence |
|---|---:|---:|---:|---:|---:|---|
| Cleveland processed | 303 | 164 / 139 | 303 | **303** | **303** | Suitable for investigating candidate resting/lab predictor *availability*, not proven predictive utility |
| Hungary processed | 294 | 188 / 106 (processed binary) | 294 | **292** | **261** | Candidate site evaluation only if label/codings/timepoint pass |
| Switzerland processed | 123 | 8 / 115 | 123 | **120** | **0** | Resting panel available; labs unusable as measured cholesterol when source zero means unavailable; only 8 negatives severely limit stable evaluation |
| VA Long Beach processed | 200 | 51 / 149 | 200 | **143** | **100** | Site shift and measurement availability differences; alternative lab/exercise paths not guaranteed |
| UCI-412 | 303 | 87 / 216 | **NOT MEASURED in comparable panels** | **NOT MEASURED in comparable panels** | **NOT MEASURED** | Different feature source and population; do not manufacture harmonization from this table |

Source-form coding findings: Switzerland has **123/123 cholesterol zeros** and VA **49/200**; an independent four-site dataset reference interprets these as unmeasured, consistent with the original source frequencies, but official UCI heart-disease.names does not itself specify zero as a universal missing code. VA also has one zero resting BP; oldpeak-negative values in Swiss/VA require a clinical coding explanation. Record all such values **unchanged** in protected originals. The descriptive audit's alternative rules **never cleaned actual data**.

UCI-412's local workbook has **55 predictor columns + Cath**, not the UCI landing page's 54-feature description; review exact source dictionary/timepoint before any 412-derived input plan. UCI-411 shares **303/303** recorded rows on common fields, with one unresolved artery-vs-Cath consistency flag; this blocks naïve augmentation or relabeling, not source preservation.

## Prospective clinical prediction contract (for review, not an API change)

- **Intended users:** treating clinicians reviewing adult patients who are already being considered for coronary angiography in the represented referral settings. **Not** general-population screening, patient self-diagnosis, emergency triage, or 30-day event forecasting.
- **Decision time (working proposal):** after history, symptom assessment, resting BP and ECG **and before coronary angiography**. Record whether diagnostics were obtained before that moment. If time-order cannot be established for source features, explicitly mark model use applicability as uncertain.
- **Target:** *binary source-referenced angiographic CAD presence* in each named dataset. Keep local source labels/threshold definitions distinct until H-01 is resolved. `num>0` maps only the UCI-45 *presence-vs-absence* target; never infer ordered severity from 1–4.
- **Model inputs:** history/resting 5-field panel, no `ca`, raw vessel stenosis, `Cath`, patient ID, angiographic or post-outcome variables, or wearable/monitoring observations. Lab/exercise fields only in a separately frozen measurement-time-qualified scenario. Never treat `thal` as a routine-history field.
- **Output semantics:** benchmark-developed score with complete provenance, intended setting and validation status. If clinically interpretable calibration is not demonstrated on an appropriate population, **do not display percentage personal CAD risk**. No autonomous treatment recommendations; clinician review is required. Current `/v1/predictions/cad-tabular` remains MOCK_SYNTHETIC and separate from any future approved model.
- **UI direction:** stage-aware form may collect available data, but the existence of a form stage does **not** imply an approved prediction model for it. Wearable Track B must remain separated from CAD prediction Track A.

## Sample-size, selection and missingness policy to freeze before training

1. **Statistical adequacy is a blocker to calculate, not guess.** Use Riley et al. BMJ 2020 predictor-model sample-size framework, with n, both event/non-event counts, candidate predictor **parameters** including categorical expansions, expected model fit/shrinkage, and desired precision. The old rule of ten events/parameter is **not** sufficient justification. Document the calculation and decision before executing any model.
2. **One patient/source observation in one cohort only:** source-version correspondence does not create extra people; investigate any exact or near duplicates with privacy controls. No near-duplicate auto-removal without reliable attribution, and no unrelated sites presumed independent by name alone. If patient identifiers are unavailable, report independence as an explicit uncertainty.
3. **Source labels:** UCI-45 zero vs 1–4; UCI-412 `Cad` vs `Normal` in memory only. Source originals remain preserved. Do not repair the one UCI-411 `Cath` discrepancy or any raw-versus-processed mismatch automatically.
4. **Handling missing values (planned, not executed):** source `?` / `-9` are documented missing markers according to format. Treat Swiss/VA nonpositive cholesterol or resting BP in *a separate proposed analysis policy* as unavailable, not literal medical measurements; retain raw values and versioned coding rationale. Keep valid categorical zero and valid `oldpeak=0`. Negative oldpeak remains flagged pending source/clinical interpretation; no clipping or inferred measurement. Pre-specify an alternate interpretation sensitivity analysis where justified, never silently discard records.
5. **Pipeline inside each training fold only:** numerical imputation (e.g., median), categorical imputation (e.g., most frequent or explicit missing category), categorical one-hot encoding with unknown handling, and scale numerical features for penalized linear models. Learn every imputation/encoding/scaling parameter from that fold's training subset **only**. Same frozen mapping applies to validation/evaluation. No full-data feature ranking, whole-dataset imputing, SMOTE before folds, or hidden resampling. With n around 303, avoid automatically adopting SMOTE; justify any later class weighting through frozen sensitivity/decision rules.
6. **Candidate-set integrity:** clinical predictor panel is pre-declared on availability and measurement timing. No searching many field combinations and subsequently calling the best result an unbiased confirmatory finding. If adjusted after examining validation metrics, date a protocol amendment, retrain/evaluate under correctly nested or fresh validation, and disclose the exploration.

## Candidate models — limited and intentionally interpretable

| Role | Candidate | Reason | Training status |
|---|---|---|---|
| Negative-control reference | Constant source-prevalence score from training fold only | Detects lack of discrimination and contextualizes AUPRC prevalence | PROPOSED / NOT FIT |
| Primary transparent baseline | Penalized logistic regression, L2 regularization | Robust small-tabular-data starting point and clinically readable coefficients after one-hot/scale | PROPOSED / NOT FIT |
| Nonlinear comparator | Random forest with constrained tree depth/minimum leaf size | Tests nonlinear interactions without deep neural architecture; bounded search and overfitting scrutiny | PROPOSED / NOT FIT |
| Optional sensitivity | Gradient boosting only if protocol's information budget and computational/reproducibility constraints justify it | Limited, logged extra complexity, not an unbounded model contest | DEFERRED |

No deep-learning benchmark as primary on n≈303 without a justified sample-size and model-complexity rationale. The most attractive AUROC alone is **not** sufficient for selection or deployment.

## Internal / external evaluation: pre-registration plan, all UNEXECUTED

### Internal Cleveland development
- **Proposed** nested stratified 5-fold outer / 5-fold inner CV with **four pre-registered repeat seeds** (consistent with the existing Gate PT outline), contingent on the Riley-style sample-size feasibility assessment and positive/negative events per fold. The inner folds tune the *bounded* model/preprocessing hyperparameters; outer predictions estimate internal development performance. Do not label any outer-fold metric as independent external validation.
- Compare **training-fold prevalence**, penalized logistic regression and a constrained random forest with the **same** eligible predictor panel, evaluation budget and leakage-protected pipelines. Keep one champion selection rule pre-registered (primary discrimination plus calibration and simplicity tie-break; details to be frozen), never choose after inspecting external-site metrics.
- **Overfitting / instability checks:** a pre-registered label-permutation null control and sensitivity to repeat seeds; small sample and class imbalance can cause noisy estimates. A label-shuffle run is a diagnostic, not proof that all leakage has been eliminated.
- **No naïve held-out 20% Cleveland test simply for aesthetics:** small development n≈303 makes a 60-person final test unstable. Prefer resampling for internal evidence; use a genuinely independent source for external evaluation **only after** eligibility/label/overlap approval.
- Freeze a locked-model training recipe *after* internal model selection under protocol, and score each eligible external cohort **once** without adapting preprocessing, thresholds, model choice or calibrator on it. If only some external cohorts qualify, name exactly which and describe the others as **NOT VALIDATED**.

### Site / dataset evaluation, conditional gates (no training currently)
- **Hungary:** candidate holdout-like external site when five resting fields have comparable measurement meaning, confirmed source target, and patient independence. Its 292/294 resting-panel completeness is not a validation guarantee; any missing values in evaluation use the training-fitted preprocessing.
- **VA Long Beach:** candidate site with 143/200 resting-stage complete under BP-zero-unavailable scenario. Under frozen intended-use policy, decide whether missing-input cases are eligible for imputation or must abstain; report site coverage and shift. No validation label unless comparability and non-overlap pass.
- **Switzerland:** 120/123 resting complete but 8/123 target negatives. Formal ROC-AUC, calibration and specificity may be **extremely imprecise**; decide via an a priori evaluation-size feasibility analysis whether to treat it as descriptive stress-test only or explicitly NOT EVALUABLE. Do not hide it because scores look weak.
- **UCI-412:** distinct endpoint definition (>=50% vs historical UCI-45 >50%), different recorded feature schema, possible measurement/time availability issues. A separate development study or specifically scoped protocol is safer than claiming immediate external validation of a Cleveland model. No UCI-411 leakage as predictors.
- **Pooling and site-held-out training:** **NO-GO** until clinical H-01 compatibility, units/codings, source independence and overlap assessment meet a predefined rule; if later approved, use leave-one-site-out evaluation to avoid optimistic mixed-site random splits. Do not assert site performance represents broader population care.

### Reporting and model-selection evidence
- **Primary planned discrimination:** ROC-AUC, clearly identified as internal nested-CV or named eligible external-site evaluation. **Secondary:** AUPRC with actual sample prevalence, Brier score and calibration-in-the-large/intercept+slope where statistically estimable; sensitivity, specificity, PPV/NPV at a **pre-registered clinical operating point**; confusion matrix. Accuracy and F1 are context only, **never the sole decision criteria**. No decision threshold optimized on external data.
- **Uncertainty:** record each outer fold/repeat, model variance and uncertainty intervals from an appropriate participant-level resampling design. The 2,000-bootstrap suggestion from the existing Gate PT outline needs a **statistically valid estimator** (do not treat 20 repeated-CV predictions per patient as independent or bootstrap them as 20 independent persons). Pre-specify the actual CI method for each metric and whether event counts support calibration slope estimation; where not, report `not estimable` without fabricated curves or precise claims.
- **Calibration:** learn any calibrator on training-side held-out/cross-fitted predictions **separately** from evaluation; never calibrate on a held-out external cohort then call the same cohort independently validated. If calibration cannot be supported, return an `uncalibrated_score` (not "% CAD risk").
- **Subgroups:** by site, source sex and age range only if subgroup cases and outcomes suffice; with low cells (Switzerland has 8 target negatives), no inferential fairness/metric precision claims. Include source case-mix/referral biases and historical dataset age in all reports.
- **Explainability (after protocol and model fit only):** logistic terms or suitable real SHAP on an explicitly fixed explanation/output scale; TreeSHAP additivity tests where valid, stability checks across refits, truthful case-level disclaimers. LIME only if installed/tested and fidelity documented; current mock 503 LIME does not permit fabricated explanations.
- **Quality and reporting:** use TRIPOD+AI 2024 for transparent reporting and PROBAST+AI 2025 to assess development quality, evaluation bias and applicability. A passing documentation checklist cannot substitute for genuine clinical validation.

## Implementation work packages and acceptance criteria (zero-dollar, phased)

| Package | Action AFTER relevant approval | Evidence of completion |
|---|---|---|
| PP-01, NOW | Merge this **documentation-only protocol proposal** after review; protect raw files, report hashes and privacy | PR CI green, source links traceable, no real data/training |
| PP-02, NOW | Write *synthetic-only* tests for candidate numerical/categorical encodings, source unit mapping, unknown categories, missing-vs-zero handling and `ca`/Cath leakage rejection; maintain existing versioned mock backend contract | Deterministic tests pass Python 3.11/3.12; no real record access or HTTP behavior changes without own authorization |
| PP-03, NOW | Draft clinical predictor dictionary / measurement-time decisions and freeze the sample-size method and data-splitting rule **in a new reviewable amendment**, without computing fitting metrics | One named, reviewable P-1/P-3 submission with exact decision options and signed status |
| PP-04, AFTER P-3 | Create source-specific, locally derived versioned training view and guarded training job (never overwrite originals); run audited, pre-registered nested CV and negative controls | Per-fold logs, source hashes, model/preprocess IDs, CIs, reproducible run registry; no patient data pushed |
| PP-05, AFTER P-3 and cross-site eligibility | Controlled one-shot assessment on eligible external cohorts; do not modify locked model in response to external data | Per-site report, applicability notes, uncertainty, any NO-GO findings |
| PP-06, AFTER successful evaluation and required clinical wording reviews | Integrate *explicitly non-clinical / clinician-reviewed* research score into a separately approved versioned service/API | Independent acceptance tests, real-vs-mock distinction, model card, validation-status flag, no autonomous medical advice |

**No active production CAD predictor or cross-site clinical validity exists at this stage.** Reusing the existing mock's synthetic probabilities as real model outputs is prohibited. Patient mobile wearable monitoring is Track B, not a substitute for clinical predictor values.

## Consolidated decision packet — what truly needs supervisor/human protocol signoff

Our **recommendations** are explicit so the meeting asks for a protocol decision rather than open-ended problem-solving:

| Decision requested once at Gate PT | Our proposed default | What remains to verify |
|---|---|---|
| P-1 diagnostic research objective | Concurrent/source-referenced angiographic CAD presence; pre-Cath clinical information only | Agreement on target definition, care population and clinical prediction moment |
| P-1/H-01 across-source threshold | Keep UCI-45 and UCI-412 separate; treat >50 vs >=50 as **not proven equivalent** | Original case-definition evidence and exactly-50% boundary semantics; no pooling before resolution |
| L-01/L-06/L-07 predictor admissibility | Primary resting 5-field panel; `ca`/stenosis/Cath forbidden; labs/exercise secondary only if pre-moment measured | Clinician timing/source dictionary and actual entry units |
| QA-ZERO/missingness | Preserve originals; planned source-documented `?`/-9 missing; prospective secondary cholesterol/BP-zero-as-unavailable sensitivity | Supervisor acceptance of primary vs sensitivity mapping; no global imputation |
| Eligibility / source independence | Cleveland-only primary; 412 separately; Hungary/VA/Swiss conditional and site-count constrained | Source overlap, label coding, case mix, class balance and sample-size feasibility |
| Statistical protocol | Training-fold-only preprocessing, prevalence/penalized LR/constrained RF, nested CV, explicit uncertainty/calibration criteria | Detailed candidate parameterization, sample-size adequacy, approved calibration and CI estimator |
| Research quality and safety | TRIPOD+AI report, PROBAST+AI quality review, no unqualified CAD risk claims | Signed protocol P-3 and later clinical copy/integration approvals |

**Approval ledger:** Maintainer may approve documentation/design PRs per project governance; supervisor P-3 **NOT APPROVED**; D-046-EP **NOT APPROVED**; real model training/evaluation remains forbidden. A future clinical review may adopt, reject, or amend this protocol without any retrospective claim that work was already approved.

## Cited primary/methodology sources (verified against public sources)

1. UCI Heart Disease (four sites, historical data, 0 vs 1–4 target, field meanings), DOI [10.24432/C52P4X](https://doi.org/10.24432/C52P4X), https://archive.ics.uci.edu/dataset/45/heart+disease; official original `heart-disease.names` (missing marker and original threshold wording).
2. UCI Z-Alizadeh Sani (CAD >=50%, 303), DOI [10.24432/C5Q31T](https://doi.org/10.24432/C5Q31T), https://archive.ics.uci.edu/dataset/412/z+alizadeh+sani.
3. UCI-411 extension and linked local exact 303-row shared correspondence (maintainer audit only): https://archive.ics.uci.edu/dataset/411/extention+of+z+alizadeh+sani+dataset.
4. Datanovia/datarium `heartdisease` documentation (secondary) on 172 cholesterol zeros / four sites: https://rpkgs.datanovia.com/datarium/reference/heartdisease.html.
5. Collins et al. **TRIPOD+AI**, BMJ 2024, doi: https://doi.org/10.1136/bmj-2023-078378 — transparent model reporting checklist (not a quality approval).
6. Moons et al. **PROBAST+AI**, BMJ 2025, doi: https://doi.org/10.1136/bmj-2024-082505 — model development quality, evaluation risk of bias and applicability.
7. Riley et al., **Calculating the sample size required for developing a clinical prediction model**, BMJ 2020, doi: https://doi.org/10.1136/bmj.m441 — beyond the crude 10-events-per-parameter rule.
8. Scikit-learn, **Common pitfalls**: https://scikit-learn.org/stable/common_pitfalls.html — fold-contained pipelines / preventing data leakage.
9. Existing project Gate PT outline: [05_gate_pt_methodology_outline_NOT_APPROVED.md](05_gate_pt_methodology_outline_NOT_APPROVED.md), decision register [03_leakage_and_target_harmonization_register.md](03_leakage_and_target_harmonization_register.md), real aggregate evidence [10_m2a_uci412_uci411_evidence_and_decisions.md](10_m2a_uci412_uci411_evidence_and_decisions.md), and executed joint availability [14_real_joint_availability_and_staged_intake_decision.md](14_real_joint_availability_and_staged_intake_decision.md).

**Next step:** Human review and merge this proposal as a **protocol draft only**, then complete PP-02 synthetic engineering and the concise P-1/P-3 clinical protocol-review package. No additional routine supervisor requests for source audits or technical decisions.
