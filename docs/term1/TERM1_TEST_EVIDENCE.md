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
