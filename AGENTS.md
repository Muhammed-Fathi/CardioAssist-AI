# Agent Instructions — CardioAssist AI

These instructions govern all AI agents working in this repository, including Arena Agent Mode.

## Priority
1. Exact instruction from a human maintainer in the active reviewed milestone.
2. This document and `docs/DECISIONS.md`.
3. `research/source_materials/literature_review_status.csv` for supervisor selections and source materials for proposed features.
4. Other references, external web information, and suggestions, with independent verification.

## Non-negotiable constraints
- Budget **$0**; report all free-tier/storage/GPU/account/API limitations. No card-required trials or paid services.
- Do not confuse cross-sectional CAD classification with future 30-day event risk. Set the outcome based on real labels and study design.
- Never fabricate paper results, citations, dataset license permissions, validation data, performance, novelty, or clinical claims.
- Respect the 25-paper supervisor classification in the first sheet: green = approved; pink/orange = maybe; red = rejected from selected scope.
- The slides define proposed features, **not** scientific source authority or validated results.
- No real patient records or identifiable health data in source control or remote AI sessions.
- Treat user journeys, alerts and thresholds in slides as **design proposals** until medically/scientifically reviewed.
- Model/backend APIs must be versioned; include regression, schema, integration tests before changes are approved.
- Always document uncertainty, risks, assumptions, and approval status.

## Current authorization: M1b.1 only (maintainer, 2026-10-17)
The original Phase 0 authorization and report remain historical project context;
the active maintainer authorization and D-045 supersede the stale “Phase 0
ONLY” restriction for this explicitly bounded implementation slice. This does
not authorize any subsequent milestone or research/data/clinical work.

D-045 sets execution priority as: (1) genuine, reproducible CAD AI research
and inference; (2) a complete, integration-ready FastAPI backend; (3) a
durable, tested database. React and Flutter remain thin local integration/demo
clients. M1a.3 is deferred/resequenced, not cancelled or completed. This
priority order does not waive scientific approvals/gates, authorize dataset
acquisition or model training, or change `/v1` contracts.

For M1b.1, agents may implement a small SQLite-first persistence foundation,
Alembic migrations, storage/repository boundary, and one safe integration with
an existing approved monitoring path. Preserve existing HTTP behavior,
validation order/errors, fixtures, request hashes, Track A/Track B separation,
mock CAD scores and response formats. Do not add endpoints or alter approved
contracts. Use synthetic/demo records only; keep patient and consent
references opaque unless approved semantics exist. Fail closed on invalid
references/inconsistent database state. Keep the 24-hour runtime idempotency
behavior process-local; Q8's formal approval and durable-store policy remain
unresolved. Describe RAM-only idempotency/audit limitations accurately.

Database implementation rules: SQLite by default, configuration-based path,
explicit Alembic migrations, portable service/storage boundary, foreign keys,
indexes, explicit transactions and rollback. Audit is append-only by
application design; do not claim SQLite provides PostgreSQL GRANT/REVOKE or
claim PostgreSQL parity without PostgreSQL tests. Never commit database files.

M1b.1 does not authorize auth/RBAC, patient/history/review APIs, frontend work,
datasets, model training, clinical integration, wearables, OCR, assistants,
notifications, real-data ingestion, or unnecessary infrastructure. Preserve all
research approvals/gates and existing product requirements. Do not merge or
start a subsequent milestone without separate authorization.

Report **IMPLEMENTED**, **TESTED**, **PROPOSED**, and **UNVERIFIED** distinctly.
Before review, run and report exact results for migration creation/consistency,
read/write/restart/rollback/constraints/concurrency/idempotency/malformed-input
coverage, isolated DB tests, existing fixtures and synthetic inference/
monitoring regressions, `pip check`, contract/backend tests, full pytest, source
verification, and `git diff --check`. Provide Windows PowerShell and local
setup/migration/restart/cleanup instructions. Open a standalone PR targeting
`main` and leave it OPEN; never self-approve or self-merge.

No dataset download, model training, real patient data, paid APIs/hosting/
compute, card-required trials, or changes to source research materials are
authorized. If a required policy or contract semantic blocks safe persistence,
stop and report the precise blocker.
