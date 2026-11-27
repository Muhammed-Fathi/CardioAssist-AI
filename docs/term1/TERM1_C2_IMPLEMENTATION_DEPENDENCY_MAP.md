# CardioAssist-AI Term 1 — C2 Implementation Dependency Map and Owner Decision Register

**Status:** `DOCUMENTATION_ONLY` / `NOT_IMPLEMENTED` / `NOT_AUTHORIZED`.

This document prepares C2. It creates no runtime code, no endpoint, no migration, no
registry entry, no model, no artifact and no test. It trains, generates, loads and executes
nothing. It authorizes nothing. **All four AI gates (A1, A2, A3, B) remain PENDING**, and
Decision A (the umbrella) and Decision B are unresolved. Where this document conflicts
with `TERM1_C0_ARCHITECTURE_AND_CONTRACTS.md`, `TERM1_AI_READINESS_MATRIX.md` or
`TERM1_DECISION_REGISTER.md`, those documents govern and this map is wrong.

**Inputs inspected:** `TERM1_C0_ARCHITECTURE_AND_CONTRACTS.md` (§3 identity, §4 ERD and
data dictionary, §5 constraints, §6 idempotency/secrets, §7 state machines and
concurrency, §8 canonical contract composition, §9 migration ordering),
`TERM1_AI_READINESS_MATRIX.md` (§1 candidates, §2 candidate B, §3 gates A1/A2/A3/B),
`TERM1_API_INTEGRATION_MATRIX.md` (§2 H1a/H1b/S1/S2/S3 and C3 D1–D4/M1–M3/H2/H3, §2.1 field contract, §3
headers/errors/replay), `TERM1_DECISION_REGISTER.md` (P-15, P-16, P-25, P-26, A1/A2/A3/B,
ART), `TERM1_BLOCKER_REGISTER.md` (B-02, B-03, B-05), and the merged C1 implementation
(`backend/app/term1/`, migrations `20261126_02`…`20261126_06`).

---

## 1. What C1 actually delivered, and what C2 may build on

C2 may depend only on what is **implemented and tested** at the merged baseline
`2a8a209`, plus what this closure branch adds. Anything else is a proposal.

| Dependency C2 needs | State at `2a8a209` | Evidence |
|---|---|---|
| Durable accounts, roles, status lifecycle, sessions | IMPLEMENTED / TESTED | migrations `20261126_02`; `tests/backend/c1/test_c1_auth_sessions.py` |
| Permanent opaque subject identity, one account per identity | IMPLEMENTED / TESTED | `patient_identity.canonical_subject_id` UNIQUE across key versions |
| Doctor↔patient assignment with revocation and history | IMPLEMENTED / TESTED | `doctor_patient_assignment`; `GET /v1/me/assignments`; E4/E5 |
| Patient-wide synthetic-demo consent with withdrawal | IMPLEMENTED / TESTED | E1 creates, E6 revokes; checked at enrollment |
| Verified prior visit + invitation + redemption chain | IMPLEMENTED / TESTED | `verified_visit`, `patient_invitation`, `invitation_redemption` |
| Durable idempotency bound to actor/operation/target | IMPLEMENTED / TESTED | `durable_idempotency`; `idempotency.py` |
| Append-only workflow audit | IMPLEMENTED / TESTED | `workflow_audit_event`; `audit.py` |
| Durable operator-key binding (pepper + identity keys) | IMPLEMENTED / TESTED | `identity_key_check`; migration `20261126_06` |
| Canonical served OpenAPI composition from modular source | IMPLEMENTED / TESTED | `openapi.py`; this branch adds `x-error-codes` |
| Exact twenty-operation raw-response/replay/503 proof | IMPLEMENTED / TESTED on this branch | `test_c1_http_closure.py`; see `TERM1_C1_HTTP_CLOSURE_EVIDENCE.md` |
| **Health profile** (`GET/PATCH /v1/me/health-profile`) | **NOT IMPLEMENTED** | no model, no table, no route |
| **Assessment** (`POST /v1/assessments`) | **NOT IMPLEMENTED** | no model, no table, no route |
| **Inference attempt / lease / generation / fence** | **NOT IMPLEMENTED** | no model, no table, no route |
| **Authoritative result publication** | **NOT IMPLEMENTED** | no model, no table, no route |
| **Response projections** (S2 `GET /v1/assessments/{id}`, S3 `GET /v1/me/assessments`) | **NOT IMPLEMENTED** | no model, no table, no route |
| **Serving adapter / registry binding for candidate B** | **NOT IMPLEMENTED** and **NOT AUTHORIZED** | `backend/app/inference/` admits `MOCK_SYNTHETIC` only |
| **Numerical backend dependencies** | **ABSENT by design** | `backend/requirements.txt` has no numpy/scikit-learn/joblib |

