# CardioAssist-AI Term 1 — C0 Architecture, Data Model, Threat Model and Contracts

**Status:** `PROPOSED_C0_DEFAULT` design; no implementation, migration, runtime contract, test or workflow change is authorized by this document.
**Base:** prototype HEAD `bca75b4646dbde26e495201938b7ae01ea7e0d21`; main `c6a6bdee46a552a2b0d705a723c862ff8a95be4d`.
**Companion documents:** `TERM1_API_INTEGRATION_MATRIX.md`, `TERM1_AI_READINESS_MATRIX.md`, `TERM1_DECISION_REGISTER.md`, `TERM1_WINDOWS_VERIFICATION_RUNBOOK.md`.

**C0-F01…F10 correction notice (2026-11-25):** this document and its companion C0 documents were corrected after the reviewer's focused final review. Where older wording in this package conflicts, the C0-F sections below are normative. The historical preflight and reviewer-verdict documents are preserved unchanged. No implementation, migration, live contract, test or workflow change is made.

**Final narrow closure clarification (2026-11-25):** §3.4, §4, §5, §6.1, §7.3 and §7.4 add mandatory C1/C2 implementation requirements for key-check metadata, actor-bound replay lookup, consent/assignment separation, notification identity, follow-up review binding and stale-attempt suppression. They do not redesign the architecture and grant no implementation or inference authorization.

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
- **Canonical login email (C0-F01):** store `email_norm` NOT NULL as the only login identifier. Normalization is: strip leading/trailing ASCII whitespace; Unicode NFKC; reject non-ASCII; ASCII-lowercase; reject NUL/control characters, more than one `@`, local part >64 bytes, domain >189 bytes, empty labels, or total >254 bytes. The stored value is compared for exact equality. `UNIQUE(email_norm)` is mandatory. Account identifiers are synthetic UUID strings (`user_id`, `doctor_id`, `patient_id`); fixtures use only `@cardioassist.local` addresses and no real patient contact details.
- Duplicate account creation returns generic `409 account_registration_unavailable`; authentication returns generic `401 invalid_credentials`; failed link/invitation/authentication responses never reveal which field matched. Uniform response bodies, comparable status codes and a uniform `Retry-After` after threshold apply to all of them.
- `user_account.status ∈ {ACTIVE, SUSPENDED, DISABLED}`. Allowed transitions: `ACTIVE→SUSPENDED`, `SUSPENDED→ACTIVE`, `ACTIVE/SUSPENDED→DISABLED`; `DISABLED` is terminal (no hard delete). Every transition revokes all sessions, is admin-only via `PATCH /v1/admin/accounts/{user_id}/status`, and is audited in `workflow_audit_event`.
- Temporary passwords: doctor accounts start with `password_change_required=true`. Until changed, the only permitted authenticated operations are `GET /v1/auth/me`, `POST /v1/me/password` and `POST /v1/auth/logout`; every other route returns `403 password_change_required`. The current session stays valid solely for those operations; refresh cannot clear the flag; no other actor can change the password.
- Password change: `POST /v1/me/password` requires the current password and a new password, applies P-01/P-02, returns `{user_id,changed_at,password_change_required:false}` with no token, revokes all other sessions and writes workflow audit.
- Lockout/rate limits (C0-F03): five failed logins per 15 min in **each** of three durable buckets — per-account `HMAC(rate_key, 'account:'||user_id_or_email_norm_hash)`, per-source `HMAC(rate_key, 'source:'||hashed_client_prefix)` and per-invitation `invitation_attempt` count — produce a 15 min lock and generic `401 invalid_credentials` with uniform `Retry-After`. A composite email+IP bucket alone is not sufficient. Failure rows are written outside the business transaction.

### 3.2 Password hashing and verification

```
salt = secrets.token_bytes(16)
dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 600000, dklen=32)
stored = {"alg":"pbkdf2_hmac_sha256","v":1,"iterations":600000,
          "salt_b64":..., "verifier_b64":...}
```

Verification recomputes with stored parameters and uses `hmac.compare_digest`. Stored parameters allow a future iteration increase without breaking existing accounts. No new dependency is required; if the owner prefers Argon2id, that requires a new pinned dependency and a separate decision.

