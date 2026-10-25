# 16 — Post-PR50 Aggregate Audit Execution Package (REVIEW DRAFT)

**Prepared:** 2026-10-25 · **Base:** `main` at merge of PR #50 (`a92a04f`) · **Revision:** 1.0 · **Status:** capability-reuse assessment + local execution handoff for human review.
**Not** a research protocol, **not** a dataset selection, **not** a training authorisation, **not** a supervisor, clinical or ethics approval, and **not** a result.
**Tracking:** PR #51 (opened for review; deliberately left open — merging it would not authorise any run and does not change a gate).

> **P-1 PENDING · Gate PT P-3 CLOSED (no supervisor sign-off exists) · P-5 NOT MADE — prohibited.**
> D-046 remains **read-only local audit only**; D-047 remains Cleveland-only internal exploratory; D-048 / M3a remains a *proposed, unauthorized* UCI-412 internal benchmark. Nothing in this document authorises data access, acquisition, fitting, inference, pooling, external validation, transfer prediction or model-artefact creation, and none was performed. No frozen dictionary, research protocol, registered plan, experiment result or decision-register entry is modified. **No dataset file was opened, downloaded, re-audited or summarised for this document**; every count quoted here is a software-test count or an already-committed maintainer-reported aggregate.

---

## 0. What this package is

This revision answers one question — **can the repository's existing, authorized read-only audit infrastructure resolve the remaining aggregate blockers without new science, new data, or new permissions?** — and then hands the maintainer the exact local commands for whatever is genuinely executable.

It contains, in the requested order:

| Requested deliverable | Section |
|---|---|
| 1. Existing-capability reuse assessment | **§1** |
| 2. Smallest necessary code/test changes | **§1.3**, **§3.3** (one focused module + one test module; no duplicate tool) |
| 3. Reproducible local execution handoff | **§2.2**, **§4** |
| 4. Synthetic test and CI results | **§5** |
| 5. Scientific questions each local audit can close | **§6** |
| 6. What remains impossible to establish from these sources | **§7** |

### 0.1 Verification boundary — what this revision did and did not do

- **No patient-level, raw, processed or workbook file was accessed.** This checkout contains no `data/` payload; the audit toolchain was exercised **only** on the repository's own synthetic software fixtures in a temporary directory.
- **No archive, workbook sheet or bundled documentation was inspected**, and the UCI-411 workbook was not touched. UCI-412 and UCI-411 are the same 303 participants (Gate DA/PT record); nothing here re-opens that question.
- **No fitting, selection, tuning, calibration, metric, threshold, pooling or comparison** was performed or enabled.
- **The tool cannot grant permission.** Every command below re-checks the local authorization manifest, the recorded provenance hashes, the committed state of the frozen dictionary, and the Git-ignore posture *before* any source byte is opened, and stops on the first failure. A passing guard means "not obviously unauthorized", never "approved".
- **Numbers about the real files are not produced here.** They are produced only by the maintainer's local run, and only that run's own report may be quoted.

### 0.2 One governance-relevant finding to read first

Two of the three Phase-3 questions are **answerable today inside D-046** at aggregate level; the third is **not authorized at all**, and the existing guard already enforces that rather than merely documenting it (§3.4). Phase 2 needs **no new code whatsoever** (§1.2, §2). This is the substance of the reuse assessment: the missing piece was one narrow diagnostic layer on `DA-A1`, not a new audit platform.

---

## 1. Deliverable 1 — Existing-capability reuse assessment

### 1.1 How the assessment was made

Read-only inspection of: `docs/DECISIONS.md` (D-046 ratification, D-047, D-048, P-1…P-6); Gate PT document 15 revision 15.1 (§0.1, §3 U-1…U-7, §4 H-1…H-6, §5, §9.2); Gate DA documents 10, 14 and 17; `research/audit/**` (README, `cli.py`, `validators.py`, `duplicates.py`, `availability_scenarios.py`, `cross_site_feasibility.py`, `provenance.py`, `reporting.py`, `git_safety.py`, `registry.py`, `synthetic_fixtures.py`); `tests/audit/**`; and `research/uci412/` (feature dictionary schema 1.1.0 and `adapter.py`) to determine what already counts tokens and under which authorization.

### 1.2 Capability map

