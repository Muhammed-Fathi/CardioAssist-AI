# 01 — Dataset-Source and Suitability Matrix

**Status: PROPOSED assessment for Gate DA (P-2). No dataset listed here is
approved or acquired.** Evidence labels per [README](README.md). Official
UCI facts for ids 45/412/411/145 and the CDC BRFSS 2015 page and Framingham
data-sharing principles were **re-fetched and re-verified on 2026-10-20**;
items marked VERIFIED-PH0 rest on the Phase 0 verification of 2026-10-16
(Phase 0 §14) and must be re-snapshotted at any future acquisition.

---

## 1. The provisional target every candidate is judged against

**T1 (PROPOSED, PENDING P-1/D-006):** cross-sectional classification of
*angiographically defined CAD presence* — diameter narrowing at the ~50%
threshold, measured at the examination, on patients referred for
angiography. It is a prevalence/diagnostic quantity in a case-enriched,
referral population (e.g. Z-Alizadeh Sani 216/303 ≈ 71% CAD as
SOURCE-REPORTED in the literature; Phase 0 §4.1).

Explicitly **not** T1:

- Future/incident events (30-day or any horizon) — requires follow-up,
  event dates, and censoring that **no T1 candidate contains**. Calling a
  T1 score a "30-day risk" is a scientific error (Phase 0 §4.1, AGENTS.md).
- Self-reported "heart disease or attack" (BRFSS/NHANES) — different
  construct (recall + access to diagnosis), target T3.
- ECG statements (PTB-XL) — no angiographic CAD label, target T5.
- Generic "cardiovascular disease present/absent" (Kaggle CVD-70K) —
  label is not CAD and provenance is undocumented.
- CAD *severity*/per-vessel stenosis — target T2, **UNAPPROVED**
  (Phase 0: UCI `num` 1–4 supports presence 0 vs 1–4 only; it does not
  establish an ordinal/per-vessel interpretation).

## 2. Traceability: supervisor-selected (GREEN) papers → datasets they name

Re-read from `research/source_materials/literature_review_status.csv` this
session (**VERIFIED**, internal): 25 papers = 9 GREEN (P1, P2, P4, P5, P7,
P9, P10, P14, P15), 1 PINK (P3), 6 ORANGE (P6, P8, P19, P20, P21, P23),
9 RED (P11, P12, P13, P16, P17, P18, P22, P24, P25). This matches the
reported baseline exactly.

| GREEN paper | Dataset(s) as recorded in the CSV (**SOURCE-REPORTED**) | Candidate(s) below |
|---|---|---|
| P1 (AutoGluon CAD, 2024) | "Combined five public CAD datasets" via UCI Heart Disease id 45; merged file **not separately published by the authors** | DS-1 (constituents only; the merged file itself is not an acquirable source) |
| P2 (XAI voting ensemble, 2024) | Kaggle "Heart Statlog Cleveland Hungary" copy; Cleveland via UCI | DS-1, DS-3 (re-source from UCI, not Kaggle) |
| P4 (LightGBM CHD, 2025) | BRFSS_2015 (Kaggle copy), "Framingham" (Kaggle), Z-Alizadeh Sani (UCI) | DS-2, DS-4, DS-6k |
| P5 (Interpretable ML CAD, 2025) | Z-Alizadeh Sani, UCI id 412 (DOI 10.24432/C5Q31T) | DS-2 |
| P7 (XAI-HD, 2025) | Cleveland & Switzerland (UCI id 45), "Framingham" (Kaggle) | DS-1, DS-6k |
| P9 (Risk-factor ML, 2024) | Z-Alizadeh Sani (UCI) | DS-2 |
| P10 (Hybrid DL CVD, 2026) | UCI Heart Disease; Kaggle Cardiovascular Disease (70K) | DS-1, DS-7 |
| P14 (CardioEnsemNet, 2026) | Cleveland (UCI), Z-Alizadeh Sani (UCI 412), Statlog Heart (UCI 145), "Framingham" (Kaggle) | DS-1, DS-2, DS-3, DS-6k |
| P15 (Comparative ML CAD, 2025) | Z-Alizadeh Sani (UCI 412), "Framingham" (Kaggle) | DS-2, DS-6k |

