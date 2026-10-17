# 03 — Milestone Roadmap and Dependency Graph

**Status:** PROPOSED planning baseline (documentation only), 2026-10-17.
Sequence M1a → M1b → M2 → M3 → M4 is maintainer-approved (D-029, Phase 0
§R2-7.6/§F-5). M0/M1a.x are complete (merged). M1a.3 is the **next
feature-development milestone** and requires explicit maintainer
authorization before it starts (its plan is
`docs/M1A3_INTEGRATION_HANDOFF.md`). M5 is a proposed extension bucket for
preserved vision scope (F14–F17) not covered by M1a–M4 and needs its own
scope authorization.

**Every milestone is one scoped PR (or a small PR series) that ends with
reproducible local tests green and a named human reviewer approving before
merge** (AGENTS.md; no self-merge).

---

## 1. Milestone sequence

| ID | Name | Scope (summary) | Status |
|---|---|---|---|
| M0 | Phase 0 research & feasibility review | `docs/phase0/PHASE0_REVIEW_DRAFT.md` Rev. 3, source-integrity fix | **COMPLETE** — PR #1 merged (`0ae333f`) |
| M1a.1 | `/v1` contract-first pack | OpenAPI + JSON Schemas + MOCK registries + 30 fixtures + 136 contract tests | **COMPLETE** — PR #3 merged (`6e677b7`) |
| M1a.2 | Mock FastAPI backend | 2 endpoints + bundled openapi.json, idempotency/audit in memory, 234 HTTP tests | **COMPLETE** — PR #4 merged (`dbb6d18`) |
| M1a.2+ | Security/dependency cleanup | Pinned dep security fixes (anyio/starlette/pytest), A-01 finding reported | **COMPLETE** — PR #5 merged (`6c2572c`) |
| **M1a.3** | **Thin React + Flutter integration** | One React synthetic-record form/action + one Flutter synthetic observation screen vs the unchanged mock contract; client tests; network config discipline | **NEXT — plan approved as handoff doc; awaiting explicit milestone authorization** |
| M1b | Platform completion on mocks | Persistence (SQLite, F18), auth/RBAC (F11), consent lifecycle + durable audit (F07), history/read APIs, review + reassessment mechanics (F06), full dashboard + full patient app (F03/F04/F13 manual entry), offline sync + batch ingestion (Q11), basic admin (F17), registry scaffolding (F09) | PROPOSED |
| M2 | Gate DA — data access & read-only audit | Authorized local-only acquisition of named datasets; §R2-4.4 checklists; coding/missingness/duplicate/overlap/availability audits; **"no fitting occurred" certification** | RESEARCH-GATED (needs P-2) |
| M3 | Gate PT — frozen protocol + first real models | Supervisor-approved frozen protocol; Strategy-A benchmarks; Strategy-B external evaluation; cross-fitted calibration; **real TreeSHAP/LIME** + stability; real model behind the unchanged contract (IC-3); fixture suite re-green | RESEARCH-GATED (needs P-3, after M2) |
| M4 | Integrated research prototype + write-up | IC-4 walkthrough; TRIPOD+AI manuscript; replication package; optional time-boxed FHIR export (F08) and Health Connect spike (F05); PostgreSQL-path validation; optional disposable hosted demo | RESEARCH/REVIEW-GATED |
| M5 | Preserved product-surface extension (PROPOSED bucket) | Lab-report upload + OCR (F14), extraction verification (F15), research-safe content/assistant (F16), admin console (F17), notifications delivery polish, second disease-module prep (F09) | **PROPOSED — not yet authorized; needs explicit scope decision** |

Workstream A (research: M2/M3/M4 gates) runs **in parallel** with platform
work (M1a.3/M1b/M5) under its own approvals (Phase 0 §R2-7). Dataset work
never blocks platform work and vice versa.

## 2. Dependency graph

