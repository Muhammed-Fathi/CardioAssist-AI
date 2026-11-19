# RH-04.3/4 · offline synthetic fixture handoff v1

Issue #114 returned HTTP 403. This implements the maintainer-supplied fallback, not a claim about the unread issue. Base: PR #113 merge `aa3c9cc39b2d08e077cb0c9873833c4e0b3bc305`.

**Already present:** four panel contracts, five route descriptors and model entries, acquisition-evidence crosswalk 1.1.0, typed offline facade, deterministic response digests, synthetic cohort/demo and authenticated bundle builders, negative and integrity tests. **New:** `research/intake/fixtures/offline_io.v1.json` (19 named I/O pairs using five base requests), `research/intake/offline_fixture_pack.py` (validator/replay), `tests/experiments/test_offline_fixture_pack.py` and this consumer guide. No changes to prior components.

## Replay from repository root

```sh
python -m pip install -r research/uci412/requirements.txt
python -m research.intake.offline_fixture_pack
python -m pytest -q -W error tests/experiments/test_offline_fixture_pack.py
```

After dependency setup the runner needs only CPU and local temporary storage. It validates the canonical pack SHA, rebuilds the fabricated requests, checks live registry, route, panel and crosswalk bindings, builds two disposable authenticated **synthetic-only** bundles, and compares the actual facade projections to the shipped examples. Blocked probes reuse a grammar-valid fabricated record: it is **not** evidence of panel compatibility. They receive a nonexistent bundle location and must stop at registry lookup. No signing material, model or path is part of a fixture.

`bindings` pins the canonical crosswalk, model registry and five descriptor hashes; `requests` pins panel SHA/version and model/route/dataset identity. `cases[].route` selects a base request. Apply each `[path, value]` edit in order to a fresh copy: a null edit value deletes a key; it is not a submitted JSON null. `expected` is a display projection, **not** an endpoint schema or full facade transcript. The projection deliberately omits explanations, model handles and submission metadata. Exact numerical goldens are for the pinned Linux replay, not portable clinical thresholds.

## Static Flutter / React demo

Read packaged examples, **never** call a model or `/v1` with a fixture. Keep a persistent **“Synthetic research fixture — not clinical”** banner. Clear previous values and plots before switching cards. The request's route identifies the scenario; do not invent a resolved panel when the facade returns null.

| Status / fixture | What to display |
|---|---|
| `SYNTHETIC_RESULT` · `da_a2_resting_v1`, `da_a1_basic_clinical_v1` | Only the explicitly labelled synthetic research score on its declared scale. Raw is not calibrated; neither is a clinical CAD probability. No risk bands or advice. |
| `ABSTAIN` · `optional` | “No score: optional measurement missing.” Show the registered missing field/reason. No imputation or fallback. |
| `UNAVAILABLE` · the three other route IDs | Disabled result card with the registry error code: resting labs pending authorization; clinical-core labs timing unverified; Hungary locked external target. No retry on another route. |
| `ERROR` · e.g. `required`, `wrong-unit`, `Cath` | Show a static refusal message/code from the top-level error or record error. Missing required fields are **errors**, not policy abstentions. Never echo the input or show a score or SHAP/LIME. Unknown status: hide results. |

## Limits and next work

No real inputs, OCR, wearables/Track B, pooled sources, real evaluation, live service or UI. Backend remains `MOCK_SYNTHETIC`. Historical D-047 covers only the original five Cleveland fields; UCI-412 basic owner-verified timing remains 0/16. Scientific holds and source permissions unchanged; AI-9.2/AI-10.2 `NOT_PERFORMED`. No supervisor or serving approval. No native Windows replay or full repository suite in this slice.

RH-04 remains incomplete: RH-04-5 backend mock-contract regression, downstream RH-04-6 screen mapping/review, RH-04-7 report pack and RH-04-8 locked-site ledger rehearsal. RH-05 still needs its reproducibility matrix, per-route rejection matrix, exact-SHA/native replay and skip register, deterministic evidence-pack checksum, Windows checklist and CI proposal. This offline replay is not those deliverables.