**Frozen password rules (C0-F01):** passwords are opaque UTF-8 byte strings. There is no trimming, no whitespace stripping, no Unicode normalization, no case folding and no silent truncation at entry, hashing or verification; leading/trailing spaces are significant. Length is 12–128 UTF-8 bytes; NUL and control characters are rejected. The current password is compared with the stored verifier, never as clear text. A new password must differ from the current verifier and must not be reused from any stored history (Term 1 stores no password history). These rules are identical for provisioning, login and password change and are covered by C1 tests.

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
- Term 1 uses one stable operator-supplied demo identity-match key with id `demo-v1`, never committed. **Key replacement is disabled for any populated database (C0-F02).** If `patient_identity`, `verified_visit`, `patient_invitation` or `invitation_attempt` contains a row, an attempt to change the key/key id is refused with `409 identity_key_replacement_unsupported`; no `demo-v2` path is implemented. On an empty disposable database only, the key id may be set once before the first attestation. A key change for populated data requires a separately reviewed migration protocol with a new decision; no silent cross-key matching, no raw identifier storage, and no cross-key authenticated linking are permitted in Term 1.
- A second, stable subject key produces `canonical_subject_id = HMAC-SHA256(subject_key, 'term1-subject-canonical/v1' || 0x00 || normalized_id)`, lowercase hex. It is stored blind-index-only and `UNIQUE(canonical_subject_id)` prevents duplicate identities even across identity-match-key versions. No raw identifier is stored. The subject key and identity-match key are distinct, purpose-separated operator secrets.
- **Both stable identity keys are bound to persisted, non-secret key-check metadata before any write on a populated database (mandatory C1).** `identity_key_check` stores one row per `(purpose, key_id)` with `key_check_hash = HMAC-SHA256(operator_key, 'identity-key-check/v1' || 0x00 || purpose || 0x00 || key_id)`, algorithm id, activated timestamp and optional retired timestamp. The hash is a verification value, not secret material; no raw key is stored. Startup and every key-replacement attempt recompute and constant-time compare the check before any write to identity/visit/invitation/identity tables. Mismatch, missing row, duplicate key id with different check, or reuse of a retired key id → refuse with `409 identity_key_material_mismatch`. This detects replacement of key material under the same key id even when the key id string is unchanged; operator-provided key id and check metadata are versioned together.
- Identifier matching is a demo binding only; it is not government identity verification or proof of attendance. The attestation is the evidence of a prior visit.

### 3.5 Invitation and redemption

- Token: 32-byte CSPRNG; plaintext displayed exactly once at `POST /v1/doctor/verified-visits/{id}/invitations`; only verifier hash stored. TTL default 24 h (owner may set 1–72 h). Revocation via `POST /v1/doctor/invitations/{id}/revoke`, idempotent, allowed only by the doctor owning the visit.
- Redemption for a **new** patient: `POST /v1/patients/register` with `{access_code, identifier, email, password, consent_ack}`. One transaction: conditional consume (`consumed_at IS NULL AND revoked_at IS NULL AND expires_at > now`), HMAC verify, create `user_account` + `patient_identity` + `patient_profile` + `doctor_patient_assignment` + `consent_record`, write idempotency and success audit. Any mismatch yields generic `401 invalid_invitation`.
- Redemption for an **existing** patient: `POST /v1/patients/link`, authenticated, with `{access_code, identifier, accept_linking:true}`. The server verifies the token verifier, invitation state and invitation `identifier_hmac` under the invitation's recorded `identifier_key_id`; it then computes `canonical_subject_id` from the submitted identifier and compares it with the authenticated patient's stored blind index. Equality of two differently keyed `identifier_hmac` values is never required. If the presented key id differs from the stored identity's key id, the request is refused as `401 identity_key_change_unsupported`. No second account is created; a new `doctor_patient_assignment` row is created and the invitation consumed atomically. Mismatch or missing invitation → generic `401 invalid_invitation`.
- Repeat visits create a new `verified_visit` and new invitation. A second invitation is allowed only after the prior one is expired/revoked/consumed; duplicate active invitations for one visit → `409 invitation_already_active`.
- Duplicate fictitious identifier: at most one `patient_identity` per `canonical_subject_id` (and therefore per identity, across key versions); a second new-patient registration with the same subject requires the authenticated link flow, not a new account.
- Concurrent redemption: conditional UPDATE rowcount check plus unique constraints; two independent connections race → exactly one success; loser receives generic failure or `409 concurrency_conflict` after bounded retry. SQLite has no `SELECT ... FOR UPDATE` assumption.

### 3.6 RBAC and object-level authorization (`R-01`)

- There is **no** `patient.doctor_id`. Doctor access is through active `doctor_patient_assignment` rows. Assessment rows bind the `assignment_id` that was active at creation.
- Every doctor-scoped operation includes `assignment_id` in the path or query and verifies `assignment.doctor_id == current_user.doctor_id AND revoked_at IS NULL`. Patient-scoped operations verify `assignment.patient_id == current_user.patient_id`.
- When a patient has multiple active assignments, the client must select one; `GET /v1/me/assignments` returns eligible assignment IDs. If a doctor-scoped patient context is ambiguous, server returns `409 assignment_selection_required` with only IDs and labels, no clinical data.
- Revocation sets `revoked_at`; authorization checks it on every request. Historical assessments/messages retain their original `assignment_id`; a revoked doctor loses access to them, and a newly assigned doctor cannot read records tied to a different assignment. Restoring historical access requires a separately recorded grant, not implicit role membership.
- Admin has no clinical payload access by default. Patient can never access another patient's objects. Wrong owner returns `404` consistently.

## 4. Proposed ERD

