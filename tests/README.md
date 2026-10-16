# Tests

Tests will cover source ingestion, data splits/leakage, models, API contracts, permission boundaries and integration/e2e once implementation is approved.

| Folder | Milestone | What it does |
|---|---|---|
| `contracts/` | **M1a.1 (D-043)** | Validates the **proposed** `/v1` API contract and the deterministic **MOCK / SYNTHETIC** fixture pack. Offline, $0, no model, no dataset, no database, no cloud service. See `contracts/README.md`. |

Run the contract tests locally:

```bash
python -m venv .venv
. .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r tests/contracts/requirements.txt
python -m pytest tests/contracts -q
```

The same suite runs automatically on every pull request
(`.github/workflows/contracts-ci.yml`).
