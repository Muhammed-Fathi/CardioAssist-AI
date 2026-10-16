# FastAPI mock backend — Phase 1 / M1a.2

**MOCK / SYNTHETIC ONLY. Research prototype, not a diagnosis, real patient
risk/measurement, clinical model, or production service.** No model or dataset
is trained, loaded, downloaded or required. No database, authentication, RBAC,
clinical alert thresholds, UI or cloud integration is implemented.

PR #3's merged `/v1` definitions are reused without editing their schemas,
registries, fixtures or tests. Read [CONTRACT_NOTES.md](CONTRACT_NOTES.md) for
explicit ambiguities and compatibility choices, including Track-B values and
live LIME unavailability. Those notes are part of the review, not silent API
redesigns.

## Local setup ($0, no Docker or accounts)

From the **repository root**, with Python **3.11 or 3.12**:

```bash
python -m venv .venv
. .venv/bin/activate            # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
python -m pip check
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

Dependency installation needs PyPI access once; running the service and tests
needs no outbound network, paid service, dataset, model artifact or account.
Runtime and test dependencies (including transitive packages) are pinned;
shared validator pins match the existing contract-test environment.
The verified local environment is Linux/Python 3.11.2. CI also targets Python
3.12; Windows/Android/team-machine execution must be verified on those devices.

**Use exactly one worker.** All state is in process memory. Multiple workers
or replicas do not share idempotency, observations or audit state. A restart,
reload or fresh `create_app()` loses everything. Do not use this unauthenticated
server for real records or expose it as a public clinical service. Binding to
`0.0.0.0` allows a controlled LAN/preview demo; use only synthetic inputs and
appropriate local network restrictions.

## Endpoints

| Method / path | Result | Key |
|---|---|---|
| `POST /v1/predictions/cad-tabular` | 200 deterministic synthetic CAD/XAI envelope | `Idempotency-Key` required |
| `POST /v1/monitoring/observations` | 201 monitoring-only acceptance, no CAD output | Key optional; honored when supplied |
| `GET /openapi.json` | Shared OpenAPI with local schemas bundled for offline use | N/A |

Only the two contracted POST operations exist. CDN-backed `/docs` and `/redoc`
pages are disabled. There are no history, model-discovery, review-action,
authentication or audit-query endpoints in this milestone.

### Track A: minimal synthetic request

In another terminal (Windows: use `curl.exe` with equivalent quoting):

```bash
curl --fail-with-body http://127.0.0.1:8000/v1/predictions/cad-tabular \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: demo-cad-write-0001' \
  -d '{
    "feature_schema_id": "mock_clinical_v1",
    "features": {
      "mock_feature_demographic_age": {"value": 43, "unit": "u_years"},
      "mock_feature_demographic_sex": {"value": "synthetic_category", "unit": "u_category"}
    },
    "context": {"source": "benchmark_import", "recorded_at": "2026-10-16T10:20:00Z"}
  }'
```

Repeat exactly to see `idempotent_replay: true` and the original `audit_id`.
Changing a value while retaining the key returns 409 with
`error.code: idempotency_key_conflict`. `request_id` is optional and generated
when omitted; regenerating it does not change the canonical payload.

All units are the approved **placeholder** `u_*` tokens, not clinical units.
Unknown/excluded features, wrong units, out-of-range values, missing required
features and model/schema mismatches return the existing contract codes.
Required null/absent values produce 422; optional null/absent values are
reported missing with existing warnings. Zero/false are data, not missing.
Wearable sources/fields produce 422
`wearable_input_not_valid_for_cad_inference`; they never trigger inference.

Supported synthetic model bindings: default `mock_model_a_v0.1.0`, its
`v0.2.0` swap, `mock_model_b_v0.1.0` (requires `mock_clinical_v2` and its
required fraction slot), and `mock_model_c_v0.1.0` (mock calibration shape).
`mock_model_e_v0.1.0` simulates 503 unavailability. The LIME-only
`mock_model_d_v0.1.0` also returns 503: **LIME is future capability, no local
fidelity or computed LIME result is fabricated**.

Explanations are **synthetic SHAP-shaped offsets**, not computed SHAP. Their
base plus contributions equals the **log-odds margin**, not the mock calibrated
value. No causal, treatment or personal-probability interpretation is allowed.
Both score branches forbid `%` rendering; calibrated output carries synthetic
cohort context. `validation_status` remains `development_internal_only`, the
target remains provisional, and review state stays `pending_review`.

### Track B: simulated monitoring request

```bash
curl --fail-with-body http://127.0.0.1:8000/v1/monitoring/observations \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: demo-monitor-write-0001' \
  -d '{
    "observation": {
      "patient_ref": "pseudo_demo_001",
      "observed_at": "2026-10-16T10:25:00Z",
      "source": "simulated_wearable",
      "consent_id": "consent_mock_001",
      "metrics": [{"metric_id": "mock_metric_heart_rate", "value": 64, "unit": "u_rate"}]
    }
  }'
