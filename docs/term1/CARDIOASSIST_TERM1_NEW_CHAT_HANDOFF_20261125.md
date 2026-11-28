# CardioAssist-AI — Complete New-Chat Handoff & Independent Reviewer Operating Agreement

> **Date / timezone:** 2026-11-25 / Africa-Cairo  
> **Purpose:** Transfer the precise state, agreements, project boundaries, roles, engineering methodology, intended Term-1 implementation and first-turn verification protocol to a **new ChatGPT conversation**.  
> **Language:** Speak to the owner in Egyptian Arabic; technical names, commands and file paths remain as written.  
> **Status:** Context handoff and verification instructions, **not** scientific approval, implementation permission or evidence of tests passing.  
> **Mandatory rule:** Inspect the live GitHub repository independently before relying on this snapshot. If current evidence differs, report the discrepancy instead of silently updating history.

## 0. Two conversations, two separate tracks

- **Original/current ChatGPT chat = FULL SYSTEM / RESEARCH**. Keep the existing research governance, RH-04 and related work here. Do not mix its Arena session, PRs or decisions with the Term-1 implementation.
- **New ChatGPT chat = TERM-1 WORKING PROTOTYPE**. It becomes the new independent reviewer/planner for the prototype and coordinates a **separate, new Arena coding session** working only on its delivery branch. It must first pass the discovery/readiness exercise in §12. This does not mean independent ChatGPT chats share private live state.
- The owner will bring the new chat's **independently generated Markdown discovery report** back to the original chat for review. The original chat will compare the report to GitHub and issue exact corrections or confirm the new chat is prepared. Until this cross-check, the new chat should not instruct Arena to start implementation or change repository files.
- Research and prototype share the original codebase at the start; they are not authorized to silently merge one another's branches or artifacts.

## 1. Project identity and product objective

- **Main source repository:** https://github.com/Muhammed-Fathi/CardioAssist-AI
- **Owner/coordinator:** human repository maintainer, who decides scope, ratifies decisions, operates a trusted local Windows machine and controls merges.
- **Product:** CardioAssist-AI — AI-assisted patient–doctor follow-up. The intended long-term system includes a Flutter patient application, React/TypeScript doctor dashboard, FastAPI backend, durable database, CAD research inference with explanation and clinician review, follow-up records and messages; later expand monitoring/wearables, OCR/lab ingestion, scheduling and additional roles.
- **Term-1 target handoff:** **Thursday, 2026-12-03**, to the software team. This is a **high-risk target, not a guarantee**.
- **Term-1 deliverable type:** limited **synthetic-only educational research prototype**, not a clinically validated patient-ready CAD system, and not suitable for actual patient treatment. No real patient health records or Egyptian national ID values in cloud agents, GitHub, CI, fixtures or sample databases.

## 2. Exact GitHub checkpoint (independently verified 2026-11-25)

