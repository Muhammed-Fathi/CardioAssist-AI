# CardioAssist-AI Term 1 — Stage Progress and Reviewer Correction Ledger

**Status:** C0 corrected after final independent review; pending final re-review, owner Windows verification and explicit acceptance. No implementation stage started.

## 1. Checkpoint ledger

| Item | Value | Evidence category |
|---|---|---|
| Review date | 2026-11-25 (UTC) | — |
| main | `c6a6bdee46a552a2b0d705a723c862ff8a95be4d` | SOURCE_VERIFIED / GITHUB |
| Prototype HEAD at C0 start | `bca75b4646dbde26e495201938b7ae01ea7e0d21` | GITHUB |
| PR #142 | OPEN / DRAFT, base main, 4 docs-only commits, `merged_at=null` | GITHUB |
| Test merge SHA | `8c4be2fb6d5d088d456ec5be935a2b30b5158173` — not a merge | GITHUB |
| PR #141 | OPEN / DRAFT, head `9fb6d5173171bbdc22fd1528131bd2dd5b8963f5` | GITHUB; boundary only |
| Issue #132 | OPEN | GITHUB; boundary only |
| PR #143 | OPEN / DRAFT, base `delivery/term1-prototype` at `bca75b4…`, head `arena/bdbd8a6e-cardioassist-ai` at `a32aca29f68e5330344b7cc79e9956acdf446a2a`, 6 commits ahead / 0 behind, 11 files, +2146/−0 | GITHUB |
| Original five C0 commits | `94465c7c1454c7506c172cffc1694a8047463d99`, `0475193dd50247f64f7cba4f6adacab32dc7711b`, `45ad692363fb0a3f019f26ac30f796548ae2f198`, `4a60f7f1c4fa0eb134d31755141b341952477053`, `4f097401366d7d0f86086b72982c0632c7c58558` — unrecoverable objects; NOT the published commits | SOURCE_VERIFIED; disclosure in plan §1.2 |
| Reconstructed five C0 commits | `6037ec7dd80c29ca6c60acba581639276bab7ec2`, `4c4584b07ba5575064cdb05f74802b4c706bbb23`, `c823b032e45365c0be5dcb15547dd12937f851f5`, `ee9804f3e2821fe062e07eac073f52105d3c4ee3`, `51a8cfeaf8723956872370f95f0cc445ad3838eb`; plus non-rewriting merge `a32aca29f68e5330344b7cc79e9956acdf446a2a` | GITHUB / SOURCE_VERIFIED |
| Native Windows | NOT_RUN | — |

## 2. Status declarations

```
C0_STATUS=CORRECTED_PENDING_FINAL_REVIEW_AND_OWNER_WINDOWS_VERIFICATION
C1_STATUS=REVISED_PENDING_INDEPENDENT_REVIEW
C2_STATUS=NOT_STARTED
C3_STATUS=NOT_STARTED
C4_STATUS=NOT_STARTED
AI_SERVING_AUTHORIZATION=PENDING
PATIENT_SCORE_DISPLAY_AUTHORIZATION=PENDING
WINDOWS_VERIFICATION_STATUS=NOT_RUN
HOSTED_CI=OWNER_DISPATCH_REQUIRED
LEGACY_RESEARCH_CI_STATUS=FAILURE_ON_PYTHON_3_11 (inherited; not suppressed)
```

## 3. C0 deliverables produced

- `CARDIOASSIST_TERM1_PREFLIGHT_REVIEW_VERDICT.md` — independent reviewer verdict preserved in content (trailing whitespace normalized).
- `CARDIOASSIST_TERM1_ARENA_PREFLIGHT_REVIEW.md` — prior Arena preflight report preserved in content (trailing whitespace normalized).
- `TERM1_STAGE_EXECUTION_PLAN.md` — supersession, owner-approved vs proposed values, stage gates, CI baseline.
- `TERM1_C0_ARCHITECTURE_AND_CONTRACTS.md` — threat model, ERD/data dictionary, idempotency/secrets, state machines, canonical contract composition, migration ordering.
- `TERM1_API_INTEGRATION_MATRIX.md` — complete proposed operation inventory and regression strategy.
- `TERM1_AI_READINESS_MATRIX.md` — candidate matrix, candidate B design, A/B proposals.
- `TERM1_DECISION_REGISTER.md` — owner-approved direction, proposed defaults, pending authorizations.
- `TERM1_TEST_EVIDENCE.md` — CI baseline, test strategy, evidence labels.
- `TERM1_BLOCKER_REGISTER.md` — blockers and dispositions.
- `TERM1_WINDOWS_VERIFICATION_RUNBOOK.md` — corrected stage-based PS5.1 procedure.

