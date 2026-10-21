# 03 — Milestone Roadmap and Dependency Graph

**Status:** Planning baseline updated for maintainer-approved D-045 (2026-10-17).
The broad sequence M1a → M1b → M2 → M3 → M4 remains, subject to the individual
research gates. PR #7 and PR #8 are both merged; A-01's technical correction
is complete. **M1b.1 Database & Persistence Foundation is the first authorized
M1b implementation slice** and is the current standalone PR. The originally
planned M1a.3 thin React/Flutter integration is **deferred/resequenced, not
cancelled and not completed**; both frontends remain preserved requirements
and thin local integration/demo clients for the team. M5 remains the **product
track** for preserved F14–F17 deliverables and still needs its own
scope/scheduling authorization.

**Research completion ≠ product completion.** M4 completes the *research
prototype* (integrated walkthrough + TRIPOD+AI write-up). Full *product*
completion additionally requires the product track (§4: F14–F17 and the
capability/device-dependent delivery items). Neither completion definition
implies clinical deployment, validation, or regulatory readiness (P-5).

**Every milestone is one scoped PR (or a small PR series) that ends with
reproducible local tests green and a named human reviewer approving before
merge** (AGENTS.md; no self-merge).

---

## 1. Milestone sequence

| ID | Name | Scope (summary) | Status |
|---|---|---|---|
| M0 | Phase 0 research & feasibility review | `docs/phase0/PHASE0_REVIEW_DRAFT.md` Rev. 3, source-integrity fix | **COMPLETE** — PR #1 merged (`0ae333f`) |
| M1a.1 | `/v1` contract-first pack | OpenAPI + JSON Schemas + MOCK registries + 31 fixtures / 38 steps; 249 contract tests after ADR-001 | **COMPLETE** — PR #3 merged (`6e677b7`); A-01 correction later merged in PR #8 |
| M1a.2 | Mock FastAPI backend | 2 existing POST endpoints + bundled openapi.json; 347 backend regressions at the PR #8 baseline; runtime idempotency/audit snapshots remain in memory | **COMPLETE** — PR #4 merged (`dbb6d18`); behavior-preserving maintenance in PR #5 and ADR-001 PR #7/#8 |
| M1a.2+ | Security/dependency cleanup | Pinned dependency security fixes; A-01 finding reported, then technically corrected in PR #7/#8 | **COMPLETE** — PR #5 merged (`6c2572c`); A-01 resolved (D-044) |
| **M1a.3** | **Thin React + Flutter integration** | One React synthetic-record form/action + one Flutter synthetic observation screen against unchanged mock contracts; client tests; network config discipline | **DEFERRED / RESEQUENCED by D-045** — not cancelled, not completed; revisit when the team schedules thin local integration/demo clients |
| **M1b.1** | **Database & Persistence Foundation** | SQLite + explicit Alembic migration; durable monitoring observation, non-null metrics and success-audit metadata through the existing POST; transaction, restart and integrity tests; no new routes | **COMPLETE** — PR #9 merged (`661876c`) |
| M1b (remaining slices) | Platform completion on mocks | Later slices: auth/RBAC (F11), consent lifecycle, patient/history/read APIs, review/reassessment (F06), full dashboard/app (F03/F04/F13), offline sync/batch (Q11), admin (F17), registries (F09), expanded durable audit/idempotency after relevant decisions | **PROPOSED / not authorized by M1b.1** |
| **M2a** | **Maintainer-Led Gate DA & Local Dataset Audit Readiness** | Gate DA suitability package merged in PR #10 (`fb928bb`); M2a adds proposed decision **D-046** (`PENDING HUMAN ACCEPTANCE`), separately reviewable proposal **D-046-EP** (`PROPOSED — NOT APPROVED`), read-only local audit toolchain (`research/audit/`), synthetic fixture tests (`tests/audit/`), and Windows PowerShell handoff (`docs/research/gate-da/09_m2a_windows_local_audit_handoff.md`) | **TOOLCHAIN IMPLEMENTED + TESTED ON SYNTHETIC FIXTURES; GOVERNANCE D-046 PENDING HUMAN ACCEPTANCE** |
| M2 | Gate DA — data access & read-only audit execution | Authorized local-only acquisition of named datasets on Windows after D-046 approval; §R2-4.4 checklists; coding/missingness/duplicate/overlap/availability audits; **"no fitting occurred" certification** | RESEARCH-GATED (needs human acceptance of D-046 / P-2) |
| M3 | Gate PT — frozen protocol + first real models | Supervisor-approved frozen protocol; Strategy-A benchmarks; Strategy-B external evaluation; cross-fitted calibration; **real TreeSHAP/LIME** + stability; first real model behind **backward-compatible `/v1` behavior with the existing mock regression fixtures preserved and green** (IC-3); separately approved, versioned **real clinical feature schemas and model registries** may be added after Gate DA/PT — a real model must **not** depend on provisional mock feature identifiers (`mock_clinical_v1/v2`, `mock_model_*`) | RESEARCH-GATED (needs P-3, after M2) |
| M4 | Integrated **research prototype** + write-up (**not** product completion, see above) | IC-4 walkthrough; TRIPOD+AI manuscript; replication package; optional time-boxed FHIR export (F08) and Health Connect capability/device spike (F05: supported-device plan + **simulator fallback deliverable**); PostgreSQL-path validation; optional disposable hosted demo | RESEARCH/REVIEW-GATED |
| M5 | **Product track** — required product-vision surfaces | Lab-report upload + OCR (F14, required), extraction verification (F15, required), research-safe content/assistant (F16, clinician-gated), admin console (F17), notifications delivery polish, second disease-module prep (F09) | **PROPOSED — scheduling authorization pending; deliverables are required vision, not optional** |

