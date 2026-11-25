# CardioAssist-AI Term 1 — C0 Architecture, Data Model, Threat Model and Contracts

**Status:** `PROPOSED_C0_DEFAULT` design; no implementation, migration, runtime contract, test or workflow change is authorized by this document.
**Base:** prototype HEAD `bca75b4646dbde26e495201938b7ae01ea7e0d21`; main `c6a6bdee46a552a2b0d705a723c862ff8a95be4d`.
**Companion documents:** `TERM1_API_INTEGRATION_MATRIX.md`, `TERM1_AI_READINESS_MATRIX.md`, `TERM1_DECISION_REGISTER.md`, `TERM1_WINDOWS_VERIFICATION_RUNBOOK.md`.

## 1. Architecture summary

```
Browser/Flutter client (software team)
        │ relative /v1 URLs, Bearer session header
        ▼
FastAPI (existing app, additive Term-1 router)
  ├─ Identity & Session (auth, RBAC, object-level via assignments)
  ├─ Visit & Invitation (attestation, HMAC subject binding, one-time code)
  ├─ Enrollment (atomic registration/link, assignment, consent)
  ├─ Assessment & Provenance (immutable snapshot, source contract)
  ├─ Policy-Gated Inference Adapter (DISABLED until Decision A)
  ├─ Review & Follow-up (append-only, clinician-authored only)
  └─ Notification / History (role-redacted projections)
        ▼
SQLAlchemy repositories ──► SQLite (WAL, FK on, explicit transactions)
        ▼
Alembic revisions (explicit upgrade; read-only startup verification)
```

**Preserved legacy boundaries:** `POST /v1/predictions/cad-tabular` stays `MOCK_SYNTHETIC`; `POST /v1/monitoring/observations` keeps its three-table persistence and success audit. The offline `ai/` package remains isolated from `backend/app/` under RD-09. No new prediction-like route may call the mock provider.

## 2. Threat model and mitigations (C0)

| Threat | Mitigation | Stage |
|---|---|---|
| Real identifiers/PHI enter Arena, Git, logs, CI | Demo-only identifier grammar `DEMO-ID-nnn`; rejection of production-format IDs; no raw identifier in logs/API/audit/fixtures; HMAC-only matching | C0/C1 |
| Attacker guesses or replays invitation codes | 256-bit CSPRNG, stored verifier, one-time disclosure, 24h TTL, revoke, bounded attempts, durable attempt counters, atomic consume | C1 |
| Invitation from visit A used for patient B | Visit stores subject HMAC; invitation inherits it; registration computes HMAC with invitation's `key_id`; mismatch fails generically | C1 |
| Cross-doctor / cross-patient access (IDOR) | Authorization via active `doctor_patient_assignment` + assessment `assignment_id`; no `patient.doctor_id`; object checks in every query | C1–C3 |
| Account existence enumeration | Generic login/invitation/link errors, uniform delay and `Retry-After` after threshold, no differentiated timing where practical | C1 |
| Password/session/token leakage into idempotency records or logs | Hash-only storage; redacted replay bodies; one-time secret non-redisclosure; structured redaction tests | C1 |
| Concurrent double redemption / duplicate accounts | Conditional UPDATE rowcount + UNIQUE constraints + bounded retry; independent-connection race tests | C1 |
| Stale or fabricated model results | Single authoritative result row, generation/fence CAS, snapshot/model/source digests, no mock fallback, Decision A gate | C2 |
| Patient sees research score before Decision B | Server-side role projection with explicit allowlist fields; negative tests on every patient-facing route | C2/C3 |
| AI authors prescription | Prescription table has `author_user_id` FK to doctor; no AI principal can be author; schema check + tests | C3 |
| Partial follow-up/notification writes | One transaction for message+notification+audit+idempotency; rollback test | C3 |
| Schema drift/destructive migration | Read-only startup verification; explicit Alembic upgrade; downgrade only on disposable DB; no `create_all`/repair | C1–C4 |
| Privilege persistence after revocation | Assignment `revoked_at` checked at authorization time; historical records retain original assignment; new doctors cannot read unrelated history | C1/C3 |
| Unauthorized inference via env/header | Adapter construction has no selector; authorization recorded in signed registry/evidence, not runtime flags; tests attempt bypass | C2 |

