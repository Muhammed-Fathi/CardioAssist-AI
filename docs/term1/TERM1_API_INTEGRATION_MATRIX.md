# CardioAssist-AI Term 1 — API Integration Matrix and Proposed Contract Inventory

**Status:** `PROPOSED_C0_DEFAULT`. No live OpenAPI file, JSON Schema, runtime route, fixture or test is changed by C0.
**Canonical served spec:** one deterministic composition described in `TERM1_C0_ARCHITECTURE_AND_CONTRACTS.md` §8.
**Legacy operations:** preserved byte/behavior-compatible; exact regression coverage retained.

**C0-F01…F10 correction notice (2026-11-25):** §2 freezes the complete method/path allowlist with GET and PATCH separate, §2.1 defines C1 field types/enums/role responses, and §3 freezes headers, errors, replay and rate-limit behavior. Older wording in this package is superseded where it conflicts. No live contract is changed by C0.

**Final narrow closure clarification (2026-11-25):** §2 and §2.1 separate assignment revocation from patient-wide consent withdrawal, align temporary-password restrictions, prohibit real patient contact information in synthetic-demo accounts and state that refresh with a revoked token fails. §3 freezes actor-isolated replay lookup ordering. These are mandatory C1 implementation/test requirements.

## 1. Contract composition and allowlist strategy

1. `shared/contracts/openapi.yaml` remains unchanged. Its two paths and existing JSON Schemas/fixtures F-01…F-12 remain the approved legacy contract.
2. Modular Term-1 source files are added later under `shared/contracts/term1/`; a deterministic build produces the **single** `/openapi.json` served document combining legacy and Term-1 operations.
3. Tests at C1+:
   - `test_legacy_openapi_file_unchanged` — hash/byte regression of the legacy document.
   - `test_legacy_exact_operations_and_schema_bindings` — original exact two-path assertions retained verbatim in intent.
   - `test_served_openapi_exact_complete_operation_set` — one explicit allowlist of every method/path in the composed document; no extra operation permitted.
   - `test_no_shadow_prediction_endpoint` — no differently named prediction route can bypass the model-serving gate.
   - `test_headers_declared_as_headers` — `Authorization`, `Idempotency-Key` modeled with `in: header`.
4. All new fixtures continue the F-xx series with an index update in the implementing stage; no fixture is altered to accommodate a new result.

## 2. Operation inventory

Key: `A` = anonymous, `AD` = admin, `D` = doctor, `P` = patient, `ANY` = authenticated any role. Object-level checks are mandatory where "owner" is noted. All times UTC. All bodies `application/json`.

