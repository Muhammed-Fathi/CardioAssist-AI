# M2a Read-Only Local Dataset Audit Toolchain (`research/audit/`)

**Status:** Toolchain **IMPLEMENTED + TESTED locally on synthetic fixtures**
(milestone **M2a**). Proposed governance decision **D-046** and dataset access
decisions (`DA-A1`, `DA-A2`, `DA-B1`, `DA-B2`) in
`research/audit/gate_da_authorization.json` are **PENDING HUMAN ACCEPTANCE**.
**No real dataset has been downloaded, and no model fitting, feature selection,
hyperparameter tuning, calibration, SHAP/LIME computation, or performance
evaluation is authorized or implemented.**

For the complete step-by-step Windows PowerShell execution guide from
`E:\CardioAssist_AI_GitHub_Starter`, see
[`docs/research/gate-da/09_m2a_windows_local_audit_handoff.md`](../../docs/research/gate-da/09_m2a_windows_local_audit_handoff.md).

---

## 1. Purpose and Non-Negotiable Safety Rules

This package provides a Python 3.11/3.12-compatible, $0, Windows-local,
read-only dataset audit workflow that executes on the maintainer's local
Windows machine **only after** human maintainer approval of **D-046** (Gate DA).

1. **Isolated $0 dependencies**: `research/audit/requirements.txt` pins only
   free open-source packages (`openpyxl==3.1.5`, `et-xmlfile==2.0.0`,
   `pytest==9.0.3` and its transitive closure), isolated from
   `backend/requirements.txt`. The `.xlsx` reader also includes a fail-closed
   Python standard-library OOXML parser (`zipfile` + `xml.etree.ElementTree`)
   so tests run in both the isolated `.venv-audit` environment and the backend
   `.venv`.
2. **Git-ignored `/data/` root only**: All raw datasets and provenance
   manifests live under `<repo_root>/data/` (`data/raw/uci-412`,
   `data/raw/uci-45`, `data/raw/uci-411`, `data/raw/uci-145`,
   `data/manifests/`). Every command runs `git check-ignore -v` and
   `git ls-files -- data/` before touching any data path and fails closed if
   any path is not ignored or is tracked by Git.
3. **Byte-identical originals**: `ByteIdentityGuard` computes and verifies
   SHA-256 and exact byte size before and after reading every dataset file.
   No dataset file is ever modified, overwritten, or rewritten in place.
4. **Zero patient-level row output**: The toolchain never commits, uploads,
   logs, or prints patient-level rows. `verify_report_no_patient_rows` scans
   all generated JSON and Markdown reports for forbidden keys, raw 14-column
   lines, and row fingerprints before writing to disk.
5. **Fail-closed validation**: Missing files, unexpected archive entries,
   path traversal, unapproved files (`new.data`, `reprocessed.hungarian.data`,
   `processed.long-beach-va.data`), unknown file formats, wrong delimiters or
   column counts, raw-versus-processed file confusion, unrecognized columns,
   corrupt files, non-UCI/mirror/Kaggle source URLs, missing license snapshots,
   or SHA-256 mismatches immediately abort with a structured `AuditError`
   (exit code `2`).

---

## 2. Implemented Audit Functions (1–12)