## 3. Authentication, session and enrollment design

### 3.1 Admin bootstrap and account lifecycle

- No HTTP admin-signup endpoint. Operator creates the first admin with a local, repository-excluded bootstrap mechanism (proposed CLI reading `CARDIOASSIST_ADMIN_BOOTSTRAP_SECRET` from environment; one-time, high entropy). No default credentials, no committed secret.
- Admin provisions doctors via `POST /v1/admin/doctors`; doctor accounts start `ACTIVE` with a temporary password that must be changed at first successful login (server enforces `password_change_required`; UI is P1 only if owner explicitly defers it).
- `user_account.status ∈ {ACTIVE, SUSPENDED, DISABLED}`. Suspension revokes sessions and blocks login; disabled is terminal for the demo (no hard delete in Term 1). Admin can change status via `PATCH /v1/admin/accounts/{user_id}/status`.
- Password change: `POST /v1/me/password` requires current password, applies KDF parameters from P-01/P-02, revokes all other sessions, writes workflow audit.
- Lockout: five failed logins per 15 min per HMAC(email)+IP bucket → 15 min lock; generic `401 invalid_credentials` and uniform `Retry-After` on all failures after threshold, so lockout does not reveal account existence. Durable failure rows are written outside the business transaction.

### 3.2 Password hashing and verification

```
salt = secrets.token_bytes(16)
dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 600000, dklen=32)
stored = {"alg":"pbkdf2_hmac_sha256","v":1,"iterations":600000,
          "salt_b64":..., "verifier_b64":...}
```

Verification recomputes with stored parameters and uses `hmac.compare_digest`. Stored parameters allow a future iteration increase without breaking existing accounts. No new dependency is required; if the owner prefers Argon2id, that requires a new pinned dependency and a separate decision.

### 3.3 Sessions

- Token: 32-byte CSPRNG, base64url without padding; raw token returned once in login response; store only `token_verifier_sha256` and `key_id`.
- Transport: bearer in `Authorization: Bearer <token>`; no cookies in Term 1, therefore no cookie-CSRF surface. CORS is off unless the owner supplies an explicit origin allowlist; browser clients use same-origin relative `/v1` paths through a dev proxy. Flutter stores the token using platform secure storage.
- Absolute lifetime 8 h, idle 30 min; rotation on login and password change; `POST /v1/auth/logout` revokes current session; `POST /v1/auth/me/sessions` (optional proposed) lists sessions and `DELETE /v1/auth/me/sessions/{id}` revokes one; admin status change revokes all for that user.
- No session token appears in any idempotency record, response replay body, log line, audit payload, or fixture.

### 3.4 Verified visit and identity binding (`R-02`)

- `verified_visit` is created by a doctor for an already occurred visit. It stores `doctor_id` (FK), `subject_identifier_hmac`, `identifier_key_id`, `visit_ref`, `asserted_visit_at` (clinician-stated time), `attested_at` (server UTC, authoritative), and `attestation_code` from a closed enum: `PRIOR_IN_PERSON_VISIT_DEMO` or `PRIOR_TELEHEALTH_VISIT_DEMO`. Free-text clinical narrative is not accepted in demo attestation; an optional bounded `note_code` may be added later with owner review.
- Subject HMAC is computed at attestation time from the normalized fictitious identifier; the same HMAC is copied to every invitation for that visit. The server refuses an invitation issue whose subject HMAC differs from the visit's; this prevents patient B's code from patient A's visit.
- Normalization: trim surrounding whitespace, uppercase ASCII, strict regex `^DEMO-ID-[0-9]{3,6}$`, reject anything else including 14-digit national-ID-shaped input.
- HMAC encoding: `HMAC-SHA256(key, b'invitation-subject-match/v1' + b'\x00' + normalized_id.encode('ascii'))`, lowercase hex. Purpose string is distinct from any other HMAC use. Key id is stored with the digest; matching uses the invitation's recorded key id.
- Term 1 uses one demo key `demo-v1`, operator-supplied, never committed. Rotation procedure: create `demo-v2`, issue new invitations only with the new key, retain old key only to verify existing invitations; existing subjects require new attestation+invitation to link under the new key. No silent cross-key matching and no raw identifier storage.
- Identifier matching is a demo binding only; it is not government identity verification or proof of attendance. The attestation is the evidence of a prior visit.

