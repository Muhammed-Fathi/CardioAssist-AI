# 02 — Exhaustive Traceability / Feature Matrix

**Status:** PROPOSED inventory (documentation only), 2026-10-17.
Sources: `research/source_materials/project_presentation.pdf` (47 slides) +
`project_presentation_speaker_notes.md` (slide order), `docs/FEATURE_REGISTER.md`
(F01–F12), `docs/phase0/PHASE0_REVIEW_DRAFT.md` §2/§R2-3, `shared/contracts/`,
`backend/`, and the 2026-10-17 master-blueprint task (which adds lab-report
OCR/verification, administration and clinical-assistant rows — see §3).

**Preservation rule (D-042):** no intended feature is removed or silently
downgraded. Rows blocked by evidence, policy, hardware or approvals are
labelled with the *named* blocker and unblock condition.

## 1. Status taxonomy (used in every row)

| Tag | Meaning |
|---|---|
| **IMPLEMENTED + TESTED** | Real software in the repo today, covered by the 370-test suite (as of merge `6c2572c`) |
| **SYNTHETIC/MOCK** | Real plumbing producing deterministic **synthetic** results (mock CAD/XAI, mock registries) — **not** a trained AI, not clinical evidence |
| **PROPOSED** | Designed/decided but not built; scheduled in [03](03_MILESTONE_ROADMAP_AND_DEPENDENCIES.md) |
| **RESEARCH-GATED** | Blocked on Gate DA / Gate PT / dataset or protocol approvals (P-1…P-3) |
| **CLINICALLY-GATED** | Blocked on clinician/supervisor wording or safety review (P-4, D-016) |
| **ACCESS-GATED** | Blocked on hardware, developer accounts, vendor terms or controlled data (P-6, D-019) |
| **PROHIBITED** | Rejected as design input (Phase 0 §2.1); may not be implemented as described in the slides |

Milestone column: `DONE-M1a.x` (merged), `M1a.3`, `M1b`, `M2`, `M3`, `M4`,
`M5` (proposed extension bucket — needs explicit maintainer scope
authorization; see [03](03_MILESTONE_ROADMAP_AND_DEPENDENCIES.md) §4).

## 2. Required external reference inputs (not in the repository)

The maintainer has **approximately 14 planning/mockup images** (screen
mockups / planning artifacts). They are **not present in this repository**
(a full-tree image search returns zero image files), so they have **not been
inspected** by this blueprint. They are recorded as **required external
reference inputs**:

| ID | Input | Needed by | Used for | Status |
|---|---|---|---|---|
| EXT-01…EXT-14 | ~14 planning/mockup images (screens, flows) | M1a.3 UI scaffolding and M1b/M5 surface design | Verifying UI surfaces for F03/F04/F13–F17 (especially lab-upload/OCR screens, admin console, assistant panels), wording/layout intent | **REQUIRED — EXTERNAL; not yet supplied to the repo.** Until they are provided (e.g. attached to the milestone PR or committed under `docs/blueprint/reference/` with permission), all UI-surface rows below are derived from the speaker notes and the blueprint request only, and remain **[AS-RECORDED — UNVERIFIED]** for layout detail |

No blueprint row pretends these images were reviewed. When supplied, add a
per-image traceability note (image ID → feature IDs) rather than editing
history.

## 3. Register extension note (F13–F18)

`docs/FEATURE_REGISTER.md` holds F01–F12. Rows **F13–F18** below are
*proposed register extensions* taken from the 2026-10-17 master-blueprint
task (they also match capabilities implied by the external mockups). They are
**not** yet in the approved register; ratify them into
`docs/FEATURE_REGISTER.md` in a follow-up maintainer decision. They are
listed here so nothing in the requested vision is silently dropped.
F14/F15 (lab-report OCR and extraction verification) are **required
product-vision deliverables** — they are scheduled in the product track
(M5) subject to implementation-readiness and safety approvals; they are not
optional and not part of the research-prototype completion definition
(see [03](03_MILESTONE_ROADMAP_AND_DEPENDENCIES.md) §4).

## 4. Summary matrix

