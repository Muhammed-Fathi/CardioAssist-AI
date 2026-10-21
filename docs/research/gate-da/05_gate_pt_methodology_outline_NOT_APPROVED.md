# 05 — Proposed Gate PT Research-Methodology Outline

> ## ⚠️ NOT APPROVED — NOT EXECUTED
> This outline is a **proposal for a future Gate PT submission** (P-3 /
> D-032). It has not been approved by the supervisor or any human gate,
> no part of it has been run, and it authorizes nothing. It may only be
> converted into a frozen, timestamped protocol **after** the Gate DA
> read-only audit exists (document 04), because several choices below
> (feature dictionary, prediction moment, completeness rules) can only
> be finalized from audit findings. Post-freeze changes require dated
> amendments; results-driven silent changes are prohibited
> (Phase 0 §R2-5.1). Distilled from Phase 0 §R2-5/§9 and
> `docs/blueprint/05` §6 — where this outline and those documents differ,
> those documents govern.

## 1. Research question and exact outcome definition (to be frozen verbatim)

- **Question (PROPOSED):** In patients referred for coronary angiography
  in the acquired benchmark cohorts, how well do pre-angiography tabular
  features classify **angiographically defined CAD presence**, internally
  and across cohorts?
- **Outcome (PROPOSED verbatim form, Gate PT must finalize):** binary
  CAD presence per source label — UCI-45 `num` 0 vs 1–4 (`>50%` diameter
  narrowing in any major vessel) and/or UCI-412 CAD/Normal (`≥50%`
  narrowing) — with the H-01 threshold ruling (document 03) recorded
  word-for-word in the protocol. If the ruling is
  *related-but-not-identical* (or remains *unresolved*, e.g. if whether
  exactly-50% records exist or how they were coded cannot be evidenced),
  the two sources are reported as related targets, never as one pooled
  label, until reconciled.
- **Explicit non-outcomes:** future events at any horizon (incl. 30-day),
  severity/ordinal grades, per-vessel stenosis (T2), self-reported
  disease (T3), ECG statements (T5). Any of these requires its own
  target-approval and protocol.
- **Intended prediction moment (must be frozen as one choice):** e.g.
  "after history, examination, resting ECG and pre-procedure labs, before
  angiography" — this single sentence decides the exercise-test block
  (L-07), `thal` (L-06), and DS-2 echo/lab admissibility (L-08). The
  model must be described with this moment everywhere (papers, model
  cards, API/UI copy).

## 2. Eligibility criteria (PROPOSED; finalized from audit)

- Inclusion: records in the acquired cohorts with a determinate source
  label under the frozen coding (H-04 recoding map).
- Exclusion: records failing the audit's pre-registered completeness
  rules; resolved duplicate patients (one retained record per patient
  under the audit's rule, L-05); cohorts failing completeness (e.g.
  Switzerland) are excluded **by rule with counts reported**, never
  silently dropped.
- No outcome-based record exclusion. No eligibility rule may be tuned
  after seeing model results (amendment process only).

## 3. Data handling and leakage-safe preprocessing (PROPOSED)

- **Read-only acquisition & audit first** (Gate DA, document 04 §4);
  originals byte-identical, SHA-256 logged; derived datasets are new
  versioned artifacts with generating-code hashes.
- **Patient-level separation:** all splits grouped by patient where any
  repeated records exist; duplicate resolution precedes splitting.
- **Training-only fitting:** imputation, scaling, encoding, feature
  selection, class-balancing, and threshold selection are fitted **inside
  training folds only** and applied frozen to evaluation folds. The
  fitted pipeline is the versioned unit (`preprocessing_id`).
- **Missingness:** mechanism tabulated per cohort in the audit; the
  protocol freezes one primary handling strategy per cohort + a stated
  sensitivity analysis. Features whose missingness is itself
  site-defining are flagged under L-10/L-12.
- **Class imbalance:** handled only by pre-registered, justified means:
  class-weighted losses and/or threshold choice on validation folds are
  preferred; SMOTE/variants, if used at all, occur inside training folds
  only, are never described as creating patients, and trigger a
  calibration caveat (resampling distorts prevalence → intercept must be
  re-examined before any probability language; document 05 §5).

## 4. Validation strategy for small datasets (PROPOSED)

- **Primary: repeated stratified nested cross-validation** per cohort
  (Phase 0 proposal: 5 outer × 5 inner folds, repeated ×4 with distinct
  fixed seeds — exact numbers to be frozen at Gate PT). Outer folds give
  the performance estimate; inner folds do all tuning/model selection.
  Every outer fold's metrics are reported, not only means.
- **No locked holdout at n≈300** (a ~60-record holdout is unstable and
  wasteful). If a future cohort ≥1,000 patients is authorized, a holdout
  may return by dated amendment.
