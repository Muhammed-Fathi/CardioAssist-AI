# CardioAssist AI — Phase 0 Research & Feasibility Review (DRAFT)

| Field | Value |
|---|---|
| Status | **DRAFT REV. 2 — CHANGES REQUESTED by maintainer; revised, awaiting explicit human approval. Not approved. DO NOT START PHASE 1.** |
| Date | 2026-10-16 (Rev. 2, same session, PR #1 updated in place) |
| Branch | `arena/f977cda2-cardioassist-ai` (dedicated Phase 0 working branch, accepted by maintainer) |
| Base commit | `9f12482` — *chore: initialize CardioAssist AI project* |
| Author | Arena Agent Mode (Phase 0 session) |
| Approvers required | Research lead + supervisor (scientific), AI/Backend/Frontend leads (engineering) |
| Budget constraint | **$0** (D-001, CONFIRMED). No paid services, no card-required trials. |
| Changes in this PR | (1) this report; (2) one-line SHA-256 correction in `research/source_materials/SOURCE_MANIFEST.sha256` (see §0). **No code, no datasets, no dependencies were added.** |

> **This is a research prototype plan, not a clinically validated diagnosis or
> risk-prediction service.** No model has been trained, no dataset has been
> downloaded, and no performance claim in this document is a result of this
> project. Every performance number below is either *as recorded in the
> supplied screening spreadsheet* or *as reported by an external source*, and
> is labelled as such.

---

## How to read this document — evidence taxonomy

Every material statement is tagged so reviewers can separate fact from proposal:

| Tag | Meaning |
|---|---|
| **[CONFIRMED]** | Stated in `AGENTS.md`, `docs/DECISIONS.md`, `README.md`, or explicitly confirmed by the maintainer for this session. |
| **[VERIFIED-INTERNAL]** | Checked by the agent against files in this repository during this session (method given). |
| **[VERIFIED-EXTERNAL]** | Checked against an official/primary external source during this session (URL in §14). |
| **[AS-RECORDED — UNVERIFIED]** | Copied from the supplied CSV/XLSX/presentation. **Not** independently checked against the paper/dataset full text. Do not cite as evidence. |
| **[PROPOSED]** | Agent recommendation. Requires human approval; not a decision. |
| **[OPEN / UNVERIFIED]** | Unknown. Must be resolved before the dependent work starts. Never treat as permission. |

---

## Executive summary

1. **Source integrity is fixed and verified** (§0). The CSV checksum mismatch
   was a line-ending artifact: the checked-in CSV is LF-normalized per
   `.gitattributes` (`*.csv text eol=lf`), and its correct SHA-256 is
   `082b3d05…e7057`. A CSV-aware CRLF reconstruction of the checked-in file
   reproduces the original manifest hash `84941248…9272` exactly, proving the
   cell content is unchanged. `python scripts/verify_sources.py` passes:
   4/4 hashes OK, **25 papers, 9 APPROVED_GREEN / 1 MAYBE_PINK /
   6 MAYBE_ORANGE / 9 REJECTED_RED** — classifications unchanged.
2. **The only clinical target the approved evidence can support today is
   cross-sectional classification of angiographically-defined CAD presence**
   (≥50% diameter narrowing) on the UCI tabular benchmarks (§4). The
   presentation's "30-day CAD risk" (slides 31, 38) is **not supported by any
   approved dataset**: none contains event dates, follow-up, or censoring.
   Labelling a cross-sectional classifier as a 30-day risk model would be a
   scientific error and a safety risk.
3. **Dataset strategy is a tiered multi-dataset programme, not a
   two-dataset restriction** (§5, §18). Tier 1 (licence-verified,
   angiographic labels): UCI Heart Disease id 45 — **all four cohorts**
   (Cleveland 303, Hungary 294, Switzerland 123, VA Long Beach 200
   rows) — and UCI Z-Alizadeh Sani id 412, all CC BY 4.0
   **[VERIFIED-EXTERNAL]**. Tier 2 (related, gated): Statlog Heart
   (overlap audit required), Z-Alizadeh **extension id 411 (same 303
   patients — never an independent cohort; its LAD/LCX/RCA fields
   define the label and are leakage if used as predictors)**.
   Tier 3 (separate tasks, never merged into angiographic CAD):
   BRFSS/NHANES self-report, PTB-XL ECG statements. Blocked/unverified:
   Kaggle "Framingham"/CVD-70K mirrors (official Framingham requires
   BioLINCC application + IRB + DUA **[VERIFIED-EXTERNAL]**), controlled
   Framingham/BioLINCC, UK Biobank, private cohorts.
4. **No approved paper deploys anything.** All 9 APPROVED_GREEN papers are
   offline model studies; the recurring, defensible research gap is
   *external validation + calibrated, explainable inference behind a
   versioned API + clinician-facing evaluation* — not a new algorithm (§3).
   Several recorded scores (100% accuracy, >97% across datasets) are
   leakage/overfitting red flags and must be treated as claims to audit,
   not targets to beat.
5. **Recommended architecture [PROPOSED, Rev. 2]: the full intended
   product is preserved** — Flutter patient app, React clinician
   dashboard, CAD classification, SHAP/LIME, wearable/health-data
   integration, monitoring/history, reassessment, clinician review,
   audit/RBAC, versioned APIs, extensible disease modules (§R2-1–§R2-3).
   It is organized as **two scientifically separate, technically
   integrated tracks** (A: clinical CAD AI; B: patient & wearable
   monitoring) on one local-first modular-monolith platform — not the
   presentation's 6-microservice Kubernetes/AWS deployment topology,
   which is a *deployment* choice, not a product feature, and is
   unmaintainable at $0 (§7, §R2-1). The Flutter app remains core scope;
   local Android emulator/physical-device testing at $0 replaces any
   assumption of app-store deployment (§R2-3, §R2-7). Free-tier hosting is
   **[OPEN / UNVERIFIED]**; local execution and GitHub Actions CI are
   the only verified zero-cost execution paths.
6. **Wearable *monitoring* is a functional Track-B feature; wearable-fed
   *CAD prediction* is blocked by evidence** (§10, §R2-2). No approved
   paper pairs wearable streams with CAD labels, so Track-B data must
   not influence Track-A scores unless/until a model is trained and
   validated on such features. A clearly labelled simulated adapter is
   the integration path; HealthKit is iOS-only and Health Connect is
   Android-only, both on-device with per-type consent.
7. **This sandbox cannot download the candidate datasets** (§6): bash
   egress to `archive.ics.uci.edu` / `physionet.org` fails (only
   github.com / pypi.org / npm registry are reachable). Dataset acquisition
   must happen in an approved local environment in a later phase, with hash
   and license snapshots recorded at download time.
8. **Rev. 2 corrections (maintainer-requested):** nested-CV-primary
   protocol with no locked holdout on n≈300 and cross-fitted calibration
   (§19, superseding §9 where they conflict); API idempotency
   contradiction resolved (replay = 200 + original response; key-reuse
   with different payload = 409) and **patient-level prediction CIs
   removed** (§20, superseding §8); explanations fixed to the
   log-odds/margin scale with a sum-check that never mixes with the
   calibrated probability (§20.5).
9. **Decisions D-011…D-030 (§13 + §23) block Phase 1**, starting with:
   primary target (D-006), dataset tiers & Kaggle-mirror rule,
   pooled-training eligibility, whether a clinician advisor exists,
   and approval of the pre-training protocol before any data download.

---

## 0. Source-integrity correction (authorized exception)

### 0.1 What was wrong

`SOURCE_MANIFEST.sha256` listed the CSV hash as
`849412486105bf3973a09cd8db851d759b20a0fcc16490468c4cebe7dfce9272`
(the hash of the original file in the starter ZIP), while the checked-in
file hashes to `082b3d05a12962c9be3aeac677a1485533d3c8b547fb63074c95984b041e7057`.

### 0.2 Verification performed this session [VERIFIED-INTERNAL]

| Check | Result |
|---|---|
| SHA-256 of checked-in `literature_review_status.csv` (LF form, UTF‑8 BOM, 42,717 bytes, 329 LF) | `082b3d05…e7057` |
| `.gitattributes` rule for CSV | `*.csv text eol=lf` — LF is the repository's canonical form |
| CSV-aware CRLF reconstruction (parse the checked-in CSV, re-emit records with Excel-style CRLF **record terminators only**, keep embedded quoted newlines as LF, preserve BOM) | SHA-256 = `84941248…9272` — **exactly the original manifest hash** |
| Parsed record identity (LF form vs CRLF form) | Identical: 26 records including header = 25 papers |
| Naive "convert every LF to CRLF" | `e702c11b…` — does **not** match; it over-converts newlines embedded inside quoted multi-line cells. This explains why a naive check appears to contradict the line-ending explanation. Only the CSV-aware test is valid. |
| Other 3 manifest entries (XLSX, PDF, speaker notes) | Already matched; untouched |

Conclusion: the discrepancy was record-terminator normalization
(CRLF → LF) on commit, exactly as the maintainer's investigation found.
The CSV's cell content — including all 25 `Supervisor_Status` values —
was never altered.

### 0.3 The change

One line in `research/source_materials/SOURCE_MANIFEST.sha256`: the CSV
entry now records the normalized hash `082b3d05…e7057`, so the manifest
describes the bytes actually in the repository. The CSV, XLSX, PDF, and
speaker notes were **not** modified.

### 0.4 Gate result

```
$ python scripts/verify_sources.py
OK sha256: literature_review_original.xlsx
OK sha256: literature_review_status.csv
OK sha256: project_presentation.pdf
OK sha256: project_presentation_speaker_notes.md
OK supervisor audit: 25 papers, statuses {'APPROVED_GREEN': 9, 'MAYBE_PINK': 1, 'MAYBE_ORANGE': 6, 'REJECTED_RED': 9}
```

Independent cross-check: the original workbook's first sheet
("Literature Review", rows 6–30) was parsed directly from
`literature_review_original.xlsx`; title-cell fills there
(9 × `FF92D050` green, 1 × theme-pink, 6 × `FFFFC000` amber/orange,
9 × `FFFF0000` red) agree with the CSV's `Supervisor_Status` /
`Original_Title_Fill` columns paper-by-paper. **[VERIFIED-INTERNAL]**

---

## 1. Materials, method, and limitations

### 1.1 Materials read in full

- `AGENTS.md`, `README.md`, `docs/DECISIONS.md`, `docs/FEATURE_REGISTER.md`,
  `docs/REPO_SETUP.md`, `docs/DATA_POLICY.md`, `prompts/arena_phase0.md`,
  and all placeholder `README.md` files in `ai/`, `backend/`, `frontend/`,
  `infra/`, `research/`, `shared/`, `tests/`. **[VERIFIED-INTERNAL]**
- `research/source_materials/project_presentation_speaker_notes.md` —
  complete, slides 1–47.
- `research/source_materials/project_presentation.pdf` — structure
  verified: 47 page objects, `/Count 47`, produced by LibreOffice Impress
  from a PptxGenJS deck (XMP metadata). The PDF's embedded fonts use custom
  encodings and this sandbox has no PDF text extractor (no `pdftotext`,
  no PyPDF), so slide content was audited via the speaker notes, which are
  the slide-order textual companion supplied for exactly this purpose.
  Visual-only slide details (diagrams, mock screenshots) are therefore
  **[AS-RECORDED — UNVERIFIED]** where the notes do not describe them.
- `research/source_materials/literature_review_status.csv` — all 25 rows,
  all 15 columns parsed.
- `research/source_materials/literature_review_original.xlsx` — workbook
  contains 6 sheets (*Literature Review, Research Gap Analysis, Project
  Insights, Source Data, Dashboard, Candidate Screening Log*); the first
  sheet was parsed and cross-checked (§0.4). The remaining sheets were
  inventoried but not relied on, per the "first sheet is authoritative"
  rule [CONFIRMED]. They should be read by the research lead before Phase 1
  (they may contain screening rationale not in the CSV).

### 1.2 Method

Read-only inspection; official-source verification via web search/fetch for
dataset licenses and access terms; sandbox capability probes (no installs,
no dataset downloads, HEAD requests only); supervisor classification audit
via the repository's own `scripts/verify_sources.py`.

### 1.3 What was deliberately NOT done

No model training, no dataset download, no package installation, no cloud
account creation, no code implementation, no branch creation, no PR merge.
Paper **full texts were not systematically retrieved** (several are behind
publisher paywalls; bash egress is restricted — §6). All paper performance
figures are therefore [AS-RECORDED — UNVERIFIED] unless stated otherwise.

---

## 2. Requirements & feature traceability (F01–F12)

Source of features: `docs/FEATURE_REGISTER.md` [CONFIRMED as *proposed*,
not approved]. Slide references are from the speaker notes. **Rev. 2
preservation rule (maintainer): no intended product feature is removed
or silently downgraded.** Each feature is classified per *layer*:
**R** = feasible with real (approved, public benchmark) data;
**P** = functional prototype on demo/benchmark data (real software,
non-clinical data); **S** = requires simulation/synthetic inputs;
**B** = blocked by scientific evidence or external access — with the
blocking reason named, so a future dataset/access change can unblock it.
The expanded preservation matrix is §17.

| ID | Capability | Slide evidence (proposal) | Phase 0 verdict | Gating dependency |
|---|---|---|---|---|
| F01 | CAD ML prediction & inference | S22, S28–S31 | **R** for cross-sectional CAD classification (Track A); **B** for 30-day/incident risk (no longitudinal labels) (§4) | D-006 target approval; D-007 dataset approval |
| F02 | Per-prediction explainability (SHAP/LIME) | S32–S34 | **R/P** (TreeSHAP on tabular models, log-odds scale §20.5); stability & clinician review [OPEN] | Clinician reviewer; explanation-fidelity tests (§19) |
| F03 | Clinician dashboard (patients, timeline, triage) | S40–S41 | **P** on benchmark/demo records; **B** for real patients (no PHI by policy) | F12 API; F11 auth |
| F04 | Patient experience — **Flutter app (core scope)**: measures, survey, lifestyle, offline | S37–S39 | **P** (full app on demo/simulated data, local Android testing §17.4); real health-data collection gated by consent/ethics design | Consent design (F07); platform decision (D-019) |
| F05 | Wearable adapters (HealthKit/Health Connect, Fitbit, Garmin, …) | S15, S38–S39 | **P** adapter pattern + **S** simulated adapter; real-device adapters gated on device/account/vendor approval; wearable→CAD prediction **B** (evidence) | Devices, developer accounts, vendor approvals (§10, §16) |
| F06 | Reassessment & follow-up loops | S31, S38, S41 | **P** mechanics; scientific validity conditions defined in §16.4; alert thresholds **B** — slide thresholds unsupported (§2.1) | Clinician review; D-016 |
| F07 | Events, audit logging, consent, data access | S26–S27, S31 | **P/R** for mechanics in the prototype platform | Privacy review; retention decision |
| F08 | Interoperability, FHIR mapping & export | S25–S27, S36 | **P minimal subset [PROPOSED]**: tabular features + prediction → FHIR-R4-shaped JSON export; full FHIR server deferred (deployment topology, not a deleted feature) | FHIR scope decision (D-020) |
| F09 | Extensible modular disease architecture | S20, S22–S23, S42–S43 | **P** as versioned disease-module boundaries in the platform (CAD first); public third-party SDK **deferred** to a later phase, explicitly | Architecture approval (D-008) |
| F10 | Reproducible evaluation & research reporting | S28–S30, S43, S46 | **R — required research core** | Protocol approval (§19) before any training |
| F11 | Authentication, access control, security | S26, S36 | **P** (hashed passwords, roles, session/JWT); no regulatory-compliance claim | Security review; no PHI in scope |
| F12 | AI–Backend versioned inference API & integration tests | S25–S26, S31 | **P — corrected contract §20 is the Phase 1 integration gate** | Contract approval (D-013) |

**Confirmed scope today [CONFIRMED]:** only the research workflow itself
(F10/F12 designs, this report). Every product capability above remains a
proposal until the §13 decisions are approved. Nothing in the presentation
constitutes scientific source authority (D-004).

### 2.1 Presentation claims that must NOT be carried forward as facts

All [AS-RECORDED — UNVERIFIED] from the speaker notes; flagged because they
would be unsafe or unreproducible if implemented literally:

| Claim (slide) | Problem |
|---|---|
| "XGBoost predicts **30-day CAD risk**"; alert at risk > 0.7, jump +0.15/7 days, escalate > 0.8 for 14 days (S31, S38) | No approved dataset has 30-day outcomes; thresholds have no cited validation. **Reject as design input** until a longitudinal dataset and clinical review exist. |
| Model table: XGBoost 93%/AUC 0.95, CNN-ECG 94%, ensemble +1.2 AUC (S30) | Literature numbers mixed across datasets; not this project's results; several exceed credible external-validation performance on n≈300 data. |
| "Latency < 250 ms p95, 1,000 predictions/sec" (S31); "on-device < 200 ms" | Unmeasured engineering targets, not requirements. No requirement source. Drop or re-derive in Phase 1. |
| "Recommended action: consider statin" attached to a SHAP tile (S34) | Treatment recommendation. **Prohibited** in any UI copy without clinical governance; explanations must not imply therapy advice. |
| "50-patient clinical pilot", FDA 510(k), EU MDR/AI-Act conformity, ISO 13485 (S42–S43) | Far outside a $0 graduation prototype; no ethics approval, site, or clinician partner is evidenced. Record as long-term aspiration only. |
| "30% reduction in missed CAD", "3 publications", "$4.2M ARR", market sizes, CPT reimbursement (S9–S10, S45) | Business projections, not research evidence; exclude from scientific documents. |
| "HIPAA/GDPR compliant by design", "wearables are FDA-cleared" (S39, S46) | A student prototype cannot claim regulatory compliance; consumer-device AFib clearances do not cover CAD prediction. |
| "MIMIC augmentation + SMOTE" as a small-data mitigation (S43) | MIMIC access is credentialed (REQUIRES_AUTHORIZATION); augmenting angiographic tabular data with ICU data is methodologically incoherent without a pairing design. SMOTE is a within-training-fold technique, not a data source. |
| Dataset shortlist "Z-Alizadeh primary, Cleveland benchmark", "Kaggle CVD (70K)" (S29) | Directionally reasonable but the Kaggle "Framingham"/CVD copies have unverified provenance (§5); primary-source UCI copies must be used. |

---

## 3. Literature audit — the 25 screened papers

Rule [CONFIRMED]: GREEN = approved evidence base; PINK/ORANGE = maybe,
usable only after explicit human promotion; RED = rejected from the
selected research scope. Results below are [AS-RECORDED — UNVERIFIED]
(transcribed from the CSV) unless a dataset fact was verified in §5.

### 3.1 Full inventory

| ID | Status | Year | Short title / focus | Data as recorded |
|---|---|---|---|---|
| P1 | ✅ GREEN | 2024 | Explainable CAD prediction, AutoGluon AutoML + SHAP | 5 merged UCI Heart Disease sets |
| P2 | ✅ GREEN | 2024 | XAI voting ensemble, SHAP+LIME | Statlog/Cleveland/Hungary (Kaggle copy) |
| P3 | 🩷 PINK | 2024 | ML + XAI technique, XGBoost/SF-2 | Cleveland + **private Egyptian hospital (n=200)** |
| P4 | ✅ GREEN | 2025 | Interpretable LightGBM, CHD scoring | BRFSS-2015, "Framingham", Z-Alizadeh (Kaggle copies) |
| P5 | ✅ GREEN | 2025 | Interpretable ML CAD stratification, SHAP, calibration plot | Z-Alizadeh Sani (UCI 412) |
| P6 | 🟠 ORANGE | 2024 | Optimized ensemble + XAI (annotated: "nothing new" vs prior) | Cleveland, "Framingham" |
| P7 | ✅ GREEN | 2025 | XAI-HD framework, MLP + SMOTEENN | Cleveland, Switzerland, "Framingham" |
| P8 | 🟠 ORANGE | 2025 | Bayesian-optimized SVM + feature selection | Z-Alizadeh Sani |
| P9 | ✅ GREEN | 2024 | ML risk-factor assessment, SHAP curves, Boruta | Z-Alizadeh Sani |
| P10 | ✅ GREEN | 2026 | Explainable hybrid DL (ensembles + CNN/LSTM), ECE reported | UCI Heart Disease, Kaggle CVD-70K |
| P11 | 🔴 RED | 2026 | Multimodal DL (CCTA+ECG+clinical), missing-data robustness | Private (2-centre, China) |
| P12 | 🔴 RED | 2025 | CVD classification with routine blood tests, XAI | Private (Almaty, n=896) |
| P13 | 🔴 RED | 2024 | ANN risk-factor ranking (psychosocial) | Private hospital records |
| P14 | ✅ GREEN | 2026 | CardioEnsemNet stacking, cross-dataset validation | Cleveland, Z-Alizadeh, Statlog, "Framingham" |
| P15 | ✅ GREEN | 2025 | Comparative ML + BESO feature selection | Z-Alizadeh, "Framingham" |
| P16 | 🔴 RED | 2024 | Genomic variant selection + classifiers | UK Biobank (controlled) |
| P17 | 🔴 RED | 2025 | 1D-CNN ECG classification + feature engineering | PhysioNet Fantasia, MIMIC-III Waveform |
| P18 | 🔴 RED | 2024 | Erythrocyte fatty-acid interpretable model + Shiny calculator | Private (single-centre, China) |
| P19 | 🟠 ORANGE | 2026 | Enhanced TabNet, Edge-IoT wearable prototype (ESP32) | Statlog/Cleveland/Hungary (n=1,190 Kaggle copy) |
| P20 | 🟠 ORANGE | 2024 | CNN-BiLSTM ECG + spatial uncertainty (SUE), Grad-CAM | PhysioNet Fantasia, INCART |
| P21 | 🟠 ORANGE | 2025 | SHAP-XGBoost "glass box" baseline | Cleveland |
| P22 | 🔴 RED | 2026 | Sex-specific ML + SHAP vs SCORE2 (n=12,116) | Private hospital cohort (Xinjiang) |
| P23 | 🟠 ORANGE | 2025 | XAI CAD stratification, routine data, calibration curves | UCI Heart Disease (4 cohorts) |
| P24 | 🔴 RED | 2025 | Stress-ECG transformer | Private single-centre |
| P25 | 🔴 RED | 2026 | AngioCAD angiography dataset + fusion model | AngioCAD (Zenodo, as recorded) |

Counts re-verified this session: 9 / 1 / 6 / 9 = 25 (§0.4).

### 3.2 Approved (GREEN) evidence — what it actually establishes

Common pattern: gradient-boosting/tree ensembles and logistic regression
on small public tabular benchmarks, SHAP (sometimes LIME) explanations,
**no external/prospective validation, no deployment, no wearable data**.
That pattern — repeated 9 times — is itself the audit finding.

| ID | Recorded headline result (UNVERIFIED) | Audit notes |
|---|---|---|
| P1 | AutoGluon ensemble Acc 91.67%, AUC 0.9562, 4-fold cross-bagging | Merged-set result; merged file not published by authors; duplicate-patient risk across the constituent UCI cohorts must be audited before any replication (§9). Sensitivity/specificity not reported. |
| P2 | XGBoost ≈89% accuracy | Full metric table not reproducible from abstract per CSV note; Kaggle copy of UCI data — re-source from UCI (§5). Dual SHAP+LIME is the reusable design idea. |
| P4 | LightGBM: BRFSS Acc 90.6%/AUROC 0.811; Framingham AUROC 0.674; Z-Alizadeh Acc 80.3% | The honest cross-dataset degradation (0.81 → 0.67) is the most decision-relevant number in the corpus: **expect large generalization drops**. Datasets mix self-reported survey labels (BRFSS) with angiographic labels — not one task (§4). |
| P5 | XGBoost Acc 90.1%, AUC 0.92, recall 0.80, with calibration plot + noise-robustness test on Z-Alizadeh | Best methodological template among GREEN (calibration + robustness), still n=303, single-centre, internal validation only. SMOTE placement relative to folds must be checked in full text before reuse. |
| P7 | MLP+SMOTEENN "100% accuracy" on Cleveland & Switzerland; 92.7% on Framingham | **Red flag.** Perfect scores on small, high-missingness cohorts almost certainly indicate leakage, resampling-before-split, or degenerate subsets. Treat as a claim to falsify, never as a baseline target. |
| P9 | Logistic regression AUROC 0.981 (95% CI 0.952–1.0) on Z-Alizadeh | Plausible only as an internal estimate on n=303; wide CI and single centre. The SHAP non-linear curve analysis is a reusable explanation idea for the dashboard. |
| P10 | Hybrid ensemble+CNN/LSTM Acc 96.94%, AUC 0.987, ECE 0.021 | 2026 paper; CNN/LSTM on tabular UCI/Kaggle-70K inputs needs full-text scrutiny (what sequence is being modelled?). Calibration (ECE) reporting is a plus. Full text **UNVERIFIED**. |
| P14 | Stacking ">97% accuracy, AUC ≈0.99 across 4 datasets" | June-2026 paper, abstract-only per CSV; near-ceiling scores across heterogeneous schemas are not credible as external performance without independent replication. Its *leakage-safe preprocessing + cross-dataset* design is the reusable part. |
| P15 | Random Forest + BESO: 90–92% accuracy; beats "traditional scores" as recorded | No XAI; single 70/30 hold-out; source sheet itself notes quoted AUCs could not be verified from open text. Use as a comparative-methods reference only. |

**What GREEN establishes [synthesis]:** tabular CAD classification on
UCI benchmarks is a solved *benchmark* exercise (typical honest range
~80–92% accuracy internally, materially lower across datasets); SHAP is
the consensus explainer; calibration and external validation are rare and
therefore publishable gaps; deployment/integration is absent. That —
not a new classifier — is the defensible contribution space (D-010,
still OPEN).

### 3.3 MAYBE (PINK/ORANGE) — disposition

- **P3 (PINK):** the only paper with an Egyptian private cohort (n=200)
  and a built mobile app. Directly relevant to the team's context but the
  data are private/not public; **cannot be used without an ethics/data
  agreement [OPEN]**. Its 97.6% accuracy is [AS-RECORDED — UNVERIFIED].
- **P19 (ORANGE):** the only wearable-prototype paper (ESP32 + ECG/PPG),
  but the model is trained on tabular benchmark data, not wearable data —
  evidence for a *simulator architecture*, not for wearable prediction.
- **P20 (ORANGE):** ECG CNN-BiLSTM + uncertainty (SUE/Grad-CAM) on **7 CAD
  patients** vs 40 healthy — technique reference only (the workbook itself
  annotates "can't be used as a benchmark").
- **P6, P8, P21, P23 (ORANGE):** incremental tabular variants (Bayesian
  tuning, SVM, SHAP-XGBoost, CatBoost + calibration). P23's calibration
  focus is methodologically useful if promoted.
- None of these may be cited as approved evidence until a human promotes
  them; this report uses them only as technique references, as recorded.

### 3.4 REJECTED (RED) — excluded

Per [CONFIRMED] rule, RED papers (P11–P13, P16–P18, P22, P24, P25) are
outside the selected research scope and are **not used** as evidence,
models, or benchmarks in the proposed plan. Observations recorded for the
decision register only: several RED items use private/controlled data
(P11, P12, P13, P16 UK Biobank, P22, P24), which would have been
infeasible at $0 in any case; P25's *dataset* (AngioCAD on Zenodo) raises
a separate question — whether a rejected paper's public dataset may be
considered as data (not evidence). That is a human decision (D-021);
this report does **not** assume permission.

### 3.5 Audit limitations

Full texts were not retrieved for most papers (paywalls, restricted
egress §6); 2026-dated papers (P10, P14, P19, P22, P25) in particular must
have their publication status and final numbers confirmed by the research
lead. No GREEN claim in §3.2 should be quoted externally until checked
against the publisher's version. This mirrors the CSV's own repeated
"not verifiable from abstract" annotations.

---

## 4. Clinical target definition — the decision everything depends on

### 4.1 Why "30-day risk" is not a relabelling of CAD classification

A model trained on UCI-style data learns
P(angiographic CAD present **at the examination** | features measured at
that examination) — a *prevalence/diagnostic* quantity from a
cross-sectional, case-enriched sample (e.g., Z-Alizadeh: 216/303 = 71%
CAD, versus a few percent in a screening population).

A "30-day risk" is P(first/new CAD event **within 30 days after today** |
features today) — an *incidence/prognostic* quantity requiring: a defined
index date, longitudinal follow-up, event dates, censoring, and a cohort
initially at risk. None of UCI-45, UCI-412, Statlog, BRFSS-2015, or the
Kaggle CVD-70K contains follow-up time or event dates [VERIFIED-EXTERNAL
for UCI label definitions, §5; AS-RECORDED for the Kaggle sets].
Prevalence odds from an enriched clinic sample also cannot be
re-interpreted as absolute risk without recalibration to a target
population incidence. **Any UI or API field named `30_day_risk`,
`risk_score` with a time horizon, or any thresholded alert derived from
these data would be scientifically false.** [CONFIRMED constraint:
AGENTS.md prohibits exactly this confusion.]

### 4.2 Candidate targets

| ID | Target | Label source | Feasible now? | Notes |
|---|---|---|---|---|
| **T1 [PROPOSED primary]** | Presence of angiographically significant CAD (≥50% diameter narrowing), cross-sectional | UCI-45 `num`>0 vs 0 (and vessel-level `num` 0–4 as an ordinal secondary analysis); UCI-412 CAD/Normal (≥50% narrowing) | **Yes** — public, CC BY 4.0, labels verified (§5) | Must be described everywhere as *"model-estimated probability that this benchmark record resembles angiography-positive cases"* — research output, not a diagnosis. |
| T2 | CAD severity / per-vessel stenosis (LAD/LCX/RCA) | UCI-411 extension per-artery fields (official UCI guidance: one artery target at a time, others excluded); P25 AngioCAD (RED) | **[OPEN]** — data dictionary at G1 + D-021 for AngioCAD only (UCI-411 is licence-verified) | The LAD/LCX/RCA fields **define** the T1 label: leakage as T1 predictors, legitimate only as T2 targets. Do not promise timelines. |
| T3 | Self-reported prevalent "heart disease or attack" (survey) | BRFSS-2015 `HeartDiseaseorAttack`; NHANES `MCQ160c–e` | Yes as a **separate secondary task** | Different construct (recall, access to diagnosis); never pooled with T1; survey weights/complex design required for population claims. |
| T4 | Incident CAD / MI over a horizon (incl. 30-day) | Framingham/BioLINCC, other longitudinal cohorts | **Blocked** | Controlled access (application + IRB + DUA [VERIFIED-EXTERNAL]); no team IRB/site evidenced; also incompatible with $0 timelines. |
| T5 | Wearable/ECG-detected CAD | PTB-XL ECG statements; PhysioNet ECG sets | **Blocked as CAD prediction**; possible as exploratory ECG-statement modelling | ECG labels ≠ angiographic CAD; no paired tabular+wearable CAD cohort exists in the approved corpus. |

**Recommendation [PROPOSED, needs D-006 approval]:** adopt T1 as the sole
Phase 1 target, with T3 as an explicitly separate external-context
experiment if time permits, and defer T2/T4/T5 behind named decisions.
All APIs, UI copy, and papers must carry the target's full name and the
"research prototype" disclaimer.

---

## 5. Dataset candidacy, licenses, and feasibility

Verification date: 2026-10-16. "Download size" is the official file size
where the source publishes it; **nothing was downloaded** (sandbox egress
blocks these hosts, §6 — sizes from official pages, not measured locally).

| # | Dataset (official source) | Population & label | n / features | Access & license [status] | Size | Verdict |
|---|---|---|---|---|---|---|
| DS-1 | **UCI Heart Disease (id 45)** — archive.ics.uci.edu/dataset/45/heart+disease | 4 clinic cohorts (Cleveland, Hungary, Switzerland, VA Long Beach), 1980s angiography patients. Label `num`: 0 = <50% narrowing, 1–4 = >50% | 303 (headline; Cleveland) + 294/123/200 in other files; 76 attrs, 14 used conventionally | Public download, **CC BY 4.0** [VERIFIED-EXTERNAL: UCI page states label definition, files, license] | Cleveland 59.2 KB; all files ≈ 564 KB total [as listed] | **PRIMARY CANDIDATE.** Caveats: Switzerland/VA files have heavy missingness; only Cleveland is "processed"; cohorts overlap conceptually with Statlog (DS-3) — cross-set duplicates must be checked (same patients recirculated). |
| DS-2 | **UCI Z-Alizadeh Sani (id 412)** — archive.ics.uci.edu/dataset/412, DOI 10.24432/C5Q31T | Shahid Rajaei Hospital (Tehran) chest-pain patients; CAD if ≥50% diameter narrowing, else Normal | 303; 54 features per UCI page (some papers say 55/56 incl. label/extension — reconcile at download) [VERIFIED-EXTERNAL: n, label, file] | Public download, **CC BY 4.0** [VERIFIED-EXTERNAL] | 120.7 KB xlsx [as listed] | **PRIMARY CANDIDATE.** 216 CAD / 87 Normal as recorded in literature; single-centre, single-ethnicity; features include symptoms/ECG/labs/echo — check each feature is available *before* angiography to avoid post-diagnosis leakage (§9). |
| DS-2b | **UCI Extension of Z-Alizadeh Sani (id 411)** — DOI 10.24432/C5461K | **Same 303 patients as DS-2** (not independent) + LAD/LCX/RCA stenosis fields | 303; 59 features | Public download, **CC BY 4.0** [VERIFIED-EXTERNAL, Rev. 2] | 128.1 KB xlsx [as listed] | **TIER 2 — same-cohort extension.** Never an external-validation set for DS-2. LAD/LCX/RCA define the CAD label → target leakage as predictors; valid as per-artery T2 targets per UCI guidance. See §R2-4.1. |
| DS-3 | **UCI Statlog Heart (id 145)** | "Similar to" UCI Heart Disease in different form (UCI wording) | 270; 13 attrs | Public, **CC BY 4.0** [VERIFIED-EXTERNAL] | 16.1 KB [as listed] | **SECONDARY.** Useful only after duplicate/overlap audit vs DS-1 Cleveland; otherwise it inflates "external validation". |
| DS-4 | **CDC BRFSS 2015** (official CDC) / Kaggle cleaned copy (253,680 rows, as recorded) | US telephone-survey adults; self-reported "heart disease or attack" (T3, **not** angiographic CAD) | 253,680 (Kaggle copy); 21 features as recorded; official CDC files larger | CDC public-use data [VERIFIED-EXTERNAL: CDC BRFSS documentation]; **Kaggle cleaned copy's licence/redistribution: UNVERIFIED** — source from CDC, not Kaggle | Kaggle copy 22.7 MB as recorded | **SECONDARY (separate T3 task only).** Needs survey-design handling; class imbalance ≈ 9.4% positive as recorded. |
| DS-5 | **Framingham Heart Study** (official) | Longitudinal cohort with incident events (T4) | ~thousands/cohort (varies) | **Controlled: BioLINCC application, local IRB evidence, DUA** [VERIFIED-EXTERNAL: ClinicalTrials/FHS policy pages]. Commercial restrictions apply. | n/a | **BLOCKED for Phase 1.** |
| DS-5k | "Framingham" **Kaggle mirrors** (used by P4/P7/P14/P15) | Unknown provenance teaching extracts | ~3–4k rows as commonly circulated | **UNVERIFIED — do not use.** A mirror cannot grant rights the official controlled source withholds; provenance, consent basis, and label definition are undocumented. | — | **PROHIBITED [PROPOSED rule]** until provenance is documented (D-012). This invalidates direct reuse of P4/P7/P14/P15 Framingham numbers. |
| DS-6 | **Kaggle Cardiovascular Disease (70K)** (used by P10; in deck S29) | Examination-time records; generic CVD present/absent; original collection undocumented | 70,000; 11 features as recorded | Kaggle page terms only; **original source, consent, label definition, redistribution rights UNVERIFIED** | ~20 MB class [UNVERIFIED] | **NOT A CANDIDATE** until provenance is established. Generic CVD ≠ CAD (T1). |
| DS-7 | **PTB-XL (PhysioNet)** | 21,801 clinical 12-lead ECGs, 18,869 patients; 71 cardiologist ECG statements (incl. MI-related) | 21,801 ECGs (10 s) | Open access, **CC BY 4.0** [VERIFIED-EXTERNAL: PhysioNet page] | Large (GB-class signals) [UNVERIFIED exact] | **EXPLORATORY ONLY (T5).** No angiographic CAD label; any "CAD" mapping from ECG statements is a new research question (D-017). Do not download in this sandbox (egress-blocked, large). |
| DS-8 | PhysioNet Fantasia / INCART / MIMIC-III Waveform (P17 RED, P20 ORANGE) | Small ECG corpora; Fantasia = healthy young/elderly sinus-rhythm subjects, **not a CAD cohort** | Tens of subjects | PhysioNet: open (Fantasia/INCART) vs credentialed (MIMIC) — per-database terms must be re-checked [OPEN] | varies | **TECHNIQUE REFERENCE ONLY.** P20's 7-CAD-patient design shows why segment-level accuracy on such sets is meaningless without subject-level splits. |
| DS-9 | **NHANES (CDC)** public-use files | US population sample; self-reported CHD/angina/MI (`MCQ160c–e`), exams, labs | ~5–10k/cycle | Public-use files free to download; restricted files via RDC **for a fee** [VERIFIED-EXTERNAL: CDC NHANES pages] | MB-class per component | **OPTIONAL SECONDARY (T3).** Only with survey weights; self-reported labels; not a CAD gold standard. |
| DS-10 | UK Biobank (P16, RED) | Genomic + clinical cohort | ~500k | Controlled application, costs likely; **RED scope** | — | **EXCLUDED.** |
| DS-11 | AngioCAD (Zenodo, via P25 RED) | 413 patients, artery-level stenosis in 7 grades + clinical data | 413 | Zenodo record/licence **UNVERIFIED** this session (not fetched); paper is RED | — | **[OPEN — D-021]** dataset-scope decision required before even verifying. |

### 5.1 Cross-cutting dataset risks

- **Recirculation/duplication:** DS-1, DS-3, and most Kaggle copies are the
  same underlying 1980s patients. "Cross-dataset validation" among them is
  not external validation. Any merged corpus (as in P1) needs record-level
  duplicate detection and a patient-overlap statement.
- **Era & spectrum bias:** DS-1/DS-2 are pre-modern-statin, referral-centre,
  angiography-selected populations. Performance will not transfer to
  screening or Egyptian outpatient populations without new data (P3's
  private cohort is the only local option, and it is gated).
- **Feature-schema incompatibility:** DS-1 (14 clinical/exercise-ECG
  features) and DS-2 (54 symptom/ECG/lab/echo features) share only a
  small common subset (demographics, some vitals/labs). A single model
  cannot serve both without a harmonized-feature design (§8.3) — this is
  the real integration research problem, and it caps any cross-dataset
  claim.
- **Licence hygiene rule [PROPOSED]:** download only from the official
  source (UCI/CDC/PhysioNet), snapshot the licence page + file hash +
  download date into the experiment log, and never commit raw data to git
  (D-007, DATA_POLICY [CONFIRMED]).

---

## 6. Agent-environment capability audit (this Arena session)

| Capability | Status | Evidence (this session) |
|---|---|---|
| Repository read/write, commit, push, PR | **VERIFIED** | `gh api`: permissions admin/maintain/push/pull/triage = true; `viewerPermission: ADMIN`; this PR is the live proof |
| Current branch discipline | **VERIFIED** | On `arena/f977cda2-cardioassist-ai`; no branch created/switched, per maintainer correction |
| Bash + Python | **VERIFIED** | Python 3.11.2, **stdlib only** (pip list: pip/setuptools/wheel only — no numpy/pandas/scikit-learn); git 2.39, gh 2.23, Node 22/npm 10 |
| CPU/RAM/disk | **VERIFIED** | 2 vCPU, 3.8 GiB RAM, ~20 GiB free disk — enough for n≈300 tabular work, not for ECG deep learning at scale |
| GPU | **UNAVAILABLE** | No `nvidia-smi`, no `/dev/nvidia*` |
| Network from bash | **PARTIALLY VERIFIED** | `curl -I https://github.com` → 200, `https://pypi.org` → 200; `archive.ics.uci.edu`, `physionet.org` → connection failure (000). **Datasets cannot be fetched from this sandbox.** |
| Web research (search/fetch tools) | **VERIFIED** | Official UCI/PhysioNet/CDC/NHLBI pages retrieved this session (§14) |
| PDF/DOCX/XLSX tooling | **LIMITED** | No `pdftotext`/PyPDF/openpyxl; XLSX/PDF audited with stdlib parsers; PDF visual text [AS-RECORDED via speaker notes] |
| Persistent storage | **VERIFIED (git only)** | Only committed+pushed files persist; sandbox files/installs do not (REPO_SETUP [CONFIRMED]) |
| Package installation | **NOT EXERCISED (prohibited)** | PyPI is reachable, but Phase 0 forbids installs; any future install must pin versions and be human-approved |
| Cloud accounts / hosting / app stores | **REQUIRES_AUTHORIZATION** | No accounts were created or checked; free-tier terms are time-sensitive → §7.4 |
| Clinical data / PHI | **UNAVAILABLE by policy** | No real patient data in this repo or session [CONFIRMED] |

Implication: Phase 1 *analysis* work (n≈300 tabular) is feasible on a
team laptop or in a later Arena session **if** a human first downloads
DS-1/DS-2 in an approved environment and supplies them through an
approved channel — the agent cannot fetch them here.

---

## 7. Zero-cost architecture assessment

### 7.1 Options compared

| Criterion | A. Modular monolith (single service) | B. Microservices (deck S25–S26: gateway, Go ingestion, Rust audit, Kafka, K8s/AWS) | C. Notebook + static demo (no backend) |
|---|---|---|---|
| $0 feasibility | **Yes** — one Python process + one DB, local or single free host | No — multiple always-on services, managed Kafka/K8s exceed free tiers; AWS requires a card | Yes |
| Team maintainability (student team, AI+backend+frontend) | **High** — one codebase, module boundaries (F09) without network boundaries | Low — distributed debugging, 4 languages (Python/Go/Rust/TS/Dart), IaC burden | Medium — but no API contract (F12 fails) |
| Testability of F12 contract | **High** — in-process contract tests | Medium — contract tests across services | Low |
| Latency/throughput needs | Ample: tabular inference is milliseconds; deck's 1,000 pred/s is not a requirement (§2.1) | Over-provisioned | n/a |
| Path to FHIR/audit (F07/F08) | Add as modules/serializers | Native but heavy | Manual |
| Risk | Monolith discipline must be enforced (module boundaries, no cross-module DB access) | **Delivery risk: highest** — the deck architecture alone could consume the whole project timeline | Fails F03/F06/F11 integration goals |

### 7.2 Recommendation [PROPOSED — D-008]

**Option A: local-first modular monolith.**

```
┌───────────────────────── single deployable (Python 3.11+, FastAPI) ─────────────────────────┐
│  api/          versioned REST (/v1/...), request validation, error model (§8)               │
│  inference/    model registry (model_id + preprocessing_id), tabular models, calibration   │
│  explanation/  TreeSHAP (tabular), explanation DTOs, fidelity metadata                      │
│  ingestion/    CSV/record intake, unit validation, (later) wearable-simulator adapter      │
│  audit/        append-only event log (who/what/model/version/hash)                         │
│  identity/     prototype auth, roles: clinician / patient / researcher (F11)               │
└──────────────┬──────────────────────────────────────────────────────────────────────────────┘
               │ SQL
        PostgreSQL (local/Docker)  — or SQLite for zero-setup dev; NO InfluxDB/Redis/Kafka
               │                                    until a measured need exists [PROPOSED]
   clinician-web (React+TS)      patient app (Flutter, CORE scope) via the
   via the same /v1 contract     same contract; local Android testing (§R2-7)
```

Rules: (1) the model is a versioned artifact *outside* git, loaded by
`model_id`; (2) inference is synchronous and stateless; (3) every
prediction writes an audit event; (4) simulated wearable input enters
through the same ingestion API as manual entry, labelled `source=simulated`;
(5) Docker Compose for local dev is the primary "deployment"; any hosted
demo is optional and disposable.

### 7.3 What is explicitly deferred

Kafka/streaming, WebSocket push, Redis/Feast feature store, InfluxDB
time-series store, Kong gateway, Kubernetes/Terraform/ArgoCD, and the
Go/Rust services from slides 25–27/36. Each may be revisited only with a
measured need and a named maintainer. FHIR is deferred to a thin export
mapping (§8.7), not a FHIR server.

### 7.4 Zero-cost execution & hosting — honest status

- **Local execution: VERIFIED for Python-level work** (this sandbox ran all
  Phase 0 checks on 2 vCPU / 3.8 GiB). **Docker Compose on team machines:
  UNVERIFIED** — no Docker daemon/binary is available in this sandbox
  (`docker` not found, no `/var/run/docker.sock`); the backend lead must
  confirm Docker (or a venv-only fallback) on team laptops at G4.
- **GitHub Actions CI: VERIFIED free quota exists** — official GitHub Docs
  list GitHub Free private repositories at 2,000 Actions minutes/month and
  500 MB artifact storage (retrieved 2026-10-16; §14). Sufficient for lint +
  unit/contract tests on a small codebase. Re-check quota before relying on it.
- **Hosted demo (any vendor free tier): UNVERIFIED.** Free tiers change
  frequently, may require a card, may sleep/cold-start, and may prohibit
  health-adjacent use in their terms. No vendor is endorsed here. At Phase 1
  kickoff, the backend lead must verify, in writing in the PR: current free
  tier, card requirement, data-location/terms, and a shutdown plan. If no
  compliant free host exists, the deliverable remains local-only — that is
  acceptable for a research prototype.
- **Object storage / model artifacts:** keep out of git [CONFIRMED];
  record SHA-256 + download URL + licence snapshot for every artifact.
  Git LFS free quota must be checked before any use (REPO_SETUP warning)
  — default is **do not use LFS**.

### 7.5 Security & privacy posture (prototype)

Hashed passwords (argon2/bcrypt via maintained library — choice at
implementation), role-based access (clinician/patient/researcher),
server-side validation, audit events with actor + model version, no PHI,
no real patient records, synthetic/demo data only, secrets via environment
variables (never committed), dependency pinning + vulnerability scanning
in CI. **No claim** of HIPAA/GDPR/regulatory compliance may be made.

---

## 8. Proposed AI–Backend inference contract (v1) — [PROPOSED, D-013]

Design only. No code exists. This is the Phase 1 contract-test gate (F12).

### 8.1 Principles

1. **One versioned contract** for clinician-web, patient app, and tests:
   `/v1/...`; breaking changes require `/v2` + migration note.
2. **Target-named outputs.** The response names the exact target (T1) and
   carries the research disclaimer. There is no `risk`, `30_day_risk`,
   `alert_level`, or treatment field.
3. **Model identity is explicit:** `model_id`, `preprocessing_id`,
   `calibration_id`, `feature_schema_id`, training-dataset IDs and hashes,
   and code commit are returned with every prediction (provenance).
4. **Units are part of the schema.** Every numeric feature declares its
   unit; unit mismatch is a `422`, never a silent conversion.
5. **Missing data is explicit:** `null` + `missing_features[]`; imputation
   happens inside the versioned preprocessing pipeline and is reported.
6. **Explanations are data, not advice:** SHAP values with feature, value,
   unit, and contribution; no recommended-action text from the model.

### 8.2 Endpoint (proposed)

`POST /v1/predictions/cad-tabular` — synchronous. **Idempotency
(Rev. 2, resolves the Rev. 1 contradiction — the full corrected
contract is §R2-6):** the client sends `Idempotency-Key: <uuid>`
(optionally mirrored as `request_id` in the body). Same key + same
canonical payload → `200` with the **original stored response** plus
`"idempotent_replay": true`; no re-inference, no second audit event
(the original `audit_id` is returned). Same key + **different**
payload → `409 idempotency_key_conflict`. A `409` is therefore never
returned for a legitimate replay. Idempotency records expire after a
versioned retention window (proposed 24 h for the prototype), after
which a reused key is treated as a new request and this is logged.

Request (abridged JSON Schema):

```json
{
  "request_id": "uuid",
  "feature_schema_id": "z_alizadeh_sani_v1 | uci_heart_14_v1",
  "features": {
    "age_years": {"value": 58, "unit": "year"},
    "sex": {"value": "female", "unit": "category"},
    "resting_systolic_bp": {"value": 142, "unit": "mmHg"},
    "serum_cholesterol": {"value": 233, "unit": "mg/dL"}
  },
  "context": {"source": "manual_entry | simulated_wearable | benchmark_import",
              "recorded_at": "ISO-8601"}
}
```

Response `200`:

```json
{
  "request_id": "uuid",
  "audit_id": "uuid",
  "model_id": "xgb_zsani_v0.1.0",
  "preprocessing_id": "prep_zsani_v1",
  "calibration_id": "isotonic_zsani_v1 | none",
  "target": {
    "id": "T1_angiographic_cad_presence",
    "definition": "Angiographic diameter narrowing >= 50% (benchmark label)",
    "time_horizon": "none_cross_sectional"
  },
  "score": {"value": 0.73, "type": "calibrated_probability | uncalibrated_score"},
  "model_performance_ref": "model_card:xgb_zsani_v0.1.0#external_validation",
  "explanation": {
    "method": "tree_shap",
    "scale": "log_odds_margin",
    "base_value": -0.31,
    "contributions": [
      {"feature": "typical_chest_pain", "value": "present", "unit": "category", "shap": 0.62}
    ],
    "note": "Contributions sum with base_value to the model log-odds, NOT to score.value (calibrated probability). See §R2-6.5."
  },
  "missing_features": ["fasting_blood_sugar"],
  "warnings": ["feature_out_of_training_range: serum_cholesterol"],
  "provenance": {"training_datasets": ["UCI-412@sha256:..."], "code_commit": "..."},
  "disclaimer": "Research prototype. Not a diagnosis. Not validated for clinical use."
}
```

### 8.3 Two schemas, not one

`uci_heart_14_v1` (age, sex, cp, trestbps mmHg, chol mg/dL, fbs>120 mg/dL,
restecg, thalach bpm, exang, oldpeak, slope, ca, thal) and
`z_alizadeh_sani_v1` (54 features, four groups) are **different feature
schemas**; a model trained on one cannot score the other. A future
`harmonized_common_v1` schema (intersection: demographics + comparable
vitals/labs) is a research deliverable (D-014), not an assumption.
Unit details for Z-Alizadeh labs are [OPEN] until its data dictionary is
inspected at download time.

### 8.4 Errors

| HTTP | `error.code` | Meaning |
|---|---|---|
| 400 | `malformed_request` | JSON/schema syntax invalid |
| 422 | `unknown_feature`, `unit_mismatch`, `value_out_of_range`, `schema_model_mismatch` | Semantically unscorable; no prediction is produced |
| 409 | `idempotency_key_conflict` | Same `Idempotency-Key` reused with a different payload (legitimate replays return `200`, §8.2) |
| 503 | `model_unavailable` | Model artifact missing/mis-hashed; system fails closed |
| 500 | `internal_error` | Logged with `audit_id`; no stack trace to client |

### 8.5 Calibration, uncertainty, explanations in the contract

`score.type` must distinguish calibrated probability from raw score;
calibration method, validation Brier score, and calibration-curve data
are published with each model version (§R2-5). **Rev. 2: there is NO
patient-level confidence interval in the response.** A per-patient CI
from a model trained/validated on n≈300 benchmark records would imply
individual precision the science does not support; uncertainty is
reported at model level (metrics with bootstrap CIs in the model card,
referenced via `model_performance_ref`). Explanations are on the
**log-odds/margin scale** (`explanation.scale`, Rev. 2): TreeSHAP
base + Σ contributions ≈ model log-odds within tolerance — this sum
check is a contract-test fixture, and the SHAP values must never be
added to, or displayed as parts of, the calibrated probability.
Before a model version is promotable, explanations must also pass the
fidelity/stability checks in §R2-5.7.

### 8.6 Mock contract tests (Phase 1 gate, F12)

Backend and frontend develop against a **mock server** implementing this
contract with fixed fixtures (no model): (a) golden request/response
pairs per schema; (b) every error code above; (c) missing-feature and
out-of-range cases; (d) duplicate `request_id`; (e) disclaimer/target
fields present (snapshot test — UI cannot drop them); (f) SHAP sum-check
fixture. Contract tests run in CI on every PR; a model swap that changes
`feature_schema_id` without a contract version bump fails CI.

### 8.7 FHIR-shaped export (minimal, [PROPOSED])

Optional read-only export mapping a prediction to FHIR R4-shaped JSON
(`Observation` for inputs, `RiskAssessment`-shaped object with the T1
definition coded as research output) for F08 demonstrations. This is a
serialization exercise, not interoperability certification, and must be
labelled as such.

---

## 9. Validation & reproducibility methodology — [PROPOSED protocol, D-015]

To be pre-registered (timestamped in-repo) **before** any training run.

### 9.1 Splitting

- **Unit of splitting is the patient/record; if any source yields multiple
  rows per patient (segments, visits), split by patient.**
- Development **(Rev. 2 corrected — full protocol §R2-5)**: repeated
  stratified nested cross-validation per dataset; **no locked holdout
  on n≈300** (a ~60-record holdout wastes data and yields unstable
  single-split estimates). Honest generalisation evidence comes from
  nested-CV out-of-fold estimates plus the untouched cross-dataset
  external evaluation (§R2-5.2). Report every outer fold, not just the mean.
- **Site-as-external-validation:** train on DS-2 → test on DS-1
  harmonized subset, and vice versa. Expect P4-style degradation; that
  number, not the internal one, headlines the abstract.
- Statlog (DS-3) may join only after the duplicate audit vs Cleveland.

### 9.2 Leakage controls (each is a CI/checklist item)

1. Imputation, scaling, encoding, feature selection, **and SMOTE fitted
   inside training folds only** (the most likely explanation for P7-style
   100% scores is resampling/selection before splitting — do not repeat it).
2. Duplicate/near-duplicate detection within and across DS-1/DS-2/DS-3
   (demographics + feature hashing); publish the overlap count.
3. Feature-availability audit for DS-2: exclude any feature not knowable
   before angiography (post-diagnosis leakage screen, clinician-reviewed).
4. No test-set peeking: hyperparameter and threshold decisions on
   validation folds only; test metrics computed once per locked model.
5. Group leakage: same-patient ECG segments never cross folds (T5 future).

### 9.3 Baselines & models

Mandatory baselines: (a) prevalence-only dummy; (b) logistic regression;
(c) a simple clinical comparator where computable (e.g., age/sex/cholesterol
logistic model). Candidates: LightGBM/XGBoost (TreeSHAP-native), random
forest. Deep learning on n=303 tabular data is **not** justified (P10's
hybrid is a cautionary example, not a template). AutoML (P1) may be run
as a sanity ceiling, with search budget logged.

### 9.4 Metrics, calibration, uncertainty

AUROC + AUPRC (with prevalence stated), sensitivity/specificity at a
**validation-chosen, pre-registered** operating point (chosen for
sensitivity at fixed specificity, clinically reviewed — not Youden on test),
Brier score, calibration intercept/slope + curve, decision-curve analysis
as supplementary. Uncertainty **(Rev. 2, §R2-5.6)**: patient-level bootstrap (2,000
  resamples, percentile + BCa sensitivity) for *model-performance*
  metrics only — never per-patient prediction intervals in the API.
  Calibration is cross-fitted so the data that fit the calibrator are
  not the data that evaluate it (§R2-5.5).
Report per-sex and per-age-group performance + calibration (fairness
audit); small subgroups reported with CIs, not suppressed silently.

### 9.5 Replication package

Pinned dependencies (lockfile), single-command pipeline
(`make reproduce` equivalent), seeds logged per fold, data hashes +
licence snapshots, model card per version (target T1 wording, training
data, metrics with CIs, limitations, intended/non-intended use), and a
run registry (append-only table: date, commit, data hash, config hash,
metrics). Negative results are reported, not file-drawered.

### 9.6 Publication strategy [PROPOSED — D-010]

Position as a **reproducibility + external-validation + contract/
integration** contribution for a graduation/regional venue or workshop:
"Calibrated, explainable CAD classification with cross-dataset validation
and a versioned clinician-facing API: a reproducibility study." Use **TRIPOD+AI** (BMJ 2024;385:e078378 — verified this revision,
§14) as the reporting reference from protocol stage onward, deposit code (not restricted data) with
a DOI-minting archive only with supervisor approval, and never claim
clinical utility, novelty of algorithm, or wearable validation that the
design does not contain.

