# M2a — UCI-412 / UCI-411 Audit Evidence & Scientific Decision Log

**Report ID:** M2A-REV-2026-10-22-V1  
**As of:** 2026-10-22  
**Repository status:** proposed documentation; maintainer-reported **local** read-only audit results, not CI-derived patient-data evidence.  
**Governance:** D-046 local read-only scope authorized; **Gate PT P-3 CLOSED**; final scientific protocol, supervisor sign-off and clinical validity NOT claimed.  
**Scope:** DA-A1 (UCI-412) and DA-B1 (UCI-411); DA-A2 (UCI-45) and DA-B2 (UCI-145) pending acquisition/audit.

> **Privacy:** Only aggregate counts, public metadata, and documented decisions appear here. Never add raw files, patient-level records, row numbers of discrepant cases, identifying combinations, or any individual measurements to the repository, PRs, issues or chat.

## 1. Evidence types and boundaries

| Code | Meaning | Evidence in this report |
|---|---|---|
| LOCAL-VERIFIED-BY-MAINTAINER | Tool output from a human-run local audit plus protected file hash checks, supplied to project review | The numerical results in §2 and §3. Not independently rerun by GitHub CI on real records |
| OFFICIAL-SOURCE | Public UCI repository landing page and/or related verified primary guidance | Citation and label-definition assertions in §4 |
| METHOD-GUIDANCE | Published model-research reporting / quality guidance | TRIPOD+AI (2024), PROBAST+AI (2025) |
| PROVISIONAL-DECISION | Conservative design choice made for safety and scientific validity | Modeling exclusions and next actions, not a substitute for Gate PT |
| PENDING-CLINICAL-REVIEW | Interpretation or protocol needing original source clarification / clinician-supervisor judgment | §3 unresolved discordance, measurement timing, endpoint freeze |

No source-host-independent cryptographic signature for the UCI upstream files has been established. Provenance classification remains `HUMAN_ATTESTED_NOT_INDEPENDENTLY_PROVEN_BY_LOCAL_HASH`; local SHA-256 verifies *local byte identity*, not independently authenticated upstream origin.

## 2. DA-A1 / UCI-412: confirmed local audit aggregates

**Original:** `data/raw/uci-412/Z-Alizadeh sani dataset.xlsx` (ignored).  
**SHA-256:** `90fefd4ecdb6263b3f2a260bb2b5d3b9fa92ba35d626dd56ad8c6db5fbbad163`.  
**CLI status:** `OK_READ_ONLY_AUDIT_COMPLETE`, audited `DA-A1`, original byte identical, zero patient-level rows emitted.

| Finding | Local result | Important limit |
|---|---|---|
| Active worksheet / other worksheets | `Sheet 1 - Table 1` / one header-only auxiliary worksheet | Auxiliary sheet has zero patient rows; not a second cohort |
| Record count | 303 | Angiographic diagnostic dataset; not longitudinal incident-risk ground truth |
| Columns | 55 predictors + `Cath` = 56 | UCI page says 54 features; `BBB` present in delivered workbook; source-description discrepancy explicitly documented |
| `Cath` in original | 216 exact `Cad`, 87 exact `Normal`, other/missing 0 | `Cad` -> canonical `CAD` in memory *only*; `class_distribution.raw_counts` reports canonical not raw spellings |
| Missingness | 0 detected cells, 0 affected columns | Applies only to implemented missing-token rules; not a clinical validation of every code or value |
| Duplicates | 0 exact full, 0 exact predictor, 0 near candidate pairs | A result of the implemented algorithms; does not prove patient independence |
| Suspicious values / invalid coding | 0 flagged by current rules | Tests cover selected known rules; not exhaustive range/dictionary validation |
| Explicit artery columns | 0 `LAD`/`LCX`/`RCA` | Other features still require temporal availability and coding audits |
| Echo/lab timing | 3 echo (`EF-TTE`, `Region RWMA`, `VHD`) and 14 lab features flagged | Clinical measurement timing and units still unresolved |

Local reports retained untracked:
`data/reports/uci-412-read-only-audit.json` and `.md`. The JSON and Markdown are not published; manual privacy review is required before any excerpt is shared.

## 3. DA-B1 / UCI-411: correspondence and consistency

**Original:** `data/raw/uci-411/extention of Z-Alizadeh sani dataset.xlsx` (ignored).  
**SHA-256:** `739343245c2ba578b541370217531750d8e936022f928b83e0d91756caa3ff0b`.  
**Archive:** `e97af1a18733d64fa88caa0628e5fe7ce6b2e26ec4c7ee03baade92a6f1470e8` (SHA-256), inspected `PASS_AUTHORIZED_CONTENTS`.  
**License:** UCI-411 CC BY 4.0; dated local license snapshot SHA-256 `14e70173013ae379ec3f7110e0f46ea05904048af9839f8459d6a334074de5ac`.

| Finding | Local result | Decision |
|---|---|---|
| Records | 303 in each dataset | **Do not sum to 606 independent persons** |
| Shared-column count | 56 | All shared columns compared after explicit target normalization |
| Matched rows in identical positions | 303/303 | Empirical exact agreement on shared recorded fields |
| Unordered matched rows | 303/303 | Corroborates same-cohort extension, not independent validation |
| Only-in-extension columns | `LAD`, `LCX`, `RCA` | **L-03: outcome-derived / leakage blockers for pre-angiography CAD model** |
| Cath / any stenotic artery consistency | 302 match rule; **1 does not** | Unresolved flag; **do not correct, delete, relabel, or infer clinical misdiagnosis** |
| Reader cross-check | Python stdlib OOXML parser and `openpyxl` both reproduce 302/1 | Establishes parser reproducibility **under the same rule**; does not independently validate clinical definition |
| Missingness / full-row duplicate pairs | 0 / 0 | Limited to the implemented checks |
| Unchanged originals | Verified by pre-/post-SHA-256 | No training or patient-row export |

