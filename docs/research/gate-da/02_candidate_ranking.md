# 02 — Candidate Ranking with Eligibility Criteria and Limitations

**Status: PROPOSED ranking for the Gate DA decision. Ranking is not
approval, and no rank authorizes acquisition.** Method: every candidate
from document 01 was scored against the *same* eligibility criteria, in
order. A candidate that fails a **hard** criterion is ineligible for that
role regardless of any other strength (sample size never compensates).

## 1. Eligibility criteria (applied in this order)

| # | Criterion | Type | Test |
|---|---|---|---|
| E1 | **Target compatibility** | Hard | Label is angiographically defined CAD *presence* compatible with T1 (document 01 §1), or the candidate is explicitly scoped to a separate named target (T2/T3/T5). Self-report, generic-CVD, and future-event labels fail T1. |
| E2 | **Official, lawful, $0 access** | Hard | Acquirable from the official source at $0 under documented terms compatible with local research use, with attribution/redistribution limits recorded. Kaggle mirrors of controlled data and undocumented-provenance copies fail. |
| E3 | **Patient independence for the claimed role** | Hard (for external-validation role) | Patients are not the same as, and not suspected duplicates of, the development cohort. Same-patient extensions and suspect recirculations fail this role. |
| E4 | **Leakage screen passable** | Hard | Label-defining / angiography-derived / post-diagnosis fields can be identified and excluded without destroying the feature set (register in document 03). |
| E5 | **Feature availability & harmonizability** | Scored | A documented dictionary (units, codings) exists or can be audited; features are knowable before the label at a definable prediction moment; a non-trivial harmonized subset exists for Strategy B. |
| E6 | **Supervisor-evidence support** | Scored | Named by GREEN papers (strongest), MAYBE papers (weaker, promotion-gated), or RED/no papers (none). GREEN approves the paper, not the dataset — this criterion never overrides E1–E4. |
| E7 | **Auditability & reproducibility** | Scored | Stable identifier/DOI, small enough for $0 local audit, missingness/overlap auditable with available (identifier-free) fields. |
| E8 | **Spectrum honesty** | Scored | Population/era/referral spectrum is documented enough to state limitations truthfully (no silent transfer claims). |

## 2. Ranking — development / internal-validation role (Strategy A)

| Rank | Candidate | E1 | E2 | E4 | E5–E8 summary | Limitations that survive ranking |
|---|---|---|---|---|---|---|
| **1 (PROPOSED primary)** | **DS-2 UCI-412 Z-Alizadeh Sani** | ✅ angiographic ≥50% binary | ✅ CC BY 4.0, official UCI (**VERIFIED**) | ⚠️ passable *after* availability audit (echo/lab/symptom timing unruled) | Richest verified feature groups; GREEN P5/P9/P15 direct; DOI-stable; no missing values per UCI (audit to confirm) | n=303, single centre/country, 216/87 balance is SOURCE-REPORTED until audited; full dictionary UNVERIFIED until Gate DA; threshold *wording* differs from DS-1 (`≥50%` vs `>50%`) — how, or whether, exactly-50% records were coded is unresolved (H-01) |
| **2 (PROPOSED primary)** | **DS-1 UCI-45 Cleveland** (within id 45) | ✅ angiographic >50%, binarized 0 vs 1–4 | ✅ CC BY 4.0, official UCI (**VERIFIED**) | ⚠️ passable after excluding `ca` (and ruling `thal`) | Literature-comparability benchmark for GREEN P1/P2/P7/P10/P14; dictionary VERIFIED from official page | 1980s referral cohort; exercise-test features constrain the prediction moment; `oldpeak` unit UNVERIFIED; missing values present; the intended development file is `processed.cleveland.data` (14 columns incl. `num`), with raw `cleveland.data` acquired for audit (document 01) |
| 3 (conditional) | DS-1 Hungary / VA / Switzerland cohorts | ✅ same `num` definition | ✅ same source | ⚠️ as Cleveland | Needed for Strategy B; Hungary largest sibling | Both formats exist per cohort (document 01): processed 14-column files (`processed.hungarian.data`, `processed.switzerland.data`, `processed.va.data`) are the candidate Strategy B formats but require audit format-verification (delimiters, missing symbols, recodings, column alignment) — never assumed identical to `processed.cleveland.data`; raw files (`hungarian.data`, `switzerland.data`, `long-beach-va.data`) serve the dictionary/identifier/missingness audit. Switzerland/VA heavy missingness (audit-gated usability); VA is a veteran population (transportability question, not noise) |
| — ineligible as independent development data | DS-2b UCI-411 | ❌ same cohort as DS-2 by source-supported provenance (E3 for any "second cohort" claim; row-level identity is an audit task, not assumed) | ✅ | ❌ LAD/LCX/RCA define label | — | Same-cohort extension only (document 01) |
| — ineligible until audit | DS-3 Statlog-145 | ⚠️ presence label, coding differs (1/2) | ✅ | ⚠️ `ca`-equivalent excluded | — | Suspect-duplicate vs Cleveland; sensitivity-only after passed overlap audit |