| # | Audit Function | Module / Function |
|---|---|---|
| 1 | Validate UCI-412 workbook sheets, `Cath` labels (`CAD`/`Normal`), columns, data types, and reconcile 54 vs 55 vs 56 feature-count discrepancies | `validators.py::audit_uci_412_or_411_workbook` |
| 2 | Validate UCI-45 raw 76-attribute and processed 14-column files separately across all four cohorts (Cleveland, Hungary, Switzerland, VA Long Beach) + `heart-disease.names` | `validators.py::audit_uci_45_processed_file`, `audit_uci_45_raw_file`, `audit_uci_45_names_file` |
| 3 | Confirm `processed.cleveland.data` conventional 14-column benchmark schema and raw/processed file roles; detect raw-vs-processed confusion (`RawVsProcessedConfusionError`) and verify raw↔processed row correspondence | `validators.py::compare_uci_45_raw_and_processed`, `registry.py::UCI_45_FILE_ROLES` |
| 4 | Tabulate row counts, class distributions (raw + provisional T1 binary), missingness (`?`, `-9.0`, blank), invalid codings, and suspicious values (e.g. `chol=0`, `oldpeak<0`) while preserving `0` as data | `validators.py` |
| 5 | Check exact full-row, exact predictor-row, exact 13/11-feature shared-profile, and tolerance-based near-duplicates within and across authorized cohorts | `duplicates.py::compute_within_dataset_duplicates`, `compute_cross_cohort_duplicates` |
| 6 | Distinguish observed duplicate counts from suspected patient overlap and enforce `proven_independence_claim_permitted = False` on identifier-free data | `duplicates.py::compute_cross_cohort_duplicates` |
| 7 | Confirm UCI-411/412 same-cohort provenance (`L-04`, never an independent cohort) and evaluate 1-to-1 positional/unordered row correspondence and `LAD/LCX/RCA -> Cath` consistency when both `DA-A1` and `DA-B1` are authorized | `duplicates.py::evaluate_uci_411_412_correspondence` |
| 8 | Investigate UCI-145 Statlog vs Cleveland overlap (`L-05`) **only** if `DA-B2` access is approved; enforce that `DA-B1` and `DA-B2` never become training or external-validation datasets by audit grant | `duplicates.py::investigate_statlog_cleveland_overlap`, `validators.py::audit_uci_145_statlog_file` |
| 9 | Maintain the Feature Availability & Leakage Review Table covering `ca` (`L-01`), raw per-vessel angiography fields (`L-02`), `LAD`/`LCX`/`RCA`/`Cath` (`L-03`), `thal` (`L-06`), exercise-test variables (`L-07`), and UCI-412 echo/lab/clinical features (`L-08`) | `registry.py::FEATURE_AVAILABILITY_AND_LEAKAGE_TABLE` |
| 10 | Document UCI-45 (`>50%`) vs UCI-412 (`>=50%`) threshold wording (`H-01`) and the unresolved 50% boundary status (`UNVERIFIED` / `REQUIRES APPROVAL`) without inventing reconciliation evidence | `registry.py::TARGET_HARMONIZATION_SPEC` |
| 11 | Generate metadata-only JSON and Markdown audit reports distinguishing `VERIFIED`, `SOURCE-REPORTED`, `UNVERIFIED`, and `REQUIRES APPROVAL` | `reporting.py::build_and_verify_reports`, `render_markdown_report` |
| 12 | Keep patient-level inputs, cleaned copies, and intermediate derivatives out of GitHub and remote AI services via `git check-ignore`, `/data/` containment, read-only execution, and report redaction guards | `git_safety.py`, `provenance.py`, `reporting.py::verify_report_no_patient_rows` |

---

## 3. CLI Subcommands

Run from the repository root (`E:\CardioAssist_AI_GitHub_Starter` on Windows):

```powershell
# 1. Check Gate DA governance & dataset authorization status
python -m research.audit check-auth

# 2. Verify git check-ignore and zero tracked files under /data/
python -m research.audit verify-ignore

# 3. Run dry-run preflight validation (no data downloaded or read)
python -m research.audit dry-run --json-out data/reports/preflight_report.json --markdown-out data/reports/preflight_report.md

# 4. Run synthetic fixture self-test in an isolated temporary directory
python -m research.audit self-test

# 5. Inspect a downloaded official UCI .zip archive in read-only mode before extraction
python -m research.audit inspect-archive --dataset-id DA-A1 --zip-path data/downloads/z+alizadeh+sani.zip

# 6. Record SHA-256 hashes, byte sizes, and license snapshots after authorized human download
python -m research.audit record-provenance --datasets DA-A1 DA-A2 DA-B1 DA-B2 --acquirer "<Maintainer Name>" --audit-reviewer "<Reviewer Name>"

# 7. Execute the read-only local dataset audit after human authorization
python -m research.audit run-audit --json-out data/reports/m2_audit_report.json --markdown-out data/reports/m2_audit_report.md
```
