# M3a — Amendment A-1 — UCI-412 Source-Encoding Correction (`M3A-AMENDMENT-A1`)

> ## `PROPOSED — NOT SIGNED — NOT AUTHORIZED — NOT EFFECTIVE`
>
> - **Status:** a versioned, reviewable **schema/protocol amendment** prepared for one explicit human
>   maintainer decision. It ratifies nothing, activates nothing, and authorizes nothing by itself.
> - **Amends (does not erase):** [doc 08](08_m3a_uci412_source_specific_benchmark_SPECIFICATION.md) and the
>   registered plan `research/uci412/uci412_cad_research_plan.v0.1.json`; the hash-bound activation
>   sequence in [doc 09](09_m3a_uci412_internal_research_RATIFICATION_PACKET.md) remains the same *procedure*
>   but every hash in it is superseded.
> - **Version identifiers:** feature dictionary `uci412_research_feature_dictionary` **1.1.0**
>   (was 1.0.0) · panel `uci412_basic_clinical_v1` **1.1.0** (was 1.0.0) · protocol revision
>   `M3A-AMENDMENT-A1` (plan file name and protocol id unchanged) · M3a local authorization manifest
>   **schema `0.1.0`** with two new required bindings.
> - **Gate PT P-3:** **CLOSED** · **P-1:** PENDING · **P-5:** prohibited · **D-046:** read-only audit only ·
>   **D-047 (Cleveland):** unchanged · **D-048:** unchanged (**not** edited; its own closing clause requires
>   a named human decision).
> - **Evidence addendum E-1 (2026-10-24, `M3A-AMENDMENT-A1-E1`):** adds one peer-reviewed secondary
>   source — Tao H. *et al.*, *Reviews in Cardiovascular Medicine* 2025;26(3):26204,
>   <https://doi.org/10.31083/RCM26204>, Table 1 — which states `True = 1; false = 0` for all six affected
>   attributes. It is **evidence documentation only**: the six-column mapping, model codes, panel,
>   parameters, CV scheme, threshold, dataset and every guard are unchanged, and the schema/panel versions
>   stay 1.1.0. S-9 stays **provisional** (no official dataset-owner codebook) and still requires explicit
>   human acceptance.
> - **No real data:** no workbook was downloaded, opened, modified, or uploaded by this amendment; no model
>   was fitted; no patient-level value, row, fingerprint, prediction file, or performance number exists in
>   this document.
> - **No clinical claim:** no supervisor, ethics, institutional, deployment, publication, novelty, or
>   clinical-readiness claim is made or implied.

---

## 1. Root cause — what actually failed, and why it was correct to fail

The first authorized real-data execution stopped **before model fitting** with:

```
FAIL CLOSED: Column 'DM' contains a category outside the registered vocabulary.
```

**Root cause (confirmed in code):** the registered feature dictionary declared twelve binary predictors
with the *assumed* text vocabularies `Y`/`N`/`Yes`/`No`, marked
`vocabulary_evidence_status: SECONDARY_RANGES_DESCRIBED_AS_YES_NO_EXACT_WORKBOOK_TOKENS_UNVERIFIED`. That
assumption was never verified against the delivered workbook.

The delivered UCI-412 workbook (*Z-Alizadeh Sani*, DA-A1) encodes **six** of those twelve admitted
predictors **numerically** (`0`/`1`). The adapter's categorical path converts a numeric cell to its text
form and looks it up in the registered vocabulary; `1` became the token `"1"`, which is not in
`{"Y","N","Yes","No"}`, so the adapter refused the column. The refusal was the *designed* behaviour: a
fail-closed guard catching an unverified vocabulary assumption. It was a **source-encoding defect in the
protocol record**, not a defect in the guard, and not a reason to relax the guard.

**Corrected source encoding:** exactly six admitted columns carry an explicit, registered numeric-binary
source encoding in which the numeric cell `0` maps to model code `0` (**absent / false**) and the numeric
cell `1` maps to model code `1` (**present / true**). The other six admitted categorical predictors keep
their registered text vocabularies unchanged.