| # | Requested check | Existing capability | Verdict | Action |
|---|---|---|---|---|
| **P2-1** | Five-field literal value domains and availability (Cleveland–Hungary) | `cross_site_feasibility.build_categorical_code_compatibility` (exact observed code sets + counts for `sex`, `cp`, `restecg`), `build_measurement_unit_diagnostics` (predeclared value bands, zero/negative and implausible counts for `age`, `trestbps`), `build_class_conditional_availability` (per-field observed counts by original target label), `_five_field_joint_availability` | **COVERED** | Reuse; run only |
| **P2-2** | Original target-code distribution and source-supported binary representation | `build_target_code_compatibility`: `original_target_label_counts` (0–4), `missing_target_value_count`, `target_codes_outside_documented_domain_count`, `derived_binary_counts` (0 vs 1–4, labelled in-memory stratification only), `observed_target_label_set_relation` | **COVERED** | Reuse; run only |
| **P2-3** | Missing-value conventions and completeness | `validators.audit_uci_45_processed_file` reports per column `{"null_or_blank", "question_mark", "minus_nine_sentinel"}`, `total_missing_cells`, `overall_cell_completeness_ratio`; cross-site diagnostics add per-field `missing_count` | **COVERED** (needs the `run-audit` command, not only the cross-site command) | Reuse; run both |
| **P2-4** | Privacy-safe overlap / collision diagnostics | `compute_exact_profile_multiset_overlap` + `build_exact_profile_overlap_checks`: per-profile multiset intersection, side collision rows, candidate record pairs, maxima, rule text; no profile values emitted | **COVERED** | Reuse; run only |
| **P2-5** | Source integrity and provenance preservation | `validate_provenance_manifest` (SHA-256, byte size, licence snapshot, exact-path containment), `ByteIdentityGuard` across the run, `verify_git_ignore` | **COVERED** | Reuse; run only |
| **P3-1** | Aggregate token-frequency counts for the six text-binary columns | **Nothing in the audit toolchain.** `research/uci412/adapter.py` computes `observed_category_token_counts` / `numeric_binary_source_value_counts`, but only inside a **D-048** internal-research run that is `PROPOSED_NOT_AUTHORIZED`, and under a different authorization manifest | **GENUINELY MISSING for audit** | New minimal module |
| **P3-2** | Four-way joint-count summaries for the chest-pain descriptors | Nothing anywhere in the repository | **GENUINELY MISSING** | New minimal module |
| **P3-3** | Verification of existing registered coding coverage | Validators check types/target/domain rules but never compare observed cells against the *registered* source vocabulary in the frozen dictionary | **GENUINELY MISSING** | New minimal module |
| **P3-4** | Review of bundled source documentation | Not authorized: `DA-A1` authorizes exactly `Z-Alizadeh sani dataset.xlsx`; `validate_provenance_manifest` **rejects** any other file in `data/raw/uci-412/` | **NOT PERMITTED** | Record the status; do not attempt |

### 1.3 What that means, and why no duplicate tool was created

1. **Phase 2 needs zero code changes.** The DA-A2 toolchain already answers all five requested Cleveland–Hungary aggregate checks — through **two** existing commands whose scopes are different and complementary: `run-audit --datasets DA-A2 --quarantine-raw-cleveland` (per-file coding, missing-token kinds, completeness, class distribution) and `research.audit.cross_site_feasibility` (predeclared five-field compatibility, source-label relation, exact-profile overlap with multiplicity). Any new DA-A2 script would duplicate both, so none was written.
2. **Phase 3 needed exactly one narrow layer.** The genuinely missing capability is aggregate token/coverage/joint-count reporting on the already-authorized `DA-A1` workbook. It was added as **one** module, `research/audit/uci412_source_semantics.py`, which **reuses** `audit_uci_412_or_411_workbook` for parsing and validation, `ByteIdentityGuard`, `validate_provenance_manifest`, `validate_and_resolve_report_output_path`, `assert_exact_keys`, `assert_int_not_bool` and `verify_report_no_patient_rows`. No parser, schema helper, hash guard or privacy scanner was re-implemented.
3. **The research adapter is not a substitute.** `research/uci412/adapter.py` is a *modelling* pipeline component. Using it to obtain token counts would (a) require the D-048 activation that does not exist, and (b) place an audit operation inside a research-run boundary. The audit layer therefore reads the **same frozen dictionary read-only** and checks it is a *committed, clean* repository file (a local or uncommitted vocabulary fails closed), recording its SHA-256 in the report — without importing the research package (which would pull `numpy` into the isolated `$0` audit environment).

---

## 2. Phase 2 — Cleveland–Hungary aggregate verification (no code change)

**Hard boundary, restated because it is the point of the phase:** Hungary may be used **only** for aggregate, descriptive verification. It must not be used for model fitting, hyperparameter selection, threshold selection, calibration, or any prediction-based evaluation, and no patient-level row, identifier or fingerprint may be exported. `run-audit` and `cross_site_feasibility` both refuse to emit rows, both byte-guard every DA-A2 original, and both write only inside `data/reports/`.

### 2.1 Requested check → where the number comes from

