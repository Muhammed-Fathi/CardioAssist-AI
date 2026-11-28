# CardioAssist-AI Term 1 — Decision Register

**Status:** live C0 register. `OWNER_APPROVED` entries come only from the human owner's active-milestone instruction; `PROPOSED` entries require confirmation at C0 acceptance; `PENDING_AUTHORIZATION` entries are not granted by this package.

## 1. Owner-approved direction (`OWNER_APPROVED`)

| ID | Decision | Source | Scope limit |
|---|---|---|---|
| O-01 | Stage-based execution: one complete stage → one master prompt → organized commits → independent review → Windows verification → remediation → GitHub evidence → explicit owner acceptance → next stage | Owner C0 master prompt 2026-11-25; independent verdict `ACCEPT_WITH_CHANGES` | No automatic advancement; no self-approval |
| O-02 | Use existing `delivery/term1-prototype` branch and Draft PR #142 as overall delivery PR; no merge by Arena | Owner C0 master prompt | No force-push or new branch |
| O-03 | Preserve complete workflow through persistent history; provisional patient score remains an intended UX but separately gated | Owner C0 master prompt | Status-only until Decision B |
| O-04 | One patient account per identity; database support for multiple independently authorized doctor-patient assignments; no global `patient.doctor_id` | Owner C0 master prompt + reviewer R-01 | Assignment-scoped authorization |
| O-05 | Clinician attestation before invitation; identity-bound, expiring, revocable, single-use codes; synthetic-only identifiers | Owner C0 master prompt | No proof of real identity/attendance |
| O-06 | FastAPI, SQLAlchemy, SQLite, Alembic; secure auth/sessions/RBAC; durable idempotency; dedicated workflow audit; additive contracts | Owner C0 master prompt | Legacy behavior preserved |
| O-07 | Genuinely trained educational AI candidate subject to separate authorization; Flutter/React are software-team work | Owner C0 master prompt | No serving/display/training in C0 |
| O-08 | No scope reduction without explicit owner decision; 2026-12-03 is a planning target only | Owner C0 master prompt | No weakened gates |
| O-09 | Documentation-only C0 publication under verified repository governance | Owner C0 master prompt | No code/migration/contract/test/workflow change |
| O-10 | Revised publication strategy 2026-11-25: one assigned Arena branch per stage; stage Draft PR targets `delivery/term1-prototype`; each stage starts from latest accepted prototype revision; independent review, exact-head CI, owner Windows tests, corrections and explicit acceptance precede owner merge; PR #142 remains overall PR to main | Owner revised branch/publication strategy | Arena does not review, approve or merge; no new branch for this stage |

## 2. Technical defaults proposed by C0 (`PROPOSED` — confirm at acceptance)

