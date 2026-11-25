# CardioAssist-AI Term 1 — Stage Execution Plan (C0 design package)

**Document status:** CORRECTED C0 DESIGN PACKAGE — awaiting final independent review, owner Windows verification and explicit owner acceptance.
**Date:** 2026-11-25 (UTC); focused C0-F01…F10 corrections dated 2026-11-25.
**Target branch:** `delivery/term1-prototype` (existing Draft PR #142).
**Verified starting HEAD:** `bca75b4646dbde26e495201938b7ae01ea7e0d21`.
**Verified main baseline:** `c6a6bdee46a552a2b0d705a723c862ff8a95be4d`.
**Handoff target:** 2026-12-03 — planning target only, not a guarantee and not authorization to weaken gates.

## 1. Purpose and authority

This document is the authoritative C0 design package for the Term 1 synthetic-only educational prototype. It records the owner-approved direction separately from technical proposals that still require acceptance. It does **not** authorize C1 implementation, model serving, patient score display, stage verification, merge, or scope reduction.

**Evidence category rule:** every claim in this package is labelled `OWNER_APPROVED_DIRECTION`, `PROPOSED_C0_DEFAULT`, `SOURCE_VERIFIED`, `HOSTED_CI_VERIFIED`, `PENDING_AUTHORIZATION`, `BLOCKED`, `NOT_RUN`, or `UNVERIFIED`. None of these labels means "implemented".

### 1.1 Formal publication authorization

Under `AGENTS.md` §Priority, "exact instruction from a human maintainer in the active reviewed milestone" has priority 1. The owner's C0 master prompt in the active milestone explicitly authorizes preparation and documentation of the C0 package and says to commit and push documentation-only changes to the existing prototype branch if publication is permitted by repository governance. That direct maintainer instruction is treated as the formal authorization for **documentation-only** publication in this session. It is not represented as a GitHub comment, PR approval, or stage acceptance, and no approval text is forged.

If a future reviewer requires a posted PR authorization record, the exact owner statement to post is:

> `AUTHORIZE-TERM1-C0-DOCS` — I authorize documentation-only C0 design changes on branch `delivery/term1-prototype` in Draft PR #142. This does not authorize C1 implementation, model serving, patient score display, stage acceptance, or merge.

Arena must not post this on the owner's behalf.

### 1.2 Stage publication policy, evidence and commit reconstruction

The owner revised the publication strategy on 2026-11-25: Arena uses its assigned session branch and publishes a stage-specific Draft PR targeting `delivery/term1-prototype`. This supersedes the earlier cherry-pick transfer plan in this section, which is retained below only as history.

Verified publication evidence (`HOSTED_CI_VERIFIED` for GitHub API state, 2026-11-25 18:54Z):

- Stage PR: https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/143 — OPEN, DRAFT, unmerged; title `docs(term1): C0 architecture, contracts and execution plan`.
- Base: `delivery/term1-prototype` at `bca75b4646dbde26e495201938b7ae01ea7e0d21`; head: `arena/bdbd8a6e-cardioassist-ai` at `a32aca29f68e5330344b7cc79e9956acdf446a2a`.
- GitHub compare: six commits ahead, zero behind; `mergeable=true`, `mergeable_state=clean`; 11 added files, +2146/−0. PR #142 stays OPEN/DRAFT/unmerged at `bca75b4…` targeting main.
- The exact prototype HEAD was merged into the session branch without rewrite; the four historical prototype documents are byte-identical in the PR head.

**Reconstructed versus original commits (must not be conflated):** the five original C0 commit objects `94465c7c…`, `0475193d…`, `45ad6923…`, `4a60f7f1…`, `4f097401…` became unrecoverable in this sandbox after workspace reset; GitHub returned 422 for `4f097401…`. They are **not** the commits published on PR #143. The five reconstructed commits, made from the preserved final document content with the same messages/grouping, are `6037ec7d…`, `4c4584b0…`, `c823b032…`, `ee9804f3…`, `51a8cfea…`; the sixth PR commit is a non-rewriting merge `a32aca29…` of the exact prototype base. Full SHAs are in `TERM1_STAGE_PROGRESS.md` §1.

No owner approval, self-review, merge or stage acceptance is implied by publication.

<details><summary>Superseded historical transfer note (do not execute)</summary>

Earlier text proposed a fast-forward-free cherry-pick of session commits onto an authorized clone of `delivery/term1-prototype`. That plan is obsolete because the original commit objects are unrecoverable and PR #143 now carries the reviewed stage content.

</details>

## 2. Dated supersession of the one-sprint policy

The following old policy is historical and superseded for all subsequent Term 1 work:

- `docs/term1/TERM1_INTEGRATED_PROTOTYPE_MASTER_PLAN_20261125.md` §8: "One branch + one draft PR + one Arena session + incremental evidence checkpoints", C0→C4 in one continuous sprint.
- `docs/term1/ARENA_NEW_SESSION_MASTER_PROMPT_20261125.md`: "ONE CONTINUOUS IMPLEMENTATION SPRINT".

**Supersession record (2026-11-25, owner-approved):** one complete logical engineering stage → one comprehensive stage master prompt → organized implementation commits → independent engineering review → native Windows testing → remediation and retesting → GitHub evidence → explicit owner acceptance → next stage. The historical documents are preserved verbatim; this record identifies the superseded policy but does not rewrite it. No stage advances automatically.

**Second dated supersession (2026-11-25, owner-approved publication strategy):** one assigned Arena branch per logical stage → stage Draft PR targeting `delivery/term1-prototype` → independent review → exact-head hosted CI → owner native Windows tests → corrections/retesting → explicit owner acceptance → owner merge. Each subsequent stage starts from the latest accepted prototype revision. PR #142 remains the overall prototype delivery PR targeting main. This supersedes "no per-stage PRs by default" and the cherry-pick transfer note; it does not grant acceptance or merge authority to Arena.

## 3. Owner-approved direction versus technical proposals

### 3.1 Owner-approved direction (`OWNER_APPROVED_DIRECTION`)

- Stage-based execution with one comprehensive master prompt per stage; existing prototype branch and Draft PR #142; **stage-specific Draft PRs from the assigned Arena branch to `delivery/term1-prototype` are the approved publication path**; no self-approval or automatic merge.
- Preserve the complete workflow: admin provisions doctor → doctor attests prior visit → doctor issues identity-bound Access Code → patient registers → patient becomes associated with doctor → patient completes synthetic health profile → patient initiates assessment → authorized trained AI produces result and explanation → doctor reviews → doctor authors educational follow-up and demo prescription → patient receives notification → persistent history.
- Provisional research result before clinician review remains part of the intended UX **only after separate authorization**; until then patient projection is status-only. No mandatory clinician confirmation before every assessment.
- Architectural direction: one patient account per identity; database support for multiple independently authorized doctor-patient assignments; clinician-attested visit before invitation; synthetic-only identifiers; FastAPI/SQLAlchemy/SQLite/Alembic; secure auth/sessions/RBAC; durable idempotency; dedicated workflow audit; additive contracts preserving legacy behavior; genuinely trained educational AI candidate subject to separate authorization; Flutter/React are software-team responsibilities.
- Do not reduce original required scope without an explicit owner decision.
- Target handoff 2026-12-03 remains a planning target.

### 3.2 Technical defaults proposed by C0 (`PROPOSED_C0_DEFAULT`)

All values in this subsection require owner confirmation at C0 acceptance; none is already approved merely by being listed.

| Area | Proposed default | Decision ID |
|---|---|---|
| Password KDF | `hashlib.pbkdf2_hmac('sha256', utf8_password, 16-byte CSPRNG salt, 600000 iterations, dklen=32)`; store algorithm id, version, iterations, salt and verifier; constant-time compare; no new dependency | P-01 |
| Password policy | 12–128 UTF-8 bytes; no composition rules; **no trimming or normalization of any kind**; leading/trailing spaces significant; reject NUL/control characters | P-02 |
| Session token | 32-byte CSPRNG, base64url; store SHA-256 verifier + `key_id`; raw token returned once | P-03 |
| Session lifetime | Absolute 8 h; idle 30 min; rotation on login/password change; logout revokes current session; admin can revoke all | P-04 |
| Session transport | Bearer token in `Authorization` header; no cookie; CORS disabled unless owner config allows an explicit origin allowlist; browser uses relative `/v1` URLs | P-05 |
| Login rate limit | 5 fails per 15 min per HMAC(email)+IP bucket; generic `401 invalid_credentials` with uniform delay/`Retry-After` for all failures; 15 min auto-unlock | P-06 |
| Invitation token | 32-byte CSPRNG (256 bits), base64url; store SHA-256 verifier with pepper; plaintext shown once | P-07 |
| Invitation TTL | 24 h default; owner may set 1–72 h at issue; revocation immediate | P-08 |
| Identifier format | Demo-only `^DEMO-ID-[0-9]{3,6}$`; uppercase ASCII, trim; reject 14-digit production-format values | P-09 |
| Identifier HMAC | `HMAC-SHA256(key, "invitation-subject-match/v1" || 0x00 || normalized_identifier)`, lowercase hex; `identifier_key_id` stored; single stable demo key `demo-v1`; blind `canonical_subject_id` UNIQUE across key versions | P-10 |
| Key rotation | **Disabled for populated databases**; refusal is `409 identity_key_replacement_unsupported`; no `demo-v2` path, no cross-key matching or authenticated linking; a populated-DB migration requires a new reviewed protocol | P-11 |
| Assignment selection | Every doctor-scoped patient operation includes `assignment_id`; patient-facing doctor selection uses one active assignment id from `GET /v1/me/assignments`; absent selection → `409 assignment_selection_required` | P-12 |
| Multiple assignments | Multiple active assignments allowed; UNIQUE(doctor_id, patient_id) over active rows; no `patient.doctor_id` anywhere | P-13 |
| Assignment revocation | Immediate loss of new access; historical records keep original `assignment_id`; revoked doctor cannot read them; new doctor cannot read records from other assignments | P-14 |
| Reassessment | New assessment row only, with `reassessment_of` and reason; never mutate prior snapshot/result | P-15 |
| Inference lease | 5 min lease; generation counter; fence token; conditional completion; recovery after expiry creates new generation | P-16 |
| Idempotency TTL | 24 h for workflow writes; actor/operation/target-bound replay identity; keyed secret fingerprints; redacted replay vs `409 secret_not_redisclosable`; no secret redistribution | P-17 |
| Scope of demo key/pepper | Operator environment only; no `.env` in Git; stable `demo-v1`; key replacement refused on populated DB | P-18 |
| Canonical OpenAPI | Deterministic composition into one served spec; legacy file unchanged | P-19 |
| Error semantics | Wrong owner 404, wrong role 403, generic 401 for auth/invite failures | P-20 |
| Canonical login email | `email_norm` NOT NULL UNIQUE; trim ASCII whitespace, NFKC, reject non-ASCII, lowercase, max 254 bytes; synthetic UUID account ids | P-21 |
| Account status | ACTIVE↔SUSPENDED, ACTIVE/SUSPENDED→DISABLED terminal; all sessions revoked on change; no hard delete | P-22 |
| Temp password | Doctor first login may only use GET /auth/me, POST /me/password, POST /auth/logout until changed | P-23 |
| Rate limits | Durable per-account + per-source + per-invitation buckets; composite email+IP alone insufficient | P-24 |
| Migration placement | C1 creates identity/auth, visit/invitation, assignment/consent, redemption, durable idempotency and workflow audit; health profile/assessment in C2; reviews/notifications in C3 | P-25 |
| AI gates | A1 development, A2 independent verification, A3 owner activation, B display are separate and all PENDING | P-26 |
| Stage publication | One Arena branch + stage Draft PR to prototype; exact-head dispatch of four CI workflows; owner Windows evidence before acceptance | P-27 |

## 4. Stage plan and gates

| Stage | Complete scope | Dependencies | Required approvals | Acceptance evidence | Blocking conditions |
|---|---|---|---|---|---|
| **C0** (this package) | Final architecture, threat model, ERD/data dictionary, canonical contract design, API matrix, AI readiness/candidate B with four gates, state machines, decision register, test strategy, stage plan, Windows candidate runbook, R-01…R-08 and C0-F01…F10 resolutions | Verified remote checkpoint; governing docs; preflight + reviewer verdict | Final independent review + owner Windows verification + owner acceptance before C1 | Exact PR #143 head, docs diff, exact-head dispatch results, owner Windows output, decision confirmations | Unresolved owner decision that changes architecture; missing exact-head CI or Windows evidence |
| **C1** | Accounts/admin bootstrap with `email_norm`, sessions, RBAC/object-level via assignments, verified visits with stable identity key, invitation issue/revoke/atomic redeem, existing-account linking, assignment lifecycle/consent, durable idempotency, workflow audit, C1 migrations in correct order, contracts and security/concurrency tests | C0 accepted; contract change-set approved; P-01…P-27 confirmed | Owner acceptance + Windows evidence | Exact-head CI for backend/contracts; migration evidence; negative/replay/concurrency/rate-limit summaries; Windows output | Any raw identifier/code/token leak, RBAC/IDOR defect, non-atomic redemption, destructive migration, legacy regression |
| **C2** | Health profile/consent, source validation, immutable snapshot, inference attempt/result/generation/fencing, recovery, role projection, authorized trained adapter after A1+A2+A3; fail-closed otherwise | C1 accepted; A1/A2/A3 for inference; synthetic-demo provenance approved; artifact/dependency decision | A3 (or documented C2-safe scope), B only for display; owner acceptance | Same-model explanation evidence, tamper/failure tests, state/restart tests, Windows output | No A and no documented revised scope; mock substitution; patient score leak; private bundle in Arena/CI |
| **C3** | Assigned doctor list/queue, append-only review decisions, clinician-authored notes/demo prescriptions, atomic messages/notifications, read status, authorized history | C2 accepted or explicit owner scope revision | Owner acceptance + Windows evidence | Cross-role negative tests, restart, atomicity, exact-head CI, Windows output | Object-level access defect, AI-authored prescription, partial follow-up writes |
| **C4** | Full synthetic E2E, security/regression/migration/restart suites, exact-head hosted CI, Windows verification, setup instructions, integration matrix, handoff/blocker ledgers | C1–C3 accepted; exact SHA freeze; A/B decisions recorded | Final owner review; separate approval for new repo/merge | Complete evidence ledger; honest BLOCKED/DEFERRED list; Windows output | ALL_GREEN claim while research suite red; missing owner evidence; unapproved repository creation |

**Planning dates (targets only):** C0 2026-11-25; C1 11-26/27; C2 11-28/29; C3 11-30/12-01; C4 12-02; handoff 12-03. Preparation of Decision A/B material may proceed while C1 is implemented, but C2 implementation must not start until gates are satisfied.

## 5. Reviewer correction resolution summary (R-01…R-08)

Full detail is in `TERM1_STAGE_PROGRESS.md` §4/§6 and the architecture document. Summary:

| ID | Resolution in C0 package |
|---|---|
| R-01 | `patient.doctor_id` removed; authorization via active `doctor_patient_assignment` and assessment's bound `assignment_id`; explicit patient assignment selection and historical-access freeze in architecture §5/§7. |
| R-02 | Visit attestation binds intended identifier HMAC before invitation; strict fictitious-ID allowlist, unambiguous HMAC encoding, purpose/key separation, single demo key with documented rotation, server vs stated timestamps, controlled attestation codes. |
| R-03 | Invitation revoke, existing-account link, assignment revoke, account suspend/activate, password change added to API inventory; generic 401 lockout semantics; bearer transport; index corrections; admin bootstrap without HTTP endpoint. |
| R-04 | Redacted idempotency records; no raw codes/passwords/session tokens; one-time secret non-redisclosure; durable failure-attempt counting outside rolled-back transactions. |
| R-05 | One authoritative `inference_result`; generation/lease/fence CAS completion; stale-result suppression with retained history; review conflict and follow-up eligibility rules; test-only doubles explicitly forbidden in production. |
| R-06 | One canonical served OpenAPI composition; complete method/path allowlist; original legacy file and behavior tests preserved; headers modeled as headers. |
| R-07 | PS5.1 explicit exit-code checks; safe reuse of verified clone; fast-forward-only updates; unique disposable DBs; exact pytest paths; full-suite research dependencies; no cleanup/reset/invented endpoints. |
| R-08 | Exact candidate B design, authorization proposals A/B, deterministic rebuild/trust/digest/rights requirements, no clinical claim, no private bundle execution or score display before approval. |

### 5.1 Final reviewer corrections C0-F01…F10

| ID | Where resolved |
|---|---|
| C0-F01 | Architecture §3.1/§3.2/§5; API matrix §2.1/§3; decision register P-21…P-23 |
| C0-F02 | Architecture §3.4/§3.5/§5; API E1/E2; decision register P-10/P-11 |
| C0-F03 | Architecture §6.1; API §3; decision register P-17/P-24 |
| C0-F04 | Architecture §9; decision register P-25 |
| C0-F05 | Architecture §7.3/§7.4 |
| C0-F06 | API matrix §2/§2.1/§3; architecture §8 |
| C0-F07 | AI readiness §3; decision register A/A1/A2/A3; P-26 |
| C0-F08 | This document §1.2/§2; `TERM1_STAGE_PROGRESS.md` §1/§6; blocker B-06; P-27 |
| C0-F09 | `TERM1_WINDOWS_VERIFICATION_RUNBOOK.md` complete C0 candidate block |
| C0-F10 | `TERM1_TEST_EVIDENCE.md` §5; completion report carries exact run URLs |

## 6. CI baseline (`HOSTED_CI_VERIFIED`)

Refreshed at C0 start; no newer run for prototype HEAD:

- [backend SUCCESS](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/45650285373)
- [contract SUCCESS](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/45650285403)
- [audit SUCCESS](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/45650285433)
- [synthetic runner FAILURE](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/45650285465)
- [Python 3.11 job](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/45650285465/job/139332628376): 1808 passed, 2 failed, 10 errors, 2 skipped (prior reviewer log verification; `AGENT_REPORTED` for Arena).
- [Python 3.12 job](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/45650285465/job/139332628534): 1820 passed, 2 skipped, then 396 passed benchmark step; structural diagnostic success.

The 3.11 failure predates prototype implementation (Issue #132, still OPEN). It is not an automatic blocker to independent safe C1 engineering, but it remains in the blocker register and no `ALL_GREEN` claim may be made. No Golden fixture, tolerance, research test, workflow, PR #141, or Issue #132 change is authorized.

**Stage-PR CI note:** the four existing validation workflows trigger on `pull_request` to main only; PR #143 targeting the prototype branch reports zero checks. Four `workflow_dispatch` attempts on the published session branch were rejected by the available GitHub integration token with `HTTP 403: Resource not accessible by integration`; no runs were created. No further dispatch attempts are made with the same restricted token. The owner must dispatch `backend-ci.yml`, `contracts-ci.yml`, `audit-ci.yml` and `experiment-runner-ci.yml` on the final published SHA using their own authorized account. Zero checks is not success.

## 7. Status declarations

```
C0_STATUS=CORRECTED_PENDING_FINAL_REVIEW_AND_OWNER_WINDOWS_VERIFICATION
C1_STATUS=NOT_STARTED
C2_STATUS=NOT_STARTED
C3_STATUS=NOT_STARTED
C4_STATUS=NOT_STARTED
AI_SERVING_AUTHORIZATION=PENDING
PATIENT_SCORE_DISPLAY_AUTHORIZATION=PENDING
WINDOWS_VERIFICATION_STATUS=NOT_RUN
HOSTED_CI=OWNER_DISPATCH_REQUIRED
```

## 8. Required owner confirmations at C0 acceptance

1. Confirm or amend every `PROPOSED_C0_DEFAULT` in §3.2 (P-01…P-27), especially P-02, P-11, P-17, P-21…P-27.
2. Confirm PR #143 publication, the reconstructed-commit disclosure and the stage-PR policy in §1.2/§2; owner merge only after acceptance.
3. Confirm multiple active assignments with `assignment_id` selection and multi-doctor consent/revocation behavior.
4. Confirm canonical email normalization, frozen password handling, single stable identity key with replacement refusal, and actor/operation/target-bound replay identity.
5. Confirm the canonical OpenAPI composition and complete GET/PATCH-separated allowlist.
6. Keep AI gates A1/A2/A3 and B PENDING; ratify tokens only with the required evidence.
7. Acknowledge the inherited research CI failure, exact-head dispatch results, missing Windows evidence and 2026-12-03 risk.

## 9. Completion report cross-reference

The stage completion report returned with this package contains exact SHAs, changed-file list, diff/stat, R-resolution matrix, final ERD/API inventory, pending decisions, A/B proposals, CI links, Windows baseline block, unresolved blockers and C1 readiness. No stage is marked VERIFIED by this document.
