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
- H-01 (`>50%` versus `>=50%`, exact-50% boundary) remains unresolved, so a
  cross-site target definition cannot be frozen.

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
| Class-conditional availability counts | Records with the field observed in each original-label stratum | Effective sample size, model eligibility, or usable cohort size |
| Value bands / `unit_verdict` | A heuristic plausibility check | Proof that units or assays are identical |
| `distinct_matching_profiles` / `record_pairs...` | Coarse exact-profile collisions with duplicate multiplicity | Patient identity, duplication rate, or proven independence |
| Zero exact matches | Consistent with independent cohorts | Proof of independence |
| `overall_status` | The audit completed and downstream comparison remains blocked | A feasibility approval or a go/no-go decision |

## 7. Blockers recorded by the report

| Blocker | Why the comparison remains blocked |
|---|---|
| `B-01-TARGET-BOUNDARY` | H-01 threshold/boundary reconciliation still open |
| `B-02-GATE-PT-CLOSED` | No supervisor-approved protocol (P-3) |
| `B-03-D047-SCOPE` | D-047 is Cleveland-only; no other-site or pooling permission |
| `B-04-RAW-CLEVELAND-QUARANTINE` | Raw Cleveland unparsed; reference raw/processed relation not re-verified |
| `B-05-REPRESENTATION-ALIGNMENT` | Raw/processed alignment discordance unresolved (Issues #20/#21) |
| `B-06-INDEPENDENCE-NOT-PROVABLE` | Identifier-free data cannot prove independence; L-05 risk open |
| `B-07-UNIT-IDENTITY` | Unit identity not verifiable from file content |
| `B-08-D046-READ-ONLY-SCOPE` | D-046 permits this audit only, not any comparison |

## 8. What the maintainer reviews after the run

1. That the executed commit and manifest are the intended authorized ones.
2. That only the three declared processed files are listed as parsed.
3. That the report's `overall_status`, blockers, and warnings are consistent with
   the existing Gate DA/PT records (no auto-promotion of status).
4. Whether any cohort-level finding needs a new maintainer/scientific question
   rather than a code change. Do not edit the tool to change observed counts.