### 3.5 Invitation and redemption

- Token: 32-byte CSPRNG; plaintext displayed exactly once at `POST /v1/doctor/verified-visits/{id}/invitations`; only verifier hash stored. TTL default 24 h (owner may set 1–72 h). Revocation via `POST /v1/doctor/invitations/{id}/revoke`, idempotent, allowed only by the doctor owning the visit.
- Redemption for a **new** patient: `POST /v1/patients/register` with `{access_code, identifier, email, password, consent_ack}`. One transaction: conditional consume (`consumed_at IS NULL AND revoked_at IS NULL AND expires_at > now`), HMAC verify, create `user_account` + `patient_identity` + `patient_profile` + `doctor_patient_assignment` + `consent_record`, write idempotency and success audit. Any mismatch yields generic `401 invalid_invitation`.
- Redemption for an **existing** patient: `POST /v1/patients/link`, authenticated, with `{access_code, identifier, accept_linking:true}`. The invitation subject HMAC must equal the authenticated patient's identity HMAC; no second account is created; a new `doctor_patient_assignment` row is created and the invitation consumed atomically. Mismatched subject → generic `401 invalid_invitation`.
- Repeat visits create a new `verified_visit` and new invitation. A second invitation is allowed only after the prior one is expired/revoked/consumed; duplicate active invitations for one visit → `409 invitation_already_active`.
- Duplicate fictitious identifier: only one `patient_identity` per `(key_id, identifier_hmac)`; a second new-patient registration with the same subject requires the authenticated link flow, not a new account.
- Concurrent redemption: conditional UPDATE rowcount check plus unique constraints; two independent connections race → exactly one success; loser receives generic failure or `409 concurrency_conflict` after bounded retry. SQLite has no `SELECT ... FOR UPDATE` assumption.

### 3.6 RBAC and object-level authorization (`R-01`)

- There is **no** `patient.doctor_id`. Doctor access is through active `doctor_patient_assignment` rows. Assessment rows bind the `assignment_id` that was active at creation.
- Every doctor-scoped operation includes `assignment_id` in the path or query and verifies `assignment.doctor_id == current_user.doctor_id AND revoked_at IS NULL`. Patient-scoped operations verify `assignment.patient_id == current_user.patient_id`.
- When a patient has multiple active assignments, the client must select one; `GET /v1/me/assignments` returns eligible assignment IDs. If a doctor-scoped patient context is ambiguous, server returns `409 assignment_selection_required` with only IDs and labels, no clinical data.
- Revocation sets `revoked_at`; authorization checks it on every request. Historical assessments/messages retain their original `assignment_id`; a revoked doctor loses access to them, and a newly assigned doctor cannot read records tied to a different assignment. Restoring historical access requires a separately recorded grant, not implicit role membership.
- Admin has no clinical payload access by default. Patient can never access another patient's objects. Wrong owner returns `404` consistently.

## 4. Proposed ERD