| # | Method / path | Actor / object-level | Headers | Request → response (core) | Errors | Idempotency / DB effect | Patient projection | Client screen |
|---|---|---|---|---|---|---|---|---|
| L1 | `POST /v1/predictions/cad-tabular` | LEGACY unchanged | `Idempotency-Key` | Existing schema | Existing catalogue | Existing behavior, no new persistence | n/a | Regression only |
| L2 | `POST /v1/monitoring/observations` | LEGACY unchanged | `Idempotency-Key` | Existing schema | Existing catalogue | Existing 3-table persistence + audit | n/a | Regression only |
| A1 | `POST /v1/auth/login` | A | `Content-Type` | `{email,password}` → `{user_id,role,profile_id,session_token once,expires_at,password_change_required}` | `400`, generic `401 invalid_credentials`, `429` | **No Idempotency-Key declared**; session insert; per-account/per-source failure counters | n/a | All login |
| A2 | `POST /v1/auth/logout` | ANY | `Authorization` | `{}` → `{revoked:true}` | `401` | Revoke current session | n/a | All |
| A3 | `GET /v1/auth/me` | ANY | `Authorization` | → `{user_id,role,status,profile_id}` | `401` | Read only | self only | Profile header |
| A4 | `POST /v1/auth/refresh` | ANY, required in C1 | `Authorization` | `{}` → new `{session_token once,expires_at}`; old session revoked | `401 invalid_session` for revoked/expired token (no new session), `403 password_change_required` | **No Idempotency-Key**; each valid call rotates once; no replay contract | n/a | All |
| A5 | `POST /v1/me/password` | ANY, including temp-password state | `Authorization` | `{current_password,new_password}` → `{user_id,changed_at,password_change_required:false}` | `400`, `401`, `403`, `422` | New KDF verifier; revoke other sessions; audit; no token returned | n/a | Change password |
| A6 | `GET /v1/me/sessions` | ANY | `Authorization` | → list of `{session_id,created_at,expires_at,last_seen_at}` | `401`, `403 password_change_required` | Read only | n/a | Security settings |
| A7 | `DELETE /v1/me/sessions/{session_id}` | ANY, own session | `Authorization` | → `{revoked:true}` | `401`, `403`, `404` | Revoke one session | n/a | Security settings |
| AD1 | `POST /v1/admin/doctors` | AD | `Authorization`, `Idempotency-Key`, `Content-Type` | `{email,display_name,temp_password_policy}` → `{doctor_id,user_id,temp_secret once}` | `400`, `401`, `403`, `409 account_registration_unavailable/idempotency...`, `422` | user+doctor+audit; synthetic `@cardioassist.local` email only; no real contact fields; replay returns `409 secret_not_redisclosable` | n/a | Admin provisioning |
| AD2 | `PATCH /v1/admin/accounts/{user_id}/status` | AD | `Authorization`, `Idempotency-Key` | `{status,reason_code}` → `{user_id,status}` | `400`, `403`, `404`, `409` | Status change; revoke sessions; audit | n/a | Admin account lifecycle |
| V1 | `POST /v1/doctor/verified-visits` | D, own actor | `Authorization`, `Idempotency-Key`, `Content-Type` | `{visit_ref,subject_identifier,asserted_visit_at,attestation_code}` → `{visit_id,attested_at,subject_label}` | `400`, `401`, `403`, `409`, `422` | visit+audit; HMAC/canonical subject id stored, raw ID not stored | n/a | Doctor visit attestation |
| V2 | `GET /v1/doctor/verified-visits/{visit_id}` | D, owns visit | `Authorization` | → visit metadata + subject label | `401`, `403`, `404` | Read only | n/a | Doctor visit detail |
| I1 | `POST /v1/doctor/verified-visits/{visit_id}/invitations` | D, owns visit | `Authorization`, `Idempotency-Key`, `Content-Type` | `{subject_identifier,ttl_seconds}` → `{invitation_id,access_code once,expires_at}` | `400`, `401`, `403`, `409`, `422`; subject mismatch `401 invalid_invitation` | invitation+audit; replay `409 secret_not_redisclosable`; no raw identifier | n/a | Doctor issue code |
| I2 | `POST /v1/doctor/invitations/{invitation_id}/revoke` | D, owns visit | `Authorization`, `Idempotency-Key` | `{reason_code}` → `{invitation_id,revoked_at}` | `401`, `403`, `404`, `409` | Set revoked_at; audit; idempotent | n/a | Doctor revoke code |
| I3 | `GET /v1/doctor/invitations/{invitation_id}` | D, owns visit | `Authorization` | → status metadata, **never code** | `401`, `403`, `404` | Read only | n/a | Doctor invitation status |
| E1 | `POST /v1/patients/register` | A, valid invite | `Idempotency-Key`, `Content-Type` | `{access_code,identifier,email,password,consent_ack}` → `{user_id,patient_id,assignment_id,session_token once}` | generic `401 invalid_invitation`, `409 account_registration_unavailable/idempotency...`, `400`, `422` | Atomic account+identity+assignment+consent+consume+audit; synthetic `@cardioassist.local` email only, no real contact fields; anon replay bound to invitation verifier | self only | Patient signup |
| E2 | `POST /v1/patients/link` | P authenticated | `Authorization`, `Idempotency-Key`, `Content-Type` | `{access_code,identifier,accept_linking:true}` → `{assignment_id,doctor_label}` | generic `401 invalid_invitation/identity_key_change_unsupported`, `403`, `409`, `422` | Verify invitation HMAC with recorded key id and compare canonical subject id; new assignment; consume; no second account | self only | Link second doctor |
| E3 | `GET /v1/me/assignments` | P | `Authorization` | → `{assignment_id,doctor_label,active,assigned_at}` | `401`, `404` | Read own assignments | self only | Patient doctor selection |
| E4 | `POST /v1/doctor/assignments/{assignment_id}/revoke` | D, owns assignment | `Authorization`, `Idempotency-Key` | `{reason_code}` → `{revoked_at}` | `401`, `403`, `404`, `409` | Set revoked_at; immediate access loss; audit | n/a | Doctor end assignment |
| E5 | `POST /v1/me/assignments/{assignment_id}/revoke` | P, own assignment | `Authorization`, `Idempotency-Key` | `{reason_code}` → `{revoked_at}` | `401`, `403`, `404`, `409` | **Assignment revocation only**; revokes this doctor's access, not patient-wide consent | self only | Patient ends one doctor link |
| E6 | `POST /v1/me/consent/synthetic-demo/revoke` | P, own account | `Authorization`, `Idempotency-Key` | `{reason_code}` → `{consent_id,revoked_at}` | `401`, `403`, `404`, `409` | Patient-wide withdrawal of the single active `synthetic_demo` consent; new assessments blocked; immutable history retained | self only | Patient consent withdrawal |
| H1a | `GET /v1/me/health-profile` | P, own | `Authorization` | — → `{profile_id,schema_version,fields,provenance,superseded_at}` | `401`, `404` | Read only | self only | Patient profile |
| H1b | `PATCH /v1/me/health-profile` | P, own | `Authorization`, `Idempotency-Key`, `Content-Type` | `{schema_version,fields,provenance}` → `{profile_id,schema_version,created_at}` | `400`, `401`, `403 password_change_required`, `409 version_conflict`, `422` | New version row; supersede old; audit | self only | Patient profile edit |
| S1 | `POST /v1/assessments` | P, own, consent active | `Authorization`, `Idempotency-Key`, `Content-Type` | `{assignment_id,health_profile_id,panel_id,panel_version,inputs}` → `{assessment_id,status,snapshot_sha256,attempt_id}` | `400`, `401`, `403`, `409 assignment_selection_required`, `422 provenance_not_admissible`, `503` only if attempt cannot be created | assessment+snapshot+attempt+idempotency; `source_contract.source_kind` server-assigned; client-supplied protected provenance rejected | status only | Patient assessment start |
| S2 | `GET /v1/assessments/{id}` | P owner or D via assignment | `Authorization` | → role-redacted assessment | `401`, `403`, `404` | Read only | status only until Decision B | Both detail |
| S3 | `GET /v1/me/assessments` | P, own | `Authorization` | paginated `{assessment_id,status,created_at,review_state}` | `400`, `401` | Read only | status only | Patient history |
| D1 | `GET /v1/doctor/patients` | D, own assignments | `Authorization` | paginated `{assignment_id,patient_label,active}` | `400`, `401`, `403` | Read only | n/a | Doctor patient list |
| D2 | `GET /v1/doctor/assignments/{assignment_id}/assessments` | D, owns assignment | `Authorization` | review queue by status | `400`, `401`, `403`, `404` | Read only | n/a | Doctor queue |
| D3 | `POST /v1/assessments/{id}/reviews` | D via assessment assignment | `Authorization`, `Idempotency-Key` | `{decision,reason_code,rationale}` → `{review_id,effective_state}` | `401`, `403`, `404`, `409 review_conflict/transition_conflict`, `422` | Append review + state + notification + audit | review state only | Doctor review |
| D4 | `POST /v1/assessments/{id}/follow-up` | D via assessment assignment | `Authorization`, `Idempotency-Key` | `{note,prescription_json}` → `{message_id,notification_id}` | `401`, `403`, `404`, `409 duplicate_follow_up`, `422 not_reviewed` | Atomic message+notification+audit | note/prescription content | Doctor follow-up |
| M1 | `GET /v1/me/messages` | P, own | `Authorization` | paginated messages + read state | `400`, `401` | Read only | self only | Patient inbox |
| M2 | `GET /v1/me/notifications` | P, own | `Authorization` | paginated notifications | `400`, `401` | Read only | self only | Patient notifications |
| M3 | `POST /v1/me/notifications/{id}/read` | P, own | `Authorization`, `Idempotency-Key` | `{}` → `{read_at}` | `401`, `404`, `409 version_conflict` | Set read_at; audit | self only | Patient inbox |
| H2 | `GET /v1/me/history` | P, own | `Authorization` | paginated authorized assessments/reviews/messages/notifications | `400`, `401` | Read only | redacted | Patient longitudinal history |
| H3 | `GET /v1/doctor/assignments/{assignment_id}/history` | D, owns assignment | `Authorization` | paginated history for that assignment only | `400`, `401`, `403`, `404` | Read only | n/a | Doctor longitudinal history |