| Requested verification | Report location (generated locally, never committed) | Legitimate reading |
|---|---|---|
| Five-field literal value domains | `cohorts.hungarian.categorical_code_compatibility.fields.{sex,cp,restecg}.observed_code_counts`; `cohorts.hungarian.measurement_unit_diagnostics.fields.{age,trestbps}.band_counts` | The code sets/bands actually present in the delivered file. Continuous fields are reported as **predeclared bands**, not literal distinct values: enumerating every distinct blood pressure is a re-identification hazard and was deliberately not implemented. |
| Five-field availability | `cohorts.hungarian.class_conditional_field_availability.strata.<stratum>.{per_field_observed_count, trestbps_zero_count, all_five_fields_observed_literal, all_five_fields_observed_zero_trestbps_unavailable, at_least_one_of_five_fields_missing_literal}` | Records with the field observed, by original target label. **Not** effective sample size, model eligibility or usable cohort size. The doc-14 expectation is `292/294` at the resting stage and `95/294` for the full exercise bundle under the conservative zero rule; the run re-derives these from the file rather than quoting them. |
| Original target-code distribution | `cohorts.hungarian.target_code_compatibility.original_target_label_counts` | Purely what codes `num` contains. Translation/recoding is never performed. |
| Source-supported binary representation | `.derived_binary_counts` + `.derived_binary_rule` + `.observed_target_label_set_relation` + `.semantic_equivalence_status` | The arithmetic of `0` vs `1–4` **as an in-memory stratification**. Codebook-level convention is documented (Gate PT 15 §4 H-1); **delivered-file equivalence is confirmed only as code counts**, never as clinical equivalence. |
| Missing-value conventions | `dataset_audits.DA-A2.processed_files.processed.hungarian.data.missingness.per_column_missing` (keys `question_mark`, `minus_nine_sentinel`, `null_or_blank`) plus `.overall_cell_completeness_ratio` | Which sentinel convention each missing cell used and how complete each column is. It does **not** explain the missingness mechanism. |
| Completeness | same block (`total_missing_cells`, `columns_with_missing_count`) + the joint-availability fields above | Source-level completeness counts, not a complete-case analysis plan. |
| Privacy-safe overlap / collision | `exact_profile_overlap_checks[]` for `PREDECLARED_FIVE_FIELD_CORE_PANEL`, `CONVENTIONAL_11_PREDICTOR_NO_CA_THAL`, `CONVENTIONAL_13_PREDICTOR`: `distinct_matching_profiles`, `minimum_multiplicity_intersection_count`, `collision_rows_in_*`, `candidate_record_pairs`, `max_profile_multiplicity_in_*` | Four different collision quantities with multiplicity preserved (worked asymmetric example in Gate DA 17 §6.1). **None** counts duplicate, identical or matched patients; a high or zero count never proves identity or independence. |
| Source integrity / provenance | `input_integrity_and_privacy.byte_identity_snapshots[]`, `governance_and_authorization.*`, `scope_and_evidence_boundary.*` | Local byte identity against the human-attested manifest, plus unchanged posture (`gate_pt_status`, `model_fitting_authorized`). It cannot prove upstream origin; that status stays `HUMAN_ATTESTED_NOT_INDEPENDENTLY_PROVEN_BY_LOCAL_HASH`. |

### 2.2 Commands — see §4.3 (steps 7 and 8). Nothing else is required.

---

## 3. Phase 3 — UCI-412 targeted source-semantic audit

### 3.1 What the authorized DA-A1 infrastructure already supports

`audit_uci_412_or_411_workbook` (used by `run-audit --datasets DA-A1`) already gives, on the authorized workbook only: sheet reconciliation, the 54/55/56 column discrepancy, `Cath` spelling/shape (`Cad` → canonical `CAD` in memory only) and class counts, per-column missing-cell kinds, inferred column types, mixed-type rejection, suspicious-value rules, echo/lab timing flags, artery-column leakage rejection, within-dataset duplicates, and a row-fingerprint list used only to *scan* reports. Reusing it means this audit inherits all of that validation instead of weakening or re-implementing it.

### 3.2 What was genuinely missing

The three Phase-3 questions were unanswerable because nothing recorded (i) which *registered tokens* actually occur and whether every cell falls inside the registered vocabulary, (ii) how the four chest-pain descriptors co-occur per record, or (iii) an explicit, machine-checked statement that the bundled documentation is out of scope. Doc 15 §3 U-4 and §5 record exactly this gap ("the *token inventory* … is **not recorded anywhere in the repository**"), and doc 15 §9.2 lists the same smallest step.

Two details make the census non-trivial, and both are enforced rather than assumed:

