# CardioAssist AI — Phase 0 Research & Feasibility Review (DRAFT)

| Field | Value |
|---|---|
| Status | **DRAFT — awaiting human scientific and engineering review. Not approved.** |
| Date | 2026-10-16 |
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
3. **Two primary candidate datasets survive license verification** (§5):
   UCI Heart Disease (id 45) and UCI Z-Alizadeh Sani (id 412), both
   CC BY 4.0 at the official UCI source **[VERIFIED-EXTERNAL]**, both small
   (n = 303), single-era, and heavily reused. Everything else is secondary,
   controlled-access, self-reported-label, ECG-only, or provenance-unverified
   (notably the Kaggle "Framingham" mirrors — official Framingham data
   requires a BioLINCC application, IRB evidence, and a data-use agreement
   **[VERIFIED-EXTERNAL]**, so a Kaggle copy cannot be assumed licensed).
4. **No approved paper deploys anything.** All 9 APPROVED_GREEN papers are
   offline model studies; the recurring, defensible research gap is
   *external validation + calibrated, explainable inference behind a
   versioned API + clinician-facing evaluation* — not a new algorithm (§3).
   Several recorded scores (100% accuracy, >97% across datasets) are
   leakage/overfitting red flags and must be treated as claims to audit,
   not targets to beat.
5. **Recommended architecture [PROPOSED]: a local-first modular monolith**
   (single Python/FastAPI service with internal AI, explanation, audit, and
   auth modules; PostgreSQL or SQLite locally; React clinician web;
   Flutter patient app only if a device owner is confirmed) — not the
   presentation's 6-microservice Kubernetes/AWS design, which is
   unmaintainable at $0 and with this team's Phase 0 resources (§7).
   Free-tier hosting is **[OPEN / UNVERIFIED]** and must be re-checked at
   implementation time; local execution and GitHub Actions CI are the only
   verified zero-cost execution paths.
6. **Wearables are simulation-only in the next phase** (§10). No approved
   paper pairs wearable streams with CAD labels; HealthKit is iOS-only and
   Health Connect is Android-only, both on-device with per-type consent, and
   no team device/developer-account access has been confirmed.
7. **This sandbox cannot download the candidate datasets** (§6): bash
   egress to `archive.ics.uci.edu` / `physionet.org` fails (only
   github.com / pypi.org / npm registry are reachable). Dataset acquisition
   must happen in an approved local environment in a later phase, with hash
   and license snapshots recorded at download time.
8. **Twelve decisions (D-011…D-022, §13) block Phase 1**, starting with:
   primary target definition (D-006), primary dataset(s) and the Kaggle
   mirror prohibition (D-007), and whether a clinician advisor is available
   to review thresholds, explanations, and UI language.

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
not approved]. Slide references are from the speaker notes. Feasibility
classes: **A** = implementable for $0 in a later phase (local/free
resources); **S** = implementable only with simulators / synthetic inputs
(integration demonstration, **not** clinical evidence); **B** = blocked by
data, hardware, access, or clinical review.

| ID | Capability | Slide evidence (proposal) | Phase 0 verdict | Gating dependency |
|---|---|---|---|---|
| F01 | CAD ML prediction & inference | S22, S28–S31: XGBoost tabular + CNN ECG, "30-day risk" | **A for cross-sectional CAD classification only; B for 30-day/incident risk** (§4) | D-006 target approval; D-007 dataset approval |
| F02 | Per-prediction explainability (SHAP/LIME) | S32–S34 | **A** (TreeSHAP on tabular models); stability & clinician review are [OPEN] | Clinician reviewer; explanation-fidelity tests (§9) |
| F03 | Clinician dashboard (patients, timeline, triage) | S40–S41, "7-minute consult" | **A as a research demo on retrospective/demo data; B for real patients** | F12 API; F11 auth; no real patient data [CONFIRMED] |
| F04 | Patient experience (measures, survey, lifestyle, offline) | S37–S39 | **S/A** — forms & offline cache A; real health-data collection B | Consent design (F07); platform decision (D-019) |
| F05 | Wearable adapters (HealthKit/Health Connect, Fitbit, Garmin, …) | S15, S38–S39 | **S only** (simulated adapter); real adapters **B** | Devices, developer accounts, vendor API approvals (§10) |
| F06 | Reassessment & follow-up loops | S31, S38, S41 | **S**; alert thresholds **B** — slide thresholds are unsupported (§2.1) | Clinical review of any threshold; D-016 |
| F07 | Events, audit logging, consent, data access | S26–S27, S31 | **A** for audit/consent mechanics in a demo system | Privacy review; data-retention decision |
| F08 | Interoperability, FHIR mapping & export | S25–S27, S36 | **A minimal subset [PROPOSED]**: map the small tabular feature set + prediction to FHIR R4 Observation/RiskAssessment-shaped JSON; full FHIR server **B/overkill** | FHIR scope decision (D-020) |
| F09 | Extensible modular disease architecture | S20, S22–S23, S42–S43 | **A as module boundaries in a monolith; B as a public SDK** | Architecture approval (D-008) |
| F10 | Reproducible evaluation & research reporting | S28–S30, S43, S46 | **A — required research core** | Protocol approval (§9) before any training |
| F11 | Authentication, access control, security | S26, S36 | **A for prototype auth (hashed passwords, roles, session/JWT); no regulatory-compliance claim** | Security review; no PHI in scope |
| F12 | AI–Backend versioned inference API & integration tests | S25–S26, S31 | **A — design in §8 is the Phase 1 gate** | Contract approval (D-013) |

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
| T2 | CAD severity / per-vessel stenosis (LAD/LCX/RCA) | UCI-412 extension fields as recorded in literature; P25 AngioCAD (RED) | **[OPEN]** — needs data-dictionary confirmation and the D-021 dataset-scope decision | Attractive differentiator; do not promise. |
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
   clinician-web (React+TS)      patient app (Flutter) — ONLY if D-019 confirms
   via the same /v1 contract     device + platform owner; otherwise web-only demo
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