```
user_account (PK user_id UUID str, email_norm UNIQUE NOT NULL, role CHECK,
              status CHECK, password_alg/version/iterations/salt_b64/verifier_b64,
              password_change_required BOOL, created_at, password_changed_at,
              failed_count, locked_until)
   │ 1:0..1
   ├── doctor_profile (PK doctor_id, FK user_id UNIQUE, display_name, active)
   └── patient_profile (PK patient_id, FK user_id UNIQUE,
                        FK patient_identity_id UNIQUE, display_label, created_at)
   │ 1:*
   └── session (PK session_id, FK user_id, token_verifier_sha256 UNIQUE,
                session_key_id, created_at, expires_at, last_seen_at, revoked_at)

identity_key_check (PK check_id, purpose CHECK {identity_match,subject_canonical},
                  key_id, key_check_hash, alg, activated_at, retired_at NULL;
                  UNIQUE(purpose,key_id), UNIQUE(purpose,key_check_hash))

patient_identity (PK identity_id, identifier_key_id, identifier_hmac,
                  canonical_subject_id UNIQUE, created_at;
                  UNIQUE(identifier_hmac), UNIQUE(canonical_subject_id))
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
            status, source_contract_version, created_at, current_generation,
            active_attempt_id NULL, current_result_id NULL,
            review_state CHECK, review_version, reassessment_of FK assessment NULL,
            reason_code)
   │ 1:1
   └── assessment_snapshot (PK snapshot_id, FK assessment_id UNIQUE,
            canonical_json, payload_sha256, provenance_json,
            schema_sha256, panel_sha256, created_at; immutable)
   │ 1:*
   ├── inference_attempt (PK attempt_id, FK assessment_id, generation INT,
   │       idempotency_key_hash UNIQUE, state, lease_until, fence_token,
   │       worker_id, requested_at, finished_at, error_code NULL,
   │       UNIQUE(assessment_id, generation);
   │       one active attempt per assessment via partial UNIQUE on active states)
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
           FK review_id UNIQUE, FK author_user_id (doctor), body,
           prescription_json, created_at, idempotency_key_hash UNIQUE)
          │ 1:*
          └── notification_record (PK notification_id UUID str (authoritative),
                 FK recipient_user_id, FK message_id NULL for system notices,
                 type CHECK, delivery_state CHECK, version,
                 system_event_key NULL, created_at, read_at NULL,
                 idempotency_key_hash UNIQUE;
                 UNIQUE(system_event_key) WHERE system_event_key IS NOT NULL)

durable_idempotency (PK replay_scope, key_hash, actor_binding, operation,
                     target_ref, request_fingerprint, secret_fingerprints_json,
                     response_public_json, status_code, created_at, expires_at,
                     secret_disclosed BOOL;
                     UNIQUE(replay_scope,key_hash,actor_binding,operation,target_ref))
workflow_audit_event (PK audit_id, event_type, actor_user_id NULL,
                     subject_type, subject_id, request_id, payload_sha256,
                     code, outcome, recorded_at)
login_attempt (PK attempt_id, bucket_key_hash, outcome, created_at)  // failure counters
```

## 5. Data dictionary and constraints

### 5.1 Core required/optional fields

