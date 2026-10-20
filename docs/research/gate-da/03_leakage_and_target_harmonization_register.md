# 03 — Leakage and Target-Harmonization Register

**Status: PROPOSED register for Gate DA audit planning and Gate PT
sign-off. No item here is a completed audit** — audits require the
acquired data, which does not exist in this repository. Severity:
**BLOCKER** = invalidates results if unresolved; **MAJOR** = must be
ruled before Gate PT; **MINOR** = must be documented in the protocol.
Evidence labels per [README](README.md). Prior rulings from Phase 0
(§F-1, §R2-5.4) are carried forward and cited, not re-decided.

## 1. Target-harmonization register (H)

| ID | Sev | Issue | Evidence | Required ruling / audit step (owner: Gate DA audit → Gate PT freeze) |
|---|---|---|---|---|
| H-01 | **BLOCKER** for Strategy B/C | **Threshold wording differs:** UCI-45 `num`: 0 = <50%, 1 = **>50%** diameter narrowing; UCI-412/411: CAD = **≥50%** narrowing. A record at exactly 50% is labelled differently by source. | **VERIFIED** 2026-10-20 from both official UCI pages; Phase 0 §R2-4.2 harmonization note | Record per source: verbatim definition; whether raw stenosis % or per-vessel fields survive in the acquired files; whether exactly-50% records can be identified and handled under one pre-registered rule. Outcomes allowed: *identical / reconciled / related-but-not-identical*. Without a documented ruling, cross-dataset results must be described as evaluation across **related-but-not-identical** labels, and pooling (Strategy C) is prohibited. |
| H-02 | **BLOCKER** for any severity claim | UCI-45 `num` values 1–4: official page supports **presence (0 vs 1–4) only**; no per-vessel or ordinal interpretation is established. | **VERIFIED** (official page: experiments "distinguish presence (values 1,2,3,4) from absence (value 0)"); Phase 0 Rev. 3 | T1 binarization 0 vs 1–4 is the only approved-direction use, and even that awaits P-1 freeze. Severity/ordinal modelling of `num` is **UNAPPROVED** — do not build targets, metrics, or UI severity displays on it. |
| H-03 | **BLOCKER** for T1 pooling | **Different constructs must never be merged into T1:** BRFSS/NHANES self-report (T3), PTB-XL ECG statements (T5), CVD-70K generic CVD, Framingham incident events (T4). | Document 01 §4 (VERIFIED/VERIFIED-PH0 per source) | Strategy D separation is binding: separate protocols, separate reports, no concatenated training/evaluation, no describing any T3/T4/T5 result as CAD-presence validation. |
| H-04 | MAJOR | **Coding direction/format differs across files that share names:** Statlog target is 1=absence/2=presence (vs UCI-45 0 vs 1–4); UCI-45's four cohorts ship as one processed + three unprocessed files whose 14-feature alignment must be re-derived; DS-2 feature counts are reported as 54/55/56 in secondary sources. | **VERIFIED** (official pages, 2026-10-20) for Statlog coding and file structure; DS-2 count discrepancy SOURCE-REPORTED | Gate DA dictionary audit must produce, per file: verbatim coding table, recoding map to the frozen T1 coding, and a feature-count reconciliation. No recoding may be inferred from Kaggle copies or paper tables. |
| H-05 | MAJOR | **Prevalence/spectrum non-comparability:** angiography-referred, case-enriched cohorts (DS-2 ≈71% CAD SOURCE-REPORTED; DS-1 referral cohorts) vs any survey/screening population. A score calibrated on DS-1/DS-2 is a **benchmark-cohort model score**, never an absolute population/personal probability (Phase 0 §F-6). | Phase 0 §4.1/§F-6 [governing]; class counts to be confirmed at audit | Protocol must state target-population limits verbatim; calibration may only be claimed for the evaluated cohort's spectrum; UI/API copy rules in document 06 §4. |
| H-06 | MAJOR | **Era effects:** DS-1 cohorts predate contemporary therapy (statins, modern revascularization thresholds); DS-2 is a single-centre cohort of its era. Feature–label relationships may not transport. | Population/dates as listed on official pages (**VERIFIED** as listings; clinical-era interpretation is PROPOSED) | Limitations section of every report; no contemporary-population claim; era recorded in every model card (document 05 §6). |
| H-07 | MINOR | **Same-named features, different measurement definitions** (e.g. cholesterol assays/units across sites and decades; BP "on admission" vs examination BP). Matching names ≠ harmonized variables (Phase 0 §5.1). | Phase 0 §5.1; DS-1 units VERIFIED from official page; DS-2 units UNVERIFIED | Harmonized intersection (Strategy B) may include a feature only with an identical-definition + unit ruling per source pair, recorded in the versioned mapping (`harmonized_t1_v1` is a *future* Gate PT artifact — it does not exist yet). |

