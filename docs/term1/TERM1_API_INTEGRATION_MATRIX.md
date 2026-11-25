# CardioAssist-AI Term 1 — API Integration Matrix and Proposed Contract Inventory

**Status:** `PROPOSED_C0_DEFAULT`. No live OpenAPI file, JSON Schema, runtime route, fixture or test is changed by C0.
**Canonical served spec:** one deterministic composition described in `TERM1_C0_ARCHITECTURE_AND_CONTRACTS.md` §8.
**Legacy operations:** preserved byte/behavior-compatible; exact regression coverage retained.

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
| A1 | `POST /v1/auth/login` | A | — | `{email,password}` → `{session_token once,expires_at,role,profile_id,password_change_required}` | `400`, generic `401`, `409` replay-with-secret | Durable idempotency redacted; session insert; failure counters | n/a | All login |
| A2 | `POST /v1/auth/logout` | ANY | `Authorization` | `{}` → `{revoked:true}` | `401` | Revoke current session | n/a | All |
| A3 | `GET /v1/auth/me` | ANY | `Authorization` | → `{user_id,role,status,profile_id}` | `401` | Read only | self only | Profile header |
| A4 | `POST /v1/auth/refresh` | ANY, optional proposed | `Authorization` | `{}` → new `{session_token once,expires_at}`; old session revoked | `401`, `409` | Rotate session; no secret in replay | n/a | All |
| A5 | `POST /v1/me/password` | ANY | `Authorization` | `{current_password,new_password}` → `{changed_at}` | `400`, `401`, `422` | New KDF verifier; revoke other sessions; audit | n/a | Change password |
| A6 | `GET /v1/me/sessions` | ANY | `Authorization` | → list of `{session_id,created_at,expires_at,last_seen_at}` | `401` | Read only | n/a | Security settings |
| A7 | `DELETE /v1/me/sessions/{session_id}` | ANY, own session | `Authorization` | → `{revoked:true}` | `401`, `404` | Revoke one session | n/a | Security settings |
| AD1 | `POST /v1/admin/doctors` | AD | `Authorization`, `Idempotency-Key` | `{email,display_name,temp_password_policy}` → `{doctor_id,temp_secret once}` | `400`, `401`, `403`, `409`, `422` | user+doctor+audit; replay has no secret | n/a | Admin provisioning |
| AD2 | `PATCH /v1/admin/accounts/{user_id}/status` | AD | `Authorization`, `Idempotency-Key` | `{status,reason_code}` → `{user_id,status}` | `400`, `403`, `404`, `409` | Status change; revoke sessions; audit | n/a | Admin account lifecycle |
| V1 | `POST /v1/doctor/verified-visits` | D, own actor | `Authorization`, `Idempotency-Key` | `{visit_ref,subject_identifier,asserted_visit_at,attestation_code}` → `{visit_id,attested_at,subject_label}` | `400`, `403`, `409`, `422` | visit+audit; HMAC stored, raw ID not stored | n/a | Doctor visit attestation |
| V2 | `GET /v1/doctor/verified-visits/{visit_id}` | D, owns visit | `Authorization` | → visit metadata + subject label | `401`, `403`, `404` | Read only | n/a | Doctor visit detail |
| I1 | `POST /v1/doctor/verified-visits/{visit_id}/invitations` | D, owns visit | `Authorization`, `Idempotency-Key` | `{subject_identifier,ttl_seconds}` → `{invitation_id,access_code once,expires_at}` | `400`, `403`, `409`, `422`; subject mismatch `422 subject_binding_mismatch` | invitation+audit; replay `409 secret_not_redisclosable` | n/a | Doctor issue code |
| I2 | `POST /v1/doctor/invitations/{invitation_id}/revoke` | D, owns visit | `Authorization`, `Idempotency-Key` | `{reason_code}` → `{invitation_id,revoked_at}` | `401`, `403`, `404`, `409` | Set revoked_at; audit; idempotent | n/a | Doctor revoke code |
| I3 | `GET /v1/doctor/invitations/{invitation_id}` | D, owns visit | `Authorization` | → status metadata, **never code** | `401`, `403`, `404` | Read only | n/a | Doctor invitation status |
| E1 | `POST /v1/patients/register` | A, valid invite | `Idempotency-Key` | `{access_code,identifier,email,password,consent_ack}` → `{user_id,patient_id,assignment_id,session_token once}` | generic `401 invalid_invitation`, `400`, `409`, `422` | Atomic account+identity+assignment+consent+consume+audit; replay never mints new session/account | self only | Patient signup |
| E2 | `POST /v1/patients/link` | P authenticated | `Authorization`, `Idempotency-Key` | `{access_code,identifier,accept_linking:true}` → `{assignment_id,doctor_label}` | generic `401`, `403`, `409`, `422` | Verify same subject HMAC; new assignment; consume; no second account | self only | Link second doctor |
| E3 | `GET /v1/me/assignments` | P | `Authorization` | → `{assignment_id,doctor_label,active,assigned_at}` | `401`, `404` | Read own assignments | self only | Patient doctor selection |
| E4 | `POST /v1/doctor/assignments/{assignment_id}/revoke` | D, owns assignment | `Authorization`, `Idempotency-Key` | `{reason_code}` → `{revoked_at}` | `401`, `403`, `404`, `409` | Set revoked_at; immediate access loss; audit | n/a | Doctor end assignment |
| E5 | `POST /v1/me/assignments/{assignment_id}/revoke` | P, own assignment | `Authorization`, `Idempotency-Key` | `{reason_code}` → `{revoked_at}` | `401`, `403`, `404`, `409` | Consent withdrawal; same effect | self only | Patient consent withdrawal |
| H1 | `GET/PATCH /v1/me/health-profile` | P, own | `Authorization`, `Idempotency-Key` on PATCH | `{schema_version,fields,provenance}` → profile projection | `400`, `401`, `409 version_conflict`, `422` | New version row; supersede old; audit | self only | Patient profile |
| S1 | `POST /v1/assessments` | P, own, consent active | `Authorization`, `Idempotency-Key` | `{assignment_id,health_profile_id,panel_id,panel_version,inputs,source_contract}` → `{assessment_id,status,snapshot_sha256,attempt_id}` | `400`, `401`, `403`, `409 assignment_selection_required`, `422 provenance_not_admissible`, `503` only if attempt cannot be created | assessment+snapshot+attempt+idempotency; source server-assigned | status only | Patient assessment start |
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

