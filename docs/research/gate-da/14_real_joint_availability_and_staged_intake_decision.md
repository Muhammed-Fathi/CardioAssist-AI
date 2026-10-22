# 14 — Real DA-A2 Joint Availability Results and Engineering Design Decision

**Date:** 2026-10-22 | **Status:** VERIFIED local aggregate feasibility evidence + ADOPTED engineering design direction; NOT an approved prediction model, selected training features, or clinical protocol. Gate PT P-3 CLOSED.

## 1. Reproducible real local evidence

On merged main `5ea7299773018e9207ec8e5cc325758b404219ee`, the maintainer ran `python -m research.audit.availability_scenarios` against D-046-authorized DA-A2 sources with signed-off local file custody and eleven cumulative provenance records. Tool status: `READ_ONLY_DESCRIPTIVE_ONLY_NOT_TRAINING_AUTHORIZATION`, `source_files_byte_guarded=true`, `raw_cleveland_parsed=false`, `modeled_or_transformed_data=false`, `gate_pt=CLOSED`; repository clean afterwards. All originals remain intact and ignored; **no patient rows or real audit JSON have been committed**.

Four **pre-specified descriptive panels** were examined. Columns denote the number of source records with *all fields in that measurement-stage panel observed*; they are NOT numbers of subjects independently eligible for clinical prediction, trainable sample sizes, or measured performance:

| Cohort | n | History-only (age/sex/cp) | Resting (+ trestbps/restecg) | Resting + labs (+ chol/fbs) | + exercise (thalach/exang/oldpeak/slope) |
|---|---:|---:|---:|---:|---:|
| Cleveland processed | 303 | 303 | 303 | 303 | 303 |
| Hungarian processed | 294 | 294 | 292 | 261 | 95 |
| Switzerland processed | 123 | 123 | 120 | **0** | **0** |
| VA Long Beach processed | 200 | 200 | 143 | 100 | 64 |

These counts use the **hypothetical zero-unavailable sensitivity rule**, where `chol=0` or `trestbps=0` is *treated as not measured for descriptive counts only*. Source files were not edited and no recoding was applied to model inputs. The **literal-source coding** counts (zero retained as an observed numeric value) reveal the interpretation sensitivity:

| Cohort | History literal | Resting literal | Labs literal | Exercise literal | Difference from conservative lab scenario |
|---|---:|---:|---:|---:|---:|
| Cleveland | 303 | 303 | 303 | 303 | 0 |
| Hungary | 294 | 292 | 261 | 95 | 0 |
| Switzerland | 123 | 120 | **47** | **46** | **47** |
| VA Long Beach | 200 | **144** | **133** | **87** | **33** |

**Key measured implications:**
- **Swiss site:** 120/123 (97.6%) resting measurements observed, but **0/123** available at lab-inclusive stage if its 123/123 numeric cholesterol zeros represent absent measurements. Literal 47/123 does not mean laboratory cholesterol was measured: third-party dataset documentation explicitly identifies all 123 Swiss zero cholesterol entries as not measured.
- **Hungarian site:** 292/294 (99.3%) resting observations, 261/294 (88.8%) with labs, only 95/294 (32.3%) with full exercise bundle; the additional stage introduces considerable missingness.
- **VA site:** 143/200 (71.5%) resting, 100/200 (50%) with labs, 64/200 (32%) with exercise under the conservative zero-availability rule. One zero resting BP creates a 144-to-143 change; lab zero assumptions remove 33 literal-available cases. Note these are source availability frequencies, not intervention availability in routine care.
- **Cleveland processed:** all four pre-specified stage panels happen to be fully observed; separate `ca` and `thal` missingness and source raw warning still apply. Its favorable completeness is **not** a license to claim all sites or care settings are complete.

The official UCI data dictionary https://archive.ics.uci.edu/dataset/45/heart+disease defines the conventional fields and angiographic target; it does not expressly define all zero codes as missing. Secondary four-site documentation https://rpkgs.datanovia.com/datarium/reference/heartdisease.html identifies the 172 cholesterol zeros (Swiss 123 plus VA 49) as not measured. TRIPOD+AI BMJ 2024 (https://doi.org/10.1136/bmj-2023-078378) calls for transparent predictor availability and missing-data handling, representative non-overlapping evaluation and discussion of model usability; it does not by itself choose a feature set or treatment rule.

## 2. Our explicit engineering decision

**ED-DA-A2-01 — ADOPT a staged, clinician-facing *data-collection* design**:

