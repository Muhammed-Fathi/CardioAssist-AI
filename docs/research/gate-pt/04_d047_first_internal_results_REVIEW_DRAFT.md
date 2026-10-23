# D-047 — First Internal Exploratory Cleveland CAD Results (Review Draft)

> ## `INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED`
>
> - **Status:** **REVIEW DRAFT — NOT SUPERVISOR APPROVED — NOT CLINICAL EVIDENCE — NOT EXTERNALLY VALIDATED**
> - **Experiment:** `CAI-T1-D047-CLEVELAND-EXPLORATORY-V0.1`
> - **Evidence basis:** **maintainer-reported, locally verified aggregate results** extracted by the human maintainer from the completed protected local run.
> - **Gate PT P-3:** **CLOSED** · **Supervisor approval:** **NOT OBTAINED** · **Clinical/patient-care use:** **NOT AUTHORIZED**
> - **Prepared:** 2026-10-23 · **Document type:** internal research review packet (documentation only)

**This document is not medical advice, not a diagnostic claim, not a publication result, and not evidence of supervisor, ethics, or institutional approval.** It records a bounded internal exploratory benchmark on one public historical dataset. It must not be used to justify clinical deployment, patient-facing risk percentages, product accuracy claims, or any statement that a CardioAssist model is validated.

---

## 0. Reading guide and evidence provenance

### 0.1 Labels used throughout this document

| Label | Meaning |
|---|---|
| **[MR]** | **Maintainer-reported.** Supplied by the human maintainer from local extraction of the protected experiment report. Not independently reproduced by the agent. |
| **[AR]** | **Agent-verified — repository.** Checked by the agent against committed repository files, commit objects, or the committed runner source at the reported code commit. |
| **[AA]** | **Agent-verified — arithmetic.** Recomputed by the agent from the maintainer-reported rounded values only (no new modelling, no data access). |
| **[GAP]** | **NOT AVAILABLE TO AGENT — HUMAN REVIEW REQUIRED.** Not supplied, or not accessible to the agent; must not be guessed or reconstructed. |
| **[BLANK]** | Intentionally unfilled. A human must complete it; the agent must not prefill it. |

### 0.2 What the agent saw, and what it deliberately did not see

**Supplied to the agent (sanitized aggregates only):** experiment identity and execution status, class counts, model comparison aggregates, per-repeat AUROC values, outer-fold family-selection counts, negative-control summary, and calibration summaries. These are attributed **[MR]** throughout.

**Never accessed, requested, transmitted, or reproduced by the agent:** local protected source rows (`data/raw/uci-45/processed.cleveland.data`), `report.json`, `predictions.csv`, the D-046/D-047 signed local authorization manifests, provenance/licence snapshot hashes, per-patient fold assignments, per-patient out-of-fold scores, confusion-matrix cell counts, model artifacts, or any run-identifier/path detail. No `data/` directory exists in this repository checkout.

**Issue #32 status:** the GitHub integration available to the agent returned **HTTP 403** for `Muhammed-Fathi/CardioAssist-AI` issues, including Issue #32 and Issue #35. Issues are therefore **not** cited here as agent-read sources. Every performance value in this document comes from that sanitized extract; repository-level facts are marked **[AR]**, and anything requiring the Issue #32 thread is marked **[GAP]**.

### 0.3 Verification boundary (explicit)

- The agent did **not** run, rerun, or re-score the experiment, and did **not** independently verify the local protected files, the source SHA-256, or the report/predictions digests.
- The agent **did** check the reported values against the committed protocol, the registered plan, the committed runner source at the reported code commit, and against each other by arithmetic (Section 6).
- Agreement in Section 6 demonstrates **internal coherence of the reported numbers with the frozen method**. It is **not** independent validation of the underlying run or data.

---

## 1. Registered experiment identity and execution record

### 1.1 Identity

| Field | Value | Source |
|---|---|---|
| Experiment ID | `CAI-T1-D047-CLEVELAND-EXPLORATORY-V0.1` | **[MR]**, **[AR]** (matches `research/experiments/cleveland_d047_exploratory_plan.v0.1.json`) |
| Report banner | `INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED` | **[MR]**, **[AR]** (pinned in `research/experiments/config.py`) |
| Code commit used for the run | `146122b7e20447c4a635215a34f6db47a5efefbb` | **[MR]**; **[AR]** this is the merge commit of PR #34 and is the `main` tip in this checkout |
| Dataset | UCI-45 `processed.cleveland.data` (DA-A2) only | **[MR]**, **[AR]** (single permitted source in plan/adapter) |
| Predictors | `age`, `sex`, `cp`, `trestbps`, `restecg` | **[MR]**, **[AR]** (five-field allowlist) |
| Outcome | `num = 0` → 0 versus `num = 1..4` → 1 | **[AR]** (plan + adapter) |
| Outer resampling | stratified 5 folds × 4 repeats (seeds `20261023`–`20261026`) | **[MR]**, **[AR]** |
| Inner resampling | stratified 5 folds | **[MR]**, **[AR]** |
| Negative control | 3 prespecified label shuffles | **[MR]**, **[AR]** (seeds `20262001`–`20262003`) |
| Governance | D-047 internal exploratory route; Gate PT P-3 **CLOSED** | **[AR]** |

### 1.2 Execution and custody record — **[MR]**

| Item | Reported result |
|---|---|
| D-047 local preflight | **PASS** |
| Real experiment execution | Completed successfully, exit code 0 |
| Source rows parsed | 303 |
| Positive cases (`num=1..4`) | 139 |
| Negative cases (`num=0`) | 164 |
| Original source after execution | **Unchanged** |
| Report and predictions SHA-256 | Locally verified by the maintainer (digests intentionally **not** reproduced here) |
| Git-ignore and NTFS ownership/ACL checks | PASS |
| Final full-cohort model artifact saved | **No** |
| External validation performed | **No** |

