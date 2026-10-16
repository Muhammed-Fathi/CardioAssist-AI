# M1a.3 — React + Flutter integration handoff (plan only)

**Do not start this work until a human reviews/merges M1a.2 and explicitly
authorizes M1a.3.** This file does not approve another milestone, change an API
schema, close scientific gates or implement a frontend.

## 1. Freeze the reviewed integration baseline

1. Verify the M1a.2 PR is merged into `main`; read its final approved diff,
   `AGENTS.md`, `docs/DECISIONS.md`, `backend/CONTRACT_NOTES.md` and the shared
   OpenAPI/schemas/fixtures. Work on the next session's dedicated branch.
2. Before claiming a green integration baseline, have the maintainer install
   `backend/ci/backend-ci.yml.example` at `.github/workflows/backend-ci.yml`
   and inspect actual CI runs (`backend/ci/README.md`). GitHub Actions remains
   **UNVERIFIED** until then. Ask the reviewer to resolve or explicitly carry
   forward notes B-01–B-04,
   A-01, G-02 and X-01. Do not let a TypeScript/Dart client silently tighten
   the permissive Track-B scalar types or fabricate a LIME panel/result.
3. From the repo root, run:

   ```bash
   python -m venv .venv
   . .venv/bin/activate
   python -m pip install -r backend/requirements-dev.txt
   python -m pytest tests/contracts tests/backend -q -W error
   python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 1
   ```

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
   key on retry. Do not claim a consent record was verified or that data will
   survive a server restart. No history/batch-sync endpoint exists yet.
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
- Use the Python test-visible in-memory audit snapshots to prove one event
  per accepted logical write. Do **not** invent an HTTP audit/history API or
  pretend the read-only review state is a completed clinician-review workflow.
- Record emulator/physical-device evidence (or explicit UNVERIFIED limits),
  rendered mandatory wording, commands and full test output in the M1a.3 PR.
- No training/downloads, real data, production auth/RBAC, persistent database,
  risk thresholds/alerts, paid services, LIME fabrication or unreviewed API
  changes. Keep other gates P-1–P-6 open.
- Open one scoped PR targeting `main`, then stop for human review; never
  self-approve or merge.
