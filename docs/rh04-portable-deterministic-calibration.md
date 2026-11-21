# RH-04: CPU-portable deterministic calibration fit — investigation and proposed acceptance policy

**Status: investigation complete. No production change is merged; no fixture, hash, tolerance, comparator or workflow file is modified by this work.**

This document is the complete, self-contained investigation record for the RH-04
exact-Replay drift (`da_a1_basic_clinical_v1`, frozen 29-case pack
`0307b396cea1e620c4004647e1d82ff7f292bb5b74de7cad1661e1299c6e7049`). It is written for
independent review; it does **not** implement an acceptance policy.

## 1. The failure

- The frozen 29-case golden replay is strict: exact equality of every non-exception
  field, including `calibrated_log_odds` for `da_a1_basic_clinical_v1`.
- On hosts whose default OpenBLAS dynamic-arch dispatch resolves to something
  other than the golden-generation dispatch (observed on Linux/x86-64 CI runners
  of Haswell-class silicon), `calibrated_log_odds` drifts by 1 ULP
  (`4.441e-16`; the `da_a2_resting_v1` case drifts by `2.220e-16`), so the exact
  Golden Replay fails.
- The frozen fixture and its hash remain unchanged. The one approved, pre-existing
  exception for the `calibrated_log_odds` field of `da_a2_resting_v1` is
  deliberately **not** reused for `da_a1_basic_clinical_v1`.

Evidence (all runs on this branch, default or forced OpenBLAS dispatch):

| Dispatch | intercept | slope | calibrated_log_odds |
|---|---|---|---|
| SkylakeX (golden) | -0.8264874886346654 | 1.6547968324340276 | 2.6971396718292335 |
| Haswell | -0.8264874886346656 | 1.6547968324340279 | 2.697139671829234 |

Diagnostic tool (`python -m research.intake.diagnose_fixture_replay`):

- default dispatch (SkylakeX-class): `EXACT_REPLAY`, 0 of 29 cases differing
- `OPENBLAS_CORETYPE=Haswell`: `MISMATCH_FOUND`; the only fields that differ are
  `calibrated_log_odds` in `da_a2_resting_v1` (2.220e-16, within the approved
  tolerance exception) and `da_a1_basic_clinical_v1` (4.441e-16, not covered by
  any exception). Everything else — model family, OOF probability pipeline, SHAP,
  statuses, thresholds, score shapes, digests — is bit-identical.

## 2. Where the drift enters

`OofLogisticCalibrator.fit_from_oof` calls `scipy.optimize.minimize(..., method="L-BFGS-B")`.
The two-parameter problem (a 2-element vector, `maxcor=10`, box bounds
`[(-15,15),(0.01,15)]`) is optimized by scipy's C `__lbfgsb` library, whose
core arithmetic calls the tied BLAS kernels `dcopy_`/`ddot_`/`daxpy_`/`dscal_`
and `dtrsl`/`dtrtrs`.  For the sizes involved these are **not** scalar paths:
`ddot_` at sizes around 10–110 (e.g. `col*(col+1)` for `col` in 1..10, and the
`n=2` projected-gradient inner product) dispatch to SIMD-reduction kernels whose
accumulation order depends on the host's dynamic-arch selection.

Empirical verification on this host (forced dispatches):

- The Python-side objective and gradients (`np.mean`, `np.logaddexp`,
  `scipy.special.expit`, `np.mean(diff * logits)`) are **bit-identical** across
  SkylakeX and Haswell dispatches — the drift does not enter there.
- `np.dot` at sizes 10, 20, 50, 110, 120, 128, 256 produces different results
  between SkylakeX and Haswell dispatches (1 ULP, e.g. -3.04831577842554 vs
  -3.0483157784255397).
- The per-iteration L-BFGS-B trace matches between dispatches for iteration 0 and
  diverges at iteration 1 (1 ULP in the intercept), confirming the divergence
  enters inside the C library's step/line-search arithmetic.
- The frozen golden was produced under the golden-generation host's dispatch; it
  is an artifact of that specific kernel arithmetic, not a portable constant.

Everything else in the pipeline — cohort selection, OOF probabilities
(`safe_clipped_logit`), model family, bootstrap, SHAP, the facade response and
digest — is bit-identical across dispatches (verified).

## 3. Why a bit-exact portable reproduction is not achievable

A CPU-portable fix would have to reproduce the frozen golden bit-for-bit on every
supported CPU. That is impossible for a code-only change, because the frozen
fixture embeds a result of a CPU-dispatched SIMD arithmetic. Specifically:

- If the fit keeps scipy L-BFGS-B, the result depends on the host's dispatch —
  exactly the current failure.
- If the fit is replaced by a deterministic CPU-portable algorithm (the
  remedy in this document), it is bit-identical across CPUs, but it converges to
  the mathematical argmin of the same objective — which differs from the
  frozen golden, which is a stopping criterion artifact of L-BFGS-B (it stops at
  a projected-gradient ceiling, not at machine precision).  Measured on the
  golden cohort: intercept delta ≈ 1.08e-6, slope delta ≈ 5.9e-7,
  calibrated_log_odds delta ≈ 1.9e-7 (relative delta ≈ 7e-8). This is **not** a
  bit-exact match and cannot be made one without either (a) hiding the
  hardware-specific arithmetic in the portable code path (i.e. re-implementing
  SkylakeX's SIMD reductions by hand — the same hardware specificity in a
  portable costume), or (b) freezing new constants that happen to equal the
  golden (forbidden).