```
user_account (PK user_id UUID str, role CHECK, status CHECK,
              password_alg/version/iterations/salt_b64/verifier_b64,
              password_change_required BOOL, created_at, password_changed_at,
              failed_count, locked_until)
   │ 1:0..1
   ├── doctor_profile (PK doctor_id, FK user_id UNIQUE, display_name, active)
   └── patient_profile (PK patient_id, FK user_id UNIQUE,
                        FK patient_identity_id UNIQUE, display_label, created_at)
   │ 1:*
   └── session (PK session_id, FK user_id, token_verifier_sha256 UNIQUE,
                key_id, created_at, expires_at, last_seen_at, revoked_at)

patient_identity (PK identity_id, identifier_key_id, identifier_hmac,
                  canonical_subject_id UNIQUE, created_at;
                  UNIQUE(identifier_key_id, identifier_hmac))
   │ 1:*
   └── patient_profile (see above; exactly one active profile per identity)

verified_visit (PK visit_id, FK doctor_id, visit_ref UNIQUE(doctor_id,visit_ref),
                subject_identifier_hmac, identifier_key_id,
                asserted_visit_at, attested_at, attestation_code CHECK, note_code NULL)
   │ 1:*
   └── patient_invitation (PK invitation_id, FK visit_id, FK issued_by_user_id,
                token_verifier_sha256 UNIQUE, subject_identifier_hmac,
                identifier_key_id, issued_at, expires_at, consumed_at, revoked_at,
                attempt_count, max_attempts, CHECK not both consumed and revoked)

patient_invitation 1:0..1 invitation_redemption (PK redemption_id,
                FK invitation_id UNIQUE, FK patient_id, FK assignment_id,
                redeemed_at, flow CHECK {register, link})
patient_invitation 1:* invitation_attempt (PK attempt_id, FK invitation_id,
                bucket_key_hash, outcome_code, created_at; metadata only)

doctor_patient_assignment (PK assignment_id, FK doctor_id, FK patient_id,
                assigned_at, revoked_at, revoked_by_user_id, reason_code;
                UNIQUE(doctor_id, patient_id) WHERE revoked_at IS NULL)

consent_record (PK consent_id, FK patient_id, kind CHECK {synthetic_demo},
                acknowledged_at, revoked_at, contract_version)
health_profile (PK profile_id, FK patient_id, schema_version, payload_json,
                provenance_json, created_at, superseded_at)

assessment (PK assessment_id, FK patient_id, FK assignment_id,
            FK consent_id, FK health_profile_id, panel_id, panel_version,
            status, source_contract_version, created_at,
            reassessment_of FK assessment NULL, reason_code)
   │ 1:1
   └── assessment_snapshot (PK snapshot_id, FK assessment_id UNIQUE,
            canonical_json, payload_sha256, provenance_json,
            schema_sha256, panel_sha256, created_at; immutable)
   │ 1:*
   ├── inference_attempt (PK attempt_id, FK assessment_id, generation INT,
   │       idempotency_key_hash UNIQUE, state, lease_until, fence_token,
   │       worker_id, requested_at, finished_at, error_code NULL,
   │       UNIQUE(assessment_id, generation))
   │       │ 1:0..1
   │       └── inference_result (PK result_id, FK attempt_id UNIQUE,
   │             FK assessment_id, generation, snapshot_sha256,
   │             model_id, model_version, artifact_sha256, source_binding,
   │             score_kind, score_json, explanation_json, explanation_method,
   │             background_id, result_sha256, recorded_at)
   │ 1:*
   ├── assessment_review (PK review_id, FK assessment_id, FK assignment_id,
   │       FK reviewer_user_id, decision CHECK, reason_code, rationale,
   │       recorded_at, idempotency_key_hash UNIQUE; append-only)
   └── follow_up_message (PK message_id, FK assessment_id,
           FK author_user_id (doctor), body, prescription_json,
           created_at, idempotency_key_hash UNIQUE)
          │ 1:*
          └── notification_record (PK notification_id, FK recipient_user_id,
                 FK message_id, type, created_at, read_at, idempotency_key_hash UNIQUE)

durable_idempotency (PK scope, key_hash, actor_user_id, operation, target_ref,
                     request_sha256, response_public_json, status_code,
                     created_at, expires_at, secret_disclosed BOOL)
workflow_audit_event (PK audit_id, event_type, actor_user_id NULL,
                     subject_type, subject_id, request_id, payload_sha256,
                     code, outcome, recorded_at)
login_attempt (PK attempt_id, bucket_key_hash, outcome, created_at)  // failure counters
```

## 5. Data dictionary and constraints

### 5.1 Core required/optional fields