## 3. Ranking — genuinely independent external-validation role (Strategy B)

External validation is a **claim about a (model, cohort) pair**, not a
property of a dataset. A cohort earns this role only when *all* Strategy B
conditions hold for the pair (Phase 0 §R2-4.2): (i) target/threshold
compatibility **checked, with a documented ruling**; (ii) documented
feature mapping with identical units/definitions; (iii) patient
independence established by audit; (iv) missingness tabulated and handled
identically. Until then every entry below is **PROPOSED-conditional**.

| Rank | Candidate pair (PROPOSED) | Why this order | Blocking conditions |
|---|---|---|---|
| 1 | DS-2 model → **DS-1 Hungary**, then Cleveland (and reverse direction) | Distinct site/country/era from DS-2; same angiographic construct; largest sibling cohort first | Threshold ruling H-01 (wording `>50%` vs `≥50%`; boundary coding unresolved until data/original-source evidence exists); harmonized-feature intersection derived & versioned; duplicate audit; processed-format verification for the Hungarian file (document 04 §4) |
| 2 | DS-2 model → **DS-1 VA Long Beach / Switzerland** | Stronger spectrum stress-test (veterans; high-missingness site) | As above, plus pre-registered completeness rules — Switzerland is usable only if they pass; failure must be reported, not silently dropped |
| 3 | DS-1 (Cleveland) model → **DS-2** | Reverse direction; tests transport to a different feature culture | DS-2 dictionary audit complete; harmonized subset only; DS-2's richer features cannot be "back-filled" into a DS-1 model |
| **Never** | DS-2 ↔ DS-2b; DS-1 ↔ DS-3 (pre-audit); any Kaggle copy; DS-4/DS-5/DS-8 (different targets) | Same patients, suspect duplicates, unverified provenance, or different constructs — calling these "external validation" would be a false claim (P-5 discipline) | — |

**Consequence if no pair passes:** the project reports internal
(nested-CV) results only, labelled exactly as such, with **no**
external-validation claim. That is an acceptable, honest outcome
(Phase 0 §R2-4.2 Strategy C fallback logic; document 05 §7).

## 4. Separate-target candidates (Strategy D — never merged into T1)

| Candidate | Separate target | Rank within its own track | Gate requirement |
|---|---|---|---|
| DS-4 BRFSS 2015 (CDC official only) | T3 self-reported heart disease/attack | 1st T3 option (large, documented survey design) | Own Gate DA + own protocol (survey weights/design); Kaggle copy prohibited as source |
| DS-5 NHANES | T3 self-reported CHD/angina/MI | 2nd T3 option | Own Gate DA + protocol; public-use files only |
| DS-8 PTB-XL | T5 ECG statements | Exploratory only | Own Gate DA; licence re-verification (this session's fetch failed); patient-level splits mandatory |
| DS-6 Framingham (official) | T4 incident events | **Blocked** — controlled access (application + IRB + DUA), feasibility UNVERIFIED | Separate ethics/access track; REQUIRES APPROVAL; not in this package's request |
| DS-2b per-artery fields | T2 per-vessel stenosis | Unranked — target itself UNAPPROVED (P-1) | Supervisor ruling on T2 before any use |

## 5. Explicitly not ranked (excluded, with reason)

- **DS-6k Kaggle "Framingham" mirrors, DS-7 Kaggle CVD-70K, DS-11 Kaggle
  combined copies** — provenance/licence UNVERIFIED; exclusion is a
  scientific-integrity rule, not a preference (Phase 0 D-012).
- **DS-9 AngioCAD** — RED-paper dataset; REQUIRES APPROVAL scope decision
  (D-021) before even licence verification is relied upon.
- **DS-10 private/controlled cohorts** (incl. P3's Egyptian cohort, PINK) —
  not public; no ethics/data agreement exists; nothing in this package
  proposes contacting holders.
- **P1's merged five-dataset file** — not separately published by its
  authors (SOURCE-REPORTED); constituents must be acquired from UCI and
  de-duplicated by this project if pooling is ever approved (Strategy C).

## 6. What would change this ranking

- Gate DA audit findings (dictionary, missingness, duplicate counts,
  availability rulings) — e.g. a failed Switzerland completeness rule or
  a large Statlog overlap count demotes that candidate automatically.
- A supervisor ruling that freezes a different target (P-1) — e.g. an
  approved T2 would re-scope DS-2b; an approved T3-first strategy would
  promote DS-4. This ranking assumes T1 as instructed.
- A human D-021 decision on AngioCAD, or documented provenance for a
  mirror (considered unlikely; the burden of proof is on provenance).
