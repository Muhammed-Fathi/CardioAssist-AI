# 15 — Scientific Evidence Resolution for the Primary CAD Development Route (REVIEW DRAFT)

**Prepared:** 2026-10-24 · **Base:** `main` at merge of PR #49 (`aecf2f3`) · **Revision:** 15.1 (methodological correction) · **Status:** research evidence review for human adjudication. **Not** a protocol, **not** a dataset selection, **not** a training authorisation, **not** a clinical or supervisor approval.

> **P-1 PENDING · Gate PT P-3 CLOSED (no supervisor sign-off exists) · P-5 NOT MADE — prohibited.** D-046 remains read-only local audit; D-047 remains Cleveland-only internal exploratory; D-048/M3a remains UCI-412 internal exploratory. Nothing in this document authorises data access, acquisition, fitting, inference, pooling, external validation, transfer prediction or model artefact creation, and none was performed. No frozen protocol, feature dictionary, registered plan, experiment result or decision-register entry is modified. **No dataset was accessed, downloaded, opened or re-audited for this review**; every number quoted from a data file is either an official-source publication figure or a maintainer-reported aggregate already committed to this repository.

---

## 0. Reading guide

### 0.1 Evidence strength scale used in this document

| Tag | Meaning | Weight |
|---|---|---|
| **[A1]** | **Official source authority** — the dataset owner's own repository metadata, codebook or DOI record, read directly in this pass | Highest for *definitions, coding conventions, licence, stated reference standard* |
| **[A2]** | **Primary publication of the dataset** (the source's originating or officially-declared introductory paper), read directly | High for *protocol, cohort, reference standard, measurement moment* |
| **[A2-p]** | Primary publication, **only partially accessible** (abstract + publisher section preview; tables paywalled) | Indicative only; cannot resolve a blocker |
| **[B1]** | **Author-associated peer-reviewed publication** (same group, same cohort, not the dataset's introductory paper) | Supporting; never authoritative |
| **[B2]** | **Independent peer-reviewed secondary literature** (third-party publication describing the dataset) | Supporting; never authoritative |
| **[L1]** | **Maintainer-reported, authorised, local read-only audit aggregate** already committed to this repository (not re-run here, originals never seen) | Evidence of representation/counts only |
| **[R1]** | **Repository frozen/registered record** — a merged Gate DA/PT document, the registered plan, the versioned feature dictionary, `docs/DECISIONS.md` | Binding project record, not external evidence |
| **[AA]** | **Agent arithmetic**, reproducible from the constants, formulae and outputs recorded in Appendix B | Deterministic; conditional on stated inputs |
| **[SC]** | **Hypothetical scenario input** — an illustrative value chosen only to size an interval (e.g. `AUC = 0.80`). Never a prediction, expectation, baseline or observed result, and never an input to a decision | None; arithmetic illustration only |
| **[INF]** | **Inference** drawn from cited facts — explicitly not a verified fact | Lowest; must not be promoted to evidence |
| **[GAP]** | **Not found / not accessible / does not exist publicly** — must not be filled by assumption | Blocks resolution |

A blocker is marked **RESOLVED** only where an [A1] or [A2] source *directly* answers the question **at the level named**. Where the only supporting evidence is [B1], [B2], [L1] or [INF], the status is **CONDITIONALLY RESOLVABLE** (a named human acceptance or a named bounded step is required) or **UNRESOLVED**.

Two corollaries are binding in revision 15.1:

1. **A documentation-level resolution is not a record-level verification.** A source that documents what a *protocol* or *codebook* says does not verify what a *delivered file* contains, nor how any individual record was measured or coded. Statuses below are therefore explicitly level-qualified — e.g. "RESOLVED — documentation level; delivered-file equivalence UNVERIFIED".
2. **Evidence *consistent with* a claim is not evidence *of* it.** Concordant aggregate counts, plausible code directions and clinical plausibility are corroboration. They do not by themselves establish semantics, identity or equivalence, and are never promoted to `RESOLVED` on that basis.

### 0.1.1 Where each requested deliverable lives

| Requested deliverable | Section |
|---|---|
| Source-by-source evidence traceability | **§2** (table) + **Appendix A** (verbatim strings) |
| Blocker resolution matrix | **§5** (per-blocker full records in **§3** and **§4**) |
| Development-route decision matrix | **§7** |
| Feasibility of a future independent assessment | **§6** |
| Proposed primary research direction and fallback | **§8** |
| Smallest next research/engineering implementation step | **§9** |

### 0.2 What was actually read, and at what depth

| Source ID | Source | Depth in this pass |
|---|---|---|
| SRC-01 | [UCI-45 Heart Disease landing page](https://archive.ics.uci.edu/dataset/45/heart+disease) (both chunks) | **Read in full** |
| SRC-02 | [`heart-disease.names`](https://archive.ics.uci.edu/ml/machine-learning-databases/heart-disease/heart-disease.names) (David Aha, July 22 1988) | **Read in full** (both chunks) |
| SRC-03 | [UCI-412 Z-Alizadeh Sani landing page](https://archive.ics.uci.edu/dataset/412/z+alizadeh+sani) | **Read in full** (single chunk) |
| SRC-04 | [UCI-411 extension landing page](https://archive.ics.uci.edu/dataset/411/extention+of+z+alizadeh+sani+dataset) | **Read in full** |
| SRC-05 | Detrano R, Jánosi A, Steinbrunn W, Pfisterer M, Schmid J-J, Sandhu S, Guppy KH, Lee S, Froelicher V. *International application of a new probability algorithm for the diagnosis of coronary artery disease.* Am J Cardiol 1989;64(5):304–310. doi:10.1016/0002-9149(89)90524-9 | **Full-text PDF read**: abstract, Methods, Table I, Table II, all three test-group descriptions (chunks 0–1 of 5). Results/discussion read in part |
| SRC-06 | Alizadehsani R *et al.* *A data mining approach for diagnosis of coronary artery disease.* Comput Methods Programs Biomed 2013;111(1):52–61. doi:10.1016/j.cmpb.2013.03.004 | **[A2-p] — abstract + publisher "section snippets" only. Table 1 (per-feature ranges/units) NOT accessible; full text paywalled** |
| SRC-07 | Alizadehsani R, Habibi J, Hosseini MJ, Boghrati R, Ghandeharioun A, Bahadorian B, Alizadeh Sani Z. *Diagnosis of coronary artery disease using data mining techniques based on symptoms and ECG features.* Eur J Sci Res 2012;82(4):542–553 | **Indexed full-text rendering read** (dataset section, Tables 2, 4, 6, 7 and their captions). Not a paginated publisher PDF |
| SRC-08 | Tao H *et al.* *A real-time computer-aided diagnosis system for coronary heart disease prediction using clinical information.* Rev Cardiovasc Med 2025;26(3):26204. doi:10.31083/RCM26204 | **Not re-read here.** Its Table 1 reading is recorded in [doc 10 §3.1 / E-1](10_m3a_uci412_source_encoding_AMENDMENT_A1.md). The article page was reached, but the table was not re-extracted in this pass |
| SRC-09 | Repository records: Gate DA 01–17, Gate PT 01–14, `docs/DECISIONS.md`, `docs/FEATURE_REGISTER.md`, the registered UCI-412 plan, feature dictionary 1.1.0, `research/intake/**` | **Read/queried as needed** (see per-section citations) |
| SRC-10 | Maintainer-reported local audit aggregates (`gate-da/10` §§2–3, `gate-da/11`, `gate-da/14`, `gate-pt/10` §1) | **Read**; originals and protected reports not seen **[GAP]** |
| SRC-11 | Riley RD *et al.* BMJ 2020;368:m441; Stat Med 2021 (sim.8806, sim.9025) as verified in [doc 05 §0.6](05_m2e1_sample_size_research_ADEQUACY_REVIEW_DRAFT.md) | **Not re-read**; relied on the repository's recorded verification |

### 0.3 Verification boundary — what this document deliberately did not do

- **No patient-level access.** No workbook, no `.data` file, no archive and no protected local report was downloaded, opened, parsed or summarised. The UCI-411 download link and the UCI-412 workbook were **not** fetched. The two ResearchGate/other pages surfaced by search that reproduce individual record rows were **not** used as evidence and no row is quoted anywhere here.
- **No training, inference, pooling, transfer or artefact creation.** This revision adds **no executable artefact**; the only computation is arithmetic on published counts, recorded step by step in Appendix B.
- **GitHub issue bodies could not be re-read**: `gh issue view` returned *GraphQL: Resource not accessible by integration (repository.issue)* for #15, #20, #21, #29 and #37. Their states are therefore taken from the merged documents and are **not** independently re-verified here **[GAP]**.
- **No dataset file, archive member, workbook sheet or bundled documentation was inspected.** Every statement about *file-level* coding, column order, value domains or missing tokens rests on a maintainer-reported audit **[L1]** and is labelled unverified wherever it matters.
- **Sani per-variable documentation — bounded statement.** Both UCI landing pages were read in full and their published **variable tables are empty** (SRC-03: 56 rows, "0 to 10 of 56", every cell blank; SRC-04: 59 rows, same). Each page also links a "full documentation" item that lives **inside the dataset archive**; under the current authorisation that archive was **not** opened, and the introductory paper's variable table is paywalled (SRC-06). The defensible statement is therefore: **no per-variable documentation was found in the materials actually examined** — the two public landing pages, the accessible text of the introductory paper, and the author-associated 2012 paper. This document does **not** claim that no such documentation exists anywhere, and does not treat an empty landing-page table as proof of absence.
- Public, offline documents can resolve *definitions and stated protocols*. They cannot certify per-record acquisition times, per-record label correctness, patient independence, or clinical transportability. Every status below is written to that limit.

### 0.4 Files changed by this document

| File | Change | Status |
|---|---|---|
| `docs/research/gate-pt/15_scientific_evidence_resolution_and_development_route_REVIEW_DRAFT.md` | **new** (rev. 15.0), **corrected** (rev. 15.1) | This report |
| `docs/research/gate-pt/README.md` | edited | Index entry for document 15 |
| `scripts/verify_pt15_precision_scenarios.py` | **added in 15.0, REMOVED in 15.1** | A deterministic-arithmetic helper was added in the first revision as a *proposed* scope extension. No explicit maintainer approval for that extension was recorded, so under this correction pass's stated scope the script is **deleted**, and Appendix B is the complete reproduction record (all constants, formulae, worked arithmetic and outputs). If a maintainer later approves a deterministic-arithmetic scope extension explicitly, Appendix B can be re-instantiated verbatim |

### 0.4.1 Revision history

| Revision | Date | Change |
|---|---|---|
| 15.0 | 2026-10-24 | First issue of this review (evidence resolution + route recommendation), plus a *proposed* arithmetic helper script |
| **15.1** | **2026-10-24** | **Methodological correction pass requested in the PR #50 review.** (a) External-validation precision interpretation corrected: Riley-2020/`pmsampsize` development criteria, descriptive binomial precision and Riley-2021 external-validation criteria are separated, and no figure is presented as a sufficient or definitive external-validation threshold. (b) AUROC uncertainty attributed to Hanley–McNeil only; the DeLong attribution is removed and the "actual intervals must be wider" claim is replaced by "width may differ in either direction". (c) Hungary conclusions level-qualified: documentary findings retained; record-level equivalence, per-record timing, person-level independence and the 294-of-425 relationship are **not** asserted. (d) UCI-412 evidence language bounded: no "negligible probability" claim, no codebook-absence claim beyond the materials examined, clinical plausibility not used as proof. (e) Route/readiness language tightened: Route A′ is provisional; no readiness or adequacy adjudication is implied; independent external validation is distinguished from a clinically validated deployable model. (f) The arithmetic script is removed and Appendix B made self-contained. **No gate, decision, protocol, dictionary or data status changed.** |

**Deliberately unchanged:** `docs/DECISIONS.md`, `AGENTS.md`, `research/uci412/**` (plan and dictionary 1.1.0 byte-identical), `research/intake/**`, `research/audit/**`, `research/experiments/**`, every Gate DA/PT document 01–14, `.github/**`, and all backend/frontend/contract code. **No decision-register entry was added because no decision was taken.**

---

## 1. Executive answer

**The evidence now supports a research direction, and it does not support a clinical one.**

1. **Four Hungary-side questions gained `RESOLVED — documentation level` components,** each on a direct [A1]/[A2] citation rather than on inference: (a) the codebook-level target convention (`num` 0 vs 1–4) and the cohort's class counts, (b) five-field source definitions and units as a *shared instrument*, (c) the missing-value convention (sentinel) and the audited quantity, and (d) the **protocol-level** measurement moment relative to angiography ("within 6 weeks before the date of the coronary angiogram"). **Each carries an explicit level qualifier.** None of them verifies what the delivered Hungarian file contains record-by-record, and none establishes person-level independence (§4).
2. **The two decision-relevant UCI-412 questions did not resolve.** **No per-variable documentation was found in the materials examined** (both public landing pages have empty variable tables; the introductory paper's table is paywalled; the archive's own documentation was not opened). `BP` quantity, `PR` unit, chest-pain elicitation definitions and per-field timing therefore cannot be settled from authority. Only `BP` and `PR` narrowed, and only to *author-associated* supporting evidence. UCI-412 per-field timing is **UNRESOLVED**.
3. **The exact-50 %-stenosis question is `NO-GO` as framed**: neither release retains a per-record stenosis percentage, so no evidence could ever decide it. It must be *dispositioned* ("related-but-not-identical"), not *resolved*.
4. **UCI-411 can never be an independent assessment of UCI-412** [A1], and **no second Z-Alizadeh-Sani-style cohort was identified anywhere in this project's source inventory**. The sixteen-field route therefore has **no route to an honest independent evaluation with the evidence the project holds today** — a bounded finding about this inventory, not proof that no such cohort exists publicly.
5. **Recommendation for human review — not taken here, and provisional:** the preferred next **research** direction is a **source-specific, Cleveland-derived five-field research line with a preserved, untouched one-shot Hungary site-shift assessment as its conditional second stage** (Route A′), on documentation-level grounds and with an explicitly descriptive/feasibility framing. The **UCI-412 sixteen-field route is recommended `HOLD` as a development route** while remaining a documented internal *methods* benchmark. The **fallback** is a narrower research-only/methods contribution (Route C) if P-1/P-3, the adequacy ruling or the Hungarian precision adjudication fail. **This is a working recommendation, not a selection, not a readiness finding, and not an adequacy adjudication:** documentation does not confer external validity, and the best that stage 2 could ever produce is a single-site descriptive transportability estimate for one locked model — **not** a clinically validated or deployable model (§6.4).
6. **Precision language, corrected.** The arithmetic in §4 H-6 and Appendix B is **descriptive binomial outcome-proportion precision**. It is **not** a Riley-2021 external-validation sample-size determination; the figure 355 is **not** an external-validation threshold, a sufficiency criterion or an approval, and no precision question is adjudicated here. A Riley-2021 determination requires a named locked model plus prespecified estimands and tolerances, none of which exists.
7. **Nothing here selects a dataset, opens P-3, or authorises work.** The smallest next step proposed (§9) is one documentation/decision act plus, only under separate authorisation, one aggregate-only read-only reconciliation of counts for files the project has already audited.

**Explicit prohibition repeated:** the Cleveland `0.8271` and UCI-412 `0.9107` internal exploratory AUROCs are **incomparable and were not used, directly or indirectly, in any judgement in this document**. They appear nowhere in the route matrix. Route preference is argued from *semantics, timing, target validity, evaluability and reproducibility only*; sample size is reported for all three routes and, being weak for all of them, contributes **no** preference.

---

## 2. Source-by-source evidence traceability

Each row states exactly what the source **does** and **does not** establish. Quotations are verbatim from the retrieved text (Appendix A collects them).

| ID | Source / locator | Verified content (what it supports) | What it does **not** support |
|---|---|---|---|
| SRC-01 | UCI-45 landing page, retrieved 2026-10-24 | "4 databases: Cleveland, Hungary, Switzerland, and the VA Long Beach"; headline `# Instances 303`, `# Features 13`; "Has Missing Values? Yes"; **Introductory Paper = Detrano et al. 1989**; variable table gives `trestbps` = "resting blood pressure (on admission to the hospital)", unit "mm Hg"; licence CC BY 4.0; DOI 10.24432/C52P4X | Does not give per-site counts, per-file coding, missing-value distribution, or per-record timing. The `303` headline is the Cleveland benchmark, not the four-site total |
| SRC-02 | `heart-disease.names`, July 22 1988, retrieved 2026-10-24 | "This directory contains 4 databases… 1. Cleveland Clinic Foundation… 2. Hungarian Institute of Cardiology, Budapest…"; "Each database has the same instance format… 76 raw attributes, only 14 … actually used"; "One file has been 'processed', that one containing the Cleveland database"; **§9: "Missing Attribute Values: Several. Distinguished with value -9.0."**; **§10 class distribution by site**: Cleveland 164/55/36/35/13 = 303, **Hungarian 188/37/26/28/15 = 294**, Switzerland 8/48/32/30/5 = 123, Long Beach VA 51/56/41/42/10 = 200; `cp` 1–4 definitions; `restecg` 0–2 definitions; `sex` 1 = male / 0 = female; `trestbps` = resting BP "in mm Hg on admission to the hospital"; **attribute 37 `trestbpd` "resting blood pressure"** (diastolic sibling); `num` = "angiographic disease status", "**Value 0: < 50 % diameter narrowing / Value 1: > 50 % diameter narrowing** (in any major vessel: attributes 59 through 68 are vessels)"; attributes 20–22 = month/day/year of exercise ECG, 55–57 = month/day/year of cardiac cath | Does not document the meaning of `num` = 2, 3, 4; does not state which site's records were selected for release; does not give per-site missingness; dates the documentation to 1988, before the 1989 publication |
| SRC-03 | UCI-412 landing page, retrieved 2026-10-24 | 303 instances; "Each patient could be in two possible categories CAD or Normal. A patient is categorized as CAD, if his/her **diameter narrowing is greater than or equal to 50 %**, and otherwise as Normal."; "Has Missing Values? No"; 54 features in four groups; donors Alizadehsani / Roshanzamir / Sani; CC BY 4.0; DOI 10.24432/C5Q31T; **the Variables Table has 56 rows and every row is blank** ("0 to 10 of 56") | **No per-variable name, description, unit, type or coding appears in the published table.** No timing statement. No collection-era statement. No missing-value mechanism. *(Bounded: this describes the materials examined — the landing page itself. It does not establish that supplementary documentation is absent from the distributed archive, which was not opened.)* |
| SRC-04 | UCI-411 landing page, retrieved 2026-10-24 | 303 instances, 59 features, no missing values, CC BY 4.0, DOI 10.24432/C5461K; same ≥50 % CAD definition; "Note 1: In this extension LAD, LCX, and RCA features have been added. CAD (Last column in dataset) happens when at least one of these three arteries is stenotic. To use this dataset only one of the LAD, LCX, RCA or Cath (Result of angiography) must be in dataset…"; **Variables Table also blank** (59 rows) | Does not state that UCI-411 is an independent cohort (it is an extension of the same 303); no per-field coding; no timing. *(Same bounded scope as SRC-03.)* |
| SRC-05 | Detrano 1989, full-text PDF, retrieved 2026-10-24 | Cleveland derivation cohort = **"303 consecutive patients referred for coronary angiography at the Cleveland Clinic between May 1981 and September 1984"**, exclusions (prior MI, valvular/cardiomyopathic disease), all had history, physical examination, resting ECG, cholesterol, FBS "as part of their routine evaluation"; "Historical data were recorded and coded without knowledge of noninvasive or angiographic test data"; "The 4 clinical variables were age, sex, chest pain type (typical anginal, atypical anginal, nonanginal, asymptomatic) and **systolic blood pressure**"; resting ECG "classified as (1) normal; (2) ST-T-wave abnormality …; or (3) probable or definite left ventricular hypertrophy by Estes' criteria"; dependent variable = "presence or absence of a **> 50 % diameter narrowing**"; **test groups = 200 Long Beach VA (1984–1987), 425 Hungarian Institute of Cardiology (1983–1987), 143 Swiss (1985)**; "Patients with prior infarction or valvular disease were excluded"; "**Clinical data and noninvasive test results were recorded before (and therefore without knowledge of) the coronary angiography results**"; test-group data "included age, sex, chest pain characteristics (as seen earlier), **systolic blood pressure at rest**, history of hypertension, smoking history, history of diabetes, family history, **electrocardiogram at rest**, serum cholesterol and fasting blood sugar"; "Coronary angiograms were considered abnormal if there was **> 50 % luminal narrowing of any major epicardial vessel**. **Histories, physical examinations and all noninvasive tests were performed within 6 weeks before the date of the coronary angiogram**"; "**workup bias or angiographic referral bias was present**" in test groups; Table I Hungary: n = 425, age 48, 71 % men, 38 % disease, SBP 132; Cleveland: n = 303, age 54, 68 % men, 46 % disease; "angiograms were read by **visual assessment** of the percent diameter narrowing" | Does not state which 294 of the 425 Hungarian patients were released to UCI; does not give per-record dates; does not define `cp`/`restecg` codes as delivered in the files (the file codebook does); does not give `num` severity grades |
| SRC-06 | Alizadehsani 2013 (CMBP), **partial** | "a dataset called Z-Alizadeh Sani with 303 patients and **54 features**"; "constructed from the information provided by **303 random visitors** to Shaheed Rajaei Cardiovascular, Medical and Research Center. **216 samples had CAD** and the rest were healthy"; "Table 1 presents the features … along with their valid [ranges]" | **[GAP]**: Table 1 itself (per-feature ranges/units/definitions) was not retrievable; **no timing statement is present in the accessible text**; no coding vocabulary; no chest-pain definition or exclusivity statement |
| SRC-07 | Alizadehsani *et al.* 2012 (EJSR), author-associated | "Information was gathered from Shaheed Rajaei Cardiovascular, Medical and Research Center, **between Fall 2011 and Winter 2012**"; **Table 2**: "BP (Blood Pressure) 90–190"; "PR (Pulse Rate) 50–110"; symptom/exam fields are *separate Yes/No items* — Edema, Weak Peripheral Pulse, Lung Rales, Systolic Murmur, Diastolic Murmur, **Typical Chest Pain**, Dyspnea, Atypical, Non-Anginal CP, Exertional CP, Low Th Ang — with Functional Class 1–4 as the only ordinal symptom item; **Table 4** derived levels: "BP2 BP<90 / 90≤BP≤140 / BP>140" and "PR2 PR<60 / 60≤PR≤100 / PR>100"; **Table 7**: "the number of patients with **value 1** for these features and their confidences" — Typical Chest Pain **164** (0.939024), DM **90** (0.888889), FH **48** (0.75), DLP 112, Dyspnea 134, Atypical 93 (0.430108), Obesity 211, T Inversion 90, BP2 48 | Not the dataset's introductory paper; a lower-tier journal; gives **ranges and derived cut-points, not the measured quantity**; does not state "systolic"; does not state measurement conditions, rest, arm, averaging, or timing relative to angiography; confidence values are association-rule confidences, not validated probabilities |
| SRC-08 | Tao 2025 (as recorded in doc 10) | Table 1 states `True = 1; false = 0` for the six numeric-binary attributes and, consistently, `Male = 1; female = 0` and `Yes = 1; no = 0` for the text binaries | Third-party secondary source; says nothing about the delivered workbook's cell types, spellings, or units; **not an official codebook** |
| SRC-09 | Repository records | Frozen target conventions (`num` 0 vs 1–4; `Cath` Cad vs Normal), the 16-column panel and 5-field panel, the six compatibility blocker families, the eight independent-assessment prerequisites, the "no pooling / no cross-dataset AUROC comparison" rules, and the registration of S-1…S-9 / H-01 / L-03 | Project policy, not external evidence; several of its "UNRESOLVED" entries are the objects this document re-examines |
| SRC-10 | Maintainer-reported audit aggregates | UCI-412: 303 rows, 55 predictors + `Cath`, 216 `Cad` / 87 `Normal`, 0 detected missing cells, 0 exact duplicates, local SHA-256 recorded; UCI-411: 303/303 shared-column row agreement, one unresolved `Cath`/artery discordance (Issue #15); UCI-45 Hungary: 294, 782 missing cells, five-field bundle present in 292/294, `ca` missing 291/294, 1/294 positional raw↔processed row agreement but 293/294 order-independent profile match; six numeric-binary column value counts (DM 213/90, HTN 124/179, Current Smoker 240/63, EX-Smoker 293/10, FH 255/48, Typical Chest Pain 139/164) | Aggregates only; not independently reproduced here; do not prove clinical validity, per-record correctness or timing |
| SRC-11 | Riley 2020 / Riley 2021 | The binary-outcome sample-size framework and the external-validation precision framework, with the recorded caveat that the R²-dependent criteria need an *anticipated* R² that does not exist without a locked model | Provides no project-specific parameters and no verdict |

---

## 3. UCI-412 unresolved semantics — question-by-question resolution

### U-1 · `BP` — measured quantity and unit (residual item **S-2**)

- **Exact scientific question.** Is the delivered `BP` value a systolic pressure, a diastolic pressure, or an unspecified single auscultatory reading, and in what unit — and may it be treated as the blood-pressure input of a clinical intake?
- **Existing evidence.** Registered dictionary: `unit: "mmHg"` with `SECONDARY_SOURCE_UNVERIFIED`; `uncertainty:` "Whether this is systolic, diastolic, or a single recorded value is not stated in the official source" **[R1]**; doc 09 S-2 ("probably systolic-only") and doc 14 row 10 (must not be mapped to `trestbps`) **[R1]**.
- **Newly verified.** (i) **[A1]** The UCI-412 published variable table is **empty** (56 rows, no content), so no owner statement of quantity or unit was found in the materials examined (SRC-03); the archive's own documentation was not opened. (ii) **[B1]** The author group's 2012 paper gives the observed domain **90–190** and derives *systolic-style* bands `BP<90 / 90≤BP≤140 / BP>140` (SRC-07). **[INF]** A diastolic reading spanning 90–190 with 140 as the "high" cut-point would be physiologically unusual; that is a plausibility argument, **not a documented fact**, and it is not treated as proof. (iii) **[A2-p]** The 2013 introductory paper's Table 1, which would carry the authoritative description, is not accessible (SRC-06). (iv) **[B2]** Independent secondary tables repeatedly describe a single "Blood Pressure (mmHg)" with the same 90–190 range.
- **Strength and limitations.** The *unit* claim is now supported by two independent lines and by the numerical domain; the *quantity* claim (systolic) rests on a scale argument and on an author-associated publication — **not** on an owner statement. A single-value systolic-only field cannot be converted to a systolic/diastolic pair, and its measurement conditions (rest, arm, repeat measurement) are undocumented at every level.
- **Status: `CONDITIONALLY RESOLVABLE`.** Two named paths exist: (a) obtain the CMBP full text's Table 1 through institutional access or interlibrary loan; (b) a written clarification from the dataset owners (Alizadehsani / Roshanzamir / Sani). Neither is available to this agent, and no public codebook exists to consult.
- **Action enabled.** None that changes the registered panel. **What the evidence forbids** is now sharper: `BP` must not be described as systolic in any report, must not be mapped to `trestbps`, and must not be used in a cross-source blood-pressure comparison. A prespecified sensitivity analysis that excludes `BP` becomes a defensible requirement for any future UCI-412 protocol.
- **Residual approval/validation.** Human acceptance of the residual ambiguity (as already framed in doc 09 S-2); owner or full-text confirmation before any clinical-meaning claim.

### U-2 · `PR` — measured quantity and unit (residual item **S-3**)

- **Exact scientific question.** Is `PR` a pulse rate in beats per minute, and is the source notation "ppm" (pulses per minute) a unit or something else?
- **Existing evidence.** Dictionary `unit: "beats/min"` with `SECONDARY_SOURCE_UNVERIFIED`; the source table's notation "ppm" recorded verbatim; plausibility guard `[20, 250]` **[R1]**.
- **Newly verified.** (i) **[A1]** No owner unit statement was found in the materials examined (SRC-03 empty table; archive documentation not opened). (ii) **[B1]** The author group's 2012 table gives `PR` domain **50–110** with derived bands `PR<60 / 60≤PR≤100 / PR>100` (SRC-07), i.e. the familiar adult resting-pulse bands. **[INF]** Those bands make "pulses per minute" the coherent reading of "ppm" and make a *parts-per-million* reading implausible on domain grounds; again this is an inference from the published ranges, not an owner statement.
- **Strength and limitations.** The *dimension* (count per minute) is effectively settled by the domain and the standard bands; the *unit token* remains owner-unconfirmed; whether the measurement is resting, averaged, or device-derived is undocumented. `PR` has **no UCI-45 counterpart**, so it cannot participate in any cross-source comparison regardless of resolution.
- **Status: `CONDITIONALLY RESOLVABLE`** (same two paths as U-1).
- **Action enabled.** A future UCI-412 protocol may register `PR` as "pulse rate, count·min⁻¹, source unit token unverified, no conversion", with a plausibility guard — which is what the dictionary already does. No clinical interpretation ("tachycardia", "bradycardia") may be attached to it.
- **Residual.** Owner confirmation; prespecified statement that `PR` is not transportable to any Cleveland-family model.

### U-3 · Direction and clinical meaning of the six numeric-binary fields (residual item **S-9**)

- **Exact scientific question.** Do numeric `0` / `1` in `DM`, `HTN`, `Current Smoker`, `EX-Smoker`, `FH`, `Typical Chest Pain` mean **absent/false** and **present/true**, respectively?
- **Existing evidence.** Human-executed, SHA-256-verified read-only audit of all 303 records establishes the **representation** (numeric only, no blanks, no text) **[L1]**; direction registered as `PROVISIONAL_DIRECTION_STATED_BY_PEER_REVIEWED_SECONDARY_LITERATURE_NOT_OFFICIAL_CODEBOOK` with Tao 2025 Table 1 as the secondary source **[B2]/[R1]**; the amendment's aggregate counts (213/90, 124/179, 240/63, 293/10, 255/48, 139/164) **[L1]**.
- **Newly verified — corroboration (not proof).** **(a) Count concordance.** Three audited aggregate counts match, jointly and exactly, the counts the dataset's author group publishes in its own 2012 paper for "the number of patients with **value 1**": `DM` 90 = 90, `FH` 48 = 48, `Typical Chest Pain` 164 = 164 (SRC-07 Table 7 vs SRC-10 §1) **[B1]+[L1]**. That three independent columns should agree to the unit, simultaneously, under an inconsistent reading is *unlikely a priori*, but **no probability statement is made and none should be inferred**: the comparison is between two published aggregates whose derivation, inclusion rules and counting basis are not documented, so it is **corroborating evidence, not proof of code semantics**. What it does support is narrower and still useful: the delivered workbook's value-`1` group is numerically the same group the authors count as `1`.
  **(b) Direction consistency (explicitly not proof).** The same table reports association confidences `P(CAD | value = 1)`: `Typical Chest Pain` 0.939024 in 164 patients, `DM` 0.888889 in 90 patients. Combined with 216 positives in 303 records these imply that the value-`1` group is the higher-CAD-frequency group (≈154/164 and ≈80/90 positives, versus ≈44 % and ≈64 % in the complementary groups). The registered reading (1 = present) is therefore **consistent with** the reported frequencies, and the inverted reading is **harder to reconcile** with them. **This is an internal-consistency check, not a validation:** it assumes the reported confidences are accurate, it reuses aggregates, and it rests on the clinical expectation that these risk factors are positively associated with angiographic CAD. **Clinical plausibility is not evidence of coding direction** and is not used here as proof. Under the binding rules of §0.1, consistent evidence is not evidence *of* a claim.
- **Strength and limitations.** The combined evidence is now: (i) an audited numeric representation **[L1]**; (ii) a peer-reviewed third-party statement of direction **[B2]**; (iii) exact aggregate count concordance with the authors' own publication **[B1]+[L1]**; and (iv) directional consistency with the authors' reported conditional frequencies **[B1]**. It remains **secondary/author-associated corroboration, not dataset-owner coding documentation**; it speaks to column semantics at cohort level, not to each record; and it says nothing about the defining clinical criteria (duration, treatment status) of "diabetes", "hypertension" or "family history", which are undocumented in every source examined.
- **Status: `CONDITIONALLY RESOLVABLE`** — supported by peer-reviewed secondary literature *and* corroborated by the authors' own published counts and conditional frequencies, but **not resolved**, because none of that is owner coding documentation and none of it is record-level. Explicit human acceptance of S-9 remains required before any real-data run **[R1]**, and the dictionary's `PROVISIONAL_DIRECTION_STATED_BY_PEER_REVIEWED_SECONDARY_LITERATURE_NOT_OFFICIAL_CODEBOOK` status remains accurate and unmodified.
- **Action enabled.** A human may accept S-9 provisionally with a materially better-documented basis. The dictionary's `semantic_uncertainty` text stays accurate; **no dictionary edit is made here**, and any change would be a new schema version and a new review.
- **Residual.** Owner coding documentation (none found in the materials examined) or written owner confirmation; acceptance decision by a named human.

### U-4 · Text-binary vocabulary and `Sex` coding (residual item **S-1**)

- **Exact scientific question.** Which exact text tokens occur in `Sex`, `DLP`, `Atypical`, `Nonanginal`, `Exertional CP`, `Dyspnea`, what do they mean, and is `Sex` coded male = 1?
- **Existing evidence.** Registered vocabularies: `Sex` {`Male`→1, `Fmale`→0, `Female`→0}; the other five {`Y`/`Yes`→1, `N`/`No`→0}, all `SECONDARY_SOURCE_UNVERIFIED` **[R1]**. Doc 10 records that the 2026-10-24 audit found these six columns contain "303/303 registered values" **[L1]**.
- **Newly verified.** (i) **[A1]** No owner vocabulary was found in the materials examined (empty variable table, SRC-03; archive documentation not opened). (ii) The audit statement in doc 10, read strictly, means **every one of the 303 cells in each of the six columns was accepted by the registered vocabulary** — i.e. the *fail-closed risk of an unregistered token* is already excluded for the twelve admitted categorical columns **[L1]/[R1]**. (iii) **[B1]** The 2012 author paper's symptom table lists these fields as plain **Yes/No** items (SRC-07), and `Sex` is described as male/female. (iv) **[B2]** Independent secondary sources and multiple independent public code bases report the delivered workbook spells the female token **`Fmale`**; that token is in any case already registered, so the practical risk is mis-*interpretation*, not adapter failure.
- **Strength and limitations.** The *coverage* question is answered at [L1] level. The *token inventory* (which of the registered tokens actually occur, and how often), and the header spellings of the 43 non-admitted columns, are **not recorded anywhere in the repository**. `Sex` direction rests on [B2] (Tao 2025) plus naming and demographics — a typo-tolerant token ("Fmale") is itself evidence that the column semantics are "male / (mis-spelled) female" rather than anything else, but that is **[INF]**, not proof.
- **Status: `CONDITIONALLY RESOLVABLE`** — and cheaply: a token-frequency inventory (counts only, no rows) can be produced from the **same already-audited file under the existing D-046 read-only scope** and registered as a dictionary addendum. No new acquisition, no new access class.
- **Action enabled.** A vocabulary *inventory* addendum would let a future protocol state "the delivered tokens are exactly X, Y; no others occur" instead of "the registered set covers them". Until then, `Sex` must be described as "recorded sex, source token unverified".
- **Residual.** Human registration of the inventory; explicit statement that no crosswalk to UCI-45 `sex` 0/1 is made (concept overlap only).

### U-5 · Chest-pain indicator definitions and exclusivity (residual item **S-4**)

- **Exact scientific question.** (a) What clinical definition was used for each of `Typical Chest Pain`, `Atypical`, `Nonanginal`, `Exertional CP`? (b) Are they mutually exclusive, i.e. does each patient carry exactly one descriptor?
- **Existing evidence.** Doc 09 S-4: mutual exclusivity "never examined"; panel registers all four as separate binaries with "no post-hoc collapsing" **[R1]**; doc 07 §7.2 records that Cleveland's single 4-category `cp` has **no** valid mapping to these flags **[R1]**.
- **Newly verified.** (i) **[A1]** No owner definition was found in the materials examined (empty variable table; archive documentation not opened). (ii) **[A2-p]** The introductory paper names `Typical Chest Pain` as the single most informative feature but its Table 1 is not accessible. (iii) **[B1]** The authors' 2012 paper presents all four as **separate Yes/No items**, alongside `Dyspnea`, `Low Th Ang` and `Functional Class` (SRC-07 Table 2) — i.e. the source structure is a **set of independent symptom flags**, not one categorical variable with mutually exclusive levels. That is documentation of *structure*; it does not prove the flags are statistically independent, and nothing in the accessible literature states the elicitation definitions (which chest-pain characteristics count as "typical").
- **Strength and limitations.** The exclusivity question is answerable **only** by counting the joint distribution of the four flags — a strictly aggregate, read-only operation on the already-audited file. The *definition* question is not answerable from any accessible source; it would require the source questionnaire or owner clarification.
- **Status: `UNRESOLVED` for definitions (U-5a); `CONDITIONALLY RESOLVABLE` for exclusivity (U-5b)** via a four-way joint-count audit (counts only).
- **Action enabled.** A future UCI-412 protocol must state that the four chest-pain fields are *source-recorded flags of undocumented elicitation* and must not be interpreted as an angina classification (no "typical angina vs atypical angina" claim, no mapping to `cp` 1–4). The joint-count addendum would let a protocol state whether the flags overlap and by how much — which changes *interpretation*, not the registered panel.
- **Residual.** Owner/source questionnaire for definitions; human adjudication of the joint-count evidence.

### U-6 · Per-feature measurement timing relative to angiography

- **Exact scientific question.** For each of the 16 panel columns, was the value recorded **before** coronary angiography, and at what clinical moment?
- **Existing evidence.** `availability_at_decision_time: EXPECTED_AVAILABLE_BEFORE_ANGIOGRAPHY` is recorded as workflow inference, not source fact **[R1]**; doc 07 §7.4 / doc 11 §7.4: "Neither released source carries per-record measurement dates… timing **NOT ASSESSED**" **[R1]**; the ECG/echo/laboratory panels are `REGISTERED_BLOCKED` precisely because their timing is undocumented **[R1]**.
- **Newly verified.** **[A1]** The UCI-412 page carries **no timing statement whatsoever** (SRC-03). **[A2-p]** The accessible text of the introductory paper contains no timing statement either — only that records come from "303 random visitors" to a cardiovascular centre (SRC-06). **[B1]** The author group's 2012 paper gives the collection window (Fall 2011 – Winter 2012) but **no** relation to catheterisation (SRC-07). No independent source located states that features were recorded pre-angiography. The cohort is angiography-referred by construction (the label *is* the catheterisation result), and it includes ECG/echo/laboratory variables that a hospital may well record during the same admission as the procedure.
- **Status: `UNRESOLVED`.** No authoritative timing statement was found in any source examined, and no per-variable documentation is available in the public materials. The remaining paths are the archive's own documentation (not openable under the current authorisation) or direct owner clarification, which is not available.
- **Action enabled.** This is decisive for the route matrix (§7): a UCI-412 protocol could not honestly claim a *pre-angiography decision moment*, which is the moment any clinical-workflow-aligned product would need. Any future UCI-412 work must be framed as **post-hoc classification of a recorded feature set with unverified acquisition order** — a materially weaker research question than Route A's. *(This records missing documentary support; it is not proof that the fields were measured after angiography — several are ordinary intake variables.)*
- **Residual.** Owner clarification; a prospective re-collection with recorded timestamps (not authorised, not in scope).

### U-7 · Source reference standard, and the exact-50 % threshold (residual items **S-7 / H-01**)

- **Exact scientific question.** What exactly is the reference standard for `Cad`, is the boundary `≥50 %` or `>50 %`, and can any record sitting at exactly 50 % be identified?
- **Existing evidence.** Gate DA H-01: the *wording* difference is VERIFIED; boundary existence/coding UNVERIFIED; permitted dispositions identical / reconciled / related-but-not-identical / unresolved **[R1]**. UCI-45 `num` wording `<50 %` / `>50 %` **[A1]**. Panel mapping `Cath` `Cad`→1 / `Normal`→0, case-sensitive, no coercion **[R1]**.
- **Newly verified.** (i) **[A1]** UCI-412 verbatim: "categorized as CAD, if his/her diameter narrowing is **greater than or equal to 50 %**" (SRC-03); UCI-411 verbatim: same, plus "CAD … happens when at least one of these three arteries is stenotic" (SRC-04). (ii) **[A1]** UCI-45 `num`: "Value 0: < 50 % diameter narrowing / Value 1: > 50 % diameter narrowing (in any major vessel)" (SRC-02) — note the codebook documents `num` as **binary** there while §10 tabulates **0–4**, a documented internal inconsistency. (iii) **[A2]** The originating publication defines disease as "presence or absence of a **> 50 % diameter narrowing**" and calls an angiogram abnormal at "**> 50 %** luminal narrowing of any major epicardial vessel", with "angiograms … read by **visual assessment** of the percent diameter narrowing" (SRC-05). (iv) Neither release retains a per-record stenosis percentage, per-vessel field in UCI-412, or any boundary marker.
- **Strength and limitations.** The *wording* is now pinned to three authoritative sources and the direction of the mismatch is unambiguous: **exactly-50 % would be negative under UCI-45/Detrano and positive under UCI-412/411.** What cannot be established, at any level of effort, is (a) whether any record in either release sits at exactly 50 % and (b) how such a record was coded — because the underlying measurement was a **visual estimate** and the released fields are categorical.
- **Status: `RESOLVED` for the wording/definition (three-source, verbatim); `NO-GO` for per-record boundary identification and for empirical reconciliation.** The only defensible disposition of H-01 is **"related-but-not-identical"**; it can never become "identical" on evidence available to this project.
- **Action enabled.** Cross-source statements can now be written precisely: two angiography-referenced presence labels that differ by a one-sided boundary rule under visual estimation, whose disagreement rate cannot be estimated. Pooling and any "same endpoint" claim are excluded on evidence, not merely by policy. **Source-specific** use of either label is unaffected.
- **Residual.** Human adjudication of the disposition; per-record verification is impossible.

---

## 4. Cleveland–Hungary compatibility — question-by-question resolution

*Scope: the five-field panel (`age`, `sex`, `cp`, `trestbps`, `restecg`) of a future locked Cleveland model assessed once on the Hungarian file. No assessment, no fit, no transfer prediction was performed.*

### H-1 · Target coding and source reference standard

- **Exact scientific question.** Does the processed Hungarian file's binary target mean `num = 0` versus `num = 1–4`, and is its reference standard the same angiography-based rule as Cleveland's?
- **Existing evidence.** Processed audit: 188 negative / 106 positive **[L1]**; raw codebook 0–4; "aggregate correspondence is consistent with binarization, but does not prove each patient's clinical label was equivalently recoded"; UCI-45 sibling-site compatibility "remains unresolved" **[R1]** (`gate-pt/06` §6.4; `gate-pt/07` §2).
- **Newly verified.** (i) **[A1]** The codebook publishes the **per-site raw class distribution**: Hungarian `188 / 37 / 26 / 28 / 15 = 294` (SRC-02 §10). (ii) **[AA]** Arithmetic identity: `37 + 26 + 28 + 15 = 106`, exactly the audited positive count, and `188` exactly the audited negative count. The alternative binarisations are excluded arithmetically — `0` vs `1` alone would give 37 positives; any other cut-point gives a different total. (iii) **[A1]** The codebook states the conventional contrast explicitly: "Experiments with the Cleveland database have concentrated on simply attempting to distinguish presence (values 1,2,3,4) from absence (value 0)" (SRC-01/SRC-02). (iv) **[A2]** For the **reference standard**, the originating publication — the *same* publication the UCI-45 page declares as the dataset's introductory paper — states that the Hungarian test-group records were collected at the Hungarian Institute of Cardiology (1983–1987) under the same protocol, that disease is `>50 %` diameter narrowing of any major epicardial vessel, read visually, with prior infarction and valvular disease excluded (SRC-05).
- **Strength and limitations.** The **codebook-level** convention and the **reference-standard provenance** are directly documented. What is **not** established is that the *delivered processed file* implements that convention record-by-record: the 188/106 agreement is between a published table and a maintainer-reported aggregate **[L1]**, and aggregate concordance does not verify per-record labels. Two further limits survive: the *ordinal* meaning of `num = 2,3,4` is undocumented (irrelevant to the approved binary target, decisive against any severity modelling); and per-record correctness cannot be checked without the raw file, whose positional correspondence with the processed file was 1/294 (row order differs) while the unordered 13-predictor/binary-target profile matched 293/294 **[L1]** — a result that is *consistent with* reordering and binarisation but proves neither.
- **Status — split by level.**
  - `RESOLVED — documentation level`: the codebook's `num` convention (0 vs 1–4) for this cohort, the cohort's class counts, and the existence of a single published protocol defining the angiography reference standard for both cohorts.
  - `CONDITIONALLY RESOLVABLE — file level`: that the delivered processed Hungarian file implements that convention for every record. Requires an authorised aggregate-only reconciliation.
  - **Neither component establishes patient-level label correctness, and the arithmetic agreement is not independent verification of the delivered file.**
- **Action enabled.** A future protocol may state the Hungarian target as "`num` 0 vs 1–4 per the source codebook, whose per-site distribution is 188/37/26/28/15; the processed representation is reported as 188/106 (maintainer-reported, aggregate only); reference standard `>50 %` narrowing in any major epicardial vessel per the source publication" — instead of "unresolved", **while explicitly recording that the delivered-file equivalence is unverified**.
- **Residual.** Human sign-off of that sentence; file-level reconciliation; registration in the D-046 audit record; no severity use.

### H-2 · Five-field source-code and unit compatibility

- **Exact scientific question.** Can `age`, `sex`, `cp`, `trestbps`, `restecg` be carried from Cleveland to Hungary without a silent crosswalk — i.e. are the codes, categories and units the same variables?
- **Existing evidence.** Cleveland five-field mapping spec `cleveland_resting_five_field.v0.1` records literal UCI-45 coding, units and a strict no-crosswalk rule **[R1]**; doc 07 §3.2 lists "verify category dictionary and category-level mapping across both source representations" as an *open requirement* **[R1]**.
- **Newly verified.** (i) **[A1]** The codebook covers **one directory, one format, one coding table**, and states "Each database has the same instance format" — the codes (`cp` 1–4, `restecg` 0–2, `sex` 1/0, `trestbps` in mm Hg) are defined **once for all four files**, not per site (SRC-02). (ii) **[A1]** `trestbps` is "resting blood pressure (in mm Hg **on admission to the hospital**)", and the sibling attribute 37 `trestbpd` is the diastolic field — i.e. `trestbps` is the **systolic** value of a two-field pair that survives in the raw 76-attribute form (SRC-02). (iii) **[A2]** The originating publication states the test-group data "included age, sex, **chest pain characteristics (as seen earlier)**, **systolic blood pressure at rest**, …, **electrocardiogram at rest**" — where "as seen earlier" refers to the four-category definition (typical anginal, atypical anginal, nonanginal, asymptomatic) and the three-class resting-ECG scheme (SRC-05). Both the definitional set and the measurement moment are therefore documented **for the Hungarian site specifically**.
- **Strength and limitations.** Note the exact wording: the paper states which data were collected for the test groups; it does **not** certify field completeness at each site, so this is a statement of a shared instrument and shared variable definitions, not of per-site data quality. Subject to that, it resolves the *convention* question at documentation level for all five fields, including the two that are hardest to defend elsewhere: `trestbps` is now documented as **systolic** (codebook + primary paper), and `cp` is documented as a **single 4-category variable** (not flags) for both cohorts. It does **not** verify the delivered processed Hungarian file's column order or the absence of file-level recoding — that is a technical audit step, cheap but not yet registered. Nor does it establish device, observer or technique comparability across two institutions and decades.
- **Status — split by level.** `RESOLVED — documentation level` for variable **definitions and units** as published in one codebook and one protocol; `CONDITIONALLY RESOLVABLE — file level` for the delivered processed file's column order, value domains and absence of file-level recoding. **This is not evidence that the two sites measured the same thing in practice** (devices, observers, technique and era differ), and no such equivalence is claimed. No silent crosswalk is needed or permitted.
- **Action enabled.** The five-field map can be registered as a **shared-instrument** mapping with per-field documented definitions and units, replacing five "unverified" rows — explicitly at documentation level, with delivered-file verification still outstanding. The prohibition on converting UCI-412 `BP`/`PR` into this panel is unaffected and now better justified (no units were found for those fields in the materials examined).
- **Residual.** Delivered-file column/value verification; observer/device heterogeneity remains a permanent limitation to be stated, not solved.

### H-3 · Missingness

- **Exact scientific question.** How much is missing in the Hungarian five-field bundle, under what convention, and does the missingness mechanism permit a defensible eligibility rule?
- **Existing evidence.** Official: "Missing Attribute Values: Several. Distinguished with value -9.0" **[A1]** (raw files). Audit: 782 missing cells across the processed 14 columns (19.00 %); five-field bundle present in **292/294**; `ca` missing 291/294, `thal` 266/294; lab bundle 261/294; exercise bundle 95/294 **[L1]**.
- **Newly verified.** (i) **[A1]** The sentinel and its existence are officially documented (SRC-02 §9); the *processed* file's missing symbol is not documented by the owner and was established by audit only **[L1]**. (ii) **[AA]** 292/294 = 99.3 % joint availability for the five fields — i.e. the panel is essentially complete for this cohort; the heavy missingness is concentrated in fields the panel excludes (`ca`, `thal`, exercise, laboratory). (iii) No source states the *mechanism* (not measured / not recorded / lost).
- **Strength and limitations.** The **quantity** is resolved; the **mechanism** is not, and cannot be from these files. An eligibility rule that uses only the five fields is therefore defensible as a coverage statement (292/294), *not* as a missing-at-random assumption.
- **Status: `RESOLVED` (sentinel convention — documented); `UNRESOLVED` (mechanism); the 782-cell and 292/294 quantities are maintainer-reported aggregates **[L1]**, not independently re-derived.**
- **Action enabled.** A future assessment can prespecify: complete-case five-field eligibility (n = 292 expected, to be confirmed at assessment time), all exclusions counted and reported, no imputation presented as measurement.
- **Residual.** Human acceptance of the complete-case rule; explicit statement that exclusion from the assessment set is *not* evidence of missing-at-random.

### H-4 · Measurement timing relative to angiography

- **Exact scientific question.** Were the five fields recorded before the angiogram for the Hungarian records?
- **Existing evidence.** Previously recorded as "no record-level chronology… timing **NOT ASSESSED**" **[R1]** (doc 07 §7.4, doc 11 §7.4).
- **Newly verified.** (i) **[A2]** "Histories, physical examinations and all noninvasive tests were performed **within 6 weeks before the date of the coronary angiogram**", and "Clinical data and noninvasive test results were recorded **before** (and therefore without knowledge of) the coronary angiography results" — stated for the test groups, of which the Hungarian cohort is one (SRC-05). (ii) **[A2]** The Cleveland derivation cohort's history/exam/resting ECG were "part of their routine evaluation", recorded and coded "without knowledge of noninvasive or angiographic test data", with "work-up bias … therefore not present" (SRC-05). (iii) **[A2]** For the test groups, by contrast, "**workup bias or angiographic referral bias was present**" — the publication says so itself. (iv) **[A1+INF]** The raw 76-attribute files retain **month/day/year of the exercise ECG (attributes 20–22) and of the cardiac catheterisation (attributes 55–57)**, so a per-record ordering check is *possible in principle* from the raw form, though the processed 14-column form drops those fields.
- **Strength and limitations.** The **protocol-level** timing question is now answered in the affirmative, for both cohorts, with a ≤6-week window stated for histories, physical examinations and non-invasive tests. This is a genuine upgrade from "design aspiration", but it is a statement about **how the study was conducted as published**, not a verification of any record: it does not show that every released record's inputs precede its angiogram, and it does **not** remove the publication's own admission of referral/workup bias in the test groups — which must be reported as a limitation of any Hungary assessment, not explained away. It also does not establish that the released subset followed the protocol.
- **Status: `RESOLVED` — protocol level only (as published). Per-record timing: `UNVERIFIED`, and `CONDITIONALLY RESOLVABLE` at best, via an authorised aggregate read-only audit of the raw Hungarian date fields (attributes 20–22, 55–57).**
- **Action enabled.** A future protocol may define the prediction moment as "a resting assessment within 6 weeks before angiography, interpreted without knowledge of the angiogram" and must state that inclusion in catheterisation was influenced by clinicians who saw non-invasive results. The per-record audit is now a **specified, bounded** task rather than an open question.
- **Residual.** Authorisation for that audit; if the raw date fields are largely `-9.0`, per-record timing stays unverifiable and the statement must stay at protocol level.

### H-5 · Cohort independence and overlap uncertainty

- **Exact scientific question.** Can the Hungarian cohort be described as independent of the Cleveland development cohort, and what overlap uncertainty remains?
- **Existing evidence.** "Different site is not proof of independent persons"; cross-site duplicates cannot be excluded from identifier-free files; an aggregate-only overlap audit was never performed for this pair **[R1]** (`gate-pt/06` §6.4, `gate-pt/07` §2, doc 11 §7.5).
- **Newly verified.** (i) **[A2]** Distinct institutions in distinct countries with **overlapping but different recruitment windows** — Cleveland May 1981–September 1984; Hungary 1983–1987 — each cohort drawn from consecutive/all catheterised patients at its own centre under its own investigators (Jánosi, Budapest; Detrano, Cleveland) (SRC-05). (ii) **[A1]** The two cohorts are separate files with separate counts (303 / 294) and separate class distributions (SRC-02). (iii) **[GAP — count discrepancy, unexplained]** The publication describes a Hungarian test group of **425** patients (SRC-05) whereas the UCI release contains **294** Hungarian records (SRC-02 §10). **The relationship between these two groups is not documented.** It is *not* asserted here that the 294 are a subset of the 425, nor that they are different patients: the publication's 425 may include records excluded from release, the release may derive from a different extraction, and no provenance statement links the two. This is recorded as an **unexplained count discrepancy**, and it must appear as a limitation in any future assessment protocol.
- **Strength and limitations.** Cohort-construction evidence is **explicit and reasonably strong** (separate centres, separate investigators, separate recruitment windows, separate files) — considerably better than "a different site name" — and it makes person-level overlap *implausible*. It is **not proof of independence**: no identifiers survive, no overlap audit has been performed, the 294-versus-425 discrepancy is unexplained, and the selection mechanism for whatever was released is undocumented. Independence therefore remains an **unverified assumption**, not a finding.
- **Status: `CONDITIONALLY RESOLVABLE`** — an authorised, aggregate-only, privacy-preserving overlap audit plus a human disposition. **Person-level independence is not claimed and must not be described as proved.**
- **Action enabled.** A future protocol may state only: "separate centre, separate investigators, separate recruitment window, separate released file; person-level independence **not verified**; the released file contains 294 records whereas the source publication describes a 425-patient Hungarian group, and the relationship between the two is undocumented". That is the honest, defensible sentence — and it is exactly what an external-assessment report would have to contain.
- **Residual.** Human adjudication; overlap audit; an explanation of the 294-versus-425 discrepancy from the data custodians or owners.

### H-6 · Whether 294 records with 106 / 188 can support a prespecified external assessment with useful precision

- **Exact scientific question.** At n = 294 (106 positive, 188 negative), how precisely could a one-shot assessment estimate the estimands it would report, and does that meet a **prespecified** target?
- **Existing evidence.** M2e.2 / M2f require a statistician's **prespecified** precision-feasibility ruling and forbid relaxing targets after seeing results **[R1]**; no such ruling exists **[GAP]**.

#### H-6.1 Three frameworks that must not be conflated

*(Correction in revision 15.1: revision 15.0 blurred these, and its wording could be read as presenting one number as a validation threshold. That reading was wrong and is withdrawn.)*

| Framework | What it sizes | Required inputs | Status today |
|---|---|---|---|
| **Riley 2020 / `pmsampsize` — development criteria** | The sample needed to **develop** a new model: expected uniform shrinkage, expected optimism in Nagelkerke R², and optionally outcome-proportion precision and minimum MAPE | Number of candidate parameters and an **anticipated** Cox–Snell R²; anticipated prevalence | Partly computable (the R²-free members, doc 05). The R²-dependent members are **not computable** — no defensible anticipated R² exists **[R1]** |
| **Descriptive binomial outcome-proportion precision** | The width of a confidence interval for **one proportion** (here, the outcome proportion in a fixed cohort) | An assumed proportion and a target half-width | **Computable** — and this is the *only* thing the arithmetic below computes |
| **Riley 2021 — external-validation criteria** | The sample needed to **validate a named, locked model**: precision of the C-statistic, of calibration slope and calibration-in-the-large, plus linear-predictor-variance / anticipated-miscalibration inputs (and net-benefit inputs if a decision-curve estimand is planned) | A **locked model**, its anticipated performance, the validation outcome proportion, anticipated miscalibration, the linear-predictor distribution, and prespecified target SEs/CI widths | **Not computable.** No locked model exists (D-047 saved no full-cohort artefact **[R1]**), no estimand set or tolerance has been prespecified, and neither has been approved |

#### H-6.2 What the arithmetic actually is — descriptive binomial precision **[AA]**

Full reproduction record: **Appendix B** (constants, formulae, worked arithmetic, outputs). Both tables below are **[AA]** and, where an AUROC appears, the AUC value is a hypothetical **[SC]** input.

| Quantity (descriptive only) | Cleveland (303; 139/164) | **Hungary (294; 106/188)** | UCI-412 (303; 216/87) |
|---|---|---|---|
| Records for a ±0.05 binomial interval on the outcome proportion (95 %) | 382 | **355** | 315 |
| Achievable binomial half-width at the available n | ±0.0561 | **±0.0549** | ±0.0509 |

| *Illustrative* AUROC interval half-width **[SC]**, Hanley–McNeil approximation | Cleveland | **Hungary** | UCI-412 |
|---|---|---|---|
| scenario AUC 0.70 | ±0.059 | **±0.064** | ±0.061 |
| scenario AUC 0.80 | ±0.051 | **±0.056** | ±0.050 |
| scenario AUC 0.90 | ±0.037 | **±0.041** | ±0.034 |

#### H-6.3 What this does and does not establish

- **It establishes one thing.** At 106/294, a 95 % binomial interval for a **single proportion** would be about ±0.055 wide; ±0.05 would require 355 records. The figure is a property of a proportion, not of a model.
- **It is not a Riley-2021 external-validation determination.** 355 is **not** an external-validation threshold, a sufficiency criterion, an adequacy verdict or an approval. It says nothing about whether a future assessment could estimate discrimination or calibration to any required precision, because those require model-specific inputs that do not exist.
- **The AUROC rows are illustrative scenarios [SC].** Every AUC entering them is a hypothetical input used only to size an interval. None is a predicted, expected, observed or borrowed performance value, and **none may be read as an expectation for any model**.
- **The interval method is an approximation.** The formula used is the **Hanley–McNeil (1982) large-sample approximation** to the variance of the AUC estimator. It is **not** the DeLong variance estimator. It assumes a particular underlying model, ignores refitting, model selection, clustering/repeat structure, and does not use the observed prediction distribution. **Actual interval width may therefore be narrower or wider than these values** depending on the observed prediction distributions, the estimator actually used, its assumptions, and the study design. No direction of error is asserted.
- **No verdict follows.** Whether 294 records can support a *useful* assessment is a **prespecified statistical judgement** that a named statistician must make, with a locked model and declared estimands and tolerances.

- **Status — split by level.**
  - `RESOLVED — arithmetic only`: the descriptive binomial precision of the outcome proportion at n = 294, and the corresponding values for the comparison cohorts.
  - `NOT ASSESSED — external-validation precision`: no Riley-2021 determination exists or can exist before a model is locked and estimands/tolerances are prespecified. This blocker is **not adjudicated** by this document.
- **Action enabled.** A future protocol may, **before** any access, record a prespecified *descriptive* tolerance (e.g. "report the outcome proportion with a half-width of approximately ±0.055 and the C-statistic with an interval whose target width is fixed prospectively"), and must state that this is a descriptive framing, not a Riley-2021 determination. What it may **not** do is (i) cite 355 as a validation threshold or as evidence of adequacy, or (ii) choose a tolerance after seeing results.
- **Residual.** A named statistician's prespecified ruling; an eligible locked model; a Riley-2021 calculation with model-specific inputs and declared tolerances — none of which this document can supply.

---

## 5. Blocker resolution matrix

Statuses are those defined in §0.1. "Direct quotes" refers to Appendix A.

| # | Blocker | Question in one line | Status | Decisive evidence | What remains |
|---|---|---|---|---|---|
| **U-1** | `BP` quantity/unit (S-2) | systolic, diastolic or unspecified? | **CONDITIONALLY RESOLVABLE** | [A1] no per-variable documentation in the materials examined; [B1] author group's 90–190 domain + systolic-style 90/140 bands | CMBP Table 1 (paywalled), archive documentation, or owner clarification; human acceptance |
| **U-2** | `PR` quantity/unit (S-3) | pulses per minute? | **CONDITIONALLY RESOLVABLE** | [A1] no per-variable documentation in the materials examined; [B1] 50–110 domain + 60/100 bands | as U-1 |
| **U-3** | Direction of six numeric binaries (S-9) | is 1 = present? | **CONDITIONALLY RESOLVABLE** (corroboration strengthened; **not resolved**) | [L1] representation; [B2] `True = 1`; [B1] authors' own counts 90/48/164 concord with the audit and the reported conditional frequencies favour the registered direction — **corroboration, not proof** | explicit human acceptance of S-9; owner coding documentation (none found in materials examined) |
| **U-4** | Text vocabulary + `Sex` (S-1) | which tokens occur? | **CONDITIONALLY RESOLVABLE** | [L1] 303/303 cells accepted by the registered vocabulary; [A1] no owner vocabulary found in the materials examined | token-frequency addendum (counts only, already-audited file) |
| **U-5a** | Chest-pain *definitions* | what counts as each descriptor? | **UNRESOLVED** | [A1] none; [A2-p] table inaccessible; [B1] structure only | source questionnaire or owner documentation; **not obtainable publicly** |
| **U-5b** | Chest-pain *exclusivity* | one descriptor per patient? | **CONDITIONALLY RESOLVABLE** | [A1] none; [B1] they are separate Yes/No items, i.e. flags not levels | aggregate four-way joint-count audit |
| **U-6** | UCI-412 per-field timing | recorded before angiography? | **UNRESOLVED** | [A1] no timing statement on the page; [A2-p] none in the accessible primary text; [B1] none | archive documentation, or owner clarification — neither available |
| **U-7** | Reference standard / 50 % threshold | ≥ or > 50 %? can boundary cases be identified? | **RESOLVED (wording) / NO-GO (per-record)** | [A1] verbatim ≥50 % (412, 411) and <50 %/>50 % (45); [A2] `>50 %` + visual estimation | human disposition "related-but-not-identical" |
| **H-1** | Hungarian target coding + reference standard | 0 vs 1–4, same standard? | **RESOLVED — documentation level**; delivered-file equivalence **UNVERIFIED** | [A1] per-site 188/37/26/28/15 and the 0-vs-1–4 convention; [AA] 37+26+28+15 = 106 = audited positives; [A2] one protocol, `>50 %`, both cohorts | file-level reconciliation; human sign-off; **aggregate concordance ≠ independent verification** |
| **H-2** | Five-field codes/units | same variables? | **RESOLVED — documentation level** / **CONDITIONALLY RESOLVABLE — delivered file** | [A1] one codebook, one format, `trestbps` = systolic mm Hg on admission with `trestbpd` sibling; [A2] same clinical variables collected at the Hungarian site | delivered-file column/value verification; device/observer/era heterogeneity is a permanent limitation, not a solvable item |
| **H-3** | Missingness | how much, under what convention? | **RESOLVED — sentinel convention**; quantities `[L1]`; mechanism **UNRESOLVED** | [A1] `-9.0` documented; [L1] 782 cells, five-field bundle 292/294 (maintainer-reported, not re-derived) | complete-case rule; mechanism stays undocumented |
| **H-4** | Timing | measured before angiography? | **RESOLVED — protocol level only**; per-record **UNVERIFIED** | [A2] "within 6 weeks before the date of the coronary angiogram"; recorded "before … without knowledge of" results | raw-file date-field audit (conditional); referral/workup-bias statement mandatory |
| **H-5** | Independence / overlap | separate patients? | **CONDITIONALLY RESOLVABLE** — independence **not proved** | [A2] separate centres, investigators, windows; [A1] separate files; **[GAP] the release has 294 records vs the publication's 425, relationship undocumented** | overlap audit; explanation of the count discrepancy; human disposition |
| **H-6** | Precision at n = 294 | useful precision? | **RESOLVED — descriptive binomial arithmetic only**; external-validation precision **NOT ASSESSED** | [AA] binomial outcome-proportion half-width ±0.0549 (355 for ±0.05, a **proportion** requirement, not a validation threshold); AUROC rows are [SC] Hanley–McNeil illustrations | a prespecified statistician's ruling; an eligible locked model; a Riley-2021 calculation with model-specific inputs |
| **X-1** | H-01 cross-source harmonisation | are the labels the same endpoint? | **NO-GO** (as an empirical reconciliation) | [A1]/[A2] one-sided boundary difference under visual estimation; no per-record stenosis survives | disposition, not resolution |
| **X-2** | Independent assessment of a UCI-412 model | exists in the project's current source inventory? | **NO-GO** (bounded to that inventory) | [A1] UCI-411 = same 303; no second Z-Alizadeh-Sani-style cohort identified in Gate DA 01–17 or in the sources examined | a genuinely new, differently-sourced cohort under a new authorization; absence in this inventory is not proof that none exists publicly |

**Summary of the matrix (revision 15.1 counts).**

- **`RESOLVED`, but only at a named, limited level — 5 items:** U-7 (label wording only), H-1 (documentation level), H-2 (documentation level), H-3 (sentinel convention only), H-4 (protocol level only). **None is resolved at record level**, and each is paired in the matrix with an explicit unverified or conditional file/per-record component.
- **`RESOLVED` as arithmetic only — 1 item:** H-6, where only the *descriptive binomial* calculation is settled; external-validation precision is **`NOT ASSESSED`**.
- **`CONDITIONALLY RESOLVABLE` — 6 items:** U-1, U-2, U-3, U-4, U-5b, H-5.
- **`UNRESOLVED` — 3 items:** U-5a (definitions), U-6 (UCI-412 timing), H-3 mechanism.
- **`NO-GO` — 2 items:** X-1 (empirical reconciliation of the 50 % boundary) and X-2 (independent assessment within the current source inventory).
- **No item is `RESOLVED` on inference, plausibility, count concordance or documentation alone at file level.** The three items that most constrain the route comparison — UCI-412 per-field timing (U-6), the exact-50 % boundary (U-7/X-1) and external-validation precision (H-6 verdict) — are respectively unresolved, no-go and not assessed.

---

## 6. Feasibility of a future independent assessment

### 6.1 Candidate-by-candidate position

| Candidate | Role | Evidence position after this review | Verdict |
|---|---|---|---|
| **UCI-45 Hungary (DA-A2)** | one-shot site-shift assessment of a *locked Cleveland five-field* model | Codebook-level target convention, reference-standard provenance, five-field definitions/units and protocol-level timing are documented (§4 H-1…H-4), each at documentation level only. Remaining: file-level verification, overlap audit, the unexplained 294-vs-425 count discrepancy, an external-validation precision ruling, and the publication's own admission of referral/workup bias | **`CONDITIONAL — most documented candidate; NOT READY`** (documentation is not readiness, and readiness is not validation) |
| UCI-45 VA Long Beach | same role, lower feasibility | 200 records, 51 negative; five-field availability 143/200 under the audit's zero-unavailable rule; same documentation base as Hungary | `CONDITIONAL — weaker` |
| UCI-45 Switzerland | site stress-test only | 123 records, **8 negatives**; all 123 cholesterol entries zero; lab bundle 0/123 under the zero-unavailable rule | `CONDITIONALLY NOT EVALUABLE` for discrimination/calibration estimands |
| UCI-411 | none for UCI-412 | **Same 303 participants** [A1] | `EXCLUDED` — can never be independent |
| Any second Z-Alizadeh-Sani-style cohort | independent assessment of a UCI-412 model | **None identified** anywhere in the project's source inventory [R1]/[GAP] | `NO-GO` (Route B's decisive weakness) |
| Statlog / Kaggle merges | overlap study only | suspect Cleveland duplication; unresolved | `EXCLUDED` |

**Read this table carefully.** "Most documented" is a statement about how much of the *methodological record* is traceable, not about statistical suitability, not about validity, and not about permission. No candidate here is `READY`, `APPROVED` or `VALIDATED`, and this review does not change that.

### 6.2 What "ready" would require, and where the gaps are

Doc 06 §7.1's eight prerequisites, re-scored against the evidence in §4:

| Prerequisite | Hungary position now |
|---|---|
| Outcome compatibility | **Documented at source level** (`>50 %` visual, one protocol); disposition "related-but-not-identical" vs UCI-412 remains, and is irrelevant to a within-UCI-45 pair |
| Cohort independence | Separate centre/investigators/window documented; **person-level independence unprovable**; subset rule unknown |
| Frozen prediction moment | **Documented** (resting assessment ≤6 weeks before angiography) at protocol level; per-record unverified |
| Feature/missingness compatibility | **Documented** shared codebook; complete-case five-field eligibility 292/294 |
| Leakage protection | Five fields contain no angiography-derived, identifier or post-outcome value; `ca`/vessel/`thal` remain prohibited |
| Case mix framing | Publication supplies the framing: 38 % disease, mean age 48, 71 % men, referral/workup bias acknowledged |
| Precision feasibility | **Not adjudicated.** Only the descriptive binomial width is computable (±0.0549 at n = 294); a Riley-2021 external-validation determination is `NOT ASSESSED` because no model is locked and no estimands or tolerances are prespecified (H-6) |
| One-shot discipline | Policy exists (doc 07 §2/§3.5); nothing has been done against Hungary — **it is still untouched** |

**Six of eight prerequisites now have some documentation basis, but none of the six is verified at record level, and two (independence, precision) remain open judgements.** That is the substantive change this review contributes — and it does **not** make Hungary "ready", for three independent reasons: a *locked model* does not exist (D-047 saved none **[R1]**), no protocol authorises a freeze, and the precision question is **not adjudicated** (H-6). Documentation reduces uncertainty about *what was done*; it establishes nothing about *how well a model would perform there*.

### 6.3 Honest statement of what a future assessment could and could not conclude

Could conclude — and only if every gate in §6.2 is satisfied and the tolerances were fixed in advance: "Under a prespecified, locked five-field model applied once to an untouched second UCI-45 site cohort, the observed discrimination and calibration were X and Y with intervals of the width prespecified for that analysis, in a historical angiography-referred cohort with documented referral and work-up bias; this is a **single-site descriptive performance estimate for one model–cohort pair**, with the interval widths and the count discrepancy stated."

Could **not** conclude: that the model is externally *validated* in the sense of being fit for use; any clinical utility, benefit or safety; any contemporary-population applicability; any calibrated individual risk percentage; any transportability beyond the assessed cohort; any between-dataset performance comparison. **No numeric interval width is quoted here as a target** — the widths a real assessment would achieve depend on the estimator, the observed predictions and the design (H-6.3).

### 6.4 Independent external validation is not the same thing as a clinically validated, deployable model

This distinction is load-bearing for the recommendation in §8, so it is stated explicitly.

| Concept | What it means | What it would require | Position today |
|---|---|---|---|
| **Documentation / compatibility review** (this document) | Establishing what the sources say, and whether a comparison is methodologically definable | Traceable primary sources; explicit unresolved items | **Exists** (this review and docs 05–14) |
| **Internal exploratory benchmark** | A within-cohort, resampled estimate of what a pipeline can do on its own source data | A frozen plan, an authorised local run, privacy-reviewed aggregates | **Exists** (D-047; M3a) — and is explicitly **not** a performance claim |
| **Independent external validation study** | Applying one **locked** model once to a **separately sourced** cohort under a prespecified protocol, reporting discrimination, calibration and uncertainty with prespecified precision | A locked artefact; an eligible independent cohort; adjudicated compatibility and independence; prespecified estimands and tolerances; one-shot discipline; P-3-level approval | **Does not exist.** No locked artefact, no adjudicated candidate, no approved protocol, no precision ruling |
| **A clinically validated, deployable model** | Evidence that using the model in a defined care pathway improves decisions or outcomes, with safety, usability and governance review, in the intended population | Everything above **plus** prospective evaluation in the intended setting, clinical utility/impact evidence, current-population representativeness, and institutional/regulatory governance | **Does not exist and is not in scope.** P-5 remains prohibited |

**Consequence for the recommendation.** Even a fully successful Hungary stage 2 would reach only the third row, for one model–cohort pair, in a historical cohort. It would **not** produce a deployable or clinically validated model, and it would not license any wording suggesting either. Conversely, no amount of documentation — including everything this review adds — can substitute for the third and fourth rows.

---

## 7. Development-route decision matrix

> **Read this first — two binding rules.**
>
> 1. **No internal exploratory AUROC appears in this matrix, and none was used to form any verdict.** The Cleveland `0.8271` and UCI-412 `0.9107` values are incomparable (different cohorts, targets, panels, codings, case mixes and evaluation designs) and were excluded, as doc 08 §11 and doc 11 §6 require. Route preference is argued **only** from semantics, timing, target validity, sample size, evaluability and reproducibility — criteria on which the two datasets *can* be compared. **No ranking of development routes by AUROC is made or implied anywhere in this document.**
> 2. **Each cell's score is about *traceability and definability*, not about expected performance.** `++` means the property is documented or structurally favourable; it does **not** mean the route will work well, and it is not a prediction.
>
> **Revision 15.1 note:** the C1–C7 scores are unchanged from 15.0, but C4, C5 and the surrounding text were reworded because 15.0's phrasing could be read as implying that Hungary had become assessment-ready and that the sample-size question was settled. Neither is true.

Scale: **++** strong / documented · **+** adequate with stated conditions · **0** neutral/indeterminate · **–** weak · **––** decisive weakness.

| Criterion | **A. Cleveland five-field** | **B. UCI-412 sixteen-field** | **C. Narrower research-only route** |
|---|---|---|---|
| **C1 Clinical-workflow alignment** | **++** Five first-encounter inputs: history (age, sex, chest-pain type), examination (`trestbps` "on admission"), resting ECG. The prediction moment is a resting assessment, exactly what the workflow asks for | **+** Sixteen intake-type fields, but the moment is *undocumented* (U-6); `BP`/`PR` measurement conditions unknown; echo/lab deliberately excluded | **++** inherited; C adds no new field burden |
| **C2 Feature semantics and timing** | **++** (documentation level) Codebook + primary publication define all five fields (incl. `trestbps` = systolic, `cp` = 4 categories, `restecg` = 3 classes) and state a ≤6-week pre-angiography protocol window (H-2, H-4). *File-level verification and per-record timing remain unverified* | **–** 2 of 16 fields have unresolved quantity/unit (U-1, U-2), 4 have undefined elicitation (U-5a), and per-field timing is unresolved for all 16 (U-6). No per-variable documentation was found in the materials examined | **++** as A; the route is deliberately restricted to what is documented |
| **C3 Target validity** | **++** `num` 0 vs 1–4 documented in codebook + primary publication + class distribution; `>50 %` visual reading stated; severity use excluded | **+** `Cath` Cad/Normal with documented ≥50 % rule and audited 216/87; one unresolved label-consistency discordance exists only in the UCI-411 *artery* columns, not in `Cath` | **++** as A |
| **C4 Sample size** | **–** n = 303 (139/164). Descriptive binomial half-width ±0.0561; a ±0.05 outcome-proportion interval would need 382 **[AA]**. The doc-05 Riley arithmetic fails at 303 on both the outcome-proportion criterion (382) and the additional approximate MAPE criterion (459 at p = 8); the *adequacy decision* remains **`NOT ASSESSED — PENDING HUMAN REVIEW`** [R1] | **–** n = 303 (216/87). ±0.0509; ±0.05 would need 315 **[AA]**; only 87 negatives. The outcome-proportion criterion is **NOT MET at 303**; shrinkage/optimism/MAPE are unassessed for the same reason as A (no admissible anticipated R²) [R1] | **0** — the route explicitly *accepts* a descriptive, under-powered framing instead of claiming adequacy. **All three routes share the same fact: no route has an adequate or adjudicated sample-size basis.** |
| **C5 Honest independent evaluation** | **+** A *candidate* exists (Hungary) with better-documented target, five-field definitions, protocol-level timing and class counts; six of eight prerequisites have a documentation basis and **none is verified at record level**; independence unproved; the cohort is not ready and no validation is authorised (§6) | **––** **no candidate exists** in the current inventory: UCI-411 is the same 303 (X-2) and no second Z-Alizadeh-Sani-style cohort was identified. Any attempt would be resampling of one cohort and must not be called validation | **+** same as A; C may deliberately drop the assessment claim entirely (see fallback) |
| **C6 Reproducibility / implementation feasibility** | **++** 5 fields ⇒ 8 slope parameters; frozen harness, synthetic fixtures, mapping validator and 167 mapping tests already exist; smallest model surface; cheapest to reproduce at $0 | **+** 16 fields ⇒ 16 parameters; frozen harness exists and is more heavily guarded, but the adapter already required one encoding amendment and still carries S-1/S-9 | **++** as A |
| **C7 Research contribution** | **+** Modest but genuine: a fully traceable, prespecified source-specific benchmark **plus** a documented site-shift feasibility study in a cohort whose provenance the literature rarely documents | **+** Richer clinical panel, more model space, more methodological material — but contribution is capped by unresolved semantics and by the impossibility of independent evaluation | **+** A methods/reproducibility contribution: end-to-end evidence traceability, fail-closed encoding discipline, and an honest negative/limited result |

### 7.1 What the matrix does and does not decide

- On these criteria, **A is better documented than B on C1, C2, C5 and C6**, and **B is better documented than A on none**; B's advantage (C7, richer panel) is shared with A and capped by X-2. **This is a comparison of evidentiary traceability and evaluability, not of expected model performance**, and it is not a ranking by any performance metric.
- It does **not** decide that Cleveland "is" the project dataset (a human decision; the R1 specification already states Cleveland is **not** selected), it does **not** establish that Route A would succeed, and it authorises **no protocol**.
- **C4 is a tie at "weak"**: all three 303/294-record cohorts are below every sizing target that has been examined (382 for Cleveland's outcome-proportion criterion, 459 for its additional approximate MAPE criterion at p = 8, 315 for UCI-412, 355 for Hungary), and **no route's adequacy question is adjudicated** — for A and B the missing input is the same (an admissible anticipated R²), not a different result. C4 therefore contributes no preference, and the differing labels above (`NOT ASSESSED` vs `NOT MET`) describe which criteria could be computed, not a difference in adequacy.
- Route C is not a competitor: it is the fallback that keeps the work defensible if A's conditions fail.

---

## 8. Recommended primary research direction and fallback

**Recommendation for human review — the agent takes no decision. It is provisional, and it is a research recommendation only.**

### 8.1 Preferred: Route A′ — five-field Cleveland research line with a protected second stage

> **Working question (proposed):** in a historical, angiography-referred cohort, at a prespecified resting assessment performed before catheterisation (history, examination, resting ECG), do five routinely recorded inputs discriminate *source-defined, angiography-referenced, cross-sectional CAD presence* (`num` 0 vs 1–4, `>50 %` narrowing in any major vessel, visual reading) with a precision that can be described honestly?

**Preconditions (all human, none satisfied today):**

1. **P-1 decided** — named target, population and prediction moment frozen (D-006 stays OPEN until then).
2. **Gate PT P-3 satisfied** for the formal protocol, or an explicitly bounded internal-exploratory route used honestly (D-047's executed run is *not* a locked artefact and cannot be relabelled as one).
3. **Adequacy framing adopted explicitly, and *not* as an adequacy finding**: no sample-size criterion has been met or adjudicated for this cohort — the R²-dependent development criteria are `NOT ASSESSED` **[R1]** and the external-validation question is `NOT ASSESSED` (H-6). The claim class is therefore fixed in advance as **descriptive feasibility**, which is a limitation accepted, not a threshold passed.
4. **Five-field mapping registered** with the documented definitions/units established in §4 H-2 — no silent crosswalk, no conversion of UCI-412 `BP`/`PR` into the panel.
5. **Hungary remains untouched** for the whole of stage 1: no feature, preprocessing, family, hyperparameter, calibration, threshold or model-version choice may use it.
6. **Stage 2 is separately authorised** and requires: a locked model + preprocessing package; an overlap/independence disposition **including an explanation of the 294-versus-425 count discrepancy**; a prespecified precision ruling that states explicitly whether a Riley-2021 determination is possible and declares descriptive tolerances before access; and P-3-level approval.

**Why this route, on evidence:** it is the only pairing in the inventory where the target rule, the five input definitions, the units, the protocol measurement window and the class counts are all documented for **both** cohorts, in **one** source's own words, with a fail-closed mapping discipline already built and tested.

**What this recommendation is not.** It is not a dataset selection, not a readiness finding, not an adequacy determination, not a validation claim, and not an authorisation. It states that among the options traceable in this repository, Route A has the fewest *documentary* unknowns — which is a necessary, never a sufficient, condition for a defensible study. Even complete success at stage 2 would yield a **single-site descriptive estimate for one locked model** (§6.4), not a clinically validated or deployable model.

### 8.2 Fallback conditions (explicit; each terminates or redirects the route)

| Trigger | Fallback |
|---|---|
| P-1/P-3 not obtainable, or a clinical-performance claim is required | **Route C-narrow**: reproducibility/methods contribution only — the frozen five-field pipeline, the evidence-traceability register and the fail-closed mapping, reported as a *feasibility and methodology* result with **no** transportability claim |
| Hungary overlap cannot be bounded (or the 294-vs-425 discrepancy cannot be explained), **or** the prespecified precision ruling is NO-GO | Drop stage 2; report Cleveland-only descriptive results; if a transport claim is required, **no claim is made** |
| The five-field mapping cannot be registered without a crosswalk (i.e. H-2 evidence is rejected by a reviewer) | Stop; the route loses its only structural advantage over Route B |
| A contemporary or locally representative claim is needed (e.g. an Egyptian/current-population question) | **Additional-data strategy only**: a new, prospectively or contemporarily collected cohort under new governance (IRB/DUA), *not* a re-use of these public historical benchmarks. Not authorised, not in scope, and not a reason to proceed with fitting on the present data |

### 8.3 Position on Route B (UCI-412 sixteen-field)

**`HOLD` as a development route** — not "no-go" as a dataset, and not a criticism of the frozen internal benchmark. Reasons: (i) two of the sixteen fields have unresolved quantity/unit; (ii) four have undefined elicitation; (iii) per-field timing is unresolved for all sixteen, so the pre-angiography decision moment cannot be claimed; (iv) **no independent assessment candidate exists within the current source inventory** (X-2, bounded). It stays valuable as a *methods* benchmark (fail-closed encoding, nested CV, negative controls) and as a source of hypothesis-generating descriptive work, and it may be revisited if per-variable owner documentation (U-1/U-2/U-6) or a genuinely new, independent second cohort appears.

### 8.4 What would change this recommendation

- Publication, release or discovery of **Z-Alizadeh-Sani per-variable owner documentation** (would resolve U-1, U-2, U-4, U-5a and possibly U-6) → Route B's C2/C5 scores improve materially and the comparison must be re-run.
- A **second, independent Sani-style cohort** → Route B becomes evaluable.
- A **per-record Hungarian timing audit** showing the raw date fields are largely populated and correctly ordered → would upgrade H-4 from protocol level toward record level for Route A stage 2 (still not a validation).
- An **explanation of the 294-versus-425 discrepancy** from the data custodians → resolves an unexplained limitation (H-5).
- A human **NO-GO** on any P-1/P-3 item → all fitting routes suspend; only Route C-narrow survives.

---

## 9. The smallest next research or engineering implementation step (proposed; to be authorised)

**Proposed, not performed. Nothing below is authorised by this document.**

### 9.1 The smallest step — one documentation/decision act (human, no engineering)

Record **five decisions** in the existing registers (no new decision id is invented here; the entries belong to the maintainer/supervisor):

| # | Decision | Basis in this document |
|---|---|---|
| D-a | Accept **S-9** direction provisionally, citing the authors'-own-counts corroboration in addition to Tao 2025 | §3 U-3 |
| D-b | Register the **Hungary target/definition/timing provenance** sentences (H-1, H-2, H-4) in the D-046 audit record | §4 |
| D-c | Adopt the **H-01 disposition "related-but-not-identical"** and state that per-record boundary identification is impossible | §3 U-7 |
| D-d | Record **U-6 (UCI-412 timing) as UNRESOLVED** and therefore hold Route B as a development route | §3 U-6, §7 |
| D-e | Fix the **precision framing** for any future assessment — explicitly distinguishing descriptive binomial precision from a Riley-2021 external-validation determination, with tolerances declared in advance (or NO-GO) | §4 H-6 |

### 9.2 The smallest *implementation* step — only under separate authorisation

**One aggregate-only, read-only reconciliation in the existing D-046 toolchain, on files the project has already audited, emitting counts only** (no rows, no fingerprints, no patient-level output, no new acquisition):

1. **DA-A2 processed Hungary**: per-field value-domain inventory for the five fields; the `num` 0–4 → binary cross-tab; five-field joint-completeness count (expected 292/294). *Deliverable: a counts table that either confirms or contradicts §4 H-1/H-2/H-3 at the delivered-file level.*
2. **DA-A1 UCI-412** (same tool, same rules, separately authorised): token-frequency inventory for the six text columns (closes the recording half of U-4) and a four-way joint count of the chest-pain flags (answers U-5b).

**Explicitly not part of this step:** any model fitting, any threshold/feature selection, any train/test evaluation, any transfer or assessment prediction, any calibration, any SHAP/LIME, any change to the frozen plan or dictionary (an inventory addendum would be a *new documentation artefact*, not a dictionary edit), any workflow file, and any new dataset.

### 9.3 Why nothing larger is proposed

A larger step (a new protocol, a freeze, an assessment run) would require decisions D-a…D-e **plus** P-1 and P-3, and would run ahead of the evidence in a way that this project's own governance (D-032, D-046, D-047, D-048) exists to prevent.

---

## 10. Residual blockers, open questions and sign-off

### 10.1 Residual blockers after this review

1. **U-6** — UCI-412 per-field timing: unresolved; no evidence path available without the archive documentation or owner clarification. *(Route B blocker.)*
2. **U-5a** — chest-pain elicitation definitions: unresolved; not obtainable from the public materials examined. *(Route B limitation.)*
3. **U-1/U-2** — `BP` quantity and `PR` unit: conditionally resolvable via the paywalled paper, the archive documentation, or owner contact.
4. **U-3 (S-9)** — direction of the six numeric binaries: corroborated but **not** owner-documented and **not** record-verified; still requires explicit human acceptance.
5. **H-1/H-2 file level** — delivered-file target and value-domain equivalence for the Hungarian five fields: unverified; requires an authorised aggregate-only reconciliation.
6. **H-5** — Hungary overlap **and** the unexplained **294-versus-425** count discrepancy: conditional on an authorised aggregate audit, an explanation from the custodians, and a human disposition. Person-level independence is **not** proved.
7. **H-3 mechanism** — missingness mechanism undocumented; complete-case framing required (quantity is `[L1]`, not re-derived).
8. **H-6** — **external-validation precision is `NOT ASSESSED`**: it requires a prespecified statistician's ruling, declared estimands and tolerances, and an eligible locked model, none of which exists. The descriptive binomial arithmetic does **not** discharge this blocker.
9. **X-2** — no independent assessment candidate exists for any UCI-412-based model **within the current source inventory**.

### 10.2 Questions that only a named human can answer

| # | Question | Blank |
|---|---|---|
| Q1 | Accept S-9 provisionally on the evidence in §3 U-3, understanding that the support is corroborating (author-count concordance and directional consistency) and **not** owner documentation or record-level verification? | `[BLANK — HUMAN ONLY]` |
| Q2 | Adopt "related-but-not-identical" for H-01 and forbid any "same endpoint" wording? | `[BLANK — HUMAN ONLY]` |
| Q3 | Approve the Route A′ direction **as a provisional working direction**, the Route B `HOLD`, and Route C-narrow as fallback? | `[BLANK — HUMAN ONLY]` |
| Q4 | Fix the precision framing for any future assessment — separating descriptive binomial precision from a Riley-2021 external-validation determination, with tolerances declared in advance (or NO-GO)? | `[BLANK — HUMAN ONLY]` |
| Q5 | Authorise the aggregate-only reconciliation in §9.2, and for which dataset(s)? | `[BLANK — HUMAN ONLY]` |
| Q6 | Record the unexplained **294-versus-425** Hungarian count discrepancy as a limitation of any future assessment (without asserting a subset relationship)? | `[BLANK — HUMAN ONLY]` |

### 10.3 Status statement for the repository record

P-1 **PENDING**. Gate PT **P-3 CLOSED** (no supervisor sign-off exists, and none is claimed here). P-5 **NOT MADE — prohibited**. D-046 read-only, D-047 Cleveland-only internal exploratory, D-048/M3a UCI-412 internal exploratory — all unchanged. The internal exploratory results remain `INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED`. **No clinical readiness is claimed, and none follows from this document.**

---

## 11. References (all retrieved 2026-10-24 unless stated)

1. UCI Machine Learning Repository. *Heart Disease* (id 45). doi:10.24432/C52P4X. https://archive.ics.uci.edu/dataset/45/heart+disease — SRC-01.
2. Aha DW. *heart-disease.names* (Heart Disease Databases documentation), July 22, 1988. https://archive.ics.uci.edu/ml/machine-learning-databases/heart-disease/heart-disease.names — SRC-02.
3. UCI Machine Learning Repository. *Z-Alizadeh Sani* (id 412). doi:10.24432/C5Q31T. https://archive.ics.uci.edu/dataset/412/z+alizadeh+sani — SRC-03.
4. UCI Machine Learning Repository. *extention of Z-Alizadeh sani dataset* (id 411). doi:10.24432/C5461K. https://archive.ics.uci.edu/dataset/411/extention+of+z+alizadeh+sani+dataset — SRC-04.
5. Detrano R, Jánosi A, Steinbrunn W, Pfisterer M, Schmid J-J, Sandhu S, Guppy KH, Lee S, Froelicher V. International application of a new probability algorithm for the diagnosis of coronary artery disease. *Am J Cardiol* 1989;64(5):304–310. doi:10.1016/0002-9149(89)90524-9 — SRC-05 (full-text PDF read).
6. Alizadehsani R, Habibi J, Hosseini MJ, Mashayekhi H, Boghrati R, Ghandeharioun A, Bahadorian B, Alizadeh Sani Z. A data mining approach for diagnosis of coronary artery disease. *Comput Methods Programs Biomed* 2013;111(1):52–61. doi:10.1016/j.cmpb.2013.03.004 — SRC-06 (**partial access**).
7. Alizadehsani R, Habibi J, Hosseini MJ, Boghrati R, Ghandeharioun A, Bahadorian B, Alizadeh Sani Z. Diagnosis of coronary artery disease using data mining techniques based on symptoms and ECG features. *Eur J Sci Res* 2012;82(4):542–553 — SRC-07 (author-associated; indexed full text).
8. Tao H, Wang C, Qi H, Li H, Li Y, Xie R, *et al.* A real-time computer-aided diagnosis system for coronary heart disease prediction using clinical information. *Rev Cardiovasc Med* 2025;26(3):26204. doi:10.31083/RCM26204 — SRC-08 (read in doc 10 §3.1; not re-read here).
9. Riley RD, Ensor J, Snell KIE, Harrell FE, Martin GP, Reitsma JB, Moons KGM, Collins GS, van Smeden M. Calculating the sample size required for developing a clinical prediction model. *BMJ* 2020;368:m441. doi:10.1136/bmj.m441 — SRC-11 (via doc 05 §0.6).
10. Riley RD, Debray TPA, Collins GS, Archer L, Ensor J, van Smeden M, Snell KIE. Minimum sample size for external validation of a clinical prediction model with a binary outcome. *Stat Med* 2021;40(19):4230–4251. doi:10.1002/sim.9025 — SRC-11 (via docs 05 and 07).
11. Collins GS *et al.* TRIPOD+AI. *BMJ* 2024;385:e078378. doi:10.1136/bmj-2023-078378; Moons KGM *et al.* PROBAST+AI. *BMJ* 2025;388:e082505. doi:10.1136/bmj-2024-082505 — reporting/risk-of-bias guidance, not evidence of model quality.
12. Repository records: Gate DA 01–17, Gate PT 01–14, `docs/DECISIONS.md`, `docs/FEATURE_REGISTER.md`, `research/uci412/**` (plan + dictionary 1.1.0), `research/intake/**`, `research/audit/**` — SRC-09/SRC-10.

---

## Appendix A — verbatim evidence strings used above

*(Quotations are reproduced exactly as retrieved; ellipses mark omitted text. No patient-level value appears anywhere in this appendix.)*

**A.1 UCI-45 codebook (`heart-disease.names`, SRC-02)**

- "This directory contains 4 databases concerning heart disease diagnosis."
- "Each database has the same instance format. While the databases have 76 raw attributes, only 14 of them are actually used."
- "One file has been "processed", that one containing the Cleveland database. All four unprocessed files also exist in this directory."
- "9. Missing Attribute Values: Several. Distinguished with value -9.0."
- "10. Class Distribution: … Hungarian: 188 37 26 28 15 294 … Long Beach VA: 51 56 41 42 10 200 … Switzerland: 8 48 32 30 5 123 … Cleveland: 164 55 36 35 13 303"
- "4 sex: sex (1 = male; 0 = female)"
- "9 cp: chest pain type -- Value 1: typical angina -- Value 2: atypical angina -- Value 3: non-anginal pain -- Value 4: asymptomatic"
- "10 trestbps: resting blood pressure (in mm Hg on admission to the hospital)"
- "19 restecg: resting electrocardiographic results -- Value 0: normal -- Value 1: having ST-T wave abnormality … -- Value 2: showing probable or definite left ventricular hypertrophy by Estes' criteria"
- "37 trestbpd: resting blood pressure"
- "58 num: diagnosis of heart disease (angiographic disease status) -- Value 0: < 50% diameter narrowing -- Value 1: > 50% diameter narrowing (in any major vessel: attributes 59 through 68 are vessels)"
- "55 cmo: month of cardiac cath (sp?) … 56 cday: day of cardiac cath (sp?) … 57 cyr: year of cardiac cath (sp?)"
- "The "goal" field refers to the presence of heart disease in the patient. It is integer valued from 0 (no presence) to 4. Experiments with the Cleveland database have concentrated on simply attempting to distinguish presence (values 1,2,3,4) from absence (value 0)."

**A.2 UCI-412 / UCI-411 landing pages (SRC-03, SRC-04)**

- UCI-412: "A patient is categorized as CAD, if his/her diameter narrowing is greater than or equal to 50%, and otherwise as Normal."
- UCI-412: "Has Missing Values? No"
- UCI-412: "The Z-Alizadeh Sani dataset contains the records of 303 patients, each of which have 54 features. The features are arranged in four groups: demographic, symptom and examination, ECG, and laboratory and echo features."
- UCI-412: Variables Table — 56 rows, all cells empty ("0 to 10 of 56").
- UCI-411: "Note 1: In this extension LAD, LCX, and RCA features have been added. CAD (Last column in dataset) happens when at least one of these three arteries is stenotic. To use this dataset only one of the LAD, LCX, RCA or Cath (Result of angiography) must be in dataset and the other ones must be eliminated for classification."
- UCI-411: Variables Table — 59 rows, all cells empty.

**A.3 Detrano *et al.* 1989 (SRC-05)**

- "The reference group used to derive the model consisted of 303 consecutive patients referred for coronary angiography at the Cleveland Clinic between May 1981 and September 1984."
- "Historical data were recorded and coded without knowledge of noninvasive or angiographic test data."
- "The 4 clinical variables were age, sex, chest pain type (typical anginal, atypical anginal, nonanginal, asymptomatic) and systolic blood pressure."
- "the angiographic variable of the presence or absence of a >50% diameter narrowing (dependent variable)"
- "These groups were (1) 200 patients at the Veterans Administration Medical Center in Long Beach, California; (2) 425 patients at the Hungarian Institute of Cardiology; and (3) 143 patients at 2 Swiss university hospitals."
- "Clinical data and noninvasive test results were recorded before (and therefore without knowledge of) the coronary angiography results."
- "The data included age, sex, chest pain characteristics (as seen earlier), systolic blood pressure at rest, history of hypertension, smoking history, history of diabetes, family history, electrocardiogram at rest, serum cholesterol and fasting blood sugar."
- "Coronary angiograms were considered abnormal if there was >50% luminal narrowing of any major epicardial vessel. Histories, physical examinations and all noninvasive tests were performed within 6 weeks before the date of the coronary angiogram."
- "In these test groups, noninvasive test results were not withheld from the treating physician, and might have influenced the decision to perform coronary angiography; therefore, workup bias or angiographic referral bias was present."
- "Hungarian Institute of Cardiology: This group was drawn from all patients undergoing catheterization at the Hungarian Institute of Cardiology in Budapest between 1983 and 1987. Patients with prior infarction or valvular disease were excluded. The remaining 425 subjects made up the Hungarian test group."
- Table I note: "Disease is defined as >50% diameter narrowing".
- "As in all previous reports on this topic, angiograms were read by visual assessment of the percent diameter narrowing."

**A.4 Alizadehsani *et al.* 2013 (SRC-06, partial) and 2012 (SRC-07, author-associated)**

- 2013: "a dataset called Z-Alizadeh Sani with 303 patients and 54 features, is introduced"
- 2013: "The Z-Alizadeh Sani dataset is constructed from the information provided by 303 random visitors to Shaheed Rajaei Cardiovascular, Medical and Research Center. 216 samples had CAD and the rest were healthy."
- 2012: "Information was gathered from Shaheed Rajaei Cardiovascular, Medical and Research Center, between Fall 2011 and Winter 2012."
- 2012 Table 2: "BP (Blood Pressure) 90-190 · PR (Pulse Rate) 50-110 · Edema Yes, No · Weak Peripheral Pulse Yes, No · Lung Rales Yes, No · Systolic Murmur Yes, No · Diastolic Murmur Yes, No · Typical Chest Pain Yes, No · Dyspnea Yes, No · Functional Class 1, 2, 3, 4 · Atypical Yes, No · Non-Anginal CP (Chest Pain) Yes, No · Exertional CP (Exertional Chest Pain) Yes, No · Low Th Ang (Low-Threshold angina) Yes, No"
- 2012 Table 4: "BP2 BP<90 | 90≤BP≤140 | BP>140 … PR2 PR<60 | 60≤PR≤100 | PR>100"
- 2012 Table 7 (extract): "the number of patients with value 1 for these features and their confidences" — "Typical Chest Pain 164 0.939024 … DM 90 0.888889 … FH 48 0.75 … DLP 112 0.705357 … Dyspnea 134 0.649254 … Atypical 93 0.430108"

---

## Appendix B — precision arithmetic: complete reproduction record

**Why this appendix replaces a script.** Revision 15.0 shipped a helper script (`scripts/verify_pt15_precision_scenarios.py`) as a *proposed* deterministic-arithmetic scope extension. No explicit maintainer approval for that extension was recorded, so in revision 15.1 the script is **deleted**, and this appendix carries everything needed to reproduce every number without trusting prose and without committing executable code. If a maintainer later approves such a scope extension explicitly, this appendix can be re-instantiated verbatim.

**Scope of the arithmetic, restated.** This appendix computes exactly two things: (a) the **descriptive binomial** precision of a single outcome proportion, and (b) an **illustrative** interval width for a hypothetical AUROC. It computes **no** development sample-size requirement and **no** Riley-2021 external-validation requirement. Nothing here is a threshold, a verdict or a performance estimate.

### B.1 Constants and their provenance

| Constant | Value | Provenance |
|---|---|---|
| Cleveland records / positives | 303 / 139 | UCI-45 codebook §10 (`164 55 36 35 13 = 303`; `139 = 55+36+35+13`) — **[A1]** |
| UCI-412 records / positives | 303 / 216 | Maintainer-reported read-only audit (216 `Cad` / 87 `Normal`) — **[L1]** |
| Hungary records / positives | 294 / 106 | Codebook §10 (`188 37 26 28 15 = 294`; `106 = 37+26+28+15`) — **[A1]**; independently concordant with the audited processed-file split 188/106 — **[L1]** |
| 95 % normal quantile | `z = 1.959963984540054` | Standard two-sided 95 % |
| Proportion half-width target | `δ = 0.05` | `pmsampsize` default for the outcome-proportion criterion; used here only as an illustrative descriptive tolerance |
| Repository anchor: Cleveland | 382 | Gate PT doc 05 §5 |
| Repository anchor: UCI-412 | 315 | Gate PT doc 08 / doc 11 §5.2 |

### B.2 Formulae (verbatim, so each can be checked by hand)

**B.2.1 Descriptive binomial precision of a single proportion.** Records needed for a two-sided 95 % half-width `δ` around an anticipated proportion `φ`:

```
n(φ, δ) = ceil( (z/δ)² · φ · (1 − φ) )
```

Half-width actually achieved at `n` records:

```
δ(φ, n) = z · sqrt( φ · (1 − φ) / n )
```

This is the same expression as the `pmsampsize` *outcome-proportion* branch, which is why the anchors in B.4 reproduce exactly. **It is not a Riley-2021 external-validation criterion**; it concerns one proportion, not the precision of a model's discrimination or calibration.

**B.2.2 Illustrative AUROC interval width — Hanley–McNeil (1982) approximation only.** With scenario AUC `A`, `n₁` positives and `n₀` negatives:

```
Q₁ = A / (2 − A)
Q₂ = 2A² / (1 + A)
SE(A) = sqrt( [ A(1−A) + (n₁−1)(Q₁ − A²) + (n₀−1)(Q₂ − A²) ] / (n₁ · n₀) )
half-width = 1.959963984540054 · SE(A)
```

**Attribution and limits (corrected in 15.1).** This is the **Hanley–McNeil large-sample approximation** to the variance of the AUC estimator. It is **not** the DeLong variance estimator, and no DeLong-based result is reported anywhere in this document. The approximation assumes a particular underlying distributional model, makes no use of the observed prediction distribution, and does not model refitting, model selection, clustering or repeated-measure structure. **Actual interval width may be narrower or wider than these values**, depending on the observed prediction distributions, the estimator actually used, its assumptions, and the study design. **No direction of error is asserted and none should be inferred.** The `A` values are hypothetical **[SC]** inputs.

### B.3 Worked arithmetic (hand-checkable)

| Computation | Substitution | Result |
|---|---|---|
| Cleveland `n(φ, 0.05)` | `φ = 139/303 = 0.458746`; `(1.95996/0.05)² = 1536.5835`; `φ(1−φ) = 0.248298`; `1536.5835 × 0.248298 = 381.53` → ceil | **382** ✔ anchor |
| UCI-412 `n(φ, 0.05)` | `φ = 216/303 = 0.712871`; `φ(1−φ) = 0.204686`; `1536.5835 × 0.204686 = 314.52` → ceil | **315** ✔ anchor |
| Hungary `φ` | `106/294` | `0.360544` |
| Hungary `n(φ, 0.05)` | `φ(1−φ) = 0.230552`; `1536.5835 × 0.230552 = 354.26` → ceil | **355** (shortfall 61 vs 294) |
| Hungary `δ(φ, 294)` | `1.95996 · sqrt(0.230552/294) = 1.95996 × 0.028003` | **±0.0549** |
| Hungary `n(φ, 0.055)` | `(1.95996/0.055)² = 1269.9037`; `× 0.230552 = 292.78` → ceil | **293** |
| Cleveland `δ(φ, 303)` | `1.95996 · sqrt(0.248298/303)` | **±0.0561** |
| UCI-412 `δ(φ, 303)` | `1.95996 · sqrt(0.204686/303)` | **±0.0509** |
| Textbook control | `n(0.5, 0.05)` | **385** (0.25 × 1536.5835 = 384.146) |

### B.4 Reproduced outputs (revision 15.0 run of the since-deleted helper)

The anchor reproductions and the two tables below are the complete output. They are recorded here so that no claim in §4 H-6 or §7 depends on unavailable code.

```
--- reproducibility anchors (already published in the repository) ---
[PASS] Cleveland outcome-proportion n at +/-0.05: 382 (expected 382)
[PASS] UCI-412 outcome-proportion n at +/-0.05: 315 (expected 315)
[PASS] phi=0.5, delta=0.05: 385 (expected 385)

--- Hungary (294 records; 106 positive / 188 negative) ---
outcome proportion p            = 0.360544  (106/294)
n required at +/-0.05 (95%)     = 355   (shortfall 61)
achievable half-width at n=294  = +/-0.0549
records needed for +/-0.055     = 293

--- illustrative AUROC precision at fixed class counts (SC = scenario) ---
cohort                                A=0.70  A=0.75  A=0.80  A=0.85  A=0.90
Hungary  294 (106 pos / 188 neg)      +/-0.064  +/-0.061  +/-0.056  +/-0.050  +/-0.041
Cleveland 303 (139 pos / 164 neg)     +/-0.059  +/-0.056  +/-0.051  +/-0.045  +/-0.037
UCI-412  303 (216 pos /  87 neg)      +/-0.061  +/-0.056  +/-0.050  +/-0.042  +/-0.034

--- class counts and achievable outcome-proportion precision ---
Cleveland  positives 139  negatives 164  positive fraction 0.4587  achievable half-width +/-0.0561  n needed at +/-0.05 = 382
Hungary    positives 106  negatives 188  positive fraction 0.3605  achievable half-width +/-0.0549  n needed at +/-0.05 = 355
UCI-412    positives 216  negatives  87  positive fraction 0.7129  achievable half-width +/-0.0509  n needed at +/-0.05 = 315
```

### B.5 Reproduction without any committed code

Any reviewer can verify every figure with a calculator from B.2–B.3, or — locally, without committing anything — by evaluating the three formulae above on the constants in B.1. The two anchor checks (382, 315) exist **only** to show that this implementation agrees with numbers already published in docs 05 and 08; they are not new evidence, not validation of any dataset, and not a claim that the source counts are correct.

### B.6 Interpretation limits (binding)

1. **Descriptive only.** Every proportion figure is the precision of a **single proportion** in a fixed cohort. It is **not** a development sample-size requirement and **not** a Riley-2021 external-validation determination. The figure 355 is **not** an external-validation threshold, not a sufficiency criterion and not an adequacy verdict.
2. **Scenarios are hypothetical.** Every AUROC in B.4 is a **[SC]** input chosen only to size an interval. None is a predicted, expected, observed or borrowed performance value, none was derived from the Cleveland or UCI-412 internal exploratory results, and none may be quoted as an expectation for any model.
3. **The interval method is an approximation.** Hanley–McNeil only; no DeLong estimator was implemented or used; actual widths may differ in either direction (B.2.2).
4. **Class counts.** The Hungary and Cleveland figures are codebook figures **[A1]**; the UCI-412 figures are maintainer-reported **[L1]**. All three are aggregate counts, and none has been independently re-derived from a data file by this document.

---

## Appendix C — what this document does not do

### C.1 Data and execution

- It does **not** access, download, open or re-audit any dataset, archive member, workbook sheet or bundled documentation, and it adds no patient-level, row-level or fingerprint material of any kind.
- It does **not** fit, tune, select, evaluate, calibrate, pool, validate or transfer anything; it creates no model artefact and no prediction file.
- It ships **no executable code** in this revision: the arithmetic is recorded in Appendix B so that it can be reproduced by hand.

### C.2 Scientific claims it does not make

- It does **not** claim that the delivered Hungarian file's target or value codings are independently verified; only that the *published* convention, definitions, units and protocol timing are documented.
- It does **not** claim person-level independence between the Cleveland and Hungarian cohorts, and it does **not** characterise the 294 released records as a subset of (or as distinct from) the publication's 425-patient group.
- It does **not** claim that per-record measurement preceded angiography, and it does **not** remove the source publication's own admission of referral/work-up bias.
- It does **not** establish the direction of the six numeric-binary UCI-412 fields; concordant counts, plausible direction and clinical consistency are corroboration, not proof.
- It does **not** claim that UCI-412 has no per-variable documentation anywhere — only that none was found in the materials examined.
- It does **not** present any sample-size figure as a threshold, a sufficiency criterion or an adequacy determination, and it does **not** make a Riley-2021 external-validation determination.
- It does **not** use clinical plausibility as evidence of coding semantics.
- It does **not** rank, compare, borrow or quote the internal exploratory AUROC values of Cleveland or UCI-412, and no route preference rests on any performance metric.

### C.3 Governance

- It does **not** modify any frozen protocol, feature dictionary, registered plan, results record, decision-register entry, contract, backend, database, frontend or workflow.
- It does **not** select a final dataset, open P-1 or P-3, close any issue, or claim any supervisor, ethics or institutional approval.
- It does **not** claim readiness, external validation, clinical validity, deployability, novelty or publication value, and no such claim follows from any sentence above. P-1 remains **PENDING**, Gate PT **P-3 CLOSED**, P-5 **prohibited**.
