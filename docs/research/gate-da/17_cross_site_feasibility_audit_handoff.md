# 17 — Cross-Site Feasibility Audit: Windows-Local Execution Handoff

> **Status: IMPLEMENTED + SYNTHETIC-TESTED — NO REAL-SOURCE RESULT RECORDED.**
> This document is an execution handoff, not a research finding. It creates no
> decision, approval, comparison, model, metric, or clinical claim. Gate PT P-3
> remains **CLOSED**; D-047 remains an `INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED`
> Cleveland-only proposal and is **not** extended here.

| Field | Value |
|---|---|
| Tool | `python -m research.audit.cross_site_feasibility` (new), `research/audit/cross_site_feasibility.py` |
| Tests | `tests/audit/test_cross_site_feasibility.py` (synthetic fixtures only) |
| Dataset used | `DA-A2` (UCI-45) processed 14-column cohorts: `processed.cleveland.data`, `processed.hungarian.data`, `processed.va.data` |
| Datasets not used | `DA-A1`, `DA-B1`, `DA-B2`, `processed.switzerland.data`, all raw files |
| Fixed scope | Reference `cleveland`; comparators `hungarian`, `va`; predeclared fields `age, sex, cp, trestbps, restecg` |
| Output | `data/reports/uci-45-cross-site-feasibility.json` and `.md` (Git-ignored, local only) |
| Prepared | 2026-10-23 |

## 1. Why this exists

The merged audit evidence already establishes per-file validation, class
distribution, missingness, stage-level joint availability, and 11/13-predictor
duplicate screening. What it does not yet provide is a single, predeclared,
aggregate-only record of **source compatibility** between the reference site and
the two candidate comparator sites on the five fields that the staged-intake
design treats as the initial feasible panel
(`age, sex, cp, trestbps, restecg`).

This tool produces that record without fitting, evaluating, pooling, translating
labels, altering originals, imputing values, or inferring identities. It adds
diagnostics; it does not add scientific conclusions.

## 2. Authorization scope determination (D-046)

**Determination: WITHIN `D-046` READ-ONLY AUDIT SCOPE.**

Basis:

1. D-046 approves local read-only suitability auditing of the named `DA-A2`
   files and forbids model fitting, feature selection, tuning, performance
   evaluation, calibration, SHAP/LIME, clinical claims, and external validation.
2. The requested diagnostics are aggregate compatibility, availability, and
   overlap counts computed from those same authorized files. No model, label
   translation, value modification, dataset creation, or performance estimate is
   produced.
3. Data custody is unchanged: inputs stay under Git-ignored `data/raw/`, outputs
   are locked to `data/reports/`, all nine `DA-A2` files are SHA-256 and
   byte-size verified and byte-guarded across the run, and raw Cleveland is never
   opened. Only `processed.*` cohorts are parsed.
4. No new dataset, file, license, or storage location is introduced, so no new
   acquisition authorization is required **for this audit**.

**Where authorization stops.** A Cleveland-vs-Hungary/VA model or outcome
comparison is **not** authorized:

- Gate PT P-3 is CLOSED; no supervisor-approved protocol exists.
- D-047 names a Cleveland-only internal exploratory experiment, excludes other
  UCI-45 sites, and prohibits pooling or external-validation claims.
- **H-01 is a cross-family question** (`>50%` in UCI-45 versus `>=50%` in
  UCI-412/411). Cleveland, Hungary, and VA are all UCI-45 sibling sites, so H-01
  is **not** a prerequisite for this audit and is not evaluated here. H-01 stays
  **OPEN for cross-family work**; no target equivalence is approved anywhere.
- What *is* outstanding within UCI-45 is a **source-specific outcome-coding and
  reference-standard review** — notably Hungary's raw `0-4` versus processed
  `0/1` recoding — which is blocker `B-01`.

Additional authorization that would be required, exactly: a **separate,
explicitly scoped governance decision naming the cohorts and permitting the
comparison**, on top of a **frozen Gate PT protocol with supervisor P-3
sign-off**. Neither is created, implied, or pre-filled by this document or by the
tool's output. If the maintainer wants those permissions, they must be requested
and recorded through the existing governance route.