Workstream A (research: M2/M3/M4 gates) remains independently gated and
runs **in parallel** with platform work. M1b.1 is the current database slice;
M1a.3 is deferred/resequenced and may later supply thin client integration
checks. Dataset work never blocks platform work and vice versa.

## 2. Dependency graph

````
                        ┌──────────────────────────────────────────────┐
                        │ P-1 target · P-2 Gate DA · P-3 Gate PT ·     │
                        │ P-4 clinician copy · P-6 wearables (human    │
                        │ gates — parallel, each unlocks its dependents)│
                        └───────┬──────────────┬───────────────┬───────┘
                                │              │               │
 M0 Phase 0 ──► M1a.1 ──► M1a.2 ──► M1a.2+ ──► M1b.1 ──► later M1b ──┬──► M5
 (COMPLETE)     contracts  mock API   cleanup   persistence   platform    (product track)
                                │                    │              │
                                │                    │              ├── F11 auth/RBAC ──► F17 admin
                                │                    │              ├── consent + durable audit expansion
                                │                    │              ├── F06 review/reassessment
                                │                    │              ├── F13 records/history APIs
                                │                    │              └── Q11 batch sync (contract-first)
                                │                    │
                                └── M1a.3 thin local React/Flutter demo integration
                                    DEFERRED/RESEQUENCED by D-045; not cancelled
                                │
        P-2 (Gate DA) ──► M2 data audit ──► P-3 (Gate PT) ──► M3 real models
              │                                    │            │
              └── §R2-4.4 checklists ──────────────┘            ├── real SHAP/LIME (F02)
                                                               ├── calibration + model cards
                                                               ├── /v1 behavior + mock regression
                                                               │    fixtures preserved (IC-3)
                                                               └── versioned real feature schemas
                                                                    + model registries (approved
                                                                    post Gate DA/PT; never the
                                                                    provisional mock identifiers)
                                                                        │
        D-020 ──► F08 FHIR export (M4 optional)                        ▼
        P-6   ──► F05 Health Connect (M4: capability/device    M4 write-up (IC-4, TRIPOD+AI)
                  plan + required simulator fallback)
        D-025 ──► literature verification (before any novelty claim, M4)
````

Hard edges worth restating:

- **No model fitting of any kind before Gate PT** (P-3), which cannot open
  before Gate DA (P-2) completes its read-only audit (Phase 0 §F-3).
- **M3 preserves backward-compatible `/v1` behavior and the existing mock
  regression fixtures** (they stay green unchanged). Separately approved,
  versioned **real clinical feature schemas and model registries** may be
  added after Gate DA/PT — a real model must never depend on provisional
  mock feature identifiers. Contract changes for research convenience are
  out of scope; use the ADR process if unavoidable.
