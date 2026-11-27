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

---

# Appendix A — C1 closure reconciliation (appended 2026-11-27; earlier sections preserved verbatim)

**This appendix is append-only.** §1–§5 above retain their original statuses as written at
C0/C1 revision time. Where this appendix disagrees with them, this appendix is current and
the earlier text is historical evidence, not a live status.

## A.1 Exact merged C1 baseline and owner acceptance

| Item | Value | Evidence category |
|---|---|---|
| Delivery branch | `delivery/term1-prototype` | GITHUB |
| Exact merged baseline | `2a8a209fba20d0c7c43c255ede4545bcaa5f34b7` | GITHUB / SOURCE_VERIFIED (`git rev-parse HEAD`) |
| Merge parents | `310534e1e334ba3be4f308f5a66d88c22b5842e0` (base), `524d57cb17c995ea5ab299a6479f66b406751e07` (accepted candidate) | GITHUB |
| Accepted candidate tree | `1a117475e2d4ccb57d0902f368885065ee9e4145` — identical to the merge tree, 0 changed files | GITHUB |
| PR #144 | `MERGED` 2026-11-27T01:54:17Z, title *feat(term1): C1 authentication, verified enrollment and durable identity workflow* | GITHUB |
| Owner acceptance | `ACCEPT-TERM1-C1-BOUNDED-PROTOTYPE-BASELINE`, [comment 7207660039](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/144#issuecomment-7207660039) 2026-11-27T01:53:34Z | GITHUB |
| Post-merge identity verification | [comment 7207679643](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/144#issuecomment-7207679643) 2026-11-27T01:54:59Z | GITHUB |
| Post-merge hosted CI at `2a8a209…` | 4/4 workflows, 8/8 jobs SUCCESS: runs 45925221406, 45925221497, 45925221365, 45925221446 | GITHUB API; see `TERM1_TEST_EVIDENCE.md` §7.1 |
| PR #142 | still OPEN / DRAFT, base `main`; not merged by this work | GITHUB |
| PR #141, Issue #132 | OPEN; separate research track; untouched | GITHUB boundary only |
| Arena closure branch | `arena/807e6023-cardioassist-ai`, from `2a8a209…` | GITHUB / local |

## A.2 Status declarations (supersedes §2 for C1 and C2 only)

```
C0_STATUS=ACCEPTED_PENDING_OWNER_CONFIRMATION_OF_RECONSTRUCTED_COMMIT_PROVENANCE
C1_STATUS=OWNER_ACCEPTED_BOUNDED_BASELINE_MERGED__HTTP_CONTRACT_CLOSURE_PENDING_INDEPENDENT_REVIEW
C2_STATUS=DOCUMENTATION_READINESS_ONLY__NOT_STARTED__BLOCKED_ON_OWNER_DECISIONS_OQ-1..OQ-10
C3_STATUS=NOT_STARTED
C4_STATUS=NOT_STARTED
AI_SERVING_AUTHORIZATION=PENDING            (A1 PENDING, A2 PENDING, A3 PENDING)
PATIENT_SCORE_DISPLAY_AUTHORIZATION=PENDING (B PENDING)
WINDOWS_VERIFICATION_STATUS=OWNER_VERIFIED_AT_524d57c_AND_MERGE; CLOSURE_BRANCH_NOT_RUN_ON_WINDOWS
HOSTED_CI=OWNER_DISPATCH_REQUIRED_FOR_CLOSURE_BRANCH
HOSTED_CI_AT_MERGED_BASELINE=4_OF_4_WORKFLOWS_8_OF_8_JOBS_SUCCESS
LEGACY_RESEARCH_CI_STATUS=FAILURE_ON_PYTHON_3_11 (inherited; not suppressed, not waived)
```

`C0_STATUS` changes only in the sense that the owner accepted and merged the bounded C1
baseline that followed it; the reconstructed-vs-original commit disclosure (C0-F08/B-06)
still requires the owner's explicit acknowledgement.

## A.3 C1 acceptance, as recorded — not as inferred

Owner acceptance was explicitly **bounded**: `delivery/term1-prototype` only, no real
clinical data, no model activation, no patient-facing AI result, no research-gate closure,
no merge of PR #142 into `main`, and C2 "subject to post-merge verification and its
applicable authorization gates". The acceptance text also made the HTTP contract work a
**prerequisite**:

> Outstanding HTTP contract coverage obligations must be completed before dependent C2
> implementation.

Acceptance of the bounded baseline is therefore **not** acceptance of exhaustive C1
contract conformance, and this branch does not treat it as such.

## A.4 Migration rollback decision, as ratified by the owner

The owner's acceptance comment approved the safe rollback policy in these terms:

> In-place downgrade is permitted only on disposable databases without C1 state. Populated
> operational databases require verified backup restoration and explicit recovery-point
> acceptance.

Recorded state: **OWNER_RATIFIED** for the invariant; operational backup restoration still
requires recovery-point acceptance and must preserve the current database. The isolated
restoration test is not a live-recovery certification. The proposal text in
`TERM1_C1_ROLLBACK_POLICY_PROPOSAL.md` is preserved verbatim; see its Addendum for the
decision record and evidence binding.

## A.5 Closure work on this branch — defects found and fixed

Owner-mandated C1 contract obligations were completed on
`arena/807e6023-cardioassist-ai` from `2a8a209…`. The work is a targeted closure, not a C1
reimplementation. **Three real defects** were found by the new tests and fixed with
narrowly scoped changes; each fix is proven load-bearing by a negative control.

| ID | Defect | Operations | Fix | Negative control |
|---|---|---|---|---|
| **D-01** | `500 text/plain` instead of declared `503 identity_key_configuration_error` — settings were resolved outside the guarded block; three handlers never checked configuration | 9 idempotent + V2 + I3 + E3 | resolve settings inside `try`; add fail-closed `handler.settings()` to V2/I3/E3 | 11 tests fail when reverted |
| **D-02** | replay body (`idempotent_replay: true`) violated its own `additionalProperties: false` schema | AD2, I2, E4, E5, E6 | declare `"idempotent_replay": {"const": true}`, matching the two schemas that already did | 1 test fails when reverted |
| **D-03** | served document under-declared reachable statuses and their closed codes | all 20 | each YAML `responses:` block lists the exact catalogue codes per status; composed into the served document as `x-error-codes`; 3 contract tests enforce catalogue agreement | contract tests fail on drift |

No assertion was weakened, no body normalisation was added, and no operation is skipped.

## A.6 C2 readiness — documentation only

`TERM1_C2_IMPLEMENTATION_DEPENDENCY_MAP.md` records the eight C2 workstreams (W1…W8), their
hard prerequisites, failure modes and reviewer artefacts; the dependency-correct build
order; and the ten owner decisions (OQ-1…OQ-10) that must be taken before C2 code. Its
decisive finding: **C2 is not blocked on the AI gates; a full-score C2 is.** W1…W7 are
ordinary software buildable in a documented `C2_SAFE_SCOPE`; only a score needs A3 and only
a patient-visible score needs B.

No C2 runtime code, migration, route, settings key, dependency, model or artifact exists.

## A.7 Stage readiness (supersedes §5)

| Stage | Readiness | Reason |
|---|---|---|
| C0 | ACCEPTED (commit-provenance acknowledgement still outstanding) | Baseline merged; B-06 disclosure unchanged |
| C1 | OWNER_ACCEPTED_BOUNDED_BASELINE; HTTP closure PENDING_INDEPENDENT_REVIEW | Local: 291 C1 tests (30 new closure), 1189 combined backend+contracts with `-W error`, 711 audit. No hosted CI at this branch head; no native Windows run of this branch |
| C2 | NOT_STARTED — documentation readiness only | Depends on C1 closure acceptance and OQ-1…OQ-10; A1/A2/A3/B PENDING |
| C3 | NOT_STARTED | Depends on C2 acceptance |
| C4 | NOT_STARTED | Depends on prior stages |

This appendix is not self-acceptance. Only the independent reviewer and the human owner may
accept the closure work, and only the owner may take OQ-1…OQ-10.