| Reference | Verified checkpoint | Interpretation |
| --- | --- | --- |
| Original main | `c6a6bdee46a552a2b0d705a723c862ff8a95be4d` | Research/system baseline |
| Term-1 branch | `delivery/term1-prototype` | Created from the above main SHA |
| Term-1 branch HEAD | `c11555c713321f0ed700a43347766971582dfffc` | **Documentation ONLY** — no new prototype implementation |
| Term-1 PR | [PR #142](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/142) | OPEN / DRAFT, base main |
| Research RH-04 PR | [PR #141](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/141) | OPEN / DRAFT, at verification HEAD `9fb6d5173171bbdc22fd1528131bd2dd5b8963f5`; do not touch in prototype |
| Research blocker | [Issue #132](https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/132) | RH-04 reproducible golden replay / numeric verification, reconcile current live issue state |
| Brand-new software-team repo | **NOT CREATED** | Only create after prototype reviewed, tested and export curated |
| Native Windows E: workspace | **User intends to set it up** | Do not assert it exists unless user confirms terminal evidence |

At this checkpoint PR #142 contains exactly these **three planning files**:
1. `docs/term1/TERM1_INTEGRATED_PROTOTYPE_MASTER_PLAN_20261125.md` — product/engineering/AI/security plan, explicit owner decisions.
2. `docs/term1/ARENA_NEW_SESSION_MASTER_PROMPT_20261125.md` — original full one-sprint English implementation mandate for Arena, *not* proof of work.
3. `docs/term1/WINDOWS_LOCAL_VERIFICATION_RUNBOOK_20261125.md` — draft Windows PowerShell testing guide, not executed proof.

This handoff document may be the fourth docs-only file added to PR #142. Re-check changed files and HEAD immediately on the new chat.

## 3. Non-negotiable engineering roles

### Human owner
- Owns feature scope, safety/privacy choices and clinical/research authorizations, merge decisions and local Windows actions.
- Shares Arena logs, PRs, screenshots and command output for review; may want a complete one-copy/paste command block instead of fragmented instructions.
- Has not granted implicit approval for research model serving or patient-visible CAD scores simply by requesting a prototype. Explicit ratification should be requested and verified at the appropriate decision point.

### ChatGPT in the new Term-1 chat: INDEPENDENT TECHNICAL REVIEWER + ARCHITECT
- First read this handoff, then **discover and inspect live repo independently**: exact Git SHAs, PR status, instructions, relevant implementation files, migrations, AI registry, tests and approval records.
- Design final architecture, reconcile features with scientific limits, write acceptance criteria and give full ready-to-copy Arena prompts and Windows PowerShell blocks.
- Review **every significant Arena checkpoint** against actual code/diff, tests, CI exact HEAD and DB/AI/security evidence, not the agent's statements. Distinguish: repository-confirmed, hosted-CI-confirmed, owner-Windows-confirmed, agent-reported, proposed and blocked.
- Find real faults and request fixes with precise paths/lines/reproduction; do not reflexively approve or apologize instead of correcting.
- Never auto-approve or merge, close RH-04 Issue #132, change research gate, disable contract checks or claim real Windows execution from a Linux runner.
- New ChatGPT chat should initially be **READ-ONLY**: produce its own Markdown discovery report first for cross-review. It must not create a new branch, new PR, duplicate planning docs, or instruct Arena to execute in this first stage.

### Arena: IMPLEMENTATION AGENT
- Has its own **separate new session** for the Term-1 branch; reads instructions/docs; carries out engineering implementation, tests and fixes.
- One continuous implementation sprint on one branch with one existing Draft PR #142 and **incremental coherent commits C0→C4**. Do not split the implementation into six mandatory separate PRs; checkpointing and tests remain mandatory.
- No changes to main, PR #141, RH-04 research branch or unrelated files. No force push, self-merging or self-ratification.
- Must provide a complete evidence report for independent review. If a policy-sensitive step is blocked, leave it disabled and continue unrelated safe work.

### Software team
- Builds **Flutter patient client + React doctor dashboard**, integrating the frozen versioned OpenAPI/JSON schemas.
- Agrees on screens, roles, validation, states and error behavior **before** building against guessed APIs.
- For Term-1, focus on thin functioning journey; richer UI and all extra features can come later.

## 4. Actual as-built stack versus target stack (never conflate)

### Confirmed as-built at main checkpoint
- Real FastAPI project and versioned OpenAPI contracts.
- `POST /v1/predictions/cad-tabular` returns deterministic **MOCK_SYNTHETIC** prediction and explanation-shaped data, NOT a trained-model result.
- `POST /v1/monitoring/observations` has **real durable SQLite persistence** for observation/metric records and an associated success audit. This is Track B only.
- Existing SQLAlchemy/Alembic migration foundation, with focused tests.
- The live application backend **does not yet implement** production-style accounts, RBAC, doctor/patient identities, invitations, review actions, prescription/messages/in-app notification/history or real-model HTTP serving. Treat the attached blueprint/contract proposals as design, not implemented code.
- Offline `ai/` research tools and bundles exist separately. The research code is not permission to instantiate a real model in the FastAPI mock service.

### Target Term-1 P0, requiring implementation and tests
- Role-bound admin/doctor/patient login and session security; clinician-verified encounter.
- One-use access code bound to **doctor + verified visit + patient national identifier match**.
- Patient demo health profile and immutable validated assessment snapshot.
- **Actually trained and explicitly authorized** educational inference and same-model explanation with provenance.
- PENDING_REVIEW state, doctor queue, append-only review action.
- Clinician-authored demo notes/prescription, patient inbox, durable in-app notifications/read status and history.
- E2E synthetic workflow and negative/concurrency tests; Windows local runbook and reproducible install/handoff.

### Strict priority
P0 first: above vertical slice. P1 only when stable: generated PDF, richer admin/dashboard, first-login-password reset UX, simple monitoring visualization. Deferred: real smartwatch/Health Connect, real OCR and lab mapping, advanced chats/attachments, push, medication reminders, appointments/reception, cloud production hosting, patient hard delete, actual personal risk bands and automated drug recommendations.

## 5. Agreed user journey end to end

1. Clinic doctor confirms an **already occurred visit** and saves an auditable attestation (actor/timestamp). A code plus ID alone does NOT prove attendance.
2. Doctor issues cryptographically random, time-limited, revocable, one-use invite tied to this visit, clinician and national-identifier matcher.
3. Patient enters code, national identifier and registration fields in Flutter; backend atomically validates and consumes invite, creates patient and doctor assignment.
4. Patient logs in, fills limited health profile. Only declared source-specific synthetic demonstration features are admissible to candidate model. Missingness and units are validated.
5. Patient starts assessment, backend saves immutable versioned input/provenance snapshot. Existing Cleveland DA-A2 historical **five-field research panel**: `age, sex, cp, trestbps, restecg`, subject to specific approved route/artifact.
6. If separately authorized, trained-model adapter actually computes research score + matched explanation. Store exact model, artifact/schema/version/digest, input snapshot, inference status. On unauthorized/abstain/unavailable/error -> fail closed, no stale score, no fake fallback.
7. Patient sees assessment status `PENDING_REVIEW`. Requested user experience of seeing **preliminary score** prior to doctor review remains an **explicit open decision** inconsistent with the previous patient-visible score prohibition. Until approved, patient sees only status and research-safety wording, not score. Do not misrepresent result as individual CAD diagnosis/risk%.
8. Doctor receives in-app pending assessment notification; dashboard lists own assigned patients/queue. Doctor sees data, version, result and explanation; chooses ACCEPTED / REJECTED / REASSESSMENT_REQUESTED with reason and audit trail; never overwrites model result.
9. Doctor writes educational follow-up note/prescription himself, independent of AI; one atomic save of message and persistent notification/outbox, with idempotency.
10. Patient opens app inbox, reads message and demo prescription, marks notification READ.
11. Both actors access authorized longitudinal history; all persists across service restart. Further reassessment creates a new assessment under an allowed reason, never from wearables/time passage alone.

## 6. National-ID/verified-visit design: user’s latest added requirement

**Product intent:** app registration is permitted only to someone whose doctor confirmed that they actually visited the clinic and issued an invitation to that identified person.

**Important boundary:** for Term-1 test work, do not use actual 14-digit Egyptian national IDs. Use **fictitious identifiers** (e.g., `DEMO-ID-001`); no real identity checking/clinical use is proven. No actual patient data anywhere in GitHub, Arena, CI, prompts, logs or fixtures.

- Architecture for eventual secure matching: server-normalized national ID → **HMAC-SHA256 keyed with separate protected secret**, not unkeyed hash, for consistent protected matching. Avoid retaining plaintext national ID unless a separately approved operational necessity/privacy design exists.
- Invitation token high entropy (≥128 bits), secret one-time display, verifier/digest stored, expiry, revocation, bounded retries, generic messages; **do not use access code itself as a login credential**.
- Verify clinician and encounter ownership. Create account, assignment and consume invitation in one atomic DB transaction with uniqueness/concurrency tests.
- Track invitation issuer, doctor, visit, verified_by, verification timestamp, expiry, redemption/revocation, without exposing sensitive identifiers in API or logs.
- New system should not infer that possession of National ID proves identity or actual clinic presence; clinician attestation is a prerequisite, with stronger real-world identity checks required outside this demo.
- Do not permit true medical-data use or production-format national-ID collection by default.

## 7. Scientific/AI integrity and approval boundaries

- Research task in RH-06 design: cross-sectional historical angiography-referenced CAD **presence classification**, not 30-day risk, severity, future heart attack, diagnosis for a current individual or treatment decision.
- Historical Cleveland DA-A2 five-field path, L2 logistic baseline plus comparators; review exact source/protocol/accepted artifact and scientific evidence. A historical **real Cleveland-trained exploratory bundle** was reported in a trusted local Windows workspace, not trusted as an Arena-hosted/public serving artifact.
- **RD-09** preserves separate `ai/` research and a single `MOCK_SYNTHETIC` HTTP provider. Model registry serving authorization remains restricted. Do not bypass this with environment flags, HTTP wiring or branch isolation.
- Some historical offline real-bundle authorizations were narrower than generic serving; re-baselining/activation gates remain separate. Read exact latest G3/A3/current gate record rather than assuming permission.
- Real trained inference could be a real-data-trained approved artifact **if** exact educational synthetic-input serving is authorized, or a trained-on-synthetic artifact **if** that specific route is explicitly authorized. The latter is genuine numerical model computation, but has no clinical validation claim.
- SHAP/LIME attributed values must come from the same identifiable model/background/score scale and be tested for stability. Do not claim synthetic-looking explanation objects from the mock endpoint are actual explanation.
- Patient-visible preliminary **CAD score** and any risk band/alert remain separately gated; default only `PENDING_REVIEW` to the patient. No AI-generated medication or medical recommendations.
- Track B wearables/monitoring cannot feed Track A CAD inference; unverified OCR/labs cannot automatically become clinical features. Preserve explicit rejection, test failures.
- Exact baseline documentation: `AGENTS.md`, `docs/DECISIONS.md` D-038/D-039/D-043/D-045, `docs/blueprint/01_MASTER_ARCHITECTURE_AND_DELIVERY_BLUEPRINT.md`, `02_FEATURE_TRACEABILITY_MATRIX.md`, `04_DATABASE_AND_API_INTEGRATION_DESIGN.md`, `docs/research/next_phase/RH06_EVIDENCE_BOUNDED_RESEARCH_PROTOTYPE_DESIGN_DECISIONS_2026_11_19.md`, `docs/GRADUATION_DELIVERY_ROADMAP.md`, research admission/scope registry and Gate PT records.

## 8. Target backend architecture, contracts and data model (PROPOSED, NOT BUILT)

### Internal boundaries
Authentication/Role Gate → Encounter/Invitation → Patient Profile → Assessment Intake + Source/Schema Validator → Policy-Gated AI Adapter → Durable Assessment/Inference → Clinician Review → Follow-up/Notifications → History.

Prefer reusing existing FastAPI and SQLAlchemy/Alembic, with portable migrations; do not start a new backend or silently alter the legacy mock CAD endpoint and monitoring behavior.

### Core entities
- `user_account`; `doctor_profile`; `patient_profile`; `doctor_patient_assignment`.
- `verified_visit`; `patient_invitation` with HMAC index, one-time verifier, expiry/revocation.
- `health_profile`; `consent_record`.
- `assessment` with stable input snapshot/provenance/versions; `inference_result` with immutable actual-model result and status.
- `assessment_review` append-only action history and reason; `follow_up_message` and `demo_prescription` clinician-authored only.
- `notification_record` read state and recipient; `audit_event` safe metadata.
- Preserve existing `monitoring_observation`, `monitoring_metric` and their audit behavior.

### Proposed API inventory — must be reconciled against current contracts
- `POST /v1/auth/login`, `POST /v1/auth/logout`, `GET /v1/auth/me`.
- `POST /v1/admin/doctors`.
- `POST /v1/doctor/verified-visits`, `POST /v1/doctor/verified-visits/{id}/invitations`.
- `POST /v1/patients/register`; `GET/PATCH /v1/me/health-profile`.
- `POST /v1/assessments`, `GET /v1/assessments/{id}`, `GET /v1/me/assessments`.
- `GET /v1/doctor/patients`, `GET /v1/doctor/assessments`, `POST /v1/assessments/{id}/reviews`.
- `POST /v1/assessments/{id}/follow-up`, `GET /v1/me/messages`.
- `GET /v1/me/notifications`, `POST /v1/me/notifications/{id}/read`.

All API contracts require RBAC + object-level authorization, validation/order/errors, idempotency and repeat/restart tests, OpenAPI and durable backing data. No approval implied by listing routes.

## 9. Continuous one-sprint execution requested by owner

The owner **does not want multiple separate implementation PRs** that each wait for sign-off. They want one Arena session, the existing single delivery branch / one Draft PR, and a broad master task that proceeds autonomously with **internal commits, checkpoints and tests**:
- **C0:** Full repo & model inventory, acceptance map, exact API/ERD proposal, identify owner-approval blockers.
- **C1:** Auth + doctor verified visit + invitation + patient registration, atomicity and security tests.
- **C2:** Health profile + assessment input snapshot + model adapter + actual approved trained inference or clearly blocked status.
- **C3:** Doctor queue/review + clinician-authored follow-up/prescription + durable inbox/notifications/history.
- **C4:** Positive & negative synthetic E2E, migration/restart/rollback, hosted CI exact HEAD, Windows local steps, handoff.

The reviewer may request remedial commits without restarting the project. If C2 authorization is blocked, Arena should continue independent safe backend modules; never announce trained-AI integration DONE until real inference and approval are shown.

## 10. Acceptance, tests and reporting style

Required positive E2E using fabricated identities:
doctor created → attested demo visit → one-time identity-bound code → correct registration and doctor link → patient login/profile → valid synthetic assessment → **actual authorized trained inference + model-tied explanation** → saved PENDING_REVIEW → doctor reviews → follow-up/demo prescription → notification unread/read → service restart → same persistent records.

Required negative tests: wrong/mismatched/expired/revoked/reused access code, concurrent double redemption; no verified visit; inactive users, IDOR/cross-tenant patient/doctor access, unauthorized model provider and tampered artifact, non-admissible fields/Track B/OCR data, invalid review transitions, duplicate follow-up, stale response, transaction rollback, migration drift, secrets/PII leaks.

Check and **record exact results**: Git SHA/branch/dirty status, source diff and ancestry, schema/Alembic upgrade/check, dependency health, focused contracts/backend tests, full pytest, git diff --check, current GitHub Actions jobs for **that exact SHA** (not earlier ones), real Windows PowerShell verification by owner.

Classification for each claim: `IMPLEMENTED_AND_TESTED` / `IMPLEMENTED_BUT_BLOCKED` / `PENDING_AUTHORIZATION` / `NOT_IMPLEMENTED` / `DEFERRED`. For source claims distinguish direct file observation, hosted CI, owner-local Windows, agent report and inference.

A Draft PR alone proves none of code functionality, approval or Windows success. No self-merge/ratification; no skipping tests, widening tolerances to green, falsifying model/artifact identity, or resetting project data.

### Response style agreed with owner
- Egyptian Arabic and professional, direct, rigorous; **do not merely agree**.
- Short conclusion first, then technical evidence and one **complete copy/paste-ready command/prompt block** whenever asking owner to run/send commands; don't dribble many command snippets.
- No needless clarification if detail already agreed. Answer what's done / what's pending / exact next action.
- Independent mathematical, scientific and engineering scrutiny; do not take Arena's 'all green' as evidence until independently corroborated.

## 11. Windows local environment and eventual separate software-team repo

User wants **E: partition**, exact workspace folder:
`E:\CardioAssist-Term1-Prototype`

It should be a clone of only `delivery/term1-prototype` from the original GitHub repository (after ensuring the destination folder does not already contain valuable files). Example:

    git clone --single-branch --branch delivery/term1-prototype https://github.com/Muhammed-Fathi/CardioAssist-AI.git E:\CardioAssist-Term1-Prototype
    Set-Location E:\CardioAssist-Term1-Prototype
    git branch --show-current
    git rev-parse HEAD
    git status --short

User will test backend/DB/AI on their own Windows device. Existing verified base backend commands in `backend/README.md` include venv, `backend/requirements-dev.txt`, `CARDIOASSIST_DATABASE_URL`, `python -m alembic upgrade head`, `python -m alembic check`, `python -m pytest tests/contracts tests/backend -q -W error` and `python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1`. Prototype seed/demo-API commands are **not yet implemented**, so do not invent them.

**Later (NOT NOW):** when prototype passes independent review and local Windows checks, curate minimal deliverable code, tests, migrations, contracts, relevant AI artifacts with redistribution rights, readme and attribution. Then create a **new clean repository** intended for the software team, with fresh history rather than copying original full git history. Do not remove/misattribute real contributors merely to disguise their work. A new repo whose commits are authored by the owner may show only that account in GitHub’s contributor list, but that does not erase actual source authorship or attribution duties. No new repo has been made yet. Keep original research repo and historical evidence intact.

## 12. REQUIRED first turn in the new ChatGPT chat: independent discovery ONLY

The owner is afraid of losing context or ChatGPT chat limits. The initial new chat **must prove understanding**, not just echo this document.

### First response tasks
1. Read this complete handoff and the three current Term-1 planning files. Then use **GitHub tools** to fetch current repository, branch/main SHAs, PR #142, PR #141, changed files, linked governing source docs and actual backend/AI/DB code/tests.
2. Independently identify as-built vs merely planned: exact backend behavior, model registry and actual available trained artifacts/eligibility, migration scope, repo controls, test suites, client status and current policy blockers.
3. Inspect origin relationship of `delivery/term1-prototype` to main and PR #142; check for new Arena commits or new commits since handoff. Note any changed HEAD with exact SHA.
4. Produce a substantial **Markdown file** named `CARDIOASSIST_TERM1_INITIAL_INDEPENDENT_AUDIT.md`, **downloadable as .md**, using the template in §13. Do not claim tests executed unless actually run. Include links/citations to files, PRs, evidence and SHA, not only broad narrative.
5. Clearly say `READY_TO_DIRECT_ARENA` or `NOT_READY_YET`, with precise reasons. A preliminary READY claim is **not final approval**. Do not send Arena instructions to start implementation, alter repo, create PR, merge or activate AI in this first turn.
6. Provide the owner the MD download/link and ask them to bring the audit report **back to the original ChatGPT conversation for independent cross-check**. After original chat critiques it, the owner returns instructions to the new Term-1 chat, and only then should it coordinate Arena on the existing branch / PR.
7. Do not interpret a summary of old messages as verified current source state. Re-verify.

### What matters most in the first audit
- Cited exact PR/branch/SHAs.
- Authenticated real backend versus mock prediction; actual DB tables.
- Explanation of real offline model/registry, gate limitations and why 'model trained' != 'serving allowed'.
- Registered patient journey and precise national-ID invitation security semantics.
- Correct one-sprint execution and roles.
- True Windows path `E:\CardioAssist-Term1-Prototype` and future software team repo distinction.
- P0 feature map with dependencies, fail-closed statuses and acceptance tests.
- Honest blockers and no unwarranted authorizations.

## 13. Initial independent audit report — minimum template

`# CARDIOASSIST_TERM1_INITIAL_INDEPENDENT_AUDIT`

`## A. Evidence time and sources`: timestamp, repo URLs, exact main/branch HEAD and PR statuses, SHA confidence.

`## B. Verified as-built inventory`: tables, model provider, HTTP routes, tests, client state, file-path evidence.

`## C. Product workflow reconstruction`: doctor-confirmed visit → ID-bound code → registration → profile → assessment/AI → pending review → doctor → follow-up → patient inbox → history.

`## D. AI/scientific authorization matrix`: model artifacts, source data, candidate inference, current registry, policy gates, patient score restriction; approval required vs verified.

`## E. Security and DB critical review`: code attack surfaces, secure matching, transaction consistency, FK/cross-tenant checks, audit privacy.

`## F. Term-1 scope & implementation map`: C0–C4, P0/P1/deferred, API/ERD review and verification strategy.

`## G. Local Windows + software-team handoff`: E: workspace, real tested commands vs hypothetical ones, future curated new repo and attribution.

`## H. Risk/blocker register`: critical/major/minor, source evidence, owners and proposed next action.

`## I. Understanding/self-check`: what the new chat initially misunderstood, newly discovered gaps, what remains unverified. No fictitious execution.

`## J. Readiness verdict`: READY_TO_DIRECT_ARENA or NOT_READY_YET, with specific evidence and questions that genuinely block safe direction.

## 14. Handoff answer to the user

The correct response after receiving this handoff in a new chat is NOT 'I have everything memorized'. It is: 'I independently checked the live repo and delivered the requested Markdown audit; no code changed; please share this report with your original reviewer for cross-check before I instruct Arena.'

**Nothing in this file ratifies serving the Cleveland model, patient-facing CAD scores, clinical deployment, real national-ID collection or merge.**
