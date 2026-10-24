# M3a — UCI-412 Internal Exploratory Benchmark — Ratification and Activation Packet

> ## `PROPOSED — NOT SIGNED — NOT AUTHORIZED — NOT EFFECTIVE`
>
> - **Status:** a review packet for a **human maintainer decision**. It ratifies nothing, activates
>   nothing, and authorizes nothing by itself.
> - **Companion (unchanged) proposal:** [doc 08](08_m3a_uci412_source_specific_benchmark_SPECIFICATION.md)
>   (specification + authorization proposal) and **D-048** in [`docs/DECISIONS.md`](../../DECISIONS.md).
>   Both remain `PROPOSED_NOT_AUTHORIZED`; this packet adds no decision id and changes no status field.
> - **Code / protocol:** **byte-identical to `main`**. The registered plan, the feature dictionary and
>   doc 08 are **not modified** by the PR that adds this file (verification in §2).
> - **Gate PT P-3:** **CLOSED** · **P-1:** PENDING · **P-5:** prohibited · **D-047 (Cleveland):**
>   unchanged.
> - **Output banner for any future real run:** `INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED`.
> - **Nothing here is a new feasibility study, dataset audit, or literature review.** It exists only to
>   give the maintainer one place to (a) accept or reject the residual scientific uncertainties and
>   (b) execute the exact, already-specified activation sequence.

---

## 1. Purpose and what this packet deliberately does not do

