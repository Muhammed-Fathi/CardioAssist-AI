# 06 — Local Testing and Milestone Acceptance Matrix

**Status:** Updated 2026-10-20 for the blocking schema-verification correction
in M1b.1. Results below are local runs on Linux / Python 3.11.2 from a fresh
`.venv`. The change is on standalone PR #9 (**OPEN**, not merged). GitHub CI is
reported separately and remains **UNVERIFIED** because check-run access was
blocked; none of the local results are CI results.

---

## 1. Current local verification (warnings treated as errors)

| Check | Location / command | Exact result | Scope |
|---|---|---|---|
| Contract/fixture/oracle suite | `python -m pytest tests/contracts -q -W error` | **249 passed** | OpenAPI/schemas, all 31 fixture scenarios / 38 steps, oracle, safety and optional-null behavior |
| Backend suite | `python -m pytest tests/backend -q -W error` | **371 passed** | 347 existing backend regressions + 24 SQLite persistence/migration cases |
| M2a dataset audit suite (synthetic) | `python -m pytest tests/audit -q -W error` | **37 passed** | D-046 global + dataset governance checks, strict provenance path/symlink containment, separated provenance timestamps, `STOP_REQUIRES_REVIEW` ZIP inspection, `ByteIdentityGuard` on success/failure, `git check-ignore`, UCI-412/45/411/145 validators, duplicate/overlap/correspondence, leakage, zero-patient-row report redaction, and proposed audit CI workflow template |
| Contract + backend combined | `python -m pytest tests/contracts tests/backend -q -W error` | **620 passed** | Fixture pack and live HTTP/persistence behavior together |
| Full repository pytest | `python -m pytest -q -W error` | **657 passed** | All pytest tests in the repository (`249` contract + `371` backend + `37` audit) |
| Persistence/schema regressions | `python -m pytest tests/backend/test_persistence.py -q -W error` | **24 passed in 1.00s** | Explicit migrations; wrong/empty revisions; missing columns/constraints; SQLite integrity; lifespan failure/no auto-repair |
| Fresh dev dependency install | `python -m pip install -r backend/requirements-dev.txt` | **PASS** | Includes importable `httpx==0.28.1` and `httpx2==2.13.1`; no requirements changes |
| Dependency consistency | `python -m pip check` | **No broken requirements found** | Fresh pinned backend + test dependencies |
| Migration smoke | Fresh disposable SQLite DB: upgrade → `alembic check` → downgrade → re-upgrade → `alembic check` | **PASS** | Both checks: `No new upgrade operations detected.` No developer DB changed |
| Source integrity | `python scripts/verify_sources.py` | **PASS: 4/4 SHA256 hashes** | 25 papers: **9 GREEN / 1 PINK / 6 ORANGE / 9 RED** |
| Diff whitespace | `git diff --check` | **PASS** | No whitespace errors |

The backend tests use fresh temporary SQLite files. Coverage includes exact
Alembic-head verification; empty, stale and unknown revisions; missing
columns, indexes, primary keys, foreign-key constraints and unique
constraints; pre-existing foreign-key violations; SQLite integrity checks;
failed FastAPI lifespan startup without auto-upgrade or repair; configurable
DB URL; fresh/repeated migration and metadata
consistency; reads/writes, restart durability, rollback, concurrency/replay,
validation/malformed-input non-persistence, isolation, and existing fixture,
synthetic CAD and monitoring regressions. No test uses real patient data,
external database services, datasets, or model weights.

### Reproduce locally ($0 mandatory cost)

From the repository root, Python 3.11 or 3.12:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r backend/requirements-dev.txt
python -m pip check
python -m pytest tests/contracts -q -W error
python -m pytest tests/backend -q -W error
python -m pytest tests/contracts tests/backend -q -W error
python -m pytest -q -W error
python scripts/verify_sources.py
git diff --check
```

Windows PowerShell (use Python **3.12.9** if reproducing the maintainer's
reported environment). The UUID-named database below is disposable and avoids
running migration commands against a developer database:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements-dev.txt
python -m pip check
python -c "import httpx, httpx2; print(httpx.__version__, httpx2.__version__)"
$testDb = Join-Path $env:TEMP ("cardioassist-pr9-" + [guid]::NewGuid().ToString() + ".sqlite3")
$env:CARDIOASSIST_DATABASE_URL = "sqlite:///$($testDb.Replace('\', '/'))"
python -m alembic upgrade head
python -m alembic check
python -m alembic downgrade base
python -m alembic upgrade head
python -m alembic check
python -m pytest tests/backend/test_persistence.py -q -W error
python -m pytest tests/contracts tests/backend -q -W error
python -m pytest -q -W error
python scripts/verify_sources.py
git diff --check
```

