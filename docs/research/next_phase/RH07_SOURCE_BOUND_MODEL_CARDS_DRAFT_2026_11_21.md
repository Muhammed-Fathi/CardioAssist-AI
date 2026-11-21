# RH-07 — source-bound research model-card draft pack (2026-11-21)

**Status:** `DRAFT_SOURCE_BOUND_NOT_REVIEWER_ACCEPTED`. This is evidence-aware **documentation**, not a trained model, protected-run audit, medical device approval, TRIPOD+AI/PROBAST+AI certification, RH-07 acceptance or RH-08 release. It implements no inference, retraining, provider or authorization change.

**Snapshot:** merged PR #128 `8f11b188f0e0326d1b06f76fc2e36eb564898ff0`; controlling RD-01–RD-10 decisions from [PR #118](https://github.com/Muhammed-Fathi/CardioAssist-AI/pull/118). Detailed records in [RH07_SOURCE_BOUND_MODEL_CARDS_DRAFT_2026_11_21.json](RH07_SOURCE_BOUND_MODEL_CARDS_DRAFT_2026_11_21.json).

## A. Five frozen research registry slots — **synthetic vs blocked**

| Registry model key | Dataset/route | Research-only state | Frozen offline fixture outcome |
|---|---|---|---|
| `synth_ai7_da_a2_resting_v1@0.1.0` | DA-A2 / `da_a2_resting_v1` | `ENTRY_STATE_ACTIVE` | `SYNTHETIC_RESULT` |
| `synth_ai8_uci412_da_a1_basic_clinical@0.1.0` | DA-A1 / `da_a1_basic_clinical_v1` | `ENTRY_STATE_ACTIVE` | `SYNTHETIC_RESULT` |
| `synth_ai7_da_a2_resting_labs_v1@0.1.0` | DA-A2 / `da_a2_resting_labs_v1` | `ENTRY_STATE_BLOCKED_PENDING_AUTHORIZATION` | `UNAVAILABLE` |
| `synth_ai7_da_a1_clinical_core_labs_v1@0.1.0` | DA-A1 / `da_a1_clinical_core_labs_v1` | `ENTRY_STATE_BLOCKED_SOURCE_TIMING` | `UNAVAILABLE` |
| `synth_ai7_da_a2_hungary_locked_transportability_v1@0.1.0` | DA-A2 / `da_a2_hungary_locked_transportability_v1` | `ENTRY_STATE_LOCKED_EXTERNAL_TARGET` | `UNAVAILABLE` |

**Source of truth:** `ai/research_registry.py` + `ai/panels.py` + `ai/research_routes.py` + `research/intake/fixtures/offline_io.v1.json`. Two synthetic routes are executable only through the offline research facade; three registry slots are blocked or locked. None is a clinical patient predictor, a deployable real-model artifact or a selectable HTTP provider. The versioned research catalog makes no general artifact-verification assertion.

### A1 — Cleveland synthetic resting research exercise

- `synth_ai7_da_a2_resting_v1@0.1.0`: DA-A2, five ordered historical fields `age, sex, cp, trestbps, restecg`; original UCI-45 target wording **>50%**; synthetic-only test evidence.
- Existing **fixture-specific** detailed card: `docs/research/ai12_1/linux-uci45-envelope.v1.json#model_card`, which records one fabricated fixture model, its version, explained score scale, provenance and refusals. That card must not be interpreted as independently authenticating every potential bundle created later.
- `trestbps` / `restecg` may be absent at the staged input; this offline route abstains rather than silently producing a score. Exploratory threshold **0.5** is not medically validated.

### A2 — UCI-412 synthetic basic clinical exercise

- `synth_ai8_uci412_da_a1_basic_clinical@0.1.0`: DA-A1, **16 required fields**, preserved in the JSON card's `feature_order_reference` and the source Python panel.
- The synthetic fixture has `SYNTHETIC_RESULT`, but no original UCI-412 field has owner-verified pre-angiography timing (**0/16**); BP/PR units, binary coding and chest-pain flags remain scientific source questions.
- Registry declares calibration/SHAP/LIME capability on its active synthetic exercise. That declaration is **not** a newly inspected artifact-specific quality report, clinical explanation, patient probability or justification for a real UCI-412 fit. Original UCI-412 target wording is **≥50%**.

