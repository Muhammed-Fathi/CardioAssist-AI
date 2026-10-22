# M2b.2 — Synthetic-Only Preprocessing Engineering Handoff

**Updated:** 2026-10-23
**Status:** Implementation and synthetic verification complete; clinician-intake
contract is a separate design proposal only. Gate PT P-3 remains **CLOSED**.
No real patient data, real dataset files, model training, or production API
changes were used or authorized.

## IMPLEMENTED

- Added an immutable field registry and reusable validation rules to
  `research/intake/synthetic_stage_validator.py`, extending the existing M2b.1
  validator rather than creating a second intake validator.
  - Fixed source-code order for UCI-45-style categorical fields.
  - Exact stage-specific predictor allowlists; unknown fields, targets,
    angiography fields, identifiers, sites and wearables fail closed.
  - Exact unit-token validation without conversion. No unit is asserted for
    `oldpeak`.
  - `age`, `trestbps`, `chol` and `thalach` require positive finite values;
    `chol=0` and `trestbps=0` cannot masquerade as measurements. Categorical
    zero codes and `oldpeak=0` remain valid; signed finite `oldpeak` is not
    clipped.
  - Explicit `not_measured`, `not_available_at_time`, and `unknown` reasons
    for null measurements; omitted stage fields require `not_provided`.
  - `_finite_real` treats integers that overflow `math.isfinite` conversion as
    invalid, so validation, fit, and transform raise controlled
    `IntakeValidationError` rather than leaking `OverflowError`.
- Added `research/intake/synthetic_preprocessing.py`, using only the Python
  standard library.
  - One-hot category dimensions/order are fixed by the field registry, not
    inferred from the sample. Unknown categories fail by default; the explicit
    synthetic-test-only indicator policy adds a separate unknown bit.
  - Numeric missing values use medians learned only from the passed synthetic
    training records. A numeric field with no observed synthetic training
    value fails closed. No holdout argument exists on `fit`.
  - Transforms include per-field missing flags and reason indicators, produce
    a deterministic immutable numeric vector, preserve valid zero and signed
    `oldpeak`, and expose no identifier, target, prediction, or explanation.
  - Input mappings are read-only; no mutation, I/O, model, or database behavior.
- Added a standalone versioned proposal at
  `shared/contracts/proposals/clinician_intake_stage.v0.1.md`; it is not wired
  into OpenAPI or a runtime route.
- Updated intake/test documentation and added synthetic-only safety and
  training/holdout tests.

## TESTED

Python 3.11.2 was available. All commands below completed successfully on that
interpreter; test fixtures are invented software values and contain no
real-patient rows. An earlier focused run found one fixture-setup failure
(stale cholesterol unit after marking that value missing); the fixture was
corrected and the focused suite was rerun successfully.

| Command | Result |
|---|---:|
| `.venv/bin/python -m pytest tests/audit/test_synthetic_stage_intake_safety.py tests/audit/test_synthetic_preprocessing.py -q -W error` | **122 passed** |
| `.venv/bin/python -m pytest tests/audit -q -W error` | **218 passed** |
| `.venv/bin/python -m pytest tests/contracts tests/backend -q -W error` | **620 passed** |
| `.venv/bin/python -m pytest -q -W error` | **838 passed** |
| `.venv/bin/python -m pip check` | **No broken requirements** |
| `.venv/bin/python scripts/verify_sources.py` | **PASS**; 4/4 source-material hashes verified; supervisor classification integrity checked (25 papers) |
| Audit CLI `check-auth`, `verify-ignore`, `dry-run`, `self-test` | **PASS**; no data rows emitted; synthetic self-test originals byte-identical; Gate PT reported closed |
| `python -m compileall -q research/intake tests/audit/test_synthetic_preprocessing.py tests/audit/test_synthetic_stage_intake_safety.py` | **PASS** |
| `git diff --check` | **PASS** |

Python 3.12 was **not available in this execution environment**, so direct
3.12 execution was not performed. The maintainer's PR review reports all three
workflows green for the prior commit `ae4d8d2`, including Python 3.11/3.12 matrix
jobs. That result predates this overflow fix; this follow-up commit's remote CI
status must be checked separately. The status-check API was not accessible to
the agent integration during this session (HTTP 403).

## PROPOSED — NOT APPROVED OR IMPLEMENTED

The clinician-intake proposal defines four cumulative stages, field types,
source codes, proposed units, required/optional semantics, missingness,
zero safeguards, errors, and synthetic request/response examples. It describes
pre-angiography CAD-presence intake (not 30-day event risk) and the compatibility
boundary with the current CAD mock and Track-B monitoring.

No existing `/v1` OpenAPI schema, endpoint behavior, backend, frontend,
database migration, approved fixture, or mock contract was changed. The
existing `POST /v1/predictions/cad-tabular` remains MOCK/SYNTHETIC and
unchanged; wearable observations remain separate under
`/v1/monitoring/observations` and are never CAD predictors.

## Future model connection

Only after a separately approved feature schema and frozen Gate PT protocol,
a model adapter could validate the intake stage, fit preprocessing inside each
training fold, and transform its corresponding holdout with those training-fit
parameters unchanged. The fixed category order avoids sample-dependent
vocabulary; the current numeric median imputation is a software foundation
only. This milestone did not add model-specific scaling, feature selection,
training, evaluation, calibration, explanations, or serving.

## Compatibility, limitations, and blockers

- The synthetic validator now requires an explicit `not_provided` reason for
  an omitted optional field. No production callers of this prototype exist;
  future callers must follow its updated local input contract.
- UCI-45-style source codes and unit tokens are software-test conventions, not
  a ratified clinical dictionary. `oldpeak`'s unit, measurement timing,
  numeric ranges, and source-specific zero semantics remain unresolved.
- The candidate panel `age, sex, cp, trestbps, restecg` is not an approved
  model feature set. Laboratory and exercise measurements remain optional,
  separately staged candidates.
- Keep UCI-412 and UCI-411 recognized as representations of the same
  303-patient cohort. Do not pool datasets or harmonize labels automatically.
- The scientific target, exactly-50% boundary, source-label compatibility,
  predictor timing, statistical adequacy, external validity, calibration,
  fairness, and clinical usefulness remain unresolved. No evidence of
  performance or clinical safety was produced.
- Gate PT P-3 remains CLOSED. No real-data fitting, feature selection, tuning,
  validation, evaluation, calibration, SHAP/LIME, publication, or clinical
  claims are authorized. D-046 read-only audit authorization is not a training
  authorization.

## Next proposed milestone (not authorized by this handoff)

**M2b.3 — Maintainer review of the clinician-intake v0.1 proposal and a
separate decision on whether to authorize a standalone versioned contract
schema/fixture implementation.** Acceptance criteria should include explicit
maintainer authorization, contract/schema review, synthetic-only contract tests,
and confirmation that `/v1`, frontend, persistence, and model behavior remain
untouched unless separately authorized. Proposal acceptance alone must not
open Gate PT or authorize real-data processing.