---

## 10. Wearable & device feasibility (F05/F06)

### 10.1 Platform facts

- **Apple HealthKit:** iOS-only, on-device store, per-type user consent;
  no server-side pull API — data must flow through the user's iPhone app.
  iOS distribution requires the paid Apple Developer Program (free
  provisioning is limited/personal) — a $0 conflict to resolve explicitly.
- **Google Health Connect:** Android-only (Android 9+ via Play services;
  framework-baked on Android 14+), on-device, per-type consent.
- **Vendor APIs (Fitbit/Garmin/Withings/Samsung/Polar as listed S39):**
  each has its own developer programme, review, and partner terms —
  status **UNVERIFIED / REQUIRES_AUTHORIZATION** per vendor.
- **Hardware reality:** no team wearable, test phone inventory, or
  developer account has been evidenced in the repo. [OPEN — D-019]

### 10.2 Evidence pairing — the core problem

No approved dataset pairs wearable signals with CAD labels. P19 (ORANGE)
trains on tabular data and demos edge sensors separately; P20 (ORANGE)
has 7 CAD patients; PTB-XL (DS-7) has ECGs without angiographic labels.
Therefore **any wearable-fed CAD score in this project would be a model
applied outside its training distribution** — permissible only as a
clearly-labelled simulation, never as validation.

