# Dependency installation plan for wider-suite verification

**Document ID:** CAI-RH04-DEPS-v1
**Status:** PLAN. Not executed in this round.

---

## 1. Why this document exists

Running the wider `tests/experiments` suite in the review sandbox produces **35
collection/setup errors and 1 failure**, all from dependencies absent from the
minimal scientific virtualenv. These are **not** passing tests and **not**
irrelevant noise; they are unexecuted coverage. Reporting them as "pre-existing"
is accurate but insufficient — pre-existing gaps are still gaps.

## 2. What is installed today (deliberately minimal)

| package | version | why |
|---|---|---|
| Python | 3.11.2 | host interpreter |
| numpy | 1.26.4 | pinned for the Lane B matrix |
| scipy | 1.15.3 | pinned |
| scikit-learn | 1.6.1 | the version `reify` asserts against |
| mpmath | 1.4.1 | Decimal/arbitrary-precision diagnostics |
| pytest | 9.0.3 | runner |
| threadpoolctl | latest | resident-kernel reporting |

`shap` is deliberately **not** installed: `ai/explainability.py` computes SHAP
in-house, and the portable lane must not depend on it.

## 3. What is missing, and what it blocks

| package | blocks | consequence |
|---|---|---|
| `openpyxl` | `test_research_evidence.py` (28 errors, 1 failure), `test_rh04_report_assembly.py` (7 errors) | Excel-evidence import/export tests never run |
| `jsonschema` | `tests/contracts/` | schema-contract tests never run |
| `alembic` | `tests/backend/` | migration tests never run |

The error is `importlib.metadata.PackageNotFoundError: openpyxl`, raised from a
fixture that records evidence-file provenance. It is a *metadata* lookup, not an
import of the library, so installing the distribution is sufficient.

## 4. Proposed installation (requires maintainer approval)

### 4.1 Pinned additions for the research-evidence tier

```
openpyxl==3.1.5
jsonschema==4.23.0
```

These are test/evidence-only. They are **not** runtime dependencies of `ai/`, and
nothing in the portable lane imports them.

### 4.2 Backend tier (separate decision)

```
alembic==1.13.3
```

`tests/backend/` also needs a database fixture. That is a larger commitment than
this round should make, and it is explicitly **out of scope** here: the portable
acceptance work does not touch the backend, and adding a database tier to the
verification story would misrepresent what has been verified.

Recommendation: cover `tests/backend/` in a **separate** verification round with
its own dependency and fixture plan.

## 5. What this round can and cannot claim

| claim | supported? |
|---|---|
| Focused V2 suite fully green — 263 passed, 0 failed | **yes** |
| Wider experiments suite green apart from dependency gaps — 1325 passed, 2 skipped | **yes** |
| Wider experiments suite fully green | **no** — 35 errors + 1 failure from missing `openpyxl` |
| Contract tests green | **no** — `jsonschema` absent, never executed |
| Backend tests green | **no** — `alembic` absent and no DB fixture |

## 6. Verification commands for a reviewer

```bash
# focused suite (fully green today)
PYTHONPATH=. python -m pytest tests/experiments/test_rh04_v2_reference.py -q

# wider suite minus the two dependency-blocked files
PYTHONPATH=. python -m pytest tests/experiments -q \
  --ignore=tests/experiments/test_rh04_report_assembly.py \
  --ignore=tests/experiments/test_research_evidence.py

# after installing §4.1, this should be green
PYTHONPATH=. python -m pytest tests/experiments -q
```

The absence of a root `requirements.txt` is itself a gap: there is no pinned,
reviewable environment definition for this repository. That is noted, not fixed
here, because introducing one is a repository-structure decision.