| # | Admitted column | Pre-amendment registration (wrong for the delivered file) | Registered v1.1.0 source encoding | Audit counts `0` / `1` (303 records) |
|---|---|---|---|---|
| 1 | `DM` | `Y`→1, `N`→0, `Yes`→1, `No`→0 | numeric `0`→0, `1`→1 | 213 / 90 |
| 2 | `HTN` | `Y`→1, `N`→0, `Yes`→1, `No`→0 | numeric `0`→0, `1`→1 | 124 / 179 |
| 3 | `Current Smoker` | `Y`→1, `N`→0, `Yes`→1, `No`→0 | numeric `0`→0, `1`→1 | 240 / 63 |
| 4 | `EX-Smoker` | `Y`→1, `N`→0, `Yes`→1, `No`→0 | numeric `0`→0, `1`→1 | 293 / 10 |
| 5 | `FH` | `Y`→1, `N`→0, `Yes`→1, `No`→0 | numeric `0`→0, `1`→1 | 255 / 48 |
| 6 | `Typical Chest Pain` | `Y`→1, `N`→0, `Yes`→1, `No`→0 | numeric `0`→0, `1`→1 | 139 / 164 |

Unchanged text vocabularies (303/303 registered values per the same audit):

| Column | Registered vocabulary (unchanged) |
|---|---|
| `Sex` | `Male`→1, `Fmale`→0, `Female`→0 |
| `DLP` | `Y`/`Yes`→1, `N`/`No`→0 |
| `Atypical` | `Y`/`Yes`→1, `N`/`No`→0 |
| `Nonanginal` | `Y`/`Yes`→1, `N`/`No`→0 |
| `Exertional CP` | `Y`/`Yes`→1, `N`/`No`→0 |
| `Dyspnea` | `Y`/`Yes`→1, `N`/`No`→0 |

The asymmetry is real and is preserved deliberately: `Typical Chest Pain` is numeric in the delivered file
while `Atypical`, `Nonanginal`, and `Exertional CP` are textual. No column was harmonised, renamed,
re-typed in the model matrix, or "made consistent".

---

## 2. What changed in the protocol record

| Artifact | Identifier | Change |
|---|---|---|
| Feature dictionary `research/uci412/schemas/uci412_feature_dictionary.v1.json` | schema `uci412_research_feature_dictionary` **1.1.0** | six features: `vocabulary` → `null`, new `source_value_encoding` block (encoding id, values, model codes, verification status, evidence, uncertainty, rejected legacy tokens, aggregate audit counts); `revision_history` records 1.0.0 → 1.1.0; two new citations (secondary numeric-binary literature; the human audit record) |
| Panel `uci412_basic_clinical_v1` | **1.1.0** | version bump only for the source-encoding contract of six members; the same 16 columns in the same order; all four registered panels moved to 1.1.0 |
| Research plan `research/uci412/uci412_cad_research_plan.v0.1.json` | protocol revision `M3A-AMENDMENT-A1` | new `protocol_revision` block and `source_encoding` block (register id, six columns, accepted values `[0, 1]`, rejected value classes, `global_automatic_coercion: FORBIDDEN`, `encoded_parameter_count_unchanged: true`); dictionary/panel version bindings → 1.1.0 |
| `research/uci412/source_spec.py` | — | `NUMERIC_BINARY_SOURCE_COLUMNS` (the audited six, in source order), encoding id/kind/semantics constants, `TEXT_CATEGORICAL_SOURCE_COLUMNS`, the audit evidence for both, and the E-1 semantics-evidence status + citation ids |
| `research/uci412/feature_schema.py` | — | `SourceValueEncoding` type; strict validation (single id, `0→0`/`1→1` only, human-audit verification status mandatory, non-empty evidence/uncertainty, aggregate counts consistent); mutual exclusion with a text vocabulary; code-level allowlist that must equal the six columns; `codes` still returns `(0, 1)` |
| `research/uci412/adapter.py` | — | one new strict reader `_numeric_binary_code`; the per-cell dispatch accepts integers `0`/`1` (and exactly equal floats) **only** for those six columns; aggregate `numeric_binary_source_value_counts` added to the audit object |
| `research/uci412/config.py` | — | `M3A_PROTOCOL_AMENDMENT_ID`, `SOURCE_ENCODING_REGISTER_ID`; plan validation of the new blocks; `source_value_encoding` section in the report payload |
| `research/uci412/safety.py` | — | the local manifest must now also bind `dictionary_schema_version` and `protocol_amendment_id`; both are validated before any workbook byte is read |
| `research/uci412/internal_research_authorization.template.json` | manifest schema `0.1.0` | template records panel `1.1.0`, dictionary `1.1.0`, `protocol_amendment_id: M3A-AMENDMENT-A1`; still non-authorizing (`REPLACE_WITH_*`, status `PROPOSED_NOT_AUTHORIZING`) |
| `research/uci412/synthetic.py` | — | the six columns are generated as numeric `0`/`1`; the other text columns keep `Y`/`N`; a fixture that still emitted `Y`/`N` there would now (correctly) be refused |
| `research/uci412/cli.py` | — | `describe` reports the amendment and the revised blocker list |
| `tests/uci412/test_source_encoding_amendment.py` | **new** | 175 synthetic assertions for this amendment |
| `docs/research/gate-pt/08…`, `09…`, `README.md`, `AGENTS.md` | — | dated amendment notices; the historical text is retained, not rewritten |