### 10.3 Recommendation [PROPOSED]

Phase 1: implement **one simulated wearable adapter** (synthetic HR/HRV/
steps/SpO2 + optional single-lead ECG waveform playback from public ECG
files if licence-checked) behind the ingestion API with
`source=simulated_wearable`, demonstrating F05/F06 plumbing (sync,
reassessment trigger mechanics, audit). Real HealthKit/Health Connect
adapters are gated on: a named device owner, a physical device, developer
account resolution, and clinician review of what (if anything) the UI may
say. Slide alert thresholds (S38) remain prohibited (§2.1).

---

## 11. Roadmap, owners, and acceptance gates — [PROPOSED]

Owners are roles (names to be filled by the maintainer). No dates are
committed; durations are relative and depend on the §13 decisions.

| Gate | Deliverable | Owner role | Acceptance criteria (human-checked) |
|---|---|---|---|
| **G0 (this PR)** | Phase 0 report + source-integrity fix | AI/Research | This report reviewed; D-011…D-016 answered; verify_sources passes |
| **G1 Protocol** | Pre-registered evaluation protocol (§9), dataset download log (DS-1/DS-2 hashes + licence snapshots), feature-availability audit | Research lead + supervisor | Protocol merged before any training; D-006/D-007/D-012 closed |
| **G2 Benchmarks** | Reproduced baselines (LR, RF, XGB/LGBM) with repeated nested CV per corrected protocol (§R2-5), duplicate audit published | AI | Metrics with CIs; leakage checklist (§9.2) signed; results (incl. negative) in `research/experiments/` |
| **G3 External validation** | Site-as-external results + calibration + fairness audit | AI + Research | Headline external metrics reported honestly; model card drafted |
| **G4 Contract & backend** | Monolith skeleton, `/v1` contract, mock server, contract tests in CI (F12), audit/auth modules (F07/F11) | Backend | §8.6 test matrix green; no PHI; secrets scan clean |
| **G5 Clinician web** | Dashboard on demo/benchmark data: list, timeline, explanation view (F03/F02) | Frontend + clinician reviewer | Disclaimer/target wording present (snapshot-tested); no alert/treatment language; clinician reviewer sign-off on copy |
| **G6 (optional)** | Patient experience + simulated wearable (F04/F05/F06 mechanics) | Mobile/Frontend | `source=simulated` labelling verified; consent flow reviewed |
| **G7 Write-up** | Manuscript/report with TRIPOD+AI checklist, replication package | Research lead | Supervisor approval; code archived per §9.6; retrospective + next-phase proposal |

