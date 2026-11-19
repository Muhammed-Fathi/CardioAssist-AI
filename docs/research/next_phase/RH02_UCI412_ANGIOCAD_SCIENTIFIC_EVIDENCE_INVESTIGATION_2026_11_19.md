# RH-02 Issue #104 — UCI-412 and AngioCAD primary-source scientific evidence investigation

**Document ID:** `CAI-RH02-ISSUE104-UCI412-ANGIOCAD-SCIENTIFIC-EVIDENCE-2026-11-19-v1.1`
**Status:** `REVIEW_DRAFT_NOT_SCIENTIFIC_ADMISSION` — documentation-only public-source investigation. **Not** a source-admission decision, supervisor signature, training authorization, ethics approval or clinical validation.
**Addendum (PR #106 review, same branch):** Independent review identified a second original-author **open full text** that v1 omitted: Alizadehsani et al. 2013 *Res. Cardiovasc. Med.* 2(3):133–139, DOI [10.5812/cardiovascmed.10888](https://doi.org/10.5812/cardiovascmed.10888), PMCID [PMC4253773](https://pmc.ncbi.nlm.nih.gov/articles/PMC4253773/), PMID [25478509](https://pubmed.ncbi.nlm.nih.gov/25478509/). This revision inspects that paper’s Tables 1–2. It does **not** lift holds, choose 54 vs 55, or treat 303 as a verified patient-level join across publications or workbooks.
**Issue:** [Issue #104](https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/104) (Issues API returned `403 Resource not accessible by integration`; the maintainer supplied the specification verbatim in-session).
**Exact `main` baseline named by the issue:** `ab613baa3de5ec7c3442f4047b1a4cc56126d624` (“Merge pull request #105”). This object **is** `HEAD` of the session branch at the start of the investigation (`git rev-parse HEAD`).
**Machine-readable companion:** [`RH02_UCI412_ANGIOCAD_SCIENTIFIC_EVIDENCE_INVESTIGATION_2026_11_19.json`](RH02_UCI412_ANGIOCAD_SCIENTIFIC_EVIDENCE_INVESTIGATION_2026_11_19.json) (schema `cardioassist.rh02_uci412_angiocad_scientific_evidence_investigation/v1`).
**Predecessor audits (not replaced):** [RH-02 first pass](RH02_PRIMARY_SOURCE_ADMISSIBILITY_2026_11_19.md) · [Round 2](RH02_ROUND2_SOURCE_RECONCILIATION_2026_11_19.md) · [16-question register](RH02_SOURCE_QUESTION_REGISTER_2026_11_19.json) · [Issue #99 technical metadata audit](RH02_TECHNICAL_DATASET_METADATA_AUDIT_V1.md) · [AI-8R source admissibility](../ai8r/SOURCE_ADMISSIBILITY.md).

> **What this document is.** An independent public-source scientific investigation of **UCI-412 (Z-Alizadeh Sani)** original-author papers (2012–2017), owner metadata, published feature tables, and **AngioCAD** (2026 article, Zenodo metadata, and publicly readable secondary documentation). Each research question is answered with source URL, author, year, section, authority, what the evidence proves and does not prove, conflicts, and a finding class.
>
> **What this document is not.** It is not permission to download patient files, fit models, change frozen protocols or dictionaries, alter model weights, rewrite supervisor paper colours, or lift a scientific hold.

**Preserved classifications (no change authorized):**

| Classification | Where it lives | This investigation |
|---|---|---|
| AngioCAD literature colour **`REJECTED_RED`** | `research/source_materials/literature_review_status.csv` paper **P25**, Excel row 30, URL `https://doi.org/10.1016/j.cmpb.2026.109368` | **Unchanged.** Supervisor sheet not edited. |
| AngioCAD research status **`SCIENTIFIC_HOLD_NOT_ADMITTED`** | Issue #99 audit §2.7 / JSON `angiocad.classification` | **Unchanged.** Not written into `questions[].status`. |
| UCI-412 **`SCIENTIFIC_HOLD`** on new real fitting / 0/16 owner-verified pre-angiography times | AI-8R; register Q-04 | **Unchanged.** |

---

## 0. Scope, method and what was actually done

### 0.1 Permitted and performed

| Activity | Performed | Detail |
|---|---|---|
| Public landing-page, API and article-preview reads | **Yes** | UCI-412/411 pages and JSON API; Mendeley deposit page; Zenodo record HTML and `/api/records/15826856`; PubMed 23537611 and 42033972; ScienceDirect previews of 2013/2016/2017/2026 papers; CC BY 4.0 deed. |
| Original-author full text | **Yes, two papers** | **(1)** Alizadehsani et al. 2012 *J. Med. Signals Sens.* 2:153–159, DOI [10.4103/2228-7477.112099](https://doi.org/10.4103/2228-7477.112099) — **clinical/ECG** Tables 1–3. **(2)** Alizadehsani et al. 2013 *Res. Cardiovasc. Med.* 2(3):133–139, DOI [10.5812/cardiovascmed.10888](https://doi.org/10.5812/cardiovascmed.10888), [PMC4253773](https://pmc.ncbi.nlm.nih.gov/articles/PMC4253773/) — **demographic Table 1 and laboratory/echocardiography Table 2**. These are two different 2013-era papers; (2) is **not** the paywalled 2013 CMPB article. |
| Original-author abstracts and paywalled snippets | **Yes** | 2013 CMPB (`10.1016/j.cmpb.2013.03.004`), 2016 *Knowl.-Based Syst.*, 2017 Arabasadi/Alizadehsani CMPB. **Table 1 of each of those three papers remains paywalled and was not read.** |
| Secondary open-access feature tables | **Yes** | Eyupoglu & Karakuş 2024 PMC11122190 Table 1; Sayadi et al. 2022 PMC9698583 Table 1; Zhang et al. 2022 *Electronics* 11(9):1495 §3–4.1. |
| Secondary AngioCAD code/README (no patient files) | **Yes** | [MRS028/AngioCAD_Project](https://github.com/MRS028/AngioCAD_Project) README and `src/angiocad_common.py`. Column names are **that repository’s code**, not an owner codebook. |
| Dataset / workbook / video / RAR / XLSX download | **No** | Zero bytes of any patient-level file. UCI `Z-Alizadeh sani dataset.xlsx`, Mendeley `CAD.xlsx`, `AngioCAD_Features.xlsx`, `AngioCAD_Labels.xlsx` and the four RAR parts were **not** retrieved. |
| Model fit, retrain, evaluation, real-data experiment | **No** | None attempted. |
| Changes to frozen protocols, panels, dictionary, models, supervisor CSV, `ai_master_progress.json`, RH-02 register | **No** | Read-only inspection only. Proposed register *text* is in §8 and is **not applied**. |

### 0.2 Authority classes used below

| Class | Meaning |
|---|---|
| `ORIGINAL_AUTHOR_PAPER` | Full text or extract of a paper whose authors include the UCI-412 depositing team (Alizadehsani / Alizadeh Sani). |
| `ORIGINAL_AUTHOR_COAUTHOR_PAPER` | Paper whose authors include Alizadehsani but which is not the 2013 dataset-introduction article (notably Arabasadi et al. 2017). |
| `OWNER_METADATA` | UCI, Mendeley or Zenodo owner/depositor landing page or machine-readable record. |
| `OWNER_PAPER_ABSTRACT` | Abstract, Highlights, Introduction, ethics/data-availability of an owner-authored article, where the methods/tables are paywalled. |
| `SECONDARY_PAPER` | Peer-reviewed third-party reanalysis. Can corroborate or conflict; **cannot** authenticate original acquisition. |
| `SECONDARY_REANALYSIS_CODE` | Public source code of a third-party reanalysis that claims to have opened the files. Not owner documentation. |
| `HISTORICAL_LOCAL_AGGREGATE` | Previously recorded maintainer-executed read-only observation already in this repository; not re-derived here. |
| `REPOSITORY_CONTRACT` | Frozen versioned artifact inspected read-only. |
| `LICENSE_REFERENCE` | Canonical Creative Commons deed text. Not legal advice. |
| `SUPERVISOR_CLASSIFICATION` | The 25-paper supervisor colour in `literature_review_status.csv`. |

Finding classes: **`SUPPORTED`**, **`PARTIALLY_SUPPORTED`**, **`UNRESOLVED`**, **`DISPUTED`**. None of these is a register-status change and none is a GO.

---

## 1. Access log (2026-11-19)

| ID | URL | Observed | What could actually be read |
|---|---|---|---|
| `OA-2012-JMSS` | [Semantic Scholar PDF of Alizadehsani et al. 2012 JMSS](https://pdfs.semanticscholar.org/c126/774693609b7c63a8477a595d6e4850c58bc1.pdf) · DOI [10.4103/2228-7477.112099](https://doi.org/10.4103/2228-7477.112099) | Full text, 4 chunks | Abstract; §2 dataset; Tables 1–3 (demographic, symptom/examination, ECG); class definition; collection site/season; §5 “37 features”; future-work statement that lab/echo were **not yet** included. |
| `OA-2012-EJSR` | [ResearchGate record of Alizadehsani et al. 2012 *Eur. J. Sci. Res.* 82(4):542–553](https://www.researchgate.net/publication/265158683_Diagnosis_of_Coronary_Artery_Disease_Using_Data_Mining_Techniques_Based_on_Symptoms_and_ECG_Features) | Extract / tables only | Table 2 BP 90–190, PR 50–110; Table 4 derived `BP2`/`PR2` cut-offs. **Full PDF not independently archived in this session.** |
| `OA-2013-RCM` | [PMC4253773](https://pmc.ncbi.nlm.nih.gov/articles/PMC4253773/) · [PubMed 25478509](https://pubmed.ncbi.nlm.nih.gov/25478509/) · DOI [10.5812/cardiovascmed.10888](https://doi.org/10.5812/cardiovascmed.10888) · tables [tbl11452](https://pmc.ncbi.nlm.nih.gov/articles/PMC4253773/table/tbl11452/) / [tbl11453](https://pmc.ncbi.nlm.nih.gov/articles/PMC4253773/table/tbl11453/) | Full PMC HTML (PDF fetch HTTP 500) | **Different 2013 paper from CMPB.** Abstract; §3 Patients and Methods; **Table 1 demographic** (16 named fields + Yes/No subgroup counts; Length omitted); **Table 2 laboratory and echo** (17 named fields + ranges); Gini Tables 4–6 use **Length** anyway; no 50% threshold restated; no per-feature timestamps. |
| `OA-2013-CMPB` | [ScienceDirect preview, *Comput. Methods Programs Biomed.* 111:52–61](https://www.sciencedirect.com/science/article/pii/S0169260713000801) · [PubMed 23537611](https://pubmed.ncbi.nlm.nih.gov/23537611/) · DOI 10.1016/j.cmpb.2013.03.004 | Abstract + snippets; Table 1 **paywalled** | 303 patients / 54 features; 216 CAD; four feature groups; feature-creation method; 94.08% accuracy claim. **Not the same article as `OA-2013-RCM`.** |
| `OA-2016-KBS` | [ScienceDirect preview, *Knowl.-Based Syst.* 109:187–197](https://www.sciencedirect.com/science/article/abs/pii/S0950705116302076) · DOI 10.1016/j.knosys.2016.07.004 | Abstract + snippets; Table 1 **paywalled** | 303 patients / 54 features; “stenotic more than 50%”; Table 1 exists but was not readable. |
| `OA-2017-ARAB` | [ScienceDirect preview, Arabasadi/Alizadehsani *Comput. Methods Programs Biomed.* 141:19–26](https://www.sciencedirect.com/science/article/pii/S0169260716309695) · DOI 10.1016/j.cmpb.2017.01.004 | Abstract + snippets; Table 1 **paywalled** | 303 patients / 54 features / 216 CAD; “stenosis of higher than 50%”. |
| `P1A` | [UCI-412](https://archive.ics.uci.edu/dataset/412/z+alizadeh+sani) | `200` | 303; ≥50% CAD; 54-feature prose; 56 blank variable rows; `Z-Alizadeh sani dataset.xlsx` 120.7 KB; CC BY 4.0; donated 2017-11-16. |
| `P1B` | [UCI-412 API](https://archive.ics.uci.edu/api/dataset?id=412) | `200` JSON | `num_instances: 303`, **`num_features: 0`**, `target_col: null`, 56 blank variable objects, `year_of_dataset_creation: 2013`. |
| `P1C` | [UCI-411](https://archive.ics.uci.edu/dataset/411/extention+of+z+alizadeh+sani+dataset) | `200` | Same 303; **59 features** prose; LAD/LCX/RCA added; 59 blank variable rows; `extention of Z-Alizadeh sani dataset.xlsx` 128.1 KB. |
| `P1D` | [Mendeley `vrymwyh2tg/1`](https://data.mendeley.com/datasets/vrymwyh2tg/1) | `200` | 303 / 54 / ≥50%; CC BY 4.0; `CAD.xlsx` 118 KB; published 23 Jan 2017. |
| `S-EYU` | [Eyupoglu & Karakuş 2024 PMC11122190](https://pmc.ncbi.nlm.nih.gov/articles/PMC11122190/) | Full HTML | §2.1 and **Table 1**: 303 records, 216 CAD / 87 normal, **55 attributes** with names, groups, ranges, BP mmHg, PR ppm, Yes/No binaries. |
| `S-SAY` | [Sayadi et al. 2022 PMC9698583](https://pmc.ncbi.nlm.nih.gov/articles/PMC9698583/) | Full HTML | §2 and Table 1: 54 features stated in prose; table still lists BP mmHg and PR ppm. |
| `S-ZHA` | [Zhang et al. 2022 *Electronics* 11(9):1495](https://www.mdpi.com/2079-9292/11/9/1495) | HTML §3–4.1 | 303 records, 55 features, 216/87; Exertional CP “same values on 303 samples”; then dropped as “External CP”. |
| `S-JOL` | [Joloudari et al. 2020 *Int. J. Environ. Res. Public Health* 17(3):731](https://www.mdpi.com/1660-4601/17/3/731) / [arXiv:2001.09841](https://arxiv.org/pdf/2001.09841) | Partial | Previously recorded 216 CAD + 88 normal (=304) vs stated 303; 55 features. Not used to overwrite 216/87. |
| `X-TAO` | [Tao et al. 2025 *Rev. Cardiovasc. Med.* 26(3):26204](https://www.imrpress.com/journal/RCM/26/3/10.31083/RCM26204) | Front matter only | **Table 1 not retrieved.** S-9 0=false/1=true direction is **not** re-verified here. |
| `P3A` | [Zenodo record 15826856](https://zenodo.org/records/15826856) and [API](https://zenodo.org/api/records/15826856) | `200` | Description, 413 patients, file manifest, `license.id: cc-by-4.0`, `access_right: open`. No schema file. |
| `P3B` | [PubMed 42033972](https://pubmed.ncbi.nlm.nih.gov/42033972/) | Abstract | 413 patients; video + structured clinical/lab; artery-level stenosis examples. |
| `P3C` | [ScienceDirect S0169260726001331](https://www.sciencedirect.com/science/article/pii/S0169260726001331) | Preview | Highlights 413 **videos**; abstract 413 **patients**; “non-commercial”; ethics retrospective Shahid Chamran; Data availability Zenodo DOI. Sections 3–5 **paywalled**. |
| `S-MRS` | [github.com/MRS028/AngioCAD_Project](https://github.com/MRS028/AngioCAD_Project) | README + `angiocad_common.py` | Secondary 377-patient clinical cohort, 39 inputs, 15 segment columns, constructed `has_cad`. **Not owner.** No licence file. |
| `LIC1` | [CC BY 4.0 deed](https://creativecommons.org/licenses/by/4.0/deed.en) | `200` | Share/adapt “for any purpose, even commercially”; **no** non-commercial restriction. |
| `N104` | `https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/104` | API `403` | Issue body not machine-readable. Specification used is the in-session maintainer text. |

---

## 2. UCI-412 — original-author corpus (2012, 2013, 2016, 2017)

The issue asked for 2013, 2016 and 2017 original-author publications. Those exist. The **first original collection paper remains 2012 JMSS** (clinical/ECG Tables 1–3, 37-feature precursor, BP/PR wording). A **second original-author full text**, 2013 *Res. Cardiovasc. Med.* (DOI 10.5812/cardiovascmed.10888, **not** the paywalled 2013 CMPB article), supplies **demographic Table 1 and laboratory/echocardiography Table 2**. v1’s claim that only the 2012 full text was accessible is **incorrect** and is corrected here. Treating CMPB 2013 as the first paper would still hide the 37-feature precursor and the BP/PR original wording.

### 2.1 What each original-author source actually establishes

| Year | Paper | Authority | Establishes | Does **not** establish |
|---|---|---|---|---|
| **2012** | Alizadehsani R, Habibi J, Bahadorian B, Mashayekhi H, Ghandeharioun A, Boghrati R, Alizadeh Sani Z. *Diagnosis of coronary arteries stenosis using data mining.* **J. Med. Signals Sens.** 2(3):153–159. DOI 10.4103/2228-7477.112099. §2, Tables 1–3, §5. | `ORIGINAL_AUTHOR_PAPER` (full text) | 303 random visitors to Shaheed Rajaei, Tehran, **autumn 2011–winter 2012**; “visitors with chest pain … suspicious of having CAD and were volunteers for angiography”; class `Cath` = `Cad` if diameter narrowing **“greater or equal to 50”**, else `Normal`; **named** demographic / symptom / ECG features with Yes/No or numeric ranges; **explicit history definitions** for HTN, DM, Current Smoker, Ex-Smoker, FH; BP labelled “Blood Pressure” range 90–190; PR labelled “Pulse Rate” range 50–110; four chest-pain flags listed as separate Yes/No columns; **37 features examined**; future work: “add other features like Lab data and Echo data”. | Units of BP/PR; systolic vs diastolic; posture/device; per-field clock time vs angiography; 0/1 workbook coding (tables are Yes/No); mutual exclusivity of chest-pain flags; lab/echo codebook; delivered UCI column count. |
| **2012** | Alizadehsani et al. *Diagnosis of coronary artery disease using data mining techniques based on symptoms and ECG features.* **Eur. J. Sci. Res.** 82(4):542–553. Tables 2 and 4 (ResearchGate extract). | `ORIGINAL_AUTHOR_PAPER` (extract only) | Same BP 90–190 and PR 50–110; derived **`BP2`**: BP&lt;90 / 90≤BP≤140 / BP&gt;140; derived **`PR2`**: PR&lt;60 / 60≤PR≤100 / PR&gt;100. | Full article not independently archived here; still no measurement protocol or pre-cath timestamp. |
| **2013** | Alizadehsani R, Habibi J, Alizadeh Sani Z, Mashayekhi H, Boghrati R, Ghandeharioun A, Khozeimeh F, Alizadeh-Sani F. *Diagnosing Coronary Artery Disease via Data Mining Algorithms by Considering Laboratory and Echocardiography Features.* **Res. Cardiovasc. Med.** 2(3):133–139. DOI 10.5812/cardiovascmed.10888. PMID 25478509. PMC4253773. Abstract; §3; Tables 1–2; Gini Tables 4–6; §5. | `ORIGINAL_AUTHOR_PAPER` (full PMC HTML) | 303 random chest-pain referrals to Rajaie, Tehran; ECG “studied in our previous works” (cites 2012 JMSS/EJSR); this paper uses **laboratory and echocardiographic** data for **per-artery** LAD/LCX/RCA stenosis; Table 1 **16 named demographics** with Yes/No counts (Length omitted from the table); Table 2 **17 named lab/echo fields** with numeric ranges (except Region RWMA range blank; VHD ordinal Normal/Mild/Moderate/Severe); Obesity **Yes if BMI > 25**; Gini tables use **Length** anyway; future work: add ECG and examination. Open-access CC BY. | **Not** a 54-feature codebook (this paper never states “54 features”); **not** a patient-ID join to 2012, CMPB 2013, or UCI/Mendeley workbooks (same *n* and centre is not identity); **no** 50% stenosis threshold restated; **no** BP/PR/chest-pain tables; **no** lab units except EF(%); **no** per-feature pre-angiography timestamps; Cr footnote prints “Creatine”. |
| **2013** | Alizadehsani et al. *A data mining approach for diagnosis of coronary artery disease.* **Comput. Methods Programs Biomed.** 111(1):52–61. DOI 10.1016/j.cmpb.2013.03.004. PMID 23537611. Abstract + “The medical dataset” snippet. **Different article from the RCM paper above.** | `OWNER_PAPER_ABSTRACT` / `ORIGINAL_AUTHOR_PAPER` (Table 1 unread) | Introduces the named **Z-Alizadeh Sani** dataset: **303 patients, 54 features**, four groups (demographic, symptom and examination, ECG, laboratory and echo); 216 CAD; feature-creation method adding **three derived** features; Typical Chest Pain, Region RWMA2 and age called most effective. | Table 1 (names/units/ranges) **not read**; collection form; timestamps; 0/1 direction; 54-vs-delivered-file reconciliation; identity of these 303 with RCM/JMSS/UCI rows. |
| **2016** | Alizadehsani et al. *Coronary artery disease detection using computational intelligence methods.* **Knowl.-Based Syst.** 109:187–197. DOI 10.1016/j.knosys.2016.07.004. Abstract + “Medical dataset used” snippet. | `ORIGINAL_AUTHOR_PAPER` (Table 1 unread) | “random sample of 303 patients with 54 features”; “features … presented in Table 1”; “medical histories, physical examinations, laboratory data, ECGs, and echocardiograms”; CAD if at least one of LAD/LCX/RCA is **“stenotic more than 50%”**. | Table 1 unread; **wording conflict** with 2012/UCI ≥50% (§2.3); timestamps. |
| **2017** | Arabasadi Z, **Alizadehsani R**, Roshanzamir M, Moosaei H, Yarifard AA. *Computer aided decision making for heart disease detection using hybrid neural network-Genetic algorithm.* **Comput. Methods Programs Biomed.** 141:19–26. DOI 10.1016/j.cmpb.2017.01.004. Abstract + Dataset snippet. | `ORIGINAL_AUTHOR_COAUTHOR_PAPER` (Table 1 unread) | 303 patients, 216 CAD, **54 features**; Table 1 exists; CAD if at least one of LAD/LCX/RCA has **“stenosis of higher than 50%”**. | Table 1 unread; not a codebook for the UCI workbook; **same &gt;50% wording conflict**. |
| **2017** | UCI-412 donation 16 Nov 2017; Mendeley 23 Jan 2017. | `OWNER_METADATA` | Official ≥50% threshold; 303; 54-feature prose; CC BY 4.0; two different files (120.7 KB vs 118 KB). | Field names (API `num_features: 0`, 56 blank rows); units; timing. |

No original **case-record form**, **CRF**, **supplementary codebook**, or **owner-signed acquisition protocol** was found in any public repository searched. Published “feature dictionaries” in later papers are **reprinted tables**, not collection forms.

### 2.2 Original 2012 feature tables (verbatim structure)

**Table 1 — Demographic** (`OA-2012-JMSS` §2): Age 30–86; Weight 48–120; Sex Male/Female; BMI 18–41 Kg/m²; DM Yes/No; HTN Yes/No; Current Smoker Yes/No; Ex-Smoker Yes/No; FH Yes/No; Obesity “Yes if MBI&gt;25, No otherwise”; CRF, CVA, Airway Disease, Thyroid Disease, CHF, DLP all Yes/No. **Length is not listed** in Table 1, but **appears in the information-gain tables** (§4.2). That is an original-author internal omission, not a secondary artefact.

**Table 2 — Symptom and examination:** BP (Blood Pressure) 90–190; PR (Pulse Rate) 50–110; Edema; Weak Peripheral Pulse; Lung rales; Systolic murmur; Diastolic murmur; Typical Chest Pain; Dyspnea; Function Class 1, 2, 3, 4; Atypical; Nonanginal CP; Exertional CP; LowTh Ang — all flags Yes/No except BP, PR, Function Class.

**Table 3 — ECG:** Rhythm Sin/AF; Q Wave; ST Elevation; ST Depression; Tinversion; LVH; Poor R Progression. **`BBB` is not in this 2012 ECG table.** The frozen local 55-predictor layout registers `BBB` and not `Rhythm` (`research/audit/registry.py`).

**Author definitions immediately under the tables (`OA-2012-JMSS` §2):**

> “HTN identifies history of Hypertension, DM is history of Diabetes Mellitus, Current Smoker is current consumption of cigarettes, Ex-Smoker is history of previous consumption of cigarettes and FH is history of heart disease in first-degree relatives.”

This is the strongest original-author **semantic** evidence located for five of the six numeric-binary panel fields. It still does not define the sixth (`Typical Chest Pain`) beyond the column name, and it does not map Yes/No onto workbook `0`/`1`.

**§5 conclusion:** “The effects of **37 features** were examined.” Arithmetic of Tables 1–3: 16 + 14 + 7 = 37. Future work: add lab and echo. The 2013 CMPB abstract’s **54-feature, four-group** description is **arithmetically compatible** with adding the 2013 RCM Table 2 laboratory/echo panel (17 named fields) to that 37-feature core. That reconstruction is a **hypothesis, not adopted** (§3.2). Same published *n* = 303 and overlapping authors/centre **do not prove** that the 2012, 2013 RCM, 2013 CMPB, and UCI/Mendeley rows are the same patients.

### 2.3 Original-author CAD threshold conflict (`DISPUTED` wording, UCI ≥50% still the owner landing-page rule)

| Statement | Source | Wording |
|---|---|---|
| Cad if diameter narrowing **greater or equal to 50** | 2012 JMSS §2 | ≥50 |
| CAD if diameter narrowing **greater than or equal to 50%** | UCI-412 Additional Information; Mendeley 2017 | ≥50 |
| CAD if at least one of LAD/LCX/RCA **stenotic more than 50%** | 2016 KBS Introduction | &gt;50 |
| CAD if at least one artery has **stenosis of higher than 50%** | 2017 Arabasadi/Alizadehsani Dataset snippet | &gt;50 |

**Finding:** `DISPUTED` for the exact-50% edge **inside original-author literature**; `SUPPORTED` that the **UCI-412 owner landing page** states ≥50%. Exact handling of a 50% lesion in the delivered 303 rows remains `UNRESOLVED`. Do **not** pool with UCI-45 `>50%` and do **not** silently pick one paper to “fix” the owner page. The 2013 RCM full text **does not restate** a 50% (or any percent) stenosis cut-off in the accessible HTML.

### 2.4 Original 2013 RCM demographic and laboratory/echo tables (`OA-2013-RCM`)

**Authority:** `ORIGINAL_AUTHOR_PAPER`, full PMC HTML of Alizadehsani et al. 2013 *Res. Cardiovasc. Med.* 2:133–139. Distinct from paywalled 2013 CMPB.

**§3 Patients and Methods (verbatim design, not a codebook):** “The dataset of the current study was gathered from 303 random individuals, who referred to Rajaie Cardiovascular, Medical and Research Center, Tehran, Iran, due to chest pain.” “Electrocardiographic (ECG) data were studied in our previous works.” Goal: “accuracy of echocardiographic and laboratory features to predict CAD patients that require angiography.” Abstract Objectives: among chest-pain referrals “a great number … are normal”; method would “select high-risk cases that definitely need angiography.” **Not** a substitute for angiography.

**Table 1 — Demographic Features** (16 named rows; **Length is not listed**, same omission as 2012 Table 1):

| Feature | Descriptive index | Range / coding |
|---|---|---|
| Age, year | 58.898 ± 10.392 | 30–86 |
| Weight, Kg | 73.832 ± 11.987 | 48–120 |
| Sex | Male 176 (58.1%); Female 127 (41.9%) | Male/Female |
| BMI, Kg/m² | 27.248 ± 4.099 | 18–41 |
| DM | Yes 90 (29.7%); No 213 (70.3%) | Yes/No |
| HTN | Yes 179 (59.1%); No 124 (40.9%) | Yes/No |
| Current Smoker | Yes 63 (20.8%); No 240 (79.2%) | Yes/No |
| Ex-Smoker | Yes 10 (3.3%); No 293 (96.7%) | Yes/No |
| FH | Yes 48 (15.8%); No 255 (84.2%) | Yes/No |
| Obesity | Yes if BMI > 25: 211 (69.6%); No otherwise 92 (30.4%) | derived |
| CRF | Yes 6 (2%); No 297 (98%) | Yes/No |
| CVA | Yes 5 (1.7%); No 298 (98.3%) | Yes/No |
| Airway Disease | Yes 11 (3.6%); No 292 (96.4%) | Yes/No |
| Thyroid Disease | Yes 7 (2.3%); No 296 (97.7%) | Yes/No |
| CHF | Yes 1 (0.3%); No 302 (99.7%) | Yes/No |
| DLP | Yes 191 (63%); No 112 (37%) | Yes/No |

**Table 2 — Laboratory and Echo Features** (17 named rows). Footnote b expands names; Cr/CR is glossed “C, Creatine” (not “creatinine”). **No printed units except EF(%).** Region with RWMA has a mean but **blank range**. VHD is severity (Normal/Mild/Moderate/Severe), “not on the basis of which valve was diseased”; “patients with known or predominant valvular heart disease were excluded.”

| Feature (paper token) | Mean ± SD | Paper range | Frozen-dict token (read-only compare) | Frozen-dict secondary range (not owner) |
|---|---|---|---|---|
| FBS | 119.185 ± 52.08 | 62–400 | FBS | 70–400 |
| Cr | 1.056 ± 0.264 | 0.5–2.2 | CR | 0.5–2.5 |
| TG | 150.343 ± 97.959 | **37–1050** | TG | 50–400 |
| LDL | 104.644 ± 35.397 | 18–232 | LDL | 40–250 |
| HDL | 40.234 ± 10.559 | 15–111 | HDL | 20–90 |
| BUN | 17.502 ± 6.957 | 6–52 | BUN | 5–60 |
| ESR | 19.462 ± 15.936 | **1–90** | ESR | 0–60 |
| HB | 13.153 ± 1.61 | 8.9–17.6 | HB | 8–19 |
| K | 4.231 ± 0.458 | **3.0–6.6** | K | 3.0–6.0 |
| Na | 140.997 ± 3.808 | 128–156 | Na | 125–155 |
| WBC | 7562.046 ± 2413.739 | **3700–18000** | WBC | 2000–15000 |
| Lymph | 32.399 ± 9.973 | 7–60 | Lymph | 10–50 |
| Neut | 60.149 ± 10.182 | 32–89 | Neut | 30–85 |
| PLT | 221.488 ± 60.796 | **25–742** | PLT | 100–450 |
| EF(%) | 50.788 ± 8.652 | 15–60 | EF-TTE | 20–70 |
| Region with RWMA | 0.620 ± 1.133 | *(blank)* | Region RWMA | 0–3 |
| VHD | Normal 116 / Mild 149 / Moderate 27 / Severe 11 | ordinal | VHD | N/Mild/Moderate/Severe |

**Name correspondence with the frozen 17 laboratory-and-echo group is 17/17** at token level (Cr↔CR, EF(%)↔EF-TTE, Region with RWMA↔Region RWMA). That is **not** a workbook header audit and **not** a licence to treat frozen secondary units (`mg/dL`, `mm/hr`, …) as original-author units.

**Gini Tables 4–6** rank **Length** for LAD, LCX and RCA even though Length is absent from Table 1 — the same original-author internal omission as 2012 IG tables.

**§5 future work:** “diagnostic accuracy may be further augmented by adding new features such as the ECG and examination features.” This paper is therefore the **lab/echo counterpart** of 2012’s clinical/ECG paper, not a statement that a 54- or 55-column file exists.

**What this paper does not supply:** BP, PR, chest-pain flags, Function Class, ECG/`BBB`/`Rhythm`, 0/1 workbook coding, lab units, a 50% CAD rule, a CRF, per-feature clocks, or proof that these 303 rows are the UCI-412 workbook.

---

## 3. The 54-versus-55-versus-56 discrepancy (Q-08)

### 3.1 Counts on the record

| Count | Source | Class |
|---|---|---|
| **37 features** | 2012 JMSS §5 | `ORIGINAL_AUTHOR_PAPER` |
| **16 named demographics + 17 named lab/echo (this paper does not state 54)** | 2013 RCM Tables 1–2; Length used only in Gini | `ORIGINAL_AUTHOR_PAPER` |
| **54 features** | 2013 **CMPB** abstract; 2016 snippet; 2017 co-author snippet; UCI-412 prose; Mendeley | `ORIGINAL_AUTHOR_PAPER` / `OWNER_METADATA` |
| **55 attributes / 55 features** | Eyupoglu 2024 Table 1 (17+14+7+17); Zhang 2022 §3; Joloudari 2020 | `SECONDARY_PAPER` |
| **56 variable rows** | UCI-412 page “0 to 10 of 56”; API `variables` length 56 | `OWNER_METADATA` (names blank) |
| **`num_features: 0`** | UCI-412 API | `OWNER_METADATA` |
| **55 predictors + `Cath` = 56 columns, `BBB` present** | `research/uci412/source_spec.py`; local 2026-10-22 audit | `HISTORICAL_LOCAL_AGGREGATE` |
| **59 features** | UCI-411 prose and 59 blank rows; three arteries added | `OWNER_METADATA` |

### 3.2 Reconstructable arithmetic (hypotheses, **not adopted**)

1. **2012 clinical/ECG + 2013 RCM lab/echo → CMPB “54” (hypothesis, not adopted).** 2012 JMSS §5 **37** (Tables 1–3: 16 demo without Length + 14 symptom/exam + 7 ECG including **Rhythm** not `BBB`) **+** 2013 RCM Table 2 **17** laboratory-and-echo names **= 54**. This is now an **original-author-table** reconstruction (no longer dependent on Eyupoglu for the 17 lab/echo names). It still **fails** if Length is counted (both 2012 IG and 2013 Gini use Length while omitting it from Table 1). It still **does not identify** the UCI workbook columns. It still **does not prove** the 303 rows are the same people.
2. **Delivered 55 predictors.** 17 demographic **including Length** + 14 symptom + 7 ECG **including `BBB` not `Rhythm`** + 17 lab/echo = **55**. Plus `Cath` = **56**. Then 56 + LAD + LCX + RCA = **59**, which is exactly UCI-411’s owner statement. **`54 + 3 ≠ 59`; `56 + 3 = 59`.**
3. **Two owner files are not identical artefacts:** UCI `Z-Alizadeh sani dataset.xlsx` 120.7 KB vs Mendeley `CAD.xlsx` 118 KB.

**Additional original-vs-secondary table conflicts (not resolved):**

| Item | 2012 JMSS | 2013 RCM | Secondary 55-row (Eyupoglu 2024) / frozen dict |
|---|---|---|---|
| Length | omitted from Table 1; used in IG | omitted from Table 1; used in Gini | listed, 140–188 |
| Lab/echo panel | future work | **17 named fields**, Table 2 | 17 fields; several **range** mismatches vs RCM (TG, ESR, K, WBC, PLT, EF) |
| ECG | **Rhythm** Sin/AF | not in this paper (previous work) | **BBB** Left/Right/Normal; Rhythm absent |
| Function Class | 1, 2, 3, 4 | not in this paper | 0, 1, 2, 3 |
| Obesity | derived, BMI&gt;25 | derived, BMI &gt; 25, with counts | Yes/No |
| Lab units | n/a | **none** except EF(%) | mmHg/ppm and mg/dL etc. are **secondary** |

**Finding:** `UNRESOLVED` / `DISPUTED` across source versions. **Neither 54 nor 55 nor 56 is chosen.** The frozen dictionary remains 56 registered entries. Original-author 2013 RCM Table 2 **supports the 17-name laboratory/echo inventory** as an author-published list; it does **not** certify the delivered column count. Choosing a secondary table — or this RCM paper — to “correct” the owner prose is prohibited.

**Cheapest decisive evidence (not performed):** authorized read-only header/shape comparison of the UCI and Mendeley workbooks, emitting column names and counts only.

---

## 4. The registered 16 predictors — original-author vs remaining gaps

Registered panel `uci412_basic_clinical_v1` (`REPOSITORY_CONTRACT`, dictionary 1.1.0). **No field is owner-verified pre-angiography.** A 2012/2013 Yes/No table is not the 2017 workbook encoding. 2013 RCM Table 1 adds **original-author subgroup counts** for the demographic subset; it does **not** cover BP, PR, or chest-pain flags.

| # | Field | Original-author evidence (`OA-2012-JMSS` unless noted) | What it proves | What it does not prove | Finding |
|---|---|---|---|---|---|
| 1 | Age | Numeric 30–86; 2013 RCM 58.898 ± 10.392, same range | Age was a collected demographic in both 2012 and 2013 RCM tables | Age-at-which-date; pre-cath clock; row identity across papers | `PARTIALLY_SUPPORTED` (meaning); timing `UNRESOLVED` |
| 2 | Sex | Male, Female; 2013 RCM Male 176 / Female 127 | Binary sex recorded | `Fmale` token; timestamp; identity of those 303 | `PARTIALLY_SUPPORTED`; token `UNRESOLVED` |
| 3 | BMI | 18–41 Kg/m²; Obesity derived if BMI&gt;25 (2012 and 2013 RCM, latter with 211/92 counts) | Unit kg/m² in original-author tables | Direct vs derived in the workbook; timing | `PARTIALLY_SUPPORTED` |
| 4 | DM | Yes/No; **“history of Diabetes Mellitus”**; 2013 RCM Yes 90 / No 213 | History flag, not a glucose cut-off in 2012 prose | 0/1 direction in the xlsx; diagnostic criteria; timing | `PARTIALLY_SUPPORTED` (history semantics); S-9 `UNRESOLVED` |
| 5 | HTN | Yes/No; **“history of Hypertension”**; 2013 RCM Yes 179 / No 124 | History flag, not the BP column | Whether history equals treated HTN; 0/1; timing | `PARTIALLY_SUPPORTED`; S-9 `UNRESOLVED` |
| 6 | Current Smoker | Yes/No; **“current consumption of cigarettes”**; 2013 RCM Yes 63 / No 240 | Current smoking history | Window (days/years); 0/1; timing | `PARTIALLY_SUPPORTED`; S-9 `UNRESOLVED` |
| 7 | EX-Smoker | Yes/No; **“history of previous consumption of cigarettes”**; 2013 RCM Yes 10 / No 293 | Former-smoking history, distinct from current | Exclusive vs overlapping with Current Smoker; 0/1 | `PARTIALLY_SUPPORTED`; S-9 `UNRESOLVED` |
| 8 | FH | Yes/No; **“history of heart disease in first-degree relatives”**; 2013 RCM Yes 48 / No 255 | First-degree family history | Age-of-onset threshold; 0/1; timing | `PARTIALLY_SUPPORTED`; S-9 `UNRESOLVED` |
| 9 | DLP | Yes/No “Dyslipidemia”; 2013 RCM Yes 191 / No 112 | Named history/diagnosis flag | Lab-derived vs recorded diagnosis; Y/N vs Yes/No tokens | `PARTIALLY_SUPPORTED` |
| 10 | BP | “Blood Pressure” 90–190; EJSR `BP2` uses **140** as high cut-off. **Absent from 2013 RCM Tables 1–2** (examination features are future work). | Single numeric; 140-cut-off is the classic **systolic** threshold, so a systolic-like quantity is **the intended reading of the derived feature** | Systolic vs diastolic vs MAP as recorded; mmHg (2012 table has **no unit**); posture, device, rest; pre-cath time. Must not be mapped to Cleveland `trestbps`. 2013 RCM does **not** add a BP subtype. | `PARTIALLY_SUPPORTED` (pulse-pressure-like single value, systolic-compatible cut-off); quantity/unit/timing `UNRESOLVED` |
| 11 | PR | “Pulse Rate” 50–110; EJSR `PR2` uses 60–100 as normal. **Absent from 2013 RCM Tables 1–2.** | Named pulse rate; 60–100 is the classic **beats/min** adult range | Printed secondary unit `ppm`; device; conditions; timing. 2013 RCM does **not** document `ppm`. | `PARTIALLY_SUPPORTED` (pulse rate, bpm-compatible); unit/timing `UNRESOLVED` |
| 12 | Typical Chest Pain | Separate Yes/No column; highest IG for LAD/RCA | A typical-pain flag existed | Case definition; 0/1; exclusivity vs other flags; timing | `UNRESOLVED` |
| 13 | Atypical | Separate Yes/No | Distinct column | Exclusive vs overlapping; timing | `UNRESOLVED` |
| 14 | Nonanginal | Separate Yes/No (“Nonanginal CP”) | Distinct column | Exclusive vs overlapping; timing | `UNRESOLVED` |
| 15 | Exertional CP | Separate Yes/No | Distinct column in 2012 | Constancy (secondary only); exclusivity; timing | `UNRESOLVED` |
| 16 | Dyspnea | Separate Yes/No | Distinct symptom flag | Case definition; timing | `PARTIALLY_SUPPORTED` (named); timing `UNRESOLVED` |

**0/16 owner-verified pre-angiography timestamps is preserved.**

---

## 5. Pre-angiography / pre-knowledge-of-outcome timing (Q-04)

**Evidence that looks like pretest intent (`OA-2012-JMSS` §2):**

- Cohort = chest-pain **visitors**, “suspicious of having CAD”, “**volunteers for angiography**”.
- Aim: diagnose vessel stenosis “when there is not enough ECG changes and **only based on** Demographic, Symptom, Examination information and ECG Features”.
- Class `Cath` “is determined by angiography” — i.e. the label is the invasive test.

**2013 RCM (`OA-2013-RCM` Abstract / §3 / §5) — related modelling intent, still no clocks:**

- 303 random chest-pain referrals to Rajaie; features “measured and collected from potential patients.”
- Objective: predict patients “most probably normal” to “obviate angiography costs and complications”; “Not a substitute for angiography.”
- Echo (EF, Region with RWMA) and laboratories are the **inputs of this paper**. Same-admission echo/labs around angiography remain compatible with every sentence.
- **No sentence states** that any named field was recorded before angiography or before knowledge of the stenosis label.
- Same published *n* = 303 is **not** a verified patient-level overlap with 2012 JMSS or the UCI workbook.

**What this proves:** the **study design** was to use non-invasive fields as an alternative to angiography in an angiography-referred sample. That is original-author *intent*.

**What this does not prove:** that each of the 16 registered values was **measured or abstracted before the angiogram was performed**, or **before the abstractor knew `Cath`**. Retrospective chart abstraction after cath is compatible with every public sentence. ECG, later echo (EF, RWMA) and laboratories in the 54-feature set are commonly obtained on the same admission as angiography. **0/16 is not elevated.**

**Secondary papers** that call the features “noninvasive clinical parameters” (Sayadi 2022) repeat the modelling *use*, not a collection log.

**Finding:** `PARTIALLY_SUPPORTED` for **cohort-level referral-for-angiography design**; `UNRESOLVED` for **per-field pre-index timing**. Scientific hold on new real pretest modelling **continues**. Plausibility is not evidence.

---

## 6. Binary direction, chest pain, BP/PR — condensed findings

### 6.1 Six numeric 0/1 fields (Q-06)

- **2012 original tables:** Yes/No, with history definitions (§2.2). **2013 RCM Table 1:** same Yes/No tokens plus subgroup counts for DM, HTN, Current Smoker, Ex-Smoker, FH, DLP; still not 0/1.
- **Local 2026-10-24 audit (`HISTORICAL_LOCAL_AGGREGATE`):** delivered cells are numeric `0`/`1` for DM, HTN, Current Smoker, EX-Smoker, FH, Typical Chest Pain.
- **Tao et al. 2025 Table 1** (secondary 0=false, 1=true): **not re-read** this round (`X-TAO`).

**Finding:** `PARTIALLY_SUPPORTED` for **Yes=present history** as 2012 author meaning; `UNRESOLVED` for **workbook 0/1 direction as owner-certified**. S-9 stays provisional. No recoding.

### 6.2 Chest-pain relations (Q-07)

2012 Table 2 lists Typical, Atypical, Nonanginal CP and Exertional CP as **four parallel Yes/No columns**. Nothing says they are mutually exclusive. Zhang et al. 2022 §3 (`SECONDARY_PAPER`) reports Exertional CP constant on *that paper’s* 303-row copy and then drops “External CP” (misspelling). That is a **secondary hypothesis**, not an original-author statement, and not a licence to edit `uci412_basic_clinical_v1`.

**Finding:** `UNRESOLVED` for exclusivity and timing; `SECONDARY_CONSTANT_FEATURE_HYPOTHESIS_ONLY` for constancy.

### 6.3 BP and PR (Q-05)

See row 10–11 of §4. Original 2012 names and ranges plus EJSR derived cut-offs **support a systolic-compatible single BP and a bpm-compatible pulse rate as the authors’ modelling interpretation**. They do **not** certify the recorded quantity, the printed `ppm` token, device, posture, or time. Do not map BP to `trestbps`.

**Finding:** `PARTIALLY_SUPPORTED` (author terminology + derived cut-offs); measurement semantics `UNRESOLVED`. Register status remains `UNRESOLVED_SCIENTIFIC_HOLD`.

---

## 7. AngioCAD

### 7.1 Owner-published facts

| Claim | Source | Authority | Proves | Does not prove |
|---|---|---|---|---|
| 413 **patients**, video sequences + structured clinical/lab data | PubMed 42033972 Methods; Zenodo description; ScienceDirect abstract/Introduction/Conclusion | `OWNER_PAPER_ABSTRACT` + `OWNER_METADATA` | Author-stated patient denominator | 413 tabular rows; 1:1 video map |
| 413 X-ray coronary angiography **videos** | ScienceDirect Highlights bullet 1 | `OWNER_PAPER_ABSTRACT` | Author-stated video count in Highlights | File count; videos per patient |
| Each case: artery-level stenosis (example: 100% proximal RCA) + demographic and laboratory information | PubMed Methods; Highlights bullet 2 | `OWNER_PAPER_ABSTRACT` | Multimodal intent | Field list, units, binary CAD rule |
| “publicly accessible, **non-commercial** XRA dataset” | ScienceDirect contribution bullet | `OWNER_PAPER_ABSTRACT` | Article wording | Identity with CC BY 4.0 |
| Retrospective angiographic collection, Shahid Chamran Heart Center, Isfahan; ethics University of Isfahan; consent obtained; identifiers removed | ScienceDirect Ethics snippet | `OWNER_PAPER_ABSTRACT` | Retrospective imaging collection | Clinical/lab clock vs cath |
| Zenodo `cc-by-4.0`, `access_right: open`, revision 5, 2025-07-15 / modified 2026-04-21 | Zenodo API | `OWNER_METADATA` | Declared instrument | Operational reuse approval |
| Files: 4× RAR (16,401,400,789 B) + `AngioCAD_Features.xlsx` 129,493 B + `AngioCAD_Labels.xlsx` 43,267 B | Zenodo API manifest | `OWNER_METADATA` | Names, sizes, MD5s | Sheet schema, row counts (files **not opened**) |

**Relationship 413 patients ↔ 413 videos:** `UNKNOWN_NOT_ESTABLISHED`. Do not collapse the two author counts.

**Patient-level binary CAD target in owner text:** `NOT VERIFIED IN ACCESSIBLE MATERIALS`. “CAD diagnosis” is listed as a supported *task*. The Introduction’s “CAD is generally diagnosed when there is &gt;50% blockage” is textbook framing, **not** a dataset rule.

**Pre-angiography predictors:** `NOT VERIFIED IN ACCESSIBLE MATERIALS`. Imaging/stenosis labels are post-catheterization by construction.

### 7.2 Secondary GitHub schema — useful, not owner, not admission

[MRS028/AngioCAD_Project](https://github.com/MRS028/AngioCAD_Project) (Md. Rifat Sheikh, 2026) is a **third-party benchmark**. README: “The patient data are not distributed”; “No license file is present yet.” Authority: `SECONDARY_REANALYSIS_CODE`.

Public code (`src/angiocad_common.py`) that we read **without opening xlsx/RAR** states:

| Item | Secondary statement | Implication for CardioAssist |
|---|---|---|
| 413 patients with segment grades; **377** with clinical data; **376** with ≥1 usable frame; ID 157 empty image folder | README “Cohort” | 413 ≠ analysable clinical *n*. Owner 413 is not a tabular sample size. |
| 15 segment columns: LM, Prox/Mid/Dist LAD, 1st/2nd dig, Prox/Mid/Dist LCX, OM, Prox/Mid/Dist RCA, PDA, PLB; bands NL, 1–25, 26–50, 51–75, 76–90, 91–99, 100 | `STENOSIS_COLS` | Artery-level seven-band labels, **post-cath**. |
| Constructed `has_cad` = max midpoint stenosis ≥ 50, so 51–75 band is positive and exact 50% in 26–50 is negative (“more than 50%, not at least 50%”) | README “Label”; `CAD_THRESHOLD = 50.0` | **Secondary-constructed** patient binary endpoint. Not an owner codebook. Conflicts with UCI-412 ≥50% wording. |
| 298 CAD / 79 non-CAD of 377 (79.0%) | README | Secondary class counts only. |
| **STEMI 186/377 (49.3%)**; 181/186 STEMI are CAD-positive; most CAD-negatives presented with stable angina | README baseline table | **Acute-coronary-syndrome mix**, not a chronic suspected-CCS pretest sample. |
| 22 numeric + 17 categorical = 39 inputs, including LVEF, lipids, meds; **Gensini excluded as computed from the angiogram** | `NUMERIC_FEATURES`, `CATEGORICAL_FEATURES`, `LEAKY_COLUMNS` | A **clinical table exists** in the deposit (by filename and by this reanalysis). It includes echo (LVEF) and presentation-related fields. **No BP, PR, or chest-pain flags** appear in this secondary input list. |
| Missingness: LVEF 22.3%, smoking 12.2%, BMI 8.8%, … | README | UCI-412’s “no missing values” does **not** transfer. |
| `BUN` header trailing space | code comment | Schema quality issue in the xlsx, unverified by us. |

**What this secondary code proves:** someone who opened the spreadsheets published a column inventory and a label rule. **What it does not prove:** owner-endorsed schema, pre-cath timing, or fitness for Track A. We did not replicate the file open.

### 7.3 Licence: CC BY 4.0 vs “non-commercial” (`DISPUTED` documentary restriction)

- Zenodo: `license.id = cc-by-4.0`.
- CC BY 4.0 deed: share/adapt **even commercially**; no NC clause (`LIC1`).
- Article contribution: “publicly accessible, **non-commercial** XRA dataset”.
- Secondary GitHub: no licence file; data not redistributed.

**Finding:** `DISPUTED` documentary restriction. Declared instrument is CC BY 4.0; article wording is not a restatement of that instrument. **Not legal advice. No reuse, download or commercial-use approval follows.** Clarify with the curator before any access discussion.

### 7.4 Classification — preserved

**`SCIENTIFIC_HOLD_NOT_ADMITTED`.** Supervisor colour **`REJECTED_RED` (P25)** unchanged.

AngioCAD is **not** imaging-only (Features.xlsx exists). It is **not** an admissible pre-procedure Track A tabular source on accessible evidence: owner schema unread, pre-cath timing unverified, patient binary CAD rule not owner-defined, 413≠377 clinical, and the secondary cohort is STEMI-heavy. Its documented core task is **post-catheterization video stenosis / view classification**. That task is out of this project’s pretest estimand.

---

## 8. Research-question register (required five-part answers)

Canonical `questions[].status` values below are **unchanged** from `RH02_SOURCE_QUESTION_REGISTER_2026_11_19.json`. Finding class ≠ register status.

### Q-03 — UCI-412 CAD threshold

1. **Sources:** UCI-412 Additional Information (owner, 2017 page); 2012 JMSS §2; 2016 KBS Introduction; 2017 Arabasadi Dataset snippet.
2. **Evidence / authority:** Owner + 2012 original: ≥50%. 2016/2017 original-author(–coauthor): &gt;50%.
3. **Proves / does not:** Proves UCI landing-page rule is ≥50%. Does not prove exact-50% row handling or equivalence to UCI-45.
4. **Conflicts:** Original-author &gt;50% vs ≥50% (§2.3).
5. **Finding:** `DISPUTED` (edge); owner-page ≥50% `SUPPORTED`. **Register status unchanged:** `RESOLVED_PRIMARY_METADATA_ONLY`.

### Q-04 — 16-field pre-angiography timing

1. **Sources:** 2012 JMSS §2; 2013 RCM Abstract/§3/§5; UCI/Mendeley (no timestamps); 2013 CMPB / 2016 snippets.
2. **Evidence:** Referred chest-pain angiography volunteers (2012) and chest-pain referrals whose lab/echo features are used to “obviate angiography” (2013 RCM). **Neither paper states a per-feature clock vs angiography or vs knowledge of the stenosis label.**
3. **Proves / does not:** Cohort design ≠ field-level pretest certification. 2013 RCM echo/lab inputs do not become pretest-certified by being called non-invasive. Same *n* = 303 is not a row join.
4. **Conflicts:** None on timestamps (universal silence).
5. **Finding:** `UNRESOLVED` (0/16). **Status unchanged:** `UNRESOLVED_SCIENTIFIC_HOLD`.

### Q-05 — BP and PR

1. **Sources:** 2012 JMSS Table 2; 2012 EJSR Table 4; Eyupoglu 2024 Table 1; UCI API empty units; 2013 RCM Tables 1–2 (negative: BP/PR absent).
2. **Evidence:** “Blood Pressure” 90–190, `BP2` high if &gt;140; “Pulse Rate” 50–110, `PR2` normal 60–100; secondary mmHg / ppm. 2013 RCM does **not** document BP subtype or `PR ppm`.
3. **Proves / does not:** Author modelling interpretation is systolic-compatible BP and bpm-compatible pulse. Not a codebook for quantity, device, `ppm`, or time.
4. **Conflicts:** 2012 no unit vs secondary mmHg/ppm.
5. **Finding:** `PARTIALLY_SUPPORTED` (terminology); measurement `UNRESOLVED`. **Status unchanged:** `UNRESOLVED_SCIENTIFIC_HOLD`.

### Q-06 — numeric binary direction

1. **Sources:** 2012 JMSS §2 definitions; 2013 RCM Table 1 Yes/No counts; local A-1 audit; Tao 2025 Table 1 unread this round.
2. **Evidence:** Yes/No history semantics originally; 2013 RCM reprints Yes/No with counts; xlsx is 0/1 per prior local audit.
3. **Proves / does not:** 2012/2013 meaning of the *concepts*; not owner 0/1 direction.
4. **Conflicts:** Yes/No tables vs numeric delivery.
5. **Finding:** `PARTIALLY_SUPPORTED` (history semantics); direction `UNRESOLVED`. **Status unchanged:** `CONDITIONAL_SOURCE_REVIEW_REQUIRED`.

### Q-07 — chest-pain flags

1. **Sources:** 2012 Table 2; Zhang 2022 §3–4.1.
2. **Evidence:** Four parallel flags; secondary constancy claim with misspelling.
3. **Proves / does not:** Distinct columns existed. Not exclusivity, timing, or constancy of *our* file.
4. **Conflicts:** Secondary “delete External CP” vs frozen 16-field panel.
5. **Finding:** `UNRESOLVED`. **Status unchanged:** `UNRESOLVED_SCIENTIFIC_HOLD`.

### Q-08 — 54 vs 55 vs 56

1. **Sources:** §3 table; 2013 RCM Tables 1–2.
2. **Evidence:** Original 2012 **37**; original 2013 RCM **16 demo + 17 lab/echo** (paper never says 54); 2013 CMPB/2016/2017/UCI/Mendeley **54**; secondary 55; local 55+Cath; UCI 56 blank rows; 411 = 59. 37+17=54 is now an original-author-table **hypothesis**, not a chosen count.
3. **Proves / does not:** A real version/count discrepancy. 2013 RCM **supports the 17 lab/echo names**. Does not identify the extra column without a header audit. Does not prove 303-row identity.
4. **Conflicts:** 54+3≠59 vs 56+3=59; Rhythm vs BBB; Function Class 1–4 vs 0–3; Length omitted from both original Table 1s but used in IG/Gini; several lab **ranges** differ from frozen secondary ranges.
5. **Finding:** `DISPUTED` / `UNRESOLVED`. **Status unchanged:** `DOCUMENTED_REPOSITORY_AGGREGATE_ONLY`. **54 vs 55 is not inferred as resolved.**

### Q-14 — AngioCAD pretest tabular source

1. **Sources:** §7.
2. **Evidence:** Owner 413 patients + 413 videos + two XLSX; secondary 377 clinical / STEMI-heavy constructed &gt;50% label; CC BY 4.0 vs “non-commercial”.
3. **Proves / does not:** Multimodal deposit exists. Does not prove pretest Track A eligibility.
4. **Conflicts:** 413 vs 377 vs 376; ≥50 vs &gt;50 constructed; CC BY vs NC wording.
5. **Finding:** `PARTIALLY_SUPPORTED` as a **different imaging/stenosis task**; `UNRESOLVED` as pretest tabular CAD; classification **`SCIENTIFIC_HOLD_NOT_ADMITTED`**. **Status unchanged:** `CONDITIONAL_SOURCE_REVIEW_REQUIRED`. Literature colour **`REJECTED_RED` (P25)** unchanged.

---

## 9. Decision matrix (recommendations, not admissions)

| ID | Decision | Finding | Authority ceiling | Permitted next action | Forbidden next action |
|---|---|---|---|---|---|
| D-UCI-TH | Keep UCI-412 target as source-defined ≥50%; report original-author &gt;50% conflict | `DISPUTED` edge | Owner page + original papers | Quote both wordings in FR-04 | Harmonize with Cleveland; pick 2016 to override UCI |
| D-UCI-TIME | Do not treat the 16 fields as verified pretest inputs | `UNRESOLVED` | 2012 and 2013 RCM design intent only; **no per-feature clocks** | Owner CRF request | New real UCI-412 training / AI-9.2; treat 303 as a verified join |
| D-UCI-BPPR | Do not map BP→`trestbps` or certify `ppm` | `PARTIALLY_SUPPORTED` | 2012 tables + EJSR BP2/PR2 | Ask owner: systolic? unit? conditions? | Recode PR or collapse with Cleveland BP |
| D-UCI-BIN | Keep S-9 provisional | `PARTIALLY_SUPPORTED` | 2012 Yes/No history | Owner 0/1 statement | Heuristic recoding |
| D-UCI-CP | Keep four flags as delivered | `UNRESOLVED` | 2012 parallel columns | Optional authorized aggregate uniqueness of Exertional CP | Drop column because Zhang 2022 did |
| D-UCI-N | Do not choose 54 or 55 or 56 | `DISPUTED` | Owner + 2012/2013 RCM tables + local + secondary | Cite 2013 RCM Table 2 as original-author **17 lab/echo names**; authorized header/shape audit of **named** delivery | “Fix” dictionary to 54 because 37+17=54 |
| D-ANG-ADM | AngioCAD remains **not admitted** | `SCIENTIFIC_HOLD_NOT_ADMITTED` | Owner + secondary | Curator schema/timing/licence questions | Download RAR/XLSX; train; call it Track A |
| D-ANG-LIT | Keep **P25 `REJECTED_RED`** | `SUPERVISOR_CLASSIFICATION` | Supervisor sheet | Cite as rejected-from-selected-scope | Recolour because a table exists |
| D-ANG-TASK | If ever in scope, it is an **imaging/stenosis + mixed-ACS** task | `PARTIALLY_SUPPORTED` (secondary) | MRS028 README | Separate protocol, separate estimand | Substitute for UCI-412/Cleveland pretest CAD |
| D-HOLD | Gate PT P-3 CLOSED; P-1 PENDING; P-5 prohibited; D-046 read-only; D-047 Cleveland-only; D-048 unratified | — | Existing governance | Human review of this packet | Infer approval from this PR |

**Conditional studies:** AI-9.2 and AI-10.2 remain `HOLD_NOT_EXECUTED`. This packet is not a GO or a permanent NO-GO.

---

## 10. Ranked recommendations (cheapest–safest first)

1. **Human review of this packet.** No register JSON, supervisor CSV, dictionary or protocol should change until a named reviewer accepts specific rows.
2. **UCI-412 author/curator letter (zero data access):** (a) original CRF for the 16 fields with clock vs angiography; (b) BP quantity (SBP/DBP/other), unit, posture; (c) PR unit and the `ppm` token; (d) Yes/No → 0/1 map; (e) chest-pain exclusivity; (f) why prose says 54, UCI UI has 56 rows, 411 says 59; (g) ≥50 vs &gt;50 in 2016/2017 papers; (h) whether 2012 JMSS, 2013 RCM, 2013 CMPB and the UCI/Mendeley workbooks are the **same 303 rows**; (i) lab units and the Cr/“Creatine” token.
3. **AngioCAD curator letter (zero download):** schema of Features/Labels; patient↔video map; clinical/lab chronology; owner patient-level CAD rule if any; which text governs reuse (CC BY 4.0 vs “non-commercial”).
4. **Do not recolour P25 and do not lift `SCIENTIFIC_HOLD_NOT_ADMITTED`.**
5. **If and only if separately authorized:** local read-only header/shape comparison of UCI vs Mendeley UCI-412 files (names/counts only).
6. **If and only if separately authorized:** aggregate-only distinct-value count of `Exertional CP` on the hash-pinned local source.
7. **Keep AngioCAD out of Track A.** A future imaging line would need its own protocol, ACS-mix handling, and leakage control (Gensini, stenosis grades, presentation).
8. **Do not** re-fit M3a/D-047, download Zenodo payloads, or treat MRS028 metrics as CardioAssist results.

---

## 11. Proposed register text (not applied)

The file `RH02_SOURCE_QUESTION_REGISTER_2026_11_19.json` is **not edited**. If a maintainer later accepts this investigation, proposed `evidence_or_gap` appendices are:

| Question | Canonical status (unchanged) | Proposed appendix only |
|---|---|---|
| Q-03 | `RESOLVED_PRIMARY_METADATA_ONLY` | 2012 JMSS ≥50 vs 2016/2017 original-author &gt;50 wording. |
| Q-04 | `UNRESOLVED_SCIENTIFIC_HOLD` | 2012 “volunteers for angiography” and 2013 RCM “obviate angiography” are cohort design, not 16 timestamps. Same *n*=303 is not a row join. |
| Q-05 | `UNRESOLVED_SCIENTIFIC_HOLD` | 2012 “Blood Pressure”/“Pulse Rate” + EJSR BP2 140 / PR2 60–100; 2013 RCM has no BP/PR; still no codebook. |
| Q-06 | `CONDITIONAL_SOURCE_REVIEW_REQUIRED` | 2012 history definitions for DM/HTN/smoker/FH; 2013 RCM Yes/No counts. |
| Q-07 | `UNRESOLVED_SCIENTIFIC_HOLD` | 2012 four parallel Yes/No flags. 2013 RCM does not list chest-pain columns. |
| Q-08 | `DOCUMENTED_REPOSITORY_AGGREGATE_ONLY` | 2012 37-feature precursor; 2013 RCM original 17 lab/echo names (not a 54-count); Rhythm vs BBB; Function Class 1–4 vs 0–3; Length omitted from both Table 1s; 54+3≠59. 54 vs 55 **not** inferred. |
| Q-14 | `CONDITIONAL_SOURCE_REVIEW_REQUIRED` | Secondary 377 clinical / STEMI 49%; constructed &gt;50% label; P25 remains REJECTED_RED; classification remains SCIENTIFIC_HOLD_NOT_ADMITTED. |

**Explicitly not proposed:** any `decision_id`, any status string change, any colour change, any dictionary/panel/hash change.

---

## 12. Frozen contracts inspected, not modified

- `research/uci412/schemas/uci412_feature_dictionary.v1.json` — 56 entries, schema 1.1.0, `PROPOSED_NOT_SUPERVISOR_APPROVED`.
- `research/uci412/source_spec.py` — 54-feature owner wording and 55+Cath local observation both registered.
- `research/audit/registry.py` — 17+14+7+17 predictors including `BBB` and `Length`.
- `research/source_materials/literature_review_status.csv` — P25 `REJECTED_RED`.
- RH-02 question register statuses.

---

## 13. Validation

Documentation-level only. Commands and results are recorded in the JSON `validation` object and in the PR. Passing JSON/reference checks proves internal consistency, **not** dataset truth or clinical validity.

---

## 14. Limitations

1. **Paywalls.** 2013 **CMPB** / 2016 / 2017 Table 1 and AngioCAD §§3–5 unread. The 2013 **RCM** Tables 1–2 **were** read (PMC HTML). Absence in accessible materials ≠ non-existence inside unread PDFs/workbooks.
2. **No file opened.** Headers, dtypes, row counts of xlsx/RAR unknown from bytes.
3. **2012 EJSR** is extract-level, not a second archived full PDF.
4. **2013 RCM PDF** fetch returned HTTP 500; PMC HTML including Tables 1–2 and Gini Tables 4–6 was read. Association-rule block described as “shown below” was not recovered as text (possible figure).
5. **Tao 2025 Table 1** not retrieved; S-9 not re-verified.
6. **MRS028** is independent secondary code, not Hosseini et al.
7. **Issue #104** not machine-read (`403`).
8. **Secondary tables are not owner CRFs.** 2013 RCM Tables 1–2 are original-author **published tables**, still not a CRF or workbook.
9. **303 is a published sample size**, not a verified patient-level identity across papers or deposits.
10. This PR **must not** be cited as scientific or clinical approval.

---

**Bottom line.** Original-author **2012 JMSS** tables name BP, PR, and history flags (clinical/ECG). Original-author **2013 RCM** (PMC4253773) — a **different paper** from paywalled 2013 CMPB — supplies **demographic Table 1 and 17 laboratory/echo names with ranges**. v1’s “only one original-author full text” claim is corrected. Neither paper certifies pre-cath timestamps (still **0/16**), 0/1 direction, BP systolic-vs-diastolic, `PR ppm`, or a single feature count. 37+17=54 is an original-author-table **hypothesis, not adopted**; 303 is not a verified row join. AngioCAD remains a post-cath multimodal resource with a CC BY 4.0 vs “non-commercial” documentary clash. **`REJECTED_RED` (P25) and `SCIENTIFIC_HOLD_NOT_ADMITTED` are preserved. No hold was lifted. No patient file was downloaded. No model was fitted.**
