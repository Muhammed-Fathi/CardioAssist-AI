# 11 — DA-A2 UCI-45 Clinical Suitability Review Packet

**Status: PROPOSED FOR HUMAN REVIEW — NO DATASET APPROVAL, NO MODEL TRAINING.**

**Research-team recommendations have now been established independently** in [12 — evidence-based decisions](12_research_team_evidence_based_decisions.md). Rows marked UNFILLED below refer **only to genuinely clinical sign-off or protocol-freeze decisions**, not permission requests for each source-check, read-only audit or technical review. The team proceeds with all already-authorized tasks and brings its defended approach for final clinical review.
**Evidence date:** 2026-10-22. **Governance:** D-046 permits local read-only metadata auditing; Gate PT P-3 remains CLOSED. No patient-level data included in this packet. All numerical observations below are scoped to the maintained UCI-45 files, not an inference-ready clinical population.

## Purpose and exact scope

Convert the real local aggregate DA-A2 read-only findings documented in [cumulative §§9–14](10_m2a_uci412_uci411_evidence_and_decisions.md) into auditable clinical/scientific decisions. Each question must have a named decision-maker, external/source rationale and explicit sign-off; no checkmarks or empty fields imply approval. Raw Cleveland is source-warned and **quarantined**. Raw and Processed files are representations of their named cohort, **not independent extra patients**.

## Real source observations requiring review (aggregates only)

| Cohort | Processed records | Class distribution (0 vs nonzero) | Source-defined missing cells in 14 cols | Zero cholesterol | Critical caveat | Triage, not authorization |
|---|---:|---:|---:|---:|---|---|
| Cleveland | 303 | 164 / 139 | 6 (0.14%) | 0 | Source WARNING for corrupt raw; processed appears usable but not independently clinically validated | CONDITIONAL CANDIDATE |
| Hungary | 294 | 188 / 106 (processed binary) | 782 (19.00%) | 0 | Raw five-class num differs from binary processed label; ca missing 291, thal 266, slope 190 | CONDITIONAL, RESTRICTED AVAILABILITY |
| Switzerland | 123 | 8 / 115 | 273 (15.85%) | **123 / 123** | ca missing 118, fbs missing 75, thal missing 52; oldpeak negative 11 | DEFER conventional full-feature use |
| VA Long Beach | 200 | 51 / 149 | 698 (24.93%) | **49 / 200** | ca missing 198, thal missing 166, slope missing 102; one BP zero | DEFER conventional full-feature use |

**Real local cross-version verification:** Hungary, Switzerland and VA have identical aggregate missing/zero/negative counts for cholesterol, resting BP and oldpeak in their Raw and Processed representations. Cleveland raw was never parsed. This does **not** establish per-patient matching. Hungary has 293/294 order-independent 13-predictor+binary-target matches; Switzerland 121/123; VA 192/200. These are **profile multiset overlaps**, not identifiable record mappings. The original 76-attribute Raw data are not extra validation cohorts. Existing fields ca and raw per-vessel outputs pose major target leakage risk.

**Important:** The 14-column formal missing-cell percentages count parser-recognized missing markers, **not** unknown conventions such as zero cholesterol. A hypothesis that zero signifies missing requires primary-source/clinical evidence; do not implement it speculatively. The near-zero availability of ca is a separate reason the unmodified full 13-predictor schema is unsuitable without a protocol.

## Human decisions required BEFORE Gate PT

| Review ID | Question / evidence required | Decision and evidence reference (to fill by clinician/research supervisor) | Status |
|---|---|---|---|
| P1-TARGET | Define intended clinical question, patient population, prediction time point and the angiographic CAD endpoint. Distinguish contemporaneous classification from future-event risk. | **UNFILLED** | PENDING |
| H-01 | Reconcile original UCI-45 num wording (>50%) with UCI-411/412 Cath threshold wording (>=50%). Verify source semantics and exactly-50 boundary policy; do not guess from vessel-value counts. | **UNFILLED** | PENDING |
| L-01 | Confirm that angiography-derived ca, vessel stenosis fields, cath-derived targets, identifiers, and post-outcome features cannot enter pre-Cath prediction. | **UNFILLED** | PENDING |
| L-06/07 | For thal, exercise ECG/oldpeak, echo, labs and vitals: document acquisition timing, clinician-entry availability and test population at decision time. | **UNFILLED** | PENDING |
| QA-ZERO | Obtain reliable original data-collection/coding documentation (or human attestation with limitations) for 123 Swiss cholesterol zeros, 49 VA cholesterol zeros and 1 VA resting BP zero. Determine whether missing placeholders are legitimate; no automatic coding. | **UNFILLED** | PENDING |
| QA-OLDPEAK | Clinically review Swiss 11 and VA 1 negative oldpeak observations and validate source exercise-test convention before proposing any exclusion or transformation. | **UNFILLED** | PENDING |
| QA-MISSING | Choose a pre-registered *clinically available predictor set* and a fully specified descriptive joint-completeness analysis; report effective n and class balance by cohort. No ad-hoc feature selection. | **UNFILLED** | PENDING |
| COHORT/OVERLAP | Verify UCI-45 site differences, referral/case-mix shifts, raw/processed coding discrepancies, and UCI-145 Statlog overlap before any assertion of independent external validation. | **UNFILLED** | PENDING |
| QA-CLEVELAND | Decide disposition of historical raw Cleveland corruption warning; processed Cleveland may be reviewed independently but is not clinically certified by passing a parser. | **UNFILLED** | PENDING |

## Evidence and decision capture rules

- Reviewer must append a **date, role and source/document reference** for each decision, distinguishing *APPROVED*, *REJECTED* and *DEFERRED*. No personal signatures or protected patient data in git.
- Preserve a protected, local signed decision record when required; the public repository should contain only an appropriately redacted summary.
- Approval of an audit or this packet never substitutes for protocol-freeze signoff. **Do not** clean data, change null handling, choose predictors, harmonize labels, train, tune, calibrate, compute SHAP/LIME, score outcomes or claim clinical validity before Gate PT.
- Raw Cleveland remains quarantined under [Issue #18](https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/18); unresolved quality/identity issues remain under [Issue #21](https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/21).
- New protocol changes after a clinical freeze need dated approval and amendment tracking. No single cohort is currently certified for external validation.

## Gate handoff

**Current decision:** *DATASET SUITABILITY DEFERRED; GATE PT CLOSED.* After complete clinical signoff, the research team may propose an explicitly authorized read-only joint-completeness follow-up using the approved timepoint/feature definitions, with metadata-only outputs and Git-ignored originals. Any training/evaluation awaits an additional, explicit supervisor-approved Gate PT protocol.