| Table | Required | Optional | Constraints / notes |
|---|---|---|---|
| `user_account` | user_id, email_norm, role, status, KDF fields, created_at | password_changed_at, locked_until | `role IN ('admin','doctor','patient')`; `status IN ('ACTIVE','SUSPENDED','DISABLED')`; `UNIQUE(email_norm)` on normalized value; verifier never contains raw password; frozen password rules in §3.2 |
| `doctor_profile` | doctor_id, user_id, display_name, active | — | FK user_id UNIQUE; display_name ≤128 chars, no identifiers |
| `patient_profile` | patient_id, user_id, patient_identity_id, display_label, created_at | — | FK both UNIQUE; one account per identity |
| `session` | session_id, user_id, token_verifier_sha256, session_key_id, created_at, expires_at | last_seen_at, revoked_at | token verifier UNIQUE; no raw token column; `session_key_id` is not an identity key id |
| `patient_identity` | identity_id, identifier_key_id, identifier_hmac, canonical_subject_id, created_at | — | `UNIQUE(identifier_hmac)`, `UNIQUE(canonical_subject_id)`; no raw identifier; key replacement refused on populated DB |
| `verified_visit` | visit_id, doctor_id, visit_ref, subject_identifier_hmac, identifier_key_id, asserted_visit_at, attested_at, attestation_code | note_code | UNIQUE(doctor_id, visit_ref); no free clinical text |
| `patient_invitation` | invitation_id, visit_id, issued_by_user_id, token_verifier_sha256, subject_identifier_hmac, identifier_key_id, issued_at, expires_at, max_attempts | consumed_at, revoked_at | UNIQUE token verifier; CHECK not both consumed/revoked; FK visit_id and issued_by_user_id only |
| `invitation_redemption` | redemption_id, invitation_id, patient_id, assignment_id, redeemed_at, flow | — | FK invitation_id UNIQUE; flow enum |
| `identity_key_check` | check_id, purpose, key_id, key_check_hash, alg, activated_at | retired_at | Purpose-separated non-secret check; `UNIQUE(purpose,key_id)`, `UNIQUE(purpose,key_check_hash)`; verified before writes |
| `doctor_patient_assignment` | assignment_id, doctor_id, patient_id, assigned_at | revoked_at, revoked_by_user_id, reason_code | Partial UNIQUE active pair; no patient.doctor_id; revocation is assignment-only |
| `consent_record` | consent_id, patient_id, kind, scope, acknowledged_at, contract_version | revoked_at | `kind='synthetic_demo'`, `scope='patient_wide_synthetic_demo'`; one active row per patient; withdrawal is patient-wide |
| `health_profile` | profile_id, patient_id, schema_version, payload_json, provenance_json, created_at | superseded_at | immutable once created; new version supersedes |
| `assessment` | assessment_id, patient_id, assignment_id, consent_id, health_profile_id, panel_id, panel_version, status, source_contract_version, created_at, current_generation, review_state, review_version | current_result_id, active_attempt_id, reassessment_of, reason_code | FK assignment binds authorization scope; all referenced records must belong to same patient; review_state authoritative |
| `assessment_snapshot` | snapshot_id, assessment_id, canonical_json, payload_sha256, provenance_json, schema_sha256, panel_sha256, created_at | — | FK assessment UNIQUE; append-only/immutable |
| `inference_attempt` | attempt_id, assessment_id, generation, idempotency_key_hash, state, lease_until, fence_token, requested_at | finished_at, error_code, worker_id | UNIQUE(assessment_id, generation), UNIQUE key hash; no score/explanation columns |
| `inference_result` | result_id, attempt_id, assessment_id, generation, snapshot_sha256, model_id, model_version, artifact_sha256, source_binding, score_kind, score_json, explanation_json, explanation_method, background_id, result_sha256, recorded_at | — | FK attempt UNIQUE; one authoritative representation |
| `assessment_review` | review_id, assessment_id, assignment_id, reviewer_user_id, decision, reason_code, rationale, recorded_at, idempotency_key_hash | — | append-only; decision enum |
| `follow_up_message` | message_id, assessment_id, review_id, author_user_id, body, prescription_json, created_at, idempotency_key_hash | — | `FK review_id UNIQUE`; one follow-up per review; author must be doctor; AI cannot author |
| `notification_record` | notification_id, recipient_user_id, type, delivery_state, version, created_at, idempotency_key_hash | message_id (NULL for system notices), system_event_key, read_at | `notification_id` authoritative; `system_event_key` unique for system notices; `delivery_state IN ('PENDING','DELIVERED','READ')` |
| `durable_idempotency` | replay_scope, key_hash, actor_binding, operation, target_ref, request_fingerprint, response_public_json, status_code, created_at, expires_at, secret_disclosed | secret_fingerprints_json (keyed digests only) | actor/operation/target-bound replay identity; keyed fingerprints; no raw secret or full request body |
| `workflow_audit_event` | audit_id, event_type, subject_type, subject_id, payload_sha256, code, outcome, recorded_at | actor_user_id, request_id | metadata only; no identifiers/secrets |
| `login_attempt` | attempt_id, bucket_key_hash, outcome, created_at | — | bucket key HMAC(email)+IP prefix; written outside rolled-back business tx |\n| `invitation_attempt` | attempt_id, invitation_id, bucket_key_hash, outcome_code, created_at | — | FK invitation_id nullable (unknown code); metadata only; written outside rolled-back business tx |\n| `admin_bootstrap_record` | bootstrap_id, user_id, email_norm, bootstrapped_at | — | one-time local admin bootstrap record; existence blocks re-bootstrap |

### 5.2 Indexes referencing actual columns

- `ux_user_account_email_norm` UNIQUE on `user_account(email_norm)`; `ix_user_account_status_role` on `user_account(status, role)`.
- `ix_login_attempt_bucket_time` on `login_attempt(bucket_key_hash, created_at)`; separate per-account, per-source and per-invitation counters are enforced.
- `ix_session_user_expires` on `session(user_id, expires_at)`; UNIQUE on `token_verifier_sha256`.
- `ix_verified_visit_doctor_time` on `verified_visit(doctor_id, attested_at)`; UNIQUE `(doctor_id, visit_ref)`.
- `ix_invitation_visit_expiry` on `patient_invitation(visit_id, expires_at)`; `ix_invitation_subject` on `(identifier_key_id, subject_identifier_hmac)`; UNIQUE `token_verifier_sha256`; `ix_invitation_redemption_assignment` on `invitation_redemption(assignment_id)`.
- `ix_assignment_patient_active` on `doctor_patient_assignment(patient_id, revoked_at)`; partial UNIQUE `(doctor_id, patient_id) WHERE revoked_at IS NULL`.
- `ix_assessment_patient_created` on `assessment(patient_id, created_at)`; `ix_assessment_assignment_status` on `(assignment_id, status)`.
- `ix_inference_attempt_assessment_state` on `inference_attempt(assessment_id, state)`; UNIQUE `(assessment_id, generation)`; partial UNIQUE on `(assessment_id)` where state is active; `ix_assessment_current_result` on `assessment(current_result_id)`.
- `ix_review_assessment_recorded` on `assessment_review(assessment_id, recorded_at)`.
- `ix_notification_recipient_read` on `notification_record(recipient_user_id, read_at, created_at)`.
- `ix_workflow_audit_subject_time` on `workflow_audit_event(subject_type, subject_id, recorded_at)`.
- `UNIQUE(replay_scope, key_hash, actor_binding, operation, target_ref)` on `durable_idempotency`; `UNIQUE(identifier_hmac)` and `UNIQUE(canonical_subject_id)` on `patient_identity`; `UNIQUE(email_norm)` on `user_account`.

