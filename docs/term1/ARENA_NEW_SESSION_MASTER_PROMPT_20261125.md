# ARENA — NEW SESSION MASTER EXECUTION PROMPT | TERM 1

Repository: https://github.com/Muhammed-Fathi/CardioAssist-AI
Target branch: delivery/term1-prototype
Starting main baseline: c6a6bdee46a552a2b0d705a723c862ff8a95be4d
Mandatory plan: docs/term1/TERM1_INTEGRATED_PROTOTYPE_MASTER_PLAN_20261125.md
Date: 2026-11-25. Handoff target: 2026-12-03 (NOT guaranteed).

## Your mission
Build, in **ONE CONTINUOUS IMPLEMENTATION SPRINT**, a safely bounded, working, synthetic-only educational CardioAssist-AI prototype with real FastAPI, real SQLite/SQLAlchemy/Alembic persistence, secure demo accounts/role enforcement, clinician-verified encounter and a **national-ID-bound access code**, actual specifically authorized trained-model inference and same-model explanation (NOT mocked scores), clinician review, clinician-authored educational prescription/follow-up, durable in-app notifications, patient inbox and history.

The product journey, implementation architecture, security model, data model, endpoint proposals, exact tests and owner gates in the MASTER PLAN ARE AUTHORITATIVE FOR THIS WORKING PROPOSAL, subject to AGENTS.md and previously controlling research governance. Read the full plan first, then inspect the entire relevant repo (not just selective snippets). Ask the owner ONLY for a genuinely needed explicit permission that cannot be inferred; continue all other safe work in parallel.

## Important start-of-session rules
1. Verify remote branch SHA and compare to main. Checkout **delivery/term1-prototype** and do not change main, PR #141, full research track, or existing workflow files. Preserve docs and history; no force-push, automatic merge, or self-ratification. Check if a draft PR already exists and update it; do not create a duplicate.
2. Read complete AGENTS.md, docs/DECISIONS.md, 01/02/04 blueprints, RH06 RD-01…10, backend/README.md, existing /v1 OpenAPI, SQLAlchemy models, Alembic migrations, all current backend/contracts tests, existing AI research facades/registries and model scope gates.
3. Inventory IMPLEMENTED vs PROPOSED vs BLOCKED by actual code and tests. Record file paths and exact source SHA; do not silently assume research artifacts are permitted to run in HTTP.
4. Do **one sprint**, **one delivery draft PR**, and **incremental logical commits/checkpoints** rather than waiting for PR approval after every small module. Never skip validation checkpoints: C0 review, C1 auth/visit/invitation, C2 assessment/AI, C3 doctor/inbox, C4 E2E/Windows handoff. Run and record tests at each checkpoint before moving on. Keep going even when a non-blocking subfeature is deferred.
5. Propose owner decision/ADR for three independently gated areas: (a) new prototype app scope; (b) trained-model local serving permission; (c) patient-visible preliminary research score. DO NOT represent them as already ratified, grant yourself access, or route a real-bundle into HTTP without actual authorization.