| ID | Capability | Slide evidence | Track | Status today | Milestone |
|---|---|---|---|---|---|
| F01 | CAD ML prediction & inference (tabular, T1 presence) | S22, S28–S31 | A | Contract + SYNTHETIC/MOCK implemented & tested; real model RESEARCH-GATED | mock DONE-M1a.1/2; real M3 |
| F02 | Per-prediction explainability (real SHAP/LIME) | S32–S34 | A | Synthetic SHAP-shaped offsets (MOCK); real TreeSHAP/LIME RESEARCH-GATED; live LIME deliberately unavailable (X-01) | mock DONE-M1a.1/2; real M3 |
| F03 | Clinician dashboard: patients, timelines, triage-style review | S40–S41 | A/B | PROPOSED (no frontend code exists) | M1a.3 thin screen; full M1b |
| F04 | Patient experience: Flutter app (measures, survey, lifestyle, offline) | S37–S39 | B | PROPOSED (no frontend code exists) | M1a.3 one screen; full M1b |
| F05 | Wearable adapters + monitoring (simulator-first, Health Connect later) | S15, S38–S39 | B | Simulated-source ingestion IMPLEMENTED + TESTED; real adapters ACCESS-GATED; wearable→CAD **PROHIBITED** (F-09 enforced) | sim DONE-M1a.1/2; real P-6 |
| F06 | Reassessment, follow-up, notifications & summaries | S31, S38, S41 | A/B | PROPOSED (validity rules designed, Phase 0 §R2-2.2); threshold alerts **PROHIBITED** | M1b |
| F07 | Events, audit logging, consent, data access | S26–S27, S31 | Platform | In-memory audit snapshots IMPLEMENTED + TESTED (test-only); durable audit/consent lifecycle PROPOSED | M1b |
| F08 | Interoperability / FHIR mapping & export | S25–S27, S36, S38–S39 | Platform | PROPOSED (thin FHIR-R4-shaped export only; "FHIR-native" slide claim downgraded) | M4 optional (D-020) |
| F09 | Extensible modular disease architecture | S20, S22–S23, S42–S43 | Platform | PROPOSED (CAD module boundary designed) | registry M1b/M4; second module post-M4 |
| F10 | Reproducible evaluation & research reporting | S28–S30, S43, S46 | A | PROPOSED protocol (Phase 0 §R2-5) — required research core | M2 → M3 → M4 |
| F11 | Authentication, roles/RBAC, access control | S26, S36 | Platform | PROPOSED (current backend is unauthenticated by design) | M1b |
| F12 | Versioned AI–backend API & integration tests | S25–S26, S31 | Platform | **IMPLEMENTED + TESTED** (OpenAPI, 30 fixtures/33 steps, 370 tests) | DONE-M1a.1/2 |
| F13 | Medical history, symptoms, surveys & clinical feature input | S38 (survey/symptom check), Track-A inputs | A/B | PROPOSED | M1b |
| F14 | Lab-report image/PDF upload & OCR extraction | Not in slides — blueprint request + external mockups | B | PROPOSED — **required product-vision deliverable** | M5 product track (authorization to schedule) |
| F15 | Extracted-field editing, provenance, confirmation & clinician verification | Not in slides — blueprint request + external mockups | B→A (gated) | PROPOSED — **required product-vision deliverable**; Track-A use only via the 05 §2.1 eligibility checklist | M5 product track (authorization to schedule) |
| F16 | Research-safe recommendations & clinical-assistant capabilities | S34/S38 contain *prohibited* variants; research-safe restatement | A/B | PROPOSED, heavily CLINICALLY-GATED | M5 product track (clinician-gated; scheduling authorization pending) |
| F17 | Administration (users, roles, registries, ops) | Implied S22/S42–S43 | Platform | PROPOSED | basic M1b; console M5 |
| F18 | Persistent database & deployment posture | S25–S27 (topology downgraded), task-locked SQLite→PG | Platform | Persistence PROPOSED (in-memory today); local-first deployment posture adopted | persistence M1b; hosting optional M4+ |

## 5. Feature detail blocks

Each block lists: status, dependencies, data entities, API requirements, UI
surfaces, local tests, scientific/safety gates, planned milestone. Entity
and endpoint names in **bold** are proposed (design in
[04](04_DATABASE_AND_API_INTEGRATION_DESIGN.md)); names in `code` exist
today.

---

### F01 — CAD ML prediction & inference

| Field | Content |
|---|---|
| Status | Wire contract + deterministic SYNTHETIC/MOCK inference IMPLEMENTED + TESTED (`POST /v1/predictions/cad-tabular`); real trained model **RESEARCH-GATED** (no dataset, no training, Gate DA/PT closed). Target = cross-sectional angiographic CAD **presence** (T1, provisional pending P-1). Never "30-day risk" (PROHIBITED claim). |
| Dependencies | F12 contract (done); P-1/D-006 target approval; D-007/P-2 dataset authorization (Gate DA); P-3 protocol freeze (Gate PT); F02 for explanations; F11 for submission auth (M1b+). |
| Data entities | **PredictionResult**, **ModelArtifact**, **ClinicalFeatureSet**, `feature_schema_id` (mock schemas exist: `mock_clinical_v1/v2`), **ModelRegistry** entry. |
| API requirements | `POST /v1/predictions/cad-tabular` (exists): `Idempotency-Key` required, 200 replay semantics, 400/409/422/503 envelope; deterministic output; provenance fields per response. Planned: prediction-history read API (M1b, contract change). |
| UI surfaces | Clinician record-detail prediction panel (target name + definition + provisional status, MOCK disclaimer, model/preprocessing/calibration/schema ids, validation_status, score label, missing values/warnings, audit_id, replay flag, read-only `pending_review`) — M1a.3 §2.4. Patient UI never shows Track-A scores. |
| Local tests | Contract tests (136) incl. F-01/F-01b/F-07/F-10/F-11/F-12 fixtures; HTTP tests: golden bodies, determinism, idempotent replay, 409 conflict, error catalogue (234 backend tests total today). Re-run unchanged against real model at M3 (IC-3). |
| Scientific/safety gates | P-1 target; Gate DA (P-2) → Gate PT (P-3); claims discipline §R2-5.9; no accuracy/risk % claims ever from mock; `validation_status` rendering rule (D-033); calibrated score is a benchmark-cohort score, never an absolute personal probability (§F-6). |
| Milestone | Mock: DONE-M1a.1/2 · Real model behind unchanged contract: **M3** · History/review integration: M1b/M4 |

