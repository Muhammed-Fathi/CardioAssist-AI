# CardioAssist AI

**Status:** Phase 1, contract-first mocks (D-043). Phase 0 and PR #3 (M1a.1 `/v1` contracts, synthetic fixtures and tests) are merged. This branch proposes the **M1a.2 FastAPI mock backend** for human review. No model has been trained, no dataset acquired, no frontend built, and no clinical performance claim is made.

**Run the mock backend locally:** [backend/README.md](backend/README.md). See [contract implementation notes / unresolved questions](backend/CONTRACT_NOTES.md) and the [M1a.3 React + Flutter handoff](docs/M1A3_INTEGRATION_HANDOFF.md).

**Purpose:** Research-oriented graduation project for Coronary Artery Disease (CAD): explainable AI, clinician dashboard, patient experience, possible wearable integrations, and a reproducible research workflow. The project is a **research prototype, not a clinically validated diagnosis or risk-prediction service**.

## Single source of truth

- **Project vision and proposed features:** `research/source_materials/project_presentation.pdf` (47 slides) plus `project_presentation_speaker_notes.md`. Presentation citations, dataset recommendations and performance claims are **not approved research evidence**.
- **Supervisor paper selection:** `research/source_materials/literature_review_status.csv` (export of the FIRST sheet of the original Excel workbook), with `Supervisor_Status` explicitly recorded; inspect original `literature_review_original.xlsx` if available.
- **Research evidence:** approved GREEN papers, verified against their originals when accessible. PINK/ORANGE are pending; RED are excluded from the selected research scope.
- **Budget:** $0, with only free-tier or existing local resources; check limits before use.
- **Implementation blueprint (proposed, 2026-10-17):** `docs/blueprint/` — master architecture/feature-traceability/roadmap/DB-API/research-gates/testing/open-decisions/status set plus ADR-001. It plans the next milestones; it authorizes nothing by itself.

## Repository organization

```
research/source_materials/  Supplied project materials, unchanged except PDF/CSV exports
research/                  Research decisions and experiments (no raw datasets)
docs/                      Scope, decisions, scientific warnings, Phase 0 reports, master blueprint (docs/blueprint/)
ai/                        AI code after Phase 0 approval
backend/                   Backend code after Phase 0 approval
frontend/patient-mobile/   Patient Flutter candidate after approval
frontend/clinician-web/    Clinician web candidate after approval
shared/contracts/          Versioned AI–backend/frontend API contracts after approval
tests/                     Unit, contract, integration, E2E tests after approval
infra/                     Local / free-tier deployments after approval
prompts/                   Governed Arena agent prompts
scripts/                   Lightweight source verification tools
```

## Current operating rules

1. Read `AGENTS.md` before executing any coding-agent task.
2. Follow the active human-authorized milestone and `docs/DECISIONS.md`. `AGENTS.md` / `prompts/arena_phase0.md` retain historical Phase-0-only text; the explicit M1a.2 authorization permits the mock backend/tests/pinned dependencies, not datasets, models, DB persistence, production auth/RBAC, UI, deployment or automatic merging.
3. Do not merge a PR without human scientific and engineering review.
4. Never commit private medical data, credentials, large datasets, model weights, or licensed data without explicit permission.
5. `main` represents **human-reviewed** baseline. On GitHub Free private repos, GitHub's paid-only enforced branch protection cannot be assumed; the team must follow the PR-only workflow voluntarily.

## Current local entry point

Use [backend/README.md](backend/README.md) for a Python-venv-only run and the combined contract/HTTP test command. Human review and an explicit next-milestone authorization precede React + Flutter implementation. The original setup history remains in `docs/REPO_SETUP.md`.
