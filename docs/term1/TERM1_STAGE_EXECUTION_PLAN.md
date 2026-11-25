# CardioAssist-AI Term 1 — Stage Execution Plan (C0 design package)

**Document status:** PROPOSED DESIGN PACKAGE — awaiting independent review and explicit owner acceptance.
**Date:** 2026-11-25 (UTC).
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

### 1.2 Session branch constraint (must be disclosed)

This Arena session is fixed to branch `arena/bdbd8a6e-cardioassist-ai` and its local HEAD is the main baseline `c6a6bde…`; the platform does not permit switching to or pushing to `delivery/term1-prototype`. The remote prototype ref was independently verified as still `bca75b4…`, four docs-only commits ahead of main, before any change was made.

Consequently, C0 documentation is committed on the **session branch only**. It is intentionally additive under `docs/term1/` and does not modify any existing tracked file, so it can be transferred by a fast-forward-free cherry-pick to the prototype branch by an actor authorized to do so:

```bash
# On an authorized clone of delivery/term1-prototype, after clean verification:
git cherry-pick <C0_COMMIT_SHA>
git push origin delivery/term1-prototype
```

No force-push, merge, new branch, or new PR is performed. This constraint is a publication-target deviation from the owner's instruction and is reported explicitly in §9 and the completion report.

## 2. Dated supersession of the one-sprint policy

The following old policy is historical and superseded for all subsequent Term 1 work:

- `docs/term1/TERM1_INTEGRATED_PROTOTYPE_MASTER_PLAN_20261125.md` §8: "One branch + one draft PR + one Arena session + incremental evidence checkpoints", C0→C4 in one continuous sprint.
- `docs/term1/ARENA_NEW_SESSION_MASTER_PROMPT_20261125.md`: "ONE CONTINUOUS IMPLEMENTATION SPRINT".

**Supersession record (2026-11-25, owner-approved):** one complete logical engineering stage → one comprehensive stage master prompt → organized implementation commits → independent engineering review → native Windows testing → remediation and retesting → GitHub evidence → explicit owner acceptance → next stage. The historical documents are preserved verbatim; this record identifies the superseded policy but does not rewrite it. No stage advances automatically.

## 3. Owner-approved direction versus technical proposals

### 3.1 Owner-approved direction (`OWNER_APPROVED_DIRECTION`)

- Stage-based execution with one comprehensive master prompt per stage; existing prototype branch and Draft PR #142; no per-stage PRs by default; no self-approval or automatic merge.
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
| Password policy | 12–128 UTF-8 bytes; no composition rules; trim only surrounding whitespace; reject NUL/control characters | P-02 |
| Session token | 32-byte CSPRNG, base64url; store SHA-256 verifier + `key_id`; raw token returned once | P-03 |
| Session lifetime | Absolute 8 h; idle 30 min; rotation on login/password change; logout revokes current session; admin can revoke all | P-04 |
| Session transport | Bearer token in `Authorization` header; no cookie; CORS disabled unless owner config allows an explicit origin allowlist; browser uses relative `/v1` URLs | P-05 |
| Login rate limit | 5 fails per 15 min per HMAC(email)+IP bucket; generic `401 invalid_credentials` with uniform delay/`Retry-After` for all failures; 15 min auto-unlock | P-06 |
| Invitation token | 32-byte CSPRNG (256 bits), base64url; store SHA-256 verifier with pepper; plaintext shown once | P-07 |
| Invitation TTL | 24 h default; owner may set 1–72 h at issue; revocation immediate | P-08 |
| Identifier format | Demo-only `^DEMO-ID-[0-9]{3,6}$`; uppercase ASCII, trim; reject 14-digit production-format values | P-09 |
| Identifier HMAC | `HMAC-SHA256(key, "invitation-subject-match/v1" || 0x00 || normalized_identifier)`, lowercase hex; key id stored; single demo key `demo-v1` for Term 1 | P-10 |
| Key rotation | New `key_id` for new invitations only; matching uses the invitation's recorded key id; no silent cross-key matching; rotation requires re-attestation for existing subjects | P-11 |
| Assignment selection | Every doctor-scoped patient operation includes `assignment_id`; patient-facing doctor selection uses one active assignment id from `GET /v1/me/assignments`; absent selection → `409 assignment_selection_required` | P-12 |
| Multiple assignments | Multiple active assignments allowed; UNIQUE(doctor_id, patient_id) over active rows; no `patient.doctor_id` anywhere | P-13 |
| Assignment revocation | Immediate loss of new access; historical records keep original `assignment_id`; revoked doctor cannot read them; new doctor cannot read records from other assignments | P-14 |
| Reassessment | New assessment row only, with `reassessment_of` and reason; never mutate prior snapshot/result | P-15 |
| Inference lease | 5 min lease; generation counter; fence token; conditional completion; recovery after expiry creates new generation | P-16 |
| Idempotency TTL | 24 h for workflow writes; hash-only keys; redacted replay responses; no secret redistribution | P-17 |
| Scope of demo key/pepper | Operator environment only; no `.env` in Git; rotation procedure documented, not implemented in C0 | P-18 |

## 4. Stage plan and gates

