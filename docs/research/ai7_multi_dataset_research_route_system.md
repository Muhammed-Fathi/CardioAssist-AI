# AI-7 — Independent Source-Specific Research Route Catalog and Synthetic-Only Orchestration Layer

**Status:** technical report for open PR implementing AI-7 on branch `arena/5a880acd-cardioassist-ai` (branched from `main` at `2b85bdf` = ratified A3 merge SHA).  
**Classification:** engineering artifact + scientific record; synthetic-only. Nothing here is clinical evidence.

---

## 1. Scope and exact work implemented

**Purpose.** Provide an independent, source-specific research route catalog and synthetic-only orchestration layer on top of the existing `ai/` architecture (panels, inference, training, calibration, explainability, packaging, execution governance). It enables source-specific exploratory exercises (e.g. UCI-45/Cleveland-resting, UCI-412/Z-Alizadeh Sani) to be specified, executed deterministically, and packaged as `RESEARCH_ONLY` artifacts — without real-data inference, training, external validation, or serving.

**New files**

| Path | Role |
|------|------|
| `ai/research_routes.py` | Route catalog (`RESEARCH_ROUTE_CATALOG`: 5 routes), `resolve_route`, `describe_route_catalog`, `get_route_descriptor`, `assert_route_eligible`, `execute_synthetic_route_exercise`, `_run_bundle_round_trip`, typed contracts (`SyntheticRouteExerciseConfig`, `SyntheticRouteExerciseResult`), `RouteResolutionError`/`RouteNotExercisableError`, `_strip_timing` (recursive timing removal for deterministic SHA-256). 1,862 lines. |
| `tests/experiments/test_research_routes.py` | 57 test functions (82 collected cases once parametrization is expanded): catalog contents, resolver positive/negative controls, end-to-end synthetic exercises for `da_a2_resting_v1` and `da_a1_basic_clinical_v1`, determinism (reproducible SHA-256 across repeats), bundle round-trip serving-eligibility contract, governance rejections, A3 frozen-registry regression. |

**Edited files**

| Path | Change |
|------|--------|
| `ai/__init__.py` | Exports all new `ai.research_routes` symbols (types, functions, error class). |

**Not touched (standing constraints):** `ai/diagnostic_scope.py` (frozen A3 registry, `HEAD == A3`), diagnostic registry contents, FastAPI real-model fail-closed boundary, protocol/source-dictionary/governance files, accepted Cleveland bundle. No real-bundle inference/training/external validation/secret access. No pooling across datasets (UCI-45+UCI-412, UCI-412+UCI-411, Cleveland+Statlog, UCI-412+AngioCAD, VA/Switzerland into Cleveland). No UCI-412 `BP`→`trestbps` conversion, no chest-pain binary→`cp` conversion, no assumed target equivalence. `>=50% vs >50%` and prediction-time feature availability remain explicitly unresolved (see §4).

**Route catalog (`RESEARCH_ROUTE_CATALOG`, all `SYNTHETIC_TEST`):**

| Route | Source panel | Panel contract | Status |
|-------|-------------|----------------|--------|
| `da_a2_resting_v1` | UCI-45 / Cleveland resting | `da_a2_resting_v1` (resting ECG panel) | synthetic only |
| `da_a2_resting_labs_v1` | UCI-45 resting + labs | `da_a2_resting_labs_v1` | synthetic only; real-data blocked (`BLOCKED_EXTENDED_PANELS`) |
| `da_a1_basic_clinical_v1` | UCI-412 Z-Alizadeh Sani | `da_a1_basic_clinical_v1` | synthetic only |
| `da_a1_clinical_core_labs_v1` | UCI-412 core labs | `da_a1_clinical_core_labs_v1` | synthetic only; real-data blocked |
| `da_a2_hungary_locked_transportability_v1` | UCI-45 Cleveland → locked Hungary target site (one-shot transport, never trained) | `da_a2_resting_v1`, Cleveland D-047 frozen profile | contract/query only — locked external target, `EVAL_NOT_AUTHORIZED` |

