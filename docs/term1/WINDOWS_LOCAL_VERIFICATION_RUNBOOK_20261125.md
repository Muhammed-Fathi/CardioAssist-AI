# Term 1 Prototype — Windows Local Verification Runbook (draft)

**Status:** This is a procedure for the human maintainer after Arena implements and pushes the prototype. It does NOT claim the new features, seed command, model serving or E2E test already exist. Test with fabricated patients and locally generated secrets only.

## 1. Base checkout / PowerShell

Use Windows PowerShell 5.1 from a new, disposable directory; never run these commands against real clinical data.

```powershell
git clone --branch delivery/term1-prototype https://github.com/Muhammed-Fathi/CardioAssist-AI.git
Set-Location .\CardioAssist-AI
git fetch origin
git status --short
git rev-parse HEAD
python --version
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend/requirements-dev.txt
python -m pip check
```

If PowerShell script execution is restricted, use the virtualenv Python executable directly, or follow your authorized local activation policy; do not disable corporate controls without permission.

## 2. Disposable development database

```powershell
New-Item -ItemType Directory -Force .\var | Out-Null
$env:CARDIOASSIST_DATABASE_URL = "sqlite:///./var/cardioassist_term1_demo.sqlite3"
python -m alembic upgrade head
python -m alembic current
python -m alembic check
```

Create **local secrets using a cryptographic RNG**, supplied through environment variables or an ignored local env file. The actual names/settings must be frozen by Arena in the delivered configuration contract; do not invent a secret name and assume code uses it. Never upload keys, `.env`, database files, logs containing credentials, patient identifiers or model bundles to GitHub/Arena.

## 3. Automated regression

```powershell
python -m pytest tests/contracts tests/backend -q -W error
python -m pytest -q -W error
python scripts/verify_sources.py
git diff --check
```

Report exact pass/fail/skip numbers and command exit codes; never say 'passed' for a test not run. Full pytest may take longer than the focused suite.

## 4. Start the service and inspect OpenAPI

In one PowerShell window:
```powershell
$env:CARDIOASSIST_DATABASE_URL = "sqlite:///./var/cardioassist_term1_demo.sqlite3"
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

In another:
```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/openapi.json | Select-Object -ExpandProperty info
```

**Final Arena delivery must supply exact validated commands** for demo admin/doctor provisioning, visit-attested patient invitation, ID-matching registration, patient/doctor login, actual trained-model run, review, message, notification read and read-status. Do not improvise API request formats; use shipped OpenAPI and demo fixture script.

## 5. Required end-to-end walkthrough (with fabricated identities)

1. Seed demo admin and doctor without hard-coded/default git credentials.
2. Doctor enters an attested fictitious visit, issues an invitation for `DEMO-ID-001`. Code appears only once in a trusted local response.
3. Patient registers with wrong fabricated ID -> generic error; retry with correct matching `DEMO-ID-001` -> success. Reuse code -> rejected.
4. Login as patient, submit valid synthetic profile/features and generate assessment.
5. Verify **actual trained-model inference** and explanation and artifact identity, or stop and report `PENDING_AUTHORIZATION`; do NOT present MOCK_SYNTHETIC as real. Under unratified patient-score display, patient sees PENDING_REVIEW but no model score.
6. Login as assigned clinician, review immutable snapshot, record action and send educational note/demo prescription. Verify unassigned clinician cannot access it.
7. Patient lists notifications, opens unread item, marks read, reads follow-up.
8. Restart Uvicorn, retry GETs; all accepted records still persisted. Inspect SQL schema and audit safely, without printing raw credentials or identifiers.

## 6. Independent negative/rollback checks

Run agent-delivered targeted test commands for expiration, revocation, duplicate/in-race invitation, wrong identifier, user role cross-access, model tampering/disallowed sources, inference unavailable, no stale outputs, double review/duplicate follow-up, server/database rollback. Then rerun all focused regressions.

Use a **fresh disposable DB** to test from-zero migrations. Do not delete existing non-demo databases.

## 7. Clean up disposable local-only files

Stop Uvicorn with Ctrl+C and make certain `CARDIOASSIST_DATABASE_URL` points to the specific disposable `cardioassist_term1_demo.sqlite3` before deleting anything. Back up any evidence you intentionally want to keep; then remove only this demo DB and its SQLite sidecars:

```powershell
Remove-Item .\var\cardioassist_term1_demo.sqlite3* -Force -ErrorAction SilentlyContinue
Remove-Item Env:\CARDIOASSIST_DATABASE_URL -ErrorAction SilentlyContinue
```

Never use `git clean -fdx` or a broad recursive delete on the repository or personal files.

## 8. Handoff acceptance fields

Record exact SHA, OS build, Python version, dependency report, Alembic current/head and check, test commands/counts, E2E authenticated HTTP trace, persistence-after-restart, AI artifact & authorization decision, patient display decision, every BLOCKED/DEFERRED item and live GitHub checks. Only human local execution establishes Windows verification.