- **The dictionary registers two different source representations.** Amendment A-1 corrected exactly six predictors to numeric `0/1` (DM, HTN, Current Smoker, EX-Smoker, FH, **Typical Chest Pain**) and left the other six (Sex, DLP, Atypical, Nonanginal, Exertional CP, Dyspnea) on text vocabularies. The audit is therefore **representation-aware**: a numeric `0` in a text-registered column is *unregistered*, and the strings `'0'`/`'1'` in the numeric-registered column are *unregistered* too — matching the dictionary's own `legacy_tokens_rejected` rule instead of silently accepting a shape that the frozen vocabulary rejects.
- **"Vocabulary failure" and "blank cell" are different findings.** The U-4 claim is about tokens, so the file-level result has three states: `CONSISTENT_WITH_PRIOR_CLAIM`, `CONSISTENT_WITH_PRIOR_VOCABULARY_BUT_MISSING_CELLS_OBSERVED`, and `NOT_CONSISTENT_WITH_PRIOR_CLAIM`. A per-column cell-shape census (`text` / `integral_number` / `non_integral_number` / `boolean` / `other`) records the shape of every observed cell — counts only, never values — so a wholly numeric column is visible immediately without any source string entering the report.

### 3.3 The minimum implementation actually made

| Artefact | Change | Why it is the minimum |
|---|---|---|
| `research/audit/uci412_source_semantics.py` (**new**) | Aggregate registered-token census, registered-vocabulary coverage, four-way joint census (direction-free token cells + registered-code cells + `0–4` descriptor distribution), fixed bundled-documentation status, strict aggregate report schema, Markdown summary, guarded run/CLI | Only the missing diagnostics; parsing, hashing, containment, output locking and privacy scanning are reused |
| `tests/audit/test_uci412_source_semantics.py` (**new**) | 26 synthetic tests: pure arithmetic/schema checks, report-schema tamper checks and guarded end-to-end/CLI checks | Proves fail-closed behaviour without any real data |
| `research/audit/synthetic_fixtures.py` (small optional keyword) | `uci_412_rows_override=` lets a test supply registered-token rows; provenance is still recorded after writing, so hashes stay consistent | Avoids a second fixture builder; default behaviour unchanged |
| `research/audit/README.md` | New §5 + audit-function row 13 | Documented capability, not a new governance artefact |

**Deliberately not implemented:** any new parser, any new provenance/hash/path helper, any CLI subcommand in `cli.py`, any new workflow file, any change to `research/uci412/**`, any change to `docs/DECISIONS.md` or any P-item, any DA-A2 code, and any "convenience" export of token values, rows, profiles or fingerprints.

### 3.4 Authorization determinations

**P3-1/P3-2/P3-3 — determination: `WITHIN_D046_READ_ONLY_AUDIT_SCOPE`.**
The `DA-A1` purpose recorded in D-046 covers "workbook sheets …, columns, data types, 54/55/56 feature-count discrepancy, missingness, within-cohort duplicates, H-01 threshold wording and L-08 pre-angiography feature availability timing". Aggregate token-frequency counts, registered-vocabulary coverage and a four-way joint count of four columns are **descriptive coding checks on the same single authorized file**, producing counts only, with no fitting, selection, tuning, evaluation, calibration or explanation. No new file, dataset, licence or storage location is introduced, so no new acquisition authorization is required **for this audit**.
**Where authorization stops:** the output is *not* evidence that the source is semantically understood, and it does not authorise any use of these columns in a model. `DA-B1`/`DA-B2` are untouched, and no cross-family statement is produced.
**The code does not decide this.** The tool requires the maintainer's manifest, the `--acknowledge-read-only-scope` flag and a clean committed dictionary, and records `d046_scope_requires_maintainer_judgement_not_granted_by_code = True`. If the maintainer judges any requested count to fall outside the recorded purpose, the run must not happen.

**P3-4 — determination: `NOT_PERFORMED_NOT_AUTHORIZED_BY_D046`.**
The archive's "full documentation" item is a **different file** from the single authorized `Z-Alizadeh sani dataset.xlsx`. D-046's `DA-A1` inventory names exactly one file, `Z-Alizadeh sani dataset.xlsx`, lists **no** optional documentation file (the committed template records `optional_documentation_files: []`), and excludes only the UCI-411 workbook; nothing in the authorization names any documentation file. Therefore:
- inspection is **not** permitted under the exact existing authorization;
- it is not implied by "read-only audit" and is not inferred here;
- the guard is already active, not merely documentary: `validate_provenance_manifest` raises `ArchiveSecurityError` for **any** file in `data/raw/uci-412/` outside the authorized list, so a documentation file cannot even be present during an authorized run;
- enabling it would require a **new explicit human authorization** naming that exact documentation file, an extended read-only scope, and a **re-recorded** provenance manifest — then a fresh review of any vocabulary change, because the frozen dictionary is not edited by an audit.

The report records this as a fixed status, and a synthetic test (`test_run_refuses_an_unapproved_documentation_file_in_the_dataset_directory`) proves the guard fires.

### 3.5 Fail-closed behaviour (each one is a synthetic test)

