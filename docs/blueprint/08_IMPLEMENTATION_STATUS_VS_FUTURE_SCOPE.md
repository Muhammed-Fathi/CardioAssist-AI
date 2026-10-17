# 08 — Current Implementation Status versus Future Scope

**Snapshot:** 2026-10-17, M1b.1 on the current session branch
`arena/b8feac51-cardioassist-ai`. The SQLite/Alembic monitoring persistence
slice is **IMPLEMENTED + TESTED locally** and submitted in standalone PR #9,
which is **OPEN**; it is not merged. Latest local results are Linux / Python
3.11.2: **249 contract + 362 backend = 611 passed** with `-W error`; `pip
check` reports no broken requirements; source verification passes 4/4 hashes.
See [06](06_TESTING_AND_ACCEPTANCE_MATRIX.md) for exact commands/results.
GitHub check status for PR #9 is **UNVERIFIED**: `gh pr checks` and REST
check-run/status endpoints returned HTTP 403 `Resource not accessible by
integration`. PR metadata reports `mergeStateStatus=UNSTABLE`, but individual
checks could not be inspected; no pass/fail is inferred. Windows and Python
3.12 local runs are also UNVERIFIED.

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
| `docs/DECISIONS.md` | D-001…D-045 and pending P-1…P-6 | Authoritative register; D-044 technical correction complete; D-045 authorizes M1b.1 only and does not close unrelated gates |
| `docs/FEATURE_REGISTER.md` | F01–F12 | Preserved proposed feature register; blueprint F13–F18 extensions are tracked separately and are not silently ratified here |
| `shared/contracts/` | OpenAPI, schema families, 2 MOCK_ONLY registries, 31 fixtures / 38 steps | **IMPLEMENTED + TESTED**, M1a.1; no M1b.1 contract/fixture changes. A-01 Option A schema correction merged in PR #8; technical correction complete |
| `tests/contracts/` | Contract/oracle suite | **249 passed** locally; fixture pack preserved |
| `backend/app/` | FastAPI mock backend, two existing POST routes, bundled `/openapi.json`; SQLAlchemy storage boundary | Existing contracts unchanged. M1b.1 persists monitoring observation, non-null metrics and success-audit metadata only. Runtime idempotency and Python audit snapshots remain in memory |
| `backend/migrations/`, `alembic.ini` | Alembic environment and initial migration | **IMPLEMENTED + TESTED locally** on disposable SQLite databases; explicit migrations; no schema auto-creation at startup |
| `backend/app/storage/` | SQLAlchemy models, DB configuration/transaction wrapper and monitoring repository | **IMPLEMENTED + TESTED locally**; configurable `CARDIOASSIST_DATABASE_URL`; SQLite only tested |
| `tests/backend/` | Existing API regressions + migration/persistence tests | **362 passed** locally, including 15 M1b.1 migration/persistence cases |
| `.github/workflows/` | Installed contracts and backend CI workflows | Workflows present; current PR #9 check results **UNVERIFIED**. Workflow presence is not a green CI result |
| `backend/README.md`, `backend/CONTRACT_NOTES.md`, `backend/VERIFICATION.md` | Setup, limitations, contract behavior and verification records | Updated; Windows/CI caveats remain explicit |
| `docs/M1A3_INTEGRATION_HANDOFF.md` | React/Flutter thin-client plan | Preserved and updated: M1a.3 is deferred/resequenced, not cancelled or completed |
| `docs/blueprint/` | Architecture, feature, roadmap, data/API, research-gate, test, open-decision and status docs | Reconciled to D-044/D-045/M1b.1; planning documents do not authorize work beyond D-045 |
| `frontend/clinician-web/`, `frontend/patient-mobile/` | Candidate React and Flutter projects | **PROPOSED**; no implementation. Thin local integration/demo clients remain preserved, deferred requirements |
| `ai/`, `infra/`, `research/experiments/` | Placeholder/future locations | **PROPOSED**; no trained model, dataset, deployment or experiment results |

### Current local verification record

- `python -m pip check`: **No broken requirements found**.
- `python -m pytest tests/contracts -q -W error`: **249 passed**.
- `python -m pytest tests/backend -q -W error`: **362 passed**.
- `python -m pytest tests/contracts tests/backend -q -W error`: **611 passed**.
- `python -m pytest -q -W error`: **611 passed**.
- Disposable SQLite migration smoke: fresh upgrade, consistency check,
  downgrade, re-upgrade and second consistency check **PASS**. Developer DBs
  were not downgraded or deleted.
- `python scripts/verify_sources.py`: **PASS**, 4/4 hashes; 25 papers with
  `9 GREEN / 1 PINK / 6 ORANGE / 9 RED`.
- `git diff --check`: **PASS**.
- **CI:** PR #9 check rollup **UNVERIFIED/unavailable**; not reported as pass or
  fail. Local Python 3.12 and Windows execution are also **UNVERIFIED**.

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
| API & tests (F12) | **249 contract + 362 backend = 611 local tests passed**; existing `/v1` contracts/fixtures unchanged; PR #9 open | Fixture pack and synthetic backend | Grows only through reviewed slices; GitHub CI result unverified |
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
