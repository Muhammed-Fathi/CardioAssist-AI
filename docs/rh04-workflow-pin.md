# RH-04 OpenBLAS dispatch pin — reviewer-applied experiment, not yet accepted

**Status:** The initially uncommitted workflow patch was applied to the **draft
PR #134 branch** by a separate GitHub-connected reviewer because Arena's token
lacked the workflow-edit permission. This document records the original agent
hypothesis and the safety additions. **Do not merge** until exact-head checks
and owner review are complete. Issue #132 stays open until validated.

## Empirical hypothesis (agent-reported, not a portability guarantee)

The frozen 29-case RH-04 synthetic fixture sometimes differs in
`da_a1_basic_clinical_v1` at `calibrated_log_odds` by `4.441e-16`.
The agent's Python 3.11 local reproduction attributed the difference to
OpenBLAS kernel dispatch during SciPy L-BFGS-B calibration fitting, observing:

- Golden-compatible reference: `intercept=-0.8264874886346654`,
  `slope=1.6547968324340276`, `calibrated_log_odds=2.6971396718292335`.
- Forced Haswell: `intercept=-0.8264874886346656`,
  `slope=1.6547968324340279`, `calibrated_log_odds=2.697139671829234`.
- Raw model probability/log-odds and calibrated probability matched in the
  source-isolation trace; the final log-odds did not.
- Frozen fixture JSON, SHA-256 digest, canonical comparator and tolerances
  must remain unchanged.

These findings are narrower than proof of bit-exact reproducibility across
all processors or operating systems. A green CI run alone does not establish
long-term stability; native Windows remains out of scope for this CI trial.

## Applied CI settings and guards

In `.github/workflows/experiment-runner-ci.yml`, **both**
`synthetic-runner-tests` (Python 3.11/3.12) and
`rh04-fixture-diagnostic` (Python 3.12) have job-level environment:

```yaml
OPENBLAS_NUM_THREADS: '1'
OMP_NUM_THREADS: '1'
MKL_NUM_THREADS: '1'
BLIS_NUM_THREADS: '1'
NUMEXPR_NUM_THREADS: '1'
VECLIB_MAXIMUM_THREADS: '1'
OPENBLAS_CORETYPE: 'SkylakeX'
```

Before installing or importing numerical libraries, each job checks Linux CPU
flags for `avx512f avx512dq avx512bw avx512vl`. **An incompatible runner
fails closed with a clear error instead of attempting unsafe SkylakeX kernels
or falling back silently.** After installation, the existing threadpool
preflight additionally verifies that OpenBLAS actually reports architecture
`SkylakeX`, not merely that an environment variable was set.

GitHub-hosted runners use virtual machines; the `ubuntu-24.04` job label
**does not guarantee AVX-512 capabilities**. This restricted kernel pin is
therefore **not a portable final fix**. If hardware is incompatible, leave the
job red and investigate a processor-independent deterministic calibration
strategy separately. Do not skip tests, regenerate historical golden fixtures,
disable the source-integrity guard, or relax UCI-412 exact matching merely to
obtain green checks.

Primary upstream documentation:
- https://www.openmathlib.org/OpenBLAS/docs/runtime_variables/
- https://www.openmathlib.org/OpenBLAS/docs/faq/
- https://docs.github.com/en/actions/reference/runners/github-hosted-runners

## Acceptance checklist

1. On the **same exact PR head**, the workflow hardware preflight proves the
   required AVX-512 capabilities and the runtime reports `SkylakeX`.
2. The workflow-structure guard
   `test_workflow_pins_openblas_core_type_and_threads` is **not skipped**
   and verifies **both job-level** pins and preflights.
3. Python 3.11 and 3.12 complete the full synthetic experiment-runner tests,
   including the 29-case strict Golden Replay, and Python 3.12's independent
   RH-04 diagnostic completes both exact replays.
4. Negative tests and blocked/nonclinical synthetic-only route restrictions
   remain unchanged; no patient data enters CI.
5. Review flaky-run history and assess whether repeated controlled runs or
   independent Windows-local evidence are needed; do not claim a definitive
   root-cause fix from one successful run.
6. Owner and independent reviewer evaluate the results before changing PR
   #134 out of Draft or resolving Issue #132. Do not merge PR #133's
   deliberately mismatch-producing Haswell experiment as a remedy.

**No frozen numerical score, fixture digest, comparator, model training logic,
registry permission or scientific evidence claim is changed by this proposal.**
