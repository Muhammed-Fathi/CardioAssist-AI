# 05 — Research Methodology and Approval-Gate Plan

**Status:** PROPOSED planning baseline (documentation only), 2026-10-17.
This document **summarizes and sequences** the governing research rules; it
does not replace them. Authority: `docs/phase0/PHASE0_REVIEW_DRAFT.md`
(Rev. 3: §4–§6, §9, §R2-4, §R2-5, §F-1…§F-6), `docs/DECISIONS.md`
(D-038/D-039/D-040, P-1…P-5), `docs/DATA_POLICY.md`, `AGENTS.md`. Where any
conflict exists, those documents govern.

**Nothing in this document authorizes dataset acquisition, model training,
or any performance/clinical claim.**

---

## 1. The two research/product tracks (binding, D-038/D-039)

| | Track A — clinical CAD AI | Track B — patient & wearable monitoring |
|---|---|---|
| Purpose | Cross-sectional CAD **presence** classification (T1, provisional) on approved tabular benchmark data, with real SHAP/LIME explanations and clinician review | Patient-entered information, lab-report processing (M5), wearable/monitoring history |
| Inputs | `benchmark_import` / `clinician_entry` only, schema-validated, unit-checked | `manual_entry`, `simulated_wearable` (later real device sources under P-6) |
| Outputs | Target-named score + explanation + `validation_status` + disclaimer; ends at clinician review | Descriptive history/trends only; **no CAD score, no interpretation overlay** |
| Data rule | Trained only on labeled tabular datasets under Gate PT | **Never feeds CAD inference** (`422 wearable_input_not_valid_for_cad_inference`; contract test F-09) |

**The one-way rule is permanent for this project unless a future model is
trained and validated, under its own protocol, on a dataset that pairs
wearable variables with CAD labels.** No approved dataset does (Phase 0
§10.2). Wearable arrival, time passage, or monitoring-trend changes are
**invalid** reassessment triggers (§R2-2.2).

## 2. Clinical target (Track A)

- Sole candidate target today: **T1 — cross-sectional angiographic CAD
  presence** (~50% diameter-narrowing threshold), on UCI tabular benchmarks.
  Status: **PENDING (P-1/D-006)** — not frozen.
- **Cross-sectional presence classification is never labelled "30-day CAD
  risk"** or any future-event probability (no approved dataset contains
  event dates/follow-up/censoring — Phase 0 §4.1). The slides' "30-day CAD
  risk" is rejected as design input.
- Threshold wording differs by source (`>50%` UCI-45 vs `≥50%` UCI-412);
  compatibility must be **checked, not assumed** (harmonization audit,
  §R2-4.2). Severity/ordinal modelling of `num` 1–4 remains UNAPPROVED.
- Candidate secondary targets (per-artery stenosis T2 via UCI-411, survey
  self-report T3, ECG-statement T5) are separate tasks — never merged into
  T1 (§R2-4.2 Strategy D).

## 3. Candidate datasets, tiers, and risks (summary of Phase 0 §5 / §R2-4)

| Tier | Datasets | License/access (as verified in Phase 0) | Key risks / rules |
|---|---|---|---|
| 1 — primary | **UCI Heart Disease id 45** (Cleveland 303, Hungary 294, Switzerland 123, VA 200), **UCI Z-Alizadeh Sani id 412** (303) | CC BY 4.0, public [VERIFIED-EXTERNAL in Phase 0] | Switzerland/VA missingness; pre-angiography feature availability audit required (esp. `ca` excluded, `thal` pending per §F-1); `oldpeak` unit UNVERIFIED |
| 2 — gated | **Statlog id 145** (270), **UCI-411 Z-Alizadeh extension** (same 303 patients) | CC BY 4.0 | Statlog ≈ Cleveland overlap (suspect-duplicate until audited); UCI-411 is **not independent** and its LAD/LCX/RCA fields are **target leakage** as predictors |
| 3 — separate tasks | BRFSS 2015 (CDC official only), NHANES (CDC), PTB-XL (PhysioNet) | public/open, per-source terms | Self-report labels ≠ angiographic CAD; survey weights; ECG statements ≠ CAD; never pooled with T1 |
| Blocked/prohibited | Official Framingham (BioLINCC+IRB+DUA), UK Biobank, private cohorts (P3 Egypt, P25 AngioCAD — D-021/D-022), **Kaggle "Framingham"/CVD-70K mirrors** | controlled / unverified provenance | Mirrors **prohibited** until provenance documented (D-012) — a mirror cannot grant rights the controlled source withholds |