- **External evaluation (Strategy B)** only for pairs passing all
  conditions in document 02 §3, evaluated **once per locked model** on
  the untouched cohort (L-11), in both directions where schemas allow.
  Harmonized intersection schema is derived, documented, and versioned
  before any such run.
- **Pooled training (Strategy C)** only after Strategy B exists and
  passes, with leave-one-site-out evaluation; random row splits across
  sites are prohibited. If no independent evaluation source survives,
  pooled work is reported as exploratory development only.
- **Negative control:** a label-shuffle run must score at chance; any
  materially above-chance result halts modelling until the leakage
  source is found (L-09 tripwire).

## 5. Models, metrics, calibration, uncertainty (PROPOSED)

- **Baselines (mandatory):** (a) prevalence-only dummy; (b) penalized
  logistic regression; (c) a simple clinical comparator if computable
  from admitted features (e.g. age/sex/cholesterol logistic model).
  A candidate model that cannot beat these honestly is reported as such.
- **Candidates (limited, justified):** logistic regression (above),
  random forest, and one gradient-boosting implementation (LightGBM or
  XGBoost — TreeSHAP-native). Deep learning on n≈300 tabular data is
  **not justified**; AutoML, if run, is a logged sanity ceiling with its
  search budget recorded, not a candidate for selection by default
  (Phase 0 §9.3). Hyperparameter tuning budgets are pre-registered.
- **Metrics (pre-registered):** primary — ROC-AUC on external evaluation
  where it legitimately exists, else nested-CV ROC-AUC labelled internal.
  Secondary: sensitivity, specificity, precision (PPV), recall (=
  sensitivity, reported once with both names cross-referenced, never
  double-counted), F1, AUPRC (with prevalence stated), Brier score,
  calibration intercept/slope + curve. Operating points are chosen on
  validation folds against a pre-registered clinical rationale (e.g.
  sensitivity at fixed specificity, clinician-reviewed), never by
  optimizing on the evaluation set.
- **Confidence intervals:** patient-level bootstrap (Phase 0 proposal:
  2,000 resamples; percentile, with BCa as sensitivity) for *performance
  metrics*; fold dispersion also reported. **No patient-level prediction
  intervals** are computed, served, or displayed.
- **Calibration:** cross-fitted so calibrator-training data ≠ evaluation
  data (Platt scaling preferred at n≈300; isotonic only with a
  pre-registered minimum-events justification). Calibration is evaluated
  on external cohorts untouched by both model and calibrator where they
  exist. Uncalibrated outputs (`calibration_id: "none"`) are labelled
  `uncalibrated_score` and never rendered as "% risk". Even a calibrated
  score is a **benchmark-cohort model score**, not an absolute
  population/personal probability (H-05, Phase 0 §F-6).

## 6. Explainability (PROPOSED; real computation only)

- **SHAP:** genuine TreeSHAP computed on the served model's
  **log-odds/margin** scale, with an automated additivity (sum) check on
  that scale; never re-based onto probability or percentage.
- **LIME:** secondary/local only, from a real run with recorded fidelity
  (local R²), versioned seed and sampling configuration
  (`explanation_config_id`). SHAP/LIME disagreements are logged, not
  hidden.
- **Stability:** rank-correlation of attributions across folds/refits and
  perturbation sensitivity are reported; **unstable explanations block
  any UI attribution display** for that model version.
- Mock SHAP-shaped offsets in the current contracts are not explanations
  and must never be presented as such (document 06).

## 7. Subgroups, reporting, and claims discipline (PROPOSED)

- **Subgroups (pre-specified only):** sex, age bands, site. Minimum cell
  ≥30 patients **and** ≥10 events per class, else descriptive counts
  only. All pre-specified results are reported, including nulls; no
  post-hoc subgroup hunting.
- **Reporting standard:** TRIPOD+AI (Collins et al., BMJ 2024;385:e078378
  — VERIFIED-PH0) as the completeness floor from protocol stage. Results,
  including negative results, are written to `research/experiments/`
  under the frozen protocol's run registry.
- **Labelling law:** internal numbers are labelled "internal (nested-CV)";
  cross-dataset numbers "external — one site/cohort pair" with the pair
  named; **nothing is "clinically validated"** (P-5 NOT MADE — prohibited).
  Recorded paper scores (incl. 100%/>97% figures) are claims to audit,
  never targets (L-09).

## 8. Reproducibility and provenance (PROPOSED)

- Fixed seeds per fold/repetition, logged; environment locked (pinned
  requirements/lockfile, Python/library versions recorded per run);
  $0 tooling only (local CPU is sufficient for n≈300 tabular work;
  Phase 0 §6).
