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
| B-12 | Exact-head dispatch results pending at final review | EVIDENCE | Four workflow_dispatch runs dispatched after correction push; see test evidence §5 and completion report | Zero checks previously reported for stage PR; no success claim until verified | Reviewer verifies run head SHA, conclusion and counts | C0/C4 |
| B-13 | Focused C0-F01…F10 corrections await final independent review | REVIEW | Corrected docs in PR #143 | C0 not accepted | Reviewer checks resolution matrix; owner confirms P-01…P-27 | C0 |

**Disposition rules:** a blocker is closed only with recorded evidence and owner decision. Inherited research failure B-01 remains visible even if independent C1 engineering proceeds. No blocker is closed by rerunning until green, suppressing a test, widening a tolerance, or changing a research gate.
