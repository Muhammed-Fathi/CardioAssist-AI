# Contract tests (M1a.1)

Lightweight, offline tests for the **proposed** CardioAssist AI `/v1` API
contract and the deterministic **MOCK / SYNTHETIC** fixture pack.

| Item | Value |
|---|---|
| Milestone | M1a.1 (D-043) — contract definitions, mock fixtures, contract tests |
| Cost | $0 — pure-Python, CPU only, no service, no account, no data |
| Network | none at test time |
| Model / dataset | none — no model is trained, loaded or downloaded; no dataset is read |
| Scope | contract design and validation only. **Not** a server, **not** an API implementation |

## What is here

| File | Role |
|---|---|
| `conftest.py` | Shared helpers: schema registry, validators, fixture loading |
| `reference_contract.py` | **Test oracle.** A deterministic, in-process implementation of the contract semantics (validation order, idempotency, mock scoring, mock explanations). It is *not* a server: there is no HTTP layer, no framework and no database. |
| `test_openapi_document.py` | The OpenAPI 3.1 document is valid, exposes exactly two endpoints, resolves every `$ref`, and documents its errors and idempotency explicitly |
| `test_schemas.py` | The JSON Schemas are valid, and the `MOCK_ONLY` schemas may not drift into impersonating a validated clinical dictionary |
| `test_fixtures.py` | The fixture pack validates against the schemas, is reproduced exactly by the oracle, and satisfies the explanation, rendering, idempotency, track-separation and claims-discipline rules |

## Running the tests

```bash
python -m venv .venv
. .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r tests/contracts/requirements.txt
python -m pytest tests/contracts -q
```

Python 3.10+ is required (3.11/3.12 are used in CI). Everything runs offline.

## Scope boundary

This directory deliberately contains **no** FastAPI server, **no** database,
**no** authentication, **no** model code and **no** dataset code. Those belong
to later milestones (M1a.2 / M1b) and are out of scope for M1a.1.
