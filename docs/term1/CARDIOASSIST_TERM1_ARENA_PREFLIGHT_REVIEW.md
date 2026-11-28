# CardioAssist-AI — Term 1 Arena Independent Read-Only Engineering Preflight Review

**Report file:** `preflight/CARDIOASSIST_TERM1_ARENA_PREFLIGHT_REVIEW.md` (untracked deliverable; no tracked repository file was changed)
**Review date / timezone:** 2026-11-25 / UTC (user-local date supplied as 2026-11-25)
**Reviewer role:** Arena implementation engineer acting ONLY as independent preflight reviewer
**Assignment:** READ-ONLY engineering preflight; no implementation, no commits, no pushes, no PR/issue/workflow changes, no research-track changes, no dataset/model execution
**Repository:** https://github.com/Muhammed-Fathi/CardioAssist-AI
**Prototype branch:** `delivery/term1-prototype`; **Draft PR:** https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/142
**Boundary PR:** https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/141 (research track; not touched)
**Boundary issue:** https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/132 (remains OPEN; not closed)
**Native Windows workspace (owner-controlled, not verified here):** `E:\CardioAssist-Term1-Prototype`
**Planning handoff date:** 2026-12-03 — planning target only, NOT a commitment
**Final preflight recommendation:** `ACCEPT_WITH_CHANGES` (justified in §18)

## Evidence-category vocabulary used throughout

| Category | Meaning in this report |
|---|---|
| `SOURCE_VERIFIED` | Directly read from a file in the checkout or from GitHub at an exact ref. |
| `HOSTED_CI_VERIFIED` | GitHub Actions / check conclusion verified through the GitHub API or PR checks at an exact SHA; line-level logs may be separately marked `UNVERIFIED`. |
| `OWNER_WINDOWS_VERIFIED` | Only evidence actually produced by the owner on native Windows. **None exists in this review.** |
| `AGENT_REPORTED` | A claim made by an agent or a document without direct corroboration here. |
| `PROPOSED` | Engineering design not implemented. |
| `PENDING_AUTHORIZATION` | A named owner decision is required before execution or exposure. |
| `BLOCKED` | An authorization or technical gate currently prevents the operation. |
| `NOT_RUN` | Test/command not executed by this review. |
| `UNVERIFIED` | Evidence exists but could not be independently confirmed under the read-only restrictions or available network paths. |

**Global limitation:** this review did not run pytest, did not execute the application, did not train or load any model, did not run the private Cleveland bundle, did not access real data, did not perform Windows verification, and did not modify the repository. All test counts from prior workflow records are labelled according to how they were actually obtained. All Windows blocks in §13 are `NOT_RUN` until the owner executes them and supplies the output.

---

## 1. Executive engineering verdict

**Verdict.** The provisional C0–C4 stage structure is a defensible backbone, but it is **not acceptable as written**. The stage plan must be tightened into explicit, owner-gated engineering units; C0 must produce and have approved the frozen architecture/contracts/decision register before C1; C2 must not be reported complete if Track A authorization remains absent; C3 must not start without C2 acceptance or a documented revised-scope decision; and C4 must not claim success while the inherited Python 3.11 research failure is unroot-caused.

**Most important facts established from live evidence:**

1. PR #142 is **OPEN, DRAFT, four documentation-only commits ahead of `main`**, with no application source, migration, contract, AI adapter, or test changes. The merged base and prototype HEAD are exactly the expected SHAs. `mergeable_state=unstable` because one required/existing workflow job fails; the PR has no posted comments or reviews. (`SOURCE_VERIFIED`, `HOSTED_CI_VERIFIED`)
2. The shipped backend implements exactly two POST operations — `POST /v1/predictions/cad-tabular` (`MOCK_SYNTHETIC`) and `POST /v1/monitoring/observations` (durable Track-B persistence) — and exact-operation tests assert that no other path exists. No auth, RBAC, visits, invitations, assessments, reviews, prescriptions, messages, notifications, or workflow history are implemented. (`SOURCE_VERIFIED`)
3. Persistence is exactly three tables: `monitoring_observation`, `monitoring_metric`, `audit_event`. `audit_event.observation_record_id` is **NOT NULL** with a foreign key to `monitoring_observation.record_id` and is unique per observation. It cannot be reused as a general workflow audit table without inventing fake monitoring rows, which is prohibited. A dedicated `workflow_audit_event` is the smallest safe design. (`SOURCE_VERIFIED`)
4. Startup schema validation is genuinely fail-closed and read-only: `Database.verify_schema()` checks Alembic head, table presence, primary keys, autogenerate drift, SQLite FK enablement, integrity check, and FK check; startup never migrates. This is a strong reusable foundation. (`SOURCE_VERIFIED`)
5. The existing idempotency cache, attempt counters, and audit snapshot are **process-local** (`MockState`) under a single global lock; they are explicitly not durable exactly-once guarantees. They must not be reused as the registration or workflow guarantee. (`SOURCE_VERIFIED`)
6. Real-model HTTP serving is not authorized and not implemented: `backend/app/inference/registry.py` can construct only `MockSyntheticProvider`; `FailClosedRealModelProvider.__init__` always raises. The offline D-049/A3 registry is **nonempty at current `main`**, but its exact operation is only `offline_synthetic_input_diagnostic_inference`, bound to the frozen real Cleveland bundle, local Windows offline execution, an exact activation revision, a clean worktree, and an ignored local operator authorization. It does not authorize HTTP serving, patient scores, retraining, or use at prototype HEAD. (`SOURCE_VERIFIED`)
7. The offline research facade accepts only deliberately fabricated synthetic fixtures with a registered generator/seed/reference and `input_source=structured_synthetic_research`. A patient-entered assessment cannot legitimately be relabelled `clinician_entry` or `benchmark_import`, and a bare `synthetic: true` flag is rejected. A new server-enforced, separately approved synthetic-demo provenance contract is required. (`SOURCE_VERIFIED`)
8. The newest PR #142 workflow checkpoint is the one supplied in the assignment: run `45650285465` at prototype HEAD — Python 3.11 synthetic runner **failure**, Python 3.12 synthetic runner success, structural diagnostic success; backend, contract, and audit workflows success. The inherited four-digit binary64 drift defect (Issue #132) remains open, and PR #141's `rh04-dual-run-gate` is failing. `ALL_GREEN` is not a truthful status. (`HOSTED_CI_VERIFIED`)
9. `docs/term1/CARDIOASSIST_TERM1_NEW_CHAT_HANDOFF_20261125.md` records an older prototype HEAD (`c11555c…`) and three planning files; live PR #142 is at `bca75b4…` and has four files. This is a stale status description, not a reason to rewrite the historical document. (`SOURCE_VERIFIED`)
10. Flutter and React directories contain placeholders only. They are software-team responsibilities; no client implementation is evidence of integration readiness. (`SOURCE_VERIFIED`)

**Engineering recommendation:** accept the five-stage shape **with changes** described in §§11–13: freeze C0 outputs first; add explicit owner decision gates D-A (inference adapter) and D-B (patient score display); add a dedicated workflow audit table and durable idempotency from C1; preserve additive contract tests in C2/C3; treat C2 as conditionally scoped if Track A remains blocked; and require exact-head hosted CI plus native Windows evidence for acceptance of C4.

---

## 2. Exact live repository and CI checkpoint

All GitHub data below was refreshed during this review through `gh api` / `gh pr checks` and direct source inspection.