Notes: (a) GREEN status approves the *paper as evidence*, not any dataset
(D-003; README). (b) All recorded performance figures for these papers are
**SOURCE-REPORTED — UNVERIFIED** (Phase 0 §3.2); P7's recorded 100% and
P14's recorded >97%/AUC≈0.99 are leakage/overfitting red flags to audit,
not baselines. (c) Datasets named **only** by PINK/ORANGE/RED papers
(P3's private Egyptian cohort; P25's AngioCAD; PhysioNet ECG sets via
P17/P20) are inventoried in §4 for completeness and carry **no** GREEN
support. (d) The project presentation (slides/speaker notes) names the
same UCI/Framingham families, but presentation dataset recommendations
are **not approved research evidence** (D-004).

## 3. Suitability matrix — T1 candidates and near-candidates

### DS-1 — UCI Heart Disease (id 45): Cleveland, Hungary, Switzerland, VA Long Beach

- **Official source / identifier:** UCI Machine Learning Repository,
  dataset **45**, "Heart Disease"; DOI 10.24432/C52P4X (citation block on
  the official page). Files as listed: `cleveland.data` 59.2 KB (the one
  "processed" file), `hungarian.data` 60.7 KB, `switzerland.data` 24.1 KB,
  `long-beach-va.data` 39 KB, `new.data` 380.6 KB. **[VERIFIED 2026-10-20]**
- **Original publication:** Detrano, Jánosi, Steinbrunn, Pfisterer et al.,
  "International application of a new probability algorithm for the
  diagnosis of coronary artery disease," *Am J Cardiol* 1989 — listed as
  the dataset's introductory paper on the official page. **[VERIFIED]**
  Relationship to GREEN papers: constituent source for P1, P2, P7, P10,
  P14 (table §2).
- **Purpose / population / label:** 4 clinic cohorts of patients referred
  for coronary angiography (1980s). Label `num`: **0 = <50% diameter
  narrowing; 1 = >50% diameter narrowing** (in any major vessel); values
  1–4 in the distributed coding. Official page: "Experiments … have
  concentrated on simply attempting to distinguish presence (values
  1,2,3,4) from absence (value 0)." n: Cleveland 303 (headline), Hungary
  294, Switzerland 123, VA Long Beach 200 rows as listed. 76 attributes
  exist; 14 are conventionally used (13 predictors + `num`). Missing
  values: **Yes** (Switzerland/VA known heavy missingness —
  SOURCE-REPORTED/literature; per-feature tabulation is a Gate DA audit
  output, not yet done). **[VERIFIED for definition/counts/files/license;
  missingness distribution UNVERIFIED until audit]**
- **Target compatibility with T1:** **Direct** — this *is* an angiographic
  presence label, with two caveats: (i) threshold wording is `>50%`
  (strictly greater), versus `≥50%` in DS-2 — boundary records at exactly
  50% cannot currently be identified or reconciled (register L/H items,
  document 03); (ii) `num` 1–4 must be binarized 0 vs 1–4 for T1;
  severity/ordinal use is **UNAPPROVED**.
- **Feature dictionary (conventional 14):** `age` (years), `sex`, `cp`
  (chest-pain type 1–4), `trestbps` (resting BP on admission, mm Hg),
  `chol` (serum cholesterol, mg/dl), `fbs` (>120 mg/dl binary), `restecg`
  (0–2), `thalach` (max heart rate achieved), `exang` (exercise-induced
  angina), `oldpeak` (ST depression induced by exercise relative to rest —
  **no unit stated on the official page; unit UNVERIFIED**, Phase 0 §F-1),
  `slope` (peak-exercise ST slope 1–3), `ca` (major vessels coloured by
  fluoroscopy, 0–3), `thal` (3=normal, 6=fixed defect, 7=reversible
  defect — thallium stress-test result, **not** thalassemia; Phase 0 §F-1)
  + `num`. **[VERIFIED from official page 2026-10-20]** Full 76-attribute
  dictionary includes identifiers (`id`, `ccf`, `name` — dummy-replaced
  per the official page) and per-vessel angiography fields (attributes
  59–68) that are label components — see document 03.
- **Clinical availability before diagnosis:** mixed and
  prediction-moment-dependent. Demographics/vitals/labs/resting ECG are
  ordinarily pre-angiography; exercise-test fields (`thalach`, `exang`,
  `oldpeak`, `slope`) exist only *after* an exercise test; `thal` exists
  only after thallium scintigraphy; `ca` is obtained **by** the
  fluoroscopy/angiography that defines the label. Rulings in document 03
  (`ca` excluded; `thal` pending) and document 06.