### 2.1 Strictness preserved (requirement 3)

For the six numeric columns the adapter now accepts **only**:

- an actual integer `0` or `1`; or
- a float that is exactly `0.0` or `1.0`.

Everything else **fails closed** with a patient-safe message that never echoes the cell value:

| Rejected | Reason recorded |
|---|---|
| `"Y"`, `"N"`, `"Yes"`, `"No"`, `"0"`, `"1"`, `"TRUE"`, any other text | no text coercion; the retired Y/N assumption is refused, not aliased |
| `True` / `False` | booleans are not the registered encoding (`True == 1` must never smuggle a code) |
| `2`, `-1`, `10`, `0.5`, `1.5`, `1.0000001`, `100.0` | not one of the registered binary source values |
| `NaN`, `+inf`, `-inf` | non-finite cell |
| a mixed column (`1` in one row, `"Y"` in another) | the first non-conforming cell aborts the run |
| `1` in `DLP`, `Sex`, or any other text-categorical column | that column has no numeric conversion registered; the existing "outside the registered vocabulary" failure is unchanged |
| `"58"` in `Age`, `"120"` in `BP` | numeric columns still never coerce text |

There is **no global automatic conversion**: the conversion is reachable only through a feature spec that
carries the registered encoding, and a code-level allowlist forces that set to be exactly the six audited
columns. A JSON-only edit cannot widen it (adding the block to `DLP` fails), invert it
(`absent_model_code: 1` fails), weaken it (`verification_status: SECONDARY_LITERATURE_ONLY` fails), drop it
(the allowlist check fails), or add a second coding (vocabulary + encoding fails).

Blank cells in these six columns keep the **pre-existing registered missing semantics**: an undocumented
gap becomes `NaN`, is counted per column, and is imputed inside training folds only. The audit observed no
blanks; the behaviour was not changed by this amendment.

---

## 3. Source evidence and unresolved assumptions

### 3.1 Evidence actually used

| Evidence | Status | What it supports |
|---|---|---|
| Human-executed, read-only, **SHA-256-verified local audit** of all 303 records and all 12 admitted categorical predictors (2026-10-24); workbook verified byte-identical before and after | **Primary for representation** (aggregate counts only; no row-level value retained anywhere) | These six columns contain exclusively numeric `0`/`1` with no blanks; the other six contain 303/303 registered values |
| <https://doi.org/10.3390/electronics11030315> — Table 1 | Secondary literature (supporting) | The six attributes are binary `0/1` |
| <https://pmc.ncbi.nlm.nih.gov/articles/PMC7037941/> — published feature descriptions | Secondary literature (supporting) | A `0/1` representation is described in the literature |
| **Tao H., Wang C., Qi H., Li H., Li Y., Xie R., *et al.* (2025)** — *A Real-Time Computer-Aided Diagnosis System for Coronary Heart Disease Prediction Using Clinical Information*, **Reviews in Cardiovascular Medicine 26(3):26204**, <https://doi.org/10.31083/RCM26204> (open access, CC BY 4.0; published 2025-03-17). Table 1 “Features of Z-Alizadeh Sani dataset” types these attributes as `Integer` and states **`True = 1; false = 0`** for `DM`, `HTN`, `Current Smoker`, `EX-Smoker`, `FH` and `Typical Chest Pain` | **Peer-reviewed secondary source, table read in full** (evidence addendum E-1) | The **direction** of the six codes (1 = present, 0 = absent), the integer representation, and — consistently — `Male = 1; female = 0` for `Sex` and `Yes = 1; no = 0` for `DLP`, `Atypical`, `Nonanginal`, `Exertional CP`, `Dyspnea` |
| <https://doi.org/10.24432/C5Q31T> — official UCI-412 dataset identity | Official dataset identity | Which file/records this is about (not per-column coding) |

