# RH-04 numerical reproducibility: SkylakeX pin trial rejected on hosted CI

**Status: BLOCKED. Do NOT merge draft PR #134.**

This document supersedes Arena's initial proposal to pin the OpenBLAS
`SkylakeX` dispatch in GitHub Actions. The original agent's GitHub token
could not edit workflow files; a connected reviewer temporarily applied the
pin **with a mandatory AVX-512 hardware safety check** to the PR #134 branch,
observed an incompatible GitHub-hosted runner, and reverted the workflow file
to match `main`. The rejected experiment's CI logs remain available.

## What was verified

- Original defect: the frozen 29-case RH-04 synthetic fixture can differ by
  `4.441e-16` at `da_a1_basic_clinical_v1` /
  `calibrated_log_odds`. `main` keeps the frozen fixture hash and exact
  UCI-412 comparator unchanged. The source-specific synthetic runner can be
  green on a retry with the same SHA even when an earlier execution was red.
- Arena's locally reported Python 3.11 experiment suggests the difference
  originates in SciPy L-BFGS-B calibration optimization and OpenBLAS kernel
  dispatch. It reported the golden-compatible fit under `SkylakeX` and a
  reproducible low-bit mismatch under forced `Haswell`. This is useful evidence
  but does not itself demonstrate **portable** binary64 reproducibility.
- Reviewer-applied experiment on PR #134:
  - Job-level `OPENBLAS_CORETYPE: 'SkylakeX'` was tested together with
    unchanged single-thread BLAS settings and a fail-closed hardware check.
  - The real GitHub-hosted runner for [Python 3.12 synthetic runner
    job](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/44901748832/job/136838961519)
    and [independent RH-04 diagnostic
    job](https://github.com/Muhammed-Fathi/CardioAssist-AI/actions/runs/44901748832/job/136838961533)
    did **not** expose `avx512f`. Both refused to start SkylakeX.
  - The synthetic runner's subsequent missing-numpy message on that job is a
    cascading effect of the refused preflight/install, **not** a new model bug.
  - The risk is confirmed: force-pinning the required AVX-512 kernel is unsafe
    or unavailable on a normal GitHub runner lacking those CPU instructions.
    The temporary workflow pin was **reverted** on the draft branch; do not
    reapply it blindly.

## Consequences

A hardware-specific `SkylakeX` pin cannot be the sole fix for the existing
`ubuntu-24.04` shared-runner CI. GitHub-hosted virtual CPUs do not have a
contract guaranteeing AVX-512. Pinning hardware-specific kernels must be
guarded by hardware capability checks and requires a compatible runner.

The new test file `tests/experiments/test_rh04_calibration_dispatch.py`
contains useful synthetic-only coefficient, response, SHAP and source-integrity
checks. Its workflow-structure guard was strengthened to **fail closed**
(no `pytest.skip`) if the required job-level pin is absent, so PR #134
remains intentionally **BLOCKED/RED** rather than silently accepting an
unimplemented remedy.

## Portable fix investigation — next steps for Arena

1. Inspect `ai.calibration.OofLogisticCalibrator.fit_from_oof`, particularly
   the SciPy L-BFGS-B gradient/objective and its 2-parameter fit. Establish
   experimentally where bit-level drift enters **relative to a trusted
   baseline**, without outputting numerical model parameters or scores to
   public CI logs.
2. Investigate portable deterministic operations for the calibration fit
   across Python 3.11/3.12 and at least Haswell/SkylakeX-class CPUs.
   A code-level remedy must preserve scientific calibration semantics,
   SHAP alignment and consumer responses. Do not hardcode a golden
   intercept/slope for known fixture cases.
3. If exact matching of already-frozen numerical fixtures is mathematically
   infeasible across arbitrary architectures, propose a **formal, explicit,
   separately approved engineering policy**. Never silently regenerate
   fixtures, weaken the golden comparator, hide an actual failure, or bypass CI.
4. Put any validated change on a **new isolated Draft PR** with exact SHA,
   positive and negative tests, CI logs and Windows-local testing instructions
   when needed. Do not merge PR #133 (diagnostic experiment) or PR #134
   (blocked hardware-specific proposal) as a remedy.
5. Keep Issue #132 **OPEN** until independent source inspection,
   reproducibility evidence and owner acceptance. No clinical inference,
   real-patient data or real-study metrics are implicated by this CI trial.

Upstream references:
- https://www.openmathlib.org/OpenBLAS/docs/runtime_variables/
- https://www.openmathlib.org/OpenBLAS/docs/faq/
- https://docs.github.com/en/actions/reference/runners/github-hosted-runners

**No frozen fixture, canonical source hash, output score, scoring code,
tolerance, registry permission or synthetic-only boundary was changed.**
