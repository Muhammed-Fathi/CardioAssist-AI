# AI-10.1 — Frozen external-site engineering rehearsal (fabricated fixtures only)

**Status:** Implementation under review, not accepted until GitHub CI and maintainer's native Windows post-merge validation. **Evidence:** `SYNTHETIC_TRANSPORT_TEST_NOT_EXTERNAL_VALIDATION`.

## Scope and reuse

This PR does **not** conduct clinical external validation on Hungary or any other real cohort. It composes the existing, already-reviewed `ai.training.train_research_model`, `evaluate_locked_external_cohort`, `ExternalEvaluationLedger` and `ai.research_routes` synthetic DA-A2 resting-panel fixtures. No independent metrics engine, new provider, dataset ingestion, frozen D-047/M3a plan change, original model load, or real-source access is introduced.

- A version-bound, immutable `SyntheticLockedSitePlan` binds the DA-A2 five-field panel, SHA-256, source-specific endpoint, size, seed, and synthetic-only plan reference.
- Synthetic development records and fake external records are generated independently; the second fixture is given an invented age and resting-BP shift. The model/preprocessor/calibrator are fitted only to synthetic development data, then used frozen against the invented external fixture.
- The existing protected one-shot ledger consumes one external synthetic test set, with reserved/completed/failed transitions and duplicate/conflict refusal. A fresh report excludes local paths and ledger reservation IDs. Internal checksums are integrity aids, **not signatures or medical validation**.
- Explicit fake identity checks detect synthetic duplicates/overlap, but **cannot establish independence between real people**.
- `INSUFFICIENT_EVIDENCE` is a valid, non-consumptive result when an invented cohort or a class has insufficient observations.
- A failed prior reservation requires the *existing* ledger's explicitly reviewed recovery path; no implicit retry or special exception in AI-10.1.

## Usage on local Windows (only after reviewed PR-head CI)

Open **PowerShell 5.1 in a new clean detached worktree at the reviewed SHA** and use the existing verified external Python 3.12 environment. The following is an **example**, not evidence it has been executed. Pick two new filenames under a **fresh private NTFS directory outside the repository**. Never use the protected real-dataset folder or an existing ledger.

```powershell
$Python = 'C:\Users\wifi\AppData\Local\CAI12-manual-641458d68d14\venv\Scripts\python.exe'
$OutputRoot = Join-Path $env:LOCALAPPDATA ('CAI10-Synthetic-' + [guid]::NewGuid().ToString('N').Substring(0,12))
$Ledger = Join-Path $OutputRoot 'ledger' 
$ReportDir = Join-Path $OutputRoot 'report'
& $Python scripts/run_ai10_synthetic_locked_site.py --ledger (Join-Path $Ledger 'one-shot.json') --output (Join-Path $ReportDir 'result.json')
if ($LASTEXITCODE -ne 0) { throw 'AI-10.1 synthetic rehearsal failed' }
& $Python -m pytest -W error -q -ra --tb=short tests/experiments/test_ai10_synthetic_transport.py
if ($LASTEXITCODE -ne 0) { throw 'AI-10.1 regression failed' }
```

**The CLI refuses** paths inside the current checkout, existing files and reparse-point parents. It writes output as a new private file. It does not accept a real cohort, patient file, or a feature input path.

## Scientific status and known limits

- All inputs, patients, outcomes, cohort identities and site differences are **fabricated**. The generated study does not test Hungary's missingness, geography, historical case mix, target equivalence, person overlap, or generalizability.
- Target remains source-defined cross-sectional historical CAD presence, **not** future heart attack risk or a treatment threshold.
- The frozen binding digest checks metadata, preprocessor and calibrator state; it is not an authenticated digest of the estimator's fitted weights.
- Reusing `ExternalEvaluationLedger` supplies an engineering single-shot guard. It does **not** confer authorization to use a real source or prove external scientific independence.
- Real Hungary remains a **conditional locked candidate, not ready**, as recorded in [M2f](../gate-pt/07_m2f_hungary_scientific_decision_and_conditional_protocol.md), [Gate PT 15](../gate-pt/15_scientific_evidence_resolution_and_development_route_REVIEW_DRAFT.md), and [Master Roadmap](../CARDIOASSIST_AI_MASTER_COMPLETION_PLAN.md).
- Existing [D-047 Cleveland](../gate-pt/04_d047_first_internal_results_REVIEW_DRAFT.md) and [M3a UCI-412](../gate-pt/11_two_dataset_scientific_evidence_synthesis_REVIEW_DRAFT.md) are prior, **separate real internal exploratory evidence**. They are **not** pooled or recalculated in AI-10.1.

## Acceptance

1. GitHub CI and targeted negative tests green on exact PR head, including fixed-plan mismatch, fake ID duplication/overlap and existing protected ledger duplicate refusal.
2. Native Windows independent exact-head tests, source hashes, private ACL security and synthetic fresh-ledger demonstration with report hash. Record genuine failures/skips; do not claim local acceptance before user logs.
3. Human review and merge only. Then short post-merge exact-SHA smoke, followed by a separate docs-only progress update. This PR must not change the master tracker as though the milestone were finished.

The broader AI-12.2 final research report should index the existing dataset/model studies without repeating them. **Clinical evaluation is separately gated and not part of this implementation.**
