# Internal model-provider boundary and offline artifact admission (M1c)

**Status: engineering foundation only — RESEARCH_ONLY.**
No trained model, real inference, dataset access, clinical threshold, medical
claim or serving authorization exists in this change. CAD scoring remains
deterministic `MOCK_SYNTHETIC` fixture arithmetic; Track B monitoring is
untouched.

| Report label | Content |
|---|---|
| **IMPLEMENTED** | A narrowly typed internal CAD inference provider boundary with exactly one constructible implementation (`MOCK_SYNTHETIC`); a fail-closed placeholder for a future reviewed real provider; a versioned offline research-artifact descriptor plus a byte-only validator that always returns `RESEARCH_ONLY`. |
| **TESTED** | `tests/backend/test_inference_provider.py` (31 tests) and `tests/backend/test_model_artifact_admission.py` (91 tests), plus the unchanged 371 existing backend regression tests and the 249 contract tests. Local full-suite result for this checkout: **1011 passed**; synthetic, non-clinical fixtures only. |
| **PROPOSED / NOT APPLIED** | A minimal `AGENTS.md` authorization sentence (§7 below) so the next review records this engineering slice explicitly. No decision register entry was edited. |
| **NOT IMPLEMENTED / UNAVAILABLE** | Real inference, artifact loading/deserialization, model fitting or tuning, dataset access, calibration, thresholds, score interpretation for patients, serving eligibility, authentication, new endpoints, UI, clinical claims. |
| **UNVERIFIED** | GitHub CI result for this PR, Windows-local behavior, any scientific/clinical validity of a future artifact, and any supervisor, ethics or institutional approval. Nothing here is an external validation. |

## 1. Why this exists

The repository can already accept a `/v1/predictions/cad-tabular` request, but
the CAD scoring call was inlined in runtime state and there was no mechanism to
decide whether a future research model package may be opened at all. This
milestone adds the two smallest pieces needed for a later, separately reviewed
model artifact:

1. **Provider boundary** — one typed internal interface with a single allowed
   implementation, so a future reviewed real provider can be added without
   re-architecting the backend.
2. **Offline admission** — a versioned descriptor and validator so a research
   package can be scope- and integrity-checked without ever being loaded.

Neither piece can serve a patient-facing prediction.

## 2. Provider boundary (`backend/app/inference/`)

| Module | Purpose |
|---|---|
| `types.py` | `CadInferenceRequest`, `CadFeature`, `CadModelBinding`, abstract `CadInferenceProvider`. No contract object, database handle, patient record or extra lookup surface is passed to a provider. |
| `mock_synthetic.py` | `MockSyntheticProvider` adapts the typed request onto the unchanged, approved fixture arithmetic in `mock_prediction.py` (byte-identical output). |
| `real_model.py` | `FailClosedRealModelProvider` — a deliberate refusal. Its constructor and `predict` always raise `RealModelServingNotAuthorized`; no instance can exist, be stored in application state or be reached from the factory. |
| `registry.py` | `build_active_provider(contracts)` — the only construction site. `ACTIVE_PROVIDER_IDS == {"mock_synthetic"}` is enforced, and the result must have `data_class == "MOCK_SYNTHETIC"` and `supports_real_predictions is False`. |

Deliberate absences (each enforced by a test):

* no `provider`/`model` parameter on `create_app` or `MockState`;
* no environment variable, settings file, request field or database value that
  selects a provider (`CARDIOASSIST_MODEL_PROVIDER`, `MODEL_PATH`, … are ignored);
* no import of `pickle`, `joblib`, `sklearn`, `numpy`, `torch`, `onnxruntime`,
  `safetensors`, any HTTP client, `socket`, `subprocess` or `os` in the
  inference package;
* the runtime never imports the offline admission package (verified in a
  subprocess import probe);
* runtime state no longer calls the mock arithmetic directly.

