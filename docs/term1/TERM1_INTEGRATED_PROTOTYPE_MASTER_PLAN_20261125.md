# CardioAssist-AI — Term 1 Integrated Working Prototype | Master Plan v1.0

**Date:** 2026-11-25 (Africa/Cairo)  
**Status:** DRAFT implementation plan; approval decisions below remain OPEN. Not clinical authorization.  
**Repository:** Muhammed-Fathi/CardioAssist-AI  
**Branch:** `delivery/term1-prototype`  
**Exact starting main SHA:** `c6a6bdee46a552a2b0d705a723c862ff8a95be4d`  
**Target handoff:** 2026-12-03, with an explicitly evidence-based scope and honest uncompleted items.

## 0. Mission and boundaries

Build a **working, educational, synthetic-only, clinically non-deployable prototype** of the user's established journey: doctor-verified encounter → national-ID-bound one-use invitation → patient registers → patient completes compatible fields → actual *authorized* trained-model inference + explanation → provisional `PENDING_REVIEW` → clinician reviews → clinician-authored note and educational demo prescription → durable in-app notification and patient inbox → longitudinal history.

The two development tracks are **independent**:
- Existing full research/system track: RH-04/05/03/07/08 and future product; remain on their existing branch/PRs, untouched. PR #141 is not an automatically approved dependency.
- Term-1 delivery track: this branch, with one continuous implementation sprint and one draft PR (rather than many delivery PRs), incremental commits and checkpointed tests. Do not merge, self-ratify or close existing gates.

Use **real FastAPI endpoints, RBAC, SQLite + SQLAlchemy/Alembic persistence and actual trained-model computations**; no cosmetic mock AI output claimed as a trained inference. A trained synthetic model is real computation but **not clinical validation**. Do not access real patients, real identifiers, private bundle, real-world prescriptions or deploy clinically.

Controlling documents include `AGENTS.md`, `docs/DECISIONS.md` (D-038, D-039, D-043, D-045), `docs/blueprint/01_MASTER_ARCHITECTURE_AND_DELIVERY_BLUEPRINT.md`, `02_FEATURE_TRACEABILITY_MATRIX.md`, `04_DATABASE_AND_API_INTEGRATION_DESIGN.md`, `docs/research/next_phase/RH06_EVIDENCE_BOUNDED_RESEARCH_PROTOTYPE_DESIGN_DECISIONS_2026_11_19.md` (RD-01…10), and `docs/GRADUATION_DELIVERY_ROADMAP.md`. A separate prototype branch does NOT waive these decisions.

## 1. Locked user journey and software-team feature mapping

1. **Clinic/admin bootstrap:** local-only provisioned admin account using env/secrets, no committed credentials. Admin creates doctor account/invitation. Doctor authenticates, changes temporary password if used.
2. **Verified visit BEFORE invitation:** clinician records a `verified_visit` (educational attestation: clinic staff confirms the visit and document at the clinic) and explicitly issues a random one-use patient access code **bound to that visit, that doctor and the presented national identifier**. No self-service code issuance.
3. **Patient enrollment:** patient supplies access code, matching national identifier, name, email, password. Server atomically checks code/expiry/revocation/unused state and identifier match, creates patient identity, links doctor and marks invite consumed. Generic rejection; never reveals which part mismatched. Send doctor an in-app new-patient notification.
4. **Authentication/profile:** patient signs in and enters limited demo health profile; field source/provenance, timestamps and validation are explicit.
5. **Assessment initiation:** patient requests a new evaluation from a versioned registered feature schema; required/missing/out-of-range data rejected. Persist immutable input snapshot before inference. Do not promote OCR, patient statements, lab results or Track-B wearables to clinician-confirmed Track-A evidence.
6. **Model inference:** independently reviewed and explicitly authorized real trained-model adapter computes a score and *same-model* explanation on synthetic records only. Store artifact/model/schema/version/digest, input snapshot digest, response/error, classification target and scientific limitations. No synthetic fallback disguised as result.
7. **Patient preliminary state:** user-requested `NOT_REVIEWED` UX; default policy hides Track-A score from patient until a separately ratified **synthetic educational demo** patient-display decision and reviewed wording. Even after approval, label as research score, not patient CAD risk probability, prediction horizon or actionable diagnosis. Score and explanation are never personalized care advice.
8. **Doctor queue/review:** clinician sees assigned patient and evidence, including unmodified input snapshot and model result, enters an auditable decision (accepted/rejected/reassessment requested) with rationale. Reviewer action does not overwrite inference.
9. **Follow-up:** clinician writes educational note and demo prescription and sends it as an assessment-linked follow-up message. AI never prescribes. In the same transaction, persist message and outbox/notification, with idempotency.
10. **Patient inbox:** read/unread in-app notifications via API polling; patient opens clinician note and demo prescription. Persistence after server restart, proper access control.
11. **History:** patient and clinician can retrieve only their authorized assessments, reviews, follow-up and notifications. Later re-assessment creates a new immutable record following valid reasons.

