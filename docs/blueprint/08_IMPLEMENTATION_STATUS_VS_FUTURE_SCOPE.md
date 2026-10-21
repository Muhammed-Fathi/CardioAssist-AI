# 08 — Current Implementation Status versus Future Scope

**Snapshot:** 2026-10-21, milestone **M2a** on top of merged `main` commit
`fb928bb96d000044c3a8617767c345555ea8c683` (PR #10 Gate DA suitability package
merged on top of PR #9 M1b.1 SQLite persistence `661876c`). The M2a read-only
local dataset audit toolchain (`research/audit/`) and synthetic fixture test
suite (`tests/audit/`) are **IMPLEMENTED + TESTED locally** on Linux / Python
3.11.2: **249 contract + 371 backend + 33 audit = 653 passed** with `-W error`;
isolated `research/audit/requirements.txt` and `backend/requirements-dev.txt`
installs and `pip check` pass; source verification passes 4/4 hashes. Proposed
governance decision **D-046** (`docs/DECISIONS.md` and
`research/audit/gate_da_authorization.json`) and its dataset access decisions
(`DA-A1`, `DA-A2`, `DA-B1`, `DA-B2`) remain **PENDING HUMAN ACCEPTANCE**; the
separately reviewable internal exploratory protocol proposal (`D-046-EP`) is
**PROPOSED — NOT APPROVED**. Windows-local execution of the audit toolchain on
real UCI datasets remains **UNVERIFIED / REQUIRES APPROVAL** until the human
maintainer approves D-046 and executes
[`docs/research/gate-da/09_m2a_windows_local_audit_handoff.md`](../research/gate-da/09_m2a_windows_local_audit_handoff.md).

**Honesty rule:** no trained model exists; all current CAD/XAI output is
deterministic synthetic fixture data (`MOCK_SYNTHETIC`). No dataset has been
acquired and no clinical performance, validation, diagnostic or deployment
claim is made.

---

## 1. Status taxonomy

| Class | Meaning |
|---|---|
| **IMPLEMENTED** | Code or documents are present in this checkout; merge status is stated separately |
| **TESTED** | The named local tests/checks actually passed; a green result is not inferred from code presence |
| **SYNTHETIC/MOCK** | Real software producing deterministic synthetic results — not trained AI, not clinical evidence |
| **PROPOSED** | Designed but not implemented/authorized in this slice |
| **RESEARCH-GATED** | Blocked by Gate DA/PT or dataset/protocol approvals |
| **CLINICALLY-GATED** | Blocked by clinician/supervisor review |
| **ACCESS-GATED** | Blocked by hardware, account, vendor terms or controlled data |
| **UNVERIFIED** | Not established by available local or GitHub evidence |
| **PROHIBITED** | Rejected design input; may not be implemented as described |

## 2. Repository inventory → status

| Path | What exists | Status |
|---|---|---|
| `research/source_materials/` | Supplied presentation, notes, literature workbook/CSV and SHA256 manifest | Preserved; latest local integrity check **4/4 hashes**; supervisor classification **25 papers (9 GREEN / 1 PINK / 6 ORANGE / 9 RED)** |
| `docs/phase0/PHASE0_REVIEW_DRAFT.md` | Rev. 3 feasibility review | Merged (PR #1); historical research/gate baseline |
| `docs/DECISIONS.md` | D-001…D-045 and proposed D-046 (`PENDING HUMAN ACCEPTANCE`) + pending P-1…P-6 | Authoritative register; D-044 technical correction complete; D-045 M1b.1 merged; D-046 proposed maintainer-led Gate DA governance and dataset access scope (`DA-A1`, `DA-A2`, `DA-B1`, `DA-B2`) awaiting human maintainer acceptance |
| `docs/research/gate-da/` | Gate DA dataset suitability & decision package (01–08, merged in PR #10) + M2a Windows handoff (`09_m2a_windows_local_audit_handoff.md`) | Merged baseline + M2a Windows PowerShell execution handoff; no real dataset downloaded |
| `research/audit/` | M2a Python 3.11/3.12-compatible, $0, Windows-local read-only dataset audit toolchain + `gate_da_authorization.json` | **IMPLEMENTED + TESTED locally on synthetic fixtures**; all dataset authorizations remain `PENDING_HUMAN_ACCEPTANCE`; fails closed on unapproved access, hash/format mismatch, or patient-row leakage |
| `tests/audit/` | M2a synthetic fixture unit & negative tests | **33 passed** locally; synthetic software test fixtures only |
| `docs/FEATURE_REGISTER.md` | F01–F12 | Preserved proposed feature register; blueprint F13–F18 extensions are tracked separately and are not silently ratified here |
| `shared/contracts/` | OpenAPI, schema families, 2 MOCK_ONLY registries, 31 fixtures / 38 steps | **IMPLEMENTED + TESTED**, M1a.1; no M1b.1 contract/fixture changes. A-01 Option A schema correction merged in PR #8; technical correction complete |
| `tests/contracts/` | Contract/oracle suite | **249 passed** locally; fixture pack preserved |
| `backend/app/` | FastAPI mock backend, two existing POST routes, bundled `/openapi.json`; SQLAlchemy storage boundary | Existing contracts unchanged. M1b.1 persists monitoring observation, non-null metrics and success-audit metadata only. Runtime idempotency and Python audit snapshots remain in memory |
| `backend/migrations/`, `alembic.ini` | Alembic environment and initial migration | **IMPLEMENTED + TESTED locally** on disposable SQLite databases; explicit migrations; exact head verification; no schema auto-creation/repair at startup |
| `backend/app/storage/` | SQLAlchemy models, DB configuration/transaction wrapper and monitoring repository | **IMPLEMENTED + TESTED locally**; configurable `CARDIOASSIST_DATABASE_URL`; startup checks revision, metadata drift and SQLite integrity; SQLite only tested |
| `tests/backend/` | Existing API regressions + migration/persistence tests | **371 passed** locally, including 24 M1b.1 migration/persistence cases |
| `.github/workflows/` | Installed contracts and backend CI workflows | Workflows present; current PR #9 check results **UNVERIFIED**. Workflow presence is not a green CI result |
| `backend/README.md`, `backend/CONTRACT_NOTES.md`, `backend/VERIFICATION.md` | Setup, limitations, contract behavior and verification records | Updated; Windows/CI caveats remain explicit |
| `docs/M1A3_INTEGRATION_HANDOFF.md` | React/Flutter thin-client plan | Preserved and updated: M1a.3 is deferred/resequenced, not cancelled or completed |
| `docs/blueprint/` | Architecture, feature, roadmap, data/API, research-gate, test, open-decision and status docs | Reconciled to D-044/D-045/M1b.1; planning documents do not authorize work beyond D-045 |
| `frontend/clinician-web/`, `frontend/patient-mobile/` | Candidate React and Flutter projects | **PROPOSED**; no implementation. Thin local integration/demo clients remain preserved, deferred requirements |
| `ai/`, `infra/`, `research/experiments/` | Placeholder/future locations | **PROPOSED**; no trained model, dataset, deployment or experiment results |

### Current local verification record

- Fresh `.venv` install from `backend/requirements-dev.txt` includes importable
  `httpx==0.28.1` and `httpx2==2.13.1`; no dependency changes were needed.
- `python -m pip check`: **No broken requirements found**.
- `python -m pytest tests/backend/test_persistence.py -q -W error`:
  **24 passed in 1.00s**; includes empty/outdated/unknown revision, missing
  column/index/primary/foreign-key/unique constraints, orphan foreign key,
  and failed lifespan/no auto-repair cases.
- `python -m pytest tests/backend -q -W error`: **371 passed in 17.49s**.
- `python -m pytest tests/contracts tests/backend -q -W error`:
  **620 passed in 17.60s**.
- `python -m pytest -q -W error`: **620 passed in 18.27s**.
- Disposable SQLite migration smoke: fresh upgrade, consistency check,
  downgrade, re-upgrade and second consistency check **PASS**. Developer DBs
  were not downgraded or deleted.
- `python scripts/verify_sources.py`: **PASS**, 4/4 hashes; 25 papers with
  `9 GREEN / 1 PINK / 6 ORANGE / 9 RED`.
- `git diff --check`: **PASS**.
- **GitHub CI:** PR #9 individual check results **UNVERIFIED** due the
  integration HTTP 403; no pass/fail inferred. Windows/Python 3.12.9
  maintainer-reported 611-test result predates this correction; Windows and
  Python 3.12 verification of this change remain **UNVERIFIED**.

These are local verification results for this checkout. They do not establish
maintainer approval/merge, Windows compatibility, PostgreSQL parity, research
validity or clinical readiness.

## 3. Feature status snapshot

| Capability | Implemented/tested today | Synthetic/mock today | Not built / boundary |
|---|---|---|---|
| CAD prediction (F01) | Contract, validation, deterministic response behavior | SHA-256-derived mock scoring; model D remains 503 | Real trained model, approved target and evaluation (M2/M3, P-1…P-3 gated) |
| Explainability (F02) | Contract/additivity behavior | Synthetic SHAP-shaped offsets | Real TreeSHAP/LIME, fidelity/stability (M3, research-gated) |
| Clinician dashboard (F03) | — | — | Thin React path M1a.3 deferred/resequenced; full surface later M1b, separately authorized |
| Patient app (F04) | — | — | Thin Flutter path M1a.3 deferred/resequenced; full surface later M1b, separately authorized |
| Monitoring (F05) | Existing Track-B POST; M1b.1 durable observation + non-null metrics + success-audit metadata, transactionally | `simulated_wearable` remains synthetic; no CAD score | No history/read/batch/consent API; real adapters P-6 gated; wearable→CAD prohibited |
| Reassessment/follow-up (F06) | Existing response state only | — | Validity-gated workflows, notifications and summaries remain proposed M1b work |
| Audit/consent (F07) | One durable metadata-only event per accepted monitoring write in M1b.1; runtime snapshots for existing behavior | Test-only/runtime snapshots remain in memory | Consent lifecycle, read/error/CAD durable audit remain deferred; no tamper-resistance claim |
| FHIR (F08) | — | — | Thin export proposed for M4, subject to D-020 |
| Disease modules (F09) | — | — | Registry scaffolding/second module later, separately authorized and research-gated |
| Research workflow (F10) | Methodology and gates documented | — | Dataset audit M2 → protocol/models M3 → write-up M4; gates remain closed |
| Auth/RBAC (F11) | — | — | Not included in M1b.1; requires separate M1b authorization and role-matrix tests |
| API & tests (F12) | **249 contract + 371 backend = 620 local tests passed**; existing `/v1` contracts/fixtures unchanged; PR #9 open | Fixture pack and synthetic backend | Grows only through reviewed slices; GitHub CI result unverified |
| History/symptoms/surveys (F13) | — | — | Proposed M1b APIs and screens; each new route contract-first |
| Lab OCR (F14) | — | — | M5 required product vision; synthetic documents only until privacy approvals |
| Extraction verification (F15) | — | — | M5 required product vision; verification does not imply Track-A eligibility |
| Research-safe assistant (F16) | — | — | M5 proposed and clinician-gated |
| Administration (F17) | — | — | Basic M1b / console M5 proposed; auth/RBAC required |
| Persistence/deployment (F18) | M1b.1 SQLite/Alembic monitoring slice implemented/tested locally | Synthetic/demo records only | PostgreSQL path is proposed/unverified; hosting optional and unverified; broad persistence remains future work |

## 4. Explicit non-claims and limitations

- **No real AI:** no dataset acquired, no model trained, no real SHAP/LIME,
  no accuracy/AUC/calibration result exists. Mock scores have no clinical
  meaning.
- **No clinical validity:** no diagnosis, risk probability, alert threshold,
  treatment recommendation, clinical readiness or patient-care use.
- **No production service:** no auth/RBAC, no real patient data, no history or
  review API, no PHI protection guarantee, no tamper-proof audit, no SLA.
- **No durable idempotency:** the 24-hour runtime behavior stays in process
  memory. Q8's formal retention/store-of-record policy remains open. A retry
  after process restart may be treated as a new write; the durable monitoring
  observation itself survives restart.
- **No consent/patient lookup:** references are stored as opaque synthetic/demo
  values; no patient/consent master rows or foreign keys are invented.
- **No PostgreSQL parity:** no PostgreSQL test run. SQLite has no PostgreSQL
  `GRANT`/`REVOKE`; append-only audit is an application-level design rule.
- **No research/data/clinical gates waived:** D-045 changes execution priority
  only. No dataset download, model training, clinical integration or research
  approval was authorized.

## 5. Delivery priority and future scope

D-045 prioritizes: **(1) genuine, reproducible CAD AI research and inference;
(2) a complete, integration-ready FastAPI backend; (3) a durable, tested
database.** This ordering does not waive the scientific, data or clinical
gates. M1b.1 is the first authorized implementation slice and delivers only
the existing monitoring POST persistence described above.

- **M1a.3:** deferred/resequenced, not cancelled or completed. Preserve its
  React/Flutter thin local integration/demo plan in
  `docs/M1A3_INTEGRATION_HANDOFF.md`; implement only after separately scheduled
  and authorized.
- **Remaining M1b:** proposed, not authorized by M1b.1. Future APIs remain
  contract-first; consent, authentication/RBAC, patient/history/review, durable
  idempotency and expanded audit each need their own decisions and tests.
- **M2:** Gate DA; no dataset acquisition before P-2 authorization and a named
  dataset/storage plan.
- **M3:** Gate PT; no fitting, selection, tuning or evaluation before P-3,
  after the read-only M2 audit.
- **M4:** research prototype completion and write-up; not product or clinical
  completion.
- **M5:** F14–F17 remain required product-vision deliverables, but are
  separately scheduled/authorized and do not block the current M1b.1 slice.

The research integrity target remains 4/4 hashes and the reviewed paper
classification **25 total: 9 GREEN / 1 PINK / 6 ORANGE / 9 RED**. Do not
download datasets, train models, close approvals, merge PR #9, or begin a
subsequent milestone without separate authorization and human review.