### F02 — Per-prediction explainability (SHAP/LIME)

| Field | Content |
|---|---|
| Status | SYNTHETIC/MOCK SHAP-shaped offsets IMPLEMENTED + TESTED (sum-check on log-odds margin, fixture F-08; determinism F-07). **Real TreeSHAP/LIME is the research deliverable (RESEARCH-GATED, M3)** — the mock offsets are NOT computed SHAP and must never be presented as model explanations. Live LIME is deliberately unavailable: `mock_model_d_v0.1.0` returns 503 `model_unavailable` (X-01); the legacy F-11c fixture (illustrative fixed local R²) remains as a frozen contract artifact only. |
| Dependencies | F01; P-4 clinician interpretation review; explanation-stability protocol (§R2-5.7); LIME fidelity validation before any LIME UI (X-01). |
| Data entities | `explanation` response object (`method`, `scale: log_odds_margin`, `base_value`, `contributions[]`, note); future **ExplanationStabilityReport** (M3 research artifact). |
| API requirements | Explanation carried inside the prediction response (exists); no separate explanation endpoint. SHAP contributions never re-based onto probability scale (§R2-6.5). |
| UI surfaces | Clinician explanation panel: contributions rendered **separately on the log-odds scale**; never summed with the score, never "%", never causal/advice text; no LIME panel until real LIME + fidelity exist (M1a.3 §2.5). |
| Local tests | F-08 additivity sum-check; F-07 determinism; F-11/F-11b rendering labels; 503 LIME-only test (HTTP); client snapshot tests for rendering rules (M1a.3). |
| Scientific/safety gates | P-4 (wording/interpretation); §R2-6.5 binding scale rule; stability checks pre-registered — unstable explanations block attribution display; no "recommended action" attached to explanation tiles (PROHIBITED, Phase 0 §2.1). |
| Milestone | Mock: DONE-M1a.1/2 · Real SHAP/LIME + stability + fidelity: **M3** |

### F03 — Clinician dashboard (patients, longitudinal records, timelines, review)

| Field | Content |
|---|---|
| Status | PROPOSED (zero frontend code today). Design intent: patient list, record detail, Track-A review queue, explanation view, monitoring views, audit view (Phase 0 §R2-3/R2-7.3). Triage-*style* ordering only — the slide's risk-threshold triage (S41 "sorted by risk delta") is re-scoped to reviewer-managed queues; any threshold logic is PROHIBITED pending validation + clinician approval. |
| Dependencies | F12 (done) for the mock surface; F11 auth (M1b) for real roles; F01/F02 outputs; F13 inputs; read APIs for history (M1b contract change); EXT mockups (§2) for layout; P-4 for copy. |
| Data entities | **PatientProfile**, **PatientTimeline** (predictions + observations + review events), **ReviewQueue**, **ReviewAction**. |
| API requirements | M1a.3: prediction POST only (no read API yet — the thin screen renders the POST response). M1b: patient list/detail, timeline, review-action endpoints (contract review required; none exist in the approved contract). |
| UI surfaces | React/TS: dashboard list, record detail, review queue, explanation view, monitoring views, audit view (M1a.3 delivers exactly one thin synthetic-record form/action per `docs/M1A3_INTEGRATION_HANDOFF.md` §2). |
| Local tests | M1a.3: React component/snapshot tests (mandatory target/disclaimer/status copy, uncalibrated vs mock-calibrated rendering, missing values, replay, 409, 422 wearable rejection, 503). M1b: role-matrix tests, timeline consistency tests. |
| Scientific/safety gates | No PHI (demo/benchmark data only); snapshot-tested disclaimers; calibrated scores labelled benchmark-cohort (§F-6); no alert/treatment language; clinician copy review (P-4/D-016). |
| Milestone | M1a.3 thin screen · Full dashboard **M1b** |

### F04 — Patient experience (Flutter app)