## 2. National-ID-bound invitation: required security semantics

**Critical distinction:** code + national ID alone do not independently prove a real visit. The **clinician's verified-visit attestation** is the system's required evidence, with actor and timestamp; this remains a demo attestation, not external government identity verification.

- Never send real Egyptian national IDs, medical records or identifying patient data to Arena, ChatGPT, git, CI or demo fixtures. Use deliberately fictitious `DEMO-ID-001`-style identities in demo mode; production-format validation is separately gated. No real patient signup or production clinic data under this prototype.
- For eventual real-data deployment: a 14-digit Egyptian national identifier (syntax alone is NOT verification) should be normalized at a trusted server boundary and *never logged or committed*. For matching, store a **keyed HMAC-SHA256 digest** with independently managed secret, not bare SHA256, in the invitation/subject identity matching index. Never expose digest to clients. If storage or recovery of the original identifier is necessary in a future regulated product, separately design authenticated encryption + strict retention/access policies; no such capability is required for this educational demo.
- Invitation token: cryptographically secure >=128 bits random entropy, display only at creation, store verifier/digest not plaintext; short TTL; revocable; single redemption; clinician/visit binding; bounded attempts and rate limiting; generic errors and no PII leakage. No email/password-based existence enumeration.
- Database transaction must atomically create a patient+assignment and consume the invite (compare-and-swap/unique constraints) under concurrent attempts; rollback cleanly on any failure, and test two concurrent redemptions.
- Separate `visit_verified_by_doctor_id`, `visit_verified_at`, `invitation_issued_by`, `issued_at`, `expires_at`, `consumed_at`, `revoked_at` audit fields.
- Restricted clinicians cannot generate invitations for other doctors' visits. Revoked/expired/used/mismatched codes fail closed.
- No national ID value in route params, responses, exception strings, audit payloads, logs, snapshots, fixture JSON or notifications.
- Any actual clinic deployment and real national IDs require separate legal/privacy/security approval, not implied by this plan.

## 3. Strict Term 1 feature scope

### P0 (acceptance-critical, single vertical slice)
- Seed/local provision of admin and at least one doctor; secure local account login/logout and roles `admin`, `doctor`, `patient`, role-bound authorization.
- Verified-visit entry + national-identifier-bound single-use patient invitation + registration and assignment.
- Patient health profile and validated synthetic five-field Cleveland DA-A2 assessment intake (`age, sex, cp, trestbps, restecg`) if that exact model route is eligible for the approved demo; do not invent fields or transfer across sources.
- Immutable assessment and input-snapshot persistence with separate inference/review status.
- One explicitly reviewed and authorized **trained AI** inference route; real compute and attached explanation. No authorized inference = explicit blocker (NOT_DONE), not a mock pass.
- Doctor pending-review queue, review action, clinician-authored follow-up/prescription (simple text/structured demo content).
- Durable in-app notifications, read/unread, inbox and assessment history.
- SQLAlchemy/Alembic migrations, RBAC, privacy, negative/transaction tests, OpenAPI, local Windows runbook, end-to-end synthetic test.

### P1 (only after P0 works)
- Forced first-login password change, admin minimal UI, PDF export generated from clinician-authored demo content, lightweight clinician patient summary, local self-service change password, simple monitoring history reused from Track B.

### DEFERRED to Term 2
- Real smartwatches/Health Connect and wearable sync, real OCR and clinical-lab mapping, unrestricted real-patient ingestion, clinician-patient realtime chat and rich uploads, email/SMS password reset, cloud push, medication schedules, appointments, receptionist, full admin dashboard, risk-band charts, high-risk alerts, automated treatment recommendations, account hard delete, source pooling, cross-source model adaptation.

## 4. Data model (proposed; inspect existing schema first)

`user_account` (role, password hash, active/session lifecycle), `doctor_profile`, `patient_profile`, `verified_visit`, `patient_invitation` (unique random token verifier + keyed identifier digest, FK doctor/visit, expiry/status), `doctor_patient_assignment`, `health_profile`, `consent_record` (synthetic demo acknowledgement), `assessment` (owner, version, snapshot, provenance, status, idempotency), `inference_result` (immutable model artifact/score/XAI and failure metadata), `assessment_review` (append-only decision history, latest effective state), `follow_up_message`, `demo_prescription`, `notification_record` (recipient/type/read_at), `audit_event` (metadata only). Existing `monitoring_observation`, `monitoring_metric` and related audit behavior MUST remain intact.

