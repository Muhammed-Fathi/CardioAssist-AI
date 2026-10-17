# M1a.2 contract implementation notes and review questions

## Verified baseline and authority

Before editing files, GitHub reported PR #3 **MERGED** into `main` at
`6e677b7924f88f88cbe50a155105cd9c44c0dff0`. The remote `main` tip was that
same commit. The final approved PR head
`fc2c62b78a84075625555a69372b687d53ab9995` and `main` had **no differences**
in `shared/contracts/`, `tests/contracts/`, or
`.github/workflows/contracts-ci.yml`. This includes the final review fixes,
30 fixtures, 136 contract tests, and the maintainer-authored workflow.

Read: `AGENTS.md`, `docs/DECISIONS.md` (D-034–D-043 and pending P-1–P-6),
Phase 0 Rev. 3, and the merged contracts/tests. The active human M1a.2
instruction authorizes this backend despite older Phase-0-only text in the
repository. It does **not** authorize models, datasets, DB persistence, auth,
RBAC, frontend work, clinical thresholds, or a merge.

The session branch `arena/cae890ca-cardioassist-ai` started at the latest
`main` commit above; it is Arena's fixed dedicated branch for this work.

**No approved contract, registry, fixture, oracle, contract-test file or
existing workflow is edited.** Historical `PROPOSED_M1A_1` labels in those
files are retained, not silently reclassified as clinical approval. The
scientific target and dataset/medical gates remain pending.

## Reuse, not a second API definition

- Runtime structural validation uses the checked-in JSON Schemas, local
  `$ref` registry, and UUID/date-time format checking. There is no parallel
  hand-maintained Pydantic request/response model.
- Feature bindings, required fields, units and ranges come from the schema
  conditional refs. Models/default selection and monitoring quantities come
  from the approved MOCK_ONLY registries. No new clinical range is defined.
- The approved F-01, F-11b and F-04a success bodies supply static target,
  rendering, safety, provenance and explanation wording. They are templates,
  **not** request-to-response lookups. New valid mock inputs use the same
  SHA-256-derived synthetic offsets as the approved pack.
- `provenance.code_commit: mock-fixture-pack-v1` intentionally identifies the
  fixture-semantics version, not a claimed Git commit of a trained model.
  Artifact hashes still denote the empty byte string / **no artifact**.
- The served `/openapi.json` bundles those same schemas by rebasing refs;
  it does not auto-generate an incompatible FastAPI `HTTPValidationError` API.
- HTTP tests import neither `ReferenceContract` nor its helpers. They compare
  committed golden bodies and independently check HTTP behaviors, validation,
  identifiers, schema compliance, additivity and concurrent side effects.

## Ambiguities explicitly reported — not silently redesigned

The following are **review questions**, not approvals of new semantics.
Current compatibility behavior is covered by HTTP tests. Any tightening or
schema revision needs a separate explicit review.

