# Tests

All committed fixtures and persistence test data are **MOCK / SYNTHETIC**.
The suites need no model, real dataset, patient data, paid service or external
database account. Backend tests use isolated temporary SQLite files; tests
apply the committed Alembic migration where appropriate, and schema-verification
regressions deliberately use unmigrated or malformed disposable databases.
Pytest removes its throwaway databases afterward.

| Folder | Milestone | What it does |
|---|---|---|
| `contracts/` | M1a.1 (D-043), merged PR #3 | **249 tests** for OpenAPI, schemas, fixture/oracle behavior, and safety/compatibility rules. ADR-001 Option A (D-044) added the optional-null matrix and minimally adapted oracle; no original test was removed. See `contracts/README.md`. |
| `backend/` | M1a.2 + M1b.1 | **371 tests**: 347 existing API/HTTP behavior regressions plus 24 SQLite persistence/migration tests. Covers fixture HTTP behavior, validation order/errors, Track separation, synthetic inference, replay/conflict and 24-hour runtime expiry, concurrency, restart durability, rollback, revision/schema drift and integrity rejection, lifespan failure without auto-migration/repair, malformed inputs, configuration-based DB path and test-DB isolation. |
| `audit/` | M2a (D-046 proposed) | **41 tests**: synthetic unit and negative tests for the read-only local dataset audit toolchain (`research/audit/`). Covers D-046 global (`workflow_status`) and dataset-level governance/authorization checks (`PENDING_HUMAN_ACCEPTANCE`), strict input path/directory containment and symlink rejection, locked output paths (`data/reports/` for reports and `data/manifests/provenance_manifest.json` for provenance) preventing dataset overwrite, separated `downloaded_at_utc` vs `manifest_recorded_at_utc` and human-attested vs locally verified integrity semantics, `STOP_REQUIRES_REVIEW` archive inspection and human-reviewed controlled extraction (`extract-authorized-archive`) with existing-file overwrite/collision protection and safe cleanup of incomplete newly created files, `ByteIdentityGuard` verification across parsing and report generation/writing on both success and failure paths, `git check-ignore` protection, UCI-412/45/411/145 parsing, null vs zero semantics, wrong delimiters/columns, raw-vs-processed confusion, duplicate/near-duplicate and correspondence checks, leakage-column detection, strict allowlisted metadata report schema (`validate_strict_metadata_report_schema`) + secondary multi-format pattern/fingerprint scanner (`verify_report_no_patient_rows`), and proposed audit CI workflow (`audit-toolchain-validation`) and official dataset reference consistency validation. See `audit/README.md`. |
| **Total** | current checkout | **661 tests** (`249` contract + `371` backend + `41` audit). The current local run, interpreter and CI caveats are recorded in `backend/VERIFICATION.md`, `research/audit/ci/README.md`, and `docs/blueprint/08_IMPLEMENTATION_STATUS_VS_FUTURE_SCOPE.md`. |

## Local setup and checks (repository root)

Python 3.11 or 3.12; no Docker or external DB service is required. Install the
pinned open-source dependencies (package-index access is needed to install):

```bash
python -m venv .venv
. .venv/bin/activate                 # Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements-dev.txt
python -m pip check
python -m pytest tests/contracts tests/backend -q -W error
python -m pytest -q -W error
python scripts/verify_sources.py
git diff --check
```

For Windows PowerShell, explicit Alembic migrations, configured SQLite path,
app restart and safe disposable-database cleanup, use
[`backend/README.md`](../backend/README.md). Tests create migrated temporary
SQLite databases; they do not use or delete a developer's configured database.

Only contract tests, without the backend dependencies:

```bash
python -m pip install -r tests/contracts/requirements.txt
python -m pytest tests/contracts -q -W error
```

## CI status and scope

Both `.github/workflows/contracts-ci.yml` and
`.github/workflows/backend-ci.yml` are installed. The backend workflow runs
contract and backend suites (including the SQLite migration/persistence tests),
`pip check`, source verification and a prohibited-artifact extension check on
Python 3.11/3.12. **Workflow presence is not evidence of a passing run.** Check
status must be reported separately from local results. For PR #9, the check
rollup and REST check-run/status endpoints returned HTTP 403 `Resource not
accessible by integration`; individual GitHub results are **UNVERIFIED**. See
[`backend/ci/README.md`](../backend/ci/README.md).

`tests/__init__.py` and `tests/backend/__init__.py` keep the backend
`conftest.py` namespaced, so it does not shadow the legacy contract tests'
`from conftest` imports. The contract oracle and actual HTTP tests remain
independent. No original contract test was rewritten to accommodate the server.

See [`backend/CONTRACT_NOTES.md`](../backend/CONTRACT_NOTES.md) for preserved
behavior, open questions, and the 503 response for the legacy LIME-only
binding. The unchanged M1a.1 LIME fixture/oracle tests still run.