Cross-cutting risks (Phase 0 §5.1): row-count ≠ patient-count discipline;
recirculation/duplication across UCI copies; era/spectrum bias (1980s
referral cohorts — no transfer claim to screening or Egyptian outpatients);
feature-schema incompatibility (UCI-45's 14 features vs UCI-412's 54 — the
real harmonization research problem).

**Multi-dataset strategy (D-040) in mandatory order:** A (per-dataset models,
always) → B (feature-harmonized cross-dataset evaluation, conditional on
compatibility checks) → C (pooled training, strictly gated, leave-one-site-out)
→ D (differently-labelled datasets as separate tasks, never merged).

## 4. Approved literature-review policy

- **Supervisor classification is law** (D-003): first sheet of
  `research/source_materials/literature_review_original.xlsx`, exported to
  `literature_review_status.csv` with explicit `Supervisor_Status` —
  GREEN = approved evidence base (9); PINK/ORANGE = maybe, only after
  explicit human promotion (1/6); RED = excluded from the selected research
  scope (9). Counts verified: `scripts/verify_sources.py` (4/4 hashes).
- GREEN papers' recorded numbers are **[AS-RECORDED — UNVERIFIED]** until
  full-text verification; several recorded scores (100% accuracy etc.) are
  leakage/overfitting **red flags to audit**, not targets to beat.
- Before **any** novelty/gap/publication claim: (i) every GREEN full text
  verified on a predefined extraction form (validation design, deployment
  artifact, wearable data, calibration, external cohort) with page/section
  evidence, and (ii) broader literature search beyond the 25-paper corpus
  (D-025, §F-2). Until then the research gap is a **provisional hypothesis**.
- RED papers contribute no methodological evidence; a RED-associated
  *dataset* needs its own human scope decision (D-021).
- Presentation citations/dataset recommendations are **not** approved
  research evidence (D-004).
- Source materials are immutable (SHA-256 manifest;
  `scripts/verify_sources.py`); publisher terms bar redistributing article
  PDFs or datasets.

## 5. The approval gates (binding order)

````
  THIS BLUEPRINT APPROVED (human)
        │
        ▼
  ┌──────────────── Gate DA (P-2 / D-031) ────────────────┐
  │ Named human authorization listing EXACT datasets      │
  │ → local-only acquisition into out-of-git storage      │
  │ → READ-ONLY audit: hashes, licence snapshot, schema,  │
  │   data dictionary (thal/oldpeak/ca rulings), counts,   │
  │   missingness, duplicates/overlap, feature availability│
  │ ✗ NO fitting, selection, tuning, calibration,          │
  │   explanation generation, or evaluation                │
  └──────────────────────┬────────────────────────────────┘
                         ▼
  ┌──────────────── Gate PT (P-3 / D-032) ────────────────┐
  │ Frozen, timestamped, SUPERVISOR-APPROVED protocol:    │
  │ target verbatim · dataset checklists · eligibility ·   │
  │ feature dictionary + availability timing · strategy    │
  │ A–D decision · model families + baselines · tuning     │
  │ budget · pre-registered metrics · calibration plan ·   │
  │ subgroup plan · CI method · leakage sign-off ·         │
  │ versioning · stopping/reporting rules                  │
  │ ✗ NO model work before sign-off; amendments dated      │
  └──────────────────────┬────────────────────────────────┘
                         ▼
   M3 modelling (nested CV, within-fold discipline, calibration,
   explanations) → M4 write-up (TRIPOD+AI, D-025 verification)
