# 06 — Local Testing and Milestone Acceptance Matrix

**Status:** PROPOSED planning baseline (documentation only), 2026-10-17.
Current counts verified on branch `arena/ebc5fdbb-cardioassist-ai` at merge
baseline `6c2572c`, Linux, Python 3.11.2.

---

## 1. Current test inventory (all green, `-W error`)

| Suite | Location | Count | What it proves |
|---|---|---|---|
| Contract/fixture/oracle tests | `tests/contracts/` (M1a.1, PR #3) | **249** | Schemas, OpenAPI document, fixture pack (31 scenarios / 38 steps), deterministic reference oracle, error catalogue, explanation additivity (F-08), rendering labels, ADR-001 optional-null semantics (D-044) |
| Backend HTTP tests | `tests/backend/` (M1a.2) | **347** | Live FastAPI behavior independent of the oracle: golden bodies, validation, missing/null/zero, Track separation, wearable rejection (F-09), replay/conflict, 24 h expiry, restart reset, concurrency (one result/one audit event), failure paths, Host-header regression (PR #5), ADR-001 schema reader + optional-null semantics |
| **Total pytest** | repo root | **596** | `python -m pytest -q -W error` → `596 passed` |
| Source integrity | `scripts/verify_sources.py` | 4/4 hashes + supervisor audit | Research sources unchanged; 25 papers (9 GREEN / 1 PINK / 6 ORANGE / 9 RED) |

Reproduce locally ($0, no Docker/accounts):

```bash
python -m venv .venv
. .venv/bin/activate            # Windows: .venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements-dev.txt
python -m pip check
python -m pytest tests/contracts tests/backend -q -W error
python -m pytest -q -W error
python scripts/verify_sources.py
```

Run the mock backend (one worker only — in-memory state):

```bash
python -m pip install -r backend/requirements.txt
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

**Local security default:** the server is unauthenticated — bind
`127.0.0.1` for ordinary local development. Bind `0.0.0.0` only for a
controlled LAN/preview demo, with synthetic inputs and appropriate network
restrictions (`backend/README.md`). A phone's `localhost` is the phone
itself (M1a.3 handoff §3.2).

CI (installed workflows, `backend/ci/README.md`): `contracts-ci.yml`
(contracts + prohibited-file check) and `backend-ci.yml` (contracts + HTTP
tests on Python 3.11/3.12, dependency consistency, source integrity,
prohibited-artifact check). **Workflow presence is not proof of a green
run** — inspect the PR Checks tab for runs tied to the latest commit.
Python 3.12 results exist only via CI; local 3.12 is UNVERIFIED in this
sandbox.

## 2. Regression suites that must stay green in every milestone

| Guard | Command / mechanism | Protects |
|---|---|---|
| Full pytest (596+) | `python -m pytest -q -W error` | Wire behavior, idempotency, audit, Track separation |
| Fixture oracle | `tests/contracts/` (incl. `reference_contract.py`) | Approved mock contract semantics |
| Source integrity | `python scripts/verify_sources.py` | Research-source files + SHA256 manifest |
| Prohibited-artifact checks | both CI workflows | No datasets/weights/credentials/PHI sneaking in |
| Dependency pins + `pip check` | `backend/requirements*.txt`, `tests/contracts/requirements.txt` | Reproducible installs at $0 |

## 3. Milestone acceptance matrix

Legend: **L** = local tests green (commands recorded in PR) · **H** = human
review recorded · **S** = safety-labelling evidence (MOCK disclaimers,
prohibited-copy absence) · **D** = demonstration/recorded walkthrough.

| Milestone | Local tests (in addition to §2 guards) | L | S | D | H (reviewer focus) |
|---|---|---|---|---|---|
| **M1a.3** thin React+Flutter (next planned; **implementation authorization pending**) | React client/component/snapshot tests (mandatory target/disclaimer/status copy; uncalibrated vs mock-calibrated labels; optional missing values; replay keeps original audit id; 409 conflict; 422 wearable rejection; 503 unavailable/LIME-only). Flutter client/widget tests (JSON fields; 201 first/replay; preserved observation id; consent-required/unknown-metric/unit/range errors; source/disclaimer labels; **absence of CAD output/actions**). Prove: monitoring does not increase inference counter | ✔ | ✔ rendered mandatory wording + absence of %/LIME/advice | ✔ 4 integration demos (retry same audit id / same observation id / 409 / 422+no score); emulator/physical-device evidence or UNVERIFIED note | Engineering: toolchain pins, network config (relative `/v1`, `--dart-define`, `127.0.0.1` local default), no client-side contract tightening (B-01), no fabricated LIME (X-01); carry B-02–B-04, A-01, G-02 forward |
| **M1b** platform completion | Full suite green **with persistence** (behavior unchanged); migration up/down tests; RBAC role-matrix tests; consent grant/revoke audit tests; one-audit-event-per-write on all new write APIs; reassessment-validity matrix (invalid triggers produce no score); offline→sync test (emulator + 1 physical device or recorded UNVERIFIED); batch-ingestion per-item results; admin-only route tests | ✔ | ✔ all user-facing text snapshot-tested or conservative fallback recorded | ✔ IC-2 demo (consent, RBAC, reassessment-validity on mocks) | Engineering + (P-4/D-016 outcome): copy review; SQLite-only-SQL checklist; wire-behavior diff empty |
| **M2** Gate DA audit | Audit scripts runnable; hash/licence verification; `verify_sources.py` untouched; duplicate/overlap audit tooling tests | ✔ | n/a (no UI) | ✔ audit report + **"no fitting occurred" certification** | Research lead + supervisor: dataset authorization match, §R2-4.4 checklist completeness, §F-1 coding rulings (`thal`/`oldpeak`/`ca`) |
| **M3** protocol + real models | Full suite re-green with real model backend (IC-3); SHAP log-odds sum-check **for real**; determinism tests; calibration evaluation scripts; label-shuffle negative control at chance; stability computation | ✔ | ✔ UI wording re-snapshot; `validation_status` rendering | ✔ IC-3: fixture suite green against real model; benchmark results incl. negatives | Supervisor: Gate PT signed **before** any fitting; leakage checklist; metrics/CI honesty; LIME fidelity real (X-01 closed) |
| **M4** prototype + write-up | Replication package re-runs key results from clean checkout (documented commands); export snapshot tests (if F08 approved) | ✔ | ✔ claims-discipline check (no invented numbers; TRIPOD+AI checklist) | ✔ IC-4 walkthrough | Supervisor + research lead: manuscript, D-025 verification before novelty claims |
| **M5** product track (scheduling authorization pending; deliverables required) | Upload validation tests; OCR pipeline tests on **synthetic sample documents**; extraction state-machine tests; "unverified fields cannot enter feature sets"; **"verified-but-ineligible fields cannot enter Track-A feature sets"** (05 §2.1); copy guardrails (prohibited-phrase tests); assistant refusal/citation tests | ✔ | ✔ PHI rules (synthetic docs only), assistant labelling | ✔ F14–F17 walkthrough per EXT mockups | Clinician (P-4/D-016/D-026) for F15 copy + F16 content; privacy review for uploads |
| Health Connect spike (M4 product item) | Capability/device check recorded; adapter tests on a qualifying device **or** recorded unsupported-device outcome with the simulator fallback exercised end-to-end | ✔ | ✔ simulated-source labelling everywhere | ✔ fallback demo is a deliverable, not a skip | Engineering: capability/device record; P-6 remains closed for vendor/real-device claims |

**Universal rule: a milestone PR is not complete until L + H are both
satisfied** (and S/D where marked). The agent never merges (AGENTS.md).

## 4. Client-side test obligations (M1a.3 detail, from the handoff doc)

Negative assertions that must exist in client tests (they are the guards
against the called-out failure modes):

1. Track-B scalar types are **not** silently tightened by the TypeScript/Dart
   client (wire schema is the authority; B-01 stays open).
2. No computed LIME/fidelity value is rendered anywhere (X-01).
3. Uncalibrated scores never render `%`; calibrated mock output always
   carries synthetic cohort context (§F-6).
4. SHAP contributions render on the log-odds scale, separate from the score;
   never summed into it.
5. Monitoring screens never call CAD inference and never display a Track-A
   score.
6. Idempotency keys survive retries of the same logical write; a changed
   payload uses a new key.

## 5. Contract-change acceptance (template: ADR-001)

Any change to approved artifacts (`shared/contracts/**`, fixtures, oracle,
contract tests) requires: ADR + maintainer decision in `docs/DECISIONS.md`,
schema+fixture+tests in one change-set, unchanged behaviors pinned by
existing tests, `verify_sources.py` green, and a stated compatibility
assessment (client/codegen impact). Backbreaking wire changes → `/v2`.

## 6. Evidence to attach to every milestone PR

1. Exact commands + full output of the local test runs (like
   `backend/VERIFICATION.md`).
2. `git diff --stat` for changed paths; explicit statement that research
   sources + manifest are untouched.
3. Feature IDs covered (from
   [02_FEATURE_TRACEABILITY_MATRIX.md](02_FEATURE_TRACEABILITY_MATRIX.md)).
4. MOCK-vs-real labelling statement.
5. Emulator/device notes where applicable (or UNVERIFIED limits).
6. Open questions carried forward (from
   [07](07_OPEN_DECISIONS_RISKS_ASSUMPTIONS.md)) — never silently resolved.
