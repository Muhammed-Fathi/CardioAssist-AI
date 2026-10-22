# CardioAssist AI

**Status update (2026-10-22, M2a):** D-046 was human-ratified for **local
read-only audit only**; see [`docs/DECISIONS.md`](docs/DECISIONS.md). The
maintainer reported successful local audits of DA-A1 (UCI-412) and DA-B1
(UCI-411), including 303/303 shared-column positional matches and an
unresolved 1/303 artery/Cath consistency flag. Their original workbooks,
manifests and patient-level records remain local and Git-ignored, **not
reproduced or uploaded on GitHub**. Evidence, methods, conservative decisions,
and limitations are recorded in
[`docs/research/gate-da/10_m2a_uci412_uci411_evidence_and_decisions.md`](docs/research/gate-da/10_m2a_uci412_uci411_evidence_and_decisions.md).
The prior 2026-10-21 snapshot in
[`docs/blueprint/08_IMPLEMENTATION_STATUS_VS_FUTURE_SCOPE.md`](docs/blueprint/08_IMPLEMENTATION_STATUS_VS_FUTURE_SCOPE.md)
is historical, not an update of these local audit results. **Gate PT (P-3)
remains CLOSED, supervisor sign-off is not claimed, no model fitting or clinical
performance evidence exists.** React/Flutter M1a.3 is still deferred,
not cancelled ([D-045](docs/DECISIONS.md)).

**Run the synthetic mock backend and SQLite persistence locally:**
[backend/README.md](backend/README.md). See
[contract implementation notes and open questions](backend/CONTRACT_NOTES.md)
and the preserved [M1a.3 React + Flutter handoff plan](docs/M1A3_INTEGRATION_HANDOFF.md).
M1b.1 adds no `/v1` endpoints and does not change existing contracts or fixture
bodies.

**Purpose:** Research-oriented graduation project for Coronary Artery Disease
(CAD): explainable AI, clinician dashboard, patient experience, possible
wearable integrations, and a reproducible research workflow. The project is a
**research prototype, not a clinically validated diagnosis or risk-prediction
service**.

## Single source of truth

- **Project vision and proposed features:** `research/source_materials/project_presentation.pdf` (47 slides) plus `project_presentation_speaker_notes.md`. Presentation citations, dataset recommendations and performance claims are **not approved research evidence**.
- **Supervisor paper selection:** `research/source_materials/literature_review_status.csv` (export of the FIRST sheet of the original Excel workbook), with `Supervisor_Status` explicitly recorded; inspect original `literature_review_original.xlsx` if available.
- **Research evidence:** approved GREEN papers, verified against their originals when accessible. PINK/ORANGE are pending; RED are excluded from the selected research scope. Current integrity target/results are recorded in `docs/blueprint/08_IMPLEMENTATION_STATUS_VS_FUTURE_SCOPE.md`.
- **Budget:** $0 mandatory cost; only existing local resources or genuinely free services, with limits checked before use. No card-required trials.
- **Implementation blueprint:** `docs/blueprint/` contains architecture, traceability, roadmap, database/API design, research gates, acceptance matrix, open decisions, current status, and ADR-001. It is planning/status documentation, not blanket authorization. D-045 authorizes M1b.1 only.

## Repository organization

```
research/source_materials/  Supplied project materials; do not alter or acquire datasets without authorization
research/                  Research decisions and experiments (no raw patient-level datasets)
docs/                      Scope, decisions, scientific warnings, Phase 0 report, and blueprint/status docs
ai/                        Future AI implementation; gated by research approvals
backend/                   FastAPI synthetic mock backend and M1b.1 SQLite persistence
frontend/patient-mobile/   Flutter candidate; thin local demo/integration client, M1a.3 deferred
frontend/clinician-web/    React candidate; thin local demo/integration client, M1a.3 deferred
shared/contracts/          Versioned API contracts, schemas, registries and fixtures
tests/                     Contract, backend and persistence tests
infra/                     Future local/free-tier deployments, separately authorized
prompts/                   Governed Arena agent prompts (historical Phase 0 prompt is not current authorization)
scripts/                   Lightweight source verification tools
```

## Current operating rules

1. Read `AGENTS.md`, `docs/DECISIONS.md`, and the applicable handoff/test docs before work. The active maintainer instruction and D-045 supersede the original Phase-0-only restrictions for the explicitly bounded M1b.1 slice only.
2. D-045 priority is: **(1) genuine, reproducible CAD AI research and inference; (2) complete, integration-ready FastAPI backend; (3) durable, tested database.** React and Flutter remain thin local integration/demo clients. M1a.3 is deferred/resequenced, not cancelled or completed.
3. M1b.1 is SQLite-first, uses explicit Alembic migrations, a configurable database path and a repository/service boundary, and integrates only with the existing monitoring write. Preserve `/v1` contracts, fixture pack, validation order/errors, Track A/Track B separation, mock CAD scores and response formats. Do not invent endpoints.
4. Patient and consent references remain opaque; use synthetic/demo data only and fail closed for invalid references/inconsistent database state. Runtime idempotency remains process-local; Q8's durable-store policy remains unresolved. Audit is append-only by application design. Do not claim PostgreSQL parity without PostgreSQL tests or SQLite GRANT/REVOKE controls.
5. No paid APIs/hosting/compute, card-required trials, real patient data, datasets, model training, clinical integration, auth/RBAC, patient/history/review APIs, wearables, OCR, assistant, notifications, or unapproved frontend/infrastructure work. D-045 does not waive any research, data, or clinical gate, and does not change the `/v1` contract.
6. Never commit database files, credentials, model weights, large datasets, or licensed data without explicit authorization. Do not merge a PR or start another milestone without separate human authorization.
7. Report exact local check results separately from GitHub CI and other unverified results. Keep **IMPLEMENTED**, **TESTED**, **PROPOSED**, and **UNVERIFIED** distinct.

## Local entry point

Use [backend/README.md](backend/README.md) for Python virtual-environment
setup, SQLite migrations, starting/restarting the app, migration consistency
checks, tests, and Windows PowerShell cleanup instructions. The repository
contains only synthetic fixtures/demo examples; do not use real patient data.

The original setup history remains in `docs/REPO_SETUP.md`. Review the
[testing and acceptance matrix](docs/blueprint/06_TESTING_AND_ACCEPTANCE_MATRIX.md)
and [open decisions](docs/blueprint/07_OPEN_DECISIONS_RISKS_ASSUMPTIONS.md)
when evaluating scope or status.
