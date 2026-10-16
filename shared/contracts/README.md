# CardioAssist AI — `/v1` API contract and MOCK fixture pack (M1a.1)

> **STATUS: PROPOSED — NOT APPROVED, NOT DEPLOYED.**
> This is the M1a.1 deliverable of D-043 ("versioned API contracts, deterministic
> mock CAD/XAI responses, contract tests"). Human review is required before any
> of it is treated as a frozen contract.
>
> **MOCK / SYNTHETIC DATA.** Every example, fixture and mock response in this
> package is synthetic and deterministic. They are **not** medical diagnoses,
> **not** real patient risk, and **not** validated clinical outputs. No model
> has been trained, loaded or fitted, and no dataset has been acquired.

---

## 1. What this package is — and what it is not

| It is | It is not |
|---|---|
| A versioned **wire contract** for two endpoints | A server, a client library or an SDK |
| A set of **JSON Schemas** that define the payloads | A validated clinical data dictionary |
| A **deterministic mock fixture pack** (30 fixtures) | Real model output or real patient data |
| A **lightweight contract test suite** (offline, $0) | A model evaluation, benchmark or claim |
| An explicit **Track A / Track B separation** | Clinical guidance, thresholds or treatment logic |

Out of scope for M1a.1 and **not** present here: FastAPI server, database,
authentication, RBAC, React/Flutter UI, model code, dataset code, FHIR export.

---

## 2. Stable envelope vs provisional feature schemas

This is the central design decision of M1a.1 and the reason the package is
split the way it is.

### 2.1 Stable envelope (contract-owned, not data-owned)

The envelope is what the API *guarantees* and is expected to survive the
scientific gates. It lives in `schemas/common.schema.json` and defines:

| Element | Contract |
|---|---|
| Versioning | `contract_version: "v1"`; artifact ids (`model_id`, `preprocessing_id`, `calibration_id`, `feature_schema_id`, `explanation_config_id`) on every response |
| Target naming | `target{id, definition, time_horizon, status}` — the target is always named, so no consumer can invent a different one |
| Score semantics | `score{value, type, scale, rendering}` with `type ∈ {uncalibrated_score, calibrated_probability}` and machine-checkable rendering rules |
| Validation lifecycle | `validation_status ∈ {development_internal_only, externally_evaluated, externally_calibrated}` |
| Explanation semantics | `explanation{method, scale, base_value, contributions[], sum_check, synthetic, note}` on the log-odds/margin scale only |
| Provenance & audit | `provenance{training_datasets[], code_commit, artifact_hashes, dataset_access_status}` plus `audit_id` |
| Error surface | one error envelope, one catalogue of codes, explicit HTTP statuses |
| Idempotency | `Idempotency-Key` header, canonical-payload hashing, replay vs conflict |
| Track separation | `track: "A" | "B"`, and a hard rule that Track-B data can never be a Track-A input |

### 2.2 Provisional feature schemas (data-owned, gated)

The feature payload is **not** part of the stable envelope. It is bound to a
versioned `feature_schema_id`, and in M1a.1 the only available feature schemas
are **MOCK_ONLY placeholders**:

| File | Status |
|---|---|
| `schemas/mock_clinical_feature_schema.v1.json` | `MOCK_ONLY`, `UNVERIFIED_PENDING_GATE_DA` |
| `schemas/mock_clinical_feature_schema.v2.json` | `MOCK_ONLY`, `UNVERIFIED_PENDING_GATE_DA` |
| `registry/mock_model_registry.v1.json` | `MOCK_ONLY` stub bindings — **no model artifact exists** |
| `registry/mock_monitoring_metrics.v1.json` | `MOCK_ONLY` monitoring metric catalogue |

Consequences that are enforced by the test suite, not just by prose:

* **No clinical unit is asserted anywhere.** Every unit token in a MOCK_ONLY
  schema matches `^u_[a-z0-9_]+$` (`u_years`, `u_pressure`, `u_concentration`, …).
  Real units such as mmHg or mg/dL are deliberately *not* used, because the
  data dictionary has not been ratified (Phase 0 §F-1).
* **No dataset field name is reused.** Feature identifiers must match
  `^mock_feature_[a-z0-9_]+$`, so the package cannot impersonate a validated
  UCI clinical schema. A denylist of the real field names is asserted by
  `test_schemas.py`.
* **No dataset provenance.** Every mock response carries
  `provenance.training_datasets: []` and
  `dataset_access_status: "not_applicable_no_dataset_used"`.
* **The target is explicitly provisional.** `target.status` is
  `provisional_pending_approval` and `time_horizon` is `none_cross_sectional`.
  A 30-day or incident-risk horizon is not expressible in v1.

When Gate DA (D-031) opens and a dictionary is audited, a **new** feature
schema version is added. The envelope does not change; the `feature_schema_id`
in the response changes. That is the whole point of the split.

---

## 3. Endpoints

### 3.1 `POST /v1/predictions/cad-tabular` — Track A

Synchronous CAD-classification research output.

* **Request**: `contract_version?`, `request_id?`, `model_id?`,
  `feature_schema_id`, `features{…}`, `context{source, recorded_at,
  patient_ref?, consent_id?}`.
* **Admissible sources**: exactly `benchmark_import` and `clinician_entry`.
  Anything wearable is rejected with **422
  `wearable_input_not_valid_for_cad_inference`** (D-039, Phase 0 §F-4).
* **Response (200)**: the full mandatory envelope listed in §2.1, plus
  `explanation`, `missing_features[]`, `warnings[]`, `review_state`.
* **Idempotency**: `Idempotency-Key` is **required**; see §5.
* **Rejected with 422**: `unknown_feature`, `feature_not_in_schema`,
  `unit_mismatch`, `value_out_of_range`, `missing_required_feature`,
  `unknown_feature_schema`, `unknown_model`, `schema_model_mismatch`,
  `invalid_context_source`, `wearable_input_not_valid_for_cad_inference`.

### 3.2 `POST /v1/monitoring/observations` — Track B

Monitoring ingestion (patient-entered or wearable-sourced).

* **Request**: `observation{patient_ref, observed_at, source, consent_id?,
  metrics[]}`.
* **Response (201)**: `observation_id`, `accepted`, `received_at`,
  `recorded_metric_count`, `validation{status, issues[]}`, `disclaimer`.
* **Contains no Track-A output**: no `score`, no `target`, no `explanation`,
  no `model_id` — asserted by a schema test and by a fixture test.
* **Wearable sources are valid here** — this is the only route by which
  wearable data may enter the platform.
* **Rejected with 422**: `unknown_metric`, `unit_mismatch`,
  `value_out_of_range`, `consent_required`.

### 3.3 Deliberately *not* in M1a.1

`GET /v1/models/current` (Phase 0 §R2-6.3), `GET /v1/patients/{ref}/monitoring`,
`POST /v1/predictions/{audit_id}/review`, consent endpoints, and the FHIR-shaped
export (Phase 0 §8.7) are Phase 0 sketches. They are **not** part of this
contract and are absent on purpose — adding them now would expand the scope
beyond M1a.1.

---

## 4. Error catalogue

One envelope for every failure:

```json
{
  "contract_version": "v1",
  "error": {
    "code": "unit_mismatch",
    "message": "…",
    "details": [{"field": "features.mock_feature_vital_systolic.unit",
                 "feature_id": "mock_feature_vital_systolic",
                 "expected": "u_pressure", "received": "u_weight"}],
    "request_id": "…",
    "audit_id": "…",
    "original_audit_id": "…"
  }
}
```

| HTTP | Code | Provenance | Meaning |
|---|---|---|---|
| 400 | `malformed_request` | Phase 0 §8.4 | Body is not a valid request object / structural violation |
| 400 | `unsupported_contract_version` | **M1a.1 proposal** | The declared contract major version is not implemented |
| 422 | `unknown_feature` | Phase 0 §8.4 | Feature not declared by the feature schema |
| 422 | `feature_not_in_schema` | Phase 0 §R2-6.2 | Feature deliberately excluded or pending review |
| 422 | `unit_mismatch` | Phase 0 §8.4 | Unit differs from the unit declared by the schema |
| 422 | `value_out_of_range` | Phase 0 §8.4 | Value outside the declared range |
| 422 | `missing_required_feature` | Phase 0 §R2-6.2 | A required feature is absent (never silently imputed) |
| 422 | `unknown_feature_schema` | **M1a.1 proposal** | The named feature schema version does not exist |
| 422 | `unknown_model` | **M1a.1 proposal** | The named model is not in the registry |
| 422 | `schema_model_mismatch` | Phase 0 §8.4 | The model is not bound to the named feature schema |
| 422 | `invalid_context_source` | **M1a.1 proposal** | The source is neither admissible nor a known wearable token |
| 422 | `wearable_input_not_valid_for_cad_inference` | Phase 0 §F-4, D-039 | Wearable/monitoring data sent to CAD inference |
| 422 | `unknown_metric` | **M1a.1 proposal** | Monitoring metric not in the catalogue |
| 422 | `consent_required` | **M1a.1 proposal** | Monitoring observation without a consent reference |
| 409 | `idempotency_key_conflict` | Phase 0 §R2-6.1 | The key was already used with a different payload |
| 503 | `model_unavailable` | Phase 0 §8.4 | Artifact missing or mis-hashed — the system fails closed |
| 500 | `internal_error` | Phase 0 §8.4 | Server-side error; logged with an `audit_id` |

**Six codes are new in M1a.1 and need human approval** (`unsupported_contract_version`,
`unknown_feature_schema`, `unknown_model`, `invalid_context_source`,
`unknown_metric`, `consent_required`). They are marked as proposals in
`schemas/common.schema.json` (`ErrorCode.description`) and are listed here for
explicit sign-off. `internal_error` is a server-side condition and is therefore
covered by the catalogue test rather than by a request fixture.

### 4.1 Validation order (normative)

The semantic layer runs before the structural schema layer, so a violation is
reported with the specific contract code rather than a generic schema error:

1. body is an object → else `400 malformed_request`
2. `contract_version` → else `400 unsupported_contract_version`
3. `feature_schema_id` known → else `422 unknown_feature_schema`
4. **idempotency conflict** → `409 idempotency_key_conflict` (§5)
5. **wearable rejection** → else `422 wearable_input_not_valid_for_cad_inference`
6. `context.source` admissible → else `422 invalid_context_source`
7. `model_id` known → else `422 unknown_model`
8. model ⇄ feature-schema binding → else `422 schema_model_mismatch`
9. per-feature rules → `feature_not_in_schema` / `unknown_feature` /
   `unit_mismatch` / `value_out_of_range`
10. required features present → else `422 missing_required_feature`

Step 4 deliberately precedes the semantic rules: the rule "same key +
different payload → 409" is unconditional, so it must not be masked by a
validation error in the second payload. A request that was *rejected* never
occupied its key, so a later valid request under the same key is a first
request, not a conflict.

Step 5 deliberately precedes the feature rules: a wearable payload must always
fail with the wearable code, so the reason can never be misreported as a
generic schema problem.

---

## 5. Idempotency

| Case | Result |
|---|---|
| First request with key `K` | `200`, response stored under (K, payload hash), `audit_id` created, `idempotent_replay: false` |
| Retry: same `K`, identical canonical payload | `200`, **stored response verbatim** + `idempotent_replay: true`, same `audit_id`, no re-inference, no second audit event |
| Same `K`, different payload | `409 idempotency_key_conflict` with `original_audit_id` — **unconditionally**, even if the second payload is itself invalid (§4.1 step 4) |
| Same `K`, payload that was rejected earlier | Not a conflict: a request that produced no result never occupied its key, so a later valid request under `K` is a first request |
| Key older than the retention window (24 h) | Treated as a new request and logged |

* **Canonical payload**: UTF-8 JSON, lexicographically sorted keys, no
  insignificant whitespace, **with `request_id` removed** — `request_id` is an
  informational correlation id, so a retry that regenerates it is still a
  replay.
* **Payload hash**: SHA-256 of that canonical string.
* **Audit id (mock only)**: `uuid5(9e139be5-1516-59e8-b50c-45c834786b99,
  "<key>|-|<payload-hash>|<attempt>")`. The mock derives its identifiers so
  fixtures are byte-reproducible and a reviewer can recompute them by hand; a
  real implementation would use random UUIDs.
* **"No duplicate inference, no second audit event" is machine-checked**, not
  only asserted in prose: the reference implementation counts the inferences
  it performs and the audit events it creates, and the contract tests assert
  that a replay performs exactly one inference and creates exactly one audit
  event, while a conflict creates neither.

---

## 6. Explanation semantics (binding)

* **Scale**: `log_odds_margin` only. A probability-scale attribution is a
  different method and needs its own validation and contract version
  (Phase 0 §R2-5.7).
* **Sum-check**: `base_value + Σ contributions = margin` within the declared
  tolerance, machine-checked. The margin is `score.value` for an uncalibrated
  score and `score.raw_margin` for a calibrated one.
* **Applicability**: `sum_check.applicable` is `true` for `tree_shap` and
  `false` for `lime`, because a local surrogate is not an exact additive
  decomposition. A LIME response therefore reports `passed: false` *by
  design* rather than silently claiming additivity.
* **Never a probability**: SHAP/LIME contributions are **not** changes in a
  calibrated disease probability and must never be displayed as percentage
  points of disease probability. The contract states this in
  `explanation.note`, and the contract test asserts the wording is present.
* **Never causal, never advice**: a contribution is an *associational
  attribution of the model output*, **not a causal effect**. No treatment,
  intervention or recommendation may be derived from a contribution, and no
  contribution may be rendered as advice. The contract states this in
  `explanation.note`, and the contract test asserts the wording is present
  both in the committed fixtures and in a live response.
* **Synthetic marker**: `explanation.synthetic` is `true` for every M1a.1
  fixture. The contribution values are hand-authored deterministic offsets,
  **not** computed by SHAP or LIME from any trained model — no model exists.
* **LIME fidelity**: `local_fidelity_r2` is required when `method = "lime"`
  and forbidden otherwise.
* **The margin is not a probability and not a risk**: `score.value` in the
  uncalibrated case is a model margin on the log-odds scale. It is not a
  probability, not a percentage and not a patient risk estimate.

---

## 7. Score rendering (binding)

| `score.type` | `scale` | `display_unit` | `%` allowed | Meaning |
|---|---|---|---|---|
| `uncalibrated_score` | `log_odds_margin` | `unitless` | **no** | A relative model output. Never a probability. |
| `calibrated_probability` | `probability` | `decimal` | **no** | A benchmark-cohort calibrated output. Still **not** an absolute population probability (Phase 0 §F-6). |

`score.rendering.absolute_population_probability_claim` is `const: false` in
v1 — the schema makes an absolute-population claim inexpressible, and a
calibrated response must carry `cohort_context` with the population scope.
The M1a.1 "calibrated" fixture uses a **mock** calibration layer over a
synthetic cohort (`population_scope: mock_synthetic_no_cohort_exists`); it
exercises the branch of the contract and asserts no probability for any real
population.

---

## 8. File inventory

```
shared/contracts/
├── README.md                                  this file
├── openapi.yaml                               OpenAPI 3.1 document (the two endpoints)
├── schemas/
│   ├── common.schema.json                     stable envelope components + error catalogue
│   ├── cad_tabular_prediction.request.schema.json
│   ├── cad_tabular_prediction.response.schema.json
│   ├── monitoring_observation.request.schema.json
│   ├── monitoring_observation.response.schema.json
│   ├── mock_clinical_feature_schema.v1.json   MOCK_ONLY placeholder feature schema
│   └── mock_clinical_feature_schema.v2.json   MOCK_ONLY placeholder feature schema (v2)
├── registry/
│   ├── mock_model_registry.v1.json            MOCK_ONLY model bindings (no artifacts)
│   └── mock_monitoring_metrics.v1.json        MOCK_ONLY monitoring metric catalogue
└── fixtures/
    ├── index.json                             pack manifest + Phase 0 coverage map
    └── F-*.json                               30 deterministic fixtures
```

The JSON Schemas are the **source of truth** for payload structure; the
OpenAPI document wires them to paths, headers and HTTP status codes.

---

## 9. Fixture pack

30 fixtures, all deterministic, all MOCK / SYNTHETIC, no randomness and a
frozen clock (`2026-10-16T12:00:00Z`).

| Phase 0 id | Covered by |
|---|---|
| F-01 golden valid request/response per schema | `F-01`, `F-01b`, `F-12a` |
| F-02 every error code | `F-02a`…`F-02k`, `F-04b`, `F-04c` (plus `internal_error` in the catalogue test) |
| F-03 missing optional vs missing required | `F-02f` (required → 422), `F-03a` (optional → 200 + `missing_features[]`), `F-03b` (null vs zero) |
| F-04 unit mismatch / unknown feature / out of range | `F-02b`, `F-02c`, `F-02d`, `F-02e` |
| F-05 idempotent replay | `F-05` |
| F-06 key conflict (409) | `F-06` |
| F-07 determinism | `F-01`, `F-07` |
| F-08 SHAP sum-check | `F-08`, `F-01`, `F-11b` |
| F-09 wearable rejected for inference | `F-09a` (source), `F-09b` (payload field) |
| F-10 mandatory-field snapshot | `F-10` + `test_mandatory_track_a_fields_are_present` |
| F-11 uncalibrated rendering | `F-11`, `F-11b`, `F-11c` |
| F-12 model swap / version compatibility | `F-12a` (model swap), `F-12b` (contract version), `F-02g` (schema ⇄ model) |

Fixture file format: each file carries `fixture_id`, `title`, `description`,
`covers_phase0_fixture_ids`, `phase0_reference`, `track`, `endpoint`,
`data_class`, `disclaimer` and a list of `steps`; each step carries the
`request` (headers + body), the `expected` status and body, and a set of
`assertions` that the test suite interprets.

**The `assertions` blocks are executed, not decorative.** Every declared
expectation in every step is checked by the suite
(`test_contract_behaviour.py::test_every_fixture_assertion_block_is_executed`),
so a fixture cannot claim an expectation that the test suite never verifies.

**Null vs zero** (Phase 0 §R2-6.2) has its own fixture, `F-03b`: a `null`
value on a required feature is "not provided" and is rejected with
`422 missing_required_feature`; a value of `0` is data — it is not missing, it
does not appear in `missing_features`, and it does appear in the explanation
contributions.

**Distinct inputs.** The pack deliberately contains no two scenarios that
exercise the same input: each scenario carries its own feature values, so a
reviewer reading one fixture has read a genuinely different request. The only
repeated payloads are the two that *must* repeat — `F-05` (the replay) and
`F-07` (the determinism check) — where the repetition is the point.

---

## 10. Tests and CI

```bash
python -m venv .venv
. .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r tests/contracts/requirements.txt
python -m pytest tests/contracts -q
```

Python 3.10+ (CI uses 3.12). Everything runs offline in under a second. The
dependencies are pinned in `tests/contracts/requirements.txt`
(`jsonschema`, `referencing`, `openapi-spec-validator`, `PyYAML`, `pytest`).

`.github/workflows/contracts-ci.yml` runs the same suite on every pull request
to `main`, with the actions pinned to immutable commit SHAs. It is pure CPU
work with no external service, so it stays within the free GitHub Actions
minutes included with every plan — **$0**.

The suite contains four groups of tests:

* `test_openapi_document.py` — the document is valid OpenAPI 3.1, exposes
  exactly the two endpoints, resolves every `$ref`, documents errors and
  idempotency, and exposes no risk/alert/treatment field.
* `test_schemas.py` — the schemas are valid JSON Schema 2020-12, and the
  MOCK_ONLY guard-rails hold (placeholder units only, no dataset field names,
  no dataset provenance, no time horizon, no Track-A output in a Track-B
  schema).
* `test_fixtures.py` — the pack validates against the schemas, is reproduced
  exactly by the reference implementation, and satisfies the sum-check,
  rendering, idempotency, determinism, track-separation and
  claims-discipline rules.
* `reference_contract.py` — the **test oracle**: a deterministic in-process
  implementation of the contract semantics. It is *not* a server (no HTTP, no
  framework, no database, no model). It exists so the fixtures are checked
  against one explicit reading of the contract instead of against prose.

---

## 11. Unresolved schema questions (open for the reviewer)

These are **not** decided here. Each one needs a human decision, and several
are blocked by gates that are not open.

| # | Question | Blocked by / owner |
|---|---|---|
| Q1 | What are the real feature-schema identifiers (`uci_heart_14_v1`? `z_alizadeh_sani_v1`?), and what is the exact feature list, type, unit and range of each? | Gate DA (D-031) + the dictionary audit |
| Q2 | What is the ratified unit of the ST-depression slot (the UCI codebook states no unit)? | §F-1 / data dictionary |
| Q3 | Is the thallium stress-test result admissible at the intended prediction moment, and is the fluoroscopy vessel count excluded from the primary schema? | D-027 + the feature-availability audit |
| Q4 | What is the approved target definition and the exact narrowing threshold wording (`>50%` vs `≥50%`)? | P-1 / D-006 (research lead + supervisor) |
| Q5 | Is `benchmark_import` the right source token for non-UCI imports, and will a third source (e.g. registry import) be needed? | Research lead |
| Q6 | May the request body select a model explicitly (`model_id`), or is the active model always implied? | Backend/AI integration review |
| Q7 | Should `POST /v1/monitoring/observations` return `201` or `200`? Is `consent_id` the right consent reference shape for the prototype? | Backend review |
| Q8 | Is a 24 h idempotency retention window acceptable, and what is the store of record (in-memory, file, Redis) once a server exists? | M1a.2 / M1b decision |
| Q9 | Should `warnings[]` be structured objects instead of strings, and is a `warning_code` needed? | Frontend/Backend review |
| Q10 | Should `explanation.contributions[]` carry a normalised importance share, or is the margin-scale offset enough? | Clinician-facing design review (P-4) |
| Q11 | Is a batch observation-ingestion endpoint needed for offline mobile sync? | Mobile workstream (M1b) |
| Q12 | How are identifier-shaped `patient_ref` values rejected in practice (denylist implementation)? | Privacy review |
| Q13 | Which of the six new M1a.1 error codes are accepted, and do any of them need renaming? | Reviewer decision |
| Q14 | When the FHIR-shaped export (Phase 0 §8.7) is added, does it need its own contract version? | D-020 decision |

---

## 12. Proposed next milestone (M1a.2) — for discussion, not decided

The Phase 0 M1a definition is wider than M1a.1. M1a.1 delivered only the
contract, the fixtures and the contract tests. A reasonable M1a.2 would add
the **mock server** that serves this contract (still no model, no dataset, no
database persistence) so the React and Flutter clients can integrate against a
stable surface. That scope decision — and the remainder of M1a (login/RBAC,
audit events, a thin end-to-end path) — belongs to the maintainer, not to
this document.