### 2.1 Frozen C1 field contract (C0-F01, C0-F06)

| Operation | Required request fields (type / constraint) | Response fields (type) | Role-specific projection |
|---|---|---|---|
| A1 | `email` normalized `email_norm`, 1–254 bytes, synthetic `@cardioassist.local` only; `password` string 12–128 UTF-8 bytes, opaque | `user_id` uuid str, `role` enum, `profile_id` uuid str|null, `session_token` str once, `expires_at` RFC3339, `password_change_required` bool | self only; temp-password state limits routes to A3/A5/A2 |
| A4 | empty object | `session_token` str once, `expires_at` RFC3339 | self only; old token revoked; revoked/expired token → `401 invalid_session` |
| A5 | `current_password`, `new_password` strings 12–128 bytes, opaque | `user_id`, `changed_at`, `password_change_required:false` | no token; other sessions revoked; only route that clears temp-password state |
| AD1 | `email` normalized synthetic string ending `@cardioassist.local`; `display_name` synthetic label 1–128; `temp_password_policy` enum `{one_time_secret}`; no phone/address/real-name fields | `doctor_id`, `user_id`, `temp_secret` str once | admin only; temp secret never replayed |
| AD2 | `status` enum `{ACTIVE,SUSPENDED,DISABLED}`, `reason_code` string 1–64 | `user_id`, `status` | admin only; all sessions revoked |
| V1 | `visit_ref` string 1–128; `subject_identifier` string matching `^DEMO-ID-[0-9]{3,6}$`; `asserted_visit_at` RFC3339; `attestation_code` enum `{PRIOR_IN_PERSON_VISIT_DEMO,PRIOR_TELEHEALTH_VISIT_DEMO}` | `visit_id`, `attested_at`, `subject_label` | doctor owner only; raw ID never returned |
| I1/I2/I3 | I1: `subject_identifier` same grammar, `ttl_seconds` int 3600–259200. I2: `reason_code` string 1–64. I3: no body | `invitation_id`, `access_code` once (I1), `expires_at`/`revoked_at` (I1/I2), status metadata (I3; never code) | doctor owner only |
| E1 | `access_code` str 32–256; `identifier` demo grammar; `email` normalized synthetic `@cardioassist.local` string; `password` str 12–128 bytes; `consent_ack` bool true; no phone/address/real-name fields | `user_id`, `patient_id`, `assignment_id`, `session_token` once | self only; no other patient's email/identifier; creates one active patient-wide consent |
| E2 | `access_code`, `identifier`, `accept_linking:true` | `assignment_id`, `doctor_label` | self only; canonical subject comparison |
| E3/E4/E5 | E4/E5: `reason_code` string 1–64 | assignment list or `{revoked_at}` | own assignments only |
| H1a/H1b | H1b: `schema_version` string, `fields` object, `provenance` object; `fields` cannot change once referenced by a snapshot | `{profile_id,schema_version,created_at}` or profile projection | patient self only |
| S1 | `assignment_id`, `health_profile_id` uuid str; `panel_id` string; `panel_version` string; `inputs` object matching five-field DA-A2 schema | `assessment_id`, `status`, `snapshot_sha256`, `attempt_id` | status only until Decision B; protected provenance server-assigned |

