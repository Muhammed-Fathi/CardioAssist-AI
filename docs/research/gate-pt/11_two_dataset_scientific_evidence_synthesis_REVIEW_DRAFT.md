# Two-Dataset Scientific Evidence Synthesis — Cleveland (D-047) and UCI-412 (M3a)

> ## `INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED`
>
> - **Status:** **REVIEW DRAFT — NOT SUPERVISOR APPROVED — NOT CLINICAL EVIDENCE — NOT EXTERNALLY VALIDATED**
> - **Document type:** documentation-only scientific synthesis of two already-completed, separately
>   authorized internal exploratory benchmarks. **No experiment was run, rerun, re-scored or repeated
>   for this document.**
> - **Datasets:** (1) D-047 — UCI-45 processed Cleveland (`DA-A2`); (2) M3a — UCI-412
>   Z-Alizadeh Sani (`DA-A1`).
> - **Gate PT P-3:** **CLOSED** · **P-1:** **PENDING** · **P-5:** **NOT MADE — prohibited** ·
>   **D-046:** read-only audit only · **D-047:** Cleveland-only internal exploratory ·
>   **D-048 / M3a:** UCI-412-only internal exploratory.
> - **Prepared:** 2026-10-24 · **Repository base:** `main` at
>   `f859cf63efd31b7f88eaeeed69b5cc3606288727` (merge of PR #46, M3a Amendment A-1).
> - **Revision 1.1 (2026-10-24, on PR #47):** UCI-412 evidence completed from an additional
>   maintainer-supplied sanitized aggregate extraction of the same run (§4.1): full three-family
>   performance table, repeat-level AUROC/Brier values, repeat-level calibration slopes and
>   calibration-in-the-large intercepts with estimability statuses, and repeat-level bootstrap
>   statuses. **No bootstrap interval endpoints were supplied to the agent; this document makes
>   no claim about whether any conditional bootstrap interval was computed in the protected
>   local report (§4.5).** Gaps closed by this revision are
>   itemized in §4.9; all other evidence boundaries are unchanged.
> - **Revision 1.2 (2026-10-24, on PR #47):** editorial clarification only — the three-way
>   confidence-interval distinction in §4.5 (conditional within-repeat bootstrap intervals,
>   the four-repeat summary, and future clinical populations) is now applied consistently
>   throughout, and the §4.7 Random Forest Brier rounding note is restated as a qualified
>   possibility rather than a verified fact. No metric, conclusion, label or blocker changed.
> - **No new milestone is created or approved by this document.** The next-gate proposal in §11 is a
>   working proposal for human naming and decision only.

**This document is not medical advice, not a diagnostic claim, not a publication result, and not
evidence of supervisor, ethics, or institutional approval.** It places two internal exploratory
benchmark reports side by side so that a human scientific reviewer can see what each one establishes
on its own terms, what neither establishes, and which compatibility questions must be adjudicated
before any between-dataset question could even be formulated. It must not be used to justify
clinical deployment, patient-facing risk percentages, product accuracy claims, cross-dataset
pooling, transfer testing, or any statement that a CardioAssist model is validated.

---

## 0. Reading guide, evidence provenance and verification boundary

### 0.1 Evidence labels used throughout this document

| Label | Meaning |
|---|---|
| **[C-DOC]** | **Committed Cleveland results review.** Taken from the existing committed scientific results review, [04 — D-047 first internal results (REVIEW DRAFT)](04_d047_first_internal_results_REVIEW_DRAFT.md), which is the primary documented source for D-047 in this synthesis. Doc 04 itself labels its performance values maintainer-reported (`[MR]` there); this synthesis does not upgrade that status. |
| **[MS-U412]** | **Maintainer-supplied, sanitized UCI-412 aggregates.** Supplied by the human maintainer for this synthesis as sanitized local aggregates from the completed M3a run (§4.1). **Not independently verified by the agent** — see §0.2. |
| **[FROZEN]** | **Frozen protocol fact.** Checked by the agent against the committed frozen protocols, registered plans, feature dictionary and Gate PT documents 02 and 08–10 at the base commit above. |
| **[M2e]** | **Carried forward from the M2e.1 / M2e.2 reviews** ([05](05_m2e1_sample_size_research_ADEQUACY_REVIEW_DRAFT.md), [06](06_m2e2_dataset_compatibility_and_independent_assessment_READINESS_REVIEW_DRAFT.md)) or from the M2f Hungary conditional-readiness document ([07](07_m2f_hungary_scientific_decision_and_conditional_protocol.md)). Not re-derived here. |
| **[AA]** | **Agent-verified — arithmetic.** Recomputed by the agent from the values cited above only (no modelling, no data access). |
| **[GAP]** | **Not available to the agent / not established.** Must not be guessed, reconstructed or filled by inference. |
| **[BLANK]** | Intentionally unfilled. A named human must complete it; the agent must not prefill it. |

### 0.2 What the agent saw, and what it deliberately did not see

**Used for this synthesis:**

- Gate PT documents 01–10 in `docs/research/gate-pt/`, in particular the frozen D-047 protocol
  (doc 02), the committed D-047 results review (doc 04, primary source for Cleveland), the M2e.1
  sample-size adequacy review (doc 05), the M2e.2 compatibility / independent-assessment readiness
  review (doc 06), the M2f Hungary decision draft (doc 07), the frozen M3a specification (doc 08),
  the M3a ratification packet (doc 09) and Amendment A-1 (doc 10);
- the decision register, [`docs/DECISIONS.md`](../../DECISIONS.md) (D-046, D-047, D-048 and gates
  P-1/P-3/P-5), and [`AGENTS.md`](../../../AGENTS.md);
- the two registered, frozen machine-readable plans
  (`research/experiments/cleveland_d047_exploratory_plan.v0.1.json`,
  `research/uci412/uci412_cad_research_plan.v0.1.json`, the latter at dictionary/panel version
  1.1.0 after Amendment A-1) **[FROZEN]**;
- the maintainer-supplied sanitized UCI-412 aggregates recorded in §4.1, §4.5 and §4.6
  (including the Revision 1.1 completion extraction) **[MS-U412]**.

**Never accessed, requested, transmitted or reproduced by the agent:**

- any patient-level record, source dataset file or workbook (Cleveland, UCI-412, UCI-411, Hungary,
  or any other cohort);
- the protected local UCI-412 `report.json` or `predictions.csv`, the protected Cleveland report or
  predictions, any signed local authorization manifest, or any provenance/licence snapshot file;
- any dataset download, model fitting, inference, re-scoring, or re-analysis of any kind.

**Verification boundary for UCI-412 (explicit).** The UCI-412 performance values in §4 are
**maintainer-supplied sanitized local aggregates [MS-U412]**. The maintainer reports that the
aggregate report was human-verified locally (SHA-256 in §4.1). The agent **did not** see that
report, **did not** recompute that hash, **did not** inspect the source workbook, and **cannot and
does not claim independent verification of any protected local artifact**. The agent checked the
supplied aggregates only for (a) consistency with the frozen M3a protocol in docs 08–10 and the
registered plan, and (b) internal arithmetic coherence (§4.7). Agreement on those two checks
demonstrates coherence with the frozen method; it is **not** independent validation of the run,
the data, or the numbers.

**Verification boundary for Cleveland.** Doc 04 records that its aggregates are
maintainer-reported from a protected local run and were not independently reproduced by the agent
(doc 04 §0.1–0.3). This synthesis inherits exactly that boundary: doc 04 is the primary
*documented* source, and no value in §3 is upgraded beyond the status doc 04 gives it.

### 0.3 The one-sentence answer this document supports

> Two separately frozen, separately authorized internal exploratory benchmarks each produced a
> within-dataset, repeated nested cross-validation estimate on their own source cohort
> (Cleveland: selected-procedure AUROC 0.8271 ± 0.0097 **[C-DOC]**; UCI-412: inner-selected
> logistic-regression AUROC 0.9107 ± 0.0071 **[MS-U412]**, where each `±` is the population SD
> across four dependent repeats of the same 303 records — never a standard error or interval). The two estimates answer two different
> source-specific questions, on non-harmonized targets, with non-identical predictor panels,
> codings and case mixes. **Nothing in either benchmark, and nothing in this synthesis, is a
> between-dataset generalization result, an external validation, a ranking of the two datasets
> or models, or evidence that either procedure transports to the other cohort or to any clinical
> population.**

---

## 1. Executive synthesis

### 1.1 What was done in each benchmark (frozen designs, as executed)

Both benchmarks used the same *family* of internal-validation design — repeated stratified nested
cross-validation with training-fold-only preprocessing, a prevalence baseline, L2 logistic
regression and a constrained random forest, inner-CV model-family selection with a 0.01
AUROC simplicity preference for logistic regression, a fixed exploratory 0.5 threshold, and a
label-permutation negative control **[FROZEN]**. That design similarity is deliberate project
methodology. It does **not** make the two results a paired comparison: the cohorts, targets,
predictor panels, codings, prevalences and selection contexts all differ (§2, §6, §7).

| Dimension | D-047 Cleveland | M3a UCI-412 |
|---|---|---|
| Governance route | D-047 internal exploratory exception (Cleveland only) | D-048 / M3a internal exploratory proposal (UCI-412 only) |
| Source | UCI-45 `processed.cleveland.data` (`DA-A2`) | UCI-412 Z-Alizadeh Sani workbook (`DA-A1`) |
| Records | 303 | 303 |
| Positive / negative | 139 / 164 (`num` 1–4 / `num` 0) | 216 / 87 (`Cath` = `Cad` / `Normal`) |
| Positive fraction | 0.4587 **[AA]** | 0.7129 **[AA]** |
| Predictor panel | 5 source fields → 8 reference-coded LR slope parameters | 16 source columns → 16 encoded parameters |
| Primary reported result | Selected-procedure AUROC 0.8271 ± 0.0097 (mean ± population SD across 4 dependent repeats) **[C-DOC]** | Inner-selected logistic regression AUROC 0.9107 ± 0.0071 (same convention) **[MS-U412]** |
| Family selected | Logistic regression in 19/20 outer folds **[C-DOC]** | Logistic regression in 20/20 outer folds **[MS-U412]** |
| Calibration evidence | Descriptive OOF slope/CITL diagnostics, partly non-estimable (§3.6) **[C-DOC]** | Descriptive OOF slope/CITL diagnostics now supplied per repeat; LR/inner-selected estimable 4/4, RF 3/4; reliability-bin values still not supplied (§4.6) **[MS-U412]/[GAP]** |
| Sample-size adequacy | `NOT ASSESSED`; published Riley criteria infeasible at n = 303 under stated tolerances (§5.1) **[M2e]** | Outcome-proportion criterion `NOT_MET_AT_STATED_HALF_WIDTH` (needs 315); R²-dependent criteria `NOT ASSESSED` (§5.2) **[FROZEN]** |
| External validation | Not performed | Not performed |

### 1.2 What the synthesis concludes — and refuses to conclude

**Supported (internal, descriptive, source-specific):**

1. Each frozen pipeline ran end-to-end under its safety controls on its own cohort and produced
   internally coherent aggregate results, with discrimination descriptively above its own
   prevalence-only reference and a label-shuffle negative control descriptively consistent with
   chance (§3, §4). This is a **feasibility and engineering-validity finding with scientific
   signal worth human review**, in each dataset separately.
2. In both benchmarks the pre-registered simplicity rule selected L2 logistic regression in
   nearly all (Cleveland 19/20 **[C-DOC]**) or all (UCI-412 20/20 **[MS-U412]**) outer folds.
   Because the rule prefers logistic regression whenever its inner AUROC is within 0.01 of the
   best family, a high logistic-regression selection count is **partly a consequence of the
   rule**, not an empirical discovery of superiority (in either dataset).
3. In both benchmarks, sample-size adequacy for a clinical prediction claim is **not
   established**: Cleveland is `NOT ASSESSED` with the published criteria arithmetically
   infeasible at n = 303 under their stated tolerances **[M2e]**; UCI-412 already fails the
   R²-independent outcome-proportion criterion at its stated half-width **[FROZEN]**.

**Refused (would exceed the evidence):**

1. **No between-dataset performance comparison.** The AUROC values 0.8271 and 0.9107 must not be
   ranked, subtracted as an effect, or read as "the UCI-412 model is better". §6 explains why the
   numbers are not commensurable; doc 08 §11 already prohibits cross-dataset metric comparison,
   and this synthesis preserves that prohibition.
2. **No external validation** — in either direction, and not via Hungary, UCI-411, Statlog, VA or
   Switzerland either (§8).
3. **No pooled or combined estimate.** The two 303-record cohorts must never be summed (no
   "n = 606"), averaged, meta-analysed or pooled for training or evaluation (§7).
4. **No transportability, clinical-utility, calibration-for-practice, or readiness claim** of any
   kind. Gate PT P-3 remains **CLOSED** and P-5 remains **NOT MADE — prohibited**.

### 1.3 Recommended decision (for human reviewers; not taken here)

The smallest defensible next step is a **documentation-only human scientific review gate** over
this synthesis (§11) — named supervisor, statistician and clinician adjudication of the
compatibility blockers in §7 and of the Hungary conditional direction in §8 — with explicit
**Go / Revise / No-Go** conditions. Even a Go at that gate authorizes only the *drafting* of a
future locked-model assessment protocol for separate approval; it authorizes no data access, no
fitting, no transfer test and no validation run. The current default, until that review happens,
is **REVISE/HOLD: no between-dataset research action is ready**.

---

## 2. The two benchmarks at a glance (inventory, not comparison)

The table below is an **inventory of design facts [FROZEN]**. Placing facts in adjacent columns is
for traceability; it is not a comparison of performance and implies no equivalence.

| Element | D-047 Cleveland | M3a UCI-412 |
|---|---|---|
| Experiment / protocol ID | `CAI-T1-D047-CLEVELAND-EXPLORATORY-V0.1` | `CAI-UCI412-CAD-BENCHMARK-V0.1` (plan revision `M3A-AMENDMENT-A1`) |
| Dataset ID / UCI id | `DA-A2` / UCI-45 | `DA-A1` / UCI-412 (DOI `10.24432/C5Q31T`) |
| Source file (local, protected; never in Git) | `data/raw/uci-45/processed.cleveland.data` | `data/raw/uci-412/Z-Alizadeh sani dataset.xlsx` |
| Cohort description | Historical (1980s-era documentation, July 1988), angiography-referred Cleveland site cohort of UCI-45 **[FROZEN]/[M2e]** | Single-centre Iranian referral cohort as described in project literature material (Shahid Rajaei Hospital, Tehran — source-reported context, not stated on the UCI landing page); UCI page states no collection era **[M2e]** |
| Records / classes | 303; 139 positive, 164 negative | 303; 216 positive (`Cad`), 87 negative (`Normal`) |
| Target construct | Historical angiography-referenced **current CAD presence**: `num = 0` vs `num = 1–4` | Angiography-referenced **CAD presence** as defined by the source: `Cath` `Cad` vs `Normal` |
| Target threshold wording | `> 50%` diameter narrowing (UCI-45 `<50%` / `>50%` wording) | `≥ 50%` diameter narrowing (UCI-412 page) — **not harmonized with UCI-45; H-01 unresolved** (§7.1) |
| Not the target (both) | Future/30-day event risk, incident disease, angiographic severity grade, population prevalence, or a clinical risk score | Same |
| Predictor panel | `age`, `sex`, `cp`, `trestbps`, `restecg` (5 fields; 8 LR slope parameters after reference coding) | `Age`, `Sex`, `BMI`, `DM`, `HTN`, `Current Smoker`, `EX-Smoker`, `FH`, `DLP`, `BP`, `PR`, `Typical Chest Pain`, `Atypical`, `Nonanginal`, `Exertional CP`, `Dyspnea` (16 columns; 16 encoded parameters) |
| Panels registered but blocked | Secondary lab/exercise panels out of scope for D-047 | Resting-ECG (23 cols), expanded-clinical (28), laboratory (30) panels `REGISTERED_BLOCKED` (timing/definition evidence insufficient) |
| Key exclusions | `num`, `ca`, `thal`, catheterization/vessel fields, identifiers, site, wearables | `Cath`, `LAD`, `LCX`, `RCA`, identifiers, `Weight`/`Length`/`Obesity` (BMI redundancy), echo fields (`EF-TTE`, `Region RWMA`, `VHD`) |
| Outer resampling | Stratified 5-fold × 4 repeats, seeds `20261023`–`20261026` | Stratified 5-fold × 4 repeats, seeds `20261024`–`20261027` |
| Inner resampling | Stratified 5-fold within each outer-training partition | Stratified 5-fold within each outer-training partition |
| Preprocessing | Training-fold median imputation, LR standardization, most-frequent categorical imputation, fixed-vocabulary reference one-hot; all inside inner folds | Same contract: training-fold median / most-frequent imputation, fixed registered vocabulary, no global preprocessing |
| Model families | Prevalence dummy (`prior`), L2 logistic regression (liblinear, `C ∈ {0.1, 1, 10}`), constrained random forest (200 trees, depth `{3,5}`, leaf `{5,10}`, `sqrt`) | Identical three families and grids; gradient boosting is a reserved, unimplemented extension point |
| Selection rule | Inner-CV AUROC; logistic regression preferred if within 0.01 of best family | Identical rule (0.01 tolerance, logistic-regression simplicity preference) |
| Decision threshold | Fixed 0.5, exploratory, never tuned on outer predictions | Fixed 0.5, exploratory, threshold tuning forbidden |
| Negative control | 3 label shuffles (seeds `20262001`–`20262003`), one repeat each; smoke test, no p-value | 3 label shuffles (seeds `20262004`–`20262006`), one repeat each; AUROC ≥ 0.9 blocking alarm, ≥ 0.7 warning; smoke test, no p-value |
| Uncertainty machinery in protocol | Repeat-level descriptive dispersion only; treating 4 × 303 rows as independent explicitly forbidden | Participant-level percentile bootstrap (500) **within one repeat**, conditional on fixed fold fits; pooled-repeat inference forbidden. All four repeat-level bootstrap statuses were supplied as `ESTIMATED_CONDITIONAL_ON_FIXED_FOLD_FITS` for each listed procedure (§4.5); **the endpoints of any such conditional interval were not supplied to the agent, and whether an interval was computed in the protected report is not verified here [GAP — endpoints only]** |
| Execution environment | Maintainer-local Windows, CPU-only, $0; protected local outputs | Maintainer-local Windows, CPU-only, $0; protected local outputs |
| Full-cohort model artifact | **None saved** **[C-DOC]** | **None saved** (`artifact_saved: false` in the frozen plan) **[FROZEN]** |
| Report banner | `INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED` | `INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED` |

---

## 3. Dataset 1 — D-047 UCI-45 Cleveland (internal exploratory)

*Primary documented source: [doc 04](04_d047_first_internal_results_REVIEW_DRAFT.md) **[C-DOC]**.
Frozen design: [doc 02](02_d047_internal_exploratory_cleveland_PROTOCOL_PROPOSED.md) and the
registered plan **[FROZEN]**. Values below carry doc 04's maintainer-reported status; nothing is
re-derived from data.*

### 3.1 Source and population

UCI-45 Heart Disease (DOI `10.24432/C52P4X`), processed Cleveland file only — one of the four
named UCI-45 site cohorts (Cleveland, Hungary, Switzerland, VA Long Beach), documented in the
1988-era `heart-disease.names` **[FROZEN]/[M2e]**. The cohort is a historical,
angiography-referred diagnostic benchmark sample: 303 records, 139 positive (45.87%) and 164
negative **[C-DOC]/[AA]**. It is not a general-population, contemporary, or screening sample, and
its event fraction is a property of this historical cohort, not a prevalence estimate for any
future clinic **[M2e]**. The upstream raw Cleveland file (`cleveland.data`, 76 attributes) carries
an integrity warning and is quarantined in this project; the processed 14-column file was the
D-047 source **[FROZEN]/[M2e]**.

### 3.2 Target definition

Historical angiography-referenced **current CAD presence**, binarized as source `num = 0`
(negative, `<50%` wording) versus `num = 1–4` (positive, `>50%` wording) **[FROZEN]**. The label
is not future-event risk, not incident disease, and not an ordinal severity model; severity
modelling remains unapproved. Whether any record sits at exactly 50% narrowing, and how such a
record was coded, is not established by the source documentation (H-01, §7.1) **[M2e]**.

### 3.3 Feature panel

Five prespecified resting fields — `age`, `sex`, `cp` (chest-pain type, source codes 1–4),
`trestbps` (resting blood pressure, mm Hg), `restecg` (resting ECG result, source codes 0–2) —
chosen for input-time plausibility and audited joint availability (303/303 source-coded), **not**
by univariate association or observed performance **[FROZEN]**. Reference-coded logistic
regression over these fields has **8 slope coefficients** (age 1 + sex 1 + cp 3 + trestbps 1 +
restecg 2) **[FROZEN]**. `?` is treated as missing (six recognized missing cells in the processed
file per the merged audit **[M2e]**); missingness reasons were never recorded in UCI-45 and must
not be invented. Angiography-derived `ca`, `thal`, vessel/catheterization fields, identifiers,
site and wearable inputs are excluded **[FROZEN]**.

### 3.4 Validation procedure and model selection

Repeated nested stratified cross-validation: outer 5 folds × 4 repeats (seeds
`20261023`–`20261026`), inner 5 folds; every imputation/encoding/scaling step fitted inside the
inner folds on outer-training data only; each family tuned and scored once per outer fold; the
inner-selected procedure reuses the chosen family's outer-fold predictions (no second fit, no
assessment-fold tuning); fixed exploratory threshold 0.5 **[FROZEN]**, as executed **[C-DOC]**.
Each person contributes exactly one outer-fold prediction per repeat; the four repeats
re-partition the **same 303 records** and are not 1,212 people **[C-DOC]**.

Under the pre-registered simplicity rule (logistic regression preferred within 0.01 inner AUROC
of the best family), **logistic regression was selected in 19/20 outer folds** and the constrained
random forest in 1/20 **[C-DOC]**. The count is descriptive and partly rule-induced (§1.2).

### 3.5 Performance (within-dataset, descriptive)

Primary registered estimand — repeated nested outer out-of-fold AUROC of the complete
inner-selected procedure: **0.8271 ± 0.0097** (mean ± population SD across the four dependent
repeats) **[C-DOC]**. The `±` quantity is resampling dispersion across repeat-level scalars; it is
**not** a standard error, confidence interval, or between-population variability estimate, and no
CI, p-value or significance test is reported for any row in the committed Cleveland record
(doc 04 §4.6) **[C-DOC]**. (The UCI-412 conditional within-repeat bootstrap is a different
construction and is treated separately in §4.5; neither construction yields a valid inferential
CI for a four-repeat summary or for future clinical populations.)

| Metric (mean ± pop. SD, 4 repeats) **[C-DOC]** | Prevalence dummy | L2 logistic regression | Constrained random forest | Inner-selected procedure |
|---|---:|---:|---:|---:|
| AUROC | 0.4947 ± 0.0000 | 0.8292 ± 0.0062 | 0.8211 ± 0.0085 | **0.8271 ± 0.0097** |
| Average precision (AUPRC) | 0.4559 ± 0.0000 | 0.7737 ± 0.0151 | 0.7544 ± 0.0151 | 0.7712 ± 0.0193 |
| Accuracy @ 0.5 (exploratory) | 0.5413 ± 0.0000 | 0.7739 ± 0.0050 | 0.7492 ± 0.0096 | 0.7723 ± 0.0077 |
| Sensitivity @ 0.5 (exploratory) | 0.0000 ± 0.0000 | 0.7536 ± 0.0060 | 0.7410 ± 0.0088 | 0.7536 ± 0.0060 |
| Specificity @ 0.5 (exploratory) | 1.0000 ± 0.0000 | 0.7912 ± 0.0066 | 0.7561 ± 0.0149 | 0.7881 ± 0.0117 |
| Brier score | 0.2483 ± 0.0000 | 0.1658 ± 0.0026 | 0.1745 ± 0.0038 | 0.1671 ± 0.0049 |

Reading constraints carried from doc 04: source prevalence is 0.4587, so average precision is not
interpretable against 0.5; dummy accuracy (0.5413) equals the negative fraction by construction;
per-family rows are predeclared supportive analyses, not an unbiased winner-selection test; the
descriptive LR−RF AUROC difference (+0.0081) is comparable to one repeat-level SD and no test was
prespecified or performed **[C-DOC]/[AA]**.

Per-repeat inner-selected AUROCs: 0.8359, 0.8326, 0.8107, 0.8292 (seeds `20261023`–`20261026`)
**[C-DOC]**. Repeat differences reflect partition randomness on the same people only.

**Negative control:** three prespecified label shuffles, mean shuffled AUROC **0.4882** —
descriptively consistent with chance; no formal permutation p-value was computed, per-shuffle
values were not supplied to doc 04, and chance-consistency does not prove absence of leakage
**[C-DOC]**.

### 3.6 Calibration evidence

Calibration was assessed descriptively on out-of-fold predictions only (free intercept+slope
logistic recalibration fit as a diagnostic; calibration-in-the-large as an offset-only intercept
with slope fixed at 1; five quantile reliability bins); no recalibration was applied and no
prediction was altered **[C-DOC]/[FROZEN]**.

| Model | Mean slope (estimable repeats) | Estimable | Mean CITL (4 repeats) |
|---|---:|---:|---:|
| L2 logistic regression | 0.9105 | 3/4 | −0.0192 |
| Constrained random forest | 1.3710 | 3/4 | −0.0033 |
| Inner-selected procedure | 0.8980 | 4/4 | −0.0212 |

*(All values **[C-DOC]**.)* Two slopes were `UNSTABLE_OR_NOT_ESTIMABLE` (LR in seed `20261025`;
RF in seed `20261024`) with cause not identified — numerical non-convergence is plausible, and a
missing slope must not be described as proven overfitting or confirmed miscalibration.
Reliability-curve bin values were not reviewed (doc 04 gap G4). **Calibration quality is
unresolved**: the diagnostics neither establish nor refute usable calibration, and no clinical
calibration or risk-percentage statement may be made from them **[C-DOC]**.

### 3.7 Scientific limitations (Cleveland)

Carried from doc 04 §8 and doc 06, without dilution: retrospective cross-sectional presence
classification in one historical angiography-referred cohort; no second site, temporal split or
independent validation; repeated evaluation of the same 303 people; no inferential statistics;
calibration partly non-estimable; three-shuffle smoke-test negative control only; Riley-style
adequacy `NOT ASSESSED` (§5.1); predictor measurement timing relative to angiography not
certified; patient identity/independence not verifiable from rows and possible overlap with other
UCI-45 sites or Statlog unresolved; missingness reasons unrecorded; 1980s-era practice, referral
and coding limit any contemporary or subgroup/fairness reading; TRIPOD+AI/PROBAST+AI human
assessment pending **[C-DOC]/[M2e]**.

---

## 4. Dataset 2 — M3a UCI-412 Z-Alizadeh Sani (internal exploratory)

*Frozen design: docs [08](08_m3a_uci412_source_specific_benchmark_SPECIFICATION.md),
[09](09_m3a_uci412_internal_research_RATIFICATION_PACKET.md),
[10](10_m3a_uci412_source_encoding_AMENDMENT_A1.md) and the registered plan (dictionary/panel
1.1.0) **[FROZEN]**. Performance values: maintainer-supplied sanitized aggregates **[MS-U412]**
only — §0.2's verification boundary applies to every number in §4.5–4.6.*

### 4.1 Run identity and provenance of the reported aggregates

| Field | Value | Source |
|---|---|---|
| Run ID | `run-20261024T151846Z-4e3866dd` | **[MS-U412]** |
| Code commit of the run | `f859cf63efd31b7f88eaeeed69b5cc3606288727` (= this synthesis's base commit; merge of PR #46) | **[MS-U412]**, commit existence **[AR]** |
| Aggregate report SHA-256 (human-verified locally by the maintainer) | `3c8524ea32aaa80a2412f3a977608c7e4eb3fdfe9883a7753f3149c662726545` | **[MS-U412]** — maintainer attestation; **not recomputed by the agent** |
| Records parsed / classes | 303; 216 positive, 87 negative | **[MS-U412]**, consistent with the frozen plan's expected counts **[FROZEN]** |
| Report banner | `INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED` | **[FROZEN]** |

The digest above is recorded exactly as supplied so a human reviewer with protected local access
can match it against the local report. Its presence here proves nothing by itself: the agent did
not hold the report bytes, and a hash quoted from a maintainer message cannot be checked against
an unseen file. **No claim of independent agent verification of protected local artifacts is made
anywhere in this document.**

The protocol under which the run was executed includes Amendment A-1 (doc 10): after a first
authorized attempt failed closed **before any model fitting** on an unverified text-vocabulary
assumption, a human read-only audit established that six admitted predictors are delivered as
numeric `0`/`1`; dictionary and panel were version-bumped to 1.1.0 with an explicit numeric-binary
encoding, all other frozen parameters proven unchanged, and a new human authorization was required
before the run **[FROZEN]**. The direction of that encoding (`1` = present) is stated by
peer-reviewed secondary literature (Tao et al. 2025, Table 1) but is **not** verified against an
official dataset-owner codebook and remains provisional (residual item S-9, §7.3) **[FROZEN]**.

### 4.2 Source and population

UCI-412 Z-Alizadeh Sani (DOI `10.24432/C5Q31T`, CC BY 4.0), delivered as one workbook with 56
columns (55 predictors + `Cath`); the UCI landing page's "54 features" wording and the delivered
55-predictor shape are both recorded verbatim and never silently reconciled **[FROZEN]/[M2e]**.
Cohort: 303 participants, 216 `Cad` (71.29%) and 87 `Normal` **[MS-U412]/[AA]** — a
case-enriched, angiography-referred referral sample, not a population sample. Project literature
material describes a single-centre Iranian referral cohort (Shahid Rajaei Hospital, Tehran); the
UCI landing page itself states no collection era and no referral pathway, so centre/era statements
remain source-reported context rather than UCI-verified facts **[M2e]**. UCI-411 is the **same 303
participants** (verified same-cohort; §7.5) and is never an independent dataset **[FROZEN]/[M2e]**.

### 4.3 Target definition

Source `Cath`: `Cad` → 1, `Normal` → 0, case-sensitive, no coercion; the label is
angiography-referenced CAD presence at the source's documented **≥50%** diameter-narrowing rule
**[FROZEN]**. It is not future-event risk and carries no time horizon. The ≥50% (UCI-412) versus
>50% (UCI-45) wording difference is verified as a wording difference; whether any exact-50%
record exists in either source or how it was coded is **unresolved** (H-01, §7.1) **[FROZEN]/[M2e]**.

### 4.4 Feature panel

The single executable panel is `uci412_basic_clinical_v1` v1.1.0 — 16 ordered intake columns:
`Age`, `Sex`, `BMI`, `DM`, `HTN`, `Current Smoker`, `EX-Smoker`, `FH`, `DLP`, `BP`, `PR`,
`Typical Chest Pain`, `Atypical`, `Nonanginal`, `Exertional CP`, `Dyspnea` — 4 numeric + 12
binary/categorical → **16 encoded parameters** **[FROZEN]**. The panel was prespecified on
availability/workflow grounds before any outcome was examined; it is not outcome-selected
**[FROZEN]**. Three wider panels (resting-ECG, expanded-clinical, laboratory) are registered but
**blocked** because ECG/laboratory timing and expanded-feature definitions lack a sufficient
evidence basis; echocardiographic fields, angiography-derived fields (`Cath`, `LAD`, `LCX`,
`RCA`), identifiers and BMI-redundant fields are excluded **[FROZEN]**. Per-field definitions,
units and timing rest largely on secondary literature, not an official per-field codebook: `BP`
is a single value, probably systolic, unverified; `PR` carries the source notation "ppm",
unverified; mutual exclusivity of the chest-pain binaries is unknown (residual items S-2…S-8,
doc 09 §4, carried into §7) **[FROZEN]**.

### 4.5 Validation procedure, model selection and performance (within-dataset, descriptive)

The executed procedure is the frozen one in §2: repeated stratified nested CV (outer 5 × 4
repeats, seeds `20261024`–`20261027`; inner 5), training-fold-only preprocessing, the same three
families and grids as Cleveland, inner-AUROC selection with the 0.01 logistic-regression
simplicity preference, fixed exploratory threshold 0.5, and a 3-shuffle label-permutation
negative control **[FROZEN]**.

**Model selection:** the inner-selected procedure selected **logistic regression in 20/20 outer
folds [MS-U412]**. As in Cleveland, this count is descriptive and partly a consequence of the
pre-registered simplicity rule; it is not a superiority finding.

**Reported performance — all entries mean ± population SD across the four dependent CV repeats
[MS-U412]** (population SD, `ddof=0`, matching the aggregation convention recorded for Cleveland
in doc 04; supplied `± 0` values are written as `± 0.0000`):

| Metric | Prevalence dummy | L2 logistic regression | Constrained random forest | Inner-selected procedure |
|---|---:|---:|---:|---:|
| **AUROC** (primary metric) | 0.4913 ± 0.0000 | 0.9107 ± 0.0071 | 0.8978 ± 0.0026 | **0.9107 ± 0.0071** |
| Average precision / AUPRC | 0.7089 ± 0.0000 | 0.9504 ± 0.0077 | 0.9471 ± 0.0032 | 0.9504 ± 0.0077 |
| Accuracy @ 0.50 (exploratory) | 0.7129 ± 0.0000 | 0.8771 ± 0.0027 | 0.8350 ± 0.0062 | 0.8771 ± 0.0027 |
| Sensitivity @ 0.50 (exploratory) | 1.0000 ± 0.0000 | 0.9225 ± 0.0038 | 0.9155 ± 0.0060 | 0.9225 ± 0.0038 |
| Specificity @ 0.50 (exploratory) | 0.0000 ± 0.0000 | 0.7644 ± 0.0129 | 0.6351 ± 0.0339 | 0.7644 ± 0.0129 |
| Brier score | 0.2047 ± 0.0000 | 0.0995 ± 0.0043 | 0.1156 ± 0.0023 | 0.0995 ± 0.0043 |

**Reading notes that must accompany these numbers:**

- Source prevalence is **0.7129**; AUPRC is therefore not interpretable against 0.5, and the
  dummy's average precision (0.7089) sits at that prevalence level, as expected for a
  prevalence-only score.
- The prevalence dummy assigns every record to the majority (positive) class: its accuracy
  (0.7129) equals the positive fraction (216/303), with sensitivity 1.0000 and specificity
  0.0000 by construction **[AA]**. This is the mirror image of the Cleveland dummy (§3.5), whose
  majority class is negative — a further reason dummy rows must never be read across datasets.
- The 0.50 operating point is **exploratory only** and is **not** a patient-care threshold. It was
  fixed before fitting and never selected from outer predictions. Only 87 negative records support
  the specificity estimates (§5.2).
- The `±` values are **descriptive dispersion across four repeat-level scalars computed on the
  same 303 records**. They are not standard errors and not confidence intervals, and they carry
  no evidence about variability across patients, sites or populations. No valid inferential CI
  for this four-repeat summary, and no p-value or significance test for any row, was supplied or
  is claimed (the same constraint as doc 04 §4.6 for Cleveland). This statement is about the
  four-repeat summary: it does not deny that the frozen procedure also defines conditional
  within-repeat bootstrap intervals, whose endpoints — if computed in the protected report —
  were not supplied to the agent (§4.5).
- Per-family rows are predeclared supportive analyses, not an unbiased winner-selection test. Any
  numerical separation between the logistic-regression and random-forest rows is **descriptive
  only**: no model-comparison test was prespecified or performed, and no statistical-superiority
  statement may be made from this table.
- The inner-selected row is **identical to the logistic-regression row** because logistic
  regression was selected in 20/20 outer folds and the procedure reuses the chosen family's
  predictions **[MS-U412]/[FROZEN]**. The primary estimand is therefore not independent evidence
  additional to the logistic-regression supportive analysis.

**Repeat-level values supplied [MS-U412]** (Repeat 1–4 in supplied order; the mapping of the
supplied order to the frozen outer seeds `20261024`–`20261027` was not separately stated and is
not assumed — **[GAP]** for that mapping only):

| Repeat | LR AUROC | LR Brier | RF AUROC | RF Brier |
|---:|---:|---:|---:|---:|
| 1 | 0.9121 | 0.0953 | 0.9004 | 0.1140 |
| 2 | 0.9009 | 0.1052 | 0.8997 | 0.1158 |
| 3 | 0.9208 | 0.0954 | 0.8939 | 0.1193 |
| 4 | 0.9091 | 0.1022 | 0.8970 | 0.1135 |

The inner-selected procedure has the **same reported repeat-level performance as logistic
regression** (all rows above, both metrics) because it selected logistic regression in every
outer fold **[MS-U412]**. All four repeats reuse the same 303 records; repeat-to-repeat
differences reflect resampling/partition randomness only.

**Bootstrap status and the three-way confidence-interval distinction.** For each listed
procedure (logistic regression, constrained random forest, and — by the supplied identity — the
inner-selected procedure), all four reported repeat-level bootstrap statuses were
`ESTIMATED_CONDITIONAL_ON_FIXED_FOLD_FITS` **[MS-U412]**. Three different interval statements
must not be conflated:

1. **Conditional within-repeat bootstrap intervals (potentially computed locally; endpoints not
   supplied).** The frozen procedure defines a participant-level percentile bootstrap *within
   each repeat*, conditional on that repeat's fitted fold models **[FROZEN]**. The supplied
   statuses are consistent with that bootstrap estimation having run in the protected local
   report, so conditional bootstrap intervals **may have been computed there**. The agent has
   not seen the protected report: **no endpoint for any repeat, metric or procedure was supplied,
   and the agent neither confirms nor denies that any specific interval exists in that report,
   nor its width, coverage or contents [GAP — endpoints and local existence unverified].** No
   endpoint is reported, approximated or invented here.
2. **The four-repeat summary (no valid inferential CI available).** The headline
   mean ± population SD across the four dependent repeats (§4.5 table) is descriptive
   partition-level dispersion on the same 303 records. Because the repeats reuse the same
   participants and no person-level inferential estimator for the repeat summary was
   prespecified or supplied, **no valid inferential confidence interval for the four-repeat
   summary is available in this record** — for UCI-412 or for Cleveland. The repeat SD must
   never be repackaged as one.
3. **Future clinical populations (no CI claimed under any construction).** Even if a conditional
   interval from (1) were supplied, it would remain conditional on the fixed fold fits, would
   exclude refitting/model-selection variability, and would describe resampling within this
   historical cohort. It would **not** be a confidence interval for performance in future
   patients, other sites, or any clinical population, and no such interval is claimed anywhere
   in this synthesis.

No standard error or p-value was supplied either **[GAP]**, and the bootstrap status in (1) must
never be quoted as though an interval of type (2) or (3) had been reported.

**Negative control:** maximum shuffled AUROC across the prespecified label permutations
**0.5503**, reported by the maintainer as **nonblocking [MS-U412]**. Against the frozen protocol's
alarm (≥ 0.90) and warning (≥ 0.70) thresholds **[FROZEN]**, 0.5503 sits below both. Permitted
reading: descriptively close to the chance level expected of a correctly wired procedure on
permuted labels. Prohibited readings: that leakage is ruled out, that a formal null distribution
or p-value exists, or that the control validates the performance estimate. Per-shuffle values and
their dispersion were not supplied **[GAP]**.

### 4.6 Calibration evidence (descriptive diagnostics only)

Calibration diagnostics for the UCI-412 run are **descriptive out-of-fold diagnostics under the
frozen protocol**: a free intercept+slope logistic recalibration fit reported as a diagnostic
only, calibration-in-the-large (CITL) as an intercept-only update, and a five-bin quantile
reliability curve when estimable. No recalibration was applied and no prediction was altered
**[FROZEN]**, mirroring the definitions recorded for Cleveland (doc 04 §5.1). The joint-fit
(free) calibration **intercepts** were not supplied — only the CITL intercepts below — and must
not be confused with them **[GAP]**.

**Aggregate summary [MS-U412]**, with means recomputed by the agent from the rounded repeat-level
values below **[AA]** (estimable repeats only, for slopes):

| Model | Mean slope (estimable repeats) | Estimable | Mean CITL (4 repeats) |
|---|---:|---:|---:|
| L2 logistic regression | 1.0891 | **4/4** | 0.0206 |
| Constrained random forest | 1.5700 | **3/4** | 0.0020 |
| Inner-selected procedure | 1.0891 | **4/4** | 0.0206 |

**Per-repeat calibration [MS-U412]** (Repeat 1–4 in supplied order, as in §4.5):

| Repeat | Model | Slope | Slope status | CITL intercept |
|---:|---|---:|---|---:|
| 1 | L2 logistic regression | 1.0247 | `ESTIMATED_DESCRIPTIVE_OOF_DIAGNOSTIC` | 0.0194 |
| 1 | Constrained random forest | 1.5715 | `ESTIMATED_DESCRIPTIVE_OOF_DIAGNOSTIC` | 0.0027 |
| 1 | Inner-selected | 1.0247 | `ESTIMATED_DESCRIPTIVE_OOF_DIAGNOSTIC` | 0.0194 |
| 2 | L2 logistic regression | 0.9599 | `ESTIMATED_DESCRIPTIVE_OOF_DIAGNOSTIC` | 0.0370 |
| 2 | Constrained random forest | **— (null)** | `UNSTABLE_OR_NOT_ESTIMABLE` | −0.0041 |
| 2 | Inner-selected | 0.9599 | `ESTIMATED_DESCRIPTIVE_OOF_DIAGNOSTIC` | 0.0370 |
| 3 | L2 logistic regression | 1.2499 | `ESTIMATED_DESCRIPTIVE_OOF_DIAGNOSTIC` | 0.0001 |
| 3 | Constrained random forest | 1.5783 | `ESTIMATED_DESCRIPTIVE_OOF_DIAGNOSTIC` | 0.0040 |
| 3 | Inner-selected | 1.2499 | `ESTIMATED_DESCRIPTIVE_OOF_DIAGNOSTIC` | 0.0001 |
| 4 | L2 logistic regression | 1.1217 | `ESTIMATED_DESCRIPTIVE_OOF_DIAGNOSTIC` | 0.0257 |
| 4 | Constrained random forest | 1.5601 | `ESTIMATED_DESCRIPTIVE_OOF_DIAGNOSTIC` | 0.0054 |
| 4 | Inner-selected | 1.1217 | `ESTIMATED_DESCRIPTIVE_OOF_DIAGNOSTIC` | 0.0257 |

The inner-selected rows are the logistic-regression rows, by the same 20/20 selection identity
recorded in §4.5 **[MS-U412]**.

**Interpretive limits — mandatory wording:**

1. **These are descriptive diagnostics, not calibration findings for practice.** Slopes and CITL
   values are out-of-fold diagnostics computed once per repeat on 303 records with 216 events and
   only 87 non-events. They are not estimates of a population calibration parameter, come with no
   supplied interval, and establish neither good nor poor calibration.
2. **An estimable slope does not establish calibration**, and slope magnitudes (logistic
   regression/inner-selected around 1.02–1.25; random forest around 1.56–1.58 where estimable)
   must not be read as a clinical calibration verdict, a recalibration instruction, or a
   between-family or between-dataset superiority statement. No recalibration was performed, and
   these diagnostics were not used for fitting, threshold selection or model selection.
3. **One slope is missing, and the cause is not identified.** The random-forest slope in Repeat 2
   is `UNSTABLE_OR_NOT_ESTIMABLE` (supplied as null). As for Cleveland (§3.6), numerical
   non-convergence is a plausible explanation; a missing slope must not be described as proven
   overfitting, confirmed miscalibration or a model defect, and a null is not a zero.
4. **CITL here is the intercept-only (offset) diagnostic**, not the free intercept of the joint
   slope/intercept fit; the joint-fit intercepts remain unsupplied **[GAP]**.
5. **Reliability-curve bin values** (`n`, mean predicted probability, observed positive fraction)
   were not supplied for any repeat or procedure **[GAP]**, so the shape of calibration across the
   probability range is unreviewed.
6. **No statement about clinical calibration, risk-percentage accuracy, or the need for
   recalibration before deployment may be made from this table.** Calibration quality for UCI-412
   remains **unresolved** — now on the basis of reviewed descriptive values rather than absent
   ones, but unresolved all the same. In particular, nothing here supports a cross-dataset
   calibration comparison with §3.6: the cohorts' prevalences, panels and estimability patterns
   differ, and no such comparison is made.

### 4.7 Internal-coherence checks performed by the agent — **[AA]**

Using only the supplied aggregates **[MS-U412]** and the frozen plan **[FROZEN]**:

| # | Check | Derived | Supplied | Outcome |
|---:|---|---|---|---|
| 1 | Cohort accounting | 216 + 87 = 303 | 303 | ✅ consistent |
| 2 | Positive fraction | 216/303 = 0.71287 | prevalence 0.7129 in frozen sample-size record | ✅ consistent |
| 3 | AP reference level | a prevalence-only/no-skill AP reference equals the positive fraction ≈ 0.7129; reported LR AP 0.9504 is above it, and the dummy AP is 0.7089 | 0.9504 / 0.7089 | ✅ plausible ordering (reference arithmetic, not a run value) |
| 4 | Brier reference level | φ(1−φ) = 0.20469 → 0.2047 for a constant-prevalence forecast; the supplied dummy Brier is 0.2047 and the LR Brier 0.0995 is below it | 0.2047 / 0.0995 | ✅ consistent (the reference arithmetic now matches the run's own supplied dummy row) |
| 5 | Sensitivity/specificity vs counts | 0.9225 × 216 ≈ 199.3 and 0.7644 × 87 ≈ 66.5 — non-integers, as expected for repeat-averaged rates rather than a single confusion matrix | 0.9225 / 0.7644 | ✅ consistent with averaged aggregates; **no confusion matrix can or may be reconstructed** |
| 6 | Negative-control threshold | 0.5503 < 0.70 (warning) < 0.90 (alarm) | "nonblocking" | ✅ consistent with the frozen thresholds |
| 7 | Dummy row vs class balance | accuracy = 216/303 = 0.71287 → 0.7129 with all-positive assignment (sensitivity 1, specificity 0); dummy AUROC ≈ 0.5 | 0.7129 / 1.0000 / 0.0000 / 0.4913 | ✅ consistent |
| 8 | LR AUROC mean / population SD from the 4 supplied repeats | 0.910725 → 0.9107 / 0.007143 → 0.0071 | 0.9107 ± 0.0071 | ✅ consistent |
| 9 | LR Brier mean / population SD from the 4 supplied repeats | 0.099525 → 0.0995 / 0.004324 → 0.0043 | 0.0995 ± 0.0043 | ✅ consistent |
| 10 | RF AUROC mean / population SD from the 4 supplied repeats | 0.897750 → 0.8978 / 0.002551 → 0.0026 | 0.8978 ± 0.0026 | ✅ consistent |
| 11 | RF Brier mean from the 4 supplied (4-dp) repeats | 0.11565 from the rounded repeats, vs supplied 0.1156 | **0.1156** ± 0.0023 (supplied aggregate preserved; SD recomputes to 0.0023 ✅) | ◐ **precision-limited, not fully verifiable from the supplied values.** The recomputation differs by one unit in the last decimal. One *possible* explanation is that the supplied aggregate was computed from values held at greater precision than the 4-dp repeat values supplied to the agent; the agent cannot verify that, or distinguish it from any other rounding/aggregation pathway, from the rounded inputs alone. The supplied **0.1156** therefore stands as the authoritative **[MS-U412]** value, the recomputation is recorded only as a 4-dp sensitivity check, **no discrepancy is inferred**, and no conclusion in this document depends on the final digit |
| 12 | Inner-selected identity | LR selected in 20/20 folds ⇒ inner-selected repeats, aggregates and calibration equal the LR values | identical rows in §4.5–4.6 | ✅ consistent with the frozen reuse rule (no second fit) |
| 13 | Calibration means from the supplied repeats | LR slope 1.0891 (4/4), RF slope 1.5700 (3 estimable), LR CITL 0.0206, RF CITL 0.0020 | §4.6 table | ✅ consistent as **[AA]** arithmetic on rounded inputs; not run-supplied aggregates |
| 14 | Bootstrap statuses vs interval supply | statuses `ESTIMATED_CONDITIONAL_ON_FIXED_FOLD_FITS` (4/4 per listed procedure); **no endpoint appears anywhere in the supplied extraction** | §4.5 | ✅ internally consistent as a statement about the *supplied extraction*. It is **not** a claim that no conditional bootstrap interval was computed in the protected local report — the agent cannot verify that (§4.5, distinction 1); the unsupplied endpoints are recorded as a gap, not filled |

**What these checks establish:** the supplied aggregates are arithmetically coherent with each
other and with the frozen protocol's counts and thresholds, at the precision of the supplied
values. Check 11 marks the limit of that precision: a last-decimal recomputation difference that
the rounded inputs cannot adjudicate, which is recorded as a qualified possibility and left with
the supplied aggregate (**0.1156**) authoritative — it is not resolved in either direction here.
**What they do not establish:** that
the run occurred as reported, that the protected report matches these values or the quoted hash,
or that the numbers are free of data-level or design-level bias. That verification remains with
the maintainer and any human reviewer with protected local access (§0.2).

### 4.8 Scientific limitations (UCI-412)

Single source cohort; retrospective cross-sectional angiography-referenced presence, not
future-event risk; no independent validation; repeated evaluation of the same 303 participants;
the supplied dispersion is **repeat-level population SD across four dependent repeats only** —
no standard error, p-value, or valid inferential confidence interval for the four-repeat summary
was supplied, and the endpoints of any conditional within-repeat bootstrap interval (which may
have been computed in the protected local report) were not supplied to the agent (§4.5's
three-way distinction); calibration is descriptive-only with one non-estimable RF slope, unsupplied
joint-fit intercepts and unsupplied reliability-bin values, so calibration quality is unresolved
(§4.6); negative control is a three-shuffle smoke test without per-shuffle values; sample-size
status `NOT_MET` / `NOT ASSESSED` (§5.2) with only 87 records in the minority (negative) class;
target threshold wording unreconciled with UCI-45 (H-01); predictor definitions, `BP`/`PR` units,
chest-pain exclusivity, and ECG/laboratory/echo timing unresolved (S-2…S-8); the six numeric-binary
directions provisional without an official codebook (S-9); per-field timing relative to
angiography not certified for any panel field, so no prospective pre-catheterization claim;
participant independence cannot be proven from an identifier-free source, and UCI-411 is the same
cohort, so no internal "replication" exists; the 54-vs-55 feature-count discrepancy is unresolved;
TRIPOD+AI/PROBAST+AI human assessment pending **[FROZEN]/[M2e]**.

### 4.9 Evidence-gap closure record for UCI-412 (Revision 1.1)

Revision 1.1 closed **only** the gaps that the additional maintainer-supplied aggregates
**[MS-U412]** directly support. Everything else remains an honest gap.

**Closed by the supplied aggregates:**

| Gap (Revision 1.0 wording) | Now recorded |
|---|---|
| "Other families: no prevalence-dummy or random-forest aggregate supplied" | Full dummy / LR / RF / inner-selected table, §4.5 |
| "Dispersion/uncertainty: no per-repeat values or repeat-level SD supplied" | Mean ± population SD for all six metrics and all four procedures, plus per-repeat AUROC and Brier for LR, RF and (by identity) inner-selected, §4.5 |
| "No numeric calibration quantity supplied" | Per-repeat slopes, slope statuses and CITL intercepts for LR, RF and inner-selected; estimability 4/4 (LR, inner-selected) and 3/4 (RF), §4.6 |
| Bootstrap status unknown | All four repeat-level statuses `ESTIMATED_CONDITIONAL_ON_FIXED_FOLD_FITS` for each listed procedure, §4.5 |

**Preserved as genuine gaps (not supplied; not invented):**

| Gap | Why it still matters |
|---|---|
| Bootstrap **interval endpoints** (every repeat, metric and procedure) — not supplied to the agent | Conditional within-repeat bootstrap intervals may have been computed in the protected local report (the supplied statuses are consistent with the bootstrap estimation having run), but the agent has not seen that report and can neither confirm nor deny any specific interval's existence or contents. Without endpoints the conditional bootstrap cannot be quoted, interpreted or compared |
| Any standard error or p-value; any valid inferential CI for the four-repeat summary or for future clinical populations | No inferential statement of that kind is available for UCI-412 (or Cleveland). This is a statement about the repeat summary and about future populations (§4.5, distinctions 2–3); it does not deny that conditional within-repeat intervals of type (1) may exist locally |
| Five-bin **reliability-curve values** | Calibration *shape* across the probability range is unreviewed |
| **Joint-fit (free) calibration intercepts** | Only offset-only CITL intercepts were supplied; the two must not be conflated |
| **Per-shuffle** negative-control AUROCs and their dispersion | Only the maximum (0.5503) is known; no null distribution can be characterized |
| Mapping of supplied Repeat 1–4 order to frozen outer seeds `20261024`–`20261027` | Repeat-level values cannot yet be tied to named seeds in this document |
| Per-repeat values for AP, accuracy, sensitivity and specificity; per-fold class counts, selected family per fold and inner-CV best parameters/scores | Fold-level behaviour and selection margins remain unexamined (the 20/20 aggregate count is supplied; its per-fold composition is not) |
| Software/library versions, run timestamp beyond the run ID, and any protected provenance/manifest hash | Reproducibility custody remains maintainer-held; the agent verified none of it (§0.2) |

---

## 5. Sample-size and precision status of the two benchmarks

Development sample-size adequacy and future validation precision are different questions with
different methods (M2e.1 §10 **[M2e]**). Neither benchmark's status licenses the other's.

### 5.1 Cleveland — `NOT ASSESSED — PENDING HUMAN REVIEW` **[M2e]**

From doc 05 (Riley binary-outcome criteria, reproduced against the published worked examples):

- the **outcome-proportion criterion** (C3, half-width δ = 0.05) requires **382** participants at
  φ = 0.4587 — independent of R² and of parameter count, so the published three-criterion set
  **cannot be met at n = 303 for any anticipated R²**;
- the additional approximate MAPE criterion requires **459** at p = 8;
- criterion 1 (shrinkage ≥ 0.90) is met at n = 303 only for anticipated Cox–Snell R² ≥ ≈ 0.2088421
  (strict-ceiling break-even, doc 05 §5.5);
- **no eligible externally anticipated Cox–Snell R² was identified** in the examined sources
  (extraction-level screen of the 25 supervisor-classified papers plus three external CAD
  studies; not a literature-wide absence claim), and back-deriving one from observed D-047
  performance is prohibited as circular;
- therefore the formal status stays **`NOT ASSESSED — PENDING HUMAN REVIEW`**, and under the frozen
  protocol's own wording the D-047 result is a **feasibility pilot only**. Any relaxation of a
  criterion or tolerance is a documented human decision, not an agent finding.
  Events-per-parameter (139/8 ≈ 17.4) is descriptive arithmetic, never a justification **[M2e]**.

### 5.2 UCI-412 — `NOT_MET_AT_STATED_HALF_WIDTH`; R²-dependent criteria `NOT ASSESSED` **[FROZEN]**

From doc 08 §10 / doc 09 §5 (audited class counts only, recorded before the run):

- the Riley **outcome-proportion criterion** at half-width 0.05 requires **n = 315** at
  φ = 0.7129 → at n = 303 the criterion is **`NOT_MET_AT_STATED_HALF_WIDTH`**;
- shrinkage, optimism and MAPE criteria are **`NOT ASSESSED`** — they require a human-reviewed
  anticipated Cox–Snell R², which must not be back-derived from the observed 0.9107;
- events per parameter is 216/16 = **13.5** descriptively **[AA]**, but the **minority class is
  the 87 negative records** (87/16 ≈ 5.4 per parameter **[AA]**), which is the binding precision
  constraint for specificity and for calibration in the negative range; neither ratio is a
  sample-size justification.

### 5.3 Consequence for this synthesis

Both cohorts have the same total (303) by coincidence of source construction. **Equal n is not
compatibility**: the event fractions (0.4587 vs 0.7129), parameter counts (8 vs 16), minority-class
sizes (164 vs 87) and criterion outcomes differ, and each benchmark is, on its own terms, below or
unassessed against the published development criteria. No adequacy claim, and no
"the two samples balance each other" claim, is available. Any future *validation* sizing would
additionally require the Riley et al. 2021 external-validation inputs (target standard errors,
validation-population event fraction, anticipated miscalibration / linear-predictor variance) for a
named locked model and population — none of which exists yet for any candidate (§8) **[M2e]**.

---

## 6. Within-dataset performance versus between-dataset generalization

This distinction is the scientific centre of the synthesis.

| Question | What it asks | Which evidence answers it |
|---|---|---|
| **Within-dataset (internal) performance** | How does the complete frozen procedure — preprocessing, tuning, family selection — perform on *new records from the same source distribution*, as estimated without touching assessment folds during selection? | Each benchmark's repeated nested-CV estimate, **on its own cohort only**: Cleveland 0.8271 ± 0.0097 **[C-DOC]**; UCI-412 0.9107 ± 0.0071 **[MS-U412]** (each `±` the population SD across four dependent repeats). Even here, "new records" means new draws from the same historical referral process, and repeated CV reuses the same 303 people, so the estimate carries no between-population variability (§3.5, §4.5). |
| **Between-dataset generalization / transportability** | How does a *single locked* model, developed in one place, perform when applied unchanged to records from a *different* source, population, era or referral pathway? | **Nothing in this project.** No model was locked and applied across datasets; no full-cohort artifact exists from either benchmark; no cross-dataset prediction was generated. Neither within-dataset estimate — however high — is evidence about this question. |
| **External validation** | A between-dataset assessment conducted under a separately frozen protocol, with the model locked beforehand, pre-specified estimands and precision targets, and independence/target-compatibility adjudicated in advance (M2e.2 §7) **[M2e]**. | **Not performed, not authorized, not claimed (P-5 prohibited).** |

Why the two AUROC values cannot be compared even descriptively as performance:

1. **Different targets.** `num` 0 vs 1–4 at a >50% wording (Cleveland) versus `Cad`/`Normal` at a
   ≥50% wording (UCI-412), with exact-50% existence/coding unresolved in both (H-01). The
   constructs are related; identity is unproven (§7.1).
2. **Different information.** An 8-parameter panel of 5 resting fields versus a 16-parameter panel
   of 16 intake fields. Discrimination rises mechanically with predictor information; the panels
   also *encode chest pain differently* (one 4-level source variable vs four separate binaries),
   so there is no common predictor space in which the two procedures were ever both expressed.
3. **Different case mix and spectrum.** Positive fractions 0.4587 vs 0.7129, different referral
   pathways, eras and measurement conventions. AUROC is prevalence-independent in construction but
   **not** case-mix/spectrum-independent; AP, Brier, sensitivity and specificity at 0.5 are
   additionally prevalence- and threshold-context-dependent. Identical procedures routinely show
   different AUROCs across spectra without either being "better".
4. **No inferential uncertainty on either side.** Both benchmarks report the same descriptive
   quantity — population SD across four dependent repeats of the same 303 people — which is not a
   standard error or confidence interval in either case, and neither four-repeat summary has a
   valid inferential CI in this record. UCI-412 additionally carries conditional-bootstrap
   *statuses*; whether conditional within-repeat intervals were computed in the protected report
   is unverified and their endpoints were not supplied (§4.5), while no bootstrap interval is
   reported for Cleveland in doc 04. Even a supplied conditional interval would not be an
   interval for the four-repeat summary or for future populations. Neither side therefore has a
   usable inferential interval estimate for comparison, and two point quantities without
   commensurable inferential statements cannot be ranked.
5. **Selection-context difference.** Each AUROC is the estimate of a *selection procedure*
   (including the 0.01 simplicity rule) tuned within its own data. A cross-dataset ranking of two
   procedure-estimates, each optimistic/pessimistic in its own unknown way, has no estimand.

**Permitted descriptive statement (the most this synthesis allows):** "Two internal exploratory
benchmarks, run under deliberately similar nested-CV methodology on two different source cohorts,
reported within-dataset AUROCs of 0.8271 (Cleveland selected procedure) and 0.9107 (UCI-412
inner-selected logistic regression), each above its own prevalence reference and each with a
chance-consistent label-shuffle control; the values are not commensurable and no ordering,
difference, or transportability conclusion follows."

**Prohibited statements (non-exhaustive):** "UCI-412 outperforms Cleveland"; "the model
generalizes"; "externally validated"; "the UCI-412 result confirms the Cleveland result" (the
cohorts test different panels against differently worded targets — neither is a replication of the
other); "combined accuracy"; any pooled or averaged metric; any statement selecting a future
assessment cohort *because* its within-dataset number looks favourable (M2e.2 §7.4 **[M2e]**).

---

## 7. Compatibility blockers to any between-dataset question

Each blocker is stated with its current disposition. **All six must be adjudicated by named humans
before a between-dataset estimand can even be defined**; none is resolved by this document.

### 7.1 Target-definition compatibility — **UNRESOLVED (H-01)**

UCI-45 documents `<50%` / `>50%`; UCI-412 documents `≥50%`. The wording difference is verified; the
existence and coding of exact-50% records in either source is not established and cannot be
established from the released fields (no per-record stenosis percentage exists). Additionally,
Cleveland's source target is a 0–4 `num` scale binarized as 0 vs 1–4, while UCI-412's is a direct
binary `Cath`; UCI-45 sibling-site processed targets (e.g. Hungary 0/1) raise their own
raw-to-processed recoding questions (§8). Permitted human dispositions (from the Gate DA register):
*identical / reconciled / related-but-not-identical / unresolved*. Until a ruling exists: no common
endpoint may be asserted, no pooling, and any future cross-source result could at most be described
as performance across *related labels whose boundary compatibility is unresolved* **[M2e]**.

### 7.2 Predictor-availability compatibility — **UNRESOLVED / HUMAN DECISION REQUIRED**

The panels intersect only conceptually (age, sex, a blood-pressure field, chest-pain information).
Cleveland's `cp` is one 4-category variable; UCI-412 spreads chest-pain characterisation over
`Typical Chest Pain`, `Atypical`, `Nonanginal`, `Exertional CP` as separate binaries whose mutual
exclusivity is unknown. UCI-412's panel adds BMI, diabetes/hypertension/smoking/family-history/
dyslipidaemia history and dyspnea, which have no Cleveland-panel counterpart; Cleveland's `restecg`
has no counterpart in the executable UCI-412 panel (UCI-412 ECG fields sit in a **blocked** panel).
No common frozen feature space, mapping, or missing-input/abstention rule exists. Availability at a
claimed decision timepoint is asserted on workflow plausibility in both protocols but certified by
neither source **[FROZEN]/[M2e]**.

### 7.3 Coding and unit compatibility — **UNRESOLVED**

Cleveland: `sex` 0/1, `cp` 1–4, `restecg` 0–2, `trestbps` in mm Hg per the UCI-45 documentation.
UCI-412: `Sex` as `Male`/`Fmale` text; six history/symptom fields as numeric `0`/`1` whose
*direction* rests on peer-reviewed secondary literature, not an official codebook (S-9, doc 10);
five text binaries; `BMI` in kg/m²; `BP` single-value, "probably systolic", unverified; `PR` source
unit "ppm" unverified. Column-name similarity is not coding equivalence; no verbatim
source-to-canonical coding map for any cross-dataset feature pair has been human-approved, and
Amendment A-1 is itself the demonstration of why: an unverified vocabulary assumption, reasonable
on its face, was wrong for six of twelve fields and was caught only by a fail-closed guard
**[FROZEN]**.

### 7.4 Measurement-timing compatibility — **NOT ASSESSED**

Neither released source carries per-record measurement dates. The UCI-45 cohorts are 1980s-era;
UCI-412's collection era is not stated on its landing page. No record-level chronology can
demonstrate that any predictor preceded angiography in either cohort, so a shared prospective
"pre-angiography decision moment" — the prediction timepoint a transportability claim would need —
is currently a design aspiration, not an evidenced property of either dataset. Frozen P-1 (final
target, population and prediction moment) is still **PENDING** **[M2e]**.

### 7.5 Patient-overlap and independence — **UNRESOLVED (with one VERIFIED prohibition)**

- **UCI-411 = UCI-412: VERIFIED same 303 participants** (official extension provenance plus
  303/303 aggregate correspondence on 56 shared columns, with one unresolved `Cath`/artery
  discordance). UCI-411 can never validate UCI-412, and the pair can never be counted as 606
  participants **[M2e]**.
- **Cleveland ↔ UCI-412:** different named source cohorts; **participant-level independence has
  not been established** and cannot be proven from identifier-free releases. "Different dataset"
  is not an independence proof (doc 08 §11) **[FROZEN]**.
- **Within UCI-45 and Statlog:** cross-site duplicates cannot be ruled out from listings; Statlog
  is a suspect Cleveland duplicate with unresolved overlap; raw/processed files are
  representations, not extra cohorts **[M2e]**.
- Neither benchmark's rows carry identifiers, so overlap adjudication can only ever be a bounded,
  privacy-preserving aggregate argument — which has not been performed for the Cleveland↔UCI-412
  pair.

### 7.6 Sample-size and precision compatibility — **NOT ASSESSED / NOT MET**

§5 in full: Cleveland `NOT ASSESSED` with the published criteria infeasible at n = 303 under
stated tolerances (382 / 459); UCI-412 `NOT_MET_AT_STATED_HALF_WIDTH` (315) with R²-dependent
criteria `NOT ASSESSED` and a minority class of 87. A future between-dataset assessment would need
its own Riley-2021 precision calculation for a named locked model — target SEs/CI widths, expected
event fraction, anticipated miscalibration and linear-predictor variance — none of which can be
computed today because there is no locked model, no adjudicated target, and no approved precision
target **[M2e]**. Equal totals (303 = 303) contribute nothing toward compatibility.

### 7.7 Further structural incompatibilities (recorded for completeness)

Referral/spectrum structure differs (both cohorts are angiography-referred and case-enriched, but
through different pathways and eras, so a second angiography cohort would reproduce, not remove,
selection effects); missingness structure differs (Cleveland `?`-coded with unrecorded reasons;
UCI-412 reported as having no missing values under its audit rules); and measurement devices,
assay conventions and clinical practice differ across the decades separating the sources. These
are effect-modifiers of any transportability claim, not footnotes **[M2e]**.

**Summary of §7:** target — UNRESOLVED; predictor availability — UNRESOLVED; coding/units —
UNRESOLVED; timing — NOT ASSESSED; overlap — UNRESOLVED (one same-cohort prohibition VERIFIED);
precision — NOT ASSESSED/NOT MET. **No between-dataset analysis of any kind is currently
definable, let alone authorized.**

---

## 8. What the existing conditional-readiness work already says (M2e.1, M2e.2, M2f Hungary)

This synthesis **incorporates** the following findings; it does not re-decide them.

### 8.1 M2e.1 (doc 05) — development sample-size adequacy

Status `NOT ASSESSED — PENDING HUMAN REVIEW` (§5.1). Two governance findings bear directly on any
next gate: the `gate-da/15` vs frozen-protocol sequencing inconsistency on *when* the Riley
analysis must exist (before execution vs in the first report) remains for human resolution (doc 05
Q10), and the Riley framework supplies **development** sizing only — it must never be quoted as a
validation sample size **[M2e]**.

### 8.2 M2e.2 (doc 06) — compatibility and independent-assessment readiness

No candidate source is `READY`, `VALIDATED` or `APPROVED` for independent assessment; every
candidate (Cleveland, Hungary, Switzerland, VA, UCI-412) is at most a **CONDITIONAL CANDIDATE —
NOT READY**, UCI-411 is **EXCLUDED FOR THIS PURPOSE** (same cohort as UCI-412), and Statlog is
**EXCLUDED FOR THIS PURPOSE** until overlap is evidenced **[M2e]**. The eight prerequisites for a
future external assessment (doc 06 §7.1) — outcome compatibility, cohort independence, frozen
prediction moment, feature/missingness compatibility, leakage protection, case-mix framing,
precision feasibility, one-shot evaluation — are adopted here as the blocker framework behind §7
and §11. M2e.2 also records that D-047's result must not be used to *choose* a favourable
assessment cohort; §6 of this synthesis extends the same prohibition to the UCI-412 result: **the
0.9107 within-dataset value is not a reason to prefer UCI-412 as a future assessment population,
and the 0.8271 Cleveland value is not a reason to prefer or avoid any other cohort [M2e]**.

### 8.3 M2f Hungary (doc 07) — conditional site-shift direction

Current disposition: **CONDITIONAL CANDIDATE — NOT READY; HOLD / DEFER is the default.** The
recommended working direction is Strategy B — *preserve* Hungary (294 records; 188 negative / 106
positive; five resting fields jointly observed in 292/294 **[M2e]**) as a possible **one-shot
site-shift assessment of a future locked Cleveland model**, rather than training a separate
Hungary model (Strategy A, not selected) **[M2e]**. Binding conditions carried into §11:

- Hungary must not be used to choose features, preprocessing, model family, hyperparameters,
  calibration or threshold; any such use converts it into development data and voids the
  independent-assessment interpretation;
- **no locked Cleveland artifact exists** — D-047 saved none — so the assessment question cannot
  be executed until a separately approved Cleveland development-and-freeze step creates one;
- Hungary-specific prerequisites remain open: UCI-45 sibling-site outcome-coding/reference-standard
  compatibility (including raw 0–4 → processed 0/1 recoding; the cross-family H-01 ruling is not
  assumed to govern this pair), five-field coding/unit map, timing, overlap adjudication,
  missingness/abstention rule, and a statistician's precision-feasibility ruling;
- UCI-412 does not displace, merge with, or get compared against this Hungary direction. The
  Hungary question is a *within-UCI-45-family* site-shift question about a future locked Cleveland
  model; the UCI-412 benchmark is a *separate-source development* question. Conflating them
  (e.g. "validate the UCI-412 model on Hungary") would require its own target/coding adjudication
  under §7 and is not proposed here.

Switzerland (123 records, only 8 source-negative) may be **not evaluable** for conventional
discrimination/calibration estimands and VA (200 records; 51 negative / 149 positive) remains a
conditional candidate under the same conditions; both are recorded in doc 06/07 and are not
re-decided here **[M2e]**.

---

## 9. Observed evidence, uncertainty, unresolved questions, and decisions

The four categories are kept strictly separate, per the synthesis mandate.

### 9.1 Observed evidence (what the record actually contains)

| # | Observation | Label |
|---|---|---|
| O1 | Cleveland: n = 303 (139/164); frozen 5-field/8-parameter nested-CV procedure executed; selected-procedure AUROC 0.8271 ± 0.0097; LR 19/20 folds; negative-control mean 0.4882; calibration slopes estimable in 3/4 (LR), 3/4 (RF), 4/4 (selected) repeats | **[C-DOC]** |
| O2 | UCI-412: n = 303 (216/87); frozen 16-column/16-parameter nested-CV procedure executed under Amendment A-1; full three-family table supplied (dummy AUROC 0.4913; LR 0.9107 ± 0.0071; RF 0.8978 ± 0.0026; inner-selected = LR, 20/20 folds) with per-repeat AUROC/Brier; calibration slopes estimable 4/4 (LR/inner-selected) and 3/4 (RF), CITL supplied per repeat; bootstrap statuses `ESTIMATED_CONDITIONAL_ON_FIXED_FOLD_FITS` 4/4 per listed procedure, **endpoints not supplied to the agent (local computation unverified, §4.5)**; max shuffled AUROC 0.5503 (nonblocking) | **[MS-U412]** |
| O3 | Both procedures descriptively exceed their own prevalence references and show chance-consistent label-shuffle controls | **[C-DOC]/[MS-U412]** |
| O4 | Both sample-size statuses are non-adequate on current evidence (Cleveland `NOT ASSESSED`, criteria infeasible at stated tolerances; UCI-412 `NOT_MET` 315, R² criteria `NOT ASSESSED`) | **[M2e]/[FROZEN]** |
| O5 | UCI-411 and UCI-412 are the same 303 participants (303/303 aggregate correspondence; one discordance unresolved) | **[M2e]** |
| O6 | Neither benchmark saved a full-cohort model artifact; neither performed any external, temporal, or cross-dataset evaluation | **[C-DOC]/[FROZEN]** |
| O7 | The UCI-412 source-encoding failure (first attempt) was caught pre-fitting by a fail-closed guard and corrected only via a versioned amendment, new hashes and a new human authorization requirement | **[FROZEN]** |

### 9.2 Uncertainty (quantified limits on O1–O2; not ignorance)

| # | Uncertainty | Consequence |
|---|---|---|
| U1 | Cleveland `± 0.0097` is dispersion across 4 dependent repeats of the same 303 people — not an SE or CI | No significance, ranking or "±" interval interpretation, even within Cleveland |
| U2 | UCI-412 dispersion is now supplied, but it is the **same limited quantity** as Cleveland's: population SD across 4 dependent repeats of the same 303 people. The within-repeat bootstrap carries `ESTIMATED_CONDITIONAL_ON_FIXED_FOLD_FITS` statuses (4/4 per listed procedure); **no endpoint was supplied to the agent**, and whether conditional intervals were computed in the protected report is unverified. Separately, no SE, p-value, or valid inferential CI **for the four-repeat summary or for future clinical populations** is available on either dataset (§4.5, distinctions 1–3) | Partition-level stability is now described for AUROC/Brier, but neither dataset has a valid inferential interval for its repeat summary or for future populations. The bootstrap status must never be quoted as if such an interval had been reported, nor as proof that no conditional interval exists locally; conditional-on-fixed-folds estimation would in any case exclude refitting variability |
| U3 | Cleveland calibration: 2/12 family-repeat slopes non-estimable, cause unidentified; reliability-bin values unreviewed; CITL is offset-only | Calibration quality unresolved; no recalibration need or sufficiency can be inferred |
| U4 | UCI-412 calibration: per-repeat slopes/CITL now supplied (LR/inner-selected estimable 4/4, mean slope 1.0891; RF estimable 3/4, mean slope 1.5700, Repeat-2 slope `UNSTABLE_OR_NOT_ESTIMABLE` with unidentified cause); reliability-bin values and joint-fit intercepts still unsupplied; no calibration-diagnostic interval was supplied (and no such interval is claimed for either dataset) | Calibration quality remains unresolved — now reviewable as descriptive values, but a slope near or above any particular value is not a clinical calibration verdict, and calibration *shape* cannot be assessed without the reliability bins |
| U5 | Both negative controls are 3-shuffle smoke tests (Cleveland per-shuffle values and UCI-412 per-shuffle distribution unsupplied) | Chance-consistency is reassuring wiring evidence, never a leakage exclusion or a p-value |
| U6 | Adequacy criteria are conditional on tolerances (S = 0.90, δ = 0.05, MAPE = 0.05) and on cohort event fractions that are not target-population prevalences | "Infeasible at n = 303" is a statement about the published criteria at stated tolerances, not a clinical-performance verdict (doc 05) |
| U7 | AP/Brier/sensitivity/specificity are prevalence- and threshold-context-dependent; AUROC is spectrum-dependent | Cross-cohort juxtaposition of any secondary metric is even less interpretable than of AUROC (§6) |

### 9.3 Unresolved scientific questions

| # | Question | Where owned |
|---|---|---|
| Q-a | H-01: are the >50% and ≥50% targets identical, reconciled, related-but-not-identical, or unresolved — per dataset pair? Does any exact-50% record exist? | §7.1; doc 06 A3 |
| Q-b | Can a single prediction moment be defined and evidenced for both sources (per-feature availability before angiography)? (P-1) | §7.4; doc 06 A1–A2 |
| Q-c | Can verbatim coding/unit maps be human-approved for any cross-dataset feature pair — including S-9 (UCI-412 numeric-binary direction without an official codebook), `BP` systolic status, `PR` unit, chest-pain exclusivity (S-2…S-8)? | §7.2–7.3; doc 10 |
| Q-d | What privacy-preserving aggregate evidence could ever bound Cleveland↔UCI-412 (and UCI-45 cross-site / Statlog) patient overlap, given identifier-free releases? | §7.5; doc 06 A6–A7 |
| Q-e | Is an eligible externally anticipated Cox–Snell R² obtainable (full-text or elicitation route) for either panel — or is `NOT ASSESSED` the permanent honest status at n = 303? | §5; doc 05 Q4 |
| Q-f | Will the maintainer supply, through a future reviewed supplement of already-computed aggregates (never a re-run), the UCI-412 evidence that remains missing: bootstrap **interval endpoints**, reliability-bin values, joint-fit calibration intercepts, per-shuffle control values, the Repeat 1–4 ↔ seed mapping, and per-repeat AP/accuracy/sensitivity/specificity? (§4.9) | §4.5, §4.6, §4.9 **[GAP]** |
| Q-g | Are Cleveland's unsupplied per-fold details (doc 04 G2/G7) and UCI-412's per-fold class counts / inner-CV best parameters needed for supervisor review, and through what protected channel? The UCI-412 family-aggregate part of this question is **closed** by Revision 1.1 (§4.9). | doc 04 §11; §4.9 |
| Q-h | Hungary: can sibling-site target recoding, five-field map, overlap and precision all be adjudicated favourably — and if not, is the disposition DEFER or NO-GO? | §8.3; doc 07 §4 |
| Q-i | Would any future locked-model assessment be precise enough at the available minority-class counts (Hungary 106 events/188 non-events; UCI-412-as-assessment 87 non-events; Switzerland 8 non-events) under Riley-2021 targets set *before* seeing results? | §7.6; doc 06 A9 |

### 9.4 Decisions requiring supervisor / named-human review (none taken here)

| # | Decision | Required decider(s) |
|---|---|---|
| D-a | Accept, revise, or reject this synthesis as the project's two-dataset evidence record | Supervisor + research lead |
| D-b | P-1: freeze (or explicitly defer) the scientific target, population and prediction moment | Research lead + supervisor (Gate PT) |
| D-c | H-01 ruling per dataset pair (Q-a), recorded in the governed register | Supervisor + clinician/statistician |
| D-d | Whether S-9 and S-1…S-8 residual semantics are acceptable for any *future* UCI-412 work, given no official codebook exists | Maintainer + supervisor |
| D-e | Sample-size disposition for both benchmarks: ratify tolerances, record any relaxation with rationale, or confirm feasibility-pilot-only status (doc 05 Q1–Q5) | Supervisor + statistician |
| D-f | Whether any between-dataset research question should be pursued at all — and if so whether the vehicle is the Hungary site-shift direction (doc 07), a UCI-412-as-assessment question, or neither | Supervisor + research lead |
| D-g | If pursued: approval of the §11 gate's Go conditions, including the precision-feasibility ruling and the one-shot rule | Supervisor + statistician + data custodian |
| D-h | Ownership and timing of a formal TRIPOD+AI checklist and assessor-led PROBAST+AI review for any eventual study | Independent assessors (named humans) |
| D-i | Disposition of doc 05's open items that this synthesis inherits (Q10 sequencing inconsistency; Q11 verification-script scope) | Maintainer + supervisor |

---

## 10. Claims discipline for this synthesis

| Claimed | Not claimed |
|---|---|
| Two frozen internal exploratory benchmarks were executed, one per dataset, under `INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED`, with the within-dataset aggregates in §3.5–3.6 and §4.5–4.6 as labelled (descriptive calibration diagnostics included; bootstrap statuses supplied without endpoints — local interval computation unverified, and no valid inferential CI for any four-repeat summary or future population is claimed) | Any between-dataset comparison, ranking, difference, pooled estimate or meta-analytic combination |
| The aggregates are coherent with the frozen protocols (§4.7; doc 04 §6 for Cleveland) | Independent agent verification of the protected UCI-412 report, its quoted SHA-256, the source workbook, or any patient-level artifact |
| Sample-size adequacy is not established for either benchmark, on the stated published criteria | That either benchmark is "underpowered" as a clinical verdict, or adequate under any relaxed tolerance (no relaxation has been human-approved) |
| Six named compatibility blockers (§7) currently prevent defining a between-dataset estimand | That the blockers are permanently insurmountable, or that any dataset is `READY`/`VALIDATED`/`APPROVED` for assessment |
| Hungary remains a conditional, preserved site-shift candidate under doc 07's conditions | Any Hungary evaluation, model lock, or comparison; any displacement of Hungary by UCI-412 (or vice versa) based on within-dataset AUROCs |
| A smallest defensible next gate is proposed in §11 with Go/Revise/No-Go conditions | That the gate exists, is approved, is named in the decision register, or authorizes anything — including this document's own acceptance |

Governance invariants preserved by this document: **Gate PT P-3 CLOSED; P-1 PENDING; P-5 NOT MADE —
prohibited; D-046 read-only; D-047 Cleveland-only; D-048 UCI-412-only; no decision-register entry
added or changed; no frozen protocol, plan, dictionary, runner, result, or status modified; no new
milestone invented.** Supervisor, ethics and institutional approval are neither obtained nor implied.

---

## 11. Proposed smallest defensible next research gate (proposal — not an approved milestone)

### 11.1 The proposal in one paragraph

**Proposed working label (human to name or reject; not a registered milestone):** *"Two-dataset
synthesis review and compatibility-adjudication gate."* Scope: **documentation and human
adjudication only.** Named supervisor, statistician and clinician reviewers work through §7's
blockers and §9.4's decisions using source documentation and already-committed aggregate evidence;
the M2f Hungary conditional direction is adjudicated in the same sitting so the two candidate
between-dataset questions are never conflated. The gate's only possible outputs are a recorded
human disposition and, at most, permission to *draft* a future locked-model assessment protocol
for a separate approval cycle. **The gate authorizes no dataset download, no source inspection
beyond already-authorized local audit custody, no model fitting, no inference, no cross-dataset
prediction, no pooling and no validation run — under any outcome, including Go.**

### 11.2 Why this is the smallest defensible step

Any smaller step (e.g. proceeding directly to drafting a transfer protocol) would embed unadjudicated
target/coding/timing assumptions into a protocol and manufacture false readiness. Any larger step
(e.g. authorizing a locked-model build or an assessment run now) would require, in advance, exactly
the artifacts that do not exist: a frozen P-1 target/moment, an H-01 ruling, approved coding maps, an
overlap disposition, a locked artifact (neither benchmark saved one), and a Riley-2021 precision
calculation with human-set targets. The adjudication gate is the least work that converts §7 from a
list of agent-recorded blockers into a set of owned human decisions.

### 11.3 Go / Revise / No-Go conditions (all human-recorded; agent fills none)

**GO — proceed only to drafting a future locked-model assessment protocol (separate approval still
required before any execution), if and only if every condition holds:**

| # | Go condition |
|---|---|
| G1 | This synthesis is accepted (with any corrections minuted) by the named supervisor and research lead (D-a), and P-1 target/population/prediction-moment are frozen or the draft protocol is explicitly scoped to the adjudicated estimand (D-b). |
| G2 | H-01 is ruled **identical** or **reconciled** for the specific named dataset pair — or ruled **related-but-not-identical** with the protocol's estimand and claim wording rewritten to match that ruling (D-c). An *unresolved* ruling cannot support Go. |
| G3 | A verbatim per-feature coding/unit/timing map for the named pair is human-approved, including an explicit disposition of S-9/S-2…S-8 for any UCI-412 feature relied upon; unverified fields are excluded by design, not assumed (D-d). |
| G4 | A privacy-preserving aggregate overlap/provenance disposition for the named pair is recorded, stating what independence claim — if any — the evidence supports (§7.5). |
| G5 | A statistician records a Riley-2021 precision-feasibility ruling for the named locked-model question (estimands, target SE/CI widths, expected event fraction, anticipated miscalibration/linear-predictor inputs) showing the available cohort can support the intended claims at targets fixed before any result is seen (§7.6). |
| G6 | The drafting mandate states the one-shot rule (no tuning/selection on the assessment cohort), the locked-artifact prerequisite (a separately approved Cleveland — or other named-source — development-and-freeze step, since no artifact currently exists), aggregate-only reporting, and the P-5 claims boundary. |

**REVISE — return this synthesis (or the adjudication record) for amendment, and take no research
action, if any of the following holds:**

| # | Revise condition |
|---|---|
| R1 | Any blocker in §7 is judged resolvable but the evidence presented is insufficient, ambiguous or sourced only from secondary literature where an authoritative source is required (e.g. an official codebook statement for a relied-upon coding). |
| R2 | A tolerance/relaxation decision is needed for the sample-size findings (§5) before the feasibility-pilot status of either benchmark can be minuted (D-e). |
| R3 | The UCI-412 evidence that remains unsupplied after Revision 1.1 — bootstrap interval endpoints, reliability-bin values, joint-fit calibration intercepts, per-shuffle control values, Repeat↔seed mapping (U2/U4, Q-f; §4.9) — is judged material to accepting O2 into the record; the remedy is a maintainer-supplied **supplement of already-computed aggregates** through human review — not a re-run. The Revision 1.0 form of this item (missing family table, dispersion and calibration values) is **closed** by the supplied aggregates. |
| R4 | The two candidate between-dataset vehicles (Hungary site-shift vs any UCI-412-as-assessment question) cannot yet be prioritized on scientific grounds recorded independently of both AUROC values (D-f). |

**NO-GO — close the between-dataset direction (for the named pair), record the reason, and preserve
both benchmarks as standalone internal evidence, if any of the following holds:**

| # | No-Go condition |
|---|---|
| N1 | H-01 is ruled such that the targets cannot support a common or honestly-labelled related estimand for the named pair (Q-a). |
| N2 | No defensible shared prediction moment exists (predictor timing cannot be evidenced pre-angiography), so the transportability question itself is ill-posed (Q-b). |
| N3 | Overlap/independence cannot be bounded sufficiently for the intended interpretation, or the only available "second" source is a same-cohort or suspect-duplicate source (UCI-411 for UCI-412; Statlog for Cleveland) (§7.5). |
| N4 | The statistician's precision ruling (G5) finds the available counts cannot support the intended estimands at pre-set targets — as is already foreseeable for Switzerland's 8 negative records (Q-i). |
| N5 | Supervisor review is declined or indefinitely deferred, or P-1 cannot be frozen: **Gate PT P-3 stays CLOSED and the default disposition of this entire direction remains HOLD.** |
| N6 | Any Go condition could only be met by using an assessment cohort for selection/tuning, by pooling cohorts, or by back-deriving an anticipated R² from observed performance — each prohibited outright. |

**Current state against these conditions (agent record, not a decision):** G1–G6 are **none of them
met today** (P-1 pending; H-01 unresolved; no approved coding map; no overlap disposition for the
pair; no precision ruling; no locked artifact). The operative disposition is therefore **HOLD under
N5's default** until human review occurs. Revise items R1–R4 are available to reviewers without any
research action.

### 11.4 What this gate is not

Not a milestone approval, not a Gate PT P-3 opening, not a dataset authorization, not a model-freeze
authorization, and not an assessment authorization. Completing it changes no status in
`docs/DECISIONS.md` unless a named human records a separate decision there. If the gate returns Go,
the *next* artifact is a draft protocol document — again documentation-only — which must return for
its own supervisor review together with the separate model-development/freeze governance that
doc 07 §3.4 already requires.

---

## 12. Reviewer checklist and sign-off (all fields human-only)

### 12.1 Scientific review checklist

| # | Item | Status / reviewer note |
|---|---|---|
| S1 | Cleveland section (§3) faithfully reproduces doc 04, including its maintainer-reported status and §4.6/§5.4 reading constraints | ☐ |
| S2 | UCI-412 section (§4) reproduces only the maintainer-supplied aggregates; the §0.2 non-verification boundary is explicit and nowhere contradicted | ☐ |
| S3 | No cross-dataset ranking, difference, pooled or averaged metric appears anywhere; §6's permitted/prohibited statements are respected by the whole document | ☐ |
| S4 | Within-dataset vs between-dataset distinction (§6) is scientifically correct for both nested-CV procedure estimates | ☐ |
| S5 | All six compatibility blockers (§7) are complete; any missing blocker is added by amendment, not silently assumed away | ☐ |
| S6 | M2e.1, M2e.2 and M2f Hungary findings (§5, §8) are incorporated without re-decision or status change | ☐ |
| S7 | Calibration sections (§3.6, §4.6) preserve the descriptive-only status and the unresolved verdict for both datasets | ☐ |
| S8 | Sample-size section (§5) keeps `NOT ASSESSED` / `NOT_MET` distinct from a clinical verdict and records no tolerance relaxation | ☐ |
| S9 | Observed / uncertainty / unresolved / decision categories (§9) are correctly separated; no [BLANK] was prefilled by the agent | ☐ |
| S10 | §11's Go conditions cannot be read as authorizing data access, fitting, inference, transfer testing or validation | ☐ |
| S11 | TRIPOD+AI reporting gaps and the need for a formal, assessor-led PROBAST+AI review are owned by named humans (D-h) | ☐ **[BLANK]** |
| S12 | Disposition recorded: Accept / Revise (items: ___) / No-Go (conditions: ___) | ☐ **[BLANK]** |

### 12.2 Sign-off block — **[BLANK]**

| Field | Value |
|---|---|
| Supervisor (scientific) | **[BLANK]** |
| Statistical reviewer | **[BLANK]** |
| Clinical reviewer | **[BLANK]** |
| Maintainer / data custodian | **[BLANK]** |
| Review date | **[BLANK]** |
| Gate PT P-3 disposition | **CLOSED — no supervisor endorsement recorded by this document** |
| Next-gate disposition (§11) | **[BLANK — HUMAN ONLY]** |

---

## 13. Evidence sources and traceability

| Claim group in this synthesis | Source |
|---|---|
| Cleveland design, counts, performance, calibration, limitations | [Doc 04](04_d047_first_internal_results_REVIEW_DRAFT.md) §§1–8 (primary documented source; maintainer-reported aggregates) **[C-DOC]**; frozen design [doc 02](02_d047_internal_exploratory_cleveland_PROTOCOL_PROPOSED.md) + `research/experiments/cleveland_d047_exploratory_plan.v0.1.json` **[FROZEN]** |
| UCI-412 run identity, counts, performance, repeat-level values, calibration diagnostics, bootstrap statuses, negative control | Maintainer-supplied sanitized aggregate extractions (original supply plus the Revision 1.1 completion) for run `run-20261024T151846Z-4e3866dd` at commit `f859cf63efd31b7f88eaeeed69b5cc3606288727`, human-verified report SHA-256 `3c8524ea32aaa80a2412f3a977608c7e4eb3fdfe9883a7753f3149c662726545` **[MS-U412]** — not independently verified by the agent; bootstrap interval endpoints were not supplied, and whether conditional intervals were computed in the protected report is unverified (§4.5) |
| UCI-412 frozen design, panel, exclusions, thresholds, sample-size record | [Doc 08](08_m3a_uci412_source_specific_benchmark_SPECIFICATION.md) §§2–6, 10–11; [doc 09](09_m3a_uci412_internal_research_RATIFICATION_PACKET.md) §§3–5; [doc 10](10_m3a_uci412_source_encoding_AMENDMENT_A1.md) §§1–4 (S-9, frozen-parameter proof); `research/uci412/uci412_cad_research_plan.v0.1.json` (dictionary/panel 1.1.0) **[FROZEN]** |
| Sample-size adequacy (Cleveland) and validation-sizing separation | [Doc 05](05_m2e1_sample_size_research_ADEQUACY_REVIEW_DRAFT.md) §§1, 6, 9–10 **[M2e]** (Riley et al., *BMJ* 2020, doi:10.1136/bmj.m441; Riley et al., *Stat Med* 2021, doi:10.1002/sim.9025, as cited there) |
| Compatibility matrix, candidate dispositions, external-assessment prerequisites | [Doc 06](06_m2e2_dataset_compatibility_and_independent_assessment_READINESS_REVIEW_DRAFT.md) §§6–7, 9 **[M2e]**; Gate DA leakage/harmonization register (H-01) as carried there |
| Hungary conditional direction and decision matrix | [Doc 07](07_m2f_hungary_scientific_decision_and_conditional_protocol.md) §§1, 3–4 **[M2e]** |
| Governance statuses (P-1/P-3/P-5, D-046/D-047/D-048) | [`docs/DECISIONS.md`](../../DECISIONS.md); [`AGENTS.md`](../../../AGENTS.md) — unchanged by this document |
| Reporting/risk-of-bias framing | TRIPOD+AI, *BMJ* 2024, doi:10.1136/bmj-2023-078378; PROBAST+AI, *BMJ* 2025, doi:10.1136/bmj-2024-082505 (frameworks only; no formal assessment performed) |

**Methodological note on sources:** the UCI-412 secondary-literature item relied upon for coding
direction (Tao et al. 2025, *Rev Cardiovasc Med* 26(3):26204, doi:10.31083/RCM26204, Table 1) is
cited through doc 10's evidence addendum E-1 **[FROZEN]**; it is peer-reviewed secondary evidence,
explicitly not an official dataset-owner codebook.

### 13.1 Verification statement (this document)

- **Files changed by this synthesis:** this new document, plus one index bullet in
  [`docs/research/gate-pt/README.md`](README.md). Nothing else. No code, protocol, plan,
  dictionary, decision-register entry, gate status or existing document text was modified.
- **Experiments:** none. No training, inference, dataset download, source inspection, protected
  report upload, or patient-level data handling occurred. No protected local artifact was seen.
- **Numbers:** every performance value is either quoted from doc 04 **[C-DOC]**, supplied by the
  maintainer **[MS-U412]** (including the Revision 1.1 completion: full family table, per-repeat
  AUROC/Brier/calibration values and bootstrap statuses), or derived by labelled arithmetic
  **[AA]** from those values (§4.7 checks 7–14). No value was fitted, simulated, imputed or
  reconstructed: in particular, no confusion matrix, bootstrap interval endpoint, standard error
  or confidence interval was manufactured for either dataset. The agent's silence on conditional
  bootstrap intervals is a supply boundary only — endpoints were not supplied and local
  computation is unverified — and is never a claim that no such interval was computed in the
  protected report. The one last-decimal recomputation difference (RF Brier, §4.7 check 11) is
  disclosed as a qualified, unverifiable-at-4-dp possibility with the supplied aggregate
  (0.1156) preserved, rather than silently aligned or asserted as explained.
- **PR handling:** this synthesis is submitted as one documentation-only pull request, left
  **OPEN and unmerged** for human scientific review. A merged or CI-green documentation PR is not
  scientific approval.

---

**END OF REVIEW DRAFT — `INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED` — NOT SUPERVISOR APPROVED —
NOT CLINICAL EVIDENCE — NOT EXTERNALLY VALIDATED — GATE PT P-3 CLOSED**
