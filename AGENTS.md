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

## Current authorization: Phase 0 ONLY
- May: inspect repository, use safe read-only tool checks, research official sources, and write reports/plans **only under `docs/phase0/`** in a dedicated branch. May propose and open one PR for review.
- May not: change files elsewhere, modify source materials, add dependencies, install packages, download datasets, train models, implement features, change branches of main, merge PRs, or deploy anything.
- If an external service cannot be verified without authentication or cost, report `UNVERIFIED` or `REQUIRES_AUTHORIZATION`. Do not attempt bypasses.
- If Phase 0 report is large, commit the written report to `docs/phase0/` before the session PR is closed or merged, so it persists across sessions.

## Required Phase 0 deliverable
`docs/phase0/PHASE0_REVIEW_DRAFT.md` with feature inventory, paper audit, dataset candidacy + licenses (verified/unverified labels), precise target feasibility, zero-cost architecture alternatives, actual agent environment audit, proposed AI–backend API, research validation methodology, roadmap/acceptance gates, and blocking decision register.

Stop after the report and PR. Do not self-approve or self-merge.
