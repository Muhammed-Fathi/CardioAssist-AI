# M2a Read-Only Local Dataset Audit Toolchain (`research/audit/`)

**Status update (2026-10-22):** D-046 is now **human-ratified for
local read-only audits only** (see `docs/DECISIONS.md`); the checked-in
`gate_da_authorization.json` is deliberately **pending / fail-closed**.
The maintainer used an **untracked local authorization manifest** to audit
DA-A1/UCI-412 and DA-B1/UCI-411; aggregate-only results and unresolved
scientific flags are documented in
[`docs/research/gate-da/10_m2a_uci412_uci411_evidence_and_decisions.md`](../../docs/research/gate-da/10_m2a_uci412_uci411_evidence_and_decisions.md).
Raw datasets and local JSON/Markdown reports **must remain Git-ignored and
must never be committed**. **No model fitting, feature selection,
hyperparameter tuning, calibration, SHAP/LIME computation, or performance
evaluation is authorized. Gate PT remains CLOSED.**

For the complete step-by-step Windows PowerShell execution guide from
`E:\CardioAssist_AI_GitHub_Starter`, see
[`docs/research/gate-da/09_m2a_windows_local_audit_handoff.md`](../../docs/research/gate-da/09_m2a_windows_local_audit_handoff.md).

---

## DA-A2 Raw Cleveland integrity stop and explicit audit isolation (2026-10-22)