| Field | Content |
|---|---|
| Status | PROPOSED (zero app code today). Core scope (D-042): onboarding/consent, health measures, baseline + reassessment surveys, lifestyle context, monitoring history, offline queue + sync, privacy/consent center, health-records export (S37–S39). Slide "daily risk pulse" / patient risk display is **PROHIBITED** (patients never see Track-A scores or personal risk %). |
| Dependencies | F12/F05 ingestion (done, mock); F11 auth (M1b); F13 surveys; F07 consent; batch sync endpoint (Q11, M1b); EXT mockups for screens; Android toolchain verification (Phase 0 §R2-7.4). |
| Data entities | **PatientProfile**, **MeasureEntry**, **SurveyResponse**, **ConsentRecord**, **OfflineOutboxEntry**. |
| API requirements | M1a.3: `POST /v1/monitoring/observations` with pseudonymous `patient_ref`, demo `consent_id`, explicit source. M1b: auth, profile, history reads, batch sync, consent endpoints. |
| UI surfaces | Flutter: one synthetic observation submission screen (M1a.3 §3); later: home/history, measures, survey, lifestyle, consent, export screens. |
| Local tests | M1a.3: Dart client/widget tests (JSON fields, 201 first/replay, preserved observation id, error paths, source/disclaimer labels, absence of CAD output). M1b: offline→sync test on emulator **and** one physical device (or recorded UNVERIFIED). |
| Scientific/safety gates | No real health records (synthetic only); consent recorded, not claimed verified; no CAD inference from monitoring; no risk display; P-4 for any symptom-safety content; iOS/store out of scope (D-019). |
| Milestone | M1a.3 one screen · Full app **M1b** |

### F05 — Wearable & health-data integration and monitoring

| Field | Content |
|---|---|
| Status | Simulated-wearable source path IMPLEMENTED + TESTED (`source: simulated_wearable` accepted on Track B; F-04 fixtures; observations never scored). Real adapters are **ACCESS-GATED** (P-6: named device owner, $0 account resolution, vendor terms). **Android Health Connect** gets a **capability- and device-dependent delivery plan**: availability varies by Android version/Play services and physical device, so the spike delivers (i) a capability check + supported-device record, (ii) an adapter behind the same ingestion API when a qualifying device exists, and (iii) the **simulated adapter as the always-available fallback** when it does not (the fallback is a deliverable, not a failure). Apple HealthKit and vendor APIs (Fitbit/Garmin/Withings/Polar) remain gated. **Wearable→CAD inference is PROHIBITED and enforced** (D-039, `422 wearable_input_not_valid_for_cad_inference`, fixtures F-09a/F-09b, test F-09) — including for any future real adapter. |
| Dependencies | F05 simulated: done. Real: P-6/D-019 + clinician review of device-facing copy. Never: labeled wearable+CAD dataset + separate validated protocol (none exists in approved evidence). |
| Data entities | **MonitoringObservation** + **MonitoringMetric** (exists on the wire), **DeviceLink** (future, M5+/P-6). |
| API requirements | `POST /v1/monitoring/observations` (exists; 201 first + 201 replay per operation contract — B-02 open question on 200-vs-201 wording). Batch ingestion (Q11). No wearable payload may ever appear in a CAD request (`context.source` closed set). |
| UI surfaces | Patient submission with visible source/synthetic labelling; clinician monitoring views distinguishing simulated/entered/device data everywhere (M1b). |
| Local tests | F-04/F-04b/F-04c fixtures; F-09 rejection tests (HTTP + contract); "monitoring does not increase the inference counter" check (M1a.3 acceptance). |
| Scientific/safety gates | One-way Track B→A rule (hard); no monitoring-triggered reassessment (§R2-2.2); `source=simulated` labelling mandatory; no device accuracy claims; no thresholds (PROHIBITED). |
| Milestone | Simulator plumbing: DONE-M1a.1/2 · History/trends: M1b · Health Connect: **M4 product-spike (capability/device-dependent plan + simulator fallback, time-boxed)** · Vendor adapters: post-P-6 |

### F06 — Reassessment, follow-up workflows, notifications & summaries

| Field | Content |
|---|---|
| Status | PROPOSED. Validity-gated reassessment mechanics are designed (Phase 0 §R2-2.2): valid triggers = new validated clinical inputs, corrected inputs, model-version change (labelled), clinician-requested re-score (deterministic). **Invalid** triggers = wearable arrival, time passage, monitoring trends, patient "check again". Slide alert thresholds (0.7/0.15/0.8 windows, S31/S38) are **PROHIBITED**. Doctor review states (`pending_review → reviewed_accepted \| reviewed_rejected \| reassessment_requested`) exist read-only in mock responses; no review-action endpoint exists yet. Notifications/summaries = in-app records + clinician-authored follow-up tasks and patient-visible static summaries; push (FCM/APNs) is deferred (needs accounts, P-6-class). |
| Dependencies | F01 review states; F11 roles; review/summary API (M1b contract change); P-4/D-016 clinician wording; F16 for any recommendation content. |
| Data entities | **ReviewAction** (decision, reason code, actor, timestamp), **ReassessmentRequest** (`reassessment_reason` enum), **FollowUpTask**, **NotificationRecord**, **VisitSummary**. |
| API requirements | Planned M1b: review-action endpoint, reassessment endpoint (validity-checked server-side), follow-up/summary CRUD; all idempotent + audited. Monitoring arrivals must NOT call inference (tested invariant). |
| UI surfaces | Clinician review actions + follow-up task list; patient notification/summary feed (static, conservative copy). |
| Local tests | Valid/invalid trigger matrix tests; determinism re-score test; "invalid trigger produces no new score" acceptance (M1b, IC-2); audit one-event-per-write. |
| Scientific/safety gates | §R2-2.2 binding validity rules; P-4/D-016 for all user-facing copy; no automated care escalation; no threshold alerting until validated + clinician-approved (indefinitely blocked for now). |
| Milestone | **M1b** (mechanics + copy review) |

