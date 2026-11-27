# CardioAssist-AI Term 1 — Test Evidence and CI Baseline

**Status:** evidence register; C0 executed no tests. `NOT_RUN` is the correct label for all local/Windows commands in this document.

## 1. Live GitHub Actions baseline (`HOSTED_CI_VERIFIED`)

Refreshed at C0 start from the exact prototype HEAD `bca75b4646dbde26e495201938b7ae01ea7e0d21`; no newer run for that SHA.

| Workflow | Run | Conclusion | Notes |
|---|---|---|---|
| mock-backend-validation | [45650285373](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/45650285373) | SUCCESS | Python 3.11/3.12 contract+backend tests, source verify, prohibited-artifact guard |
| contract-validation | [45650285403](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/45650285403) | SUCCESS | Contract and fixture validation |
| audit-toolchain-validation | [45650285433](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/45650285433) | SUCCESS | Python 3.11/3.12 audit tests |
| synthetic-experiment-runner-validation | [45650285465](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/45650285465) | FAILURE | Python 3.11 failure; Python 3.12 success; structural diagnostic success |

Recorded counts from prior independent reviewer log access (`AGENT_REPORTED` for Arena, `HOSTED_CI_VERIFIED` for conclusions):

- [Python 3.11 job](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/45650285465/job/139332628376): 1808 passed, 2 failed, 10 errors, 2 skipped; UCI-412 calibrated-log-odds delta `4.441e-16`; forced-dispatch JSONDecodeError; cause not proven.
- [Python 3.12 job](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/45650285465/job/139332628534): 1820 passed, 2 skipped, then 396 passed benchmark step.
- Structural diagnostic [job](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/45650285465/job/139332628013): SUCCESS.

Issue #132 remains OPEN. No Golden fixture, tolerance, research test, workflow, PR #141 or Issue #132 change is authorized. No `ALL_GREEN` claim.

### Post-merge re-verification at accepted baseline SHA `310534e1e334ba3be4f308f5a66d88c22b5842e0`

The independent reviewer verified that all four post-merge C0 workflow runs completed successfully at the accepted prototype baseline:

| Workflow | Run | Conclusion | Notes |
|---|---|---|---|
| backend-ci | [45701993590](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/45701993590) | SUCCESS | Backend tests at baseline SHA |
| contracts-ci | [45701995312](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/45701995312) | SUCCESS | Contract validation at baseline SHA |
| audit-ci | [45701993465](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/45701993465) | SUCCESS | Audit tests at baseline SHA |
| experiment-runner-ci | [45701993785](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/45701993785) | SUCCESS | Synthetic experiments at baseline SHA |

These runs are appended to the ledger without erasing the earlier C0 baseline runs in §1. This successful re-verification does not establish that the intermittent Python 3.11 research issue (§1, blocker B-01) has been resolved.

## 2. Test strategy by stage

| Stage | Positive tests | Negative tests | Evidence required |
|---|---|---|---|
| C0 | Documentation consistency, exact SHA/PR checks, C0-F01…F10 cross-references | No source/migration/contract/workflow change; no PHI/model artifacts; reconstructed SHAs not presented as originals | Exact PR #143 head, diff/stat, exact-head dispatch links, reviewer verdict, owner Windows candidate transcript |
| C1 | Admin/doctor provision; email normalization/duplicate; login/logout; temp-password change; visit attestation; invitation issue/revoke; register; link; assignment list/revoke; restart persistence; Alembic upgrade/current/check | wrong/expired/revoked/consumed code; wrong identifier; subject mismatch visit A→patient B; duplicate identifier across key versions; populated-DB key replacement refusal; two-connection concurrent redemption; cross-doctor/patient IDOR; suspended/disabled user; per-account/per-source/per-invitation lockout; no raw ID/email/token/code in logs/API/DB; rollback orphan; keyed fingerprint replay conflict; secret_not_redisclosable; unknown-invitation audit; legacy route regressions | Backend+contract CI at exact head; migration evidence; Windows output |
| C2 | Profile versioning; snapshot digest; idempotent assessment; authorized inference with model identity/digest and same-model explanation; role projection; restart | invalid source/units/ranges; optional absence abstention; wearable/OCR/Track-B leakage; client provenance override; tampered artifact/wrong digest; unauthorized flag/header/env; no mock fallback; abstain/unavailable/error carry no score; lease recovery/fencing; patient projection redaction | Adapter-specific CI; oracle/tamper evidence; Windows output; Decisions A/B status |
| C3 | Review decisions; append-only history; clinician-authored note/prescription; message+notification atomicity; read status; authorized history; restart | unassigned doctor; patient attempting review; duplicate review/follow-up; illegal transition; cross-assignment history; notification of wrong user; AI author; partial write rollback | Cross-role CI; Windows output |
| C4 | Full synthetic E2E; migration upgrade/downgrade-on-disposable/reupgrade; restart; full pytest with correct deps; source verification | all stage negatives re-run; secret/PHI/artifact scan; exact operation allowlist; no shadow prediction route | Exact-head hosted CI; Windows output; handoff ledger |

