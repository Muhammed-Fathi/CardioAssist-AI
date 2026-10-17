# M1a.2 contract implementation notes and review questions

## Verified baseline and authority

Before editing files, GitHub reported PR #3 **MERGED** into `main` at
`6e677b7924f88f88cbe50a155105cd9c44c0dff0`. The remote `main` tip was that
same commit. The final approved PR head
`fc2c62b78a84075625555a69372b687d53ab9995` and `main` had **no differences**
in `shared/contracts/`, `tests/contracts/`, or
`.github/workflows/contracts-ci.yml`. This includes the final review fixes,
30 fixtures, 136 contract tests, and the maintainer-authored workflow.

This paragraph records the **historical M1a.2** authorization context; the
branch and baseline details below are not the current session. Current
repository authorization is the maintainer-approved D-045 M1b.1 slice only,
which permits the SQLite/Alembic monitoring persistence documented later in
this file. It does not authorize datasets, model training, clinical claims,
auth/RBAC, frontend work, other new APIs or a merge. See `AGENTS.md` and
`docs/DECISIONS.md` for current scope. D-045 supersedes the stale original
Phase-0-only restriction only for the explicitly bounded M1b.1 work.

The session branch `arena/cae890ca-cardioassist-ai` named in the historical
M1a.2 record is not the current Arena branch.

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
| A-01 | CAD feature prose said explicit null = absent; the shared feature schemas' per-feature `allOf` value constraints rejected null, including optional slots, while the live backend treated optional null as missing. | **RESOLVED — technical correction complete.** Maintainer-approved ADR-001 Option A (D-044): runtime schema-reader prerequisite PR #7 merged (`7f850bd`); schema/fixture/test correction PR #8 merged (`156bde2582671ad08f187850e3a7cc20790b19d2`). Required null/absent still produces 422 `missing_required_feature`; optional null succeeds with the existing missing-feature warning. Original JSON is still hashed, so null and absent remain different idempotency payloads. There is no fitted imputer: missing slots have no synthetic contribution. No unrelated decision or approval gate is changed. |
| G-01 | Both requests make `request_id` optional, but both success schemas require a UUID; the oracle returns null when it is omitted. | Generate a deterministic prototype correlation UUID for an omitted id. A replay preserves the original id; invalid ids in errors are omitted rather than echoed into a schema-invalid error. No request or response schema change is necessary. |
| G-02 | README validation-order table places version/schema checks before conflict, while its unconditional-conflict prose, OpenAPI, and the active task say any different payload under a used key is 409. | Follow the **unconditional** rule: parse JSON, require an object and a valid header, then look up conflict/replay **before all semantic checks**, including version/schema. Tests cover invalid versions and missing envelopes under a used key. Malformed JSON/non-object/header failures cannot identify a valid canonical request and remain 400. Reviewer should reconcile the ordering table. |
| X-01 | Legacy F-11c/registry include a synthetic LIME result with an illustrative fixed local R². The active task explicitly prohibits fabricating a computed LIME result. | The known LIME-only `mock_model_d_v0.1.0` binding is **unavailable in this server**: 503 `model_unavailable`, no score/explanation/fidelity. Its legacy contract fixture/test remains unchanged and still runs. Live HTTP coverage explicitly asserts 503 rather than skipping the case. LIME stays a future integration capability requiring actual method/fidelity validation, never a made-up result. |

Other unresolved questions already recorded in the merged contract README
§11 remain open: real feature dictionary/units/eligibility, target wording,
consent lifecycle, future retention store, patient-ref privacy checks, offline
batch sync, FHIR scope, and clinician wording. No dataset, clinical or privacy
gate is closed by implementing this mock.

## A-01 schema compatibility finding — RESOLVED (D-044; PRs #7 and #8 merged)

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

**Status:** The approved technical correction is complete. PR #7 merged the
behavior-preserving runtime adapter; PR #8 merged the optional-null schema,
fixture and regression-test changes. The historical finding below records the
reasoning and verified behavior; it is not an outstanding implementation task.

