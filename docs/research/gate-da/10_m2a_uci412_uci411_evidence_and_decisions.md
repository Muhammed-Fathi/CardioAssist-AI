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