Explicit non-goals for the whole roadmap: real patients, clinical
deployment, app-store release, regulatory submission, paid cloud,
30-day/incident risk, treatment recommendations.

---

## 12. Risk register

| ID | Risk | L/I | Mitigation |
|---|---|---|---|
| R1 | Cross-sectional score marketed (internally or in UI) as "risk"/diagnosis | M/H | Target-named API (§8), snapshot-tested disclaimer, §2.1 prohibited-claims list, clinician copy review |
| R2 | Leakage-inflated results (SMOTE/selection before split; segment-level splits) repeat P7-style 100% claims | H/H | §9.2 checklist as merge gate; nested CV; independent re-run of the pipeline by a second team member |
| R3 | Kaggle-mirror data (Framingham/CVD-70K) used without rights/provenance | M/H | DS-5k/DS-6 prohibition (D-012); official-source-only rule (§5.1) |
| R4 | n=303 overfitting; subgroup claims on handfuls of patients | H/M | External validation headline; bootstrap CIs; pre-registered analysis; report nulls |
| R5 | Feature schema/unit errors silently corrupt predictions | M/H | Contract unit validation (422), golden fixtures, SHAP sum-check |
| R6 | Free-tier/hosting terms change or require a card mid-project | M/M | Local-first design; hosting optional/disposable (§7.4); re-verify at kickoff |
| R7 | Scope creep to deck's microservices/Kubernetes/36-month vision | H/H | §7.1 decision + roadmap non-goals; any addition needs a decision entry |
| R8 | Wearable demo mistaken for validated monitoring | M/H | `source=simulated` labelling; §10.3 gate; no thresholds |
| R9 | 2026/GREEN paper claims fail full-text scrutiny, collapsing a planned comparison | M/M | §3.5 limitation; research lead verifies full texts at G1; methods chosen to stand without any single paper |
| R10 | Sensitive-data accident (real health data committed) | L/H | DATA_POLICY [CONFIRMED]; git hooks/CI secret+large-file scan at G4; demo data only |

