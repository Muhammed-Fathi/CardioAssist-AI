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

## M2a context: Maintainer-Led Gate DA Proposal & Read-Only Audit Toolchain (2026-10-21)
Following the merge of PR #9 (M1b.1 SQLite foundation, `661876c`) and PR #10
(Gate DA dataset suitability package, `fb928bb`), milestone **M2a** prepares:
1. Proposed governance decision **D-046** (`docs/DECISIONS.md` and
   `research/audit/gate_da_authorization.json`, status **PENDING HUMAN
   ACCEPTANCE**), documenting the maintainer-led local read-only dataset audit
   workflow, honest deferral of supervisor review (never fabricating or implying
   supervisor approval), explicit proposed access decisions for `DA-A1`,
   `DA-A2`, `DA-B1` (audit-only, never independent cohort), and `DA-B2`
   (audit-only duplicate/overlap investigation), and a separately reviewable
   proposal for an internal exploratory protocol (`D-046-EP`, **PROPOSED — NOT
   APPROVED**).
2. A $0, Python 3.12-compatible, Windows-local read-only dataset audit
   toolchain (`research/audit/`) and synthetic fixture test suite
   (`tests/audit/`).

M2a does **not** authorize the agent to download datasets, fit models, publish
results, or self-approve any governance change. Existing `/v1` contracts,
FastAPI backend, SQLite persistence, and source materials remain unchanged.


## D-047 / M2c proposal — INTERNAL Cleveland exploratory experiments (2026-10-23)

**NOT EFFECTIVE UNTIL HUMAN MAINTAINER RATIFICATION; NO TRAINING IS CURRENTLY AUTHORIZED BY THIS SECTION.** The earlier M1b.1 and D-046 audit authorizations above are historical, scoped decisions, not blanket permission to fit real-data models.

The separate D-047 governance amendment proposes a limited, maintainer-owned **internal, not supervisor-approved** exploratory pilot. See:
- `docs/DECISIONS.md` D-047 proposal
- `docs/research/gate-pt/02_d047_internal_exploratory_cleveland_PROTOCOL_PROPOSED.md`

The implementation agent may **prepare synthetic-only tests and fail-closed local-only runner code** after a human-approved milestone prompt, but cannot download datasets, fit/evaluate models on real records, handle local patient data or write clinical results in its cloud environment.

Only after the explicit D-047 PR review keyword, maintainer merge, and locally signed, ignored, hash-bound authorization can the **human local operator** run approved internal experimental training on `DA-A2/processed.cleveland.data`. A successful PR/CI alone is not approval. Never set an artificial `synthetic=true` flag for real records to bypass the synthetic-only validator.

Required experimental labels are **`INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED`** on all reports/artifacts. Gate PT P-3 remains CLOSED for formal supervisor-approved research and any clinical performance/publication/use claim. No pooling, UCI-411, Statlog, other sites, wearables, identifiers or downstream clinical integration. Leave code PRs open for maintainer review and do not forge local authorization.


## M1c — MAINTAINER-RATIFIED internal inference boundary & offline artifact admission (2026-10-24)

**Status: AUTHORIZED — narrowly scoped engineering milestone only.** Recorded
2026-10-24 from the explicit ratification of the human maintainer (repository
owner), in PR #42. This section supersedes the previously *proposed* M1c
amendment; it does not supersede, extend or reinterpret any earlier
authorization.

Authorized scope (closed list):

1. The **`MOCK_SYNTHETIC`-only CAD inference provider boundary**
   (`backend/app/inference/`): one typed internal interface, one constructible
   implementation, a fail-closed placeholder for a future reviewed real
   provider, and the registry that permits no other provider.
2. The **offline `RESEARCH_ONLY` artifact admission validator**
   (`backend/app/artifact_admission/`): a versioned descriptor, a reviewed
   synthetic feature-order binding, calibration-integrity and explainability
   checks, and a decision type that can only report `RESEARCH_ONLY` with
   `approved_for_serving` false.
