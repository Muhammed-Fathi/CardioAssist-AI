# CardioAssist-AI Term 1 — Decision Register

**Status:** live C0 register. `OWNER_APPROVED` entries come only from the human owner's active-milestone instruction; `PROPOSED` entries require confirmation at C0 acceptance; `PENDING_AUTHORIZATION` entries are not granted by this package.

## 1. Owner-approved direction (`OWNER_APPROVED`)

| ID | Decision | Source | Scope limit |
|---|---|---|---|
| O-01 | Stage-based execution: one complete stage → one master prompt → organized commits → independent review → Windows verification → remediation → GitHub evidence → explicit owner acceptance → next stage | Owner C0 master prompt 2026-11-25; independent verdict `ACCEPT_WITH_CHANGES` | No automatic advancement; no self-approval |
| O-02 | Use existing `delivery/term1-prototype` branch and Draft PR #142; no per-stage PRs by default; no merge | Owner C0 master prompt | No force-push or new branch |
| O-03 | Preserve complete workflow through persistent history; provisional patient score remains an intended UX but separately gated | Owner C0 master prompt | Status-only until Decision B |
| O-04 | One patient account per identity; database support for multiple independently authorized doctor-patient assignments; no global `patient.doctor_id` | Owner C0 master prompt + reviewer R-01 | Assignment-scoped authorization |
| O-05 | Clinician attestation before invitation; identity-bound, expiring, revocable, single-use codes; synthetic-only identifiers | Owner C0 master prompt | No proof of real identity/attendance |
| O-06 | FastAPI, SQLAlchemy, SQLite, Alembic; secure auth/sessions/RBAC; durable idempotency; dedicated workflow audit; additive contracts | Owner C0 master prompt | Legacy behavior preserved |
| O-07 | Genuinely trained educational AI candidate subject to separate authorization; Flutter/React are software-team work | Owner C0 master prompt | No serving/display/training in C0 |
| O-08 | No scope reduction without explicit owner decision; 2026-12-03 is a planning target only | Owner C0 master prompt | No weakened gates |
| O-09 | Documentation-only C0 publication under verified repository governance | Owner C0 master prompt | No code/migration/contract/test/workflow change |

## 2. Technical defaults proposed by C0 (`PROPOSED` — confirm at acceptance)

| ID | Decision | Proposed value | Rationale / trade-off |
|---|---|---|---|
| P-01 | Password KDF | PBKDF2-HMAC-SHA256, 600k iterations, 16-byte salt, 32-byte key | Stdlib, no new pins; Argon2id alternative requires dependency approval |
| P-02 | Password policy | 12–128 UTF-8 bytes, no composition rules | Usable and testable; no unsafe truncation |
| P-03 | Session token | 32-byte CSPRNG base64url; store SHA-256 verifier + key id | One-time disclosure, no raw token at rest |
| P-04 | Session lifetime | 8 h absolute, 30 min idle, rotation on login/password change | Prototype-grade; shorter than a day |
| P-05 | Session transport | Bearer header, no cookies, CORS off by default | Avoids cookie CSRF; browser uses relative URLs |
| P-06 | Login lockout | 5 fails/15 min, 15 min lock, generic 401 with uniform Retry-After | Limits guessing without enumeration |
| P-07 | Invitation token | 256-bit CSPRNG; verifier hash only; shown once | High entropy, no plaintext at rest |
| P-08 | Invitation TTL | 24 h default, 1–72 h configurable by doctor | Short-lived; revoke/reissue for lost code |
| P-09 | Identifier grammar | `^DEMO-ID-[0-9]{3,6}$`, uppercase ASCII, trim | Prevents real-ID entry |
| P-10 | HMAC encoding | `HMAC-SHA256(key, 'invitation-subject-match/v1' || 0x00 || normalized)`, lowercase hex | Unambiguous, purpose-separated |
| P-11 | Key rotation | New key id for new invitations; old key verifies existing only; re-attestation for existing subjects | Avoids silent cross-key identity merge |
| P-12 | Assignment selection | `assignment_id` required for doctor-scoped patient context; patient picks from `GET /v1/me/assignments` | Supports multiple doctors unambiguously |
| P-13 | Multiple assignments | Multiple active allowed; partial UNIQUE(doctor_id,patient_id) where active | No global ownership column |
| P-14 | Revocation history | Revoked doctor loses new and historical access; new doctor cannot read unrelated history | Prevents data leakage across assignments |
| P-15 | Reassessment | New assessment row with `reassessment_of` and reason | Immutable history |
| P-16 | Inference lease | 5 min lease, generation counter, fence token, CAS completion | Prevents stale late result |
| P-17 | Idempotency | 24 h, hash-only keys, redacted replay, no secret redistribution | Safe replay |
| P-18 | Secrets | Operator env only; no `.env`/keys in Git | No committed credentials |
| P-19 | Canonical OpenAPI | Deterministic composition into one served spec; legacy file unchanged | One public truth |
| P-20 | Error semantics | Wrong owner 404, wrong role 403, generic 401 for auth/invite failures | Non-enumerating |

## 3. Pending authorizations (`PENDING_AUTHORIZATION`)

| ID | Decision | Required owner act | Current state |
|---|---|---|---|
| A | Candidate B local-demo inference adapter | Exact ratification text in `TERM1_AI_READINESS_MATRIX.md` §3.1 after independent implementation review; registry/digest/dependency binding | PENDING; adapter disabled |
| B | Synthetic patient score display | Exact ratification text in `TERM1_AI_READINESS_MATRIX.md` §3.2 with reviewed wording/redaction | PENDING; patient sees status only |
| AC-C0 | C0 acceptance | Independent reviewer verdict on docs + owner acceptance of technical defaults and publication deviation | PENDING |
| AC-C1…C4 | Stage acceptances | Evidence, Windows verification, owner acceptance per stage | NOT_STARTED |
| ART | Artifact trust/distribution and backend dependency pins | Owner decision on deterministic rebuild vs curated bundle; new pins if A granted | PENDING |
| HR | Software-team repository creation | Final review, curated files, attribution, redistribution rights | PENDING; do not create |

## 4. Explicit non-decisions

This register does not grant: model serving, patient score display, real-data work, clinical claims, research gate changes, workflow/test/fixture changes, merge, frontend implementation, or C1 start.

## 5. Exact owner statement if a posted PR authorization is required

> `AUTHORIZE-TERM1-C0-DOCS` — I authorize documentation-only C0 design changes on branch `delivery/term1-prototype` in Draft PR #142. This does not authorize C1 implementation, model serving, patient score display, stage acceptance, or merge.

Arena has not posted, and must not post, this statement on the owner's behalf.