L/I = likelihood/impact (H/M/L) — judgement calls [PROPOSED], to be
re-scored by the team.

---

## 13. Decision register — items requiring human approval

Existing open decisions (docs/DECISIONS.md, unchanged by this report):
D-006 target, D-007 datasets, D-008 stack, D-009 wearables, D-010 gap.
The following **proposed** decisions are recorded here only, per AGENTS.md
(this file is the Phase 0 decision draft; `docs/DECISIONS.md` itself was
not modified).

| ID | Decision needed | Options / recommendation | Blocks |
|---|---|---|---|
| D-011 | Approve this Phase 0 report as the Phase 1 basis? | Approve / approve with edits / reject | Everything |
| D-012 (=D-007 detail) | Dataset rule: official-source-only; DS-1 + DS-2 primary; Kaggle mirrors prohibited | **[PROPOSED] adopt** | G1–G3 |
| D-013 | Approve §8 `/v1` contract shape (target-named output, no risk/alert fields) | Approve / revise | G4–G5 |
| D-014 | Fund the harmonized-common-feature research track (DS-1 ↔ DS-2)? | Yes (core) / per-dataset models only | G3, §8.3 |
| D-015 | Approve §9 protocol incl. operating-point rule, bootstrap CIs, fairness audit | Approve at G1 with protocol text | G2 |
| D-016 | Is a clinician advisor available for threshold/explanation/UI-copy review? | Name them, or record "none — demo copy must be maximally conservative" | G5, F02/F06 |
| D-017 | ECG track: pursue PTB-XL statement-mapping (T5) as exploratory, or drop? | Drop for Phase 1 [PROPOSED] | Scope |
| D-018 | BRFSS/NHANES self-report track (T3): include as secondary experiment? | Optional; only with survey methods owner | G2+ |
| D-019 | Mobile: is there a device + platform owner (Android and/or iOS) and a developer-account resolution at $0? | Web-only demo if "no" [PROPOSED default] | F04/F05, G6 |
| D-020 | FHIR scope: thin export (§8.7) vs none | Thin export [PROPOSED] | F08 |
| D-021 | May a RED paper's public dataset (AngioCAD) be considered as *data*? Default: **no** | Human ruling required before any verification/download | T2 |
| D-022 | P3's private Egyptian cohort (PINK): pursue an ethics/data agreement, or exclude? | Exclude unless the supervisor sponsors it | Local-data track |

Also still open from DECISIONS.md: D-005 (private monorepo formal
approval — note the repo already operates as one), D-006 (= target:
recommendation T1 in §4.2), D-008 (recommendation: §7.2 monolith),
D-009 (recommendation: simulator-only, §10.3), D-010 (recommendation:
§9.6 positioning).

---

---

# PART II — REV. 2 (maintainer-requested revisions)

> Part I (§§0–13) is preserved, including all verified evidence and the
> 25-paper classification. Where Part II and Part I conflict, **Part II
> governs**; the known superseded items are: §8 idempotency/`ci_95`
> (corrected in place and in §R2-6), §9.1 locked holdout (corrected in
> place and in §R2-5), §7/§11 Flutter conditionality (Flutter is core
> scope, §R2-3), and §5's two-dataset framing (expanded in §R2-4).

## R2-1. Revised system workflow

```
TRACK A — CLINICAL CAD AI (research model, benchmark/clinical inputs)
  Clinical/record inputs (schema-validated, units checked)
    → versioned preprocessing (preprocessing_id; fitted only on training data)
    → CAD classification model (model_id; target T1 only, §4)
    → calibration layer (calibration_id; only if validated, §R2-5.5)
    → score + SHAP/LIME explanation (log-odds scale, §R2-6.5)
    → versioned inference API (§R2-6)
    → clinician review (accept / reject / request reassessment — human decision)
    → audit event with full provenance

TRACK B — PATIENT & WEARABLE MONITORING (no CAD inference by default)
  Flutter patient app (manual measures, surveys, lifestyle, offline sync)
    + wearable adapters (simulated | Health Connect | HealthKit | vendor)
    → backend validation & ingestion (schema, units, consent, source label)
    → monitoring history (time series + patient-entered records)
    → patient views (own history, trends — NO CAD score from Track-B data)
    → clinician dashboard monitoring views (reviewed alongside, not fused
      into, Track-A outputs)

UNIFIED PLATFORM (shared by both tracks)
  Identity & RBAC · patient/record management · versioned APIs & contracts ·
  audit events · consent & privacy controls · clinician review workflow ·
  model/data provenance registry · disease-module registry (CAD first)
```