- **M1b read/history/review/consent APIs are new contract surface** → each
  still needs contract-first approval, schemas, fixtures and tests before
  server code. This authorized M1b.1 slice avoids all new routes. D-045
  re-sequences the earlier proposed "M1b.1 contracts first" step; it does not
  waive that requirement for future APIs.
- **The M1a.3 integration plan remains preserved but deferred/resequenced**
  under D-045; it is not complete or cancelled. React/Flutter remain thin
  local demo/integration clients, not the maintainer's primary deliverables.
- **M5 items never block M1b.1/M2/M3/M4** (separate product track, §4), but
  they remain required product-vision deliverables — unscheduled ≠ optional.

## 3. Milestone exit criteria (acceptance gates)

Full test commands and per-milestone matrices live in
[06_TESTING_AND_ACCEPTANCE_MATRIX.md](06_TESTING_AND_ACCEPTANCE_MATRIX.md).
The universal exit gate for **every** milestone PR:

1. All documented local test commands green (`-W error`, pinned deps).
2. `python scripts/verify_sources.py` passes (4/4 hashes) whenever the
   milestone could touch source materials — it must never touch them.
3. No research-source file or SHA256 manifest entry modified.
4. Feature IDs + milestone criteria cited in the PR description.
5. Safety-labelling evidence: screenshots/snapshots of mandatory wording
   where UI exists; explicit statement of what is MOCK vs real.
6. Human review (scientific and/or engineering as applicable) recorded on
   the PR; **no self-merge**.

### M1b.1 — Database & Persistence Foundation exit criteria (current slice)

- SQLite default with configurable `CARDIOASSIST_DATABASE_URL`, explicit
  Alembic migrations and fresh/re-upgrade/schema-consistency checks.
- Durable `monitoring_observation`, `monitoring_metric` and success `audit_event`
  rows from the existing monitoring POST only; no new routes or changed
  contract fixture bodies/statuses.
- Accepted observation, non-null metrics and one metadata-only audit row
  commit/rollback together; foreign keys, useful indexes and uniqueness are
  tested. Successful writes survive app restart/reopen.
- 24-hour idempotency runtime behavior remains process-local; Q8 and its
  durable store-of-record decision remain open. Consent/patient references are
  stored opaquely without inventing master records or FK semantics.
- SQLite tests only; PostgreSQL compatibility is **UNVERIFIED**. No auth/RBAC,
  patient/history API, frontend, AI training or dataset work in this slice.

### M1a.3 (deferred/resequenced; not cancelled) — eventual thin-client criteria
(from `docs/M1A3_INTEGRATION_HANDOFF.md`)

- React thin path + Flutter thin path built with pinned toolchains; all
  backend/contract tests + React client/component tests + Flutter
  client/widget tests green.
- Demonstrations: React → synthetic prediction → retry with same audit id;
  Flutter → monitoring → retry with same observation id; changed payload
  under a used key → 409; wearable source → CAD endpoint → 422 and no score;
  monitoring does not increase the inference counter.
- Mandatory rendering: target/disclaimer/status copy, mock-calibrated cohort
  context, log-odds SHAP separation, no `%`, no LIME panel.
- Network discipline: relative `/v1` URLs in browser code; Flutter
  `API_BASE_URL` via `--dart-define`; no `localhost` from browser to other
  services; no broad credentialed CORS.
- Emulator/physical-device evidence or explicit UNVERIFIED limits recorded.
- Open items B-01–B-04, G-02, X-01 explicitly carried (not silently
  changed); A-01's technical correction is complete (D-044 / PR #8).

### M1b (remaining slices) — exit criteria (PROPOSED; separate authorization)

- Extend the M1b.1 SQLite foundation by independently reviewed, contract-first
  slices; preserve wire behavior unless an ADR authorizes a change. In-memory
  idempotency/error-audit limitations remain until their policy is reviewed.
- Auth/RBAC role-matrix tests and consent lifecycle only after a separate
  authorization; durable append-only audit coverage expands with each accepted
  write. IC-2 remains future work.
- Clinician/conservative-copy review of all user-facing text (P-4/D-016
  outcome recorded) when those surfaces are implemented.
- Offline→sync test (emulator + physical device or recorded UNVERIFIED);
  batch-ingestion contract approved first.

### M2 — exit criteria (draft)

- Authorized datasets only (named in the Gate DA authorization); acquired
  out-of-git; license + hash snapshots recorded.
