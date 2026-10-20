# 06 — Clinician-Input Feature Availability & Backend Integration Feasibility

**Status: PROPOSED feasibility assessment. It defines no schema, changes
no contract, and authorizes no frontend or backend work.** The existing
`/v1` contracts, fixtures, registries, and mock behavior are untouched by
this package. Real clinical schemas require a separate contract-first
approval (contracts Q1, `shared/contracts/README.md` §11).

## 1. The boundary that governs everything below

| Track | Rule (binding today) |
|---|---|
| **Track A** — CAD presence classification (D-038) | Inputs only from `benchmark_import` or clinician-verified `clinician_entry`, exactly matching the approved model's `feature_schema_id`. Trained only on Gate DA/PT-approved data. |
| **Track B** — wearable/monitoring (D-039) | Monitoring observations never feed CAD inference (`422 wearable_input_not_valid_for_cad_inference`, fixture F-09) — permanently for wearable data; for clinician-verified lab values, only via the six-condition eligibility checklist in `docs/blueprint/05` §2.1 (schema membership, target, prediction time, units, provenance, protocol coverage). Verification alone never confers eligibility. |
| Parallel platform scope | Auth/RBAC, durable idempotency, consent, patient records, DB expansion, and the approved **planning-only** entitlement proposal (Free: 2 successful AI uses/account lifetime; Doctor Trial: 14 days via doctor-issued code, then back to Free with remaining quota; Premium: full eligible patient access, locally simulated, no live payments) are a **separate workstream**. Nothing here implements them. Subscription/entitlement state is an access-control concept: it is **not** clinical authorization, not doctor–patient linking, and must never gate or alter a clinical input definition. |

## 2. What a clinician could plausibly supply — candidate input specification (PROPOSED)

Derived **only** from the verified UCI-45 conventional feature set and the
verified UCI-412 feature *groups* (document 01). This is a plausibility
specification for the frontend team's planning and for the Gate DA/PT
feature dictionary — **it is not a schema**: final names, units, ranges,
categorical codings, and required/optional status come from the Gate DA
dictionary audit + Gate PT freeze + contract-first approval (Q1).

| Group | Candidate clinician-suppliable inputs (candidate source features) | Units / coding as verified at source | Availability at a pre-angiography clinic moment | Feasibility notes |
|---|---|---|---|---|
| Demographics | Age (`age`); sex (`sex`) | years; source coding to be confirmed per file at audit (UCI-45 lists 1=male/0=female **[VERIFIED]**; DS-2 coding UNVERIFIED) | Routinely available | Lowest-risk inputs; still require exact coding map — do not assume cross-dataset coding equality |
| History / symptoms | Chest-pain type (`cp` 1–4: typical/atypical/non-anginal/asymptomatic **[VERIFIED]**); DS-2 symptom & examination group (per-feature list UNVERIFIED until audit) | categorical, source-specific | Available by history/examination, if the clinician elicits them in the source's terms | UI must present the *source's* categories verbatim (clinician-reviewed wording, P-4); free-text symptoms are not model inputs |
| Vitals | Resting BP (`trestbps`, "on admission", mm Hg **[VERIFIED]**) | mm Hg | Routinely available | Measurement-context difference (admission vs clinic) is a harmonization note (H-07), not a UI detail |
| Labs | Serum cholesterol (`chol`, mg/dl **[VERIFIED]**); fasting glucose indicator (`fbs` >120 mg/dl **[VERIFIED]**); DS-2 laboratory group (features/units UNVERIFIED until audit) | mg/dl as listed; any mmol/L source needs a protocol-approved explicit conversion — never silent (422 unit-mismatch rule already in contract) | Available only if drawn before the prediction moment; results pending = missing, not zero | Null/absent semantics already contracted: explicit `null` = not provided; `0` is data (ADR-001/fixtures F-03b/c). Clinician-verified lab values additionally need the §2.1 six-condition checklist before Track-A use |
| Resting ECG | Resting ECG result (`restecg` 0–2 **[VERIFIED]**) | categorical | Available if ECG performed pre-angiography | Category definitions are source-specific; UI needs clinician-reviewed labels (P-4) |
| Exercise test *(conditional block)* | Max HR achieved (`thalach`), exercise angina (`exang`), ST depression (`oldpeak`, **unit UNVERIFIED**), ST slope (`slope` 1–3) | as listed; `oldpeak` unit must not be asserted in any UI/schema until ratified at Gate DA | **Only after an exercise test exists.** Not suppliable at a first-visit/pre-test moment | Admissibility is decided by the frozen prediction moment (L-07). Frontend must be able to hide/require this whole block per model version — it must not collect it "just in case" for a pre-test model |
| Stress imaging *(pending)* | Thallium result (`thal` 3/6/7) | categorical | Only after scintigraphy | **Pending-review (L-06): excluded from primary model until ruled.** Do not build a required UI field for it |
| **Never clinician inputs for T1** | `ca` (fluoroscopy vessel count); per-vessel angiography fields; LAD/LCX/RCA/Cath; cath dates; any post-diagnosis treatment/procedure/result | — | Obtained by/during the label-defining procedure, or after diagnosis | **Leakage (L-01/L-02/L-03).** The UI must never solicit these as predictors; their absence from the input form is a safety feature. (They may exist in backends later as *outcomes/records* under separate contracts — not as inference inputs.) |
| Wearable/monitoring | HR/HRV, steps, SpO₂, sleep, etc. | Track-B metric catalogue (mock today) | Continuous, patient-side | **Track B only.** Never rendered as CAD inputs, never merged into the Track-A form, never a reassessment trigger by arrival/trend (Phase 0 §R2-2.2) |