All optional fields are nullable only where the table above or the architecture §5 says NULL; every enum is closed. All timestamps are UTC RFC3339. All idempotent writes require `Idempotency-Key` except A1/A4. None of these values is accepted from the client for `source_contract.source_kind`, `user_id`, role, status, `assessment.status`, generation, fence or result fields.

## 3. Validation, headers, errors and replay (C0-F03/C0-F06)

- Headers: `Authorization: Bearer <token>` is required on every authenticated operation; `Idempotency-Key` is required on every operation whose row marks it, including PATCH H1b; `Content-Type: application/json` is required on all listed bodies. `Authorization`/`Idempotency-Key` are OpenAPI header parameters, never body fields. A1/A4 ignore and do not declare `Idempotency-Key`.
- All requests: strict UTF-8 JSON, duplicate object member rejection, non-finite number rejection, exact content type. Passwords are opaque bytes with no normalization.
- Schema validation before domain validation. Enrollment order: token verifier → expiry/revocation/consumed → invitation HMAC under recorded `identifier_key_id` → canonical subject check → consent → uniqueness → commit.
- Status catalogue: `400` malformed/schema; `401` unauthenticated or generic auth/invitation failure; `403` wrong role, suspended/disabled, `password_change_required`, or unsupported identity-key change; `404` wrong owner/nonexistent resource; `409` idempotency/domain/generation/version conflicts; `422` semantic/value validation including protected provenance; `429` rate limit; `503` only when inference cannot be attempted. Wrong owner is `404`, wrong role `403`.
- Replay identity is `UNIQUE(replay_scope,key_hash,actor_binding,operation,target_ref)`; authenticated scope uses `user:<user_id>`, anonymous enrollment uses `anon:<invitation verifier digest>` and `target_ref=invitation_id`. **Lookup is only by the complete identity; there is no global key lookup.** A key presented by a different actor is simply not found and cannot reveal another actor's replay existence, status, identifiers or payload; no cross-actor scope conflict is returned. Within the same actor, different public or keyed secret fingerprints → `409 idempotency_key_conflict` and same key with different operation/target → `409 idempotency_scope_conflict`.
- Frozen lookup order: (1) validate structure/header presence; (2) compute actor-bound identity and keyed fingerprints; (3) look up that identity only; (4) on matching fingerprints return redacted replay or `409 secret_not_redisclosable` without re-checking invitation state or reopening a consumed invitation; (5) on fingerprint conflict return `409 idempotency_key_conflict`; (6) only when no row exists run invitation-state, subject, consent and uniqueness checks then commit effect plus idempotency row. If the idempotency TTL expired, consumed invitations still fail generically.
- Secret-bearing response replay returns `409 secret_not_redisclosable` with non-secret identifiers only. No password, access code, session token, raw identifier or full credential response is persisted or replayed. Lost response: revoke/reissue invitation or log in again; consumed invitations are permanent.
- Rate limits: durable per-account, per-source and per-invitation buckets; five failed login attempts/15 min → 15 min lock; five failed invitation attempts → invitation revoked. Unknown-invitation attempts are recorded through `workflow_audit_event` with keyed code digest and NULL invitation FK.
- New error codes are added to versioned `errors.yaml`; no legacy code meaning changes. Legacy L1 schemas and L2 optional `Idempotency-Key` behavior and fixtures remain unchanged.