## 3. Prerequisites (verify before running)

1. Clean, synced `main` that includes the merge of this PR.
2. The D-046 operational manifest exists locally at
   `data/manifests/gate_da_authorization.local.json` with `DA-A2` authorized and
   all sign-off fields populated.
3. `data/manifests/provenance_manifest.json` exists and still matches the
   on-disk originals (if any original changed, the audit fails closed — do not
   "fix" the manifest without re-recording provenance).
4. The audit virtual environment is active and `pip check` is clean.
5. `/data/` remains Git-ignored with zero tracked files (the tool re-verifies
   this itself).

## 4. Exact Windows PowerShell execution

From `E:\CardioAssist_AI_GitHub_Starter`:

```powershell
# 0. Clean state and dependency check
git status --short
git rev-parse HEAD
python -m pip check

# 1. Governance and ignore preflight
python -m research.audit check-auth
python -m research.audit verify-ignore

# 2. Confirm the tool's own synthetic tests pass in this environment
python -m pytest tests/audit/test_cross_site_feasibility.py -q

# 3. Run the authorized read-only feasibility audit
python -m research.audit.cross_site_feasibility `
  --auth-manifest data/manifests/gate_da_authorization.local.json `
  --provenance-manifest data/manifests/provenance_manifest.json `
  --json-out data/reports/uci-45-cross-site-feasibility.json `
  --markdown-out data/reports/uci-45-cross-site-feasibility.md

# 4. Confirm the repository is unchanged and nothing under /data/ is tracked
git status --short
git ls-files -- data
```

The command prints a short aggregate summary (status label, overall feasibility
status, cohorts with blocking findings, blocker/limitation counts, output paths)
and writes the two reports. It never prints row values.

**Abort if** governance, hash, byte-size, parser, schema, privacy-scanner, or
output-path validation fails. Do not retry with weakened checks; report the exact
error instead.

## 4.1 Status semantics after a run

| Field | Synthetic fixture run | Real authorized local run |
|---|---|---|
| `execution_status` | `SYNTHETIC_FIXTURE_EXECUTION_COMPLETED_TEST_ONLY` | `LOCAL_READ_ONLY_EXECUTION_COMPLETED` |
| `new_evidence_generated` | `SYNTHETIC_TEST_FIXTURES_ONLY` | `LOCAL_AGGREGATE_EVIDENCE_GENERATED` |
| `evidence_review_status` | `SYNTHETIC_TEST_ONLY_NOT_EVIDENCE` | `PENDING_HUMAN_PRIVACY_AND_SCIENTIFIC_REVIEW` |

A successful real run is reported as **execution completed locally**, with the
resulting aggregate evidence explicitly **pending human privacy and scientific
review**. Do not describe a completed local execution as still pending, and do
not describe synthetic fixtures as evidence.

## 5. Sharing rules

- Keep both report files local and Git-ignored. Do **not** commit them.
- Human privacy review is required **before** pasting any section into GitHub,
  a PR, or a chat. Even though the report is schema-validated aggregate output,
  the schema check is not a formal proof against arbitrary free-text encodings.
- Safe to share after review: the JSON/Markdown report and the printed summary.
- Never share: raw/processed dataset files, provenance or authorization
  manifests, license snapshots, row-level values, hashes of individual records,
  or any reconstructed profile.
- Label any quoted number with `REAL_LOCAL_AGGREGATE_READ_ONLY_AUDIT_NOT_MODEL_OR_CLINICAL_EVIDENCE`
  and state that it is maintainer-executed, not re-run by CI.

## 6. How to read the result (and what not to claim)