Data flows one way by default: Track B never feeds Track A. The only
sanctioned crossing is a *future*, separately validated model whose
training features include wearable variables (D-009 revisited) — until
then the API must reject wearable-sourced features for CAD inference
(`422 schema_model_mismatch`, or accept-and-ignore only if the contract
version explicitly says so; **reject is the Rev. 2 recommendation**).

## R2-2. Two-track scientific architecture & safety separation

### R2-2.1 Separation rules (binding on all UI copy and APIs)

| Output class | Examples | Allowed presentation |
|---|---|---|
| **Research-model output (Track A)** | T1 score, SHAP/LIME contributions, model card | Clinician-facing research view only; carries target definition + disclaimer; never shown to patients as a diagnosis or personal risk % |
| **General health monitoring (Track B)** | HR/HRV/steps/SpO₂/sleep trends, entered measures, survey answers | Patient + clinician history views; descriptive trends only; no CAD interpretation overlaid |
| **Symptom-safety messaging** | "Seek urgent care for crushing chest pain…" type content | Only clinician-approved, guideline-sourced, model-independent static content (D-026); never triggered by a model score or an unvalidated threshold |

No automated medical decisions: the system never starts/stops/changes
treatment, never messages a patient "you are high risk" from a model
output, and never escalates care without a human clinician action.
Every Track-A output ends at a clinician review state
(`pending_review → reviewed_accepted | reviewed_rejected |
reassessment_requested`), all transitions audited.

### R2-2.2 When reassessment is scientifically valid

A reassessment (new Track-A inference for the same person) is valid
**only if at least one holds**, and the trigger is recorded:

1. **New clinical inputs** that belong to the model's feature schema
   (e.g., new labs/examination) have arrived and passed validation; or
2. **Corrected inputs** (a documented data error is fixed); or
3. **Model/preprocessing/calibration version changed**, and the record
   is re-scored for comparability (labelled `reassessment_reason=
   model_version_change`, never mixed silently with older scores); or
4. A clinician explicitly requests re-scoring of the *same* validated
   inputs to inspect explanation stability (labelled
   `clinician_requested`; result must be deterministic-identical for
   identical inputs + versions — a contract test).

Explicitly **invalid** reassessment triggers: arrival of wearable data
alone; passage of time alone ("every 7 days"); a monitoring-trend
change; a patient pressing "check again" with unchanged inputs. Those
events may refresh Track-B views, but must not produce a new CAD score.
Repeated identical-input re-scores must return the stored result
(idempotency + determinism), preventing spurious "score drift."

### R2-2.3 Disease-module extensibility (preserved, F09)

`DiseaseModule` registry entry = {target definition, feature schema,
model artifacts, explanation config, review workflow}. CAD is module #1.
A new module (e.g., hypertension) plugs in without changing the
unified-platform services; it may not share CAD scores, thresholds, or
claims. The public third-party SDK from the deck is a later-phase
decision, recorded as deferred — not deleted.

## R2-3. Feature preservation & feasibility matrix

Legend: **R** real approved data · **P** functional prototype
(real software, demo/benchmark data) · **S** simulation required ·
**B** blocked (reason named) · $0 status applies to every row.

| Intended capability (vision) | Track | Class | What ships in the first milestone(s) | Blocker / unblock condition |
|---|---|---|---|---|
| Flutter Patient Application | B + platform | **P** (core scope) | Full app: auth, measures, survey, lifestyle, offline queue, monitoring history, consent screens; local Android build/run (§R2-7.4) | iOS build needs Mac + Apple account (D-019); store release out of scope by decision, not by omission |
| React Doctor Dashboard | A/B | **P** | Patient list, record detail, Track-A review queue, explanation view, monitoring views, audit view | Real patients **B** by policy (no PHI) |
| CAD AI Classification / Assessment | A | **R** | T1 classifier(s) on approved benchmark data behind `/v1`; per-dataset models first (§R2-4) | Any other outcome (30-day, severity) **B** until labels exist (D-006) |
| Explainable AI (SHAP/LIME) | A | **R/P** | TreeSHAP (log-odds) primary; LIME as secondary/stability comparator with seed + sampling config versioned | Clinical interpretation of explanations **B** until clinician review (D-016) |
| Wearable & health-data integration | B | **P + S** | Adapter interface; **simulated adapter**; manual entry; Health Connect adapter spike if a device owner exists | Real HealthKit/vendor adapters gated (device, account, vendor approval); wearable→CAD **B** (evidence) |
| Patient monitoring & history | B | **P** | Ingestion, storage, trend views for entered/simulated streams | Population/clinical monitoring claims **B** |
| Reassessment & follow-up | A/B | **P** | Validity-gated reassessment mechanics (§R2-2.2), clinician-requested follow-up tasks (no automated alerts) | Threshold-based alerting **B** indefinitely until validated + clinician-approved |
| Clinician review workflows | Platform | **P** | Review states, accept/reject/reassess actions, reason codes, full audit | Deployment with practising clinicians **B** (no site/ethics approval) |
| Audit logging & RBAC | Platform | **P/R** | Append-only audit, roles (admin/clinician/patient/researcher), consent grants/revocations logged | Regulatory-grade compliance claims **B** (prototype) |
| Versioned Backend APIs | Platform | **P** | `/v1` contract §R2-6, mock server, contract tests in CI | — |
| Extensible disease-module architecture | Platform | **P** | Module registry (§R2-2.3), CAD module only | Second disease module = separate scientific approval |

**Nothing above is removed.** Items marked B are blocked by named
scientific/access reasons; P/S items are fully built as software with
honestly labelled data.

## R2-4. Multi-dataset research feasibility strategy

Starting point is the GREEN corpus (P1, P2, P4, P5, P7, P9, P10, P14,
P15). Dataset sources named by GREEN papers: UCI-45, UCI-412, UCI
Statlog-145, BRFSS-2015, "Framingham" (Kaggle copies — see prohibition),
Kaggle CVD-70K (P10), plus their constituent sources. RED papers
contribute **no** methodological evidence; a RED-associated dataset
needs its own human scope decision (D-021, AngioCAD). MAYBE papers'
datasets may be inventoried but not used as approved evidence.

### R2-4.1 Cohort inventory — rows ≠ independent patients

| Cohort | Rows (as listed) | Independent patients | Target | Missingness / schema notes [status] |
|---|---|---|---|---|
| UCI-45 Cleveland | 303 | Presumed 303; **verify at download** (IDs were de-identified; duplicates cannot be ruled out from the listing) | `num` 0–4 angiographic (0 = <50%, ≥1 = >50%) | Processed file; 14 of 76 attrs conventional; missing values present [VERIFIED-EXTERNAL: UCI listing] |
| UCI-45 Hungary | 294 | Presumed 294, verify | Same `num` definition | Unprocessed file; schema alignment to Cleveland's 14 must be re-derived, not assumed |
| UCI-45 Switzerland | 123 | Presumed 123, verify | Same | Known heavy missingness in the literature [AS-RECORDED]; per-feature missingness must be tabulated before any modelling — usable only if pre-registered completeness rules pass |
| UCI-45 VA Long Beach | 200 | Presumed 200, verify | Same | Unprocessed; site/population differs (veterans) — transportability is a research question, not noise |
| UCI Statlog-145 | 270 | **Unknown overlap with Cleveland** — treat as *suspect-duplicate* until audited | Heart-disease presence (Statlog coding) | "Similar to UCI Heart Disease in different form" (UCI); exact/near-duplicate audit on shared features is a G1 gate |
| UCI-412 Z-Alizadeh Sani | 303 | 303 as listed | CAD ≥50% narrowing (binary) | 54 features, no missing as listed; pre-angiography availability audit required |
| UCI-411 Z-Alizadeh **extension** | 303 | **The same 303 patients as UCI-412 — NOT independent** | CAD defined by LAD/LCX/RCA stenosis | 59 features incl. LAD/LCX/RCA. **Those three fields define the label: they are target leakage as CAD predictors** (UCI itself warns to keep only one of LAD/LCX/RCA/Cath per task). Legitimate uses: (a) per-artery stenosis targets T2 with the other arteries excluded per UCI guidance; (b) feature superset for the same patients. Never count as a second cohort, never as external validation for UCI-412 models [VERIFIED-EXTERNAL: UCI-411 listing, CC BY 4.0, DOI 10.24432/C5461K] |
| BRFSS-2015 (CDC official) | 253,680 survey rows (Kaggle cleaned copy as recorded; source from CDC) | Survey respondents; complex sample design | Self-reported "heart disease or attack" (T3) | Separate task; survey weights; never pooled with angiographic labels |
| NHANES (CDC) | ~5–10k/cycle | Sampled persons + weights | Self-reported CHD/angina/MI (T3) | Not GREEN-derived; optional Tier-3 track (D-018) |
| PTB-XL | 21,801 ECGs / 18,869 patients | Patient count given; ECG-level splits prohibited | ECG statements (not CAD) | Tier-3 exploratory only |
| Framingham official | Longitudinal cohort | Controlled | Incident events (T4) | **Blocked**: BioLINCC + IRB + DUA |
| Kaggle "Framingham", CVD-70K | ~4k / 70k rows as circulated | Unknown provenance | Unknown/unverified | **Prohibited** until provenance documented (D-012) |
| AngioCAD (RED P25) | 413 | As recorded | Stenosis grades | Dataset use needs separate human scope decision (D-021) |

Row-count discipline: every experiment log must report **rows,
patients, outcome events, and sites** separately; a "920-patient UCI
corpus" claim is valid only after the UCI-45 internal cohort
boundaries and Statlog overlap are empirically handled.

### R2-4.2 The four strategies (in mandatory order)

**Strategy A — Dataset-specific models + internal validation
(always permitted, first).** One model family per cohort with its
native schema (`uci_cleveland_v1`, `z_alizadeh_sani_v1`, …), each
evaluated by the §R2-5 protocol. Deliverable: per-cohort model cards.
This is the only strategy whose results may be reported without
harmonization caveats.

**Strategy B — Feature-harmonized cross-dataset evaluation
(conditional).** Permitted only when **all** hold for the pair:
(i) same target definition & threshold (T1 ≥50% for UCI-45 cohorts
and UCI-412 — plausible; BRFSS/NHANES/PTB-XL fail by construction);
(ii) a documented feature mapping with identical units/definitions
(e.g., cholesterol mg/dL vs mmol/L converted explicitly);
(iii) patient independence established (duplicate audit passed;
UCI-411 can never be an external set for UCI-412);
(iv) missingness mechanisms tabulated and handled identically.
Design: train on cohort X → evaluate untouched on cohort Y
(site-as-external), both directions where schemas allow; the
harmonized intersection schema is versioned (`harmonized_t1_v1`)
and expected to be small (demographics + comparable vitals/labs).

**Strategy C — Pooled training (strictly gated).** Considered only
after A and B results exist, and only if: B's compatibility checks
pass for every pooled cohort; site is carried as a variable for
heterogeneity analysis; duplicates removed; and **evaluation uses a
cohort (or later, a dataset) never touched in pooling** — leave-one-
site-out at minimum. Pooled data with random row splits is
prohibited (site leakage masquerading as performance). If no
independent evaluation source survives these rules, pooling is
reported as exploratory development only, with no generalisation claim.

**Strategy D — Larger, differently-labelled datasets as separate
tasks (never merged).** BRFSS/NHANES (T3 survey task: sampling
weights, prevalence calibration to the survey population) and PTB-XL
(T5 ECG-statement task) may run as clearly separate sub-studies with
their own protocols and papers sections. Their scores, features, and
cohorts must never be concatenated with T1 data or described as CAD
validation.

### R2-4.3 Ranking (scientific validity + reproducibility, not n)

1. **UCI-412** (angiographic, richest pre-angio schema, CC BY) —
   development + T2 potential via UCI-411's per-artery targets.
2. **UCI-45 Cleveland** (literature comparability) + **Hungary**
   (largest sibling cohort) for Strategy B.
3. **UCI-45 VA Long Beach, Switzerland** — Strategy B stress tests;
   Switzerland contingent on the missingness audit.
4. **Statlog-145** — only post-overlap-audit, as sensitivity analysis.
5. **BRFSS → NHANES (Tier 3, separate task)**, then **PTB-XL**
   (exploratory ECG), in that order.
6. Framingham-official / UK Biobank / private Egyptian cohort (P3) /
   AngioCAD: **decision-gated**, in no plan until D-021/D-022/access
   approvals exist.

### R2-4.4 Pre-download feasibility checklist (per dataset, G1)

Official URL + licence snapshot; population/setting/dates; target
definition verbatim; rows/patients/events; per-feature dictionary,
units, missingness; patient-independence statement; overlap-audit
plan; leakage screen (is every feature knowable before the label?);
transportability notes (era, ethnicity, sex, referral pathway);
storage (local, out of git); hash at download. No checklist = no download.

