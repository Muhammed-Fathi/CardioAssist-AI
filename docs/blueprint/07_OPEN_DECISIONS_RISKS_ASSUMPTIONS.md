# 07 — Open Decisions, Risks, Assumptions and $0-Budget Constraints

**Status:** Updated 2026-10-17 to reconcile D-044, D-045 and M1b.1 scope.
This file **consolidates and indexes** open items; it does not close unrelated
decisions or approval gates. The authoritative registers remain
`docs/DECISIONS.md`, Phase 0 §13/§R2-9, `shared/contracts/README.md` §11
(Q1–Q14), and `backend/CONTRACT_NOTES.md` (A-01 technical status, B-01…B-04,
G-01/G-02, X-01).

---

## 1. Pending human approvals (P-register — `docs/DECISIONS.md`, unchanged)

| # | Pending item | Blocks | Status |
|---|---|---|---|
| P-1 | Final scientific target + model evaluation protocol | D-006; all Track-A modelling | PENDING — research lead + supervisor |
| P-2 | Dataset acquisition authorization (Gate DA), per exact dataset list | D-007; M2; any download | PENDING — named human |
| P-3 | Supervisor approval of frozen pre-training protocol (Gate PT) | D-032; M3; any fitting/selection/tuning/evaluation | PENDING — supervisor |
| P-4 | Clinician approval of medical explanation & safety wording | D-016/D-026; all user-facing clinical copy (F03/F04/F06/F13/F15/F16) | PENDING — named clinician reviewer (or "none — maximally conservative copy") |
| P-5 | External-validation / clinical-readiness claims | — | **NOT MADE — prohibited** (lifecycle-governed, D-033) |
| P-6 | Real wearable integrations & access-dependent features | D-009; F05 real adapters | PENDING — device owner + $0 account resolution + vendor terms |

## 2. Open technical/decision items (indexed)

### 2.1 Decision register (`docs/DECISIONS.md`)

| ID | Item | Status |
|---|---|---|
| D-005 | Private monorepo formal approval | PROPOSED (operates as one already) |
| D-006 | Precise ML target/horizon | OPEN (= P-1; T1 is working assumption only) |
| D-007 | Selected datasets / data handling | OPEN (= P-2; multi-dataset *strategy* D-040 approved, acquisitions not) |
| D-009 | Wearable integrations | OPEN (Track-B architecture approved; real integrations = P-6) |
| D-010 | Research gap / publication contribution | OPEN (= D-025 verification first) |
| D-011…D-033 | Phase 0 proposed decisions (§13/§R2-9) | Tracked in Phase 0; several *directions* adopted by D-034…D-045 without closing scientific/data/clinical approvals |

### 2.2 Contract questions (`shared/contracts/README.md` §11)

| # | Question | Owner / blocker |
|---|---|---|
| Q1 | Real feature-schema ids and per-feature type/unit/range | Gate DA + dictionary audit |
| Q2 | Ratified unit for ST-depression (`oldpeak`) | §F-1 / data dictionary |
| Q3 | `thal` admissibility at the intended prediction moment; `ca` exclusion confirmation | D-027 + availability audit |
| Q4 | Approved target definition + narrowing threshold wording | P-1 / D-006 |
| Q5 | `benchmark_import` source token adequacy | Research lead |
| Q6 | Explicit `model_id` selection in request? | Backend/AI review |
| Q7 | Track-B replay 201 vs 200; `consent_id` shape | Backend review (current: 201 both, per merged tests) |
| Q8 | **24 h idempotency retention is the implemented & tested runtime behavior** (window in the merged OpenAPI; expiry covered by tests). Q8 = **formal ratification** of the window + the durable **store of record** (in-memory/file/DB). M1b.1 persists monitoring observations and success-audit metadata, not idempotency keys or replay state; process-local 24 h behavior remains unchanged | Separate future decision; unresolved |
| Q9 | Structured `warnings[]` / `warning_code`? | Frontend/Backend review |
| Q10 | Normalized importance share in explanations? | Clinician-facing design (P-4) |
| Q11 | Batch observation ingestion for offline sync | Mobile workstream (M1b) |
| Q12 | `patient_ref` identifier-shaped value denylist implementation | Privacy review |
| Q13 | Which of the six M1a.1 error codes accepted/renamed? | Reviewer decision |
| Q14 | FHIR export contract versioning | D-020 |