| ID | Decision | Proposed value | Rationale / trade-off |
|---|---|---|---|
| P-01 | Password KDF | PBKDF2-HMAC-SHA256, 600k iterations, 16-byte salt, 32-byte key | Stdlib, no new pins; Argon2id alternative requires dependency approval |
| P-02 | Password policy | 12–128 UTF-8 bytes, no composition rules, **no trimming or normalization**; leading/trailing spaces significant | Prevents silent mutation of credentials |
| P-03 | Session token | 32-byte CSPRNG base64url; store SHA-256 verifier + key id | One-time disclosure, no raw token at rest |
| P-04 | Session lifetime | 8 h absolute, 30 min idle, rotation on login/password change | Prototype-grade; shorter than a day |
| P-05 | Session transport | Bearer header, no cookies, CORS off by default | Avoids cookie CSRF; browser uses relative URLs |
| P-06 | Login lockout | 5 fails/15 min, 15 min lock, generic 401 with uniform Retry-After | Limits guessing without enumeration |
| P-07 | Invitation token | 256-bit CSPRNG; verifier hash only; shown once | High entropy, no plaintext at rest |
| P-08 | Invitation TTL | 24 h default, 1–72 h configurable by doctor | Short-lived; revoke/reissue for lost code |
| P-09 | Identifier grammar | `^DEMO-ID-[0-9]{3,6}$`, uppercase ASCII, trim | Prevents real-ID entry |
| P-10 | HMAC encoding | `HMAC-SHA256(key, 'invitation-subject-match/v1' || 0x00 || normalized)`, lowercase hex; blind `canonical_subject_id` UNIQUE across key versions | Unambiguous, purpose-separated; no raw identifier |
| P-11 | Key rotation | **Disabled for populated databases**; `409 identity_key_replacement_unsupported`; one stable `demo-v1`; populated-DB protocol requires new review | Avoids silent cross-key identity merge and failed authenticated links |
| P-12 | Assignment selection | `assignment_id` required for doctor-scoped patient context; patient picks from `GET /v1/me/assignments` | Supports multiple doctors unambiguously |
| P-13 | Multiple assignments | Multiple active allowed; partial UNIQUE(doctor_id,patient_id) where active | No global ownership column |
| P-14 | Revocation history | Revoked doctor loses new and historical access; new doctor cannot read unrelated history | Prevents data leakage across assignments |
| P-15 | Reassessment | New assessment row with `reassessment_of` and reason | Immutable history |
| P-16 | Inference lease | 5 min lease, generation counter, fence token, CAS completion | Prevents stale late result |
| P-17 | Idempotency | 24 h, actor/operation/target-bound replay identity, keyed secret fingerprints, redacted replay vs `409 secret_not_redisclosable`, no secret redistribution | Safe replay |
| P-18 | Secrets | Operator env only; no `.env`/keys in Git | No committed credentials |
| P-19 | Canonical OpenAPI | Deterministic composition into one served spec; legacy file unchanged | One public truth |
| P-20 | Error semantics | Wrong owner 404, wrong role 403, generic 401 for auth/invite failures | Non-enumerating |
| P-21 | Login email | `email_norm` NOT NULL UNIQUE; trim ASCII whitespace, NFKC, reject non-ASCII, lowercase, max 254 bytes; synthetic UUID account ids | Consistent API/ERD; no enumeration |
| P-22 | Account status | ACTIVE↔SUSPENDED, ACTIVE/SUSPENDED→DISABLED terminal; revoke sessions; no hard delete | Contained lifecycle |
| P-23 | Temporary password | Only GET /auth/me, POST /me/password, POST /auth/logout until changed; others `403 password_change_required` | Forces credential change |
| P-24 | Rate limits | Durable per-account, per-source and per-invitation buckets; not email+IP alone | Prevents guessing and invitation brute force |
| P-25 | Migration placement | C1 identity/auth, visit/invitation, assignment/consent, redemption, durable idempotency, workflow audit; health profile/assessment C2; review/notification C3 | Dependencies exist when first needed |
| P-26 | AI gates | A1 development, A2 independent verification, A3 owner activation, B display separate and PENDING | No premature serving authorization |
| P-27 | Stage publication | Assigned Arena branch, stage Draft PR to prototype, exact-head dispatch of four CI workflows, owner Windows evidence before acceptance | Verifiable stage PR evidence |

## 3. Pending authorizations (`PENDING_AUTHORIZATION`)

