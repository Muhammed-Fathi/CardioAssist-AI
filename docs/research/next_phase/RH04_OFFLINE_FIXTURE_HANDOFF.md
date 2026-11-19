# RH-04.3/4 · offline synthetic fixture handoff v1

Issue #114 returned HTTP 403. This implements the maintainer-supplied fallback, not a claim about the unread issue. Base: PR #113 merge `aa3c9cc39b2d08e077cb0c9873833c4e0b3bc305`.

**Already present:** four panel contracts, five route descriptors and model entries, acquisition-evidence crosswalk 1.1.0, typed offline facade, deterministic response digests, synthetic cohort/demo and authenticated bundle builders, negative and integrity tests. **New:** `research/intake/fixtures/offline_io.v1.json` (29 named I/O pairs using five base requests), `research/intake/offline_fixture_pack.py` (validator/replay), `tests/experiments/test_offline_fixture_pack.py` and this consumer guide. No changes to prior components.

## Replay from repository root

```sh
python -m pip install -r research/uci412/requirements.txt
python -m research.intake.offline_fixture_pack
python -m pytest -q -W error tests/experiments/test_offline_fixture_pack.py
```

After dependency setup the runner needs only CPU and local temporary storage. It validates the canonical pack SHA, rebuilds the fabricated requests, checks live registry, route, panel and crosswalk bindings, builds two disposable authenticated **synthetic-only** bundles, and compares the actual facade projections to the shipped examples. Blocked probes reuse a grammar-valid fabricated record: it is **not** evidence of panel compatibility. They receive a nonexistent bundle location and must stop at registry lookup. No signing material, model or path is part of a fixture.

`bindings` pins the canonical crosswalk, model registry and five descriptor hashes; `requests` pins panel SHA/version and model/route/dataset identity. `cases[].route` selects a base request. In revised pack 1.1.0, apply edits in order to a fresh copy. `{"op":"delete","path":["records",0,"features","trestbps"]}` removes an existing key. `{"op":"set","path":["records",0,"features","trestbps"],"value":null}` keeps the key present with a JSON null; any non-null `value` is assigned as-is. Paths traverse objects by key and arrays by zero-based index; edits end at an object field. The legacy pair syntax is rejected. `expected` is a display projection, **not** an endpoint schema or full facade transcript. The projection deliberately omits explanations, model handles and submission metadata. Exact numerical goldens are for the pinned Linux replay. Other platforms, numerical libraries or dependency versions may differ; a mismatch fails verification, not a reason to relax checks or reinterpret a number clinically.

Canonical pack SHA-256: `0307b396cea1e620c4004647e1d82ff7f292bb5b74de7cad1661e1299c6e7049`. Counts below exclude successes from the refusal column:

| Registered route | Total | Refusals |
|---|---:|---:|
| `da_a2_resting_v1` | 14 | 13 |
| `da_a1_basic_clinical_v1` | 6 | 5 |
| `da_a2_resting_labs_v1` | 3 | 3 |
| `da_a1_clinical_core_labs_v1` | 3 | 3 |
| `da_a2_hungary_locked_transportability_v1` | 3 | 3 |

For each blocked route, the matching binding yields its registered `UNAVAILABLE` reason; a foreign dataset or stale panel SHA instead yields `ERROR` (`dataset_id_mismatch` or `panel_contract_hash_mismatch`). All nine probes stop before artifact access. These are registry precedence examples, not tests of blocked-route scoring or field validity.

## Static Flutter / React demo

Read packaged examples, **never** call a model or `/v1` with a fixture. Keep a persistent **“Synthetic research fixture — not clinical”** banner. Clear previous values and plots before switching cards. The request's route identifies the scenario; do not invent a resolved panel when the facade returns null.

| Status / fixture | What to display |
|---|---|
| `SYNTHETIC_RESULT` · `da_a2_resting_v1`, `da_a1_basic_clinical_v1` | Only the explicitly labelled synthetic research score on its declared scale. Raw is not calibrated; neither is a clinical CAD probability. No risk bands or advice. |
| `ABSTAIN` · `optional`, `optional-null` | “No score: optional measurement missing.” Show the registered missing field/reason: omitted with `not_provided`, or explicitly null with `not_measured`. No imputation or fallback. |
| `UNAVAILABLE` · the three other route IDs | Disabled result card with the registry error code: resting labs pending authorization; clinical-core labs timing unverified; Hungary locked external target. No retry on another route. |
| `ERROR` · e.g. `required`, `wrong-unit`, `Cath` | Show a static refusal message/code from the top-level error or record error. Required fields omitted or explicitly null yield `missing_required_field`. An optional null with a structural reason yields `invalid_missing_reason`; with no reason it yields `missing_reason_mismatch`. These are **errors**, not policy abstentions. Never echo the input or show a score or SHAP/LIME. Unknown status: hide results. |

## Limits and next work

No real inputs, OCR, wearables/Track B, pooled sources, real evaluation, live service or UI. Backend remains `MOCK_SYNTHETIC`. Historical D-047 covers only the original five Cleveland fields; UCI-412 basic owner-verified timing remains 0/16. Scientific holds and source permissions unchanged; AI-9.2/AI-10.2 `NOT_PERFORMED`. No supervisor or serving approval. No native Windows replay or full repository suite in this slice.

RH-04 remains incomplete: RH-04-5 backend mock-contract regression, downstream RH-04-6 screen mapping/review, RH-04-7 report pack and RH-04-8 locked-site ledger rehearsal. RH-05 still needs its reproducibility matrix, per-route rejection matrix, exact-SHA/native replay and skip register, deterministic evidence-pack checksum, Windows checklist and CI proposal. This offline replay is not those deliverables.
