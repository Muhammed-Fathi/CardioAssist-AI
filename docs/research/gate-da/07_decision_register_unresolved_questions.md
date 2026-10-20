# 07 — Decision Register: Unresolved Questions

**Status: OPEN register. Nothing below is decided by this package.**
IDs are local to this package (DQ-*) and cross-reference the governing
registers (`docs/DECISIONS.md` D-/P- items, Phase 0 D-011…D-033,
contracts Q1–Q14). "Blocks" names the first step that cannot proceed
without an answer. Owners are *roles*, not named people — naming
individuals is a human act.

## 1. Scientific questions

| ID | Question | Blocks | Owner / gate | Current evidence |
|---|---|---|---|---|
| DQ-SCI-1 | Is **T1** (cross-sectional angiographic CAD presence, binarized as in H-02) confirmed as the primary target, and are T2/T3/T5 formally deferred as separate tasks? | Gate PT freeze; all modelling | Supervisor + research lead (P-1/D-006) | PROPOSED only (Phase 0 §4.2, document 05 §1) |
| DQ-SCI-2 | H-01 ruling: are UCI-45 (`>50%`) and UCI-412 (`≥50%`) labels *identical / reconciled / related-but-not-identical*, and can exactly-50% records be identified in the acquired files? | Strategy B external validation; any pooling | Gate DA audit → Gate PT | Threshold wording **VERIFIED** different; reconciliation **UNVERIFIED** until data exist |
| DQ-SCI-3 | Per-feature availability rulings for UCI-412's 54 features (esp. echocardiography and any treatment-adjacent fields) and for `thal` (L-06): what is knowable before the angiography decision, and what is the frozen prediction moment? | Feature dictionary; clinician-input spec finalization | Gate DA audit + clinician reviewer + Gate PT | Groups VERIFIED; per-feature timing UNVERIFIED |
| DQ-SCI-4 | `oldpeak` unit and all DS-2 lab/echo units/codings from the acquired dictionary — ratified or explicitly left UNVERIFIED? | Any schema/unit assertion; harmonized mapping | Gate DA audit | `oldpeak` unit UNVERIFIED (official page states none) |
| DQ-SCI-5 | Duplicate/overlap findings: UCI-45 cross-cohort duplicates; Statlog↔Cleveland counts; resolution rule (which record is retained)? | Splits; Statlog's role; all "n patients" claims | Gate DA audit → Gate PT rule | UNVERIFIED (identifier-free data limit what can be proven — the audit must state that limit) |
| DQ-SCI-6 | Switzerland (and VA) completeness: do pre-registered completeness rules pass, or is a cohort excluded by rule? | Strategy B cohort list | Audit proposes rules; Gate PT freezes | UNVERIFIED until audit |
| DQ-SCI-7 | GREEN full-text verification (validation design, deployment, wearable data, calibration, external cohort — with page/section evidence) + broader literature search: is the proposed research gap real? | Any novelty/gap/publication claim (D-010/D-025) | Research lead | NOT DONE. Recorded paper numbers remain SOURCE-REPORTED; P7/P14 red-flag scores unresolved (Phase 0 §F-2) |
| DQ-SCI-8 | Is a T2 per-vessel stenosis task (UCI-411 arteries as targets) ever in scope? | Any use of DA-B1 beyond dictionary audit | Supervisor (P-1 family) | UNAPPROVED; leakage register L-03 governs meanwhile |
| DQ-SCI-9 | Subgroup/fairness feasibility: will sex/age/site cells meet the ≥30-patient/≥10-events-per-class minimums at n≈303? | Subgroup reporting promises | Gate PT (after audit counts) | UNVERIFIED until audit counts exist |

## 2. Access, licensing, and privacy questions