## R2-5. Corrected experimental protocol — [PROPOSED, requires supervisor approval before any training (D-024)]

This section **supersedes §9** where they differ. Reporting reference:
**TRIPOD+AI** (Collins et al., BMJ 2024;385:e078378
[VERIFIED-EXTERNAL, §14]) — its 27 items are adopted as the protocol
and manuscript checklist, including data-source, outcome-definition,
fairness, and open-science items. Adopting a reporting guideline is
not a novelty or quality claim; it is a completeness floor.

### R2-5.1 Pre-training protocol (gate G1 — nothing trains before this is merged)

Written, timestamped, supervisor-approved protocol containing:
research question + target (T1 verbatim); dataset checklist
(§R2-4.4) per cohort; eligibility/exclusion rules; feature dictionary
with availability timing; strategies A→D applicability decision;
model families + baselines; tuning budget; primary metric
(pre-registered: AUROC on external evaluation; secondary AUPRC,
Brier, calibration slope/intercept, sensitivity at pre-fixed
specificity); calibration plan; subgroup plan; CI method; leakage
checklist sign-off; code/data versioning plan; stopping/reporting
rules (including reporting null results). Amendments after seeing
results require a dated amendment note — no silent protocol drift.

### R2-5.2 Resampling: nested CV, no locked holdout (small-n rule)

- Primary: **repeated stratified nested CV** (proposed 5×5 outer/
  inner, repeated ×4 with distinct seeds; exact numbers fixed in the
  protocol). Outer folds give the unbiased performance estimate;
  inner folds do all tuning. Every outer fold's metrics are reported.
- **No single locked holdout on n≈300**: a ~60-row holdout has
  ~±10-point metric instability and discards 20% of development data.
  The untouched-test role is played by **Strategy-B external cohorts**,
  which are stronger evidence anyway. If a future cohort ≥1,000
  patients arrives, a locked holdout may be reintroduced by amendment.
- All splits are patient-level (grouped where repeated rows exist)
  and stratified by outcome and, in pooled settings, by site.

### R2-5.3 Within-fold discipline

Imputation, scaling, encoding, feature selection, class balancing
(SMOTE and variants), and threshold selection are **fitted inside
training folds only** and applied frozen to validation/test folds.
Pipeline objects are the unit of versioning (`preprocessing_id`
bundles every fitted transformer + its training-fold provenance).

### R2-5.4 Leakage audits (all documented per dataset)

1. **Target leakage:** exclude any feature that is the label, a label
   component, or post-label (UCI-411 LAD/LCX/RCA for the CAD target;
   angiography-derived fields; treatments started because of the
   diagnosis).
2. **Feature-availability:** each feature timestamped relative to the
   angiography decision; unknowable-before-label features excluded
   or the model is explicitly re-scoped as post-test.
3. **Duplicate patients:** exact + fuzzy matching on stable
   demographics/features within and across cohorts (incl. Statlog);
   matches resolved before splitting; overlap counts published.
4. **Site/era leakage (pooled runs):** leave-one-site-out evaluation;
   no random row splits across sites.
5. **Preprocessing leakage:** §R2-5.3; plus a negative control
   (label-shuffle run must score at chance — a cheap leakage tripwire).

### R2-5.5 Calibration without leakage

- Calibrator (Platt logistic preferred at n≈300; isotonic only with
  a pre-registered minimum-events justification) is fitted on
  **cross-fitted out-of-fold predictions** of the development data,
  never on the same predictions used to report calibration.
- Calibration is *evaluated* on external cohorts untouched by both
  model and calibrator; recalibration on an external cohort converts
  that cohort into development data and is reported as model updating
  (TRIPOD+AI item), requiring a new untouched evaluation source.
- Report Brier, intercept, slope, and the calibration plot (with
  binning/smoothing method stated) alongside discrimination; a model
  with `calibration_id: "none"` must serve `score.type:
  "uncalibrated_score"` and the UI must not render it as "% risk".

### R2-5.6 Uncertainty & confidence intervals (corrected)

- **Model-performance CIs:** patient-level nonparametric bootstrap,
  2,000 resamples, percentile intervals primary with a BCa
  sensitivity where computable; resampling respects patient groups
  and site clusters; nested-CV estimates report fold dispersion as
  well as bootstrap CIs, and the protocol names which is primary.
- **No patient-level prediction intervals** are computed, served, or
  displayed (§R2-6). Individual-score stability may be studied
  scientifically (e.g., explanation stability §R2-5.7) without being
  presented as a confidence interval for a person's disease status.

### R2-5.7 Explanations: scale, calibration consistency, stability

- Declared scale: **log-odds/margin** for tree models (TreeSHAP).
  Sum check on that scale only. The calibrated probability is a
  monotone transform of the margin; SHAP contributions must not be
  re-based onto the probability scale (a probability-scale
  attribution, if ever required, is a different method and needs
  its own validation + contract version).
- LIME (when used): fixed seed + sampling count in
  `explanation_config_id`; reported as a secondary, local, surrogate
  explanation with its fidelity (local R²) attached; SHAP/LIME
  disagreements are logged, not hidden.
- Stability checks pre-registration: rank correlation of top-k
  features across CV folds and across bootstrap refits; explanation
  sensitivity to clinically plausible input perturbations (cf. P5's
  noise test, as a technique reference). Unstable explanations block
  UI display of feature attributions for that model version.

### R2-5.8 Subgroups & fairness (small-n honest rules)

Pre-specified subgroups (sex; age <55 / 55–70 / >70; site) with a
**minimum reportable cell**: ≥30 patients **and** ≥10 events per
class in the subgroup, else descriptive counts only, no performance
claim, no significance test. No post-hoc subgroup hunting; all
pre-specified results reported whether favourable or not;
subgroup calibration reported only when the cell rule passes for
calibration bins as well.

### R2-5.9 Claims discipline

Internal-validation numbers are labelled "internal (nested-CV)";
cross-dataset numbers "external — one site/cohort pair"; nothing is
"clinically validated". No novelty/publication claim is made in any
output until the G7 broader-literature verification (systematic
comparison beyond the 25-paper corpus) is done (D-025, TRIPOD+AI
checklist completed at protocol **and** manuscript stages).

## R2-6. Corrected AI–Backend API contract (v1) — [PROPOSED, D-013; supersedes §8 on every point of conflict]

### R2-6.1 Idempotency (contradiction resolved)

