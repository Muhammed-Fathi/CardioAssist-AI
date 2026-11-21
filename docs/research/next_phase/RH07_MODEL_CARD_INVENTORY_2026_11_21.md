# RH-07 — model-card coverage and gap inventory (2026-11-21)

**Status:** `MODEL_CARD_COVERAGE_REVIEW_PENDING`, not a served model, clinical signoff or new training.

## Already committed, mechanically inspectable

- The read-only projection `ai/research_catalog.py` describes **five** registry entries and explicitly withholds artifact-verified capability claims. It permits **no serving**.
- The one published synthetic Cleveland card lives inside `docs/research/ai12_1/linux-uci45-envelope.v1.json` at key `model_card`, referenced by the catalog as `#model_card`. It is **synthetic only**, with no genuine patient prognosis or clinical probability claim.
- The five-entry registry in `ai/research_registry.py` has two executable *offline synthetic* routes and three non-executable contracts. Its active synthetic declarations are not a real clinical model inventory.

## Source-specific entries to cover in final handoff

| Registry model key | Route | Executability | Model-card evidence / action |
|---|---|---|---|
| `synth_ai7_da_a2_resting_v1@0.1.0` | `da_a2_resting_v1` | Active synthetic offline only | Existing embedded AI-12.1 synthetic card; verify its source/feature/model scale and artifact provenance for the exact fixture |
| `synth_ai8_uci412_da_a1_basic_clinical@0.1.0` | `da_a1_basic_clinical_v1` | Active synthetic offline only | No equivalent standalone published card found in this inventory; draft from frozen 16-field contract, no invented timestamp verification |
| `synth_ai7_da_a2_resting_labs_v1@0.1.0` | `da_a2_resting_labs_v1` | Blocked — authorization | Contract/NOT_PERFORMED card only; no study metrics or score |
| `synth_ai7_da_a1_clinical_core_labs_v1@0.1.0` | `da_a1_clinical_core_labs_v1` | Blocked — pre-reference source timing | Contract/NOT_PERFORMED card only; no clinical labs benefit claim |
| `synth_ai7_da_a2_hungary_locked_transportability_v1@0.1.0` | `da_a2_hungary_locked_transportability_v1` | Locked external target | No true Hungary performance; document only synthetic rehearsal/NO-GO |

## Historical research results are separate

- The original D-047 five-feature Cleveland and M3a UCI-412 aggregate reports are **historical internally reported analyses**, not the two newly generated synthetic artifacts above.
- Future research-specific cards must distinguish the original 303-subject source cohorts, protocol, intended outcome and available metrics from the executable synthetic route; do not imply a real fitted deployable artifact exists.
- Missing sections for final reviewer: data origin and rights, target label and boundary, chronological eligibility/units/missingness, model family/selection, cross-validation provenance, discrimination/calibration/precision, source bias and transportability, explanation scale/fidelity, limitations, genuine tested software SHA, exact model/panel hashes, refusal behavior, and human review state.
- Do **not** publish real-patient model data, SHAP backgrounds, sensitive local artifacts, protected `report.json`, or raw prediction rows.

**Acceptance:** this index helps scope RH-07; it does not itself fill all missing model cards or close AC-09.

## 2026-11-21 independent source-bound follow-up (PR #129 draft)

The companion [source-bound model-card draft](RH07_SOURCE_BOUND_MODEL_CARDS_DRAFT_2026_11_21.md) and [machine-readable seven-record pack](RH07_SOURCE_BOUND_MODEL_CARDS_DRAFT_2026_11_21.json) now inventory the five frozen synthetic/blocked registry slots **and** two separately archived historic experiments. Their source/fixture consistency validator guards accidental approval or model-score promotion. This closes a **documentation coverage drafting gap only**; AC-09 still requires independent reviewer confirmation, artifact-specific evidence as applicable and final handoff acceptance. No protected experiment rerun, fitted real-serving model, clinical approval or RH-07 closure is implied.