Historical `TERM1_INTEGRATED_PROTOTYPE_MASTER_PLAN_20261125.md`, `ARENA_NEW_SESSION_MASTER_PROMPT_20261125.md`, `CARDIOASSIST_TERM1_NEW_CHAT_HANDOFF_20261125.md` and `WINDOWS_LOCAL_VERIFICATION_RUNBOOK_20261125.md` are preserved unchanged; the new plan records the supersession.

## 4. Reviewer correction resolution (R-01…R-08)

| ID | Owner/reviewer requirement | C0 resolution | Location | Verification needed |
|---|---|---|---|---|
| R-01 | Remove `patient.doctor_id`; assignment-based ownership; multiple authorized assignments; patient selection; historical freeze | No `patient.doctor_id` in ERD; doctor access via active `doctor_patient_assignment` and assessment `assignment_id`; `GET /v1/me/assignments` and `assignment_id` selection; revocation keeps history under original assignment | Architecture §3.6, §4, §7.4; API E3/D1/D2/H3 | Owner confirms P-12…P-14; C1 negative IDOR tests |
| R-02 | Bind identity at visit attestation; prevent B code on A visit; HMAC encoding/key separation/rotation; server timestamps; no clinical free text | Visit stores subject HMAC, invitation inherits; strict demo grammar; exact HMAC byte encoding; purpose separation; `demo-v1` with re-attestation rotation; `asserted_visit_at` vs `attested_at`; controlled attestation codes | Architecture §3.4, §3.5; API V1/I1 | Owner confirms P-09…P-11; C1 mismatch/rotation tests |
| R-03 | Add revoke, link/accept, assignment revoke, account lifecycle; lockout semantics; transport; fix indexes | I2, E2, E4/E5, AD2, A5 added; generic 401 lockout; bearer transport; indexes use actual columns; local admin bootstrap | API §2; Architecture §3.1–3.3, §5.2 | Owner confirms P-01…P-08; C1 contract tests |
| R-04 | Secret-safe idempotency; one-time disclosure/lost response; durable failure counters | Hash-only keys, redacted replay, `secret_not_redisclosable`, no token/code in records; failure rows in separate tx | Architecture §6; API §3 | C1 replay/lockout/rate-limit tests |
| R-05 | One authoritative result; generation/lease/fencing; review conflicts; follow-up eligibility; test doubles only in tests | Single `inference_result`; generation/fence CAS; history retained, stale hidden; review conflict rules; no AI prescription author | Architecture §4, §7.3–7.4 | C2/C3 tests; Decision A |
| R-06 | One canonical served OpenAPI; complete allowlist; preserve legacy coverage; headers as headers | Deterministic composition into single served spec; legacy file unchanged; four named test classes; headers in `parameters` | Architecture §8; API §1 | C1/C2 contract tests and owner confirmation |
| R-07 | PS5.1 exit-code checks; safe clone reuse; fresh DBs; exact pytest paths; correct deps | New Windows runbook with explicit `$LASTEXITCODE`, ff-only fetch/merge, unique DBs, preservation DB, exact paths, full-suite deps | `TERM1_WINDOWS_VERIFICATION_RUNBOOK.md` | Owner Windows execution (NOT_RUN) |
| R-08 | Exact candidate B, A/B proposals, deterministic trust/rights, no clinical claim | Full candidate B design, A/B ratification text, rebuild/digest/trust requirements, non-authorizations | `TERM1_AI_READINESS_MATRIX.md` §2/§3 | Owner gates A1/A2/A3/B; C2 independent review |

## 4.1 Final reviewer corrections (C0-F01…F10)

