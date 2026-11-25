# CardioAssist-AI Term 1 — Stage Progress and Reviewer Correction Ledger

**Status:** C0 design package produced; not accepted. No implementation stage started.

## 1. Checkpoint ledger

| Item | Value | Evidence category |
|---|---|---|
| Review date | 2026-11-25 (UTC) | — |
| main | `c6a6bdee46a552a2b0d705a723c862ff8a95be4d` | SOURCE_VERIFIED / GITHUB |
| Prototype HEAD at C0 start | `bca75b4646dbde26e495201938b7ae01ea7e0d21` | GITHUB |
| PR #142 | OPEN / DRAFT, base main, 4 docs-only commits, `merged_at=null` | GITHUB |
| Test merge SHA | `8c4be2fb6d5d088d456ec5be935a2b30b5158173` — not a merge | GITHUB |
| PR #141 | OPEN / DRAFT, head `9fb6d5173171bbdc22fd1528131bd2dd5b8963f5` | GITHUB; boundary only |
| Issue #132 | OPEN | GITHUB; boundary only |
| Workspace branch used for C0 commit | `arena/bdbd8a6e-cardioassist-ai` at main baseline | SOURCE_VERIFIED; disclosure in plan §1.2 |
| Native Windows | NOT_RUN | — |

## 2. Status declarations

```
C0_STATUS=DESIGN_PENDING_INDEPENDENT_REVIEW_AND_OWNER_ACCEPTANCE
C1_STATUS=NOT_STARTED
C2_STATUS=NOT_STARTED
C3_STATUS=NOT_STARTED
C4_STATUS=NOT_STARTED
AI_SERVING_AUTHORIZATION=PENDING
PATIENT_SCORE_DISPLAY_AUTHORIZATION=PENDING
WINDOWS_VERIFICATION_STATUS=NOT_RUN
LEGACY_RESEARCH_CI_STATUS=FAILURE_ON_PYTHON_3_11 (inherited; not suppressed)
```

## 3. C0 deliverables produced

- `CARDIOASSIST_TERM1_PREFLIGHT_REVIEW_VERDICT.md` — independent reviewer verdict preserved in content (trailing whitespace normalized).
- `CARDIOASSIST_TERM1_ARENA_PREFLIGHT_REVIEW.md` — prior Arena preflight report preserved in content (trailing whitespace normalized).
- `TERM1_STAGE_EXECUTION_PLAN.md` — supersession, owner-approved vs proposed values, stage gates, CI baseline.
- `TERM1_C0_ARCHITECTURE_AND_CONTRACTS.md` — threat model, ERD/data dictionary, idempotency/secrets, state machines, canonical contract composition, migration ordering.
- `TERM1_API_INTEGRATION_MATRIX.md` — complete proposed operation inventory and regression strategy.
- `TERM1_AI_READINESS_MATRIX.md` — candidate matrix, candidate B design, A/B proposals.
- `TERM1_DECISION_REGISTER.md` — owner-approved direction, proposed defaults, pending authorizations.
- `TERM1_TEST_EVIDENCE.md` — CI baseline, test strategy, evidence labels.
- `TERM1_BLOCKER_REGISTER.md` — blockers and dispositions.
- `TERM1_WINDOWS_VERIFICATION_RUNBOOK.md` — corrected stage-based PS5.1 procedure.

Historical `TERM1_INTEGRATED_PROTOTYPE_MASTER_PLAN_20261125.md`, `ARENA_NEW_SESSION_MASTER_PROMPT_20261125.md`, `CARDIOASSIST_TERM1_NEW_CHAT_HANDOFF_20261125.md` and `WINDOWS_LOCAL_VERIFICATION_RUNBOOK_20261125.md` are preserved unchanged; the new plan records the supersession.

## 4. Reviewer correction resolution (R-01…R-08)

| ID | Owner/reviewer requirement | C0 resolution | Location | Verification needed |
|---|---|---|---|---|
| R-01 | Remove `patient.doctor_id`; assignment-based ownership; multiple authorized assignments; patient selection; historical freeze | No `patient.doctor_id` in ERD; doctor access via active `doctor_patient_assignment` and assessment `assignment_id`; `GET /v1/me/assignments` and `assignment_id` selection; revocation keeps history under original assignment | Architecture §3.6, §4, §7.4; API E3/D1/D2/H3 | Owner confirms P-12…P-14; C1 negative IDOR tests |
| R-02 | Bind identity at visit attestation; prevent B code on A visit; HMAC encoding/key separation/rotation; server timestamps; no clinical free text | Visit stores subject HMAC, invitation inherits; strict demo grammar; exact HMAC byte encoding; purpose separation; `demo-v1` with re-attestation rotation; `asserted_visit_at` vs `attested_at`; controlled attestation codes | Architecture §3.4, §3.5; API V1/I1 | Owner confirms P-09…P-11; C1 mismatch/rotation tests |
| R-03 | Add revoke, link/accept, assignment revoke, account lifecycle; lockout semantics; transport; fix indexes | I2, E2, E4/E5, AD2, A5 added; generic 401 lockout; bearer transport; indexes use actual columns; local admin bootstrap | API §2; Architecture §3.1–3.3, §5.2 | Owner confirms P-01…P-08; C1 contract tests |
| R-04 | Secret-safe idempotency; one-time disclosure/lost response; durable failure counters | Hash-only keys, redacted replay, `secret_not_redisclosable`, no token/code in records; failure rows in separate tx | Architecture §6; API §3 | C1 replay/lockout/rate-limit tests |
| R-05 | One authoritative result; generation/lease/fencing; review conflicts; follow-up eligibility; test doubles only in tests | Single `inference_result`; generation/fence CAS; history retained, stale hidden; review conflict rules; no AI prescription author | Architecture §4, §7.3–7.4 | C2/C3 tests; Decision A |
| R-06 | One canonical served OpenAPI; complete allowlist; preserve legacy coverage; headers as headers | Deterministic composition into single served spec; legacy file unchanged; four named test classes; headers in `parameters` | Architecture §8; API §1 | C1/C2 contract tests and owner confirmation |
| R-07 | PS5.1 exit-code checks; safe clone reuse; fresh DBs; exact pytest paths; correct deps | New Windows runbook with explicit `$LASTEXITCODE`, ff-only fetch/merge, unique DBs, preservation DB, exact paths, full-suite deps | `TERM1_WINDOWS_VERIFICATION_RUNBOOK.md` | Owner Windows execution (NOT_RUN) |
| R-08 | Exact candidate B, A/B proposals, deterministic trust/rights, no clinical claim | Full candidate B design, exact A/B ratification text, rebuild/digest/trust requirements, non-authorizations | `TERM1_AI_READINESS_MATRIX.md` | Owner decisions A/B; C2 independent review |

## 5. Stage readiness

| Stage | Readiness | Reason |
|---|---|---|
| C0 | DESIGN_PENDING_ACCEPTANCE | Docs complete; independent review and owner confirmation of proposed defaults pending |
| C1 | NOT_STARTED | C0 acceptance required; contract change-set and technical defaults pending |
| C2 | NOT_STARTED | C1 acceptance, Decision A or documented safe-scope decision, artifact/dependency decision required |
| C3 | NOT_STARTED | C2 acceptance or explicit owner scope revision required |
| C4 | NOT_STARTED | Prior stages and evidence required |

This ledger does not constitute self-acceptance. Only the independent reviewer and human owner may accept C0.