The resolver's operation vocabulary is the `OP_*` constants in `ai/research_routes.py`: synthetic operations `synthetic_training`, `synthetic_prediction`, `synthetic_external_evaluation`, `shap_attribution`, `lime_assessment`, `bundle_packaging`, `route_contract_query`, `synthetic_end_to_end_exercise`, with the real-data operations `real_data_training`, `real_external_evaluation`, `real_bundle_inference`, `clinical_serving` blocked while Gate PT is closed. `resolve_route`/`assert_route_eligible` accept valid synthetic operations for exercisable routes and reject unknown route IDs, non-synthetic statuses, contract/query-only routes, blocked operations, and cross-dataset pooling requests. Orchestrator guards non-exercisable routes with `RouteNotExercisableError` before any resolver call.

## 2. Dataset / route × panel matrix

| Route id | Source dataset (UCI) | N | Target definition | Feature groups | Timing restriction | Real-data status |
|----------|----------------------|---|-------------------|----------------|--------------------|------------------|
| `da_a2_resting_v1` | UCI-45 Heart Disease (Detrano et al. 1989; Cleveland resting subset) | 303 (repository-level; Cleveland sub-cohort per bundle) | Diameter narrowing >50% (obstructive CAD; Cleveland `num ∈ {1,2,3,4}` ⇒ >50%, target `t1.uci45.angiographic_cad_gt50`) | Resting clinical + ECG | Resting-state record only; no labs | synthetic only in this PR |
| `da_a2_resting_labs_v1` | UCI-45 + lab measurements | same cohort | as above (>50%) | resting + lab panel (incl. cholesterol) | Resting-state record only | blocked from real-data execution |
| `da_a1_basic_clinical_v1` | UCI-412 Z-Alizadeh Sani | 303 | Diameter narrowing ≥50% → CAD vs Normal (target `t1.uci412.angiographic_cad_ge50`; related-but-not-identical to the Cleveland >50% target) | demographic, symptom/examination, ECG, laboratory/echo | angiography referral-time panel | synthetic only in this PR |
| `da_a1_clinical_core_labs_v1` | UCI-412 core labs | 303 | as above (≥50%) | laboratory core subset | angiography referral-time panel | blocked from real-data execution |
| `da_a2_hungary_locked_transportability_v1` | UCI-45 Cleveland → locked Hungary external target site (never trained or tuned on) | locked external, one-shot transport | >50% (Hungary `num >50%`, target `t1.uci45.angiographic_cad_gt50`) | Cleveland `da_a2_resting_v1` features under the D-047 frozen profile | `LOCKED_EXTERNAL_TARGET_NEVER_TRAIN` | not authorized; requires Gate PT P-3 plus separate dataset/ledger approval |

Timing: all routes require the input record timestamp to match the panel's timing domain (resting vs referral-time). Lab-timing verification rejects zero/missing required lab values (e.g. zero cholesterol in an unverified lab panel). Source dictionaries are not modified.

## 3. Evidence strengths and unresolved clinical questions

**Strengths of the engineering artifact (not clinical evidence):**

- Determinism: fixed-seed exercises reproduce byte-identical SHA-256 across repeats (verified across repeated runs in tests).
- Serving boundary: bundle round-trip reports `RESEARCH_ONLY`, `approved_for_serving == False`, `clinical_use_authorized == False`; SHAP sum_check and LIME acceptability checks run inside the exercise.
- Governance: resolver rejects blocked/unknown/contract-only operations; frozen A3 registry is never written or used as a back door; no real-data path exists for any route in this PR.

**Unresolved clinical questions (explicitly labeled unresolved; no assumption made in code):**

