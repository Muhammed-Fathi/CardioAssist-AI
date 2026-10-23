# M2e.1 — CAD Riley-Style Sample-Size Evidence and Adequacy Review (Review Draft)

> ## `NOT ASSESSED — PENDING HUMAN REVIEW`
>
> - **Status:** **REVIEW DRAFT — NO SAMPLE-SIZE DECISION TAKEN — NOT A GATE, APPROVAL, OR SUPERVISOR SIGN-OFF**
> - **Work item:** Issue #37, milestone **M2e.1** (sample-size evidence for the M2 Cleveland experiment)
> - **Scope:** documentation and arithmetic only. No data access, no model fitting of any kind (real or synthetic), no new experiment, no change to D-047.
> - **Gate PT P-3:** **CLOSED** · **P-1:** **PENDING** · **D-047:** unchanged, already executed, not re-analysed
> - **Prepared:** 2026-10-23 · **Version 2.1** (post-QA corrections plus the Issue #37 risk, framework, checklist and acceptance material, see [Appendix D](#appendix-d--revision-history)) · **Document type:** statistical evidence review (internal research record)

**This document does not approve a sample size, does not approve the experiment, does not make a clinical claim, and does not close any gate.** It states what can be verified arithmetically, what the examined literature does and does not supply, and what a named human must decide. Where the evidence does not support a number, the status is **NOT ASSESSED** and stays that way.

The sample-size quantities in this document are **conditional planning thresholds under stated assumed tolerances**. They are not clinical performance verdicts, not estimates of future model performance, and not decisions about the study.

---

## 0. Reading guide

### 0.1 Evidence labels

| Label | Meaning |
|---|---|
| **[AR]** | **Agent-verified — repository.** Checked against a committed file at the base commit (paths given). |
| **[AA]** | **Agent-verified — arithmetic.** Recomputed deterministically from published formulae; reproducible via `scripts/verify_m2e1_sample_size.py` or by hand from [Appendix E](#appendix-e--documentation-only-verification-record). |
| **[LIT]** | **Literature claim**, primary source cited by DOI in [§18](#18-references). The *depth* to which each source was actually read is stated in [§0.6](#06-evidence-provenance-what-was-actually-read). |
| **[XTR]** | **Extraction-level finding.** Based on the supervisor's literature spreadsheet and the CSV extraction derived from it — i.e. recorded metadata and summaries, **not** verified against the papers' full texts. |
| **[MR]** | **Maintainer-reported** aggregate, carried forward from `04_…REVIEW_DRAFT.md`. Not independently reproduced from protected local output. |
| **[SC]** | **Hypothetical sensitivity scenario.** An arithmetic "what if", *not* an adopted assumption and *not* an input to any decision. |
| **[BRIEF]** | **Maintainer-written instruction** in the PR #38 review threads or the correction briefs. Used only where the Issue #37 body itself was unreadable (**[GAP]**, §11.4). |
| **[GAP]** | **Not available / not established.** Must not be filled by inference. |
| **[BLANK]** | Intentionally empty. A human completes it; the agent must not prefill it. |

### 0.2 What this document is

A reviewable evidence package answering one question: **can the sample size of the M2 Cleveland experiment be judged adequate?** It:

1. states the frozen analysis inputs, why the parameter count is 8, and what 8 does and does not represent ([§2](#2-frozen-inputs)–[§3](#3-why-p--8-and-not-5));
2. records the Riley binary-outcome methodology from primary sources, separating the three published criteria from the additional approximate criterion ([§4](#4-the-riley-framework-for-binary-outcomes));
3. reports the numerical verification actually performed ([§5](#5-numerical-verification));
4. reports the structural finding that governs everything else, with the break-even behaviour shown at full precision ([§6](#6-the-decisive-result-that-does-not-depend-on-r²cs));
5. defines what an admissible external anticipated Cox–Snell R² would have to be, and reports what the examined sources contain and do not contain ([§7](#7-the-externally-anticipated-coxsnell-r²-what-would-be-admissible-and-what-was-found));
6. presents clearly-labelled hypothetical scenarios so a reviewer can see the decision landscape **without** any of them being adopted ([§8](#8-hypothetical-sensitivity-scenarios-sc-not-assumptions-not-decisions));
7. records the status determination, a non-binding proposal for recording a future decision, implications for a future independent-dataset assessment, and governance findings ([§9](#9-status-determination)–[§11](#11-governance-findings));
8. lists the questions requiring human scientific review, with blank approval fields ([§13](#13-questions-requiring-human-scientific-review));
9. assesses the risks that bear on any **future independent-dataset** assessment — target harmonisation, measurement timepoints, referral bias, cohort overlap, UCI-411/412 identity, missingness and distribution shift — as an evidence matrix with four explicit dispositions ([§14](#14-independent-dataset-research-risk-assessment));
10. records a framework-based **TRIPOD+AI / PROBAST+AI** assessment, explicitly distinguished from a completed PROBAST+AI judgement ([§15](#15-methodological-framework-assessment-tripodai-and-probastai));
11. provides a **next-gate reviewer checklist** with blank sign-off fields, and an **Issue #37 acceptance matrix** recording exactly what is and is not complete ([§16](#16-next-gate-reviewer-checklist)–[§17](#17-issue-37-acceptance-matrix-and-filename-reconciliation)).

### 0.3 What this document deliberately does **not** do

- It does **not** derive an anticipated R² from any observed metric of D-047, including AUROC 0.8271 (primary), 0.8292 (logistic regression), 0.8211 (random forest), or any fold-level value. This is prohibited by the frozen protocol and by `04_…REVIEW_DRAFT.md` §7.4. **[AR]**
- It does **not** fit any model, real or synthetic, and does **not** run simulations. An earlier revision of the companion script did fit logistic models to synthetic samples to reproduce a C-statistic→R² conversion; that pathway has been **removed** and the associated numbers **withdrawn** ([§0.7](#07-corrections-in-this-revision), [Appendix D](#appendix-d--revision-history)).
- It does **not** run, rerun, re-score, re-split, or re-select anything; it does **not** re-open the experiment.
- It does **not** modify `research/experiments/**` (runner, reporting status string, plan), the frozen protocol (`gate-pt/02`), or the results draft (`gate-pt/04`). **[AR]**
- It does **not** record approval. Every approval field is `[BLANK]`.
- It does **not** claim that the wider CAD literature contains no suitable source, nor that the 25 papers' full texts have been searched and found empty. Both claims would exceed what was actually done.
- It does **not** treat its own arithmetic as a substitute for a statistician's review of the criteria chosen, the tolerance values used, or the population assumptions.
- It does **not** assign any PROBAST+AI risk-of-bias or applicability rating, and does not present framework-based concerns as a completed assessment ([§15](#15-methodological-framework-assessment-tripodai-and-probastai)).
- It does **not** treat any second dataset as suitable for independent validation, and does not assume that datasets can be pooled ([§14](#14-independent-dataset-research-risk-assessment)).

### 0.4 Files changed by this deliverable

| File | Change | Status |
|---|---|---|
| `docs/research/gate-pt/05_m2e1_cad_riley_sample_size_adequacy_REVIEW_DRAFT.md` | **new** | This review. |
| `docs/research/gate-pt/README.md` | edited | Registers document 05 in the Gate PT index, and corrects one pre-D-047 sentence that the merged record no longer supports (§11.6). |
| `scripts/verify_m2e1_sample_size.py` | **new** | **PROPOSED SCOPE EXCEPTION — see [§0.5](#05-scope-discrepancy-documentation-only-issue-vs-this-diff).** Strictly deterministic arithmetic; fits nothing, simulates nothing. |

**Deliberately unchanged:** `research/experiments/reporting.py` (its `sample_size_sensitivity.status` string remains `NOT_ASSESSED_NO_HUMAN_REVIEWED_ANTICIPATED_COX_SNELL_R2_ASSUMPTIONS`), `research/experiments/cleveland_d047_exploratory_plan.v0.1.json`, `docs/research/gate-pt/02_…PROTOCOL_PROPOSED.md`, `docs/research/gate-pt/04_…REVIEW_DRAFT.md`, `docs/DECISIONS.md`, `research/source_materials/**`, and all backend/frontend/contract code. **No decision-register entry was added because no decision was taken.** **[AR]**

### 0.5 Scope discrepancy: documentation-only Issue vs this diff

**Issue #37 asks for a documentation-only change.** This PR contains three files, one of which — `scripts/verify_m2e1_sample_size.py` — is executable code and is therefore **outside a strict reading of that authorisation**.

| Position | Statement |
|---|---|
| Why the script exists | Every number in this review can be recomputed without trusting prose, and the recomputation is checkable by a reviewer in one command. |
| Why that is not self-authorised | The agent cannot broaden Issue #37. The exception is **proposed**, not claimed. |
| Current status of the script | **PROPOSED — PENDING MAINTAINER DECISION.** It is deterministic arithmetic only: no data access, no model fitting, no simulation, no experiment. |
| Documentation-only fallback | [Appendix E](#appendix-e--documentation-only-verification-record) records every input and every computed output so that a reviewer can verify the numbers with a calculator. If the exception is refused, **delete the script** and keep Appendices A and E; the PR then reduces to two documentation files. |
| Recorded as an open question | **Q11** in [§13](#13-questions-requiring-human-scientific-review). |

This discrepancy is also stated in the pull-request body. It is not resolved by this document.

### 0.6 Evidence provenance: what was actually read

Distinguishing what was read in full from what was read as an abstract or from a secondary description is part of the evidence.

| Source | Depth of reading |
|---|---|
| Riley et al., *BMJ* 2020;368:m441 | **Full text** (open-access PDF), including the criteria, the maximum-R² expression and the worked examples. |
| `pmsampsize` v1.1.3 source (commit `ebbe7c9`) | **Full source** of `R/pmsampsize_bin.R`, `R/cstat2rsq.R`, and the binary branch of `R/pmsampsize.R`. |
| Riley, Van Calster & Collins, *Stat Med* 2021 (sim.8806) | **Full text** (open access), including the five-step conversion and its stated precondition. |
| Riley et al., *Stat Med* 2021 (sim.9025, external validation) | **Abstract and landing page**; input requirements and worked-example figures taken from the abstract. Full text not read. |
| van Smeden et al., *Stat Methods Med Res* 2019 | **Not read directly.** The minimum-MAPE expression is used as reported in Riley 2020 and as restated in the 2024 evaluation (Pavlou et al.); this is a **secondary** attribution and is flagged where used. |
| Pavlou et al., *BMC Med Res Methodol* 2024;24:146 | **Abstract** (open access); the direction-of-error findings quoted are from the abstract. |
| Van Houwelingen & Le Cessie 1990; Nagelkerke 1991 | **Not read.** Cited as the origin of the shrinkage and generalised-R² constructions respectively, via the secondary sources above. |
| Genders et al. 2011 / 2012 / 2018 (CAD models) | **Abstract and landing page**; the discrimination, prevalence and calibration-slope statements quoted are abstract-level. Full texts not read. |
| The 25 supervisor-selected papers | **Extraction metadata only** (`literature_review_original.xlsx`, `literature_review_status.csv`). **No full text of any of the 25 was obtained or read.** |

Consequences are carried into [§7](#7-the-externally-anticipated-coxsnell-r²-what-would-be-admissible-and-what-was-found) and [§12](#12-limitations-of-this-review) rather than being left implicit.

### 0.7 Corrections in this revision

Version 2.0 corrects six substantive defects identified in independent scientific QA of revision 1, plus three methodological qualifications. They are listed with their resolutions in [Appendix D](#appendix-d--revision-history). In summary:

1. the fixed-n "expected shrinkage" helper used a formula that is **not** the inverse of criterion 1 and produced 0.8873 where the correct value is 0.9000 — replaced by a deterministic implicit inversion;
2. the optional `--simulate` pathway fitted logistic models to synthetic samples, which Issue #37 prohibits — **removed**, and the numbers that depended on it are withdrawn;
3. scenario rows labelled `0.209` while computing with `0.20884` are corrected, and the ceiling discontinuity at the break-even is now shown explicitly;
4. absence claims were made at full-text strength from extraction metadata — rescoped;
5. "lower bound" language applied to criteria that can err in either direction — corrected, and the additional criterion is now separated from the published three;
6. a decision rule was described as pre-registered although it was written after the experiment — relabelled, and its arbitrary 1.25 multiplier removed.

---

## 1. The question, and the answer in one page

### 1.1 The question

The frozen D-047 protocol requires a "Riley-style binary-model sample-size sensitivity analysis with explicit anticipated Cox–Snell `R²` assumptions … If those assumptions are not defensible, results are a software/research feasibility pilot only; no clinical predictive adequacy is claimed." — `gate-pt/02_…PROTOCOL_PROPOSED.md`, line 32. **[AR]**

So the question is not "is n = 303 a large number?" It is: **for 8 slope parameters in the reference-coded logistic candidate, 139 events and 164 non-events, is the development sample large enough under the Riley criteria, and if that cannot be established, what status must the experiment carry?**

### 1.2 The answer

| # | Statement | Status |
|---|---|---|
| 1 | The three published Riley binary-outcome criteria, implemented as in `pmsampsize` v1.1.3, are reproduced here: the worked examples match the paper to the participant (5,249 / 1,770 / 73). The additional minimum-MAPE example matches too (460.86 → 461). | **VERIFIED** **[AA]** |
| 2 | At n = 303 and event fraction 139/303 = 0.458746, the **outcome-proportion criterion alone requires 382 participants** at δ = 0.05. This value depends on neither R² nor the number of parameters. | **VERIFIED** **[AA]** |
| 3 | The **additional** minimum-MAPE criterion at p = 8 requires **459** participants for every value of the anticipated R². | **VERIFIED** **[AA]** |
| 4 | Because criterion 3 is independent of R² and of p, **the published three-criterion set cannot be satisfied at n = 303 for any R² and any parameter count**; adding criterion 4 makes p = 8 infeasible as well. | **VERIFIED** **[AA]** |
| 5 | Whether 303 is nevertheless acceptable *for this project's stated exploratory purpose* depends on tolerances and on an anticipated R² that no admissible source supplies. | **NOT ASSESSED — PENDING HUMAN REVIEW** |
| 6 | No eligible externally anticipated Cox–Snell R² was **identified** in the supervisor's spreadsheet/CSV extraction for the 25 papers, or in the specific external studies reviewed. Full-text verification of the 25 papers was **not** performed, and no statement is made about the wider CAD literature as a whole. | **NOT IDENTIFIED IN THE EXAMINED SOURCES** **[XTR]**, **[LIT]** — see [§7](#7-the-externally-anticipated-coxsnell-r²-what-would-be-admissible-and-what-was-found) |
| 7 | Under the protocol's own rule (line 32), unavailability of defensible assumptions means the D-047 results are a **feasibility pilot only**. Recording that consequence applies the frozen text; it is not a new decision. | **PROPOSED for human confirmation** |

**Read points 2–4 and 5 together.** The sample size is *structurally below the published criteria* on grounds that need no R² input. That is different from — and stronger than — "we cannot tell". It is also different from a GO/NO-GO decision, which remains human. And it is a statement about criteria at stated tolerances, not a measurement of clinical performance.

### 1.3 Why the answer is not a single number

The Riley framework has no single "required n"; it returns the maximum over criteria that each targets a different property (shrinkage, optimism, precision of the overall risk, precision of prediction error). Changing any one tolerance — shrinkage target, R² optimism allowed, width of the risk confidence interval, target MAPE — changes the answer. The framework also requires an **externally anticipated** R², which is a judgement about a model that does not yet exist. Both features are why the framework cannot be reduced to a rule of thumb, and why its output for this dataset is a *set of consequences*, not a pass mark.

---

## 2. Frozen inputs

| Input | Value | Source | Note |
|---|---:|---|---|
| Records | **303** | **[MR]** (D-047 run), consistent with **[AR]** protocol | Criteria use realised counts. |
| Positive cases (`num = 1..4`) | **139** | **[MR]** | 45.8746% |
| Negative cases (`num = 0`) | **164** | **[MR]** | 54.1254% |
| Event fraction used in the criteria, φ | **0.458746** | **[AA]** arithmetic from the two counts | **This is the historical source-cohort event fraction, not an established event proportion for any future clinical population** ([§2.1](#21-what-φ-is-and-is-not)). |
| Predictor fields | 5: `age`, `sex`, `cp`, `trestbps`, `restecg` | **[AR]** `gate-pt/02`, line 26 | |
| Slope parameters p | **8** | **[AR]** `gate-pt/02`, line 32; `reporting.py` | Reference-coded logistic candidate. See [§3](#3-why-p--8-and-not-5). |
| Shrinkage target S | **0.90** | **[LIT]** Riley 2020 default; `pmsampsize` default | A tolerance, not a law. |
| Optimism tolerance (Nagelkerke R²) | **0.05** | **[LIT]** Riley 2020 | |
| Outcome-proportion half-width δ | **0.05** | **[LIT]** Riley 2020 | 95% CI for φ within ±0.05. |
| Target MAPE | **0.05** | **[LIT]** van Smeden 2019, via secondary sources | Approximation stated for p ≤ 30. |
| Anticipated Cox–Snell R² | **[BLANK]** | — | The missing input. See [§7](#7-the-externally-anticipated-coxsnell-r²-what-would-be-admissible-and-what-was-found). |

Derived descriptives, repeated only for orientation (they are **not** sample-size justifications and were already recorded as such in `04_…REVIEW_DRAFT.md` §7.2): events per parameter 139/8 = **17.4**; non-events per parameter 164/8 = **20.5**; records per parameter 303/8 = **37.9**. **[AA]**

> The frozen protocol already states: "Reporting n/parameters or `139/8` is **not** a valid sample-size justification" (`gate-pt/02`, line 32). **[AR]** Nothing here reintroduces that rule under another name.

### 2.1 What φ is and is not

φ = 139/303 describes **who happens to be in this historical Cleveland benchmark**. It is not the expected prevalence in any future clinic, and it is not a design assumption for a future study. Every criterion in this document is therefore conditional on reproducing this cohort's composition. A future population with a different event proportion would move **all** of n₃, n₄ and maxR²cs, in either direction: n₃ and n₄ both rise as φ approaches 0.5, and maxR²cs peaks at 0.5.

This matters for reading §6: the statement "382 is required" means *382 is required to estimate an event proportion of about 0.46 to ±0.05*, which is a property of this cohort, not a universal constant.

---

## 3. Why p = 8 (and not 5)

### 3.1 The registered parameterisation

`gate-pt/02_…PROTOCOL_PROPOSED.md`, line 32, verbatim: **[AR]**

> "The five source fields imply **8 slope coefficients for a reference-coded LR**: age 1 + sex 1 + cp 3 + trestbps 1 + restecg 2."

The registered plan and the runner report the same count (`candidate_logistic_slope_parameters_after_reference_encoding: 8`). **[AR]**

### 3.2 What p = 8 represents — and what it does not

**p = 8 characterises one fitted reference-coded logistic regression**, not the full nested model-selection procedure that D-047 actually executed. That procedure compares candidate families (penalised logistic regression and a constrained random forest) and tunes hyperparameters inside each inner fold. Model-family choice and tuning consume information beyond the eight slopes of any single fit, and the Riley framework has no term for them.

Consequently:

- the numbers in this document are **conditional on the p = 8 logistic scenario**, which is the only parameterisation the protocol registers as a countable quantity **[AR]**;
- 8 is best read as a **partial, probably optimistic** description of the effective complexity of the selection procedure — but this document does **not** quantify the extra cost, because no authorised method for doing so is applied here;
- a reviewer who wants the sizing to reflect the selection procedure must say so explicitly and name a method (Q1).

### 3.3 Why the field count understates the parameter count

Sample size is driven by **parameters consumed**, not by the number of named variables. Counting five fields as five parameters understates the criterion-1 requirement by roughly 37% at every strength examined: at R²cs = 0.112 the requirement is 376 for p = 5 but 601 for p = 8 (ratio 1.6). **[AA]** The draft Gate DA protocol anticipated this trap: "five raw field names may encode more than five parameters after one-hot encoding; n = 303 does **not** automatically establish adequate statistical sample size or predictive accuracy" (`gate-da/15`, R-MD-02). **[AR]**

### 3.4 Would a different encoding help?

Arithmetically yes, practically no. `cp` and `restecg` are multi-category fields; collapsing them into binary indicators would reduce p but change the model and its interpretation, and would have to be pre-registered as a different analysis. Even p = 5 does not make 303 adequate under the published criteria — the outcome-proportion criterion binds independently at 382 ([§6.2](#62-the-outcome-proportion-criterion-binds-independently-of-r²)). **[AA]**

---

## 4. The Riley framework for binary outcomes

### 4.1 The published criteria, and the additional one

| ID | Criterion | Formula | What it targets | Source | Status |
|---|---|---|---|---|---|
| **C1** | Shrinkage | n₁ = ⌈p / ((S − 1)·ln(1 − R²cs/S))⌉, S = 0.90 | Expected uniform shrinkage ≥ S | Van Houwelingen & Le Cessie 1990; Riley 2020 | Published; returned by `pmsampsize` |
| **C2** | Optimism in Nagelkerke R² | s = R²cs/(R²cs + 0.05·maxR²cs); n₂ = ⌈p / ((s − 1)·ln(1 − R²cs/s))⌉ | Apparent vs adjusted R² difference ≤ 0.05 | Riley 2019 (Part II); Riley 2020 | Published; returned by `pmsampsize` |
| **C3** | Precision of the outcome proportion | n₃ = ⌈(1.96/0.05)²·φ(1 − φ)⌉ | 95% CI for the overall risk within ±0.05 | Riley 2020 | Published; returned by `pmsampsize` |
| **C4** | Precision of prediction error | n₄ = ⌈exp((−0.508 + 0.259·ln φ + 0.504·ln p − ln 0.05)/0.544)⌉ | Mean absolute prediction error (MAPE) ≈ 0.05 | van Smeden 2019, via Riley 2020 | **Additional, approximate**; *not* returned by `pmsampsize` |

with

> **maxR²cs = 1 − exp(2·[φ·ln φ + (1 − φ)·ln(1 − φ)])**

the largest Cox–Snell R² attainable for a binary outcome at outcome proportion φ (0.74829 here; the theoretical maximum over all φ is 0.75 at φ = 0.5). **[AA]**

**C1–C3 are one published set**; they are the three criteria `pmsampsize` returns together and they share a single derivation. **C4 is different in kind**: it is an additional precision target for prediction error, it is an approximation whose stated validity range is p ≤ 30, and it is *not* part of the `pmsampsize` output. It is reported here because it targets a property (individual-level prediction error) that C1–C3 do not, and because it happens to bind in this dataset. It is labelled **[AA]/[LIT]** rather than presented as part of the same package, and it is never used alone to characterise adequacy.

### 4.2 Direction of error: not uniformly conservative

An earlier revision described all values here as "lower bounds". That was wrong, and the error direction is not uniform: **[LIT]** (Pavlou 2024, abstract)

- the calibration/shrinkage-based formulae (C1–C3) can **underestimate** the sample size when the model is strong;
- the minimum-MAPE formula (C4) can **overestimate** it when the model is strong.

So each criterion can err in either direction depending on the true model strength and the tolerance chosen. The correct reading of [§6](#6-the-decisive-result-that-does-not-depend-on-r²cs) is therefore: **these are conditional formula estimates under stated tolerances, not a conservative bound and not a guaranteed minimum**.

### 4.3 What the criteria do and do not guarantee

They target **development-sample overfitting and precision**, at tolerances the analyst selects. They do **not** guarantee calibration in a new population, do not substitute for external validation, and do not address measurement error, case-mix shift or selection. Riley et al. present the calculation as a minimum planning target, not a certificate. **[LIT]**

Two structural properties matter for this dataset:

- **C3 targets the precision of the model intercept — in practice the overall outcome proportion — not discrimination.** It contains no predictor, no parameter count and no R², and therefore binds at a fixed value for every model of every size on this dataset. **[LIT]**, **[AA]**
- **C1 and C2 are monotone in opposite ways to intuition:** stronger assumed models require *smaller* samples. A reviewer who assumes a stronger model therefore lowers the requirement. This is precisely why the anticipated R² must come from outside the study rather than from the study's own results ([§7.3](#73-absolute-prohibition-observed-performance-of-this-model-or-its-benchmark)).

### 4.4 Implementation verified

The reference implementation used for checking is `pmsampsize` v1.1.3 (CRAN; source commit `ebbe7c9`, 2023-12-05). The formulas above are transcriptions of `R/pmsampsize_bin.R` lines 12, 28–30 and 39, and the maximum-R² expression at lines 19–20. **[AR]** Source traceability is tabulated in [Appendix B](#appendix-b--pmsampsize-source-traceability).

Two guards in that source are part of the methodology and were reproduced: the function stops if `shrinkage < rsquared` (the shrinkage target must exceed the anticipated R²) and if `max_r2a < r2a` (an anticipated R² above the attainable ceiling). **[AR]**

### 4.5 The C-statistic → R² conversion: documented, deliberately not executed

`pmsampsize` can accept a C-statistic instead of an R². Its implementation (`R/cstat2rsq.R`) **generates a million synthetic observations and fits a logistic calibration model to them**; the R² is then computed from that fit's likelihood ratio. **[AR]**

The methodological justification is Riley, Van Calster & Collins 2021, whose stated precondition is decisive for this project: the method obtains an anticipated R² from **a reported C statistic of an existing published model in the same field, evaluated at the outcome proportion of the target population**, and the authors advise using the *lowest* plausible C. **[LIT]** — full text read.

Two independent reasons mean this method is **not executed here**:

1. **Authorization.** Issue #37 prohibits real *and synthetic* model fitting. The conversion method as implemented *is* model fitting on synthetic data, so executing it would breach the work item's scope even though no patient data is involved. The method is therefore described as a documented reference only, and **no C→R² number is produced in this document**.
2. **Circularity.** Even where authorized, the conversion is not a licence to convert a model's own apparent AUROC into a planning input: the apparent AUROC of the model being sized is an output of the very fit whose stability is in question, so the sample-size calculation would depend on the result it is meant to constrain. This is the formal reason behind the prohibition in `04_…REVIEW_DRAFT.md` §7.4, independent of any suspicion about the specific D-047 numbers. **[AR]**, **[LIT]**

---

### 4.6 Applicability domain of the additional MAPE criterion

C4 is the least robust quantity in this document, so its domain is stated explicitly rather than implied:

| Boundary | Statement | Consequence here |
|---|---|---|
| Parameter count | The approximation is stated for **p ≤ 30**. | p = 8 is well inside; the guard is enforced in the companion script. |
| Model form | Derived for a **single binary outcome** logistic model with no interaction or penalisation term. | The registered candidate is L2-penalised, and the procedure compares families; C4 therefore describes an unpenalised single-fit approximation to a more complex procedure. |
| What it targets | **Mean absolute prediction error**, i.e. accuracy of individual predicted risks — not discrimination, not calibration slope. | C4 is not interchangeable with C1–C3; it binds here only because 459 > 382. |
| Estimation | Derived from simulation, so it is an **approximation with its own error**, reported to overestimate the requirement when the model is strong. **[LIT]** (Pavlou 2024) | Treated as one criterion among four, never as the sole basis for a conclusion. |
| Prevalence parameterisation | The formula is written in terms of the **outcome proportion φ**. When events exceed half the sample, the minority-class proportion is used, i.e. **φ\* = min(φ, 1 − φ)**, so that a cohort with 70% events is evaluated as its 30% complement rather than as a structurally different planning problem. | **This cohort has φ = 0.458746 < 0.5, so φ\* = φ and no transformation is applied.** C4 = 459 is therefore unaffected. Verified: φ\* = φ to machine precision, and C4(φ = 0.70) = C4(φ = 0.30) = 375 for illustration. **[AA]** |
| Provenance of the transformation | The symmetry convention is applied by published usage; the primary van Smeden 2019 text was **not read in full** ([§0.6](#06-evidence-provenance-what-was-actually-read)). | Recorded as **[LIT]-secondary**. It changes nothing for this cohort; it matters if the function is reused elsewhere. |

The practical points: (i) C4 = 459 is a property of an *unpenalised single fit*, so the true information requirement of the executed nested procedure is not smaller than this; (ii) no C4 number in this document was computed under a prevalence transformation, because none is needed at φ < 0.5; (iii) a reviewer who rejects the MAPE criterion entirely still faces C3 = 382 (§6.2).

---

## 5. Numerical verification

### 5.1 Published anchors reproduced exactly

| Check | Expected | Reproduced | Status |
|---|---:|---:|---|
| maxR²cs at φ = 0.05 | 0.32769 | 0.32769 | **PASS** |
| C1, p = 30, R²cs = 0.05, φ = 0.05, S = 0.90 | 5,249 | 5,249 | **PASS** |
| C2, same inputs | 1,770 | 1,770 | **PASS** |
| C3, φ = 0.05 | 73 | 73 | **PASS** |
| Final (max of the published three) | 5,249 | 5,249 | **PASS** |
| Additional criterion C4, p = 10, φ = 0.30, MAPE = 0.05 | 460.86 → 461 | 460.86 → 461 | **PASS** |
| maxR²cs at φ = 0.5 (theoretical ceiling) | 0.75000 | 0.75000 | **PASS** |

**[AA]** — reproduced by `python3 scripts/verify_m2e1_sample_size.py`.

### 5.2 Implementation cross-checks

| Check | Result |
|---|---|
| C1 decreases as R²cs rises, increases with p | **PASS** |
| Both `pmsampsize` error guards reproduced | **PASS** |
| C3 independent of p (identical at p = 3 and p = 8) | **PASS** |
| Implicit inversion of C1 round-trips: n(S(R²cs)) = 303 to 1e-3 | **PASS** (six values, [§6.4](#64-shrinkage-actually-achieved-at-n--303)) |
| At the exact C1 break-even the achieved shrinkage equals the 0.90 target | **PASS** to 1e-6 |
| Distinctness of the correct inversion from a plausible-looking wrong one | **PASS** (the naive expression differs from the criterion-1 inverse by > 0.01 at the break-even) |

**[AA]**

### 5.3 What verification does not establish

That the criteria are the right ones for this project; that the default tolerances are the right ones; that the anticipated R² is knowable; or that 303 records of a 1980s single-centre benchmark represent any target population. Verification covers the arithmetic and the transcription of published formulas — nothing else. **The methodological choice remains a human decision.** **[GAP]**

### 5.4 Withdrawn in this revision

Revision 1 reported a simulation-based reproduction of `pmsampsize`'s C→R² conversion (0.212115 against the published 0.2100957), a seed-sensitivity figure, and a table of C-statistic-derived R² values. **All of these depended on fitting logistic models to synthetic samples** and are withdrawn: they are not reproduced anywhere in version 2.0, and no derived claim now rests on them. The method itself remains documented in [§4.5](#45-the-c-statistic--r²-conversion-documented-deliberately-not-executed). **[AR]**

---

### 5.5 Analytical equality versus floating-point representation

The criterion-1 break-even solves 8/((0.90−1)·ln(1−R²/0.90)) = 303 and is **0.20884206294424718** to 17 significant digits. Analytically the real-valued requirement there is exactly 303. Evaluated in ordinary double precision, however, the arithmetic returns

> **303.00000000000006**

for which `math.ceil()` returns **304**. Nothing is wrong with either the formula or the arithmetic: the true value is an integer and the computed value differs from it by about **6×10⁻¹⁴**, i.e. a few units in the last place. A plain ceiling has no way to distinguish "303 exactly" from "303 plus representation noise", and so reports one participant more than the mathematics requires.

Both behaviours are recorded here rather than hidden:

| Evaluation | At the exact break-even | At R²cs = 0.20884 | At R²cs = 0.209 |
|---|---:|---:|---:|
| Real-valued requirement | 303.00000000000006 | 303.0034 | 302.7380 |
| Strict ceiling (`math.ceil`, `pmsampsize` behaviour) | **304** | 304 | 303 |
| Representation-aware ceiling | **303** | 304 | 303 |

**Why a guard is legitimate here, and why it is narrow.** The companion script adds `analytically_ceiled()`, which treats a value as analytically equal to the nearest integer only when the gap is within **8 units in the last place** — about 3.6×10⁻¹² at 303, or roughly 10⁻¹⁴ of a participant. That is a *representation* threshold, not a substantive rounding tolerance. It is twelve orders of magnitude smaller than the smallest shortfall discussed anywhere in this document (one record), so it cannot convert an insufficient sample size into a sufficient one. The regression checks demonstrate exactly that: at R²cs = 0.20884 (real 303.0034) both ceilings return **304**; at R²cs = 0.205 both return **310**; at R²cs = 0.170054 both return **382**; only at analytical equality do they diverge. **[AA]**

**Does any conclusion depend on this?** No. The disclosure matters for reproducibility, not for the science:

- criterion 1 is a knife-edge at exactly 303 either way, and it is the *only* criterion satisfied there;
- criteria 3 and 4 fail at 303 by 79 and 156 participants respectively, so the final requirement is 459 under every reading of the break-even;
- the review therefore states criterion-1 status at the break-even as "met, at exactly the available size" and does not rely on that fact for any adequacy claim.

Revision 1 reported 304 at the break-even without noting that the value was a representation artefact rather than a substantive shortfall. That was not wrong arithmetic, but it was an under-explained number; it is now explained and tested both ways.

---

## 6. The decisive result that does not depend on R²cs

### 6.1 The two R²-free numbers

| Quantity | Value | Depends on R²? | Depends on p? |
|---|---:|:---:|:---:|
| C3 — outcome-proportion precision (δ = 0.05) | **382** (real-valued 381.5448) | no | **no** |
| C4 — minimum MAPE (MAPE = 0.05) | **459** at p = 8 (real-valued 458.7802) | no | yes |

Since 382 > 303, and 459 > 303 at p = 8, **both criteria fail at the current sample size before any R² assumption is made.** **[AA]**

C4 varies with p: 2 → 128, 3 → 185, 4 → 242, 5 → 297, 6 → 352, 7 → 406, 8 → **459**, 9 → 512, 10 → 565. C4 is therefore satisfied at n = 303 only for p ≤ 5 — well below the registered 8. **[AA]**

### 6.2 The outcome-proportion criterion binds independently of R²

C3 = (1.96/0.05)²·φ(1 − φ) contains no parameter count and no R². At φ = 0.458746 it equals 381.5448, rounded up to **382**. Consequently:

- **No choice of anticipated R² can make the published three-criterion `pmsampsize` set satisfiable at n = 303.**
- **No reduction in the number of parameters can make it satisfiable either.** C3 is unchanged by p, so no positive p satisfies C1–C3 at n = 303.

This is the cleanest statement in the review, and it is available without any literature judgement about R². It does not by itself declare the study worthless: a reviewer may decide that ±0.05 precision on the overall risk is not required for an internal exploratory benchmark. But that decision is a **documented relaxation of a published criterion**, and must be recorded as such rather than presented as adequacy (Q3).

### 6.3 The full requirement as a function of the missing input

Required n at p = 8, φ = 0.458746, S = 0.90, MAPE = 0.05, δ = 0.05. "n₁" is shown before and after the ceiling so that the behaviour near the criterion-1 break-even is unambiguous. "Final" is the maximum of all four criteria. **[AA]**

| Anticipated R²cs | Nagelkerke-equivalent\* | real n₁ | ⌈n₁⌉ | n₂ | n₃ | n₄ | **Final** | Shortfall vs 303 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.050 | 0.067 | 1,399.62 | 1,400 | 205 | 382 | 459 | **1,400** | 1,097 |
| 0.075 | 0.100 | 919.42 | 920 | 202 | 382 | 459 | **920** | 617 |
| 0.100 | 0.134 | 679.22 | 680 | 199 | 382 | 459 | **680** | 377 |
| 0.11224 (15% of max) | 0.150 | 600.59 | 601 | 198 | 382 | 459 | **601** | 298 |
| 0.125 | 0.167 | 535.00 | 536 | 196 | 382 | 459 | **536** | 233 |
| 0.144 | 0.192 | 458.84 | 459 | 194 | 382 | 459 | **459** | 156 |
| 0.150 | 0.201 | 438.79 | 439 | 194 | 382 | 459 | **459** | 156 |
| 0.170054 | 0.227 | 382.00 | 382 | 191 | 382 | 459 | **459** | 156 |
| 0.20884 (2×10⁻⁶ below break-even) | 0.279 | 303.0034 | **304** | 187 | 382 | 459 | **459** | 156 |
| **0.20884206294424718** (exact break-even) | 0.279 | **303.0000** | **303** | 187 | 382 | 459 | **459** | 156 |
| 0.209 | 0.279 | 302.7380 | **303** | 187 | 382 | 459 | **459** | 156 |
| 0.250 | 0.334 | 245.83 | 246 | 182 | 382 | 459 | **459** | 156 |
| 0.300 | 0.401 | 197.30 | 198 | 176 | 382 | 459 | **459** | 156 |
| 0.500 | 0.668 | 98.65 | 99 | 150 | 382 | 459 | **459** | 156 |
| 0.748290 (attainable max) | 1.000 | 44.93 | 45 | 110 | 382 | 459 | **459** | 156 |

\* R²cs / maxR²cs at this event fraction; an interpretation aid only, not an approved input.

**On the three break-even rows.** The exact break-even solves 8/((0.90−1)·ln(1−R²/0.90)) = 303 and is **0.20884206294424718**; by construction the real-valued requirement there is exactly 303.000, so criterion 1 is met. Two-sided caution is warranted because the ceiling is discontinuous by a whole participant: at R²cs = **0.20884** the real-valued requirement is 303.0034, which **ceils to 304**, so criterion 1 is *not* met; at R²cs = **0.209** the real-valued requirement is 302.7380, which ceils to **303**, so it *is* met. Revision 1 displayed `0.209` while computing with `0.20884`, which silently crossed that discontinuity. All three rows are now shown with the value actually used. **[AA]**

**Three readings of the table:**

1. **Below R²cs ≈ 0.144**, criterion 1 dominates and the requirement exceeds 459; at R²cs = 0.05 it is 1,400 — 4.6× the available records.
2. **Between 0.144 and the ceiling**, the requirement is flat at **459** because criterion 4 binds. Raising the assumed model strength beyond ≈0.14 buys nothing.
3. **Criterion 1 alone is met at 303 for R²cs ≥ 0.2088421** (27.9% of the attainable R²); criteria 3 and 4 are still not met, so the final requirement remains 459 for every row in this table.

### 6.4 Shrinkage actually achieved at n = 303

Criterion 1 answers "how large must n be for the expected shrinkage to reach S?" The complementary question — "if the anticipated adjusted R² is R²cs and n is fixed at 303, what shrinkage should we expect?" — is the **same equation solved for S instead of n**:

> n = p / ((S − 1)·ln(1 − R²cs/S)) **solved for S**, with R²cs and n held at the values used in the criterion-1 calculation.

There is no elementary closed form for S; it is obtained by deterministic bisection ([§5.2](#52-implementation-cross-checks)). Note that this *is* the correct inversion: the earlier, simpler-looking expression `S = 1 + p/(n·ln(1 − R²cs))` is **not** equivalent and drops a factor of S, which is why revision 1 reported 0.8873 at the break-even where the correct value is exactly 0.9000. **[AA]**

| Anticipated R²cs | Shrinkage S achieved at n = 303, p = 8 | Interpretation |
|---:|---:|---|
| 0.050 | **0.663** | heavy overfitting; coefficients retain about two-thirds of their fitted value |
| 0.075 | **0.750** | substantial overfitting |
| 0.100 | **0.802** | moderate overfitting |
| 0.11224 | **0.821** | |
| 0.150 | **0.862** | |
| 0.208842 (the criterion-1 break-even) | **0.900** | by construction the target is exactly met |
| 0.250 | **0.917** | |
| 0.300 | **0.932** | |

**How to read this table.** The shrinkage target S = 0.90 is met at n = 303 *only if* the anticipated adjusted Cox–Snell R² is at least ≈0.209. For a model of modest strength (R²cs ≈ 0.10) the same 303 records would be expected to deliver S ≈ 0.80, i.e. coefficients shrinking by about a fifth in new data of the same type. These are conditional expectations from the criterion-1 equation — not predictions about D-047, whose own shrinkage was not estimated here and must not be inferred from these rows. **[AA]**

### 6.5 What would have to change

Each row is arithmetic. **None of these is a recommendation**; each would be a documented methodological decision requiring human approval. **[AA]**

| Lever | Current | Threshold implied by n = 303 | Comment |
|---|---:|---:|---|
| C3 precision δ | ±0.050 | **±0.0561** | 303 gives δ = 0.056108 |
| C4 target MAPE | 0.050 | **0.0627** | 303 gives 6.27% mean absolute prediction error at p = 8 |
| C1 shrinkage S | 0.90 | **0.900 exactly** at R²cs = 0.208842 | S = 0.85 is delivered from R²cs ≥ 0.13719; S = 0.80 from R²cs ≥ 0.09894 |
| Parameters p | 8 | **≤ 7** at R²cs = 0.20884; **≤ 8** at R²cs = 0.209 | criterion-3 is unaffected by p and still fails |
| Sample size n | 303 | **459** (all four criteria) / **382** (published three) | +156 or +79 records — not available within this fixed public benchmark |

Required R²cs for criterion 1 to be satisfied at n = 303, by parameter count (S = 0.90): p = 3 → 0.08484; 4 → 0.11130; 5 → 0.13691; 6 → 0.16168; 7 → 0.18565; **8 → 0.20884**; 9 → 0.23128; 10 → 0.25299. **[AA]**

> The parameter-budget statement must be read at the value actually used: at R²cs = 0.20884 the real-valued requirement for p = 8 is 303.0034, which ceils to 304, so **p = 8 fails** and the budget is p ≤ 7. At R²cs = 0.209 it ceils to 303, so **p = 8 passes**. Both statements are true of their own inputs; applying one to the other would cross the discontinuity. Neither changes the conclusion, because criterion 3 fails for every p.

### 6.6 Consequence under the frozen protocol's own wording

`gate-pt/02`, line 32 states that if the anticipated-R² assumptions are not defensible, "results are a software/research feasibility pilot only; no clinical predictive adequacy is claimed." **[AR]**

Two facts are now established: (a) no admissible anticipated R² was identified — see [§7](#7-the-externally-anticipated-coxsnell-r²-what-would-be-admissible-and-what-was-found); and (b) the criteria fail for every hypothetical value at the stated tolerances. The protocol's fallback clause therefore applies on both grounds. Recording that is **PROPOSED** for human confirmation, not self-executed: this draft does not alter the banner on the D-047 results, which already reads `INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED`. **[AR]**

---

## 7. The externally anticipated Cox–Snell R²: what would be admissible, and what was found

### 7.1 What the input is, and who owns it

An **anticipated Cox–Snell R²** is a *pre-modelling* judgement about how much variation a model of this predictor set is expected to explain in the target population. It is an assumption about a model that does not yet exist, not a summary of a fitted one. It can legitimately come from:

- a published model with **the same outcome definition**, **comparable predictor set**, **comparable case-mix / event fraction**, reporting R²cs or Nagelkerke R² directly; or
- the Riley 2021 conversion from **a published model's C statistic evaluated at the target event proportion** (subject to [§4.5](#45-the-c-statistic--r²-conversion-documented-deliberately-not-executed)); or
- a **documented expert elicitation** with a stated protocol, panel and consensus rule.

The choice belongs to the research lead/supervisor, not to the agent. The agent's job is to state the admissibility test, search what is available, and report what was and was not found.

### 7.2 Admissibility test applied to every candidate

| ID | Condition | Why it is required |
|---|---|---|
| **A1** | Outcome definition matches (`num = 0` vs `1..4`; historical angiography-referenced CAD presence) | R² is outcome-specific; a 30-day-event or ≥50%-stenosis-on-CTA endpoint is a different quantity |
| **A2** | Predictor set comparable to `age, sex, cp, trestbps, restecg` (8 parameters) | R² rises mechanically with additional predictors; borrowing from a richer model overstates expected fit |
| **A3** | Event fraction comparable to 0.4587 | maxR²cs and every criterion depend on φ; a 23%-prevalence cohort is a different planning problem |
| **A4** | Measurement timepoint compatible with a resting pre-angiography decision | otherwise the model answers a different clinical question |
| **A5** | R²cs or Nagelkerke R² reported, **or** a published C convertible under Riley 2021's precondition | otherwise no number exists |
| **A6** | Provenance checkable (DOI, table/figure locatable by a reviewer) | an unverifiable number is not evidence |

### 7.3 Absolute prohibition: observed performance of this model or its benchmark

Deriving the anticipated R² from D-047's own apparent AUROC (0.8271 primary, 0.8292 logistic regression, 0.8211 random forest **[MR]**), or from any fold-level or resampled value, would be circular and is prohibited by `04_…REVIEW_DRAFT.md` §7.4. **[AR]**

For the avoidance of doubt, this revision contains **no** C-statistic→R² conversion of any kind, for D-047 or for any published model: the conversion method requires synthetic model fitting ([§4.5](#45-the-c-statistic--r²-conversion-documented-deliberately-not-executed)), which this work item does not authorise, and using D-047's own C would additionally be circular. Nothing in [§8](#8-hypothetical-sensitivity-scenarios-sc-not-assumptions-not-decisions) is derived from a C-statistic.

### 7.4 Screen of the supervisor-selected corpus — extraction level

**Source of truth:** `research/source_materials/literature_review_original.xlsx` (sheet *Literature Review*, 25 papers, rows 6–30) and its extraction `research/source_materials/literature_review_status.csv` (25 rows × 15 columns). The presentation (`project_presentation*`) is **not** used as a status source. **[AR]**

**Method.** Whole-row, case-insensitive term sweep across all 15 columns of the CSV, plus the equivalent sweep of the workbook sheet. **[AR]**

**Scope of the claim.** The 15 columns contain bibliographic fields, the recorded algorithms, the recorded dataset references, the recorded results and the recorded limitations. They are an **extraction, not the papers**. A finding of "no mention in the extraction" therefore supports only: *the extraction does not record such a quantity*. It does not establish that the authors never computed one, and it does not constitute a full-text absence claim. **[XTR]**

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

**What this supports.** In the recorded extraction, none of the 25 papers is described as reporting a Cox–Snell or Nagelkerke R², a Riley-style sample-size calculation, a shrinkage estimate, or an events-per-variable analysis; seven papers use Cleveland in some form; six report a 303-record dataset (the Z-Alizadeh Sani cohort used by P5, P8 and P9 also has 303 records); and P6 explicitly raises the n = 303 overfitting concern ("Small Cleveland dataset (n = 303). Potential overfitting risk at 98.4% on a small benchmark"). **[XTR]**

**What this does not support.** It does not show that no paper *contains* an R², and it is **not** a statement about the wider CAD literature. The extraction is a summary prepared for literature-review purposes; a paper reporting R² in a supplementary table without it reaching the summary would be invisible to this screen.

**Conclusion drawn here is limited accordingly:** *no eligible anticipated R² was identified in the supervisor's extraction*, and a reviewer who wants certainty must check the full texts (Q4). Full screen, all 25 papers: [Appendix C](#appendix-c--extraction-screen-all-25-papers).

### 7.5 External CAD prediction literature examined

The purpose here is narrow: **do the specific published CAD models that were examined offer a defensible anticipatory R² for a five-field resting panel at ~46% event fraction?** Three CAD-consortium publications were consulted at abstract/landing-page level. **[LIT]** — abstracts only, full texts not read.

| Source | Cohort / endpoint | Event fraction | Published discrimination | Fails |
|---|---|---:|---|---|
| Genders 2011, *Eur Heart J* (CAD Consortium updating/extension) | 2,260 patients, CT/catheter angiography, obstructive CAD | 58.4% (1,319/2,260) | c = 0.79 (updated); 0.82 (extended) | A2 (symptoms/risk factors/CAC), A3 (58.4% vs 45.9%), A5 (no R² reported) |
| Genders 2012, *BMJ* (pooled cohorts, basic/clinical/extended models) | 18 hospitals, ≥50% stenosis | mixed by setting | cross-validated c = 0.77 / 0.79 / 0.88 | A2, A3, A5 |
| Genders 2018, *JACC Cardiovasc Imaging* (PROMISE external validation) | 3,468 patients, ≥50% stenosis on CTA | 23% (779/3,468) | c = 0.69 / 0.72 / 0.86; calibration slope < 1 | A2, A3 (23% vs 45.9%), A5 |

Two points from these three sources remain relevant beyond the admissibility test:

- **Calibration slopes below 1 are reported in external CAD data even for well-known models** (PROMISE reports a calibration slope < 1 overall, with the clinical model over-predicting at higher probabilities, most pronounced in women). Overfitting is an empirical phenomenon in this literature, not a theoretical worry. **[LIT]**
- **Discrimination moves substantially with predictor set**: 0.69 → 0.72 → 0.86 as chest-pain type gives way to risk factors and then to coronary calcium. Borrowing an R² from a calcium-augmented model to plan a five-field model would be indefensible even if an R² had been reported. **[LIT]**

**Scope of this claim.** These are three studies selected because they are the CAD prediction models most likely to be relevant; they are **not** a systematic review, and **no claim is made that no suitable source exists in the wider CAD literature**. What can be said is narrower and sufficient for the status determination: *among the sources examined, none passes the admissibility test*.

### 7.6 Outcome of the search

> **Anticipated Cox–Snell R²: NOT ASSESSED — PENDING HUMAN REVIEW.**
>
> No eligible value was identified in (a) the supervisor's spreadsheet/extraction for the 25 papers, or (b) the specific external studies examined. No value has been assumed, borrowed, interpolated, or reverse-engineered. Full-text verification of the 25 papers was not performed, and the wider CAD literature was not systematically searched. **[XTR]**, **[LIT]**, **[GAP]**

A reviewer may still supply one. [§13](#13-questions-requiring-human-scientific-review) lists exactly what would have to accompany it.

---

## 8. Hypothetical sensitivity scenarios **[SC]** (not assumptions, not decisions)

> **Banner.** Everything in this section is arithmetic contingent on an input that has **not** been approved. The values below are not the project's assumptions, are not a basis for GO, and must never be quoted as if the project had adopted them. Their purpose is to let a reviewer see how the answer moves.

### 8.1 The scenario grid

Repeated from [§6.3](#63-the-full-requirement-as-a-function-of-the-missing-input); the "consequence" column is phrased as an arithmetic consequence, not a decision.

| Scenario | R²cs **[SC]** | Final n required | Consequence under the stated criteria |
|---|---:|---:|---|
| Very weak model | 0.050 | 1,400 | requirement 4.6× available records |
| Weak model | 0.075 | 920 | 3.0× |
| Low-moderate | 0.100 | 680 | 2.2× |
| 15% of attainable R² | 0.11224 | 601 | 2.0× |
| Moderate | 0.150 | 459 | 156 records more than available |
| Just below the C1 break-even | 0.20884 | 459 | C1 itself needs 304 |
| At the C1 break-even | 0.208842063 | 459 | C1 met (real-valued 303.000); C3 and C4 not met |
| Rounded above the break-even | 0.209 | 459 | C1 met (302.738 → 303); C3 and C4 not met |
| Strong | 0.250 | 459 | same floor; strength no longer helps |
| Attainable maximum | 0.748290 | 459 | same floor |

**No scenario in this grid yields an adequate sample size under the stated criteria.** The consequences do not depend on which scenario a reviewer prefers — only the margin does.

### 8.2 What the flat floor means

Because C3 = 382 and C4 = 459 are R²-free, the entire plausible range of anticipated R² collapses onto the same conclusion. A reviewer who wants to argue that 303 is adequate must therefore argue **against a criterion or a tolerance**, not **about a model's expected strength**. That is a much narrower and more explicit disagreement, and it is the kind of disagreement that can be recorded and reviewed.

### 8.3 How these scenarios must and must not be used

| Permitted | Prohibited |
|---|---|
| Showing a reviewer the decision landscape | Quoting any row as "the project's assumed R²" |
| Comparing the margin across plausible strengths | Selecting the row that produces a favourable verdict |
| Showing that the conclusion is insensitive to R² | Using any row to argue that D-047 is adequate |
| Sensitivity of the *thresholds* to S, δ, MAPE, p | Feeding any row into a report, gate or claim |

---

## 9. Status determination

### 9.1 The recorded status

| Field | Value |
|---|---|
| Sample-size adequacy | **`NOT ASSESSED — PENDING HUMAN REVIEW`** |
| Machine-readable status (unchanged, already in the runner) | `NOT_ASSESSED_NO_HUMAN_REVIEWED_ANTICIPATED_COX_SNELL_R2_ASSUMPTIONS` **[AR]** `research/experiments/reporting.py` |
| R²-independent structural finding | `PUBLISHED_CRITERIA_INFEASIBLE_AT_N_303` — established by C3 = 382 for every p, and C4 = 459 at p = 8 **[AA]** |
| Anticipated R²cs | `NOT SUPPLIED — NOT IDENTIFIED IN THE EXAMINED SOURCES` |
| Decision | **none taken**; no approval recorded; no gate action |

The two statements are consistent, not contradictory: *we cannot assess adequacy* **and** *the stated criteria cannot be met here* are both true, and the second is the reason the first will not resolve by better guessing.

### 9.2 Three-part verdict

**(a) VERIFIED** — the arithmetic and the transcription of the published criteria; the extraction-level literature screen; the absence of an eligible R² *in the sources examined*.

**(b) NOT ASSESSED** — whether 303 is adequate for the project's *own* stated purpose under *its own* chosen tolerances, and whether an admissible anticipated R² exists outside those sources.

**(c) CONDITIONAL FACT** — under the stated defaults (S = 0.90, optimism 0.05, δ = 0.05, MAPE = 0.05) and p = 8 on this cohort's event fraction, no anticipated R² makes the four criteria satisfiable at 303; the minimum is 459, and the published three alone require 382. This holds for this event fraction and these tolerances only.

### 9.3 A post-experiment proposal for recording a future decision — NOT pre-registered

**Provenance first.** D-047 was executed before this document existed. Nothing in this section can therefore be pre-registration for D-047, and it must not be described as such. An earlier revision of this document did describe a rule here as "pre-registered"; that label was wrong and has been removed. A rule written after seeing results cannot control bias for those results; it can only structure a later human decision.

**Status:** **UNAPPROVED PROPOSAL.** Not binding, not ratified, not a gate criterion. It becomes usable only if a named human ratifies it (Q6), and it would be binding on *future* studies only if ratified before their data analysis.

**Withdrawn element.** Revision 1 proposed a three-band classification using a multiplier of 1.25 (≤ n, ≤ 1.25n, > 1.25n). **That multiplier had no methodological derivation** — it was an editorial convenience, and no source in [§18](#18-references) supplies it. Rather than retain an arbitrary threshold with a caveat, it is **removed**. What remains is descriptive recording with no automatic classification.

Proposed recording procedure (descriptive only):

1. Record the inputs actually used: anticipated R²cs **and its provenance**, p, φ, S, δ, MAPE.
2. Compute C1, C2, C3, C4; record the real-valued and ceiling forms of each, and the maximum.
3. Record the available n and the ratio max/n — as a **descriptive** quantity, with no banding.
4. Record which criteria are met and which fail, each with its tolerance.
5. Record any relaxation (waived criterion, changed tolerance, substituted analysis) with **who, when and why**, in the approval ledger.
6. A named human determines the status. No threshold in this document assigns one automatically.
7. The anticipated R² must arrive with: the numeric value, the source (DOI + table/figure), the population and endpoint it refers to, the predictor set it refers to, and a statement of why A1–A6 hold. Incomplete submissions are returned, not completed by the agent.

### 9.4 What would constitute a defensible adequacy finding — and why none of it is met

A defensible "adequate" finding would require all of: an eligible R² (§7); criteria met or a documented relaxation (§9.3); the relaxation signed by a named human; and the interpretation bounded to the stated population. **None of these exists.** The status therefore remains `NOT ASSESSED`, and the operative research description of D-047 remains *internal exploratory feasibility*, as the protocol already says. **[AR]**

---

## 10. Implications for independent-dataset assessment (no experiments conducted)

### 10.1 Two different questions

Development sizing (this document) asks whether the model can be estimated stably. **Validation sizing** asks whether a fitted, locked model can be *evaluated* precisely in a new dataset. They use different methods, different inputs and different targets, and neither substitutes for the other. **[LIT]**

### 10.2 The applicable validation method requires inputs this project does not yet have

Riley et al. 2021 (external validation, binary outcome) size a validation study from: target standard errors for each performance measure, the anticipated event proportion in the validation population, the anticipated (mis)calibration, the variance of the linear predictor in that population, and — for net benefit — the risk thresholds of interest. In their worked example the **calibration-slope criterion drove the sample size** (177 events / 9,835 participants at 1.8% prevalence), not discrimination. **[LIT]** — abstract-level.

For any future external dataset here, no target can be computed until that dataset is named, its event proportion established, and its anticipated miscalibration stated. **Status: NOT ASSESSED for every candidate dataset; no dataset has been approved.** **[GAP]**

### 10.3 What this implies concretely

| Implication | Consequence for planning |
|---|---|
| Precision targets are driven by the calibration slope, not AUROC alone | A future validation plan must pre-specify calibration measures and their target standard errors, not only discrimination |
| Event count matters more than total n | A small-cohort site (for example 123 records with 8 source-target negatives in Switzerland, per `gate-da/15`) cannot support a conventional discrimination or calibration claim — `gate-da/15` itself anticipates this. **[AR]** |
| Development performance is not validation performance | Calibration slopes < 1 in external CAD data (PROMISE) are the expected pattern, not an anomaly. **[LIT]** |
| 303 records cannot be "reused" as external validation of a model developed on the same 303 records | circular and prohibited (`validation_status` lifecycle; P-5 remains **NOT MADE — prohibited**) **[AR]** |

### 10.4 Arithmetic illustration only (not a target, not a recommendation)

At the historical event fraction 0.458746, an events-based target of 100 corresponds to ≈ 218 participants and 200 to ≈ 436 — plain arithmetic conversions, shown only for order of magnitude. They are **not** output from the validation method above, are not a substitute for it, and must not be adopted as a target without a proper calculation in the eventual validation protocol. **[AA]**, **[SC]**

### 10.5 Non-consequences

No external validation was performed, attempted, planned or implied. No candidate external dataset was accessed. P-5 remains **NOT MADE — prohibited**. D-047 remains a single-source internal benchmark. **[AR]**

---

## 11. Governance findings

### 11.1 Sequencing: the two governing documents disagree

`gate-da/15_…_DRAFT.md` (draft pre-registration) requires, at item 1 of its sample-size policy: **"Document the calculation and decision before executing any model."** **[AR]**

`gate-pt/02_…_PROTOCOL_PROPOSED.md` (the frozen protocol under which D-047 ran) requires the Riley-style analysis in **"the first report"** — i.e. after execution. **[AR]**

D-047 was executed before this analysis existed. Under `gate-pt/02` that timing is permitted; under `gate-da/15` it would not have been. **This is a documentation inconsistency to be resolved by a human, not a breach to be quietly repaired, and it must not be presented as either.** It is recorded because a reviewer comparing the two documents will notice it, and because the resolution determines the sequencing of any future model execution. → **Q10**

### 11.2 Scope discrepancy

The documentation-only authorisation in Issue #37 is not strictly satisfied by a diff that adds a Python script. This is recorded in [§0.5](#05-scope-discrepancy-documentation-only-issue-vs-this-diff) and raised as Q11. The agent has not broadened the authorisation, and the script carries an explicit deletion fallback.

### 11.3 No sample-size policy in the methodology blueprint

`docs/blueprint/05_RESEARCH_METHODOLOGY_AND_APPROVAL_GATES.md` contains **no** sample-size policy: searches for `riley`, `sample size` and `events per` return only the §6 subgroup rule (cells need ≥ 30 patients and ≥ 10 events per class, otherwise counts only) and TRIPOD+AI reporting. **[AR]** The operative policy lives in the two protocol documents instead, which is how the inconsistency in §11.1 arose. A one-paragraph policy pointer in blueprint 05 would prevent recurrence — **PROPOSED**, not done here.

### 11.4 Issue thread inaccessible

`gh issue view 37` and the issue API returned **HTTP 403**; the web view returned **404**. **[GAP]** The issue body and any discussion in it are therefore **not** cited as evidence anywhere in this document. The task requirements used here come from the maintainer's written instructions in the PR review threads and the correction brief, not from the issue text. If the issue contains an additional requirement (for example a reviewer-specified tolerance), this review has not seen it. → **Q12**

### 11.5 One pre-D-047 sentence corrected in the Gate PT index

`docs/research/gate-pt/README.md` previously stated that "No signed clinical study plan, real model fit or clinical performance exists at this point." That sentence is no longer accurate: an internal exploratory model run has been executed and is recorded in `gate-pt/04`, merged with PR #36. The sentence is corrected to distinguish (i) the absence of any signed clinical study plan and of any supervisor-approved, externally validated or clinical performance, from (ii) the existence of one completed **internal exploratory** run under the `INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED` banner.

The correction is limited to that historical claim. It does **not** alter: the decision-register entry for D-047, which remains `PENDING_EXPLICIT_HUMAN_RATIFICATION`; the frozen protocol; the reported results; or any gate status. It records what the merged record already shows and nothing more. **[AR]**

### 11.6 Nothing was approved, closed, or changed

No gate was closed. No approval was recorded. No code, plan, protocol, result or source file was modified. This change set touches only the three files listed in [§0.4](#04-files-changed-by-this-deliverable). **[AR]**

---

## 12. Limitations of this review

1. **Arithmetic, not statistics.** Verification covers published formulas and their transcription. It does not establish that the Riley criteria are the appropriate frame for this project.
2. **Default tolerances are defaults.** S = 0.90, optimism 0.05, δ = 0.05, MAPE = 0.05 are published defaults, not project decisions. A reviewer may ratify different values, which changes every number ([§6.5](#65-what-would-have-to-change)).
3. **The anticipated R² is absent.** Every n in [§6](#6-the-decisive-result-that-does-not-depend-on-r²cs) and [§8](#8-hypothetical-sensitivity-scenarios-sc-not-assumptions-not-decisions) is conditional. None estimates the truth.
4. **Error direction is not uniform.** The published C1–C3 formulae can underestimate the requirement for strong models, while the approximate C4 can overestimate it there; these are conditional formula estimates, not bounds. **[LIT]** (Pavlou 2024)
5. **C4 is an approximation**, stated for p ≤ 30, and is attributed here to van Smeden 2019 **via secondary sources** — the primary paper was not read in full ([§0.6](#06-evidence-provenance-what-was-actually-read)).
6. **φ is a historical cohort fraction**, not a target-population prevalence ([§2.1](#21-what-φ-is-and-is-not)). Sampling variability in φ is not propagated into the criteria.
7. **p = 8 describes the reference-coded logistic candidate**, not the nested LR/RF selection procedure; the extra complexity of model-family choice and tuning is not quantified here ([§3.2](#32-what-p--8-represents--and-what-it-does-not)).
8. **No account of missing data, measurement error, or case-mix heterogeneity.** These reduce the effective information available; ignoring them is optimistic.
9. **The corpus screen is extraction-level.** It searched a summary, not the papers; full texts of the 25 papers were not obtained ([§7.4](#74-screen-of-the-supervisor-selected-corpus--extraction-level)).
10. **The external literature check is purposive, not systematic.** Three CAD studies were examined; no systematic search was performed and no absence claim is made about the wider literature.
11. **Penalisation is not a substitute.** L2 regularisation constrains the fitted coefficients; it does not create information. The formal confirmation that no penalisation setting is being treated as a sample-size remedy is a human action (Q8).
12. **No claim about the historical cohort's representativeness.** Nothing here speaks to whether a 1980s single-centre Cleveland cohort is clinically transportable; that is a separate and larger question already flagged in `04_…REVIEW_DRAFT.md` §8.
13. **This review is not a statistical analysis plan.** It is an evidence input to one; it does not replace review by a statistician.
14. **The risk matrix in §14 is a documentation-level synthesis.** It draws on audit evidence recorded elsewhere in the repository and on official source descriptions; it is not a new data-level audit, and it cannot establish record-level facts such as whether any patient sits at exactly 50% stenosis.
15. **§15 is not a PROBAST+AI assessment.** No signalling question was formally scored, no domain was rated, and no overall risk-of-bias judgement exists. The section names concerns so that a real assessment can start from evidence.
16. **The Issue #37 acceptance matrix in §17 rests on maintainer briefs, not on the issue text**, which remained unreadable (403/404). A requirement present only in the issue would be invisible here.

---

## 13. Questions requiring human scientific review

Each question has a blank decision field. The agent must not prefill any of them.

| # | Question | Owner | Decision **[BLANK]** |
|---|---|---|---|
| **Q1** | Is p = 8 the correct sizing basis (reference-coded logistic candidate), or should the additional complexity of the nested LR/RF selection procedure be represented explicitly by a named method? | Research lead / statistician | |
| **Q2** | Is the four-criterion set (C1–C4) the adopted frame, the published three (C1–C3), or another named subset? | Research lead / statistician | |
| **Q3** | If a subset, which criteria are waived and what tolerances apply (S, optimism, δ, MAPE)? Record who decided, when and why. | Research lead | |
| **Q4** | Is an anticipated Cox–Snell R² available from an eligible source (A1–A6)? Supply value, DOI + table/figure, population, endpoint, predictor set. If not, record **NOT ASSESSED** as the formal status. Alternatively, authorise a full-text check of the 25 papers so that the extraction-level screen can be upgraded. | Supervisor / research lead | |
| **Q5** | Given §6, is 303 acceptable **only** as an internal exploratory feasibility pilot with no predictive-adequacy claim? Confirm or reject in writing. | Supervisor | |
| **Q6** | Is the posting of a recording procedure in §9.3 acceptable as a non-binding proposal, given that it was written after D-047 was executed and is **not** pre-registration? | Research lead | |
| **Q7** | For a future independent-dataset assessment, which sizing method and which performance measures drive the target? | Statistician | |
| **Q8** | Confirm that L2 penalisation and nested resampling are **not** treated as remedies for the sample-size shortfall. | Research lead | |
| **Q9** | Who signs this record (name, role, date), and where is it filed in the approval ledger? | Maintainer | |
| **Q10** | How should the `gate-da/15` vs `gate-pt/02` sequencing inconsistency be resolved — amendment, or a note on the record? | Maintainer + supervisor | |
| **Q11** | **Scope discrepancy:** does the maintainer accept `scripts/verify_m2e1_sample_size.py` as an authorised exception to the documentation-only Issue, or should it be deleted in favour of [Appendix E](#appendix-e--documentation-only-verification-record)? | Maintainer | |
| **Q12** | Issue #37 could not be read by the agent (403/404). Do the maintainer's instructions captured in the review threads and correction brief fully represent the issue's requirements? | Maintainer | |
| **Q13** | Which dataset, if any, is to be pursued for a future independent-dataset assessment, and under which target-compatibility ruling (H-01)? Or is the question closed for now? | Supervisor + research lead | |
| **Q14** | Given §14.2, is any currently available dataset capable of serving as independent validation, or must the project treat external validation as blocked until a new, audited source is acquired? | Supervisor + data owner | |
| **Q15** | Who performs the formal PROBAST+AI assessment and the TRIPOD+AI checklist, and when? §15 records concerns only and assigns no rating. | Independent assessors | |
| **Q16** | What is the exact filename Issue #37 requests for this document? Confirm either that name (one `git mv` plus one link update, §17.4) or the current canonical path. | Maintainer | |

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

## 14. Independent-dataset research risk assessment

This section answers a question the sample-size arithmetic cannot: **if this line of work ever moves to a second dataset, what would undermine the claim?** It is a documentation-level synthesis of evidence already recorded in the repository. It is **not** a data-level audit, **not** an external validation, and **not** a decision that any dataset is suitable.

### 14.1 Disposition vocabulary

Every row receives one **primary** disposition. Where a verified finding contains an open sub-item, the sub-item is named explicitly in the same cell rather than being allowed to disappear behind the primary label (for example: the same-cohort finding for UCI-411/412 is verified, while its single `Cath` discordance stays unresolved). The vocabulary is deliberately blunt so that no item can be quietly treated as settled.

| Disposition | Meaning |
|---|---|
| **VERIFIED** | Established from an official source, an audit record, or repository evidence, and adequate for planning. |
| **UNRESOLVED** | A specific question is open, an audit has produced a discordance, or the available evidence does not settle it. Not a guess; not a no. |
| **NOT ASSESSED** | The question has not been examined at the required level (for example, no data-level audit, or the enabling field does not exist in the released schema). |
| **HUMAN DECISION REQUIRED** | The evidence is sufficient to describe the options, but choosing among them is a scientific/governance act that no agent may perform. |

### 14.2 Risk matrix

| # | Risk | Evidence recorded in this repository | Disposition | Consequence for a future independent-dataset assessment |
|---|---|---|---|---|
| **R1** | **Target harmonisation: `>50%` (UCI-45) versus `≥50%` (UCI-412/411)** | The historical `num` description gives 0 = <50%, 1 = >50%; the UCI-412/411 pages define CAD as ≥50% narrowing. The register records the **wording difference as VERIFIED** and states explicitly that it does **not** establish whether any record sits at exactly 50% or how such a record was coded (H-01, `gate-da/03`). Approved dispositions are limited to *identical / reconciled / related-but-not-identical / unresolved*, and until a ruling exists, pooling is prohibited. **[AR]** | **UNRESOLVED** | Cross-dataset results must be described as evaluation across **related labels whose boundary compatibility is unresolved**. They cannot be called external validation of a common target, and cannot be pooled. |
| **R2** | **Measurement dates and prediction-timepoint compatibility** | The historical cohorts are 1980s data (`heart-disease.names`, 1988); DS-2 is a single-centre cohort of its own era. The conventional 14-attribute processed schema recorded in `gate-da/01` and `gate-da/03` contains **no measurement-date or visit-date field**; whether any date information exists in the 76-attribute raw files has **not** been audited. The prediction moment itself is not frozen — the per-feature "knowable before the angiography decision" rulings are open (DQ-SCI-3) and the front-end prediction moment is open (DQ-INT-2). **[AR]** | **NOT ASSESSED** | A validation study must pre-specify the prediction moment and show that each predictor is knowable at it. With no per-record dates, **temporal ordering within a cohort cannot be demonstrated** from the released fields; any claim of a clinically realistic timepoint rests on the source's data-collection description, not on the data. |
| **R3** | **Referral and selection bias** | Every candidate cohort is an **angiography-referred, case-enriched** sample. DS-2 records 216/303 ≈ 71% CAD (source-reported); Cleveland records 139/303 = 45.9% events **[MR]**. Phase 0 §F-6 restricts any score to a benchmark-cohort statement and forbids absolute-probability or population-screening claims (`gate-da/01` §5, `gate-da/03` H-05). **[AR]** | **VERIFIED as a structural limitation**; magnitude **NOT ASSESSED** | A second angiography cohort reproduces the same selection mechanism rather than removing it. Independence of *dataset* does not imply independence of *selection*; a future claim must name the referral pathway, not just the data source. |
| **R4** | **Source/cohort overlap** | `gate-da/01` §5 states that **no pair of acquirable datasets is yet proven independent**: DS-2/DS-2b are the same cohort by source-supported provenance; Statlog (DS-3) is a **suspect duplicate** of Cleveland with unknown overlap; cross-cohort duplicates inside UCI-45 cannot be ruled out from listings. Identifier-free data limit what can ever be proven (DQ-SCI-5). **[AR]** | **UNRESOLVED** | "External validation" is a **conditional, audit-gated** claim. Any future protocol must show a passed overlap audit and must state that independence is *evidenced*, not assumed from filenames or publishers. |
| **R5** | **UCI-411 versus UCI-412 cohort identity and possible duplication** | Both files contain **303 records**; the local read-only audit compared **56 shared columns** and found **303/303 matched rows in identical positions** and **303/303 unordered matches**, with `LAD`, `LCX`, `RCA` present only in the extension. Both official pages name the same creators and the same CAD definition, and the 411 page describes itself as an *extension* of the 412 dataset. One `Cath`-versus-artery discordance remains unresolved (302 consistent, 1 not); it is explicitly **not** to be corrected, relabelled, or interpreted as a clinical misdiagnosis. **[AR]** (`gate-da/10` §3) | **VERIFIED same cohort**; the single discordance **UNRESOLVED** | UCI-411 must **never** be counted as additional patients and can never serve as independent validation of a UCI-412 model. The 303 rows must not be summed with any other 303 to claim 606 subjects. |
| **R6** | **Missingness and site-specific distribution shift** | The local availability audit records, under the conservative zero-as-unavailable rule: Cleveland 303/303 on every pre-specified panel; Hungary 294 records with 292 resting-complete and 261 lab-complete; Switzerland 123 records with 120 resting-complete but **0** lab-complete (its 123 cholesterol zeros are third-party-documented as not measured); VA Long Beach 200 records with 143 resting-complete (`gate-da/14`). Feature definitions, units and era differ across sites (H-06, H-07), and `oldpeak` units remain unverified (DQ-SCI-4). **[AR]** | Availability **VERIFIED** for the named panels; transportability **NOT ASSESSED** | Missingness is **site-structured**, not random: a cohort can be large and still contribute almost no analysable records at a given measurement stage. A future protocol must pre-specify the analysis stage and report stage-specific denominators, not total n. |
| **R7** | **Implications for a future independent-dataset assessment** | Combining R1–R6: no candidate pair is proven independent, no target compatibility ruling exists, no per-record timepoint evidence exists, and every cohort shares the angiography-referral selection mechanism. Validation sizing also requires its own method and inputs ([§10](#10-implications-for-independent-dataset-assessment-no-experiments-conducted)). Several cohorts are too small for a conventional claim — Switzerland has 8 source-target-negative records, a point `gate-da/15` already anticipates. **[AR]** | **HUMAN DECISION REQUIRED** | The choice of whether to pursue independent-dataset assessment at all, which cohort(s) if so, and under which target-compatibility ruling, is a scientific decision for the supervisor and research lead (Q13, Q14). No agent may preselect it. |

### 14.3 What this matrix establishes — and what it does not

**Establishes:** (i) the D-047 cohort's own results cannot be externally validated against any currently available dataset without a prior overlap and target-compatibility ruling; (ii) independent dataset ≠ independent selection, so a second angiography cohort addresses transportability only partially; (iii) the strongest single technical finding in the matrix is that **UCI-411 is verified to be the same 303 patients as UCI-412**, which forecloses one obvious-looking validation path.

**Does not establish:** whether a suitable independent dataset exists anywhere (no systematic search was performed; **[GAP]**); whether the threshold difference at H-01 changes any record's label in practice (unverifiable without record-level stenosis percentages); or whether the historical cohorts transport to any contemporary population.

### 14.4 Standing prohibitions restated

No dataset was downloaded, opened, or inspected for this section. Nothing here authorises pooling, harmonisation, external validation, or a second experiment. P-5 remains **NOT MADE — prohibited**. The `validation_status` lifecycle is untouched.

---

## 15. Methodological-framework assessment: TRIPOD+AI and PROBAST+AI

### 15.1 What this section is, and what it is not

An earlier revision listed both frameworks as references only, which did not meet the requirement that they inform the review. This section records **framework-based concerns** item by item.

> **This is not a completed PROBAST+AI assessment.** PROBAST+AI requires trained assessors to answer **34 signalling questions (16 for model development, 18 for model evaluation)** across four domains — *participants and data sources; predictors; outcome; analysis* — plus **six applicability items**, and then to assign domain-level and overall judgements of *low / high / unclear*. **[LIT]** (R11, R12) **No domain judgement and no overall risk-of-bias rating is assigned here**, because assigning one would require a formal, documented, assessor-led procedure that has not taken place, and because a rating produced by the agent would be exactly the kind of fabricated endorsement this project forbids.

The purpose here is narrower: record which domains already raise documented concerns, so that a future formal assessment starts from evidence rather than from a blank page.

### 15.2 What each framework contributes

| Framework | Structure | How it is used here |
|---|---|---|
| **PROBAST+AI** | Four domains — participants and data sources; predictors; outcome; analysis — with 16 development and 18 evaluation signalling questions, six applicability items, and low/high/unclear judgements. **[LIT]** | Used as the organising structure for §15.3. **No ratings assigned.** |
| **TRIPOD+AI** | 27 main items: title (1), abstract (2), introduction (3–4), methods (5–17, including outcome 8, predictors 9, sample size 10, missing data 11, analysis 12a–12g), open science (18), patient and public involvement (19), results (20–24), discussion (25–27). **[LIT]** | Used to identify **reporting gaps that would block a submission**, not to certify compliance. Full item-by-item completion is a human task (Q15). |

### 15.3 Framework-based concerns

Statuses below are **framework-based concerns**, not PROBAST+AI judgements.

| Theme | Framework anchor | What the record shows | Concern raised? | What would resolve it |
|---|---|---|---|---|
| **Population and participant selection** | PROBAST+AI domain 1 / TRIPOD+AI items 5–6 | Angiography-referred, case-enriched, historical cohorts; no population sampling; selection mechanism shared by every candidate dataset (§14.2 R3). | **Yes** — applicability concern, structural | A stated target population with an explicit referral pathway, and a cohort whose selection matches it |
| **Predictor availability and measurement timing** | PROBAST+AI domain 2 / TRIPOD+AI item 9 | The five-field resting panel is pre-specified on availability grounds; per-feature "knowable before the decision" rulings are open (DQ-SCI-3); no per-record dates (§14.2 R2); `oldpeak` units unverified for other sites. | **Yes** — timing and availability | A frozen prediction moment plus a per-feature availability table ruled by a clinician |
| **Outcome definition and reference standard** | PROBAST+AI domain 3 / TRIPOD+AI item 8 | The endpoint is historical angiography-referenced CAD presence, binarised 0 vs 1–4; the `>50%` vs `≥50%` wording difference is verified and unresolved (H-01, §14.2 R1); the outcome is not a future event, and no time horizon exists. | **Yes** — reference-standard compatibility across sources | An H-01 ruling (*identical / reconciled / related-but-not-identical / unresolved*) recorded per dataset |
| **Sample size and overfitting risk** | PROBAST+AI domain 4 / TRIPOD+AI item 10 | §6: criteria 3 and 4 fail at n = 303 for any anticipated R²; criterion 1 requires R²cs ≥ 0.2088; expected shrinkage at n = 303 is ≈0.80 if R²cs ≈ 0.10 (§6.4). No anticipated R² was available (§7). | **Yes** — documented deficit, not a matter of opinion | A ratified anticipated R² plus an explicit tolerance decision (Q2–Q4) |
| **Validation and calibration evidence** | PROBAST+AI domain 4 (evaluation) / TRIPOD+AI items 20–24 | Internal nested-CV aggregates only; three of four LR calibration slopes estimable; no external cohort; calibration diagnoses described as descriptive, with no recalibration performed (`gate-pt/04`). | **Yes** — no external validation exists at all | A separate, audit-gated validation protocol (§14, §10) |
| **Reporting transparency and missing information** | TRIPOD+AI items 2–19 | The internal report carries sanitised aggregates and explicit claim boundaries; but a TRIPOD+AI-formatted report does not exist, no abstract checklist is completed, and items 18 (open science) and 19 (patient and public involvement) have no recorded content. | **Yes** — reporting gaps | A TRIPOD+AI-mapped report, completed by a human against the full checklist |
| **Remaining requirements before a scientific or clinical claim** | all four domains | See the list in §15.4. | **Yes** | All of §15.4, none of which exists |

### 15.4 What remains before any scientific or clinical claim

1. A ratified scientific target and intended use (P-1), with the prediction moment frozen.
2. A target-harmonisation ruling for any cross-dataset statement (H-01).
3. A source-independence and overlap audit for any evaluation dataset (§14.2 R4).
4. An anticipated R² from an eligible source, or an explicit decision to proceed without one (§7; Q4).
5. An explicit tolerance decision for the sample-size criteria (Q2–Q3).
6. A TRIPOD+AI-mapped report of whatever is eventually claimed.
7. A **formal** PROBAST+AI assessment performed by trained assessors, with the signalling questions answered and domain judgements recorded.
8. Ethics/governance clearance appropriate to the data used.
9. Clinician approval of any wording shown to a user (P-4).

### 15.5 Explicit non-claims

No overall risk-of-bias rating has been produced. No domain has been rated low, high or unclear. No applicability judgement has been made. **PROBAST+AI and TRIPOD+AI are assessment tools, not approvals**, and nothing in this section constitutes certification, endorsement, or readiness for publication or clinical use.

---

## 16. Next-gate reviewer checklist

For use by a human at the next gate. **No row is signed, approved, or completed by the agent**, and the decision column is blank throughout. Status values reuse §14.1.

| # | Requirement | Evidence currently available | Outstanding evidence | Responsible human reviewer | Status | Decision / sign-off **[BLANK]** |
|---|---|---|---|---|---|---|
| **C1** | **Anticipated R² evidence decision** | Extraction-level screen of 25 papers; three external CAD studies examined; none eligible (§7) | An eligible value with DOI + table/figure, population, endpoint, predictor set and A1–A6 justification — **or** a recorded decision to proceed without one | Supervisor + research lead | **NOT ASSESSED** | |
| **C2** | **Predictor complexity (p) basis** | Registered 8 reference-coded logistic slopes explained and scoped (§3) | Decision on whether the nested LR/RF selection procedure requires an additional complexity allowance, and by which method | Research lead + statistician | **VERIFIED for p = 8**; procedure-level complexity **NOT ASSESSED** | |
| **C3** | **Accepted statistical tolerances** | Published defaults computed (S = 0.90, optimism 0.05, δ = 0.05, MAPE = 0.05) and their consequences (§6.5) | Ratification or replacement of each tolerance, with rationale | Research lead + statistician | **NOT ASSESSED** | |
| **C4** | **Sample-size interpretation** | R²-free result: C3 = 382, C4 = 459 at p = 8; criterion 1 needs R²cs ≥ 0.2088 (§6) | A written decision on whether 303 is acceptable *only* as a feasibility pilot, or which criterion is relaxed and why | Supervisor | **NOT ASSESSED** | |
| **C5** | **Target harmonisation (H-01)** | Wording difference verified; boundary existence/coding unverified; pooling prohibited (§14.2 R1) | A per-dataset ruling: identical / reconciled / related-but-not-identical / unresolved | Supervisor + clinician | **UNRESOLVED** | |
| **C6** | **Source independence and overlap** | DS-2/DS-2b same cohort verified; Statlog suspect duplicate; UCI-45 cross-site duplicates unruled (§14.2 R4–R5) | A passed overlap audit and an explicit statement of what independence is claimed | Research lead + data owner | **UNRESOLVED** | |
| **C7** | **Future validation protocol requirements** | Method and required inputs described (§10); no dataset approved | A separate validation protocol with pre-specified performance measures, target standard errors and one-shot evaluation | Statistician + supervisor | **NOT ASSESSED** | |
| **C8** | **TRIPOD+AI reporting completeness** | Internal report exists with claim boundaries; no TRIPOD+AI mapping | A completed TRIPOD+AI checklist for whatever is claimed (§15.3) | Research lead | **NOT ASSESSED** | |
| **C9** | **Formal PROBAST+AI assessment** | Framework-based concerns recorded (§15.3) | A formal assessor-led PROBAST+AI assessment with signalling questions answered and domain judgements | Independent assessors | **NOT ASSESSED** | |
| **C10** | **D-047 description and ratification status** | D-047 executed and recorded as internal exploratory (`gate-pt/04`); decision-register entry remains `PENDING_EXPLICIT_HUMAN_RATIFICATION` | Confirmation of how the completed internal run is to be described and whether it is ratified | Maintainer | **PENDING** | |
| **C11** | **Scope of this work item** | Documentation-only Issue; a verification script is included as a proposed exception (§0.5) | Accept or reject the exception (Q11) | Maintainer | **PROPOSED** | |
| **C12** | **Document naming** | Canonical path `05_m2e1_cad_riley_sample_size_adequacy_REVIEW_DRAFT.md`; exact Issue-requested filename unreadable (§17.3) | The exact requested filename, or confirmation that the canonical path is acceptable | Maintainer | **UNRESOLVED** | |

**Gate status attached to this checklist:** P-1 **PENDING**, P-3 **CLOSED**, D-046-EP **NOT APPROVED**, P-5 **NOT MADE — prohibited**. Completing any row does not by itself close a gate.

---

## 17. Issue #37 acceptance matrix and filename reconciliation

### 17.1 Basis of this matrix

The Issue #37 body could **not** be retrieved by the agent: `gh issue view 37` and the REST API return **HTTP 403**, and the web view returns **404** (§11.4). The maintainer has confirmed in review that the issue requires the deliverables mapped below. This matrix is therefore built from **two written maintainer briefs [BRIEF]** plus the merged repository evidence, and is **not** a direct reading of the issue text. Where a brief and the issue might differ, the discrepancy is flagged rather than smoothed over.

### 17.2 Deliverable matrix

| # | Issue #37 deliverable (as conveyed) | Where it is delivered | Status |
|---|---|---|---|
| **1** | Research the original Riley-style sample-size methodology for binary clinical prediction models from authoritative publications | §4 (criteria, formulas, sources), §5 (numerical verification against published worked examples), §7 (anticipation method), Appendix B (source traceability to `pmsampsize` v1.1.3) | **COMPLETE** |
| **2** | Examine the supervisor-selected literature using the **original spreadsheet and CSV extraction** as the status source, not the presentation | §7.4 (term sweep, scope limits), Appendix C (all 25 papers with recorded datasets), §0.6 (read-depth disclosure) | **COMPLETE at extraction level.** Full-text verification of the 25 papers is **NOT DONE** and is not claimed (Q4). |
| **3** | Use the established Cleveland context: 303 records, 139 positives, 164 negatives, five predictors → eight reference-coded slopes | §2 (inputs table), §3 (why p = 8, and what it does not represent), §2.1 (what φ is not) | **COMPLETE** |
| **4** | Investigate defensible externally anticipated Cox–Snell R² assumptions; cite sources; evaluate population, endpoint and predictor compatibility. **Never derive R² from observed AUROC** | §7.1–§7.2 (what would be admissible; A1–A6), §7.4 (corpus screen), §7.5 (external CAD models), §7.6 (outcome), §4.5 (why the C→R² route is not executed), §7.3 (prohibition) | **COMPLETE as an investigation.** Result is a documented negative: no eligible value identified. **The assumption itself remains `[BLANK]`** by design, not by omission. |
| **5** | Document shrinkage, precision, outcome-proportion and predictor-budget requirements; separate verified evidence from hypothetical scenarios and assumptions needing approval | §6.3–§6.4 (requirement tables, achieved shrinkage), §6.5 (levers), §8 (hypothetical scenarios with usage rules), §0.1 (evidence labels), §9.2 (three-part verdict) | **COMPLETE** |
| **6** | If evidence cannot justify a numerical decision, report **NOT ASSESSED / PENDING HUMAN REVIEW**; never fabricate an assumption to force GO | §1.2 rows 5–6, §9.1 (recorded status), §9.2, §13 (blank decision record) | **COMPLETE** |

**Additional requirements from the maintainer's second brief, now also delivered:**

| # | Requirement | Where it is delivered | Status |
|---|---|---|---|
| **A** | Independent-dataset research risk assessment: target harmonisation (`>50%` vs `≥50%`), measurement dates and timepoint compatibility, referral/selection bias, source overlap, UCI-411 vs UCI-412 identity, missingness and distribution shift, implications | §14 (risk matrix R1–R7 with four-way disposition) | **COMPLETE as documentation.** It rests on already-recorded audit evidence; no new data-level audit was performed. |
| **B** | Source-grounded TRIPOD+AI / PROBAST+AI assessment covering population, predictors and timing, outcome/reference standard, sample size, validation and calibration gaps, reporting transparency, remaining requirements | §15 (six themes plus a nine-item requirement list) | **PARTIAL BY DESIGN.** Framework-based concerns are recorded; a **formal** PROBAST+AI assessment with signalling questions and domain judgements is **NOT DONE** and must be performed by trained assessors (§15.1, Q15). |
| **C** | Next-gate reviewer checklist with requirement, available evidence, outstanding evidence, responsible reviewer, status, blank sign-off | §16 (C1–C12, all sign-off fields blank) | **COMPLETE.** No research approval marked completed. |
| **D** | Numerical edge case at the C1 break-even | §5.5 (analytical equality vs floating point) and §5.2/Appendix A (regression coverage with a representation-scale guard that cannot rescue genuinely insufficient sizes) | **COMPLETE** |
| **E** | MAPE approximation applicability domain, including the prevalence transformation above 0.5 | §4.6 | **COMPLETE** (with the symmetry convention attributed to secondary sources) |
| **F** | Documentation-only scope discrepancy kept visibly pending | §0.5, §11.2, Appendix E, Q11, checklist C11 | **PENDING HUMAN DECISION** — not resolved, not presented as authorised |

### 17.3 Incomplete or unresolved requirements — stated plainly

To avoid any impression of full completion, the following are **not** delivered:

| Item | Why | Consequence |
|---|---|---|
| Reading the Issue #37 text | 403/404 from the API and web view | Requirements are taken from maintainer briefs; if the issue contains a requirement absent from those briefs, it is unmet and unknown (Q12) |
| Full-text verification of the 25 supervisor papers | Not performed | The literature finding is extraction-level only (§7.4) |
| A formal PROBAST+AI assessment | Requires trained assessors and the full signalling-question set | §15 records concerns only; **no rating exists** |
| A completed TRIPOD+AI checklist | Requires the full 27-item instrument applied to a real report | Reporting gaps are named, not certified |
| Any eligible anticipated R² | None identified in the examined sources | Status remains `NOT ASSESSED — PENDING HUMAN REVIEW` |
| Any decision on tolerances, target harmonisation, or dataset independence | Human decisions | Checklist C3, C5, C6 remain open |
| Resolution of the filename discrepancy | See below | Needs the maintainer's exact requested name |

### 17.4 Filename discrepancy

The brief records that **Issue #37 requests a specific document filename**, while this package uses `05_m2e1_cad_riley_sample_size_adequacy_REVIEW_DRAFT.md`. The exact requested name could not be read by the agent (**[GAP]**, §11.4), so it is not guessed here.

| Aspect | Record |
|---|---|
| Canonical path used | `docs/research/gate-pt/05_m2e1_cad_riley_sample_size_adequacy_REVIEW_DRAFT.md` |
| Why this name | It follows the existing convention of the folder: numbered prefix, topic slug, and a status suffix matching siblings `01_..._NOT_APPROVED.md`, `02_..._PROPOSED.md`, `03_..._TEMPLATE.md`, `04_..._REVIEW_DRAFT.md`. **[AR]** |
| Inbound links | Two: the Gate PT index (`docs/research/gate-pt/README.md`) and the PR description. Both are single-line updates if the file is renamed. |
| Why not renamed now | The requested name is unknown; guessing would produce a file the maintainer did not ask for, and duplicating the document under two names would create exactly the second scientific report the brief forbids. |
| Ready-to-apply resolution | `git mv docs/research/gate-pt/05_m2e1_cad_riley_sample_size_adequacy_REVIEW_DRAFT.md <requested-name>` then update the one README link. One file, one link, no content change, no duplicate. |
| Who decides | Maintainer (Q16 / checklist C12) |

---

## 18. References

| ID | Reference | Read as |
|---|---|---|
| **R1** | Riley RD, Ensor J, Snell KIE, Harrell FE Jr, Martin GP, Reitsma JB, Moons KGM, Collins G, van Smeden M. Calculating the sample size required for developing a clinical prediction model. *BMJ* 2020;368:m441. doi:10.1136/bmj.m441 | Full text |
| **R2** | Riley RD, Snell KIE, Ensor J, et al. Minimum sample size for developing a multivariable prediction model: Part II — binary and time-to-event outcomes. *Stat Med* 2019;38(7):1276–1296. doi:10.1002/sim.7992 | Cited via R1 |
| **R3** | Riley RD, Van Calster B, Collins GS. A note on estimating the Cox–Snell R² from a reported C statistic (AUROC) to inform sample size calculations for developing a prediction model with a binary outcome. *Stat Med* 2021;40(4):859–864. doi:10.1002/sim.8806 | Full text |
| **R4** | Riley RD, Debray TPA, Collins GS, Archer L, Ensor J, van Smeden M, Snell KIE. Minimum sample size for external validation of a clinical prediction model with a binary outcome. *Stat Med* 2021;40(19):4230–4251. doi:10.1002/sim.9025 | Abstract |
| **R5** | van Smeden M, Moons KGM, de Groot JAH, Collins GS, Altman DG, Eijkemans MJC, Reitsma JB. Sample size for binary logistic prediction models: beyond events per variable criteria. *Stat Methods Med Res* 2019;28(8):2455–2474. doi:10.1177/0962280218784726 | Secondary (via R1, R10) |
| **R6** | Van Houwelingen JC, Le Cessie S. Predictive value of statistical models. *Stat Med* 1990;9(11):1303–1325. doi:10.1002/sim.4780091109 | Secondary |
| **R7** | Nagelkerke NJD. A note on a general definition of the coefficient of determination. *Biometrika* 1991;78(3):691–692. doi:10.1093/biomet/78.3.691 | Secondary |
| **R8** | *pmsampsize*: calculates the minimum sample size required for developing a multivariable prediction model. R package version 1.1.3 (2023). CRAN; source `github.com/JoieEnsor/pmsampsize`, commit `ebbe7c9`. | Full source (relevant files) |
| **R9** | Pate A, Riley RD, Collins GS, van Smeden M, Van Calster B, Ensor J, Martin GP. Minimum sample size for developing a multivariable prediction model using multinomial logistic regression. *Stat Methods Med Res* 2023;32(3):555–571. doi:10.1177/09622802231151220 | Abstract |
| **R10** | Pavlou M, Ambler G, Qu C, Seaman SR, White IR, Omar RZ. An evaluation of sample size requirements for developing risk prediction models with binary outcomes. *BMC Med Res Methodol* 2024;24:146. doi:10.1186/s12874-024-02268-5 | Abstract |
| **R11** | Collins GS, Moons KGM, Dhiman P, et al. TRIPOD+AI statement: updated guidance for reporting clinical prediction models that use regression or machine learning methods. *BMJ* 2024;385:e078378. doi:10.1136/bmj-2023-078378 | Abstract, plus the 27-item structure and the text of items 8–12 from the open-access record. The full checklist was **not** applied item by item. |
| **R12** | Moons KGM, Damen JAA, Kaul T, et al. PROBAST+AI: an updated quality, risk of bias, and applicability assessment tool for prediction models using regression or artificial intelligence methods. *BMJ* 2025;388:e082505. doi:10.1136/bmj-2024-082505 | Abstract and tool structure (four domains; 34 signalling questions, 16 development / 18 evaluation; six applicability items; low/high/unclear judgements). Full instrument **not** applied. |
| **R13** | Genders TSS, Steyerberg EW, Alkadhi H, et al. A clinical prediction rule for the diagnosis of coronary artery disease: validation, updating, and extension. *Eur Heart J* 2011;32(11):1316–1330. doi:10.1093/eurheartj/ehr014 | Abstract |
| **R14** | Genders TSS, Steyerberg EW, Hunink MGM, et al. Prediction model to estimate presence of coronary artery disease: retrospective pooled analysis of existing cohorts. *BMJ* 2012;344:e3485. doi:10.1136/bmj.e3485 | Abstract |
| **R15** | Genders TSS, Coles A, Hoffmann U, Patel MR, Mark DB, Lee KL, Steyerberg EW, Hunink MGM, Douglas PS; CAD Consortium and PROMISE Investigators. The external validity of prediction models for the diagnosis of obstructive coronary artery disease in patients with stable chest pain: insights from the PROMISE trial. *JACC Cardiovasc Imaging* 2018;11(3):437–446. doi:10.1016/j.jcmg.2017.02.020 | Abstract |

**Internal documents cited:** `gate-pt/02` (frozen protocol), `gate-pt/04` (results draft), `gate-da/15` (draft pre-registration), `blueprint/05` (methodology), `research/experiments/reporting.py`, `research/experiments/cleveland_d047_exploratory_plan.v0.1.json`, `research/source_materials/literature_review_status.csv` and `…_original.xlsx`.

---

## Appendix A — Reproduction

```bash
# deterministic arithmetic checks only (standard library; no model fitting, no simulation)
python3 scripts/verify_m2e1_sample_size.py
```

Expected: `All deterministic checks passed. No model was fitted and no simulation was run.` with exit code 0; any mismatch prints `[FAIL]` and exits 1. There is no `--simulate` option: the fitting pathway present in revision 1 has been removed.

The script reads no project data, contains no patient records, fits nothing to any dataset, and generates nothing random. Section letters in its output: A = published anchors; B = structural properties; C = the D-047 scenario including break-even and rounding; D = analytical equality versus floating-point representation; E = applicability domain of the additional MAPE criterion; F = the implicit shrinkage inversion. 60 checks in total.

**If the script is not authorised** ([§0.5](#05-scope-discrepancy-documentation-only-issue-vs-this-diff)), every number can be checked by hand from [Appendix E](#appendix-e--documentation-only-verification-record).

## Appendix B — `pmsampsize` source traceability

| Item | Location | Behaviour reproduced here |
|---|---|---|
| C1 shrinkage | `R/pmsampsize_bin.R` line 12 | `n1 <- ceiling(parameters/((shrinkage-1)*(log(1-(r2a/shrinkage)))))` |
| maxR²cs | lines 19–20 | `1 - exp(2*lnLnull/n1)`, equal to the prevalence-only expression because `E1/n1 = prevalence` |
| C2 optimism | lines 28–30 | `s = r2a/(r2a + 0.05*max_r2a)`, then the shrinkage expression with `s` |
| C3 proportion | line 39 | `ceiling(((1.96/0.05)^2)*(prevalence*(1-prevalence)))` |
| Error guard 1 | lines 6–9 | stop if `shrinkage < rsquared` |
| Error guard 2 | lines 23–26 | stop if `max_r2a < rsquared` |
| C→R²cs (**described only, not executed**) | `R/cstat2rsq.R` lines 2–24 | n = 10⁶; LP ~ N(0,1) non-events, N(√2·Φ⁻¹(C),1) events; `glm(y ~ LP)`; `1-exp(-(null.deviance-deviance)/n)`; seed 123456. **Requires synthetic model fitting; not run under this work item** |
| Rounding in the C path | `R/pmsampsize.R` (binary branch) | `rsquared <- round(cstat2rsq(...)$R.coxsnell, digits = 4)` |

C4 is **not** in `pmsampsize`; it is transcribed from the published minimum-MAPE expression and attributed accordingly ([§4.1](#41-the-published-criteria-and-the-additional-one)).

## Appendix C — Extraction screen (all 25 papers)

Sweep of `literature_review_status.csv`, all 15 columns, case-insensitive. **Extraction-level only; full texts were not examined.** No row *as recorded* reports a Cox–Snell or Nagelkerke R², a Riley-style sample size, a shrinkage estimate, or an events-per-parameter analysis, so that column is omitted. Source dataset as recorded in the sheet. **[XTR]**

| ID | Supervisor status | Year | Source dataset (as recorded) | Eligible anticipated-R² source? |
|---|---|---|---:|---|
| P1 | APPROVED_GREEN | 2024 | Combined five public CAD datasets (UCI-derived) | Not identified — no R² recorded; merged cohorts |
| P2 | APPROVED_GREEN | 2024 | Heart Statlog / Cleveland / Hungary (Kaggle) | Not identified — no R² recorded |
| P3 | MAYBE_PINK | 2024 | Cleveland public portion + private Egyptian data | Not identified — no R² recorded; private cohort |
| P4 | APPROVED_GREEN | 2025 | BRFSS 2015 / Framingham / Z-Alizadeh Sani | Not identified — no R² recorded |
| P5 | APPROVED_GREEN | 2025 | Z-Alizadeh Sani (UCI-412) | Not identified — different source; no R² recorded |
| P6 | MAYBE_ORANGE | 2024 | Cleveland + Framingham | Not identified — but records the n = 303 overfitting concern |
| P7 | APPROVED_GREEN | 2025 | Cleveland & Switzerland | Not identified — no R² recorded |
| P8 | MAYBE_ORANGE | 2025 | Z-Alizadeh Sani | Not identified — no R² recorded |
| P9 | APPROVED_GREEN | 2024 | Z-Alizadeh Sani | Not identified — no R² recorded |
| P10 | APPROVED_GREEN | 2026 | UCI Heart Disease + Kaggle CVD dataset | Not identified — no R² recorded |
| P11 | REJECTED_RED | 2026 | Private | Not identified — private data |
| P12 | REJECTED_RED | 2025 | Private (on request) | Not identified — private data |
| P13 | REJECTED_RED | 2024 | Private (I-PAD records) | Not identified — private data |
| P14 | APPROVED_GREEN | 2026 | Cleveland / Z-Alizadeh Sani / Statlog / Framingham | Not identified — no R² recorded |
| P15 | APPROVED_GREEN | 2025 | Z-Alizadeh Sani + Framingham | Not identified — no R² recorded |
| P16 | REJECTED_RED | 2024 | UK Biobank (controlled access) | Not identified — controlled access |
| P17 | REJECTED_RED | 2025 | PhysioNet waveform databases | Not identified — ECG signals; other endpoint |
| P18 | REJECTED_RED | 2024 | Private + online calculator | Not identified — private data |
| P19 | MAYBE_ORANGE | 2026 | Heart Statlog/Cleveland/Hungary, n = 1,190 | Not identified — no R² recorded; merged cohort |
| P20 | MAYBE_ORANGE | 2024 | PhysioNet Fantasia / INCART | Not identified — ECG signals |
| P21 | MAYBE_ORANGE | 2025 | Cleveland (UCI) | Not identified — no R² recorded |
| P22 | REJECTED_RED | 2026 | Private hospital cohort | Not identified — no R² recorded; private data |
| P23 | MAYBE_ORANGE | 2025 | UCI Heart Disease (4 cohorts) | Not identified — no R² recorded |
| P24 | REJECTED_RED | 2025 | Private single-centre | Not identified — private data |
| P25 | REJECTED_RED | 2026 | AngioCAD (Zenodo) | Not identified — angiography dataset; different endpoint |

Status counts: 9 GREEN, 6 ORANGE, 1 PINK, 9 RED. **[AR]**

## Appendix D — Revision history

| Field | Value |
|---|---|
| Version | 1.0 — initial review draft (commit `cbae437`) |
| Version | 1.0a — C1 threshold wording clarification (commit `ff934da`) |
| Version | 2.0 — post-QA scientific corrections (commit `e2f2edd`) |
| **Version** | **2.1 — Issue #37 risk, framework, checklist and acceptance material (this revision)** |
| Date | 2026-10-23 |
| Basis commit | `a0d4007` (merge of PR #36) |
| Supersedes | revision 2.0 of this document |
| Change control | any future numeric change requires a dated amendment naming who changed it and why |

### Corrections applied in 2.0

| # | Defect in 1.0a | Resolution in 2.0 |
|---|---|---|
| **1** | `expected_shrinkage()` used `S = 1 + p/(n·ln(1−R²cs))`, which is **not** the inverse of criterion 1; it returned 0.8873 at the break-even where criterion 1 gives 0.9000. | Replaced by `shrinkage_at_n()`, a deterministic bisection solving n = p/((S−1)ln(1−R²cs/S)) for S. Roots verified against an independent solve: 0.05→0.6632, 0.10→0.8018, 0.15→0.8619, 0.208842→0.9000, 0.25→0.9171, 0.30→0.9320. Table, text and checks rebuilt from the corrected function ([§6.4](#64-shrinkage-actually-achieved-at-n--303)). |
| **2** | `--simulate` fitted logistic models to synthetic samples, exceeding the Issue's authorisation. | Removed entirely, together with the numpy/scipy path. The C→R² method is documented but **not executed** ([§4.5](#45-the-c-statistic--r²-conversion-documented-deliberately-not-executed)); the simulation-derived numbers, seed sensitivity and C-derived table are **withdrawn** ([§5.4](#54-withdrawn-in-this-revision)). |
| **3** | Scenario rows labelled `0.209` computed with `0.20884`, crossing a ceiling discontinuity; §6.4 claimed p ≤ 7 at "0.209" although p = 8 passes at that value. | All three values (0.20884, exact 0.20884206294424718, 0.209) are shown with the value actually used, plus real-valued n before ceiling. Budget statements split: p ≤ 7 at 0.20884, p ≤ 8 at 0.209 ([§6.3](#63-the-full-requirement-as-a-function-of-the-missing-input), [§6.5](#65-what-would-have-to-change)). |
| **4** | Absence of R² claimed at full-text strength from extraction metadata; implied claim about the wider CAD literature. | Rescoped to `[XTR]` extraction-level findings with an explicit "what this does not support" paragraph ([§7.4](#74-screen-of-the-supervisor-selected-corpus--extraction-level)); external-literature claim restricted to the three studies examined ([§7.5](#75-external-cad-prediction-literature-examined)). |
| **5** | "Lower bound" language applied to all criteria although C4 can overestimate; C4 not distinguished from the published three; p = 8 and φ presented without qualification. | C1–C3 separated from the additional approximate C4 ([§4.1](#41-the-published-criteria-and-the-additional-one)); direction-of-error paragraph added ([§4.2](#42-direction-of-error-not-uniformly-conservative)); p = 8 scope stated ([§3.2](#32-what-p--8-represents--and-what-it-does-not)); φ scope stated ([§2.1](#21-what-φ-is-and-is-not)). |
| **6** | A decision rule written after D-047 was executed was described as "pre-registered", and contained an underived 1.25 multiplier. | §9.3 rewritten as an **UNAPPROVED post-experiment proposal** with provenance stated; the 1.25 multiplier and its three-band classification **removed** as methodologically underived. |
| **7** | (QA follow-up) Documentation-only scope vs an added script. | Recorded explicitly in [§0.5](#05-scope-discrepancy-documentation-only-issue-vs-this-diff), the script header, and Q11; a documentation-only fallback is provided in [Appendix E](#appendix-e--documentation-only-verification-record). |

### Additions in 2.1

Not corrections of previously published numbers — every quantity in §6 is unchanged — but fulfilment of the Issue #37 deliverables that revision 2.0 did not carry.

| # | Requirement | Where it is now delivered |
|---|---|---|
| **8** | Independent-dataset research risk assessment (target harmonisation, timepoints, referral bias, overlap, UCI-411/412 identity, missingness/shift, implications) with a VERIFIED / UNRESOLVED / NOT ASSESSED / HUMAN DECISION REQUIRED matrix | §14 |
| **9** | Source-grounded TRIPOD+AI and PROBAST+AI assessment, explicitly not a formal PROBAST+AI judgement | §15 |
| **10** | Next-gate reviewer checklist with requirement, evidence, outstanding evidence, responsible reviewer, status and blank sign-off | §16 |
| **11** | Issue #37 acceptance matrix and filename reconciliation, including an explicit list of incomplete requirements | §17 |
| **12** | Break-even floating-point edge case, with regression coverage that distinguishes analytical equality from representation noise and cannot rescue genuinely insufficient sizes | §5.5, §5.2 |
| **13** | Applicability domain of the additional MAPE criterion, including the prevalence (minority-class) transformation above 0.5 | §4.6 |

## Appendix E — documentation-only verification record

If the verification script is not authorised, this appendix is the substitute. Every quantity used in the decision-relevant sections is listed so that a reviewer can reproduce it with a calculator. Formulas are in [§4.1](#41-the-published-criteria-and-the-additional-one).

**Inputs.** n = 303; events = 139; non-events = 164; φ = 139/303 = 0.458745875; p = 8; S = 0.90; optimism tolerance = 0.05; δ = 0.05; MAPE target = 0.05.

**Derived constants.** maxR²cs = 1 − exp(2[0.458745875·ln 0.458745875 + 0.541254125·ln 0.541254125]) = **0.748290342**.

| Quantity | Formula | Value |
|---|---|---:|
| C3 real-valued | (1.96/0.05)²·φ(1−φ) | 381.544788 → **382** |
| C4 real-valued, p = 8 | exp((−0.508 + 0.259·ln φ + 0.504·ln 8 − ln 0.05)/0.544) | 458.780212 → **459** |
| C1 at R²cs = 0.05 | 8/((−0.10)·ln(1 − 0.05/0.90)) | 1399.6190 → 1400 |
| C1 at R²cs = 0.10 | as above | 679.2150 → 680 |
| C1 at R²cs = 0.15 | as above | 438.7852 → 439 |
| C1 at R²cs = 0.20884 | as above | 303.0034 → **304** |
| C1 at R²cs = 0.209 | as above | 302.7380 → **303** |
| C1 break-even | 0.90·(1 − exp(8/((0.90−1)·303))) | **0.208842062944** |
| Shrinkage at n = 303, R²cs = 0.10 | solve 303 = 8/((S−1)ln(1−0.10/S)) | **0.801798** |
| Shrinkage at n = 303, R²cs = 0.208842 | as above | **0.900000** |
| δ at n = 303 | 1.96·√(φ(1−φ)/303) | 0.056108 |
| MAPE at n = 303, p = 8 | exp(−0.508 + 0.259 ln φ + 0.504 ln 8 − 0.544 ln 303) | 0.062658 |
| Required R²cs for C1 at p = 8 | 0.90·(1 − exp(8/((0.90−1)·303))) | 0.208842 |

## Appendix F — Status vocabulary

| Term | Meaning in this document |
|---|---|
| **VERIFIED** | Recomputed and matched against the published source or an independent solve. |
| **NOT ASSESSED — PENDING HUMAN REVIEW** | No defensible determination is possible from the available evidence; a named human must decide. |
| **NOT IDENTIFIED IN THE EXAMINED SOURCES** | A bounded negative: searched these sources, found none. Not an absence claim about the literature. |
| **PROPOSED** | Put forward for decision; carries no authority until ratified. |
| **WITHDRAWN** | Present in revision 1, removed in revision 2.0, and not relied upon anywhere. |
| **[BLANK]** | Intentionally empty; must be completed by a named human. |
| **VERIFIED** (risk-matrix disposition) | Established from an official source, audit record or repository evidence, and adequate for planning (§14.1). |
| **UNRESOLVED** | A specific question is open, a discordance exists, or the available evidence does not settle it. |
| **NOT ASSESSED** (risk-matrix disposition) | Not examined at the required level — for example no data-level audit, or the enabling field does not exist in the released schema. |
| **HUMAN DECISION REQUIRED** | Options can be described; choosing among them is a scientific/governance act reserved to a named human. |
