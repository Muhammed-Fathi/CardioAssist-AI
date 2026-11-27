# CardioAssist-AI Term 1 — C1 HTTP Contract Closure Evidence

**Status:** `PENDING_INDEPENDENT_REVIEW`. Bounded closure work on the owner-accepted C1
prototype baseline. Documentation plus narrowly-scoped defect fixes and one new test
module. No C2 runtime code, no migration, no model work, no AI gate change.

**Baseline this work starts from (merged, owner-accepted):** `2a8a209fba20d0c7c43c255ede4545bcaa5f34b7`
(merge of PR #144 into `delivery/term1-prototype`; parents `310534e1e334ba3be4f308f5a66d88c22b5842e0`
and accepted candidate `524d57cb17c995ea5ab299a6479f66b406751e07`; accepted candidate and merge tree
`1a117475e2d4ccb57d0902f368885065ee9e4145`).

---

## 1. The outstanding obligation this document closes

Owner acceptance (`ACCEPT-TERM1-C1-BOUNDED-PROTOTYPE-BASELINE`, PR #144 comment
[7207660039](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/144#issuecomment-7207660039))
accepted the C1 baseline for `delivery/term1-prototype` **only**, with this explicit
condition:

> Outstanding HTTP contract coverage obligations must be completed before dependent C2
> implementation.

The post-merge independent verification
([7207679643](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/144#issuecomment-7207679643))
named the residual gap precisely:

> No claim of exhaustive raw-response/replay/503 conformance matrix: targeted coverage
> improved, but explicit non-skipping coverage proof remains outstanding.

The reviewer's closing recommendation listed the four still-missing proofs:

1. an explicit twenty-operation **non-skipping** coverage proof;
2. replay variants;
3. missing-configuration (503) proof;
4. raw-response validation that does not normalise the body.

`tests/backend/c1/test_c1_http_closure.py` is that proof. It also **found three real
defects**, which are fixed here rather than papered over by weaker assertions.

---

## 2. Defects found by the closure tests

Each defect was reproduced over the real HTTP surface before it was fixed, and each new
test was re-run against the unfixed code to confirm it fails there (negative control in
§5.3). Nothing was weakened; no assertion was normalised; no operation was skipped.

### D-01 — `500` with a non-JSON body instead of the declared `503` (nine operations)

`run_idempotent()` and `_run_anonymous_idempotent()` resolved operator key material
**before** entering their guarded block:

```python
settings = handler.settings()      # raises ApiError(503) outside the try
try:
    ...
except ApiError as error:
    return error_response_json(error)     # never reached
```

With no operator key material configured, nine idempotent operations raised an unhandled
`ApiError` and FastAPI answered `500 Internal Server Error` with `text/plain`, not the
frozen `{"contract_version": "v1", "error": {...}}` envelope. Three further operations
(`V2`, `I3`, `E3`) never consulted configuration at all and answered normally on an
unconfigured deployment.

| Operation | Before | After |
|---|---|---|
| `POST /v1/admin/doctors` | `500 text/plain` | `503 identity_key_configuration_error` |
| `PATCH /v1/admin/accounts/{user_id}/status` | `500 text/plain` | `503 identity_key_configuration_error` |
| `POST /v1/doctor/verified-visits` | `500 text/plain` | `503 identity_key_configuration_error` |
| `POST /v1/doctor/verified-visits/{visit_id}/invitations` | `500 text/plain` | `503 identity_key_configuration_error` |
| `POST /v1/doctor/invitations/{invitation_id}/revoke` | `500 text/plain` | `503 identity_key_configuration_error` |
| `POST /v1/doctor/assignments/{assignment_id}/revoke` | `500 text/plain` | `503 identity_key_configuration_error` |
| `POST /v1/me/assignments/{assignment_id}/revoke` | `500 text/plain` | `503 identity_key_configuration_error` |
| `POST /v1/me/consent/synthetic-demo/revoke` | `500 text/plain` | `503 identity_key_configuration_error` |
| `POST /v1/patients/link` | `500 text/plain` | `503 identity_key_configuration_error` |
| `GET /v1/doctor/verified-visits/{visit_id}` | `401` (no configuration check) | `503 identity_key_configuration_error` |
| `GET /v1/doctor/invitations/{invitation_id}` | `401` (no configuration check) | `503 identity_key_configuration_error` |
| `GET /v1/me/assignments` | `401` (no configuration check) | `503 identity_key_configuration_error` |

Fix (`backend/app/term1/api.py`, three call sites): resolve settings **inside** the
`try`, and add the missing fail-closed `handler.settings()` to `V2`, `I3` and `E3`,
matching the twelve sibling handlers that already had it (`A2`, `A3`, `A4`, `A5`, `A6`,
`A7`, `E1`, `E2` and the idempotent runner).

### D-02 — replay bodies violated their own served response schema (five operations)

A secret-free idempotent replay returns the stored body **plus**
`idempotent_replay: true`. Five response schemas declare
`additionalProperties: false` and did not list that property, so a successful replay
failed its own contract:

```
post /v1/doctor/invitations/{invitation_id}/revoke  → 200
Additional properties are not allowed ('idempotent_replay' was unexpected)
```

Affected: `term1_admin_status_response`, `term1_invitation_revoke_response`,
`term1_assignment_doctor_revoke_response`, `term1_assignment_patient_revoke_response`,
`term1_consent_revoke_response`.

`term1_visit_create_response` and `term1_patient_link_response` already declared
`"idempotent_replay": {"const": true}`; the five above now match that convention exactly
(`const: true`, not `type: boolean`), so a replay is provably a replay and an initial
response provably is not. The replay field remains absent from the initial response —
that asymmetry is asserted. No property was made optional and no schema was loosened:
`additionalProperties` stays `false` everywhere.

### D-03 — the served document under-declared the real status catalogue

`POST /v1/patients/link` answers `409 idempotency_key_conflict` and
`POST /v1/me/assignments/{assignment_id}/revoke` answers `409 assignment_already_revoked`,
but neither operation declared any `409`, and no C1 operation declared `422` from the
runtime request-schema gate (C1-R01) or `500`/`503` from the transport layer. The
served contract therefore could not have been used to validate the real surface.

Fix: each operation's `responses:` block in the modular YAML source now lists the exact
closed-catalogue codes it can emit at each status, and
`backend/app/term1/openapi.py` carries them into the served document as the
`x-error-codes` vendor extension on each error response. This is derived from the raise
sites in `backend/app/term1/` and cross-checked against `errors.py::ERROR_CATALOGUE`;
three contract tests enforce that every listed code exists in the catalogue at that exact
status. Successful statuses, response schemas and header requirements are unchanged.

No application behaviour was relaxed to satisfy a test. D-01 makes fail-closed behaviour
stricter; D-02 makes the schema match the behaviour the accepted C1 baseline already had;
D-03 makes the served contract state the behaviour the accepted baseline already had.

---

## 3. What the closure module proves

`tests/backend/c1/test_c1_http_closure.py` — 30 tests, no conditional skipping.

| # | Proof | Mechanism |
|---|---|---|
| 1 | Exact executed-operation inventory | One end-to-end chain records every `(method, path)` it issues and asserts **equality** with `openapi.C1_OPERATIONS` (20). Equality, not containment: a skipped operation and an undeclared extra operation both fail. |
| 2 | Raw success responses validate | Every recorded 2xx body is validated **unmodified** against the JSON Schema the served document binds to that operation's actual status. `null`s are kept, `idempotent_replay` is kept, extra properties are not stripped. An undeclared status is a failure, not a skip. |
| 3 | Replay variants | Seven secret-free idempotent operations are replayed; each replay body must carry `idempotent_replay: true`, return the same resource identifier, keep the initial status, and validate against the same served schema. |
| 4 | Secret non-redisclosure | Three secret-bearing idempotent operations (`AD1`, `I1`, `E1`) must answer the replay with `409 secret_not_redisclosable`, must not reproduce the one-time secret, and the 409 body must still validate against the served error schema and its declared code list. |
| 5 | Error catalogue closure | Every failure probe's status must be declared by the served document for that operation, and its `error.code` must appear in that status's declared closed list. Every one of the twenty operations receives at least one failure probe. |
| 6 | Missing-configuration 503 | With all four operator secrets absent, each of the twenty operations answers `503 identity_key_configuration_error`, JSON, `Cache-Control: no-store`, validating against the served 503 schema, with no secret-shaped field. |
| 7 | Authentication, authorization, isolation | Anonymous probes on all eighteen authenticated operations; wrong-role probes; cross-doctor visit read is `404 visit_not_found` (not `403`, not the resource); doctor listing patient assignments is `403 forbidden`; read-back of an invitation never discloses its access code or subject identifier. |
| 8 | Structural guarantee | Every C1 operation declares a 2xx, declares `500` and `503`, and every non-2xx entry carries a non-empty closed code list and a local component reference. |

Coverage arithmetic forced by the tests themselves: 20 operations × 1 success = 20
validated success bodies; 10 idempotent operations split exhaustively into 7 replayable +
3 secret-bearing (`test_idempotent_operation_partition_is_exhaustive`); 20 × 1
missing-configuration response; and a failure-probe set whose covered path set must equal
the full twenty-operation path set.

---

## 4. Repository reconciliation

Appended, not rewritten. Historical failures stay visible:

| Ledger | What was appended |
|---|---|
| `TERM1_STAGE_PROGRESS.md` §6 | C1 acceptance, merged SHA, branch/PR evidence, D-01…D-03, closure status |
| `TERM1_TEST_EVIDENCE.md` §7 | Post-merge hosted CI, this branch's exact commands/counts/exit codes, Windows evidence received, unresolved RH-04 findings |
| `TERM1_DECISION_REGISTER.md` §6/§7 | AC-C1 acceptance recorded; rollback decision recorded; unresolved C2 gates unchanged |
| `TERM1_BLOCKER_REGISTER.md` §2 | B-02/03/04/05 re-stated at their true state; B-14 (closure) closed; B-15…B-18 added |
| `TERM1_C1_ROLLBACK_POLICY_PROPOSAL.md` §Addendum | Owner decision recorded; proposal text preserved verbatim above it |
| `TERM1_API_INTEGRATION_MATRIX.md` §7 | Closure operation/status/code inventory and the defect corrections |

The separate Windows RH-04 portability findings are **recorded, not touched**: no file
under `research/`, no test under `tests/experiments/`, `tests/audit/` or `tests/uci412/`,
no `.github/workflows/**` and no research requirement pin is modified by this branch
(verified mechanically in §5.5).

---

## 5. Verification actually executed

Environment: Linux sandbox, Python 3.11.2, `backend/requirements-dev.txt` pinned set plus
`research/audit/requirements.txt`. Commands are verbatim; counts and exit codes are as
observed.

### 5.1 Focused closure and C1 suites

| Command | Result | Exit |
|---|---|---|
| `python -m pytest tests/backend/c1/test_c1_http_closure.py -q -W error` | **30 passed** | 0 |
| `python -m pytest tests/backend/c1 -q -W error` | **291 passed** (213 at the accepted baseline + 30 closure + 48 previously relocated) | 0 |

### 5.2 Combined regression, warnings as errors

| Command | Result | Exit |
|---|---|---|
| `python -m pytest tests/contracts tests/backend -q -W error` | **1189 passed**, 0 failed | 0 |
| `python -m pytest tests/audit -q -W error` | **711 passed**, 0 failed | 0 |

`1189` is the same combined backend+contracts count recorded by hosted CI and by the
owner's native Windows run at the accepted baseline (`1159` before this branch's 30 new
closure tests; `1159 + 30 = 1189`). The existing CI command
`.github/workflows/backend-ci.yml` already passes `-q -W error`; this branch runs the
same command and does not suppress warnings to obtain the count.

### 5.3 Negative controls (the tests are load-bearing)

| Temporarily reverted | Focused test | Observed |
|---|---|---|
| `backend/app/term1/api.py` (D-01 fix) | `-k missing_configuration` | **11 failed**, 9 passed |
| `term1_consent_revoke_response` + `term1_assignment_patient_revoke_response` (D-02 fix) | `-k secret_free_replays` | **1 failed** — `Additional properties are not allowed ('idempotent_replay' was unexpected)` |

Both reverts were restored immediately; the working tree was re-verified afterwards.

### 5.4 Static and environment checks

| Command | Result | Exit |
|---|---|---|
| `python -m pip check` | `No broken requirements found.` | 0 |
| `python scripts/verify_sources.py` | all four source hashes `OK`; supervisor audit 25 papers `{APPROVED_GREEN: 9, MAYBE_PINK: 1, MAYBE_ORANGE: 6, REJECTED_RED: 9}` | 0 |
| `python -m alembic upgrade head` (fresh disposable DB) | head `20261126_06` | 0 |
| `python -m alembic current` | `20261126_06 (head)` | 0 |
| `python -m alembic check` | `No new upgrade operations detected.` | 0 |
| `git diff --check` | no whitespace errors | 0 |

No migration is added, altered or downgraded by this branch; the migration chain is
untouched at `20261126_06`.

### 5.5 Scope containment checks

* `git diff --stat` touches **no** path under `research/`, `tests/experiments/`,
  `tests/audit/`, `tests/uci412/`, `tests/manuscript_audit/`, `ai/`, `.github/`,
  `frontend/`, `infra/`, `prompts/` or `shared/contracts/openapi.yaml`.
* No new migration file, no `backend/app/term1/models.py` change, no settings/env var
  added, no provider or registry selector added.
* No file with a prohibited extension (`.pkl`, `.joblib`, `.onnx`, `.csv`, `.sqlite`,
  `.db`, `.env`, keys) is added; the existing backend CI guard covers `backend/` and
  `tests/backend/`.

### 5.6 Post-merge hosted CI at the exact merged baseline

Verified from the GitHub API against `head_sha = 2a8a209fba20d0c7c43c255ede4545bcaa5f34b7`
(`total_count = 4`), all `status: completed`, all `conclusion: success`, and **all eight
jobs** confirmed individually at the same SHA:

| Workflow run | Workflow | Jobs at `2a8a209…` | Conclusion |
|---|---|---|---|
| [45925221406](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/45925221406) | mock-backend-validation | Mock backend (3.12), Mock backend (3.11) | SUCCESS (both) |
| [45925221497](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/45925221497) | contract-validation | Contract and fixture validation | SUCCESS |
| [45925221365](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/45925221365) | audit-toolchain-validation | Dataset audit toolchain (3.11), (3.12) | SUCCESS (both) |
| [45925221446](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/45925221446) | synthetic-experiment-runner-validation | Synthetic experiment runner (3.11), (3.12), RH-04 structural drift diagnostic (3.12) | SUCCESS (all three) |

These are the **post-merge** runs on the merged tree. They do not cover this branch; see
§6.

### 5.7 Native Windows evidence received (not produced by this branch)

Owner-supplied, from `E:\CardioAssist-C1-Retest-f35326a6fd`, recorded as received and
**not** re-derived here:

* migration + reviewer regressions: **27 passed** in `71.86s`;
* combined backend/contracts: **1159 passed** in `893.97s`;
* identity, dependency-freeze match, legacy HTTP seed, upgrade/check, legacy
  preservation, empty-C1 downgrade/re-upgrade, enrollment/restart, source verification
  and final identity checks: all exit `0`;
* populated-database downgrade: exit `1` and **expected** under the accepted invariant,
  with the preservation check exit `0` and schema, rows, revision, FKs and integrity
  unchanged;
* isolated legacy backup restore: exit `0`.

Full Windows log files and per-suite exact counts beyond the two supplied tails were not
provided, so this branch asserts only the two headline counts and does not claim a
complete Windows count.

---

## 6. What is still NOT claimed

* **No hosted CI run exists for this branch's exact HEAD.** The 403 dispatch limitation
  recorded as B-16 is unchanged; the owner must dispatch the four existing workflows on
  the final SHA and the reviewer must verify the run head SHA, conclusions and counts.
  Zero checks is not success.
* **No native Windows execution of this branch.** The 503 matrix, the replay matrix and
  the new `x-error-codes` closure have not been run on Windows. Linux-only evidence.
* **Not an exhaustive conformance claim for the whole C1 surface.** What is now proven is
  the specific matrix in §3: twenty non-skipping successes, ten replay variants with the
  secret/no-secret split, a declared-status/code closure over failure probes, and a
  twenty-operation 503 matrix. Deep negative semantics (enumeration timing, lockout
  boundary arithmetic, two-connection races, byte-level KDF behaviour) remain covered by
  the existing C1 modules listed in `TERM1_TEST_EVIDENCE.md`, not re-proven here.
* **`tests/experiments` and `tests/uci412` were not executed.** The research dependency
  set (`numpy`, `scikit-learn`, …) is not installed in this environment and this branch
  must not change research requirements, tolerances, fixtures or workflows. `NOT_RUN` is
  the correct label, not a pass. Combined with B-01/B-17, no `ALL_GREEN` claim is made.
* **No owner decision is inferred.** C1 closure acceptance, rollback ratification and the
  C2 authorization gates are the owner's alone.
* **No C2 work.** `TERM1_C2_IMPLEMENTATION_DEPENDENCY_MAP.md` is documentation only: no
  runtime module, endpoint, model, artifact, registry entry or migration is created, and
  A1/A2/A3/B remain `PENDING`.
* **PR #142 remains OPEN/DRAFT**; PR #141 and Issue #132 are the separate research track
  and are untouched.

---

# Appendix A — Independent-review corrections at `b860efc` (2026-11-27)

Append-only. §1–§6 above describe the first candidate (`b860efc`). This appendix records
the residual corrections the reviewer required and what was found when they were executed.

## A.1 Reviewer residuals, and their disposition

Reviewer branch `review/term1-closure-residuals-b860efc`, head
`f81c37b9ff0ba8d4d498fc6a5ffce1171b801e01`, four commits cherry-picked onto this branch
(`c0ea509`, `4840eac`, `8a22d9e`, then the map correction). The reviewer stated the patch
was *proposed and not runtime-executed*; the tests were therefore executed here.

| # | Residual | Finding | Disposition |
|---|---|---|---|
| R-1 | A4 temporary-password refresh refusal undeclared | Confirmed: `403 password_change_required` was reachable and undeclared | **FIXED** in the YAML; regression test passes |
| R-2 | E1 duplicate-email 409 and unusable-doctor 403 undeclared | Confirmed | **FIXED** in the YAML |
| R-3 | E2 invalid identifier 422 / role-profile 409 undeclared | Confirmed | **FIXED** in the YAML |
| R-4 | Shared `verify_or_activate` can emit 409 identity errors on routes that never declared them | **Confirmed and larger than reported**: 11 of 20 routes reached the binding; only some declared it; `POST /v1/auth/login` declared **no 409 at all** | **FIXED** — `identity_key_material_mismatch` and `identity_key_replacement_unsupported` declared on all 10 idempotent operations **and** on login |
| R-5 | `role_profile_mismatch` reachable but undeclared | **Confirmed**: `require_doctor` and the patient-profile lookups raise it fail-closed | **FIXED** on V1/V2/I1/I2/I3/E3/E4/E5/E6 |
| R-6 | Failure coverage compared paths without method; wrong-role probes accepted any `>= 400` | Confirmed as a genuine weak spot in the first candidate | **FIXED** — `(METHOD, template)` pair equality, and 12 role-guarded operations pinned to exact `403 forbidden` |
| R-7 | 500 declared JSON but generic C1 faults escape as bare ASGI errors | **Confirmed as a runtime defect** (§A.2) | **FIXED** — uniform unexpected-failure boundary on all 20 routes |

## A.2 D-04 — unexpected exceptions escaped as `500 text/plain` (runtime defect)

The reviewer predicted this and it reproduced exactly. With a fault injected into
`create_doctor` before business completion:

```
Recorded(method='post', path='/v1/admin/doctors', status=500, body=None,
         text='Internal Server Error',
         headers={'content-length': '21',
                  'content-type': 'text/plain; charset=utf-8'})
```

Three contract violations in one response: the body is **not JSON** (the served 500 is
declared `application/json`), the body is **not the frozen error envelope**, and there is
**no `Cache-Control: no-store`** — on the one status where a cacheable error is most
harmful. `main.py`'s generic handler is scoped to the **legacy** routes only, and every C1
handler caught `ApiError` alone, so any other exception reached Starlette.

**Fix:** a uniform response boundary. Each of the twenty route registrations is now a thin
wrapper around a renamed `_impl_*` function:

```python
try:
    return await _impl_<op>(...)
except ApiError as error:
    return error_response_json(error)
except Exception as error:  # noqa: BLE001 - mapped to the declared 500
    return unexpected_failure_json(error)
```

The decorator sits on the **wrapper**, so no path can bypass it — an earlier attempt left
the decorator on the implementation and silently deregistered the route; that was caught
by asserting the registered route count, not by inspection.

`unexpected_failure_json` returns the static catalogue body
(`{"contract_version":"v1","error":{"code":"internal_error","message":"The service could
not complete the request."}}`) with `Cache-Control: no-store`, and logs the real exception
server-side at ERROR. The message never embeds the exception type, text, traceback,
submitted value or resource identifier.

**What is deliberately *not* changed:** the boundary opens no transaction and performs no
database work. An unexpected fault has already left the operation's own
`write_transaction` block, so that block rolls back exactly as before; mandatory audit
obligations inside the transaction are unaffected; legacy behaviour is untouched because
legacy routes have their own handler. Returning success is structurally impossible — the
status is fixed at 500.

## A.3 Reachability audit — method, and honest limits

Codes were audited from the **actual call graph**, not from a sampled probe set: an AST
walk over `backend/app/term1/*.py` builds the call edges, marks a code as *raised* only at
an `api_error("<code>")` / `ApiError(_, "<code>")` call site, and propagates through the
transitive closure from each `_impl_*` entry point.

Result: **20 routes, 20 implementations, 0 reachable-but-undeclared codes.**

Two false-positive classes were found and eliminated while building the audit, and are
recorded because they are the reason a naive grep is not evidence:

* `invalid_invitation` appeared to be reachable from `admin/doctors` etc. It was only
  **compared** (`error.code == "invalid_invitation"`) inside a `failure_hook`, never
  raised. Counting call-site arguments instead of raised codes produced the artifact.
* `password_change_required` on `GET /v1/auth/me` arrives through
  `sessions.current_account`, so it is genuinely reachable and *was* already declared.

**Limit, stated plainly:** this is a static over-approximation of reachability, not a proof
of empirical reachability, and not a claim that every reachable code has been *observed*.
It answers "is any code that the code can raise missing from the contract?" — the direction
the reviewer asked for. It does not establish that each code has been triggered at runtime.

## A.4 Verification of the corrected candidate

| Command | Result | Exit |
|---|---|---|
| `pytest tests/backend/c1/test_c1_http_closure.py -q -W error` | **39 passed** (30 + 9 reviewer) | 0 |
| `pytest tests/backend/c1 -q -W error` | see `TERM1_TEST_EVIDENCE.md` Appendix B | 0 |
| `pytest tests/contracts tests/backend -q -W error` | see `TERM1_TEST_EVIDENCE.md` Appendix B | 0 |
| `pytest tests/audit -q -W error` | see `TERM1_TEST_EVIDENCE.md` Appendix B | 0 |
| `pip check`, `verify_sources.py`, `git diff --check` | clean | 0 |

**Negative control (R-7):** reverting only `backend/app/term1/api.py` leaves
`test_reviewer_unexpected_c1_failure_matches_declared_500` failing (`1 failed, 8 passed`);
restoring it gives `9 passed`. The boundary is load-bearing, not cosmetic.

## A.5 Still not claimed

No hosted CI exists at this HEAD (B-15), no native Windows run of this branch (B-16), and
`tests/experiments` / `tests/uci412` remain `NOT_RUN` (B-17). No `ALL_GREEN` claim. The
reachability audit is static (§A.3). C1 closure acceptance remains PENDING independent
review.


## Independent reviewer follow-up — exception-log redaction (proposed)

The corrected HTTP 500 envelope is static and no-store. However, the c9026a1 implementation logs the full exception with `logger.exception(..., exc_info=error)`. Exception messages and SQLAlchemy tracebacks can contain submitted values, SQL parameters or security material. The proposed follow-up replaces that call with a fixed metadata-only ERROR event, and strengthens the existing fault-injection regression to require an error log without exception/stack payload or the synthetic sentinel. It does not change transaction boundaries, status or error catalogue. The earlier description of full exception logging is superseded by this proposal; runtime verification and owner acceptance remain pending. No claim that every logging channel has been exhaustively audited.