Consequence: C2 is **net-new schema, net-new surface and net-new authorization**. It is
not an extension of an existing C2 skeleton, because none exists. That is the single most
important planning fact in this document.

---

## 2. C2 surface to be built (proposed, unapproved)

From `TERM1_API_INTEGRATION_MATRIX.md` §2/§2.1, restated as a dependency-ordered list. H1b
is `PATCH` and H1a is `GET`; they are distinct allowlist operations (C0-F06).

| ID | Operation | Actor | Profile / consent dependency |
|---|---|---|---|
| H1a | `GET /v1/me/health-profile` | Patient, self | assignment + active consent |
| H1b | `PATCH /v1/me/health-profile` | Patient, self, idempotent | immutable version payload from creation; new version supersedes |
| S1 | `POST /v1/assessments` | Patient, self, idempotent | `assignment_id` + `health_profile_id` + panel binding |
| S2 | `GET /v1/assessments/{id}` | Patient owner or doctor via active assignment; no admin clinical access | role-redacted current result; A3 before any score, B additionally before patient score |
| S3 | `GET /v1/me/assessments` | Patient, self | paginated status/history |
| H2/H3 | `GET /v1/me/history`; `GET /v1/doctor/assignments/{assignment_id}/history` | Patient self / doctor via active assignment | C3 longitudinal-history boundary |

C2 owns H1a, H1b, S1, S2, S3 and projection redaction rules. C3 owns D1–D4, M1–M3, H2/H3, review decisions, clinician-authored follow-up and notifications. No invented R1 operation or admin clinical route is approved.

---

## 3. Workstream dependency map

Eight workstreams, each with its hard prerequisites, its observable contract, its failure
mode and the artefacts an independent reviewer needs. The order in §5 is derived from
these edges; no workstream may start before its prerequisites are *accepted*, not merely
merged.

### W1 — Health profiles and synthetic input provenance

| Aspect | Specification |
|---|---|
| Hard prerequisites | C1 identity/assignment/consent **accepted** (done); P-25 migration placement confirmed; this map reviewed |
| New tables | `health_profile` (versioned), `health_profile_field` or JSON column with a frozen field contract, `synthetic_demo_consent` link already exists |
| Immutability rule | profile payload/provenance are immutable from creation; a change creates a new version and supersedes the prior version without rewriting its fields (C0 §5.1) |
| Provenance | **server-assigned only.** `source_contract.source_kind = synthetic_demo_patient_entry`, `term1.synthetic_demo_intake/v1`, acknowledgement id, actor id, panel/schema digest. A client-supplied provenance field is `422`, never silently overridden |
| Panel binding | five-field DA-A2 panel (`age`, `sex`, `cp`, `trestbps`, `restecg`) in that exact order, units `years`/`0|1`/code/`mmHg`/code; reuses `da_a2_resting_v1` only if the owner confirms that reuse (OQ-4) |
| Abstention | absent optional `trestbps`/`restecg` → `ABSTAIN` at S1, no imputation, no zero default. A measured `0` for `trestbps` is *unavailable*, reusing the R1 `ED-DA-A2-01` rule |
| Rejected input | wearable/Track-B payloads, OCR/lab-derived values, outcome-derived fields, real identifiers, real contact info, unit mismatch → fail closed, no score, terminal attempt |
| Observable contract | H1a/H1b served schemas + `x-error-codes`; a snapshot digest that is stable across restarts |
| Failure mode to test | clients trying to set `user_id`, `role`, `status`, provenance, `source_kind`, panel id/version or digest; changing `fields` on a referenced version; absent-vs-zero confusion; units mismatch |
| Reviewer artefacts | migration diff, ERD delta, H1a/H1b schema files, provenance negative tests, restart evidence |