**Not used, and explicitly absent:** an official per-column codebook. The UCI landing page publishes group
membership, record count, the ≥50 % target rule, "no missing values", and the licence — **not** per-field
coding. Secondary literature is supporting evidence, not an independently verified official codebook.

**Direction evidence (addendum E-1).** Tao *et al.* 2025 Table 1 is not an inference from attribute naming:
it states the coding explicitly and in the same direction the dictionary registers (`True = 1; false = 0`,
i.e. `1` = present/true). That raises the *direction* claim from "inferred" to **"directly stated by
peer-reviewed secondary literature"**. It does **not** make the claim official: the source is a third-party
publication, it says nothing about the delivered workbook's exact cell types or spellings, and no
dataset-owner codebook has been issued or independently checked. The six codes therefore stay
`PROVISIONAL_DIRECTION_STATED_BY_PEER_REVIEWED_SECONDARY_LITERATURE_NOT_OFFICIAL_CODEBOOK`, and explicit
human acceptance of **S-9** is still required before any real-data run.

### 3.2 Residual uncertainty (S-9 — requires explicit human acceptance)

| # | Unresolved item | Current behaviour | If it cannot be accepted |
|---|---|---|---|
| **S-9** (evidence addendum E-1) | The human audit establishes the **representation** (numeric `0`/`1`). The **direction** (`1` = present) is now **directly stated by peer-reviewed secondary literature** — Tao *et al.* 2025, Table 1: `True = 1; false = 0` — but it is still **not independently verified against an official dataset-owner codebook**, because none is published. Secondary evidence reduces, but does not remove, the residual risk. | `0` → absent/false, `1` → present/true, recorded as `PROVISIONAL_DIRECTION_STATED_BY_PEER_REVIEWED_SECONDARY_LITERATURE_NOT_OFFICIAL_CODEBOOK`; `semantic_uncertainty` and the citation ids are mandatory fields of each of the six encodings; explicit human acceptance stays required | Do not sign. A direction change is a new dictionary schema version and a new review; it is never a local edit |
| S-1 (partially resolved) | Exact header spellings and category tokens for the **43 non-admitted** columns (e.g. `Fmale`, VHD levels in blocked panels) remain unverified | Unchanged: only the registered 56-header set is accepted; blocked panels stay blocked | Do not sign; a vocabulary change is a new dictionary version |
| S-2 … S-8 | Unchanged residual items from doc 09 §4 (`BP` single-value, `PR` unit, chest-pain exclusivity, ECG/echo timing, target threshold ≥50 % vs >50 %, 54 vs 55 features) | Unchanged, byte-for-byte | Carried forward unchanged |

Nothing outside these six columns became newly admitted, newly executable, or newly interpretable.

---

## 4. Frozen parameters proven unchanged

| Element | Frozen value | Evidence it is unchanged |
|---|---|---|
| Panel identity and membership | `uci412_basic_clinical_v1`, 16 columns | `PRIMARY_PANEL_COLUMNS` asserted equal in code, in the dictionary, in the plan and in tests |
| Feature order | `Age, Sex, BMI, DM, HTN, Current Smoker, EX-Smoker, FH, DLP, BP, PR, Typical Chest Pain, Atypical, Nonanginal, Exertional CP, Dyspnea` | exact tuple equality asserted; `X.shape == (303, 16)` |
| Encoded parameter count | **16** (4 numeric + 12 reference-coded binary) | `encoded_parameter_count() == 16`; every categorical column still has codes `(0, 1)`; encoder categories still `[0.0, 1.0]` |
| Model-side codes | categorical inputs still `0.0`/`1.0` | only the *source representation* changed; the model matrix values are identical in type and coding |
| Target mapping | `Cath`: `Cad`→1, `Normal`→0, case-sensitive, no coercion | unchanged code and tests; class counts still 216/87 |
| Model families | `prevalence_dummy`, `l2_logistic_regression`, `constrained_random_forest` | plan validation unchanged (`RESERVED_EXTENSION_POINT_NOT_IMPLEMENTED` untouched) |
| Parameter grids | logistic `C ∈ {0.1, 1, 10}`, `max_iter 2000`, liblinear, L2, no class weight; forest 200 trees, depth `{3, 5}`, leaf `{5, 10}`, `sqrt` | `test_registered_plan_matches_the_frozen_config` |
| Nested CV | outer 5 × 4 seeds `20261024–20261027`, inner 5, stratified, seed derivations `+211+1013k`, `+200003+131k+offset`, `+500009` | unchanged plan + config validation |
| Selection rule | inner ROC-AUC, 0.01 equivalence tolerance, logistic simplicity preference | unchanged |
| Threshold | fixed exploratory `0.5`; threshold tuning forbidden | unchanged |
| Preprocessing | training-fold median / most-frequent imputation, fixed-vocabulary reference one-hot, no global transform, unseen category = error | unchanged; only the *source* value domain of six columns changed |
| Negative control | 3 shuffle seeds `20262004–20262006`, 1 outer repeat, alarm ≥ 0.90, warn ≥ 0.70 | unchanged |
| Leakage checks | `assert_no_target_leakage` unchanged; target/prohibited/pooling rules unchanged | unchanged code; asserted in the new tests |
| Privacy controls | aggregate-only report, `data/` Git-ignored, no patient-level commit/upload, `predictions.csv` protected-local only | unchanged |
| Execution gate | Windows-local, CPU-only, clean worktree, `$0`, interactive confirmation | unchanged |

