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

## Historical pytest output (2026-10-16)

The output below records the original M1a.2 verification before this security
and documentation cleanup. Its counts are a historical snapshot, not the
current PR's final results. Current cleanup verification is recorded in the
follow-up section at the end of this file.

At that time, the live TCP fixture run passed **33/33 supported steps**, plus
the explicit LIME-only 503 check.

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

- **Historical CI handoff (at the time of the original verification):** the
  backend workflow existed only as `backend/ci/backend-ci.yml.example`; the
  then-current note said the maintainer still needed to install it. That
  handoff is superseded. The maintainer has since installed
  `.github/workflows/backend-ci.yml`; see the current status in
  [`ci/README.md`](ci/README.md).
- This record does not claim GitHub Actions passed for the current cleanup PR.
  Inspect actual checks tied to the latest reviewed commit. Python 3.12 and
  Windows/device execution were unavailable in this original sandbox run.
  Local results do not imply green GitHub Actions. No automatic merge is
  authorized.
- Remaining contract ambiguities/capability restrictions are reported in
  [CONTRACT_NOTES.md](CONTRACT_NOTES.md), not hidden by test skips or schema edits.

## Security and contract cleanup follow-up (2026-10-17)

### Dependency findings

- `anyio==4.12.1` was affected by [GHSA-82r6-8w77-94w6 / CVE-2026-63374]
  (incorrect IDNA handling in `TLSStream`; patched in 4.14.2). Exploitation
  requires a TLS connection to a non-ASCII hostname whose connection has been
  redirected. This mock backend makes no outbound TLS connections, so the
  vulnerable path was not exercised by its current code, but AnyIO is a
  runtime dependency and was upgraded to `4.14.2`.
- `starlette==0.52.1` was below fixes for five audited advisories: malformed
  Host URL-path poisoning (GHSA-86qp-5c8j-p5mr / CVE-2026-48710; fixed 1.0.1),
  `HTTPEndpoint` method dispatch (GHSA-x746-7m8f-x49c / CVE-2026-48817; fixed
  1.1.0), Windows `StaticFiles` UNC/SMB credential exposure
  (GHSA-wqp7-x3pw-xc5r / CVE-2026-48818; fixed 1.1.0), malformed path URL
  hostname poisoning (GHSA-jp82-jpqv-5vv3 / CVE-2026-54282; fixed 1.3.0), and
  ignored URL-encoded form parser limits (GHSA-82w8-qh3p-5jfq / CVE-2026-54283;
  fixed 1.3.1). Current routes are FastAPI operations, not `HTTPEndpoint`;
  the app does not mount `StaticFiles`, parse form bodies, or make
  security-sensitive decisions based on `request.url`. Those conditions make
  these particular exploit paths inapplicable to the current app, but the
  Starlette code is on the HTTP stack. It was upgraded to `1.3.1`, the smallest
  audited release covering the set. A malformed-Host URL-inspection regression
  test now checks that `request.url.path` and `.hostname` fall back safely.
- `pytest==8.3.4` was affected by [GHSA-6w46-j5rx-g56g / CVE-2025-71176]
  (unsafe pytest temporary-directory handling on UNIX for pytest through
  9.0.2; patched in 9.0.3). The attack requires a hostile local user able to
  interact with the test runner's `/tmp` area; pytest is test-only here. It was
  upgraded to `9.0.3` and its newly required `Pygments==2.21.0` dependency was
  pinned.
- Starlette 1.3.1 deprecates its legacy HTTPX TestClient adapter. To keep
  `-W error` meaningful rather than suppress the warning, test dependencies
  now pin `httpx2==2.13.1`, `httpcore2==2.13.1`, and `truststore==0.10.5` for
  Starlette's TestClient. `httpx==0.28.1` / `httpcore==1.0.9` remain pinned for
  separate async ASGI integration tests. FastAPI 0.135.4 requires Starlette
  `>=0.46.0`; Starlette 1.3.1 requires Python `>=3.10`, satisfying the
  repository's Python 3.11/3.12 support range. This combination passed local
  Python 3.11 tests and dependency resolution.

The full pinned backend + test requirements were checked using `pip check`
(**no broken requirements**) and `pip-audit` (**no known vulnerabilities**).
The audit was also run directly against `tests/contracts/requirements.txt`;
no vulnerabilities were reported. These are point-in-time advisory database
results, not a guarantee against future advisories.

### Current local verification

Executed with Python **3.11.2**. Python 3.12 is not installed in this sandbox;
that leg is left for the installed GitHub Actions matrix/maintainer review.

```text
pip check: No broken requirements found
pytest tests/contracts -q -W error: 136 passed
pytest tests/backend -q -W error: 234 passed
pytest -q -W error: 370 passed
pip-audit -r backend/requirements-dev.txt: No known vulnerabilities found
pip-audit -r tests/contracts/requirements.txt: No known vulnerabilities found
scripts/verify_sources.py: PASS
compileall -W error: PASS
```

The backend suite includes the existing HTTP/ASGI integration tests and the
new malformed-Host regression. No GitHub Actions result is claimed for this
PR; verify the actual checks against its final commit. No `.github/workflows/`
file was changed.