| ID | Existing tension / question | M1a.2 behavior and outstanding decision |
|---|---|---|
| B-01 | Track-B request `value` permits number/string/boolean/null, but the metric catalogue has numeric/integer `value_type`. The merged oracle does not enforce `value_type` (including integer-only counts). | Preserve the wire schema + merged reference behavior: accept schema-permitted scalars, range-check numeric non-booleans, do not coerce. Strings/booleans and fractional counts are **not ratified measurement semantics**. Reviewer must decide the intended type rule and error code before tightening the contract. This path remains MOCK_SYNTHETIC only. |
| B-02 | Common idempotency prose says replay = 200; the Track-B operation documents only 201, and the merged behavior test explicitly expects 201 for a replay. The contract README Q7 also asks 200 vs 201. | Use **201 for both first acceptance and replay**, preserving the operation-specific OpenAPI and merged tests. Reviewer should reconcile the generic wording, not add an undocumented 200 response here. |
| B-03 | Idempotency namespace is not explicitly scoped by route/client in the prose. The merged oracle uses one global key store for both tracks. | Preserve a **global namespace**, with an additional route-identity guard: reuse on the other endpoint is 409, never a wrong-track replay. Clients should prefix keys by logical write/track. Endpoint/client scoping requires a reviewed decision. |
| B-04 | Schema says null means “not measured”; it does not explicitly define all-null observations, repeated metric ids or count semantics. The merged oracle skips nulls, counts other entries, accepts all-null observations and does not deduplicate metric ids. | Preserve that behavior: zero is counted; null is not stored as a measurement; all-null = 201, accepted, count 0; duplicate entries count individually. Validate the whole request before publishing any observation/audit. Reviewer must ratify or revise these cases. |
| A-01 | CAD feature prose says explicit null = absent; the shared feature schemas' per-feature `allOf` value constraints reject null, including optional slots, while the live backend treats optional null as missing. | Preserve the approved runtime behavior: required null/absent → 422 `missing_required_feature`; explicit optional null → successful response with the existing missing-feature warning. Validate wrapper shape/unit/extra fields and omit optional null only from a validation copy. Original JSON is still hashed, so null and absent remain different idempotency payloads. **Maintainer approved ADR-001 Option A (D-044, 2026-10-17).** Implementation is sequenced behind a behavior-preserving runtime schema-reader prerequisite (this change-set) because the runtime reads `properties.value["type"]` directly and would otherwise raise `KeyError` for the future `anyOf` shape. The committed schemas remain unchanged here; the schema/fixture correction is deferred to a separate follow-up PR. There is no fitted imputer: missing slots have no synthetic contribution. |
| G-01 | Both requests make `request_id` optional, but both success schemas require a UUID; the oracle returns null when it is omitted. | Generate a deterministic prototype correlation UUID for an omitted id. A replay preserves the original id; invalid ids in errors are omitted rather than echoed into a schema-invalid error. No request or response schema change is necessary. |
| G-02 | README validation-order table places version/schema checks before conflict, while its unconditional-conflict prose, OpenAPI, and the active task say any different payload under a used key is 409. | Follow the **unconditional** rule: parse JSON, require an object and a valid header, then look up conflict/replay **before all semantic checks**, including version/schema. Tests cover invalid versions and missing envelopes under a used key. Malformed JSON/non-object/header failures cannot identify a valid canonical request and remain 400. Reviewer should reconcile the ordering table. |
| X-01 | Legacy F-11c/registry include a synthetic LIME result with an illustrative fixed local R². The active task explicitly prohibits fabricating a computed LIME result. | The known LIME-only `mock_model_d_v0.1.0` binding is **unavailable in this server**: 503 `model_unavailable`, no score/explanation/fidelity. Its legacy contract fixture/test remains unchanged and still runs. Live HTTP coverage explicitly asserts 503 rather than skipping the case. LIME stays a future integration capability requiring actual method/fidelity validation, never a made-up result. |

Other unresolved questions already recorded in the merged contract README
§11 remain open: real feature dictionary/units/eligibility, target wording,
consent lifecycle, future retention store, patient-ref privacy checks, offline
batch sync, FHIR scope, and clinician wording. No dataset, clinical or privacy
gate is closed by implementing this mock.

## A-01 schema compatibility finding — approval required

**Finding.** The normative feature schemas combine the generic `FeatureValue`
object with each property's value rule using `allOf`. `FeatureValue` permits a
null scalar, but the per-feature `type` rule (integer, number, string, or
boolean) excludes null. A Draft 2020-12 validator therefore rejects an
optional feature wrapper such as `{"value": null, "unit": "u_count"}`.
The live backend's semantic validator deliberately interprets that optional
null as missing, returns success, reports the feature as missing, and emits
its existing `imputed_feature:` warning. Required null remains a 422
`missing_required_feature`; absent optional fields already work in both
schema and backend. Zero/false remain data.

Thus a standards-compliant client-side schema validator or generated client
that enforces the per-feature schema can reject an optional-null request that
the backend accepts. Code-generator nullability behavior differs by tool, so
this is a risk, not a claim that every React/Flutter generator will reject it.
The current schema does not accept invalid values by virtue of this
inconsistency; it is stricter than the runtime only for optional null values.

**Proposed patch (not applied).** In both
`shared/contracts/schemas/mock_clinical_feature_schema.v1.json` and
`mock_clinical_feature_schema.v2.json`, replace each *optional* property's
second `allOf` member's direct `properties.value` constraint with an `anyOf`
containing `{ "type": "null" }` and the exact existing typed/ranged
constraint. For example, for `mock_feature_vital_systolic`:

```json
"value": {
  "anyOf": [
    { "type": "null" },
    { "type": "number", "minimum": 0, "maximum": 400 }
  ]
}
```

Apply the same shape to all optional slots (including string/boolean/integer
slots where present), leaving their current range/type/unit constraints
unchanged. Keep required `mock_feature_demographic_age` and
`mock_feature_demographic_sex` non-null so required null remains invalid as a
successful request and continues to produce the existing 422. Do not change
error codes, feature definitions, target semantics, or response schemas.

