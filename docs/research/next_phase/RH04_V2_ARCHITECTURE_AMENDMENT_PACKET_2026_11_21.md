# RH-04 architecture amendment — ratification packet

**Document ID:** CAI-RH04-AMEND-v3 (supersedes v1 and v2 in full)
**Status:** PROPOSAL. **Not ratified by the agent.** Zero gates closed.
**Controlling until ratified:** `docs/rh04-issue132-acceptance-decision.md` §7.

This document supersedes every earlier amendment text in this repository,
including `RH04_V2_AMENDMENT_PROPOSAL_2026_11_21.md` §§1–7. Where they conflict,
this document governs as *proposal*; where it is unratified, §7 governs as
*contract*.

---

## 1. The two lanes

### Lane A — registered synthetic regeneration

Trains, selects and calibrates through the registered producer. This is the only
lane that produces a scientific reference from data.

**Declared fit contract (observed, not assumed):**

| element | value |
|---|---|
| calibrator objective | mean log-loss + `0.5·λ·(a² + (b−1)²)`, λ = 1e-3 |
| intercept bounds | [−15, 15] |
| slope bounds | [0.01, 15] |
| solver | `scipy_lbfgsb` (L-BFGS-B) |
| stopping settings | SciPy defaults, `x0 = (0, 1)`, analytic gradient supplied |
| input link (linear route) | `exact_raw_log_odds` — exact affine map, no clamping |
| input link (tree route) | `clipped_logit_of_raw_probability` — clamp to [1e-6, 1−1e-6], then logit |
| fit scope | `FULL_DEVELOPMENT_OOF_FINAL` |
| successful status | `FITTED_OOF_MONOTONE_LOGISTIC` |

**What must be reported, per environment:** the objective value at the returned
point, the gradient norm (first-order optimality), the number of iterations, and
the fitted parameters. These are *independently evaluated residual/optimality
evidence*, not a restatement of the solver's own success flag.

**A required distinction.** Lane A must separate three outcomes that are easily
conflated:

| outcome | classification |
|---|---|
| numbers differ between environments, fit converged and status valid | **diagnostic finding** — acceptable variation to report |
| fit failed to converge, status is not the success value | **invalid** — not acceptable variation |
| evidence missing (no objective, gradient, iterations or parameters) | **invalid** — not acceptable variation |
| output malformed, non-finite, or structurally wrong | **invalid** — not acceptable variation |

Only the first row is a reportable difference. The other three are failures, and
the amendment states explicitly that they **must not** be presented as diagnostic
variation.

### Lane B — independently admitted fixed artifacts

No training, no fitting, no optimization. Rehydrates declared arrays into genuine
scikit-learn estimators and executes the registered facade over all 29 cases.

**Mandatory exact replay, no numeric tolerance, in any environment.**

**A limit that must be stated.** Lane B must **not** be described as
"host-independent because it does not train". Inference still performs floating
point work — matrix products, `expit`, tree traversal. What Lane B actually
establishes is narrower and must be stated in those terms:

> Lane B's *result* is invariant across the measured resident dispatch classes.
> That is a measured property, not a proof. It does not follow from the absence of
> training, and it must be re-measured, not deduced, for any new environment.

---

## 2. Clause amendments — original and proposed text

### V2-02 — Solver and criterion declaration

**ORIGINAL:**
> `V2-02` **Solver + criterion declaration.** Either the hardened
> `deterministic_portable_newton` (whose P0 issues recorded in Issue #132 / PR #135
> comment 2026-11-21T13:45:03Z must be *closed*, not merely patched: inward-gradient
> face pinning, Armijo sign, zero-step-with-nonzero-KKT false success, the
> tautological assertion, and deserialized-provenance mislabelling) or a documented
> alternative whose convergence test is explicitly *not* host-dependent. **The
> criterion is part of the contract.**

**PROPOSED:**
> `V2-02` **Solver + criterion declaration, per lane.**
>
> **Lane A.** The producer's objective, bounds, input link, solver, stopping
> settings and successful fit status are declared as recorded in §1 above, together
> with independently evaluated optimality evidence (objective at the returned
> point, gradient norm, iteration count, fitted parameters) for every reported
> environment. The criterion is part of the contract. Lane A **does not** claim
> host-independent convergence; it claims *credible, reported* convergence with
> explicit invalid/valid classification.
>
> **Lane B.** No fitting occurs, therefore **no fitted-solver claim is made**. Lane
> B's guarantee is exact replay of a fixed artifact, measured per environment.
>
> **Provenance.** An isolated arbitrary-precision oracle is **not** evidence of
> producer provenance. Provenance requires the registered producer, captured at its
> own boundary.

**Retained:** the requirement that the criterion is part of the contract; the
requirement that P0 issues be closed, not patched.
**Withdrawn:** the requirement that a single solver be host-independent on the
registered path, which the measured evidence does not support.
**Not withdrawn:** any V1 obligation.

### V2-03 — New pack, digest, provenance, delta mapping

**ORIGINAL:** (unchanged text, quoted in §7 of the controlling document)

**PROPOSED:**
> `V2-03` **Versioned reference pack and identities.** The V2 reference consists of
> (a) the fixed Lane B artifact set — two archive bodies plus one trusted manifest,
> each addressed by full SHA-256 and each pinned in the manifest by raw-file
> digest; (b) the manifest's own canonical identity, compiled into reviewed source
> as the trust anchor; and (c) a complete per-case, per-field mapping from every V1
> expected value to its V2 counterpart, with the numeric delta where the value is
> numeric. V1 files remain frozen and byte-identical to `main`.