`POST /v1/predictions/cad-tabular` — synchronous, idempotent via
`request_id` (UUID, client-supplied; duplicate `request_id` returns the
original audit record).

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
  "score": {"value": 0.73, "type": "calibrated_probability | uncalibrated_score",
            "ci_95": [0.61, 0.83]},
  "explanation": {
    "method": "tree_shap",
    "base_value": 0.42,
    "contributions": [
      {"feature": "typical_chest_pain", "value": "present", "unit": "category", "shap": 0.18}
    ]
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
| 409 | `duplicate_request_id` (with original `audit_id`) | Idempotency guard |
| 503 | `model_unavailable` | Model artifact missing/mis-hashed; system fails closed |
| 500 | `internal_error` | Logged with `audit_id`; no stack trace to client |

### 8.5 Calibration, uncertainty, explanations in the contract

`score.type` must distinguish calibrated probability from raw score;
calibration method, validation Brier score, and calibration-curve data
are published with each model version (§9). `ci_95` comes from the
pre-registered uncertainty method (bootstrap / conformal — D-015).
Explanations must pass fidelity/stability checks (e.g., SHAP sum check:
base + Σ contributions ≈ score on the model's link scale, within tolerance)
before a model version is promotable.

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
- Development: stratified nested cross-validation (outer 5-fold for
  unbiased estimates, inner folds for tuning) per dataset, with a locked
  hold-out (20%) touched once. On n=303, report every fold, not just the mean.
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
as supplementary. Uncertainty: 1,000× bootstrap CIs (patient-level) for all
headline metrics; calibration via Platt/isotonic fitted on validation only.
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
and a versioned clinician-facing API: a reproducibility study." Follow a
recognized prediction-model reporting checklist (TRIPOD-family; confirm
current version at writing time), deposit code (not restricted data) with
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
| **G2 Benchmarks** | Reproduced baselines (LR, RF, XGB/LGBM) with nested CV + locked hold-out, duplicate audit published | AI | Metrics with CIs; leakage checklist (§9.2) signed; results (incl. negative) in `research/experiments/` |
| **G3 External validation** | Site-as-external results + calibration + fairness audit | AI + Research | Headline external metrics reported honestly; model card drafted |
| **G4 Contract & backend** | Monolith skeleton, `/v1` contract, mock server, contract tests in CI (F12), audit/auth modules (F07/F11) | Backend | §8.6 test matrix green; no PHI; secrets scan clean |
| **G5 Clinician web** | Dashboard on demo/benchmark data: list, timeline, explanation view (F03/F02) | Frontend + clinician reviewer | Disclaimer/target wording present (snapshot-tested); no alert/treatment language; clinician reviewer sign-off on copy |
| **G6 (optional)** | Patient experience + simulated wearable (F04/F05/F06 mechanics) | Mobile/Frontend | `source=simulated` labelling verified; consent flow reviewed |
| **G7 Write-up** | Manuscript/report with TRIPOD-family checklist, replication package | Research lead | Supervisor approval; code archived per §9.6; Phase 1 retrospective + Phase 2 proposal |

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

*End of Phase 0 draft. Awaiting human review.*
