# AI-9 through AI-12: implementation-ready slices

**Research proposal, 2026-11-17; no implementation in this PR.** Read [medical review](INDEPENDENT_MEDICAL_ENGINEERING_RESEARCH.md) and [disagreements](INDEPENDENT_DISAGREEMENTS.md). Each code PR requires explicit review of its actual scope; none below grants data access or changes a frozen protocol. Prioritize synthetic engineering independently of clinical-deployment approvals. The suggested file paths are boundaries, not a mandate to duplicate existing code.

## Existing components to reuse, not recreate

- `ai/panels.py` has versioned source-specific panel contracts, rejected fields and missingness; verify identity/version/hash, don't conflate source codes.
- `ai/preprocessing.py`, `ai/training.py`, `ai/calibration.py` implement fold-contained training/evaluation and calibration; examine actual algorithms and tests before reuse. `ai/training.py` also has an external-evaluation primitive and ledger. This is not a claim that every proposed protocol is implemented or approved.
- `ai/packaging.py` verifies local integrity and producer authenticity before deserialization; SHA alone is not authenticity. `ai/inference.py` offers offline research prediction; `ai/cli.py` intentionally enforces synthetic provenance. `ai/research_routes.py` has route metadata, `ai/lime_quality.py` has fidelity gates. Do not loosen these boundaries to make a registry work.
- `backend/app/inference/registry.py` allows only `MOCK_SYNTHETIC`; backend mock XAI-shaped fixtures are **not genuine SHAP**. Offline admission is not a serving entitlement. Keep existing `/v1` contract unchanged and preserve diagnostic registry empty.
- AI-8R source status is `SCIENTIFIC_HOLD`; the maintainer acceptance record documents 2,366 passing/3 skipped across **two disjoint completed suites**, not a completed monolithic Windows suite. Synthetic software results are not medical results.

## Shared acceptance and runbook

All steps $0, local CPU; no paid accounts/services. Each PR states exact source revision, Python/dependency versions, execution environment, command, result/exit, skips, evidence and claim level. Keep credentials, records, local authorization manifests, real bundles and patient-derived backgrounds outside Git/CI. Never delete or inspect ignored authorizations to make tests pass. Avoid changing files bound into frozen governance or hashes.

**Windows PowerShell** (maintainer after merge, clean isolated worktree, Python 3.12, NTFS for applicable security tests). **Proposed, not a claimed executed fresh-venv verification.** Create the virtual environment **outside the Git worktree**: the repository's actual `.gitignore` does not ignore `.venv-ai/` inside it. Use the already validated external Windows full-suite environment if available, or provision a fresh external environment with both research and backend development dependencies. Run from the exact intended SHA; do not copy local ignored manifests, datasets or signing keys:

```powershell
$ErrorActionPreference = 'Stop'
$ExpectedSHA = '<EXACT_REVIEWED_MERGE_SHA>'
if ((git rev-parse HEAD).Trim() -ne $ExpectedSHA) { throw 'Unexpected HEAD' }
if (git status --porcelain --untracked-files=all) {
    throw 'Checkout is dirty; use a fresh isolated worktree, do not delete files'
}
$Venv = Join-Path $env:LOCALAPPDATA 'CardioAssist_AI\AI11_Research_Venv'
if (Test-Path -LiteralPath $Venv) {
    throw 'External venv path exists; choose a separate new path or use an already validated environment'
}
py -3.12 -m venv $Venv
if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 environment creation failed' }
$Python = Join-Path $Venv 'Scripts\python.exe'
& $Python -m pip install -r research/uci412/requirements.txt -r backend/requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
& $Python -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Dependency consistency failed' }
& $Python scripts/verify_sources.py
if ($LASTEXITCODE -ne 0) { throw 'Source integrity failed' }
& $Python -m pytest -W error -q tests/uci412 tests/experiments
if ($LASTEXITCODE -ne 0) { throw 'Focused research tests failed' }
# Run new PR-specific tests, then the complementary or monolithic suite as warranted.
& $Python -m pytest -W error -q --tb=short --ignore=tests/experiments --ignore=tests/uci412
if ($LASTEXITCODE -ne 0) { throw 'Complementary tests failed' }
& $Python -m ai uci412-demo --format text
if ($LASTEXITCODE -ne 0) { throw 'Synthetic demo failed' }
if (git status --porcelain --untracked-files=all) {
    throw 'Worktree became dirty; investigate without deleting protected files'
}
```