## 3. Exact commands (to be executed in later stages; all NOT_RUN here)

```bash
python -m pip install -r backend/requirements-dev.txt
python -m pip check
python -m alembic upgrade head
python -m alembic current
python -m alembic check
python -m pytest tests/contracts tests/backend -q -W error
python -m pytest tests/audit -q -W error
python -m pytest tests/experiments -q -W error
python -m pytest tests/uci412 -q -W error
python scripts/verify_sources.py
git diff --check
```

For the full suite, research dependencies must also be installed: `research/experiments/requirements.txt`, `research/audit/requirements.txt`, `research/uci412/requirements.txt`. Do not claim full-suite success without them. During C0 only the existing baseline commands apply; no new API smoke command exists yet.

## 4. Native Windows evidence

`NOT_RUN`. The owner must execute the complete PR-candidate block in `TERM1_WINDOWS_VERIFICATION_RUNBOOK.md` and supply exact PowerShell version, OS build, host and virtualenv Python versions, exit codes for every Git verification query, test counts per suite, migration outputs, source verification output, git diff result, legacy preservation row counts, exact served paths and service transcripts. Hosted Linux CI does not substitute.

## 5. Exact-head hosted CI (C0-F10)

The four existing validation workflows with `workflow_dispatch` (`mock-backend-validation`, `contract-validation`, `audit-toolchain-validation`, `synthetic-experiment-runner-validation`) could not be dispatched by Arena: each attempt returned `HTTP 403: Resource not accessible by integration` from the restricted integration token, and `actions/runs?head_sha=c68af475...` returned `total_count=0`. No workflow, research test, Golden fixture, tolerance or research gate is edited. No unrelated research-evidence workflow is dispatched and no further attempts are made with the same token.

`HOSTED_CI=OWNER_DISPATCH_REQUIRED`. The owner will dispatch these four workflows on the final reviewed published SHA using their own authorized GitHub account: `backend-ci.yml`, `contracts-ci.yml`, `audit-ci.yml`, `experiment-runner-ci.yml`.

Evidence fields the owner/reviewer must report: run URL, workflow file, requested ref, exact run head SHA, checkout revision shown in the job, job conclusion, available log excerpts/counts, and reviewer classification of any failure against the known baseline. Zero checks is not success; no result is claimed here. The inherited Python 3.11 research failure remains in §1 and blocker B-01.

## 6. Local execution evidence (arena branch `arena/2b22dd7d-cardioassist-ai`)

Counts below are from local execution on this branch only. They do not alter the hosted-CI baseline in §1, the NOT_RUN labels in §3–§5, or the Windows 3.12 NOT_RUN status (owner-dispatched; dispatch attempts returned 403 and are not retried).