1. `>=50%` vs `>50%` stenosis threshold for "obstructive CAD" is unresolved across sources (ESC 2024 and UCI repository both use visual thresholds ~50%; UCI-412 explicitly defines CAD as ≥50%). No target equivalence between UCI-45, UCI-412, UCI-411, Statlog, Cleveland, or AngioCAD is assumed.
2. Prediction-time feature availability is unresolved: which UCI-412 laboratory/echo features are actually available at prediction (referral) time vs only post-angiography is not established by this PR.
3. Whether UCI-412 `BP` maps to Cleveland `trestbps` is explicitly NOT converted and NOT assumed equivalent (per standing constraint).
4. Chest-pain binary flags are NOT converted to `cp` and NOT assumed equivalent across sources.
5. Clinical utility (net benefit at decision thresholds) has not been estimated for any route; performance numbers in tests are synthetic-exercise smoke checks, not clinical performance claims.

## 4. Comparative scientific options and engineering recommendation

**Options considered for source-specific orchestration:**

| Option | Description | Assessment |
|--------|-------------|------------|
| A (implemented) | Independent route catalog + synthetic-only resolver/orchestrator on existing `ai/` contracts; `RESEARCH_ONLY` packaging; frozen A3 registry untouched. | Meets all standing constraints; resolver is not a back door; deterministic; negative-control tests pass. |
| B | Extend the ratified A3 diagnostic scope / real-model fail-closed boundary to cover research routes. | Rejected: would modify frozen governance and weaken `HEAD == A3`; violates real-model fail-closed boundary. |
| C | Real-data execution for `da_a2_resting_labs_v1` / `da_a1_clinical_core_labs_v1`. | Rejected: both panels are in `BLOCKED_EXTENDED_PANELS`; real-data execution blocked by `execution.py` governance. |
| D | Pool UCI-45 + UCI-412 (or Cleveland+Statlog, UCI-412+UCI-411, VA/Switzerland into Cleveland) to boost N. | Rejected: standing constraint prohibits pooling; no target equivalence established. |

**Recommendation:** proceed with Option A as merged (this PR). Do not pursue B–D without a separate governance change and established target equivalence.

## 5. Performance measures appropriate to each study

Per Riley et al. 2021 (Stat Med 40:4230–4251; minimum sample size for external validation) and the BMJ "Evaluation of clinical prediction models" series (part 1 development→external validation; part 2 how to undertake external validation, BMJ 2024;384:e074820; part 3 sample size), appropriate measures for a binary CAD outcome are:

- **Calibration:** observed/expected (O/E) ratio and calibration slope (agreement between predicted and observed risk).
- **Discrimination:** C-statistic / AUROC (separation between predicted values in those with and without the event).
- **Clinical utility:** standardized net benefit at clinically relevant risk thresholds.

Sample-size reality (Riley et al. 2021, at event proportion ~0.018 illustration; for CAD cohorts with higher event rates the absolute N is lower but the principle holds): precise estimation of calibration slope alone drove N≈9,835 (177 events) in their illustration; C-statistic CI width 0.1 needs ≈4,252–5,125 participants. Both UCI-45 (303 records repository-level) and UCI-412 (N=303) are far below the sample sizes needed for a precise external validation of a multivariable CAD model. Therefore:

- All performance figures produced by this PR's synthetic exercises are **smoke checks only** (determinism, SHAP additivity, LIME acceptability, serving-eligibility contract) and must not be reported as clinical performance.
- Any future external-validation study on UCI-45/UCI-412 must justify sample size a priori (Riley et al. 2021 / BMJ part 3) and report calibration, discrimination, and clinical utility with confidence intervals (TRIPOD+AI items 18a–18e, 19a–19d).

## 6. Risks: leakage, optimism, prevalence shift, unsuitable transport

| Risk | Assessment in this PR | Mitigation / status |
|------|----------------------|---------------------|
| **Data leakage** | No real data is loaded; synthetic fixtures are generated inside the exercise and never mixed with repository bundles. Lab-timing verification prevents lab values from leaking into resting-only records. | Negative-control tests (label-shuffle, unverified-lab rejection, zero-chol rejection) pass. |
| **Optimism bias** | Training/evaluation on the same synthetic cohort would be optimistic; no such claim is made. Label-shuffle negative control confirms the shuffle ceiling is respected (config `shuffle_max_allowed_auroc`). | `shuffle_max_allowed_auroc` field (default 0.68; FAST_CONFIG 0.85) wired into the training pipeline call site. |
| **Prevalence shift** | UCI-45 repository-level CAD prevalence and UCI-412 CAD prevalence (216/303 ≈ 71% CAD vs 87 normal per UCI description) differ materially; no prevalence adjustment is applied and none is assumed. | Explicitly unresolved; no transport claim across sources. |
| **Unsuitable transport** | No model is transported between UCI-45, UCI-412, Statlog, Cleveland, or AngioCAD; pooling prohibited; target equivalence unresolved. | Resolver rejects pooling; no cross-source inference path exists. |

