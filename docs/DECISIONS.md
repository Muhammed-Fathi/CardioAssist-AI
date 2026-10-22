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