The two pytest invocations above are **segmented test coverage**, not a successful *single* monolithic run. For a future AI-11 implementation PR, add its **new focused test module(s)** to the runbook and execute them explicitly. If monolithic full-suite acceptance is required for a specific release, run and record it separately; never relabel an interrupted run as success. Report actual local outcomes/exit codes and any skipped cases rather than assuming this snippet was executed.

Record failures/skips, Windows security/ACL cases actually executed and any known ignored-manifest isolation conflict; no blanket local acceptance if failures remain. Test installation availability may vary; no patient data or model uploads. For any retained synthetic demo output use a fresh private NTFS path outside repository; remove **only that explicit synthetic path** after verifying it is correct, never protected folders. `python -m ai demo` is also a synthetic CLI option. GitHub CI must run focused tests plus applicable existing contract, synthetic runner, audit, mock backend and source-integrity workflows; do not add private secrets/datasets. CI and native Windows results are separate. For docs-only work use Markdown link/JSON checks, source verification and `git diff --check` where applicable.

## P0 / AI-11.1 — Offline synthetic route registry and typed facade (first code PR)

**Scope:** add a small, immutable, explicit registry/facade under `ai/` (e.g. `ai/research_registry.py`, `ai/research_facade.py`) that composes, rather than replaces, `research_routes`, `panels`, `cli` and the existing verified synthetic predictor. API request contains route ID/version, panel version/hash, synthetic fixture provenance and typed feature/value/unit/acquisition-stage/missingness; response has status (`SYNTHETIC_RESULT`, `ABSTAIN`, `UNAVAILABLE`, `ERROR`), route/model/panel versions and evidence level. A numeric synthetic output is labeled synthetic, not clinical probability. When calibration is not supported return absent calibration with reason, not a raw score relabeled calibrated. Explainability is optional with declared target/scale/background and LIME quality; unavailable is acceptable. Typed error reasons should not echo input values, paths or secrets. Never trust a caller-supplied `synthetic=true` as evidence for real records; only deliberately fabricated fixtures and existing provenance/security controls are admissible.

**Boundaries:** no real artifact deserialization, no new HTTP endpoint or environment switch; never import real provider into application selection. `backend/app/inference/*` remains mock-only; test compatibility through existing boundary with no `/v1` schema or fixture change. No new clinical rules or use of guideline coefficients. Synthetic registry cannot accept arbitrary plugins. Unknown/disabled routes or unsupported panels fail closed. Dependencies/security controls in packaging/CLI remain intact.

**Tests:** `tests/experiments/test_research_facade.py` and focused existing routes/CLI/panel/backend tests: known synthetic round trip; panel/model version mismatch; invalid type/unit/unknown field; unavailable required feature; optional missing reason; injected target/wearable data; real provenance/profile or forged flag rejected before deserialization; untrusted bundle; missing calibrator/XAI; deterministic result, path/feature redaction; backend only mock; diagnostic registry empty and no HTTP contract drift. Mock fixtures do not prove clinical accuracy.

**Done:** exact PR-head CI passes, relevant Windows commands and negative cases pass and are reported; normal demo returns explicit synthetic status, at least three refusal paths return typed results, schema/version stable and no real access path exists. **Permission:** synthetic only. **Forbidden:** real model/patient data, bypassing provider admission, changing locked outcomes, protocol or `/v1`. **Claim:** `ENGINEERING_READY` / `SYNTHETIC_TEST_ONLY`; no `REAL_EVALUATION` or clinical claim.

## P0 parallel / AI-12.1 — minimum viable research E2E and evidence pack

**Scope:** a separate `scripts/` synthetic demo or extend existing `ai` CLI only after interface review, plus docs/model-card template and `tests/` regression. Fabricated input → versioned source-specific validation → synthetic fallback → optional correctly labeled calibrated output → explanation with scale/quality or explicit unavailable → mock backend contract test → reproducible report/model card. Include dependency lock/version and clean-room instructions, source/license inventory, intended target, source and panel hash, provenance, abstentions, limitations, test results and scientific status. Evidence inventory can be checksum-bound to released synthetic files; an actual human signature, if desired, must be separately made and verified by that human, not faked by an agent. Never label a checksum as a human signature.

**Tests:** repeat demo on identical fixture, assert stable canonical report after excluding explicit timestamps/random identifiers; report schema validation; malformed/unsupported/unsafe input fails; uncalibrated result not called calibrated; unavailable explanation; no paths, secrets, patient data; verify clean cleanup. Run shared Windows/CI suite plus targeted new demo tests.

