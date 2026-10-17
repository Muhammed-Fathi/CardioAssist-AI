# FastAPI backend — MOCK_SYNTHETIC API + M1b.1 persistence

**Research prototype only.** CAD scoring and explanation-shaped output remain
deterministic `MOCK_SYNTHETIC` behavior: no trained model, dataset, clinical
result or performance claim exists. This milestone adds durable SQLite storage
only to the existing Track-B monitoring write path. There is still no
authentication/RBAC, actual consent lookup, patient-history API, or production
security guarantee.

The approved `/v1` schemas, fixture pack and request/response behavior are
unchanged. Read [CONTRACT_NOTES.md](CONTRACT_NOTES.md) for unresolved contract
questions. The database work uses SQLAlchemy + Alembic, pinned open-source
packages and local SQLite; it requires no Docker, account, paid service or
cloud connection. Database files and SQLite sidecars are git-ignored.

## Local setup and migration ($0)

From the repository root with Python **3.11 or 3.12**:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements-dev.txt
python -m pip check
$env:CARDIOASSIST_DATABASE_URL = "sqlite:///./var/cardioassist.sqlite3"
python -m alembic upgrade head
python -m alembic check
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

On Linux/macOS, activate with `. .venv/bin/activate`. The environment variable
is optional: the same relative SQLite URL is the default. Set a different
`CARDIOASSIST_DATABASE_URL` to choose another location; the application and
Alembic read the same variable. No user-specific absolute path is built into
the code. Do not put credentials in the URL or commit a database file.

Migrations are explicit. The app fails closed at startup if the migration
schema is missing; it never silently creates or upgrades tables. For normal
local development:

```bash
python -m alembic current
python -m alembic history
python -m alembic upgrade head
python -m alembic check
```

`alembic check` verifies that the current revision matches the SQLAlchemy
metadata. Use `alembic downgrade` only against a disposable test database;
never downgrade or delete a developer's existing database. Test migration
downgrade/re-upgrade operations run only in pytest's temporary directories.

## M1b.1 schema and service boundary

The current migration is
`backend/migrations/versions/20261017_01_monitoring_persistence.py`.
`MonitoringRepository` is injected into the existing backend state service;
there is no parallel HTTP schema/model and no new route.

| Implemented entity | Purpose and integrity |
|---|---|
| `monitoring_observation` | Durable Track-B write. A private storage UUID is the database primary key. The public deterministic `observation_id`, request id, patient reference, opaque consent reference, source, UTC timestamp and recorded time are stored. Indexes cover public id and `(patient_ref, observed_at)`. |
| `monitoring_metric` | One child row per non-null accepted metric, with a foreign key to the observation and a unique `(observation_record_id, ordinal)` constraint. The ordinal preserves repeated metric IDs and request order; duplicate metric IDs remain allowed by current B-04 behavior. JSON storage preserves contract-permitted scalar values without coercion. Null means “not measured” and is not stored; zero, booleans and strings retain current semantics. |
| `audit_event` | One successful-write metadata row per observation, in the same transaction. A foreign key and unique observation constraint prevent orphan/multiple success events. It contains IDs, request id, route/type, payload SHA-256 and timestamp—not raw measurements, patient reference or consent reference. The application exposes insertion and read methods only; there is no audit update/delete service method. |

SQLite foreign-key enforcement is enabled per connection, with WAL and a busy
timeout. All database columns and migrations use SQLAlchemy's common dialect
(types such as `String` and `JSON`). SQLite integration is **IMPLEMENTED and
TESTED**; PostgreSQL compatibility is **UNVERIFIED**—no PostgreSQL server or
driver tests were run, and parity is not claimed.

### References intentionally not resolved yet

The existing POST contract requires a non-empty `consent_id`, but the approved
backend only checks that it is present; it does not look up a consent grant.
M1b.1 preserves that exact behavior and stores `patient_ref` and `consent_id`
as opaque synthetic/demo references. Neither is a foreign key in this
migration: there is no `PatientProfile` or `ConsentRecord`, and inventing one
would imply unapproved reference/consent semantics. This is explicitly
**deferred** until the Q7/Q12/consent contract review. No patient identity is
created and no real patient data may be used.

Also **deferred**: `UserAccount`, role/session tables, patient/clinician
profiles, consent lifecycle, clinical feature sets, predictions, medical
history/symptom/survey records, lab documents/extraction/verification,
follow-up/review/notification tables, disease/model registries and
`idempotency_record`. Patient history/read APIs, consent APIs, review APIs and
all other new endpoints remain contract-first M1b work and are not added here.

## What persists today

`POST /v1/monitoring/observations` is the one persistent HTTP path. Existing
validation runs in its current order; the full request is validated before any
write. After the same response body has passed the approved response-schema
validator, a single explicit transaction inserts the observation, its
non-null metrics and its success-audit metadata. If any insert/constraint/commit
fails, SQLAlchemy rolls back the whole transaction; the existing handler
returns its generic `500 internal_error`, and the request does not consume the
runtime idempotency key. Validation failures, conflicts and in-process replays
create no durable success rows. Track-B input never invokes or alters CAD
inference. The CAD POST remains the existing synthetic mock and is not stored
in this slice.