### F07 — Events, audit logging, consent & data access

| Field | Content |
|---|---|
| Status | Audit event capture + test-only introspection IMPLEMENTED (in-memory snapshots: `audit_events`, `inference_count`, observation snapshot — no HTTP audit API by design, M1a.2). Durable append-only audit, consent lifecycle (grant/revoke/export), access logging for reads, retention policy: PROPOSED (M1b). |
| Dependencies | F11 actor identity; persistence (F18); privacy review (open); retention decision (open, Q8-class). |
| Data entities | **AuditEvent** (exists in memory; durable table M1b), **ConsentRecord**, **DataExportJob**. |
| API requirements | No audit/history endpoint today (deliberate). M1b: consent endpoints + audited reads; audit query API restricted to admin/clinician scope — needs contract review (none in approved contract). |
| UI surfaces | Patient privacy/consent center (F04); clinician audit view (F03); admin access logs (F17). |
| Local tests | One-event-per-accepted-write assertions (exists); M1b: audit immutability tests, consent grant/revoke audit tests, RBAC read-scope tests. |
| Scientific/safety gates | No PHI in event payloads (hashes/metadata only); no regulatory-compliance claims; DATA_POLICY.md rules; tamper-resistance NOT claimed (prototype). |
| Milestone | In-memory: DONE-M1a.2 · Durable + consent lifecycle: **M1b** |

### F08 — Interoperability / FHIR mapping & export

| Field | Content |
|---|---|
| Status | PROPOSED — minimal FHIR-R4-shaped JSON export of tabular features + prediction results (Phase 0 §8.7). The slides' "FHIR-normalized ingestion / SMART-on-FHIR / Epic-Cerner interop" (S27, S36, S39) is **deferred architecture aspiration**, not prototype scope (Phase 0 §7.3). No FHIR server. |
| Dependencies | F07/F18 persistence; D-020 scope decision (thin export proposed); Q14 (contract versioning of export). |
| Data entities | Export mapping: **Observation/Condition/RiskAssessment-shaped** JSON artifacts (research serialization, labelled). |
| API requirements | Planned `GET /v1/exports/fhir`-class endpoint (exact shape TBD at M4 contract review); research-serialization label mandatory; no interoperability certification claim. |
| UI surfaces | Patient "health records export" action (F04); researcher export tool (F03/F10). |
| Local tests | Snapshot tests of export shape; label presence tests. |
| Scientific/safety gates | Export labelled research prototype serialization; never "FHIR-compliant/compatible" product claim; D-020 approval first. |
| Milestone | **M4 optional, time-boxed** (Phase 0 workstream B5) |

### F09 — Extensible modular disease architecture

| Field | Content |
|---|---|
| Status | PROPOSED. `DiseaseModule` registry design (target definition, feature schema, model artifacts, explanation config, review workflow) per Phase 0 §R2-2.3; CAD = module #1. Public third-party SDK (S42–S43) deferred as a later-phase decision — preserved, not deleted. |
| Dependencies | F12 versioning; F18 persistence; second module requires its own scientific approval (never shares CAD scores/thresholds/claims). |
| Data entities | **DiseaseModule** registry row; per-module artifact registry entries. |
| API requirements | Module-scoped `/v1/...` namespaces later; registry admin API (F17). Contract versioning rules apply. |
| UI surfaces | Admin registry view (F17); module-aware clinician navigation (M4+). |
| Local tests | Registry CRUD tests; module-isolation tests (no shared thresholds). |
| Scientific/safety gates | Each new disease module is a separate research approval (target, data, protocol, wording); no cross-module claim reuse. |
| Milestone | Registry scaffolding: **M1b/M4** · Second module (e.g. hypertension): **post-M4, decision-gated** |

### F10 — Reproducible evaluation & research reporting

| Field | Content |
|---|---|
| Status | PROPOSED protocol is fully specified (Phase 0 §R2-5: nested CV, leakage audits, cross-fitted calibration, bootstrap CIs, subgroup cell rules, TRIPOD+AI reporting) but **not started** — Gate DA/PT closed. Required research core (not optional). |
| Dependencies | P-2 Gate DA → P-3 Gate PT (binding order); P-1 target; D-025 broader-literature verification before novelty claims; supervisor approval of protocol. |
| Data entities | **ExperimentLog**, **DatasetAuditReport**, **ModelCard**, **ReplicationPackage** (all in `research/experiments/`, out of git for raw data). |
| API requirements | None (offline research workflow); model artifacts enter the registry (F01 provenance) only after Gate PT + validation lifecycle. |
| UI surfaces | None directly; feeds F01/F02 rendering via `model_performance_ref` + `validation_status`. |
| Local tests | Research pipeline re-runnable from `research/experiments/`; label-shuffle negative control; fixture suite re-green with real model (IC-3). |
| Scientific/safety gates | **Gate DA, Gate PT**; leakage checklist sign-off; claims discipline (§R2-5.9); no invented accuracy numbers; no guarantee of beating published papers; dataset license hygiene (DATA_POLICY.md). |
| Milestone | M2 (data audit) → M3 (protocol + benchmarks) → M4 (write-up) |