| Guard | Behaviour |
|---|---|
| Scope acknowledgement | Refuses to run without `--acknowledge-read-only-scope` |
| Global D-046 authorization | Requires `workflow_status = AUTHORIZED_FOR_LOCAL_READ_ONLY_AUDIT` |
| Dataset authorization | Requires `DA-A1 … AUTHORIZED_FOR_READ_ONLY_AUDIT` with all sign-off fields populated |
| Prohibited authorizations | `model_fitting_authorized` and the other five flags must be `false`; `supervisor_approval_claimed` must be `false` |
| Gate PT | Must remain `CLOSED_REQUIRES_SUPERVISOR_SIGNOFF_P3` |
| Provenance | SHA-256 + exact byte size must match the manifest |
| Single-file scope | Refuses if the `DA-A1` provenance entry contains anything but the one authorized workbook |
| Unapproved files | Any extra file in `data/raw/uci-412/` aborts (`ArchiveSecurityError`) |
| Dictionary commitment | Untracked, modified or symlinked dictionary → abort; schema id must match |
| Output paths | JSON/Markdown only inside `data/reports/<filename>.{json,md}` |
| Byte identity | Source bytes verified before and after the run |
| Report schema | Strict allowlisted aggregate schema; unknown keys, a non-`false` certification flag, non-integer counts or inconsistent census arithmetic → abort |
| Privacy | Existing row/fingerprint scanner runs on JSON **and** Markdown before either is written |
| Unregistered tokens | Counted, never echoed; the report cannot carry an unexpected source string |

### 3.6 What the new audit deliberately does not do

No reading of `UCI-411`, `UCI-45`, raw or unapproved files. No archive opening. No values imputed, recoded, trimmed or translated. No stem of `Cath` beyond the existing validator. No model, metric, statistic, threshold, calibration, SHAP/LIME, pooling or comparison. No change to the frozen dictionary (the report records its SHA-256; schema 1.1.0 is `503c0e08…5da9320` at this revision, so any drift is visible). No change to any P-item, D-decision, protocol or registration.

---

## 4. Phase 4 — Local execution handoff (Windows PowerShell)

**Environment:** `E:\CardioAssist_AI_GitHub_Starter`, existing audit interpreter `E:\CardioAssist_PR11_Audit_Venv\Scripts\python.exe`, Python 3.12, `$0`, CPU-only, local.
**Before you start:** the working tree must be clean and synced to `main` **including the merge of the PR that introduced this package**. If the tree is dirty, stop — do not stash patient data-adjacent files or "tidy" `data/` to make a check pass.

### 4.1 Preflight — authorization and provenance first (opens no source file)

```powershell
Set-Location "E:\CardioAssist_AI_GitHub_Starter"
$python = "E:\CardioAssist_PR11_Audit_Venv\Scripts\python.exe"

# 0. Repository state and dependencies
git status --short
git rev-parse HEAD
& $python --version
& $python -m pip check

# 1. Authorization record: D-046 authorized, Gate PT CLOSED, no fitting flags
& $python -m research.audit check-auth --auth-manifest "data/manifests/gate_da_authorization.local.json"

# 2. Git-ignore and tracking posture for /data/
& $python -m research.audit verify-ignore

# 3. Dry-run preflight (no dataset is read; it only re-checks governance state).
#    These commands default to the committed PENDING template, so pass the local
#    manifest explicitly. With an authorized local manifest the statuses should read
#    AUTHORIZED_FOR_READ_ONLY_AUDIT; with the template they read
#    PENDING_HUMAN_ACCEPTANCE, which is the expected CI behaviour.
& $python -m research.audit dry-run --auth-manifest "data/manifests/gate_da_authorization.local.json"
& $python -m research.audit dry-run --json-out data/reports/preflight_report.json --markdown-out data/reports/preflight_report.md
& $python -m research.audit self-test

# 4. The tool's own synthetic tests must pass in THIS environment first
& $python -m pytest tests/audit -q -W error
```

**Stop if** `check-auth` does not show `AUTHORIZED_FOR_READ_ONLY_AUDIT` for the dataset you intend to audit, if `model_fitting_authorized` is not `false`, if `gate_pt_status` is not `CLOSED_REQUIRES_SUPERVISOR_SIGNOFF_P3`, if `verify-ignore` does not pass, or if any test fails.

### 4.2 Provenance and byte integrity (no source byte is opened)

```powershell
# 5. Confirm the provenance manifest is present and still matches the originals.
#    The audits re-verify SHA-256 and exact byte size themselves and abort on any
#    mismatch. Do NOT hand-edit the manifest to "fix" a hash.
Get-Item "data\manifests\provenance_manifest.json" | Select-Object Length, LastWriteTime

# 6. Confirm nothing under /data/ is tracked or staged
git ls-files -- data
git status --porcelain -- data/
```

**Stop if** `git ls-files -- data` prints anything, or if step 6 lists staged/untracked-but-unignored entries.

### 4.3 Runs