The M3a UCI-412 pipeline is implemented, merged ([PR #44](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/44),
merge commit `ca96be7ab3d1f34b196d22d8b6f9b87ba8b4763c`), CI-covered by tests, and has passed a
Windows-local **synthetic** dry-run. The remaining gap between "implementation exists" and "one
authorized local experiment may run" is **purely a human governance act**. This packet is the
shortest artifact that carries that act.

**This packet does not:**

- re-audit any dataset, re-derive any source fact, or re-open the Cleveland (D-047) work;
- propose, alter, or re-freeze any part of the experimental protocol;
- change, extend, or weaken any gate, guard, blocker, prohibition, or status;
- contain, request, or imply any patient-level data, model result, performance number, or claim;
- sign, simulate, or pre-fill a human decision (every human field below is `[BLANK]`).

**This packet does:**

- pin the exact bytes the human is being asked to freeze (§2);
- state the frozen experiment scope in one page so it can be accepted or rejected without reading four
  prior documents (§3);
- isolate the **unresolved source-feature semantics** (§4) and the **sample-size limitations** (§5) as
  explicit, individually acceptable/rejectable items;
- give the **exact maintainer-side activation sequence**, including the required verbatim PR comment,
  the human-approved merge, the hash binding, the protected local manifest field-by-field, and the
  Windows-local preflight (§6, §7);
- state exactly what voids or revokes an activation (§8), and why the existing authorization validator
  can validate a future merge of this PR **without any code change** (§9).

---

## 2. The frozen bytes, and proof this packet does not touch them

Base: `main` at `ca96be7ab3d1f34b196d22d8b6f9b87ba8b4763c` (the merge of PR #44).

| Artifact | Path | SHA-256 at `ca96be7` |
|---|---|---|
| Authorization proposal / specification | `docs/research/gate-pt/08_m3a_uci412_source_specific_benchmark_SPECIFICATION.md` | `aeacb56aedc4fe8c79ab8f32ad627e21895e155e1d6035b84e315e8e28a2ea37` |
| Frozen research plan | `research/uci412/uci412_cad_research_plan.v0.1.json` | `92d103b4dfc3bf43635a33999b44fe9722389082c808b5e132fc60f6be6576a9` |
| Frozen feature dictionary | `research/uci412/schemas/uci412_feature_dictionary.v1.json` | `b692a296a7a409ccfadc713f3ab6c8143ca8d91cf0b914462b78a3c32ccb4983` |
| Audited source workbook (never in Git) | `data/raw/uci-412/Z-Alizadeh sani dataset.xlsx` | `90fefd4ecdb6263b3f2a260bb2b5d3b9fa92ba35d626dd56ad8c6db5fbbad163` |

The governance PR carrying this packet changes **documentation only** — this file, one index bullet in
[`README.md`](README.md), and one dated addendum in [`AGENTS.md`](../../../AGENTS.md). It does not edit
doc 08, the plan, the dictionary, `research/uci412/**`, `research/experiments/**`, `backend/**`, `app/**`
or `.github/**`. Therefore the three hashes above are **identical at your governance merge commit**, and
they are the exact values to bind in the local manifest (§6.6).

Verify at your own checkout before signing anything (**all four `diff` commands must print nothing; all
four hashes must match the table**):

```powershell
git switch main
git pull --ff-only origin main
$MERGE = "REPLACE_WITH_THIS_GOVERNANCE_PR_MERGE_SHA"
git merge-base --is-ancestor $MERGE HEAD    # must exit 0
git diff --quiet $MERGE HEAD -- `
  docs/research/gate-pt/08_m3a_uci412_source_specific_benchmark_SPECIFICATION.md `
  research/uci412/uci412_cad_research_plan.v0.1.json `
  research/uci412/schemas/uci412_feature_dictionary.v1.json `
  research/uci412 research/experiments .github/workflows
if ($LASTEXITCODE -ne 0) { Write-Error "STOP: the frozen artifacts moved; do not sign." }

foreach ($p in @(
  "docs\research\gate-pt\08_m3a_uci412_source_specific_benchmark_SPECIFICATION.md",
  "research\uci412\uci412_cad_research_plan.v0.1.json",
  "research\uci412\schemas\uci412_feature_dictionary.v1.json",
  "data\raw\uci-412\Z-Alizadeh sani dataset.xlsx"
)) { "{0}  {1}" -f (Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash.ToLower(), $p }
```

**If any value differs, stop.** A different hash means a different protocol or different source bytes;
it is a new review, not a signature on this one. Binding a wrong hash is not a warning the code issues —
it is a hard `FAIL CLOSED`.

---

## 3. The exact experiment scope proposed for ratification

Everything below is already frozen in code and in the committed plan; the human ratifies **these bytes**,
not a description of them.

| Element | Frozen value |
|---|---|
| Dataset | `DA-A1` only — UCI-412 (*Z-Alizadeh Sani*), exact file `data/raw/uci-412/Z-Alizadeh sani dataset.xlsx`, **303 rows**, `216` `Cad` / `87` `Normal` |
| Target | `Cath`: `Cad` → 1, `Normal` → 0, case-sensitive, no coercion, blank/other token fails closed |
| Meaning of the label | **cross-sectional angiography-referenced CAD presence** at the source's ≥50 % narrowing rule. Never future-event risk, never a risk score, never a horizon |
| Feature panel | `uci412_basic_clinical_v1` v1.0.0 — **16 ordered columns**: `Age`, `Sex`, `BMI`, `DM`, `HTN`, `Current Smoker`, `EX-Smoker`, `FH`, `DLP`, `BP`, `PR`, `Typical Chest Pain`, `Atypical`, `Nonanginal`, `Exertional CP`, `Dyspnea` (4 numeric + 12 binary/categorical → 16 reference-coded parameters) |
| Model families | **exactly three**: `prevalence_dummy` (prior only), `l2_logistic_regression` (`liblinear`, L2, `C ∈ {0.1, 1, 10}`, `max_iter = 2000`, no class weighting), `constrained_random_forest` (200 trees, `max_depth ∈ {3, 5}`, `min_samples_leaf ∈ {5, 10}`, `max_features = sqrt`) |
| Selection | inner 5-fold ROC-AUC, `0.01` equivalence tolerance, simplicity preference = logistic regression |
| Resampling | repeated **stratified nested CV**: outer 5 folds × 4 fixed repeat seeds (`20261024`–`20261027`), inner 5 folds; every transform fitted inside the training folds only; no global preprocessing |
| Metrics | outer ROC-AUC primary; fixed exploratory decision threshold `0.5`, **threshold tuning forbidden**; participant-level percentile bootstrap **within each repeat** (500 resamples), pooled-repeat inference forbidden |
| Negative control | label permutation, 3 fixed seeds (`20262004`–`20262006`), 1 outer repeat each; AUROC ≥ 0.90 alarms, ≥ 0.70 warns; explicitly a **smoke test, not a permutation p-value** |
| Runtime | local Windows, CPU only, `$0`, interactive console, no CI/cloud/notebook/remote |
| Outputs | `data/uci412-experiments/<run-id>/report.json` (aggregate only) + protected `predictions.csv` (patient-level derivative, never committed/uploaded/pasted) |
| Authorization | `PROPOSED_UNAUTHORIZED` until §6 steps 1–7 are completed by a named human |

**Explicitly out of scope, at every stage and for every output:** pooling with Cleveland / Hungary / VA /
Switzerland; external or independent validation; treating UCI-411 as a separate dataset (it is the same
303 participants); patient-level SHAP/LIME; model serving, artifact admission or packaging;
patient-facing risk percentages; alarming or treatment language; any accuracy, novelty, publication,
supervisor, ethics or clinical-readiness claim; any change to Gate PT (`P-3` stays **CLOSED**) or to
D-046 / D-047 status. Angiography-derived fields (`Cath`, `LAD`, `LCX`, `RCA`), identifiers, derived
anthropometrics (`Weight`, `Length`, `Obesity`) and echo fields stay excluded; the resting-ECG, expanded
clinical and laboratory panels stay **registered but blocked**.

> **Human decision 0 — scope:** accept / reject the frozen scope exactly as tabulated above.
> Decision: `[BLANK — HUMAN ONLY]` · Name: `[BLANK]` · Date: `[BLANK]`

---

## 4. Unresolved source-feature semantics that require explicit human acceptance

These are **not** defects introduced by this PR and **not** repaired by it. They are the residual
`[GAP]` items from doc 08 §4/§5.5/§16, restated here because a signature that silently implies they are
resolved would be a misrepresentation. The code is fail-closed on every one of them: a mismatch **stops
the run** and requires a schema-version change, never a silent alias.

| # | Unresolved item | Current frozen behaviour | If you cannot accept it |
|---|---|---|---|
| S-1 | Exact header spellings and category tokens in the local workbook (`Y`/`N` vs `Yes`/`No`, `Fmale` vs `Female`, `VHD` levels for blocked panels); the UCI landing page documents no per-field codebook | Adapter accepts only the registered 56-header set and registered tokens; anything else aborts with a patient-safe message | Do not sign; a vocabulary change is a new dictionary version, hence a new review |
| S-2 | `BP` — single value, **probably systolic-only**, not documented by the source | One numeric predictor, plausibility guard `[40, 300]` mmHg, no reconstruction of diastolic/pulse pressure | Exclude `BP` only via a new panel version (not possible in this freeze) or accept the ambiguity |
| S-3 | `PR` — source notation "ppm"; unit vs pulse-rate semantics unverified | One numeric predictor, guard `[20, 250]`, no unit conversion | As S-2 |
| S-4 | Whether `Typical Chest Pain`, `Atypical`, `Nonanginal` are mutually exclusive (their joint distribution was never examined) | All three enter as separate binary predictors; no post-hoc collapsing | Accept the encoding as-is or do not sign |
| S-5 | Acquisition timing of resting-ECG and echocardiographic fields relative to angiography is undocumented | Those fields are excluded from the executable panel; the ECG panel stays `REGISTERED_BLOCKED` | No action — the freeze already excludes them |
| S-6 | Definitions/scale evidence for expanded history, examination and functional-class features is secondary-literature only | Expanded panel stays `REGISTERED_BLOCKED` | No action — excluded |
| S-7 | Target threshold semantics: UCI-45 Cleveland uses **> 50 %**, UCI-412 is documented at **≥ 50 %** | Not harmonised anywhere in code; no cross-dataset comparison is permitted | Accept that the discrepancy stays open and unreconciled |
| S-8 | "54 features" on the landing page vs **55 predictors** in the delivered workbook | Both recorded verbatim; no silent resolution | Accept the discrepancy as recorded |

> **Human decision 1 — source semantics:** accept S-1 … S-8 as documented residual uncertainty, or stop.
> Decision: `[BLANK — HUMAN ONLY]` · Name: `[BLANK]` · Date: `[BLANK]`
> If rejected: no local manifest may be created; `preflight` and `run` stay unreachable.

---

## 5. Sample-size limitations that require explicit human acceptance

Reported by the committed tooling (`python -m research.uci412 describe`, `research/uci412/sample_size.py`)
from audited class counts only. This is planning arithmetic, **not** an adequacy verdict and **not** a
result.

| Quantity | Value |
|---|---|
| Participants / events / non-events | 303 / 216 / 87 |
| Outcome prevalence | 0.7129 |
| Reference-coded parameters | 16 |
| Events per parameter (descriptive only — never a justification) | 13.5 |
| Riley outcome-proportion criterion at half-width 0.05 | requires **n = 315** → **`NOT_MET_AT_STATED_HALF_WIDTH`** |
| Shrinkage / optimism / minimum-MAPE criteria | `NOT_ASSESSED_NO_HUMAN_REVIEWED_ANTICIPATED_R2` |
| Uses observed model performance | `false` |

**Consequences the human must accept in writing:**

1. The benchmark may be run as an **internal exploratory feasibility / replication exercise** only.
2. It may **never** be described as adequately powered, as a clinical prediction model, or as evidence of
   predictive adequacy — at n = 303 the R²-independent criterion already fails.
3. The R²-dependent criteria stay `NOT ASSESSED`; an anticipated Cox–Snell R² may **not** be back-derived
   from observed performance, and a future attempt to supply one is a separate human scientific judgement.
4. Observed metrics from any run carry the mandatory banner `INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED`
   and are internal exploratory evidence only.

> **Human decision 2 — sample size:** accept the `NOT_MET` / `NOT ASSESSED` status and its consequences
> (1)–(4).
> Decision: `[BLANK — HUMAN ONLY]` · Name: `[BLANK]` · Date: `[BLANK]`

---

## 6. Maintainer-side activation sequence (all steps human-executed, in order)

Steps 1–2 are the governance act. Steps 3–7 are local, on the maintainer's Windows machine, and are the
only way the code will open a single real row. **No step may be performed by an agent, a bot, or CI.**

### 6.1 Step 1 — the required explicit PR authorization comment

On **this** governance PR, post a review comment containing **exactly** this token, verbatim, as its own
line and with no paraphrase, prefix, or spelling change:

```
AUTHORIZE-M3A-UCI412-INTERNAL-RESEARCH
```

- The token is the frozen constant `M3A_AUTHORIZATION_COMMENT` in `research/uci412/config.py`; the local
  manifest must record the **identical** string or validation fails.
- The comment is a **review artifact**, not the authorization. It authorizes nothing on its own and does
  not close P-1, P-3, or P-5.
- Posting it is a deliberate human act on record. Do not post it if you intend to reject §4 and/or §5.

### 6.2 Step 2 — human-approved merge

Merge this PR yourself, through the GitHub UI, after reviewing the diff. Requirements imposed by the
existing validator (so the merge stays referenceable — see §9):

- merge **into `main`** (merge commit or squash — both keep doc 08 byte-identical; the squash body should
  retain the PR number);
- do **not** let an automation identity perform the merge;
- record the resulting merge commit SHA and the PR number — they become
  `governance_merge_commit_sha` and `governance_pr_number` in the local manifest;
- keep the merge commit reachable in the local clone (`git fetch origin`), because the validator checks
  that the pinned commit exists **and is an ancestor of the checked-out commit**;
- after the merge, `main` must contain a **newer** commit than `ca96be7` (this packet) while doc 08, the
  plan and the dictionary keep the hashes in §2.

### 6.3 Step 3 — satisfy the pre-existing D-046 `DA-A1` read-only chain (repository-external)

This PR **does not** cure the known gap stated in D-048: the checked-in
[`research/audit/gate_da_authorization.json`](../../../research/audit/gate_da_authorization.json) is still
`PENDING_HUMAN_ACCEPTANCE` with null sign-off fields. Locally, create
`data/manifests/gate_da_authorization.local.json` (Git-ignored) from that file by populating the human
sign-off fields, so that it records:

- `workflow_status = "AUTHORIZED_FOR_LOCAL_READ_ONLY_AUDIT"`;
- `datasets.DA-A1.authorization_status = "AUTHORIZED_FOR_READ_ONLY_AUDIT"`, populated `authorized_by`,
  `authorized_date`, `responsible_acquirer`, `audit_reviewer`, `environment`;
- `datasets.DA-A1.training_authorized = false` (**must stay `false`** — D-046 remains audit-only);
- `supervisor_approval_claimed = false`, `gate_pt_status = "CLOSED_REQUIRES_SUPERVISOR_SIGNOFF_P3"`.

The repository record stays `PENDING_HUMAN_ACCEPTANCE`; this local file is a personal local attestation
and is never committed. It gives **audit provenance only** — the permission to fit comes solely from
step 5.

### 6.4 Step 4 — protected provenance + licence snapshot for the exact bytes

Create, under the Git-ignored `data/manifests/`:

- `provenance_manifest.json` following
  [`research/audit/provenance_manifest.template.json`](../../../research/audit/provenance_manifest.template.json),
  with a `DA-A1` entry carrying `uci_id = 412`, `doi = "10.24432/C5Q31T"`,
  `official_source_url = "https://archive.ics.uci.edu/dataset/412/z+alizadeh+sani"`,
  `license_spdx = "CC-BY-4.0"`, `filename = "Z-Alizadeh sani dataset.xlsx"`,
  `relative_path = "data/raw/uci-412/Z-Alizadeh sani dataset.xlsx"`, real `sha256` and `size_bytes`,
  and `license_snapshot_path = "data/manifests/licenses/uci-412-license-snapshot.txt"` with its
  `license_snapshot_sha256`;
- `licenses/uci-412-license-snapshot.txt` containing the licence statement ("CC BY 4.0" /
  "Creative Commons Attribution 4.0").

The workbook's SHA-256 must equal `90fefd4ecdb6263b3f2a260bb2b5d3b9fa92ba35d626dd56ad8c6db5fbbad163`.
Any other bytes mean a different file: **stop and re-audit** — the gate refuses to proceed.

### 6.5 Step 5 — create the protected local M3a authorization (the actual human signature)

Copy [`research/uci412/internal_research_authorization.template.json`](../../../research/uci412/internal_research_authorization.template.json)
to the Git-ignored path

```
data\manifests\uci412_internal_research_authorization.local.json
```

and fill it **exactly** as follows. Everything not listed here stays as the template has it; every value
below is checked by `research/uci412/safety.py::validate_m3a_authorization`, so a near-miss is a hard
failure, not a warning.

| Field | Required value |
|---|---|
| `schema_version` | `"0.1.0"` |
| `proposal_id` | `"M3A-UCI412-INTERNAL-RESEARCH-PROPOSAL"` |
| `authorization_status` | `"AUTHORIZED_FOR_LOCAL_INTERNAL_RESEARCH"` |
| `experiment_type` | `"INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED"` |
| `supervisor_signoff_claimed` | `false` (must stay `false`) |
| `gate_pt_status` | `"CLOSED_REQUIRES_SUPERVISOR_SIGNOFF_P3"` |
| `maintainer_approval_comment_exact` | `"AUTHORIZE-M3A-UCI412-INTERNAL-RESEARCH"` (the template's `REPLACE_WITH_…` prefix must be removed) |
| `governance_pr_number` | this PR's number, as a positive integer |
| `governance_merge_commit_sha` | the merge commit from step 2, 40 hex chars |
| `pinned_protocol_commit_sha` | **identical** to `governance_merge_commit_sha` |
| `authorization_proposal_relative_path` | `"docs/research/gate-pt/08_m3a_uci412_source_specific_benchmark_SPECIFICATION.md"` |
| `frozen_authorization_proposal_sha256` | §2 doc-08 hash |
| `frozen_feature_dictionary_sha256` | §2 dictionary hash |
| `frozen_research_plan_sha256` | §2 plan hash |
| `expected_sha256_from_protected_provenance_manifest` | `"90fefd4ecdb6263b3f2a260bb2b5d3b9fa92ba35d626dd56ad8c6db5fbbad163"` |
| `dataset_id` / `target_column` / `allowed_original_relative_file` / `authorized_source_row_count` | `"DA-A1"` / `"Cath"` / `"data/raw/uci-412/Z-Alizadeh sani dataset.xlsx"` / `303` |
| `panel_schema_id` / `panel_schema_version` | `"uci412_basic_clinical_v1"` / `"1.0.0"` |
| `allowlisted_model_families` | `["prevalence_dummy", "l2_logistic_regression", "constrained_random_forest"]` (exact order) |
| `allowed_operations_if_approved` | the six template operations, unchanged |
| `forbidden_operations` | the ten template prohibitions, unchanged |
| `allowed_runtime` | `"LOCAL_WINDOWS_CPU_ONLY"` |
| `protected_outputs_relative_root` | `"data/uci412-experiments"` |
| `local_signer` | `"Muhammed Fathi"` (must equal the maintainer constant) |
| `local_signed_at_iso8601` | timezone-aware timestamp, e.g. `"2026-10-25T14:12:00+02:00"`; **must be ≥ the merge commit's committer time** and **not in the future** |
| `local_signature_attestation` | verbatim: “I have reviewed and authorize this exact hash-bound local UCI-412 internal research benchmark. I understand Gate PT P-3 remains CLOSED, that no supervisor approval is claimed, and that no clinical use, external validation, or publication claim is made.” |
| `signature_semantics` | `"HUMAN_ATTESTATION_FIELDS_NOT_A_CRYPTOGRAPHIC_SIGNATURE"` |

The template contains no readable patient content and no secret; the populated file is a local personal
attestation. **Never commit it, paste it in a PR, or upload it.** `data/` is Git-ignored and the gate
also verifies that nothing under `data/` is tracked.

### 6.6 Step 6 — hash binding, then preflight

Recompute the three frozen hashes plus the source hash **on the machine that will run**, compare them to
§2, and only then run preflight. Preflight itself checks the bindings, the D-046 chain, the provenance
chain, the licence snapshot, Git-ignored storage, a clean worktree, the local-Windows/CPU/interactive
runtime, and that the pinned merge commit is an ancestor of `HEAD`. It opens **no** workbook rows and
fits nothing.

### 6.7 Step 7 — first real experiment (only after steps 1–6 pass)

Type the confirmation phrase when prompted. The run writes only under `data/uci412-experiments/`, prints
the banner, run ID and report hash, and refuses any configuration other than the frozen default.

---

## 7. Windows-local commands (execute only after authorization)

Environment: Windows 10/11, PowerShell, a **fixed local drive** (no UNC/network path, no junction/symlink
in the repo path), interactive console, `$0`.

```powershell
# 0) Clean checkout at the governance merge commit, on a fixed local drive
git clone https://github.com/Muhammed-Fathi/CardioAssist-AI.git CardioAssist-AI
cd CardioAssist-AI
git fetch origin
$MERGE = "REPLACE_WITH_THE_GOVERNANCE_MERGE_COMMIT_SHA"
git merge-base --is-ancestor $MERGE HEAD; if ($LASTEXITCODE -ne 0) { Write-Error "STOP" }
git status --porcelain --untracked-files=all      # must be empty

# 1) Isolated CPU-only environment (.venv is Git-ignored, so the worktree stays clean)
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r research/uci412/requirements.txt
python -m pip check

# 2) Offline sanity checks — no data, no fitting
python -m pytest tests/uci412 -q
python -m research.uci412 describe
python -m research.uci412 dry-run

# 3) Place the human-authorized local files (never committed), then verify storage protection
#    data\raw\uci-412\Z-Alizadeh sani dataset.xlsx
#    data\manifests\provenance_manifest.json
#    data\manifests\licenses\uci-412-license-snapshot.txt
#    data\manifests\gate_da_authorization.local.json
#    data\manifests\uci412_internal_research_authorization.local.json
python -m research.audit verify-ignore

# 4) Hash binding — all four must match §2 exactly
foreach ($p in @(
  "docs\research\gate-pt\08_m3a_uci412_source_specific_benchmark_SPECIFICATION.md",
  "research\uci412\uci412_cad_research_plan.v0.1.json",
  "research\uci412\schemas\uci412_feature_dictionary.v1.json",
  "data\raw\uci-412\Z-Alizadeh sani dataset.xlsx"
)) { "{0}  {1}" -f (Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash.ToLower(), $p }

# 5) Windows-local preflight — opens no rows, fits nothing
python -m research.uci412 preflight
# expected: status = PREFLIGHT_PASS, source_sha256_and_byte_size_verified = true,
#           source_rows_parsed = false, model_fitting_started = false,
#           code_commit_sha printed, output_root = data/uci412-experiments

# 6) First authorized real experiment — only if step 5 passed
python -m research.uci412 run
#   when prompted, type exactly:  RUN M3A UCI412 LOCALLY
# expected: banner INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED, a run ID
#           run-YYYYMMDDTHHMMSSZ-xxxxxxxx, and the report hash.
# Do NOT commit, upload, or paste data\uci412-experiments\**\predictions.csv.
```

Any `FAIL CLOSED:` message is a completed, correct refusal — record the message verbatim and do not work
around it. Optional operator notes about a stopped run go in
`data\manifests\uci412_failed_runs.local.json` (short single-line strings only).

---

## 8. What voids, revokes, or stops an activation

**Voids an activation (requires a new review + new manifest):**

- any change to doc 08, the plan, the feature dictionary, the adapter, the model grid, the CV scheme, the
  seeds, the metric set, or the threshold — even a "harmless" wording or JSON edit;
- any change to `research/uci412/safety.py` guards or to the D-046 chain contract;
- a different source file, different bytes, a re-download, or a different path;
- a different signer, a different panel, a different dataset id, a different target, an added dataset,
  an added model family, or an added operation;
- a merge that is rewritten/rebased away so the pinned commit is no longer an ancestor of `HEAD`.

**Revokes an activation:** delete or rename `data/manifests/uci412_internal_research_authorization.local.json`.
Without it, `preflight` and `run` fail closed again immediately; nothing else needs editing.

**Stops a run in flight:** any hash mismatch; any new, malformed, unknown, prohibited or identifier
column; any unregistered vocabulary token; an all-missing admitted column; a blank target; a value outside
a plausibility guard; a workbook changed between the pre-run and post-run hashes; any leakage alarm; or any
request to expand data, operations, or outputs.

---

## 9. Why no code or protocol change is needed for a future merge to be consistent

The existing validator already anticipates exactly this pattern, so this packet needs **zero** code edits:

1. `validate_m3a_authorization` binds `frozen_authorization_proposal_sha256` to the **doc-08 blob at
   `governance_merge_commit_sha`** (`git show <merge>:docs/…/08_….md`), not to a directory, PR, or this
   packet. Because this PR leaves doc 08 byte-identical, the bound value is the *same* hash before and
   after the merge — one hash, no ambiguity.
2. It requires `pinned_protocol_commit_sha == governance_merge_commit_sha`, so the "pinned protocol
   commit" **is** the governance merge commit; there is no separate freeze commit to create.
3. It requires that commit to exist locally **and** be an ancestor of the checked-out `HEAD` — satisfied
   by step 0's `git fetch` + `git merge-base --is-ancestor`.
4. It requires `local_signed_at_iso8601` to be **≥ the merge commit's committer timestamp** and not in the
   future — satisfied by signing after the merge, in a timezone-aware form.
5. It requires a positive `governance_pr_number` and the verbatim comment token — supplied by steps 1–2.
6. This packet itself is **not** in the hash-bound set (`PACKAGE_FILES` in `research/uci412/reporting.py`),
   so it can be corrected or annotated later without invalidating a signed manifest, while every file
   that can influence the experiment remains hash-bound.

Consequence: **this governance PR is the last governance artifact required before a maintainer-chosen
local run.** No further documentation cycle, no re-freeze, no code change, no CI change is needed —
only steps 1–7 above, executed by a named human.

---

## 10. Confirmation: no experimental configuration changed

The PR adding this file changes documentation only. Verification (all must print nothing / exit 0):

```bash
git diff --stat origin/main -- research/ backend/ app/ shared/ tests/ .github/ infra/ scripts/
git diff --quiet origin/main -- research/uci412/uci412_cad_research_plan.v0.1.json \
  research/uci412/schemas/uci412_feature_dictionary.v1.json \
  research/uci412/config.py research/uci412/safety.py \
  docs/research/gate-pt/08_m3a_uci412_source_specific_benchmark_SPECIFICATION.md
```

The registered panel, model families and grids, CV folds/seeds, metrics, threshold, negative controls,
guards, blockers and gate statuses are **identical to `main`**. D-048's proposal text is deliberately
**not edited** here: its own closing clause states that changing that section requires a named human
decision, which only the maintainer can give — at ratification time, not in preparation.

---

## 11. Claims and non-claims

**Claimed:** a documentation-only ratification packet exists that (a) restates the frozen scope,
(b) isolates the residual source-semantics and sample-size limitations for explicit human acceptance,
(c) gives the exact, complete activation sequence, and (d) demonstrates that the existing validator can
consume a future merge unchanged.

**Not claimed:** any approval, ratification, signature, authorization, or activation; any supervisor,
ethics or institutional approval; any gate-status change (P-1 pending, **P-3 CLOSED**, P-5 prohibited);
any dataset access, model fitting, performance number, calibration, external validation, transportability,
participant independence, or clinical utility; any readiness for patient care, publication, or deployment.
Synthetic test results are software evidence only.

---

## 12. Human decision block (to be completed only by the named maintainer, outside this file)

Leaving this block blank is the current, correct state.

- Scope accepted (§3): `[BLANK — HUMAN ONLY]`
- Source-feature semantics S-1 … S-8 accepted (§4): `[BLANK — HUMAN ONLY]`
- Sample-size limitations and consequences 1–4 accepted (§5): `[BLANK — HUMAN ONLY]`
- Authorization comment posted verbatim (§6.1): `[BLANK — HUMAN ONLY]`
- Governance PR merged by a human (§6.2) — PR number / merge commit: `[BLANK — HUMAN ONLY]`
- Local manifest created, signed, and never committed (§6.5): `[BLANK — HUMAN ONLY]`
- Maintainer name: `[BLANK]`
- Signature timestamp (timezone-aware ISO-8601): `[BLANK]`
- Attestation: “I have reviewed and authorize this exact hash-bound local UCI-412 internal research
  benchmark. I understand Gate PT P-3 remains CLOSED, that no supervisor approval is claimed, and that no
  clinical use, external validation, or publication claim is made.”
- Status: `PROPOSED — NOT SIGNED — NOT EFFECTIVE`