## 4. Synthetic examples (all fictitious)

- Admin provisions `demo.doctor@cardioassist.local`; doctor attests `DEMO-VISIT-001` for `DEMO-ID-001`; invitation code shown once locally; patient registers with `DEMO-ID-001`; second doctor links same patient via a new attested visit and a new invitation under the same single `demo-v1` key (key replacement refused on the populated DB); patient profile uses five-field synthetic panel `age=58, sex=1, cp=3, trestbps=134, restecg=0` with `mmHg` unit and server-assigned `synthetic_demo_patient_entry` provenance; assessment status becomes `INFERENCE_UNAVAILABLE` until Decision A, else `PENDING_REVIEW` after authorized success; doctor reviews ACCEPTED, writes note and demo prescription; notification state PENDING→DELIVERED→READ.
- No real Egyptian national ID, real patient data, real credential, private bundle or actual prescription appears in any example or fixture.

## 5. Acceptance tests per operation (stage-level detail)

Each operation requires: positive actor/owner path; anonymous; wrong role; cross-user/cross-assignment object; malformed JSON/duplicate keys; schema/value failure; idempotent replay; key/payload conflict; one-time secret non-redisclosure where relevant; restart persistence where relevant; role redaction; audit record check; and log-scan asserting no raw identifier/token/secret.

Additional closure tests at C1: key-check metadata detects same-key-id material replacement before any write on a populated DB; different actors presenting the same Idempotency-Key cannot detect each other's records; a legitimate consumed-invitation replay returns only the authorized redacted result or `secret_not_redisclosable` and never reopens the invitation; E5 revokes only one assignment while E6 revokes patient-wide consent; active consent is created at E1, checked at S1 and inference completion, and withdrawn only at E6; refresh with a revoked token returns `401 invalid_session` and creates no session; synthetic-demo accounts reject real email domains, phone/address/real-name fields.

Additional C0-F tests at C1: `email_norm` case/whitespace normalization and UNIQUE duplicate → generic `409 account_registration_unavailable`; password with leading/trailing spaces hashes/verifies byte-for-byte; temp-password state blocks every route except A1/A3/A5/A2; suspended/disabled login rejected generically; duplicate fictitious identity across key versions rejected by `UNIQUE(canonical_subject_id)`; populated-DB key replacement refused; authenticated link rejects cross-key HMAC equality; replay with changed password/code fingerprint → `409 idempotency_key_conflict`; replay of secret-bearing response → `409 secret_not_redisclosable`; unknown invitation attempt audit has no raw code and NULL invitation FK; per-account/per-source/per-invitation limits enforced independently; GET and PATCH H1 are distinct allowlist operations; client-supplied provenance rejected. Stage-specific exact test paths are in the stage plan and test-evidence document.

## 6. Integration readiness

Every new operation is `PROPOSED` / `NOT_RUN`. Legacy L1/L2 are `IMPLEMENTED_AND_HOSTED_CI_VERIFIED`. Flutter and React consumers are software-team responsibilities; no client code is implemented or accepted here.
