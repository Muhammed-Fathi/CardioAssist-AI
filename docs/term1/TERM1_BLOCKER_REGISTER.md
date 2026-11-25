# CardioAssist-AI Term 1 — Blocker Register

**Status:** live register at C0. A blocker may be inherited, authorization-gated, or evidentiary; none is waived by this document.

| ID | Blocker | Category | Evidence | Impact | Owner / resolution | Affected stage |
|---|---|---|---|---|---|---|
| B-01 | Python 3.11 synthetic runner failure (UCI-412 calibrated-log-odds delta `4.441e-16`, forced-dispatch JSONDecodeError, 10 downstream errors) | INHERITED_RESEARCH | Run 45650285465; Issue #132 OPEN | No ALL_GREEN claim; separate from prototype correctness; keep in evidence | Owner acknowledges; research track investigates separately; no fixture/tolerance/workflow change | C4 reporting; all status reports |
| B-02 | Decision A (local-demo inference adapter) not ratified | AUTHORIZATION | `TERM1_AI_READINESS_MATRIX.md` §3.1 | C2 full AI integration cannot proceed; no model execution | Owner ratifies exact text after independent implementation review | C2 |
| B-03 | Decision B (patient score display) not ratified | AUTHORIZATION | `TERM1_AI_READINESS_MATRIX.md` §3.2 | Patient projection status-only | Owner ratifies exact text and wording | C2/C3 |
| B-04 | Native Windows evidence absent | EVIDENCE | No owner output supplied | No stage VERIFIED | Owner executes Windows runbook and supplies transcript | All stages |
| B-05 | Artifact trust/distribution and backend numerical dependency pins undecided | DESIGN/AUTHORIZATION | `.gitignore` excludes artifacts; `backend/requirements.txt` has no numpy/scikit-learn/joblib | Candidate B cannot be served or handed off without decision | Owner chooses deterministic rebuild vs curated bundle; approves pins under A | C2/C4 |
| B-06 | C0 commit publication target deviation | PLATFORM CONSTRAINT | Session fixed to `arena/bdbd8a6e-cardioassist-ai` at main; remote prototype ref verified `bca75b4…` | Docs are committed on session branch, not prototype branch | Owner confirms cherry-pick transfer or authorizes alternative | C0 acceptance |
| B-07 | Technical defaults P-01…P-20 not yet confirmed | DECISION | `TERM1_DECISION_REGISTER.md` §2 | C1 implementation choices not final | Owner confirms/amends at C0 acceptance | C0/C1 |
| B-08 | Exact C0 design not yet independently reviewed | REVIEW | Reviewer verdict accepted preflight, not this package | C0 not accepted | Independent reviewer checks docs/diff/CI | C0 |
| B-09 | PR #141 dual-run gate failing; Issue #132 open | BOUNDARY | PR #141 head `9fb6d517…`; dual gate run 45643212294 failure | Research track remains unresolved; no import into prototype | Owner/research track only; Term 1 does not touch | C4 reporting |
| B-10 | Handoff date 2026-12-03 at high risk | SCHEDULE | C0 docs-only; C1–C4 not started | Full scope may not be complete by target | Owner may accept revised scope explicitly; no silent reduction | C4 |

**Disposition rules:** a blocker is closed only with recorded evidence and owner decision. Inherited research failure B-01 remains visible even if independent C1 engineering proceeds. No blocker is closed by rerunning until green, suppressing a test, widening a tolerance, or changing a research gate.