Rows survive application/process restart. There is no history/read HTTP API;
repository reads are internal Python integration methods only. Example
PowerShell request using synthetic data:

```powershell
$payload = @{
  observation = @{
    patient_ref = "pseudo_demo_001"
    observed_at = "2026-10-16T10:25:00Z"
    source = "simulated_wearable"
    consent_id = "consent_mock_001"
    metrics = @(@{ metric_id = "mock_metric_heart_rate"; value = 64; unit = "u_rate" })
  }
} | ConvertTo-Json -Depth 8
$headers = @{ "Idempotency-Key" = "demo-monitor-write-001" }
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/v1/monitoring/observations" `
  -ContentType "application/json" -Headers $headers -Body $payload
```

To confirm a persisted row after stopping and restarting the server, query the
repository from Python (no new HTTP endpoint):

```powershell
python -c "from backend.app.storage.database import Database; from backend.app.storage.monitoring import MonitoringRepository; db=Database(); print(MonitoringRepository(db).list_observations()); db.dispose()"
```

### Idempotency and audit limits (Q8 remains open)

- The tested **24-hour, monotonic-clock** idempotency behavior is preserved
  while one app process is alive: same key + same canonical payload replays
  the original response; changed key use conflicts before semantic checks;
  a replay creates no second database row or success-audit row.
- Q8 is still **OPEN** for formal ratification of the retention window and
  durable store of record. Idempotency keys, response snapshots, attempt
  counters, expiry and in-memory audit snapshots remain RAM-only; this PR does
  not silently choose an idempotency storage policy.
- After restart, runtime state resets as before. A retry may be accepted as a
  new write, and the existing deterministic public observation id can repeat.
  A separate database UUID keeps the durable rows distinct. This is not
  cross-process exactly-once delivery; durable idempotency is deferred to a
  later M1b slice after Q8 review.
- Successful monitoring audit metadata is durable and transactionally coupled
  to its observation. Unexpected 500/error audit IDs remain process-local (a
  database failure cannot reliably audit itself). SQLite append-only behavior
  is an application design rule, **not** PostgreSQL-style `GRANT`/`REVOKE`
  permissions. The repository has no audit update/delete path.
- One process/one worker only. No multi-process/replica transaction guarantee,
  tamper resistance, authentication, authorization, real consent verification,
  PHI protection, rate limit, backup/export procedure or production guarantee.

## Existing HTTP contract (unchanged)

| Method / path | Result | Key |
|---|---|---|
| `POST /v1/predictions/cad-tabular` | 200 deterministic synthetic CAD/XAI envelope | `Idempotency-Key` required |
| `POST /v1/monitoring/observations` | 201 monitoring-only acceptance; durable observation + metrics + success audit | Optional; honored in-process |
| `GET /openapi.json` | Shared OpenAPI with local schemas bundled for offline use | N/A |

Only the two contracted POST operations exist. CDN-backed `/docs` and `/redoc`
pages are disabled. There are no history, model-discovery, review-action,
authentication or audit-query endpoints.

The mock CAD response, error codes, Track A/Track B separation, wearable
rejection, source/consent presence checks, request hashing, response shapes and
fixture pack are unchanged. All monitoring payloads remain Track B; a wearable
observation cannot become a CAD inference feature.

## Tests and independent Windows verification

From the repository root, after activating `.venv`:

```powershell
python -m pip check
python -m alembic upgrade head
python -m alembic check
python -m pytest tests/contracts tests/backend -q -W error
python -m pytest -q -W error
python scripts/verify_sources.py
git diff --check
```

The backend tests use a fresh disposable SQLite database per test, apply the
Alembic migration, and cover migration up/down/re-up on temporary files,
metadata consistency, successful writes/reads, restart durability, rollback,
foreign-key/unique constraints, concurrency/replay, malformed and rejected
inputs, test-database isolation, contract fixtures and synthetic CAD/Track-B
regressions. No migration downgrade or delete is run against a developer's
local database.

## Local restart and cleanup (PowerShell)

1. Stop Uvicorn with `Ctrl+C`; the configured database remains at
   `.\var\cardioassist.sqlite3` by default. Start the server again with the
   same `CARDIOASSIST_DATABASE_URL`; accepted monitoring rows remain.
2. For an intentionally disposable synthetic demo DB only, stop the server
   first and remove the DB plus SQLite sidecars:

   ```powershell
   Remove-Item .\var\cardioassist.sqlite3* -Force -ErrorAction SilentlyContinue
   ```

   **Do not run this cleanup or `alembic downgrade` against any existing
   database you need.** Pytest databases are temporary and cleaned by pytest.

The runtime accepts synthetic/demo inputs only. Do not place actual patient
identifiers or health records in SQLite, source control, logs, fixtures, or
remote AI sessions.