| Case | Result |
|---|---|
| First request with `Idempotency-Key: K` | `200`, response stored under (K, payload-hash), `audit_id` created, `"idempotent_replay": false` |
| Retry: same K, **byte-identical canonical payload** | `200`, **stored response verbatim** + `"idempotent_replay": true`, same `audit_id`; **no re-inference, no new audit event** (a replay access-log line is allowed) |
| Same K, **different payload** | `409 {"error": {"code": "idempotency_key_conflict", "original_audit_id": "…"}}` |
| Key older than retention window (proposed 24 h, configurable per deployment, versioned in the contract's meta endpoint) | Treated as new; logged; clients must not rely on replay beyond the window |

Determinism corollary (contract test): identical inputs + identical
`model_id`/`preprocessing_id`/`calibration_id` must produce
identical scores/explanations, replay or not.

### R2-6.2 Schemas — required vs optional

Common envelope (required): `request_id` (uuid, informational —
idempotency is governed by the header key), `feature_schema_id`,
`context.source` ∈ {`benchmark_import`, `clinician_entry`,
`patient_entry`, `simulated_wearable`}, `context.recorded_at`
(ISO-8601). `context.patient_ref` is a **pseudonymous prototype ID**
only (no names/identifiers — validation rejects identifier-shaped
values per a maintained denylist, prototype-grade control).

Per-schema feature rules (`uci_heart_14_v1` shown; the DS-2 schema
`z_alizadeh_sani_v1` mirrors this table at G1 after its dictionary audit):

| Feature | Type / unit | Required? | Missing handling |
|---|---|---|---|
| `age_years` | integer, year (18–120) | Required | Missing → `422 missing_required_feature` (no silent imputation for identity-critical fields, list fixed per schema) |
| `sex` | enum {female, male} (source coding documented) | Required | As above |
| `chest_pain_type` | enum (schema codebook) | Required | As above |
| `resting_systolic_bp` | number, **mmHg** | Required | As above |
| `serum_cholesterol` | number, **mg/dL** (mmol/L input → `422 unit_mismatch`; conversion is a client responsibility in v1) | Optional | Pipeline imputation (fitted on training folds), listed in `missing_features[]`, warning added |
| `fasting_blood_sugar_gt_120` | boolean (threshold in mg/dL) | Optional | As above |
| `resting_ecg` | enum | Optional | As above |
| `max_heart_rate_bpm` | number, **bpm** | Optional | As above |
| `exercise_induced_angina` | boolean | Optional | As above |
| `st_depression_oldpeak` | number, **mm (mV-equivalent as in source — dictionary confirmation at G1)** | Optional | As above |
| `st_slope` | enum | Optional | As above |
| `num_major_vessels_fluoroscopy` (`ca`) | integer 0–3 | Optional — **flagged**: knowable only after imaging; schemas must declare `availability: post_test`, and models for pre-test use exclude it (protocol decision, D-027) | As above |
| `thalassemia_test` (`thal`) | enum | Optional (`post_test` flag as above) | As above |

General rules: unknown feature → `422 unknown_feature`; wrong unit
→ `422 unit_mismatch`; out-of-range → `422 value_out_of_range`
(schema carries plausible ranges; out-of-*training*-range is a
warning, not an error); `null` means "not provided" — a feature
asserted with value `0` is data, never conflated with missing.
Track-B (wearable) fields sent to this endpoint →
`422 schema_model_mismatch` (§R2-1 one-way rule).

### R2-6.3 Versioning

URL major version (`/v1`) + artifact versions in every response
(`model_id`, `preprocessing_id`, `calibration_id`,
`feature_schema_id`, `explanation_config_id`). A change to feature
semantics/units/target = new `feature_schema_id` version and, if
breaking, `/v2`. Models are never silently swapped:
`GET /v1/models/current` exposes the active artifact set + hashes;
promotion requires the §R2-5 gates + a contract-test run against the
new model (mock fixtures with a stub model make this testable
before any real model exists).

### R2-6.4 Response (corrected — changes from §8 shown)

`score.type` ∈ {`calibrated_probability`, `uncalibrated_score`};
**no `ci_95` or any per-patient interval** (removed in §8 as well);
`model_performance_ref` points to the model card section containing
externally-validated metrics **with** bootstrap CIs; `explanation`
carries `scale: "log_odds_margin"`, `base_value`, `contributions[]`
(each: feature, original value, unit, shap), and the invariant
*base + Σ ≈ margin* (machine-checked); `warnings[]`,
`missing_features[]`, `provenance{training_datasets[ids+sha256],
code_commit, artifact_hashes}`, `review_state: "pending_review"`,
and the research disclaimer are mandatory — a response missing any
of them fails contract validation in CI.

### R2-6.5 Explanation ↔ calibrated-score compatibility (binding)

The UI may display the calibrated probability (if calibrated) and,
separately, the ranked log-odds contributions labelled *"influence
on the model score (log-odds scale)"*. It must never present SHAP
values as percentage points of the probability, never colour them
as risk itself, and never attach action text. If only an
uncalibrated score exists, the UI shows the score as a relative
model output (no % sign) per §R2-5.5.

### R2-6.6 Mock fixtures & contract tests (Backend/Frontend unblocked during AI experiments)

Fixture pack (versioned with the contract, stub model, fixed seeds):
**F-01** golden valid request/response per schema; **F-02** every
error code in §8.4 (as amended by R2-6.1); **F-03** missing-optional
(with imputation notice) vs missing-required (`422`); **F-04**
unit-mismatch + unknown-feature + out-of-range; **F-05** idempotent
replay (response identity + single audit event) and **F-06**
key-conflict `409`; **F-07** determinism (repeat → identical score);
**F-08** SHAP sum-check within tolerance on the margin scale;
**F-09** Track-B payload rejected for inference; **F-10** mandatory-
field snapshot (target definition, disclaimer, provenance, review
state present — UI snapshot tests pin their rendering);
**F-11** uncalibrated model rendering (no % / no probability label);
**F-12** model-swap simulation (new `model_id`, contract unchanged
→ tests pass; schema change without version bump → tests fail).
Backend serves these from a mock implementation; Frontend integrates
against the mock from day one; AI replaces the stub behind the same
contract at G4. All fixtures run in CI on every PR.

### R2-6.7 Non-inference platform APIs (sketch, same versioning/audit rules)

Monitoring ingestion `POST /v1/monitoring/observations` (source-
labelled, consent-checked, unit-validated; purely Track B);
history reads `GET /v1/patients/{ref}/monitoring`; review actions
`POST /v1/predictions/{audit_id}/review` {action, reason_code};
consent `POST/DELETE /v1/patients/{ref}/consents`. Schemas for
these are a G4 deliverable reviewed with the same rigour; no
endpoint may return a Track-A score inside a Track-B resource.

## R2-7. Parallel team execution roadmap — [PROPOSED]

Supersedes §11's sequential gates with three parallel workstreams
plus shared integration checkpoints (IC). Owners are roles until the
maintainer names people. All milestones are local/$0.

### R2-7.1 Workstream A — AI & Research

| # | Deliverable | Depends on | Acceptance |
|---|---|---|---|
| A1 | Pre-training protocol (§R2-5.1) + TRIPOD+AI checklist (protocol stage) | D-006, D-024 approval | Supervisor sign-off recorded; merged before downloads |
| A2 | Dataset acquisition pack: §R2-4.4 checklist per Tier-1/2 cohort, hashes + licence snapshots, overlap & missingness audits | A1 | Independent team member re-verifies hashes; datasets stored out of git |
| A3 | Strategy-A baselines per cohort (dummy, LR, RF, GBM) under nested CV | A2 | Model cards v0; leakage checklist + label-shuffle control pass |
| A4 | Strategy-B harmonization + cross-dataset external evaluation; Strategy-C eligibility report (go/no-go with evidence) | A3 | External metrics headline; D-028 records pooling decision |
| A5 | Calibration (cross-fitted) + explanation stability pack; model cards v1 + `model_performance_ref` content | A4 | §R2-5.5/5.7 checks pass; unpromotable models explicitly marked |
| A6 | Artifact registry: versioned model/preprocessing/calibration artifacts + hashes, promotion log | A5 | Serving loads by ID + hash; mismatch fails closed (`503`) |

### R2-7.2 Workstream B — Backend

| # | Deliverable | Depends on | Acceptance |
|---|---|---|---|
| B1 | DB schema: users/roles, pseudonymous patient records, monitoring observations, predictions + review states, audit events, consents, artifact registry | Contract §R2-6 (draft suffices) | Migration + seed on SQLite/PostgreSQL; no PHI fields exist |
| B2 | **Mock inference server** implementing §R2-6 + fixture pack F-01…F-12 | B1 | Contract tests green in CI; Frontend unblocked (IC-1) |
| B3 | Platform APIs: auth/RBAC, ingestion (Track B), history, review, consent, audit query | B2 | Role-matrix tests; every mutation writes an audit event |
| B4 | Real model serving behind the same contract (stub → A6 artifacts) | A6, B3 | Fixture suite re-run against the real model; determinism + sum-check pass (IC-3) |
| B5 | Thin FHIR-shaped export (§8.7) — optional, time-boxed | B3 | Labelled research serialization; no interoperability claim |

### R2-7.3 Workstream C — Frontend (React clinician web + Flutter patient app)

| # | Deliverable | Depends on | Acceptance |
|---|---|---|---|
| C1 | Clinician dashboard skeleton vs mock: list, record detail, review queue, explanation view (per §R2-6.5 rendering rules) | B2 fixtures | Snapshot tests pin target/disclaimer; no % on uncalibrated scores (IC-1) |
| C2 | Monitoring views (Track-B history/trends, source labels visible) | B3 | Simulated vs entered vs device data distinguishable everywhere |
| C3 | **Flutter patient app** vs mock: auth, measures, survey, lifestyle, offline queue + sync, history, consent screens | B2 fixtures | Runs on local Android emulator **and** one physical device (§R2-7.4); offline→sync test passes |
| C4 | Clinician-review + reassessment UX (validity-gated per §R2-2.2; no alert language) | B3, D-016 copy review | Copy checklist signed; invalid triggers demonstrably produce no new score |
| C5 | Accessibility/wording pass with clinician reviewer (or conservative-copy fallback, D-016) | C1–C4 | Reviewer sign-off or fallback recorded |

### R2-7.4 Flutter at $0 — local Android testing (investigated, Rev. 2)

[VERIFIED-EXTERNAL, §14] Android Studio + Emulator are free
downloads; apps run/debug on virtual devices (AVD) and on physical
Android phones over USB/Wi-Fi ADB with Developer options + USB
debugging — **no Play Store account, no fee, no store release is
required for the entire development/test cycle**. Health Connect is
on-device on Android (availability by version/Play services), so the
simulated adapter remains the default data source; a real Health
Connect spike is optional and device-gated. iOS remains gated on a
Mac + Apple Developer account decision (D-019) and is **not** on the
critical path. Team-machine verification task (first week of Phase 1,
owner: Mobile lead): install Flutter + Android Studio on one team
laptop, run the template app on emulator + one phone, record
versions — if no team machine can run the emulator (RAM/virtualization),
physical-device-only testing is the fallback and is recorded as a risk.

### R2-7.5 Integration checkpoints

**IC-1** (B2+C1+C3): end-to-end demo on fixtures — clinician reviews a
mock prediction; patient app submits monitoring data; audit shows
both. **IC-2** (B3+C2/C4): consent, RBAC, and reassessment-validity
behaviour proven on mocks. **IC-3** (A6+B4+C1): first real model
behind the unchanged contract; fixture suite + explanation checks
green; UI wording re-snapshotted. **IC-4**: full research-prototype
walkthrough + TRIPOD+AI manuscript draft (G7 equivalent).

### R2-7.6 Recommended first implementation milestone

**M1 — "Contract-first vertical slice on mock data"** (B1+B2+C1+C3
core screens, IC-1): the platform shell with auth/RBAC, mock
inference, review states, monitoring ingestion (simulated adapter),
and both frontends running locally, while Workstream A executes
A1–A2 in parallel. Rationale: it validates the riskiest integration
assumptions (contract, idempotency, explanation rendering, offline
sync) with zero scientific dependencies, so AI results later land
without rework. M1 explicitly contains **no trained model, no real
data, and no clinical claim** — and is only proposed here; Phase 1
starts on explicit human approval of this report.

## R2-8. Scientific validation risks (Rev. 2 supplement to §12)

| ID | Risk | Control (owner) |
|---|---|---|
| SR1 | Harmonization quietly changes the target (different thresholds/codings across cohorts) | Feature-mapping table signed by Research lead; target verbatim per cohort in every model card (A) |
| SR2 | Pooled training inflates performance via site/patient leakage | Strategy-C gate (§R2-4.2); leave-one-site-out; duplicate audit (A) |
| SR3 | Calibration fitted and judged on the same data | Cross-fitted calibrators; external calibration evaluation only (A) |
| SR4 | SHAP (log-odds) misread as probability contributions in UI/papers | §R2-6.5 rendering rules + snapshot tests (Backend/Frontend) |
| SR5 | Subgroup "findings" from tiny cells | §R2-5.8 minimum-cell rule; pre-specification (A) |
| SR6 | Wearable variables drift into CAD inference by convenience | One-way rule + `422` + contract test F-09 (Backend) |
| SR7 | Benchmark overfitting to UCI quirks presented as clinical performance | Claims discipline §R2-5.9; external headline metric (A + supervisor) |
| SR8 | Extension (UCI-411) mistaken for independent validation cohort | §R2-4.1 prohibition; dataset registry entry marks `independent_patients: same_as_UCI-412` (A) |
| SR9 | Reassessment spam creates illusory score trajectories | §R2-2.2 validity triggers + determinism test (Backend) |
| SR10 | Reporting drift from TRIPOD+AI (missing outcome/fairness/open-science items) | Checklist at protocol and manuscript gates (A) |

## R2-9. Revised decision register (Rev. 2 additions — approval required)

D-011…D-022 (§13) stand unless superseded below. New/clarified:

| ID | Decision | Recommendation |
|---|---|---|
| D-023 | Adopt the two-track architecture + separation rules (§R2-1/R2-2) as binding design constraints | Adopt |
| D-024 | Approve the pre-training protocol mechanism (§R2-5.1) — protocol document itself returns for supervisor sign-off at G1/A1 before any download/training | Approve mechanism |
| D-025 | Broader-literature verification required before any novelty/publication claim (§R2-5.9) | Adopt as gate |
| D-026 | Symptom-safety messaging: who (clinician) approves static content + sources, or is it omitted from the prototype? | Omit until a named clinician approves content |
| D-027 | `ca`/`thal` post-test features: excluded from the primary (pre-test) models and relegated to a labelled post-test variant? | Exclude from primary |
| D-028 | Strategy-C pooled training: eligible at all, and only after Strategy-B evidence? | Conditional — decide on A4 evidence |
| D-029 | First milestone = M1 contract-first vertical slice (§R2-7.6) | Adopt as Phase 1 entry (on report approval) |
| D-030 | Android-first Flutter testing (emulator + physical device; iOS deferred per D-019) | Adopt |

**Blocking decisions for any implementation:** D-011 (report
approval), D-006 (target), D-012/D-007 (dataset rules), D-013
(contract), D-023, D-024, D-029, plus D-016 (clinician advisor) for
any user-facing explanation/alert copy. **No Phase 1 work — including
dataset downloads — is authorized by this revision.**

## 14. References

Internal [VERIFIED-INTERNAL]: `AGENTS.md`; `README.md`;
`docs/DECISIONS.md` (D-001…D-010); `docs/FEATURE_REGISTER.md` (F01–F12);
`docs/DATA_POLICY.md`; `docs/REPO_SETUP.md`;
`research/source_materials/` (PDF 47 pp.; speaker notes slides 1–47;
XLSX first sheet rows 6–30; CSV 25 rows — all hashes §0);
`scripts/verify_sources.py` (passing output §0.4).

External (official/primary; accessed 2026-10-16):
1. UCI Heart Disease (id 45) — label (`num` 0 = <50%, 1 = >50% narrowing),
   files/sizes, CC BY 4.0: https://archive.ics.uci.edu/dataset/45/heart+disease
2. UCI Z-Alizadeh Sani (id 412) — 303 records, CAD = ≥50% narrowing,
   54 features, CC BY 4.0, DOI 10.24432/C5Q31T:
   https://archive.ics.uci.edu/dataset/412/z+alizadeh+sani
3. UCI Statlog (Heart) (id 145) — 270 instances, CC BY 4.0:
   https://archive.ics.uci.edu/dataset/145/statlog+heart
4. PhysioNet PTB-XL v1.0.3 — 21,801 ECGs / 18,869 patients, open access,
   CC BY 4.0: https://physionet.org/content/ptb-xl/1.0.3/
5. CDC BRFSS 2015 survey data & documentation:
   https://www.cdc.gov/brfss/annual_data/annual_2015.html
6. CDC NHANES — public-use files free; restricted data via RDC (fee);
   MCQ160c–e item wording:
   https://wwwn.cdc.gov/nchs/nhanes/ and
   https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2021/DataFiles/MCQ_L.htm
7. Framingham Heart Study / BioLINCC — controlled access: registration,
   IRB evidence, data-use agreement:
   https://www.framinghamheartstudy.org/fhs-for-researchers/policies-and-procedures/data-sharing-principles/
   and https://clinicaltrials.gov/study/NCT00005121
8. GitHub Docs — Actions billing (Free, private repos: 2,000 min/month,
   500 MB artifact storage) and Free-plan branch-protection limits:
   https://docs.github.com/en/billing/concepts/product-billing/github-actions
9. Apple HealthKit (iOS, on-device, per-type consent):
   https://developer.apple.com/documentation/healthkit
10. Android Health Connect (Android, on-device, per-type consent):
    https://developer.android.com/health-and-fitness/health-connect
11. **(Rev. 2)** UCI Extension of Z-Alizadeh Sani (id 411) — same 303
    patients as id 412, 59 features incl. label-defining LAD/LCX/RCA,
    CC BY 4.0, DOI 10.24432/C5461K:
    https://archive.ics.uci.edu/dataset/411/extention+of+z+alizadeh+sani+dataset
12. **(Rev. 2)** TRIPOD+AI statement — Collins GS et al., BMJ
    2024;385:e078378. https://doi.org/10.1136/bmj-2023-078378
13. **(Rev. 2)** Android Studio / Emulator / physical-device debugging
    (free local testing, no store account):
    https://developer.android.com/studio/run/emulator and
    https://developer.android.com/studio/run/device

Paper-level URLs/DOIs are recorded per-paper in
`research/source_materials/literature_review_status.csv` (P1–P25) and are
[AS-RECORDED — UNVERIFIED] until checked against publisher versions (§3.5).

---

## Appendix A — What this report did NOT establish

- No dataset was downloaded; every size/label statement for DS-1/DS-2/DS-3/
  DS-7 is from the official listing page, not from inspected data. Feature
  units (esp. DS-2 labs), missingness, and the 54-vs-56-feature question
  are G1 download-day tasks.
- No paper full text was systematically verified; §3 numbers are the
  screening sheet's, with red flags noted.
- No free hosting vendor, wearable vendor API, app-store path, or
  Framingham/Kaggle-mirror provenance was verified — all are marked
  UNVERIFIED / REQUIRES_AUTHORIZATION rather than assumed.
- The workbook's non-first sheets (Research Gap Analysis, Project
  Insights, Source Data, Dashboard, Candidate Screening Log) were
  inventoried, not audited; the research lead should mine them at G1.
- No clinician, patient, or supervisor interview was conducted by the agent.

## Appendix B — Pre-commit checklist for this PR (completed)

- [x] `python scripts/verify_sources.py` passes (§0.4)
- [x] 25-paper classification unchanged (9/1/6/9, audit + XLSX cross-check)
- [x] Only two paths changed: `research/source_materials/SOURCE_MANIFEST.sha256`
      (one line) and `docs/phase0/PHASE0_REVIEW_DRAFT.md` (new)
- [x] No datasets, weights, credentials, PHI, or large files added
- [x] PR targets `main`; **not merged**; Phase 1 not started
- [x] **Rev. 2**: maintainer-requested sections added (§R2-1–§R2-9); §8/§9 contradictions corrected in place; PR #1 updated on the same branch (`arena/f977cda2-cardioassist-ai`); classifications and §0 evidence preserved

*End of Phase 0 draft. Awaiting human review.*