The existing local correspondence report is `data/reports/uci-412-411-read-only-audit.{json,md}`; **keep ignored**.

**Clinical/source interpretation of the one discordance:** UCI-411 publicly states CAD at diameter narrowing **>=50%**, and `Cath` positive when *at least one* of LAD/LCX/RCA is stenotic. The currently implemented validator recognizes `Stenotic`, `CAD`, `1` for stenosis and `Normal`, `0` for absence. The single flag means one local record did not satisfy this implemented mapping; it **does not establish** an erroneous patient diagnosis or an erroneous UCI file. No real row details were published. Tracking: [Issue #15](https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/15). Clinical/source adjudication remains open; preserve the original data verbatim.

## 4. Evidence-based decisions (as of report date)

| ID | Decision, rationale, and current disposition | Evidence/status |
|---|---|---|
| REV-01 | **Use angiography-referenced binary CAD diagnosis as the provisional research endpoint (T1), not prospective CAD risk prediction.** Time horizon for a future-risk claim is absent in UCI-411/412. Formal final protocol/clinical intended use remains pending P-1 / Gate PT. | UCI-411/412: **OFFICIAL-SOURCE**, final target **PENDING-CLINICAL-REVIEW** |
| REV-02 | **DA-A1 and DA-B1 are the same cohort; no additive sample size or external validation using DA-B1.** No model fit authorized. | 303/303 shared-row equality **LOCAL-VERIFIED-BY-MAINTAINER**, UCI extension description **OFFICIAL-SOURCE**, exclusion **DECIDED** |
| REV-03 | **Retain `Cath` as provisional outcome; exclude `Cath` as predictor and exclude `LAD`, `LCX`, `RCA` from pre-angiography input.** Preserve the exact `Cad` source string; allow only explicit in-memory alias to `CAD`. | Source outcome structure **OFFICIAL-SOURCE**, code PR #14, L-03 **DECIDED** |
| REV-04 | **One discordance is an unresolved quality finding**, not a proven wrong label. Independent parser agreement ≠ independent clinical truth. No automated clinical correction or row exclusion. | 302/1 **LOCAL-VERIFIED-BY-MAINTAINER**, [Issue #15](https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/15) **PENDING-CLINICAL-REVIEW** |
| REV-05 | **No default inclusion of Echo (`EF-TTE`, `Region RWMA`, `VHD`) or the 14 flagged lab variables for a pre-angiography deployment.** They are *candidate* features only after proving available before the frozen decision time and verifying dictionary/unit semantics. Do not claim they were measured after the procedure; timing is **unknown**. | Source lists feature groups; timing **UNVERIFIED**, exclusion-by-default **PROVISIONAL-DECISION** |
| REV-06 | **Keep cross-dataset threshold ambiguity open.** UCI-412/411 pages use `>=50%`; UCI-45 raw `num` documentation uses `>50%`. Individual exact-boundary cases and compatibility have not been established. No pooling and no external validation claims from simple column renaming. | UCI source descriptions **OFFICIAL-SOURCE**, harmonization `H-01` **PENDING-CLINICAL-REVIEW** |
| REV-07 | **DA-A2 is the next authorized read-only acquisition/audit; DA-B2 remains overlap investigation only.** For UCI-45: inspect **all** raw/processed files and historical excluded archive members, do not bypass `STOP_REQUIRES_REVIEW`. Treat repository `303 instances` headline as insufficient to conclude four cohorts total 303. | D-046 **AUTHORIZED AUDIT ONLY**, acquisition/audit results **NOT YET VERIFIED** |
| REV-08 | **No model fitting, feature selection, hyperparameter tuning, performance evaluation, calibration, SHAP/LIME based on real data** without P-3 supervisor protocol approval. A synthetic mock is not clinical evidence. | `docs/DECISIONS.md`, human-ratified D-046, `D-046-EP` not approved — **DECIDED / GATE CLOSED** |
| REV-09 | Reporting to follow **TRIPOD+AI 2024** (transparent predictor timing/outcome definition, sample size, validation, limitations); quality and risk-of-bias review to follow **PROBAST+AI 2025** (participants, predictors, outcome, analysis). Do not use reporting-checklist compliance as proof of low bias. | **METHOD-GUIDANCE**, implementation after Gate PT approval |
| REV-10 | **Never upload original dataset files, patient rows, case-specific discordance details, or unreviewed local audit reports** to GitHub/third-party services. Share only privacy-reviewed aggregates. | D-046 privacy scope — **DECIDED** |

### Why detection ≠ medical readiness

- Technical validation checks *known schema, selected code/range rules and duplicates*. It cannot prove correct diagnoses, correct units, pre-outcome feature timing, population representativeness, independence or generalizability.
- Prevalence `216/303 = 71.3%` is the **fraction in this selected sample**, not prevalence in the population and not a calibrated individual disease probability.
- A 303-record, 55-predictor dataset poses feasibility/overfitting questions, and local tuning/testing cannot be authorized or defended until a frozen endpoint, feature eligibility and evaluation protocol exists.

## 5. Gates, open items and actionable continuation

**Completed locally (maintainer attestation):**
- [x] D-046 scope authorization for DA-A1/DA-A2/DA-B1/DA-B2 **read-only** audit.
- [x] DA-A1 and DA-B1: official-source acquisition recorded with human-attested provenance and CC BY 4.0 snapshots.
- [x] DA-A1+DA-B1: parser/label-sheet bugfixes merged in [PR #13](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/13) and [PR #14](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/14); local synthetic regression suite reported **65 passed**; three CI workflows confirmed successful at PR #14 head.
- [x] Local DA-A1 and combined DA-A1+DA-B1 metadata-only audit and independent parser cross-check; originals unchanged.
- [x] L-03 follow-up [Issue #15](https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/15) created with aggregates only.

**Next actions in order, without waiving gates:**
1. **DA-A2/UCI-45**: maintainer downloads only from official UCI to `E:\UCI_Downloads` (outside repo); record ZIP SHA-256 and complete inventory; run `inspect-archive --dataset-id DA-A2 --auth-manifest data/manifests/gate_da_authorization.local.json`; **stop and review excluded historic files** before any extraction. No uninspected/automatic extraction, no patient-level material in chat. 
2. Verify CC BY 4.0 and DOI `10.24432/C52P4X` on official page; capture Git-ignored license snapshot. Extract only exact authorized raw/processed files after gated archive approval; preserve originals. 
3. Append DA-A2 entries to the *existing* local provenance while preserving DA-A1 and DA-B1, take hash-verified non-overwriting backup, validate entire manifest. Use the local authorization manifest, never the pending committed template. 
4. Run DA-A2 read-only audit; interpret raw↔processed correspondence, missing-token semantics, code validity, duplicates, and leakage/timing; retain immutable audit outputs under ignored `data/reports/` with human privacy inspection.
5. Audit DA-B2/UCI-145 **only for overlap investigation** against Cleveland, with the same authorization/provenance controls and no independence assumption.
6. For **Issue #15**, retain unchanged labels/inputs while clinical reviewer clarifies artery coding, the isolated discordance and intended use. No case-identifying evidence in public/shared logs.
7. Freeze proposed target population, diagnostic decision moment, eligible predictors, missingness handling, cohort compatibility and evaluation design; present a concise Gate PT dossier to supervisor. **Only after P-3 sign-off** consider fitting/clinical performance evaluation.

**Current stop boundary:** D-046 permits acquisition and read-only auditing of the four named sources only. Dataset acquisition is **not** in progress automatically: execution must occur on the maintainer's Windows system. This report and code review cannot access those local originals. No clinical dataset was downloaded by GitHub or assistant.

## 6. Citations (primary sources and independent guidance)

1. UCI-412 Z-Alizadeh Sani, DOI 10.24432/C5Q31T, dataset + label definition, https://archive.ics.uci.edu/dataset/412/z+alizadeh+sani
2. UCI-411 extension of Z-Alizadeh Sani, DOI 10.24432/C5461K, source statement that the extension adds LAD/LCX/RCA and only one artery/Cath outcome should be retained for classification, https://archive.ics.uci.edu/dataset/411/extention+of+z+alizadeh+sani
3. UCI-45 Heart Disease, DOI 10.24432/C52P4X, multi-cohort details and raw vs 14-column processed documentation, https://archive.ics.uci.edu/dataset/45/heart+disease
4. Collins et al. (2024), **TRIPOD+AI**, BMJ 385:e078378, DOI 10.1136/bmj-2023-078378, https://www.bmj.com/content/385/bmj-2023-078378
5. Moons et al. (2025), **PROBAST+AI**, BMJ 388:e082505, DOI 10.1136/bmj-2024-082505, https://www.bmj.com/content/388/bmj-2024-082505
6. Primary repo governance: `docs/DECISIONS.md`; toolchain: `research/audit/{registry.py,validators.py,duplicates.py,provenance.py,reporting.py}`; local untracked reports listed above (not copied to repo).

## 7. Change log

- **2026-10-22 V1:** consolidated confirmed local DA-A1 and DA-B1 aggregate audit evidence, two parser/label corrections, L-03 unresolved case, public clinical-label references, explicit diagnosis-not-future-risk recommendation, predictor timing/leakage exclusions, Gate PT boundaries, and DA-A2 acquisition checklist. **No raw patient records, model weights, models, or local manifests committed.**

## 8. DA-A2 / UCI-45 official archive inventory and selective-extraction decision (2026-10-22, V2)

**Status: STOP_REQUIRES_REVIEW, no extraction yet.** Maintainer acquired the official UCI-45 ZIP outside Git and inspected ZIP *central-directory metadata only*; patient-level payloads were not read, printed, or committed.

- Local file: `E:\\UCI_Downloads\\heart+disease.zip`; SHA-256 `b17cd273da9ce1caa4710fce80227ea454d4dbf9fcbc8e6a9121672751563adc`; **128,894 bytes**; expanded inventory **673,802 bytes**.
- **23 entries:** **9/9** strictly authorized root dataset files, **2** unapproved historical datasets (`new.data`, `reprocessed.hungarian.data`), **3** root metadata (`Index`, `WARNING`, `bak`), **2** auxiliaries (`ask-detrano`, `cleve.mod`), and **7** costs paths (`costs/`, `costs/Index`, `costs/heart-disease.README`, `costs/heart-disease.cost`, `costs/heart-disease.delay`, `costs/heart-disease.expense`, `costs/heart-disease.group`).
- The original auditor rejected `costs/` unconditionally; separate metadata-only inspection listed all 23 members and found **zero flags under that supplementary structural check**, without certifying clinical data safety or granting extraction.
- Official UCI dataset page documents the `Costs` directory for test-cost metadata, distinct from the four cohort records; see https://archive.ics.uci.edu/dataset/45/heart+disease.
- **Engineering decision REV-11 (proposed in this PR):** permit classification of only the nine specifically named auxiliary members as **excluded, NEVER extracted** for **DA-A2 only**. Do not permit any unrecognized nested path/directory or wildcard exception, and preserve checks for archive SHA-256, symlinks, traversal, case collisions, limits and unauthorized extra files.
- The full **11 excluded-member acknowledgement**, 23-member inventory, exact ZIP fingerprint and size, nine authorized filenames, human reviewer name and review timestamp must match an explicit, Git-ignored `data/manifests/archive_reviews/uci-45-archive-review.json` prior to extraction. Merely inspecting the archive or merging this code PR does **not** authorize automatic extraction.
- All selective extraction uses exact root-level names. `costs/Index` is NOT classified as root `Index`.
- Synthetic regression tests cover the known layout, unknown path rejection, tampered review document, selective nine-file extraction and overwrite refusal.

**Review outcome:** Code remediation prepared for review, no real UCI-45 files extracted. Scientific suitability, cohort overlap, H-01 target harmonization and Gate PT remain unresolved.

## 9. DA-A2 real read-only audit stopped on legacy raw Cleveland encoding (2026-10-22; partial-audit remediation pending PR)

**Observed locally, evidence VERIFIED:** Under ratified D-046 and validated combined provenance (11 records: DA-A1 1, DA-B1 1, DA-A2 9), the maintainer ran `run-audit --datasets DA-A2` against original, SHA-matched UCI-45 files. The audit **FAILED_CLOSED** with `format_validation_error`: `utf-8 codec can't decode byte 0x8e in position 58079: invalid start byte` in the unmodified `cleveland.data`. No reports were produced by this run. The user's byte-integrity recheck concluded that protected originals and prior reports were unchanged; Git main remained clean; Gate PT CLOSED.

**Primary-source documentation verified from local official ZIP:** `WARNING` (407 bytes, SHA-256 `01ae7cb6ab43a387b206f7127ce81869639d9d3076d447c12d7df17ad583f954`) reports historical source-side raw `cleveland.data` transfer/copy damage while describing `processed.cleveland.data` as *apparently usable* for the conventional 14-attribute task. See https://archive.ics.uci.edu/ml/machine-learning-databases/heart-disease/WARNING and [Issue #18](https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/18). An invalid UTF-8 byte demonstrates only **non-UTF8-valid bytes under this parser**; alone, it cannot identify a patient record error, ascertain historical encoding, or justify automated repair.

**Scientific/engineering decision R-DA-A2-RAW-01 (proposed, pending PR review):**

- Preserve original `cleveland.data`, its content hash, license and provenance; do not replace, transcode, lossy-decode, delete, re-encode, infer missing patient values, or assert corruption at an individual row.
- **Default audit remains FAIL_CLOSED.** Provide a separate, explicit DA-A2-only `--quarantine-raw-cleveland` mode for a *partial read-only audit* that does **not** parse raw Cleveland or compare it to processed Cleveland. The known local asset fingerprint must match; all nine files, including the quarantined one, remain provenance-verified and byte-guarded.
- In partial mode, audit **all four processed** cohorts, **only the other three raw** cohorts, and **only three** raw-to-processed correspondence pairs. Emit a typed `quarantined_raw_files` record and DA-A2 `REQUIRES APPROVAL` status; never describe the entire UCI-45 audit as complete or verified.
- Any additional malformed raw/processed data, schema violation, target problem, or privacy-scanner finding **still stops the run**. No generic `errors=replace`, `ignore`, permissive format handling or hidden file exclusion.
- Keep complete raw Cleveland audit, interpretation of its original data, and clinical suitability **unresolved** under [Issue #18](https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/18).
- Synthetic-only regression tests must demonstrate strict default failure and explicit partial-mode behavior. **Do not use actual patient data in CI**.

**Status at time of writing:** PR-based remediation is being reviewed; no partial audit result yet. No model training/evaluation; Gate PT remains CLOSED. All local data and reports remain under Git-ignored `data/`.

## 10. DA-A2 correspondence audit — aggregate-only follow-up (2026-10-22, engineering change pending review)

The first successful **partial** DA-A2 local real-data audit (PR #19 raw Cleveland quarantine) reported 4 processed cohorts, 3 non-Cleveland raw cohorts, and 3 positional raw-to-processed comparisons. Aggregate results supplied by the maintainer:

| Cohort | Processed rows | Raw rows | Processed missing cells | 13-predictor positional exact matches |
| --- | ---: | ---: | ---: | ---: |
| Cleveland | 303 | QUARANTINED | 6 | NOT EVALUATED |
| Hungary | 294 | 294 | 782 | 1 |
| Switzerland | 123 | 123 | 273 | 1 |
| VA Long Beach | 200 | 200 | 698 | 192 |

**Inference boundary:** Matching row counts do not demonstrate corresponding patients. These unexpectedly low positional agreements do not establish source corruption or that the datasets are unrelated. Prior audit reports had no order-independent/raw-vs-processed multiset diagnostic and the raw file may contain 76-attribute conventions while the processed set has 14. Explanations including ordering, missingness coding, different transforms/versions, or actual record differences remain OPEN until specifically tested.

**Engineering follow-up proposed in PR:** augment the existing read-only correspondence function with:
- Order-independent whole-row 13-predictor multiset overlaps, then exact original-`num` and 0-vs-1..4 binarized-`num` 14-column overlaps (with duplicate-safe multiplicities)
- Per-conventional-predictor positional value agreements and unordered value multiset overlaps (aggregated counts only)
- Strict report-schema allowlists and bound checks so no patient signature, clinical values, IDs, pair mappings, or row snippets can enter committed output
- Synthetic permutations, differences, duplicate checks and privacy-schema tests

**Decision status:** PENDING local execution/review. The proposed metrics can distinguish findings consistent with reordering from differences of values/distributions; they cannot prove patient identity or harmonization correctness. Keep raw Cleveland quarantined, four processed cohorts candidates only, all A2 evidence `REQUIRES APPROVAL`, and Gate PT **CLOSED**. Never sum raw and processed rows as independent patients. No model training, automatic recoding or clinical claim.


## 11. DA-A2 order-independent correspondence: real local aggregate findings (2026-10-22, after PR #22 merge)

**Run and provenance evidence (local maintainer logs; VERIFIED for report generation only):** Main synchronized to merge commit `1acda84e5b44c59f46810f5f4630b6bc6975a3fe`. D-046 local-only authorization and eleven cumulative provenance entries validated. Read-only alignment audit completed successfully on **DA-A2** with raw Cleveland quarantined, after **88 passing synthetic/toolchain tests**. Local outputs: `data/reports/uci-45-da-a2-alignment-audit.json` and `data/reports/uci-45-da-a2-alignment-audit.md`, both Git-ignored and **not committed**. Audit reported `originals_byte_identical=true`, `patient_level_rows_emitted=0`, `model_fitting_performed=false` and Gate PT **CLOSED**. New output metrics are **aggregate-only**, and the complete DA-A2 evidence remains **PARTIAL / REQUIRES APPROVAL**.

| Cohort | Raw vs processed rows | Exact 13 predictors at same position | Unordered 13-predictor multiset match | Unordered exact original-`num` 14-col match | Unordered binary-`num` 14-col match |
|---|---:|---:|---:|---:|---:|
| Cleveland | raw QUARANTINED / processed 303 | not evaluated | not evaluated | not evaluated | not evaluated |
| Hungary | 294 / 294 | 1 | **293** | 224 | **293** |
| Switzerland | 123 / 123 | 1 | **121** | 121 | **121** |
| VA Long Beach | 200 / 200 | 192 | **192** | 192 | **192** |

**Further aggregated feature-level evidence (normalized 13 conventional predictors, counts only):**
- **Hungary:** unordered single-feature distributions match 294/294 for **12 of 13**, but `ca` matches **293/294**. This is consistent with a dominant row-order change plus a limited feature-level discrepancy. The drop from 293 binary-target full-row matches to 224 exact-original-target full-row matches is compatible with recoding of positive `num` severity categories to a binary label, **not an authorization to alter labels**.
- **Switzerland:** unordered single-feature distributions match 123/123 for **12 of 13**; `thal` matches **121/123**. Whole-profile 121/123 unordered agreement is consistent with substantial ordering difference plus at least limited data-value disagreement; individual patient identity and correctness remain unknown.
- **VA:** most feature distributions and positional counts match 200/200; `slope` has **199/200** positional and multiset agreement, `thal` **193/200**. Whole-profile agreement is **192/200** regardless of order. This is more consistent with field-level differences in approximately this scope than a broad row permutation, but **not** a basis for determining exactly which patient entries or historical version is correct.

**Critical interpretation boundary:** A multiset overlap of 293/294 does **not** independently identify which person corresponds to whom; duplicates and same-valued clinical profiles can exist. The 224 vs 293 target match difference **does not prove a precise number of individual target relabelings**. Marginal per-feature count overlaps alone cannot show patient-level source correctness, legitimate target recoding or clinical comparability. No new data were inferred/imputed, no rows were repaired, no files were combined and no training/evaluation was performed.

**Decision register — DA-A2-CORR-02 (read-only evidence; suitability remains pending):**
1. **Accept as verified aggregate finding**: strongly order-independent overlap for Hungary and Switzerland; high already-positionally-aligned VA; non-exact raw-vs-processed profiles and likely target coding differences remain unresolved.
2. **Do not** treat raw/processed files as distinct cohorts; do not create a 2x sample count, match or publish patient identities, transform original labels or silently repair `ca`/`thal`/`slope`.
3. **Next controlled evidence step:** read existing local strict-schema alignment JSON **without patient rows** for processed and raw target distributions, per-column missingness (especially study endpoints/available predictors), suspicious/invalid codings, and duplicates; inspect original UCI `heart-disease.names` coding descriptions. Report aggregate-only, preserve output paths and hashes, then resolve target harmonization H-01 with clinical supervisor before any PT freeze.
4. **Still blocked**: raw Cleveland historical integrity ([Issue #18](https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/18)); unexplained differences and target meaning ([Issue #21](https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/21)); DA-B2/UCI-145 overlap pending; any model-fit, training, feature selection, calibration, interpretation or performance claim before Gate PT P-3 signoff.

**Decision state:** Data-acquisition integrity verified; partial and scoped read-only correspondence audit verified as executed; **clinical dataset suitability not approved**. Raw Cleveland remains quarantined, with original sources preserved and Gate PT CLOSED.


## 12. DA-A2 target distribution, missingness and duplication: local read-only evidence (2026-10-22)

**Provenance and privacy checks:** Maintainer executed strictly metadata-only summary of the pre-existing `data/reports/uci-45-da-a2-alignment-audit.json` on clean `main`, checked 11 cumulative provenance records under D-046, validated the strict report schema, original ZIP/raw Cleveland hashes and unchanged protected evidence, and confirmed Gate PT **CLOSED**. No new dataset files, trained models or patient-level records were produced.

| Cohort | Processed rows | Processed source `num` counts (0 / 1 / 2 / 3 / 4) | Raw source `num` counts (0 / 1 / 2 / 3 / 4) | Processed missing cells of 14 columns | Processed exact full-row excess duplicates |
|---|---:|---|---|---:|---:|
| Cleveland | 303 | 164 / 55 / 36 / 35 / 13 | **Not audited — raw quarantined** | 6 (0.14%) | 0 |
| Hungary | 294 | 188 / 106 / 0 / 0 / 0 | 188 / 37 / 26 / 28 / 15 | 782 (19.00%) | 1 |
| Switzerland | 123 | 8 / 48 / 32 / 30 / 5 | 8 / 48 / 32 / 30 / 5 | 273 (15.85%) | 0 |
| VA Long Beach | 200 | 51 / 56 / 41 / 42 / 10 | 51 / 56 / 41 / 42 / 10 | 698 (24.93%) | 1 |

**Source corroboration and crucial inference limits:** The original official `heart-disease.names` dictionary (https://archive.ics.uci.edu/ml/machine-learning-databases/heart-disease/heart-disease.names) lists the four **raw** class-count vectors above exactly (see section 10). Its `num` variable description says **0: <50% diameter narrowing**, **1: >50%** (sections 7–8), while its broader conventional goal is 0 versus 1–4. This historical wording does **not** harmonize UCI-45 to the UCI-411/412 **≥50%** convention and does not establish cases at exactly 50%; H-01 stays OPEN. Hungary `processed` has a binary 0/1 target, whose positive 106 equals the sum of raw positives 37+26+28+15; 293/294 predictor-plus-binary unordered profiles matched in the preceding audit. These are strong *aggregate* signals of binary recoding, **not** proof of patient identity, clinical threshold harmonization, or that the remaining mismatched observation is an erroneous diagnosis.

**Processed missingness by named field (only nonzero counts; source report definitions retained):**
- Cleveland: `ca=4`, `thal=2`; all other conventional predictor slots and `num` have zero recorded missing cells.
- Hungary: `ca=291`, `thal=266`, `slope=190`, `chol=23`, `fbs=8`, and one each in `exang,restecg,thalach,trestbps`; total 782.
- Switzerland: `ca=118`, `fbs=75`, `thal=52`, `slope=17`, `oldpeak=6`, `trestbps=2`, and one each in `exang,restecg,thalach`; total 273.
- VA Long Beach: `ca=198`, `thal=166`, `slope=102`, `oldpeak=56`, `trestbps=56`, `exang=53`, `thalach=53`, `chol=7`, `fbs=7`; total 698.

**Audited raw-vs-processed missingness differences** (aggregate counts, *not attributed to patients*): Hungary raw `ca=290` missing vs processed 291; Switzerland raw `thal=50` vs processed 52; VA raw `thal=159` vs processed 166 and `slope=101` vs processed 102. The original raw 76-attribute missing-cell counts (Hungary 7,953; Switzerland 2,433; VA 4,088) **are not directly comparable** to processed 14-column missing totals because they cover radically different denominators. No invalid categorical-coding counters were reported for the four processed cohorts; this does **not** rule out all suspicious values or clinical data-quality defects. Processed whole-row duplicate *excess records* were Hungary 1 and VA 1; **never delete or merge patients automatically**.

**Scientific feasibility constraints (not feature selection):** `ca` is angiography-dependent and pre-designated a leakage risk (L-01); `thal` and exercise-test variables require availability/timing rulings (L-06/L-07). Hungary, Switzerland and VA do **not** support unqualified 13-predictor complete-case claims: the single marginal `ca` missing count alone bounds all-13-predictor complete records to at most 3/294, 5/123 and 2/200, respectively; actual joint complete-case counts have **not** been measured and may be lower. Removing, imputing or prioritizing any feature would constitute a future protocol choice, **not approved** by Gate DA. Similarly, the 14-column cell-completeness percentage does not show the joint availability of a clinical feature set. Distributional class imbalance and differences across cohorts must be considered when eventually judging transportability; no model prediction or performance can be inferred.

**Decision DA-A2-QA-03 — evidence VERIFIED as metadata, dataset suitability DEFERRED:**
1. Preserve original raw and processed files and the local-only reports without repair; raw Cleveland remains quarantined under Issue #18.
2. Register Hungarian `num` change as **source-consistent binary recoding**; do not use it as proof of a common clinical threshold, and keep H-01 unresolved.
3. Flag missingness/feature availability and raw-vs-processed differences for separate methodology review; do not assume 14 columns are jointly present or that repeated profiles are the same patient.
4. Next: quantify explicitly audited joint completeness **only within a supervisor-reviewed, pre-specified set of clinical timepoint assumptions** (or submit bounded descriptive completeness with current marginals), inspect `ca`, `thal`, stress testing and suspicious-value flags before freezing any Gate PT protocol. Keep DA-B2 Statlog overlap pending under its separate read-only approval scope.
5. Do not treat UCI-411 extension as additional patients; do not claim independent external validation from UCI-45, alter or relabel data, fit/select/evaluate models, or open Gate PT without supervisor P-3 signoff.

**Status:** Local read-only metadata audit success; original input bytes unchanged; scientific clinical suitability **NOT APPROVED**; Gate PT **CLOSED**.


## 13. DA-A2 suspicious-value and angiography-field coding flags: local aggregate review (2026-10-22)

**Evidence and safety:** The maintainer read **strict-allowlisted aggregate metadata** from the already validated DA-A2 local alignment report; Git remained clean, original files and provenance were unchanged, no patient records were read or printed, and Gate PT remained **CLOSED**. The `suspicious_values` detector is a selective heuristic; an empty result is **not a guarantee of data correctness**.

| Processed cohort | Rows | `chol` <= 0 | `oldpeak` < 0 | `trestbps` <= 0 | Exact full-row excess duplicates | Near-duplicate candidate pairs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Cleveland | 303 | 0 | 0 | 0 | 0 | 0 |
| Hungary | 294 | 0 | 0 | 0 | 1 | 0 |
| Switzerland | 123 | **123** | **11** | 0 | 0 | 0 |
| VA Long Beach | 200 | **49** | **1** | **1** | 1 | 1 |

**Source-document interpretation:** The original UCI `heart-disease.names` defines `chol` as **serum cholesterol mg/dl**, `trestbps` as resting blood pressure **mm Hg** and `oldpeak` as exercise-induced ST depression relative to rest; it specifies historical missing-value code `-9.0`, **not an explicit dataset-wide convention that zero cholesterol is missing** (https://archive.ics.uci.edu/ml/machine-learning-databases/heart-disease/heart-disease.names, attribute list and section 9). Consequently, Switzerland's 123/123 `chol=0` values are **physiologically implausible literal measurements** and strongly suggest undocumented structural missingness, non-measurement or a coding convention; which is true is **UNVERIFIED**. The current parser correctly preserves zero instead of silently imputing, but its reported processed-cell `missingness` percentage *understates potential effective clinical missingness* **if** zeros represent unavailable measurements. VA has 49/200 nonpositive cholesterol values and one nonpositive resting-BP value requiring the same type of independent review. Negative `oldpeak` counts indicate numeric values requiring clinical/measurement semantics review; they do not establish automatically erroneous observations, and they must **not** be clipped to zero.

**Raw angiographic field metadata are measurements of values, not people:** Hungary had 314 classified `discrete_code_0_1_2` non-missing field entries, Switzerland 1,230, and VA 1,996 plus 1 `other_numeric` entry. These counts span the ten named raw per-vessel fields and **must not** be read as patient counts or as proof of target threshold; UCI source notes the `num` status is angiographic and has historical `<50` versus `>50` wording. The isolated VA nonstandard numeric value requires an aggregate-only controlled investigation of source representation, not a patient-level publication, autocorrection, target derivation or diagnostic reclassification.

**Evidence distinction and gate decisions:**
1. **VERIFIED**: printed aggregate counts, historical dictionary definitions, and preserved-byte audit results.
2. **UNVERIFIED**: whether Swiss/VA zero-cholesterol and VA zero resting BP encode absent measurement; validity of negative oldpeak in their data-collection conventions; clinical equivalence of raw vessel codes; UCI-45 versus UCI-412 `num` threshold harmonization.
3. **NOT AUTHORIZED**: converting zero to missing, excluding samples, applying feature transformations, dropping columns, treating multiple raw and processed versions as independent cohorts, model training or evaluation.
4. **Follow-up control:** arrange source/dictionary evidence review with supervisor for laboratory and exercise-test availability, triage `chol` / `oldpeak` / `trestbps` flags and angiographic leakage, then design a **pre-specified** analysis of conditional feature completeness. Keep H-01, L-01/L-06/L-07 and Issue #21 OPEN. Cleveland raw remains quarantined under Issue #18.

**Decision DA-A2-QA-04:** The observed zero-valued lab/BP fields are unresolved, high-impact clinical data-quality flags; cohort readiness and all-13-predictor completeness **NOT APPROVED**, and Gate PT stays **CLOSED**. No raw data or local report is included here.


## 14. DA-A2 cross-version zero-value investigation (real local read-only aggregate evidence, 2026-10-22)

**Safeguards verified:** Maintainer used the authorized D-046 local-only audit context, the previously validated DA-A2 alignment report, and SHA-256 integrity checks on the authorized sources, manifest and archive. The original Cleveland raw file was **not parsed**. All protected bytes were unchanged, no patient-level record printed or fitting/evaluation done, and Gate PT **CLOSED**.

| Cohort | Raw versus processed comparable? | Cholesterol: missing / zero / negative | Resting BP: missing / zero / negative | Oldpeak: missing / zero / negative |
|---|---|---|---|---|
| Cleveland processed (n=303) | NO — raw quarantined | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 99 / 0 |
| Hungary (n=294) | YES — aggregate counts equal in both formats | 23 / 0 / 0 | 1 / 0 / 0 | 0 / 189 / 0 |
| Switzerland (n=123) | YES — aggregate counts equal in both formats | **0 / 123 / 0** | 2 / 0 / 0 | 6 / 42 / 11 |
| VA Long Beach (n=200) | YES — aggregate counts equal in both formats | **7 / 49 / 0** | **56 / 1 / 0** | 56 / 40 / 1 |

**What this establishes:** All these observed numeric zero, negative, and coded-missing frequencies are already present in the 76-attribute Raw files for Hungary, Switzerland, and VA. Their appearance cannot be attributed only to the later 14-column Processed files. These are **frequency comparisons**, not patient-identity mappings or proof of record-level equality. The original source may contain placeholder conventions; there is no approval to modify or reinterpret any recorded patient value.

**Clinical interpretation to resolve:** The original UCI heart-disease.names dictionary defines cholesterol in mg/dl and the historical raw missing sentinel as -9.0; it does not establish that a numeric zero in cholesterol is a valid measured concentration or a universal missing-value code. Therefore, **Swiss 123/123 zero cholesterol** is physiologically implausible as a literal clinical measurement and is a high-priority structural-missingness / encoding question with status **UNVERIFIED**. VA has 49 zero cholesterol values and one zero resting BP in both formats. The original audit missing-cell rates exclude these numeric zeros; if a future independently justified coding rule treats some as unavailable, *effective clinical completeness* may be lower. **No zero-to-null conversion, clipping, filtering, or imputation was conducted or authorized.** Negative oldpeak values (Swiss 11, VA 1) require source/clinical convention review, not automatic clipping; a zero oldpeak value is not itself automatically invalid.

### 14.1 Provisional dataset-suitability triage (NOT model authorization)

| Processed cohort | Observed evidence | Provisional disposition | Unresolved scientific constraints |
|---|---|---|---|
| Cleveland (303) | 6 of 4242 cells formally missing; no current suspicious-value flags; raw source warning | **CONDITIONAL CANDIDATE for methodology review** | Raw Cleveland integrity under Issue #18; referral population, target definition, leakage (ca), availability/timing (thal, stress tests), possible overlap with Statlog UCI-145 |
| Hungary (294) | Binary processed target; 293/294 unordered raw-versus-processed 13-predictor+binary target match; 782 missing cells | **CONDITIONAL — LIMITED FEATURE AVAILABILITY** | ca missing 291/294, thal 266/294, slope 190/294, raw/processed ca difference, historical target recoding and timing |
| Switzerland (123) | 121/123 unordered predictor match; 273 formally missing cells; cholesterol zero for **all 123** | **DEFER conventional full-feature protocol** | Unresolved 0-cholesterol convention, ca missing 118/123, fbs missing 75/123, thal missing 52/123, class imbalance (8 zero/115 nonzero), raw/processed thal discrepancy |
| VA Long Beach (200) | 192/200 positional and unordered matches; 698 formally missing cells; 49 zero cholesterol and one zero resting BP | **DEFER conventional full-feature protocol** | ca missing 198/200, thal 166/200, slope 102/200, 49 zero cholesterol, BP zero, oldpeak/timing, raw/processed thal/slope differences |

**Decision DA-A2-QA-05:** These classifications are **triage labels for supervisor review**, not final dataset inclusion/exclusion, feature selection, imputation instructions, independent-validation claims, or Gate PT approval. Alternative clinically pre-specified input schemas remain unassessed; none is authorized here. The small all-13-feature complete-case upper bounds driven by ca alone (Hungary <=3, Switzerland <=5, VA <=2) must **not** be treated as observed joint complete-case totals. Keep raw/processed versions of each cohort linked as representations, never add their row counts as new patients.

### 14.2 Required next scientific decision

1. Research supervisor to resolve P-1 primary clinical endpoint, measurement timing, and H-01 stenosis-threshold wording (>50% versus >=50%) with source-verified evidence.
2. Review original UCI acquisition notes and clinical availability for numeric zero in Swiss/VA cholesterol, VA resting BP, and negative oldpeak; distinguish unknown coding from proven error.
3. Before any reduced schema or complete-case audit, agree on allowed pre-outcome predictors and explicitly address ca angiographic leakage (L-01), thal (L-06), and exercise-related tests (L-07).
4. Only with a documented analysis definition, run a separate approved descriptive *joint* completeness audit (and assess possible inter-cohort/Statlog overlap) using aggregate output, no row publication.
5. Preserve source files, original hashes, and local-only reports; Issues #18 and #21 remain OPEN; no model training, selection, explanation generation, calibration, or evaluation while Gate PT P-3 is CLOSED.

**Status:** Read-only observational evidence VERIFIED from local aggregates; clinical coding and dataset suitability **NOT APPROVED**, Gate PT **CLOSED**.


## 15. Executed stage-availability analysis resolves next step from §§14.1–14.2 (2026-10-22)

A subsequently authorized **real local D-046 read-only DA-A2 joint-availability run completed successfully** following merge PRs #23 and #24 (main `5ea7299773018e9207ec8e5cc325758b404219ee`). The module strictly guarded original file bytes, read only the four authorized **processed** site files, kept raw Cleveland unparsed, printed only aggregate descriptive stage counts, performed **no transformations or model fitting**, and reported Gate PT `CLOSED`. The user's console showed a clean Git main after execution.

**Jointly observed counts under hypothetical zero-unavailable rule (chol=0 or trestbps=0 treated as not measured for counting only; NOT changed in the data):**

| Processed cohort (n) | age/sex/cp | + resting BP and ECG | + chol and fasting glucose | + exercise-test measurements |
|---|---:|---:|---:|---:|
| Cleveland (303) | 303 | 303 | 303 | 303 |
| Hungary (294) | 294 | 292 | 261 | 95 |
| Switzerland (123) | 123 | 120 | **0** | **0** |
| VA Long Beach (200) | 200 | 143 | 100 | 64 |

**Literal-source-coded sensitivity comparison:** Switzerland has 47/123 lab-stage and 46/123 exercise-stage complete records **only if all numeric cholesterol zeros are counted as observations**, despite an independent dataset source describing Swiss zero cholesterol as unmeasured. VA has 144 resting / 133 lab / 87 exercise literal records vs 143 / 100 / 64 in hypothetical-zero-unavailable scenario. Hungary (292 / 261 / 95) and Cleveland (303 / 303 / 303) are unchanged. Identical stage count at Cleveland does not demonstrate quality or predictive value.

**Decisions made by engineering team today:** We will prioritize a **stage-aware clinician intake architecture** with initial/resting information as the initial cross-site feasibility anchor and optional lab/exercise sections, while preserving missingness reasons and keeping outcome-leaking features out of proposed pre-Cath inputs. Site-specific actual predictive model performance and common-label compatibility remain untested. We explicitly **do not** declare the history-only or resting bundle an approved model feature set: the results concern missingness, not predictive value or patient-level transportability. The complete rationale, citations, implementation plan, and acceptance criteria are in [14_real_joint_availability_and_staged_intake_decision.md](14_real_joint_availability_and_staged_intake_decision.md).

**Research handoff change:** The §14.2 request for a predefined joint-completeness analysis is now **satisfied for four declared descriptive source-availability panels**. The unresolved decisions about clinical target, outcome timepoint, exact 50% stenosis boundary, true missing-zero conventions, fairness, site shifts, and Statlog overlap are not solved by this. Continue synthetic-only engineering of a stage-aware data contract and clinical UI mock under usual software review. Pre-training Gate PT remains CLOSED and human P-3 signoff is required for any fitting, feature selection or evaluation. No datasets or local reports committed.