- **Model provenance per artifact:** `model_id`, `preprocessing_id`,
  `calibration_id`, `feature_schema_id`, `explanation_config_id`,
  training-dataset identifiers + SHA-256 hashes + licence snapshots,
  code commit, protocol version, seed set — the same provenance fields
  the `/v1` contract already reserves (document 06).
- **Experiment tracking:** append-only run registry (date, commit, data
  hash, config hash, metrics with CIs, fold-level results, negative
  results). Replication package = code + configs + audit summaries,
  **never** restricted/patient-level data (DATA_POLICY.md).
- **Model cards** per version: frozen target wording, prediction moment,
  training cohorts, metrics with CIs, calibration status, subgroup
  results, limitations (era/spectrum), intended/non-intended use,
  `validation_status` lifecycle value.

## 9. Stopping and amendment rules (PROPOSED)

- Stop and report (do not improvise) if: the label-shuffle control fails;
  a BLOCKER register item (document 03) cannot be closed; an external
  cohort is found non-independent; or subgroup cells collapse below
  minimums across cohorts.
- Any post-freeze change (features, models, metrics, eligibility) is a
  dated amendment approved by the supervisor; the original frozen
  protocol remains in the record.

## 10. Gate PT submission checklist (what the supervisor will be asked to sign)

- [ ] Frozen target wording + H-01/H-02 rulings attached (from Gate DA audit)
- [ ] Per-cohort eligibility/completeness rules + duplicate-resolution rule
- [ ] Feature dictionary with per-feature availability rulings (L-01…L-08 closed)
- [ ] Prediction moment (one sentence) + admitted feature blocks
- [ ] Strategy A/B/C/D applicability decision per cohort pair
- [ ] Model families, baselines, tuning budgets, seeds, fold design
- [ ] Pre-registered metrics, operating-point rule, CI method
- [ ] Calibration plan + uncalibrated-score handling
- [ ] Subgroup plan + minimum-cell rule
- [ ] Leakage sign-off sheet (document 03 register, signed per row)
- [ ] Versioning/provenance/run-registry plan
- [ ] Stopping/reporting rules incl. null-result reporting

**Sign-off: NOT SOUGHT by this document. NOT SIGNED. NOT EXECUTED.**

---

## 11. Separately Reviewable Proposal: Internal Exploratory Protocol (`D-046-EP` — NOT Approved)

> **Status: SEPARATELY REVIEWABLE PROPOSAL ONLY — NOT APPROVED, NOT EFFECTIVE,
> AND AUTHORIZES ZERO MODEL FITTING IN M2a.**

The existing Gate PT (`P-3` / `D-032`) requires academic supervisor sign-off
before any model fitting, feature selection, hyperparameter tuning, or
performance evaluation. This project **never** silently bypasses Gate PT and
**never** fabricates or implies supervisor approval.

To document how the team could conduct preliminary technical exploration if an
academic supervisor meeting remains deferred *after* the M2 local read-only
dataset audit is completed and reviewed, **D-046-EP** (`docs/DECISIONS.md`)
defines the requirements for a potential future governance amendment:

1. **Prerequisite 1 — Completed M2 Read-Only Audit:** The Gate DA read-only
   dataset audit report (`M2`) must first be completed on the maintainer's
   Windows machine and merged via an independently reviewed PR, closing the
   data-level findings in document 03 (`H-01`..`H-07`, `L-01`..`L-08`).
2. **Prerequisite 2 — Separate Governance Amendment PR:** A separate,
   standalone governance amendment PR must be opened, reviewed, and explicitly
   approved by the human maintainer to activate `D-046-EP`. Approving M2a
   (`D-046` Gate DA audit readiness) does **not** approve `D-046-EP`.
3. **Prerequisite 3 — Frozen Timestamped Exploratory Protocol:** Before any
   preliminary experiment runs under `D-046-EP`, the exact target wording,
   feature dictionary, leakage exclusions (`ca`, per-vessel fields,
   `LAD`/`LCX`/`RCA`/`Cath` excluded), nested-CV fold structure, seeds,
   within-fold preprocessing, and label-shuffle negative control must be frozen
   in a timestamped protocol file.
4. **Mandatory Distinction from Supervisor-Approved Research:** Every run,
   artifact, table, and document produced under an internal exploratory
   protocol must carry the explicit banner
   `INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED`. It does **not** satisfy or
   close `P-3` (Gate PT supervisor sign-off), cannot be presented as
   supervisor-approved research, and remains subject to all `P-5` / `D-010`
   prohibitions on clinical, external-validation, novelty, and publication
   claims.
5. **Audit-Only Datasets Remain Excluded from Modelling:** Even under a future
   approved `D-046-EP`, `DA-B1` (UCI-411) and `DA-B2` (UCI-145 Statlog) remain
   strictly audit-only and may never be used as training or external-validation
   cohorts for T1.
