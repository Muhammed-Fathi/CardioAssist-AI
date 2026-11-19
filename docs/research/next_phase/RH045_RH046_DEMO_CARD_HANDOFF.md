# RH-04.5 / RH-04.6 · offline-boundary and demo-card handoff

This handoff implements the Issue #116 fallback scope after GitHub Issue access
returned HTTP 403. It is an implementation slice, not a research report and
not an authorization change.

## Machine-readable consumer contract

The consumer source of truth is
`research/intake/fixtures/offline_demo_cards.v1.json`, validated by
`research.intake.offline_demo_card_mapping`. The validator binds **all 29**
reviewed examples from the offline fixture pack using per-case canonical
expected-projection hashes. It also fails closed if its source digests no longer
match the fixture pack, frozen registry/crosswalk bindings, mock OpenAPI,
approved mock fixture index/model registry, or the selected approved F-01 mock
fixture example.

```sh
python -m research.intake.offline_demo_card_mapping
python -m pytest -q -W error \
  tests/experiments/test_offline_demo_card_mapping.py \
  tests/backend/test_offline_research_boundary.py
```

It is standard-library-only and imports neither the backend nor `ai`; backend
CI therefore receives no research/ML dependency. The established experiment
fixture replay remains the executable proof that the source pack matches the
offline facade.

| Bound source | SHA-256 binding |
|---|---|
| Offline pack canonical projection | `0307b396cea1e620c4004647e1d82ff7f292bb5b74de7cad1661e1299c6e7049` |
| Offline pack bytes | `206418e5f15787c5048c1ebad86d107e40ad4dfcbf727feb6b08ed305e273ab9` |
| Offline registry binding | `e423882d21cf74a42a8270d5d3e929a1b0f346a7ff4ef69bbf8c0e3dc5b2fec7` |
| Offline crosswalk binding | `1c79195261c40ffc212d384c64b3645a2ef563f39b3b5b240a5a906c108abda7` |
| Approved mock OpenAPI bytes | `2748ab7e09771d5ad1793d09d17d1ecef46be7ded930f5530109889ab65f567a` |
| Approved mock fixture-index bytes | `4c6cd73f3746970b9c0230b15d8b96b44b58d31b52e365e5c379f3f96fd71ada` |
| Approved mock model-registry bytes | `65f711e3b8a34148db68b30d17e21f6a8fbebfcd4835a6aff488d58f50f2b552` |
| Approved static F-01 mock-fixture bytes | `37024d7970a8214fe9d318eba4a785f5ee182a912e0229c72469392d0cbfb571` |

## Required consumer behavior

A persistent **“Synthetic research fixture — not clinical”** warning is
required on every card. The JSON mapping is deliberately allowlist-based:
consumer code may show only its listed fields. It cannot add a raw submitted
feature, patient/record identifier, local location, artifact/signing material,
raw score/log-odds, clinical risk percentage, medical advice, or performance
claim.

| Offline status | Safe label and behavior |
|---|---|
| `SYNTHETIC_RESULT` | **Synthetic research result.** A calibrated research score can appear only as a neutral decimal with its research-only interpretation; no percent, risk band, prognosis, or advice. |
| `ABSTAIN` | **No synthetic research score.** Disable the value and show the registered missing-field reason; do not impute, retry, or fall back. This remains distinct from `ERROR`. |
| `UNAVAILABLE` | **Synthetic research route unavailable.** Render a disabled card with the registered refusal code; do not switch route, load an artifact, or retry. |
| `ERROR` | **Synthetic research fixture refused.** Clear prior values and show only the static registered refusal code/message; never echo request or exception detail. |

The mapping encodes the different optional-null rules rather than letting a UI
collapse them: mock HTTP treats an optional null like omission, while the
offline pack retains `not_provided` for omission and `not_measured` for an
explicit null. Both are visible only as the allowlisted missing-field reason on
an `ABSTAIN` card.

## Separate mock backend presentation

`MOCK_SYNTHETIC` is a **fifth, separate** card presentation named
`approved_mock_http_v1`, bound only to `POST /v1/predictions/cad-tabular` in the
existing approved mock HTTP contract. It selects exactly the approved
**static-display-only** F-01 example:

- fixture ID `F-01`, file `F-01-cad-tabular-valid-mock-clinical-v1.json`
- endpoint `POST /v1/predictions/cad-tabular`, expected HTTP status `200`
- model `mock_model_a_v0.1.0`, feature schema `mock_clinical_v1`, data class
  `MOCK_SYNTHETIC`

A frontend can package that selected response as a deterministic **static mock
example only** after validating the mapping; it must not submit the fixture
request, invoke a route, or use it as a prediction. No offline fixture case can
select it. Its allowlist keeps the mock data class, mock model/schema identity,
safe rendering metadata, missing-feature/warning labels, review state,
dataset-access status, and disclaimer—but never a submitted feature,
patient/reference field, explanation, artifact hash, score value, risk
percentage, raw model output, or clinical probability.

## Boundary coverage and limits

The new backend bridge tests prove the five registry-bound offline model IDs
are `unknown_model` through mock CAD; all offline request and response
structures are malformed for the `/v1` mock wire contract; mock OpenAPI paths,
fixture replay, Track A/Track B isolation, idempotency, and the single
`MOCK_SYNTHETIC` provider survive those attempts; and no offline artifact,
signing material, model loader, or real scoring endpoint is reachable.

Nothing here changes backend code, OpenAPI, routes, models, panels, crosswalk,
protocols, approvals, database, frontend, or workflows. D-047 remains
historical Cleveland five-field scope only; UCI-412 owner-verified
pre-angiography timing remains 0/16; scientific holds remain; and AI-9.2 /
AI-10.2 remain `NOT_PERFORMED`. No real-data processing, clinical inference,
performance validation, deployment, or medical advice is enabled.