No index references a nonexistent `doctor_id` on invitations or a `status` column on sessions.

### 5.3 Legacy tables preserved

`monitoring_observation`, `monitoring_metric`, `audit_event` and migration `20261017_01` remain unchanged. `audit_event.observation_record_id` stays NOT NULL with FK to `monitoring_observation.record_id` and UNIQUE per observation. Workflow events use `workflow_audit_event`; no fake monitoring rows are created.

### 5.4 C1 sixteen-table inventory

The Term 1 C1 stage owns exactly sixteen tables (plus the three untouched legacy monitoring tables):

| # | Table | Purpose |
|---|---|---|
| 1 | `user_account` | Accounts (admin/doctor/patient) with KDF password verifiers and lifecycle status |
| 2 | `doctor_profile` | Doctor display profile linked to a user account |
| 3 | `patient_identity` | Blind identity binding (HMAC + canonical subject id), no raw identifier |
| 4 | `patient_profile` | Patient profile linked to account + identity |
| 5 | `identity_key_check` | Non-secret key-material binding per purpose; verified before identity writes |
| 6 | `session` | Session rows with token verifier hash, absolute/idle expiry, revocation |
| 7 | `login_attempt` | Durable failed-login counters for lockout; written outside rolled-back business tx |
| 8 | `verified_visit` | Doctor-attested prior synthetic-demo visit with subject binding |
| 9 | `patient_invitation` | One-time access code verifier, expiry, attempt count, consumption/revocation |
| 10 | `invitation_attempt` | Durable failed-invitation-attempt evidence; metadata only |
| 11 | `doctor_patient_assignment` | Active doctor↔patient assignment with partial UNIQUE; revocation-only |
| 12 | `consent_record` | Patient-wide synthetic-demo consent; withdrawal is patient-wide |
| 13 | `invitation_redemption` | One redemption per consumed invitation; links invitation→patient→assignment |
| 14 | `durable_idempotency` | Actor/operation/target-bound replay identity; keyed secret fingerprints |
| 15 | `workflow_audit_event` | Metadata-only audit trail; no identifiers or secrets |
| 16 | `admin_bootstrap_record` | One-time administrator bootstrap record; blocks re-bootstrap |

The legacy `monitoring_observation`, `monitoring_metric` and `audit_event` tables are preserved unchanged and are not part of the C1 inventory.

## 6. Transaction boundaries, idempotency and secret safety (`R-04`)

### 6.1 Durable idempotency record (C0-F03)

The replay identity is explicit and actor/operation/target-bound:

```
replay_scope  = authenticated ? 'user' : 'anonymous'
actor_binding = authenticated ? 'user:'+user_id
                             : 'anon:'+first_32_hex(invitation_verifier_sha256)
operation     = exact method + path, e.g. 'POST /v1/patients/register'
target_ref    = opaque resource id (invitation_id, assessment_id, ...) or 'none'
key_hash      = HMAC-SHA256(idempotency_pepper, raw_Idempotency_Key)
request_fingerprint = HMAC-SHA256(fingerprint_pepper, canonical(secret-free fields))
secret_fingerprints = {field: HMAC-SHA256(secret_pepper, domain||field||exact_utf8_value)}
UNIQUE(replay_scope, key_hash, actor_binding, operation, target_ref)
```

`durable_idempotency` stores only `replay_scope`, `key_hash`, `actor_binding`, `operation`, `target_ref`, `request_fingerprint`, keyed `secret_fingerprints`, a redacted `response_public_json`, `status_code`, timestamps and `secret_disclosed`. It never stores a raw Idempotency-Key, password, access code, bearer token, raw identifier, raw request body or full credential-bearing response. For anonymous enrollment the actor binding is derived from the invitation verifier and `target_ref` from `invitation_id`, so replay cannot disclose another patient's identifiers or email.

Rules and frozen lookup ordering (mandatory C1 implementation/test requirement):

