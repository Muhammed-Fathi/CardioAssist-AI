# 09 — M2a Windows-Local Dataset Audit Handoff (`E:\CardioAssist_AI_GitHub_Starter`)

| Field | Value |
|---|---|
| Milestone | **M2a — Maintainer-Led Gate DA and Local Dataset Audit Readiness** |
| Governance status | **PROPOSED — PENDING HUMAN ACCEPTANCE (`D-046`)** |
| Supervisor status | **DEFERRED — no supervisor approval is asserted or implied** |
| Model fitting status | **PROHIBITED (`model_fitting_authorized = false`)** |
| Target machine | Maintainer's local Windows 10/11 workstation (`E:\CardioAssist_AI_GitHub_Starter`), Python 3.12, $0 budget (no Docker, paid GPU, cloud compute, or credit card) |
| Testing boundary note | The Python CLI commands (`python -m research.audit ...`), pytest suites (`tests/audit/`, `tests/contracts/`, `tests/backend/`), `pip check`, and `git check-ignore` checks were executed and verified in the Linux sandbox (Python 3.11.2). Windows-specific PowerShell session activation (`.\.venv-audit\Scripts\Activate.ps1`), Windows drive paths (`E:\CardioAssist_AI_GitHub_Starter`), and live outbound downloads from `archive.ics.uci.edu` (blocked in the sandbox) must be executed by the maintainer on Windows after approving **D-046**. |

---

## Step 1 — Environment Setup ($0, Isolated Audit Virtual Environment)

Open **Windows PowerShell** on your local machine and navigate to the repository root:

```powershell
Set-Location E:\CardioAssist_AI_GitHub_Starter
git status
git rev-parse HEAD
python --version
```

Create and activate an isolated Python virtual environment for the M2a audit
toolchain (isolated from `backend/requirements.txt`), install the pinned free
dependencies (`openpyxl==3.1.5`, `et-xmlfile==2.0.0`, `pytest==9.0.3` and its
transitive closure), and verify dependency consistency and synthetic self-tests:

```powershell
python -m venv .venv-audit
.\.venv-audit\Scripts\Activate.ps1
python -m pip install -r research/audit/requirements.txt
python -m pip check
python -m pytest tests/audit -q -W error
python -m research.audit self-test
python scripts/verify_sources.py
```

*(Note: `.venv-audit/` is local; if you prefer to reuse `.venv`, `research/audit/requirements.txt` is also pin-compatible with `backend/requirements-dev.txt`, and `.gitignore` ignores `.venv/`.)*

---

## Step 2 — Authorization-Status Check

Before any dataset acquisition, verify the current Gate DA governance and
per-dataset authorization status recorded in
`research/audit/gate_da_authorization.json`:

```powershell
Set-Location E:\CardioAssist_AI_GitHub_Starter
python -m research.audit check-auth
```

By default on this PR branch, all four proposed dataset entries (`DA-A1`,
`DA-A2`, `DA-B1`, `DA-B2`) report:

- `"workflow_status": "PENDING_HUMAN_ACCEPTANCE"`
- `"authorization_status": "PENDING_HUMAN_ACCEPTANCE"`
- `"supervisor_approval_claimed": false`
- `"model_fitting_authorized": false`

If you attempt to run `python -m research.audit run-audit` while datasets are
still `PENDING_HUMAN_ACCEPTANCE`, the toolchain **fails closed** with exit code
`2` (`governance_authorization_error`).

---

## Step 3 — Dry Run / Preflight Validation (No Data Downloaded)

Verify that `/data/` paths are git-ignored (`git check-ignore -v`), zero files
under `/data/` are tracked in Git, and generate the metadata-only preflight
readiness report without downloading or reading any dataset files:

```powershell
Set-Location E:\CardioAssist_AI_GitHub_Starter
python -m research.audit verify-ignore
python -m research.audit dry-run `
  --json-out data\reports\m2a_preflight_report.json `
  --markdown-out data\reports\m2a_preflight_report.md
Get-Content data\reports\m2a_preflight_report.md
```

---

## Step 4 — Exact Official Acquisition Procedure (ONLY After Human Maintainer Approval of D-046)

> **STOP — HUMAN GATE:** Execute this step **only after** you (the human
> maintainer) have reviewed and approved **D-046** and updated the approved
> dataset entries in `research/audit/gate_da_authorization.json` from
> `"PENDING_HUMAN_ACCEPTANCE"` to `"AUTHORIZED_FOR_READ_ONLY_AUDIT"` with your
> name (`authorized_by`), date (`authorized_date`), `responsible_acquirer`,
> and `audit_reviewer`.

