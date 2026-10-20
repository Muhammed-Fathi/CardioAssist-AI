# Backend CI status and local verification

The maintainer-installed backend workflow is at
[`.github/workflows/backend-ci.yml`](../../.github/workflows/backend-ci.yml).
It is an executing GitHub Actions workflow, not merely a proposed template;
its backend test command now includes the M1b.1 SQLite migration/persistence
suite. The existing [`contracts-ci.yml`](../../.github/workflows/contracts-ci.yml)
remains separate and unchanged.

**GitHub Actions results are not asserted here.** Workflow presence does not
prove that a run was triggered, completed, or passed for a particular commit.
Review the Checks tab for the PR and confirm each result is attached to the
latest commit before reporting CI status.

## What the workflow covers

The backend workflow tests Python 3.11 and 3.12, installs the pinned backend
and contract-test dependencies, runs dependency consistency checks, runs the
contract and backend suites with warnings treated as errors (including the
SQLite migration/persistence tests), verifies the source-integrity baseline,
and rejects a narrow set of prohibited artifact extensions. The extension
guard is not a secrets or PHI scanner. Dependency installation requires
package-index access; tests use isolated temporary SQLite files but require
no external database service, model, dataset, cloud service, credentials or
paid service.

`backend-ci.yml.example` is retained as historical/reference material only.
The installed workflow under `.github/workflows/` is authoritative; do not
copy the example over it or use the example as evidence of a CI result.

## Local verification

From the repository root, with Python 3.11 or 3.12:

```bash
python -m pip install -r backend/requirements-dev.txt
python -m pip check
python -m pytest tests/contracts -q -W error
python -m pytest tests/backend -q -W error
python -m pytest -q -W error
python scripts/verify_sources.py
```

A local pass is useful verification but is not a GitHub Actions result.

## Scope and deployment status

- **Synthetic mock functionality:** this repository's backend returns
  deterministic mock outputs and mock monitoring acceptance responses. It
  does not train, load, or use a real AI model or real patient data.
- **Research deployment:** the code is a research prototype for local and
  controlled synthetic-data integration testing. Research deployment requires
  separate review, governance, infrastructure, and operational controls.
- **Clinical deployment:** not approved or implemented. No clinical validity,
  patient-care use, production readiness, or diagnostic capability is claimed.

D-045 authorizes the M1b.1 persistence slice only; further implementation
requires separate human authorization. Workflow CI passing would validate
software checks only; it would not establish model validity, research-gate
approval or clinical approval. Current-session GitHub check status is reported
separately and is not inferred from this workflow's presence.
