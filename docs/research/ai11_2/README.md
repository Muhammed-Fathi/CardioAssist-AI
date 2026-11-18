# AI-11.2 — Read-only synthetic research model catalog

**Status:** Implementation proposal pending code review, hosted CI and native Windows acceptance. This is synthetic-only metadata, not a model loader, serving contract, patient-facing feature, or clinical evidence.

## Existing interfaces and the added boundary

- `ai.research_registry.registry_contract()` is the **sole** source of five registered model slots, their versions, route/panel hashes, capability declarations, states and policies. `ai/research_catalog.py` projects these immutable contracts without creating a second registry.
- The exported catalog describes **two active offline synthetic registrations**, two blocked contracts and one locked Hungary target. Active is NOT permission for real data, clinical use or proof that an artifact is present.
- `registry_declared_capabilities` reflects policy only. `verified_artifact_capabilities` is always `null` because catalog-only reading never loads or authenticates a bundle.
- `published_synthetic_model_card_reference` points to the existing AI-12.1 **Cleveland fixed synthetic demo** evidence pack for only that one slot; no other synthetic or real model card is fabricated.
- The SHA-256 catalog digest is a deterministic **checksum, not a signature**. It must not authenticate or register a caller-supplied model. All inference continues through the existing offline `run_offline_research_inference_from_document()` and its trusted-root/HMAC authorization checks.
- The application backend still constructs only `MOCK_SYNTHETIC`. This export adds no `/v1` endpoints, provider switches, database changes, patient inputs, real bundle paths or scoring.

## Run with an existing pinned research Python environment

From a clean repository checkout with Python 3.11/3.12 and existing research dependencies:

```powershell
& $Python scripts/export_research_model_catalog.py --format json
```

Or write **only a brand-new file outside the checkout**:

```powershell
$Out = Join-Path $env:LOCALAPPDATA 'CAI11-2-Review'
New-Item -ItemType Directory -Force -Path $Out | Out-Null
$File = Join-Path $Out ('catalog-' + [guid]::NewGuid().ToString('N') + '.json')
& $Python scripts/export_research_model_catalog.py --output $File
if ($LASTEXITCODE -ne 0) { throw 'Catalog export failed' }
```

The script never overwrites an existing file, and rejects destinations inside its repository. Invalid CLI options or write failures return nonzero exit codes without printing private target paths. A successful export produces reproducible UTF-8 JSON; do not upload any user records or keys.

## Contract and acceptance

- Schema: [`research-model-catalog.v1.schema.json`](research-model-catalog.v1.schema.json) (JSON Schema draft 2020-12). Every entry includes registry identity, `model_key`, route and panel versions, SHA-bound ordered field descriptors, policy, operational state and explicit false serving/clinical/real-data flags.
- Focused tests: `tests/experiments/test_research_catalog.py`, `tests/contracts/test_research_catalog_schema.py`, plus existing research facade, source integrity and backend-provider tests.
- Repeat two exports to **distinct fresh external files**, confirm byte-identical data, valid schema, 5 states, zero model loads, and unchanged Git checkout.
- On exact reviewed code SHA: run applicable Linux Actions and maintainer Windows Python 3.12 `-W error` focused/full tests, native NTFS 8/8 security harness, synthetic eight-stage demo and `ai.research_evidence` comparison. Keep actual pass/skip/fail/exit and warnings in the handoff; older AI-12.1 results do **not** count as AI-11.2 code acceptance.
- AI-11.2 stays `NOT_STARTED` in the tracker until code is accepted. After human merge and post-merge Windows validation, use a separate docs-only closeout PR to update tracking.

## Non-authorizations

No UCI-412 real-data scientific hold lifted; no D-048 activation, Hungary evaluation, patient-level evidence, clinical serving, healthcare advice, Gate PT amendment, real inference, new training or protected-manifest access. The only new product is a static, read-only **research handoff**. No GPU, cloud service or paid license required.