| ID | Question | Blocks | Owner / gate | Current evidence |
|---|---|---|---|---|
| DQ-ACC-1 | Gate DA itself: are DA-A (and DA-B) authorized, by whom, on what date, for exactly which files? | Any download | Named human authorizer (P-2/D-031) | **OPEN** — document 04 is the request |
| DQ-ACC-2 | Download-day licence snapshots confirm CC BY 4.0 (or reveal changed terms) for ids 412/45/411/145? | Lawful use; redistribution of *derived* artifacts | Acquirer at download (document 04 G3) | VERIFIED as listed 2026-10-20; snapshot still required |
| DQ-ACC-3 | Attribution mechanics: how will CC BY attribution + UCI citation be rendered in model cards, papers, and any future UI "about this model" surface? | Publication; model-card release | Research lead + Gate PT | UNDECIDED (licence permits use with credit; the *form* of credit is ours to document) |
| DQ-ACC-4 | AngioCAD (DS-9): may a RED paper's public dataset be considered as data (not evidence)? | Even licence verification reliance for DS-9 | Human scope decision (D-021) | REQUIRES APPROVAL; Zenodo terms UNVERIFIED this session |
| DQ-ACC-5 | Framingham/BioLINCC: does the team have (or can it obtain at $0) the IRB evidence + DUA + application the controlled track requires? | Any T4 question | Supervisor + institution | Feasibility UNVERIFIED; **not requested** in this package |
| DQ-ACC-6 | Local storage custodianship: who holds acquired files, on which machines, with what backup/deletion practice? (Benchmark data are de-identified, but handled as patient-level research data; re-identification prohibited.) | Acquisition day | Named acquirer + research lead (document 04 §3) | Rules PROPOSED; custodians unnamed |
| DQ-ACC-7 | May *derived* artifacts (harmonized datasets, trained weights, SHAP outputs) be shared, and under what terms, given CC BY source terms + DATA_POLICY's no-patient-data-in-git rule? | Replication package; artifact sharing | Research lead + supervisor at Gate PT/M4 | UNDECIDED; default = code+configs only, no patient-level derivatives leave local storage |
| DQ-ACC-8 | P3's private Egyptian cohort (PINK): promotion of the paper, and separately any ethics/data agreement — is either pursued? | Any local-cohort work | Human promotion + ethics agreement | NOT PURSUED in this package; no contact authorized |

## 3. Integration and platform questions

| ID | Question | Blocks | Owner / gate | Current evidence |
|---|---|---|---|---|
| DQ-INT-1 | Real feature-schema identity (Q1): exact `feature_schema_id`, feature list, types, units, ranges, codings for the first real model — created contract-first under **new** identifiers (never `mock_*`)? | Any real inference; frontend clinical forms | Contract review after Gate DA+PT | OPEN (contracts Q1). Document 06 §2 is a plausibility spec only |
| DQ-INT-2 | Which prediction moment does the first real model serve, and does its UI show/hide the exercise-test block accordingly (L-07)? | Frontend form design; model card wording | Gate PT + clinician (P-4) | OPEN (= DQ-SCI-3's moment freeze) |
| DQ-INT-3 | Clinician-approved wording for categories, explanations, and score rendering (incl. uncalibrated/calibrated labels)? | Any clinician-facing display of real output | Named clinician reviewer (P-4) | OPEN; conservative fallback applies |
| DQ-INT-4 | Entitlement workstream boundaries (planning-only approval): Free = 2 successful AI uses per account lifetime; Doctor Trial = 14 days of eligible patient-role features via doctor-issued code, then return to Free with remaining lifetime quota; Premium = full eligible patient access, locally simulated, no live payments. **Confirm explicitly:** entitlement never alters clinical input definitions, never substitutes for clinician confirmation (`clinician_entry`), and is not doctor–patient linking or clinical authorization. | Parallel platform PR (not this one) | Platform workstream + maintainer | Planning approval SOURCE-REPORTED in the tasking for this package; **not implemented here**; the confirmation column is for that workstream's PR to record |
| DQ-INT-5 | Auth/RBAC, durable idempotency (Q8), consent lifecycle, patient records, DB expansion sequencing vs the research track — which lands first, and what must the research artifacts (model registry entries, provenance) look like for that backend? | M1b follow-on slices | Maintainer + backend lead (separate authorizations) | OPEN; M1b.1 deliberately stored opaque references only. Research track must not pre-empt these designs |
| DQ-INT-6 | Model-serving mechanics for a future real artifact: registry format, artifact storage (out of git), versioning/rollback, and how `validation_status` transitions (internal → externally evaluated → externally calibrated) are reviewed? | M3 integration | Backend + research leads, contract-first | PROPOSED patterns exist (blueprint 04/05); nothing approved for real artifacts |
| DQ-INT-7 | Frontend ownership/handoff: frontend team owns full React/Flutter apps; M1a.3 thin local demos remain deferred/resequenced (D-045). What input-spec *format* (this package's §2 table vs a future schema document) does the frontend team want frozen for planning? | Frontend planning (not clinical forms) | Frontend team + research lead | Document 06 PROPOSED as that planning input; no clinical freeze implied |

## 4. Standing non-decisions (recorded so they are not mistaken for gaps)

- **No performance target exists.** Recorded literature scores are not
  benchmarks to beat (L-09); the project's first honest numbers will be
  its own internal/external estimates under the frozen protocol.
- **No external-validation or clinical-readiness claim is available**
  at any point in this package's scope (P-5: NOT MADE — prohibited).
- **No dataset substitution rule exists.** Refusal or failure of a named
  candidate never authorizes falling back to Kaggle mirrors, private
  data, or RED-scope datasets (document 04 §6).
