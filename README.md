# CardioAssist AI

**Status:** Phase 0 — Discovery & Scientific Feasibility. No model has been trained, no backend/front-end implementation has been approved, and no clinical performance claim is verified.

**Purpose:** Research-oriented graduation project for Coronary Artery Disease (CAD): explainable AI, clinician dashboard, patient experience, possible wearable integrations, and a reproducible research workflow. The project is a **research prototype, not a clinically validated diagnosis or risk-prediction service**.

## Single source of truth

- **Project vision and proposed features:** `research/source_materials/project_presentation.pdf` (47 slides) plus `project_presentation_speaker_notes.md`. Presentation citations, dataset recommendations and performance claims are **not approved research evidence**.
- **Supervisor paper selection:** `research/source_materials/literature_review_status.csv` (export of the FIRST sheet of the original Excel workbook), with `Supervisor_Status` explicitly recorded; inspect original `literature_review_original.xlsx` if available.
- **Research evidence:** approved GREEN papers, verified against their originals when accessible. PINK/ORANGE are pending; RED are excluded from the selected research scope.
- **Budget:** $0, with only free-tier or existing local resources; check limits before use.

## Repository organization

```
research/source_materials/  Supplied project materials, unchanged except PDF/CSV exports
research/                  Research decisions and experiments (no raw datasets)
docs/                      Scope, decisions, scientific warnings, Phase 0 reports
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
2. Start with `prompts/arena_phase0.md` — the agent is permitted to write only Phase 0 **documentation drafts on its own branch**, then open a PR; no implementation, data download, package installs, or deployment.
3. Do not merge a PR without human scientific and engineering review.
4. Never commit private medical data, credentials, large datasets, model weights, or licensed data without explicit permission.
5. `main` represents **human-reviewed** baseline. On GitHub Free private repos, GitHub's paid-only enforced branch protection cannot be assumed; the team must follow the PR-only workflow voluntarily.

## First step

Read `docs/REPO_SETUP.md`, publish this starter as a *private* GitHub repository, connect it to Arena Agent Mode, then use the supplied Phase 0 prompt.