## P0 feature work
A. Secure local-only admin account provisioning, physician invite/registration, demo patient registration; password hashing, authorization (admin/doctor/patient), non-leaky error handling, tokens/session expiry and invalidation, rate limits and audit.
B. Verified encounter first. Doctor records a demo verified_visit attestation. Only then issues crypto-random 128-bit+ one-time Access Code tied to own doctor ID, visit and patient national-ID match. Never store raw ID: use secret-keyed HMAC comparison in isolated demo and use **fabricated DEMO-ID-style identifiers, NOT real Egyptian IDs or PHI**. Code verifier hashed, TTL, revoke, one-use atomic transaction, concurrency tests, generic error responses, no raw ID in logs, URLs, audits, fixtures or notifications. Code + ID is not independent proof of visit; doctor attestation is the explicit prerequisite.
C. Versioned synthetic-only health input and assessment with immutable input snapshot, server-side schema and source checks, idempotency and persistence. Cleveland five-field route candidate: age/sex/cp/trestbps/restecg; do not invent a patient-probability model, blend sources, let OCR or wearables enter CAD inference.
D. **ACTUAL TRAINED MODEL:** investigate and select admissible existing artifact/runner. Distinguish trained-on-synthetic vs trained-on-real-data, and whether local synthetic-only execution is authorized. Preserve RD-09, Gate PT and all research admission restrictions. Implement a separately reviewed adapter whose safety-gated path remains disabled until approved. Test that no unauthorized flag, header or env var can bypass permission. A real trained synthetic inference demo may be enabled only with the corresponding owner decision; the accepted real Cleveland bundle must NEVER be loaded in cloud Arena or used in HTTP without distinct authorization. Record actual score/explanation source, hashes and versions. No fake SHAP/LIME. No fallback to MOCK_SYNTHETIC when inference fails. Separate statuses OK/ABSTAIN/UNAVAILABLE/ERROR.
E. Product journey: patient submits synthetic demo input → authorized model executes → immutable result stored with PENDING_REVIEW. Patient score hidden by default unless ratified explicit educational display decision; physician can inspect research evidence. Doctor review accepted/rejected/reassessment requested with reason and actor, immutable audit, no modification of AI result.
F. Clinician-authored educational note + demo prescription as text/structured record, no AI medication recommendations. Atomic persisted follow-up message + notification/outbox, idempotency and cross-user access security. Patient inbox, read/unread, restart persistence, assessment and doctor histories. No realtime chat/push.
G. Preserve existing /v1 CAD mock endpoint, monitoring endpoint, schema fixtures and AI/Track B separation. Implement new reviewed contract-first routes for this scope; no silent existing behavior change. Provide OpenAPI/JSON schema and real HTTP smoke tests.
H. SQLite-first migrations, foreign keys, uniqueness and portable data model. No raw national identifier persisted or logged. Run SQL injection/IDOR, multi-user access, replay and concurrent-registration tests.

## Hard acceptance / severity
- No actual trained inference -> explicitly FAIL/NOT_DONE for AI integration; do not pretend mock result passes.
- No signed model serving owner approval -> keep adapter locked and show exact blocker; continue safe auth/DB/review feature work.
- No patient-score display authorization -> show only PENDING_REVIEW to patient; do not show clinician score in patient app.
- No confirmed clinician visit -> no invitation. Wrong ID, expired/consumed/revoked code -> fail closed.
- No real patient data or national IDs in prompts, tests, git, messages or CI.
- No auto-merge, research-gate closure, workflow gate relaxation, production/clinical claims, model hot swapping, secrets in git, hardcoded credentials or destructive migration.
- No accidental high/medium/low risk bands or AI drug recommendations.
- Reduce P1 scope only: PDFs, rich admin, statistics, chat attachment, smartwatch, OCR, medication reminders, push, real ID processing, forgot-password-email, appointments and account deletion all OUT.

## Artifacts required by handoff
1. Updated proposed architecture/ADR/decision requests and a feature-status matrix.
2. Actual FastAPI implementation, SQLAlchemy models, Alembic migrations; versioned OpenAPI.
3. Environment template (.env.example with NO secrets), setup and deterministic fictitious fixtures.
4. One complete synthetic E2E test: admin/doctor → visit attestation → code + matching fabricated ID → patient signup → real authorized model inference → physician review → educational prescription/message → unread/read notification → restart persistence. If AI authorization absent: an E2E that proves FAIL-CLOSED plus a **separate** offline research demo; clearly report full product E2E NOT DONE.
5. Negative tests for used/expired/wrong-ID/concurrent invitation, cross-user IDOR, invalid provenance, tampered model, unauthorized provider, stale result, invalid review transitions, duplicate follow-up, migration rollback.
6. PowerShell 5.1-compatible local Windows guide with exact installation, DB upgrade/check, config/secrets, demo seed, backend start, request sequence, full test commands, restart and safe cleanup.
7. Evidence report with exact base/head SHA, changed files, exact commands/versions, test counts, latest hosted CI statuses and job links, manual Windows status labelled NOT_RUN until human verifies; known blockers and remediation owner.

## Execute autonomously but safely
Proceed as far as possible in this one session without arbitrary waiting or repeated planning; inspect, implement, test, fix and commit progressively. Do not hide blocked gates, fake acceptance or request premature owner merge. Stop only on an authorization-sensitive or integrity-sensitive action that cannot be safely completed without the owner. Finish by pushing **only to the prototype branch** and leaving one DRAFT PR for independent review. Do not self-approve or merge.

At the end provide: exact HEAD, PR link, source files, migrations, endpoint matrix, sample synthetic test trace, commands/output, AI model identity/eligibility/serving status, patient display policy, Windows run instructions and every remaining gate. Explicitly distinguish LIVE_TRAINED, OFFLINE_TRAINED, MOCK_CONTRACT, PENDING_AUTHORIZATION, and NOT_IMPLEMENTED.
