# Internal model-provider boundary and offline artifact admission (M1c)

**Status: engineering foundation only — RESEARCH_ONLY.**
No trained model, real inference, dataset access, clinical threshold, medical
claim or serving authorization exists in this change. CAD scoring remains
deterministic `MOCK_SYNTHETIC` fixture arithmetic; Track B monitoring is
untouched.

| Report label | Content |
|---|---|
| **IMPLEMENTED** | A narrowly typed internal CAD inference provider boundary with exactly one constructible implementation (`MOCK_SYNTHETIC`); a fail-closed placeholder for a future reviewed real provider; a versioned offline research-artifact descriptor plus a validator that enforces an explicit ordered feature binding, verifies calibration bytes, and always returns `RESEARCH_ONLY`. |
| **TESTED** | `tests/backend/test_inference_provider.py` (33 tests) and `tests/backend/test_model_artifact_admission.py` (177 tests), plus the unchanged 371 existing backend regression tests and the 249 contract tests. Synthetic, non-clinical fixtures only. Local result for this checkout: `tests/backend` **581 passed**, `tests/contracts` **249 passed**, full suite **1099 passed**. |
| **RATIFIED (2026-10-24)** | The human maintainer approved M1c as a narrowly scoped engineering milestone (provider boundary, offline `RESEARCH_ONLY` admission, synthetic order/calibration tests). Recorded in `AGENTS.md` §7; real inference, training, dataset access, clinical deployment, genuine SHAP/LIME, the approved contracts and P-1/P-3/P-5/D-046/D-047 remain unauthorized and unchanged. |
| **NOT IMPLEMENTED / UNAVAILABLE** | Real inference, artifact loading/deserialization, model fitting or tuning, dataset access, real calibration, thresholds, patient-facing score interpretation, serving eligibility, genuine TreeSHAP/LIME, an approved research feature-binding for the five Cleveland predictors, authentication, new endpoints, UI, clinical claims. |
| **UNVERIFIED** | Windows-local behavior, any future artifact's scientific/clinical validity, and any supervisor, ethics or institutional approval. Nothing here is external validation. CI results are reported by the PR checks, not by this document. |

## 1. What the admission boundary does — and does not — cover

The provider abstraction is **implemented and testable**. The offline admission
implementation is usable **only for the descriptors it explicitly supports**:
artifacts whose feature contract is expressed in the current *mock fixture*
feature schemas and bound to the registered synthetic admission order.

It is **not yet a scientifically approved bridge** to the Cleveland D-047
research pipeline:

* the mock feature ids (`mock_feature_demographic_age`, …) are placeholders and
  are **not** the five prespecified D-047 predictor columns
  (`age, sex, cp, trestbps, restecg`);
* `synthetic_fixture_input_order/v1` is a **synthetic-only** ordering policy; it
  carries no clinical semantics and must never be reused as the research input
  order;
* the D-047 predictor order and its feature-to-position mapping must come from
  that protocol's reviewed research registry, which does not exist yet;
* a real artifact packaging protocol (container, preprocessing serialization,
  calibration representation, provenance binding) remains future work.

Still outstanding before any research-only artifact could ever be considered
for serving: an approved research feature-binding mapping, a real packaging and
provenance protocol, independent scientific review, and a separate serving
authorization. **No research-only artifact may be served**, and this release
contains no code path that could serve one.

## 2. Provider boundary (`backend/app/inference/`)

| Module | Purpose |
|---|---|
| `types.py` | `CadInferenceRequest`, `CadFeature`, `CadModelBinding`, abstract `CadInferenceProvider`. No contract object, database handle, patient record or extra lookup surface is passed to a provider. |
| `mock_synthetic.py` | `MockSyntheticProvider` adapts the typed request onto the unchanged approved fixture arithmetic in `mock_prediction.py` (byte-identical output). |
| `real_model.py` | `FailClosedRealModelProvider` — a deliberate refusal. Constructor and `predict` always raise `RealModelServingNotAuthorized`; no instance can exist, be stored in application state or be reached from the factory. |
| `registry.py` | `build_active_provider(contracts)` — the only construction site. `ACTIVE_PROVIDER_IDS == {"mock_synthetic"}` is enforced, and the result must have `data_class == "MOCK_SYNTHETIC"` and `supports_real_predictions is False`. |

Deliberate absences (each enforced by a test): no `provider`/`model` parameter on
`create_app`/`MockState`; no environment variable, settings file, request field
or database value that selects a provider; no import of `pickle`, `joblib`,
`sklearn`, `numpy`, `torch`, `onnxruntime`, `safetensors`, `shap`, `lime`, any
HTTP client, `socket`, `subprocess` or `os` in the inference package; the
runtime never imports the offline admission package; runtime state no longer
calls the mock arithmetic directly.