**Required vs optional (PROPOSED principle, not a ruling):** the frozen
model's dictionary decides. Demographics are the only candidates this
package would expect to be *required* (mirroring the mock schemas'
pattern); everything else should be assumed optional-with-explicit-null
until Gate PT rules — because a model that requires an exercise test or
scintigraphy is a different clinical tool than one that does not.

## 3. Feasibility against the existing backend/contracts (VERIFIED against repo)

| Question | Finding |
|---|---|
| Can the current `/v1` CAD endpoint accept real features today? | **No — by design.** Only `mock_clinical_v1/v2` exist (`MOCK_ONLY`, `UNVERIFIED_PENDING_GATE_DA`), populated by `mock_feature_*` slots with placeholder units (`u_years`, `u_pressure`, …). Real models **must not** reuse `mock_feature_*` or `mock_model_*` identifiers as clinical definitions. |
| What already transfers to a future real schema? | The envelope discipline: versioned `feature_schema_id`; per-feature `{value, unit, entered_by}`; unit mismatch = 422 (never silent conversion); explicit-null = absent; zero/false are data; unknown feature/schema/model = 422 with named codes; provenance IDs (`model_id`, `preprocessing_id`, `calibration_id`, `explanation_config_id`, `validation_status`) on every response; Track-B rejection of wearable payloads (F-09). These are contract *patterns* to reuse under a new, separately approved schema — not permission to edit the mock schemas into clinical ones. |
| What is missing before any real integration? | (1) Gate DA dictionary audit → real feature list/units/ranges/codings (Q1). (2) Gate PT frozen dictionary + prediction moment. (3) Contract-first approval of new schema/registry artifacts under **new identifiers** (e.g. a future `feature_schema_id` naming the audited dictionary — exact ID is a contract decision, not asserted here). (4) Clinician-approved wording (P-4). (5) A trained, versioned model artifact + model card (M3) — serving an untrained or mock artifact under a clinical schema would be a false claim. |
| Database implications? | **None in this task.** Future clinical feature sets/prediction provenance are proposed entities in `docs/blueprint/04`; M1b.1's SQLite foundation deliberately stores only the existing monitoring write with opaque references. No migration is proposed or authorized here. |
| Frontend implications? | The frontend team can plan forms against §2's *grouping and availability logic* (conditional exercise block, never-collect leakage fields, Track A/B separation) using **mock schemas only** for any thin local demo (M1a.3 remains deferred/resequenced per D-045). Full React/Flutter apps remain the frontend team's deliverable; no form field becomes a clinical definition until the contract-first approval above lands. |

## 4. Serving/copy constraints any future integration must preserve

- Uncalibrated model output renders as `uncalibrated_score` — never "%",
  "risk", or a probability (fixture F-11 pattern; H-05).
- Calibrated output is labelled a benchmark-cohort model score with
  cohort context (Phase 0 §F-6); no absolute personal-risk language.
- No diagnosis, alert-threshold, triage, or treatment-recommendation
  copy without clinician approval (P-4); conservative fallback until then.
- Explanation values (when real SHAP exists, M3) are log-odds-margin
  contributions, not probability shares (document 05 §6).
- Patient-entered values reach inference only as a new clinician-confirmed
  `clinician_entry` (Phase 0 §F-4); entitlement/tier state (§1) plays no
  role in this rule.

## 5. Feasibility verdict (PROPOSED)

**Integration is feasible without changing any existing contract** —
precisely because the mock contract already reserves the versioning,
provenance, unit, null, and track-separation machinery a real schema
needs. The blockers are scientific and contractual, not technical:
Gate DA audit (dictionary), Gate PT freeze (moment + features), Q1
contract-first schema approval, P-4 clinician wording, and a real trained
artifact. Any attempt to shortcut them by renaming mock features would
violate the identifier rule above and invalidate the fixture pack's
meaning.