The digests referenced above establish **byte integrity of local artifacts only**; they are not reproduced in this document and do not, by themselves, prove that the bytes originated from the official UCI host. The committed runner records that limitation as `HUMAN_ATTESTED_NOT_INDEPENDENTLY_PROVEN_BY_LOCAL_HASH` **[AR]**.

### 1.3 Repository-level provenance checks performed by the agent — **[AR]**

| Check | Result |
|---|---|
| Frozen protocol content since D-047 ratification (PR #31 merge `434e49a`) | **Unchanged** — protocol blob `b882c74` is identical at the ratification merge and at the run commit |
| Registered plan file since ratification | **Changed before the first fit** during M2c implementation (plan blob `2ae2af8` at ratification → `58e07c2` at the run commit). Direct comparison identifies exactly **five** changed paths: `dataset.prohibited_predictors` (expanded), `dataset.expected_binary_target_counts` (added), `cv.seed_derivation` (added), `preprocessing.categorical_missing_imputation` (added), and `metrics.calibration_diagnostics` (added). Model grids, fold counts, repeat seeds, negative-control seeds, the 0.01 selection tolerance, the 0.50 threshold, and the primary metric are unchanged. **No naive-confidence-interval restriction was added to the plan JSON by this diff.** |
| Protocol/plan bound at run time | The runner requires the local manifest's frozen protocol and plan SHA-256 values to match the files at run time and re-checks them after fitting **[AR]** |

**Naive-CI restriction attribution:** the prohibition on treating the four repeated out-of-fold rows as independent observations is **pre-existing** in the registered plan (present at ratification and untouched by the five paths above). It is stated in the frozen protocol and enforced by the runner's registered-configuration validation in `research/experiments/config.py` **[AR]**. It is **not** part of the pre-fit plan change and must not be attributed to it.

> **Human action required:** confirm that the **five pre-fit plan-file changes** were recorded as a documented pre-fit amendment to the registered plan (D-047 requires post-fit revisions to be logged as amendments; this change preceded the fit, but the traceability record should still be explicit). **[GAP]**

---

## 2. Research question, cohort, target and predictors

### 2.1 Cohort and target — **[MR]/[AR]**

| Property | Value |
|---|---|
| Source | UCI-45 processed Cleveland (`DA-A2`), single cohort |
| Records | **303** |
| Positive (`num` 1–4) | **139** |
| Negative (`num` 0) | **164** |
| Positive fraction | 139/303 ≈ **0.4587** **[AA]** |
| Endpoint | historical angiography-referenced **current CAD presence**, source-defined |
| Not the endpoint | 30-day or future event risk, incident disease, angiographic severity, population prevalence |

Every person contributes exactly one outer-fold prediction per repeat. The four repeats **re-partition the same 303 records**; they are **not** four cohorts and not 1,212 people.

### 2.2 Predictors and effective parameter count — **[AR]**

Reference-coded logistic regression over the five source fields implies **8 slope coefficients** (excluding intercept): `age` 1, `sex` 1, `cp` 3, `trestbps` 1, `restecg` 2. `num` is a label only; `ca`, `thal`, catheterization/vessel/angiography fields, identifiers, site fields, and wearable inputs are excluded by the plan and adapter.

Raw `n`/parameters or `139/8` is **not** a sample-size justification. See Section 7.

### 2.3 Intended-use and timing caveats

The historical UCI chronology does **not** certify that all five fields were clinically recorded *before* coronary angiography. This is a **retrospective benchmark**, not a prospective pre-catheterization decision tool. Predictor timing, referral selection, and the 1980s-era measurement conventions remain unresolved limitations (Section 8), and no clinical workflow claim is made.

---

## 3. Registered design as executed

### 3.1 Model families and bounded grids — **[AR]**

| Method | Registered configuration |
|---|---|
| Prevalence dummy | `DummyClassifier(strategy="prior")`, fitted on the outer-training fold only; no predictors |
| L2 logistic regression | `solver=liblinear`, `penalty=l2`, `C ∈ {0.1, 1, 10}`, `max_iter=2000`, `class_weight=None` |
| Constrained random forest | 200 trees, `max_depth ∈ {3, 5}`, `min_samples_leaf ∈ {5, 10}`, `max_features=sqrt`, `class_weight=None` |
| Inner-selected procedure | Per-outer-fold choice between the two families and their bounded grids using inner-CV ROC-AUC; **primary estimand** |
| Label-shuffle negative control | Identical nested-CV wiring on permuted labels; 3 shuffles, one repeat each |

No neural network, AutoML sweep, boosted-tree family, or post-hoc predictor panel was registered, and the runner rejects configuration other than the frozen plan **[AR]**.

### 3.2 Repeated nested stratified CV and selection rule — **[AR]**

- Outer 5 stratified folds × 4 repeat seeds; inner 5 stratified folds within each outer-training partition.
- Inner search sees **only** the outer-training partition. Median imputation, LR standardization, most-frequent categorical imputation, and fixed-vocabulary reference one-hot encoding are all fitted inside sklearn `Pipeline`/`ColumnTransformer` objects within the inner folds.
- Both families are tuned in every outer fold; the outer assessment fold is scored **once** per family.
- Selection rule: **L2 logistic regression is chosen if its inner mean ROC-AUC is no more than 0.01 below the best family; otherwise the best family is chosen.** Simplicity preference is pre-registered, not post hoc.
- The inner-selected procedure's outer score **reuses the chosen family's outer-fold predictions**; no second fit and no assessment-fold tuning occurs.
- Fixed exploratory classification threshold: **0.50**, never tuned on outer predictions.

### 3.3 Leakage controls documented by the registered design — **[AR]**

Training-only preprocessing; no target-based feature selection; whole-cohort variable screening prohibited; source-specific label mapping; prohibited-predictor registry enforced in code and plan; nested selection isolated from outer assessment; deterministic seeds with single-threaded numerical libraries; source hash re-verified after parsing and after fitting. Residual leakage risk that the design cannot exclude (record-level identity, undocumented documentation/site proxies, historical cohort artefacts) remains **(Section 8)**.

### 3.4 Negative control

Three prespecified label-shuffle runs (seeds `20262001`–`20262003`), each one outer repeat, using the same nested-CV wiring. Interpreted as a **smoke test only**: no formal permutation p-value is computed, and a result near 0.5 **does not prove** the absence of every form of leakage.

---

## 4. Aggregate results — **[MR]**

### 4.1 Primary registered estimand

> **Repeated nested outer out-of-fold AUROC of the complete inner-selected procedure** = **0.8271 ± 0.0097** (mean ± population SD across four dependent CV repeats).

Supporting per-family analyses are reported below. They are **predeclared supportive analyses**, not an unbiased winner-selection test, and not a claim that logistic regression is superior.

### 4.2 Aggregate model comparison

All entries are **mean ± population SD across the four dependent CV repeats** (population SD, `ddof=0`) **[MR]**, matching the committed aggregation code **[AR]**.

| Metric | Prevalence dummy | L2 logistic regression | Constrained random forest | Inner-selected procedure |
|---|---:|---:|---:|---:|
| **AUROC** (primary metric) | 0.4947 ± 0.0000 | 0.8292 ± 0.0062 | 0.8211 ± 0.0085 | **0.8271 ± 0.0097** |
| Average precision / AUPRC | 0.4559 ± 0.0000 | 0.7737 ± 0.0151 | 0.7544 ± 0.0151 | 0.7712 ± 0.0193 |
| Accuracy @ 0.50 (exploratory) | 0.5413 ± 0.0000 | 0.7739 ± 0.0050 | 0.7492 ± 0.0096 | 0.7723 ± 0.0077 |
| Sensitivity @ 0.50 (exploratory) | 0.0000 ± 0.0000 | 0.7536 ± 0.0060 | 0.7410 ± 0.0088 | 0.7536 ± 0.0060 |
| Specificity @ 0.50 (exploratory) | 1.0000 ± 0.0000 | 0.7912 ± 0.0066 | 0.7561 ± 0.0149 | 0.7881 ± 0.0117 |
| Brier score | 0.2483 ± 0.0000 | 0.1658 ± 0.0026 | 0.1745 ± 0.0038 | 0.1671 ± 0.0049 |

**Reading notes that must accompany these numbers:**

- Source prevalence is **0.4587**; AUPRC is therefore not interpretable against 0.5.
- The 0.50 operating point is **exploratory only** and is **not** a patient-care threshold. It was fixed before fitting and never selected from outer predictions.
- Accuracy of the prevalence dummy (0.5413) equals the negative fraction (164/303) because a prior-only dummy assigns every record to the majority class.
- No confidence interval, standard error, test statistic, or p-value exists for any row of this table. The `±` values are **descriptive dispersion across repeat-level scalars**, not sampling uncertainty (Section 4.6).

### 4.3 Per-repeat AUROC — **[MR]**

| Outer repeat seed | L2 logistic regression | Constrained random forest | Inner-selected procedure |
|---|---:|---:|---:|
| 20261023 | 0.8359 | 0.8255 | 0.8359 |
| 20261024 | 0.8326 | 0.8263 | 0.8326 |
| 20261025 | 0.8192 | 0.8064 | 0.8107 |
| 20261026 | 0.8292 | 0.8262 | 0.8292 |
| **Mean** | **0.8292** | **0.8211** | **0.8271** |
| **Population SD** | **0.0062** | **0.0085** | **0.0097** |

All four repeats reuse the same 303 records. Repeat-to-repeat differences reflect **resampling/partition randomness only**, not between-cohort or between-population variation.

### 4.4 Model-family selection across outer folds — **[MR]**

| Selected family | Outer folds (of 20) |
|---|---:|
| L2 logistic regression | **19** |
| Constrained random forest | **1** |

Interpretation constraints:

- This is a **descriptive count** under the registered rule, which grants LR preference whenever its inner AUROC is within 0.01 of the best family. The high LR selection rate is partly a **consequence of the pre-registered simplicity rule**, not an empirical discovery.
- `19/20` must **not** be read as a 95% "probability of clinical superiority", a confidence level, or an effect size.
- Because the inner-selected outer scores reuse the chosen family's predictions, the primary estimand is **not independent evidence** additional to the LR supportive analysis. In any repeat where LR won every fold, the two are numerically identical (Section 6).

### 4.5 Negative-control smoke test — **[MR]**

| Item | Value |
|---|---|
| Method | Prespecified label-shuffle nested-CV smoke test, identical safe CV wiring |
| Shuffle count | 3 |
| Mean shuffled-label AUROC | **0.4882** |
| Formal permutation p-value | **NOT COMPUTED** |
| Per-shuffle AUROC values and dispersion | **[GAP]** |

**Permitted reading:** the negative-control result is **descriptively consistent with chance-level discrimination**, which is the expected behaviour of a correctly wired procedure on permuted labels.
**Prohibited readings:** that leakage is "ruled out"; that a mean slightly below 0.5 demonstrates anti-learning or a systematic defect (ordinary sampling variation under permutation is sufficient to produce this); or that 0.4882 constitutes a formal null distribution, p-value, or type-I-error control.

### 4.6 What the reported dispersion is — and is not

| It **is** | It **is not** |
|---|---|
| The population SD of four **repeat-level** metric values | A standard error of the performance estimate |
| A description of how much the estimate moves when the folds are repartitioned | A 95% (or any) confidence interval |
| Computed across **four correlated evaluations of the same 303 records** | Evidence about variability across patients, sites, or populations |
| Reported to keep the descriptive result honest | A basis for statistical significance, ranking, or hypothesis testing |

**No pooled 4 × 303 = 1,212 inference is valid.** The registered plan explicitly forbids treating repeated-CV rows as independent (a pre-existing clause; see §1.3), and no appropriate person-level resampling estimator was prespecified for this pilot. Any interval reported later requires a **separately prespecified and justified** estimator (for example, resampling at the person level), documented before it is computed.

### 4.7 Descriptive differences that must not be over-read

| Comparison | Descriptive difference | Status |
|---|---:|---|
| LR AUROC − inner-selected AUROC | +0.0021 | Descriptive arithmetic only. Smaller than the repeat-to-repeat dispersion of both rows |
| LR AUROC − RF AUROC | +0.0081 | Descriptive arithmetic only. Comparable to one repeat-level SD; **no test was prespecified or performed** |
| Inner-selected AUROC − dummy AUROC | +0.3324 | Descriptive arithmetic only. The dummy is a reference baseline, not a subject of hypothesis testing |

No claim of statistical significance, proven superiority, or "best model" is made anywhere in this document.

---

## 5. Calibration findings

### 5.1 Definitions used by the committed runner — **[AR]**

- **Calibration slope / intercept** come from a **free intercept + slope logistic recalibration fit on the out-of-fold predictions**, reported **only** as a descriptive diagnostic. No recalibration is applied and no prediction is altered.
- **Calibration-in-the-large (CITL)** is an **intercept-only** logistic update with the prediction logit as a **fixed offset (slope held at 1)**. It is **not** the free intercept from the joint fit.
- The runner marks slopes `ESTIMATED_DESCRIPTIVE_OOF_DIAGNOSTIC` when the optimiser converges and the coefficients are finite and bounded, and `UNSTABLE_OR_NOT_ESTIMABLE` otherwise (including non-convergence, rank deficiency, or out-of-bound coefficients) **[AR]**. A `NOT_ESTIMABLE` slope therefore carries **no numerical value** and is **not** a zero.
- Reliability curves use five quantile bins and collapse repeated cut points; bin values are aggregate-only.

### 5.2 Aggregate calibration summary — **[MR]**

| Model | Mean slope (estimable repeats only) | Estimable | Mean CITL (4 repeats) |
|---|---:|---:|---:|
| L2 logistic regression | 0.9105 | **3/4** | −0.0192 |
| Constrained random forest | 1.3710 | **3/4** | −0.0033 |
| Inner-selected procedure | 0.8980 | **4/4** | −0.0212 |

### 5.3 Per-repeat calibration — **[MR]**

| Seed | Model | Slope | Slope status | CITL |
|---|---|---|---:|---:|
| 20261023 | L2 logistic regression | 0.9202 | `ESTIMATED_DESCRIPTIVE_OOF_DIAGNOSTIC` | −0.0140 |
| 20261023 | Constrained random forest | 1.3817 | `ESTIMATED_DESCRIPTIVE_OOF_DIAGNOSTIC` | −0.0061 |
| 20261023 | Inner-selected | 0.9202 | `ESTIMATED_DESCRIPTIVE_OOF_DIAGNOSTIC` | −0.0140 |
| 20261024 | L2 logistic regression | 0.9281 | `ESTIMATED_DESCRIPTIVE_OOF_DIAGNOSTIC` | −0.0237 |
| 20261024 | Constrained random forest | **NOT_ESTIMABLE** | `UNSTABLE_OR_NOT_ESTIMABLE` | −0.0149 |
| 20261024 | Inner-selected | 0.9281 | `ESTIMATED_DESCRIPTIVE_OOF_DIAGNOSTIC` | −0.0237 |
| 20261025 | L2 logistic regression | **NOT_ESTIMABLE** | `UNSTABLE_OR_NOT_ESTIMABLE` | −0.0320 |
| 20261025 | Constrained random forest | 1.2781 | `ESTIMATED_DESCRIPTIVE_OOF_DIAGNOSTIC` | −0.0109 |
| 20261025 | Inner-selected | 0.8604 | `ESTIMATED_DESCRIPTIVE_OOF_DIAGNOSTIC` | −0.0399 |
| 20261026 | L2 logistic regression | 0.8833 | `ESTIMATED_DESCRIPTIVE_OOF_DIAGNOSTIC` | −0.0071 |
| 20261026 | Constrained random forest | 1.4533 | `ESTIMATED_DESCRIPTIVE_OOF_DIAGNOSTIC` | +0.0186 |
| 20261026 | Inner-selected | 0.8833 | `ESTIMATED_DESCRIPTIVE_OOF_DIAGNOSTIC` | −0.0071 |

### 5.4 Interpretive limits of the calibration findings — mandatory wording

1. **Two slopes are missing, and the cause is not identified.** The LR slope in seed `20261025` and the RF slope in seed `20261024` are `UNSTABLE_OR_NOT_ESTIMABLE`.
2. **Numerical non-convergence is a plausible explanation** for a missing slope, and the recorded status vocabulary is deliberately non-specific. A missing slope **must not** be described as proven overfitting, confirmed miscalibration, statistical non-identifiability, or a model defect.
3. Conversely, an **estimable** slope does **not** establish good calibration. Slopes near 0.9 (LR/inner-selected) and above 1.3 (RF) are **descriptive out-of-fold diagnostics on roughly 303 records with 139 events**, obtained once per repeat, and are **not** estimates of a population calibration parameter.
4. **CITL values here are offset-only diagnostics.** They are not interchangeable with the free intercept of a joint slope/intercept fit, and the joint-fit intercepts were not supplied **[GAP]**.
5. No recalibration was performed, and these diagnostics were **not** used for fitting, threshold selection, or model selection.
6. **No statement about clinical calibration, risk-percentage accuracy, or the need for recalibration before deployment may be made from this table.** Calibration quality remains an open question requiring a separately reviewed analysis.

### 5.5 Reliability curves

All **12** reported reliability-curve status entries are `DESCRIPTIVE_OOF_AGGREGATES` **[MR]**. They correspond exactly to the three procedures requested from the maintainer's local extraction script — **L2 logistic regression, constrained random forest, and the inner-selected procedure** — across four repeats (**3 × 4 = 12**). The prevalence-dummy procedure **was not requested in that extraction**, so no dummy reliability curve is reported here.

**The count of 12 is therefore expected and complete for the extraction. It is not an experiment discrepancy, a reporting omission, or evidence of missing calibration output.** Individual reliability-bin values (`n`, mean predicted probability, observed positive fraction) for those 12 curves remain **unreviewed and unsupplied** and are **[GAP]**.

---

## 6. Arithmetic and internal-coherence checks performed by the agent — **[AA]**

All checks below use **only** the rounded values supplied by the maintainer. No experiment was run, no data were accessed, and no new model was fitted.

| # | Check | Expected / derived | Reported | Outcome |
|---:|---|---|---|---|
| 1 | Cohort accounting | 139 + 164 = 303 | 303 records | ✅ consistent |
| 2 | Positive fraction | 139/303 = 0.45875 | 0.4587 (used as AUPRC reference) | ✅ consistent |
| 3 | Dummy accuracy vs class balance | 164/303 = 0.54125 | 0.5413 | ✅ consistent |
| 4 | Dummy sensitivity/specificity | all-negative assignment ⇒ sensitivity 0, specificity 1 | 0.0000 / 1.0000 | ✅ consistent |
| 5 | Dummy Brier score — **approximate reference** using global prevalence p = 139/303 | p(1−p)² + (1−p)p² = 0.24830 | 0.2483 | ✅ consistent as a four-decimal reasonableness check |
| 6 | Dummy AUPRC vs prevalence | ≈ 0.4587 for a near-random score | 0.4559 | ✅ consistent in magnitude (slight offset expected because the per-fold dummy probability varies) |
| 7 | Mean of per-repeat AUROCs (LR) | 0.829225 | 0.8292 | ✅ consistent |
| 8 | Mean of per-repeat AUROCs (RF) | 0.821100 | 0.8211 | ✅ consistent |
| 9 | Mean of per-repeat AUROCs (inner-selected) | 0.827100 | 0.8271 | ✅ consistent |
| 10 | Population SD from 4-dp rounded repeats (LR / RF / inner-selected) | 0.006254 / 0.008493 / 0.009760 | 0.0062 / 0.0085 / 0.0097 | ✅ consistent within 4-dp rounding of the inputs |
| 11 | Inner-selected equals LR in seeds 20261023, 20261024, 20261026 (AUROC and calibration), differs only in 20261025 | Expected if LR won every fold in those repeats and RF won in one fold of 20261025 | Matches exactly | ✅ consistent with **19/20** LR selection and with the runner reusing the selected family's predictions |
| 12 | Mean slopes across estimable repeats | 0.91053 / 1.37103 / 0.89800 | 0.9105 / 1.3710 / 0.8980 | ✅ consistent |
| 13 | Mean CITL across four repeats | −0.01918 / −0.00333 / −0.02118 | −0.0192 / −0.0033 / −0.0212 | ✅ consistent |

**Check 5 is an approximation, not an exact recomputation.** The recorded dummy was fitted on each **outer-training fold's** prevalence, which can differ slightly from the full-cohort 139/303. The global-prevalence formula is therefore a four-decimal **reasonableness check**; exact agreement is neither expected nor required, and a near-match does not imply the fold prevalences were constant.

**What these checks establish:** the supplied numbers are **internally coherent** with the frozen selection rule, the fold-fitted prevalence dummy, and the aggregation definitions in the committed code.
**What they do not establish:** that the run occurred as reported, that the protected files match these values, or that the numbers are free of data-level or design-level bias. Items 10 and 11 reveal no contradiction — the small SD differences are fully explained by recomputing from four-decimal inputs.

---

## 7. Sample-size adequacy — **NOT ASSESSED**

### 7.1 Recorded status

> `NOT_ASSESSED_NO_HUMAN_REVIEWED_ANTICIPATED_COX_SNELL_R2_ASSUMPTIONS`

This status is recorded in the committed experiment report structure **[AR]** and is carried forward unchanged here. **No Riley-style sample-size adequacy assessment has been performed for this experiment.**

### 7.2 Descriptive planning quantities (not adequacy evidence)

| Quantity | Value |
|---|---:|
| Events (positive) | 139 |
| Non-events | 164 |
| Reference-coded LR slope parameters | 8 |
| Events per parameter (descriptive) | ≈ 17.4 |
| Non-events per parameter (descriptive) | ≈ 20.5 |

These ratios are **descriptive planning arithmetic only**. They do **not** demonstrate adequacy and must not be presented as a sample-size justification.

### 7.3 What a human reviewer must supply before any adequacy statement

- Anticipated **Cox–Snell R²** (and the resulting Nagelkerke R²) for this predictor set, drawn from **external literature or explicit expert elicitation**, with citations.
- The target **shrinkage** criterion (e.g. ≥ 0.9) and the **precision** criterion for the overall risk estimate.
- Sensitivity scenarios across plausible R² values, with the resulting minimum sample sizes.
- A recorded NO-GO / caution rule if 303 records and 139 events fall short under any defensible scenario.
- Confirmation that penalisation (L2) is being treated as a stability aid, **not** as a substitute for adequate sample size.

### 7.4 Prohibited derivation (explicit)

**The observed performance of this experiment must not be used to derive the anticipated R² assumptions.** Back-calculating `R²` from the observed AUROC would make the adequacy test circular: it would use the result to justify the sample that produced it. This prohibition applies to the primary estimate (0.8271), to the LR estimate (0.8292), and to any per-repeat or calibration-derived quantity.

### 7.5 Consequence for interpretation

Until Section 7.3 is completed by a human, this experiment supports **software/research feasibility findings only**. It does **not** support clinical predictive adequacy, model-selection finality, or a claim that the model is sufficiently powered for confirmatory research.

---

## 8. Scientific limitations

1. **Design/endpoint.** Retrospective, cross-sectional **CAD presence** classification in a historical angiography-referred cohort. Not future-event risk, not incident disease, not severity, not population screening.
2. **Single source.** One cohort (303 records). No second site, no temporal split, no independent external validation. No pooling with UCI-411/412, Statlog, Hungary, VA, or Switzerland.
3. **Repeated evaluation, not repeated sampling.** Four repeats reuse the same 303 individuals. All dispersion is resampling-based and describable only.
4. **No inferential statistics.** No confidence intervals, no p-values, no formal model comparison, no multiplicity handling, no non-inferiority/equivalence testing.
5. **Calibration.** Slopes estimable in 3/4 (LR), 3/4 (RF) and 4/4 (inner-selected) repeats; missing values of unknown cause; CITL offset-only; reliability-bin values not reviewed. Calibration quality is **unresolved**, not established and not refuted.
6. **Negative control.** Three shuffles, smoke-test scope, no formal null distribution. Consistent-with-chance is reassuring but not proof of absence of leakage.
7. **Sample size.** Riley-style adequacy **NOT ASSESSED**; anticipated R² assumptions are absent; 8 reference-coded parameters against 139 events remains a shrinkage/optimism concern.
8. **Selection-rule artefact.** The 0.01 LR preference means the inner-selected procedure and the LR supportive analysis are near-identical. The primary estimand is therefore **not** an independent confirmation of LR.
9. **Predictor provenance.** The five resting fields were chosen for input plausibility and audited availability, **not** because they are clinically validated predictors, and their historical measurement timing relative to angiography is not certified.
10. **Data quality and identity.** UCI-45 raw Cleveland carries an upstream integrity warning and is quarantined in this project; processed Cleveland was used. Patient identity/independence cannot be verified from rows, and possible overlap with other UCI-45 sites or Statlog remains an open, separately reviewed question.
11. **Missingness.** `?` is treated as missing; **missingness reasons were never recorded in UCI-45** and must not be invented as indicators. Informative missingness cannot be excluded.
12. **Generalisation.** 1980s-era clinical practice, referral patterns, coding conventions and measurement devices differ from any current setting. Nothing here speaks to contemporary performance or fairness across subgroups.
13. **Reporting standards.** TRIPOD+AI and PROBAST+AI assessments are **pending human review** (Section 10). This document is not TRIPOD+AI-complete.
14. **Governance.** Gate PT **P-3 remains CLOSED**; no supervisor, ethics, or institutional approval exists; no clinical, deployment, or external-validation claim is made or implied.

---

## 9. Provisional research conclusion (internal exploratory only)

**Provisional, descriptive, and non-inferential.** On a single historical cohort of 303 records with five resting predictors, the registered repeated nested 5×5 stratified CV procedure (four outer repeats) produced:

- a **primary AUROC of 0.8271 ± 0.0097** for the inner-selected procedure;
- a **supporting LR AUROC of 0.8292 ± 0.0062**, with L2 logistic regression chosen in **19 of 20** outer folds under the pre-registered selection rule;
- a **constrained RF AUROC of 0.8211 ± 0.0085**;
- all three well above the **prevalence-dummy AUROC of 0.4947 ± 0.0000**; and
- a **label-shuffle smoke test mean AUROC of 0.4882**, consistent with chance-level discrimination.

**What this may be taken to mean:** the registered pipeline runs end-to-end under its safety controls, produces internally coherent aggregate results, and yields descriptive discrimination well above a prevalence-only baseline on this benchmark. That is a **feasibility and engineering-validity finding** with scientific signal worth following up under proper review.

**What this may not be taken to mean:** that the model is clinically useful, calibrated, adequately powered, superior to any alternative, transportable to another cohort, or ready for any supervisor, publication, regulatory, product, or patient-facing statement. Calibration is only partly estimable, the sample-size assessment is absent, and every evaluation reuses the same 303 people.

**Status of this conclusion:** **PROVISIONAL — REVIEW DRAFT — `INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED`.** It becomes citable only after human completion of Sections 7 and 10 and a documented supervisor review under a formal Gate PT process.

---

## 10. Reviewer checklist

Tick boxes require a **named human reviewer**. The agent has deliberately left every disposition, signature, and date blank.

### 10.1 TRIPOD+AI reporting readiness

| # | Item | Status / reviewer note |
|---|---|---|
| T1 | Title/abstract identify this as an **internal exploratory, not externally validated** model study | ☐ |
| T2 | Source data, dates, and cohort setting described; single-cohort scope explicit | ☐ |
| T3 | Eligibility, inclusion/exclusion, and the 303/139/164 flow documented | ☐ |
| T4 | Outcome definition (`num` 0 vs 1–4) and its historical angiography reference stated | ☐ |
| T5 | Predictors defined, timing relative to outcome addressed, and leakage exclusions listed | ☐ |
| T6 | Sample size / events-per-parameter handled with a justified method, not EPV alone | ☐ **BLOCKED — Section 7 not assessed** |
| T7 | Missing data: mechanism assumed, handling described, reasons not fabricated | ☐ |
| T8 | Model development, hyperparameter search space, and inner-selection rule fully specified | ☐ |
| T9 | Internal validation design (nested CV) and its limits reported accurately | ☐ |
| T10 | Performance measures reported with the primary estimand distinguished from supportive analyses | ☐ |
| T11 | Calibration reported with estimability status and explicit diagnostic definitions | ☐ |
| T12 | No confidence intervals, p-values, or significance claims where none were computed | ☐ |
| T13 | Code, protocol and plan availability and versioning recorded (protected data excluded) | ☐ |
| T14 | Limitations, risk of bias, and applicability stated without overclaiming | ☐ |
| T15 | Registration/protocol deviation log (including the pre-run plan tightening in §1.3) recorded | ☐ |
| T16 | Fairness/subgroup performance addressed or explicitly declared out of scope | ☐ |

### 10.2 PROBAST+AI risk of bias and applicability

| Domain | Question | Status / reviewer note |
|---|---|---|
| Participants | Was selection representative, and is the angiography-referred historical sample appropriate for the stated intended use? | ☐ |
| Participants | Is patient independence within/between records verified or honestly bounded? | ☐ |
| Predictors | Are the five predictors available at the claimed decision timepoint, and is timing verified? | ☐ |
| Predictors | Are documentation/site proxies and post-outcome information excluded? | ☐ |
| Outcome | Is the outcome definition reproducible and free of ascertainment bias? | ☐ |
| Outcome | Is the >50% vs ≥50% boundary question kept separate from this source-specific result? | ☐ |
| Analysis | Is the nested CV correctly implemented and free of outer-fold leakage? | ☐ |
| Analysis | Are sample size, overfitting, and optimism adequately handled? | ☐ **BLOCKED — Section 7** |
| Analysis | Are performance and calibration analyses appropriate for the small event count? | ☐ |
| Analysis | Are selection-rule artefacts (LR preference, near-identical primary/supportive analyses) disclosed? | ☐ |
| Applicability | Is the result applicable to any real target population, and is that claim avoided? | ☐ |

### 10.3 Calibration QA

| # | Item | Status / reviewer note |
|---|---|---|
| C1 | Confirm slope/intercept are free recalibration fits on OOF predictions only, not refits of the model | ☐ |
| C2 | Confirm **CITL is offset-only** and not reported as a joint-fit intercept | ☐ |
| C3 | Review the two non-estimable slopes for possible numerical non-convergence without labelling them overfitting | ☐ |
| C4 | Decide whether a documented convergence/optimiser investigation is warranted (new analysis ⇒ new amendment) | ☐ |
| C5 | Review and, if appropriate, approve disclosure of the 5-bin reliability curves (values not yet supplied) | ☐ |
| C6 | Confirm no recalibration, threshold tuning, or risk-percentage claim was derived from these diagnostics | ☐ |
| C7 | Confirm the 12 reliability entries cover the three extracted non-dummy procedures × four repeats (3 × 4 = 12), with the prevalence dummy deliberately not extracted | ☐ |
| C8 | Confirm calibration remains **unresolved** in all external communication | ☐ |

### 10.4 Sample-size sensitivity

| # | Item | Status / reviewer note |
|---|---|---|
| S1 | Supply cited anticipated Cox–Snell R² assumptions from external evidence or elicitation | ☐ **REQUIRED** |
| S2 | State the shrinkage and precision criteria to be met | ☐ **REQUIRED** |
| S3 | Run and record sensitivity scenarios (minimum n per scenario) | ☐ **REQUIRED** |
| S4 | Compare required versus available 303 records / 139 events and record GO / CAUTION / NO-GO | ☐ **REQUIRED** |
| S5 | Confirm assumptions were **not** back-derived from observed AUROC | ☐ |
| S6 | Keep the `NOT_ASSESSED` status in all downstream documents until S1–S5 are complete | ☐ |

### 10.5 Future dataset suitability (no work authorized by this checklist)

| # | Item | Status / reviewer note |
|---|---|---|
| F1 | Any external validation requires a **separately frozen** protocol with the model locked beforehand | ☐ |
| F2 | UCI-412 / UCI-411 same-participant relationship must be resolved before treating either as external | ☐ |
| F3 | Statlog overlap with Cleveland requires an identity/duplicate review before any use | ☐ |
| F4 | Hungary / VA / Switzerland require eligibility, target harmonisation, quality and overlap review | ☐ |
| F5 | Target-definition equivalence (e.g. >50% vs ≥50% stenosis) must be settled per source | ☐ |
| F6 | Distribution shift, site effects, missingness patterns and era effects need a pre-specified plan | ☐ |
| F7 | No pooled training or pooled evaluation is permitted without an approved multi-site protocol | ☐ |
| F8 | External-validation claims remain **P-5 NOT MADE — prohibited** until completed under a frozen protocol | ☐ |

### 10.6 Sign-off block — **[BLANK]**

| Field | Value |
|---|---|
| Internal reviewer (research) | **[BLANK]** |
| Statistical reviewer | **[BLANK]** |
| Clinical reviewer / data custodian | **[BLANK]** |
| Supervisor review date | **[BLANK]** |
| Gate PT P-3 disposition | **CLOSED — no supervisor endorsement recorded** |
| Reanalysis or amendments requested | **[BLANK]** |

---

## 11. Evidence gaps — **NOT AVAILABLE TO AGENT — HUMAN REVIEW REQUIRED**

The following were not supplied in the sanitized extract, or were inaccessible because Issue #32 returned **HTTP 403** to the agent. They must be transcribed or resolved by a human before this draft can be considered complete. **None may be inferred, approximated, or invented.**

| # | Gap | Why it matters |
|---:|---|---|
| G1 | Full Issue #32 thread text, including any maintainer commentary and reviewer discussion | Cannot confirm no additional reported findings or caveats exist |
| G2 | Per-repeat values for AUPRC, accuracy, sensitivity, specificity, Brier, and confusion matrices | Only means/SDs and per-repeat AUROCs were supplied; per-fold stability is unexamined |
| G3 | Per-shuffle negative-control AUROCs and their dispersion | Only the mean (0.4882) is known; the null's spread is unknown |
| G4 | Reliability-curve bin values (`n`, mean predicted probability, observed positive fraction) | Calibration shape is unreviewed |
| G5 | ~~Twelve reported statuses vs 16 model×repeat combinations~~ — **RESOLVED:** the extraction requested calibration output only for the three non-dummy procedures (3 × 4 = 12); the prevalence-dummy curve was not extracted | No longer an experiment gap; reliability **bin values** remain a separate gap under G4 |
| G6 | Free intercepts from the joint slope/intercept calibration fits | Only offset-only CITL was supplied |
| G7 | Per-fold class counts, per-fold selected family, and inner-CV best parameters/scores | Fold-level behaviour and selection margin are unexamined |
| G8 | Software/library versions, Python version, run timestamp, run identifier | Reproducibility record not verified by the agent |
| G9 | Source SHA-256, report/predictions SHA-256, licence snapshot hash, manifest hashes | **Intentionally not requested**; protected provenance must not be copied into Git |
| G10 | Evidence that the real-source aggregate report composition path (`build_real_experiment_report`) was exercised on genuine Cleveland bytes | Previous synthetic integration testing deliberately did not cover this path |
| G11 | Local Windows runtime, NTFS ACL and console evidence beyond the reported "PASS" | Reported as PASS by the maintainer; not independently inspectable |
| G12 | Recorded pre-run amendment note for the plan-file tightening in §1.3 | Governance traceability |
| G13 | Explicit statement of whether the full `tests/experiments` suite and dry-run passed on the run commit before the real fit | Run-readiness evidence |
| G14 | Any stakeholder decision on how these results may be described outside the team | Communication/claims boundary |

---

## 12. Governance status and boundaries

| Governance item | Status |
|---|---|
| D-047 internal exploratory route | Ratified by the maintainer (PR #31) and used for this bounded run; the human authorization comment and local manifest are **not** reproduced here |
| Report label | `INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED` — **retained in this document** |
| Gate PT **P-3** (supervisor approval of a frozen pre-training protocol) | **CLOSED** |
| P-1 (final scientific target/evaluation protocol) | **PENDING** |
| P-5 (external validation / clinical readiness claims) | **NOT MADE — prohibited** |
| Clinical, deployment, diagnostic, or patient-care use | **NOT AUTHORIZED** |
| External validation | **NOT PERFORMED** |
| Pooling, other UCI-45 sites, UCI-411/412, Statlog, wearables | **OUT OF SCOPE** |
| Backend / Frontend / API contracts / model-serving behaviour | **UNCHANGED by this document** |
| Frozen protocol, registered plan, runner code, results template | **UNCHANGED by this document** |
| Protected local data, `report.json`, `predictions.csv`, signed manifests | **NOT ACCESSED, NOT REQUESTED, NOT REPRODUCED** |

This draft **does not** close any gate, record any approval, authorize any further fitting, or permit any external communication of these numbers beyond internal review.

### Standards and methodological references

- TRIPOD+AI reporting statement, *BMJ* 2024 — https://doi.org/10.1136/bmj-2023-078378
- PROBAST+AI risk-of-bias/applicability tool, *BMJ* 2025 — https://doi.org/10.1136/bmj-2024-082505
- Riley et al., sample-size guidance for prediction models, *BMJ* 2020 — https://doi.org/10.1136/bmj.m441
- scikit-learn, nested versus non-nested cross-validation — https://scikit-learn.org/stable/auto_examples/model_selection/plot_nested_cross_validation_iris.html
- scikit-learn, common pitfalls and leakage — https://scikit-learn.org/stable/common_pitfalls.html

### Related repository documents

- [D-047 internal exploratory protocol](02_d047_internal_exploratory_cleveland_PROTOCOL_PROPOSED.md) — frozen scientific method for this experiment
- [Results template (no results)](03_internal_exploratory_RESULTS_TEMPLATE.md) — structure this draft follows
- [One-decision Gate PT packet](01_first_cleveland_model_review_packet_NOT_APPROVED.md) — formal supervisor route, still not approved
- [Registered experiment plan](../../../research/experiments/cleveland_d047_exploratory_plan.v0.1.json) — machine-readable frozen configuration
- [M2c runner documentation](../../../research/experiments/README.md) — execution, safety and custody boundaries
- [Decision register](../../DECISIONS.md) — D-047 and standing gate statuses

---

**END OF REVIEW DRAFT — `INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED` — NOT SUPERVISOR APPROVED — NOT CLINICAL EVIDENCE — NOT EXTERNALLY VALIDATED**