Track separation is unchanged and re-tested: monitoring requests never invoke a
provider, `inference_count` stays `0` for Track B, only CAD audit events carry a
`model_id`, and wearable sources or wearable field names are rejected with
`422 wearable_input_not_valid_for_cad_inference` before any provider call.

Externally observable behavior is unchanged: fixture responses (including F-01,
F-03, F-08, F-11b, F-12), status codes, idempotency replay/conflict semantics,
24-hour process-local retention, error bodies, SHAP-shaped synthetic output,
response-schema validation and monitoring persistence all still pass their
original assertions.

## 3. Offline artifact admission (`backend/app/artifact_admission/`)

Offline API — not a route, not a startup hook:

```python
from backend.app.artifact_admission import (
    AdmissionPolicy, DirectoryArtifactSource, SYNTHETIC_FIXTURE_INPUT_ORDER,
    admit_research_artifact,
)

decision = admit_research_artifact(
    descriptor,
    source=DirectoryArtifactSource(package_root),   # bytes only; never deserialized
    policy=AdmissionPolicy.from_shared_contracts(
        registered_targets={"<target_id>": "<exact registered definition text>"},
        input_order_policy=SYNTHETIC_FIXTURE_INPUT_ORDER,   # omit -> fails closed
    ),
)
assert decision.serving_eligibility == "RESEARCH_ONLY"      # always
assert decision.approved_for_serving is False               # always
```

### 3.1 Descriptor (`artifact_descriptor/v1`)

`artifact_descriptor.v1.schema.json` (Draft 2020-12, `additionalProperties:
false`) requires and describes:

| Section | Declared content |
|---|---|
| `artifact` | artifact id + semantic version, container type, relative reference, SHA-256, byte size, preprocessing reference and SHA-256. |
| `model` | research model family, preprocessing version, declared `score_type`, calibration status **and representation** (+ reference, SHA-256 and size for a separate calibration artifact), explainability method and capability. |
| `feature_contract` | pinned shared `feature_schema_id`, SHA-256 of that schema file, **`order_policy_id`**, and the ordered feature list with name, order, value type, unit and required flag. |
| `target` | registered target id, SHA-256 of its exact definition, declared prediction timepoint, source cohort and dataset ids, `pooled_cohorts` (must be false). |
| `provenance` | protocol id, relative protocol reference + SHA-256, experiment id, code commit, generation timestamp. |
| `eligibility` | `research_label` and `serving_status` (`RESEARCH_ONLY` or the future `APPROVED_FOR_SERVING`, which is rejected). |

There is **no second clinical feature dictionary**: names, value types, units and
required flags are read from the approved `shared/contracts/schemas` files via
`backend.app.validation.feature_rules`.

### 3.2 Ordered feature binding (`feature_order.py`)

Input order is a contract, not an accident of serialization.

* The approved order lives in code as `synthetic_fixture_input_order/v1`
  (`SYNTHETIC_ONLY_NOT_CLINICAL`), reviewed like any other source.
* Admission checks **position by position**: the descriptor feature at index *i*
  must equal the policy feature at index *i*. Swapping the order numbers of two
  otherwise valid features is rejected (`feature_position_binding_mismatch`)
  even though the index set remains contiguous `0..n-1`.
* Duplicate, missing, negative or out-of-range indices are rejected
  (`feature_order_mismatch`, or `descriptor_schema_invalid` for negative values).
* JSON Schema object property order is **never** used as an input order. A test
  proves this: `mock_clinical_v2` declares `mock_feature_fraction` third but the
  binding places it last — the policy order is admitted and the serialization
  order is refused. Another test shuffles the schema's `properties` mapping and
  shows that no admitted position moves.
* A schema with no registered order fails closed (`feature_order_unregistered`);
  a missing policy fails closed (`feature_order_policy_missing`); an
  unregistered `order_policy_id` (`feature_order_policy_unknown`) or a policy id
  different from the active one (`feature_order_policy_mismatch`) is rejected.

**Registration identity, not just the id string.** The active
`AdmissionPolicy.input_order_policy` must be the registered, code-reviewed
definition. Admission resolves `policy_id` in the read-only registry and
compares **every** registered field — policy id, status, note and the full
schema→order mapping, including the exact name tuple per schema and the exact
set of covered schemas:

| Caller-supplied active policy | Result |
|---|---|
| the registered object, or a faithful reconstruction of it | admitted |
| same registered id, different feature ordering | `feature_order_policy_tampered` |
| same registered id, different status or note | `feature_order_policy_tampered` |
| same registered id, added/removed/renamed schema coverage or shortened order | `feature_order_policy_tampered` |
| a policy id that is not registered at all | `feature_order_policy_not_registered` |

The comparison also reads the admitted order from the **registered** object, so
even a descriptor built around an impostor's ordering cannot be admitted.