1. **Initial consultation:** capture age, sex and `cp` where clinically appropriate; then resting BP and resting ECG as the baseline stage when actually recorded. UI reports *measurement completeness*, never a CAD probability based only on available fields.
2. **Optional laboratory stage:** record `chol` and `fbs` if already measured. Treat unexplained `chol=0` / resting BP=0 as **unavailable for proposed clinical use**, preserving raw codes. The source/clinical interpretation remains flagged for protocol review and sensitivity analysis; no automatic replacement in data files.
3. **Optional exercise stage:** capture `thalach`, `exang`, `oldpeak`, `slope` only when an actual exercise test was performed before the intended decision. Never request exercise testing merely to satisfy an ML field.
4. **Forbidden predicted-outcome proxies:** do not offer `ca`, raw angiography-derived vessels, target `num`, patient IDs or post-catheterization measures as patient-risk predictors in a proposed pre-angiography workflow. `thal` requires distinct time-of-acquisition review and is **not** in the first staged interface contract proposal.
5. **Missingness semantics in UI/API proposal:** represent absent fields as omitted/null with a distinct documented unavailable/not-measured reason **only if an existing or approved contract supports it**; retain clinically valid zero values for categorical binary features and `oldpeak`. No approved OpenAPI contract is modified by this memo. Missing-value conversion in future model preprocessing must be reversible, auditable, and fitted only inside development folds under a frozen protocol.
6. **Prediction gate:** until a clinically justified input schema and matching model have been approved and evaluated, use mock/synthetic demonstration with unambiguous labels or show **no prediction**; never imply the prototype is a deployable medical diagnostic service.

This is a *product data-flow decision*, NOT a data-driven feature-selection decision. We prefer investigating **resting assessment** as the initial multi-site *feasibility anchor*, not because these five features have established CAD predictive accuracy but because their availability is high across three sites and more manageable at VA than the exercise/lab-heavy schema. `history_only` is an information-collection fallback and has no demonstrated model utility. A reduced core-panel model is a **hypothesis to test later**, not an approved conclusion or trained artifact.

## 3. Concrete engineering backlog and acceptance criteria

| Workstream | Next implementation | Acceptance condition BEFORE any real model fitting |
|---|---|---|
| Research/AI | Draft **model-independent** structured input registry (field, source unit, categorical values, acquisition time, forbidden-if-post-Cath flag, null/zero meaning); define traceable cohort-specific missingness scenarios and source exclusions | Reviewed proposal, complete source citations and synthetic unit tests. No selection from real labels or training results |
| Backend | Add a proposed versioned **clinical intake stage contract**, structurally separate from current `POST /v1/predictions/cad-tabular` mock. Explicit stage, available measurements, nullability, provenance and no-result state; retain versioned backward compatibility | Synthetic request/response tests; invalid and missing inputs fail clearly; no real CAD output or leakage field |
| Frontend (clinician website) | Multi-step initial/resting/lab/exercise form; medically meaningful units; display available vs not-measured; never convert zero cholesterol/BP to a valid measurement silently | Synthetic UI integration; optional stages genuinely optional; no data loss; real clinical predictions disabled |
| Patient app / wearables | Maintain a **separate monitoring track** for observations; do not pass wearable values into CAD tabular model by accident | Contract tests enforce monitoring vs diagnostic separation and explicit clinician review |
| Governance/evaluation | Pre-register clinical outcome including exactly-50% stenosis boundary, timepoint, candidate cohorts, target mapping, overlap/dedup checks, split strategy, calibration/uncertainty, fold-contained preprocessing, outcome/site imbalance | One consolidated supervisor signoff of frozen P-1/P-3 Gate PT protocol; only then begin real model fitting |

**Not proven or authorized:** site-level transportability, common outcome semantics across UCI-45 and UCI-412, absence of Statlog–Cleveland overlap, patient identity alignment, fairness, calibration, performance, or clinical usefulness. Source `UCI-411` is an extension of the same 303 UCI-412 patients, not additional independent training subjects.

## 4. Decision for next handoff

**We do not need another ad hoc missing-cell audit before drafting engineering work.** Build a **synthetic-only, stage-aware intake contract / UI mock** behind existing governed APIs while the team prepares one cohesive scientific protocol and requests human signoff **only at Gate PT before real fitting**. This decision, evidence and any dissenting alternatives should be presented in the next consolidated supervisor meeting, rather than asking the supervisor to bless each engineering step.

**Decision status:** ED-DA-A2-01 ADOPTED as engineering architecture direction within current task governance; any implementation affecting approved API schemas must undergo normal owner review and separate PR; no model training or performance claims.