| ID | Decision | Required owner act | Current state |
|---|---|---|---|
| A1 | Candidate B development/artifact generation only | Development token in `TERM1_AI_READINESS_MATRIX.md` §3.1 | PENDING; no execution in C0 |
| A2 | Independent artifact verification | Reviewer confirmation token after exact implementation/digest/protocol verification | PENDING |
| A3 | Controlled local-demo adapter activation | Activation token after A1+A2, registry/digest/source binding | PENDING; adapter disabled |
| A (umbrella) | Full Decision A | A1 + A2 + A3 all satisfied | PENDING; no serving authorization granted |
| B | Synthetic patient score display | Exact ratification text in `TERM1_AI_READINESS_MATRIX.md` §3.2 with reviewed wording/redaction | PENDING; patient sees status only |
| AC-C0 | C0 acceptance | Independent reviewer verdict on docs + owner acceptance of technical defaults and publication deviation | PENDING |
| AC-C1…C4 | Stage acceptances | Evidence, Windows verification, owner acceptance per stage | NOT_STARTED |
| ART | Artifact trust/distribution and backend dependency pins | Owner decision on deterministic rebuild vs curated bundle; new pins if A granted | PENDING |
| HR | Software-team repository creation | Final review, curated files, attribution, redistribution rights | PENDING; do not create |
| C0-F01…F10 | Focused final corrections | Final independent review of corrected docs and owner Windows verification | PENDING; C0 not accepted |

## 4. Explicit non-decisions

This register does not grant: model serving, patient score display, real-data work, clinical claims, research gate changes, workflow/test/fixture changes, merge, frontend implementation, or C1 start.

## 5. Historical authorization statement (superseded by O-10)

The earlier draft statement `AUTHORIZE-TERM1-C0-DOCS` referred to direct documentation changes on `delivery/term1-prototype` in PR #142. It is retained for audit history but is superseded by the owner's revised stage-PR strategy (O-10) and PR #143. Arena has not posted, and must not post, any owner statement on the owner's behalf.

---

# Appendix A — C1 acceptance and C1-closure decisions (appended 2026-11-27)

Append-only. §1–§5 keep their original text and their `PENDING` states as written at C0.
Where this appendix and an earlier section disagree about C1 or C2, this appendix is
current; every earlier `PENDING_AUTHORIZATION` entry that is *not* named below is
**unchanged**.

## A.1 New recorded decisions

