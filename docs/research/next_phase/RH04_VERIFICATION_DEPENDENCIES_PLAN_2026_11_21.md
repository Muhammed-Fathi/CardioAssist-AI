# Dependency reconciliation for RH-04 verification

**Document ID:** CAI-RH04-DEPS-v2 (supersedes v1)
**Status:** PLAN, plus measured results from reconciling the repository's own pins.

---

## 1. Correction to v1

v1 of this document proposed `openpyxl==3.1.5` and `jsonschema==4.23.0` as new
additions. **That was wrong in approach**, even though the versions happened to
match: the repository already carries reviewed, pinned requirement files, and
proposing versions independently risks drifting from them.

The correct action is to **use the existing files**. This document does that.

## 2. The reviewed requirement files, reconciled

| file | scope | used here? |
|---|---|---|
| `research/uci412/requirements.txt` | numpy/scipy/sklearn/joblib/threadpoolctl/openpyxl/pytest | **yes** — the scientific core |
| `research/experiments/requirements.txt` | same core minus openpyxl | superseded by the uci412 file (subset) |
| `research/experiments/requirements-oracle.txt` | `mpmath==1.4.1`, test-only oracle | **yes** |
| `research/audit/requirements.txt` | openpyxl only, for the dataset audit toolchain | no — its pins are a subset already installed |
| `tests/contracts/requirements.txt` | jsonschema, openapi-spec-validator, PyYAML, referencing, pytest | **yes** |
| `backend/requirements.txt` | FastAPI/SQLAlchemy/alembic | **no** — backend is a later roadmap stage |
| `backend/requirements-dev.txt` | backend + contracts + httpx | no — same reason |

No version was invented. No file was edited. Nothing was added to any
`requirements*.txt`.

## 3. Exact commands used (measured)

```bash
python3 -m venv /tmp/venv-clean
/tmp/venv-clean/bin/pip install \
  -r research/uci412/requirements.txt \
  -r research/experiments/requirements-oracle.txt \
  -r tests/contracts/requirements.txt
/tmp/venv-clean/bin/pip check
```

**Measured `pip check` output:** `No broken requirements found.`

**Measured installed versions:** Python 3.11.2, numpy 1.26.4, scipy 1.15.3,
scikit-learn 1.6.1, mpmath 1.4.1, openpyxl 3.1.5, pytest 9.0.3.

## 4. What the 35 errors and 1 failure actually were

Round 10.3 reported `35 errors, 1 failure` in `tests/experiments` and described
them as pre-existing. That was accurate but **misleading by omission**: they were
not "known failures", they were **unexecuted coverage**. Every one traced to
`importlib.metadata.PackageNotFoundError: openpyxl`.

With `research/uci412/requirements.txt` installed:

| file | before | after |
|---|---|---|
| `test_research_evidence.py` | 28 errors, 1 failure | **passes** |
| `test_rh04_report_assembly.py` | 7 errors | **passes** |
| both together | 35 errors + 1 failure | **47 passed** |

And the full wider suite went from `1336 passed / 1 failed / 35 errors` to:

```
1380 passed, 2 skipped in 1376.30s
```

**No file is excluded from the final verification suite.** Round 10.3 ran the
wider suite with `--ignore=` on those two files; that exclusion is withdrawn.

## 5. Test tiers and their real status

| tier | command | measured |
|---|---|---|
| focused RH-04 V2 | `pytest tests/experiments/test_rh04_v2_reference.py` | **276 passed** (delivery tree) |
| experiments + contracts | `pytest tests/experiments tests/contracts` | **1691 passed, 2 skipped** (delivery tree) |
| contracts alone | `pytest tests/contracts` | **306 passed** |
| backend | `pytest tests/backend` | **not run — out of scope** |

The 2 skips are native-Windows-only tests on a Linux host, each with a stated
reason. They are not hidden.

## 6. Backend: deliberately out of scope

`tests/backend/` needs `alembic` **and a database fixture**. Adding a database
tier to this workstream would overstate what has been verified about RH-04, which
touches no backend code. Recommendation: cover it in a later roadmap stage with
its own dependency and fixture plan, under separate authorization.

**This is not a dismissal.** It is an explicit, named gap.

## 7. Remaining dependency gap

There is still **no root-level pinned environment file** for the whole repository.
Each subsystem has its own reviewed pins, and today they are mutually consistent
(numpy/scipy/sklearn pins agree across `research/uci412` and
`research/experiments`), but nothing enforces that agreement mechanically.

That is a real gap. It is **not fixed here**, because introducing a root
requirements file is a repository-structure decision that belongs to the
maintainer, not to an acceptance-corrective round.

## 8. Reviewer commands

```bash
# Minimal: scientific core + oracle. Sufficient for the focused suite.
python -m pip install -r research/uci412/requirements.txt \
                       -r research/experiments/requirements-oracle.txt
python -m pip check
PYTHONPATH=. python -m pytest tests/experiments/test_rh04_v2_reference.py -q

# Full research-verification tier: adds the contract validators.
python -m pip install -r tests/contracts/requirements.txt
python -m pip check
PYTHONPATH=. python -m pytest tests/experiments tests/contracts -q
```

Expected on the delivery tree: `pip check` clean, `276 passed`, then
`1691 passed, 2 skipped`.
