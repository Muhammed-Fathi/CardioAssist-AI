# Dataset Audit Toolchain CI Specification (`research/audit/ci/`)

## Purpose

The existing `.github/workflows/backend-ci.yml` workflow executes:

```bash
python -m pytest tests/contracts tests/backend -q -W error
```

Green `backend-ci.yml` and `contracts-ci.yml` runs validate only the contract
and backend test suites (`249 + 371 = 620` tests); they **do not** execute or
validate `tests/audit` unless a workflow running `pytest tests/audit` is
installed under `.github/workflows/`.

## Proposed Audit CI Workflow (`audit-ci.yml.example`)

[`audit-ci.yml.example`](audit-ci.yml.example) defines the dedicated
`audit-toolchain-validation` GitHub Actions workflow (`Python 3.11` and
`Python 3.12` matrix on `ubuntu-24.04`) with:

1. **Pinned dependencies**:
   ```bash
   python -m pip install -r research/audit/requirements.txt
   python -m pip check
   ```
2. **Audit unit and negative test suite**:
   ```bash
   python -m pytest tests/audit -q -W error
   ```
3. **Audit CLI preflight and isolated synthetic self-test**:
   ```bash
   python -m research.audit check-auth
   python -m research.audit verify-ignore
   python -m research.audit dry-run
   python -m research.audit self-test
   ```
4. **Original source-integrity verification**:
   ```bash
   python scripts/verify_sources.py
   ```
5. **Prohibited artifact and `/data/` directory guard**:
   Rejects any file under `/data/` and any `.pkl`, `.joblib`, `.pt`, `.pth`,
   `.onnx`, `.h5`, `.parquet`, `.csv`, `.xlsx`, `.xls`, `.data`, `.dat`,
   `.sqlite`, `.sqlite3`, `.db`, `.p12`, `.pem`, `.key`, `.env`, or `.env.*`
   file inside `research/audit/` or `tests/audit/`.

## Maintainer Action Required (`workflows` Permission Limitation Verified)

Pushing `.github/workflows/audit-ci.yml` from the Arena GitHub App integration
is rejected by GitHub with:

```text
! [remote rejected] arena/a1f1816a-cardioassist-ai -> arena/a1f1816a-cardioassist-ai (refusing to allow a GitHub App to create or update workflow `.github/workflows/audit-ci.yml` without `workflows` permission)
```

Because `.github/workflows/` cannot be modified without the `workflows`
permission on the GitHub App token, `tests/audit` (`37 passed` locally) is
**NOT yet CI-verified by GitHub Actions**, and green `backend-ci.yml` /
`contracts-ci.yml` runs (`620 passed`) do **not** validate `tests/audit`.

The human maintainer can install the proposed workflow directly from PowerShell
on `E:\CardioAssist_AI_GitHub_Starter`:

```powershell
Set-Location E:\CardioAssist_AI_GitHub_Starter
Copy-Item research\audit\ci\audit-ci.yml.example .github\workflows\audit-ci.yml
git add .github/workflows/audit-ci.yml
git commit -m "ci(audit): install M2a dataset audit toolchain GitHub Actions workflow"
git push
```