**Immutability of the registered definition.** `FeatureOrderPolicy` is a
`frozen=True, slots=True` dataclass whose mapping is copied into a
`MappingProxyType` with tuple values at construction, and
`REGISTERED_FEATURE_ORDER_POLICIES` is itself a `MappingProxyType`. Therefore:

* item assignment, `del`, `update` and `clear` on the order mapping raise;
* the order tuples are immutable;
* field reassignment raises `FrozenInstanceError` and adding new state is
  impossible;
* the registry rejects insertions, replacements and deletions at runtime;
* mutating the caller's original dictionary afterwards cannot change an
  existing policy instance.

`dataclasses.replace(...)` still produces a new object, but it is rejected at
admission unless it reproduces the registered definition exactly. (As with any
Python frozen dataclass, `object.__setattr__` remains an in-process escape hatch;
the guarantees are about the declared API, not about defending a process from
itself.)

### 3.3 Calibration integrity

A declared calibration hash is only accepted when the corresponding **bytes**
were read through the artifact source and hashed:

| Status | Representation | Behaviour |
|---|---|---|
| `calibrated` | `separate_artifact` | `calibration_ref`, `calibration_sha256` and `calibration_size_bytes` are all required; bytes are read, size compared and SHA-256 recomputed. Missing file, altered bytes, size or hash mismatch, unsafe reference, symlink, or reuse of another verified reference is rejected. |
| `calibrated` | `embedded_in_verified_artifact` | Admitted **only as an unverified claim**: no separate hash/ref may be asserted, nothing inside the model container is opened, and the decision records `calibration_integrity = EMBEDDED_NOT_INDEPENDENTLY_VERIFIED` plus an explicit non-approval reason. |
| `calibrated` | `none` | Rejected (`calibration_integrity_missing`). |
| `uncalibrated` / `not_assessed` | any non-`none` representation, or any calibration field set | Rejected (`calibration_reference_unexpected`). |

A syntactically valid 64-hex digest therefore no longer qualifies on its own.

### 3.4 Explainability claims

Genuine TreeSHAP/LIME is **not implemented or verified anywhere in this
repository**: `backend/app/mock_prediction.py` computes a deterministic
SHAP-*shaped* synthetic offset from a hash of the feature value, and no `shap`
or `lime` dependency or computation exists under `backend/`, `research/` or
`scripts/` (a regression test scans imports and requirement pins). The
capability vocabulary is therefore:

| Method | Required capability |
|---|---|
| `tree_shap` | `mock_shap_shaped_fixture_only` |
| `lime` | `not_implemented` |
| `none` | `not_implemented` |

A descriptor asserting `implemented_and_verified_in_research_harness` is
rejected with `explainability_claim_unsupported`, because no such
implementation exists. This milestone computes no SHAP or LIME value, and the
existing HTTP mock explanation fixtures are preserved unchanged (F-08 asserted
verbatim, including `explanation.synthetic == true`).

### 3.5 Rejection codes

Every rejection is an `ArtifactAdmissionError` with a stable `code` and a field
path **only** — descriptor values, hashes, artifact bytes, feature values and
registered definition text are never echoed, and nothing is logged.

| Group | Codes |
|---|---|
| Structure | `malformed_descriptor`, `descriptor_schema_invalid` |
| Eligibility | `self_declared_serving_status_not_permitted`, `unsupported_research_label` |
| Model | `unexpected_model_family`, `score_interpretation_mismatch`, `calibration_integrity_missing`, `calibration_reference_missing`, `calibration_reference_unexpected`, `calibration_reference_conflict`, `calibration_size_mismatch`, `calibration_sha256_mismatch`, `explainability_claim_unsupported`, `explainability_capability_mismatch` |
| Features / order | `unknown_feature_schema`, `feature_schema_digest_mismatch`, `duplicate_feature`, `feature_set_mismatch`, `feature_order_policy_missing`, `feature_order_policy_unknown`, `feature_order_policy_mismatch`, `feature_order_policy_not_registered`, `feature_order_policy_tampered`, `feature_order_unregistered`, `feature_order_mismatch`, `feature_position_binding_mismatch`, `feature_unit_mismatch`, `feature_type_mismatch`, `feature_required_mismatch`, `feature_schema_unsupported` |
| Target | `unknown_target`, `target_definition_mismatch`, `cohort_pooling_not_admitted` |
| Bytes / sources | `artifact_type_reference_mismatch`, `artifact_missing`, `artifact_empty`, `artifact_too_large`, `artifact_reference_invalid`, `artifact_symlink_not_permitted`, `artifact_size_mismatch`, `artifact_sha256_mismatch`, `preprocessing_sha256_mismatch`, `protocol_sha256_mismatch` |

Semantics worth stating explicitly:

