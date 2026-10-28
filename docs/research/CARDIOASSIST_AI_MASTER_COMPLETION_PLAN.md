# CardioAssist AI — Master AI Research & Engineering Completion Plan

**Document ID:** CAI-AI-MASTER-ROADMAP-2026-10-28-V1.3  
**Version:** 1.3 — workflow-reconciled roadmap with amended AI-8 PR #66 code/demo review and milestone tracking  
**Date:** 2026-10-28  
**Repository:** [Muhammed-Fathi/CardioAssist-AI](https://github.com/Muhammed-Fathi/CardioAssist-AI)  
**Suggested repository location:** `docs/research/CARDIOASSIST_AI_MASTER_COMPLETION_PLAN.md`  
**Owner:** Project maintainer and AI team  
**Status:** **TEAM WORKING EXECUTION PLAN / RESEARCH-ONLY; submitted through a reviewable documentation PR, not a clinical approval, authorization for new real-patient processing, or regulatory clearance.**

> **Purpose.** Deliver a technically reliable, medically defensible, reproducible, multi-source coronary artery disease (CAD) **research AI system** whose input acquisition is compatible with its actual validated features, whose output probabilities are calibrated and honestly scoped, whose explanations faithfully describe model behavior, and whose real-world limitations are explicit. Code completeness and high AUROC alone do not satisfy this goal.

---

## 0. Executive decision

This roadmap is the **working strategy for completing the AI workstream**. It supersedes neither ratified governance decisions nor frozen protocols and does not silently override existing source dictionaries, exact-version security controls, dataset restrictions, or clinical review gates.

**Key decisions**

1. **Build a multi-route system, not a single “highest-accuracy” model.** Each eligible cohort has a declared task; no naïve dataset pooling, feature crosswalks, or cross-source performance ranking.
2. **The clinical question precedes both dataset and model selection.** The intended output is *research estimation of the presence of angiography-referenced obstructive CAD*, **not** 30-day events, myocardial infarction, mortality, or a guaranteed diagnosis.
3. **Design clinical input acquisition and model feature eligibility together.** The approved model-specific feature contract drives future patient/clinician questions and OCR extraction; the model cannot claim eligibility for features that are unavailable at the specified prediction time.
4. **Use synthetic data to test software; use appropriately authorized real datasets to measure medical-model performance.** Synthetic results never stand in for real-data validation. A previous scoped real-data permission does not authorize a new study or deployment.
5. **Research prediction scores are not automatically patient-specific risk probabilities.** Validated calibration, appropriate population and outcome definitions, and independent evaluation are essential before stating a percentage as a clinically meaningful probability.
6. **Treat SHAP/LIME as model-behavior explanations, not proven causal factors.** Test mathematical fidelity, stability, inputs and patient-facing interpretation.
7. **Continue productive implementation without waiting idly.** Independent software engineering, source research, synthetic tests, audits, and approval-ready local runbooks proceed. Newly scoped real-patient training, locked external evaluation, or clinical serving requires its own explicit authorization.
8. **Every milestone must deliver working code plus evidence**, not a docs-only milestone disguised as AI completion.

### Non-negotiable success definition

**Engineering-complete** ≠ **research-evaluated** ≠ **clinically validated/deployable**. Each is tracked and reported separately. The project can become a well-demonstrated research prototype without asserting unearned clinical utility or population-wide calibration.

---

## 1. Clinical problem and intended use (decision prerequisite)

### 1.1 Intended estimand — Track A

- Candidate target: **cross-sectional presence of angiography-referenced obstructive CAD**, as defined by each source.
- Candidate workflow: pre-reference-test clinician-supported assessment in an appropriately defined referral/consultation population.
- Prediction moment: explicitly recorded **before** the reference diagnostic assessment, with each predictor verified to be available at that moment.
- Intended users for the initial research prototype: investigators and clinicians reviewing research outputs. No autonomous medical diagnosis or treatment instruction.
- Clearly separate the **positive-class probability** on the development population from any claim of risk for a generic mobile-app user.

**Critical scientific discrepancy:** UCI-45/Cleveland is documented with an historical `>50%` stenosis convention while UCI-412 uses `≥50%`; exact-boundary equivalence and per-record correspondence remain unresolved. Maintain **separate source-defined outcome contracts**; never silently combine or relabel them.

### 1.2 What this is *not*

- Not a time-to-event cardiovascular-risk score.
- Not a prediction of a heart attack in 30 days or a future horizon.
- Not a confirmed clinical CAD diagnosis.
- Not an acute-coronary-syndrome rule-out or emergency-triage model.
- Not an unconditional risk estimate for asymptomatic consumers or Egyptian outpatients.

### 1.3 Track B — monitoring stays distinct

- Patient history, symptoms, wearables, activity, sleep, SpO₂ and related monitoring data support longitudinal records and monitoring **outside the current CAD classifier**.
- Wearable/monitoring streams do not become Track A predictors merely because the app collects them.
- A future wearable-aware CAD model would need its own labeled target-compatible data, model development, validation and authorization.
- Verified laboratory measurements are different from wearable signals, but **verification alone never establishes prediction-model eligibility**.

---

## 2. Starting point: what is actually done vs not yet established

**Verified repository snapshot (2026-10-28):** `main` at `6ecc191800c2f505b80f97bb8261b2ed3cb36af7` following merged AI-7 PR [#65](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/65). **AI-8 is implemented in OPEN, UNMERGED [PR #66](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/66), head `13430c7ca1f52f10e8f4b75cdef1b7148fbb40ac` as reviewed.** All four remote GitHub Actions workflows were independently observed successful on that head. The agent reports local `2293 passed, 2 skipped`, not independently rerun by the plan author. This roadmap does not treat an open PR as merged. Recheck SHAs/status before acting.

| Workstream | Evidence / implementation state | What it does **not** establish |
|---|---|---|
| AI-7 research routes | Merged route catalog with five source-specific routes, strict synthetic routing and synthetic end-to-end Cleveland/UCI-412 exercises | No permission to run real patient records or deploy a model |
| Shared AI engineering | Panel validation, fold-safe preprocessing, nested CV, model selection, calibration, SHAP/LIME, evaluation, authenticated research-only bundling and inference are implemented in varying established scopes | These components do not validate a new medical cohort or a new intended-use population |
| Cleveland D-047 | A locally accepted real-data research bundle exists; maintainer reported successful offline inference on two **synthetic** inputs, including calibration and explainability engineering checks | No proof from those two outputs of real-world predictive accuracy, independent validation or clinical use |
| UCI-412 M3a / AI-8 | Prior exploratory real-data aggregate OOF AUROC approximately `0.9107` remains separately documented. AI-8 PR #66 implements synthetic 16-field source-specific training, independent synthetic holdout, calibration, SHAP/LIME, secure research-only bundle and field-contract tests; **PR is open** | Not a merged milestone, real-data fit, accepted real-model package, independent clinical validation, or eligible patient-facing risk model; **strict per-record context guard needs correction before merge** |
| Clinical + lab models | Proposed/registered contracts and engineering scaffolding | No justified real-data fit or proof that extra labs improve decisions |
| Hungary | Conditional source-compatibility documentation and locked external-evaluation architecture | No completed independent locked transportability evaluation |
| Patient mobile / OCR / doctor dashboard | Requirements and product blueprint present, including F13/F14/F15. AI-8 PR #66 introduces a proposed UCI-412 16-field acquisition contract, bound to existing panel/dictionary | OCR extraction is not model-input authorization; mappings remain PROPOSED, and no interactive patient/doctor interface or visible reproducible demo was delivered by AI-8 PR #66 |

**Important:** Existing scientific reports contain historical proposals, some stale implementation descriptions, and unresolved recommendations. AI-8 PR #66 proposes corrections to the historical AI-7 report, but these are not on `main` until that PR merges. Actual code and independently verified dataset evidence are authoritative for their respective technical/source claims. This roadmap creates no new legal/clinical approval.

---

## 3. Dataset & cohort strategy — every source has an explicit job

| Source / cohort | Primary proposed role | Allowed next work | Critical restrictions |
|---|---|---|---|
| **UCI-45 Cleveland / DA-A2** | Existing real resting-panel research baseline (5 predictors); candidate staged resting+basic-lab comparison | Audit existing bundle/evaluation; preserve exact frozen real artifact; prepare independent extension code and protocol | Do not modify accepted frozen D-047 or infer broader patient applicability |
| **UCI-412 Z-Alizadeh Sani / DA-A1** | Source-specific 16-field clinical baseline; potential same-source Clinical+Labs incremental-value study | Finish reproducible standalone engineering, validate source semantics and measurement-time evidence, prepare scoped real-data run | Scientific review currently recommends **HOLD as final development route** until key semantics/timing and validation limitations are resolved; methods benchmark remains valuable |
| **UCI-45 Hungary** | **Locked external transportability** for the predefined Cleveland resting model when justified | Source audit, locked evaluation code and fixed analysis specification | **No tuning on Hungary**, no repeated peeking at results; single-shot ledger; requires scoped real-data authorization |
| **UCI-45 VA Long Beach** | Prespecified missingness/domain-shift stress assessment where feasible | Documentation/audit and conditional evaluation design | Missing data, endpoint compatibility and sample-size constraints; do not pool blindly |
| **UCI-45 Switzerland** | High-missingness stress / data suitability analysis | Documentation/audit; quantify limitations | Very sparse relevant variables; may be unfit for predictive evaluation |
| **UCI-411** | Overlap/leakage audit or separate research task | Verify patient overlap, source dictionary and labels | Not independent of UCI-412; artery/outcome-derived fields must not leak into predictors |
| **Statlog** | Overlap and data provenance audit | Recheck independence and duplicates | Suspected Cleveland overlap; never assume independent validation |
| **AngioCAD** | Candidate modern external or alternative task source | Public metadata/source-paper audit; if later permitted, controlled file-level suitability review | Not admitted by default; distinguish per-artery angiographic labels and actual independent negative controls; D-021/source policy remains in force |
| **Other official datasets** | Filling proven gaps: new site, adequate N, routine labs, exact target, pre-test timing | Search and documented candidate screening | Only scientifically compatible datasets with verified provenance/access; no uncontrolled Kaggle mirrors or target mismatch |

### 3.1 Source admissibility scorecard (required for all candidates)

For each source, explicitly record:

1. Official landing page, owner, original paper, version, download rights and hash/provenance.
2. Number of **unique people** (not just rows or angiographic artery records); site, geography, era, referral setting, inclusion/exclusion.
3. Positive and negative counts; exact CAD reference standard, stenosis thresholds and target timing.
4. Predictor dictionary, category encodings, units, missing-value sentinel definitions, acquisition source and **pre-outcome availability**.
5. Leakage risk, overlap with our other cohorts and any same-center or publication duplicates.
6. Suitability for **development, external evaluation, calibration, or stress testing**, with rationale for acceptance/rejection.
7. External-validation sample-size/precision assessment against **predeclared estimands**, not a universal crude N cutoff.
8. Ethical/institutional/access requirements; no real-data acquisition until those are satisfied.

**Decision rule:** More records, more features or higher published AUROC do not themselves make a dataset better.

---

## 4. Model system design — feature stages and independent routes

### 4.1 Staged, source-specific panels

| Stage | Examples | Model behavior |
|---|---|---|
| **Consultation/basic history** | Age, sex, symptom characterization, verified risk factors | Use only the **source-defined**, temporally admissible features of the corresponding registered panel |
| **Resting / basic vitals + ECG** | `trestbps`, `restecg` in the Cleveland route | Never translate non-equivalent UCI-412 `BP` or chest-pain flags automatically |
| **Routine labs extension** | Cleveland `chol`, binary `fbs`; UCI-412 candidate `FBS, CR, TG, LDL, HDL, HB, WBC` | Each extension needs proven definitions/units/timing, adequate sample size, independent training/evaluation and incremental-value evidence |
| **Monitoring** | Wearable and symptom trends | **Track B only** until a separately validated wearable-aware target/model exists |

**Cleveland:** Existing five-field `da_a2_resting_v1` must remain preserved; `da_a2_resting_labs_v1` is an independent proposed extension.  
**UCI-412:** Existing 16-field `da_a1_basic_clinical_v1` is the reference baseline; `da_a1_clinical_core_labs_v1` is a proposed extension and **not** automatically eligible for real-data use.

### 4.2 Algorithm selection

- Begin with properly regularized, interpretable, source-appropriate baselines (e.g. L2 logistic regression) and only a bounded justified set of comparators (e.g. constrained tree ensemble).
- Compare models under **identical target, data, folds, censoring/exclusion, measurement stage and evaluation protocol**.
- Protect all preprocessing, imputation, feature selection and hyperparameter tuning **inside training folds**.
- Avoid using small datasets to justify increasingly complex ensembles or deep learning without sufficient evidence.
- Do not automatically choose the model with maximum AUROC; consider calibration, stability, confidence intervals, sample-size adequacy, missingness and practical data acquisition.

### 4.3 Model selection and abstention

The future model router must require explicit source/panel/model version and approved intended use; route selection is NOT automatically inferred from whichever features happen to be present. It must **not** auto-select based on whichever dataset produced the highest metric. Reject or abstain when:

- Required fields or source encodings are invalid, temporally unavailable, or unverified.
- A unit is unknown or no approved conversion exists.
- The measured population/use case is outside the model's documented scope.
- The relevant model artifact is unavailable or has not passed integrity and authorization checks.
- The clinical operation is not approved, even if a research model can technically score the record.

An unvalidated missing-field fallback or model-switching strategy is **not** silently substituted.

---

## 5. Patient/clinician inputs, OCR and future app contracts

### 5.1 The correct design order

**Clinical question & prediction time → eligible predictor evidence → model-specific feature contract → validated model → versioned acquisition mapping → Backend/OCR/Mobile/Doctor UI → integration testing.**

Data acquisition is considered *during AI design*, not invented after model training; the mobile/OCR implementation can remain scheduled downstream. The AI team must hand over complete machine-readable input contracts before the application team binds forms to predictions.

### 5.2 Required feature-to-acquisition matrix

For **every** model feature, deliver the fields below in a versioned contract:

| Contract field | Meaning |
|---|---|
| `model_id`, `panel_id`, `feature_schema_id`, `contract_hash` | Exact version/provenance binding |
| `feature_name`, `clinical_definition` | Exact source-specific clinical meaning, not a guessed synonym |
| `dtype`, `allowed_values`, `unit`, `approved_conversion` | Strict typed inputs, vocabulary and explicit conversion |
| `required`, `missing_reason`, `missing_policy` | Completeness and permitted imputation strategy |
| `prediction_time`, `availability_evidence` | Proof feature is known before reference diagnosis |
| `candidate_acquisition` | Patient questionnaire, clinician entry, measured vital, ECG interpretation, lab report, etc. |
| `acquisition_mapping_status` | **Verified / proposed / unresolved / rejected** |
| `verification_requirement` | Patient confirmation, clinician review, provenance/audit |
| `eligibility_rule` | Whether this value is admissible for this exact model/operation |
| `patient_ui_copy_status` | Whether medical phrasing has been reviewed for safe presentation |

**Example distinctions — do not collapse:**

- UCI-45 `trestbps` is resting systolic blood pressure (`mmHg`) per its source definition; UCI-412 `BP` must remain separate while its quantity/unit are uncertain.
- UCI-45 `fbs` denotes a categorical threshold around fasting glucose, **not** the raw numeric value in a lab PDF.
- A patient's chest-pain description is **not** equivalent to a verified source-specific categorical `cp` code without a tested, reviewed mapping.
- An ECG-derived category should not be guessed from the patient's self-report.
- OCR-extracted `LDL` is not automatically an input to a resting Cleveland model that does not include LDL.

### 5.3 Product blueprint boundaries already planned

- **F13** — structured history/symptoms/feature entry.
- **F14** — laboratory image/PDF upload and field extraction.
- **F15** — raw extraction → correction → patient confirmation → clinician verification, with document provenance and audit.
- **F03/F04** — clinician site and patient app.
- **F05 / Track B** — monitoring and wearables, independently handled.

**Two independent checks are mandatory:** (1) was the OCR/entered number accurately extracted and verified? (2) is this particular field **eligible** for this model, target, measurement time and protocol? A “verified” OCR field does not automatically pass check (2).

The AI milestone must produce contracts and synthetic acquisition-to-model tests; it **does not** require implementing full OCR or Flutter immediately.

---

## 6. Evaluation and medically honest probability reporting

### 6.1 Performance layers must never be conflated

| Evaluation layer | May prove | Does not prove |
|---|---|---|
| Synthetic end-to-end smoke | Software contracts, determinism, calibration/XAI code path, artifact integrity | CAD prediction performance |
| Development cross-validation / OOF | Internal performance on the studied source/population, subject to uncertainty and methodology | External transport or calibration of mobile-app users |
| Independent locked site evaluation | Transportability evidence to that specific site with stated confidence intervals | Broad clinical validation in all hospitals and countries |
| Target-population evaluation / prospective research | Stronger evidence for intended use if properly designed and authorized | Automatic regulatory/clinical deployment authorization |

### 6.2 Report the complete evaluation matrix

At minimum, where scientifically estimable: ROC-AUC, PR-AUC, sensitivity/specificity, PPV/NPV, Brier score, log loss, calibration-in-the-large/intercept, calibration slope, observed/expected (O/E) and calibration curve, prevalence, clear exploratory threshold, bootstrap or other justified uncertainty intervals, sample-size/precision constraints, and subgroup/site heterogeneity where sample size supports them. Consider decision-curve/net-benefit analysis **only when clinically meaningful, prespecified decision thresholds and valid use cases exist**.

- Identify the exact cohort, model, panel, target, time point and estimation procedure for every metric.
- Distinguish apparent, OOF, fixed-fold internal, held-out, independent external and synthetic performance.
- **Do not label a person's 54% score as 54% accuracy.**
- A threshold of 0.5 is exploratory unless clinically justified; do not market it as a diagnostic action boundary.
- A patient's calibrated probability is interpretable only under its documented target, prevalence, model transport and calibration conditions.
- Include reliability diagrams and report small-sample uncertainty honestly.
- Avoid calibration on a locked test cohort unless its design explicitly authorizes a separate recalibration exercise; report any recalibration separately from unadjusted evaluation.

### 6.3 Reference comparators

Evaluate an established clinical reference such as the **2024 ESC RF-CL** *only if*: the exact intended patient group and outcome match; all required predictor definitions and inputs can be measured correctly; the method can be implemented faithfully; and the data support a fair, prespecified comparison. Otherwise explain why that comparator is not admissible. Do not insert it just to improve presentation.

### 6.4 Calibration as a scientific criterion

- A model with excellent AUROC and poor calibration is **not** an acceptable source of a clinically meaningful percentage.
- Historic angiography-referral prevalence cannot be assumed equal to the prevalence among all mobile-app users.
- Intercept or slope recalibration is a **prespecified research intervention** requiring legitimate target-population data and separate evaluation, not an arithmetic trick applied to make scores look plausible.
- No unearned wording like "Your heart-attack risk is 60%."

---

## 7. Explainability: mathematical fidelity vs medical interpretation

**SHAP**
- Declare the explained scale (raw probability, log-odds or calibrated score as applicable).
- Check exact/appropriate additivity on that scale and consistency of one-hot/missingness lineage.
- Use representative, provenance-safe reference backgrounds and verify stability where feasible.
- Never describe SHAP feature contribution as proof that the feature *caused* CAD.

**LIME**
- Report local-fidelity error, holdout fit, perturbation settings, quality acceptance and stability.
- Reject or flag misleading explanations even when the predictor produces a numerical score.
- Use explicit “approximation of this model's local behavior” wording.

**Clinical review**
- Verify that included predictors were knowable at prediction time and not target-derived.
- Review wording and medically misleading feature names.
- Show reason codes for unavailable predictions or unreliable explanation artifacts.

---

## 8. Implementation roadmap — code and evidence, not serial reporting

**Milestone IDs here are proposed working delivery labels.** They do not silently rename or ratify existing governance gates.

| Milestone | Engineering deliverable | Real scientific deliverable | Exit criteria |
|---|---|---|---|
| **AI-7 (DONE)** | Five-route catalog, strict synthetic router and E2E exercises | Correctly bounded synthetic research evidence | PR #65 merged; four GitHub workflows passed on final PR head; research-only |
| **AI-8: Input & real-research readiness + UCI-412 completion** | Finalize source-specific 16-field contract, acquisition provenance matrix, robust UCI-412 training/package/verification adapter, negative tests, local execution handoff | Resolve or clearly label BP/PR/chest-pain/timing/encoding uncertainties; document exact eligibility, baseline CV and any permitted real experiment | A tested UCI-412 research bundle **when separately authorized and scientifically admissible**; otherwise a complete synthetic-engineered route plus evidence-qualified, explicit non-completion of real model |
| **AI-9: Clinical + routine labs** | Stage-compatible panel/model tooling, missingness policy, versioned bundle and comparison harness | Same-source incremental-value evaluation (discrimination **and** calibration), feature timing review and complexity/sample-size budget | Keep or reject each lab extension on evidence; no automatic rollout |
| **AI-10: Independent evaluation + source expansion** | Protected locked-site evaluation runner, audit/ledger, site-drift and missingness diagnostics; AngioCAD/other-source suitability tooling | Frozen-model Cleveland→Hungary evaluation where authorized, with CIs, limitations and no test-set tuning; evidence-based acceptance/rejection of new sources | Transport conclusion constrained to the evaluated site and prespecified protocol, or honest insufficient-evidence outcome |
| **AI-11: Research system integration** | Versioned multi-model registry, feature acquisition contracts, offline research inference facade, validation, verified calibration/XAI, typed status/error results and backend handoff | Reproducibility pack and research model cards; TRIPOD+AI reporting; PROBAST+AI structured appraisal | End-to-end local research demonstration; all eligible operations and explicit refusal paths tested; clinical serving still gated |
| **AI-12: Completion evidence & research handoff** | Final test matrix, versioned artifacts, instructions and scientific reporting package | Scientific strengths/limitations, model selection rationale, intended population, external validation status and unresolved approvals | Evidence-indexed handoff accepted for academic **research prototype**; no clinical readiness claim without independent support |

### 8.1 Execution sequencing (parallel tracks)

**Track 1 — engineering (start now):** source contract implementation, clinical input mapping, model and packaging adapters, negative controls, CI, local-run CLI, scientific reporting templates.  
**Track 2 — evidence (start now):** official dataset research, owner-coded variable documentation, leakage/overlap/timing audits, clinical-target and sample-size review, new dataset screening.  
**Track 3 — real research (scoped permission only):** human-reviewed protocol and authorization → reproducible local real-data execution → integrity checks → independent metrics/model-card review.  
**Track 4 — product handoff (downstream):** Backend/OCR/Mobile/Doctor UI bind only to eligible versioned AI contracts; Track B remains distinct.

**Hard rule:** Track 3 cannot be simulated as “done” by more Track 1 synthetic work. Conversely, lack of Track 3 authorization does **not** stop independent Track 1 or Track 2 progress.

---

## 9. Priority decision register: resolve with evidence, not guesses

| Issue | Current disposition | Evidence / next step | Gate |
|---|---|---|---|
| UCI-45 `>50%` versus UCI-412 `≥50%` | Unresolved source-definition equivalence | Original owner/repository definition and per-record/target audit; separate targets until justified | No silent harmonization |
| UCI-412 `BP`, `PR`, chest-pain semantics | Unresolved/partially supported | Owner-authored codebook, original methods, source archive files if permitted, explicit evidence grade per field | No user-facing mapping presented as verified |
| UCI-412 predictors available before angiography | Unresolved | Documentary/protocol evidence at variable level, with date where possible | Lab expansion blocked from real model until admissibility demonstrated |
| UCI-412 six 0/1 categorical source fields | Supported by local audit and secondary literature; residual S-9 | Confirm exact direction with owner/source documentation or make an explicit bounded scientific decision | No silent interpretation |
| UCI-412 research model as production candidate | Scientific report recommends HOLD pending key issues | Complete software and evidence gathering, do not declare final real deployment eligibility | Independent human research decision |
| Cleveland 5-field research score calibration outside referral cohort | Not demonstrated | Target population and independent evaluation; inspect existing bundle metrics | No patient-wide calibrated risk claim |
| Hungary locked evaluation | Not performed | Fixed protocol, site compatibility, appropriate N/precision and scoped authorization | Ledger must remain single-shot |
| AngioCAD/other source | Candidate, not admitted | Metadata and ethics/licensing/source-specific suitability matrix, then explicit data-use decision | No unapproved download or model training |
| Clinical risk wording and thresholds | Not validated | Clinician-approved copy and intended population/protocol | Research-only statements until approval |

### 9.1 Evidence-resolution rule

A reliable paper can motivate the **engineering design** but cannot by itself verify that a specific patient's feature was collected before diagnosis, that a private workbook follows a particular encoding, or that institutional permission was granted. All such inferences are documented as proposed/unverified unless supported by direct admissible evidence.

---

## 10. Governance and safety requirements

- Maintain existing exact scoped authorizations; D-047 Cleveland diagnostic A3 is frozen at `2b85bdff255266d216eb25f097b3eaa49d771e34` and **must not be reinterpreted as authorizing later main commits**.
- Do not change frozen A3 guards to make a new model or later commit run.
- Never commit raw patient spreadsheets, patient-level predictions, private keys, sensitive model background rows, or PHI.
- Preserve local-only, authenticated, hash-verified bundle loading and `RESEARCH_ONLY` / `approved_for_serving=False` / `clinical_use_authorized=False` until separately authorized.
- No patient-derived data in GitHub CI or external agent execution; test with generated synthetic fixtures.
- Any use of real cohort files must respect exact permitted local path, source hash, provenance and purpose.
- Ethics, institutional/medical and research-governance approvals cannot be replaced by AI research or an agent's opinion.
- Escalate unresolved patient-safety/institutional questions; proceed with independent, non-sensitive engineering meanwhile.

---

## 11. Mandatory PR and milestone quality gates

A milestone is **not** complete simply because files were added or pytest reports are green.

1. **Scope** — one bounded PR, exact baseline and full HEAD SHA; no unauthorized modifications to frozen protocols or real-bundle gates.
2. **Working system** — executable path demonstrated, source-specific feature validation, route selection and reliable error cases.
3. **Reproducibility** — pinned environment, deterministic seeds where applicable, data/code/artifact hashes, documented operating system and CLI.
4. **Medical semantics** — every outcome and predictor defined with its authority, timing, unit, missingness and unresolved flags.
5. **Performance truthfulness** — metrics labeled by data source/population and whether synthetic, internal, or truly external; confidence intervals appropriately described.
6. **Calibration** — evaluated on genuine data if claiming meaningful probabilities; no unearned risk language.
7. **Explainability** — SHAP scale/additivity and LIME local quality checked; limitations and non-causal language preserved.
8. **Safety** — no dataset pooling leakage, no premature deployment, no patient data in repo/tests, no unauthorized run.
9. **Software tests** — relevant `pytest -W error`, security/integrity regression, negative scenarios, source checks, `git diff --check`, applicable GitHub CI green.
10. **Output** — model card, feature acquisition contract, evaluation report, evidence table, explicit blocker list, next executable handoff.

**Review verdicts:** `READY_FOR_REVIEW`, `REVISION_REQUIRED`, `RESEARCH_ONLY_COMPLETE`, `INSUFFICIENT_EVIDENCE`, `CLINICAL_USE_NOT_AUTHORIZED`. A software-complete but medically unqualified route must be reported as such.

---

## 12. Immediate next implementation brief (AI-8)

The next coding-agent PR should **not** be another general documentation pass or duplicate AI-7's two synthetic E2E exercises. Instead:

1. **Audit exact current UCI-412 code, panels, aggregate results, governance and real-bundle gap.** Reconcile the current scientific `HOLD` with the older AI-First proposal without altering history.
2. **Create versioned per-field `Model Input ↔ Clinical Acquisition` contracts** for Cleveland and UCI-412, with raw→canonical coding, units, source, temporal admissibility and verification requirements. Any patient/app/OCR mapping without evidence remains clearly `PROPOSED`.
3. **Implement new negative-control and contract tests** for source mismatch, units, timing, source coding, non-equivalence, disallowed OCR/wearable routes and missing fields. Preserve existing feature schema as sole authority.
4. **Complete source-specific UCI-412 research packaging/inference integration on synthetic fixtures** by reusing existing AI components; do not duplicate a training framework. Demonstrate verified `RESEARCH_ONLY` bundle, calibration and XAI contracts.
5. **Produce a runnable, protected Windows-local real-model handoff** listing exact named prerequisites, authorized scope and deterministic commands; do not trigger or falsify authorization. If approval is not in scope, engineering can be done while real model remains explicitly unfinished.
6. **Research outstanding UCI-412 owner documentation and independent candidate cohorts** from primary scientific sources. Include a candidate decision matrix with evidence level and download restrictions.
7. **Record actual measured progress**: PR, changed files, regression counts, CI, features fixed, clinical uncertainties, what remains for a truly calibrated percentage.

**AI-8 exit target:** a concrete engineering advance toward a medically defensible real-model system **plus** a source-grounded, machine-readable app-input handoff. **Do not call it a clinically completed model if evidence/authorization is missing.**

---

## 13. Reconciliation of the supplied patient/doctor/system diagrams (2026-10-28)

**Source priority for this section:** two newly supplied infographic images, the preserved 47-slide presentation and speaker notes, the original literature-review status export, `docs/blueprint/**`, and the merged implementation on `main`. A diagram is a **product requirement**, not evidence of a trained model or a medically safe alert threshold. The slides contain aspirational/marketing claims that were explicitly rejected or narrowed in Phase 0; they do not override scientific contracts.

### 13.1 Patient workflow (first diagram: six steps)

| Diagram step | Kept in product vision | AI contract and scientific handling |
|---|---|---|
| 1. Sign up and create account | Account, verification, demographics, consent | **Identity/consent**, not CAD-model features by default; role-based access |
| 2. CAD assessment | Structured clinical history, symptoms/vitals and optional uploaded reports | Only **eligible model-panel fields**, with explicit provenance and intended measurement time; upload/OCR cannot silently populate the model |
| 3. View results | View a research assessment and explanatory information | Display **research score + cohort/calibration status + model/version + non-causal SHAP/LIME** to authorized reviewers; no medically unvalidated consumer risk percentage or individual treatment recommendation |
| 4. Connect to doctor | Link via verified authorization/code and manage consent | Association and access-control workflow; doctor must authenticate; record linking and audit |
| 5. Wearable monitoring | Sync time-stamped vitals where supported or use a simulator | **Track B only**; never automatically updates the angiographic CAD presence score |
| 6. Receive alerts | Monitoring notices and review of follow-up instructions | **Policy-driven, separately tested monitoring workflow**; NOT a CAD diagnosis or a prediction from an unvalidated real-time risk model |

### 13.2 Doctor workflow (first diagram: six steps)

1. Review patient summary, verified records, research prediction/evidence and measurement quality.
2. View monitoring alerts separately from CAD research scores; distinguish thresholds, data quality and observation provenance.
3. Record clinician review, optional note and action **without overwriting the original AI result**.
4. Set policy-governed follow-up reminders when not reviewed; never invent clinical severity cutoffs.
5. Follow up, request further assessment when clinician-authorized, update care-plan notes.
6. Manage only linked/authorized patients with auditable access.

**Important invariant from the supplied workflow:** `alert_status` and `review_status` are **independent state machines**. Doctor review may stop outstanding reminders according to a versioned policy, but **does not implicitly close/delete the underlying alert**. Alerts close only by a defined permissible policy/admin action, with audit. Reminders have capped retries, idempotency and no indefinite spam.

### 13.3 System workflow and wearable-alert diagram (second image)

**Proposed product state machine:** `DATA_RECEIVED -> DATA_QUALITY_CHECKED -> MONITORING_RULE_EVALUATED -> ALERT_CREATED (if policy condition met) -> PATIENT_NOTIFIED -> DOCTOR_LINK_CHECKED/ESCALATED -> REVIEW_RECORDED -> REMINDER_POLICY -> ALERT_STATUS_UPDATED`.

- The second image specifically shows **patient-first notification**, optional escalation to a linked doctor when policy conditions hold, and **repeated doctor reminders until reviewed or policy maximum**. These are product behaviors; implement with synthetic fixtures and testable rule definitions.
- The monitoring algorithm in the images is described as detecting abnormal patterns. **This remains a planned rules/simulation monitoring module**, not a validated anomaly detector or CAD-prognostic model. Missing sensor readings, measurement uncertainty, device capability, duplicate events and data-quality failures must not generate fabricated medical conclusions.
- A clinician review records actor/time/note and changes `review_status`; it does not modify a frozen CAD score or silently reset the alert itself.
- The illustrated severity and ``AI-powered alerts`` copy is **not medically authorized evidence**. Clinical thresholds, automated escalation and patient instructions require separately justified and reviewed policies; development may proceed with explicitly synthetic demonstration thresholds that are NEVER used on real patients.
- For acute warning symptoms, the prototype must not give false reassurance or autonomous diagnosis. Any emergency guidance is general safety copy reviewed for the intended setting, not generated from a CAD risk score.

### 13.4 Technical topology: requirement versus actual implementation

| Area in the diagram | Product intent | Technical decision for delivery |
|---|---|---|
| Flutter/React Native patient mobile, React doctor web | Cross-platform mobile + browser | Repository blueprint favors **Flutter patient + React/TypeScript doctor**; React Native is a diagram alternative, not an approved migration |
| FastAPI and AI model service | Separate API and source-specific AI contracts | Reuse the existing FastAPI mock and guarded offline research inference; do not activate real medical serving by drawing an arrow to it |
| PostgreSQL, Redis/Celery, object storage, Docker/cloud | Later product components | Do not assume these have been built or approved; existing local database/persistence decisions and free-tier/local-first constraints take precedence |
| Users/Patients/Doctors/Alerts/Reviews/Reminders tables | Conceptual ERD | **Design sketch only**, not proof of production schema, audit, consent, roles, migrations or working alert lifecycle |
| Rules and decisions panel | Capped reminders; active/reviewed independent | Express these as **versioned state/transition and audit tests** in a later backend/monitoring milestone |

### 13.5 Presentation claims explicitly NOT carried into the CAD model

The 47-slide source deck (especially slides 22–23, 29–31, 34 and 37–41) presented an ambitious **wearable-driven 30-day CAD risk**, recurrent recalculation after sensor updates, ECG-CNN fusion, automatic severity thresholds and automatic medication/lifestyle recommendations. These are **aspirational presentation statements, not accepted model evidence**. The UCI tabular target is cross-sectional CAD presence, lacks prospective outcomes and cannot support time-horizon risk, wearable re-inference or automatic clinical advice.

**No system feature is silently deleted:** these ideas are retained in a `FUTURE_SEPARATELY_VALIDATED` or `REJECTED_AS_CURRENT_MEDICAL_CLAIM` bucket, with evidence requirements. The working product may still demonstrate history, reports, wearable plots, notifications, doctor review and follow-up as **independent modules** without misrepresenting them as CAD predictive signals.

---

## 14. Original 25-paper literature review: evidence-policy and reuse

**Authoritative record:** `research/source_materials/literature_review_original.xlsx` (original colors), with `research/source_materials/literature_review_status.csv` as the searchable derived register. Verified status count: **25 papers = 9 `APPROVED_GREEN`, 1 `MAYBE_PINK`, 6 `MAYBE_ORANGE`, 9 `REJECTED_RED`**.

1. Approved papers can guide candidate comparators, algorithms, source links and reporting, but **published accuracy is never imported as CardioAssist performance**.
2. `MAYBE_*` studies are possible candidates for additional review, not automatically accepted benchmarks or source access permissions.
3. `REJECTED_RED` studies are excluded as primary project evidence/data by the existing literature policy unless the maintainer explicitly records a **new, auditable research-source re-evaluation**; neither an agent nor this roadmap silently reverses original classification.
4. Example: **P25 AngioCAD is `REJECTED_RED`**, even though its metadata is scientifically interesting. Public metadata review is fine; downloading/processing the dataset or promoting it to a primary cohort still requires a new recorded decision (`D-021`) and dataset suitability checks.
5. Framingham controlled-access cohorts, NHANES/BRFSS self-report and generic Kaggle CVD datasets may have different targets, licensing, or participants; **never swap labels, pool samples, or claim validation of angiographic CAD by convenience**.
6. For every new source/paper the research team must record `paper_id`, supervisor sheet status, DOI/owner URL, target/reference standard, selection process, independent people/sites, sample size/events, pre-test predictors/timing/units, licensing, leakage/overlap risk, feature coverage, acquisition cost, and a justified `ADMIT / HOLD / REJECT` **proposal**.

**Acceptance standard for source expansion:** a source that fixes a missing scientific requirement (e.g., independent site, reliable clinical timing, proper CAD outcome) is more valuable than another copy of a high-scoring overlapping benchmark. Document candidate screening even when the result is `NO SUITABLE NEW SOURCE FOUND`.

---

## 15. Decision authority: act now where research evidence suffices; never fabricate authority

### 15.1 Decisions the AI engineering team can make and execute immediately

- Choose modular source-specific code architecture, reproducibility methods, test fixtures, error handling, evidence matrices, UX-to-model contract design and CI.
- Reject leakage, target mismatches, false unit assumptions, invalid OCR auto-fill, unverified SHAP/LIME claims and misleading probability labels based on documented source definitions.
- Set **pre-specified research comparisons and evaluation-method proposals**, including performance and uncertainty metrics; build their software now using synthetic data.
- Perform public, read-only source research and compare open dataset **metadata**, protocol descriptions, papers and licensing.
- Select software-ready demonstration scenarios and create a deterministic, **non-clinical** research demo using synthetic test subjects.
- Register a provisional internal `ADMIT_FOR_RESEARCH_REVIEW / HOLD / REJECT` finding with supporting evidence and confidence level. This is not clinical authorization.

### 15.2 Decisions that cannot be self-ratified by searching the literature

- Institutional or research-ethics approval, consent/PHI access, and rights to use restricted datasets.
- Altering existing frozen approval gates or widening the accepted D-047/A3 scope to another dataset, feature panel, commit or intended use.
- Authorizing a new human-patient/model-training or protected external-validation run when repository governance requires a specific sign-off.
- Declaring a prediction score fit for patient-specific clinical decisions, automatic emergency triage, treatment or deployment without applicable evidence and approvals.

**Execution policy:** never stop all engineering because one permission is outstanding. Mark precisely `BLOCKED_REAL_EXECUTION — <named condition>`, then continue the separate source documentation, validations, synthetic local demonstration and integration contracts. If a critical source definition remains unverifiable, select a narrower demonstrably valid research task rather than invent an answer.

### 15.3 Evidence grades and conflicts

`E1 = official dataset-owner documentation / original publication / registry; E2 = reproducible local audited aggregate under recorded scope; E3 = peer-reviewed secondary research; E4 = engineering inference/assumption; E5 = synthetic software fixture.`

Do not upgrade E4 or E5 to E1/E2. Resolve contradictions in this order: binding governance/safety contract for **permission**, original source for **data meaning**, verified code/tests for **implemented behavior**, measured real output for **observed model performance**, product diagrams for **desired experience**. Historical presentation claims are lower-priority than later validated research findings.

---

## 16. A concrete, visible demonstration before broad AI-8 expansion

**User-facing academic progress requirement:** before counting another general AI implementation milestone as complete, deliver a **repeatable local AI research demo** whose output is understandable beyond pytest logs. The demo may be a CLI + generated Markdown/HTML report or lightweight offline viewer; it is **not** a real-patient app and must not imply approved clinical serving.

### Scenario D1 — Cleveland research score on a synthetic patient (already technically feasible)

- In a **clean authorized historical A3 environment**, retain the separately frozen Cleveland real model and its exact offline guard. Do not change SHA or replay it on a later `main` revision; prior successful local evidence may be shown read-only and properly labeled if a new run cannot satisfy historical guards.
- Alternatively exercise the fully synthetic Cleveland route on current `main` and label it `SYNTHETIC_MODEL`.
- Display original input names, strict units, validation status, research score and score definition, model/version/dataset lineage, calibration evidence status, SHAP/LIME mathematical scale and quality, plus `RESEARCH_ONLY` warning.
- Include a malformed/unavailable-value case that fails closed with a clear reason; show no diagnosis, treatment or fabricated patient-level certainty.

### Scenario D2 — UCI-412 separate panel on synthetic records

- Use the registered `da_a1_basic_clinical_v1` route and a synthetic fixture.
- Demonstrate no cross-routing to Cleveland and show why `BP`, `PR` and chest-pain fields cannot be auto-mapped to other source schemas without proof.
- Provide signed **synthetic** bundle round-trip and repeatable SHAP/LIME with declared fidelity status.

### Scenario D3 — clinical acquisition and monitoring **separately**

- Demonstrate mocked report extraction: `raw_text -> candidate analyte/value/unit/date -> corrected -> patient_confirmed -> clinician_verified -> model_eligibility_check`. All data are synthetic; `verified` must **not** imply `eligible`.
- Demonstrate simulated monitoring event: `rule evaluated -> patient notice -> possible linked-doctor notification -> review recorded -> capped reminder -> alert stays open until authorized closure`.
- Confirm a wearable event **never** changes a CAD research score and cannot be smuggled into the inference payload.

### Visible acceptance checklist

- [ ] One reproducible entry point with exact commands shown in the README; **do not invent a CLI command before it exists**.
- [ ] Source-specific valid examples and >=3 negative cases.
- [ ] Calibrated research score is marked by study/model status; synthetic numbers are **not presented as clinical performance**.
- [ ] At least one SHAP and one LIME explanation with scale and quality verdict, and safe fallback when unavailable.
- [ ] Model bundle integrity, manifest, panel/route version and source evidence shown.
- [ ] Separate, simulated doctor-review/monitoring-flow story demonstrates **no CAD auto-reprediction**.
- [ ] Aggregate model evidence and limitations provided independently from individual test predictions.
- [ ] No real patient spreadsheet, keys, private bundle, patient-level derivative or unauthorized data use in GitHub, CI, Arena or screenshots.

**End-user acceptance question:** Can the maintainer start the demo, enter/choose a synthetic sample, observe a transparent research result, see valid explanations and meaningful rejections, and explain what dataset evidence supports (or does not support) the output? If not, AI-8 cannot be claimed end-to-end complete.

---

## 17. Near-term executable PR slices and no-drift progress register

**Work on the latest merged `main`; each task creates a focused, reviewable PR.** Do not bundle an enormous rewrite or spend multiple PRs generating only governance reports. Preserve all existing controls.

| Priority | Slice | Real software artifact | Proof / acceptance | Research constraint |
|---|---|---|---|---|
| **P0** | **Plan reconciliation + demo foundation** | Register this MD in a standalone docs PR, reference existing contracts, add a runnable offline deterministic demo orchestrator and synthetic fixtures | One command documented and run; source- and calibration-labelled research score/XAI output + fail-closed invalid-input sample; CI | **Documented UCI-412 synthetic research demo now exists in OPEN PR #66 (`python -m ai uci412-demo`); code and automated CLI tests independently reviewed, maintainer-local reproduction still an acceptance step.** Historical A3 untouched |
| **P1** | **UCI-412 model input contract** | AI-8 PR #66 includes a proposed 16-feature JSON contract, stdlib validator and live-panel binding tests | Validate schema/units/types/meaning; re-run all tests and CI at corrected PR head | **IMPLEMENTED IN OPEN PR; NOT MERGED OR CLINICALLY APPROVED.** `BP`, `PR`, chest pain, S-9 binary direction and timing remain unresolved |
| **P1** | **UCI-412 package + local evidence handoff** | AI-8 PR #66 contains synthetic train/test + origin-labelled evaluation + authenticated offline bundle + SHAP/LIME | **Prior blocking review corrected in AI-8 head `3a937181`: per-record explicit context, strict real-data declaration, +27 negative cases; documented 12-stage demo added. Confirm final GitHub experiment-runner workflow and maintainer-local demo before merge | **OPEN PR; code review improvements verified. Final CI and human review remain merge prerequisites.** No new real cohort training or historical M3a scope expansion |
| **P1** | **External cohort suitability & dataset search** | Read-only source evidence matrix + reusable metadata audit and source-level eligibility tests | Explain why each cohort helps; no hidden pooling; qualified Hungary plan and AngioCAD conditional disposition | Do not peek at locked real external outcome to tune models |
| **P2** | **Labs incremental-value test framework** | Versioned baseline-vs-labs same-source comparison framework and feature timing/missingness guards | No false improvement claims from synthetic results; per-feature evidence and sample-size limits reported | Real lab fitting remains gated until valid source/timing/authorization |
| **P2** | **Research model performance and calibration proof** | Aggregate evaluation/plot generator with scoring provenance, calibration slope/intercept, intervals, subgroups if supported | Clearly distinguishes synthetic, internal and external metrics; no consumer risk claim | Real-data values only from appropriately authorized local outputs |
| **P3** | **Final research AI facade and backend contracts** | Integrate eligible packages and explanation/status responses; refuse inappropriate clinical/monitoring inputs | Repeatable demo + negative tests + versioned handoff to Backend/Mobile/OCR | Real-model serving cannot be activated from this roadmap |

### AI-8 PR #66 technical review history (2026-10-28)

- Initial review baseline: PR was **OPEN / UNMERGED** at head `13430c7ca1f52f10e8f4b75cdef1b7148fbb40ac`, with remote CI **4/4 successful** at that earlier head and agent-reported **2293 passed / 2 skipped**. This is preserved as historical evidence, not current PR status.
- New engineering content: `ai/uci412_research.py`; source-specific JSON contract and stdlib-only validator; calibration/SHAP/LIME/bundle round-trip; corrected AI-7 historical report in the PR; **174 newly collected test cases according to agent/PR**.
- **Initial blocking review (resolved in amended code):** missing `context`/`track`/`source` used to be defaulted, and a contradictory `real_data=True` could pass. Independent follow-up inspection at `3a937181` confirms a mandatory context gate, delegation to AI-7 strict context policy and 27 new regression cases.
- **Demo review (implemented, awaiting maintainer-local reproduction):** `python -m ai uci412-demo --format text` and `--budget full` now invoke a documented 12-stage synthetic-only run, report scores and SHAP/LIME, verify research-only bundle and demonstrate genuine validator rejection; see `docs/research/ai8_uci412_research_demo_runbook.md` in PR #66.
- **Scientific status:** all AI-8 numerical results are *synthetic software checks*. They are neither real UCI-412 CAD performance nor a clinically calibrated risk probability. No new UCI-412 real-data run is authorized by this PR.

### Current amended AI-8 PR #66 acceptance snapshot (2026-10-28)

- **Source:** PR [#66](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/66), **OPEN / UNMERGED**; independently inspected head `3a9371817e707cd2a8ad4254a5e873bfbc744272`, base `6ecc191800c2f505b80f97bb8261b2ed3cb36af7`.
- **Engineering changes checked:** strict per-record synthetic context validation reusing AI-7 policy; 27 new fail-closed regression cases; `ai/uci412_demo.py`, CLI `uci412-demo`, 19 new demo tests and a full runbook; versioned field contract, SHAP/LIME, calibration, authenticated `RESEARCH_ONLY` bundle remain in scope. No research model serving or authorization change.
- **Agent local test report:** `2339 passed, 2 skipped` under `-W error`; these are agent-measured local counts, not tests rerun by this reviewer.
- **GitHub CI at the exact amended head, last checked 2026-10-28:** `contract-validation`, `audit-toolchain-validation`, `mock-backend-validation` **SUCCESS**; `synthetic-experiment-runner-validation` **IN_PROGRESS**. This is a snapshot, not a claim of final 4/4 success; recheck before merge.
- **Research boundary:** complete synthetic engineering demo is **not** real UCI-412 training, calibrated individual clinical risk, clinical validation or external validation. P-1 pending; Gate PT P-3 closed; A3 frozen. Real-data completion is a distinct next scientific phase.
- **Acceptance still open:** final experiment-runner CI success on `3a937181...`, maintainer-local execution of documented CLI and review of the intended research/clinical score language. PR #66 and this docs PR #67 must be reviewed/merged separately; do not imply either is already on `main`.

### 17.1 Machine-readable completion register proposal

Add `docs/research/ai_master_progress.yaml` (or JSON) with a stable schema:

```yaml
roadmap_version: '1.3'
source_main_sha: '6ecc191800c2f505b80f97bb8261b2ed3cb36af7'
updated_on: '2026-10-28'
workstreams:
  AI-7:
    engineering: DONE
    scientific_evaluation: SYNTHETIC_ONLY
    pr: 65
    evidence: 'merged PR + successful workflows'
  AI-8:
    engineering: IMPLEMENTED_IN_OPEN_PR_CODE_REVIEWED_FINAL_CI_PENDING
    pr: 66
    head_sha_reviewed: 3a9371817e707cd2a8ad4254a5e873bfbc744272
    ci_status_on_reviewed_sha: THREE_SUCCESS_ONE_IN_PROGRESS
    scientific_evaluation: SYNTHETIC_ONLY_NOT_CLINICAL_EVIDENCE
    demo: DOCUMENTED_12_STAGE_SYNTHETIC_CLI_AWAITING_MAINTAINER_REPRODUCTION
    real_data_permission: SCOPED_SEPARATE_NOT_CONFERRED
    blocking_review: FIXED_CONTEXT_GUARD_FINAL_CI_AND_HUMAN_REVIEW_PENDING
    evidence: AI8_open_PR_3a93718_plus_3_success_1_running_GitHub_CI_and_agent_local_2339_passed
  AI-9:
    engineering: NOT_STARTED
    scientific_evaluation: NOT_COMPLETE
  AI-10:
    engineering: NOT_STARTED
    scientific_evaluation: NOT_COMPLETE
```

Each milestone update must include: `base_sha`, `head_sha`, PR URL, actual command/demo output, unit/CI results, files changed, evidence grade, real-data scope, unresolved medical assertions, and a specific `NEXT_EXECUTABLE_STEP`. Never mark `SCIENTIFIC_EVALUATION=DONE` merely because the synthetic pipeline passes.

### 17.2 Review rules for working with Arena

- The agent first reads this roadmap, actual `main`, `AGENTS.md`, ratified decisions, all relevant panels, recent PRs, source documentation and scoped tests.
- It must propose a **minimal implementation delta** against existing code and enumerate what will be reused; no replacement of working pipelines without a measured necessity.
- The agent must research field semantics and independent external sources, but never promote unverifiable data definitions to known facts.
- Every PR handoff contains concrete demonstration output, scientific evidence, test metrics and blocking conditions, including any test skipped or remote CI still pending.
- If merged descriptions disagree with code, maintain a **documentation-correction PR** or the narrowly scoped next implementation PR, not a silent rewrite of history.
- Immediate sequence: repair the AI-8 PR #66 strict-context blocker, verify CI at the new head, merge only after review, then deliver a runnable visible research demo (and preserve the source-linked input contracts). Do not substitute another generic architecture report.

---

## 18. New decisions and unresolved questions after workflow reconciliation

| ID | Question | Proposed disposition | Evidence / owner action |
|---|---|---|---|
| WRK-01 | Is patient CAD score a 30-day future-event risk? | **NO** for current tabular CAD data | Cross-sectional CAD presence only, separate any prognostic model |
| WRK-02 | Does a wearable event trigger re-inference of CAD score? | **NO** with current model, preserving Track B | Simulate monitoring/notification without CAD-model route |
| WRK-03 | Is OCR verified-value equal to model-eligible input? | **NO** | Separate trust from model-feature eligibility and timing |
| WRK-04 | Does clinician review auto-close an alert? | **NO** per supplied diagram; separate states | Versioned review/reminder/alert transitions and tests |
| WRK-05 | Can a real patient see 0.78 as a verified CAD probability? | **NO** on current evidence | Calibration/transport/current population must be established |
| WRK-06 | Does a high AUROC justify adding the next dataset/model? | **NO** | Source target, independent people, feature timing, sample size and medical value come first |
| WRK-07 | Can the project team independently research candidate data and decide engineering priorities? | **YES** | Public source research, documented reproducible decisions, bounded implementation |
| WRK-08 | Can a team decision replace required data-use/clinical authorizations? | **NO** | Remain research-only, preserve actual governance boundaries |
| WRK-09 | Can product UI be built from the provided diagrams even while AI stays offline? | **YES, as separate synthetic/monitoring prototypes** | Versioned API contracts, no clinical serving or invented severity policies |
| WRK-10 | Do we prioritize observable AI progress next? | **YES — first next delivery** | Local repeatable demo + CLI + tests + named screenshot/report evidence |

---

## 19. References and canonical repository sources

### Primary/authoritative clinical and reporting sources

- **2024 ESC Guidelines on Chronic Coronary Syndromes** — European Society of Cardiology clinical practice guideline: https://www.escardio.org/guidelines/clinical-practice-guidelines/all-esc-practice-guidelines/chronic-coronary-syndromes/
- **TRIPOD+AI 2024**, reporting guidance: https://doi.org/10.1136/bmj-2023-078378
- **PROBAST+AI 2025**, risk of bias/applicability appraisal: https://doi.org/10.1136/bmj-2024-082505
- **External validation methodology** (BMJ 2024): https://www.bmj.com/content/384/bmj-2023-074820
- **Riley et al. 2021 external-validation sample size**: https://doi.org/10.1002/sim.9025

### Original dataset catalogs and candidate identifiers

- **UCI Heart Disease (id 45)**: https://archive.ics.uci.edu/dataset/45/heart+disease
- **UCI Z-Alizadeh Sani (id 412)**: https://archive.ics.uci.edu/dataset/412/z+alizadeh+sani
- **AngioCAD candidate (Zenodo DOI; admission still gated)**: https://doi.org/10.5281/zenodo.15826856

### Workflow and literature source artifacts (present in the private repository)

- `research/source_materials/project_presentation.pdf` and `research/source_materials/project_presentation_speaker_notes.md` — 47-slide product vision, **not** the medical protocol.
- `research/source_materials/literature_review_original.xlsx` and `research/source_materials/literature_review_status.csv` — 25-paper authoritative inclusion/color policy; distinguish actual paper evidence from the source sheet's reviewer notes.
- Two new user-supplied workflow infographics dated 2026-10-28: (1) Patient/Doctor/System journey and high-level architecture; (2) monitoring alerts, reminders, review and status distinctions. These are **conversation attachments**, not yet committed to GitHub. Future maintainers must add authorized copies or a versioned textual transcription before claiming the original images are archived in-repo.

### Repository documents to read together with this plan

- [`docs/research/AI_FIRST_COMPLETION_STRATEGY.md`](https://github.com/Muhammed-Fathi/CardioAssist-AI/blob/main/docs/research/AI_FIRST_COMPLETION_STRATEGY.md)
- [`docs/research/gate-pt/15_scientific_evidence_resolution_and_development_route_REVIEW_DRAFT.md`](https://github.com/Muhammed-Fathi/CardioAssist-AI/blob/main/docs/research/gate-pt/15_scientific_evidence_resolution_and_development_route_REVIEW_DRAFT.md)
- [`docs/research/ai7_multi_dataset_research_route_system.md`](https://github.com/Muhammed-Fathi/CardioAssist-AI/blob/main/docs/research/ai7_multi_dataset_research_route_system.md) — **historical report; some initial catalog/function/test-count descriptions are stale** and must be reconciled against merged code; do not treat all narrative details as canonical.
- [`docs/blueprint/02_FEATURE_TRACEABILITY_MATRIX.md`](https://github.com/Muhammed-Fathi/CardioAssist-AI/blob/main/docs/blueprint/02_FEATURE_TRACEABILITY_MATRIX.md)
- [`docs/blueprint/05_RESEARCH_METHODOLOGY_AND_APPROVAL_GATES.md`](https://github.com/Muhammed-Fathi/CardioAssist-AI/blob/main/docs/blueprint/05_RESEARCH_METHODOLOGY_AND_APPROVAL_GATES.md)
- [`docs/DECISIONS.md`](https://github.com/Muhammed-Fathi/CardioAssist-AI/blob/main/docs/DECISIONS.md)

---

## 20. Change control and acceptance

**Adoption decision:** This document is adopted as the team's **working AI engineering/research completion roadmap**. It may be added through a normal reviewable documentation PR. Its adoption **does not** ratify `P-1`, open `P-3`, approve `D-021`, resolve S-9/H-01, or authorize processing any new private/real dataset or operating a clinical service.

**Approval signatures (to be completed by humans where applicable):**

| Role | Decision | Date | Notes |
|---|---|---|---|
| AI technical lead / maintainer | Working roadmap accepted / revise | — | — |
| Clinical supervisor | Clinical target/protocol acceptance (separate act) | — | — |
| Data/research governance owner | Scoped data access and study operation (separate act) | — | — |

**Next review trigger:** AI-8 PR #66 receives a new commit addressing per-record context validation and providing a reproducible demo; then check all CI at the new head and determine merge readiness. Also review any authoritative source evidence that changes predictor timing/target definitions, scoped real-data authorization, or discovery of an independent validation cohort.

**Version 1.2 change summary:** Retains all v1.1 workflow, source-evidence, feature-acquisition, monitoring and dataset decisions; tracks AI-8 PR #66 as **open** rather than merged; records verified 4/4 GitHub CI and separately attributed local test counts; and gates its merge on explicit synthetic context/real-data flag rejection plus an observable demo handoff. No real-data permission, clinical deployment, supervisor gate, research-protocol decision, or frozen A3 revision was altered.