| Report element | Legitimate reading | Forbidden reading |
|---|---|---|
| `original_target_label_counts` | What codes the delivered file actually contains | Evidence that the labels mean the same thing clinically across sites |
| `compatibility_status` (`..._REQUIRES_REVIEW`) | A documented codebook difference needing human review | A recoded or harmonized target |
| `semantic_equivalence_status` | `UNVERIFIED_PENDING_UCI45_SOURCE_OUTCOME_CODING_REVIEW` | Any cross-site target equivalence |
| Class-conditional availability counts | Records with the field observed in each original-label stratum | Effective sample size, model eligibility, or usable cohort size |
| Value bands / `unit_verdict` | A heuristic plausibility check | Proof that units or assays are identical |
| `minimum_multiplicity_intersection_count` / `collision_rows_*` / `candidate_record_pairs` | Three distinct coarse collision quantities with multiplicity preserved | Patient identity, a duplication rate, or proven independence |
| Zero exact matches | Consistent with independent cohorts | Proof of independence |
| `overall_status` | The audit completed and downstream comparison remains blocked | A feasibility approval or a go/no-go decision |

## 6.1 Exact-profile overlap formula (read this before quoting any overlap number)

For every canonical profile `p` present in both cohorts, with multiplicity
`count_A(p)` in the reference (Cleveland) and `count_B(p)` in the comparator:

| Quantity | Formula | Meaning |
|---|---|---|
| Multiset intersection | `sum over p of min(count_A(p), count_B(p))` | Records that can be paired one-to-one per profile |
| Collision rows, A side | `sum over p of count_A(p)` | Every reference record whose profile also occurs in the comparator |
| Collision rows, B side | `sum over p of count_B(p)` | Every comparator record whose profile also occurs in the reference |
| Candidate record pairs | `sum over p of count_A(p) * count_B(p)` | Cross-side record pairs whose profiles collide |

Worked asymmetric example (also a unit test): multiplicity `A=2`, `B=3` gives
**intersection 2, side counts 2 and 3, candidate pairs 6**. Side counts are not
intersections and may each exceed the intersection. **None of these four numbers
counts duplicate, identical, or matched patients**, and none is evidence of
patient identity.

## 7. Blockers versus acknowledged limitations

Only four items genuinely gate a downstream comparison and are counted as
blockers (`blocks_downstream_comparison: true`):

| Blocker | Why the comparison remains blocked |
|---|---|
| `B-01-UCI45-OUTCOME-CODING-REVIEW` | Source-specific UCI-45 outcome-coding and reference-standard review outstanding (incl. Hungary raw `0-4` vs processed `0/1`). Not the cross-family H-01 question. |
| `B-02-GATE-PT-CLOSED` | No supervisor-approved protocol (P-3) |
| `B-03-D047-SCOPE-AUTHORIZATION` | D-047 is Cleveland-only; no comparison-specific authorization |
| `B-04-SOURCE-PAIR-OVERLAP-INDEPENDENCE` | Development-vs-assessment source-pair overlap evidence incomplete (Issues #20/#21) and patient independence cannot be established from identifier-free data |

The following are recorded as **contextual limitations, explicitly not
unresolved blockers** (`blocks_downstream_comparison: false`, each with a
`why_not_a_prerequisite` field in the report):

| ID | Why it is not a prerequisite for this audit |
|---|---|
| `C-01-RAW-CLEVELAND-QUARANTINE` | This audit is deliberately processed-14-column only; parsing raw Cleveland is neither required nor authorized for these counts. |
| `C-02-STATLOG-OVERLAP-CONDITIONAL` | UCI-145 Statlog is outside this scope; the Cleveland/Statlog overlap check becomes mandatory only if Statlog is considered as a source. |
| `C-03-D046-SCOPE-SUFFICIENCY` | D-046 scope is sufficient for this descriptive audit and insufficient for model fitting or evaluation; that boundary is an authorization fact, not an outstanding defect. |
| `C-04-UNIT-IDENTITY-HEURISTIC` | Unit diagnostics are descriptive and non-probative; the substantive measurement/reference-standard review is already required by `B-01`. |

## 8. What the maintainer reviews after the run

1. That the executed commit and manifest are the intended authorized ones.
2. That only the three declared processed files are listed as parsed.
3. That the report's `overall_status`, blockers, and warnings are consistent with
   the existing Gate DA/PT records (no auto-promotion of status).
4. Whether any cohort-level finding needs a new maintainer/scientific question
   rather than a code change. Do not edit the tool to change observed counts.
