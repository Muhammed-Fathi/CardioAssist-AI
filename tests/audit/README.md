# M2a Dataset Audit Toolchain Tests (`tests/audit/`)

All tests in this folder exercise the read-only local dataset audit toolchain
(`research/audit/`) against small, deterministic **synthetic software test
fixtures** materialized in pytest temporary directories (`tmp_path`).

- **No real dataset** is downloaded, stored, or required.
- **No model** is fitted, selected, tuned, calibrated, explained, or evaluated.
- **Synthetic fixture metrics** are solely software test results — never
  medical, benchmark, or model-performance evidence.
- Existing mock `/v1` API fixtures (`shared/contracts/fixtures/`) and backend
  runtime behavior (`backend/app/`) are untouched.

## Coverage

| File | Scope |
|---|---|
| `test_audit_governance_and_ignore.py` | D-046 authorization manifest defaults (`PENDING_HUMAN_ACCEPTANCE`), unapproved-source rejection (Kaggle/mirrors/HTTP), role restrictions (`DA-B1`/`DA-B2` audit-only, never training/external validation), `git check-ignore` protection on `/data/`, archive path-traversal and excluded-file (`new.data`, `reprocessed.hungarian.data`) rejection, SHA-256/size/license-snapshot mismatch, and pre/post-read byte-identity verification. |
| `test_audit_parsers_and_validators.py` | Correct parsing of UCI-412 (54 and 55 predictor layouts), UCI-45 processed 14-column files (all 4 cohorts), UCI-45 raw 76-attribute multi-line files + `heart-disease.names`, UCI-411, and UCI-145 Statlog; missing values (`?`, `-9.0`, null) vs `0` semantics; wrong delimiter or column count; raw-versus-processed confusion; unexpected categories or target mappings; and leakage-column detection (`ca`, per-vessel fields, `LAD`/`LCX`/`RCA`/`Cath`, `thal`, exercise-test block, UCI-412 echo/lab features). |
| `test_audit_duplicates_and_correspondence.py` | Within-cohort and cross-cohort exact and near-duplicate detection; distinction between observed duplicates and suspected overlap; prohibition on claiming proven patient independence from identifier-free data; UCI-411/412 same-cohort provenance and 1-to-1 row correspondence; and DA-B2-gated UCI-145/Cleveland overlap investigation. |
| `test_audit_reporting_and_cli.py` | Metadata-only JSON and Markdown report generation; `VERIFIED`, `SOURCE-REPORTED`, `UNVERIFIED`, and `REQUIRES APPROVAL` evidence tags; H-01 `>50%` vs `>=50%` threshold wording and unresolved 50% boundary reporting; zero patient-level content redaction enforcement; and CLI subcommands (`check-auth`, `verify-ignore`, `dry-run`, `self-test`, `inspect-archive`, `record-provenance`, `run-audit`). |
