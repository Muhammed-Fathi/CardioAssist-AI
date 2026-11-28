# Decision Register

> **Operating note (updated 2026-10-16):** Phase 0 is complete — PR #1
> (`docs: Phase 0 feasibility review and source integrity fix`, merge commit
> `0ae333f`) is merged into `main`, including
> `docs/phase0/PHASE0_REVIEW_DRAFT.md` (Rev. 3, with the final UCI
> target-label clarification: `num` supports presence classification 0 vs 1–4
> only; severity/ordinal modelling remains UNAPPROVED) and the corrected
> `research/source_materials/SOURCE_MANIFEST.sha256`. The Phase 0 report
> records its proposed decisions D-011…D-033 in its own register (§13 /
> §R2-9); to avoid ID collisions, this file's Phase 1 entries continue at
> D-034. Phase 1 additions below were recorded per explicit maintainer
> instruction and, like every change to `main`, take effect only after human
> PR review and merge. Confirmed decisions D-001…D-004 are unchanged.

## Phase 0 and earlier (D-001 … D-010)

| ID | Decision | Current status | Approver / rationale |
|---|---|---|---|
| D-001 | Project budget is $0 | CONFIRMED by project team | No mandatory paid services |
| D-002 | Use Arena Agent with GitHub repo-first workflow | CONFIRMED by project team | Persist reviewed work across sessions |
| D-003 | Supervisor paper classification follows first-tab title cell colors | CONFIRMED by project team | Green approved; pink/orange conditional; red rejected |
| D-004 | Presentation defines requirements/vision, not authoritative datasets or papers | CONFIRMED by project team | Review all scientific claims independently |
| D-005 | Private GitHub monorepo | PROPOSED | Owner/team to create and approve |
| D-006 | Precise ML prediction target and horizon | **OPEN** — pending approval P-1 | Research lead + supervisor; depends on labeled data. Track A adopted as a *track* (D-038) does not freeze the final target or the model evaluation protocol |
| D-007 | Selected datasets / redistribution and human data handling | **OPEN** — P-2 approved only for the D-046 local read-only audit scope; P-3 remains pending | Research lead + supervisor; needs license review. The multi-dataset strategy (D-040) is adopted, but each dataset still requires its own acquisition authorization (Gate DA) before any download |
| D-008 | Deployment stack and model serving topology | **CONFIRMED** by maintainer 2026-10-16 | Resolved by the Phase 1 baseline: D-036 (unified versioned FastAPI backend), D-037 (backend responsibilities), D-041 (local-first modular monolith at $0) |
| D-009 | Clinically meaningful wearable integrations | **OPEN** — partially resolved | Track B monitoring architecture and the wearable→CAD-inference prohibition are approved (D-039); real wearable integrations and access-dependent features remain PENDING (P-6) |
| D-010 | Research gap / publication contribution | OPEN | Validate against accepted paper full texts and current literature; no novelty claim before the Phase 0 §F-2 / D-025 full-text verification and broader literature search |

## Phase 1 technical decision baseline — maintainer-approved (D-034 … D-043)

Recorded 2026-10-16 after the maintainer merged Phase 0 PR #1. These are
**technical/architectural directions**; they do not settle any scientific
target, dataset access, protocol, clinician-wording, or validation question
— those remain in the pending table below.

| ID | Decision | Status | Approver / rationale |
|---|---|---|---|
| D-034 | The patient frontend is a **Flutter mobile application** | **APPROVED** | Maintainer (Phase 1 baseline). Flutter app is core scope per the Phase 0 preservation rule (§R2-3, C3/G6); Android-first local testing (emulator + physical device) at $0 per §R2-7.4; iOS build and store release remain out of scope |
| D-035 | The clinician frontend is a **React + TypeScript website** | **APPROVED** | Maintainer (Phase 1 baseline). Dashboard per Phase 0 §R2-7.3 (C1/C2/C4) on demo/benchmark data only; no PHI |
| D-036 | Both frontends communicate through a **unified versioned FastAPI backend** (`/v1`, one contract) | **APPROVED** | Maintainer (Phase 1 baseline). Resolves D-008's API/serving layer; contract shape per Phase 0 §R2-6, to be frozen by the M1a contract review |
| D-037 | The backend handles **authentication, authorization, patient records, monitoring, inference integration, audit logging, and clinician review** | **APPROVED** | Maintainer (Phase 1 baseline). Aligns with the Phase 0 §R2-1 unified-platform services and §R2-7.2 workstream B; prototype-grade security only (§7.5); no PHI; no regulatory-compliance claims |
| D-038 | **Track A is clinical CAD classification with SHAP/LIME explainability and clinician review** | **APPROVED** (as a track) | Maintainer (Phase 1 baseline). Adopts the Phase 0 §R2-1/§R2-2 two-track separation (D-023) and explanation rules (§R2-5.7, §R2-6.5). The final scientific target and model evaluation protocol remain **PENDING** (P-1); D-006 stays OPEN; Phase 0 T1 remains the working assumption only |
| D-039 | **Track B is patient and wearable monitoring; wearable observations must not feed CAD inference without separately validated scientific evidence** | **APPROVED** | Maintainer (Phase 1 baseline). Binding one-way rule per Phase 0 §F-4/§R2-6.2 — wearable payloads to CAD inference fail with `422 wearable_input_not_valid_for_cad_inference`; contract test F-09 enforces it. Real wearable integrations remain **PENDING** (P-6); D-009 stays OPEN |
| D-040 | The project uses a **multi-dataset research strategy with explicit compatibility, overlap, licensing, and leakage gates** | **APPROVED** (as a strategy) | Maintainer (Phase 1 baseline). Per Phase 0 §R2-4 (strategies A–D, the §R2-4.2 harmonization/leakage conditions, and the §R2-4.4 pre-download checklist). Does **not** authorize any dataset acquisition — each dataset needs its own Gate DA authorization (P-2); D-007 stays OPEN |
| D-041 | The architecture is a **local-first modular monolith**, maintaining the **$0 budget** | **APPROVED** | Maintainer (Phase 1 baseline). Resolves D-008's serving topology; consistent with D-001; microservices/Kafka/Kubernetes topology deferred per Phase 0 §7.1–§7.3; free-tier hosting remains optional and disposable (§7.4) |
| D-042 | **Flutter and React are both core project components; neither may be silently removed** | **APPROVED** | Maintainer (Phase 1 baseline). Codifies `docs/FEATURE_REGISTER.md` ("never remove a feature silently") and the Phase 0 Rev. 2 preservation rule; any future removal requires an explicit new decision entry in this register with human approval |
| D-043 | The **first implementation milestone is M1a: versioned API contracts, deterministic mock CAD/XAI responses, contract tests, and minimal integration scaffolding** | **APPROVED** | Maintainer (Phase 1 baseline). Per Phase 0 §R2-7.6 M1a: mock/simulated data only (fixtures F-01–F-12); no real models, no datasets, no training; sequence remains M1a → M1b → M2 → M3 → M4, each an independently reviewable PR |