## 7. TRIPOD+AI reporting gaps (BMJ 2024;385:e078378; Collins et al.)

TRIPOD+AI (27 items, superseding TRIPOD 2015) applies to studies developing/evaluating prediction models with regression or machine learning. This PR is an **engineering orchestration layer**, not a prediction-model development/evaluation study, so TRIPOD+AI does not formally apply — but the gaps below are listed for transparency should any downstream study use artifacts from this PR:

- **No model development reported:** no candidate predictors, sample size, missing-data handling, functional-form selection, or shrinkage is reported by this PR (items 10a–10g). Not applicable yet; required for any downstream development study.
- **No performance results:** no discrimination/calibration/clinical-utility estimates with confidence intervals are claimed (items 18a–18e, 19a–19d). Synthetic-exercise smoke checks are not TRIPOD+AI performance reporting.
- **No model access/code availability statement** for a trained model exists (items 20a–20c); artifacts are `RESEARCH_ONLY` and not approved for serving.
- **No intended users, setting, or health-inequalities analysis** (items 4a–4c); not in scope of an orchestration layer.

A downstream study using these routes for CAD prediction would need to satisfy the full TRIPOD+AI 27-item checklist (and the 13-item abstract checklist) before any reporting of performance.

## 8. PROBAST+AI concerns (BMJ 2025;388:e082505; Moons et al.)

PROBAST+AI assesses model development (quality, 16 signalling questions) and model evaluation (risk of bias, 18 signalling questions) across four domains: participants/data sources, predictors, outcome, analysis; plus six applicability items. Applied hypothetically to any future CAD study using these routes:

- **Participants/data sources (bias):** UCI-45 and UCI-412 are single-center/repository cohorts (Cleveland Clinic foundations; Shaheed Rajaei Cardiovascular Center, Tehran) with unclear consecutive-enrollment reporting — high risk-of-bias potential for spectrum bias.
- **Predictors (bias/applicability):** predictor definitions and units are taken from source dictionaries (`research/uci412/feature_schema.py`), but prediction-time availability of laboratory/echo features is unresolved (see §3). Blinding of predictor assessment to outcome is not documented by this PR.
- **Outcome (bias):** outcome = angiographic diameter narrowing ≥50%; definition varies `≥50%` vs `>50%` across sources and is unresolved here — outcome definition bias risk if sources are mixed.
- **Analysis (bias):** no sample-size justification (Riley et al. 2021), no handling of optimism (no internal validation/resampling reported), no calibration-slope estimation — all high concern if a development study is claimed.
- **Applicability:** patients, predictors, and outcome in UCI-45/UCI-412 may not match an intended real-world CCS population (ESC 2024 pre-test-likelihood strata: very low ≤5%, low >5–15%, moderate >15–50%, high >50–85%, very high >85%). Transport to ESC 2024 CCS pathways is unsupported.

No PROBAST+AI assessment is performed or claimed by this PR; any downstream study must complete one.

## 9. Real-data execution blockers and precise dependencies

**Blockers (all standing, enforced by code/governance):**

- `da_a2_resting_labs_v1` and `da_a1_clinical_core_labs_v1` are in `BLOCKED_EXTENDED_PANELS` (`ai/execution.py`); real-data execution rejected.
- No real bundle is loaded by `ai/research_routes.py`; `_run_bundle_round_trip` uses a synthetic sample payload and reports the serving-eligibility contract only.
- FastAPI real-model fail-closed boundary untouched; no real-model serving path added.
- No secret access, no external validation, no real-patient training.