3. **Synthetic** feature-order policy, calibration-integrity checks and the
   associated regression tests.

This approval does **NOT** authorize, and must never be cited as authorizing:

- real model inference or any serving of a research artifact;
- model fitting, tuning, calibration or training;
- access to, download of, or use of patient datasets or any local experiment
  output/manifest;
- clinical deployment, patient-facing use, or any clinical/performance,
  publication, novelty or external-validation claim;
- genuine SHAP/LIME computation (none exists; the API returns mock SHAP-*shaped*
  synthetic fixture offsets only);
- any change to **P-1** (pending), **P-3** (closed), **P-5** (prohibited),
  **D-046** (read-only audit), **D-047** (Cleveland-only internal exploratory),
  or the approved `/v1` OpenAPI/schemas/fixtures.

Binding conditions:

- `MOCK_SYNTHETIC` remains the only provider reachable in application
  execution. No environment variable, settings file, request field, endpoint or
  dependency-injection hook may select another.
- The admission validator stays offline: it is not imported by the running
  application, cannot be reached over HTTP, and never deserializes an artifact.
  Its synthetic order policy (`synthetic_fixture_input_order/v1`) is
  mock-fixture scope only and is **not** a clinical feature dictionary and
  **not** the five-feature D-047 Cleveland input order. An independently
  reviewed research feature-binding mapping and a real artifact packaging and
  provenance protocol remain future work requiring their own authorization.
- No research-only artifact may be served, and no descriptor, checksum or model
  file implies scientific, clinical or supervisor approval.
- Track A CAD prediction and Track B wearable monitoring stay strictly
  separated; wearable payloads never reach a CAD provider.

Governance record: this authorization is recorded **here** only. It adds no
decision id to `docs/DECISIONS.md` and changes no register entry. The historical
**M1b.1 (2026-10-17)** and **M2a / D-046 read-only (2026-10-21)** sections above
remain in force exactly as written.

The older **D-047 / M2c proposal** section above is retained verbatim as a
**historical snapshot** of the proposal as it was written on 2026-10-23; its own
status line and "not effective until ratification" wording describe that earlier
moment and are **not** a current-status statement. That limited internal
exploratory authorization was subsequently **activated**: through the
maintainer's `AUTHORIZE-D047-INTERNAL-CLEVELAND` review comment on PR #31, the
merge of that PR (`434e49a`), and a separate locally signed, hash-bound,
Git-ignored authorization manifest, after which the bounded Cleveland
(`DA-A2`) internal exploratory experiment was executed by the human local
operator under the required
`INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED` label.

That activation is exactly the pre-existing D-047 internal exploratory scope. It
is not reopened, extended, reinterpreted or re-granted by this M1c section, and
it authorizes nothing else: **Gate PT P-3 remains CLOSED**, no supervisor,
ethics or institutional approval is claimed, the D-047 results stay internal
exploratory evidence and never a deployable model, and **no new model fitting,
artifact serving, patient-facing use, publication/novelty claim or clinical
authorization is granted here**.

This section authorizes no subsequent milestone; the next stage still requires
its own explicit maintainer authorization and, for any real artifact,
independent scientific review.

## M3a context: UCI-412 source-specific research benchmark (2026-10-24)

**Status: PROPOSED; NOT AUTHORIZED.** Milestone **M3a** prepares proposed
governance decision **D-048** (`docs/DECISIONS.md`) together with a synthetic-only,
Windows-local research package (`research/uci412/`, `tests/uci412/`) for the
single dataset **`DA-A1` UCI-412** (*Z-Alizadeh Sani*, 303 participants).

- **What is prepared:** a strict, versioned, read-only adapter (exact 56-column
  header, `Normal`→0 / `Cad`→1 only, no coercion or row deletion); a versioned
  feature dictionary with **one executable panel** (16 ordered basic clinical
  columns) and three registered-but-blocked panels; a bounded repeated
  nested-CV harness with training-fold-only preprocessing and a reserved
  gradient-boosting extension point; a label-permutation negative control;
  aggregate-only reporting; and fail-closed local authorization/provenance
  gates. The checked-in authorization JSON is a **template that authorizes
  nothing**.