### A3 — Blocked and locked contracts

- DA-A2 resting+`chol/fbs`: authorization-blocked. Real AI-9.2 clinical+labs experiment **NOT_PERFORMED**. No fake laboratory gain.
- DA-A1 clinical plus seven labs: blocked due to original pre-reference field-timing uncertainty; no paired real-lab improvement or fitted route claimed.
- Cleveland-to-Hungary locked target: real AI-10.2 **NOT_PERFORMED**, no real external validation; AI-10.1 was only a synthetic software rehearsal.
- A blocked route's frozen offline fixture outcome is `UNAVAILABLE`; it must **not** offer a score or implied model card with measured clinical metrics.

## B. Two separate, historical internally reported research summaries

| Historically reported study | n / positive / negative | Main selected-procedure AUROC | AP/AUPRC | Brier |
|---|---:|---|---|---|
| D-047_CLEVELAND_HISTORICAL | 303 / 139 / 164 | 0.8271 ± 0.0097 | 0.7712 ± 0.0193 | 0.1671 ± 0.0049 |
| M3A_UCI412_HISTORICAL | 303 / 216 / 87 | 0.9107 ± 0.0071 | 0.9504 ± 0.0077 | 0.0995 ± 0.0043 |

**Evidence source:** original committed D-047 local-aggregate results review and M3a two-source synthesis respectively. All displayed quantities are **previously maintainer-reported**; this PR neither accesses nor reruns their protected `report.json`, predictions, per-person rows or fitted bundles. Every `±` is population SD across four **dependent** repeated-CV run aggregates on the same 303 people, **not** a confidence interval, standard error or clinically meaningful precision guarantee. The two AUROCs must **not** be ranked or pooled: differing cohorts, predictors, case mix and >50% vs ≥50% endpoints. Neither record is an independently externally validated clinical model.

## C. Explanation, model-governance and release limits

- Calibrated synthetic research scores and SHAP/LIME output are model-specific; SHAP may explain calibrated **log-odds** on the relevant synthetic LR bundle, not a calibrated individual medical probability. LIME is a local surrogate, not a causal feature effect. Absent/unstable fidelity must be reported or explained away by abstention, not by invented importance.
- The HTTP application is deliberately limited to `MOCK_SYNTHETIC` per RD-09, and original historical internal bundles are not published or served.
- RH-05 Windows full suite (`2909 passed / 3 skipped`, native NTFS 8/8) is **maintainer-reported** at its original tested source SHA `64f34e4cb8580ced461237ffa46ba0a91e8fc1c5`; source-bound Linux/Windows comparison used a separate SHA `09b895423171eff7569fc49dd8ceac7dfb0d43c6`. These runs are **not** at this card-documentation SHA.
- The Python 3.12 Golden Replay intermittent failure still lacks a proven root cause. PR #126 provided safe diagnostic instrumentation, not an assertion that the issue is fixed.
- TRIPOD+AI and PROBAST+AI gaps, 19 unverified claims and 10 human review actions remain unchanged. These cards are draft science/reporting artifacts until real review and RH-08 handoff.

## D. Next acceptance actions

An independent reviewer should (1) verify registry/panel/fixture linkages; (2) check precise sources for each historical numeric row; (3) assess source-specific biases, chronology and calibration limits; (4) verify the existing Cleveland fixture-specific card separately; (5) preserve unresolved source questions and reviewer ownership; and (6) sign or reject the reviewed **research-only documentation** with actual evidence, never a fabricated clinical approval.

The stdlib-only validator `scripts/verify_rh07_model_card_pack.py` checks identity, fixture outcomes and source-text consistency, not scientific accuracy or protected-run reexecution. The associated negative tests exercise blocked-state and approval overclaims.