| Item | Verified value | Evidence |
|---|---|---|
| `main` HEAD | `c6a6bdee46a552a2b0d705a723c862ff8a95be4d` (commit date `2026-11-22T20:24:06+02:00`, merge PR #140) | Local `git rev-parse main`; `gh api repos/.../branches` |
| Local Arena branch | `arena/bdbd8a6e-cardioassist-ai` at `c6a6bde…`, clean worktree | `git status --short --branch`; no files changed by review |
| Prototype HEAD | `bca75b4646dbde26e495201938b7ae01ea7e0d21` | `git ls-remote --heads origin`; GitHub branches API |
| Prototype ancestry | `ahead_by=4`, `behind_by=0`, `status=ahead` vs `main`; four added files only | https://github.com/Muhammed-Fathi/CardioAssist-AI/compare/c6a6bdee46a552a2b0d705a723c862ff8a95be4d...bca75b4646dbde26e495201938b7ae01ea7e0d21 |
| PR #142 commits | `6ef6d8f7cd0961d2235e5aa7865aab2b67632c5e`, `2631dd22b40a557006418b79591a4e0cdb78cde9`, `c11555c713321f0ed700a43347766971582dfffc`, `bca75b4646dbde26e495201938b7ae01ea7e0d21` | GitHub PR commits API |
| PR #142 metadata | OPEN, DRAFT, base `main`, 4 commits, 4 changed files, +546/-0, updated `2026-11-25T16:00:05Z`, `mergeable_state=unstable`, zero comments, zero reviews | https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/142 |
| PR #142 test merge SHA | `8c4be2fb6d5d088d456ec5be935a2b30b5158173` — a **test merge**, not a completed merge; `merged_at=null` | GitHub PR API |
| Research PR #141 | OPEN, DRAFT, head `9fb6d5173171bbdc22fd1528131bd2dd5b8963f5`, 28 commits, 61 changed files, updated `2026-11-25T15:36:37Z` | https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/141 |
| Issue #132 | OPEN, `OPEN_REPRODUCIBILITY_DEFECT`, updated `2026-11-21T13:45:03Z`, 6 comments | https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/132 |
| PR #142 exact-head workflow runs | `45650285465` synthetic experiment runner (**failure**), `45650285433` audit (**success**), `45650285403` contract (**success**), `45650285373` backend (**success**) | GitHub Actions runs API |
| Run `45650285465` jobs | 3.11 synthetic runner `139332628376` failure; 3.12 synthetic runner `139332628534` success; 3.12 structural diagnostic `139332628013` success | https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/45650285465 |
| PR `gh pr checks 142` | 5 pass / 1 fail: 3.11 synthetic fail; contract/audit 3.11+3.12/backend 3.11+3.12/structural 3.12 pass | `gh pr checks 142` |
| Prior reviewer-recorded counts | 3.11: 1808 passed, 2 failed, 10 setup errors, 2 skipped; 3.12: 1820 passed, 2 skipped; structural success | `AGENT_REPORTED` from assignment; current job conclusions `HOSTED_CI_VERIFIED`; line-level counts `UNVERIFIED` here because job log redirect targets Azure Blob storage outside the allowed outbound host set |
| PR #141 dual gate | Run `45643212294` conclusion failure; host dispatch jobs pass, all eight dual-run CPU/kernel jobs fail | https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/45643212294 |
| G3 governance | PR #63 merged `ad30acc7b05705bf45436d4be95aa1d6a616f8ed`; owner comment id `6455258530`, exact token `RATIFY-BOUNDED-OFFLINE-DIAGNOSTIC-INFERENCE-SCOPE`, created `2026-10-27T22:34:12Z` | https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/63#issuecomment-6455258530 |
| A3 activation | PR #64 merged `2b85bdff255266d216eb25f097b3eaa49d771e34`; independently recorded in `docs/research/CARDIOASSIST_AI_MASTER_COMPLETION_PLAN.md:300` as frozen and not authorizing later commits | GitHub PR API; `SOURCE_VERIFIED` doc line |

**No new commits were made to the current Arena branch.** The prototype branch is a separate remote branch; this review did not fetch it into a local branch or switch branches.

---

## 3. Evidence and source inventory

### 3.1 Governing documents read

| Path | What it establishes | Status caution |
|---|---|---|
| `AGENTS.md` | Research/system constraints, D-045 priority, M1c provider boundary, D-047/M3a/R1 historical sections, no real patient data, $0 budget | Multiple sections each call themselves "current"; the file contains no Term-1 stage authorization. Historical sections must not be silently interpreted as current status. (`SOURCE_VERIFIED`) |
| `docs/DECISIONS.md` | D-036/D-038/D-039/D-043, D-045, D-046/47/48, D-049 G2→G3→A3 sequence | D-049 explicitly says G3 re-baseline was PROPOSED at that PR; G3/A3 activations are separately recorded by live PR SHAs. (`SOURCE_VERIFIED`) |
| `docs/term1/CARDIOASSIST_TERM1_NEW_CHAT_HANDOFF_20261125.md` at `bca75b4` | Roles, owner decisions, journey, as-built vs target | Stale checkpoint (`c11555c…`, 3 files) at §2; historical descriptions retained. (`SOURCE_VERIFIED`) |
| `docs/term1/TERM1_INTEGRATED_PROTOTYPE_MASTER_PLAN_20261125.md` at `bca75b4` | P0/P1/deferred scope, proposed ERD/routes/state machine, one-sprint policy | Draft/unratified; the owner's new one-stage-per-master-prompt policy supersedes its §8. (`SOURCE_VERIFIED`) |
| `docs/term1/ARENA_NEW_SESSION_MASTER_PROMPT_20261125.md` at `bca75b4` | Historical full one-sprint implementation mandate | Historical planning only; NOT implementation authorization under the new policy. (`SOURCE_VERIFIED`) |
| `docs/term1/WINDOWS_LOCAL_VERIFICATION_RUNBOOK_20261125.md` at `bca75b4` | Draft PowerShell procedure | Clone target and cleanup need tightening (§11 F-08). (`SOURCE_VERIFIED`) |
| `docs/blueprint/01_MASTER_ARCHITECTURE_AND_DELIVERY_BLUEPRINT.md` | Modular monolith, identity/review/notification modules planned, auth is future work | Explicitly says no auth/RBAC in M1b.1. (`SOURCE_VERIFIED`) |
| `docs/blueprint/02_FEATURE_TRACEABILITY_MATRIX.md` | F01–F18 traceability, F11 auth/RBAC, F17 admin, F06 follow-up/notifications | Feature register entries are requirements, not implementations. (`SOURCE_VERIFIED`) |
| `docs/blueprint/04_DATABASE_AND_API_INTEGRATION_DESIGN.md` | Planned ERD, contract-change protocol, exact as-built three-table scope | §5.2 routes are PROPOSED; §7 confirms process-local idempotency/audit. (`SOURCE_VERIFIED`) |
| `docs/GRADUATION_DELIVERY_ROADMAP.md` | RH track status, APP-01/02 planning aliases, evidence discipline | APP-01/02 are not new authorizations. (`SOURCE_VERIFIED`) |
| `docs/research/next_phase/RH06_EVIDENCE_BOUNDED_RESEARCH_PROTOTYPE_DESIGN_DECISIONS_2026_11_19.md` | RD-01…RD-10, RD-09 separation, offline-only research demo | Research design record; does not approve serving. (`SOURCE_VERIFIED`) |
| `docs/research/gate-pt/18_bounded_offline_diagnostic_inference_scope.md`, `19_...runbook.md`, `docs/DECISIONS.md` D-049 | Exact offline operation, revision chain, local operator authorization | Applies only to the bounded offline scope. (`SOURCE_VERIFIED`) |
| `backend/README.md`, `ai/README.md` | Setup/verification commands; genuine offline SHAP/LIME and trust model | AI README explicitly says backend never imports `ai/`. (`SOURCE_VERIFIED`) |

### 3.2 Application and persistence source

| Path (line ranges where useful) | Verified fact |
|---|---|
| `backend/app/main.py:64-125` | `create_app` installs exactly two POST routes; `app.openapi = contracts.bundled_openapi`; startup calls read-only `verify_schema()`; docs disabled; `Cache-Control: no-store` on responses. |
| `backend/app/contracts.py`, `shared/contracts/openapi.yaml:93-232` | Versioned document; source-of-truth JSON Schemas; `x-idempotency` per operation; no `/v1/auth/*` or workflow routes. |
| `backend/app/validation.py:16-240` | CAD accepts only `benchmark_import`/`clinician_entry`; wearable fields and Track-B metric ids are rejected before inference; units/ranges come from schemas; no clinical thresholds. |
| `backend/app/state.py:1-210` | Process-local idempotency (`_idempotency`), attempts, audit snapshot, global lock; explicitly "Multiple Uvicorn workers or replicas are NOT supported". |
| `backend/app/storage/models.py:14-123` | Only `MonitoringObservation`, `MonitoringMetric`, `AuditEvent`; `AuditEvent.observation_record_id` NOT NULL FK + unique constraint. |
| `backend/app/storage/database.py:19-255` | `CARDIOASSIST_DATABASE_URL`, SQLite default, foreign keys/WAL/busy timeout, explicit transactions, strict startup schema verification. |
| `backend/migrations/versions/20261017_01_monitoring_persistence.py:21-125` | Single migration creates the three legacy tables and a complete downgrade. |
| `backend/migrations/env.py:22-71` | Alembic URL resolution and SQLite batch rendering; no automatic migration at app startup. |
| `backend/app/inference/registry.py:24-38`, `mock_synthetic.py`, `real_model.py:30-56` | One hard-wired provider; real provider construction always refuses. |
| `backend/app/artifact_admission/` | Offline, `RESEARCH_ONLY` descriptor validation; never imported by the running app; cannot grant serving. |
| `tests/backend/test_openapi_http.py:14-31`, `tests/contracts/test_openapi_document.py:61-219` | Exact sets of two paths, one operation each; no `/docs`, `/redoc`, or unapproved sketches; $refs local; error catalogue/tags/schema bindings enforced. |
| `tests/backend/test_persistence.py:38-536` | Strong migration/drift/FK/unique/replay/rollback/isolation coverage for legacy monitoring only. |
| `tests/backend/test_offline_research_boundary.py`, `test_model_artifact_admission.py` | Research IDs rejected by mock CAD; research structures cannot pass `/v1`; no genuine SHAP/LIME in backend; admission cannot grant serving. |
| `frontend/patient-mobile/README.md`, `frontend/clinician-web/README.md` | Both are placeholders only. |

### 3.3 AI research and governance source

| Path | Verified fact |
|---|---|
| `ai/diagnostic_scope.py:98-147,193-231,1286-1408` | Exact bounded operation, frozen bundle identity, nonempty A3 registry, HEAD/clean-worktree/ancestry/registry-only-diff checks, local operator attestation and confirmation phrase. |
| `ai/research_registry.py:21-46,77-103,121-142,597-681` | Closed synthetic registry; real-prefix model IDs refused; registered entries all have `approved_for_serving=False`, `real_data_execution_authorized=False`, `clinical_use_authorized=False`; two synthetic entries ACTIVE; three blocked. |
| `ai/research_facade.py:127-141,883-1018,1875-1949,2268-2321` | Four facade statuses `SYNTHETIC_RESULT`/`ABSTAIN`/`UNAVAILABLE`/`ERROR`; strict synthetic provenance; patient-entered input not admissible; score interpretation `RESEARCH_ONLY_NOT_INDIVIDUAL_CLINICAL_RISK`. |
| `ai/research_routes.py:137-151,430-470,1066-1105` | Operation allowlists, DA-A2 route permits synthetic training/prediction/explanations only; five-field cohort generator supplies all five fields. |
| `ai/panels.py:82-90,309-314`, `research/intake/synthetic_stage_validator.py:18-23,58-90` | Cleveland panel ordered `age, sex, cp, trestbps, restecg`; units years, code 0/1, codes 1..4, mmHg, codes 0..2; `trestbps` and `restecg` are optional in the staged contract and abstention is required rather than imputation. |
| `ai/packaging.py` + `ai/README.md:176-181` | Bundle trust requires containment, ACL/DACL checks, SHA-256 integrity and local HMAC producer authentication before deserialization; SHA-256 alone is not safety. |
| `ai/explainability.py`, `ai/lime_explainability.py`, `ai/lime_quality.py` | Genuine offline exact grouped SHAP and first-principles LIME with scale/fidelity/stability rules and quality verdicts; none is wired to FastAPI. |
| `research/experiments/requirements.txt` | Pinned CPU-only numpy 1.26.4, scipy 1.15.3, scikit-learn 1.6.1, joblib 1.4.2; not part of `backend/requirements.txt`. |
| `.gitignore` | Ignores `*.pkl`, `*.joblib`, model artifacts, databases, `.env`; source bundles/keys cannot simply be committed for software-team handoff. |

### 3.4 Evidence URLs used

- PR #142: https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/142
- PR #142 failing job: https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/45650285465/job/139332628376
- PR #142 passing backend run: https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/45650285373
- PR #141 failing dual gate: https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/45643212294
- Issue #132: https://github.com/Muhammed-Fathi/CardioAssist-AI/issues/132
- G3 owner comment: https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/63#issuecomment-6455258530
- Exact source at `main`: https://github.com/Muhammed-Fathi/CardioAssist-AI/tree/c6a6bdee46a552a2b0d705a723c862ff8a95be4d
- Exact planning docs at prototype HEAD: https://github.com/Muhammed-Fathi/CardioAssist-AI/tree/bca75b4646dbde26e495201938b7ae01ea7e0d21/docs/term1

---

## 4. Implemented versus proposed versus blocked feature matrix

| Capability | Status | Exact evidence | Notes |
|---|---|---|---|
| FastAPI app, two `/v1` POST routes, versioned OpenAPI/JSON Schema, fixtures | **IMPLEMENTED + HOSTED_CI_VERIFIED** | `backend/app/main.py:114-120`; `tests/backend/test_openapi_http.py:14-31`; backend run `45650285373` success | Legacy behavior must be preserved byte/behavior-compatible. |
| Deterministic `MOCK_SYNTHETIC` CAD score and SHAP-*shaped* fixture offsets | **IMPLEMENTED (mock only)** | `backend/app/inference/registry.py`, `mock_synthetic.py`, `shared/contracts/registry/mock_model_registry.v1.json` | A trained-model result must never be claimed from this path. |
| Durable Track-B monitoring persistence + one success audit per accepted write | **IMPLEMENTED + TESTED in hosted CI** | `models.py:18-123`; migration `20261017_01`; `tests/backend/test_persistence.py:337-536` | Three tables only; no patient/consent entities. |
| Read-only startup schema validation and explicit migration workflow | **IMPLEMENTED** | `database.py:136-253`; `main.py:74-81` | No startup migration or silent repair. |
| Accounts, password hashing, sessions, RBAC, object-level authorization | **NOT IMPLEMENTED / PROPOSED** | `AGENTS.md` M1b.1 section; blueprint 01 §4; no auth modules or tables | C1 scope. |
| Admin doctor provisioning, verified visits, invitations, atomic enrollment | **NOT IMPLEMENTED / PROPOSED** | Planning docs only | Requires owner acceptance of synthetic identifier semantics. |
| Health profile, assessment snapshot, persistence, status projection | **NOT IMPLEMENTED / PROPOSED** | Planning docs only | C2 scope. |
| Authorized real/trained inference over HTTP with same-model explanation | **BLOCKED / PENDING_AUTHORIZATION** | `real_model.py:30-56`; RD-09; D-049; `ai/README.md` | Decision A required. No fallback to mock. |
| Patient-facing research score before clinician review | **BLOCKED / PENDING_AUTHORIZATION** | Handoff §7; master plan §7/§11; OpenAPI track-a tag description | Decision B required. Until then patient sees status only. |
| Doctor queue, review actions, clinician-authored follow-up/prescription | **NOT IMPLEMENTED / PROPOSED** | Planning docs; blueprint 04 §5.2 | C3 scope. |
| Durable notifications/messages/read status/history | **NOT IMPLEMENTED / PROPOSED** | README/blueprint only | C3 scope. |
| Offline research: synthetic training, genuine SHAP/LIME, golden replay, registries | **IMPLEMENTED OFFLINE; CI PARTIALLY FAILING** | `ai/*`; `tests/experiments/*`; run `45650285465` | Research track boundary; not a serving capability. |
| Bounded real-bundle offline diagnostic inference | **AUTHORIZED HISTORICALLY, ACTIVATED AT A3, BUT HEAD/LOCAL-BOUND; NOT RUN BY THIS REVIEW** | D-049; `ai/diagnostic_scope.py`; PR #63/#64 | Private bundle not accessed; prototype HEAD is not A3. |
| Flutter patient app / React clinician dashboard | **PLACEHOLDER** | `frontend/*/README.md` | Software-team responsibility; no implementation claim. |
| Software-team repository | **NOT CREATED** | GitHub branch list; planning docs | Only after final review and owner approval. |
| Native Windows verification of Term-1 features | **NOT_RUN** | No owner evidence supplied | All Windows evidence in this report is `NOT_RUN`. |

---

## 5. Workflow correctness review

The intended 17-step workflow is a coherent educational journey, but several steps are specified with unsafe or ambiguous semantics. Step-by-step engineering verdict:

| # | Intended step | Verdict | Required correction |
|---|---|---|---|
| 1 | Admin provisions doctor | `PROPOSED` | Admin bootstrap must be local/operator-supplied; no committed credentials; temporary password lifecycle and first-login change need an owner decision (P1 may defer UX but not credential safety). |
| 2 | Doctor authenticates | `NOT IMPLEMENTED` | Add password hashing, sessions, expiry/revocation, RBAC (§6). |
| 3 | Doctor attests a previously occurred visit | `PROPOSED` | Attestation is the *only* visit evidence; code/ID possession is not proof of attendance. Store actor, timestamp, visit reference, and revocation state. |
| 4 | Doctor issues expiring, revocable, single-use code | `PROPOSED` | ≥128-bit CSPRNG token, one-time disclosure, stored verifier only, TTL, revoke, bounded attempts, rate limit, generic errors. |
| 5 | Code bound to doctor, verified visit, intended identifier matcher | `PROPOSED` | Use keyed HMAC-SHA256 over a server-normalized fictitious matcher; raw identifier never logged/stored; no production-format IDs in Term 1. |
| 6 | Patient registers with code + matching fictitious identifier | `PROPOSED` | Generic rejection; no account-existence enumeration; identity matcher is not government identity verification. |
| 7 | Registration + assignment + code consumption atomic | `PROPOSED` | One DB transaction with unique consumed constraint/CAS; concurrent redemption test across independent connections (§6.4). |
| 8 | Patient completes synthetic demonstration health profile | `PROPOSED` | Consent/synthetic acknowledgement and source/provenance must be explicit; no real PHI. |
| 9 | Patient initiates assessment | `PROPOSED` | Patient-initiated input must keep patient-entry provenance; do not relabel as `clinician_entry`/`benchmark_import`. |
| 10 | Backend validates schema, values, source, provenance | `PROPOSED` | Reuse schema-driven validation pattern from `validation.py`, but add a **new** synthetic-demo provenance channel; legacy CAD route remains unchanged. |
| 11 | Actual trained model runs only if that exact operation is separately authorized | `BLOCKED / PENDING_AUTHORIZATION` | Decision A. Until then create assessment + attempt with `INFERENCE_UNAVAILABLE` and no score. |
| 12 | Snapshot, model identity, result, same-model explanation durably recorded | `PROPOSED` | One immutable snapshot; separate inference attempt row; identical model/scale/background for explanation; digests and code revision. |
| 13 | Successful assessment awaits clinician review | `PROPOSED` | Only a **successful authorized** inference may set `PENDING_REVIEW`. |
| 14 | Assigned doctor reviews with reasoned decision | `PROPOSED` | Append-only review history; object-level ownership; no overwrite of inference result. |
| 15 | Doctor authors educational notes + demo prescription | `PROPOSED` | Clinician-authored only; AI never prescribes; structured text is sufficient. |
| 16 | Patient receives persistent notifications/follow-up messages | `PROPOSED` | Atomic message + notification/outbox write; idempotency; read state. |
| 17 | Authorized history survives restart | `PROPOSED` | Durable tables + migration + restart test; health of schema verified at startup. |

**Two workflow contradictions require explicit resolution before C0 is accepted:**

1. **Provisional patient score versus patient-score prohibition.** The handoff and master plan state both a requested `NOT_REVIEWED` UX with provisional score and an existing prohibition on patient-visible research scores. The owner's current instruction resolves this operationally — patient API projection must expose status only until Decision B — but the planning documents must receive an approved supersession note later, not be silently rewritten now. (Finding F-18)
2. **Doctor confirmation before every inference.** No such confirmation is part of the approved workflow and it must not be invented as though already approved. A patient-initiated assessment may create an authorized inference attempt directly, provided Decision A exists and the source/provenance contract is enforced. Doctor review happens *after* a successful result. (Finding F-14)

**Stale-result rule:** an attempt that abstains, is unavailable, errors, or fails authorization must never leave a stored research score visible to any role, and must not be labelled `PENDING_REVIEW` unless the approved state contract explicitly defines that meaning. The recommended §10 state machine keeps `PENDING_REVIEW` strictly for successful authorized inference.

---

## 6. Authentication, enrollment, identity, and security assessment

### 6.1 Accounts and credential lifecycle (`PROPOSED`; no implementation exists)

Minimum safe design for this prototype:

- `user_account` with immutable `user_id` (UUID/ULID string), role enum `admin|doctor|patient`, `status` (`ACTIVE`, `SUSPENDED`, `DISABLED`), password verifier, verifier parameters, `created_at`, `password_changed_at`, `failed_login_count`, `locked_until`.
- Password hashing: use a memory-hard KDF if a vetted package is explicitly approved and pinned; otherwise `hashlib.pbkdf2_hmac('sha256', ...)` with a per-user ≥16-byte CSPRNG salt, a documented high iteration count, constant-time comparison, and stored algorithm/version/iterations. Never SHA-256 a password; never log or echo a password or verifier.
- Temporary passwords: one-time delivery through operator-controlled channel, forced change on first login unless the owner explicitly defers only the *UX* to P1; even then the server must not accept a temporary password indefinitely.
- No self-registration for admin/doctor; patient self-registration only through a valid, unconsumed invitation.

### 6.2 Sessions (`PROPOSED`)

- Session table with opaque CSPRNG token verifier (store hash, not raw token), `user_id`, `created_at`, `expires_at`, `revoked_at`, `last_seen_at`, optional device label.
- Short TTL, explicit logout revocation, logout-all for a user, rotation on privilege change, and server-side invalidation on account disable/suspend.
- Transport is local-only for Term 1; cookie vs bearer choice must be frozen in C0. If cookies are used: `HttpOnly`, `Secure` when TLS is present, `SameSite`, CSRF defense for state-changing routes. If bearer tokens are used: browser-facing clients must use relative URLs and secure local storage appropriate to the software team's platform.
- Rate-limit login and invitation redemption per account/IP/token with bounded attempts and generic responses.

### 6.3 RBAC and object-level authorization (`PROPOSED`)

Role capabilities must be enforced server-side on every operation, not inferred from UI:

| Role | Allowed objects/actions (minimum) |
|---|---|
| `admin` | Provision/suspend doctors; no access to clinical assessment contents unless separately authorized. |
| `doctor` | Create visits only for self; issue invitations only for own verified visits; list only assigned patients; review only assessments assigned to self; author follow-up only for own patient's assessment. |
| `patient` | Read own profile/assessments/messages/notifications; initiate own assessment; no access to another patient or to model internals other than the permitted status projection. |

Every ID-based operation must verify ownership in the same query or transaction (`WHERE patient.doctor_id == current_doctor_id`, `WHERE assessment.patient_id == current_user.patient_id`). Return `404` (or `403` where the contract explicitly chooses it) consistently; never leak existence through timing or distinct messages. (Finding F-15 covers unresolved relational policy.)

### 6.4 Invitation design (`PROPOSED`; high-risk area)

**Token and verifier**

- Generate ≥128 bits (prefer 256) with `secrets.token_urlsafe(32)` or equivalent CSPRNG.
- Display the plaintext exactly once at creation; store only a keyed verifier or SHA-256 of the token plus a separate pepper managed by the operator. A stored verifier must never be returned by any read endpoint.
- Short TTL (C0 must freeze a value, e.g. hours not days), `revoked_at`, `consumed_at`, `attempt_count`, `max_attempts`, `issued_by_user_id`, `verified_visit_id`, `identifier_hmac`, `identifier_alg_version`.
- Bounded attempts and rate limits; all failure modes (`unknown`, `expired`, `revoked`, `consumed`, `identifier_mismatch`, `inactive_issuer`) produce the same generic client error and distinct internal audit codes only.

**Identifier matching**

- Term 1 uses deliberately fictitious values such as `DEMO-ID-001`. Reject 14-digit production-format identifiers in demo mode so real IDs cannot be accidentally entered.
- Server-normalizes the fictitious matcher (trim/case policy frozen in C0), computes `HMAC-SHA256(secret, normalized || version || purpose)`, stores only the digest. Purpose separation (`invitation-match/v1`) and versioning prevent cross-context reuse. Secret comes from operator environment, is never committed, and supports rotation by storing `key_id`.
- No raw identifier in routes, request logs, exception strings, audit payloads, snapshots, fixtures, notifications, or URLs. HMAC digest is also never exposed to clients.
- Code possession + identifier match is **not** independent proof of physical attendance or government identity. The verified-visit attestation is the prerequisite; the UI and docs must state this.

**Atomic redemption and concurrency**

- In one `Database.transaction()`: load invitation `FOR UPDATE` where SQLite semantics permit (SQLite has no row-level `SELECT ... FOR UPDATE`; use a conditional `UPDATE ... WHERE consumed_at IS NULL AND revoked_at IS NULL AND expires_at > now` and check `rowcount`, plus unique constraints), verify token verifier in constant time and HMAC matcher, create patient account/profile/assignment/consent, mark `consumed_at`, and write a workflow audit event.
- `UNIQUE(invitation_id)` on the redemption/consumption record and `UNIQUE(patient_identifier_hmac, key_id)` (if duplicate identifiers are disallowed) make double redemption impossible at the storage layer even if two connections race.
- On any failure, rollback all patient/assignment/consumption effects. Failure-attempt audit records must be written in a **separate** transaction after rollback (§7.4).
- Test with two independent SQLAlchemy connections/processes attempting the same code simultaneously: exactly one success, exactly one generic failure, one consumed record, no orphan patient.

**Unresolved policies that C0 must decide (Finding F-15):**

| Question | Recommended minimum safe policy |
|---|---|
| Repeat visits | New `verified_visit` row each time; existing patient may receive a new invitation only with a new attestation and explicit re-consent/assignment policy. |
| Existing patient account | Do not create a duplicate account; require authenticated binding to an existing account under a separately approved flow, or reject with generic error in Term 1. |
| Second invitation to same patient | Allowed only if the first is expired/revoked/consumed and the policy permits; old invitations remain readable in audit, not reusable. |
| Multiple doctors per patient | Term 1 uses exactly one active treating doctor per assignment; additional doctors require an explicit owner decision and a new assignment row with status/consent. |
| Duplicate fictitious identifier | Reject second registration unless owner approves a deterministic reuse policy; log only an internal audit code. |
| Assignment revocation/consent | Store `assigned_at`, `revoked_at`, `revoked_by`, `reason`, and patient acknowledgement timestamp; revocation must immediately remove doctor's object-level access. |
| Account-existence enumeration | Generic errors for login, registration, invitation, and password reset (reset is deferred); no differential responses. |
| Cross-doctor/cross-patient access | Object-level checks plus negative tests for IDOR; `404` consistently. |
| Transaction rollback | Mandatory rollback test with injected failure after patient creation but before consumption. |

---

## 7. Proposed ERD, database constraints, and migration strategy

### 7.1 Proposed minimum entity set (`PROPOSED`; none exists yet)

```
user_account (PK user_id, role, status, password_verifier, verifier_params,
              created_at, password_changed_at, failed_login_count, locked_until)
  1─0..1 doctor_profile (PK doctor_id, FK user_id UNIQUE, display_name, active)
  1─0..1 patient_profile (PK patient_id, FK user_id UNIQUE, fictitious_label,
                          identifier_hmac, identifier_key_id, created_at)
  1─*   session (PK session_id, FK user_id, token_verifier UNIQUE, expires_at,
                 revoked_at, created_at)

doctor_profile 1─* verified_visit (PK visit_id, FK doctor_id, attested_at,
                  visit_ref, status, note_metadata_only)
verified_visit 1─* patient_invitation (PK invitation_id, FK visit_id,
                  FK issued_by_user_id, token_verifier UNIQUE,
                  identifier_hmac, identifier_alg_version, key_id,
                  issued_at, expires_at, consumed_at, revoked_at,
                  attempt_count, max_attempts)
patient_invitation 1─0..1 invitation_redemption (PK redemption_id,
                  FK invitation_id UNIQUE, FK patient_id, consumed_at)

doctor_profile *─* doctor_patient_assignment (PK assignment_id,
                  FK doctor_id, FK patient_id, assigned_at, revoked_at,
                  revoked_by, reason; UNIQUE active pair via partial index
                  or application-enforced status with unique constraint)
patient_profile 1─* consent_record (PK consent_id, FK patient_id, kind,
                  acknowledged_at, revoked_at, contract_version)
patient_profile 1─0..1 health_profile (PK profile_id, FK patient_id UNIQUE,
                  schema_version, payload_json, provenance_json, updated_at)

patient_profile 1─* assessment (PK assessment_id, FK patient_id,
                  FK assignment_id, schema_version, source_contract_version,
                  status, created_at, reassessment_of NULL, reason)
assessment 1─1 assessment_snapshot (PK snapshot_id, FK assessment_id UNIQUE,
                  payload_sha256, canonical_json, provenance_json,
                  panel_id, panel_version, immutable)
assessment 1─* inference_attempt (PK attempt_id, FK assessment_id,
                  idempotency_key UNIQUE, state, requested_at, finished_at,
                  model_id, model_version, artifact_sha256, panel_sha256,
                  code_revision, source_binding, score_json NULL,
                  explanation_json NULL, error_code NULL, attempt_digest)
inference_attempt 1─0..1 inference_result (PK result_id,
                  FK attempt_id UNIQUE, score_kind, score_value_json,
                  explanation_json, explanation_method, background_id,
                  digest, recorded_at)
assessment 1─* assessment_review (PK review_id, FK assessment_id,
                  FK reviewer_doctor_id, decision, reason_code, rationale,
                  recorded_at; append-only)
assessment 1─* follow_up_message (PK message_id, FK assessment_id,
                  FK author_doctor_id, body, prescription_json, created_at,
                  idempotency_key UNIQUE)
follow_up_message 1─* notification_record (PK notification_id,
                  FK recipient_user_id, FK message_id NULL, type,
                  created_at, read_at, idempotency_key UNIQUE)

durable_idempotency (PK scope + idempotency_key, request_sha256,
                  response_json, status, created_at, expires_at)
workflow_audit_event (PK audit_id, event_type, actor_user_id NULL,
                  subject_type, subject_id, request_id, payload_sha256,
                  code, recorded_at, outcome)
```

**Legacy tables preserved unchanged:** `monitoring_observation`, `monitoring_metric`, `audit_event` and migration `20261017_01` remain as-is. `audit_event` continues to require a real monitoring observation; no fake monitoring row may be created to satisfy a workflow audit write. (`SOURCE_VERIFIED` from `models.py:90-123` and migration lines 83-105.)

### 7.2 Cardinality, ownership, and indexes

- One active user → at most one doctor or patient profile; role changes require explicit migration/administrative action, not implicit row creation.
- One verified visit → many invitations over time; one invitation → at most one successful redemption.
- One patient → one active doctor assignment in Term 1; historical assignments retained with `revoked_at`.
- One assessment → one immutable snapshot, many inference attempts (for retry/recovery), at most one successful result per successful attempt, many append-only review actions and follow-ups.
- One message → one notification per intended recipient; read state is mutable, message body is not.
- Indexes: `(user_id, status)` on sessions; `(doctor_id, expires_at)` on invitations; `(patient_id, created_at)` on assessments; `(assessment_id, state)` on attempts; `(actor_user_id, recorded_at)` and `(subject_type, subject_id, recorded_at)` on workflow audit; `(scope, idempotency_key)` unique on durable idempotency.
- All timestamps UTC strings in an agreed RFC 3339 form; all monetary/clinical values explicitly typed; JSON payloads are canonicalized before hashing.

### 7.3 Why a dedicated workflow audit table is required

`audit_event` has `observation_record_id NOT NULL` with `ForeignKey("monitoring_observation.record_id", ondelete="RESTRICT")` and `UNIQUE(observation_record_id)` (one audit per accepted monitoring write). Reusing it for login, enrollment, assessment, review, or follow-up would either require fake monitoring observations or violate the schema. A new `workflow_audit_event` with nullable subject references and safe metadata only is the smallest compatible alternative. Keep the legacy repository API untouched. (Finding F-02)

### 7.4 Transaction boundaries and failure audits

| Operation | Transaction contents | Failure behavior |
|---|---|---|
| Invitation issue | Insert visit audit + invitation row; token disclosed only after commit | Generic error; no token disclosed on failure |
| Registration/redemption | Conditional consume; create account/profile/assignment/consent; durable idempotency; success audit | Rollback all; then separate failure audit with redacted code only |
| Assessment create | Insert assessment + immutable snapshot + idempotency | Rollback; failure audit separately |
| Inference attempt start | Insert attempt row `INFERENCE_RUNNING` with unique idempotency key | No long write transaction during model execution |
| Inference completion | Short transaction: update attempt, insert result, clear stale scores, emit doctor notification | On crash before commit, recovery marks stale attempt failed; no result |
| Review | Insert append-only review row + update current review state + audit; idempotent key | Rollback; failure audit separately |
| Follow-up | Insert message + notification + audit + idempotency in one commit | Rollback; no partial message |
| Read status | Small update with optimistic version/`read_at`; idempotent | 409 on conflicting version if used |

### 7.5 Migration and startup strategy

- Add one Alembic revision (or a small ordered set) whose `down_revision` is `20261017_01`; every new SQLAlchemy model must exist in `Base.metadata` so `verify_schema()` can detect drift. `alembic check` must pass after upgrade.
- Upgrade path: explicit `python -m alembic upgrade head`; verify `current` equals expected head; then start application, which re-verifies schema. Never auto-upgrade at startup, never stamp an uncertain DB, never silently repair.
- Downgrade: implement and test only on disposable test databases; prove downgrade→upgrade preserves legacy monitoring rows where required and that workflow rows are removed intentionally. Do not run downgrade against an owner database.
- SQLite: WAL + `busy_timeout=10000` + `foreign_keys=ON` are already configured (`database.py:28-60`); SQLite still has a single writer. Enrollment concurrency must rely on atomic conditional updates/unique constraints and retry/409, not application locks alone.
- PostgreSQL compatibility is **NOT** verified; do not claim parity. New migrations should use portable SQLAlchemy operations (`batch_alter_table` where SQLite needs it) and be reviewed separately if PostgreSQL is ever introduced.
- No destructive schema resets, no startup `create_all`, no dataset or DB files in Git. (Finding F-17)

---

## 8. Proposed API contracts and integration matrix

### 8.1 Contract-change protocol (must be reviewed before implementation)

1. Keep `shared/contracts/openapi.yaml` and the two legacy JSON Schemas/fixtures behavior-compatible. Add new schemas in a clearly versioned Term-1 contract document (e.g. `shared/contracts/term1/openapi.term1.v1.yaml`) referenced from a reviewed additive change; do not silently mutate the approved v1 document.
2. Extend exact-operation tests deliberately: keep the historical assertion that the *legacy* document contains exactly the two approved operations; add a separate assertion for the new document's allowlisted operations. If the served `/openapi.json` must include both, update `test_bundled_openapi_is_valid_and_has_exactly_the_approved_operations` and `test_openapi_declares_exactly_the_two_m1a1_paths` in a reviewed change that explicitly names the new paths; never delete the historical check and replace it with a weaker subset assertion. (Finding F-04)
3. Add F-xx fixture IDs for each new operation; update `shared/contracts/fixtures/index.json`; add request/response schema tests, error-catalogue tests, idempotency tests, and object-level authorization tests.
4. Do not create a differently named unapproved prediction endpoint. A new assessment route must not call the mock provider and present it as trained inference. Decision A must define a distinct adapter and operation identifier if inference is ever enabled.
5. Breaking wire changes require `/v2` and a new decision; additive routes use `/v1` with explicit tags and `x-term1-*` metadata.

### 8.2 Proposed operations (`PROPOSED` — not implemented, not authorized by listing)

For brevity: every operation below requires authentication except `/v1/auth/login` and registration; every request body is `application/json` with strict duplicate-key/non-finite-number rejection; error envelope follows the existing `contracts.error_body` shape; all object-level checks are server enforced.

| # | Method/path | Actor & access | Request → response (core fields) | Validation/errors | Idempotency & DB effect | Client screen |
|---|---|---|---|---|---|---|
| A1 | `POST /v1/auth/login` | Anonymous | `{email, password}` → `{session_token (once), expires_at, role, profile_id}` | `400 malformed_request`, `401 invalid_credentials` (generic), `423 account_locked` | New `session`; no state change on failure | All login screens |
| A2 | `POST /v1/auth/logout` | Any authenticated | `{}` → `{revoked:true}` | `401 unauthenticated` | Revoke current session; repeat returns success or defined 404 | All apps |
| A3 | `GET /v1/auth/me` | Any authenticated | → `{user_id, role, status, profile_id, display_name}` | `401` | Read only | Profile header |
| A4 | `POST /v1/admin/doctors` | Admin only | `{email, display_name, temporary_password_policy}` → `{doctor_id, temporary_secret once}` | `403`, `409 duplicate_email` (generic to non-admin), `422` | Create user+doctor+audit | Admin provisioning |
| A5 | `POST /v1/doctor/verified-visits` | Doctor, own actor | `{visit_ref, attestation_text, attested_at}` → `{visit_id, attested_at}` | `403`, `422`, `409 duplicate_visit_ref` | Insert visit+workflow audit | Doctor visit attestation |
| A6 | `POST /v1/doctor/verified-visits/{id}/invitations` | Doctor, owns visit | `{identifier (fictitious, request body only), ttl_seconds}` → `{access_code once, expires_at, invitation_id}` | `404/403` for non-owned visit; `409 visit_already_active_invite` if policy restricts | Insert invitation+audit; verifier stored only | Doctor invitation issue |
| A7 | `POST /v1/patients/register` | Anonymous, valid invitation | `{access_code, identifier, email, password, consent_ack}` → `{user_id, patient_id, assignment_id, session_token once}` | Generic `401 invalid_invitation` for all mismatch classes; `409` only for defined idempotent replay | Atomic redemption + assignment + consent + audit + durable idempotency | Patient signup |
| A8 | `GET/PATCH /v1/me/health-profile` | Patient, own | `GET` → profile+schema version; `PATCH {schema_version, fields, provenance}` → profile projection | `422 invalid_field/source`, `409 version_conflict` | Upsert profile; no inference | Patient health profile |
| A9 | `POST /v1/assessments` | Patient, own; consent present | `{profile_id, panel_id, panel_version, inputs, source_contract, Idempotency-Key}` → `{assessment_id, status, snapshot_digest, attempt_id}` | `422` schema/value/provenance; `503 inference_unavailable` only if no attempt can be created; no score in error | Assessment+snapshot+attempt (`RUNNING`→terminal) + idempotency | Patient assessment start |
| A10 | `GET /v1/assessments/{id}` | Patient owner or assigned doctor | → role-redacted assessment: patient gets status only until Decision B; doctor gets snapshot/model/result/explanation | `404` wrong owner; `403` revoked assignment | Read | Patient status / doctor detail |
| A11 | `GET /v1/me/assessments` | Patient, own | Paginated `{id,status,created_at}`; no score projection pre-Decision B | `400 bad_cursor` | Read | Patient history |
| A12 | `GET /v1/doctor/patients` | Doctor, own assignments | Paginated patients with assignment status | `403` non-doctor | Read | Doctor patient list |
| A13 | `GET /v1/doctor/assessments` | Doctor, own assignments | Review queue filtered by state; no unassigned records | `400 bad_cursor`, `403` | Read | Doctor review queue |
| A14 | `POST /v1/assessments/{id}/reviews` | Assigned doctor only | `{decision, reason_code, rationale, Idempotency-Key}` → `{review_id, effective_state}` | `409 illegal_transition/duplicate_review`, `404` wrong owner | Append-only review + state + notification + audit | Doctor review |
| A15 | `POST /v1/assessments/{id}/follow-up` | Assigned doctor only | `{note, demo_prescription, Idempotency-Key}` → `{message_id, notification_id}` | `409 duplicate_follow_up`, `422` | Atomic message+notification+audit | Doctor follow-up authoring |
| A16 | `GET /v1/me/messages` | Patient, own | Paginated messages with read state | `400 bad_cursor` | Read | Patient inbox |
| A17 | `GET /v1/me/notifications` + `POST /v1/me/notifications/{id}/read` | Patient, own | Notification list; read-mark returns `{read_at}` | `404` wrong owner, `409 version_conflict` | Notification read update + audit | Patient notifications |

**Role-specific redaction:** patient projection of A9/A10/A11/A16/A17 must contain `status`, safe timestamps, and clinician-authored content only. It must not contain research score, calibrated probability, log-odds, SHAP/LIME values, artifact digests, or internal error diagnostics until Decision B is ratified and tests enforce the wording/model label. Doctor projection includes those fields with explicit `RESEARCH_ONLY_NOT_INDIVIDUAL_CLINICAL_RISK` labelling.

### 8.3 API integration matrix (software-team handoff view)

| Endpoint | Method | Actor | Authentication | Schema | Errors | DB effects | Demo example (fictitious) | Related client screen | Test status | Integration readiness |
|---|---|---|---|---|---|---|---|---|---|---|
| `/v1/auth/login` | POST | any | public | `AuthLoginRequest/Response` | 400/401/423 | session row | admin/doctor/patient local demo login | All | `NOT_RUN` | `PROPOSED` |
| `/v1/auth/logout` | POST | any | session | empty/response | 401 | revoke session | end demo session | All | `NOT_RUN` | `PROPOSED` |
| `/v1/auth/me` | GET | any | session | `MeResponse` | 401 | none | inspect role | All | `NOT_RUN` | `PROPOSED` |
| `/v1/admin/doctors` | POST | admin | session+RBAC | `DoctorProvision` | 403/409/422 | user+doctor+audit | provision `demo.doctor` | Admin | `NOT_RUN` | `PROPOSED` |
| `/v1/doctor/verified-visits` | POST | doctor | session+RBAC | `VerifiedVisit` | 403/409/422 | visit+audit | attested `DEMO-VISIT-001` | Doctor | `NOT_RUN` | `PROPOSED` |
| `/v1/doctor/verified-visits/{id}/invitations` | POST | doctor | session+ownership | `InvitationIssue` | 404/409/422 | invitation+audit | code shown once | Doctor | `NOT_RUN` | `PROPOSED` |
| `/v1/patients/register` | POST | anonymous→patient | invitation | `PatientRegister` | generic 401/409 | atomic enrollment | `DEMO-ID-001` | Patient | `NOT_RUN` | `PROPOSED` |
| `/v1/me/health-profile` | GET/PATCH | patient | session+ownership | `HealthProfile` | 403/409/422 | profile | synthetic five fields | Patient | `NOT_RUN` | `PROPOSED` |
| `/v1/assessments` | POST | patient | session+consent | `AssessmentCreate` | 422/409/503 | snapshot+attempt+idempotency | patient-initiated demo input | Patient | `NOT_RUN` | `PROPOSED` |
| `/v1/assessments/{id}` | GET | patient/doctor | session+ownership | role-redacted | 403/404 | none | status vs clinician detail | Both | `NOT_RUN` | `PROPOSED` |
| `/v1/me/assessments` | GET | patient | session+ownership | paginated | 400 | none | own history | Patient | `NOT_RUN` | `PROPOSED` |
| `/v1/doctor/patients` | GET | doctor | session+ownership | paginated | 403/400 | none | assigned demo patient | Doctor | `NOT_RUN` | `PROPOSED` |
| `/v1/doctor/assessments` | GET | doctor | session+ownership | paginated queue | 403/400 | none | pending review | Doctor | `NOT_RUN` | `PROPOSED` |
| `/v1/assessments/{id}/reviews` | POST | doctor | session+ownership | `ReviewAction` | 403/404/409 | append review+state+audit+notification | ACCEPTED with rationale | Doctor | `NOT_RUN` | `PROPOSED` |
| `/v1/assessments/{id}/follow-up` | POST | doctor | session+ownership | `FollowUp` | 403/404/409 | message+notification+audit | educational note/demo prescription | Doctor | `NOT_RUN` | `PROPOSED` |
| `/v1/me/messages` | GET | patient | session+ownership | paginated | 400 | none | read clinician note | Patient | `NOT_RUN` | `PROPOSED` |
| `/v1/me/notifications` | GET | patient | session+ownership | paginated | 400 | none | unread/read items | Patient | `NOT_RUN` | `PROPOSED` |
| `/v1/me/notifications/{id}/read` | POST | patient | session+ownership | `ReadAck` | 404/409 | read_at+audit | mark read | Patient | `NOT_RUN` | `PROPOSED` |
| `/v1/predictions/cad-tabular` | POST | existing legacy | unchanged | existing v1 schema | existing catalogue | no new persistence | legacy mock fixture | Regression only | `HOSTED_CI_VERIFIED` | IMPLEMENTED, protected |
| `/v1/monitoring/observations` | POST | existing legacy | unchanged | existing v1 schema | existing catalogue | 3 legacy tables | Track-B fixture | Regression only | `HOSTED_CI_VERIFIED` | IMPLEMENTED, protected |

**Positive/negative acceptance tests required per proposed operation:** (a) happy path with the correct role and object; (b) unauthenticated; (c) wrong role; (d) cross-user/cross-doctor object; (e) malformed JSON/duplicate keys; (f) schema/value/provenance failure; (g) idempotent replay with same key; (h) key/payload conflict; (i) restart persistence where applicable; (j) role-specific redaction. Detailed stage-level tests are in §13.

---

## 9. `AI_READINESS_MATRIX` and scientific authorization boundaries

### 9.1 Matrix Part A — identity, provenance, and input contract

| Candidate / route | Route and model identity/version | Dataset and training provenance | Ordered feature schema and units | Optional-field and abstention rules |
|---|---|---|---|---|
| **M1 — legacy HTTP mock** `POST /v1/predictions/cad-tabular` | `mock_model_a_v0.1.0` etc.; `feature_schema_id=mock_clinical_v1/v2`; `validation_status=development_internal_only` | No dataset; no training; `artifact_sha256=e3b0c442…b855` = empty-string placeholder | Mock feature schemas with placeholder `u_*` units; not a clinical dictionary | Explicit optional nulls skipped, no imputation; required missing → `422 missing_required_feature` |
| **R1 — offline synthetic DA-A2** `da_a2_resting_v1` | `synth_ai7_da_a2_resting_v1`, model `0.1.0`, route `1.0.0`, panel `1.0.0`; profile `EXECUTION_PROFILE_AI1_GENERIC_V1` | Deterministic generated cohort via `ai.research_routes.build_synthetic_uci45_resting_cohort`; no real records | `age` (years), `sex` (0/1), `cp` (1..4), `trestbps` (mmHg), `restecg` (0..2), in that order | `trestbps`/`restecg` optional in staged panel; registered entry `abstain_on_missing_optional=True`; no silent imputation |
| **R2 — offline synthetic UCI-412** `da_a1_basic_clinical_v1` | `synth_ai8_uci412_da_a1_basic_clinical`, `0.1.0`; route `1.1.0`; panel `1.1.0` | Deterministic synthetic UCI-412-style cohort; real DA-A1 execution subject to M3a/D-048 and Gate PT | 16 ordered `uci412_basic_clinical_v1` fields; see `ai/panels.py`; target `>=50%` boundary | All 16 required; no optional abstention; blocked routes return `UNAVAILABLE` |
| **R3 — real Cleveland D-047 bounded offline diagnostic** | `cai_real_da-a2_da_a2_resting_v1`, version `0.2.0`, protocol `CAI-D047-CLEVELAND-EXPLORATORY-V1` | Accepted real Cleveland D-047 bundle; historical internal exploratory; no new fitting/calibration | DA-A2 five-field panel as R1 | Max 8 synthetic records per invocation; optional missing rules as R1; fabricated synthetic inputs only |
| **P1 — proposed synthetic-trained educational HTTP adapter (candidate B)** | **NOT DEFINED**; must get a new versioned model ID, route ID, panel ID, operation ID | Must be trained only on deliberately generated synthetic data; no private bundle; no source pooling; no real records | Same ordered five fields/units as R1 if that panel is reused; no invented fields | Must abstain for unavailable optional fields; no default/zero imputation; patient entry labelled with new synthetic-demo provenance |

### 9.2 Matrix Part B — artifact trust, runtime, authorization

| Candidate | Artifact identity/digest | Source/protocol binding | Trust and redistribution requirements | Allowed operation | Runtime admissibility | Serving authorization status |
|---|---|---|---|---|---|---|
| M1 | Empty-string SHA-256; no artifact | `shared/contracts/registry/mock_model_registry.v1.json`; D-043/M1a contracts | No artifact to trust; mock fixture offsets only | Deterministic mock CAD contract response | Only provider constructible by `build_active_provider` | **AUTHORIZED for mock only**; cannot be relabelled trained |
| R1 | Registry pins panel `contract_sha256` and versioned artifact declaration; bundle verification required before deserialization | `CAI-AI7-SYNTHETIC-DA_A2_RESTING_V1-V1`; route permits synthetic training/prediction/SHAP/LIME | Local synthetic bundle + trusted root/ACL + HMAC producer attestation; no real SHAP background | `synthetic_prediction`, `shap_attribution`, `lime_assessment`, `synthetic_end_to_end_exercise` (offline) | Offline `ai/` only; backend never imports `ai/`; no HTTP path | `approved_for_serving=False`; `OP_CLINICAL_SERVING` not in route allowlist |
| R2 | Same registry pattern; panel `1.1.0` | M3a/D-048 and source-specific target `>=50%` | Same trust rules; no UCI-412/Cleveland translation | Offline synthetic prediction only | Offline only | Blocked for serving; real route not authorized |
| R3 | Bundle dir `cai_real_cleveland_d047_20261027T070610Z_deffa577`; manifest SHA-256 `089f931b…d4a`; source SHA-256 `a74b7efa…27c8` recorded in `ai/diagnostic_scope.py:215-231` | G3 `ad30acc…`, I3 `87bccd6…`, A3 `2b85bd…`; exact governance document digest; registry-only activation diff | Private local artifact/key; trusted Windows operator; no upload, no cloud Arena execution | **Only** `offline_synthetic_input_diagnostic_inference`, ≤8 synthetic records | Requires HEAD==A3, clean tracked worktree, ancestry checks, local ignored attestation, exact confirmation phrase. Prototype HEAD `bca75b4…` is not eligible | **BLOCKED for HTTP/patient use**; offline activation does not extend |
| P1 | Must be generated, pinned, and independently verified; deterministic rebuild preferred for CI | New protocol/registry entry + owner Decision A; panel/feature digest frozen | `.gitignore` excludes model artifacts; distribution requires curated artifact with rights or deterministic rebuild; no private key in hosted CI | Only the exact new educational local-demo inference operation named in Decision A | New adapter remains disabled/unavailable until Decision A; no env/header bypass | `PENDING_AUTHORIZATION` — Decision A |

### 9.3 Matrix Part C — score meaning, explanations, evidence, CI, blockers

| Candidate | Score interpretation and scale | Explanation method/background | Same-model fidelity/stability evidence | Reproducible synthetic test oracle | CI status | Blocking decisions |
|---|---|---|---|---|---|---|
| M1 | `uncalibrated_score` or mock calibrated shape; synthetic intercept; **no clinical meaning** | SHAP-*shaped* fixture offsets; not genuine SHAP/LIME | Mock determinism only; backend test asserts no genuine implementation | Fixtures F-01…F-12 and reference contract | Backend/contract runs success at exact prototype HEAD | None for mock use; cannot be promoted to trained result |
| R1 | `CALIBRATED_RESEARCH_SCORE_SYNTHETIC` or raw probability; interpretation `RESEARCH_ONLY_NOT_INDIVIDUAL_CLINICAL_RISK`; cross-sectional CAD presence, not future risk | Exact grouped interventional SHAP on declared scale; optional LIME on same declared scale with decoded synthetic background | Offline $2^M$ coalition verification, scale comparison, LIME quality verdicts/stability seeds in `ai/explainability.py`, `ai/lime_explainability.py`, `ai/lime_quality.py` | 29-case golden replay fixture pack; strict comparator | Synthetic runner 3.12 success; 3.11 failure is inherited cross-route numeric drift (Issue #132) | Decision A for HTTP; Decision B for patient display; no Golden changes |
| R2 | Separate source-specific research score; `>=50%` target; never mixed with Cleveland | Same genuine framework on UCI-412 background | Offline tests; route separation enforced | UCI-412 29-case pack / synthetic benchmark | 3.12 success at prototype run; inherited issue applies to UCI-412 calibrated log-odds path specifically | No serving authorization; no source pooling |
| R3 | Internal exploratory research classification on synthetic inputs; never patient risk | Exact SHAP tied to frozen bundle/background | Offline feasibility tests on historical activation commits; no patient output; this review ran none | Committed A2 feasibility tests; private bundle not touched | Not exercised by this preflight; research gates remain separate | Human local operator authorization; HEAD==A3; no prototype use |
| P1 | Must state research-only synthetic score, its scale (calibrated log-odds vs raw probability), and explicit non-clinical label | Must use the **same** model and declared background/scale; no synthetic-looking explanation from a different provider | Must produce digest-stable repeated runs and explanation stability evidence; fail closed if unavailable | New synthetic oracle with frozen seed/panel/digest; negative tamper/refusal tests | `NOT_RUN`; no adapter exists | Owner Decision A, contract review, artifact trust/distribution decision; Decision B separately |

### 9.4 Scientific authorization boundaries (binding)

- **Decision A** (not granted): authorization for an exact educational local-demo inference adapter and its permitted synthetic input sources. Until it exists, new application-path inference remains disabled/unavailable; the assessment may be created and attempt recorded as `INFERENCE_UNAVAILABLE`, with no mock fallback.
- **Decision B** (not granted): authorization to display a research-model score to the synthetic patient. Until it exists, patient projections expose status only, without score or explanation.
- Owner's PR #63 comment ratifies only `offline_synthetic_input_diagnostic_inference` for the exact frozen real Cleveland bundle, bounded by frozen identity, local operator authorization, artifact trust, revision binding, and runtime requirements. It is **not** permission for HTTP model serving, real-data fitting/retraining, patient scores, private artifacts in Arena, or clinical deployment.
- RD-09 separation must remain: offline `ai/` research, offline intake/reporting, and one `MOCK_SYNTHETIC` backend provider. Do not bypass with environment flags, headers, or differently named prediction endpoints.
- Track B wearable/monitoring inputs must never enter CAD inference; unverified OCR/labs must never become clinical features. Existing `reject_wearable()` and offline provenance guards must be preserved and mirrored in the new pipeline.
- AI must never author prescriptions or medical recommendations. No high/medium/low risk bands, no 30-day horizon, no actionable diagnosis claim.
- A nonempty activation registry at `main` is a fact about A3, not about prototype HEAD. The private Cleveland bundle was not accessed or executed by this review.

### 9.5 Proposed server-enforced synthetic-demo provenance contract (for separate approval)

The existing facade requires `synthetic_provenance` with `declaration=DELIBERATELY_FABRICATED_SYNTHETIC_FIXTURE`, a registered generator identifier, an integer seed, and a fixture reference, plus `input_source=structured_synthetic_research` and `acquisition_stage`; a bare `synthetic: true` is rejected (`ai/research_facade.py:883-1018,1875-1899`). A patient-entered assessment cannot truthfully claim to have been produced by that generator. Proposed new contract:

```
input_source = "synthetic_demo_patient_entry"          // NEW value, not an alias
source_contract = "term1.synthetic_demo_intake/v1"     // NEW versioned contract
declaration = "SYNTHETIC_DEMO_SELF_REPORTED_FABRICATED_VALUES"
subject_kind = "DEMO_PATIENT_PROFILE"
record_ref = "<assessment_id>:<snapshot_digest>"
server_asserted = {
  demo_mode: true,
  synthetic_acknowledgement_id: <consent_record id>,
  submission_actor_user_id: <session user id>,
  server_time_utc: <timestamp>,
  panel_id/panel_version, schema_sha256
}
forbidden = ["clinician_entry", "benchmark_import", "structured_synthetic_research",
             "wearable", "ocr", "lab_import", "government_verified"]
```

Server rules to enforce: the value is assigned by the server from the authenticated patient session and the accepted synthetic-demo acknowledgement, never accepted from a client field; any client attempt to set a protected source is `422 provenance_not_admissible`; the new value is not accepted by the legacy CAD route; the adapter's registry entry must explicitly allow this source in Decision A; explanation and score carry the same provenance label. No real patient input may be transformed into this contract. (Finding F-05)

---

## 10. Assessment state machine and failure recovery

### 10.1 Recommended states

```
assessment.status:
  DRAFT (profile incomplete)
    -> INPUT_VALIDATED (immutable snapshot committed)
    -> INFERENCE_RUNNING (durable attempt id created)
       -> INFERENCE_SUCCEEDED  -> PENDING_REVIEW (only here)
       -> INFERENCE_ABSTAINED
       -> INFERENCE_UNAVAILABLE   (includes not authorized / adapter disabled)
       -> INFERENCE_ERROR

review.effective_state (append-only actions; no overwrite):
  NOT_REVIEWED -> ACCEPTED | REJECTED | REASSESSMENT_REQUESTED
  illegal transitions -> 409 review_transition_conflict
```

`PENDING_REVIEW` is reserved for a **successful authorized** inference with a durable result row. Failure/abstention/unavailability/error states are terminal for that attempt; they clear any stale score/explanation and expose status-only to the patient. A new assessment row (never mutation of the old one) is created for a permitted reassessment with a recorded reason.

### 10.2 Attempt lifecycle and invariants

1. `POST /v1/assessments` validates schema, units, panel, source, provenance, consent, and object ownership; writes assessment + immutable snapshot + durable idempotency in one short transaction. A retry with the same key/payload returns the same assessment (with `idempotent_replay` flag); a conflicting key returns `409`.
2. A durable `inference_attempt` row is created with a unique idempotency key and state `INFERENCE_RUNNING` before expensive computation. No long database write transaction is held during model execution.
3. The adapter checks Decision A authorization, artifact trust, panel digest, and source binding before loading/executing. If unavailable, the attempt transitions to `INFERENCE_UNAVAILABLE` with a redacted error code. No mock fallback.
4. On success, one short transaction writes `inference_result`, updates attempt/assessment state, clears stale outputs, and emits a doctor notification. Score and explanation must come from the same model identity and scale.
5. On crash while `INFERENCE_RUNNING`, a recovery job/startup task (explicit, not silent schema repair) marks attempts older than a configured lease as `INFERENCE_ERROR` or retries idempotently with the same durable key; it never fabricates a result. Concurrent attempts for one assessment are prevented by a unique partial constraint/conditional update on active attempts.
6. Result/snapshot consistency: result row references both `attempt_id` and the immutable `snapshot_digest`; any mismatch fails closed and is audited.
7. Review is append-only; the current effective state is derived from the latest accepted review action or maintained in one authoritative column updated in the same transaction as the append. Do not keep two independent sources of truth.
8. Follow-up and notification are written in a single transaction with idempotency; patient read status is a separate, small update.
9. Role-specific projection is enforced at the response layer: patient sees status (and clinician-authored content after review), doctor sees evidence with research-only labels, admin sees no clinical payload by default.
10. Durable audit events record success metadata in the same transaction; failure attempts record redacted metadata in a separate transaction after rollback. (Finding F-20)

---

## 11. Engineering contradictions, findings, and risks

Severity: **CRITICAL** blocks stage acceptance or safety; **HIGH** must be resolved before the affected stage is accepted; **MEDIUM** must be tracked with a named owner; **LOW** is a hygiene item.

### F-01 — Draft PR is documentation-only; historical handoff checkpoint is stale
- **Severity:** CRITICAL. **Evidence category:** `SOURCE_VERIFIED`, `HOSTED_CI_VERIFIED`.
- **Exact evidence:** PR #142 has 4 docs-only files (+546/-0), head `bca75b4…`, commits listed in §2; handoff §2 records `c11555c…` and three files; compare `ahead_by=4, behind_by=0`.
- **Impact:** no application functionality exists to accept; relying on the stale snapshot could cause wrong SHA verification or false claims.
- **Correction:** treat PR #142 as a planning branch only; keep the historical handoff intact and add an approved dated supersession note in future C0 documentation recording `bca75b4…` and four files.
- **Alternatives/trade-offs:** rewriting the handoff would destroy historical evidence; a dated note preserves lineage at the cost of a second file to read.
- **Affected stage:** C0. **Owner decision:** none beyond approving the supersession note.

### F-02 — Legacy audit table cannot host workflow audit
- **Severity:** CRITICAL. `SOURCE_VERIFIED`.
- **Evidence:** `backend/app/storage/models.py:90-123`; migration `20261017_01` lines 83-105: `observation_record_id` NOT NULL, FK to `monitoring_observation.record_id`, `UNIQUE(observation_record_id)`.
- **Impact:** reusing it would force fake monitoring records or schema breakage; both violate the assignment.
- **Correction:** add `workflow_audit_event` in a new migration; leave legacy tables and repository untouched.
- **Alternatives:** nullable FK + polymorphism would weaken constraints and couple unrelated domains — reject.
- **Stage:** C1 onward. **Owner decision:** accept ERD addition.

### F-03 — No serving authorization or adapter; A3 registry is not applicable
- **Severity:** CRITICAL. `SOURCE_VERIFIED`.
- **Evidence:** `backend/app/inference/registry.py:24-38`; `real_model.py:30-56`; `ai/diagnostic_scope.py:193-231`; D-049; PR #63/#64; A3 frozen note in `docs/research/CARDIOASSIST_AI_MASTER_COMPLETION_PLAN.md:300`.
- **Impact:** trained inference cannot legally/safely execute through the new workflow; no mock substitution allowed.
- **Correction:** Decision A; keep adapter disabled; record `INFERENCE_UNAVAILABLE` until approved; tests prove no bypass.
- **Alternatives:** synthetic-trained candidate B (recommended if owner wants a working AI demo) requires new training/packaging/registry work and explicit authorization — not available for this preflight.
- **Stage:** C2. **Owner decision:** A (and separately B for display).

### F-04 — Exact-operation assertions will break under additive endpoints
- **Severity:** HIGH. `SOURCE_VERIFIED`.
- **Evidence:** `tests/backend/test_openapi_http.py:14-31`; `tests/contracts/test_openapi_document.py:61-63,198-219`.
- **Impact:** a naive implementation either fails CI or deletes the historical regression guard.
- **Correction:** reviewed additive contract change: preserve frozen legacy document/test; add a separate Term-1 document and explicitly amended allowlist test that still asserts the two legacy paths and their schema bindings.
- **Alternatives:** one combined document with expanded allowlist is acceptable only if the original assertions are explicitly updated and retained, not removed.
- **Stage:** C1/C2. **Owner decision:** approve contract change-set.

### F-05 — Patient input cannot satisfy existing synthetic provenance
- **Severity:** HIGH. `SOURCE_VERIFIED`.
- **Evidence:** `ai/research_facade.py:883-1018,1875-1899`; `ai/research_registry.py:131-136`; `backend/app/validation.py:16,238-240`.
- **Impact:** relabelling as `clinician_entry`/`benchmark_import` would be scientific misrepresentation; `synthetic: true` is rejected.
- **Correction:** new server-enforced synthetic-demo provenance contract in §9.5, explicitly allowed by Decision A.
- **Alternatives:** reuse existing generator-based provenance by generating fixtures server-side and having patient "select" a fixture — truthful but weakens the requested patient-initiated workflow; requires owner choice.
- **Stage:** C2. **Owner decision:** A includes admissible sources.

### F-06 — Process-local idempotency/audit cannot be reused
- **Severity:** HIGH. `SOURCE_VERIFIED`.
- **Evidence:** `backend/app/state.py:1-13,83-91,128-157`; `docs/blueprint/04:267-285`.
- **Impact:** restart loses replay protection; multi-worker inconsistency; no durable exactly-once enrollment.
- **Correction:** `durable_idempotency` table with unique `(scope, key)` and atomic write; separate workflow audit; keep legacy cache only for legacy routes.
- **Alternatives:** accept weaker at-most-once UX — not acceptable for registration/redemption.
- **Stage:** C1. **Owner decision:** none; engineering requirement.

### F-07 — Inherited research CI failure is not a prototype defect but is still a blocker for ALL_GREEN
- **Severity:** HIGH. `HOSTED_CI_VERIFIED`, `AGENT_REPORTED` for counts, `UNVERIFIED` for log lines.
- **Evidence:** run `45650285465` 3.11 failure; prior counts 1808/2/10/2; Issue #132 open; PR #141 dual-run gate `45643212294` failure; workflow step keeps hard failure intentionally (`.github/workflows/experiment-runner-ci.yml:81-83`).
- **Impact:** no truthful ALL_GREEN claim; downstream fixture errors may mask new prototype regressions.
- **Correction:** report exact failure and unaffected backend/contract/audit suites; no tolerance widening, fixture edits, suppression, or RH-04 work in Term 1.
- **Alternatives:** waive research job for prototype stages only with explicit owner decision — not recommended before evidence is understood.
- **Stage:** C4 (and status reporting at every stage). **Owner decision:** acknowledgement of residual risk.

### F-08 — Windows runbook destination and cleanup need tightening
- **Severity:** HIGH. `SOURCE_VERIFIED`.
- **Evidence:** runbook §1 clones to `.\CardioAssist-AI`, not `E:\CardioAssist-Term1-Prototype`; §7 contains `Remove-Item ...sqlite3*` guarded by an environment-variable check but still a delete command; §2 says secret names must be frozen by Arena and are not.
- **Impact:** wrong workspace, risk of deleting a non-disposable DB, unverifiable setup.
- **Correction:** explicit non-empty-directory guard, exact `E:\` target, expected SHA check, disposable DB path assertion before any cleanup, frozen env/secret names in delivered configuration contract; mark cleanup as optional and owner-controlled.
- **Alternatives:** never delete from PowerShell at all; leave disposable DB for manual owner cleanup — safer.
- **Stage:** C1–C4. **Owner decision:** confirm workspace is empty/new.

### F-09 — No native Windows evidence
- **Severity:** HIGH. `NOT_RUN`, `OWNER_WINDOWS_VERIFIED` absent.
- **Evidence:** no owner-provided command output; planning docs explicitly state runbook is a draft.
- **Impact:** hosted Linux CI does not prove Windows/PowerShell/SQLite/timestamp/HMAC behavior.
- **Correction:** owner executes §13 blocks and supplies exact output; every result remains `NOT_RUN` until then.
- **Stage:** every stage acceptance. **Owner decision:** execution and evidence.

### F-10 — Governing authorization records are layered and partly stale
- **Severity:** MEDIUM. `SOURCE_VERIFIED`.
- **Evidence:** `AGENTS.md` says "Current authorization: M1b.1 only" then adds M1c, D-047 activation, M3a, R1; no Term-1 stage authorization; master plan §8 still mandates one continuous sprint.
- **Impact:** an implementer could cite an old section as permission for auth/model serving.
- **Correction:** future C0 document explicitly identifies the owner's new stage policy as superseding the one-sprint policy, while preserving old approval records verbatim.
- **Alternatives:** editing AGENTS.md in place would obscure history — avoid.
- **Stage:** C0. **Owner decision:** approve supersession note.

### F-11 — Artifact trust and redistribution conflict with `.gitignore`
- **Severity:** MEDIUM. `SOURCE_VERIFIED`.
- **Evidence:** `.gitignore` excludes `*.pkl`, `*.joblib`, model artifacts; `ai/packaging.py` requires local trusted root + HMAC key; `backend/requirements.txt` has no numpy/scikit-learn/joblib.
- **Impact:** a synthetic-trained artifact cannot simply be committed or served in hosted CI; backend dependency pins must change for any real inference adapter.
- **Correction:** prefer deterministic rebuild from pinned code/seeds with published digest; if a bundle is handed off, curate it outside Git with explicit redistribution rights and owner-approved provenance; add pinned backend deps only under Decision A.
- **Alternatives:** offline-only demonstration with no HTTP adapter — safe but does not satisfy AI integration P0.
- **Stage:** C2/C4. **Owner decision:** artifact distribution and dependency change.

### F-12 — Frontend placeholders are not integration evidence
- **Severity:** MEDIUM. `SOURCE_VERIFIED`.
- **Evidence:** both frontend README files are placeholders; D-045 makes clients thin local integrations, not primary deliverables.
- **Impact:** software-team handoff cannot rely on implemented screens.
- **Correction:** freeze the API Integration Matrix (§8.3) and supply fixtures; no frontend implementation in Term 1 without separate owner approval.
- **Stage:** C4. **Owner decision:** confirm software-team scope.

### F-13 — Enrollment policy gaps are unresolved
- **Severity:** MEDIUM. `PROPOSED`.
- **Evidence:** planning docs specify a single happy path; §6.4 table lists six unresolved policies.
- **Impact:** ambiguous behavior for repeat visits/second invitations/duplicate fictitious IDs could create security or data-integrity defects.
- **Correction:** C0 decision register must choose the minimum safe policy; implement fail-closed defaults for anything undecided.
- **Stage:** C0/C1. **Owner decision:** yes (D-06…D-10 in §14).

### F-14 — Failed inference must not become `PENDING_REVIEW`; no mandatory doctor confirmation exists
- **Severity:** MEDIUM. `PROPOSED`.
- **Evidence:** master plan §7 lists failure states; the requested workflow has doctor review after inference, not before; assignment says do not invent doctor confirmation and do not mislabel failed inference.
- **Impact:** wrong patient status and inaccurate clinician queue.
- **Correction:** §10 state machine; negative tests for each terminal failure state.
- **Stage:** C2. **Owner decision:** approve state contract.

### F-15 — SQLite single-writer and multi-worker limits need explicit handling
- **Severity:** MEDIUM. `SOURCE_VERIFIED`.
- **Evidence:** `database.py:28-60` WAL/busy timeout; `state.py:7-8` says multiple workers/replicas not supported.
- **Impact:** concurrent enrollment or inference retries can produce `database is locked` or duplicate effects if implemented with locks only.
- **Correction:** conditional atomic UPDATE + unique constraints + bounded retry returning `409 concurrency_conflict`; run Uvicorn `--workers 1` for Term 1 and document it.
- **Stage:** C1/C2. **Owner decision:** none.

### F-16 — Migration drift detection will reject unpaired models/migrations
- **Severity:** MEDIUM. `SOURCE_VERIFIED`.
- **Evidence:** `database.py:148-225` checks every `Base.metadata` table and compares metadata to live schema; only one migration exists.
- **Impact:** adding SQLAlchemy models without a migration causes startup failure; adding a migration without matching metadata also fails `alembic check`.
- **Correction:** each stage ships model + migration + drift test together; never bypass `verify_schema()`.
- **Stage:** C1–C3. **Owner decision:** none.

### F-17 — Failure audit after rollback is not designed
- **Severity:** MEDIUM. `SOURCE_VERIFIED`/`PROPOSED`.
- **Evidence:** legacy `audit_event` is written only for accepted monitoring writes; process-local error audit in `state.py`; no workflow failure audit.
- **Impact:** failed enrollment/inference attempts leave no safe evidence trail.
- **Correction:** `workflow_audit_event` failure rows written in a separate transaction with redacted codes only; no request bodies or identifiers.
- **Stage:** C1/C2. **Owner decision:** none.

### F-18 — Patient-score display contradiction
- **Severity:** HIGH. `SOURCE_VERIFIED`/`PENDING_AUTHORIZATION`.
- **Evidence:** handoff §7 and master plan §7/§11; OpenAPI track-a tag says research view only; assignment gates patient display separately.
- **Impact:** implementing provisional score display would violate current policy.
- **Correction:** Decision B with reviewed wording and tests; until then status-only projection.
- **Stage:** C2/C3. **Owner decision:** B.

### F-19 — Stale source comments in diagnostic scope
- **Severity:** LOW. `SOURCE_VERIFIED`.
- **Evidence:** `ai/diagnostic_scope.py:62-64` says registry is EMPTY, while lines 193-231 define the nonempty A3 record; historical tests reference "until A2".
- **Impact:** reviewer confusion if comments are treated as current status; no runtime defect.
- **Correction:** do not alter research source in Term 1; document the distinction in the C0 evidence register.
- **Stage:** C0. **Owner decision:** none.

### F-20 — Test-merge SHA is not a merge
- **Severity:** LOW. `HOSTED_CI_VERIFIED`.
- **Evidence:** PR #142 `merge_commit_sha=8c4be2f…`, `merged_at=null`, state OPEN/DRAFT.
- **Impact:** false claim that prototype code entered `main`.
- **Correction:** always report head SHA and `merged_at` together.
- **Stage:** all. **Owner decision:** none.

### F-21 — CI log line-level counts not independently retrievable here
- **Severity:** LOW. `UNVERIFIED`.
- **Evidence:** GitHub API returns Azure Blob signed URLs; outbound host allowlist excludes that domain; rendered job page shows step-level failure but not pytest summary.
- **Impact:** the numeric counts remain `AGENT_REPORTED`, not independently verified by this reviewer.
- **Correction:** owner/reviewer with full GitHub UI access can paste the exact job log summary; do not upgrade these numbers to `HOSTED_CI_VERIFIED` without it.
- **Stage:** all. **Owner decision:** none.

### F-22 — Planning language risks reusing the real Cleveland bundle as "Candidate A"
- **Severity:** HIGH. `SOURCE_VERIFIED`.
- **Evidence:** master plan §6 "Candidate A (preferred if eligible): exact reviewed trained model artifact with permitted synthetic demonstration inputs"; combined with D-049 and A3 this could be misread as permitting HTTP reuse of the real bundle.
- **Impact:** policy breach if an implementer wires the accepted real bundle into FastAPI.
- **Correction:** C0 must state explicitly that Candidate A requires a **new** serving authorization and that the accepted real Cleveland bundle is never loaded in cloud Arena or HTTP under any existing authorization.
- **Stage:** C0/C2. **Owner decision:** A scope must name exact artifact or forbid it.

---

## 12. Recommended final stage division and dependency map

### 12.1 Verdict on the provisional structure

Keep the five logical stages, but **change their acceptance semantics**. The owner's new policy — one complete stage → one comprehensive master prompt → implementation and organized commits → independent code review → native Windows testing → remediation/retesting → GitHub evidence → explicit owner acceptance → next stage — is a material improvement over the one-sprint policy in PR #142. It must be recorded as a supersession in future C0 documentation without rewriting historical approvals.

| Stage | Recommended scope | Dependencies | Required approvals before start / acceptance | Complexity and risk |
|---|---|---|---|---|
| **C0 — Architecture, Contracts & Stage Planning** | Final workflow, threat model, ERD, authorization design, versioned API contract proposal, AI readiness matrix, state machines, dependency map, owner decision register, acceptance/test strategy, delivery scope. No application changes. | Live repo checkpoint from §2; all governing docs; this preflight. | Owner approves final stage plan and C0 outputs before C1. Decisions A/B at least registered; can be answered at C2. | Medium; mostly analysis, but it gates all downstream work. Risk: treating proposals as approvals. |
| **C1 — Auth, Verified Visit & Enrollment** | Accounts/session/RBAC, verified visits, invitations, HMAC identifier matcher, atomic registration/assignment/consumption, durable idempotency, workflow audit, migration, contracts, negative/concurrency tests. Preserve legacy routes. | C0 accepted; contract change-set approved; F-02/F-06/F-08 resolved. | Owner acceptance of synthetic visit/invitation semantics and Windows evidence. | High; security- and concurrency-sensitive. Do not include AI or assessment. |
| **C2 — Patient Profile, Assessment & Authorized AI** | Health profile/consent, validated patient-initiated synthetic input, immutable snapshot, inference attempts/results/status, recovery, model provenance, role projection. | C1 accepted; Decision A for any real adapter; new synthetic-demo provenance contract approved; backend dependency/artifact decision (F-11). | Decision A; owner acceptance of revised safe scope if A is unavailable; Decision B only if patient score display is desired. | Very high; AI authorization and scientific integrity dominate. |
| **C3 — Doctor Review, Follow-up & Notifications** | Doctor assignment access, review queue, append-only reviews, clinician-authored notes/demo prescriptions, durable messages/notifications/read status, authorized history. | C2 accepted or documented owner decision accepting C2-safe scope; role projection from C0/C2. | Owner acceptance plus Windows evidence. | Medium-high; object-level authorization and atomicity. |
| **C4 — Full Integration, Validation & Handoff** | Whole synthetic E2E, security/regression/migration/restart tests, hosted CI at exact head, Windows verification, setup docs, integration matrix, evidence ledger, honest status labels. | C1–C3 accepted; exact SHA freeze; residual risk register. | Owner review and explicit handoff approval; no automatic merge. | High coordination risk; 2026-12-03 target is tight. |

### 12.2 Dependency map

```
C0 (frozen architecture + decision register)
 ├─ contract change-set ─────────────► C1 routes/tests ──► C2 assessment routes
 ├─ ERD + audit split ───────────────► C1 migration ──────► C2/C3 tables
 ├─ auth/session policy ─────────────► C1
 ├─ enrollment policies ─────────────► C1
 ├─ Decision A (adapter + sources) ──► C2 real inference ONLY
 ├─ Decision B (patient display) ────► C2/C3 patient projection ONLY
 └─ software-team matrix ────────────► C4 handoff

C1 accepted ─► C2 accepted or documented C2-safe scope ─► C3 accepted ─► C4
Cross-cutting: hosted CI at each exact head; native Windows evidence at each stage;
no stage advancement without explicit owner acceptance.
```

**Recommended restructuring rationale:** no new stages are needed; however, C2 must be explicitly conditional. If Decision A is not granted, C2 may deliver snapshot/state/failure/recovery and tests, but must be recorded as `C2_SAFE_SCOPE_ACCEPTED` (or `C2_BLOCKED_FOR_AI`) by the owner before C3. It must never be reported as full C2 completion.

### 12.3 GitHub evidence strategy per stage

- One Draft PR (#142) and one prototype branch; multiple coherent commits per stage with stage-tagged messages (e.g. `feat(term1-c1): ...`).
- Push only to `delivery/term1-prototype` (or the owner-approved continuation branch); no PR per stage by default, no self-review/approval, no merge.
- At each stage boundary record: base/head SHA, `git status`, changed files, exact test commands/counts, workflow URLs/jobs at that SHA, Windows output from owner, blocker register updates, and owner acceptance comment/file.
- Research PR #141 and Issue #132 remain untouched and open.

---

## 13. Per-stage acceptance criteria and automated/Windows tests

All automated checks below are **NOT_RUN by this preflight**; they are specifications for implementation and owner verification. All Windows verification is `NOT_RUN` until the owner supplies output.

### 13.1 C0 acceptance criteria

- **Deliverables:** final architecture/threat model; ERD from §7; API Integration Matrix from §8.3; AI readiness matrix from §9; state machine from §10; decision register from §14; test strategy; explicit supersession note for the one-sprint policy; exact base/head evidence record.
- **Positive tests:** documentation consistency assertions (no route listed as implemented without source evidence; no score display without Decision B); SHA/PR status checks.
- **Negative tests:** no source/migration/workflow changes in C0 diff; no dataset/model artifact committed; no claim of Windows execution.
- **Evidence:** PR #142 diff at exact head; this report; owner acceptance record.
- **Blocking conditions:** owner does not approve plan; decisions A/B left unresolved without a documented deferral path.

### 13.2 C1 acceptance criteria

- **Deliverables:** migration(s), models/repositories, auth/session/RBAC middleware or dependencies, verified visits, invitations, registration/assignment, durable idempotency, workflow audit, additive contract files/tests, negative/concurrency tests, setup documentation updates staged for owner approval.
- **Positive automated tests:** admin provisions doctor; doctor logs in; visit attested; invitation issued; correct fictitious identifier registers; code consumed once; assignment exists; session logout invalidates; restart preserves records; Alembic upgrade/current/check pass.
- **Negative automated tests:** wrong/expired/revoked/consumed code; wrong identifier; duplicate identifier; concurrent double redemption from two connections; non-owned visit; cross-doctor/cross-patient IDOR; suspended user; malformed JSON/duplicate headers; SQL injection-shaped input; no raw identifier in logs/API/DB; rollback leaves no orphan patient; legacy endpoints unchanged.
- **Windows:** full §13.4 C1 block executed by owner.
- **Blocking:** any RBAC/IDOR weakness, raw identifier leakage, non-atomic redemption, destructive migration, or legacy regression.

### 13.3 C2 acceptance criteria

- **Deliverables:** health profile/consent, immutable snapshot, inference attempt/result tables and idempotency, state/recovery logic, role projection, new synthetic-demo provenance contract, adapter either authorized and implemented or explicitly disabled, tests.
- **Positive automated tests:** patient profile accepted with panel version; assessment snapshot digest stable; idempotent resubmission returns same assessment; authorized adapter (if Decision A) produces result + same-model explanation with recorded model identity/digest; `PENDING_REVIEW` only after success; restart preserves all.
- **Negative automated tests:** invalid source/units/out-of-range/missing optional fields; wearable/OCR/Track-B leakage; client-supplied provenance override; tampered artifact/wrong digest; unauthorized env/header/flag bypass; no fallback to mock; abstain/unavailable/error states carry no score; stale attempt recovery; concurrent attempts; patient projection has no score before Decision B.
- **Windows:** C2 block executed by owner; if Decision A absent, Windows block runs fail-closed assertions only and owner signs `C2_SAFE_SCOPE`.
- **Blocking:** no Decision A and no documented revised-scope acceptance; genuine explanation cannot be produced from the same model; score leaks to patient; private bundle used in Arena/CI.

### 13.4 C3 acceptance criteria

- **Deliverables:** doctor patient list/review queue, append-only review actions, clinician-authored follow-up/prescription, message + notification atomic persistence, read status, authorized history.
- **Positive automated tests:** assigned doctor reviews own assessment; rationale stored; follow-up creates message and unread notification; patient marks read; history after restart; pagination.
- **Negative automated tests:** unassigned doctor sees 404/403; patient cannot review/author follow-up; duplicate review/follow-up idempotency; illegal transition; notification of wrong user; partial write rollback; patient projection redaction.
- **Windows:** C3 block executed by owner.
- **Blocking:** object-level access failure, AI-authored prescription, partial message/notification writes.

### 13.5 C4 acceptance criteria

- **Deliverables:** full E2E synthetic journey; security/regression suite; migration upgrade/downgrade-on-disposable/reupgrade/restart evidence; exact-head hosted CI jobs; Windows evidence; setup and handoff docs; integration matrix; residual blocker register.
- **Positive automated tests:** complete journey from admin provisioning to restart-persisted read notification; exact OpenAPI snapshots; fixture pack; source verification; dependency health.
- **Negative automated tests:** all stage negatives re-run; no real ID/PHI/model artifact/secrets in Git or logs; no prohibited workflow weakening; exact test counts recorded including inherited failure.
- **Windows:** full C4 block executed by owner.
- **Blocking:** ALL_GREEN claim while research 3.11 job fails; missing owner acceptance; uncurated software-team repository or artifacts.

### 13.6 Native Windows PowerShell verification blocks (`NOT_RUN`)

**Common safety conditions for every block:** run in PowerShell 5.1 or later as the owner; do not point `CARDIOASSIST_DATABASE_URL` at any non-demo database; do not commit `.env`, DB files, logs, or model bundles; do not use `git clean -fdx`; do not delete the repository or any personal files; do not claim results until the actual output is captured. Each stage block begins with a non-empty-directory guard so an existing `E:\CardioAssist-Term1-Prototype` is never overwritten.

**C0 — baseline verification block (`NOT_RUN`)**

```powershell
$ErrorActionPreference = 'Stop'
$Target = 'E:\CardioAssist-Term1-Prototype'
$RepoUrl = 'https://github.com/Muhammed-Fathi/CardioAssist-AI.git'
if (Test-Path $Target) {
    $Existing = @(Get-ChildItem -LiteralPath $Target -Force)
    if ($Existing.Count -gt 0) { throw "Refusing to reuse non-empty directory: $Target" }
} else {
    New-Item -ItemType Directory -Path $Target | Out-Null
}
git clone --single-branch --branch delivery/term1-prototype $RepoUrl $Target
Set-Location $Target
$ExpectedHead = 'bca75b4646dbde26e495201938b7ae01ea7e0d21'
$ActualHead = (git rev-parse HEAD).Trim()
if ($ActualHead -ne $ExpectedHead) { throw "Unexpected HEAD: $ActualHead" }
git branch --show-current
git remote -v
git status --short
python --version
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
& .\.venv\Scripts\python.exe -m pip check
$env:CARDIOASSIST_DATABASE_URL = 'sqlite:///./var/cardioassist_term1_demo.sqlite3'
New-Item -ItemType Directory -Force .\var | Out-Null
& .\.venv\Scripts\python.exe -m alembic upgrade head
& .\.venv\Scripts\python.exe -m alembic current
& .\.venv\Scripts\python.exe -m alembic check
& .\.venv\Scripts\python.exe -m pytest tests/contracts tests/backend -q -W error
& .\.venv\Scripts\python.exe scripts/verify_sources.py
git diff --check
# HTTP smoke: start in a separate window with the same env var:
#   & .\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1
# Then: Invoke-RestMethod -Uri http://127.0.0.1:8000/openapi.json
# At C0 assert exactly /v1/predictions/cad-tabular and /v1/monitoring/observations.
```

**C1 — auth/visit/enrollment block (`NOT_RUN`; replace the head placeholder with the accepted C1 head before running)**

```powershell
$ErrorActionPreference = 'Stop'
# Repeat the exact clone/non-empty/SHA/branch/dirty checks above; set:
$ExpectedHead = '<PASTE_ACCEPTED_C1_HEAD_SHA>'
$ActualHead = (git rev-parse HEAD).Trim()
if ($ActualHead -ne $ExpectedHead) { throw "Unexpected HEAD: $ActualHead" }
if (git status --porcelain) { throw 'Dirty worktree; refusing verification' }
# ... then from the verified checkout:
$env:CARDIOASSIST_DATABASE_URL = 'sqlite:///./var/cardioassist_term1_demo.sqlite3'
& .\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
& .\.venv\Scripts\python.exe -m pip check
& .\.venv\Scripts\python.exe -m alembic upgrade head
& .\.venv\Scripts\python.exe -m alembic current
& .\.venv\Scripts\python.exe -m alembic check
& .\.venv\Scripts\python.exe -m pytest tests/contracts tests/backend -q -W error
& .\.venv\Scripts\python.exe -m pytest -q -k 'auth or invitation or enrollment or rbac or migration' -W error
& .\.venv\Scripts\python.exe scripts/verify_sources.py
git diff --check
# Use ONLY request bodies/commands shipped in the delivered OpenAPI/fixture script.
# Required owner-observed smoke sequence:
#   1) provision local admin/doctor with operator-supplied secrets;
#   2) doctor login -> attested fictitious visit -> issue code for DEMO-ID-001;
#   3) two concurrent registration attempts with the same code from two shells;
#      exactly one success, one generic rejection, one consumed invitation;
#   4) logout and verify the session is invalid;
#   5) restart uvicorn and verify assigned patient record persists.
```

**C2 — profile/assessment/AI block (`NOT_RUN`)**

```powershell
$ErrorActionPreference = 'Stop'
# Verify exact accepted C2 head and clean tree as in C1.
$ExpectedHead = '<PASTE_ACCEPTED_C2_HEAD_SHA>'
$ActualHead = (git rev-parse HEAD).Trim()
if ($ActualHead -ne $ExpectedHead) { throw "Unexpected HEAD: $ActualHead" }
if (git status --porcelain) { throw 'Dirty worktree; refusing verification' }
$env:CARDIOASSIST_DATABASE_URL = 'sqlite:///./var/cardioassist_term1_demo.sqlite3'
& .\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
& .\.venv\Scripts\python.exe -m pip check
& .\.venv\Scripts\python.exe -m alembic upgrade head
& .\.venv\Scripts\python.exe -m alembic current
& .\.venv\Scripts\python.exe -m alembic check
& .\.venv\Scripts\python.exe -m pytest tests/contracts tests/backend -q -W error
& .\.venv\Scripts\python.exe -m pytest -q -k 'assessment or provenance or inference or state' -W error
# If Decision A is granted, run the delivered adapter-specific authorized test command.
# If Decision A is absent, run only the delivered fail-closed test command and record
# INFERENCE_UNAVAILABLE; do NOT load any real bundle or claim trained inference.
if (Test-Path Env:\CARDIOASSIST_TERM1_INFERENCE_AUTHORIZED) {
    throw 'Authorization must be an owner decision recorded in evidence, not an ad-hoc environment flag.'
}
& .\.venv\Scripts\python.exe scripts/verify_sources.py
git diff --check
# HTTP smoke: patient creates assessment from delivered fixture; patient GET shows status only
# unless Decision B is recorded; doctor GET shows model provenance only if authorized.
```

**C3 — review/follow-up/notification block (`NOT_RUN`)**

```powershell
$ErrorActionPreference = 'Stop'
# Verify exact accepted C3 head and clean tree as in C1.
$ExpectedHead = '<PASTE_ACCEPTED_C3_HEAD_SHA>'
$ActualHead = (git rev-parse HEAD).Trim()
if ($ActualHead -ne $ExpectedHead) { throw "Unexpected HEAD: $ActualHead" }
if (git status --porcelain) { throw 'Dirty worktree; refusing verification' }
$env:CARDIOASSIST_DATABASE_URL = 'sqlite:///./var/cardioassist_term1_demo.sqlite3'
& .\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
& .\.venv\Scripts\python.exe -m pip check
& .\.venv\Scripts\python.exe -m alembic upgrade head
& .\.venv\Scripts\python.exe -m alembic current
& .\.venv\Scripts\python.exe -m alembic check
& .\.venv\Scripts\python.exe -m pytest tests/contracts tests/backend -q -W error
& .\.venv\Scripts\python.exe -m pytest -q -k 'review or followup or notification or authorization' -W error
& .\.venv\Scripts\python.exe scripts/verify_sources.py
git diff --check
# Owner smoke: assigned doctor reviews, authors note/demo prescription, patient lists
# notification UNREAD -> READ, unassigned doctor gets 404/403, restart preserves records.
```

**C4 — full integration/handoff block (`NOT_RUN`)**

```powershell
$ErrorActionPreference = 'Stop'
# Verify exact final head, clean tree, remote and branch as in C1.
$ExpectedHead = '<PASTE_ACCEPTED_FINAL_HEAD_SHA>'
$ActualHead = (git rev-parse HEAD).Trim()
if ($ActualHead -ne $ExpectedHead) { throw "Unexpected HEAD: $ActualHead" }
if (git status --porcelain) { throw 'Dirty worktree; refusing verification' }
$env:CARDIOASSIST_DATABASE_URL = 'sqlite:///./var/cardioassist_term1_demo.sqlite3'
& .\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
& .\.venv\Scripts\python.exe -m pip check
& .\.venv\Scripts\python.exe -m alembic upgrade head
& .\.venv\Scripts\python.exe -m alembic current
& .\.venv\Scripts\python.exe -m alembic check
& .\.venv\Scripts\python.exe -m pytest tests/contracts tests/backend -q -W error
& .\.venv\Scripts\python.exe -m pytest -q -W error
& .\.venv\Scripts\python.exe scripts/verify_sources.py
git diff --check
# Record exact pass/fail/skip counts. Do not filter or suppress the inherited
# synthetic-research failure. Capture hosted CI URLs for THIS exact head.
# Restart: stop uvicorn, start again with the same env var, repeat the full E2E
# read sequence and record output. Do not delete non-demo databases.
# Optional cleanup only after confirming the exact disposable DB path:
#   if ($env:CARDIOASSIST_DATABASE_URL -ne 'sqlite:///./var/cardioassist_term1_demo.sqlite3') { throw 'Refusing cleanup' }
```

**Evidence fields the owner must supply for each executed stage block:** PowerShell version; OS build; Python version; exact head/dirty status; pip check output; Alembic head/current/check output; every pytest summary line; source-verification output; `git diff --check` result; HTTP smoke transcript (with no secrets/identifiers); restart observations; failures and remediation commits. Until this is supplied, all stage Windows statuses remain `NOT_RUN`.

---

## 14. Owner decision register

None of the items below is granted by this report, by PR #142, by the historical one-sprint prompt, or by research gate approvals.

| ID | Decision required | Why it blocks / affects | Recommended default until decided | Stage |
|---|---|---|---|---|
| D-01 | Approve the final stage division and one-master-prompt-per-stage policy; acknowledge supersession of the one-sprint policy in PR #142 | Before C1 | No implementation beyond C0 | C0 |
| D-02 | Approve C0 architecture/ERD/API/state/test outputs | Before C1 | Treat all as `PROPOSED` | C0 |
| D-03A | **Decision A:** exact educational local-demo inference adapter and permitted synthetic input sources | Before any real inference in C2 | Adapter disabled; `INFERENCE_UNAVAILABLE`; no mock fallback | C2 |
| D-03B | **Decision B:** display of a research-model score to synthetic patient, with reviewed wording | Before patient score/explanation display | Patient sees status only | C2/C3 |
| D-04 | Confirm the real Cleveland bundle is NOT authorized for HTTP/prototype use under any existing record | Immediately; prevents F-22 | Forbid loading in Arena/CI/HTTP | C0/C2 |
| D-05 | Approve synthetic-demo provenance contract §9.5 and forbid relabelling | Before C2 assessment intake | Reject all non-demo sources | C2 |
| D-06 | Accept clinician-attested fictitious visit + identifier-bound invitation semantics for the demo | Before C1 enrollment | Fictitious IDs only; no real IDs | C1 |
| D-07 | Choose repeat-visit / existing-account / second-invitation policies | Before C1 tests freeze | Fail closed; one active assignment | C1 |
| D-08 | Choose multiple-doctor and assignment-revocation/consent policy | Before C1/C3 | One active doctor; explicit revocation | C1/C3 |
| D-09 | Choose duplicate fictitious identifier policy | Before C1 | Reject duplicate registration | C1 |
| D-10 | Accept session scheme (bearer vs cookie), TTL, revocation, and password-hashing library/pins | Before C1 | Stdlib PBKDF2 if no new dependency approved | C1 |
| D-11 | Approve additive OpenAPI/JSON Schema change-set and exact-test amendment | Before new endpoints | Legacy document unchanged | C1/C2 |
| D-12 | Approve artifact trust/distribution strategy and new backend dependency pins if Decision A is granted | Before C2 adapter | Deterministic rebuild preferred; no private keys in CI | C2/C4 |
| D-13 | Accept revised safe C2 scope if Decision A is unavailable | Before C3 | `C2_SAFE_SCOPE` acceptance required | C2 |
| D-14 | Acknowledge inherited research CI failure and residual risk; decide whether to waive it for prototype handoff | Before C4 handoff | Report honestly; do not suppress | C4 |
| D-15 | Approve software-team curated repository creation, attribution, redistribution rights, and timing | Only after final review | Do not create any new repository | C4 |

---

## 15. Delivery feasibility and prioritized scope reductions

**Feasibility of 2026-12-03:** high risk. As of this review, zero Term-1 application functionality exists. C1 alone requires secure accounts, sessions, RBAC, verified visits, keyed matching, atomic redemption, migrations, contracts, and security tests. C2 depends on a separate AI authorization that does not yet exist. C3 and C4 depend on prior acceptance and native Windows evidence from the owner. The date can be a handoff of an honestly scoped prototype, but not a guarantee of the full original P0 list.

**Cut in this order if time is short (never cut privacy, model integrity, persistence, access control, or tests):**

1. PDF export, rich admin UI, statistics/risk-band charts, rich chat, push, reminders, OCR, wearables, appointments — already deferred in planning.
2. Forced-first-login-password-change *UX* (server-side temporary-password expiry still required).
3. Advanced pagination/filtering and clinician patient summary beyond a minimal list/detail.
4. Non-essential message metadata and notification types beyond assessment review/follow-up.
5. If Decision A is absent: real inference and same-model explanation. Deliver fail-closed assessment state, provenance validation, persistence, and doctor workflow; report AI integration as `BLOCKED`, not complete.
6. If Decision B is absent: patient score display; status-only projection is the safe, policy-compliant fallback.

**Must not be cut:** secure password hashing/session revocation; object-level authorization; non-enumerating generic errors; keyed identifier matching with no raw IDs; atomic redemption with concurrency test; migration + startup verification + restart evidence; immutable snapshots; failure-state correctness; role redaction; clinician authorship; negative tests; exact-head CI evidence; owner Windows verification.

**Realistic handoff artifact set if gates are partially blocked:** working C1 + C2-safe + C3 (with owner's documented decision) + C4 evidence ledger, plus an explicit `AI BLOCKED — Decision A pending` and `PATIENT SCORE BLOCKED — Decision B pending` section. This is preferable to a simulated trained-model demo.

---

## 16. GitHub evidence and software-team handoff strategy

### 16.1 Future documentation structure under `docs/term1/` (PROPOSED — do not create now)

- `TERM1_STAGE_EXECUTION_PLAN.md` — owner-approved final stage division and prompts index.
- `TERM1_STAGE_PROGRESS.md` — append-only stage status with exact SHAs and evidence categories.
- `TERM1_API_INTEGRATION_MATRIX.md` — §8.3 augmented with frozen schemas and fixture paths.
- `TERM1_DECISION_REGISTER.md` — §14 with owner decision records and timestamps.
- `TERM1_TEST_EVIDENCE.md` — exact commands, counts, job links, Windows output supplied by owner.
- `CARDIOASSIST_TERM1_ARENA_PREFLIGHT_REVIEW.md` — this report (or an approved copy) plus the independent ChatGPT reviewer verdict.
- Per-stage acceptance reports: `TERM1_C0_ACCEPTANCE.md` … `TERM1_C4_ACCEPTANCE.md`.
- `TERM1_BLOCKER_REGISTER.md` — Decisions A/B, inherited CI defect, artifact rights, Windows status.
- `TERM1_FINAL_HANDOFF_REPORT.md` — implemented/tested/blocked/deferred status, setup guide, exact release SHA.

Historical files (`CARDIOASSIST_TERM1_NEW_CHAT_HANDOFF_20261125.md`, the old one-sprint prompt, master plan) remain preserved; a dated supersession note must identify the old one-sprint policy explicitly.

### 16.2 GitHub evidence rules

- Use the existing Draft PR #142; no PR per stage unless the owner requests one; no merge/close/approval by agents.
- Record both commit SHAs and PR check conclusions for the **exact head**; a test-merge SHA is not evidence of merge.
- Keep job-level URLs for backend, contract, audit, and synthetic runner workflows; record the inherited 3.11 failure verbatim. Do not widen tolerances, edit Golden fixtures, suppress tests, or weaken workflows.
- Do not comment on, merge, or close PR #141 or Issue #132; do not import research changes. Note only the boundary status for awareness.
- Evidence labels must be explicit: `SOURCE_VERIFIED`, `HOSTED_CI_VERIFIED`, `OWNER_WINDOWS_VERIFIED`, `AGENT_REPORTED`, `PROPOSED`, `PENDING_AUTHORIZATION`, `BLOCKED`, `NOT_RUN`, `UNVERIFIED`.

### 16.3 Software-team handoff

- Primary deliverables: authorized-scope AI adapter (if approved), FastAPI backend, durable database + migrations, versioned API contracts/schemas/fixtures, synthetic setup instructions, automated tests, and owner-verified Windows evidence.
- Flutter/React apps remain the software team's work; README placeholders are not clients. Integration should use the frozen OpenAPI/JSON Schemas from §8.3 with relative URLs in browser code and a documented API base for Flutter.
- A new clean repository may be created only after final review and owner approval, with curated files, fresh history, correct attribution, and confirmed redistribution rights. Do not create it in this assignment.
- `.gitignore` excludes model artifacts/keys; any artifact handed off must be deterministic-rebuildable or explicitly curated with rights. Do not copy private bundles or keys.

---

## 17. Residual limitations and unverified claims

1. **No tests executed by this review.** All pytest commands in §13 are `NOT_RUN`; hosted CI conclusions are `HOSTED_CI_VERIFIED`, counts are `AGENT_REPORTED`, and log lines are `UNVERIFIED`.
2. **No native Windows execution.** Every Windows item is `NOT_RUN`; only the owner can produce `OWNER_WINDOWS_VERIFIED` evidence.
3. **No research-track execution or import.** PR #141 and Issue #132 were inspected for boundary awareness only; no branch was switched, no research file changed, no private bundle opened, no dataset acquired.
4. **No model training or serving.** No synthetic model was trained; no real artifact was loaded; no patient score display was activated.
5. **Prototype branch source was not materially different from `main`.** The GitHub compare shows only four added documentation files; source evidence was read at `main` with that verified relationship.
6. **Log-line limitation:** GitHub job log URLs redirect to Azure Blob storage outside the permitted outbound host list; the rendered job page confirmed step failure/success but not the exact pytest summary lines.
7. **No supplied independent reviewer audit addendum.** This report reconciles the assignment, live GitHub evidence, governing documents, and source; no separate addendum file was present in the checkout.
8. **Stale status vs historical truth.** Statements in older documents that conflict with live SHAs are reported as stale status, not rewritten or treated as current approvals.
9. **PostgreSQL compatibility untested.** No claim of parity is made; migration strategy is SQLite-first and portable by design only.
10. **Authorization records are interpreted, not created.** Decision A/B and Stage acceptance remain owner acts; nothing here ratifies them.

---

## 18. Final preflight recommendation

**`PREFLIGHT_RECOMMENDATION=ACCEPT_WITH_CHANGES`**

**Justification.** The five-stage C0–C4 structure is the right granularity under the owner's new policy: each proposed stage is a coherent engineering unit, and the one-master-prompt-per-stage rule is preserved. However, accepting the provisional plan verbatim would be unsafe for four source-verified reasons: (1) PR #142 contains only documentation, so no stage can claim implementation until code exists; (2) the legacy audit table's mandatory monitoring foreign key and the absence of any workflow/auth tables force a dedicated audit table and a new migration before C1; (3) serving authorization is absent and the A3 offline activation is HEAD- and operation-bounded, so C2 cannot claim AI completion without Decision A or an owner-accepted revised scope; and (4) exact two-operation OpenAPI assertions and the inherited Python 3.11 research failure make naive additive endpoints or `ALL_GREEN` claims invalid.

**Conditions attached to the recommendation:**

1. Owner approves C0 outputs and the supersession note before C1.
2. Decisions A and B are separately recorded; until A, inference is disabled and reported `INFERENCE_UNAVAILABLE`; until B, patient projection is status-only.
3. The real Cleveland bundle is explicitly excluded from HTTP/cloud use under existing authorizations.
4. `workflow_audit_event` and durable idempotency are introduced in C1; legacy monitoring tables/contracts/tests remain intact.
5. C2 may be accepted only as full C2 with authorized real inference **or** as documented `C2_SAFE_SCOPE` with AI blocked; never as full C2 with a mock or fabricated result.
6. Every stage requires independent review, exact-head hosted CI evidence, owner-executed native Windows evidence, and explicit owner acceptance before the next stage.
7. No Golden fixture, tolerance, workflow, research gate, Issue #132 state, PR #141, merge, or new repository is changed by this work.

The independent ChatGPT engineering reviewer and the human repository owner should determine the final plan and authorizations. This review does not begin C1 or any implementation stage.

**End of preflight report.**
