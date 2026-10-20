# M1a.3 — React + Flutter integration handoff (preserved plan; deferred)

**Status under D-045 (2026-10-17): M1a.3 is deferred/resequenced, not
cancelled or completed.** M1b.1 is the first authorized implementation
slice. Resume this client work only when the maintainer separately schedules
and authorizes it. This file preserves the future plan; it does not approve
another milestone, change an API schema, close scientific gates or implement a
frontend. React and Flutter remain thin local integration/demo clients.

## 1. Freeze the reviewed integration baseline

1. After M1a.3 is separately authorized, verify that the reviewed M1b.1
   persistence slice is present in the selected `main` baseline; read the
   current `AGENTS.md`, `docs/DECISIONS.md`, `backend/CONTRACT_NOTES.md`,
   backend README and shared OpenAPI/schemas/fixtures. Work on the next
   authorized branch and do not assume the current open PR is merged.
2. The installed `.github/workflows/backend-ci.yml` is distinct from the
   historical example under `backend/ci/`. Before claiming a green integration
   baseline, inspect actual CI runs tied to the latest reviewed commit
   (`backend/ci/README.md`); workflow presence alone proves no result. Carry
   B-01–B-04, G-02 and X-01 explicitly, and note that A-01's technical
   correction is complete (PR #7/#8 merged). Do not let a TypeScript/Dart
   client silently tighten permissive Track-B scalar types or fabricate a
   LIME panel/result.
3. From the repo root, run:

   ```bash
   python -m venv .venv
   . .venv/bin/activate
   python -m pip install -r backend/requirements-dev.txt
   python -m pip check
   python -m alembic -c alembic.ini upgrade head
   python -m alembic -c alembic.ini check
   python -m pytest tests/contracts tests/backend -q -W error
   python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 1
   ```

   For database URL, working directory, Windows PowerShell and cleanup
   details, follow `backend/README.md`. Runtime idempotency/replay state remains
   in-memory; the monitoring observation, non-null metrics and success-audit
   metadata persist in SQLite.

4. Use `GET /openapi.json` (self-contained/offline refs) and the committed
   JSON Schemas as the sole wire definitions. If generating DTOs, pin the
   generator and review its handling of JSON Schema 2020-12 conditionals.
   Do not create a conflicting unreviewed client-side API contract.

## 2. Thin React + TypeScript clinician path

1. Scaffold the approved React/TypeScript app in `frontend/clinician-web/`
   using a pinned zero-cost toolchain (e.g. Vite), lock dependencies, and add
   a typed `/v1` HTTP client with tests. No full dashboard or auth system yet.
2. Use **relative `/v1/...` browser URLs**. Configure the dev server's proxy
   to the backend and bind it to `0.0.0.0`; explicitly permit the controlled
   `.e2b.app` preview host when needed. Server-side proxy targets may use the
   sandbox's backend loopback address; browser code must never try to reach
   another service at `localhost`/`127.0.0.1`. Do not solve this with a broad
   credentialed CORS policy or production deployment.
3. Build one synthetic-record form/action that posts a valid mock CAD payload
   with an `Idempotency-Key`. Keep that key for retries of the same write;
   choose a new key when payload/model/schema changes. Display the existing
   400/409/422/503 error envelopes without inventing medical interpretations.
4. Render the target name/definition/provisional status, MOCK disclaimer,
   model/preprocessing/calibration/schema/config ids, validation status,
   score rendering label, missing values/warnings, `audit_id`, replay status
   and read-only `pending_review`. There is no review-action endpoint yet.
5. Render synthetic SHAP attributions **separately on the log-odds scale**.
   Never add them to the mock calibrated score, display percentage points,
   attach advice, claim causality, or label a score a personal disease risk.
   Both score types forbid `%`; the mock calibrated branch needs synthetic
   cohort context. Do not show a computed LIME/fidelity result.
6. Add component/snapshot tests for mandatory target/disclaimer/status copy,
   uncalibrated and mock-calibrated rendering, optional missing values,
   replay with the original audit id, 409 conflict, 422 wearable rejection,
   validation errors and 503 unavailable/LIME-only models.

## 3. Thin Flutter Android patient path

1. Verify Flutter + Android SDK tooling on a team machine, record versions,
   and scaffold in `frontend/patient-mobile/` with pinned dependencies.
   Test on an emulator and one physical Android device at $0. If unavailable,
   report the unverified device path; no cloud emulator or app-store account
   is required. iOS remains gated/out of this slice.
2. Configure the API origin at build/run time, not in committed credentials:
   emulator example `--dart-define=API_BASE_URL=http://10.0.2.2:8000`;
   physical device uses the development machine's reachable LAN address or a
   controlled HTTPS backend preview. A phone's `localhost` is **the phone**.
   Keep any HTTP cleartext allowance debug-only; do not weaken release policy.
3. Add a typed client and one screen that submits a **synthetic** Track-B
   observation with a prototype pseudonymous ref, demo consent ref, explicit
   source (`manual_entry` or visibly simulated wearable), mock metric ids
   and placeholder units. Do not collect real health records or attach a
   real wearable adapter.
4. Show 201 acceptance, observation id, recorded count, source/synthetic
   labeling, disclaimer and errors. Preserve a logical write's idempotency
   key on retry. The monitoring observation, non-null metrics and success-audit
   metadata persist across restart, but the 24-hour idempotency cache remains
   process-local; do not promise durable replay or exactly-once behavior after
   restart. Do not claim a consent record was verified. No history/batch-sync
   endpoint exists.
5. The patient screen must not call CAD inference from monitoring values or
   show a Track-A personal score. Monitoring arrivals/changes must not trigger
   CAD reassessment. Full offline queue/history/consent lifecycle belongs to
   the separately reviewed M1b contract/work, not a fabricated endpoint.
6. Add Dart client/widget tests for the actual JSON fields, 201 first/replay,
   preserved observation id, consent-required/unknown-metric/unit/range errors,
   source/disclaimer labels, and absence of CAD output/actions.

## 4. Shared acceptance checks and delivery

- Run all backend/contract tests plus React client/component tests and Flutter
  client/widget tests with pinned dependencies. Keep fixture-oracle tests
  separate from actual HTTP/client tests.
- Demonstrate: React → synthetic prediction → retry with same audit id;
  Flutter → monitoring → retry with same observation id; changed payload under
  a used key → 409; wearable → CAD endpoint → 422 and no score. Prove that
  monitoring does not increase the backend inference counter.
- Use isolated test/database inspection to prove exactly one durable,
  metadata-only success-audit row for the first accepted monitoring write and
  none on an in-process replay. Do **not** invent an HTTP audit/history API or
  pretend the read-only review state is a completed clinician-review workflow.
  Error-audit snapshots and CAD-write auditing remain outside M1b.1's durable
  scope.
- Record emulator/physical-device evidence (or explicit UNVERIFIED limits),
  rendered mandatory wording, commands and full test output in the M1a.3 PR.
- M1a.3 may only add the thin client paths; it must not expand M1b.1's
  persistence schema, retention/idempotency policy or API surface without a
  separate authorization. No training/downloads, real data, production
  auth/RBAC, risk thresholds/alerts, paid services, LIME fabrication or
  unreviewed API changes. Keep other gates P-1–P-6 open.
- Open one scoped PR targeting `main`, then stop for human review; never
  self-approve or merge.
