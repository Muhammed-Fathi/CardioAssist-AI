# M3a — UCI-412 (Z-Alizadeh Sani) Source-Specific CAD Research Benchmark — Specification and Internal-Research Authorization Proposal

> ## `PROPOSED — NOT FROZEN — NOT AUTHORIZED — NOT SUPERVISOR-APPROVED`
>
> - **Status:** implementation + proposal draft. Nothing in this document authorizes a real-data run.
> - **Work item:** milestone **M3a** (source-specific UCI-412 research benchmark).
> - **Gate PT P-3:** **CLOSED** (requires supervisor sign-off) · **P-1:** PENDING · **P-5:** prohibited · **D-047 (Cleveland):** unchanged.
> - **Code:** `research/uci412/` (new package) · **Tests:** `tests/uci412/` · **Output banner (real runs):** `INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED`
> - **Target of the benchmark:** presence of angiographically referenced CAD in a source cohort — **not** future event risk, **not** a clinical prediction model, **not** a `MOCK_SYNTHETIC` replacement.

**This document does not approve anything.** It records what was implemented, what was tested synthetically, what cannot be established from the available source documentation, and the exact decision a named human must make before the first real workbook is opened on the maintainer's own Windows machine.

### Evidence labels used below

| Label | Meaning |
|---|---|
| **[CODE]** | Implemented in `research/uci412/` at the commit containing this document. |
| **[TEST]** | Exercised by a synthetic test in `tests/uci412/`. Synthetic tests are software evidence only. |
| **[AR]** | Repository/audit fact carried from Gate DA (`docs/research/gate-da/`), not re-derived here. |
| **[LIT]** | Secondary literature (the source paper's feature table, journal reproductions). Not an official UCI codebook. |
| **[GAP]** | Not established. Must not be filled by inference, and is not silently defaulted. |

---

## 1. Purpose

M3a builds one **source-specific** research benchmark for the UCI-412 (Z-Alizadeh Sani) CAD dataset: a strict adapter, versioned feature schemas, a bounded offline nested-CV harness, adversarial tests, an exact experiment-metadata record, and a separately reviewable internal-research authorization proposal.

It exists because D-047 covers **Cleveland only**. Reusing that authorization, or pooling Cleveland with UCI-412, would be a governance and scientific error. UCI-412 must be its own development/replication question with its own frozen protocol (Gate DA R-MD-03).

### 1.1 Non-goals

- No production model, no `/v1` contract change, no artifact admission, no model serving.
- No external validation, no independent-cohort claim, no publication or novelty claim.
- No pooling with Cleveland, Hungary, VA, or Switzerland; no reuse of UCI-411 rows.
- No patient-level SHAP/LIME, no patient-facing risk percentage, no fabricated risk horizon.
- No feature selection driven by correlation, univariate association, or evaluation results.
- No modification of the frozen D-047 Cleveland runner, its plan, or its reported results.

---

## 2. Source identity and frozen provenance

| Field | Value | Evidence |
|---|---|---|
| Dataset ID | `DA-A1` | [AR] |
| Source | UCI Machine Learning Repository id **412**, *Z-Alizadeh Sani* | [AR] |
| Exact filename | `Z-Alizadeh sani dataset.xlsx` | [AR] |
| Permitted local path | `data/raw/uci-412/Z-Alizadeh sani dataset.xlsx` | [CODE] |
| SHA-256 (audited reference) | `90fefd4ecdb6263b3f2a260bb2b5d3b9fa92ba35d626dd56ad8c6db5fbbad163` | [AR] |
| Licence | CC BY 4.0 (`10.24432/C5Q31T`) | [AR] |
| Records | **303** | [AR] |
| Predictors | **55** + target `Cath` (56 columns) | [AR] |
| Classes | **216** `Cad` · **87** `Normal` | [AR] |
| Missing cells | 0 reported by the source; blanks are nevertheless handled | [AR]/[CODE] |

**The landing page says "54 features" while the delivered workbook has 55 predictors.** Both facts are registered verbatim; the discrepancy is documented, never silently resolved.

**UCI-411 is the same 303 participants.** It is never an independent dataset, its `LAD`/`LCX`/`RCA` columns are outcome definitions, and no row from it may enter this benchmark. Because the source contains no participant identifier, **participant independence cannot be proven** and must never be claimed.

The audited SHA-256 is an integrity cross-check, **not** a substitute for local D-046 provenance: a real run must independently hash the local file and match it against the protected provenance record *and* the locally signed M3a authorization.

---

## 3. Target definition and mapping

- Source tokens are case-sensitive: **`Cad` → 1**, **`Normal` → 0**. Any other token, any numeric cell, any blank, and any surrounding whitespace is rejected. There is no fuzzy match, no case folding, and no default class.
- The label means **angiography-referenced CAD presence as defined by the source**, reported as diameter narrowing of at least 50 %. It is **not** a future-event risk, and no time horizon is invented.
- **Threshold ambiguity stays open.** The UCI-45 Cleveland convention is *> 50 %* narrowing; UCI-412 is documented at *≥ 50 %*. These are not the same rule and are not harmonised anywhere in this code.
- `Cath`, `LAD`, `LCX`, `RCA`, and every identifier/administrative field are prohibited as predictors at the adapter level ([CODE], [TEST]).

---

## 4. Strict source adapter

`research/uci412/adapter.py` ([CODE], [TEST]).

**Structure**

- exactly one **data-bearing** worksheet; extra header-only/blank sheets are tolerated but never merged; two data sheets fail closed;
- exact registered 56-column **set** with exact spelling; duplicate normalised headers fail closed; unknown, prohibited, or identifier columns fail closed;
- column *order* is accepted in any order and recorded (`header_order_matches_registered_profile`), because access is strictly by header name; an unregistered order cannot silently change which values are read;
- row width must equal the header width; the data row count must equal **303**.

**Values**

- numeric columns accept only numeric cells — text is never coerced (`"58"` fails);
- categorical columns accept only registered tokens; unknown tokens, numeric cells in `Y`/`N` columns, and tokens with surrounding whitespace fail closed;
- the UCI-45 missing markers `?`, `-9`, `-9.0` are rejected as wrong-source signals;
- blanks in admitted columns become `NaN` and are **imputed inside training folds only**; a fully blank admitted column fails closed; a blank target fails closed;
- values outside a wide **plausibility guard** (adult physiology, data-integrity ranges such as `Age ∈ [1, 120]`, `BP ∈ [40, 300]`, `PR ∈ [20, 250]`, `BMI ∈ [10, 80]`) fail closed; values outside the *source-reported typical* range are counted, not rejected;
- **no** value repair, row deletion, duplicate resolution, winsorising, or unit conversion is performed, and the audit block records `value_repair_or_row_deletion_performed: false`.

**Immutability and privacy**

- the file is opened read-only, its bytes hashed before and after parsing, and a changed file aborts the run ([CODE]);
- only the *(row, panel)* matrix and a binary target leave the adapter; no row, cell value, or patient-level structure is returned, logged, or raised;
- every error message is patient-safe and is covered by a sentinel test that asserts source values are never echoed ([TEST]).

---

## 5. Versioned feature schemas

`research/uci412/schemas/uci412_feature_dictionary.v1.json` (schema `uci412_research_feature_dictionary` **v1.0.0**) plus the in-code allowlist in `feature_schema.py` and the frozen plan ([CODE]).

Each of the 56 source columns carries: position, group, role, kind, clinical meaning, unit **and unit-evidence status**, source domain, availability at the decision moment, missing semantics, leakage risk, input owner, evidence, uncertainty, admission status, panel membership, exclusion reason, vocabulary, and plausibility guard. A JSON-only edit cannot admit a new predictor or flip a blocked panel to executable — the loader rejects it ([TEST]).

### 5.1 The Basic Clinical Input Panel (ordered, executable candidate)

Panel `uci412_basic_clinical_v1` v1.0.0 — 16 columns, all recorded at clinical intake by history, examination, or vital-sign measurement:

| # | Column | Role | Unit | Admission rationale |
|---|---|---|---|---|
| 1 | `Age` | numeric | years | demographic, measured at intake |
| 2 | `Sex` | categorical | — | demographic |
| 3 | `BMI` | numeric | kg/m² | anthropometric measurement |
| 4 | `DM` | binary | — | medical history |
| 5 | `HTN` | binary | — | medical history |
| 6 | `Current Smoker` | binary | — | history |
| 7 | `EX-Smoker` | binary | — | history |
| 8 | `FH` | binary | — | family history |
| 9 | `DLP` | binary | — | history |
| 10 | `BP` | numeric | mmHg (single-value systolic likely, **unverified**) | vital sign |
| 11 | `PR` | numeric | beats/min (source notation "ppm", **unverified**) | vital sign |
| 12 | `Typical Chest Pain` | binary | — | symptom characterisation |
| 13 | `Atypical` | binary | — | symptom characterisation |
| 14 | `Nonanginal` | binary | — | symptom characterisation |
| 15 | `Exertional CP` | binary | — | symptom characterisation |
| 16 | `Dyspnea` | binary | — | symptom |

16 reference-coded parameters (12 binary + 4 numeric). The panel is an **ordered allowlist**; membership is duplicated in code so the JSON cannot expand it.

The panel is deliberately **parsimonious**: it covers the conventional clinical CAD-likelihood inputs (age, sex, chest-pain characterisation, risk-factor history, vital signs) and leaves secondary comorbidity, functional class, the remaining examination findings, resting ECG, laboratory values and echocardiography to registered-but-blocked panels. This is a prespecified design choice made **before** any outcome was examined — not a claim that those fields are unavailable at the bedside, and not a result-driven selection.

### 5.2 Registered but blocked panels

| Panel | Columns | Status |
|---|---|---|
| `uci412_basic_plus_resting_ecg_v1` | 23 (basic + 7 resting-ECG findings) | `REGISTERED_BLOCKED` — ECG acquisition time relative to angiography is not documented in the source |
| `uci412_expanded_clinical_v1` | 28 (basic + additional history/examination/functional class) | `REGISTERED_BLOCKED` — definition/scale evidence is secondary only |
| `uci412_basic_plus_laboratory_v1` | 30 (basic + 14 laboratory values) | `REGISTERED_BLOCKED` — laboratory timing and assay units are unverified |

Blocked panels are registered so a reviewer can see the exact candidate set, but **no configuration can select them for fitting**: the runner requires the frozen plan, and the plan binds the executable panel only.

### 5.3 Exclusions and why

| Excluded | Reason |
|---|---|
| `Cath` | target, never a predictor |
| `LAD`, `LCX`, `RCA` | UCI-411 angiography outcome definitions (L-03); absent from DA-A1 |
| `Weight`, `Length` | deterministic redundancy with `BMI` (BMI = weight / height²) |
| `Obesity` | categorical annotation of BMI with an unverified threshold |
| `EF-TTE`, `Region RWMA`, `VHD` | echocardiography timing relative to angiography is unverified (L-08); not registered in any panel |
| `Function Class`, `LowTH Ang`, examination findings other than vitals | registered in the expanded (blocked) panel only — secondary-literature definitions, no official codebook |

### 5.4 Vocabulary (fail-closed, recorded, never silently renamed)

- binary: `Y`/`Yes` → 1, `N`/`No` → 0 (the observed raw spelling is counted per column in the run audit);
- `Sex`: `Male` → 1, `Fmale`/`Female` → 0 (reference coding is arbitrary and documented);
- ordinal (blocked panels only): `Function Class` 1–4, `VHD` `N`/`Mild`/`Moderate`/`Severe`;
- anything else fails closed. The authoritative spellings remain **[GAP]** until a human inspects the local workbook; the adapter is deliberately strict so a mismatch stops the run instead of being silently approximated.

### 5.5 What cannot be sourced from the official documentation

The UCI landing page supplies group membership, the record count, the target rule, and the licence — **not** per-field definitions, units, acquisition timing, or coding. Per-field semantics above therefore rest on the source paper's table as reproduced in secondary literature **[LIT]**, and every field is marked with an explicit uncertainty string. This is the honest blocker: the schema is *registered and executable as an internal exploratory protocol*, not *verified against an official codebook*.

---

## 6. Offline training and evaluation harness

`research/uci412/{models,evaluation,config}.py` ([CODE], [TEST]).

| Element | Registered choice |
|---|---|
| Outer CV | repeated **stratified 5-fold**, 4 repeats, fixed seeds `20261024–20261027` |
| Inner CV | stratified **5-fold** per outer fold, seed `outer + 211 + 1013 × fold` |
| Preprocessing | **inside** the pipeline: training-fold median imputation + standardisation (logistic only); training-fold most-frequent imputation + fixed-vocabulary reference one-hot encoding; unseen categories are an error; all-missing training column is an error; **no** variance or univariate filtering; no global preprocessing |
| Families | prevalence baseline (`prior`), L2 logistic regression (liblinear, `C ∈ {0.1, 1, 10}`, `max_iter 2000`), constrained random forest (200 trees, depth `{3, 5}`, leaf `{5, 10}`, `max_features = sqrt`, `n_jobs = 1`) |
| Reserved | `gradient_boosting_reserved` is a named extension point with **no implementation**; requesting it raises |
| Selection | inner-CV mean AUROC only; logistic preferred within a **0.01** tolerance of the best family (simplicity rule); selection never sees assessment-fold data |
| Threshold | fixed **0.5**, exploratory only, **never tuned** |
| Metrics | AUROC, AUPRC/average precision, sensitivity, specificity, accuracy, Brier score, confusion matrix at 0.5, calibration-in-the-large intercept, calibration slope, 5-bin quantile reliability curve |
| Uncertainty | participant-level percentile bootstrap **within one repeat** (500 resamples, seed `outer + 500009`), explicitly conditional on the fitted fold models; repeats reuse the same participants, so no pooled k-repeat inference and no naive CI across repeats |
| Negative control | label permutation before the entire nested procedure, seeds `20262004–20262006`; AUROC ≥ 0.9 is a blocking leakage alarm, ≥ 0.7 a warning; result is a smoke test, **not** a formal permutation p-value |

Additional runtime guard: `assert_pipeline_contract` refuses any estimator whose preprocessing, imputer strategy, category vocabulary, unseeded encoder policy, or single-threaded forest deviates from the registered contract ([CODE], [TEST]). Model seeds, fold plans, and prediction arrays are fixed and read-only; repeated runs are bitwise identical on the same machine and package pins ([TEST]).

The random forest is single-threaded on purpose; nested parallelism is not used, so results do not depend on scheduler behaviour.

---

## 7. Experiment-metadata record

Every real run writes `data/uci412-experiments/<run-id>/report.json` (private, Git-ignored) containing, at minimum:

- experiment ID `CAI-UCI412-CAD-BENCHMARK-V0.1`, protocol status, report banner;
- dataset/source ID, exact relative path, source SHA-256 and byte size, provenance/licence/manifest hashes;
- Git commit SHA and commit timestamp; per-file and aggregate **package fingerprints** of every code/protocol file that can influence the run;
- protocol version, feature-schema ID/version, panel ID/version, preprocessing contract;
- model families, hyperparameters, CV strategy, seeds, threshold rule;
- Python/numpy/scipy/scikit-learn/joblib/threadpoolctl versions and platform;
- metrics, calibration diagnostics, uncertainty interpretation, negative-control aggregates, leakage checks;
- cohort aggregates (`303` / `216` / `87`) and **no** patient-level values;
- sample-size planning arithmetic and its explicit non-adequacy status;
- failed-run and limitation records — including the optional operator-maintained `data/manifests/uci412_failed_runs.local.json` list of short, single-line notes about earlier stopped runs (never patient-level content; malformed notes fail closed); `$0`/local-CPU status; every claim flag set to `false`.

Row-aligned out-of-fold probabilities are written to the **same protected local directory** as `predictions.csv` for audit only — one row per participant per repeat, with repeat seed and outer-fold number, so the file can be checked against the registered fold plan. The aggregate report never contains them, and both files are rejected by the repository's artifact scan.

**Failed runs.** A run that stops before its report (preflight failure, source change, leakage alarm) is recorded by the operator in `failed_runs` on the next successful run; the harness never fabricates a success record, and a leakage alarm discards results and writes nothing.

---

## 8. Execution model

| Command | Where | What it does |
|---|---|---|
| `python -m research.uci412 describe` | anywhere | prints the registered panels, exclusions, planning arithmetic, and blockers; reads no data |
| `python -m research.uci412 dry-run` | anywhere (synthetic only) | generates 303 synthetic rows in memory, runs the same adapter + nested CV + negative control with a **reduced smoke fit budget**, writes nothing |
| `python -m research.uci412 preflight` | local Windows only | validates runtime, Git-ignored storage, clean worktree, D-046 DA-A1 audit chain, the separate M3a authorization, frozen hashes, and source hash/size **without parsing rows** |
| `python -m research.uci412 run` | local Windows only | requires the exact interactive phrase `RUN M3A UCI412 LOCALLY`, then runs preflight, parses the authorized workbook, fits the registered procedure, and writes the protected report |

Fail-closed rules: non-Windows, CI/hosted notebook, remote/UNC drive, non-TTY stdin, dirty worktree, tracked `data/` file, missing/symlinked manifest, hash mismatch, future-dated or pre-merge signature, non-ancestor governance commit, or a leaked-label alarm all stop the run **before** rows are parsed or results are written, with exit code `2` and a safe message.

### 8.1 CI coverage (maintainer-applied patch)

This PR **does not** modify `.github/workflows/experiment-runner-ci.yml`; the automation
identity used to push the branch has no `workflows` permission, so that file is left byte-identical.

Instead, the exact, already-reviewed change ships as a plain diff:
`research/uci412/ci/experiment-runner-ci.uci412.patch`. It adds the audit and UCI-412
requirement installs, `pytest tests/uci412 -q -W error`, `python -m research.uci412 describe`,
the synthetic-only `dry-run`, and widens the forbidden-artifact `find` scan to
`research/{experiments,audit,uci412}`, `tests/{experiments,audit,uci412}`, `*.xlsx` and `*.xls`.

A maintainer with `workflows` permission applies it before or after merge:

```bash
git apply research/uci412/ci/experiment-runner-ci.uci412.patch
```

Both the current and the patched workflow parse as YAML, and the patch applies cleanly with
`git apply --check` against this branch's tree (**VERIFIED**, 2026-10-24). Until it is applied,
`tests/uci412` runs locally but not in GitHub Actions.

---

## 9. Tests (synthetic evidence only)

`tests/uci412/` exercises the pass and fail-closed path of every safety-relevant rule: source schema, exact column set, prohibited/leakage columns, target labels, unknown categories, whitespace/malformed tokens, missing values, type/unit guards, row and class-count drift, duplicate headers, multi-sheet workbooks, header reordering, hash/size/source-change detection, safe error messages, sealed arrays, preprocessing learned on training folds only, unseen-category and all-missing-column failure, structural pipeline contract, bounded grids, inner-fold-only selection, deterministic repeats, read-only predictions, calibration/uncertainty status, negative-control determinism and alarm thresholds, leakage preconditions, report privacy guards, protected output directory creation, Git-ignore enforcement, non-authorizing template rejection, runtime guards before any parse, and Cleveland (D-047) regression compatibility — the frozen Cleveland panel, seeds, plan, and preprocessing contract are re-asserted unchanged, and constructing UCI-412 objects is proven not to perturb the global NumPy RNG.

**These tests are software evidence, not CAD performance evidence.** No test result here says anything about how well any model predicts CAD.

---

## 10. Sample-size planning arithmetic (not an adequacy verdict)

Using the audited class counts only (`n = 303`, events `= 216`, prevalence `0.7129`):

- Riley outcome-proportion criterion at half-width `0.05`: **required n = 315** → at `n = 303` the criterion is **NOT MET** (`NOT_MET_AT_STATED_HALF_WIDTH`).
- Shrinkage, optimism and minimum-MAPE criteria: **NOT ASSESSED** — they require a human-reviewed *anticipated* Cox–Snell R², which cannot be back-derived from observed performance.
- Events per parameter (16 parameters) ≈ **13.5**, reported as a descriptive count only; it is not a sample-size justification.

Consequence: this benchmark can be executed as an internal feasibility/replication exercise, but the protocol may not be described as adequately powered for a clinical prediction claim.

---

## 11. UCI-412 versus Cleveland (comparison, never a cross-dataset performance claim)

| Dimension | D-047 Cleveland (frozen) | M3a UCI-412 (this proposal) |
|---|---|---|
| Dataset ID / source | `DA-A2` / UCI-45 | `DA-A1` / UCI-412 |
| Records / predictors | 303 / 13 (+ target) | 303 / 55 (+ target) |
| Target | `num > 0` (any vessel > 50 %) | `Cath = Cad` (≥ 50 % narrowing) |
| Threshold rule | **> 50 %** | **≥ 50 %**, deliberately unresolved vs UCI-45 |
| Feature panel | 5 ordered predictors | 16 ordered predictors |
| Outcome meaning | angiography-referenced presence | angiography-referenced presence |
| Cohort identity | Cleveland patients | Z-Alizadeh Sani patients — **different people**; UCI-411 is the same 303 |
| Cross-dataset comparison | prohibited | prohibited |
| Authorization | D-047 (executed) | **this proposal (unsigned, not effective)** |

The two experiments differ in population, era, referral pathway, panel, and threshold semantics. **No AUROC, calibration, or error metric may be compared across them**, and neither may be called external validation of the other.

For orientation only, the executed Cleveland run reported inner-selected AUROC `0.8271 ± 0.0097` (logistic `0.8292 ± 0.0062`, forest `0.8211 ± 0.0085`, prevalence `0.4947`) at merge `146122b`; **these numbers must never be used as a target, baseline, or expectation for UCI-412**.

---

## 12. Exact blockers before the first real experiment

1. **Human ratification.** A named maintainer must approve this proposal in a merged governance PR using the exact comment `AUTHORIZE-M3A-UCI412-INTERNAL-RESEARCH`. Gate PT P-3 stays CLOSED; no supervisor sign-off may be claimed.
2. **Locally signed, hash-bound authorization.** `data/manifests/uci412_internal_research_authorization.local.json` must exist, name the merged governance commit and PR, bind the SHA-256 of this document, the feature dictionary, the research plan, and the source bytes, carry the exact signer/attestation fields, and post-date the merge. The checked-in JSON template authorizes nothing and is rejected.
3. **D-046 provenance chain.** `data/manifests/gate_da_authorization.local.json` must show `DA-A1` authorized for **read-only audit**, `workflow_status = AUTHORIZED_FOR_LOCAL_READ_ONLY_AUDIT`, Gate PT closed, `supervisor_approval_claimed = false`, and no training authority. The checked-in `research/audit/gate_da_authorization.json` still records `PENDING_HUMAN_ACCEPTANCE` with null sign-off fields, so this gate is **not yet satisfied even locally**; the read-only audit evidence in Gate DA is not a substitute for the populated local authorization.
4. **Local provenance + licence snapshot.** `data/manifests/provenance_manifest.json` must contain the `DA-A1` entry with UCI id 412, DOI `10.24432/C5Q31T`, canonical URL, CC BY 4.0, exact relative path, verified SHA-256 and byte size, and a licence snapshot containing "CC BY 4.0". The source bytes must match `90fefd4e…bad163`.
5. **Human review of source spellings and vocabularies.** The exact header spellings and category tokens (`Y`/`N` vs `Yes`/`No`, `Fmale`, `VHD` levels) must be confirmed against the local workbook; any mismatch stops the run and requires a schema-version change, not a silent alias.
6. **Human acceptance of the statistics.** The 16-parameter panel, the fixed 0.5 threshold, the 0.01 selection tolerance, the bootstrap interpretation, and the **NOT ASSESSED** R²-dependent criteria must be accepted in writing.
7. **Human acceptance of the sample-size finding.** The outcome-proportion criterion is **not met** at 303; the benchmark must be accepted as internal exploratory work.
8. **Windows-local environment.** Clean checkout, fixed local drive, `data/` ignored, Python 3.11/3.12 with pinned packages, interactive console.

Until 1–8 hold, `preflight` and `run` fail closed and only `describe`/`dry-run` are usable.

---

## 13. Internal-research authorization proposal (M3a) — to be signed by a human

**Proposal ID:** `M3A-UCI412-INTERNAL-RESEARCH-PROPOSAL` · **Experiment type:** `INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED`

**Requested, if and only if this proposal is ratified:**

| Item | Requested scope |
|---|---|
| Dataset | `DA-A1` only, exact file `data/raw/uci-412/Z-Alizadeh sani dataset.xlsx`, 303 rows |
| Panel | `uci412_basic_clinical_v1` v1.0.0 (16 ordered columns) |
| Operations | read-only loading, internal fitting, internal nested CV, internal family comparison, internal negative control, internal aggregate report |
| Families | prevalence baseline, L2 logistic regression, constrained random forest |
| Runtime | local Windows, CPU only, `$0`, no cloud/CI/remote upload |
| Outputs | `data/uci412-experiments/<run-id>/report.json` + protected `predictions.csv` |
| Duration | one local session per run, revocable by the signer |

**Explicitly excluded by the same approval:** model serving, clinical decision support, external validation claims, multi-cohort pooling, UCI-411 row reuse, patient-level SHAP/LIME, patient-level Git commits or uploads, artifact packaging, and any change to Gate PT status.

**Stops:** any hash mismatch, any new/malformed/prohibited column, any unregistered vocabulary token, any all-missing column, any leakage alarm, or any request to add data or operations voids the authorization.

**Signature block (human-only; the agent must not fill this in):**

- Maintainer name: `[BLANK]`
- Governance PR and merge commit: `[BLANK]`
- Signature timestamp (timezone-aware): `[BLANK]`
- Attestation: “I have reviewed and authorize this exact hash-bound local UCI-412 internal research benchmark. I understand Gate PT P-3 remains CLOSED, that no supervisor approval is claimed, and that no clinical use, external validation, or publication claim is made.”
- Status: `PROPOSED — NOT SIGNED — NOT EFFECTIVE`

The machine-readable template is `research/uci412/internal_research_authorization.template.json`; the real manifest is created only by the human, locally, under `data/manifests/`, and never committed.

---

## 14. Windows-local execution handoff

```powershell
# 1) Clean checkout of the PR merge candidate
git clone <repo> CardioAssist-AI
cd CardioAssist-AI

# 2) Isolated CPU-only environment
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r research/uci412/requirements.txt
python -m pip check

# 3) Offline sanity checks (no data, no fitting)
python -m pytest tests/uci412 -q
python -m research.uci412 describe
python -m research.uci412 dry-run

# 4) Place the human-authorized files (never committed)
#    data/raw/uci-412/Z-Alizadeh sani dataset.xlsx
#    data/manifests/provenance_manifest.json
#    data/manifests/gate_da_authorization.local.json
#    data/manifests/uci412_internal_research_authorization.local.json
#    data/manifests/licenses/uci-412-license-snapshot.txt

# 5) Read-only gate check (opens no rows)
python -m research.uci412 preflight

# 6) Only after every blocker in §12 is satisfied
python -m research.uci412 run      # type: RUN M3A UCI412 LOCALLY
```

Expected outcomes: `preflight` prints `PREFLIGHT_PASS` with the code commit and source hash binding; `run` prints the banner, run ID, and report hash, and writes only under `data/uci412-experiments/`. `data/` is Git-ignored; do not commit, upload, or paste the report's `predictions.csv`.

---

## 15. Claims

**Claimed:** a strict, tested, source-specific research harness and a reviewable authorization proposal exist; every gate fails closed; no real UCI-412 row was read, written, fitted, or uploaded during this milestone.

**Not claimed:** supervisor approval, Gate PT status change, external validation, clinical utility, calibration for future patients, transportability, participant independence, independence from UCI-411, adequacy of sample size, or *any* UCI-412 model performance number.

---

## 16. Open questions for human review

1. Exact source spellings and category tokens in the local workbook (headers, `Y`/`N` vs `Yes`/`No`, `Fmale`, `VHD`).
2. Whether `BP` is systolic-only and what `PR`'s source unit notation ("ppm") means in practice.
3. Whether resting-ECG findings can be shown to precede angiography; if so, the panel amendment is a separate protocol version.
4. Whether the expanded history/examination features have defensible definitions and coding.
5. Whether `Typical Chest Pain`, `Atypical`, and `Nonanginal` are mutually exclusive (their joint distribution is unknown here).
6. Whether the 16-parameter panel, or a smaller prespecified panel, is the panel the human wants frozen.
7. Whether an anticipated Cox–Snell R² can be defended for the sample-size criteria that remain **NOT ASSESSED**.
8. Whether any publication or supervisory claim is intended at all — none is made by this document.