**Dependencies required to run tests / exercises:**

- Python 3.11+; `numpy`, `scipy`, `scikit-learn`, `joblib`, `threadpoolctl`, `pytest`, `openpyxl`, `et-xmlfile` (pinned in the project `.venv`, git-ignored).
- `ai/` package imports cleanly (`ai.research_routes` imports verified).
- Test command: `python -m pytest tests/experiments/test_research_routes.py -q -W error` (57 test functions; 82 collected cases once parametrization is expanded, all passing under `-W error`).
- Regression: the repository-wide count is produced by the four pinned CI workflows (`audit-ci`, `backend-ci`, `contracts-ci`, `experiment-runner-ci`) rather than hard-coded in this report. Regenerate it with `python -m pytest -q -W error` after installing each workflow's pinned requirements; an earlier draft's "2037 passed / 2 skipped at `2b85bdf`" figure could not be re-verified against the committed tree and has been removed. The AI-8 report records the count verified for its own branch.

## 10. Next two implementation milestones (after this PR)

1. **AI-7b — Synthetic external-validation harness on UCI-45/UCI-412 (no real data):** extend the synthetic-only orchestrator so a research route exercise can hold out a synthetic validation split, report O/E, calibration slope, C-statistic with confidence intervals, and standardized net benefit at a predefined risk threshold, with sample-size justification per Riley et al. 2021 / BMJ part 3 and explicit labeling as synthetic smoke checks. Governance: remains `RESEARCH_ONLY`, no real data, no serving.

2. **AI-7c — TRIPOD+AI/PROBAST+AI reporting pack + unresolved-questions register:** add a reporting template (route × panel matrix, target definition with `≥50%` vs `>50%` decision, prediction-time feature availability, prevalence by source) and a PROBAST+AI self-assessment skeleton for the four domains, to be completed only if a downstream development/evaluation study is proposed. Requires governance review before any real-data or cross-source work.

---

## References

1. 2024 ESC Guidelines for the management of chronic coronary syndromes. Eur Heart J. 2024;45:3415–3512. (Pre-test likelihood strata; obstructive CAD visual thresholds ~50%; CCTA first-line for low/moderate likelihood.)
2. Collins GS, Moons KGM, Dhiman P, et al. TRIPOD+AI statement: updated guidance for reporting clinical prediction models that use regression or machine learning methods. BMJ. 2024;385:e078378. doi:10.1136/bmj-2023-078378.
3. Moons KGM, Damen JAA, Kaul T, et al. PROBAST+AI: an updated quality, risk of bias, and applicability assessment tool for prediction models using regression or artificial intelligence methods. BMJ. 2025;388:e082505. doi:10.1136/bmj-2024-082505.
4. Riley RD, Debray TPA, Collins GS, et al. Minimum sample size for external validation of a clinical prediction model with a binary outcome. Stat Med. 2021;40:4230–4251. doi:10.1002/sim.9025.
5. Riley RD, Archer L, Snell KIE, et al. Evaluation of clinical prediction models (part 2): how to undertake an external validation study. BMJ. 2024;384:e074820. doi:10.1136/bmj-2023-074820. (External validation = evaluation in a dataset not used in development; no refitting.)
6. UCI Machine Learning Repository, Heart Disease (ID 45, Detrano et al.) and Z-Alizadeh Sani (ID 412; N=303, CAD = diameter narrowing ≥50%; four feature groups). Repository landing pages.
7. Project docs: `docs/research/gate-pt/README.md` (governance gate state), `ai/diagnostic_scope.py` (frozen A3 registry), `ai/execution.py` (authorized/blocked panels), `ai/research_routes.py`, `tests/experiments/test_research_routes.py`.

---

**Labeling:** All performance numbers produced by this PR are synthetic-exercise smoke checks. They are not clinical evidence, not calibrated to any real population, and not suitable for clinical deployment. Unresolved items in §3 remain unresolved by this PR.
