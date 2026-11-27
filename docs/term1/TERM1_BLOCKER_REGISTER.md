# CardioAssist-AI Term 1 — Blocker Register

**Status:** live register at C0. A blocker may be inherited, authorization-gated, or evidentiary; none is waived by this document.

| ID | Blocker | Category | Evidence | Impact | Owner / resolution | Affected stage |
|---|---|---|---|---|---|---|
| B-01 | Python 3.11 synthetic runner failure (UCI-412 calibrated-log-odds delta `4.441e-16`, forced-dispatch JSONDecodeError, 10 downstream errors) | INHERITED_RESEARCH | Run 45650285465; Issue #132 OPEN | No ALL_GREEN claim; separate from prototype correctness; keep in evidence | Owner acknowledges; research track investigates separately; no fixture/tolerance/workflow change | C4 reporting; all status reports |
| B-02 | Decision A (local-demo inference adapter) not ratified | AUTHORIZATION | `TERM1_AI_READINESS_MATRIX.md` §3.1 | C2 full AI integration cannot proceed; no model execution | Owner ratifies exact text after independent implementation review | C2 |
| B-03 | Decision B (patient score display) not ratified | AUTHORIZATION | `TERM1_AI_READINESS_MATRIX.md` §3.2 | Patient projection status-only | Owner ratifies exact text and wording | C2/C3 |
| B-04 | Native Windows evidence absent | EVIDENCE | No owner output supplied | No stage VERIFIED | Owner executes Windows runbook and supplies transcript | All stages |
| B-05 | Artifact trust/distribution and backend numerical dependency pins undecided | DESIGN/AUTHORIZATION | `.gitignore` excludes artifacts; `backend/requirements.txt` has no numpy/scikit-learn/joblib | Candidate B cannot be served or handed off without decision | Owner chooses deterministic rebuild vs curated bundle; approves pins under A | C2/C4 |
| B-06 | C0 publication route and unrecoverable original commits | PLATFORM CONSTRAINT / EVIDENCE | PR #143 published from session branch at `a32aca2…` to prototype base `bca75b4…`; original five SHAs absent from GitHub (422) and local objects; five reconstructed commits disclosed in plan §1.2 | Stage PR policy supersedes cherry-pick; provenance needs owner acknowledgment | Owner acknowledges reconstructed-vs-original distinction and stage-PR route; no merge before acceptance | C0 acceptance |
| B-07 | Technical defaults P-01…P-20 not yet confirmed | DECISION | `TERM1_DECISION_REGISTER.md` §2 | C1 implementation choices not final | Owner confirms/amends at C0 acceptance | C0/C1 |
| B-08 | Exact C0 design not yet independently reviewed | REVIEW | Reviewer verdict accepted preflight, not this package | C0 not accepted | Independent reviewer checks docs/diff/CI | C0 |
| B-09 | PR #141 dual-run gate failing; Issue #132 open | BOUNDARY | PR #141 head `9fb6d517…`; dual gate run 45643212294 failure | Research track remains unresolved; no import into prototype | Owner/research track only; Term 1 does not touch | C4 reporting |
| B-10 | Handoff date 2026-12-03 at high risk | SCHEDULE | C0 docs-only; C1–C4 not started | Full scope may not be complete by target | Owner may accept revised scope explicitly; no silent reduction | C4 |
| B-11 | Native Windows verification of reviewed PR candidate absent | EVIDENCE | `TERM1_WINDOWS_VERIFICATION_RUNBOOK.md` NOT_RUN at `a32aca2…` | C0 acceptance blocked | Owner runs complete PS5.1 block and supplies transcript | C0 |
| B-12 | Exact-head dispatch requires owner authorization | PLATFORM/EVIDENCE | Four workflow_dispatch attempts rejected `HTTP 403: Resource not accessible by integration`; `total_count=0` at final head | No CI success can be claimed for stage PR; zero checks is not success | Owner dispatches four existing workflows on final SHA with authorized account; reviewer verifies head SHA/conclusions/counts | C0/C4 |
| B-13 | Focused C0-F01…F10 corrections await final independent review | REVIEW | Corrected docs in PR #143 | C0 not accepted | Reviewer checks resolution matrix; owner confirms P-01…P-27 | C0 |