Track separation is unchanged and re-tested: monitoring requests never invoke a
provider, `inference_count` stays `0` for Track B, CAD audit events are the only
ones carrying a `model_id`, and wearable sources or wearable field names are
rejected with `422 wearable_input_not_valid_for_cad_inference` before any
provider call.

Externally observable behavior is unchanged: the fixture pack responses
(including F-01, F-03, F-11b and F-12), status codes, idempotency replay/conflict
semantics, 24-hour process-local retention, error bodies, SHAP-shaped synthetic
output, response-schema validation and monitoring persistence all still pass
their original assertions.

## 3. Offline artifact admission (`backend/app/artifact_admission/`)

Offline API — not a route, not a startup hook:

```python
from backend.app.artifact_admission import (
    AdmissionPolicy, DirectoryArtifactSource, admit_research_artifact,
)

decision = admit_research_artifact(
    descriptor,                                  # artifact_descriptor/v1 mapping
    source=DirectoryArtifactSource(package_root),  # bytes only; never deserialized
    policy=AdmissionPolicy.from_shared_contracts(
        registered_targets={"<target_id>": "<exact registered definition text>"}
    ),
)
assert decision.serving_eligibility == "RESEARCH_ONLY"   # always
assert decision.approved_for_serving is False            # always
```

### 3.1 Descriptor (`artifact_descriptor/v1`)

`artifact_descriptor.v1.schema.json` (Draft 2020-12, `additionalProperties:
false`) requires and describes:

| Section | Declared content |
|---|---|
| `artifact` | artifact id + semantic version, container type, relative reference, SHA-256, byte size, preprocessing reference and SHA-256. |
| `model` | research model family, preprocessing version, declared `score_type`, calibration status (+ pinned calibration hash when calibrated), explainability method and capability. |
| `feature_contract` | pinned shared `feature_schema_id`, SHA-256 of that schema file, and the ordered feature list with name, order, value type, unit and required flag. |
| `target` | registered target id, SHA-256 of its exact definition, declared prediction timepoint, source cohort and dataset ids, `pooled_cohorts` (must be false). |
| `provenance` | protocol id, relative protocol reference + SHA-256, experiment id, code commit, generation timestamp. |
| `eligibility` | `research_label` and `serving_status` (`RESEARCH_ONLY` or the future `APPROVED_FOR_SERVING`, which is rejected). |

There is **no second clinical feature dictionary**: names, value types, units and
required flags are read from the approved `shared/contracts/schemas` files via
`backend.app.validation.feature_rules`, and a descriptor that changes any of
them is refused.

### 3.2 Checks and rejection codes

Every rejection is an `ArtifactAdmissionError` with a stable `code` and a field
path **only** — descriptor values, hashes, artifact bytes, feature values and
registered definition text are never echoed, and nothing is logged.

| Group | Codes |
|---|---|
| Structure | `malformed_descriptor`, `descriptor_schema_invalid` (missing/unknown field, wrong type/format, unknown `descriptor_schema_version`) |
| Eligibility | `self_declared_serving_status_not_permitted`, `unsupported_research_label` |
| Model | `unexpected_model_family`, `score_interpretation_mismatch`, `calibration_reference_missing`, `calibration_reference_unexpected`, `explainability_capability_mismatch` |
| Features | `unknown_feature_schema`, `feature_schema_digest_mismatch`, `duplicate_feature`, `feature_set_mismatch`, `feature_order_mismatch`, `feature_unit_mismatch`, `feature_type_mismatch`, `feature_required_mismatch`, `feature_schema_unsupported` |
| Target | `unknown_target`, `target_definition_mismatch`, `cohort_pooling_not_admitted` |
| Bytes | `artifact_type_reference_mismatch`, `artifact_missing`, `artifact_empty`, `artifact_too_large`, `artifact_reference_invalid`, `artifact_symlink_not_permitted`, `artifact_size_mismatch`, `artifact_sha256_mismatch`, `preprocessing_sha256_mismatch`, `protocol_sha256_mismatch` |