## 3. Validation and error semantics

- All requests: strict UTF-8 JSON, duplicate object member rejection, non-finite number rejection, exact content type `application/json`.
- Schema validation before domain validation; domain validation order for enrollment: token verifier → expiry/revocation/consumed → subject HMAC → consent → uniqueness → commit.
- Wrong owner returns `404` (not `403`) to avoid existence leakage; wrong role returns `403`; unauthenticated `401`.
- Login/link/invitation failures are generic `401 invalid_invitation`/`invalid_credentials`; no differentiated messages for expired/revoked/consumed/wrong identifier.
- Idempotency conflict takes precedence over semantic validation where the legacy contract already establishes that rule; new operations follow the same rule unless the owner approves otherwise.
- `409 secret_not_redisclosable` for replay of one-time-secret responses; no secret is ever included in the replay body.
- New error codes are added to the versioned `errors.yaml`; no legacy code meaning is changed.

## 4. Synthetic examples (all fictitious)

- Admin provisions `demo.doctor@cardioassist.local`; doctor attends `DEMO-VISIT-001` for `DEMO-ID-001`; invitation code shown once locally; patient registers with `DEMO-ID-001`; second doctor links same patient via a new attested visit and new invitation; patient profile uses five-field synthetic panel `age=58, sex=1, cp=3, trestbps=134, restecg=0` with `mmHg` unit and `synthetic_demo_patient_entry` provenance; assessment status becomes `INFERENCE_UNAVAILABLE` until Decision A, else `PENDING_REVIEW` after authorized success; doctor reviews ACCEPTED, writes note and demo prescription; patient notification UNREAD→READ.
- No real Egyptian national ID, real patient data, real credential, private bundle or actual prescription appears in any example or fixture.

## 5. Acceptance tests per operation (stage-level detail)

Each operation requires: positive actor/owner path; anonymous; wrong role; cross-user/cross-assignment object; malformed JSON/duplicate keys; schema/value failure; idempotent replay; key/payload conflict; one-time secret non-redisclosure where relevant; restart persistence where relevant; role redaction; audit record check; and log-scan asserting no raw identifier/token/secret. Stage-specific exact test paths are in the stage plan and test-evidence document.

## 6. Integration readiness

Every new operation is `PROPOSED` / `NOT_RUN`. Legacy L1/L2 are `IMPLEMENTED_AND_HOSTED_CI_VERIFIED`. Flutter and React consumers are software-team responsibilities; no client code is implemented or accepted here.