### 2.3 Backend compatibility notes (`backend/CONTRACT_NOTES.md`)

| ID | Issue | Current behavior | Pending decision |
|---|---|---|---|
| **A-01** | Optional-null rejected by schema `allOf` but accepted by backend | Optional null = missing (success + existing warning); required null remains invalid | **RESOLVED — technical correction complete** under D-044: runtime schema reader merged in PR #7; schema/fixture/test correction merged in PR #8 (`156bde2`). Independent Windows test and GitHub check rollup are not claimed here; those verification limits do not reopen the technical correction |
| B-01 | Track-B wire scalars (number/string/boolean/null) vs numeric metric catalogue | Permissive accept + numeric range check; no coercion | Reviewer must ratify intended type rule + error code before tightening |
| B-02 | Common prose "replay = 200" vs Track-B 201 | 201 for first + replay (merged tests) | Reconcile generic wording; do not change behavior silently |
| B-03 | Idempotency namespace scoping | Global key store + route-identity guard (cross-route reuse = 409) | Endpoint/client scoping needs reviewed decision |
| B-04 | All-null observations, repeated metric ids, count semantics | Null skipped; all-null = 201 count 0; duplicates counted individually | Reviewer ratify or revise |
| G-01 | Optional `request_id` vs required UUID in success schemas | Deterministic correlation UUID generated; replay preserves | No change needed (recorded) |
| G-02 | Validation-order table vs unconditional-conflict rule | Unconditional: conflict/replay lookup **before** semantic checks | Reconcile README table wording |
| X-01 | Legacy LIME fixture with illustrative fixed local R² | LIME-only model = 503 on live server; fixture frozen | Real LIME only with method+fidelity validation (M3) |

### 2.4 M1a.3 carry-forward items (handoff §1.2; deferred/resequenced)

