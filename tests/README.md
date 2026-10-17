# Tests

All current tests run on committed **MOCK / SYNTHETIC** contracts/inputs only.
No model, dataset, database, service or account is needed at test time.

| Folder | Milestone | What it does |
|---|---|---|
| `contracts/` | M1a.1 (D-043), merged PR #3 | 249 contract/fixture/oracle tests. Historical proposal markers do not imply scientific/clinical approval. The ADR-001 Option A correction (D-044) adds the optional-null matrix and a minimally adapted oracle; the original tests are kept. See `contracts/README.md`. |
| `backend/` | M1a.2 | 347 actual FastAPI HTTP tests, independent of the fixture-generating oracle. Golden HTTP responses, schema/error compliance, missing/null/zero, Track separation, XAI additivity, replay/conflict, 24-hour expiry, restart reset, failure paths, concurrent one-result/one-event guarantees and the ADR-001 optional-null semantics. |

## Combined suite (repository root)

```bash
python -m venv .venv
. .venv/bin/activate            # Windows: .venv\Scripts\activate
python -m pip install -r backend/requirements-dev.txt
python -m pip check
python -m pytest tests/contracts tests/backend -q -W error
# Or discover every pytest test in the repository:
python -m pytest -q -W error
```

Only original contract tests:

```bash
python -m pip install -r tests/contracts/requirements.txt
python -m pytest tests/contracts -q
```

The original `.github/workflows/contracts-ci.yml` is unchanged. The proposed
backend workflow is a **non-executing template** at
`backend/ci/backend-ci.yml.example`; its exact intended destination is
`.github/workflows/backend-ci.yml`. The maintainer must install it manually
and inspect actual runs. **GitHub Actions status is UNVERIFIED** until then.
See `backend/ci/README.md` for exact content/location and installation steps.
The template covers contracts + HTTP tests on Python 3.11/3.12, with pinned
dependencies/actions and no network during tests.
`tests/__init__.py` and `tests/backend/__init__.py` keep the new suite's conftest
namespaced, so it does not shadow the legacy contract tests' `from conftest`
imports. No original contract test is rewritten to accommodate the server.

See `backend/CONTRACT_NOTES.md` for reported ambiguities/compatibility behavior
and the explicit 503 for the legacy LIME-only binding. Its HTTP test is not
skipped, and the unchanged M1a.1 LIME fixture/oracle tests still run.