1. Validate only request structure and header presence. Compute the replay identity **including** `actor_binding`, operation and target. There is no global lookup by `key_hash`: a key presented by a different actor is simply not found in that actor's scope. Different actors can never discover or receive another actor's replay record, status, existence or identifiers; no cross-actor `scope_conflict` is returned.
2. Look up the idempotency row **only** by the complete actor/operation/target-bound identity. If found with identical public and keyed secret fingerprints, return the stored redacted response with `idempotent_replay:true`; do not re-check invitation state, do not reopen a consumed invitation and do not repeat effects. If the original response carried a one-time secret, return `409 secret_not_redisclosable` with non-secret identifiers only.
3. If found with different fingerprints but the same actor/operation/target, return `409 idempotency_key_conflict` before semantic validation. If the same actor uses the same key for a different operation or target, return `409 idempotency_scope_conflict` within that actor's scope only.
4. Only when no record exists in the actor's scope may invitation expiry/revocation/consumption, subject binding, consent, uniqueness and commit occur. A legitimate replay is therefore resolved from the durable redacted result even after the invitation was consumed; it never reopens the invitation. If the idempotency record itself expired, normal invitation validation applies and a consumed invitation fails generically; a missing record never permits reuse.
5. `POST /v1/patients/register` replay never mints a second account, identity, consent, assignment or session. Secret-bearing responses (temporary passwords, access codes, session tokens) are returned only in the original response.
6. Login (`A1`) and refresh (`A4`) declare **no** `Idempotency-Key`: repeated login creates a new session; each refresh rotates and invalidates the prior token; refresh with an already revoked or expired token fails `401 invalid_session` and creates no session. Failed logins and invitation attempts are counted durably.
7. Failed enrollment/invitation attempts increment `invitation_attempt` and `login_attempt` in a separate transaction after rollback. Unknown-invitation attempts are recorded as `workflow_audit_event` with `subject_type='unknown_invitation'`, keyed code digest, `invitation_id=NULL`, outcome and metadata only; no raw code is stored.
8. Rate limits are durable and independent: per-account, per-source and per-invitation buckets (5 failures/15 min; 15 min lock; 5 failed invitation attempts exhaust and revoke that invitation). A composite email+IP bucket alone is not sufficient.
9. A database key gives at-most-once replay within its scope and TTL, not distributed exactly-once execution. Single Uvicorn worker is required for Term 1.

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

### 7.3 Inference concurrency, fencing and recovery (`R-05`, C0-F05)

- `assessment` owns `current_generation`, `active_attempt_id`, `current_result_id`, `review_state` and `review_version`. There is **one active attempt per assessment across all generations**, enforced by a partial UNIQUE index on active states and by `active_attempt_id`.
- Lease: proposed 5 min. `lease_until` is authoritative; a worker may publish only while `lease_until > now()`. Expiry alone never creates a result.
- Atomic completion transaction (`BEGIN IMMEDIATE`): all of the following must hold — attempt id; `attempt.assessment_id`; `attempt.generation == assessment.current_generation`; `assessment.active_attempt_id == attempt_id`; `state='INFERENCE_RUNNING'`; `fence_token` matches; `worker_id` matches; `lease_until > now()`; `assessment.status='INFERENCE_RUNNING'`; the assessment's assignment is still active; and the referenced consent is still active. Only then may the attempt become `INFERENCE_SUCCEEDED`, `inference_result` be inserted and `assessment.current_result_id` be set. Any failed condition → `409 stale_attempt`, no result, no review transition.
- If assignment or consent was withdrawn before publication, the attempt terminates as `INFERENCE_UNAVAILABLE` with reason `authorization_withdrawn`; no score, no `PENDING_REVIEW`, no stale current-result projection.
- An expired (`lease_until <= now()`), superseded (`generation < assessment.current_generation`), cancelled or non-`RUNNING` attempt can never publish a result or set `current_result_id`, even if the worker later returns with a valid-looking fence. The completion CAS is the only path that may publish.
- Recovery scans `lease_until <= now AND state='INFERENCE_RUNNING'`, consistent with the lease-expiry rejection boundary and the C2 schema/integration contract; it marks the attempt `INFERENCE_ERROR`, clears `active_attempt_id`, increments `current_generation` and keeps authoritative history. An idempotent retry may create generation+1 with a new fence token; the late worker's CAS fails.
- `inference_result` is the sole authoritative score/explanation representation and is immutable. Attempts/results are append-only; only `assessment.current_result_id` selects the current view. Stale rows remain as evidence but are never projected as current. Result binds `snapshot_sha256`, model id/version, artifact digest, source binding and panel/schema hashes; mismatch fails closed.
- Decision A absent → `INFERENCE_UNAVAILABLE` before artifact access. Test doubles are permitted only in tests and never constitute production results.

### 7.4 Review, follow-up and notification (C0-F05)

