# ADR-001 — CAD optional-null feature values: JSON Schema / backend compatibility (APPROVED — Option A; implementation in progress)

| Field | Value |
|---|---|
| Status | **APPROVED — Option A** (maintainer, 2026-10-17; decision **D-044**). Implementation is **in progress** in two reviewed change-sets: (1) a behavior-preserving runtime schema-reader prerequisite (in review), and (2) the schema/fixture/test correction (not yet applied). Do not describe the schema correction as implemented or merged before change-set (2) is actually merged. |
| Date | 2026-10-17 |
| Origin | M1a.2 review finding **A-01** (`backend/CONTRACT_NOTES.md`), re-reported for approval in PR #5 (`security: dependency and contract compatibility cleanup`) |
| Scope | `shared/contracts/schemas/mock_clinical_feature_schema.v1.json`, `mock_clinical_feature_schema.v2.json` (optional feature slots only) |
| Out of scope | Target semantics, error codes, units, ranges, response schemas, registries, real feature schemas (which do not exist yet), any backend behavior change |

## 1. Context

The normative mock feature schemas combine the generic `FeatureValue`
definition (which permits a `null` scalar — `null` means "not provided")
with each feature property's typed value rule using `allOf`:

```json
"mock_feature_vital_systolic": {
  "allOf": [
    { "$ref": "#/$defs/FeatureValue" },
    { "properties": { "value": { "type": "number", "minimum": 0, "maximum": 400 },
                      "unit": { "const": "u_pressure" } } }
  ]
}
```

Under JSON Schema Draft 2020-12, the two `allOf` members must both hold, so
the typed member rejects `{"value": null, "unit": "u_pressure"}` even though
`FeatureValue` allows `null`. This applies to **optional** slots as well as
required ones.

The live mock backend (`backend/app/validation.py`, behavior pinned by
`tests/backend/test_behavior_http.py::test_required_null_optional_null_and_zero_are_distinct`)
deliberately interprets:

| Input | Backend (runtime) behavior | Schema (Draft 2020-12) verdict |
|---|---|---|
| Required feature `value: null` or absent | `422 missing_required_feature` | rejected (consistent) |
| Optional feature absent | success, reported in `missing_features` + `imputed_feature:` warning | accepted (consistent) |
| Optional feature `value: null` | success, same missing-feature reporting | **rejected (INCONSISTENT)** |
| `0` / `false` | data, never treated as missing | accepted (consistent) |

`FeatureValue`'s own prose says null means "not provided" and is treated
exactly like an absent feature (Phase 0 §R2-6.2). The v1 contract prose
therefore already intends optional-null to be valid on the wire.

**Consequence of the mismatch (the real problem):** a standards-compliant
client-side schema validator, or a generated TypeScript/Dart client whose
generator resolves `allOf` + nullable strictly, can reject a request the
server accepts. Code-generator nullability handling varies by tool, so this
is a compatibility *risk*, not a claim that every generator breaks. No
*invalid* input becomes valid through this inconsistency — the schema is
stricter than the runtime only for optional nulls.

## 2. Decision drivers

1. The runtime behavior (optional null = missing, with warning) is already
   documented contract prose and is covered by an existing HTTP regression
   test; it is the behavior the M1a.3 clients are being handed
   (`docs/M1A3_INTEGRATION_HANDOFF.md` §2.4 "optional missing values").