- **Access / licence / redistribution:** Official page states **CC BY 4.0**
  ("sharing and adaptation … for any purpose, provided appropriate credit
  is given"). **[VERIFIED 2026-10-20]** No application or fee. Project
  rule regardless of licence: raw patient-level files are **never
  committed to git** (DATA_POLICY.md); local out-of-git storage only
  (document 04). Licence page must be snapshotted at acquisition —
  a 2026-10-20 reading is not a substitute for the download-day record.
- **Leakage / overlap:** `ca` + per-vessel fields = label leakage
  (document 03, L-01/L-02). Cross-cohort patient overlap cannot be ruled
  out from the listing (identifiers were removed/dummy-replaced) —
  duplicate screening is a Gate DA audit item; rows ≠ proven-independent
  patients until then. Statlog (DS-3) is suspected to recirculate
  Cleveland patients.
- **Suitability (PROPOSED):** **Development + internal validation**
  (Cleveland, Strategy A); **candidate external validation** for a DS-2
  model and vice-versa (Hungary first) **only** under Strategy B after
  the harmonization audit. Era/spectrum limits (1980s referral cohorts)
  prohibit any transfer claim to contemporary, screening, or Egyptian
  outpatient populations.

### DS-2 — UCI Z-Alizadeh Sani (id 412)

- **Official source / identifier:** UCI dataset **412**, DOI
  **10.24432/C5Q31T**; one file, `Z-Alizadeh sani dataset.xlsx` (120.7 KB
  as listed). **[VERIFIED 2026-10-20]**
- **Original publication:** Roohallah Alizadehsani et al., "A data mining
  approach for diagnosis of coronary artery disease," *Comput Methods
  Programs Biomed* 2013;111(1):52–61, DOI 10.1016/j.cmpb.2013.03.004
  (publisher/PubMed record located this session; full text **not** read —
  dataset facts below rest on the official UCI page, not the paper).
  **[VERIFIED as bibliographic record; paper content UNVERIFIED]**
  Relationship: direct dataset of GREEN P5, P9, P15; also used by P4, P14.
- **Purpose / population / label:** Records of 303 patients (Shahid Rajaei
  Hospital, Tehran, per SOURCE-REPORTED literature; the UCI page itself
  says "collected for CAD diagnosis"). Label: **CAD if diameter narrowing
  ≥50%, otherwise Normal** (binary as distributed). Class balance
  216 CAD / 87 Normal is **SOURCE-REPORTED** (literature), to be confirmed
  by audit counts. 54 features in four groups: **demographic; symptom and
  examination; ECG; laboratory and echocardiography**. UCI page: "Has
  Missing Values? No." **[VERIFIED for definition, n, groups, file,
  licence; class counts and the full 54-feature dictionary UNVERIFIED
  until the Gate DA dictionary audit]**
- **Target compatibility with T1:** **Direct**, subject to the `≥50%` vs
  `>50%` (DS-1) threshold-wording difference (document 03, H-01). Binary
  as distributed — no severity gradation is available or approved.
- **Feature dictionary:** The complete 54-feature list with units,
  categorical codings, and per-feature timing **must not be asserted from
  secondary papers**; it is a Gate DA read-only audit deliverable from the
  acquired file + official documentation. Known audit-critical categories
  (from the verified group structure): echocardiography features and any
  symptom/examination, ECG, or treatment-adjacent fields whose recording
  time relative to the angiography decision is undocumented — each needs
  an availability ruling before Gate PT (documents 03, 06). Literature
  sometimes reports "55/56 features" (counting label/extension fields) —
  reconcile at audit; do not pre-assert.
- **Access / licence / redistribution:** **CC BY 4.0** on the official
  page. **[VERIFIED 2026-10-20]** Same project storage/redistribution
  rules as DS-1 (never in git; snapshot licence at acquisition).
- **Leakage / overlap:** Same 303 patients as DS-411 (below) — **never**
  an independent cohort. Any feature recorded during/after angiography,
  or treatment started because of the diagnosis, would be leakage; the
  pre-angiography availability audit is mandatory (Phase 0 §9.2/§R2-5.4).
  Single-centre, single-country referral spectrum: no general-population
  or cross-country claim.
- **Suitability (PROPOSED):** **Primary development + internal validation**
  candidate (Strategy A; richest verified pre-angiography feature groups
  among T1 candidates); external evaluation only via Strategy B against
  DS-1 cohorts after harmonization checks.