- `assessment.review_state` is authoritative: `NOT_REVIEWED → ACCEPTED | REJECTED | REASSESSMENT_REQUESTED`. Review rows are append-only and bind `assignment_id` and `reviewer_user_id`. The state update is CAS on `review_state = expected` plus `review_version`; the loser gets `409 review_conflict`. Illegal transitions → `409 review_transition_conflict`. Replay of the same idempotency key returns the original public review row.
- Follow-up eligibility is exact: a current successful result must exist; the review decision must be `ACCEPTED` or `REASSESSMENT_REQUESTED` by the doctor assigned to that assessment; the assignment must still be active or covered by a separately recorded historical grant; and no follow-up may already exist for that `review_id`. `REJECTED` blocks follow-up until reassessment. Each follow-up binds `review_id` with a UNIQUE constraint; AI cannot be an author because `author_user_id` must resolve to a doctor user.
- **Authoritative notification identity (mandatory C1/C2/C3):** `notification_id` is a server-assigned UUID and the only public identifier. For a system notice, `message_id` is NULL, `type` is a closed `system_*` enum, and `system_event_key` is a unique server-generated key derived from event type, recipient and source object; it prevents duplicate system notices under retry. Permitted transitions are `PENDING→DELIVERED`, `PENDING→READ` and `DELIVERED→READ`; `READ` is terminal and no backward transition exists. Every transition uses the `version` CAS; repeated read is idempotent, stale version → `409 version_conflict`.
- System notices require no follow-up message and no prescription. `read_at` is set exactly once.
- Reassessment creates a new assessment row with `reassessment_of` and a reason code. Generations, attempts, results and review state are per-assessment; the old result and review remain immutable and are never inherited as current. Patient history is read-only and role-redacted.

## 8. Canonical API contract composition (`R-06`)

- Keep `shared/contracts/openapi.yaml` byte-for-byte unchanged for legacy compatibility.
- Introduce a **single canonical served specification** composed deterministically from modular source files under `shared/contracts/term1/` (e.g. `openapi.term1.v1.yaml` assembled from `paths-legacy.yaml`, `paths-auth.yaml`, `paths-enrollment.yaml`, `paths-assessment.yaml`, `paths-clinical.yaml`, `schemas/*.json`, `errors.yaml`, `security.yaml`). The composed document is the only document served at `/openapi.json`.
- A deterministic build step (documented, not implemented in C0) generates the combined spec; no hand-maintained second public spec may diverge from it.
- Headers are modeled as OpenAPI `parameters` with `in: header`, never as body fields.
- Preserve original exact-operation tests on the legacy artifact and add one complete served-operation allowlist test enumerating every method/path. Original fixtures F-01…F-12 and behavior regressions remain unchanged.
- Error catalogue: existing codes preserved; new codes added to a versioned `errors.yaml` (`invalid_invitation`, `invitation_expired`, `invitation_revoked`, `invitation_consumed`, `invitation_already_active`, `identity_key_change_unsupported`, `identity_key_replacement_unsupported`, `account_registration_unavailable`, `password_change_required`, `assignment_selection_required`, `assignment_revoked`, `provenance_not_admissible`, `idempotency_scope_conflict`, `idempotency_key_conflict`, `stale_attempt`, `review_conflict`, `review_transition_conflict`, `secret_not_redisclosable`, `concurrency_conflict`). The complete method/path allowlist treats GET and PATCH as separate operations in `TERM1_API_INTEGRATION_MATRIX.md` §2.
- Patient projection allowlist (until Decision B): `assessment_id`, `status`, `created_at`, `review_state`, clinician-authored message metadata/content; **no** score, calibrated probability, log-odds, SHAP/LIME values, artifact digest, or internal diagnostics. Doctor projection adds research fields with `RESEARCH_ONLY_NOT_INDIVIDUAL_CLINICAL_RISK` labelling. `source_contract.source_kind` is server-assigned; a client-supplied protected provenance value is rejected with `422 provenance_not_admissible`.

## 9. Migration ordering and restart requirements (C0-F04)

1. Keep revision `20261017_01` and the legacy three tables unchanged. Every referenced table is created before its dependent table. Exact revision ids are assigned at implementation; ordering and stage placement are frozen here.
2. **C1 (mandatory dependencies all inside C1):** `20261126_02_identity_auth` creates `user_account` (with `email_norm` UNIQUE), `identity_key_check`, `doctor_profile`, `patient_identity` (with `canonical_subject_id` UNIQUE), then `patient_profile`, `session`, `login_attempt`, **and** `durable_idempotency` + `workflow_audit_event`. Infrastructure is not deferred past the clinical workflow.
3. **C1:** `20261126_03_visit_invitation` creates `verified_visit`, `patient_invitation`, `invitation_attempt` (nullable invitation reference for unknown-attempt audit).
4. **C1:** `20261126_04_assignment_consent` creates `doctor_patient_assignment` and `consent_record` before any constraint that references an assignment.
5. **C1:** `20261126_05_enrollment_redemption` creates `invitation_redemption` only after invitation, patient identity/profile and assignment exist.
6. **C2:** `20261127_06_health_assessment` creates `health_profile` (synthetic profile is a C2 capability), then `assessment`, `assessment_snapshot`, `inference_attempt`, `inference_result`.
7. **C3:** `20261128_07_clinical_workflow` creates `assessment_review`, `follow_up_message`, `notification_record`.
8. Cross-entity consistency: user roles match profile type; identity/profile are 1:1; visit doctor matches invitation issuer; redemption patient matches the identity's profile and assignment's patient/doctor; assessment's patient, assignment, consent and health profile all reference the same patient and the assignment was active at creation; inference attempt/result share assessment and generation; review uses the assessment's assignment; follow-up author is the assigned doctor; notification recipient is the assessment's patient. The database constraints are complemented by transaction-level checks under SQLite.
9. Consent scope with multiple doctors: `kind='synthetic_demo'` consent is patient-wide and versioned. Revocation stops **new** assessments for every assignment but never mutates an existing immutable assessment/consent reference. Revoking one assignment blocks only that assignment's access and does not create access for another doctor. Linking a second doctor creates a new assignment only; it never grants access to records bound to an earlier assignment. Restoring historical access needs a separately recorded grant.
10. Field names are frozen: `identifier_key_id` on identity/visit/invitation; `session_key_id` on session. `key_id` alone is not a valid identity field name.
11. Every upgrade is explicit (`python -m alembic upgrade head`); startup verification remains read-only (head, table presence, PKs, autogenerate drift, FK enablement, integrity and FK checks). No `create_all`, stamp, auto-repair or destructive reset. Downgrade is implemented and tested only on disposable databases; legacy monitoring rows must survive upgrade→downgrade→upgrade. Restart preserves sessions, idempotency within TTL, attempt history, reviews, messages/notifications and legacy behavior. No PostgreSQL parity claim.

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