**Done:** a new developer can reproduce the entire synthetic demo and expected refusal without a dataset, paid service or external model; evidence pack identifies versioned model/fixture and differentiates synthetic from real. **Permission:** synthetic only. **Forbidden:** live patient traffic, real bundle, unverified performance claims. **Claim:** `SYNTHETIC_E2E_COMPLETE` only, not external validation or clinical readiness.

## AI-9.1 — same-source incremental-value harness, synthetic only

**Scope:** in `ai/` or `research/` extend existing evaluation primitives with versioned comparison plan: matched cohort, same outer patient folds, matched clinical-only vs clinical+labs, fold-local preprocessing/imputation/calibration, paired metric deltas and uncertainty, missingness denominator and feasibility status. Develop sample-size sensitivity input/parameter accounting; do not encode unsupported medical thresholds. Do not edit existing frozen experiment plans.

**Tests:** seeded synthetic data with missing labs, different row IDs/order, labels, folds and malformed panel; refuse unmatched patients or mismatched target, verify no train/test contamination or imputation fitted on outer tests, deterministic paired estimates; no assertions about real medical improvement. Shared Windows/CI and new tests.

**Done:** executable synthetic compare report with cohort counts, model complexity, calibration/discrimination delta and explicitly synthetic status; rejected mismatch and no misleading improvement claim. **Real NO-GO:** lab timing/semantics, comparable same-source records, size and approved study/access scope all missing; no real fit or data access. **Claim:** engineering only.

## AI-10.1 — locked-site simulation, synthetic only

**Scope:** reuse `evaluate_locked_external_cohort` and `ExternalEvaluationLedger`, not a second independent mechanism. Add protected synthetic preflight/ledger contract if gaps remain: frozen model digest and panel/schema/endpoint, explicit unique cohort identity, split/overlap evidence, one-shot state, failure/recovery, no outcome access prior to approval, and signed-off evaluation plan reference. Generate fake site shifts and fixed invented outcomes only. The ledger manages attempts, not an ethics approval or cryptographic proof of independence.

**Tests:** frozen model/schema mismatch; duplicate identity; unauthorized route; reserve/concurrent/resume semantics; failure and no implicit retry or test-set tuning; redaction; drift report; empty/single-class/low-N gracefully `INSUFFICIENT_EVIDENCE`. Show external metrics are only from fixed synthetic data. Shared Windows/CI, especially file locks and path security.

**Done:** clear audit trail, version-binding and refusal test; no changes to locked Hungary assets. **Real gate:** individual overlap, site mapping/target comparability, missingness, sample-size/precision, separate approved protocol and local access. Even authorized evaluation may conclude insufficient evidence. **Claim:** `SYNTHETIC_TRANSPORT_TEST` only.

## AI-11.2 — research model catalog / optional integration boundary

After AI-11.1, add immutable model-card/descriptor catalog, provenance/status and optional offline-only interface; keep backend's one mock implementation. Version schema, validate panel/artifact/calibration/explainability compatibility, ensure bundle authentication before deserialization using existing safety code. Strict allowlist of synthetic routes. Add contract and regression tests for incompatible models, compromised hashes/HMAC, data leak and refusal paths. No real provider switch, no new endpoint, no protected artifact import. Done when catalog, facade and `/v1` mocks compose under focused CI and Windows tests; claim synthetic engineering only. Any future real-bundle operation requires its *own* ratification/activation, not this plan.

## AI-9.2 / AI-10.2 / AI-12.2 — conditional scientific follow-through

- **Source-evidence PR, parallel now:** metadata-only audit of owner codebook, timeline, exact licenses, provenance and target; update only a new reviewed evidence document, not the protected register or frozen protocols. Test link structure and source checks; no data files. Owner clarification can change the recommendation, not self-authorize.
- **Real comparisons/evaluation, later only:** a separately scoped governance decision and approved protocol must precede authorized local access and fitting. Specify source and hashes, methods, privacy, reproducibility, HMAC/trusted boundaries, operator, and success/failure reporting. No locked-set peek. Clinical certification is not a prerequisite for doing an *authorized* academic experiment; neither academic intent nor public license overrides data restrictions.
- **AI-12 final handoff:** evidence-indexed README/model cards, versioned synthetic artifacts and verification instructions; accurately cite any separately authorized and human-reviewed internal results with original limitations, without exposing protected derivatives. Final acceptance: synthetic E2E and refusal cases reproducible; every scientific claim tied to permitted evidence, external-validation status explicit, open blockers/roles listed, no fabricated signature. Record exact CI and maintainer Windows results; keep prototype research-only.
