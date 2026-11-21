# RH-04 workflow dispatch pin (REQUIRED — not committed by this PR)

This file documents the **exact required workflow modification** for the RH-04
Golden Replay fix. It is **not committed** in this branch because the agent's
GitHub token does not hold the `workflows` permission needed to update
`.github/workflows/experiment-runner-ci.yml`. The Draft PR is therefore
**marked BLOCKED** until this patch is applied and the full suite is
re-validated green.

## Rationale

The frozen 29-case Golden Replay (`da_a1_basic_clinical_v1`) failed
intermittently on CI (Python 3.11 especially) with a one-ULP drift in
`calibrated_log_odds` (absolute delta `4.441e-16`). The drift entered through
the L-BFGS-B calibration fit in
`ai.calibration.OofLogisticCalibrator`, whose `_lbfgsb` C routine calls
OpenBLAS-dispatched kernels (`ddot_`, `daxpy_`, `dcopy_`) selected by the host's
default DYNAMIC_ARCH dispatch. The frozen golden intercept/slope
(`-0.8264874886346654`, `1.6547968324340276`) and `calibrated_log_odds`
(`2.6971396718292335`) match the golden-generation host's SkylakeX dispatch;
other hosts (e.g. Haswell on runners lacking AVX512F) produce ~2 ULP-different
intercept/slope and ~1 ULP-different `calibrated_log_odds`, breaking the
exact-equality Golden Replay comparator. Frozen fixtures, their digest, the
comparator and all tolerances are NOT changed by this fix.

## Exact patch

Apply to `.github/workflows/experiment-runner-ci.yml` (both
`synthetic-runner-tests` and `rh04-fixture-diagnostic` jobs):

```diff
@@ -26,6 +26,15 @@ jobs:
     # RH-04 numerical reproducibility experiment: pin BLAS/OpenMP pools before
     # Python/scikit-learn import in BOTH full suite and independent diagnosis.
     # Source fixtures, expected binary64 values and strict replay stay frozen.
+    # OPENBLAS_CORETYPE pins the exact OpenBLAS kernel dispatch used to generate the
+    # frozen RH-04 29-case golden replay (SkylakeX on the golden-generation host, the
+    # default DYNAMIC_ARCH choice on such hosts). scipy's L-BFGS-B calibration fit
+    # (ai.calibration) dispatches ddot_/daxpy_/dcopy_ to OpenBLAS kernels selected
+    # by this dispatch, so a different default dispatch (e.g. Haswell on a runner
+    # lacking AVX512F) can change the final intercept/slope by ~2 ULP and break the
+    # exact-equality calibrated_log_odds replay. Pinning the kernel makes the
+    # golden replay bit-exact regardless of the host's default dispatch. This does
+    # not modify fixtures, tolerances, or scoring.
     env:
       OPENBLAS_NUM_THREADS: '1'
       OMP_NUM_THREADS: '1'
@@ -33,6 +42,7 @@ jobs:
       BLIS_NUM_THREADS: '1'
       NUMEXPR_NUM_THREADS: '1'
       VECLIB_MAXIMUM_THREADS: '1'
+      OPENBLAS_CORETYPE: 'SkylakeX'
@@ -137,6 +147,8 @@ jobs:
     # RH-04 numerical reproducibility experiment: pin BLAS/OpenMP pools before
     # Python/scikit-learn import in BOTH full suite and independent diagnosis.
     # Source fixtures, expected binary64 values and strict replay stay frozen.
+    # Keep the same SkylakeX OpenBLAS dispatch pin as the full suite so the
+    # diagnostic verifies the production dispatch, not a stale default.
     env:
       OPENBLAS_NUM_THREADS: '1'
       OMP_NUM_THREADS: '1'
@@ -144,6 +156,7 @@ jobs:
       BLIS_NUM_THREADS: '1'
       NUMEXPR_NUM_THREADS: '1'
       VECLIB_MAXIMUM_THREADS: '1'
+      OPENBLAS_CORETYPE: 'SkylakeX'
```

## Hardware constraint

`SkylakeX` requires AVX512F support. The golden-generation host supported
AVX512F (it is the default DYNAMIC_ARCH choice on such hosts and the only
dispatch that reproduces the frozen golden bit-exactly). Any CI runner lacking
AVX512F must be retired or the golden replay regenerated via the documented
fixture process — **not** by loosening the frozen comparator.

## Validation after the patch is applied

1. Confirm the `Synthetic experiment runner` (Python 3.11/3.12) and
   `RH-04 fixture structural drift diagnostic` jobs both go green.
2. Confirm `tests/experiments/test_rh04_calibration_dispatch.py` fully passes
   (including `test_workflow_pins_openblas_core_type_and_threads`, which is
   SKIPPED until the patch is applied).
3. Then mark the Draft PR ready-for-review. Do NOT merge until ChatGPT and the
   owner have both signed off.