| ID | Decision | Status | Source / evidence | Scope limit |
|---|---|---|---|---|
| **AC-C1** | Accept the bounded C1 prototype baseline at `524d57cb17c995ea5ab299a6479f66b406751e07`, base `310534e1e334ba3be4f308f5a66d88c22b5842e0`, and authorize its integration into `delivery/term1-prototype` only | **OWNER_RATIFIED** (2026-11-27T01:53:34Z) | `ACCEPT-TERM1-C1-BOUNDED-PROTOTYPE-BASELINE`, PR #144 [comment 7207660039](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/144#issuecomment-7207660039); merged as `2a8a209fba20d0c7c43c255ede4545bcaa5f34b7` | Prototype delivery branch only. Explicitly **not**: real clinical data, model activation, patient-facing AI results, research-gate closure, or merging PR #142 into `main` |
| **RB-C1** | In-place downgrade permitted **only** on disposable databases without C1 state; populated operational databases require verified backup restoration with explicit recovery-point acceptance | **OWNER_RATIFIED** (same comment) | `TERM1_C1_ROLLBACK_POLICY_PROPOSAL.md` + its Addendum; owner Windows retest transcript | Operational restoration still requires recovery-point acceptance and preservation of the current database. Isolated restoration test ≠ live-recovery certification. No automatic production rollback authorized |
| **CL-C1** | The outstanding HTTP contract coverage obligations are a **prerequisite** to dependent C2 implementation | **OWNER_MANDATED** | Same acceptance text; reviewer recommendation [7207660039](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/144#issuecomment-7207660039) | Closure evidence: `TERM1_C1_HTTP_CLOSURE_EVIDENCE.md`; acceptance of it remains PENDING independent review |
| **C2S** | C2 runtime work is not started and is blocked on owner decisions OQ-1…OQ-10 | **NOT_STARTED / NOT_AUTHORIZED** | `TERM1_C2_IMPLEMENTATION_DEPENDENCY_MAP.md` §6 | Documentation readiness only. No code, migration, route, dependency, model or artifact |

## A.2 AC-C1 clauses as written by the owner (not paraphrased into a stronger grant)

The acceptance text conditions were, verbatim in substance:

1. exact-head hosted CI 4/4 workflows and 8/8 jobs successful;
2. native Windows backend and contracts 1159 passed;
3. native Windows migration and reviewer regressions 27 passed;
4. legacy data preservation, application restart and isolated backup restoration verified;
5. controlled populated-database downgrade refusal verified without schema or data loss;
6. the safe rollback policy approved as in RB-C1;
7. integration authorized into `delivery/term1-prototype` **only**;
8. outstanding HTTP contract coverage obligations to be completed before dependent C2;
9. historical Windows research failures remain unresolved in the separate RH-04 track;
10. no authorization of real clinical data, model activation, patient-facing AI results,
    research gate closure, or merging PR #142 into `main`;
11. PR #142 to remain open and draft;
12. C2 continuation subject to post-merge verification and its applicable authorization gates.

Clause 8 is the reason this branch exists. Clause 10 is the reason it does none of those
things.

## A.3 Unchanged pending authorizations (re-stated, not relaxed)

| ID | Decision | State |
|---|---|---|
| A1 | Candidate B synthetic development only | **PENDING** — no generation, training or execution |
| A2 | Independent artifact/model verification | **PENDING** |
| A3 | Controlled local-demo activation | **PENDING** — adapter disabled, registry admits `MOCK_SYNTHETIC` only |
| A (umbrella) | Full Decision A = A1 + A2 + A3 | **PENDING** |
| B | Patient-facing synthetic score display | **PENDING** — patient sees status only |
| ART | Artifact trust/distribution and numerical dependency pins (OQ-6) | **PENDING** |
| HR | Software-team repository creation | **PENDING** — do not create |
| OQ-1…OQ-10 | C2 scope, snapshot form, lease parameters, panel reuse, publication semantics, dependency route, S1 replay target, migration grouping, display wording, CI evidence route | **PENDING** — see the C2 map §6 |

Technical defaults P-01…P-27 remain `PROPOSED`; P-16 and P-25 are specifically implicated
by C2 (OQ-3 and OQ-8) and require explicit confirmation there.

## A.4 Explicit non-decisions

This appendix grants no model serving, no patient score display, no real-data work, no
clinical or publication claim, no research-gate change, no C2 implementation, no C3/C4
start, no workflow/test/fixture/research change, no merge, and no acceptance of the closure
work itself. Arena has not posted and must not post any owner statement.

## Dated owner-direction record — 2026-11-27 (proposed exact-head ratification)

| ID | Direction | Status / boundary |
|---|---|---|
| O-11 | Reuse inherited main AI code and prefer existing real-data-trained Cleveland artifact rather than new synthetic-trained Candidate B; no duplicate training or rewrite without evidence and explicit decision. | OWNER_DIRECTION_RECORDED_IN_CHAT; exact plan PR ratification pending, artifact not independently inspected, A gates pending. |
| O-12 | Preserve existing journey and add bounded fabricated report upload/view, fixed-template local OCR autofill, patient edit/confirmation, manual input and source traceability; no general real clinical OCR/PHI. | OWNER_DIRECTION_RECORDED_IN_CHAT; reviewed document contracts and narrow demo provenance exception required; unverified OCR never enters current Track A. |
| O-13 | Preserve provisional research result before review and derived Reviewed label with actual doctor decision; doctor response/inbox/history. | OWNER_DIRECTION_RECORDED_IN_CHAT; B pending, no personal risk percentage, no implicit acceptance or clinical use. |
| O-14 | Preserve accepted C0/C1 runtime, migration and contract behavior; reuse existing implementations and continue logical stage PR workflow, target 2026-12-03. | OWNER_DIRECTION_RECORDED_IN_CHAT; exact diff review, CI, native Windows and owner acceptance required. |

Governing proposal: [delivery plan amendment](TERM1_DELIVERY_PLAN_AMENDMENT_REAL_AI_OCR_20261127.md). Chat direction authorizes documentation of intended scope, not a GitHub owner acceptance impersonation. Previous Candidate B tokens must not be used for Candidate A. A1/A2/A3/B remain PENDING; C2-safe-scope decision, OQ resolutions, C1 projection reconciliation and B20 acknowledgement remain separate. No operational or research authorization, no clinical deployment, no waiver of RH-04 findings. Historical records above remain unchanged.


## Dated C2 owner decision and implementation grant — 2026-11-28

Append-only reviewer record of the actual owner statements; not a new authorization. Governing sources: merged PR #146 delivery amendment; merged PR #147 Revision 3 design; owner design acceptance [#7232282565](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/147#issuecomment-7232282565), mandatory reviewer clarifications [#7229164710](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/147#issuecomment-7229164710) and [#7229713779](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/147#issuecomment-7229713779), post-merge verification [#7232298149](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/147#issuecomment-7232298149), explicit owner implementation grant [#7232372420](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/147#issuecomment-7232372420) by Muhammed-Fathi at 2026-11-28T02:27:15Z.

| Item | Current disposition (supersedes historical pending status only within named scope) |
|---|---|
| O-11–O-14 | Accepted intended delivery direction via PR #146; preserve C0/C1, Candidate A reuse subject to separate gates, bounded fabricated reports/OCR, doctor review and response; target 2026-12-03 not guaranteed. |
| B-20 | Owner acknowledged unrecoverable original five C0 SHAs and reconstructed provenance in #7232282565; preserve distinction, never reconstruct original identity claims. |
| OQ-1–OQ-10 / OQ-H1A | Design decisions accepted subject to all five mandatory reviewer clarifications in #7229164710 and evidence #7229713779. H1a own stored profile self-read after withdrawal; write/submit active consent, S1 exact assignment. |
| P-16 / P-25 | Accepted defaults binding: 300-second lease, generation/fence/CAS; additive C2 07/08, C3 09. No old migration edits. |
| C2_SAFE_SCOPE | AUTHORIZED FOR IMPLEMENTATION ONLY at exact merged baseline `5c96a2b9d5438b6600cf5eebebb70294fdeeadad`, grant #7232372420. Core migration 07/H1a/H1b/S1–S3 and bounded DOC1–DOC7/migration 08; no result rows, private artifact access, inference adapter dispatch or mock fallback; manual assessments fail closed INFERENCE_UNAVAILABLE; OCR drafts/confirmation only. |
| A1 / A2 / A3 / B / RD-09-TERM1-EDU-DEMO-V1 / EXC-TERM1-OCR-DEMO-V1 | PENDING. Historical Candidate B tokens must not be reused. No training, artifact admission/access, real inference, OCR-derived inference or patient score display. |
| C2 acceptance / C3 / C4 / main merge / research closure | NOT AUTHORIZED. One logical C2 stage Draft PR; exact-head review/CI/native Windows and explicit owner acceptance required. |
| Research blockers | RH-04 golden replay, forced dispatch and Windows research portability remain unresolved; no waiver, tolerance change, rerun-to-green or research modification. Candidate design CI 3/4 workflows, 7/8 jobs; prior native Windows evidence carried forward for unchanged implementation only, not for new C2 code. |

Implementation coordination: use isolated branches from this authorized baseline plus this append-only record. Core integrator owns migration 07, assessment APIs/persistence, common app registration, error/OpenAPI composition, shared contract reconciliation and final integration. Document/OCR contributor owns migration 08 and dedicated document/OCR modules, fixture generation, DOC schemas/routes and tests; no concurrent changes to shared integration files. Freeze one exact shared schema/enum/attachment identity and handoff interface before dependent code. Explicitly reconcile all reviewer clarifications in implementation evidence, not by merely repeating this record. Track-specific commits are integrated into one C2 Draft PR targeting delivery/term1-prototype after review; no independent merge. Post-merge base CI at first grant check: backend, contracts, audit SUCCESS; synthetic run 46097533597 IN_PROGRESS. This is not an all-green or runtime acceptance claim.
