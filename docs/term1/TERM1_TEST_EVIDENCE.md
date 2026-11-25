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
| C0 | Documentation consistency, exact SHA/PR checks | No source/migration/contract/workflow change; no PHI/model artifacts | Exact head, diff/stat, CI links, reviewer verdict, owner Windows baseline |
| C1 | Admin/doctor provision; login/logout; visit attestation; invitation issue/revoke; register; link; assignment list/revoke; restart persistence; Alembic upgrade/current/check | wrong/expired/revoked/consumed code; wrong identifier; subject mismatch visit A→patient B; duplicate identifier; two-connection concurrent redemption; cross-doctor/patient IDOR; suspended user; lockout; no raw ID/token/code in logs/API/DB; rollback orphan check; replay no secret redisclosure; legacy route regressions | Backend+contract CI at exact head; migration evidence; Windows output |
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

`NOT_RUN`. The owner must execute `TERM1_WINDOWS_VERIFICATION_RUNBOOK.md` and supply exact PowerShell version, OS build, Python version, exit codes, test counts, migration output, source verification output, git diff result and smoke/restart transcripts. Hosted Linux CI does not substitute.