### 4.1 Record Human Authorization in `research/audit/gate_da_authorization.json`

After approving the M2a PR, update `research/audit/gate_da_authorization.json`
for the exact datasets you are authorizing (`DA-A1`, `DA-A2`, and optionally
`DA-B1` / `DA-B2` for audit-only use) and verify via `check-auth`:

```powershell
python -m research.audit check-auth
```

### 4.2 Create Git-Ignored `/data/` Directories and Verify `git check-ignore`

```powershell
Set-Location E:\CardioAssist_AI_GitHub_Starter
New-Item -ItemType Directory -Force -Path `
  data\downloads, `
  data\raw\uci-412, `
  data\raw\uci-45, `
  data\raw\uci-411, `
  data\raw\uci-145, `
  data\manifests\licenses, `
  data\reports | Out-Null

python -m research.audit verify-ignore
git check-ignore -v data/ data/raw/uci-412/ data/raw/uci-45/ data/raw/uci-411/ data/raw/uci-145/ data/manifests/
```

### 4.3 Official-Source Acquisition (Primary PowerShell Procedure + Manual Browser Fallback)

Acquire files **exclusively** from the official UCI Machine Learning Repository
(`https://archive.ics.uci.edu`). **Never** download from Kaggle, GitHub mirrors,
Zenodo, or third-party links.

| Dataset ID | Official UCI Landing Page | DOI | Required Local Destination & Exact Filenames |
|---|---|---|---|
| `DA-A1` | `https://archive.ics.uci.edu/dataset/412/z+alizadeh+sani` | `10.24432/C5Q31T` | `data\raw\uci-412\Z-Alizadeh sani dataset.xlsx` |
| `DA-A2` | `https://archive.ics.uci.edu/dataset/45/heart+disease` | `10.24432/C52P4X` | `data\raw\uci-45\` → `processed.cleveland.data`, `cleveland.data`, `processed.hungarian.data`, `hungarian.data`, `processed.switzerland.data`, `switzerland.data`, `processed.va.data`, `long-beach-va.data`, `heart-disease.names` |
| `DA-B1` *(if authorized, audit-only)* | `https://archive.ics.uci.edu/dataset/411/extention+of+z+alizadeh+sani` | `10.24432/C5461K` | `data\raw\uci-411\extention of Z-Alizadeh sani dataset.xlsx` |
| `DA-B2` *(if authorized, audit-only)* | `https://archive.ics.uci.edu/dataset/145/statlog+heart` | `10.24432/C57303` | `data\raw\uci-145\heart.dat` |

#### Option A — Official UCI Static Archive Download via PowerShell (`Invoke-WebRequest`)

```powershell
Set-Location E:\CardioAssist_AI_GitHub_Starter

# 1. Download official UCI ZIP archives into git-ignored data\downloads\
Invoke-WebRequest -Uri "https://archive.ics.uci.edu/static/public/412/z+alizadeh+sani.zip" `
  -OutFile "data\downloads\uci-412.zip"
Invoke-WebRequest -Uri "https://archive.ics.uci.edu/static/public/45/heart+disease.zip" `
  -OutFile "data\downloads\uci-45.zip"

# Only if DA-B1 / DA-B2 are explicitly authorized for audit-only investigation:
Invoke-WebRequest -Uri "https://archive.ics.uci.edu/static/public/411/extention+of+z+alizadeh+sani.zip" `
  -OutFile "data\downloads\uci-411.zip"
Invoke-WebRequest -Uri "https://archive.ics.uci.edu/static/public/145/statlog+heart.zip" `
  -OutFile "data\downloads\uci-145.zip"
```

#### Option B — Manual Official-Source Browser Fallback (If Automated Download Is Blocked or Unreliable)

If `Invoke-WebRequest` fails due to network/TLS interception or UCI rate-limiting:

1. Open each official UCI landing page URL in your Windows browser:
   - `https://archive.ics.uci.edu/dataset/412/z+alizadeh+sani`
   - `https://archive.ics.uci.edu/dataset/45/heart+disease`
   - `https://archive.ics.uci.edu/dataset/411/extention+of+z+alizadeh+sani` *(only if DA-B1 authorized)*
   - `https://archive.ics.uci.edu/dataset/145/statlog+heart` *(only if DA-B2 authorized)*