### F11 — Authentication, roles & access control

| Field | Content |
|---|---|
| Status | PROPOSED (M1b). Current backend is intentionally unauthenticated and single-process; M1a.3 clients use synthetic refs. Prototype-grade security only — hashed passwords, roles, sessions/tokens, RBAC, audit; **no compliance claims** (Phase 0 §7.5). |
| Dependencies | F18 persistence (users table); F07 audit; security review; M1b milestone authorization (re-confirm auth scope after M1a.2/1a.3 deferral). |
| Data entities | **UserAccount**, **RoleAssignment**, **Session/TokenRecord**. |
| API requirements | Planned `/v1/auth/*` (login/refresh/logout), role-guarded routes; error envelope reused; contract review required (not in approved contract). |
| UI surfaces | React + Flutter login/session handling (M1b); admin user provisioning (F17). |
| Local tests | RBAC role-matrix tests (Phase 0 workstream B3); auth failure paths; secret-scanning in CI (planned). |
| Scientific/safety gates | No regulatory-compliance claims; no PHI guarantee; threat model documented at M1b review. |
| Milestone | **M1b** |

### F12 — Versioned AI–backend API & integration tests

| Field | Content |
|---|---|
| Status | **IMPLEMENTED + TESTED** (DONE-M1a.1/2): `shared/contracts/` (OpenAPI, 4 schema families, 2 MOCK_ONLY registries, 30 fixtures / 33 steps), 136 contract tests, FastAPI mock backend (2 endpoints + bundled `/openapi.json`), 234 HTTP tests; 370 total green (`-W error`); CI workflows `contracts-ci.yml` + `backend-ci.yml` installed. Open contract questions Q1–Q14 and compat notes A-01/B-01…X-01 remain explicitly open (`shared/contracts/README.md` §11, `backend/CONTRACT_NOTES.md`). |
| Dependencies | None (baseline). Change protocol: ADR process (ADR-001 example); approved artifacts never edited without maintainer approval. |
| Data entities | Fixture pack, schema/registry artifacts, idempotency records (in-memory, 24 h retention). |
| API requirements | `POST /v1/predictions/cad-tabular`, `POST /v1/monitoring/observations`, `GET /openapi.json` (all exist). `/docs` disabled; only one worker. |
| UI surfaces | n/a (contract layer). |
| Local tests | `python -m pytest tests/contracts tests/backend -q -W error` (370); `python scripts/verify_sources.py` (4/4). |
| Scientific/safety gates | MOCK_SYNTHETIC data class; no schema edits without approval (ADR-001); versioning rule (breaking change → `/v2`). |
| Milestone | DONE-M1a.1/2 · Continues as the regression gate for every later milestone (IC-3 re-greens it with real models) |

### F13 — Medical history, symptoms, surveys & clinical feature input

| Field | Content |
|---|---|
| Status | PROPOSED (register extension §3). Vision sources: patient journey "baseline survey", "2-minute symptom check" (S38), clinician/exam inputs for Track A (Phase 0 Track A flow), blueprint request 2026-10-17. Includes: structured medical-history entries, symptom entries, versioned survey instruments, lifestyle questionnaires, and clinician-entered clinical feature sets mapped to a `feature_schema_id`. |
| Dependencies | F11 identity; F18 persistence; F12 feature-schema versioning; survey-instrument content review (P-4-class for anything symptom/clinical wording); real feature schemas blocked on Gate DA dictionary work (Q1). |
| Data entities | **MedicalHistoryEntry**, **SymptomEntry**, **SurveyDefinition** (versioned), **SurveyResponse**, **ClinicalFeatureSet** (feature_schema_id + values + provenance). |
| API requirements | Planned M1b: history/symptom/survey write+read APIs, clinical-feature-set submission wrapping the existing prediction contract (`clinician_entry` source); all idempotent + audited. |
| UI surfaces | Flutter: history/survey/lifestyle screens (F04); React: clinician feature-entry form (M1a.3 starts with the synthetic-record form). |
| Local tests | Survey versioning tests; feature-set validation tests (units/ranges via schema); audit-per-write; RBAC ownership tests. |
| Scientific/safety gates | Survey/clinical wording review (P-4); no feature enters a CAD model outside a frozen protocol (Gate PT); patient-entered values reach inference only via clinician-confirmed `clinician_entry` (§F-4); any lab-derived member of a clinical feature set must pass the **05 §2.1 eligibility checklist** (schema membership, target, prediction time, units, provenance, protocol) — verification or confirmation alone never suffices, and no feature mapping is invented (real schemas come from Gate DA, Q1). |
| Milestone | **M1b** (manual entry + basic surveys) · Instrument content finalized with clinician review |

### F14 — Laboratory-report image/PDF upload & OCR extraction