| Suite | Command | Result |
|---|---|---|
| C1 behavioral + contracts (relocated to `tests/backend/c1/` per C1-R08; collected exactly once by the existing backend command) | `python -m pytest tests/backend/c1 -q -W error` | 213 passed, 0 failed, 0 skipped — C1 revision complete: C1-R01 canonical contract composition from modular YAML source with operation-specific schemas + runtime enforcement; C1-R02 temporary-password enforcement on all authenticated C1 operations (incl. session listing/revocation); refresh preserves absolute lifetime; duplicate Authorization rejected; non-ASCII bearer safe; C1-R03 durable idempotency expiration lifecycle (flush expired row before replacement insert); C1-R04 independent source-based enrollment rate limiting; Non-ASCII access codes safe at `invitation_verifier()`; C1-R05 single authoritative login transaction with constant-time password-verification work; C1-R06 read-only fail-closed startup key verification (`invitation_attempt` probe; exactly-one active key-check row per purpose); C1-R07 invitation expiry at the consumption boundary and doctor suspension/disabling effect |
| Legacy backend + contracts | `python -m pytest tests/contracts tests/backend -q -W error` | 898 passed, 0 failed (unchanged from baseline; warnings-as-errors clean) |
| Audit | `python -m pytest tests/audit -q -W error` | 711 passed, 0 failed |
| Experiments | `python -m pytest tests/experiments -q -W error` | NOT_RUN — 30 collection errors; `ModuleNotFoundError: No module named 'numpy'`; research dependencies (`research/experiments/requirements.txt`) not installed |
| UCI-412 | `python -m pytest tests/uci412 -q -W error` | NOT_RUN — `ImportError` in conftest; `No module named 'numpy'`; research dependencies (`research/uci412/requirements.txt`) not installed |
| pip check | `python -m pip check` | Pass — no broken requirements |
| verify_sources | `python scripts/verify_sources.py` | Pass — exit 0 |
| Alembic | `alembic upgrade head / current / check` | Pass — head `20261126_05`; "No new upgrade operations detected" |
| Migration preservation | Disposable DB: downgrade to base, re-upgrade to head | Pass — current == head == `20261126_05` |
| git diff --check | `git diff --check` | Pass — exit 0 (no whitespace errors) |

Combined local total for runnable suites: C1 213 + legacy 898 + audit 711 = 1,822 passed, 0 failed.

Research suites (experiments, uci412) are NOT_RUN pending research dependency installation; no research code, test, Golden fixture, tolerance or CI was changed to obtain a result.

Counts below are from local execution on this branch only. They do not alter the hosted-CI baseline in §1, the NOT_RUN labels in §3–§5, or the Windows 3.12 NOT_RUN status (owner-dispatched; dispatch attempts returned 403 and are not retried).

| Suite | Command | Result |
|---|---|---|
| C1 behavioral + contracts (relocated to `tests/backend/c1/` per C1-R08) | `python -m pytest tests/backend/c1 -q` | 205 passed, 0 failed, 0 skipped (C1 revision complete: C1-R01..C1-R09 applied) |
| Legacy backend + contracts | `python -m pytest tests/contracts tests/backend -q -W error` | 898 passed (unchanged from baseline; warnings-as-errors clean) |

Combined local total for this branch: 1,103 passed, 0 failed.

---

# Appendix A — Post-merge C1 evidence and closure-branch execution (appended 2026-11-27)

**Append-only.** §1–§6 above keep their original text, including every `NOT_RUN` label and
every inherited failure. This appendix adds evidence; it deletes nothing.

## A.1 Hosted CI at the exact merged baseline `2a8a209fba20d0c7c43c255ede4545bcaa5f34b7`

Read from the GitHub Actions API, not from a report. `total_count = 4` for that `head_sha`;
all four `status: completed`, `conclusion: success`; **every job** individually confirmed at
the same SHA.