### W2 — Immutable assessment snapshots

| Aspect | Specification |
|---|---|
| Hard prerequisites | W1 accepted; P-15 reassessment rule confirmed |
| New tables | `assessment` (status state machine), `assessment_snapshot` (frozen input bytes + `snapshot_sha256`), `reassessment_of` self-reference + reason |
| Snapshot rule | the snapshot is the **only** input an inference attempt may read. It binds: profile version, panel id + version + digest, ordered inputs, server-assigned provenance, consent id at creation, `snapshot_sha256` |
| Immutability | no `UPDATE` on a written snapshot; corrections create a new assessment with `reassessment_of` |
| Status machine | C0 §7.2: `DRAFT` → `INPUT_VALIDATED` → `INFERENCE_RUNNING` → `INFERENCE_SUCCEEDED` → `PENDING_REVIEW`; terminal `INFERENCE_ABSTAINED`/`INFERENCE_UNAVAILABLE`/`INFERENCE_ERROR` carry no current result and cannot enter review. Without A, terminate unavailable before artifact access. |
| Idempotency | S1 is idempotent; replay identity is actor/operation/target-bound as in C1, with a stable pre-creation target (OQ-7); the recommended existing C1 pattern is `target_ref="none"` for a creation operation, with actor, operation and key in the complete replay identity and assignment/profile/panel/input fields in the keyed request fingerprint |
| Observable contract | `assessment_id`, `status`, `snapshot_sha256`, `attempt_id` |
| Failure mode to test | snapshot mutation attempts, digest mismatch, reassessment without reason, double-create under one key |
| Reviewer artefacts | snapshot immutability proof, digest recomputation, reassessment lineage |

### W3 — Assignment and consent authorization

| Aspect | Specification |
|---|---|
| Hard prerequisites | W1; C1 assignment/consent behaviour (implemented) |
| Rules | every doctor projection re-checks an **active** assignment at read time; revocation removes historical access for that doctor (P-14); a second doctor sees only its own assignment's history; consent withdrawal blocks *new* assessments and is re-checked at **inference completion**, not only at S1 |
| Patient rules | a patient sees only its own profiles/assessments; `assignment_id` selection is mandatory for any doctor-scoped context (P-12) |
| Observable contract | `404` for wrong owner, `403` for wrong role, identical shape to C1; consent withdrawal mid-flight produces no score |
| Failure mode to test | IDOR across assignments, doctor reading an unassigned assessment, revoked-doctor read, consent revoked between S1 and publication, patient attempting a doctor projection |
| Reviewer artefacts | cross-actor matrix, mid-flight consent test, redaction assertions |

### W4 — Inference attempts, leases, generation and fencing