```powershell
# 7. DA-A2: per-file coding, missing-token conventions, completeness, class distribution.
#    Raw Cleveland stays quarantined (never parsed); processed cohorts and the other
#    raw cohorts are audited normally and the partial result is flagged explicitly.
& $python -m research.audit run-audit --datasets DA-A2 `
  --quarantine-raw-cleveland `
  --auth-manifest data/manifests/gate_da_authorization.local.json `
  --provenance-manifest data/manifests/provenance_manifest.json `
  --json-out data/reports/uci-45-da-a2-quarantined-audit.json `
  --markdown-out data/reports/uci-45-da-a2-quarantined-audit.md

# 8. DA-A2: predeclared Cleveland-vs-Hungary/VA five-field compatibility,
#    source target-label relation, privacy-safe exact-profile overlap with multiplicity.
& $python -m research.audit.cross_site_feasibility `
  --auth-manifest data/manifests/gate_da_authorization.local.json `
  --provenance-manifest data/manifests/provenance_manifest.json `
  --json-out data/reports/uci-45-cross-site-feasibility.json `
  --markdown-out data/reports/uci-45-cross-site-feasibility.md

# 9. DA-A1: UCI-412 registered-coding coverage + four-way chest-pain joint census
#    + bundled-documentation authorization status. Counts only; unregistered token
#    text is never emitted.
& $python -m research.audit.uci412_source_semantics `
  --auth-manifest data/manifests/gate_da_authorization.local.json `
  --provenance-manifest data/manifests/provenance_manifest.json `
  --acknowledge-read-only-scope `
  --json-out data/reports/uci-412-source-semantics.json `
  --markdown-out data/reports/uci-412-source-semantics.md
```

Each command prints a short aggregate summary (status labels, counts, output paths) and no row value. Run them one at a time; do not chain them with `;` or `|`, so a failure is never masked.

### 4.4 Post-run verification and privacy review

```powershell
# 10. Repository and custody unchanged; nothing under /data/ tracked
git status --short
git ls-files -- data

# 11. Only expected reports were created
Get-ChildItem data\reports | Select-Object Name, Length, LastWriteTime

# 12. Human privacy review of each report BEFORE sharing any excerpt:
#     open the .md, confirm it contains aggregates only, and confirm no value that
#     could identify a participant.
```

Reporting rules: keep every report **local and Git-ignored**. Never commit, paste or upload a report, a manifest, a licence snapshot, a row, a profile or an individual record hash. After review, quote numbers only with the label `REAL_LOCAL_AGGREGATE_READ_ONLY_AUDIT_NOT_MODEL_OR_CLINICAL_EVIDENCE` and state that they were maintainer-executed, not re-run by CI.

### 4.5 Abort rules (never weaken a guard to make a run pass)

Stop and report the exact error if **any** of the following occurs: authorization status changed or a sign-off field is empty; a prohibited flag is not `false`; `gate_pt_status` is not the closed value; a SHA-256 / byte-size mismatch; an unexpected or unapproved file in a dataset directory; an untracked, modified or symlinked dictionary; a report output path outside `data/reports/`; a parser or format error; a schema or privacy-scanner rejection.

**Never**: edit `.gitignore`, the authorization manifest, the provenance manifest or the frozen dictionary to make an audit pass; replace a protected original with a "clean" copy; decode a failing file with `errors="ignore"`; delete or re-extract a quarantined file; copy a documentation member into `data/raw/uci-412/`; or add a token to the dictionary so a coverage check succeeds. Each of those converts a reproducible negative finding into an unreproducible positive one.

---

## 5. Deliverable 4 — synthetic tests and CI results

| Check | Result |
|---|---|
| `python -m pytest tests/audit -q -W error` (isolated venv with **only** `research/audit/requirements.txt`: openpyxl + pytest; Python 3.11.2) | **430 passed**, 0 failed, 0 warnings-as-errors |
| `python -m pytest tests/experiments tests/audit -q -W error` (third-party suite the `synthetic-experiment-runner-validation` workflow runs) | **462 passed** |
| `python -m pytest tests/uci412 -q -W error` (the `research/uci412` suite, unaffected by this change) | **374 passed** |
| New tests, `tests/audit/test_uci412_source_semantics.py` | **26 passed** — 13 pure arithmetic/schema/render checks, 12 guarded end-to-end/CLI checks, 1 synthetic-fixture shape check |
| Baseline before this change | 404 passed — no pre-existing test was modified or removed; `synthetic_fixtures.py` gained an optional keyword with unchanged default behaviour |
| `python -m research.audit check-auth` / `verify-ignore` / `dry-run` / `self-test` | all exit 0 on the committed PENDING baseline manifest, as designed |
| `python scripts/verify_sources.py` | all source SHA-256 match; supervisor classification intact (25 papers) |
| Workflow `audit-toolchain-validation` | unchanged; runs `pytest tests/audit -q -W error` plus the four CLI checks on **Python 3.11 and 3.12**, and `synthetic-experiment-runner-validation` runs `pytest tests/experiments tests/audit` on the same two versions. Both run automatically on this PR; **read the two per-version job results in the PR's Checks tab — they are the authoritative cross-version evidence.** This sandbox could not retrieve them (the GitHub integration token has no Actions scope), so no cross-version result is claimed here |
| Workflow-step replication on **Python 3.11** (the only interpreter in this sandbox) | every step of `audit-toolchain-validation` and `synthetic-experiment-runner-validation` was replayed locally and exited 0: `pytest tests/audit`, the four CLI commands, `scripts/verify_sources.py`, both artifact guards, `pytest tests/experiments tests/audit`, `pytest tests/uci412`, and `python -m research.experiments dry-run`. **Python 3.12 is CI-only and is not claimed here.** |
| Synthetic fixture provenance | no `data/` file, no row, no manifest and no report is committed; all fixtures live in a temporary directory |