The maintainer reported 611 passing tests on Windows/Python 3.12.9 for the
pre-correction PR head; that report does **not** verify this new fix. Windows
execution of the correction remains **UNVERIFIED** until the above commands
are rerun against it. For restart, cleanup of a deliberately disposable demo
database, and warnings about not deleting an existing DB, see
[`backend/README.md`](../../backend/README.md).

Run the local backend after applying migrations (one worker only):

```bash
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

The app fails closed unless the database revision and schema match the
checked-in migration head; it never silently creates, upgrades or repairs the
schema. It remains unauthenticated. Bind beyond loopback
only for a controlled synthetic-data demo with suitable network restrictions.

### GitHub CI (reported separately)

The `contracts-ci.yml` and `backend-ci.yml` workflows are installed. Workflow
presence does not prove a passing run. At the final PR head, `gh pr checks 9` reported no checks on the branch; the
REST check-runs and GitHub Actions-run endpoints returned HTTP 403 `Resource
not accessible by integration`. PR metadata reports `mergeStateStatus=UNKNOWN`,
which is not an individual check result. CI pass/fail remains **UNVERIFIED**.
Python 3.12 and Windows results
are not inferred from the Linux local runs. See
[`backend/ci/README.md`](../../backend/ci/README.md).

## 2. Regression gates that remain required

| Guard | Command / mechanism | Protects |
|---|---|---|
| Full suite (**620+** at this snapshot) | `python -m pytest -q -W error` | Wire behavior, fixtures, idempotency, audit boundaries, Track separation and persistence regressions |
| Contract oracle | `tests/contracts/` (`reference_contract.py`) | Approved mock semantics and complete fixture pack |
| Monitoring persistence | `tests/backend/test_persistence.py` + HTTP tests | Atomic observation/metric/success-audit commit; replay/error non-persistence; restart durability; SQLite constraints |
| Source integrity | `python scripts/verify_sources.py` | Four original source files + SHA256 manifest and supervisor classification |
| Prohibited artifacts | Installed CI workflows + `.gitignore` | No committed dataset/weights/database/credential artifacts (extension guard is not a secrets/PHI scanner) |
| Dependency pins | `backend/requirements*.txt`, `tests/contracts/requirements.txt`; `pip check` | Reproducible open-source setup at $0 mandatory cost |

M1b.1 does **not** persist CAD predictions, runtime idempotency/replay
records, Python audit snapshots, error-audit events, patient records, or
consent records. Its success-audit metadata is append-only by application
design; SQLite does not provide PostgreSQL `GRANT`/`REVOKE` controls. PostgreSQL
compatibility is **UNVERIFIED** (no PostgreSQL tests were run).

## 3. Milestone acceptance matrix

Legend: **L** = local tests green (commands recorded in PR) · **H** = human
review recorded · **S** = safety-labelling evidence · **D** = demonstration /
recorded walkthrough. Current status is shown explicitly; checkmarks in future
rows describe eventual acceptance requirements, not work already done.

| Milestone | Status | Local acceptance beyond §2 | S / D | Human review / boundary |
|---|---|---|---|---|
| **M1a.3** thin React + Flutter | **DEFERRED / RESEQUENCED by D-045; not cancelled or completed** | When separately scheduled: React component/snapshot tests for target/disclaimer/status copy, mock score labels, optional missing values, replay, 409, 422 wearable rejection and 503; Flutter widget tests for fields/status/errors, source labels and absence of CAD output/actions. Preserve relative `/v1`, `--dart-define`, and no browser-side `localhost`. | Demonstrate synthetic prediction and observation submission/retry, changed-key conflict and wearable→CAD 422/no score; record emulator/physical-device evidence or UNVERIFIED limits. | Requires later explicit scheduling/authorization. Carry B-01–B-04, G-02 and X-01; A-01 technical correction is complete (D-044 / PR #7/#8). |
| **M1b.1** SQLite/Alembic persistence foundation | **AUTHORIZED; IMPLEMENTED + TESTED locally; blocking schema-verification correction on standalone PR #9 OPEN** | Fresh/repeated migration + `alembic check`; disposable downgrade/re-upgrade; exact Alembic head check; reject empty/unknown/stale revisions, missing columns/indexes/primary keys and FK violations; lifespan fails without auto-migrate/repair; configurable path; isolated reads/writes; transaction rollback; restart durability; concurrent/replay behavior; existing `/v1` fixture, inference and monitoring regressions unchanged. | Synthetic/demo records only. Verify one metadata-only success-audit row in the same transaction; no CAD response, no new route, no contract/fixture change. | Human PR review and GitHub CI remain separate; no merge is claimed. SQLite only; PostgreSQL parity is not claimed. Patient/consent refs remain opaque. |
| **M1b remaining slices** platform completion | **PROPOSED / not authorized by M1b.1** | Future slices need their own tests/approval: auth/RBAC role matrix, consent lifecycle, durable audit/error/idempotency only after policy review, read/history/review APIs contract-first, offline/batch sync contract-first, admin and registry. | Client text and behavior must remain clearly synthetic; no unapproved clinical copy or inference from Track B. | Q8's durable idempotency/store-of-record policy remains open; no auth/RBAC, history/review/consent API or frontend is included in M1b.1. |
| **M2** Gate DA audit | **RESEARCH-GATED (P-2)** | Authorized read-only dataset audit, hash/license/availability/duplicate/overlap tooling tests; `verify_sources.py` remains green. | Attach dataset checklist and **“no fitting occurred”** certification. | Named human dataset authorization before any acquisition. |
| **M3** frozen protocol + real models | **RESEARCH-GATED (P-3 after M2)** | Protocol, leakage checks, negative controls, calibration, explanation fidelity/stability, and full mock-regression suite green behind separately approved real schemas/models. | Report negative as well as positive results; no mock/real confusion. | Supervisor signs Gate PT before fitting, selection, tuning or evaluation. |
| **M4** integrated research prototype + write-up | **RESEARCH / REVIEW-GATED** | Clean-checkout replication package and any approved export tests. | IC-4 walkthrough; TRIPOD+AI reporting; no unsupported novelty or clinical claims. | Supervisor/research lead; research completion is not product or clinical completion. |
| **M5** product track F14–F17 | **PROPOSED; scheduling authorization pending; preserved required vision** | Synthetic-document upload/OCR tests, extraction state machine and eligibility boundaries, admin/RBAC, assistant refusal/citation and copy-safety tests. | F14–F17 walkthrough; real patient reports prohibited absent privacy/ethics approval. | Product track remains required but scheduling and implementation need explicit authorization; D-045 priority order applies. |
| Health Connect spike | M4 product item, capability/device-dependent | Device/capability check and adapter tests on a qualifying device, or recorded unsupported-device case with simulator fallback exercised. | Simulated-source labels everywhere. | P-6 and $0/vendor terms remain open. |

**Universal rule:** a milestone is not complete until the required local gate
and named human review are satisfied. A local green run is not a CI result; a
CI software pass is not research validity or clinical approval. Do not self-
approve or merge.

## 4. Client-side obligations when M1a.3 is resumed

1. Track-B scalar types are not silently tightened by TypeScript/Dart (B-01).
2. Do not render fabricated LIME/fidelity values (X-01).
3. Never render uncalibrated scores as percentages; calibrated mock output
   retains its synthetic-cohort context.
4. Render SHAP contributions separately on the log-odds scale; never sum them
   into the score or present them as causal/advisory.
5. Monitoring screens do not call CAD inference or display Track-A scores.
6. Reuse an idempotency key only for retries of the same logical request. The
   runtime 24-hour cache is process-local; do not promise durable replay after
   restart. Accepted monitoring rows themselves persist in SQLite.

## 5. Contract-change acceptance

Any future change to approved artifacts (`shared/contracts/**`, fixtures,
oracle, contract tests) needs a maintainer decision/ADR, schema + fixture +
tests in one reviewed change-set, existing-behavior coverage, source
verification, and an explicit compatibility assessment. Breaking wire
changes require `/v2`. M1b.1 makes no contract change and adds no endpoint.

## 6. Evidence to attach to milestone PRs

1. Exact commands and full output of local runs; report CI separately.
2. Changed-path summary and confirmation that research sources/manifest are
   untouched.
3. Feature IDs and milestone acceptance criteria covered.
4. Explicit MOCK vs real statement and persistence/idempotency limitations.
5. Emulator/device evidence where applicable, or UNVERIFIED limits.
6. Open questions/gates carried forward; never silently resolve them.