````
                        ┌──────────────────────────────────────────────┐
                        │ P-1 target · P-2 Gate DA · P-3 Gate PT ·     │
                        │ P-4 clinician copy · P-6 wearables (human    │
                        │ gates — parallel, each unlocks its dependents)│
                        └───────┬──────────────┬───────────────┬───────┘
                                │              │               │
 M0 Phase 0 ──► M1a.1 ──► M1a.2 ──► M1a.2+ ──► M1a.3 ──► M1b ──┬──► M5 (F14–F17)
 (COMPLETE)     contracts  mock API   cleanup   thin UIs   platform   (proposed)
                                │                  │         │
                                │                  │         ├── F11 auth/RBAC ──► F17 admin
                                │                  │         ├── F18 persistence ──► F07 durable audit/consent
                                │                  │         ├── F06 review/reassessment ◄── F11, F07
                                │                  │         ├── F13 inputs ◄── F11, F18
                                │                  │         └── Q11 batch sync ◄── F04 offline queue
                                │                  │
                                │                  └── client tests pin F01/F02/F05 rendering rules
                                │                        (guards M3 UI re-snapshot, IC-3)
                                │
        P-2 (Gate DA) ──► M2 data audit ──► P-3 (Gate PT) ──► M3 real models
              │                                    │            │
              └── §R2-4.4 checklists ──────────────┘            ├── real SHAP/LIME (F02)
                                                               ├── calibration + model cards
                                                               └── unchanged /v1 contract (IC-3)
                                                                        │
        D-020 ──► F08 FHIR export (M4 optional)                        ▼
        P-6   ──► F05 Health Connect spike (M4 optional)      M4 write-up (IC-4, TRIPOD+AI)
        D-025 ──► literature verification (before any novelty claim, M4)
````

Hard edges worth restating:

- **No model fitting of any kind before Gate PT** (P-3), which cannot open
  before Gate DA (P-2) completes its read-only audit (Phase 0 §F-3).
- **M3 serves real models only through the unchanged M1a contract** —
  contract changes for research convenience are out of scope; use ADR
  process if unavoidable.
- **M1b read/history/review APIs are new contract surface** → each needs the
  same contract-first treatment (schema + fixtures + tests before server),
  i.e. an "M1b.1 contracts" slice inside M1b.
- **M5 features never block M1a.3/M1b/M2/M3/M4.** They are preserved vision,
  scheduled only after explicit authorization.

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

### M1a.3 (next) — concrete exit criteria (from `docs/M1A3_INTEGRATION_HANDOFF.md`)

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
- Open items B-01–B-04, A-01, G-02, X-01 explicitly carried (not silently
  changed).

### M1b — exit criteria (draft, to be ratified at M1b authorization)

- SQLite persistence with migrations; full suite green; in-memory
  limitations removed **without wire-behavior changes** (fixture suite
  unchanged and green).
- Auth/RBAC role-matrix tests; consent lifecycle + durable append-only audit
  (one event per accepted write); IC-2 checkpoint (consent, RBAC,
  reassessment-validity on mocks) demonstrated.
- Clinician/conservative-copy review of all user-facing text (P-4/D-016
  outcome recorded).
- Offline→sync test (emulator + physical device or recorded UNVERIFIED);
  batch ingestion contract approved first.

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
- Fixture suite + HTTP suite re-green against the real model backend
  (IC-3); `validation_status` lifecycle enforced; UI wording re-snapshotted.

### M4 — exit criteria (draft)

- IC-4 walkthrough recorded; TRIPOD+AI checklist completed at manuscript
  stage; replication package assembled (code + configs, no restricted data);
  supervisor approval; no novelty claim without D-025 verification.

## 4. M5 bucket — preserved scope awaiting authorization

F14 (lab OCR), F15 (extraction verification), F16 (research-safe
recommendations/assistant), F17 console, F09 second-module prep. Scheduling
proposal (not a commitment): start **after M1b** in parallel with M2/M3, in
this internal order — F17 basics → F14 → F15 → F16 (last, because it has the
heaviest clinician gates). Each sub-item is its own scoped PR with the
universal exit gate. Until the maintainer authorizes M5, these rows remain
PROPOSED in the traceability matrix and nothing in M1a.3/M1b depends on them.

## 5. Integration checkpoints (from Phase 0 §R2-7.5, unchanged)

| Checkpoint | Proves | Target milestone |
|---|---|---|
| IC-1 | End-to-end on fixtures: clinician reviews mock prediction + patient submits monitoring + audit shows both | M1a.3 |
| IC-2 | Consent, RBAC, reassessment-validity behavior on mocks | M1b |
| IC-3 | First real model behind the unchanged contract; fixture suite + explanation checks green | M3 |
| IC-4 | Full research-prototype walkthrough + manuscript draft | M4 |

## 6. Sequencing risks (delivery)

| Risk | Control |
|---|---|
| M1b silently expands into M5 scope | Scope list in §1 is exhaustive for M1b; anything else goes to M5 or a new decision |
| Clients tighten Track-B scalar types or fabricate LIME (called out in handoff §1.2) | Client test lists in [06](06_TESTING_AND_ACCEPTANCE_MATRIX.md) include negative assertions |
| Research pressure to bypass Gate DA/PT | Gates are human sign-offs named in `docs/DECISIONS.md`; agent must refuse and record the request |
| Contract drift while building M1b read APIs | "M1b.1 contracts first" rule (§2); ADR process; fixture suite is the merge gate |