The tests specifically prove: cell classification never returns an unregistered token's text; a numeric cell in a text-registered column (and a numeric *string* in the numeric-registered column) is rejected rather than silently matched; the coverage partition always equals the row count and the cell-shape census accounts for every observed cell; both census totals equal the censused-record count; the descriptor distribution sums to it; a missing or unregistered cell removes the record from the census and is counted separately; a blank cell is reported as a missing cell and not as a vocabulary failure; the report schema rejects patient-row keys, non-`false` certification flags, a `true` documentation-authorization claim, unknown status triples and inconsistent census arithmetic, any `audit_summary` field that disagrees with the section it summarises, and any evidence status other than the single fixed verified label; and every guard in §3.5 fires.

---

## 6. Deliverable 5 — the specific scientific questions each local audit can close

"Close" means *produce the decisive aggregate evidence at the level named*. It never means "produce a clinical conclusion".

### 6.1 Phase 2 (existing DA-A2 toolchain, steps 7–8)

| Question | Closed at this level | Not closed |
|---|---|---|
| **H-2 file level** — do the delivered Hungarian `age/sex/cp/trestbps/restecg` values sit in the documented code/unit domains? | Yes: exact observed code sets, predeclared value bands, zero/negative and implausible counts, per-column domain conformance, and a heuristic unit verdict explicitly marked "not proof of unit identity" | Device/observer/era heterogeneity; whether "on admission" was applied identically in 1983–1987 |
| **H-1 file level** — what original `num` codes does the delivered Hungarian file contain, and how many records fall on each side of `0` vs `1–4`? | Yes: exact 0–4 counts, missing/outside-domain counts, derived binary counts, and the observed label-set relation to Cleveland | Any semantic equivalence of the endpoint across sites |
| **H-3 quantity** — how much is missing, under which sentinel convention, per column? | Yes: per-column `?`/`-9`/blank counts, total missing cells, completeness ratio, five-field joint availability, expected 292-of-294 resting availability re-derived from the file | The missingness **mechanism**, and any complete-case analysis plan |
| **H-5 supported part** — do Cleveland and Hungary share exact five-field / 11- / 13-predictor profiles, and with what multiplicity? | Yes: the four collision quantities per profile set, so the reviewer can state an aggregate lower/upper picture of profile coincidence | Person-level independence, the 294-vs-425 release discrepancy, and any duplication *rate* |
| **Provenance** — are the analysed bytes the ones that were acquired and recorded? | Yes: local SHA-256 + byte-size verification before and after, with byte-identical snapshots | Upstream origin (still human-attested) |

### 6.2 Phase 3 (new DA-A1 audit, step 9)

| Question | Closed at this level | Not closed |
|---|---|---|
| **U-4 recording half** — which registered tokens actually occur in the six text-binary columns, and how often? | Yes: per-column registered-token counts, observed-token list, missing cells, unregistered cells, distinct unregistered values, a cell-shape census, and an explicit file-level result against the prior "all 303 cells accepted" claim — `CONSISTENT_WITH_PRIOR_CLAIM`, `CONSISTENT_WITH_PRIOR_VOCABULARY_BUT_MISSING_CELLS_OBSERVED` or `NOT_CONSISTENT_WITH_PRIOR_CLAIM` | Which token the owner intended; whether `Fmale` and `Female` are interchangeable; whether data entry was consistent over time; the direction of `Sex` coding as an owner-confirmed fact |
| **U-4 failure mode** — can an unregistered token silently pass the adapter? | Yes, negatively: any unregistered cell is counted and flagged, and its text never reaches a report | Whether the *research* adapter would accept it (that is a D-048 run, not this audit) |
| **U-5b** — do the four chest-pain descriptors co-occur within records, i.e. are the flags mutually exclusive in the delivered file? | Yes, at two levels: a direction-free registered-token census over the full registered-token product, and a registered-code census with a `0–4` descriptor-count distribution and an explicit count of records carrying ≥2 descriptors | U-5a (what counts clinically as each descriptor); whether co-occurrence reflects questionnaire design, transcription, or clinicians recording several descriptors; any angina classification or mapping to UCI-45 `cp` 1–4 |
| **P3-4** — is the bundled documentation inspectable under the current authorization? | Yes: **no**, as a fixed, code-enforced status, with the exact additional authorization a future attempt would need | Whether the documentation would have resolved U-1/U-2/U-5a/U-6 — unknown until it is separately authorized and read |