| Workflow | Run | Jobs (all at `2a8a209…`) | Conclusion |
|---|---|---|---|
| mock-backend-validation | [45925221406](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/45925221406) | Mock backend (Python 3.12), Mock backend (Python 3.11) | SUCCESS / SUCCESS |
| contract-validation | [45925221497](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/45925221497) | Contract and fixture validation | SUCCESS |
| audit-toolchain-validation | [45925221365](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/45925221365) | Dataset audit toolchain (Python 3.11), (Python 3.12) | SUCCESS / SUCCESS |
| synthetic-experiment-runner-validation | [45925221446](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/45925221446) | Synthetic experiment runner (Python 3.11), (Python 3.12), RH-04 fixture structural drift diagnostic (Python 3.12) | SUCCESS / SUCCESS / SUCCESS |

These are **post-merge** runs on the merged tree. They are not runs of this closure branch.

## A.2 Native Windows evidence received from the owner (recorded as supplied, not re-derived)

Verifier working directory `E:\CardioAssist-C1-Retest-f35326a6fd`.

| Check | Result |
|---|---|
| Environment identity, dependency-freeze match, final identity | exit 0 |
| Genuine legacy HTTP seed | exit 0 |
| `alembic upgrade head` / `current` / schema check | exit 0 |
| Legacy data preservation | exit 0 |
| Empty-C1 downgrade + re-upgrade | exit 0 |
| Enrollment / application restart | exit 0 |
| Focused migration + reviewer regression suite | **27 passed** in 71.86 s, exit 0 |
| Combined backend + contracts | **1159 passed** in 893.97 s, exit 0 |
| Source verification | exit 0 |
| Populated-database in-place downgrade | exit **1**, **expected** under the ratified invariant; preservation check exit 0 with full schema, all rows, revision, FKs and integrity unchanged |
| Isolated legacy backup restore | exit 0 |

Limitation, stated plainly: full Windows log files and per-suite counts beyond the two log
tails above were not supplied. Only those two counts are asserted. The pre-closure Windows
research run (**1093 passed, 9 failed, 4 skipped, 5 errors**) remains unresolved and is
**not** rerun by the focused retest and **not** waived — see A.4.

## A.3 Closure-branch local execution — exact commands, counts, exit codes

Branch `arena/807e6023-cardioassist-ai` from `2a8a209…`. Linux sandbox, Python 3.11.2,
`backend/requirements-dev.txt` + `research/audit/requirements.txt`.

| # | Command | Result | Exit |
|---|---|---|---|
| 1 | `python -m pytest tests/backend/c1/test_c1_http_closure.py -q -W error` | **30 passed**, 0 failed, 0 skipped | 0 |
| 2 | `python -m pytest tests/backend/c1 -q -W error` | **291 passed**, 0 failed, 0 skipped | 0 |
| 3 | `python -m pytest tests/contracts tests/backend -q -W error` | **1189 passed**, 0 failed | 0 |
| 4 | `python -m pytest tests/audit -q -W error` | **711 passed**, 0 failed | 0 |
| 5 | `python -m pip check` | `No broken requirements found.` | 0 |
| 6 | `python scripts/verify_sources.py` | 4 source hashes OK; supervisor audit 25 papers `{APPROVED_GREEN 9, MAYBE_PINK 1, MAYBE_ORANGE 6, REJECTED_RED 9}` | 0 |
| 7 | `python -m alembic upgrade head` (fresh disposable DB) | head `20261126_06` | 0 |
| 8 | `python -m alembic current` | `20261126_06 (head)` | 0 |
| 9 | `python -m alembic check` | `No new upgrade operations detected.` | 0 |
| 10 | `git diff --check` | no whitespace errors | 0 |

Count arithmetic, so the numbers are auditable rather than asserted: the accepted baseline
combined count was **1159**; this branch adds exactly **30** closure tests; `1159 + 30 =
1189`. The C1 suite rises from **261** to **291** by the same 30. Nothing was removed,
renamed or skipped.