| Field | Content |
|---|---|
| Status | **PROPOSED — required product-vision deliverable** (register extension §3; product track M5). **Provenance: 2026-10-17 master-blueprint request + external mockups (EXT-01…14, uninspected).** Not described in the 47-slide speaker notes; treated as preserved vision, not as a slide-traced feature. Scope: patient/clinician upload of lab-report images/PDFs; local OCR extraction of structured fields (analyte, value, unit, reference range, collection date); raw text retained. Scheduling/implementation subject to implementation-readiness and safety approvals — it is not part of research-prototype completion (M4), and not optional. |
| Dependencies | F18 persistence + file storage (out-of-git, hashed); F11 auth; **$0 local OCR engine decision** (Tesseract-class local engine — cloud OCR APIs prohibited: cost + PHI egress); EXT mockups for upload UX; P-4-class review of extraction-display copy. |
| Data entities | **LabDocument** (mime, sha256, storage ref, uploaded_by, status), **ExtractionField** (raw text, value, unit, page/region locator, engine+version, confidence). Extracted fields are **Track-B document data**; they carry no model eligibility by default (see F15 / 05 §2.1). |
| API requirements | Planned M5: `POST /v1/documents/lab-reports` (multipart upload), `GET .../extraction` (fields + provenance); all audited; virus/size/type validation; no raw document bytes in audit events. Contract review required. |
| UI surfaces | Flutter upload screen; React document review screen (per EXT mockups once supplied). |
| Local tests | Upload validation tests (type/size/hash); OCR pipeline tests on **committed synthetic sample documents** (not real reports); extraction-accuracy *engineering* checks only — never reported as clinical accuracy. |
| Scientific/safety gates | Real patient reports are PHI: prototype accepts **synthetic sample documents only** until a privacy/ethics design exists; OCR output is unverified data until F15 verification; extracted fields never auto-feed a CAD model; no diagnostic interpretation of lab values by the system; eligibility for Track A is decided only per 05 §2.1, never by the upload/OCR pipeline. |
| Milestone | **M5 product track** (required deliverable; requires maintainer authorization before scheduling) |

### F15 — Extracted-field editing, provenance, confirmation & clinician verification

| Field | Content |
|---|---|
| Status | **PROPOSED — required product-vision deliverable** (register extension §3; product track M5, with F14). Scope: every extracted field is editable with full provenance (raw vs edited, who/when); patient confirmation step; clinician verification step; verification state machine `extracted → edited → confirmed → verified` (or `rejected`). A verified field may be *recorded* in a **ClinicalFeatureSet** (F13) **only when the 05 §2.1 eligibility checklist also passes** for the approved model version. **Verification alone never implies Track-A model eligibility** — a verified field that is not a named feature of the approved `feature_schema_id` remains a Track-B/record value only (no feature mapping is invented). |
| Dependencies | F14; F11 roles (clinician verification permission); F07 audit (every edit/verification is an event); F13 feature-set mapping (unit reconciliation!); 05 §2.1 boundary; Gate DA feature dictionary (Q1) before any Track-A mapping can exist. |
| Data entities | **ExtractionField** (+ edit history), **VerificationEvent**, link to **ClinicalFeatureSet** (eligibility-gated edge). |
| API requirements | Planned M5: `PATCH /v1/documents/lab-reports/{id}/fields/{field_id}` (idempotent), `POST .../verify`; response carries provenance + state; 409 on concurrent conflicting edits (idempotency/conflict patterns reused). Promotion to a Track-A-bound feature set is a separate, eligibility-checked operation — `verify` alone never writes to an inference-eligible set. |
| UI surfaces | Side-by-side document viewer + field editor (React); patient confirmation (Flutter). Per EXT mockups. |
| Local tests | State-machine transition tests; provenance retention tests (raw never lost); "unverified field cannot enter feature set" test; **"verified-but-ineligible field cannot enter a Track-A feature set"** test (05 §2.1 negative case); unit-mismatch fail-closed test; audit-per-edit tests. |
| Scientific/safety gates | Human-in-the-loop mandatory (no auto-verification); unit mismatches must fail closed (422-class, never silent conversion); clinician verification ≠ clinical validation claim ≠ model eligibility; wearable/monitoring values can never ride this path into inference (F-09 rule preserved); P-4 copy review for patient-facing confirmation text. |
| Milestone | **M5 product track** (required deliverable, with F14; requires maintainer authorization before scheduling) |

### F16 — Research-safe recommendations & clinical-assistant capabilities