| Table | Required | Optional | Constraints / notes |
|---|---|---|---|
| `user_account` | user_id, role, status, KDF fields, created_at | password_changed_at, locked_until | `role IN ('admin','doctor','patient')`; `status IN ('ACTIVE','SUSPENDED','DISABLED')`; verifier never contains raw password |
| `doctor_profile` | doctor_id, user_id, display_name, active | — | FK user_id UNIQUE; display_name ≤128 chars, no identifiers |
| `patient_profile` | patient_id, user_id, patient_identity_id, display_label, created_at | — | FK both UNIQUE; one account per identity |
| `session` | session_id, user_id, token_verifier_sha256, key_id, created_at, expires_at | last_seen_at, revoked_at | token verifier UNIQUE; no raw token column |
| `patient_identity` | identity_id, identifier_key_id, identifier_hmac, canonical_subject_id, created_at | — | UNIQUE(key_id, hmac), UNIQUE(canonical_subject_id) |
| `verified_visit` | visit_id, doctor_id, visit_ref, subject_identifier_hmac, identifier_key_id, asserted_visit_at, attested_at, attestation_code | note_code | UNIQUE(doctor_id, visit_ref); no free clinical text |
| `patient_invitation` | invitation_id, visit_id, issued_by_user_id, token_verifier_sha256, subject_identifier_hmac, identifier_key_id, issued_at, expires_at, max_attempts | consumed_at, revoked_at | UNIQUE token verifier; CHECK not both consumed/revoked; FK visit_id and issued_by_user_id only |
| `invitation_redemption` | redemption_id, invitation_id, patient_id, assignment_id, redeemed_at, flow | — | FK invitation_id UNIQUE; flow enum |
| `doctor_patient_assignment` | assignment_id, doctor_id, patient_id, assigned_at | revoked_at, revoked_by_user_id, reason_code | Partial UNIQUE active pair; no patient.doctor_id |
| `consent_record` | consent_id, patient_id, kind, acknowledged_at, contract_version | revoked_at | kind only `synthetic_demo` in Term 1 |
| `health_profile` | profile_id, patient_id, schema_version, payload_json, provenance_json, created_at | superseded_at | immutable once created; new version supersedes |
| `assessment` | assessment_id, patient_id, assignment_id, consent_id, health_profile_id, panel_id, panel_version, status, source_contract_version, created_at | reassessment_of, reason_code | FK assignment binds authorization scope |
| `assessment_snapshot` | snapshot_id, assessment_id, canonical_json, payload_sha256, provenance_json, schema_sha256, panel_sha256, created_at | — | FK assessment UNIQUE; append-only/immutable |
| `inference_attempt` | attempt_id, assessment_id, generation, idempotency_key_hash, state, lease_until, fence_token, requested_at | finished_at, error_code, worker_id | UNIQUE(assessment_id, generation), UNIQUE key hash; no score/explanation columns |
| `inference_result` | result_id, attempt_id, assessment_id, generation, snapshot_sha256, model_id, model_version, artifact_sha256, source_binding, score_kind, score_json, explanation_json, explanation_method, background_id, result_sha256, recorded_at | — | FK attempt UNIQUE; one authoritative representation |
| `assessment_review` | review_id, assessment_id, assignment_id, reviewer_user_id, decision, reason_code, rationale, recorded_at, idempotency_key_hash | — | append-only; decision enum |
| `follow_up_message` | message_id, assessment_id, author_user_id, body, prescription_json, created_at, idempotency_key_hash | — | author must be doctor; AI cannot author |
| `notification_record` | notification_id, recipient_user_id, message_id, type, created_at, idempotency_key_hash | read_at | message nullable for system notices; one per recipient/message |
| `durable_idempotency` | scope, key_hash, actor_user_id, operation, target_ref, request_sha256, response_public_json, status_code, created_at, expires_at, secret_disclosed | — | key_hash never raw; response redacted |
| `workflow_audit_event` | audit_id, event_type, subject_type, subject_id, payload_sha256, code, outcome, recorded_at | actor_user_id, request_id | metadata only; no identifiers/secrets |
| `login_attempt` | attempt_id, bucket_key_hash, outcome, created_at | — | bucket key HMAC(email)+IP prefix; written outside rolled-back business tx |