### 10.1 Final reviewer corrections (C0-F01…F10)

| ID | Normative resolution in this package |
|---|---|
| C0-F01 | §3.1/§3.2/§5: canonical `email_norm` with UNIQUE, exact normalization, synthetic UUID identifiers, non-enumerating errors, status transitions, mandatory temp-password restrictions, frozen no-normalization password rules. |
| C0-F02 | §3.4/§3.5/§5: blind `canonical_subject_id` UNIQUE across key versions; single stable `demo-v1`; key replacement refused on populated DBs; authenticated link compares canonical subject id, not cross-key HMAC equality. |
| C0-F03 | §6.1: actor/operation/target-bound replay identity, keyed secret fingerprints, rate-limit buckets, unknown-invitation audit, redacted replay vs `409 secret_not_redisclosable`, login/refresh without idempotency, permanent invitation consumption. |
| C0-F04 | §9: referenced-before-dependent migration ordering, C1 infrastructure inside C1, health profile in C2, consistent field names/cardinalities, cross-entity constraints and multi-doctor consent behavior. |
| C0-F05 | §7.3/§7.4: lease and current-generation CAS, one active attempt, assignment/consent checks at publication, authoritative review state, notification states, exact follow-up eligibility and reassessment isolation. |
| C0-F06 | §8 and `TERM1_API_INTEGRATION_MATRIX.md` §2/§3: frozen method/path allowlist with GET and PATCH separate, exact headers/errors/replay, C1 field contract, server-assigned provenance, legacy schemas preserved. |
| C0-F07 | `TERM1_AI_READINESS_MATRIX.md` §3: four distinct gates for development, independent verification, owner activation and patient display; all PENDING. |
| C0-F08 | `TERM1_STAGE_EXECUTION_PLAN.md` §1.2/§2/§5 and `TERM1_STAGE_PROGRESS.md`: stage-PR policy, PR #143 evidence, reconstructed vs original commit disclosure; no self-acceptance. |
| C0-F09 | `TERM1_WINDOWS_VERIFICATION_RUNBOOK.md`: complete PS5.1 C0 candidate verification block at PR #143 head, no prototype-branch overwrite. |
| C0-F10 | `TERM1_TEST_EVIDENCE.md` §5: exact-head workflow_dispatch plan/evidence category; no ALL_GREEN inference. |

### 10.2 Final narrow closure clarifications (mandatory C1/C2/C3)

| Topic | Normative rule | Location |
|---|---|---|
| Key material binding | Both operator keys have persisted non-secret checks; same-key-id material replacement detected before any write on a populated DB | §3.4, §4, §5.1, §9 |
| Idempotency actor isolation | Full actor/operation/target lookup only; no cross-actor lookup or disclosure | §6.1 |
| Replay ordering | Identity lookup → fingerprint compare → redacted replay/secret error; invitation state checked only on first execution | §6.1 |
| Consent vs assignment | Assignment revocation is local; patient-wide consent withdrawal is separate with one active consent row | §5.1, §9 |
| Notification identity | Server-assigned UUID, unique system event key and forward-only state transitions | §7.4 |
| Follow-up review binding | `review_id` FK UNIQUE; one follow-up per review | §4, §5.1, §7.4 |
| Stale inference | Expired/superseded attempts can never publish or set current result | §7.3 |

## 11. Explicit non-authorizations

This document does not authorize: C1–C4 implementation; HTTP model serving; patient score display; training or loading any model; use of private Cleveland bundle in Arena/CI; changes to research gates, Golden fixtures, tolerances, workflows, PR #141 or Issue #132; merge; frontend implementation; or a software-team repository.
