# M2e.1 — CAD Riley-Style Sample-Size Evidence and Adequacy Review (Review Draft)

> ## `NOT ASSESSED — PENDING HUMAN REVIEW`
>
> - **Status:** **REVIEW DRAFT — NO SAMPLE-SIZE DECISION TAKEN — NOT A GATE, APPROVAL, OR SUPERVISOR SIGN-OFF**
> - **Work item:** Issue #37, milestone **M2e.1** (sample-size evidence for the M2 Cleveland experiment)
> - **Scope:** documentation and arithmetic only. No data access, no model fitting, no new experiment, no change to D-047.
> - **Gate PT P-3:** **CLOSED** · **P-1:** **PENDING** · **D-047:** unchanged, already executed, not re-analysed
> - **Prepared:** 2026-10-23 · **Document type:** statistical evidence review (internal research record)

**This document does not approve a sample size, does not approve the experiment, does not make a clinical claim, and does not close any gate.** It states what can be verified arithmetically, what the literature does and does not supply, and what a named human must decide. Where the evidence does not support a number, the status is **NOT ASSESSED** and stays that way.

---

## 0. Reading guide

### 0.1 Evidence labels

| Label | Meaning |
|---|---|
| **[AR]** | **Agent-verified — repository.** Checked against a committed file at the base commit (paths given). |
| **[AA]** | **Agent-verified — arithmetic.** Recomputed by the agent from published formulae, reproducibly via `scripts/verify_m2e1_sample_size.py`. |
| **[LIT]** | **Literature claim**, with the primary source cited by DOI in [§14](#14-references). |
| **[MR]** | **Maintainer-reported** aggregate, carried forward from `04_…REVIEW_DRAFT.md`. Not independently reproduced from protected local output. |
| **[SC]** | **Hypothetical sensitivity scenario.** An arithmetic "what if", *not* an adopted assumption and *not* an input to any decision. |
| **[GAP]** | **Not available / not established.** Must not be filled by inference. |
| **[BLANK]** | Intentionally empty. A human completes it; the agent must not prefill. |

### 0.2 What this document is

A reviewable evidence package answering one question: **can the sample size of the M2 Cleveland experiment be judged adequate?** It:

1. states the frozen analysis inputs and why the parameter count is 8, not 5 ([§2](#2-frozen-inputs)–[§3](#3-why-p--8-and-not-5));
2. records the Riley binary-outcome methodology from primary sources, including the exact implementation checks performed ([§4](#4-the-riley-framework-for-binary-outcomes)–[§5](#5-numerical-verification));
3. reports the **R²-independent structural finding** that governs everything else ([§6](#6-the-decisive-result-that-does-not-depend-on-r²cs));
4. defines what an admissible external anticipated Cox–Snell R² would have to be, searches the project literature corpus and the CAD literature for one, and reports the result honestly ([§7](#7-the-externally-anticipated-coxsnell-r²-what-would-be-admissible-and-what-exists));
5. presents clearly-labelled hypothetical scenarios so that a reviewer can see the decision landscape **without** any of them being adopted ([§8](#8-hypothetical-sensitivity-scenarios-sc-not-assumptions-not-decisions));
6. records the status determination, the decision rule that would apply if humans later supply inputs, implications for a future independent-dataset assessment, and governance findings ([§9](#9-status-determination)–[§11](#11-governance-findings));
7. lists the questions that require human scientific review, with blank approval fields ([§13](#13-questions-requiring-human-scientific-review)).

### 0.3 What this document deliberately does **not** do

- It does **not** derive an anticipated R² from any observed metric of D-047, including AUROC 0.8271 (primary), 0.8292 (logistic regression), 0.8211 (random forest), or any fold-level value. This is prohibited by the frozen protocol and by `04_…REVIEW_DRAFT.md` §7.4. **[AR]**
- It does **not** run, rerun, re-score, re-split, or re-select anything; it does **not** re-open the experiment.
- It does **not** modify `research/experiments/**` (runner, reporting status string, plan), the frozen protocol (`gate-pt/02`), or the results draft (`gate-pt/04`). **[AR]**
- It does **not** record approval. Every approval field is `[BLANK]`.
- It does **not** treat its own arithmetic as a substitute for a statistician's review of the criteria chosen, the tolerance values used, or the population assumptions.

### 0.4 Files changed by this deliverable

| File | Change | Purpose |
|---|---|---|
| `docs/research/gate-pt/05_m2e1_cad_riley_sample_size_adequacy_REVIEW_DRAFT.md` | **new** | This review. |
| `scripts/verify_m2e1_sample_size.py` | **new** | Dependency-free reproduction of every number quoted here; contains no project data and fits nothing to patient records. |
| `docs/research/gate-pt/README.md` | edited | Registers document 05 in the Gate PT index. |

**Deliberately unchanged:** `research/experiments/reporting.py` (its `sample_size_sensitivity.status` string remains `NOT_ASSESSED_NO_HUMAN_REVIEWED_ANTICIPATED_COX_SNELL_R2_ASSUMPTIONS`), `research/experiments/cleveland_d047_exploratory_plan.v0.1.json`, `docs/research/gate-pt/02_…PROTOCOL_PROPOSED.md`, `docs/research/gate-pt/04_…REVIEW_DRAFT.md`, `docs/DECISIONS.md`, all source materials. **No decision-register entry was added because no decision was taken.** **[AR]**

---

## 1. The question, and the answer in one page

### 1.1 The question

The frozen D-047 protocol requires a "Riley-style binary-model sample-size sensitivity analysis with explicit anticipated Cox–Snell `R²` assumptions … If those assumptions are not defensible, results are a software/research feasibility pilot only; no clinical predictive adequacy is claimed." — `gate-pt/02_…PROTOCOL_PROPOSED.md`, line 32. **[AR]**

So the question is not "is n = 303 a large number?" It is: **for 8 slope parameters, 139 events and 164 non-events, is the development sample large enough under the Riley criteria, and if that cannot be established, what status must the experiment carry?**

### 1.2 The answer

| # | Statement | Status |
|---|---|---|
| 1 | The Riley binary-outcome criteria, implemented exactly as in `pmsampsize` v1.1.3, are reproduced here: published worked examples match to the participant (5,249 / 1,770 / 73). | **VERIFIED** **[AA]** |
| 2 | At n = 303 and prevalence 139/303 = 0.458746, the **outcome-proportion criterion alone requires 382 participants** (δ = 0.05). This value does not depend on R² or on the number of parameters. | **VERIFIED** **[AA]** |
| 3 | Adding the minimum-MAPE criterion, p = 8 requires **459** participants for every value of the anticipated R². | **VERIFIED** **[AA]** |
| 4 | Therefore the default criteria set **cannot be satisfied at n = 303 for any value of the anticipated R²**, and no reduction in the number of parameters would rescue it either. | **VERIFIED** **[AA]** |
| 5 | Whether 303 is nevertheless acceptable *for this project's stated exploratory purpose* depends on tolerances and on an anticipated R² that no admissible source supplies. | **NOT ASSESSED — PENDING HUMAN REVIEW** |
| 6 | No external, population-compatible anticipated Cox–Snell R² exists in the supervisor-selected corpus or in the CAD prediction literature that was examined. | **VERIFIED (absence)** **[AR]**, **[LIT]** — see [§7](#7-the-externally-anticipated-coxsnell-r²-what-would-be-admissible-and-what-exists) |
| 7 | Under the protocol's own rule (line 32), unavailability of defensible assumptions means the D-047 results are a **feasibility pilot only**. Recording that consequence is a factual application of the frozen text; it is not a new decision. | **PROPOSED for human confirmation** |

**Read points 2–4 and 5 together.** The sample size is *structurally below the default criteria* on grounds that need no R² input. That is different from — and stronger than — "we cannot tell". It is also different from a GO/NO-GO decision, which remains human.

### 1.3 Why the answer is not a single number

The Riley framework has no single "required n"; it returns the maximum over criteria that each target a different property (shrinkage, optimism, precision of the overall risk, precision of prediction error). Changing any one tolerance — shrinkage target, R² optimism allowed, width of the risk confidence interval, target MAPE — changes the answer. The framework also requires an **externally anticipated** R², which is a judgement about a model that does not yet exist. Both features are why the framework cannot be reduced to a rule of thumb, and why its output for this dataset is a *set of consequences*, not a pass mark.

---

## 2. Frozen inputs

| Input | Value | Source | Note |
|---|---:|---|---|
| Records | **303** | **[MR]** (D-047 run), consistent with **[AR]** protocol | Counts as reported; the criteria use realised counts, so fold-internal imputation does not change them. |
| Positive cases (`num = 1..4`) | **139** | **[MR]** | 45.8746% |
| Negative cases (`num = 0`) | **164** | **[MR]** | 54.1254% |
| Outcome proportion φ | **0.458746** | **[AA]** arithmetic from the two counts | Used for all criteria. |
| Predictor fields | 5: `age`, `sex`, `cp`, `trestbps`, `restecg` | **[AR]** `gate-pt/02`, line 26 | |
| Slope parameters p | **8** | **[AR]** `gate-pt/02`, line 32; `reporting.py` | See [§3](#3-why-p--8-and-not-5). |
| Shrinkage target S | **0.90** | **[LIT]** Riley 2020 default; used by `pmsampsize` | A tolerance, not a law. |
| Optimism tolerance (Nagelkerke R²) | **0.05** | **[LIT]** Riley 2020 | |
| Outcome-proportion half-width δ | **0.05** | **[LIT]** Riley 2020 | 95% CI for φ within ±0.05. |
| Target MAPE | **0.05** | **[LIT]** van Smeden 2019 | Approximation stated for p ≤ 30. |
| Anticipated Cox–Snell R² | **[BLANK]** | — | The missing input. See [§7](#7-the-externally-anticipated-coxsnell-r²-what-would-be-admissible-and-what-exists). |

Derived descriptives, repeated here only for orientation (they are **not** sample-size justifications and were already recorded as such in `04_…REVIEW_DRAFT.md` §7.2): events per parameter 139/8 = **17.4**; non-events per parameter 164/8 = **20.5**; records per parameter 303/8 = **37.9**. **[AA]**

> The frozen protocol already states: "Reporting n/parameters or `139/8` is **not** a valid sample-size justification" (`gate-pt/02`, line 32). **[AR]** Nothing in this document reintroduces that rule under another name.

---

## 3. Why p = 8 (and not 5)

### 3.1 The registered parameterisation

`gate-pt/02_…PROTOCOL_PROPOSED.md`, line 32, verbatim: **[AR]**

> "The five source fields imply **8 slope coefficients for a reference-coded LR**: age 1 + sex 1 + cp 3 + trestbps 1 + restecg 2."

The registered plan and the runner report the same count (`candidate_logistic_slope_parameters_after_reference_encoding: 8`). **[AR]**

### 3.2 Why this matters more than it looks

Sample size is driven by **parameters consumed**, not by the number of named variables. Counting five fields as five parameters understates the requirement by about 37% in this case: at R²cs = 0.112 the C1 requirement is 376 for p = 5 but 601 for p = 8 (the ratio is 1.6 at every strength examined; see the p-sensitivity in [§6.4](#64-what-would-have-to-change)). The draft Gate DA protocol anticipated this exact trap: "five raw field names may encode more than five parameters after one-hot encoding; n = 303 does **not** automatically establish adequate statistical sample size or predictive accuracy" (`gate-da/15`, R-MD-02). **[AR]**

### 3.3 Would a different encoding help?

Yes arithmetically, no practically. `cp` and `restecg` are multi-category fields; collapsing them into binary indicators would reduce p but change the model and its interpretation, and would have to be pre-registered as a different analysis. Even p = 5 does not make 303 adequate under the default criteria — the outcome-proportion criterion binds independently at 382 ([§6.2](#62-the-outcome-proportion-criterion-binds-independently-of-r²)). **[AA]**

---

## 4. The Riley framework for binary outcomes

### 4.1 The four criteria used in this review

| ID | Criterion | Formula | What it targets | Source |
|---|---|---|---|---|
| **C1** | Shrinkage | n₁ = ⌈p / ((S − 1)·ln(1 − R²cs/S))⌉, S = 0.90 | Expected uniform shrinkage ≥ S, i.e. limited overfitting | van Houwelingen & Le Cessie 1990; Riley 2020 |
| **C2** | Optimism in Nagelkerke R² | s = R²cs/(R²cs + 0.05·maxR²cs), then n₂ = ⌈p / ((s − 1)·ln(1 − R²cs/s))⌉ | Apparent vs adjusted R² difference ≤ 0.05 | Riley 2019 (Part II); Riley 2020 |
| **C3** | Precision of the outcome proportion | n₃ = ⌈(1.96/0.05)²·φ(1 − φ)⌉ | 95% CI for overall risk within ±0.05 | Riley 2020 |
| **C4** | Precision of prediction error | n₄ = ⌈exp((−0.508 + 0.259·ln φ + 0.504·ln p − ln 0.05)/0.544)⌉ | Mean absolute prediction error (MAPE) ≈ 0.05 | van Smeden 2019; summarised in Riley 2020 |

with

> **maxR²cs = 1 − exp(2·[φ·ln φ + (1 − φ)·ln(1 − φ)])**

the largest Cox–Snell R² attainable for a binary outcome at outcome proportion φ (0.74829 here; the theoretical maximum over all φ is 0.75 at φ = 0.5). **[AA]**

C1–C3 are the three criteria returned by `pmsampsize` for a binary outcome. C4 is an *additional* published criterion for precise prediction error, not part of that function's output; it is reported separately below so that a reviewer can see which criterion is doing the work. **[AR]** (source traceability in [Appendix B](#appendix-b--pmsampsize-source-traceability)).

### 4.2 What the criteria do and do not guarantee

They target **development-sample overfitting and precision**, at tolerances the analyst selects. They do **not** guarantee calibration in a new population, do not substitute for external validation, and do not address measurement error, case-mix shift, or selection. Riley et al. are explicit that the calculation is a minimum planning target, not a certificate. **[LIT]**

Two further caveats that matter here:

- **C3 targets the precision of the model intercept — in practice the overall outcome proportion — not discrimination.** It is independent of any predictor, and therefore binds at a fixed value for every model of every size on this dataset. **[LIT]**, **[AA]**
- The MAPE criterion (C4) is an approximation whose validity is stated for p ≤ 30, and independent simulation work reports that the Cox–Snell-based formulae **underestimate** the required n when model strength is high (C ≈ 0.85–0.90 needs ≥ 50–100% more), while the MAPE formula **overestimates** at high strength. For this dataset, therefore, the numbers below should be read as *lower bounds conditional on the stated tolerance set*. **[LIT]** (Pavlou 2024)

### 4.3 Implementation verified

The reference implementation used for checking is `pmsampsize` v1.1.3 (CRAN; source commit `ebbe7c9`, 2023-12-05). The formulas above are transcriptions of `R/pmsampsize_bin.R` lines 12, 28–30 and 39, and the maximum-R² expression at lines 19–20. **[AR]**

Two guards in that source are part of the methodology and were reproduced: the function stops if `shrinkage < rsquared` (the shrinkage target must exceed the anticipated R²) and if `max_r2a < r2a` (an anticipated R² above the attainable ceiling). **[AR]**

### 4.4 The C-statistic → R²cs conversion, and its precondition

`pmsampsize` can accept a C-statistic instead of a R², converting it by simulation (`R/cstat2rsq.R`): a million observations, linear predictor drawn from N(0,1) for non-events and N(√2·Φ⁻¹(C), 1) for events, logistic calibration, then R²cs = 1 − exp(−(D_null − D_model)/n). **[AR]**

The methodological justification is Riley, Van Calster & Collins 2021, whose stated precondition is decisive for this project: the method is for obtaining an anticipated R² from **a reported C statistic of an existing published model in the same field, evaluated at the outcome proportion of the target (development) population**, and the authors advise using the *lowest* plausible C. **[LIT]**

It is **not** a licence to convert a model's own apparent AUROC into a planning input, because that is circular: the apparent AUROC of the model being sized is an output of the very fit whose stability is in question. Using it would make the sample-size calculation depend on the result it is meant to constrain. This is the formal reason behind the prohibition in `04_…REVIEW_DRAFT.md` §7.4, and it is independent of any suspicion about the specific D-047 numbers. **[AR]**, **[LIT]**

---

## 5. Numerical verification

### 5.1 Published anchors reproduced exactly

| Check | Expected | Reproduced | Status |
|---|---:|---:|---|
| maxR²cs at φ = 0.05 | 0.32769 | 0.32769 | **PASS** |
| C1, p = 30, R²cs = 0.05, φ = 0.05, S = 0.90 | 5,249 | 5,249 | **PASS** |
| C2, same inputs | 1,770 | 1,770 | **PASS** |
| C3, φ = 0.05 | 73 | 73 | **PASS** |
| Final (max of C1–C3) | 5,249 | 5,249 | **PASS** |
| C4 worked example, p = 10, φ = 0.30, MAPE = 0.05 | 460.86 → 461 | 460.86 → 461 | **PASS** |
| maxR²cs at φ = 0.5 (theoretical ceiling) | 0.75000 | 0.75000 | **PASS** |

**[AA]** — all seven reproduced by `python3 scripts/verify_m2e1_sample_size.py`, which exits non-zero on any mismatch.

### 5.2 Implementation cross-checks

- **Monotonicity:** C1 decreases as R²cs rises and increases with p, as the formula requires. **PASS**
- **Guards:** both `pmsampsize` error conditions are reproduced. **PASS**
- **C→R²cs replication:** at C = 0.81, φ = 0.77 the published example gives R²cs = 0.2100957; this implementation gives **0.212115** (a ~1% relative difference). This is an *implementation-convention* difference in a simulation-based approximation, not a discrepancy in the method: it moves n by about 1%, whereas the differences that matter below are of order 50%. It is recorded rather than smoothed away. **[AA]**
- **Seed sensitivity** of the C→R²cs conversion at this scale: ≈0.001 in R²cs across seeds (0.0007–0.0010 over three seeds, n = 4×10⁵), i.e. ≈0.5% in n — far smaller than any difference that matters below. **[AA]**

### 5.3 What verification does not establish

That the criteria are the right ones for this project; that the default tolerances are the right ones; that the anticipated R² is knowable; or that 303 records of a 1980s single-centre benchmark represent any target population. Verification covers the arithmetic and the transcription of published formulas — nothing else. **The methodological choice remains a human decision.** **[GAP]**

---

## 6. The decisive result that does not depend on R²cs

### 6.1 The two R²-free numbers

| Quantity | Value | Depends on R²? | Depends on p? |
|---|---:|:---:|:---:|
| C3 — outcome-proportion precision (δ = 0.05) | **382** | no | **no** |
| C4 — minimum MAPE (p = 8, MAPE = 0.05) | **459** | no | yes (p = 8) |

Since 382 > 303 and 459 > 303, **both criteria fail at the current sample size before any R² assumption is made.** **[AA]**

### 6.2 The outcome-proportion criterion binds independently of R²

C3 = (1.96/0.05)²·φ(1 − φ) contains no parameter count and no R². At φ = 0.458746 it equals 381.54, rounded up to **382**. Consequently:

- **No choice of anticipated R² can make the three-criterion `pmsampsize` set satisfiable at n = 303.**
- **No reduction in the number of parameters can make it satisfiable either.** C3 is unchanged by p, so *no positive* p satisfies C1–C3 at n = 303.

This is the cleanest statement in the review, and it is available without any literature judgement about R². It does not by itself declare the study worthless: a reviewer may decide that ±0.05 precision on the overall risk is not required for an internal exploratory benchmark. But that decision is a **documented relaxation of a published criterion**, and must be recorded as such rather than presented as adequacy.

### 6.3 The full requirement as a function of the missing input

Required n at p = 8, φ = 0.458746, S = 0.90, MAPE = 0.05, δ = 0.05. Column "final" is the maximum of the four criteria; "shortfall" is final − 303. **[AA]**

| Anticipated R²cs | Nagelkerke-equivalent\* | C1 | C2 | C3 | C4 | **Final** | Shortfall |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.050 | 0.067 | 1,400 | 205 | 382 | 459 | **1,400** | 1,097 |
| 0.075 | 0.100 | 920 | 202 | 382 | 459 | **920** | 617 |
| 0.100 | 0.134 | 680 | 199 | 382 | 459 | **680** | 377 |
| 0.112 (15% of max) | 0.150 | 601 | 198 | 382 | 459 | **601** | 298 |
| 0.125 | 0.167 | 536 | 196 | 382 | 459 | **536** | 233 |
| 0.144 | 0.192 | 459 | 194 | 382 | 459 | **459** | 156 |
| 0.150 | 0.201 | 439 | 194 | 382 | 459 | **459** | 156 |
| 0.170 | 0.227 | 383 | 191 | 382 | 459 | **459** | 156 |
| 0.209 (break-even for C1) | 0.279 | 304 | 187 | 382 | 459 | **459** | 156 |
| 0.250 | 0.334 | 246 | 182 | 382 | 459 | **459** | 156 |
| 0.500 | 0.668 | 99 | 150 | 382 | 459 | **459** | 156 |
| 0.748 (theoretical max) | 1.000 | 45 | 110 | 382 | 459 | **459** | 156 |

\* R²cs / maxR²cs at this prevalence; shown only to help a reviewer interpret the magnitude. It is not an approved input either.

**Three readings of this table:**

1. **Below R²cs ≈ 0.144**, C1 dominates and the requirement exceeds 459; at R²cs = 0.05 it is 1,400 — 4.6× the available records.
2. **Between 0.144 and the ceiling**, the requirement is flat at **459** because C4 binds. Raising the assumed model strength beyond ~0.14 buys nothing.
3. **C1 is satisfied at 303 only for R²cs ≥ 0.20884** (exactly 0.208842), i.e. 27.9% of the attainable R² — and even then C2 is satisfied but C3 and C4 still fail.

### 6.4 What would have to change

Each row is arithmetic. **None of these is a recommendation**; each would be a documented methodological decision requiring human approval. **[AA]**

| Lever | Current | Threshold implied by n = 303 | Comment |
|---|---:|---:|---|
| C3 precision δ | ±0.050 | **±0.0561** | Weaker precision of the overall risk; 303 gives δ = 0.056108 |
| C4 target MAPE | 0.050 | **0.0627** | 303 gives 6.27% mean absolute prediction error |
| C1 shrinkage S | 0.90 | **0.887** delivered for R²cs = 0.209 | To deliver S = 0.90 you need R²cs ≥ 0.2088; S = 0.85 needs ≥ 0.1372; S = 0.80 needs ≥ 0.0989 |
| Parameters p | 8 | ≤ 7 (C1) / ≤ 5 (C1+C2+C4) at R²cs = 0.209 | C3 is unaffected by p and still fails |
| Sample size n | 303 | **459** (four criteria) / **382** (three criteria) | +156 or +79 records — not available within this fixed public benchmark |

Required n at n = 303 for C1 by parameter count, S = 0.90: p = 3 → 0.0848; 4 → 0.1113; 5 → 0.1369; 6 → 0.1617; 7 → 0.1857; **8 → 0.2088**; 9 → 0.2313; 10 → 0.2530. **[AA]**

The corresponding expected shrinkage at n = 303, p = 8 — the quantity C1 is really about — is: R²cs 0.05 → **S ≈ 0.49**; 0.10 → 0.75; 0.15 → 0.84; 0.209 → 0.89; 0.25 → 0.91; 0.30 → 0.93. **[AA]** A model with true R²cs around 0.10 fitted to this dataset would be expected to shrink to about three-quarters of its apparent performance in new data of the same type.

### 6.5 Consequence under the frozen protocol's own wording

`gate-pt/02`, line 32 states that if the anticipated-R² assumptions are not defensible, "results are a software/research feasibility pilot only; no clinical predictive adequacy is claimed." **[AR]**

Two facts are now established: (a) the assumptions are not merely unavailable — see [§7](#7-the-externally-anticipated-coxsnell-r²-what-would-be-admissible-and-what-exists); and (b) the criteria fail even for favourable hypothetical values. The protocol's fallback clause therefore applies on both grounds. Recording that is **PROPOSED** for human confirmation, not self-executed: this draft does not alter the banner on the D-047 results, which already reads `INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED`. **[AR]**

---

## 7. The externally anticipated Cox–Snell R²: what would be admissible, and what exists

### 7.1 What the input is, and who owns it

An **anticipated Cox–Snell R²** is a *pre-modelling* judgement about how much variation a model of this predictor set is expected to explain in this population. It is a scientific assumption about the future model, not a summary of a fitted one. It can legitimately come from:

- a published model with **the same outcome definition**, **comparable predictor set**, **comparable case-mix / prevalence**, reporting R²cs or Nagelkerke R² directly; or
- the Riley 2021 conversion from **a published model's C statistic evaluated at the target prevalence**; or
- a **documented expert elicitation** with a stated protocol, panel and consensus rule.

The choice belongs to the research lead/supervisor, not to the agent. The agent's job is to state the admissibility test, search, and report.

### 7.2 Admissibility test applied to every candidate

| ID | Condition | Why it is required |
|---|---|---|
| **A1** | Outcome definition matches (`num = 0` vs `1..4`; historical angiography-referenced CAD presence) | R² is outcome-specific; a 30-day-event or ≥50%-stenosis-on-CTA endpoint is a different quantity |
| **A2** | Predictor set comparable to `age, sex, cp, trestbps, restecg` (8 parameters) | R² rises mechanically with additional predictors; borrowing from a 12-variable model overstates expected fit |
| **A3** | Population prevalence comparable to 45.87% | maxR²cs and every criterion depend on φ; a 23%-prevalence cohort is a different planning problem |
| **A4** | Measurement timepoint compatible with a resting pre-angiography decision | otherwise the model is answering a different clinical question |
| **A5** | R²cs or Nagelkerke R² reported, **or** a published C convertible under Riley 2021's precondition | otherwise no number exists |
| **A6** | Provenance checkable (DOI, table/figure locatable by a reviewer) | an unverifiable number is not evidence |

### 7.3 Absolute prohibition: observed performance of this model or its benchmark

Deriving the anticipated R² from D-047's own apparent AUROC (0.8271 primary, 0.8292 logistic regression, 0.8211 random forest **[MR]**), or from any fold-level or resampled value, would be circular and is prohibited by `04_…REVIEW_DRAFT.md` §7.4. **[AR]** For completeness, the *hypothetical* C→R²cs mapping is shown in [§8.3](#83-c-derived-illustration-sc--and-why-every-row-is-inadmissible) purely so that the prohibition has a visible numeric consequence; **none of those values is used, adopted, or recommended anywhere in this document.**

### 7.4 Screen of the supervisor-selected corpus

**Source of truth:** `research/source_materials/literature_review_original.xlsx` (sheet *Literature Review*, 25 papers, rows 6–30) and its extraction `research/source_materials/literature_review_status.csv` (25 rows × 15 columns). The presentation (`project_presentation*`) is **not** used as a status source. **[AR]**

**Method.** Whole-row, case-insensitive term sweep across all 15 columns of the CSV, plus the equal sweep of the workbook sheet. **[AR]**

| Search term | Rows matched |
|---|---:|
| `riley` | 0 |
| `shrinkage` | 0 |
| `cox-snell`, `cox snell` | 0, 0 |
| `nagelkerke` | 0 |
| `r-squared`, `r2` | 0, 0 |
| `events per variable`, `epv` | 0, 0 |
| `sample size` | 1 (P22, in a limitation sentence about ethnic subgroups) |
| `overfitting` | 1 (P6, self-criticism of a 303-record benchmark) |
| `calibration slope` | 0 |
| `tripod`, `probast` | 0, 0 |
| `cleveland` | 7 (P2, P3, P6, P7, P14, P19, P21) |
| `303` | 6 (P1, P5, P6, P8, P9, P21) |

**Result.** The corpus contains **no paper reporting a Cox–Snell or Nagelkerke R²**, no sample-size calculation, no shrinkage estimate, and no reference to TRIPOD or PROBAST in the extraction. Seven papers use Cleveland in some form (P2, P3, P6, P7, P14, P19, P21) and six papers report a 303-record dataset (P1, P5, P6, P8, P9, P21 — the Z-Alizadeh Sani cohort used by P5, P8 and P9 also has 303 records). None justifies the size. P6 states the concern directly ("Small Cleveland dataset (n = 303). Potential overfitting risk at 98.4% on a small benchmark"). **[AR]**

**Therefore: the supervisor-selected corpus cannot supply an admissible anticipated R².** That is not a criticism of the corpus — it is a machine-learning benchmarking literature, not a methodological one — but it settles the question for the source of truth we were instructed to use.

Full screen, all 25 papers: **[Appendix C](#appendix-c--corpus-screen-all-25-papers)**.

### 7.5 External CAD prediction literature examined

The purpose here is narrow: does any published CAD model give a defensible *anticipatory* R² for a five-field resting panel at ~46% prevalence? These are the most relevant published CAD prediction models; none reports R²cs. **[LIT]**

| Source | Cohort / endpoint | Prevalence | Published discrimination | Fails |
|---|---|---:|---|---|
| Genders 2011, *Eur Heart J* (CAD Consortium updating/extension) | 2,260 patients, CT/catheter angiography, obstructive CAD | 58.4% (1,319/2,260) | c = 0.79 (updated); 0.82 (extended) | A2 (includes symptoms/risk factors/CAC), A3 (58.4% vs 45.9%), A5 (no R²) |
| Genders 2012, *BMJ* (pooled cohorts, basic/clinical/extended models) | 18 hospitals, ≥50% stenosis | mixed by setting | cross-validated c = 0.77 / 0.79 / 0.88 | A2, A3, A5 |
| Genders 2018, *JACC Cardiovasc Imaging* (PROMISE external validation) | 3,468 patients, ≥50% stenosis on CTA | 23% (779/3,468) | c = 0.69 / 0.72 / 0.86; calibration slope < 1 | A2, A3 (23% vs 45.9%), A5 |

Two further points from this literature are relevant beyond the admissibility test:

- **Calibration slopes below 1 persist in external data even for well-known models** (PROMISE reports calibration slope < 1 overall, with the clinical model over-predicting at higher probabilities, most pronounced in women). Overfitting is an empirical phenomenon in this literature, not a theoretical worry. **[LIT]**
- **The numbers move a lot with predictor set**: 0.69 → 0.72 → 0.86 as chest-pain type gives way to risk factors and then to coronary calcium. Borrowing an R² from a CAC-augmented model to plan a five-field model would be indefensible. **[LIT]**

**No candidate passes the admissibility test.** The C-statistics above remain *interesting context* and are explicitly **not** converted into an adopted anticipated R² anywhere in this document.

### 7.6 Outcome of the search

> **Anticipated Cox–Snell R²: NOT ASSESSED — PENDING HUMAN REVIEW.**
>
> No admissible value exists in (a) the supervisor-selected corpus, (b) the CAD prediction literature examined, or (c) any D-047 output that this project is permitted to use. No value has been assumed, borrowed, interpolated, or reverse-engineered. **[AR]**, **[LIT]**, **[GAP]**

A reviewer may still supply one. [§13](#13-questions-requiring-human-scientific-review) lists exactly what would have to accompany it.

---

## 8. Hypothetical sensitivity scenarios **[SC]** (not assumptions, not decisions)

> **Banner.** Everything in this section is arithmetic contingent on an input that has **not** been approved. The values below are not the project's assumptions, are not a basis for GO, and must never be quoted as if the project had adopted them. Their purpose is to let a reviewer see how the answer moves, so that any eventual decision is made with the landscape visible.

### 8.1 The scenario grid

Repeated from [§6.3](#63-the-full-requirement-as-a-function-of-the-missing-input) for continuity; the "verdict" column is deliberately phrased as a consequence, not a decision.

| Scenario | R²cs **[SC]** | Final n required | Verdict under the default criteria |
|---|---:|---:|---|
| Very weak model | 0.050 | 1,400 | Inadequate by a factor of 4.6 |
| Weak model | 0.075 | 920 | Inadequate by a factor of 3.0 |
| Low-moderate | 0.100 | 680 | Inadequate by a factor of 2.2 |
| 15% of attainable R² | 0.112 | 601 | Inadequate by a factor of 2.0 |
| Moderate | 0.150 | 459 | Inadequate by 156 records |
| Break-even for C1 | 0.209 | 459 | C1 needs 304 (one record short); C3 and C4 not met |
| Strong | 0.250 | 459 | Same floor; strength no longer helps |
| Perfect model | 0.748 | 459 | Same floor |

**No scenario in this grid yields an adequate sample size under the default criteria.** The verdicts do not depend on which scenario a reviewer prefers — only the *margin* does.

### 8.2 What the flat floor means

Because C3 = 382 and C4 = 459 are R²-free, the entire plausible range of anticipated R² collapses onto the same conclusion. A reviewer who wants to argue that 303 is adequate must therefore argue **against a criterion**, not **about a model's expected strength**. That is a much narrower and more explicit disagreement, and it is the kind of disagreement that can be recorded and reviewed.

### 8.3 C-derived illustration **[SC]** — and why every row is inadmissible

The conversion below applies the Riley 2021 simulation at the project's own prevalence to a set of illustrative C-statistics. It is shown to demonstrate that even a flattering assumption does not rescue 303 — **not** because any of these C-statistics is admissible for D-047. **[AA]**

| Hypothetical C **[SC]** | → R²cs | → Nagelkerke-equiv. | → C1 n | → final n | Admissible? |
|---:|---:|---:|---:|---:|---|
| 0.69 (PROMISE basic, 23% prevalence) | 0.1087 | 0.145 | 622 | 622 | **No** — A2, A3 fail |
| 0.75 (not a published CAD value) | 0.1840 | 0.246 | 350 | 459 | **No** — no source |
| 0.77 (Genders 2012 basic) | 0.2128 | 0.284 | 297 | 459 | **No** — A2, A3 fail |
| 0.79 (Genders 2011 updated) | 0.2434 | 0.325 | 254 | 459 | **No** — A2, A3, A5 fail |
| 0.82 (Genders 2011 extended) | 0.2924 | 0.391 | 204 | 459 | **No** — A2, A3 fail |
| 0.85 (hypothetical) | 0.3453 | 0.462 | 166 | 459 | **No** — no source |

For completeness of the prohibition: the same arithmetic applied to D-047's own apparent AUROCs (0.8271 primary, 0.8292 logistic regression **[MR]**) would land in the same range as the rows above. **That conversion is deliberately not performed, not reported, and not used here**, because it is exactly the circular derivation that `04_…REVIEW_DRAFT.md` §7.4 forbids — and because, as the table shows, it would not change the final requirement of 459.

### 8.4 How these scenarios must and must not be used

| Permitted | Prohibited |
|---|---|
| Showing a reviewer the decision landscape | Quoting any row as "the project's assumed R²" |
| Comparing the margin across plausible strengths | Selecting the row that produces a favourable verdict |
| Justifying why the verdict is insensitive to R² | Using any row to argue that D-047 is adequate |
| Sensitivity of the *thresholds* to S, δ, MAPE, p | Feeding any row into a report, gate, or claim |

---

## 9. Status determination

### 9.1 The recorded status

| Field | Value |
|---|---|
| Sample-size adequacy | **`NOT ASSESSED — PENDING HUMAN REVIEW`** |
| Machine-readable status (unchanged, already in the runner) | `NOT_ASSESSED_NO_HUMAN_REVIEWED_ANTICIPATED_COX_SNELL_R2_ASSUMPTIONS` **[AR]** `research/experiments/reporting.py` |
| R²-independent structural finding | `DEFAULT_CRITERIA_INFEASIBLE_AT_N_303` — established by C3 = 382 and C4 = 459 **[AA]** |
| Anticipated R²cs | `NOT SUPPLIED — NOT ADMISSIBLE FROM AVAILABLE SOURCES` |
| Decision | **none taken**; no approval recorded; no gate action |

The two statements are consistent, not contradictory: *we cannot assess adequacy* **and** *the default criteria cannot be met here* are both true, and the second is the reason the first will not resolve by better guessing.

### 9.2 Three-part verdict

**(a) VERIFIED** — the arithmetic, the transcription of the published criteria, the corpus screen, and the absence of an admissible R².

**(b) NOT ASSESSED** — whether 303 is adequate for the project's *own* stated purpose under *its own* chosen tolerances.

**(c) CONDITIONAL FACT** — under the published defaults (S = 0.90, optimism 0.05, δ = 0.05, MAPE = 0.05) and p = 8, no anticipated R² makes the criteria satisfiable at 303; the minimum is 459, and even the three-criterion `pmsampsize` set requires 382.

### 9.3 Decision rule if humans later supply the missing inputs

Pre-registered here so that the number cannot be chosen after seeing the answer. **PROPOSED** — requires human ratification before it governs anything. **[BLANK]** for approval.

> **Note on internal consistency:** because C3 = 382 at this prevalence, step 3 can never be reached without a ratified relaxation of C3 (step 6). The rule is written this way deliberately: it makes the relaxation the visible decision, rather than burying it in the choice of R².

1. Compute `pmsampsize`'s three criteria with the supplied R²cs, p = 8, φ = 0.458746, S as ratified. Record C1–C3 and the maximum.
2. Compute C4 (MAPE) separately and record it.
3. If max(C1…C4) ≤ 303 → record **ADEQUATE**, listing the criteria met and the source of the R².
4. If 303 < max ≤ 1.25 × 303 → record **MARGINALLY INADEQUATE** and require an explicit, documented limitation in the results.
5. If max > 1.25 × 303 → record **NOT ADEQUATE FOR FORMAL DEVELOPMENT**; the experiment remains an internal feasibility pilot and cannot support a predictive-adequacy claim.
6. Any deviation (waiving a criterion, changing a tolerance, substituting a sensitivity analysis) must be recorded with **who**, **when**, and **why**, in the approval ledger, before the number is used.
7. The anticipated R² must arrive with: the numeric value, the source (DOI + table/figure), the population and endpoint it refers to, the predictor set it refers to, and a statement of why A1–A6 hold. Incomplete submissions are returned, not completed by the agent.

### 9.4 What would constitute a GO — and why none of it is met

A defensible "adequate" finding would require all of: an admissible R² (§7); criteria met or a documented relaxation (§9.3); the relaxation signed by a named human; and the interpretation bounded to the stated population. **None of these exists.** The status therefore remains `NOT ASSESSED`, and the operative research description of D-047 remains *internal exploratory feasibility*, as the protocol already says. **[AR]**

---

## 10. Implications for independent-dataset assessment (no experiments conducted)

### 10.1 Two different questions

Development sizing (this document) asks whether the model can be estimated stably. **Validation sizing** asks whether a fitted, locked model can be *evaluated* precisely in a new dataset. They use different methods, different inputs, and different targets, and neither substitutes for the other. **[LIT]**

### 10.2 The applicable validation method requires inputs this project does not yet have

Riley et al. 2021 (external validation, binary outcome) size a validation study from: target standard errors for each performance measure, the anticipated event proportion in the validation population, the anticipated (mis)calibration, the variance of the linear predictor in that population, and — for net benefit — the risk thresholds of interest. In their worked example the **calibration slope criterion drove the sample size** (177 events / 9,835 participants at 1.8% prevalence), not discrimination. **[LIT]**

For any future external dataset here, that means: no target can be computed until that dataset is named, its event proportion established, and its anticipated miscalibration stated. **Status: NOT ASSESSED for every candidate dataset; no dataset has been approved.** **[GAP]**

### 10.3 What this implies concretely

| Implication | Consequence for planning |
|---|---|
| Precision targets are driven by calibration slope, not AUROC alone | A future validation plan must pre-specify calibration measures and their target SEs, not only discrimination |
| Event count matters more than total n | A small-cohort site (for example 123 records with 8 outcome-negatives in Switzerland, per `gate-da/15`) cannot support a conventional discrimination or calibration claim — `gate-da/15` itself anticipates this. **[AR]** |
| Development performance is not validation performance | Calibration slopes < 1 in external CAD data (PROMISE) are the expected pattern, not an anomaly. **[LIT]** |
| 303 records cannot be "reused" as external validation of a model developed on the same 303 records | Any such claim is circular and prohibited (`validation_status` lifecycle; P-5 remains **NOT MADE — prohibited**) **[AR]** |

### 10.4 Arithmetic illustration only **(not a target, not a recommendation)**

At φ = 0.458746, an events-based target of 100 corresponds to ≈ 218 participants and 200 to ≈ 436 — pure arithmetic conversions, shown only so that reviewers can see the order of magnitude. They are **not** output from the validation method above, are not a substitute for it, and must not be adopted as a target without a proper calculation in the eventual validation protocol. **[AA]**, **[SC]**

### 10.5 Non-consequences

No external validation was performed, attempted, planned, or implied. No candidate external dataset was accessed. P-5 remains **NOT MADE — prohibited**. D-047 remains a single-source internal benchmark. **[AR]**

---

## 11. Governance findings

### 11.1 Sequencing: the two governing documents disagree

`gate-da/15_…_DRAFT.md` (draft pre-registration) requires, at item 1 of its sample-size policy: **"Document the calculation and decision before executing any model."** **[AR]**

`gate-pt/02_…_PROTOCOL_PROPOSED.md` (the frozen protocol under which D-047 ran) requires the Riley-style analysis in **"the first report"** — i.e. after execution. **[AR]**

D-047 was executed before this analysis existed. Under `gate-pt/02` that timing is permitted; under `gate-da/15` it would not have been. **This is a documentation inconsistency to be resolved by a human, not a breach to be quietly repaired, and it must not be presented as either.** It is recorded because a reviewer comparing the two documents will notice it, and because the resolution determines the sequencing of any future model execution. → **Q10**

### 11.2 No sample-size policy in the methodology blueprint

`docs/blueprint/05_RESEARCH_METHODOLOGY_AND_APPROVAL_GATES.md` contains **no** sample-size policy: greps for `riley`, `sample size`, `events per` return only the §6 subgroup rule (cells need ≥ 30 patients and ≥ 10 events per class, otherwise counts only) and TRIPOD+AI reporting. **[AR]** The operative policy lives in the two protocol documents instead, which is how the inconsistency in §11.1 arose. A one-paragraph policy pointer in blueprint 05 would prevent recurrence — **PROPOSED**, not done here.

### 11.3 Issue thread inaccessible

`gh issue view 37` and the issue API returned **HTTP 403**; the web view returned **404**. **[GAP]** The issue body and any discussion in it are therefore **not** cited as evidence anywhere in this document. If the issue contains an additional requirement (for example a reviewer-specified tolerance), this review has not seen it, and that must be checked by a human.

### 11.4 Nothing was approved, closed, or changed

No gate was closed. No approval was recorded. No code, plan, protocol, or result file was modified. This change set touches only the three files listed in [§0.4](#04-files-changed-by-this-deliverable). **[AR]**

---

## 12. Limitations of this review

1. **Arithmetic, not statistics.** Verification covers published formulas and their transcription. It does not establish that the Riley criteria are the appropriate frame for this project.
2. **Default tolerances are defaults.** S = 0.90, optimism 0.05, δ = 0.05, MAPE = 0.05 are the published defaults. A reviewer may ratify different values, which changes every number — see [§6.4](#64-what-would-have-to-change).
3. **The anticipated R² is absent.** Every n in [§6](#6-the-decisive-result-that-does-not-depend-on-r²cs) and [§8](#8-hypothetical-sensitivity-scenarios-sc-not-assumptions-not-decisions) is conditional. None is an estimate of the truth.
4. **The criteria are lower bounds in this regime.** Independent simulation work reports that the Cox–Snell-based formulae underestimate the requirement when model strength is high, and that the MAPE formula overestimates it there. **[LIT]** (Pavlou 2024)
5. **C4 is an approximation** stated for p ≤ 30 and derived for a single binary outcome without interaction or penalisation terms.
6. **Prevalence is taken as fixed** at 139/303. Sampling variability in φ is not propagated into the criteria.
7. **p = 8 is taken as fixed** by the registered encoding. Any change to encoding changes the requirement, and would itself be a protocol amendment.
8. **No account of missing data, measurement error, or case-mix heterogeneity.** These make the effective sample size smaller, not larger; ignoring them is optimistic.
9. **The corpus screen is a text sweep.** A paper could report an R² under a different name that the sweep would miss; the 25 rows were also read in full, which mitigates but does not eliminate this.
10. **Penalisation is not a substitute.** L2 regularisation constrains the fitted coefficients; it does not create information. The statistical principle is stated here for the record, but the formal confirmation that no penalisation setting is being treated as a sample-size remedy is a human action (Q8).
11. **No claim about the historical cohort's representativeness.** Nothing here speaks to whether a 1980s single-centre Cleveland cohort is clinically transportable; that is a separate and larger question already flagged in `04_…REVIEW_DRAFT.md` §8.
12. **This review is not a statistical analysis plan.** It is the evidence input to one; it does not replace review by a statistician.

---

## 13. Questions requiring human scientific review

Each question has a blank decision field. The agent must not prefill any of them.

| # | Question | Owner | Decision **[BLANK]** |
|---|---|---|---|
| **Q1** | Is p = 8 the correct sizing basis (reference-coded LR over the five-field panel), or should a reduced encoding be pre-registered as a separate analysis? | Research lead / statistician | |
| **Q2** | Is the four-criterion set (C1–C4) the adopted frame, or only `pmsampsize`'s three criteria, or a named subset? | Research lead / statistician | |
| **Q3** | If a subset, which criteria are waived and what tolerances apply (S, optimism, δ, MAPE)? Record who decided, when, and why. | Research lead | |
| **Q4** | Is an anticipated Cox–Snell R² available from an admissible source (A1–A6)? Supply value, DOI + table/figure, population, endpoint, predictor set. If not, record **NOT ASSESSED** as the formal status. | Supervisor / research lead | |
| **Q5** | Given §6, is 303 acceptable **only** as an internal exploratory feasibility pilot with no predictive-adequacy claim? Confirm or reject in writing. | Supervisor | |
| **Q6** | Is the decision rule in [§9.3](#93-decision-rule-if-humans-later-supply-the-missing-inputs) ratified as pre-registered? | Research lead | |
| **Q7** | For a future independent-dataset assessment, which sizing method and which performance measures drive the target? | Statistician | |
| **Q8** | Confirm that L2 penalisation and nested resampling are **not** treated as remedies for the sample-size shortfall. | Research lead | |
| **Q9** | Who signs this record (name, role, date), and where is it filed in the approval ledger? | Maintainer | |
| **Q10** | How should the `gate-da/15` vs `gate-pt/02` sequencing inconsistency be resolved, and does it require an amendment or a note on the record? | Maintainer + supervisor | |

**Decision record (to be completed by a named human, not the agent):**

| Field | Value |
|---|---|
| Sample-size status determined | **[BLANK]** |
| Anticipated R²cs (if supplied) | **[BLANK]** |
| Criteria and tolerances adopted | **[BLANK]** |
| Relaxations and rationale | **[BLANK]** |
| Consequence for D-047 interpretation | **[BLANK]** |
| Name / role / date | **[BLANK]** |

---

## 14. References

| ID | Reference |
|---|---|
| **R1** | Riley RD, Ensor J, Snell KIE, Harrell FE Jr, Martin GP, Reitsma JB, Moons KGM, Collins G, van Smeden M. Calculating the sample size required for developing a clinical prediction model. *BMJ* 2020;368:m441. doi:10.1136/bmj.m441 |
| **R2** | Riley RD, Snell KIE, Ensor J, et al. Minimum sample size for developing a multivariable prediction model: Part II — binary and time-to-event outcomes. *Stat Med* 2019;38(7):1276–1296. doi:10.1002/sim.7992 |
| **R3** | Riley RD, Van Calster B, Collins GS. A note on estimating the Cox–Snell R² from a reported C statistic (AUROC) to inform sample size calculations for developing a prediction model with a binary outcome. *Stat Med* 2021;40(4):859–864. doi:10.1002/sim.8806 |
| **R4** | Riley RD, Debray TPA, Collins GS, Archer L, Ensor J, van Smeden M, Snell KIE. Minimum sample size for external validation of a clinical prediction model with a binary outcome. *Stat Med* 2021;40(19):4230–4251. doi:10.1002/sim.9025 |
| **R5** | van Smeden M, Moons KGM, de Groot JAH, Collins GS, Altman DG, Eijkemans MJC, Reitsma JB. Sample size for binary logistic prediction models: beyond events per variable criteria. *Stat Methods Med Res* 2019;28(8):2455–2474. doi:10.1177/0962280218784726 |
| **R6** | Van Houwelingen JC, Le Cessie S. Predictive value of statistical models. *Stat Med* 1990;9(11):1303–1325. doi:10.1002/sim.4780091109 |
| **R7** | Nagelkerke NJD. A note on a general definition of the coefficient of determination. *Biometrika* 1991;78(3):691–692. doi:10.1093/biomet/78.3.691 |
| **R8** | *pmsampsize*: calculates the minimum sample size required for developing a multivariable prediction model. R package version 1.1.3 (2023). CRAN; source `github.com/JoieEnsor/pmsampsize`, commit `ebbe7c9`. |
| **R9** | Pate A, Riley RD, Collins GS, van Smeden M, Van Calster B, Ensor J, Martin GP. Minimum sample size for developing a multivariable prediction model using multinomial logistic regression. *Stat Methods Med Res* 2023;32(3):555–571. doi:10.1177/09622802231151220 |
| **R10** | Pavlou M, Ambler G, Qu C, Seaman SR, White IR, Omar RZ. An evaluation of sample size requirements for developing risk prediction models with binary outcomes. *BMC Med Res Methodol* 2024;24:146. doi:10.1186/s12874-024-02268-5 |
| **R11** | Collins GS, Moons KGM, Dhiman P, et al. TRIPOD+AI statement: updated guidance for reporting clinical prediction models that use regression or machine learning methods. *BMJ* 2024;385:e078378. doi:10.1136/bmj-2023-078378 |
| **R12** | Moons KGM, Damen JAA, Kaul T, et al. PROBAST+AI: an updated quality, risk of bias, and applicability assessment tool for prediction models using regression or artificial intelligence methods. *BMJ* 2025;388:e082505. doi:10.1136/bmj-2024-082505 |
| **R13** | Genders TSS, Steyerberg EW, Alkadhi H, et al. A clinical prediction rule for the diagnosis of coronary artery disease: validation, updating, and extension. *Eur Heart J* 2011;32(11):1316–1330. doi:10.1093/eurheartj/ehr014 |
| **R14** | Genders TSS, Steyerberg EW, Hunink MGM, et al. Prediction model to estimate presence of coronary artery disease: retrospective pooled analysis of existing cohorts. *BMJ* 2012;344:e3485. doi:10.1136/bmj.e3485 |
| **R15** | Genders TSS, Coles A, Hoffmann U, Patel MR, Mark DB, Lee KL, Steyerberg EW, Hunink MGM, Douglas PS; CAD Consortium and PROMISE Investigators. The external validity of prediction models for the diagnosis of obstructive coronary artery disease in patients with stable chest pain: insights from the PROMISE trial. *JACC Cardiovasc Imaging* 2018;11(3):437–446. doi:10.1016/j.jcmg.2017.02.020 |

**Internal documents cited:** `gate-pt/02` (frozen protocol), `gate-pt/04` (results draft), `gate-da/15` (draft pre-registration), `blueprint/05` (methodology), `research/experiments/reporting.py`, `research/experiments/cleveland_d047_exploratory_plan.v0.1.json`, `research/source_materials/literature_review_status.csv` and `…_original.xlsx`.

---

## Appendix A — Reproduction

```bash
# deterministic checks only (standard library)
python3 scripts/verify_m2e1_sample_size.py

# optionally, also reproduce pmsampsize::cstat2rsq (needs numpy + scipy)
python3 scripts/verify_m2e1_sample_size.py --simulate
```

Expected: `All deterministic checks passed.` and exit code 0; any mismatch prints `[FAIL]` and exits 1. The script reads no project data, contains no patient records, and fits nothing to any dataset. Section letters in its output correspond to: A = published anchors, B = structural properties, C = D-047 scenario, D = C→R²cs simulation (optional), E = expected shrinkage at n = 303.

## Appendix B — `pmsampsize` source traceability

| Item | Location | Behaviour reproduced here |
|---|---|---|
| C1 shrinkage | `R/pmsampsize_bin.R` line 12 | `n1 <- ceiling(parameters/((shrinkage-1)*(log(1-(r2a/shrinkage)))))` |
| maxR²cs | lines 19–20 | `1 - exp(2*lnLnull/n1)`, which equals the prevalence-only expression because `E1/n1 = prevalence` |
| C2 optimism | lines 28–30 | `s = r2a/(r2a + 0.05*max_r2a)`, then the shrinkage expression with `s` |
| C3 proportion | line 39 | `ceiling(((1.96/0.05)^2)*(prevalence*(1-prevalence)))` |
| Error guard 1 | lines 6–9 | stop if `shrinkage < rsquared` |
| Error guard 2 | lines 23–26 | stop if `max_r2a < rsquared` |
| C→R²cs | `R/cstat2rsq.R` lines 2–24 | n = 10⁶; LP ~ N(0,1) non-events, N(√2·Φ⁻¹(C),1) events; `glm(y ~ LP)`; `1-exp(-(null.deviance-deviance)/n)`; seed 123456 |
| Rounding in the C path | `R/pmsampsize.R` (binary branch) | `rsquared <- round(cstat2rsq(...)$R.coxsnell, digits = 4)` |

## Appendix C — Corpus screen (all 25 papers)

Sweep of `literature_review_status.csv`, all 15 columns, case-insensitive. **No row reports a Cox–Snell or Nagelkerke R², a Riley-style sample size, a shrinkage estimate, or an events-per-parameter analysis.** "R²/Riley/shrinkage/EPV evidence" is therefore `none` throughout and the column is omitted. Source dataset as recorded in the sheet. **[AR]**

| ID | Supervisor status | Year | Source dataset (as recorded) | Usable as anticipated-R² source? |
|---|---|---:|---|---|
| P1 | APPROVED_GREEN | 2024 | Combined five public CAD datasets (UCI-derived) | No — no R²; merged cohorts, no single population |
| P2 | APPROVED_GREEN | 2024 | Heart Statlog / Cleveland / Hungary (Kaggle) | No — no R² |
| P3 | MAYBE_PINK | 2024 | Cleveland public portion + private Egyptian data | No — no R²; private cohort |
| P4 | APPROVED_GREEN | 2025 | BRFSS 2015 / Framingham / Z-Alizadeh Sani | No — no R² |
| P5 | APPROVED_GREEN | 2025 | Z-Alizadeh Sani (UCI-412) | No — different source; no R² |
| P6 | MAYBE_ORANGE | 2024 | Cleveland + Framingham | No — but states the n = 303 overfitting concern |
| P7 | APPROVED_GREEN | 2025 | Cleveland & Switzerland | No — no R² |
| P8 | MAYBE_ORANGE | 2025 | Z-Alizadeh Sani | No — no R² |
| P9 | APPROVED_GREEN | 2024 | Z-Alizadeh Sani | No — no R² |
| P10 | APPROVED_GREEN | 2026 | UCI Heart Disease + Kaggle CVD dataset | No — no R² |
| P11 | REJECTED_RED | 2026 | Private | No — private data |
| P12 | REJECTED_RED | 2025 | Private (on request) | No — private data |
| P13 | REJECTED_RED | 2024 | Private (I-PAD records) | No — private data |
| P14 | APPROVED_GREEN | 2026 | Cleveland / Z-Alizadeh Sani / Statlog / Framingham | No — no R² |
| P15 | APPROVED_GREEN | 2025 | Z-Alizadeh Sani + Framingham | No — no R² |
| P16 | REJECTED_RED | 2024 | UK Biobank (controlled access) | No — controlled access |
| P17 | REJECTED_RED | 2025 | PhysioNet waveform databases | No — ECG/other endpoint |
| P18 | REJECTED_RED | 2024 | Private + online calculator | No — private data |
| P19 | MAYBE_ORANGE | 2026 | Heart Statlog/Cleveland/Hungary, n = 1,190 | No — no R²; merged cohort |
| P20 | MAYBE_ORANGE | 2024 | PhysioNet Fantasia / INCART | No — ECG signals |
| P21 | MAYBE_ORANGE | 2025 | Cleveland (UCI) | No — no R² |
| P22 | REJECTED_RED | 2026 | Private hospital cohort | No — no R²; private data |
| P23 | MAYBE_ORANGE | 2025 | UCI Heart Disease (4 cohorts) | No — no R² |
| P24 | REJECTED_RED | 2025 | Private single-centre | No — private data |
| P25 | REJECTED_RED | 2026 | AngioCAD (Zenodo) | No — angiography dataset, different endpoint |

Status counts: 9 GREEN, 6 ORANGE, 1 PINK, 9 RED. **[AR]**

## Appendix D — Version

| Field | Value |
|---|---|
| Version | 1.0 (initial review draft, M2e.1) |
| Date | 2026-10-23 |
| Basis commit | `a0d4007` (merge of PR #36) |
| Supersedes | nothing |
| Change control | any future numeric change requires a dated amendment that names who changed it and why |