Semantics worth stating explicitly:

* **`RESEARCH_ONLY` is not a serving status.** Admission reports
  `serving_eligibility` and `approved_for_serving` as read-only properties, so no
  decision object can represent approval; `dataclasses.replace` cannot create one
  either.
* **Checksums are integrity only.** A matching SHA-256 does not imply
  calibration adequacy, scientific validity or clinical approval; every decision
  carries explicit non-approval reasons.
* **D-047 stays internal exploratory.** A descriptor labelled
  `INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED` is admitted for research tooling
  only, and its decision records
  `d047_internal_exploratory_run_is_not_a_deployable_model`.
* **No deserialization.** Artifacts are hashed as raw bytes; a synthetic pickle
  fixture proves admission completes while `pickle.load`/`pickle.loads` are
  patched to fail. Container suffixes are consistency checks only.
* **No data exfiltration surface.** `DirectoryArtifactSource` refuses absolute
  paths, `..`, empty segments, backslashes, symlinked components, directories,
  empty files and files above 512 MiB, and resolves every reference inside its
  root. `InMemoryArtifactSource` is for tests and offline harnesses.

### 3.3 Template

`docs/model-admission/artifact_descriptor.template.json` is a blank,
clearly-fake template (`REPLACE_WITH_…` placeholders). It is intentionally
**invalid** until completed by a human; completing it successfully still yields
`RESEARCH_ONLY`.

## 4. What remains explicitly unavailable

* Any real CAD prediction, model artifact, training, tuning, calibration or
  threshold selection; P-1 and P-3 are unchanged (`PENDING`/`CLOSED`).
* Any dataset read or download, including the already-audited Cleveland local
  data; no local experiment output or manifest is touched by this change.
* Any promotion path from a research descriptor to serving: there is no
  environment variable, request field, registry entry, API route or admission
  outcome that activates one.
* Any clinical, publication, novelty, external-validation or accuracy claim, and
  any patient-facing use.
* Authentication/RBAC, new endpoints, UI work, wearables and OpenAPI changes
  (the approved contract files are untouched).

## 5. Running the checks

```bash
python -m pip install -r backend/requirements-dev.txt
python -m pytest tests/backend -q -W error     # 493 tests
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
* Admission validates declarations and integrity, not correctness of a
  timepoint, cohort representativeness, calibration or fairness. Those remain
  human/scientific review items.
* The 512 MiB size cap and the suffix/type map are engineering guards, not a
  security boundary against a malicious local operator.
* CI status for this PR is recorded by the PR checks; a local pass is not a CI
  result, and neither is a scientific approval.

## 7. Governance and authorization boundary

This change does **not** modify `docs/DECISIONS.md`, `AGENTS.md`, the Gate PT
records, P-1, P-3, P-5, D-046 or D-047, and it does not alter the `/v1`
contracts. The completed D-047 Cleveland run is treated strictly as internal
exploratory evidence, never as a deployable model.

The repository's `AGENTS.md` still records "Current authorization: M1b.1 only".
The actual authority for this slice is the maintainer's active milestone
instruction (AGENTS.md priority 1), not that historical paragraph. So that the
code and the governance text stop disagreeing, the smallest reviewable amendment
would be to append one sentence to the AGENTS.md authorization section — shown
here as text only, **not applied**, and requiring the maintainer's own decision:

> **PROPOSED (NOT APPLIED) — M1c authorization:** Under maintainer instruction
> dated 2026-10-23, agents may implement and test (a) an internal CAD inference
> provider boundary whose only constructible implementation is `MOCK_SYNTHETIC`
> and (b) an offline, fail-closed research-artifact descriptor/validator that
> always reports `RESEARCH_ONLY`. This does not authorize real inference, model
> fitting, dataset access, artifact activation, contract changes, or any
> clinical/scientific claim, and it changes no gate (P-1/P-3/P-5, D-046, D-047).