Use proper FKs, indexes, uniqueness, migration history, crash/restart tests, timestamp UTC, transactions, and server-enforced ownership. Avoid two sources of truth for review state. No blind destructive migrations, reset-on-start or schema auto-create as deployment substitute.

## 5. Proposed /v1 contracts — MUST reconcile and freeze before code

Existing `POST /v1/predictions/cad-tabular`, monitoring and OpenAPI stay byte/behavior compatible; do not silently switch their provider. Propose (not yet implemented):
- `POST /v1/auth/login`, `POST /v1/auth/logout`, `GET /v1/auth/me`
- `POST /v1/admin/doctors`
- `POST /v1/doctor/verified-visits`, `POST /v1/doctor/verified-visits/{id}/invitations`
- `POST /v1/patients/register` (access code + identifier match)
- `GET/PATCH /v1/me/health-profile`
- `POST /v1/assessments`, `GET /v1/assessments/{id}`, `GET /v1/me/assessments`
- `GET /v1/doctor/patients`, `GET /v1/doctor/assessments`, `POST /v1/assessments/{id}/reviews`
- `POST /v1/assessments/{id}/follow-up`, `GET /v1/me/messages`
- `GET /v1/me/notifications`, `POST /v1/me/notifications/{id}/read`.

For each endpoint: role/actor/subject ownership; request and response schemas; idempotency, validation order, errors, pagination, confidentiality, versioning and contract tests. Avoid exposing the model service as a general-purpose ungated API.

## 6. Model selection/serving: explicit owner gate

- Research track currently has synthetic offline research paths and separately recorded Cleveland real-data exploratory results. These are NOT automatically licensed for HTTP medical serving.
- RD-09 explicitly separates the approved `MOCK_SYNTHETIC` HTTP provider from offline `ai/` research. Prototype branch does not override it. Existing Cleveland real-bundle permission does not authorize clinical/patient-serving. Review full source/protocol/registry and preserve Gate PT.
- Candidate A (preferred if eligible): exact reviewed trained model artifact with permitted synthetic demonstration inputs and verified SHAP/LIME or model-tied explanations, under a **new explicit educational local-demo activation decision** and dedicated adapter. If Cleveland real-data-trained bundle is not authorized, do not load it in hosted Arena.
- Candidate B: explicitly authorized trained-on-synthetic model, with real model computation, exact artifact SHA, matching five-field schema and transparent `TRAINED_ON_SYNTHETIC` label; not clinically validated.
- No new real-data download, retraining, bypass of trusted registry, model-deserialization shortcuts or medical claim. Never re-label `MOCK_SYNTHETIC` as a real model.
- Withhold patient score by default. Draft a separate owner decision specifying exactly what synthetic patient UI may display. Do not activate this merely by a flag unless the decision is ratified and tests enforce it.
- Independent reviewer checks actual model output against the registered local research oracle and validates explanation, tamper refusal, mismatch refusal, failure behavior and no leakage before admission.

## 7. State machine

`assessment_state`: DRAFT/INPUT_VALIDATED → INFERENCE_RUNNING → PENDING_REVIEW on valid inference; INFERENCE_ABSTAINED/INFERENCE_UNAVAILABLE/INFERENCE_ERROR otherwise. `review_state`: NOT_REVIEWED → ACCEPTED/REJECTED/REASSESSMENT_REQUESTED (revisions are append-only review actions). Never infer clinical triage/risk level. All failures clear stale scores. Reassessment is a new snapshot with a permissible reason; time passage or wearables alone are not valid triggers.

## 8. One-sprint implementation workflow (user-authorized delivery preference)

**One branch + one draft PR + one Arena session + incremental evidence checkpoints**, not six sequential PRs. Proceed continuously on safe P0 engineering work. Keep cohesive commits and an append-only evidence log; do not hide unfinished modules or weaken tests.