Therefore the exact Golden Replay cannot pass on an arbitrary CPU while the
fixture, its hash, tolerances and the frozen comparator remain unchanged. This
is the fundamental, honest boundary of a portable code-level fix.

## 4. The CPU-portable deterministic remedy (provided, not wired-in)

The repository now provides `ai.calibration.deterministic_logistic_fit` — a
fully-portable, deterministic two-parameter L2-anchored logistic fit:

- pure-Python float64 scalar arithmetic (no BLAS/OpenBLAS/LAPACK calls, no
  numpy pairwise-summation reductions, fixed evaluation order, no hidden
  state),
- full-Newton step with the analytic Hessian and box projection (same bounds
  and same objective as the L-BFGS-B path),
- bit-identical across `OPENBLAS_CORETYPE` dispatches (verified empirically for
  the synthetic dataset across `generic`/`Haswell`/`Sandybridge`/`SkylakeX`,
  and on the golden cohort data across SkylakeX/Haswell),
- validates the same inputs, and `fit_from_oof` dispatches to it behind
  `solver="deterministic_portable_newton"`.

**Deliberately not the default.** The default `fit_from_oof` path keeps the
scipy L-BFGS-B call so that the frozen contract and the existing exact Golden
Replay remain unchanged. The deterministic path is the CPU-portable remedy for
environments where the golden is not the contract (e.g. fixture re-certification,
other references). It is explicitly documented as a *numerical-stability*
remedy, never a bit-exact reproduction of the frozen golden.

Usage:

```python
from ai.calibration import OofLogisticCalibrator

cal = OofLogisticCalibrator.fit_from_oof(
    y_oof, p_oof_raw,
    model_family="constrained_random_forest",
    solver="deterministic_portable_newton",   # new, opt-in, portable
)
```

## 5. Proposed engineering acceptance policy (NOT implemented — for independent review)

The following is a **proposal only**. It must not be implemented, merged, or
reverted without explicit owner approval and its own evidence review.

**Option A — fixture re-certification (new golden).**
Adopt the deterministic portable solver as the production calibration path;
regenerate and re-freeze the 29-case golden pack from a trusted reference
machine, with a fresh digest, recorded provenance and evidence of cross-CPU
replay on the exact CI reference environment; remove or rewrite the frozen
coefficient assertions accordingly. Requires owner approval, a new frozen-pack
digest (new `fixtures.PACK_SHA256`), and full replay re-certification.
This is **not** authorized by this work.

**Option B — bounded tolerance exception (no fixture changes).**
Keep the frozen pack and comparator unchanged; add an explicitly documented,
owner-approved bounded-tolerance exception for `calibrated_log_odds` of
`da_a1_basic_clinical_v1` (analogous to the pre-existing `da_a2_resting_v1`
exception), approved by the owner with a written justification, recorded in the
report and the comparator, and only after independent review of the evidence in
this document. This is **not** authorized by this work.

Either option must come with: independent owner review of the diff, a full
regression run of `tests/experiments`, `tests/audit` and `tests/uci412`, and an
explicit statement that the exact frozen Golden Replay remains the contract
until the owner approves the transition. Until then: PR #133 and PR #134 must
remain unmerged and Issue #132 must remain open.

## 6. What is explicitly NOT included

- no hardcoded golden coefficients,
- no fixture/hash/tolerance/comparator changes,
- no workflow changes or SkylakeX pins,
- no merge of any PR,
- no new CLI or consumer-facing behavior changes; `to_json_dict` /
  `from_json_dict` / `state_sha256` semantics are identical.

## 7. Tests

- `tests/experiments/test_rh04_calibration_portable_determinism.py` — new:
  bit-identity of the deterministic solver across OpenBLAS dispatches
  (subprocess-verified), bit-reproducibility across repeated calls, bounded and
  finite parameters, input/bounds validation, contract preservation via
  `fit_from_oof(solver="deterministic_portable_newton")`, JSON round-trip,
  unknown-solver rejection, default-path contract (scipy L-BFGS-B stays default).
- `tests/experiments/test_rh04_calibration_dispatch.py` — unchanged: the
  frozen-value, frozen-response, SHAP-contract, workflow-guard and digest
  assertions remain exactly as they were on the frozen path.

## 8. residual risks and limitations

- Python 3.11 is verified locally; Python 3.12 verification is expected in CI
  (both `synthetic-runner-tests` jobs). The deterministic solver uses pure-Python
  float64 arithmetic, so Python-version drift is limited to interpreter/libc
  last-ULP differences (out of scope for the CI reference platform).
- The frozen golden remains an artifact of the golden-generation host's dispatch.
  The exact Golden Replay remains the contract only on hosts whose dispatch
  matches; on Haswell-class hosts the strict replay is known to fail and is the
  explicit subject of the policy above.
- `math.exp`/`math.log1p` last-ULP differences across libc builds are outside the
  scope of this CI-reference fixture, which is pinned to the reference platform.