2. Click the official **Download** button on each UCI page and save the `.zip`
   archives to:
   - `E:\CardioAssist_AI_GitHub_Starter\data\downloads\uci-412.zip`
   - `E:\CardioAssist_AI_GitHub_Starter\data\downloads\uci-45.zip`
   - `E:\CardioAssist_AI_GitHub_Starter\data\downloads\uci-411.zip`
   - `E:\CardioAssist_AI_GitHub_Starter\data\downloads\uci-145.zip`

### 4.4 Inspect Archives in Read-Only Mode Before Extraction (Fail-Closed Gate)

Run `inspect-archive` on every downloaded `.zip` archive **before** extracting:

```powershell
Set-Location E:\CardioAssist_AI_GitHub_Starter
python -m research.audit inspect-archive --dataset-id DA-A1 --zip-path data\downloads\uci-412.zip
python -m research.audit inspect-archive --dataset-id DA-A2 --zip-path data\downloads\uci-45.zip
# If DA-B1 / DA-B2 are authorized:
python -m research.audit inspect-archive --dataset-id DA-B1 --zip-path data\downloads\uci-411.zip
python -m research.audit inspect-archive --dataset-id DA-B2 --zip-path data\downloads\uci-145.zip
```

> **Important (`DA-A2` UCI-45 exclusion rule):** The official UCI-45 zip archive
> contains legacy files such as `new.data` and `reprocessed.hungarian.data` that
> are **NOT authorized** by `DA-A2`. `inspect-archive` flags them under
> `excluded_files_detected_do_not_extract`. Extract **only** the 9 authorized
> files listed in `research/audit/gate_da_authorization.json`!

```powershell
# Safe selective extraction of ONLY the authorized files into data\raw\...
python -c "
import json, pathlib, shutil, zipfile
auth = json.loads(pathlib.Path('research/audit/gate_da_authorization.json').read_text(encoding='utf-8'))
zip_map = {'DA-A1': 'data/downloads/uci-412.zip', 'DA-A2': 'data/downloads/uci-45.zip', 'DA-B1': 'data/downloads/uci-411.zip', 'DA-B2': 'data/downloads/uci-145.zip'}
for ds_id, z_rel in zip_map.items():
    zp = pathlib.Path(z_rel)
    if not zp.exists():
        continue
    spec = auth['datasets'][ds_id]
    allowed = set(spec['authorized_files']) | set(spec.get('optional_documentation_files', []))
    out_dir = pathlib.Path(spec['local_subdir'])
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zp, 'r') as zf:
        for info in zf.infolist():
            name = pathlib.PurePosixPath(info.filename.replace('\\', '/')).name
            if not info.is_dir() and name in allowed:
                target = out_dir / name
                with zf.open(info, 'r') as src, target.open('wb') as dst:
                    shutil.copyfileobj(src, dst)
                print(f'Extracted authorized file: {target}')
"
```

### 4.5 Save Download-Day License Snapshots and Record SHA-256 Provenance

Save the download-day official UCI license snapshot (`CC BY 4.0`) for each
acquired dataset under `data\manifests\licenses\` and run `record-provenance`:

```powershell
Set-Location E:\CardioAssist_AI_GitHub_Starter