The user's real official UCI-45 archive `cleveland.data` raised a strict UTF-8
error at byte offset 58079 during the fully gated `run-audit` (no input mutation,
no reports created). The **original UCI WARNING** confirms a historical
source-side raw Cleveland data-integrity concern. The UTF-8 error alone is
not proof that a particular patient record is invalid; do not guess an encoding
or use replacement/ignore decoding to make the file appear valid. See
[Issue #18](https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/18).

Default `run-audit` **remains fail-closed** on raw Cleveland. After the human
maintainer has reviewed the warning, an explicit limited **read-only partial
DA-A2 audit** may be run with:

```powershell
& $python -m research.audit run-audit --datasets DA-A2 \`
  --quarantine-raw-cleveland \`
  --auth-manifest data/manifests/gate_da_authorization.local.json \`
  --provenance-manifest data/manifests/provenance_manifest.json \`
  --json-out data/reports/uci-45-da-a2-quarantined-audit.json \`
  --markdown-out data/reports/uci-45-da-a2-quarantined-audit.md
```

This mode verifies the raw file's provenance hash and unchanged bytes but
**does not open/parse raw Cleveland or calculate its raw/processed matching
counts**. It audits the four processed cohorts and the three other raw cohorts
as usual, with an explicit metadata-only `quarantined_raw_files` entry and
DA-A2 evidence status `REQUIRES APPROVAL`. The switch is rejected unless
`--datasets DA-A2` is explicitly specified. No patient data or full local
reports should be committed or pasted into GitHub. It does **not** lift Gate
PT; it neither repairs nor reinterprets Cleveland or establishes external
validation. If any other data parsing error occurs, the audit still fails
closed; do not weaken further parsers without separate evidence and review.

---

## DA-A2 raw/processed alignment: aggregate-only diagnostics

Following the 2026-10-22 partial audit, positional 13-feature matches were
Hungary **1/294**, Switzerland **1/123**, and VA Long Beach **192/200**.
Those numbers alone **cannot determine** whether rows are permuted,
recoded, mismatched or from different populations. The approved read-only
audit reports both positional and order-independent multiset overlaps for
13 predictors, exact 14-column target, and binary-target alternative, plus
per-feature positional and order-independent value-overlap counts.
Multiset intersections use minimum multiplicities to avoid double-counting
duplicates; they are metadata-only and **do not create patient mappings**.

A higher unordered match count is evidence *consistent with* order changes,
**not proof of common patient identity**, complete provenance or clinical
validity. Equal column-value distributions are weaker than whole-row matches.
The original raw Cleveland quarantine remains unchanged. Gate PT CLOSED;
no patient-level keys/values, reconstructed rows, model fitting or training.

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
2. **Git-ignored `/data/` root, input containment, and locked output paths**:
   All raw datasets, provenance manifests, and generated reports live under
   `<repo_root>/data/`. Every command runs `git check-ignore -v` and
   `git ls-files -- data/` before touching any data path.
   - `validate_provenance_manifest()` enforces that each dataset file resolves
     directly inside its exact approved `data/raw/uci-<id>/` directory and each
     license snapshot resolves directly inside `data/manifests/licenses/`.
   - `validate_and_resolve_report_output_path()` restricts JSON and Markdown
     report outputs strictly to `data/reports/<filename>`, and
     `validate_and_resolve_provenance_output_path()` restricts provenance
     manifest output strictly to `data/manifests/provenance_manifest.json`.
   - Any absolute/external path, `..` traversal, symlink target, `data/raw/`
     target, tracked repository file, or filename colliding with a dataset
     original is rejected before any file is opened for writing.
3. **Global + dataset-level Gate DA authorization**:
   `verify_dataset_authorized_for_audit()` requires both the global
   `workflow_status` to be explicitly set to
   `AUTHORIZED_FOR_LOCAL_READ_ONLY_AUDIT` and the individual dataset's
   `authorization_status` to be `AUTHORIZED_FOR_READ_ONLY_AUDIT` with all human
   sign-off fields populated before any real audit, archive extraction, or
   provenance recording can run.
4. **Byte-identical originals across parsing, report generation, and writing**:
   `ByteIdentityGuard` remains active across dataset parsing, report assembly,
   privacy validation, and report writing, verifying SHA-256 and exact byte
   size on both success and failure paths while preserving the original
   exception and surfacing any file mutation.
5. **Honest provenance timestamp and origin semantics**:
   `build_provenance_manifest()` separates `downloaded_at_utc` (human-attested
   acquisition timestamp or `UNKNOWN_PENDING_HUMAN_VERIFICATION` by default)
   from `manifest_recorded_at_utc` (automatically generated when the manifest is
   recorded), and distinguishes `local_file_integrity_status:
   "VERIFIED_LOCAL_SHA256_AND_BYTE_SIZE"` from
   `official_source_provenance_status:
   "HUMAN_ATTESTED_NOT_INDEPENDENTLY_PROVEN_BY_LOCAL_HASH"`.
6. **Report privacy controls and limitations**:
   `validate_strict_metadata_report_schema()` enforces an explicit allowlisted
   schema of metadata and integer/float aggregates as the primary control
   (rejecting unexpected top-level or nested keys and non-aggregate values),
   and `verify_report_no_patient_rows()` acts as a secondary defense-in-depth
   scanner for forbidden keys, 14-column rows, 76-attribute raw record
   fragments, multi-column patient rows, and in-memory row fingerprints.
   Because heuristic scanners are not a formal proof against arbitrary free-text
   encodings, human maintainer inspection of any generated report remains
   required before PR sharing.
7. **Fail-closed archive inspection and controlled selective extraction**:
   `inspect_zip_archive()` and `extract_authorized_archive()` enforce Gate DA
   authorization, member path safety, no symlinks, no duplicate/case-colliding
   basenames, and member/total size limits. When `inspect_zip_archive()` stops
   with `STOP_REQUIRES_REVIEW` on known excluded historical files (`new.data`,
   `reprocessed.hungarian.data` in `DA-A2`), auto-extraction is blocked;
   `extract_authorized_archive()` requires an explicit human-reviewed approval
   manifest (`data/manifests/archive_reviews/uci-<id>-archive-review.json`)
   matching the exact archive SHA-256, byte size, and full inventory before
   extracting only the authorized files.
   - **DA-A2 historical archive inventory (2026-10-22):** 23 members: 9 authorized inputs, 2 previously excluded, 3 metadata, 2 auxiliary, 7 `costs/` entries. `UCI_45_REVIEW_ONLY_HISTORICAL_MEMBERS` recognizes the nine additional historical paths by **exact name only**; all remain excluded and review-gated. `costs/Index` is not root `Index`. The review manifest must bind full inventory, SHA-256 and exclusions. See [V2 evidence and decision log](../../docs/research/gate-da/10_m2a_uci412_uci411_evidence_and_decisions.md).

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
| 12 | Keep patient-level inputs, cleaned copies, and intermediate derivatives out of GitHub and remote AI services via `git check-ignore`, `/data/` containment, locked output paths, read-only execution, strict metadata report schema validation, and secondary redaction guards | `git_safety.py`, `provenance.py`, `reporting.py::validate_strict_metadata_report_schema`, `reporting.py::verify_report_no_patient_rows` |

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
python -m research.audit inspect-archive --dataset-id DA-A1 --zip-path E:\UCI_Downloads\z+alizadeh+sani.zip

# 6. Safely extract ONLY authorized dataset files from an inspected official UCI .zip archive
python -m research.audit extract-authorized-archive --dataset-id DA-A1 --zip-path E:\UCI_Downloads\z+alizadeh+sani.zip

# 7. Record SHA-256 hashes, byte sizes, and license snapshots after authorized human download
python -m research.audit record-provenance --datasets DA-A1 DA-A2 DA-B1 DA-B2 --acquirer "<Maintainer Name>" --audit-reviewer "<Reviewer Name>"

# 8. Execute the read-only local dataset audit after human authorization
python -m research.audit run-audit --json-out data/reports/m2_audit_report.json --markdown-out data/reports/m2_audit_report.md
```