| Field | Content |
|---|---|
| Status | PROPOSED, **most heavily gated** (register extension §3). The slides' model-attached "recommended action: consider statin / reassess in 7 days" (S34) and score-triggered nudges/alerts (S38) are **PROHIBITED as model outputs** (Phase 0 §2.1). Preserved instead: (a) static, guideline-sourced, clinician-approved symptom-safety and lifestyle content (D-026: omit until a named clinician approves); (b) research-safe summaries for clinicians (model card + explanation + literature references, explicitly non-directive); (c) a future assistant that answers questions **from project documentation/literature only**, with citations, never individualized treatment advice. |
| Dependencies | Named clinician content approval (D-016/D-026, P-4); F02 real explanations before any explanation-grounded assistance (M3+); F16 copy must pass clinician review; any literature-grounded claims need D-025 verification. |
| Data entities | **ContentItem** (static, sourced, versioned, approver), **AssistantExchange** (log, citations, scope limits). |
| API requirements | Planned M5: content retrieval API; assistant endpoints only if scoped as documentation-Q&A with mandatory citations + refusal rules for medical advice; audited. |
| UI surfaces | Patient static safety/lifestyle content; clinician research summary panel; assistant panel (clearly labelled "research information, not medical advice"). |
| Local tests | Copy snapshot tests (prohibited-phrase guardrails); citation-presence tests; refusal-behavior tests for advice-like questions. |
| Scientific/safety gates | **P-4 + D-016/D-026** hard gates; model-driven treatment/diagnostic advice permanently out of scope for the prototype; never triggered by unvalidated thresholds; no performance claims in assistant output. |
| Milestone | **M5** (proposed) · Static safety content earlier only if clinician approves (D-026) |

### F17 — Administration

| Field | Content |
|---|---|
| Status | PROPOSED (register extension §3). Basic ops (user provisioning, role assignment, registry maintenance, system health, dependency/CI status) at prototype level; full admin console (audit search, dataset/model registry management, content approval workflow) in M5. |
| Dependencies | F11 auth/RBAC; F07 audit; F09 registry. |
| Data entities | **UserAccount**, **RoleAssignment**, registry tables, **AdminAction** (audited). |
| API requirements | Planned M1b minimal admin endpoints (user create/disable/role set); M5 registry/content-admin APIs. |
| UI surfaces | React admin section (M5); CLI/script fallback acceptable in M1b. |
| Local tests | RBAC admin-only route tests; admin-action audit tests. |
| Scientific/safety gates | Admin ≠ clinical authority; registry edits can never change a served model's provenance retroactively; content approval workflow records approver identity (P-4). |
| Milestone | Basic: **M1b** · Console: **M5** |

### F18 — Persistent database & deployment posture

| Field | Content |
|---|---|
| Status | Persistence PROPOSED (today: in-memory state, resets on restart — documented limitation). Plan: SQLite for local development + documented PostgreSQL migration path ([04](04_DATABASE_AND_API_INTEGRATION_DESIGN.md)). Deployment posture: local-first modular monolith (D-041); Docker-optional; hosted demo optional/disposable and **UNVERIFIED** at $0 (Phase 0 §7.4); slide's AWS/K8s/microservice topology explicitly deferred (§7.3). |
| Dependencies | M1b milestone; Alembic-class migration tooling; CI migration test; team-machine Docker verification (optional). |
| Data entities | All durable entities in [04](04_DATABASE_AND_API_INTEGRATION_DESIGN.md) ERD. |
| API requirements | None directly; persistence must not change wire behavior (fixture suite is the guard). |
| UI surfaces | None; admin system-health (F17). |
| Local tests | Migration up/down tests; SQLite→PostgreSQL compatibility test job (Postgres service container or local PG) before any production-ish deployment; full suite green after persistence lands. |
| Scientific/safety gates | No real patient data in the database (synthetic/demo only until ethics/privacy design); backup/export rules follow DATA_POLICY.md; no deployment-readiness claims (P-5). |
| Milestone | Persistence: **M1b** · PostgreSQL path validated: **M4** · Optional hosted demo: M4+ (disposable) |

## 6. Presentation claims rejected as design inputs (traceability of *non*-features)

These slide claims must not appear as requirements or facts (full table:
Phase 0 §2.1). Rejected: "30-day CAD risk" + threshold alerts (S31/S38);
literature accuracy figures as targets (S30); latency/throughput SLAs (S31);
treatment recommendations on SHAP tiles (S34); 50-patient pilot / FDA 510(k)
/ EU MDR / ISO 13485 scope (S42–S43); business projections (S9–S10, S45);
"HIPAA/GDPR compliant by design", "wearables are FDA-cleared" for CAD (S39,
S46); MIMIC augmentation claims (S43); Kaggle CVD/Framingham mirrors as data
sources (S29). Any future revival needs its own decision entry + evidence.

## 7. Feature → source-document index (quick trace)

| Source | Rows |
|---|---|
| Slides S20, S22–S27, S36, S42–S43 (platform/architecture) | F07–F09, F11, F12, F17, F18 |
| Slides S28–S34 (data/ML/XAI) | F01, F02, F10 |
| Slides S37–S39 (patient) | F04, F05, F06, F13 |
| Slides S40–S41 (clinician) | F03, F06 |
| `docs/FEATURE_REGISTER.md` F01–F12 | F01–F12 1:1 |
| Phase 0 §R2-1–§R2-3, §F-4 | Track split; F05 prohibition; reassessment rules (F06) |
| Blueprint request 2026-10-17 + EXT mockups | F13–F18 |
| Merged implementation (`shared/contracts/`, `backend/`) | F12 (and mock layers of F01, F02, F05, F07) |