**Disposition rules:** a blocker is closed only with recorded evidence and owner decision. Inherited research failure B-01 remains visible even if independent C1 engineering proceeds. No blocker is closed by rerunning until green, suppressing a test, widening a tolerance, or changing a research gate.

---

# Appendix A — Blocker state after C1 acceptance (appended 2026-11-27)

Append-only. §1 above keeps every original row verbatim, including rows now superseded.
This appendix states the **current** disposition and adds the new blockers found during
closure. A closed row is closed only with recorded evidence; nothing is closed by rerunning
until green, suppressing a test, widening a tolerance or changing a research gate.

## A.1 State changes

| ID | Previous state | Current state | Basis |
|---|---|---|---|
| B-02 | Decision A not ratified | **OPEN — narrowed** | A1/A2/A3 all PENDING. Now scoped: C2 W1…W7 are buildable *without* A in a documented `C2_SAFE_SCOPE`; only a **score** requires A3 (and only a patient-visible score requires B). Requires owner decision OQ-1 |
| B-03 | Decision B not ratified | **OPEN** | Unchanged. Patient projection stays status-only. Warning wording is OQ-9 |
| B-04 | Native Windows evidence absent | **PARTIALLY_CLOSED at `524d57c` / `2a8a209`** | Owner supplied the retest transcript and two log tails (27 passed; 1159 passed) and exit codes for all other steps. Still OPEN for **this closure branch** and still OPEN for full per-suite Windows counts |
| B-05 | Artifact trust/distribution undecided | **OPEN — actioned as OQ-6** | Deterministic rebuild vs curated bundle must be decided before A3. `backend/requirements.txt` still has no numerical dependency, by design |
| B-07 | Technical defaults P-01…P-20 unconfirmed | **OPEN — narrowed** | C1 was implemented and accepted; the C2-relevant defaults (P-16 lease/fence, P-25 migration placement) need explicit confirmation as OQ-3 and OQ-8 |
| B-12 | Exact-head dispatch 403 | **OPEN** | Still `OWNER_DISPATCH_REQUIRED`; applies to this branch's head (B-16) |
| B-13 | Focused C0 corrections pending review | **CLOSED** | C0 accepted and the bounded C1 baseline built on it was owner-accepted and merged |

## A.2 B-14 — closed

| ID | Blocker | Resolution | Evidence |
|---|---|---|---|
| **B-14** | Outstanding HTTP contract coverage obligations: no explicit twenty-operation non-skipping proof, no replay-variant proof, no missing-configuration (503) proof, no unnormalised raw-response validation | **CLOSED_ENGINEERING_PENDING_INDEPENDENT_REVIEW** | `tests/backend/c1/test_c1_http_closure.py` (30 tests, no conditional skipping); fixes D-01/D-02/D-03; `TERM1_C1_HTTP_CLOSURE_EVIDENCE.md` §3/§5. Three defects were found and fixed rather than the assertions weakened |

Closure is **not** acceptance: independent review and owner acceptance are still required.

## A.3 New blockers

| ID | Blocker | Category | Evidence | Impact | Owner / resolution | Affected stage |
|---|---|---|---|---|---|---|
| **B-15** | No hosted CI run exists at this closure branch's exact head | EVIDENCE | Four `workflow_dispatch` attempts at C0 returned `HTTP 403: Resource not accessible by integration`; unchanged for this branch | No CI success can be claimed for the closure PR; zero checks is not success | Owner dispatches the four existing workflows on the final SHA; reviewer verifies run head SHA, conclusions and counts | C1 closure acceptance; C2 gate |
| **B-16** | Closure branch not executed on native Windows | EVIDENCE | Linux-only execution for the 503 matrix, replay matrix and `x-error-codes` closure | Windows parity of the new proofs is unproven; hosted Linux does not substitute | Owner runs the focused closure suite + combined backend/contracts on Windows and supplies counts and exit codes | C1 closure acceptance |
| **B-17** | `tests/experiments` and `tests/uci412` not executed here | INHERITED_RESEARCH / ENVIRONMENT | `NOT_RUN`: research dependency set (numpy, scikit-learn, …) not installed; changing research requirements is out of scope | No full-suite claim; B-01/B-09 remain live | Research track only; this branch may not change requirements, tolerances, fixtures or workflows | C4 reporting |
| **B-18** | Windows RH-04 portability failures unresolved | INHERITED_RESEARCH | Pre-closure Windows research run 1093 passed / **9 failed** / 4 skipped / **5 errors**, confined to the unchanged RH-04 Issue #132 environment-classifier module (Windows path handling, `RTLD_NOLOAD` AST assertion) | Separate research-track failure; not a prototype regression, and not waived | RH-04 / Issue #132 track only; PR #141 untouched | Research track |
| **B-19** | C2 scope requires an owner decision before any C2 code | AUTHORIZATION / DESIGN | `TERM1_C2_IMPLEMENTATION_DEPENDENCY_MAP.md` §6 | C2 cannot start: OQ-1 (safe scope), OQ-2 (snapshot form), OQ-7 (S1 replay target) are hard blockers on W1/W2 | Owner answers OQ-1…OQ-10 | C2 |
| **B-20** | C0 reconstructed-vs-original commit provenance not yet acknowledged | EVIDENCE / PLATFORM | Original five C0 SHAs unrecoverable; five reconstructed commits disclosed in the plan §1.2 | C0 provenance needs an explicit owner acknowledgement; no rewrite or merge implies it | Owner acknowledges the distinction | C0 record |