## ADR-001 contract decision — maintainer-approved (D-044)

Recorded 2026-10-17. This entry records the ADR-001 decision only. It does
**not** authorize M1a.3, dataset acquisition, model training, clinical
claims, or any other pending item.

| ID | Decision | Status | Approver / rationale |
|---|---|---|---|
| D-044 | **ADR-001 Option A — in-place correction of optional-feature nullability in the existing mock clinical feature schemas (`mock_clinical_v1`, `mock_clinical_v2`)**, with matching fixtures and regression tests | **APPROVED** by the maintainer 2026-10-17. Implementation **COMPLETE**: runtime schema-reader prerequisite merged in PR #7 (`7f850bd`); schema/fixture/test correction merged in PR #8 (`156bde2582671ad08f187850e3a7cc20790b19d2`). Finding A-01's technical correction is complete | Maintainer approval. **Scope:** optional feature `value: null` only, in the two mock feature schemas, fixtures and tests. **Rationale:** the approved contract prose and tested backend already interpret an explicit null for an optional feature as "not provided"; the existing JSON Schema `allOf` typed constraints incorrectly reject that representation. **Compatibility:** a schema-validity broadening aligned with existing accepted server behavior — not a scoring or HTTP behavior change. **Safeguards:** required features remain non-null; zero/false remain valid data; existing types, units and ranges are preserved; no clinical semantics change. **Implementation sequencing:** an audit found the runtime reads `properties.value["type"]` directly, so the ADR's `anyOf` shape required a minimal runtime adapter before the schema correction; both reviewed change-sets are now merged. ADR: `docs/blueprint/ADR_001_CAD_OPTIONAL_NULL_FEATURE_VALUES.md` |

The runtime prerequisite is PR #7
(<https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/7>), **MERGED** into
`main` at merge commit `7f850bd7e2eaceb16bfa664f394021837c678f93`. The
schema/fixture correction is PR #8
(<https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/8>), **MERGED** into
`main` at merge commit `156bde2582671ad08f187850e3a7cc20790b19d2`. Together they
complete the A-01 technical correction. This administrative status does not
assert independent Windows verification or a CI check result unless recorded
separately; it does not reopen the merged code correction.

## Approved delivery-priority adjustment — maintainer-approved (D-045)

Recorded 2026-10-17 from the maintainer's explicit M1b.1 authorization.

| ID | Decision | Status | Approver / rationale |
|---|---|---|---|
| D-045 | Prioritize final delivery in this order: **(1) real, reproducible CAD AI research and inference; (2) a complete, integration-ready FastAPI backend; (3) a durable, tested database.** React and Flutter are thin local integration/demo clients and are not the maintainer's primary deliverables. | **APPROVED** by the maintainer 2026-10-17. The first authorized M1b implementation slice is M1b.1, a small SQLite/Alembic persistence foundation (merged in PR #9, `661876c`). | This is an execution-priority/resequencing decision only. The originally planned M1a.3 thin React/Flutter integration is **deferred/resequenced, not cancelled and not completed**; client applications remain preserved product requirements and may be used by the team for local integration testing. The priority adjustment does not waive any research/data/clinical approval gate, does not authorize dataset acquisition or model training, does not change the `/v1` contract, and does not authorize unrelated product features. M1b.1 is limited to the persistence scope in PR #9; later endpoints remain contract-first. |

## D-046 — Original Gate DA proposal (historical; see ratification below)

**Current D-046 decision:** On 2026-10-21, the named human
maintainer authorized local read-only auditing of DA-A1, DA-A2,
DA-B1, and DA-B2. See the Human Ratification section below and
docs/research/gate-da/10_local_audit_authorization.md.

The proposal and pending statuses in the following table are
historical snapshots, not the current operational authorization.
The committed research/audit/gate_da_authorization.json remains
a PENDING regression-test template. Authorized local operations
must explicitly use the git-ignored manifest at
data/manifests/gate_da_authorization.local.json.

Gate PT remains closed. This decision does not permit model
training or claim supervisor approval.


Prepared 2026-10-21 for milestone **M2a** after PR #10 (`fb928bb`, Gate DA
dataset suitability & decision package). **This entry is a proposed governance
change and proposed dataset-access scope. It is NOT self-approved and becomes
effective ONLY after explicit human maintainer review and acceptance of the
M2a PR.**

| ID | Decision | Status | Approver / rationale |
|---|---|---|---|
| D-046 | **Maintainer-led Gate DA authorization workflow for local, read-only public benchmark dataset audits**, plus explicit proposed dataset access decisions (`DA-A1`, `DA-A2`, `DA-B1`, `DA-B2`) and a separately reviewable proposal for a future **Internal Exploratory Protocol** (`D-046-EP`). | **PROPOSED — PENDING HUMAN ACCEPTANCE** (awaiting human maintainer review and acceptance of the M2a PR; **no dataset is downloaded in M2a and no model fitting is authorized**). | **Maintainer-led workflow rules (1–7):** (1) The maintainer can explicitly authorize local, read-only audits of specified publicly accessible benchmark datasets after provenance and license verification. (2) Authorization must name exact datasets/files, purpose, responsible acquirer, environment (`E:\CardioAssist_AI_GitHub_Starter`, Windows local, Python 3.12), data-custody rules (`/data/` git-ignored, `git check-ignore` verified prior to acquisition, byte-identical originals, SHA-256 + download-day license snapshots, zero patient-level commits/uploads/prints), date, and audit reviewer. (3) This workflow is a **proposed change to existing approval governance** (P-2 / D-031) and becomes effective **only after explicit human maintainer review and acceptance of this PR**. (4) **Supervisor review is deferred to a later research-review stage; its absence is recorded honestly and no supervisor approval is asserted or implied.** (5) Final clinical, publication, novelty, or external-validation claims remain **prohibited** (`NOT MADE — prohibited`, P-5, D-010/D-025) until their actual evidence and review requirements are met. (6) Existing Gate PT (P-3 / D-032) requires supervisor sign-off and is **not** silently bypassed; a separately reviewable proposal (`D-046-EP`, below) documents how a future governance amendment could permit preliminary experiments under a frozen internal exploratory protocol clearly distinguished from supervisor-approved research. (7) **No model fitting, feature selection, hyperparameter tuning, performance evaluation, calibration, SHAP, or LIME is authorized in this PR.** Machine-enforced record: `research/audit/gate_da_authorization.json`. |