| Aspect | Specification |
|---|---|
| Hard prerequisites | W2 + W3 accepted; **P-16 confirmed** (5 min lease, generation counter, fence token, CAS completion) |
| New tables | `inference_attempt` (one active attempt per assessment); authoritative `lease_until`, `worker_id`, generation and fence in the attempt, with `assessment.active_attempt_id`/`current_generation` per C0 §5/§7.3. No extra lease table without a reviewed schema amendment. |
| Rules | at most one active attempt per assessment; atomic completion must check attempt id/assessment link, active attempt id, current generation, running attempt and assessment states, fence, worker, unexpired lease, active assignment and referenced consent (C0 §7.3). Withdrawn authorization terminates unavailable; expired/superseded/cancelled attempts cannot publish. |
| Provider boundary | the existing `backend/app/inference/` registry admits **`MOCK_SYNTHETIC` only**. C2 must not add an environment-variable, header, settings or DI selector for any other provider. Candidate B admission requires A3 |
| Failure mode to test | two workers racing the same assessment, lease expiry then stale publish attempt, fence mismatch, generation rollback, attempt restart across process restart, and *no* mock fallback when the real adapter is absent |
| Observable contract | `attempt_id`; terminal states carry **no score** on `ABSTAIN`/`UNAVAILABLE`/`ERROR` |
| Reviewer artefacts | concurrency test log, restart-recovery test, negative provider-selection tests |

### W5 — Authoritative result publication

| Aspect | Specification |
|---|---|
| Hard prerequisites | W4; Decision A for any real-model result; Decision B for any patient-visible score |
| New tables | `inference_result` (single authoritative row per assessment), explanation rows |
| Rules | exactly one authoritative result per assessment; later attempts supersede by generation, and history is retained but not served as current; publication is idempotent; publication re-checks assignment + consent |
| Score semantics | `CALIBRATED_RESEARCH_SCORE_SYNTHETIC` in `calibrated_log_odds`, labelled `RESEARCH_ONLY_NOT_INDIVIDUAL_CLINICAL_RISK`; never a CAD probability, future-event risk, diagnosis or treatment advice |
| Without Decision A | proposed owner-authorized `C2_SAFE_SCOPE`: status-only, `INFERENCE_UNAVAILABLE`, no result row, no artifact access, no adapter reachable. No full C2 acceptance or review eligibility may be claimed. OQ-5 still requires explicit confirmation. |
| Failure mode to test | duplicate publication, stale publication, tampered artifact/wrong digest, wrong panel, wrong source kind, unauthorized flag/header/env bypass, and no fallback to the M1 mock |
| Reviewer artefacts | single-result proof, supersession proof, tamper-refusal log, A/B status recorded |

### W6 — Restart and failure recovery

| Aspect | Specification |
|---|---|
| Hard prerequisites | W4 + W5 |
| Rules | a restart mid-lease must not double-publish; an expired lease must be reclaimable without data loss; snapshots and published results survive restart unchanged; the durable idempotency record must still replay after restart with the same body |
| Failure mode to test | crash between snapshot write and attempt creation; crash between attempt completion and publication; restart with a stale fence; operator key material unchanged across restart (C1 behaviour must still hold) |
| Reviewer artefacts | restart transcript, post-restart idempotent replay, post-restart snapshot digest equality |

### W7 — Doctor and patient response projections

| Aspect | Specification |
|---|---|
| Hard prerequisites | W5 + W3 |
| Rules | the doctor projection requires an active assignment; patient projection is self-only. Before A3 both expose status only. After A3 an authorized doctor may see the reviewed research-only fields under the governing C0 projection; the patient remains status-only until the separate B grant. After B, patient-visible fields and wording must exactly match the ratified contract. No admin clinical projection. |
| Redaction | no raw identifier, no HMAC, no verifier, no other patient's identifiers, no provenance secret, no artifact bytes, no digest of a private bundle in any projection |
| Failure mode to test | cross-role projection, cross-assignment projection, score present before B, score absent after A3+B for the correct actor, wording mismatch |
| Reviewer artefacts | projection matrix per role, redaction scan, B-status assertion |

### W8 — Candidate B model development requirements

Requirements only. **Nothing here is executed, and none of it may be executed before A1.**