| Stage | Complete scope | Dependencies | Required approvals | Acceptance evidence | Blocking conditions |
|---|---|---|---|---|---|
| **C0** (this package) | Final architecture, threat model, ERD/data dictionary, canonical contract design, API matrix, AI readiness/candidate B, state machines, decision register, test strategy, stage plan, Windows baseline runbook, R-01…R-08 resolutions | Verified remote checkpoint; governing docs; preflight + reviewer verdict | Independent review + owner acceptance before C1 | Exact head, docs diff, CI baseline, owner Windows baseline output, decision confirmations | Unresolved owner decision that changes architecture; publication-target deviation not acknowledged |
| **C1** | Accounts/admin bootstrap, sessions, RBAC/object-level via assignments, verified visits with identity binding, invitation issue/revoke/atomic redeem, existing-account linking, assignment lifecycle/consent, durable idempotency, workflow audit, migration, contracts and security/concurrency tests | C0 accepted; contract change-set approved; P-01…P-14 confirmed | Owner acceptance + Windows evidence | Exact-head CI for backend/contracts; migration evidence; negative/replay/concurrency summaries; Windows output | Any raw identifier/code/token leak, RBAC/IDOR defect, non-atomic redemption, destructive migration, legacy regression |
| **C2** | Health profile/consent, source validation, immutable snapshot, inference attempt/result/generation/fencing, recovery, role projection, authorized trained adapter if Decision A; fail-closed otherwise | C1 accepted; Decision A for inference; synthetic-demo provenance approved; artifact/dependency decision | Decision A (or documented C2-safe scope), Decision B only for display; owner acceptance | Same-model explanation evidence, tamper/failure tests, state/restart tests, Windows output | No A and no documented revised scope; mock substitution; patient score leak; private bundle in Arena/CI |
| **C3** | Assigned doctor list/queue, append-only review decisions, clinician-authored notes/demo prescriptions, atomic messages/notifications, read status, authorized history | C2 accepted or explicit owner scope revision | Owner acceptance + Windows evidence | Cross-role negative tests, restart, atomicity, exact-head CI, Windows output | Object-level access defect, AI-authored prescription, partial follow-up writes |
| **C4** | Full synthetic E2E, security/regression/migration/restart suites, exact-head hosted CI, Windows verification, setup instructions, integration matrix, handoff/blocker ledgers | C1–C3 accepted; exact SHA freeze; A/B decisions recorded | Final owner review; separate approval for new repo/merge | Complete evidence ledger; honest BLOCKED/DEFERRED list; Windows output | ALL_GREEN claim while research suite red; missing owner evidence; unapproved repository creation |

**Planning dates (targets only):** C0 2026-11-25; C1 11-26/27; C2 11-28/29; C3 11-30/12-01; C4 12-02; handoff 12-03. Preparation of Decision A/B material may proceed while C1 is implemented, but C2 implementation must not start until gates are satisfied.

## 5. Reviewer correction resolution summary (R-01…R-08)

Full detail is in `TERM1_STAGE_PROGRESS.md` §4 and the architecture document. Summary:

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

## 6. CI baseline (`HOSTED_CI_VERIFIED`)

Refreshed at C0 start; no newer run for prototype HEAD:

- [backend SUCCESS](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/45650285373)
- [contract SUCCESS](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/45650285403)
- [audit SUCCESS](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/45650285433)
- [synthetic runner FAILURE](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/45650285465)
- [Python 3.11 job](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/45650285465/job/139332628376): 1808 passed, 2 failed, 10 errors, 2 skipped (prior reviewer log verification; `AGENT_REPORTED` for Arena).
- [Python 3.12 job](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/45650285465/job/139332628534): 1820 passed, 2 skipped, then 396 passed benchmark step; structural diagnostic success.

The 3.11 failure predates prototype implementation (Issue #132, still OPEN). It is not an automatic blocker to independent safe C1 engineering, but it remains in the blocker register and no `ALL_GREEN` claim may be made. No Golden fixture, tolerance, research test, workflow, PR #141, or Issue #132 change is authorized.

## 7. Status declarations

```
C0_STATUS=DESIGN_PENDING_INDEPENDENT_REVIEW_AND_OWNER_ACCEPTANCE
C1_STATUS=NOT_STARTED
C2_STATUS=NOT_STARTED
C3_STATUS=NOT_STARTED
C4_STATUS=NOT_STARTED
AI_SERVING_AUTHORIZATION=PENDING
PATIENT_SCORE_DISPLAY_AUTHORIZATION=PENDING
WINDOWS_VERIFICATION_STATUS=NOT_RUN
```

## 8. Required owner confirmations at C0 acceptance

1. Confirm or amend every `PROPOSED_C0_DEFAULT` in §3.2 and the detailed register.
2. Confirm the publication-target deviation in §1.2 and decide how the C0 commit reaches `delivery/term1-prototype`.
3. Confirm that multiple active assignments with `assignment_id` selection is the final ownership model.
4. Confirm invitation/identifier policies and the single demo key with documented rotation.
5. Confirm the canonical OpenAPI composition and complete allowlist approach.
6. Record Decisions A and B as still PENDING; approve exact ratification text when ready.
7. Acknowledge the inherited research CI failure and 2026-12-03 risk.

## 9. Completion report cross-reference

The stage completion report returned with this package contains exact SHAs, changed-file list, diff/stat, R-resolution matrix, final ERD/API inventory, pending decisions, A/B proposals, CI links, Windows baseline block, unresolved blockers and C1 readiness. No stage is marked VERIFIED by this document.
