# AI Workstream (`ai/`) — Track A Research Pipeline (`RESEARCH_ONLY`)

This package implements the reusable, offline Track A tabular CAD AI research pipeline specified in [`docs/research/AI_FIRST_COMPLETION_STRATEGY.md`](../docs/research/AI_FIRST_COMPLETION_STRATEGY.md).

## Modules

- **`ai/panels.py`** — Versioned staged clinical & routine-laboratory input contracts (`da_a2_resting_v1`, `da_a2_resting_labs_v1`, `da_a1_basic_clinical_v1`, and proposed synthetic-only `da_a1_clinical_core_labs_v1`), reusing `research.intake.synthetic_stage_validator` and `research.uci412.feature_schema` while rejecting Track B wearable inputs and angiography/echo leakage fields.
- **`ai/preprocessing.py`** — `FoldSafeClinicalPreprocessor`: strictly training-fold-fitted imputation, scaling, and fixed-order reference coding with explicit `raw_feature -> encoded_columns` group slices and pure JSON state serialization (`preprocessing.json`).
- **`ai/calibration.py`** — `OofLogisticCalibrator` (`calibration.json`), discrimination/calibration/class-specific metrics with stratified bootstrap 95% CIs (reusing `research.uci412.evaluation.calculate_metrics`), prevalence-shift prior-odds diagnostics, and outer-fold-ensemble epistemic uncertainty.
- **`ai/explainability.py`** — Exact **Grouped Interventional LinearSHAP** (`log_odds`, for `l2_logistic_regression`) and Exact **Grouped Interventional TreeSHAP** (`raw_model_probability`, for `constrained_random_forest`), verified against exact $2^M$ coalition Shapley enumeration and checked for additivity at runtime.
- **`ai/training.py`** — Fold-contained nested-CV model selection, label-permutation negative control, and `evaluate_locked_external_cohort` enforcing anti-pooling and anti-test-selection rules.
- **`ai/packaging.py`** — Atomic `RESEARCH_ONLY` bundle writer (`manifest.json`, `model.joblib`, `preprocessing.json`, `calibration.json`, `shap_background.json`, `evaluation_summary.json`, `protocol.md`) and pre-deserialization SHA-256/symlink/path-traversal/git-ignore verifier.
- **`ai/inference.py`** — Offline `ResearchCadPredictor` returning predictions, uncertainty, faithful SHAP explanations, and mandatory clinical/scientific limitations (`approved_for_serving = False`, `clinical_use_authorized = False`).

## Governance & Runtime Boundaries

- **Gate PT (`P-3`) remains CLOSED:** Real-data training and external cohort execution fail closed unless explicitly unlocked under a future ratified Gate PT protocol; CI executes exclusively on generated in-memory synthetic cohorts (`tests/experiments/test_ai_research_pipeline.py`).
- **Isolated from `/v1` HTTP serving (`M1c`):** `backend/app/` never imports `ai/`, and `MOCK_SYNTHETIC` remains the sole active FastAPI provider.
- **Zero committed patient data or binary artifacts:** Bundles may only be written to temporary test directories (`tmp_path`) or git-ignored local paths (`data/`).