### 5.2 Indexes referencing actual columns

- `ix_user_account_status_role` on `user_account(status, role)`.
- `ix_session_user_expires` on `session(user_id, expires_at)`; UNIQUE on `token_verifier_sha256`.
- `ix_verified_visit_doctor_time` on `verified_visit(doctor_id, attested_at)`; UNIQUE `(doctor_id, visit_ref)`.
- `ix_invitation_visit_expiry` on `patient_invitation(visit_id, expires_at)`; `ix_invitation_subject` on `(identifier_key_id, subject_identifier_hmac)`; UNIQUE `token_verifier_sha256`.
- `ix_assignment_patient_active` on `doctor_patient_assignment(patient_id, revoked_at)`; partial UNIQUE `(doctor_id, patient_id) WHERE revoked_at IS NULL`.
- `ix_assessment_patient_created` on `assessment(patient_id, created_at)`; `ix_assessment_assignment_status` on `(assignment_id, status)`.
- `ix_inference_attempt_assessment_state` on `inference_attempt(assessment_id, state)`; UNIQUE `(assessment_id, generation)`.
- `ix_review_assessment_recorded` on `assessment_review(assessment_id, recorded_at)`.
- `ix_notification_recipient_read` on `notification_record(recipient_user_id, read_at, created_at)`.
- `ix_workflow_audit_subject_time` on `workflow_audit_event(subject_type, subject_id, recorded_at)`.
- `UNIQUE(scope, key_hash)` on `durable_idempotency`; `UNIQUE(key_id, identifier_hmac)` on `patient_identity`.

No index references a nonexistent `doctor_id` on invitations or a `status` column on sessions.

### 5.3 Legacy tables preserved

`monitoring_observation`, `monitoring_metric`, `audit_event` and migration `20261017_01` remain unchanged. `audit_event.observation_record_id` stays NOT NULL with FK to `monitoring_observation.record_id` and UNIQUE per observation. Workflow events use `workflow_audit_event`; no fake monitoring rows are created.

## 6. Transaction boundaries, idempotency and secret safety (`R-04`)

### 6.1 Durable idempotency record

`durable_idempotency` stores only:

- `scope` (e.g. `invitation_issue`, `enrollment`, `assessment_create`, `review`, `follow_up`),
- `key_hash = SHA256(pepper || idempotency_key)`, never the raw key,
- `actor_user_id`, `operation`, `target_ref`, `request_sha256`,
- `response_public_json` — **redacted** projection containing no access code, password, session token, bearer value, HMAC secret, or full credential-bearing response,
- `status_code`, `created_at`, `expires_at`, `secret_disclosed`.

Rules:

1. A write with the same `(scope, key_hash)` and same `request_sha256` is a replay: return the stored **redacted** response with `idempotent_replay: true`. It never re-executes effects.
2. Same key with different payload → `409 idempotency_key_conflict`, evaluated before semantic validation where the legacy contract requires conflict precedence.
3. One-time secrets (access codes, session tokens) are returned only in the original response. Replay returns the same public fields with `secret_disclosed` noted and **no secret**. If the client lost a code, it must ask the doctor to revoke/reissue; if it lost a session token, it must log in again.
4. `POST /v1/patients/register` replay never mints a second session or account; it returns the original patient/assignment identifiers only.
5. Failed enrollment attempts increment `invitation_attempt outcome=failure` and `login_attempt` in a **separate transaction after rollback**; privacy-safe rate-limit keys are HMAC-derived and metadata-only.
6. A database key provides at-most-once replay within its scope and TTL; it is **not** a claim of distributed exactly-once execution. Single Uvicorn worker is required for Term 1.

### 6.2 Audit failure handling

Success workflow audit rows are inserted in the same transaction as the business effect. Failure audit rows are inserted in a separate transaction after rollback, with event type, actor id, subject type/id, redacted code, outcome and payload hash. If the failure-audit insert itself fails, the request still fails and the incident is logged at `ERROR` with metadata only; no retry loop masks the original failure.

## 7. State machines

### 7.1 Profile