`tests/experiments` and `tests/uci412`: **NOT_RUN**. The research dependency set is not
installed and this branch may not change research requirements, tolerances, fixtures or
workflows to obtain a result. Inherited Python 3.11 research drift (B-01 / Issue #132)
remains open.

## A.4 Unresolved separate Windows RH-04 portability findings — preserved, not modified

Recorded from the owner's pre-closure Windows run and left exactly as they are:

* **1093 passed, 9 failed, 4 skipped, 5 errors** in the Windows research suite.
* Failures confined to the **unchanged** RH-04 Issue #132 environment-classifier test
  module, including invalid Windows repository-path handling and an `RTLD_NOLOAD` AST
  assertion requiring a platform flag that does not exist on Windows.
* Cause class: **platform portability**, not a Term 1 prototype regression.
* Disposition: **separate unresolved research findings** on the RH-04 / Issue #132 track.
  No waiver, no research edit, no tolerance change, no fixture change, no workflow change,
  no AI-gate change, and no `ALL_GREEN` claim.

This branch touches no file under `research/`, `tests/experiments/`, `tests/audit/`,
`tests/uci412/`, `tests/manuscript_audit/`, `.github/` or `ai/`.

## A.5 Load-bearing proof for the two fixes (negative controls)

| Reverted change | Focused command | Result |
|---|---|---|
| `backend/app/term1/api.py` (D-01: 503 vs 500) | `pytest ... -k missing_configuration` | **11 failed**, 9 passed — the `500 text/plain` responses |
| two response schemas (D-02: replay field) | `pytest ... -k secret_free_replays` | **1 failed** — `Additional properties are not allowed ('idempotent_replay' was unexpected)` |

Both reverts were restored immediately and the tree re-verified with `git diff --check`.
A test that passes either way would prove nothing; these do not.

## A.6 Honest evidence classification

| Label | Applies to |
|---|---|
| `SOURCE_VERIFIED` | merged SHA, merge parents, tree equality, branch head, file inventory, migration head, source hashes |
| `GITHUB` / `API_VERIFIED` | PR #144 merged state, acceptance comment identities and timestamps, the four post-merge runs and all eight jobs at `2a8a209…` |
| `EXECUTED_LOCALLY` | the ten commands in A.3 and the two negative controls in A.5 |
| `OWNER_REPORTED` | the Windows table in A.2 (log tails supplied; full logs not supplied) |
| `NOT_RUN` | `tests/experiments`, `tests/uci412`, hosted CI at this branch's head, native Windows of this branch |
| `UNRESOLVED` | B-01 / B-09 / B-17 / B-18 research track; B-06 commit provenance |

**No `ALL_GREEN` claim.** Hosted CI at this exact head is `OWNER_DISPATCH_REQUIRED`; zero
checks is not success.

---

# Appendix B — Reviewer-corrected C1 closure candidate (appended 2026-11-27)

Append-only. Appendix A records the first closure candidate at `b860efc`. This appendix
records the corrected candidate produced after independent review, on the same branch and
the same PR #145. Nothing above is edited, and no earlier `NOT_RUN` label is cleared.

## B.1 What changed and why

The independent review published the residual list and a **proposed, not
runtime-executed** corrective branch (`review/term1-closure-residuals-b860efc`, head
`f81c37b9ff0ba8d4d498fc6a5ffce1171b801e01`). Its four commits were cherry-picked onto
`arena/807e6023-cardioassist-ai` from `b860efc`; the resulting tree was verified
byte-identical to the reviewer's head before any further work:

```
mine:     2ea561503346345452e921ac1debdd739b67d0f4
reviewer: 2ea561503346345452e921ac1debdd739b67d0f4
```

Then the residuals were **executed**, not assumed, and the ones that reproduced were
corrected.

## B.2 The four reviewer regressions, as executed

| Test | Before correction | After correction |
|---|---|---|
| `test_reviewer_temporary_password_refresh_declares_exact_403` | passed (YAML already corrected) | passed |
| `test_reviewer_duplicate_registration_declares_exact_409` | passed | passed |
| `test_reviewer_invalid_link_identifier_declares_exact_422` | passed | passed |
| `test_reviewer_unexpected_c1_failure_matches_declared_500` | **FAILED** — `assert None == 'no-store'`, body `text/plain`, 500 | **passed** |

The 500 regression exposed the defect the reviewer predicted: an unexpected exception
escaped to the ASGI server as a bare `text/plain` `Internal Server Error` with no
`Cache-Control`, on all twenty C1 routes, because every handler caught `ApiError` alone
and `main.py`'s generic converter is scoped to the legacy routes. See
`TERM1_C1_HTTP_CLOSURE_EVIDENCE.md` Appendix A §A.2.

## B.3 Full verification of the corrected candidate

Linux sandbox, Python 3.11.2, `backend/requirements-dev.txt` + `research/audit/requirements.txt`.

| # | Command | Result | Exit |
|---|---|---|---|
| 1 | `pytest tests/backend/c1/test_c1_http_closure.py -q -W error` | **39 passed** (30 original + 9 reviewer) | 0 |
| 2 | `pytest tests/backend/c1 -q -W error` | **300 passed** | 0 |
| 3 | `pytest tests/contracts tests/backend -q -W error` | **1198 passed** | 0 |
| 4 | `pytest tests/audit -q -W error` | **711 passed** | 0 |
| 5 | `pip check` | `No broken requirements found.` | 0 |
| 6 | `python scripts/verify_sources.py` | 4 source hashes OK; 25-paper supervisor audit | 0 |
| 7 | `alembic upgrade head` / `current` / `check` (fresh disposable DB) | head `20261126_06`; no new upgrade operations | 0 |
| 8 | `git diff --check` | clean | 0 |

Auditable arithmetic: first candidate 30 closure tests → 39 (+9 reviewer regressions);
C1 suite 291 → 300 (+9); combined 1189 → 1198 (+9). Nothing was removed, renamed, skipped
or marked xfail to obtain these numbers.

## B.4 Negative controls — the corrections are load-bearing

| Reverted change | Focused command | Result |
|---|---|---|
| `backend/app/term1/api.py` (the unexpected-failure boundary) | `-k reviewer` | **1 failed, 8 passed** — the 500 regression returns to `text/plain` with no `no-store` |
| (same, reverted) | `-k missing_configuration` | **11 failed, 9 passed** (D-01, from the first candidate) |
| two revoke response schemas | `-k secret_free_replays` | **1 failed** — `idempotent_replay` unexpected (D-02) |

Each revert was restored immediately and the tree re-verified.

## B.5 One existing test was updated — and nothing was weakened

`tests/backend/c1/test_c1_enrollment_assignments.py::test_registration_rolls_back_completely_on_a_mid_transaction_failure`
previously asserted that a deliberately injected `RuntimeError` **propagated out of the
test client** (`with pytest.raises(RuntimeError)`). That assertion encoded the very defect
under review: propagation to the ASGI server is what produced the bare non-JSON 500.

It now asserts the corrected contract **and keeps every rollback assertion unchanged**:

```python
assert response.status_code == 500
assert response.headers["cache-control"] == "no-store"
assert response.json()["error"]["code"] == "internal_error"
assert "simulated persistence failure" not in response.text
```

The six orphan-table count assertions and the invitation-consumption assertion that
follow it were not touched. So the test now proves *more* than before: the fault is
reported as the declared redacted envelope **and** the transaction still rolled back
completely. No assertion was deleted, relaxed or skipped.

## B.6 Reachability audit

Codes were audited through the real call graph (AST call edges, raise sites only, transitive
closure from each C1 entry point), not from a sampled probe set:

**20 routes, 20 implementations, 0 reachable-but-undeclared codes.**

Honest limit: this is a **static over-approximation of reachability**. It answers "is any
code the code can raise missing from the served contract?" — the direction requested. It
does **not** claim every reachable code has been empirically observed, and no exhaustive
runtime-reachability claim is made. Two false-positive classes found while building the
audit (a code that was only *compared*, never raised; a code reached via a session helper)
are recorded in the closure evidence Appendix A §A.3 so the method can be reviewed.

## B.7 Still not claimed

* **No hosted CI at this HEAD** — B-15 unchanged; `OWNER_DISPATCH_REQUIRED`. Zero checks is
  not success.
* **No native Windows run of this branch** — B-16 unchanged.
* **`tests/experiments` and `tests/uci412`: `NOT_RUN`** — B-17 unchanged.
* **Windows RH-04 research failures stay unresolved** — B-18 unchanged, untouched.
* **No `ALL_GREEN` claim.** No C2 implementation, no model work, no AI gate change.

---

# Appendix C — Exception-log redaction verification (appended 2026-11-27)

Append-only. Appendix B recorded the reviewer-corrected candidate at `c9026a1`. This
appendix records the focused logging correction applied after that review. The reviewer's
three commits (`b816861`, `06993d1`, `5ab92f8`) were cherry-picked; the resulting tree was
verified byte-identical to the reviewer head `5ab92f8` (`78ef389306c2eca9a2e25e17f03c0e8bf9ec6f8c`)
before anything else was run.

## C.1 Commands, counts and exit codes

Linux sandbox, Python 3.11.2, `backend/requirements-dev.txt` + `research/audit/requirements.txt`.

| # | Command | Result | Expected | Exit |
|---|---|---|---|---|
| 1 | `pytest tests/backend/c1/test_c1_http_closure.py -q -W error` | **39 passed**, 0 failed, 0 skipped | 39 | 0 |
| 2 | `pytest tests/contracts tests/backend -q -W error` | **1198 passed**, 0 failed | 1198 | 0 |
| 3 | `pytest tests/audit -q -W error` | **711 passed**, 0 failed | 711 | 0 |
| 4 | `pip check` | `No broken requirements found.` | clean | 0 |
| 5 | `python scripts/verify_sources.py` | 4 source hashes OK; 25-paper supervisor audit | clean | 0 |
| 6 | `alembic upgrade head` / `current` / `check` (fresh disposable DB) | head `20261126_06`; no new upgrade operations | unchanged | 0 |
| 7 | `git diff --check` | clean | clean | 0 |

All three expected counts held exactly. **No additional regression test was introduced**,
so no count was justified upward: the strengthened assertions were added to an existing
fault-injection test rather than as a new test, and the totals are unchanged at 39 / 1198 /
711.

## C.2 Negative controls

| Reverted change | Focused command | Result |
|---|---|---|
| only the metadata-only log call (`logger.error(...)` → `logger.exception(..., exc_info=error)`) | `-k unexpected_c1_failure` | **1 failed** — the log assertion catches the exception payload |
| the whole unexpected-failure boundary (`api.py` from the previous candidate) | `-k reviewer` | **1 failed, 8 passed** (from Appendix B §B.4) |
| `api.py` D-01 fix | `-k missing_configuration` | **11 failed, 9 passed** |
| two revoke response schemas | `-k secret_free_replays` | **1 failed** |

Every revert was restored immediately and the tree re-verified with `git diff --check`.

## C.3 Scope containment

`git diff --name-only c9026a1..HEAD` touches exactly three paths:
`backend/app/term1/api.py`, `docs/term1/TERM1_C1_HTTP_CLOSURE_EVIDENCE.md`,
`tests/backend/c1/test_c1_http_closure.py` (plus this appendix). No path under `research/`,
`tests/experiments/`, `tests/audit/`, `tests/uci412/`, `tests/manuscript_audit/`, `ai/`,
`.github/`, `frontend/`, `infra/` or `prompts/`. No migration. Legacy
`shared/contracts/openapi.yaml` unchanged. No contract declaration changed by this
appendix — the corrections landed at `c9026a1` and are untouched here.

## C.4 Still not claimed

No hosted CI at this HEAD (**B-15**, owner dispatch; zero checks is not success). No native
Windows run of this branch (**B-16**). `tests/experiments` / `tests/uci412` **`NOT_RUN`**
(**B-17**). Windows RH-04 findings untouched (**B-18**). The logging assertion covers one
logger and one event, not every logging channel (§B.5). **No `ALL_GREEN` claim.**