2. Approved shared v1 artifacts must not be edited without maintainer
   approval (AGENTS.md priority rules; PR #3 froze the pack).
3. The fix should be the *minimal* one: it must not ratify any new
   measurement semantics, change error codes, or touch target/clinical
   meaning.
4. Two remediation routes exist (in-place v1 correction vs. a separately
   versioned revision), and the choice between them is a maintainer
   decision, not an agent decision.

## 3. Proposed decision (Option A — recommended)

**A. In-place, schema-only correction to the existing v1/v2 mock feature
schemas, applied together with fixture/test coverage and an artifact-revision
note, treating the change as a clarification of the already-documented
"null = not provided" semantics.**

### 3.1 Minimal patch

In `mock_clinical_feature_schema.v1.json` and
`mock_clinical_feature_schema.v2.json`, for each **optional** property
(everything except `mock_feature_demographic_age`, `mock_feature_demographic_sex`,
and — in v2 — the required `mock_feature_fraction`), replace the second
`allOf` member's direct `properties.value` constraint with an `anyOf` of
`null` and the exact existing typed/ranged constraint. Example
(`mock_feature_vital_systolic`):

```json
"mock_feature_vital_systolic": {
  "allOf": [
    { "$ref": "#/$defs/FeatureValue" },
    {
      "properties": {
        "value": {
          "anyOf": [
            { "type": "null" },
            { "type": "number", "minimum": 0, "maximum": 400 }
          ]
        },
        "unit": { "const": "u_pressure" }
      }
    }
  ]
}
```

Apply the same shape to every optional slot (integer, number, string and
boolean slots included), leaving all range/type/unit constraints otherwise
byte-identical. Required slots stay non-null, so required null continues to
produce `422 missing_required_feature` exactly as today. No error code,
feature definition, registry, target semantic, or response schema changes.

### 3.1.1 Implementation prerequisite discovered during the audit (2026-10-17)

The original proposal assumed "no backend code change is required — the
runtime already accepts the request". That assumption was correct for the
**wire behavior** but incomplete for the **implementation**: the live runtime
reads the typed rule directly from each `allOf` member
(`backend/app/validation.py`, `feature_rules`/`validate_features`). Applying
the `anyOf` shape without an adapter makes a non-null optional value raise
`KeyError: 'type'` (verified: 20 existing backend tests fail with HTTP 500).

The maintainer therefore authorized a **minimal, behavior-preserving runtime
schema-reader adapter** as a separate prerequisite PR (**PR #7**,
<https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/7>). The adapter extracts
the single non-null typed alternative from `anyOf` for non-null values; null
continues to be skipped before type checking. It is a no-op for all current
schemas and required slots. The schema/fixture correction itself remains
deferred to the follow-up PR and must not be applied until the prerequisite is
reviewed and merged.

### 3.2 Required coverage changes (must ship in the same change-set)

1. **Fixture:** `F-03b-null-and-zero-value-semantics.json` (required-null /
   zero semantics) stays unchanged. Add an optional-null request assertion —
   either a new step in F-03b's pack entry or a new fixture
   (e.g. `F-03c-optional-null-equivalent-to-absent.json`) — with a
   committed expected body identical to the corresponding
   missing-feature response (missing list + existing warning), covering
   **both** `mock_clinical_v1` and `mock_clinical_v2` optional slots.
2. **Contract tests:** extend the schema/behavior tests in
   `tests/contracts/` to assert Draft 2020-12 acceptance of the
   optional-null wrapper and semantic equivalence with the absent form.
3. **HTTP regression:** the existing
   `tests/backend/test_behavior_http.py::test_required_null_optional_null_and_zero_are_distinct`
   must continue to pass **unchanged** (it already pins the behavior).
4. **Fixture-oracle consistency:** `tests/contracts/reference_contract.py`
   must validate the new fixture under the patched schema; no change to its
   scoring semantics.
5. **Source manifest:** `research/source_materials/` and its SHA-256 manifest
   are untouched (this ADR concerns contracts only).

### 3.3 Effects on clients

- Generated clients/validators that currently reject optional-null wrappers
  become consistent with the server. Clients that simply omit optional
  features are unaffected (absent form already valid).
- No wire-behavior change for any request the server previously accepted;
  the only newly *schema*-valid request class is optional-null wrappers,
  which the server already accepted.
- Idempotency is unaffected: canonical payload hashing distinguishes null
  from absent (`backend/CONTRACT_NOTES.md`, idempotency lifecycle), and that
  behavior must not change.
- The M1a.3 handoff's rendering/behavior rules are unaffected.

## 4. Alternatives considered

| Option | Description | Trade-off |
|---|---|---|
| **B. Versioned revision** (e.g. `mock_clinical_feature_schema.v1.1.json` + contract bump) | Keep v1 bytes immutable; publish a corrected schema revision and coordinate clients | Safest for any external consumer treating v1 bytes as immutable; heavier: fixture-pack version bump, oracle/index update, dual-schema support for one placeholder feature set that has no external consumers yet |
| C. Document-only workaround | Tell clients to omit optional features rather than send null | Leaves the schema/runtime inconsistency in an approved artifact; every client must remember a non-obvious rule; rejected |
| D. Tighten the runtime instead (reject optional null) | Make the backend match the strict schema | Changes accepted-wire behavior after clients were handed the M1a.3 contract; contradicts `FeatureValue` prose ("null = not provided"); rejected |

**Recommendation:** Option A, because the affected schemas are the
*mock/provisional* feature schemas (`x-contract-status` marks them
provisional, data-owned and gated — `shared/contracts/README.md` §2.2), no
external consumer contract exists yet, and the change is a pure validity
broadening toward the already-documented semantics. If the maintainer rules
that even provisional published schema bytes are immutable, Option B is the
fallback and must be delivered as its own reviewed change-set.

## 5. Consequences of approving Option A

- Positive: one consistent nullability story across schema, backend, and
  generated clients; removes a client-side footgun before M1a.3 codegen;
  unlocks the Q: "may clients send explicit null for unmeasured optional
  features?" with a tested **yes (equivalent to absent)**.
- Negative/accepted: v1 schema bytes change after the PR #3 freeze; mitigated
  by the fixture + test + revision-note bundle and by the fact that the
  semantic prose never changed.
- Neutral: required-null remains invalid-with-422; zero/false remain data;
  the real feature schemas (`uci_heart_14_v1`, `z_alizadeh_sani_v1`) do not
  exist yet and will be written to this corrected pattern from day one
  (recorded in `docs/blueprint/04_DATABASE_AND_API_INTEGRATION_DESIGN.md`).

## 6. Regression test checklist (acceptance for the implementing PR)

- [ ] `python -m pytest tests/contracts tests/backend -q -W error` green
      (existing counts preserved or increased; nothing deleted).
- [ ] New fixture/step present in `shared/contracts/fixtures/index.json` and
      validated by both oracle and HTTP layers.
- [ ] `test_required_null_optional_null_and_zero_are_distinct` unchanged and
      passing.
- [ ] Required-null still 422 `missing_required_feature` (fixture F-03b
      unchanged).
- [ ] Zero/false still accepted as data.
- [ ] Null vs absent still hash differently under idempotency
      (canonical-payload rule unchanged).
- [ ] `python scripts/verify_sources.py` still passes (4/4 hashes).
- [ ] `docs/DECISIONS.md` records the maintainer decision (approve Option A /
      approve Option B / reject) before the implementing change-set merges.

## 7. Decision record (maintainer answers)

| Question | Maintainer answer |
|---|---|
| Approve Option A (in-place schema-only correction)? | **YES — approved 2026-10-17.** |
| If no: approve Option B (versioned revision) instead? | **NO — Option B not selected.** |
| Target milestone for the approved option (M1a.3 prep vs. M1b)? | **M1a.3 preparation** (client-contract alignment before client code). No M1a.3 implementation authorization is granted by this ADR. |
| Name/ID of the decision entry added to `docs/DECISIONS.md` | **D-044** |
| Sequencing after the implementation audit | **Runtime schema-reader prerequisite first** (separate reviewed PR), then the schema/fixture/test correction. The prerequisite changes no wire behavior; the schema correction is **not yet applied**. |

The runtime prerequisite is documented in
`backend/CONTRACT_NOTES.md` §A-01 and covered by
`tests/backend/test_schema_reader.py`. The schema/fixture correction remains
pending its own review and is not to be described as implemented or merged
until that follow-up PR is merged.