### D-046 Proposed Dataset Access Decisions (historical pending-status snapshot)

None of the access decisions below take effect until the human maintainer
explicitly approves the listed scope and populates the named sign-off fields
(`authorized_by`, `authorized_date`, `responsible_acquirer`, `audit_reviewer`,
`environment`) in `research/audit/gate_da_authorization.json`. **`DA-B1` and
`DA-B2` must never become training or external-validation datasets merely
because audit access is granted.**

| Access ID | Official Dataset & DOI | Exact Authorized Files (and Excluded Files) | Permitted Purpose & Hard Role Restrictions | Proposed Status |
|---|---|---|---|---|
| **DA-A1** | **UCI-412 Z-Alizadeh Sani** (`https://archive.ics.uci.edu/dataset/412/z+alizadeh+sani`, DOI `10.24432/C5Q31T`, CC BY 4.0) | `Z-Alizadeh sani dataset.xlsx` under `data/raw/uci-412/` | Local read-only audit of workbook sheets, `Cath` target labels (`CAD` vs `Normal`), columns, data types, 54/55/56 feature-count discrepancy, missingness, within-cohort duplicates, H-01 threshold wording (`>=50%`), and L-08 pre-angiography feature availability timing. **No model fitting authorized.** | **PENDING HUMAN ACCEPTANCE** |
| **DA-A2** | **UCI-45 Heart Disease — four cohorts, raw and processed files + official documentation** (`https://archive.ics.uci.edu/dataset/45/heart+disease`, DOI `10.24432/C52P4X`, CC BY 4.0) | Under `data/raw/uci-45/`: Processed 14-column files: `processed.cleveland.data`, `processed.hungarian.data`, `processed.switzerland.data`, `processed.va.data`. Raw 76-attribute files: `cleveland.data`, `hungarian.data`, `switzerland.data`, `long-beach-va.data`. Official documentation: `heart-disease.names` (exactly as defined in PR #10 / `docs/research/gate-da/04_gate_da_approval_packet.md` §1.1). **Explicitly excluded:** `new.data`, `reprocessed.hungarian.data`, `processed.long-beach-va.data`. | Local read-only audit of raw 76-attribute and processed 14-column files separately across all four cohorts; confirmation of `processed.cleveland.data` conventional 14-column benchmark schema and raw/processed roles; missingness (`-9.0` vs `?`), invalid codings, suspicious values (e.g. `chol=0`); within/cross-cohort duplicate screening; L-01/L-02/L-06/L-07 feature availability/leakage review; and H-01/H-02 target verification (`>50%` wording and `0` vs `1–4` binarization). **No model fitting authorized.** | **PENDING HUMAN ACCEPTANCE** |
| **DA-B1** | **UCI-411 Extension of Z-Alizadeh Sani** (`https://archive.ics.uci.edu/dataset/411/extention+of+z+alizadeh+sani`, DOI `10.24432/C5461K`, CC BY 4.0) | `extention of Z-Alizadeh sani dataset.xlsx` under `data/raw/uci-411/` | **Audit-only and NEVER an independent cohort.** Sole purpose: confirm same-cohort provenance with DA-A1 (UCI-412), evaluate 1-to-1 row correspondence and feature superset against DA-A1, and verify L-03 leakage rules (`LAD`, `LCX`, `RCA`, `Cath`). **Must never become a training or external-validation dataset or additive sample size (`n=606`) merely because audit access is granted.** | **PENDING HUMAN ACCEPTANCE** |
| **DA-B2** | **UCI-145 Statlog (Heart)** (`https://archive.ics.uci.edu/dataset/145/statlog+heart`, DOI `10.24432/C57303`, CC BY 4.0) | `heart.dat` (and optional official companion doc `heart.doc` if present) under `data/raw/uci-145/` | **Audit-only for duplicate/overlap investigation** against DA-A2 Cleveland (`L-05`). **Must never become a training or external-validation dataset merely because audit access is granted.** | **PENDING HUMAN ACCEPTANCE** |

### Separately Reviewable Proposal: Internal Exploratory Protocol (`D-046-EP` — NOT Approved in This PR)

- **Why documented now:** The existing Gate PT (`P-3` / `D-032`) requires
  academic supervisor sign-off on a frozen pre-training protocol after the
  Gate DA read-only audit. To prevent silent gate-skipping while documenting a
  transparent path if supervisor review remains deferred after the M2 read-only
  audit completes, `D-046-EP` is recorded as a **separately reviewable
  proposal** (detailed in `docs/research/gate-da/05_gate_pt_methodology_outline_NOT_APPROVED.md` §11).
- **Proposed scope if later adopted via a separate governance amendment:**
  Only **after** (a) the M2 local read-only dataset audit report is completed
  and reviewed on GitHub, and (b) a **separate, explicit governance amendment
  PR** freezes a timestamped protocol and authorizes `D-046-EP`, the team could
  run preliminary internal experiments strictly labeled
  `INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED`.
- **Hard boundaries:** `D-046-EP` is **PROPOSED — NOT APPROVED** in M2a. It
  does **not** bypass or close `P-3` (Gate PT supervisor sign-off remains
  mandatory before any supervisor-approved research, publication, novelty,
  external-validation, or clinical claim), and **no model fitting is
  authorized in this PR**.

## D-046 — Human Ratification of Local Read-Only Audit

- **Decision date:** 2026-10-21
- **Decision status:** APPROVED FOR LOCAL READ-ONLY AUDIT ONLY
- **Human authorizer:** Muhammed Fathi
- **Responsible acquirer and audit reviewer:** Muhammed Fathi
- **Authorized dataset IDs:** DA-A1, DA-A2, DA-B1, DA-B2
- **Approved file inventory:** docs/research/gate-da/10_local_audit_authorization.md
- **Operational authorization manifest:** data/manifests/gate_da_authorization.local.json (git-ignored, local only)

The named maintainer explicitly confirmed authorization using
AUTHORIZE-READ-ONLY-4 and populated the required dataset-specific
authorization fields. This decision supersedes the pending state of
the original D-046 proposal for the listed read-only audit scope.

DA-A1 and DA-A2 are approved for local dataset suitability auditing.
DA-B1 is restricted to UCI-411/412 correspondence and leakage auditing.
DA-B2 is restricted to Statlog/Cleveland overlap investigation.

Acquisition is limited to the authorized files from official UCI
sources, subject to download-day provenance, license verification,
local-only custody, and byte-identical original preservation.

This ratification does NOT authorize model fitting, feature selection,
hyperparameter tuning, performance evaluation, calibration, SHAP/LIME,
clinical claims, or external validation.

Supervisor approval is NOT claimed. Gate PT (P-3) remains closed.
D-046-EP remains a separate, unapproved exploratory protocol proposal.

The committed research/audit/gate_da_authorization.json remains the
pending baseline template for regression tests. Real-data operations
must explicitly use the local authorization manifest via --auth-manifest.

---
## Governance gates — Gate DA audit scope authorized; remaining approvals pending

The following were **not** approved by the Phase 0 merge and are **not**
approved by the baseline above. Each requires its own explicit human
sign-off before the dependent work starts.

| # | Pending approval | Status | Gate / approver |
|---|---|---|---|
| P-1 | **Final scientific target and model evaluation protocol** | PENDING | Research lead + supervisor (D-006); protocol frozen at Gate PT (Phase 0 §R2-5.1, D-024/D-032) |
| P-2 | **Individual dataset acquisition authorization (Gate DA)** | APPROVED FOR D-046 LOCAL READ-ONLY AUDIT SCOPE ONLY | Named human data-access authorization listing the exact datasets (D-031, Phase 0 §R2-5.1); local-only acquisition into out-of-git storage, read-only audit, no fitting/selection/tuning/evaluation; no download before it |
| P-3 | **Supervisor approval of the frozen pre-training protocol (Gate PT)** | PENDING | Supervisor sign-off after the Gate DA read-only audit, before any model fitting, feature selection, hyperparameter tuning, or performance evaluation (D-032, Phase 0 §F-3) |
| P-4 | **Clinician approval of medical explanation and safety wording** | PENDING | Named clinician reviewer (D-016/D-026); conservative-copy fallback until then; no alert thresholds or treatment-recommendation language (Phase 0 §2.1, §R2-2.1) |
| P-5 | **Any claims of external validation or clinical readiness** | NOT MADE — prohibited | Requires external validation completed under the frozen protocol; governed by the `validation_status` lifecycle and serving policy (D-033, Phase 0 §R2-5.9/§R2-6.4) and the claims discipline (§R2-5.9); internal-only models are served and labelled strictly as such |
| P-6 | **Real wearable integrations and access-dependent features** | PENDING | Named device owner, developer-account resolution at $0, and vendor approvals per Phase 0 §10 (D-019); simulated adapter only until then; wearable data never feeds CAD inference (D-039) |

## D-047 — Proposed maintainer-authorized INTERNAL exploratory experiment (NOT APPROVED)

**Proposed date:** 2026-10-23; **status:** `PENDING_EXPLICIT_HUMAN_RATIFICATION`; **supersedes no prior P-3 supervisor gate.**

The team requested a **self-executed, documented preliminary comparison before supervisor review**. This was contemplated by `D-046-EP` but the D-046 read-only audit authorization explicitly did **not** authorize fitting. A **separate governance PR** now proposes activating `D-046-EP` for one narrow experiment under a human maintainer's own research responsibility:

- **In scope only after ratification:** privately run internal *exploratory* model development/comparison on the previously locally audited **processed UCI-45 Cleveland** 303-record public benchmark; fixed source `num=0` vs `1..4` binary label, five prespecified historical fields, bounded dummy / L2 LR / constrained RF nested-CV procedure, local-only model/score custody and reproducible report.
- **Evidence prerequisite:** D-046 ratified local audit; data-level report(s) merged. Unresolved warnings or harmonization questions remain OPEN and **exclude other cohorts**; they are not silently signed off.
- **Human activation condition:** an **explicit maintainer review comment** `AUTHORIZE-D047-INTERNAL-CLEVELAND` on the separate PR **AND** its human-approved merge, plus locally signed ignored authorization manifest binding the adopted protocol commit, actual source hash and allowed tasks. No agent may record human approval itself.
- **Science / product boundary:** every internal output marked exactly `INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED`. P-1/P-3 stay PENDING/CLOSED for **formal supervisor-approved research**; no patient-facing use, clinical recommendation, published accuracy/novelty claim, medical outcome guarantee, inferred supervisor approval or independently validated result. Distinguish this narrow exploratory exception from the old P-3 requirement for formal research.
- **Data boundary:** Existing D-046 audit permission **remains unchanged** and cannot be relabeled as training permission. D-047 is separate; it may authorize local research-model fitting only after human ratification and guarded preflight. `DA-B1` UCI-411 and `DA-B2` Statlog remain audit-only. UCI-412 and all other UCI-45 sites are excluded from this first experiment, no pooling or external validation claim.
- **Approved-method scope (if accepted):** [first internal experiment protocol](research/gate-pt/02_d047_internal_exploratory_cleveland_PROTOCOL_PROPOSED.md). Require a version-stamped frozen protocol SHA before data-fitting; future revisions after first fitting must be logged as exploratory amendments, never silently modified to improve results.
- **Result delivery:** produce a full internal transparent report and check the methods against TRIPOD+AI/PROBAST+AI before eventual presentation to the supervisor. No automatic promotion of internal results to formal clinical/scientific approval.

**Status of D-047 on this proposed PR: NOT APPROVED; no local manifest or actual human approval recorded.** No training permitted until the listed conditions are met. This section records only the proposed amendment; changing this text later requires a named human decision.

---

## D-048 — Proposed M3a UCI-412 source-specific research benchmark (PROPOSED; NOT AUTHORIZED)

**Proposed date:** 2026-10-24; **status:** `PROPOSED_NOT_AUTHORIZED`; **supersedes no prior decision and changes no existing gate status.**

A separate governance proposal to add a **single-dataset, source-specific** internal research benchmark on **`DA-A1` UCI-412** (*Z-Alizadeh Sani*, 303 participants). The implementation (synthetic-only code and tests) exists on its own PR; **nothing here authorizes a real-data run today**.

- **Relationship to D-046/D-047 — no new permission is inherited.** The D-046 ratification authorizes *read-only audit* of `DA-A1` and explicitly **does not** authorize model fitting. D-047's internal exploratory exception covers **only** `DA-A2` processed Cleveland. D-048 is a third, separate scope; neither earlier decision may be relabeled to cover it.
- **Scope if ratified:** one bounded internal exploratory benchmark on the UCI-412 workbook, using the prespecified **Basic Clinical Input Panel** (`uci412_basic_clinical_v1`, 16 ordered source columns → 16 encoded parameters), repeated stratified nested CV, prevalence baseline / bounded L2 logistic regression / constrained random forest only, participant-level bootstrap uncertainty qualified as conditional on fixed folds, and a label-permutation negative control. Everything is local, $0, CPU-only.
- **Scientific reading (binding on every output):** the label is **cross-sectional angiography-referenced CAD presence** at a ≥50% stenosis threshold — never future-event risk, never a risk score, never a horizon. UCI-412 and UCI-411 are **the same 303 participants** and can never be treated as independent datasets, pooled, or used to validate each other. The dataset's own ≥50% versus UCI-45's >50% threshold distinction **remains unresolved** and must not be silently reconciled.
- **Data boundary:** no pooling with Cleveland/Hungary/VA/Switzerland, no external validation, no patient-level output in Git, CI, chat, or any report. Angiography-derived fields (`Cath`, `LAD`, `LCX`, `RCA`), identifiers, post-outcome fields and outcome-adjacent echocardiographic timing remain excluded; the resting-ECG, expanded-clinical and laboratory panels stay **registered but blocked** until a definition/timing basis is established.
- **Human activation condition (all three required):** (1) an explicit maintainer review comment `AUTHORIZE-M3A-UCI412-INTERNAL-RESEARCH` on the separately reviewed governance PR; (2) that PR's human-approved merge; (3) a locally signed, hash-bound, Git-ignored authorization manifest at `data/manifests/uci412_internal_research_authorization.local.json` binding this proposal, the protocol, the feature dictionary, the source SHA-256/byte size and the permitted operations. The checked-in template authorizes nothing and is rejected by the code.
- **Pre-existing gap that blocks even a compliant local run today:** the checked-in `research/audit/gate_da_authorization.json` is still `PENDING_HUMAN_ACCEPTANCE` with null sign-off fields, so the local D-046 `DA-A1` chain this proposal depends on is not satisfied in-repo either. D-048 records that dependency; it does not cure it.
- **Evidence boundary:** every output is marked exactly `INTERNAL_EXPLORATORY_NOT_SUPERVISOR_APPROVED`; no supervisor, ethics or institutional approval is claimed; no clinical, deployment, novelty or publication claim follows. Synthetic test results are software evidence, **not** CAD performance evidence. **Gate PT P-3 remains CLOSED.**

**Status on this PR: PROPOSED; no authorization manifest, human signature, or real-data result exists.** Changing this section, or the plan/dictionary it references, requires a new named human decision.


---

## D-049 — Bounded offline diagnostic inference scope (ratified at `G2` for `I2`; `G3` re-baseline PROPOSED; NOT ACTIVATED)

**Originating proposal:** 2026-10-27 (PR #60). **Historical ratification:** the
scope enumerated below was ratified by the repository owner on 2026-10-27 in PR
#60 (exact comment
`RATIFY-BOUNDED-OFFLINE-DIAGNOSTIC-INFERENCE-SCOPE`,
<https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/60#issuecomment-6442269752>,
posted 2026-10-27T12:48:25Z; PR merged 12:48:38Z), producing governance baseline
`G2 = 44f06091602f66078726fcc3b62b6ee1305abd83`. **Current status of the `G3`
re-baseline recorded here:** `PROPOSED_NOT_RATIFIED` — awaiting a **NEW** explicit
owner ratification of this revised text on a new governance PR. **Activation
status:** `NOT_ACTIVATED`; no activation revision exists and **no real-bundle
diagnostic inference has ever been executed**. This revision supersedes no prior
decision and changes no existing gate status. Details and exact bindings:
[Gate PT doc 18](research/gate-pt/18_bounded_offline_diagnostic_inference_scope.md);
security review and gated Windows procedure:
[Gate PT doc 19](research/gate-pt/19_offline_diagnostic_inference_security_review_and_runbook.md).

**Three states that must not be conflated:**

1. **Historical scope decision — RATIFIED (`G2`, PR #60).** The owner really did
   ratify the operation in §"Proposed single new operation" for the `G2`
   document text, bound to approved implementation revision
   `I2 = 40b544be79acc9099e565a0ede183e9b376a238f`. This is a real prior decision
   and is recorded as such, with its evidence link above.
2. **Test repair — MERGED (`I3`, PR #62).** Merge commit
   `I3 = 87bccd6d3ef2331f1e2b2ba8905f34366734538d`. `G2..I3` is **tests only**
   (six files under `tests/experiments/`); production runtime code, the frozen
   training registry, the synthetic-only CLI, workflows, examples and the
   diagnostic registry are unchanged, and
   `RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES` is still `{}` at `I3`. `I3` is the new
   approved implementation/test baseline.
3. **`G3` re-baseline — PROPOSED (this PR).** Docs only. It proposes binding the
   same narrow operation to `I3` and to this document's own bytes at the future
   `G3` merge. **It is not ratified by PR #60's comment**; that comment approved
   an earlier revision of the text and the `I2` baseline. Nothing in state 1 or 2
   activates anything, and no `A3` exists.

- **Why:** `AI2-OPERATIONAL-SCOPE-001` (ratified at `G`, activated at `A`)
  authorized exactly `persistent_model_packaging` and
  `patient_level_shap_background`. Its §9 prohibits any `ResearchCadPredictor` /
  CLI / serving call on the accepted real bundle, including with synthetic
  inputs. A training authorization is not an inference authorization; the
  general `python -m ai` CLI stays synthetic-only.
- **Exact accepted artifact (unchanged by this re-baseline):**
  `cai_real_cleveland_d047_20261027T070610Z_deffa577`; maintainer-computed
  `manifest.json` SHA-256
  `089f931be27be67606b9d2622beea54208976f1743a70909029619f50a6e5d4a`.
  Acceptance-marker presence, quarantine-marker absence, producer authentication
  and trusted local verification are maintainer-reported, not Arena-verified.
  No bundle, key, or dataset is touched by this PR.
- **Proposed single new operation (scope identical in `G2` and `G3`):**
  `offline_synthetic_input_diagnostic_inference` on the ONE accepted bundle,
  using explicitly fabricated synthetic five-field records over
  `da_a2_resting_v1` (`age`, `sex`, `cp`, `trestbps`, `restecg`), reusing
  existing validation, calibration, exact SHAP and registered LIME quality
  checks. Maximum eight records per invocation; private Windows-local offline
  `RESEARCH_ONLY` execution only. No patient inputs, retraining, tuning,
  recalibration, regeneration, bundle mutation, serving, telemetry, upload,
  bundle write, or new clinical/performance claim.
- **Independent gate:** a separate trusted registry
  (`ai/diagnostic_scope.py::RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES`), EMPTY at
  `I3` and required to remain EMPTY at `G3`, plus a separate guarded entry point.
  Until a **fresh** ratification (`G3`) and a separate registry-only activation
  (`A3`) exist, all real-bundle inference fails closed with
  `diagnostic_scope_not_ratified`. Acceptance markers, HMAC authentication, the
  earlier training authorization, and the PR #60 comment cannot substitute.
- **New revision sequence, no circular SHA:** `I3` is the approved
  implementation/test revision (`approved_implementation_commit_sha`), `G3` is
  the immutable governance baseline whose document bytes are bound
  (`governance_baseline_commit_sha` + `frozen_governance_document_sha256`), and
  `A3` is the registry-only activation revision (`activation_merge_commit_sha`,
  present ONLY in the ignored local operator authorization). These are names for
  a revision sequence, **not new schema fields**: the v1.1 validator, its
  interface version and its field names are unchanged. A commit cannot contain
  its own SHA-1 in tracked content, so the tracked registry at `A3` would contain
  ONLY previously known values (`I3`, `G3`, the recomputed governance-document
  SHA-256 at `G3`, the exact operation/bundle identity and the
  maintainer-supplied `manifest.json` SHA-256). `A3` is recorded only in the
  ignored local operator authorization after its merge and is checked at runtime
  against independently resolved `git rev-parse HEAD`. Neither `G3` nor `A3` is
  precomputed anywhere, and doc 18's own digest is never inserted into doc 18.
- **Two-step human activation:** (1) a **new** exact owner ratification comment
  on the new governance PR, after reviewing its final content, and a human merge
  producing the actual `G3`; (2) a separate future registry-only PR based on
  `G3` producing `A3`, whose `G3..A3` diff modifies only
  `ai/diagnostic_scope.py::RATIFIED_DIAGNOSTIC_INFERENCE_SCOPES` (empty ->
  exactly one literal record). Runtime additionally requires `I3` ancestry of
  `G3` with documentation-only changes, `G3` ancestry of HEAD, a clean tracked
  worktree, strict masked-source equality of the registry file, and equality of
  the committed literal registry with the in-process registry. Each invocation
  additionally needs a private local operator authorization document (an
  **attestation**, not a cryptographic signature) and the exact operator
  confirmation phrase. Code cannot verify human authority or GitHub evidence. A
  genuine committed `I3 -> G3 -> A3` pytest history proves the procedure is
  realizable; no registry state is invented by monkeypatch alone.
- **Required human decision and exact handoff:** only the repository maintainer
  may post `RATIFY-BOUNDED-OFFLINE-DIAGNOSTIC-INFERENCE-SCOPE` on this new
  governance PR after reviewing its exact, final scope, then merge it. The agent
  must not post that comment, self-ratify, or merge. The PR #60 comment
  (<https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/60#issuecomment-6442269752>)
  is historical evidence of the earlier decision only and must not be reused. If
  substantive changes follow the new comment, review and renewed confirmation of
  the revised content are required before merge. Only after the merge: read the
  actual full `G3` merge SHA from GitHub, confirm `I3..G3` is docs-only and the
  registry is still `{}`, then compute the SHA-256 of doc 18's **raw committed
  bytes at `G3`** with no newline/encoding conversion. The historical digest of
  the `G2` bytes must **not** be reused. The activation record must bind `I3`,
  `G3`, this governance PR's number, the exact document hash, the owner identity
  and exact comment, and the unchanged artifact identity. The `A3` PR must start
  from `G3`, and runtime must use a clean checkout of exactly `A3`. PR #61's
  `I2`/`G2` activation record is superseded for this route and must not be
  merged.
- **Status on this PR:** the historical ratification and the `I3` test repair are
  recorded facts; the `G3` binding is PROPOSED only. This PR contains no new
  ratification comment, no activation registry entry, no local operator
  authorization, no human signature, no real bundle action, and no real
  inference. All test evidence is synthetic. Gate PT P-1 remains PENDING and P-3
  CLOSED; no supervisor, ethics, institutional, clinical, or external-validation
  approval is claimed, and the broader multi-dataset strategy is untouched and
  outside this PR.

---

## Standing rules

- Status vocabulary: **CONFIRMED** (project team), **APPROVED** (maintainer,
  this baseline), **PROPOSED**, **OPEN**, **PENDING** (awaiting a named
  human gate), **NOT MADE — prohibited** (no such claim exists anywhere in
  project materials and none may be added).
- Only the explicit D-046 human ratification authorizes local acquisition and read-only audit of its named official UCI files.
  Model training, deployment, clinical claims, novelty claims, and external-validation claims remain unauthorized.
- Merging any PR (including the Phase 0 report) never auto-approves a
  pending item; each P-item closes only through its own recorded human
  approval.
- Phase 1 proceeds milestone-by-milestone (M1a → M1b → M2 → M3 → M4 per
  Phase 0 §R2-7.6 / §F-5), each as its own scoped, human-reviewed PR.

---

## D-RH04-V2-01 — RH-04 V2 transition ratified (Act C)

- **Decision date:** 2026-11-28.
- **Status:** Owner-ratified; recorded on the delivery branch for review. V2-01 is the only gate addressed by this decision. The entry is not yet effective on main; no other gate is closed by it.
- **Owner authorization:** explicit instruction in chat, transcribed below by the reviewer; not a manufactured GitHub signature or cryptographic attestation.
- **Independent engineering reviewer:** ChatGPT, expressly designated by the owner. Arena supplied independent candidate-verification and isolated rollback reports. Neither constitutes clinical, supervisor, institutional or ethics approval.
- **Controlling decision:** [RH-04 Issue #132 acceptance decision](rh04-issue132-acceptance-decision.md), §7, as amended by [CAI-RH04-AMEND-v3](research/next_phase/RH04_V2_ARCHITECTURE_AMENDMENT_PACKET_2026_11_21.md), [CAI-RH04-AMEND-v4](research/next_phase/RH04_V2_AMENDMENT_V4_RECONCILIATION_2026_11_24.md) and the owner-adopted [V2-06 external declaration v1](research/next_phase/RH04_V2_06_EXTERNAL_DECLARATION_V1.md).
- **Accepted evidence HEAD (not this record's future commit):** `801acbd3102c1cc9ec67aa006754d170cd715d98`; frozen base `c6a6bdee46a552a2b0d705a723c862ff8a95be4d`; [PR #141](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/141). The evidence revision comprises 32 commits and 69 changed files relative to the frozen base. This append-only decision record is a subsequent documentation change; no inference that historical run IDs certify a new SHA.

### Owner instruction (verbatim)

> أوافق على Act C واعتماد الانتقال المعماري من RH-04 V1 إلى V2 وفق CAI-RH04-AMEND-v3 وv4، والتصحيح التوثيقي الخارجي المعتمد لـV2-06، والأدلة المقبولة في Act B على HEAD 801acbd3102c1cc9ec67aa006754d170cd715d98.
>
> أعتمد ChatGPT كمراجع هندسي مستقل لهذا القرار، وأصرح بإضافة القرار D-RH04-V2-01 إلى docs/DECISIONS.md، مع توثيق المنهجية الفعلية للمعايرة، وآلية التحقق من البصمات، وحدود الأدلة، والـRollback، والحفاظ على جميع القرارات السابقة.
>
> يقتصر الاعتماد على قابلية إعادة الإنتاج البحثية للبيانات الاصطناعية، ولا يشمل إنهاء إلزامية V1 أو Merge أو اعتمادًا سريريًا أو تشغيل النماذج على المرضى أو إغلاق أي Gate أخرى.

### Ratified architecture and scientific boundaries

Act A adopts the two lanes and the v4 validity/equality separation; Act B accepts the scoped evidence, including its recorded limitations; Act C records the owner's V1-to-V2 architecture decision. In case of inconsistent historical proposal wording, use these explicit owner-adopted provisions and the external declaration for the research semantics. Historical proposal texts and prior decisions are preserved.

- **Lane A (V2-02, V2-04a):** registered synthetic training, selection, out-of-fold calibration and regeneration. Require source provenance, actual digested parameter identity, reconstructable lineage, independent convergence evidence, same case/status/field structure, and measured archived-parameter and fresh/frozen response differences. Cross-environment parameter bit-identity is not required; valid converged differences are findings, never a new tolerance. Failed training, missing or non-evaluable criterion, invalid lineage and malformed/nonfinite output remain failures. Host-independent fitting/convergence is not asserted. The retained P0 obligations are not erased by the amendment; their individual engineering disposition must be substantiated, not inferred from this owner record.
- **Lane B (V2-03, V2-04b):** no fit, no calibration optimization, no fallback to regeneration. Exact type-and-value replay of all 29 registered cases against the admitted immutable reference, with no numeric tolerance; at least three resident Linux dispatch classes on each of Python 3.11 and 3.12 plus native Windows. Exactness in measured environments is evidence, not a universal mathematical guarantee or proof of equivalence to scikit-learn. Re-measure new environments. Neither lane substitutes for the other; D-V2-7 is not ratified here.

### Registered numerical methodology (V2-02 / V2-06)

The nonconstant OOF calibration path at the evidence revision uses `scipy_lbfgsb` (L-BFGS-B), with mean binary logistic loss plus `0.5 * lambda * (a^2 + (b-1)^2)`, default lambda 1e-3, intercept bounds [-15,15], slope bounds [0.01,15], x0=(0,1), analytic gradient and SciPy 1.15.3 library-default stopping settings. No explicit tol/gtol/ftol/options is passed by the calibrator. The evidence evaluator records the optimizer result and uses its declared projected-gradient criterion (1e-5 in the existing evidence path); this is not an explicit argument to minimize and not a replay tolerance. The model-fit evidence uses the declared estimator criterion (1e-4 in the existing Lane A evaluator) with profile-specific objective/intercept treatment. Model and calibration optimization are separate; random forest has no iterative gradient criterion. Require recorded objective, parameters, termination/status, iterations, independent optimality evaluation and failure classification, not merely the serialized FITTED label or an isolated oracle. Independent decimal evaluation is not an independent fit. No new tolerance, optimizer, feature set, dataset or model family is authorized.

For input z, calibrated log-odds is the affine eta_cal=a+b*z; calibrated research score is expit(eta_cal), **not** affine. For the linear route z is exact raw log-odds; for the tree route it is the logit of raw probability clipped to [1e-6,1-1e-6]. The calibrator is fitted on the development OOF predictions and labels, not directly on the design matrix; the constant/dummy path is distinct from fitted two-parameter calibration. Exploratory score threshold 0.5 is not a clinical threshold or a log-odds cut. Neither score denotes validated patient probability or future-event risk.

The historical source in the external declaration predates F-CAL-01. At the accepted evidence HEAD the correction rejects unsuccessful/malformed optimization results and invalid fitted parameters instead of substituting defaults; 41 new tests and independently reported 82/82 bit-identical successful-path results, with pinned numerical libraries. Stored archive fit-status is still not independent convergence evidence, nor does the manifest make the archive's solver provenance intrinsic. Instrumented refit evidence does not retrospectively certify the archived fit or every separate regeneration call. The external declaration is carried forward by this exact-evidence binding; no hashed runtime string, model card, archive or manifest bytes are rewritten. Inline production metadata changes and RH-07 model-card work remain separate.

### Reference admission and identities (V2-03)

The adopted reference is the two raw archive bodies and trusted manifest under `research/intake/fixtures/rh04_v2_portable/`, with enforced raw archive SHA-256 pins and distinct semantic artifact identities. The manifest's canonical identity is compiled into the reviewed admission code, not a self-referential raw pin inside itself. The manifest records solver provenance externally (`solver_bound_in_archive: false`); deserialized unknown provenance is not relabelled as known. These are integrity/trust-anchor checks, not an external signature or certification of a clinical model.

| Identity | SHA-256 |
| --- | --- |
| DA-A1 raw archive | `58a50a14ca83e9f3e34f95c8bd809594b798695e3c2d6594193ce3c8179dfc77` |
| DA-A2 raw archive | `a77182ad3e098374dabd306e427affa4d715fc6a4c005eee5509a90d365a0c25` |
| Canonical trusted manifest anchor | `293c6e3f6e9aa74f1119a52b56d97af8774a76e90b162a41a222a46a07a63c70` |
| Fixed Lane B aggregate | `891d9e3b2a332c6efc251d97fee25ed46a627ed25b2a089594057b4c9896cdc8` |
| External declaration raw bytes | `d3d78794dff1a26b6ebe310ccb9cfeaba6c708baa416d8e620cf436cc1c6e92e` |

Use the complete per-case/per-field delta mapping, preserve type distinctions and the frozen V1 bytes and existing narrow exception. V3 replaces the original requirement to certify a new `PACK_SHA256_V2` identity with the admitted reference mechanism above; an earlier `offline_io.v2.json` file does exist in the evidence tree (blob dd476c31f0b14f95743313ce57749ed7a547b5c9), so the amendment must not be read as a claim of its physical absence. Do not infer that candidate file is the ratified Lane B reference. Preserve the existing negative tests and fail-closed security obligations V2-07/08; no new numeric tolerance or dropped/coerced leaf. Artifact-byte identity is not implied by numerical closeness.

### Accepted evidence and limitations (Act B)

- [Act A](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/141#issuecomment-7233603063); [F-CAL-01 independent review](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/141#issuecomment-7235763822); [publication](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/141#issuecomment-7235938251); [hosted and Windows audit](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/141#issuecomment-7236492250); [rollback reconciliation](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/141#issuecomment-7237083752); [Act B](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/141#issuecomment-7237675594).
- [Synthetic CI 46121171999](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/46121171999): 2268 passed/2 skipped plus 396 UCI-412 tests on each of Linux Python 3.11 and 3.12; structural diagnostic exact replay twice. Contract 46121171996, audit 46121172015 and mock backend 46121171994 passed. [Dual-run 46121172024](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/46121172024) remains RED: each of 8 forced jobs has V1 456 passed/1 failed, while other mandatory stages and the 2 host jobs passed. No suppression, no rerun-to-green.
- Reviewer audited 10 hosted ZIPs, 60 sealed payloads, 18 valid hosted Lane A reports, and recorded 10 exact Lane B replays; pure resident Haswell, Nehalem and Sandybridge on each Python minor (mixed classes supplementary). Owner-local native Windows 3.11.9 pure Haswell: 45 PASS/1 FINDING/0 FAIL, exit 0; V1 457 passed, selected 67, hardening 73, Lane A valid, Lane B exact. ZIP SHA-256 `93726d7f32d3841e8bec74180df8200384332119697e711346373ff799773361`. Total recorded Lane B 11/11 exact, 29 cases each, no recorded fitting; Windows DA-A2 coefficient difference 2.7755575615628914e-17 is diagnostic only. These are independent byte-integrity/log/JSON consistency checks and owner-local measurements, not independently signed runs or re-execution of every experiment/raw response.
- Rollback report SHA-256 `9d0ee481d86841e0df3588ff0f3c86ba3d4a41e6c86d2d928878e75eeb41ff1a`: Arena reports isolated squash a192a7f586bcf955f8f30a401e55a87a98446135 with delivery tree 5137fc2537db7a03f0ec1494b569095653e992f9; single revert df89dc2478a974059c5794c43a5172580b069798 restores frozen base tree 3106bece1fe0e7c09ff0635d66cc883d1ecca33e. Native restored V1 457 passed, forced Prescott/Nehalem/Sandybridge/Haswell still fail golden replay. Remote identity/composition and restored calibration blob cross-checked; local scratch objects and execution are report-derived. Arena local reports use pytest 8.3.4 rather than declared 9.0.3; this is disclosed, not described as a fully pinned rollback. No remote rollback executed.
- V2-10 evidence is bounded to the complete squash unit at the accepted evidence revision against the frozen base, not universal V1 green or a revert of the final tip. A future integration must preserve this boundary and verify the actual delivery tree and revertability, including subsequent governance changes, or separately re-certify a different strategy. This decision records the limitation and does not itself close V2-10.

### Effect and exclusions

This entry records the Act C/V2-01 ratification on a draft branch, with main effectiveness pending human review and merge. It is not formal closure of other V2 gates. V1 remains mandatory in the dual-run window (V2-05). A separate Act D must explicitly disclose the loss of fresh-refit exactness as a required guarantee and authorize any retirement/gate policy transition; never mark the historical failure repaired. No merge, Issue #132 closure, V1 retirement, production inline wording change, registry activation, real-data acquisition or fitting, patient inference, clinical/model equivalence, RH-07 science, RH-08 release or D-047/M3a metric claim is authorized. Existing decisions, privacy/security rules, research-only synthetic scope and authorization boundaries remain unchanged. Issue #132 additionally requires accepted V2 integration, cross-environment evidence, explicit owner retirement and RH-07/RH-08 risk-register reconciliation. Historical evidence remains SHA-bound; later governance/implementation changes require proportionate exact-revision verification before acceptance.
