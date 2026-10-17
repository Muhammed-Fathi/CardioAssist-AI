# Backend CI status and local verification

The maintainer has installed the backend workflow at
[`.github/workflows/backend-ci.yml`](../../.github/workflows/backend-ci.yml).
It is an executing GitHub Actions workflow, not merely a proposed template.
The existing [`contracts-ci.yml`](../../.github/workflows/contracts-ci.yml)
remains a separate workflow. Neither workflow file is changed by this cleanup.

**GitHub Actions results are not asserted here.** Workflow presence does not
prove that a run was triggered, completed, or passed for a particular commit.
Review the Checks tab for the PR and confirm each result is attached to the
latest commit before reporting CI status.

## What the workflow covers

The backend workflow tests Python 3.11 and 3.12, installs the pinned backend
and contract-test dependencies, runs dependency consistency checks, runs
contract and HTTP backend tests with warnings treated as errors, verifies the
source-integrity baseline, and rejects a narrow set of prohibited artifact
extensions. The extension guard is not a secrets or PHI scanner. Dependency
installation requires package-index access; the tests do not require a model,
dataset, database, cloud service, credentials, or paid service.

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

Human review and explicit authorization are required before moving beyond the
mock integration milestone. Workflow CI passing would validate software
checks only; it would not establish model validity or clinical approval.