| Requirement | Detail |
|---|---|
| Development scope | exactly `term1_synthetic_demo_inference_v1` / `synth_term1_demo_da_a2_v1` v0.1.0, trained **only** on a deterministic synthetic cohort from a pinned generator (function path, seed, row count recorded), inside the offline local research workspace and nowhere else |
| Prohibited in A1 | hosted HTTP serving, backend provider activation, CI artifact distribution, patient exposure, real-data fitting, private Cleveland bundle, any execution outside that offline synthetic environment |
| Ordered schema | `age` years; `sex` 0/1; `cp` 1..4; `trestbps` mmHg; `restecg` 0..2, in that order — never invented fields, never source translation |
| Determinism | pinned package versions, seed, row count, fold protocol, calibration and code revision. Cross-platform byte identity is **not assumed**; a differing digest is a **blocked verification result**, not a green one, and requires an owner decision on a curated bundle |
| Explanation | genuine same-model exact grouped SHAP on the declared scale; optional LIME only on the same scale and background and only with an acceptable quality verdict. No mock-shaped explanation may ever be relabelled as genuine |
| Dependencies | numerical pins added to `backend/requirements.txt` only under A, with separate approval and `pip check` evidence; today that file has none of them |
| Trust / distribution | deterministic rebuild preferred over a committed bundle; `.gitignore` already excludes artifacts; any handed-off bundle needs redistribution rights and must not carry a private key |
| Reproducibility | frozen synthetic oracle, repeated-run digest equality, tamper/wrong-digest/wrong-panel refusal, unauthorized flag/header/env bypass tests |
| Scientific limits | cross-sectional synthetic-only; no real-person validation; not future-event risk; not diagnosis; never authors a prescription or treatment recommendation |

---

## 4. Separate authorization gates — all PENDING

| Gate | Grants | Blocking artefacts | Current state |
|---|---|---|---|
| **A1** | Synthetic-data generation, fitting/calibration and offline testing of candidate B **inside the offline research workspace only** | W8 requirements accepted; owner token `AUTHORIZE-TERM1-CANDIDATE-B-DEVELOPMENT-ONLY` | **PENDING** — no generation, training or execution |
| **A2** | Independent verification of the exact implementation, generator hash, seed, row count, protocol, panel digest, pins, artifact SHA-256, rebuild, oracle, tamper refusal and explanation quality | A1 output + full diff | **PENDING** |
| **A3** | Controlled local-demo activation through a reviewed registry binding to the exact digest | A1 + A2 evidence; owner token `AUTHORIZE-TERM1-CANDIDATE-B-LOCAL-DEMO-ACTIVATION` | **PENDING** — adapter disabled |
| **B** | Patient-facing provisional synthetic score with ratified wording/redaction | A3 (any score) + owner token `AUTHORIZE-TERM1-SYNTHETIC-PATIENT-SCORE-DISPLAY` | **PENDING** — patient sees status only |

Decision A (umbrella) is satisfied only when A1, A2 and A3 are each satisfied. B is
independent and cannot be inferred from A1, A2, A3 or from a merge, a CI result or an
acceptance comment about a different stage. **All four remain PENDING at the time of
writing.**

---

## 5. Required build order

Dependency-correct, each step blocked by the previous acceptance (not merely a merge):

```
C1 closure accepted (this branch, independent review)
  └─ W1 health profile + provenance  [needs OQ-1, OQ-4]
       └─ W2 assessment snapshot     [needs OQ-2, OQ-7]
            └─ W3 assignment/consent authorization  [stdlib only]
                 └─ W4 attempts/leases/fencing      [needs OQ-3 = P-16 confirm]
                      └─ W5 publication             [needs C2_SAFE_SCOPE default, OQ-5]
                           ├─ W6 restart recovery
                           └─ W7 projections         [score only after A3+B]
  W8 model development  [strictly after A1; never a C2 code dependency]
  A1 → A2 → A3 → B      [strictly ordered, each owner-ratified]
```

W1…W7 are buildable **without any AI authorization** in `C2_SAFE_SCOPE`: profiles,
snapshots, authorization, attempts, leases, fencing, publication-of-status and
projections are all ordinary software. Only a *score* needs A3, and only a *patient-visible*
score needs B. This is the decisive scoping insight: **C2 is not blocked on the AI gates;
a full-score C2 is.**