## A.4 Disposition rules (unchanged)

A blocker closes only with recorded evidence **and** an owner decision. Inherited research
failures stay visible forever. No blocker is closed by rerunning until green, suppressing a
test, widening a tolerance, deleting evidence or changing a research gate.

## A.5 Blocker updates after independent review (2026-11-27)

| ID | Change | Basis |
|---|---|---|
| **B-14** | Remains **CLOSED_ENGINEERING_PENDING_INDEPENDENT_REVIEW**, scope broadened: the reviewer's residual list (R-1…R-7) is now also addressed | `TERM1_C1_HTTP_CLOSURE_EVIDENCE.md` Appendix A |
| **B-21** (new) | **Runtime defect: unexpected C1 exceptions escaped as bare `text/plain` 500 with no `Cache-Control`** — the declared `500 internal_error` envelope was never produced for non-`ApiError` faults. **FIXED** with a uniform unexpected-failure boundary on all 20 routes; proven load-bearing by negative control | `TERM1_TEST_EVIDENCE.md` Appendix B §B.2/B.4 |
| **B-22** (new) | **Contract under-declaration**: shared `verify_or_activate` 409 refusals and `role_profile_mismatch` were reachable but undeclared on up to 11 routes, and `POST /v1/auth/login` declared no 409 at all. **FIXED**; static reachability audit now reports 0 undeclared reachable codes over 20 routes | `TERM1_C1_HTTP_CLOSURE_EVIDENCE.md` Appendix A §A.3 |
| **B-23** (new) | **Weak failure-coverage assertion**: failure probes compared bare paths (method-blind) and wrong-role probes accepted any `>= 400`. **FIXED** — `(METHOD, template)` pair equality plus 12 operations pinned to exact `403 forbidden` | same |
| **B-15/B-16/B-17/B-18** | Unchanged and still open | — |

## A.6 Blocker update after focused logging review (2026-11-27)

| ID | Change | Basis |
|---|---|---|
| **B-24** (new) | **Disclosure risk in operational logging**: the unexpected-failure boundary logged the full exception with `exc_info`, so SQLAlchemy statements, bound parameters, submitted identifiers or key material could reach log aggregation and long-term retention. The HTTP response was already static and `no-store`; the log was the residual surface. **FIXED** — one metadata-only ERROR event, no `exc_info`/`stack_info`/`traceback` anywhere under `backend/app/term1/`; proven load-bearing by negative control | `TERM1_C1_HTTP_CLOSURE_EVIDENCE.md` Appendix B; `TERM1_TEST_EVIDENCE.md` Appendix C §C.2 |
| **B-14** | Remains **CLOSED_ENGINEERING_PENDING_INDEPENDENT_REVIEW**; scope now also covers R-8 (log redaction) | same |
| **B-15/B-16/B-17/B-18** | Unchanged and still open | — |

Limit recorded with the fix: the assertion covers the `cardioassist.term1.api` logger and
the `term1 operation failed unexpectedly` event on the fault-injection path. It is **not** a
claim that every logging channel has been audited — the legacy `main.py` handler,
SQLAlchemy engine logging configuration and the audit tables remain separate surfaces.