M1a.3 is deferred/resequenced by D-045, not cancelled or completed. When it
is rescheduled, B-01–B-04, G-02 and X-01 must be explicitly carried into its
review, not silently resolved by client code. A-01's technical correction is
complete (D-044 / PR #7 and #8 merged); it is not an open carry-forward item.

## 3. Risks (delivery + scientific)

Scientific risks SR1–SR10 (Phase 0 §R2-8) and R1–R10 (§12) remain the
authoritative registers (leakage inflation, harmonization drift, calibration
leakage, SHAP misreading, tiny-cell subgroup claims, wearable drift into
inference, benchmark-overfitting-as-clinical-performance, UCI-411 mistaken
for external validation, reassessment-spam score drift, TRIPOD+AI reporting
drift). Additional **delivery** risks from this blueprint:

| ID | Risk | Mitigation |
|---|---|---|
| DR1 | Blueprint treated as authorization to implement beyond the current slice | D-045 authorizes M1b.1 only; these planning docs do not authorize later M1b work, M1a.3, dataset/model research, or clinical work |
| DR2 | M1b scope creep (F14–F17 sneaking in) | Product track (M5, [03](03_MILESTONE_ROADMAP_AND_DEPENDENCIES.md) §4) + scope list in §1; anything else needs a new decision |
| DR3 | Mock CAD output misrepresented as trained AI in UI/PR/paper | Mandatory MOCK labelling + snapshot tests + PR evidence (06 §6) |
| DR4 | Contract drift during future M1b read/consent/review API work | Contract-first protocol ([04](04_DATABASE_AND_API_INTEGRATION_DESIGN.md) §6) + fixture suite before implementation; M1b.1 adds no new route |
| DR5 | External mockup images never supplied, UI built on guesses | EXT-01…14 tracked as required inputs (02 §2); UI rows marked UNVERIFIED for layout until supplied |
| DR6 | SQLite-only habits blocking PostgreSQL path | Portability rules ([04](04_DATABASE_AND_API_INTEGRATION_DESIGN.md) §4) + PG compatibility job by M4 |
| DR7 | Free-tier/CI quota exhaustion or term changes | Local-first default; re-verify quotas before relying (Phase 0 §7.4); hosting optional/disposable |
| DR8 | Agent session loss mid-milestone | Commit early; one milestone per session/PR (REPO_SETUP guidance) |

## 4. Assumptions (explicit)

| ID | Assumption | If false |
|---|---|---|
| A1 | The maintainer continues the PR-only, human-reviewed workflow (no enforced branch protection on GitHub Free private repos) | Process must tighten; never claim technical protection |
| A2 | Team machines can run Python 3.11+, and at least one can run Flutter + Android emulator or a physical device | F04 testing degrades to recorded-UNVERIFIED (Phase 0 §R2-7.4 fallback) |
| A3 | T1 (cross-sectional CAD presence) will be approved as the Track-A target (working assumption only) | Redesign target-dependent items; contract already target-named so impact is bounded |
| A4 | UCI-45/UCI-412 remain publicly CC-BY-accessible at acquisition time | Gate DA re-checks licences at download; strategy ranking may change |
| A5 | The existing contract fixture pack and tests define current wire behavior; future work may add but not silently change it | Any change goes through the contract-change protocol |
| A6 | Product-track scope (F14–F17) remains required product vision; its schedule is separate and must follow D-045 priorities and explicit authorization. Nothing in M1b.1 depends on it | Rows stay PROPOSED until scheduled; no loss of vision (matrix keeps them); M4 research completion never implies product completion |
| A7 | A named clinician reviewer (P-4) may be unavailable; conservative-copy fallback is acceptable for the prototype | F16 stays omitted (D-026 default); wording stays generic |
| A8 | Datasets will be acquired on a team machine outside the Arena sandbox (sandbox egress blocks UCI/PhysioNet) and supplied through the approved channel for M2/M3 | M2/M3 slip; platform milestones unaffected |

## 5. $0-budget constraints (D-001) — operational inventory

| Resource | Constraint | Current status |
|---|---|---|
| Paid services | **None allowed**; no card-required trials | Enforced (AGENTS.md) |
| GitHub Actions | GitHub Free private repos: 2,000 min/month, 500 MB artifacts (Phase 0 §7.4, verified 2026-10-16) | Two lean workflows installed; re-check quota monthly |
| Hosting | Free tiers time-sensitive, may require cards, may prohibit health-adjacent use | Local-first is the deliverable; hosted demo optional + disposable + terms-verified in writing first |
| Datasets | Free public sources only (UCI CC BY, CDC public-use, PhysioNet open); controlled sets need institutional paths (Framingham/BioLINCC) | Nothing acquired; Gate DA required |
| ML compute | CPU-only sandbox (2 vCPU / 3.8 GiB); n≈300 tabular work feasible; ECG deep learning not | Matches Track A scope; no GPU assumed |
| OCR (M5) | Local free engine only (Tesseract-class); cloud OCR prohibited (cost + PHI egress) | Decision recorded in 02/F14 |
| Wearables | No paid developer accounts; Apple Developer Program conflicts with $0 for iOS (D-019) | Simulator-first; iOS out of scope |
| Model artifacts | Out of git; Git LFS **not** used by default (quota unknown) | Policy in DATA_POLICY/REPO_SETUP |
| Third-party IdP/notifications | FCM/APNs/OAuth providers need accounts; deferred | Local sessions (M1b); in-app notifications only |

## 6. What would unblock the next work items (cheat-sheet)

| Next work | Needs |
|---|---|
| M1b.1 | **First M1b slice authorized by D-045**; scope is existing monitoring POST + SQLite/Alembic persistence only. PR #9 is the standalone review artifact; leave open and do not merge without human approval |
| Resume M1a.3 | Separate scheduling/authorization; deferred/resequenced by D-045, not cancelled or completed. Preserve the existing handoff plan |
| Later M1b slices | Separate maintainer authorization; future endpoints remain contract-first. Q8/idempotency store policy and consent semantics remain unresolved |
| Apply ADR-001 patch | Complete: Option A recorded in D-044; PR #7 and #8 merged; A-01 technical correction complete |
| Start M2 | P-2 Gate DA authorization naming exact datasets + storage plan |
| Start M3 | M2 audit merged + P-3 Gate PT supervisor sign-off |
| Any clinical copy | P-4 named clinician (else conservative fallback) |
| Real wearables | P-6 named device owner + accounts + vendor terms |
| UI mockup fidelity | EXT-01…14 supplied to the repo/session |
