# Tests

All committed fixtures and persistence test data are **MOCK / SYNTHETIC**.
The suites need no model, real dataset, patient data, paid service or external
database account. The backend suite creates isolated temporary SQLite files
and applies the committed Alembic migration per test; pytest removes its
throwaway databases afterward.

| Folder | Milestone | What it does |
|---|---|---|
| `contracts/` | M1a.1 (D-043), merged PR #3 | **249 tests** for OpenAPI, schemas, fixture/oracle behavior, and safety/compatibility rules. ADR-001 Option A (D-044) added the optional-null matrix and minimally adapted oracle; no original test was removed. See `contracts/README.md`. |
| `backend/` | M1a.2 + M1b.1 | **362 tests**: 347 existing API/HTTP behavior regressions plus 15 SQLite persistence/migration tests. Covers fixture HTTP behavior, validation order/errors, Track separation, synthetic inference, replay/conflict and 24-hour runtime expiry, concurrency, restart durability of monitoring rows, rollback, constraints, malformed inputs, configuration-based DB path and test-DB isolation. |
| **Total** | current checkout | **611 tests** (`249` contract + `362` backend). The exact latest local run, interpreter and CI caveats are recorded in `backend/VERIFICATION.md` and `docs/blueprint/08_IMPLEMENTATION_STATUS_VS_FUTURE_SCOPE.md`. |

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