* **`RESEARCH_ONLY` is not a serving status.** `serving_eligibility` and
  `approved_for_serving` are read-only properties, so no decision object can
  represent approval, and `dataclasses.replace` cannot create one.
* **Checksums are integrity only** — never calibration adequacy, scientific
  validity or clinical approval. Every decision carries explicit non-approval
  reasons, including `genuine_treeshap_or_lime_not_implemented_in_repository`
  and `feature_order_policy_is_synthetic_mock_fixture_scope_only`.
* **D-047 stays internal exploratory**: a descriptor labelled
  `INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED` is admitted for research tooling
  only and records `d047_internal_exploratory_run_is_not_a_deployable_model`.
* **No deserialization**: artifacts are hashed as raw bytes; a synthetic pickle
  fixture proves admission completes while `pickle.load`/`loads` are patched to
  fail. Container suffixes are consistency checks only.
* **No data-exfiltration surface**: `DirectoryArtifactSource` refuses absolute
  paths, `..`, empty segments, backslashes, symlinked components, directories,
  empty files and files above 512 MiB, and resolves every reference inside its
  root. `InMemoryArtifactSource` is for tests and offline harnesses.

### 3.6 Template

`docs/model-admission/artifact_descriptor.template.json` is a blank,
clearly-fake template (`REPLACE_WITH_…` placeholders). It is intentionally
**invalid** until completed by a human; completing it successfully still yields
`RESEARCH_ONLY`.

## 4. What remains explicitly unavailable

* Any real CAD prediction, model artifact, training, tuning, real calibration or
  threshold selection; P-1 and P-3 are unchanged (`PENDING`/`CLOSED`).
* Genuine TreeSHAP or LIME computation.
* An approved research feature-binding mapping for the five D-047 Cleveland
  predictors, and a real artifact packaging/provenance protocol.
* Any dataset read or download, including the already-audited Cleveland local
  data; no local experiment output or manifest is touched by this change.
* Any promotion path from a research descriptor to serving: no environment
  variable, request field, registry entry, API route or admission outcome
  activates one.
* Any clinical, publication, novelty, external-validation or accuracy claim, and
  any patient-facing use.
* Authentication/RBAC, new endpoints, UI work, wearables and OpenAPI changes
  (the approved contract files are untouched).

## 5. Running the checks

```bash
python -m pip install -r backend/requirements-dev.txt
python -m pytest tests/backend -q -W error     # 581 tests
python -m pytest tests/contracts -q            # 249 tests
python -m pytest -q -W error                   # full repository suite
git diff --check
python scripts/verify_sources.py
```

## 6. Limitations

* `MockSyntheticProvider` is an adapter; it is not evidence that a real
  inference path exists or would be safe.
* `FailClosedRealModelProvider` documents a refusal, not an implementation
  plan; it commits to no model family, preprocessing, threshold or output
  interpretation.
* Admission validates declarations, ordering and byte integrity — not the
  correctness of a timepoint, cohort representativeness, calibration adequacy or
  fairness. Those remain human/scientific review items.
* `synthetic_fixture_input_order/v1` is mock-scope only and is not a clinical
  ordering; a research pipeline needs its own reviewed registry.
* The 512 MiB size cap and the suffix/type map are engineering guards, not a
  security boundary against a malicious local operator.
* A local pass is not a CI result, and neither is a scientific approval.

## 7. Governance and authorization boundary

The implementation in this PR does **not** modify `docs/DECISIONS.md`, the Gate
PT records, P-1, P-3, P-5, D-046 or D-047, and it does not alter the `/v1`
contracts. The only governance change accompanying it is the maintainer's
ratification of M1c, recorded in `AGENTS.md`; no decision id was added and no
register entry was edited. The completed D-047 Cleveland run is treated strictly
as internal exploratory evidence, never as a deployable model.

The historical "Current authorization: M1b.1 only" paragraph in `AGENTS.md` is
retained verbatim. On **2026-10-24** the human maintainer explicitly ratified
**M1c as a narrowly scoped engineering milestone**: the `MOCK_SYNTHETIC`-only
provider boundary, the offline `RESEARCH_ONLY` admission validator, and the
synthetic feature-order, calibration-integrity and regression tests. That
ratification is recorded in the `AGENTS.md` M1c section; this document does not
grant it.

Its limits are unchanged and binding: no real model inference, no training or
calibration, no patient-dataset access, no clinical deployment, no genuine
SHAP/LIME computation, no change to P-1 (pending), P-3 (closed), P-5
(prohibited), D-046 (read-only audit), D-047 (Cleveland-only internal
exploratory) or the approved `/v1` contracts. No research-only artifact may be
served, and an independently reviewed research feature-binding mapping plus a
real artifact packaging/provenance protocol remain future work under their own
authorization.

Merging is still a separate human action; the agent neither approves nor merges
the PR.