```

Both the first write and keyed replay return **201** (operation-specific
contract/merged tests); a replay retains the `observation_id` and creates no
second observation/audit. Without a key, every accepted call is a new append.
A consent reference is required, but **no consent record is looked up**.
Invalid metric/unit/range/structure rejects the entire write. Track-B data
never feeds CAD inference and contains no score, target or explanation.

Important unresolved contract detail: the wire schema/reference currently
accept string/boolean values and fractional counts despite the numeric metric
catalogue. This prototype preserves that behavior; it does not ratify those
as measurement semantics. Null metrics are not measured, zero is counted,
and all-null observations currently accept with count 0. See notes B-01/B-04.

## In-memory idempotency and audit

- Canonical payload: compact UTF-8 JSON, sorted keys, top-level `request_id`
  excluded. No normalization of defaults, null vs absent, or array order.
- Same key + same route/payload replays the stored response with only the
  replay flag changed. Different payload/route returns 409 **before semantic
  validation**. Rejected requests do not occupy keys.
- One in-process lock prevents concurrent duplicate mock inference,
  observation recording and success-audit publication. Retention is the
  approved **24 hours**, using monotonic time; expired reuse is logged and
  treated as a new write. Replays do not extend retention.
- Keys are globally scoped as in the merged reference. Use distinct logical
  write keys across tracks. No production identity/client scoping is claimed.
- Python tests can inspect `app.state.mock.audit_events`, `.inference_count`
  and a defensive `.observations` snapshot. No extra HTTP endpoint is added.
  Audit events contain metadata/hash/ids, not raw feature or measurement data.
- Unexpected 500s are logged with an error `audit_id`, without client stack
  traces/internal details; unsuccessful writes are not cached.

**This is not persistent, tamper-resistant, production-grade auditing.** All
state resets on restart and fixture-derived ids can repeat after restart.
Memory can grow during a run; expiry is lazy on key reuse, not a background
memory collector. No durability, multi-process, PHI protection, access-control
or production security guarantee is made.

## Tests

```bash
python -m pip install -r backend/requirements-dev.txt
python -m pip check
python -m pytest tests/contracts tests/backend -q -W error
# Entire repository's pytest suite:
python -m pytest -q -W error
# Original source integrity check (no source materials changed):
python scripts/verify_sources.py
```

The HTTP suite uses FastAPI/Starlette `TestClient` and concurrent HTTPX ASGI
requests. It has its **own** shared-schema validators and never imports the
fixture-generating oracle. All 29 supported fixture scenarios (33 steps) match
their approved bodies exactly; the 30th scenario explicitly tests the
LIME-only binding's 503 restriction instead of skipping it. Additional tests
cover validation, error schemas, missing/null/zero, deterministic XAI,
request-id generation, unconditional conflicts, 24-hour expiry, keyless append,
restart reset, failures and concurrent single-event publication.

The original `.github/workflows/contracts-ci.yml` stays untouched.
**GitHub Actions status: UNVERIFIED.** The new backend workflow is delivered
only as **`backend/ci/backend-ci.yml.example`**, a non-executing template.
Its exact intended destination is **`.github/workflows/backend-ci.yml`**.
The maintainer must install it and inspect actual CI runs before claiming a
result. See [CI handoff and exact manual instructions](ci/README.md).
The template covers Python 3.11/3.12 contract + HTTP tests, pinned actions,
dependency consistency and source integrity. No additional GitHub permissions
are requested for the agent; no paid hosting/account/service is introduced.

## M1a.3 handoff

See [docs/M1A3_INTEGRATION_HANDOFF.md](../docs/M1A3_INTEGRATION_HANDOFF.md) for
exact React + Flutter next steps, network configuration, safety/rendering
rules and acceptance tests. **No frontend implementation is part of M1a.2.**
Human review/merge and explicit next-milestone authorization come first.
