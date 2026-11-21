# RH-07 — source-bound PROBAST+AI question-level preassessment workbook

**State:** `PREASSESSMENT_WORKBOOK_NOT_FORMAL_APPRAISAL`. This is a reviewer work queue based on repository-visible historical results. **No quality or risk-of-bias judgment has been scored.** It is not scientific acceptance, a new experiment, patient inference, or a release decision.

**Source anchor:** merged PR #129 / main `c3d044beb15cbbcd4e565644a76f26a7cae44ad7`. The two studies are assessed **separately** because their outcomes, panels, source time semantics and historical populations are not interchangeable.

**Primary assessment standard:** [PROBAST+AI, BMJ 2025;388:e082505](https://www.bmj.com/content/388/bmj-2024-082505) (Table 2). There are 16 development questions and 18 evaluation questions per study, across four domains, plus three applicability domains per phase. Summaries below are *paraphrases* for reviewer navigation; use the official original wording for formal appraisal.

## Scope separation

- **Cleveland D-047**: original five-field, >50% UCI-45 source phrasing, 303 participants (139/164), original exploratory validation reported locally; original source-level patient evidence not re-executed.
- **UCI-412 M3a**: original 16-field, ≥50% owner endpoint, 303 participants (216/87), original 16/16 acquisition-time proofs unavailable; no independent external data.
- The included nested repeated CV is **internal evaluation only**. Never present UCI-412 as externally validating Cleveland. The protected local original aggregates are historical maintainer reports, not independently audited subject-level scores.

## Findings that require actual adjudication

| Scientific domain | Repository evidence located | Open review requirement |
|---|---|---|
| Participants / sources | Separate archived cohort counts and source reports exist | Enrollment provenance, selection dates, intended population and representativeness not fully independently verified |
| Predictors | Frozen source-specific feature order and fold-contained preprocessing protocols exist | Original timing/assessment, coding and blinding remain unresolved; particularly UCI-412 0/16 verified chronology |
| Outcome | Cleveland `>50%`, UCI-412 `≥50%` source wording retained | Exact-50% boundary, original assessor method and outcome-blinding require source evidence |
| Analysis | Frozen repeated nested CV and descriptive AUROC/AUPRC/Brier archived | Patient-level original fold audit unavailable, repeated SD not confidence interval, precision and utility/fairness incomplete |

## Complete question-level index (source-bound, not scored)

### Cleveland D-047

| Phase | Domain | Question | Reviewer prompt | Current state |
|---|---|---|---|---|
| Develop | participants and sources | `DEV-1.1` | Appropriateness of source cohort and sampling for intended research use | `NOT_ASSESSED` |
| Develop | participants and sources | `DEV-1.2` | Whether the original study design supports the reported scope | `NOT_ASSESSED` |
| Develop | participants and sources | `DEV-1.3` | Selection/exclusion and representativeness of included people | `NOT_ASSESSED` |
| Develop | predictors | `DEV-2.1` | Consistent predictor definitions and measurement across people | `NOT_ASSESSED` |
| Develop | predictors | `DEV-2.2` | Consistent predictor preprocessing across source records | `NOT_ASSESSED` |
| Develop | predictors | `DEV-2.3` | Predictor measurement independence from outcome knowledge | `NOT_ASSESSED` |
| Develop | predictors | `DEV-2.4` | Availability of all predictors at the intended prediction moment | `NOT_ASSESSED` |
| Develop | outcome | `DEV-3.1` | Appropriateness of angiography-referenced outcome definition | `NOT_ASSESSED` |
| Develop | outcome | `DEV-3.2` | Consistency of outcome ascertainment among subjects | `NOT_ASSESSED` |
| Develop | outcome | `DEV-3.3` | Outcome determination independence from predictor knowledge | `NOT_ASSESSED` |
| Develop | outcome | `DEV-3.4` | Suitability of elapsed time between predictors and outcome | `NOT_ASSESSED` |
| Develop | analysis | `DEV-4.1` | Sample size/usable events and adequacy of model development | `NOT_ASSESSED` |
| Develop | analysis | `DEV-4.2` | Handling of continuous and categorical predictors | `NOT_ASSESSED` |
| Develop | analysis | `DEV-4.3` | Treatment of missing or censored records | `NOT_ASSESSED` |
| Develop | analysis | `DEV-4.4` | Class-imbalance remedy and resulting recalibration, if any | `NOT_ASSESSED` |
| Develop | analysis | `DEV-4.5` | Controls against model overfitting during training | `NOT_ASSESSED` |
| Evaluate | participants and sources | `EVAL-1.1` | Appropriateness of source cohort and sampling for intended research use | `NOT_ASSESSED` |
| Evaluate | participants and sources | `EVAL-1.2` | Whether the original study design supports the reported scope | `NOT_ASSESSED` |
| Evaluate | participants and sources | `EVAL-1.3` | Selection/exclusion and representativeness of included people | `NOT_ASSESSED` |
| Evaluate | predictors | `EVAL-2.1` | Consistent predictor definitions and measurement across people | `NOT_ASSESSED` |
| Evaluate | predictors | `EVAL-2.2` | Consistent predictor preprocessing across source records | `NOT_ASSESSED` |
| Evaluate | predictors | `EVAL-2.3` | Predictor measurement independence from outcome knowledge | `NOT_ASSESSED` |
| Evaluate | predictors | `EVAL-2.4` | Availability of all predictors at the intended prediction moment | `NOT_ASSESSED` |
| Evaluate | outcome | `EVAL-3.1` | Appropriateness of angiography-referenced outcome definition | `NOT_ASSESSED` |
| Evaluate | outcome | `EVAL-3.2` | Consistency of outcome ascertainment among subjects | `NOT_ASSESSED` |
| Evaluate | outcome | `EVAL-3.3` | Outcome determination independence from predictor knowledge | `NOT_ASSESSED` |
| Evaluate | outcome | `EVAL-3.4` | Suitability of elapsed time between predictors and outcome | `NOT_ASSESSED` |
| Evaluate | analysis | `EVAL-4.1` | Distinction of internal validation from apparent training-set performance | `NOT_ASSESSED` |
| Evaluate | analysis | `EVAL-4.2` | Sample size and precision of performance evaluation | `NOT_ASSESSED` |
| Evaluate | analysis | `EVAL-4.3` | Missing/censored data handling at evaluation | `NOT_ASSESSED` |
| Evaluate | analysis | `EVAL-4.4` | Whether evaluation kept original prevalence rather than artificially balancing it | `NOT_ASSESSED` |
| Evaluate | analysis | `EVAL-4.5` | Prevention of data leakage across held-out folds | `NOT_ASSESSED` |
| Evaluate | analysis | `EVAL-4.6` | Replication of all preprocessing and model selection within resampling | `NOT_ASSESSED` |
| Evaluate | analysis | `EVAL-4.7` | Appropriate discrimination, calibration, utility and uncertainty metrics | `NOT_ASSESSED` |

Full per-question observed sources and unresolved decisions: [JSON workbook](RH07_PROBAST_AI_QUESTION_LEVEL_WORKBOOK_2026_11_21.json).

### UCI-412 M3a

| Phase | Domain | Question | Reviewer prompt | Current state |
|---|---|---|---|---|
| Develop | participants and sources | `DEV-1.1` | Appropriateness of source cohort and sampling for intended research use | `NOT_ASSESSED` |
| Develop | participants and sources | `DEV-1.2` | Whether the original study design supports the reported scope | `NOT_ASSESSED` |
| Develop | participants and sources | `DEV-1.3` | Selection/exclusion and representativeness of included people | `NOT_ASSESSED` |
| Develop | predictors | `DEV-2.1` | Consistent predictor definitions and measurement across people | `NOT_ASSESSED` |
| Develop | predictors | `DEV-2.2` | Consistent predictor preprocessing across source records | `NOT_ASSESSED` |
| Develop | predictors | `DEV-2.3` | Predictor measurement independence from outcome knowledge | `NOT_ASSESSED` |
| Develop | predictors | `DEV-2.4` | Availability of all predictors at the intended prediction moment | `NOT_ASSESSED` |
| Develop | outcome | `DEV-3.1` | Appropriateness of angiography-referenced outcome definition | `NOT_ASSESSED` |
| Develop | outcome | `DEV-3.2` | Consistency of outcome ascertainment among subjects | `NOT_ASSESSED` |
| Develop | outcome | `DEV-3.3` | Outcome determination independence from predictor knowledge | `NOT_ASSESSED` |
| Develop | outcome | `DEV-3.4` | Suitability of elapsed time between predictors and outcome | `NOT_ASSESSED` |
| Develop | analysis | `DEV-4.1` | Sample size/usable events and adequacy of model development | `NOT_ASSESSED` |
| Develop | analysis | `DEV-4.2` | Handling of continuous and categorical predictors | `NOT_ASSESSED` |
| Develop | analysis | `DEV-4.3` | Treatment of missing or censored records | `NOT_ASSESSED` |
| Develop | analysis | `DEV-4.4` | Class-imbalance remedy and resulting recalibration, if any | `NOT_ASSESSED` |
| Develop | analysis | `DEV-4.5` | Controls against model overfitting during training | `NOT_ASSESSED` |
| Evaluate | participants and sources | `EVAL-1.1` | Appropriateness of source cohort and sampling for intended research use | `NOT_ASSESSED` |
| Evaluate | participants and sources | `EVAL-1.2` | Whether the original study design supports the reported scope | `NOT_ASSESSED` |
| Evaluate | participants and sources | `EVAL-1.3` | Selection/exclusion and representativeness of included people | `NOT_ASSESSED` |
| Evaluate | predictors | `EVAL-2.1` | Consistent predictor definitions and measurement across people | `NOT_ASSESSED` |
| Evaluate | predictors | `EVAL-2.2` | Consistent predictor preprocessing across source records | `NOT_ASSESSED` |
| Evaluate | predictors | `EVAL-2.3` | Predictor measurement independence from outcome knowledge | `NOT_ASSESSED` |
| Evaluate | predictors | `EVAL-2.4` | Availability of all predictors at the intended prediction moment | `NOT_ASSESSED` |
| Evaluate | outcome | `EVAL-3.1` | Appropriateness of angiography-referenced outcome definition | `NOT_ASSESSED` |
| Evaluate | outcome | `EVAL-3.2` | Consistency of outcome ascertainment among subjects | `NOT_ASSESSED` |
| Evaluate | outcome | `EVAL-3.3` | Outcome determination independence from predictor knowledge | `NOT_ASSESSED` |
| Evaluate | outcome | `EVAL-3.4` | Suitability of elapsed time between predictors and outcome | `NOT_ASSESSED` |
| Evaluate | analysis | `EVAL-4.1` | Distinction of internal validation from apparent training-set performance | `NOT_ASSESSED` |
| Evaluate | analysis | `EVAL-4.2` | Sample size and precision of performance evaluation | `NOT_ASSESSED` |
| Evaluate | analysis | `EVAL-4.3` | Missing/censored data handling at evaluation | `NOT_ASSESSED` |
| Evaluate | analysis | `EVAL-4.4` | Whether evaluation kept original prevalence rather than artificially balancing it | `NOT_ASSESSED` |
| Evaluate | analysis | `EVAL-4.5` | Prevention of data leakage across held-out folds | `NOT_ASSESSED` |
| Evaluate | analysis | `EVAL-4.6` | Replication of all preprocessing and model selection within resampling | `NOT_ASSESSED` |
| Evaluate | analysis | `EVAL-4.7` | Appropriate discrimination, calibration, utility and uncertainty metrics | `NOT_ASSESSED` |

Full per-question observed sources and unresolved decisions: [JSON workbook](RH07_PROBAST_AI_QUESTION_LEVEL_WORKBOOK_2026_11_21.json).

## Reporting-standard gaps and next reviewer steps

1. Each study requires its **own** independent PROBAST+AI evaluation. This worksheet has **zero formally answered signalling questions**, **zero formal domain ratings**, and no applicability score. A rubric score cannot be automated from file existence.
2. The RH-03 TRIPOD+AI crosswalk identifies **27 main items**, but its **52 official subitems** are not yet mapped or resolved here. Keep them open, and also keep the abstract-specific checklist open.
3. Original RH-03 audit statuses remain **9 limited source-text matches / 19 not independently verifiable**, plus **10 pending human reviewer actions**. No retrospective source truth or new real benchmark measurement was established.
4. Reviewer should classify each question using the official permitted answer vocabulary and provide an actual rationale, evidence ID, reviewer identity and review date; until then each row remains `NOT_ASSESSED`.
5. This workbook does **not** close RH-07, RH-03, RH-06 or RH-08. Final research-only handoff and the old completion tracker must be reconciled explicitly with verified evidence and owner acceptance.

## Read-only audit command

`python scripts/verify_rh07_probast_workbook.py` checks the 2 × (16 + 18) indexing, six applicability items per study, source existence and prohibition on made-up scoring. The validator does not judge medical evidence.
