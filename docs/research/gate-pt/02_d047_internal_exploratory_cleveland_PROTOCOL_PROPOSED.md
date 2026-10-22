# D-047 / D-046-EP — Bounded Internal Exploratory CAD Experiment (Review Copy)

**Owner:** CardioAssist-AI maintainer and research team  
**Prepared:** 2026-10-23  
**Scope:** UCI-45 `processed.cleveland.data` **only**, on the maintainer-controlled Windows PC  
**Current state:** **PROPOSED / NOT YET AUTHORIZED**  
**Expected report banner:** `INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED`

## What this changes — and does NOT change

**This proposal implements the previously drafted D-046-EP route:** The team can run its **own clearly marked preliminary experiments** before presenting a documented research package to the academic supervisor. It creates an explicitly bounded exception to the old rule "no fitting before P-3": **only internal exploratory, source-specific work** may be authorized by the human maintainer; **formal Gate PT P-3 remains CLOSED**. This is *not* academic/ethics approval, clinical validation, a published performance result or permission to diagnose patients.

Activation requires **all**: (a) human maintainer explicitly reviews this separate governance PR and records **`AUTHORIZE-D047-INTERNAL-CLEVELAND`** in its PR conversation, (b) human maintainer merges this PR, (c) the pinned experiment protocol is identified by commit SHA and signed/dated in a **local ignored** authorization manifest, and (d) a guarded local preflight confirms the exact source file SHA-256, allowed experiment, and local-only output path. Merely merging a document without explicit approval text, or verbally telling an agent to train, is **not** enough. All unperformed tasks remain forbidden until activation.

