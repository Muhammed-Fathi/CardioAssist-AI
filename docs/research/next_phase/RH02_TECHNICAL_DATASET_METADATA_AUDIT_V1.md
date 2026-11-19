# RH-02 — Technical Dataset Metadata Audit V1: AngioCAD and UCI-412

**Date checked:** 2026-11-19 · **Review state:** `REVIEW_DRAFT_NOT_SCIENTIFIC_ADMISSION`
**Task:** [Issue #99](https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/99) — RH-02 agent task, public AngioCAD/UCI-412 metadata and feature-schema audit (NO real-data access).
**Issue-pinned baseline:** `092b0f528d8d6c00101d5e013dc8221ebf8f5896` ("Merge pull request #98", 2026-11-19). That object is not reachable from the default shallow clone and had to be fetched explicitly; it is **not** an ancestor of the current `main`, so the audit was reconciled against the latest merged state.
**Audited `main`:** `a57220c2151680fe53e561dceddbcf88c481196f` (merge of PR #100, "docs(rh02): distinguish AngioCAD article's 413 patients and 413-video Highlights").
**Machine-readable companion:** [`RH02_TECHNICAL_DATASET_METADATA_AUDIT_V1.json`](RH02_TECHNICAL_DATASET_METADATA_AUDIT_V1.json) (schema `cardioassist.rh02_technical_dataset_metadata_audit/v1`).
**Cross-references:** [RH-02 first pass](RH02_PRIMARY_SOURCE_ADMISSIBILITY_2026_11_19.md) · [RH-02 Round 2](RH02_ROUND2_SOURCE_RECONCILIATION_2026_11_19.md) · [16-question register](RH02_SOURCE_QUESTION_REGISTER_2026_11_19.json) · [AI-8R source admissibility](../ai8r/SOURCE_ADMISSIBILITY.md) · [AI-12.2 manuscript](../next_phase/AI12_2_GRADUATION_RESEARCH_MANUSCRIPT_DRAFT_2026_11_19.md).

> **What this document is.** A read-only, documentation-level audit of **public owner metadata and published article text** for two candidate sources. It records what a stranger to the project could verify today from public pages, and precisely what remains unverifiable. It is **not** an admission decision, **not** a dataset audit of any workbook, **not** scientific or clinical approval, and **not** an authorization to read patient-level data.
> **Nothing here lifts a hold.** Gate PT `P-3` stays **CLOSED**, `P-1` **PENDING**, `P-5` prohibited; D-046 stays read-only audit; D-047 stays Cleveland-only; D-048/M3a remain unratified where they already were.

---

## 0. Scope, authorization and what was actually done

### 0.1 Permitted and performed

| Activity | Performed | Detail |
|---|---|---|
| Public landing-page and metadata-API reads | **Yes** | Zenodo record API; UCI dataset page **and** UCI JSON API for 412 (and 411 as context); Mendeley Data deposit page; PubMed abstract pages (42033972, 23537611); ScienceDirect article preview page; MDPI article page. |
| Published abstract/text reads | **Yes** | PubMed abstracts (full); ScienceDirect preview (Highlights, abstract, Introduction, contribution bullets, Conclusion, Ethics statement, Data availability, reference list); MDPI §3 and §4.1 text. |
| Repository contract inspection (read-only) | **Yes** | `research/uci412/schemas/uci412_feature_dictionary.v1.json`, `research/uci412/source_spec.py`, `ai/panels.py`, `docs/research/ai8r/SOURCE_ADMISSIBILITY.md`, RH-02 register/round-2 report. |
| Dataset / workbook / video download | **No** | Zero bytes of any dataset file were retrieved. Only HTTP metadata responses were read. |
| Model fit, retrain, evaluation, real-data experiment | **No** | None attempted. |
| Changes to frozen protocols, panels, dictionary, models, providers, manifests, `ai_master_progress.json` | **No** | See §3.7 and §7. |

### 0.2 Scope limits stated up front

1. **Article full text is paywalled.** For AngioCAD only the public preview (Highlights → Data availability) was readable. The dataset section, the per-task method subsections and the results tables (which would contain the clinical field inventory, units, and the exact CAD label construction) were `NOT_ACCESSIBLE`.
2. **UCI-412 field names are not published.** The owner's machine-readable metadata declares the variable list but leaves every name/type/description blank (§3.2). Therefore no per-field claim in this document is derived from UCI metadata; per-field statements are restricted to what is already registered in the repository or explicitly labelled `SECONDARY_PAPER`.
3. **One secondary source was re-read (`S1`), one was not.** The 2022 *Electronics* paper was fetched and quoted in this pass; the 2020 *IJERPH* paper (`S2`) was **not** re-fetched and is carried forward only as previously recorded in the RH-02 register.
4. **The directive text reached the agent through the maintainer, not the API.** The session's GitHub token can read code and pull requests but returns `403 Resource not accessible by integration` for every Issues endpoint, so Issue #99 itself was not machine-read. The maintainer supplied the specification verbatim in-session; the issue URL is recorded here as the scope-of-record. This limitation is procedural, not scientific, and is listed again in §9.

---

## 1. Access log (exact URLs, observed outcomes, 2026-11-19)

| ID | URL | Observed | What could actually be read |
|---|---|---|---|
| `P3A` | `https://zenodo.org/api/records/15826856` | `200 OK`, JSON | Full record metadata **including the file manifest** (names, byte sizes, MD5s), licence, description, creators, dates, revision, download/view statistics. No file content. |
| `P3B` | `https://pubmed.ncbi.nlm.nih.gov/42033972/` | `200 OK` (first attempt returned `HTTP 500`; retried successfully) | Complete structured abstract, keywords, conflict-of-interest statement. |
| `P3C` | `https://www.sciencedirect.com/science/article/pii/S0169260726001331` | `200 OK`, **preview only** | Journal/volume/article number, all five Highlights, abstract, Introduction (full), contribution bullets, Conclusion, Data availability, Ethics statement, reference list. **Sections 3–5 body and tables: paywalled, `NOT_ACCESSIBLE`.** |
| `P1A` | `https://archive.ics.uci.edu/dataset/412/z+alizadeh+sani` | `200 OK` | Dataset characteristics, "Additional Information", "Additional Variable Information", variables-table shell (names blank; paginator reports 56 rows), file list and size, DOI, licence, creators. |
| `P1B` | `https://archive.ics.uci.edu/api/dataset?id=412` | `200 OK`, JSON | Machine-readable record: `num_instances 303`, `num_features 0`, `target_col null`, 56 variable objects with `name` = `" "`. |
| `P1C` | `https://archive.ics.uci.edu/api/dataset?id=411` | `200 OK`, JSON | Context only: same 303 instances; "59 features"; Note 1 on the three added artery columns and `Cath`. |
| `P1D` | `https://data.mendeley.com/datasets/vrymwyh2tg/1` | `200 OK` | Depositor description, version, DOI, licence, single file `CAD.xlsx` (118 KB). |
| `P2` | `https://pubmed.ncbi.nlm.nih.gov/23537611/` | `200 OK` | Complete 2013 abstract (303 patients / 54 features / feature-creation method / 94.08% accuracy claim). |
| `S1` | `https://www.mdpi.com/2079-9292/11/9/1495` | `200 OK` | Abstract, §1 opening, §3 (Dataset), §4.1 (Preprocessing) and §6 fragment via page and search-index text. Full 44-page PDF not downloaded. |
| `S1B` | `https://arxiv.org/abs/2609.06931` | `200 OK` | Abstract page of a 2026 preprint that re-uses AngioCAD; **body text not read** (third-party count quoted only at excerpt level, §2.2). |
| `X1` | `https://www.imrpress.com/journal/RCM/26/3/10.31083/RCM26204` | `200 OK` but only front matter, figure links and reference list rendered | Tao et al. (2025) body/Table 1 **not retrieved**. The S-9 direction claim therefore remains exactly as the repository recorded it in Amendment A-1 — **not** independently re-verified here. |
| `N1` | `https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/99` | `403` via API; `404` unauthenticated | Issue body not machine-readable (private repository; token lacks Issues read). See §0.2.4. |

---

## 2. AngioCAD — public metadata audit

### 2.1 What the owner published (authority: `OWNER_METADATA`, `P3A`)

Record `15826856` (concept DOI `10.5281/zenodo.15826855`), title *"AngioCAD: A Publicly Available X-ray Angiography Dataset for Coronary Artery Stenosis and CAD Detection"*, publication date **2025-07-15**, record created 2025-07-15, last modified **2026-04-21**, revision **5**, state `published`, `access_right: "open"`, `license.id: "cc-by-4.0"`, resource type `dataset`, editors `University of Isfahan`, `Isfahan University of Technology`, `Isfahan University of Medical Sciences`.

Depositor description (verbatim): *"…consists of anonymized and expert-annotated X-ray coronary angiography video frames from 413 patients. The dataset includes sequential PNG images extracted from DICOM format after removing identifiable metadata. Each case contains clinical and laboratory data, along with artery-level stenosis labels in seven severity categories. The dataset supports multiple CAD-related tasks, including view classification, stenosis detection, and CAD diagnosis."*

### 2.2 The two author-reported counts must stay separate

| Count | Where it appears | Authority | What it does **not** establish |
|---|---|---|---|
| **413 patients** | Zenodo description (`P3A`); PubMed abstract Methods (`P3B`); ScienceDirect abstract, Introduction, Conclusion (`P3C`) | `OWNER_METADATA` + `OWNER_PAPER_ABSTRACT` | Does not establish 413 analyzable rows in either spreadsheet; does not establish a per-patient tabular record. |
| **413 X-ray angiography videos** | ScienceDirect **Highlights** bullet 1 (`P3C`): *"a public dataset of 413 X-ray coronary angiography videos with expert annotations and clinical data"* | `OWNER_PAPER_ABSTRACT` (article front matter) | Does not establish 413 files, 413 studies, or one video per patient. |

**Relationship between the two numbers: `UNKNOWN_NOT_ESTABLISHED`.** The owner publishes no manifest, no per-patient file index, and no statement that video count equals patient count. One case *may* comprise several views/sequences; the accessible text does not say. The earlier repository correction (PR #100) is therefore confirmed and **must not** be "resolved" in either direction: neither "413 videos, not patients" nor "413 patients, so 413 videos" is supported.

**Third-party conflict (excerpt level only, `SECONDARY_PAPER_EXCERPT_ONLY`).** A 2026 preprint re-using AngioCAD states a *"full cohort (n=412)"* and a valid-views subset `n=326` ([arXiv:2609.06931](https://arxiv.org/abs/2609.06931), abstract page read; body quoted from the search index, **not** full-text verified). This is recorded as a **count conflict in secondary literature** and is not evidence about the owner's records. It reinforces the rule: do not restate 413 as a file-level or analyzable-n fact.

### 2.3 Verified archive file manifest (public API only, no download)

| File | Bytes | Format | MD5 (as published) | Content inspected? |
|---|---|---|---|---|
| `AngioCAD_Dataset.part1.rar` | 4,194,304,000 | RAR (multi-part) | `3f406741a35ce45a5b6caa60e3ac8ab9` | **No** |
| `AngioCAD_Dataset.part2.rar` | 4,194,304,000 | RAR (multi-part) | `0596e0a58a7a252a19b31e8bec37dc96` | **No** |
| `AngioCAD_Dataset.part3.rar` | 4,194,304,000 | RAR (multi-part) | `f425ca88df9e6024dbeeed3cea582ce9` | **No** |
| `AngioCAD_Dataset.part4.rar` | 3,818,488,789 | RAR (multi-part) | `a8f24f0523a129ede37112533eb9629b` | **No** |
| `AngioCAD_Features.xlsx` | 129,493 | XLSX | `1617d242df42367787f445392729f35e` | **No** |
| `AngioCAD_Labels.xlsx` | 43,267 | XLSX | `fc97ffc2978f6cee93a1059e8b1c282f` | **No** |

Derived arithmetic (document-level only): the four RAR parts total **16,401,400,789 bytes**; parts 1–3 are exactly 4,000 MiB each, consistent with a fixed-volume archive split. Record statistics at access time: 7,228 downloads (1,637 unique), 1,204 views (1,042 unique).

**Naming inference must not be promoted to fact.** That `AngioCAD_Features.xlsx` holds the clinical/laboratory attributes and `AngioCAD_Labels.xlsx` holds the seven-category artery labels is an **inference from filenames only** (`UNVERIFIED_INFERENCE`). The owner metadata does not assign content to filenames, publish a sheet inventory, or state row/column counts.

### 2.4 Issue §A.4 checklist — what public metadata does and does not identify

| Question | Answer | Basis |
|---|---|---|
| Structured clinical/tabular files present? | **Yes, by filename and format only** — two XLSX files exist in the public manifest | `P3A` manifest |
| File formats (CSV/XLSX)? | **XLSX, not CSV.** No CSV/TSV/JSON/Parquet file exists in the record | `P3A` manifest |
| Field/schema documentation available? | **No.** No data dictionary, codebook, README, schema file, or per-column list in the record; the description is prose only | `P3A` |
| Patient/sample counts? | **413 patients** (owner prose); **no per-file record count**; no video count in the record | `P3A`, `P3B`, `P3C` |
| Licence and access restrictions? | **`CC BY 4.0`, `access_right: open`** in the record; article text calls the resource **"non-commercial"** — an unreconciled conflict (§2.6) | `P3A`, `P3C` |
| Pre-angiography clinical/laboratory predictors? | **Not identified.** No statement of when clinical/lab values were captured relative to the angiographic procedure | `P3A`, `P3B`, `P3C` (accessible parts) |
| Independently defined patient-level binary CAD presence target? | **Not identified.** Published annotations are **artery-level, seven-severity-category**; "CAD diagnosis" is listed as a *supported task*, with no published binary definition, threshold, or adjudication process | `P3A`, `P3B`, `P3C` |

### 2.5 Pre-procedure predictors versus post-catheterization annotation

- The **imaging and stenosis material is post-catheterization by construction**: the record describes *"anonymized and expert-annotated X-ray coronary angiography video frames"* derived from *"sequential PNG images extracted from DICOM"*, and the annotations are *"artery-level stenosis labels in seven severity categories"*. X-ray coronary angiography is itself the invasive reference procedure.
- The article's ethics statement confirms **retrospective** collection: *"The angiographic data were retrospectively collected from Shahid Chamran Heart Center (Isfahan, Iran)"*, with ethics approval from the University of Isfahan, consent obtained, and identifying information removed.
- The **clinical/laboratory attributes have no documented acquisition moment.** Because collection was retrospective and no field-level chronology is published, the source could equally represent (a) history/labs recorded at/around the procedure, (b) values copied from a report generated after the angiogram, or (c) a mixture. **The project's rule applies unchanged: no field may be treated as a pre-angiography predictor on plausibility grounds.**
- Consequence: AngioCAD's angiography/label layer must never be treated as a candidate *predictor* set, and its tabular layer cannot yet be positioned on the pre-procedure side of the Track A / Track B boundary.

### 2.6 Licence wording conflict (new, unresolved)

The record declares `CC BY 4.0` (a licence permitting commercial reuse with attribution), while the article's contribution list describes a *"publicly accessible, **non-commercial** XRA dataset"*. These are different permissions. This audit does **not** choose between them: the Zenodo declaration is the machine-readable deposit statement, the article wording is prose from the authors, and neither is a legal interpretation. **Consequence:** the repository's previous "licence unverified" note can now be sharpened to *"record declares CC BY 4.0; article describes the resource as non-commercial; the conflict is unresolved and requires owner/legal clarification before any reuse decision."* No reuse, redistribution, or commercial-use assumption may be made from this audit.

### 2.7 Classification

**`SCIENTIFIC_HOLD_NOT_ADMITTED`.**

Position, stated in the narrowest defensible terms:

1. AngioCAD is **not** an imaging-only dataset — it demonstrably ships a tabular component (`AngioCAD_Features.xlsx`).
2. It is nevertheless **not admissible as a pre-procedure tabular Track A source** on available documentation, because the four required properties are all missing: a published field schema, a documented pre-angiography acquisition moment, a defined patient-level binary CAD target, and a patient↔row identity statement.
3. Its well-documented core task is **a different, post-catheterization imaging/stenosis research task** (view classification, artery-level stenosis detection). That task is legitimate research but is **not** the CardioAssist Track A target, and it cannot be substituted for it.
4. Therefore the honest classification is: *"potentially interesting multi-modal source whose tabular eligibility is undetermined — `SCIENTIFIC_HOLD_NOT_ADMITTED`, with a clearly distinct imaging/stenosis research task that is out of this project's target scope."* The decision is **not** upgraded, and D-021 human scope review remains the gate.

### 2.8 Evidence required from the owner/curator (AngioCAD)

1. A public **schema for `AngioCAD_Features.xlsx` and `AngioCAD_Labels.xlsx`**: sheet names, column names, dtypes, units, allowed value sets, missing-value conventions, and row counts per sheet.
2. The **patient↔row↔video/study mapping rule**, including the number of videos per patient and the total video/study count actually in the archive.
3. The **acquisition chronology** for every clinical/laboratory field, relative to the angiographic procedure (recorded before / during / after; by whom; from what form).
4. The **patient-level CAD label definition**: threshold, adjudicator(s), whether it is derived from the artery-level severity categories, and the class counts (CAD / non-CAD).
5. Clarification of **licence intent**: is the resource CC BY 4.0 as the deposit declares, or non-commercial as the article states?
6. Confirmation of whether the tabular file contains **any** non-angiography-derived pre-procedure predictor at all.

---

## 3. UCI-412 — feature and source-contract audit

### 3.1 What the owner published

| Source | Authority | Verbatim/near-verbatim content |
|---|---|---|
| UCI dataset page (`P1A`) | `OWNER_METADATA` | 303 instances; `# Features` shown as `-`; types Integer/Real; tabular/classification; missing values **No**; *"A patient is categorized as CAD, if his/her diameter narrowing is greater than or equal to 50%"*; *"The Z-Alizadeh Sani dataset contains the records of 303 patients, each of which have 54 features… four groups: demographic, symptom and examination, ECG, and laboratory and echo features"*; one file `Z-Alizadeh sani dataset.xlsx` (120.7 KB); DOI `10.24432/C5Q31T`; **CC BY 4.0**; donated 2017-11-16; variables table paginates to **56 rows, all names blank**. |
| UCI JSON API (`P1B`) | `OWNER_METADATA` | `num_instances: 303`, **`num_features: 0`**, `target_col: null`, `index_col: null`, `has_missing_values: "no"`, `year_of_dataset_creation: 2013`, `last_updated: 2023-11-03`, and a `variables` array of **56 objects whose `name`, `type`, `role`, `description`, `units` are all blank**. |
| Mendeley deposit (`P1D`) | `OWNER_METADATA` (depositor description) | Published **23 January 2017**, Version 1, DOI `10.17632/vrymwyh2tg.1`; same 303/54/≥50% description; **CC BY 4.0**; single file **`CAD.xlsx` (118 KB)**. |
| 2013 owner study abstract (`P2`) | `OWNER_PAPER_ABSTRACT` | *"a dataset called Z-Alizadeh Sani with 303 patients and 54 features, is introduced"*; Information Gain used; *"Typical Chest Pain, Region RWMA2, and age were the most effective"*; 94.08% accuracy claim. |
| UCI-411 API (`P1C`, context only) | `OWNER_METADATA` | Same 303 instances; *"contains the records of 303 patients, each of which have **59** features"*; Note 1: *"In this extension LAD, LCX, and RCA features have been added. CAD (Last column in dataset) happens when at least one of these three arteries is stenotic. To use this dataset only one of the LAD, LCX, RCA or Cath (Result of angiography) must be in dataset…"* |

**Two owner-delivered artifacts, not one.** UCI distributes `Z-Alizadeh sani dataset.xlsx` (120.7 KB, 2017 donation); Mendeley distributes `CAD.xlsx` (118 KB, 2017 v1). Different filenames and sizes mean the project's "owner-delivered file" is not a single, unique artifact. Any future count reconciliation must name **which** delivery is being measured.

**A positively verified absence.** The owner's machine-readable metadata contains **no** field names, **no** types, **no** units, **no** descriptions, **no** target declaration. That is not "we did not look": the API response is structurally present and the content fields are empty (`num_features: 0`). This is the strongest available evidence for why BP/PR semantics, the six binary directions and per-field timing cannot be resolved from public metadata.

### 3.2 Q-08 — the 54-versus-55+Cath discrepancy

**Counts on the record:**

| Count | Source | Class |
|---|---|---|
| **54 features** | UCI page text; UCI API `additional_info.variable_info`; Mendeley description; 2013 abstract | `OWNER_METADATA` / `OWNER_PAPER_ABSTRACT` |
| **56 variable rows** | UCI dataset page variables table (`0 to 10 of 56`); UCI API `variables` array length | `OWNER_METADATA` (structure only; names blank) |
| **`num_features: 0`** | UCI API | `OWNER_METADATA` |
| **59 features** | UCI-411 API (same 303 participants; three artery columns added) | `OWNER_METADATA` |
| **55 predictors + `Cath` = 56 columns** | Maintainer's 2026-10-22 read-only local audit, as registered in `research/uci412/source_spec.py` | `HISTORICAL_LOCAL_AGGREGATE` |
| **55 features, 216 CAD / 87 normal** | Zhang et al. 2022, *Electronics* 11(9):1495 §3 | `SECONDARY_PAPER` |

**Arithmetic results (this is the new, useful part):**

- The owner says UCI-411 adds **exactly three** artery columns to the same participants. If 412 had 54 feature columns, the extension would hold **57** — but the owner states **59**. **`54 + 3 ≠ 59`.**
- If the delivered 412 workbook holds **56** columns (55 predictors + `Cath`, per the local audit), then adding LAD/LCX/RCA yields exactly **59** — which is what the owner states. **`56 + 3 = 59`.**
- The 2022 secondary paper's "55 features" and 216/87 class counts are internally consistent (`216 + 87 = 303`), and are consistent with a 55-predictor file.

**Classification: `UNRESOLVED_OWNER_FILE_VERSION_FEATURE_COUNT` — with a documented arithmetic inconsistency inside owner metadata.**

- **Hypothesis H-56** (`HYPOTHESIS_NOT_VERIFIED`): the delivered workbook has 56 columns (55 predictors + target), and the owner's "54 features" prose understates by one. This reading is the only one under which the owner's own 59-feature statement for the extension holds.
- **Hypothesis H-55** (`HYPOTHESIS_NOT_VERIFIED`): the owner's "54 features" excludes a further undocumented column and 411's "59" counts differently (e.g. including `Cath` plus another field). This leaves the +3 arithmetic unexplained.
- **Neither hypothesis may be adopted.** The repository rule stands: both facts are recorded verbatim, the discrepancy is documented and **not silently resolved**, and the registered 56-entry dictionary is unchanged. Choosing a number to make a paper agree is explicitly prohibited by Issue #99 §B.2.
- **Cheapest decisive evidence:** the owner's original column schema or an authorized read-only header/shape comparison of the two owner deliveries (UCI `Z-Alizadeh sani dataset.xlsx` vs Mendeley `CAD.xlsx`), reporting only column names/counts and never cell values outside approved scope. That requires its own written authorization; this audit cannot perform it.

### 3.3 Q-07 — the "Exertional CP is constant" claim

**Re-verified in this pass** (`S1`, `SECONDARY_PAPER`, §3 and §4.1 of [Electronics 11(9):1495](https://www.mdpi.com/2079-9292/11/9/1495)):

- §3, after noting the class split: *"(1) Exertional CP feature has the same values on 303 samples. In other words, External CP feature does not contribute to the classification prediction of CAD"*.
- §4.1 *Preprocessing of Data*: *"(1) delete the External CP feature directly; and (2) standardize the continuous features."*

Observations that matter:

1. The claim is about **that paper's downloaded copy**, and the paper does not state which delivery (UCI vs Mendeley) or byte hash it used. It is therefore **not** evidence about our protected source.
2. The same paragraph misspells the field ("External CP"), which is a small but real reliability signal for field-level statements in this literature.
3. The claim is **consistent** with the frozen panel's own redundancy logic but must never *drive* a change: if the column is constant, it carries zero information; that is a finding for a scientific amendment process, not an engineering edit.

**Status: `SECONDARY_CONSTANT_FEATURE_HYPOTHESIS_ONLY` (unchanged).** What would actually test it, on the project's own authorized source and within existing guard rails:

- an **aggregate-only** count, emitted by the authorized local read-only audit chain: number of non-null cells, number of distinct values, and the count per value for the single column `Exertional CP` across the 303 records;
- output restricted to those integers plus the bound source SHA-256 and the audit date — **no row, no identifier, no file excerpt** leaves the local machine;
- a separately written scope agreement, because this is a *new question asked of protected data*, even though the aggregate is coarse.

Any resulting change to panel `uci412_basic_clinical_v1` would require a protocol amendment, a **new panel version**, re-freezing of hashes, and a named human decision. Nothing in this audit proposes such a change.

### 3.4 Q-05 — BP quantity and PR meaning/units; the six binary directions; chest-pain relations

| Item | Registered position (frozen repository) | New evidence this pass | Consequence |
|---|---|---|---|
| `BP` | single numeric, registered mmHg; systolic/diastolic/other, posture, device, timing, operator **unknown** | **None.** Owner metadata has no units or descriptions (verified empty, §3.1) | `UNRESOLVED_SCIENTIFIC_HOLD` unchanged. Must not be mapped onto UCI-45 `trestbps`. |
| `PR` | numeric, registered beats/min; some secondary texts say "ppm"; pulse-rate intention plausible | **None** from owner; the 2022 paper's Table 2 was not read in full | `UNRESOLVED_SCIENTIFIC_HOLD` unchanged. |
| Six binary directions (`DM`, `HTN`, `Current Smoker`, `EX-Smoker`, `FH`, `Typical Chest Pain`) | Numeric `0/1` **representation** verified by the 2026-10-24 local audit (Amendment A-1); `0=absent, 1=present` **provisional**, supported only by a peer-reviewed secondary Table 1 (Tao et al. 2025) | The Tao et al. article page rendered only front matter/figures/references in this pass; **Table 1 was not retrieved**, so the S-9 direction is **not** re-verified here | Direction stays provisional (`S-9` open). Owner codebook or an author statement is required. |
| Chest-pain relations (`Typical Chest Pain` numeric vs `Atypical`/`Nonanginal`/`Exertional CP` textual) | Mutually exclusive vs overlapping **undocumented**; all four kept as delivered | **None** | `UNRESOLVED` unchanged. `Exertional CP` also intersects Q-07 above. |

**Where the missing evidence must come from:** the original owner codebook/collection form, or a written statement from the depositing author. Public metadata, secondary tables and plausibility arguments are not substitutes, and were not treated as such.

### 3.5 Q-04 — pre-angiography acquisition of the 16 predictors

**`0/16` owner-verified pre-angiography acquisition times is preserved.** This audit found no owner document that establishes the decision moment for any predictor:

- The UCI record and the Mendeley description describe *what* the groups contain, never *when* the values were captured.
- The owner's machine-readable field metadata is empty (§3.1).
- The 2013 abstract describes feature effectiveness and a data-mining result, not a collection protocol; it contains no chronology statement.
- Plausibility (history, symptoms and vital signs are *obtainable* before catheterization) remains exactly that — plausibility, not evidence. Retrospective recording and post-result coding cannot be excluded from public documentation.

**Scientific consequence:** the D-047/M3a framing of these 16 fields as pre-procedure inputs rests on clinical plausibility plus an explicit documented limitation, **not** on owner certification. That limitation must continue to be stated in every derived report, and no field may be relabelled `VERIFIED`/`DOCUMENTED_PRE_ANGIOGRAPHY` on the strength of this audit. The validator's hard binding of `UNVERIFIED` timing is untouched.

### 3.6 Cross-source and independence notes (documentation only)

- UCI-411 remains the **same 303 participants** with three angiography-defined artery columns added (owner Note 1, `P1C`); it cannot become an independent cohort and its artery columns remain outcome-definition fields.
- UCI-45 (Cleveland) uses `>50%`-style wording while UCI-412 states `≥50%`; **no threshold equivalence is established** and no pooling or target remapping is proposed here.
- The AngioCAD article's generic background sentence (*"CAD is generally diagnosed when there is >50% blockage in at least one coronary artery"*) is a **textbook framing statement**, not an AngioCAD label definition; it must not be quoted as the dataset's threshold.

### 3.7 Frozen contracts touched: none

Read-only inspection confirmed that the registered dictionary is `uci412_research_feature_dictionary` schema `1.1.0`, status `PROPOSED_NOT_SUPERVISOR_APPROVED`, with **56 registered entries**: 16 `ADMITTED_PRIMARY_PANEL`, 33 `REGISTERED_EXPANDED_PANEL_ONLY`, 3 `EXCLUDED_DERIVED_REDUNDANT` (`Weight`, `Length`, `Obesity`), 3 `EXCLUDED_ECHO_TIMING_UNVERIFIED` (`EF-TTE`, `Region RWMA`, `VHD`), 1 `EXCLUDED_TARGET` (`Cath`). `ai/panels.py` consumes that dictionary and the UCI-45 intake definitions; `research/uci412/source_spec.py` records both the "54 features" owner wording and the "55 predictors plus `Cath`" local observation verbatim and deliberately does not resolve them.

**This audit changed no schema version, no panel, no vocabulary, no admission status, no hash, no threshold and no guard.**

---

## 4. Discrepancies between original sources and repository contracts

| # | Discrepancy | Parties | Status after this audit |
|---|---|---|---|
| D-1 | **54 features (owner)** vs **55 predictors + `Cath` = 56 columns (local)** vs **56 variable rows (UCI UI/API structure)** | `OWNER_METADATA` ×2, `HISTORICAL_LOCAL_AGGREGATE` | **Unresolved.** New arithmetic noted: `54+3≠59` but `56+3=59` (§3.2). No value chosen. |
| D-2 | **59 features (UCI-411)** for "the same 303 patients plus 3 artery columns" | `OWNER_METADATA` | Consistent only under H-56; recorded, not adopted. |
| D-3 | **`num_features: 0`** in the owner API while prose says 54 features and the variable array has 56 blank entries | `OWNER_METADATA` internal | Recorded as a metadata-quality defect of the owner release; it is the reason field-level questions cannot be answered publicly. |
| D-4 | **Two owner deliveries** — `Z-Alizadeh sani dataset.xlsx` (120.7 KB, UCI) vs `CAD.xlsx` (118 KB, Mendeley) | `OWNER_METADATA` ×2 | Recorded. Any count/audit statement must name the delivery. |
| D-5 | **413 patients (abstract/record)** vs **413 videos (Highlights)** vs **n=412 (third-party preprint)** | `OWNER_METADATA`, `OWNER_PAPER_ABSTRACT`, `SECONDARY_PAPER_EXCERPT_ONLY` | Mapping `UNKNOWN_NOT_ESTABLISHED`; none may be adopted as a file-level count. |
| D-6 | **CC BY 4.0 (record)** vs **"non-commercial" (article contribution text)** for AngioCAD | `OWNER_METADATA` vs `OWNER_PAPER_ABSTRACT` | **New unresolved conflict**; needs owner/legal clarification before reuse. |
| D-7 | AngioCAD record links **no** scholarly work; the article's Data-availability note is the only record↔article bridge | `OWNER_METADATA`, `OWNER_PAPER_ABSTRACT` | Recorded; the archive is reachable via the DOI cited in the article, not via a record-side relation. |
| D-8 | **`Exertional CP` reported constant (secondary)** while the frozen panel registers it as an admitted member | `SECONDARY_PAPER` vs frozen contract | Hypothesis only; no contract change; test defined in §3.3. |

---

## 5. Proposed register updates (proposals only — **not applied**)

The RH-02 register JSON is deliberately **not edited** by this PR. If a maintainer accepts this audit, the following text is proposed:

| Question | Current status | Proposed change to `evidence_or_gap` | Status change? |
|---|---|---|---|
| **Q-05** (BP/PR semantics) | `UNRESOLVED_SCIENTIFIC_HOLD` | Add: *"Owner machine-readable field metadata verified empty (UCI API `num_features: 0`, 56 blank variable objects). BP quantity and PR units/conditions therefore cannot be resolved from public metadata; owner codebook or author statement required."* | **No change** — stays `UNRESOLVED_SCIENTIFIC_HOLD`. |
| **Q-07** (Exertional CP) | `SECONDARY_CONSTANT_FEATURE_HYPOTHESIS_ONLY` | Add: *"2022 Electronics §3/§4.1 re-verified: constant across that copy's 303 samples, field then dropped; delivery/hash unspecified; spelling 'External CP' in the same paragraph. Test requires an aggregate-only distinct-value count inside the authorized local read-only chain under separate written scope."* | **No change.** |
| **Q-08** (54 vs 55+Cath) | `OWNER_FILE_VERSION_FEATURE_COUNT_UNRESOLVED` | Add: *"Arithmetic inconsistency recorded: UCI-411 states 59 features for 412+3 artery columns, whereas 54+3=57; the locally observed 56 columns (55+Cath) satisfy 56+3=59. Two owner deliveries exist (UCI 120.7 KB; Mendeley 118 KB). Neither hypothesis adopted."* | **No change.** |
| **Q-14** (AngioCAD) | `MULTIMODAL_PATIENT_SOURCE_SUPPORTED_BY_ABSTRACT_NOT_ADMITTED` | Replace *"record access/schema/rights unverified"* with the verified specifics: *"Zenodo record 15826856 verified: 4 RAR parts (16,401,400,789 B total) + `AngioCAD_Features.xlsx` (129,493 B) + `AngioCAD_Labels.xlsx` (43,267 B); `access_right: open`; `license: CC BY 4.0` conflicting with article's 'non-commercial'; no schema, no data dictionary, no per-file counts, no patient↔video mapping, no pre-angiography chronology, no published patient-level binary CAD definition. Classification: `SCIENTIFIC_HOLD_NOT_ADMITTED`."* | **No change** — still not admitted. |
| Round-2 block `angiocad_source_count_correction` | `record_file_manifest_verified: false`, `original_zenodo_file_manifest_obtained: false` | Propose flipping these two flags to **true** (manifest now read from the public API) while keeping `actual_patient_video_linkage_verified: false` and `new_real_data_access_authorized: false`. | Record-keeping only; **no** scientific state change. |

**Explicitly not proposed:** any new `decision_id`, any change to gate/blocker/status strings, any change to `ai_master_progress.json`, any change to the frozen dictionary, panels, plan or manifests, and any claim of acceptance.

---

## 6. Requirements for human authorization (nothing in this document grants them)

| # | Decision needed | Who |
|---|---|---|
| H-1 | Accept or reject the AngioCAD classification `SCIENTIFIC_HOLD_NOT_ADMITTED` as the project's documented position. | Maintainer + scientific reviewer |
| H-2 | Resolve the **CC BY 4.0 vs "non-commercial"** conflict before any reuse discussion. | Maintainer (+ legal/licensing advice) |
| H-3 | Decide whether to approach the AngioCAD curator with the §2.8 question list, and under what recording/permission terms. | Maintainer |
| H-4 | Decide whether to approach the UCI-412 depositing author with the codebook/timing/direction questions (§3.4, §3.5). | Maintainer |
| H-5 | Authorize — or refuse — a **read-only header/shape comparison** of the two owner deliveries to settle D-1/D-2. This is a new data-reading act and needs its own written scope. | Maintainer, local-only execution |
| H-6 | Authorize — or refuse — the aggregate-only `Exertional CP` distinct-value count (§3.3) inside the existing authorized local chain. | Maintainer |
| H-7 | Confirm that **Gate PT P-3 stays CLOSED**, `P-1` PENDING, `P-5` prohibited, D-046 read-only, D-047 Cleveland-only, and that M3a remains unratified. | Maintainer |
| H-8 | Confirm that **no supervisor, ethics or institutional approval** is implied by, or may be inferred from, this audit. | Maintainer / supervisor |

---

## 7. Validation performed (exact, reproducible)

All checks are documentation-level; no test suite, model, migration or contract was modified, so the behavioural suites are unaffected. Commands were run in this repository at the audited `main` with the two new files present.

| Check | Command | Result |
|---|---|---|
| JSON parses | `python3 -c "import json;json.load(open('docs/research/next_phase/RH02_TECHNICAL_DATASET_METADATA_AUDIT_V1.json'))"` | see §7.1 |
| Structural/schema self-check (stdlib only) | inline validator (§7.1) | see §7.1 |
| Internal source-reference integrity | inline validator: every `source_ids` entry used by a finding exists in `sources`; every `question_updates[].question_id` exists in the register; every URL is `https://` and present in `sources` | see §7.1 |
| Frozen source verification | `python3 scripts/verify_sources.py` | `exit 0` — four SHA-256 source hashes OK; supervisor audit 25 papers (9 green / 1 pink / 6 orange / 9 red) |
| Whitespace/conflict hygiene | `git diff --check` | see PR |
| Patch is documentation-only | `git diff --stat a57220c...HEAD` | exactly 2 added files under `docs/research/next_phase/` |

`jsonschema` is not installed in this environment (`ModuleNotFoundError`), so validation was performed with a **stdlib structural validator** rather than a third-party schema engine. This is a tooling limitation, not a claim of formal schema validation.

### 7.1 Validator results

The validator enforces: required top-level keys; `schema_id`/`version` presence; unique `source_id`/`finding_id`; every finding's `source_ids` resolvable; every `question_updates` target present in the RH-02 register with a **non-changing** status proposal; `angiocad.classification == "SCIENTIFIC_HOLD_NOT_ADMITTED"`; `uci412.owner_verified_pre_angiography_fields == 0`; `authorization_required` non-empty; `frozen_contracts_modified == false`; `patient_data_accessed == false`; `dataset_bytes_downloaded == 0`; and that every relative Markdown link resolves.

**Observed result: 22 / 22 checks passed, exit code `0`.** Notable specifics: 15 sources, 9 findings, 8 discrepancies, 8 authorization requirements, all `applied` flags `false`, all source URLs `https`, all finding→source references resolvable, all Markdown links resolve to existing files. The full pass/fail list is reproduced in the PR description; the same results are recorded in the JSON companion under `validation`.

### 7.2 What these results do **not** mean

Passing JSON/reference checks proves the document is internally consistent and cites what it claims to cite. It proves **nothing** about dataset truth, licence permissibility, scientific validity, clinical validity or readiness.

---

## 8. Recommended next steps (ranked, cheapest-safest first)

1. **Human review of this audit** and of the proposed register text (§5). No file in the existing register should change until a maintainer accepts it — the register's own closing clause requires a named human decision.
2. **Owner-first evidence requests** (zero data access, zero cost): send the §2.8 list to the AngioCAD curator and the §3.4/§3.5 list to the UCI-412 depositing author. These are the only routes that can close Q-05, Q-07 and Q-04 without reading protected records.
3. **Resolve D-6 (licence wording)** before any AngioCAD file is even considered for download; treat "CC BY 4.0" as *declared*, not as an operational permission.
4. **If and only if H-5 is authorized**, run the read-only header/shape comparison of the two owner deliveries locally, emitting column names/counts only — this is the cheapest decisive evidence for Q-08/D-1/D-2.
5. **If and only if H-6 is authorized**, run the aggregate-only `Exertional CP` distinct-value count inside the existing authorized chain, emitting integers + source SHA-256 only.
6. **Keep AngioCAD out of the Track A candidate set**; if the project ever wants an imaging/stenosis research line, scope it explicitly as a *different* task with its own protocol — never as a substitute for pre-procedure tabular CAD classification.
7. **Do not** re-run, re-fit or extend any M3a/D-047 work on the basis of this audit; the scientific holds and the Windows-local authorization chain are unchanged.

---

## 9. Limitations of this audit (read before citing it)

1. **Paywall.** AngioCAD Sections 3–5, tables and any supplement were not readable. Every statement about the AngioCAD *schema*, *field list*, *label construction* and *class balance* is therefore an absence-of-evidence finding, not a negative finding about the dataset itself.
2. **No file was opened.** The XLSX/RAR contents, sheet names, headers, dtypes and row counts are unknown. Filename-based inferences are labelled as such.
3. **One secondary direction source was not re-verified** (Tao et al. 2025 Table 1). The S-9 direction therefore remains exactly as strong — and as weak — as the repository already recorded it.
4. **`S2` (2020 *IJERPH*) was not re-fetched** in this pass; its 216/88 arithmetic contradiction is carried forward from the RH-02 register, not re-derived.
5. **Issue #99 text was not machine-retrievable** (Issues API `403`); the specification used is the maintainer-supplied verbatim text. If the written issue differs materially, this audit's scope must be re-checked.
6. **Metadata is not data.** A record description, a licence field and a file manifest describe what the owner *published*; they do not certify measurement chronology, patient identity, label quality, class balance, missingness or fitness for any modelling purpose.
7. **Secondary sources are not authority.** Where they disagree with owner metadata (counts, features, constancy, class balance) the disagreement is recorded, not adjudicated — third-party reanalyses cannot authenticate source acquisition and cannot override protected local evidence.

---

**Bottom line:** AngioCAD is publicly available, CC-BY-4.0-declared, ships two XLSX tabular files whose schema and chronology are undocumented, and publishes artery-level seven-category stenosis annotations with no defined patient-level binary CAD target — therefore `SCIENTIFIC_HOLD_NOT_ADMITTED`, with a documented licence conflict and a clearly distinct imaging/stenosis research task. UCI-412's owner metadata still provides **no** field-level dictionary, its "54 features" wording remains arithmetically inconsistent with its own "59 features" extension statement unless the delivered file really has 56 columns, and the six binary directions, BP/PR semantics and **all 16** pre-angiography acquisition times remain unverified. Nothing was downloaded, nothing was fitted, no contract changed, and no hold was lifted.
