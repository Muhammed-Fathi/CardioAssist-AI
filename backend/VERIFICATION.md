# M1a.2 verification record

Executed locally on **2026-10-16**, Linux, **Python 3.11.2**, from the
repository root, using the pinned `backend/requirements-dev.txt` environment.
No model, dataset, DB, cloud account or paid service was used.

## Gate before edits

- PR #3: GitHub state **MERGED**, base `main`.
- Merge / remote-main commit:
  `6e677b7924f88f88cbe50a155105cd9c44c0dff0`.
- Final approved PR head:
  `fc2c62b78a84075625555a69372b687d53ab9995`.
- `git diff --exit-code <final-head> origin/main -- shared/contracts tests/contracts .github/workflows/contracts-ci.yml`: **PASS, empty**.
- Working branch initially at that main tip:
  `arena/cae890ca-cardioassist-ai` (Arena-fixed dedicated branch).
- Remote `main` was rechecked after implementation/tests: still the same tip.
- The approved contract/fixture/test/original-workflow paths remain unchanged.

## Final pytest output

Re-run after the maintainer-selected CI template handoff; all counts remain
unchanged. The live TCP fixture run was also repeated: **33/33 supported
steps passed**, plus the explicit LIME-only 503 check.

```text
$ .venv/bin/python -m pip check
No broken requirements found.

$ .venv/bin/python -m pytest tests/contracts -q -W error
........................................................................ [ 52%]
................................................................         [100%]
136 passed in 0.45s

$ .venv/bin/python -m pytest tests/backend -q -W error
........................................................................ [ 30%]
........................................................................ [ 61%]
........................................................................ [ 92%]
.................                                                        [100%]
233 passed in 7.14s

$ .venv/bin/python -m pytest -q -W error
........................................................................ [ 19%]
........................................................................ [ 39%]
........................................................................ [ 58%]
........................................................................ [ 78%]
........................................................................ [ 97%]
.........                                                                [100%]
369 passed in 7.97s
```

**369 passed; zero failures, skips or warnings** (warnings are errors).
The 136 original contract tests are unchanged; the 233 new tests exercise the
FastAPI HTTP boundary independently of the fixture-generating oracle.

### Additional concurrency stress

Repeated the four concurrent HTTP tests ten times:

```text
4 passed, 59 deselected in 0.24s
4 passed, 59 deselected in 0.25s
4 passed, 59 deselected in 0.25s
4 passed, 59 deselected in 0.26s
4 passed, 59 deselected in 0.25s
4 passed, 59 deselected in 0.26s
4 passed, 59 deselected in 0.28s
4 passed, 59 deselected in 0.29s
4 passed, 59 deselected in 0.27s
4 passed, 59 deselected in 0.26s
```

40 additional race-test executions passed. Each test issues 16 concurrent
actual HTTPX/ASGI requests (identical payloads or two competing payloads),
checks the documented response schemas/statuses, one original result, replay
vs conflict behavior, and exactly one success audit/inference/observation as
applicable. The 59 deselected tests are excluded by `-k concurrent` **only in
these focused stress runs**, not skipped from the full suite above.

## Runtime-only, live TCP check (not just the test client)

1. Created an ignored nested venv at `.venv/runtime-check` and installed
   **only** `backend/requirements.txt`; `pip check` passed.
2. Confirmed it imports the app without `pytest`, `httpx`, NumPy, pandas,
   scikit-learn, SHAP or LIME installed.
3. Started:

   ```bash
   .venv/runtime-check/bin/python -m uvicorn backend.app.main:app \
     --host 0.0.0.0 --port 8000 --workers 1
   ```

4. Used Python stdlib `urllib.request` to make real TCP HTTP calls, reading
   the committed fixture files directly (no oracle):

   ```text
   PASS: live Uvicorn/TCP HTTP — 33 exact fixture steps, LIME 503,
   README minimal requests, replay/409, Track-B 201, bundled OpenAPI.
   ```

   All 29 supported fixture scenarios matched exact approved response bodies;
   F-11c explicitly returned 503 without an explanation/fidelity result.
   Both README examples work with omitted `request_id`, producing valid UUIDs.
5. Stopped the smoke-test server cleanly. No long-running deployment remains.

## Other checks

```text
$ python scripts/verify_sources.py
OK sha256: literature_review_original.xlsx
OK sha256: literature_review_status.csv
OK sha256: project_presentation.pdf
OK sha256: project_presentation_speaker_notes.md
OK supervisor audit: 25 papers, statuses {'APPROVED_GREEN': 9,
'MAYBE_PINK': 1, 'MAYBE_ORANGE': 6, 'REJECTED_RED': 9}

$ .venv/bin/python -W error -m compileall -q backend/app tests/backend
PASS (exit 0)
```

- The proposed backend CI is now a **non-executing template** at
  `backend/ci/backend-ci.yml.example`. Its exact intended destination is
  **`.github/workflows/backend-ci.yml`**. It defines Python **3.11 and 3.12**
  jobs with pinned actions/dependencies, strict-warning contract + HTTP tests,
  dependency consistency, source integrity and an artifact-extension guard.
  There are **no changes under `.github/workflows/`** in this PR; the original
  maintainer workflow is unchanged.
- **GitHub Actions status: UNVERIFIED.** The initial push of a new workflow was
  rejected by the GitHub App's permission boundary. The maintainer explicitly
  chose the template/manual-install handoff instead of requesting additional
  permissions. The template cannot execute here: the maintainer must install
  it and inspect actual CI runs (`backend/ci/README.md`). Python 3.12 and
  Windows/device execution were not run in this sandbox. Local results do
  not claim green GitHub Actions. No automatic merge is authorized.
- Remaining contract ambiguities/capability restrictions are reported in
  [CONTRACT_NOTES.md](CONTRACT_NOTES.md), not hidden by test skips or schema edits.