@"
Dataset: UCI Z-Alizadeh Sani (UCI ID 412)
DOI: 10.24432/C5Q31T
Official URL: https://archive.ics.uci.edu/dataset/412/z+alizadeh+sani
License verified on official UCI page at acquisition: Creative Commons Attribution 4.0 International (CC BY 4.0)
Snapshot Date (UTC): $( (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ") )
"@ | Set-Content -Encoding UTF8 data\manifests\licenses\uci-412-license-snapshot.txt

@"
Dataset: UCI Heart Disease (UCI ID 45)
DOI: 10.24432/C52P4X
Official URL: https://archive.ics.uci.edu/dataset/45/heart+disease
License verified on official UCI page at acquisition: Creative Commons Attribution 4.0 International (CC BY 4.0)
Snapshot Date (UTC): $( (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ") )
"@ | Set-Content -Encoding UTF8 data\manifests\licenses\uci-45-license-snapshot.txt

@"
Dataset: UCI Extension of Z-Alizadeh Sani (UCI ID 411)
DOI: 10.24432/C5461K
Official URL: https://archive.ics.uci.edu/dataset/411/extention+of+z+alizadeh+sani
License verified on official UCI page at acquisition: Creative Commons Attribution 4.0 International (CC BY 4.0)
Snapshot Date (UTC): $( (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ") )
"@ | Set-Content -Encoding UTF8 data\manifests\licenses\uci-411-license-snapshot.txt

@"
Dataset: UCI Statlog (Heart) (UCI ID 145)
DOI: 10.24432/C57303
Official URL: https://archive.ics.uci.edu/dataset/145/statlog+heart
License verified on official UCI page at acquisition: Creative Commons Attribution 4.0 International (CC BY 4.0)
Snapshot Date (UTC): $( (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ") )
"@ | Set-Content -Encoding UTF8 data\manifests\licenses\uci-145-license-snapshot.txt

# Generate and validate data\manifests\provenance_manifest.json with SHA-256 hashes and byte sizes
python -m research.audit record-provenance `
  --datasets DA-A1 DA-A2 DA-B1 DA-B2 `
  --acquirer "Muhammed Fathi" `
  --audit-reviewer "Muhammed Fathi" `
  --environment "E:\CardioAssist_AI_GitHub_Starter (Windows PowerShell, Python 3.12)"
```

---

## Step 5 — Safe Read-Only Audit Execution

Execute the read-only local dataset audit:

```powershell
Set-Location E:\CardioAssist_AI_GitHub_Starter
python -m research.audit run-audit `
  --json-out data\reports\m2_local_audit_report.json `
  --markdown-out data\reports\m2_local_audit_report.md
```

What happens during `run-audit`:
- Verifies `git check-ignore -v` and zero tracked files under `/data/`.
- Verifies `gate_da_authorization.json` and `data\manifests\provenance_manifest.json`.
- Records pre-audit SHA-256 and byte size of every file via `ByteIdentityGuard`.
- Runs all 12 read-only audit functions in memory without modifying any file.
- Re-computes post-audit SHA-256 and byte size of every file to prove originals remain byte-identical.
- Runs `verify_report_no_patient_rows` to guarantee zero patient-level rows or raw data lines appear in the generated reports.

---

## Step 6 — Reading the Generated Reports

Inspect the generated metadata-only Markdown and JSON audit reports in
PowerShell:

```powershell
Set-Location E:\CardioAssist_AI_GitHub_Starter
Get-Content data\reports\m2_local_audit_report.md
Get-Content data\reports\m2_local_audit_report.json | ConvertFrom-Json | Format-List
```

If you wish to submit the metadata-only report in a subsequent M2 review PR
after reviewing its contents, copy **only** the verified metadata-only Markdown
report into `docs\research\gate-da\` — never copy anything from `data\raw\` or
any patient-level file.

---

## Step 7 — Verifying That Patient-Level Data Remain Ignored

Run the following verification commands immediately after acquisition and after
audit execution to confirm that no dataset file or `/data/` artifact is staged,
tracked, or unignored by Git:

```powershell
Set-Location E:\CardioAssist_AI_GitHub_Starter
python -m research.audit verify-ignore
git check-ignore -v data/ data/raw/uci-412/ data/raw/uci-45/ data/raw/uci-411/ data/raw/uci-145/ data/manifests/ data/reports/
git status --ignored
git ls-files -- data/
```

Expected results:
- `python -m research.audit verify-ignore` outputs `"passed": true` and `"tracked_files_under_data": []`.
- `git ls-files -- data/` produces **empty output** (0 tracked files).
- `git status` shows no untracked or staged files under `data/`.

---

## Step 8 — Safe Cleanup Instructions (No Automatic Deletion of Research Data)

1. **Research data under `data\raw\` and `data\manifests\` are NEVER deleted
   automatically** by any script, test, or CLI command in this repository.
2. To deactivate and remove the disposable `.venv-audit` virtual environment
   without touching any research data:

   ```powershell
   deactivate
   Remove-Item -Recurse -Force .\.venv-audit
   ```

3. To remove only the disposable preflight/audit report outputs in
   `data\reports\` while keeping `data\raw\` and `data\manifests\` intact:

   ```powershell
   Remove-Item -Force .\data\reports\m2a_preflight_report.* -ErrorAction SilentlyContinue
   ```

4. **Do NOT delete `data\raw\` or `data\manifests\` unless a named human
   maintainer explicitly decides to retire the local dataset cache and records a
   dated note in the audit log** (per `docs/research/gate-da/04_gate_da_approval_packet.md` §3 rule 5).