**Note on naming:** this does not create `offline_io.v2.json` and does not claim
`PACK_SHA256_V2`. The Lane B artifact set is a different shape and is addressed by
raw-file SHA-256, which the amendment states rather than pretends otherwise.

### V2-04a / V2-04b — Cross-environment requirement

**ORIGINAL:**
> `V2-04` **Cross-environment replay evidence** on the new pack: ≥3 dispatch
> classes × {Python 3.11, 3.12} on Linux, **plus native Windows**, all reporting
> `EXACT_REPLAY`. Deltas-only is *not* acceptable for V2 — that is the entire point.

**PROPOSED — split, with the matrix retained in full:**
> `V2-04a` **Lane A cross-environment evidence — diagnostic.** The registered
> regeneration path is executed and reported **for ≥3 resident dispatch classes on
> Linux Python 3.11, ≥3 on Linux Python 3.12, and on native Windows**. Differences
> are reported as findings, classified per §1. Missing evidence, failed training or
> invalid output is a **failure**, not a finding.
>
> `V2-04b` **Lane B cross-environment exact replay — mandatory.** The fixed Lane B
> artifact set must report the identical reference digest **for ≥3 resident
> dispatch classes on Linux Python 3.11, ≥3 on Linux Python 3.12, and on native
> Windows**, with no numeric tolerance.

**The matrix is retained, not replaced.** The required environments are named
exactly as in the original clause — three resident dispatch classes per Linux
Python minor version, plus native Windows — and are **not** substituted by
whichever environments happened to be measurable.

**Retained:** the exactness requirement, in full, on the lane that can satisfy it;
the complete environment matrix.
**Withdrawn:** the requirement that the *training* path achieve it.

**Evidence added since this clause was drafted.** The Lane A environment dependence
is no longer inferred from one red run. The same diagnostic command on the same
frozen fixture produced `MISMATCH_FOUND` (2 differing cases) on one GitHub-hosted
runner at `f78f521` and `EXACT_REPLAY` on another at `89b0a8f`, with identical
workflow bytes and a commit range containing nothing the diagnostic imports. The
kernel table (§1) shows the same effect locally across five resident dispatch
classes. Lane A is therefore environment-dependent **and non-deterministic per
run**, which is why `V2-04a` is a diagnostic clause and `V2-04b` carries the
mandatory exactness. This also means a single green Lane A observation is never by
itself evidence of anything.

### V2-06 — Semantics re-statement

**ORIGINAL:** (unchanged)

**PROPOSED:** `calibration.json`, `scale_declaration`, model cards and manifest
wording must declare the **fitted criterion** (objective, bounds, link, solver,
stopping settings) rather than implying "L-BFGS-B output". They must state that
`calibrated_research_score` is an affine map of raw log-odds fitted on the
development OOF vector, that the calibrator was fitted on that vector and not on
the design matrix, and that the threshold 0.5 is exploratory and not clinically
validated. The §2.4 artifact-byte statement is retained.

### V2-07 — Negative tests

**ORIGINAL:** (unchanged — wrong digest, >29 cases, drifted non-calibration field,
planted second tolerance exception, solver-provenance regression,
unreachable-criterion fail-closed case, V1 pack byte-integrity)

**PROPOSED:** retain every listed case. The **unreachable-criterion** case is
reconciled explicitly: under the amended contract, the requirement is that the
criterion be **evaluable and reported** for Lane A, and that Lane B make no
criterion claim at all. The negative test therefore asserts that a missing or
non-evaluable criterion is **refused or fails closed**, rather than asserting a
property of a solver Lane B does not run.

### V2-08 — No new tolerance

**ORIGINAL:** (unchanged)

**PROPOSED:** unchanged in substance. No new numerical acceptance tolerance is
introduced anywhere. Lane B comparison is exact type-and-value. Lane A differences
are reported, never thresholded.

### Clauses preserved without change

**V2-01** (owner ratification), **V2-05** (dual-run window until owner retires V1),
**V2-09** (explicit non-claims), **V2-10** (single-revert rollback). Their original
text stands.

---

## 3. Guarantees: retained, withdrawn, not claimed

| guarantee | before | under proposal |
|---|---|---|
| Lane A produces the scientific reference | retained | retained |
| Lane A model selection reproduced from the producer | retained | retained |
| Lane A convergence is *credible and reported* | — | **added** |
| Lane A exactness across environments | required | **withdrawn** (measured differences) |
| Lane A differences classified, not concealed | — | **added** |
| Lane B exact replay, fixed artifact | retained | retained, mandatory, matrixed |
| Lane B fits nothing | retained | retained |
| Lane B "host-independent because no training" | implied | **withdrawn** as a deduction; replaced by measured invariance |
| Solver provenance from an isolated oracle | never accepted | still never accepted |
| No new numerical tolerance | retained | retained |

## 4. What ratification would and would not do

**Would:** move the cross-environment exactness requirement to the lane that can
satisfy it, with the matrix retained; require Lane A to report optimality evidence
and classify failures; correct the Lane B host-independence wording.

**Would not:** close any gate; accept RH-04; authorize production, real data or
clinical use; retire V1; or assert scientific validity.

**Required:** an owner entry in `docs/DECISIONS.md` naming the accepting reviewer
and this document's ID and version. **Not performed by the agent.**
