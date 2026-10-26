# AI Workstream (`ai/`) — Track A Research Pipeline (`RESEARCH_ONLY`)

This package implements the reusable, offline Track A tabular CAD AI research pipeline specified in [`docs/research/AI_FIRST_COMPLETION_STRATEGY.md`](../docs/research/AI_FIRST_COMPLETION_STRATEGY.md).

## Modules

- **`ai/execution.py`** — Auditable, locally protected real-data execution controller bridging validated read-only source adapters (`research.uci412.adapter` and `research.experiments.data_adapter`) to the AI pipeline under hash-bound, human-ratified authorization manifests, enforcing zero-leakage, anti-disguise, and private untracked artifact storage.
- **`ai/panels.py`** — Versioned staged clinical & routine-laboratory input contracts (`da_a2_resting_v1`, `da_a2_resting_labs_v1`, `da_a1_basic_clinical_v1`, and proposed synthetic-only `da_a1_clinical_core_labs_v1`), reusing `research.intake.synthetic_stage_validator` and `research.uci412.feature_schema` while rejecting Track B wearable inputs and angiography/echo leakage fields.
- **`ai/preprocessing.py`** — `FoldSafeClinicalPreprocessor`: strictly training-fold-fitted imputation, scaling, and fixed-order reference coding with explicit `raw_feature -> encoded_columns` group slices and pure JSON state serialization (`preprocessing.json`).
- **`ai/calibration.py`** — `OofLogisticCalibrator` (`calibration.json`), discrimination/calibration/class-specific metrics with stratified bootstrap 95% CIs (reusing `research.uci412.evaluation.calculate_metrics`), prevalence-shift prior-odds diagnostics, and **descriptive outer-fold model dispersion** (`compute_fold_prediction_dispersion`, applying each outer fold's own inner-OOF-fitted calibrator without claiming validated epistemic uncertainty or clinical action thresholds).
- **`ai/explainability.py`** — Exact **Grouped Interventional LinearSHAP** (derived in closed form on `calibrated_log_odds` when paired with an `exact_raw_log_odds` logistic calibrator, or on `raw_log_odds` when uncalibrated) and Exact **Grouped Interventional TreeSHAP** (on `raw_model_probability` for `constrained_random_forest`, never mislabeled as calibrated-probability SHAP), verified against $2^M$ coalition enumeration. Explicitly marks `shap_background.json` as an encoded training-row derivative (`reconstructible_with_preprocessor_stats = true`).
- **`ai/lime_explainability.py`** — Genuine **local tabular LIME** implemented from first principles (no external `lime` dependency): seeded binary-mask perturbations over validated clinical/laboratory fields, reference values decoded from the training background (registered categorical codes, in-range numerics, explicit optional-missing states) under one of two registered reference schemes (`fixed_background_reference` — numeric background median / modal registered code, the default; or `sampled_background_marginals`, the classic but reference-noise-limited comparator), an exponential normalized-Hamming kernel, and a kernel-weighted ridge local surrogate fitted exclusively on **actual estimator calls**. Every explanation declares its target (`calibrated_log_odds` / `raw_model_log_odds` / `raw_model_probability`), states `is_exact = False` and `additive_decomposition_claim = False`, and reports local-fidelity (absolute, relative and neighborhood-σ-scaled), weighted/held-out R², effective sample size, condition number, model rows/calls, memory footprint, runtime, and multi-seed stability. `assert_comparable_explanation_scales` refuses SHAP↔LIME numeric comparison on incompatible scales; hard numerical ceilings fail closed. Generation only: it attaches but never sets the acceptance thresholds.
- **`ai/lime_quality.py`** — Generation-free **LIME explanation-quality assessment**: `LimeQualityPolicy` (documented variance-explained / σ / condition-number / rank-agreement thresholds), `LimeQualityEvidence`, `LimeQualityCriterion`, `LimeQualityAssessment` and five machine-readable verdicts — `ACCEPTABLE_LOCAL_APPROXIMATION`, `LOW_LOCAL_FIDELITY`, `UNSTABLE`, `UNVERIFIED_STABILITY`, `INVALID` — with documented precedence, per-dimension outcomes (`numerical_validity`, `instance_fidelity`, `neighborhood_fidelity`, `stability`), per-criterion evidence, warnings and an explicit "DO NOT RELY ON THESE FEATURE WEIGHTS" guard for anything not accepted. `require_acceptable_lime_quality` fails closed for callers that demand a certifiable explanation.
- **`ai/filesystem_security.py`** — Cross-platform private-file and directory access-control enforcement & verification: POSIX `0600`/`0700` + UID checks on Linux/macOS and Win32 NTFS Security-Descriptor DACL enforcement & binary ACE inspection (`D:PAI` user-only + `SYSTEM`/`Administrators`, `FILE_PERSISTENT_ACLS` volume check, symlink/junction/reparse-point rejection, and case-normalized path containment) on Windows Python 3.12 without trusting `os.chmod` or CRT `stat.st_mode` bits.
- **`ai/training.py`** — Fold-contained nested-CV selection separating (1) **uncalibrated nested-CV performance**, (2) **independently evaluated cross-fitted calibrated nested-CV performance** (where every evaluated observation is excluded from fitting both its prediction model and its calibrator), and (3) the **final development-OOF calibrator** (whose resubstitution numbers are explicitly isolated as an apparent diagnostic); plus label-shuffle negative controls and `evaluate_locked_external_cohort` (frozen-model evaluation primitive with optional locally protected two-phase `ExternalEvaluationLedger` (`RESERVED` -> `COMPLETED` | `FAILED`) enforcing cross-process locking, failure auditability, and identical-provenance recovery).
- **`ai/packaging.py`** — Staging-directory atomic `RESEARCH_ONLY` bundle writer (`manifest.json`, `model.joblib`, `preprocessing.json`, `calibration.json`, `shap_background.json`, `evaluation_summary.json`, `protocol.md`; full cleanup on interrupted/failed writes), separating SHA-256 self-consistency (`verify_research_bundle`) from trusted-local-origin authentication (`verify_trusted_local_bundle`: `trusted_local_root` containment + POSIX `0600`/`0700` or verified Windows NTFS DACL isolation + `HMAC-SHA256` local producer attestation) required before `joblib.load`.
- **`ai/inference.py`** — Offline `ResearchCadPredictor` enforcing `verify_trusted_local_bundle` before deserialization and returning explicitly separated `raw_model_score`, `raw_model_log_odds`, `calibrated_research_score`, `calibrated_log_odds`, descriptive fold dispersion, aligned SHAP attributions, an optional scale-aligned LIME explanation with its stability report and quality verdict, and mandatory non-clinical limitations.
- **`ai/validation_harness.py`** (`scripts/validate_ai_windows_compat.py`) — Self-contained 8-step synthetic validation runner for Windows Python 3.12 (NTFS) and POSIX environments.
- **`ai/cli.py`** (`python -m ai`) — Offline synthetic-demo command-line interface (`panels`, `verify-bundle`, `predict`, `demo`) layering only argument handling, output serialization, and a synthetic-only provenance/profile guard over the existing packaging verification and `ResearchCadPredictor.predict_research_only` engine. It never deserializes before trusted verification, never predicts with real-provenance bundles or non-synthetic inputs, and never prints local paths, key material, or submitted feature values.

## Local CLI usage (AI-4.1) — Windows Python 3.12

All commands are offline, synthetic-only, and exit with code `2` (fail closed, structured JSON error on stderr) for invalid inputs or untrusted/compromised bundles. From the repository root in PowerShell:

```powershell
py -3.12 -m venv .venv-ai
.\.venv-ai\Scripts\Activate.ps1
python -m pip install -r research\experiments\requirements.txt
python -m pip check

# Registered panels, required features, input types, profile status
python -m ai panels

# Isolated end-to-end synthetic demo (train -> package -> verify -> load -> predict; temp artifacts deleted)
python -m ai demo

# Retain a demo bundle on an NTFS volume OUTSIDE the repository, then verify + predict
$Work   = Join-Path $env:LOCALAPPDATA "CardioAssistAI\ai41-demo"   # must be a fresh directory
python -m ai demo --work-dir $Work
$Bundle = Join-Path $Work "trusted_bundles\synthetic_demo_bundle_v1"
$Root   = Join-Path $Work "trusted_bundles"
$Key    = Join-Path $Work "private_keys\local_bundle_hmac_v1.key"
python -m ai verify-bundle --bundle-dir $Bundle --trusted-root $Root --signing-key-path $Key
python -m ai predict --bundle-dir $Bundle --trusted-root $Root --signing-key-path $Key `
  --input ai\examples\synthetic_da_a2_resting_labs_v1.json

# Focused + pipeline regression tests
python -m pytest tests\experiments\test_ai_cli.py tests\experiments\test_ai_research_pipeline.py -q

# Cleanup (demo bundle + isolated demo signing key; never commit either)
Remove-Item -Recurse -Force $Work
deactivate
```

Notes: `--format text` renders the same quantities for console reading (JSON is the default). `verify-bundle --integrity-only` checks SHA-256 integrity only and never authenticates or authorizes loading. `predict` additionally accepts `--expect-panel`, `--expect-profile`, and `--expect-model-family` guards. The committed example input (`ai/examples/synthetic_da_a2_resting_labs_v1.json`) contains invented synthetic values only. Real-provenance bundles, the frozen `CLEVELAND_D047_FROZEN_V1` profile, and any input without `"synthetic": true` are rejected before deserialization; they remain reachable only through their existing guarded workflows. The same `python -m ai ...` commands work unchanged on POSIX.

## Local LIME usage (AI-5.1) — Windows Python 3.12

LIME is an explicitly **local approximation**, never an exact Shapley method and never clinical advice. It is also **never reported as trustworthy by default**: every explanation carries a machine-readable quality verdict, and anything that is not `ACCEPTABLE_LOCAL_APPROXIMATION` is returned for diagnostic inspection only, with feature weights explicitly marked as unusable.

All commands below are offline and synthetic-only; real-provenance bundles and non-synthetic inputs remain rejected before deserialization.

```powershell
# End-to-end synthetic demo: genuine SHAP + genuine LIME + certified quality verdict
python -m ai demo --format text

# Single verified synthetic bundle with an explicit LIME request.
# Stability is assessed by default (three registered seeds) so the verdict can
# reach ACCEPTABLE_LOCAL_APPROXIMATION instead of UNVERIFIED_STABILITY.
$Work   = Join-Path $env:LOCALAPPDATA "CardioAssistAI\ai51-demo"   # fresh directory, outside the repo
python -m ai demo --work-dir $Work
$Bundle = Join-Path $Work "trusted_bundles\synthetic_demo_bundle_v1"
$Root   = Join-Path $Work "trusted_bundles"
$Key    = Join-Path $Work "private_keys\local_bundle_hmac_v1.key"
python -m ai predict --bundle-dir $Bundle --trusted-root $Root --signing-key-path $Key `
  --input ai\examples\synthetic_da_a2_resting_labs_v1.json --with-lime `
  --lime-seed 20261026 --lime-perturbations 512 --format text

# Sensitivity / strictness controls
python -m ai predict ... --with-lime --lime-stability-seeds 11,12,13,14,15
python -m ai predict ... --with-lime --lime-reference-scheme sampled_background_marginals
python -m ai predict ... --with-lime --lime-no-stability                 # verdict stays UNVERIFIED_STABILITY
python -m ai predict ... --with-lime --lime-require-acceptable-quality   # fail closed if not acceptable

# Focused AI-5.1 test modules plus the existing AI regressions
python -m pytest tests\experiments\test_ai_lime_explainability.py -q -W error
python -m pytest tests\experiments\test_ai_lime_quality.py -q -W error
python -m pytest tests\experiments -q -W error
```

Programmatic use (the same synthetic fixtures as the tests):

```python
from ai import (
    DA_A2_RESTING_LABS_PANEL,
    FoldSafeClinicalPreprocessor,
    LimeConfig,
    LimeQualityPolicy,
    ShapBackgroundReference,
    assert_comparable_explanation_scales,
    assess_lime_quality,
    assess_lime_stability,
    explain_clinical_instance,
    explain_clinical_instance_lime,
    explain_clinical_instance_lime_certified,
    require_acceptable_lime_quality,
    validate_cohort_records,
)

# ``records``/``labels``/``family``/``estimator``/``calibrator``/``i`` come from
# the synthetic fixtures and fitted models used in the AI-5.1 tests.
X, y, _ = validate_cohort_records(records, labels, DA_A2_RESTING_LABS_PANEL)
preprocessor = FoldSafeClinicalPreprocessor.fit(X, DA_A2_RESTING_LABS_PANEL)
background = ShapBackgroundReference.from_training_encoded(
    preprocessor.transform(X), y, preprocessor, max_samples=32, seed=7
)
x_raw = X[i]
z_row = preprocessor.transform(X[[i]])[0]
config = LimeConfig(num_perturbations=512, seed=20261026)

shap_explanation = explain_clinical_instance(
    model_family=family, estimator=estimator, preprocessor=preprocessor,
    panel=DA_A2_RESTING_LABS_PANEL, background=background,
    z_row=z_row, calibrator=calibrator,
)

# Generation attaches a fidelity-only verdict; it never guesses stability.
lime_explanation = explain_clinical_instance_lime(
    model_family=family, estimator=estimator, preprocessor=preprocessor,
    panel=DA_A2_RESTING_LABS_PANEL, background=background,
    x_raw_row=x_raw, z_row=z_row, calibrator=calibrator, config=config,
)
assert lime_explanation.quality_status == "UNVERIFIED_STABILITY"
comparability = assert_comparable_explanation_scales(
    shap_explanation, lime_explanation
)

# Assessment is a separate, explicit step.
stability = assess_lime_stability(
    (11, 12, 13), config=config, model_family=family, estimator=estimator,
    preprocessor=preprocessor, panel=DA_A2_RESTING_LABS_PANEL,
    background=background, x_raw_row=x_raw, z_row=z_row,
    calibrator=calibrator,
)
certified = lime_explanation.certify(stability=stability)
print(certified.quality_status, certified.is_reliable_for_interpretation)
print(certified.quality.to_dict()["warnings"])
assess_lime_quality(certified)  # re-assesses; reuses the attached stability evidence

# ... or one call that generates and certifies, optionally failing closed.
verified, stability = explain_clinical_instance_lime_certified(
    stability_seeds=(11, 12, 13), quality_policy=LimeQualityPolicy(),
    model_family=family, estimator=estimator, preprocessor=preprocessor,
    panel=DA_A2_RESTING_LABS_PANEL, background=background,
    x_raw_row=x_raw, z_row=z_row, calibrator=calibrator, config=config,
)
require_acceptable_lime_quality(verified)  # raises lime_quality_not_acceptable
```

`ResearchCadPredictor.predict_research_only(..., lime_config=LimeConfig())` attaches the LIME explanation, its stability report and its quality verdict to the `RESEARCH_ONLY` result, refuses any LIME target that is not on the same declared scale as the SHAP explanation, and adds a `LIME quality verdict: ...` limitation line. Set `lime_stability_seeds=None` to skip stability (verdict capped at `UNVERIFIED_STABILITY`) or `lime_require_acceptable_quality=True` to fail closed.

### Verdicts (documented precedence)

| Status | Meaning |
|---|---|
| `INVALID` | A numerical-validity criterion failed (effective sample size, condition number, non-finite/all-zero weights, missing attributions). Nothing may be read from the weights. |
| `LOW_LOCAL_FIDELITY` | Instance or neighborhood fidelity failed **or could not be demonstrated** (an unproven fit is not accepted). Includes the classic trap: a surrogate that matches `f(x)` closely while explaining the neighborhood poorly. |
| `UNSTABLE` | Locally faithful, but the weights disagree across the registered seeds. |
| `UNVERIFIED_STABILITY` | Locally faithful, but no stability evidence was supplied while the policy requires it. |
| `ACCEPTABLE_LOCAL_APPROXIMATION` | Every registered criterion passed. Still a local approximation — not an exact Shapley decomposition, not additive in probability units, never causal or clinical advice. |

Default thresholds (variance-explained, σ-scaled error, condition number, rank agreement) are stated in `ai/lime_quality.py` with their rationale; they are **not** tuned per fixture and cannot be relaxed by a generation config. `LimeConfig` carries no acceptance threshold at all.

**Scientific limits (binding):** LIME weights are local surrogate coefficients for "field keeps the instance's value" versus "field takes a reference value from the decoded training background". They are **not** Shapley values, are **not** additive in probability units, do **not** satisfy local accuracy/efficiency, are conditional on the perturbation distribution, reference scheme, kernel width, ridge penalty and seed, and are **never** causal effects, individual risk estimates, or clinical advice. Stability, instance fidelity and neighborhood fidelity are independent properties; passing one never implies another. The `fixed_background_reference` scheme uses per-field background medians/modal codes, so development-cohort inter-feature correlations are still not preserved and no reference value is ever emitted in an explanation.

## Governance, Security & Runtime Boundaries

- **Gate PT (`P-3`) & `D-021` remain CLOSED:** Real-data training and real external cohort execution (including real Hungary and real AngioCAD) fail closed; CI executes exclusively on generated in-memory synthetic cohorts (`tests/experiments/test_ai_research_pipeline.py`).
- **SHA-256 != pickle safety:** `manifest.json` SHA-256 digests detect accidental corruption only; never pass untrusted bundles to `joblib.load`. `ResearchCadPredictor.from_verified_bundle` requires an explicit user-owned `trusted_local_root` and valid local `HMAC-SHA256` producer signature.
- **Sensitive training derivatives (`shap_background.json`):** Encoded background rows can be inverted using `preprocessing.json` scaling parameters; real-patient backgrounds are blocked while `P-3` is closed and must never be committed, uploaded, or shared publicly.
- **Isolated from `/v1` HTTP serving (`M1c`):** `backend/app/` never imports `ai/`, and `MOCK_SYNTHETIC` remains the sole active FastAPI provider.