- **What is not prepared, permitted or implied:** no real workbook is bundled,
  downloaded, or read; no model is fitted on real records; no patient-level
  result exists; **Gate PT P-3 remains CLOSED**; no supervisor, ethics or
  institutional approval is claimed; no clinical, deployment, novelty or
  publication claim is made. Synthetic results are software evidence only.
- **Relationship to earlier decisions:** the D-046 ratification remains
  read-only audit and is **not** training permission; D-047 remains limited to
  `DA-A2` processed Cleveland and is unchanged by this milestone. D-048 shares
  no scope with either.
- **Scientific constraints binding on any future authorized work:** the target is
  cross-sectional angiography-referenced CAD presence, never future-event risk;
  UCI-412 and UCI-411 are the **same 303 participants** and are never independent
  datasets; no pooling with Cleveland/Hungary/VA/Switzerland; the ≥50% versus
  >50% threshold question stays unresolved; angiography-derived features,
  identifiers and post-outcome fields stay excluded; feature selection never
  uses outcome data.
- **CI note:** `.github/workflows/**` is untouched by this branch (the pushing
  automation identity has no `workflows` permission). The reviewed CI change
  ships as `research/uci412/ci/experiment-runner-ci.uci412.patch` for a
  maintainer to apply.

This section authorizes no subsequent milestone and no real-data execution.

### M3a activation preparation (2026-10-24) — PROPOSED; NOT AUTHORIZED

**Status: PROPOSED; NOT AUTHORIZED; NOTHING ACTIVATED.** A documentation-only ratification
packet, [doc 09](docs/research/gate-pt/09_m3a_uci412_internal_research_RATIFICATION_PACKET.md),
prepares the single human governance act that D-048 and doc 08 leave open. It adds no
decision id, changes no register entry, and modifies no gate, guard, blocker or status.

- **Unchanged by this preparation:** doc 08, the registered plan
  (`research/uci412/uci412_cad_research_plan.v0.1.json`), the feature dictionary
  (`research/uci412/schemas/uci412_feature_dictionary.v1.json`), all of `research/uci412/**`,
  `research/experiments/**`, the application code and `.github/**`. The 16-column basic
  clinical panel, the three model families, the repeated nested-CV scheme and seeds, the fixed
  0.5 exploratory threshold, the negative controls and every guard remain byte-identical.
  D-048's proposal text in `docs/DECISIONS.md` is deliberately not edited: its own closing
  clause requires a named human decision to change it.
- **What the packet contains:** the frozen artifact hashes the human would bind; the frozen
  scope restated for accept/reject; the residual source-feature semantics (S-1 … S-8) and the
  sample-size limitations (`NOT_MET_AT_STATED_HALF_WIDTH`; R²-dependent criteria
  `NOT ASSESSED`) as explicit blank human decisions; and the exact activation sequence —
  verbatim `AUTHORIZE-M3A-UCI412-INTERNAL-RESEARCH` PR comment, human-approved merge, the
  pre-existing D-046 `DA-A1` local read-only chain, protected provenance and licence snapshot,
  the field-by-field local manifest at
  `data/manifests/uci412_internal_research_authorization.local.json`, hash binding and the
  Windows-local `preflight`, followed only then by `run`.
- **Nothing is claimed or implied:** no signature, approval, ratification or activation; no
  supervisor, ethics or institutional approval; **Gate PT P-3 remains CLOSED**, P-1 PENDING,
  P-5 prohibited; D-046 stays read-only audit and D-047 stays Cleveland-only. No dataset was
  accessed, no model was fitted, no performance number exists, and no patient-level output was
  created, committed, or uploaded by this preparation.

This addendum authorizes no subsequent milestone and no real-data execution.