````

Neither gate is open today. **No agent may proceed on a request that would
bypass them** — record the request and stop (AGENTS.md).

## 6. Experimental protocol essentials (Track A, after Gate PT)

Distilled from Phase 0 §R2-5 (the frozen protocol will carry the exact
numbers):

- **Resampling:** repeated stratified **nested CV** (proposed 5×5 outer/inner
  ×4 seeds), patient-level splits; **no locked holdout at n≈300** — the
  untouched-test role is played by Strategy-B external cohorts. If a cohort
  ≥1,000 patients arrives, a holdout may return by dated amendment.
- **Within-fold discipline:** imputation, scaling, encoding, feature
  selection, SMOTE/balancing, threshold selection fitted **inside training
  folds only**; pipelines versioned as `preprocessing_id`.
- **Leakage audits (per dataset, documented):** target-leakage exclusion
  (UCI-411 LAD/LCX/RCA; angiography-derived fields; post-diagnosis
  treatments); feature-availability timing vs the angiography decision;
  duplicate patients (exact + fuzzy, incl. Statlog); site/era leakage in
  pooled runs (leave-one-site-out; random row splits across sites
  prohibited); preprocessing leakage + **label-shuffle negative control**.
- **Calibration:** cross-fitted (Platt preferred at n≈300; isotonic only
  with pre-registered minimum-events justification); evaluated on external
  cohorts untouched by model and calibrator; Brier + intercept + slope +
  plot reported. `calibration_id: "none"` → `uncalibrated_score`, never
  rendered as "% risk". **§F-6:** a calibrated score is a
  **benchmark-cohort model score**, never an absolute population/personal
  probability.
- **Uncertainty:** patient-level bootstrap CIs (2,000 resamples) for
  performance; fold dispersion also reported; **no patient-level prediction
  intervals** served or displayed.
- **Explanations:** TreeSHAP on the **log-odds/margin** scale with sum-check;
  never re-based onto probability; LIME as secondary local surrogate with
  real fidelity (local R²) and versioned seed/sampling config; SHAP/LIME
  disagreements logged; stability checks (rank correlation across folds and
  refits; perturbation sensitivity) — **unstable explanations block UI
  attribution display**.
- **Subgroups/fairness:** pre-specified (sex, age bands, site); minimum cell
  ≥30 patients **and** ≥10 events per class else descriptive counts only; no
  post-hoc hunting; all pre-specified results reported.
- **Reporting:** TRIPOD+AI (BMJ 2024;385:e078378) as the completeness floor
  from protocol stage; results (including nulls) in `research/experiments/`;
  replication package = code + configs, never restricted data.

## 7. Real SHAP/LIME requirements (M3 acceptance, feature F02)

1. SHAP values **computed** by a real explainer on the served model (not the
   mock offsets); additivity verified on the log-odds scale in tests (the
   existing F-08-style sum-check re-run for real).
2. LIME results only from a real run with recorded fidelity; the legacy
   F-11c fixture's illustrative fixed R² stays frozen history; the live
   503-for-LIME-only-model behavior is removed only when real LIME is
   integrated and validated (X-01 resolution).
3. `explanation_config_id` versions method + seed + sampling count;
   stability report attached to the model version.
4. UI re-snapshot after explanations become real (wording unchanged:
   log-odds separation, no %, no advice).

## 8. Claims discipline (permanent)

- No invented accuracy, clinical-risk percentages, diagnosis timelines,
  latency SLAs, or deployment-readiness claims — anywhere, including mock
  surfaces, PRs, and papers.
- No guarantee our results will outperform published papers; recorded paper
  numbers are claims to audit, not targets.
- Internal numbers labelled "internal (nested-CV)"; cross-dataset numbers
  labelled "external — one site/cohort pair"; nothing is "clinically
  validated" (P-5 is NOT MADE — prohibited).
- Mock output is never reported as model performance (DATA_POLICY.md).
- Any UI/clinical wording needs clinician review (P-4); conservative
  fallback until then.