---

## 5. Why PR #45's signed manifest cannot simply be reused

PR #45 (merged as doc 09's packet) froze specific bytes. Three of them changed, so a manifest signed
against them is not a valid authorization for these bytes — it is a signature on a *different protocol*.

1. **The byte bindings no longer match.** The manifest binds `frozen_research_plan_sha256`,
   `frozen_feature_dictionary_sha256` and `frozen_authorization_proposal_sha256`. The plan, the dictionary,
   and doc 08 all changed in this amendment, so those three hashes changed. `safety.validate_m3a_authorization`
   recomputes them from disk and raises `FAIL CLOSED: The registered research plan differs from the
   human-frozen hash.` (or the dictionary/proposal equivalent). The values in doc 09 §2 are **obsolete**.
2. **The version bindings no longer match.** The manifest records `panel_schema_version`. The executable
   panel moved to `1.1.0` because the source-encoding contract of six of its members changed. An old
   manifest fails with `FAIL CLOSED: The M3a authorization binds a different panel version.`
3. **The amendment is now an explicit binding.** The manifest must now also name `dictionary_schema_version`
   (`1.1.0`) and `protocol_amendment_id` (`M3A-AMENDMENT-A1`). A manifest written before the amendment
   lacks both fields and fails closed with
   `FAIL CLOSED: The M3a authorization does not bind the amended feature-dictionary schema version.`
   (then `…does not bind the reviewed protocol amendment.`).

Three independent guards fail closed, and all three are covered by synthetic tests
(`tests/uci412/test_source_encoding_amendment.py`, §7). In addition, doc 09 §8 already declares that *any*
change to the plan, dictionary, adapter or panel versions voids an activation — this amendment is exactly
such a change, so reusing the old signature would contradict the protocol the human signed.

**What did *not* change and therefore needs no new evidence:** the source workbook bytes
(`90fefd4ecdb6263b3f2a260bb2b5d3b9fa92ba35d626dd56ad8c6db5fbbad163`, unchanged by the audit and by this
amendment), the D-046 read-only chain, the protected provenance/licence requirement, the target, the
panel membership/order, the models, the CV scheme, the seeds, the metric set, the threshold, and every
privacy rule.

---

## 6. Exact maintainer actions required (human only, in order)

**Nothing below may be executed by an agent, a bot, or CI.** Steps 1–2 are the governance act; steps 3–7
are local to the maintainer's Windows machine and are the only way a single real row is ever opened.

1. **Review this PR** (documentation + `research/uci412/**` + `tests/uci412/**` only; no workflow file, no
   data file, no backend/contract change). Accept or reject:
   - the corrected encoding table in §1;
   - residual item **S-9** (the `0` = absent/false, `1` = present/true direction — now directly stated by
     Tao *et al.* 2025 Table 1, but still not confirmed by an official dataset-owner codebook);
   - the version bumps (`dictionary 1.1.0`, `panel 1.1.0`) and the fact that all earlier hashes are void.

2. **Record the decision explicitly** on the amendment PR: the verbatim review comment

   ```
   AUTHORIZE-M3A-UCI412-INTERNAL-RESEARCH
   ```

   as its own line, then **merge the PR yourself** through the GitHub UI (no automation identity), and
   keep the merge commit reachable locally (`git fetch origin`). Do not post the comment if you intend to
   reject S-9.

