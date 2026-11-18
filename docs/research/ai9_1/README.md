# AI-9.1 — Same-source paired clinical vs routine labs (synthetic engineering)

**Current status:** proposed implementation PR, not yet merged or locally accepted. **All observations, labels and additional laboratory values are fabricated in process.** This is not a real-source lab study, a clinical probability comparison, or evidence that adding any lab improves CAD prediction.

## What this code actually compares

For one fabricated **DA-A2 / Cleveland-style** source cohort, the runner compares the registered `da_a2_resting_v1` panel (five features: `age, sex, cp, trestbps, restecg`) against `da_a2_resting_labs_v1` (same five plus invented `chol, fbs`). These are **panel descriptions only**, not authorization to execute the separately blocked real/labs route. The sole public command generates its own synthetic records; there is deliberately **no input-dataset, model-bundle, external cohort or patient-data argument**.

Both arms use **identical generated pseudopatient IDs, labels, source-specific target, outer folds and training/test positions**. Matched IDs are checked and reordered internally, never silently paired by row position. Labels, target IDs, panel version/hash and shared clinical features must agree before fitting. Only registered panel fields, units, permitted synthetic context and explicit missing lab reasons are accepted by the existing `ai.panels.validate_clinical_record` validator. A synthetic flag alone does not authorize real data; this experiment never accepts caller-provided cohort inputs through its public command.

The pipeline **reuses** `FoldSafeClinicalPreprocessor`, `ai.training._select_best_params_and_inner_oof`, the reviewed L2 logistic estimator, and `OofLogisticCalibrator`. For each of three shared outer folds, both arms independently refit preprocessing and inner selected regularization on the **outer training patients only**. The calibrator fits exclusively to **inner OOF predictions inside outer training**; neither model nor calibrator fits on the outer test rows. The two arms use the same fixed model family to limit comparison differences to the additional fields, rather than automatically changing model family.

## Reported observables and scope

A versioned JSON report, validated against [`synthetic-paired-comparison.v1.schema.json`](synthetic-paired-comparison.v1.schema.json), includes:

- cohort counts and missing `chol/fbs` denominators;
- exact panel IDs, versions and SHA-256, source/target identity and matched outer fold checksums;
- per-arm fold-training counts, encoded coefficient/parameter accounting, and inner-fitted calibration scope;
- discrimination (AUROC, average precision) and calibration diagnostics (Brier, ECE, Cox);
- **paired labs-minus-clinical AUROC/Brier deltas** and stratified **paired** percentile intervals.

**Interval limitation:** Bootstrap resamples the already fixed out-of-fold predictions of the **same synthetic participants** (paired within resample); it **does not refit the model, repeat nested CV, quantify training/selection uncertainty, establish sample-size adequacy, or license clinical inference**. ECE deltas are **descriptive only**. No favorable-lab performance assertion or threshold-based care rule is produced. Lab values are invented primarily from age and random noise and were **not** generated to prove additional value.

## Commands — Windows PowerShell 5.1

From a separate clean worktree for the reviewed PR commit, using the maintainer's existing pinned Python 3.12 research environment:

```powershell
$ErrorActionPreference = 'Stop'
$Python = 'C:\Users\wifi\AppData\Local\CAI12-manual-641458d68d14\venv\Scripts\python.exe'
& $Python -m pytest -W error -q -ra --tb=short tests/experiments/test_ai9_paired_synthetic.py tests/contracts/test_ai9_paired_synthetic_schema.py
if ($LASTEXITCODE -ne 0) { throw 'Focused AI-9.1 tests failed' }
$Out = Join-Path $env:LOCALAPPDATA ('CAI9-1-Results-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $Out -ErrorAction Stop | Out-Null
$File = Join-Path $Out 'synthetic-paired.json'
& $Python scripts/run_ai9_synthetic_comparison.py --output $File
if ($LASTEXITCODE -ne 0) { throw 'AI-9.1 synthetic comparison failed' }
```

The script exclusively creates a **new** external `.json` file; it rejects existing and repository-contained destinations. The same fixed seed and package set should reproduce the JSON byte-for-byte on the same machine. For actual acceptance run source integrity, native Windows security harness, appropriate existing regression tests and the full applicable `pytest -W error` suite at the **exact reviewed head**; report the real exit codes, skips and warnings. Merge only after human review; smoke the exact merge SHA on Windows and record evidence in a later docs-only tracking PR. Older AI-11 tests do **not** count as AI-9.1 acceptance.

## Explicit research NO-GO

The model system targets **source-defined angiographic obstructive CAD in referred populations**, not 30-day events. Routine-labs real assessment still requires proven pre-angiography measurement time, eligible identical patients, source semantics, scientific protocol and separate permission. In particular the blocked `da_a2_resting_labs_v1` route is **not** activated by merely using its panel schema on fabricated data. UCI-412 feature semantics remain `SCIENTIFIC_HOLD`. Real Hungary remains a separately locked independent test cohort. The application backend remains `MOCK_SYNTHETIC`; no model endpoints, patient input, real scoring, new ethical permission or clinical validation is introduced.

**Next:** evaluate tests/CI for the proposed code head, perform local Windows acceptance, then update `ai_master_progress.json` only after separately reviewed and merged acceptance evidence.