**Expected coverage changes.** The required-null and zero cases in committed
fixture `F-03b-null-and-zero-value-semantics.json` remain unchanged. It does
not currently contain an optional-null case. Add an optional-null request
assertion to the contract behavior/schema tests and fixture pack (or add a
new fixture) confirming the same successful semantics as
`tests/backend/test_behavior_http.py::test_required_null_optional_null_and_zero_are_distinct`.
That HTTP regression already covers the current backend behavior. No existing
fixture response body needs changing for the proposed optional-null case; the
new schema acceptance assertion is the missing coverage.

**Runtime prerequisite (maintainer-authorized, separate change-set, PR #7).** The
original proposal assumed no runtime change was necessary. During the
implementation audit, `feature_rules`/`validate_features` in
`backend/app/validation.py` were confirmed to read `properties.value["type"]`
directly from each `allOf` member. The ADR's `anyOf` shape would therefore
raise `KeyError: 'type'` for every non-null optional feature (20 existing
backend tests failed in verification). The maintainer authorized a minimal,
behavior-preserving adapter that extracts the single non-null typed
alternative for non-null values; null is still skipped before type checking.
It is a no-op for the current schemas and for every required slot, and it
changes no wire behavior, error code, scoring or audit rule. Coverage lives in
`tests/backend/test_schema_reader.py`. The committed feature schemas are
**not** changed by this prerequisite; the schema/fixture correction remains
the follow-up change-set.

**Compatibility/versioning.** The backend already accepts this request and
v1 prose already says null means not provided, so the approved change broadens
only schema validity and aligns code generation with existing wire behavior;
it does not change HTTP semantics, scoring or error codes. The maintainer
approved Option A in D-044. The schema bundle, fixture/test assertions and
contract artifact revision must be updated together in the follow-up PR; no
schema, fixture or client change is made in this prerequisite PR.

## CI workflow status

The maintainer has installed `.github/workflows/backend-ci.yml`; it is an
executing workflow on `main`, not a proposed/non-executing template. The
existing `.github/workflows/contracts-ci.yml` remains separate and is not
changed here. Workflow presence and local test results do not establish that
GitHub Actions ran or passed for this PR: inspect actual checks on the latest
commit. See `backend/ci/README.md`. CI checks software behavior only; it does
not validate a real trained AI, authorize a research deployment, or approve
clinical deployment.

## Idempotency and audit lifecycle

1. Only successful, schema-validated results occupy keys. Validation failures,
   simulated unavailability and internal failures do not consume a key.
2. Canonicalization is UTF-8 JSON with sorted object keys, compact separators
   and top-level `request_id` removed. It is the merged pack's rule, **not** a
   new RFC-8785/numeric/default/null normalizer. Arrays remain ordered.
3. One coarse in-process lock covers lookup, validation, mock calculation,
   response validation, storage and success-audit publication. HTTP handlers
   run that transaction in a worker thread, not on the ASGI event-loop thread.
4. Same key + same route/canonical payload returns a defensive copy of the
   original response with only `idempotent_replay` changed to true. Audit id,
   correlation id, frozen timestamp and score/explanation remain original.
5. Same key + different canonical payload (or different route) returns 409
   with the original result identifier in `original_audit_id`. For Track B
   that identifier is the `observation_id`; no unapproved `audit_id` is added
   to its response schema.
6. Retention is the **approved 24 hours**, read from OpenAPI and measured with
   a monotonic clock. Replays do not extend it. Expired keys are evicted lazily
   on reuse; reuse is logged without raw key/body/measurement data. A new
   successful attempt gets a new deterministic identifier within the process.
7. The app exposes immutable success/error audit-event snapshots, a defensive
   observation snapshot and an inference counter **to Python tests only**.
   No audit/history/admin HTTP endpoint is added. Validation errors/conflicts
   create no inference/success-audit; an unexpected 500 has its own error audit
   id, safe log message and no client traceback/internal detail.

**Prototype limitations:** RAM only, one process/one worker, no replicas,
no durable log, no cross-process transaction, no tamper resistance, no consent
record lookup, no authentication/authorization, no PHI screening guarantee,
no rate limits, no production memory bound/garbage collector. Audit events,
observations and attempt bookkeeping can grow until restart; the 24-hour rule
is replay retention, not a complete memory-management policy. All state is
lost on restart/reload and deterministic fixture ids can repeat after restart.
These are not production auditing, storage, privacy or uniqueness guarantees.
