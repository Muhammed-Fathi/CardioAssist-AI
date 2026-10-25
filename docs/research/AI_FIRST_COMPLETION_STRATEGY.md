# AI-First Completion Strategy: Gap Assessment, External Cohort Audit, Multi-Cohort Architecture, and Dependency Order

**Date:** 2026-10-25  
**Branch baseline:** `main` @ `0c5d993` (includes PR #51)  
**Scope:** Track A tabular coronary artery disease (CAD) AI research system (`RESEARCH_ONLY`)  
**Governance status:** Strategy & gap assessment + authorized synthetic-safe AI engineering milestone (`ai/`). Formal Gate PT (`P-3`) remains **CLOSED**; target definition (`P-1` / `D-006`) and clinical wording (`P-4`) remain **PENDING**; clinical/deployment/external-validation claims (`P-5`) remain **NOT MADE — prohibited**.

---

## 1. Executive Summary

CardioAssist-AI already possesses strong governance, read-only local dataset audit tooling (`research/audit/`, `D-046`), two isolated single-cohort internal exploratory runners (`research/experiments/` for `D-047` UCI-45 Cleveland; `research/uci412/` for `D-048`/`M3a` UCI-412 Z-Alizadeh Sani), synthetic UCI-45 staged intake prototypes (`research/intake/`), and a fail-closed `MOCK_SYNTHETIC` FastAPI inference boundary (`backend/app/inference/`, `M1c`).

However, **the repository did not yet contain a complete, end-to-end CAD AI research pipeline**:

1. **Cleveland-only (`D-047`) is scientifically insufficient as a final standalone solution:** its 5-field resting panel (`age`, `sex`, `cp`, `trestbps`, `restecg`; OOF AUROC `0.8271 ± 0.0097` across 4 repeats) contains **zero laboratory biomarkers**, reflects 1980s referral care, and even UCI-45's full 14-column processed schema offers only two crude lab fields (`chol`, binary `fbs > 120 mg/dL`) with severe cross-site missingness (`0/123` usable `chol` in Switzerland; `100/200` in VA Long Beach).
2. **Existing exploratory runners stop at aggregate CV tables (`artifact_saved: false`):** `ai/` was a 3-line placeholder. The repository lacked:
   - a unified staged clinical + routine laboratory input validator covering both UCI-45 and UCI-412 panels,
   - a lineage-preserving, JSON-serializable fold-safe preprocessor (`preprocessing.json`) tracking raw-feature-to-encoded-column ownership,
   - leak-free cross-fitted out-of-fold probability calibration evaluation (separating uncalibrated nested-CV metrics, independently cross-fitted calibrated nested-CV metrics, and the final development-OOF `calibration.json` artifact) plus descriptive outer-fold model dispersion and stage-completeness reporting,
   - **any genuine Shapley / SHAP implementation** (especially critical because `L2 LogisticRegression` won **19/20** outer folds on Cleveland and **20/20** outer folds on UCI-412, meaning a hardcoded TreeSHAP-only assumption would be unfaithful to the empirically selected model family),
   - a frozen-model external-cohort evaluation primitive paired with an optional locally protected single-shot ledger (`ExternalEvaluationLedger`),
   - a staging-atomic `RESEARCH_ONLY` model artifact packager (`0700`/`0600`), SHA-256 integrity checker, and trusted-local-origin (`trusted_local_root` + `HMAC-SHA256`) pre-deserialization boundary protecting `joblib.load` and training-projection derivatives (`shap_background.json`), and
   - an offline `RESEARCH_ONLY` inference interface returning explicitly separated raw and calibrated scores, descriptive fold dispersion, scale-aligned SHAP attributions, and explicit clinical/scientific limitations without touching the `MOCK_SYNTHETIC` HTTP API.

This milestone (**Milestone AI-1**) delivers both (a) the complete evidence-based multi-cohort strategy and dependency order below, and (b) the reusable, synthetic-tested end-to-end `RESEARCH_ONLY` AI pipeline in `ai/` (`ai.panels`, `ai.preprocessing`, `ai.calibration`, `ai.explainability`, `ai.training`, `ai.packaging`, `ai.inference`).

---

## 2. Evidence-Based Audit of Current Repository State & Exploratory Results

### 2.1 Measured local internal-exploratory evidence (already recorded on `main`)

| Run / Cohort | Source & Governance | Sample & Class Balance | Admitted Predictors | Inner-Selected OOF AUROC | Model Selection Frequency | Key Empirical Findings & Hard Limits |
|---|---|---|---|---|---|---|
| **D-047** (`docs/research/gate-pt/04_*`) | UCI-45 `processed.cleveland.data` (`DA-A2`, CC BY 4.0) | $n=303$ (`139` CAD `>50%`, `164` `<50%`; prevalence `45.9%`) | 5 resting fields (`age, sex, cp, trestbps, restecg` $\to$ 8 LR params) | **`0.8271 ± 0.0097`** (LR `0.8292`, RF `0.8211`, dummy `0.4947`) | `L2 LogisticRegression` selected **19/20** outer folds | Label-shuffle control mean `0.4882`. Calibration slope estimable `4/4` repeats (selected), `3/4` (RF). No bootstrap CIs, no lab features, no SHAP, no saved artifact. |
| **M3a / D-048** (`docs/research/gate-pt/11_*`) | UCI-412 `Z-Alizadeh sani dataset.xlsx` (`DA-A1`, CC BY 4.0, Amendment A-1) | $n=303$ (`216` CAD `>=50%`, `87` Normal; prevalence `71.3%`) | 16 basic clinical fields (`uci412_basic_clinical_v1` v1.1.0 $\to$ 16 params) | **`0.9107 ± 0.0071`** (LR `0.9107`, RF `0.8978`, dummy `0.4913`) | `L2 LogisticRegression` selected **20/20** outer folds | Max shuffle AUROC `0.5503`. Conditional bootstrap 95% CIs implemented. ECG (`7`), lab (`14`), and echo (`3`) source columns remain `REGISTERED_BLOCKED` pending timing review. Same 303 patients as UCI-411. |
| **DA-A2 Cross-Site Audit** (`docs/research/gate-da/14_*`) | UCI-45 4 processed sites (`DA-A2` read-only audit) | Cleve `303`, Hung `294`, Swiss `123`, VA `200` | Staged availability under zero-unavailable rule | Read-only descriptive audit (`modeled=false`) | N/A | Resting (`5` cols): Cleve `303/303`, Hung `292/294` (`99.3%`), Swiss `120/123`, VA `143/200`. Resting+Labs (`+ chol, fbs`): Cleve `303/303`, Hung `261/294` (`88.8%`), Swiss **`0/123`**, VA `100/200`. Exercise (`11` cols): Hung `95/294` (`32.3%`). |

*Non-comparability notice:* D-047 (`0.8271`) and M3a (`0.9107`) differ in cohort geography, era, referral prevalence (`45.9%` vs `71.3%`), stenosis boundary wording (`>50%` vs `>=50%`), and predictor richness (`5` vs `16` fields). Neither number establishes cross-population superiority or clinically reliable individual CAD risk.

### 2.2 Component-by-component AI pipeline gap assessment

| Pipeline Requirement | Pre-Milestone State (`0c5d993`) | Concrete Gap Identified | Addressed in `ai/` (This Milestone) | Still Gated on Human Approval |
|---|---|---|---|---|
| **1. Validated clinical inputs & feature mapping** | `research/intake/` covers UCI-45 synthetic stages & 5-field R1 mapping; `research/uci412/feature_schema.py` validates 55-col workbook dictionary. | No unified record-level clinical/lab input contract spanning UCI-45 staged panels (`resting`, `resting+labs`) and UCI-412 panels (`basic_clinical`, `clinical+core_labs`) with unit, zero-unavailable, missing-reason, anti-leakage, and anti-wearable enforcement. | **`ai/panels.py`** — Reuses `research.intake` and `research.uci412.feature_schema` to provide immutable staged panel contracts (`da_a2_resting_v1`, `da_a2_resting_labs_v1`, `da_a1_basic_clinical_v1`, and synthetic-only proposed `da_a1_clinical_core_labs_v1`). | Admitting `da_a1_clinical_core_labs_v1` or `AngioCAD` into real-data runs requires Gate PT (`P-3`) / `D-021`. |
| **2. Missing-data handling & fold-contained preprocessing** | `ColumnTransformer` inside `experiments` & `uci412`; M2b synthetic array preprocessor. | No portable JSON-serializable preprocessor (`preprocessing.json`) that both enforces training-fold-only imputation/scaling/reference-coding and records exact `raw_feature -> encoded_columns` group lineage. | **`ai/preprocessing.py`** — `FoldSafeClinicalPreprocessor` fits strictly on training folds, preserves categorical `0` vs missing `NaN`, emits missingness indicators, tracks disjoint per-feature column slices, and exports/reloads pure JSON + SHA-256. | None for software; real-data fitting gated on `P-3`. |
| **3. Model training & model selection** | Nested CV in `experiments` and `uci412` (`Dummy`, `L2 LR`, `RF`). | Runners discard all fitted estimators (`artifact_saved: false`); no post-selection research refit pipeline exists even for synthetic CI verification. | **`ai/training.py`** — Fold-contained nested-CV selection (with simplicity tie-breaker) + synthetic-guarded refit of selected family and fold ensemble. | Real-patient artifact fitting remains blocked until `P-1` + `P-3` sign-off. |
| **4. Internal & independent evaluation** | Internal repeated nested CV + label-shuffle control exist per dataset; `cross_site_feasibility.py` is descriptive only. | **Zero executable frozen-model external cohort evaluation primitive or local single-shot ledger** enforcing non-pooling, known-overlap blocks, and prevalence-shift diagnostics without touching the external cohort during selection. | **`ai/training.py`** — `evaluate_locked_external_cohort()` evaluates a frozen `TrainedResearchRun` without refitting; optional `ExternalEvaluationLedger` (`one_shot_ledger_path`) enforces single-shot protocol consumption locally. String metadata checks are documented as metadata guards only, never proof of participant non-overlap. | Real `Hungary` and `AngioCAD` evaluations are hard-blocked in code until `P-3` (plus `D-021`/Gate DA for `AngioCAD`). |
| **5. Discrimination, calibration, class-specific metrics & dispersion** | `research/uci412/evaluation.py` computes AUROC, PR-AUC, Brier, log-loss, intercept/slope, 10-bin reliability, Sens/Spec/PPV/NPV/F1, and OOF bootstrap CIs. | No cross-fitted out-of-sample calibrated nested-CV evaluation (where evaluated rows are excluded from both model AND calibrator fitting), no standalone `calibration.json`, and no compatible fold-dispersion summary. | **`ai/calibration.py` & `ai/training.py`** — Preserves separate (1) uncalibrated nested-CV metrics, (2) cross-fitted calibrated nested-CV metrics (inner-OOF calibrator per outer training fold), and (3) final development-OOF `calibration.json` (whose resubstitution check is labeled an apparent diagnostic); reports descriptive outer-fold dispersion using each fold's own compatible calibrator without claiming validated epistemic uncertainty or clinical cutoffs. | Threshold selection for clinical action (`P-4`) remains pending clinician sign-off; exploratory `0.5` only. |
| **6. Genuine model-faithful & score-aligned SHAP explanations** | **None.** `backend/app/mock_prediction.py` emits hash-derived fake offsets (`synthetic: True`); `research/` has no XAI code. | Both **LinearSHAP** and **TreeSHAP** were absent, and raw-model attributions must never be misdescribed as additive explanations of post-hoc calibrated probability. | **`ai/explainability.py`** — Exact **Grouped Interventional LinearSHAP** on `calibrated_log_odds` ($\phi_{0,\text{cal}} = a + b\phi_{0,\text{raw}}$, $\phi_{j,\text{cal}} = b\phi_{j,\text{raw}}$; `expit(...) == calibrated_research_score`, additive in log-odds, not probability) or `raw_log_odds` when uncalibrated; Exact **Grouped Interventional TreeSHAP** on `raw_model_score` (`raw_model_probability`, never relabeled as calibrated-probability SHAP), verified against $2^M$ coalition enumeration to `< 1e-12`. | Updating `/v1` HTTP mock capabilities waits until backend integration after `P-3`/`P-4`. |
| **7. Model versioning, artifact safety, privacy & integrity** | `backend/app/artifact_admission/` verifies `artifact_descriptor/v1` for `mock_clinical_v1`/`v2` only. | No staging-atomic bundle writer, no trusted-local-origin authentication before `joblib.load`, and no privacy guard for encoded training rows in `shap_background.json`. | **`ai/packaging.py`** — Temporary-staging-directory atomic commit (`0700`/`0600`) with full cleanup on interrupted/failed builds; distinguishes SHA-256 self-consistency (`verify_research_bundle`) from trusted-local-origin authentication (`verify_trusted_local_bundle`: `trusted_local_root` + local UID/`0600` + `HMAC-SHA256`) enforced before `joblib.load`; classifies `shap_background.json` as an invertible training-row derivative blocked for real patients while `P-3` is closed. | Real-data bundles must remain strictly local under git-ignored `data/` after Gate PT authorization; never committed or shared publicly. |
| **8. Research-only inference interface** | `backend/app/inference/` is `MOCK_SYNTHETIC`-only (`FailClosedRealModelProvider` refuses construction). | No offline `RESEARCH_ONLY` predictor existed to turn a trusted local bundle + validated clinical/lab record into aligned raw/calibrated scores, dispersion, SHAP, and explicit limitations. | **`ai/inference.py`** — `ResearchCadPredictor.from_verified_bundle(..., trusted_local_root=...)` enforces producer authentication prior to `joblib.load`, exposes separate `raw_model_score`, `raw_model_log_odds`, `calibrated_research_score`, `calibrated_log_odds`, and exact SHAP target/scale, and stamps `clinical_use_authorized=False`. | Serving any real model over FastAPI HTTP routes remains prohibited (`M1c`) pending `P-1`–`P-5`. |
| **9. Automated unit, reproducibility, regression, failure-mode & integration tests** | 1,666 tests across `contracts`, `backend`, `audit`, `experiments`, `uci412`. | Zero tests for `ai/`, faithful SHAP axioms, OOF calibration serialization, locked external-cohort governance, bundle tamper rejection, or research-only inference. | **`tests/experiments/test_ai_research_pipeline.py`** — Executed automatically by `experiment-runner-ci.yml` on Python 3.11 & 3.12 with `-W error`. | None. |

---

## 3. External Authoritative Dataset Search & Suitability Evaluation (`2026-10-25`)

Authoritative biomedical and ML repositories (UCI Machine Learning Repository, Zenodo, NHLBI BioLINCC, PhysioNet, Nature *Scientific Data* / Figshare / Dryad, Mendeley Data) were searched on `2026-10-25` using metadata/documentation inspection only (**zero patient files downloaded**). Candidates were judged against Target `T1` (cross-sectional angiography-referenced obstructive CAD presence), pre-test clinical/laboratory predictor timing, cohort independence, open licensing, `$0` accessibility, and Riley sample-size adequacy.

| Candidate Dataset & Persistent Identifier | Reference Standard & Target | Cohort Size & Provenance | Clinical & Laboratory Predictors | Access, License & Cost (`2026-10-25`) | Suitability Ruling for CardioAssist-AI |
|---|---|---|---|---|---|
| **AngioCAD** — Zenodo `10.5281/zenodo.15826856` (Hosseini et al., *Comput Methods Programs Biomed* 2026:109368; audited row `P25` = `REJECTED_RED` in `literature_review_status.csv`; Zenodo record API metadata checked `2026-10-25`) | **Source-verified:** Invasive X-ray coronary angiography with artery-level stenosis labels in **7 severity categories** (`AngioCAD_Labels.xlsx`, 43,267 B). **Unverified before file audit:** exact mapping to binary `T1` (`>=50%` vs `<50%`) and usable positive vs negative non-CAD control counts. | **Source-verified:** **$n=413$ patients** at one heart center in Isfahan, Iran (distinct city/hospital from `UCI-412` in Tehran). *Note:* secondary community estimates suggesting subsets with complete clinical rows (`~377`) or mapped clinical/lab counts (`~13`) are **not** file-level verified. | **Source-verified:** Standalone `AngioCAD_Features.xlsx` (129,493 B) containing structured clinical + laboratory attributes. **Unverified before file audit:** exact column dictionary/units, compatibility with `UCI-412`, and pre-angiography acquisition timing. | **Source-verified via Zenodo API:** `access_right: "open"`, **`CC BY 4.0`**, **`$0`**, standalone `.xlsx` files separate from video `.rar` archives. **Governance:** `P25` is **`REJECTED_RED`** (`D-021`); zero patient files downloaded. | **PROMISING CANDIDATE ONLY — NOT AN ACCEPTED VALIDATION COHORT (Blocked on `D-021` + Gate DA):** Publication & Zenodo metadata justify human `D-021` review, but do *not* establish `UCI-412` schema compatibility, pre-cath feature timing, or non-CAD control counts without an authorized read-only `Gate DA` workbook audit. |
| **NHLBI BioLINCC — PROMISE (`HLB01661717a`, NCT01174550) & ISCHEMIA (`HLB02742323a`) & CASS (`HLB00250309a`)** | `PROMISE` CCTA arm ($n \approx 4,533$ of $10,003$ outpatients) & `CASS` ($n=2,099$ invasive angiography) | Multi-center North American prospective clinical trials with adjudicated obstructive CAD | Rich, prospectively timed baseline clinical history, vitals, resting ECG, and **fasting lipid/glucose/renal laboratory panels** | `$0` NHLBI fee, **Controlled Access**: requires institutional IRB/ethics determination + executed NHLBI RMDA | **LONG-TERM CLINICAL-GRADE VALIDATION TRACK (Blocked now):** Gold-standard pre-test timing and sample size, but cannot be acquired without institutional signatory + IRB review. Documented for post-prototype clinical validation; not a blocker for current `$0` local engineering. |
| **MultiD4CAD** — Zenodo `10.5281/zenodo.15063615` / `15148653` (*Sci Data* Sept 2025, `10.1038/s41597-025-05743-w`) | CCTA plaque / CAD status | $n=118$ selected (from 300 screened) at University Hospital Palermo, Italy | Framingham clinical risk factors (BMI, HTN, DM, LDL/statin, FH, smoking) + EAT/PAT CT radiomics | **Restricted Zenodo access** (authenticated request + author approval required) | **EXCLUDE FOR CURRENT MILESTONE:** Restricted access + small sample ($n=118$ provides insufficient validation events). |
| **UCI Nasarian CAD Dataset** — UCI Repository (Nasarian et al., *Pattern Recognit Lett* 2020) | Clinical/CAD diagnosis in occupational clinic | $n=150$ **male-only** industrial employees, Abadan, Iran | 52 workplace/environmental, demographic, symptom, and lab features | Open UCI, `$0` | **EXCLUDE:** Very small ($n=150$), **100% male occupational cohort** (complete exclusion of female patients creates severe sex/spectrum bias), and non-uniform angiography verification. |
| **Tabriz SYNTAX Angiogram Dataset** — Figshare `10.6084/m9.figshare.25801447` (*Sci Data* Mar 2025, `10.1038/s41597-025-04727-0`) | Invasive X-ray angiography + 16-segment AHA SYNTAX score | $n=231$ patients, Shahid Madani Hospital, Tabriz, Iran (2018–2020) | Clinical HIS records + angiographic SYNTAX variables | Open Figshare, `$0` | **EXCLUDE FOR T1 CAD PRESENCE:** Cohort inclusion restricted exclusively to patients who **already had `>70%` obstructive stenosis** (`0` non-CAD controls; cannot train or validate CAD presence vs absence). |
| **CADICA** (Mendeley `10.17632/p9bpx9ctcv.2`, 2024) & **Danilov XCA** (Mendeley `10.17632/ydrm75xywg.1`) & **ARCADE** (Zenodo `10.5281/zenodo.10390295`) & **CardioSYNTAX** (Zenodo `10.5281/zenodo.14005818`) | Invasive XCA lesion / SYNTAX annotations | `CADICA` $n=42$; `Danilov` $n=100$ (all 1-vessel CAD); `ARCADE` / `CardioSYNTAX` image-centric | `CADICA` has basic comorbidities on only 42 patients; `ARCADE` lacks pre-cath clinical/lab table | Open (`CC BY 4.0`) | **EXCLUDE FOR TABULAR T1:** Either far below minimum validation sample size ($n=42$), all-positive cases (`0` controls), or imaging-only without pre-angiography clinical/lab tables. |
| **PhysioNet Databases** (`PTB-XL`, `STAFF-III` $n=104$ elective PTCA ECGs, `INCART` $n=32$ Holters with 7 CAD patients, `MIMIC-IV`) | Waveform ECG statements / ICU records | Various | Waveform-centric; lacks standardized outpatient pre-angiography CAD presence reference cohort | Open / credentialed | **EXCLUDE FOR T1:** Different target construct (`T5` ECG statements or acute ICU care), not outpatient pre-angiography tabular CAD presence. |

**Existing inventory reminder (`docs/research/gate-da/01_*`):** `UCI-411` (`DA-B1`) is the exact same 303 patients as `UCI-412` (`DA-A1`) with leakage vessel columns (`LAD`, `LCX`, `RCA`) — **never an independent cohort or additive sample size**. `UCI-145 Statlog` ($n=270$) is a suspected Cleveland recirculation — **excluded from external validation**. `CDC BRFSS` / `NHANES` (`T3` self-report) and Kaggle mirrors (`DS-6k`, `DS-7`) remain excluded from `T1`.

---

## 4. Cohort & Feature Strategy: Accounting for Product Needs Without Premature Product Build

### 4.1 Why future product requirements matter to AI feature design now
CardioAssist-AI's target platform (`D-035`, `D-037`, `D-038`, `ED-DA-A2-01`) will eventually support:
1. **Structured clinical consultation & vitals** (age, sex, chest-pain characteristics, dyspnea, diabetes, hypertension, smoking, dyslipidemia, family history, BMI, resting BP, pulse rate, resting ECG),
2. **Routine laboratory report values** (fasting blood glucose, lipid panel `LDL`/`HDL`/`TG` or total cholesterol, serum creatinine, hemoglobin, WBC — entered as structured values first and later assisted by OCR), and
3. **Mandatory clinician review** of model output, calibration caveats, missing-stage completeness, and patient-specific SHAP attributions, while **strictly blocking unvalidated wearable (`Track B`) streams** from entering `Track A` CAD inference (`D-039`).

Therefore, the AI layer must be organized around **explicit measurement stages** (`consultation/resting` $\to$ `resting + routine labs`) with:
- strict unit tokens (no silent unit guessing between `mg/dL` and `mmol/L`),
- conservative zero-as-unavailable rejection (`trestbps=0`, `chol=0`, `BP=0`),
- explicit `missing_reasons` (`not_provided`, `not_measured`, `not_available_at_time`, `unknown`) paired with fold-contained imputation + missingness indicators, and
- faithful clinical-feature-level SHAP attributions (summing encoded one-hot + missingness-indicator contributions back to each named clinical/lab variable for clinician inspection).

### 4.2 Rejected multi-cohort practices (Hard Prohibitions)
1. **Never pool datasets (`UCI-45 + UCI-412`, multi-site `UCI-45` naive row concatenation, or `UCI-412 + AngioCAD`)** merely to inflate $N$: differences in referral prevalence (`36%` Hungary vs `46%` Cleveland vs `71%` Tehran), era (1980s vs 2010s–2020s), stenosis wording (`>50%` vs `>=50%`), and coding create severe site-confounding shortcuts and miscalibration.
2. **Never treat overlapping or extension files (`UCI-412` + `UCI-411`, or `Cleveland` + `Statlog`) as independent observations.**
3. **Never use `Hungary` (or `AngioCAD`) for feature selection, missingness-rule tuning, model-family choice, hyperparameter tuning, or threshold tuning** while it is designated as a locked external assessment cohort.

### 4.3 Preferred Evidence-Based Development & Validation Strategy

**Dual-Track Non-Pooled Source-Specific + Harmonized Transportability Strategy:**

1. **Primary Rich Clinical + Routine Laboratory Development Track (`DA-A1` UCI-412, Tehran, $n=303$, $87$ Normal minority class):**
   - **Stage 1 Baseline (`da_a1_basic_clinical_v1`, 16 consultation/risk-factor/symptom/vital predictors; 16 encoded parameters):** Retains the audited M3a panel (OOF AUROC `0.9107`, `L2 LogisticRegression`) as the zero-lab consultation benchmark.
   - **Stage 2 Routine Lab Expansion (`da_a1_clinical_core_labs_v1`, proposed for Gate PT `P-3` review):** Adds a pre-specified, clinically standard 7-biomarker routine blood panel (`FBS`, `CR`, `TG`, `LDL`, `HDL`, `HB`, `WBC`) — chosen *a priori* from standard outpatient metabolic/lipid/renal/CBC lab reports rather than data-dredged against `Cath` labels — fitted with strong L2 / elastic-net shrinkage to respect the 87-non-event Riley degrees-of-freedom budget, while keeping echocardiography (`EF-TTE`, `Region RWMA`, `VHD`) excluded unless pre-angiography timing is independently documented.
   - Evaluates whether routine blood labs materially improve nested-CV discrimination, Brier score, and calibration slope over `da_a1_basic_clinical_v1` before admitting the larger panel.

2. **Locked Independent External Transportability Tracks (Zero Pooling, One-Shot Locked Evaluation):**
   - **External Track E1 — Immediate Multi-Site Transportability within `DA-A2` (`Cleveland` $n=303$ $\to$ Locked `Hungary` $n=294$):**
     - Under a frozen Gate PT protocol, fit two staged `Cleveland` models — **Resting (`da_a2_resting_v1`, 5 fields)** and **Resting + Basic Labs (`da_a2_resting_labs_v1`, 7 fields: `+ chol, fbs`)** — with training-fold median + missingness-indicator preprocessing and inner-OOF logistic calibration.
     - Evaluate **once** on **locked `Hungary` ($n=294$)** (`292/294` complete at Resting; `261/294` complete and `294/294` evaluable with Cleveland-fitted missingness handling at Resting+Labs). Report unadjusted transport discrimination, calibration-in-the-large (explicitly quantifying the `45.9% -> ~36.1%` prevalence shift), calibration slope, class-specific metrics, and prior-odds intercept-recalibrated sensitivity. (`VA Long Beach` and `Switzerland` are restricted to pre-specified high-missingness stress tests, never pooled.)
   - **External Track E2 — Candidate Clinical + Lab External Investigation via `AngioCAD` (Promising Candidate Only; Blocked on `D-021` + Gate DA):**
     - Preserve the existing **`REJECTED_RED` (`P25`) / `D-021`** governance boundary: do **not** treat `AngioCAD` as an accepted validation cohort and do **not** self-authorize downloading `AngioCAD_Features.xlsx` or `AngioCAD_Labels.xlsx`.
     - *If* human scope decision **`D-021`** authorizes a read-only `Gate DA` inspection (`D-046` pattern), first verify at the file level: (i) usable binary `T1` positive AND negative (`<50%` / `0%`) event counts across the 413 patients, (ii) exact column definitions and measurement units, (iii) pre-angiography acquisition timing, and (iv) institutional/temporal separation from `UCI-412`. Only if all four checks pass may a pre-registered harmonized `UCI-412 -> AngioCAD` external evaluation protocol be proposed under `Gate PT` (`P-3`), executed once via `ExternalEvaluationLedger`.

### 4.4 Clearly Defined Fallback Strategy

If human scope decision **`D-021` (`AngioCAD`) is declined or deferred** AND **UCI-412 laboratory/ECG pre-angiography timing cannot be resolved at Gate PT**:

- Execute final real-data research completion strictly on the **already-custodied, SHA-256-verified UCI inventory (`DA-A1` + `DA-A2`)** under one consolidated Gate PT (`P-1` + `P-3`) protocol producing **two complementary, non-pooled `RESEARCH_ONLY` model packages**:
  1. **`UCI-412` Consultation & Vitals Model (`da_a1_basic_clinical_v1`, 16 fields):** Full internal repeated nested CV + conditional bootstrap 95% CIs + inner-OOF calibration + faithful Linear/TreeSHAP + verified `RESEARCH_ONLY` bundle, explicitly labeled *single-center internal referral validation only (routine lab panel held out due to unverified pre-cath timing)*.
  2. **`UCI-45` Staged Resting & Resting+Lab Transportability Pair (`da_a2_resting_v1` [5 fields] & `da_a2_resting_labs_v1` [7 fields], `Cleveland` $n=303$ $\to$ one-shot locked `Hungary` $n=294$):** Provides genuine independent-center external evaluation and prevalence-shift calibration evidence, explicitly documenting 1980s-era and 2-lab-field boundaries.

---

## 5. Authorization Boundaries & Ordered Implementation Dependency Graph

### 5.1 Authorization distinction
- **Authorized NOW (executed in Milestone AI-1):** Implementing and testing the complete software architecture in `ai/` — staged clinical/lab panel contracts, fold-contained lineage-preserving preprocessing, nested-CV model selection with cross-fitted inner-OOF calibration evaluation, frozen external-cohort evaluation primitive + `ExternalEvaluationLedger`, development-OOF logistic calibration (`calibration.json`), descriptive outer-fold model dispersion, exact score-aligned LinearSHAP & TreeSHAP, staging-atomic `RESEARCH_ONLY` bundle packaging, SHA-256 integrity verification + trusted-local-origin `HMAC-SHA256` authentication (`verify_trusted_local_bundle`), and the offline `ResearchCadPredictor` inference interface — **tested exclusively on generated synthetic fixtures** without touching real datasets, `/v1` OpenAPI contracts, or `backend/app/inference/` (`MOCK_SYNTHETIC` remains the sole active FastAPI provider).
- **Requires New Scoped Human Authorization (NOT bypassed here):**
  1. **`D-021` + Gate DA (`P-2`) amendment:** Before downloading `AngioCAD_Features.xlsx` / `AngioCAD_Labels.xlsx` into local git-ignored `data/raw/angiocad/` to inspect column definitions, timing, and event counts.
  2. **Gate PT (`P-1` target sign-off + `P-3` protocol sign-off):** Before running `ai/` to fit/save any real-patient model bundle (or `shap_background.json` derivative) on `UCI-412` or `Cleveland`, executing the single-shot `Hungary` evaluation via `ExternalEvaluationLedger`, or unlocking `da_a1_clinical_core_labs_v1` on real `UCI-412` rows.
  3. **Clinician wording & serving gate (`P-4` + `P-5` + post-`M1c` authorization):** Before exposing any real or research model through FastAPI HTTP endpoints or presenting probabilities in clinician/patient UIs.

### 5.2 Implementation dependency order

```text
[Step 1: Staged Clinical + Lab Input Contracts & Feature Lineage (ai/panels.py)]
        │  (reuses research.intake + research.uci412.feature_schema)
        ▼
[Step 2: Fold-Contained Lineage-Preserving Preprocessing (ai/preprocessing.py)]
        │  (training-fold-only stats + disjoint raw->encoded feature slices + JSON export)
        ├───────────────────────────────────────────────┐
        ▼                                               ▼
[Step 3: Cross-Fitted OOF Calibration & Dispersion] [Step 4: Score-Aligned Grouped Interventional SHAP]
        (ai/calibration.py)                             (ai/explainability.py: calibrated-log-odds
        │                                                LinearSHAP & raw-prob TreeSHAP + 2^M oracle)
        └───────────────────────┬───────────────────────┘
                                ▼
[Step 5: Nested-CV + Cross-Fitted Cal Eval + Frozen External Primitive & Ledger (ai/training.py)]
        │  (separates uncalibrated, cross-fitted calibrated, and apparent final-OOF diagnostics)
        ▼
[Step 6: Staging-Atomic RESEARCH_ONLY Packager & Trusted-Local-Origin Verifier (ai/packaging.py)]
        │  (0700/0600 staging commit, SHA-256 + local HMAC-SHA256 auth, shap_background privacy)
        ▼
[Step 7: Offline RESEARCH_ONLY Inference Interface (ai/inference.py)]
        │  (raw & calibrated scores + descriptive fold dispersion + aligned SHAP + limitations)
        ▼
[Step 8: Automated Synthetic Unit, Oracle, Calibration-Exclusion, Security & Integration Tests]
        │  (tests/experiments/test_ai_research_pipeline.py — executed in CI now)
        ▼
[Step 9 (BLOCKED ON HUMAN GATE PT / D-021): Local Authorized Real-Cohort Execution]
           (UCI-412 Stage 1/2 + Cleveland->Hungary ledger-enforced eval + candidate AngioCAD audit)
```