3. **Confirm the D-046 read-only chain** for `DA-A1` locally:
   `data/manifests/gate_da_authorization.local.json` with
   `workflow_status = AUTHORIZED_FOR_LOCAL_READ_ONLY_AUDIT`,
   `datasets.DA-A1.authorization_status = AUTHORIZED_FOR_READ_ONLY_AUDIT`, populated human sign-off fields,
   `training_authorized = false`, `supervisor_approval_claimed = false`,
   `gate_pt_status = CLOSED_REQUIRES_SUPERVISOR_SIGNOFF_P3`. Read-only audit provenance; it authorizes no
   fitting and grants nothing new.

4. **Confirm protected provenance and licence** for the unchanged bytes:
   `data/manifests/provenance_manifest.json` + `data/manifests/licenses/uci-412-license-snapshot.txt`, with
   `uci_id = 412`, `doi = 10.24432/C5Q31T`, the canonical UCI URL, `license_spdx = CC-BY-4.0`, the exact
   relative path, and a local `sha256` equal to
   `90fefd4ecdb6263b3f2a260bb2b5d3b9fa92ba35d626dd56ad8c6db5fbbad163`.

5. **Compute the new hashes at the merge commit** (§7 step 3) and **create a NEW** Git-ignored
   `data/manifests/uci412_internal_research_authorization.local.json` from
   `research/uci412/internal_research_authorization.template.json`, changing at minimum:

   | Field | Required value |
   |---|---|
   | `authorization_status` | `AUTHORIZED_FOR_LOCAL_INTERNAL_RESEARCH` |
   | `maintainer_approval_comment_exact` | `AUTHORIZE-M3A-UCI412-INTERNAL-RESEARCH` (remove the `REPLACE_WITH_` prefix) |
   | `governance_pr_number` | this amendment PR's number |
   | `governance_merge_commit_sha`, `pinned_protocol_commit_sha` | identical, the amendment merge commit |
   | `panel_schema_version` | `1.1.0` |
   | `dictionary_schema_version` | `1.1.0` |
   | `protocol_amendment_id` | `M3A-AMENDMENT-A1` |
   | `frozen_research_plan_sha256` | the plan hash **at the merge commit** |
   | `frozen_feature_dictionary_sha256` | the dictionary hash **at the merge commit** |
   | `frozen_authorization_proposal_sha256` | the doc-08 hash **at the merge commit** |
   | `expected_sha256_from_protected_provenance_manifest` | the unchanged workbook hash above |
   | `local_signer` | `Muhammed Fathi` |
   | `local_signed_at_iso8601` | timezone-aware timestamp ≥ the merge committer time and not in the future |
   | `local_signature_attestation` | the verbatim code constant `M3A_LOCAL_SIGNATURE_ATTESTATION` |
   | every other field | unchanged from the template |

   Never commit, paste, or upload this file or `predictions.csv`.

6. **Run `preflight`** (opens no rows, fits nothing) and only then **`run`** (interactive; type the exact
   confirmation phrase). Any `FAIL CLOSED:` message is a completed, correct refusal: record it verbatim in
   `data/manifests/uci412_failed_runs.local.json` and do not work around it.

7. **Report** the run banner (`INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED`), the run id, the report hash,
   and — separately — the aggregate counts the report now records under
   `cohort.aggregate_source_audit.numeric_binary_source_value_counts`, which is the direct evidence that
   the six columns were read through the amended encoding. If those counts do not reconcile to 303 records
   per column, stop: do not interpret any metric.

**Blank human decision fields (this document records no signature):**

| Decision | Field |
|---|---|
| Accept §1 encoding and §2–§4 unchanged freeze | `[BLANK — HUMAN ONLY]` |
| Accept S-9 direction (peer-reviewed secondary evidence, no official codebook) as provisional | `[BLANK — HUMAN ONLY]` |
| Name / date | `[BLANK]` / `[BLANK]` |

---

## 7. Minimal Windows-local verification (after human approval)

Environment: Windows 10/11, PowerShell, fixed local drive (no UNC/network path, no symlink/junction in the
repo path), interactive console, `$0`.