`DRAFT → COMPLETE → SUPERSEDED(by new version)`. A profile linked to an immutable assessment snapshot cannot be mutated; changes create a new `health_profile` row.

### 7.2 Assessment and inference

```
DRAFT --consent+valid snapshot--> INPUT_VALIDATED
INPUT_VALIDATED -> INFERENCE_RUNNING (durable attempt, generation N, lease)
INFERENCE_RUNNING -> INFERENCE_SUCCEEDED -> PENDING_REVIEW
INFERENCE_RUNNING -> INFERENCE_ABSTAINED | INFERENCE_UNAVAILABLE | INFERENCE_ERROR
any terminal failure -> no current result; history attempt retained
```

Only `INFERENCE_SUCCEEDED` with a durable `inference_result` may enter `PENDING_REVIEW`. Failure/unavailability/abstention/error never enter review and never expose a score. Decision A absent → `INFERENCE_UNAVAILABLE`. No mandatory doctor confirmation before inference.

### 7.3 Inference concurrency, fencing and recovery (`R-05`)

- Each attempt has `generation`, `lease_until`, `fence_token`, `worker_id`. Only one active attempt per assessment+generation; recovery increments generation.
- Completion is conditional: `UPDATE inference_attempt SET state='INFERENCE_SUCCEEDED' WHERE attempt_id=? AND generation=? AND state='INFERENCE_RUNNING' AND fence_token=?` followed by `INSERT inference_result` in the same transaction with `rowcount==1` check. A late worker whose lease expired cannot publish; it receives `409 stale_attempt`.
- A startup/recovery task scans attempts with `lease_until < now AND state='INFERENCE_RUNNING'`, marks them `INFERENCE_ERROR` (authoritative history), clears any current-result projection for that assessment, and may create a new attempt with generation+1 if an idempotent retry is requested. It never fabricates a result and never silently repairs schema.
- `inference_result` is the only authoritative score/explanation representation. `inference_attempt` stores status/error metadata only. Stale/failed current results are hidden from projections; historical evidence rows remain intact.
- Result binds `snapshot_sha256`, `model_id/version`, `artifact_sha256`, `source_binding`, panel/schema hashes; mismatch fails closed.

### 7.4 Review, follow-up and notification

- Review state: `NOT_REVIEWED → ACCEPTED | REJECTED | REASSESSMENT_REQUESTED`. Each review action is append-only with `assignment_id`, reviewer id, reason code, rationale and idempotency key. Duplicate key replay returns previous public result; conflicting decision for same assessment+key → `409 review_conflict`; illegal transition → `409 review_transition_conflict`. Concurrent reviews use conditional update on current state; loser receives `409`.
- Follow-up eligibility: assessment must have a successful result and an existing review action by the assigned doctor; AI-authored follow-up is impossible because `author_user_id` must resolve to a doctor user. `POST /v1/assessments/{id}/follow-up` writes message + notification + audit + idempotency in one transaction; duplicate key returns the same message/notification ids without re-sending.
- Notification: `PENDING → DELIVERED → READ`. `read_at` is set once; repeated read is idempotent. Concurrent read with stale version → `409 version_conflict` or idempotent success per frozen contract.

## 8. Canonical API contract composition (`R-06`)