---

## 6. Owner decisions required before implementation

Each is a real fork with a real cost. None is inferable from the merged C1 baseline.

| ID | Decision | Options | Consequence of deferring | Blocks |
|---|---|---|---|---|
| **OQ-1** | C2 scope under unresolved Decision A | (a) `C2_SAFE_SCOPE` only, documented and recorded as AI-BLOCKED; (b) wait for A1–A3 before any C2 code | (a) C2 ships a status-only surface with an empty score column and no adapter; (b) C2 does not start | W1…W7 start |
| **OQ-2** | Snapshot representation | (a) canonical JSON bytes with `snapshot_sha256`; (b) normalized child rows plus a digest | changes the whole W2/W5 schema and the digest provenance | W2 |
| **OQ-3** | Confirm P-16 lease/fence parameter values | 5-minute lease, generation counter, fence token, CAS | concurrency tests have no frozen target | W4 |
| **OQ-4** | Reuse `da_a2_resting_v1` for candidate B | (a) reuse the panel contract + `contract_sha256`; (b) define a C2-specific panel contract | a new panel contract needs its own review and digest | W1, W8 |
| **OQ-5** | Publication semantics without A | (a) `INFERENCE_UNAVAILABLE` terminal status, no result row; (b) result row with `status` and a null score | (a) simplest and provably score-free; (b) needs a nullable-score column and a proof it can never be non-null pre-A3 | W5 |
| **OQ-6** | Numeric dependency admission (B-05 / ART) | (a) deterministic rebuild with pinned numerical deps; (b) curated signed bundle with pinned digest | no adapter can be admitted under A3 | W8, A3 |
| **OQ-7** | S1 replay identity before the target exists | (a) derive `target_ref` from `(actor, idempotency key)`; (b) two-phase create with a client-supplied draft id | S1 cannot be made idempotent without a decision | W2 |
| **OQ-8** | Whether C2 may add the `health_profile`/`assessment` migrations in one PR | (a) one C2 migration block as P-25 states; (b) split per workstream | a split needs an explicit migration-ordering amendment | all |
| **OQ-9** | Display wording finalisation | the AI matrix §3.2 text vs an owner edit | B cannot be ratified with unapproved wording | B |
| **OQ-10** | Windows + hosted CI evidence route for C2 | owner dispatch on the C2 PR (B-16) | no C2 acceptance is possible | C2 acceptance |

---

## 7. Non-authorizations restated

This document does **not**: implement C2; add a migration; add a route; add a settings key;
add a numerical dependency; create, train, generate, load or execute a model; create or
copy an artifact or registry entry; enable any provider other than `MOCK_SYNTHETIC`; change
any AI gate; waive any blocker; change `research/`, PR #141 or Issue #132; change
`delivery/term1-prototype` or `main`; or approve, merge or self-approve anything.

A1, A2, A3 and B remain **PENDING**. Gate PT P-1 remains PENDING, P-3 CLOSED, P-5
prohibited. B-01, B-09, B-17 and B-18 (the separate RH-04 / Issue #132 research track)
remain open and are untouched.


## Independent reviewer clarification (proposed, not authorization)

The preceding corrections reconcile the dependency map with the governing C0 design. OQ-7 should also explicitly consider the existing C1 create-operation `target_ref="none"` pattern, with actor-local scope and full request fingerprint; neither a client-draft protocol nor a new key-derived target is established. OQ-3 and OQ-8 must distinguish already accepted P-16/P-25 defaults from any proposed amendment. Keep A1 offline numerical dependencies separate from backend admission under A3; no private artifact or real patient data. An owner-authorized safe-scope implementation and an independently authorized offline A1 development stream may be planned in parallel, but neither starts from this document. No full C2 or clinical-readiness claim without its applicable gates. The final decision register must be reconciled before implementation.