### DS-2b — UCI Extension of Z-Alizadeh Sani (id 411)

- **Official source / identifier:** UCI dataset **411**, DOI
  **10.24432/C5461K**; `extention of Z-Alizadeh sani dataset.xlsx`
  (128.1 KB). 303 instances, 59 features (same four groups + LAD/LCX/RCA).
  **[VERIFIED 2026-10-20]**
- **Label / leakage (decisive):** The official page states CAD "happens
  when at least one of these three arteries is stenotic" and instructs
  that only one of LAD/LCX/RCA/Cath may be kept per classification task.
  **[VERIFIED]** Therefore LAD/LCX/RCA (and Cath) **define the label**:
  as T1 predictors they are target leakage (document 03, L-03). Their
  only legitimate scientific use is as *separate per-artery targets*
  (T2), which is itself **UNAPPROVED** (P-1).
- **Suitability (PROPOSED):** **Not a development cohort, never external
  validation for DS-2** (identical patients). Conditional acquisition
  only, for (a) the same-cohort feature-superset audit and (b) a possible
  future T2 protocol — each REQUIRES APPROVAL at Gate DA/PT. Do not count
  its 303 rows toward any sample-size total.

### DS-3 — UCI Statlog (Heart) (id 145)

- **Official source / identifier:** UCI dataset **145**, DOI
  10.24432/C57303; `heart.dat` 16.1 KB; 270 instances, 13 features.
  Official wording: "a heart disease database similar to a database
  already present in the repository (Heart Disease databases) but in a
  slightly different form." Target: absence (1) / presence (2) of heart
  disease. UCI page: "Has Missing Values? No." Features mirror the DS-1
  conventional set (incl. `ca`-equivalent "number of major vessels
  (0-3) colored by flourosopy" [sic] and `thal` 3/6/7). **CC BY 4.0.**
  **[VERIFIED 2026-10-20]**
- **Decisive limitation:** Patient overlap with DS-1 Cleveland is
  **unknown and suspected** (same underlying clinic data recirculated in
  different form). Until an exact + near-duplicate audit on shared
  features is passed, Statlog is a **suspect-duplicate** set: it cannot
  support "external validation," pooled sample-size claims, or
  independent replication. Its `ca`-equivalent field carries the same
  leakage ruling as DS-1.
- **Suitability (PROPOSED):** **Sensitivity analysis only, after** a
  passed overlap audit; otherwise exclude. Named in GREEN P2/P14 only
  via Kaggle copies — re-source from UCI if ever authorized.

## 4. Suitability matrix — separate-target, blocked, and excluded sources

| ID | Source (official identifier) | Target / population | Access & licence [status] | Relation to GREEN evidence | Suitability for T1 (PROPOSED ruling) |
|---|---|---|---|---|---|
| DS-4 | **CDC BRFSS 2015** (official CDC annual data page; 441,456 records, 330 variables in the official combined file) **[VERIFIED 2026-10-20]** | **T3** — self-reported "heart disease or attack"; US telephone-survey adults; complex survey design/weights | CDC public-use files; official page re-verified this session. The Kaggle cleaned copy (253,680 rows, SOURCE-REPORTED) has **UNVERIFIED** licence/provenance — source from CDC only | Named by GREEN P4 (via Kaggle copy) | **Separate T3 task only (Strategy D). Never pooled with, and never external validation for, angiographic T1.** Requires its own Gate DA + protocol if ever pursued |
| DS-5 | **NHANES** (CDC public-use files; `MCQ160c–e` self-reported CHD/angina/MI) | **T3** — sampled US population, survey weights | Public-use free; restricted files via RDC for a fee **[VERIFIED-PH0]**; not re-fetched this session | Not GREEN-derived (Phase 0 Tier-3 option) | Optional separate T3 task only; same prohibitions as DS-4. Not requested in this Gate DA package |
| DS-6 | **Framingham Heart Study (official)** via NHLBI BioLINCC / dbGaP | **T4** — longitudinal incident events (the only listed source that could support a future-event question) | **Controlled:** qualified-investigator research application; phenotype data released via BioLINCC to investigators who have completed an application **[VERIFIED 2026-10-20: FHS data-sharing principles page]**; Phase 0 additionally recorded IRB evidence + DUA requirements **[VERIFIED-PH0]**. $0/timeline/IRB feasibility **UNVERIFIED** for this team | Named (via Kaggle mirrors) by GREEN P4/P7/P14/P15 — that use does **not** transfer access rights | **BLOCKED. Not requested.** A mirror cannot grant rights the controlled source withholds. Any future T4 question needs its own ethics/access approval track; it must not be conflated with T1 |
| DS-6k | **Kaggle "Framingham" mirrors** (~3–4k rows as circulated) | Unknown — provenance, consent basis, label definition undocumented | **UNVERIFIED** | Used by GREEN papers as recorded — recorded use is not provenance | **PROHIBITED — do not acquire** until provenance is documented (Phase 0 D-012 rule). Recorded P4/P7/P14/P15 Framingham numbers are not reusable evidence |
| DS-7 | **Kaggle Cardiovascular Disease (70K)** (P10) | Generic CVD present/absent; original collection undocumented; **not CAD** | Kaggle page terms only; original source/consent/label/redistribution **UNVERIFIED** | GREEN P10 as recorded | **NOT A CANDIDATE** for T1. Do not acquire for this programme |
| DS-8 | **PTB-XL** (PhysioNet, 21,801 ECGs / 18,869 patients, ECG statements) | **T5** — ECG statements, no angiographic CAD label | Open access CC BY 4.0 **[VERIFIED-PH0]**; official page **could not be re-fetched this session (HTTP 500) → UNVERIFIED this session**, re-check required before any reliance | Not GREEN-derived for CAD (Phase 0 Tier-3 exploratory) | Exploratory separate task only; never T1 validation. Not requested in this package |
| DS-9 | **AngioCAD** (Zenodo record 15826856, via RED paper P25) | Artery-level stenosis in 7 grades + clinical data; 413 patients (SOURCE-REPORTED) | Zenodo record/licence **UNVERIFIED** this session (not fetched) | **RED paper** — contributes no evidence; dataset use needs a separate human scope decision (**D-021, REQUIRES APPROVAL**) | **Excluded from this package.** No acquisition, no verification reliance, until D-021 is decided by a human |
| DS-10 | Private/controlled cohorts in the screening record: P3 private Egyptian hospital (n=200, PINK); P11/P12/P13/P18/P22/P24 private cohorts (RED); UK Biobank via P16 (RED, controlled application) | Various; none publicly acquirable | Private / controlled / not public (SOURCE-REPORTED) | No GREEN support (P3 is PINK — promotion REQUIRES APPROVAL, and its data would still need an ethics/data agreement) | **Excluded.** No contact, request, or acquisition is authorized or proposed in this package |
| DS-11 | Kaggle combined copies: P1's merged 5-dataset file (not published by authors); P2/P19 "Statlog-Cleveland-Hungary" copies (n=1,190 as recorded) | Recirculations of DS-1/DS-3 constituents | **UNVERIFIED** provenance per copy | GREEN/ORANGE as recorded | **Not acquisition sources.** Acquire constituents from UCI only; treat every merged copy as duplicate-suspect |

## 5. Cross-cutting findings

1. **Only DS-1 and DS-2 satisfy all three primary-candidate conditions**
   (angiographic T1-compatible label + official public CC BY 4.0 source +
   GREEN support). Everything else fails at least one condition by
   construction, not by ranking preference.
2. **No pair of acquirable datasets is yet proven independent.** DS-2/DS-2b
   are identical patients; DS-3 is suspect-duplicate vs DS-1; DS-1's four
   cohorts are distinct sites but cross-cohort duplicates cannot be ruled
   out from listings. "External validation" is therefore a *conditional,
   audit-gated* claim (Strategy B), never a default.
3. **Matching feature names do not imply harmonized labels, units, or
   populations** (Phase 0 §5.1): DS-1 (13 conventional predictors,
   exercise-test-centred) and DS-2 (54 features across symptoms/ECG/labs/
   echo) share only a small plausibly-common subset; the harmonized
   intersection must be *derived and versioned* at Gate PT, not assumed.
4. **Spectrum/era bias is structural:** 1980s (DS-1) and single-centre
   Iranian referral (DS-2) angiography populations, case-enriched
   prevalence. No result on them supports screening, contemporary, or
   Egyptian-outpatient claims (Phase 0 §5.1, §F-6).
5. **Licence ≠ project permission to redistribute:** CC BY 4.0 (VERIFIED
   for DS-1/DS-2/DS-2b/DS-3) permits reuse with attribution, but
   DATA_POLICY.md still forbids committing patient-level data to git, and
   Gate DA must name the exact datasets before any download.