- Keep `shared/contracts/openapi.yaml` byte-for-byte unchanged for legacy compatibility.
- Introduce a **single canonical served specification** composed deterministically from modular source files under `shared/contracts/term1/` (e.g. `openapi.term1.v1.yaml` assembled from `paths-legacy.yaml`, `paths-auth.yaml`, `paths-enrollment.yaml`, `paths-assessment.yaml`, `paths-clinical.yaml`, `schemas/*.json`, `errors.yaml`, `security.yaml`). The composed document is the only document served at `/openapi.json`.
- A deterministic build step (documented, not implemented in C0) generates the combined spec; no hand-maintained second public spec may diverge from it.
- Headers are modeled as OpenAPI `parameters` with `in: header`, never as body fields.
- Preserve original exact-operation tests on the legacy artifact and add one complete served-operation allowlist test enumerating every method/path. Original fixtures F-01…F-12 and behavior regressions remain unchanged.
- Error catalogue: existing codes preserved; new codes added to a versioned `errors.yaml` (`invalid_invitation`, `invitation_expired`, `invitation_revoked`, `invitation_consumed`, `invitation_already_active`, `assignment_selection_required`, `assignment_revoked`, `provenance_not_admissible`, `stale_attempt`, `review_conflict`, `review_transition_conflict`, `secret_not_redisclosable`, `concurrency_conflict`).
- Patient projection allowlist (until Decision B): `assessment_id`, `status`, `created_at`, `review_state`, clinician-authored message metadata/content; **no** score, calibrated probability, log-odds, SHAP/LIME values, artifact digest, or internal diagnostics. Doctor projection adds research fields with `RESEARCH_ONLY_NOT_INDIVIDUAL_CLINICAL_RISK` labelling.

## 9. Migration ordering and restart requirements

1. Keep revision `20261017_01` as base. Add ordered revisions, each paired with SQLAlchemy models in the same commit:
   - `20261126_02_identity_auth` — user_account, doctor_profile, patient_profile, patient_identity, session, login_attempt.
   - `20261126_03_visit_invitation` — verified_visit, patient_invitation, invitation_redemption, invitation_attempt.
   - `20261126_04_assignment_consent` — doctor_patient_assignment, consent_record, health_profile.
   - `20261127_05_assessment_inference` — assessment, assessment_snapshot, inference_attempt, inference_result.
   - `20261128_06_clinical_workflow` — assessment_review, follow_up_message, notification_record.
   - `20261128_07_workflow_infrastructure` — durable_idempotency, workflow_audit_event.
   Exact revision ids are assigned at implementation time; ordering and dependencies are frozen here.
2. Every upgrade must be explicit (`python -m alembic upgrade head`); startup verification remains read-only and checks head, table presence, primary keys, autogenerate drift, FK enablement, integrity and FK checks. No `create_all`, stamp, auto-repair, or destructive reset.
3. Downgrade implemented and tested only on disposable databases; upgrade→downgrade→upgrade must preserve legacy monitoring rows where required and remove workflow rows intentionally.
4. Restart: sessions survive with verifier hashes until expiry; idempotency records survive until TTL; inference attempts in expired leases are recovered; notifications/messages/reviews persist; legacy monitoring behavior unchanged. No PostgreSQL parity claim.

## 10. Reviewer correction detail (R-01…R-08)

| ID | Detailed resolution |
|---|---|
| R-01 | §3.6 and ERD remove `patient.doctor_id`; all doctor access checks active assignment + assessment binding; patient selects `assignment_id`; revocation freezes history per original assignment. |
| R-02 | §3.4 binds subject HMAC at visit attestation; strict demo ID grammar, exact HMAC byte encoding, purpose separation, key id, single demo key and re-attestation rotation; server UTC vs stated visit time separated. |
| R-03 | API inventory (companion matrix) adds revoke/link/assignment revoke/status change; generic 401 lockout; bearer transport; indexes use real columns; admin bootstrap local-only. |
| R-04 | §6 redacted idempotency, one-time non-redisclosure, durable failure counters outside business tx. |
| R-05 | §7.3 single result row, generation/fence/lease CAS, stale suppression with retained history, review conflicts and follow-up eligibility. |
| R-06 | §8 canonical composed served spec, complete allowlist, legacy file/behavior preserved, headers as headers. |
| R-07 | Companion Windows runbook: explicit native exit codes, safe clone reuse, exact pytest paths, unique DBs, correct deps. |
| R-08 | `TERM1_AI_READINESS_MATRIX.md`: candidate B design, A/B proposals, deterministic trust/distribution, no clinical claim or private bundle execution. |

## 11. Explicit non-authorizations

This document does not authorize: C1–C4 implementation; HTTP model serving; patient score display; training or loading any model; use of private Cleveland bundle in Arena/CI; changes to research gates, Golden fixtures, tolerances, workflows, PR #141 or Issue #132; merge; frontend implementation; or a software-team repository.
