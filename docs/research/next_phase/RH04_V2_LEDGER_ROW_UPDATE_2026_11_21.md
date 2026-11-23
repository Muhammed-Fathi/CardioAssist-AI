# WITHDRAWN — V2-01 … V2-10 Round 8 status

> **THIS DOCUMENT IS WITHDRAWN AND MUST NOT BE USED AS AN ACCEPTANCE RECORD.**
>
> It reassigned the meanings of the V2 acceptance IDs. The controlling meanings
> in `docs/rh04-issue132-acceptance-decision.md` §7 were not followed: rows labelled
> V2-01…V2-07 here describe implementation work, not the acceptance gates those
> IDs actually name. It also implied progress toward V2-04 that a toy Path B test
> does not provide and V2-01 that only the owner can ratify.
>
> Superseded by
> [`RH04_V2_ACCEPTANCE_LEDGER_RESTORED_2026_11_21.md`](RH04_V2_ACCEPTANCE_LEDGER_RESTORED_2026_11_21.md),
> which restores the original meanings and separates implementation-task IDs from
> acceptance-gate IDs. Retained unmodified below as historical evidence of the
> error.


Head `cd0209b` · base #138 `2469dc6` · PR #139 **Draft/Open** · Issue #132 **OPEN**.
Nothing below is ratified. No acceptance semantics are active.

| ID | Status | Evidence | Blocker |
|---|---|---|---|
| **V2-01** | **CORRECTED** | Reversed calibration parameters fixed; max \|Δ\| 4.262104 measured; regression pins the real `OofLogisticCalibrator` contract | needs reviewer sign-off on the 3-version digest history |
| **V2-02** | **CORRECTED** | Two declared profiles; intercept penalty confirmed by gradient (7.157e-04 vs 9.160e-09) | none local |
| **V2-03** | **DELIVERED (candidate)** | 29 cases executed twice → identical `aea7d617…`; 3 families measured, not assumed | not an acceptance pack; `FULL_REFERENCE_SENTINEL` |
| **V2-04** | **DELIVERED (candidate)** | Path B round trip exact; refusals fire | **D-V2-7 unratified** — Path A remains the only reference path |
| **V2-05** | **BLOCKED** | Full reference is **not** kernel-invariant (2 resolved classes measured) | needs a decision on acceptable cross-kernel scope, or a ratified portability story |
| **V2-06** | **OPEN** | Requested ≠ resident proven (`Prescott`→NumPy Prescott, SciPy **Katmai**) | no third class locally; Python 3.12 and native Windows not measured |
| **V2-07** | **CORRECTED** | Exit grid 0 mismatches / 8 cells vs the real classifier; tautology removed | separate reviewable commit — done, needs review |
| **V2-08** | **PARTIAL** | V1→candidate mapping is 2/29 on exactly the 4 calibrated paths | §8 `pipeline_digest()` still excludes `declared` |
| **V2-09** | **PARTIAL** | Oracle fails closed; 1e-16 agreement; convergence bound 1e-30 (derived) | `1e-16` is agreement, **not** proof of identical binary64 rounding — worded as such |
| **V2-10** | **PARTIAL** | 140 + 906 passing; 7 frozen files byte-identical | hosted CI not re-run; native Windows unmeasured; 3.12 unmeasured |

## Blockers requiring an owner decision

1. **V2-05 portability scope.** The full reference is kernel-sensitive by
   construction. Either accept a per-class expectation table, or ratify that the
   full reference is host-scoped and only the isolated pipeline is portable.
2. **§8 `declared` binding.** `pipeline_digest()` still excludes `declared`, so
   the algorithm declaration is not yet integrity-bound. Not yet changed because
   it moves the digest again and needs its own reviewable commit.
3. **D-V2-7.** Frozen-parameter reuse is demonstrated and refused-safe, but
   unratified. The accepted regeneration requirement still stands.
4. **Hosted CI.** `091b26c` had zero check runs; `cd0209b` is unpushed to CI by
   instruction ("do not rerun hosted CI until green"). No green claim is made.

## Explicit non-claims

- Finite-precision Decimal arithmetic is **not** mathematically exact; the
  golden-section line minimisation converges to a tolerance and the document says
  so.
- `1e-16` is an observed agreement threshold, **not** a proof of identical
  binary64 rounding.
- SHAP/LIME reproducibility does **not** follow from fixed coefficients; they are
  outside the 29-case exported scored fields and need separate RH-07 evidence.
- `1e-16`-scale classification agreement does **not** establish exact
  classification; no threshold-sign test with an arbitrary near-zero allowance is
  used as evidence.
