# Backend CI — non-executing maintainer handoff

**GitHub Actions status: UNVERIFIED.** This directory does not enable any
workflow. The agent's push of a new workflow was rejected because its GitHub
App lacks workflow-write permission. The maintainer explicitly chose this
handoff instead of requesting additional permissions.

## Exact template and destination

- Full, exact YAML content: [`backend-ci.yml.example`](backend-ci.yml.example).
- Current location: **`backend/ci/backend-ci.yml.example`** (non-executing).
- Exact intended installation destination:
  **`.github/workflows/backend-ci.yml`**.
- Existing **`.github/workflows/contracts-ci.yml` must remain unchanged**.

The template uses the same immutable action revisions as the merged contract
workflow, read-only contents permission, Python 3.11/3.12, pinned dependencies,
strict-warning contract + HTTP tests, source-integrity verification and a
narrow prohibited-artifact extension guard. It uses no secrets, paid service,
model, dataset or cloud account. Existing GitHub Actions quota still applies.

## Manual installation — maintainer only

After reviewing the PR/template, use the maintainer's normal workflow-authorized
GitHub session. No extra permission is requested for the agent.

### Option A: GitHub file editor

1. Open this PR's branch, **`arena/cae890ca-cardioassist-ai`**.
2. Create a new file named exactly **`.github/workflows/backend-ci.yml`**.
3. Copy the complete content of `backend/ci/backend-ci.yml.example` unchanged.
   Comments calling it a template are harmless; a byte-for-byte copy is valid.
4. Commit the new file to this same PR branch using the maintainer's session.
   Do **not** edit `contracts-ci.yml` and do **not** merge just to install CI.
5. Inspect the actual PR checks for **Mock backend (Python 3.11)** and
   **Mock backend (Python 3.12)**, plus the original contract workflow.
   Confirm their jobs ran against the latest reviewed commit and passed.

### Option B: Maintainer's local checkout

From the repository root, **already on this PR's branch**, after reviewing the
copy and using the maintainer's ordinary workflow-authorized GitHub session:

```bash
cp backend/ci/backend-ci.yml.example .github/workflows/backend-ci.yml
# PowerShell equivalent:
# Copy-Item backend/ci/backend-ci.yml.example .github/workflows/backend-ci.yml

git add .github/workflows/backend-ci.yml
git commit -m "ci: enable mock backend validation"
git push origin arena/cae890ca-cardioassist-ai
```

Inspect the PR checks as above. There is no merge command in these steps.

## Until then

- **UNVERIFIED** means no backend GitHub Actions result is claimed. A locally
  validated template, a successful local test suite, a push or a PR URL is not
  evidence that the new workflow executed.
- The unchanged original contract workflow may run on the PR, but it does not
  replace the backend HTTP suite. Its result is also not claimed without
  inspecting an actual GitHub run.
- Local confirmation uses:

  ```bash
  python -m pip install -r backend/requirements-dev.txt
  python -m pip check
  python -m pytest tests/contracts -q -W error   # 136 tests
  python -m pytest tests/backend -q -W error     # 233 tests
  python -m pytest -q -W error                  # 369 combined
  ```

- See [`../VERIFICATION.md`](../VERIFICATION.md) for local tests and the live
  TCP run of all 33 supported HTTP fixture steps. See
  [`../CONTRACT_NOTES.md`](../CONTRACT_NOTES.md) for unresolved contract
  questions. Human review/approval is still required; M1a.3 has not started.
