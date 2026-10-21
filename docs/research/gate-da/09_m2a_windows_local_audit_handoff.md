# 09 — M2a Windows Local Audit Handoff (`E:\CardioAssist_AI_GitHub_Starter`)

- **Document Status**: `READY FOR MAINTAINER EXECUTION AFTER D-046 HUMAN ACCEPTANCE`
- **Milestone**: `M2a — Maintainer-Led Gate DA and Local Dataset Audit Readiness`
- **Target Workstation Path**: `E:\CardioAssist_AI_GitHub_Starter` (Windows 10/11 PowerShell, Python 3.12)
- **Target PR Branch**: `arena/a1f1816a-cardioassist-ai` (PR #11)
- **Related Governance Proposal**: `D-046` (`PROPOSED — PENDING HUMAN ACCEPTANCE`)

---

## 1. Purpose and Hard Safety Rules

This runbook provides exact, copy-pasteable Windows PowerShell commands for the human maintainer (`Muhammed Fathi`) to:
1. Install and verify the proposed GitHub Actions audit workflow (`.github/workflows/audit-ci.yml`) on the PR #11 branch (`arena/a1f1816a-cardioassist-ai`) before merging.
2. Verify repository and `.gitignore` readiness in dry-run mode.
3. Explicitly record human Gate DA acceptance in `research/audit/gate_da_authorization.json` (`workflow_status` + dataset `authorization_status`) after reviewing `D-046`.
4. Acquire the authorized official UCI files into git-ignored `/data/raw/uci-<id>/` directories (preferring direct individual-file acquisition from official UCI landing pages where available, or using the hardened `inspect-archive` + `extract-authorized-archive` toolchain with explicit human archive-inventory review).
5. Record SHA-256 hashes, byte sizes, and CC BY 4.0 license snapshots into `data/manifests/provenance_manifest.json`.
6. Execute the read-only local dataset audit (`python -m research.audit run-audit`), generating metadata-only JSON and Markdown reports strictly inside `data/reports/`.
7. Verify before sharing that `git status` shows zero tracked or staged files under `/data/` and that the generated report contains zero patient-level rows.

### Non-Negotiable Custody & Output Protection Rules
- **Never commit or push any file under `/data/raw/`, `/data/manifests/`, `/data/interim/`, `/data/processed/`, or `/data/external/`.**
- **Locked Output Locations (Blocker 1 Protection)**:
  - Report outputs (`--json-out`, `--markdown-out`) are strictly confined to `data/reports/<filename>.json` and `data/reports/<filename>.md`.
  - Provenance manifest output (`--output`) is strictly confined to `data/manifests/provenance_manifest.json`.
  - Any attempt to pass an absolute path, `..` traversal, symlink target, `data/raw/` path, or a filename colliding with a dataset original is rejected before any file is opened for writing.
- **Originals Byte-Identity**: `ByteIdentityGuard` verifies pre-audit and post-audit SHA-256 digests and byte sizes across the entire audit and report-writing lifecycle, including failure paths.
- **No model fitting, feature selection, hyperparameter tuning, performance evaluation, calibration, or SHAP/LIME is performed in M2a.**

---

## 2. Step 0 — Install Audit CI Workflow on PR #11 Branch Before Merge (Optional Before Local Audit, Required Before PR Merge)

> **Why this must run on `arena/a1f1816a-cardioassist-ai`**: `research/audit/ci/audit-ci.yml.example` was introduced on the PR #11 branch (`arena/a1f1816a-cardioassist-ai`) and does not exist on `main` until PR #11 is merged. GitHub Actions has **not** validated `tests/audit` until this workflow is pushed by a maintainer with `workflows` permission and the Actions run completes.

```powershell
Set-Location "E:\CardioAssist_AI_GitHub_Starter"

# 1. Fetch and check out the exact PR #11 branch (NOT stale main)
git fetch origin arena/a1f1816a-cardioassist-ai
git checkout arena/a1f1816a-cardioassist-ai
git pull --ff-only origin arena/a1f1816a-cardioassist-ai

# 2. Verify local HEAD matches remote PR branch HEAD with no divergence
$localHead = (git rev-parse HEAD).Trim()
$remoteHead = (git rev-parse origin/arena/a1f1816a-cardioassist-ai).Trim()
if ($localHead -ne $remoteHead) {
    throw "STOP: Local HEAD ($localHead) diverged from origin/arena/a1f1816a-cardioassist-ai ($remoteHead)."
}

# 3. Ensure we do not overwrite an existing workflow file unintentionally
if (Test-Path ".github\workflows\audit-ci.yml") {
    throw "STOP: .github\workflows\audit-ci.yml already exists. Inspect it before overwriting."
}

# 4. Copy the proposed workflow template and push to PR #11 branch
Copy-Item "research\audit\ci\audit-ci.yml.example" ".github\workflows\audit-ci.yml" -ErrorAction Stop
git add .github/workflows/audit-ci.yml
git commit -m "ci(audit): enable GitHub Actions workflow for M2a read-only audit tests"
git push origin arena/a1f1816a-cardioassist-ai
```

Wait for the **`audit-toolchain-validation`** workflow (jobs `Dataset audit toolchain (Python 3.11)` and `Dataset audit toolchain (Python 3.12)`) on PR #11 to finish and confirm it is green before merging PR #11.

---

## 3. Step 1 — Workstation Preflight and Synthetic Self-Test

Open **Windows PowerShell** on your workstation:

```powershell
# 1. Navigate to your local clone on the E: drive
Set-Location "E:\CardioAssist_AI_GitHub_Starter"

# 2. Activate your Python 3.12 virtual environment
.\.venv\Scripts\Activate.ps1
python --version

# 3. Verify original literature source PDFs and CSV hashes (must pass 4/4)
python scripts/verify_sources.py

# 4. Verify git check-ignore rules protect /data/raw/ and /data/manifests/
python -m research.audit verify-ignore

# 5. Run dry-run preflight (reads zero datasets; confirms D-046 is currently PENDING_HUMAN_ACCEPTANCE)
python -m research.audit --dry-run

# 6. Run the synthetic fixture self-test in an isolated temp folder
python -m research.audit self-test

# 7. Run the full automated test suite (contract + backend + audit)
pytest tests/contract tests/backend tests/audit -q
```

---

## 4. Step 2 — Create Git-Ignored Local Directories Under `E:\CardioAssist_AI_GitHub_Starter\data`

```powershell
$RepoRoot = "E:\CardioAssist_AI_GitHub_Starter"
Set-Location $RepoRoot

New-Item -ItemType Directory -Force -Path `
    "$RepoRoot\data\raw\uci-412", `
    "$RepoRoot\data\raw\uci-45", `
    "$RepoRoot\data\raw\uci-411", `
    "$RepoRoot\data\raw\uci-145", `
    "$RepoRoot\data\manifests\licenses", `
    "$RepoRoot\data\manifests\archive_reviews", `
    "$RepoRoot\data\reports" | Out-Null

# Confirm git check-ignore blocks every created path
git check-ignore -v `
    data/raw/uci-412/test.xlsx `
    data/raw/uci-45/processed.cleveland.data `
    data/raw/uci-411/test.xlsx `
    data/raw/uci-145/heart.dat `
    data/manifests/provenance_manifest.json `
    data/manifests/archive_reviews/uci-45-archive-review.json `
    data/reports/m2a_local_audit_report.json
```

---

## 5. Step 3 — Record Explicit Human Gate DA Acceptance (`D-046`)

After reviewing `docs/DECISIONS.md` (`D-046`) and `docs/research/gate-da/08_gate_da_decision_package.md`:
- Open `research/audit/gate_da_authorization.json` in your editor.
- Set the top-level `"workflow_status"` from `"PENDING_HUMAN_ACCEPTANCE"` to `"AUTHORIZED_FOR_READ_ONLY_AUDIT"`.
- Both the top-level `"workflow_status"` **and** each authorized dataset's `"authorization_status"` must be `"AUTHORIZED_FOR_READ_ONLY_AUDIT"` (the toolchain fails closed if either remains `"PENDING_HUMAN_ACCEPTANCE"`).
- For each dataset you are authorizing (`DA-A1`, `DA-A2`, and optionally `DA-B1`, `DA-B2`), update:
  - `"authorization_status": "AUTHORIZED_FOR_READ_ONLY_AUDIT"`
  - `"authorized_by": "Muhammed Fathi"`
  - `"authorized_date": "YYYY-MM-DD"` (actual date of human approval)
  - `"responsible_acquirer": "Muhammed Fathi"`
  - `"audit_reviewer": "Muhammed Fathi"`
  - `"environment": "E:\\CardioAssist_AI_GitHub_Starter (Windows 11 PowerShell, Python 3.12)"`
- **Do NOT** change `"supervisor_approval_claimed"` (must remain `false`) or `"model_fitting_authorized"` (must remain `false`).

Verify your authorization update:

```powershell
python -m research.audit check-auth
```

---

## 6. Step 4 — Acquire Official UCI Files and Save License Snapshots

Download **only** from the exact official UCI landing pages listed below (never from Kaggle, GitHub mirrors, or Zenodo):

| Dataset ID | Official UCI URL | DOI | Target Local Directory |
|---|---|---|---|
| `DA-A1` | `https://archive.ics.uci.edu/dataset/412/z+alizadeh+sani` | `10.24432/C5Q31T` | `data\raw\uci-412\` |
| `DA-A2` | `https://archive.ics.uci.edu/dataset/45/heart+disease` | `10.24432/C52P4X` | `data\raw\uci-45\` |
| `DA-B1` | `https://archive.ics.uci.edu/dataset/411/extention+of+z+alizadeh+sani` | `10.24432/C5461K` | `data\raw\uci-411\` |
| `DA-B2` | `https://archive.ics.uci.edu/dataset/145/statlog+heart` | `10.24432/C57303` | `data\raw\uci-145\` |

> **Canonical URL Note for `DA-B1` (UCI ID 411)**: `https://archive.ics.uci.edu/dataset/411/extention+of+z+alizadeh+sani` is the canonical `official_source_url` recorded in `research/audit/gate_da_authorization.json` and `docs/DECISIONS.md` (`D-046`). (UCI's web router also resolves the slug variant `https://archive.ics.uci.edu/dataset/411/extention+of+z+alizadeh+sani+dataset` to dataset ID `411`, while provenance validation enforces the exact canonical URL `https://archive.ics.uci.edu/dataset/411/extention+of+z+alizadeh+sani`.)

### Acquisition Procedure (Blocker 2 Controls: Direct Official Files vs Inspected ZIP Extraction)

#### Option A (Preferred Where Available on the Official UCI Page): Direct Individual-File Download
If the official UCI landing page allows downloading individual files directly:
- Save `Z-Alizadeh sani dataset.xlsx` directly into `E:\CardioAssist_AI_GitHub_Starter\data\raw\uci-412\`.
- Save the 9 authorized UCI-45 files (`processed.cleveland.data`, `processed.hungarian.data`, `processed.switzerland.data`, `processed.va.data`, `cleveland.data`, `hungarian.data`, `switzerland.data`, `long-beach-va.data`, `heart-disease.names`) directly into `E:\CardioAssist_AI_GitHub_Starter\data\raw\uci-45\`. Do **not** download `new.data`, `reprocessed.hungarian.data`, or any subdirectories.
- If `DA-B1` is authorized, save `extention of Z-Alizadeh sani dataset.xlsx` into `E:\CardioAssist_AI_GitHub_Starter\data\raw\uci-411\`.
- If `DA-B2` is authorized, save `heart.dat` into `E:\CardioAssist_AI_GitHub_Starter\data\raw\uci-145\`.

#### Option B (If the Official UCI Landing Page Provides a `.zip` Bundle): Mandatory Inspection + Controlled Extraction
Never use `Expand-Archive` or ad-hoc inline Python extraction scripts. Use the built-in `inspect-archive` and `extract-authorized-archive` subcommands, which enforce Gate DA authorization, member path safety, symlink/executable rejection, duplicate basename rejection, member/total size limits, and **existing-file overwrite protection** (rejecting extraction before modifying any destination file if any authorized file already exists in `data/raw/uci-<id>/`):

**1. For `DA-A1` (`z+alizadeh+sani.zip`), `DA-B1`, and `DA-B2`**:

```powershell
# 1a. Inspect the archive first in read-only mode (must return PASS_AUTHORIZED_CONTENTS)
python -m research.audit inspect-archive --dataset-id DA-A1 --zip-path "E:\UCI_Downloads\z+alizadeh+sani.zip"

# 1b. Only if inspect-archive returns PASS_AUTHORIZED_CONTENTS (exit code 0), extract the authorized file:
python -m research.audit extract-authorized-archive --dataset-id DA-A1 --zip-path "E:\UCI_Downloads\z+alizadeh+sani.zip"

# Repeat for DA-B1 and DA-B2 if authorized:
python -m research.audit inspect-archive --dataset-id DA-B1 --zip-path "E:\UCI_Downloads\extention+of+z+alizadeh+sani.zip"
python -m research.audit extract-authorized-archive --dataset-id DA-B1 --zip-path "E:\UCI_Downloads\extention+of+z+alizadeh+sani.zip"

python -m research.audit inspect-archive --dataset-id DA-B2 --zip-path "E:\UCI_Downloads\statlog+heart.zip"
python -m research.audit extract-authorized-archive --dataset-id DA-B2 --zip-path "E:\UCI_Downloads\statlog+heart.zip"
```

**2. For `DA-A2` (`heart+disease.zip`) — Handling `STOP_REQUIRES_REVIEW` Safely**:

The official UCI-45 `heart+disease.zip` bundle historically includes legacy files (`new.data`, `reprocessed.hungarian.data`, `bak`, etc.) alongside the 9 authorized files.
- **Step 2a**: Run `inspect-archive` to obtain the complete archive inventory and SHA-256 digest:

```powershell
python -m research.audit inspect-archive --dataset-id DA-A2 --zip-path "E:\UCI_Downloads\heart+disease.zip"
```

- **Step 2b**: If `inspect-archive` exits with `"outcome": "STOP_REQUIRES_REVIEW"`:
  1. **STOP and review the printed JSON output manually.** Never auto-extract after a `STOP_REQUIRES_REVIEW` result.
  2. Verify that `"unexpected_entries_detected"` is `[]` (if any unrecognized file is listed in `"unexpected_entries_detected"`, **abort immediately**—extraction is unconditionally prohibited).
  3. Record your explicit human review of the complete `archive_inventory`, `archive_sha256`, and `archive_size_bytes` in `data\manifests\archive_reviews\uci-45-archive-review.json` (substituting the exact values printed by `inspect-archive` and your actual UTC review timestamp):

```powershell
@"
{
  "governance_decision_id": "D-046",
  "dataset_id": "DA-A2",
  "review_outcome": "APPROVED_SELECTIVE_EXTRACTION_OF_AUTHORIZED_FILES_ONLY",
  "reviewed_by": "Muhammed Fathi",
  "reviewed_at_utc": "2026-10-21T11:15:00Z",
  "archive_filename": "heart+disease.zip",
  "archive_sha256": "<PASTE_EXACT_64_HEX_ARCHIVE_SHA256_FROM_INSPECT_ARCHIVE>",
  "archive_size_bytes": <PASTE_EXACT_INTEGER_SIZE_BYTES_FROM_INSPECT_ARCHIVE>,
  "reviewed_archive_inventory": <PASTE_EXACT_ARCHIVE_INVENTORY_JSON_ARRAY_FROM_INSPECT_ARCHIVE>,
  "excluded_historical_files_acknowledged_do_not_extract": <PASTE_EXACT_EXCLUDED_FILES_DETECTED_ARRAY_FROM_INSPECT_ARCHIVE>,
  "authorized_files_approved_for_extraction": [
    "cleveland.data",
    "heart-disease.names",
    "hungarian.data",
    "long-beach-va.data",
    "processed.cleveland.data",
    "processed.hungarian.data",
    "processed.switzerland.data",
    "processed.va.data",
    "switzerland.data"
  ]
}
"@ | Set-Content -Encoding UTF8 "data\manifests\archive_reviews\uci-45-archive-review.json"
```

- **Step 2c**: Run `extract-authorized-archive` passing `--review-approval`. The command verifies your review manifest against the live ZIP's SHA-256, byte size, and complete entry inventory before extracting **only** the 9 authorized files into `data\raw\uci-45\`:

```powershell
python -m research.audit extract-authorized-archive `
    --dataset-id DA-A2 `
    --zip-path "E:\UCI_Downloads\heart+disease.zip" `
    --review-approval "data/manifests/archive_reviews/uci-45-archive-review.json"
```

### Save Official CC BY 4.0 Landing-Page License Snapshots

For each acquired dataset, save the landing-page license attribution text (`Creative Commons Attribution 4.0 International (CC BY 4.0)`, DOI, and official URL) into `data\manifests\licenses\`:
- `data\manifests\licenses\uci-412-license-snapshot.txt`
- `data\manifests\licenses\uci-45-license-snapshot.txt`
- `data\manifests\licenses\uci-411-license-snapshot.txt`
- `data\manifests\licenses\uci-145-license-snapshot.txt`

---

## 7. Step 5 — Record SHA-256 Provenance Manifest

Run `record-provenance` to compute and record SHA-256 digests and exact byte sizes into `data/manifests/provenance_manifest.json` (git-ignored).
- Pass `--downloaded-at-utc` with the actual UTC timestamp when you downloaded the files (e.g., `"2026-10-21T11:00:00Z"`), or omit `--downloaded-at-utc` so it defaults to `"UNKNOWN_PENDING_HUMAN_VERIFICATION"`.
- The toolchain records `downloaded_at_utc` separately from `manifest_recorded_at_utc`, and marks `official_source_provenance_status` as `HUMAN_ATTESTED_NOT_INDEPENDENTLY_PROVEN_BY_LOCAL_HASH` while marking `local_file_integrity_status` as `VERIFIED_LOCAL_SHA256_AND_BYTE_SIZE`.

```powershell
python -m research.audit record-provenance `
    --datasets DA-A1 DA-A2 DA-B1 DA-B2 `
    --acquirer "Muhammed Fathi" `
    --audit-reviewer "Muhammed Fathi" `
    --downloaded-at-utc "2026-10-21T11:00:00Z" `
    --environment "E:\CardioAssist_AI_GitHub_Starter (Windows 11 PowerShell, Python 3.12)"
```

---

## 8. Step 6 — Execute Read-Only Local Dataset Audit

Run the read-only local dataset audit. Report outputs are restricted to `data/reports/`:

```powershell
python -m research.audit run-audit `
    --json-out "data/reports/m2a_local_audit_report.json" `
    --markdown-out "data/reports/m2a_local_audit_report.md"
```

### What `run-audit` Verifies Automatically
1. **Git-Ignore & Path Containment**: Verifies `/data/raw/` and `/data/manifests/` are git-ignored, rejects symlinks/traversal/external paths, and restricts report outputs strictly to `data/reports/`.
2. **Gate DA Authorization & Provenance**: Verifies both global `workflow_status` and each dataset's `authorization_status` are `AUTHORIZED_FOR_READ_ONLY_AUDIT`, and verifies pre-audit SHA-256 and byte sizes against `data/manifests/provenance_manifest.json`.
3. **Dataset Audits (`DA-A1`, `DA-A2`, `DA-B1`, `DA-B2`)**:
   - Reconciles UCI-412 (`56` columns = `54` predictors + `BBB` + `Cath`) and UCI-411 (`59` columns = `55` predictors + `LAD`/`LCX`/`RCA` + `Cath`).
   - Audits all 4 processed 14-column cohorts and all 4 raw 76-attribute cohorts in UCI-45, confirming `#76 name` is dummy `"name"` on every row and quantifying `-9` sentinel missingness across all 76 attributes (`P16`).
   - Screens within-dataset and cross-cohort exact/near-duplicates (`R-03`, `L-03`), evaluates UCI-411 ↔ UCI-412 row alignment (`L-04`), and quantifies UCI-145 Statlog ↔ Cleveland overlap (`L-05`).
4. **Byte-Identity Guard (`ByteIdentityGuard`)**: Remains active across dataset parsing, report assembly, privacy validation, and report writing, verifying on both success and failure paths that every file in `/data/raw/` has the exact same SHA-256 and byte size after execution.
5. **Report Privacy Controls & Limitations**:
   - **Primary Control**: `validate_strict_metadata_report_schema()` enforces an explicit allowlisted schema of metadata and integer/float aggregates, rejecting any unexpected top-level or nested fields.
   - **Secondary Control**: `verify_report_no_patient_rows()` scans serialized JSON and Markdown for 14-column rows, 76-attribute raw record fragments, multi-column patient rows, and in-memory patient row fingerprints.
   - **Limitation & Mandatory Human Check**: Automated schema and pattern checks do not replace human inspection against arbitrary free-text encodings; always review `data\reports\m2a_local_audit_report.md` before sharing.

---

## 9. Step 7 — Post-Audit Verification Checklist Before Sharing Results

Run these final verification commands in PowerShell:

```powershell
# 1. Confirm git status is completely clean under /data/ (zero tracked or untracked data files staged)
git status --short
git status --ignored --short data/

# 2. Confirm originals_byte_identical == true and patient_level_rows_emitted == 0
python -c "import json; r=json.load(open('data/reports/m2a_local_audit_report.json')); print('byte_identical:', r['safety_and_non_fitting_certification']['originals_byte_identical'], 'patient_rows:', r['safety_and_non_fitting_certification']['patient_level_rows_emitted'])"

# 3. Inspect the Markdown report manually to confirm only aggregate metadata is present
Get-Content "data\reports\m2a_local_audit_report.md" | Select-Object -First 80
```