- **C0: inventory & decision register.** Read full repo, controlling docs, actual backend/schema/contracts, local/test instructions. Audit model eligibility, gaps and consent/security concerns. Produce a no-assumption acceptance map, freeze API+ERD, owner-decision questions. Continue safe non-serving work if a separate decision is pending.
- **C1: auth/visit/invitation.** Migrations, secure accounts, verified visit and patient matching workflow; negative/concurrency tests.
- **C2: assessment/AI.** Snapshot, validated source-specific intake, authorized trained adapter; genuine score+XAI only; fail-closed and model provenance tests. If serving approval blocked, implement the interface and disabled path, label this gate NOT_DONE and continue other pieces.
- **C3: review/follow-up/notifications.** Atomic clinician audit, note/prescription/in-app inbox, history and restart tests.
- **C4: integration, regression, handoff.** Whole synthetic journey, role isolation, migration-upgrade, API contract, backend and full pytest, dependencies and Windows execution instructions; exact-head hosted CI and native-local verification.

No automatic merge. Owner and independent reviewer accept only after evidence. If one sprint becomes too large, pause optional features, never reduce privacy/scientific gates.

## 9. Term 1 test and acceptance protocol

Positive synthetic E2E: provision admin/doctor → doctor attests demo visit → issue national-ID-bound code → patient registers with matching test ID → consumed code cannot be reused → profile → assessment → real trained authorized model executes once (real inference digest/score/XAI) → stored PENDING_REVIEW → authorized doctor reviews → follow-up note and synthetic prescription → notification UNREAD → patient opens → READ → restart backend → all durable history intact.

Negative tests: code wrong/expired/revoked/used, mismatched ID, duplicate concurrent signup, non-verified visit, doctor/patient cross-tenant IDOR, suspended user, invalid data source/snapshot, Track B or unverified OCR feeding CAD, tampered model or wrong digest, missing model authorization, failed inference not leaving stale scores, refusal/abstention, review double-post and illegal transitions, idempotent follow-up, SQL transaction rollback, audit secrecy, no National ID in API/DB except approved HMAC in test environment, and migration/restart integrity.

Record exact commands, test counts and failures on Windows, `python -m pip check`, `python -m alembic upgrade head` / `check`, `python -m pytest tests/contracts tests/backend -q -W error`, `python -m pytest -q -W error`, `git diff --check`, hosted CI exact head, and actual POST/read/restart smoke tests. Do not claim Windows result from Linux.

## 10. Timing, severity and handoff

Target 2026-11-25 to 2026-12-03 is **high-risk**, not guaranteed:
- 25: branch + master plan + feature freeze, owner-decision packet.
- 26: audit + frozen contract/ERD + tested onboarding data model.
- 27–29: auth/visit/registration + assessment/persistence/model adapter.
- 30–Dec 1: clinician review, follow-up, notifications, end-to-end and regressions.
- Dec 2: review, exact SHA freeze, Windows run, documents.
- Dec 3: handoff to software team; list IMPLEMENTED/TESTED/DEMO_BLOCKED/DEFERRED honestly.

**P0 stop-the-line:** uncontrolled National ID or PHI; unapproved real-bundle invocation; silent bypass of RD-09/Track A/B rule; mock claimed as trained; forged medical prediction risk; broken RBAC/IDOR; destructive migration; no working patient→doctor→patient journey. **P1 cuts:** PDF first, UI/admin sophistication, stats, optional account features. Do not declare complete if P0 not met.

Deliverable: one draft PR, implementation evidence register, README local Windows PowerShell runbook, OpenAPI snapshots, ERD/migrations, demo seed *fictitious* identities, synthetic E2E tests, current CI and residual blocker ledger. No self-merge.

## 11. Required owner decisions (not granted by this doc)

1. Explicitly authorize the new non-clinical **Term 1 demo software scope**, preserving old workflows and no PHI.
2. Approve a suitable **trained-model inference serving/adapter scope** with exact artifact/inputs/access, or keep serving disabled and report NOT_DONE.
3. Decide whether **synthetic patient actor may see a research-model score before clinician review**, and specify reviewed educational wording. Until then: only state PENDING_REVIEW on patient side.
4. Confirm clinician-attested synthetic visit + national-ID-bound invitation semantics are acceptable for educational demo; real identification requires separate validation and privacy review.

The draft plan/branch/PR are **not** any of these ratifications.

## 12. Dated delivery-scope amendment (2026-11-27; proposed for exact-head acceptance)

See [Term 1 real-model reuse and bounded OCR delivery plan](TERM1_DELIVERY_PLAN_AMENDMENT_REAL_AI_OCR_20261127.md) for the owner-directed intended delivery scope, preservation of accepted C0/C1, exact main reuse inventory, new bounded document/OCR slice, real-data-trained Candidate A preference, local admission and patient-display gates, remaining stage sequence and handoff checklist. Once separately ratified and merged, it governs only the explicitly amended scope. The original plan is retained for audit history. General clinical OCR/rich uploads remain deferred; the new scope is fabricated fixed-template reports only. No operational authorization is granted by this pointer.