| ID | Resolution | Exact document reference | Verification still required |
|---|---|---|---|
| C0-F01 | Canonical `email_norm` UNIQUE, normalization, synthetic UUID ids, non-enumerating errors, status transitions, mandatory temp-password restriction, frozen password rules | Architecture §3.1/§3.2/§5.1/§5.2; API §2.1/§3; plan P-21…P-23 | Owner confirms P-21…P-23; C1 tests |
| C0-F02 | Blind canonical subject id UNIQUE across key versions; single stable `demo-v1`; key replacement refused on populated DB; link compares canonical id | Architecture §3.4/§3.5/§5; API E1/E2; plan P-10/P-11 | C1 duplicate-across-keys and refusal tests |
| C0-F03 | Actor/operation/target replay identity; keyed secret fingerprints; rate-limit buckets; unknown-invitation audit; redacted replay vs secret_not_redisclosable; login/refresh no Idempotency-Key | Architecture §6.1; API §3; plan P-17/P-24 | C1 replay/rate-limit/audit tests |
| C0-F04 | Referenced-before-dependent migrations; C1 infra in C1; health profile C2; consistent field names; cross-entity constraints; multi-doctor consent | Architecture §9; plan P-25 | C1/C2 migration evidence |
| C0-F05 | Lease + current-generation CAS; one active attempt; assignment/consent at publication; authoritative review state; notification states; exact follow-up eligibility | Architecture §7.3/§7.4 | C2/C3 concurrency tests |
| C0-F06 | GET/PATCH separated allowlist; headers/errors/replay frozen; C1 field contract; server-assigned provenance; legacy schemas unchanged | API §2/§2.1/§3; architecture §8 | C1 contract allowlist test |
| C0-F07 | Four AI gates A1/A2/A3/B, all PENDING | AI matrix §3; decision register A1/A2/A3; plan P-26 | Owner tokens and independent verification |
| C0-F08 | Stage-PR policy, PR #143 evidence, reconstructed/original SHA distinction | Plan §1.2/§2/§5.1; blockers B-06 | Final review and owner acceptance |
| C0-F09 | Complete PS5.1 candidate-before-merge block | `TERM1_WINDOWS_VERIFICATION_RUNBOOK.md` | Owner Windows transcript |
| C0-F10 | Four dispatch attempts blocked by 403; owner dispatch required | `TERM1_TEST_EVIDENCE.md` §5; completion report | Owner dispatch and reviewer verification; no ALL_GREEN claim |

## 4.2 C1 reviewer corrections (C1-R01…C1-R09)