```powershell
# 0) Clean checkout at the amendment merge commit
git switch main
git pull --ff-only origin main
$MERGE = "REPLACE_WITH_THE_AMENDMENT_MERGE_COMMIT_SHA"
git merge-base --is-ancestor $MERGE HEAD; if ($LASTEXITCODE -ne 0) { Write-Error "STOP" }
git status --porcelain --untracked-files=all      # must be empty

# 1) Isolated CPU-only environment (Git-ignored, keeps the worktree clean)
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r research/uci412/requirements.txt
python -m pip check

# 2) Synthetic-only evidence, no data, no fitting
python -m pytest tests/uci412 -q -W error
python -m research.uci412 describe          # expect dictionary 1.1.0 / panel 1.1.0 and the amendment
python -m research.uci412 dry-run           # synchronous in-memory synthetic rows only

# 3) Hash binding at the merge commit — copy these into the local manifest (never from a document)
foreach ($p in @(
  "docs\research\gate-pt\08_m3a_uci412_source_specific_benchmark_SPECIFICATION.md",
  "research\uci412\uci412_cad_research_plan.v0.1.json",
  "research\uci412\schemas\uci412_feature_dictionary.v1.json",
  "data\raw\uci-412\Z-Alizadeh sani dataset.xlsx"
)) { "{0}  {1}" -f (Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash.ToLower(), $p }

# 4) Storage protection + authorization gates (no rows parsed)
python -m research.audit verify-ignore
python -m research.uci412 preflight         # expect PREFLIGHT_PASS, source_rows_parsed=false

# 5) Only after step 4 passes
python -m research.uci412 run               # type exactly:  RUN M3A UCI412 LOCALLY

# 6) Confirm the workbook bytes were not modified and nothing entered Git
foreach ($p in @("data\raw\uci-412\Z-Alizadeh sani dataset.xlsx")) {
  "{0}  {1}" -f (Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash.ToLower(), $p
}                                            # must still be 90fefd4e…5fbbad163
git status --porcelain --untracked-files=all  # must be empty
```

Expected if everything is correct: `preflight` passes; `run` prints
`INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED`, a run id `run-YYYYMMDDTHHMMSSZ-xxxxxxxx`, and the report
hash; outputs appear only under `data/uci412-experiments/`. `predictions.csv` is patient-level and must
never be committed, uploaded, or pasted.

A refusal here is a **success of the guard**, not a reason to edit the protocol. The only legitimate
remedies are a new amendment (new schema/panel version) or reverting this PR.

---

## 8. Test evidence and what is *not* claimed

Synthetic evidence added by this amendment (`tests/uci412/test_source_encoding_amendment.py`, 175 cases,
all synthetic in-memory fixtures):

1. the six numeric `0/1` columns are accepted and map `0`→`0`, `1`→`1` (integers and exactly equal floats);
2. the other six categorical columns keep their registered text vocabularies, including `Sex`
   (`Male`/`Fmale`/`Female`) and `Y`/`No` handling;
3. unexpected text, booleans, non-binary/non-integral numbers, non-finite cells, mixed representations,
   numeric cells in text columns, and text in numeric columns all fail closed, with sentinel tests proving
   no cell value is echoed;
4. the exact 16-column order, the 16 encoded parameters, the `(0, 1)` category codes and the encoder
   categories `[0.0, 1.0]` are unchanged — and the dictionary cannot be widened, inverted, weakened or
   de-registered by a JSON-only edit;
5. target separation and the leakage checks pass on the corrected encoding, and no numeric-binary column
   is a copy of the outcome;
6. the full synthetic end-to-end run (`run_synthetic_dry_run`, the same path the CLI dry-run uses)
   completes with `status PASS`, writes no files, and opens no real data;
7. a PR-#45-shaped manifest fails closed on the panel version, on the missing dictionary schema binding,
   and on the missing amendment id, and the checked-in template remains non-authorizing;
8. evidence addendum E-1: each of the six encodings cites `TAO_2025_RCM_TABLE1` with the full DOI and the
   `True = 1; false = 0` statement, the provisional-not-official status string is unchanged in code and in
   the plan, and the dictionary/plan cannot be edited to claim official-codebook confirmation.

**Claimed:** a narrow, documented, versioned source-encoding correction exists; the strict adapter now
handles the audited numeric representation without weakening any guard; every affected gate fails closed;
the previous authorization is demonstrably not reusable.

**Not claimed:** supervisor/ethics/institutional approval; any Gate PT status change (**P-3 stays
CLOSED**); clinical utility, deployment or publication readiness; external validation; sample-size
adequacy; and **any** UCI-412 model performance number. No real workbook was opened and no model was
fitted.
