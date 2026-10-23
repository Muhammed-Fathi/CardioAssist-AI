# Tests

All committed fixtures and persistence test data are **MOCK / SYNTHETIC**. No
real dataset rows are used in the test suite. The M2c experiment tests fit
scikit-learn estimators only on generated, in-memory synthetic fixtures; the
real-data `preflight`/`run` path is never invoked. Backend tests use isolated
temporary SQLite files; tests apply the committed Alembic migration where
appropriate, and schema-verification regressions deliberately use unmigrated or
malformed disposable databases. Pytest removes its throwaway databases after
the tests.

| Folder | Milestone | What it does |
|---|---|---|
| `contracts/` | M1a.1 (D-043), merged PR #3 | **249 tests** for OpenAPI, schemas, fixture/oracle behavior, and safety/compatibility rules. ADR-001 Option A (D-044) added the optional-null matrix and minimally adapted oracle; no original test was removed. See `contracts/README.md`. |
| `backend/` | M1a.2 + M1b.1 | **371 tests**: 347 existing API/HTTP behavior regressions plus 24 SQLite persistence/migration tests. Covers fixture HTTP behavior, validation order/errors, Track separation, synthetic inference, replay/conflict and 24-hour runtime expiry, concurrency, restart durability, rollback, revision/schema drift and integrity rejection, lifespan failure without auto-migration/repair, malformed inputs, configuration-based DB path and test-DB isolation. |
| `audit/` | M2a + M2b.2 | **218 collected test cases**: synthetic-only unit and negative tests for the read-only local audit toolchain plus stage validation and model-independent preprocessing. Coverage includes source-code ordering, missingness/reasons, zero safeguards, exact units, finite numerics, leakage/identifier/wearable rejection, deterministic transforms, and synthetic training-only preprocessing. See `audit/README.md`. |
| `experiments/` | M2c | **25 tests** using only generated synthetic fixtures: exact processed-source schema and target mapping, `?` handling, source-hash mismatch and byte preservation, authorization/runtime rejection, no-row preflight, frozen-config enforcement, fold-local preprocessing, nested split separation, model selection, metrics/calibration, deterministic predictions, and ignored output/symlink/tracked-file protection. |
| **Total** | current checkout | **863 tests** (`249` contract + `371` backend + `218` audit + `25` experiment-runner). These are local results, not GitHub CI results. |

## Local setup and checks (repository root)

Python 3.11 or 3.12; no Docker or external DB service is required. Install the
pinned open-source dependencies (package-index access is needed to install):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements-dev.txt
python -m pip install -r research/audit/requirements.txt
python -m pip install -r research/experiments/requirements.txt
python -m pip check
python -m pytest -q -W error
python scripts/verify_sources.py
python -m research.experiments dry-run
```

The experiment dry-run fits only generated synthetic data in memory, writes no
reports/predictions/models, and prints a synthetic-only PASS marker. For the
full protected Windows-local D-047 handoff and the explicit authorization
boundary, see [`research/experiments/README.md`](../research/experiments/README.md).

For Windows PowerShell, explicit Alembic migrations, configured SQLite path,
app restart and safe disposable-database cleanup, use
[`backend/README.md`](../backend/README.md). Tests create migrated temporary
SQLite databases; they do not use or delete a developer's configured database.

Only contract tests, without the backend dependencies:

```powershell
python -m pip install -r tests/contracts/requirements.txt
python -m pytest tests/contracts -q -W error
```

## CI status and scope

The repository's contract, backend, and audit workflows are the active CI
workflows. The experiment-runner workflow is retained only as the tracked
example template at
[`research/experiments/ci/experiment-runner-ci.yml.example`](../research/experiments/ci/experiment-runner-ci.yml.example).
It is **not active**: GitHub Actions does not discover or execute it from that
path. There is currently no dedicated GitHub CI result for the M2c ML runner;
passing contract, backend, or audit checks do not establish that the new runner
passed dedicated CI. The template is synthetic-only and does not invoke
`preflight` or `run`. Check status must be reported separately from local
results; confirm active workflow checks on the PR page.

`tests/__init__.py` and `tests/backend/__init__.py` keep the backend
`conftest.py` namespaced, so it does not shadow the legacy contract tests'
`from conftest` imports. The contract oracle and actual HTTP tests remain
independent. No original contract test was rewritten to accommodate the server.

See [`backend/CONTRACT_NOTES.md`](../backend/CONTRACT_NOTES.md) for preserved
behavior, open questions, and the 503 response for the legacy LIME-only
binding. The unchanged M1a.1 LIME fixture/oracle tests still run.