### 6.3 What a *successful* pair of runs therefore changes in the blocker matrix

It moves **U-4** from "the registered set covers the cells" to "the delivered tokens are exactly X and Y, with counts" (the recording half), moves **U-5b** from "never examined" to a measured co-occurrence distribution, and re-derives **H-1/H-2/H-3** at the delivered-file level. It does **not** promote any of them to `RESOLVED`: doc 15's binding rule stands — *a documentation-level resolution is not a record-level verification, and evidence consistent with a claim is not evidence of it*. Human adjudication is still required, and the descriptor-count distribution in particular remains conditional on a provisionally-directed coding.

---

## 7. Deliverable 6 — what remains impossible to establish from these sources

These are limitations of the sources and the authorization, not of the tools. No amount of additional read-only auditing closes them.

1. **U-5a — chest-pain elicitation definitions.** What made a clinician record "typical", "atypical", "non-anginal" or "exertional"? Not in the landing pages, not in the accessible primary text, not in the authorized file. Requires the source questionnaire or owner clarification.
2. **U-6 — UCI-412 per-field measurement timing.** No timing statement exists on the page or in the accessible primary text; the workbook carries no dates. The pre-angiography decision moment therefore **cannot be claimed for any of the sixteen fields**, and the bundled documentation is not authorized (§3.4). Route B stays on `HOLD`.
3. **U-1 / U-2 — `BP` quantity and `PR` unit.** A token census says nothing about whether `BP` is systolic, diastolic or unspecified, or whether `PR` is beats·min⁻¹. Owner documentation, the paywalled table, or owner confirmation is required — none is available here.
4. **Owner coding documentation for the six numeric binaries (S-9).** Direction remains `PROVISIONAL`/secondary-source-based; the audit can corroborate representation and counts, never semantics.
5. **X-1 / U-7 — the 50 % boundary.** UCI-45 (`>50 %`) and UCI-412/411 (`≥50 %`) are *related but not identical*. No per-record stenosis value survives into any released file, so exact-boundary cases **cannot** be identified or reconciled empirically. This is a `NO-GO`, not a task.
6. **H-4 — per-record Hungarian timing.** The protocol statement ("within 6 weeks before the angiogram") is documented; per-record dates are not established, and the raw date fields are not authorized for that analysis.
7. **H-5 — person-level independence and the 294-vs-425 release relationship.** Identifier-free data cannot prove independence, and an overlap audit cannot separate "shared patient" from "same profile". Needs an explanation from the custodians plus a human disposition.
8. **H-6 — external-validation precision.** Requires a locked model, declared estimands/tolerances and a statistician's prespecified ruling. None exists; the descriptive binomial arithmetic is not a validation threshold.
9. **Any transportability, calibration, performance, fairness or clinical-utility statement.** Not producible read-only, and prohibited by P-5 in any case.
10. **Any per-record or per-participant statement.** By construction: the audit is aggregate-only, and the privacy controls are designed so that no such statement can be written into a report even accidentally.
11. **Upstream authenticity.** SHA-256 proves local byte identity against a human-attested record; it does not prove the file came from UCI.
12. **Whether the delivered workbook equals what the authors released in content.** Only the local bytes are verified.
13. **Anything about Egypt, contemporaneous populations, or current practice.** These are historical benchmark cohorts; a contemporary claim needs new, separately governed data.

---

## 8. Governance statement

- No decision, protocol, plan, registration, feature dictionary or P-item is changed by this package. **P-1 PENDING · P-3 CLOSED · P-5 NOT MADE — prohibited**, unchanged. D-046 remains read-only local audit; D-047 remains Cleveland-only internal exploratory and was neither extended nor re-run; D-048 / M3a remains proposed and unauthorized.
- No model was fitted, selected, tuned, calibrated or evaluated; no threshold was chosen; no SHAP/LIME value was computed; no cohorts were pooled; no comparison result was produced.
- No patient-level file, row, identifier or fingerprint was read, produced, exported, committed or pasted anywhere.
- **Nothing in this document authorises a run.** The local manifest, the maintainer's judgement on scope, and the guards in §3.5 and §4.5 are what permit an execution — and any one of them may refuse it.