## 2. Leakage register (L)

| ID | Sev | Leakage / contamination risk | Evidence | Required disposition |
|---|---|---|---|---|
| L-01 | **BLOCKER** | **UCI-45 `ca`** (major vessels coloured by fluoroscopy): obtained by the fluoroscopy/angiography that determines the label. | **VERIFIED** (official page definition); Phase 0 §F-1 ruling carried forward | **Excluded from primary pre-angiography models.** This package does not reopen that ruling. Any future exception requires a re-scoped (post-test) target + clinician + Gate PT approval. Mirrored in the mock contracts by design (`mock_feature_excluded_probe`, document 06). |
| L-02 | **BLOCKER** | **UCI-45 per-vessel angiography fields** (attributes 59–68: `lmt, ladprox, laddist, diag, cxmain, ramus, om1, om2, rcaprox, rcadist`) and cath-date fields (55–57): these *are* the label's components/procedure record. | **VERIFIED** (official 76-attribute list, 2026-10-20) | Excluded from all T1 predictors. Identifiers in the same list (`id`, `ccf`, `name` — dummy-replaced per official page) are likewise never features and never re-identified. |
| L-03 | **BLOCKER** | **UCI-411 LAD/LCX/RCA (+ Cath):** official note — CAD "happens when at least one of these three arteries is stenotic"; only one of LAD/LCX/RCA/Cath may be kept per task. | **VERIFIED** (official page, 2026-10-20) | Never T1 predictors. Only conceivable use: one artery as a *target* in a separate, supervisor-approved T2 protocol with the other arteries + Cath excluded. |
| L-04 | **BLOCKER** | **UCI-411 ↔ UCI-412 identity:** same 303 patients. Using 411 to "externally validate" a 412 model (or counting 606 patients) is false independence. | **VERIFIED** (both official pages, same n/creators; Phase 0 §R2-4.1) | Hard prohibition; overlap statement mandatory in every experiment log (rows / patients / events / sites reported separately). |
| L-05 | **BLOCKER** until audited | **Statlog-145 ↔ Cleveland overlap (suspect recirculation)** and, generally, Kaggle merged copies (P1/P2/P19) recirculating DS-1/DS-3 patients. Duplicate patients across train/test inflate every metric and fake "external" success. | UCI Statlog wording "similar to … in a slightly different form" (**VERIFIED**); overlap itself **UNVERIFIED** until data audit | Gate DA: exact + near-duplicate screening on shared stable features within and across DS-1 cohorts/DS-3; publish counts; resolve matches *before* any split. Statlog stays sensitivity-only until passed (document 02). |
| L-06 | MAJOR | **UCI-45 `thal`** (thallium stress-test result 3/6/7 — *not* thalassemia): admissibility depends on the frozen prediction moment (before stress testing → excluded; after routine pre-angiography workup → admissible only with clinician + protocol approval). | **VERIFIED** coding (official page); Phase 0 §F-1 ruling | **Pending-review: excluded from the primary model until the feature-availability audit rules.** Processed-file recodings must be confirmed against the acquired dictionary. Mirrored by `mock_feature_pending_availability_probe` (document 06). |
| L-07 | MAJOR | **Exercise-test feature block (UCI-45 `thalach, exang, oldpeak, slope`)**: knowable only *after* an exercise test. A model using them is a post-exercise-test model; presenting it as a pre-test/clinic-visit tool would be an availability falsehood. Medications during testing (`dig, prop, nitr, pro, diuretic` in the 76-attribute list) are further timing-sensitive fields. | **VERIFIED** definitions (official page); prediction-moment consequence is PROPOSED methodology | Gate PT must freeze one explicit prediction moment and admit/exclude this block accordingly; the moment must be named wherever the model is described (documents 05, 06). |
| L-08 | MAJOR | **UCI-412 availability timing (whole-dictionary audit):** 54 features across demographic / symptom & examination / ECG / laboratory & **echocardiography** groups. Any feature recorded during/after angiography, derived from its result, or reflecting post-diagnosis treatment is leakage; echo and treatment-adjacent fields are the audit-critical categories. **No per-feature ruling exists yet and none is asserted here.** | Groups **VERIFIED** (official page); per-feature timing **UNVERIFIED** | Gate DA read-only audit produces a per-feature availability table (knowable-before-angiography-decision: yes/no/unknown + source). Gate PT admits only "yes" features into the primary dictionary; "unknown" defaults to excluded. Clinician reviewer confirms borderline rulings (P-4-adjacent; document 07 Q-SCI-3). |
| L-09 | MAJOR | **Preprocessing/selection leakage (the P7 failure mode):** imputation, scaling, encoding, feature selection, SMOTE/balancing, or threshold choice fitted before/on the full data — the most plausible explanation of recorded 100% scores. | Phase 0 §9.2/§R2-5.3/§R2-5.4 [governing]; P7 figure SOURCE-REPORTED | Within-fold fitting only; label-shuffle negative control mandatory; SMOTE (if ever used) inside training folds only with a calibration caveat (document 05 §§3–5). Using any recorded paper score as a target to beat is prohibited. |
| L-10 | MAJOR | **Site/era leakage in pooled runs (Strategy C):** random row splits across sites let site identity masquerade as signal. | Phase 0 §R2-4.2/§R2-5.4 | Leave-one-site-out evaluation minimum; site carried as a variable; pooling prohibited until Strategy B checks pass for every pooled cohort (H-01 ruling included). |
| L-11 | MINOR | **Test-set peeking via repeated external evaluation:** repeatedly evaluating on the "external" cohort during development converts it into a tuning set. | Standard methodology; Phase 0 §9.2(4) | External cohorts are evaluated **once per locked model** under the frozen protocol; every evaluation is logged; a cohort used for any selection decision is re-labelled development data thereafter. |
| L-12 | MINOR | **Identifier/provenance leakage into features:** record order, file/site codes, or acquisition dates used (even accidentally, e.g. via row index) as predictors. | PROPOSED audit item | Feature dictionary must enumerate *every* admitted column; anything not in the dictionary is excluded by construction (schema-validated ingestion, document 06). |

## 3. Items that look like leakage but are not (to prevent over-exclusion)

- **Resting ECG, symptoms, examination, demographics, pre-procedure labs**
  are legitimate *if* the frozen prediction moment postdates their routine
  collection and the audit confirms recording time (L-08 process decides;
  nothing is pre-cleared here).
- **Class imbalance itself** (e.g. DS-2's reported 216/87) is not leakage;
  it is a design fact to handle transparently (document 05 §5). Synthetic
  oversampling never creates new patients and must never be described as
  doing so.
- **Using DS-411's extra non-artery features for the same patients** is
  not leakage per se, but it is also not new data: it changes the feature
  dictionary of the *same* cohort and must be versioned as such.

## 4. Register maintenance rule

This register is a living audit plan, not a result. At Gate DA, each row
gets: auditor, date, acquired-file hash, verbatim evidence, ruling.
At Gate PT, each BLOCKER/MAJOR row must be **closed with a signed ruling**
or the dependent modelling step does not proceed. New rows discovered
during the audit are appended with new IDs — rows are never deleted or
silently edited.