| ID | Owner/reviewer requirement | C1 resolution | Location | Verification |
|---|---|---|---|---|
| C1-R01 | Canonical contract composition from modular YAML source; operation-specific schemas; runtime enforcement | Served `/openapi.json` composed from `shared/contracts/term1/paths-*.yaml`; per-operation request/response JSON Schemas (draft 2020-12) under `shared/contracts/term1/schemas/`; request bodies validated at runtime against the operation-specific schema (422 `validation_failed` on structural violation; business vocabularies kept to handler-specific codes) | `backend/app/term1/openapi.py`, `shared/contracts/term1/paths-*.yaml`, `shared/contracts/term1/schemas/*.json`, `backend/app/term1/api.py` (`body()`) | C1 contract tests (inventory/header sets/catalogue/schema existence); 213/213 C1 tests pass |
| C1-R02 | Temporary-password enforcement; refresh preserves absolute lifetime; lockout; duplicate Authorization; Non-ASCII bearer | `authenticate()` rejects `password_change_required` accounts except `me/password`/`logout`/`me`; refresh keeps original absolute expiry (no lifetime extension); bearer rejects duplicate Authorization headers; non-ASCII bearer → `authentication_required` (no 500); `list_sessions`/`revoke_session` use `handler.authenticate()` (fail-closed `settings()`) | `backend/app/term1/api.py`, `backend/app/term1/sessions.py` | C1 auth/session tests incl. `test_concurrent_refresh_produces_exactly_one_replacement`, `test_suspension_revokes_sessions_and_blocks_reads` |
| C1-R03 | Durable idempotency expiration lifecycle (flush before replacement insert) | `precheck()` deletes expired DurableIdempotency rows and `session.flush()`es before `remember()` inserts a replacement, preventing UNIQUE constraint violation on `(replay_scope, key_hash, actor_binding, operation, target_ref)`. Same-scope key reuse after expiry proven; cross-operation key reuse after expiry proven; permanent invitation consumption after idempotency expiry proven. | `backend/app/term1/idempotency.py`, `tests/backend/c1/test_c1_idempotency.py` | C1 idempotency tests: `test_precheck_deletes_expired_row_then_remembers_without_conflict`, `test_precheck_expired_row_allows_cross_operation_reuse`, `test_consumed_invitation_stays_consumed_after_idempotency_expiry` |
| C1-R04 | Independent source-based enrollment rate limiting; Non-ASCII access codes safe | Source-based enrollment buckets (independent from login) checked inside write transaction; `crypto.invitation_verifier()` encodes with utf-8/replace so Non-ASCII access codes never raise UnicodeEncodeError; failure-hook classification excludes idempotency codes from guessing counts | `backend/app/term1/api.py`, `backend/app/term1/crypto.py` | C1 enrollment/invitation attempt tests: `test_source_based_enrollment_rate_limit`, `test_unknown_invitation_bootstrap_lifecycle` |
| C1-R05 | Single authoritative login transaction; constant-time password verification work | Login under one `BEGIN IMMEDIATE` write transaction; `run_in_threadpool(run)` no-arg (no `None` session); bounded dummy KDF params for unknown/inactive accounts; malformed requests write no failure evidence | `backend/app/term1/api.py`, `backend/app/term1/sessions.py` | C1 auth/login tests |
| C1-R06 | Read-only fail-closed startup key verification incl. `invitation_attempt` probe and exactly-one active key-check row per purpose | `verify_startup` fail-closes populated DB without key checks; `InvitationAttempt` probe table; `verify_or_activate` enforces exactly-one active key-check row per purpose; `verify_identity_keys` fail-closes populated DB without configured material; `handler.settings()` fail-closed on logout/me/refresh/list_sessions/revoke_session | `backend/app/term1/identity.py`, `backend/app/term1/api.py` | C1 audit/keycheck tests |
| C1-R07 | Invitation expiry at the consumption boundary; doctor suspension/disabling effect | `_consume_invitation` rechecks expiry at consumption boundary; `_require_usable_doctor` guard in `register_patient` and `link_patient` | `backend/app/term1/enrollment.py` | C1 enrollment/invitation tests |
| C1-R08 | Relocate C1 suite under `tests/backend/c1/`; existing backend workflow collects every C1 test exactly once; no `.github/workflows/` edit | `git mv tests/c1 tests/backend/c1`; `conftest.py` ROOT `parents[3]`; all `tests.c1.` imports → `tests.backend.c1.`; `test_c1_contracts.py` ROOT `parents[3]` | `tests/backend/c1/` | `pytest tests/backend/c1` collects 205 tests exactly once |
| C1-R09 | Complete C1 revision documentation set | Test evidence, stage progress, decision register, API integration matrix, blocker register, integration documentation, repository-governance basis for additive contract change-set | `docs/term1/` | This ledger; PR #144 (DRAFT, no force-push) |

## 5. Stage readiness

| Stage | Readiness | Reason |
|---|---|---|
| C0 | CORRECTED_PENDING_FINAL_REVIEW_AND_OWNER_WINDOWS_VERIFICATION | Corrections committed to PR #143; final review, exact-head CI, Windows transcript and owner confirmations pending |
| C1 | REVISED_PENDING_INDEPENDENT_REVIEW | C1-R01..C1-R09 corrected in place on branch `arena/2b22dd7d-cardioassist-ai` (HEAD `ff9f794`): canonical contract composition from modular YAML source with operation-specific schemas and runtime enforcement; temporary-password enforcement on all authenticated C1 operations including session listing/revocation; transactional idempotency expiration lifecycle; durable failed-attempt accounting for authenticated link; single authoritative login transaction with constant-time password-verification work; read-only fail-closed startup key verification including `invitation_attempt` probe and exactly-one active key-check row per purpose; invitation expiry at the consumption boundary and doctor suspension/disabling effect; C1 suite relocated to `tests/backend/c1/` (collected exactly once, no workflow edit). Local suite: 213 passed, 0 failed, 0 skipped. Pending independent review; no owner acceptance, no C2. |
| C2 | NOT_STARTED | C1 acceptance, Decision A or documented safe-scope decision, artifact/dependency decision required |
| C3 | NOT_STARTED | C2 acceptance or explicit owner scope revision required |
| C4 | NOT_STARTED | Prior stages and evidence required |

This ledger does not constitute self-acceptance. Only the independent reviewer and human owner may accept C0.