**Evidence prerequisite:** D-046 local read-only audit ratified by the maintainer, reported in merged dataset-QA/research PRs (including PRs #23–#25). Raw Cleveland has an upstream integrity warning and remains quarantined; processed Cleveland's aggregate availability was reviewed. Unresolved harmonization, Swiss/VA quality or patient independence is **not falsely declared CLOSED**; instead such cohorts are excluded from this single-source exploratory scope. No new dataset acquisition or multi-cohort fitting is approved.

**Human scope, not supervisor signoff:** Maintainer may authorize an internal $0 proof-of-research on *public benchmark* data while retaining accurate review-status banners. Supervisor approval remains required before any formal research/clinical claim, approved study protocol, publication assertion, or real medical application. A later supervisor can revise questions and demand reruns without retroactively upgrading early results.

## Pinned source, target and eligible predictors

| Item | Frozen-for-review candidate |
|---|---|
| Cohort | `DA-A2 / UCI-45 / processed.cleveland.data` only; official UCI source |
| Source count (local audit, aggregate) | n=303, target `num`: 164 label 0, 139 labels 1–4 |
| Research-only endpoint | Historical angiography-referenced *current* CAD-presence grouping (`num=0` vs `num=1..4`); no 30-day/incident disease endpoint, no severity inference |
| Primary predeclared panel | `age`, `sex`, `cp`, `trestbps`, `restecg` |
| Candidate panel rationale | Input-time plausibility, simple interface and 303/303 locally audited joint source-coded availability, NOT chosen by association, test performance or clinician-validated workflow |
| Excluded as predictors | `num`, `ca`, `thal`, catheterization/vessel columns, post-outcome measurements, identifiers, site, and any wearable data |
| Secondary panels / other sources | **OUT OF SCOPE** for this first authorization; later dated protocols can add lab-inclusive or exercise-stage candidates, or separate UCI-412 experiments, after input-time/codebook review |
| Source custody | Existing ignored `data/raw/uci-45/processed.cleveland.data`; SHA-256 must match the maintainer's protected verified manifest; do not publish or upload original patient-level records |

The five source fields imply **8 slope coefficients for a reference-coded LR**: age 1 + sex 1 + cp 3 + trestbps 1 + restecg 2. Reporting n/parameters or `139/8` is **not** a valid sample-size justification. The first report must contain a Riley-style binary-model sample-size sensitivity analysis with explicit anticipated Cox–Snell `R²` assumptions, events, parameters and a NO-GO / caution interpretation. If those assumptions are not defensible, results are a software/research feasibility pilot only; no clinical predictive adequacy is claimed.

Clinical prediction timepoint is **not certified by historic UCI chronology**. Therefore this is explicitly a retrospective benchmark; do not imply all features were clinically confirmed pre-catheterization or that results generalize to patient care.

## First internal comparison — review-frozen candidate settings

**Models:**
1. Training-fold prevalence-only dummy baseline.
2. L2 penalized Logistic Regression (`solver=liblinear`, `C={0.1,1,10}`, `max_iter=2000`, `class_weight=None`).
3. Constrained Random Forest (`n_estimators=200`, `max_depth={3,5}`, `min_samples_leaf={5,10}`, `max_features=sqrt`; deterministic per-fit random_state).

**Evaluation:**
- Repeated nested stratified CV: **outer 5 folds, inner 5 folds, 4 repeats**, distinct outer seeds `20261023,20261024,20261025,20261026`; all model families compared on the same outer splits.
- Every inner search receives only the outer-training partition; median imputation, numerical scaling (for LR), categorical reference/one-hot encoding and any preprocessing are **fitted inside the inner folds** via `sklearn.pipeline.Pipeline` and `ColumnTransformer`. Final outer-fold estimator is trained on outer-training data only. Nothing learns from outer assessment rows.
- Field registry must be UCI-45 source-specific; **do not** bypass `synthetic_only` by setting a false `synthetic: true` assertion for real data. Implement separate local adapter with explicitly approved dictionary. Original `?` codes are missing; do not pretend `not_measured` reasons were recorded when they were not. No arbitrary zero-to-null recoding; this first five-field panel excludes `chol` and does not contain source-flagged BP zeros in the local Cleveland audit.
- Encode categorical `sex` (0/1), `cp` (1–4) and `restecg` (0–2) with deterministic source vocabulary; for LR use reference drop or a justified equivalent penalty setting. No target-based feature selection or whole-cohort variable screening.
- **Procedure-level selection:** within every outer-training split use inner CV to choose among *both* model families and the bounded hyperparameters (primary inner metric ROC-AUC; if difference ≤0.01 prefer LR as simplicity rule). Evaluate the winner **once** on the untouched outer fold; report this *nested selected procedure* as the principal internal performance estimate. Also report per-family nested results as predeclared supportive analyses, not an unbiased winner-selection test.
- Inner and outer stratification must preserve source labels 0/1 and report per-fold positive/negative counts. Freeze deterministic seed derivation in code/versioned config before the first real-data fit.
- Predeclared negative control: perform a *label-shuffle null run* with identical safe CV wiring and no access to true labels in the shuffled run, report distribution/variance; do not falsely demand exactly 0.50 observed AUROC.
- **Primary metric:** internally cross-validated ROC-AUC of the complete model-selection procedure. Report AUPRC with n and source prevalence; Brier and calibration-in-the-large/curve only if statistically estimable; accuracy, sensitivity, specificity, confusion matrix at a **fixed 0.50 exploratory cutoff only**. Never select a cutoff based on outer predictions; 0.50 is not a patient-care threshold. No personal risk percentages.
- For each repeat, every person contributes **one** outer-fold prediction; compare four repeat-level results and report variation. Those repeats contain the **same 303 subjects**, not 1212 independent people. No invalid CI from treating rows in repeated CV outputs as independent. Formal intervals need a separately prespecified justified estimator.
- **Final model:** a final training artifact may be fitted on this same authorized source **only as a LOCAL exploratory prototype after the internal evaluation procedure is fixed and recorded**; it is not independently validated, deployable as a clinical model or suitable for patient-facing percentages.

**A real first result is not required to be high.** Write down weak results, uncertainty, class imbalance, negative controls, unresolved chronology and failures. Do not run additional models or iterate panels in response to outer-CV metrics without an amendment and clear exploratory status.

## Local execution + provenance boundary

1. **Before fitting:** validate authorizing PR and signed local manifest, protocol commit SHA, source basename and SHA-256, ignored output directory, exact model set; confirm the source hashes match the original protected audit manifests. Fail closed if anything disagrees.
2. **Where:** local Windows CPU, $0, a dedicated virtual environment; no cloud training, Colab, hosted notebook, external API, telemetry, experiment dashboard, remote GitHub agent payload, or copied patient records.
3. **Outputs:** write sensitive per-record folds/scores, model weights and artifacts **only under ignored local `data/experiments/`** with restrictive file permissions; never commit model artifacts, actual row data, raw predictions, run-path/identifier details or sensitive logs. Share only carefully checked aggregate counts, methodology, safety status and non-identifying metrics via an explicitly reviewed report. Avoid small-cell subgroup disclosure.
4. **Immutable originals:** read source bytes but never edit original UCI files. SHA-256 before/after to detect change; original hash mismatch → STOP.
5. **Run registry:** versioned protocol ID/SHA, data hash in *local* protected manifest, Git code commit, Python/sklearn/numpy versions, source row-count checks, enabled models, CV seeds, full preprocessing config, class counts, all prespecified metrics, negative-control result, failure log and experimental status. **No fake results.**
6. **Report:** before any supervisor presentation prepare internally reviewed methodology, cohort flow, target, predictor dictionary, per-model primary/secondary metrics, uncertainty, leak tests, comparison decision, limitations, source/citation list, model card and honest TRIPOD+AI/PROBAST+AI assessment. A future supervisor review is recorded separately from this internal stage.

## Manual activation fields (must remain unfilled in Git)

- `human_maintainer_approval_comment`: **NOT RECORDED**
- `human_maintainer_merge_of_separate_governance_pr`: **NOT RECORDED**
- `local_authorization_manifest`: `data/manifests/internal_exploratory_authorization.local.json` — **NOT CREATED OR SIGNED BY ASSISTANT**
- `signed_protocol_commit_sha / approved_source_sha256 / local_data_custodian / review_date`: **PENDING LOCAL HUMAN RECORD**
- `P-3 supervisor_gate`: **CLOSED / NOT SUPERVISOR APPROVED**

**No agent may self-activate these fields or train because this draft exists.** After explicit human ratification, separate agent implementation code is allowed only within the adopted scope, but a privacy-protected dataset may only be *fitted on the user's local computer* after local authorization. Human-run setup is the single operational handoff; any clinical/published claim still requires formal review.

## Why this method (independent references)

- [scikit-learn: nested vs non-nested CV](https://scikit-learn.org/stable/auto_examples/model_selection/plot_nested_cross_validation_iris.html) — evaluating tuned models without reusing selection data.
- [scikit-learn: common pitfalls and leakage](https://scikit-learn.org/stable/common_pitfalls.html) — train-only preprocessing fit in an integrated Pipeline.
- [Riley et al., BMJ 2020, sample-size guidance](https://www.bmj.com/content/368/bmj.m441) — sample-size adequacy needs more than a fixed events/parameter rule.
- [PROBAST+AI, BMJ 2025](https://www.bmj.com/content/388/bmj-2024-082505) — internal evaluation versus external validation and clinical applicability.
- [TRIPOD+AI reporting statement, BMJ 2024](https://www.bmj.com/content/385/bmj-2023-078378) — honest model reporting.