- Completed §R2-4.4 checklist per dataset + duplicate/overlap audit +
  feature-availability documentation (incl. `thal`/`oldpeak` rulings per
  §F-1).
- **Certification merged: "no model fitting, selection, tuning, or
  evaluation occurred."**

### M3 — exit criteria (draft)

- Frozen protocol signed (Gate PT) before any fitting.
- Nested-CV benchmark results (with CIs, leakage checklist signed) in
  `research/experiments/`; negative results reported.
- Real SHAP (log-odds sum-check) + LIME (with real fidelity) explanations;
  explanation stability documented.
- Fixture suite + HTTP suite re-green **unchanged** against the real model
  backend (backward-compatible `/v1`; real clinical feature schemas and
  model registries separately approved and versioned — never provisional
  mock identifiers; IC-3); `validation_status` lifecycle enforced; UI
  wording re-snapshotted.

### M4 — exit criteria (draft)

- IC-4 walkthrough recorded; TRIPOD+AI checklist completed at manuscript
  stage; replication package assembled (code + configs, no restricted data);
  supervisor approval; no novelty claim without D-025 verification.

## 4. Product track (M5) — required product-vision deliverables

**Product completion is a separate, explicit definition from research
completion (§ intro).** The items below are **required product-vision
deliverables** (not optional extras): their implementation is subject to
implementation-readiness and safety approvals, and their scheduling needs
maintainer authorization — that pending scheduling does not demote them.

| Item | Deliverable | Readiness/safety conditions |
|---|---|---|
| F14 (required) | Lab-report image/PDF upload + local OCR extraction | $0 local OCR engine decision; PHI/privacy design (synthetic sample documents only until approved); EXT mockups |
| F15 (required) | Extraction editing, provenance, confirmation, clinician verification | Clinician verification workflow + 05 §2.1 eligibility boundary (verification ≠ model eligibility); P-4 copy review |
| F16 (clinician-gated) | Research-safe recommendations / clinical-assistant surfaces | Named clinician content approval (D-016/D-026); no model-driven advice; citations + refusal rules |
| F17 | Admin console (beyond M1b basics) | RBAC + audit |
| F09 prep | Second disease-module groundwork | Separate scientific approval to activate any module |
| F05 (M4 spike, carried) | **Health Connect: capability- and device-dependent delivery plan** | Supported-device/capability check recorded; adapter only on a qualifying device; **simulated adapter is the always-available fallback deliverable** when no qualifying device exists |

Scheduling proposal (not a commitment): start **after M1b** in parallel with
M2/M3, internal order F17 basics → F14 → F15 → F16 (last — heaviest
clinician gates). Each sub-item is its own scoped PR with the universal exit
gate. Until the maintainer authorizes M5 scheduling, these rows remain
PROPOSED in the traceability matrix and nothing in M1a.3/M1b depends on
them — but M4 alone never closes the product vision.

## 5. Integration checkpoints (from Phase 0 §R2-7.5, unchanged)

| Checkpoint | Proves | Target milestone |
|---|---|---|
| IC-1 | End-to-end on fixtures: clinician reviews mock prediction + patient submits monitoring + audit shows both | M1a.3 when resumed (deferred/resequenced by D-045) |
| IC-2 | Consent, RBAC, reassessment-validity behavior on mocks | M1b |
| IC-3 | First real model behind **backward-compatible `/v1` behavior**; existing mock regression fixtures preserved and green unchanged; explanation checks green; real model served on a separately approved, versioned real feature schema + model registry (never provisional mock identifiers) | M3 |
| IC-4 | Full research-prototype walkthrough + manuscript draft | M4 |

## 6. Sequencing risks (delivery)

| Risk | Control |
|---|---|
| M1b silently expands into M5 scope | Scope list in §1 is exhaustive for M1b; anything else goes to M5 or a new decision |
| Clients tighten Track-B scalar types or fabricate LIME (called out in handoff §1.2) | Client test lists in [06](06_TESTING_AND_ACCEPTANCE_MATRIX.md) include negative assertions |
| Research pressure to bypass Gate DA/PT | Gates are human sign-offs named in `docs/DECISIONS.md`; agent must refuse and record the request |
| Contract drift while building future M1b read/consent/review APIs | Contract-first approval + ADR process + fixture suite are required before server implementation; this M1b.1 slice adds no route |