**Approved correction (implemented in PR #8).** In both
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

**Coverage delivered in PR #8.** The required-null and zero cases in
`F-03b-null-and-zero-value-semantics.json` remain unchanged. The new fixture
`F-03c-optional-null-equivalent-to-absent.json` and contract/HTTP regression
tests verify the same successful semantics as
`tests/backend/test_behavior_http.py::test_required_null_optional_null_and_zero_are_distinct`.
The runtime HTTP behavior and error codes did not change.

**Runtime prerequisite (maintainer-authorized, separate change-set, PR #7).** The
original proposal assumed no runtime change was necessary. During the
implementation audit, `feature_rules`/`validate_features` in
`backend/app/validation.py` were confirmed to read `properties.value["type"]`
directly from each `allOf` member. The ADR's `anyOf` shape would therefore
raise `KeyError: 'type'` for every non-null optional feature (20 existing
backend tests failed in verification). The maintainer authorized a minimal,
behavior-preserving adapter that extracts the single non-null typed
alternative only from the exact approved shape (no siblings beside `anyOf`,
exactly two alternatives, one exact `{"type": "null"}`); null is still skipped
before type checking, and unexpected structures are left unchanged so the
runtime fails closed. It is a no-op for the current schemas and for every
required slot, and it
changes no wire behavior, error code, scoring or audit rule. Coverage lives in
`tests/backend/test_schema_reader.py`. The committed feature schemas were
**not** changed by that prerequisite. **PR #7 is MERGED** into `main` at
merge commit `7f850bd`.

**Schema/fixture correction (PR #8 — MERGED).** PR #8 applies the approved
Option A patch to the two mock feature schemas: the nine optional slots (5 in
v1, 4 in v2) declare `{"anyOf": [{"type": "null"}, <the original
typed/ranged rule>]}`, and required slots are untouched. It adds fixture
`F-03c-optional-null-equivalent-to-absent.json` (both schema versions) and the
matching contract and HTTP regression tests. PR #8 merged to `main` at
`156bde2582671ad08f187850e3a7cc20790b19d2`. A-01's technical correction is
complete.

**Compatibility/versioning.** The backend already accepted this request and
v1 prose already said null means not provided, so the approved change broadens
only schema validity and aligns code generation with existing wire behavior;
it does not change HTTP semantics, scoring or error codes. The maintainer
approved Option A in D-044. The schema bundle, fixture/test assertions and
contract artifact revision were updated together in PR #8. Independent
Windows verification and any CI result are reported separately, not inferred
from the merge state.

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

1. Only successful, schema-validated results occupy runtime keys. Validation
   failures, simulated unavailability and storage failures do not consume a
   key. Canonicalization remains UTF-8 JSON with sorted object keys, compact
   separators and top-level `request_id` removed; arrays remain ordered.
2. One coarse in-process lock still covers conflict/replay lookup, validation,
   mock response construction, response-schema validation, the Track-B SQL
   transaction and runtime publication. The HTTP handler runs it in a worker
   thread, not on the ASGI event-loop thread.
3. Same key + same route/canonical payload during a process lifetime replays
   the original response with only `idempotent_replay` changed. Replays create
   no additional observation/metric/audit rows. Changed payload or route gives
   409 before semantic validation, with the existing `original_audit_id` rule.
4. The existing **24-hour runtime window** remains read from OpenAPI and is
   measured with a monotonic clock; replays do not extend it and expiry is
   lazy. **Q8 remains OPEN** for formal ratification of the window and the
   durable store of record. Idempotency keys, response snapshots, attempt
   counters and expiry state are still process-local and are not written to
   the database in this slice.
5. Each accepted `POST /v1/monitoring/observations` writes one observation row,
   its non-null metric rows and exactly one success `audit_event` row in a
   single SQL transaction. A rollback publishes none of them. The audit row
   contains only identifiers, path/type, request id, payload hash and time —
   never raw metric values, patient reference, consent reference or request
   body. The repository has insert/read methods only; it exposes no audit
   update/delete service path. SQLite itself has no PostgreSQL-style
   `GRANT`/`REVOKE` enforcement.
6. Rejected requests, conflicts and replays create no durable success audit.
   CAD predictions are not persisted by M1b.1. Unexpected 500s retain their
   existing safe, process-local error-audit id; an error row is not guaranteed
   durable if the database itself failed. No history/audit HTTP endpoint was
   added.
7. `patient_ref` and `consent_id` are stored as opaque, synthetic/demo-only
   contract values. As before, `consent_id` is required to be non-empty but is
   not looked up against a consent record. There is no PatientProfile or
   ConsentRecord FK yet; adding either would change the approved endpoint's
   reference semantics and is deferred to a separate reviewed M1b slice.

**Restart and security limitations:** SQLite monitoring observations and
success-audit metadata survive app/process restart. Runtime idempotency/audit
snapshots and inference counters reset. Therefore a same-key retry after a
restart may be accepted as a new write; deterministic public `observation_id`
values may repeat, while a separate private storage UUID keeps database rows
individually addressable. This preserves existing runtime behavior but is not
cross-process exactly-once delivery. The service remains single-process /
one-worker, unauthenticated, synthetic/demo-only, without PHI screening,
rate limits, tamper-resistant audit, multi-replica guarantees or PostgreSQL
compatibility evidence. Durable idempotency is assigned to a future M1b slice
after Q8 review; patient/consent linkage remains gated by Q7/Q12 and a
contract-first consent decision.
